"""hub_server.py `/release-check` 라우트 테스트(docs/prps/hub-release-check-on-refresh.md, 결정 RR2·RR3·RR7).

새로고침 버튼·페이지 열기가 보내는 즉시 확인 신호의 배선(헤더 검사·정확 일치·Host 가드 순서·수집 게이트 부재·
OPTIONS/POST 거절)을 실소켓으로 고정한다. 허브 페이지 응답의 틀 삽입 차단 헤더(RR11)도 이 모듈이 맡는다. 판정기·수집기는 Mock 으로 주입해 git 을 부르지 않는다 — 판정기 자체는
test_hub_release_wiring.py 가 맡는다.
"""

import http.client
import os
import sys
import unittest
from unittest import mock

try:
    from .test_hub_server import _RunningHubServerTestCase, _valid_dashboard_jsonl
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from test_hub_server import _RunningHubServerTestCase, _valid_dashboard_jsonl  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_release  # noqa: E402
import hub_server  # noqa: E402

SIGNAL_HEADERS = {hub_server.RELEASE_CHECK_REQUEST_HEADER_NAME: "1"}
FORGED_HOST_NAME = "evil.example"
FRAME_ANCESTORS_HEADER_NAME = "Content-Security-Policy"
FRAME_ANCESTORS_HEADER_VALUE = "frame-ancestors 'self'"    # 상수를 import 하지 않는다 — 값 자체가 계약이다
DASHBOARD_KEY = "1111111111111111"


class ReleaseCheckRoutingTest(_RunningHubServerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.release_checker = mock.Mock()
        self.snapshot_refresher = mock.Mock()
        self.httpd.release_checker = self.release_checker
        self.httpd.snapshot_refresher = self.snapshot_refresher
        self.actual_port = self.httpd.server_address[1]

    def _request(self, method: str, path: str, headers: dict[str, str] | None = None) -> http.client.HTTPResponse:
        connection = http.client.HTTPConnection("127.0.0.1", self.actual_port, timeout=5)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        response.body = response.read()
        connection.close()
        return response

    def test_rs1_signal_with_header_is_204_without_body_and_asks_the_checker_with_the_manual_interval(self) -> None:
        response = self._request("GET", hub_server.RELEASE_CHECK_REQUEST_PATH, SIGNAL_HEADERS)
        self.assertEqual(response.status, 204)
        self.assertEqual(response.body, b"")
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertIsNone(response.getheader("Content-Length"))    # RFC 9110 — 204 에 금지
        self.release_checker.check_if_due.assert_called_once_with(hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS)

    def test_rs2_signal_without_header_is_403(self) -> None:
        response = self._request("GET", hub_server.RELEASE_CHECK_REQUEST_PATH)
        self.assertEqual(response.status, 403)
        self.release_checker.check_if_due.assert_not_called()

    def test_rs3_without_a_checker_the_signal_is_a_no_op_204(self) -> None:
        self.httpd.release_checker = None
        self.assertEqual(self._request("GET", hub_server.RELEASE_CHECK_REQUEST_PATH, SIGNAL_HEADERS).status, 204)
        del self.httpd.release_checker    # 판정기가 실리지 않은 서버(단독 구성) — getattr 관례
        self.assertEqual(self._request("GET", hub_server.RELEASE_CHECK_REQUEST_PATH, SIGNAL_HEADERS).status, 204)

    def test_rs4_forged_host_is_403_before_the_checker_is_asked(self) -> None:
        headers = {**SIGNAL_HEADERS, "Host": f"{FORGED_HOST_NAME}:{self.actual_port}"}
        response = self._request("GET", hub_server.RELEASE_CHECK_REQUEST_PATH, headers)
        self.assertEqual(response.status, 403)
        self.release_checker.check_if_due.assert_not_called()

    def test_rs5_query_string_or_trailing_slash_is_404(self) -> None:
        for path in (f"{hub_server.RELEASE_CHECK_REQUEST_PATH}?x=1", f"{hub_server.RELEASE_CHECK_REQUEST_PATH}/"):
            with self.subTest(path=path):
                self.assertEqual(self._request("GET", path, SIGNAL_HEADERS).status, 404)
        self.release_checker.check_if_due.assert_not_called()

    def test_rs6_the_signal_does_not_run_the_freshness_gate(self) -> None:
        """강제 수집은 확인이 실제로 돈 판정기 몫이다 — 이 경로가 `_refresh_if_stale` 을 부르면 확인 전 캐시를 다시 모은다."""
        self._request("GET", hub_server.RELEASE_CHECK_REQUEST_PATH, SIGNAL_HEADERS)
        self.snapshot_refresher.collect_if_older_than.assert_not_called()

    def test_rs7_options_and_post_are_501_and_never_allow_cross_origin(self) -> None:
        """RR3 의 서버 쪽 전제 — 교차 출처 사전 요청(OPTIONS)이 통과하지 못해 본 요청이 나가지 않는다."""
        preflight_headers = {
            "Origin": "http://evil.example", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": hub_server.RELEASE_CHECK_REQUEST_HEADER_NAME,
        }
        responses = (
            self._request("OPTIONS", hub_server.RELEASE_CHECK_REQUEST_PATH, preflight_headers),
            self._request("POST", hub_server.RELEASE_CHECK_REQUEST_PATH, SIGNAL_HEADERS),
        )
        for response in responses:
            self.assertEqual(response.status, 501)
            self.assertFalse([name for name, _ in response.getheaders() if name.lower().startswith("access-control-allow-")])
        self.release_checker.check_if_due.assert_not_called()

    def test_rs8_the_header_means_nothing_on_the_hub_html_path(self) -> None:
        response = self._request("GET", "/hub.html", SIGNAL_HEADERS)
        self.assertEqual(response.status, 200)
        self.release_checker.check_if_due.assert_not_called()


class HubPageFrameAncestorsTest(_RunningHubServerTestCase):
    """RR11 — 다른 출처의 iframe 에 허브 페이지가 실리지 않게 한다(실린 페이지 스크립트가 진짜 헤더를 붙여 신호가 통과하는 길)."""

    def setUp(self) -> None:
        super().setUp()
        dashboard_path = self.temp_dir / "dashboard.jsonl"
        dashboard_path.write_text(_valid_dashboard_jsonl(), encoding="utf-8")
        self.httpd.dashboard_paths_by_key = {DASHBOARD_KEY: str(dashboard_path)}

    def test_rs9_both_hub_page_paths_carry_the_frame_ancestors_policy(self) -> None:
        for path in ("/", "/hub.html"):
            with self.subTest(path=path):
                response = self._get(path)
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader(FRAME_ANCESTORS_HEADER_NAME), FRAME_ANCESTORS_HEADER_VALUE)

    def test_rs10_the_project_dashboard_is_left_alone_because_the_hub_panel_frames_it(self) -> None:
        response = self._get(f"/project/{DASHBOARD_KEY}/dashboard.html")
        self.assertEqual(response.status, 200)
        self.assertIsNone(response.getheader(FRAME_ANCESTORS_HEADER_NAME))


if __name__ == "__main__":
    unittest.main()
