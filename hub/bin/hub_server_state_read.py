"""hub_server_state_read.py — 상주 서버 상태(하트비트·server.json·성공 스탬프)의 I/O.

hub_workflow.py(★순수)/hub_workflow_read.py(I/O) · hub_subagent.py/hub_subagent_read.py ·
hub_live_session.py/hub_live_session_read.py 세 쌍과 이름·역할·임포트 방향이 동형이다 — 판정·
파싱은 hub_server_state.py(★순수, 잎 모듈)에 있고, 그 결과를 실제 파일에 읽고 쓰는 쪽은 여기 있다.
hub_collect.py 가 리베이스로 808/800줄이 되어 다시 상한을 넘겼을 때(서브에이전트 생존 신호
작업과 다른 세션의 세션·프로젝트·카드 변경이 합쳐진 결과 — 어느 한쪽 단독으로는 넘지 않았다)
이 블록을 옮겨 상한 아래로 되돌렸다. 이 분리는 새로 정한 것이 아니다 —
docs/prps/hub-subagent-liveness-signal.md §11 R4 가 "다음 회차가 이 파일을 또 늘려야 하면 그때
분리한다"고 이미 예견해 둔 지점이고, 절차 자체는 docs/prps/hub-model-module-split.md 결정 MS1
을 다시 적용한 것이다. 이 블록을 고른 이유는 다른 세션이 같은 파일의 세션·프로젝트·카드 쪽을
동시에 편집 중이라 겹치지 않는 부분이 필요해서였다.

hub_workflow_read.py 등 세 쌍은 hub_collect.collect_snapshot 파이프라인 **안에서만** 호출되어
PROJECTS_DIR 처럼 호출자가 이미 아는 공용 경로를 인자로 받는다(순환 임포트 회피, 각 모듈
docstring 참조). 이 모듈은 다르다 — 7개 함수 전부가 hub.py·hub_daemon.py·hub_server.py·
hub_hook.py 에서 파이프라인 바깥으로도 직접 호출되고, 그중 일부는 서로를 내부에서 부른다
(clear_server_state → read_server_record). 시그니처를 그대로 두는 것이 이 분리의 요구(동작
변경 0)였으므로, HUB_HOME·SERVER_RECORD_PATH·SERVER_HEARTBEAT_PATH·COLLECT_SUCCESS_STAMP_PATH
4개를 매 호출마다 인자로 꿰어 넘기는 대신 이 모듈이 직접 선언한다 — hub_collect.py 가 자신의
HUB_HOME 을 선언하는 것과 같은 방식이다. hub_atomic_write.py(표준 라이브러리만 임포트)와
hub_server_state.py("어떤 허브 모듈도 임포트하지 않는 잎 모듈")만 임포트하므로 hub_collect.py
와의 순환은 구조적으로 생기지 않는다.
"""

import dataclasses
import json
from pathlib import Path

import hub_atomic_write
import hub_server_state

HUB_HOME = Path.home() / ".claude" / "hub"
# 상주 서버(개정 1 rev2) 상태 파일 2종. server.json 은 서버 자신이 bind 직후 1회,
# server_heartbeat 는 유지보수 티커가 매 사이클 touch 한다. server.log(stderr 리다이렉션
# 대상)는 이 두 파일과 달리 hub_collect.py 에 남아 있다 — 이 모듈의 7개 함수 중 어느 것도
# 그 파일을 쓰거나 읽지 않는다.
SERVER_RECORD_PATH = HUB_HOME / "server.json"
SERVER_HEARTBEAT_PATH = HUB_HOME / "server_heartbeat"
# 마지막으로 수집이 성공한 시각의 스탬프(개정 2) — evaluate_collect_health 의 유일한 성공
# 시각 출처다. hub.html 의 mtime 은 쓸 수 없다 — 내용이 같으면 다시 쓰지 않으므로 그 mtime 은
# "마지막 변화 시각"일 뿐 "마지막 수집 시각"이 아니다. 서버 생애(clear_server_state)와
# 무관하게 남는다 — 수집 이력이지 서버가 살아 있었다는 증거가 아니므로 재기동해도 지우지 않는다.
COLLECT_SUCCESS_STAMP_PATH = HUB_HOME / "last_collect_success"


def touch_server_heartbeat() -> None:
    """상주 서버의 유지보수 티커가 매 사이클 호출한다 — 생존 판정의 정본(TTL 안이면 살아 있다)."""
    HUB_HOME.mkdir(parents=True, exist_ok=True)
    SERVER_HEARTBEAT_PATH.touch(exist_ok=True)


def read_server_heartbeat_mtime_ms() -> int | None:
    """하트비트 파일의 mtime(ms). 없으면 None."""
    try:
        return int(SERVER_HEARTBEAT_PATH.stat().st_mtime * 1000)
    except OSError:
        return None


def touch_collect_success_stamp() -> None:
    """수집이 성공할 때마다(쓰기를 건너뛴 사이클 포함) 호출한다 — collect_health 판정의
    유일한 성공 시각 출처다(개정 2)."""
    HUB_HOME.mkdir(parents=True, exist_ok=True)
    COLLECT_SUCCESS_STAMP_PATH.touch(exist_ok=True)


def read_collect_success_stamp_mtime_ms() -> int | None:
    """마지막 수집 성공 스탬프의 mtime(ms). 없으면(한 번도 성공한 적 없으면) None."""
    try:
        return int(COLLECT_SUCCESS_STAMP_PATH.stat().st_mtime * 1000)
    except OSError:
        return None


def write_server_record(record: hub_server_state.ServerRecord) -> None:
    """server.json 을 원자적으로 쓴다. 서버 자신이 bind 성공 직후 1회만 호출한다."""
    HUB_HOME.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dataclasses.asdict(record), ensure_ascii=False)
    hub_atomic_write.atomic_write_text(SERVER_RECORD_PATH, HUB_HOME, "server.json.", payload)


def read_server_record() -> hub_server_state.ServerRecord | None:
    """server.json 을 읽어 판다. 없거나 깨졌으면 None.

    파싱은 hub_server_state.parse_server_record(순수)에 위임한다(검수 m3) — 예전에는 순환
    임포트를 피하려고 이 함수 안에 같은 로직을 따로 두었는데, 그 결과 실제 운영 경로(이 함수)가
    테스트 대상(hub_daemon 의 사본)과 다른 코드를 쓰는 위험이 있었다. hub_server_state.py 는
    다른 허브 모듈을 임포트하지 않는 잎 모듈이라 순환이 구조적으로 불가능하다.
    """
    try:
        text = SERVER_RECORD_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    return hub_server_state.parse_server_record(text)


def clear_server_state(expected_pid: int | None = None) -> None:
    """server.json + 하트비트를 제거한다. SIGTERM 정리와 stale 정리 양쪽에서 쓴다.

    `expected_pid` 가 주어지면 **compare-and-delete** 로 동작한다(검수 m1) — 삭제 직전에
    server.json 을 다시 읽어 그 pid 가 여전히 `expected_pid` 와 같을 때만 지운다. 무조건
    삭제하면, 이 함수를 부르기로 판단한 시점과 실제 삭제 시점 사이에 다른 프로세스(다른
    셸의 `server-start` 등)가 새 서버를 띄워 server.json 을 갈아 끼웠을 경우 방금 뜬 새
    서버의 기록을 지워 CLI 로는 더 이상 찾지도 끌 수도 없는 고아로 만든다(실측).
    `expected_pid` 를 생략하면(기본값 `None`) 무조건 삭제한다 — 다만 실사용 호출부는 SIGTERM
    핸들러를 포함해 전부 자신의 pid 를 `expected_pid` 로 넘긴다(검수 Nit). 이 무조건 삭제
    경로는 지금은 어떤 실행 경로도 밟지 않는 방어적 기본값이고, 최소 동작 확인은 테스트에서만
    한다.
    """
    if expected_pid is not None:
        current_record = read_server_record()
        if current_record is not None and current_record.pid != expected_pid:
            return
    SERVER_RECORD_PATH.unlink(missing_ok=True)
    SERVER_HEARTBEAT_PATH.unlink(missing_ok=True)
