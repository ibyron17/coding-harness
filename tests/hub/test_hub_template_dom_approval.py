"""tests/hub/test_hub_template_dom_approval.py — 헤드리스 Chrome DOM 행동 검사 중 승인 대기 표지 3건(D43~D45,
docs/prps/hub-approval-wait-badge.md §6.2, 결정 AW1·AW3·AW4·AW5).

진행 기록의 「승인」 단계가 진행중이고 세션이 사용자 입력을 기다리면(base_state idle ∧ 한도 초과 아님) 세션 줄 첫 줄의 상태 배지
바로 뒤에 「◆ 승인 대기」 표지가 붙는다. 카드 목록의 세션 줄과 카드 상세보기의 세션 카드는 같은 조각(renderSessionContent)을 그리므로
세 시나리오 모두 두 화면을 같은 프로브로 잰다(기하는 카드 목록만). 공용 하네스는 template_dom_harness.py(무변경).

Chrome 이 없으면 SKIP(사유 출력). 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 — 변경 전 템플릿으로 돌려
이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (옛 페이로드 흉내를 위한 직렬화 재사용)
import hub_parse  # noqa: E402  (Tier1Snapshot 픽스처용)
import hub_session  # noqa: E402  (BackgroundWait·SessionInterruption 픽스처용)

try:
    from .template_dom_harness import (
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        inject_scripts,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document,
        pre_script,
        run_scenario,
        safe_js_string_literal,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        inject_scripts,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document,
        pre_script,
        run_scenario,
        safe_js_string_literal,
    )

_MS_PER_MINUTE = 60000
_SETTLE_MS = 30                     # 클릭 뒤 동기 렌더가 끝나길 기다리는 짧은 여유
_PROJECT_PATH = "/repo/approval"
_TRACK_WIDTH_PX = 320               # 카드 격자의 최소 트랙 — 가장 좁은 실제 폭(PRP §5.3)
_GEOMETRY_TOLERANCE_PX = 0.5
# 1px 테두리가 있는 「소식 없음」 배지(21px)와 테두리 없는 안쪽 링 표지(19px)는 baseline 으로 정렬돼 top 이 1px 어긋난다(실측). 표지가 줄바꿈으로
# 다른 줄에 서면 top 이 줄 높이(약 19px 이상) 벌어지므로 이 여유를 더해도 여전히 잡힌다.
_BORDERED_STATE_BADGE_TOP_OFFSET_PX = 1
_BADGE_TEXT = "◆승인 대기"           # 글리프(aria-hidden) + 글자. textContent 에는 둘이 붙어 나온다
_BADGE_TOOLTIP = "진행 기록이 「승인」 단계에 있고 세션이 사용자 입력을 기다리고 있습니다. 세션에 답하면(승인·수정 요청) 이 표시가 거둬집니다."
_LEGACY_SESSION_ID = "legacy-no-key"   # 서버 사실 키를 payload 에서 지운 옛 스냅샷 흉내 대상
_SURFACES = (("list", "카드 목록 줄"), ("modal", "카드 상세보기 카드"))


# ── 픽스처 ──
def _steps(*name_state: tuple[str, str]) -> tuple[hub_parse.StepView, ...]:
    return tuple(
        hub_parse.StepView(index=index, name=name, state=state, detail="", started_at=None)
        for index, (name, state) in enumerate(name_state, start=1)
    )


_APPROVAL_STEPS = _steps(("설계", "done"), ("승인", "active"), ("구현", "wait"), ("검수", "wait"))


def _tier1(is_approval_step_active: bool, title: str = "승인 중") -> hub_parse.Tier1Snapshot:
    steps = _APPROVAL_STEPS
    completed = sum(1 for step in steps if step.state == "done")
    return hub_parse.Tier1Snapshot(
        title=title, subtitle="", completed=completed, total=len(steps), percent=round(completed * 100 / len(steps)),
        steps=steps, matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
        file_mtime_ms=BASE_TIME_MS, is_approval_step_active=is_approval_step_active,
    )


_BACKGROUND_WAIT = hub_session.BackgroundWait(
    since_ms=BASE_TIME_MS - 2 * _MS_PER_MINUTE, until_ms=BASE_TIME_MS + 60 * _MS_PER_MINUTE, task_count=1, wakeup_count=0,
)
_INTERRUPTION = hub_session.SessionInterruption(interrupted_at_ms=BASE_TIME_MS - 5 * _MS_PER_MINUTE, resets_at_ms=None)


def _dated(session_id: str, state: str, base_state: str, minutes_ago: int, **fields) -> hub_session.SessionView:
    """세션 하나 — 발췌를 달아 끝난 세션도 화면에 보이게 한다(결정 V2). 필요한 필드만 fields 로 얹는다."""
    base = _session(session_id, state, base_state, BASE_TIME_MS - minutes_ago * _MS_PER_MINUTE, task_excerpt=f"{session_id} 발췌")
    return dataclasses.replace(base, **fields)


# D43 — AW1 조건표의 행마다 세션 1개. 키 = 세션 ID, 값 = (표지 개수 기대, 사유). 식별 이름이 곧 행이다.
_CONDITION_SESSIONS = (
    _dated("idle", "idle", "idle", 1, tier1=_tier1(True)),
    _dated("background", "background", "idle", 2, tier1=_tier1(True), background_wait=_BACKGROUND_WAIT),
    _dated("stale-after-idle", "stale", "idle", 40, tier1=_tier1(True)),
    _dated("stale-after-working", "stale", "working", 40, tier1=_tier1(True)),
    _dated("working", "working", "working", 3, tier1=_tier1(True)),
    _dated("interrupted", "interrupted", "idle", 4, tier1=_tier1(True), interruption=_INTERRUPTION),
    _dated("done", "done", "done", 5, tier1=_tier1(True)),
    _dated("fact-off", "idle", "idle", 6, tier1=_tier1(False)),
    _dated("no-tier1", "idle", "idle", 7),
    _dated(_LEGACY_SESSION_ID, "idle", "idle", 8, tier1=_tier1(True)),
)
_EXPECTED_BADGE_COUNTS = {"idle": 1, "background": 1, "stale-after-idle": 1}   # 나머지는 0
_CONDITION_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "approval", "working", _CONDITION_SESSIONS),))


def _drop_fact_for_legacy_session(payload: dict) -> None:
    """옛 서버의 페이로드 흉내 — 이 세션의 tier1 에서만 새 사실 키를 지운다(키가 없으면 JS 에서 undefined)."""
    for project in payload["projects"]:
        for session in project["sessions"]:
            if session["session_id"] == _LEGACY_SESSION_ID:
                del session["tier1"]["is_approval_step_active"]


def _page_without_legacy_key(snapshot: hub_model.HubSnapshot, probe_body: str) -> str:
    """snapshot 을 구운 페이지의 #dzh-data JSON 을 고친 사본(옛 스냅샷 키 없음)."""
    rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, snapshot)
    opening = '<script type="application/json" id="dzh-data">'
    start = rendered.index(opening) + len(opening)
    end = rendered.index("</script>", start)
    payload = json.loads(rendered[start:end])
    _drop_fact_for_legacy_session(payload)
    escaped = json.dumps(payload, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return inject_scripts(rendered[:start] + escaped + rendered[end:], pre_script(None), probe_body)


# 두 화면의 세션 하나를 재는 공통 조각. 채우는 자리: ids·path·settle.
_SCOPE_REPORT = """
function scopeReport(scope){
  var line = scope.querySelector('.session-line');
  var badges = scope.querySelectorAll('.badge.approval-wait');
  var badge = badges.length ? badges[0] : null;
  var glyph = badge ? badge.querySelector('.glyph') : null;
  var pct = scope.querySelector('.tier1-pct');
  var previous = badge ? badge.previousElementSibling : null;
  return {
    count: scope.querySelectorAll('.approval-wait').length,
    inLine: badge ? line.contains(badge) : null,
    afterStateBadge: previous ? previous.className : null,
    badgeClass: badge ? badge.className : null,
    text: badge ? badge.textContent : null,
    glyphHidden: glyph ? glyph.getAttribute('aria-hidden') : null,
    tooltip: badge ? badge.getAttribute('data-tooltip') : null,
    inMeta: scope.querySelectorAll('.session-meta .approval-wait').length,
    inPct: scope.querySelectorAll('.tier1-pct .approval-wait').length,
    pctElementCount: pct ? pct.children.length : null,
    pctText: pct ? pct.textContent : null,
    runChipCount: scope.querySelectorAll('.agent-run-list .agent-chip').length,
  };
}
var ids = %(ids)s;
var listCard = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
var list = {};
ids.forEach(function(id){ list[id] = scopeReport(listCard.querySelector('.session-row[data-session-id="' + id + '"]')); });
__dispatchClick(listCard.querySelector('.path'));
await __sleep(%(settle)d);
var modal = {};
ids.forEach(function(id){ modal[id] = scopeReport(document.querySelector('#dzh-session-modal-body .session-card[data-session-id="' + id + '"]')); });
__probeResult({list: list, modal: modal});
"""


def _scope_probe(sessions: tuple[hub_session.SessionView, ...]) -> str:
    return _SCOPE_REPORT % {"ids": json.dumps([session.session_id for session in sessions]), "path": _PROJECT_PATH, "settle": _SETTLE_MS}


# D44 — 표지가 붙는 세션. 서브에이전트 실행 줄이 있는 세션도 섞어 「실행 칩 수 불변」과 「진행률 줄에 표지 없음」을 같이 잰다.
_RUN_STARTED_AT_MS = BASE_TIME_MS - 6 * _MS_PER_MINUTE
_APPEARANCE_RUN = hub_session.SubagentRunView(
    agent_id="run-1", agent_type="design-architect", phase="설계", is_running=False, started_at_ms=_RUN_STARTED_AT_MS,
    ended_at_ms=_RUN_STARTED_AT_MS + 3 * _MS_PER_MINUTE, title="설계 실행", model="opus",
)
_APPEARANCE_SESSIONS = (
    _dated("plain", "idle", "idle", 1, tier1=_tier1(True, "제목 A")),
    _dated("with-run", "idle", "idle", 2, tier1=_tier1(True, "제목 B"), agent_runs=(_APPEARANCE_RUN,)),
    _dated("background", "background", "idle", 3, tier1=_tier1(True, "제목 C"), background_wait=_BACKGROUND_WAIT),
)
_APPEARANCE_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "approval", "working", _APPEARANCE_SESSIONS),))
_EXPECTED_RUN_CHIP_COUNTS = {"with-run": 1}   # 나머지는 0


# D45 ① — 320px 트랙의 첫 줄 기하. 「대기」 줄에 표지가 붙어도 높이·상태 배지 중심이 같아야 하고(안쪽 링 — border 였다면 +2px),
# 「소식 없음 · 직전 대기 + 표지 + 긴 소요」 최악 조합도 가로로 넘치지 않고 표지가 상태 배지와 같은 줄에 선다.
_STALE_TASK_START_MINUTES = 83     # 「1시간 23분 소요」 — 첫 줄에서 가장 긴 소요 라벨 계열
_GEOMETRY_SESSIONS = (
    _dated("geo-plain", "idle", "idle", 1, tier1=_tier1(False)),
    _dated("geo-badge", "idle", "idle", 2, tier1=_tier1(True)),
    _dated(
        "geo-stale-long", "stale", "idle", 40, tier1=_tier1(True),
        task_started_at_ms=BASE_TIME_MS - (40 + _STALE_TASK_START_MINUTES) * _MS_PER_MINUTE,
    ),
)
_GEOMETRY_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "approval", "working", _GEOMETRY_SESSIONS),))
_GEOMETRY_PROBE = """
var app = document.getElementById('dzh-app');
app.style.gridTemplateColumns = '%(track)dpx';
await __sleep(%(settle)d);
var card = app.querySelector('.card[data-project-path="%(path)s"]');
function geometry(id){
  var row = card.querySelector('.session-row[data-session-id="' + id + '"]');
  var line = row.querySelector('.session-line');
  var lineRect = line.getBoundingClientRect();
  var state = line.querySelector('.badge[class*="state-"]').getBoundingClientRect();
  var approval = line.querySelector('.approval-wait');
  var approvalRect = approval ? approval.getBoundingClientRect() : null;
  return {
    lineHeight: lineRect.height,
    stateCenter: state.top + state.height / 2 - lineRect.top,
    stateTop: state.top, approvalTop: approvalRect ? approvalRect.top : null,
    rowOverflows: row.scrollWidth > row.clientWidth,
  };
}
__probeResult({
  cardWidth: card.getBoundingClientRect().width,
  plain: geometry('geo-plain'), badge: geometry('geo-badge'), staleLong: geometry('geo-stale-long'),
});
""" % {"track": _TRACK_WIDTH_PX, "settle": _SETTLE_MS, "path": _PROJECT_PATH}


# D45 ② — 사용자가 답해 세션이 작업중이 된 폴링 응답: 표지가 사라지고 세션 줄 노드는 그대로다(맞대기). 응답은 트리거 직전에 심는다 —
# 헤드리스 dump-dom 이 poll() 을 먼저 한 번 돌릴 때가 있어 페이지 로드부터 심어 두면 「처음 화면」이 이미 갱신된 모양이 된다(D1 의 실측 함정).
_POLL_SESSION_ID = "poll-session"


def _poll_snapshot(state: str, base_state: str) -> hub_model.HubSnapshot:
    session = _dated(_POLL_SESSION_ID, state, base_state, 1, tier1=_tier1(True))
    return _snapshot((_project(_PROJECT_PATH, "approval", "working", (session,)),))


_POLL_PROBE = """
var app = document.getElementById('dzh-app');
function readLine(){ return app.querySelector('.session-row[data-session-id="%(id)s"] .session-line'); }
function badgeCount(){ return app.querySelectorAll('.approval-wait').length; }
var line = readLine();
var before = {badgeCount: badgeCount(), stateClass: line.firstElementChild.className};
window.__mockFetchResponseText = %(response)s;
await __triggerPoll();
var lineAfter = readLine();
__probeResult({
  before: before,
  after: {badgeCount: badgeCount(), stateClass: lineAfter.firstElementChild.className},
  lineNodeKept: line === lineAfter && line.isConnected,
});
""" % {"id": _POLL_SESSION_ID, "response": safe_js_string_literal(minimal_data_document(_poll_snapshot("working", "working")))}


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubApprovalWaitBadgeDomTest(unittest.TestCase):
    """승인 대기 표지의 행동 계약 — 근거는 PRP 결정 AW1(표시 조건)·AW3(자리)·AW4(모양)·AW5(LM12 와의 관계)."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def test_d43_badge_shows_only_when_approval_is_active_and_the_session_waits_for_the_user(self) -> None:
        # 결정 AW1 — 표지 = 서버 사실(승인 단계 진행중) ∧ base_state idle ∧ 한도 초과 아님. 대기·백그라운드 대기·소식 없음(직전 대기)에서만 켜지고,
        # 작업중·소식 없음(직전 작업중)·한도 초과·완료·사실 꺼짐·진행 기록 없음·키 없는 옛 스냅샷(페일 클로즈)에서는 꺼진다. 두 화면 모두.
        page = _page_without_legacy_key(_CONDITION_SNAPSHOT, _scope_probe(_CONDITION_SESSIONS))
        result = run_scenario(page, window_width=1440, window_height=900)
        for session in _CONDITION_SESSIONS:
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session.session_id, surface=surface_label):
                    expected = _EXPECTED_BADGE_COUNTS.get(session.session_id, 0)
                    self.assertEqual(result[surface][session.session_id]["count"], expected, "승인 대기 표지 개수가 조건표(AW1)와 다름(D43)")

    def test_d44_badge_sits_right_after_the_state_badge_in_the_first_line_and_is_not_a_stage_chip(self) -> None:
        # 결정 AW3·AW4·AW5 — 표지는 첫 줄(.session-line) 안이고 상태 배지의 바로 다음 형제다. 클래스는 .badge + .approval-wait 이고 실행 칩(.agent-chip)
        # 어휘가 아니다. 글자는 「◆승인 대기」(글리프는 aria-hidden)이고 툴팁은 판정 기준 문구다. 식별 줄·진행률 줄에는 새지 않으며 진행률 줄은 LM12 그대로
        # (자식 요소 0·「제목 — 완료/전체 · %」 글자뿐), 서브에이전트 실행 칩 수도 불변이다. 두 화면 모두.
        result = run_scenario(_make_page(_APPEARANCE_SNAPSHOT, _scope_probe(_APPEARANCE_SESSIONS)), window_width=1440, window_height=900)
        for session in _APPEARANCE_SESSIONS:
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session.session_id, surface=surface_label):
                    self._assert_badge_contract(session, result[surface][session.session_id])

    def _assert_badge_contract(self, session: hub_session.SessionView, report: dict) -> None:
        """표지가 붙은 세션 하나의 자리·모양·LM12 계약(D44)."""
        self.assertEqual(report["count"], 1, "표지가 정확히 하나가 아님(D44)")
        self.assertTrue(report["inLine"], "표지가 첫 줄(.session-line) 안에 없음(D44, AW3)")
        self.assertIn("state-", report["afterStateBadge"], "표지가 상태 배지 바로 뒤가 아님(D44, AW3)")
        badge_classes = report["badgeClass"].split()
        self.assertTrue({"badge", "approval-wait"} <= set(badge_classes), f"표지 클래스에 badge·approval-wait 가 없음(D44, AW4): {badge_classes}")
        self.assertNotIn("agent-chip", badge_classes, "표지가 실행 칩 클래스를 씀(D44, AW5 — LM12 혼동의 재발)")
        self.assertEqual(report["text"], _BADGE_TEXT, "표지 글자가 「◆승인 대기」가 아님(D44, AW4)")
        self.assertEqual(report["glyphHidden"], "true", "표지 글리프가 aria-hidden 이 아님(D44, AW4)")
        self.assertEqual(report["tooltip"], _BADGE_TOOLTIP, "표지 툴팁이 판정 기준 문구가 아님(D44, AW4)")
        self.assertEqual((report["inMeta"], report["inPct"]), (0, 0), "표지가 식별 줄이나 진행률 줄에 있음(D44, AW3·AW5)")
        tier1 = session.tier1
        self.assertEqual(report["pctElementCount"], 0, "진행률 줄 안에 자식 요소가 있음(D44, LM12)")
        self.assertEqual(report["pctText"], f"{tier1.title} — {tier1.completed}/{tier1.total} · {tier1.percent}%", "진행률 줄 글자가 달라짐(D44, LM12)")
        self.assertEqual(report["runChipCount"], _EXPECTED_RUN_CHIP_COUNTS.get(session.session_id, 0), "서브에이전트 실행 칩 수가 달라짐(D44)")

    def test_d45_badge_adds_no_height_and_stays_on_the_state_badge_line_at_320px(self) -> None:
        # 결정 AW4(안쪽 링 — 실측) — 320px 트랙에서 「대기」 줄에 표지가 붙어도 첫 줄 높이와 상태 배지 중심이 표지 없는 줄과 같다(1px border 였다면 +2px·+1px,
        # 트리 갈고리 정렬 허용치를 소진한다). 「소식 없음 · 직전 대기 + 표지 + 긴 소요」 최악 조합은 시간 글자가 둘째 줄로 감겨도 표지가 상태 배지와 같은
        # 줄에 서고(테두리 없는 「대기」 줄은 top 이 같고, 1px 테두리 「소식 없음」 배지 줄은 baseline 정렬로 1px 까지만 어긋난다) 행이 가로로 넘치지 않는다.
        result = run_scenario(_make_page(_GEOMETRY_SNAPSHOT, _GEOMETRY_PROBE), window_width=1440, window_height=900)
        self.assertAlmostEqual(result["cardWidth"], _TRACK_WIDTH_PX, delta=_GEOMETRY_TOLERANCE_PX, msg="카드 트랙이 320px 가 아님(D45 사전조건)")
        plain, badge, stale_long = result["plain"], result["badge"], result["staleLong"]
        self.assertIsNotNone(badge["approvalTop"], "사전조건: 대기 줄에 표지가 없음(D45)")
        self.assertAlmostEqual(badge["lineHeight"], plain["lineHeight"], delta=_GEOMETRY_TOLERANCE_PX, msg="표지가 붙자 첫 줄 높이가 달라짐(D45, AW4 — border 였다)")
        self.assertAlmostEqual(badge["stateCenter"], plain["stateCenter"], delta=_GEOMETRY_TOLERANCE_PX, msg="표지가 붙자 상태 배지 중심이 움직임(D45, AW4)")
        self.assertAlmostEqual(badge["approvalTop"], badge["stateTop"], delta=_GEOMETRY_TOLERANCE_PX, msg="표지가 상태 배지와 다른 줄에 섬(D45, AW3)")
        self.assertIsNotNone(stale_long["approvalTop"], "사전조건: 소식 없음 줄에 표지가 없음(D45)")
        self.assertAlmostEqual(stale_long["approvalTop"], stale_long["stateTop"], delta=_GEOMETRY_TOLERANCE_PX + _BORDERED_STATE_BADGE_TOP_OFFSET_PX, msg="320px 최악 조합에서 표지가 배지 줄에서 밀려남(D45, AW3)")
        for name, report in (("대기+표지", badge), ("소식 없음+표지+긴 소요", stale_long)):
            self.assertFalse(report["rowOverflows"], f"{name} 줄이 가로로 넘침(D45)")

    def test_d45_poll_that_brings_the_session_back_to_work_removes_the_badge_without_replacing_the_line(self) -> None:
        # 결정 AW3·맞대기(PU1) — 사용자가 답해 세션이 작업중이 된 폴링 응답이면 표지 span 만 지워지고 세션 줄 노드는 같은 노드다.
        result = run_scenario(_make_page(_poll_snapshot("idle", "idle"), _POLL_PROBE), window_width=1440, window_height=900)
        self.assertEqual(result["before"]["badgeCount"], 1, "사전조건: 처음 화면에 표지가 있지 않음(D45)")
        self.assertEqual(result["after"]["badgeCount"], 0, "작업중이 됐는데 표지가 남음(D45)")
        self.assertIn("state-working", result["after"]["stateClass"], "사전조건: 폴링 뒤 세션이 작업중이 아님(D45)")
        self.assertTrue(result["lineNodeKept"], "표지가 사라지며 세션 줄 노드가 갈아 끼워짐(D45 — 맞대기가 깨졌다)")


if __name__ == "__main__":
    unittest.main()
