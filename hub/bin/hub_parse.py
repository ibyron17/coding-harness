"""hub_parse.py — 세션별 진행 기록(.claude/dashboards/<세션 ID>.jsonl)을 읽는 순수 파서.

이 모듈은 파일시스템·시각·환경에 닿지 않는다(★순수, tests/hub/test_hub_parse.py 대상).
상태의 단일 출처는 JSONL 이벤트 열이다(docs/prps/dashboard-native-data-source.md DN2·DN3) —
이벤트를 파싱하고(parse_event_lines) 단계 상태를 축약해(derive_phase_states) 허브 카드가
읽는 Tier1Snapshot 을 합성한다(snapshot_from_events). HTML 은 읽지 않는다
(docs/prps/dashboard-into-hub.md HD5~HD7) — 허브 서버가 요청 때마다 이 모듈이 읽은 같은
이벤트를 hub_dashboard_render.render_from_events 로 그려 화면을 서빙하므로, 카드 요약과
화면은 항상 같은 출처에서 나온다.
"""

import datetime
import json
from dataclasses import dataclass
from typing import Literal

StepState = Literal["done", "active", "wait"]

# file_mtime_ms 는 이 모듈이 채우지 않는다(파일시스템 접근은 순수 레이어의 경계 밖이다).
# I/O 레이어(hub_collect.py)가 stat 으로 얻은 실제 mtime 을 dataclasses.replace 로 덮어쓴다.
UNSET_FILE_MTIME_MS = 0

# source_path 도 file_mtime_ms 와 같은 계열이다 — 이 스냅샷을 읽어 온 JSONL 파일의
# 소유 디렉토리는 I/O 레이어(hub_collect.py)만 안다(결정 WT7, docs/prps/hub-worktree-fold.md).
UNSET_SOURCE_PATH = ""


@dataclass(frozen=True)
class StepView:
    """선형 진행 표시의 단계 하나(#dz-step-{n})."""

    index: int
    name: str
    state: StepState
    detail: str
    started_at: str | None  # 현재 렌더 소비자 없음(hub_parse 밖에서 읽는 곳이 없다) — 보존은 문서화된 결정


@dataclass(frozen=True)
class Tier1Snapshot:
    """세션별 진행 기록에서 읽은 진행 상태 전체."""

    title: str
    subtitle: str
    completed: int
    total: int
    percent: int
    steps: tuple[StepView, ...]
    matrix_done: int | None  # 소비자 없음(hub_template 에 matrix 렌더 경로 부재) — 보존은 문서화된 결정(HD6)
    impl_done: int
    impl_total: int
    updated_text: str
    file_mtime_ms: int
    source_path: str = UNSET_SOURCE_PATH   # 이 스냅샷을 읽어 온 JSONL 파일의 **소유 디렉토리**
    # 세션별 파일(.claude/dashboards/<id>.jsonl)의 그 id. source_path 와 같은 계열 —
    # 파서는 채우지 않고 hub_collect 가 dataclasses.replace 로 덮어쓴다(결정 ST10,
    # docs/prps/hub-session-tree-and-per-session-dashboards.md).
    session_id: str | None = None
    # 이 대시보드가 기록하는 **작업이 시작된 시각**(결정 RL8, docs/prps/
    # hub-card-gate-and-run-list-reset.md §3.7) = JSONL 첫 줄(init 이벤트)의 time_ms
    # (docs/prps/dashboard-into-hub.md HD8 — M1 까지는 `/dashboard init` 사이드카 mtime
    # 이었다). snapshot_from_events 가 채운다 — hub_collect 는 이 값을 덮어쓰지 않는다.
    task_started_at_ms: int | None = None
    # 마지막 pass 기록 뒤에 commit 기록이 있는가(결정 LM6, docs/prps/hub-session-row-layout-and-modal-size.md).
    # pass 가 없으면 False. 사실만 싣는다 — 「커밋 전」 칩이 걷힌 뒤(결정 LM12) 현재 화면은 읽지 않는다. 정적 값이라
    # snapshot_content_key 를 흔들지 않는다.
    is_committed: bool = False


# ---------------------------------------------------------------------------
# 이벤트 스키마·파싱 — parse_event_lines. 줄 단위로 fail-open 한다(허브 파서들의 계약 B와
# 같은 태도). hub/README.md 「진행 기록」>「데이터 모델」 표가 이 어휘의 정본이다.
# ---------------------------------------------------------------------------

LOG_EVENT_KINDS = ("design", "approve", "impl", "pass", "fail", "commit", "note")
STEP_STATES = frozenset({"done", "active", "wait"})
_KNOWN_EVENT_KINDS = frozenset({"init", "step", *LOG_EVENT_KINDS})

# time_ms sanity 범위(밀리초) — 2000-01-01 ~ 2100-01-01(UTC, 실측 왕복 확인). datetime.fromtimestamp
# 가 다루는 전체 범위(연도 1~9999)보다 훨씬 좁지만, 이 도구가 다루는 실제 세션은 전부 이 구간
# 안에 있다. 손상된 값(예: 자릿수가 밀린 UNIX ms)이 이 구간을 벗어나면 파싱 단계에서 걸러
# datetime.fromtimestamp 의 예외가 렌더 단계까지 번지지 않게 한다(검수 H2 — 실측:
# time_ms=99999999999999999 한 줄이 "ValueError: year 3170843 is out of range" 로 렌더 전체를
# 깨뜨렸다). 이름·값은 다른 파서(hub_session_facts.py EVENT_TIME_MAX_MS)의 주석이 인용한다 — 옮기며
# 바꾸지 않는다.
_MIN_VALID_TIME_MS = 946_684_800_000  # 2000-01-01T00:00:00Z
_MAX_VALID_TIME_MS = 4_102_444_800_000  # 2100-01-01T00:00:00Z

# init 의 phases 배열 길이 상한(재검수 2회차 RA3 — 실측: 6000단계 × 6000줄 JSONL 이 파싱 1회
# 1.1초. derive_phase_states 가 이벤트마다 길이 P 인 상태 튜플을 새로 만들어(_state_from_
# completed_count) 이벤트 수 × 단계 수에 이차로 든다). 정상 사용은 2~4단계뿐이다
# (hub/rules/dashboard-recording.md 의 `설계|승인|구현|검수`) — 그 값의 8배인 32 를 상한으로
# 두고, 넘으면 init 자체를 무효로 처리해 기존 "init 없음" 경고로 떨어뜨린다.
_MAX_PHASE_COUNT = 32


@dataclass(frozen=True)
class DashboardEvent:
    """JSONL 이벤트 한 줄(hub/README.md 「진행 기록」>「데이터 모델」 표 그대로). phases 는
    tuple[str, ...].

    title·summary·detail 은 원문이다(이스케이프는 렌더 시점 — hub_dashboard_render.escape_for_dom·
    _escape_single_line 이 적용한다). kind 에 해당하지 않는 필드는 기본값(빈 문자열·빈 튜플·0)을
    둔다.
    """

    time_ms: int
    kind: str
    title: str = ""
    phases: tuple[str, ...] = ()
    project: str = ""
    summary: str = ""
    detail: str = ""
    index: int = 0
    state: str = ""


def _parse_init_event(time_ms: int, raw: dict) -> DashboardEvent | None:
    """kind == "init" 한 줄 → DashboardEvent. 필수 필드가 없거나 타입이 다르거나 phases 가
    _MAX_PHASE_COUNT 를 넘으면 None."""
    title, phases, project = raw.get("title"), raw.get("phases"), raw.get("project")
    if not isinstance(title, str) or not isinstance(project, str):
        return None
    if not isinstance(phases, list) or not phases or not all(isinstance(p, str) for p in phases):
        return None
    if len(phases) > _MAX_PHASE_COUNT:
        return None
    return DashboardEvent(time_ms=time_ms, kind="init", title=title, phases=tuple(phases), project=project)


def _parse_step_event(time_ms: int, raw: dict) -> DashboardEvent | None:
    """kind == "step" 한 줄 → DashboardEvent. index·state 가 없거나 형식이 다르면 None."""
    index, state = raw.get("index"), raw.get("state")
    # bool 은 int 의 서브클래스라 isinstance(index, int) 만으로는 {"index": true} 가 index=True
    # (=1) 로 통과한다 — 멤버십 검사(`state not in STEP_STATES`)도 state 가 리스트·dict 면
    # 해시를 시도하다 TypeError: unhashable type 을 던지므로 isinstance(str) 을 먼저 본다
    # (재검수 2회차 RA1).
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    if not isinstance(state, str) or state not in STEP_STATES:
        return None
    return DashboardEvent(time_ms=time_ms, kind="step", index=index, state=state)


def _parse_log_event(time_ms: int, kind: str, raw: dict) -> DashboardEvent | None:
    """design|approve|impl|pass|fail|commit|note 한 줄 → DashboardEvent. detail 은 선택(기본 "")."""
    summary = raw.get("summary")
    detail = raw.get("detail", "")
    if not isinstance(summary, str) or not isinstance(detail, str):
        return None
    return DashboardEvent(time_ms=time_ms, kind=kind, summary=summary, detail=detail)


def _parse_single_event_line(line: str) -> DashboardEvent | None:
    """JSONL 한 줄을 파싱한다. 깨진 줄·모르는 kind·타입 불일치·time_ms 범위 밖은 None(그 줄만 건너뛴다).

    예외를 던지지 않는다(계약 B, hub_session_facts.parse_event_line·hub_live_session.
    parse_live_session_record 와 동형) — 재검수 2회차 RA1 이 실측한 두 병리적 입력을 여기서
    막는다. (1) json.loads 자체가 던지는 ValueError(4,300자리 초과 정수 리터럴의 문자열 변환
    자릿수 한도 — JSONDecodeError 의 상위 클래스라 기존 구문 오류 케이스도 그대로 잡힌다)·
    RecursionError(깊은 중첩, `"["*n`) — 옛 `except json.JSONDecodeError` 는 이 둘을 잡지
    못해 collect_snapshot·서버 응답 전체를 죽였다. (2) kind 자리에 리스트·dict 가 오면
    `kind not in _KNOWN_EVENT_KINDS`(frozenset 멤버십)가 그 값을 해시하려다
    `TypeError: unhashable type` 을 던진다 — 멤버십 검사 전에 isinstance(str) 로 먼저 거른다.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        raw = json.loads(stripped)
    except (ValueError, RecursionError):
        return None
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind not in _KNOWN_EVENT_KINDS:
        return None
    time_ms = raw.get("time_ms")
    # bool 은 int 의 서브클래스지만 여기서는 별도 가드가 필요 없다 — 아래 하한(_MIN_VALID_TIME_MS,
    # 2000년) 이 bool 값 0·1 을 이미 걸러낸다(검수 3회차 RC3, 실측: 이 가드를 지워도 유닛 테스트
    # 전부 통과). hub_session_facts.parse_event_line 은 하한이 0(0 < raw_time)이라 bool 가드가
    # 실제로 필요하지만(그 함수 주석 참고) 여기는 하한이 훨씬 커서 사정이 다르다 — 대칭을
    # 이유로 되살리지 않는다.
    if not isinstance(time_ms, int):
        return None
    if not (_MIN_VALID_TIME_MS <= time_ms <= _MAX_VALID_TIME_MS):
        return None
    if kind == "init":
        return _parse_init_event(time_ms, raw)
    if kind == "step":
        return _parse_step_event(time_ms, raw)
    return _parse_log_event(time_ms, kind, raw)


def _find_last_init_index(events: list[DashboardEvent]) -> int | None:
    """events 중 kind == "init" 인 마지막 인덱스. 하나도 없으면 None."""
    last_index = None
    for index, event in enumerate(events):
        if event.kind == "init":
            last_index = index
    return last_index


def parse_event_lines(text: str) -> tuple[DashboardEvent, ...]:
    """JSONL 본문 → 이벤트 열. 줄 단위 fail-open 방식('\\n' 분할, U+2028 보존). 마지막 init 이후만."""
    events: list[DashboardEvent] = []
    # JSONL 의 줄 구분자는 "\n" 하나뿐이다(재검수 MEDIUM — 실측: str.splitlines() 는 그보다
    # 넓어 U+2028(LINE SEPARATOR)·U+2029(PARAGRAPH SEPARATOR) 도 줄 경계로 본다. summary·
    # detail·title 값에 그 문자가 하나라도 있으면 JSONL 한 줄이 물리적으로 둘로 쪼개져 양쪽
    # 다 json.loads 에 실패하고, 그 이벤트가 오류 없이 통째로 사라진다). split("\n") 은 \r\n
    # 의 잔여 "\r" 을 _parse_single_event_line 의 strip() 으로 흡수하고, 파일 끝 개행이 만드는
    # 마지막 빈 문자열도 같은 strip 뒤 빈 줄 처리로 흡수한다.
    for line in text.split("\n"):
        event = _parse_single_event_line(line)
        if event is not None:
            events.append(event)
    last_init_index = _find_last_init_index(events)
    if last_init_index is None:
        return ()
    return tuple(events[last_init_index:])


# ---------------------------------------------------------------------------
# 단계 상태 파생 — derive_phase_states(DN4). `log` 의 종류가 단계 전이를 함의하고, `step` 은
# 비표준 단계 목록 전용으로 그 인덱스 하나만 명시 갱신한다(같은 reducer 의 한 갈래).
# ---------------------------------------------------------------------------

_PHASE_NAME_BY_COMPLETION_KIND = {"design": "설계", "approve": "승인", "impl": "구현"}


def _state_from_completed_count(phase_count: int, completed_count: int) -> tuple[str, ...]:
    """앞에서부터 completed_count 개는 done, 그다음 1개는 active, 나머지는 wait."""
    return tuple(
        "done" if index < completed_count else "active" if index == completed_count else "wait"
        for index in range(phase_count)
    )


def _apply_log_kind_transition(
    phases: tuple[str, ...], state: tuple[str, ...], event: DashboardEvent
) -> tuple[str, ...]:
    """DN4 — `log` 종류 하나가 함의하는 단계 전이. pass·fail 은 이름과 무관하게 위치로 정해진다."""
    if event.kind == "pass":
        return _state_from_completed_count(len(phases), len(phases))
    if event.kind == "fail":
        return _state_from_completed_count(len(phases), max(len(phases) - 2, 0))
    phase_name = _PHASE_NAME_BY_COMPLETION_KIND.get(event.kind)
    if phase_name is not None and phase_name in phases:
        return _state_from_completed_count(len(phases), phases.index(phase_name) + 1)
    return state


def derive_phase_states(phases: tuple[str, ...], events: tuple[DashboardEvent, ...]) -> tuple[str, ...]:
    """DN4 축약기. 각 단계의 'done'|'active'|'wait'. 활성은 첫 미완료 하나뿐."""
    state = _state_from_completed_count(len(phases), 0)
    for event in events:
        if event.kind != "step":
            state = _apply_log_kind_transition(phases, state, event)
        elif 1 <= event.index <= len(phases):
            state = tuple(
                event.state if index == event.index - 1 else value for index, value in enumerate(state)
            )
    return state


def latest_log_summary(events: tuple[DashboardEvent, ...]) -> str:
    """가장 최근 로그 요약 원문(DN6). 없으면 ''. hub_dashboard_render 와 이 값을 공유해
    카드 요약과 화면의 활성 단계 상세가 항상 같은 텍스트를 보인다."""
    for event in reversed(events):
        if event.kind in LOG_EVENT_KINDS:
            return event.summary
    return ""


def is_commit_logged_after_last_pass(events: tuple[DashboardEvent, ...]) -> bool:
    """마지막 pass 기록 뒤에 commit 기록이 있는가(결정 LM6). pass 가 없으면 False."""
    last_pass_index = None
    for index, event in enumerate(events):
        if event.kind == "pass":
            last_pass_index = index
    if last_pass_index is None:
        return False
    return any(event.kind == "commit" for event in events[last_pass_index + 1 :])


_UPDATED_LABEL_PREFIX = "갱신: "


def format_event_updated_label(time_ms: int) -> str:
    """"갱신: YYYY-MM-DD HH:MM"(로컬 시간대) — hub_dashboard_render 의 로그 시각 포맷과 같은
    이유로 로컬 시간대를 쓴다(결정성은 time_ms 라는 기록된 절대 시각에서 나온다)."""
    moment = datetime.datetime.fromtimestamp(time_ms / 1000)
    return _UPDATED_LABEL_PREFIX + moment.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# 이벤트 → Tier1Snapshot 합성 — snapshot_from_events·parse_dashboard_jsonl.
# ---------------------------------------------------------------------------

_PERCENT_ROUND_BASE = 100  # P = round(완료 수 / 단계 수 × 100) 산식의 배수(매직 넘버 회피)


def snapshot_from_events(events: tuple[DashboardEvent, ...]) -> Tier1Snapshot:
    """이벤트 열 → Tier1Snapshot(hub/README.md 「진행 기록」>「데이터 모델」 대응).
    events[0] 은 init 이어야 한다(parse_event_lines 계약)."""
    init_event = events[0]
    later_events = events[1:]
    phase_states = derive_phase_states(init_event.phases, later_events)
    total = len(phase_states)
    completed = sum(1 for state in phase_states if state == "done")
    percent = round(completed * _PERCENT_ROUND_BASE / total) if total else 0
    active_detail = latest_log_summary(later_events)
    steps = tuple(
        StepView(
            index=index + 1,
            name=name,
            state=state,
            detail=active_detail if state == "active" else "",
            started_at=None,
        )
        for index, (name, state) in enumerate(zip(init_event.phases, phase_states))
    )
    return Tier1Snapshot(
        title=init_event.title,
        subtitle="",
        completed=completed,
        total=total,
        percent=percent,
        steps=steps,
        matrix_done=None,
        impl_done=0,
        impl_total=0,
        updated_text=format_event_updated_label(events[-1].time_ms),
        file_mtime_ms=UNSET_FILE_MTIME_MS,
        task_started_at_ms=init_event.time_ms,
        is_committed=is_commit_logged_after_last_pass(later_events),
    )


def parse_dashboard_jsonl(text: str) -> Tier1Snapshot | None:
    """= snapshot_from_events(parse_event_lines(text)); init 이 없으면 None(호출자가 경고 후 건너뛴다)."""
    events = parse_event_lines(text)
    if not events:
        return None
    return snapshot_from_events(events)
