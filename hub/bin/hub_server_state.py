"""hub_server_state.py — 상주 서버의 기록 형식과 생존·재수집 판정(순수).

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_server_state.py 대상).
어떤 허브 모듈도 임포트하지 않는 **잎 모듈**이다 — parse_server_record 가 예전에
hub_daemon.py·hub_collect.py 에 사본으로 갈라져 있던 이유가 "순환 임포트 회피"였고(검수 m3),
잎으로 두면 그 위험이 구조적으로 재발할 수 없다. 설계 정본은
docs/prps/hub-dashboard.md 「상주 서버」 절과 docs/prps/hub-server-control-skill.md 다.
"""

import json
from dataclasses import dataclass
from typing import Literal


# ---- 상주 서버 (개정 1 rev2, hub_py_path 는 개정 3) ----
@dataclass(frozen=True)
class ServerRecord:
    """server.json 의 내용 — 서버 자신이 bind 성공 직후 1회 쓴다."""

    pid: int
    port: int
    started_at_ms: int
    # 이 서버를 띄운 hub.py 의 경로 — `sys.argv[0]` 그대로다(정규화하지 않는다).
    # 정규화하지 않는 이유: 신원 대조 상대가 `ps -p <pid> -o args=` 텍스트이고 그 텍스트는
    # 정규화되지 않은 argv 다. 상대 경로·심볼릭 링크 경유 실행에서 Path.resolve() 결과는
    # ps 출력의 부분문자열이 아니다(docs/prps/hub-server-identity.md 관측 E).
    # None = 이 필드가 없던 구버전 코드가 쓴 레코드(완화 판정으로 강등, 같은 문서 §3).
    hub_py_path: str | None = None


# 수집 건강도 판정 결과(개정 2, evaluate_collect_health 참조). "최근에 수집이 없었다"가
# 그대로 고장을 뜻하지 않는 요청 구동 수집에서, "수집이 실제로 되고 있는가"에 답한다.
CollectHealth = Literal["ok", "failing", "never_collected"]


@dataclass(frozen=True)
class ServerStatus:
    """`/hub server status` 의 보고 단위.

    `maintenance_stalled` 는 이전 필드명에서 이름만 사실에 맞춰 바꾼 것이다 — 판정식은
    그대로다. 프로세스(HTTP 서버 스레드)는 살아 있는데 유지보수 티커만 죽어 하트비트가
    만료된 상태를 가리킨다(검수 M2, 개정 2). `crashed_evidence`(완전 사망)와는 다른
    상태라 이름이 따로 필요했다.
    """

    record: ServerRecord | None
    process_present: bool
    heartbeat_age_ms: int | None
    alive: bool
    http_ok: bool
    crashed_evidence: bool
    log_tail: str | None
    orphaned_evidence: bool                        # 하트비트는 살아 있는데 server.json 이 없다(검수 m1)
    maintenance_stalled: bool                       # 유지보수 티커만 죽은 상태(위 docstring 참조)
    collect_health: CollectHealth                   # 수집이 실제로 되고 있는가(개정 2 신설)
    last_collect_success_age_ms: int | None         # 마지막 수집 성공으로부터 지난 시간(ms, 개정 2 신설)


# ---- 브라우저 열기 (재기동 + 포커스, docs/prps/hub-server-control-skill.md) ----
@dataclass(frozen=True)
class BrowserOpenResult:
    """브라우저 열기 시도의 결과. `focus_requested` 는 '포그라운드로 올리는 경로를 썼다'는
    뜻이며, 실제로 창이 올라왔는지는 OS 소관이라 확인하지 않는다.

    `fallback_reason` 이 필요한 이유: macOS 에서 탭은 떴는데 창이 뒤에 남는 상황이 이 기능이
    고치려는 증상이다. 폴백이 조용히 일어나면 사용자는 "고쳐졌다더니 그대로"만 보게 된다 —
    이 필드가 그 원인을 표면화하는 유일한 창구다.
    """

    opened: bool                       # URL 을 여는 데 성공했는가
    focus_requested: bool              # 포커스를 가져오는 경로(/usr/bin/open)로 열었는가
    # 포커스 경로 실패 사유 또는(포커스 경로가 없던 플랫폼이면) webbrowser 예외. 정상이면 None
    fallback_reason: str | None


# ---- 상주 서버 (개정 1 rev2) ----
SERVER_HEARTBEAT_TTL_MULTIPLIER = 3      # 하트비트 주기의 3배까지는 살아 있다고 본다(개정 2 — 수집 주기가 아니다)
SERVER_HEARTBEAT_MIN_TTL_SECONDS = 15    # 주기를 아주 짧게 잡아도 하한을 둔다
MILLISECONDS_PER_SECOND = 1000


def server_heartbeat_ttl_ms(heartbeat_interval_seconds: int) -> int:
    """하트비트를 '살아 있음'으로 인정하는 최대 나이(ms)."""
    ttl_seconds = max(
        heartbeat_interval_seconds * SERVER_HEARTBEAT_TTL_MULTIPLIER,
        SERVER_HEARTBEAT_MIN_TTL_SECONDS,
    )
    return ttl_seconds * MILLISECONDS_PER_SECOND


def is_server_alive(now_ms: int, heartbeat_mtime_ms: int | None, ttl_ms: int) -> bool:
    """하트비트 나이로 상주 서버 생존을 판정한다. 파일이 없으면 False."""
    if heartbeat_mtime_ms is None:
        return False
    return (now_ms - heartbeat_mtime_ms) < ttl_ms


def evaluate_collect_health(
    last_success_at_ms: int | None,
    last_failure_at_ms: int | None,
) -> CollectHealth:
    """마지막 성공·실패 시각으로 수집 건강도를 판정한다(순수).

    요청 구동 수집(개정 2)에서는 "최근에 수집이 없었다"가 고장이 아니다 — 아무도 페이지를
    열지 않았다는 뜻일 수 있다. 그래서 나이(age)로 판정하지 않고 **성공과 실패의 순서**만
    본다. 동시각(둘이 같음)은 성공으로 접는다 — 한 사이클이 성공하면
    `clear_collect_failure()` 가 실패 기록을 지운 뒤 성공 스탬프를 찍으므로, 같은 ms 에
    둘이 잡히면 성공이 나중이다.
    """
    if last_failure_at_ms is None:
        return "ok" if last_success_at_ms is not None else "never_collected"
    if last_success_at_ms is None:
        return "failing"
    return "failing" if last_failure_at_ms > last_success_at_ms else "ok"


def _normalize_hub_py_path(raw_value: object) -> str | None:
    """hub_py_path 필드를 접는다 — 문자열이 아니거나 공백만이면 None
    (docs/prps/hub-server-identity.md §9-1 P3~P5 회귀 방지). 비공백 문자열은 그대로
    보존한다 — 여기서 손질(strip 등)하면 ps 출력과의 부분문자열 대조가 그만큼 깨질 수
    있다(같은 문서 관측 E, D2)."""
    if not isinstance(raw_value, str):
        return None
    return raw_value if raw_value.strip() else None


def parse_server_record(text: str) -> ServerRecord | None:
    """server.json 텍스트를 판다. 깨졌거나 필수 필드가 없으면 None(예외를 던지지 않는다).

    hub_daemon.py(신원 확인·kill 경로)와 hub_server_state_read.py(read_server_record)가 둘
    다 이 함수를 쓴다 — 예전에는 두 곳에 같은 로직이 따로 있어(순환 임포트를 피하려는 시도),
    실제 운영 경로(hub_server_state_read.read_server_record)가 테스트 대상(hub_daemon 사본)과
    달라지는 위험이 있었다(검수 m3). 이 모듈(hub_server_state)은 다른 허브 모듈을 임포트하지
    않는 잎 모듈이라 순환 자체가 구조적으로 불가능하다.

    hub_py_path 는 선택 필드다 — 없거나 null 이거나 공백만이면 None 으로 접는다. 필수로
    만들면 그 필드가 없던 구버전 레코드가 통째로 None 이 되어 그 서버가 영구 정지 불가가
    된다(docs/prps/hub-server-identity.md 관측 B).
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return ServerRecord(
            pid=int(payload["pid"]),
            port=int(payload["port"]),
            started_at_ms=int(payload["started_at_ms"]),
            hub_py_path=_normalize_hub_py_path(payload.get("hub_py_path")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def should_spawn_collect(
    now_ms: int,
    server_alive: bool,
    hub_html_mtime_ms: int | None,
    spawn_stamp_mtime_ms: int | None,
    throttle_ms: int,
) -> bool:
    """훅이 재수집을 spawn 해야 하는가. 서버가 살아 있으면 항상 False(수집 위임).

    `hub_html_mtime_ms` 가 없을 때(서버가 아직/다시는 hub.html 을 만들지 못한 상태)도 서버가
    죽어 있으면 True 를 돌려준다(검수 M2-5) — 예전에는 이 경우 무조건 False 라, 상주 서버가
    HUB_HOME 쓰기 불가 등으로 hub.html 을 한 번도 못 만든 채 수집 스레드까지 죽으면 훅 폴백
    조차 영원히 뚫리지 않는 이중 실패였다(실측: 서버는 HTTP 로 계속 응답해 `server_alive` 는
    이미 이 함수 호출 전 단계에서 False 로 판정되지만, hub.html 부재가 이어지면 사용자는
    영구히 빈 페이지만 본다). `spawn_stamp` 로는 여전히 쓰로틀한다 — 스탬프가 없으면(첫
    시도) 곧바로 True.
    """
    if server_alive:
        return False
    if hub_html_mtime_ms is None:
        if spawn_stamp_mtime_ms is None:
            return True
        return (now_ms - spawn_stamp_mtime_ms) >= throttle_ms
    reference_mtime_ms = (
        spawn_stamp_mtime_ms if spawn_stamp_mtime_ms is not None else hub_html_mtime_ms
    )
    return (now_ms - reference_mtime_ms) >= throttle_ms
