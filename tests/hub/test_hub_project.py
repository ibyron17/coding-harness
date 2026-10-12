"""hub_project 단위 테스트. docs/prps/hub-dashboard.md 「테스트 계획」 M12~M20,
docs/prps/hub-session-revival-and-stale-tier1.md 결정 GN1~GN4(테스트 GN1~GN10),
쟁점 3(Tier1PriorityTest), 결정 N1(ProjectDashboardKeyTest), 결정 N3(ComposeProjectViewsDashboardKeyTest),
docs/prps/hub-session-tree-and-per-session-dashboards.md 「테스트 계획」 P1~P6(결정 ST9·ST12·ST13·ST14)."""

import dataclasses
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402  (sys.path 조정 후 임포트)
import hub_model  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_session  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_transcript  # noqa: E402
import hub_usage  # noqa: E402
import hub_workflow  # noqa: E402

STALE_AFTER_MS = 30 * 60 * 1000
BASE_TIME_MS = 1_786_000_000_000


class Tier1GenerationTest(unittest.TestCase):
    """GN1~GN10 — docs/prps/hub-session-revival-and-stale-tier1.md 결정 GN1~GN4."""

    def _session_facts(self, session_id, started_at_ms, ended_at_ms=None):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd="/repo", observed_cwds=("/repo",), started_at_ms=started_at_ms,
            last_event_at_ms=started_at_ms, last_event_name="UserPromptSubmit",
            turn_state="running" if ended_at_ms is None else "ended",
            ended_at_ms=ended_at_ms, subagents=(),
        )

    def _tier1(self, file_mtime_ms):
        # source_path="/repo" — 이 클래스의 모든 세션이 cwd="/repo" 를 쓴다(결정 WT18 GN
        # 재개정으로 tier1_source_path 가 facts.observed_cwds 에 있어야 판정 집합에 들어간다).
        # 워크트리 없는 프로젝트에서는 완전한 무동작이라는 결정 WT9 의 전제를 여기서 명시적으로
        # 재현한다.
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=file_mtime_ms, source_path="/repo",
        )

    def test_gn1_no_live_sessions_is_false(self) -> None:
        self.assertFalse(hub_project.is_tier1_from_previous_task(BASE_TIME_MS, ()))

    def test_gn2_live_session_started_after_mtime_is_true(self) -> None:
        self.assertTrue(hub_project.is_tier1_from_previous_task(BASE_TIME_MS, (BASE_TIME_MS + 1,)))

    def test_gn3_live_session_started_before_mtime_is_false(self) -> None:
        self.assertFalse(hub_project.is_tier1_from_previous_task(BASE_TIME_MS, (BASE_TIME_MS - 1,)))

    def test_gn4_one_earlier_session_among_many_makes_it_false(self) -> None:
        self.assertFalse(
            hub_project.is_tier1_from_previous_task(BASE_TIME_MS, (BASE_TIME_MS - 1, BASE_TIME_MS + 1))
        )

    def test_gn5_boundary_equal_start_and_mtime_is_false(self) -> None:
        """경계는 엄격한 > 다 — 같은 밀리초면 그 세션이 갱신했다고 본다."""
        self.assertFalse(hub_project.is_tier1_from_previous_task(BASE_TIME_MS, (BASE_TIME_MS,)))

    def test_gn6_compose_project_views_marks_previous_task(self) -> None:
        tier1 = self._tier1(BASE_TIME_MS)
        working_session = self._session_facts("s-working", BASE_TIME_MS + 60_000)
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1}, sessions_by_path={"/repo": (working_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertTrue(views[0].tier1_is_previous_task)

    def test_gn7_zombie_stale_session_does_not_break_the_verdict(self) -> None:
        """atlas 실측 형태(G5) — stale 좀비 세션이 있어도 working 세션 하나로 판정이 켜진다."""
        tier1 = self._tier1(BASE_TIME_MS)
        working_session = self._session_facts("s-working", BASE_TIME_MS + 60_000)
        zombie_session = self._session_facts("s-zombie", BASE_TIME_MS - 3_600_000)
        now_ms = zombie_session.started_at_ms + STALE_AFTER_MS + 60_000
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1},
            sessions_by_path={"/repo": (working_session, zombie_session)},
            tier3_last_activity_by_path={}, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
        )
        zombie_view = next(view for view in views[0].sessions if view.session_id == "s-zombie")
        self.assertEqual(zombie_view.state, "stale")
        self.assertTrue(views[0].tier1_is_previous_task)

    def test_gn8_no_tier1_is_false(self) -> None:
        working_session = self._session_facts("s-working", BASE_TIME_MS + 60_000)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (working_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertFalse(views[0].tier1_is_previous_task)

    def test_gn9_render_hub_html_round_trip_carries_the_field(self) -> None:
        tier1 = self._tier1(BASE_TIME_MS)
        working_session = self._session_facts("s-working", BASE_TIME_MS + 60_000)
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1}, sessions_by_path={"/repo": (working_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=BASE_TIME_MS, projects=views, unresolved_dir_names=(), warnings=(),
        )
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        parsed = json.loads(payload)
        self.assertIs(parsed["projects"][0]["tier1_is_previous_task"], True)

    def test_gn10_idle_only_session_is_false(self) -> None:
        """결정 GN2 — idle 은 판정 집합 밖이다. 승인 항목 4 가 뒤집히면 이 케이스가 True 로 바뀐다."""
        idle_session = hub_session_facts.SessionFacts(
            session_id="s-idle", cwd="/repo", observed_cwds=("/repo",), started_at_ms=BASE_TIME_MS + 60_000,
            last_event_at_ms=BASE_TIME_MS + 60_000, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )
        tier1 = self._tier1(BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1}, sessions_by_path={"/repo": (idle_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertFalse(views[0].tier1_is_previous_task)

    def test_u18_only_worktree_session_enters_the_verdict(self) -> None:
        """U-18(S6) — 승자가 워크트리 파일이면 그 워크트리 cwd 의 세션만 판정에 들어간다(결정 WT9).
        루트 세션은 대시보드보다 먼저 시작했으니 포함되면 판정을 False 로 뒤집었을 것이다."""
        root = "/repo"
        worktree = "/repo/.claude/worktrees/w"
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path=worktree,
        )
        root_session_before_mtime = hub_session_facts.SessionFacts(
            session_id="s-root", cwd=root, observed_cwds=(root,), started_at_ms=BASE_TIME_MS - 60_000,
            last_event_at_ms=BASE_TIME_MS - 60_000, last_event_name="UserPromptSubmit",
            turn_state="running", ended_at_ms=None, subagents=(),
        )
        worktree_session_after_mtime = hub_session_facts.SessionFacts(
            session_id="s-wt", cwd=worktree, observed_cwds=(worktree,), started_at_ms=BASE_TIME_MS + 60_000,
            last_event_at_ms=BASE_TIME_MS + 60_000, last_event_name="UserPromptSubmit",
            turn_state="running", ended_at_ms=None, subagents=(),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={root: tier1},
            sessions_by_path={root: (root_session_before_mtime, worktree_session_after_mtime)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertTrue(views[0].tier1_is_previous_task)

    def test_u19_project_without_worktree_matches_pre_fold_verdict(self) -> None:
        """U-19(S7) — 워크트리가 없는 프로젝트는 GN 판정이 이 기능 이전과 완전히 같다."""
        tier1 = self._tier1(BASE_TIME_MS)
        working_session = self._session_facts("s-working", BASE_TIME_MS + 60_000)
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1}, sessions_by_path={"/repo": (working_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertTrue(views[0].tier1_is_previous_task)

    def test_u24_label_turns_on_for_session_that_moved_into_the_worktree(self) -> None:
        """GN 대응 U-24(결정 WT18) — 세션이 워크트리로 **이동**해도 `cwd` 는 여전히 창 안
        최초 이벤트인 레포 루트에 고정된다(결정 WT14). `observed_cwds` 에 워크트리가 남아
        있으면 세대 판정에 들어간다. `facts.cwd` 로만 비교하던 이전 규칙(`==`, 뮤테이션 11)
        이면 이 세션은 판정 집합에서 빠져 라벨이 우연히 꺼졌을 것이다(E15)."""
        root = "/repo"
        worktree = "/repo/.claude/worktrees/w"
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path=worktree,
        )
        moved_session = hub_session_facts.SessionFacts(
            session_id="s-moved", cwd=root, observed_cwds=(root, worktree),
            started_at_ms=BASE_TIME_MS + 60_000, last_event_at_ms=BASE_TIME_MS + 60_000,
            last_event_name="UserPromptSubmit", turn_state="running", ended_at_ms=None,
            subagents=(),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={root: tier1}, sessions_by_path={root: (moved_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertTrue(views[0].tier1_is_previous_task)

    def test_p6_live_session_own_session_file_is_not_marked_previous_task(self) -> None:
        """P6(hub-session-tree-and-per-session-dashboards.md) — 승자가 살아 있는 세션 자신의
        세션별 파일이면(자기 파일은 시작 이후에만 갱신되므로 start < mtime 이 항상 성립)
        '이전 작업' 라벨이 켜지지 않는다(GN 판정 무변경, 결정 ST11)."""
        own_session_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS + 60_000, source_path="/repo", session_id="s-working",
        )
        working_session = self._session_facts("s-working", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": own_session_tier1}, sessions_by_path={"/repo": (working_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertFalse(views[0].tier1_is_previous_task)

    def test_p6_done_session_file_with_only_later_working_session_is_marked_previous_task(self) -> None:
        """P6 대조군 — 승자가 done 세션의 파일이고, 그 뒤에 시작한 working 세션만 있으면
        라벨이 켜진다(오늘과 같은 판정, 결정 ST11)."""
        done_session_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path="/repo", session_id="s-done",
        )
        working_session = self._session_facts("s-working", BASE_TIME_MS + 60_000)
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": done_session_tier1}, sessions_by_path={"/repo": (working_session,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertTrue(views[0].tier1_is_previous_task)


class ProjectTierOneFinishedTaskTest(unittest.TestCase):
    """CD1~CD7(이슈 1, docs/prps/hub-session-list-and-glow-fixes.md §3) —
    is_project_tier1_from_finished_session_task 순수 함수와
    ProjectView.tier1_is_finished_task 필드."""

    def _tier1(self, session_id, percent=100):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=1, percent=percent, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path="/repo", session_id=session_id,
        )

    def _session_view(self, session_id, tier1_is_finished_task):
        return hub_session.SessionView(
            session_id=session_id, short_id=session_id[:8], started_at_ms=BASE_TIME_MS,
            state="idle", base_state="idle", last_event_at_ms=BASE_TIME_MS,
            task_excerpt=None, agent_runs=(), tier1_is_finished_task=tier1_is_finished_task,
        )

    def test_cd1_winner_is_a_finished_sessions_own_file_and_it_is_present_is_true(self) -> None:
        tier1 = self._tier1("s-done")
        session_views = (self._session_view("s-done", tier1_is_finished_task=True),)
        self.assertTrue(hub_project.is_project_tier1_from_finished_session_task(tier1, session_views))

    def test_cd2_legacy_single_file_winner_is_false(self) -> None:
        """승자가 레거시 단일 파일(session_id is None)이면 세션 귀속이 원리적으로
        불가능하다(알려진 공백 — §11)."""
        tier1 = self._tier1(None)
        session_views = (self._session_view("s-done", tier1_is_finished_task=True),)
        self.assertFalse(hub_project.is_project_tier1_from_finished_session_task(tier1, session_views))

    def test_cd3_matching_session_not_present_is_false(self) -> None:
        """승자가 세션 파일이지만 그 세션이 sessions 에 없다(이벤트 창 밖) — 열린 채로
        실패한다(오늘 동작 유지)."""
        tier1 = self._tier1("s-outside-window")
        session_views = (self._session_view("s-other", tier1_is_finished_task=True),)
        self.assertFalse(hub_project.is_project_tier1_from_finished_session_task(tier1, session_views))

    def test_cd4_in_progress_dashboard_is_false(self) -> None:
        tier1 = self._tier1("s-working", percent=60)
        session_views = (self._session_view("s-working", tier1_is_finished_task=False),)
        self.assertFalse(hub_project.is_project_tier1_from_finished_session_task(tier1, session_views))

    def test_cd5_finished_task_and_previous_task_are_independently_true(self) -> None:
        """FT6 표의 「독립적으로 참/거짓」 재확인 — 두 판정은 서로 다른 것을 본다. S 는
        자기 파일을 100% 로 끝내고 30분 넘게 조용해져(FT1 True) 이전 작업 실행 경계를
        얻지만 상태는 idle 이라 GN 의 all() 판정에는 들어가지 않는다. T 는 그 파일보다
        나중에 시작한 유일한 working 세션이라(GN True) 카드 세대 판정도 함께 켜진다."""
        source_path = "/repo"
        tier1_file_mtime_ms = BASE_TIME_MS
        one_minute_ms = 60_000
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=1, percent=100, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=tier1_file_mtime_ms, source_path=source_path, session_id="s-done",
        )
        finished_session = hub_session_facts.SessionFacts(
            session_id="s-done", cwd=source_path, observed_cwds=(source_path,),
            started_at_ms=tier1_file_mtime_ms - one_minute_ms,
            last_event_at_ms=tier1_file_mtime_ms + 31 * one_minute_ms,
            last_event_name="Stop", turn_state="ended", ended_at_ms=None, subagents=(),
        )
        live_session = hub_session_facts.SessionFacts(
            session_id="s-live", cwd=source_path, observed_cwds=(source_path,),
            started_at_ms=tier1_file_mtime_ms + 40 * one_minute_ms,
            last_event_at_ms=tier1_file_mtime_ms + 40 * one_minute_ms,
            last_event_name="UserPromptSubmit", turn_state="running", ended_at_ms=None, subagents=(),
        )
        now_ms = tier1_file_mtime_ms + 40 * one_minute_ms
        views = hub_project.compose_project_views(
            tier1_by_path={source_path: tier1},
            sessions_by_path={source_path: (finished_session, live_session)},
            tier3_last_activity_by_path={}, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            session_dashboards_by_path={source_path: (tier1,)},
        )
        self.assertTrue(views[0].tier1_is_previous_task)
        self.assertTrue(views[0].tier1_is_finished_task)

    def test_cd6_no_tier1_is_false(self) -> None:
        session_views = (self._session_view("s-done", tier1_is_finished_task=True),)
        self.assertFalse(hub_project.is_project_tier1_from_finished_session_task(None, session_views))


class EncodeProjectDirNameTest(unittest.TestCase):
    """M12~M14 — 정방향 인코딩과 미확인 처리.

    N1(docs/prps/hub-agent-title-and-excerpt-freshness.md §16) — Claude Code 의 프로젝트 폴더
    이름 규칙과 같은가: 영숫자(ASCII)가 아닌 글자는 전부 `-`(UTF-16 코드 유닛 단위), 이름이 200자를
    넘으면 앞 200자 + `-` + 원래 경로의 해시(자바 String.hashCode 의 절댓값을 36진수로). 해시 접미사
    기대값은 이 함수로 계산하지 않았다 — 호스트 번들(2.1.284)의 함수 원문을 Node 로 실행해 얻은
    독립 계산 리터럴이다(순환 검증 방지)."""

    def test_m12_hyphenated_directory_name_untouched(self) -> None:
        encoded = hub_project.encode_project_dir_name(
            "/Users/b/private/project/claude-agents-manager"
        )
        self.assertEqual(encoded, "-Users-b-private-project-claude-agents-manager")

    def test_m13_dot_and_slash_both_become_dash(self) -> None:
        encoded = hub_project.encode_project_dir_name("/Users/b/.claude/projects/x")
        self.assertEqual(encoded, "-Users-b--claude-projects-x")

    def test_n1_underscore_becomes_dash(self) -> None:
        """실측 결함 — 밑줄 든 경로를 `_` 그대로 두어 호스트 폴더를 찾지 못했다."""
        encoded = hub_project.encode_project_dir_name("/Users/dev/works/notebook_wiki/NotebookWiki")
        self.assertEqual(encoded, "-Users-dev-works-notebook-wiki-NotebookWiki")

    def test_n1_space_becomes_dash(self) -> None:
        encoded = hub_project.encode_project_dir_name("/Users/dev/Library/Application Support/Litmus")
        self.assertEqual(encoded, "-Users-dev-Library-Application-Support-Litmus")

    def test_n1_each_hangul_syllable_becomes_one_dash(self) -> None:
        self.assertEqual(hub_project.encode_project_dir_name("/Users/dev/한글"), "-Users-dev---")

    def test_n1_other_symbols_become_dash(self) -> None:
        encoded = hub_project.encode_project_dir_name("/Users/dev/a@b#c(d)e+f~g'h&i")
        self.assertEqual(encoded, "-Users-dev-a-b-c-d-e-f-g-h-i")

    def test_n1_consecutive_symbols_are_not_collapsed(self) -> None:
        self.assertEqual(hub_project.encode_project_dir_name("/a//b/../c"), "-a--b----c")

    def test_n1_letters_digits_and_case_are_kept(self) -> None:
        self.assertEqual(hub_project.encode_project_dir_name("/Users/Dev/App2Go"), "-Users-Dev-App2Go")

    def test_n1_empty_path_gives_empty_name(self) -> None:
        self.assertEqual(hub_project.encode_project_dir_name(""), "")

    def test_n1_character_beyond_the_basic_plane_becomes_two_dashes(self) -> None:
        """호스트는 UTF-16 코드 유닛마다 바꾼다 — 이모지 1글자는 서로게이트 쌍이라 `-` 2개가 된다."""
        self.assertEqual(hub_project.encode_project_dir_name("/tmp/\U0001F600"), "-tmp---")

    def test_n1_lone_surrogate_becomes_one_dash_instead_of_raising(self) -> None:
        """이벤트 JSON 의 `\\ud83d` 같은 짝 없는 서로게이트도 cwd 로 들어올 수 있다 — 호스트(JS)는 1유닛으로 세고
        `-` 로 바꾼다. 인코딩 예외로 수집 전체가 죽으면 안 된다(옛 규칙은 어떤 문자열에도 예외가 없었다)."""
        self.assertEqual(hub_project.encode_project_dir_name("/tmp/\ud83d"), "-tmp--")

    def test_n1_name_of_exactly_200_characters_is_kept_whole(self) -> None:
        self.assertEqual(hub_project.encode_project_dir_name("/" + "a" * 199), "-" + "a" * 199)

    def test_n1_name_over_200_characters_is_cut_and_gets_a_path_hash(self) -> None:
        """201자 → 앞 200자 + `-b6ymvl`. 이 경로의 자바 해시는 음수(-676821585)라 절댓값을 쓰는지도 본다."""
        encoded = hub_project.encode_project_dir_name("/" + "a" * 200)
        self.assertEqual(encoded, "-" + "a" * 199 + "-b6ymvl")

    def test_n1_hash_is_taken_from_the_original_path_not_the_encoded_name(self) -> None:
        """밑줄 경로와 점 경로는 인코딩 결과의 앞 200자가 같지만 해시가 다르다(각각 음수·양수 해시)."""
        head = "-" + "a-" * 99 + "a"
        self.assertEqual(hub_project.encode_project_dir_name("/" + "a_" * 100), head + "-ftjvo9")
        self.assertEqual(hub_project.encode_project_dir_name("/" + "a." * 100), head + "-cv7qrn")

    def test_n1_hash_is_taken_from_the_original_hangul_not_from_dashes(self) -> None:
        encoded = hub_project.encode_project_dir_name("/Users/dev/" + "한글폴더" * 50)
        self.assertEqual(encoded, "-Users-dev-" + "-" * 189 + "-3qwdyw")

    def test_n1_length_is_counted_in_utf16_code_units(self) -> None:
        """이모지 100개 + 슬래시는 101글자지만 UTF-16 으로 201유닛이라 호스트는 자른다(글자 수로 세면
        자르지 않는다). 같은 모양에서 200유닛이면 자르지 않는다."""
        over_limit = hub_project.encode_project_dir_name("/" + "\U0001F600" * 100)
        at_limit = hub_project.encode_project_dir_name("/" + "\U0001F600" * 99 + "x")
        self.assertEqual(over_limit, "-" * 200 + "-5s12ud")
        self.assertEqual(at_limit, "-" * 199 + "x")

    def test_n1_hash_zero_is_written_as_a_single_zero(self) -> None:
        """NUL 글자만으로 된 201자 경로는 해시가 0 이다 — 호스트의 (0).toString(36) 은 "0" 이다."""
        self.assertEqual(hub_project.encode_project_dir_name("\x00" * 201), "-" * 200 + "-0")

    def test_n1_hash_of_the_smallest_32bit_value_uses_its_magnitude(self) -> None:
        """문자열 polygenelubricants 의 자바 해시는 -2^31 이다. 글자를 붙일 때마다 해시에 31 이 곱해지지만
        -2^31 × 31 ≡ -2^31 (mod 2^32) 이라 NUL(0 을 더함)을 붙여도 -2^31 이 유지된다. 호스트의 Math.abs 는
        이것을 2^31(36진수 zik0zk)로 돌려준다 — 32비트 안에서 부호만 떼면 틀린다."""
        encoded = hub_project.encode_project_dir_name("polygenelubricants" + "\x00" * 183)
        self.assertEqual(encoded, "polygenelubricants" + "-" * 182 + "-zik0zk")

    def test_m14_unmatched_encoded_name_has_no_path(self) -> None:
        resolved, unresolved = hub_project.resolve_project_dirs(
            encoded_names=["-Users-b-unknown-project"],
            candidate_paths=["/Users/b/private/project/coding-harness"],
        )
        self.assertEqual(resolved, {})
        self.assertEqual(unresolved, ("-Users-b-unknown-project",))

    def test_n1_underscore_path_resolves_from_the_host_folder_name(self) -> None:
        """티어 3 매칭도 같은 결함을 겪었다 — 호스트 폴더 이름(리터럴)이 밑줄 든 후보 경로와 짝지어진다."""
        folder_name = "-Users-dev-works-notebook-wiki-NotebookWiki"
        project_path = "/Users/dev/works/notebook_wiki/NotebookWiki"
        resolved, unresolved = hub_project.resolve_project_dirs([folder_name], [project_path])
        self.assertEqual(resolved, {folder_name: project_path})
        self.assertEqual(unresolved, ())


class EncodePathGlobToProjectDirGlobTest(unittest.TestCase):
    """N1 의 여파 — ignore_globs(실경로 glob)를 폴더 이름에 대고 쓰려면 경로와 같은 규칙으로 인코딩하되
    와일드카드는 살려야 한다. 옛 규칙은 `/`·`.` 만 바꿔 `*` 가 저절로 남았지만, 호스트 규칙은 영숫자가
    아닌 글자를 전부 바꿔 `*` 까지 `-` 가 된다(그러면 티어 3 의 worktree·scratchpad 걸러내기가 조용히 죽는다)."""

    def test_default_ignore_globs_keep_their_wildcards(self) -> None:
        globs = ("**/.claude/worktrees/**", "/tmp/**", "/private/tmp/**")
        encoded = tuple(hub_project.encode_path_glob_to_project_dir_glob(glob) for glob in globs)
        self.assertEqual(encoded, ("**--claude-worktrees-**", "-tmp-**", "-private-tmp-**"))

    def test_literal_characters_are_encoded_like_a_path(self) -> None:
        encoded = hub_project.encode_path_glob_to_project_dir_glob("/Users/dev/my_app v1.0/**")
        self.assertEqual(encoded, "-Users-dev-my-app-v1-0-**")

    def test_question_mark_and_bracket_wildcards_survive(self) -> None:
        encoded = hub_project.encode_path_glob_to_project_dir_glob("/Users/dev/app?/[ab]x/[!a]y")
        self.assertEqual(encoded, "-Users-dev-app?-[ab]x-[!a]y")

    def test_pattern_without_wildcards_is_encoded_like_a_path(self) -> None:
        self.assertEqual(hub_project.encode_path_glob_to_project_dir_glob("/Users/dev"), "-Users-dev")

    def test_long_pattern_is_not_cut_or_hashed(self) -> None:
        """패턴은 실제 경로가 아니라 200자 절단·해시 규칙이 적용될 이름이 아니다."""
        encoded = hub_project.encode_path_glob_to_project_dir_glob("/" + "a" * 250 + "/**")
        self.assertEqual(encoded, "-" + "a" * 250 + "-**")

    def test_encoded_glob_matches_the_encoded_name_of_every_path_the_glob_matches(self) -> None:
        cases = (
            ("**/.claude/worktrees/**", "/Users/dev/repo/.claude/worktrees/feature_one"),
            ("/private/tmp/**", "/private/tmp/claude-501/my project/scratchpad"),
            ("/tmp/**", "/tmp/a.b_c"),
            ("/Users/dev/my_app/**", "/Users/dev/my_app/sub dir"),
        )
        for glob, path in cases:
            with self.subTest(glob=glob):
                encoded_glob = hub_project.encode_path_glob_to_project_dir_glob(glob)
                encoded_name = hub_project.encode_project_dir_name(path)
                self.assertTrue(hub_project.should_ignore_cwd(path, (glob,)))
                self.assertTrue(hub_project.should_ignore_cwd(encoded_name, (encoded_glob,)))

    def test_encoded_glob_does_not_match_neighbouring_names(self) -> None:
        cases = (
            ("/tmp/**", "/tmpfile/x"),
            ("/Users/dev/my_app/**", "/Users/dev/my_apple/x"),
        )
        for glob, path in cases:
            with self.subTest(glob=glob):
                encoded_glob = hub_project.encode_path_glob_to_project_dir_glob(glob)
                encoded_name = hub_project.encode_project_dir_name(path)
                self.assertFalse(hub_project.should_ignore_cwd(encoded_name, (encoded_glob,)))


class ShouldIgnoreCwdTest(unittest.TestCase):
    """M15 — worktree·scratchpad 경로는 무시 대상이다."""

    def test_m15_worktree_and_tmp_paths_are_ignored(self) -> None:
        ignore_globs = hub_model.HubConfig().ignore_globs
        self.assertTrue(hub_project.should_ignore_cwd("/Users/b/repo/.claude/worktrees/f1", ignore_globs))
        self.assertTrue(hub_project.should_ignore_cwd("/private/tmp/claude-501/x", ignore_globs))
        self.assertFalse(hub_project.should_ignore_cwd("/Users/b/private/project/coding-harness", ignore_globs))


class FoldWorktreePathTest(unittest.TestCase):
    """U-1~U-5 — 워크트리 경로를 소유 레포 루트로 접는다(결정 WT3, docs/prps/hub-worktree-fold.md)."""

    def test_u1_worktree_path_folds_to_repo_root(self) -> None:
        self.assertEqual(hub_project.fold_worktree_path("/repo/.claude/worktrees/w"), "/repo")

    def test_u2_non_worktree_path_is_identity(self) -> None:
        self.assertEqual(hub_project.fold_worktree_path("/repo"), "/repo")

    def test_u3_multi_segment_worktree_name_folds_to_repo_root(self) -> None:
        """X-2 — EnterWorktree 의 name 은 `/` 로 구분된 다단 세그먼트를 허용한다."""
        self.assertEqual(
            hub_project.fold_worktree_path("/repo/.claude/worktrees/feature/sub"), "/repo"
        )

    def test_u4_nested_worktree_folds_to_outermost_repo_via_first_marker(self) -> None:
        """X-1 — 중첩 워크트리는 첫 마커에서 잘라야 최외곽 레포까지 한 번에 접힌다.
        `rfind` 구현이면 `/a/repo/.claude/worktrees/w1` 이 나와 이 테스트가 실패한다(뮤테이션 1)."""
        nested = "/a/repo/.claude/worktrees/w1/.claude/worktrees/w2"
        self.assertEqual(hub_project.fold_worktree_path(nested), "/a/repo")

    def test_u5_home_directory_worktree_folds_to_home(self) -> None:
        """X-3 — 가드를 붙이지 않는다. `$HOME` 바로 아래 워크트리는 `$HOME` 으로 접히는 것이 맞다."""
        self.assertEqual(hub_project.fold_worktree_path("/Users/u/.claude/worktrees/x"), "/Users/u")


class GroupPathsByRepoRootTest(unittest.TestCase):
    """U-6~U-7 — 경로들을 소유 레포 루트별로 묶는다(결정 WT6 의 동률 처리 순서 근거)."""

    def test_u6_root_is_first_element_even_when_absent_from_input(self) -> None:
        result = hub_project.group_paths_by_repo_root(["/repo/.claude/worktrees/w"])
        self.assertEqual(result, {"/repo": ("/repo", "/repo/.claude/worktrees/w")})

    def test_u7_members_are_ordered_root_then_worktrees_alphabetically(self) -> None:
        paths = ["/repo/.claude/worktrees/b", "/repo", "/repo/.claude/worktrees/a"]
        result = hub_project.group_paths_by_repo_root(paths)
        self.assertEqual(
            result["/repo"],
            ("/repo", "/repo/.claude/worktrees/a", "/repo/.claude/worktrees/b"),
        )


class PlanTier1CandidatesTest(unittest.TestCase):
    """검수 1회차 M1 — `collect_snapshot` 조립부(observed_paths/members_by_root/candidate_paths
    3줄)를 추출한 순수 함수의 단위 테스트. 이 조립이 `collect_snapshot` 안에 있을 때는 이를
    실행하는 테스트가 하나도 없었다(참조하는 모든 테스트가 `_read_tier1_for_root` 자체를
    mock.patch 로 우회) — 아래 테스트들이 그 미검출 뮤테이션 2건을 직접 겨냥한다."""

    def _facts(self, cwd: str, observed_cwds: tuple[str, ...] | None = None) -> hub_session_facts.SessionFacts:
        # observed_cwds 기본값은 (cwd,) — cwd 하나만 관측된 세션(observed_cwds 무기본값의
        # 정상적인 최소 형태, 결정 WT19). 워크트리를 관측 목록에만 남겨 두고 싶은 테스트는
        # observed_cwds 를 명시적으로 넘긴다.
        return hub_session_facts.SessionFacts(
            session_id="s1", cwd=cwd,
            observed_cwds=observed_cwds if observed_cwds is not None else (cwd,),
            started_at_ms=BASE_TIME_MS, last_event_at_ms=BASE_TIME_MS,
            last_event_name="UserPromptSubmit", turn_state="running", ended_at_ms=None,
            subagents=(),
        )

    def test_worktree_member_survives_fold_then_ignore_with_default_globs(self) -> None:
        """뮤테이션 방어 — `observed_paths` 를 `facts.observed_cwds` 대신 그룹 키(facts.cwd)만
        보게 되돌리거나(뮤테이션 7·9) ignore 를 접기 전 원본 경로에 적용하면(결정 WT5 위반,
        뮤테이션 8) 전부 이 결과를 `{"/repo": ("/repo",)}` 로 쪼그라뜨린다 — 기본 ignore_globs 의
        `**/.claude/worktrees/**` 가 원본 워크트리 경로에는 매칭되지만 접힌 루트에는 매칭되지
        않기 때문에, 세 뮤테이션 전부 이 단언 하나로 잡힌다.

        `cwd` 는 레포 루트로 고정하고 워크트리는 `observed_cwds` 로만 알려준다 — 이것이 결정
        WT16 이후 프로덕션이 실제로 만드는 값이다(2판 이전 판은 여기서 `cwd` 자체에 워크트리를
        넣어 두었는데, 그것은 `facts.cwd` 가 창 안 최초 이벤트로 고정된다는 사실(결정 WT14)과
        맞지 않는, 프로덕션이 만들 수 없는 입력이었다 — 결정 WT20)."""
        facts = self._facts("/repo", observed_cwds=("/repo", "/repo/.claude/worktrees/w"))
        sessions_by_path = {"/repo": (facts,)}
        ignore_globs = hub_model.HubConfig().ignore_globs

        result = hub_project.plan_tier1_candidates(sessions_by_path, (), ignore_globs)

        self.assertEqual(result, {"/repo": ("/repo", "/repo/.claude/worktrees/w")})

    def test_worktree_in_observed_cwds_becomes_a_tier1_member(self) -> None:
        """U-27(S9 의 순수 단위 대응) — 이번 결함의 최소 재현. `facts.cwd` 는 레포 루트로
        고정된 채(결정 WT14) `observed_cwds` 에만 워크트리가 있어도 후보 멤버가 된다(결정
        WT16). 뮤테이션 9(`facts.observed_cwds` → `(facts.cwd,)`)를 넣으면 이 테스트가
        실패해야 한다."""
        facts = self._facts("/repo", observed_cwds=("/repo", "/repo/.claude/worktrees/w"))
        sessions_by_path = {"/repo": (facts,)}
        ignore_globs = hub_model.HubConfig().ignore_globs

        result = hub_project.plan_tier1_candidates(sessions_by_path, (), ignore_globs)

        self.assertEqual(result["/repo"], ("/repo", "/repo/.claude/worktrees/w"))

    def test_ignored_root_is_excluded_entirely(self) -> None:
        """결정 WT5 — ignore 는 접힌 루트에 적용된다. 루트 자체가 무시 패턴에 해당하면
        (여기서는 `/private/tmp/**`) 그 루트와 멤버 전부가 후보에서 빠진다. 이 케이스는 세션의
        모든 이벤트가 워크트리인 「창이 구른 뒤」 시나리오(X-14)도 겸한다 — `cwd` 와
        `observed_cwds` 가 둘 다 워크트리 경로뿐이다."""
        sessions_by_path = {"/private/tmp/x": (self._facts("/private/tmp/x/.claude/worktrees/w"),)}
        ignore_globs = hub_model.HubConfig().ignore_globs

        result = hub_project.plan_tier1_candidates(sessions_by_path, (), ignore_globs)

        self.assertEqual(result, {})

    def test_scanned_path_becomes_a_candidate_even_without_sessions(self) -> None:
        """세션이 없어도 스캔된 레포 루트는 티어 1 후보다(S7 계열)."""
        result = hub_project.plan_tier1_candidates({}, ("/repo",), ())
        self.assertEqual(result, {"/repo": ("/repo",)})

    def test_empty_string_root_is_excluded(self) -> None:
        """검수 1회차 m5 — `fold_worktree_path` 가 빈 문자열을 만드는 입력(마커가 경로 맨
        앞에 옴)은 후보에서 제외된다. 제외하지 않으면 `read_session_dashboard_snapshots` 이 프로세스 CWD
        기준 상대경로를 참조하게 된다."""
        result = hub_project.plan_tier1_candidates({}, ("/.claude/worktrees/w",), ())
        self.assertNotIn("", result)

    def test_foreign_observed_path_creates_no_root_and_no_member(self) -> None:
        """U-30(S12 의 순수 단위 대응) — 앵커 규칙(결정 WT17). 관측 cwd 에 남의 프로젝트나
        자기 프로젝트의 **하위 디렉토리**가 섞여 있어도 새 루트를 만들거나 멤버로 들어오지
        않는다(E14 가 실데이터로 이 입력의 존재를 확인했다). 뮤테이션 12(`root in anchors`
        조건 삭제)를 넣으면 이 테스트가 실패해야 한다."""
        facts = self._facts("/repo", observed_cwds=("/repo", "/other/project", "/repo/sub"))
        sessions_by_path = {"/repo": (facts,)}

        result = hub_project.plan_tier1_candidates(sessions_by_path, (), ())

        self.assertEqual(set(result), {"/repo"})
        self.assertEqual(result["/repo"], ("/repo",))


class SelectTier1SourceTest(unittest.TestCase):
    """U-8~U-10 — 티어 1 후보 중 mtime 최신을 고른다. 동률이면 목록 앞이 이긴다(결정 WT6)."""

    def _tier1(self, file_mtime_ms, source_path):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=file_mtime_ms, source_path=source_path,
        )

    def test_u8_newer_mtime_wins(self) -> None:
        older = self._tier1(BASE_TIME_MS, "/repo")
        newer = self._tier1(BASE_TIME_MS + 1000, "/repo/.claude/worktrees/w")
        self.assertEqual(hub_project.select_tier1_source([older, newer]), newer)

    def test_u9_tie_favors_the_earlier_candidate_in_the_list(self) -> None:
        """결정 WT6 을 못 박는다 — 후보 순서가 `(루트, 워크트리…)` 면 동률 시 루트가 이긴다."""
        root = self._tier1(BASE_TIME_MS, "/repo")
        worktree = self._tier1(BASE_TIME_MS, "/repo/.claude/worktrees/w")
        self.assertEqual(hub_project.select_tier1_source([root, worktree]), root)

    def test_u10_empty_candidates_returns_none(self) -> None:
        self.assertIsNone(hub_project.select_tier1_source([]))


class ComposeProjectViewsTest(unittest.TestCase):
    """M16~M17, M20 — 프로젝트 상태 합성과 정렬."""

    def _session_facts(self, session_id, cwd, last_event_at_ms, ended_at_ms=None):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=last_event_at_ms,
            last_event_at_ms=last_event_at_ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=ended_at_ms, subagents=(),
        )

    def test_m16_one_working_beats_three_done(self) -> None:
        sessions = (
            self._session_facts("s-working", "/repo/a", BASE_TIME_MS),
            self._session_facts("s-done-1", "/repo/a", BASE_TIME_MS, ended_at_ms=BASE_TIME_MS),
            self._session_facts("s-done-2", "/repo/a", BASE_TIME_MS, ended_at_ms=BASE_TIME_MS),
            self._session_facts("s-done-3", "/repo/a", BASE_TIME_MS, ended_at_ms=BASE_TIME_MS),
        )
        working = hub_session_facts.SessionFacts(
            session_id="s-working", cwd="/repo/a", observed_cwds=("/repo/a",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="UserPromptSubmit",
            turn_state="running", ended_at_ms=None, subagents=(),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (working, *sessions[1:])},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "working")

    def test_m17_sorted_by_last_activity_regardless_of_state(self) -> None:
        older_but_active = self._session_facts("s-old", "/repo/old", BASE_TIME_MS)
        newer_but_done = self._session_facts(
            "s-new", "/repo/new", BASE_TIME_MS + 10_000, ended_at_ms=BASE_TIME_MS + 10_000
        )
        views = hub_project.compose_project_views(
            tier1_by_path={},
            sessions_by_path={"/repo/old": (older_but_active,), "/repo/new": (newer_but_done,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual([view.path for view in views], ["/repo/new", "/repo/old"])

    def test_q3_session_view_preserves_started_at_ms(self) -> None:
        """요구 3(세션 구분, docs/prps/hub-collect-on-demand-and-readability.md §4.6) —
        compose_project_views 를 거쳐도 started_at_ms 가 last_event_at_ms 와 섞이지 않고
        보존된다."""
        facts = hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo/a", observed_cwds=("/repo/a",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS + 90_000, last_event_name="UserPromptSubmit",
            turn_state="running", ended_at_ms=None, subagents=(),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 90_000, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].sessions[0].started_at_ms, BASE_TIME_MS)
        self.assertEqual(views[0].sessions[0].last_event_at_ms, BASE_TIME_MS + 90_000)

    def test_m20_tier3_only_project_has_no_sessions(self) -> None:
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={},
            tier3_last_activity_by_path={"/repo/quiet": BASE_TIME_MS},
            now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(len(views), 1)
        self.assertEqual(views[0].tier, 3)
        self.assertEqual(views[0].sessions, ())
        self.assertEqual(views[0].last_activity_at_ms, BASE_TIME_MS)

    def test_sessionless_tier3_project_with_recent_activity_is_idle_not_done(self) -> None:
        """검수 M3 회귀 — 세션이 없다는 이유로 영구히 'done' 이 되면 안 된다."""
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={},
            tier3_last_activity_by_path={"/repo/quiet": BASE_TIME_MS},
            now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "idle")

    def test_sessionless_tier1_project_past_stale_window_is_stale_not_done(self) -> None:
        """검수 M3 회귀 — 티어 1 전용(세션 없음) 프로젝트도 오래되면 stale, done 은 아니다."""
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS,
        )
        past_stale_window_ms = BASE_TIME_MS + STALE_AFTER_MS + 1
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo/old": tier1}, sessions_by_path={}, tier3_last_activity_by_path={},
            now_ms=past_stale_window_ms, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "stale")
        self.assertNotEqual(views[0].state, "done")


class ComposeProjectViewsTailBySessionIdTest(unittest.TestCase):
    """§8.5 — tail_by_session_id(요구 2, docs/prps/hub-tier1-clamp-fix-and-session-model.md
    결정 MD1~MD10). 결정 PS3(docs/prps/hub-agent-runs-and-prompt-source.md)로
    `model_by_session_id` 를 대체한다 — 모델과 마지막 프롬프트가 같은 꼬리 읽기에서 나와
    딕셔너리 하나로 묶인다."""

    def _session_facts(self, session_id, cwd, last_event_at_ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=last_event_at_ms,
            last_event_at_ms=last_event_at_ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def test_model_is_assigned_only_to_the_matching_session(self) -> None:
        with_model = self._session_facts("s-with-model", "/repo/a", BASE_TIME_MS)
        without_model = self._session_facts("s-without-model", "/repo/a", BASE_TIME_MS)
        model = hub_transcript.SessionModel(model_label="Opus 5", raw_model_id="claude-opus-5", effort="xhigh")
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (with_model, without_model)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id={"s-with-model": hub_transcript.SessionTail(model=model, last_prompt=None)},
        )
        sessions_by_id = {session.session_id: session for session in views[0].sessions}
        self.assertEqual(sessions_by_id["s-with-model"].model, model)
        self.assertIsNone(sessions_by_id["s-without-model"].model)

    def test_missing_tail_by_session_id_argument_defaults_all_sessions_to_none(self) -> None:
        """기존 호출부(tail_by_session_id 없이 부름)가 무해하다 — 기본값 None."""
        facts = self._session_facts("s1", "/repo/a", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertIsNone(views[0].sessions[0].model)
        self.assertIsNone(views[0].sessions[0].task_excerpt)

    def test_last_prompt_is_assigned_only_to_the_matching_session(self) -> None:
        with_prompt = self._session_facts("s-with-prompt", "/repo/a", BASE_TIME_MS)
        without_prompt = self._session_facts("s-without-prompt", "/repo/a", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (with_prompt, without_prompt)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id={
                "s-with-prompt": hub_transcript.SessionTail(model=None, last_prompt="마지막 프롬프트")
            },
        )
        sessions_by_id = {session.session_id: session for session in views[0].sessions}
        self.assertEqual(sessions_by_id["s-with-prompt"].task_excerpt, "마지막 프롬프트")
        self.assertIsNone(sessions_by_id["s-without-prompt"].task_excerpt)

    def test_snapshot_content_key_changes_when_model_changes(self) -> None:
        """모델이 같으면 키가 같고, 모델이 바뀌면 키가 바뀐다(hub.html 재작성 억제 유지, 결정 D2)."""
        facts = self._session_facts("s1", "/repo/a", BASE_TIME_MS)

        def _content_key(tail_by_session_id):
            views = hub_project.compose_project_views(
                tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
                tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
                tail_by_session_id=tail_by_session_id,
            )
            snapshot = hub_model.HubSnapshot(
                collected_at_ms=BASE_TIME_MS, projects=views, unresolved_dir_names=(), warnings=(),
            )
            return hub_model.snapshot_content_key(snapshot)

        opus = hub_transcript.SessionModel(model_label="Opus 5", raw_model_id="claude-opus-5", effort="xhigh")
        fable = hub_transcript.SessionModel(model_label="Fable 5", raw_model_id="claude-fable-5", effort="high")

        key_without_model = _content_key({})
        key_with_opus = _content_key({"s1": hub_transcript.SessionTail(model=opus, last_prompt=None)})
        key_with_opus_again = _content_key({"s1": hub_transcript.SessionTail(model=opus, last_prompt=None)})
        key_with_fable = _content_key({"s1": hub_transcript.SessionTail(model=fable, last_prompt=None)})

        self.assertNotEqual(key_without_model, key_with_opus)
        self.assertEqual(key_with_opus, key_with_opus_again)
        self.assertNotEqual(key_with_opus, key_with_fable)


class ComposeProjectViewsSessionDashboardTest(unittest.TestCase):
    """P4(hub-session-tree-and-per-session-dashboards.md) — compose_project_views 가
    session_dashboards_by_path 를 세션 뷰에 싣는다(결정 ST12)."""

    def _session_facts(self, session_id, cwd, last_event_at_ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=last_event_at_ms,
            last_event_at_ms=last_event_at_ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def _session_tier1(self, session_id, file_mtime_ms=BASE_TIME_MS, source_path="/repo/a"):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=file_mtime_ms, source_path=source_path, session_id=session_id,
        )

    def test_session_with_file_is_filled_session_without_stays_none(self) -> None:
        with_file = self._session_facts("s-a", "/repo/a", BASE_TIME_MS)
        without_file = self._session_facts("s-b", "/repo/a", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (with_file, without_file)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
            session_dashboards_by_path={"/repo/a": (self._session_tier1("s-a"),)},
        )
        # B-8(검수 2회차): dict 변환에 기대지 않고 세션 뷰 순서 자체를 먼저 확인한다 —
        # {facts.session_id: view} 로 바로 넘어가면 순서가 뒤집혀도 이 테스트가 못 잡는다.
        session_ids_in_order = [session.session_id for session in views[0].sessions]
        self.assertEqual(session_ids_in_order, ["s-a", "s-b"])
        sessions_by_id = {session.session_id: session for session in views[0].sessions}
        self.assertIsNotNone(sessions_by_id["s-a"].tier1)
        self.assertIsNotNone(sessions_by_id["s-a"].dashboard_key)
        self.assertIsNone(sessions_by_id["s-b"].tier1)
        self.assertIsNone(sessions_by_id["s-b"].dashboard_key)
        # B-8: 세션별 대시보드 주입이 기존 필드(state·short_id)를 건드리지 않는다.
        self.assertEqual(sessions_by_id["s-a"].state, "idle")
        self.assertEqual(sessions_by_id["s-a"].short_id, "s-a"[:8])

    def test_missing_session_dashboards_by_path_argument_defaults_all_sessions_to_none(self) -> None:
        """기존 호출부(session_dashboards_by_path 없이 부름)가 무해하다 — 기본값 None."""
        facts = self._session_facts("s1", "/repo/a", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertIsNone(views[0].sessions[0].tier1)
        self.assertIsNone(views[0].sessions[0].dashboard_key)


class IndexSessionDashboardsTest(unittest.TestCase):
    """P5(hub-session-tree-and-per-session-dashboards.md) — index_session_dashboards: 세션당
    mtime 최신 승자, 동률은 앞, session_id=None 제외(결정 ST12)."""

    def _tier1(self, session_id, file_mtime_ms, source_path="/repo"):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=file_mtime_ms, source_path=source_path, session_id=session_id,
        )

    def test_newer_mtime_wins_for_the_same_session(self) -> None:
        root_file = self._tier1("s1", file_mtime_ms=1_000, source_path="/repo")
        worktree_file = self._tier1("s1", file_mtime_ms=2_000, source_path="/repo/.claude/worktrees/w")
        winners = hub_project.index_session_dashboards((root_file, worktree_file))
        self.assertEqual(winners["s1"].source_path, "/repo/.claude/worktrees/w")

    def test_tie_favors_the_earlier_candidate_in_the_list(self) -> None:
        first = self._tier1("s1", file_mtime_ms=1_000, source_path="/repo")
        second = self._tier1("s1", file_mtime_ms=1_000, source_path="/repo/.claude/worktrees/w")
        winners = hub_project.index_session_dashboards((first, second))
        self.assertEqual(winners["s1"].source_path, "/repo")

    def test_legacy_snapshot_without_session_id_is_excluded(self) -> None:
        legacy = self._tier1(None, file_mtime_ms=1_000)
        winners = hub_project.index_session_dashboards((legacy,))
        self.assertEqual(winners, {})


class ComposeProjectViewsWorkflowBySessionIdTest(unittest.TestCase):
    """§11 — workflow_by_session_id(결정 WF1, docs/prps/hub-workflow-visibility.md)."""

    def _session_facts(self, session_id, cwd, last_event_at_ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=last_event_at_ms,
            last_event_at_ms=last_event_at_ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def _workflow(self) -> hub_workflow.WorkflowRunView:
        return hub_workflow.WorkflowRunView(agents=())

    def test_workflow_is_assigned_only_to_the_matching_session(self) -> None:
        with_workflow = self._session_facts("s-with-workflow", "/repo/a", BASE_TIME_MS)
        without_workflow = self._session_facts("s-without-workflow", "/repo/a", BASE_TIME_MS)
        workflow = self._workflow()
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (with_workflow, without_workflow)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
            workflow_by_session_id={"s-with-workflow": workflow},
        )
        sessions_by_id = {session.session_id: session for session in views[0].sessions}
        self.assertEqual(sessions_by_id["s-with-workflow"].workflow, workflow)
        self.assertIsNone(sessions_by_id["s-without-workflow"].workflow)

    def test_missing_workflow_by_session_id_argument_defaults_all_sessions_to_none(self) -> None:
        """기존 호출부(workflow_by_session_id 없이 부름)가 무해하다 — 기본값 None."""
        facts = self._session_facts("s1", "/repo/a", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertIsNone(views[0].sessions[0].workflow)


class ComposeProjectViewsDashboardEnabledTest(unittest.TestCase):
    """RL10(docs/prps/hub-card-gate-and-run-list-reset.md §5.1) — dashboard_enabled_by_path 가
    판단 없이 compute_session_view 의 실행 목록 경계 판정까지 전달된다. 경계의 프롬프트는 훅 시각이 아니라
    transcript 꼬리의 사람 입력 시각이다(tail_by_session_id 로 넘긴다 — 알림에도 발화하는 훅 값은 경계에 쓰지 않는다)."""

    def _human_prompt_tail(self, session_id, human_prompt_at_ms):
        tail = hub_transcript.SessionTail(model=None, last_prompt=None, last_human_prompt_at_ms=human_prompt_at_ms)
        return {session_id: tail}

    def _session_facts_with_one_run(self, session_id, cwd, prompt_at_ms, run_started_at_ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=run_started_at_ms,
            last_event_at_ms=prompt_at_ms, last_event_name="UserPromptSubmit", turn_state="running",
            ended_at_ms=None,
            subagents=(
                hub_session_facts.SubagentFact(
                    agent_id="agt-1", agent_type="implementer",
                    started_at_ms=run_started_at_ms, ended_at_ms=run_started_at_ms + 1000,
                ),
            ),
            last_prompt_at_ms=prompt_at_ms,
        )

    def test_missing_dashboard_enabled_by_path_argument_defaults_to_true_for_existing_call_sites(self) -> None:
        """기존 호출부(dashboard_enabled_by_path 없이 부름)가 무해하다 — 기본값 켜짐."""
        facts = self._session_facts_with_one_run("s1", "/repo/a", BASE_TIME_MS + 10_000, BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 10_000, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id=self._human_prompt_tail("s1", BASE_TIME_MS + 10_000),
        )
        self.assertTrue(views[0].sessions[0].agent_runs[0].is_previous_task)

    def test_dashboard_disabled_project_keeps_runs_before_prompt_visible(self) -> None:
        """RL10 — 껐으면 프롬프트로 경계를 추측하지 않는다(반례 B 재발 방지)."""
        facts = self._session_facts_with_one_run("s1", "/repo/a", BASE_TIME_MS + 10_000, BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 10_000, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id=self._human_prompt_tail("s1", BASE_TIME_MS + 10_000),
            dashboard_enabled_by_path={"/repo/a": False},
        )
        self.assertFalse(views[0].sessions[0].agent_runs[0].is_previous_task)

    def test_dashboard_enabled_false_is_assigned_only_to_the_matching_project_path(self) -> None:
        facts_a = self._session_facts_with_one_run("s-a", "/repo/a", BASE_TIME_MS + 10_000, BASE_TIME_MS)
        facts_b = self._session_facts_with_one_run("s-b", "/repo/b", BASE_TIME_MS + 10_000, BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts_a,), "/repo/b": (facts_b,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 10_000, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id={
                **self._human_prompt_tail("s-a", BASE_TIME_MS + 10_000),
                **self._human_prompt_tail("s-b", BASE_TIME_MS + 10_000),
            },
            dashboard_enabled_by_path={"/repo/a": False},
        )
        runs_by_path = {view.path: view.sessions[0].agent_runs[0] for view in views}
        self.assertFalse(runs_by_path["/repo/a"].is_previous_task)
        self.assertTrue(runs_by_path["/repo/b"].is_previous_task)

    def test_dashboard_enabled_true_entry_behaves_like_default(self) -> None:
        facts = self._session_facts_with_one_run("s1", "/repo/a", BASE_TIME_MS + 10_000, BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS + 10_000, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id=self._human_prompt_tail("s1", BASE_TIME_MS + 10_000),
            dashboard_enabled_by_path={"/repo/a": True},
        )
        self.assertTrue(views[0].sessions[0].agent_runs[0].is_previous_task)


class ComposeProjectViewsSubagentActivityTest(unittest.TestCase):
    """SL-P1(G7) — docs/prps/hub-subagent-liveness-signal.md 결정 SL4·SL6.
    subagent_activity_by_agent_id 가 subagent_meta_by_agent_id 와 같은 경로로 전달돼
    프로젝트 카드까지 교정하는지 확인한다."""

    def _session_facts_with_unfinished_subagent(self, session_id, cwd, started_at_ms, agent_id):
        subagent = hub_session_facts.SubagentFact(
            agent_id=agent_id, agent_type="implementer", started_at_ms=started_at_ms, ended_at_ms=None,
        )
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=started_at_ms,
            last_event_at_ms=started_at_ms, last_event_name="SubagentStart", turn_state="ended",
            ended_at_ms=None, subagents=(subagent,),
        )

    def test_project_state_is_corrected_when_activity_dict_is_passed(self) -> None:
        """G7 — 42분째 도는 실행 하나뿐인 세션의 프로젝트 카드가 working 으로 교정된다."""
        forty_two_minutes_ms = 42 * 60 * 1000
        one_minute_ms = 60 * 1000
        facts = self._session_facts_with_unfinished_subagent("s1", "/repo/a", BASE_TIME_MS, "agt-1")
        now_ms = BASE_TIME_MS + forty_two_minutes_ms
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
            subagent_activity_by_agent_id={"agt-1": now_ms - one_minute_ms},
        )
        self.assertEqual(views[0].state, "working")

    def test_missing_subagent_activity_argument_keeps_todays_verdict(self) -> None:
        """넘기지 않으면 오늘의 값 그대로 — 기본값 None 이 기존 호출부를 무해하게 둔다."""
        forty_two_minutes_ms = 42 * 60 * 1000
        facts = self._session_facts_with_unfinished_subagent("s1", "/repo/a", BASE_TIME_MS, "agt-1")
        now_ms = BASE_TIME_MS + forty_two_minutes_ms
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "stale")


class ComposeProjectViewsLiveActivityTest(unittest.TestCase):
    """LA-PJ1(docs/prps/hub-live-activity.md 결정 LA14) — `live_activity` 가 판단 없이 세션 뷰까지 전달된다.
    SL6 의 `subagent_activity_by_agent_id` 와 같은 모양의 통과 배선이고, 기본값 None 이 기존 호출부를 무해하게 둔다."""

    def _facts(self):
        subagent = hub_session_facts.SubagentFact(
            agent_id="agt-1", agent_type="implementer", started_at_ms=BASE_TIME_MS, ended_at_ms=None,
        )
        return hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo/a", observed_cwds=("/repo/a",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="SubagentStart", turn_state="ended",
            ended_at_ms=None, subagents=(subagent,),
        )

    def _activity(self):
        return hub_activity.SubagentActivity(
            last_record_at_ms=BASE_TIME_MS + 1000, last_tool_kind="edit", pending_count=0, pending_tool_kind=None,
            pending_since_ms=None, recent_tool_counts=hub_activity.ToolKindCounts(edit=1),
            recent_counts_since_ms=BASE_TIME_MS,
        )

    def _compose(self, **kwargs):
        return hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (self._facts(),)}, tier3_last_activity_by_path={},
            now_ms=BASE_TIME_MS + 60_000, stale_after_ms=STALE_AFTER_MS, **kwargs,
        )

    def test_la_pj1_live_activity_reaches_the_session_view(self) -> None:
        live_activity = hub_activity.LiveActivity({"agt-1": self._activity()}, {})

        views = self._compose(live_activity=live_activity)

        run = views[0].sessions[0].agent_runs[0]
        self.assertEqual(run.activity.last_tool_kind, "edit")
        self.assertIsNotNone(run.activity.stall_suspect_at_ms)

    def test_without_live_activity_the_view_is_todays(self) -> None:
        views = self._compose()

        self.assertIsNone(views[0].sessions[0].agent_runs[0].activity)

    def test_la_v5_project_state_is_not_changed_by_live_activity(self) -> None:
        stalled = dataclasses.replace(self._activity(), last_record_at_ms=BASE_TIME_MS - 3_600_000)
        live_activity = hub_activity.LiveActivity({"agt-1": stalled}, {})

        without = self._compose()
        with_stall = self._compose(live_activity=live_activity)

        self.assertEqual(with_stall[0].state, without[0].state)
        self.assertEqual(with_stall[0].sessions[0].state, without[0].sessions[0].state)


class Tier1PriorityTest(unittest.TestCase):
    """쟁점 3 — 티어 1 이 있으면 티어 1 이 이긴다(합성 시 tier=1)."""

    def test_tier1_present_wins_over_sessions(self) -> None:
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-", file_mtime_ms=BASE_TIME_MS,
        )
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1}, sessions_by_path={}, tier3_last_activity_by_path={},
            now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].tier, 1)


class ProjectDashboardKeyTest(unittest.TestCase):
    """U1~U3 — project_dashboard_key 의 결정성·충돌 회피·형식(결정 N1)."""

    def test_u1_same_path_always_same_key(self) -> None:
        self.assertEqual(
            hub_project.project_dashboard_key("/Users/b/repo"),
            hub_project.project_dashboard_key("/Users/b/repo"),
        )

    def test_u2_different_paths_never_collide(self) -> None:
        """구 인코딩(encode_project_dir_name)은 '/a.b' 와 '/a/b' 를 같은 키로 만들었다 —
        sha256 기반은 그 충돌 사례를 포함해 서로 다른 경로가 다른 키를 갖는다."""
        self.assertNotEqual(
            hub_project.project_dashboard_key("/a.b"),
            hub_project.project_dashboard_key("/a/b"),
        )

    def test_u3_key_matches_hex_pattern_and_length(self) -> None:
        key = hub_project.project_dashboard_key("/Users/b/repo")
        self.assertRegex(key, r"^[0-9a-f]{16}$")
        self.assertEqual(len(key), hub_project.DASHBOARD_KEY_LENGTH)


class ComposeProjectViewsDashboardKeyTest(unittest.TestCase):
    """U6 — compose_project_views 가 티어 1 에만 dashboard_key 를 채운다."""

    def test_u6_only_tier1_view_has_dashboard_key(self) -> None:
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-", file_mtime_ms=BASE_TIME_MS,
        )
        tier2_session = hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo/tier2", observed_cwds=("/repo/tier2",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo/tier1": tier1},
            sessions_by_path={"/repo/tier2": (tier2_session,)},
            tier3_last_activity_by_path={"/repo/tier3": BASE_TIME_MS},
            now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        by_path = {view.path: view for view in views}
        self.assertEqual(
            by_path["/repo/tier1"].dashboard_key, hub_project.project_dashboard_key("/repo/tier1")
        )
        self.assertIsNone(by_path["/repo/tier2"].dashboard_key)
        self.assertIsNone(by_path["/repo/tier3"].dashboard_key)


class SessionIdFromDashboardFileNameTest(unittest.TestCase):
    """P1(hub-session-tree-and-per-session-dashboards.md) — session_id_from_dashboard_file_name:
    정상 uuid 만 통과, 나머지 None(결정 ST9). M2(dashboard-into-hub.md HD6)로 확장자가
    `.jsonl` 로 바뀌었다."""

    VALID_UUID = "f733cfcd-32eb-4339-9d99-e7375887e376"

    def test_valid_uuid_file_name_returns_the_uuid(self) -> None:
        self.assertEqual(
            hub_project.session_id_from_dashboard_file_name(f"{self.VALID_UUID}.jsonl"),
            self.VALID_UUID,
        )

    def test_uppercase_uuid_is_rejected(self) -> None:
        self.assertIsNone(
            hub_project.session_id_from_dashboard_file_name(f"{self.VALID_UUID.upper()}.jsonl")
        )

    def test_wrong_length_is_rejected(self) -> None:
        """길이 35 — uuid 를 한 글자 자른 값은 정규식을 통과하지 않는다."""
        truncated_to_35_chars = self.VALID_UUID[:-1]
        self.assertIsNone(hub_project.session_id_from_dashboard_file_name(f"{truncated_to_35_chars}.jsonl"))

    def test_html_extension_is_rejected(self) -> None:
        """M2 회귀 — M1 까지의 확장자(.html)는 더 이상 세션 파일로 인식되지 않는다(HD6)."""
        self.assertIsNone(hub_project.session_id_from_dashboard_file_name(f"{self.VALID_UUID}.html"))

    def test_path_traversal_attempt_is_rejected(self) -> None:
        self.assertIsNone(hub_project.session_id_from_dashboard_file_name(f"../{self.VALID_UUID}.jsonl"))

    def test_empty_string_is_rejected(self) -> None:
        self.assertIsNone(hub_project.session_id_from_dashboard_file_name(""))


class SessionDashboardRelativePathTest(unittest.TestCase):
    """P2(hub-session-tree-and-per-session-dashboards.md) — session_dashboard_relative_path 의
    정확한 형태(결정 ST1). M2(HD6)로 확장자가 `.jsonl` 로 바뀌었다."""

    def test_relative_path_has_no_leading_slash(self) -> None:
        session_id = "f733cfcd-32eb-4339-9d99-e7375887e376"
        relative_path = hub_project.session_dashboard_relative_path(session_id)
        self.assertEqual(relative_path, f".claude/dashboards/{session_id}.jsonl")
        self.assertFalse(relative_path.startswith("/"))


class TierOneFilePathAndDashboardFileKeyTest(unittest.TestCase):
    """P3(hub-session-tree-and-per-session-dashboards.md) — tier1_file_path·dashboard_file_key
    (결정 ST13·ST14). M2(dashboard-into-hub.md HD7)로 레거시 단일 파일 갈래가 폐기돼
    tier1_file_path 는 이제 항상 세션별 경로 하나로만 조립한다."""

    def _tier1(self, source_path, session_id=None):
        return hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=1, source_path=source_path, session_id=session_id,
        )

    def test_session_tier1_resolves_to_its_own_file(self) -> None:
        tier1 = self._tier1("/repo", session_id="f733cfcd-32eb-4339-9d99-e7375887e376")
        self.assertEqual(
            hub_project.tier1_file_path(tier1),
            "/repo/.claude/dashboards/f733cfcd-32eb-4339-9d99-e7375887e376.jsonl",
        )

    def test_dashboard_file_key_matches_hex_pattern_and_length(self) -> None:
        # B-8(검수 2회차): 정규식·길이만 보면 sha256 이 md5 등 다른 알고리즘으로 바뀌어도
        # (자리 수만 맞으면) 통과한다 — 기대 해시를 테스트 안에서 직접 계산해 알고리즘까지 고정한다.
        tier1 = self._tier1("/repo")
        file_path = hub_project.tier1_file_path(tier1)
        key = hub_project.dashboard_file_key(file_path)
        expected_key = hashlib.sha256(file_path.encode("utf-8")).hexdigest()[: hub_project.DASHBOARD_KEY_LENGTH]
        self.assertEqual(key, expected_key)
        self.assertEqual(len(key), hub_project.DASHBOARD_KEY_LENGTH)

    def test_dashboard_file_key_differs_from_project_dashboard_key(self) -> None:
        tier1 = self._tier1("/repo")
        file_path = hub_project.tier1_file_path(tier1)
        self.assertNotEqual(
            hub_project.dashboard_file_key(file_path),
            hub_project.project_dashboard_key(tier1.source_path),
        )


class ProjectStatePriorityWithInterruptedTest(unittest.TestCase):
    """P1 — docs/prps/hub-rate-limit-interruption.md 결정 RI9. PROJECT_STATE_PRIORITY 의
    interrupted 순위(working 다음·idle 앞)."""

    def _idle_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def _interrupted_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="StopFailure", turn_state="ended",
            ended_at_ms=None, subagents=(), failed_turn=hub_session_facts.FailedTurn("rate_limit", ms),
        )

    def _working_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="UserPromptSubmit", turn_state="running",
            ended_at_ms=None, subagents=(),
        )

    def test_p1_idle_and_interrupted_sessions_make_the_project_interrupted(self) -> None:
        idle = self._idle_facts("s-idle", "/repo", BASE_TIME_MS)
        interrupted = self._interrupted_facts("s-interrupted", "/repo", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (idle, interrupted)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "interrupted")

    def test_p1_working_session_still_wins_over_interrupted(self) -> None:
        working = self._working_facts("s-working", "/repo", BASE_TIME_MS)
        interrupted = self._interrupted_facts("s-interrupted", "/repo", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (working, interrupted)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "working")


class TailBySessionIdTurnFailureWiringTest(unittest.TestCase):
    """P2 — tail_by_session_id 의 turn_failure 가 세션 뷰까지 배선된다(판단 0, 배선만)."""

    def test_p2_turn_failure_flows_from_tail_to_session_view_interruption(self) -> None:
        facts = hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo/a", observed_cwds=("/repo/a",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )
        turn_failure = hub_transcript.TranscriptTurnFailure(
            error_kind="rate_limit", failed_at_ms=BASE_TIME_MS, resets_at_ms=BASE_TIME_MS + 60000
        )
        tail = hub_transcript.SessionTail(model=None, last_prompt=None, turn_failure=turn_failure)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
            tail_by_session_id={"s1": tail},
        )
        session_view = views[0].sessions[0]
        self.assertEqual(session_view.state, "interrupted")
        self.assertIsNotNone(session_view.interruption)
        self.assertEqual(session_view.interruption.resets_at_ms, BASE_TIME_MS + 60000)

    def test_p2_missing_tail_leaves_interruption_none(self) -> None:
        """기존 호출부(tail_by_session_id 없이 부름)가 무해하다 — 배선 자체가 인터럽션을
        만들어내지 않는다."""
        facts = hub_session_facts.SessionFacts(
            session_id="s1", cwd="/repo/a", observed_cwds=("/repo/a",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo/a": (facts,)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertIsNone(views[0].sessions[0].interruption)


class ProjectStatePriorityWithBackgroundTest(unittest.TestCase):
    """P1 — docs/prps/hub-subagent-background-pause.md 결정 BW8. PROJECT_STATE_PRIORITY 의
    background 순위(interrupted 다음·idle 앞)."""

    def _idle_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def _background_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
            background_report=hub_session_facts.BackgroundReport(ms, (("shell", 1),), 0),
        )

    def _interrupted_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="StopFailure", turn_state="ended",
            ended_at_ms=None, subagents=(), failed_turn=hub_session_facts.FailedTurn("rate_limit", ms),
        )

    def _working_facts(self, session_id, cwd, ms):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=ms,
            last_event_at_ms=ms, last_event_name="UserPromptSubmit", turn_state="running",
            ended_at_ms=None, subagents=(),
        )

    def test_p1_background_and_idle_sessions_make_the_project_background(self) -> None:
        background = self._background_facts("s-background", "/repo", BASE_TIME_MS)
        idle = self._idle_facts("s-idle", "/repo", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (background, idle)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "background")

    def test_p1_interrupted_session_still_wins_over_background(self) -> None:
        interrupted = self._interrupted_facts("s-interrupted", "/repo", BASE_TIME_MS)
        background = self._background_facts("s-background", "/repo", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (interrupted, background)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "interrupted")

    def test_p1_working_session_still_wins_over_background(self) -> None:
        working = self._working_facts("s-working", "/repo", BASE_TIME_MS)
        background = self._background_facts("s-background", "/repo", BASE_TIME_MS)
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path={"/repo": (working, background)},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS,
        )
        self.assertEqual(views[0].state, "working")

    def test_p2_background_session_included_in_live_set_prevents_previous_task_label(self) -> None:
        """BW8 — LIVE_SESSION_STATES 에서 background 를 빼면(결함) 대시보드를 쓴 이
        background 세션 A 가 "살아 있는 세션" 집합에서 빠져, 더 늦게 시작한 working
        세션 B 만 살아 있다고 오판해 tier1_is_previous_task 가 True 로 켜진다(A 자신의
        진행 중 대시보드가 "이전 작업"으로 잘못 톤다운된다)."""
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=BASE_TIME_MS, source_path="/repo",
        )
        background_session = self._background_facts("s-background", "/repo", BASE_TIME_MS - 3_600_000)
        working_session = self._working_facts("s-working", "/repo", BASE_TIME_MS + 60_000)
        now_ms = BASE_TIME_MS + 60_000
        views = hub_project.compose_project_views(
            tier1_by_path={"/repo": tier1},
            sessions_by_path={"/repo": (background_session, working_session)},
            tier3_last_activity_by_path={}, now_ms=now_ms, stale_after_ms=STALE_AFTER_MS,
        )
        background_view = next(view for view in views[0].sessions if view.session_id == "s-background")
        self.assertEqual(background_view.state, "background")
        self.assertFalse(views[0].tier1_is_previous_task)


class ComposeProjectViewsSessionCostTest(unittest.TestCase):
    """⑨ — session_cost_by_session_id 는 판단 없이 세션 id 로 찾아 뷰에 싣는다(docs/prps/harness-benchmark-adoption.md §7-1)."""

    COST = hub_usage.SessionCost(captured_at_ms=BASE_TIME_MS, total_cost_cents=1284, api_duration_minutes=31, context_used_percent=62)

    def _session_facts(self, session_id):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd="/repo/a", observed_cwds=("/repo/a",), started_at_ms=BASE_TIME_MS,
            last_event_at_ms=BASE_TIME_MS, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def _sessions_by_id(self, **extra_arguments):
        views = hub_project.compose_project_views(
            tier1_by_path={},
            sessions_by_path={"/repo/a": (self._session_facts("s-with-cost"), self._session_facts("s-without-cost"))},
            tier3_last_activity_by_path={}, now_ms=BASE_TIME_MS, stale_after_ms=STALE_AFTER_MS, **extra_arguments,
        )
        return {session.session_id: session for session in views[0].sessions}

    def test_cost_is_assigned_only_to_the_matching_session(self) -> None:
        sessions = self._sessions_by_id(session_cost_by_session_id={"s-with-cost": self.COST})
        self.assertEqual(sessions["s-with-cost"].session_cost, self.COST)
        self.assertIsNone(sessions["s-without-cost"].session_cost)

    def test_missing_argument_defaults_all_sessions_to_none(self) -> None:
        """기존 호출부(session_cost_by_session_id 없이 부름)가 무해하다 — 기본값 None."""
        sessions = self._sessions_by_id()
        self.assertIsNone(sessions["s-with-cost"].session_cost)


if __name__ == "__main__":
    unittest.main()
