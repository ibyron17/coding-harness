"""hub_server.py Host 헤더 검사 테스트(docs/prps/hub-host-header-guard.md, 결정 HG1~HG7).

브라우저에 열린 원격 페이지가 DNS 리바인딩으로 이 서버의 응답을 읽는 길을 막는 검사다 —
`IsAllowedHostHeaderTest` 는 판정(§8 표)을, `HostHeaderGuardRoutingTest` 는 배선(위치·순서·코드)을
실소켓으로 고정한다.
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

import hub_collect  # noqa: E402
import hub_server  # noqa: E402

ACTUAL_PORT = 8794
HUB_HTML_SENTINEL = "HOST-GUARD-SENTINEL"
REGISTERED_DASHBOARD_KEY = "1111111111111111"
FORGED_HOST_NAME = "evil.example"


class IsAllowedHostHeaderTest(unittest.TestCase):
    """§8 경계 사례 판정표 — 순수 함수라 실소켓 없이 표로 돌린다."""

    def test_accepts_loopback_names_with_actual_port(self) -> None:
        accepted_cases = (
            ["127.0.0.1:8794"],
            ["localhost:8794"],
            ["LOCALHOST:8794"],
            ["Localhost:8794"],
            ["localhost:8794  "],
            ["localhost:8794\t"],
        )
        for host_header_values in accepted_cases:
            with self.subTest(host_header_values=host_header_values):
                is_allowed = hub_server.is_allowed_host_header(host_header_values, ACTUAL_PORT)
                self.assertTrue(is_allowed)

    def test_rejects_everything_else(self) -> None:
        rejected_cases = (
            [],
            ["localhost:8794", "localhost:8794"],
            ["localhost:8794", "evil.example"],
            ["evil.example:8794"],
            ["evil.example"],
            ["localhost"],
            ["127.0.0.1"],
            ["localhost.:8794"],
            ["localhost:9999"],
            ["localhost:08794"],
            ["localhost:+8794"],
            ["user@localhost:8794"],
            ["localhost:8794@evil.example"],
            ["localhost:8794/hub.html"],
            ["localhost :8794"],
            [""],
            ["[::1]:8794"],
            ["127.0.0.2:8794"],
            ["0.0.0.0:8794"],
            ["sub.localhost:8794"],
        )
        for host_header_values in rejected_cases:
            with self.subTest(host_header_values=host_header_values):
                is_allowed = hub_server.is_allowed_host_header(host_header_values, ACTUAL_PORT)
                self.assertFalse(is_allowed)

    def test_default_port_allows_host_without_port(self) -> None:
        default_port = hub_server.HTTP_DEFAULT_PORT
        for host_header_values in (["localhost"], ["127.0.0.1"], [f"localhost:{default_port}"]):
            with self.subTest(host_header_values=host_header_values):
                self.assertTrue(hub_server.is_allowed_host_header(host_header_values, default_port))

        self.assertFalse(hub_server.is_allowed_host_header(["localhost"], ACTUAL_PORT))


class HostHeaderGuardRoutingTest(_RunningHubServerTestCase):
    """Host 판정이 경로 판정·신선도 게이트보다 먼저 일어나는지 실소켓으로 확인한다."""

    def setUp(self) -> None:
        super().setUp()
        hub_collect.HUB_HTML_PATH.write_text(f"<html>{HUB_HTML_SENTINEL}</html>", encoding="utf-8")
        dashboard_path = self.temp_dir / "dashboard.jsonl"
        dashboard_path.write_text(_valid_dashboard_jsonl(), encoding="utf-8")
        self.httpd.dashboard_paths_by_key = {REGISTERED_DASHBOARD_KEY: str(dashboard_path)}
        self.actual_port = self.httpd.server_address[1]
        self.dashboard_path = f"/project/{REGISTERED_DASHBOARD_KEY}/dashboard.html"

    def _get_with_host_values(self, path: str, host_values: tuple[str, ...]) -> http.client.HTTPResponse:
        """Host 를 0개(누락)·1개·2개(중복)로 직접 적어 보낸다 — `request(headers=)` 는 단일 값만 만든다."""
        connection = http.client.HTTPConnection("127.0.0.1", self.actual_port, timeout=5)
        connection.putrequest("GET", path, skip_host=True)
        for host_value in host_values:
            connection.putheader("Host", host_value)
        connection.endheaders()
        response = connection.getresponse()
        response.body = response.read()
        connection.close()
        return response

    def test_loopback_hosts_are_served(self) -> None:
        loopback_hosts = (f"127.0.0.1:{self.actual_port}", f"localhost:{self.actual_port}")
        for path in ("/", "/hub.html"):
            for loopback_host in loopback_hosts:
                with self.subTest(path=path, host=loopback_host):
                    response = self._get_with_host_values(path, (loopback_host,))

                    self.assertEqual(response.status, 200)
                    self.assertIn(HUB_HTML_SENTINEL.encode(), response.body)

    def test_forged_host_is_403_on_every_path(self) -> None:
        forged_host = f"{FORGED_HOST_NAME}:{self.actual_port}"
        for path in ("/", "/hub.html", self.dashboard_path, "/favicon.ico"):
            with self.subTest(path=path):
                response = self._get_with_host_values(path, (forged_host,))

                self.assertEqual(response.status, 403)
                self.assertNotIn(HUB_HTML_SENTINEL.encode(), response.body)

    def test_missing_host_is_403(self) -> None:
        response = self._get_with_host_values("/hub.html", ())

        self.assertEqual(response.status, 403)
        self.assertNotIn(HUB_HTML_SENTINEL.encode(), response.body)

    def test_duplicate_host_is_403(self) -> None:
        valid_host = f"localhost:{self.actual_port}"

        response = self._get_with_host_values("/hub.html", (valid_host, valid_host))

        self.assertEqual(response.status, 403)
        self.assertNotIn(HUB_HTML_SENTINEL.encode(), response.body)

    def test_rejected_requests_do_not_call_the_gate(self) -> None:
        mock_refresher = mock.Mock()
        self.httpd.snapshot_refresher = mock_refresher
        valid_host = f"localhost:{self.actual_port}"
        rejected_cases = (
            ("/hub.html", (f"{FORGED_HOST_NAME}:{self.actual_port}",), 403),
            (self.dashboard_path, (f"{FORGED_HOST_NAME}:{self.actual_port}",), 403),
            ("/hub.html", (), 403),
            (self.dashboard_path, (), 403),
            ("/hub.html", (valid_host, valid_host), 403),
            (self.dashboard_path, (valid_host, valid_host), 403),
            # absolute-form 은 Host 가 정상이면 통과해 경로 화이트리스트가 404 로 거절한다(§8 마지막 행).
            (f"http://{FORGED_HOST_NAME}/hub.html", (valid_host,), 404),
        )
        for path, host_values, expected_status in rejected_cases:
            with self.subTest(path=path, host_values=host_values):
                mock_refresher.reset_mock()

                response = self._get_with_host_values(path, host_values)

                self.assertEqual(response.status, expected_status)
                mock_refresher.collect_if_older_than.assert_not_called()


if __name__ == "__main__":
    unittest.main()
