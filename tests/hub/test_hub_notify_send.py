"""hub_notify_send 단위 테스트(I/O — subprocess.run·경로 상수를 patch 로 가둔다. 실제 알림은 띄우지 않는다).
docs/prps/hub-macos-notification.md §9.2, 결정 MN6~MN8·MN11."""

import dataclasses
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)
import hub_notify  # noqa: E402
import hub_notify_send  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_session  # noqa: E402

BASE_MS = 1_786_000_000_000
MINUTE_MS = 60_000
TEXT = hub_notify.NotificationText(title="제목", subtitle="부제", message="본문")


def _completed(returncode: int, stderr: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=b"", stderr=stderr)


class SendNotificationTest(unittest.TestCase):
    def _send(self, **run_behavior):
        stderr = io.StringIO()
        with mock.patch.object(hub_notify_send.subprocess, "run", **run_behavior) as run_mock, redirect_stderr(stderr):
            result = hub_notify_send.send_notification(TEXT)
        return result, run_mock, stderr.getvalue()

    def test_success_passes_the_pure_argv_without_a_shell(self) -> None:
        result, run_mock, _ = self._send(return_value=_completed(0))
        self.assertEqual(result, (None, 0))
        run_mock.assert_called_once()
        (argv,), kwargs = run_mock.call_args
        self.assertEqual(tuple(argv), hub_notify.osascript_argv(TEXT))
        self.assertNotIn("shell", kwargs)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], hub_notify_send.NOTIFY_SEND_TIMEOUT_SECONDS)
        self.assertIs(kwargs["check"], False)

    def test_send_timeout_is_ten_seconds(self) -> None:
        self.assertEqual(hub_notify_send.NOTIFY_SEND_TIMEOUT_SECONDS, 10)

    def test_nonzero_exit_reports_reason_and_code_and_logs_only_the_applescript_error_number(self) -> None:
        stderr = f"osascript: execution error: {TEXT.message} {TEXT.title} 를 처리하지 못했습니다 (-1728)\n{TEXT.subtitle}"
        result, _, logged = self._send(return_value=_completed(1, stderr.encode("utf-8")))
        self.assertEqual(result, ("exit_nonzero", 1))
        self.assertIn("-1728", logged)

    def test_logged_failure_never_contains_notification_text_from_stderr(self) -> None:
        """S2 — osascript 오류문은 argv 피연산자를 인용한다. 문구가 섞인 stderr 의 어느 조각도 server.log 에 남지 않는다."""
        secret_words = (TEXT.title, TEXT.subtitle, TEXT.message)
        for stderr in (f"error: {TEXT.message}", f"{TEXT.title} {TEXT.subtitle} (-50) {TEXT.message}", "x" * 500 + TEXT.message):
            with self.subTest(stderr=stderr[:20]):
                _, _, logged = self._send(return_value=_completed(2, stderr.encode("utf-8")))
                for word in secret_words:
                    self.assertNotIn(word, logged)

    def test_stderr_without_an_error_number_logs_a_fixed_reason(self) -> None:
        _, _, logged = self._send(return_value=_completed(2, TEXT.message.encode("utf-8")))
        self.assertIn(hub_notify_send.NO_ERROR_NUMBER_LOG, logged)

    def test_lone_surrogate_in_argv_is_reported_as_invalid_text_without_raising(self) -> None:
        """S3 — 고립 서로게이트는 subprocess 가 UnicodeEncodeError(OSError 아님)를 내는 입력이다. 정제를 우회한 값이 와도 배치가 죽지 않는다."""
        result, _, logged = self._send(side_effect=UnicodeEncodeError("utf-8", "\ud800", 0, 1, "surrogates not allowed"))
        self.assertEqual(result, ("invalid_text", None))
        self.assertIn("invalid_text", logged)

    def test_embedded_null_byte_is_reported_as_invalid_text(self) -> None:
        result, _, _ = self._send(side_effect=ValueError("embedded null byte"))
        self.assertEqual(result, ("invalid_text", None))

    def test_undecodable_stderr_does_not_raise(self) -> None:
        result, _, _ = self._send(return_value=_completed(1, b"\xff\xfe bad"))
        self.assertEqual(result, ("exit_nonzero", 1))

    def test_timeout_is_reported(self) -> None:
        result, _, logged = self._send(side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=10))
        self.assertEqual(result, ("timeout", None))
        self.assertIn("timeout", logged)

    def test_missing_osascript_is_reported(self) -> None:
        result, _, _ = self._send(side_effect=FileNotFoundError("osascript"))
        self.assertEqual(result, ("osascript_missing", None))


class StatusFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.status_path = Path(self._temp.name) / "hub" / "notify_status.json"
        patcher = mock.patch.object(hub_notify_send, "NOTIFY_STATUS_PATH", self.status_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _record(self, **fields) -> hub_notify.NotifyStatusRecord:
        values = dict(active_since_ms=BASE_MS, last_attempt_at_ms=None, last_success_at_ms=None,
                      last_failure_reason=None, last_failure_exit_code=None)
        values.update(fields)
        return hub_notify.NotifyStatusRecord(**values)

    def test_write_then_read_round_trips_and_creates_the_directory(self) -> None:
        record = self._record(last_attempt_at_ms=BASE_MS + 1, last_failure_reason="exit_nonzero", last_failure_exit_code=1)
        hub_notify_send.write_notify_status(record)
        self.assertEqual(hub_notify_send.read_notify_status(), record)

    def test_file_holds_no_notification_text(self) -> None:
        hub_notify_send.write_notify_status(self._record())
        self.assertEqual(set(json.loads(self.status_path.read_text(encoding="utf-8"))),
                         {"active_since_ms", "last_attempt_at_ms", "last_success_at_ms", "last_failure_reason", "last_failure_exit_code"})

    def test_missing_file_reads_as_none(self) -> None:
        self.assertIsNone(hub_notify_send.read_notify_status())

    def test_broken_json_reads_as_none(self) -> None:
        self.status_path.parent.mkdir(parents=True)
        self.status_path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(hub_notify_send.read_notify_status())

    def test_wrong_field_types_read_as_none(self) -> None:
        self.status_path.parent.mkdir(parents=True)
        self.status_path.write_text(json.dumps({"active_since_ms": "yesterday"}), encoding="utf-8")
        self.assertIsNone(hub_notify_send.read_notify_status())

    def test_invalid_text_reason_round_trips(self) -> None:
        record = hub_notify.NotifyStatusRecord(BASE_MS, BASE_MS, None, "invalid_text", None)
        hub_notify_send.write_notify_status(record)
        self.assertEqual(hub_notify_send.read_notify_status(), record)

    def test_unknown_failure_reason_reads_as_none(self) -> None:
        self.status_path.parent.mkdir(parents=True)
        payload = {"active_since_ms": 1, "last_attempt_at_ms": None, "last_success_at_ms": None,
                   "last_failure_reason": "made_up", "last_failure_exit_code": None}
        self.status_path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertIsNone(hub_notify_send.read_notify_status())


class DeliverNotificationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.status_path = Path(self._temp.name) / "notify_status.json"
        patcher = mock.patch.object(hub_notify_send, "NOTIFY_STATUS_PATH", self.status_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_failure_among_two_sends_records_once_with_the_failure(self) -> None:
        with mock.patch.object(hub_notify_send, "send_notification", side_effect=[(None, 0), ("exit_nonzero", 1)]) as send_mock, \
                mock.patch.object(hub_notify_send, "write_notify_status", wraps=hub_notify_send.write_notify_status) as write_mock:
            hub_notify_send.deliver_notifications((TEXT, TEXT), BASE_MS)
        self.assertEqual(send_mock.call_count, 2)
        write_mock.assert_called_once()
        record = hub_notify_send.read_notify_status()
        self.assertEqual((record.last_attempt_at_ms, record.last_failure_reason, record.last_failure_exit_code),
                         (BASE_MS, "exit_nonzero", 1))

    def test_all_success_records_success(self) -> None:
        with mock.patch.object(hub_notify_send, "send_notification", return_value=(None, 0)):
            hub_notify_send.deliver_notifications((TEXT,), BASE_MS)
        record = hub_notify_send.read_notify_status()
        self.assertEqual((record.last_success_at_ms, record.last_failure_reason), (BASE_MS, None))

    def test_active_since_written_at_startup_survives_a_batch(self) -> None:
        hub_notify_send.write_notify_status(hub_notify.NotifyStatusRecord(BASE_MS - 5, None, None, None, None))
        with mock.patch.object(hub_notify_send, "send_notification", return_value=(None, 0)):
            hub_notify_send.deliver_notifications((TEXT,), BASE_MS)
        self.assertEqual(hub_notify_send.read_notify_status().active_since_ms, BASE_MS - 5)

    def test_status_write_failure_is_absorbed_into_one_stderr_line(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(hub_notify_send, "send_notification", return_value=(None, 0)), \
                mock.patch.object(hub_notify_send, "write_notify_status", side_effect=OSError("disk full")), \
                redirect_stderr(stderr):
            hub_notify_send.deliver_notifications((TEXT,), BASE_MS)
        self.assertEqual(len(stderr.getvalue().strip().splitlines()), 1)
        self.assertIn("disk full", stderr.getvalue())

    def test_invalid_text_in_one_notification_does_not_drop_the_rest_of_the_batch(self) -> None:
        with mock.patch.object(hub_notify_send, "send_notification", side_effect=[("invalid_text", None), (None, 0)]) as send_mock:
            hub_notify_send.deliver_notifications((TEXT, TEXT), BASE_MS)
        self.assertEqual(send_mock.call_count, 2)
        record = hub_notify_send.read_notify_status()
        self.assertEqual((record.last_attempt_at_ms, record.last_failure_reason), (BASE_MS, "invalid_text"))

    def test_unexpected_exception_never_escapes(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(hub_notify_send, "send_notification", side_effect=RuntimeError("boom")), redirect_stderr(stderr):
            hub_notify_send.deliver_notifications((TEXT,), BASE_MS)
        self.assertIn("boom", stderr.getvalue())


class DispatchInBackgroundTest(unittest.TestCase):
    def test_runs_deliver_on_a_named_daemon_thread_and_returns_at_once(self) -> None:
        seen = {}
        finished = threading.Event()

        def fake_deliver(texts, now_ms) -> None:
            seen["thread"] = threading.current_thread()
            seen["args"] = (texts, now_ms)
            finished.set()

        with mock.patch.object(hub_notify_send, "deliver_notifications", side_effect=fake_deliver):
            self.assertIsNone(hub_notify_send.dispatch_in_background((TEXT,), BASE_MS))
            self.assertTrue(finished.wait(timeout=5))
        self.assertEqual(seen["args"], ((TEXT,), BASE_MS))
        self.assertTrue(seen["thread"].daemon)
        self.assertIsNot(seen["thread"], threading.main_thread())


class ActivitySignatureTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.events_dir = Path(self._temp.name) / "events"
        self.sessions_dir = Path(self._temp.name) / "sessions"
        self.events_dir.mkdir()
        self.sessions_dir.mkdir()

    def _signature(self):
        return hub_notify_send.read_activity_signature((self.events_dir, self.sessions_dir))

    def test_append_to_an_event_file_changes_the_signature(self) -> None:
        event_file = self.events_dir / "2026-10-15.jsonl"
        event_file.write_text("{}\n", encoding="utf-8")
        before = self._signature()
        with event_file.open("a", encoding="utf-8") as handle:
            handle.write("{}\n")
        self.assertNotEqual(self._signature(), before)

    def test_new_roster_file_changes_the_signature(self) -> None:
        before = self._signature()
        (self.sessions_dir / "123.json").write_text("{}", encoding="utf-8")
        self.assertNotEqual(self._signature(), before)

    def test_key_files_are_ignored(self) -> None:
        before = self._signature()
        (self.sessions_dir / "123.key").write_text("secret", encoding="utf-8")
        self.assertEqual(self._signature(), before)

    def test_unchanged_directories_give_equal_signatures(self) -> None:
        (self.sessions_dir / "1.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self._signature(), self._signature())

    def test_missing_directory_is_empty_and_does_not_raise(self) -> None:
        missing = Path(self._temp.name) / "nope"
        self.assertEqual(hub_notify_send.read_activity_signature((missing,)), frozenset())

    def test_entries_name_the_directory_so_same_file_names_do_not_collide(self) -> None:
        (self.events_dir / "a.json").write_text("{}", encoding="utf-8")
        (self.sessions_dir / "a.json").write_text("{}", encoding="utf-8")
        self.assertEqual(len(self._signature()), 2)

    def test_entry_signature_is_none_for_a_vanished_file(self) -> None:
        class VanishedEntry:
            name = "1.json"

            def stat(self):
                raise FileNotFoundError(self.name)

        self.assertIsNone(hub_notify_send._entry_signature(Path("events"), VanishedEntry()))

    def test_file_vanishing_during_scan_is_skipped(self) -> None:
        (self.sessions_dir / "1.json").write_text("{}", encoding="utf-8")
        real_scandir = os.scandir

        class VanishingEntry:
            name = "2.json"

            def stat(self):
                raise FileNotFoundError(self.name)

        class FakeScandir:
            def __init__(self, path) -> None:
                self._real = real_scandir(path)

            def __enter__(self):
                return [*self._real.__enter__(), VanishingEntry()]

            def __exit__(self, *exc_info):
                return self._real.__exit__(*exc_info)

        with mock.patch.object(hub_notify_send.os, "scandir", FakeScandir):
            signature = self._signature()
        self.assertEqual({entry[1] for entry in signature}, {"1.json"})


class LocalClockLabelTest(unittest.TestCase):
    def setUp(self) -> None:
        previous = os.environ.get("TZ")
        os.environ["TZ"] = "Asia/Seoul"
        time.tzset()

        def restore() -> None:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()

        self.addCleanup(restore)

    @staticmethod
    def _epoch_ms(text: str) -> int:
        return int(time.mktime(time.strptime(text, "%Y-%m-%d %H:%M"))) * 1000

    def test_same_day_is_clock_only(self) -> None:
        now_ms = self._epoch_ms("2026-10-15 09:00")
        self.assertEqual(hub_notify_send.local_clock_label(self._epoch_ms("2026-10-15 14:05"), now_ms), "14:05")

    def test_other_day_includes_month_and_day(self) -> None:
        now_ms = self._epoch_ms("2026-10-15 23:00")
        self.assertEqual(hub_notify_send.local_clock_label(self._epoch_ms("2026-10-16 02:30"), now_ms), "10/16 02:30")


def _session(session_id: str, state: str, base_state: str, is_awaiting_approval: bool = False) -> hub_session.SessionView:
    return hub_session.SessionView(
        session_id=session_id, short_id=session_id, started_at_ms=BASE_MS, state=state, base_state=base_state,
        last_event_at_ms=BASE_MS, task_excerpt=None, agent_runs=(), is_awaiting_approval=is_awaiting_approval,
    )


def _snapshot(collected_at_ms: int, *sessions: hub_session.SessionView) -> hub_model.HubSnapshot:
    project = hub_project.ProjectView(
        display_name="proj", path="/repo/proj", tier=2, state="working", last_activity_at_ms=BASE_MS,
        sessions=sessions, tier1=None, note=None,
    )
    return hub_model.HubSnapshot(collected_at_ms=collected_at_ms, projects=(project,), unresolved_dir_names=(), warnings=())


class SessionNotifierTest(unittest.TestCase):
    T0 = BASE_MS

    def _notifier(self, include_task_title: bool = True):
        dispatched = []
        notifier = hub_notify_send.SessionNotifier(include_task_title, dispatch=lambda texts, now_ms: dispatched.append((texts, now_ms)))
        return notifier, dispatched

    def _working(self, at_ms: int):
        return _snapshot(at_ms, _session("s", "working", "working"))

    def _waiting(self, at_ms: int):
        """알림 국면은 승인 대기뿐이다(AN1) — 대기 세션에 승인 표지를 붙여 알림을 만든다."""
        return _snapshot(at_ms, _session("s", "idle", "idle", is_awaiting_approval=True))

    def test_first_observation_dispatches_nothing_even_for_a_waiting_session(self) -> None:
        notifier, dispatched = self._notifier()
        notifier.observe(self._waiting(self.T0))
        self.assertEqual(dispatched, [])

    def test_transition_then_confirmation_dispatches_once(self) -> None:
        notifier, dispatched = self._notifier()
        notifier.observe(self._working(self.T0))
        notifier.observe(self._waiting(self.T0 + 5 * MINUTE_MS))
        self.assertEqual(dispatched, [])
        self.assertTrue(notifier.has_pending())
        notifier.observe(self._waiting(self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS))
        self.assertEqual(len(dispatched), 1)
        texts, now_ms = dispatched[0]
        self.assertEqual((texts[0].title, now_ms), ("◆ 승인 대기 · proj", self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS))
        self.assertFalse(notifier.has_pending())

    def test_same_snapshot_repeated_dispatches_nothing_more(self) -> None:
        notifier, dispatched = self._notifier()
        notifier.observe(self._working(self.T0))
        notifier.observe(self._waiting(self.T0 + 5 * MINUTE_MS))
        for index in range(1, 5):
            notifier.observe(self._waiting(self.T0 + 5 * MINUTE_MS + index * hub_notify.NOTIFY_SETTLE_MS))
        self.assertEqual(len(dispatched), 1)

    def test_no_confirmed_event_never_calls_dispatch(self) -> None:
        notifier, dispatched = self._notifier()
        for index in range(3):
            notifier.observe(self._working(self.T0 + index * MINUTE_MS))
        self.assertEqual(dispatched, [])
        self.assertFalse(notifier.has_pending())

    def test_has_pending_is_false_before_any_observation(self) -> None:
        notifier, _ = self._notifier()
        self.assertFalse(notifier.has_pending())

    def test_include_task_title_flag_reaches_the_text(self) -> None:
        tier1 = hub_parse.Tier1Snapshot(
            title="비공개 제목", subtitle="", completed=0, total=1, percent=0, steps=(), matrix_done=None,
            impl_done=0, impl_total=0, updated_text="-", file_mtime_ms=BASE_MS,
        )
        waiting_with_title = _snapshot(0, _session("s", "idle", "idle", is_awaiting_approval=True))
        for include, expected_subtitle in ((True, "비공개 제목"), (False, "")):
            with self.subTest(include=include):
                notifier, dispatched = self._notifier(include_task_title=include)
                notifier.observe(self._working(self.T0))
                titled = dataclasses.replace(waiting_with_title.projects[0].sessions[0], tier1=tier1)
                for offset in (5 * MINUTE_MS, 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS):
                    notifier.observe(_snapshot(self.T0 + offset, titled))
                self.assertEqual(dispatched[0][0][0].subtitle, expected_subtitle)

    def test_default_dispatch_hands_the_batch_to_the_background_sender(self) -> None:
        """공개 동작으로 확인한다 — 기본 dispatch 는 전송 스레드를 거쳐 deliver_notifications 에 문구와 수집 시각을 넘긴다."""
        delivered = threading.Event()
        received = {}

        def fake_deliver(texts, now_ms) -> None:
            received["batch"] = (texts, now_ms)
            delivered.set()

        notifier = hub_notify_send.SessionNotifier(True)
        confirmed_at_ms = self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS
        with mock.patch.object(hub_notify_send, "deliver_notifications", side_effect=fake_deliver):
            notifier.observe(self._working(self.T0))
            notifier.observe(self._waiting(self.T0 + 5 * MINUTE_MS))
            notifier.observe(self._waiting(confirmed_at_ms))
            self.assertTrue(delivered.wait(timeout=5))
        texts, now_ms = received["batch"]
        self.assertEqual((texts[0].title, now_ms), ("◆ 승인 대기 · proj", confirmed_at_ms))


class IsNotifySupportedTest(unittest.TestCase):
    def test_non_macos_is_unsupported(self) -> None:
        with mock.patch.object(hub_notify_send.sys, "platform", "linux"):
            self.assertFalse(hub_notify_send.is_notify_supported())

    def test_macos_without_osascript_is_unsupported(self) -> None:
        with mock.patch.object(hub_notify_send.sys, "platform", "darwin"), \
                mock.patch.object(hub_notify_send.hub_notify, "OSASCRIPT_PATH", "/nonexistent/osascript"):
            self.assertFalse(hub_notify_send.is_notify_supported())

    def test_macos_with_osascript_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_osascript = Path(directory) / "osascript"
            fake_osascript.write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.object(hub_notify_send.sys, "platform", "darwin"), \
                    mock.patch.object(hub_notify_send.hub_notify, "OSASCRIPT_PATH", str(fake_osascript)):
                self.assertTrue(hub_notify_send.is_notify_supported())


if __name__ == "__main__":
    unittest.main()
