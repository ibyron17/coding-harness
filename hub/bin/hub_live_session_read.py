"""hub_live_session_read.py — ~/.claude/sessions/<pid>.json(호스트 소유 「살아있는 세션 명부」)를
찾아 읽고 PID 생존을 확인하는 I/O.

hub_workflow.py(★순수) / hub_workflow_read.py(I/O), hub_subagent.py(★순수) /
hub_subagent_read.py(I/O) 쌍과 파일명·역할·임포트 방향이 동형이다(결정 LS2,
docs/prps/hub-live-session-native-source.md) — 파싱은 hub_live_session.parse_live_session_record
(★순수)에 위임하고, 이 모듈은 디렉터리 열거·파일 읽기·PID 생존 확인만 한다.

대상 디렉터리는 `SESSIONS_DIR` 같은 모듈 상수로 여기에 선언하지 않는다 — 호출자(hub_collect.py)가
자신의 상수를 인자로 넘긴다(PROJECTS_DIR→read_subagent_metas(..., projects_dir) 와 같은 관례).
"""

import os
from pathlib import Path

import hub_live_session


def _is_process_alive(pid: int) -> bool:
    """전제: pid > 0(LiveSessionRecord 불변식, hub_live_session.parse_live_session_record 가
    강제한다). 시그널 0 전송으로 프로세스 존재만 확인하고 실제로 신호를 보내지 않는다.

    ProcessLookupError → 죽음(False). PermissionError → 생존(True, 남의 프로세스지만 존재한다).
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_record_text(record_path: Path) -> tuple[str | None, bool]:
    """(본문, 실패 여부)를 돌려준다. 상한(LIVE_SESSION_RECORD_MAX_BYTES) 초과·읽기 실패는
    (None, True). `errors="replace"` 로 GOTCHA 7(UnicodeDecodeError 는 ValueError 서브클래스라
    `except OSError` 를 뚫는다)을 방어한다 — hub_subagent_read._read_meta_text 와 같은 형태.
    """
    try:
        size = record_path.stat().st_size
        if size > hub_live_session.LIVE_SESSION_RECORD_MAX_BYTES:
            return None, True
        return record_path.read_text(encoding="utf-8", errors="replace"), False
    except OSError:
        return None, True


def _read_one_record(record_path: Path) -> tuple[hub_live_session.LiveSessionRecord | None, bool]:
    """레코드 1건을 읽고 판다. (레코드, 실패 여부)를 돌려준다 — 실패는 읽기·크기·파싱
    실패를 한데 묶는다(결정 LS11의 2단 가드 중 레코드 단위 실패)."""
    text, read_failed = _read_record_text(record_path)
    if read_failed:
        return None, True
    record = hub_live_session.parse_live_session_record(text)
    if record is None:
        return None, True
    return record, False


def read_live_session_roster(
    sessions_dir: Path,
) -> tuple[hub_live_session.LiveSessionIndex, tuple[str, ...]]:
    """명부 디렉터리를 훑어 (인덱스, 경고) 를 돌려준다. 절대 예외를 던지지 않는다.

    2단 가드(결정 LS11): 열거 실패는 명부 전체를 포기하고(is_complete=False), 레코드 단위
    실패는 그 레코드만 건너뛰되 is_complete 를 내린다(사이클당 집계 1건). 죽은 PID 의
    레코드는 인덱스에 넣지 않는다 — 이것은 실패가 아니라 정상 경로다(결정 LS7 — 부재의
    증거력만 is_complete 로 통제한다). `*.json` 만 대상이고 같은 디렉터리의 `<pid>.<sha256>.key`
    는 건드리지 않는다(iterdir 결과를 suffix 로 걸러낸다).

    `is_dir()` 은 ENOENT 는 삼키지만 EACCES 는 올린다(pathlib 실측, hub_workflow_read.
    `_existing_workflow_directories` 와 같은 형태) — 권한 없는 부모 아래 sessions_dir 를
    두면 이 검사 자체가 예외를 던져 명부 하나가 아니라 collect_snapshot 전체가 죽는다
    (검수 2회차 H1). 바로 다음의 열거 실패와 같은 급으로 흡수한다.

    열거에 `glob("*.json")` 이 아니라 `iterdir()` + suffix 비교를 쓰는 이유(실측, Python
    3.11.5) — `Path.glob()` 은 디렉터리에 읽기 권한이 없어도(EACCES) 예외를 던지지 않고
    조용히 빈 이터레이터를 반환한다(내부적으로 `os.scandir` 실패를 흡수한다). `is_dir()`
    은 그 상황에서도 부모만 순회 가능하면 `True` 를 돌려주므로, 열거를 `glob` 으로 하면
    바로 아래 `except OSError` 가드가 아예 호출되지 않고 `is_complete=True`·경고 0건인 채로
    명부가 통째로 비어 버린다 — LS7 이 「가장 위험한 판정」이라 부른 실패(살아 있는데
    죽었다고 오판)를 무성음으로 만드는 경로다. `iterdir()` 은 같은 조건에서
    `PermissionError`(`OSError` 서브클래스)를 던져 이 가드에 정상적으로 걸린다.
    """
    try:
        if not sessions_dir.is_dir():
            return hub_live_session.LiveSessionIndex(by_session_id={}, is_complete=False), ()
    except OSError as error:
        return (
            hub_live_session.LiveSessionIndex(by_session_id={}, is_complete=False),
            (f"{sessions_dir}: 접근 실패 — 살아있는 세션 명부를 건너뜁니다 ({error})",),
        )

    try:
        record_paths = sorted(path for path in sessions_dir.iterdir() if path.suffix == ".json")
    except OSError as error:
        return (
            hub_live_session.LiveSessionIndex(by_session_id={}, is_complete=False),
            (f"{sessions_dir}: 목록 조회 실패 — 살아있는 세션 명부를 건너뜁니다 ({error})",),
        )

    records: list[hub_live_session.LiveSessionRecord] = []
    failed_count = 0
    for record_path in record_paths:
        record, failed = _read_one_record(record_path)
        if failed:
            failed_count += 1
        elif _is_process_alive(record.pid):
            records.append(record)

    warnings = ()
    if failed_count > 0:
        warnings = (f"{sessions_dir}: 살아있는 세션 명부 레코드 {failed_count}건을 읽지 못했습니다",)
    index = hub_live_session.build_live_session_index(records, is_complete=(failed_count == 0))
    return index, warnings
