"""tests/hub/test_hub_template_dom_session_row.py — 헤드리스 Chrome DOM 행동 검사 중 세션 줄 정보 순서·
2단 레일·단계 칩 부재 3건(D25~D27, docs/prps/hub-session-row-layout-and-modal-size.md §6, 결정 LM2·LM3 와 그 문서의
LM5·LM6 을 걷은 개정 LM12 — 진행률 줄 맨 앞 단계 칩은 서브에이전트 실행 칩과 헷갈려 없앴다)과 첫 줄의 시간 표시(D32 — 작업 시작부터 소요된 시간).

카드 목록의 세션 줄(button.session-row)과 카드 상세보기의 세션 카드(.session-card)는 같은 조각
(renderSessionContent)을 그리므로 세 시나리오 모두 두 화면을 같은 프로브로 잰다. 공용 하네스는
template_dom_harness.py(무변경) — 세션·진행률 픽스처는 이 모듈 안에서 dataclasses.replace 로 만든다.
D21(창 높이)·D22(긴 글)·D24(프로젝트 진행률)의 개정분은 test_hub_template_dom_modal_cleanup.py 에 있다.

Chrome 이 없으면 SKIP(사유 출력). 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 —
변경 전 템플릿으로 돌려 이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_parse  # noqa: E402  (sys.path 조정 후 임포트 — Tier1Snapshot 픽스처용)
import hub_session  # noqa: E402  (BackgroundWait·SubagentRunView 픽스처용)
import hub_usage  # noqa: E402  (SessionCost 픽스처용)
import hub_workflow  # noqa: E402  (WorkflowRunView 픽스처용)

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
        run_scenario,
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
        run_scenario,
    )

_MS_PER_MINUTE = 60000
_SETTLE_MS = 30                     # 클릭 뒤 동기 렌더가 끝나길 기다리는 짧은 여유
_GEOMETRY_TOLERANCE_PX = 0.5        # PRP §4.5 R3 의 접합 허용 오차(서브픽셀 반올림)
_PROJECT_PATH = "/repo/rows"
_BRANCH_CLASSES = ("session-tier1", "agent-run-list", "workflow-runs")
_EXPECTED_ORDER = ("session-line", "session-meta", "excerpt", *_BRANCH_CLASSES)
_TICK_ADVANCE_MINUTES = 1           # 하네스 __fireTick 이 시계를 61초 앞으로 보낸다 — 진행 중 세션의 소요 분이 정확히 1 늘어나는 조합이다
_DURATION_SR_LABEL = "작업 시작부터 "


# ── 픽스처 ──
def _steps(*name_state_detail: tuple[str, str, str]) -> tuple[hub_parse.StepView, ...]:
    return tuple(
        hub_parse.StepView(index=index, name=name, state=state, detail=detail, started_at=None)
        for index, (name, state, detail) in enumerate(name_state_detail, start=1)
    )


def _tier1(
    title: str, steps: tuple[hub_parse.StepView, ...], is_committed: bool = False, is_approval_step_active: bool = False,
) -> hub_parse.Tier1Snapshot:
    completed = sum(1 for step in steps if step.state == "done")
    return hub_parse.Tier1Snapshot(
        title=title, subtitle="", completed=completed, total=len(steps), percent=round(completed * 100 / len(steps)),
        steps=steps, matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
        file_mtime_ms=BASE_TIME_MS, is_committed=is_committed, is_approval_step_active=is_approval_step_active,
    )


def _run(agent_id: str, phase: str, is_running: bool, title: str) -> hub_session.SubagentRunView:
    started_at_ms = BASE_TIME_MS - 6 * _MS_PER_MINUTE
    return hub_session.SubagentRunView(
        agent_id=agent_id, agent_type="code-reviewer", phase=phase, is_running=is_running, started_at_ms=started_at_ms,
        ended_at_ms=None if is_running else started_at_ms + 3 * _MS_PER_MINUTE, title=title, model="sonnet",
    )


def _workflow(*labels: str) -> hub_workflow.WorkflowRunView:
    return hub_workflow.WorkflowRunView(
        agents=tuple(hub_workflow.WorkflowAgentView(index=index, label=label, state="done") for index, label in enumerate(labels, start=1)),
    )


_FOUR_PHASES_REVIEWING = _steps(("설계", "done", ""), ("승인", "done", ""), ("구현", "done", ""), ("검수", "active", "구현 1회차 완료 요약"))
_FOUR_PHASES_ALL_DONE = _steps(("설계", "done", ""), ("승인", "done", ""), ("구현", "done", ""), ("검수", "done", ""))
_BACKGROUND_WAIT = hub_session.BackgroundWait(
    since_ms=BASE_TIME_MS - 2 * _MS_PER_MINUTE, until_ms=BASE_TIME_MS + 60 * _MS_PER_MINUTE, task_count=1, wakeup_count=0,
)
_ESCAPE_DETAIL = '직전 "기록" & <i>요약</i>'
_ESCAPE_TITLE = "이스케이프 <b>제목</b> & 따옴표\""


def _dated(session_id: str, state: str, base_state: str, minutes_ago: int, **fields) -> hub_session.SessionView:
    """세션 하나. 기본은 발췌 없는 세션이라 필요한 필드만 fields 로 얹는다."""
    base = _session(session_id, state, base_state, BASE_TIME_MS - minutes_ago * _MS_PER_MINUTE)
    session = dataclasses.replace(base, **fields)
    # 결정 MN5 — 승인 대기 표지는 서버 판정(session.is_awaiting_approval)을 읽는다. 픽스처도 같은 함수로 채워 승인 DOM 테스트와 모양을 맞춘다.
    return dataclasses.replace(session, is_awaiting_approval=hub_session.is_awaiting_approval(state, base_state, session.tier1))


# D25·D26 — 가지(진행률·실행 줄·워크플로)와 발췌의 유무 조합. 식별 이름이 곧 조합이다.
_STRUCTURE_SESSIONS = (
    _dated("full", "working", "working", 1, task_excerpt="모든 조각이 있는 세션의 발췌",
           tier1=_tier1("전체 구성", _FOUR_PHASES_REVIEWING),
           agent_runs=(_run("r1", "검수", True, "검수 실행"), _run("r2", "구현", False, "구현 실행")),
           workflow=_workflow("lint-sweep", "type-check")),
    _dated("bare", "idle", "idle", 2, tier1=_tier1("진행률만", _FOUR_PHASES_REVIEWING)),
    _dated("runs-only", "idle", "idle", 3, task_excerpt="진행률과 실행 줄", tier1=_tier1("진행률과 실행", _FOUR_PHASES_REVIEWING),
           agent_runs=(_run("r3", "검수", False, "끝난 검수"),)),
    _dated("workflow-only", "idle", "idle", 4, task_excerpt="진행률과 워크플로", tier1=_tier1("진행률과 워크플로", _FOUR_PHASES_REVIEWING),
           workflow=_workflow("lint-sweep")),
    _dated("no-dashboard", "idle", "idle", 5, task_excerpt="대시보드 없는 세션의 발췌", agent_runs=(_run("r4", "구현", False, "구현 실행"),)),
)
_STRUCTURE_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "rows", "working", _STRUCTURE_SESSIONS),))

# D27 — 옛 단계 칩이 떴던 상태마다 세션 1개(진행중 단계 있음·백그라운드 대기·검수 통과 뒤 커밋 전·커밋 완료·끝난 작업·이스케이프). 어느 상태에서도
# 진행률 줄에는 칩이 없고, 서브에이전트 실행 줄(.agent-run-list)의 칩만 남는다. 진행률 줄에는 단계 이름·직전 기록 요약이 그려지지 않는다 — 승인 대기
# 표지는 첫 줄(결정 AW3, 검사는 test_hub_template_dom_approval.py)이라 idle-approval 은 그 사실을 켜도 진행률 줄에 자식 요소가 없어야 한다.
_STAGE_SESSIONS = (
    _dated("working-review", "working", "working", 1, task_excerpt="실행 줄 있는 검수", tier1=_tier1("검수 중", _FOUR_PHASES_REVIEWING),
           agent_runs=(_run("r5", "검수", True, "검수 실행"),)),
    _dated("background-review", "background", "idle", 2, task_excerpt="백그라운드 대기·실행 줄 없음", tier1=_tier1("검수 중", _FOUR_PHASES_REVIEWING),
           background_wait=_BACKGROUND_WAIT),
    _dated("background-precommit", "background", "idle", 3, task_excerpt="검수 통과·커밋 전", tier1=_tier1("통과 뒤", _FOUR_PHASES_ALL_DONE),
           background_wait=_BACKGROUND_WAIT),
    _dated("idle-committed", "idle", "idle", 4, task_excerpt="커밋까지 끝", tier1=_tier1("커밋 뒤", _FOUR_PHASES_ALL_DONE, is_committed=True)),
    _dated("idle-finished-task", "idle", "idle", 5, task_excerpt="끝난 작업의 대시보드", tier1=_tier1("끝난 작업", _FOUR_PHASES_ALL_DONE),
           tier1_is_finished_task=True),
    _dated("idle-approval", "idle", "idle", 6, task_excerpt="승인 기다림",
           tier1=_tier1("승인 중", _steps(("설계", "done", ""), ("승인", "active", ""), ("구현", "wait", ""), ("검수", "wait", "")), is_approval_step_active=True)),
    _dated("idle-escape", "idle", "idle", 7, task_excerpt="이스케이프",
           tier1=_tier1(_ESCAPE_TITLE, _steps(("설계", "done", ""), ("<b>검수</b>", "active", _ESCAPE_DETAIL)))),
    _dated("two-runs", "working", "working", 8, task_excerpt="실행 칩 둘", tier1=_tier1("실행 둘", _FOUR_PHASES_REVIEWING),
           agent_runs=(_run("r6", "검수", True, "검수 실행"), _run("r7", "구현", False, "구현 실행"))),
    _dated("no-dashboard", "idle", "idle", 9, task_excerpt="대시보드 없음"),
)
_STAGE_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "rows", "working", _STAGE_SESSIONS),))
_EXPECTED_RUN_CHIP_COUNTS = {"working-review": 1, "two-runs": 2}   # 나머지는 0 — 실행 줄이 없다

# 두 화면(카드 목록의 세션 줄 · 카드 상세보기의 세션 카드)을 같은 모양으로 재는 프로브. 세션 ID 마다 자식 클래스 순서·세로
# 위치, 가지의 레일 의사요소 좌표, 진행률 줄의 높이와 단계 칩을 돌려준다. 채우는 자리: settle(ms)·ids(JSON 배열)·path.
_ROW_PROBE = """
function px(value){ var n = parseFloat(value); return isNaN(n) ? null : n; }
var BRANCH_CLASSES = %(branch_classes)s;
function railReport(branch){
  var rect = branch.getBoundingClientRect();
  var after = getComputedStyle(branch, '::after'), before = getComputedStyle(branch, '::before');
  var hasAfter = after.display !== 'none';
  return {
    cls: branch.classList[0],
    hookTop: rect.top + px(before.top), hookHeight: px(before.height),
    afterDisplay: after.display,
    afterTop: hasAfter ? rect.top + px(after.top) : null,
    afterBottom: hasAfter ? rect.top + px(after.top) + px(after.height) : null,
  };
}
function scopeReport(scope){
  var pct = scope.querySelector('.tier1-pct');
  return {
    children: Array.prototype.map.call(scope.children, function(el){
      var rect = el.getBoundingClientRect();
      return {cls: el.classList[0], top: rect.top};
    }),
    rails: Array.prototype.filter.call(scope.children, function(el){
      return BRANCH_CLASSES.indexOf(el.classList[0]) !== -1;
    }).map(railReport),
    chipCount: scope.querySelectorAll('.tier1-step').length,
    pctChipCount: scope.querySelectorAll('.tier1-pct .agent-chip').length,
    pctElementCount: pct ? pct.children.length : null,
    runChipCount: scope.querySelectorAll('.agent-run-list .agent-chip').length,
    tier1ActiveCount: scope.querySelectorAll('.tier1-active').length,
    noDashboardCount: scope.querySelectorAll('.session-no-dashboard').length,
    injectedElements: scope.querySelectorAll('.tier1-pct b, .tier1-pct i').length,
    pctText: pct ? pct.textContent : null,
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


def _probe_body(sessions: tuple[hub_session.SessionView, ...]) -> str:
    return _ROW_PROBE % {
        "settle": _SETTLE_MS, "path": _PROJECT_PATH, "branch_classes": json.dumps(list(_BRANCH_CLASSES)),
        "ids": json.dumps([session.session_id for session in sessions]),
    }


_SURFACES = (("list", "카드 목록 줄"), ("modal", "카드 상세보기 카드"))

# D32 — 첫 줄 시간 = 해당 작업을 시작한 순간부터의 소요(결정 LM11). 시작 = task_started_at_ms(없으면 세션 시작). 끝 = 세션이 도는 중(working·background)이면
# 지금이라 시계와 함께 늘고, 그 밖(idle·done·stale)이면 마지막 이벤트로 고정이다 — 멈춘 세션의 시간이 불어나면 의미가 없다. 음수는 durationLabel 이 「1분 미만」으로 처리한다.
# 키 = 세션 ID, 값 = (상태, 기본 상태, 세션 시작이 몇 분 전, 마지막 이벤트가 몇 분 전, 작업 시작이 몇 분 전(없으면 None), 기대 라벨, 틱(+61초) 뒤 기대 라벨).
# 목킹 시계가 고정이라 정각도 안정이고, 1분 미만 케이스만 30초 오프셋을 둔다. 세션 시작은 일부러 작업 시작보다 훨씬 이르게 둬 「세션 시작부터」로 읽히면 실패한다.
_DURATION_FIXTURES = {
    "task-restart-minutes": ("working", "working", 300, 1, 12, "12분 소요", "13분 소요"),
    "task-hours": ("working", "working", 900, 2, 83, "1시간 23분 소요", "1시간 24분 소요"),
    "task-seconds": ("working", "working", 60, 0, 0.5, "1분 미만 소요", "1분 소요"),
    "background-grows": ("background", "idle", 120, 3, 20, "20분 소요", "21분 소요"),
    "session-start-fallback": ("working", "working", 50, 1, None, "50분 소요", "51분 소요"),
    "idle-fixed": ("idle", "idle", 400, 60, 100, "40분 소요", "40분 소요"),
    "done-fixed": ("done", "done", 600, 20, 200, "3시간 0분 소요", "3시간 0분 소요"),
    "stale-fixed": ("stale", "working", 500, 30, 90, "1시간 0분 소요", "1시간 0분 소요"),
    "idle-fallback-fixed": ("idle", "idle", 100, 40, None, "1시간 0분 소요", "1시간 0분 소요"),
    "negative-clamped": ("idle", "idle", 100, 30, 10, "1분 미만 소요", "1분 미만 소요"),
}
_DURATION_CASES = {session_id: (fixture[5], fixture[6]) for session_id, fixture in _DURATION_FIXTURES.items()}


def _duration_session(session_id: str, fixture: tuple) -> hub_session.SessionView:
    state, base_state, started_ago, last_ago, task_ago, _, _ = fixture
    task_started_at_ms = None if task_ago is None else BASE_TIME_MS - int(task_ago * _MS_PER_MINUTE)
    return _dated(
        session_id, state, base_state, last_ago, task_excerpt=f"{session_id} 발췌",   # 끝난 세션은 발췌가 있어야 화면에 보인다(결정 V2)
        started_at_ms=BASE_TIME_MS - started_ago * _MS_PER_MINUTE, task_started_at_ms=task_started_at_ms,
        background_wait=_BACKGROUND_WAIT if state == "background" else None,
    )


_DURATION_SESSIONS = tuple(_duration_session(session_id, fixture) for session_id, fixture in _DURATION_FIXTURES.items())
_DURATION_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "rows", "working", _DURATION_SESSIONS),))
_DURATION_PROBE = """
function timeReport(scope){
  var line = scope.querySelector('.session-line');
  var time = line.querySelector('.session-time');
  var sr = time.querySelector('.sr-only');
  var visible = Array.prototype.filter.call(time.childNodes, function(node){ return node.nodeType === 3; })
    .map(function(node){ return node.textContent; }).join('');
  return {visible: visible, sr: sr ? sr.textContent : null, hasTooltip: time.hasAttribute('data-tooltip'), full: time.textContent};
}
function collect(){
  var listCard = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
  var list = {}, modal = {};
  ids.forEach(function(id){
    list[id] = timeReport(listCard.querySelector('.session-row[data-session-id="' + id + '"]'));
    modal[id] = timeReport(document.querySelector('#dzh-session-modal-body .session-card[data-session-id="' + id + '"]'));
  });
  return {list: list, modal: modal, lastActivity: listCard.querySelector('.last-activity').textContent};
}
var ids = %(ids)s;
var listCardForOpen = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
__dispatchClick(listCardForOpen.querySelector('.path'));
await __sleep(%(settle)d);
var before = collect();
await __fireTick();
await __sleep(%(settle)d);
var after = collect();
__probeResult({before: before, after: after});
"""


# D33(⑨, docs/prps/harness-benchmark-adoption.md §7-2 안 A) — 세션 비용·컨텍스트 칩은 식별 줄(.session-meta)의 네 번째 칩이다. 키 = 세션 ID,
# 값 = (SessionCost 또는 None, 기대 칩 글자(칩이 없으면 None), 툴팁에 있어야 하는 조각들).
_COST_TOOLTIP_NOTE = "정가 기준 추정, 구독 요금과 무관"
_COST_FIXTURES = {
    "cost-full": (hub_usage.SessionCost(BASE_TIME_MS, 1284, 31, 62), "≈$12.84 · 컨텍스트 62%", (_COST_TOOLTIP_NOTE, "API 시간 31분")),
    "cost-hundred-plus": (hub_usage.SessionCost(BASE_TIME_MS, 12345, 0, 91), "≈$123 · 컨텍스트 91%", (_COST_TOOLTIP_NOTE, "API 시간 1분 미만")),
    "cost-cents-only": (hub_usage.SessionCost(BASE_TIME_MS, 3, None, None), "≈$0.03", (_COST_TOOLTIP_NOTE,)),
    "context-only": (hub_usage.SessionCost(BASE_TIME_MS, None, None, 62), "컨텍스트 62%", (_COST_TOOLTIP_NOTE,)),
    "all-values-absent": (hub_usage.SessionCost(BASE_TIME_MS, None, 5, None), None, ()),
    "no-capture": (None, None, ()),
}
_COST_SESSIONS = tuple(
    _dated(session_id, "idle", "idle", index + 1, task_excerpt=f"{session_id} 발췌", session_cost=fixture[0])
    for index, (session_id, fixture) in enumerate(_COST_FIXTURES.items())
)
_COST_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "rows", "working", _COST_SESSIONS),))
_COST_PROBE = """
function costReport(scope){
  var chips = scope.querySelectorAll('.session-cost');
  var chip = chips.length ? chips[0] : null;
  var srEl = chip ? chip.querySelector('.sr-only') : null;
  return {
    count: chips.length,
    inMeta: scope.querySelectorAll('.session-meta .session-cost').length,
    inFirstLine: scope.querySelectorAll('.session-line .session-cost').length,
    label: chip ? chip.textContent.slice(srEl ? srEl.textContent.length : 0) : null,
    sr: srEl ? srEl.textContent : null,
    tooltip: chip ? chip.getAttribute('data-tooltip') : null,
    metaChildClasses: Array.prototype.map.call(scope.querySelector('.session-meta').children, function(el){ return el.classList[0]; }),
  };
}
var ids = %(ids)s;
var listCard = document.querySelector('#dzh-app .card[data-project-path="%(path)s"]');
var list = {};
ids.forEach(function(id){ list[id] = costReport(listCard.querySelector('.session-row[data-session-id="' + id + '"]')); });
__dispatchClick(listCard.querySelector('.path'));
await __sleep(%(settle)d);
var modal = {};
ids.forEach(function(id){ modal[id] = costReport(document.querySelector('#dzh-session-modal-body .session-card[data-session-id="' + id + '"]')); });
__probeResult({list: list, modal: modal});
"""


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubSessionRowLayoutDomTest(unittest.TestCase):
    """세션 줄 정보 순서·레일·단계 칩의 행동 계약 — 근거는 PRP 결정 LM2·LM3·LM5·LM6."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def _structure_result(self) -> dict:
        return run_scenario(_make_page(_STRUCTURE_SNAPSHOT, _probe_body(_STRUCTURE_SESSIONS)), window_width=1440, window_height=900)

    def test_d25_children_follow_the_tree_order_and_the_dom_order_is_the_visual_order(self) -> None:
        # 결정 LM2 — 세션 줄 안의 자식은 line → meta → 발췌 → 진행률 → 실행 줄 → 워크플로 순(있는 것만)이고, DOM 순서와 화면의
        # 위→아래 순서가 같다(CSS order 로 뒤집지 않는다 — 화면 낭독기가 버튼 안 자식을 DOM 순서로 읽는다). 발췌 없음·
        # 실행 줄 없음·워크플로 없음·대시보드 없음 조합과 카드 목록·상세보기 두 화면 모두.
        result = self._structure_result()
        for session in _STRUCTURE_SESSIONS:
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session.session_id, surface=surface_label):
                    children = result[surface][session.session_id]["children"]
                    present = {child["cls"] for child in children}
                    expected = [name for name in _EXPECTED_ORDER if name in present]
                    self.assertEqual([child["cls"] for child in children], expected, "자식 DOM 순서가 line→meta→발췌→진행률→실행 줄→워크플로가 아님(D25, LM2)")
                    tops = [child["top"] for child in children]
                    self.assertEqual(tops, sorted(tops), f"화면의 위→아래 순서가 DOM 순서와 다름(D25, LM2 — CSS order 가 남았다): {children}")
                    self.assertEqual(len(set(tops)), len(tops), "두 자식이 같은 높이에 겹쳐 있음(D25, LM2)")

    def test_d25_fixture_covers_every_combination(self) -> None:
        # 사전조건 — 위 시나리오가 실제로 여섯 자식이 다 있는 세션과 일부가 빠진 세션을 모두 본다.
        result = self._structure_result()
        full = {child["cls"] for child in result["list"]["full"]["children"]}
        self.assertEqual(full, set(_EXPECTED_ORDER), "full 세션에 여섯 자식이 다 있지 않음(D25 사전조건)")
        bare = {child["cls"] for child in result["list"]["bare"]["children"]}
        self.assertEqual(bare, {"session-line", "session-meta", "session-tier1"}, "bare 세션이 line·meta·진행률만이 아님(D25 사전조건)")

    def test_d26_each_branch_hooks_to_the_rail_above_and_only_the_last_branch_ends_it(self) -> None:
        # 결정 LM3 — 2단 가지(진행률·실행 줄·워크플로)는 각자 갈고리를 갖고, 마지막이 아닌 가지는 아래 레일을 이어 다음 가지의
        # 갈고리 윗끝과 맞닿는다. 마지막 가지는 레일이 없다(display:none).
        result = self._structure_result()
        for session in _STRUCTURE_SESSIONS:
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session.session_id, surface=surface_label):
                    self._assert_branch_rails_join(result[surface][session.session_id]["rails"])

    def _assert_branch_rails_join(self, rails: list[dict]) -> None:
        """가지 레일의 접합(D26) — 앞 가지의 레일 아랫끝 = 뒤 가지의 갈고리 윗끝, 마지막 가지는 레일 없음."""
        self.assertGreaterEqual(len(rails), 1, "가지가 하나도 없음(D26 사전조건)")
        for current, following in zip(rails, rails[1:]):
            self.assertNotEqual(current["afterDisplay"], "none", f"뒤에 가지가 이어지는데 {current['cls']} 레일이 숨겨짐(D26, LM3)")
            self.assertAlmostEqual(
                current["afterBottom"], following["hookTop"], delta=_GEOMETRY_TOLERANCE_PX,
                msg=f"{current['cls']} 레일 아랫끝이 {following['cls']} 갈고리 윗끝과 어긋남(D26, LM3)",
            )
        self.assertEqual(rails[-1]["afterDisplay"], "none", f"마지막 가지 {rails[-1]['cls']} 에 레일이 남음(D26, LM3)")

    def test_d27_progress_line_has_no_stage_chip_and_run_chips_stay(self) -> None:
        # 결정 LM12(LM5·LM6 개정) — 진행률 줄 맨 앞 단계 칩은 걷혔다: 아래 서브에이전트 실행 줄의 .agent-chip 과 같은 어휘라 헷갈렸다. 어떤 상태
        # (진행중 단계·백그라운드 대기·검수 통과 뒤 커밋 전·커밋 완료·끝난 작업)에서도 진행률 줄은 「제목 — 완료/전체 · 퍼센트」 글자뿐이고 자식 요소가
        # 하나도 없다(칩·툴팁·보조기술 라벨 없음). 진행률 줄에는 단계 이름과 직전 기록 요약이 글자로 새지 않는다(승인 대기 표지는 첫 줄 — AW3). 제목은 글자 그대로 그려진다(이스케이프).
        # 별도 「진행중 단계」 줄(.tier1-active)도 없다(LM4). 서브에이전트 실행 줄의 칩 수는 그대로다. 대시보드 없는 세션은 진행률 줄 없이 「대시보드 없음」 1개.
        result = run_scenario(_make_page(_STAGE_SNAPSHOT, _probe_body(_STAGE_SESSIONS)), window_width=1440, window_height=900)
        for session in _STAGE_SESSIONS:
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session.session_id, surface=surface_label):
                    self._assert_no_stage_chip(session, result[surface][session.session_id])

    def _assert_no_stage_chip(self, session: hub_session.SessionView, report: dict) -> None:
        """세션 하나의 계약(D27) — 칩 부재·진행률 글자·실행 칩 수·대시보드 없음 표시."""
        self.assertEqual((report["chipCount"], report["pctChipCount"], report["tier1ActiveCount"]), (0, 0, 0), "진행률 줄에 단계 칩이나 진행중 단계 줄이 있음(D27, LM12)")
        self.assertEqual(report["runChipCount"], _EXPECTED_RUN_CHIP_COUNTS.get(session.session_id, 0), "서브에이전트 실행 줄의 칩 수가 달라짐(D27 — 실행 칩은 그대로여야 한다)")
        self.assertEqual(report["injectedElements"], 0, "제목의 태그가 요소로 해석됨(D27, escape)")
        if session.tier1 is None:
            self.assertEqual((report["pctText"], report["noDashboardCount"]), (None, 1), "대시보드 없는 세션의 진행률 줄·안내 개수가 없음·1 이 아님(D27)")
            return
        tier1 = session.tier1
        self.assertEqual(report["pctText"], f"{tier1.title} — {tier1.completed}/{tier1.total} · {tier1.percent}%", "진행률 줄 글자가 「제목 — 완료/전체 · 퍼센트」 가 아님(D27, LM12)")
        self.assertEqual(report["pctElementCount"], 0, "진행률 줄 안에 자식 요소가 있음(D27, LM12 — 칩이 다시 붙었다)")

    def test_d32_session_time_is_the_elapsed_time_since_the_task_started(self) -> None:
        # 요구 2(결정 LM11) — 세션 줄 첫 줄의 시간은 「N분 전」(마지막 이벤트 경과 — 프로젝트 머리 .last-activity 와 같은 종류)도, 세션이 처음 시작된 때부터도 아니라
        # 해당 작업을 시작한 순간(task_started_at_ms)부터 소요된 시간이다. 새 필드가 없으면 세션 시작부터로 되돌아가고, 끝이 시작보다 앞서면 0(1분 미만)이다.
        # 1분 미만·분·시간+분 세 형태이고 라벨 끝에 「소요」가 붙어 「N분 전」과 섞이지 않는다. 낭독기에는 「작업 시작부터 」가 앞서 읽힌다(sr-only) —
        # 시작 시각은 바로 아래 meta 줄에 보이므로 툴팁은 달지 않는다(R4). 카드 목록 줄과 카드 상세보기 카드 두 화면 모두.
        probe_body = _DURATION_PROBE % {"settle": _SETTLE_MS, "path": _PROJECT_PATH, "ids": json.dumps(list(_DURATION_CASES))}
        result = run_scenario(_make_page(_DURATION_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        for session_id, (expected_label, _) in _DURATION_CASES.items():
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session_id, surface=surface_label):
                    report = result["before"][surface][session_id]
                    self.assertEqual(report["visible"], expected_label, "세션 첫 줄 시간이 작업 시작부터 소요된 시간이 아님(D32, LM11)")
                    self.assertEqual(report["sr"], _DURATION_SR_LABEL, "소요 시간 앞 보조기술용 「작업 시작부터 」가 없음(D32)")
                    self.assertFalse(report["hasTooltip"], "정보 손실 없는 소요 시간에 data-tooltip 이 달림(D32, R4)")
                    self.assertNotIn("전", report["visible"], "소요 시간이 「…전」(마지막 이벤트 경과)로 읽힘(D32)")

    def test_d32_working_sessions_grow_with_the_clock_and_stopped_sessions_stay_fixed(self) -> None:
        # 요구 2(결정 LM11) — 30초 틱이 같은 렌더 경로로 라벨을 다시 그린다: 도는 중(working·background) 세션은 시계(+61초)와 함께 늘고(1분 미만 → 1분, 12분 → 13분),
        # 멈춘 세션(idle·done·stale)은 작업 시작 → 마지막 이벤트로 고정이라 시계가 가도 그대로다(멈춘 세션의 시간이 불어나면 의미가 없다).
        probe_body = _DURATION_PROBE % {"settle": _SETTLE_MS, "path": _PROJECT_PATH, "ids": json.dumps(list(_DURATION_CASES))}
        result = run_scenario(_make_page(_DURATION_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        for session_id, (_, expected_after_tick) in _DURATION_CASES.items():
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session_id, surface=surface_label):
                    self.assertEqual(result["after"][surface][session_id]["visible"], expected_after_tick, f"틱 뒤 소요 시간이 다름(D32 — {_TICK_ADVANCE_MINUTES}분 경과)")

    def test_d33_session_cost_chip_is_the_fourth_meta_chip_and_never_in_the_first_line(self) -> None:
        # ⑨ 안 A — 비용·컨텍스트는 식별 줄(.session-meta)의 마지막 칩이다(시작·ID·모델 다음). 첫 줄(.session-line)에는 새지 않는다(T25-127 의 불변).
        # 값이 하나도 그릴 수 없으면(null·세 값 중 표시할 것이 없음) 칩 자체가 없다. 라벨은 ≈ 접두 + 100달러 미만은 센트까지·이상은 정수,
        # 툴팁은 「정가 기준 추정」 고지와 API 시간(0분이면 「1분 미만」). 카드 목록 줄과 카드 상세보기 카드 두 화면 모두.
        probe_body = _COST_PROBE % {"settle": _SETTLE_MS, "path": _PROJECT_PATH, "ids": json.dumps(list(_COST_FIXTURES))}
        result = run_scenario(_make_page(_COST_SNAPSHOT, probe_body), window_width=1440, window_height=900)
        for session_id, (_, expected_label, tooltip_parts) in _COST_FIXTURES.items():
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session_id, surface=surface_label):
                    report = result[surface][session_id]
                    self.assertEqual(report["inFirstLine"], 0, "비용 칩이 첫 줄(.session-line)에 있음(D33, 안 A)")
                    if expected_label is None:
                        self.assertEqual(report["count"], 0, "그릴 값이 없는데 비용 칩이 있음(D33)")
                        continue
                    self.assertEqual((report["count"], report["inMeta"]), (1, 1), "비용 칩이 식별 줄 안에 정확히 하나가 아님(D33)")
                    self.assertEqual(report["metaChildClasses"][-1], "session-cost", "비용 칩이 식별 줄의 마지막 칩이 아님(D33)")
                    self.assertEqual(report["label"], expected_label, "비용 칩 글자가 다름(D33)")
                    self.assertEqual(report["sr"], "세션 비용 ", "비용 칩 앞 보조기술용 「세션 비용 」이 없음(D33)")
                    for tooltip_part in tooltip_parts:
                        self.assertIn(tooltip_part, report["tooltip"], f"비용 칩 툴팁에 「{tooltip_part}」가 없음(D33)")


if __name__ == "__main__":
    unittest.main()
