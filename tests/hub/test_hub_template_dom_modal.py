"""tests/hub/test_hub_template_dom_modal.py — 헤드리스 Chrome DOM 행동 검사 중 M2(카드
상세보기 모달, D8~D17, 승인 2, 결정 SC1~SC17, docs/prps/hub-session-modal-and-partial-update.md
§10.3). 공용 하네스(Chrome 탐색·서버·사전 스크립트·프로브·픽스처 빌더)는
template_dom_harness.py 를 볼 것 — M1(D1~D7)은 test_hub_template_dom.py 에 그대로 남는다
(구현 단계 개정(2026-09-24) — 한 파일이었다면 800줄 상한을 넘는다).

Chrome 이 없으면 SKIP(사유 출력). 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수
있다 — 구현자가 M1 템플릿(카드 상세보기 도입 전)으로 돌려 이 모듈의 시나리오가 실패함
(RED)을 확인하는 용도다.

노드 동일성·앵커 판정은 D1~D7 과 같은 관례를 따른다 — 참조를 액션 전에 잡아 isConnected 로
확인하거나, `data-render-key` 로 같은 세션을 대표하는지 다시 확인한다(D13).
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)
import hub_parse  # noqa: E402  (Tier1Snapshot — D10 픽스처용)
import hub_project  # noqa: E402  (ProjectView — D10 픽스처 반환 타입 표기용)

try:
    from .template_dom_harness import (
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        inject_scripts as _inject_scripts,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document as _minimal_data_document,
        pre_script as _pre_script,
        run_scenario,
        run_scenario_via_file,
        safe_js_string_literal as _safe_js_string_literal,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        inject_scripts as _inject_scripts,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document as _minimal_data_document,
        pre_script as _pre_script,
        run_scenario,
        run_scenario_via_file,
        safe_js_string_literal as _safe_js_string_literal,
    )


def _make_page(snapshot: hub_model.HubSnapshot, probe_body: str) -> str:
    """snapshot 을 실제 템플릿으로 굽고 사전 스크립트·프로브를 끼운다(D1~D7 의 _make_page 와
    같은 역할 — 이 파일은 시나리오마다 다른 기준 스냅샷을 쓰므로 스냅샷을 인자로 받는다)."""
    rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, snapshot)
    return _inject_scripts(rendered, _pre_script(None), probe_body)


def _poll_response_literal(snapshot: hub_model.HubSnapshot) -> str:
    """폴링 대상 스냅샷을 프로브 JS 안에 안전하게 심을 문자열 리터럴로 만든다(D1~D7 의 같은
    패턴 — __triggerPoll 전에 window.__mockFetchResponseText 를 이 값으로 바꿔 끼운다)."""
    return _safe_js_string_literal(_minimal_data_document(snapshot))


# ── 픽스처 — 카드 상세보기 일반 시나리오(D8~D12·D15·D17) ──
# s2·s3 는 dashboard_key 를 가져 모달 세션 카드 클릭이 실제 패널 신원을 만든다. 발췌를 채워
# D1~D7 과 같은 이유로 카드 안 세션 줄 높이를 키운다(레이아웃 사전조건에 영향 없음 — 모달은
# 별도 넘침 계산을 쓴다).
_MODAL_SESSION_S1 = _session("s1", "idle", "idle", BASE_TIME_MS - 5 * 60000, task_excerpt="s1 작업 발췌")
_MODAL_SESSION_S2 = _session(
    "s2", "working", "working", BASE_TIME_MS - 1 * 60000,
    dashboard_key="cafe0000cafe0000", task_excerpt="s2 작업 발췌",
)
_MODAL_SESSION_S3 = _session(
    "s3", "idle", "idle", BASE_TIME_MS - 9 * 60000,
    dashboard_key="babe0000babe0000", task_excerpt="s3 작업 발췌",
)
_MODAL_SNAPSHOT = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "working", (_MODAL_SESSION_S1, _MODAL_SESSION_S2, _MODAL_SESSION_S3)),
    _project("/repo/atlas", "atlas", "idle", (_session("k1", "idle", "idle", BASE_TIME_MS - 20 * 60000),)),
))
# D15 — coding-harness 가 폴링 결과에서 통째로 사라진다(atlas 만 남는다).
_MODAL_SNAPSHOT_PROJECT_GONE = _snapshot((
    _project("/repo/atlas", "atlas", "idle", (_session("k1", "idle", "idle", BASE_TIME_MS - 20 * 60000),)),
))

# ── 픽스처 — 모달 루트는 어떤 경우에도 패널 타깃이 아니다(D10, 결정 MX1). 루트가 눌리던 옛 갈래(보이는 세션 0개·
# 주인 세션이 목록에 없음 — 옛 판정 isRootOnlyDashboardPath)와 눌리지 않던 갈래(주인 세션이 보임·프로젝트
# 대시보드가 없음)에, 끝난 작업 표지가 붙은 갈래까지 덮는다. 정적 4갈래는 프로젝트 넷을 한 스냅샷에 담아 한 번의
# Chrome 실행으로 본다 — 프로젝트마다 보이는 세션 둘을 둬 카드 → 모달 진입 동선은 D8~D9 와 같다. ──
_ROOT_CASE_LABELS = ("owner-visible", "orphan", "no-tier1", "finished-task")
_GONE_OWNER_SESSION_ID = "gone-owner"    # 어느 프로젝트의 세션 목록에도 없는 주인


def _root_case_project(label: str, owner_session_id: str | None, is_finished_task: bool = False) -> hub_project.ProjectView:
    """루트 클릭 시나리오용 프로젝트. label 이 경로·세션 ID 를 가르고, owner_session_id 가 None 이면 프로젝트
    대시보드가 없다. 그 밖에는 프로젝트 대시보드(project.tier1)의 주인 세션 ID 를 준다."""
    sessions = (
        _session(f"{label}-a", "idle", "idle", BASE_TIME_MS - 5 * 60000, task_excerpt=f"{label} 작업"),
        _session(f"{label}-b", "idle", "idle", BASE_TIME_MS - 9 * 60000, task_excerpt=f"{label} 다른 작업"),
    )
    project = _project(f"/repo/{label}", label, "idle", sessions)
    if owner_session_id is None:
        return project
    tier1 = hub_parse.Tier1Snapshot(
        title=f"{label} 진행", subtitle="-", completed=1, total=2, percent=50, steps=(),
        matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
        file_mtime_ms=BASE_TIME_MS, session_id=owner_session_id,
    )
    return dataclasses.replace(
        project, tier=1, tier1=tier1, dashboard_key="feed0000feed0000", tier1_is_finished_task=is_finished_task,
    )


_ROOT_CASES_SNAPSHOT = _snapshot((
    _root_case_project("owner-visible", "owner-visible-a"),
    _root_case_project("orphan", _GONE_OWNER_SESSION_ID),
    _root_case_project("no-tier1", None),
    _root_case_project("finished-task", _GONE_OWNER_SESSION_ID, is_finished_task=True),
))
# D10 — 열린 채 폴링으로 보일 세션이 0개가 된다: 완료 + 발췌 없음 세션만 남으면 화면에서 숨겨진다(결정 V2).
_MODAL_SNAPSHOT_ALL_HIDDEN = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "done", (_session("s1", "done", "done", BASE_TIME_MS - 400 * 60000),)),
    _project("/repo/atlas", "atlas", "idle", (_session("k1", "idle", "idle", BASE_TIME_MS - 20 * 60000),)),
))
# D10 — file:// 모드: 옛 루트는 서버를 켜라는 안내(사유 속성 + 툴팁)를 달았다. 프로젝트 대시보드가 있는데
# 서버가 없는 갈래가 그 안내를 만드는 유일한 분기였다.
_ROOT_FILE_MODE_SNAPSHOT = _snapshot((_root_case_project("orphan", _GONE_OWNER_SESSION_ID),))
_STRIP_EMPTY_TEXT = "화면에 보일 세션이 없습니다."

# D10 프로브 조각(JS) — 세 시나리오가 함께 쓴다. 루트와 자손의 패널 속성, 커서, 제목 태그를 재고 루트·제목을
# 누른 뒤 패널이 열렸는지 본다. % 서식 밖에서 이어붙이므로 퍼센트 기호를 써도 된다.
_ROOT_INSPECT_JS = """
var PANEL_ATTRIBUTES = ['data-project-path', 'data-dashboard-key', 'data-panel-empty-reason'];
async function inspectRoot(settleMs){
  var root = document.querySelector('.session-modal-root');
  var title = document.getElementById('dzh-session-modal-title');
  var elements = [root].concat(Array.prototype.slice.call(root.querySelectorAll('*')));
  var report = {
    panelOpenBefore: document.body.classList.contains('dzh-panel-open'),
    panelAttributeElements: elements.filter(function(el){
      return PANEL_ATTRIBUTES.some(function(name){ return el.hasAttribute(name); });
    }).length,
    rootTooltipAttribute: root.getAttribute('data-tooltip'),
    rootCursor: getComputedStyle(root).cursor,
    titleCursor: getComputedStyle(title).cursor,
    titleTag: title.tagName,
    titleText: title.textContent.trim(),
  };
  __dispatchClick(root);
  await __sleep(settleMs);
  __dispatchClick(title);
  await __sleep(settleMs);
  report.panelOpenAfterClicks = document.body.classList.contains('dzh-panel-open');
  report.rootMarkedOpen = root.classList.contains('card-open');
  report.listCardMarkedOpen = document.querySelector('#dzh-app .card.card-open') !== null;
  return report;
}
"""
# 정적 4갈래 — 카드마다 모달을 열어 루트를 잰 뒤 스크림 클릭으로 닫고(D12a) 다음 프로젝트로 넘어간다.
_ROOT_STATIC_PROBE = """
var labels = %(labels)s;
var results = [];
for(var i = 0; i < labels.length; i++){
  var card = document.querySelector('#dzh-app .card[data-project-path="/repo/' + labels[i] + '"]');
  __dispatchClick(card.querySelector('.path'));
  await __sleep(%(settle)d);
  var report = await inspectRoot(%(settle)d);
  report.label = labels[i];
  results.push(report);
  // 케이스를 서로 격리한다 — 이 케이스의 루트·제목 클릭이 패널을 열었다면(결함 재현) 그 잔재가 다음 케이스의
  // 「이 경우 이전에 패널이 이미 열려 있음」 사전조건 실패로 번져 원인이 흐려진다. 열린 패널은 닫고 넘어간다.
  if(document.body.classList.contains('dzh-panel-open')){
    __dispatchClick(document.getElementById('dzh-detail-close'));
    await __sleep(%(settle)d);
  }
  __dispatchClick(document.getElementById('dzh-session-modal'));
  await __sleep(%(settle)d);
}
__probeResult({results: results});
"""
# 열린 채 폴링 — coding-harness 모달을 연 뒤 그 프로젝트의 세션이 전부 숨김 조건이 되는 스냅샷을 받는다.
_ROOT_POLL_PROBE = """
var card = document.querySelector('#dzh-app .card[data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var sessionCardsBefore = document.querySelectorAll('#dzh-session-modal-body .session-card').length;
window.__mockFetchResponseText = %(poll_snapshot)s;
await __triggerPoll();
var report = await inspectRoot(%(settle)d);
report.sessionCardsBefore = sessionCardsBefore;
report.sessionCardsAfter = document.querySelectorAll('#dzh-session-modal-body .session-card').length;
report.modalStillOpen = document.body.classList.contains('dzh-session-modal-open');
report.bodyText = document.getElementById('dzh-session-modal-body').textContent;
__probeResult({report: report});
"""
_ROOT_FILE_PROBE = """
var card = document.querySelector('#dzh-app .card[data-project-path="/repo/orphan"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
__probeResult({report: await inspectRoot(%(settle)d)});
"""

# ── 픽스처 — 가로 스크롤 시나리오(D13·D14). 6개 세션을 모두 idle 로 두고 last_event_at_ms 를
# 내림차순으로 줘 생성 순서(s1..s6)가 그대로 표시 순서가 되게 한다(정렬 규칙과 뒤섞이지
# 않게 하기 위한 선택 — compareSessionsForDisplay 참고). ──
_SCROLL_SESSIONS = tuple(
    _session(f"s{i}", "idle", "idle", BASE_TIME_MS - i * 60000, task_excerpt=f"세션 {i} 작업 발췌")
    for i in range(1, 7)
)
_SCROLL_SNAPSHOT = _snapshot((_project("/repo/coding-harness", "coding-harness", "idle", _SCROLL_SESSIONS),))
# D13 폴링 대상 — s6 가 working 으로 바뀌어 맨 앞으로 재정렬된다(뒤쪽 세션이 작업중이 되어
# 끼어드는 §2.2 실측 조건 그대로).
_SCROLL_SNAPSHOT_S6_WORKING = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "working", (
        _session("s1", "idle", "idle", BASE_TIME_MS - 1 * 60000, task_excerpt="세션 1 작업 발췌"),
        _session("s2", "idle", "idle", BASE_TIME_MS - 2 * 60000, task_excerpt="세션 2 작업 발췌"),
        _session("s3", "idle", "idle", BASE_TIME_MS - 3 * 60000, task_excerpt="세션 3 작업 발췌"),
        _session("s4", "idle", "idle", BASE_TIME_MS - 4 * 60000, task_excerpt="세션 4 작업 발췌"),
        _session("s5", "idle", "idle", BASE_TIME_MS - 5 * 60000, task_excerpt="세션 5 작업 발췌"),
        _session("s6", "working", "working", BASE_TIME_MS + 60000, task_excerpt="세션 6 작업 발췌"),
    )),
))

# ── 픽스처 — file:// 모드(D16). 세션에 dashboard_key 가 있어도 isServed=false 면
# 클릭 불가 사유로 대체돼야 한다(sessionRowAttributes 의 isClickable 산식). ──
_FILE_MODE_SNAPSHOT = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "idle", (
        _session("s1", "idle", "idle", BASE_TIME_MS - 1 * 60000, dashboard_key="feed0000feed0000", task_excerpt="s1 작업 발췌"),
    )),
))
_FILE_MODE_DASHBOARD_HINT = "허브 서버를 켜면(/hub server start) 카드에서 대시보드를 볼 수 있습니다"

_SETTLE_MS = 30            # __triggerPoll·__fireTick 의 TRIGGER_SETTLE_MS 와 같은 여유
_TRANSITION_SETTLE_MS = 400   # 180ms CSS 전이(패널 밀어내기·모달 열기) + ResizeObserver 콜백 여유


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubSessionModalDomTest(unittest.TestCase):
    """D8~D17(§10.3) — 카드 상세보기 모달이 클릭 계약·ESC 순서·가로 앵커·file:// 사유를 지키는지."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def test_d8a_card_path_click_opens_modal_not_panel(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%d);
__probeResult({
  modalOpen: document.body.classList.contains('dzh-session-modal-open'),
  appInert: document.getElementById('dzh-app').inert,
  focusedIsCloseButton: document.activeElement === document.getElementById('dzh-session-modal-close'),
  panelOpen: document.body.classList.contains('dzh-panel-open'),
});
""" % _SETTLE_MS
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertTrue(result["modalOpen"], "카드 여백 클릭인데 카드 상세보기가 안 열림(D8, 확정 2)")
        self.assertTrue(result["appInert"], "모달 열림 중 #dzh-app 이 inert 가 아님(D8, SC2)")
        self.assertTrue(result["focusedIsCloseButton"], "모달을 열었는데 포커스가 닫기 버튼에 없음(D8, SC13)")
        self.assertFalse(result["panelOpen"], "카드 여백 클릭인데 상세 패널도 함께 열림(D8, 확정 2 위반 — 카드가 여전히 패널 속성을 달고 있을 가능성)")

    def test_d8b_session_row_click_opens_panel_not_modal(self) -> None:
        probe_body = """
var row = document.querySelector('[data-session-id="s2"]');
__dispatchClick(row);
await __sleep(%d);
__probeResult({
  modalOpen: document.body.classList.contains('dzh-session-modal-open'),
  panelOpen: document.body.classList.contains('dzh-panel-open'),
  panelTitle: document.getElementById('dzh-detail-title').textContent,
});
""" % _SETTLE_MS
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertFalse(result["modalOpen"], "세션 줄 클릭인데 카드 상세보기가 열림(D8, 확정 1 위반)")
        self.assertTrue(result["panelOpen"], "세션 줄 클릭인데 상세 패널이 안 열림(D8, 확정 1 — 지름길 유지)")
        self.assertEqual(result["panelTitle"], "coding-harness · 세션 s2")

    def test_d9_modal_session_card_click_opens_panel_and_marks_both(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var modalCard = document.querySelector('#dzh-session-modal-body [data-session-id="s2"]');
__dispatchClick(modalCard);
await __sleep(%(settle)d);
var listRow = document.querySelector('#dzh-app [data-session-id="s2"]');
__probeResult({
  panelTitle: document.getElementById('dzh-detail-title').textContent,
  listRowOpen: listRow.classList.contains('card-open') && listRow.getAttribute('aria-current') === 'true',
  modalCardOpen: modalCard.classList.contains('card-open') && modalCard.getAttribute('aria-current') === 'true',
});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertEqual(result["panelTitle"], "coding-harness · 세션 s2", "모달 세션 카드 클릭이 그 세션의 대시보드를 열지 않음(D9, SC4)")
        self.assertTrue(result["listRowOpen"], "목록 세션 줄에 선택 표시가 없음(D9, SC7 — 신원이 같은 요소 전부)")
        self.assertTrue(result["modalCardOpen"], "모달 세션 카드 자신에 선택 표시가 없음(D9, SC7)")

    def test_d10_modal_root_is_never_a_panel_target_in_any_static_case(self) -> None:
        # ① 결정 MX1 — 카드 상세보기 머리(루트)는 어떤 경우에도 패널 타깃이 아니다. 옛 게이트가 갈랐던 네 갈래
        # (주인 세션 보임 · 주인 세션이 목록에 없음(orphan) · 프로젝트 대시보드 없음 · 끝난 작업)를 한 번에 본다:
        # 루트와 자손에 패널 속성이 없고, 커서가 손가락이 아니며, 제목은 눌리는 버튼이 아니고, 루트·제목을 눌러도
        # 패널이 안 열리고 열림 표시(card-open)가 안 붙는다. 열린 채 폴링으로 세션이 0개가 되는 갈래는 아래 별도 시나리오다.
        probe_body = _ROOT_INSPECT_JS + _ROOT_STATIC_PROBE % {
            "settle": _SETTLE_MS, "labels": json.dumps(list(_ROOT_CASE_LABELS)),
        }
        result = run_scenario(_make_page(_ROOT_CASES_SNAPSHOT, probe_body))
        self.assertEqual([entry["label"] for entry in result["results"]], list(_ROOT_CASE_LABELS), "프로브가 네 갈래를 다 돌지 않음(D10 사전조건)")
        for report in result["results"]:
            with self.subTest(case=report["label"]):
                self._assert_root_is_not_a_panel_target(report, report["label"])

    def test_d10_modal_root_stays_inert_when_polling_leaves_no_visible_session(self) -> None:
        # ①③ 결정 MX1·MX3 — 모달을 연 채 폴링으로 보일 세션이 0개가 되면 모달은 닫히지 않고 빈 문구를 보이되
        # (읽던 화면을 빼앗지 않는다, SC15), 루트는 그때도 패널 타깃이 아니다(옛 게이트의 「세션 0개」 갈래).
        probe_body = _ROOT_INSPECT_JS + _ROOT_POLL_PROBE % {
            "settle": _SETTLE_MS, "poll_snapshot": _poll_response_literal(_MODAL_SNAPSHOT_ALL_HIDDEN),
        }
        report = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))["report"]
        self.assertEqual(report["sessionCardsBefore"], 3, "폴링 전 세션 카드가 3장이 아님(D10 사전조건)")
        self.assertTrue(report["modalStillOpen"], "보일 세션이 0개가 되자 모달이 닫힘(D10, MX3 — 읽던 화면을 빼앗지 않는다)")
        self.assertEqual(report["sessionCardsAfter"], 0, "폴링 뒤에도 세션 카드가 남음(D10 사전조건)")
        self.assertIn(_STRIP_EMPTY_TEXT, report["bodyText"], "세션 0개인데 빈 문구가 없음(D10, MX3)")
        self._assert_root_is_not_a_panel_target(report, "열린 채 폴링으로 세션 0개")

    def test_d10_modal_root_in_file_mode_carries_neither_panel_attribute_nor_server_hint(self) -> None:
        # ① 결정 MX1 — file:// 모드에서 옛 루트는 「서버를 켜면…」 안내(사유 속성 + 툴팁)를 달았다. 이제 루트는
        # 그 안내도 달지 않는다 — 안내는 세션 줄·세션 카드(D16)가 계속 맡는다.
        probe_body = _ROOT_INSPECT_JS + _ROOT_FILE_PROBE % {"settle": _SETTLE_MS}
        report = run_scenario_via_file(_make_page(_ROOT_FILE_MODE_SNAPSHOT, probe_body))["report"]
        self._assert_root_is_not_a_panel_target(report, "file:// 모드")

    def _assert_root_is_not_a_panel_target(self, report: dict, where: str) -> None:
        """모달 루트가 패널 타깃이 아니다(D10, 결정 MX1). where 는 실패 메시지에 실릴 경우 이름이다."""
        where = f"D10, MX1 — {where}"
        self.assertFalse(report["panelOpenBefore"], f"이 경우 이전에 패널이 이미 열려 있음(사전조건 — {where})")
        self.assertEqual(report["panelAttributeElements"], 0, f"루트·자손에 패널 속성이 남음({where})")
        self.assertIsNone(report["rootTooltipAttribute"], f"루트에 file:// 안내 툴팁이 남음({where})")
        self.assertNotEqual(report["rootCursor"], "pointer", f"루트 커서가 손가락 모양임({where})")
        self.assertNotEqual(report["titleCursor"], "pointer", f"루트 제목 커서가 손가락 모양임({where})")
        self.assertNotEqual(report["titleTag"], "BUTTON", f"루트 제목이 눌리는 버튼임({where})")
        self.assertNotEqual(report["titleText"], "", f"루트 제목 글자가 비어 있음(다이얼로그 aria-labelledby 대상 — {where})")
        self.assertFalse(report["panelOpenAfterClicks"], f"루트·제목 클릭이 상세 패널을 엶({where})")
        self.assertFalse(report["rootMarkedOpen"], f"루트에 열림 표시(card-open)가 붙음({where})")
        self.assertFalse(report["listCardMarkedOpen"], f"목록 카드에 열림 표시가 붙음({where})")

    def test_d11_escape_closes_panel_first_then_modal(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
var cardNameButton = card.querySelector('.project-name');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var modalCard = document.querySelector('#dzh-session-modal-body [data-session-id="s2"]');
__dispatchClick(modalCard);
await __sleep(%(settle)d);
var panelOpenBefore = document.body.classList.contains('dzh-panel-open');
var modalOpenBefore = document.body.classList.contains('dzh-session-modal-open');
document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
await __sleep(%(settle)d);
var panelOpenAfterFirstEsc = document.body.classList.contains('dzh-panel-open');
var modalOpenAfterFirstEsc = document.body.classList.contains('dzh-session-modal-open');
document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
await __sleep(%(settle)d);
__probeResult({
  panelOpenBefore: panelOpenBefore, modalOpenBefore: modalOpenBefore,
  panelOpenAfterFirstEsc: panelOpenAfterFirstEsc, modalOpenAfterFirstEsc: modalOpenAfterFirstEsc,
  modalOpenAfterSecondEsc: document.body.classList.contains('dzh-session-modal-open'),
  focusIsCardName: document.activeElement === cardNameButton,
});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertTrue(result["panelOpenBefore"] and result["modalOpenBefore"], "패널·모달이 함께 열리지 않음(사전조건)")
        self.assertFalse(result["panelOpenAfterFirstEsc"], "1차 Esc 가 패널을 닫지 않음(D11, SC8)")
        self.assertTrue(result["modalOpenAfterFirstEsc"], "1차 Esc 에 모달까지 닫힘(D11, SC8 — 패널이 먼저 소비해야 한다)")
        self.assertFalse(result["modalOpenAfterSecondEsc"], "2차 Esc 가 모달을 닫지 않음(D11, SC8)")
        self.assertTrue(result["focusIsCardName"], "모달을 닫은 뒤 포커스가 카드 .project-name 으로 돌아가지 않음(D11, SC13)")

    def test_d12a_scrim_click_closes_modal(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var modalOpenBefore = document.body.classList.contains('dzh-session-modal-open');
__dispatchClick(document.getElementById('dzh-session-modal'));
await __sleep(%(settle)d);
__probeResult({modalOpenBefore: modalOpenBefore, modalOpenAfter: document.body.classList.contains('dzh-session-modal-open')});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertTrue(result["modalOpenBefore"], "사전조건 실패 — 모달이 열리지 않음")
        self.assertFalse(result["modalOpenAfter"], "스크림 클릭이 모달을 닫지 않음(D12, SC4·SC13)")

    def test_d12b_refresh_button_click_does_not_close_modal(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
__dispatchClick(document.getElementById('dzh-refresh'));
await __sleep(%(settle)d);
__probeResult({modalOpenAfter: document.body.classList.contains('dzh-session-modal-open')});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertTrue(result["modalOpenAfter"], "헤더(새로고침) 클릭에 모달이 닫힘(D12, SC4 — 스크림 밖 클릭은 그대로다)")

    def test_d13_poll_reorder_preserves_strip_scroll_anchor(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var strip = document.querySelector('#dzh-session-modal-body .session-strip');
if(!strip) throw new Error('세션 칸을 찾지 못함(사전조건 실패)');
if(strip.scrollWidth <= strip.clientWidth){
  throw new Error('세션 칸이 넘치지 않음(사전조건 실패 — scrollWidth ' + strip.scrollWidth + ' <= clientWidth ' + strip.clientWidth + ')');
}
strip.scrollLeft = 60;
function findAnchor(){
  var stripLeft = strip.getBoundingClientRect().left;
  for(var item = strip.firstElementChild; item; item = item.nextElementSibling){
    var rect = item.getBoundingClientRect();
    if(rect.right > stripLeft) return item;
  }
  return null;
}
var anchorBefore = findAnchor();
var anchorKey = anchorBefore.getAttribute('data-render-key');
var anchorXBefore = anchorBefore.getBoundingClientRect().left;
window.__mockFetchResponseText = %(poll_snapshot)s;
await __triggerPoll();
var anchorAfter = strip.querySelector('[data-render-key="' + anchorKey + '"]');
var hiddenBody = document.getElementById('dzh-session-modal-body');
var hiddenLeftExpected = strip.scrollLeft > 1;
var hiddenRightExpected = (strip.scrollLeft + strip.clientWidth) < (strip.scrollWidth - 1);
__probeResult({
  stripSame: strip.isConnected,
  // 검수 1회차 MEDIUM — !!anchorAfter 는 같은 키로 다시 조회한 요소의 존재만 보므로
  // 노드가 파괴·재생성돼도 참이 된다. D1·D4 관례대로 폴링 전에 잡아 둔 참조
  // (anchorBefore)의 isConnected 와 재조회 결과의 참조 동일성을 함께 본다 — 둘 다
  // 참이어야 "정말 같은 노드"다.
  anchorSame: anchorBefore.isConnected && anchorAfter === anchorBefore,
  anchorXDelta: anchorAfter ? Math.abs(anchorAfter.getBoundingClientRect().left - anchorXBefore) : null,
  hiddenLeftExpected: hiddenLeftExpected, hiddenLeftClass: hiddenBody.classList.contains('session-strip-hidden-left'),
  hiddenRightExpected: hiddenRightExpected, hiddenRightClass: hiddenBody.classList.contains('session-strip-hidden-right'),
});
""" % {
            "settle": _SETTLE_MS,
            "poll_snapshot": _poll_response_literal(_SCROLL_SNAPSHOT_S6_WORKING),
        }
        result = run_scenario(_make_page(_SCROLL_SNAPSHOT, probe_body), window_width=1024)
        self.assertTrue(result["stripSame"], "폴링 뒤 세션 칸이 같은 노드가 아님(D13)")
        self.assertTrue(result["anchorSame"], "폴링 뒤 기준 카드가 같은 노드가 아님(D13, SC9 — 사라졌거나 파괴·재생성됨)")
        self.assertIsNotNone(result["anchorXDelta"], "기준 카드를 다시 찾지 못해 위치를 비교할 수 없음(D13)")
        # 실측(2026-09-24, 스크래치 스크립트로 이 시나리오를 5회 연속 실행): anchorXDelta 는
        # 5회 모두 0 — PRP §10.3 D13 원안의 「보던 카드 x ±1px」를 그대로 채택한다(검수
        # 1회차 LOW — 이전 2 는 원안보다 느슨했다. PRP 는 개정하지 않는다: 이 값은 원안과
        # 어긋나 있던 구현을 원안에 맞춘 것이라 "설계 대비 구현 단계 개정"이 아니다).
        self.assertLessEqual(result["anchorXDelta"], 1, "뒤쪽 세션이 앞으로 끼어들자 보던 카드의 화면 x 가 밀림(D13, SC9)")
        self.assertEqual(result["hiddenLeftClass"], result["hiddenLeftExpected"], "왼쪽 가장자리 흐림 클래스가 실제 스크롤 상태와 어긋남(D13, SC11)")
        self.assertEqual(result["hiddenRightClass"], result["hiddenRightExpected"], "오른쪽 가장자리 흐림 클래스가 실제 스크롤 상태와 어긋남(D13, SC11)")

    def test_d14a_opening_modal_with_panel_already_open_reveals_that_session(self) -> None:
        probe_body = """
var thirdRow = document.querySelector('#dzh-app [data-session-id="s3"]');
__dispatchClick(thirdRow);
await __sleep(%(transition)d);
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var strip = document.querySelector('#dzh-session-modal-body .session-strip');
var targetCard = strip.querySelector('[data-session-id="s3"]');
var stripRect = strip.getBoundingClientRect();
var cardRect = targetCard.getBoundingClientRect();
__probeResult({
  panelOpen: document.body.classList.contains('dzh-panel-open'),
  fullyVisible: cardRect.left >= stripRect.left - 1 && cardRect.right <= stripRect.right + 1,
});
""" % {"transition": _TRANSITION_SETTLE_MS, "settle": _SETTLE_MS}
        result = run_scenario(_make_page(_SCROLL_SNAPSHOT, probe_body), window_width=1024)
        self.assertTrue(result["panelOpen"], "사전조건 실패 — 세션 줄 클릭이 패널을 안 엶")
        self.assertTrue(result["fullyVisible"], "패널에 열려 있던 세션의 카드가 모달을 연 순간 칸 안에 온전히 보이지 않음(D14, SC10-1)")

    def test_d14b_clicking_clipped_modal_card_reveals_it_immediately(self) -> None:
        # 구현 단계 개정(2026-09-24, D1 의 "브라우저가 실제로 보장하는 것만 본다" 선례와 같은
        # 조정) — 원안은 "잘린 카드 클릭 → 패널 밀어내기 → 그 카드가 칸 안에 온전히"까지
        # 한 시나리오로 봤다(SC10-2·SC10-3 동시 검증). 실측(진단 스크립트, 헤드리스 Chrome
        # --virtual-time-budget): ResizeObserver 는 .observe() 호출 시 1회만 발화하고, 그
        # 뒤 패널 밀어내기 CSS 전이가 만드는 실제 폭 변화(908px→440px, 여러 프레임에 걸쳐
        # 진행됨을 별도로 확인)에는 재발화하지 않는다 — 이 헤드리스 모드가 전이 도중의
        # "업데이트 렌더링" 단계를 프레임마다 돌리지 않는 것으로 보인다(§2.2 함정 4 와 같은
        # 계열의 가상 시간·연속 렌더링 간극). 그래서 SC10-2(리사이즈로 재-드러내기)는 이
        # 하네스로 재현할 수 없다 — 실제 브라우저(연속 리사이즈)에서는 ResizeObserver 가
        # 신뢰성 있게 재발화하므로 제품 코드는 바꾸지 않는다(§10.4 수동 확인 대상으로 남긴다).
        # 이 테스트는 SC10-3(클릭 직후 동기 구간의 즉시 드러내기)만 검증한다 — 그 reveal 은
        # revealStripItem 이 클릭 리스너 안에서 동기로 호출되므로 ResizeObserver 와 무관하다
        # (진단 스크립트로 클릭 직후 0ms 시점에 이미 온전히 보임을 확인).
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var strip = document.querySelector('#dzh-session-modal-body .session-strip');
var farCard = strip.querySelector('[data-session-id="s6"]');
var stripRectBefore = strip.getBoundingClientRect();
var farRectBefore = farCard.getBoundingClientRect();
var wasClippedBefore = !(farRectBefore.left >= stripRectBefore.left - 1 && farRectBefore.right <= stripRectBefore.right + 1);
__dispatchClick(farCard);
// 동기 구간 직후 — 패널 밀어내기 CSS 전이가 폭을 바꾸기 전이다.
var stripRectImmediate = strip.getBoundingClientRect();
var farRectImmediate = farCard.getBoundingClientRect();
__probeResult({
  wasClippedBefore: wasClippedBefore,
  panelOpen: document.body.classList.contains('dzh-panel-open'),
  fullyVisibleImmediate: farRectImmediate.left >= stripRectImmediate.left - 1 && farRectImmediate.right <= stripRectImmediate.right + 1,
});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_SCROLL_SNAPSHOT, probe_body), window_width=1024)
        self.assertTrue(result["wasClippedBefore"], "사전조건 실패 — 클릭 대상 카드가 애초에 잘려 있지 않음")
        self.assertTrue(result["panelOpen"], "잘린 세션 카드 클릭이 패널을 열지 않음(D14, SC4)")
        self.assertTrue(result["fullyVisibleImmediate"], "잘린 카드를 누른 직후 칸 안에 온전히 들어오지 않음(D14, SC10-3)")

    def test_d15_project_removed_by_poll_keeps_modal_open_with_reason(self) -> None:
        # labelledbyProbe 는 검수 1회차 MEDIUM 대상 — 다이얼로그(.session-modal-dialog)의
        # aria-labelledby 가 가리키는 요소가 존재하고 글자가 비어 있지 않은지를 정상 열림
        # 상태(Before)와 프로젝트 소실 뒤(After) 양쪽에서 본다. sessionModalBodyHtml(null)
        # 이 본문을 사유 한 줄로 바꾸면 SESSION_MODAL_TITLE_ID 를 달고 있던 프로젝트명
        # 버튼이 함께 사라져, 고치기 전에는 After 쪽이 비게 된다.
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
function labelledbyProbe(){
  var dialogEl = document.querySelector('.session-modal-dialog');
  var id = dialogEl.getAttribute('aria-labelledby');
  var el = document.getElementById(id);
  return {exists: !!el, text: el ? el.textContent.trim() : ''};
}
var labelledbyBefore = labelledbyProbe();
window.__mockFetchResponseText = %(poll_snapshot)s;
await __triggerPoll();
var labelledbyAfter = labelledbyProbe();
__probeResult({
  modalOpenAfter: document.body.classList.contains('dzh-session-modal-open'),
  bodyText: document.getElementById('dzh-session-modal-body').textContent,
  labelledbyExistsBefore: labelledbyBefore.exists, labelledbyTextBefore: labelledbyBefore.text,
  labelledbyExistsAfter: labelledbyAfter.exists, labelledbyTextAfter: labelledbyAfter.text,
});
""" % {"settle": _SETTLE_MS, "poll_snapshot": _poll_response_literal(_MODAL_SNAPSHOT_PROJECT_GONE)}
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body))
        self.assertTrue(result["modalOpenAfter"], "열린 프로젝트가 스냅샷에서 사라지자 모달이 닫힘(D15, SC15 — 닫지 않아야 한다)")
        self.assertIn("이 프로젝트는 최신 목록에 없습니다", result["bodyText"], "사라진 프로젝트 사유 문구가 없음(D15, SC15)")
        self.assertTrue(result["labelledbyExistsBefore"], "정상 열림 상태에서 aria-labelledby 가 가리키는 요소가 없음(D15 사전조건)")
        self.assertNotEqual(result["labelledbyTextBefore"], "", "정상 열림 상태에서 aria-labelledby 가 가리키는 요소의 글자가 비어 있음(D15 사전조건)")
        self.assertTrue(result["labelledbyExistsAfter"], "열린 프로젝트가 사라진 뒤 aria-labelledby 가 가리키는 요소가 없음(D15, 검수 1회차 MEDIUM — 다이얼로그의 접근 가능한 이름이 끊김)")
        self.assertNotEqual(result["labelledbyTextAfter"], "", "열린 프로젝트가 사라진 뒤 aria-labelledby 가 가리키는 요소의 글자가 비어 있음(D15, 검수 1회차 MEDIUM)")

    def test_d16_file_mode_shows_panel_empty_reason_on_modal_session_card(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var modalCard = document.querySelector('#dzh-session-modal-body [data-session-id="s1"]');
var hasReason = modalCard.hasAttribute('data-panel-empty-reason');
var hasKey = modalCard.hasAttribute('data-dashboard-key');
__dispatchClick(modalCard);
await __sleep(%(settle)d);
__probeResult({
  modalOpen: document.body.classList.contains('dzh-session-modal-open'),
  hasReason: hasReason, hasKey: hasKey,
  panelEmpty: document.getElementById('dzh-detail-panel').classList.contains('detail-empty'),
  emptyReasonText: document.getElementById('dzh-detail-empty-reason').textContent,
});
""" % {"settle": _SETTLE_MS}
        page = _make_page(_FILE_MODE_SNAPSHOT, probe_body)
        result = run_scenario_via_file(page)
        self.assertTrue(result["modalOpen"], "file:// 모드에서 카드 여백 클릭이 모달을 안 엶(D16, T25-235 — GOTCHA)")
        self.assertTrue(result["hasReason"], "file:// 모드인데 모달 세션 카드에 data-panel-empty-reason 이 없음(D16)")
        self.assertFalse(result["hasKey"], "file:// 모드인데 모달 세션 카드가 여전히 data-dashboard-key 를 닮(D16, isClickable 산식 위반)")
        self.assertTrue(result["panelEmpty"], "file:// 모드에서 세션 카드를 눌렀는데 패널이 빈 상태가 아님(D16)")
        self.assertEqual(result["emptyReasonText"], _FILE_MODE_DASHBOARD_HINT)

    def test_d17_narrow_viewport_panel_covers_modal_and_returns_on_close(self) -> None:
        probe_body = """
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
var modalCard = document.querySelector('#dzh-session-modal-body [data-session-id="s2"]');
__dispatchClick(modalCard);
await __sleep(%(settle)d);
var wrapInertDuring = document.querySelector('.wrap').inert;
var panelOpenDuring = document.body.classList.contains('dzh-panel-open');
document.getElementById('dzh-detail-close').dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
await __sleep(%(settle)d);
__probeResult({
  wrapInertDuring: wrapInertDuring, panelOpenDuring: panelOpenDuring,
  wrapInertAfter: document.querySelector('.wrap').inert,
  modalOpenAfter: document.body.classList.contains('dzh-session-modal-open'),
  focusIsModalCard: document.activeElement === modalCard,
});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_MODAL_SNAPSHOT, probe_body), window_width=820)
        self.assertTrue(result["panelOpenDuring"], "좁은 화면에서 모달 세션 카드 클릭이 패널을 안 엶(D17)")
        self.assertTrue(result["wrapInertDuring"], "좁은 화면에서 패널이 열렸는데 .wrap(모달 포함)이 inert 가 아님(D17, SC14·SC1-③)")
        self.assertFalse(result["wrapInertAfter"], "패널을 닫았는데 .wrap 이 여전히 inert(D17)")
        self.assertTrue(result["modalOpenAfter"], "패널을 닫자 카드 상세보기까지 닫힘(D17, SC14 — 모달은 유지돼야 한다)")
        self.assertTrue(result["focusIsModalCard"], "패널을 닫은 뒤 포커스가 그 세션 카드로 돌아가지 않음(D17, SC13)")


if __name__ == "__main__":
    unittest.main()
