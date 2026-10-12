"""사람 입력 시각을 작업 경계에 쓰는 변경의 단위 테스트.

배경: `UserPromptSubmit` 훅은 사람이 입력하지 않은 프롬프트(백그라운드 완료 알림·서브에이전트 보고)에도
발화한다. 그 훅 시각(`facts.last_prompt_at_ms`)을 끝난 작업의 경계(결정 RL8-(b)·(c))와 세션 줄 시작 시각
(결정 LM11)에 쓰면 알림 한 번에 경계가 앞으로 밀린다. 그래서 두 곳은 transcript 꼬리에서 읽은 마지막 사람
입력 시각(`SessionTail.last_human_prompt_at_ms`)을 쓴다. 오류 뒤 재개 판정은 훅 값을 그대로 쓴다.

픽스처는 전부 합성 값이다 — 프롬프트 본문은 읽지 않으므로 줄에 본문 자체가 없다."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_parse  # noqa: E402  (sys.path 조정 후 임포트)
import hub_project  # noqa: E402
import hub_session  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_transcript  # noqa: E402

STALE_AFTER_MS = 30 * 60 * 1000
BASE_TIME_MS = 1_786_000_000_000
ONE_MINUTE_MS = 60 * 1000

# 합성 시각(UTC) — epoch ms 는 아래 상수와 짝이다(테스트 첫 케이스가 짝을 검증한다)
HUMAN_TIMESTAMP = "2026-10-08T01:00:00.000Z"
HUMAN_TIMESTAMP_MS = 1791421200000
NOTIFICATION_TIMESTAMP = "2026-10-08T01:05:00.000Z"


def _user_line(origin_kind: str | None, timestamp: str | None = HUMAN_TIMESTAMP, **overrides) -> str:
    """origin.kind 와 시각만 가진 user 줄 — 본문(message)은 일부러 싣지 않는다."""
    payload: dict = {"type": "user"}
    if origin_kind is not None:
        payload["origin"] = {"kind": origin_kind}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    payload.update(overrides)
    return json.dumps(payload)


def _human_prompt_at_ms(*lines: str) -> int | None:
    return hub_transcript.parse_session_tail("\n".join(lines)).last_human_prompt_at_ms


class HumanPromptTimeFromTailTest(unittest.TestCase):
    """꼬리에서 마지막 사람 입력 줄의 시각만 읽는다(케이스 ①②⑦)."""

    def test_human_line_time_is_converted_to_epoch_ms(self) -> None:
        self.assertEqual(_human_prompt_at_ms(_user_line("human")), HUMAN_TIMESTAMP_MS)

    def test_later_non_human_lines_do_not_move_the_time(self) -> None:
        """① 사람 입력 뒤에 알림·peer·메타 줄이 와도 시각은 사람 입력의 것이다."""
        later_lines = (
            _user_line("task-notification", NOTIFICATION_TIMESTAMP),
            _user_line("peer", NOTIFICATION_TIMESTAMP),
            _user_line("human", NOTIFICATION_TIMESTAMP, isMeta=True),
        )
        self.assertEqual(_human_prompt_at_ms(_user_line("human"), *later_lines), HUMAN_TIMESTAMP_MS)

    def test_most_recent_human_line_wins_over_older_one(self) -> None:
        self.assertEqual(
            _human_prompt_at_ms(_user_line("human", HUMAN_TIMESTAMP), _user_line("human", NOTIFICATION_TIMESTAMP)),
            HUMAN_TIMESTAMP_MS + 5 * ONE_MINUTE_MS,
        )

    def test_scan_continues_past_model_and_last_prompt_lines_to_the_human_line(self) -> None:
        """모델·last-prompt 가 먼저 확정돼도 스캔이 끊기지 않고 더 앞의 사람 입력 줄에 닿는다(조기 종료 회귀 방지)."""
        assistant_line = json.dumps({"type": "assistant", "message": {"model": "claude-opus-5", "role": "assistant"}})
        last_prompt_line = json.dumps({"type": "last-prompt", "lastPrompt": "synthetic"})
        self.assertEqual(
            _human_prompt_at_ms(_user_line("human"), assistant_line, last_prompt_line), HUMAN_TIMESTAMP_MS
        )

    def test_only_non_human_lines_give_none(self) -> None:
        """② 비사람 입력만 있는 꼬리 — 사람 입력 시각을 모른다."""
        lines = (
            _user_line("task-notification"),
            _user_line("peer"),
            _user_line(None),
            _user_line("human", isMeta=True),
            _user_line("human", isSidechain=True),
            _user_line("human", isCompactSummary=True),
        )
        self.assertIsNone(_human_prompt_at_ms(*lines))

    def test_empty_tail_gives_none(self) -> None:
        self.assertIsNone(_human_prompt_at_ms(""))

    def test_broken_or_missing_timestamp_gives_none_without_raising(self) -> None:
        """⑦ 시각이 깨졌거나 없으면 None — 예외 없음(계약 B). 더 오래된 사람 줄로 물러나지 않는다."""
        broken_values = ("not-a-time", "", "2026-13-99T99:99:99Z", None)
        for broken in broken_values:
            with self.subTest(timestamp=broken):
                self.assertIsNone(
                    _human_prompt_at_ms(_user_line("human", HUMAN_TIMESTAMP), _user_line("human", broken))
                )

    def test_non_string_timestamp_gives_none_without_raising(self) -> None:
        for broken in (12345, ["2026-10-08T01:00:00Z"], {"a": 1}, True):
            with self.subTest(timestamp=broken):
                self.assertIsNone(_human_prompt_at_ms(_user_line("human", timestamp=broken)))

    def test_garbage_lines_around_the_human_line_are_ignored(self) -> None:
        garbage = ("{not json", "[1, 2, 3]", '"just a string"', "42", "null")
        self.assertEqual(
            _human_prompt_at_ms(garbage[0], _user_line("human"), *garbage[1:]), HUMAN_TIMESTAMP_MS
        )

    def test_human_line_without_message_body_is_enough(self) -> None:
        """시각만 읽는다 — message.content 가 없거나 이상해도 시각은 나온다(자유 텍스트를 읽지 않는다)."""
        for body in ({}, {"message": "plain string"}, {"message": {"content": 5}}):
            with self.subTest(body=body):
                self.assertEqual(_human_prompt_at_ms(_user_line("human", **body)), HUMAN_TIMESTAMP_MS)

    def test_other_parsed_fields_are_unchanged_by_the_new_field(self) -> None:
        tail = hub_transcript.parse_session_tail(_user_line("human"))
        self.assertIsNone(tail.model)
        self.assertIsNone(tail.turn_failure)

    def test_new_field_defaults_to_none_for_existing_constructor_calls(self) -> None:
        tail = hub_transcript.SessionTail(model=None, last_prompt=None)
        self.assertIsNone(tail.last_human_prompt_at_ms)


def _hook_event(hook_event_name: str, offset_ms: int = 0, **overrides) -> hub_session_facts.HookEvent:
    fields = {
        "received_at_ms": BASE_TIME_MS + offset_ms,
        "hook_event_name": hook_event_name,
        "session_id": "session-1",
        "cwd": "/repo/a",
        "source": None,
        "reason": None,
        "agent_id": None,
        "agent_type": None,
    }
    fields.update(overrides)
    return hub_session_facts.HookEvent(**fields)


def _facts(events) -> hub_session_facts.SessionFacts:
    return hub_session_facts.build_session_facts(events)["session-1"]


def _tier1(percent: int, task_started_at_ms: int | None) -> hub_parse.Tier1Snapshot:
    return hub_parse.Tier1Snapshot(
        title="t", subtitle="s", completed=1, total=2, percent=percent, steps=(),
        matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
        file_mtime_ms=BASE_TIME_MS, task_started_at_ms=task_started_at_ms,
    )


# 시나리오 시각(BASE 기준): 사람 지시 → 작업 시작(대시보드 init) → 서브에이전트 실행 → 완료 알림 훅
HUMAN_PROMPT_OFFSET_MS = 0
TASK_START_OFFSET_MS = 1 * ONE_MINUTE_MS
RUN_START_OFFSET_MS = 2 * ONE_MINUTE_MS
RUN_STOP_OFFSET_MS = 3 * ONE_MINUTE_MS
NOTIFICATION_OFFSET_MS = 10 * ONE_MINUTE_MS


def _facts_with_notification_after_run() -> hub_session_facts.SessionFacts:
    """사람 지시 훅 → 실행 1건(종료) → 알림이 일으킨 훅. 훅의 last_prompt_at_ms 는 알림 시각이다."""
    return _facts([
        _hook_event("UserPromptSubmit", HUMAN_PROMPT_OFFSET_MS),
        _hook_event("SubagentStart", RUN_START_OFFSET_MS, agent_id="agt-1", agent_type="implementer"),
        _hook_event("SubagentStop", RUN_STOP_OFFSET_MS, agent_id="agt-1", agent_type="implementer"),
        _hook_event("UserPromptSubmit", NOTIFICATION_OFFSET_MS),
    ])


def _view(facts, tier1=None, human_prompt_offset_ms=None, is_dashboard_enabled=True) -> hub_session.SessionView:
    human_prompt_at_ms = None if human_prompt_offset_ms is None else BASE_TIME_MS + human_prompt_offset_ms
    return hub_session.compute_session_view(
        facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, tier1=tier1,
        is_dashboard_enabled=is_dashboard_enabled, last_human_prompt_at_ms=human_prompt_at_ms,
    )


class FinishedTaskBoundaryTest(unittest.TestCase):
    """끝난 작업(percent 100)의 경계 — 알림 훅이 경계를 밀지 않는다(케이스 ③)."""

    def test_notification_hook_does_not_fold_the_just_finished_run(self) -> None:
        facts = _facts_with_notification_after_run()
        view = _view(facts, _tier1(100, BASE_TIME_MS + TASK_START_OFFSET_MS), HUMAN_PROMPT_OFFSET_MS)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [False])

    def test_boundary_is_the_task_start_when_human_prompt_is_older(self) -> None:
        facts = _facts_with_notification_after_run()
        view = _view(facts, _tier1(100, BASE_TIME_MS + TASK_START_OFFSET_MS), HUMAN_PROMPT_OFFSET_MS)
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + TASK_START_OFFSET_MS)

    def test_new_human_instruction_after_finish_still_folds_earlier_runs(self) -> None:
        """사람이 끝난 작업 뒤에 새로 지시하면(경계 b) 그 이전 실행은 이전 작업으로 접힌다 — 기존 의도 유지."""
        facts = _facts_with_notification_after_run()
        new_instruction_offset_ms = RUN_STOP_OFFSET_MS + ONE_MINUTE_MS
        view = _view(facts, _tier1(100, BASE_TIME_MS + TASK_START_OFFSET_MS), new_instruction_offset_ms)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [True])
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + new_instruction_offset_ms)

    def test_unknown_human_prompt_falls_back_to_the_task_start_not_the_hook(self) -> None:
        """꼬리에 사람 입력이 없으면(None) 훅 알림 시각이 아니라 작업 시작이 경계다."""
        facts = _facts_with_notification_after_run()
        view = _view(facts, _tier1(100, BASE_TIME_MS + TASK_START_OFFSET_MS), human_prompt_offset_ms=None)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [False])
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + TASK_START_OFFSET_MS)


class FallbackBoundaryTest(unittest.TestCase):
    """(c) 폴백(tier1 없음·대시보드 켬)과 대시보드 끈 세션(케이스 ④⑤)."""

    def test_fallback_boundary_ignores_notification_hook(self) -> None:
        facts = _facts_with_notification_after_run()
        view = _view(facts, tier1=None, human_prompt_offset_ms=HUMAN_PROMPT_OFFSET_MS)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [False])

    def test_fallback_boundary_uses_human_prompt_when_it_is_after_the_run(self) -> None:
        facts = _facts_with_notification_after_run()
        view = _view(facts, tier1=None, human_prompt_offset_ms=RUN_STOP_OFFSET_MS + ONE_MINUTE_MS)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [True])

    def test_fallback_without_human_prompt_hides_nothing(self) -> None:
        """RL4 페일오픈 — 사람 입력 시각을 모르면 경계가 없어 아무것도 숨기지 않는다(훅 시각으로 추측하지 않는다)."""
        facts = _facts_with_notification_after_run()
        view = _view(facts, tier1=None, human_prompt_offset_ms=None)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [False])
        self.assertIsNone(view.task_started_at_ms)

    def test_session_row_start_time_is_the_human_prompt_not_the_notification(self) -> None:
        """⑤ 세션 줄 시간의 시작이 알림 시각으로 바뀌지 않는다 — 대시보드 없음·끔 모두."""
        facts = _facts_with_notification_after_run()
        expected_ms = BASE_TIME_MS + HUMAN_PROMPT_OFFSET_MS
        for is_dashboard_enabled in (True, False):
            with self.subTest(is_dashboard_enabled=is_dashboard_enabled):
                view = _view(facts, None, HUMAN_PROMPT_OFFSET_MS, is_dashboard_enabled=is_dashboard_enabled)
                self.assertEqual(view.task_started_at_ms, expected_ms)

    def test_disabled_dashboard_hides_nothing_even_with_human_prompt(self) -> None:
        """RL10 — 대시보드를 껐으면 사람 입력이 있어도 실행 목록 경계는 없다."""
        facts = _facts_with_notification_after_run()
        view = _view(facts, None, RUN_STOP_OFFSET_MS + ONE_MINUTE_MS, is_dashboard_enabled=False)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [False])

    def test_running_task_boundary_is_unaffected(self) -> None:
        """(a) 진행 중 작업은 프롬프트를 쓰지 않는다."""
        facts = _facts_with_notification_after_run()
        view = _view(facts, _tier1(50, BASE_TIME_MS + TASK_START_OFFSET_MS), RUN_STOP_OFFSET_MS + ONE_MINUTE_MS)
        self.assertEqual([run.is_previous_task for run in view.agent_runs], [False])
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + TASK_START_OFFSET_MS)


class TurnResumedStillUsesHookPromptTest(unittest.TestCase):
    """⑥ 오류 뒤 재개 판정은 훅 값을 그대로 쓴다 — 비사람 입력도 턴을 되살리는 것이 맞다(회귀 방지)."""

    FAILED_AT_OFFSET_MS = 5 * ONE_MINUTE_MS

    def _failure(self) -> hub_transcript.TranscriptTurnFailure:
        return hub_transcript.TranscriptTurnFailure(
            error_kind="rate_limit", failed_at_ms=BASE_TIME_MS + self.FAILED_AT_OFFSET_MS, resets_at_ms=None
        )

    def test_hook_prompt_after_failure_resumes_even_without_human_prompt_time(self) -> None:
        facts = _facts([
            _hook_event("UserPromptSubmit", HUMAN_PROMPT_OFFSET_MS),
            _hook_event("UserPromptSubmit", NOTIFICATION_OFFSET_MS),
        ])
        self.assertIsNone(hub_session.effective_interruption(facts, self._failure()))

    def test_failure_after_last_hook_prompt_still_interrupts(self) -> None:
        facts = _facts([_hook_event("UserPromptSubmit", HUMAN_PROMPT_OFFSET_MS)])
        interruption = hub_session.effective_interruption(facts, self._failure())
        self.assertIsNotNone(interruption)

    def test_view_resumed_state_does_not_depend_on_human_prompt_time(self) -> None:
        facts = _facts([
            _hook_event("UserPromptSubmit", HUMAN_PROMPT_OFFSET_MS),
            _hook_event("UserPromptSubmit", NOTIFICATION_OFFSET_MS),
        ])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            transcript_turn_failure=self._failure(), last_human_prompt_at_ms=None,
        )
        self.assertIsNone(view.interruption)


class ComposeProjectViewsHumanPromptTest(unittest.TestCase):
    """수집 배선 — 꼬리의 사람 입력 시각이 compose_project_views 를 거쳐 경계까지 전달된다."""

    def _views(self, tail):
        facts = _facts_with_notification_after_run()
        return hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)}, tier3_last_activity_by_path={},
            now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id={} if tail is None else {"session-1": tail},
        )

    def _session_of(self, tail):
        return self._views(tail)[0].sessions[0]

    def test_human_prompt_time_from_tail_reaches_the_boundary(self) -> None:
        tail = hub_transcript.SessionTail(
            model=None, last_prompt=None, last_human_prompt_at_ms=BASE_TIME_MS + HUMAN_PROMPT_OFFSET_MS
        )
        session = self._session_of(tail)
        self.assertEqual([run.is_previous_task for run in session.agent_runs], [False])
        self.assertEqual(session.task_started_at_ms, BASE_TIME_MS + HUMAN_PROMPT_OFFSET_MS)

    def test_later_human_prompt_folds_earlier_run(self) -> None:
        tail = hub_transcript.SessionTail(
            model=None, last_prompt=None, last_human_prompt_at_ms=BASE_TIME_MS + RUN_STOP_OFFSET_MS + ONE_MINUTE_MS
        )
        self.assertEqual([run.is_previous_task for run in self._session_of(tail).agent_runs], [True])

    def test_missing_tail_hides_nothing(self) -> None:
        session = self._session_of(None)
        self.assertEqual([run.is_previous_task for run in session.agent_runs], [False])
        self.assertIsNone(session.task_started_at_ms)

    def test_tail_without_human_prompt_hides_nothing(self) -> None:
        session = self._session_of(hub_transcript.SessionTail(model=None, last_prompt=None))
        self.assertEqual([run.is_previous_task for run in session.agent_runs], [False])


if __name__ == "__main__":
    unittest.main()
