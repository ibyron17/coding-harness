"""tests/hub/test_hub_template_dom_activity.py — 헤드리스 Chrome DOM 행동 검사 중 실행 중 활동 표시(D-LA1~D-LA9,
docs/prps/hub-live-activity.md §10.4, 결정 LA8~LA10).

도는 서브에이전트의 실행 줄 아래 활동 줄(.agent-run-activity)과 「새 기록 없음」 표지, 백그라운드 대기 세션 첫 줄의
출력 갱신(.session-activity), 두 곳의 툴팁을 잰다. 카드 목록의 세션 줄과 카드 상세보기의 세션 카드는 같은 조각
(renderSessionContent)을 그리므로 문구 시나리오는 두 화면을 같은 프로브로 잰다(D-LA8). 공용 하네스는
template_dom_harness.py(무변경).

문구의 정본은 PRP §8.2·LA9·LA10 이다 — 이 모듈의 기대 문자열은 템플릿의 상수가 아니라 PRP 에서 옮겼다. 시각은 로컬
시간대라 툴팁의 HH:MM 은 정규식으로 맞춘다.

Chrome 이 없으면 SKIP(사유 출력). 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 — 변경 전 템플릿으로 돌려
이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402  (sys.path 조정 후 임포트 — 활동 계약 타입 픽스처용)
import hub_model  # noqa: E402  (옛 페이로드 흉내를 위한 직렬화 재사용)
import hub_session  # noqa: E402  (BackgroundWait·SubagentRunView 픽스처용)

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

_MINUTE_MS = 60000
_SECOND_MS = 1000
_SETTLE_MS = 30                     # 클릭 뒤 동기 렌더가 끝나길 기다리는 짧은 여유
_RUNS_PER_SESSION = 5               # 템플릿 MAX_VISIBLE_AGENT_RUNS — 한 세션 줄에 그려지는 실행 상한
_PROJECT_PATH = "/repo/activity"
_STALL_GLYPH = "▲"
_COUNTS_SPAN_MS = 4 * _MINUTE_MS    # 도구 개수 범위의 길이 — 하한은 마지막 기록보다 이만큼 앞이다(LA5)
_TRACK_WIDTH_PX = 320               # 카드 격자의 최소 트랙 — 가장 좁은 실제 폭(PRP §8.4)
_GEOMETRY_TOLERANCE_PX = 0.5
_ONE_LINE_MAX_HEIGHT_PX = 16        # 11px × 1.35 = 14.85 — 두 줄이 되면 29.7
_TIME = r"(?:\d{1,2}/\d{1,2} )?\d{2}:\d{2}"
_RUNNING_BASE = rf"implementer · 구현 단계 · sonnet · 시작 {_TIME} · 진행 중"
_ENDED_BASE = rf"implementer · 구현 단계 · sonnet · 시작 {_TIME} · 종료"
_STALL_NOTE = "허브는 멈춤을 단정하지 않습니다 — 길게 생각하는 중일 수도 있습니다\\."
_STALL_CLASS = "agent-run-activity-stall"

# PRP §8.2 — 종류 5값의 진행 중 문구와 마지막 도구 명사.
_PENDING_LABELS = {"read": "읽는 중", "edit": "고치는 중", "run": "명령 실행 중", "delegate": "다른 에이전트 기다리는 중", "other": "도구 실행 중"}
_KIND_NOUNS = {"read": "읽기", "edit": "수정", "run": "실행", "delegate": "위임", "other": "기타"}


# ── 픽스처 ──
def _output(updated_ago_ms: int, total_bytes: int = 49152, file_count: int = 1) -> hub_activity.BackgroundOutputView:
    return hub_activity.BackgroundOutputView(file_count=file_count, updated_at_ms=BASE_TIME_MS - updated_ago_ms, total_bytes=total_bytes)


def _activity(
    last_record_ago_ms: int = 20 * _SECOND_MS,
    last_tool_kind: str | None = "read",
    pending_count: int = 0,
    pending_tool_kind: str | None = None,
    pending_since_ago_ms: int | None = None,
    counts: hub_activity.ToolKindCounts = hub_activity.ToolKindCounts(read=6, edit=2, run=3),
    stall_suspect_in_ms: int | None = None,
    output: hub_activity.BackgroundOutputView | None = None,
) -> hub_activity.SubagentActivity:
    """활동 값 하나 — 모든 시각은 목킹 시계(BASE_TIME_MS) 기준 상대값이다."""
    return hub_activity.SubagentActivity(
        last_record_at_ms=BASE_TIME_MS - last_record_ago_ms, last_tool_kind=last_tool_kind,
        pending_count=pending_count, pending_tool_kind=pending_tool_kind,
        pending_since_ms=None if pending_since_ago_ms is None else BASE_TIME_MS - pending_since_ago_ms,
        recent_tool_counts=counts, recent_counts_since_ms=BASE_TIME_MS - last_record_ago_ms - _COUNTS_SPAN_MS,
        stall_suspect_at_ms=None if stall_suspect_in_ms is None else BASE_TIME_MS + stall_suspect_in_ms,
        background_output=output,
    )


def _run(agent_id: str, activity: hub_activity.SubagentActivity | None, is_running: bool = True,
         started_ago_ms: int = 29 * _MINUTE_MS) -> hub_session.SubagentRunView:
    started_at_ms = BASE_TIME_MS - started_ago_ms
    return hub_session.SubagentRunView(
        agent_id=agent_id, agent_type="implementer", phase="구현", is_running=is_running, started_at_ms=started_at_ms,
        ended_at_ms=None if is_running else BASE_TIME_MS - 3 * _MINUTE_MS, title="허브 활동 표시 — 파서와 읽기", model="sonnet",
        activity=activity,
    )


def _session_with(session_id: str, state: str, base_state: str, **fields) -> hub_session.SessionView:
    """세션 하나. 끝나지 않은 세션이라 발췌 없이도 화면에 보인다."""
    return dataclasses.replace(_session(session_id, state, base_state, BASE_TIME_MS - _MINUTE_MS), task_excerpt=f"{session_id} 발췌", **fields)


def _sessions_holding(runs: list[hub_session.SubagentRunView], prefix: str) -> tuple[hub_session.SessionView, ...]:
    """실행들을 한 세션 줄의 표시 상한(5)씩 나눠 작업중 세션으로 담는다."""
    chunks = [runs[start:start + _RUNS_PER_SESSION] for start in range(0, len(runs), _RUNS_PER_SESSION)]
    return tuple(_session_with(f"{prefix}-{index}", "working", "working", agent_runs=tuple(chunk)) for index, chunk in enumerate(chunks))


def _background_wait(output: hub_activity.BackgroundOutputView | None) -> hub_session.BackgroundWait:
    return hub_session.BackgroundWait(
        since_ms=BASE_TIME_MS - 2 * _MINUTE_MS, until_ms=BASE_TIME_MS + 60 * _MINUTE_MS, task_count=1, wakeup_count=0, output=output,
    )


# D-LA1·D-LA2 — 활동 줄 본문 표. 키 = 실행 ID, 값 = (활동, 틱 전 기대 본문(글리프 제외) — 줄이 없어야 하면 None).
_PENDING_CASES = {
    f"pending-{kind}": (_activity(last_tool_kind=kind, pending_count=1, pending_tool_kind=kind, pending_since_ago_ms=12 * _MINUTE_MS), f"{label} · 12분째")
    for kind, label in _PENDING_LABELS.items()
}
_LAST_CASES = {
    f"last-{kind}": (_activity(last_record_ago_ms=3 * _MINUTE_MS, last_tool_kind=kind), f"마지막 기록 3분 전 · {noun}")
    for kind, noun in _KIND_NOUNS.items()
}
_STALLED_COUNTS = hub_activity.ToolKindCounts(read=4, edit=5, run=1)
_LINE_CASES = {
    "plain-none": (None, None),
    **_PENDING_CASES,
    **_LAST_CASES,
    "pending-output": (_activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS, output=_output(_MINUTE_MS)), "명령 실행 중 · 4분째 · 출력 1분 전"),
    "pending-many": (_activity(pending_count=2, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS, output=_output(_MINUTE_MS)), "명령 실행 중 외 1건 · 4분째 · 출력 1분 전"),
    "pending-just-started": (_activity(pending_count=1, pending_tool_kind="read", pending_since_ago_ms=20 * _SECOND_MS), "읽는 중 · 방금 시작"),
    "pending-hours": (_activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=90 * _MINUTE_MS), "명령 실행 중 · 1시간 30분째"),
    "last-now": (_activity(), "마지막 기록 방금 · 읽기"),
    "last-no-kind": (_activity(last_record_ago_ms=3 * _MINUTE_MS, last_tool_kind=None), "마지막 기록 3분 전"),
    "last-output": (_activity(output=_output(25 * _MINUTE_MS)), "마지막 기록 방금 · 읽기 · 출력 25분 전"),
    "last-hours": (_activity(last_record_ago_ms=65 * _MINUTE_MS), "마지막 기록 1시간 5분 전 · 읽기"),
    "stall-past": (_activity(last_record_ago_ms=12 * _MINUTE_MS, counts=_STALLED_COUNTS, stall_suspect_in_ms=-2 * _MINUTE_MS), "12분째 새 기록 없음"),
    "stall-boundary": (_activity(last_record_ago_ms=10 * _MINUTE_MS, stall_suspect_in_ms=0), "10분째 새 기록 없음"),
    "stall-output": (_activity(last_record_ago_ms=12 * _MINUTE_MS, stall_suspect_in_ms=-2 * _MINUTE_MS, output=_output(25 * _MINUTE_MS)), "12분째 새 기록 없음 · 출력 25분 전"),
    "stall-soon": (_activity(last_record_ago_ms=570 * _SECOND_MS, stall_suspect_in_ms=30 * _SECOND_MS), "마지막 기록 9분 전 · 읽기"),
}
_STALLED_BEFORE_TICK = {"stall-past", "stall-boundary", "stall-output", "resumed-stall"}
# 재개된 실행 — 시작(재개) 시각이 마지막 기록보다 늦다. 표지 시각은 둘 중 늦은 쪽 + 10분이다(LA8).
_RESUMED_STARTED_AGO_MS = 11 * _MINUTE_MS
_RESUMED_ACTIVITY = _activity(last_record_ago_ms=40 * _MINUTE_MS, counts=_STALLED_COUNTS, stall_suspect_in_ms=-1 * _MINUTE_MS)
# 틱(+61초) 뒤 기대 본문. 표지 여부가 뒤집히거나(stall-soon) 숫자가 한 칸 늘어야 하는 줄만 단정한다.
_AFTER_TICK_BODIES = {
    "stall-past": "13분째 새 기록 없음", "stall-boundary": "11분째 새 기록 없음",
    "stall-output": "13분째 새 기록 없음 · 출력 26분 전", "resumed-stall": "41분째 새 기록 없음",
    "stall-soon": "10분째 새 기록 없음",
}
_STALLED_AFTER_TICK = _STALLED_BEFORE_TICK | {"stall-soon"}

# D-LA7 — 행 툴팁 전용 실행(첫 줄은 오늘과 같다, 정규식 줄 목록 = 줄바꿈으로 나뉜 줄).
_LAST_LINE_NOW = rf"마지막 기록 {_TIME}\(방금\) · {_TIME} 이후 도구 — 읽기 6 · 수정 2 · 실행 3"
_TOOLTIP_RUNS = {
    "tip-full": _activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS, output=_output(_MINUTE_MS, 49152)),
    "tip-multi": _activity(
        last_record_ago_ms=3 * _MINUTE_MS, pending_count=2, pending_tool_kind="delegate", pending_since_ago_ms=12 * _MINUTE_MS,
        counts=hub_activity.ToolKindCounts(delegate=1, other=2),
    ),
    "tip-zero-counts": _activity(last_record_ago_ms=3 * _MINUTE_MS, counts=hub_activity.ToolKindCounts()),
    "tip-small": _activity(output=_output(_MINUTE_MS, 512, file_count=2)),
    "tip-megabytes": _activity(output=_output(_MINUTE_MS, 1258291)),
}
_STALL_LINES = [
    rf"{_TIME} 이후 새 기록이 없고 결과를 기다리는 도구도 없습니다\(기준 10분\)\.", _STALL_NOTE,
]
_TOOLTIP_PATTERNS = {
    "tip-full": [
        _RUNNING_BASE, _LAST_LINE_NOW, rf"결과를 기다리는 도구 1건 — 명령 실행 중, {_TIME} 부터",
        rf"백그라운드 출력 파일 1개 — {_TIME} 갱신 · 48KB",
    ],
    "tip-multi": [
        _RUNNING_BASE, rf"마지막 기록 {_TIME}\(3분 전\) · {_TIME} 이후 도구 — 위임 1 · 기타 2",
        rf"결과를 기다리는 도구 2건 — 다른 에이전트 기다리는 중, {_TIME} 부터",
    ],
    "tip-zero-counts": [_RUNNING_BASE, rf"마지막 기록 {_TIME}\(3분 전\)"],
    "tip-small": [_RUNNING_BASE, _LAST_LINE_NOW, rf"백그라운드 출력 파일 2개 — {_TIME} 갱신 · 512B"],
    "tip-megabytes": [_RUNNING_BASE, _LAST_LINE_NOW, rf"백그라운드 출력 파일 1개 — {_TIME} 갱신 · 1\.2MB"],
    "last-now": [_RUNNING_BASE, _LAST_LINE_NOW],
    "stall-past": [
        _RUNNING_BASE, rf"마지막 기록 {_TIME}\(12분 전\) · {_TIME} 이후 도구 — 읽기 4 · 수정 5 · 실행 1", *_STALL_LINES,
    ],
    "resumed-stall": [
        _RUNNING_BASE, rf"마지막 기록 {_TIME}\(40분 전\) · {_TIME} 이후 도구 — 읽기 4 · 수정 5 · 실행 1", *_STALL_LINES,
    ],
    "ended-with-activity": [_ENDED_BASE],
    "plain-none": [_RUNNING_BASE],
}

# D-LA5 — 세션 첫 줄의 출력 갱신. 키 = 세션 ID, 값 = (상태, 기본 상태, 배경 대기, 기대 본문(없으면 None)).
_BACKGROUND_SENTENCE = (
    rf"이 세션은 {_TIME} 부터 백그라운드 작업 1개를 기다리고 있습니다\. 끝나거나 알림이 오면 이어서 진행합니다 — "
    rf"{_TIME} 까지 소식이 없으면 이 표시를 거둡니다\."
)
_SESSION_OUTPUT_NOTE = "조용히 오래 도는 명령은 끝날 때만 출력이 늘 수 있습니다\\."
_SESSION_CASES = {
    "bg-output": ("background", "idle", _background_wait(_output(_MINUTE_MS, 1258291)), "출력 1분 전 갱신"),
    "bg-output-old": ("background", "idle", _background_wait(_output(90 * _MINUTE_MS, 49152, file_count=2)), "출력 1시간 30분 전 갱신"),
    "bg-no-output": ("background", "idle", _background_wait(None), None),
    "working-with-output": ("working", "working", _background_wait(_output(_MINUTE_MS)), None),
}
_SESSION_TOOLTIP_PATTERNS = {
    "bg-output": [_BACKGROUND_SENTENCE, rf"작업 출력은 {_TIME}\(1분 전\)에 마지막으로 늘었습니다 — 확인된 출력 파일 1개 · 1\.2MB\. {_SESSION_OUTPUT_NOTE}"],
    "bg-output-old": [_BACKGROUND_SENTENCE, rf"작업 출력은 {_TIME}\(1시간 30분 전\)에 마지막으로 늘었습니다 — 확인된 출력 파일 2개 · 48KB\. {_SESSION_OUTPUT_NOTE}"],
    "bg-no-output": [_BACKGROUND_SENTENCE],
}


def _main_runs() -> list[hub_session.SubagentRunView]:
    runs = [_run(run_id, activity) for run_id, (activity, _) in _LINE_CASES.items()]
    runs += [_run(run_id, activity) for run_id, activity in _TOOLTIP_RUNS.items()]
    runs.append(_run("resumed-stall", _RESUMED_ACTIVITY, started_ago_ms=_RESUMED_STARTED_AGO_MS))
    runs.append(_run("ended-with-activity", _activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS), is_running=False))
    return runs


def _main_sessions() -> tuple[hub_session.SessionView, ...]:
    background = tuple(
        _session_with(session_id, state, base_state, background_wait=wait)
        for session_id, (state, base_state, wait, _) in _SESSION_CASES.items()
    )
    return _sessions_holding(_main_runs(), "runs") + background


_MAIN_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "activity", "working", _main_sessions()),))

# 두 화면(카드 목록 · 카드 상세보기)을 같은 모양으로 읽는 프로브 조각. 채우는 자리: PATH·SETTLE.
_REPORT_FUNCTIONS = """
function textWithoutGlyph(element){
  var clone = element.cloneNode(true);
  Array.prototype.forEach.call(clone.querySelectorAll('.glyph'), function(glyph){ glyph.remove(); });
  return clone.textContent;
}
function runReport(row){
  var activity = row.querySelector('.agent-run-activity');
  var glyph = activity ? activity.querySelector('.glyph') : null;
  return {
    className: row.className, tooltip: row.getAttribute('data-tooltip'),
    childClasses: Array.prototype.map.call(row.children, function(child){ return child.className; }),
    activityCount: row.querySelectorAll('.agent-run-activity').length,
    activityClass: activity ? activity.className : null,
    activityText: activity ? textWithoutGlyph(activity) : null,
    glyphText: glyph ? glyph.textContent : null, glyphAriaHidden: glyph ? glyph.getAttribute('aria-hidden') : null,
    activityIsLastChild: activity ? activity === row.lastElementChild : null,
  };
}
function sessionReport(scope){
  var line = scope.querySelector('.session-line');
  var spans = line.querySelectorAll('.session-activity');
  var span = spans.length ? spans[0] : null;
  var badge = line.querySelector('.badge');
  return {
    activityCount: spans.length, activityText: span ? span.textContent : null,
    activityParentClass: span ? span.parentElement.className : null,
    activityPreviousClass: span ? span.previousElementSibling.className : null,
    badgeTooltip: badge.hasAttribute('data-tooltip') ? badge.getAttribute('data-tooltip') : null,
  };
}
function surfaceReport(scope, sessionSelector){
  var runs = {}, sessions = {};
  Array.prototype.forEach.call(scope.querySelectorAll('.agent-run'), function(row){ runs[row.getAttribute('data-render-key')] = runReport(row); });
  Array.prototype.forEach.call(scope.querySelectorAll(sessionSelector), function(el){ sessions[el.getAttribute('data-session-id')] = sessionReport(el); });
  return {runs: runs, sessions: sessions};
}
function collect(){
  var card = document.querySelector('#dzh-app .card[data-project-path="PATH"]');
  return {
    list: surfaceReport(card, '.session-row'),
    modal: surfaceReport(document.getElementById('dzh-session-modal-body'), '.session-card'),
  };
}
""".replace("PATH", _PROJECT_PATH)

_MAIN_PROBE = _REPORT_FUNCTIONS + """
var card = document.querySelector('#dzh-app .card[data-project-path="%s"]');
__dispatchClick(card.querySelector('.path'));
await __sleep(%d);
var before = collect();
await __fireTick();
await __sleep(%d);
var after = collect();
__probeResult({before: before, after: after});
""" % (_PROJECT_PATH, _SETTLE_MS, _SETTLE_MS)

_SURFACES = (("list", "카드 목록 줄"), ("modal", "카드 상세보기 카드"))


def _mutated_page(snapshot, probe_body: str, mutate) -> str:
    """snapshot 을 구운 페이지의 #dzh-data JSON 을 mutate(payload) 로 고친 사본 — 새 키가 없던 옛 서버 페이로드 흉내."""
    rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, snapshot)
    opening = '<script type="application/json" id="dzh-data">'
    start = rendered.index(opening) + len(opening)
    end = rendered.index("</script>", start)
    payload = json.loads(rendered[start:end])
    mutate(payload)
    escaped = json.dumps(payload, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return inject_scripts(rendered[:start] + escaped + rendered[end:], pre_script(None), probe_body)


def _drop_activity_keys(payload: dict) -> None:
    for project in payload["projects"]:
        for session in project["sessions"]:
            for run in session["agent_runs"]:
                run.pop("activity", None)
            if session["background_wait"]:
                session["background_wait"].pop("output", None)


class HubActivityLabelTableTest(unittest.TestCase):
    """Chrome 없이 도는 사전 조건 — 이 모듈의 문구 표가 도구 종류 5값을 빠짐없이 덮는다."""

    def test_expected_label_tables_cover_every_tool_kind(self) -> None:
        self.assertEqual(set(_PENDING_LABELS), set(hub_activity.TOOL_KINDS), "진행 중 문구 표가 도구 종류 5값과 다름")
        self.assertEqual(set(_KIND_NOUNS), set(hub_activity.TOOL_KINDS), "마지막 도구 명사 표가 도구 종류 5값과 다름")


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubActivityLineDomTest(unittest.TestCase):
    """활동 줄·툴팁·세션 출력 갱신의 행동 계약 — 근거는 PRP 결정 LA8~LA10. 한 번 굽고 여러 단정이 나눠 읽는다."""

    result: dict

    @classmethod
    def setUpClass(cls) -> None:
        if not _TEMPLATE_TEXT:
            raise unittest.SkipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")
        cls.result = run_scenario(_make_page(_MAIN_SNAPSHOT, _MAIN_PROBE), window_width=1440, window_height=900)

    def _run_reports(self, phase: str, run_id: str) -> list[tuple[str, dict]]:
        """한 실행의 두 화면(카드 목록·카드 상세보기) 보고 — (화면 이름, 보고) 쌍."""
        return [(surface_label, self.result[phase][surface]["runs"][run_id]) for surface, surface_label in _SURFACES]

    def test_d_la1_running_rows_show_what_they_are_doing_or_when_they_last_wrote(self) -> None:
        # 결정 LA9 — 진행 중 호출이 있으면 「<종류별 문구> · N분째」(여럿이면 「외 N건」, 1분 미만이면 「방금 시작」), 없으면 「마지막 기록 <경과>
        # · <종류>」(종류가 없으면 생략). 출력 파일이 있으면 어느 쪽이든 「 · 출력 N분 전」이 꼬리로 붙는다. 활동이 없는 실행은 줄이 없다.
        for run_id, (activity, expected_body) in _LINE_CASES.items():
            if activity is None or run_id in _STALLED_BEFORE_TICK:
                continue
            for surface_label, report in self._run_reports("before", run_id):
                with self.subTest(run=run_id, surface=surface_label):
                    self.assertEqual(report["activityText"], expected_body, "활동 줄 문구가 PRP §8.2 와 다름(D-LA1)")
                    self.assertEqual(report["activityClass"], "agent-run-activity", "표지 전인데 새 기록 없음 모양이 붙음(D-LA1)")
                    self.assertIsNone(report["glyphText"], "표지가 아닌 줄에 ▲ 가 붙음(D-LA1)")
                    self.assertEqual(report["className"], "agent-run agent-run-with-activity", "활동 줄이 있는 실행 줄에 modifier 가 없음(D-LA1)")
                    self.assertTrue(report["activityIsLastChild"], "활동 줄이 실행 줄의 마지막 자식이 아님(D-LA1)")
                    self.assertEqual(report["activityCount"], 1, "활동 줄이 하나가 아님(D-LA1)")

    def test_d_la2_the_stall_line_appears_only_when_the_static_time_has_passed(self) -> None:
        # 결정 LA8 — 서버는 「언제부터 의심할지」라는 정적 시각만 싣고 클라이언트가 now ≥ 그 시각일 때만 그린다(경계 포함). 표지는 ▲ + 같은 줄의
        # 주황 글자(.agent-run-activity-stall)이고 문구는 사실만 적는다 — 「멈춘」·「것 같음」 같은 원인 추측이 없다. 틱(+61초)이 시계를 넘기면
        # 같은 줄이 표지로 바뀐다.
        for run_id, expected_body in {"stall-past": "12분째 새 기록 없음", "stall-boundary": "10분째 새 기록 없음", "stall-output": "12분째 새 기록 없음 · 출력 25분 전",
                                      "resumed-stall": "40분째 새 기록 없음"}.items():
            for surface_label, report in self._run_reports("before", run_id):
                with self.subTest(run=run_id, surface=surface_label):
                    self.assertEqual(report["activityText"], expected_body, "새 기록 없음 줄 문구가 PRP 와 다름(D-LA2)")
                    self.assertEqual((report["activityClass"] or "").split(), ["agent-run-activity", _STALL_CLASS], "표지 줄에 stall 모양이 없음(D-LA2)")
                    self.assertEqual((report["glyphText"], report["glyphAriaHidden"]), (_STALL_GLYPH, "true"), "표지 글리프가 ▲(aria-hidden)가 아님(D-LA2)")
                    self.assertNotIn("멈춘", report["activityText"], "원인을 추측하는 문구가 줄에 있음(D-LA2, P9)")
        for surface_label, report in self._run_reports("before", "stall-soon"):
            with self.subTest(run="stall-soon", surface=surface_label):
                self.assertEqual(report["activityClass"], "agent-run-activity", "시각 전인데 표지가 뜸(D-LA2)")

    def test_d_la2_the_clock_crossing_the_time_flips_the_line_and_only_stalled_rows_carry_the_mark(self) -> None:
        for run_id, expected_body in _AFTER_TICK_BODIES.items():
            for surface_label, report in self._run_reports("after", run_id):
                with self.subTest(run=run_id, surface=surface_label):
                    self.assertEqual(report["activityText"], expected_body, "틱 뒤 문구가 다름(D-LA2)")
                    self.assertIn(_STALL_CLASS, (report["activityClass"] or "").split(), "틱 뒤 표지 모양이 없음(D-LA2)")
        for run_id, (activity, _) in _LINE_CASES.items():
            if activity is None or run_id in _STALLED_AFTER_TICK:
                continue
            for surface_label, report in self._run_reports("after", run_id):
                with self.subTest(run=run_id, surface=surface_label):
                    self.assertIsNotNone(report["activityClass"], "활동 줄이 없음(D-LA2 사전조건)")
                    self.assertNotIn(_STALL_CLASS, report["activityClass"].split(), "서버가 표지 시각을 주지 않은 줄에 표지가 뜸(D-LA2)")

    def test_d_la3_a_run_without_activity_keeps_today_markup(self) -> None:
        # 서버가 activity 를 null 로 준 실행(읽지 못함·형식 변화 — fail-open)은 오늘과 같은 세 칸(칩·제목·경과)이다.
        for surface_label, report in self._run_reports("before", "plain-none"):
            with self.subTest(surface=surface_label):
                self.assertEqual(report["className"], "agent-run", "활동 없는 실행 줄에 modifier 가 붙음(D-LA3)")
                self.assertEqual(report["activityCount"], 0, "활동 없는 실행 줄에 활동 줄이 있음(D-LA3)")
                self.assertEqual(report["childClasses"], ["agent-chip agent-chip-running", "agent-run-title", "agent-run-meta"], "오늘의 세 칸이 아님(D-LA3)")

    def test_d_la3_a_payload_without_the_new_keys_renders_today_screen(self) -> None:
        # 새 키가 없던 옛 서버의 페이로드(키 자체가 없다 → undefined) — 어느 줄에도 활동 줄·출력 줄이 없고 툴팁은 오늘 문장 그대로다.
        page = _mutated_page(_MAIN_SNAPSHOT, _MAIN_PROBE, _drop_activity_keys)
        result = run_scenario(page, window_width=1440, window_height=900)
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                runs, sessions = result["before"][surface]["runs"], result["before"][surface]["sessions"]
                self.assertTrue(runs and sessions, "프로브가 아무것도 읽지 못함(D-LA3 사전조건)")
                for run_id, report in runs.items():
                    self.assertEqual((report["activityCount"], report["className"]), (0, "agent-run"), f"{run_id}: 키 없는 페이로드에 활동 줄이 그려짐(D-LA3)")
                    self.assertNotIn("\n", report["tooltip"], f"{run_id}: 키 없는 페이로드의 툴팁에 줄이 더해짐(D-LA3)")
                for session_id, report in sessions.items():
                    self.assertEqual(report["activityCount"], 0, f"{session_id}: 키 없는 페이로드에 출력 줄이 그려짐(D-LA3)")
                    self.assertNotIn("\n", report["badgeTooltip"] or "", f"{session_id}: 키 없는 페이로드의 배지 툴팁에 줄이 더해짐(D-LA3)")

    def test_d_la4_an_ended_run_gets_no_activity_line_even_when_the_payload_carries_one(self) -> None:
        for surface_label, report in self._run_reports("before", "ended-with-activity"):
            with self.subTest(surface=surface_label):
                self.assertEqual((report["activityCount"], report["className"]), (0, "agent-run"), "끝난 실행에 활동 줄이 그려짐(D-LA4)")

    def test_d_la5_a_waiting_session_shows_when_its_output_last_grew_on_the_first_line(self) -> None:
        # 결정 LA10 — 백그라운드 대기 세션에 output 이 있으면 첫 줄(.session-line) 소요 시간 바로 뒤에 「출력 N분 전 갱신」. output 이 없거나
        # 백그라운드 대기가 아닌 세션에는 줄이 없다. 배지 라벨은 바뀌지 않는다.
        for session_id, (_, _, _, expected_body) in _SESSION_CASES.items():
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session_id, surface=surface_label):
                    report = self.result["before"][surface]["sessions"][session_id]
                    self.assertEqual(report["activityText"], expected_body, "세션 첫 줄 출력 갱신 문구가 다름(D-LA5)")
                    if expected_body is None:
                        self.assertEqual(report["activityCount"], 0, "출력이 없는 세션에 줄이 있음(D-LA5)")
                        continue
                    self.assertEqual(report["activityParentClass"], "session-line", "출력 갱신이 첫 줄 안이 아님(D-LA5)")
                    self.assertEqual(report["activityPreviousClass"], "session-time", "출력 갱신이 소요 시간 바로 뒤가 아님(D-LA5)")

    def test_d_la5_the_badge_tooltip_gets_one_more_line_only_when_output_is_known(self) -> None:
        for session_id, patterns in _SESSION_TOOLTIP_PATTERNS.items():
            for surface, surface_label in _SURFACES:
                with self.subTest(session=session_id, surface=surface_label):
                    self._assert_tooltip_lines(self.result["before"][surface]["sessions"][session_id]["badgeTooltip"], patterns)

    def _assert_tooltip_lines(self, tooltip: str, patterns: list[str]) -> None:
        """툴팁이 줄바꿈으로 나뉜 줄마다 정규식과 정확히(처음부터 끝까지) 맞는지 본다."""
        self.assertIsNotNone(tooltip, "툴팁이 없음")
        lines = tooltip.split("\n")
        self.assertEqual(len(lines), len(patterns), f"툴팁 줄 수가 다름: {lines}")
        for line, pattern in zip(lines, patterns):
            self.assertRegex(line, f"^{pattern}$")

    def test_d_la7_the_row_tooltip_adds_lines_after_today_first_line(self) -> None:
        # 결정 LA9 — 첫 줄은 오늘과 같고, 마지막 기록·도구 개수(0 인 종류 생략), 기다리는 도구, 출력 파일, 새 기록 없음 설명이 줄로 더해진다.
        # 끝난 실행·활동 없는 실행은 첫 줄 하나뿐이다.
        for run_id, patterns in _TOOLTIP_PATTERNS.items():
            for surface, surface_label in _SURFACES:
                with self.subTest(run=run_id, surface=surface_label):
                    self._assert_tooltip_lines(self.result["before"][surface]["runs"][run_id]["tooltip"], patterns)

    def test_d_la7_the_stall_explanation_and_the_threshold_come_from_the_server_time(self) -> None:
        # 표지가 서 있지 않은 동안에는 설명이 없고, 시계가 넘으면 같은 행 툴팁에 설명이 생긴다. 「기준 10분」은 자바스크립트 사본이 아니라
        # 서버가 준 시각에서 거꾸로 센 값이다(LA8) — 재개된 실행도 같은 10분이다.
        for surface, surface_label in _SURFACES:
            with self.subTest(surface=surface_label):
                before = self.result["before"][surface]["runs"]["stall-soon"]["tooltip"]
                after = self.result["after"][surface]["runs"]["stall-soon"]["tooltip"]
                self.assertNotIn("새 기록이 없고", before, "표지 전인데 설명이 있음(D-LA7)")
                self._assert_tooltip_lines(after, [
                    _RUNNING_BASE, rf"마지막 기록 {_TIME}\(10분 전\) · {_TIME} 이후 도구 — 읽기 6 · 수정 2 · 실행 3", *_STALL_LINES,
                ])

    def test_d_la8_the_modal_card_draws_the_same_pieces_as_the_list_row(self) -> None:
        # 결정 LA9·LA10 + D-LA8 — 카드 목록의 세션 줄과 카드 상세보기의 세션 카드는 같은 조각을 쓴다: 모든 실행 줄·세션 첫 줄의 보고가 같다.
        for phase in ("before", "after"):
            listed, modal = self.result[phase]["list"], self.result[phase]["modal"]
            self.assertEqual(set(listed["runs"]), set(modal["runs"]), "두 화면이 보이는 실행 집합이 다름(D-LA8)")
            self.assertTrue(listed["runs"], "프로브가 실행 줄을 읽지 못함(D-LA8 사전조건)")
            self.assertEqual(listed["runs"], modal["runs"], f"{phase}: 모달 세션 카드의 실행 줄이 카드 목록과 다름(D-LA8)")
            self.assertEqual(listed["sessions"], modal["sessions"], f"{phase}: 모달 세션 카드의 첫 줄이 카드 목록과 다름(D-LA8)")


# D-LA6 — 가장 좁은 트랙(320px)에서의 기하. 같은 실행을 활동 있게/없게 두 세션에 둬 줄 모양이 한 칸도 안 변하는지 본다.
_LONG_TITLE = "허브 활동 표시 — 파서와 읽기 그리고 아주 긴 제목이 말줄임으로 잘리는지 보는 실행"
_WIDEST_ACTIVITY = _activity(
    pending_count=12, pending_tool_kind="delegate", pending_since_ago_ms=72 * _MINUTE_MS, output=_output(65 * _MINUTE_MS),
)
_GEOMETRY_RUNS = {
    "geo-with": _activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS, output=_output(_MINUTE_MS)),
    "geo-without": None,
    "geo-widest": _WIDEST_ACTIVITY,
}
_GEOMETRY_SESSIONS = tuple(
    _session_with(f"session-{run_id}", "working", "working", agent_runs=(dataclasses.replace(_run(run_id, activity), title=_LONG_TITLE),))
    for run_id, activity in _GEOMETRY_RUNS.items()
)
_GEOMETRY_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "activity", "working", _GEOMETRY_SESSIONS),))
_GEOMETRY_PROBE = """
var app = document.getElementById('dzh-app');
app.style.gridTemplateColumns = '%dpx';
await __sleep(%d);
function geometry(id){
  var row = app.querySelector('.agent-run[data-render-key="' + id + '"]');
  var rowRect = row.getBoundingClientRect();
  function relative(el){
    var rect = el.getBoundingClientRect();
    return {top: rect.top - rowRect.top, bottom: rect.bottom - rowRect.top, left: rect.left - rowRect.left, right: rect.right - rowRect.left, height: rect.height};
  }
  var title = row.querySelector('.agent-run-title');
  var activity = row.querySelector('.agent-run-activity');
  return {
    chip: relative(row.querySelector('.agent-chip')), title: relative(title), meta: relative(row.querySelector('.agent-run-meta')),
    titleTruncated: title.scrollWidth > title.clientWidth,
    rowOverflows: row.scrollWidth > row.clientWidth,
    activity: activity ? Object.assign(relative(activity), {truncated: activity.scrollWidth > activity.clientWidth}) : null,
  };
}
__probeResult({
  cardWidth: app.querySelector('.card').getBoundingClientRect().width,
  withActivity: geometry('geo-with'), withoutActivity: geometry('geo-without'), widest: geometry('geo-widest'),
});
""" % (_TRACK_WIDTH_PX, _SETTLE_MS)


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubActivityGeometryDomTest(unittest.TestCase):
    """320px 트랙에서 실행 줄이 흐트러지지 않는다 — 근거는 PRP 결정 LA9(modifier 로만 격자를 바꿔 활동 없는 줄을 보존)."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def test_d_la6_the_first_line_keeps_its_shape_and_the_activity_takes_its_own_line(self) -> None:
        result = run_scenario(_make_page(_GEOMETRY_SNAPSHOT, _GEOMETRY_PROBE), window_width=1440, window_height=900)
        self.assertAlmostEqual(result["cardWidth"], _TRACK_WIDTH_PX, delta=_GEOMETRY_TOLERANCE_PX, msg="카드 트랙이 320px 가 아님(D-LA6 사전조건)")
        with_activity, without_activity = result["withActivity"], result["withoutActivity"]
        for part in ("chip", "title", "meta"):
            for edge in ("top", "bottom", "left", "right"):
                self.assertAlmostEqual(
                    with_activity[part][edge], without_activity[part][edge], delta=_GEOMETRY_TOLERANCE_PX,
                    msg=f"활동 줄이 붙자 {part} 의 {edge} 위치가 달라짐(D-LA6 — 줄바꿈이 제목·경과를 밀어냄)",
                )
        self.assertTrue(without_activity["titleTruncated"], "사전조건: 활동 없는 실행의 긴 제목이 말줄임으로 잘리지 않음(D-LA6)")
        self.assertTrue(with_activity["titleTruncated"], "활동 줄이 붙자 제목 말줄임이 사라짐(D-LA6)")

    def test_d_la6_the_activity_is_one_line_below_the_first_line_and_never_widens_the_row(self) -> None:
        result = run_scenario(_make_page(_GEOMETRY_SNAPSHOT, _GEOMETRY_PROBE), window_width=1440, window_height=900)
        for name in ("withActivity", "widest"):
            with self.subTest(case=name):
                report = result[name]
                self.assertIsNotNone(report["activity"], "활동 줄이 없음(D-LA6 사전조건)")
                first_line_bottom = max(report[part]["bottom"] for part in ("chip", "title", "meta"))
                self.assertGreaterEqual(report["activity"]["top"], first_line_bottom - _GEOMETRY_TOLERANCE_PX, "활동 줄이 첫 줄 아래가 아님(D-LA6)")
                self.assertLessEqual(report["activity"]["height"], _ONE_LINE_MAX_HEIGHT_PX, "활동 줄이 두 줄로 접힘(D-LA6 — nowrap 이 풀림)")
                self.assertFalse(report["rowOverflows"], "활동 줄이 실행 줄을 가로로 넘침(D-LA6)")
        self.assertFalse(result["withActivity"]["activity"]["truncated"], "전형적인 활동 줄이 320px 에서 잘림(D-LA6, PRP §8.4)")
        self.assertFalse(result["withoutActivity"]["rowOverflows"])
        self.assertIsNone(result["withoutActivity"]["activity"], "활동 없는 실행에 줄이 생김(D-LA6)")


# D-LA6 정렬(2026-10-07 사용자 요청) — 활동 줄의 왼쪽은 칩이 아니라 제목의 왼쪽에 맞는다. 칩 폭은 단계 라벨(「설계」)이냐 agent_type 폴백(12자 + 말줄임)이냐에
# 따라 달라 고정 들여쓰기로는 맞출 수 없으니, 칩 폭이 크게 다른 두 실행으로 잰다. 제목은 카드 목록(한 줄 말줄임)과 상세보기(여러 줄)를 모두 덮을 만큼 길다.
_ALIGNMENT_TITLE = "활동 줄 왼쪽이 칩이 아니라 제목 왼쪽에 맞는지 보는 아주 긴 제목 — 카드 상세보기에서는 여러 줄로 줄바꿈되고 카드 목록에서는 말줄임으로 잘린다 " * 2
_ALIGNMENT_ACTIVITY = _activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS)
_ALIGNMENT_RUNS = [
    dataclasses.replace(_run("align-short-chip", _ALIGNMENT_ACTIVITY), phase="설계", agent_type="design-architect", title=_ALIGNMENT_TITLE),
    dataclasses.replace(_run("align-long-chip", _ALIGNMENT_ACTIVITY), phase=None, agent_type="pytorch-build-resolver", title=_ALIGNMENT_TITLE),
]
_ALIGNMENT_SNAPSHOT = _snapshot((_project(_PROJECT_PATH, "activity", "working", _sessions_holding(_ALIGNMENT_RUNS, "align")),))
_MIN_CHIP_WIDTH_GAP_PX = 20          # 두 칩 폭이 이만큼 달라야 「고정 들여쓰기로는 못 맞춘다」는 사전조건이 선다
_ALIGNMENT_PROBE = """
var app = document.getElementById('dzh-app');
app.style.gridTemplateColumns = '%dpx';
await __sleep(%d);
function alignment(scope){
  var report = {};
  Array.prototype.forEach.call(scope.querySelectorAll('.agent-run'), function(row){
    var chip = row.querySelector('.agent-chip').getBoundingClientRect();
    var title = row.querySelector('.agent-run-title').getBoundingClientRect();
    var activity = row.querySelector('.agent-run-activity').getBoundingClientRect();
    report[row.getAttribute('data-render-key')] = {
      chipLeft: chip.left, chipWidth: chip.width, titleLeft: title.left, titleBottom: title.bottom, titleHeight: title.height,
      activityLeft: activity.left, activityTop: activity.top,
    };
  });
  return report;
}
var card = app.querySelector('.card[data-project-path="%s"]');
var listReport = alignment(card);
__dispatchClick(card.querySelector('.path'));
await __sleep(%d);
__probeResult({list: listReport, modal: alignment(document.getElementById('dzh-session-modal-body'))});
""" % (_TRACK_WIDTH_PX, _SETTLE_MS, _PROJECT_PATH, _SETTLE_MS)


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubActivityAlignmentDomTest(unittest.TestCase):
    """활동 줄이 어느 서브에이전트에 딸린 내용인지 보이도록 제목 왼쪽에 선다 — 근거는 PRP 결정 LA9(2026-10-07 개정, grid)."""

    result: dict

    @classmethod
    def setUpClass(cls) -> None:
        if not _TEMPLATE_TEXT:
            raise unittest.SkipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")
        cls.result = run_scenario(_make_page(_ALIGNMENT_SNAPSHOT, _ALIGNMENT_PROBE), window_width=1440, window_height=900)

    def test_d_la6_the_activity_line_starts_at_the_title_left_edge_whatever_the_chip_width(self) -> None:
        for surface, surface_label in (("list", "카드 목록 줄(320px)"), ("modal", "카드 상세보기 카드")):
            rows = self.result[surface]
            self.assertEqual(set(rows), {run.agent_id for run in _ALIGNMENT_RUNS}, f"{surface_label}: 프로브가 두 실행 줄을 다 읽지 못함(D-LA6 사전조건)")
            chip_widths = [row["chipWidth"] for row in rows.values()]
            self.assertGreater(max(chip_widths) - min(chip_widths), _MIN_CHIP_WIDTH_GAP_PX, f"{surface_label}: 두 칩 폭이 비슷함(D-LA6 사전조건)")
            for run_id, row in rows.items():
                with self.subTest(surface=surface_label, run=run_id):
                    self.assertAlmostEqual(row["activityLeft"], row["titleLeft"], delta=_GEOMETRY_TOLERANCE_PX, msg="활동 줄 왼쪽이 같은 행 제목 왼쪽과 다름(D-LA6)")
                    self.assertGreater(row["activityLeft"], row["chipLeft"] + _GEOMETRY_TOLERANCE_PX, "활동 줄 왼쪽이 칩 왼쪽보다 오른쪽이 아님(D-LA6)")
                    self.assertGreaterEqual(row["activityTop"], row["titleBottom"] - _GEOMETRY_TOLERANCE_PX, "활동 줄이 제목 아래가 아님(D-LA6)")

    def test_d_la6_the_detail_view_title_wraps_and_the_activity_still_sits_below_all_of_it(self) -> None:
        # 사전조건 — 상세보기 카드의 제목은 여러 줄이고(목록은 한 줄 말줄임) 그래도 활동 줄은 제목 전체 아래·같은 왼쪽에 선다(MX9 와 함께 쓴다).
        for run_id in (run.agent_id for run in _ALIGNMENT_RUNS):
            with self.subTest(run=run_id):
                listed, modal = self.result["list"][run_id], self.result["modal"][run_id]
                self.assertGreater(modal["titleHeight"], listed["titleHeight"] * 1.5, "사전조건: 상세보기 제목이 여러 줄로 줄바꿈되지 않음(D-LA6)")
                self.assertGreaterEqual(modal["activityTop"], modal["titleBottom"] - _GEOMETRY_TOLERANCE_PX, "활동 줄이 줄바꿈된 제목 전체의 아래가 아님(D-LA6)")


# D-LA9 — 폴링 갱신이 활동 줄을 새로 만든다(맞대기가 새 자식을 받아들이고, 실행 줄 노드는 그대로 산다).
_POLL_RUN_ID = "poll-run"
_POLL_BACKGROUND_ID = "poll-background"
_POLL_ACTIVITY = _activity(pending_count=1, pending_tool_kind="run", pending_since_ago_ms=4 * _MINUTE_MS, output=_output(_MINUTE_MS))


def _poll_snapshot(activity, output):
    run_session = _session_with("poll-session", "working", "working", agent_runs=(_run(_POLL_RUN_ID, activity),))
    background_session = _session_with(_POLL_BACKGROUND_ID, "background", "idle", background_wait=_background_wait(output))
    return _snapshot((_project(_PROJECT_PATH, "activity", "working", (run_session, background_session)),))


# 응답은 트리거 직전에 심는다 — 헤드리스 dump-dom 이 사람 조작 없이 poll() 을 먼저 한 번 돌릴 때가 있어, 페이지 로드부터 심어 두면 그 우연한
# 호출이 「처음 화면」을 이미 갱신된 모양으로 바꾼다(test_hub_template_dom.py D1 이 실측으로 남긴 함정). 그때까지는 빈 응답(무해한 no-op)이다.
_POLL_PROBE = """
var app = document.getElementById('dzh-app');
function readRow(){ return app.querySelector('.agent-run[data-render-key="%s"]'); }
function texts(selector){ return Array.prototype.map.call(app.querySelectorAll(selector), function(el){ return el.textContent; }); }
var row = readRow();
var before = {runClass: row.className, runActivity: texts('.agent-run-activity'), sessionActivity: texts('.session-activity')};
window.__mockFetchResponseText = %s;
await __triggerPoll();
var rowAfter = readRow();
__probeResult({
  before: before,
  after: {runClass: rowAfter.className, runActivity: texts('.agent-run-activity'), sessionActivity: texts('.session-activity')},
  rowNodeKept: row === rowAfter && row.isConnected,
});
""" % (_POLL_RUN_ID, safe_js_string_literal(minimal_data_document(_poll_snapshot(_POLL_ACTIVITY, _output(_MINUTE_MS)))))


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubActivityPollDomTest(unittest.TestCase):
    """활동이 새로 생긴 폴링 응답 — 근거는 PRP 결정 LA9·LA10, 맞대기(PU1)."""

    def test_d_la9_a_poll_that_brings_activity_adds_the_lines_without_replacing_the_row(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")
        result = run_scenario(_make_page(_poll_snapshot(None, None), _POLL_PROBE), window_width=1440, window_height=900)
        self.assertEqual(result["before"], {"runClass": "agent-run", "runActivity": [], "sessionActivity": []}, "사전조건: 처음 화면에 활동이 있음(D-LA9)")
        self.assertEqual(result["after"]["runClass"], "agent-run agent-run-with-activity", "폴링 뒤 실행 줄에 modifier 가 안 붙음(D-LA9)")
        self.assertEqual(result["after"]["runActivity"], ["명령 실행 중 · 4분째 · 출력 1분 전"], "폴링 뒤 활동 줄이 안 생김(D-LA9)")
        self.assertEqual(result["after"]["sessionActivity"], ["출력 1분 전 갱신"], "폴링 뒤 세션 출력 갱신이 안 생김(D-LA9)")
        self.assertTrue(result["rowNodeKept"], "활동 줄이 생기며 실행 줄 노드가 갈아 끼워짐(D-LA9 — 맞대기 키가 깨졌다)")


if __name__ == "__main__":
    unittest.main()
