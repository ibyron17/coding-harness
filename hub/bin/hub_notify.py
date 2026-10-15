"""hub_notify.py — 세션이 작업중에서 벗어나는 순간을 판정하고 macOS 알림 문구·인자를 만드는 순수 로직.

이 모듈은 파일시스템·시각·환경변수·프로세스에 닿지 않는다(★순수, tests/hub/test_hub_notify.py 대상, tests/run.sh T25-10 이
파일시스템 접근 흔적을 기계적으로 강제한다). 시계는 항상 `now_ms` 인자로 받고, 로컬 시간대 표기는 호출자가 `clock_label` 로
주입한다. 알림을 실제로 보내고 상태를 파일에 남기는 일은 I/O 위성 모듈 hub_notify_send.py 가 한다(hub_release.py ↔
hub_release_read.py, hub_usage.py ↔ hub_usage_fetch.py 와 같은 배치).

근거: docs/prps/hub-macos-notification.md — 알림 규칙(결정 MN1)·소음 기준(MN2)·확인 지연(MN3)·백그라운드 대기(MN4)·
첫 관측 기준선(MN7)·전달 인자(MN8)·문구와 프라이버시(MN9)·상태 기록(MN11).
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from hub_model import HubSnapshot
from hub_redact import redact_secret_tokens
from hub_session import SessionView

NotifyPhase = Literal["working", "background", "waiting", "awaiting_approval", "interrupted", "done"]
NotifyKind = Literal["turn_ended", "background_wait", "awaiting_approval", "interrupted"]
NotifyFailureReason = Literal["osascript_missing", "timeout", "exit_nonzero", "invalid_text"]

# MN2 — 질의응답 한 번(대개 1분 안쪽)은 거르고, 사용자가 다른 창으로 갔을 법한 길이부터 울린다. 측정한 값이 아니라 판단의
# 하한이다 — 이름 있는 상수 하나라 사용 후 조정이 한 줄이다. 설정 키로 열지 않는다(MN10 — YAGNI).
NOTIFY_MIN_BUSY_EPISODE_MS = 2 * 60 * 1000
# MN3 — 서브에이전트 완료 직후 「작업중 → 대기 → 작업중」 틈에 걸린 가짜 알림을 막는 확인 지연. 티커 기본 주기(5초) 안에
# 들어가 확인이 대개 다음 틱 한 번에 끝나는 값이다.
NOTIFY_SETTLE_MS = 3_000
MS_PER_MINUTE = 60 * 1000
MINUTES_PER_HOUR = 60

# MN1 표 — 지금 국면이 이 넷 중 하나이고 직전 국면이 working 일 때만 알림 후보가 된다.
NOTIFY_KIND_BY_PHASE: Mapping[NotifyPhase, NotifyKind] = MappingProxyType({
    "interrupted": "interrupted",
    "awaiting_approval": "awaiting_approval",
    "waiting": "turn_ended",
    "background": "background_wait",
})
# 한 수집에서 나가는 알림의 순서(MN8).
NOTIFY_KIND_ORDER: tuple[NotifyKind, ...] = ("interrupted", "awaiting_approval", "turn_ended", "background_wait")
# 화면 배지 어휘(STATE_GLYPH·STATE_LABEL·BACKGROUND_SESSION_LABEL·APPROVAL_WAIT_*)와 같은 글자 — 규칙이 아니라 어휘라
# 두 벌이 허용되고, tests/run.sh T25-287 가 템플릿에 같은 글자가 있는지 교차 확인한다.
NOTIFY_TITLE_LABEL_BY_KIND: Mapping[NotifyKind, str] = MappingProxyType({
    "interrupted": "■ 한도 초과",
    "awaiting_approval": "◆ 승인 대기",
    "turn_ended": "○ 대기",
    "background_wait": "◐ 백그라운드 대기",
})

NOTIFY_TITLE_MAX_CHARS = 60
NOTIFY_SUBTITLE_MAX_CHARS = 60
NOTIFY_MESSAGE_MAX_CHARS = 120
NOTIFY_TASK_TITLE_MAX_CHARS = 40
NOTIFY_LISTED_PROJECT_MAX = 3
# 시크릿 마스킹 정규식은 입력 길이에 제곱으로 느려질 수 있다(hub_redact.redact_secret_tokens docstring). 작업 제목은 사용자가
# 쓴 임의 길이 글이라 마스킹 전에 길이를 제한해야 한다. 공백 정규화를 먼저 한 뒤 이 상한을 넘는 제목은 **자르지 않고 통째로 버린다** —
# hub_subagent 의 제목 경로(SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS)와 같은 선택이다. 잘라서 마스킹하면 자른 자리에 걸린 토큰의 머리가
# 패턴 불일치로 살아남고, 앞쪽이 긴 비밀 블록(PEM 등)의 마스킹으로 줄어들면 그 조각이 부제 앞으로 올 수 있다(검수 1회차 S1).
# 2,000자 넘는 글은 작업 제목이 아니므로 버려도 잃는 정보가 없다.
NOTIFY_TASK_TITLE_SCRUB_INPUT_MAX_CHARS = 2_000
ELLIPSIS = "…"

OSASCRIPT_PATH = "/usr/bin/osascript"
# MN8 — 스크립트 소스는 고정 상수이고 사용자 문자열이 들어가는 자리가 없다. 문자열은 `--` 뒤 argv 로만 간다.
NOTIFY_APPLESCRIPT_LINES = (
    "on run argv",
    "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of argv)",
    "end run",
)

_BUSY_PHASES = frozenset({"working", "background"})
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
# 고립 서로게이트는 UTF-8 로 인코딩할 수 없어 subprocess 가 argv 를 만들다 UnicodeEncodeError 를 낸다 — 대체 문자로 바꾼다(검수 1회차 S3).
_LONE_SURROGATES = re.compile(r"[\ud800-\udfff]")
REPLACEMENT_CHARACTER = "\ufffd"
_WHITESPACE_RUN = re.compile(r"\s+")
_PROJECT_SEPARATOR = " · "
_INTERRUPTED_MESSAGE = "사용량 한도로 멈췄습니다"


# ---- 데이터 모델 ----
@dataclass(frozen=True)
class SessionObservation:
    """수집 1회에서 세션 1개를 알림 관점으로 접은 값."""

    session_id: str
    phase: NotifyPhase
    project_name: str               # ProjectView.display_name
    task_title: str | None          # session.tier1.title 원문 — 마스킹·자르기는 문구를 조립할 때 한다
    resets_at_ms: int | None        # phase == "interrupted" 일 때만 값이 있다
    background_task_count: int      # phase == "background" 일 때만 task_count + wakeup_count, 아니면 0


@dataclass(frozen=True)
class PendingNotice:
    """확인 대기 중인 후보(MN3)."""

    kind: NotifyKind
    observed_at_ms: int             # 전이를 처음 본 수집 시각
    busy_duration_ms: int           # 그 시각까지의 바쁜 구간 길이


@dataclass(frozen=True)
class SessionTrack:
    """세션별 직전 관측(MN7) — 서버 프로세스 메모리에만 산다."""

    phase: NotifyPhase
    busy_since_ms: int | None       # 바쁜 구간 시작(MN2). 비바쁜 국면이 확정되면 None
    pending: PendingNotice | None = None


@dataclass(frozen=True)
class NotifyEvent:
    """확정된 알림 1건(세션 1개)."""

    kind: NotifyKind
    project_name: str
    task_title: str | None
    busy_duration_ms: int
    resets_at_ms: int | None
    background_task_count: int


@dataclass(frozen=True)
class NotificationText:
    """osascript 로 넘길 세 문자열(정제가 끝난 값)."""

    title: str
    subtitle: str
    message: str


@dataclass(frozen=True)
class NotifyStatusRecord:
    """~/.claude/hub/notify_status.json 과 맺은 계약(MN11). 문구는 담지 않는다."""

    active_since_ms: int | None
    last_attempt_at_ms: int | None
    last_success_at_ms: int | None
    last_failure_reason: NotifyFailureReason | None
    last_failure_exit_code: int | None


# ---- 국면 판정·관측 ----
def notify_phase(session: SessionView) -> NotifyPhase:
    """세션 표시 상태를 알림 국면 6값으로 접는다(MN1 표, 위에서부터 먼저 맞는 것)."""
    if session.state == "done":
        return "done"
    if session.state == "interrupted":
        return "interrupted"
    if session.is_awaiting_approval:
        return "awaiting_approval"
    if session.state == "background":
        return "background"
    if session.base_state == "working":
        return "working"
    return "waiting"


def _observe_session(session: SessionView, project_name: str) -> SessionObservation:
    """세션 1개를 관측값으로 접는다."""
    phase = notify_phase(session)
    resets_at_ms = session.interruption.resets_at_ms if phase == "interrupted" and session.interruption else None
    background_task_count = 0
    if phase == "background" and session.background_wait is not None:
        background_task_count = session.background_wait.task_count + session.background_wait.wakeup_count
    return SessionObservation(
        session_id=session.session_id,
        phase=phase,
        project_name=project_name,
        task_title=session.tier1.title if session.tier1 is not None else None,
        resets_at_ms=resets_at_ms,
        background_task_count=background_task_count,
    )


def observe_sessions(snapshot: HubSnapshot) -> tuple[SessionObservation, ...]:
    """스냅샷의 모든 프로젝트·세션을 관측값으로 펼친다."""
    return tuple(
        _observe_session(session, project.display_name)
        for project in snapshot.projects
        for session in project.sessions
    )


# ---- 전이 추적 ----
def _busy_since_or_now(previous: SessionTrack, now_ms: int) -> int:
    """이어지는 바쁜 구간의 시작 시각. 작업중 추적은 항상 값이 있어 폴백은 방어선이다."""
    return previous.busy_since_ms if previous.busy_since_ms is not None else now_ms


def _next_busy_since(previous: SessionTrack, phase: NotifyPhase, now_ms: int) -> int | None:
    """바쁜 국면이면 이어지는 구간의 시작, 아니면 None(구간이 끝났다)."""
    if phase not in _BUSY_PHASES:
        return None
    return _busy_since_or_now(previous, now_ms)


def _start_pending(previous: SessionTrack, phase: NotifyPhase, now_ms: int) -> SessionTrack:
    """작업중에서 알림 국면으로 처음 넘어온 수집 — 후보로만 둔다(MN3)."""
    busy_since_ms = _busy_since_or_now(previous, now_ms)
    pending = PendingNotice(
        kind=NOTIFY_KIND_BY_PHASE[phase], observed_at_ms=now_ms, busy_duration_ms=now_ms - busy_since_ms,
    )
    return SessionTrack(phase=phase, busy_since_ms=busy_since_ms, pending=pending)


def _confirm_pending(
    previous: SessionTrack, observation: SessionObservation, pending: PendingNotice, now_ms: int,
) -> tuple[SessionTrack, NotifyEvent | None]:
    """확인 지연이 지난 후보를 확정한다. 소음 기준(MN2)을 못 넘으면 알림 없이 후보만 거둔다."""
    settled_track = SessionTrack(
        phase=observation.phase, busy_since_ms=_next_busy_since(previous, observation.phase, now_ms), pending=None,
    )
    is_loud_enough = pending.kind == "interrupted" or pending.busy_duration_ms >= NOTIFY_MIN_BUSY_EPISODE_MS
    if not is_loud_enough:
        return settled_track, None
    event = NotifyEvent(
        kind=pending.kind,
        project_name=observation.project_name,
        task_title=observation.task_title,
        busy_duration_ms=pending.busy_duration_ms,
        resets_at_ms=observation.resets_at_ms,
        background_task_count=observation.background_task_count,
    )
    return settled_track, event


def advance_session_track(
    previous: SessionTrack | None, observation: SessionObservation, now_ms: int,
) -> tuple[SessionTrack, NotifyEvent | None]:
    """세션 1개의 추적을 한 수집만큼 전진시키고, 확정된 알림이 있으면 함께 돌려준다(MN1~MN3·MN7)."""
    phase = observation.phase
    if previous is None:
        return SessionTrack(phase=phase, busy_since_ms=now_ms if phase in _BUSY_PHASES else None), None
    pending = previous.pending
    if pending is not None and phase == previous.phase:
        if now_ms - pending.observed_at_ms < NOTIFY_SETTLE_MS:
            return previous, None
        return _confirm_pending(previous, observation, pending, now_ms)
    # 후보가 있었는데 국면이 바뀌었다 — 새 국면이 알림 국면이면 보존한 바쁜 구간 시작으로 그 국면의 후보를 다시 시작한다(앞 후보는
    # 확정 전에 사라지므로 한 전이에 알림은 하나다). 새 국면이 working 이면(복귀) 후보를 버린다. 후보는 working 에서만 생기므로
    # 「후보가 있다」는 「작업중에서 막 나왔다」와 같은 뜻이다(결정 MN3, 검수 1회차 C1).
    came_from_working = previous.phase == "working" or pending is not None
    if came_from_working and phase in NOTIFY_KIND_BY_PHASE:
        return _start_pending(previous, phase, now_ms), None
    return SessionTrack(phase=phase, busy_since_ms=_next_busy_since(previous, phase, now_ms)), None


def advance_tracks(
    previous: Mapping[str, SessionTrack] | None, observations: Sequence[SessionObservation], now_ms: int,
) -> tuple[Mapping[str, SessionTrack], tuple[NotifyEvent, ...]]:
    """previous 가 None(서버 첫 수집)이면 기준선만 잡고 알림 0건. 사라진 세션은 결과에서 빠진다."""
    known_tracks: Mapping[str, SessionTrack] = {} if previous is None else previous
    tracks: dict[str, SessionTrack] = {}
    events: list[NotifyEvent] = []
    for observation in observations:
        track, event = advance_session_track(known_tracks.get(observation.session_id), observation, now_ms)
        tracks[observation.session_id] = track
        if event is not None:
            events.append(event)
    return MappingProxyType(tracks), tuple(events)


def has_pending(tracks: Mapping[str, SessionTrack]) -> bool:
    """확인 대기 후보가 하나라도 있으면 True — 티커의 확인 수집 게이트(MN3·MN6)."""
    return any(track.pending is not None for track in tracks.values())


# ---- 문구 ----
def duration_label(duration_ms: int) -> str:
    """'23분' / '1시간' / '1시간 5분'."""
    total_minutes = duration_ms // MS_PER_MINUTE
    hours, minutes = divmod(total_minutes, MINUTES_PER_HOUR)
    if hours == 0:
        return f"{minutes}분"
    return f"{hours}시간" if minutes == 0 else f"{hours}시간 {minutes}분"


def _normalize_text(text: str) -> str:
    """제어문자·NUL → 공백, 고립 서로게이트 → 대체 문자, 공백 접기, 앞뒤 공백 제거(길이는 건드리지 않는다)."""
    spaced = _CONTROL_CHARACTERS.sub(" ", text)
    encodable = _LONE_SURROGATES.sub(REPLACEMENT_CHARACTER, spaced)
    return _WHITESPACE_RUN.sub(" ", encodable).strip()


def sanitize_notification_text(text: str, max_chars: int) -> str:
    """제어문자·NUL → 공백, 고립 서로게이트 → 대체 문자, 공백 접기, 앞뒤 공백 제거, 상한 초과 시 앞 max_chars 자 + '…'(MN8).

    NUL·고립 서로게이트가 인자에 들어가면 프로세스 실행이 ValueError·UnicodeEncodeError 로 죽는다 — 이 정제가 그 예외도 막는다.
    """
    collapsed = _normalize_text(text)
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[:max_chars] + ELLIPSIS


def _subtitle_for(event: NotifyEvent, include_task_title: bool) -> str:
    """작업 제목(공백 정규화 → 시크릿 마스킹 → 40자 상한). 끄면 빈 값 — 프라이버시 스위치는 record_prompt_excerpt 다(MN9).

    정규화가 마스킹보다 먼저다 — 공백을 접기 전에 길이를 재면 앞 공백이 길 때 정규화 뒤 글이 창 경계에 걸린다. 정규화한 글이 창을 넘으면
    통째로 버린다(NOTIFY_TASK_TITLE_SCRUB_INPUT_MAX_CHARS 주석).
    """
    if not include_task_title or not event.task_title:
        return ""
    normalized = _normalize_text(event.task_title)
    if len(normalized) > NOTIFY_TASK_TITLE_SCRUB_INPUT_MAX_CHARS:
        return ""
    return sanitize_notification_text(redact_secret_tokens(normalized), NOTIFY_TASK_TITLE_MAX_CHARS)


def _message_for(event: NotifyEvent, clock_label: Callable[[int], str]) -> str:
    """종류별 본문(MN9 표)."""
    if event.kind == "interrupted":
        if event.resets_at_ms is None:
            return _INTERRUPTED_MESSAGE
        return f"{_INTERRUPTED_MESSAGE} · {clock_label(event.resets_at_ms)} 초기화 예정"
    elapsed = duration_label(event.busy_duration_ms)
    if event.kind == "awaiting_approval":
        return f"{elapsed} 작업 뒤 승인을 기다립니다"
    if event.kind == "background_wait":
        return f"{elapsed} 작업 뒤 백그라운드 작업 {event.background_task_count}개를 기다립니다"
    return f"{elapsed} 작업을 마치고 입력을 기다립니다"


def _group_message(events: Sequence[NotifyEvent]) -> str:
    """같은 종류 여러 세션의 본문 — 프로젝트 이름을 중복 없이 3개까지 나열하고 나머지는 개수로."""
    names = list(dict.fromkeys(event.project_name for event in events))
    listed = _PROJECT_SEPARATOR.join(names[:NOTIFY_LISTED_PROJECT_MAX])
    rest = len(names) - NOTIFY_LISTED_PROJECT_MAX
    return f"{listed} 외 {rest}" if rest > 0 else listed


def _compose_group(
    kind: NotifyKind, events: Sequence[NotifyEvent], include_task_title: bool, clock_label: Callable[[int], str],
) -> NotificationText:
    """같은 종류의 확정 알림들을 알림 1건으로 만든다."""
    label = NOTIFY_TITLE_LABEL_BY_KIND[kind]
    if len(events) == 1:
        event = events[0]
        title = f"{label} · {event.project_name}"
        subtitle = _subtitle_for(event, include_task_title)
        message = _message_for(event, clock_label)
    else:
        title, subtitle, message = f"{label} · 세션 {len(events)}개", "", _group_message(events)
    return NotificationText(
        title=sanitize_notification_text(title, NOTIFY_TITLE_MAX_CHARS),
        subtitle=sanitize_notification_text(subtitle, NOTIFY_SUBTITLE_MAX_CHARS),
        message=sanitize_notification_text(message, NOTIFY_MESSAGE_MAX_CHARS),
    )


def compose_notifications(
    events: Sequence[NotifyEvent], include_task_title: bool, clock_label: Callable[[int], str],
) -> tuple[NotificationText, ...]:
    """종류별로 묶어 NOTIFY_KIND_ORDER 순서의 알림 문구를 만든다(MN9 표). clock_label 은 I/O 층이 주입한다."""
    texts = []
    for kind in NOTIFY_KIND_ORDER:
        group = [event for event in events if event.kind == kind]
        if group:
            texts.append(_compose_group(kind, group, include_task_title, clock_label))
    return tuple(texts)


def osascript_argv(text: NotificationText) -> tuple[str, ...]:
    """고정 스크립트 + '--' + (message, title, subtitle). 사용자 문자열은 '--' 뒤에만 온다(MN8).

    `--` 가 없으면 `-` 로 시작하는 문자열을 osascript 가 옵션으로 다시 읽는다.
    """
    script_arguments = tuple(part for line in NOTIFY_APPLESCRIPT_LINES for part in ("-e", line))
    return (OSASCRIPT_PATH, *script_arguments, "--", text.message, text.title, text.subtitle)


# ---- 상태 기록 ----
def next_notify_status_record(
    previous: NotifyStatusRecord | None,
    now_ms: int,
    failure_reason: NotifyFailureReason | None,
    exit_code: int | None,
) -> NotifyStatusRecord:
    """배치 1회의 결과로 새 기록을 돌려준다(원본은 불변).

    배치에 실패가 있으면 마지막 실패의 사유·코드를 남기고 last_success_at_ms 는 보존하며, 모두 성공이면 실패 필드를 지운다
    (hub_release.next_release_check_record 와 같은 의미). active_since_ms 는 항상 보존한다.
    """
    active_since_ms = previous.active_since_ms if previous is not None else None
    if failure_reason is None:
        return NotifyStatusRecord(
            active_since_ms=active_since_ms, last_attempt_at_ms=now_ms, last_success_at_ms=now_ms,
            last_failure_reason=None, last_failure_exit_code=None,
        )
    return NotifyStatusRecord(
        active_since_ms=active_since_ms,
        last_attempt_at_ms=now_ms,
        last_success_at_ms=previous.last_success_at_ms if previous is not None else None,
        last_failure_reason=failure_reason,
        last_failure_exit_code=exit_code,
    )


def is_notifier_active(record: NotifyStatusRecord | None, server_started_at_ms: int | None) -> bool:
    """지금 도는 서버가 알림기를 켜고 시작했는가(active_since_ms ≥ 서버 기동 시각)."""
    if record is None or record.active_since_ms is None or server_started_at_ms is None:
        return False
    return record.active_since_ms >= server_started_at_ms
