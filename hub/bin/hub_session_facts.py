"""hub_session_facts.py — 훅 이벤트를 세션 사실로 접는 순수 로직.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_session_facts.py
대상). `hub_transcript`(오류 종류 정규화) 외 허브 모듈을 임포트하지 않는다(결정 BW11,
docs/prps/hub-subagent-background-pause.md — T25-253).

`hub_session.py`("훅 이벤트를 세션 사실로 접고, 그 사실을 표시 상태로 판정하는 순수 로직")의
앞 절반이었다 — 800줄 상한(T25-100) 에스컬레이션(결정 RI13)을 이행한 첫 단계(M1, 결정 BW11)로
분리됐다. 이 분리는 동작을 한 글자도 바꾸지 않는다: 이동한 심볼은 시그니처·본문 그대로다. 두
모듈의 계약은 이 모듈이 만드는 `SessionFacts` 하나다 — `hub_session.py` 가 그 결과를 받아
표시 상태로 판정한다.
"""

import json
import re
from dataclasses import dataclass
from typing import Literal, Sequence

from hub_transcript import UNKNOWN_ERROR_KIND, normalize_error_kind

STOP_FAILURE_EVENT_NAME = "StopFailure"

# ---- 백그라운드 대기 보고(결정 BW2·BW3, docs/prps/hub-subagent-background-pause.md) ----
# Stop·SubagentStop 만 background_tasks·session_crons 를 싣는다(호스트 계약, §1.3-1) — 그
# 밖의 이벤트는 이 보고를 갖지 않는다(BW3 표).
BACKGROUND_REPORTING_EVENT_NAMES: frozenset[str] = frozenset({"Stop", "SubagentStop"})
# ERROR_KIND_PATTERN(hub_transcript.py)과 같은 모양(BW2) — 호스트 라벨을 정규화한 결과이자
# 이벤트 로그에서 다시 읽을 때의 재검증 패턴이다.
BACKGROUND_TASK_TYPE_PATTERN = re.compile(r"\A[a-z_]{1,32}\Z")
UNKNOWN_BACKGROUND_TASK_TYPE = "unknown"
# 훅이 분류하는 작업 수 상한 — 훅은 수 ms 안에 끝나야 한다(병리적 입력 방어선, BW2).
BACKGROUND_TASK_SCAN_MAX = 256
# 이벤트 줄에 싣는 종류 수 상한(unknown 포함) — 줄이 짧아야 동시 append 가 안전하다(BW2).
BACKGROUND_TASK_KIND_MAX = 8
# 개수·1회성 예약 수 상한 — 자릿수 폭탄 방어(재검증 쪽도 같은 값, BW2).
BACKGROUND_COUNT_MAX = 999


@dataclass(frozen=True)
class BackgroundReport:
    """Stop·SubagentStop 이 보고한, 세션(부모) 범위 진행 중 백그라운드 작업의 종류별 개수와
    1회성 예약 수(BW2·BW3). SubagentStop 이 실어도 그 서브에이전트 것만이 아니다 — 호스트의
    작업 등록소가 세션 하나이기 때문이다(§1.3-4)."""

    reported_at_ms: int
    task_counts: tuple[tuple[str, int], ...]  # (정규화된 종류, 개수 1..999) — 종류 오름차순(결정적)
    wakeup_count: int                         # session_crons 중 recurring 이 false 인 항목 수 0..999


def normalize_background_task_type(value: object) -> str:
    """호스트 background_tasks[].type 라벨을 닫힌 모양으로 접는다.

    문자열이 아니면 곧바로 unknown. 문자열이면 소문자화하고 공백·하이픈을 밑줄로 바꾼 뒤
    BACKGROUND_TASK_TYPE_PATTERN 을 통과해야 한다 — 아니면 unknown. 호스트 라벨 목록의
    사본을 두지 않는다(형태 검사만으로 충분 — 호스트가 종류를 늘려도 유지 비용 0)."""
    if not isinstance(value, str):
        return UNKNOWN_BACKGROUND_TASK_TYPE
    normalized = re.sub(r"[ \-]", "_", value.lower())
    return normalized if BACKGROUND_TASK_TYPE_PATTERN.match(normalized) else UNKNOWN_BACKGROUND_TASK_TYPE


# ---- 입력 ----
@dataclass(frozen=True)
class HookEvent:
    """이벤트 로그 한 줄이 나타내는 훅 이벤트 하나."""

    received_at_ms: int
    hook_event_name: str
    session_id: str
    cwd: str
    source: str | None
    reason: str | None
    agent_id: str | None
    agent_type: str | None
    error_kind: str | None = None   # 이벤트 로그 "er" — StopFailure 에만 있다(RI7)
    background_report: BackgroundReport | None = None   # 이벤트 로그 "bt"·"sw" 가 있는 줄만(BW2)


# ---- 사실(fact) ----
@dataclass(frozen=True)
class SubagentFact:
    """서브에이전트 실행 1건."""

    agent_id: str
    agent_type: str
    started_at_ms: int          # 마지막 (재)시작 — 재개되면 그 시각으로 덮인다
    ended_at_ms: int | None
    # 같은 agent_id 의 SubagentStart 재발화 수(결정 TF7, docs/prps/hub-agent-title-and-excerpt-freshness.md) — 호스트는
    # SendMessage 로 재개할 때도 SubagentStart 를 같은 id 로 다시 낸다(훅 문서 SubagentStart). 0 = 재개된 적 없음. 이벤트
    # 창(오늘+어제) 밖의 재개는 세지 못한다(과소 집계). 맨 뒤·기본값이라 기존 생성 지점이 무해하다.
    resume_count: int = 0


@dataclass(frozen=True)
class FailedTurn:
    """메인 턴이 API 오류로 끝났다는 훅 사실(StopFailure, agent_id 없음, 결정 RI1·RI4)."""

    error_kind: str
    failed_at_ms: int


@dataclass(frozen=True)
class SessionFacts:
    """한 세션의 이벤트를 접어 만든 사실. 표시 판정의 입력이다."""

    session_id: str
    cwd: str
    # 이 창에서 관측된 모든 cwd. 첫 관측 순서, 중복 제거, **기본값 없음**(결정 WT19,
    # docs/prps/hub-worktree-fold.md). observed_cwds[0] == cwd 가 언제나 참이다 — 둘 다
    # 내부 이벤트 필터보다 앞에서 정해진다. `EnterWorktree` 가 살아 있는 세션의 cwd 를
    # 바꾸므로(E2) `cwd` 하나로는 "이 세션이 어디서 일했는가"를 답할 수 없다. 티어 1
    # 후보(결정 WT16)와 GN 세대 판정(결정 WT18)이 이 값을 쓴다.
    observed_cwds: tuple[str, ...]
    started_at_ms: int
    last_event_at_ms: int
    last_event_name: str
    turn_state: Literal["running", "ended"]
    ended_at_ms: int | None
    subagents: tuple[SubagentFact, ...]
    # 마지막 UserPromptSubmit 훅의 received_at_ms(결정 RL1,
    # docs/prps/hub-card-gate-and-run-list-reset.md §3.1) — 서브에이전트 디스패치는 이
    # 훅을 내지 않으므로 "사람이 이 세션에 말을 걸었다"와 1:1 이다. 실행 목록 경계
    # (previous_task_boundary_ms)의 폴백 입력이다. model·workflow 와 같은 계열의 부가
    # 정보라 기본값을 둔다(정체성 필드가 아니다 — 프롬프트 0건인 세션도 정당하다). 맨 뒤에
    # 두면 기존 SessionFacts(...) 생성 지점(테스트)이 무해하다.
    last_prompt_at_ms: int | None = None
    # 메인 턴이 API 오류로 끝났다는 최신 사실(결정 RI1·RI4) — UserPromptSubmit·Stop 이 지운다.
    # last_prompt_at_ms 와 같은 계열(부가 정보, 기본값 있음)이라 맨 뒤에 둔다.
    failed_turn: FailedTurn | None = None
    # 가장 최근 추적 이벤트가 Stop·SubagentStop 이면 그 보고, 아니면 None(결정 BW3) — 세션
    # (부모) 범위의 "지금 유효한" 백그라운드 작업 사진이다. failed_turn 과 같은 계열(부가
    # 정보, 기본값 있음)이라 맨 뒤에 둔다.
    background_report: BackgroundReport | None = None


# ---- 내부 이벤트 필터 ----
def is_internal_session_start(event: HookEvent) -> bool:
    """compact 등 CLI 내부 사유로 발생한 SessionStart 인가."""
    return event.hook_event_name == "SessionStart" and event.source == "compact"


def is_untracked_internal_subagent_stop(
    event: HookEvent, known_agent_ids: frozenset[str]
) -> bool:
    """agent_type 이 비어 있고 대응하는 SubagentStart 를 본 적 없는 SubagentStop 인가."""
    return (
        event.hook_event_name == "SubagentStop"
        and not (event.agent_type or "")
        and (event.agent_id or "") not in known_agent_ids
    )


# ---- 이벤트 파싱 ----
# t 상한(ms) — 2100-01-01T00:00:00Z. hub_parse.py._MAX_VALID_TIME_MS 와 같은 값
# (결합을 피하려 import 하지 않는다). 하한 0 은 음수·자릿수 폭탄만 막는다(그럴듯함 검사 아님).
EVENT_TIME_MAX_MS = 4_102_444_800_000


def _parse_background_report(payload: dict, received_at_ms: int) -> BackgroundReport | None:
    """이벤트 줄의 "bt"·"sw" 를 재검증해 BackgroundReport 로 접는다(BW2 방어 재검증 — 옛
    줄·찢긴 줄이 섞인다).

    둘 다 없으면 None. "bt" 는 dict·키 수 ≤ BACKGROUND_TASK_KIND_MAX·키가
    BACKGROUND_TASK_TYPE_PATTERN 통과·값이 bool 이 아닌 1..BACKGROUND_COUNT_MAX 범위의
    int 여야 한다. "sw" 는 bool 이 아닌 0..BACKGROUND_COUNT_MAX 범위의 int 여야 한다.
    하나라도 형태 위반이면 보고 전체를 버린다(None) — 한쪽 키만 있으면 다른 쪽은 빈 값으로
    본다(빈 "bt"={} 는 부재가 아니라 "진행 중인 것 없음"이라는 유효한 빈 보고다)."""
    raw_task_counts = payload.get("bt")
    raw_wakeup_count = payload.get("sw")
    if raw_task_counts is None and raw_wakeup_count is None:
        return None
    task_counts: list[tuple[str, int]] = []
    if raw_task_counts is not None:
        if not isinstance(raw_task_counts, dict) or len(raw_task_counts) > BACKGROUND_TASK_KIND_MAX:
            return None
        for task_type, count in raw_task_counts.items():
            if not isinstance(task_type, str) or not BACKGROUND_TASK_TYPE_PATTERN.match(task_type):
                return None
            if isinstance(count, bool) or not isinstance(count, int) or not (1 <= count <= BACKGROUND_COUNT_MAX):
                return None
            task_counts.append((task_type, count))
    wakeup_count = 0
    if raw_wakeup_count is not None:
        if isinstance(raw_wakeup_count, bool) or not isinstance(raw_wakeup_count, int) \
                or not (0 <= raw_wakeup_count <= BACKGROUND_COUNT_MAX):
            return None
        wakeup_count = raw_wakeup_count
    return BackgroundReport(
        reported_at_ms=received_at_ms, task_counts=tuple(sorted(task_counts)), wakeup_count=wakeup_count,
    )


def parse_event_line(line: str) -> HookEvent | None:
    """이벤트 로그 한 줄을 파싱한다. 예외를 던지지 않는다 — 깨진 줄, 범위를 벗어난 t, 문자열이
    아닌 선택 필드는 None(호출자가 건너뛴다)."""
    try:
        payload = json.loads(line)
    except (ValueError, RecursionError, TypeError):  # 자릿수 한도·중첩 한도는 hub_live_session 참고
        return None
    if not isinstance(payload, dict):
        return None
    try:
        hook_event_name = str(payload["e"])
        session_id = str(payload["s"])
        cwd = str(payload["c"])
    except (KeyError, TypeError, ValueError):
        return None
    raw_time = payload.get("t")
    if isinstance(raw_time, bool) or not isinstance(raw_time, int) or not (0 < raw_time <= EVENT_TIME_MAX_MS):
        return None
    # "er" 를 normalize_error_kind 로 다시 거른다(방어 재검증 — 이벤트 로그는 우리 파일이지만
    # 옛 줄·찢긴 줄이 섞인다). 키 자체가 없으면(부재) None 그대로 둔다 — normalize_error_kind
    # 를 거치면 "unknown"이 되어 "부재"와 "형태 위반"을 더 이상 구별할 수 없다(F8).
    raw_error_kind = payload.get("er")
    error_kind = normalize_error_kind(raw_error_kind) if raw_error_kind is not None else None
    return HookEvent(
        received_at_ms=raw_time,
        hook_event_name=hook_event_name,
        session_id=session_id,
        cwd=cwd,
        source=payload.get("so") if isinstance(payload.get("so"), str) else None,
        reason=payload.get("r") if isinstance(payload.get("r"), str) else None,
        agent_id=payload.get("ai") if isinstance(payload.get("ai"), str) else None,
        agent_type=payload.get("at") if isinstance(payload.get("at"), str) else None,
        error_kind=error_kind,
        background_report=_parse_background_report(payload, raw_time),
    )


# ---- 세션 사실 접기 ----
@dataclass
class _MutableSubagent:
    agent_type: str
    started_at_ms: int
    ended_at_ms: int | None
    resume_count: int = 0


@dataclass
class _MutableSession:
    cwd: str
    observed_cwds: list[str]
    started_at_ms: int
    last_event_at_ms: int
    last_event_name: str
    turn_state: Literal["running", "ended"]
    ended_at_ms: int | None
    subagents: dict[str, _MutableSubagent]
    known_agent_ids: set[str]
    last_prompt_at_ms: int | None
    failed_turn: FailedTurn | None
    background_report: BackgroundReport | None


def _handle_subagent_start(session: _MutableSession, event: HookEvent) -> None:
    """같은 id 의 항목이 이미 있으면 재개다(결정 TF7) — 항목은 덮어써 시작 시각을 재개 시각으로 바꾸고 종료를 지우되 재개 횟수를 잇는다.
    Stop 이 먼저 와서 생긴 합성 항목도 앞선 Start 를 뜻하므로 이어 온 Start 는 재개다."""
    agent_id = event.agent_id or ""
    session.known_agent_ids.add(agent_id)
    earlier = session.subagents.get(agent_id)
    session.subagents[agent_id] = _MutableSubagent(
        agent_type=event.agent_type or "",
        started_at_ms=event.received_at_ms,
        ended_at_ms=None,
        resume_count=0 if earlier is None else earlier.resume_count + 1,
    )


def _handle_subagent_stop(session: _MutableSession, event: HookEvent) -> None:
    agent_id = event.agent_id or ""
    existing = session.subagents.get(agent_id)
    if existing is not None:
        existing.ended_at_ms = event.received_at_ms
        return
    session.subagents[agent_id] = _MutableSubagent(
        agent_type=event.agent_type or "",
        started_at_ms=event.received_at_ms,
        ended_at_ms=event.received_at_ms,
    )


def _handle_stop_failure(session: _MutableSession, event: HookEvent) -> None:
    """StopFailure 를 세션 사실에 반영한다(결정 RI11).

    `agent_id` 가 있으면 서브에이전트 문맥이다 — 그 실행이 `SubagentStart` 로 이미 알려져
    있고 아직 미종료면 `ended_at_ms` 를 채운다. 모르는 id 면 무시한다(유령 실행 방지 —
    `is_untracked_internal_subagent_stop` 과 같은 정신). 어느 쪽이든 메인 턴(`turn_state`·
    `failed_turn`)은 건드리지 않는다 — 이 StopFailure 는 서브에이전트에 대한 것이지 메인
    턴에 대한 것이 아니기 때문이다.

    `agent_id` 가 없으면 메인 스레드다 — Stop 대신 온 것이므로 턴을 닫고(`turn_state="ended"`),
    최신 오류로 `failed_turn` 을 갱신한다(`error_kind` 부재는 UNKNOWN_ERROR_KIND 로 접는다).
    """
    agent_id = event.agent_id
    if agent_id:
        existing = session.subagents.get(agent_id)
        if existing is not None and existing.ended_at_ms is None:
            existing.ended_at_ms = event.received_at_ms
        return
    session.turn_state = "ended"
    session.failed_turn = FailedTurn(
        error_kind=event.error_kind or UNKNOWN_ERROR_KIND, failed_at_ms=event.received_at_ms
    )


def _apply_tracked_event(session: _MutableSession, event: HookEvent) -> None:
    """필터를 통과한(내부 이벤트가 아닌) 이벤트를 세션 사실에 반영한다."""
    # BW3 — 가장 최근 추적 이벤트가 Stop·SubagentStop 이면 그 보고, 그 밖의 추적 이벤트는
    # 지운다. 분기마다 흩어 쓰지 않고 맨 앞 한 줄로 두는 이유: 분기 하나를 빠뜨리면 낡은
    # 보고가 살아남는다(docs/prps/hub-subagent-background-pause.md GOTCHA 12).
    session.background_report = (
        event.background_report if event.hook_event_name in BACKGROUND_REPORTING_EVENT_NAMES else None
    )
    if event.hook_event_name == "UserPromptSubmit":
        session.turn_state = "running"
        session.last_prompt_at_ms = event.received_at_ms
        session.failed_turn = None   # 사용자가 다시 지시하면 원래 판정으로 돌아간다(RI4)
    elif event.hook_event_name == "Stop":
        session.turn_state = "ended"
        session.failed_turn = None   # RI4 — 정상 종료도 미해결 오류를 지운다
    elif event.hook_event_name == "SessionEnd":
        session.ended_at_ms = event.received_at_ms
    elif event.hook_event_name == "SessionStart":
        # 재부착(resume·startup·clear)은 "이 세션이 다시 살아났다"는 유일한 권위 있는 신호다
        # (결정 RV1, docs/prps/hub-session-revival-and-stale-tier1.md). compact 는 이 함수에
        # 도달하지 못한다(build_session_facts 의 필터가 is_internal_session_start 로 앞서
        # continue 한다) — 그 필터가 곧 부활 오발동을 막는 안전판이다. failed_turn 은 여기서
        # 지우지 않는다(RI4) — resume 은 대화가 끊긴 채라는 사실을 바꾸지 않는다.
        session.ended_at_ms = None
    elif event.hook_event_name == "SubagentStart":
        _handle_subagent_start(session, event)
    elif event.hook_event_name == "SubagentStop":
        _handle_subagent_stop(session, event)
    elif event.hook_event_name == STOP_FAILURE_EVENT_NAME:
        _handle_stop_failure(session, event)


def _new_session_builder(event: HookEvent) -> _MutableSession:
    return _MutableSession(
        cwd=event.cwd,
        observed_cwds=[],
        started_at_ms=event.received_at_ms,
        last_event_at_ms=event.received_at_ms,
        last_event_name=event.hook_event_name,
        turn_state="ended",
        ended_at_ms=None,
        subagents={},
        known_agent_ids=set(),
        last_prompt_at_ms=None,
        failed_turn=None,
        background_report=None,
    )


def _freeze_session(session_id: str, session: _MutableSession) -> SessionFacts:
    subagents = tuple(
        SubagentFact(
            agent_id=agent_id,
            agent_type=sub.agent_type,
            started_at_ms=sub.started_at_ms,
            ended_at_ms=sub.ended_at_ms,
            resume_count=sub.resume_count,
        )
        for agent_id, sub in session.subagents.items()
    )
    return SessionFacts(
        session_id=session_id,
        cwd=session.cwd,
        observed_cwds=tuple(session.observed_cwds),
        started_at_ms=session.started_at_ms,
        last_event_at_ms=session.last_event_at_ms,
        last_event_name=session.last_event_name,
        turn_state=session.turn_state,
        ended_at_ms=session.ended_at_ms,
        subagents=subagents,
        last_prompt_at_ms=session.last_prompt_at_ms,
        failed_turn=session.failed_turn,
        background_report=session.background_report,
    )


def build_session_facts(events: Sequence[HookEvent]) -> dict[str, SessionFacts]:
    """시간순 이벤트 목록을 세션별 사실로 접는다. 내부 이벤트 필터를 여기서 적용한다."""
    builders: dict[str, _MutableSession] = {}
    for event in events:
        session = builders.get(event.session_id)
        if session is None:
            session = _new_session_builder(event)
            builders[event.session_id] = session
        session.last_event_at_ms = event.received_at_ms
        session.last_event_name = event.hook_event_name
        # observed_cwds 누적은 내부 이벤트 필터보다 앞이다(결정 WT19) — cwd 도 필터 이전
        # (빌더 생성 시점)에 정해지므로 두 값의 모집단이 같아 observed_cwds[0] == cwd 가
        # 언제나 참이다. 내부 이벤트(compact 등)도 실제로 관측된 cwd 이므로 여기서 놓치면
        # 안 된다(U-29).
        if event.cwd not in session.observed_cwds:
            session.observed_cwds.append(event.cwd)

        is_filtered = is_internal_session_start(event) or is_untracked_internal_subagent_stop(
            event, frozenset(session.known_agent_ids)
        )
        if is_filtered:
            continue
        _apply_tracked_event(session, event)
    return {
        session_id: _freeze_session(session_id, session)
        for session_id, session in builders.items()
    }
