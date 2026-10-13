"""hub_collect.py — I/O 레이어. 프로젝트 발견 · 3티어 읽기 · 스냅샷 조립 · hub.html 원자적 쓰기.

hub_model.py·hub_session.py·hub_session_facts.py·hub_project.py·hub_parse.py·
hub_transcript.py(순수)의 결과를 조립해 ~/.claude/hub/hub.html 을 만든다. collect_snapshot
파이프라인 안에서 파일시스템에 닿는 로직의 핵심은 이 모듈이 갖되, 워크플로우 실행 기록
읽기만은 hub_workflow_read.py(I/O 위성 모듈)로 분리돼 있다 — hub_collect.py 가 800/800줄
상한에 닿아 신규 함수를 더 얹을 여유가 없었다(구현 2회차 검수 A-1, docs/prps/
hub-model-module-split.md 의 800줄 분리 선례와 같은 이유). hub_usage_fetch.py(I/O, 별도
프로세스에서만 호출)와 달리 hub_workflow_read.py 는 이 파이프라인 **안**에서 호출된다.

main(세션 트리)과 워크플로우 가시성을 리베이스로 통합하며 849줄이 되어 800줄 상한을 다시
넘었다 — config 스키마·검증(순수 로직)은 hub_config.py 로, 원자적 쓰기 유틸은
hub_atomic_write.py 로 옮겨 800줄 상한 아래로 되돌렸다(docs/prps/hub-collect-split-for-merge.md).
CONFIG_PATH·load_config 자체(파일을 읽는 부분)는 이 모듈에 남는다 — 두 모듈 다 이 모듈이
임포트하는 단방향 하류이며 어떤 허브 모듈의 상수도 참조하지 않는다.

서브에이전트 생존 신호 작업이 다른 세션의 세션·프로젝트·카드 변경과 리베이스로 합쳐지며
808줄이 되어 800줄 상한을 다시 넘었다 — 상주 서버 상태 I/O(하트비트·성공 스탬프·
server.json)를 hub_server_state_read.py 로 옮겨 800줄 아래로 되돌렸다. 이 후속 분리는
docs/prps/hub-subagent-liveness-signal.md §11 R4 가 이미 예견해 둔 것이고, 절차 자체는
docs/prps/hub-model-module-split.md 결정 MS1 을 다시 적용한 것이다(새 절차 아님).
SERVER_LOG_PATH(server.log)는 그 7개 함수 중 어느 것도 쓰지 않아 이 모듈에 남는다.
"""

import dataclasses
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Sequence

import hub_account
import hub_activity
import hub_atomic_write
import hub_config
import hub_live_session
import hub_live_session_read
import hub_model
import hub_parse
import hub_project
import hub_release_read
import hub_session_cost
import hub_session_facts
import hub_subagent
import hub_subagent_read
import hub_transcript
import hub_usage
import hub_workflow
import hub_workflow_read

HUB_HOME = Path.home() / ".claude" / "hub"
EVENTS_DIR = HUB_HOME / "events"
HUB_HTML_PATH = HUB_HOME / "hub.html"
CONFIG_PATH = HUB_HOME / "config.json"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
# 호스트(Claude Code)가 살아있는 세션마다 쓰는 명부 — 우리가 소유하지 않는 읽기 전용 입력이다.
# *.json 만 대상이고 같은 디렉터리의 <pid>.<sha256>.key 는 건드리지 않는다(결정 LS11,
# docs/prps/hub-live-session-native-source.md).
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "hub_template.html"
# 세션 페이지(진행 기록) 템플릿 — hub_server._serve_project_dashboard 가 요청마다 읽는다
# (HD5, docs/prps/dashboard-into-hub.md). 캐시하지 않는다(YAGNI) — 60KB 문자열 치환은
# 밀리초 단위라 collect_snapshot 의 50ms 에스컬레이션 조건에 편입한다.
DASHBOARD_TEMPLATE_PATH = SCRIPT_DIR / "hub_dashboard_template.html"
# 배경 spawn(hub_hook.py)의 stdout/stderr 는 DEVNULL 이라 실패가 완전히 무성음이 된다 — 마지막
# collect 실패를 이 파일에 남겨 `/hub status` 가 읽을 수 있게 한다(검수 M7).
LAST_COLLECT_ERROR_PATH = HUB_HOME / "last_collect_error.json"
# 사용량 API 폴링(R1) 실패 기록 — last_collect_error.json 과 완전히 같은 모양이다(새 개념 0개,
# 결정 A5). schema_mismatch 일 때만 response_keys(키 구조, 값 없음)가 더 실린다.
LAST_USAGE_API_ERROR_PATH = HUB_HOME / "last_usage_api_error.json"
# 훅 버스트(같은 5초 안에 여러 세션이 동시에 훅을 쏘는 경우) 디바운스용 스탬프(검수 n3).
# hub.html 의 mtime 은 spawn 된 collect 가 끝나야 바뀌므로, 그 사이 도착하는 훅들은 여전히
# 오래된 mtime 을 보고 각자 spawn 을 결정해 버린다 — spawn 직전에 이 파일을 touch 하면
# 뒤따르는 훅들이 곧바로 "최근에 이미 처리했다"고 판단한다.
SPAWN_STAMP_PATH = HUB_HOME / ".collect_spawn_stamp"
# 상주 서버(개정 1 rev2)의 stderr 리다이렉션 대상. server.json·server_heartbeat·
# last_collect_success 는 hub_server_state_read.py 로 옮겨졌다(위 모듈 docstring 참조) — 이
# 파일만 옮기지 않았다. hub_daemon.py(_server_log_tail·_spawn_server_process)·hub_server.py
# (run_server 의 로그 절단)가 여전히 이 모듈을 거쳐 읽고 쓴다.
SERVER_LOG_PATH = HUB_HOME / "server.log"
# hub_statusline.py 가 statusLine stdin 에서 캡처한 한도 초기화 예정 시각 + 사용률 —
# 퍼센트의 유일한 출처다(결정 P1, docs/prps/hub-card-cleanup-and-usage-source.md).
RATE_LIMITS_PATH = HUB_HOME / "rate_limits.json"
# Claude Code 가 쓰는 전역 설정 — 우리가 소유하지 않는 읽기 전용 입력이다. oauthAccount 의
# 세 값만 꺼낸다(결정 AC1, docs/prps/hub-usage-panel-account.md).
CLAUDE_GLOBAL_CONFIG_PATH = Path.home() / ".claude.json"
PROJECT_LOCAL_SETTINGS_RELATIVE_PATH = ".claude/settings.local.json"  # 진행 기록 오프 스위치(결정 RL10, `/hub dashboard off`)


class HubCollectError(Exception):
    """collect 파이프라인에서 예상된 실패(배포 자산 누락 등)를 나타낸다(검수 M7).

    session.json 파싱 실패(설계 결정 5)를 제외한 나머지는 원래 "실패 → 한 티어 낮은 표시"로
    흡수해야 하는데, 템플릿 파일처럼 흡수할 하위 티어가 없는 경우에 한해 이 예외로 사유를 분명히
    하고 호출자(hub.py)가 `{"ok": false, "reason": ...}` 계약으로 변환한다.
    """

PROJECT_MARKER_NAMES = (".claude", ".git")
MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000
DATE_FORMAT = "%Y-%m-%d"


def load_config() -> tuple[hub_model.HubConfig, tuple[str, ...]]:
    """~/.claude/hub/config.json 을 읽는다. 없거나 깨졌으면 기본값 전부.
    필드 타입·주기 하한 검증은 hub_config.config_from_raw(★순수)에 위임한다."""
    defaults = hub_model.HubConfig()
    if not CONFIG_PATH.exists():
        return defaults, ()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults, (f"{CONFIG_PATH}: JSON 파싱 실패 — 기본값을 씁니다",)
    if not isinstance(raw, dict):
        return defaults, (f"{CONFIG_PATH}: 최상위 값이 객체가 아니라 기본값을 씁니다",)
    return hub_config.config_from_raw(raw, defaults)


# ---- 프로젝트 발견 (config.roots 스캔, 쟁점 4) ----
def _has_project_marker(directory: Path) -> bool:
    """.claude 또는 .git 존재 여부. `Path.exists` 는 ENOENT 만 흡수하고 EACCES 는 올린다
    (macOS 실측, 검수 M7) — 권한 없는 디렉토리를 훑다 collect 전체가 죽지 않도록 감싼다."""
    try:
        return any((directory / marker).exists() for marker in PROJECT_MARKER_NAMES)
    except OSError:
        return False


def _scan_directory(directory: Path, remaining_depth: int) -> list[str]:
    matches = []
    if _has_project_marker(directory):
        matches.append(str(directory))
    if remaining_depth <= 0:
        return matches
    try:
        children = [child for child in directory.iterdir() if child.is_dir()]
    except OSError:
        return matches
    for child in children:
        matches.extend(_scan_directory(child, remaining_depth - 1))
    return matches


def scan_roots_for_projects(roots: tuple[str, ...], scan_depth: int) -> list[str]:
    """config.roots 를 scan_depth 까지 훑어 .claude 또는 .git 을 가진 디렉토리를 찾는다."""
    found = []
    for root in roots:
        root_path = Path(root).expanduser()
        if root_path.is_dir():
            found.extend(_scan_directory(root_path, scan_depth))
    return found


# ---- 티어 2: 이벤트 로그 ----
def _date_string(epoch_ms: int) -> str:
    return time.strftime(DATE_FORMAT, time.localtime(epoch_ms / 1000))


def _recent_event_file_paths(now_ms: int) -> list[Path]:
    dates = [_date_string(now_ms), _date_string(now_ms - MILLISECONDS_PER_DAY)]
    unique_dates = list(dict.fromkeys(dates))
    return [EVENTS_DIR / f"{date}.jsonl" for date in unique_dates]


def read_recent_events(now_ms: int) -> tuple[list[hub_session_facts.HookEvent], tuple[str, ...]]:
    """오늘 + 어제 이벤트 파일을 읽어 파싱된 이벤트를 시간순으로 돌려준다.

    파일 하나를 못 읽어도 나머지로 계속 진행한다(검수 M7, 리스크 6 "이벤트 손실은 1건 한정"과
    같은 원칙) — `errors="replace"` 로 깨진 바이트(동시 append 찢김 등)를 U+FFFD 로 바꿔
    디코딩 자체가 죽지 않게 하고, 그 결과로 JSON 이 안 맞는 줄만 parse_event_line 에서 탈락한다.
    파일 단위 읽기 실패(권한 등)는 그 파일만 건너뛰고 사유를 warnings 로 돌려준다.
    """
    events = []
    warnings: list[str] = []
    for file_path in _recent_event_file_paths(now_ms):
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            warnings.append(f"{file_path}: 이벤트 파일 읽기 실패 ({error})")
            continue
        for line in text.splitlines():
            event = hub_session_facts.parse_event_line(line)
            if event is not None:
                events.append(event)
    events.sort(key=lambda event: event.received_at_ms)
    return events, tuple(warnings)


def _group_sessions_by_project(
    events: list[hub_session_facts.HookEvent], ignore_globs: tuple[str, ...]
) -> dict[str, tuple[hub_session_facts.SessionFacts, ...]]:
    """이벤트를 세션 사실로 접고 소유 레포 루트(워크트리는 fold)별로 묶는다.

    fold 가 ignore 보다 먼저다(결정 WT4·WT5) — 접힌 루트에 대해서만 무시 패턴을 판정해야
    워크트리 경로가 `ignore_globs` 기본값(`**/.claude/worktrees/**`)에 걸려 접힌 세션이
    통째로 사라지는 사고를 막는다. `SessionFacts.cwd` 자신은 재작성하지 않는다(결정 WT14) —
    원본 cwd 는 GN9 의 티어 1 출처 대조에 그대로 필요하다.
    """
    grouped: dict[str, list[hub_session_facts.SessionFacts]] = {}
    for facts in hub_session_facts.build_session_facts(events).values():
        folded_cwd = hub_project.fold_worktree_path(facts.cwd)
        if hub_project.should_ignore_cwd(folded_cwd, ignore_globs):
            continue
        grouped.setdefault(folded_cwd, []).append(facts)
    return {path: tuple(sessions) for path, sessions in grouped.items()}


# ---- 요구 2: 세션이 지금 쓰는 모델·effort (docs/prps/hub-tier1-clamp-fix-and-session-model.md
#      결정 MD1~MD10) ----
def _read_transcript_tail(transcript_path: Path) -> str | None:
    """transcript 파일의 꼬리 TRANSCRIPT_TAIL_BYTES 만 읽어 텍스트로 디코딩한다.

    파일이 없거나 읽기에 실패하면(권한 등) None — 이 함수는 절대 예외를 던지지 않는다.
    `errors="replace"` 로 디코딩한다(결정 MD3) — 꼬리 경계에서 멀티바이트가 찢기고, 활성
    세션이 동시에 append 중인 파일이다. `UnicodeDecodeError` 는 `ValueError` 서브클래스라
    `except OSError` 를 뚫는다(GOTCHA 7, read_rate_limit_capture 의 검수 M1 과 같은 함정).
    """
    try:
        file_size = transcript_path.stat().st_size
        with transcript_path.open("rb") as transcript_file:
            if file_size > hub_transcript.TRANSCRIPT_TAIL_BYTES:
                transcript_file.seek(-hub_transcript.TRANSCRIPT_TAIL_BYTES, os.SEEK_END)
            raw_tail = transcript_file.read()
    except OSError:
        return None
    return raw_tail.decode("utf-8", errors="replace")


def read_session_tail(
    session_id: str, observed_cwds: Sequence[str]
) -> hub_transcript.SessionTail | None:
    """세션의 transcript 꼬리를 읽어 (모델·effort, 마지막 프롬프트)를 판다. 이 함수는 절대
    예외를 던지지 않는다(결정 PS1 — read_session_model 의 개명. 본문은 파서 호출 한 줄만
    바뀐다, docs/prps/hub-agent-runs-and-prompt-source.md).

    파일 위치는 디렉토리 스캔 없이 `observed_cwds` 로 직접 조립한다(결정 MD2) —
    `encode_project_dir_name`(순수 함수)으로 인코딩해 `PROJECTS_DIR/<인코딩>/<session_id>.jsonl`
    후보를 만들고, **먼저 존재하는 것을 쓴다**(결정적, E14) — 존재하는 파일을 찾은 뒤에는
    그 파일의 꼬리에 유효한 값이 없어도 다음 후보로 넘어가지 않는다(§3.4 절차 5, E7 —
    상한이 곧 예산이다). `observed_cwds` 전부를 후보로 삼는 이유는 워크트리로 이동한 세션의
    transcript 디렉토리가 최초 cwd 기준으로 남기 때문이다(E13). 세션당 stat/open 1~2회뿐이라
    `PROJECTS_DIR` 전체 열거(수백 개)를 하지 않는다.
    """
    for cwd in observed_cwds:
        encoded_project_dir_name = hub_project.encode_project_dir_name(cwd)
        transcript_path = PROJECTS_DIR / encoded_project_dir_name / f"{session_id}.jsonl"
        tail_text = _read_transcript_tail(transcript_path)
        if tail_text is not None:
            return hub_transcript.parse_session_tail(tail_text)
    return None


def read_session_tails(
    sessions_by_path: dict[str, tuple[hub_session_facts.SessionFacts, ...]], record_prompt_excerpt: bool
) -> dict[str, hub_transcript.SessionTail]:
    """수집 대상 세션 전부의 표시 정보(모델·마지막 프롬프트)를 모은다. 값을 못 얻은 세션은
    키 자체를 넣지 않는다(결정 PS1 — read_session_models 의 개명).

    캐시를 두지 않는다(결정 MD4, YAGNI) — 대상 파일은 정의상 지금 활성 세션이 append 중인
    파일이라 페이지 캐시가 뜨거운 상태이고(실측 1.5MB 총 읽기량이 ~6ms), 수집 자체가 요청이
    이끄는 빈도(최악 5초 1회)라 반복 비용이 크지 않다. `collect_snapshot` 이 50ms 를 넘기
    시작하면 그때 캐시를 재검토한다(에스컬레이션 조건 명시).

    `record_prompt_excerpt` 가 거짓이어도 꼬리 자체는 계속 읽는다(결정 PS7) — 모델 표시는
    별도 옵트아웃이 없는 기본 표시 정보이기 때문이다. 여기서 버려지는 것은 `last_prompt`
    뿐이다 — `wf_*.json` 을 아예 안 읽는 read_session_workflows 와 다른 유일한 지점이다.
    """
    tails: dict[str, hub_transcript.SessionTail] = {}
    for sessions in sessions_by_path.values():
        for facts in sessions:
            tail = read_session_tail(facts.session_id, facts.observed_cwds)
            if tail is None:
                continue
            if not record_prompt_excerpt:
                tail = dataclasses.replace(tail, last_prompt=None)
            tails[facts.session_id] = tail
    return tails


def prune_old_event_files(now_ms: int, retention_days: int) -> None:
    """retention_days 보다 오래된 이벤트 파일을 삭제한다. 살아 있는 파일은 절대 다시 쓰지 않는다.

    hub.html 이 없어도(허브 off 상태) 호출돼야 "최대 N일 보관" 고지가 성립한다 — 공개 함수로 두어
    hub_hook.py 가 append 직후 곧바로 호출한다(검수 M5).
    """
    if not EVENTS_DIR.is_dir():
        return
    cutoff_date = time.strftime(DATE_FORMAT, time.localtime((now_ms - retention_days * MILLISECONDS_PER_DAY) / 1000))
    for file_path in EVENTS_DIR.glob("*.jsonl"):
        match = re.match(r"(\d{4}-\d{2}-\d{2})\.jsonl$", file_path.name)
        if match and match[1] < cutoff_date:
            file_path.unlink(missing_ok=True)


# ---- 티어 1: 세션별 진행 기록 JSONL ----
def read_session_dashboard_snapshots(
    project_path: str,
) -> tuple[tuple[hub_parse.Tier1Snapshot, ...], tuple[str, ...]]:
    """<project_path>/.claude/dashboards/ 를 1회 열거해 파일명 정규식(결정 ST9)을 통과한 파일만 파싱한다.
    (스냅샷들, 경고들). 디렉토리 부재는 정상(빈 튜플). 미통과 파일명은 열지도 않는다 — 발견된 경로만
    레지스트리에 오른다(결정 N3). iterdir·읽기 실패·파싱 실패·init 없음은 그 항목만 건너뛰고 경고
    1건을 남긴다.
    task_started_at_ms 는 파서(hub_parse.parse_dashboard_jsonl)가 JSONL 첫 줄(init)에서 채운
    값을 그대로 두고 이 함수가 덮어쓰지 않는다(HD8, docs/prps/dashboard-into-hub.md — M1 까지는
    사이드카 mtime 을 이 함수가 별도로 읽어 덮어썼다).
    """
    dashboards_dir = Path(project_path) / hub_project.SESSION_DASHBOARDS_RELATIVE_DIRECTORY
    if not dashboards_dir.is_dir():
        return (), ()
    try:
        entries = sorted(dashboards_dir.iterdir())
    except OSError as error:
        return (), (f"{dashboards_dir}: 목록 조회 실패 — 세션별 대시보드를 건너뜁니다 ({error})",)

    warnings: list[str] = []
    snapshots: list[hub_parse.Tier1Snapshot] = []
    for entry in entries:
        session_id = hub_project.session_id_from_dashboard_file_name(entry.name)
        if session_id is None or not entry.is_file():
            continue
        try:
            text = entry.read_text(encoding="utf-8", errors="replace")
            mtime_ms = int(entry.stat().st_mtime * 1000)
        except OSError as error:
            warnings.append(f"{entry}: 세션 대시보드 읽기 실패 ({error})")
            continue
        try:
            snapshot = hub_parse.parse_dashboard_jsonl(text)
        except (ValueError, TypeError, RecursionError) as error:
            # 최종 방어선(재검수 2회차 RA1-e) — hub_parse 는 계약 B(어떤 입력에도 예외를
            # 던지지 않는다)를 지키지만, 그 계약이 미래에 깨져도 이 파일 하나만 건너뛰고
            # 다른 프로젝트의 collect_snapshot 전체가 죽지 않게 한다(넓은 except Exception
            # 은 쓰지 않는다 — 타입을 좁혀 진짜 프로그램 결함(예: AttributeError)까지
            # 삼키지 않는다).
            warnings.append(f"{entry}: 세션 대시보드 파싱 실패 ({type(error).__name__}) — 건너뜁니다")
            continue
        if snapshot is None:
            warnings.append(f"{entry}: 세션 대시보드 JSONL 계약 불일치(init 없음 또는 무효 — 단계 수 상한 초과 포함) — 건너뜁니다")
            continue
        snapshots.append(dataclasses.replace(
            snapshot, file_mtime_ms=mtime_ms, source_path=project_path, session_id=session_id,
        ))
    return tuple(snapshots), tuple(warnings)


def read_dashboard_enabled(project_path: str) -> bool:
    """진행 기록 오프 스위치(결정 RL10, `/hub dashboard off`) — 파일·필드 없음·읽기·파싱 실패·
    타입 불일치는 켜짐(True)으로 넘어진다."""
    settings_path = Path(project_path) / PROJECT_LOCAL_SETTINGS_RELATIVE_PATH
    if not settings_path.is_file():
        return True
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    value = raw.get("dashboard_enabled", True) if isinstance(raw, dict) else True
    return value if isinstance(value, bool) else True


def _read_tier1_for_root(
    member_paths: Sequence[str],
) -> tuple[hub_parse.Tier1Snapshot | None, tuple[hub_parse.Tier1Snapshot, ...], tuple[str, ...]]:
    """레포 루트와 그 워크트리 멤버 전부의 세션별 진행 기록을 읽어 mtime 최신 승자를 고른다
    (결정 WT6, ST11). 레거시 단일 파일(.claude/dashboard.html) 읽기는 폐기됐다(HD7,
    docs/prps/dashboard-into-hub.md — 09-14 이후 그 파일을 쓰는 곳이 없었다). 멤버 첫 원소가
    레포 루트다(`group_paths_by_repo_root` 의 순서 계약). ignore 는 루트에만 적용됐으므로
    (결정 WT5) 멤버 각각은 여기서 무조건 읽는다 — 워크트리가 없으면 `member_paths == (root,)`
    라 오늘과 동일하게 동작한다(S7). 반환의 두 번째 원소(세션별 스냅샷 전부)는 승자 여부와
    무관하게 발견된 것 전부다 — `compose_project_views` 가 `index_session_dashboards` 로
    세션당 1개를 다시 골라 쓴다(결정 ST12).
    """
    session_snapshots: list[hub_parse.Tier1Snapshot] = []
    warnings: list[str] = []
    for member_path in member_paths:
        member_session_snapshots, session_warnings = read_session_dashboard_snapshots(member_path)
        session_snapshots.extend(member_session_snapshots)
        warnings.extend(session_warnings)

    winner = hub_project.select_tier1_source(session_snapshots)
    return winner, tuple(session_snapshots), tuple(warnings)


def _collect_tier1_snapshots(
    tier1_candidates_by_root: dict[str, tuple[str, ...]]
) -> tuple[dict[str, hub_parse.Tier1Snapshot], dict[str, tuple[hub_parse.Tier1Snapshot, ...]], tuple[str, ...]]:
    """루트별 (승자, 세션별 스냅샷들) 을 모은다 — 두 번째 값은 `collect_snapshot` 이
    `compose_project_views` 의 `session_dashboards_by_path` 로 넘긴다(결정 ST9).

    각 루트의 멤버 튜플을 그대로 `_read_tier1_for_root` 에 넘겨야 한다 — 루트만 넘기면
    (`(root,)`) 워크트리 멤버가 조용히 빠져 결함 A(레포 루트 파일만 읽힘)가 되살아난다
    (검수 1회차 M1 — `CollectTier1SnapshotsTest` 가 이 계약을 직접 검증한다).
    """
    tier1_by_path: dict[str, hub_parse.Tier1Snapshot] = {}
    session_dashboards_by_path: dict[str, tuple[hub_parse.Tier1Snapshot, ...]] = {}
    warnings: list[str] = []
    for root, member_paths in tier1_candidates_by_root.items():
        snapshot, session_snapshots, tier1_warnings = _read_tier1_for_root(member_paths)
        if snapshot is not None:
            tier1_by_path[root] = snapshot
        session_dashboards_by_path[root] = session_snapshots
        warnings.extend(tier1_warnings)
    return tier1_by_path, session_dashboards_by_path, tuple(warnings)


# ---- 티어 3: ~/.claude/projects 의 mtime ----
def _encoded_ignore_globs(ignore_globs: tuple[str, ...]) -> tuple[str, ...]:
    """ignore_globs(실경로 패턴)를 encode_project_dir_name 과 같은 규칙으로 인코딩한다.

    호스트 규칙은 영숫자가 아닌 글자를 전부 `-` 로 바꾸므로 `*` 까지 바뀐다 — 와일드카드를 살리는
    glob 전용 인코더(`encode_path_glob_to_project_dir_glob`)를 거쳐야 fnmatch 패턴으로 계속 쓸 수 있다.
    """
    return tuple(hub_project.encode_path_glob_to_project_dir_glob(pattern) for pattern in ignore_globs)


def _tier3_activity_by_encoded_name(
    ignore_globs: tuple[str, ...]
) -> tuple[dict[str, int], tuple[str, ...]]:
    """~/.claude/projects/<인코딩>/*.jsonl (maxdepth 1) mtime 최댓값을 인코딩명별로 모은다.

    ignore_globs 를 인코딩한 패턴으로도 걸러 scratchpad·worktree 소음을 원천에서 제거한다
    (검수 m4) — 그러지 않으면 이 항목들이 매칭에 실패해 "미확인 프로젝트" 개수만 부풀린다.

    두 지점에 OSError 가드를 둔다(검수 R3-m1): `iterdir()` 실패(권한 없음 등)는 티어 3
    전체를 포기하고(티어 1·2 는 산다), entry 단위 stat 실패(glob 열거와 stat 사이의 TOCTOU)는
    그 프로젝트만 건너뛴다. 상주 서버에서는 수집 사이클마다(요청 구동이든 유지보수 티커든)
    같은 예외를 다시 만나므로 이 구멍을 열어 두면 위험이 더 크다.
    """
    if not PROJECTS_DIR.is_dir():
        return {}, ()
    encoded_ignore_globs = _encoded_ignore_globs(ignore_globs)
    try:
        entries = list(PROJECTS_DIR.iterdir())
    except OSError as error:
        return {}, (f"{PROJECTS_DIR}: 목록 조회 실패 — 티어 3 전체를 건너뜁니다 ({error})",)

    activity: dict[str, int] = {}
    warnings: list[str] = []
    for entry in entries:
        if not entry.is_dir() or hub_project.should_ignore_cwd(entry.name, encoded_ignore_globs):
            continue
        try:
            mtimes = [child.stat().st_mtime for child in entry.glob("*.jsonl")]
        except OSError as error:
            warnings.append(f"{entry}: mtime 조회 실패 — 이 프로젝트만 건너뜁니다 ({error})")
            continue
        if mtimes:
            activity[entry.name] = int(max(mtimes) * 1000)
    return activity, tuple(warnings)


# ---- 한도 초기화 예정 시각 + 사용률 (docs/prps/hub-usage-reset-time-and-refresh.md,
#      docs/prps/hub-card-cleanup-and-usage-source.md 결정 P1~P8) ----
def read_rate_limit_capture() -> tuple[hub_usage.RateLimitCapture | None, tuple[str, ...]]:
    """캡처 파일을 읽어 판다. 이 함수는 절대 예외를 던지지 않는다.

    반환 계약(PRP 「반환 계약」 표가 정본): 파일 부재는 statusLine 미설치·미실행의 정상
    상태라 경고를 내지 않는다. 읽기 실패·계약 불일치만 경고 1건을 남긴다. 퍼센트의 유일한
    출처가 됐으므로(결정 P1) `errors="replace"` 로 찢긴 멀티바이트 읽기를 흡수한다 — 그러지
    않으면 `UnicodeDecodeError`(ValueError 서브클래스)가 `except OSError` 를 뚫는다
    (read_latest_usage_sample 의 검수 M1 선례와 같은 문제, §17 발견 1).
    """
    if not RATE_LIMITS_PATH.is_file():
        return None, ()
    try:
        text = RATE_LIMITS_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return None, (f"{RATE_LIMITS_PATH}: 한도 초기화 시각 캡처 파일 읽기 실패 ({error})",)
    capture = hub_usage.parse_rate_limit_capture(text)
    if capture is None:
        return None, (f"{RATE_LIMITS_PATH}: 캡처 파일 계약 불일치 — 사용량 패널을 표시하지 않습니다",)
    return capture, ()


def write_rate_limit_capture(capture: hub_usage.RateLimitCapture) -> None:
    """캡처를 원자적으로 쓴다(hub_statusline.py 전용 쓰기 경로). hub_atomic_write.atomic_write_text 재사용."""
    HUB_HOME.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dataclasses.asdict(capture), ensure_ascii=False)
    hub_atomic_write.atomic_write_text(RATE_LIMITS_PATH, HUB_HOME, "rate_limits.json.", payload)


def _capture_for_snapshot(
    now_ms: int, config: hub_model.HubConfig
) -> tuple[hub_usage.UsageSample | None, hub_usage.RateLimitResets | None, tuple[str, ...]]:
    """캡처를 **사이클당 1회만** 읽어 화면에 실을 사용률·리셋 시각을 고른다(사설, 결정 P3).

    `show_usage_panel` 이 꺼져 있으면 캡처 파일을 열지도 않는다(전제 8) — CSS 로 숨기는 게
    아니라 읽기 자체를 중단하는 것이 진짜 프라이버시 제어다. 사용률은 5시간 만료(U3) 또는
    세션 창 롤오버(결정 P5)여도 **숨기지 않는다** — `mark_stale_usage_sample` 이 `is_stale`
    로 표시만 하고 값은 그대로 살려 둔다(R-B, 결정 EX1·EX5) — 화면은 그 값을 "조회되지
    않음"으로 그린다. 지난 리셋 시각은 여기(서버 쪽 1차 필터, 결정 R5)에서 걷어낸다 —
    클라이언트 쪽 2차 필터는 템플릿이 30초 틱마다 담당한다. 두 사설 함수
    (_usage_for_snapshot·_rate_limit_resets_for_snapshot)가 각각 파일을 읽던 구조를 여기
    하나로 합쳐, 계약 불일치 경고가 2건으로 중복되는 문제(GOTCHA 5)를 없앤다.
    """
    if not config.show_usage_panel:
        return None, None, ()
    capture, warnings = read_rate_limit_capture()
    if capture is None:
        return None, None, warnings

    usage = hub_usage.usage_sample_from_capture(capture)
    if usage is not None:
        usage = hub_usage.mark_stale_usage_sample(usage, capture, now_ms)  # 숨기지 않고 표식만 단다(R-B)

    resets = hub_usage.resets_from_capture(capture)
    if resets is not None:
        resets = hub_usage.drop_passed_resets(resets, now_ms)

    return usage, resets, warnings


def read_account_info() -> tuple[hub_account.AccountInfo | None, tuple[str, ...]]:
    """~/.claude.json 에서 계정 표시 3값을 읽는다. 절대 예외를 던지지 않는다(결정 AC9 표가 정본).

    파일 부재(API 키 사용자·미로그인)와 oauthAccount 부재는 정상 상태라 경고를 내지 않는다.
    읽기 실패·계약 불일치만 경고 1건 — 경고는 경로와 고정 사유뿐이고 파일 내용은 담지 않는다
    (이메일이 화면에 보이는 경고 줄로 새지 않게, GOTCHA 2). `errors="replace"` 는
    read_rate_limit_capture 의 검수 M1 과 같은 이유다 — UnicodeDecodeError 가 except OSError 를
    뚫지 않게 한다.
    """
    try:
        text = CLAUDE_GLOBAL_CONFIG_PATH.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None, ()
    except OSError as error:
        return None, (f"{CLAUDE_GLOBAL_CONFIG_PATH}: 계정 정보 파일 읽기 실패 ({error})",)
    account, mismatch_reason = hub_account.parse_account_info(text)
    if mismatch_reason is not None:
        return None, (f"{CLAUDE_GLOBAL_CONFIG_PATH}: {mismatch_reason}",)
    return account, ()


def _usage_panel_for_snapshot(
    now_ms: int, config: hub_model.HubConfig
) -> tuple[
    hub_usage.UsageSample | None,
    hub_usage.RateLimitResets | None,
    hub_account.AccountInfo | None,
    tuple[str, ...],
]:
    """사용량 패널에 실을 네 덩어리(사용률·리셋·계정·경고)를 고른다(사설).

    usage 가 없거나 `show_account_info` 가 꺼지면 계정 파일을 열지 않는다(결정 AC2·AC7) —
    `hub.html` 에 남는 것은 화면에 보일 수 있는 것뿐이어야 한다. `show_usage_panel:false` 면
    `_capture_for_snapshot` 이 usage=None 을 돌려주므로 계정도 자동으로 읽히지 않는다.
    """
    usage, resets, warnings = _capture_for_snapshot(now_ms, config)
    if usage is None or not config.show_account_info:
        return usage, resets, None, warnings
    account, account_warnings = read_account_info()
    return usage, resets, account, (*warnings, *account_warnings)


# ---- 템플릿 세대 스탬프 (docs/prps/hub-ungated-poll-and-stale-tab-self-heal.md 결정 SH3) ----
TEMPLATE_STAMP_LENGTH = 16


def read_template_stamp() -> str:
    """hub_template.html 바이트의 SHA-256 앞 16자리. 이 파일이 곧 '세대'다.

    읽기 실패(배포 누락 등)는 ""로 흡수한다(결정 SH5) — 보고 지점은 write_hub_html 하나로
    충분하다. 메모이즈하지 않는다 — 재기동 없이 디스크의 변화를 감지하는 것이 목적이다.
    """
    try:
        return hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest()[:TEMPLATE_STAMP_LENGTH]
    except OSError:
        return ""


# ---- 합성 ----
def _read_session_annotations(
    sessions_by_path: dict[str, tuple[hub_session_facts.SessionFacts, ...]],
    record_prompt_excerpt: bool,
    now_ms: int,
) -> tuple[
    dict[str, hub_transcript.SessionTail],
    dict[str, hub_workflow.WorkflowRunView],
    dict[str, hub_subagent.SubagentMeta],
    hub_live_session.LiveSessionIndex,
    tuple[str, ...],
    dict[str, int],
    hub_activity.LiveActivity,
]:
    """세션에 얹을 보강 정보 6종(모델·마지막 프롬프트 / 워크플로우 / 서브에이전트 메타 /
    살아있는 세션 명부 / 서브에이전트 생존 신호 / 실행 중 활동)을 한데 모아 읽는다. collect_snapshot 을
    50줄 제한 안에 두려고 뽑았다(재검수 1회차 M4) — 읽기 호출과 그 경고 합치기 외에는
    아무 판단도 하지 않는 순수 배선이다. 명부·생존 신호·활동은 `record_prompt_excerpt` 로
    게이팅하지 않는다(각각 결정 LS2·SL7·LA13, docs/prps/hub-live-session-native-source.md ·
    hub-subagent-liveness-signal.md · hub-live-activity.md) — 셋 다 프롬프트 콘텐츠가 아니다. 생존 신호는
    (dict, warnings) 가 아니라 dict 하나만 돌려주므로(결정 SL8) 경고 합치기에 끼지 않고, 활동도 경고가 없다(결정 LA12).
    """
    tail_by_session_id = read_session_tails(sessions_by_path, record_prompt_excerpt)
    workflow_by_session_id, workflow_warnings = hub_workflow_read.read_session_workflows(
        sessions_by_path, record_prompt_excerpt, PROJECTS_DIR
    )
    subagent_meta_by_agent_id, subagent_warnings = hub_subagent_read.read_subagent_metas(
        sessions_by_path, record_prompt_excerpt, PROJECTS_DIR
    )
    live_roster, roster_warnings = hub_live_session_read.read_live_session_roster(SESSIONS_DIR)
    subagent_activity_by_agent_id = hub_subagent_read.read_unfinished_subagent_activity(
        sessions_by_path, PROJECTS_DIR
    )
    live_activity = hub_subagent_read.read_live_activity(
        sessions_by_path, PROJECTS_DIR, now_ms, subagent_activity_by_agent_id
    )
    warnings = (*workflow_warnings, *subagent_warnings, *roster_warnings)
    return (
        tail_by_session_id, workflow_by_session_id, subagent_meta_by_agent_id, live_roster,
        warnings, subagent_activity_by_agent_id, live_activity,
    )


def _prune_and_read_session_costs(
    sessions_by_path: dict[str, tuple[hub_session_facts.SessionFacts, ...]],
    now_ms: int,
    config: hub_model.HubConfig,
) -> dict[str, hub_usage.SessionCost]:
    """보관 기간이 지난 세션 비용 캡처 파일을 **지우고**, 보이는 세션들의 캡처를 읽는다(⑨, docs/prps/harness-benchmark-adoption.md).

    이름이 읽기만 하는 함수로 오해되지 않게 정리(삭제) 부작용을 드러냈다. statusLine 을 켜지 않았거나 캡처 디렉터리가 없으면
    빈 dict 다 — 칩이 없는 것은 정당한 부재다. 보관 기간은 이벤트 파일과 같은 설정(`event_retention_days`)을 쓴다.
    collect_snapshot 을 50줄 제한 안에 두려고 정리와 읽기를 한 함수로 묶었다.
    """
    hub_session_cost.prune_old_session_cost_files(now_ms, config.event_retention_days)
    session_ids = (facts.session_id for facts_group in sessions_by_path.values() for facts in facts_group)
    return hub_session_cost.read_session_costs(session_ids)


def collect_snapshot(now_ms: int) -> hub_model.HubSnapshot:
    """3티어를 전부 읽어 하나의 HubSnapshot 으로 합성한다. 실패는 warnings 로 드러난다."""
    config, config_warnings = load_config()
    prune_old_event_files(now_ms, config.event_retention_days)

    events, event_read_warnings = read_recent_events(now_ms)
    sessions_by_path = _group_sessions_by_project(events, config.ignore_globs)   # 키가 이미 접힌 루트
    scanned_paths = scan_roots_for_projects(config.roots, config.scan_depth)

    # 티어 1 후보 조립(관측 경로 → 루트별 멤버 → ignore 필터)은 hub_project.py(★순수)로
    # 옮겨졌다(검수 1회차 M1) — 여기 남겨 두면 이 조립을 실제로 실행하는 테스트가 하나도
    # 없어(전부 mock.patch 로 우회) 뮤테이션이 검출되지 않았다.
    tier1_candidates_by_root = hub_project.plan_tier1_candidates(
        sessions_by_path, scanned_paths, config.ignore_globs
    )
    tier1_by_path, session_dashboards_by_path, tier1_read_warnings = _collect_tier1_snapshots(tier1_candidates_by_root)
    dashboard_enabled_by_path = {root: read_dashboard_enabled(root) for root in tier1_candidates_by_root}

    tier3_by_encoded_name, tier3_warnings = _tier3_activity_by_encoded_name(config.ignore_globs)
    resolved, unresolved = hub_project.resolve_project_dirs(
        list(tier3_by_encoded_name), list(tier1_candidates_by_root)
    )
    tier3_by_path = {resolved[name]: mtime for name, mtime in tier3_by_encoded_name.items() if name in resolved}

    warnings: list[str] = [*config_warnings, *event_read_warnings, *tier1_read_warnings, *tier3_warnings]
    stale_after_ms = config.stale_after_minutes * 60 * 1000
    (
        tail_by_session_id, workflow_by_session_id, subagent_meta_by_agent_id,
        live_roster, annotation_warnings, subagent_activity_by_agent_id, live_activity,
    ) = _read_session_annotations(sessions_by_path, config.record_prompt_excerpt, now_ms)
    warnings.extend(annotation_warnings)
    projects = hub_project.compose_project_views(
        tier1_by_path, sessions_by_path, tier3_by_path, now_ms, stale_after_ms,
        tail_by_session_id, session_dashboards_by_path, workflow_by_session_id,
        subagent_meta_by_agent_id, subagent_activity_by_agent_id, dashboard_enabled_by_path,
        live_roster, live_activity, _prune_and_read_session_costs(sessions_by_path, now_ms, config),
    )
    usage, rate_limit_resets, account, panel_warnings = _usage_panel_for_snapshot(now_ms, config)
    harness_version, harness_version_warnings = hub_release_read.read_harness_version_view(config)
    return hub_model.HubSnapshot(
        collected_at_ms=now_ms,
        projects=projects,
        unresolved_dir_names=unresolved,
        warnings=(*warnings, *panel_warnings, *harness_version_warnings),
        usage=usage,
        rate_limit_resets=rate_limit_resets,
        account=account,
        template_stamp=read_template_stamp(),
        harness_version=harness_version,
    )


def write_hub_html(snapshot: hub_model.HubSnapshot) -> None:
    """hub.html 을 프로세스마다 고유한 임시 파일에 쓴 뒤 원자적으로 교체한다.

    템플릿을 못 읽으면(배포 누락 등) 원시 OSError 대신 사유가 분명한 HubCollectError 를 던진다
    (검수 M7) — 호출자(hub.py)가 이를 잡아 `{"ok": false, "reason": ...}` 계약으로 변환한다.
    """
    try:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise HubCollectError(f"{TEMPLATE_PATH}: 템플릿 읽기 실패 ({error})") from error
    rendered = hub_model.render_hub_html(template, snapshot)
    HUB_HOME.mkdir(parents=True, exist_ok=True)
    hub_atomic_write.atomic_write_text(HUB_HTML_PATH, HUB_HOME, "hub.html.", rendered)


def touch_spawn_stamp() -> None:
    """collect 재수집을 spawn 하기 직전에 찍는 디바운스 스탬프(검수 n3).

    hub.html 의 mtime 은 spawn 된 자식이 다 끝나야 갱신되므로, 그 사이 도착하는 훅들이 전부
    같은 오래된 mtime 을 보고 각자 spawn 을 결정해 버린다 — 결정 시점을 이 파일로 옮긴다.
    """
    HUB_HOME.mkdir(parents=True, exist_ok=True)
    SPAWN_STAMP_PATH.touch(exist_ok=True)


def record_collect_failure(reason: str) -> None:
    """마지막 collect 실패를 관측 가능한 위치에 남긴다. 이 함수 자신은 절대 예외를 던지지 않는다.

    배경 spawn(hub_hook.py)은 stdout/stderr 가 DEVNULL 이라 실패가 완전히 무성음이 된다 —
    `/hub status` 가 이 파일을 읽어 사용자에게 보여줄 수 있게 한다(검수 M7).

    기록 자체가 실패해도(검수 M2) 예외를 올리지 않고 stderr(상주 서버라면 server.log 로
    리다이렉션된다)로만 남긴다 — 1차 실패의 가장 흔한 원인이 HUB_HOME 쓰기 불가라, 이 함수가
    그대로 예외를 던지면 "실패를 기록하려다 또 실패하는" 상관 실패가 호출자의 예외 처리
    범위를 뚫고 나가 상주 서버의 수집 스레드 전체를 죽인다.
    """
    try:
        HUB_HOME.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"at_ms": int(time.time() * 1000), "reason": reason}, ensure_ascii=False)
        hub_atomic_write.atomic_write_text(LAST_COLLECT_ERROR_PATH, HUB_HOME, "last_collect_error.json.", payload)
    except OSError as error:
        print(f"collect 실패 기록 자체가 실패했습니다: {reason} (기록 실패 사유: {error})", file=sys.stderr)


def clear_collect_failure() -> None:
    """collect 가 성공하면 이전 실패 기록을 지운다."""
    LAST_COLLECT_ERROR_PATH.unlink(missing_ok=True)


def read_last_collect_failure() -> dict | None:
    """마지막으로 기록된 collect 실패(있으면)를 읽는다. 없거나 깨졌으면 None."""
    if not LAST_COLLECT_ERROR_PATH.exists():
        return None
    try:
        return json.loads(LAST_COLLECT_ERROR_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---- 사용량 API 폴링 실패 기록 (R1) — record_collect_failure 와 완전히 같은 형태(결정 A5) ----
def record_usage_api_failure(
    reason: str, response_keys: list[str] | None = None, message: str | None = None
) -> None:
    """사용량 API 실패를 기록한다. 이 함수 자신은 절대 예외를 던지지 않는다
    (`record_collect_failure` 와 완전히 같은 형태·같은 이유 — 기록 자체의 실패가 호출자의
    예외 처리 범위를 뚫고 나가면 안 된다).

    `response_keys` 는 `reason="schema_mismatch"` 일 때만 채운다(SP3 생략 개정의 자기 진단
    창구) — 키 경로 + 타입 목록뿐이며 값은 절대 담지 않는다(불변식 A-SEC).

    `message` 는 N1(docs/prps/shell-hardening.md §8-3·§14 승인 3) — `reason` 고정 어휘를
    사람이 읽는 문장으로 바꾼 것이다. 이 모듈은 그 어휘 사전(`hub_usage_fetch.
    FAILURE_REASON_MESSAGES`)을 모른다 — 호출자(`hub_server.py`, 이미 두 모듈을 안다)가
    `hub_usage_fetch.failure_reason_message(reason)` 로 미리 구해 넘긴다. 생략하면(기존
    호출부와의 하위 호환) payload 에 이 키 자체가 없다.
    """
    try:
        HUB_HOME.mkdir(parents=True, exist_ok=True)
        payload: dict = {"at_ms": int(time.time() * 1000), "reason": reason}
        if response_keys is not None:
            payload["response_keys"] = response_keys
        if message is not None:
            payload["message"] = message
        hub_atomic_write.atomic_write_text(
            LAST_USAGE_API_ERROR_PATH,
            HUB_HOME,
            "last_usage_api_error.json.",
            json.dumps(payload, ensure_ascii=False),
        )
    except OSError as error:
        print(f"사용량 API 실패 기록 자체가 실패했습니다: {reason} (기록 실패 사유: {error})", file=sys.stderr)


def clear_usage_api_failure() -> None:
    """사용량 API 폴링이 성공하면 이전 실패 기록을 지운다."""
    LAST_USAGE_API_ERROR_PATH.unlink(missing_ok=True)


def read_last_usage_api_failure() -> dict | None:
    """마지막으로 기록된 사용량 API 실패(있으면)를 읽는다. 없거나 깨졌으면 None."""
    if not LAST_USAGE_API_ERROR_PATH.exists():
        return None
    try:
        return json.loads(LAST_USAGE_API_ERROR_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
