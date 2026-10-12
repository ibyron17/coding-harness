"""tests/hub/test_hub_template_dom_modal_layout.py — 헤드리스 Chrome DOM 행동 검사 중 카드 상세보기 창의
자리·스크롤 막대·카드 폭 3건(D29~D31, docs/prps/hub-session-row-layout-and-modal-size.md 결정 LM8 개정 ·
docs/prps/hub-session-modal-cleanup.md 결정 MX8·SC16 개정).

- D29 창의 자리는 사용량 패널(없음·펼침·접힘)에 의존하지 않고, 윗변이 영역 높이의 12.5% 지점(화면의 약 20%)에 오며(내용이 길면 그
  오프셋이 줄어 창이 영역 안에 들어온다), 내용이 넘쳐도 윗변이 헤더 밑으로 잘려 접근 불가해지지 않는다.
- D30 가로 스크롤 칸(ul.session-strip)의 스크롤 막대는 보이지 않고 높이를 차지하지 않으며, 가로 스크롤은 그대로다.
- D31 세션 카드 li 의 폭은 같은 화면의 메인 카드(div.card, 그리드 트랙) 폭보다 크지 않고 근접하며(열 최소폭 320px 는 지킨다),
  2·3개 세션은 가로 스크롤 없이 칸에 딱 들어간다 — 좁은 화면에서는
  max-width:calc(100% - 40px) 가 누른다.

창 높이(내용 높이)의 기본 계약(D21)과 연결선 접합(D20)은 test_hub_template_dom_modal_cleanup.py 에 있고,
이 모듈은 그 픽스처를 빌려 쓴다. Chrome 이 없으면 SKIP. 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 —
변경 전 템플릿으로 돌려 이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import json
import unittest

try:
    from .template_dom_harness import (
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        make_project as _project,
        make_snapshot as _snapshot,
        run_scenario,
    )
    from .test_hub_template_dom_modal_cleanup import (
        _LAYOUT_SNAPSHOT,
        _LAYOUT_USAGE_SNAPSHOT,
        _LONG_PATH,
        _LONG_SNAPSHOT,
        _SETTLE_MS,
        _SOLO_PATH,
        _WIDE_PATH,
        _plain_sessions,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        make_project as _project,
        make_snapshot as _snapshot,
        run_scenario,
    )
    from test_hub_template_dom_modal_cleanup import (  # noqa: E402
        _LAYOUT_SNAPSHOT,
        _LAYOUT_USAGE_SNAPSHOT,
        _LONG_PATH,
        _LONG_SNAPSHOT,
        _SETTLE_MS,
        _SOLO_PATH,
        _WIDE_PATH,
        _plain_sessions,
    )

_GEOMETRY_TOLERANCE_PX = 0.5
_MODAL_BOTTOM_MARGIN_PX = 16           # 오버레이의 아래 여백 — 사용량 패널과 무관한 고정값
_DIALOG_TOP_FRACTION = 0.125           # 창 윗변 = 영역(헤더 아래 ~ 화면 아래 16px) 윗변에서 영역 높이의 12.5% 아래 — 내용이 길면 줄어든다(결정 LM8 재재개정)
_CENTERED_GAP_LIMIT = 0.5              # 「약간만 위로」 — 창 위 간격이 가운데 정렬일 때 간격((영역 − 창 높이) / 2)의 이 비율 이하여야 한다. 옛 30% 는 약 0.9 라 가운데처럼 보였다
_STRIP_PEEK_PX = 40                    # max-width:calc(100% - 40px) — 다음 카드가 엿보이는 폭
_LONG_USAGE_SNAPSHOT = dataclasses.replace(_LONG_SNAPSHOT, usage=_LAYOUT_USAGE_SNAPSHOT.usage)
_OVERFLOW_HEIGHTS = (400, 480, 560, 640)   # 1024 폭에서 긴 세션 하나가 가용 높이에 걸쳐 넘치다 들어가는 구간
# (너비, 높이, 프로젝트, 칸에 딱 들어가야 하는가). 1024 는 3열 문턱(안쪽 폭 942~984px) 바로 위라 열 최소폭 320px 가 걸려 3개가 34px 넘친다 —
# 그 폭에서는 넘침을 허용하고 320px 를 지키는지만 본다. 600 은 1열이라 한 장이 칸보다 40px 좁다(엿보기).
_LIST_VS_MODAL_VIEWPORTS = (
    (1440, 900, "/repo/three", True), (1024, 560, "/repo/three", False), (820, 700, "/repo/two", True), (600, 700, "/repo/three", False),
)
_MIN_CARD_WIDTH_PX = 320               # 메인 그리드의 열 최소폭 — 세션 카드도 이 밑으로 줄지 않는다
# 세션 카드는 메인 카드보다 (창 안쪽 패딩 + 테두리 42px) ÷ 열 수 만큼 좁다: 2열 21px · 3열 14px. 메인 카드 폭에 대한 비율의 최댓값은
# 2열 문턱 바로 위(메인 카드 약 341px)에서 6.2% 라 7% 를 상한으로 둔다.
_MAX_NARROWER_FRACTION = 0.07
_FIT_SNAPSHOT = _snapshot((
    _project("/repo/two", "two", "idle", _plain_sessions("two", 2)),
    _project("/repo/three", "three", "idle", _plain_sessions("three", 3)),
))
# 세션 1·3·5개 — 내용이 들어가는 구간에서 창 윗변이 영역의 12.5% 에 오는지 본다(D29).
_TOP_POSITION_SNAPSHOT = _snapshot((
    _project(_SOLO_PATH, "solo", "idle", _plain_sessions("solo", 1)),
    _project("/repo/three", "three", "idle", _plain_sessions("three", 3)),
    _project(_WIDE_PATH, "wide", "idle", _plain_sessions("wide", 5)),
))
_TOP_POSITION_PATHS = (_SOLO_PATH, "/repo/three", _WIDE_PATH)
_TOP_POSITION_VIEWPORTS = ((1440, 900), (1024, 560), (820, 700))

# D29 프로브 — 프로젝트마다 카드 상세보기를 열어 사용량 패널의 지금 상태에서 창·영역의 자리를 재고,
# 패널이 보이면 토글을 눌러 반대 상태에서 한 번 더 잰다(없으면 한 번). 채우는 자리: settle(ms)·paths(JSON 배열).
_USAGE_STATE_PROBE = """
function rectOf(el){ var r = el.getBoundingClientRect(); return {top: r.top, height: r.height, left: r.left, width: r.width, bottom: r.bottom}; }
function snapshotState(){
  var usage = document.getElementById('dzh-usage');
  return {
    usageHidden: usage.hidden, usageHeight: usage.offsetHeight,
    usageExpanded: document.getElementById('dzh-usage-toggle').getAttribute('aria-expanded') === 'true',
    modal: rectOf(document.getElementById('dzh-session-modal')),
    dialog: rectOf(document.querySelector('.session-modal-dialog')),
  };
}
async function measureProject(path){
  var card = document.querySelector('#dzh-app .card[data-project-path="' + path + '"]');
  __dispatchClick(card.querySelector('.path'));
  await __sleep(%(settle)d);
  var states = [snapshotState()];
  if(!document.getElementById('dzh-usage').hidden){
    __dispatchClick(document.getElementById('dzh-usage-toggle'));
    await __sleep(%(settle)d);
    states.push(snapshotState());
    __dispatchClick(document.getElementById('dzh-usage-toggle'));
    await __sleep(%(settle)d);
  }
  var modalStillOpen = document.body.classList.contains('dzh-session-modal-open');
  __dispatchClick(document.getElementById('dzh-session-modal'));
  await __sleep(%(settle)d);
  return {path: path, states: states, modalStillOpen: modalStillOpen};
}
var paths = %(paths)s;
var results = [];
for(var i = 0; i < paths.length; i++) results.push(await measureProject(paths[i]));
__probeResult({results: results, innerWidth: window.innerWidth, innerHeight: window.innerHeight});
"""

# D30 프로브 — 가로로 넘치는 프로젝트를 열어 칸의 스크롤 막대 흔적과 가로 스크롤 동작을 잰다. 넘침 단서는 scroll 이벤트가 켜는데, 헤드리스
# 가상 시간에서는 scrollLeft 대입이 낳는 scroll 이벤트가 프레임 타이밍에 따라 오지 않는 실행이 있어(실측: 같은 프로브가 실행마다 달랐다)
# 이벤트를 직접 보낸다 — 이 검사가 보는 것은 막대를 숨겨도 스크롤 위치→단서 경로가 살아 있다는 것이다. 채우는 자리: settle(ms)·path.
_STRIP_SCROLLBAR_PROBE = """
function px(value){ var n = parseFloat(value); return isNaN(n) ? null : n; }
var card = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var strip = document.querySelector('#dzh-session-modal-body .session-strip');
var body = document.getElementById('dzh-session-modal-body');
var style = getComputedStyle(strip);
var firstItemRect = strip.firstElementChild.getBoundingClientRect();
var before = {scrollLeft: strip.scrollLeft, canScroll: strip.scrollWidth > strip.clientWidth, hiddenLeft: body.classList.contains('session-strip-hidden-left'), hiddenRight: body.classList.contains('session-strip-hidden-right')};
strip.scrollLeft = strip.scrollWidth - strip.clientWidth;
strip.dispatchEvent(new Event('scroll'));
await __sleep(%(settle)d);
__probeResult({
  before: before,
  after: {scrollLeft: strip.scrollLeft, hiddenLeft: body.classList.contains('session-strip-hidden-left'), hiddenRight: body.classList.contains('session-strip-hidden-right')},
  overflowX: style.overflowX, scrollbarWidthProperty: style.scrollbarWidth,
  webkitScrollbarDisplay: getComputedStyle(strip, '::-webkit-scrollbar').display,
  horizontalScrollbarHeight: strip.offsetHeight - strip.clientHeight,
  paddingTop: px(style.paddingTop), paddingBottom: px(style.paddingBottom),
  itemHeight: firstItemRect.height, stripHeight: strip.offsetHeight,
});
"""

# D31 프로브 — 메인 화면의 첫 카드(div.card) 폭과, 카드 상세보기를 연 뒤 칸의 세션 카드 li 폭을 잰다.
# 모달이 열리면 본문 스크롤이 잠겨 세로 스크롤바가 사라지므로(폭이 달라질 수 있다) 카드 폭도 모달을 연 뒤에 잰다.
# 채우는 자리: settle(ms)·path.
_CARD_WIDTH_PROBE = """
var projectCard = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
__dispatchClick(projectCard.querySelector('.path'));
await __sleep(%(settle)d);
var strip = document.querySelector('#dzh-session-modal-body .session-strip');
var stripStyle = getComputedStyle(strip);
__probeResult({
  innerWidth: window.innerWidth,
  cardWidth: document.querySelector('#dzh-app .card').getBoundingClientRect().width,
  stripContentWidth: strip.clientWidth - parseFloat(stripStyle.paddingLeft) - parseFloat(stripStyle.paddingRight),
  itemWidths: Array.prototype.map.call(strip.children, function(item){ return item.getBoundingClientRect().width; }),
  stripScrollWidth: strip.scrollWidth, stripClientWidth: strip.clientWidth,
});
"""


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubSessionModalLayoutDomTest(unittest.TestCase):
    """카드 상세보기 창의 자리·스크롤 막대·카드 폭의 행동 계약."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def _assert_near(self, actual: float, expected: float, message: str) -> None:
        self.assertAlmostEqual(actual, expected, delta=_GEOMETRY_TOLERANCE_PX, msg=f"{message} (실측 {actual:.2f} vs 기대 {expected:.2f})")

    def _measure_usage_states(self, snapshot, paths: tuple[str, ...], width: int, height: int) -> dict:
        probe_body = _USAGE_STATE_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps(list(paths))}
        result = run_scenario(_make_page(snapshot, probe_body), window_width=width, window_height=height)
        return {entry["path"]: entry for entry in result["results"]}

    def test_d29_dialog_position_and_height_ignore_the_usage_panel_state(self) -> None:
        # 결정 LM8 개정 — 사용량 패널은 떠 있는(floating) 컴포넌트다: 없음·펼침·접힘 어느 상태에서도 창의 top·높이가
        # 같다(예전에는 펼치면 가운데 영역의 아랫변이 패널 높이만큼 올라가 창이 위로 올라갔다). 내용이 들어가는 경우(세션 1·5개,
        # 1440×900)와 넘치는 경우(긴 세션, 1024×560 — 창 최대 높이도 패널에 의존하지 않는다) 모두 본다.
        scenarios = (
            ("내용이 들어감", _LAYOUT_SNAPSHOT, _LAYOUT_USAGE_SNAPSHOT, (_SOLO_PATH, _WIDE_PATH), 1440, 900),
            ("내용이 넘침", _LONG_SNAPSHOT, _LONG_USAGE_SNAPSHOT, (_LONG_PATH,), 1024, 560),
        )
        for label, plain_snapshot, usage_snapshot, paths, width, height in scenarios:
            baseline = self._measure_usage_states(plain_snapshot, paths, width, height)
            with_usage = self._measure_usage_states(usage_snapshot, paths, width, height)
            for path in paths:
                with self.subTest(scenario=label, project=path):
                    self._assert_same_position_in_every_usage_state(baseline[path], with_usage[path], f"D29, LM8 — {label} {path}")

    def _assert_same_position_in_every_usage_state(self, plain: dict, with_usage: dict, where: str) -> None:
        """패널 없는 화면의 창 자리와, 패널이 펼침·접힘인 두 상태의 창 자리가 같다(D29)."""
        self.assertEqual(len(plain["states"]), 1, f"패널 없는 픽스처에서 패널이 보임(사전조건 — {where})")
        self.assertTrue(plain["states"][0]["usageHidden"], f"패널 없는 픽스처에서 패널이 보임(사전조건 — {where})")
        self.assertEqual(len(with_usage["states"]), 2, f"패널이 있는 픽스처에서 토글이 안 됨(사전조건 — {where})")
        self.assertEqual({state["usageExpanded"] for state in with_usage["states"]}, {True, False}, f"펼침·접힘 두 상태를 다 재지 못함(사전조건 — {where})")
        expanded = next(state for state in with_usage["states"] if state["usageExpanded"])
        collapsed = next(state for state in with_usage["states"] if not state["usageExpanded"])
        self.assertGreater(expanded["usageHeight"], collapsed["usageHeight"] + 20, f"펼친 패널이 접힌 패널보다 충분히 높지 않음(사전조건 — {where})")
        self.assertTrue(with_usage["modalStillOpen"], f"패널을 토글하자 카드 상세보기가 닫힘(사전조건 — {where})")
        baseline_dialog = plain["states"][0]["dialog"]
        for state, state_label in ((expanded, "펼침"), (collapsed, "접힘")):
            self._assert_near(state["dialog"]["top"], baseline_dialog["top"], f"패널 {state_label}에서 창 윗변이 패널 없음과 다름({where})")
            self._assert_near(state["dialog"]["height"], baseline_dialog["height"], f"패널 {state_label}에서 창 높이가 패널 없음과 다름({where})")
            self._assert_near(state["modal"]["height"], plain["states"][0]["modal"]["height"], f"패널 {state_label}에서 모달 영역 높이가 달라짐({where})")

    def _expected_gap_above(self, state: dict) -> float:
        """영역 윗변에서 창 윗변까지의 기대 간격 — 영역 높이의 12.5% 이되, 그만큼 내리면 창이 영역 아래를 넘을 때는 영역에 들어오는 만큼까지만
        (스페이서가 먼저 줄어든다). 영역 = 오버레이 높이 − 아래 여백 16px."""
        area = state["modal"]["height"] - _MODAL_BOTTOM_MARGIN_PX
        return max(0.0, min(_DIALOG_TOP_FRACTION * area, area - state["dialog"]["height"]))

    def test_d29_dialog_top_sits_at_one_eighth_of_the_area(self) -> None:
        # 결정 LM8 재개정 — 창 윗변은 영역(헤더 아래 ~ 화면 아래 16px) 윗변에서 영역 높이의 12.5% 아래다(가운데 정렬이 아니다). 세션 1·3·5개 ×
        # 세 화면 크기 모두에서 같은 식(_expected_gap_above)이 성립하고, 아래 간격은 창 높이 몫이라 창이 영역 안(아래 16px 여백 유지)에 있다.
        probe_body = _USAGE_STATE_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps(list(_TOP_POSITION_PATHS))}
        for width, height in _TOP_POSITION_VIEWPORTS:
            result = run_scenario(_make_page(_TOP_POSITION_SNAPSHOT, probe_body), window_width=width, window_height=height)
            for entry in result["results"]:
                with self.subTest(viewport=f"{width}x{height}", project=entry["path"]):
                    state = entry["states"][0]
                    gap_above = state["dialog"]["top"] - state["modal"]["top"]
                    gap_below = state["modal"]["bottom"] - state["dialog"]["bottom"]
                    self._assert_near(gap_above, self._expected_gap_above(state), f"창 윗변이 영역 높이의 12.5% 지점이 아님(D29, LM8 — {width}x{height})")
                    self.assertGreaterEqual(gap_below, _MODAL_BOTTOM_MARGIN_PX - _GEOMETRY_TOLERANCE_PX, f"창 아랫변이 화면 아래 16px 여백을 침범함(D29, LM8 — {width}x{height})")

    def test_d29_dialog_top_is_exactly_one_eighth_and_well_above_the_center_when_the_content_fits_below_it(self) -> None:
        # 사전조건을 겸한다 — 1440×900 에서는 어느 프로젝트도 12.5% 아래에 다 들어가므로(창 높이 ≤ 영역의 87.5%) 위 식의 줄어드는 갈래가 아니라
        # 12.5% 갈래를 본다: 창 윗변이 영역 높이의 정확히 12.5% 이고 가운데 정렬 자리에서 뚜렷이 위다(사용자 지시 「약간만 위로」 — 옛 30% 는 창 높이가
        # 280~350px 인 화면에서 가운데 정렬 간격의 약 0.9 라 가운데처럼 보였다).
        probe_body = _USAGE_STATE_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps(list(_TOP_POSITION_PATHS))}
        result = run_scenario(_make_page(_TOP_POSITION_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        for entry in result["results"]:
            with self.subTest(project=entry["path"]):
                state = entry["states"][0]
                area = state["modal"]["height"] - _MODAL_BOTTOM_MARGIN_PX
                self.assertLessEqual(state["dialog"]["height"], (1 - _DIALOG_TOP_FRACTION) * area, "창이 12.5% 아래에 다 들어가지 않음(D29 사전조건)")
                gap_above = state["dialog"]["top"] - state["modal"]["top"]
                self._assert_near(gap_above, _DIALOG_TOP_FRACTION * area, "창 윗변이 영역 높이의 12.5% 가 아님(D29, LM8)")
                centered_gap = (area - state["dialog"]["height"]) / 2
                self.assertLessEqual(gap_above, _CENTERED_GAP_LIMIT * centered_gap, "창이 세로 가운데에 가깝게 뜸(D29, LM8 재재개정 — 「약간만 위로」가 아니다)")

    def test_d29_dialog_stays_reachable_while_the_offset_gives_way_to_overflowing_content(self) -> None:
        # 결정 LM8 재개정 — 내용이 12.5% 아래에 못 들어가기 시작하는 구간에서는 오프셋이 먼저 줄어(0 까지) 창을 영역 안에 들인다: 위 간격은 늘 0 이상이고
        # 창은 영역(− 아래 여백) 안에 있으며 위 간격은 위 식을 따른다. 내용이 넘쳤을 때 창이 영역 끝까지 늘고 창 안에서 스크롤하는 것은 D21 이 본다.
        probe_body = _USAGE_STATE_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps([_LONG_PATH])}
        for height in _OVERFLOW_HEIGHTS:
            with self.subTest(height=height):
                state = run_scenario(_make_page(_LONG_SNAPSHOT, probe_body), window_width=1024, window_height=height)["results"][0]["states"][0]
                gap_above = state["dialog"]["top"] - state["modal"]["top"]
                gap_below = state["modal"]["bottom"] - state["dialog"]["bottom"]
                self.assertGreaterEqual(gap_above, -_GEOMETRY_TOLERANCE_PX, f"창 윗변이 헤더 밑으로 잘려 올라감(D29, LM8 — 높이 {height})")
                self._assert_near(gap_above, self._expected_gap_above(state), f"위 간격이 min(영역의 12.5%, 영역 − 창 높이)가 아님(D29, LM8 — 높이 {height})")
                self.assertGreaterEqual(gap_below, _MODAL_BOTTOM_MARGIN_PX - _GEOMETRY_TOLERANCE_PX, f"창 아랫변이 화면 아래 16px 여백을 침범함(D29, LM8 — 높이 {height})")
                self.assertLessEqual(state["dialog"]["height"], state["modal"]["height"] - _MODAL_BOTTOM_MARGIN_PX + _GEOMETRY_TOLERANCE_PX, f"창이 영역(− 아래 여백)보다 큼(D29, LM8 — 높이 {height})")

    def test_d30_strip_scrollbar_is_invisible_takes_no_height_and_horizontal_scrolling_still_works(self) -> None:
        # 요구 3 — 칸(ul.session-strip)의 스크롤 막대는 표준 scrollbar-width:none 과 ::-webkit-scrollbar 로 숨기고 높이를 차지하지
        # 않는다(offsetHeight − clientHeight = 0). overflow-x:auto 는 그대로라 가로 스크롤이 되고, 넘침 단서(SC11)도 스크롤에 따라
        # 켜지고 꺼진다. 칸의 위·아래 안쪽 패딩(4px·10px)과 연결선 위 패딩(27px)은 막대가 사라져도 그대로다.
        probe_body = _STRIP_SCROLLBAR_PROBE % {"settle": _SETTLE_MS, "path": _WIDE_PATH}
        report = run_scenario(_make_page(_LAYOUT_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        self.assertEqual(report["scrollbarWidthProperty"], "none", "칸에 scrollbar-width:none 이 없음(D30)")
        self.assertEqual(report["webkitScrollbarDisplay"], "none", "칸의 ::-webkit-scrollbar 가 숨겨지지 않음(D30)")
        self._assert_near(report["horizontalScrollbarHeight"], 0, "스크롤 막대가 칸의 높이를 차지함(D30)")
        self.assertEqual(report["overflowX"], "auto", "칸이 가로 스크롤 컨테이너가 아님 — 막대를 숨기며 가로 스크롤까지 죽였다(D30)")
        self.assertTrue(report["before"]["canScroll"], "칸이 가로로 넘치지 않음(D30 사전조건)")
        self.assertGreater(report["after"]["scrollLeft"], 0, "칸이 가로로 스크롤되지 않음(D30)")
        self.assertTrue(report["before"]["hiddenRight"] and not report["before"]["hiddenLeft"], "스크롤 시작에서 넘침 단서가 오른쪽에만 켜지지 않음(D30, SC11)")
        self.assertTrue(report["after"]["hiddenLeft"] and not report["after"]["hiddenRight"], "스크롤 끝에서 넘침 단서가 왼쪽에만 켜지지 않음(D30, SC11)")
        self._assert_near(report["paddingBottom"], 10, "칸 아래 안쪽 패딩이 10px 가 아님(D30)")
        self._assert_near(report["stripHeight"], report["paddingTop"] + report["itemHeight"] + report["paddingBottom"], "칸 높이가 위 패딩 + 카드 + 아래 패딩이 아님(D30)")

    def test_d31_session_card_width_stays_close_to_the_list_card_and_never_exceeds_it(self) -> None:
        # 요구 4 — 카드 상세보기 세션 카드 li 는 같은 화면의 메인 카드(그리드 트랙)보다 넓지 않고 7% 안쪽으로 좁다. 열 최소폭 320px 밑으로는
        # 줄지 않는다. 좁은 화면에서는 칸에 다음 카드가 엿보이도록 max-width:calc(100% - 40px)(결정 MX8)가 누른다 — 위·아래 한계는
        # min(메인 카드 폭, 칸 안쪽 폭 − 40) 기준이다. 2·3개 세션이 칸에 딱 들어가는 폭인지는 아래 검사가 본다.
        probe_template = _CARD_WIDTH_PROBE
        for width, height, path, _ in _LIST_VS_MODAL_VIEWPORTS:
            with self.subTest(viewport=f"{width}x{height}"):
                report = self._measure_card_width(probe_template, path, width, height)
                peek_cap = report["stripContentWidth"] - _STRIP_PEEK_PX
                upper = min(report["cardWidth"], peek_cap)
                lower = min(report["cardWidth"] * (1 - _MAX_NARROWER_FRACTION), peek_cap, report["cardWidth"])
                floor = min(_MIN_CARD_WIDTH_PX, peek_cap)
                for index, item_width in enumerate(report["itemWidths"], start=1):
                    where = f"{index}번째 세션 카드 li {item_width:.2f}px, 메인 카드 {report['cardWidth']:.2f}px, {width}x{height}"
                    self.assertLessEqual(item_width, upper + _GEOMETRY_TOLERANCE_PX, f"세션 카드가 메인 카드(또는 엿보기 상한)보다 넓음(D31, MX8 개정 — {where})")
                    self.assertGreaterEqual(item_width, lower - _GEOMETRY_TOLERANCE_PX, f"세션 카드가 메인 카드보다 7% 넘게 좁음(D31, MX8 개정 — {where})")
                    self.assertGreaterEqual(item_width, floor - _GEOMETRY_TOLERANCE_PX, f"세션 카드가 열 최소폭 320px 밑으로 줄었음(D31, MX8 개정 — {where})")

    def test_d31_two_and_three_sessions_fit_in_the_strip_without_horizontal_scrolling(self) -> None:
        # 요구 4(조정) — 2열 폭에서는 세션 2개, 3열 폭에서는 세션 3개가 가로 스크롤 없이 칸에 딱 들어간다(예전 메인 카드와 같은 폭 식은
        # 1440 에서 세션 3개가 42px 넘쳤다). 열 최소폭 320px 가 걸리는 문턱 위 구간(1024)은 이 검사에서 뺀다.
        for width, height, path, must_fit in _LIST_VS_MODAL_VIEWPORTS:
            if not must_fit:
                continue
            with self.subTest(viewport=f"{width}x{height}", project=path):
                report = self._measure_card_width(_CARD_WIDTH_PROBE, path, width, height)
                self.assertLessEqual(report["stripScrollWidth"], report["stripClientWidth"] + 1, f"세션 {len(report['itemWidths'])}개가 가로로 넘침(D31, MX8 개정 — {width}x{height})")

    def test_d31_session_card_is_wider_than_the_old_fixed_320px_on_wide_screens(self) -> None:
        # 요구 4 — 넓은 화면의 카드 폭이 옛 고정 320px 보다 실제로 커졌다(위 검사가 둘 다 320 으로 맞아 통과하는 길을 막는다).
        report = self._measure_card_width(_CARD_WIDTH_PROBE, "/repo/three", 1440, 900)
        self.assertGreater(report["cardWidth"], 400, "메인 카드가 넓지 않음(D31 사전조건)")
        self.assertGreater(min(report["itemWidths"]), 400, "세션 카드가 옛 고정 폭 320px 근처에 머묾(D31, MX8 개정)")

    def _measure_card_width(self, probe_template: str, path: str, width: int, height: int) -> dict:
        probe_body = probe_template % {"settle": _SETTLE_MS, "path": path}
        report = run_scenario(_make_page(_FIT_SNAPSHOT, probe_body), window_width=width, window_height=height)
        if report["innerWidth"] != width:
            self.skipTest(f"헤드리스 Chrome 이 {width}px 폭 창을 만들지 못함(실측 {report['innerWidth']}px)")
        return report


if __name__ == "__main__":
    unittest.main()
