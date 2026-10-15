"""hub_notify 단위 테스트(★순수 — 시계를 패치하지 않고 now_ms 를 인자로 넘긴다).
docs/prps/hub-macos-notification.md §9.1, 결정 MN1~MN4·MN7~MN9·MN11."""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)
import hub_notify  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_session  # noqa: E402

BASE_MS = 1_786_000_000_000
MINUTE_MS = 60_000
SECOND_MS = 1_000


def _observation(phase: str, session_id: str = "s1", project: str = "proj", **fields) -> hub_notify.SessionObservation:
    values = {
        "session_id": session_id, "phase": phase, "project_name": project,
        "task_title": None, "resets_at_ms": None, "background_task_count": 0,
    }
    values.update(fields)
    return hub_notify.SessionObservation(**values)


def _step(previous, phase: str, now_ms: int, **fields):
    """추적 1칸 전진 — (새 추적, 알림 또는 None)."""
    return hub_notify.advance_session_track(previous, _observation(phase, **fields), now_ms)


def _run(steps):
    """(phase, now_ms) 열을 차례로 먹여 (마지막 추적, 알림 목록)을 돌려준다."""
    track, events = None, []
    for phase, now_ms in steps:
        track, event = _step(track, phase, now_ms)
        if event is not None:
            events.append(event)
    return track, events


def _tier1(title: str = "작업", is_approval_step_active: bool = False) -> hub_parse.Tier1Snapshot:
    return hub_parse.Tier1Snapshot(
        title=title, subtitle="", completed=1, total=4, percent=25, steps=(),
        matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
        file_mtime_ms=BASE_MS, is_approval_step_active=is_approval_step_active,
    )


def _session(session_id: str, state: str, base_state: str, **fields) -> hub_session.SessionView:
    values = dict(
        session_id=session_id, short_id=session_id, started_at_ms=BASE_MS, state=state, base_state=base_state,
        last_event_at_ms=BASE_MS, task_excerpt=None, agent_runs=(),
    )
    values.update(fields)
    return hub_session.SessionView(**values)


def _snapshot(*projects: hub_project.ProjectView) -> hub_model.HubSnapshot:
    return hub_model.HubSnapshot(collected_at_ms=BASE_MS, projects=projects, unresolved_dir_names=(), warnings=())


def _project(name: str, *sessions: hub_session.SessionView) -> hub_project.ProjectView:
    return hub_project.ProjectView(
        display_name=name, path=f"/repo/{name}", tier=2, state="working", last_activity_at_ms=BASE_MS,
        sessions=sessions, tier1=None, note=None,
    )


def _event(kind: str, project: str = "proj", **fields) -> hub_notify.NotifyEvent:
    values = dict(kind=kind, project_name=project, task_title=None, busy_duration_ms=5 * MINUTE_MS,
                  resets_at_ms=None, background_task_count=0)
    values.update(fields)
    return hub_notify.NotifyEvent(**values)


def _clock(epoch_ms: int) -> str:
    return f"CLOCK{epoch_ms}"


class NotifyPhaseTest(unittest.TestCase):
    """MN1 표 — 위에서부터 먼저 맞는 것."""

    def _phase(self, state: str, base_state: str, **fields) -> str:
        return hub_notify.notify_phase(_session("s", state, base_state, **fields))

    def test_finished_session_is_done_phase(self) -> None:
        self.assertEqual(self._phase("done", "done"), "done")

    def test_rate_limit_stop_is_interrupted_phase(self) -> None:
        self.assertEqual(self._phase("interrupted", "idle"), "interrupted")

    def test_idle_session_with_approval_flag_is_awaiting_approval(self) -> None:
        self.assertEqual(self._phase("idle", "idle", is_awaiting_approval=True), "awaiting_approval")

    def test_approval_flag_wins_over_background_wait(self) -> None:
        self.assertEqual(self._phase("background", "idle", is_awaiting_approval=True), "awaiting_approval")

    def test_background_wait_without_approval_is_background_phase(self) -> None:
        self.assertEqual(self._phase("background", "idle"), "background")

    def test_silent_session_that_was_working_stays_working(self) -> None:
        self.assertEqual(self._phase("stale", "working"), "working")

    def test_silent_session_that_was_idle_is_waiting(self) -> None:
        self.assertEqual(self._phase("stale", "idle"), "waiting")

    def test_idle_session_is_waiting_phase(self) -> None:
        self.assertEqual(self._phase("idle", "idle"), "waiting")

    def test_running_turn_is_working_phase(self) -> None:
        self.assertEqual(self._phase("working", "working"), "working")

    def test_rate_limit_stop_wins_over_approval_flag(self) -> None:
        self.assertEqual(self._phase("interrupted", "idle", is_awaiting_approval=True), "interrupted")


class ObserveSessionsTest(unittest.TestCase):
    def test_empty_snapshot_has_no_observations(self) -> None:
        self.assertEqual(hub_notify.observe_sessions(_snapshot()), ())

    def test_flattens_projects_and_sessions_with_project_display_name(self) -> None:
        snapshot = _snapshot(
            _project("alpha", _session("a1", "working", "working"), _session("a2", "idle", "idle")),
            _project("beta", _session("b1", "done", "done")),
        )
        observations = hub_notify.observe_sessions(snapshot)
        self.assertEqual([(o.session_id, o.project_name, o.phase) for o in observations],
                         [("a1", "alpha", "working"), ("a2", "alpha", "waiting"), ("b1", "beta", "done")])

    def test_task_title_comes_from_tier1(self) -> None:
        snapshot = _snapshot(_project("p", _session("s", "idle", "idle", tier1=_tier1("설계 끝"))))
        self.assertEqual(hub_notify.observe_sessions(snapshot)[0].task_title, "설계 끝")

    def test_no_tier1_means_no_task_title(self) -> None:
        snapshot = _snapshot(_project("p", _session("s", "idle", "idle")))
        self.assertIsNone(hub_notify.observe_sessions(snapshot)[0].task_title)

    def test_interrupted_carries_reset_time_only_then(self) -> None:
        interruption = hub_session.SessionInterruption(interrupted_at_ms=BASE_MS, resets_at_ms=BASE_MS + 5 * MINUTE_MS)
        snapshot = _snapshot(_project("p", _session("s", "interrupted", "idle", interruption=interruption),
                                      _session("t", "idle", "idle")))
        first, second = hub_notify.observe_sessions(snapshot)
        self.assertEqual((first.resets_at_ms, second.resets_at_ms), (BASE_MS + 5 * MINUTE_MS, None))

    def test_background_carries_task_and_wakeup_count_only_then(self) -> None:
        wait = hub_session.BackgroundWait(since_ms=BASE_MS, until_ms=BASE_MS + MINUTE_MS, task_count=2, wakeup_count=1)
        snapshot = _snapshot(_project("p", _session("s", "background", "idle", background_wait=wait),
                                      _session("t", "idle", "idle")))
        first, second = hub_notify.observe_sessions(snapshot)
        self.assertEqual((first.background_task_count, second.background_task_count), (3, 0))


class SessionTrackTest(unittest.TestCase):
    """MN1~MN3·MN7 — 전이·확인 지연·바쁜 구간."""

    T0 = BASE_MS

    def test_first_observation_is_baseline_without_event(self) -> None:
        track, event = _step(None, "waiting", self.T0)
        self.assertIsNone(event)
        self.assertEqual((track.phase, track.busy_since_ms, track.pending), ("waiting", None, None))

    def test_first_observation_of_working_starts_the_busy_episode(self) -> None:
        track, _ = _step(None, "working", self.T0)
        self.assertEqual(track.busy_since_ms, self.T0)

    def test_working_to_waiting_confirms_after_settle(self) -> None:
        track, events = _run([
            ("working", self.T0),
            ("waiting", self.T0 + 5 * MINUTE_MS),
            ("waiting", self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS),
        ])
        self.assertEqual([(e.kind, e.busy_duration_ms) for e in events], [("turn_ended", 5 * MINUTE_MS)])
        self.assertIsNone(track.pending)

    def test_second_observation_only_makes_a_pending_candidate(self) -> None:
        _, events = _run([("working", self.T0), ("waiting", self.T0 + 5 * MINUTE_MS)])
        self.assertEqual(events, [])

    def test_settle_boundary(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        before = _run([("working", self.T0), ("waiting", self.T0 + 5 * MINUTE_MS),
                       ("waiting", self.T0 + 5 * MINUTE_MS + settle - 1)])[1]
        at = _run([("working", self.T0), ("waiting", self.T0 + 5 * MINUTE_MS),
                   ("waiting", self.T0 + 5 * MINUTE_MS + settle)])[1]
        self.assertEqual((len(before), len(at)), (0, 1))

    def test_unsettled_observation_keeps_the_same_candidate_clock(self) -> None:
        """확인 전 수집이 후보 시각을 밀지 않는다 — 3초는 처음 본 시각부터 잰다."""
        first_seen = self.T0 + 5 * MINUTE_MS
        _, events = _run([("working", self.T0), ("waiting", first_seen), ("waiting", first_seen + 2 * SECOND_MS),
                          ("waiting", first_seen + 3 * SECOND_MS)])
        self.assertEqual(len(events), 1)

    def test_return_to_working_before_confirmation_drops_the_candidate_and_keeps_busy_start(self) -> None:
        track, events = _run([("working", self.T0), ("waiting", self.T0 + 5 * MINUTE_MS),
                              ("working", self.T0 + 5 * MINUTE_MS + 5 * SECOND_MS)])
        self.assertEqual(events, [])
        self.assertEqual((track.phase, track.busy_since_ms, track.pending), ("working", self.T0, None))

    def test_busy_under_two_minutes_is_silent_and_resets_busy_start(self) -> None:
        track, events = _run([("working", self.T0), ("waiting", self.T0 + 2 * MINUTE_MS - SECOND_MS),
                              ("waiting", self.T0 + 2 * MINUTE_MS + 2 * SECOND_MS)])
        self.assertEqual(events, [])
        self.assertIsNone(track.busy_since_ms)

    def test_busy_exactly_two_minutes_notifies(self) -> None:
        _, events = _run([("working", self.T0), ("waiting", self.T0 + hub_notify.NOTIFY_MIN_BUSY_EPISODE_MS),
                          ("waiting", self.T0 + hub_notify.NOTIFY_MIN_BUSY_EPISODE_MS + hub_notify.NOTIFY_SETTLE_MS)])
        self.assertEqual(len(events), 1)

    def test_interrupted_notifies_even_when_short(self) -> None:
        _, events = _run([("working", self.T0), ("interrupted", self.T0 + 30 * SECOND_MS),
                          ("interrupted", self.T0 + 30 * SECOND_MS + hub_notify.NOTIFY_SETTLE_MS)])
        self.assertEqual([e.kind for e in events], ["interrupted"])

    def test_approval_wins_over_turn_ended(self) -> None:
        _, events = _run([("working", self.T0), ("awaiting_approval", self.T0 + 5 * MINUTE_MS),
                          ("awaiting_approval", self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS)])
        self.assertEqual([e.kind for e in events], ["awaiting_approval"])

    def test_approval_reentry_notifies_again_with_new_busy_length(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        first_end = self.T0 + 5 * MINUTE_MS
        back_to_work = first_end + 10 * SECOND_MS
        second_end = back_to_work + 4 * MINUTE_MS
        _, events = _run([
            ("working", self.T0), ("awaiting_approval", first_end), ("awaiting_approval", first_end + settle),
            ("working", back_to_work), ("awaiting_approval", second_end), ("awaiting_approval", second_end + settle),
        ])
        self.assertEqual([(e.kind, e.busy_duration_ms) for e in events],
                         [("awaiting_approval", 5 * MINUTE_MS), ("awaiting_approval", 4 * MINUTE_MS)])

    def test_busy_episode_survives_background_wait(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        t_bg = self.T0 + 10 * MINUTE_MS
        t_wake = t_bg + 5 * MINUTE_MS
        t_end = t_wake + MINUTE_MS
        _, events = _run([
            ("working", self.T0), ("background", t_bg), ("background", t_bg + settle),
            ("working", t_wake), ("waiting", t_end), ("waiting", t_end + settle),
        ])
        self.assertEqual([e.kind for e in events], ["background_wait", "turn_ended"])
        self.assertEqual(events[1].busy_duration_ms, 16 * MINUTE_MS)

    def test_background_to_waiting_is_silent(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        _, events = _run([("working", self.T0), ("background", self.T0 + 5 * MINUTE_MS),
                          ("background", self.T0 + 5 * MINUTE_MS + settle),
                          ("waiting", self.T0 + 95 * MINUTE_MS), ("waiting", self.T0 + 95 * MINUTE_MS + settle)])
        self.assertEqual([e.kind for e in events], ["background_wait"])

    def test_working_to_done_is_silent(self) -> None:
        _, events = _run([("working", self.T0), ("done", self.T0 + 5 * MINUTE_MS),
                          ("done", self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS)])
        self.assertEqual(events, [])

    def test_repeated_observations_after_confirmation_stay_silent(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        steps = [("working", self.T0), ("waiting", self.T0 + 5 * MINUTE_MS), ("waiting", self.T0 + 5 * MINUTE_MS + settle)]
        steps += [("waiting", self.T0 + 5 * MINUTE_MS + settle + index * 5 * SECOND_MS) for index in range(1, 4)]
        _, events = _run(steps)
        self.assertEqual(len(events), 1)

    def test_waiting_to_working_to_waiting_notifies_with_the_new_episode_only(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        start = self.T0 + 10 * MINUTE_MS
        end = start + 3 * MINUTE_MS
        _, events = _run([("waiting", self.T0), ("working", start), ("waiting", end), ("waiting", end + settle)])
        self.assertEqual([(e.kind, e.busy_duration_ms) for e in events], [("turn_ended", 3 * MINUTE_MS)])

    def _restart_scenario(self, phases_in_pending_window: list[str]):
        """working 5분 뒤 phases 를 1초 간격으로 넣고, 5초 간격 수집을 5번 더 한다 — 확인 대기 중 국면이 다른 알림 국면으로 바뀌는 재현(C1)."""
        steps = [("working", self.T0)]
        moment = self.T0 + 5 * MINUTE_MS
        for phase in phases_in_pending_window:
            steps.append((phase, moment))
            moment += SECOND_MS
        last_phase = phases_in_pending_window[-1]
        steps += [(last_phase, moment + index * 5 * SECOND_MS) for index in range(1, 6)]
        return _run(steps)

    def test_candidate_restarts_when_waiting_turns_into_background_wait(self) -> None:
        _, events = self._restart_scenario(["waiting", "background"])
        self.assertEqual([(e.kind, e.busy_duration_ms) for e in events], [("background_wait", 5 * MINUTE_MS + SECOND_MS)])

    def test_candidate_restarts_when_waiting_turns_into_awaiting_approval(self) -> None:
        _, events = self._restart_scenario(["waiting", "awaiting_approval"])
        self.assertEqual([e.kind for e in events], ["awaiting_approval"])

    def test_candidate_restarts_when_waiting_turns_into_interrupted(self) -> None:
        _, events = self._restart_scenario(["waiting", "interrupted"])
        self.assertEqual([e.kind for e in events], ["interrupted"])

    def test_restarted_candidate_replaces_the_earlier_one_so_one_transition_notifies_once(self) -> None:
        track, events = self._restart_scenario(["waiting", "awaiting_approval"])
        self.assertEqual(len(events), 1)
        self.assertIsNone(track.pending)

    def test_restarted_candidate_waits_for_its_own_settle_delay(self) -> None:
        first_seen = self.T0 + 5 * MINUTE_MS
        _, events = _run([("working", self.T0), ("waiting", first_seen), ("background", first_seen + SECOND_MS),
                          ("background", first_seen + SECOND_MS + hub_notify.NOTIFY_SETTLE_MS - 1)])
        self.assertEqual(events, [])

    def test_event_carries_the_confirming_observation_details(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        track, _ = _step(None, "working", self.T0)
        track, _ = _step(track, "background", self.T0 + 5 * MINUTE_MS, background_task_count=1)
        _, event = _step(track, "background", self.T0 + 5 * MINUTE_MS + settle,
                         project="proj-x", task_title="제목", background_task_count=2)
        self.assertEqual((event.project_name, event.task_title, event.background_task_count), ("proj-x", "제목", 2))

    def test_tracks_are_immutable_values(self) -> None:
        track, _ = _step(None, "working", self.T0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            track.phase = "waiting"  # type: ignore[misc]  # frozen dataclass 의 대입을 일부러 시도한다(타입 검사기가 막는 바로 그 동작)


class AdvanceTracksTest(unittest.TestCase):
    T0 = BASE_MS

    def test_first_collection_is_baseline_with_no_events(self) -> None:
        tracks, events = hub_notify.advance_tracks(
            None, [_observation("waiting", "a"), _observation("interrupted", "b")], self.T0)
        self.assertEqual((events, sorted(tracks)), ((), ["a", "b"]))

    def test_unseen_session_is_baseline_even_if_waiting_for_approval(self) -> None:
        tracks, _ = hub_notify.advance_tracks({}, [_observation("working", "a")], self.T0)
        later, events = hub_notify.advance_tracks(
            tracks, [_observation("working", "a"), _observation("awaiting_approval", "new")], self.T0 + MINUTE_MS)
        self.assertEqual((events, "new" in later), ((), True))

    def test_vanished_session_is_dropped(self) -> None:
        tracks, _ = hub_notify.advance_tracks(None, [_observation("working", "a"), _observation("working", "b")], self.T0)
        later, _ = hub_notify.advance_tracks(tracks, [_observation("working", "a")], self.T0 + SECOND_MS)
        self.assertEqual(sorted(later), ["a"])

    def test_empty_snapshot_clears_tracks(self) -> None:
        tracks, _ = hub_notify.advance_tracks(None, [_observation("working", "a")], self.T0)
        later, events = hub_notify.advance_tracks(tracks, [], self.T0 + SECOND_MS)
        self.assertEqual((dict(later), events), ({}, ()))

    def test_result_mapping_cannot_be_mutated(self) -> None:
        tracks, _ = hub_notify.advance_tracks(None, [_observation("working", "a")], self.T0)
        with self.assertRaises(TypeError):
            tracks["x"] = tracks["a"]  # type: ignore[index]  # 읽기 전용 매핑(MappingProxyType)에 대입해 TypeError 를 일부러 낸다

    def test_events_from_several_sessions_in_one_collection(self) -> None:
        settle = hub_notify.NOTIFY_SETTLE_MS
        names = ["a", "b"]
        tracks, _ = hub_notify.advance_tracks(None, [_observation("working", name) for name in names], self.T0)
        pending, _ = hub_notify.advance_tracks(
            tracks, [_observation("waiting", name) for name in names], self.T0 + 5 * MINUTE_MS)
        _, events = hub_notify.advance_tracks(
            pending, [_observation("waiting", name) for name in names], self.T0 + 5 * MINUTE_MS + settle)
        self.assertEqual(len(events), 2)

    def test_has_pending_reflects_candidates(self) -> None:
        tracks, _ = hub_notify.advance_tracks(None, [_observation("working", "a")], self.T0)
        self.assertFalse(hub_notify.has_pending(tracks))
        pending, _ = hub_notify.advance_tracks(tracks, [_observation("waiting", "a")], self.T0 + 5 * MINUTE_MS)
        self.assertTrue(hub_notify.has_pending(pending))
        settled, _ = hub_notify.advance_tracks(
            pending, [_observation("waiting", "a")], self.T0 + 5 * MINUTE_MS + hub_notify.NOTIFY_SETTLE_MS)
        self.assertFalse(hub_notify.has_pending(settled))


class DurationLabelTest(unittest.TestCase):
    def test_labels(self) -> None:
        cases = {2: "2분", 59: "59분", 60: "1시간", 65: "1시간 5분", 125: "2시간 5분"}
        for minutes, expected in cases.items():
            with self.subTest(minutes=minutes):
                self.assertEqual(hub_notify.duration_label(minutes * MINUTE_MS), expected)


class SanitizeNotificationTextTest(unittest.TestCase):
    def test_control_characters_become_single_spaces(self) -> None:
        self.assertEqual(hub_notify.sanitize_notification_text("a\n\tb\x00c\x7fd", 50), "a b c d")

    def test_collapses_runs_and_strips_ends(self) -> None:
        self.assertEqual(hub_notify.sanitize_notification_text("  a   b  ", 50), "a b")

    def test_over_limit_keeps_limit_chars_plus_ellipsis(self) -> None:
        self.assertEqual(hub_notify.sanitize_notification_text("가" * 10, 4), "가가가가…")

    def test_at_limit_is_unchanged(self) -> None:
        self.assertEqual(hub_notify.sanitize_notification_text("가" * 4, 4), "가가가가")

    def test_lone_surrogates_become_replacement_characters_and_encode_cleanly(self) -> None:
        cleaned = hub_notify.sanitize_notification_text("x\ud83dy\udc00z", 50)
        self.assertEqual(cleaned, "x\ufffdy\ufffdz")
        cleaned.encode("utf-8")

    def test_nul_never_survives(self) -> None:
        self.assertNotIn("\x00", hub_notify.sanitize_notification_text("x\x00" * 30, 20))

    def test_only_control_characters_gives_empty(self) -> None:
        self.assertEqual(hub_notify.sanitize_notification_text("\n\x00 \t", 10), "")


class ComposeNotificationsTest(unittest.TestCase):
    def _compose(self, events, include_task_title: bool = True):
        return hub_notify.compose_notifications(events, include_task_title, _clock)

    def test_turn_ended_text(self) -> None:
        (text,) = self._compose([_event("turn_ended", "alpha", task_title="설계 정리", busy_duration_ms=65 * MINUTE_MS)])
        self.assertEqual((text.title, text.subtitle, text.message),
                         ("○ 대기 · alpha", "설계 정리", "1시간 5분 작업을 마치고 입력을 기다립니다"))

    def test_approval_text(self) -> None:
        (text,) = self._compose([_event("awaiting_approval", "alpha", busy_duration_ms=23 * MINUTE_MS)])
        self.assertEqual((text.title, text.message), ("◆ 승인 대기 · alpha", "23분 작업 뒤 승인을 기다립니다"))

    def test_background_wait_text(self) -> None:
        (text,) = self._compose([_event("background_wait", "alpha", busy_duration_ms=23 * MINUTE_MS, background_task_count=2)])
        self.assertEqual((text.title, text.message),
                         ("◐ 백그라운드 대기 · alpha", "23분 작업 뒤 백그라운드 작업 2개를 기다립니다"))

    def test_interrupted_text_with_reset_time(self) -> None:
        (text,) = self._compose([_event("interrupted", "alpha", resets_at_ms=BASE_MS)])
        self.assertEqual((text.title, text.message),
                         ("■ 한도 초과 · alpha", f"사용량 한도로 멈췄습니다 · {_clock(BASE_MS)} 초기화 예정"))

    def test_interrupted_without_reset_time(self) -> None:
        (text,) = self._compose([_event("interrupted", "alpha", resets_at_ms=None)])
        self.assertEqual(text.message, "사용량 한도로 멈췄습니다")

    def test_task_title_off_gives_empty_subtitle(self) -> None:
        (text,) = self._compose([_event("turn_ended", task_title="비밀 작업")], include_task_title=False)
        self.assertEqual(text.subtitle, "")

    def test_missing_task_title_gives_empty_subtitle(self) -> None:
        (text,) = self._compose([_event("turn_ended", task_title=None)])
        self.assertEqual(text.subtitle, "")

    def test_task_title_is_masked_and_clipped_to_forty_chars(self) -> None:
        secret_title = "sk-ant-abcdefghijklmnopqrstuvwxyz 로 " + "가" * 60
        (text,) = self._compose([_event("turn_ended", task_title=secret_title)])
        self.assertIn("[REDACTED]", text.subtitle)
        self.assertNotIn("sk-ant", text.subtitle)
        self.assertEqual(len(text.subtitle), hub_notify.NOTIFY_TASK_TITLE_MAX_CHARS + 1)
        self.assertTrue(text.subtitle.endswith("…"))

    def test_leading_whitespace_cannot_push_a_token_fragment_past_the_scrub_window(self) -> None:
        """S1 — 공백 접기가 스크럽 창 자르기보다 먼저라, 앞 공백이 1,961자여도 토큰이 통째로 마스킹된다."""
        title = " " * 1961 + "ghp_" + "a" * 36
        (text,) = self._compose([_event("turn_ended", task_title=title)])
        self.assertEqual(text.subtitle, "[REDACTED]")
        self.assertNotIn("ghp_", text.subtitle)

    def test_title_longer_than_the_scrub_window_is_dropped_whole(self) -> None:
        """S1 — 창(NOTIFY_TASK_TITLE_SCRUB_INPUT_MAX_CHARS)을 넘는 제목은 자르지 않고 통째로 버린다(자른 경계의 시크릿 조각을 막는다)."""
        limit = hub_notify.NOTIFY_TASK_TITLE_SCRUB_INPUT_MAX_CHARS
        (over,) = self._compose([_event("turn_ended", task_title="가" * (limit + 1))])
        (at_limit,) = self._compose([_event("turn_ended", task_title="가" * limit)])
        self.assertEqual(over.subtitle, "")
        self.assertEqual(len(at_limit.subtitle), hub_notify.NOTIFY_TASK_TITLE_MAX_CHARS + 1)

    def test_secret_straddling_the_scrub_window_never_reaches_the_subtitle(self) -> None:
        """S1 — 긴 PEM 블록이 앞을 마스킹으로 줄여도, 창 경계에 걸린 토큰 조각이 부제 앞으로 오지 않는다."""
        title = "-----BEGIN PRIVATE KEY-----" + "A" * 1960 + " ghp_" + "b" * 36
        (text,) = self._compose([_event("turn_ended", task_title=title)])
        self.assertNotIn("ghp_", text.subtitle)

    def test_lone_surrogate_in_project_name_becomes_a_replacement_character(self) -> None:
        """S3 — 고립 서로게이트가 argv 로 가면 subprocess 가 UnicodeEncodeError 를 낸다."""
        (text,) = self._compose([_event("turn_ended", "a\ud800b")])
        self.assertEqual(text.title, "○ 대기 · a\ufffdb")
        text.title.encode("utf-8")

    def test_grouping_by_kind_with_deduplicated_project_list(self) -> None:
        texts = self._compose([
            _event("interrupted", "a"), _event("interrupted", "a"), _event("interrupted", "b"), _event("turn_ended", "c"),
        ])
        self.assertEqual([text.title for text in texts], ["■ 한도 초과 · 세션 3개", "○ 대기 · c"])
        self.assertEqual((texts[0].subtitle, texts[0].message), ("", "a · b"))

    def test_group_lists_three_projects_then_rest_count(self) -> None:
        events = [_event("turn_ended", f"p{index}") for index in range(1, 6)]
        (text,) = self._compose(events)
        self.assertEqual((text.title, text.message), ("○ 대기 · 세션 5개", "p1 · p2 · p3 외 2"))

    def test_output_order_follows_kind_order(self) -> None:
        texts = self._compose([_event("background_wait"), _event("turn_ended"), _event("awaiting_approval"), _event("interrupted")])
        self.assertEqual([text.title.split(" ")[1] for text in texts], ["한도", "승인", "대기", "백그라운드"])

    def test_no_events_gives_no_texts(self) -> None:
        self.assertEqual(self._compose([]), ())

    def test_long_project_name_is_clipped_in_title(self) -> None:
        (text,) = self._compose([_event("turn_ended", "긴" * 200)])
        self.assertLessEqual(len(text.title), hub_notify.NOTIFY_TITLE_MAX_CHARS + 1)

    def test_control_characters_in_project_name_are_sanitized(self) -> None:
        (text,) = self._compose([_event("turn_ended", "a\nb\x00c")])
        self.assertEqual(text.title, "○ 대기 · a b c")

    def test_labels_match_the_screen_vocabulary(self) -> None:
        self.assertEqual(
            dict(hub_notify.NOTIFY_TITLE_LABEL_BY_KIND),
            {"interrupted": "■ 한도 초과", "awaiting_approval": "◆ 승인 대기", "turn_ended": "○ 대기", "background_wait": "◐ 백그라운드 대기"},
        )


class OsascriptArgvTest(unittest.TestCase):
    FIXED_PREFIX_LENGTH = 8   # 경로 1 + (-e, 줄) 3쌍 6 + "--" 1

    def test_user_strings_only_follow_the_double_dash(self) -> None:
        hostile = hub_notify.NotificationText(title='-e', message='" & (do shell script "x") & "', subtitle="-- --")
        argv = hub_notify.osascript_argv(hostile)
        expected_prefix = (hub_notify.OSASCRIPT_PATH,) + tuple(
            part for line in hub_notify.NOTIFY_APPLESCRIPT_LINES for part in ("-e", line)) + ("--",)
        self.assertEqual(argv[:self.FIXED_PREFIX_LENGTH], expected_prefix)
        self.assertEqual(argv[self.FIXED_PREFIX_LENGTH:], (hostile.message, hostile.title, hostile.subtitle))

    def test_script_lines_hold_no_user_string_slot_for_formatting(self) -> None:
        script = "\n".join(hub_notify.NOTIFY_APPLESCRIPT_LINES)
        self.assertIn("on run argv", script)
        for forbidden in ("{", "%", "format("):
            self.assertNotIn(forbidden, script)

    def test_script_does_not_contain_the_user_text(self) -> None:
        text = hub_notify.NotificationText(title="TITLE-MARK", message="MESSAGE-MARK", subtitle="SUBTITLE-MARK")
        argv = hub_notify.osascript_argv(text)
        for part in argv[:self.FIXED_PREFIX_LENGTH]:
            self.assertNotIn("MARK", part)

    def test_message_title_subtitle_order_matches_the_script_item_numbers(self) -> None:
        text = hub_notify.NotificationText(title="T", message="M", subtitle="S")
        self.assertEqual(hub_notify.osascript_argv(text)[self.FIXED_PREFIX_LENGTH:], ("M", "T", "S"))


class NotifyStatusRecordTest(unittest.TestCase):
    def test_success_from_nothing(self) -> None:
        record = hub_notify.next_notify_status_record(None, BASE_MS, None, None)
        self.assertEqual(record, hub_notify.NotifyStatusRecord(
            active_since_ms=None, last_attempt_at_ms=BASE_MS, last_success_at_ms=BASE_MS,
            last_failure_reason=None, last_failure_exit_code=None))

    def test_failure_keeps_previous_success_and_records_reason(self) -> None:
        success = hub_notify.next_notify_status_record(None, BASE_MS, None, None)
        failed = hub_notify.next_notify_status_record(success, BASE_MS + 5, "exit_nonzero", 1)
        self.assertEqual((failed.last_attempt_at_ms, failed.last_success_at_ms, failed.last_failure_reason, failed.last_failure_exit_code),
                         (BASE_MS + 5, BASE_MS, "exit_nonzero", 1))

    def test_success_after_failure_clears_failure_fields(self) -> None:
        failed = hub_notify.next_notify_status_record(None, BASE_MS, "timeout", None)
        recovered = hub_notify.next_notify_status_record(failed, BASE_MS + 5, None, None)
        self.assertEqual((recovered.last_success_at_ms, recovered.last_failure_reason, recovered.last_failure_exit_code),
                         (BASE_MS + 5, None, None))

    def test_active_since_is_preserved(self) -> None:
        started = hub_notify.NotifyStatusRecord(active_since_ms=BASE_MS, last_attempt_at_ms=None, last_success_at_ms=None,
                                                last_failure_reason=None, last_failure_exit_code=None)
        self.assertEqual(hub_notify.next_notify_status_record(started, BASE_MS + 9, None, None).active_since_ms, BASE_MS)

    def test_previous_record_is_not_mutated(self) -> None:
        previous = hub_notify.next_notify_status_record(None, BASE_MS, None, None)
        hub_notify.next_notify_status_record(previous, BASE_MS + 1, "timeout", None)
        self.assertIsNone(previous.last_failure_reason)


class IsNotifierActiveTest(unittest.TestCase):
    @staticmethod
    def _record(active_since_ms):
        return hub_notify.NotifyStatusRecord(active_since_ms=active_since_ms, last_attempt_at_ms=None,
                                             last_success_at_ms=None, last_failure_reason=None, last_failure_exit_code=None)

    def test_no_record_is_false(self) -> None:
        self.assertFalse(hub_notify.is_notifier_active(None, BASE_MS))

    def test_record_older_than_server_is_false(self) -> None:
        self.assertFalse(hub_notify.is_notifier_active(self._record(BASE_MS - 1), BASE_MS))

    def test_record_at_or_after_server_start_is_true(self) -> None:
        self.assertTrue(hub_notify.is_notifier_active(self._record(BASE_MS), BASE_MS))
        self.assertTrue(hub_notify.is_notifier_active(self._record(BASE_MS + 1), BASE_MS))

    def test_no_server_is_false(self) -> None:
        self.assertFalse(hub_notify.is_notifier_active(self._record(BASE_MS), None))

    def test_record_without_active_since_is_false(self) -> None:
        self.assertFalse(hub_notify.is_notifier_active(self._record(None), BASE_MS))


if __name__ == "__main__":
    unittest.main()
