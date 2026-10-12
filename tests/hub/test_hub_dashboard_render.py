"""hub/bin/hub_dashboard_render.py 의 이벤트 기반 렌더링 단위 테스트.

docs/prps/dashboard-native-data-source.md §7.1 테스트 계획 대상. 이벤트 스키마·파싱·단계
축약(DashboardEvent·parse_event_lines·derive_phase_states)은 docs/prps/
dashboard-into-hub.md M2(HD5~HD8)에서 hub_parse.py 로 옮겨갔다 — 그 두 함수를 대상으로
하던 `ParseEventLinesTest`·`DerivePhaseStatesTest` 는 tests/hub/test_hub_parse.py 로
이전됐다(검증 로직 불변). 이 파일은 남은 절반(render_detail_html·render_log_entry_lines·
build_published_values·render_from_events)을 다루는데, tests/hub/test_hub_dashboard_log.py
도 hub_dashboard_log.py 의 I/O 층 테스트에 더해 같은 순수 함수 일부를 동명 클래스로 중복
테스트한다 — 두 파일의 통합은 이번 회차 범위 밖이다. `resolve_dashboard_paths`(M1 부터
호출되지 않던 사본)를 겨냥한 `ResolveDashboardPathsTest` 는 M2 에서 그 함수 자체가
삭제되며 함께 걷혔다(§10.3).
"""

import contextlib
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_dashboard_render  # noqa: E402  (sys.path 조정 후 임포트)
import hub_parse  # noqa: E402  (읽기 전용 — 계약 검증에만 쓴다. 수정하지 않는다)

_DASHBOARD_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "hub", "bin", "hub_dashboard_template.html"
)

# 2026-09-21 04:00:00 UTC 부터 1분 간격 — 시각 포맷(hub_dashboard_render._format_event_clock 등)은
# 이제 로컬 시간대를 쓴다(검수 H4). 로컬 시간 문자열을 직접 단언하는 테스트는 아래
# _forced_timezone 으로 TZ 를 고정해 실행 기계와 무관하게 결정적으로 만든다.
_BASE_TIME_MS = 1789963200000
_MINUTE_MS = 60_000


def _time_at(minute_offset: int) -> int:
    return _BASE_TIME_MS + minute_offset * _MINUTE_MS


def _jsonl(*event_dicts: dict) -> str:
    """이벤트 dict 목록 → JSONL 본문(줄마다 하나, ensure_ascii=False)."""
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in event_dicts)


def _init_dict(minute_offset: int, title: str, phases: list, project: str = "coding-harness") -> dict:
    return {"time_ms": _time_at(minute_offset), "kind": "init", "title": title, "phases": phases, "project": project}


def _log_dict(minute_offset: int, kind: str, summary: str, detail: str = "") -> dict:
    return {"time_ms": _time_at(minute_offset), "kind": kind, "summary": summary, "detail": detail}


def _step_dict(minute_offset: int, index: int, state: str) -> dict:
    return {"time_ms": _time_at(minute_offset), "kind": "step", "index": index, "state": state}


def _read_real_template() -> str:
    with open(_DASHBOARD_TEMPLATE_PATH, encoding="utf-8") as handle:
        return handle.read()


def _entry_block(lines: list, seq: int) -> list:
    """render_log_entry_lines 결과에서 data-seq=={seq} 인 <li> 하나를 통째로 잘라낸다."""
    start = next(i for i, line in enumerate(lines) if 'data-seq="%d"' % seq in line)
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "</li>")
    return lines[start : end + 1]


@contextlib.contextmanager
def _forced_timezone(tz_name: str):
    """블록 동안만 프로세스 TZ 를 고정한다(H4 회귀 검증 전용) — 호스트 시간대와 무관하게
    로컬 시간 포맷 단언을 결정적으로 만든다. time.tzset() 은 POSIX 전용(이 저장소는 macOS·
    Linux 만 지원 — tests/hub, tests/commands 어디에도 Windows 전용 코드가 없다)."""
    original_tz = os.environ.get("TZ")
    os.environ["TZ"] = tz_name
    time.tzset()
    try:
        yield
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


class RenderDetailHtmlTest(unittest.TestCase):
    """render_detail_html — hub/README.md 「진행 기록」의 「상세 마크업」 4단계 규칙."""

    def test_empty_input_returns_no_detail_placeholder(self) -> None:
        self.assertEqual(hub_dashboard_render.render_detail_html(""), "(상세 없음)")

    def test_worked_example_matches_dashboard_md_character_for_character(self) -> None:
        """hub/README.md 「헬퍼 스크립트」 절의 워크드 예시와 문자 단위로 동일해야 한다."""
        detail = "재현 조건 두 가지를 확인했다.\n\n- 32px → 12px 전환에서만 발생\n- `buildChipBadge` 는 통과"

        rendered = hub_dashboard_render.render_detail_html(detail)

        self.assertEqual(
            rendered,
            "<p>재현 조건 두 가지를 확인했다.</p>"
            "<ul><li>32px → 12px 전환에서만 발생</li>"
            "<li><code>buildChipBadge</code> 는 통과</li></ul>",
        )

    def test_backward_compat_single_paragraph_is_not_wrapped(self) -> None:
        """단일 블록·목록 없음·백틱 없음 — hub/README.md 의 후방 호환 예시와 동일하다."""
        detail = "검수자 32px→12px 재현. buildChipBadge·runBottom 은 통과. margin 누적으로 전환 지시."

        rendered = hub_dashboard_render.render_detail_html(detail)

        self.assertEqual(rendered, detail)

    def test_single_list_block_is_still_wrapped_in_ul(self) -> None:
        """블록이 하나뿐이어도 그 블록이 목록이면 감싸지 않는 예외가 적용되지 않는다."""
        rendered = hub_dashboard_render.render_detail_html("- a\n- b")

        self.assertEqual(rendered, "<ul><li>a</li><li>b</li></ul>")

    def test_backtick_pairing_does_not_cross_block_boundary(self) -> None:
        """백틱 짝짓기가 블록 경계를 넘지 않음 — 블록마다 홀수 백틱이라 둘 다 글자 그대로 남는다."""
        rendered = hub_dashboard_render.render_detail_html("a `b\n\nc` d")

        self.assertEqual(rendered, "<p>a `b</p><p>c` d</p>")

    def test_escaping_is_applied_before_backtick_markup(self) -> None:
        rendered = hub_dashboard_render.render_detail_html("a<b> & `x<y>`")

        self.assertEqual(rendered, "a&lt;b&gt; &amp; <code>x&lt;y&gt;</code>")

    def test_odd_trailing_backtick_stays_literal(self) -> None:
        rendered = hub_dashboard_render.render_detail_html("`code` 뒤에 짝 없는 ` 하나")

        self.assertEqual(rendered, "<code>code</code> 뒤에 짝 없는 ` 하나")

    def test_multiline_paragraph_preserves_single_newline(self) -> None:
        """블록 안 단일 개행은 보존한다(불변식 10 근거)."""
        rendered = hub_dashboard_render.render_detail_html("첫 줄\n둘째 줄")

        self.assertEqual(rendered, "첫 줄\n둘째 줄")

    def test_result_has_no_newline_between_tags(self) -> None:
        """구 불변식 10 — 태그 사이에는 개행이 없다(멀티 블록으로 실제 태그를 만들어 확인)."""
        rendered = hub_dashboard_render.render_detail_html("문단.\n\n- 목록1\n- 목록2")

        self.assertNotIn(">\n<", rendered)


class RenderLogEntryLinesTest(unittest.TestCase):
    """render_log_entry_lines — 최신이 위, data-seq 1부터, 최신 3건만 펼침, 회차 자동."""

    def test_empty_events_returns_empty_list(self) -> None:
        self.assertEqual(hub_dashboard_render.render_log_entry_lines(()), [])

    def test_newest_first_with_incrementing_seq(self) -> None:
        events = (
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="impl", summary="첫 번째"),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="두 번째"),
        )

        lines = hub_dashboard_render.render_log_entry_lines(events)

        first_entry = _entry_block(lines, seq=2)
        second_entry = _entry_block(lines, seq=1)
        self.assertLess(lines.index(first_entry[0]), lines.index(second_entry[0]))
        self.assertTrue(any("두 번째" in line for line in first_entry))
        self.assertTrue(any("첫 번째" in line for line in second_entry))

    def test_only_most_recent_three_are_open(self) -> None:
        events = tuple(
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(i), kind="impl", summary="작업%d" % i)
            for i in range(4)
        )

        lines = hub_dashboard_render.render_log_entry_lines(events)

        for seq, expect_open in ((4, True), (3, True), (2, True), (1, False)):
            entry = _entry_block(lines, seq)
            self.assertEqual(entry[1] == "        <details open>", expect_open, msg="seq=%d" % seq)

    def test_round_number_tracks_cumulative_pass_and_fail_only(self) -> None:
        events = (
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="design", summary="설계"),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="구현"),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(2), kind="fail", summary="검수 실패"),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(3), kind="impl", summary="재구현"),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(4), kind="pass", summary="검수 통과"),
        )

        lines = hub_dashboard_render.render_log_entry_lines(events)

        self.assertTrue(any("badge round\">R1<" in line for line in _entry_block(lines, seq=3)))
        self.assertTrue(any("badge round\">R2<" in line for line in _entry_block(lines, seq=5)))
        for seq in (1, 2, 4):
            self.assertFalse(any("badge round" in line for line in _entry_block(lines, seq)))

    def test_kind_maps_to_data_kind_and_badge(self) -> None:
        events = (hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="commit", summary="배포 완료"),)

        entry = _entry_block(hub_dashboard_render.render_log_entry_lines(events), seq=1)

        self.assertEqual(entry[0], '      <li class="entry" data-kind="commit" data-seq="1">')
        self.assertTrue(any('<span class="badge commit">커밋</span>' in line for line in entry))

    def test_summary_is_escaped(self) -> None:
        events = (hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="note", summary="a < b & c"),)

        entry = _entry_block(hub_dashboard_render.render_log_entry_lines(events), seq=1)

        self.assertTrue(any('<span class="lead">a &lt; b &amp; c</span>' in line for line in entry))

    def test_detail_is_rendered_through_render_detail_html(self) -> None:
        events = (
            hub_dashboard_render.DashboardEvent(
                time_ms=_time_at(0), kind="impl", summary="요약", detail="- 항목1\n- 항목2"
            ),
        )

        entry = _entry_block(hub_dashboard_render.render_log_entry_lines(events), seq=1)

        self.assertTrue(
            any('<div class="detail"><ul><li>항목1</li><li>항목2</li></ul></div>' in line for line in entry)
        )

    def test_each_entry_is_one_li_per_line_boundary(self) -> None:
        """불변식 — 로그 <li> 는 한 줄에 하나. 다음 항목의 여는 태그가 이전 항목 안에 섞이지 않는다."""
        events = tuple(
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(i), kind="impl", summary="작업%d" % i)
            for i in range(2)
        )

        lines = hub_dashboard_render.render_log_entry_lines(events)

        opening_tag_lines = [line for line in lines if line.startswith('      <li class="entry"')]
        self.assertEqual(len(opening_tag_lines), 2)
        for line in lines:
            self.assertLessEqual(line.count("<li "), 1)

    def test_summary_with_newline_is_folded_to_single_line(self) -> None:
        """H1 회귀 — summary 의 개행이 공백으로 접혀 <span class="lead"> 가 한 줄로 남는다."""
        events = (hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="impl", summary="줄1\n줄2"),)

        entry = _entry_block(hub_dashboard_render.render_log_entry_lines(events), seq=1)

        self.assertTrue(any('<span class="lead">줄1 줄2</span>' in line for line in entry))
        for line in entry:
            self.assertNotIn("\n", line)

    def test_time_label_uses_local_timezone_not_hardcoded_utc(self) -> None:
        """H4 회귀 — 로그 항목 시각이 UTC 로 고정돼 있지 않고 로컬 시간대를 반영한다."""
        events = (hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="impl", summary="작업"),)

        with _forced_timezone("Asia/Seoul"):
            entry = _entry_block(hub_dashboard_render.render_log_entry_lines(events), seq=1)

        # _time_at(0) = 2026-09-21 04:00:00 UTC → Asia/Seoul(UTC+9, DST 없음) 로는 13:00
        self.assertTrue(any('<span class="time">13:00</span>' in line for line in entry))


class BuildPublishedValuesTest(unittest.TestCase):
    """build_published_values — 계약 위반(첫 이벤트가 init 이 아님)은 ValueError."""

    def test_empty_events_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            hub_dashboard_render.build_published_values((), "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

    def test_first_event_not_init_raises_value_error(self) -> None:
        events = (hub_dashboard_render.DashboardEvent(time_ms=_time_at(0), kind="impl", summary="요약"),)

        with self.assertRaises(ValueError):
            hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

    def test_owner_token_is_first_eight_chars_of_session_id(self) -> None:
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["구현", "검수"])))

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        self.assertEqual(values.log_owner_token, "d4973ae5")
        self.assertEqual(values.log_server_port, "")
        self.assertIsNone(values.impl_count_html)
        self.assertIsNone(values.impl_block_lines)

    def test_step_line_attribute_order_and_one_per_line(self) -> None:
        """불변식 — id="dz-step-{n}" class="{state}" 순서 고정, 줄마다 하나."""
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["설계", "승인", "구현", "검수"]), _log_dict(1, "impl", "구현 요약"))
        )

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        step_lines = [line for line in values.progress_block_lines if "dz-step-" in line]
        self.assertEqual(len(step_lines), 4)
        for line in step_lines:
            self.assertRegex(line, r'^\s*<li id="dz-step-\d+" class="(done|active|wait)">')
            self.assertEqual(line.count("<li "), 1)

    def test_title_with_newline_is_folded_to_single_line(self) -> None:
        """H1 회귀 — title 의 개행이 공백으로 접혀 <h1> 이 한 줄로 남는다."""
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목 줄1\n제목 줄2", ["구현", "검수"])))

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        self.assertEqual(values.title_html, "제목 줄1 제목 줄2")

    def test_project_with_newline_is_folded_to_single_line(self) -> None:
        """H1 회귀 — project 의 개행도 같은 이유로 접힌다."""
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["구현", "검수"], project="proj\nname"))
        )

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        self.assertEqual(values.project_name_html, "proj name")

    def test_phase_name_with_newline_is_folded_in_step_line(self) -> None:
        """H1 회귀 — phases 항목의 개행이 <li> 를 여러 줄로 쪼개지 않는다."""
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["설계\n승인", "구현"])))

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        step_lines = [line for line in values.progress_block_lines if "dz-step-1" in line]
        self.assertEqual(len(step_lines), 1)
        self.assertNotIn("\n", step_lines[0])
        self.assertIn("설계 승인", step_lines[0])

    def test_percent_rounds_two_of_three_to_67_not_66(self) -> None:
        """H3 회귀 — 비표준 3단계에서 버림(66%)이 아니라 반올림(67%)이어야 한다."""
        events = (
            hub_dashboard_render.DashboardEvent(
                time_ms=_time_at(0), kind="init", title="제목", phases=("가", "나", "다"), project="proj"
            ),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(1), kind="step", index=1, state="done"),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(2), kind="step", index=2, state="done"),
        )

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        self.assertEqual(values.progress_text_html, "2/3 · 67%")
        self.assertEqual(values.progress_width, "67%")

    def test_percent_rounds_one_of_six_to_17_not_16(self) -> None:
        """H3 회귀 — 비표준 6단계에서 버림(16%)이 아니라 반올림(17%)이어야 한다."""
        events = (
            hub_dashboard_render.DashboardEvent(
                time_ms=_time_at(0), kind="init", title="제목",
                phases=("a", "b", "c", "d", "e", "f"), project="proj",
            ),
            hub_dashboard_render.DashboardEvent(time_ms=_time_at(1), kind="step", index=1, state="done"),
        )

        values = hub_dashboard_render.build_published_values(events, "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2")

        self.assertEqual(values.progress_text_html, "1/6 · 17%")


class RenderFromEventsSnapshotConsistencyTest(unittest.TestCase):
    """render_from_events(화면) ↔ hub_parse.snapshot_from_events(카드 요약)의 일관성.

    M2(dashboard-into-hub.md HD6)에서 hub_parse.parse_dashboard_html 이 사라져 이전처럼
    "렌더 → 재파싱" 으로 계약을 고정할 수 없다. 대신 같은 이벤트를 두 소비자(화면
    렌더러·카드 스냅샷 합성기)에 각각 흘려 제목·진행률·단계 상태·활성 상세가 같은 값으로
    나오는지 직접 대조한다 — 두 소비자가 서로 다른 이야기를 하면 카드와 화면이 어긋난다.
    """

    _SESSION_ID = "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2"

    @classmethod
    def setUpClass(cls) -> None:
        cls.template_text = _read_real_template()

    def _render(self, events: tuple) -> str:
        return hub_dashboard_render.render_from_events(self.template_text, events, self._SESSION_ID)

    def test_full_path_title_and_progress_match_snapshot(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "네이티브 대시보드 설계", ["설계", "승인", "구현", "검수"]),
                _log_dict(1, "design", "PRP 작성 완료"),
                _log_dict(2, "approve", "사용자 승인"),
                _log_dict(3, "impl", "1단계 A 구현 완료"),
                _log_dict(4, "pass", "검수 통과"),
            )
        )
        snapshot = hub_parse.snapshot_from_events(events)

        rendered = self._render(events)

        self.assertIn('<h1 id="dz-title">%s</h1>' % snapshot.title, rendered)
        self.assertIn(
            '<div class="pct" id="dz-progress-pct">%d/%d · %d%%</div>'
            % (snapshot.completed, snapshot.total, snapshot.percent),
            rendered,
        )
        for step in snapshot.steps:
            self.assertIn('<li id="dz-step-%d" class="%s">' % (step.index, step.state), rendered)

    def test_fail_recovery_step_states_and_active_detail_match_snapshot(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "네이티브 대시보드 설계", ["설계", "승인", "구현", "검수"]),
                _log_dict(1, "design", "PRP 작성 완료"),
                _log_dict(2, "approve", "사용자 승인"),
                _log_dict(3, "impl", "1단계 A 구현 완료"),
                _log_dict(4, "fail", "검수 실패", "margin 누적으로 전환 지시"),
            )
        )
        snapshot = hub_parse.snapshot_from_events(events)

        rendered = self._render(events)

        active_step = next(step for step in snapshot.steps if step.state == "active")
        self.assertEqual(active_step.name, "구현")
        self.assertIn('<li id="dz-step-%d" class="active">' % active_step.index, rendered)
        self.assertIn('<span class="step-detail">%s</span>' % active_step.detail, rendered)

    def test_shortened_path_step_states_match_snapshot(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "버그 수정", ["구현", "검수"]), _log_dict(1, "impl", "수정 완료"))
        )
        snapshot = hub_parse.snapshot_from_events(events)

        rendered = self._render(events)

        for step in snapshot.steps:
            self.assertIn('<li id="dz-step-%d" class="%s">' % (step.index, step.state), rendered)

    def test_updated_label_matches_hub_parse_format(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["구현", "검수"]), _log_dict(3, "impl", "작업 완료"))
        )

        # _time_at(3) = _BASE_TIME_MS + 3분 = 2026-09-21 04:03:00 UTC → Asia/Seoul(UTC+9,
        # DST 없음)로는 13:03(FormatEventUpdatedLabelTest 와 같은 값 체계, tests/hub/
        # test_hub_parse.py). hub_parse.format_event_updated_label 을 다시 불러 기대값을
        # 만들면 그 함수가 UTC 로 고정된 회귀에서도 함께 무너져 순환 검증이 된다(검수 3회차
        # 참고 항목) — 하드코딩 리터럴로 그 순환을 끊는다.
        with _forced_timezone("Asia/Seoul"):
            rendered = self._render(events)

        self.assertIn('<div class="foot" id="dz-updated">갱신: 2026-09-21 13:03</div>', rendered)

    def test_summary_with_embedded_newline_step_detail_matches_snapshot(self) -> None:
        """H1 회귀 — summary 개행은 스냅샷(카드 요약)에는 원문 그대로 남고, 화면에는
        <li> 한 줄 계약을 지키려고 공백으로 접혀 렌더된다(단일 행 필드 정규화, hub_dashboard_
        render._escape_single_line)."""
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "제목", ["설계", "승인", "구현", "검수"]),
                _log_dict(1, "design", "PRP 작성 완료"),
                _log_dict(2, "approve", "사용자 승인"),
                _log_dict(3, "impl", "재현 조건 확인.\n두 번째 줄도 있음."),
            )
        )
        snapshot = hub_parse.snapshot_from_events(events)

        rendered = self._render(events)

        active_step = next(step for step in snapshot.steps if step.state == "active")
        self.assertEqual(active_step.detail, "재현 조건 확인.\n두 번째 줄도 있음.")
        self.assertIn('<span class="step-detail">재현 조건 확인. 두 번째 줄도 있음.</span>', rendered)


if __name__ == "__main__":
    unittest.main()
