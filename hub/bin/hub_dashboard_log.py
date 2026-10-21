"""hub/bin/hub_dashboard_log.py — 워크트리 격리 세션의 Bash 관문을 위한 진행 기록 실행체.

워크트리로 격리된 세션의 Bash 관문은 "명령이 워크트리를 벗어나지 않음을 검증할 수 없다"는
이유로 (i) `$HOME` 이 아닌 환경변수 읽기 (ii) 셸 `for` 루프 (iii) 큰 heredoc 을 거부한다
(docs/prps/dashboard-worktree-bash-gate.md 실측 M1~M15). `hub/rules/dashboard-recording.md`
가 이 파일을 Bash 로 직접 부른다 — `Skill(dashboard)` 은 더 이상 존재하지 않는다(HD1,
docs/prps/dashboard-into-hub.md — 진행 기록은 허브 설치기가 배포하는 자산이라 허브가 없는
머신에는 이 파일도 그 지침도 없다).

관문은 **명령줄만 검사하고 스크립트 파일 내용은 검사하지 않는다**(dashboard-worktree-bash-gate.md
M12~M14) — 이 파일은 그 정상 경로를 쓴다. 호출은
`python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" <서브커맨드> [인자…]` 다(프로젝트
폴백 없음 — 허브는 머신 전역 자산이라 프로젝트 사본을 두지 않는다, HD3). 서브커맨드 4종
(init·log·step·switch)과 각각의 출력 계약은 hub/README.md 「진행 기록」 절의
「헬퍼 스크립트」 표 참조 — 그 표가 폐쇄 어휘의 단일 출처이고, 이 파일은 표와 어긋나면
안 된다(G2 가드, T34).

이 파일은 I/O 층이다 — 파일에 닿는 얇은 껍데기. 이벤트 스키마 어휘(hub_parse.LOG_EVENT_KINDS·
STEP_STATES)는 hub_parse.py(★순수, 잎)에서 재사용한다(HD14) — 생산자(이 파일)와 소비자
(파서·렌더러)가 같은 상수를 본다.

기록 파일·오프 스위치·표시 이름은 cwd 가 아니라 **소유 레포 루트**(워크트리면 그 바깥 레포)
기준이다(`_dashboard_base_directory`) — 워크트리 폴더에 쓰면 `git worktree remove` 때 기록이
함께 사라져 허브가 끝난 작업을 미완료로 그렸다.

상태의 단일 출처는 세션별 JSONL 이다(DN2) — `init` 이 새로 쓰고 `log`·`step` 은 한 줄씩
append 한다. 동시 작업은 서브커맨드 바로 뒤 `--task '<이름표>'` 로 구분한다(docs/prps/
hub-dashboard-multi-task.md MT2) — 이름표 `init` 은 기존 기록을 지우지 않고 덧붙인다. HTML 은 더 이상 이 파일이 만들지 않는다(HD5·HD15,
docs/prps/dashboard-into-hub.md M2) — 화면은 허브 서버가 요청 때마다 이 JSONL 을 읽어
그 자리에서 렌더한다(hub_server.py). `render` 서브커맨드는 그 재발행이 필요 없어져
M2 에서 폐기됐다.

M1(docs/prps/dashboard-into-hub.md HD1·HD4)에서 commands/dashboard_helper.py 를 그대로
옮기며 HD14 세 가지를 허브 모듈 재사용으로 바꿨다 — 원자적 쓰기(hub_atomic_write)·오프
스위치 판정(hub_collect.read_dashboard_enabled)·경로 상수(hub_project). `sys.dont_write_bytecode`
는 뺐다 — 그 이유(commands/ 파일 수 계산 오염, T22-138)가 이 파일이 hub/bin 으로 옮겨오며
사라졌다(hub/install.sh 의 파일 수 계산은 `find -maxdepth 1 -type f` 라 __pycache__ 디렉터리를
애초에 세지 않는다).
"""

import json
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass

import hub_atomic_write
import hub_collect
import hub_parse
import hub_project

# ---------------------------------------------------------------------------
# 상수 — 이 파일(I/O 층)에서만 쓰는 값
# ---------------------------------------------------------------------------

# 옛 `find .claude/dashboards -mtime +7 -delete` 와 같은 임계값이다(ST5, 8일째부터 정리 대상).
RETENTION_SECONDS = 7 * 24 * 60 * 60

# 리텐션 대상 패턴 3종 — jsonl(DN2 의 상태 파일)과, M1 까지의 구세대 산출물(html·사이드카)이다.
# M2(HD8)에서 이 파일은 더 이상 html·사이드카를 만들지 않지만, 이미 디스크에 남아 있는
# 구세대 파일을 계속 청소해야 하므로 패턴 3종은 그대로 유지한다(§10.5).
_RETENTION_GLOB_PATTERNS = ("*.html", "*.jsonl", "*.init-values.json")

_SESSION_ID_PATTERN = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")

# 원자적 쓰기 임시 파일 접두(HD14 — hub_atomic_write.atomic_write_text 의 prefix 인자).
# jsonl·settings.local.json 쓰기가 모두 이 접두를 공유한다(사이드카·HTML 쓰기는 M2 에서
# 사라졌다, HD8·HD15 — 옛 로컬 _atomic_write_text 와 같은 관례).
_ATOMIC_WRITE_TEMP_PREFIX = ".dashboard-reissue-"


@dataclass(frozen=True)
class _DashboardPaths:
    """세션 ID 로부터 계산한 이 회차의 파일 경로(hub/README.md 「대시보드 경로 규칙」과
    1:1 대응). M2(HD8)에서 html·사이드카 경로가 사라져 jsonl 하나만 남는다."""

    jsonl_path: str


# ---------------------------------------------------------------------------
# I/O 층 — 파일에 닿는 얇은 껍데기. 순수 층을 호출하고 폐쇄 어휘를 출력한다.
# ---------------------------------------------------------------------------


def _current_session_id() -> str | None:
    return os.environ.get("CLAUDE_CODE_SESSION_ID")


def _resolve_paths(session_id: str | None) -> _DashboardPaths | None:
    """세션 ID가 UUID 형식이면 jsonl 경로를, 아니면 None 을 돌려준다.

    UUID 가 아니면 호출자가 NOSESSION 으로 처리한다 — LEGACY 경로가 없다(DN9). UUID 정규식이
    소문자 hex 와 '-' 만 허용하는 완전일치이므로 경로 구분자('/')나 '..' 가 섞인 값은 이
    정규식과 애초에 매치되지 않는다 — 별도 검사 없이 경로 탈출이 차단된다.
    """
    if not (session_id and _SESSION_ID_PATTERN.match(session_id)):
        return None
    return _DashboardPaths(jsonl_path=hub_project.session_dashboard_relative_path(session_id))


def _dashboard_base_directory() -> pathlib.Path:
    """기록 파일·스위치·표시 이름의 기준 폴더 — cwd 가 워크트리 안이면 소유 레포 루트다.

    워크트리 폴더의 `.claude/dashboards/` 는 gitignore 대상이라 `git worktree remove` 때 함께
    사라지고, 허브는 그러면 소유 루트의 낡은 기록으로 되돌아가 끝낸 작업을 미완료로 그렸다.
    허브가 워크트리를 소유 루트로 접어 보는 규칙(hub_project.fold_worktree_path)과 같은 함수를
    써서 읽는 쪽과 쓰는 쪽이 같은 폴더를 본다. 워크트리가 아니면 cwd 그대로라 일반 프로젝트의
    동작은 바뀌지 않는다.
    """
    return pathlib.Path(hub_project.fold_worktree_path(os.getcwd()))


def _cleanup_stale_session_dashboards(base_directory: pathlib.Path) -> None:
    """7일 초과 세션별 대시보드·상태·값 파일을 지운다(ST5) — 최선 노력이며 실패는 조용히 넘어간다.

    파일 단위로 예외를 잡는다 — 한 파일의 권한 문제가 나머지 정리를 막지 않는다. `init`
    본체(JSONL 새로 쓰기)는 이 정리의 성패와 무관하게 이어진다.
    """
    directory = base_directory / hub_project.SESSION_DASHBOARDS_RELATIVE_DIRECTORY
    if not directory.is_dir():
        return
    cutoff = time.time() - RETENTION_SECONDS
    for pattern in _RETENTION_GLOB_PATTERNS:
        for candidate in directory.glob(pattern):
            try:
                if candidate.stat().st_mtime < cutoff:
                    candidate.unlink()
            except OSError:
                continue


def _project_display_name(base_directory: pathlib.Path) -> str:
    """기준 폴더(소유 레포 루트)의 마지막 세그먼트 — init 이벤트의 project 필드로 쓰인다(허브
    hub_model._display_name 과 같은 규칙이라 같은 프로젝트가 두 화면에서 같은 문자열로 보이고,
    워크트리 이름이 프로젝트 이름으로 새지 않는다)."""
    return base_directory.name


def _now_ms() -> int:
    return int(time.time() * 1000)


def _dump_event_line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def _read_text_or_none(path: str) -> str | None:
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _read_existing_text(path: str) -> str:
    """기존 기록 본문. 파일이 없을 때만 빈 문자열이고, 있는데 못 읽으면(권한 등) OSError 를 그대로 올린다 — 빈 기록으로 보고
    덮어쓰면 이름표 init 이 기존 작업 기록을 지운다."""
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_text_atomically(final_path: str, text: str) -> None:
    """hub_atomic_write.atomic_write_text 를 이 파일의 호출 관례(경로 하나 + 본문)에
    맞춘 얇은 래퍼(HD14) — commands/·hub/bin/ 은 이제 같은 배포 채널이라 더는 이 관용구를
    따로 베끼지 않는다."""
    final = pathlib.Path(final_path)
    hub_atomic_write.atomic_write_text(final, final.parent, _ATOMIC_WRITE_TEMP_PREFIX, text)


# ---------------------------------------------------------------------------
# 서브커맨드 4종 — hub/README.md 「진행 기록」의 「헬퍼 스크립트」 표와 1:1 대응(G2, T34).
# ---------------------------------------------------------------------------


_TASK_OPTION = "--task"
INIT_POSITIONAL_ARGUMENT_COUNT = 2  # init 의 위치 인자: 제목·단계 목록


def _is_misplaced_task_option(arg: str) -> bool:
    """서브커맨드 바로 뒤가 아닌 자리에 놓인 `--task`·`--task=…` 인가. 요약·상세가 `--task 라는 글자…` 처럼 그저
    그 글자로 시작하는 본문은 아니다(정확히 `--task` 이거나 `--task=` 로 시작할 때만)."""
    return arg == _TASK_OPTION or arg.startswith(_TASK_OPTION + "=")


def _split_task_option(args: list[str]) -> tuple[str | None, list[str]] | None:
    """서브커맨드 바로 뒤 첫 인자의 `--task <이름표>` 를 떼어 (앞뒤 공백을 걷은 이름표, 나머지 인자) 를 돌려준다
    (결정 MT2). 옵션이 없으면 (None, args). 값이 없거나 형식 위반이거나 `--task=…` 처럼 `--task` 로 시작하는
    다른 첫 인자면 None(BADTASK) — 받지 않으면 `init --task=결함① …` 이 제목 「--task=결함①」인 무표 init 으로
    읽혀 기존 기록을 통째로 지운다. 떼고 남은 위치 인자 중에도 `--task`·`--task=…` 가 있으면 None 이다 — 맨 뒤에
    붙인 `init '제목' '단계' --task C` 가 무표 init 으로 읽혀 기록을 지우고, `log … --task B` 의 이름표가 버려져 첫 작업
    몫으로 기록되거나 상세로 들어가는 것을 막는다. 본문이 그저 `--task` 글자로 시작하는 요약·상세는 옵션이 아니다."""
    task_label: str | None = None
    positional_args = args
    if args and args[0].startswith(_TASK_OPTION):
        if args[0] != _TASK_OPTION or len(args) < 2:
            return None
        task_label = args[1].strip()
        if not hub_parse.is_valid_task_label(task_label):
            return None
        positional_args = args[2:]
    if any(_is_misplaced_task_option(arg) for arg in positional_args):
        return None
    return task_label, positional_args


def _with_task_label(event: dict, task_label: str | None) -> dict:
    """이름표가 있을 때만 `task` 키를 단 새 이벤트 — 이름표 없는 호출이 쓰는 바이트는 오늘과 같다(MT2)."""
    return event if task_label is None else {**event, "task": task_label}


def cmd_init(args: list[str]) -> None:
    session_id = _current_session_id()
    paths = _resolve_paths(session_id)
    if paths is None:
        print("NOSESSION")
        return
    base_directory = _dashboard_base_directory()
    if not hub_collect.read_dashboard_enabled(str(base_directory)):
        print("DISABLED")
        return
    task_split = _split_task_option(args)
    if task_split is None:
        print("BADTASK")
        return
    task_label, positional_args = task_split
    if len(positional_args) != INIT_POSITIONAL_ARGUMENT_COUNT:
        # 이름표 값을 빠뜨리면 제목이 이름표로 읽혀 인자가 모자라고, 철자 틀린 옵션(`--Task C`·`—task C`·`'--task C'`)이
        # 위치 인자로 남으면 이름표 없는 init 이 기록 전체를 지운다 — 어느 쪽이든 조용히 틀리게 쓰지 않는다.
        print("BADTASK")
        return
    title, phases_arg = positional_args[0], positional_args[1]
    jsonl_path = str(base_directory / paths.jsonl_path)
    try:
        os.makedirs(base_directory / hub_project.SESSION_DASHBOARDS_RELATIVE_DIRECTORY, exist_ok=True)
        _cleanup_stale_session_dashboards(base_directory)
        init_event = _with_task_label(
            {
                "time_ms": _now_ms(),
                "kind": "init",
                "title": title,
                "phases": phases_arg.split("|"),
                "project": _project_display_name(base_directory),
            },
            task_label,
        )
        # 이름표 없는 init 은 세션 기록을 새로 시작하고(오늘 동작), 이름표 붙은 init 은 기존 기록 뒤에 덧붙인다.
        kept_text = _read_existing_text(jsonl_path) if task_label is not None else ""
        _write_text_atomically(jsonl_path, kept_text + _dump_event_line(init_event))
    except OSError:
        print("MKDIR-FAILED")
        return
    print("OK")


@dataclass(frozen=True)
class _AppendTarget:
    """log·step 이 한 줄 덧붙일 대상 — 읽어 둔 현재 본문, 이름표, 이름표를 뗀 나머지 인자."""

    jsonl_path: str
    current_text: str
    task_label: str | None
    positional_args: list[str]


def _prepare_append(args: list[str]) -> _AppendTarget | None:
    """log·step 공통 앞 검사 NOSESSION → DISABLED → BADTASK → NOINIT. 걸리면 그 어휘를 출력하고 None."""
    session_id = _current_session_id()
    paths = _resolve_paths(session_id)
    if paths is None:
        print("NOSESSION")
        return None
    base_directory = _dashboard_base_directory()
    if not hub_collect.read_dashboard_enabled(str(base_directory)):
        print("DISABLED")
        return None
    task_split = _split_task_option(args)
    if task_split is None:
        print("BADTASK")
        return None
    jsonl_path = str(base_directory / paths.jsonl_path)
    current_jsonl_text = _read_text_or_none(jsonl_path)
    if current_jsonl_text is None:
        print("NOINIT")
        return None
    return _AppendTarget(jsonl_path, current_jsonl_text, task_split[0], task_split[1])


def _is_task_live(target: _AppendTarget) -> bool:
    """이름표가 없으면 첫 작업 몫이라 항상 참. 있으면 그 이름표 작업의 init 이 살아 있는 기록에 있어야 한다."""
    if target.task_label is None:
        return True
    live_labels = hub_parse.live_task_labels(hub_parse.parse_event_lines(target.current_text))
    return target.task_label in live_labels


def _append_event(target: _AppendTarget, event: dict) -> None:
    """이벤트(이름표 있으면 `task` 키 포함) 한 줄을 기록 뒤에 덧붙이고 OK 를 출력한다."""
    labeled_event = _with_task_label(event, target.task_label)
    _write_text_atomically(target.jsonl_path, target.current_text + _dump_event_line(labeled_event))
    print("OK")


def cmd_log(args: list[str]) -> None:
    target = _prepare_append(args)
    if target is None:
        return
    kind = target.positional_args[0]
    if kind not in hub_parse.LOG_EVENT_KINDS:
        print("BADKIND")
        return
    if not _is_task_live(target):
        print("NOTASK")
        return
    summary = target.positional_args[1]
    detail = target.positional_args[2] if len(target.positional_args) > 2 else ""
    _append_event(target, {"time_ms": _now_ms(), "kind": kind, "summary": summary, "detail": detail})


def _parse_step_args(args: list[str]) -> tuple[int | None, str]:
    """`<n> <state>` 를 파싱한다. n 이 1 이상 정수가 아니거나 state 가 done/active/wait 가
    아니면 (None, "")."""
    try:
        index = int(args[0])
    except ValueError:
        return None, ""
    if index < 1 or args[1] not in hub_parse.STEP_STATES:
        return None, ""
    return index, args[1]


def cmd_step(args: list[str]) -> None:
    target = _prepare_append(args)
    if target is None:
        return
    index, state = _parse_step_args(target.positional_args)
    if index is None:
        print("BADINDEX")
        return
    if not _is_task_live(target):
        print("NOTASK")
        return
    _append_event(target, {"time_ms": _now_ms(), "kind": "step", "index": index, "state": state})


def cmd_switch(state_arg: str) -> None:
    """DN16 — hub_collect.PROJECT_LOCAL_SETTINGS_RELATIVE_PATH(.claude/settings.local.json)의
    dashboard_enabled 필드만 설정한다. 다른 필드는 값·유무 그대로 보존한다. 파싱 실패 시
    쓰지 않는다(권한 허용 목록 보호가 이 불변식의 핵심 이유). 경로 상수를
    hub_collect.read_dashboard_enabled 와 공유해(HD14) 두 도구가 같은 스위치를 본다는
    RL10 합의가 코드로 강제된다."""
    desired_enabled = state_arg == "on"
    settings_path = _dashboard_base_directory() / hub_collect.PROJECT_LOCAL_SETTINGS_RELATIVE_PATH
    settings: dict = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print("INVALID-SETTINGS")
            return
        if not isinstance(settings, dict):
            print("INVALID-SETTINGS")
            return
    settings["dashboard_enabled"] = desired_enabled
    # .claude/ 가 아직 없는(첫 액션이 이 스위치인) 프로젝트에서도 쓸 수 있어야 한다 — 원자적
    # 쓰기는 대상 디렉터리가 이미 있다고 가정한다(hub_atomic_write.atomic_write_text 는
    # 디렉터리를 만들지 않는다). exist_ok=True 라 이미 있어도 무해하다.
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomically(str(settings_path), json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print("ON" if desired_enabled else "OFF")


# ---------------------------------------------------------------------------
# 디스패치
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: hub_dashboard_log.py <subcommand> [args...]", file=sys.stderr)
        return 2
    subcommand, args = argv[0], argv[1:]
    if subcommand == "init":
        cmd_init(args)
    elif subcommand == "log":
        cmd_log(args)
    elif subcommand == "step":
        cmd_step(args)
    elif subcommand == "switch":
        cmd_switch(args[0])
    else:
        print("unknown subcommand: %s" % subcommand, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
