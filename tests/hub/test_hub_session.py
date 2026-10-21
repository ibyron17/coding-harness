"""hub_session 단위 테스트. docs/prps/hub-dashboard.md 「테스트 계획」 M1~M4(M5~M11 은
hub_session_facts.py 분리로 test_hub_session_facts.py 로 이관 — 결정 BW11,
docs/prps/hub-subagent-background-pause.md),
docs/prps/hub-zombie-subagent-guard.md 결정 ZG1~ZG7(테스트 ZG1~ZG15),
docs/prps/hub-session-revival-and-stale-tier1.md 결정 RV1~RV3(테스트 RV1~RV10),
docs/prps/hub-agent-runs-and-prompt-source.md 결정 AR1~AR11·PS3(서브에이전트 실행 단위 표시·
task_excerpt 인자화)."""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402  (sys.path 조정 후 임포트)
import hub_live_session  # noqa: E402
import hub_model  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_session  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_subagent  # noqa: E402
import hub_transcript  # noqa: E402
import hub_usage  # noqa: E402
import hub_workflow  # noqa: E402

STALE_AFTER_MS = 30 * 60 * 1000
BASE_TIME_MS = 1_786_000_000_000
MINUTE_MS = 60 * 1000


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


class SessionStateLadderTest(unittest.TestCase):
    """M1~M4 — 우선순위 사다리 + stale 오버레이."""

    def test_m1_prompt_submit_is_working(self) -> None:
        facts = _facts_from([_event("SessionStart"), _event("UserPromptSubmit", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "working")

    def test_m2_stop_is_idle(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "idle")

    def test_m3_ended_session_stays_done_after_two_hours(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", 1000)])
        two_hours_later = facts.last_event_at_ms + 2 * 60 * 60 * 1000
        view = hub_session.compute_session_view(facts, now_ms=two_hours_later, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")

    def test_m4_stale_overlay_preserves_base_state(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        thirty_one_minutes_later = facts.last_event_at_ms + 31 * 60 * 1000
        view = hub_session.compute_session_view(facts, now_ms=thirty_one_minutes_later, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "stale")
        self.assertEqual(view.base_state, "working")


class SessionIdentityTest(unittest.TestCase):
    """요구 3(세션 구분, docs/prps/hub-collect-on-demand-and-readability.md §4.6) —
    compute_session_view 가 facts.started_at_ms 를 뷰로 그대로 옮긴다."""

    def test_q3_started_at_ms_is_carried_from_facts_unchanged(self) -> None:
        facts = _facts_from([_event("SessionStart"), _event("UserPromptSubmit", 5000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.started_at_ms, facts.started_at_ms)

    def test_q3_started_at_ms_differs_from_last_event_at_ms_without_conflation(self) -> None:
        """시작 시각과 마지막 이벤트 시각이 다른 사실로, 뷰에서 둘이 섞이지 않는지 확인한다."""
        facts = _facts_from([_event("SessionStart", 0), _event("UserPromptSubmit", 90000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.started_at_ms, BASE_TIME_MS)
        self.assertEqual(view.last_event_at_ms, BASE_TIME_MS + 90000)
        self.assertNotEqual(view.started_at_ms, view.last_event_at_ms)


class SubagentZombieGuardTest(unittest.TestCase):
    """ZG1~ZG15 — docs/prps/hub-zombie-subagent-guard.md 결정 ZG1~ZG7.

    `SubagentStop` 을 못 본 서브에이전트가 나이(`now_ms - started_at_ms`)로 좀비 판정을 받는지,
    그리고 그 판정이 상태(`base_state`)와 칩(`is_running`)에 동시에 반영되는지를 검증한다.
    """

    ZOMBIE_AFTER_MS = 90 * 60 * 1000
    ONE_MINUTE_MS = 60 * 1000
    # stale 오버레이(30분)는 M4·RV7 이 이미 별도로 잠갔다. 이 클래스는 base_state·is_running 이
    # 나이만으로 어떻게 갈리는지를 보려는 것이라, 오버레이가 우연히 결과를 가리지 않도록 시나리오
    # 지속 시간(최대 약 3시간)보다 넉넉히 큰 stale_after_ms 를 쓴다(실측 E9 — 오버레이는 sticky
    # working 을 "부분적으로만" 구제하므로, 오버레이에 기대지 않는 경로를 따로 확인해야 한다).
    NO_OVERLAY_STALE_AFTER_MS = 24 * 60 * 60 * 1000

    def test_zg1_ended_subagent_is_never_running_regardless_of_age(self) -> None:
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer",
            started_at_ms=BASE_TIME_MS, ended_at_ms=BASE_TIME_MS + 1000,
        )
        self.assertFalse(
            hub_session.is_running_subagent(subagent, now_ms=BASE_TIME_MS + 2000, zombie_after_ms=self.ZOMBIE_AFTER_MS)
        )

    def test_zg2_age_one_ms_under_threshold_is_running(self) -> None:
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        now_ms = BASE_TIME_MS + self.ZOMBIE_AFTER_MS - 1
        self.assertTrue(hub_session.is_running_subagent(subagent, now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS))

    def test_zg3_age_exactly_threshold_is_zombie(self) -> None:
        """경계는 >= 가 좀비다(GOTCHA 5) — < 로 잘못 쓰면 이 테스트가 잡는다."""
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        now_ms = BASE_TIME_MS + self.ZOMBIE_AFTER_MS
        self.assertFalse(hub_session.is_running_subagent(subagent, now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS))

    def test_zg4_age_past_threshold_by_an_hour_is_zombie(self) -> None:
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        one_hour_ms = 60 * self.ONE_MINUTE_MS
        now_ms = BASE_TIME_MS + self.ZOMBIE_AFTER_MS + one_hour_ms
        self.assertFalse(hub_session.is_running_subagent(subagent, now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS))

    def test_zg5_negative_age_from_clock_skew_is_running(self) -> None:
        """X4 — now_ms < started_at_ms 이면 안전한 방향(실행 중)으로 본다."""
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        now_ms = BASE_TIME_MS - 1000
        self.assertTrue(hub_session.is_running_subagent(subagent, now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS))

    def test_zg6_e1_zombie_after_three_hours_reproduces_idle(self) -> None:
        """E1 실측 재현(G1) — 현재 코드에서는 working 이다(버그 재현)."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer"),
            _event("UserPromptSubmit", 1000),
            _event("Stop", 2000),
        ]
        facts = _facts_from(events)
        three_hours_later = facts.started_at_ms + 3 * 60 * self.ONE_MINUTE_MS
        view = hub_session.compute_session_view(
            facts, now_ms=three_hours_later, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS
        )
        self.assertEqual(view.state, "idle")
        self.assertEqual(view.base_state, "idle")

    def test_zg7_age_89_minutes_still_working(self) -> None:
        """오탐 방어 — 아직 90분이 안 됐으면 좀비가 아니다. 구현 전에도 통과해야 한다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer"),
            _event("UserPromptSubmit", 1000),
            _event("Stop", 2000),
        ]
        facts = _facts_from(events)
        eighty_nine_minutes_later = facts.started_at_ms + 89 * self.ONE_MINUTE_MS
        view = hub_session.compute_session_view(
            facts, now_ms=eighty_nine_minutes_later, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS
        )
        self.assertEqual(view.state, "working")

    def test_zg8_running_run_appears_first_next_to_its_zombie_sibling(self) -> None:
        """X2 재개정(결정 AR4 — 1:1 투영, docs/prps/hub-agent-runs-and-prompt-source.md) —
        같은 타입이라도 실행은 더 이상 합쳐지지 않는다. 좀비 1건과 정상 실행 1건이 각자
        뷰로 남고, 카드 상태는 정상 실행 덕에 여전히 working 이며 정상 실행이 K2 로 앞선다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", self.ZOMBIE_AFTER_MS, agent_id="agt-2", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + self.ZOMBIE_AFTER_MS
        view = hub_session.compute_session_view(facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS)
        self.assertEqual(view.state, "working")
        self.assertEqual(len(view.agent_runs), 2)
        self.assertEqual(view.agent_runs[0].agent_id, "agt-2")
        self.assertTrue(view.agent_runs[0].is_running)
        self.assertEqual(view.agent_runs[1].agent_id, "agt-1")
        self.assertFalse(view.agent_runs[1].is_running)

    def test_zg9_zombie_chip_demotes_to_ended_group_ordering(self) -> None:
        """결정 ZG4 — 좀비 칩은 종료 그룹으로 내려가 최근 시작순에 편입된다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer"),
            _event("SubagentStart", 1000, agent_id="agt-2", agent_type="implementer"),
            _event("SubagentStop", 2000, agent_id="agt-2", agent_type="implementer"),
            _event("Stop", 3000),
        ]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + self.ZOMBIE_AFTER_MS + self.ONE_MINUTE_MS
        runs = hub_session.summarize_agent_runs(facts, now_ms=now_ms)
        self.assertTrue(all(not run.is_running for run in runs))
        self.assertEqual([run.agent_type for run in runs], ["implementer", "code-reviewer"])

    def test_zg10_running_turn_overrides_zombie_only_session(self) -> None:
        """X3 — turn_state=="running" 이면 좀비뿐이어도 working. 구현 전에도 통과해야 한다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer"),
            _event("UserPromptSubmit", 1000),
        ]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + self.ZOMBIE_AFTER_MS + self.ONE_MINUTE_MS
        view = hub_session.compute_session_view(facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS)
        self.assertEqual(view.state, "working")

    def test_zg11_state_and_chips_never_contradict_for_zombie_only_session(self) -> None:
        """G4·S4 — 좀비만 있는 세션에서 상태와 칩이 동시에 어긋나지 않는다(동시 단정)."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer"),
            _event("UserPromptSubmit", 1000),
            _event("Stop", 2000),
        ]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + self.ZOMBIE_AFTER_MS + self.ONE_MINUTE_MS
        view = hub_session.compute_session_view(facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS)
        self.assertNotEqual(view.state, "working")
        self.assertTrue(all(not run.is_running for run in view.agent_runs))

    def test_zg12_longest_real_run_reproduces_e6(self) -> None:
        """E6 실측 최장 재현(G2) — T=기본값(SUBAGENT_ZOMBIE_AFTER_MS)에서도 좀비로 오인되지 않는다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("Stop", 100),
        ]
        facts = _facts_from(events)
        forty_seven_point_three_minutes_ms = int(47.3 * self.ONE_MINUTE_MS)
        now_ms = facts.started_at_ms + forty_seven_point_three_minutes_ms
        runs = hub_session.summarize_agent_runs(facts, now_ms=now_ms)
        self.assertTrue(runs[0].is_running)

    def test_zg13_zombie_session_is_excluded_from_tier1_generation_verdict(self) -> None:
        """결정 ZG6·G5 — 좀비가 살아 있는 세션 집합에서 빠져 세대 판정 오염이 해소된다."""
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS,
        )
        events = [
            _event("SubagentStart", 60_000, agent_id="agt-1", agent_type="code-reviewer"),
            _event("Stop", 61_000),
        ]
        facts = hub_session_facts.build_session_facts(events)["session-1"]
        now_ms = facts.started_at_ms + self.ZOMBIE_AFTER_MS + self.ONE_MINUTE_MS
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1},
            sessions_by_path={"/repo": (facts,)},
            tier3_last_activity_by_path={},
            now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS,
        )
        self.assertNotEqual(views[0].state, "working")
        self.assertFalse(views[0].tier1_is_previous_task)

    def test_zg14_zombie_chip_survives_json_round_trip_as_not_running(self) -> None:
        """선례: 기존 test_a8·test_gn9 — 렌더링 왕복 후에도 계약이 유지된다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer")]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + self.ZOMBIE_AFTER_MS + self.ONE_MINUTE_MS
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS
        )
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state=view.state,
            last_activity_at_ms=BASE_TIME_MS, sessions=(view,), tier1=None, note=None,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=(),
        )
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        parsed = json.loads(payload)
        self.assertIs(parsed["projects"][0]["sessions"][0]["agent_runs"][0]["is_running"], False)

    def test_zg15_compute_session_view_default_zombie_threshold_applies(self) -> None:
        """GOTCHA 8 회귀 — zombie_after_ms 없이 호출해도 SUBAGENT_ZOMBIE_AFTER_MS 가 적용된다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="code-reviewer"),
            _event("Stop", 1000),
        ]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + hub_session.SUBAGENT_ZOMBIE_AFTER_MS + self.ONE_MINUTE_MS
        view = hub_session.compute_session_view(facts, now_ms, self.NO_OVERLAY_STALE_AFTER_MS)
        self.assertEqual(view.base_state, "idle")


class SubagentLivenessSignalTest(unittest.TestCase):
    """SL-U1~U12 — docs/prps/hub-subagent-liveness-signal.md 결정 SL1~SL5.

    미종료 서브에이전트 실행의 transcript 마지막 기록 시각(subagent_activity_by_agent_id)이
    좀비 판정(is_running_subagent)과 stale 오버레이(last_known_activity_at_ms) 를 보강하는지
    검증한다. SubagentZombieGuardTest 와 같은 표 기반 — 전부 ★순수라 파일을 만들지 않고
    dict[str, int] 를 직접 넘긴다.
    """

    ZOMBIE_AFTER_MS = 90 * 60 * 1000
    ONE_MINUTE_MS = 60 * 1000
    # SubagentZombieGuardTest 와 같은 이유(오버레이가 결과를 가리지 않게) — 시나리오 지속
    # 시간보다 넉넉히 큰 stale_after_ms.
    NO_OVERLAY_STALE_AFTER_MS = 24 * 60 * 60 * 1000

    def _not_listed_index(self) -> hub_live_session.LiveSessionIndex:
        return hub_live_session.build_live_session_index([], is_complete=True)

    def test_slu1_g1_42_minute_run_with_recent_activity_stays_working(self) -> None:
        """G1 — 42분째 도는 실행, 마지막 훅은 42분 전이지만 transcript 활동은 1분 전.
        현행 코드는 last_event_at_ms 만 보고 stale 로 뒤집는다(버그 재현, SL-U3 이 고정)."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + 42 * self.ONE_MINUTE_MS
        activity = {"agt-1": now_ms - self.ONE_MINUTE_MS}
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id=activity,
        )
        self.assertEqual(view.state, "working")

    def test_slu2_g2_98_minute_run_with_recent_activity_is_still_running(self) -> None:
        """G2 — 시작 98분 전(오늘의 90분 상한을 넘김)이어도 활동이 1분 전이면 실행 중이다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + 98 * self.ONE_MINUTE_MS
        activity = {"agt-1": now_ms - self.ONE_MINUTE_MS}
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS,
            subagent_activity_by_agent_id=activity,
        )
        self.assertEqual(view.base_state, "working")
        self.assertTrue(view.agent_runs[0].is_running)

    def test_slu3_g3_without_activity_argument_matches_todays_verdict(self) -> None:
        """G3 — 보강 인자 없이 호출하면 오늘의 판정과 완전히 같다(무동작 회귀 고정,
        SL2 단조성의 근거). SL-U1·SL-U2 와 같은 사실을 활동 dict 없이 재현한다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)

        forty_two_minutes_later = facts.started_at_ms + 42 * self.ONE_MINUTE_MS
        view_42 = hub_session.compute_session_view(
            facts, now_ms=forty_two_minutes_later, stale_after_ms=STALE_AFTER_MS
        )
        self.assertEqual(view_42.state, "stale")

        ninety_eight_minutes_later = facts.started_at_ms + 98 * self.ONE_MINUTE_MS
        view_98 = hub_session.compute_session_view(
            facts, now_ms=ninety_eight_minutes_later, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS
        )
        self.assertEqual(view_98.base_state, "idle")
        self.assertFalse(view_98.agent_runs[0].is_running)

    def test_slu4_g4_ninety_minutes_after_last_activity_is_zombie(self) -> None:
        """G4 — 상한이 살아 있다. 시작 5분 뒤 활동이 멎은 실행은 그 활동+90분에 좀비다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        last_activity_ms = facts.started_at_ms + 5 * self.ONE_MINUTE_MS
        now_ms = last_activity_ms + self.ZOMBIE_AFTER_MS
        self.assertFalse(
            hub_session.is_running_subagent(
                facts.subagents[0], now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS,
                last_activity_at_ms=last_activity_ms,
            )
        )

    def test_slu5_boundary_one_ms_under_ninety_minutes_is_still_running(self) -> None:
        """G4 경계 — 경계는 <(ZG3 와 같은 관례)다, 1ms 못 미치면 아직 실행 중이다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        last_activity_ms = facts.started_at_ms + 5 * self.ONE_MINUTE_MS
        now_ms = last_activity_ms + self.ZOMBIE_AFTER_MS - 1
        self.assertTrue(
            hub_session.is_running_subagent(
                facts.subagents[0], now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS,
                last_activity_at_ms=last_activity_ms,
            )
        )

    def test_slu6_ended_subagent_ignores_fresh_activity_signal(self) -> None:
        """종료 검사가 먼저다(결정 SL3) — 방금 시각의 활동이 있어도 종료된 실행은 죽은 것이다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 1000, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + self.ONE_MINUTE_MS
        fresh_activity = {"agt-1": now_ms}
        self.assertFalse(
            hub_session.is_running_subagent(
                facts.subagents[0], now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS,
                last_activity_at_ms=fresh_activity["agt-1"],
            )
        )
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS,
            subagent_activity_by_agent_id=fresh_activity,
        )
        self.assertEqual(view.base_state, "idle")

    def test_slu7_g6_state_and_chip_do_not_contradict_when_working_via_activity(self) -> None:
        """G6 — 활동 신호만으로 working 이 된 경우에도 상태·칩이 일치한다(ZG11 의 이번 판)."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + 98 * self.ONE_MINUTE_MS
        activity = {"agt-1": now_ms - self.ONE_MINUTE_MS}
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS,
            subagent_activity_by_agent_id=activity,
        )
        self.assertEqual(view.base_state, "working")
        self.assertTrue(any(run.is_running for run in view.agent_runs))

    def test_slu8_stale_verdict_is_identical_for_unknown_and_not_listed_roster(self) -> None:
        """SL-U8/G5 — 활동 dict 가 같으면 살아있는 세션 명부가 unknown 이든 not_listed 든
        is_stale 이 같다(결정 LS9 P1). 두 경우 base_state 는 다르다(working vs idle)는
        점에서, is_stale 이 그 차이와 무관하게 True 로 같음을 보여 T25-224 의 행동 대응판이
        된다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        last_activity_ms = facts.started_at_ms + self.ONE_MINUTE_MS
        activity = {"agt-1": last_activity_ms}
        now_ms = last_activity_ms + STALE_AFTER_MS + self.ONE_MINUTE_MS

        view_unknown = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id=activity,
        )
        view_not_listed = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id=activity, live_roster=self._not_listed_index(),
        )
        self.assertEqual(view_unknown.state, "stale")
        self.assertEqual(view_not_listed.state, "stale")

    def test_slu9_last_known_activity_uses_max_across_unfinished_runs(self) -> None:
        """max 가 맞다 — 조용한 실행 하나와 활발한 실행 하나가 같이 있으면, 활발한 쪽의
        최신 활동이 stale 판정을 구원한다(하나만 보면 이 테스트가 잡는다)."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-quiet", agent_type="implementer"),
            _event("SubagentStart", 0, agent_id="agt-lively", agent_type="code-reviewer"),
        ]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + 42 * self.ONE_MINUTE_MS
        activity = {
            "agt-quiet": facts.started_at_ms + 2 * self.ONE_MINUTE_MS,
            "agt-lively": now_ms - self.ONE_MINUTE_MS,
        }
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id=activity,
        )
        self.assertEqual(view.state, "working")

    def test_slu10_g9_activity_timestamp_does_not_leak_into_the_view(self) -> None:
        """G9 — transcript mtime 은 판정에만 쓰이고 뷰에는 실리지 않는다(결정 LS10 과 같은
        이유). 1ms 차이는 어떤 문턱도 넘지 않으므로 두 뷰는 완전히 같아야 한다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + 5 * self.ONE_MINUTE_MS
        view_a = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id={"agt-1": now_ms - self.ONE_MINUTE_MS},
        )
        view_b = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id={"agt-1": now_ms - self.ONE_MINUTE_MS + 1},
        )
        self.assertEqual(dataclasses.asdict(view_a), dataclasses.asdict(view_b))

    def test_slu11_unrelated_agent_id_in_activity_dict_is_harmless(self) -> None:
        """조회 실패가 무해하다 — 이 세션과 무관한 agent_id 만 있으면 오늘의 판정 그대로다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        now_ms = facts.started_at_ms + 98 * self.ONE_MINUTE_MS
        unrelated_activity = {"agt-from-another-session": now_ms}
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=self.NO_OVERLAY_STALE_AFTER_MS,
            subagent_activity_by_agent_id=unrelated_activity,
        )
        self.assertEqual(view.base_state, "idle")
        self.assertFalse(view.agent_runs[0].is_running)

    def test_slu12_clock_skew_with_future_activity_timestamp_is_running(self) -> None:
        """ZG5 선례 — now_ms 가 활동 시각보다 과거여도(시계 역행) 안전한 방향(실행 중)으로
        본다."""
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        now_ms = BASE_TIME_MS + 100 * self.ONE_MINUTE_MS   # 이미 좀비 나이(첫 분기 False)
        future_activity_ms = now_ms + self.ONE_MINUTE_MS   # 활동 시각이 now_ms 보다 미래
        self.assertTrue(
            hub_session.is_running_subagent(
                subagent, now_ms=now_ms, zombie_after_ms=self.ZOMBIE_AFTER_MS,
                last_activity_at_ms=future_activity_ms,
            )
        )

    def test_slu13_last_known_activity_ignores_ended_run_even_with_fresh_timestamp(self) -> None:
        """재검수 2회차 MEDIUM-2 — last_known_activity_at_ms 자신의 '종료된 실행은 후보에서
        뺀다' 필터를 직접 문다. SL-U6 은 NO_OVERLAY_STALE_AFTER_MS(24시간)로 stale 오버레이
        자체를 꺼 두고 base_state 만 보므로, 그 필터가 사라져도 SL-U1~U12 어느 것도 잡지
        못한다. 여기서는 문턱과 같은 크기의 stale_after_ms 를 써서, 종료된 실행의 agent_id
        에 방금 시각의 활동이 남아 있어도 is_stale 판정이 그 활동을 보지 않고 마지막 훅
        이벤트만 보는지 확인한다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 1000, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + STALE_AFTER_MS + self.ONE_MINUTE_MS
        fresh_activity_for_ended_run = {"agt-1": now_ms - self.ONE_MINUTE_MS}
        view = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id=fresh_activity_for_ended_run,
        )
        self.assertEqual(view.state, "stale")


class SummarizeAgentRunsTest(unittest.TestCase):
    """세션의 서브에이전트 실행 요약(결정 AR4~AR11,
    docs/prps/hub-agent-runs-and-prompt-source.md) — 타입 합계에서 실행 단위로."""

    def test_same_type_three_runs_yields_three_views(self) -> None:
        """AR4 의 출발점 — 오늘은 1개로 합쳐지던 것이 실행 3건이면 뷰 3개가 된다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 100, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 200, agent_id="agt-2", agent_type="implementer"),
            _event("SubagentStop", 300, agent_id="agt-2", agent_type="implementer"),
            _event("SubagentStart", 400, agent_id="agt-3", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertEqual(len(runs), 3)
        self.assertEqual({run.agent_id for run in runs}, {"agt-1", "agt-2", "agt-3"})

    def test_sort_order_is_running_first_then_recency_then_agent_id(self) -> None:
        """AR5(K2) — 실행 중 우선, 그 다음 started_at_ms 내림차순, 동률은 agent_id 오름차순."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-old", agent_type="design-architect"),
            _event("SubagentStop", 100, agent_id="agt-old", agent_type="design-architect"),
            _event("SubagentStart", 200, agent_id="agt-b", agent_type="implementer"),
            _event("SubagentStart", 200, agent_id="agt-a", agent_type="implementer"),
            _event("SubagentStart", 300, agent_id="agt-running", agent_type="code-reviewer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertEqual(
            [run.agent_id for run in runs], ["agt-running", "agt-a", "agt-b", "agt-old"]
        )

    def test_same_ms_start_order_is_deterministic_across_calls(self) -> None:
        """D2 — snapshot_content_key 안정성을 위해 동률 타이브레이커가 매 호출 같은 순서를 낸다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-z", agent_type="implementer"),
            _event("SubagentStart", 0, agent_id="agt-a", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        first = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        second = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertEqual([run.agent_id for run in first], [run.agent_id for run in second])
        self.assertEqual([run.agent_id for run in first], ["agt-a", "agt-z"])

    def test_zombie_run_is_not_running_matching_base_state(self) -> None:
        """ZG1·ZG4 — 90분 초과 미종료 실행은 카드 상태와 같은 술어로 실행 중이 아니다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + hub_session.SUBAGENT_ZOMBIE_AFTER_MS + 60_000
        runs = hub_session.summarize_agent_runs(facts, now_ms=now_ms)
        self.assertFalse(runs[0].is_running)

    def test_missing_meta_falls_back_to_hook_values_only(self) -> None:
        """AR9 — meta 가 없으면 title·model 은 None, agent_type·시각은 훅 값 그대로다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertIsNone(runs[0].title)
        self.assertIsNone(runs[0].model)
        self.assertEqual(runs[0].agent_type, "implementer")
        self.assertEqual(runs[0].started_at_ms, facts.subagents[0].started_at_ms)

    def test_meta_present_without_subagent_start_uses_meta_started_at(self) -> None:
        """AR7 — SubagentStart 미발화 실행(started_at_ms == ended_at_ms)의 진짜 시작은
        meta.json mtime 이다. SubagentFact 자체(사실)는 손대지 않는다 — 뷰에서만 보정한다."""
        events = [_event("SubagentStop", 5000, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        self.assertEqual(facts.subagents[0].started_at_ms, facts.subagents[0].ended_at_ms)   # 합성 실행(경과 0)
        meta = hub_subagent.SubagentMeta(
            title="구현 작업", agent_type="implementer", model="sonnet", started_at_ms=1000
        )
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id={"agt-1": meta}
        )
        self.assertEqual(runs[0].started_at_ms, 1000)
        self.assertNotEqual(runs[0].started_at_ms, facts.subagents[0].ended_at_ms)

    def test_meta_fields_are_carried_into_the_view(self) -> None:
        meta = hub_subagent.SubagentMeta(
            title="레포 subtree 스코핑 구현", agent_type="implementer", model="sonnet", started_at_ms=0
        )
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id={"agt-1": meta}
        )
        self.assertEqual(runs[0].title, "레포 subtree 스코핑 구현")
        self.assertEqual(runs[0].model, "sonnet")

    def test_meta_agent_type_fills_in_when_hook_agent_type_is_empty(self) -> None:
        """SubagentRunView.agent_type 필드 계약 — "훅 원문(없으면 meta.json)". 훅이 빈
        문자열을 보냈어도 meta 에 값이 있으면 그 실행은 사라지지 않는다."""
        meta = hub_subagent.SubagentMeta(
            title="탐색", agent_type="Explore", model="haiku", started_at_ms=0
        )
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="")]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id={"agt-1": meta}
        )
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].agent_type, "Explore")

    def test_subagent_fact_is_unaffected_by_meta_presence(self) -> None:
        """AR1 구조 보증 — meta 는 뷰에만 영향을 주고 상태-판정 입력(state·base_state·
        is_running)에는 영향을 주지 않는다. 훅은 1분 전 시작(안 끝남), meta.json 은 3시간
        전 시작을 주장한다 — meta 유무로 갈리는 것은 표시용 started_at_ms 뿐이어야 한다.

        (재검수 1회차 M1 — 이전 버전은 같은 인자로 _facts_from 을 두 번 불러 비교했다.
        build_session_facts 는 애초 meta 인자를 받지 않으므로 그 비교는 항상 참이라 AR1을
        증명하지 못했다. compute_session_view 에 meta 를 실제로 넣고/빼서 비교한다.)"""
        now_ms = BASE_TIME_MS + 60_000  # 훅 시작(BASE_TIME_MS)으로부터 1분 후
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        meta = hub_subagent.SubagentMeta(
            title="구현 작업", agent_type="implementer", model="sonnet",
            started_at_ms=now_ms - 3 * 60 * 60 * 1000,
        )

        view_without_meta = hub_session.compute_session_view(facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS)
        view_with_meta = hub_session.compute_session_view(
            facts, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS, subagent_meta_by_agent_id={"agt-1": meta}
        )

        self.assertEqual(view_without_meta.state, view_with_meta.state)
        self.assertEqual(view_without_meta.base_state, view_with_meta.base_state)
        self.assertEqual(view_without_meta.agent_runs[0].is_running, view_with_meta.agent_runs[0].is_running)
        self.assertTrue(view_with_meta.agent_runs[0].is_running)  # 공허한 참(둘 다 False)이 아님을 확인

        self.assertEqual(view_without_meta.agent_runs[0].started_at_ms, facts.subagents[0].started_at_ms)
        self.assertEqual(view_with_meta.agent_runs[0].started_at_ms, meta.started_at_ms)
        self.assertNotEqual(view_without_meta.agent_runs[0].started_at_ms, view_with_meta.agent_runs[0].started_at_ms)

    def test_hook_agent_type_and_agent_id_over_32_chars_are_clipped(self) -> None:
        """M2(재검수 1회차, 결정 AR10 소급 적용) — summarize_agent_runs 의
        clip_metadata(raw_agent_type)·clip_metadata(sub.agent_id) 호출에 전용 회귀가
        없었다. 훅이 32자 넘는 agent_type·agent_id 를 보내면 뷰에서 잘리는지 직접 본다."""
        long_agent_type = "T" * 40
        long_agent_id = "I" * 40
        events = [_event("SubagentStart", 0, agent_id=long_agent_id, agent_type=long_agent_type)]
        facts = _facts_from(events)

        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)

        self.assertEqual(len(runs), 1)
        max_chars = hub_subagent.SUBAGENT_METADATA_MAX_CHARS
        expected_agent_type = "T" * (max_chars - 1) + "…"
        expected_agent_id = "I" * (max_chars - 1) + "…"
        self.assertEqual(runs[0].agent_type, expected_agent_type)
        self.assertEqual(runs[0].agent_id, expected_agent_id)
        self.assertEqual(len(runs[0].agent_type), max_chars)
        self.assertEqual(len(runs[0].agent_id), max_chars)

    def test_empty_agent_type_is_excluded(self) -> None:
        facts = _facts_from([_event("SubagentStart", 0, agent_id="agt-1", agent_type="")])
        self.assertEqual(hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms), ())

    def test_unmapped_type_has_no_phase(self) -> None:
        facts = _facts_from(
            [_event("SubagentStart", 0, agent_id="agt-1", agent_type="workflow-subagent")]
        )
        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertEqual(len(runs), 1)
        self.assertIsNone(runs[0].phase)
        self.assertTrue(runs[0].is_running)

    def test_no_subagent_yields_empty_tuple(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        self.assertEqual(hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms), ())

    def test_run_count_over_cap_keeps_the_front_after_sorting(self) -> None:
        """AR11 — 실행 150건이면 뷰는 SUBAGENT_RUN_MAX_PER_SESSION(100)건, 정렬 앞쪽이 남는다."""
        total_runs = hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION + 50
        events = [
            _event("SubagentStart", index, agent_id=f"agt-{index}", agent_type="implementer")
            for index in range(total_runs)
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertEqual(len(runs), hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION)
        # 전부 미종료(실행 중)이므로 1차 정렬 키가 동률이라 -started_at_ms 가 갈라 가장 최근
        # 시작(가장 큰 index)이 맨 앞이다.
        self.assertEqual(runs[0].agent_id, f"agt-{total_runs - 1}")

    def test_done_session_still_exposes_agent_runs(self) -> None:
        """이 PRP 가 고치는 결함의 직접 회귀 테스트 — 완료된 세션도 agent_runs 를 잃지 않는다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 100, agent_id="agt-1", agent_type="implementer"),
            _event("SessionEnd", 200),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")
        self.assertEqual(len(view.agent_runs), 1)
        self.assertFalse(view.agent_runs[0].is_running)

    def test_task_excerpt_argument_is_carried_into_the_view_verbatim(self) -> None:
        """PS3 — compute_session_view 는 task_excerpt 를 계산하지 않고 인자로 받아 그대로 싣는다."""
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            task_excerpt="마지막 프롬프트",
        )
        self.assertEqual(view.task_excerpt, "마지막 프롬프트")

    def test_agent_runs_reaches_json_contract(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 100, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state="working",
            last_activity_at_ms=BASE_TIME_MS, sessions=(view,), tier1=None, note=None,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=(),
        )
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        parsed = json.loads(payload)
        session_json = parsed["projects"][0]["sessions"][0]
        self.assertEqual(session_json["agent_runs"][0]["agent_type"], "implementer")
        self.assertEqual(session_json["agent_runs"][0]["agent_id"], "agt-1")
        self.assertNotIn("active_agent_types", session_json)
        self.assertNotIn("inferred_phase", session_json)

    def test_agent_runs_difference_changes_content_key(self) -> None:
        def _snapshot(agent_runs):
            session = hub_session.SessionView(
                session_id="s1", short_id="s1", started_at_ms=BASE_TIME_MS,
                state="working", base_state="working",
                last_event_at_ms=BASE_TIME_MS, task_excerpt=None, agent_runs=agent_runs,
            )
            project = hub_project.ProjectView(
                display_name="coding-harness", path="/repo", tier=2, state="working",
                last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
            )
            return hub_model.HubSnapshot(
                collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=(),
            )

        key_without_runs = hub_model.snapshot_content_key(_snapshot(()))
        key_with_runs = hub_model.snapshot_content_key(
            _snapshot((
                hub_session.SubagentRunView(
                    agent_id="agt-1", agent_type="implementer", phase="구현", is_running=True,
                    started_at_ms=BASE_TIME_MS, ended_at_ms=None, title=None, model=None,
                ),
            ))
        )
        self.assertNotEqual(key_without_runs, key_with_runs)


class SummarizeAgentRunsPreviousTaskTest(unittest.TestCase):
    """PT1~PT7(이슈 3, docs/prps/hub-session-list-and-glow-fixes.md §5) —
    summarize_agent_runs 의 previous_task_boundary_ms 인자와
    SubagentRunView.is_previous_task 필드."""

    def test_pt1_boundary_none_leaves_every_run_false(self) -> None:
        """경계를 안 주면(기본값 None) 오늘과 동일 — 전부 False."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", 100, agent_id="agt-2", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(not run.is_previous_task for run in runs))

    def test_pt2_started_one_ms_before_boundary_is_true(self) -> None:
        """실행이 이미 끝났을 때의 경계 비교(RL3 의 실행 중 면제와 분리해서 본다 — 그 면제는
        아래 test_running_run_before_boundary_is_not_previous 가 따로 문다)."""
        events = [
            _event("SubagentStart", -1, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 0, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertTrue(runs[0].is_previous_task)

    def test_running_run_before_boundary_is_not_previous(self) -> None:
        """RL3(실측 22.7%, docs/prps/hub-card-gate-and-run-list-reset.md §1.4) — 지금 돌고
        있는 실행은 경계 이전에 시작됐어도 숨기지 않는다."""
        events = [_event("SubagentStart", -1, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertFalse(runs[0].is_previous_task)

    def test_zombie_run_before_boundary_is_previous(self) -> None:
        """RL3 경계 — SUBAGENT_ZOMBIE_AFTER_MS(90분)를 넘긴 미종료 실행은 "지금 돌고 있다"는
        근거를 잃어(is_running_subagent 와 같은 술어) 다시 경계 판정에 걸린다."""
        events = [_event("SubagentStart", -1, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        ninety_one_minutes_later = facts.last_event_at_ms + 91 * 60 * 1000
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=ninety_one_minutes_later, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertTrue(runs[0].is_previous_task)

    def test_runs_before_task_start_are_previous(self) -> None:
        """RL8 — previous_task_boundary_ms 로 얻은 경계(작업 시작 시각) 이전에 시작되고
        끝난 실행은 이전 작업으로 표시된다."""
        events = [
            _event("SubagentStart", 100, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 150, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS + 200,
        )
        self.assertTrue(runs[0].is_previous_task)

    def test_pt3_started_exactly_at_boundary_is_false(self) -> None:
        """결정 PT2 — 경계는 현재 작업 쪽으로 연다(엄격한 <). 같은 밀리초는 현재 작업이다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertFalse(runs[0].is_previous_task)

    def test_pt4_started_after_boundary_is_false(self) -> None:
        events = [_event("SubagentStart", 1, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertFalse(runs[0].is_previous_task)

    def test_pt5_all_runs_before_boundary_are_all_true_and_none_are_dropped(self) -> None:
        """결정 PT3 — 서버는 목록을 잘라내지 않는다. 실행이 전부 이전 작업이어도 개수는
        그대로다(표시 정책은 클라이언트의 몫)."""
        events = [
            _event("SubagentStart", -300, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", -200, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStart", -100, agent_id="agt-2", agent_type="implementer"),
            _event("SubagentStop", -50, agent_id="agt-2", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run.is_previous_task for run in runs))

    def test_pt6_mixed_previous_and_current_keep_ar5_sort_order(self) -> None:
        """정렬은 AR5(K2) 그대로(실행 중 우선 → 최근 시작 → agent_id) — is_previous_task 는
        플래그로만 얹히고 정렬 키에 들어가지 않는다."""
        events = [
            _event("SubagentStart", -300, agent_id="agt-old-1", agent_type="implementer"),
            _event("SubagentStop", -290, agent_id="agt-old-1", agent_type="implementer"),
            _event("SubagentStart", -200, agent_id="agt-old-2", agent_type="implementer"),
            _event("SubagentStop", -190, agent_id="agt-old-2", agent_type="implementer"),
            _event("SubagentStart", 100, agent_id="agt-new-1", agent_type="implementer"),
            _event("SubagentStart", 200, agent_id="agt-new-running", agent_type="code-reviewer"),
        ]
        facts = _facts_from(events)
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertEqual(
            [run.agent_id for run in runs],
            ["agt-new-running", "agt-new-1", "agt-old-2", "agt-old-1"],
        )
        is_previous_by_id = {run.agent_id: run.is_previous_task for run in runs}
        self.assertTrue(is_previous_by_id["agt-old-1"])
        self.assertTrue(is_previous_by_id["agt-old-2"])
        self.assertFalse(is_previous_by_id["agt-new-1"])
        self.assertFalse(is_previous_by_id["agt-new-running"])

    def test_pt7_boundary_compares_against_view_started_at_ms_not_hook_value(self) -> None:
        """AR7 — meta.json 시작 시각이 있으면 뷰의 started_at_ms 는 그 값이고, 경계 비교도
        같은 값을 쓴다(뷰 기준 — 훅 값이 아니다). 훅 값(경계+500)은 경계보다 뒤지만
        meta 값(경계-1)은 앞이므로, 경계 비교가 뷰 값을 쓴다면 True 가 나와야 한다."""
        events = [_event("SubagentStop", 500, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        meta = hub_subagent.SubagentMeta(
            title="구현 작업", agent_type="implementer", model="sonnet",
            started_at_ms=BASE_TIME_MS - 1,
        )
        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id={"agt-1": meta},
            previous_task_boundary_ms=BASE_TIME_MS,
        )
        self.assertEqual(runs[0].started_at_ms, meta.started_at_ms)
        self.assertTrue(runs[0].is_previous_task)


class SummarizeAgentRunsResumeTest(unittest.TestCase):
    """V1~V3(결정 TF11, docs/prps/hub-agent-title-and-excerpt-freshness.md §9.2) — SubagentRunView 맨 뒤 2필드 resume_title·
    resume_count. `title` 의 뜻(meta.description)은 그대로(AR9)이고, 화면이 쓸 재개 제목과 횟수가 따로 실린다."""

    @staticmethod
    def _resumed_facts(resume_count: int, agent_id: str = "agt-1"):
        """Start → Stop → (Start → Stop) × resume_count 로 만든 사실 — 훅 사실만으로 resume_count 가 서는 경로까지 함께 탄다."""
        events = [_event("SubagentStart", 0, agent_id=agent_id, agent_type="code-reviewer")]
        for cycle in range(resume_count + 1):
            if cycle:
                events.append(_event("SubagentStart", cycle * 1000, agent_id=agent_id, agent_type="code-reviewer"))
            events.append(_event("SubagentStop", cycle * 1000 + 500, agent_id=agent_id, agent_type="code-reviewer"))
        return _facts_from(events)

    @staticmethod
    def _meta(resume_title: str | None, title: str = "첫 작업 이름", started_at_ms: int = BASE_TIME_MS) -> hub_subagent.SubagentMeta:
        return hub_subagent.SubagentMeta(
            title=title, agent_type="code-reviewer", model="sonnet", started_at_ms=started_at_ms, resume_title=resume_title,
        )

    def test_v1_meta_resume_title_and_hook_resume_count_reach_the_view_and_title_keeps_its_meaning(self) -> None:
        facts = self._resumed_facts(resume_count=2)

        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id={"agt-1": self._meta("지금 작업 이름")},
        )

        self.assertEqual(runs[0].resume_title, "지금 작업 이름")
        self.assertEqual(runs[0].resume_count, 2)
        self.assertEqual(runs[0].title, "첫 작업 이름")   # title = meta.description 그대로(AR9)

    def test_v2_without_a_meta_the_view_keeps_the_hook_resume_count_and_has_no_resume_title(self) -> None:
        facts = self._resumed_facts(resume_count=1)

        runs = hub_session.summarize_agent_runs(facts, now_ms=facts.last_event_at_ms)

        self.assertIsNone(runs[0].resume_title)
        self.assertEqual(runs[0].resume_count, 1)

    def test_a_run_that_was_never_resumed_has_the_defaults(self) -> None:
        facts = self._resumed_facts(resume_count=0)

        runs = hub_session.summarize_agent_runs(
            facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id={"agt-1": self._meta(None)},
        )

        self.assertEqual((runs[0].resume_title, runs[0].resume_count), (None, 0))

    def test_v3_resume_fields_do_not_change_ordering_running_or_previous_task(self) -> None:
        """정렬(K2)·is_running·is_previous_task 는 재개 필드와 무관하다 — 같은 입력에 재개 제목·횟수만 얹어 비교한다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-old", agent_type="design-architect"),
            _event("SubagentStop", 100, agent_id="agt-old", agent_type="design-architect"),
            _event("SubagentStart", 200, agent_id="agt-b", agent_type="implementer"),
            _event("SubagentStop", 250, agent_id="agt-b", agent_type="implementer"),
            _event("SubagentStart", 300, agent_id="agt-run", agent_type="code-reviewer"),
            _event("SubagentStart", 400, agent_id="agt-run", agent_type="code-reviewer"),   # 재개 — 실행 중
        ]
        facts = _facts_from(events)
        start_offsets_ms = {"agt-old": 0, "agt-b": 200, "agt-run": 400}
        plain = {agent_id: self._meta(None, started_at_ms=BASE_TIME_MS + offset) for agent_id, offset in start_offsets_ms.items()}
        titled = {
            agent_id: self._meta(f"{agent_id} 의 지금 작업", started_at_ms=BASE_TIME_MS + offset)
            for agent_id, offset in start_offsets_ms.items()
        }
        boundary_ms = BASE_TIME_MS + 150

        def _judged(metas):
            runs = hub_session.summarize_agent_runs(
                facts, now_ms=facts.last_event_at_ms, subagent_meta_by_agent_id=metas, previous_task_boundary_ms=boundary_ms,
            )
            return [(run.agent_id, run.is_running, run.is_previous_task, run.started_at_ms) for run in runs]

        self.assertEqual(_judged(titled), _judged(plain))
        # 전제 — 공허한 비교가 아니다: 실행 중 우선 → 최근 시작 순, 경계(+150)보다 먼저 시작해 끝난 것만 이전 작업
        self.assertEqual(
            [(agent_id, is_running, is_previous) for agent_id, is_running, is_previous, _ in _judged(titled)],
            [("agt-run", True, False), ("agt-b", False, False), ("agt-old", False, True)],
        )

    def test_resume_fields_reach_the_json_contract_as_static_values(self) -> None:
        facts = self._resumed_facts(resume_count=1)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_meta_by_agent_id={"agt-1": self._meta("지금 작업 이름")},
        )
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state="working",
            last_activity_at_ms=BASE_TIME_MS, sessions=(view,), tier1=None, note=None,
        )
        snapshot = hub_model.HubSnapshot(collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=())
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'

        rendered = hub_model.render_hub_html(template, snapshot)

        payload = json.loads(rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0])
        run_json = payload["projects"][0]["sessions"][0]["agent_runs"][0]
        self.assertEqual((run_json["resume_title"], run_json["resume_count"]), ("지금 작업 이름", 1))
        self.assertEqual(run_json["title"], "첫 작업 이름")

    def test_resume_title_participates_in_the_content_key_but_is_stable_for_equal_input(self) -> None:
        """정적 값이라 snapshot_content_key 가 안정적이다(D2) — 같은 입력이면 같은 키, 제목이 바뀌면 다른 키(쓰기 억제가 새 제목을 막지 않는다)."""
        def _key(resume_title):
            facts = self._resumed_facts(resume_count=1)
            view = hub_session.compute_session_view(
                facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
                subagent_meta_by_agent_id={"agt-1": self._meta(resume_title)},
            )
            project = hub_project.ProjectView(
                display_name="coding-harness", path="/repo", tier=2, state="working",
                last_activity_at_ms=BASE_TIME_MS, sessions=(view,), tier1=None, note=None,
            )
            return hub_model.snapshot_content_key(
                hub_model.HubSnapshot(collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=())
            )

        self.assertEqual(_key("지금 작업 이름"), _key("지금 작업 이름"))
        self.assertNotEqual(_key("지금 작업 이름"), _key("다음 작업 이름"))

    def test_view_construction_without_the_new_fields_keeps_working(self) -> None:
        """기존 생성 지점(테스트·합성 뷰)은 새 필드 없이 만든다 — 맨 뒤 기본값이라 무해하다."""
        run = hub_session.SubagentRunView(
            agent_id="agt-1", agent_type="implementer", phase="구현", is_running=True,
            started_at_ms=BASE_TIME_MS, ended_at_ms=None, title=None, model=None,
        )

        self.assertEqual((run.resume_title, run.resume_count), (None, 0))


class SessionRevivalTest(unittest.TestCase):
    """RV1~RV10 — docs/prps/hub-session-revival-and-stale-tier1.md 결정 RV1·RV2."""

    def test_rv1_prompt_then_end_is_done(self) -> None:
        """회귀 방어 — 기존 M3 와 같은 사실. 부활 없이 SessionEnd 만 오면 done 이다."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")

    def test_rv2_resume_after_end_clears_ended_at_ms(self) -> None:
        events = [_event("SessionEnd"), _event("SessionStart", 1000, source="resume")]
        facts = _facts_from(events)
        self.assertIsNone(facts.ended_at_ms)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "idle")

    def test_rv3_resume_then_prompt_is_working(self) -> None:
        events = [
            _event("SessionEnd"),
            _event("SessionStart", 1000, source="resume"),
            _event("UserPromptSubmit", 2000),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "working")

    def test_rv4_compact_session_start_does_not_revive(self) -> None:
        """GOTCHA 1 동작 검증 — 필터가 compact 를 부활 트리거에서 원천 차단한다."""
        events = [_event("SessionEnd"), _event("SessionStart", 1000, source="compact")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")

    def test_rv5_delayed_subagent_stop_after_end_does_not_revive(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 100, agent_id="agt-1", agent_type="implementer"),
            _event("SessionEnd", 200),
            _event("SubagentStop", 300, agent_id="agt-1", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")

    def test_rv6_stop_after_end_does_not_revive(self) -> None:
        events = [_event("SessionEnd"), _event("Stop", 1000)]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")

    def test_rv7_revived_session_goes_stale_after_thirty_one_minutes(self) -> None:
        events = [_event("SessionEnd"), _event("SessionStart", 1000, source="resume")]
        facts = _facts_from(events)
        thirty_one_minutes_later = facts.last_event_at_ms + 31 * 60 * 1000
        view = hub_session.compute_session_view(facts, now_ms=thirty_one_minutes_later, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "stale")
        self.assertEqual(view.base_state, "idle")

    def test_rv8_repeated_end_start_cycles_are_idempotent(self) -> None:
        events = [
            _event("SessionEnd", 0),
            _event("SessionStart", 1000, source="resume"),
            _event("SessionEnd", 2000),
            _event("SessionStart", 3000, source="resume"),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "idle")

    def test_rv9_e1_observed_sequence_reproduces_working(self) -> None:
        """E1 실측 축약 — 사용자 보고 재현(G3)."""
        events = [
            _event("UserPromptSubmit", 0),
            _event("SessionEnd", 1000),
            _event("SessionStart", 2000, source="resume"),
            _event("UserPromptSubmit", 3000),
            _event("SubagentStart", 4000, agent_id="agt-1", agent_type="design-architect"),
            _event("Stop", 5000),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "working")
        self.assertEqual(view.base_state, "working")

    def test_rv10_lone_session_start_is_a_harmless_no_op(self) -> None:
        """X1 — ended_at_ms 가 이미 None 이므로 부활은 무해한 무동작이다."""
        facts = _facts_from([_event("SessionStart", source="startup")])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "idle")


class SessionModelFieldTest(unittest.TestCase):
    """§8.5 — compute_session_view 의 model 인자(요구 2,
    docs/prps/hub-tier1-clamp-fix-and-session-model.md 결정 MD7)."""

    def test_model_defaults_to_none_for_existing_call_sites(self) -> None:
        """기존 호출부(model 인자 없이 부름)가 무해하다 — 기본값 None."""
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertIsNone(view.model)

    def test_model_is_carried_through_when_provided(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        model = hub_transcript.SessionModel(model_label="Opus 5", raw_model_id="claude-opus-5", effort="xhigh")
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, model=model
        )
        self.assertEqual(view.model, model)


class SessionViewTierOneDashboardFieldTest(unittest.TestCase):
    """P7(hub-session-tree-and-per-session-dashboards.md) — compute_session_view 의
    tier1·dashboard_key 인자(결정 ST12)."""

    def test_tier1_and_dashboard_key_default_to_none(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertIsNone(view.tier1)
        self.assertIsNone(view.dashboard_key)

    def test_tier1_and_dashboard_key_are_carried_through_when_provided(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path="/repo", session_id="session-1",
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            tier1=tier1, dashboard_key="abcdef0123456789",
        )
        self.assertEqual(view.tier1, tier1)
        self.assertEqual(view.dashboard_key, "abcdef0123456789")


class SessionWorkflowFieldTest(unittest.TestCase):
    """§11 — compute_session_view 의 workflow 인자(결정 WF1,
    docs/prps/hub-workflow-visibility.md). "SessionView 의 마지막 필드" 검사(T25-150 이전)는
    이 클래스가 아니라 SessionTierOneFinishedTaskTest 가 갖는다 — 결정 FT7(이슈 4,
    docs/prps/hub-ui-4-issues.md §5)이 그 자리를 workflow 에서 tier1_is_finished_task 로
    다시 넘겼다."""

    def _workflow(self) -> hub_workflow.WorkflowRunView:
        return hub_workflow.WorkflowRunView(agents=())

    def test_workflow_defaults_to_none_for_existing_call_sites(self) -> None:
        """기존 호출부(workflow 인자 없이 부름)가 무해하다 — 기본값 None."""
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertIsNone(view.workflow)

    def test_workflow_is_carried_through_when_provided(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        workflow = self._workflow()
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, workflow=workflow
        )
        self.assertEqual(view.workflow, workflow)

    def test_workflow_value_does_not_change_state_judgement(self) -> None:
        """결정 WF1 회귀 검사 — 워크플로우는 보강일 뿐 상태 판정 입력이 아니다. 같은 사실에
        workflow 유무만 더해도 state·base_state 가 그대로다."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", offset_ms=1000)])
        view_without_workflow = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS
        )
        view_with_workflow = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, workflow=self._workflow()
        )
        self.assertEqual(view_without_workflow.state, view_with_workflow.state)
        self.assertEqual(view_without_workflow.base_state, view_with_workflow.base_state)


class SessionTierOneFinishedTaskTest(unittest.TestCase):
    """FT1~FT7(이슈 4, docs/prps/hub-ui-4-issues.md §5) — is_session_tier1_from_finished_task
    순수 함수와 compute_session_view 의 tier1_is_finished_task 필드."""

    STALE_AFTER_MS = 30 * 60 * 1000
    ONE_MINUTE_MS = 60 * 1000

    def test_ft1_below_100_percent_is_false(self) -> None:
        """연접 1 — 100% 미만이면 Δ 와 무관하게 False."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=99, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 10 * 60 * 60 * 1000, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_ft2_100_percent_and_delta_over_threshold_is_true(self) -> None:
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 31 * self.ONE_MINUTE_MS, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertTrue(result)

    def test_ft3_delta_under_threshold_is_false(self) -> None:
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 29 * self.ONE_MINUTE_MS, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_ft4_boundary_exactly_threshold_is_false(self) -> None:
        """경계는 엄격한 > 다(오탐 회피 방향) — 같은 밀리초는 판정을 켜지 않는다."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + self.STALE_AFTER_MS, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_ft5_negative_delta_is_false(self) -> None:
        """파일이 마지막 이벤트보다 새롭다 — 음수 Δ 는 False."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS - 1, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_ft6_live_session_real_shape_is_false(self) -> None:
        """실측 d0e8c16b(§1.5) — 진행 중인 대시보드(0%)는 Δ 와 무관하게 False."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=0, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 48_000, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_ft7_stale_session_real_shape_is_true(self) -> None:
        """실측 1fc9c845(§1.5) — Δ 56.3분, 100%."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + int(56.3 * self.ONE_MINUTE_MS), stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertTrue(result)

    def test_ft8_idle_finished_recent_real_shape_is_false(self) -> None:
        """실측 af5c0abe(§1.5) — Δ 4.6분, 100%지만 임계값 아래."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + int(4.6 * self.ONE_MINUTE_MS), stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_ft9_compute_session_view_without_tier1_is_false(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertFalse(view.tier1_is_finished_task)

    def test_ft10_compute_session_view_sets_field(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", offset_ms=1000)])
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=2, total=2, percent=100, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=facts.last_event_at_ms - 31 * self.ONE_MINUTE_MS,
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, tier1=tier1,
        )
        self.assertTrue(view.tier1_is_finished_task)

    def test_ft11_session_view_last_field_is_the_new_flag(self) -> None:
        """T25-150 갱신(GOTCHA 8) — ⑨(docs/prps/harness-benchmark-adoption.md)가 SessionView 의
        마지막 필드 자리를 background_wait 에서 session_cost 로 넘겼다(tests/run.sh 의 동일 검사와
        일치). 그 앞서 결정 BW9 가 interruption → background_wait 으로, RI8 이 tier1_is_finished_task
        → interruption 으로, FT7 이 workflow → tier1_is_finished_task 로 넘긴 적이 있다."""
        self.assertEqual(
            dataclasses.fields(hub_session.SessionView)[-1].name, "session_cost"
        )

    def test_ft12_percent_over_100_is_true_when_delta_over_threshold(self) -> None:
        """percent 가 100 을 초과해도(101) 연접 1(>= 100)은 그대로 만족한다."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=101, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 31 * self.ONE_MINUTE_MS, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertTrue(result)

    def test_ft13_negative_percent_is_false(self) -> None:
        """percent 가 음수면 연접 1(>= 100)을 만족하지 못해 Δ 와 무관하게 False."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=-5, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 31 * self.ONE_MINUTE_MS, stale_after_ms=self.STALE_AFTER_MS,
        )
        self.assertFalse(result)

    def test_pt8_finished_task_session_marks_only_the_earlier_run_as_previous(self) -> None:
        """RL8-(b)(결정 RL2 가 PT1 을 번복 — 경계는 이제 file_mtime_ms 가 아니라
        task_started_at_ms 다, docs/prps/hub-card-gate-and-run-list-reset.md §3.7) — tier1
        의 작업이 끝났고(percent=100) 마지막 프롬프트가 없으면 경계 = task_started_at_ms.
        경계 앞뒤로 하나씩 있는 실행 중 앞의 것(이미 종료됨)만 is_previous_task=True 다.
        tier1_is_finished_task(RL5, 클릭 게이트용) 는 file_mtime_ms 로 여전히 판정된다 —
        실행 목록 경계와는 이제 독립이다."""
        events = [
            _event("SubagentStart", -35 * self.ONE_MINUTE_MS, agent_id="agt-before", agent_type="implementer"),
            _event("SubagentStop", -34 * self.ONE_MINUTE_MS, agent_id="agt-before", agent_type="implementer"),
            _event("SubagentStart", 31 * self.ONE_MINUTE_MS, agent_id="agt-after", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=2, total=2, percent=100, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, task_started_at_ms=BASE_TIME_MS,
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=self.STALE_AFTER_MS, tier1=tier1,
        )
        self.assertTrue(view.tier1_is_finished_task)
        is_previous_by_id = {run.agent_id: run.is_previous_task for run in view.agent_runs}
        self.assertTrue(is_previous_by_id["agt-before"])
        self.assertFalse(is_previous_by_id["agt-after"])

    def test_pt9_in_progress_tier1_without_sidecar_leaves_every_run_false(self) -> None:
        """RL8-(c) 회귀 표면(RL2 가 PT6 을 번복) — 사이드카가 없어(task_started_at_ms=None)
        작업 시작을 모르고, 프롬프트도 없으면(last_prompt_at_ms=None) 경계가 없다 — percent
        와 무관하게 전부 False 다. tier1_is_finished_task 는 여전히 percent<100 이라 False."""
        events = [
            _event("SubagentStart", -35 * self.ONE_MINUTE_MS, agent_id="agt-before", agent_type="implementer"),
            _event("SubagentStop", -34 * self.ONE_MINUTE_MS, agent_id="agt-before", agent_type="implementer"),
            _event("SubagentStart", 31 * self.ONE_MINUTE_MS, agent_id="agt-after", agent_type="implementer"),
        ]
        facts = _facts_from(events)
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=60, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS,
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=self.STALE_AFTER_MS, tier1=tier1,
        )
        self.assertFalse(view.tier1_is_finished_task)
        self.assertTrue(all(not run.is_previous_task for run in view.agent_runs))


class PreviousTaskBoundaryMsTest(unittest.TestCase):
    """RL8·RL10(docs/prps/hub-card-gate-and-run-list-reset.md §3.7) —
    previous_task_boundary_ms 의 네 갈래(순수 함수). PT1 을 대체한다(결정 RL2)."""

    def _tier1(self, percent, task_started_at_ms):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=percent, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, task_started_at_ms=task_started_at_ms,
        )

    def test_boundary_uses_task_start_while_task_in_progress(self) -> None:
        """반례 B — 작업이 진행 중이면 경계 = 작업 시작 시각, 마지막 프롬프트는 무시한다."""
        tier1 = self._tier1(percent=50, task_started_at_ms=200)
        result = hub_session.previous_task_boundary_ms(tier1, last_prompt_at_ms=900, is_dashboard_enabled=True)
        self.assertEqual(result, 200)

    def test_boundary_uses_later_of_task_start_and_prompt_when_finished(self) -> None:
        """RL8-(b) — 작업이 끝났으면 경계 = max(작업 시작, 마지막 프롬프트)."""
        tier1 = self._tier1(percent=100, task_started_at_ms=200)
        result = hub_session.previous_task_boundary_ms(tier1, last_prompt_at_ms=900, is_dashboard_enabled=True)
        self.assertEqual(result, 900)

    def test_boundary_uses_task_start_when_finished_without_prompt(self) -> None:
        """RL8-(b) 의 max — 프롬프트가 없으면 작업 시작 시각 그대로."""
        tier1 = self._tier1(percent=100, task_started_at_ms=200)
        result = hub_session.previous_task_boundary_ms(tier1, last_prompt_at_ms=None, is_dashboard_enabled=True)
        self.assertEqual(result, 200)

    def test_boundary_falls_back_to_prompt_without_tier1(self) -> None:
        """반례 A — 대시보드 자체가 없어도(워크트리 제거 등) 대시보드는 켜져 있으면
        마지막 프롬프트가 경계다."""
        result = hub_session.previous_task_boundary_ms(None, last_prompt_at_ms=900, is_dashboard_enabled=True)
        self.assertEqual(result, 900)

    def test_boundary_falls_back_to_prompt_without_sidecar(self) -> None:
        """RL8-(c) — tier1 은 있지만 사이드카가 없으면(task_started_at_ms=None) 마지막
        프롬프트로 폴백한다."""
        tier1 = self._tier1(percent=60, task_started_at_ms=None)
        result = hub_session.previous_task_boundary_ms(tier1, last_prompt_at_ms=900, is_dashboard_enabled=True)
        self.assertEqual(result, 900)

    def test_boundary_none_when_dashboard_disabled(self) -> None:
        """RL10/반례 B — 신호가 없고(tier1=None) 대시보드를 껐으면 경계 자체가 없다 —
        프롬프트로 추측하지 않는다(RL6 이 반려된 이유와 같다)."""
        result = hub_session.previous_task_boundary_ms(None, last_prompt_at_ms=900, is_dashboard_enabled=False)
        self.assertIsNone(result)

    def test_boundary_ignores_disabled_flag_when_dashboard_present(self) -> None:
        """RL10 범위 한정 — 스위치를 껐어도 그 작업의 사이드카가 실재하면 그 선언을 쓴다."""
        tier1 = self._tier1(percent=50, task_started_at_ms=200)
        result = hub_session.previous_task_boundary_ms(tier1, last_prompt_at_ms=900, is_dashboard_enabled=False)
        self.assertEqual(result, 200)

    def test_boundary_none_without_any_signal(self) -> None:
        """RL4 — 신호가 전부 없으면 페일오픈(경계 없음 → 아무것도 숨기지 않는다)."""
        result = hub_session.previous_task_boundary_ms(None, last_prompt_at_ms=None, is_dashboard_enabled=True)
        self.assertIsNone(result)

    def test_tier1_is_finished_task_unchanged(self) -> None:
        """RL5 회귀 — 실행 목록 경계가 RL8 로 바뀌어도 is_session_tier1_from_finished_task
        (클릭 게이트·CD1 승격용)의 판정식은 그대로다."""
        result = hub_session.is_session_tier1_from_finished_task(
            tier1_percent=100, tier1_file_mtime_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 31 * 60 * 1000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertTrue(result)


class SessionTaskStartedAtFieldTest(unittest.TestCase):
    """SessionView.task_started_at_ms — 세션 줄 첫 줄의 「작업 시작부터 소요」 근거
    (docs/prps/hub-session-row-layout-and-modal-size.md 결정 LM11). 경계는
    previous_task_boundary_ms 가 이미 정하고(결정 RL8·RL10), 그 값이 None 이면
    마지막 사람 입력 시각으로, 그것도 없으면 None 으로 둔다. 「프롬프트」는 훅 시각이 아니라
    transcript 꼬리에서 읽은 사람 입력 시각이다(last_human_prompt_at_ms — 알림에도 발화하는 훅 값을
    쓰면 시작 시각이 알림마다 바뀐다. 알림 쪽 회귀는 test_hub_human_prompt_boundary.py)."""

    PROMPT_OFFSET_MS = 10 * 60 * 1000
    DASHBOARD_TASK_START_MS = BASE_TIME_MS + 1000

    def _tier1(self, percent, task_started_at_ms):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=percent, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, task_started_at_ms=task_started_at_ms,
        )

    def _facts_with_two_prompts(self):
        return _facts_from([
            _event("UserPromptSubmit"),
            _event("UserPromptSubmit", offset_ms=self.PROMPT_OFFSET_MS),
        ])

    def _view(self, facts, tier1, is_dashboard_enabled=True, last_human_prompt_at_ms=BASE_TIME_MS + PROMPT_OFFSET_MS):
        return hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            tier1=tier1, is_dashboard_enabled=is_dashboard_enabled, last_human_prompt_at_ms=last_human_prompt_at_ms,
        )

    def test_running_dashboard_task_uses_the_dashboard_start_time(self) -> None:
        """진행 중인 대시보드 작업 — 프롬프트를 여러 번 거쳐도 시작은 대시보드가 남긴 작업 시작 시각이다."""
        view = self._view(self._facts_with_two_prompts(), self._tier1(50, self.DASHBOARD_TASK_START_MS))
        self.assertEqual(view.task_started_at_ms, self.DASHBOARD_TASK_START_MS)

    def test_finished_task_followed_by_a_new_prompt_uses_the_prompt_time(self) -> None:
        """끝난 작업 뒤 새 프롬프트 — 같은 세션에서 다른 작업을 시작했으므로 시작 시각이 그 프롬프트로 초기화된다."""
        view = self._view(self._facts_with_two_prompts(), self._tier1(100, self.DASHBOARD_TASK_START_MS))
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + self.PROMPT_OFFSET_MS)

    def test_session_without_dashboard_uses_the_last_prompt_time(self) -> None:
        """대시보드가 없으면 마지막 프롬프트가 작업의 시작이다."""
        view = self._view(self._facts_with_two_prompts(), tier1=None)
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + self.PROMPT_OFFSET_MS)

    def test_disabled_dashboard_falls_back_to_the_last_prompt_time(self) -> None:
        """대시보드를 껐으면 실행 목록 경계는 없지만(결정 RL10) 소요 시간은 마지막 프롬프트로 센다."""
        view = self._view(self._facts_with_two_prompts(), tier1=None, is_dashboard_enabled=False)
        self.assertEqual(view.task_started_at_ms, BASE_TIME_MS + self.PROMPT_OFFSET_MS)

    def test_session_without_prompt_or_dashboard_has_no_task_start(self) -> None:
        """사람 입력도 대시보드도 없으면 None — 화면은 세션 시작으로 되돌아간다."""
        facts = _facts_from([_event("SessionStart")])
        self.assertIsNone(self._view(facts, tier1=None, last_human_prompt_at_ms=None).task_started_at_ms)

    # ---- 작업 시작은 세션 시작보다 앞서지 않는다(끝나지 않은 채 남은 옛 대시보드 파일 대비) ----
    # 세션 시작 = 첫 훅 이벤트 시각 = BASE_TIME_MS(facts.started_at_ms).
    BEFORE_SESSION_START_MS = BASE_TIME_MS - 5 * 60 * 1000

    def test_running_dashboard_started_before_the_session_is_clamped_to_the_session_start(self) -> None:
        """진행 중 대시보드의 init 이 세션 시작보다 앞서면(옛 파일) 세션 시작으로 당긴다."""
        facts = self._facts_with_two_prompts()
        view = self._view(facts, self._tier1(50, self.BEFORE_SESSION_START_MS))
        self.assertEqual(view.task_started_at_ms, facts.started_at_ms)

    def test_running_dashboard_started_after_the_session_start_is_kept(self) -> None:
        """세션 시작 이후의 init 은 그대로다(회귀 방지)."""
        facts = self._facts_with_two_prompts()
        view = self._view(facts, self._tier1(50, self.DASHBOARD_TASK_START_MS))
        self.assertEqual(view.task_started_at_ms, self.DASHBOARD_TASK_START_MS)

    def test_boundary_equal_to_the_session_start_is_kept(self) -> None:
        """경계가 세션 시작과 같으면 그대로다."""
        facts = self._facts_with_two_prompts()
        view = self._view(facts, self._tier1(50, facts.started_at_ms))
        self.assertEqual(view.task_started_at_ms, facts.started_at_ms)

    def test_finished_task_boundary_before_the_session_start_is_clamped(self) -> None:
        """끝난 작업(b)에서 프롬프트가 없어 경계가 옛 init 에 머물면 세션 시작으로 당긴다."""
        facts = self._facts_with_two_prompts()
        view = self._view(facts, self._tier1(100, self.BEFORE_SESSION_START_MS), last_human_prompt_at_ms=None)
        self.assertEqual(view.task_started_at_ms, facts.started_at_ms)

    def test_human_prompt_fallback_before_the_session_start_is_clamped(self) -> None:
        """대시보드가 없어 사람 입력 시각으로 폴백하는 경우(c)도 세션 시작보다 앞서지 않는다."""
        facts = self._facts_with_two_prompts()
        view = self._view(facts, tier1=None, last_human_prompt_at_ms=self.BEFORE_SESSION_START_MS)
        self.assertEqual(view.task_started_at_ms, facts.started_at_ms)

    def test_clamp_keeps_none_when_there_is_no_candidate(self) -> None:
        """후보가 None 이면 None 그대로 — 화면이 세션 시작으로 폴백한다."""
        facts = _facts_from([_event("SessionStart")])
        self.assertIsNone(self._view(facts, tier1=None, last_human_prompt_at_ms=None).task_started_at_ms)

    def test_run_list_boundary_is_not_clamped(self) -> None:
        """실행 목록 경계는 원래 값이다 — 옛 init 과 세션 시작 사이에 시작한 끝난 실행은 이전 작업이 아니다."""
        facts = _facts_from([
            _event("SessionStart"),
            _event("SubagentStart", 1000, agent_id="agt-1", agent_type="implementer"),
            _event("SubagentStop", 2000, agent_id="agt-1", agent_type="implementer"),
        ])
        run_started_at_ms = BASE_TIME_MS - 60 * 1000       # 옛 init(-5분) 뒤, 세션 시작(0) 앞
        meta = hub_subagent.SubagentMeta(
            title="", agent_type="implementer", model=None, started_at_ms=run_started_at_ms,
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            tier1=self._tier1(50, self.BEFORE_SESSION_START_MS), is_dashboard_enabled=True,
            subagent_meta_by_agent_id={"agt-1": meta},
        )
        self.assertEqual(view.task_started_at_ms, facts.started_at_ms)
        self.assertFalse(view.agent_runs[0].is_previous_task)

    def test_field_sits_right_after_the_finished_task_flag_and_keeps_session_cost_last(self) -> None:
        """T25-150 — session_cost 가 맨 뒤(is_awaiting_approval·background_wait 가 그 앞)이고, 새 필드는 tier1_is_finished_task 바로 뒤다."""
        names = [field.name for field in dataclasses.fields(hub_session.SessionView)]
        self.assertEqual(names[-3:], ["background_wait", "is_awaiting_approval", "session_cost"])   # MN5 — 승인 대기 판정 필드가 그 사이에 든다
        self.assertEqual(names[names.index("tier1_is_finished_task") + 1], "task_started_at_ms")

    def test_field_is_serialized_into_the_snapshot_json(self) -> None:
        """화면은 스냅샷 JSON 으로 값을 받는다 — dataclasses.asdict 경로가 필드를 싣는다."""
        view = self._view(self._facts_with_two_prompts(), tier1=None)
        self.assertEqual(dataclasses.asdict(view)["task_started_at_ms"], BASE_TIME_MS + self.PROMPT_OFFSET_MS)


class RosterReconciliationTest(unittest.TestCase):
    """C1~C12 — docs/prps/hub-live-session-native-source.md §7.3, 결정 LS5 화해 표.

    표의 5행(unknown·not_listed·listed·busy·idle) × 훅 상태 조합(E·T·S)을 compute_session_view
    의 live_roster 인자로 검증한다. C7 이 "호스트가 훅을 대체한다"와 "둘을 OR 한다"를 가르는
    유일한 테스트다 — C6 은 짝이 아니라 자기 고유 역할(busy 가 turn ended 를 무시한다)을
    진다(검수 1회차 M5 — 실측: OR 합성 변조에서도 C6 은 통과한다. PRP §7.3 참조).
    """

    def _roster_index(self, session_id: str, is_busy: bool | None) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=is_busy)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _not_listed_index(self) -> hub_live_session.LiveSessionIndex:
        return hub_live_session.build_live_session_index([], is_complete=True)

    def test_c1_unknown_ended_matches_todays_judgement(self) -> None:
        """C1 — compute_session_view 는 항상 roster 를 명시적으로 계산해 넘기므로(never relies
        on _compute_base_state 의 기본값), 실제 변조 검출은 unknown 분기 자체다: 변조 검출:
        unknown 행의 "E→done" 체크를 지우면(직접 확인, 손 변조) 여기서 "working" 이 나와
        실패한다."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.base_state, "done")

    def test_c1_unknown_running_matches_todays_judgement(self) -> None:
        facts = _facts_from([_event("SessionStart"), _event("UserPromptSubmit", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.base_state, "working")

    def test_c2_not_listed_with_running_turn_is_idle(self) -> None:
        """C2 — 변조 검출: not_listed 행 삭제(→ working 이 나와 실패)."""
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._not_listed_index(),
        )
        self.assertEqual(view.base_state, "idle")

    def test_c3_not_listed_with_running_subagent_is_idle(self) -> None:
        """C3 — 변조 검출: S 항을 not_listed 행에서 살려 두면 working 이 나와 실패한다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._not_listed_index(),
        )
        self.assertEqual(view.base_state, "idle")

    def test_c4_not_listed_with_session_end_is_done(self) -> None:
        """C4 — 변조 검출: 부재를 무조건 idle 로 접으면(→ done 이 사라져 실패)."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", 1000)])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._not_listed_index(),
        )
        self.assertEqual(view.base_state, "done")

    def test_c5_busy_overrides_session_end_and_stays_working(self) -> None:
        """C5 — 변조 검출: 부활(E 무시) 삭제 → done."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("SessionEnd", 1000)])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=True),
        )
        self.assertEqual(view.base_state, "working")

    def test_c6_busy_overrides_hook_turn_ended(self) -> None:
        """C6 — 레코드 busy vs 훅 turn_state=="ended". 레코드가 이긴다(working). 자기 고유
        역할은 "busy 가 turn ended 를 무시한다"이다 — OR 합성 변조(status 가 turn_state 를
        대체하지 않고 OR 로만 합쳐지는 결함)는 이 케이스 단독으로는 못 잡는다(busy 자체가
        이미 working 이라 OR 이든 대체든 결과가 같다, 검수 1회차 M5 실측). 그 변조를 잡는
        것은 C7 이다."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000)])
        self.assertEqual(facts.turn_state, "ended")
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=True),
        )
        self.assertEqual(view.base_state, "working")

    def test_c7_idle_overrides_hook_turn_running(self) -> None:
        """C7 — 레코드 idle vs 훅 turn_state=="running". 이 표에서 OR 합성 변조(status 가
        turn_state 를 "대체"하지 않고 OR 로만 합쳐지는 결함)를 잡는 **유일한** 테스트다 —
        지우면 여기서 working 이 나와 실패한다(검수 1회차 M5 — C6 은 이 변조를 못 잡는다,
        그 docstring 참조)."""
        facts = _facts_from([_event("UserPromptSubmit")])
        self.assertEqual(facts.turn_state, "running")
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=False),
        )
        self.assertEqual(view.base_state, "idle")

    def test_c8_idle_with_running_subagent_is_working(self) -> None:
        """C8 — 결정 ZG7 보존. 변조 검출: S 항 삭제 시 실패."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=False),
        )
        self.assertEqual(view.base_state, "working")

    def test_c7b_idle_with_session_end_is_revived_to_idle(self) -> None:
        """C7b — 부활(E 무시)이 idle 행에도 있다. 표에서 E 를 무시하는 행은 busy·listed·idle
        셋인데 앞의 둘만 C5·C10 이 고정하고 있었다(검수 3회차 H1). idle 은 실측상 가장 자주
        타는 행이다 — 살아 있으면서 조용한 세션은 전부 status:"idle" 이므로, 여기서 부활이
        빠지면 결정 RV1~RV3 의 "done 은 표시일 뿐 사실이 아니다"가 지배 경로에서 무너진다.

        C10 과 같은 기법으로 Stop 을 선행시켜 T=0 을 만든다 — 그러지 않으면 T=running 이
        결과를 좌우해 E 무시를 단독으로 증명하지 못한다. 변조 검출: idle 행 앞에
        `if facts.ended_at_ms is not None: return "done"` 을 넣으면 여기서 done 이 나와
        실패한다(그 변조는 이 테스트가 없으면 803건을 전부 통과했다)."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000), _event("SessionEnd", 2000)])
        self.assertEqual(facts.turn_state, "ended")
        self.assertIsNotNone(facts.ended_at_ms)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=False),
        )
        self.assertEqual(view.base_state, "idle")

    def test_c9_listed_with_running_turn_is_working(self) -> None:
        """C9 — 변조 검출: listed 를 busy 로 접으면(항상 working) 이 테스트 자체는 우연히
        통과하지만 짝인 C9b 가 잡는다."""
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=None),
        )
        self.assertEqual(view.base_state, "working")

    def test_c9b_listed_with_ended_turn_and_no_subagent_is_idle(self) -> None:
        """C9b — C9 와 짝. 변조 검출: listed 를 busy 로 접으면 여기서 working 이 나와 실패한다."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000)])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=None),
        )
        self.assertEqual(view.base_state, "idle")

    def test_c9c_listed_with_ended_turn_and_running_subagent_is_working(self) -> None:
        """C9c(검수 1회차 M1) — listed 행의 판정은 (T∨S)→working 인데, S 항을 검증하는
        케이스가 없었다(C8 이 idle 행의 S 항은 지키지만 listed 행은 무방비). listed 는
        호스트가 status 키를 안 쓴 경우(실측 10%)라, 여기서 S 가 빠지면 "백그라운드
        서브에이전트가 도는데 glow 가 꺼진다"(ZG7 회귀)가 idle 행이 아니라 listed 행에서
        재발한다. 변조 검출: listed 행의 (T∨S) 에서 S 를 지우면(T 만 남으면) turn 이 이미
        끝난 상태라 idle 이 나와 실패한다."""
        events = [_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=None),
        )
        self.assertEqual(view.base_state, "working")

    def test_c10_listed_with_session_end_is_revived_to_idle(self) -> None:
        """C10 — 부활(E 무시)이 busy 행뿐 아니라 listed 행에도 있다. 훅 쪽 turn 은 미리 끝내둔다
        (Stop 선행) — 그러지 않으면 T=running 이 결과를 working 으로 만들어 E 무시를 증명하지
        못한다. 변조 검출: 부활을 busy 행에만 달면 여기서 done 이 나와 실패한다."""
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000), _event("SessionEnd", 2000)])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=None),
        )
        self.assertEqual(view.base_state, "idle")

    def test_c11_stale_overlay_ignores_roster(self) -> None:
        """C11 — 결정 LS9 회귀 가드. 변조 검출: is_stale 계산에 roster 를 섞으면 실패한다."""
        facts = _facts_from([_event("UserPromptSubmit")])
        thirty_one_minutes_later = facts.last_event_at_ms + 31 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms=thirty_one_minutes_later, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._roster_index(facts.session_id, is_busy=True),
        )
        self.assertEqual(view.state, "stale")
        self.assertEqual(view.base_state, "working")

    def test_c12_live_roster_defaults_to_none_for_existing_call_sites(self) -> None:
        """C12 — 변조 검출: 기본값을 없애면(필수 인자로 바뀌면) 호출부 전체가 TypeError 로 깨진다."""
        facts = _facts_from([_event("SessionStart"), _event("UserPromptSubmit", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "working")


class InterruptionLadderTest(unittest.TestCase):
    """I1~I13 — docs/prps/hub-rate-limit-interruption.md 결정 RI1~RI9 사다리 표 전체."""

    def _idle_roster(self, session_id: str) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=False)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _busy_roster(self, session_id: str) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=True)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _not_listed_roster(self) -> hub_live_session.LiveSessionIndex:
        return hub_live_session.build_live_session_index([], is_complete=True)

    def test_i1_hook_only_rate_limit_unknown_roster_is_interrupted(self) -> None:
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "interrupted")
        self.assertEqual(view.base_state, "idle")

    def test_i2_hook_only_with_running_subagent_is_interrupted_over_working(self) -> None:
        """RI3 — interrupted 는 working(좀비 아닌 미종료 실행)을 이긴다."""
        events = [
            _event("UserPromptSubmit", 0),
            _event("SubagentStart", 500, agent_id="agt-1", agent_type="code-reviewer"),
            _event("StopFailure", 1000, error_kind="rate_limit"),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "interrupted")
        self.assertEqual(view.base_state, "working")

    def test_i3_hook_only_busy_roster_is_interrupted_over_working(self) -> None:
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._busy_roster(facts.session_id),
        )
        self.assertEqual(view.state, "interrupted")
        self.assertEqual(view.base_state, "working")

    def test_i4_not_listed_roster_cancels_interruption(self) -> None:
        """RI4 — 명부 not_listed 는 취소한다(프로세스가 없다)."""
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._not_listed_roster(),
        )
        self.assertEqual(view.state, "idle")
        self.assertEqual(view.base_state, "idle")

    def test_i5_session_end_wins_over_interruption(self) -> None:
        events = [
            _event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit"),
            _event("SessionEnd", 2000),
        ]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")

    def test_i6_interruption_is_exempt_from_stale_overlay(self) -> None:
        """RI2 — interrupted 는 stale 보다 앞선 오버레이다. 2시간 뒤(stale 창 30분을 넘어도)
        여전히 interrupted 다."""
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        two_hours_later = facts.last_event_at_ms + 2 * 60 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms=two_hours_later, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "interrupted")

    def test_i7_non_rate_limit_error_only_closes_the_turn(self) -> None:
        """RI6 — rate_limit 만 interrupted 로 승격한다. 다른 오류는 턴만 닫아 대기로 보인다."""
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="authentication_failed")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "idle")

    def test_i8_transcript_only_failed_at_or_after_last_prompt_is_interrupted(self) -> None:
        events = [_event("UserPromptSubmit", 0)]
        facts = _facts_from(events)
        self.assertEqual(facts.turn_state, "running")
        turn_failure = hub_transcript.TranscriptTurnFailure(
            error_kind="rate_limit", failed_at_ms=facts.last_prompt_at_ms + 500, resets_at_ms=None
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            transcript_turn_failure=turn_failure,
        )
        self.assertEqual(view.state, "interrupted")
        self.assertEqual(view.base_state, "working")

    def test_i9_transcript_only_failed_before_last_prompt_is_invalidated(self) -> None:
        """R2 — 오류 뒤 사용자가 이미 다시 지시했다면 그 transcript 관측은 낡은 것이다."""
        events = [_event("UserPromptSubmit", 0)]
        facts = _facts_from(events)
        turn_failure = hub_transcript.TranscriptTurnFailure(
            error_kind="rate_limit", failed_at_ms=facts.last_prompt_at_ms - 500, resets_at_ms=None
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            transcript_turn_failure=turn_failure,
        )
        self.assertEqual(view.state, "working")

    def test_i10_transcript_wins_timestamp_and_resets_when_both_present(self) -> None:
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        turn_failure = hub_transcript.TranscriptTurnFailure(
            error_kind="rate_limit", failed_at_ms=facts.failed_turn.failed_at_ms + 50, resets_at_ms=999999
        )
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            transcript_turn_failure=turn_failure,
        )
        self.assertEqual(view.interruption.interrupted_at_ms, turn_failure.failed_at_ms)
        self.assertEqual(view.interruption.resets_at_ms, 999999)

    def test_i11_hook_only_has_no_resets_at(self) -> None:
        events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        facts = _facts_from(events)
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertIsNotNone(view.interruption)
        self.assertIsNone(view.interruption.resets_at_ms)

    def test_i12_interruption_field_matches_interrupted_state_invariant(self) -> None:
        """RI8 불변식(compute_session_view 가 강제) — interruption is not None ⇔
        state == "interrupted". 표의 대표 시나리오(interrupted·취소된 interrupted·done 이
        이김·평범한 working)를 모아 한 번에 확인한다."""
        interrupted_events = [_event("UserPromptSubmit", 0), _event("StopFailure", 1000, error_kind="rate_limit")]
        interrupted_facts = _facts_from(interrupted_events)
        views = [
            hub_session.compute_session_view(
                interrupted_facts, now_ms=interrupted_facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
            ),
            hub_session.compute_session_view(
                interrupted_facts, now_ms=interrupted_facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS,
                live_roster=self._not_listed_roster(),
            ),
            hub_session.compute_session_view(
                _facts_from(interrupted_events + [_event("SessionEnd", 2000)]),
                now_ms=BASE_TIME_MS + 2000, stale_after_ms=STALE_AFTER_MS,
            ),
            hub_session.compute_session_view(
                _facts_from([_event("UserPromptSubmit", 0)]), now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
            ),
        ]
        for view in views:
            with self.subTest(state=view.state):
                self.assertEqual(view.interruption is not None, view.state == "interrupted")

    def test_session_interruption_carries_exactly_two_integer_fields(self) -> None:
        """검수 1회차 MEDIUM ② — RI7 「hub.html 에 새로 인라인되는 값은 정수 2개
        (interrupted_at_ms·resets_at_ms)뿐, 종류 문자열도 싣지 않는다」계약을 고정한다.
        SessionInterruption 에 error_kind 등 세 번째 필드가 더해져도(예: 오류 종류를
        화면에 실으려는 변경) 지금까지의 다른 테스트는 그 필드를 그냥 무시해 조용히
        통과했다 — 필드 이름 튜플을 직접 고정해야 그 추가를 잡는다."""
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(hub_session.SessionInterruption)),
            ("interrupted_at_ms", "resets_at_ms"),
        )

    def test_i13_reproduced_incident_timeline_across_roster_variants(self) -> None:
        """§1.1 실측 재현(익명 fixture, 가짜 cwd) — 메인 턴이 한도로 끊기고, 좀비 서브에이전트
        가 SubagentStop 없이 남는다. 각 시점의 facts 는 그 시점까지 실제로 일어난 이벤트만으로
        접는다(now_ms 이후 이벤트를 미리 보지 않는다 — §1.1 재생 절차와 같은 원칙). 명부가
        unknown/idle 어느 쪽이어도 재개 전에는 interrupted, 재개(UserPromptSubmit) 뒤에는
        working 이다."""
        events_before_resume = [
            _event("SessionStart", 0),
            _event("UserPromptSubmit", 1000),
            _event("SubagentStart", 2000, agent_id="agt-zombie", agent_type="code-reviewer"),
            _event("StopFailure", 3000, error_kind="rate_limit"),
        ]
        events_after_resume = events_before_resume + [_event("UserPromptSubmit", 200000)]
        transcript_error = hub_transcript.TranscriptTurnFailure(
            error_kind="rate_limit", failed_at_ms=BASE_TIME_MS + 3000, resets_at_ms=None
        )
        facts_before = _facts_from(events_before_resume)
        facts_after = _facts_from(events_after_resume)

        roster_variants = {"unknown": None, "idle": self._idle_roster(facts_before.session_id)}
        for roster_label, roster in roster_variants.items():
            with self.subTest(roster=roster_label):
                view_1 = hub_session.compute_session_view(
                    facts_before, now_ms=BASE_TIME_MS + 50000, stale_after_ms=STALE_AFTER_MS,
                    live_roster=roster, transcript_turn_failure=transcript_error,
                )
                view_2 = hub_session.compute_session_view(
                    facts_before, now_ms=BASE_TIME_MS + 120000, stale_after_ms=STALE_AFTER_MS,
                    live_roster=roster, transcript_turn_failure=transcript_error,
                )
                view_3 = hub_session.compute_session_view(
                    facts_after, now_ms=BASE_TIME_MS + 200000, stale_after_ms=STALE_AFTER_MS,
                    live_roster=roster, transcript_turn_failure=transcript_error,
                )
                self.assertEqual(view_1.state, "interrupted")
                self.assertEqual(view_2.state, "interrupted")
                self.assertEqual(view_3.state, "working")


class BackgroundWaitLadderTest(unittest.TestCase):
    """L1~L16 — docs/prps/hub-subagent-background-pause.md 결정 BW4~BW6 사다리 표 전체
    (InterruptionLadderTest·RosterReconciliationTest 와 같은 관례로 명부를 주입한다)."""

    def _idle_roster(self, session_id: str) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=False)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _busy_roster(self, session_id: str) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=True)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _listed_roster(self, session_id: str) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=None)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _not_listed_roster(self) -> hub_live_session.LiveSessionIndex:
        return hub_live_session.build_live_session_index([], is_complete=True)

    def _minimal_facts(self, **overrides) -> hub_session_facts.SessionFacts:
        fields = dict(
            session_id="s1", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )
        fields.update(overrides)
        return hub_session_facts.SessionFacts(**fields)

    def test_l1_unknown_roster_shell_two_ten_minutes_is_background(self) -> None:
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(facts, now_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "background")
        self.assertEqual(view.base_state, "idle")
        self.assertEqual(
            view.background_wait,
            hub_session.BackgroundWait(
                facts.last_event_at_ms, facts.last_event_at_ms + hub_session.BACKGROUND_WAIT_MAX_MS, 2, 0,
            ),
        )

    def test_l2_idle_roster_is_background(self) -> None:
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "background")

    def test_l3_busy_roster_is_working_and_background_wait_is_none(self) -> None:
        """roster busy 는 base_state 를 working 으로 강제한다 — background 후보가 계산돼도
        state != "background" 라 되접힌다(BW9)."""
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._busy_roster(facts.session_id),
        )
        self.assertEqual(view.state, "working")
        self.assertIsNone(view.background_wait)

    def test_l4_not_listed_roster_cancels_background(self) -> None:
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._not_listed_roster(),
        )
        self.assertEqual(view.state, "idle")

    def test_l5_listed_roster_is_background(self) -> None:
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._listed_roster(facts.session_id),
        )
        self.assertEqual(view.state, "background")

    def test_l6_running_subagent_wins_over_background(self) -> None:
        """S(도는 서브에이전트)가 있으면 idle 명부에서도 base_state 가 working 이라
        background 오버레이가 끼어들 자리(base idle)가 없다."""
        events = [
            _event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer"),
            _event("Stop", 500, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS + 500, (("shell", 2),), 0)),
        ]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "working")

    def test_l7_thirty_one_minutes_is_background_not_stale(self) -> None:
        """§1.2 의 7/25 건이 고쳐지는 지점 — 오늘은 30분 문턱에서 stale 였다."""
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 31 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "background")

    def test_l8_ninety_minutes_exactly_expires_to_stale(self) -> None:
        """경계 `>=`(is_running_subagent 의 `<` 와 대응하는 반대쪽, BW6)."""
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 90 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "stale")
        self.assertEqual(view.base_state, "idle")

    def test_l9_one_ms_under_ninety_minutes_is_still_background(self) -> None:
        events = [_event("Stop", 0, background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0))]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + (90 * 60 * 1000 - 1)
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "background")

    def test_l10_only_non_waking_kinds_is_idle(self) -> None:
        """subagent·teammate·dream·unknown 은 깨우는 종류가 아니다(BW4) — 전부 0 으로
        합산돼 background 후보 자체가 서지 않는다."""
        report = hub_session_facts.BackgroundReport(
            BASE_TIME_MS, (("dream", 1), ("subagent", 1), ("teammate", 1), ("unknown", 1)), 0,
        )
        events = [_event("Stop", 0, background_report=report)]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "idle")

    def test_l11_zero_tasks_with_one_wakeup_is_background(self) -> None:
        report = hub_session_facts.BackgroundReport(BASE_TIME_MS, (), 1)
        events = [_event("Stop", 0, background_report=report)]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 10 * 60 * 1000
        view = hub_session.compute_session_view(
            facts, now_ms, stale_after_ms=STALE_AFTER_MS, live_roster=self._idle_roster(facts.session_id),
        )
        self.assertEqual(view.state, "background")
        self.assertEqual(view.background_wait.task_count, 0)
        self.assertEqual(view.background_wait.wakeup_count, 1)

    def test_l12_failed_turn_and_report_together_is_interrupted(self) -> None:
        """사실 직접 구성 — 실제 이벤트 재생으로는 failed_turn 과 background_report 가
        동시에 살아 있는 조합을 만들 수 없다(Stop·StopFailure 가 서로 다른 필드를
        지운다, BW3). 사다리 자체의 우선순위(interrupted > background)를 겨냥한
        구성이다."""
        facts = self._minimal_facts(
            last_event_name="StopFailure",
            failed_turn=hub_session_facts.FailedTurn("rate_limit", BASE_TIME_MS),
            background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0),
        )
        now_ms = BASE_TIME_MS + 10 * 60 * 1000
        view = hub_session.compute_session_view(facts, now_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "interrupted")
        self.assertIsNone(view.background_wait)

    def test_l13_ended_session_with_report_is_done(self) -> None:
        facts = self._minimal_facts(
            ended_at_ms=BASE_TIME_MS,
            background_report=hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0),
        )
        now_ms = BASE_TIME_MS + 10 * 60 * 1000
        view = hub_session.compute_session_view(facts, now_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view.state, "done")
        self.assertIsNone(view.background_wait)

    def test_l14_background_wait_invariant_holds_across_the_ladder(self) -> None:
        """BW9 불변식 — background_wait is not None ⇔ state == "background". L1~L13 이
        만든 대표 시나리오(background·취소된 background·working·interrupted·done)를
        모아 한 번에 확인한다(I12 와 같은 형태)."""
        shell_two = hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 2),), 0)
        background_events = [_event("Stop", 0, background_report=shell_two)]
        background_facts = _facts_from(background_events)
        ten_minutes_later = background_facts.last_event_at_ms + 10 * 60 * 1000
        views = [
            hub_session.compute_session_view(
                background_facts, ten_minutes_later, stale_after_ms=STALE_AFTER_MS,
                live_roster=self._idle_roster(background_facts.session_id),
            ),
            hub_session.compute_session_view(
                background_facts, ten_minutes_later, stale_after_ms=STALE_AFTER_MS,
                live_roster=self._not_listed_roster(),
            ),
            hub_session.compute_session_view(
                background_facts, ten_minutes_later, stale_after_ms=STALE_AFTER_MS,
                live_roster=self._busy_roster(background_facts.session_id),
            ),
            hub_session.compute_session_view(
                self._minimal_facts(
                    last_event_name="StopFailure",
                    failed_turn=hub_session_facts.FailedTurn("rate_limit", BASE_TIME_MS),
                    background_report=shell_two,
                ),
                ten_minutes_later, stale_after_ms=STALE_AFTER_MS,
            ),
            hub_session.compute_session_view(
                self._minimal_facts(ended_at_ms=BASE_TIME_MS, background_report=shell_two),
                ten_minutes_later, stale_after_ms=STALE_AFTER_MS,
            ),
        ]
        for view in views:
            with self.subTest(state=view.state):
                self.assertEqual(view.background_wait is not None, view.state == "background")

    def test_l15_reproduced_incident_timeline_across_checkpoints(self) -> None:
        """§1.1 실측 재생(익명 fixture, 가짜 cwd·id) — 사실을 이벤트로 다시 접지 않고
        각 시점에 "그때까지 접힌 사실이 이랬을 것"을 직접 구성한다(L12·L13 과 같은 이유
        — 정확한 초 단위 이벤트 재현은 이 표의 논지에 필요하지 않다). 13:36:03 의 Stop
        보고(shell:2) 이후 14:06(30분 문턱)에도 여전히 background 인 것이 §1.2 의
        7/25 건이 고쳐지는 지점이고, 14:08:30 재개(SubagentStart) 뒤에는 working, 재개가
        없었다고 가정하면 15:07(91분 뒤)에는 상한을 넘겨 stale 이다."""
        stop_report_at_ms = BASE_TIME_MS
        report = hub_session_facts.BackgroundReport(stop_report_at_ms, (("shell", 2),), 0)
        before_resume_facts = self._minimal_facts(last_event_at_ms=stop_report_at_ms, background_report=report)
        idle_roster = self._idle_roster("s1")

        four_minutes_later = stop_report_at_ms + 4 * 60 * 1000
        view_at_1340 = hub_session.compute_session_view(
            before_resume_facts, four_minutes_later, stale_after_ms=STALE_AFTER_MS, live_roster=idle_roster,
        )
        self.assertEqual(view_at_1340.state, "background")

        thirty_minutes_later = stop_report_at_ms + 30 * 60 * 1000
        view_at_1406 = hub_session.compute_session_view(
            before_resume_facts, thirty_minutes_later, stale_after_ms=STALE_AFTER_MS, live_roster=idle_roster,
        )
        self.assertEqual(view_at_1406.state, "background")

        resumed_at_ms = stop_report_at_ms + 32 * 60 * 1000
        after_resume_facts = self._minimal_facts(
            last_event_at_ms=resumed_at_ms,
            subagents=(hub_session_facts.SubagentFact("agt-1", "implementer", resumed_at_ms, None),),
            background_report=None,   # BW3 — SubagentStart 가 지운다
        )
        ten_seconds_after_resume = resumed_at_ms + 10 * 1000
        view_at_1408_40 = hub_session.compute_session_view(
            after_resume_facts, ten_seconds_after_resume, stale_after_ms=STALE_AFTER_MS, live_roster=idle_roster,
        )
        self.assertEqual(view_at_1408_40.state, "working")

        ninety_one_minutes_later = stop_report_at_ms + 91 * 60 * 1000   # 재개 없다고 가정
        view_at_1507 = hub_session.compute_session_view(
            before_resume_facts, ninety_one_minutes_later, stale_after_ms=STALE_AFTER_MS, live_roster=idle_roster,
        )
        self.assertEqual(view_at_1507.state, "stale")

    def test_l16_main_owned_shell_across_a_new_prompt(self) -> None:
        """§1.2 12:05→12:38 재생 — 메인 자신이 띄운 백그라운드 셸도 같은 결함을 낸다.
        명부는 "unknown"(live_roster 생략)으로 둔다 — roster=="idle" 은 status 가
        turn_state 를 대체해(LS5) 사용자의 실제 새 프롬프트(중간 시점의 turn_state=
        "running")를 덮어 버려 이 표의 논지("새 프롬프트가 오면 working 으로 돌아온다")를
        가릴 수 있다(구현 판단 — PRP §11 확인 대상은 아니다)."""
        first_stop_at_ms = BASE_TIME_MS
        first_report = hub_session_facts.BackgroundReport(first_stop_at_ms, (("shell", 1),), 0)
        before_prompt_facts = self._minimal_facts(last_event_at_ms=first_stop_at_ms, background_report=first_report)

        twenty_five_minutes_later = first_stop_at_ms + 25 * 60 * 1000
        view_at_1230 = hub_session.compute_session_view(before_prompt_facts, twenty_five_minutes_later, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view_at_1230.state, "background")

        prompt_at_ms = first_stop_at_ms + 33 * 60 * 1000
        after_prompt_facts = self._minimal_facts(
            last_event_at_ms=prompt_at_ms, turn_state="running",
            last_prompt_at_ms=prompt_at_ms, background_report=None,   # BW3 — UserPromptSubmit 가 지운다
        )
        five_seconds_after_prompt = prompt_at_ms + 5 * 1000
        view_at_1238_40 = hub_session.compute_session_view(after_prompt_facts, five_seconds_after_prompt, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view_at_1238_40.state, "working")

        second_stop_at_ms = prompt_at_ms + 60 * 1000
        empty_report = hub_session_facts.BackgroundReport(second_stop_at_ms, (), 0)
        after_second_stop_facts = self._minimal_facts(last_event_at_ms=second_stop_at_ms, background_report=empty_report)
        one_minute_after_second_stop = second_stop_at_ms + 60 * 1000
        view_at_1240 = hub_session.compute_session_view(after_second_stop_facts, one_minute_after_second_stop, stale_after_ms=STALE_AFTER_MS)
        self.assertEqual(view_at_1240.state, "idle")


class PassiveSubscriptionTest(unittest.TestCase):
    """PW-L1~L5·PW-G1 — docs/prps/hub-bg-wait-passive-watch.md 결정 PW1. 훅 종류 monitor(아티팩트 실시간
    감시처럼 호스트가 재개 때마다 다시 거는 끝나지 않는 구독)는 「백그라운드 대기」로 세지 않는다."""

    def _idle_roster(self, session_id: str) -> hub_live_session.LiveSessionIndex:
        record = hub_live_session.LiveSessionRecord(session_id=session_id, pid=1, is_busy=False)
        return hub_live_session.build_live_session_index([record], is_complete=True)

    def _stop_with(self, offset_ms: int, task_counts, wakeup_count: int = 0) -> hub_session_facts.HookEvent:
        report = hub_session_facts.BackgroundReport(BASE_TIME_MS + offset_ms, task_counts, wakeup_count)
        return _event("Stop", offset_ms, background_report=report)

    def _view_at(self, events, minutes_after_base: int) -> hub_session.SessionView:
        facts = _facts_from(events)
        return hub_session.compute_session_view(
            facts, BASE_TIME_MS + minutes_after_base * MINUTE_MS, stale_after_ms=STALE_AFTER_MS,
            live_roster=self._idle_roster(facts.session_id),
        )

    def test_pw_l1_monitor_only_report_is_idle(self) -> None:
        view = self._view_at([self._stop_with(0, (("monitor", 1),))], 10)

        self.assertEqual(view.state, "idle")
        self.assertIsNone(view.background_wait)

    def test_pw_l2_monitor_only_report_goes_stale_after_thirty_minutes(self) -> None:
        view = self._view_at([self._stop_with(0, (("monitor", 1),))], 31)

        self.assertEqual(view.state, "stale")

    def test_pw_l3_monitor_is_not_counted_next_to_shells(self) -> None:
        view = self._view_at([self._stop_with(0, (("monitor", 1), ("shell", 2)))], 10)

        self.assertEqual(view.state, "background")
        self.assertEqual(view.background_wait.task_count, 2)

    def test_pw_l4_monitor_with_one_shot_wakeup_counts_only_the_wakeup(self) -> None:
        view = self._view_at([self._stop_with(0, (("monitor", 1),), wakeup_count=1)], 10)

        self.assertEqual(view.state, "background")
        self.assertEqual(view.background_wait.task_count, 0)
        self.assertEqual(view.background_wait.wakeup_count, 1)

    def test_pw_l5_artifact_watch_session_replay(self) -> None:
        """사례 재생 — 매 턴 끝마다 monitor 1 이 보고돼도 진짜 셸이 남은 구간만 대기이고 나머지는 사용자 차례다."""
        monitor_only = (("monitor", 1),)
        events = [
            self._stop_with(0, monitor_only),
            _event("UserPromptSubmit", 4 * MINUTE_MS),
            self._stop_with(14 * MINUTE_MS, (("monitor", 1), ("shell", 1))),
            _event("UserPromptSubmit", 34 * MINUTE_MS),
            self._stop_with(35 * MINUTE_MS, monitor_only),
        ]
        events_until_shell_report = events[:3]

        view_at_1230 = self._view_at(events_until_shell_report, 24)
        view_at_1245 = self._view_at(events, 39)

        self.assertEqual(view_at_1230.state, "background")
        self.assertEqual(view_at_1245.state, "idle")

    def test_pw_g1_monitor_only_report_is_not_a_scan_target(self) -> None:
        facts = _facts_from([self._stop_with(0, (("monitor", 1),))])

        self.assertFalse(hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + 10 * MINUTE_MS))


class EffectiveBackgroundWaitTest(unittest.TestCase):
    """E1~E4 — `effective_background_wait` 단독 단위 테스트(사다리 나머지는 위
    BackgroundWaitLadderTest)."""

    def _facts_with_report(self, report: hub_session_facts.BackgroundReport | None) -> hub_session_facts.SessionFacts:
        return hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(), background_report=report,
        )

    def test_e1_custom_max_age_ms_boundary(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0))
        just_under = hub_session.effective_background_wait(facts, BASE_TIME_MS + 999, "idle", max_age_ms=1000)
        at_boundary = hub_session.effective_background_wait(facts, BASE_TIME_MS + 1000, "idle", max_age_ms=1000)
        self.assertIsNotNone(just_under)
        self.assertIsNone(at_boundary)

    def test_e2_until_ms_is_since_plus_max_age(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0))
        result = hub_session.effective_background_wait(facts, BASE_TIME_MS + 10, "idle")
        self.assertEqual(result.since_ms, BASE_TIME_MS)
        self.assertEqual(result.until_ms, BASE_TIME_MS + hub_session.BACKGROUND_WAIT_MAX_MS)

    def test_e3_no_report_is_none(self) -> None:
        facts = self._facts_with_report(None)
        self.assertIsNone(hub_session.effective_background_wait(facts, BASE_TIME_MS, "idle"))

    def test_e4_only_waking_kinds_are_summed(self) -> None:
        report = hub_session_facts.BackgroundReport(
            BASE_TIME_MS, (("dream", 5), ("monitor", 3), ("shell", 2), ("subagent", 7)), 0,
        )
        facts = self._facts_with_report(report)
        result = hub_session.effective_background_wait(facts, BASE_TIME_MS + 10, "idle")
        self.assertEqual(result.task_count, 2)   # shell 2 — monitor·dream·subagent 는 제외(BW4·PW1)


class BackgroundOutputScanGateTest(unittest.TestCase):
    """LA-V6(docs/prps/hub-live-activity.md 결정 LA7) — `waking_background_task_count`(effective_background_wait 와 같은 식을
    공유하도록 뽑은 함수)와 I/O 가 메인 기록을 열지 말지 정하는 순수 게이트 `is_background_output_scan_target`."""

    def _facts_with_report(self, report: hub_session_facts.BackgroundReport | None) -> hub_session_facts.SessionFacts:
        return hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(), background_report=report,
        )

    def test_waking_count_sums_only_waking_kinds(self) -> None:
        report = hub_session_facts.BackgroundReport(
            BASE_TIME_MS, (("dream", 5), ("monitor", 3), ("shell", 2), ("subagent", 7), ("workflow", 1)), 0,
        )

        self.assertEqual(hub_session.waking_background_task_count(report), 3)   # shell 2 + workflow 1

    def test_waking_count_of_no_report_is_zero(self) -> None:
        self.assertEqual(hub_session.waking_background_task_count(None), 0)

    def test_waking_count_matches_what_effective_background_wait_reports(self) -> None:
        report = hub_session_facts.BackgroundReport(BASE_TIME_MS, (("dream", 5), ("monitor", 3), ("shell", 2)), 0)
        wait = hub_session.effective_background_wait(self._facts_with_report(report), BASE_TIME_MS + 10, "idle")

        self.assertEqual(wait.task_count, hub_session.waking_background_task_count(report))

    def test_report_with_waking_tasks_is_a_scan_target(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0))

        self.assertTrue(hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + 10))

    def test_report_with_only_a_one_shot_wakeup_is_a_scan_target(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (), 1))

        self.assertTrue(hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + 10))

    def test_report_with_only_non_waking_kinds_is_not_a_scan_target(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (("subagent", 1),), 0))

        self.assertFalse(hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + 10))

    def test_no_report_is_not_a_scan_target(self) -> None:
        self.assertFalse(hub_session.is_background_output_scan_target(self._facts_with_report(None), BASE_TIME_MS))

    def test_expiry_boundary_is_inclusive_like_effective_background_wait(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0))
        max_age_ms = hub_session.BACKGROUND_WAIT_MAX_MS

        just_under = hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + max_age_ms - 1)
        at_boundary = hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + max_age_ms)

        self.assertTrue(just_under)
        self.assertFalse(at_boundary)

    def test_custom_max_age_is_honoured(self) -> None:
        facts = self._facts_with_report(hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0))

        self.assertFalse(hub_session.is_background_output_scan_target(facts, BASE_TIME_MS + 1000, max_age_ms=1000))


class LiveActivityViewTest(unittest.TestCase):
    """LA-V1~V5(docs/prps/hub-live-activity.md 결정 LA7·LA8·LA11) — 활동은 도는 실행에만 붙고, 백그라운드 출력은
    `background` 상태일 때만 뷰에 남으며, 어느 쪽도 상태 사다리를 바꾸지 않는다. LA-V7(SL-U10)은 위 테스트가 무수정으로 진다."""

    ONE_MINUTE_MS = 60 * 1000

    def _activity(self, **overrides) -> hub_activity.SubagentActivity:
        fields = dict(
            last_record_at_ms=BASE_TIME_MS + 5 * self.ONE_MINUTE_MS, last_tool_kind="read", pending_count=0,
            pending_tool_kind=None, pending_since_ms=None, recent_tool_counts=hub_activity.ToolKindCounts(read=2),
            recent_counts_since_ms=BASE_TIME_MS,
        )
        fields.update(overrides)
        return hub_activity.SubagentActivity(**fields)

    def _output(self) -> hub_activity.BackgroundOutputView:
        return hub_activity.BackgroundOutputView(file_count=1, updated_at_ms=BASE_TIME_MS + 1000, total_bytes=2048)

    def _running_facts(self):
        return _facts_from([_event("SubagentStart", 0, agent_id="agt-1", agent_type="implementer")])

    def _background_facts(self):
        report = hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0)
        return hub_session_facts.SessionFacts(
            session_id="session-1", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended", ended_at_ms=None,
            subagents=(), background_report=report,
        )

    def test_la_v1_only_a_running_run_carries_the_activity(self) -> None:
        events = [
            _event("SubagentStart", 0, agent_id="agt-running", agent_type="implementer"),
            _event("SubagentStart", 10, agent_id="agt-done", agent_type="code-reviewer"),
            _event("SubagentStop", 20, agent_id="agt-done", agent_type="code-reviewer"),
            _event("SubagentStart", 30, agent_id="agt-zombie", agent_type="design-architect"),
        ]
        facts = _facts_from(events)
        now_ms = facts.last_event_at_ms + 5 * self.ONE_MINUTE_MS
        zombie_started_ms = now_ms - hub_session.SUBAGENT_ZOMBIE_AFTER_MS - 1
        facts = dataclasses.replace(facts, subagents=tuple(
            dataclasses.replace(sub, started_at_ms=zombie_started_ms) if sub.agent_id == "agt-zombie" else sub
            for sub in facts.subagents
        ))
        activity_by_agent_id = {agent_id: self._activity() for agent_id in ("agt-running", "agt-done", "agt-zombie")}

        runs = hub_session.summarize_agent_runs(facts, now_ms, activity_by_agent_id=activity_by_agent_id)

        activity_by_run = {run.agent_id: run.activity for run in runs}
        self.assertIsNotNone(activity_by_run["agt-running"])
        self.assertIsNone(activity_by_run["agt-done"])
        self.assertIsNone(activity_by_run["agt-zombie"])

    def test_a_running_run_without_a_found_activity_has_none(self) -> None:
        facts = self._running_facts()

        runs = hub_session.summarize_agent_runs(facts, facts.last_event_at_ms, activity_by_agent_id={"someone-else": self._activity()})

        self.assertIsNone(runs[0].activity)

    def test_la_v2_stall_suspect_time_is_filled_from_the_views_own_start_time(self) -> None:
        facts = self._running_facts()
        resumed_at_ms = BASE_TIME_MS + 40 * self.ONE_MINUTE_MS
        meta = hub_subagent.SubagentMeta(title="", agent_type="implementer", model=None, started_at_ms=resumed_at_ms)
        activity = self._activity(last_record_at_ms=BASE_TIME_MS + 5 * self.ONE_MINUTE_MS)

        runs = hub_session.summarize_agent_runs(
            facts, resumed_at_ms + self.ONE_MINUTE_MS, subagent_meta_by_agent_id={"agt-1": meta},
            activity_by_agent_id={"agt-1": activity},
        )

        self.assertEqual(runs[0].started_at_ms, resumed_at_ms)
        self.assertEqual(runs[0].activity.stall_suspect_at_ms, resumed_at_ms + hub_activity.SUBAGENT_STALL_SUSPECT_AFTER_MS)

    def test_la_v2_a_pending_call_leaves_the_suspect_time_empty(self) -> None:
        facts = self._running_facts()
        activity = self._activity(pending_count=1, pending_tool_kind="run", pending_since_ms=BASE_TIME_MS)

        runs = hub_session.summarize_agent_runs(facts, facts.last_event_at_ms, activity_by_agent_id={"agt-1": activity})

        self.assertIsNone(runs[0].activity.stall_suspect_at_ms)

    def test_la_v3_an_absent_or_empty_live_activity_gives_todays_view(self) -> None:
        facts = self._running_facts()
        now_ms = facts.last_event_at_ms + self.ONE_MINUTE_MS

        without = hub_session.compute_session_view(facts, now_ms, STALE_AFTER_MS)
        with_none = hub_session.compute_session_view(facts, now_ms, STALE_AFTER_MS, live_activity=None)
        with_empty = hub_session.compute_session_view(
            facts, now_ms, STALE_AFTER_MS, live_activity=hub_activity.LiveActivity({}, {})
        )

        self.assertEqual(dataclasses.asdict(without), dataclasses.asdict(with_none))
        self.assertEqual(dataclasses.asdict(without), dataclasses.asdict(with_empty))
        self.assertIsNone(dataclasses.asdict(without)["agent_runs"][0]["activity"])

    def test_la_v3_new_fields_are_trailing_and_default_to_none(self) -> None:
        for view_class, expected_last in ((hub_session.SubagentRunView, "activity"), (hub_session.BackgroundWait, "output")):
            with self.subTest(view_class=view_class.__name__):
                last_field = dataclasses.fields(view_class)[-1]
                self.assertEqual(last_field.name, expected_last)
                self.assertIsNone(last_field.default)

    def test_activity_of_a_running_run_flows_through_compute_session_view(self) -> None:
        facts = self._running_facts()
        now_ms = facts.last_event_at_ms + self.ONE_MINUTE_MS
        live_activity = hub_activity.LiveActivity({"agt-1": self._activity()}, {})

        view = hub_session.compute_session_view(facts, now_ms, STALE_AFTER_MS, live_activity=live_activity)

        self.assertEqual(view.agent_runs[0].activity.last_tool_kind, "read")
        self.assertIsNotNone(view.agent_runs[0].activity.stall_suspect_at_ms)

    def test_la_v4_output_is_carried_when_the_state_is_background(self) -> None:
        facts = self._background_facts()
        live_activity = hub_activity.LiveActivity({}, {"session-1": self._output()})

        view = hub_session.compute_session_view(facts, BASE_TIME_MS + self.ONE_MINUTE_MS, STALE_AFTER_MS, live_activity=live_activity)

        self.assertEqual(view.state, "background")
        self.assertEqual(view.background_wait.output, self._output())

    def test_la_v4_output_never_makes_a_background_wait_out_of_nothing(self) -> None:
        facts = dataclasses.replace(self._background_facts(), background_report=None)
        live_activity = hub_activity.LiveActivity({}, {"session-1": self._output()})

        view = hub_session.compute_session_view(facts, BASE_TIME_MS + self.ONE_MINUTE_MS, STALE_AFTER_MS, live_activity=live_activity)

        self.assertIsNone(view.background_wait)

    def test_la_v4_output_is_dropped_when_the_state_is_not_background(self) -> None:
        running = self._running_facts()
        report = hub_session_facts.BackgroundReport(BASE_TIME_MS, (("shell", 1),), 0)
        facts = dataclasses.replace(running, background_report=report)
        live_activity = hub_activity.LiveActivity({}, {facts.session_id: self._output()})

        view = hub_session.compute_session_view(facts, facts.last_event_at_ms + self.ONE_MINUTE_MS, STALE_AFTER_MS, live_activity=live_activity)

        self.assertEqual(view.state, "working")
        self.assertIsNone(view.background_wait)

    def test_la_v4_effective_background_wait_without_output_has_none_output(self) -> None:
        wait = hub_session.effective_background_wait(self._background_facts(), BASE_TIME_MS + 1, "idle")

        self.assertIsNone(wait.output)

    def test_la_v5_a_stall_suspect_activity_does_not_change_any_state(self) -> None:
        facts = self._running_facts()
        now_ms = facts.last_event_at_ms + 30 * self.ONE_MINUTE_MS
        stalled = hub_activity.LiveActivity({"agt-1": self._activity(last_record_at_ms=BASE_TIME_MS)}, {})
        activity_by_mtime = {"agt-1": now_ms}

        plain = hub_session.compute_session_view(facts, now_ms, STALE_AFTER_MS, subagent_activity_by_agent_id=activity_by_mtime)
        with_stall = hub_session.compute_session_view(
            facts, now_ms, STALE_AFTER_MS, subagent_activity_by_agent_id=activity_by_mtime, live_activity=stalled
        )

        self.assertLess(with_stall.agent_runs[0].activity.stall_suspect_at_ms, now_ms)   # 표지는 켜질 조건이다
        self.assertEqual((with_stall.state, with_stall.base_state), (plain.state, plain.base_state))
        self.assertEqual(with_stall.last_event_at_ms, plain.last_event_at_ms)

    def test_session_view_gets_no_activity_field(self) -> None:
        """GOTCHA 3 — 활동은 SubagentRunView·BackgroundWait 에만 실린다. SessionView 에는 새 필드가 없다."""
        names = {field.name for field in dataclasses.fields(hub_session.SessionView)}

        self.assertFalse({name for name in names if "activity" in name})
        self.assertEqual(dataclasses.fields(hub_session.SessionView)[-3].name, "background_wait")   # MN5 — is_awaiting_approval 이 그 뒤에 낀다


class SessionCostWiringTest(unittest.TestCase):
    """⑨ — compute_session_view 가 statusLine 비용 캡처를 판단 없이 뷰에 싣는다(docs/prps/harness-benchmark-adoption.md §10-1)."""

    COST = hub_usage.SessionCost(captured_at_ms=BASE_TIME_MS, total_cost_cents=1284, api_duration_minutes=31, context_used_percent=62)

    def _facts(self):
        return _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000)])

    def test_default_is_none(self) -> None:
        facts = self._facts()
        view = hub_session.compute_session_view(facts, facts.last_event_at_ms, STALE_AFTER_MS)
        self.assertIsNone(view.session_cost)

    def test_given_cost_is_carried_as_is_and_serialized(self) -> None:
        facts = self._facts()
        view = hub_session.compute_session_view(facts, facts.last_event_at_ms, STALE_AFTER_MS, session_cost=self.COST)
        self.assertIs(view.session_cost, self.COST)
        self.assertEqual(dataclasses.asdict(view)["session_cost"]["total_cost_cents"], 1284)

    def test_cost_does_not_change_any_state_decision(self) -> None:
        facts = self._facts()
        plain = hub_session.compute_session_view(facts, facts.last_event_at_ms, STALE_AFTER_MS)
        with_cost = hub_session.compute_session_view(facts, facts.last_event_at_ms, STALE_AFTER_MS, session_cost=self.COST)
        self.assertEqual(dataclasses.replace(with_cost, session_cost=None), plain)


class IsAwaitingApprovalTest(unittest.TestCase):
    """MN5(docs/prps/hub-macos-notification.md) — 승인 대기 판정의 정본. AW1 표의 행 전부를 Python 단위로 잠근다
    (그동안 DOM D43 이 지던 규칙)."""

    @staticmethod
    def _tier1(is_approval_step_active: bool) -> hub_parse.Tier1Snapshot:
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="", completed=1, total=4, percent=25, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, is_approval_step_active=is_approval_step_active,
        )

    def test_idle_with_active_approval_step_is_true(self) -> None:
        self.assertTrue(hub_session.is_awaiting_approval("idle", "idle", self._tier1(True)))

    def test_background_over_idle_is_true(self) -> None:
        self.assertTrue(hub_session.is_awaiting_approval("background", "idle", self._tier1(True)))

    def test_stale_over_idle_is_true(self) -> None:
        self.assertTrue(hub_session.is_awaiting_approval("stale", "idle", self._tier1(True)))

    def test_stale_over_working_is_false(self) -> None:
        self.assertFalse(hub_session.is_awaiting_approval("stale", "working", self._tier1(True)))

    def test_working_is_false(self) -> None:
        self.assertFalse(hub_session.is_awaiting_approval("working", "working", self._tier1(True)))

    def test_interrupted_is_false(self) -> None:
        self.assertFalse(hub_session.is_awaiting_approval("interrupted", "idle", self._tier1(True)))

    def test_done_is_false(self) -> None:
        self.assertFalse(hub_session.is_awaiting_approval("done", "done", self._tier1(True)))

    def test_fact_off_is_false(self) -> None:
        self.assertFalse(hub_session.is_awaiting_approval("idle", "idle", self._tier1(False)))

    def test_no_tier1_is_false(self) -> None:
        self.assertFalse(hub_session.is_awaiting_approval("idle", "idle", None))

    def test_compute_session_view_carries_the_flag(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000)])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, tier1=self._tier1(True),
        )
        self.assertEqual((view.state, view.is_awaiting_approval), ("idle", True))

    def test_compute_session_view_is_false_without_tier1(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit"), _event("Stop", 1000)])
        view = hub_session.compute_session_view(facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS)
        self.assertFalse(view.is_awaiting_approval)

    def test_compute_session_view_is_false_while_working(self) -> None:
        facts = _facts_from([_event("UserPromptSubmit")])
        view = hub_session.compute_session_view(
            facts, now_ms=facts.last_event_at_ms, stale_after_ms=STALE_AFTER_MS, tier1=self._tier1(True),
        )
        self.assertFalse(view.is_awaiting_approval)


if __name__ == "__main__":
    unittest.main()
