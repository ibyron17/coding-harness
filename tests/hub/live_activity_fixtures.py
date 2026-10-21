"""실행 중 활동 표시(docs/prps/hub-live-activity.md)의 합성 기록 줄 픽스처 — 여러 테스트 모듈이 공유한다.

전부 합성이다: 줄은 테스트 안에서 json.dumps 로 만든다. 실제 경로·프롬프트·기록을 넣지 않는다. 도구 입력·출력 자리에는
SENTINEL 값을 넣어, 어느 층이든 그 내용이 새면 카나리가 잡게 한다.
"""

import json
from datetime import datetime, timezone

BASE_MS = 1_791_370_000_000
SECOND_MS = 1_000
MINUTE_MS = 60_000
SESSION_ID = "11111111-2222-3333-4444-555555555555"
SENTINEL_INPUT = "SENTINEL-INPUT"
SENTINEL_OUTPUT = "SENTINEL-OUTPUT"


def iso(epoch_ms: int) -> str:
    """epoch ms → 호스트 기록과 같은 UTC "Z" 문자열."""
    moment = datetime.fromtimestamp(epoch_ms // SECOND_MS, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % SECOND_MS:03d}Z"


def line(line_type: str, epoch_ms: int, blocks: object = None) -> dict:
    """기록 줄 하나(type·timestamp, blocks 가 있으면 message.content)."""
    payload: dict = {"type": line_type, "timestamp": iso(epoch_ms)}
    if blocks is not None:
        payload["message"] = {"role": line_type, "content": blocks}
    return payload


def use_line(epoch_ms: int, use_id: str, name: object = "Read") -> dict:
    """assistant 줄 — tool_use 블록 하나(입력에는 SENTINEL)."""
    block = {"type": "tool_use", "id": use_id, "name": name, "input": {"payload": SENTINEL_INPUT}}
    return line("assistant", epoch_ms, [block])


def result_line(epoch_ms: int, use_id: str, content: object = SENTINEL_OUTPUT) -> dict:
    """user 줄 — tool_result 블록 하나."""
    return line("user", epoch_ms, [{"type": "tool_result", "tool_use_id": use_id, "content": content}])


def jsonl_bytes(*lines: object) -> bytes:
    """줄들을 한 줄에 하나씩 이은 기록 파일 내용."""
    return b"".join(json.dumps(item).encode("utf-8") + b"\n" for item in lines)


def output_phrase(session_id: str, task_id: str, directory: str = "tasks", root: str = "/t/x") -> str:
    """호스트가 백그라운드 작업을 띄운 결과 본문에 적는 문구(경로는 root/<세션>/<디렉터리>/<id>.output)."""
    return (
        f"Command running in background with ID: {task_id}. "
        f"Output is being written to: {root}/{session_id}/{directory}/{task_id}.output"
    )


def moved_phrase(session_id: str, task_id: str, root: str = "/t/x") -> str:
    """타임아웃에 포그라운드 명령이 백그라운드로 옮겨졌을 때 호스트가 적는 결과 본문(실측 문장, 경로 뒤에 마침표가 붙는다)."""
    return (
        f"Command did not complete within its 120s timeout and was moved to the background (ID: {task_id}). "
        f"Output is being written to: {root}/{session_id}/tasks/{task_id}.output. "
        "You will be notified when it completes. To check interim output, use Read on that file path."
    )
