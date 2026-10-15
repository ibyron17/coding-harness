"""hub_notify_send.py — macOS 알림의 I/O 레이어. osascript 실행 · 전송 스레드 · notify_status.json 읽기/쓰기 ·
활동 서명 읽기 · 수집 결과를 받아 알림을 내보내는 SessionNotifier(docs/prps/hub-macos-notification.md 결정 MN6~MN8·MN11).

국면 판정·전이·문구·argv 조립은 hub_notify.py(★순수)에 있다 — 이 모듈은 그 결과를 프로세스·파일과 잇는 얇은 층이다
(hub_release.py ↔ hub_release_read.py 와 같은 배치). 경로 상수는 이 모듈이 갖는다: hub_collect·hub_server 를 임포트하지
않는다(hub_server 가 이 모듈을 부르므로 순환이 된다). 임포트 방향은 hub_notify ← hub_notify_send ← hub_server · hub.

사용자 문자열은 셸·AppleScript 소스를 거치지 않는다 — hub_notify.osascript_argv 가 만든 리스트 argv 를 그대로 `subprocess.run`
에 넘긴다(rules/python/security.md). 알림 문구는 어떤 파일에도 남기지 않는다 — 상태 기록에는 시각·실패 사유·종료 코드만,
server.log(stderr)에는 실패 사유·종료 코드와 AppleScript 오류 번호만 남는다. osascript 의 오류문은 argv 피연산자(= 알림 문구)를 인용할 수
있어 stderr 의 글을 그대로 남기지 않는다(결정 MN9·MN11, 검수 1회차 S2).
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

import hub_atomic_write
import hub_notify
from hub_model import HubSnapshot

NOTIFY_STATUS_PATH = Path.home() / ".claude" / "hub" / "notify_status.json"
# 시간 초과 — osascript 는 손자 프로세스를 만들지 않고, subprocess.run 이 시간 초과 시 자식을 직접 죽인다.
NOTIFY_SEND_TIMEOUT_SECONDS = 10
# 오류 번호가 없을 때 server.log 에 남기는 고정 문구 — stderr 의 글(알림 문구를 인용할 수 있다)은 남기지 않는다.
NO_ERROR_NUMBER_LOG = "AppleScript 오류 번호 없음"
_APPLESCRIPT_ERROR_NUMBER = re.compile(r"\((-\d{1,6})\)")
# 활동 서명이 보는 파일: 훅 이벤트(.jsonl)와 호스트 세션 명부(.json). 같은 폴더의 `*.key` 등은 보지 않는다.
ACTIVITY_FILE_SUFFIXES = (".jsonl", ".json")
NOTIFY_SEND_THREAD_NAME = "hub-notify-send"
MS_PER_SECOND = 1000
_FAILURE_REASONS = frozenset({"osascript_missing", "timeout", "exit_nonzero", "invalid_text"})
_RECORD_OPTIONAL_INT_FIELDS = ("active_since_ms", "last_attempt_at_ms", "last_success_at_ms", "last_failure_exit_code")

ActivitySignature = frozenset[tuple[str, str, int, int]]


def is_notify_supported() -> bool:
    """macOS 이고 /usr/bin/osascript 가 실재하는가."""
    return sys.platform == "darwin" and Path(hub_notify.OSASCRIPT_PATH).is_file()


# ---- 전송 ----
def _applescript_error_summary(stderr: bytes) -> str:
    """osascript 오류문에서 AppleScript 오류 번호(`(-1728)` 형태)만 뽑아 한 줄로 만든다. 번호가 없으면 고정 문구.

    오류문의 나머지는 알림 문구를 인용할 수 있어 로그에 옮기지 않는다. 디코딩 못 하는 바이트는 대체 문자로 둔다.
    """
    numbers = _APPLESCRIPT_ERROR_NUMBER.findall(stderr.decode("utf-8", errors="replace"))
    return f"AppleScript 오류 번호 {numbers[-1]}" if numbers else NO_ERROR_NUMBER_LOG


def _log_send_failure(reason: hub_notify.NotifyFailureReason, exit_code: int | None, detail: str) -> None:
    """실패 한 줄을 stderr(= server.log)에 남긴다. 알림 문구는 싣지 않는다."""
    print(f"알림 전송 실패({reason}, exit {exit_code}): {detail}", file=sys.stderr)


def send_notification(text: hub_notify.NotificationText) -> tuple[hub_notify.NotifyFailureReason | None, int | None]:
    """osascript 1회. 성공이면 (None, 0). 실패 사유·종료 코드를 돌려주고 AppleScript 오류 번호만 server.log(stderr)에 남긴다."""
    try:
        completed = subprocess.run(
            hub_notify.osascript_argv(text),
            stdin=subprocess.DEVNULL, capture_output=True, timeout=NOTIFY_SEND_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        _log_send_failure("timeout", None, "")
        return "timeout", None
    except ValueError as error:
        # NUL·고립 서로게이트가 정제를 우회해 argv 에 들어온 경우(UnicodeEncodeError 도 ValueError 의 하위 클래스다). 이 알림만 버리고
        # 배치의 나머지는 계속 보낸다 — 오류문은 문구를 인용할 수 있어 종류 이름만 남긴다(검수 1회차 S3).
        _log_send_failure("invalid_text", None, type(error).__name__)
        return "invalid_text", None
    except OSError as error:
        _log_send_failure("osascript_missing", None, str(error))
        return "osascript_missing", None
    if completed.returncode != 0:
        _log_send_failure("exit_nonzero", completed.returncode, _applescript_error_summary(completed.stderr))
        return "exit_nonzero", completed.returncode
    return None, 0


# ---- 상태 기록 ----
def _status_record_from_raw(raw: object) -> hub_notify.NotifyStatusRecord | None:
    """notify_status.json 의 dict 를 기록으로 옮긴다. 모양이 틀리면 None."""
    if not isinstance(raw, dict):
        return None
    for name in _RECORD_OPTIONAL_INT_FIELDS:
        value = raw.get(name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            return None
    reason = raw.get("last_failure_reason")
    if reason is not None and reason not in _FAILURE_REASONS:
        return None
    return hub_notify.NotifyStatusRecord(
        active_since_ms=raw.get("active_since_ms"),
        last_attempt_at_ms=raw.get("last_attempt_at_ms"),
        last_success_at_ms=raw.get("last_success_at_ms"),
        last_failure_reason=reason,
        last_failure_exit_code=raw.get("last_failure_exit_code"),
    )


def read_notify_status() -> hub_notify.NotifyStatusRecord | None:
    """notify_status.json 을 읽는다. 없거나 깨졌거나 타입이 틀리면 None."""
    try:
        return _status_record_from_raw(json.loads(NOTIFY_STATUS_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def write_notify_status(record: hub_notify.NotifyStatusRecord) -> None:
    """notify_status.json 을 원자적으로 쓴다. OSError 는 호출측이 받는다."""
    NOTIFY_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    hub_atomic_write.atomic_write_text(
        NOTIFY_STATUS_PATH, NOTIFY_STATUS_PATH.parent, "notify_status.json.",
        json.dumps(asdict(record), ensure_ascii=False),
    )


def _send_batch(
    texts: Sequence[hub_notify.NotificationText],
) -> tuple[hub_notify.NotifyFailureReason | None, int | None]:
    """배치를 차례로 보내고 마지막 실패의 (사유, 종료 코드)를 돌려준다. 모두 성공이면 (None, None)."""
    failure_reason: hub_notify.NotifyFailureReason | None = None
    exit_code: int | None = None
    for text in texts:
        reason, code = send_notification(text)
        if reason is not None:
            failure_reason, exit_code = reason, code
    return failure_reason, exit_code


def deliver_notifications(texts: Sequence[hub_notify.NotificationText], now_ms: int) -> None:
    """배치를 차례로 보내고 notify_status.json 을 1회 갱신한다. 예외를 올리지 않는다(최후선은 stderr)."""
    try:
        failure_reason, exit_code = _send_batch(texts)
        try:
            record = hub_notify.next_notify_status_record(read_notify_status(), now_ms, failure_reason, exit_code)
            write_notify_status(record)
        except OSError as error:
            print(f"알림 상태 기록 쓰기 실패: {error}", file=sys.stderr)
    except Exception as error:  # 알림 스레드의 최후선 — 여기서 죽어도 수집·티커는 영향이 없어야 한다
        print(f"알림 전송 배치에서 처리되지 않은 예외: {error}", file=sys.stderr)


def dispatch_in_background(texts: Sequence[hub_notify.NotificationText], now_ms: int) -> None:
    """deliver_notifications 를 데몬 스레드 1개로 띄운다(결정 MN8 — 수집 락·하트비트를 막지 않는다).

    알림은 시간당 몇 건이라 배치마다 스레드 1개로 충분하다. 시간 초과가 최대 10초라 티커(하트비트 TTL 15초)에서 직접
    기다리면 훅이 서버를 죽었다고 보고 폴백 수집을 띄운다.
    """
    threading.Thread(
        target=deliver_notifications, args=(tuple(texts), now_ms), name=NOTIFY_SEND_THREAD_NAME, daemon=True,
    ).start()


# ---- 활동 서명 ----
def _entry_signature(directory: Path, entry: os.DirEntry) -> tuple[str, str, int, int] | None:
    """디렉터리 항목 하나의 (디렉터리 이름, 파일 이름, 크기, mtime_ns). 훑는 사이 지워졌으면 None(다음 틱의 서명이 다시 잡는다)."""
    try:
        stat_result = entry.stat()
    except OSError:
        return None
    return directory.name, entry.name, stat_result.st_size, stat_result.st_mtime_ns


def _directory_signature(directory: Path) -> set[tuple[str, str, int, int]]:
    """디렉터리 하나의 서명 집합. 읽을 수 없으면 빈 집합."""
    try:
        with os.scandir(directory) as entries:
            signatures = (_entry_signature(directory, entry) for entry in entries if entry.name.endswith(ACTIVITY_FILE_SUFFIXES))
            return {signature for signature in signatures if signature is not None}
    except OSError:
        return set()


def read_activity_signature(directories: Sequence[Path]) -> ActivitySignature:
    """훅 이벤트·세션 명부 파일의 (디렉터리 이름, 파일 이름, 크기, mtime_ns) 집합(결정 MN6).

    디렉터리 부재·읽기 실패는 그 디렉터리만 빈 것으로 본다. 직전 틱의 값과 다르면 세션 상태가 바뀌었을 수 있다는 신호다.
    """
    merged: set[tuple[str, str, int, int]] = set()
    for directory in directories:
        merged |= _directory_signature(directory)
    return frozenset(merged)


# ---- 시각 표기 ----
def local_clock_label(epoch_ms: int, now_ms: int) -> str:
    """'HH:MM'(오늘) / 'M/D HH:MM'(다른 날) — 로컬 시간대. 화면과 같은 규칙이다."""
    target = time.localtime(epoch_ms / MS_PER_SECOND)
    today = time.localtime(now_ms / MS_PER_SECOND)
    clock = f"{target.tm_hour:02d}:{target.tm_min:02d}"
    if (target.tm_year, target.tm_mon, target.tm_mday) == (today.tm_year, today.tm_mon, today.tm_mday):
        return clock
    return f"{target.tm_mon}/{target.tm_mday} {clock}"


# ---- 알림기 ----
class SessionNotifier:
    """수집 결과를 받아 전이를 판정하고 확정된 알림을 내보낸다.

    왜 클래스인가: 수집과 수집 사이에 살아야 하는 직전 관측(추적 매핑)이 있고 전역 가변 상태는 금지다 —
    _SnapshotRefresher 와 같은 이유·같은 자리(서버 인스턴스)다. 추적은 서버 프로세스 메모리에만 둔다(결정 MN7).
    `observe` 는 _SnapshotRefresher 락 안에서만 불려 수집과 같은 직렬화를 공유한다.
    """

    def __init__(
        self,
        include_task_title: bool,
        dispatch: Callable[[Sequence[hub_notify.NotificationText], int], None] = dispatch_in_background,
    ) -> None:
        self._include_task_title = include_task_title
        self._dispatch = dispatch
        self._tracks: Mapping[str, hub_notify.SessionTrack] | None = None

    def observe(self, snapshot: HubSnapshot) -> None:
        """_SnapshotRefresher 락 안에서만 부른다. 첫 호출은 기준선이다."""
        now_ms = snapshot.collected_at_ms
        self._tracks, events = hub_notify.advance_tracks(
            self._tracks, hub_notify.observe_sessions(snapshot), now_ms,
        )
        if not events:
            return
        texts = hub_notify.compose_notifications(
            events, self._include_task_title, lambda epoch_ms: local_clock_label(epoch_ms, now_ms),
        )
        self._dispatch(texts, now_ms)

    def has_pending(self) -> bool:
        """티커가 확인 수집을 부를지 정한다. 통째로 교체되는 불변 매핑의 참조 하나만 읽는다."""
        tracks = self._tracks
        return tracks is not None and hub_notify.has_pending(tracks)
