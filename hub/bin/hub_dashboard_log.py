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
append 한다. HTML 은 더 이상 이 파일이 만들지 않는다(HD5·HD15,
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


def _write_text_atomically(final_path: str, text: str) -> None:
    """hub_atomic_write.atomic_write_text 를 이 파일의 호출 관례(경로 하나 + 본문)에
    맞춘 얇은 래퍼(HD14) — commands/·hub/bin/ 은 이제 같은 배포 채널이라 더는 이 관용구를
    따로 베끼지 않는다."""
    final = pathlib.Path(final_path)
    hub_atomic_write.atomic_write_text(final, final.parent, _ATOMIC_WRITE_TEMP_PREFIX, text)


# ---------------------------------------------------------------------------
# 서브커맨드 4종 — hub/README.md 「진행 기록」의 「헬퍼 스크립트」 표와 1:1 대응(G2, T34).
# ---------------------------------------------------------------------------


def cmd_init(title: str, phases_arg: str) -> None:
    session_id = _current_session_id()
    paths = _resolve_paths(session_id)
    if paths is None:
        print("NOSESSION")
        return
    base_directory = _dashboard_base_directory()
    if not hub_collect.read_dashboard_enabled(str(base_directory)):
        print("DISABLED")
        return
    try:
        os.makedirs(base_directory / hub_project.SESSION_DASHBOARDS_RELATIVE_DIRECTORY, exist_ok=True)
        _cleanup_stale_session_dashboards(base_directory)
        init_event = {
            "time_ms": _now_ms(),
            "kind": "init",
            "title": title,
            "phases": phases_arg.split("|"),
            "project": _project_display_name(base_directory),
        }
        _write_text_atomically(str(base_directory / paths.jsonl_path), _dump_event_line(init_event))
    except OSError:
        print("MKDIR-FAILED")
        return
    print("OK")


def cmd_log(args: list[str]) -> None:
    session_id = _current_session_id()
    paths = _resolve_paths(session_id)
    if paths is None:
        print("NOSESSION")
        return
    base_directory = _dashboard_base_directory()
    if not hub_collect.read_dashboard_enabled(str(base_directory)):
        print("DISABLED")
        return
    jsonl_path = str(base_directory / paths.jsonl_path)
    current_jsonl_text = _read_text_or_none(jsonl_path)
    if current_jsonl_text is None:
        print("NOINIT")
        return
    kind = args[0]
    if kind not in hub_parse.LOG_EVENT_KINDS:
        print("BADKIND")
        return
    event = {
        "time_ms": _now_ms(),
        "kind": kind,
        "summary": args[1],
        "detail": args[2] if len(args) > 2 else "",
    }
    new_jsonl_text = current_jsonl_text + _dump_event_line(event)
    _write_text_atomically(jsonl_path, new_jsonl_text)
    print("OK")


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
    session_id = _current_session_id()
    paths = _resolve_paths(session_id)
    if paths is None:
        print("NOSESSION")
        return
    base_directory = _dashboard_base_directory()
    if not hub_collect.read_dashboard_enabled(str(base_directory)):
        print("DISABLED")
        return
    jsonl_path = str(base_directory / paths.jsonl_path)
    current_jsonl_text = _read_text_or_none(jsonl_path)
    if current_jsonl_text is None:
        print("NOINIT")
        return
    index, state = _parse_step_args(args)
    if index is None:
        print("BADINDEX")
        return
    event = {"time_ms": _now_ms(), "kind": "step", "index": index, "state": state}
    new_jsonl_text = current_jsonl_text + _dump_event_line(event)
    _write_text_atomically(jsonl_path, new_jsonl_text)
    print("OK")


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
        cmd_init(args[0], args[1])
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
