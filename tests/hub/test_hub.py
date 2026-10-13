"""hub.py CLI 엔트리 단위 테스트. 검수 M7(4) — collect 예외를 ok:false 계약으로 변환하는지 확인."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub  # noqa: E402
import hub_collect  # noqa: E402
import hub_daemon  # noqa: E402
import hub_release  # noqa: E402
import hub_release_read  # noqa: E402
import hub_server_state  # noqa: E402
import hub_server_state_read  # noqa: E402
import hub_settings  # noqa: E402


class _Args:
    def __init__(self, as_json: bool = True) -> None:
        self.json = as_json


class CmdCollectFailureContractTest(unittest.TestCase):
    """검수 M7 — hub.py cmd_collect/cmd_open 은 예상치 못한 예외를 원시 트레이스백으로 흘리지 않는다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_server_state_hub_home = hub_server_state_read.HUB_HOME
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"
        # 개정 2 — cmd_collect 의 성공 경로(_collect_and_write)가 touch_collect_success_stamp()
        # 를 부른다. 격리하지 않으면 개발자 실제 머신의 ~/.claude/hub/last_collect_success 를
        # touch 한다.
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_server_state_read.HUB_HOME = self.original_server_state_hub_home
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_collect_snapshot_exception_becomes_ok_false_contract(self) -> None:
        with mock.patch.object(hub_collect, "collect_snapshot", side_effect=RuntimeError("boom")):
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = hub.cmd_collect(_Args())

        self.assertEqual(exit_code, 1)
        payload = json.loads(captured.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("boom", payload["reason"])

    def test_failure_is_recorded_and_readable_via_status(self) -> None:
        with mock.patch.object(hub_collect, "collect_snapshot", side_effect=RuntimeError("boom")):
            with redirect_stdout(io.StringIO()):
                hub.cmd_collect(_Args())

        recorded = hub_collect.read_last_collect_failure()
        self.assertIsNotNone(recorded)
        self.assertIn("boom", recorded["reason"])

    def test_success_clears_previous_failure_record(self) -> None:
        hub_collect.record_collect_failure("이전 실패")
        with mock.patch.object(hub_collect, "collect_snapshot") as mock_collect, \
             mock.patch.object(hub_collect, "write_hub_html"):
            mock_collect.return_value = mock.Mock(projects=())
            with redirect_stdout(io.StringIO()):
                exit_code = hub.cmd_collect(_Args())

        self.assertEqual(exit_code, 0)
        self.assertIsNone(hub_collect.read_last_collect_failure())


class CmdOpenServerAwareTest(unittest.TestCase):
    """개정 쟁점 R2 — `/hub`(cmd_open)는 서버를 절대 기동하지 않는다(요구 R-2)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_server_state_hub_home = hub_server_state_read.HUB_HOME
        self.original_html_path = hub_collect.HUB_HTML_PATH
        self.original_heartbeat_path = hub_server_state_read.SERVER_HEARTBEAT_PATH
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.temp_dir / "server_heartbeat"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        # 개정 2 — cmd_open 의 수집 폴백(_collect_and_write)이 touch_collect_success_stamp()
        # 를 부른다(위 setUp 격리와 같은 이유).
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_server_state_read.HUB_HOME = self.original_server_state_hub_home
        hub_collect.HUB_HTML_PATH = self.original_html_path
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.original_heartbeat_path
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _stub_open_browser(self):
        """실제 브라우저를 띄우지 않는 hub_daemon.open_browser 대체(GOTCHA 3).

        `mock.patch("webbrowser.open")` 는 cmd_open 이 hub_daemon.open_browser 를 거쳐
        `/usr/bin/open` 을 서브프로세스로 실행하는 경로를 전혀 막지 못한다 — hub_daemon
        모듈의 함수 자체를 대체해야 한다.
        """
        return mock.patch.object(
            hub_daemon, "open_browser",
            return_value=hub_server_state.BrowserOpenResult(opened=True, focus_requested=True, fallback_reason=None),
        )

    def test_fresh_heartbeat_and_existing_hub_html_opens_http_url_without_collecting(self) -> None:
        hub_server_state_read.SERVER_HEARTBEAT_PATH.write_text("")  # mtime = 지금 = 신선
        hub_collect.HUB_HTML_PATH.write_text("<html></html>")

        with mock.patch.object(hub_collect, "collect_snapshot") as mock_collect, \
             self._stub_open_browser():
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = hub.cmd_open(_Args())

        self.assertEqual(exit_code, 0)
        mock_collect.assert_not_called()
        payload = json.loads(captured.getvalue())
        self.assertTrue(payload["server_alive"])
        self.assertTrue(payload["url"].startswith("http://localhost:8794"))
        self.assertNotIn("note", payload)

    def test_fresh_heartbeat_but_missing_hub_html_recovers_with_one_time_collect(self) -> None:
        """검수 M1 — 하트비트만으로 서버 URL 을 열면 hub.html 이 없을 때 깨진 링크를 연다.
        server_alive=true 여도 hub.html 실재를 확인해 1회 수집으로 복구해야 한다."""
        hub_server_state_read.SERVER_HEARTBEAT_PATH.write_text("")  # mtime = 지금 = 신선, hub.html 은 없음

        with mock.patch.object(hub_collect, "collect_snapshot") as mock_collect, \
             mock.patch.object(hub_collect, "write_hub_html"), \
             self._stub_open_browser():
            mock_collect.return_value = mock.Mock(projects=())
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = hub.cmd_open(_Args())

        self.assertEqual(exit_code, 0)
        mock_collect.assert_called_once()
        payload = json.loads(captured.getvalue())
        self.assertTrue(payload["server_alive"])
        self.assertTrue(payload["url"].startswith("file://"))
        self.assertIn("배경 상한", payload["note"])  # §0.3 Minor 4 — "수집 주기" 서술 정정

    def test_no_heartbeat_collects_once_and_opens_file_url_with_note(self) -> None:
        with mock.patch.object(hub_collect, "collect_snapshot") as mock_collect, \
             mock.patch.object(hub_collect, "write_hub_html"), \
             self._stub_open_browser():
            mock_collect.return_value = mock.Mock(projects=())
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = hub.cmd_open(_Args())

        self.assertEqual(exit_code, 0)
        mock_collect.assert_called_once()
        payload = json.loads(captured.getvalue())
        self.assertFalse(payload["server_alive"])
        self.assertTrue(payload["url"].startswith("file://"))
        self.assertIn("server start", payload["note"])

    def test_open_payload_exposes_browser_focus_field(self) -> None:
        """계약 회귀 — `open --json` payload 에 browser_focus_requested 가 노출된다."""
        hub_server_state_read.SERVER_HEARTBEAT_PATH.write_text("")  # mtime = 지금 = 신선
        hub_collect.HUB_HTML_PATH.write_text("<html></html>")

        with mock.patch.object(hub_collect, "collect_snapshot") as mock_collect, \
             self._stub_open_browser():
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = hub.cmd_open(_Args())

        self.assertEqual(exit_code, 0)
        mock_collect.assert_not_called()
        payload = json.loads(captured.getvalue())
        self.assertIn("browser_focus_requested", payload)
        self.assertTrue(payload["browser_focus_requested"])


class CmdStatusServerSummaryTest(unittest.TestCase):
    """검수 M2-3 — `/hub status` 가 server_maintenance_stalled(개정 2, 구 server_collect_stalled)
    를 서버 요약에 포함하는지 확인한다.
    실제 ~/.claude 는 건드리지 않는다 — HUB_HTML_PATH·hook_install_status·이벤트 읽기·
    config.json·사용량 히스토리·마지막 collect 실패 기록을 전부 모킹/격리한다(검수 M2 — cmd_status 가
    load_config()·_usage_sample_age_ms() 를 호출하게 되면서 실제 개발자 머신의
    비공개 사용량 파일을 읽던 회귀가 있었다).

    LAST_COLLECT_ERROR_PATH 도 격리한다(검수 R2-n1) — cmd_status 는 read_last_collect_failure()
    도 부르는데, 그 상수는 HUB_HOME 과 별개로 임포트 시점에 확정되므로 직접 바꿔야 한다.
    RATE_LIMITS_PATH·SETTINGS_PATH 도 같은 이유로 격리한다 — cmd_status 가
    hub_settings.statusline_install_status()·hub_collect.read_rate_limit_capture() 를
    새로 호출하게 되면서(docs/prps/hub-usage-reset-time-and-refresh.md, 사용률 퍼센트까지
    이 캡처 하나로 통합된 뒤로는 docs/prps/hub-card-cleanup-and-usage-source.md 결정 P1)
    실제 개발자 머신의 ~/.claude/settings.json·~/.claude/hub/rate_limits.json 을 읽던
    회귀가 생길 수 있었다. 이 클래스의 "실제 ~/.claude 를 건드리지 않는다"는 주장이 문자
    그대로 참이 되는 조건이다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_html_path = hub_collect.HUB_HTML_PATH
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_usage_api_error_path = hub_collect.LAST_USAGE_API_ERROR_PATH
        self.original_settings_path = hub_settings.SETTINGS_PATH
        self.neutralized_account_path = hub_collect.CLAUDE_GLOBAL_CONFIG_PATH
        # cmd_status 가 계정 유무를 진단하려 ~/.claude.json 을 읽는다 — 임시 경로로 격리한다(결정 AC12).
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH = self.temp_dir / "claude.json"
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"  # 존재하지 않는 경로 — 실제 파일 미접근
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"  # 존재하지 않으면 기본값
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"  # 존재하지 않으면 None
        # R1 — cmd_status 가 read_last_usage_api_failure()·usage_api_last_attempt_age_ms 를
        # 새로 호출하게 되면서 실제 ~/.claude/hub/last_usage_api_error.json 을 읽던 회귀가
        # 생길 수 있었다(위 RATE_LIMITS_PATH·LAST_COLLECT_ERROR_PATH 격리와 같은 이유).
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.temp_dir / "last_usage_api_error.json"
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"  # 존재하지 않으면 미설치로 판정

    def tearDown(self) -> None:
        hub_collect.HUB_HTML_PATH = self.original_html_path
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.original_usage_api_error_path
        hub_settings.SETTINGS_PATH = self.original_settings_path
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH = self.neutralized_account_path   # 중화값으로 복구한다(AC12)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_status(self, maintenance_stalled: bool) -> hub_server_state.ServerStatus:
        return hub_server_state.ServerStatus(
            record=None, process_present=True, heartbeat_age_ms=1, alive=not maintenance_stalled,
            http_ok=True, crashed_evidence=False, log_tail=None, orphaned_evidence=False,
            maintenance_stalled=maintenance_stalled, collect_health="ok",
            last_collect_success_age_ms=None,
        )

    def _run_cmd_status(self, maintenance_stalled: bool) -> dict:
        with mock.patch.object(hub_daemon, "server_status", return_value=self._make_status(maintenance_stalled)), \
             mock.patch.object(hub_collect, "read_recent_events", return_value=([], ())), \
             mock.patch("hub_settings.hook_install_status", return_value={}):
            captured = io.StringIO()
            with redirect_stdout(captured):
                hub.cmd_status(_Args())
        return json.loads(captured.getvalue())

    def test_maintenance_stalled_is_surfaced_in_status_summary(self) -> None:
        payload = self._run_cmd_status(maintenance_stalled=True)
        self.assertTrue(payload["server_maintenance_stalled"])

    def test_maintenance_not_stalled_is_surfaced_as_false(self) -> None:
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["server_maintenance_stalled"])

    def test_collect_health_is_surfaced_in_status_summary(self) -> None:
        """개정 2 — server_collect_health·last_collect_success_age_ms 가 서버 요약에 실린다."""
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertEqual(payload["server_collect_health"], "ok")
        self.assertIn("last_collect_success_age_ms", payload)

    def test_usage_sample_age_ms_is_null_when_switch_is_off(self) -> None:
        """`commands/hub.md` 의 공개 출력 계약 — 스위치 off 면 usage_sample_age_ms 는 null."""
        hub_collect.CONFIG_PATH.write_text(json.dumps({"show_usage_panel": False}))
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["usage_panel_enabled"])
        self.assertIsNone(payload["usage_sample_age_ms"])

    def test_usage_sample_age_ms_is_null_when_usage_file_is_absent(self) -> None:
        """`commands/hub.md` 의 공개 출력 계약 — 캡처 파일이 없으면 enabled 는 true 인데 age 는 null.

        statusLine 을 등록하지 않은 사용자가 **항상** 보게 되는 상태다(검수 R2-n2, 결정 P1).
        스위치 off 와 값이 다르다는 점이 핵심이다 — off 는 enabled 도 false 다. setUp 이 잡아 둔
        임시 경로에 파일을 쓰지 않는 것만으로 이 상황이 재현된다.
        """
        self.assertFalse(hub_collect.RATE_LIMITS_PATH.exists())
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertTrue(payload["usage_panel_enabled"])
        self.assertIsNone(payload["usage_sample_age_ms"])

    def test_usage_sample_age_ms_is_int_when_usage_file_is_normal(self) -> None:
        """`commands/hub.md` 의 공개 출력 계약 — 캡처에 퍼센트가 있으면 usage_sample_age_ms 는
        정수다(결정 P1 — 퍼센트의 유일한 출처가 캡처 파일로 바뀌었다)."""
        hub_collect.RATE_LIMITS_PATH.write_text(
            json.dumps(
                {
                    "captured_at_ms": 1,
                    "session_resets_at_ms": None,
                    "weekly_resets_at_ms": None,
                    "session_used_percent": 10,
                    "weekly_used_percent": 19,
                }
            )
        )
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertTrue(payload["usage_panel_enabled"])
        self.assertIsInstance(payload["usage_sample_age_ms"], int)

    def test_rate_limit_diagnostic_fields_are_null_when_capture_and_statusline_are_absent(self) -> None:
        """docs/prps/hub-usage-reset-time-and-refresh.md 「hub.py」 절 — statusline_installed·
        rate_limit_capture_age_ms·rate_limit_resets_remaining_ms 3필드가 새로 추가된다."""
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["statusline_installed"])
        self.assertIsNone(payload["rate_limit_capture_age_ms"])
        self.assertIsNone(payload["rate_limit_resets_remaining_ms"])

    def test_rate_limit_diagnostic_fields_are_null_when_switch_is_off_even_if_capture_exists(self) -> None:
        """검수 MEDIUM 1 회귀 방지 — PRP 「확정된 전제」4: show_usage_panel:false 는 usage 파일뿐
        아니라 rate_limits 캡처 파일도 읽지 않는다. 캡처가 있어도 스위치가 꺼져 있으면 두
        진단 필드는 null 이어야 한다(캡처 부재와 스위치 off 를 구분 못 하는 회귀를 잡는다)."""
        hub_collect.CONFIG_PATH.write_text(json.dumps({"show_usage_panel": False}))
        hub_collect.RATE_LIMITS_PATH.write_text(
            json.dumps({"captured_at_ms": 1, "session_resets_at_ms": 2, "weekly_resets_at_ms": 3})
        )
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["usage_panel_enabled"])
        self.assertIsNone(payload["rate_limit_capture_age_ms"])
        self.assertIsNone(payload["rate_limit_resets_remaining_ms"])

    def test_usage_api_fields_default_to_disabled_and_no_evidence(self) -> None:
        """R1 — usage_api_enabled 기본값 false(결정 A6), 시도 흔적이 없으면 age·failure 는 null."""
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["usage_api_enabled"])
        self.assertIsNone(payload["usage_api_last_attempt_age_ms"])
        self.assertIsNone(payload["usage_api_last_failure"])

    def test_usage_api_last_failure_is_surfaced_from_error_file(self) -> None:
        hub_collect.LAST_USAGE_API_ERROR_PATH.write_text(json.dumps({"at_ms": 1, "reason": "network_error"}))
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertEqual(payload["usage_api_last_failure"]["reason"], "network_error")
        self.assertIsInstance(payload["usage_api_last_attempt_age_ms"], int)

    def test_usage_api_enabled_reflects_config(self) -> None:
        hub_collect.CONFIG_PATH.write_text(json.dumps({"usage_api_enabled": True}))
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertTrue(payload["usage_api_enabled"])

    def test_release_check_fields_default_to_on_with_no_record(self) -> None:
        """harness-versioning 결정 UN2 — 한 번도 확인하지 않았으면 release_check 는 null, 스위치는 기본 on."""
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertTrue(payload["update_check_enabled"])
        self.assertIsNone(payload["release_check"])

    def test_release_check_failure_is_surfaced_only_here(self) -> None:
        """실패는 화면 경고가 아니라 /hub status 에서만 보인다 — 사유와 직전 성공의 최신 버전이 함께 나온다."""
        original_path = hub_release_read.RELEASE_CHECK_PATH
        hub_release_read.RELEASE_CHECK_PATH = self.temp_dir / "release_check.json"
        self.addCleanup(setattr, hub_release_read, "RELEASE_CHECK_PATH", original_path)
        hub_release_read.write_release_check_record(hub_release.ReleaseCheckRecord(5, 1, "1.1.0", "timeout"))
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertEqual(
            payload["release_check"],
            {"last_attempt_at_ms": 5, "last_success_at_ms": 1, "latest_version": "1.1.0", "last_failure_reason": "timeout"},
        )

    def test_update_check_enabled_reflects_config(self) -> None:
        hub_collect.CONFIG_PATH.write_text(json.dumps({"update_check_enabled": False}))
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["update_check_enabled"])

    def _write_synthetic_account(self) -> None:
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH.write_text(
            json.dumps(
                {
                    "oauthAccount": {
                        "organizationType": "claude_team",
                        "organizationName": "Example Labs",
                        "emailAddress": "dev.user@example.com",
                    }
                }
            )
        )

    def test_ac11_account_fields_report_presence_only_never_values(self) -> None:
        """결정 AC11 — /hub status 출력은 transcript 에 영구 기록된다. 유무 불리언만 싣고
        출력 JSON 전체 어디에도 이메일·조직 이름이 없어야 한다."""
        self._write_synthetic_account()
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertTrue(payload["account_info_enabled"])
        self.assertEqual(payload["account_info_fields"], {"plan": True, "organization": True, "email": True})
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("dev.user@example.com", serialized)
        self.assertNotIn("Example Labs", serialized)

    def test_ac11_partial_account_reports_which_field_is_missing(self) -> None:
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH.write_text(
            json.dumps({"oauthAccount": {"organizationType": "claude_future", "emailAddress": "dev.user@example.com"}})
        )
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertEqual(payload["account_info_fields"], {"plan": False, "organization": False, "email": True})

    def test_ac11_account_fields_are_null_when_file_is_absent(self) -> None:
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertTrue(payload["account_info_enabled"])
        self.assertIsNone(payload["account_info_fields"])

    def test_ac7_account_switch_off_reports_disabled_and_never_opens_the_file(self) -> None:
        self._write_synthetic_account()
        hub_collect.CONFIG_PATH.write_text(json.dumps({"show_account_info": False}))
        with mock.patch.object(hub_collect, "read_account_info") as mocked_read:
            payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["account_info_enabled"])
        self.assertIsNone(payload["account_info_fields"])
        mocked_read.assert_not_called()

    def test_ac7_usage_panel_off_also_disables_account_info(self) -> None:
        self._write_synthetic_account()
        hub_collect.CONFIG_PATH.write_text(json.dumps({"show_usage_panel": False}))
        payload = self._run_cmd_status(maintenance_stalled=False)
        self.assertFalse(payload["account_info_enabled"])
        self.assertIsNone(payload["account_info_fields"])


if __name__ == "__main__":
    unittest.main()
