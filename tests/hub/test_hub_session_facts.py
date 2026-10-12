"""hub_session_facts 단위 테스트. docs/prps/hub-dashboard.md 「테스트 계획」 M5~M11(M1~M4 는
표시 판정 쪽이라 test_hub_session.py 에 남는다) — hub_session.py 의 입력·사실·필터·파싱·접기
절이 hub_session_facts.py 로 분리되며(결정 BW11, docs/prps/hub-subagent-background-pause.md,
M1 — 동작 불변) 이 클래스들도 그대로 이관됐다. `compute_session_view` 를 부르지 않는
접기 전용 테스트만 이 파일에 둔다(MS9 — 소스 1:테스트 1).

M2(결정 BW2·BW3) — `BackgroundReport` 파싱(`BackgroundReportParseTest`, P1~P9)·종류
정규화(`NormalizeBackgroundTaskTypeTest`, N1~N4)·BW3 접기(`BackgroundFoldTest`, F1~F11)를
더한다."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_session_facts  # noqa: E402  (sys.path 조정 후 임포트)

BASE_TIME_MS = 1_786_000_000_000


def _event(hook_event_name: str, offset_ms: int = 0, **overrides) -> hub_session_facts.HookEvent:
    fields = {
        "received_at_ms": BASE_TIME_MS + offset_ms,
        "hook_event_name": hook_event_name,
        "session_id": "session-1",
        "cwd": "/Users/dev/private/project/coding-harness",
        "source": None,
        "reason": None,
        "agent_id": None,
        "agent_type": None,
    }
    fields.update(overrides)
    return hub_session_facts.HookEvent(**fields)


def _facts_from(events):
    return hub_session_facts.build_session_facts(events)["session-1"]


class InternalEventFilterTest(unittest.TestCase):
    """M5~M7 — 내부 이벤트 필터와 안전판."""

    def test_m5_compact_session_start_is_recorded_for_freshness_but_not_tracked(self) -> None:
        """결정 PS3(docs/prps/hub-agent-runs-and-prompt-source.md) — 발췌가 transcript
        출처로 옮겨가며 `task_excerpt` 는 더 이상 `SessionFacts` 의 필드가 아니다(옛
        M5 테스트가 지키던 "compact 가 발췌를 안 건드린다"는 이제 지킬 대상 자체가 없다).
        여전히 유효한 성질만 남긴다 — compact SessionStart 는 내부 필터로 걸러져
        `_apply_tracked_event` 에 도달하지 못하지만(예: SessionEnd 로 인한 종료 해제가 없다),
        신선도 기록(last_event_name)은 필터 이전 단계에서 갱신된다.
        """
        events = [
            _event("UserPromptSubmit", 0),
            _event("SessionStart", 1000, source="compact"),
        ]
        facts = _facts_from(events)
        self.assertEqual(facts.last_event_name, "SessionStart")

    def test_m6_untracked_subagent_stop_creates_no_subagent(self) -> None:
        facts = _facts_from([_event("SubagentStop", agent_type="", agent_id="agt-1")])
        self.assertEqual(facts.subagents, ())

    def test_m7_tracked_subagent_stop_is_finalized(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 1000, agent_id="agt-1", agent_type=""),
        ]
        facts = _facts_from(events)
        self.assertEqual(len(facts.subagents), 1)
        self.assertIsNotNone(facts.subagents[0].ended_at_ms)


class SubagentTrackingTest(unittest.TestCase):
    """M8 — 같은 타입 두 개 동시 실행."""

    def test_m8_two_concurrent_same_type_tracked_independently(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 100, agent_id="agt-2", agent_type="implementer"),
            _event("SubagentStop", 200, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        by_id = {sub.agent_id: sub for sub in facts.subagents}
        self.assertIsNotNone(by_id["agt-1"].ended_at_ms)
        self.assertIsNone(by_id["agt-2"].ended_at_ms)


class SubagentResumeCountTest(unittest.TestCase):
    """결정 TF7(docs/prps/hub-agent-title-and-excerpt-freshness.md §9.2 F1~F4) — 같은 agent_id 의 SubagentStart 재발화 수가
    resume_count 다. 호스트는 SendMessage 로 재개할 때도 SubagentStart 를 같은 id 로 다시 낸다(훅 문서) — 새 훅 필드 없이 훅
    사실만으로 센다."""

    def test_f1_start_stop_start_counts_one_resume_and_reopens_the_run(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 1000, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 2000, agent_id="agt-1", agent_type="implementer"),
        ]

        subagent = _facts_from(events).subagents[0]

        self.assertEqual(subagent.resume_count, 1)
        self.assertEqual(subagent.started_at_ms, BASE_TIME_MS + 2000)   # 덮어쓰기 자체는 오늘과 같다 — 시작 = 마지막 재개
        self.assertIsNone(subagent.ended_at_ms)

    def test_f2_three_start_stop_cycles_count_two_resumes(self) -> None:
        events = []
        for cycle_index in range(3):
            events.append(_event("SubagentStart", cycle_index * 2000, agent_id="agt-1", agent_type="implementer"))
            events.append(_event("SubagentStop", cycle_index * 2000 + 1000, agent_id="agt-1", agent_type="implementer"))

        self.assertEqual(_facts_from(events).subagents[0].resume_count, 2)

    def test_f3_stop_that_implies_a_missed_start_counts_the_next_start_as_a_resume(self) -> None:
        """Start 없이 Stop(agent_type 있음)이 먼저 오면 합성 항목이 생긴다 — Stop 은 앞선 Start 를 뜻하므로 이어 온 Start 는 재개다."""
        events = [
            _event("SubagentStop", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 1000, agent_id="agt-1", agent_type="implementer"),
        ]

        subagent = _facts_from(events).subagents[0]

        self.assertEqual(subagent.resume_count, 1)
        self.assertIsNone(subagent.ended_at_ms)

    def test_first_start_and_a_run_that_was_never_resumed_count_zero(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 1000, agent_id="agt-1", agent_type="implementer"),
        ]

        self.assertEqual(_facts_from(events).subagents[0].resume_count, 0)

    def test_resume_counts_are_tracked_per_agent_id(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 100, agent_id="agt-2", agent_type="code-reviewer"),
            _event("SubagentStop", 200, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 300, agent_id="agt-1", agent_type="implementer"),
        ]

        counts = {sub.agent_id: sub.resume_count for sub in _facts_from(events).subagents}

        self.assertEqual(counts, {"agt-1": 1, "agt-2": 0})

    def test_f4_four_argument_construction_keeps_working_and_defaults_to_zero(self) -> None:
        """하위 호환 — 기존 생성 지점(테스트·합성 사실)이 넘기는 4인자만으로 만들어지고 resume_count 는 0 이다."""
        subagent = hub_session_facts.SubagentFact("agt-1", "implementer", BASE_TIME_MS, None)

        self.assertEqual(subagent.resume_count, 0)


class ObservedCwdsTest(unittest.TestCase):
    """U-28~U-29 — `SessionFacts.observed_cwds` 누적 규칙(결정 WT16·WT19,
    docs/prps/hub-worktree-fold.md)."""

    def test_u28_first_element_is_always_cwd_and_dedup_keeps_first_seen_order(self) -> None:
        """S13 — `observed_cwds[0] == cwd` 가 언제나 참이고, 중복 제거·첫 관측 순서가 지켜진다.
        세 번째 이벤트가 첫 번째 cwd 로 되돌아와도(루트 → 워크트리 → 루트) 그 값은 다시
        추가되지 않는다."""
        events = [
            _event("UserPromptSubmit", 0, cwd="/repo"),
            _event("UserPromptSubmit", 1000, cwd="/repo/.claude/worktrees/w"),
            _event("UserPromptSubmit", 2000, cwd="/repo"),
        ]
        facts = _facts_from(events)
        self.assertEqual(facts.cwd, facts.observed_cwds[0])
        self.assertEqual(facts.observed_cwds, ("/repo", "/repo/.claude/worktrees/w"))

    def test_u29_internally_filtered_event_still_contributes_its_cwd(self) -> None:
        """결정 WT19 — 누적 지점은 내부 이벤트 필터(compact 등)보다 앞이다. 필터에 걸려
        `_apply_tracked_event` 로 넘어가지 못하는 이벤트도 실제로 관측된 cwd 이므로 놓치면
        안 된다."""
        events = [
            _event("UserPromptSubmit", 0, cwd="/repo"),
            _event("SessionStart", 1000, source="compact", cwd="/repo/.claude/worktrees/w"),
        ]
        facts = _facts_from(events)
        self.assertIn("/repo/.claude/worktrees/w", facts.observed_cwds)


class LastPromptAtMsFieldTest(unittest.TestCase):
    """RL1(docs/prps/hub-card-gate-and-run-list-reset.md §3.1) —
    SessionFacts.last_prompt_at_ms 는 마지막 UserPromptSubmit 시각을 보존한다."""

    def test_build_session_facts_records_last_prompt_time(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit", 100), _event("UserPromptSubmit", 300)])
        self.assertEqual(facts.last_prompt_at_ms, BASE_TIME_MS + 300)

    def test_build_session_facts_last_prompt_none_without_prompt(self) -> None:
        facts = _facts_from([_event("SessionStart"), _event("Stop", 100)])
        self.assertIsNone(facts.last_prompt_at_ms)


class StopFailureFoldingTest(unittest.TestCase):
    """F1~F8 — docs/prps/hub-rate-limit-interruption.md 결정 RI1·RI4·RI7·RI11. StopFailure
    훅이 SessionFacts.failed_turn 으로 접히는 규칙."""

    def test_f1_stop_failure_after_prompt_submit_ends_turn_and_records_failed_turn(self) -> None:
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        self.assertEqual(facts.turn_state, "ended")
        self.assertEqual(facts.failed_turn, hub_session_facts.FailedTurn("rate_limit", BASE_TIME_MS + 1000))

    def test_f2_user_prompt_submit_clears_failed_turn(self) -> None:
        """RI4 — 「지운다」. 사용자가 다시 지시하면 원래 판정으로 돌아간다."""
        events = [
            _event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit"),
            _event("UserPromptSubmit", 2000),
        ]
        facts = _facts_from(events)
        self.assertIsNone(facts.failed_turn)
        self.assertEqual(facts.turn_state, "running")

    def test_f3_stop_clears_failed_turn(self) -> None:
        events = [
            _event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit"),
            _event("Stop", 2000),
        ]
        facts = _facts_from(events)
        self.assertIsNone(facts.failed_turn)

    def test_f4_session_start_preserves_failed_turn(self) -> None:
        """RI4 — resume 은 transcript 에 user 줄을 쓰지 않아 두 관측이 어긋나고, 대화의
        마지막 턴이 끊긴 채라는 것은 여전히 사실이다."""
        events = [
            _event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit"),
            _event("SessionStart", 2000, source="resume"),
        ]
        facts = _facts_from(events)
        self.assertEqual(facts.failed_turn, hub_session_facts.FailedTurn("rate_limit", BASE_TIME_MS + 1000))

    def test_f5_subagent_stop_failure_closes_only_that_execution(self) -> None:
        """RI11 — agent_id 가 있으면 메인 턴(turn_state·failed_turn)은 건드리지 않는다."""
        events = [
            _event("UserPromptSubmit", 0),
            _event("SubagentStart", 100, agent_id="agt-1", agent_type="implementer"),
            _event("StopFailure", 200, agent_id="agt-1", error_kind="rate_limit"),
        ]
        facts = _facts_from(events)
        self.assertEqual(facts.subagents[0].ended_at_ms, BASE_TIME_MS + 200)
        self.assertEqual(facts.turn_state, "running")
        self.assertIsNone(facts.failed_turn)

    def test_f6_stop_failure_with_unknown_agent_id_creates_no_execution(self) -> None:
        """RI11 — 모르는 id 는 무시한다(유령 실행 방지). last_event_at_ms 는 여전히 갱신된다
        (build_session_facts 의 필터 이전 단계에서 기록되므로)."""
        events = [_event("StopFailure", 0, agent_id="agt-unknown", error_kind="rate_limit")]
        facts = _facts_from(events)
        self.assertEqual(facts.subagents, ())
        self.assertEqual(facts.last_event_at_ms, BASE_TIME_MS)

    def test_f7_stop_failure_without_error_kind_defaults_to_unknown(self) -> None:
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000)]
        facts = _facts_from(events)
        self.assertEqual(facts.turn_state, "ended")
        self.assertEqual(facts.failed_turn.error_kind, "unknown")

    def test_f8_parse_event_line_reapplies_normalize_error_kind(self) -> None:
        """방어 재검증 — 이벤트 로그는 우리 파일이지만 옛 줄·찢긴 줄이 섞인다. 부재(키 없음)는
        "unknown" 으로 접지 않고 None 그대로 둔다 — _handle_stop_failure 가 그 구분으로
        기본값(UNKNOWN_ERROR_KIND)을 적용한다(F7)."""
        base = '{"t":1,"e":"StopFailure","s":"s1","c":"/repo"'
        good = hub_session_facts.parse_event_line(base + ',"er":"rate_limit"}')
        bad_shape = hub_session_facts.parse_event_line(base + ',"er":"Bad Text!"}')
        absent = hub_session_facts.parse_event_line(base + "}")
        self.assertEqual(good.error_kind, "rate_limit")
        self.assertEqual(bad_shape.error_kind, "unknown")
        self.assertIsNone(absent.error_kind)


class ParseEventLineTest(unittest.TestCase):
    """M11 — 깨진 JSON 줄 · 필드 누락 줄은 건너뛰고 나머지로 상태를 만든다."""

    def test_m11_broken_and_missing_field_lines_are_skipped(self) -> None:
        lines = [
            '{"t":1,"e":"SessionStart","s":"s1","c":"/repo"}',
            "not-json-at-all",
            '{"t":2,"e":"UserPromptSubmit"}',
            '{"t":3,"e":"Stop","s":"s1","c":"/repo"}',
        ]
        events = [event for event in (hub_session_facts.parse_event_line(line) for line in lines) if event]
        self.assertEqual(len(events), 2)
        facts = hub_session_facts.build_session_facts(events)["s1"]
        self.assertEqual(facts.last_event_name, "Stop")

    def test_rejects_invalid_or_out_of_range_t(self) -> None:
        """결함 수정(RI13 후속) — t 가 bool·문자열·실수·범위 밖 정수·자릿수 폭탄이면 None
        (키 부재도 같다). int() 변환을 더 이상 하지 않으므로 이 값들이 OverflowError·순수
        ValueError 로 수집 전체를 중단시키지 않는다."""
        base = '{"e":"Stop","s":"s1","c":"/repo"'
        invalid_t_literals = {
            "positive_infinity": "Infinity",
            "negative_infinity": "-Infinity",
            "nan": "NaN",
            "huge_float": "1e300",
            "huge_int_301_digits": str(10**300),
            "huge_int_5000_digits": "9" * 5000,
            "bool_true": "true",
            "bool_false": "false",
            "numeric_string": '"1786000000000"',
            "whole_number_float": "1786000000000.0",
            "fractional_float": "1786000000000.5",
            "negative": "-5",
            "zero": "0",
            "over_max": str(hub_session_facts.EVENT_TIME_MAX_MS + 1),
        }
        for label, t_literal in invalid_t_literals.items():
            with self.subTest(label=label):
                self.assertIsNone(hub_session_facts.parse_event_line(base + ',"t":' + t_literal + "}"))
        with self.subTest(label="missing_key"):
            self.assertIsNone(hub_session_facts.parse_event_line(base + "}"))

    def test_rejects_deeply_nested_payload_without_raising(self) -> None:
        """RecursionError — 깊게 중첩된 배열은 JSONDecodeError 가 아니라 이것을 던진다
        (hub_live_session.parse_live_session_record 와 같은 병리적 입력)."""
        nested_line = '{"t":1,"e":' + "[" * 5000 + "]" * 5000 + ',"s":"s1","c":"/repo"}'
        self.assertIsNone(hub_session_facts.parse_event_line(nested_line))
        self.assertIsNone(hub_session_facts.parse_event_line("[" * 100000))

    def test_accepts_valid_t_values_at_realistic_and_boundary_scale(self) -> None:
        base = '{"e":"Stop","s":"s1","c":"/repo"'
        valid_t_values = {"one": 1, "realistic": BASE_TIME_MS, "max_boundary": hub_session_facts.EVENT_TIME_MAX_MS}
        for label, t_value in valid_t_values.items():
            with self.subTest(label=label):
                event = hub_session_facts.parse_event_line(base + ',"t":' + str(t_value) + "}")
                self.assertIsNotNone(event)
                self.assertEqual(event.received_at_ms, t_value)

    def test_optional_fields_become_none_for_non_string_values(self) -> None:
        """ai·at·so·r 는 문자열일 때만 그대로, 아니면 None — 줄 자체는 살아 있다."""
        base = '{"t":1,"e":"SubagentStart","s":"s1","c":"/repo"'
        non_string_json_values = {"list": "[1]", "dict": '{"x":1}', "number": "1", "bool": "true"}
        for label, json_value in non_string_json_values.items():
            with self.subTest(label=label):
                event = hub_session_facts.parse_event_line(base + ',"ai":' + json_value + "}")
                self.assertIsNotNone(event)
                self.assertIsNone(event.agent_id)
        string_event = hub_session_facts.parse_event_line(base + ',"ai":"agt-1"}')
        self.assertEqual(string_event.agent_id, "agt-1")

    def test_subagent_start_with_list_agent_id_does_not_crash_build_session_facts(self) -> None:
        """실측 결함 — "ai":[1] 인 SubagentStart 가 known_agent_ids.add(agent_id) 에서
        TypeError: unhashable type: 'list' 로 수집 전체를 중단시켰다."""
        line = '{"t":1,"e":"SubagentStart","s":"s1","c":"/repo","ai":[1],"at":"implementer"}'
        event = hub_session_facts.parse_event_line(line)
        facts = hub_session_facts.build_session_facts([event])["s1"]
        self.assertEqual(facts.subagents[0].agent_id, "")


class BackgroundReportParseTest(unittest.TestCase):
    """P1~P9 — 결정 BW2. `_parse_background_report` 의 재검증 규칙(BackgroundReport 로
    접거나 통째로 버린다). P1 은 실제 이벤트 줄(`parse_event_line`)을 통과시켜 `bt`·`sw`
    가 `HookEvent.background_report` 까지 배선되는지도 함께 확인한다 — 나머지는 검증 규칙
    자체가 초점이라 `_parse_background_report` 를 직접 부른다(화이트박스, P4 의 "키가
    비문자열" 처럼 실제 JSON 텍스트로는 표현할 수 없는 입력도 다뤄야 하기 때문이다 — JSON
    객체 키는 언제나 문자열이라 이 방어선은 parse_event_line 경로에서는 도달 불가능하지만
    다른 생산자를 상정한 방어다)."""

    def test_p1_stop_line_wires_shell_two_through_parse_event_line(self) -> None:
        line = '{"t":' + str(BASE_TIME_MS) + ',"e":"Stop","s":"s1","c":"/repo","bt":{"shell":2},"sw":0}'
        event = hub_session_facts.parse_event_line(line)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.background_report,
            hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0),
        )

    def test_p2_no_keys_is_none(self) -> None:
        self.assertIsNone(hub_session_facts._parse_background_report({}, BASE_TIME_MS))

    def test_p3_empty_bt_is_a_valid_empty_report_not_none(self) -> None:
        """부재(P2)와 "빈 보고"(진행 중인 것 없음의 명시적 기록)를 구별한다."""
        report = hub_session_facts._parse_background_report({"bt": {}, "sw": 0}, BASE_TIME_MS)
        self.assertEqual(report, hub_session_facts.BackgroundReport(BASE_TIME_MS, (), 0))

    def test_p4_malformed_keys_are_rejected(self) -> None:
        malformed_keys = {
            "punctuation_and_space": "Bad Key!",
            "over_32_chars": "a" * 33,
            "non_string": 1,
        }
        for label, bad_key in malformed_keys.items():
            with self.subTest(label=label):
                payload = {"bt": {bad_key: 1}, "sw": 0}
                self.assertIsNone(hub_session_facts._parse_background_report(payload, BASE_TIME_MS))

    def test_p5_malformed_values_are_rejected(self) -> None:
        malformed_values = {"bool_true": True, "zero": 0, "negative": -1, "over_max": 1000, "float": 1.5, "numeric_string": "2"}
        for label, bad_value in malformed_values.items():
            with self.subTest(label=label):
                payload = {"bt": {"shell": bad_value}, "sw": 0}
                self.assertIsNone(hub_session_facts._parse_background_report(payload, BASE_TIME_MS))

    def test_p6_more_than_kind_max_distinct_keys_is_rejected(self) -> None:
        nine_kinds = {f"kind_{i}": 1 for i in range(9)}
        self.assertIsNone(hub_session_facts._parse_background_report({"bt": nine_kinds, "sw": 0}, BASE_TIME_MS))

    def test_p7_malformed_sw_is_rejected(self) -> None:
        malformed_sw_values = {"bool_true": True, "negative": -1, "over_max": 1000}
        for label, bad_sw in malformed_sw_values.items():
            with self.subTest(label=label):
                payload = {"bt": {"shell": 1}, "sw": bad_sw}
                self.assertIsNone(hub_session_facts._parse_background_report(payload, BASE_TIME_MS))

    def test_p8_bt_wrong_type_is_rejected(self) -> None:
        wrong_types = {"list": ["shell"], "str": "shell"}
        for label, bad_bt in wrong_types.items():
            with self.subTest(label=label):
                self.assertIsNone(hub_session_facts._parse_background_report({"bt": bad_bt, "sw": 0}, BASE_TIME_MS))

    def test_p9_task_counts_are_sorted_ascending_by_kind(self) -> None:
        """스냅샷 키 흔들림 방지(결정적) — 딱 삽입 순서와 반대로 넣어 정렬이 실제로
        일어나는지 확인한다."""
        report = hub_session_facts._parse_background_report({"bt": {"workflow": 1, "shell": 2}, "sw": 0}, BASE_TIME_MS)
        self.assertEqual(report.task_counts, (("shell", 2), ("workflow", 1)))


class NormalizeBackgroundTaskTypeTest(unittest.TestCase):
    """N1~N4 — `normalize_background_task_type`. 호스트 라벨을 닫힌 모양으로 접는다."""

    def test_n1_already_normalized_label_is_unchanged(self) -> None:
        self.assertEqual(hub_session_facts.normalize_background_task_type("shell"), "shell")

    def test_n2_space_becomes_underscore_and_lowercased(self) -> None:
        self.assertEqual(hub_session_facts.normalize_background_task_type("MCP task"), "mcp_task")

    def test_n3_hyphen_and_space_both_become_underscore(self) -> None:
        self.assertEqual(hub_session_facts.normalize_background_task_type("auto-mode scan"), "auto_mode_scan")

    def test_n4_shape_violations_become_unknown(self) -> None:
        shape_violations = {
            "empty_string": "", "none": None, "int": 5, "over_32_chars": "x" * 33,
            "non_ascii_letter": "셸", "slash": "a/b",
        }
        for label, bad_value in shape_violations.items():
            with self.subTest(label=label):
                self.assertEqual(
                    hub_session_facts.normalize_background_task_type(bad_value),
                    hub_session_facts.UNKNOWN_BACKGROUND_TASK_TYPE,
                )


class BackgroundFoldTest(unittest.TestCase):
    """F1~F11 — 결정 BW3. `_apply_tracked_event` 맨 앞 한 줄이 정하는 "지금 유효한 보고"
    규칙(BW3 표 전 행). `_event`(맨 위 헬퍼)에 `background_report` 오버라이드를 얹어
    이벤트를 직접 구성한다 — bt·sw 재검증 규칙은 위 BackgroundReportParseTest 가 이미
    다루므로 여기서는 BW3 접기 규칙만 본다."""

    def _report(self, reported_at_ms: int, shell_count: int = 2) -> hub_session_facts.BackgroundReport:
        return hub_session_facts.BackgroundReport(reported_at_ms, (("shell", shell_count),), 0)

    def test_f1_stop_with_report_is_kept(self) -> None:
        report = self._report(BASE_TIME_MS)
        facts = _facts_from([_event("Stop", 0, background_report=report)])
        self.assertEqual(facts.background_report, report)

    def test_f2_user_prompt_submit_after_stop_clears_report(self) -> None:
        events = [
            _event("Stop", 0, background_report=self._report(BASE_TIME_MS)),
            _event("UserPromptSubmit", 1000),
        ]
        self.assertIsNone(_facts_from(events).background_report)

    def test_f3_subagent_start_after_stop_clears_report(self) -> None:
        events = [
            _event("Stop", 0, background_report=self._report(BASE_TIME_MS)),
            _event("SubagentStart", 1000, agent_id="agt-1", agent_type="implementer"),
        ]
        self.assertIsNone(_facts_from(events).background_report)

    def test_f4_compact_session_start_does_not_clear_report(self) -> None:
        """필터된 내부 이벤트는 `_apply_tracked_event` 에 도달하지 못해 보고가 그대로
        남는다(BW3 표 "필터된 내부 이벤트" 행)."""
        report = self._report(BASE_TIME_MS)
        events = [_event("Stop", 0, background_report=report), _event("SessionStart", 1000, source="compact")]
        self.assertEqual(_facts_from(events).background_report, report)

    def test_f5_resume_session_start_clears_report(self) -> None:
        events = [
            _event("Stop", 0, background_report=self._report(BASE_TIME_MS)),
            _event("SessionStart", 1000, source="resume"),
        ]
        self.assertIsNone(_facts_from(events).background_report)

    def test_f6_untracked_internal_subagent_stop_does_not_clear_report(self) -> None:
        report = self._report(BASE_TIME_MS)
        events = [
            _event("Stop", 0, background_report=report),
            _event("SubagentStop", 1000, agent_type="", agent_id="agt-unknown"),
        ]
        self.assertEqual(_facts_from(events).background_report, report)

    def test_f7_tracked_subagent_stop_replaces_report_with_its_own(self) -> None:
        stop_report = self._report(BASE_TIME_MS, shell_count=1)
        subagent_stop_report = self._report(BASE_TIME_MS + 1000, shell_count=3)
        events = [
            _event("Stop", 0, background_report=stop_report),
            _event("SubagentStart", 500, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 1000, agent_id="agt-1", agent_type="implementer", background_report=subagent_stop_report),
        ]
        self.assertEqual(_facts_from(events).background_report, subagent_stop_report)

    def test_f8_stop_failure_clears_report_for_main_and_for_known_subagent(self) -> None:
        report = self._report(BASE_TIME_MS)
        main_events = [_event("Stop", 0, background_report=report), _event("StopFailure", 1000, error_kind="rate_limit")]
        self.assertIsNone(_facts_from(main_events).background_report)

        subagent_events = [
            _event("Stop", 0, background_report=report),
            _event("SubagentStart", 500, agent_id="agt-1", agent_type="implementer"),
            _event("StopFailure", 1000, agent_id="agt-1", error_kind="rate_limit"),
        ]
        self.assertIsNone(_facts_from(subagent_events).background_report)

    def test_f9_stop_without_keys_after_stop_with_report_clears_it(self) -> None:
        """옛 호스트(배열 부재) — Stop 이 다시 와도 보고가 없으면 지워진다(페일오픈)."""
        events = [
            _event("Stop", 0, background_report=self._report(BASE_TIME_MS)),
            _event("Stop", 1000),
        ]
        self.assertIsNone(_facts_from(events).background_report)

    def test_f10_session_end_clears_report(self) -> None:
        events = [_event("Stop", 0, background_report=self._report(BASE_TIME_MS)), _event("SessionEnd", 1000)]
        self.assertIsNone(_facts_from(events).background_report)

    def test_f11_unrelated_existing_folding_behavior_is_unaffected(self) -> None:
        """M1 이 이관한 기존 접기 테스트가 기대하는 그대로 — 이 필드 추가가 다른 필드의
        접기 규칙을 건드리지 않았음을 재확인한다(회귀 없음)."""
        events = [
            _event("UserPromptSubmit", 0, background_report=self._report(BASE_TIME_MS)),
            _event("Stop", 1000),
        ]
        facts = _facts_from(events)
        self.assertEqual(facts.turn_state, "ended")
        self.assertIsNone(facts.failed_turn)
        self.assertIsNone(facts.background_report)


if __name__ == "__main__":
    unittest.main()
