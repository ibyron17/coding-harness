"""tests/hub/test_hub_template_dom_resume.py — 헤드리스 Chrome DOM 행동 검사 중 다시 불러낸(재개한) 서브에이전트의 실행 줄
(D25~D28, docs/prps/hub-agent-title-and-excerpt-freshness.md §9.3, 결정 TF11·TF12).

서버가 실행 뷰에 싣는 새 필드 둘(resume_title·resume_count)을 화면이 제대로 그리는지 본다. 제목은 재개 요청의 요약이 먼저이고(없으면
호스트가 남긴 설명, 그마저 없으면 타입명), 툴팁은 재개된 실행이면 시작 라벨이 「재개」로 바뀌고 끝에 「재개 N회」가 붙는다. 재개된 적 없는
실행은 오늘과 한 글자도 같아야 하고, 두 필드를 싣기 전 서버의 페이로드(키 없음)도 오늘 화면 그대로다(§6.5). 카드 목록과 카드 상세보기는
같은 실행 줄 렌더를 쓰므로 두 화면을 다 본다. 공용 하네스(Chrome 탐색·서버·사전 스크립트·프로브·픽스처 빌더)는
template_dom_harness.py 를 볼 것 — 하네스는 무변경이다.

시나리오가 굽는 값은 전부 합성이다(실제 대화·요약이 아니다).

Chrome 이 없으면 SKIP(사유 출력). 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 — 변경 전 템플릿으로 돌려 이 모듈의
시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import functools
import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_session  # noqa: E402  (sys.path 조정 후 임포트 — SubagentRunView 픽스처용)

try:
    from .template_dom_harness import (
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document as _minimal_data_document,
        run_scenario,
        safe_js_string_literal as _safe_js_string_literal,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document as _minimal_data_document,
        run_scenario,
        safe_js_string_literal as _safe_js_string_literal,
    )

_MS_PER_MINUTE = 60000
_ENDED_RUN_DURATION_MINUTES = 3    # 끝난 실행의 길이 — 경과 라벨을 고정한다
_SETTLE_MS = 30                    # 클릭 뒤 동기 렌더가 끝나길 기다리는 짧은 여유(폴링·틱의 TRIGGER_SETTLE_MS 와는 별개)
_SURFACES = (("list", "카드 목록"), ("modal", "카드 상세보기"))
_NARROW_CARD_WIDTH_PX = 320        # 카드 트랙의 최소 폭 — 헤드리스 Chrome 창은 500px 밑으로 줄지 않아 카드를 이 폭으로 직접 묶는다
_GEOMETRY_TOLERANCE_PX = 0.5


def _run(
    agent_id: str, agent_type: str, phase: hub_session.Phase | None, minutes_ago: int, title: str | None, *,
    is_running: bool = False, model: str | None = "sonnet", resume_title: str | None = None, resume_count: int = 0,
) -> hub_session.SubagentRunView:
    """서브에이전트 실행 1건. 끝난 실행은 시작 _ENDED_RUN_DURATION_MINUTES 분 뒤에 끝난 것으로 둔다."""
    started_at_ms = BASE_TIME_MS - minutes_ago * _MS_PER_MINUTE
    ended_at_ms = None if is_running else started_at_ms + _ENDED_RUN_DURATION_MINUTES * _MS_PER_MINUTE
    return hub_session.SubagentRunView(
        agent_id=agent_id, agent_type=agent_type, phase=phase, is_running=is_running,
        started_at_ms=started_at_ms, ended_at_ms=ended_at_ms, title=title, model=model,
        resume_title=resume_title, resume_count=resume_count,
    )


def _clock_label(at_ms: int) -> str:
    """툴팁 시각 라벨(오늘이면 HH:MM, 다른 날이면 M/D HH:MM)의 독립 계산 — 템플릿 함수를 베끼지 않고 파이썬 현지 시각으로 구한다."""
    target, now = time.localtime(at_ms / 1000), time.localtime(BASE_TIME_MS / 1000)
    clock = time.strftime("%H:%M", target)
    return clock if target[:3] == now[:3] else f"{target.tm_mon}/{target.tm_mday} {clock}"


def _session_with_runs(session_id: str, runs: tuple[hub_session.SubagentRunView, ...]) -> hub_session.SessionView:
    working_session = _session(session_id, "working", "working", BASE_TIME_MS - 1 * _MS_PER_MINUTE, task_excerpt="재개 실행 줄 확인용 작업")
    return dataclasses.replace(working_session, agent_runs=runs)


# ── 픽스처 — 주 시나리오(D25~D27). 다섯 갈래를 한 세션에 싣는다 ──
# 실행 중 재개 · 끝난 재개 · 요약 없는 재개(resume_title 없음) · 재개된 적 없음 · 설명도 모델도 없는 실행.
# 서버의 정렬(실행 중 먼저, 그다음 최근 시작 순)대로 늘어놓는다 — 템플릿은 순서를 바꾸지 않는다.
_PATH = "/repo/resume"
_SESSION_ID = "resume-1"
_RUNNING_RESUMED = _run("r-running", "code-reviewer", "검수", 5, "M1 칩 제거 검수", is_running=True, resume_title="M3 변경 검수", resume_count=2)
_ENDED_RESUMED = _run("r-ended", "implementer", "구현", 50, "M1 칩 제거 구현", resume_title="M3 이어서 구현", resume_count=2)
_SUMMARYLESS_RESUMED = _run("r-summaryless", "code-reviewer", "검수", 70, "보안 검수", resume_count=1)
_NEVER_RESUMED = _run("r-plain", "design-architect", "설계", 90, "설계 문서 작성", model="opus")
_UNTITLED = _run("r-untitled", "custom-checker", None, 110, None, model=None)
_MAIN_RUNS = (_RUNNING_RESUMED, _ENDED_RESUMED, _SUMMARYLESS_RESUMED, _NEVER_RESUMED, _UNTITLED)
_MAIN_SNAPSHOT = _snapshot((_project(_PATH, "resume", "working", (_session_with_runs(_SESSION_ID, _MAIN_RUNS),)),))

# 기대 제목 — 재개 요약 → 호스트 설명 → 타입명. 위 실행 값에서 읽지 않고 리터럴로 적는다(순환 검증 방지).
_EXPECTED_TITLES = {
    "r-running": "M3 변경 검수",
    "r-ended": "M3 이어서 구현",
    "r-summaryless": "보안 검수",
    "r-plain": "설계 문서 작성",
    "r-untitled": "custom-checker",
}
# 두 필드를 싣기 전 서버에서는 재개 여부와 무관하게 오늘의 사슬(설명 → 타입명)이다.
_TODAYS_TITLES = {**_EXPECTED_TITLES, "r-running": "M1 칩 제거 검수", "r-ended": "M1 칩 제거 구현"}
_NEVER_RESUMED_KEYS = ("r-plain", "r-untitled")

# 기대 경과 칸 — 재개 횟수를 줄 끝에 늘 보이게 하는 안(Q1 안 B)은 기각됐다: 경과 칸은 오늘처럼 경과 시간뿐이다.
# 끝난 실행은 _ENDED_RUN_DURATION_MINUTES 분, 실행 중인 r-running 은 시작 5분 뒤인 지금(BASE_TIME_MS)까지 5분이다.
_EXPECTED_ELAPSED = {"r-running": "5분", "r-ended": "3분", "r-summaryless": "3분", "r-plain": "3분", "r-untitled": "3분"}

# 기대 툴팁 — 재개된 실행은 시작 라벨이 「재개」, 끝에 「 · 재개 N회」. 재개된 적 없는 실행은 오늘과 같다.
_EXPECTED_TOOLTIPS = {
    "r-running": f"code-reviewer · 검수 단계 · sonnet · 재개 {_clock_label(_RUNNING_RESUMED.started_at_ms)} · 진행 중 · 재개 2회",
    "r-ended": f"implementer · 구현 단계 · sonnet · 재개 {_clock_label(_ENDED_RESUMED.started_at_ms)} · 종료 · 재개 2회",
    "r-summaryless": f"code-reviewer · 검수 단계 · sonnet · 재개 {_clock_label(_SUMMARYLESS_RESUMED.started_at_ms)} · 종료 · 재개 1회",
    "r-plain": f"design-architect · 설계 단계 · opus · 시작 {_clock_label(_NEVER_RESUMED.started_at_ms)} · 종료",
    "r-untitled": f"custom-checker · 워크플로우 단계 매핑 없음 · 모델 미기록 · 시작 {_clock_label(_UNTITLED.started_at_ms)} · 종료",
}
_TODAYS_TOOLTIPS = {
    **_EXPECTED_TOOLTIPS,
    "r-running": f"code-reviewer · 검수 단계 · sonnet · 시작 {_clock_label(_RUNNING_RESUMED.started_at_ms)} · 진행 중",
    "r-ended": f"implementer · 구현 단계 · sonnet · 시작 {_clock_label(_ENDED_RESUMED.started_at_ms)} · 종료",
    "r-summaryless": f"code-reviewer · 검수 단계 · sonnet · 시작 {_clock_label(_SUMMARYLESS_RESUMED.started_at_ms)} · 종료",
}

# ── 픽스처 — D28(제목에 마크업이 든 재개 요약) ──
_HOSTILE_TITLE = '<img src=x onerror="window.__dzhResumeXss=1">&amp;'
_HOSTILE_SNAPSHOT = _snapshot((_project(_PATH, "resume", "working", (_session_with_runs(_SESSION_ID, (
    _run("x1", "code-reviewer", "검수", 5, "평범한 설명", is_running=True, resume_title=_HOSTILE_TITLE, resume_count=1),
)),)),))

# ── 픽스처 — 가장 좁은 카드(320px)에서의 줄 모양. 긴 재개 요약은 끊을 곳 없는 토큰까지 달고, 짧은 재개 요약은 그대로 보인다 ──
_LONG_RESUME_TITLE = (
    "M3 변경 검수 — 설계 문서 대비 누락 항목과 회귀 위험을 전수 대조한다 "
    "verify_hub_template_session_modal_layout_regressions_across_viewports"
)
_SHORT_RESUME_TITLE = "M3 이어서 구현"
_NARROW_SNAPSHOT = _snapshot((_project(_PATH, "resume", "working", (_session_with_runs(_SESSION_ID, (
    _run("n-long", "code-reviewer", "검수", 5, "설명", is_running=True, resume_title=_LONG_RESUME_TITLE, resume_count=2),
    _run("n-short", "implementer", "구현", 50, "설명", resume_title=_SHORT_RESUME_TITLE, resume_count=2),
)),)),))

# ── 픽스처 — 폴링으로 같은 에이전트가 또 재개된다(M2 구간이 끝난 줄 → M3 구간이 도는 줄). 사용자가 본 바로 그 장면이다 ──
_POLL_KEY = "p1"
_POLL_BEFORE = _run(_POLL_KEY, "code-reviewer", "검수", 60, "M1 칩 제거 검수", resume_title="M2 변경 검수", resume_count=1)
_POLL_AFTER = _run(_POLL_KEY, "code-reviewer", "검수", 2, "M1 칩 제거 검수", is_running=True, resume_title="M3 변경 검수", resume_count=2)
_POLL_SNAPSHOT_BEFORE = _snapshot((_project(_PATH, "resume", "working", (_session_with_runs(_SESSION_ID, (_POLL_BEFORE,)),)),))
_POLL_SNAPSHOT_AFTER = _snapshot((_project(_PATH, "resume", "working", (_session_with_runs(_SESSION_ID, (_POLL_AFTER,)),)),))

# 실행 줄마다 키·제목·툴팁·마크업 전체를 읽는다. 채우는 자리 없음(% 서식 밖 조각).
_ROW_REPORT_FUNCTION = """
function rowReports(scope){
  return Array.prototype.map.call(scope.querySelectorAll('.agent-run'), function(row){
    return {
      key: row.getAttribute('data-render-key'),
      title: row.querySelector('.agent-run-title').textContent,
      meta: row.querySelector('.agent-run-meta').textContent,
      tooltip: row.getAttribute('data-tooltip'),
      html: row.outerHTML,
    };
  });
}
"""
# 카드 목록의 줄을 읽고, 카드 경로를 눌러 카드 상세보기를 연 뒤 그 안의 줄을 읽는다. 채우는 자리: settle(ms)·path.
_LIST_AND_MODAL_PROBE = _ROW_REPORT_FUNCTION + """
var listRows = rowReports(document.getElementById('dzh-app'));
__dispatchClick(document.querySelector('#dzh-app [data-project-path="%(path)s"] .path'));
await __sleep(%(settle)d);
__probeResult({list: listRows, modal: rowReports(document.getElementById('dzh-session-modal-body'))});
"""
# D28 프로브 — 마크업 문자열이 글자로만 나오고 요소·스크립트 실행으로 새지 않는다. 채우는 자리: settle(ms)·path.
_MARKUP_PROBE = """
function titleReport(scope){
  var title = scope.querySelector('.agent-run[data-render-key="x1"] .agent-run-title');
  return {text: title.textContent, childElements: title.childElementCount, imageCount: scope.querySelectorAll('img').length};
}
var list = titleReport(document.getElementById('dzh-app'));
__dispatchClick(document.querySelector('#dzh-app [data-project-path="%(path)s"] .path'));
await __sleep(%(settle)d);
__probeResult({list: list, modal: titleReport(document.getElementById('dzh-session-modal-body')), scriptRan: typeof window.__dzhResumeXss});
"""
# 가장 좁은 카드 프로브 — #dzh-app 을 카드 트랙 최소 폭으로 묶고 줄마다 넘침·말줄임·경과 칸 위치를 잰다. 채우는 자리: width(px).
_NARROW_ROW_PROBE = """
var app = document.getElementById('dzh-app');
app.style.width = '%(width)dpx';
var card = app.querySelector('.card');
__probeResult({
  cardWidth: card.getBoundingClientRect().width,
  rows: Array.prototype.map.call(card.querySelectorAll('.agent-run'), function(row){
    var rowBox = row.getBoundingClientRect();
    var title = row.querySelector('.agent-run-title');
    var titleBox = title.getBoundingClientRect();
    var metaBox = row.querySelector('.agent-run-meta').getBoundingClientRect();
    return {
      key: row.getAttribute('data-render-key'),
      rowOverflowX: row.scrollWidth - row.clientWidth,
      titleClipped: title.scrollWidth > title.clientWidth,
      titleWhiteSpace: getComputedStyle(title).whiteSpace,
      metaInsideRow: metaBox.right <= rowBox.right + 0.5,
      metaAfterTitle: metaBox.left >= titleBox.right - 0.5,
    };
  }),
});
"""
# 폴링 프로브 — 같은 줄이 제자리에서 바뀐다. 폴링 응답은 프로브 안에서 장전한다(페이지 로드가 조용히 먼저 폴링하면 목표가 이미 채워진다 — D1 주석).
# 채우는 자리: key·poll_document(JS 문자열 리터럴).
_POLL_PROBE = """
function rowState(row){
  return {
    title: row.querySelector('.agent-run-title').textContent,
    tooltip: row.getAttribute('data-tooltip'),
    running: row.querySelector('.agent-chip').classList.contains('agent-chip-running'),
  };
}
var rowBefore = document.querySelector('.agent-run[data-render-key="%(key)s"]');
var before = rowState(rowBefore);
window.__mockFetchResponseText = %(poll_document)s;
await __triggerPoll();
var rowAfter = document.querySelector('.agent-run[data-render-key="%(key)s"]');
__probeResult({before: before, after: rowState(rowAfter), sameNode: rowAfter === rowBefore && rowBefore.isConnected});
"""

# 두 필드를 싣기 전 서버의 페이로드: 구운 페이지의 JSON 에서 모든 실행의 두 키를 걷어 낸다(asdict 는 두 필드를 맨 뒤에 싣는다).
_RESUME_FIELDS_JSON_PATTERN = re.compile(r', "resume_title": (?:null|"(?:[^"\\]|\\.)*"), "resume_count": \d+')


def _page_from_server_without_resume_fields(snapshot, probe_body: str) -> str:
    """신버전 템플릿 + 구버전 서버(PRP §6.5) — 키가 실제로 모든 실행에서 걷혔는지 확인하고, 아니면 검사 전제가 깨진 것이다."""
    page = _make_page(snapshot, probe_body)
    stripped_page, removed_count = _RESUME_FIELDS_JSON_PATTERN.subn("", page)
    run_count = sum(len(session.agent_runs) for project in snapshot.projects for session in project.sessions)
    if removed_count != run_count:
        raise AssertionError(f"구버전 서버 페이로드 재현 실패: 두 키를 걷어 낸 실행이 {removed_count}개, 실행은 {run_count}개")
    return stripped_page


def _rows_by_key(rows: list[dict]) -> dict[str, dict]:
    return {row["key"]: row for row in rows}


@functools.cache
def _main_report() -> dict:
    """주 시나리오를 한 번만 돌린다 — D25·D26·D27 이 같은 결과를 읽기 전용으로 나눠 본다(Chrome 기동이 시나리오당 1~2초)."""
    probe_body = _LIST_AND_MODAL_PROBE % {"settle": _SETTLE_MS, "path": _PATH}
    return run_scenario(_make_page(_MAIN_SNAPSHOT, probe_body))


@functools.cache
def _server_without_resume_fields_report() -> dict:
    probe_body = _LIST_AND_MODAL_PROBE % {"settle": _SETTLE_MS, "path": _PATH}
    return run_scenario(_page_from_server_without_resume_fields(_MAIN_SNAPSHOT, probe_body))


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubResumedAgentRunDomTest(unittest.TestCase):
    """D25~D28(§9.3) — 재개된 서브에이전트의 실행 줄 제목·툴팁이 카드 목록과 카드 상세보기 양쪽에서 맞는지."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def test_d25_resumed_run_shows_the_resume_title_in_the_card_list_and_the_card_modal(self) -> None:
        # 결정 TF12 — 재개된 실행의 제목은 첫 띄움 설명(M1 …)이 아니라 마지막 재개 요청의 요약이다. 카드 목록과 카드 상세보기가 같은 줄 렌더를 쓴다.
        report = _main_report()
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                rows = _rows_by_key(report[surface])
                self.assertEqual(sorted(rows), sorted(_EXPECTED_TITLES), f"실행 줄이 다섯 개가 아님(D25 사전조건 — {surface_label})")
                for key in ("r-running", "r-ended"):
                    self.assertEqual(rows[key]["title"], _EXPECTED_TITLES[key], f"재개된 실행의 제목이 재개 요약이 아님(D25, TF12 — {surface_label} {key})")

    def test_d25_elapsed_column_stays_plain_elapsed_time_without_the_resume_count(self) -> None:
        # Q1 안 A(승인) — 재개 횟수는 툴팁에만 적고 줄 끝 경과 칸에는 늘 보이게 하지 않는다(안 B 기각: 좁은 화면에서 제목이 더 잘린다).
        # 재개된 줄도 경과 칸은 오늘처럼 경과 시간뿐이다(경과는 마지막 재개부터 센다는 기존 계약 그대로).
        report = _main_report()
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                rows = _rows_by_key(report[surface])
                self.assertEqual({key: row["meta"] for key, row in rows.items()}, _EXPECTED_ELAPSED, f"경과 칸이 경과 시간뿐이 아님(D25, Q1 안 A — {surface_label})")

    def test_d25_poll_replaces_the_title_and_tooltip_in_place_when_the_agent_is_resumed_again(self) -> None:
        # 사용자가 본 장면 — 검수 에이전트가 M2 를 끝내고 M3 로 또 재개된다. 같은 줄(같은 노드)이 새 제목·새 툴팁·실행 중 표시로 바뀐다.
        probe_body = _POLL_PROBE % {"key": _POLL_KEY, "poll_document": _safe_js_string_literal(_minimal_data_document(_POLL_SNAPSHOT_AFTER))}
        result = run_scenario(_make_page(_POLL_SNAPSHOT_BEFORE, probe_body))
        clock_before, clock_after = _clock_label(_POLL_BEFORE.started_at_ms), _clock_label(_POLL_AFTER.started_at_ms)
        self.assertEqual(result["before"]["title"], "M2 변경 검수", "폴링 전 제목이 M2 재개 요약이 아님(D25 사전조건)")
        self.assertFalse(result["before"]["running"], "폴링 전 줄이 실행 중 표시임(D25 사전조건)")
        self.assertTrue(result["sameNode"], "폴링 뒤 같은 에이전트의 줄이 같은 노드가 아님(D25 — 제목만 제자리에서 바뀌어야 한다)")
        self.assertEqual(result["after"]["title"], "M3 변경 검수", "폴링 뒤 제목이 새 재개 요약으로 바뀌지 않음(D25, TF12)")
        self.assertEqual(
            result["after"]["tooltip"], f"code-reviewer · 검수 단계 · sonnet · 재개 {clock_after} · 진행 중 · 재개 2회",
            "폴링 뒤 툴팁이 새 재개 시각·횟수로 바뀌지 않음(D25·D27, TF12)",
        )
        self.assertEqual(
            result["before"]["tooltip"], f"code-reviewer · 검수 단계 · sonnet · 재개 {clock_before} · 종료 · 재개 1회",
            "폴링 전 툴팁이 M2 재개 시각·횟수가 아님(D25 사전조건)",
        )
        self.assertTrue(result["after"]["running"], "폴링 뒤 재개된 줄이 실행 중 표시가 아님(D25)")

    def test_d25_long_resume_title_is_clipped_inside_the_row_at_the_narrowest_card_width(self) -> None:
        # 결정 TF12(안 A) — 제목 칸만 바꿨으므로 줄 모양은 그대로다: 긴 재개 요약(끊을 곳 없는 토큰 포함)은 한 줄 말줄임으로 줄 안에 머물고,
        # 경과 칸은 제목 오른쪽에서 줄을 벗어나지 않는다. 짧은 재개 요약은 잘리지 않는다. 카드 트랙의 최소 폭 320px 에서 본다.
        probe_body = _NARROW_ROW_PROBE % {"width": _NARROW_CARD_WIDTH_PX}
        result = run_scenario(_make_page(_NARROW_SNAPSHOT, probe_body))
        self.assertAlmostEqual(result["cardWidth"], _NARROW_CARD_WIDTH_PX, delta=_GEOMETRY_TOLERANCE_PX, msg="카드 폭이 320px 가 아님(D25 사전조건)")
        rows = _rows_by_key(result["rows"])
        for key, is_clipped in (("n-long", True), ("n-short", False)):
            with self.subTest(row=key):
                self.assertLessEqual(rows[key]["rowOverflowX"], _GEOMETRY_TOLERANCE_PX, f"재개 제목이 줄을 가로로 넘침(D25, TF12 — {key})")
                self.assertEqual(rows[key]["titleWhiteSpace"], "nowrap", f"카드 목록의 제목이 한 줄이 아님(D25, TF12 — {key})")
                self.assertEqual(rows[key]["titleClipped"], is_clipped, f"제목의 잘림 여부가 기대와 다름(D25, TF12 — {key})")
                self.assertTrue(rows[key]["metaInsideRow"], f"경과 칸이 줄 오른쪽 밖으로 밀림(D25, TF12 — {key})")
                self.assertTrue(rows[key]["metaAfterTitle"], f"경과 칸이 제목과 겹침(D25, TF12 — {key})")

    def test_d26_run_without_a_resume_title_keeps_todays_title_chain(self) -> None:
        # 결정 TF8·TF12 — 재개 요청에 요약이 없으면(resume_title 없음) 더 옛 요약으로 대신하지 않고 오늘의 사슬(설명 → 타입명)이다.
        # 재개 횟수는 있어도 제목을 바꾸지 않는다(요약 없는 재개 r-summaryless).
        report = _main_report()
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                rows = _rows_by_key(report[surface])
                for key in ("r-summaryless", "r-plain", "r-untitled"):
                    self.assertEqual(rows[key]["title"], _EXPECTED_TITLES[key], f"재개 요약이 없는 실행의 제목이 오늘의 사슬이 아님(D26 — {surface_label} {key})")

    def test_d26_payload_without_the_new_fields_renders_exactly_like_today(self) -> None:
        # §6.5 — 두 필드를 싣기 전 서버의 페이로드(키 없음)를 새 템플릿이 그려도 재개된 실행까지 오늘 화면 그대로다(제목은 설명, 툴팁은 「시작」).
        report = _server_without_resume_fields_report()
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                rows = _rows_by_key(report[surface])
                self.assertEqual({key: row["title"] for key, row in rows.items()}, _TODAYS_TITLES, f"키 없는 페이로드의 제목이 오늘의 사슬이 아님(D26 — {surface_label})")
                self.assertEqual({key: row["tooltip"] for key, row in rows.items()}, _TODAYS_TOOLTIPS, f"키 없는 페이로드의 툴팁이 오늘 모양이 아님(D26 — {surface_label})")

    def test_d26_never_resumed_run_renders_character_for_character_like_a_payload_without_the_new_fields(self) -> None:
        # 성공 기준 ①(c) — 재개된 적 없는 실행(resume_title 없음 · resume_count 0)은 두 키를 싣든 안 싣든 줄 마크업 전체가 한 글자도 같다.
        with_fields, without_fields = _main_report(), _server_without_resume_fields_report()
        for surface, surface_label in _SURFACES:
            for key in _NEVER_RESUMED_KEYS:
                with self.subTest(surface=surface_label, row=key):
                    self.assertEqual(
                        _rows_by_key(with_fields[surface])[key]["html"], _rows_by_key(without_fields[surface])[key]["html"],
                        f"재개된 적 없는 실행의 줄 마크업이 두 필드 유무에 따라 달라짐(D26, 성공 기준 ①(c) — {surface_label} {key})",
                    )

    def test_d27_tooltip_names_the_resume_time_and_count_only_for_resumed_runs(self) -> None:
        # 결정 TF12 — 재개된 실행의 툴팁은 시작 라벨이 「재개 HH:MM」(그 시각은 마지막 재개였다)이고 끝에 「 · 재개 N회」가 붙는다. 재개된 적 없는
        # 실행은 「시작 HH:MM」 그대로이고 「재개」라는 말이 없다. 「N회차」는 쓰지 않는다 — 검수 회차(재검수 왕복)와 헷갈린다.
        report = _main_report()
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                rows = _rows_by_key(report[surface])
                self.assertEqual({key: row["tooltip"] for key, row in rows.items()}, _EXPECTED_TOOLTIPS, f"툴팁이 기대와 다름(D27, TF12 — {surface_label})")
                for key in _NEVER_RESUMED_KEYS:
                    self.assertNotIn("재개", rows[key]["tooltip"], f"재개된 적 없는 실행의 툴팁에 「재개」가 있음(D27 — {surface_label} {key})")
                for row in rows.values():
                    self.assertNotIn("회차", row["tooltip"], f"툴팁에 「N회차」 표현이 있음(D27, TF12 — {surface_label} {row['key']})")

    def test_d28_resume_title_with_markup_is_text_only_on_both_surfaces(self) -> None:
        # T25-11(호출부 escapeHtml 정적 가드)과 이중 방어 — 재개 요약에 태그·따옴표·엔티티가 들어 있어도 제목은 입력 글자 그대로의 텍스트이고,
        # 요소(img)도 스크립트 실행도 없다. 엔티티 글자(&amp;)는 한 번 더 해석되지 않고 그대로 보인다.
        result = run_scenario(_make_page(_HOSTILE_SNAPSHOT, _MARKUP_PROBE % {"settle": _SETTLE_MS, "path": _PATH}))
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                self.assertEqual(result[surface]["text"], _HOSTILE_TITLE, f"마크업이 든 재개 요약이 입력 글자 그대로 보이지 않음(D28, TF12 — {surface_label})")
                self.assertEqual(result[surface]["childElements"], 0, f"제목 칸 안에 자식 요소가 생김(D28 — {surface_label})")
                self.assertEqual(result[surface]["imageCount"], 0, f"재개 요약의 img 태그가 요소가 됨(D28 — {surface_label})")
        self.assertEqual(result["scriptRan"], "undefined", "재개 요약의 이벤트 핸들러가 실행됨(D28)")


if __name__ == "__main__":
    unittest.main()
