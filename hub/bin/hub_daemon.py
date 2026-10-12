"""hub_daemon.py — 프로세스 생명주기: 분리 spawn · ps 신원 확인 · SIGTERM/SIGKILL · 상태 보고.

`is_our_server_process`·`browser_open_command`·`restart_note` 만 ★순수하다
(tests/hub/test_hub_daemon.py 대상). `parse_server_record` 는 hub_server_state.py 에 있다(검수 m3 —
hub_collect.py 와 이중으로 유지하던 순수 파서를 하나로 합쳤다). 나머지(`start_server`/
`stop_server`/`server_status`/`open_browser`/`restart_server`)는 subprocess·시그널·시각에
닿는 I/O 다.

모듈 이름이 `hub_launchd.py` 가 아니라 `hub_daemon.py` 인 것은 개정 1(rev2)의 결과다 —
특정 OS 서비스 관리자(launchd 등)에 묶이지 않는다는 사실이 이름에 드러나야 한다
(docs/prps/hub-dashboard.md 개정 쟁점 R1).
"""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import hub_collect
import hub_server_state
import hub_server_state_read

# "server-run" 이 있어야 한다 — 같은 hub.py 를 쓰는 배경 collect 프로세스(`hub.py collect`)를
# 서버로 오인하면 PID 재사용 방어의 의미가 없어진다.
SERVER_ENTRY_POINT_MARKER = "server-run"
# 구버전 레코드(hub_py_path 필드가 없다) 완화 판정에서 쓰는 토큰 접미. 슬래시를 포함해
# "hub.py" 단독 토큰(예: grep 인자로 등장하는 bare 파일명)을 배제한다 — 부분문자열보다
# 좁게 잡아 우연한 일치를 줄인다(docs/prps/hub-server-identity.md §3).
LEGACY_RECORD_HUB_PY_TOKEN_SUFFIX = "/hub.py"
HUB_PY_PATH = str(Path(__file__).resolve().parent / "hub.py")
BIND_ADDRESS = "127.0.0.1"
PORT_PROBE_TIMEOUT_SECONDS = 1
PS_TIMEOUT_SECONDS = 2
SERVER_START_WAIT_SECONDS = 5
SERVER_START_POLL_INTERVAL_SECONDS = 0.2
SERVER_STOP_WAIT_SECONDS = 5
SERVER_STOP_POLL_INTERVAL_SECONDS = 0.2
SERVER_LOG_TAIL_LINES = 20

# /usr/bin/open 은 -g 가 없으면 앱을 포그라운드로 올린다. 절대 경로를 쓰는 이유: PATH 에
# 같은 이름의 사용자 스크립트가 있으면 그것이 실행될 수 있다.
MACOS_OPEN_COMMAND_PATH = "/usr/bin/open"
MACOS_PLATFORM_NAME = "darwin"
BROWSER_OPEN_TIMEOUT_SECONDS = 5
FORCED_STOP_NOTE = "정상 종료 신호에 응답하지 않아 강제 종료했습니다"
SERVER_RESTART_PORT_WAIT_SECONDS = 3
SERVER_RESTART_PORT_POLL_INTERVAL_SECONDS = 0.1
ORPHANED_HEARTBEAT_REASON = (
    "정지 직후에도 서버가 살아 있다고 판정됐습니다 — 고아 하트비트일 수 있습니다"
    "(`/hub server status` 의 orphaned_evidence 를 확인하십시오)"
)


def _is_path_like_hub_py_path(hub_py_path: str | None) -> bool:
    """`hub_py_path` 값이 디렉토리 성분을 포함하는 경로 형태인가.

    `is_our_server_process` 의 완화 분기 판정과 `stop_server` 의 §5 게이트(완화 분기였는지
    세는 판정)가 **같은 기준**을 쓰게 하는 공용 헬퍼다(3회차 검수 Major 1) — 전에는
    `stop_server` 가 `record.hub_py_path is None` 만 완화로 셌는데, 이 판정은 None 과
    "hub.py" 같은 비경로 문자열을 **똑같이** 완화로 취급한다. 그 간극에서 비경로 문자열
    레코드가 완화 기준으로 신원이 확인되고도 §5 의 하트비트 게이트를 건너뛰어 무증인
    SIGTERM 으로 갔다(검수 실측). `/` 하나만 본다 — `LEGACY_RECORD_HUB_PY_TOKEN_SUFFIX`
    ("/hub.py")로 끝나는 값은 반드시 `/` 를 포함하므로 접미 검사를 따로 더할 이유가 없다
    (3회차 검수 Minor A, 죽은 조건 제거).
    """
    return hub_py_path is not None and "/" in hub_py_path


def is_our_server_process(ps_output: str, hub_py_path: str | None) -> bool:
    """`ps -p <pid> -o args=` 출력이 `hub_py_path` 로 기동된 우리 hub.py server-run 인가.

    PID 재사용으로 남의 프로세스를 죽이지 않기 위한 유일한 안전장치다. 판정할 수 없으면
    (빈 출력 등) False 를 돌려준다 — "확인할 수 없으면 손대지 않는다"가 안전한 기본값이다.

    `hub_py_path` 는 이 서버를 기동한 레코드 자신의 경로다 — 판정을 수행하는 이 모듈
    자신의 경로(HUB_PY_PATH)가 아니다. 두 값은 레포 사본·설치본처럼 허브가 두 벌 존재할
    때 서로 다를 수 있다(docs/prps/hub-server-identity.md §1). `hub_py_path` 가
    None(그 필드가 없던 구버전 레코드)이거나, 있어도 디렉토리 성분이 없는 파일명뿐인 값
    (예: 포그라운드 디버깅에서 온 bare "hub.py")이면 완화 기준으로 판정한다(2회차 검수
    Minor 2 — 경로 형태가 아닌 값을 엄격 대조에 그대로 쓰면 `in` 연산이 부분문자열 하나로
    풀려 hub.py 를 언급하는 아무 명령행에도 걸리고, 완화 기준보다도 약해진다). 완화 기준은
    공백으로 끊은 토큰 중 하나가 `/hub.py` 로 끝나고 `server-run` 을 담아야 우리 것으로
    본다(같은 문서 §3) — 디렉토리 성분 없이 기동된 프로세스는 이 접미 판정도 통과하지
    못한다(비망라 예시: 심볼릭 링크를 상대 경로로 참조해 기동한 경우도 같다. 전수 증명이
    아니다).
    """
    if not ps_output:
        return False
    if hub_py_path == "":
        return False
    if not _is_path_like_hub_py_path(hub_py_path):
        has_hub_py_token = any(
            token.endswith(LEGACY_RECORD_HUB_PY_TOKEN_SUFFIX) for token in ps_output.split()
        )
        return has_hub_py_token and SERVER_ENTRY_POINT_MARKER in ps_output
    return hub_py_path in ps_output and SERVER_ENTRY_POINT_MARKER in ps_output


# parse_server_record 는 hub_server_state.py 로 옮겼다(검수 m3) — hub_collect.py 와 이중으로
# 유지하던 순수 파서를 하나로 합쳤다. 이 모듈은 (다른 모든 실사용 경로와 마찬가지로)
# hub_server_state_read.read_server_record() 를 통해서만 이 값을 읽는다. 직접 호출이 필요하면
# hub_server_state.parse_server_record 를 쓴다.


def browser_open_command(platform_name: str, url: str) -> list[str] | None:
    """포커스까지 가져오며 URL 을 여는 외부 명령 argv. 지원 플랫폼이 아니면 None(webbrowser 폴백).

    `url` 은 argv 원소 하나로 그대로 넣는다 — 셸을 거치면 공백이 든 `file://` 경로가 두
    인자로 쪼개지고 셸 메타문자 주입 표면이 생긴다(GOTCHA 5). 리눅스·윈도우는 분기를 두지
    않는다 — `webbrowser` 가 이미 그 플랫폼에서 창을 올린다.
    """
    if platform_name == MACOS_PLATFORM_NAME:
        return [MACOS_OPEN_COMMAND_PATH, url]
    return None


def restart_note(stop_result: dict) -> str | None:
    """stop 단계의 이례(PID 재사용·이미 종료·강제 종료)를 사용자에게 알릴 한 줄로 바꾼다. 정상이면 None.

    `reason` 이 있으면 그 문구를 그대로 옮긴다 — 한국어 설명을 두 곳에서 관리하지 않기
    위해서다(그 문구는 stop_server 가 이미 만든다).
    """
    reason = stop_result.get("reason")
    if reason:
        return reason
    if stop_result.get("forced"):
        return FORCED_STOP_NOTE
    return None


# ---- I/O: 프로세스 조회·기동·종료 ----
def _now_ms() -> int:
    return int(time.time() * 1000)


def _is_port_occupied(port: int) -> bool:
    with socket.socket() as probe_socket:
        probe_socket.settimeout(PORT_PROBE_TIMEOUT_SECONDS)
        return probe_socket.connect_ex((BIND_ADDRESS, port)) == 0


def _ps_args_for_pid(pid: int) -> str | None:
    """`ps -p <pid> -o args=` 출력. 명령 실행 자체가 실패하면 None(판정 불가),
    프로세스가 없으면 빈 문자열, 있으면 그 명령행 문자열."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True, text=True, timeout=PS_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else ""


def _server_log_tail(max_lines: int = SERVER_LOG_TAIL_LINES) -> str:
    try:
        text = hub_collect.SERVER_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-max_lines:])


def _check_http_ok(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/hub.html", timeout=PORT_PROBE_TIMEOUT_SECONDS) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def _spawn_server_process() -> None:
    """세션 무관 분리 프로세스로 `hub.py server-run` 을 띄운다(개정 쟁점 R1)."""
    hub_collect.HUB_HOME.mkdir(parents=True, exist_ok=True)
    with open(hub_collect.SERVER_LOG_PATH, "a", encoding="utf-8") as log_file:
        subprocess.Popen(
            [sys.executable, HUB_PY_PATH, "server-run"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=log_file,
            start_new_session=True,   # setsid(2) — 부모 세션·터미널과 무관하게 산다
            close_fds=True,
        )


def _server_already_running(ttl_ms: int) -> bool:
    if hub_server_state.is_server_alive(_now_ms(), hub_server_state_read.read_server_heartbeat_mtime_ms(), ttl_ms):
        return True
    record = hub_server_state_read.read_server_record()
    if record is None:
        return False
    return is_our_server_process(_ps_args_for_pid(record.pid) or "", record.hub_py_path)


def start_server() -> dict:
    """멱등 확인 → 포트 프로브 → 분리 spawn → 하트비트 대기."""
    config, _config_warnings = hub_collect.load_config()
    ttl_ms = hub_server_state.server_heartbeat_ttl_ms(config.server_heartbeat_interval_seconds)

    if _server_already_running(ttl_ms):
        return {"ok": True, "already_running": True}
    if _is_port_occupied(config.server_port):
        return {"ok": False, "reason": f"포트 {config.server_port} 이 이미 사용 중입니다(다른 프로세스)"}

    _spawn_server_process()

    deadline = time.monotonic() + SERVER_START_WAIT_SECONDS
    while time.monotonic() < deadline:
        if hub_server_state.is_server_alive(_now_ms(), hub_server_state_read.read_server_heartbeat_mtime_ms(), ttl_ms):
            record = hub_server_state_read.read_server_record()
            return {
                "ok": True,
                "pid": record.pid if record else None,
                "url": f"http://localhost:{config.server_port}/hub.html",
            }
        time.sleep(SERVER_START_POLL_INTERVAL_SECONDS)
    return {"ok": False, "reason": "하트비트가 신선해지지 않았습니다", "log_tail": _server_log_tail()}


def _current_heartbeat_is_fresh() -> bool:
    """현재 설정의 TTL 로 하트비트 신선도를 판정한다(§5 게이트가 stop 경로에서 조회하는 값)."""
    config, _config_warnings = hub_collect.load_config()
    ttl_ms = hub_server_state.server_heartbeat_ttl_ms(config.server_heartbeat_interval_seconds)
    return hub_server_state.is_server_alive(_now_ms(), hub_server_state_read.read_server_heartbeat_mtime_ms(), ttl_ms)


def _preserve_state_diagnostic(record: hub_server_state.ServerRecord, reason: str) -> dict:
    """신원을 확정하지 못했을 때 상태 파일을 보존하며 ok:false 로 보고한다(§5 게이트의 공통 반환)."""
    return {"ok": False, "reason": reason, "pid": record.pid, "recorded_hub_py_path": record.hub_py_path}


def stop_server() -> dict:
    """신원 확인 → SIGTERM → (필요 시) SIGKILL → 상태 파일 정리.

    정확한 경로 일치가 아닐 때는 하트비트가 게이트한다
    (docs/prps/hub-server-identity.md §5·D4·R4). 방향이 두 분기에서 반대라 뭉뚱그리면
    안 된다 — 신원이 불일치하면 하트비트가 `만료`돼야(살아 있다는 증거가 없어야) 상태 파일
    정리로 넘어가고, 완화 기준으로만 일치했으면 반대로 하트비트가 `신선`해야(생존이
    확증돼야) kill 로 넘어간다. 어긋나는 두 조합(불일치+신선 · 완화 일치+만료)은 상태
    파일을 보존한 채 `ok:false` 로 진단만 낸다.

    `clear_server_state` 는 항상 `expected_pid=record.pid` 로 호출한다
    (compare-and-delete, 검수 m1) — 그 사이 다른 프로세스가 새 서버를 등록했을 수 있어서다.
    """
    record = hub_server_state_read.read_server_record()
    if record is None:
        return {"ok": True, "was_running": False}

    ps_args = _ps_args_for_pid(record.pid)
    if ps_args is None:
        return {"ok": False, "reason": "ps 실행 실패 — 확인할 수 없어 아무것도 하지 않았습니다"}
    if not ps_args:
        hub_server_state_read.clear_server_state(expected_pid=record.pid)
        return {"ok": True, "was_running": False, "reason": "프로세스가 이미 종료돼 있어 상태 파일만 정리했습니다"}

    identity_match = is_our_server_process(ps_args, record.hub_py_path)
    # is_our_server_process 호출은 여기 둔다(T25-16·D7). 완화 분기 판정은 공용 헬퍼로 뽑는다
    # (3회차 검수 Major 1 — 이유는 _is_path_like_hub_py_path 문서 참고).
    is_legacy_relaxed_match = identity_match and not _is_path_like_hub_py_path(record.hub_py_path)
    if not identity_match or is_legacy_relaxed_match:
        heartbeat_fresh = _current_heartbeat_is_fresh()
        if is_legacy_relaxed_match and not heartbeat_fresh:
            return _preserve_state_diagnostic(
                record,
                f"PID {record.pid} 이 적어 둔 기동 경로가 경로 형태가 아니어서 "
                "완화 기준과 일치했지만 하트비트가 없어 "
                "우리 서버라는 확증이 없습니다 — 상태 파일을 그대로 두고 아무것도 하지 않았습니다",
            )
        if not identity_match:
            if heartbeat_fresh:
                return _preserve_state_diagnostic(
                    record,
                    f"PID {record.pid} 의 프로세스를 우리 서버로 확인하지 못했는데 하트비트는 살아 있습니다 — "
                    "오판일 수 있어 상태 파일을 그대로 두고 아무것도 하지 않았습니다",
                )
            hub_server_state_read.clear_server_state(expected_pid=record.pid)
            return {
                "ok": True, "was_running": False,
                "reason": "PID 가 재사용됐습니다 — 그 프로세스는 건드리지 않고 상태 파일만 정리했습니다",
            }

    try:
        os.kill(record.pid, signal.SIGTERM)
    except ProcessLookupError:
        hub_server_state_read.clear_server_state(expected_pid=record.pid)
        return {"ok": True, "was_running": False}
    return _wait_for_process_exit(record)


def _wait_for_process_exit(record: hub_server_state.ServerRecord) -> dict:
    """SIGTERM 후 최대 SERVER_STOP_WAIT_SECONDS 동안 재확인하고, 안 죽으면 SIGKILL.

    재확인도 record 의 경로로 대조한다(pid 하나가 아니라 record 전체를 받는 이유) — 이
    모듈 자신의 경로(HUB_PY_PATH)로 대조하면 두 벌 설치에서 살아 있는 프로세스를 죽었다고
    오판해 상태 파일을 지운다(docs/prps/hub-server-identity.md §4).
    """
    deadline = time.monotonic() + SERVER_STOP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not is_our_server_process(_ps_args_for_pid(record.pid) or "", record.hub_py_path):
            hub_server_state_read.clear_server_state(expected_pid=record.pid)
            return {"ok": True, "was_running": True}
        time.sleep(SERVER_STOP_POLL_INTERVAL_SECONDS)

    try:
        os.kill(record.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    hub_server_state_read.clear_server_state(expected_pid=record.pid)
    return {"ok": True, "was_running": True, "forced": True}


def _wait_for_port_release(port: int) -> None:
    """포트가 풀릴 때까지 최대 SERVER_RESTART_PORT_WAIT_SECONDS 동안 폴링한다(D5).

    SIGKILL 직후 커널이 리스닝 소켓을 정리하기까지의 아주 짧은 창에 start 가 돌면 "다른
    프로세스가 점유 중"이라는 틀린 진단이 난다. 대기는 짧고 상한이 있어야 한다(GOTCHA 2) —
    초과해도 그냥 넘어간다. 그때는 정말 남의 프로세스이고 start 의 진단이 정확하다.
    """
    deadline = time.monotonic() + SERVER_RESTART_PORT_WAIT_SECONDS
    while time.monotonic() < deadline and _is_port_occupied(port):
        time.sleep(SERVER_RESTART_PORT_POLL_INTERVAL_SECONDS)


def restart_server() -> dict:
    """기존 서버를 확실히 내린 뒤 새로 띄운다(멱등 start 와 달리 항상 재기동한다).

    stop 이 실패하면 start 를 시도하지 않는다 — 낡은 서버가 살아 있을 수 있는 상태에서
    새로 띄우면 서버가 둘이 되려 시도하거나 포트 충돌로 엉뚱한 진단을 낸다(D4).
    stop_server()·start_server() 를 그대로 호출하며(D3), 그 사이에 포트 해제를 잠깐
    기다린다 — 두 함수의 안전장치(신원 확인·멱등)를 복제하지 않는다(GOTCHA 1).
    """
    stop_result = stop_server()
    if not stop_result.get("ok"):
        return {"ok": False, "phase": "stop", "reason": stop_result.get("reason")}

    config, _config_warnings = hub_collect.load_config()
    _wait_for_port_release(config.server_port)

    start_result = start_server()
    if start_result.get("already_running"):
        # stop 을 성공시킨 직후이므로 이 상태는 정상이 아니다 — 고아 하트비트일 가능성이
        # 크다(D6). 그 파일을 여기서 지우지 않는다(D7) — compare-and-delete 가 막으려던
        # 위험(다른 셸이 그 사이 띄운 새 서버의 기록을 지우는 것)을 재현하지 않기 위해서다.
        return {"ok": False, "phase": "start", "reason": ORPHANED_HEARTBEAT_REASON}
    if not start_result.get("ok"):
        result = {"ok": False, "phase": "start", "reason": start_result.get("reason")}
        if "log_tail" in start_result:
            result["log_tail"] = start_result["log_tail"]
        return result

    result = {
        "ok": True,
        "stopped_previous": stop_result.get("was_running", False),
        "pid": start_result.get("pid"),
        "url": start_result.get("url"),
    }
    note = restart_note(stop_result)
    if note is not None:
        result["note"] = note
    return result


def server_status() -> hub_server_state.ServerStatus:
    """프로세스 · 하트비트 · HTTP 응답 · 비정상 종료 흔적 · 수집 건강도를 종합 판정한다."""
    config, _config_warnings = hub_collect.load_config()
    record = hub_server_state_read.read_server_record()
    process_present = record is not None and is_our_server_process(
        _ps_args_for_pid(record.pid) or "", record.hub_py_path
    )
    heartbeat_mtime_ms = hub_server_state_read.read_server_heartbeat_mtime_ms()
    ttl_ms = hub_server_state.server_heartbeat_ttl_ms(config.server_heartbeat_interval_seconds)
    alive = hub_server_state.is_server_alive(_now_ms(), heartbeat_mtime_ms, ttl_ms)
    heartbeat_age_ms = (_now_ms() - heartbeat_mtime_ms) if heartbeat_mtime_ms is not None else None
    crashed_evidence = record is not None and not alive and not process_present
    # 프로세스(HTTP 서버 스레드)는 살아 있는데 하트비트만 만료됐다 — 유지보수 티커만 죽은
    # 상태다(검수 M2, 개정 2 — 이전 필드명에서 이름만 사실에 맞춰 고쳤다. 판정식은 그대로다).
    # HTTP 는 계속 200 을 돌려줘 겉으론 정상처럼 보이지만, 하트비트가 갱신되지 않는다.
    # crashed_evidence 는 "프로세스까지 죽었다"에 한정되므로 이 상태는 이름이 따로 필요하다.
    maintenance_stalled = process_present and not alive
    # 하트비트는 살아 있는데 server.json 이 없다 — CLI 로는 PID 를 몰라 찾지도 끌 수도 없는
    # 고아 신호다(검수 m1). compare-and-delete 도입 전에는 잘못된 clear_server_state() 가
    # 이 상태를 만들 수 있었다; 지금은 예방됐지만, 과거에 이미 만들어졌거나 수동 조작으로
    # 생길 수 있는 상태이므로 관측 필드로 남겨 사용자가 직접 발견하게 한다.
    orphaned_evidence = record is None and alive
    success_at_ms = hub_server_state_read.read_collect_success_stamp_mtime_ms()
    failure = hub_collect.read_last_collect_failure()
    collect_health = hub_server_state.evaluate_collect_health(
        last_success_at_ms=success_at_ms,
        last_failure_at_ms=(failure or {}).get("at_ms"),
    )
    last_collect_success_age_ms = (_now_ms() - success_at_ms) if success_at_ms is not None else None
    return hub_server_state.ServerStatus(
        record=record,
        process_present=process_present,
        heartbeat_age_ms=heartbeat_age_ms,
        alive=alive,
        http_ok=_check_http_ok(config.server_port),
        crashed_evidence=crashed_evidence,
        # crashed_evidence(완전 사망)·maintenance_stalled(유지보수 티커만 사망)·
        # collect_health=="failing"(수집만 실패) 셋 다 "무언가 죽었다"이고, 원인 규명에는
        # 같은 server.log 꼬리가 쓰인다(검수 M2-3, §0.3 정정 3) — 증거 창구가 같다. 티커만
        # 죽으면 요청 구동 수집은 계속 성공해 collect_health 는 ok 로 남으므로, 이 항을
        # 빼면 스레드 사망 트레이스백이 남아 있는 유일한 순간을 놓친다.
        log_tail=_server_log_tail()
        if (crashed_evidence or maintenance_stalled or collect_health == "failing")
        else None,
        orphaned_evidence=orphaned_evidence,
        maintenance_stalled=maintenance_stalled,
        collect_health=collect_health,
        last_collect_success_age_ms=last_collect_success_age_ms,
    )


# ---- I/O: 브라우저 ----
def _fallback_to_webbrowser(url: str, fallback_reason: str | None) -> hub_server_state.BrowserOpenResult:
    """포커스 경로가 없거나 실패했을 때 webbrowser 로 연다. 예외는 밖으로 내지 않는다(GOTCHA 7).

    webbrowser.open() 이 던지는 예외도 fallback_reason 에 담는다 — 포커스 경로 실패 사유가
    이미 있으면 그것을 보존하고, 없을 때만(포커스 경로 자체가 없던 경우) 이 예외로 채운다.
    그러지 않으면 두 경로가 모두 실패했을 때 사유가 통째로 사라진다.
    """
    try:
        opened = bool(webbrowser.open(url))
    except Exception as error:
        opened = False
        if fallback_reason is None:
            fallback_reason = str(error)
    return hub_server_state.BrowserOpenResult(opened=opened, focus_requested=False, fallback_reason=fallback_reason)


def open_browser(url: str, platform_name: str = sys.platform) -> hub_server_state.BrowserOpenResult:
    """포커스 경로로 URL 을 열고, 안 되면 webbrowser 로 폴백한다. 예외를 밖으로 내보내지 않는다."""
    command = browser_open_command(platform_name, url)
    if command is None:
        return _fallback_to_webbrowser(url, fallback_reason=None)
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=BROWSER_OPEN_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return _fallback_to_webbrowser(url, fallback_reason=str(error))
    if result.returncode == 0:
        return hub_server_state.BrowserOpenResult(opened=True, focus_requested=True, fallback_reason=None)
    return _fallback_to_webbrowser(
        url, fallback_reason=f"{MACOS_OPEN_COMMAND_PATH} 종료 코드 {result.returncode}"
    )
