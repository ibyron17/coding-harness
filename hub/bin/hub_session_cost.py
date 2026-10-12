"""hub_session_cost.py — 세션 비용 캡처 파일의 I/O 층(⑨, docs/prps/harness-benchmark-adoption.md §6-1·§7-1).

statusLine 이 알려 준 세션별 누적 비용·API 시간·컨텍스트 사용률을 `~/.claude/hub/session_costs/
<session_id>.json` 에 한 세션당 파일 하나로 둔다. 쓰는 쪽은 hub_statusline.py(0.3초 주기, 값이 바뀔 때만),
읽는 쪽은 hub_collect.py(수집 1회마다 보이는 세션들 것만)다. 파서·판정은 순수 모듈 hub_usage.py 에 있다
(★순수가 아니다 — 파일시스템에 닿는다. tests/run.sh T25-10 의 순수 파일 목록에 넣지 말 것).

파일 내용에는 프롬프트·응답이 없다 — 숫자 세 개와 관측 시각뿐이다. 세션 ID 는 UUID 형식 검증을 통과한 값만
파일 이름 키로 쓴다(`/`·`..` 가 매치될 수 없어 경로 탈출이 차단된다). 읽기 실패·계약 위반은 전부 None 이다
(경고를 내지 않는다 — 세션별 파일이라 경고가 세션 수만큼 늘 수 있다). 임포트는 hub_atomic_write(잎)와
hub_usage(순수)뿐이라 hub_collect 와 순환하지 않는다.
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import hub_atomic_write
import hub_usage

HUB_HOME = Path.home() / ".claude" / "hub"
SESSION_COSTS_DIR = HUB_HOME / "session_costs"
SESSION_COST_FILE_SUFFIX = ".json"
SESSION_COST_ATOMIC_WRITE_PREFIX = "session_cost."


def _capture_path(session_id: str) -> Path:
    return SESSION_COSTS_DIR / f"{session_id}{SESSION_COST_FILE_SUFFIX}"


def read_session_cost(session_id: str) -> hub_usage.SessionCost | None:
    """세션 하나의 캡처를 읽는다. 형식이 틀린 ID·부재·읽기 실패·계약 위반은 전부 None(예외 없음)."""
    if not hub_usage.is_valid_session_id(session_id):
        return None
    try:
        text = _capture_path(session_id).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return hub_usage.parse_session_cost_capture(text)


def write_session_cost(session_id: str, cost: hub_usage.SessionCost) -> None:
    """원자적으로 쓴다(hub_statusline 전용 쓰기 경로). 형식이 틀린 ID 면 아무것도 하지 않는다."""
    if not hub_usage.is_valid_session_id(session_id):
        return
    SESSION_COSTS_DIR.mkdir(parents=True, exist_ok=True)
    hub_atomic_write.atomic_write_text(
        _capture_path(session_id), SESSION_COSTS_DIR, SESSION_COST_ATOMIC_WRITE_PREFIX, json.dumps(asdict(cost))
    )


def read_session_costs(session_ids: Iterable[str]) -> dict[str, hub_usage.SessionCost]:
    """수집용 — 캡처가 있는 세션만 담은 dict."""
    if not SESSION_COSTS_DIR.is_dir():
        return {}
    costs_by_session_id: dict[str, hub_usage.SessionCost] = {}
    for session_id in set(session_ids):
        cost = read_session_cost(session_id)
        if cost is not None:
            costs_by_session_id[session_id] = cost
    return costs_by_session_id


def prune_old_session_cost_files(now_ms: int, retention_days: int) -> None:
    """보관 기간(mtime 기준)을 넘긴 캡처 파일을 지운다. 파일 단위로 실패를 흡수한다."""
    if not SESSION_COSTS_DIR.is_dir():
        return
    cutoff_seconds = (now_ms - retention_days * hub_usage.MILLISECONDS_PER_DAY) / hub_usage.MILLISECONDS_PER_SECOND
    for file_path in SESSION_COSTS_DIR.glob(f"*{SESSION_COST_FILE_SUFFIX}"):
        try:
            if file_path.stat().st_mtime < cutoff_seconds:
                file_path.unlink(missing_ok=True)
        except OSError:
            continue  # 다른 프로세스가 지웠거나 권한이 없다 — 다음 수집에서 다시 본다
