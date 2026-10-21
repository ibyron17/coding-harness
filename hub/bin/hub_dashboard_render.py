"""hub/bin/hub_dashboard_render.py — hub_dashboard_log.py 의 순수 로직 층.

이 모듈은 파일시스템·소켓·프로세스·시각·환경변수에 닿지 않는다(★순수,
tests/hub/test_hub_dashboard_render.py 대상). 입력→출력만 있는 함수만 둔다 — I/O 는
hub_dashboard_log.py(기록기) 와 hub_server.py(요청 시 렌더 서빙, HD5,
docs/prps/dashboard-into-hub.md)가 담당한다.

이벤트 스키마·파싱·단계 축약(DashboardEvent·parse_event_lines·derive_phase_states)은
M2 에서 hub_parse.py(★순수, 잎)로 옮겨갔다 — 그 모듈이 이벤트 → Tier1Snapshot 합성의
생산자이기도 해서, 두 소비자(허브 카드 요약과 이 모듈의 화면 렌더)가 같은 파싱·축약
로직을 공유해야 하기 때문이다(단일 출처). 이 모듈은 그 결과(이벤트 열)를 받아 앵커
치환용 마크업으로 그리는 나머지 절반만 남는다: 로그 항목 렌더(render_log_entry_lines)·
상세 마크업(render_detail_html)·PublishedValues 조립(build_published_values)·최종
HTML 조립(render_from_events).
"""

import datetime
import html
import re
from dataclasses import dataclass

from hub_parse import DashboardEvent, TaskProgress, format_event_updated_label, task_progresses

# ---------------------------------------------------------------------------
# 앵커 상수 6종 — render_reissue 가 6개 전부 쓴다(build_published_values 는 간접 경유).
# 템플릿 슬롯의 마크업이 바뀌면 고칠 자리가 여기 한 곳이다. 값은
# hub_dashboard_template.html 의 빈 상태(발행 전 원본) 그대로다. 제목·진행 막대·진행률·단계
# 목록 앵커 4종은 작업 카드 묶음 하나(ANCHOR_TASKS)로 합쳐졌다(결정 MT7 — 카드가 여러 장이면 id 가 겹친다).
# ---------------------------------------------------------------------------

ANCHOR_PROJECT_NAME = '  <span class="project-name" id="dz-project-name">프로젝트</span>'
ANCHOR_TASKS = '  <div id="dz-tasks"></div>'
ANCHOR_IMPL_COUNT = '    <div class="pct" id="dz-impl-count">0/0 · 0%</div>'
ANCHOR_IMPL_TASKS_BLOCK = '    <ol class="steps" id="dz-impl-tasks">\n    </ol>'
ANCHOR_LOG = '    <ul class="log" id="dz-log" data-owner-token="" data-server-port=""></ul>'
ANCHOR_UPDATED = '  <div class="foot" id="dz-updated">갱신: -</div>'

# impl 슬롯이 한 번도 채워지지 않은 대시보드(옛 버전 호환 포함)의 기본값 — 템플릿 원본과 같다.
# build_published_values 는 impl_count_html 을 항상 None 으로 두므로(PRP §6.6 — impl 세부
# 작업 패널은 폐기됐다) render_reissue 는 이 값으로 고정 렌더한다.
_DEFAULT_IMPL_COUNT_HTML = "0/0 · 0%"


@dataclass(frozen=True)
class PublishedValues:
    """render_reissue 가 템플릿에 적용하는 동적 값 전부 — build_published_values 가 조립한다.

    모든 문자열 필드는 **이미 DOM 이스케이프된 텍스트**다(원문 사용자 텍스트는
    DashboardEvent 가 담고, escape_for_dom·render_detail_html 이 렌더 시점에 이스케이프를
    적용한다). None 은 「그 슬롯을 채우지 않는다」를 뜻하며, render_reissue 가 템플릿
    기본값으로 남긴다.
    """

    project_name_html: str | None
    task_block_lines: list[str]  # <div id="dz-tasks"> … </div> 전체(작업 카드 묶음, 결정 MT7)
    impl_count_html: str | None
    impl_block_lines: list[str] | None
    log_owner_token: str
    log_server_port: str
    log_entry_lines: list[str]
    updated_html: str


class AnchorMismatch(Exception):
    """render_reissue 의 앵커가 정확히 1회 등장하지 않을 때 발생한다."""

    def __init__(self, count: int, anchor: str) -> None:
        self.count = count
        self.anchor = anchor
        super().__init__("%d %s" % (count, anchor))


def escape_for_dom(raw: str) -> str:
    """`&`→`&amp;` 를 가장 먼저 적용해 이후 `<`/`>` 치환이 만드는 `&` 를 다시 이스케이프하지
    않는다. 따옴표는 바꾸지 않는다(quote=False) — 이 값들은 속성이 아니라 텍스트 노드에 들어간다.
    """
    return html.escape(raw, quote=False)


def _replace_unique(text: str, replacements: list[tuple[str, str]]) -> str:
    """앵커별 등장 횟수 1을 확인하며 순서대로 치환한다(render_reissue 가 쓴다).

    앵커 등장 횟수가 1이 아니면 그 시점에서 AnchorMismatch 를 일으키고 아무것도 반환하지
    않는다. text 는 str(불변)이므로 예외가 나도 호출자가 든 원본은 그대로다.
    """
    result = text
    for anchor, replacement in replacements:
        found = result.count(anchor)
        if found != 1:
            raise AnchorMismatch(found, anchor.strip()[:56])
        result = result.replace(anchor, replacement)
    return result


# ---------------------------------------------------------------------------
# 재발행 — 렌더 (build_published_values 가 만든 PublishedValues 를 템플릿에 적용한다)
# ---------------------------------------------------------------------------


def _render_log_block(values: PublishedValues) -> str:
    """로그가 비면 `<ul …></ul>` 한 줄로, 아니면 항목을 끼운 뒤 `</ul>` 을 되붙인
    블록으로 렌더한다."""
    opening_tag = (
        '    <ul class="log" id="dz-log" data-owner-token="%s" data-server-port="%s">'
        % (values.log_owner_token, values.log_server_port)
    )
    if not values.log_entry_lines:
        return opening_tag + "</ul>"
    return "\n".join([opening_tag, *values.log_entry_lines, "    </ul>"])


def render_reissue(template_text: str, values: PublishedValues) -> str:
    """현재 템플릿의 앵커 6종을 values 로 치환한 새 문자열을 돌려준다.

    앵커 등장 횟수가 1이 아니면 AnchorMismatch.
    project_name_html 이 None 이면 ValueError — 호출 전에 I/O 층이 채워야 한다.
    """
    if values.project_name_html is None:
        raise ValueError("project_name_html 이 비어 있다 — 호출 전에 I/O 층이 채워야 한다")

    impl_count_html = _DEFAULT_IMPL_COUNT_HTML if values.impl_count_html is None else values.impl_count_html
    impl_tasks_replacement = (
        ANCHOR_IMPL_TASKS_BLOCK if values.impl_block_lines is None else "\n".join(values.impl_block_lines)
    )

    replacements = [
        (ANCHOR_PROJECT_NAME,
         '  <span class="project-name" id="dz-project-name">%s</span>' % values.project_name_html),
        (ANCHOR_TASKS,
         "\n".join(values.task_block_lines)),
        (ANCHOR_IMPL_COUNT,
         '    <div class="pct" id="dz-impl-count">%s</div>' % impl_count_html),
        (ANCHOR_IMPL_TASKS_BLOCK,
         impl_tasks_replacement),
        (ANCHOR_LOG,
         _render_log_block(values)),
        (ANCHOR_UPDATED,
         '  <div class="foot" id="dz-updated">%s</div>' % values.updated_html),
    ]
    return _replace_unique(template_text, replacements)


# ---------------------------------------------------------------------------
# 이벤트 기반 렌더링 — hub_parse 가 파싱·축약한 이벤트 열을 받아 로그·상세 마크업
# (render_detail_html·render_log_entry_lines) → PublishedValues 조립
# (build_published_values) → render_reissue 로 최종 HTML(render_from_events) 순서로 그린다.
# 파일 읽기·세션 ID 판정 같은 I/O 는 이 모듈에 들어오지 않는다 — hub_dashboard_log.py(기록기)
# 와 hub_server.py(요청 시 서빙)의 몫이다.
# ---------------------------------------------------------------------------

# kind → (data-kind 값, 배지 class, 배지 라벨) — hub/README.md 「진행 기록」>「데이터 모델」
# 표 그대로.
_LOG_KIND_DISPLAY: dict[str, tuple[str, str, str]] = {
    "design": ("note", "impl", "설계"),
    "approve": ("note", "impl", "승인"),
    "impl": ("impl", "impl", "구현"),
    "pass": ("review", "pass", "검수 PASS"),
    "fail": ("review", "fail", "검수 FAIL"),
    "commit": ("commit", "commit", "커밋"),
    "note": ("note", "impl", "메모"),
}
_ROUND_TRACKED_KINDS = ("pass", "fail")  # DN5 — 회차는 이 두 종류의 작업별 누적 수다(결정 MT4).
_RECENT_LOG_OPEN_COUNT = 3  # 최신 3건만 <details open> — 「로그 항목 스키마」 절의 기존 UX 그대로.
_NO_DETAIL_TEXT = "(상세 없음)"
_STEP_STATE_LABEL = {"done": "완료", "active": "진행중", "wait": "대기"}
# 세션 ID 앞 8자리를 소유 토큰으로 쓴다(ST3 — 허브 표시와 같은 규칙).
_OWNER_TOKEN_LENGTH = 8


# ---------------------------------------------------------------------------
# 상세 마크업 — render_detail_html. hub/README.md 「진행 기록」의 「상세 마크업」 4단계 규칙을
# 그대로 옮긴다(불변식 10). 순서: 이스케이프 → 블록 분할 → 블록별 <p>/<ul> → 블록 안 백틱 짝짓기.
# ---------------------------------------------------------------------------


def _convert_backtick_code_spans(text: str) -> str:
    """왼쪽부터 짝지어 백틱 구간을 <code> 로 바꾼다. 짝이 없는 마지막 백틱은 그대로 둔다."""
    parts = text.split("`")
    backtick_count = len(parts) - 1
    pair_count = backtick_count // 2
    rendered = [parts[0]]
    for pair_index in range(pair_count):
        rendered.append("<code>%s</code>" % parts[1 + pair_index * 2])
        rendered.append(parts[2 + pair_index * 2])
    if backtick_count % 2 == 1:
        rendered.append("`" + parts[-1])
    return "".join(rendered)


def _split_into_blocks(escaped_text: str) -> list[list[str]]:
    """빈 줄(공백만 있는 줄 포함)을 경계로 블록을 나눈다."""
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for line in escaped_text.splitlines():
        if line.strip() == "":
            if current_block:
                blocks.append(current_block)
                current_block = []
            continue
        current_block.append(line)
    if current_block:
        blocks.append(current_block)
    return blocks


def _is_list_block(block_lines: list[str]) -> bool:
    """블록의 모든 줄이 `- ` 로 시작하면 목록 블록이다."""
    return all(line.startswith("- ") for line in block_lines)


def _render_list_block(block_lines: list[str]) -> str:
    """목록 블록 → `<ul><li>…</li>…</ul>` 하나. 선행 `- ` 는 지운다."""
    items = "".join("<li>%s</li>" % _convert_backtick_code_spans(line[len("- "):]) for line in block_lines)
    return "<ul>%s</ul>" % items


def _render_paragraph_inner(block_lines: list[str]) -> str:
    """블록 안 단일 개행은 보존한다(불변식 10 근거, docs/prps/dashboard-rationale.md#inv10)."""
    return _convert_backtick_code_spans("\n".join(block_lines))


def render_detail_html(detail: str) -> str:
    """상세 마크업 규칙(이스케이프 → 빈 줄로 블록 → `- ` 블록은 <ul>, 그 밖은 <p>, 단일 비목록 블록은
    맨 텍스트 → 블록 안에서만 백틱 짝짓기 → 태그 사이 개행 없음). 빈 입력은 '(상세 없음)'."""
    if not detail:
        return _NO_DETAIL_TEXT
    blocks = _split_into_blocks(escape_for_dom(detail))
    if not blocks:
        return _NO_DETAIL_TEXT
    if len(blocks) == 1 and not _is_list_block(blocks[0]):
        return _render_paragraph_inner(blocks[0])
    return "".join(
        _render_list_block(block) if _is_list_block(block) else "<p>%s</p>" % _render_paragraph_inner(block)
        for block in blocks
    )


# ---------------------------------------------------------------------------
# 단일 행 필드 정규화 — _escape_single_line. title·project·phases 항목·summary 처럼 DOM 에서
# 한 줄 안에 있어야 하는 필드 전용이다(불변식 2·3). 개행이 들어오면 템플릿 자체 폴링(부분
# 치환)이 그 id 를 한 줄로 기대하는 계약이 깨져 단계·항목이 조용히 어긋난다(검수 H1 —
# 실측: summary 에 개행 1개만 있어도 단계 <li> 가 물리적으로 여러 줄로 쪼개져
# 렌더 결과가 그 계약을 어겼다). escape_for_dom 자체에 넣지 않는 이유: 그 함수는 detail
# 경로도 쓰는데 detail 은 개행이 블록 구분자라 보존해야 한다(render_detail_html) — 정규화
# 여부는 필드의 성격에 달렸으므로 호출부에서 선택한다.
# ---------------------------------------------------------------------------

_SINGLE_LINE_NEWLINE_PATTERN = re.compile(r"\r\n|\r|\n")


def _escape_single_line(raw: str) -> str:
    """개행을 공백 1개로 접은 뒤 이스케이프한다. 개행을 그냥 지우면 양쪽 단어가 붙으므로
    (예: "가" + 개행 + "나" → "가나") 삭제 대신 공백으로 접는다."""
    return escape_for_dom(_SINGLE_LINE_NEWLINE_PATTERN.sub(" ", raw))


# ---------------------------------------------------------------------------
# 로그 항목 렌더 — render_log_entry_lines. 형식은 사람이 읽는 화면·필터 스크립트 계약뿐이다.
# ---------------------------------------------------------------------------


def _format_event_clock(time_ms: int) -> str:
    """HH:MM(로컬 시간대). 결정성은 time_ms 라는 기록된 절대 시각을 쓰는 데서 나온다 — 같은
    기계에서 같은 time_ms 를 다시 렌더해도 로컬 변환 문자열은 항상 같다. 시간대를 UTC 로
    고정할 이유는 없다(검수 H4 — 이전 주석은 "결정적 재렌더"의 근거를 이 둘과 혼동해 UTC 고정
    사유로 잘못 들었다. PRP·dashboard-rationale.md 어디에도 UTC 고정 요구는 없다, 검수 확인)."""
    return datetime.datetime.fromtimestamp(time_ms / 1000).strftime("%H:%M")


@dataclass(frozen=True)
class _LogEntryFields:
    """render_log_entry_lines 내부 전용 — 로그 항목 하나를 렌더하기 직전의 값들."""

    seq: int
    time_label: str
    data_kind: str
    badge_class: str
    badge_label: str
    round_number: int | None
    task_label_html: str  # 이스케이프된 작업 이름표. 이름표 없는 항목은 ""(배지 없음)
    summary_html: str
    detail_html: str


def _collect_log_entries(events: tuple[DashboardEvent, ...]) -> list[_LogEntryFields]:
    """로그로 남는 이벤트만 골라 순번(오래된 것부터 1)·작업별 누적 회차를 매긴다."""
    entries: list[_LogEntryFields] = []
    seq = 0
    round_numbers_by_task: dict[str, int] = {}
    for event in events:
        display = _LOG_KIND_DISPLAY.get(event.kind)
        if display is None:
            continue
        seq += 1
        data_kind, badge_class, badge_label = display
        is_round_tracked = event.kind in _ROUND_TRACKED_KINDS
        if is_round_tracked:
            round_numbers_by_task[event.task] = round_numbers_by_task.get(event.task, 0) + 1
        entries.append(
            _LogEntryFields(
                seq=seq,
                time_label=_format_event_clock(event.time_ms),
                data_kind=data_kind,
                badge_class=badge_class,
                badge_label=badge_label,
                round_number=round_numbers_by_task[event.task] if is_round_tracked else None,
                task_label_html=_escape_single_line(event.task),
                summary_html=_escape_single_line(event.summary),
                detail_html=render_detail_html(event.detail),
            )
        )
    return entries


def _render_single_log_entry(entry: _LogEntryFields, is_open: bool) -> list[str]:
    """로그 항목 하나를 줄 목록으로 렌더한다."""
    lines = [
        '      <li class="entry" data-kind="%s" data-seq="%d">' % (entry.data_kind, entry.seq),
        "        <details%s>" % (" open" if is_open else ""),
        "          <summary>",
        '            <span class="time">%s</span>' % entry.time_label,
    ]
    if entry.task_label_html:
        lines.append('            ' + _task_badge_html(entry.task_label_html))
    if entry.round_number is not None:
        lines.append('            <span class="badge round">R%d</span>' % entry.round_number)
    lines.append('            <span class="badge %s">%s</span>' % (entry.badge_class, entry.badge_label))
    lines.append('            <span class="lead">%s</span>' % entry.summary_html)
    lines.append("          </summary>")
    lines.append('          <div class="detail">%s</div>' % entry.detail_html)
    lines.append("        </details>")
    lines.append("      </li>")
    return lines


def render_log_entry_lines(events: tuple[DashboardEvent, ...]) -> list[str]:
    """최신이 위. data-seq 1부터, 최신 3건만 <details open>. 이름표 배지, pass/fail 에 작업별 회차 R{n}."""
    newest_first = list(reversed(_collect_log_entries(events)))
    lines: list[str] = []
    for position, entry in enumerate(newest_first):
        lines.extend(_render_single_log_entry(entry, is_open=position < _RECENT_LOG_OPEN_COUNT))
    return lines


# ---------------------------------------------------------------------------
# 이벤트 → PublishedValues 조립 — build_published_values·render_from_events.
# ---------------------------------------------------------------------------


def _task_badge_html(escaped_label: str) -> str:
    """작업 이름표 배지 — 이름표는 이미 이스케이프된 텍스트다."""
    return '<span class="badge task">%s</span>' % escaped_label


def _render_steps_block(task: TaskProgress) -> list[str]:
    """작업 카드 안 진행 단계 <ol> — 단계 줄은 줄마다 li 하나다(id 는 없다, 결정 MT7)."""
    item_lines = [
        '        <li class="%s"><span class="num">%d</span>%s<span class="chip">%s</span>'
        '<span class="step-detail">%s</span></li>'
        % (
            step.state,
            step.index,
            _escape_single_line(step.name),
            _STEP_STATE_LABEL[step.state],
            _escape_single_line(step.detail),
        )
        for step in task.steps
    ]
    return ['      <ol class="steps">', *item_lines, "      </ol>"]


def _render_open_task_card(task: TaskProgress) -> list[str]:
    """펼친 작업 카드 — 이름표 배지(있을 때만)·제목·진행 막대·진행률·단계 목록."""
    badge = _task_badge_html(_escape_single_line(task.label)) if task.label else ""
    return [
        '    <div class="card task-card">',
        "      <h1>%s%s</h1>" % (badge, _escape_single_line(task.title)),
        '      <div class="bar-outer"><div class="bar-inner" style="width:%d%%"></div></div>' % task.percent,
        '      <div class="pct">%d/%d · %d%%</div>' % (task.completed, task.total, task.percent),
        *_render_steps_block(task),
        "    </div>",
    ]


def _render_folded_task_card(task: TaskProgress) -> list[str]:
    """접힌 작업 카드 — 네이티브 details(키보드·낭독기 지원). 한 줄 요약에 이름표·제목·커밋 배지·진행률."""
    badge = _task_badge_html(_escape_single_line(task.label)) if task.label else ""
    return [
        '    <details class="card task-card task-folded">',
        '      <summary>%s<span class="task-folded-title">%s</span><span class="badge commit">커밋</span>'
        '<span class="task-folded-pct">%d/%d · %d%%</span></summary>'
        % (badge, _escape_single_line(task.title), task.completed, task.total, task.percent),
        *_render_steps_block(task),
        "    </details>",
    ]


def render_task_block_lines(tasks: tuple[TaskProgress, ...]) -> list[str]:
    """작업 카드 묶음 — 펼친 카드는 .card.task-card, 접힌 카드는 details.card.task-card.task-folded(결정 MT7).
    카드는 받은 순서(표시 순서) 그대로 그린다."""
    card_lines = [
        line
        for task in tasks
        for line in (_render_folded_task_card(task) if task.is_folded else _render_open_task_card(task))
    ]
    return ['  <div id="dz-tasks">', *card_lines, "  </div>"]


def build_published_values(events: tuple[DashboardEvent, ...], session_id: str) -> PublishedValues:
    """이벤트 → 앵커 6종 값. impl 슬롯은 None(카드 비움). owner_token = 세션 ID 앞 8자리, server_port = ''."""
    if not events or events[0].kind != "init":
        raise ValueError("events[0] 은 kind == 'init' 이어야 한다 — hub_parse.parse_event_lines 의 계약")
    return PublishedValues(
        project_name_html=_escape_single_line(events[0].project),
        task_block_lines=render_task_block_lines(task_progresses(events)),
        impl_count_html=None,
        impl_block_lines=None,
        log_owner_token=(session_id or "")[:_OWNER_TOKEN_LENGTH],
        log_server_port="",
        log_entry_lines=render_log_entry_lines(events),
        updated_html=format_event_updated_label(events[-1].time_ms),
    )


def render_from_events(template_text: str, events: tuple[DashboardEvent, ...], session_id: str) -> str:
    """= render_reissue(template_text, build_published_values(events, session_id)). AnchorMismatch 전파."""
    return render_reissue(template_text, build_published_values(events, session_id))
