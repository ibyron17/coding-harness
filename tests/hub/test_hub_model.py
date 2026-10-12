"""hub_model 단위 테스트. docs/prps/hub-dashboard.md 「테스트 계획」 M18~M19, M27~M29,
결정 U4~U5(BuildDashboardRegistryTest), U13(SnapshotContentKeyDashboardKeyTest),
결정 D3(UsageSnapshotContentKeyTest),
docs/prps/hub-session-tree-and-per-session-dashboards.md 「테스트 계획」 P11~P13(결정 ST14·ST15)."""

import dataclasses
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_account  # noqa: E402  (sys.path 조정 후 임포트)
import hub_activity  # noqa: E402
import hub_model  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_session  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_subagent  # noqa: E402
import hub_subagent_read  # noqa: E402
import hub_usage  # noqa: E402
import hub_workflow  # noqa: E402

try:
    from .live_activity_fixtures import (
        BASE_MS as ACTIVITY_BASE_MS,
        MINUTE_MS as ACTIVITY_MINUTE_MS,
        SECOND_MS as ACTIVITY_SECOND_MS,
        SENTINEL_INPUT,
        SENTINEL_OUTPUT,
        jsonl_bytes,
        line as activity_line,
        output_phrase,
        result_line,
        use_line,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from live_activity_fixtures import (  # noqa: E402
        BASE_MS as ACTIVITY_BASE_MS,
        MINUTE_MS as ACTIVITY_MINUTE_MS,
        SECOND_MS as ACTIVITY_SECOND_MS,
        SENTINEL_INPUT,
        SENTINEL_OUTPUT,
        jsonl_bytes,
        line as activity_line,
        output_phrase,
        result_line,
        use_line,
    )

BASE_TIME_MS = 1_786_000_000_000
HUB_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "hub" / "bin" / "hub_template.html"
DATA_MARKER_OPEN = '<script type="application/json" id="dzh-data">'


class RenderHubHtmlTest(unittest.TestCase):
    """M18~M19 — 데이터 마커 치환의 안전성과 정확성."""

    def _minimal_snapshot(self, prompt_excerpt="</script> 공격 시도"):
        session = hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=BASE_TIME_MS,
            state="working", base_state="working",
            last_event_at_ms=BASE_TIME_MS, task_excerpt=prompt_excerpt, agent_runs=(),
        )
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state="working",
            last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
        )
        return hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,),
            unresolved_dir_names=(), warnings=(),
        )

    def test_m18_script_closing_tag_survives_json_round_trip(self) -> None:
        """검수 M1 — HTML 엔티티가 아니라 JSON 유니코드 이스케이프를 써야 JSON.parse 후
        원문(&·<·> 포함)이 그대로 복원된다. <script> 내부는 raw text 라 엔티티가 복원되지 않는다."""
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        original_excerpt = "A & <b></script>attack</b>"
        rendered = hub_model.render_hub_html(template, self._minimal_snapshot(prompt_excerpt=original_excerpt))
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]

        self.assertNotIn("</script>", payload)
        self.assertNotIn("&lt;", payload)  # HTML 엔티티가 아니라 \uXXXX 이스케이프여야 한다

        parsed = json.loads(payload)
        round_tripped_excerpt = parsed["projects"][0]["sessions"][0]["task_excerpt"]
        self.assertEqual(round_tripped_excerpt, original_excerpt)

    def test_m19_marker_replaced_exactly_once_rest_untouched(self) -> None:
        template = (
            '<html><head><title>허브</title></head><body>'
            '<script type="application/json" id="dzh-data">PLACEHOLDER</script>'
            "</body></html>"
        )
        rendered = hub_model.render_hub_html(template, self._minimal_snapshot(prompt_excerpt="정상 문자열"))
        self.assertTrue(rendered.startswith('<html><head><title>허브</title></head><body>'))
        self.assertTrue(rendered.endswith("</script></body></html>"))
        inner = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        parsed = json.loads(inner)
        self.assertEqual(parsed["collected_at_ms"], BASE_TIME_MS)

    def test_case28_usage_none_snapshot_renders_json_null(self) -> None:
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, self._minimal_snapshot())
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        self.assertIn('"usage": null', payload)
        parsed = json.loads(payload)
        self.assertIsNone(parsed["usage"])

    def test_ac_account_none_renders_json_null_and_account_info_round_trips_escaped(self) -> None:
        """결정 AC2·AC8 — account 키가 #dzh-data 에 실리고(없으면 null), 값 안의 </script> 는
        유니코드 이스케이프를 거쳐 JSON.parse 로 원문 그대로 복원된다."""
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        without_account = hub_model.render_hub_html(template, self._minimal_snapshot())
        payload = without_account.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        self.assertIsNone(json.loads(payload)["account"])

        hostile_name = "Example </script><img src=x onerror=alert(1)>"
        account = hub_account.AccountInfo("Claude Team", hostile_name, "dev.user@example.com")
        snapshot = dataclasses.replace(self._minimal_snapshot(), account=account)
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        self.assertNotIn("</script>", payload)
        self.assertEqual(
            json.loads(payload)["account"],
            {"plan_label": "Claude Team", "organization_name": hostile_name, "email": "dev.user@example.com"},
        )

    def test_q3_session_json_contains_started_at_ms(self) -> None:
        """세션 식별(요구 3, §4.6 신규 ③) — 렌더된 #dzh-data 의 세션 객체에 started_at_ms 가 실린다."""
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, self._minimal_snapshot())
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        session_json = json.loads(payload)["projects"][0]["sessions"][0]
        self.assertEqual(session_json["started_at_ms"], BASE_TIME_MS)

    def test_sh_template_stamp_round_trips_through_dzh_data(self) -> None:
        """docs/prps/hub-ungated-poll-and-stale-tab-self-heal.md 전제 6 — #dzh-data 는
        HubSnapshot 을 그대로 담는다는 계약이 template_stamp 에도 성립한다(계약 A)."""
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        snapshot = dataclasses.replace(self._minimal_snapshot(), template_stamp="abc123def4567890")
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        self.assertEqual(json.loads(payload)["template_stamp"], "abc123def4567890")

    def test_p13_session_tier1_and_dashboard_key_reach_the_json_contract(self) -> None:
        """P13(hub-session-tree-and-per-session-dashboards.md, S3) — #dzh-data 의 sessions[0]
        에 tier1.session_id·dashboard_key 가 실린다."""
        session_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path="/repo", session_id="s1",
        )
        session = hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=BASE_TIME_MS,
            state="working", base_state="working", last_event_at_ms=BASE_TIME_MS,
            task_excerpt=None, agent_runs=(), tier1=session_tier1, dashboard_key="abc0000000000000",
        )
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state="working",
            last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=(),
        )
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        session_json = json.loads(payload)["projects"][0]["sessions"][0]
        self.assertEqual(session_json["tier1"]["session_id"], "s1")
        self.assertEqual(session_json["dashboard_key"], "abc0000000000000")


class BuildDashboardRegistryTest(unittest.TestCase):
    """U4~U5 — build_dashboard_registry 는 티어 1 프로젝트 요약과 각 세션 자신의 대시보드를 담고,
    값은 hub_project.tier1_file_path 의 출력이다(세션별 .claude/dashboards/<id>.jsonl —
    결정 ST13·ST14, docs/prps/hub-session-tree-and-per-session-dashboards.md). M2
    (dashboard-into-hub.md HD7)로 레거시 단일 파일 갈래가 폐기돼 값은 이제 항상 세션별
    경로다. U-17 — 승자가 워크트리 파일이면 값은 project.path 가 아니라 그 워크트리
    경로다(S5, 결정 WT8)."""

    _SESSION_ID = "f733cfcd-32eb-4339-9d99-e7375887e376"

    def _tier1(self, source_path: str, session_id: str = _SESSION_ID) -> hub_parse.Tier1Snapshot:
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path=source_path, session_id=session_id,
        )

    def _project_view(
        self, path: str, tier: int, tier1: hub_parse.Tier1Snapshot | None = None
    ) -> hub_project.ProjectView:
        return hub_project.ProjectView(
            display_name=path.rsplit("/", 1)[-1], path=path, tier=tier, state="idle",
            last_activity_at_ms=BASE_TIME_MS, sessions=(), tier1=tier1, note=None,
        )

    def test_u4_only_tier1_projects_are_registered(self) -> None:
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(
                self._project_view("/repo/one", tier=1, tier1=self._tier1("/repo/one")),
                self._project_view("/repo/two", tier=2),
                self._project_view("/repo/three", tier=3),
            ),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        self.assertEqual(len(registry), 1)
        self.assertIn(hub_project.project_dashboard_key("/repo/one"), registry)

    def test_u5_registry_value_is_dashboard_jsonl_path(self) -> None:
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(self._project_view("/repo/one", tier=1, tier1=self._tier1("/repo/one")),),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        key = hub_project.project_dashboard_key("/repo/one")
        self.assertEqual(registry[key], "/repo/one/.claude/dashboards/%s.jsonl" % self._SESSION_ID)

    def test_u17_registry_value_uses_worktree_source_path_when_it_wins(self) -> None:
        worktree_path = "/repo/one/.claude/worktrees/w"
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(self._project_view("/repo/one", tier=1, tier1=self._tier1(worktree_path)),),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        key = hub_project.project_dashboard_key("/repo/one")
        self.assertEqual(registry[key], worktree_path + "/.claude/dashboards/%s.jsonl" % self._SESSION_ID)

    def test_tier1_with_unset_source_path_is_excluded_defensively(self) -> None:
        """검토 지적 반영 — tier==1 인데 tier1.source_path 가 UNSET_SOURCE_PATH(계약 위반)로
        남으면 "" + "/.claude/dashboard.html" 이라는 엉뚱한 경로를 등록하지 않고 제외한다."""
        broken_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS,   # source_path 생략 → UNSET_SOURCE_PATH
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(self._project_view("/repo/one", tier=1, tier1=broken_tier1),),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        self.assertEqual(registry, {})

    def _session_view(
        self, session_id: str, tier1: hub_parse.Tier1Snapshot | None, dashboard_key: str | None
    ) -> hub_session.SessionView:
        return hub_session.SessionView(
            session_id=session_id, short_id=session_id[:8], started_at_ms=BASE_TIME_MS,
            state="working", base_state="working", last_event_at_ms=BASE_TIME_MS,
            task_excerpt=None, agent_runs=(), tier1=tier1, dashboard_key=dashboard_key,
        )

    def test_p11_session_dashboard_is_registered_under_its_own_key(self) -> None:
        """P11(hub-session-tree-and-per-session-dashboards.md) — 세션 키 → 세션 자신의
        대시보드 파일(결정 ST14)."""
        session_tier1 = self._tier1("/repo/one")
        session = self._session_view("s1", tier1=session_tier1, dashboard_key="abc0000000000000")
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(
                hub_project.ProjectView(
                    display_name="one", path="/repo/one", tier=2, state="working",
                    last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
                ),
            ),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        self.assertEqual(registry["abc0000000000000"], hub_project.tier1_file_path(session_tier1))

    def test_p11_project_winner_that_is_a_session_file_registers_that_file(self) -> None:
        """P11 — 프로젝트 요약 승자가 세션별 파일이면 프로젝트 키의 값도 그 세션 파일 경로다
        (결정 ST11·ST14)."""
        winner_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path="/repo/one", session_id="s1",
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(self._project_view("/repo/one", tier=1, tier1=winner_tier1),),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        key = hub_project.project_dashboard_key("/repo/one")
        self.assertEqual(registry[key], hub_project.tier1_file_path(winner_tier1))

    def test_p11_session_snapshot_with_unset_source_path_is_excluded(self) -> None:
        """P11 — UNSET_SOURCE_PATH 세션 스냅샷은 제외한다(ST14, 방어는 프로젝트·세션 경로
        모두에 적용된다)."""
        broken_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, session_id="s1",   # source_path 생략 → UNSET_SOURCE_PATH
        )
        session = self._session_view("s1", tier1=broken_tier1, dashboard_key="abc0000000000000")
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS,
            projects=(
                hub_project.ProjectView(
                    display_name="one", path="/repo/one", tier=2, state="working",
                    last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
                ),
            ),
            unresolved_dir_names=(), warnings=(),
        )
        registry = hub_model.build_dashboard_registry(snapshot)
        self.assertEqual(registry, {})


class SnapshotContentKeyTest(unittest.TestCase):
    """M27~M29 — collected_at_ms 를 뺀 안정적 키(쓰기 억제, 개정 쟁점 R3)."""

    def _session(self, state="working", base_state="working", started_at_ms=BASE_TIME_MS):
        return hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=started_at_ms,
            state=state, base_state=base_state,
            last_event_at_ms=BASE_TIME_MS, task_excerpt=None, agent_runs=(),
        )

    def _snapshot(
        self, collected_at_ms=BASE_TIME_MS, session_state="working", warnings=(),
        started_at_ms=BASE_TIME_MS,
    ):
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state=session_state,
            last_activity_at_ms=BASE_TIME_MS,
            sessions=(self._session(session_state, started_at_ms=started_at_ms),),
            tier1=None, note=None,
        )
        return hub_model.HubSnapshot(
            collected_at_ms=collected_at_ms, projects=(project,),
            unresolved_dir_names=(), warnings=warnings,
        )

    def test_m27_only_collected_at_ms_differs_same_key(self) -> None:
        key_a = hub_model.snapshot_content_key(self._snapshot(collected_at_ms=BASE_TIME_MS))
        key_b = hub_model.snapshot_content_key(self._snapshot(collected_at_ms=BASE_TIME_MS + 5000))
        self.assertEqual(key_a, key_b)

    def test_q3_started_at_ms_difference_changes_key(self) -> None:
        """§4.6 신규 ① — started_at_ms 가 다르면 키가 다르다(필드가 실제로 페이로드에 실렸다는 증명)."""
        key_a = hub_model.snapshot_content_key(self._snapshot(started_at_ms=BASE_TIME_MS))
        key_b = hub_model.snapshot_content_key(self._snapshot(started_at_ms=BASE_TIME_MS + 1000))
        self.assertNotEqual(key_a, key_b)

    def test_q3_started_at_ms_present_collected_at_ms_only_diff_same_key(self) -> None:
        """§4.6 신규 ② — started_at_ms 가 있어도 collected_at_ms 만 다르면 키는 같다("지금"
        파생값이 섞이지 않았다는 증명. D3 회귀 방지 테스트와 같은 형태)."""
        key_a = hub_model.snapshot_content_key(
            self._snapshot(collected_at_ms=BASE_TIME_MS, started_at_ms=BASE_TIME_MS)
        )
        key_b = hub_model.snapshot_content_key(
            self._snapshot(collected_at_ms=BASE_TIME_MS + 5000, started_at_ms=BASE_TIME_MS)
        )
        self.assertEqual(key_a, key_b)

    def test_m28_session_state_transition_changes_key(self) -> None:
        key_working = hub_model.snapshot_content_key(self._snapshot(session_state="working"))
        key_stale = hub_model.snapshot_content_key(self._snapshot(session_state="stale"))
        self.assertNotEqual(key_working, key_stale)

    def test_m29_warnings_only_difference_changes_key(self) -> None:
        key_clean = hub_model.snapshot_content_key(self._snapshot(warnings=()))
        key_warned = hub_model.snapshot_content_key(self._snapshot(warnings=("문제 발생",)))
        self.assertNotEqual(key_clean, key_warned)

    def test_sh4_template_stamp_only_difference_changes_key(self) -> None:
        """docs/prps/hub-ungated-poll-and-stale-tab-self-heal.md 결정 SH4 — template_stamp 가
        HubSnapshot 필드가 되어 쓰기 게이트(snapshot_content_key)에 자동 편입된다. 이 성질이
        없으면 템플릿만 바뀐 재기동 이후에도 hub.html 이 다시 쓰이지 않아 열려 있던 탭이
        영영 치유되지 않는다(전제 7 의 잠복 결함이 되살아난다)."""
        base = self._snapshot()
        key_a = hub_model.snapshot_content_key(dataclasses.replace(base, template_stamp="aaaaaaaaaaaaaaaa"))
        key_b = hub_model.snapshot_content_key(dataclasses.replace(base, template_stamp="bbbbbbbbbbbbbbbb"))
        self.assertNotEqual(key_a, key_b)

    def test_ac_account_only_difference_changes_key(self) -> None:
        """결정 AC8 — account 도 snapshot_content_key 에 편입돼, 계정이 바뀌면 hub.html 이 다시 쓰인다."""
        base = self._snapshot()
        account = hub_account.AccountInfo("Claude Team", "Example Labs", "dev.user@example.com")
        key_without = hub_model.snapshot_content_key(base)
        key_with = hub_model.snapshot_content_key(dataclasses.replace(base, account=account))
        self.assertNotEqual(key_without, key_with)


class UsageSnapshotContentKeyTest(unittest.TestCase):
    """케이스 26~27 — usage 필드와 snapshot_content_key 의 상호작용(결정 D3 회귀 방지)."""

    def _snapshot(self, collected_at_ms=BASE_TIME_MS, usage=None):
        return hub_model.HubSnapshot(
            collected_at_ms=collected_at_ms, projects=(), unresolved_dir_names=(),
            warnings=(), usage=usage,
        )

    def test_case26_usage_only_difference_changes_key(self) -> None:
        key_without_usage = hub_model.snapshot_content_key(self._snapshot(usage=None))
        key_with_usage = hub_model.snapshot_content_key(
            self._snapshot(usage=hub_usage.UsageSample(sampled_at_ms=BASE_TIME_MS, session_percent=10, weekly_percent=19))
        )
        self.assertNotEqual(key_without_usage, key_with_usage)

    def test_case27_collected_at_ms_only_difference_same_key_usage_present(self) -> None:
        """D3 회귀 방지 — usage 가 있어도 collected_at_ms 만 다르면 키는 같다(5초마다 재작성되지 않는다)."""
        usage = hub_usage.UsageSample(sampled_at_ms=BASE_TIME_MS, session_percent=10, weekly_percent=19)
        key_a = hub_model.snapshot_content_key(self._snapshot(collected_at_ms=BASE_TIME_MS, usage=usage))
        key_b = hub_model.snapshot_content_key(self._snapshot(collected_at_ms=BASE_TIME_MS + 5000, usage=usage))
        self.assertEqual(key_a, key_b)


class SnapshotContentKeyWorkflowTest(unittest.TestCase):
    """§11 — 중첩 dataclass(WorkflowRunView·WorkflowAgentView)가 asdict/json.dumps 를
    통과하고, snapshot_content_key 가 같은 입력에 같은 값을 준다(파생 "지금" 값이 섞이지
    않았다는 증명 — 결정 D2, docs/prps/hub-workflow-visibility.md)."""

    def _workflow(self, label: str = "설계") -> hub_workflow.WorkflowRunView:
        agent = hub_workflow.WorkflowAgentView(index=1, label=label, state="done")
        return hub_workflow.WorkflowRunView(agents=(agent,))

    def _snapshot(self, workflow=None) -> hub_model.HubSnapshot:
        session = hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=BASE_TIME_MS,
            state="working", base_state="working",
            last_event_at_ms=BASE_TIME_MS, task_excerpt=None, agent_runs=(),
            workflow=workflow,
        )
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state="working",
            last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
        )
        return hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,),
            unresolved_dir_names=(), warnings=(),
        )

    def test_render_hub_html_serializes_nested_workflow_dataclasses(self) -> None:
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, self._snapshot(workflow=self._workflow(label="구현")))
        start = rendered.index('id="dzh-data">') + len('id="dzh-data">')
        end = rendered.index("</script>", start)
        payload = json.loads(rendered[start:end])
        workflow_json = payload["projects"][0]["sessions"][0]["workflow"]
        self.assertEqual(workflow_json["agents"][0]["label"], "구현")

    def test_snapshot_content_key_changes_when_workflow_changes(self) -> None:
        key_without_workflow = hub_model.snapshot_content_key(self._snapshot(workflow=None))
        key_with_workflow = hub_model.snapshot_content_key(self._snapshot(workflow=self._workflow()))
        key_with_workflow_again = hub_model.snapshot_content_key(self._snapshot(workflow=self._workflow()))
        key_with_different_workflow = hub_model.snapshot_content_key(
            self._snapshot(workflow=self._workflow(label="다른 라벨"))
        )
        self.assertNotEqual(key_without_workflow, key_with_workflow)
        self.assertEqual(key_with_workflow, key_with_workflow_again)
        self.assertNotEqual(key_with_workflow, key_with_different_workflow)


class SnapshotContentKeySubagentRunTest(unittest.TestCase):
    """M6(재검수 1회차, 결정 AR6·D2, docs/prps/hub-agent-runs-and-prompt-source.md) —
    SnapshotContentKeyWorkflowTest 의 서브에이전트 실행 판. SubagentRunView 의
    started_at_ms·ended_at_ms 는 정적 절대 시각이어야 한다 — summarize_agent_runs 에 넘기는
    now_ms 가 몇 시간 벌어져도(종료된 실행이라 is_running 은 두 시각 모두 False) 결과가
    바이트 단위로 같아야 snapshot_content_key 도 같다. 파생 "경과 시간" 값이 뷰에 섞여
    들면 이 시험이 깨진다."""

    def _facts(self) -> hub_session_facts.SessionFacts:
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer",
            started_at_ms=BASE_TIME_MS, ended_at_ms=BASE_TIME_MS + 60_000,
        )
        return hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 60_000, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(subagent,),
        )

    def _snapshot(self, now_ms: int) -> hub_model.HubSnapshot:
        agent_runs = hub_session.summarize_agent_runs(self._facts(), now_ms=now_ms)
        session = hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=BASE_TIME_MS,
            state="idle", base_state="idle",
            last_event_at_ms=BASE_TIME_MS + 60_000, task_excerpt=None, agent_runs=agent_runs,
        )
        project = hub_project.ProjectView(
            display_name="coding-harness", path="/repo", tier=2, state="idle",
            last_activity_at_ms=BASE_TIME_MS + 60_000, sessions=(session,), tier1=None, note=None,
        )
        return hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=(),
        )

    def test_snapshot_content_key_is_stable_when_only_now_ms_differs(self) -> None:
        one_minute_after_start = BASE_TIME_MS + 60_000
        three_hours_after_start = BASE_TIME_MS + 3 * 60 * 60 * 1000
        snapshot_soon = self._snapshot(now_ms=one_minute_after_start)
        snapshot_much_later = self._snapshot(now_ms=three_hours_after_start)

        # 픽스처 자체가 실제로 실행 뷰를 만들어 내는지 먼저 확인한다 — 둘 다 종료된 실행이라
        # is_running 은 now_ms 와 무관하게 항상 False 여야 한다(is_running_subagent 계약).
        self.assertEqual(len(snapshot_soon.projects[0].sessions[0].agent_runs), 1)
        self.assertFalse(snapshot_soon.projects[0].sessions[0].agent_runs[0].is_running)
        self.assertFalse(snapshot_much_later.projects[0].sessions[0].agent_runs[0].is_running)

        self.assertEqual(
            hub_model.snapshot_content_key(snapshot_soon),
            hub_model.snapshot_content_key(snapshot_much_later),
        )


class LiveActivityCanaryTest(unittest.TestCase):
    """LA-M1(docs/prps/hub-live-activity.md §9.3 카나리, G4) — 합성 기록의 명령·출력·본문·도구 이름·경로가 `read_live_activity` →
    `compose_project_views` → `render_hub_html` 어디에도 새지 않는다. 구조 값(시각·개수·종류)만 화면 데이터에 실린다."""

    SENTINEL_TEXT = "SENTINEL-TXT"
    SENTINEL_THOUGHT = "SENTINEL-THOUGHT"
    SENTINEL_TOOL = "mcp__SENTINELSRV__x"
    CWD = "/repo/canary"
    RUN_SESSION_ID = "sess-canary-run"
    WAIT_SESSION_ID = "sess-canary-wait"
    NOW_MS = ACTIVITY_BASE_MS

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.projects_dir = self.temp_dir / "projects"
        self.host_tmp_dir = self.temp_dir / "host_tmp"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write(self, path: Path, *lines: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(jsonl_bytes(*lines))

    def _output_file(self, session_id: str, task_id: str) -> None:
        output_path = self.host_tmp_dir / session_id / "tasks" / f"{task_id}.output"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"y" * 64)

    def _phrase_result(self, session_id: str, task_id: str, offset_ms: int, use_id: str) -> dict:
        body = f"{SENTINEL_OUTPUT} " + output_phrase(session_id, task_id, root=str(self.host_tmp_dir))
        return result_line(self.NOW_MS - offset_ms, use_id, body)

    def _facts(self, session_id: str, subagents: tuple, report=None):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=self.CWD, observed_cwds=(self.CWD,), started_at_ms=self.NOW_MS - 3_600_000,
            last_event_at_ms=self.NOW_MS - ACTIVITY_MINUTE_MS, last_event_name="Stop" if report else "SubagentStart",
            turn_state="ended", ended_at_ms=None, subagents=subagents, background_report=report,
        )

    def _scenario_facts(self) -> tuple:
        running = hub_session_facts.SubagentFact(
            agent_id="agt-canary", agent_type="implementer", started_at_ms=self.NOW_MS - 10 * ACTIVITY_MINUTE_MS, ended_at_ms=None,
        )
        report = hub_session_facts.BackgroundReport(self.NOW_MS - 5 * ACTIVITY_MINUTE_MS, (("shell", 1),), 0)
        return self._facts(self.RUN_SESSION_ID, (running,)), self._facts(self.WAIT_SESSION_ID, (), report)

    def _write_scenario_files(self) -> None:
        self._output_file(self.RUN_SESSION_ID, "abc")
        self._output_file(self.WAIT_SESSION_ID, "wait1")
        agent_dir = self.projects_dir / hub_project.encode_project_dir_name(self.CWD) / self.RUN_SESSION_ID / hub_subagent.SUBAGENT_DIR_NAME
        self._write(
            agent_dir / "agent-agt-canary.jsonl",
            activity_line("assistant", self.NOW_MS - 90 * ACTIVITY_SECOND_MS, [{"type": "thinking", "thinking": self.SENTINEL_THOUGHT}]),
            activity_line("assistant", self.NOW_MS - 80 * ACTIVITY_SECOND_MS, [{"type": "text", "text": self.SENTINEL_TEXT}]),
            use_line(self.NOW_MS - 70 * ACTIVITY_SECOND_MS, "u-mcp", self.SENTINEL_TOOL),
            result_line(self.NOW_MS - 60 * ACTIVITY_SECOND_MS, "u-mcp"),
            use_line(self.NOW_MS - 50 * ACTIVITY_SECOND_MS, "u-bash", "Bash"),
            self._phrase_result(self.RUN_SESSION_ID, "abc", 40 * ACTIVITY_SECOND_MS, "u-bash"),
            use_line(self.NOW_MS - 30 * ACTIVITY_SECOND_MS, "u-pending", "Bash"),
        )
        main_path = self.projects_dir / hub_project.encode_project_dir_name(self.CWD) / f"{self.WAIT_SESSION_ID}.jsonl"
        self._write(main_path, self._phrase_result(self.WAIT_SESSION_ID, "wait1", 20 * ACTIVITY_SECOND_MS, "toolu_wait1"))

    def _rendered_payload_and_views(self) -> tuple[str, tuple]:
        self._write_scenario_files()
        run_facts, wait_facts = self._scenario_facts()
        sessions_by_path = {self.CWD: (run_facts, wait_facts)}
        live_activity = hub_subagent_read.read_live_activity(sessions_by_path, self.projects_dir, self.NOW_MS, {})
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path=sessions_by_path, tier3_last_activity_by_path={},
            now_ms=self.NOW_MS, stale_after_ms=30 * ACTIVITY_MINUTE_MS, live_activity=live_activity,
        )
        snapshot = hub_model.HubSnapshot(collected_at_ms=self.NOW_MS, projects=views, unresolved_dir_names=(), warnings=())
        template = HUB_TEMPLATE_PATH.read_text(encoding="utf-8")
        return hub_model.render_hub_html(template, snapshot), views

    def test_la_m1_no_content_path_or_tool_name_reaches_the_rendered_page(self) -> None:
        rendered, _ = self._rendered_payload_and_views()
        # 경로 토큰은 데이터 페이로드(#dzh-data)에서만 본다 — 페이지 전체에는 템플릿 JS 가 있고, 그 JS 가
        # `background_wait.output` 같은 필드 이름을 읽을 수 있어(M4) 경로 토큰이 우연히 들어올 수 있다.
        payload_text = rendered.split(DATA_MARKER_OPEN, 1)[1].split("</script>", 1)[0]
        self.assertIn('"background_output"', payload_text)   # 페이로드를 제대로 잘랐다는 확인(빈 조각이면 아래가 헛통과한다)

        for leaked in (
            "SENTINEL", SENTINEL_INPUT, SENTINEL_OUTPUT, self.SENTINEL_TEXT, self.SENTINEL_THOUGHT, self.SENTINEL_TOOL,
            str(self.host_tmp_dir), str(self.temp_dir),
        ):
            with self.subTest(whole_page=leaked):
                self.assertNotIn(leaked, rendered)
        for leaked_path_token in ("/tasks/", ".output"):
            with self.subTest(payload_only=leaked_path_token):
                self.assertNotIn(leaked_path_token, payload_text)

    def test_la_m1_the_structure_values_are_what_reaches_the_views(self) -> None:
        _, views = self._rendered_payload_and_views()

        sessions = {session.session_id: session for project in views for session in project.sessions}
        activity = sessions[self.RUN_SESSION_ID].agent_runs[0].activity
        self.assertEqual((activity.pending_count, activity.pending_tool_kind, activity.last_tool_kind), (1, "run", "run"))
        self.assertEqual(activity.recent_tool_counts, hub_activity.ToolKindCounts(run=2, other=1))
        self.assertEqual(activity.background_output.file_count, 1)
        wait_session = sessions[self.WAIT_SESSION_ID]
        self.assertEqual(wait_session.state, "background")
        self.assertEqual((wait_session.background_wait.output.file_count, wait_session.background_wait.output.total_bytes), (1, 64))

    def test_la_m1_every_string_in_the_activity_payload_is_a_closed_tool_kind_literal(self) -> None:
        _, views = self._rendered_payload_and_views()

        run = next(session for project in views for session in project.sessions if session.session_id == self.RUN_SESSION_ID).agent_runs[0]
        payload = dataclasses.asdict(run)["activity"]
        strings = []

        def collect_strings(value) -> None:
            if isinstance(value, str):
                strings.append(value)
            elif isinstance(value, dict):
                for item in value.values():
                    collect_strings(item)

        collect_strings(payload)
        self.assertEqual(set(strings) - set(hub_activity.TOOL_KINDS), set())
        self.assertTrue(strings)


class SnapshotContentKeyLiveActivityTest(unittest.TestCase):
    """LA-M2(결정 LA11, G6) — 아무것도 안 돌 때 키는 오늘과 같고(쓰기 억제가 산다), 활동이 바뀌면 키도 바뀐다."""

    def _snapshot(self, live_activity) -> hub_model.HubSnapshot:
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        facts = hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="SubagentStart", turn_state="ended",
            ended_at_ms=None, subagents=(subagent,),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (facts,)}, tier3_last_activity_by_path={},
            now_ms=BASE_TIME_MS + 60_000, stale_after_ms=30 * 60 * 1000, live_activity=live_activity,
        )
        return hub_model.HubSnapshot(collected_at_ms=BASE_TIME_MS, projects=views, unresolved_dir_names=(), warnings=())

    def _activity(self, last_record_at_ms: int) -> hub_activity.SubagentActivity:
        return hub_activity.SubagentActivity(
            last_record_at_ms=last_record_at_ms, last_tool_kind="read", pending_count=0, pending_tool_kind=None,
            pending_since_ms=None, recent_tool_counts=hub_activity.ToolKindCounts(read=1), recent_counts_since_ms=BASE_TIME_MS,
        )

    def test_la_m2_no_live_activity_and_an_empty_one_give_the_same_key(self) -> None:
        key_none = hub_model.snapshot_content_key(self._snapshot(None))
        key_empty = hub_model.snapshot_content_key(self._snapshot(hub_activity.LiveActivity({}, {})))

        self.assertEqual(key_none, key_empty)

    def test_la_m2_the_same_activity_gives_the_same_key_even_when_collected_later(self) -> None:
        live_activity = hub_activity.LiveActivity({"agt-1": self._activity(BASE_TIME_MS + 1000)}, {})
        earlier = self._snapshot(live_activity)
        later = dataclasses.replace(self._snapshot(live_activity), collected_at_ms=BASE_TIME_MS + 5000)

        self.assertEqual(hub_model.snapshot_content_key(earlier), hub_model.snapshot_content_key(later))

    def test_la_m2_a_different_record_time_gives_a_different_key(self) -> None:
        first = self._snapshot(hub_activity.LiveActivity({"agt-1": self._activity(BASE_TIME_MS + 1000)}, {}))
        second = self._snapshot(hub_activity.LiveActivity({"agt-1": self._activity(BASE_TIME_MS + 2000)}, {}))

        self.assertNotEqual(hub_model.snapshot_content_key(first), hub_model.snapshot_content_key(second))


class SnapshotContentKeyDashboardKeyTest(unittest.TestCase):
    """U13 — dashboard_key 필드 추가 후에도 snapshot_content_key 가 같은 입력에 결정적이다."""

    def _snapshot(self) -> hub_model.HubSnapshot:
        project = hub_project.ProjectView(
            display_name="repo", path="/repo", tier=1, state="idle",
            last_activity_at_ms=BASE_TIME_MS, sessions=(), tier1=None, note=None,
            dashboard_key=hub_project.project_dashboard_key("/repo"),
        )
        return hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=(project,), unresolved_dir_names=(), warnings=(),
        )

    def test_u13_same_input_yields_same_key(self) -> None:
        self.assertEqual(
            hub_model.snapshot_content_key(self._snapshot()),
            hub_model.snapshot_content_key(self._snapshot()),
        )


class SessionTier1SnapshotContentKeyTest(unittest.TestCase):
    """P12(hub-session-tree-and-per-session-dashboards.md) — 세션 tier1 이 실린 스냅샷에서도
    snapshot_content_key 가 결정적이다(결정 ST15). collected_at_ms 만 다르면 같은 키,
    updated_text 가 다르면 다른 키."""

    def _snapshot(self, collected_at_ms=BASE_TIME_MS, updated_text="-") -> hub_model.HubSnapshot:
        session_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text=updated_text,
            file_mtime_ms=BASE_TIME_MS, source_path="/repo", session_id="s1",
        )
        session = hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=BASE_TIME_MS,
            state="working", base_state="working", last_event_at_ms=BASE_TIME_MS,
            task_excerpt=None, agent_runs=(), tier1=session_tier1,
            dashboard_key=hub_project.dashboard_file_key(hub_project.tier1_file_path(session_tier1)),
        )
        project = hub_project.ProjectView(
            display_name="repo", path="/repo", tier=2, state="working",
            last_activity_at_ms=BASE_TIME_MS, sessions=(session,), tier1=None, note=None,
        )
        return hub_model.HubSnapshot(
            collected_at_ms=collected_at_ms, projects=(project,),
            unresolved_dir_names=(), warnings=(),
        )

    def test_only_collected_at_ms_differs_same_key(self) -> None:
        key_a = hub_model.snapshot_content_key(self._snapshot(collected_at_ms=BASE_TIME_MS))
        key_b = hub_model.snapshot_content_key(self._snapshot(collected_at_ms=BASE_TIME_MS + 5000))
        self.assertEqual(key_a, key_b)

    def test_updated_text_difference_changes_key(self) -> None:
        key_a = hub_model.snapshot_content_key(self._snapshot(updated_text="2026-08-20 00:00"))
        key_b = hub_model.snapshot_content_key(self._snapshot(updated_text="2026-08-20 00:05"))
        self.assertNotEqual(key_a, key_b)


if __name__ == "__main__":
    unittest.main()
