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


MANUAL_INTERVAL_MS = hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS
AUTOMATIC_INTERVAL_MS = hub_release.RELEASE_CHECK_INTERVAL_MS


class ReleaseCheckerTest(unittest.TestCase):
    """판정기(`_ReleaseChecker`, docs/prps/hub-release-check-on-refresh.md RR4·RR5) — 자동·수동 두 경로가 같은 시도 시각을 공유한다.
    시계(`_wall_clock_ms`)는 락 안에서 읽는 것이 계약이라 테스트가 `clock` 딕셔너리로 제어한다."""

    def setUp(self) -> None:
        self.clock = {"now": NOW_MS}
        self.refresher = mock.Mock()
        clock_patch = mock.patch.object(hub_server, "_wall_clock_ms", side_effect=lambda: self.clock["now"])
        cycle_patch = mock.patch.object(hub_release_read, "run_release_check_cycle")
        clock_patch.start()
        self.cycle = cycle_patch.start()
        self.addCleanup(mock.patch.stopall)

    def _checker(self, last_attempt_at_ms: int | None = None) -> "hub_server._ReleaseChecker":
        return hub_server._ReleaseChecker(self.refresher, last_attempt_at_ms)

    def test_rc1_first_check_runs_the_cycle_and_forces_a_collect(self) -> None:
        checker = self._checker()
        self.assertTrue(checker.check_if_due(MANUAL_INTERVAL_MS))
        self.cycle.assert_called_once_with(NOW_MS)
        self.refresher.collect_if_older_than.assert_called_once()
        self.assertEqual(self.refresher.collect_if_older_than.call_args.args[1], hub_server.ACTIVITY_COLLECT_MAX_AGE_MS)

    def test_rc2_inside_the_manual_interval_does_nothing(self) -> None:
        checker = self._checker(NOW_MS)
        self.clock["now"] = NOW_MS + MANUAL_INTERVAL_MS - 1
        self.assertFalse(checker.check_if_due(MANUAL_INTERVAL_MS))
        self.cycle.assert_not_called()
        self.refresher.collect_if_older_than.assert_not_called()

    def test_rc3_at_the_manual_interval_runs_again(self) -> None:
        checker = self._checker(NOW_MS)
        self.clock["now"] = NOW_MS + MANUAL_INTERVAL_MS
        self.assertTrue(checker.check_if_due(MANUAL_INTERVAL_MS))
        self.cycle.assert_called_once_with(NOW_MS + MANUAL_INTERVAL_MS)

    def test_rc4_a_manual_check_pushes_the_automatic_check_back(self) -> None:
        """U5 — 수동 확인도 시도로 기록돼 다음 자동 확인은 그 시각부터 6시간 뒤다."""
        checker = self._checker()
        checker.check_if_due(MANUAL_INTERVAL_MS)
        self.cycle.reset_mock()
        self.clock["now"] = NOW_MS + AUTOMATIC_INTERVAL_MS - 1
        self.assertFalse(checker.check_if_due(AUTOMATIC_INTERVAL_MS))
        self.clock["now"] = NOW_MS + AUTOMATIC_INTERVAL_MS
        self.assertTrue(checker.check_if_due(AUTOMATIC_INTERVAL_MS))
        self.cycle.assert_called_once_with(NOW_MS + AUTOMATIC_INTERVAL_MS)

    def test_rc5_a_manual_check_right_after_an_automatic_one_is_skipped(self) -> None:
        checker = self._checker()
        checker.check_if_due(AUTOMATIC_INTERVAL_MS)
        self.cycle.reset_mock()
        self.clock["now"] = NOW_MS + 30_000
        self.assertFalse(checker.check_if_due(MANUAL_INTERVAL_MS))
        self.cycle.assert_not_called()

    def test_rc6_an_unexpected_cycle_exception_is_logged_and_still_counts_as_an_attempt(self) -> None:
        """AR4 선례 — 예외가 시도 시각 갱신을 무산시키면 같은 예외가 깨어날 때마다 반복된다. 강제 수집은 그래도 한다(RR5)."""
        self.cycle.side_effect = RuntimeError("boom")
        checker = self._checker()
        captured = io.StringIO()
        with redirect_stderr(captured):
            self.assertTrue(checker.check_if_due(MANUAL_INTERVAL_MS))
        self.assertIn("boom", captured.getvalue())
        self.refresher.collect_if_older_than.assert_called_once()
        self.assertFalse(checker.check_if_due(MANUAL_INTERVAL_MS))
        self.assertEqual(self.cycle.call_count, 1)

    def test_rc7_a_backwards_wall_clock_means_attempt(self) -> None:
        checker = self._checker(NOW_MS)
        self.clock["now"] = NOW_MS - 1000
        self.assertTrue(checker.check_if_due(MANUAL_INTERVAL_MS))

    def test_rc8_a_waiting_request_skips_after_the_running_check_finishes(self) -> None:
        """git 은 한 번에 하나 — 확인이 진행 중일 때 온 두 번째 호출은 락을 기다렸다가 앞선 시도를 보고 건너뛴다.
        그 건너뜀이 반환될 때 강제 수집은 이미 끝나 있어야 한다(RR5). 락이 있다는 것(직렬화)과 건너뜀 전에 수집이 끝난다는 것을 문다 —
        수집·시계가 락 안이라는 위치 자체는 RC11·RC12 가 락 상태를 직접 본다."""
        started = threading.Event()
        release_first = threading.Event()
        waiter_entering = threading.Event()
        collect_calls_at_waiter_return: list[int] = []
        waiter_results: list[bool] = []

        def blocked_cycle(_now_ms: int) -> None:
            started.set()
            self.assertTrue(release_first.wait(timeout=5))

        self.cycle.side_effect = blocked_cycle
        checker = self._checker()
        first_thread = threading.Thread(target=checker.check_if_due, args=(MANUAL_INTERVAL_MS,))

        def waiter() -> None:
            waiter_entering.set()
            waiter_results.append(checker.check_if_due(MANUAL_INTERVAL_MS))
            collect_calls_at_waiter_return.append(self.refresher.collect_if_older_than.call_count)

        waiter_thread = threading.Thread(target=waiter)
        first_thread.start()
        self.assertTrue(started.wait(timeout=5))
        waiter_thread.start()
        self.assertTrue(waiter_entering.wait(timeout=5))
        release_first.set()
        first_thread.join(timeout=5)
        waiter_thread.join(timeout=5)
        self.assertEqual(self.cycle.call_count, 1)
        self.assertEqual(self.refresher.collect_if_older_than.call_count, 1)
        self.assertEqual(waiter_results, [False])
        self.assertEqual(collect_calls_at_waiter_return, [1])

    def test_rc11_the_clock_is_read_while_the_lock_is_held(self) -> None:
        """RR4 — 시계를 락 밖(진입 시각)에서 읽으면 밀린 호출이 더 늦은 시도 시각보다 이른 now 로 판정한다. 락 상태를 시계가 불리는 순간에 본다."""
        checker = self._checker()
        lock_states: list[bool] = []

        def clock_reporting_lock_state() -> int:
            lock_states.append(checker._lock.locked())
            return NOW_MS

        hub_server._wall_clock_ms.side_effect = clock_reporting_lock_state
        checker.check_if_due(MANUAL_INTERVAL_MS)
        self.assertEqual(lock_states, [True])

    def test_rc12_the_forced_collect_runs_while_the_lock_is_held(self) -> None:
        """RR5 — 강제 수집이 락 밖이면 락을 기다리던 호출이 새 확인 결과가 캐시에 담기기 전에 건너뛰고 반환한다. 락 상태를 수집이 불리는 순간에 본다."""
        checker = self._checker()
        lock_states: list[bool] = []
        self.refresher.collect_if_older_than.side_effect = lambda *_args: lock_states.append(checker._lock.locked())
        checker.check_if_due(MANUAL_INTERVAL_MS)
        self.assertEqual(lock_states, [True])


class BuildReleaseCheckerTest(unittest.TestCase):
    def test_rc9_switch_off_builds_no_checker_and_reads_no_record(self) -> None:
        config = hub_model.HubConfig(update_check_enabled=False)
        with mock.patch.object(hub_release_read, "read_release_check_record") as read_record:
            checker = hub_server._build_release_checker(config, mock.Mock())
        self.assertIsNone(checker)
        read_record.assert_not_called()

    def test_rc10_resumes_the_persisted_last_attempt_so_a_restart_keeps_the_manual_interval(self) -> None:
        previous = hub_release.ReleaseCheckRecord(NOW_MS, NOW_MS, "1.0.0", None)
        config = hub_model.HubConfig(update_check_enabled=True)
        with mock.patch.object(hub_release_read, "read_release_check_record", return_value=previous), \
             mock.patch.object(hub_server, "_wall_clock_ms", return_value=NOW_MS + 30_000), \
             mock.patch.object(hub_release_read, "run_release_check_cycle") as cycle:
            checker = hub_server._build_release_checker(config, mock.Mock())
            assert checker is not None
            self.assertFalse(checker.check_if_due(MANUAL_INTERVAL_MS))
        cycle.assert_not_called()

    def test_without_a_persisted_record_the_first_check_is_due(self) -> None:
        config = hub_model.HubConfig(update_check_enabled=True)
        with mock.patch.object(hub_release_read, "read_release_check_record", return_value=None), \
             mock.patch.object(hub_server, "_wall_clock_ms", return_value=NOW_MS), \
             mock.patch.object(hub_release_read, "run_release_check_cycle") as cycle:
            checker = hub_server._build_release_checker(config, mock.Mock())
            assert checker is not None
            self.assertTrue(checker.check_if_due(MANUAL_INTERVAL_MS))
        cycle.assert_called_once()


class ReleaseCheckLoopTest(unittest.TestCase):
    def _run_loop(self, check_side_effect=None, wakeups: int = 2) -> mock.Mock:
        stop_event = threading.Event()
        wake_count = {"n": 0}

        def bounded_wait(_timeout=None) -> bool:
            wake_count["n"] += 1
            if wake_count["n"] >= wakeups:
                stop_event.set()
            return False

        checker = mock.Mock()
        checker.check_if_due.side_effect = check_side_effect
        config = hub_model.HubConfig(server_heartbeat_interval_seconds=0)
        with mock.patch.object(stop_event, "wait", side_effect=bounded_wait):
            hub_server._release_check_loop(config, stop_event, checker)
        return checker

    def test_rl1_every_wakeup_asks_the_checker_with_the_automatic_interval(self) -> None:
        checker = self._run_loop(wakeups=2)
        self.assertEqual(checker.check_if_due.call_count, 2)
        for call in checker.check_if_due.call_args_list:
            self.assertEqual(call.args, (AUTOMATIC_INTERVAL_MS,))

    def test_rl2_loop_survives_a_checker_exception(self) -> None:
        captured = io.StringIO()
        with redirect_stderr(captured):
            checker = self._run_loop(check_side_effect=RuntimeError("checker boom"), wakeups=3)
        self.assertEqual(checker.check_if_due.call_count, 3)
        self.assertIn("checker boom", captured.getvalue())


class StartReleaseCheckThreadTest(unittest.TestCase):
    def test_rt1_no_checker_starts_no_thread(self) -> None:
        with mock.patch.object(hub_server.threading, "Thread") as thread_class:
            result = hub_server._start_release_check_thread(hub_model.HubConfig(), threading.Event(), None)
        self.assertIsNone(result)
        thread_class.assert_not_called()

    def test_rt2_a_checker_starts_one_daemon_thread_running_the_loop(self) -> None:
        stop_event = threading.Event()
        config = hub_model.HubConfig(update_check_enabled=True)
        checker = mock.Mock()
        with mock.patch.object(hub_server, "_release_check_loop") as loop:
            thread = hub_server._start_release_check_thread(config, stop_event, checker)
            assert thread is not None
            thread.join(timeout=2)
        self.assertTrue(thread.daemon)
        loop.assert_called_once_with(config, stop_event, checker)


if __name__ == "__main__":
    unittest.main()
