"""hub_server.py 단위 테스트. 검수 M1 — 쓰기 게이트가 hub.html 실재를 함께 확인하는지,
쓰기 실패 시 캐시가 무효화되고 실패 기록이 지워지지 않는지 확인한다.
검수 M2 — 사이클 안의 어떤 예외도(기록 자체의 실패까지 포함) 수집 스레드를 죽이지 못하는지,
쓰기가 없어도 성공한 사이클이면 낡은 실패 기록을 지우는지 확인한다.
"""

import http.client
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402
import hub_model  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_server  # noqa: E402
import hub_server_state_read  # noqa: E402
import hub_session  # noqa: E402
import hub_usage  # noqa: E402
import hub_usage_fetch  # noqa: E402


def _minimal_snapshot(collected_at_ms: int = 1) -> hub_model.HubSnapshot:
    return hub_model.HubSnapshot(
        collected_at_ms=collected_at_ms, projects=(), unresolved_dir_names=(), warnings=()
    )


def _valid_dashboard_jsonl(title: str = "세션 대시보드") -> str:
    """서버가 요청 시점에 렌더할 수 있는 최소 진행 기록 한 줄(init 이벤트만, HD5)."""
    event = {"time_ms": 1_700_000_000_000, "kind": "init", "title": title, "phases": ["구현", "검수"], "project": "p"}
    return json.dumps(event, ensure_ascii=False) + "\n"


class _DummyHttpd:
    """`dashboard_paths_by_key` 속성만 있으면 되는 최소 더미(m1) — 실제 소켓을 bind 하는
    `ThreadingHTTPServer` 없이 `_SnapshotRefresher` 의 레지스트리 배선만 검증한다(개정 2)."""


class _FakeUrlopenResponse:
    """`_open_usage_api_request` 가 돌려주는 응답의 컨텍스트 매니저 계약만 흉내내는 최소
    더미(AR4 회귀 테스트, H10 이후 이음선 이전 — docs/prps/shell-hardening.md §5-4).

    `hub_usage_fetch.fetch_rate_limit_capture` 는
    `with _open_usage_api_request(...) as response: response.read(상한+1)` 형태로 쓰므로
    (H11) `read` 가 선택적 size 인자를 받아야 한다 — 인자가 없으면(레거시 호출부) 전체를,
    있으면 그 길이까지만 자른 bytes 를 돌려준다."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeUrlopenResponse":
        return self

    def __exit__(self, *_exc_info) -> bool:
        return False

    def read(self, size: int | None = None) -> bytes:
        return self._body if size is None else self._body[:size]


class RunCollectCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_server_state_hub_home = hub_server_state_read.HUB_HOME
        self.original_html_path = hub_collect.HUB_HTML_PATH
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"
        # 개정 2 — _run_collect_cycle 이 성공 시 touch_collect_success_stamp() 를 부른다.
        # 격리하지 않으면 개발자 실제 머신의 ~/.claude/hub/last_collect_success 를 touch 한다.
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_server_state_read.HUB_HOME = self.original_server_state_hub_home
        hub_collect.HUB_HTML_PATH = self.original_html_path
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_deleted_hub_html_is_regenerated_even_when_content_unchanged(self) -> None:
        """검수 M1(1) — hub.html 이 삭제/손상돼도 내용이 그대로면 다음 사이클에 재생성돼야 한다.
        content_key 만으로 쓰기를 게이트하면 이 경우 영구히 재생성되지 않는다."""
        snapshot = _minimal_snapshot()
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            last_key, _ = hub_server._run_collect_cycle(None)
        self.assertTrue(hub_collect.HUB_HTML_PATH.exists())

        hub_collect.HUB_HTML_PATH.unlink()  # 외부에서 삭제/손상된 상황을 흉내낸다
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            next_key, _ = hub_server._run_collect_cycle(last_key)  # 캐시 키 기준으로는 "내용 불변"

        self.assertEqual(last_key, next_key)
        self.assertTrue(hub_collect.HUB_HTML_PATH.exists(), "hub.html 이 재생성되지 않음")

    def test_write_failure_invalidates_cache_and_keeps_failure_recorded(self) -> None:
        """검수 M1(2) — 쓰기 실패 시 다음 사이클이 반드시 재시도하고, 그 사이 실패 기록이
        지워지지 않는다(옛 캐시 키가 남으면 다음 사이클이 쓰기를 건너뛰고 실패 증거까지
        clear_collect_failure() 로 지워 버리는 것이 원래 결함이었다)."""
        snapshot = _minimal_snapshot()
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot), \
             mock.patch.object(hub_collect, "write_hub_html", side_effect=OSError("disk full")):
            first_key, _ = hub_server._run_collect_cycle(None)

        self.assertIsNone(first_key)  # 캐시 무효화 — 다음 사이클이 무조건 다시 쓰기를 시도한다
        recorded = hub_collect.read_last_collect_failure()
        self.assertIsNotNone(recorded)
        self.assertIn("disk full", recorded["reason"])

        # 다음 사이클: 쓰기가 이번엔 성공한다.
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            second_key, _ = hub_server._run_collect_cycle(first_key)

        self.assertIsNotNone(second_key)
        self.assertTrue(hub_collect.HUB_HTML_PATH.exists())
        self.assertIsNone(hub_collect.read_last_collect_failure())  # 성공 후에만 실패 기록 해제

    def test_no_write_needed_still_clears_stale_failure_record(self) -> None:
        """검수 n2 — 쓰기가 필요 없는(내용 불변 + hub.html 실재) 사이클도 성공했다면 이전
        실패 기록을 지운다. 예전에는 clear_collect_failure() 가 쓰기 발생 사이클에서만 불려,
        안정 상태가 오래 지속되면 다른 경로(예: 전경 cmd_collect)가 남긴 낡은 실패 기록이
        `/hub status` 에 영구히 허위 경보로 남았다."""
        snapshot = _minimal_snapshot()
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            last_key, _ = hub_server._run_collect_cycle(None)

        hub_collect.record_collect_failure("다른 경로가 남긴 낡은 실패")
        self.assertIsNotNone(hub_collect.read_last_collect_failure())

        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            next_key, _ = hub_server._run_collect_cycle(last_key)  # 내용 불변 + hub.html 실재 → 쓰기 스킵

        self.assertEqual(last_key, next_key)
        self.assertIsNone(hub_collect.read_last_collect_failure())


class RunCollectCycleRegistryTest(unittest.TestCase):
    """U19~U20 — _run_collect_cycle 이 (content_key, registry) 튜플을 돌려주고,
    실패 사이클은 (None, None) 이라 호출자가 직전 레지스트리를 그대로 유지할 수 있다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_server_state_hub_home = hub_server_state_read.HUB_HOME
        self.original_html_path = hub_collect.HUB_HTML_PATH
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"
        # 개정 2 — _run_collect_cycle 이 성공 시 touch_collect_success_stamp() 를 부른다.
        # 격리하지 않으면 개발자 실제 머신의 ~/.claude/hub/last_collect_success 를 touch 한다.
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_server_state_read.HUB_HOME = self.original_server_state_hub_home
        hub_collect.HUB_HTML_PATH = self.original_html_path
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_u19_successful_cycle_returns_content_key_and_registry(self) -> None:
        snapshot = _minimal_snapshot()
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            content_key, registry = hub_server._run_collect_cycle(None)
        self.assertIsNotNone(content_key)
        self.assertEqual(registry, {})

    def test_u20_failed_cycle_returns_none_none(self) -> None:
        with mock.patch.object(hub_collect, "collect_snapshot", side_effect=RuntimeError("collect 실패")):
            content_key, registry = hub_server._run_collect_cycle(None)
        self.assertIsNone(content_key)
        self.assertIsNone(registry)


class ProjectDashboardPathPatternTest(unittest.TestCase):
    """U14~U15 — 대시보드 경로 정규식이 정상 키만 매치하고 traversal·변형 시도는 전부 불매치."""

    def test_u14_valid_key_matches_and_captures_group(self) -> None:
        match = hub_server.PROJECT_DASHBOARD_PATH_PATTERN.match(
            "/project/3f9a1b2c3d4e5f60/dashboard.html"
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "3f9a1b2c3d4e5f60")

    def test_u15_traversal_and_malformed_paths_do_not_match(self) -> None:
        malformed_paths = (
            "/project/../../etc/passwd",
            "/project/%2e%2e/dashboard.html",
            "/project/ABCDEF0123456789/dashboard.html",   # 대문자
            "/project/3f9a/dashboard.html",                # 짧음
            "/project/3f9a1b2c3d4e5f60/index.html",
        )
        for path in malformed_paths:
            with self.subTest(path=path):
                self.assertIsNone(hub_server.PROJECT_DASHBOARD_PATH_PATTERN.match(path))


class _RunningHubServerTestCase(unittest.TestCase):
    """실제 소켓에 bind 한 서버로 라우팅을 검증하기 위한 공통 준비(U16~U18)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_html_path = hub_collect.HUB_HTML_PATH
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"
        hub_collect.HUB_HTML_PATH.write_text("<html>hub</html>", encoding="utf-8")

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), hub_server._HubRequestHandler)
        self.httpd.dashboard_paths_by_key = {}
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.server_thread.join(timeout=2)
        hub_collect.HUB_HTML_PATH = self.original_html_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get(self, path: str) -> http.client.HTTPResponse:
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.httpd.server_address[1], timeout=5
        )
        connection.request("GET", path)
        response = connection.getresponse()
        response.body = response.read()  # 렌더 본문을 확인해야 하는 테스트를 위한 편의 속성
        connection.close()
        return response


class ProjectDashboardRoutingTest(_RunningHubServerTestCase):
    """U16~U18 — 레지스트리 조회 실패·TOCTOU·기존 화이트리스트 유지를 실제 서버로 확인한다."""

    def test_u16_well_formed_but_unregistered_key_is_404(self) -> None:
        self.assertEqual(self._get("/project/0000000000000000/dashboard.html").status, 404)

    def test_u17_registered_key_with_deleted_file_is_404(self) -> None:
        dashboard_path = self.temp_dir / "dashboard.html"
        dashboard_path.write_text("<html>dashboard</html>", encoding="utf-8")
        self.httpd.dashboard_paths_by_key = {"1111111111111111": str(dashboard_path)}
        dashboard_path.unlink()  # 수집 이후 삭제된 상황(TOCTOU)을 흉내낸다
        self.assertEqual(self._get("/project/1111111111111111/dashboard.html").status, 404)

    def test_u18_internal_files_stay_404_through_new_route(self) -> None:
        """S5 — 라우트가 하나 늘어도 bin/*.py·events/*.jsonl·config.json 은 어떤 경로로도 200 이 아니다."""
        blocked_paths = ("/bin/hub_server.py", "/events/x.jsonl", "/config.json")
        for blocked_path in blocked_paths:
            with self.subTest(path=blocked_path):
                self.assertEqual(self._get(blocked_path).status, 404)

    def test_registered_key_serves_dashboard_with_nosniff_header(self) -> None:
        """HD5(docs/prps/dashboard-into-hub.md) — 서버가 .jsonl 을 요청 시점에 렌더한다.
        본문에 init 이벤트의 제목 원문이 그대로 실린다(dz-title)."""
        dashboard_path = self.temp_dir / "dashboard.jsonl"
        dashboard_path.write_text(_valid_dashboard_jsonl("제목"), encoding="utf-8")
        self.httpd.dashboard_paths_by_key = {"2222222222222222": str(dashboard_path)}

        response = self._get("/project/2222222222222222/dashboard.html")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        self.assertIn('<h1 id="dz-title">제목</h1>', response.body.decode("utf-8"))

    def test_lone_surrogate_in_title_is_replaced_and_serves_200(self) -> None:
        """RA2(재검수 2회차) — JSONL 의 title 이 UTF-16 서로게이트 쌍이 쪼개진 값(hub_atomic_
        write.encode_safe_utf8 문서화 재현과 동형)을 담아도 응답 인코딩이 UnicodeEncodeError
        로 끊기지 않고, U+FFFD 로 치환된 본문을 200 으로 서빙한다. `\\ud83d` 는 파일에 쓰는
        JSON 유니코드 이스케이프(리터럴 텍스트, 아직 실제 서로게이트 문자가 아니다) —
        json.loads 가 이를 읽어야 인코딩 불가능한 실제 서로게이트 문자가 된다."""
        dashboard_path = self.temp_dir / "dashboard.jsonl"
        raw_line = (
            '{"time_ms": 1700000000000, "kind": "init", "title": "a\\ud83db", '
            '"phases": ["구현", "검수"], "project": "p"}\n'
        )
        dashboard_path.write_text(raw_line, encoding="utf-8")
        self.httpd.dashboard_paths_by_key = {"5555555555555555": str(dashboard_path)}

        response = self._get("/project/5555555555555555/dashboard.html")

        self.assertEqual(response.status, 200)
        self.assertIn('<h1 id="dz-title">a�b</h1>', response.body.decode("utf-8"))

    def test_registered_key_with_no_init_event_is_404(self) -> None:
        """init 없음 — 이벤트가 있어도 첫 줄이 init 이 아니면 렌더할 스냅샷이 없다."""
        dashboard_path = self.temp_dir / "dashboard.jsonl"
        dashboard_path.write_text(
            json.dumps({"time_ms": 1_700_000_000_000, "kind": "impl", "summary": "init 없음", "detail": ""}) + "\n",
            encoding="utf-8",
        )
        self.httpd.dashboard_paths_by_key = {"4444444444444444": str(dashboard_path)}

        response = self._get("/project/4444444444444444/dashboard.html")

        self.assertEqual(response.status, 404)

    def test_missing_template_is_404_and_writes_a_diagnostic_line(self) -> None:
        """템플릿 부재 — 404 로 접되, 배포 결함이라는 사실이 진단 출력(server.log 로
        리다이렉션되는 stderr)에 한 줄 남는다."""
        dashboard_path = self.temp_dir / "dashboard.jsonl"
        dashboard_path.write_text(_valid_dashboard_jsonl(), encoding="utf-8")
        self.httpd.dashboard_paths_by_key = {"3333333333333333": str(dashboard_path)}
        captured_stderr = io.StringIO()

        with mock.patch.object(hub_collect, "DASHBOARD_TEMPLATE_PATH", self.temp_dir / "missing_template.html"):
            with mock.patch("sys.stderr", captured_stderr):
                response = self._get("/project/3333333333333333/dashboard.html")

        self.assertEqual(response.status, 404)
        self.assertNotEqual(captured_stderr.getvalue(), "")

    def test_p14_session_keyed_registry_entry_serves_dashboard_with_nosniff_header(self) -> None:
        """P14(hub-session-tree-and-per-session-dashboards.md, S5) — 세션 대시보드도 같은
        라우트·정규식·핸들러로 서빙된다(회귀: hub_server.py 정규식·핸들러는 무수정, 결정 ST13).
        레지스트리는 손으로 조립하지 않고 build_dashboard_registry 가 실제로 만든 것을 그대로
        쓴다 — build_dashboard_registry 의 세션 등록 경로가 빠지면 이 테스트도 함께 실패한다
        (§14.3 뮤테이션 검증)."""
        session_id = "f733cfcd-32eb-4339-9d99-e7375887e376"
        session_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=1, source_path=str(self.temp_dir), session_id=session_id,
        )
        session_dashboard_path = Path(hub_project.tier1_file_path(session_tier1))
        session_dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        session_dashboard_path.write_text(_valid_dashboard_jsonl("세션 대시보드"), encoding="utf-8")
        session = hub_session.SessionView(
            session_id=session_id, short_id=session_id[:8], started_at_ms=1,
            state="working", base_state="working", last_event_at_ms=1, task_excerpt=None,
            agent_runs=(), tier1=session_tier1,
            dashboard_key=hub_project.dashboard_file_key(str(session_dashboard_path)),
        )
        project = hub_project.ProjectView(
            display_name="repo", path=str(self.temp_dir), tier=2, state="working",
            last_activity_at_ms=1, sessions=(session,), tier1=None, note=None,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=1, projects=(project,), unresolved_dir_names=(), warnings=(),
        )
        self.httpd.dashboard_paths_by_key = hub_model.build_dashboard_registry(snapshot)

        response = self._get(f"/project/{session.dashboard_key}/dashboard.html")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")


class SnapshotRefresherTest(unittest.TestCase):
    """개정 2 — `_SnapshotRefresher` 의 신선도 창·락 이중 검사·버스트 합치기(이 기능의 핵심)."""

    WINDOW_MS = 2000

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_server_state_hub_home = hub_server_state_read.HUB_HOME
        self.original_html_path = hub_collect.HUB_HTML_PATH
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_server_state_read.HUB_HOME = self.original_server_state_hub_home
        hub_collect.HUB_HTML_PATH = self.original_html_path
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _collect_at(self, refresher: hub_server._SnapshotRefresher, now_ms: int, window_ms: int) -> None:
        """`_collect_once` 내부의 시각 스탬프도 `now_ms` 에 맞춰 고정한다 — 그러지 않으면
        내부 스탬프가 실제 단조 시계 값으로 찍혀 이후 판정이 테스트가 준 합성 시각과
        어긋난다(§0.3 정정 4 — 간격 측정이 단조 시계로 바뀌었다)."""
        with mock.patch.object(hub_server, "_monotonic_ms", return_value=now_ms):
            refresher.collect_if_older_than(now_ms, window_ms)

    def test_repeated_call_within_window_collects_once(self) -> None:
        snapshot = _minimal_snapshot()
        refresher = hub_server._SnapshotRefresher(_DummyHttpd())
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot) as mocked_collect:
            self._collect_at(refresher, 1_000_000, self.WINDOW_MS)
            self._collect_at(refresher, 1_000_500, self.WINDOW_MS)  # 창 안(500ms 뒤)
        mocked_collect.assert_called_once()

    def test_repeated_call_outside_window_collects_each_time(self) -> None:
        snapshot = _minimal_snapshot()
        refresher = hub_server._SnapshotRefresher(_DummyHttpd())
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot) as mocked_collect:
            self._collect_at(refresher, 1_000_000, self.WINDOW_MS)
            self._collect_at(refresher, 1_000_000 + self.WINDOW_MS + 1, self.WINDOW_MS)  # 창 밖
        self.assertEqual(mocked_collect.call_count, 2)

    def test_first_call_always_collects(self) -> None:
        """`_last_attempt_at_ms` 가 `None` 인 최초 호출은 창 크기와 무관하게 반드시 수집한다."""
        snapshot = _minimal_snapshot()
        refresher = hub_server._SnapshotRefresher(_DummyHttpd())
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot) as mocked_collect:
            self._collect_at(refresher, 1_000_000, self.WINDOW_MS)
        mocked_collect.assert_called_once()

    def test_concurrent_burst_within_window_collects_once(self) -> None:
        """버스트 합치기 — 락 이중 검사가 동시 진입 N개를 수집 1회로 합친다.
        `start_barrier` 로 N 스레드의 진입 시점을 맞춰 실제 경합을 만들고, `collect_snapshot`
        을 일부러 느리게(50ms) 만들어 락이 없었다면 그 창에 다른 스레드가 끼어들 수 있게 한다.

        `hub_server._monotonic_ms` 를 스레드 시작 **전에 한 번만** 고정 값(1_000_000ms)으로 패치해
        진입 시각과 `_collect_once` 내부 스탬프가 같은 시계를 쓰게 한다(§0.3 Minor 2) —
        그러지 않으면 스탬프가 실제 단조 시계 값으로 찍혀, 이후 재진입 판정이 "버스트가
        합쳐졌다"가 아니라 "합성 시각이 실제 시계보다 작아 나이가 음수로 접혔다"는 무관한
        이유로 통과할 수 있다(회귀를 가르지 못하는 검사가 된다)."""
        snapshot = _minimal_snapshot()
        refresher = hub_server._SnapshotRefresher(_DummyHttpd())
        thread_count = 8
        start_barrier = threading.Barrier(thread_count)
        call_count = {"n": 0}
        call_count_lock = threading.Lock()

        def slow_collect_snapshot(now_ms):
            with call_count_lock:
                call_count["n"] += 1
            time.sleep(0.05)
            return snapshot

        def call_refresher() -> None:
            start_barrier.wait(timeout=5)
            refresher.collect_if_older_than(1_000_000, self.WINDOW_MS)

        with mock.patch.object(hub_collect, "collect_snapshot", side_effect=slow_collect_snapshot), \
             mock.patch.object(hub_server, "_monotonic_ms", return_value=1_000_000):
            threads = [threading.Thread(target=call_refresher) for _ in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertEqual(call_count["n"], 1)

    def test_failed_collect_still_updates_attempt_time_and_skips_retry_within_window(self) -> None:
        """실패해도 시도 시각을 갱신한다(§2.10 `_collect_once` docstring) — 창 안 재호출은
        재시도하지 않는다."""
        refresher = hub_server._SnapshotRefresher(_DummyHttpd())
        with mock.patch.object(
            hub_collect, "collect_snapshot", side_effect=RuntimeError("collect 실패")
        ) as mocked_collect:
            self._collect_at(refresher, 1_000_000, self.WINDOW_MS)
            self._collect_at(refresher, 1_000_500, self.WINDOW_MS)  # 창 안
        mocked_collect.assert_called_once()

    def test_exception_from_collect_cycle_does_not_propagate_and_still_stamps_attempt(self) -> None:
        """§0.3 정정 5 — `_run_collect_cycle` 자체가 새는 예외(구조적으로 열려 있다 —
        `record_collect_failure` 가 OSError 를 자체 흡수해 실질 발생은 막혀 있지만 코드로
        강제되지는 않았다)를 흉내낸다. 검증할 두 성질: (1) `collect_if_older_than` 이 그
        예외를 밖으로 올리지 않는다(그러지 않으면 `do_GET` 까지 올라가 응답 없이 끊긴다).
        (2) 예외가 나도 시도 시각이 `finally` 로 갱신돼, 창 안 재호출이 재시도를 반복하지
        않는다(그러지 않으면 다음 요청도 무한히 같은 실패를 반복한다)."""
        refresher = hub_server._SnapshotRefresher(_DummyHttpd())
        with mock.patch.object(
            hub_server, "_run_collect_cycle", side_effect=RuntimeError("구조적으로 열린 예외")
        ) as mocked_cycle:
            try:
                refresher.collect_if_older_than(1_000_000, self.WINDOW_MS)
            except Exception as error:  # pragma: no cover - 실패하면 테스트가 바로 알려준다
                self.fail(f"collect_if_older_than 이 예외를 밖으로 던졌다: {error}")
            refresher.collect_if_older_than(1_000_500, self.WINDOW_MS)  # 창 안 재호출
        mocked_cycle.assert_called_once()  # 재시도하지 않았다 — 시도 시각이 예외 경로에서도 갱신됐다

    def test_successful_cycle_fills_dashboard_paths_by_key(self) -> None:
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=1, source_path="/repo",
        )
        tier1_project = hub_project.ProjectView(
            display_name="repo", path="/repo", tier=1, state="idle",
            last_activity_at_ms=1, sessions=(), tier1=tier1, note=None,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=1, projects=(tier1_project,), unresolved_dir_names=(), warnings=(),
        )
        httpd = _DummyHttpd()
        refresher = hub_server._SnapshotRefresher(httpd)
        with mock.patch.object(hub_collect, "collect_snapshot", return_value=snapshot):
            self._collect_at(refresher, 1_000_000, self.WINDOW_MS)
        expected_key = hub_project.project_dashboard_key("/repo")
        self.assertIn(expected_key, httpd.dashboard_paths_by_key)

    def test_failed_cycle_keeps_previous_registry(self) -> None:
        httpd = _DummyHttpd()
        httpd.dashboard_paths_by_key = {"deadbeefdeadbeef": "/old/.claude/dashboard.html"}
        refresher = hub_server._SnapshotRefresher(httpd)
        with mock.patch.object(hub_collect, "collect_snapshot", side_effect=RuntimeError("collect 실패")):
            self._collect_at(refresher, 1_000_000, self.WINDOW_MS)
        self.assertEqual(httpd.dashboard_paths_by_key, {"deadbeefdeadbeef": "/old/.claude/dashboard.html"})


class RequestFreshnessGateTest(_RunningHubServerTestCase):
    """개정 2, §2.10 `do_GET` — 게이트는 인식된 경로에만 걸리고, 본문 생산보다 먼저 호출된다."""

    def test_recognized_paths_call_the_gate(self) -> None:
        mock_refresher = mock.Mock()
        self.httpd.snapshot_refresher = mock_refresher
        recognized_paths = ("/", "/hub.html", "/project/1111111111111111/dashboard.html")
        for path in recognized_paths:
            with self.subTest(path=path):
                mock_refresher.reset_mock()
                self._get(path)
                mock_refresher.collect_if_older_than.assert_called_once()

    def test_unrecognized_path_does_not_call_the_gate(self) -> None:
        """favicon 처럼 화이트리스트 밖 요청이 수집을 유발하면 안 된다(404 경로 비용 0)."""
        mock_refresher = mock.Mock()
        self.httpd.snapshot_refresher = mock_refresher
        response = self._get("/favicon.ico")
        self.assertEqual(response.status, 404)
        mock_refresher.collect_if_older_than.assert_not_called()

    def test_gate_runs_before_body_is_served(self) -> None:
        """게이트가 본문 생산 전에 호출된다 — 첫 요청이 hub.html 을 만들어 404 창을 닫는다."""
        hub_collect.HUB_HTML_PATH.unlink()  # setUp 이 미리 써 둔 파일을 없앤 상태에서 시작한다

        def _write_hub_html_as_side_effect(now_ms, max_age_ms) -> None:
            hub_collect.HUB_HTML_PATH.write_text("<html>fresh</html>", encoding="utf-8")

        mock_refresher = mock.Mock()
        mock_refresher.collect_if_older_than.side_effect = _write_hub_html_as_side_effect
        self.httpd.snapshot_refresher = mock_refresher

        response = self._get("/hub.html")
        self.assertEqual(response.status, 200)


class MaintenanceLoopResilienceTest(unittest.TestCase):
    """검수 M2-1, 개정 2 — 사이클 전체를 감싸는 try/except 가 최종 방어선인지 확인한다.
    대상이 `_collect_loop` 에서 `_maintenance_loop` 로 바뀌었다 — 상관 실패 재현은
    `refresher.collect_if_older_than` 이 예외를 던지게 해서 유지한다(최종 방어선의 요구는
    그대로다)."""

    def test_refresher_raising_does_not_kill_the_loop(self) -> None:
        stop_event = threading.Event()
        attempt_count = {"n": 0}

        class _RaisingRefresher:
            def collect_if_older_than(self, now_ms: int, max_age_ms: int) -> None:
                attempt_count["n"] += 1
                if attempt_count["n"] >= 2:
                    stop_event.set()
                raise RuntimeError("배경 수집 상한 보장 중 예외가 났다고 흉내낸다")

        config = hub_model.HubConfig(server_heartbeat_interval_seconds=0)
        with mock.patch.object(hub_server_state_read, "touch_server_heartbeat"):
            hub_server._maintenance_loop(config, stop_event, _RaisingRefresher())  # 예외 없이 정상 반환해야 한다

        self.assertGreaterEqual(attempt_count["n"], 2)


class MaintenanceLoopTest(unittest.TestCase):
    """개정 2, AR5 로 폴링 분리 — `_maintenance_loop` 는 하트비트 touch·배경 수집 상한 보장만
    한다(수집 자체는 `refresher` 에 위임하고, 사용량 API 폴링은 `_usage_api_poll_loop` 로
    옮겨졌다 — 아래 `UsageApiPollLoopTest` 참조)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_usage_api_error_path = hub_collect.LAST_USAGE_API_ERROR_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.temp_dir / "last_usage_api_error.json"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.original_usage_api_error_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_one_cycle(self, config: hub_model.HubConfig, refresher) -> int:
        """`stop_event` 를 하트비트 touch 2회째에 세워 정확히 한 바퀴만 돈다."""
        stop_event = threading.Event()
        heartbeat_call_count = {"n": 0}

        def fake_touch_heartbeat() -> None:
            heartbeat_call_count["n"] += 1
            if heartbeat_call_count["n"] >= 2:
                stop_event.set()

        with mock.patch.object(hub_server_state_read, "touch_server_heartbeat", side_effect=fake_touch_heartbeat):
            hub_server._maintenance_loop(config, stop_event, refresher)
        return heartbeat_call_count["n"]

    def test_heartbeat_touched_before_and_after_cycle(self) -> None:
        config = hub_model.HubConfig(server_heartbeat_interval_seconds=0)
        heartbeat_call_count = self._run_one_cycle(config, mock.Mock())
        self.assertGreaterEqual(heartbeat_call_count, 2)

    def test_collect_if_older_than_uses_background_max_age(self) -> None:
        config = hub_model.HubConfig(server_heartbeat_interval_seconds=0)
        refresher = mock.Mock()
        self._run_one_cycle(config, refresher)
        refresher.collect_if_older_than.assert_called_once()
        called_args = refresher.collect_if_older_than.call_args.args
        self.assertEqual(called_args[1], hub_server.BACKGROUND_COLLECT_MAX_AGE_MS)

    def test_maintenance_loop_no_longer_polls_usage_api(self) -> None:
        """AR5 회귀 — 폴링이 전용 스레드(`_usage_api_poll_loop`)로 이동했으므로 유지보수
        루프는 더 이상 `hub_usage_fetch` 를 참조하지 않는다. 파이썬 유닛 테스트판 T25-122 ①
        이다(셸 쪽은 tests/run.sh 가 sed 앵커로 같은 성질을 고정한다) — 아래
        `UsageApiPollLoopTest` 가 반대쪽(② 신설 스레드에만 폴링이 있다)을 확인한다."""
        config = hub_model.HubConfig(
            server_heartbeat_interval_seconds=0, show_usage_panel=True, usage_api_enabled=True
        )
        with mock.patch.object(hub_usage_fetch, "fetch_rate_limit_capture") as mocked_fetch:
            mocked_fetch.return_value = (None, "network_error", None)
            self._run_one_cycle(config, mock.Mock())
        mocked_fetch.assert_not_called()


class UsageApiPollLoopTest(unittest.TestCase):
    """AR5 — 사용량 API 폴링은 전용 데몬 스레드 `_usage_api_poll_loop` 에만 있다(T25-122 ②
    의 파이썬 유닛 테스트판)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_usage_api_error_path = hub_collect.LAST_USAGE_API_ERROR_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.temp_dir / "last_usage_api_error.json"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.original_usage_api_error_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    _MAX_LOOP_ITERATIONS = 5

    def _run_one_cycle(self, config: hub_model.HubConfig) -> None:
        """`stop_event` 를 `_run_usage_api_poll_cycle` 1회 호출 뒤 세워 정확히 한 바퀴만 돈다.

        검수 MINOR 1 — 종료를 오직 그 호출의 side effect 에만 걸면, 이 테스트가 잡으려는
        바로 그 회귀(폴링 호출이 루프에서 사라짐)가 나면 `stop_event` 가 영원히 set 되지
        않아 스위트가 실패가 아니라 hang 으로 멈춘다. `_maintenance_loop` 쪽 테스트가
        무조건 호출(하트비트 touch)에 종료를 거는 것과 같은 이유로, 여기서도 매 반복
        무조건 호출되는 `stop_event.wait` 에 반복 횟수 상한을 함께 걸어 회귀가 fail 로
        나오게 한다."""
        stop_event = threading.Event()
        original_cycle = hub_server._run_usage_api_poll_cycle
        original_wait = stop_event.wait
        wait_call_count = {"n": 0}

        def _one_shot_cycle(now_ms, poll_state, cfg):
            stop_event.set()
            return original_cycle(now_ms, poll_state, cfg)

        def _bounded_wait(timeout=None):
            wait_call_count["n"] += 1
            if wait_call_count["n"] >= self._MAX_LOOP_ITERATIONS:
                stop_event.set()
            return original_wait(timeout)

        with mock.patch.object(hub_server, "_run_usage_api_poll_cycle", side_effect=_one_shot_cycle), \
             mock.patch.object(stop_event, "wait", side_effect=_bounded_wait):
            hub_server._usage_api_poll_loop(config, stop_event)

    def test_usage_api_poll_loop_calls_fetch(self) -> None:
        config = hub_model.HubConfig(
            server_heartbeat_interval_seconds=0, show_usage_panel=True, usage_api_enabled=True
        )
        with mock.patch.object(hub_usage_fetch, "fetch_rate_limit_capture") as mocked_fetch:
            mocked_fetch.return_value = (None, "network_error", None)
            self._run_one_cycle(config)
        mocked_fetch.assert_called_once()


class RunUsageApiPollCycleTest(unittest.TestCase):
    """GOTCHA 2 회귀 — show_usage_panel·usage_api_enabled 가 둘 다 참일 때만 자격증명을
    읽고 원격 호출을 한다. 캡처 성공/실패에 따른 파일 부수효과도 함께 확인한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_usage_api_error_path = hub_collect.LAST_USAGE_API_ERROR_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.temp_dir / "last_usage_api_error.json"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.original_usage_api_error_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _capture(self, session_percent=23, weekly_percent=41) -> hub_usage.RateLimitCapture:
        return hub_usage.RateLimitCapture(
            captured_at_ms=1, session_resets_at_ms=None, weekly_resets_at_ms=None,
            session_used_percent=session_percent, weekly_used_percent=weekly_percent,
        )

    def test_disabled_switch_never_calls_fetch(self) -> None:
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=False)
        with mock.patch.object(hub_usage_fetch, "fetch_rate_limit_capture") as mocked_fetch:
            result = hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        mocked_fetch.assert_not_called()
        self.assertEqual(result, hub_usage.UsageApiPollState())

    def test_usage_panel_off_blocks_fetch_even_if_api_enabled(self) -> None:
        """GOTCHA 2 의 핵심 — usage_api_enabled 만 보면 안 된다."""
        config = hub_model.HubConfig(show_usage_panel=False, usage_api_enabled=True)
        with mock.patch.object(hub_usage_fetch, "fetch_rate_limit_capture") as mocked_fetch:
            hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        mocked_fetch.assert_not_called()

    def test_successful_fetch_writes_capture_and_clears_failure(self) -> None:
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=True)
        capture = self._capture()
        hub_collect.record_usage_api_failure("network_error")
        with mock.patch.object(hub_usage_fetch, "fetch_rate_limit_capture", return_value=(capture, None, None)):
            next_state = hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        written, _warnings = hub_collect.read_rate_limit_capture()
        self.assertEqual(written, capture)
        self.assertIsNone(hub_collect.read_last_usage_api_failure())
        self.assertEqual(next_state.consecutive_failures, 0)

    def test_failed_fetch_records_failure_and_does_not_touch_capture_file(self) -> None:
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=True)
        with mock.patch.object(
            hub_usage_fetch, "fetch_rate_limit_capture", return_value=(None, "schema_mismatch", ["/x <str>"])
        ):
            next_state = hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        self.assertFalse(hub_collect.RATE_LIMITS_PATH.exists())
        recorded = hub_collect.read_last_usage_api_failure()
        self.assertEqual(recorded["reason"], "schema_mismatch")
        self.assertEqual(recorded["response_keys"], ["/x <str>"])
        # N1(§8-3) — 이 호출부가 failure_reason_message 를 실제로 부르는 두 배선 지점 중
        # 첫 번째다(나머지 하나는 아래 test_unclassified_exception_from_fetch_records_
        # internal_error_with_fallback_message 의 except Exception 분기).
        self.assertEqual(recorded["message"], hub_usage_fetch.failure_reason_message("schema_mismatch"))
        self.assertEqual(next_state.consecutive_failures, 1)

    def test_unclassified_exception_from_fetch_records_internal_error_with_fallback_message(self) -> None:
        """N1 배선의 두 번째 호출부(`except Exception` 분기) — `fetch_rate_limit_capture`
        자신이 튜플이 아니라 예외를 던지는(계약 위반) 경우에도 message 가 실린다."""
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=True)
        with mock.patch.object(
            hub_usage_fetch, "fetch_rate_limit_capture", side_effect=RuntimeError("계약 위반 흉내")
        ):
            hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        recorded = hub_collect.read_last_usage_api_failure()
        self.assertEqual(recorded["reason"], hub_server.USAGE_API_UNEXPECTED_ERROR_REASON)
        self.assertEqual(
            recorded["message"], hub_usage_fetch.failure_reason_message(hub_server.USAGE_API_UNEXPECTED_ERROR_REASON)
        )

    def test_not_yet_due_skips_fetch(self) -> None:
        config = hub_model.HubConfig(
            show_usage_panel=True, usage_api_enabled=True, usage_api_poll_interval_seconds=300
        )
        state = hub_usage.UsageApiPollState(last_attempt_at_ms=1_000, consecutive_failures=0)
        with mock.patch.object(hub_usage_fetch, "fetch_rate_limit_capture") as mocked_fetch:
            result = hub_server._run_usage_api_poll_cycle(1_000 + 1000, state, config)  # 1초 뒤 — 5분 미도달
        mocked_fetch.assert_not_called()
        self.assertEqual(result, state)


class RunUsageApiPollCycleDeepNestingRegressionTest(unittest.TestCase):
    """AR4(B-1) 회귀(§8-2) — 폴링 사이클이 어떤 경로로 끝나도 시도가 반영된 상태를
    반환한다. `fetch_rate_limit_capture` 자체는 mock 하지 않고 그 아래 층(urlopen·Keychain
    판독)만 mock 해 실제 파싱 경로를 태운다 — 기존 테스트들이 fetch 를 통째로 mock 해서
    이 경로를 못 덮는다는 감사 지적의 직접 반영이다."""

    _DEEP_NESTING_DEPTH = 3000   # 감사 실측 — 이 깊이에서 json.loads 가 RecursionError 를 던진다

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_usage_api_error_path = hub_collect.LAST_USAGE_API_ERROR_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.temp_dir / "last_usage_api_error.json"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.original_usage_api_error_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _deeply_nested_body(self) -> bytes:
        nested = ("[" * self._DEEP_NESTING_DEPTH) + ("]" * self._DEEP_NESTING_DEPTH)
        return nested.encode("utf-8")

    def _patch_credential_and_transport(self, body: bytes):
        """모킹 이음선은 `_open_usage_api_request` 다(H10, §5-4) — `fetch_rate_limit_capture`
        가 리다이렉트를 막는 opener 로 바뀌면서 `urllib.request.urlopen` 을 더 이상 호출하지
        않는다. 여기서 옮기지 않으면 이 mock 이 조용히 무력해져 실제 네트워크 호출을
        시도하게 된다 — 절대 하지 말아야 할 일이라 반드시 함께 옮긴다."""
        return (
            mock.patch.object(
                hub_usage_fetch, "_read_oauth_access_token_with_reason", return_value=("token", None)
            ),
            mock.patch.object(
                hub_usage_fetch, "_open_usage_api_request", return_value=_FakeUrlopenResponse(body)
            ),
        )

    def test_deep_nesting_does_not_lose_attempt_state(self) -> None:
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=True)
        credential_patch, transport_patch = self._patch_credential_and_transport(self._deeply_nested_body())
        with credential_patch, transport_patch:
            next_state = hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        self.assertEqual(next_state.last_attempt_at_ms, 1_000)
        self.assertEqual(next_state.consecutive_failures, 1)

    def test_deep_nesting_records_failure_for_observability(self) -> None:
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=True)
        credential_patch, transport_patch = self._patch_credential_and_transport(self._deeply_nested_body())
        with credential_patch, transport_patch:
            hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        recorded = hub_collect.read_last_usage_api_failure()
        self.assertIsNotNone(recorded)
        self.assertTrue(recorded["reason"])

    def test_cleanup_failure_after_success_still_counts_as_attempt(self) -> None:
        """성공 후 `clear_usage_api_failure()` 가 OSError 로 새도 보수적으로 실패 시도로
        집계한다(원격 호출은 성공했지만 백오프가 자란다 — 의도된 보수성, PRP §4 AR4)."""
        config = hub_model.HubConfig(show_usage_panel=True, usage_api_enabled=True)
        capture = hub_usage.RateLimitCapture(
            captured_at_ms=1, session_resets_at_ms=None, weekly_resets_at_ms=None,
            session_used_percent=10, weekly_used_percent=20,
        )
        with mock.patch.object(
            hub_usage_fetch, "fetch_rate_limit_capture", return_value=(capture, None, None)
        ), mock.patch.object(
            hub_collect, "clear_usage_api_failure", side_effect=OSError("unlink 실패")
        ):
            next_state = hub_server._run_usage_api_poll_cycle(1_000, hub_usage.UsageApiPollState(), config)
        self.assertEqual(next_state.last_attempt_at_ms, 1_000)
        self.assertEqual(next_state.consecutive_failures, 1)


if __name__ == "__main__":
    unittest.main()
