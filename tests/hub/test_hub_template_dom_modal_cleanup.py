"""tests/hub/test_hub_template_dom_modal_cleanup.py — 헤드리스 Chrome DOM 행동 검사 중 카드 상세보기
정리 7건(D18~D24, docs/prps/hub-session-modal-cleanup.md §10.3, 결정 MX14).

이 모듈은 마일스톤마다 자란다 — 시나리오는 아래 한 클래스에 메서드로, 시나리오가 굽는 스냅샷은
「픽스처」 절에 더한다(M1 D23 · M2 D24 · M3 D18·D19 · M4 D20~D22). 지금 들어 있는 것은 D18~D24 전부다.
D10(모달 루트는 어떤 경우에도 패널 타깃이 아니다)은 기존 test_hub_template_dom_modal.py 의 것을
고쳐 썼고, 그 파일이 800줄 상한에 닿기 전에 이 모듈이 새 시나리오를 받는다. 공용 하네스(Chrome 탐색·
서버·사전 스크립트·프로브·픽스처 빌더)는 template_dom_harness.py 를 볼 것 — 하네스는 무변경이고,
세션·실행처럼 풍부한 픽스처는 이 모듈 안에서 dataclasses.replace 로 만든다(D10 선례).

Chrome 이 없으면 SKIP(사유 출력). 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 —
변경 전 템플릿으로 돌려 이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_parse  # noqa: E402  (sys.path 조정 후 임포트 — Tier1Snapshot, D24 픽스처용)
import hub_project  # noqa: E402  (ProjectView — D24 픽스처 반환 타입 표기용)
import hub_session  # noqa: E402  (SubagentRunView — D23 픽스처용)
import hub_usage  # noqa: E402  (UsageSample — D21 사용량 패널 변형 픽스처용)

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
# 클릭 뒤 동기 렌더가 끝나길 기다리는 짧은 여유 — 폴링·틱 트리거의 TRIGGER_SETTLE_MS(200)와는 별개 값이다.
_SETTLE_MS = 30


def _agent_run(
    agent_id: str, agent_type: str, phase: hub_session.Phase | None, is_running: bool, minutes_ago: int, title: str,
) -> hub_session.SubagentRunView:
    """서브에이전트 실행 1건. 끝난 실행은 시작 _ENDED_RUN_DURATION_MINUTES 분 뒤에 끝난 것으로 둔다."""
    started_at_ms = BASE_TIME_MS - minutes_ago * _MS_PER_MINUTE
    ended_at_ms = None if is_running else started_at_ms + _ENDED_RUN_DURATION_MINUTES * _MS_PER_MINUTE
    return hub_session.SubagentRunView(
        agent_id=agent_id, agent_type=agent_type, phase=phase, is_running=is_running,
        started_at_ms=started_at_ms, ended_at_ms=ended_at_ms, title=title, model="sonnet",
    )


def _progress(title: str, owner_session_id: str | None) -> hub_parse.Tier1Snapshot:
    """진행률 스냅샷 하나 — 「1/2 · 50%」. 제목이 서로 달라 화면 글자로 어느 진행률인지 가려낼 수 있다."""
    return hub_parse.Tier1Snapshot(
        title=title, subtitle="-", completed=1, total=2, percent=50, steps=(),
        matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
        file_mtime_ms=BASE_TIME_MS, session_id=owner_session_id,
    )


# ── 픽스처 — D23(⑦ 실행중 칩 글리프 제거) ──
# 실행중 3(검수)·종료 1(구현). 카드 세션 줄과 모달 세션 카드가 같은 실행 줄 렌더를 쓰므로 한 세션이
# 두 화면을 모두 덮는다. 매핑 없는 타입의 칩(agent_type 으로 폴백)도 실행중일 수 있어 한 건은 폴백으로 둔다.
_RUN_CHIP_SESSION = dataclasses.replace(
    _session("s1", "working", "working", BASE_TIME_MS - 1 * _MS_PER_MINUTE, task_excerpt="실행 줄 칩 확인용 작업"),
    agent_runs=(
        _agent_run("r1", "code-reviewer", "검수", True, 3, "검수 ① 엔진 회귀"),
        _agent_run("r2", "code-reviewer", "검수", True, 3, "검수 ② 보안"),
        _agent_run("r3", "custom-checker", None, True, 4, "매핑 없는 타입의 실행"),
        _agent_run("r4", "implementer", "구현", False, 20, "구현 M1"),
    ),
)
_RUN_CHIP_SNAPSHOT = _snapshot((_project("/repo/coding-harness", "coding-harness", "working", (_RUN_CHIP_SESSION,)),))

# ── 픽스처 — D24(④ 카드·모달 루트의 프로젝트 단위 진행률 제거) ──
# 프로젝트마다 프로젝트 단위 진행률(project.tier1)과 세션 자기 진행률(session.tier1)을 **서로 다른 제목**으로
# 싣는다. 세 프로젝트가 프로젝트 진행률에 붙던 세 갈래를 나눠 맡는다 — 주인 세션이 목록에 있다 · 주인 세션이
# 목록에 없다(orphan) · 이전 작업 표지(tier1_is_previous_task). 세션은 프로젝트마다 둘이고 하나만 자기
# 진행률을 갖는다(자기 진행률이 프로젝트 진행률에 섞여 세지는 일을 막는다).
_PROJECT_PROGRESS_TITLE = "프로젝트 단위 진행률"
_SESSION_PROGRESS_TITLE = "세션 자기 진행률"
_GONE_OWNER_SESSION_ID = "gone-owner"    # 어느 프로젝트의 세션 목록에도 없는 주인


def _progress_project(label: str, owner_session_id: str, is_previous_task: bool = False) -> hub_project.ProjectView:
    """진행률이 두 층(프로젝트·세션)에 다 있는 프로젝트. label 이 경로·세션 ID·진행률 제목을 가른다."""
    session_with_progress = dataclasses.replace(
        _session(f"{label}-a", "idle", "idle", BASE_TIME_MS - 5 * _MS_PER_MINUTE, task_excerpt=f"{label} 작업 발췌"),
        tier1=_progress(f"{_SESSION_PROGRESS_TITLE} {label}", f"{label}-a"), dashboard_key="cafe0000cafe0000",
    )
    session_without_progress = _session(
        f"{label}-b", "idle", "idle", BASE_TIME_MS - 9 * _MS_PER_MINUTE, task_excerpt=f"{label} 다른 작업",
    )
    return dataclasses.replace(
        _project(f"/repo/{label}", label, "idle", (session_with_progress, session_without_progress)),
        tier=1, tier1=_progress(f"{_PROJECT_PROGRESS_TITLE} {label}", owner_session_id),
        dashboard_key="feed0000feed0000", tier1_is_previous_task=is_previous_task,
    )


_PROJECT_PROGRESS_LABELS = ("owner-visible", "orphan", "previous-task")
_PROJECT_PROGRESS_SNAPSHOT = _snapshot((
    _progress_project("owner-visible", "owner-visible-a"),
    _progress_project("orphan", _GONE_OWNER_SESSION_ID),
    _progress_project("previous-task", "previous-task-a", is_previous_task=True),
))
# 프로젝트마다 카드 목록 → 카드 상세보기 머리 순으로 프로젝트 단위 진행률의 흔적과 세션 자기 진행률을 잰다.
# 스크림 클릭으로 모달을 닫고(D12a) 다음 프로젝트로 넘어간다. 채우는 자리: settle(ms)·labels(JSON 배열)·
# project_title(JSON 문자열) — % 서식이라 JS 안의 퍼센트 기호는 쓰지 않는다.
_PROJECT_PROGRESS_PROBE = """
var PROJECT_LEVEL_LINES = ':scope > .tier1-pct, :scope > .tier1-impl';
function textsOf(scope, selector){
  return Array.prototype.map.call(scope.querySelectorAll(selector), function(el){ return el.textContent; });
}
function projectProgressReport(scope, label){
  var projectTitle = %(project_title)s + ' ' + label;
  return {
    projectLevelLines: scope.querySelectorAll(PROJECT_LEVEL_LINES).length,
    labelChips: scope.querySelectorAll('.tier1-prev-label').length,
    hasProjectTitle: scope.textContent.indexOf(projectTitle) !== -1,
    hasPreviousText: scope.textContent.indexOf('이전 작업') !== -1,
    hasOrphanText: scope.textContent.indexOf('주인 세션 없음') !== -1,
    scopeAttributes: scope.hasAttribute('data-tier1-previous') || scope.hasAttribute('data-tier1-orphan'),
  };
}
var labels = %(labels)s;
var results = [];
for(var i = 0; i < labels.length; i++){
  var label = labels[i];
  var card = document.querySelector('#dzh-app .card[data-project-path="/repo/' + label + '"]');
  var listReport = projectProgressReport(card, label);
  listReport.sessionProgressTexts = textsOf(card, '.session-tier1 .tier1-pct');
  __dispatchClick(card.querySelector('.path'));
  await __sleep(%(settle)d);
  var modalBody = document.getElementById('dzh-session-modal-body');
  var modalReport = projectProgressReport(modalBody.querySelector('.session-modal-root'), label);
  modalReport.sessionProgressTexts = textsOf(modalBody, '.session-card .session-tier1 .tier1-pct');
  __dispatchClick(document.getElementById('dzh-session-modal'));
  await __sleep(%(settle)d);
  results.push({
    label: label, list: listReport, modal: modalReport,
    modalClosed: !document.body.classList.contains('dzh-session-modal-open'),
  });
}
__probeResult({results: results});
"""

# ── 픽스처 — D18·D19(② 보일 세션이 없는 카드는 카드 상세보기를 열지 않는다) ──
# 보일 세션이 있는 카드 둘 사이에 「보일 세션이 0개인 카드」(daily-brief)를 끼운다 — 그 프로젝트의 유일한 세션이
# 완료 + 발췌 없음이라 화면에서 숨겨진다(결정 V2). project.sessions 는 비어 있지 않다: 세션이 없는 게 아니라 「보일」
# 세션이 없다(PRP §1.2 ②). 저장된 순서가 없으면 카드 순서는 스냅샷 순서 그대로다.
_EMPTY_CARD_PATH = "/repo/daily-brief"
_FULL_CARD_PATH = "/repo/coding-harness"
_EMPTY_CARD_SNAPSHOT = _snapshot((
    _project(_FULL_CARD_PATH, "coding-harness", "idle",
             (_session("c1", "idle", "idle", BASE_TIME_MS - 5 * _MS_PER_MINUTE, task_excerpt="coding-harness 작업"),)),
    _project(_EMPTY_CARD_PATH, "daily-brief", "done", (_session("e1", "done", "done", BASE_TIME_MS - 300 * _MS_PER_MINUTE),)),
    _project("/repo/atlas", "atlas", "idle",
             (_session("k1", "idle", "idle", BASE_TIME_MS - 20 * _MS_PER_MINUTE, task_excerpt="atlas 작업"),)),
))
_EMPTY_CARD_ORDER = ["/repo/coding-harness", _EMPTY_CARD_PATH, "/repo/atlas"]
# D18 프로브 — 카드 하나의 표지·제목·커서를 재고, 여백(카드 자신)·경로·제목을 차례로 눌러 모달이 열렸는지 본다.
# 열렸으면 스크림 클릭으로 닫고(D12a) 다음 클릭으로 넘어간다. 채우는 자리: settle(ms)·empty·full(경로).
# 카드는 data-project-path 가 아니라 data-render-key(같은 경로 값)로 찾는다 — 검사 대상인 그 속성이 사라진 카드도
# 찾아야 hasProjectPath 단언(「드래그·순서 저장에서 빠진다」)에 닿는다. 셀렉터를 data-project-path 로 두면
# 조회가 null 이 돼 프로브가 TypeError 로 죽고, 설계된 단언이 아니라 원인 없는 오류만 남는다.
_EMPTY_CARD_CLICK_PROBE = """
async function clickOutcome(target){
  __dispatchClick(target);
  await __sleep(%(settle)d);
  var outcome = {modalOpen: document.body.classList.contains('dzh-session-modal-open'),
                 appInert: document.getElementById('dzh-app').inert};
  if(outcome.modalOpen){
    __dispatchClick(document.getElementById('dzh-session-modal'));
    await __sleep(%(settle)d);
  }
  return outcome;
}
async function inspectCard(path){
  var card = document.querySelector('#dzh-app .card[data-render-key="' + path + '"]');
  var title = card.querySelector('.project-name');
  return {
    opener: card.getAttribute('data-opens-session-modal'),
    hasProjectPath: card.hasAttribute('data-project-path'),
    titleTag: title.tagName,
    titlePopup: title.getAttribute('aria-haspopup'),
    cardCursor: getComputedStyle(card).cursor,
    titleCursor: getComputedStyle(title).cursor,
    margin: await clickOutcome(card),
    path: await clickOutcome(card.querySelector('.path')),
    title: await clickOutcome(card.querySelector('.project-name')),
  };
}
__probeResult({empty: await inspectCard('%(empty)s'), full: await inspectCard('%(full)s')});
"""
# D19 프로브 — 합성 DragEvent 로 빈 카드의 핸들을 잡아 맨 앞 카드 위에 놓는다(dragstart → dragover → drop →
# dragend, 실제 드래그와 같은 순서). 채우는 자리: settle(ms)·empty(경로). D18 과 같은 이유로 카드는
# data-render-key 로 찾고 순서도 그 값으로 읽는다 — data-project-path 를 잃은 카드는 드래그에서 빠져 순서가
# 안 바뀌는데(그 실패가 단언에 닿는다), 순서를 그 속성으로 읽으면 사전조건 실패로 원인이 흐려진다.
_EMPTY_CARD_DRAG_PROBE = """
function dragEvent(type){
  return new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: new DataTransfer()});
}
var app = document.getElementById('dzh-app');
function cardOrder(){
  return Array.prototype.map.call(app.querySelectorAll(':scope > .card'), function(card){ return card.getAttribute('data-render-key'); });
}
var before = cardOrder();
var emptyCard = app.querySelector('.card[data-render-key="%(empty)s"]');
var emptyCardHasProjectPath = emptyCard.hasAttribute('data-project-path');
var emptyCardCursor = getComputedStyle(emptyCard).cursor;
var firstCard = app.querySelector('.card');
var handle = emptyCard.querySelector('.card-drag-handle');
handle.dispatchEvent(dragEvent('dragstart'));
firstCard.dispatchEvent(dragEvent('dragover'));
firstCard.dispatchEvent(dragEvent('drop'));
handle.dispatchEvent(dragEvent('dragend'));
await __sleep(%(settle)d);
var stored = null;
try{ stored = JSON.parse(localStorage.getItem('dzh-project-order')); }catch(error){}
var emptyCardAfter = app.querySelector('.card[data-render-key="%(empty)s"]');
__probeResult({
  before: before, after: cardOrder(), stored: stored, emptyCardCursor: emptyCardCursor,
  emptyCardHasProjectPath: emptyCardHasProjectPath,
  emptyCardOpensModal: emptyCardAfter.hasAttribute('data-opens-session-modal'),
  modalOpen: document.body.classList.contains('dzh-session-modal-open'),
  draggingLeft: document.querySelectorAll('.card-dragging').length,
});
"""

# ── 픽스처 — D20·D21(③⑤ 연결선 기하 · 창 높이와 카드 폭) ──
# 세션이 하나뿐인 프로젝트(only-child — 버스가 없다)와 다섯인 프로젝트(1440·1024 어디서나 카드 상세보기의 칸이
# 가로로 스크롤된다)를 한 스냅샷에 담는다. 세션은 전부 idle 이고 시작 시각이 내림차순이라 만든 순서가 곧 표시 순서다.
_SOLO_PATH = "/repo/solo"
_WIDE_PATH = "/repo/wide"
_GEOMETRY_TOLERANCE_PX = 0.5      # PRP §1.1 ③ 의 등식 허용 오차(서브픽셀 반올림)
_DIALOG_MARGIN_PX = 16            # 결정 LM8 — 오버레이의 아래 여백(사용량 패널과 무관한 고정값). 넘칠 때 창의 최대 높이가 영역보다 낮은 만큼
_DIALOG_TOP_FRACTION = 0.125      # 결정 LM8 재재개정 — 창 윗변 = 영역(헤더 아래 ~ 화면 아래 16px) 윗변에서 영역 높이의 12.5% 아래
_EMPTY_STATE_GAP_PX = 9           # M3 — 세션 0개인 채 열려 있을 때 머리 경로와 빈 문구 사이(옛 루트 아랫 패딩 8 + 테두리 1)
_CONNECTOR_VIEWPORTS = ((1440, 900), (1024, 900), (820, 700))    # 밀어내기 여부와 무관한, 카드 상세보기만 열린 세 폭(세션 카드 폭이 3열·3열·2열 산식인 폭)


def _plain_sessions(label: str, count: int) -> tuple[hub_session.SessionView, ...]:
    """발췌만 있는 idle 세션 count 개. label 이 세션 ID·발췌를 가른다."""
    return tuple(
        _session(f"{label}-{index}", "idle", "idle", BASE_TIME_MS - index * _MS_PER_MINUTE, task_excerpt=f"{label} 세션 {index} 작업 발췌")
        for index in range(1, count + 1)
    )


_LAYOUT_SNAPSHOT = _snapshot((
    _project(_SOLO_PATH, "solo", "idle", _plain_sessions("solo", 1)),
    _project(_WIDE_PATH, "wide", "idle", _plain_sessions("wide", 5)),
))
_LAYOUT_USAGE_SNAPSHOT = dataclasses.replace(
    _LAYOUT_SNAPSHOT,
    usage=hub_usage.UsageSample(sampled_at_ms=BASE_TIME_MS - 4 * _MS_PER_MINUTE, session_percent=64, weekly_percent=44),
)
# D21 「빈 상태 간격」 — 열린 채 폴링으로 보일 세션이 0개가 되는 갈래(완료 + 발췌 없음 세션만 남으면 숨겨진다, 결정 V2).
_GAP_PATH = "/repo/gap"
_GAP_OPEN_SNAPSHOT = _snapshot((_project(_GAP_PATH, "gap", "idle", _plain_sessions("gap", 2)),))
_GAP_HIDDEN_SNAPSHOT = _snapshot((
    _project(_GAP_PATH, "gap", "done", (_session("gap-1", "done", "done", BASE_TIME_MS - 400 * _MS_PER_MINUTE),)),
))

# ── 픽스처 — D21(1024×560 에서 내용이 가용 높이를 넘는다)·D22(⑥ 잘림 해제) ──
# 긴 진행률 제목과 긴 실행 줄 제목(둘째는 통째로 끊을 곳 없는 토큰)을 가진 세션 하나와 평범한 세션 하나. 실행 줄이 셋(실행중 2·
# 종료 1)이고 진행률 제목이 여러 줄로 접혀, 모달 세션 카드가 1024×560 의 가용 높이를 넘긴다. 진행중 단계명은 진행률 줄 앞 칩이고
# 그 직전 기록 요약은 툴팁이라 화면 글자가 아니다(결정 LM4·LM5).
_LONG_PATH = "/repo/long"
_LONG_SESSION_ID = "long-1"
_LONG_RUN_TITLE_TOKEN = "verify_hub_template_session_modal_layout_regressions_across_viewports_and_scroll_positions"
_LONG_PROGRESS_TITLE = "연결선 기하를 단일 출처로 묶고 창 높이와 카드 폭을 키운다 — 가로 스크롤 뒤 T 자 접합과 세로 넘침 경로를 실측하고 긴 제목이 두 화면에서 모두 줄바꿈되는지 본다 — 창 최대 높이를 넘겨 다이얼로그만 스크롤하는 경로까지 이어서 확인하고 칸과 카드가 줄어들지 않는지도 함께 본다"
_LONG_PROGRESS = dataclasses.replace(
    _progress(_LONG_PROGRESS_TITLE, _LONG_SESSION_ID),
    steps=(
        hub_parse.StepView(index=1, name="설계", state="done", detail="", started_at=None),
        hub_parse.StepView(index=2, name="구현", state="active", detail="직전 기록 요약", started_at=None),
        hub_parse.StepView(index=3, name="검수", state="wait", detail="", started_at=None),
    ),
    total=3, percent=33,
)
_LONG_SESSION = dataclasses.replace(
    _session(_LONG_SESSION_ID, "working", "working", BASE_TIME_MS - 1 * _MS_PER_MINUTE, task_excerpt="긴 진행률 제목과 긴 실행 제목을 가진 세션"),
    agent_runs=(
        _agent_run("l1", "code-reviewer", "검수", True, 3, "검수 ④ 스펙 적합성·완료 기준 — 설계 문서 대비 누락 항목 전수 대조"),
        _agent_run("l2", "code-reviewer", "검수", True, 3, _LONG_RUN_TITLE_TOKEN),
        _agent_run("l3", "implementer", "구현", False, 40, "구현 M4 (연결선·높이·폭·잘림)"),
    ),
    tier1=_LONG_PROGRESS,
)
_LONG_SNAPSHOT = _snapshot((_project(_LONG_PATH, "long", "working", (_LONG_SESSION,) + _plain_sessions("long", 1)),))

# D20 프로브 — 프로젝트마다 카드 상세보기를 열어 줄기·드롭·버스의 좌표를 칸의 스크롤 시작과 끝에서 잰다. 의사요소의
# 자리는 getComputedStyle(요소, '::after') 의 left/top/height(사용자 정의 속성이 풀린 px)에 호스트 상자의 좌표를
# 더해 구한다. 버스의 양끝은 첫 카드의 버스 왼끝(busLeft)과 끝 카드의 버스 오른끝(busRight)이고, 각각이 닿아야 할
# 곳은 첫 드롭 x(dropX)와 끝 드롭 x(lastDropX)다. 버스는 카드마다 조각(busPieces — 카드 순서대로 왼끝·오른끝)으로
# 그려져 이웃 조각이 이어져야 한다. 채우는 자리: settle(ms)·paths(JSON 배열).
_CONNECTOR_PROBE = """
function px(value){ var n = parseFloat(value); return isNaN(n) ? null : n; }
function connectorGeometry(){
  var root = document.querySelector('.session-modal-root');
  var strip = document.querySelector('#dzh-session-modal-body .session-strip');
  var firstItem = strip.firstElementChild, lastItem = strip.lastElementChild;
  var rootRect = root.getBoundingClientRect();
  var firstRect = firstItem.getBoundingClientRect(), lastRect = lastItem.getBoundingClientRect();
  var stemStyle = getComputedStyle(root, '::after');
  var dropStyle = getComputedStyle(firstItem, '::before');
  var lastDropStyle = getComputedStyle(lastItem, '::before');
  var firstBusStyle = getComputedStyle(firstItem, '::after');
  var lastBusStyle = getComputedStyle(lastItem, '::after');
  var dropTop = firstRect.top + px(dropStyle.top);
  return {
    scrollLeft: strip.scrollLeft, canScroll: strip.scrollWidth > strip.clientWidth,
    rootLeft: rootRect.left, firstCardLeft: firstRect.left,
    stemX: rootRect.left + root.clientLeft + px(stemStyle.left),
    stemBottom: rootRect.top + root.clientTop + px(stemStyle.top) + px(stemStyle.height),
    dropX: firstRect.left + px(dropStyle.left), lastDropX: lastRect.left + px(lastDropStyle.left),
    dropTop: dropTop, dropBottom: dropTop + px(dropStyle.height), cardTop: firstRect.top,
    busHidden: firstBusStyle.display === 'none',
    busTop: firstRect.top + px(firstBusStyle.top),
    busLeft: firstRect.left + px(firstBusStyle.left),
    busRight: lastRect.left + px(lastBusStyle.left) + px(lastBusStyle.width),
    busPieces: Array.prototype.map.call(strip.children, function(item){
      var pieceStyle = getComputedStyle(item, '::after');
      var pieceLeft = item.getBoundingClientRect().left + px(pieceStyle.left);
      return {left: pieceLeft, right: pieceLeft + px(pieceStyle.width)};
    }),
  };
}
var paths = %(paths)s;
var results = [];
for(var i = 0; i < paths.length; i++){
  var card = document.querySelector('#dzh-app .card[data-project-path="' + paths[i] + '"]');
  __dispatchClick(card.querySelector('.path'));
  await __sleep(%(settle)d);
  var strip = document.querySelector('#dzh-session-modal-body .session-strip');
  var atStart = connectorGeometry();
  strip.scrollLeft = strip.scrollWidth - strip.clientWidth;
  await __sleep(%(settle)d);
  results.push({path: paths[i], atStart: atStart, atEnd: connectorGeometry()});
  __dispatchClick(document.getElementById('dzh-session-modal'));
  await __sleep(%(settle)d);
}
__probeResult({results: results});
"""
# D21 프로브 — 프로젝트마다 카드 상세보기를 열어 모달 영역·다이얼로그·칸·세션 카드 li 의 크기를 잰다.
# 채우는 자리: settle(ms)·paths(JSON 배열).
_DIALOG_SIZE_PROBE = """
function px(value){ var n = parseFloat(value); return isNaN(n) ? null : n; }
async function measureDialog(path){
  var card = document.querySelector('#dzh-app .card[data-project-path="' + path + '"]');
  __dispatchClick(card.querySelector('.path'));
  await __sleep(%(settle)d);
  var modal = document.getElementById('dzh-session-modal');
  var dialog = document.querySelector('.session-modal-dialog');
  var strip = document.querySelector('#dzh-session-modal-body .session-strip');
  var dialogRect = dialog.getBoundingClientRect(), stripRect = strip.getBoundingClientRect();
  var dialogStyle = getComputedStyle(dialog), stripStyle = getComputedStyle(strip);
  var modalRect = modal.getBoundingClientRect();
  var report = {
    path: path,
    modalHeight: modalRect.height,
    dialogHeight: dialogRect.height,
    gapAbove: dialogRect.top - modalRect.top,
    gapBelow: modalRect.bottom - dialogRect.bottom,
    dialogScroll: {scroll: dialog.scrollHeight, client: dialog.clientHeight},
    stripScroll: {scroll: strip.scrollHeight, client: strip.clientHeight},
    stripContentHeight: strip.clientHeight - px(stripStyle.paddingTop) - px(stripStyle.paddingBottom),
    gapBelowStrip: dialogRect.bottom - px(dialogStyle.borderBottomWidth) - px(dialogStyle.paddingBottom) - stripRect.bottom,
    items: Array.prototype.map.call(strip.children, function(item){
      return {height: item.getBoundingClientRect().height};
    }),
    clippedCards: Array.prototype.filter.call(strip.querySelectorAll('.session-card'), function(sessionCard){
      return sessionCard.scrollHeight - sessionCard.clientHeight > 1;
    }).length,
  };
  __dispatchClick(modal);
  await __sleep(%(settle)d);
  return report;
}
var paths = %(paths)s;
var results = [];
for(var i = 0; i < paths.length; i++) results.push(await measureDialog(paths[i]));
__probeResult({results: results});
"""
# D21 프로브 — 카드 상세보기를 연 채 폴링으로 보일 세션이 0개가 된 뒤 머리 경로 아랫변에서 빈 문구 윗변까지의 간격.
# 채우는 자리: settle(ms)·path·poll_snapshot(JS 문자열 리터럴).
_EMPTY_STATE_GAP_PROBE = """
var card = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
window.__mockFetchResponseText = %(poll_snapshot)s;
await __triggerPoll();
var empty = document.querySelector('#dzh-session-modal-body .session-strip-empty');
var rootPath = document.querySelector('.session-modal-root .path');
__probeResult({
  modalOpen: document.body.classList.contains('dzh-session-modal-open'),
  emptyText: empty.textContent,
  pathToEmptyPhrase: empty.getBoundingClientRect().top - rootPath.getBoundingClientRect().bottom,
});
"""
# D22 프로브 — 같은 세션의 카드 목록 줄과 카드 상세보기 세션 카드에서 진행률 줄(.tier1-pct)과 실행 줄 제목
# (.agent-run-title)의 넘침·줄 수·줄바꿈 규칙을 잰다. 줄 수는 보이는 높이 ÷ 줄 높이다. 채우는 자리: settle(ms)·path·session.
_LONG_TEXT_PROBE = """
function px(value){ var n = parseFloat(value); return isNaN(n) ? null : n; }
function textReport(el){
  var style = getComputedStyle(el);
  return {
    overflowX: el.scrollWidth - el.clientWidth, overflowY: el.scrollHeight - el.clientHeight,
    lines: Math.round(el.clientHeight / px(style.lineHeight)), whiteSpace: style.whiteSpace,
  };
}
function collect(scope){
  return {
    progress: textReport(scope.querySelector('.tier1-pct')),
    titles: Array.prototype.map.call(scope.querySelectorAll('.agent-run-title'), textReport),
  };
}
var listCard = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
var list = collect(listCard.querySelector('[data-session-id="%(session)s"]'));
__dispatchClick(listCard.querySelector('.path'));
await __sleep(%(settle)d);
var modal = collect(document.querySelector('#dzh-session-modal-body [data-session-id="%(session)s"]'));
__probeResult({list: list, modal: modal});
"""


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubSessionModalCleanupDomTest(unittest.TestCase):
    """카드 상세보기 정리 7건의 행동 계약 — 각 시나리오의 근거는 PRP §1.1 표의 요구 번호와 결정 번호다."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def test_d18_card_without_visible_session_neither_looks_nor_acts_like_it_opens_the_modal(self) -> None:
        # ② 결정 MX2 — 보일 세션이 없는 카드(daily-brief)는 눌러도 카드 상세보기가 열리지 않고 열릴 것처럼 보이지도
        # 않는다: 모달 표지가 없고, 제목은 보조기술 표지 없는 span 이며, 커서는 손가락이 아니다. 여백(카드 자신)·경로·제목
        # 어디를 눌러도 모달이 안 열리고 목록도 inert 로 잠기지 않는다. 대조군인 보일 세션이 있는 카드는 표지·버튼·손가락
        # 커서를 갖고 세 곳 어디를 눌러도 열린다. 두 카드 모두 data-project-path 는 있다(드래그·순서 저장 — D19).
        probe_body = _EMPTY_CARD_CLICK_PROBE % {"settle": _SETTLE_MS, "empty": _EMPTY_CARD_PATH, "full": _FULL_CARD_PATH}
        result = run_scenario(_make_page(_EMPTY_CARD_SNAPSHOT, probe_body))
        with self.subTest(card="보일 세션이 없는 카드"):
            self._assert_card_does_not_open_modal(result["empty"])
        with self.subTest(card="보일 세션이 있는 카드"):
            self._assert_card_opens_modal(result["full"])

    def _assert_card_does_not_open_modal(self, facts: dict) -> None:
        """보일 세션이 없는 카드의 표지·제목·커서·클릭 결과(D18, 결정 MX2)."""
        self.assertIsNone(facts["opener"], "보일 세션이 없는 카드에 모달 표지가 있음(D18, MX2)")
        self.assertTrue(facts["hasProjectPath"], "보일 세션이 없는 카드가 data-project-path 를 잃음(D18, MX2 — 드래그·순서 저장에서 빠진다)")
        self.assertEqual(facts["titleTag"], "SPAN", "보일 세션이 없는 카드의 제목이 눌리지 않는 span 이 아님(D18, MX2)")
        self.assertIsNone(facts["titlePopup"], "눌리지 않는 제목에 aria-haspopup 이 있음(D18, MX2 — 없는 기능을 있는 척한다)")
        self.assertNotEqual(facts["cardCursor"], "pointer", "보일 세션이 없는 카드의 커서가 손가락 모양임(D18, MX2)")
        self.assertNotEqual(facts["titleCursor"], "pointer", "보일 세션이 없는 카드 제목의 커서가 손가락 모양임(D18, MX2)")
        for place, place_label in (("margin", "여백"), ("path", "경로"), ("title", "제목")):
            self.assertFalse(facts[place]["modalOpen"], f"보일 세션이 없는 카드의 {place_label} 클릭이 카드 상세보기를 엶(D18, MX2)")
            self.assertFalse(facts[place]["appInert"], f"보일 세션이 없는 카드의 {place_label} 클릭이 목록을 잠금(D18, MX2)")

    def _assert_card_opens_modal(self, facts: dict) -> None:
        """보일 세션이 있는 카드(대조군)의 표지·제목·커서·클릭 결과(D18, 결정 MX2)."""
        self.assertEqual(facts["opener"], "1", "보일 세션이 있는 카드에 모달 표지가 없음(D18, MX2)")
        self.assertTrue(facts["hasProjectPath"], "보일 세션이 있는 카드가 data-project-path 를 잃음(D18)")
        self.assertEqual(facts["titleTag"], "BUTTON", "보일 세션이 있는 카드의 제목이 버튼이 아님(D18, MX2)")
        self.assertEqual(facts["titlePopup"], "dialog", "모달을 여는 제목에 aria-haspopup=dialog 가 없음(D18)")
        self.assertEqual(facts["cardCursor"], "pointer", "보일 세션이 있는 카드의 커서가 손가락 모양이 아님(D18, MX2)")
        self.assertEqual(facts["titleCursor"], "pointer", "보일 세션이 있는 카드 제목의 커서가 손가락 모양이 아님(D18, MX2)")
        for place, place_label in (("margin", "여백"), ("path", "경로"), ("title", "제목")):
            self.assertTrue(facts[place]["modalOpen"], f"보일 세션이 있는 카드의 {place_label} 클릭이 카드 상세보기를 안 엶(D18, MX2)")
            self.assertTrue(facts[place]["appInert"], f"카드 상세보기가 열렸는데 목록이 잠기지 않음(D18 — {place_label} 클릭)")

    def test_d19_card_without_visible_session_still_reorders_by_drag_and_opens_nothing(self) -> None:
        # ② 결정 MX2·U10 — 보일 세션이 없는 카드도 드래그로 순서를 바꿀 수 있어야 한다(드래그·순서 저장은 모든 카드의
        # data-project-path 를 쓴다). 합성 DragEvent(dragstart → dragover → drop → dragend)로 그 카드를 맨 앞으로
        # 끌면 화면 순서와 저장값(localStorage)이 함께 바뀌고 카드 상세보기는 안 열린다. 그 카드가 이미 모달을 열지
        # 않는 카드라는 사전조건(커서·표지)을 함께 본다 — 「열리지 않는 카드」의 재정렬을 확인하는 시나리오다.
        probe_body = _EMPTY_CARD_DRAG_PROBE % {"settle": _SETTLE_MS, "empty": _EMPTY_CARD_PATH}
        result = run_scenario(_make_page(_EMPTY_CARD_SNAPSHOT, probe_body))
        expected_order = [_EMPTY_CARD_PATH, "/repo/coding-harness", "/repo/atlas"]
        self.assertEqual(result["before"], _EMPTY_CARD_ORDER, "드래그 전 카드 순서가 스냅샷 순서와 다름(D19 사전조건)")
        self.assertTrue(result["emptyCardHasProjectPath"], "보일 세션이 없는 카드가 data-project-path 를 잃음(D19, MX2 — 드래그·순서 저장에서 빠진다)")
        self.assertNotEqual(result["emptyCardCursor"], "pointer", "보일 세션이 없는 카드가 손가락 커서임(D19 사전조건, MX2)")
        self.assertEqual(result["after"], expected_order, "빈 카드를 맨 앞으로 끌었는데 순서가 바뀌지 않음(D19, MX2 — 드래그 재정렬이 깨졌다)")
        self.assertIsNotNone(result["stored"], "드래그 뒤 순서가 localStorage 에 저장되지 않음(D19, MX2)")
        self.assertEqual(result["stored"][:3], expected_order, "드래그 뒤 저장된 순서가 새 순서와 다름(D19, MX2)")
        self.assertFalse(result["emptyCardOpensModal"], "다시 그린 뒤 보일 세션이 없는 카드에 모달 표지가 생김(D19, MX2)")
        self.assertFalse(result["modalOpen"], "드래그가 카드 상세보기를 엶(D19, MX2)")
        self.assertEqual(result["draggingLeft"], 0, "드래그가 끝났는데 card-dragging 표시가 남음(D19)")

    def _assert_near(self, actual: float, expected: float, message: str) -> None:
        """두 좌표가 허용 오차(_GEOMETRY_TOLERANCE_PX) 안에서 같다 — 실패 메시지에 실측값을 붙인다."""
        self.assertAlmostEqual(actual, expected, delta=_GEOMETRY_TOLERANCE_PX, msg=f"{message} (실측 {actual:.2f} vs 기대 {expected:.2f})")

    def test_d20_connector_lines_stay_joined_to_root_bus_and_cards_at_every_scroll_position(self) -> None:
        # ③ 결정 MX6 — 루트↔세션 연결선의 세 접합(줄기 x = 첫 드롭 x · 줄기 아랫끝 = 버스 윗변 · 드롭 아랫끝 = 카드 윗변)이
        # 칸의 가로 스크롤 시작에서 ±0.5px 로 맞고, 끝까지 넘긴 뒤에도 줄기는 제자리(x 불변)이며 버스 구간 안에서 버스와
        # 만나 버스 아래로 삐져나온 조각이 없다(옛 줄기는 36px 라 버스 아래 31px 가 카드 사이 틈에 남았다). 버스의 양끝도
        # 맞는다 — 첫 카드 버스의 왼끝 = 첫 드롭 x(그 왼쪽에 꼬리가 없다), 끝 카드 버스의 오른끝 = 끝 드롭 x(끝 드롭까지
        # 닿고 지나치지 않는다). 가운데 카드가 있으면 이웃한 카드 버스 조각이 이어진다 — 앞 카드 버스 오른끝 = 뒤 카드
        # 버스 왼끝(간격에 구멍이 없다). 세션이 하나뿐이면 버스가 없고 줄기와 드롭이 곧바로 이어진다. 카드 상세보기만
        # 열린 세 폭(1440·1024·820)에서 본다.
        probe_body = _CONNECTOR_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps([_WIDE_PATH, _SOLO_PATH])}
        for width, height in _CONNECTOR_VIEWPORTS:
            with self.subTest(viewport=f"{width}x{height}"):
                result = run_scenario(_make_page(_LAYOUT_SNAPSHOT, probe_body), window_width=width, window_height=height)
                by_path = {entry["path"]: entry for entry in result["results"]}
                wide_label = f"{width}x{height} 세션 5개"
                self._assert_connector_joined_across_scroll(by_path[_WIDE_PATH], wide_label)
                self._assert_bus_pieces_meet(by_path[_WIDE_PATH]["atStart"]["busPieces"], wide_label)
                self._assert_connector_joined_without_bus(by_path[_SOLO_PATH]["atStart"], f"{width}x{height} 세션 1개")

    def _assert_connector_joined_across_scroll(self, entry: dict, where: str) -> None:
        """세션 여럿(버스 있음) 프로젝트의 연결선 접합 — 스크롤 시작과 끝(D20, 결정 MX6)."""
        where = f"D20, MX6 — {where}"
        start, end = entry["atStart"], entry["atEnd"]
        self.assertTrue(start["canScroll"], f"칸이 가로로 넘치지 않음(사전조건 — {where})")
        self.assertGreater(end["scrollLeft"], 0, f"칸을 끝까지 넘기지 못함(사전조건 — {where})")
        self.assertFalse(start["busHidden"], f"세션이 여럿인데 버스가 숨겨져 있음({where})")
        self._assert_near(start["firstCardLeft"], start["rootLeft"], f"루트 왼끝과 첫 카드 왼끝이 어긋남({where})")
        self._assert_near(start["dropX"], start["stemX"], f"줄기 x 와 첫 드롭 x 가 어긋남(스크롤 0 — {where})")
        self._assert_near(start["busTop"], start["stemBottom"], f"줄기 아랫끝이 버스 윗변과 어긋남(스크롤 0 — {where})")
        self._assert_near(start["dropBottom"], start["cardTop"], f"드롭 아랫끝이 카드 윗변과 어긋남(스크롤 0 — {where})")
        self._assert_near(start["busLeft"], start["dropX"], f"첫 카드 버스 왼끝이 첫 드롭 x 와 어긋남 — 첫 드롭 왼쪽에 꼬리가 남거나 버스가 첫 드롭에 못 닿음(스크롤 0 — {where})")
        self._assert_near(start["busRight"], start["lastDropX"], f"끝 카드 버스 오른끝이 끝 드롭 x 와 어긋남 — 버스가 끝 드롭에 못 닿거나 지나침(스크롤 0 — {where})")
        self._assert_near(end["stemX"], start["stemX"], f"칸을 넘기자 줄기 x 가 움직임(줄기는 제자리다, SC12 — {where})")
        self._assert_near(end["busTop"], end["stemBottom"], f"칸 끝에서 줄기가 버스 아래로 삐져나옴(스크롤 끝 — {where})")
        self.assertGreaterEqual(end["stemX"], end["busLeft"] - _GEOMETRY_TOLERANCE_PX, f"칸 끝에서 줄기가 버스 왼쪽 끝 밖에 있음({where})")
        self.assertLessEqual(end["stemX"], end["busRight"] + _GEOMETRY_TOLERANCE_PX, f"칸 끝에서 줄기가 버스 오른쪽 끝 밖에 있음({where})")

    def _assert_bus_pieces_meet(self, pieces: list[dict], where: str) -> None:
        """이웃한 카드 버스 조각이 이어진다 — 앞 카드 버스 오른끝 = 뒤 카드 버스 왼끝(D20, 결정 MX6). 가운데 카드가
        있어야 가운데 규칙(양쪽으로 gap / 2 번짐)이 쓰이므로 세션 3개 이상을 요구한다. 카드 상자는 칸 밖으로 넘쳐도
        자리가 있어, 보이는 카드 수와 무관하게 모든 이웃 쌍을 잰다(스크롤 0 — 조각의 자리는 스크롤과 함께 움직인다)."""
        where = f"D20, MX6 — {where}"
        self.assertGreaterEqual(len(pieces), 3, f"버스 이음새를 보려면 세션이 3개 이상이어야 함(사전조건 — {where})")
        for index in range(len(pieces) - 1):
            self._assert_near(
                pieces[index]["right"], pieces[index + 1]["left"],
                f"{index + 1}번째 카드 버스 오른끝과 {index + 2}번째 카드 버스 왼끝이 이어지지 않음 — 이웃 카드 버스 사이에 구멍이 나거나 겹침(스크롤 0 — {where})",
            )

    def _assert_connector_joined_without_bus(self, geometry: dict, where: str) -> None:
        """세션 하나(only-child) 프로젝트의 연결선 접합 — 버스가 없고 줄기 → 드롭이 곧바로 이어진다(D20, 결정 MX6)."""
        where = f"D20, MX6 — {where}"
        self.assertTrue(geometry["busHidden"], f"세션이 하나인데 버스가 그려져 있음({where})")
        self._assert_near(geometry["dropX"], geometry["stemX"], f"줄기 x 와 드롭 x 가 어긋남({where})")
        self._assert_near(geometry["dropTop"], geometry["stemBottom"], f"줄기 아랫끝과 드롭 윗끝이 어긋남({where})")
        self._assert_near(geometry["dropBottom"], geometry["cardTop"], f"드롭 아랫끝이 카드 윗변과 어긋남({where})")

    def test_d21_dialog_is_as_tall_as_its_content_and_hangs_from_one_eighth_of_the_area(self) -> None:
        # ⑤ 결정 LM8(MX7 개정) — 카드 상세보기 창은 내용 높이이고 헤더 아래 ~ 화면 아래 16px 영역의 윗변에서 영역 높이의 12.5% 아래에 윗변이
        # 걸린다: 내용이 들어가면 스크롤이 없고 창이 영역보다 낮으며, 창 윗변이 그 지점에 있다(아래 간격은 남는 몫 —
        # 오버레이의 아래 여백 16px 을 뺀 값이고 사용량 패널과 무관하다).
        # 칸은 창 안쪽 아랫변까지 닿고(카드 아래 빈 면이 없다) 세션 카드 li 는 칸의 내용 높이를 채운다(폭은 D31).
        # 세션 1개와 5개 모두 — 세션 수가 아니라 내용(가장 긴 카드)이 높이를 정한다.
        probe_body = _DIALOG_SIZE_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps([_SOLO_PATH, _WIDE_PATH])}
        result = run_scenario(_make_page(_LAYOUT_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        for report, label in zip(result["results"], ("세션 1개", "세션 5개")):
            with self.subTest(project=label):
                self._assert_dialog_is_content_height_and_hangs_at_one_eighth(report, label)
                self._assert_dialog_fills_without_scrolling(report, label)
                self._assert_cards_fill_strip_height(report, label)

    def _assert_dialog_is_content_height_and_hangs_at_one_eighth(self, report: dict, label: str) -> None:
        """창이 영역보다 낮고(내용 높이) 윗변이 영역 윗변에서 영역 높이의 12.5% 아래다(D21, 결정 LM8 재개정). 영역 = 오버레이 높이 − 아래 여백 16px.
        내용이 12.5% 아래에 들어가는 구간이라 줄어드는 갈래가 아니다(사전조건 — 창 높이 ≤ 영역의 87.5%)."""
        where = f"D21, LM8 — {label}"
        available = report["modalHeight"] - _DIALOG_MARGIN_PX
        self.assertLess(report["dialogHeight"], available - 1, f"창이 가용 높이를 다 차지함 — 내용 높이가 아님({where})")
        self.assertLessEqual(report["dialogHeight"], (1 - _DIALOG_TOP_FRACTION) * available, f"창이 12.5% 아래에 다 들어가지 않음(사전조건 — {where})")
        self._assert_near(report["gapAbove"], _DIALOG_TOP_FRACTION * available, f"창 윗변이 영역 높이의 12.5% 지점이 아님({where})")

    def _assert_dialog_fills_without_scrolling(self, report: dict, label: str) -> None:
        """내용이 가용 높이에 들어가는 경우 — 스크롤이 없고 칸이 창 안쪽 아랫변까지 닿는다(D21, 결정 LM8)."""
        where = f"D21, LM8 — {label}"
        self.assertLessEqual(report["dialogScroll"]["scroll"], report["dialogScroll"]["client"] + 1, f"내용이 들어가는데 다이얼로그가 스크롤함({where})")
        self.assertLessEqual(report["stripScroll"]["scroll"], report["stripScroll"]["client"] + 1, f"칸이 세로로 스크롤함({where})")
        self._assert_near(report["gapBelowStrip"], 0, f"칸이 창 안쪽 아랫변까지 닿지 않음 — 카드 아래 빈 면이 있다({where})")

    def _assert_cards_fill_strip_height(self, report: dict, label: str) -> None:
        """세션 카드 li 가 칸의 내용 높이를 채운다(D21, 결정 LM8). 폭은 메인 카드와 비슷하다(D31, test_hub_template_dom_modal_layout.py)."""
        where = f"D21, LM8 — {label}"
        self.assertGreater(len(report["items"]), 0, f"세션 카드가 없음(사전조건 — {where})")
        for item in report["items"]:
            self._assert_near(item["height"], report["stripContentHeight"], f"세션 카드 li 가 칸의 내용 높이를 채우지 않음({where})")

    def test_d21_dialog_alone_scrolls_when_the_content_exceeds_the_available_height(self) -> None:
        # ⑤ 결정 LM8·LM9 — 내용이 가용 높이를 넘으면 창은 최대 높이에서 멈추고 다이얼로그만 세로로 스크롤한다: 칸은 자기 안에서
        # 세로 스크롤하지 않고(칸·프레임·본문의 flex-shrink 0 이 하중을 진다, GOTCHA 8 — SC6 이 기각한 가로·세로 스크롤 칸의 겹침) 세션 카드는
        # 내용 높이 밑으로 줄지 않는다. 1024×560 에서 긴 진행률 제목과 실행 줄 셋을 가진 세션으로 본다.
        probe_body = _DIALOG_SIZE_PROBE % {"settle": _SETTLE_MS, "paths": json.dumps([_LONG_PATH])}
        report = run_scenario(_make_page(_LONG_SNAPSHOT, probe_body), window_width=1024, window_height=560)["results"][0]
        self._assert_near(report["dialogHeight"], report["modalHeight"] - _DIALOG_MARGIN_PX, "내용이 넘치면 다이얼로그 높이가 모달 영역 − 16px(최대 높이)이어야 함(D21, LM8)")
        # 줄어드는 쪽(칸·카드)을 먼저 본다 — 칸이 줄면 다이얼로그가 스크롤할 만큼 넘치지 않아 아래 사전조건이 먼저 깨지는데, 그 원인은 픽스처가 아니다.
        self.assertLessEqual(report["stripScroll"]["scroll"], report["stripScroll"]["client"] + 1, "칸이 자기 안에서 세로 스크롤함(D21, MX7 — 넘침은 다이얼로그만 받는다)")
        self.assertEqual(report["clippedCards"], 0, "세션 카드가 내용 높이 밑으로 줄어 내용이 넘침(D21, MX7)")
        self.assertGreater(report["dialogScroll"]["scroll"], report["dialogScroll"]["client"] + 1, "내용이 가용 높이를 넘는데 다이얼로그가 스크롤하지 않음(D21, MX7 — 넘침을 다이얼로그가 받지 못한다)")

    def test_d21_empty_state_keeps_the_gap_between_root_path_and_phrase(self) -> None:
        # ① 결정 MX1·MX3 (M3 검수 인계) — 루트 상자를 단순화하며 사라진 옛 아랫 여백(패딩 8 + 테두리 1)을 세션 0개 상태의
        # 간격 9px 가 메운다. 본문이 세로 flex 컨테이너가 된 뒤에도(M4 — 마진이 합쳐지지 않는 컨텍스트) 그 간격이 그대로다.
        probe_body = _EMPTY_STATE_GAP_PROBE % {
            "settle": _SETTLE_MS, "path": _GAP_PATH, "poll_snapshot": _safe_js_string_literal(_minimal_data_document(_GAP_HIDDEN_SNAPSHOT)),
        }
        result = run_scenario(_make_page(_GAP_OPEN_SNAPSHOT, probe_body))
        self.assertTrue(result["modalOpen"], "보일 세션이 0개가 되자 모달이 닫힘(D21 사전조건, MX3)")
        self.assertEqual(result["emptyText"], "화면에 보일 세션이 없습니다.", "세션 0개인데 빈 문구가 아님(D21 사전조건)")
        self._assert_near(result["pathToEmptyPhrase"], _EMPTY_STATE_GAP_PX, "세션 0개 상태에서 머리 경로와 빈 문구 사이 간격이 9px 가 아님(D21, MX1)")

    def test_d22_modal_session_card_shows_long_run_titles_in_full_while_the_list_keeps_clamping(self) -> None:
        # ⑥ 결정 MX9·LM4 — 카드 상세보기의 세션 카드는 카드 목록보다 덜 보여 주지 않는다: 실행 줄 제목은 줄바꿈해 가로로 넘치지
        # 않는다(끊을 곳 없는 긴 토큰도 마찬가지). 같은 세션의 카드 목록 줄은 그대로다 — 실행 줄 제목은 한 줄 말줄임. 긴 진행률
        # 제목(진행중 단계 줄과 단계 칩이 걷힌 뒤 제목만 남은 줄)은 두 화면 모두 잘리지 않고 여러 줄로 접힌다(클램프 없음).
        probe_body = _LONG_TEXT_PROBE % {"settle": _SETTLE_MS, "path": _LONG_PATH, "session": _LONG_SESSION_ID}
        result = run_scenario(_make_page(_LONG_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        listed, modal = result["list"], result["modal"]
        self.assertEqual(len(modal["titles"]), 3, "모달 세션 카드의 실행 줄이 3개가 아님(D22 사전조건)")
        for listed_title in listed["titles"]:
            self.assertEqual(listed_title["whiteSpace"], "nowrap", "카드 목록 줄의 실행 줄 제목이 한 줄 말줄임이 아님(D22, MX9 — 잘림 해제가 목록까지 샜다)")
        for surface, report in (("카드 목록 줄", listed), ("카드 상세보기 카드", modal)):
            with self.subTest(surface=surface):
                self.assertLessEqual(report["progress"]["overflowY"], _GEOMETRY_TOLERANCE_PX, f"{surface}의 진행률 줄이 세로로 잘림(D22, LM4)")
                self.assertLessEqual(report["progress"]["overflowX"], _GEOMETRY_TOLERANCE_PX, f"{surface}의 진행률 줄이 가로로 잘림(D22, LM4)")
                self.assertGreaterEqual(report["progress"]["lines"], 2, f"{surface}의 진행률 줄이 여러 줄로 접히지 않음(D22 사전조건 — 긴 제목이 짧다)")
        for index, modal_title in enumerate(modal["titles"]):
            self.assertLessEqual(modal_title["overflowX"], _GEOMETRY_TOLERANCE_PX, f"모달 세션 카드의 {index + 1}번째 실행 줄 제목이 가로로 잘림(D22, MX9)")

    def test_d23_running_chip_has_no_glyph_keeps_screen_reader_text_and_color_distinction(self) -> None:
        # ⑦ 결정 MX10 — 실행중 칩의 ● 를 걷는다. 시각 채널은 강조색 하나로 줄고, 화면 낭독기에는 지금과
        # 같게 「 진행 중」이 읽혀야 한다(.sr-only). 종료 칩에는 둘 다 없다. 목록 카드와 상세보기 양쪽.
        probe_body = """
function chipReport(scope){
  return Array.prototype.map.call(scope.querySelectorAll('.agent-run'), function(row){
    var chip = row.querySelector('.agent-chip');
    var style = getComputedStyle(chip);
    return {
      running: chip.classList.contains('agent-chip-running'),
      glyphCount: chip.querySelectorAll('.glyph').length,
      hasBulletText: chip.textContent.indexOf('●') !== -1,
      srTexts: Array.prototype.map.call(chip.querySelectorAll('.sr-only'), function(el){ return el.textContent; }),
      colorSignature: style.color + ' on ' + style.backgroundColor,
    };
  });
}
var listChips = chipReport(document.getElementById('dzh-app'));
var card = document.querySelector('#dzh-app [data-project-path="/repo/coding-harness"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%(settle)d);
__probeResult({list: listChips, modal: chipReport(document.getElementById('dzh-session-modal-body'))});
""" % {"settle": _SETTLE_MS}
        result = run_scenario(_make_page(_RUN_CHIP_SNAPSHOT, probe_body))
        for surface, surface_label in (("list", "카드 목록"), ("modal", "카드 상세보기")):
            with self.subTest(surface=surface_label):
                chips = result[surface]
                running_chips = [chip for chip in chips if chip["running"]]
                ended_chips = [chip for chip in chips if not chip["running"]]
                self.assertEqual(len(running_chips), 3, f"실행중 칩이 3개가 아님(D23 사전조건 — {surface_label})")
                self.assertEqual(len(ended_chips), 1, f"종료 칩이 1개가 아님(D23 사전조건 — {surface_label})")
                for chip in chips:
                    self.assertFalse(chip["hasBulletText"], f"칩 글자에 ● 가 남음(D23, MX10 — {surface_label})")
                for chip in running_chips:
                    self.assertEqual(chip["glyphCount"], 0, f"실행중 칩에 글리프가 남음(D23, MX10 — {surface_label})")
                    self.assertEqual(chip["srTexts"], [" 진행 중"], f"실행중 칩의 보조기술용 텍스트가 「 진행 중」 하나가 아님(D23, MX10 — {surface_label})")
                for chip in ended_chips:
                    self.assertEqual(chip["glyphCount"], 0, f"종료 칩에 글리프가 있음(D23 — {surface_label})")
                    self.assertEqual(chip["srTexts"], [], f"종료 칩에 보조기술용 텍스트가 있음(D23 — {surface_label})")
                # 글리프를 뺀 뒤 실행중/종료의 시각 구분은 색 하나다(MX10 의 대가) — 그 색 구분이 살아 있어야 한다.
                running_signatures = {chip["colorSignature"] for chip in running_chips}
                ended_signatures = {chip["colorSignature"] for chip in ended_chips}
                self.assertTrue(
                    running_signatures.isdisjoint(ended_signatures),
                    f"실행중 칩과 종료 칩의 색이 같음(D23, MX10 — 글리프가 없으면 색이 유일한 시각 구분이다): {running_signatures} / {ended_signatures}",
                )

    def test_d24_card_and_modal_root_draw_no_project_progress_while_sessions_keep_theirs(self) -> None:
        # ④ 결정 MX4 — 카드와 카드 상세보기 머리(루트)에서 프로젝트 단위 진행률 3줄을 걷는다. 그 대시보드를
        # 기록한 세션 줄·세션 카드 아래의 자기 진행률은 그대로다. 프로젝트 진행률에 붙던 경고 두 가지(「이전
        # 작업」 라벨·「주인 세션 없음」 칩)와 그 톤다운 스코프 속성도 함께 사라진다. 세 갈래를 한 번에 본다.
        probe_body = _PROJECT_PROGRESS_PROBE % {
            "settle": _SETTLE_MS,
            "labels": json.dumps(list(_PROJECT_PROGRESS_LABELS)),
            "project_title": json.dumps(_PROJECT_PROGRESS_TITLE),
        }
        result = run_scenario(_make_page(_PROJECT_PROGRESS_SNAPSHOT, probe_body))
        self.assertEqual(
            [entry["label"] for entry in result["results"]], list(_PROJECT_PROGRESS_LABELS),
            "프로브가 세 프로젝트를 다 돌지 않음(D24 사전조건)",
        )
        for entry in result["results"]:
            label = entry["label"]
            self.assertTrue(entry["modalClosed"], f"다음 프로젝트로 넘어가기 전에 카드 상세보기가 안 닫힘(D24 사전조건 — {label})")
            for surface, surface_label in (("list", "카드"), ("modal", "카드 상세보기 머리")):
                with self.subTest(project=label, surface=surface_label):
                    self._assert_no_project_progress(label, entry[surface], f"{label} {surface_label}")

    def _assert_no_project_progress(self, label: str, report: dict, where: str) -> None:
        """한 화면(카드 또는 카드 상세보기 머리)에 프로젝트 단위 진행률의 흔적이 하나도 없고, 세션 자기
        진행률만 정확히 한 줄 있다(D24). where 는 실패 메시지에 실릴 「프로젝트 화면」 이름이다."""
        where = f"D24, MX4 — {where}"
        self.assertEqual(report["projectLevelLines"], 0, f"프로젝트 단위 진행률 줄이 남음({where})")
        self.assertEqual(report["labelChips"], 0, f"경고 라벨 칩이 남음({where})")
        self.assertFalse(report["hasProjectTitle"], f"프로젝트 단위 진행률 제목이 화면 글자에 남음({where})")
        self.assertFalse(report["hasPreviousText"], f"「이전 작업」 글자가 남음({where})")
        self.assertFalse(report["hasOrphanText"], f"「주인 세션 없음」 글자가 남음({where})")
        self.assertFalse(report["scopeAttributes"], f"톤다운 스코프 속성이 남음({where})")
        # 세션 자기 진행률은 그대로 — 그 대시보드를 기록한 세션 한 곳에 정확히 한 줄이다.
        self.assertEqual(len(report["sessionProgressTexts"]), 1, f"세션 자기 진행률이 한 줄이 아님({where})")
        self.assertIn(
            f"{_SESSION_PROGRESS_TITLE} {label}", report["sessionProgressTexts"][0],
            f"세션 줄·세션 카드의 자기 진행률 제목이 다름({where})",
        )


if __name__ == "__main__":
    unittest.main()
