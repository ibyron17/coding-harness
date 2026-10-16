"""hub_server.py — 상주 서버 본체. `server-run` 의 진입점.

메인 스레드는 허용 경로 화이트리스트만 서빙하는 HTTP 서버이자 요청 구동 수집(개정 2)의
트리거다 — 수집 경로는 `_SnapshotRefresher` 하나뿐이고, 요청과 유지보수 티커가 그것을
공유한다. 데몬 스레드는 더 이상 수집을 직접 하지 않고 둘로 나뉜다 — 하트비트 touch·배경
수집 상한 보장만 도는 유지보수 티커(`_maintenance_loop`)와, 사용량 API 폴링 전용 스레드
(`_usage_api_poll_loop`, 결정 AR5). 원래는 폴링도 유지보수 티커가 겸했으나, 원격 호출
(최악 15초 블로킹, hub_usage_fetch.py)이 하트비트와 같은 스레드에 있으면 하트비트 TTL(15초)
산술이 성립하지 않아(감사 B-2) 전용 스레드로 분리했다. 설치된 하네스의 새 릴리스 태그를 확인하는
전용 스레드(`_release_check_loop`, docs/prps/harness-versioning.md 결정 UN2)가 하나 더 있고,
`update_check_enabled` 가 꺼지면 뜨지 않는다. 그 스레드와 `/release-check` 요청(새로고침 버튼·페이지
열기의 즉시 확인 신호)은 같은 판정기(`_ReleaseChecker`)를 쓴다 — 시도 시각 하나를 공유하므로 자동은
6시간, 수동은 최소 1분 간격이 한 곳에서 지켜진다(docs/prps/hub-release-check-on-refresh.md RR4).
이 모듈은 I/O 다(HTTP 소켓·파일·시그널) — 순수 로직은 hub_model.py·hub_server_state.py·
hub_usage.py 의 관련 함수들에 있다. 프로젝트 대시보드 경로(`_serve_project_dashboard`)는
docs/prps/dashboard-into-hub.md M2(HD5)부터 레지스트리 값(.jsonl)을 읽어 hub_parse·
hub_dashboard_render(둘 다 ★순수)로 요청 시점에 그린다 — 디스크에는 더 이상 HTML 이
없다.
개정 쟁점 R1·R3(docs/prps/hub-dashboard.md), 결정 AR4·AR5(docs/prps/audit-remediation.md) 참조.
"""

import dataclasses
import http.server
import os
import re
import signal
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path

import hub_atomic_write
import hub_collect
import hub_dashboard_render
import hub_model
import hub_notify
import hub_notify_send
import hub_parse
import hub_project
import hub_release
import hub_release_read
import hub_server_state
import hub_server_state_read
import hub_usage
import hub_usage_fetch

BIND_ADDRESS = "127.0.0.1"
# 이 둘만 hub.html 을 서빙한다 — 그 밖의 인식 경로는 프로젝트 대시보드(200)와 새 릴리스 확인 신호(204/403)뿐이고
# 나머지는 전부 404. 디렉토리를 통째로 서빙하지 않으므로 노출 표면이 "이 목록에 없으면 절대 나가지 않는다"로
# 고정된다(경로 traversal 여지가 없다).
ALLOWED_REQUEST_PATHS = ("/", "/hub.html")
# 새 릴리스 즉시 확인 신호(docs/prps/hub-release-check-on-refresh.md RR2·RR3). 헤더 이름은 안전 목록 밖 헤더라 교차 출처
# fetch 는 사전 요청(OPTIONS)을 피할 수 없고 이 서버는 OPTIONS 를 받지 않는다(do_OPTIONS 없음 → 501). 화면(hub_template.html)의
# 같은 글자 상수와 tests/run.sh T25-288 이 대조한다. 접두 `X-Dzh-` 는 템플릿의 `dzh-` 네임스페이스와 같은 계열이다.
RELEASE_CHECK_REQUEST_PATH = "/release-check"
RELEASE_CHECK_REQUEST_HEADER_NAME = "X-Dzh-Release-Check"
# 요청 문자열에서 뽑는 것은 정규식이 확정한 16자리 hex 뿐이다 — 이 문자열은 절대 경로 조립에
# 쓰이지 않고 오직 dashboard_paths_by_key 딕셔너리의 조회 키로만 쓰인다(결정 N3).
PROJECT_DASHBOARD_PATH_PATTERN = re.compile(r"^/project/([0-9a-f]{16})/dashboard\.html\Z")
# DNS 리바인딩 방어(docs/prps/hub-host-header-guard.md): 원격 페이지가 자기 도메인을 127.0.0.1 로
# 다시 풀어 이 포트의 응답을 읽어도 그 요청의 Host 는 공격자 도메인이다. `[::1]` 은 넣지 않는다 —
# BIND_ADDRESS 가 IPv4 전용이라 그 Host 로 도착하는 요청이 없다(HG3).
ALLOWED_HOST_NAMES = ("localhost", "127.0.0.1")
# 기본 포트면 클라이언트가 Host 에서 포트를 생략한다 — 이 규칙이 없으면 `server_port: 80` 설정의
# 모든 요청(http_ok 확인 포함)이 403 이 된다(HG4).
HTTP_DEFAULT_PORT = 80
# RFC 9110 OWS: 파서가 앞 공백만 벗기고 뒤 공백·탭은 남긴다. `str.strip()` 은 NBSP 등까지 벗겨
# RFC 보다 넓어지므로 쓰지 않는다(HG5).
HTTP_OPTIONAL_WHITESPACE = " \t"
SERVER_LOG_MAX_BYTES = 256 * 1024
CACHE_CONTROL_NO_STORE = "no-store"
# 허브 페이지(hub.html)를 다른 출처의 iframe 에 싣지 못하게 한다(결정 RR11, docs/prps/hub-release-check-on-refresh.md). 실린 페이지의
# 진짜 스크립트가 `/release-check` 에 헤더를 붙여 보내면 서버는 위조와 구별하지 못한다. X-Frame-Options 는 이 지시어로 대체됐다.
# 프로젝트 대시보드 응답에는 달지 않는다 — 허브 상세 패널이 같은 출처 iframe 으로 싣는다. 최상위 이동·새 창 열기는 막지 않는다(사용자 눈에 보이고 확인은 1분 상한).
HUB_PAGE_CONTENT_SECURITY_POLICY = "frame-ancestors 'self'"

# ---- 요청 구동 수집 (개정 2) ----
# 창 안이면 캐시된 결과를 그대로 서빙하고, 넘으면 락을 잡고 1회만 수집한다.
# 2000ms 인 근거: (1) 한 페이지 로드가 만드는 요청 버스트(/hub.html + 열려 있던 패널의
# /project/<key>/dashboard.html)를 한 번으로 합치기에 충분하다 (2) 사람이 인지하지 못할 만큼
# 짧다 (3) 이보다 크게 잡으면 "즉시 보고 싶으면 새로고침 버튼"이라는 hub/README.md 의
# 약속이 그 차이만큼 거짓이 된다.
SNAPSHOT_FRESHNESS_WINDOW_MS = 2000
# 요청과 무관하게 수집을 보장하는 상한. **브라우저 신선도를 위한 값이 아니다** — 브라우저는
# 자기 요청으로 위 창을 통해 신선도를 얻는다. 이 값이 존재하는 이유는 둘뿐이다:
# (1) `/hub` 를 거치지 않고 file:// 북마크로 hub.html 을 직접 여는 경로의 신선도
# (2) collect_health 가 계속 관측 가능하도록 — 아무도 페이지를 열지 않는 서버가 영구히
#     "never_collected" 를 보고하면 사용자가 정상과 고장을 구분할 수 없다.
BACKGROUND_COLLECT_MAX_AGE_MS = 5 * 60 * 1000
# 알림이 켜져 있을 때 훅 이벤트·세션 명부 파일의 변화가 보이면 신선도 창과 무관하게 수집한다(결정 MN6,
# docs/prps/hub-macos-notification.md). 0 인 이유: 창 안의 캐시는 그 변화 **이전**에 만든 것일 수 있다.
ACTIVITY_COLLECT_MAX_AGE_MS = 0

# `_run_usage_api_poll_cycle` 이 fetch 계약 밖에서 새는 예외를 잡았을 때 쓰는 실패 사유
# (결정 AR4). `hub_usage_fetch.FailureReason` Literal 에는 넣지 않는다 — 그 사유는 fetch 가
# 반환하는 것이 아니라 이 사이클이 자체적으로 집계하는 것이라서다.
USAGE_API_UNEXPECTED_ERROR_REASON = "internal_error"


def _monotonic_ms() -> int:
    """단조 시계를 밀리초 정수로 반환한다.

    호출부(`_HubRequestHandler._refresh_if_stale`·`_maintenance_loop`·`_SnapshotRefresher.
    _collect_once`)가 `time.monotonic` 을 직접 부르지 않고 이 함수 하나만 거치게 해서,
    테스트가 `mock.patch.object(hub_server, "_monotonic_ms")` 로 이 모듈에 한정해 패치할 수
    있다 — `time.monotonic` 자체를 패치하면 프로세스 전역 시계가 얼어 다른 코드의 타임아웃·
    재시도 유틸까지 함께 멈춘다(검수 Nit 13).
    """
    return int(time.monotonic() * 1000)


def _wall_clock_ms() -> int:
    """벽시계를 밀리초 정수로 반환한다 — `_ReleaseChecker` 가 락 안에서 읽는다(RR4).

    `_monotonic_ms` 와 같은 이유로 테스트가 이 모듈에 한정해 패치할 수 있게 한 곳으로 모은다. 확인 시도 시각은
    `release_check.json` 에 저장되므로 단조 시계가 아니라 벽시계다."""
    return int(time.time() * 1000)


def _truncate_log_if_oversized(log_path, max_bytes: int) -> None:
    """server.log 가 max_bytes 를 넘으면 시작 시 잘라낸다(사후 원인 규명 창구가 무한히 크지 않게)."""
    try:
        if log_path.stat().st_size <= max_bytes:
            return
        tail_bytes = log_path.read_bytes()[-max_bytes:]
        log_path.write_bytes(tail_bytes)
    except OSError:
        pass


def is_allowed_host_header(host_header_values: list[str], server_port: int) -> bool:
    """Host 헤더가 정확히 1개이고 그 값이 허용 이름:실제 포트일 때만 True(순수 — DNS 리바인딩 방어).

    문자열 전체 일치로만 판정한다 — 포트를 `int()` 로 파싱하면 `+8794`·`08794`·`8_794` 를 전부
    8794 로 받아 준다(docs/prps/hub-host-header-guard.md §6)."""
    if len(host_header_values) != 1:
        return False
    normalized_host = host_header_values[0].strip(HTTP_OPTIONAL_WHITESPACE).lower()
    allowed_hosts = {f"{name}:{server_port}" for name in ALLOWED_HOST_NAMES}
    if server_port == HTTP_DEFAULT_PORT:
        allowed_hosts.update(ALLOWED_HOST_NAMES)
    return normalized_host in allowed_hosts


class _HubRequestHandler(http.server.BaseHTTPRequestHandler):
    """허용 경로 2개는 hub.html 을, 프로젝트 대시보드 경로는 레지스트리 조회로 서빙한다.
    `/release-check` 는 전용 헤더가 있을 때만 새 릴리스 확인 신호로 받아 204 로 답하고 헤더가 없으면 403 이다(결정 RR2·RR3).
    그 외는 전부 404(결정 N3 — 요청 문자열로 경로를 조립하지 않는다). Host 가 루프백
    이름:실제 포트가 아니면 경로와 무관하게 403(docs/prps/hub-host-header-guard.md HG1)."""

    def do_GET(self) -> None:
        """Host 판정 → 경로 판정 → 신선도 게이트 → 본문 생산(docs/prps/hub-host-header-guard.md).
        게이트는 **인식된 경로에만** 건다 —
        favicon 처럼 화이트리스트 밖 요청이 수집을 유발하면 안 된다.

        인식된 경로 판정을 `if`/`return` 으로 먼저 끝내 두 분기가 각자의 `dashboard_match`
        상태(불변식)를 함께 들고 다니지 않게 한다(검수 Minor D) — 이전에는 그 불변식이
        `is_hub_path`·`dashboard_match` 두 지역 변수에 흩어져 있어 타입 검사기가 좁히지
        못했다."""
        if not is_allowed_host_header(self.headers.get_all("Host", []), self.server.server_address[1]):
            self.send_error(403)
            return
        if self.path == RELEASE_CHECK_REQUEST_PATH:    # 정확 일치. 수집 게이트를 걸지 않는다 — 강제 수집은 판정기 몫(RR2·RR5)
            self._serve_release_check_request()
            return
        if self.path in ALLOWED_REQUEST_PATHS:
            self._refresh_if_stale()
            self._serve_hub_html()
            return
        dashboard_match = PROJECT_DASHBOARD_PATH_PATTERN.match(self.path)
        if dashboard_match is None:
            self.send_error(404)
            return
        self._refresh_if_stale()
        self._serve_project_dashboard(dashboard_match.group(1))

    def _refresh_if_stale(self) -> None:
        """`snapshot_refresher` 가 실려 있으면 신선도 창을 넘겼을 때만 수집한다.

        getattr 로 받는다 — `_serve_project_dashboard` 의 `dashboard_paths_by_key` 조회가 세운
        관례와 같다. `self.server` 의 정적 타입(BaseServer)에는 이 속성이 없고, refresher 가 실리지
        않은 서버로 핸들러를 단독 구성하는 테스트에서 AttributeError → 500 이 되면
        안 된다. None 이면 게이트를 건너뛰고 디스크에 있는 것을 그대로 서빙한다."""
        refresher = getattr(self.server, "snapshot_refresher", None)
        if refresher is not None:
            refresher.collect_if_older_than(_monotonic_ms(), SNAPSHOT_FRESHNESS_WINDOW_MS)

    def _serve_release_check_request(self) -> None:
        """새로고침 버튼·페이지 열기의 즉시 확인 신호(RR2·RR3). 헤더가 없으면 403. 판정기가 있으면 확인(또는 건너뛰기)이 끝난
        뒤, 없으면(update_check_enabled:false, RR7) 바로 204 — 본문 없음·no-store. 204 에는 Content-Length 를 보내지 않는다(RFC 9110).

        getattr 로 받는다 — `_refresh_if_stale` 과 같은 관례(판정기가 실리지 않은 서버를 단독 구성하는 테스트에서 500 방지)."""
        if not self.headers.get_all(RELEASE_CHECK_REQUEST_HEADER_NAME):
            self.send_error(403)
            return
        release_checker = getattr(self.server, "release_checker", None)
        if release_checker is not None:
            release_checker.check_if_due(hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS)
        self.send_response(204)
        self.send_header("Cache-Control", CACHE_CONTROL_NO_STORE)
        self.end_headers()

    def _serve_hub_html(self) -> None:
        """hub.html 을 서빙한다 — 다른 출처가 iframe 으로 싣지 못하게 `frame-ancestors 'self'` 를 단다(결정 RR11)."""
        try:
            body = hub_collect.HUB_HTML_PATH.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self._respond_with_html(body, extra_headers={"Content-Security-Policy": HUB_PAGE_CONTENT_SECURITY_POLICY})

    def _serve_project_dashboard(self, dashboard_key: str) -> None:
        """`dashboard_key` 는 정규식이 이미 `[0-9a-f]{16}` 로 검증했다 — 딕셔너리 조회 결과만
        신뢰한다. 레지스트리 값(.jsonl 절대경로)을 읽어 parse_event_lines → render_from_events
        로 그 자리에서 그린다(HD5, docs/prps/dashboard-into-hub.md). 모르는 키·파일 부재·
        init 없음·AnchorMismatch·템플릿 읽기 실패는 전부 404 로 접고, 뒤의 둘은 진단 메시지를
        stderr(상주 서버에서는 server.log 로 리다이렉션된다)에 한 줄 남긴다(배포 결함이라
        사용자가 알아야 한다)."""
        registry: dict[str, str] = getattr(self.server, "dashboard_paths_by_key", {})
        target_path = registry.get(dashboard_key)
        if target_path is None:
            self.send_error(404)
            return
        try:
            jsonl_text = Path(target_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            self.send_error(404)
            return
        events = hub_parse.parse_event_lines(jsonl_text)
        if not events:
            self.send_error(404)
            return
        try:
            template_text = hub_collect.DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")
        except OSError as error:
            print(f"{dashboard_key}: 대시보드 템플릿 읽기 실패 ({error})", file=sys.stderr)
            self.send_error(404)
            return
        session_id = hub_project.session_id_from_dashboard_file_name(Path(target_path).name) or ""
        try:
            rendered = hub_dashboard_render.render_from_events(template_text, events, session_id)
        except hub_dashboard_render.AnchorMismatch as error:
            print(f"{dashboard_key}: 대시보드 렌더 실패 ({error})", file=sys.stderr)
            self.send_error(404)
            return
        # 대시보드는 이제 이 프로세스가 렌더한 결과다 — 원본 파일(.jsonl)의 내용이 무엇이든
        # 응답은 text/html 로만 해석되게 못 박는다(hub.html 응답에는 없는 방어선, 결정 N3).
        # 인코딩 전에 hub_atomic_write.encode_safe_utf8 로 고립 서로게이트를 U+FFFD 로
        # 치환한다(재검수 2회차 RA2) — JSONL 의 사용자 입력(title·summary 등)이 UTF-16
        # 서로게이트 쌍이 쪼개진 값을 담으면(그 함수 docstring 의 재현 입력과 동형) 원문
        # 그대로인 rendered 의 encode("utf-8") 가 UnicodeEncodeError 를 던져 매 요청마다
        # 연결이 끊긴다. hub.html 쓰기는 atomic_write_text 내부에서 같은 정규화를 이미
        # 거치지만, 이 응답 경로는 파일 쓰기가 아니라 직접 인코딩이라 그 보호를 받지 못했다.
        safe_rendered = hub_atomic_write.encode_safe_utf8(rendered)
        self._respond_with_html(safe_rendered.encode("utf-8"), extra_headers={"X-Content-Type-Options": "nosniff"})

    def _respond_with_html(self, body: bytes, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", CACHE_CONTROL_NO_STORE)
        for header_name, header_value in (extra_headers or {}).items():
            self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args) -> None:
        """요청이 상시로 들어와 server.log 를 부풀리므로 무음으로 오버라이드한다."""


def _observe_for_notification(
    notifier: hub_notify_send.SessionNotifier | None, snapshot: hub_model.HubSnapshot
) -> None:
    """수집 성공 스냅샷을 알림기에 넘긴다. notifier 가 None 이면 아무것도 안 한다.

    예외는 stderr 한 줄로 흡수한다 — `_run_collect_cycle` 의 `except Exception` 이 잡으면 알림 쪽 결함이 수집 실패
    (`record_collect_failure`)로 잘못 기록된다(결정 MN7).
    """
    if notifier is None:
        return
    try:
        notifier.observe(snapshot)
    except Exception as error:
        print(f"알림 관측 처리되지 않은 예외: {error}", file=sys.stderr)


def _run_collect_cycle(
    last_content_key: str | None,
    notifier: hub_notify_send.SessionNotifier | None = None,
) -> tuple[str | None, dict[str, str] | None]:
    """한 사이클: 수집 → (내용이 바뀌었거나 hub.html 이 없으면) 쓰기 → 실패 기록/해제.

    설계 결정 5(실패 격리)의 서버판이다 — 한 사이클의 예외가 상주 프로세스를 죽이면
    "사용자가 끄기 전까지 산다"(요구 R-1)가 조용히 깨진다.

    쓰기 게이트에 `hub.html` 실재 여부를 반드시 함께 본다(검수 M1) — content_key 만 보면
    파일이 삭제·손상돼도 내용이 그대로인 한 영구히 재생성되지 않는 "조용한 비복구 실패"가 된다.
    쓰기 자체가 실패하면(`write_hub_html` 예외) 캐시를 `None` 으로 무효화해 다음 사이클이
    반드시 다시 시도하게 한다 — 실패한 채로 `last_content_key` 가 낡은 값으로 남으면, 다음
    사이클이 "내용 동일"로 오판해 쓰기를 건너뛰고 그 상태에서 `clear_collect_failure()` 까지
    불러 실패 증거를 지워 버린다.

    `clear_collect_failure()` 는 쓰기가 일어났을 때만이 아니라 **이 사이클이 예외 없이
    끝나면(쓰기를 건너뛰었어도) 항상** 호출한다(검수 n2) — 쓰기를 건너뛰는 경우는 내용이
    같고 hub.html 도 실재할 때뿐이라 이미 "정상"이 확인된 상태다. 예전에는 쓰기 발생 사이클
    에서만 지워, 안정 상태(내용 불변 + hub.html 실재)가 오래 지속되면 그전에 다른 경로
    (예: 전경 `cmd_collect`)가 남긴 실패 기록이 영구 잔존해 `/hub status` 가 허위 경보를 냈다.

    반환값은 `(content_key, dashboard_registry)` 튜플이다(개정 쟁점 R3). 성공하면 둘 다
    채워지고(내용이 안 바뀌어 쓰기를 건너뛰었어도 레지스트리는 매 사이클 새로 만든다 — 순수
    함수라 비용이 없다), 실패하면 둘 다 `None` 이다 — 호출자(`_SnapshotRefresher`)가 `None` 을
    "직전 레지스트리를 그대로 유지하라"는 신호로 읽는다.

    성공 스탬프(`touch_collect_success_stamp`)는 `clear_collect_failure()` 와 같은 지점에서
    찍는다(개정 2) — `evaluate_collect_health` 가 보는 유일한 성공 시각 출처다.

    `notifier` 가 있으면 성공한 스냅샷을 그쪽에 넘긴다(결정 MN7 — 수집 실패 사이클은 넘기지 않는다). 반환 모양은 불변이다.
    """
    now_ms = int(time.time() * 1000)
    try:
        snapshot = hub_collect.collect_snapshot(now_ms)
        content_key = hub_model.snapshot_content_key(snapshot)
        needs_write = content_key != last_content_key or not hub_collect.HUB_HTML_PATH.exists()
        if needs_write:
            hub_collect.write_hub_html(snapshot)
        hub_collect.clear_collect_failure()
        hub_server_state_read.touch_collect_success_stamp()
        _observe_for_notification(notifier, snapshot)
        return content_key, hub_model.build_dashboard_registry(snapshot)
    except Exception as error:
        hub_collect.record_collect_failure(str(error))
        return None, None


def _apply_dashboard_registry(
    httpd: http.server.ThreadingHTTPServer, registry: dict[str, str] | None
) -> None:
    """레지스트리를 서버 인스턴스에 통째로 교체한다(결정 N3) — `None` 이면 손대지 않는다.

    수집 실패 사이클(`registry is None`)에도 직전 레지스트리를 유지해야 이미 열려 있는
    모달의 폴링이 죽지 않는다(U20).
    """
    if registry is not None:
        httpd.dashboard_paths_by_key = registry


class _SnapshotRefresher:
    """요청 구동 수집의 임계 구역(개정 2).

    왜 클래스인가: ThreadingHTTPServer 의 여러 요청 스레드가 공유하는 가변 상태(마지막 수집
    시도 시각·last_content_key)와 그것을 지키는 락이 한 덩어리로 묶여야 한다. 모듈 전역
    변수로 두면 결정 A3(전역 가변 상태 금지)를 어기므로, 기존 `dashboard_paths_by_key`
    (결정 N3)와 같은 관례로 서버 인스턴스에 실어 둔다.

    수집 경로는 이 클래스 하나다 — 요청도, 유지보수 티커도 `collect_if_older_than` 만
    부르고 창 크기만 다르게 준다. 그래서 두 경로가 동시에 수집해 `last_content_key` 를
    각자 갱신하는(쓰기 억제 판정이 깨지는) 일이 구조적으로 생길 수 없다.
    """

    def __init__(
        self, httpd: http.server.ThreadingHTTPServer, notifier: hub_notify_send.SessionNotifier | None = None
    ) -> None:
        self._httpd = httpd
        self._notifier = notifier    # 수집 락 안에서만 관측을 받는다(결정 MN7) — 별도 락이 없다
        self._lock = threading.Lock()
        self._last_attempt_at_monotonic_ms: int | None = None
        self._last_started_at_monotonic_ms: int | None = None    # 마지막 수집이 **시작**한 시각 — 강제 수집의 이중 검사가 쓴다(C2)
        self._last_content_key: str | None = None

    def collect_if_older_than(self, now_monotonic_ms: int, max_age_ms: int) -> None:
        """마지막 수집 시도가 max_age_ms 보다 오래됐으면 1회 수집한다. 예외를 올리지 않는다.

        간격은 **단조 시계**(`time.monotonic()`)로만 잰다(§0.3 정정 4) — 벽시계는 NTP 스텝·
        수동 시각 변경으로 뒤로 점프할 수 있고, 그러면 이 게이트가 그 폭만큼 전혀 발동하지
        않는다(성공 스탬프는 그대로라 `collect_health` 로도 드러나지 않는다). 성공/실패
        스탬프(파일 mtime, `collect_health` 의 입력)는 이 시계와 무관하게 벽시계 그대로
        둔다 — 두 시계의 용도가 다르다.
        """
        is_forced = max_age_ms <= 0
        if not is_forced and self._is_within(now_monotonic_ms, max_age_ms):
            return
        with self._lock:
            # 이중 검사. 진입 시점의 now_monotonic_ms 를 **그대로 다시 쓴다** — 락을 기다리는
            # 동안 다른 스레드가 수집을 마쳤다면 이 요청은 그 결과를 쓰면 된다. 스탬프가 수집
            # 완료 시점(`_collect_once` 의 `finally`)에 찍히므로 여기서 시계를 다시 읽어도
            # 결과는 같지만, 진입 시각을 재사용하는 편이 "이 요청은 자기가 본 시점 기준으로
            # 판정한다"는 뜻이 더 분명하다.
            if self._is_covered_after_lock_wait(now_monotonic_ms, max_age_ms):
                return
            try:
                self._collect_once()
            except Exception as error:
                # 최종 방어선(§0.3 정정 5) — 여기서 잡지 않으면 예외가 do_GET 까지 올라가
                # 그 요청은 응답 없이 끊긴다. _collect_once 가 finally 로 시도 시각을 이미
                # 갱신했으므로 다음 요청은 재시도를 반복하지 않는다. 다시 실패할 수 있는
                # I/O(record_collect_failure 등)는 여기서 부르지 않는다 — _maintenance_loop
                # 의 최종 방어선과 같은 형태다.
                print(f"수집 사이클에서 처리되지 않은 예외: {error}", file=sys.stderr)

    def _is_within(self, now_monotonic_ms: int, max_age_ms: int) -> bool:
        if self._last_attempt_at_monotonic_ms is None:
            return False
        return (now_monotonic_ms - self._last_attempt_at_monotonic_ms) < max_age_ms

    def _is_covered_after_lock_wait(self, entry_monotonic_ms: int, max_age_ms: int) -> bool:
        """락을 기다리는 동안 다른 스레드가 한 수집이 이 호출의 몫을 대신하는가.

        창이 있는 일반 수집은 마지막 시도가 창 안이면 대신한다(위 이중 검사). 강제 수집(max_age_ms <= 0 — 알림이 켜졌을 때 파일 변화가
        보인 경우, 결정 MN6)은 **진입 뒤에 시작한** 수집만 대신한다 — 진입 전에 시작한 수집은 그 변화보다 앞선 캐시일 수 있어, 그 수집이
        끝났다고 건너뛰면 알림이 다음 요청이나 5분 상한까지 늦어진다(검수 1회차 C2).
        """
        if max_age_ms > 0:
            return self._is_within(entry_monotonic_ms, max_age_ms)
        started_at_ms = self._last_started_at_monotonic_ms
        return started_at_ms is not None and started_at_ms > entry_monotonic_ms

    def _collect_once(self) -> None:
        """한 사이클을 돌리고 시도 시각을 갱신한다.

        시도 시각 갱신을 **`finally` 로 옮겨 예외 경로도 덮는다**(§0.3 정정 5) — 갱신이
        성공 경로에만 있으면, `_run_collect_cycle` 안에서 새는 예외(구조적으로 열려 있다 —
        `record_collect_failure` 가 OSError 를 자체 흡수해 실질 발생은 막혀 있지만 그 사실이
        코드로 강제되지는 않았다)가 `collect_if_older_than` → `do_GET` 까지 올라가 그 요청의
        연결이 끊기고, 시도 시각이 갱신되지 않아 **다음 요청도 무한히 같은 실패를 반복**한다.

        **실패해도 시각을 갱신한다.** 성공에만 스탬프를 찍으면 수집이 계속 실패하는 동안 매
        요청이 재시도를 물고 응답이 그만큼 느려진다 — `touch_spawn_stamp`
        (hub_collect.py:475-482)가 "Popen 이 실패해도 스탬프는 남긴다"로 같은 판단을 이미
        내렸다. 실패 사실은 last_collect_error.json 이 따로 보존한다.
        """
        self._last_started_at_monotonic_ms = _monotonic_ms()
        try:
            self._last_content_key, registry = _run_collect_cycle(self._last_content_key, self._notifier)
            _apply_dashboard_registry(self._httpd, registry)
        finally:
            self._last_attempt_at_monotonic_ms = _monotonic_ms()


def _write_usage_api_capture(capture: hub_usage.RateLimitCapture) -> None:
    """사용량 API 캡처를 statusLine 생산자와 같은 공존 규칙으로 쓴다(결정 A2) —
    `same_capture_values` 게이트를 거쳐야 두 생산자가 값이 같을 때 서로를 덮어쓰지 않는다.

    로컬 쓰기 실패는 여기서 흡수하고 기존 collect 실패 채널(`record_collect_failure`)에
    남긴다 — 사용량 API 백오프 스케줄(poll_state)은 원격 API 와의 상호작용 결과만 반영해야
    하므로, 로컬 디스크 문제를 그 스케줄에 섞지 않는다.
    """
    try:
        previous, _warnings = hub_collect.read_rate_limit_capture()
        if not hub_usage.same_capture_values(previous, capture):
            hub_collect.write_rate_limit_capture(capture)
    except OSError as error:
        hub_collect.record_collect_failure(str(error))


def _run_usage_api_poll_cycle(
    now_ms: int, poll_state: hub_usage.UsageApiPollState, config: hub_model.HubConfig
) -> hub_usage.UsageApiPollState:
    """사용량 API 폴링 게이트 1사이클(R1, 결정 A3 — 호출 스레드는 AR5 로 전용 분리됨).

    `show_usage_panel`·`usage_api_enabled` 이 **둘 다** 참일 때만 자격증명을 읽고 원격
    호출을 한다(GOTCHA 2) — 하나만 보면 "패널을 껐는데 계속 자격증명을 읽고 원격 호출을
    한다"는, 사용자가 가장 화낼 상황이 된다. 캡처가 오면 기존 공존 규칙으로 쓰고 실패
    기록을 지운다. 실패(`schema_mismatch` 포함)면 **기존 캡처 파일을 덮어쓰지 않고**
    (결정 A7) 사유·상세를 `last_usage_api_error.json` 에 남긴다.

    게이트를 통과하면(위 두 return 문 아래) **어떤 경로로 끝나도 시도 1회로 집계된 상태를
    반환한다**(결정 AR4 — B-1 회귀 수정). fetch 계약 밖의 예외(RecursionError 등 분류되지
    않은 예외)까지 여기서 잡아 반환값에 반영해야 한다 — 그러지 않으면 이 함수를 부르는
    쪽(`_usage_api_poll_loop`)의 지역 변수 대입이 무산되고, 다음 사이클이
    `should_attempt_usage_api_poll` 판정에 쓸 새 `last_attempt_at_ms` 를 못 받아 같은 예외를
    무한히 반복한다(감사 B-1 이 실측한 결함). **`finally` 가 아니라 내부 except + 함수 끝
    단일 return** 형태다 — 여기 상태는 가변 속성이 아니라 불변 dataclass 반환값이라
    `finally` 안의 `return` 은 예외를 삼키는 안티패턴이 되기 때문이다(GOTCHA 1).
    """
    if not (config.show_usage_panel and config.usage_api_enabled):
        return poll_state
    if not hub_usage.should_attempt_usage_api_poll(now_ms, poll_state, config.usage_api_poll_interval_seconds):
        return poll_state

    failure_reason: str | None = USAGE_API_UNEXPECTED_ERROR_REASON
    try:
        capture, fetch_failure_reason, failure_detail = hub_usage_fetch.fetch_rate_limit_capture(now_ms)
        if capture is not None:
            _write_usage_api_capture(capture)
            hub_collect.clear_usage_api_failure()
            failure_reason = None    # 부수 효과까지 끝난 뒤에만 성공으로 친다
        else:
            # fetch_rate_limit_capture 의 계약(캡처 또는 실패사유 중 정확히 하나)상 이 분기에서
            # fetch_failure_reason 은 항상 채워져 있다 — record_usage_api_failure(reason: str) 에
            # None 을 넘길 일은 없다.
            fetch_failure_message = hub_usage_fetch.failure_reason_message(fetch_failure_reason)  # N1(§8-3)
            hub_collect.record_usage_api_failure(fetch_failure_reason, failure_detail, fetch_failure_message)
            failure_reason = fetch_failure_reason
    except Exception as error:
        # 관측 가능성 복구: /hub status 의 usage_api_last_failure 가 비지 않게 한다.
        # record_usage_api_failure 는 자신은 절대 예외를 던지지 않는다(hub_collect.py 문서화).
        unexpected_error_message = hub_usage_fetch.failure_reason_message(USAGE_API_UNEXPECTED_ERROR_REASON)
        hub_collect.record_usage_api_failure(USAGE_API_UNEXPECTED_ERROR_REASON, None, unexpected_error_message)
        print(f"사용량 API 폴링 사이클에서 분류되지 않은 예외: {error}", file=sys.stderr)
    return hub_usage.next_usage_api_poll_state(now_ms, poll_state, failure_reason)


def _collect_for_notification(
    refresher: _SnapshotRefresher,
    notifier: hub_notify_send.SessionNotifier,
    activity_directories: Sequence[Path],
    last_signature: hub_notify_send.ActivitySignature | None,
) -> hub_notify_send.ActivitySignature:
    """서명 읽기(먼저) → 바뀌었으면 강제 수집 → 확인 대기 후보가 있으면 확인 수집(결정 MN3·MN6). 다음 틱의 서명을 돌려준다.

    서명을 수집보다 먼저 읽는다 — 읽은 뒤 수집 사이에 온 이벤트는 그 수집에 포함되거나 다음 틱의 서명 변화로 다시 잡힌다
    (놓침 없음). 첫 틱(직전 서명 없음)은 비교만 시작한다 — 기동 첫 수집은 배경 상한 경로가 이미 한다.
    """
    signature = hub_notify_send.read_activity_signature(activity_directories)
    if last_signature is not None and signature != last_signature:
        refresher.collect_if_older_than(_monotonic_ms(), ACTIVITY_COLLECT_MAX_AGE_MS)
    if notifier.has_pending():
        refresher.collect_if_older_than(_monotonic_ms(), hub_notify.NOTIFY_SETTLE_MS)
    return signature


def _maintenance_loop(
    config: hub_model.HubConfig,
    stop_event: threading.Event,
    refresher: _SnapshotRefresher,
    notifier: hub_notify_send.SessionNotifier | None = None,
    activity_directories: Sequence[Path] = (),
) -> None:
    """데몬 스레드 본체(개정 2, AR5 로 폴링 분리). 수집은 요청이 이끌고, 이 루프는 둘만 한다.

    (1) 하트비트 touch — 사이클 앞뒤로 두 번 찍는다(배경 수집이 파일시스템 상황에 따라
        느릴 수 있으므로, 그 앞에 한 번 찍어야 외부 관찰자가 일하는 서버를 죽었다고 오판하지
        않는다). 하트비트의 뜻은 이제 "이 티커가 살아 있다"다 — "수집이 성공했다"는
        collect_health 가 따로 답한다.
    (2) 배경 수집 상한 보장 — 요청이 이미 갱신했으면 아무것도 하지 않는다.

    알림기(`notifier`)가 있을 때만 (1)·(2) 사이에 활동 감시(`_collect_for_notification`)가 끼어든다(결정 MN6). 없으면 이 루프는
    알림 기능 이전과 한 글자도 다르게 동작하지 않는다.

    사용량 API 폴링은 더 이상 이 루프에 없다(결정 AR5 — 결정 A3 의 배치 번복) — 그 원격
    호출(최악 15초 블로킹, hub_usage_fetch.py)을 이 하트비트 티커에 태우면 TTL(15초) 산술이
    성립하지 않는다(감사 B-2)는 것이 번복 사유다. 폴링은 전용 스레드 `_usage_api_poll_loop`
    로 옮겼다.

    사이클 전체를 try/except 로 감싸는 최종 방어선은 종전과 같은 이유로 유지한다(검수 M2-1) —
    `record_collect_failure` 가 실패를 기록하려다 자기 자신도 예외를 던지는 상관 실패나
    `touch_server_heartbeat` 자체의 실패처럼 개별 단계 바깥에서 나는 예외까지 있다. 이 한
    곳이 예외로 빠져나가면 데몬 스레드가 죽고, "사용자가 끄기 전까지 산다"(요구 R-1)가
    조용히 깨진다. 여기서 잡은 예외는 다시 실패할 수 있는 I/O(record_collect_failure 등)를
    부르지 않고 stderr 에만 남긴다 — 이 print 자체가 마지막 방어선이라 더 실패할 여지를
    만들지 않는 것이 핵심이다.
    """
    last_signature: hub_notify_send.ActivitySignature | None = None
    while not stop_event.is_set():
        try:
            hub_server_state_read.touch_server_heartbeat()
            if notifier is not None:
                last_signature = _collect_for_notification(refresher, notifier, activity_directories, last_signature)
            refresher.collect_if_older_than(_monotonic_ms(), BACKGROUND_COLLECT_MAX_AGE_MS)
            hub_server_state_read.touch_server_heartbeat()
        except Exception as error:
            print(f"유지보수 티커 사이클에서 처리되지 않은 예외: {error}", file=sys.stderr)
        stop_event.wait(config.server_heartbeat_interval_seconds)


def _usage_api_poll_loop(config: hub_model.HubConfig, stop_event: threading.Event) -> None:
    """사용량 API 폴링 전용 데몬 스레드(결정 AR5 — 결정 A3 의 배치 번복).

    유지보수 티커에서 분리한 이유: 원격 호출(최악 HTTP 10 + Keychain 5초, 소켓 연산별 상한이라
    상수 상한 없음)이 하트비트와 같은 스레드에 있으면 TTL(15초) 산술이 성립하지 않는다.
    백오프 상태는 이 함수의 지역 변수로만 산다(전역 가변 상태 금지는 유지, 결정 A3).
    깨우기 주기는 유지보수 티커와 같은 `server_heartbeat_interval_seconds` 를 쓴다 — 실제
    호출 간격은 `should_attempt_usage_api_poll` 이 게이트로 따로 결정하므로 새 설정 키를
    만들지 않는다(YAGNI).
    """
    usage_api_poll_state = hub_usage.UsageApiPollState()
    while not stop_event.is_set():
        try:
            usage_api_poll_state = _run_usage_api_poll_cycle(
                int(time.time() * 1000), usage_api_poll_state, config
            )
        except Exception as error:
            # AR4 이후 이 경로는 이론상 도달하지 않지만, 스레드 사망 = 폴링 영구 정지이므로
            # _maintenance_loop 와 같은 최후선을 둔다(stderr 만, 추가 I/O 없음).
            print(f"사용량 API 폴링 루프에서 처리되지 않은 예외: {error}", file=sys.stderr)
        stop_event.wait(config.server_heartbeat_interval_seconds)


class _ReleaseChecker:
    """새 릴리스 확인의 임계 구역 — 자동(6시간, 전용 스레드)·수동(최소 1분, 요청 스레드) 두 경로가 공유한다(RR4).

    왜 클래스인가: `_SnapshotRefresher` 와 같다 — 여러 스레드가 공유하는 가변 상태(마지막 시도 시각)와 그것을 지키는 락이 한
    덩어리다. 서버 인스턴스에 싣는다(결정 N3 관례, 전역 가변 상태 금지). 시도 시각이 하나라서 수동 확인도 시도로 기록되고
    다음 자동 확인은 그때부터 6시간 뒤다(U5). 판정·확인·강제 수집이 전부 락 안이라 git 은 언제나 한 번에 하나만 돈다.
    """

    def __init__(self, refresher: _SnapshotRefresher, last_attempt_at_ms: int | None) -> None:
        self._refresher = refresher
        self._lock = threading.Lock()
        self._last_attempt_at_ms = last_attempt_at_ms

    def check_if_due(self, min_interval_ms: int) -> bool:
        """마지막 시도가 min_interval_ms 이상 지났으면 1회 확인하고 스냅샷을 강제 수집한다. 돌았으면 True. 예외를 올리지 않는다.

        시계는 **락 안에서** 읽는다 — 진입 시각을 넘기면 밀린 호출이 더 늦은 시도 시각보다 이른 now 로 판정해 「벽시계 역행」
        분기(참)를 타고 1분 안에 두 번 묻는다(RR4). 시도 시각은 사이클 **전에** 갱신한다 — 사이클 계약 밖 예외가 갱신을
        무산시키면 같은 예외가 깨어날 때마다 반복된다(AR4·감사 B-1). 확인이 돌았으면 락 안에서 스냅샷을 강제 수집해, 락을
        기다리던 호출이 건너뛰고 반환할 때 새 확인 결과가 이미 캐시에 담겨 있게 한다(RR5).
        """
        with self._lock:
            now_ms = _wall_clock_ms()
            if not hub_release.should_attempt_release_check(now_ms, self._last_attempt_at_ms, min_interval_ms):
                return False
            self._last_attempt_at_ms = now_ms
            try:
                hub_release_read.run_release_check_cycle(now_ms)
            except Exception as error:
                print(f"릴리스 확인 사이클에서 분류되지 않은 예외: {error}", file=sys.stderr)
            self._refresher.collect_if_older_than(_monotonic_ms(), ACTIVITY_COLLECT_MAX_AGE_MS)
            return True


def _build_release_checker(config: hub_model.HubConfig, refresher: _SnapshotRefresher) -> _ReleaseChecker | None:
    """update_check_enabled 가 참일 때만 판정기를 만든다(UN4·RR7 — 꺼지면 기록도 읽지 않는다). 기록의 마지막 시도 시각을
    이어받아, 서버를 자주 재시작해도 6시간·1분 간격이 지켜진다."""
    if not config.update_check_enabled:
        return None
    previous_record = hub_release_read.read_release_check_record()
    return _ReleaseChecker(refresher, previous_record.last_attempt_at_ms if previous_record else None)


def _release_check_loop(config: hub_model.HubConfig, stop_event: threading.Event, checker: _ReleaseChecker) -> None:
    """새 릴리스 태그 확인 전용 데몬 스레드(결정 UN2). 원격 호출(최악 15초 블로킹)을 하트비트 티커에 태우지
    않으려고 사용량 API 폴링(`_usage_api_poll_loop`)처럼 스레드를 따로 둔다(결정 AR5 선례).

    하트비트 주기로 깨어 판정기(`_ReleaseChecker`)만 부른다 — 실제 확인 간격은 판정기가 정하므로 새 설정 키를 만들지
    않는다(YAGNI). 기록의 마지막 시도 시각은 `_build_release_checker` 가 이어받는다. 스레드 사망 = 자동 확인 영구 정지라
    최후선은 stderr 만 남긴다(AR4·AR5 선례).
    """
    while not stop_event.is_set():
        try:
            checker.check_if_due(hub_release.RELEASE_CHECK_INTERVAL_MS)
        except Exception as error:
            print(f"릴리스 확인 루프에서 처리되지 않은 예외: {error}", file=sys.stderr)
        stop_event.wait(config.server_heartbeat_interval_seconds)


def _start_release_check_thread(
    config: hub_model.HubConfig, stop_event: threading.Event, checker: _ReleaseChecker | None
) -> threading.Thread | None:
    """판정기가 있을 때만(= update_check_enabled) 확인 스레드를 띄운다(결정 UN4 — 꺼지면 스레드 자체가 없다)."""
    if checker is None:
        return None
    release_check_thread = threading.Thread(target=_release_check_loop, args=(config, stop_event, checker), daemon=True)
    release_check_thread.start()
    return release_check_thread


def _start_notifier(config: hub_model.HubConfig, now_ms: int) -> hub_notify_send.SessionNotifier | None:
    """notify_enabled ∧ 지원 환경일 때만 알림기를 만들고 active_since_ms 를 기록한다. 아니면 None(+필요 시 한 줄 로그).

    기동 때는 직전 기록의 나머지 필드를 보존하고 active_since_ms 만 바꾼다(결정 MN11). 기록 쓰기 실패는 한 줄로 흡수한다 —
    알림기는 그대로 돈다. 작업 제목은 record_prompt_excerpt 가 켜져 있을 때만 알림에 싣는다(결정 MN9).
    """
    if not config.notify_enabled:
        return None
    if not hub_notify_send.is_notify_supported():
        print("알림 비활성: macOS 가 아니거나 /usr/bin/osascript 가 없습니다", file=sys.stderr)
        return None
    previous = hub_notify_send.read_notify_status()
    if previous is None:
        record = hub_notify.NotifyStatusRecord(now_ms, None, None, None, None)
    else:
        record = dataclasses.replace(previous, active_since_ms=now_ms)
    try:
        hub_notify_send.write_notify_status(record)
    except OSError as error:
        print(f"알림 상태 기록 쓰기 실패: {error}", file=sys.stderr)
    return hub_notify_send.SessionNotifier(include_task_title=config.record_prompt_excerpt)


def _start_background_threads(
    config: hub_model.HubConfig,
    stop_event: threading.Event,
    refresher: _SnapshotRefresher,
    notifier: hub_notify_send.SessionNotifier | None,
    release_checker: _ReleaseChecker | None,
) -> None:
    """데몬 스레드를 띄운다 — 유지보수 티커 · 사용량 API 폴링 · (켜져 있으면) 새 릴리스 확인.

    활동 감시 디렉터리는 훅 이벤트와 호스트 세션 명부뿐이다 — ~/.claude/hub/ 자체는 넣지 않는다(hub.html·notify_status.json 쓰기가
    다시 수집을 부르는 자기 유발 루프가 된다, 결정 MN6).
    """
    activity_directories = (hub_collect.EVENTS_DIR, hub_collect.SESSIONS_DIR)
    maintenance_thread = threading.Thread(
        target=_maintenance_loop, args=(config, stop_event, refresher, notifier, activity_directories), daemon=True,
    )
    maintenance_thread.start()

    usage_api_poll_thread = threading.Thread(
        target=_usage_api_poll_loop, args=(config, stop_event), daemon=True
    )
    usage_api_poll_thread.start()

    _start_release_check_thread(config, stop_event, release_checker)


def run_server(config: hub_model.HubConfig) -> int:
    """HTTP 서버(메인) + 유지보수 티커·사용량 API 폴링·새 릴리스 확인(데몬 스레드 2~3개)을 띄우고 블로킹한다.

    bind 성공 직후 server.json 을 쓰고, SIGTERM 을 받으면 상태 파일을 정리하고 종료한다.
    """
    _truncate_log_if_oversized(hub_collect.SERVER_LOG_PATH, SERVER_LOG_MAX_BYTES)

    try:
        httpd = http.server.ThreadingHTTPServer((BIND_ADDRESS, config.server_port), _HubRequestHandler)
    except OSError as error:
        print(f"포트 {config.server_port} bind 실패: {error}", file=sys.stderr)
        return 1
    httpd.dashboard_paths_by_key = {}    # 첫 수집 사이클 전까지는 프로젝트 대시보드가 전부 404
    # 알림기의 active_since_ms 가 server.json 의 started_at_ms 와 같은 시각이어야 /hub status 의 notify_active 가 성립한다.
    started_at_ms = int(time.time() * 1000)
    notifier = _start_notifier(config, started_at_ms)
    # 요청 핸들러와 유지보수 티커가 같은 refresher 를 공유한다 —
    # dashboard_paths_by_key 와 같은 관례로 서버 인스턴스에 싣는다(결정 N3).
    httpd.snapshot_refresher = _SnapshotRefresher(httpd, notifier)
    httpd.release_checker = _build_release_checker(config, httpd.snapshot_refresher)    # 요청 핸들러·확인 스레드가 공유(RR4)

    try:
        hub_server_state_read.write_server_record(
            hub_server_state.ServerRecord(
                pid=os.getpid(), port=config.server_port, started_at_ms=started_at_ms,
                # sys.argv[0] 그대로 — 정규화하지 않는다(docs/prps/hub-server-identity.md D2).
                hub_py_path=sys.argv[0],
            )
        )
    except OSError as error:
        # server.json 이 없으면 hub_daemon 이 이 프로세스를 영원히 찾을 수 없다(검수 Nit4) —
        # 기록 없는 고아 서버로 계속 도는 것보다, 사유를 남기고 즉시 종료하는 편이 안전하다.
        print(f"server.json 쓰기 실패 — 기록 없는 고아 서버를 막기 위해 종료합니다: {error}", file=sys.stderr)
        httpd.server_close()
        return 1

    stop_event = threading.Event()
    own_pid = os.getpid()

    def _handle_sigterm(_signum, _frame) -> None:
        stop_event.set()
        hub_server_state_read.clear_server_state(expected_pid=own_pid)
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _handle_sigterm)

    _start_background_threads(config, stop_event, httpd.snapshot_refresher, notifier, httpd.release_checker)

    httpd.serve_forever()
    return 0
