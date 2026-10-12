"""hub_dashboard_render.py 순수 로직 + hub_dashboard_log.py I/O 층 단위 테스트.

docs/prps/dashboard-native-data-source.md §7.1 테스트 계획 대상. 파일명은 이전 PRP
(dashboard-worktree-bash-gate.md)가 `tests/commands/test_dashboard_helper.py` 로 지정한
이후 docs/prps/dashboard-into-hub.md M1(HD1·HD4)에서 이 경로로 이전됐다 — 두 모듈을 한
파일에서 함께 다루는 구성은 그대로 승계했다.
- hub_dashboard_render.py(★순수): 상세 마크업·로그 렌더·앵커 치환(이벤트 파싱·단계 상태
  파생은 docs/prps/dashboard-into-hub.md M2 에서 hub_parse.py 로 옮겨갔다).
- hub_dashboard_log.py(I/O 층): 세션/스위치 판정·리텐션·원자적 쓰기·서브커맨드 4종
  (init·log·step·switch, M2 HD15 — render 폐기)의 출력 계약. 이 부분은 실제 파일시스템에
  닿으므로 샌드박스 cwd·HOME 을 쓰고 실제 `$HOME` 은 절대 건드리지 않는다(각 테스트가
  tempfile 로 격리된 사본에서만 동작한다).
"""

import contextlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_atomic_write  # noqa: E402
import hub_collect  # noqa: E402
import hub_dashboard_log  # noqa: E402  (sys.path 조정 후 임포트)
import hub_dashboard_render  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402

# 템플릿 앵커 9종을 정확히 1회씩 담은 최소 픽스처 — 실제 hub_dashboard_template.html 의
# 발행 전 원본과 문자 단위로 같다(hub_dashboard_render.ANCHOR_* 상수 참고). 아래 순수 로직
# 테스트(RenderFromEventsTest 등)가 이 최소 픽스처를 쓴다. 헬퍼 I/O 테스트는 hub_dashboard_log
# 가 SCRIPT_DIR 기준으로 찾는 실제 배포 템플릿을 그대로 쓴다(HD3 — 프로젝트 폴백이 없어져
# 이 픽스처를 프로젝트 로컬에 심어 둘 수 없다).
_SANDBOX_TEMPLATE = (
    '  <span class="project-name" id="dz-project-name">프로젝트</span>\n'
    '    <h1 id="dz-title">세션 제목</h1>\n'
    '    <div class="bar-outer"><div class="bar-inner" id="dz-progress-bar" style="width:0%"></div></div>\n'
    '    <div class="pct" id="dz-progress-pct">0/0 · 0%</div>\n'
    '    <ol class="steps" id="dz-steps">\n'
    '    </ol>\n'
    '    <div class="pct" id="dz-impl-count">0/0 · 0%</div>\n'
    '    <ol class="steps" id="dz-impl-tasks">\n'
    '    </ol>\n'
    '    <ul class="log" id="dz-log" data-owner-token="" data-server-port=""></ul>\n'
    '  <div class="foot" id="dz-updated">갱신: -</div>\n'
)


class EscapeForDomTest(unittest.TestCase):
    """escape_for_dom — html.escape(quote=False) 위임, 순서·따옴표 보존 확인."""

    def test_less_than_escaped_once_not_double_escaped(self) -> None:
        """`&` 를 먼저 치환하므로 `<`→`&lt;` 가 만든 `&` 가 다시 이스케이프되지 않는다.
        순서가 반대라면 결과가 `&amp;lt;` 로 이중 이스케이프된다."""
        result = hub_dashboard_render.escape_for_dom("<")

        self.assertEqual(result, "&lt;")

    def test_angle_brackets_escaped(self) -> None:
        result = hub_dashboard_render.escape_for_dom("Foo<T>")

        self.assertEqual(result, "Foo&lt;T&gt;")

    def test_ampersand_in_logical_and_escaped(self) -> None:
        result = hub_dashboard_render.escape_for_dom("a && b")

        self.assertEqual(result, "a &amp;&amp; b")

    def test_quotes_are_not_escaped(self) -> None:
        result = hub_dashboard_render.escape_for_dom("""a "double" and 'single'""")

        self.assertEqual(result, """a "double" and 'single'""")


class DerivePhaseStatesTest(unittest.TestCase):
    """derive_phase_states — DN4 축약기: log 종류가 단계 전이를 함의하고 step 은 명시 갱신."""

    PHASES = ("설계", "승인", "구현", "검수")

    @staticmethod
    def _event(kind: str, **overrides: object) -> hub_dashboard_render.DashboardEvent:
        defaults: dict = {"time_ms": 1_700_000_000_000, "kind": kind}
        defaults.update(overrides)
        return hub_dashboard_render.DashboardEvent(**defaults)

    def test_full_standard_sequence_completes_all_four(self) -> None:
        events = (
            self._event("design"),
            self._event("approve"),
            self._event("impl"),
            self._event("pass"),
        )

        states = hub_dashboard_render.derive_phase_states(self.PHASES, events)

        self.assertEqual(states, ("done", "done", "done", "done"))

    def test_abbreviated_path_impl_then_pass(self) -> None:
        phases = ("구현", "검수")
        events = (self._event("impl"), self._event("pass"))

        states = hub_dashboard_render.derive_phase_states(phases, events)

        self.assertEqual(states, ("done", "done"))

    def test_fail_then_impl_then_pass_recovers(self) -> None:
        events = (
            self._event("impl"),
            self._event("fail"),
            self._event("impl"),
            self._event("pass"),
        )

        states_after_fail = hub_dashboard_render.derive_phase_states(self.PHASES, events[:2])
        states_after_recovery = hub_dashboard_render.derive_phase_states(self.PHASES, events)

        self.assertEqual(states_after_fail, ("done", "done", "active", "wait"))
        self.assertEqual(states_after_recovery, ("done", "done", "done", "done"))

    def test_skips_earlier_phases_when_only_later_kind_logged(self) -> None:
        """`impl` 만 기록해도 설계·승인이 앞서 완료된 것으로 본다(그 단계까지 완료 원칙)."""
        events = (self._event("impl"),)

        states = hub_dashboard_render.derive_phase_states(self.PHASES, events)

        self.assertEqual(states, ("done", "done", "done", "active"))

    def test_step_event_explicitly_sets_single_index(self) -> None:
        phases = ("원인 분석", "설계", "구현", "검수")
        events = (
            hub_dashboard_render.DashboardEvent(time_ms=1, kind="step", index=1, state="done"),
            hub_dashboard_render.DashboardEvent(time_ms=2, kind="step", index=2, state="active"),
        )

        states = hub_dashboard_render.derive_phase_states(phases, events)

        self.assertEqual(states, ("done", "active", "wait", "wait"))

    def test_log_kind_name_not_in_phase_list_is_ignored(self) -> None:
        phases = ("원인 분석", "설계", "구현", "검수")
        events = (self._event("approve"),)  # "승인" 은 이 비표준 목록에 없다

        states = hub_dashboard_render.derive_phase_states(phases, events)

        self.assertEqual(states, ("active", "wait", "wait", "wait"))

    def test_no_events_yields_first_phase_active(self) -> None:
        states = hub_dashboard_render.derive_phase_states(self.PHASES, ())

        self.assertEqual(states, ("active", "wait", "wait", "wait"))

    def test_repeating_same_event_is_idempotent(self) -> None:
        events = (self._event("impl"), self._event("impl"), self._event("impl"))

        states = hub_dashboard_render.derive_phase_states(self.PHASES, events)

        self.assertEqual(states, ("done", "done", "done", "active"))


class RenderDetailHtmlTest(unittest.TestCase):
    """render_detail_html — 이스케이프 → 블록 분할 → <p>/<ul> → 블록 안 백틱 짝짓기."""

    def test_empty_string_yields_no_detail_placeholder(self) -> None:
        self.assertEqual(hub_dashboard_render.render_detail_html(""), "(상세 없음)")

    def test_single_paragraph_renders_as_bare_text(self) -> None:
        result = hub_dashboard_render.render_detail_html("한 줄 상세")

        self.assertEqual(result, "한 줄 상세")

    def test_two_paragraphs_each_wrapped_in_p_tag(self) -> None:
        result = hub_dashboard_render.render_detail_html("첫 문단\n\n둘째 문단")

        self.assertEqual(result, "<p>첫 문단</p><p>둘째 문단</p>")

    def test_dash_prefixed_block_becomes_unordered_list(self) -> None:
        result = hub_dashboard_render.render_detail_html("- 첫째\n- 둘째")

        self.assertEqual(result, "<ul><li>첫째</li><li>둘째</li></ul>")

    def test_mixed_paragraph_and_list_blocks(self) -> None:
        result = hub_dashboard_render.render_detail_html("문단\n\n- 목록1\n- 목록2")

        self.assertEqual(result, "<p>문단</p><ul><li>목록1</li><li>목록2</li></ul>")

    def test_backtick_pairing_does_not_cross_block_boundary(self) -> None:
        """블록 하나에 백틱이 홀수 개면 다음 블록의 백틱과 짝지어지지 않는다."""
        result = hub_dashboard_render.render_detail_html("`code 시작\n\n닫는 백틱`")

        self.assertNotIn("<code>", result)
        self.assertIn("`code 시작", result)
        self.assertIn("닫는 백틱`", result)

    def test_odd_backtick_count_kept_literal(self) -> None:
        result = hub_dashboard_render.render_detail_html("`a` 그리고 `b")

        self.assertEqual(result, "<code>a</code> 그리고 `b")

    def test_escaping_happens_before_markup(self) -> None:
        result = hub_dashboard_render.render_detail_html("<script> & `code`")

        self.assertEqual(result, "&lt;script&gt; &amp; <code>code</code>")

    def test_whitespace_only_line_is_block_boundary(self) -> None:
        result = hub_dashboard_render.render_detail_html("첫 문단\n   \n둘째 문단")

        self.assertEqual(result, "<p>첫 문단</p><p>둘째 문단</p>")

    def test_result_never_has_newline_between_tags(self) -> None:
        """구 불변식 10 — `.detail` 은 태그 사이 개행 없이 한 줄로 조립된다."""
        result = hub_dashboard_render.render_detail_html("문단1\n\n- a\n- b\n\n문단2")

        self.assertNotIn(">\n<", result)


class ParseEventLinesTest(unittest.TestCase):
    """parse_event_lines — 줄 단위 fail-open, 마지막 init 이후만 반환."""

    @staticmethod
    def _init_line(title: str = "제목", time_ms: int = 1_700_000_000_000) -> str:
        return json.dumps(
            {"time_ms": time_ms, "kind": "init", "title": title, "phases": ["구현", "검수"], "project": "p"},
            ensure_ascii=False,
        )

    def test_malformed_json_line_is_skipped(self) -> None:
        text = self._init_line() + "\n{not json\n"

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_unknown_kind_is_skipped(self) -> None:
        text = self._init_line() + "\n" + json.dumps({"time_ms": 1, "kind": "unknown"})

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_type_mismatch_is_skipped(self) -> None:
        """summary 가 문자열이 아니라 숫자면 그 줄만 건너뛴다."""
        text = self._init_line() + "\n" + json.dumps(
            {"time_ms": 1_700_000_000_002, "kind": "impl", "summary": 42}
        )

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_no_init_event_returns_empty_tuple(self) -> None:
        text = json.dumps({"time_ms": 1_700_000_000_000, "kind": "impl", "summary": "s", "detail": ""})

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(events, ())

    def test_two_init_events_keeps_only_after_the_last(self) -> None:
        first_init = self._init_line(title="첫 제목", time_ms=1_700_000_000_001)
        impl_before_second_init = json.dumps(
            {"time_ms": 1_700_000_000_002, "kind": "impl", "summary": "가려짐", "detail": ""}
        )
        second_init = self._init_line(title="둘째 제목", time_ms=1_700_000_000_003)
        text = "\n".join([first_init, impl_before_second_init, second_init])

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "둘째 제목")


class RenderLogEntryLinesTest(unittest.TestCase):
    """render_log_entry_lines — 최신이 위, data-seq 연속, 최신 3건만 open, pass/fail 만 R{n}."""

    @staticmethod
    def _event(kind: str, time_ms: int, summary: str = "요약", detail: str = "") -> hub_dashboard_render.DashboardEvent:
        return hub_dashboard_render.DashboardEvent(time_ms=time_ms, kind=kind, summary=summary, detail=detail)

    def test_newest_event_appears_first(self) -> None:
        events = (self._event("design", 1, "오래됨"), self._event("impl", 2, "최신"))

        joined = "\n".join(hub_dashboard_render.render_log_entry_lines(events))

        self.assertLess(joined.index("최신"), joined.index("오래됨"))

    def test_data_seq_is_contiguous_starting_from_one(self) -> None:
        events = tuple(self._event("note", i, "메모%d" % i) for i in range(1, 4))

        joined = "\n".join(hub_dashboard_render.render_log_entry_lines(events))

        for seq in (1, 2, 3):
            self.assertIn('data-seq="%d"' % seq, joined)

    def test_only_newest_three_are_open(self) -> None:
        events = tuple(self._event("note", i) for i in range(1, 5))

        joined = "\n".join(hub_dashboard_render.render_log_entry_lines(events))

        self.assertEqual(joined.count("<details open>"), 3)

    def test_only_pass_and_fail_get_round_badge(self) -> None:
        events = (self._event("design", 1), self._event("impl", 2), self._event("pass", 3))

        joined = "\n".join(hub_dashboard_render.render_log_entry_lines(events))

        self.assertEqual(joined.count('class="badge round"'), 1)

    def test_round_number_accumulates_across_pass_and_fail(self) -> None:
        events = (self._event("fail", 1), self._event("impl", 2), self._event("pass", 3))

        joined = "\n".join(hub_dashboard_render.render_log_entry_lines(events))

        self.assertIn(">R1<", joined)
        self.assertIn(">R2<", joined)

    def test_kind_to_badge_mapping_for_all_seven_kinds(self) -> None:
        kind_to_badge_class = {
            "design": "impl",
            "approve": "impl",
            "impl": "impl",
            "pass": "pass",
            "fail": "fail",
            "commit": "commit",
            "note": "impl",
        }
        for index, (kind, badge_class) in enumerate(kind_to_badge_class.items()):
            with self.subTest(kind=kind):
                joined = "\n".join(hub_dashboard_render.render_log_entry_lines((self._event(kind, index),)))

                self.assertIn('class="badge %s"' % badge_class, joined)

    def test_summary_is_escaped(self) -> None:
        joined = "\n".join(hub_dashboard_render.render_log_entry_lines((self._event("note", 1, summary="<b>굵게</b>"),)))

        self.assertIn("&lt;b&gt;굵게&lt;/b&gt;", joined)
        self.assertNotIn("<b>굵게</b>", joined)

    def test_each_entry_closes_its_own_li_tag(self) -> None:
        joined = "\n".join(hub_dashboard_render.render_log_entry_lines((self._event("note", 1), self._event("note", 2))))

        self.assertEqual(joined.count("<li"), 2)
        self.assertEqual(joined.count("</li>"), 2)


class BuildPublishedValuesTest(unittest.TestCase):
    """build_published_values — 이벤트 → 앵커 9종 값. impl 슬롯 None 고정, owner_token 앞 8자리."""

    SESSION_ID = "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2"

    def test_progress_percent_matches_width_and_text(self) -> None:
        init_event = hub_dashboard_render.DashboardEvent(
            time_ms=1, kind="init", title="t", phases=("a", "b", "c"), project="p"
        )
        step_event = hub_dashboard_render.DashboardEvent(time_ms=2, kind="step", index=2, state="done")

        values = hub_dashboard_render.build_published_values((init_event, step_event), self.SESSION_ID)

        self.assertEqual(values.progress_text_html, "1/3 · 33%")
        self.assertEqual(values.progress_width, "33%")

    def test_impl_slots_are_always_none(self) -> None:
        init_event = hub_dashboard_render.DashboardEvent(
            time_ms=1, kind="init", title="t", phases=("구현", "검수"), project="p"
        )

        values = hub_dashboard_render.build_published_values((init_event,), self.SESSION_ID)

        self.assertIsNone(values.impl_count_html)
        self.assertIsNone(values.impl_block_lines)

    def test_owner_token_is_first_eight_chars_of_session_id(self) -> None:
        init_event = hub_dashboard_render.DashboardEvent(
            time_ms=1, kind="init", title="t", phases=("구현",), project="p"
        )

        values = hub_dashboard_render.build_published_values((init_event,), self.SESSION_ID)

        self.assertEqual(values.log_owner_token, "d4973ae5")

    def test_updated_html_reflects_last_event_time(self) -> None:
        init_event = hub_dashboard_render.DashboardEvent(
            time_ms=1_700_000_000_000, kind="init", title="t", phases=("구현",), project="p"
        )
        later_event = hub_dashboard_render.DashboardEvent(time_ms=1_800_000_000_000, kind="note", summary="s", detail="")

        values = hub_dashboard_render.build_published_values((init_event, later_event), self.SESSION_ID)

        self.assertEqual(values.updated_html, hub_parse.format_event_updated_label(1_800_000_000_000))

    def test_first_event_not_init_raises_value_error(self) -> None:
        not_init_event = hub_dashboard_render.DashboardEvent(time_ms=1, kind="note", summary="s")

        with self.assertRaises(ValueError):
            hub_dashboard_render.build_published_values((not_init_event,), self.SESSION_ID)


class RenderFromEventsTest(unittest.TestCase):
    """render_from_events — build_published_values + render_reissue 의 합성."""

    SESSION_ID = "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2"

    def test_matches_manual_composition(self) -> None:
        events = (
            hub_dashboard_render.DashboardEvent(time_ms=1, kind="init", title="t", phases=("구현", "검수"), project="p"),
        )

        via_helper = hub_dashboard_render.render_from_events(_SANDBOX_TEMPLATE, events, self.SESSION_ID)
        via_manual = hub_dashboard_render.render_reissue(
            _SANDBOX_TEMPLATE, hub_dashboard_render.build_published_values(events, self.SESSION_ID)
        )

        self.assertEqual(via_helper, via_manual)

    def test_zero_log_events_closes_log_block_exactly_once(self) -> None:
        """H3(검수 1회차 정정) — init 만 있고 로그 이벤트가 0건이면 `</ul>` 은 문서 전체에 정확히
        한 번만 나타난다(템플릿에 `<ul>` 이 #dz-log 하나뿐이므로). 옛 "기존 HTML 추출 →
        슬라이스 → 재접합" 파이프라인 특유의 닫는 태그 중복·누락 버그는 이 새 파이프라인
        (_render_log_block 이 매번 문자열을 새로 만든다)에서 구조적으로 재발할 수 없지만, 그
        성질을 직접 단언하는 테스트가 없었다 — 위 test_matches_manual_composition 은
        render_from_events 를 두 경로로 불러 비교할 뿐인 동어반복이라 이 성질을 잡지 못한다.

        `count("></ul>")`(여는 태그 직후 닫힘만 확인)나 `assertIn(정확한 문자열)` 만으로는
        부족하다 — 직접 깨뜨려 확인한 결과, 닫는 태그가 뒤에 하나 더 붙는 회귀
        (`...></ul></ul>`)를 두 방식 모두 놓친다(각각 여전히 1 과 True 를 낸다). 문서 전체의
        `</ul>` 개수를 세야 그 결함을 잡는다."""
        events = (
            hub_dashboard_render.DashboardEvent(time_ms=1, kind="init", title="t", phases=("구현", "검수"), project="p"),
        )

        rendered = hub_dashboard_render.render_from_events(_SANDBOX_TEMPLATE, events, self.SESSION_ID)

        self.assertEqual(rendered.count("</ul>"), 1)
        self.assertIn(
            '<ul class="log" id="dz-log" data-owner-token="d4973ae5" data-server-port=""></ul>', rendered
        )


class ResolvePathsRuntimeContractTest(unittest.TestCase):
    """hub_dashboard_log._resolve_paths — 검수 1회차 F13.

    경로 탈출 방어를 실제로 지키는 것은 이 함수(_resolve_paths, HD14 — hub_project 상수를
    직접 재사용)다. M2(dashboard-into-hub.md HD8)에서 html·사이드카 경로가 사라져 이 함수는
    이제 jsonl 경로 하나만 돌려준다 — 옛 hub_dashboard_render.resolve_dashboard_paths 와
    그 계약을 고정하던 테스트는 그 함수 자체와 함께 삭제됐다(§10.3)."""

    _SESSION_ID = "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2"

    def test_valid_lowercase_uuid_resolves_the_jsonl_path(self) -> None:
        paths = hub_dashboard_log._resolve_paths(self._SESSION_ID)

        self.assertIsNotNone(paths)
        self.assertEqual(paths.jsonl_path, ".claude/dashboards/%s.jsonl" % self._SESSION_ID)

    def test_uppercase_uuid_is_rejected(self) -> None:
        self.assertIsNone(hub_dashboard_log._resolve_paths(self._SESSION_ID.upper()))

    def test_path_traversal_segments_are_rejected(self) -> None:
        self.assertIsNone(hub_dashboard_log._resolve_paths("../../etc/passwd"))
        self.assertIsNone(hub_dashboard_log._resolve_paths(self._SESSION_ID + "/../x"))

    def test_none_session_id_returns_none(self) -> None:
        self.assertIsNone(hub_dashboard_log._resolve_paths(None))

    def test_empty_string_session_id_returns_none(self) -> None:
        self.assertIsNone(hub_dashboard_log._resolve_paths(""))


# ---------------------------------------------------------------------------
# 기록기 I/O 테스트 — hub_dashboard_log.py 는 ★순수가 아니다(파일시스템에 닿는다).
# 샌드박스 cwd·HOME 을 쓰고 실제 $HOME 은 절대 건드리지 않는다.
# ---------------------------------------------------------------------------


class _HelperIOTestCase(unittest.TestCase):
    """기록기 I/O 공통 준비 — 샌드박스 cwd·HOME, 유효 세션 ID.

    M2(dashboard-into-hub.md HD15)에서 기록기가 템플릿을 읽지 않게 됐다 — HTML 재발행
    경로 자체가 사라져 `hub_dashboard_log.py` 는 더 이상 템플릿 파일을 찾지 않는다(화면은
    허브 서버가 요청 시점에 렌더한다).
    """

    SESSION_ID = "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2"
    OWNER_TOKEN = "d4973ae5"

    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        root = pathlib.Path(tmpdir.name)
        self._project_dir = root / "project"
        home_dir = root / "home"
        self._project_dir.mkdir(parents=True)
        home_dir.mkdir(parents=True)

        original_cwd = os.getcwd()
        os.chdir(self._project_dir)
        self.addCleanup(os.chdir, original_cwd)

        env_patch = mock.patch.dict(
            os.environ, {"HOME": str(home_dir), "CLAUDE_CODE_SESSION_ID": self.SESSION_ID}
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def _dashboards_dir(self) -> pathlib.Path:
        return self._project_dir / ".claude" / "dashboards"

    def _settings_path(self) -> pathlib.Path:
        return self._project_dir / ".claude" / "settings.local.json"

    @staticmethod
    def _run(func, *args: object) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            func(*args)
        return buffer.getvalue().strip()

    def _init(self, title: str = "제목", phases: str = "구현|검수") -> str:
        return self._run(hub_dashboard_log.cmd_init, title, phases)


class HelperNoSessionAndDisabledTest(_HelperIOTestCase):
    """NOSESSION·DISABLED — 세션/스위치 상태에 따라 아무것도 쓰지 않는다."""

    def test_nosession_when_env_var_missing(self) -> None:
        del os.environ["CLAUDE_CODE_SESSION_ID"]

        output = self._init()

        self.assertEqual(output, "NOSESSION")
        self.assertFalse(self._dashboards_dir().exists())

    def test_nosession_when_env_var_not_uuid(self) -> None:
        os.environ["CLAUDE_CODE_SESSION_ID"] = "not-a-uuid"

        output = self._init()

        self.assertEqual(output, "NOSESSION")

    def test_nosession_when_env_var_is_path_traversal(self) -> None:
        """검수 1회차 F13 — 경로 탈출 방어를 cmd_init 종단까지 확인한다(파일 미기록 포함)."""
        os.environ["CLAUDE_CODE_SESSION_ID"] = "../../etc/passwd"

        output = self._init()

        self.assertEqual(output, "NOSESSION")
        self.assertFalse(self._dashboards_dir().exists())

    def test_nosession_when_env_var_has_traversal_suffix(self) -> None:
        os.environ["CLAUDE_CODE_SESSION_ID"] = self.SESSION_ID + "/../x"

        output = self._init()

        self.assertEqual(output, "NOSESSION")
        self.assertFalse(self._dashboards_dir().exists())

    def test_disabled_when_settings_say_off(self) -> None:
        self._settings_path().parent.mkdir(parents=True, exist_ok=True)
        self._settings_path().write_text(json.dumps({"dashboard_enabled": False}), encoding="utf-8")

        output = self._init()

        self.assertEqual(output, "DISABLED")
        self.assertFalse(self._dashboards_dir().exists())


class HelperNoInitAndBadArgumentTest(_HelperIOTestCase):
    """NOINIT·BADKIND·BADINDEX — init 이전 호출, 잘못된 kind/index/state."""

    def test_noinit_when_log_called_before_init(self) -> None:
        output = self._run(hub_dashboard_log.cmd_log, ["impl", "요약"])

        self.assertEqual(output, "NOINIT")

    def test_noinit_when_step_called_before_init(self) -> None:
        output = self._run(hub_dashboard_log.cmd_step, ["1", "done"])

        self.assertEqual(output, "NOINIT")

    def test_badkind_for_unknown_log_kind(self) -> None:
        self._init()

        output = self._run(hub_dashboard_log.cmd_log, ["unknown", "요약"])

        self.assertEqual(output, "BADKIND")

    def test_badindex_for_non_integer_index(self) -> None:
        self._init()

        output = self._run(hub_dashboard_log.cmd_step, ["abc", "done"])

        self.assertEqual(output, "BADINDEX")

    def test_badindex_for_invalid_state_literal(self) -> None:
        self._init()

        output = self._run(hub_dashboard_log.cmd_step, ["1", "somewhere"])

        self.assertEqual(output, "BADINDEX")

    def test_badindex_for_zero_index(self) -> None:
        self._init()

        output = self._run(hub_dashboard_log.cmd_step, ["0", "done"])

        self.assertEqual(output, "BADINDEX")


class HelperRetentionTest(_HelperIOTestCase):
    """리텐션 — init 호출 시 7일 초과 *.html·*.jsonl·*.init-values.json 만 지운다(ST5)."""

    def test_only_files_older_than_seven_days_are_removed(self) -> None:
        dashboards_dir = self._dashboards_dir()
        dashboards_dir.mkdir(parents=True)
        now = time.time()
        eight_days_ago = now - 8 * 24 * 60 * 60
        six_days_ago = now - 6 * 24 * 60 * 60

        old_files = [
            dashboards_dir / "old-session.html",
            dashboards_dir / "old-session.jsonl",
            dashboards_dir / "aaaaaaaa.init-values.json",
        ]
        recent_files = [
            dashboards_dir / "recent-session.html",
            dashboards_dir / "recent-session.jsonl",
            dashboards_dir / "bbbbbbbb.init-values.json",
        ]
        for path in old_files + recent_files:
            path.write_text("{}", encoding="utf-8")
        for path in old_files:
            os.utime(path, (eight_days_ago, eight_days_ago))
        for path in recent_files:
            os.utime(path, (six_days_ago, six_days_ago))

        self._init()

        for path in old_files:
            self.assertFalse(path.exists(), "%s 는 지워졌어야 한다" % path.name)
        for path in recent_files:
            self.assertTrue(path.exists(), "%s 는 남아 있어야 한다" % path.name)


class HelperAtomicWriteTest(_HelperIOTestCase):
    """원자적 쓰기 — 쓰기 후 임시 파일이 남지 않는다."""

    def test_no_temp_file_residue_after_init(self) -> None:
        self._init()

        leftover = list(self._dashboards_dir().glob(".dashboard-reissue-*"))

        self.assertEqual(leftover, [])


class HelperSwitchTest(_HelperIOTestCase):
    """switch — dashboard_enabled 필드만 바꾸고 다른 필드는 보존, 파싱 실패 시 무기록."""

    def test_off_sets_field_and_preserves_others(self) -> None:
        self._settings_path().parent.mkdir(parents=True, exist_ok=True)
        self._settings_path().write_text(
            json.dumps({"permissions": {"allow": ["Bash"]}, "dashboard_enabled": True}), encoding="utf-8"
        )

        output = self._run(hub_dashboard_log.cmd_switch, "off")

        self.assertEqual(output, "OFF")
        saved = json.loads(self._settings_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["dashboard_enabled"], False)
        self.assertEqual(saved["permissions"], {"allow": ["Bash"]})

    def test_on_sets_field_true(self) -> None:
        output = self._run(hub_dashboard_log.cmd_switch, "on")

        self.assertEqual(output, "ON")
        saved = json.loads(self._settings_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["dashboard_enabled"], True)

    def test_invalid_json_yields_invalid_settings_and_does_not_write(self) -> None:
        self._settings_path().parent.mkdir(parents=True, exist_ok=True)
        self._settings_path().write_text("{not json", encoding="utf-8")
        original_bytes = self._settings_path().read_bytes()

        output = self._run(hub_dashboard_log.cmd_switch, "off")

        self.assertEqual(output, "INVALID-SETTINGS")
        self.assertEqual(self._settings_path().read_bytes(), original_bytes)


class HelperEndToEndSmokeTest(_HelperIOTestCase):
    """init→log→step 을 이어 호출해 OK 사슬과 JSONL 산출물을 확인한다(HD15 — render 없음,
    HD8 — 사이드카 없음)."""

    def test_init_log_step_chain_succeeds(self) -> None:
        init_output = self._init(title="스모크 테스트", phases="구현|검수")
        self.assertEqual(init_output, "OK")

        self.assertEqual(self._run(hub_dashboard_log.cmd_log, ["impl", "1차 구현"]), "OK")
        self.assertEqual(self._run(hub_dashboard_log.cmd_step, ["1", "done"]), "OK")

        jsonl_path = self._dashboards_dir() / ("%s.jsonl" % self.SESSION_ID)
        lines = jsonl_path.read_text(encoding="utf-8").strip("\n").split("\n")
        self.assertEqual(len(lines), 3)
        self.assertIn("스모크 테스트", lines[0])

        html_path = self._dashboards_dir() / ("%s.html" % self.SESSION_ID)
        self.assertFalse(html_path.exists())
        sidecar_path = self._dashboards_dir() / ("%s.init-values.json" % self.OWNER_TOKEN)
        self.assertFalse(sidecar_path.exists())


class HelperReusesHubModulesTest(_HelperIOTestCase):
    """HD14(docs/prps/dashboard-into-hub.md) — 원자적 쓰기·오프 스위치 판정·경로 상수는
    로컬로 다시 구현하지 않고 허브 모듈을 그대로 재사용한다. 세 테스트 모두 "그 허브
    모듈을 실제로 거치는가" 를 확인한다 — 로컬 재구현으로 되돌아가면 아래 patch 가
    걸리지 않아 조용히 실패한다."""

    def test_atomic_write_delegates_to_hub_atomic_write(self) -> None:
        with mock.patch.object(
            hub_atomic_write, "atomic_write_text", wraps=hub_atomic_write.atomic_write_text
        ) as spy:
            self._init()

        # M2(HD8·HD15) — init 하나가 쓰는 파일은 jsonl 하나뿐이다(사이드카·html 쓰기는
        # 사라졌다). 옛 3회 이상 기대치를 1회 이상으로 내린다 — 0 이면 원자적 쓰기 경로
        # 자체가 로컬 재구현으로 되돌아간 것이다.
        self.assertGreaterEqual(spy.call_count, 1)

    def test_disabled_check_delegates_to_hub_collect(self) -> None:
        with mock.patch.object(hub_collect, "read_dashboard_enabled", return_value=False) as spy:
            output = self._init()

        spy.assert_called_once_with(os.getcwd())
        self.assertEqual(output, "DISABLED")

    def test_session_directory_delegates_to_hub_project_constant(self) -> None:
        alternate_directory = ".claude/elsewhere"
        with mock.patch.object(hub_project, "SESSION_DASHBOARDS_RELATIVE_DIRECTORY", alternate_directory):
            self._init()

        self.assertTrue((self._project_dir / alternate_directory).is_dir())
        self.assertFalse(self._dashboards_dir().exists())


class HelperOutputContractTest(_HelperIOTestCase):
    """M2(dashboard-into-hub.md HD8·HD15) — init 출력·산출물·폐기된 서브커맨드의 계약."""

    def test_init_output_is_exactly_ok(self) -> None:
        """HD15 — HTML 이 없으니 재발행도 없다. init 출력은 경로가 붙지 않은 `OK` 다."""
        output = self._init()

        self.assertEqual(output, "OK")

    def test_init_does_not_create_html_or_sidecar_files(self) -> None:
        """HD8 — 사이드카가 폐기되고, HD15 — HTML 재발행이 폐기됐다."""
        self._init()

        dashboards_dir = self._dashboards_dir()
        self.assertEqual(list(dashboards_dir.glob("*.html")), [])
        self.assertEqual(list(dashboards_dir.glob("*.init-values.json")), [])
        self.assertEqual(len(list(dashboards_dir.glob("*.jsonl"))), 1)

    def test_render_is_an_unknown_subcommand_now(self) -> None:
        """HD15 — render 서브커맨드가 폐기돼 main() 디스패치에서 알 수 없는 서브커맨드로
        처리된다(stderr 메시지 + exit 2)."""
        self._init()
        captured_stderr = io.StringIO()

        with contextlib.redirect_stderr(captured_stderr):
            exit_code = hub_dashboard_log.main(["render"])

        self.assertEqual(exit_code, 2)
        self.assertIn("unknown subcommand", captured_stderr.getvalue())


class HelperWorktreeOwnerRootTest(_HelperIOTestCase):
    """워크트리 cwd 에서 불러도 기록·스위치가 소유 레포 루트(.claude/worktrees/ 앞)에 쓰인다.

    워크트리 폴더의 `.claude/dashboards/` 는 gitignore 대상이라 `git worktree remove` 때 함께
    사라지고, 그러면 허브가 메인 폴더의 낡은 기록으로 되돌아가 완료한 작업이 미완료로 보였다.
    소유 루트는 `self._project_dir` 이다(임시 디렉터리 안에 `.claude/worktrees/<이름>/` 을 만든다).
    """

    def _make_worktree(self, *segments: str) -> pathlib.Path:
        worktree_dir = self._project_dir / ".claude" / "worktrees" / pathlib.Path(*segments)
        worktree_dir.mkdir(parents=True)
        return worktree_dir

    def _owner_jsonl_path(self) -> pathlib.Path:
        return self._dashboards_dir() / ("%s.jsonl" % self.SESSION_ID)

    def test_init_from_worktree_writes_to_owner_root_not_worktree(self) -> None:
        worktree_dir = self._make_worktree("feature-a")
        os.chdir(worktree_dir)

        output = self._init()

        self.assertEqual(output, "OK")
        self.assertTrue(self._owner_jsonl_path().is_file())
        self.assertFalse((worktree_dir / ".claude" / "dashboards").exists())

    def test_log_and_step_append_to_owner_root_file(self) -> None:
        os.chdir(self._make_worktree("feature-a"))
        self._init()

        log_output = self._run(hub_dashboard_log.cmd_log, ["impl", "1차 구현"])
        step_output = self._run(hub_dashboard_log.cmd_step, ["1", "done"])

        self.assertEqual((log_output, step_output), ("OK", "OK"))
        lines = self._owner_jsonl_path().read_text(encoding="utf-8").strip("\n").split("\n")
        self.assertEqual([json.loads(line)["kind"] for line in lines], ["init", "impl", "step"])

    def test_record_survives_worktree_removal(self) -> None:
        worktree_dir = self._make_worktree("feature-a")
        os.chdir(worktree_dir)
        self._init()
        self._run(hub_dashboard_log.cmd_log, ["pass", "검수 통과"])
        os.chdir(self._project_dir)

        shutil.rmtree(worktree_dir)

        lines = self._owner_jsonl_path().read_text(encoding="utf-8").strip("\n").split("\n")
        self.assertEqual(len(lines), 2)

    def test_retention_cleanup_from_worktree_runs_on_owner_root(self) -> None:
        """리텐션 정리가 워크트리 cwd 에서도 소유 루트의 8일 지난 기록을 지운다(검수 지적 — 변조 시 통과하던 구멍)."""
        self._dashboards_dir().mkdir(parents=True)
        old_path = self._dashboards_dir() / "11111111-1111-4111-8111-111111111111.jsonl"
        old_path.write_text("{}\n", encoding="utf-8")
        eight_days_ago = time.time() - 8 * 24 * 60 * 60
        os.utime(old_path, (eight_days_ago, eight_days_ago))
        os.chdir(self._make_worktree("feature-a"))

        self._init()

        self.assertFalse(old_path.exists())
        self.assertTrue(self._owner_jsonl_path().is_file())

    def test_plain_project_cwd_keeps_writing_under_cwd(self) -> None:
        output = self._init()

        self.assertEqual(output, "OK")
        self.assertTrue(self._owner_jsonl_path().is_file())

    def test_off_switch_in_owner_root_disables_init_from_worktree(self) -> None:
        self._settings_path().parent.mkdir(parents=True, exist_ok=True)
        self._settings_path().write_text(json.dumps({"dashboard_enabled": False}), encoding="utf-8")
        worktree_dir = self._make_worktree("feature-a")
        os.chdir(worktree_dir)

        output = self._init()

        self.assertEqual(output, "DISABLED")
        self.assertFalse(self._dashboards_dir().exists())
        self.assertFalse((worktree_dir / ".claude" / "dashboards").exists())

    def test_switch_from_worktree_writes_owner_settings_and_keeps_other_fields(self) -> None:
        self._settings_path().parent.mkdir(parents=True, exist_ok=True)
        self._settings_path().write_text(json.dumps({"permissions": {"allow": ["Bash"]}}), encoding="utf-8")
        worktree_dir = self._make_worktree("feature-a")
        os.chdir(worktree_dir)

        output = self._run(hub_dashboard_log.cmd_switch, "off")

        self.assertEqual(output, "OFF")
        saved = json.loads(self._settings_path().read_text(encoding="utf-8"))
        self.assertEqual(saved, {"permissions": {"allow": ["Bash"]}, "dashboard_enabled": False})
        self.assertFalse((worktree_dir / ".claude" / "settings.local.json").exists())

    def test_init_project_field_is_owner_root_name(self) -> None:
        os.chdir(self._make_worktree("feature-a"))

        self._init()

        first_event = json.loads(self._owner_jsonl_path().read_text(encoding="utf-8").split("\n")[0])
        self.assertEqual(first_event["project"], "project")

    def test_nested_worktree_and_subfolder_fold_to_outermost_root(self) -> None:
        nested_dir = self._make_worktree("outer", ".claude", "worktrees", "inner", "src", "deep")

        for candidate_cwd in (nested_dir, nested_dir.parents[0], self._project_dir / ".claude" / "worktrees" / "outer"):
            with self.subTest(cwd=str(candidate_cwd)):
                os.chdir(candidate_cwd)
                self._owner_jsonl_path().unlink(missing_ok=True)

                output = self._init()

                self.assertEqual(output, "OK")
                self.assertTrue(self._owner_jsonl_path().is_file())

    def test_non_uuid_session_in_worktree_is_nosession_and_writes_nothing(self) -> None:
        worktree_dir = self._make_worktree("feature-a")
        os.chdir(worktree_dir)
        os.environ["CLAUDE_CODE_SESSION_ID"] = "../../etc/passwd"

        output = self._init()

        self.assertEqual(output, "NOSESSION")
        self.assertFalse(self._dashboards_dir().exists())
        self.assertFalse((worktree_dir / ".claude").exists())


if __name__ == "__main__":
    unittest.main()
