"""하네스 릴리스 알림의 배선 테스트 — collect_snapshot 합성 · 서버 확인 스레드 · config 스위치 · 스냅샷 키
(docs/prps/harness-versioning.md §5.5.6 「서버」). 순수 규칙은 test_hub_release.py, I/O 는
test_hub_release_read.py 가 맡는다. 네트워크·실제 ~/.claude 를 쓰지 않는다(경로는 setUp 에서 임시로 바꾼다).
"""

import dataclasses
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402
import hub_config  # noqa: E402
import hub_model  # noqa: E402
import hub_release  # noqa: E402
import hub_release_read  # noqa: E402
import hub_server  # noqa: E402

NOW_MS = 1791000000000
INSTALLED_RECORD = {
    "version": 3, "repo_path": "/some/repo", "scope": "user", "installed_at": "2026-10-13T05:00:00Z",
    "installed_from_commit": "d" * 40, "harness_version": "1.0.0",
}


class ConfigSwitchTest(unittest.TestCase):
    def test_update_check_defaults_to_on(self) -> None:
        self.assertTrue(hub_model.HubConfig().update_check_enabled)

    def test_config_json_can_turn_it_off(self) -> None:
        config, warnings = hub_config.config_from_raw({"update_check_enabled": False}, hub_model.HubConfig())
        self.assertFalse(config.update_check_enabled)
        self.assertEqual(warnings, ())

    def test_wrong_type_falls_back_to_default_with_warning(self) -> None:
        config, warnings = hub_config.config_from_raw({"update_check_enabled": "no"}, hub_model.HubConfig())
        self.assertTrue(config.update_check_enabled)
        self.assertEqual(len(warnings), 1)
        self.assertIn("update_check_enabled", warnings[0])


class SnapshotContractTest(unittest.TestCase):
    def _snapshot(self, view: hub_release.HarnessVersionView | None) -> hub_model.HubSnapshot:
        return hub_model.HubSnapshot(
            collected_at_ms=1, projects=(), unresolved_dir_names=(), warnings=(), harness_version=view
        )

    def test_harness_version_defaults_to_none(self) -> None:
        self.assertIsNone(hub_model.HubSnapshot(collected_at_ms=1, projects=(), unresolved_dir_names=(), warnings=()).harness_version)

    def test_view_is_serialised_into_the_page_data(self) -> None:
        view = hub_release.HarnessVersionView("1.0.0", "ddddddd", "2026-10-13T05:00:00Z", "1.1.0", True)
        template = '<script type="application/json" id="dzh-data">{}</script>'
        rendered = hub_model.render_hub_html(template, self._snapshot(view))
        payload = json.loads(rendered.split('id="dzh-data">')[1].split("</script>")[0])
        self.assertEqual(payload["harness_version"]["latest_version"], "1.1.0")
        self.assertTrue(payload["harness_version"]["is_update_available"])

    def test_content_key_changes_when_a_new_release_appears(self) -> None:
        before = hub_release.HarnessVersionView("1.0.0", "ddddddd", "t", "", False)
        after = dataclasses.replace(before, latest_version="1.1.0", is_update_available=True)
        self.assertNotEqual(
            hub_model.snapshot_content_key(self._snapshot(before)), hub_model.snapshot_content_key(self._snapshot(after))
        )


class CollectSnapshotHarnessVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.saved = {
            (hub_collect, name): getattr(hub_collect, name)
            for name in ("EVENTS_DIR", "PROJECTS_DIR", "CONFIG_PATH", "RATE_LIMITS_PATH", "SESSIONS_DIR")
        }
        self.saved[(hub_release_read, "INSTALL_RECORD_PATH")] = hub_release_read.INSTALL_RECORD_PATH
        self.saved[(hub_release_read, "RELEASE_CHECK_PATH")] = hub_release_read.RELEASE_CHECK_PATH
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"
        hub_release_read.INSTALL_RECORD_PATH = self.temp_dir / ".coding-harness.json"
        hub_release_read.RELEASE_CHECK_PATH = self.temp_dir / "release_check.json"

    def tearDown(self) -> None:
        for (module, name), value in self.saved.items():
            setattr(module, name, value)

    def _install(self, **overrides) -> None:
        hub_release_read.INSTALL_RECORD_PATH.write_text(json.dumps({**INSTALLED_RECORD, **overrides}), encoding="utf-8")

    def _cache_latest(self, version: str) -> None:
        hub_release_read.write_release_check_record(hub_release.ReleaseCheckRecord(NOW_MS, NOW_MS, version, None))

    def test_no_install_record_means_no_view(self) -> None:
        self.assertIsNone(hub_collect.collect_snapshot(NOW_MS).harness_version)

    def test_new_release_in_the_cache_raises_the_alert(self) -> None:
        self._install()
        self._cache_latest("1.1.0")
        view = hub_collect.collect_snapshot(NOW_MS).harness_version
        assert view is not None
        self.assertTrue(view.is_update_available)
        self.assertEqual((view.installed_version, view.latest_version, view.installed_commit_short), ("1.0.0", "1.1.0", "ddddddd"))

    def test_alert_disappears_once_the_install_catches_up(self) -> None:
        """/harness-update 직후 — 설치 기록은 매 수집마다 새로 읽으므로 캐시를 지우지 않아도 알림이 사라진다."""
        self._install()
        self._cache_latest("1.1.0")
        self._install(harness_version="1.1.0")
        view = hub_collect.collect_snapshot(NOW_MS).harness_version
        assert view is not None
        self.assertFalse(view.is_update_available)

    def test_switch_off_in_config_json_hides_the_alert_but_keeps_the_label(self) -> None:
        self._install()
        self._cache_latest("1.1.0")
        hub_collect.CONFIG_PATH.write_text(json.dumps({"update_check_enabled": False}), encoding="utf-8")
        view = hub_collect.collect_snapshot(NOW_MS).harness_version
        assert view is not None
        self.assertFalse(view.is_update_available)
        self.assertEqual((view.installed_version, view.latest_version), ("1.0.0", ""))

    def test_broken_install_record_becomes_a_snapshot_warning(self) -> None:
        hub_release_read.INSTALL_RECORD_PATH.write_text("{", encoding="utf-8")
        snapshot = hub_collect.collect_snapshot(NOW_MS)
        self.assertIsNone(snapshot.harness_version)
        self.assertTrue(any(str(hub_release_read.INSTALL_RECORD_PATH) in warning for warning in snapshot.warnings))


class ReleaseCheckGateTest(unittest.TestCase):
    INTERVAL_MS = hub_release.RELEASE_CHECK_INTERVAL_MS

    def test_first_attempt_runs_the_cycle_and_returns_now(self) -> None:
        with mock.patch.object(hub_release_read, "run_release_check_cycle") as cycle:
            self.assertEqual(hub_server._run_release_check_gate(NOW_MS, None), NOW_MS)
        cycle.assert_called_once_with(NOW_MS)

    def test_inside_the_interval_does_nothing(self) -> None:
        with mock.patch.object(hub_release_read, "run_release_check_cycle") as cycle:
            result = hub_server._run_release_check_gate(NOW_MS + self.INTERVAL_MS - 1, NOW_MS)
        self.assertEqual(result, NOW_MS)
        cycle.assert_not_called()

    def test_after_the_interval_runs_again(self) -> None:
        with mock.patch.object(hub_release_read, "run_release_check_cycle") as cycle:
            result = hub_server._run_release_check_gate(NOW_MS + self.INTERVAL_MS, NOW_MS)
        self.assertEqual(result, NOW_MS + self.INTERVAL_MS)
        cycle.assert_called_once()

    def test_an_unexpected_cycle_exception_is_logged_and_still_counts_as_an_attempt(self) -> None:
        """AR4 선례 — 예외가 시도 시각 갱신을 무산시키면 다음 깨우기가 같은 예외를 5초마다 반복한다."""
        captured = io.StringIO()
        with mock.patch.object(hub_release_read, "run_release_check_cycle", side_effect=RuntimeError("boom")):
            with redirect_stderr(captured):
                result = hub_server._run_release_check_gate(NOW_MS, None)
        self.assertEqual(result, NOW_MS)
        self.assertIn("boom", captured.getvalue())


class ReleaseCheckLoopTest(unittest.TestCase):
    def _run_loop(self, gate_side_effect=None, previous_record=None, wakeups: int = 2) -> mock.MagicMock:
        stop_event = threading.Event()
        wake_count = {"n": 0}

        def bounded_wait(_timeout=None) -> bool:
            wake_count["n"] += 1
            if wake_count["n"] >= wakeups:
                stop_event.set()
            return False

        config = hub_model.HubConfig(server_heartbeat_interval_seconds=0)
        with mock.patch.object(hub_release_read, "read_release_check_record", return_value=previous_record), \
             mock.patch.object(hub_server, "_run_release_check_gate", side_effect=gate_side_effect) as gate, \
             mock.patch.object(stop_event, "wait", side_effect=bounded_wait):
            hub_server._release_check_loop(config, stop_event)
        return gate

    def test_loop_survives_a_gate_exception(self) -> None:
        captured = io.StringIO()
        with redirect_stderr(captured):
            gate = self._run_loop(gate_side_effect=RuntimeError("gate boom"), wakeups=3)
        self.assertEqual(gate.call_count, 3)
        self.assertIn("gate boom", captured.getvalue())

    def test_loop_resumes_from_the_persisted_last_attempt(self) -> None:
        """서버를 자주 재시작해도 6시간에 한 번을 넘지 않도록 — 첫 게이트 호출이 기록의 시도 시각을 받는다."""
        previous = hub_release.ReleaseCheckRecord(NOW_MS, NOW_MS, "1.0.0", None)
        gate = self._run_loop(gate_side_effect=lambda _now, last: last, previous_record=previous, wakeups=1)
        self.assertEqual(gate.call_args_list[0].args[1], NOW_MS)

    def test_loop_starts_without_a_previous_attempt_when_there_is_no_record(self) -> None:
        gate = self._run_loop(gate_side_effect=lambda now, _last: now, previous_record=None, wakeups=1)
        self.assertIsNone(gate.call_args_list[0].args[1])


class StartReleaseCheckThreadTest(unittest.TestCase):
    def test_switch_off_starts_no_thread(self) -> None:
        with mock.patch.object(hub_server.threading, "Thread") as thread_class:
            result = hub_server._start_release_check_thread(hub_model.HubConfig(update_check_enabled=False), threading.Event())
        self.assertIsNone(result)
        thread_class.assert_not_called()

    def test_switch_on_starts_one_daemon_thread_running_the_loop(self) -> None:
        stop_event = threading.Event()
        config = hub_model.HubConfig(update_check_enabled=True)
        with mock.patch.object(hub_server, "_release_check_loop") as loop:
            thread = hub_server._start_release_check_thread(config, stop_event)
            assert thread is not None
            thread.join(timeout=2)
        self.assertTrue(thread.daemon)
        loop.assert_called_once_with(config, stop_event)


if __name__ == "__main__":
    unittest.main()
