"""hub_live_session.py — ~/.claude/sessions/<pid>.json(호스트 소유 「살아있는 세션 명부」)의
순수 파서 + 명부 판정값 변환.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_live_session.py 대상).
호스트(Claude Code)가 세션마다 쓰는 이 레코드의 계약은 이 모듈 하나에 가둔다(결정 LS2,
docs/prps/hub-live-session-native-source.md) — hub_transcript.py·hub_workflow.py·
hub_subagent.py 가 세운 선례와 같은 이유로, 호스트가 형식을 바꾸면 이 파일만 고치면 된다.

hub_session.py 는 이 모듈이 내보내는 RosterState 5값(결정 LS3)만 보고, 레코드의 필드 이름도
"status" 라는 문자열도 모른다. 파일 접근(디렉터리 열거·읽기·PID 생존 확인)은 전부
hub_live_session_read.py 가 맡는다 — 이 모듈은 이미 읽힌 텍스트만 받는다.
"""

import json
from dataclasses import dataclass
from typing import Literal, Sequence

# 화해(hub_session._compute_base_state)가 건너보는 5값(결정 LS3) — 호스트 레코드의 필드 이름·
# status 문자열 자체는 이 모듈 밖으로 나가지 않는다.
RosterState = Literal["unknown", "not_listed", "listed", "busy", "idle"]

LIVE_SESSION_STATUS_BUSY = "busy"
LIVE_SESSION_STATUS_IDLE = "idle"
# 실측 레코드 1건 약 660B(§1.1)의 약 100배 방어선 — SUBAGENT_META_MAX_BYTES 와 같은 형태·같은 값.
LIVE_SESSION_RECORD_MAX_BYTES = 64 * 1024
# pid_t 32비트 부호 있는 정수 상한(실측, Darwin — 시그널 0 전송에 2**31 을 넘기면 그 즉시
# OverflowError: "signed integer is greater than maximum"). 이 값을 넘는 pid 는
# _is_process_alive 의 시그널 0 전송이 생존 확인 자체를 하기도 전에 OverflowError 를
# 던지고, 그 예외는 ProcessLookupError·PermissionError 두 분기를 모두 뚫는다(재현:
# {"pid": 99999999999999999999}, 검수 1회차 H1-3). ValueError/RecursionError 흡수
# (parse_live_session_record 의 except 절)로는 못 막는 별개의 실패 통로라 파서 쪽 상한으로
# 막는다(결정 LS8 "불변식은 파서가 강제한다").
LIVE_SESSION_PID_MAX = 2**31 - 1


@dataclass(frozen=True)
class LiveSessionRecord:
    """레코드 1건에서 허브가 쓰는 3필드만 남긴 것(결정 LS11·LS13) — cwd·name·entrypoint 등
    나머지 키는 파싱하지 않는다(화면에 실을 이유가 없다)."""

    session_id: str
    pid: int              # 불변식: bool 이 아닌 0 < pid <= LIVE_SESSION_PID_MAX — 파서가 강제한다
                           # (아래 parse_live_session_record 참조, 결정 LS8, 검수 1회차 L1·H1-3)
    is_busy: bool | None   # "busy"→True, "idle"→False, 키 부재·미지값→None(실측 10%)


@dataclass(frozen=True)
class LiveSessionIndex:
    """수집 1회분의 명부. `is_complete` 가 거짓이면 부재를 근거로 쓰지 않는다(결정 LS7) —
    `by_session_id` 의 truthiness 로 대신하지 않는다. `{}` 와 `None` 의 차이에 가장 위험한
    판정(살아 있는데 죽었다고 오판)이 걸리면 안 되기 때문이다."""

    by_session_id: dict[str, LiveSessionRecord]
    is_complete: bool


def _is_busy_from_status(status: object) -> bool | None:
    """status 문자열 → is_busy. 키 부재(payload.get 이 None 반환)·미지값은 None(실측 10%)."""
    if status == LIVE_SESSION_STATUS_BUSY:
        return True
    if status == LIVE_SESSION_STATUS_IDLE:
        return False
    return None


def parse_live_session_record(text: str) -> LiveSessionRecord | None:
    """레코드 1건의 본문을 판다. 깨졌거나 필수 키(sessionId·pid)가 없거나 pid 가 방어선을
    벗어나면 None(호출자가 건너뛴다).

    **계약 B(hub_workflow.parse_workflow_run·hub_subagent.parse_subagent_meta 와 동형) —
    어떤 입력에도 예외를 던지지 않는다.**
    """
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        # ValueError — json.JSONDecodeError(구문 오류)의 상위 클래스라 기존 케이스를
        # 포함하면서, 4,300자리를 넘는 정수 리터럴이 던지는 순수 ValueError(정수 문자열
        # 변환 자릿수 한도)까지 함께 잡는다. RecursionError — 깊게 중첩된 입력("["*n)은
        # json.JSONDecodeError 가 아니라 RecursionError 를 던진다. hub_workflow.py·
        # hub_subagent.py 가 이미 겪은 실패를 이 모듈이 신설 당시 그대로 재현했다(재현:
        # 4,400자리 정수·중첩 30,000단, 검수 1회차 H1) — 병리적 입력 표로
        # tests/hub/test_hub_live_session.py 에 회귀를 고정한다. TypeError 는 잡지 않는다
        # — 유일 호출자(hub_live_session_read._read_one_record)가 항상 str 을 넘겨 도달
        # 경로가 없다(검수 1회차 H1, 일어날 수 없는 상황에 대한 에러 처리 금지).
        return None
    if not isinstance(payload, dict):
        return None

    session_id = payload.get("sessionId")
    pid = payload.get("pid")
    # 아래 검사는 이 레코드가 나중에 프로세스 생존 확인(시그널 0 전송)에 쓰일 때의 방어선이다
    # (결정 LS8). pid > 0 이 없으면 0 을 그대로 넘겨 "그 신호는 프로세스 그룹 전체를 가리켜
    # 항상 생존"이라는 거짓 참을 만든다. bool 을 배제하는 이유 — JSON 의 true/false 는
    # Python 에서 int 의 서브클래스라 isinstance(True, int) 가 참이 되고, pid=True 로 시그널을
    # 보내면 pid=1(launchd)과 같아 항상 생존이라는 거짓 참을 만든다(재현: {"pid": true},
    # 검수 1회차 L1). 상한(LIVE_SESSION_PID_MAX)이 없으면 pid_t 32비트 범위를 넘는 값이
    # 그 시그널 전송에서 OverflowError 를 던져 그 두 예외 분기를 모두 뚫는다(검수 1회차
    # H1-3). 이 검사가 빠지면 이 footgun 들이 그대로 재개통된다(T25-216 이 이 리터럴 자체를
    # 기계적으로 고정한다).
    is_valid_pid = isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid <= LIVE_SESSION_PID_MAX
    if not isinstance(session_id, str) or not is_valid_pid:
        return None

    return LiveSessionRecord(
        session_id=session_id, pid=pid, is_busy=_is_busy_from_status(payload.get("status"))
    )


def _fold_priority(record: LiveSessionRecord) -> int:
    """같은 session_id 접기 우선순위 — busy(0) > 미상(1) > idle(2), 낮을수록 우선."""
    if record.is_busy is True:
        return 0
    if record.is_busy is None:
        return 1
    return 2


def build_live_session_index(
    records: Sequence[LiveSessionRecord], is_complete: bool
) -> LiveSessionIndex:
    """같은 session_id 의 레코드가 여럿이면 결정적으로 하나로 접는다 — busy > 미상 > idle,
    동률은 pid 가 작은 쪽(결정론 = snapshot_content_key 안정성)."""
    winners: dict[str, LiveSessionRecord] = {}
    for record in records:
        current = winners.get(record.session_id)
        if current is None or (_fold_priority(record), record.pid) < (
            _fold_priority(current), current.pid
        ):
            winners[record.session_id] = record
    return LiveSessionIndex(by_session_id=winners, is_complete=is_complete)


def roster_state_for_session(index: LiveSessionIndex | None, session_id: str) -> RosterState:
    """이 세션에 대해 명부가 말하는 것(결정 LS3 의 5값). index 가 None 이면 항상 "unknown".

    미등재(레코드 없음)의 뜻은 `is_complete` 로 갈린다(결정 LS7) — 열거·읽기가 불완전했다면
    "없다"는 관측을 신뢰할 수 없어 "unknown"(오늘의 동작과 동일)에 머물고, 완전했을 때만
    "not_listed"(=프로세스가 없다)로 승격한다.
    """
    if index is None:
        return "unknown"
    record = index.by_session_id.get(session_id)
    if record is None:
        return "not_listed" if index.is_complete else "unknown"
    if record.is_busy is True:
        return "busy"
    if record.is_busy is False:
        return "idle"
    return "listed"
