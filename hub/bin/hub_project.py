"""hub_project.py — 프로젝트를 발견하고 세션 뷰·티어 1 스냅샷을 프로젝트 뷰로 합성하는 순수 로직.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_project.py 대상).
디렉토리명 인코딩은 **정방향 전용**이다(역방향 디코딩은 원리적으로 모호하다 —
docs/prps/hub-dashboard.md). 세대 판정(tier1_is_previous_task)의 근거는
docs/prps/hub-session-revival-and-stale-tier1.md 결정 GN1~GN3 이 정본이다.
"""

import fnmatch
import hashlib
import re
import string
import struct
from dataclasses import dataclass
from typing import Literal, Sequence

from hub_activity import LiveActivity
from hub_live_session import LiveSessionIndex
from hub_parse import UNSET_SOURCE_PATH, Tier1Snapshot
from hub_session import SessionState, SessionView, compute_session_view
from hub_session_facts import SessionFacts
from hub_subagent import SubagentMeta
from hub_transcript import SessionTail
from hub_usage import SessionCost
from hub_workflow import WorkflowRunView

WORKTREE_PATH_MARKER = "/.claude/worktrees/"
"""Claude Code 가 만드는 워크트리의 관례 경로 마커. 이 앞이 소유 레포 루트다(결정 WT3,
docs/prps/hub-worktree-fold.md). 판정은 이 문자열 마커 절단뿐이다 — git 호출도 `.git` 파일
읽기도 하지 않는다(★순수 계약 유지)."""

DASHBOARD_KEY_LENGTH = 16          # sha256(경로) 앞 자리 수 — 대시보드 서빙용 불투명 키(결정 N1)

SESSION_DASHBOARDS_RELATIVE_DIRECTORY = ".claude/dashboards"
"""세션별 진행 기록 디렉토리(프로젝트 루트 기준). 앞에 "/" 를 붙이지 않는다 — 붙이면 pathlib 의
`/` 연산자가 뒤 조각을 절대경로로 취급해 앞부분을 통째로 버리는 함정에 걸린다(예: 루트 / 슬래시로
시작하는 조각). hub/README.md 「진행 기록」>「대시보드 경로 규칙」과 문자 단위로 같아야 한다
(T25-158, docs/prps/hub-session-tree-and-per-session-dashboards.md 결정 ST1)."""

SESSION_DASHBOARD_FILE_NAME_PATTERN = re.compile(
    r"\A(?P<session_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl\Z"
)
"""파일명 → 세션 ID. 이 정규식을 통과하지 않는 파일은 존재하지 않는 것으로 본다(결정 ST9) —
레지스트리 값이 여기서 발견된 경로로만 만들어지므로(결정 N3) 발견 단계가 곧 서빙 표면의 **경로
집합**의 경계다. 그 경로가 가리키는 바이트는 서빙 시점(hub_server.py)에 다시 해석되므로 심링크는
따라간다 — 코드로 막는 것은 이 diff 의 범위 밖이다(검수 2회차 B-1)."""

# 앞이 이긴다 — 하나라도 working 이면 프로젝트는 working. interrupted 는 working 다음·idle
# 앞이다(결정 RI9, docs/prps/hub-rate-limit-interruption.md) — 살아 있다는 증거가 working
# 다음으로 강한 신호이고(SO1), idle 보다 앞인 이유는 사용자의 판단이 필요한 상태이기 때문이다.
# background 는 interrupted 다음·idle 앞이다(결정 BW8, docs/prps/
# hub-subagent-background-pause.md) — 할 일은 없지만 일이 진행 중이다("사용자 판단
# 필요" 뒤, "사용자 차례" 앞).
PROJECT_STATE_PRIORITY: tuple[SessionState, ...] = ("working", "interrupted", "background", "idle", "stale", "done")

# 살아 있는 세션 = 지금 이 프로젝트에서 실제로 일하고 있는 세션(결정 GN2,
# docs/prps/hub-session-revival-and-stale-tier1.md). stale·done 을 넣지 않는다 — 부활 규칙(RV1)이
# 만드는 좀비 stale 세션이 세대 판정(is_tier1_from_previous_task)을 조용히 깨뜨린다(실측 E6).
# background 를 넣는다(결정 BW8) — 빼면 대시보드를 쓴 세션 A 가 백그라운드 대기 중이고 뒤에
# 시작한 세션 B 가 working 일 때 살아 있는 세션이 B 뿐이라 tier1_is_previous_task 가 켜져
# A 의 진행 중 대시보드가 「이전 작업」으로 톤다운된다.
LIVE_SESSION_STATES: frozenset[SessionState] = frozenset({"working", "background"})


# ---- 표시(view) ----
@dataclass(frozen=True)
class ProjectView:
    """프로젝트 하나의 화면 표시 상태 — 소속 세션과 티어 1 스냅샷을 합성한 것."""

    display_name: str
    path: str | None
    tier: Literal[1, 2, 3]
    state: SessionState
    last_activity_at_ms: int
    sessions: tuple[SessionView, ...]
    tier1: Tier1Snapshot | None
    note: str | None
    dashboard_key: str | None = None    # 티어 1 프로젝트만 값을 갖는다. None 이면 카드가 클릭 대상이 아니다
    # 티어 1 파일이 "지금 일하는 세션보다 오래된" 세대인가(결정 GN1~GN3).
    # 이름에 stale 을 쓰지 않는다 — 세션의 stale(30분 무소식)·사용량의 is_stale(조회되지 않음)과
    # 뜻이 다르다.
    tier1_is_previous_task: bool = False
    # 카드가 열 티어 1 파일이 어떤 세션의 *끝난 작업* 대시보드인가(결정 CD1·CD2,
    # docs/prps/hub-session-list-and-glow-fixes.md §3). SessionView.tier1_is_finished_task
    # 와 같은 이름을 쓴다 — 담체만 다를 뿐 같은 판정이기 때문이다. tier1_is_previous_task
    # 와는 독립적인 판정이다(그쪽은 다른 세션이 남긴 대시보드를 겨냥한다) — 둘이 동시에
    # 참일 수 있다(FT6). 맨 뒤, 기본값 있음.
    tier1_is_finished_task: bool = False


# ---- 프로젝트 발견 — 정방향 인코딩 전용 ----
# 프로젝트 폴더 이름 규칙은 Claude Code 호스트의 함수를 그대로 옮긴 것이다(번들 2.1.108·2.1.281·2.1.284 세
# 곳이 같다, docs/prps/hub-agent-title-and-excerpt-freshness.md §16 N1). 호스트 원문:
#   name = path.replace(/[^a-zA-Z0-9]/g, "-")
#   name.length <= 200 ? name : `${name.slice(0, 200)}-${Math.abs(hash(path)).toString(36)}`
#   hash: h = 0; for each charCodeAt c: h = (h << 5) - h + c | 0      (자바 String.hashCode 와 같다)
# JS 문자열은 UTF-16 이라 치환·길이·해시가 모두 코드 유닛 단위다 — BMP 밖 문자(이모지 등)는 2유닛이다.
PROJECT_DIR_NAME_MAX_LENGTH = 200       # 호스트가 이름을 자르고 경로 해시를 붙이기 시작하는 길이(넘을 때만)
ASCII_ALPHANUMERIC_CHARACTERS = frozenset(string.ascii_letters + string.digits)
UTF16_CODE_UNIT_BYTES = 2
JAVA_HASH_MULTIPLIER = 31               # (h << 5) - h == h * 31
UNSIGNED_32_BIT_MODULUS = 1 << 32
SIGNED_32_BIT_LIMIT = 1 << 31           # 이 값 이상의 32비트 패턴은 음수다(JS 의 `| 0`)
BASE36_DIGITS = string.digits + string.ascii_lowercase
PATH_GLOB_TOKEN_PATTERN = re.compile(r"(\[!?|[*?\]])")
"""fnmatch 와일드카드 토큰(`*`·`?`·`[`·`[!`·`]`). 캡처 그룹이라 `split` 이 토큰을 결과에 남긴다."""


def _utf16_code_units(text: str) -> tuple[int, ...]:
    """JS `charCodeAt` 열 — BMP 밖 문자는 서로게이트 쌍 2유닛이고, 짝 없는 서로게이트도 그대로 1유닛이다."""
    utf16_bytes = text.encode("utf-16-le", "surrogatepass")
    return struct.unpack(f"<{len(utf16_bytes) // UTF16_CODE_UNIT_BYTES}H", utf16_bytes)


def _dash_non_alphanumeric_code_units(text: str) -> str:
    """코드 유닛마다 ASCII 영숫자가 아니면 `-` 로 바꾼다(호스트의 `replace(/[^a-zA-Z0-9]/g, "-")`)."""
    characters = (chr(code_unit) for code_unit in _utf16_code_units(text))
    return "".join(
        character if character in ASCII_ALPHANUMERIC_CHARACTERS else "-" for character in characters
    )


def _java_string_hash(text: str) -> int:
    """자바 String.hashCode 와 같은 부호 있는 32비트 해시(호스트의 `(h << 5) - h + c | 0` 누적)."""
    unsigned_hash = 0
    for code_unit in _utf16_code_units(text):
        unsigned_hash = (unsigned_hash * JAVA_HASH_MULTIPLIER + code_unit) % UNSIGNED_32_BIT_MODULUS
    if unsigned_hash >= SIGNED_32_BIT_LIMIT:
        return unsigned_hash - UNSIGNED_32_BIT_MODULUS
    return unsigned_hash


def _to_base36(non_negative_number: int) -> str:
    """JS `Number.prototype.toString(36)` — 소문자 0-9a-z."""
    if non_negative_number == 0:
        return BASE36_DIGITS[0]
    reversed_digits = []
    remaining = non_negative_number
    while remaining:
        remaining, digit_value = divmod(remaining, len(BASE36_DIGITS))
        reversed_digits.append(BASE36_DIGITS[digit_value])
    return "".join(reversed(reversed_digits))


def encode_project_dir_name(absolute_path: str) -> str:
    """절대경로를 ~/.claude/projects 의 디렉토리명으로 인코딩한다(정방향 전용).

    Claude Code 호스트의 규칙 그대로다: ASCII 영숫자가 아닌 글자는 전부 `-` 로 바꾸고(`/`·`.`·`_`·공백·
    한글 포함, 연속돼도 합치지 않는다), 그 이름이 200자를 넘으면 앞 200자 뒤에 `-` 와 **원래 경로**의
    해시(절댓값, 36진수)를 붙인다. 이 함수는 받은 그대로 인코딩하고 유니코드 정규화를 하지 않는다 —
    훅이 주는 cwd 는 호스트가 이미 NFC 로 고정해 두지만, 루트 스캔으로 들어온 경로가 파일시스템의
    NFD 저장형이면 한글 등의 글자 수가 달라 빗나간다. 서로 다른 경로가 같은 이름으로 접히면
    (`/w/a_b`·`/w/a.b`·`/w/a b` → `-w-a-b`) 호스트도 같은 폴더를 공유하고, `resolve_project_dirs` 는
    그중 마지막 후보를 고른다.
    """
    encoded_name = _dash_non_alphanumeric_code_units(absolute_path)
    if len(encoded_name) <= PROJECT_DIR_NAME_MAX_LENGTH:
        return encoded_name
    path_hash = _to_base36(abs(_java_string_hash(absolute_path)))
    return f"{encoded_name[:PROJECT_DIR_NAME_MAX_LENGTH]}-{path_hash}"


def encode_path_glob_to_project_dir_glob(path_glob: str) -> str:
    """경로 glob(ignore_globs)을 프로젝트 디렉토리명에 대고 쓸 glob 으로 바꾼다.

    리터럴 글자는 `encode_project_dir_name` 과 같은 규칙으로 `-` 로 바꾸고, 와일드카드 토큰은 그대로
    둔다 — 호스트 규칙은 영숫자가 아니면 전부 바꾸므로 `*` 까지 `-` 가 돼 와일드카드가 죽는다(옛 규칙은
    `/`·`.` 만 바꿔 `*` 가 저절로 남았다). 패턴은 실제 경로가 아니라서 200자 절단·해시는 붙이지 않는다.
    대괄호 안의 비영숫자 리터럴은 지원 범위 밖이다 — `[a_b]` 는 `[a-b]` 범위가 돼 뜻이 바뀐다.
    """
    pieces = PATH_GLOB_TOKEN_PATTERN.split(path_glob)
    # `split` 은 와일드카드 토큰을 홀수 위치에, 그 사이의 리터럴을 짝수 위치에 돌려준다.
    return "".join(
        piece if index % 2 == 1 else _dash_non_alphanumeric_code_units(piece)
        for index, piece in enumerate(pieces)
    )


def resolve_project_dirs(
    encoded_names: Sequence[str], candidate_paths: Sequence[str]
) -> tuple[dict[str, str], tuple[str, ...]]:
    """인코딩 디렉토리명 → 절대경로 매칭 결과와, 매칭되지 않은 이름들을 돌려준다."""
    encoded_to_path = {encode_project_dir_name(path): path for path in candidate_paths}
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for name in encoded_names:
        if name in encoded_to_path:
            resolved[name] = encoded_to_path[name]
        else:
            unresolved.append(name)
    return resolved, tuple(unresolved)


def should_ignore_cwd(cwd: str, ignore_globs: Sequence[str]) -> bool:
    """cwd 가 무시 패턴(worktree·scratchpad 등)에 해당하는지 판정한다."""
    return any(fnmatch.fnmatch(cwd, pattern) for pattern in ignore_globs)


def fold_worktree_path(path: str) -> str:
    """워크트리 경로를 소유 레포 루트로 접는다. 워크트리가 아니면 원본 그대로.

    절단은 `find`(첫 번째 마커)다 — 마커가 여러 번 나오면(중첩 워크트리) **첫 번째**에서
    잘라 최외곽 레포까지 한 번에 접는다. `rfind` 를 쓰면 중첩 워크트리에서 여전히 워크트리
    경로가 남아 뒤이은 ignore 판정에 걸려 세션이 사라진다(결정 WT3, U-4 가 이 방향을 못 박는다).
    """
    marker_index = path.find(WORKTREE_PATH_MARKER)
    if marker_index == -1:
        return path
    return path[:marker_index]


def group_paths_by_repo_root(paths: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """경로들을 소유 레포 루트별로 묶는다.

    키는 접힌 루트, 값은 **접기 전 원본 경로들**이며 순서는 `(루트, 워크트리…사전순)` 이다.
    루트는 입력에 없어도 언제나 첫 원소로 들어간다 — 레포 루트의 dashboard.html 은 그 레포에
    세션이 없어도 티어 1 후보이기 때문이다. 이 순서가 티어 1 동률 처리의 근거다(결정 WT6).
    """
    worktree_members_by_root: dict[str, list[str]] = {}
    for path in paths:
        root = fold_worktree_path(path)
        worktree_members_by_root.setdefault(root, [])
        if path != root:
            worktree_members_by_root[root].append(path)
    return {
        root: (root, *sorted(members))
        for root, members in worktree_members_by_root.items()
    }


def plan_tier1_candidates(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    scanned_paths: Sequence[str],
    ignore_globs: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    """세션 관측 cwd·스캔 경로를 소유 레포 루트별 티어 1 후보 멤버로 묶는다(결정 WT2·WT5·WT16·WT17).

    fold 가 ignore 보다 먼저다 — **접힌 루트에 대해서만** 무시 패턴을 판정해야 워크트리 경로가
    `ignore_globs` 기본값(`**/.claude/worktrees/**`)에 걸려 티어 1 후보 확장이 죽지 않는다
    (검수 1회차 M1 — 이 조립을 `collect_snapshot` 안에 그대로 두면 `mock.patch` 로 우회되는
    통합 테스트에서만 검증돼 실질적으로 아무 테스트도 이 배선을 실행하지 않았다).

    후보 입력은 `SessionFacts.observed_cwds`(이 창에서 실제 관측된 cwd 전부)다(결정 WT16) —
    `facts.cwd` 하나만 보면 그 값이 창 안 **최초 이벤트**로 고정돼(결정 WT14) `EnterWorktree`
    이후의 워크트리 이동이 후보에 반영될 길이 없다(2판 결함 A, E11). `sessions_by_path` 의
    키는 이미 접힌 루트다(결정 WT14).

    **앵커 규칙**(`root in anchors`, 결정 WT17) — 관측 cwd 는 멤버만 늘리고 루트를 새로 만들지
    않는다. 앵커는 오늘의 그룹 키 집합(`sessions_by_path`)과 접힌 스캔 경로뿐이다. 이 조건이
    없으면 프로젝트 **하위 디렉토리** 같은 관측 cwd 가 새 루트가 돼 한 프로젝트가 카드 둘로
    쪼개진다(E14) — 그런 입력이 실데이터에 존재한다.

    빈 문자열 루트는 후보에서 제외한다(검수 1회차 m5) — `fold_worktree_path` 는 워크트리 마커가
    경로 맨 앞에 오는 입력(예: `"/.claude/worktrees/w"`)에서 빈 문자열을 만들 수 있는데, 빈
    문자열은 `should_ignore_cwd` 를 그냥 통과해 `read_session_dashboard_snapshots` 이 프로세스
    CWD 기준 상대경로를 참조하게 만든다.
    """
    anchors = set(sessions_by_path) | {fold_worktree_path(path) for path in scanned_paths}
    observed_paths = {
        cwd
        for group in sessions_by_path.values()
        for facts in group
        for cwd in facts.observed_cwds
    }
    observed_paths |= set(scanned_paths)
    members_by_root = group_paths_by_repo_root(sorted(observed_paths))
    return {
        root: members
        for root, members in members_by_root.items()
        if root and root in anchors and not should_ignore_cwd(root, ignore_globs)
    }


# ---- 프로젝트 합성 ----
def _display_name(path: str) -> str:
    trimmed = path.rstrip("/")
    return trimmed.rsplit("/", 1)[-1] if trimmed else path


def _project_tier(tier1: Tier1Snapshot | None, sessions: tuple[SessionFacts, ...]) -> int:
    if tier1 is not None:
        return 1
    return 2 if sessions else 3


def _project_state_without_sessions(last_activity_at_ms: int, now_ms: int, stale_after_ms: int) -> SessionState:
    """세션이 하나도 없는 프로젝트(티어 1/3 전용)의 상태.

    `done` 은 `SessionEnd` 를 관측했고 그 뒤 재부착(`SessionStart`, compact 제외)이 없을
    때만 성립하는 상태다(결정 RV3) — 세션이 없으면 그 근거가 없으므로 마지막 활동 시각만으로
    idle/stale 을 가른다(검수 M3, docs/prps/hub-dashboard.md 「상태 판정 규칙 4」 참조).
    """
    if now_ms - last_activity_at_ms >= stale_after_ms:
        return "stale"
    return "idle"


def _project_state(
    session_views: tuple[SessionView, ...], last_activity_at_ms: int, now_ms: int, stale_after_ms: int
) -> SessionState:
    if not session_views:
        return _project_state_without_sessions(last_activity_at_ms, now_ms, stale_after_ms)
    ranked = sorted(session_views, key=lambda view: PROJECT_STATE_PRIORITY.index(view.state))
    return ranked[0].state


def _last_activity_at_ms(
    tier1: Tier1Snapshot | None, session_views: tuple[SessionView, ...], tier3_mtime: int
) -> int:
    candidates = [tier3_mtime]
    if tier1 is not None:
        candidates.append(tier1.file_mtime_ms)
    candidates.extend(view.last_event_at_ms for view in session_views)
    return max(candidates)


def _opaque_key(text: str) -> str:
    """문자열 → 불투명 식별자(sha256 앞 16자리, 결정 N1). `project_dashboard_key`·`dashboard_file_key`
    가 공유하는 유일한 해시 규칙이다(결정 ST13) — 규칙이 하나뿐이라 두 키가 서로 어긋날 수 없다.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:DASHBOARD_KEY_LENGTH]


def project_dashboard_key(project_path: str) -> str:
    """프로젝트 절대경로 → 대시보드 서빙용 불투명 키(sha256 앞 16자리 hex, 결정 N1).

    `encode_project_dir_name` 과 달리 서로 다른 두 경로가 같은 키가 되는 충돌이 실질적으로
    없고, 문자 집합이 `[0-9a-f]` 뿐이라 경로로 오독될 여지가 없다.
    """
    return _opaque_key(project_path)


# ---- 세션별 대시보드 발견·서빙 (결정 ST9·ST12·ST13·ST14) ----
def session_id_from_dashboard_file_name(file_name: str) -> str | None:
    """`<uuid>.jsonl` 이면 uuid, 아니면 None."""
    match = SESSION_DASHBOARD_FILE_NAME_PATTERN.match(file_name)
    return match["session_id"] if match else None


def session_dashboard_relative_path(session_id: str) -> str:
    """세션별 진행 기록의 프로젝트 루트 기준 상대경로. 예: `.claude/dashboards/<id>.jsonl`."""
    return f"{SESSION_DASHBOARDS_RELATIVE_DIRECTORY}/{session_id}.jsonl"


def tier1_file_path(tier1: Tier1Snapshot) -> str:
    """스냅샷이 읽힌 파일의 절대경로 — 레지스트리 값의 유일한 조립 지점(결정 WT8 확장, ST14).

    항상 세션별 파일 경로다(HD7, docs/prps/dashboard-into-hub.md — 레거시 단일 파일 갈래는
    폐기됐다). `dashboard_file_key` 도 이 함수가 돌려준 같은 문자열을 해시하므로 키와 값이
    한 함수의 출력이라 서로 어긋날 수 없다 — "카드에 보이는 진행률과 클릭해서 열리는 파일이
    다른 파일"(T25-113 이 막는 결함)이 세션에서 재발하지 않는다.
    """
    return f"{tier1.source_path}/{session_dashboard_relative_path(tier1.session_id)}"


def dashboard_file_key(absolute_file_path: str) -> str:
    """파일 절대경로 → 서빙용 불투명 키(sha256 앞 16자리). `project_dashboard_key` 와 같은
    해시 규칙(`_opaque_key`)을 공유한다(결정 ST13) — 두 키가 같은 16자리 hex 공간에 산다.
    """
    return _opaque_key(absolute_file_path)


def index_session_dashboards(snapshots: Sequence[Tier1Snapshot]) -> dict[str, Tier1Snapshot]:
    """세션 ID 별 mtime 최신 스냅샷. `session_id` 가 `None` 인 것(레거시)은 넣지 않는다.

    같은 세션의 파일이 루트·워크트리 양쪽에 있으면 mtime 최신이 승자다(WT6 과 같은 규칙).
    엄격한 비교(`>`)만 쓰므로 동률이면 먼저 만난 스냅샷이 유지된다 — `select_tier1_source` 의
    `max` 동률 처리(목록 앞이 이긴다)와 같은 이유다.
    """
    winner_by_session_id: dict[str, Tier1Snapshot] = {}
    for snapshot in snapshots:
        if snapshot.session_id is None:
            continue
        current_winner = winner_by_session_id.get(snapshot.session_id)
        if current_winner is None or snapshot.file_mtime_ms > current_winner.file_mtime_ms:
            winner_by_session_id[snapshot.session_id] = snapshot
    return winner_by_session_id


def select_tier1_source(candidates: Sequence[Tier1Snapshot]) -> Tier1Snapshot | None:
    """티어 1 후보 중 파일 mtime 이 가장 새로운 것을 고른다. 동률이면 목록 앞이 이긴다(결정 WT6).

    파이썬 `max` 는 동률일 때 **먼저 나온 원소**를 유지하므로, 후보를 `(레포 루트, 워크트리…)`
    순서로 넘기면 동률 시 레포 루트가 자연히 이긴다(`group_paths_by_repo_root` 의 순서 계약).
    """
    if not candidates:
        return None
    return max(candidates, key=lambda snapshot: snapshot.file_mtime_ms)


def is_tier1_from_previous_task(
    tier1_file_mtime_ms: int, live_session_start_times_ms: Sequence[int]
) -> bool:
    """살아 있는 세션이 있고, 그 전부가 대시보드 파일이 갱신된 뒤에 시작됐는가(결정 GN1).

    경계는 엄격한 `>` 다 — 같은 밀리초에 시작·갱신됐다면 그 세션이 갱신했다고 본다.
    `all()` 은 한 세션이라도 대시보드보다 먼저 시작했으면 라벨을 켜지 않는다(오탐 회피 방향).
    """
    if not live_session_start_times_ms:
        return False
    return all(start_ms > tier1_file_mtime_ms for start_ms in live_session_start_times_ms)


def is_project_tier1_from_finished_session_task(
    tier1: Tier1Snapshot | None, session_views: Sequence[SessionView]
) -> bool:
    """카드가 열 티어 1 파일이 어떤 세션의 *끝난 작업* 대시보드인가(결정 CD1,
    docs/prps/hub-session-list-and-glow-fixes.md §3).

    세션 판정(SessionView.tier1_is_finished_task)을 프로젝트 담체로 들어 올리기만
    한다 — 새 임계값도 새 술어도 만들지 않는다. `tier1.session_id` 대조가 정확한 이유:
    `index_session_dashboards` 는 세션별 mtime 최대를, `select_tier1_source` 는 전체
    후보 중 mtime 최대를 고르는 같은 규칙이라, 전체 최대가 한 세션의 파일이면 그것은
    곧 그 세션의 최대이기도 하다 — 두 승자는 같은 스냅샷이다. `session_id` 가 없으면
    (레거시 단일 파일) 세션 귀속이 원리적으로 불가능해 항상 False 다.
    """
    if tier1 is None or tier1.session_id is None:
        return False
    return any(
        view.session_id == tier1.session_id and view.tier1_is_finished_task
        for view in session_views
    )


def _live_session_start_times_ms(
    sessions: tuple[SessionFacts, ...], session_views: tuple[SessionView, ...], tier1_source_path: str
) -> tuple[int, ...]:
    """살아 있는 세션들의 시작 시각. 표시 상태는 뷰가, 시작 시각은 사실이 갖고 있다.

    `sessions` 와 `session_views` 는 `compose_project_views` 안에서 같은 순서로 만들어지므로
    `zip` 이 안전하다 — 두 튜플을 함수 밖으로 넘겨 다시 조립하지 않는다.

    `tier1_source_path` 가 `facts.observed_cwds` 에 있는 세션만 담는다(결정 WT18, WT9 재개정) —
    기록기는 cwd 상대경로에만 쓰므로, 그 파일을 갱신하는 주체는 그 cwd 에서 일한 적
    있는 세션뿐이다. `facts.cwd`(창 안 최초 이벤트의 cwd, 결정 WT14)로 비교하면 워크트리로
    이동한 세션은 그 값이 레포 루트로 남아 있어 승자가 워크트리 파일일 때 일치하는 세션이
    0 이 되고, 판정이 `if not live: return False` 분기로 우연히 맞는 상태가 된다(E15). 워크트리가
    없는 프로젝트는 `observed_cwds == (cwd,)` 라 이 조건이 완전한 무동작이다.
    """
    return tuple(
        facts.started_at_ms
        for facts, view in zip(sessions, session_views)
        if view.state in LIVE_SESSION_STATES and tier1_source_path in facts.observed_cwds
    )


def _session_dashboard_key(tier1: Tier1Snapshot | None) -> str | None:
    """세션 자신의 대시보드 서빙 키(결정 ST12). 파일이 없거나 `source_path` 가 미설정이면 None.

    `UNSET_SOURCE_PATH` 가드는 `hub_model._register_dashboard` 와 같은 불변식을 강제한다
    (검수 2회차 B-3) — 이 가드가 없으면 레지스트리 등록은 거부되는데 키는 채워져, 클릭하면
    404 로 이어지는 링크가 된다. 불변식이 두 지점(여기·hub_model)에서 각각 강제되는 이유는
    `tier1_file_path` 한 곳으로 모으려면 그 함수의 반환 타입을 `str | None` 으로 바꿔야 해서
    (공개 인터페이스 변경) 이 진단(Minor)의 범위를 넘기 때문이다.
    """
    if tier1 is None or tier1.source_path == UNSET_SOURCE_PATH:
        return None
    return dashboard_file_key(tier1_file_path(tier1))


def _session_views_for_path(
    sessions: tuple[SessionFacts, ...],
    session_dashboards: tuple[Tier1Snapshot, ...],
    tail_by_session_id: dict[str, SessionTail],
    workflow_by_session_id: dict[str, WorkflowRunView],
    subagent_meta_by_agent_id: dict[str, SubagentMeta],
    subagent_activity_by_agent_id: dict[str, int],
    now_ms: int,
    stale_after_ms: int,
    is_dashboard_enabled: bool,
    live_roster: LiveSessionIndex | None = None,
    live_activity: LiveActivity | None = None,
    session_cost_by_session_id: dict[str, SessionCost] | None = None,
) -> tuple[SessionView, ...]:
    """한 프로젝트 경로의 세션 사실들을 표시 뷰로 접는다.

    세션별 대시보드는 세션당 승자 1개로 색인해(`index_session_dashboards`) 자기 것만
    싣는다(결정 ST12) — 다른 세션의 파일이 섞이지 않는다. `workflow_by_session_id` 는
    hub_collect.read_session_workflows 가 미리 모아 넘긴 값을 세션별로 그대로 실어
    나르기만 한다(결정 WF1). `tail_by_session_id` 는 같은 관례로 모델·마지막 프롬프트·
    마지막 턴의 API 오류(`turn_failure`, 결정 RI1)를 한 번에 나른다(결정 PS3 — 같은 꼬리
    읽기 한 번에서 나온 값들이 드리프트하지 않게 묶음으로 전달한다). 판단은 하지 않는다 —
    `tail.turn_failure` 를 `compute_session_view` 의 `transcript_turn_failure` 인자로, `tail.last_human_prompt_at_ms`
    를 `last_human_prompt_at_ms` 인자로 그대로 넘길 뿐이다. `subagent_meta_by_agent_id`·`subagent_activity_by_agent_id` 는
    세션에 스코프되지 않는 전역 맵이다 — 어느 세션의 실행이든 자기 agent_id 로만
    조회하므로 그대로 넘긴다(후자는 결정 SL6 — 전자와 완전히 같은 경로).
    `is_dashboard_enabled` 은 이 프로젝트 경로의 진행 기록 오프 스위치 값(결정 RL10,
    `/hub dashboard off`)이다 — 이 함수는 판단 없이 compute_session_view 에 그대로 넘긴다
    (live_roster 와 같은 관례).
    `live_roster` 도 세션에 스코프되지 않는 전역 인덱스다 — compute_session_view 가
    session_id 로 직접 조회하므로 판단 없이 그대로 넘긴다(결정 LS2). `live_activity` 도 같은 전역 묶음이다 —
    compute_session_view 가 agent_id·session_id 로 직접 조회한다(결정 LA14, SL6 과 같은 모양의 통과 배선).
    `session_cost_by_session_id` 는 hub_collect 가 캡처 파일에서 미리 읽어 넘긴 세션별 비용이다(⑨) — 세션 id 로 찾아 그대로 싣는다.
    """
    session_cost_by_session_id = session_cost_by_session_id or {}
    session_dashboards_by_id = index_session_dashboards(session_dashboards)
    views = []
    for facts in sessions:
        tail = tail_by_session_id.get(facts.session_id)
        views.append(
            compute_session_view(
                facts,
                now_ms,
                stale_after_ms,
                model=tail.model if tail else None,
                tier1=session_dashboards_by_id.get(facts.session_id),
                dashboard_key=_session_dashboard_key(session_dashboards_by_id.get(facts.session_id)),
                workflow=workflow_by_session_id.get(facts.session_id),
                task_excerpt=tail.last_prompt if tail else None,
                subagent_meta_by_agent_id=subagent_meta_by_agent_id,
                subagent_activity_by_agent_id=subagent_activity_by_agent_id,
                is_dashboard_enabled=is_dashboard_enabled,
                live_roster=live_roster,
                transcript_turn_failure=tail.turn_failure if tail else None,
                live_activity=live_activity,
                last_human_prompt_at_ms=tail.last_human_prompt_at_ms if tail else None,
                session_cost=session_cost_by_session_id.get(facts.session_id),
            )
        )
    return tuple(views)


def _project_view_for_path(
    path: str,
    tier1_by_path: dict[str, Tier1Snapshot],
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    tier3_last_activity_by_path: dict[str, int],
    session_dashboards_by_path: dict[str, tuple[Tier1Snapshot, ...]],
    tail_by_session_id: dict[str, SessionTail],
    workflow_by_session_id: dict[str, WorkflowRunView],
    subagent_meta_by_agent_id: dict[str, SubagentMeta],
    subagent_activity_by_agent_id: dict[str, int],
    now_ms: int,
    stale_after_ms: int,
    dashboard_enabled_by_path: dict[str, bool],
    live_roster: LiveSessionIndex | None = None,
    live_activity: LiveActivity | None = None,
    session_cost_by_session_id: dict[str, SessionCost] | None = None,
) -> ProjectView:
    """`compose_project_views` 의 all_paths 순회 1건을 ProjectView 1개로 합성한다.
    compose_project_views 를 50줄 제한 안에 두려고 뽑았다(재검수 1회차 M4) — 새 판단은
    없고, 세션 뷰 합성 결과를 티어·상태·마지막 활동 판정 호출에 그대로 실어 나른다.
    """
    tier1 = tier1_by_path.get(path)
    sessions = sessions_by_path.get(path, ())
    # dashboard_enabled_by_path 는 tier3_last_activity_by_path 와 같은 관례(경로별 dict,
    # 호출자가 .get(path, ...) 로 직접 조회) — 값이 없으면 켜짐(결정 RL10 의 페일 방향).
    # compose_project_views 가 이미 or {} 로 정규화해 넘긴다(tail_by_session_id 등과 동일).
    is_dashboard_enabled = dashboard_enabled_by_path.get(path, True)
    session_views = _session_views_for_path(
        sessions,
        session_dashboards_by_path.get(path, ()),
        tail_by_session_id,
        workflow_by_session_id,
        subagent_meta_by_agent_id,
        subagent_activity_by_agent_id,
        now_ms,
        stale_after_ms,
        is_dashboard_enabled,
        live_roster,
        live_activity,
        session_cost_by_session_id,
    )
    tier1_source_path = tier1.source_path if tier1 is not None else UNSET_SOURCE_PATH
    live_session_start_times_ms = _live_session_start_times_ms(sessions, session_views, tier1_source_path)
    tier1_is_previous_task = tier1 is not None and is_tier1_from_previous_task(
        tier1.file_mtime_ms, live_session_start_times_ms
    )
    tier1_is_finished_task = is_project_tier1_from_finished_session_task(tier1, session_views)
    last_activity_at_ms = _last_activity_at_ms(
        tier1, session_views, tier3_last_activity_by_path.get(path, 0)
    )
    tier = _project_tier(tier1, sessions)
    return ProjectView(
        display_name=_display_name(path),
        path=path,
        tier=tier,
        state=_project_state(session_views, last_activity_at_ms, now_ms, stale_after_ms),
        last_activity_at_ms=last_activity_at_ms,
        sessions=session_views,
        tier1=tier1,
        note=None,
        dashboard_key=project_dashboard_key(path) if tier == 1 else None,
        tier1_is_previous_task=tier1_is_previous_task,
        tier1_is_finished_task=tier1_is_finished_task,
    )


def compose_project_views(
    tier1_by_path: dict[str, Tier1Snapshot],
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    tier3_last_activity_by_path: dict[str, int],
    now_ms: int,
    stale_after_ms: int,
    tail_by_session_id: dict[str, SessionTail] | None = None,
    session_dashboards_by_path: dict[str, tuple[Tier1Snapshot, ...]] | None = None,
    workflow_by_session_id: dict[str, WorkflowRunView] | None = None,
    subagent_meta_by_agent_id: dict[str, SubagentMeta] | None = None,
    subagent_activity_by_agent_id: dict[str, int] | None = None,
    dashboard_enabled_by_path: dict[str, bool] | None = None,
    live_roster: LiveSessionIndex | None = None,
    live_activity: LiveActivity | None = None,
    session_cost_by_session_id: dict[str, SessionCost] | None = None,
) -> tuple[ProjectView, ...]:
    """세 티어의 사실을 프로젝트별로 합성해 화면 표시 뷰를 만든다. 정렬은 마지막 활동 내림차순.

    `tail_by_session_id`·`workflow_by_session_id`·`subagent_meta_by_agent_id` 는 이 함수가
    계산하지 않는다 — transcript 꼬리 읽기·워크플로우 파일 읽기·서브에이전트 메타 읽기는
    전부 I/O 라 hub_collect.read_session_tails·read_session_workflows·hub_subagent_read.
    read_subagent_metas 가 미리 모아 넘긴다(`tier3_last_activity_by_path` 를 이미 이 방식으로
    받고 있어 새 패턴이 아니다). 값을 못 찾은 세션은 딕셔너리에 키 자체가 없으므로
    `.get(...)` 이 자연히 None 을 돌려준다. `session_dashboards_by_path` 도 같은 관례다 —
    세션별 파일 발견(I/O)은 hub_collect 가 하고, 여기서는 세션당 승자 1개만 골라 SessionView
    에 싣는다(결정 ST12). `tail_by_session_id` 는 결정 PS3(docs/prps/
    hub-agent-runs-and-prompt-source.md)로 옛 `model_by_session_id` 를 대체한다 — 모델과
    마지막 프롬프트가 같은 꼬리 읽기 한 번에서 나오므로 딕셔너리 하나로 묶어 나른다(둘로
    나르면 호출부마다 따로 전달돼 드리프트한다). `subagent_activity_by_agent_id` 는
    hub_subagent_read.read_unfinished_subagent_activity 가 미리 읽어 넘긴, 미종료 실행의
    transcript 마지막 기록 시각이다(결정 SL4·SL6, docs/prps/hub-subagent-liveness-signal.md)
    — `subagent_meta_by_agent_id` 와 완전히 같은 경로다. `dashboard_enabled_by_path` 는
    프로젝트 경로별 진행 기록 오프 스위치(`/hub dashboard off`) 값이다(결정 RL10, docs/prps/
    hub-card-gate-and-run-list-reset.md §5.1) — hub_collect.read_dashboard_enabled 가
    프로젝트 루트마다 미리 읽어 넘긴다. `tier3_last_activity_by_path` 와 같은 관례(경로별
    dict, 값이 없으면 켜짐)이고, 판단 없이 compute_session_view 의 실행 목록 경계 판정에만
    실어 나른다(뷰에는 싣지 않는다 — `live_roster` 와 같은 계열). `live_roster` 는 hub_collect.
    _read_session_annotations 가 hub_live_session_read.read_live_session_roster 로 미리
    읽어 넘긴 살아있는 세션 명부다(결정 LS2·LS4, docs/prps/hub-live-session-native-source.md)
    — 다른 보강 인자와 달리 뷰에 실리지 않고 compute_session_view 의 상태 판정에만 쓰인다.
    `live_activity` 는 hub_collect._read_session_annotations 가 hub_subagent_read.read_live_activity 로 미리 읽어 넘긴
    활동 묶음이다(결정 LA14, docs/prps/hub-live-activity.md) — 판단 없이 세션 뷰까지 실어 나른다.
    `session_cost_by_session_id` 는 hub_collect 가 hub_session_cost.read_session_costs 로 미리 읽어 넘긴 세션별 statusLine 비용 캡처다
    (⑨, docs/prps/harness-benchmark-adoption.md) — 판단 없이 세션 뷰까지 실어 나른다.
    기본값 None 은 기존 호출부를 무해하게 둔다.
    """
    tail_by_session_id = tail_by_session_id or {}
    session_dashboards_by_path = session_dashboards_by_path or {}
    workflow_by_session_id = workflow_by_session_id or {}
    subagent_meta_by_agent_id = subagent_meta_by_agent_id or {}
    subagent_activity_by_agent_id = subagent_activity_by_agent_id or {}
    dashboard_enabled_by_path = dashboard_enabled_by_path or {}
    all_paths = set(tier1_by_path) | set(sessions_by_path) | set(tier3_last_activity_by_path)
    views = [
        _project_view_for_path(
            path, tier1_by_path, sessions_by_path, tier3_last_activity_by_path,
            session_dashboards_by_path, tail_by_session_id, workflow_by_session_id,
            subagent_meta_by_agent_id, subagent_activity_by_agent_id, now_ms, stale_after_ms,
            dashboard_enabled_by_path, live_roster, live_activity, session_cost_by_session_id,
        )
        for path in all_paths
    ]
    return tuple(sorted(views, key=lambda view: view.last_activity_at_ms, reverse=True))
