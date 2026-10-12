"""hub_activity.py — 실행 중 활동 표시(결정 LA1~LA15, docs/prps/hub-live-activity.md)의 순수 해석 + 계약 타입.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_activity.py 대상). 호스트 기록 내용을
해석하는 이 기능의 코드는 전부 여기 있다 — 읽는 필드는 화이트리스트(T25-269), 내보내는 타입에는 자유 문자열이
없다(T25-270), 지금 시각을 받지 않는다(T25-271).

활동 값은 **파일 내용과 stat 의 함수**다(결정 LA11) — 같은 파일이면 같은 값이라 아무것도 돌지 않을 때
snapshot_content_key 는 오늘과 똑같이 안정적이다. 호스트 기록(agent-<id>.jsonl)은 우리가 소유하지 않는 외부
형식이라 이 모듈 하나에 가둔다(hub_transcript.py·hub_subagent.py 와 같은 이유). 문자열을 밖으로 내보내지 않는다 —
도구 이름은 5값 종류로 접어 분류에만 쓰고 버리며, 출력 파일 경로는 I/O 층이 파일 상태를 보는 데에만 쓰고 어떤
데이터 클래스에도 담기지 않는다. 해석 실패는 예외가 아니라 None·빈 값이다(계약 B — fail-open, 결정 LA12).

임포트는 hub_transcript.epoch_ms_from_iso8601 하나뿐이다("Z" 처리 사본을 만들지 않으려고, 결정 LA14).
`_json_object_or_none`·표지 줄 선별은 hub_subagent.py 의 사적 헬퍼와 같은 방식의 작은 사본이다 — 사적 심볼을
임포트하지 않는 관례를 따르고, 이 모듈이 hub_subagent 에 의존하지 않게 한다.
"""

import dataclasses
import itertools
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator, Literal, Mapping, NamedTuple, Sequence

from hub_transcript import epoch_ms_from_iso8601

ToolKind = Literal["read", "edit", "run", "delegate", "other"]
TOOL_KINDS: tuple[ToolKind, ...] = ("read", "edit", "run", "delegate", "other")

# 도구 이름 → 종류(결정 LA3). 표에 없는 이름(Skill·TodoWrite·AskUserQuestion·ToolSearch·mcp__* 등)과 문자열이 아닌
# 값은 "other" 다 — 호스트 목록의 사본을 늘리지 않는다(모르면 other, 페일오픈). mcp__<서버>__… 이름에는 사용자가
# 붙인 서버 이름이 들어 있어 종류만 싣고 이름은 싣지 않는다.
TOOL_KIND_BY_NAME: dict[str, ToolKind] = {
    "Read": "read", "Grep": "read", "Glob": "read", "LS": "read", "NotebookRead": "read",
    "WebFetch": "read", "WebSearch": "read",
    "Edit": "edit", "MultiEdit": "edit", "Write": "edit", "NotebookEdit": "edit",
    "Bash": "run", "BashOutput": "run", "KillShell": "run", "KillBash": "run", "Monitor": "run",
    "Agent": "delegate", "Task": "delegate", "SendMessage": "delegate", "Workflow": "delegate",
}

# 한 번 읽는 창 = 출력 경로를 찾는 범위(결정 LA2·LA6). 바쁜 날 기록 증가가 약 1.4MB/시간이라 40분 남짓을 덮는다 —
# 실행이 백그라운드 셸을 띄운 뒤 sleep·확인 루프(작은 줄)를 도는 전형에서 띄운 줄이 오래 창 안에 남는다.
ACTIVITY_WINDOW_BYTES = 1024 * 1024
# 줄 단위로 전량 해석하는 창(결정 LA2). 실측(E5): 256KiB 는 해석 0.8~1.1ms 에 바쁜 실행의 3~5분을 덮는다.
ACTIVITY_PARSE_BYTES = 256 * 1024
# 도구 개수 범위의 상한(결정 LA5) — 마지막 기록 기준이라 지금 시각과 무관하다.
RECENT_TOOL_WINDOW_MS = 10 * 60 * 1000
# 「새 기록 없음」을 띄우는 기록 공백(결정 LA8). 근거: M0 재생(2026-10-07) — 10분 넘는 과거 공백 48건은 전부
# 진행 중 호출이 있거나 일시정지(SubagentStop)였고 이 규칙이 모두 제외한다(오탐 0, 확인 불가 5건). 값을 바꾸면
# hub/README.md 의 고지도 같이 바꾼다.
SUBAGENT_STALL_SUSPECT_AFTER_MS = 10 * 60 * 1000
ACTIVITY_RUNS_MAX_PER_SESSION = 8          # 결정 LA2 — 화면 상한(5)의 여유이자 실측 동시 미종료 최대 4건의 2배
BACKGROUND_SCAN_SUBAGENTS_MAX = 8          # 결정 LA7
BACKGROUND_OUTPUT_MAX_FILES = 8            # 결정 LA6
# 호스트가 백그라운드 작업을 띄운 결과 본문에 적는 문구(E3) — 줄 선별 표지.
BACKGROUND_OUTPUT_MARKER = b"Output is being written to"

_LINE_SEPARATOR = b"\n"
_OUTPUT_FILE_SUFFIX = ".output"
_TASKS_DIRECTORY_NAME = "tasks"
_OUTPUT_PHRASE_PATTERN = re.compile(
    re.escape(BACKGROUND_OUTPUT_MARKER.decode("ascii")) + r":? *(/\S+?\.output)(?!\w)"
)
_OUTPUT_STEM_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
_PATH_PIECES_TO_REJECT = ("", ".", "..")
_MINIMUM_PATH_PIECES = 3                   # <세션>/tasks/<id>.output 의 세 조각


@dataclass(frozen=True)
class ToolKindCounts:
    """종류별 도구 호출 수 — 필드 이름이 곧 TOOL_KINDS 다."""

    read: int = 0
    edit: int = 0
    run: int = 0
    delegate: int = 0
    other: int = 0


@dataclass(frozen=True)
class BackgroundOutputView:
    """백그라운드 작업 출력 파일들의 stat 요약 — 파일은 열지 않는다(결정 LA6)."""

    file_count: int          # 지금 존재하는 정규 파일 수 1..BACKGROUND_OUTPUT_MAX_FILES
    updated_at_ms: int       # 그 파일들 수정 시각의 최댓값(ms)
    total_bytes: int         # 크기의 합


@dataclass(frozen=True)
class SubagentActivity:
    """도는 서브에이전트 실행 1건의 활동 — 호스트 기록 끝 창의 구조 값만(결정 LA3~LA5, LA8)."""

    last_record_at_ms: int                          # 창 안 마지막 기록의 시각
    last_tool_kind: ToolKind | None                 # 창 안 마지막 tool_use 의 종류
    pending_count: int                              # 결과가 아직 없는 tool_use 수
    pending_tool_kind: ToolKind | None              # 그중 가장 오래된 것의 종류 (pending_count == 0 ⇔ None)
    pending_since_ms: int | None                    # 그 시각 (pending_count == 0 ⇔ None)
    recent_tool_counts: ToolKindCounts              # [recent_counts_since_ms, last_record_at_ms] 의 tool_use 수
    recent_counts_since_ms: int                     # 개수 범위 하한(결정 LA5)
    stall_suspect_at_ms: int | None = None          # hub_session 이 채운다(결정 LA8). 결과 대기 호출이 있으면 None
    background_output: BackgroundOutputView | None = None   # I/O 층이 채운다(결정 LA6·LA7)


@dataclass(frozen=True)
class LiveActivity:
    """수집 1회의 활동 판독 — hub_collect → hub_project → hub_session 의 통로(뷰가 아니다, 직렬화되지 않는다)."""

    by_agent_id: Mapping[str, SubagentActivity]
    background_output_by_session_id: Mapping[str, BackgroundOutputView]


class _ToolUse(NamedTuple):
    use_id: str
    at_ms: int
    kind: ToolKind


class _ToolEvents(NamedTuple):
    uses: tuple[_ToolUse, ...]       # 파일 순서, 같은 id 는 첫 줄만
    result_ids: frozenset[str]


def classify_tool_kind(tool_name: object) -> ToolKind:
    """도구 이름을 5값 종류로 접는다. 표에 없거나 문자열이 아니면 "other"."""
    if not isinstance(tool_name, str):
        return "other"
    return TOOL_KIND_BY_NAME.get(tool_name, "other")


# ---- 줄 해석 공통 ----
def _json_object_or_none(line: bytes) -> dict | None:
    """한 줄(bytes)을 JSON 객체로 푼다. 깨졌거나 객체가 아니면 None — 예외를 던지지 않는다(계약 B).

    ValueError 는 구문 오류와 4,300자리 초과 정수 리터럴, RecursionError 는 깊은 중첩이다. 창은 파일 한가운데서
    시작하고 활성 기록은 동시에 append 중이라 찢긴 줄이 있을 수 있다 — `errors="replace"` 로 디코딩 오류 없이
    풀어 보고 JSON 실패면 건너뛴다.
    """
    try:
        payload = json.loads(line.decode("utf-8", errors="replace"))
    except (ValueError, RecursionError):
        return None
    return payload if isinstance(payload, dict) else None


def _content_blocks(payload: dict) -> list[dict]:
    """줄의 message.content 가 리스트면 그 안의 객체 블록들, 아니면 빈 목록."""
    message = payload.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _decoded_lines(window: bytes) -> list[tuple[int | None, dict]]:
    """창의 모든 줄을 (기록 시각 또는 None, 객체) 로 푼다 — 풀리지 않는 줄은 건너뛴다."""
    decoded = []
    for raw_line in window.split(_LINE_SEPARATOR):
        payload = _json_object_or_none(raw_line) if raw_line else None
        if payload is not None:
            decoded.append((epoch_ms_from_iso8601(payload.get("timestamp")), payload))
    return decoded


# ---- 안 A: 꼬리 창 활동 ----
def _tool_uses_of_line(blocks: Iterable[dict], at_ms: int) -> Iterator[_ToolUse]:
    for block in blocks:
        use_id = block.get("id")
        if block.get("type") == "tool_use" and isinstance(use_id, str):
            yield _ToolUse(use_id, at_ms, classify_tool_kind(block.get("name")))


def _tool_result_ids_of_line(blocks: Iterable[dict]) -> Iterator[str]:
    for block in blocks:
        use_id = block.get("tool_use_id")
        if block.get("type") == "tool_result" and isinstance(use_id, str):
            yield use_id


def _tool_events(lines: Sequence[tuple[int | None, dict]]) -> _ToolEvents:
    """assistant 줄의 tool_use 와 user 줄의 tool_result 짝 재료를 모은다(결정 LA4).

    같은 id 의 사본 줄은 첫 것만 센다 — 대화 기록 재부착이 같은 줄을 다시 붙인다. 호출은 줄 시각이 있어야 자리를
    잡는다. 결과는 시각이 없어도 짝을 푼다 — 결과를 버리면 거짓 진행 중이 생긴다.
    """
    uses: dict[str, _ToolUse] = {}
    result_ids: set[str] = set()
    for at_ms, payload in lines:
        line_type = payload.get("type")
        if line_type == "assistant" and at_ms is not None:
            for use in _tool_uses_of_line(_content_blocks(payload), at_ms):
                uses.setdefault(use.use_id, use)
        elif line_type == "user":
            result_ids.update(_tool_result_ids_of_line(_content_blocks(payload)))
    return _ToolEvents(tuple(uses.values()), frozenset(result_ids))


def _pending_calls(events: _ToolEvents) -> list[_ToolUse]:
    """결과가 아직 없는 호출들 — 창 밖에서 시작해 창 안에서 끝난 호출(결과만 보임)은 짝이 없어 자연히 빠진다."""
    return [use for use in events.uses if use.use_id not in events.result_ids]


def _recent_counts(uses: Sequence[_ToolUse], since_ms: int) -> ToolKindCounts:
    counts = Counter(use.kind for use in uses if use.at_ms >= since_ms)
    return ToolKindCounts(**{kind: counts[kind] for kind in TOOL_KINDS})


def parse_tool_activity(window: bytes) -> SubagentActivity | None:
    """기록 끝 창에서 활동을 읽는다(결정 LA2~LA5). 끝 ACTIVITY_PARSE_BYTES 만 줄 단위로 전량 해석한다.

    시각이 붙은 줄이 없거나 인식한 tool_use/tool_result 블록이 없으면 None — 호스트 형식이 바뀌었거나 아직 도구를
    안 쓴 실행이고, 이때 활동을 내면 형식 변경이 「새 기록 없음」 오탐으로 번진다(결정 LA12). 예외를 던지지 않는다.
    """
    lines = _decoded_lines(window[-ACTIVITY_PARSE_BYTES:])
    record_times = [at_ms for at_ms, _ in lines if at_ms is not None]
    if not record_times:
        return None
    events = _tool_events(lines)
    if not events.uses and not events.result_ids:
        return None
    last_record_at_ms = max(record_times)
    recent_counts_since_ms = max(min(record_times), last_record_at_ms - RECENT_TOOL_WINDOW_MS)
    pending = _pending_calls(events)
    oldest_pending = min(pending, key=lambda use: use.at_ms) if pending else None
    return SubagentActivity(
        last_record_at_ms=last_record_at_ms,
        last_tool_kind=events.uses[-1].kind if events.uses else None,
        pending_count=len(pending),
        pending_tool_kind=oldest_pending.kind if oldest_pending else None,
        pending_since_ms=oldest_pending.at_ms if oldest_pending else None,
        recent_tool_counts=_recent_counts(events.uses, recent_counts_since_ms),
        recent_counts_since_ms=recent_counts_since_ms,
    )


# ---- 안 B: 출력 경로 찾기 ----
def _marker_lines_backwards(window: bytes) -> Iterator[bytes]:
    """BACKGROUND_OUTPUT_MARKER 를 품은 줄을 파일에서 뒤에 있는 것부터 차례로 낸다. 표지 없는 줄은 만지지 않는다.

    표지를 rfind 로 건너뛰며 찾는다 — 줄마다 개행을 거슬러 찾는 방식보다 빠르다(hub_subagent 의 같은 방식, PRP
    §2.1 구현 측정). UTF-8 에서 개행 바이트(0x0A)는 다중 바이트 글자 안에 나오지 않아 줄 경계가 안전하다.
    """
    hit = window.rfind(BACKGROUND_OUTPUT_MARKER)
    while hit >= 0:
        line_start = window.rfind(_LINE_SEPARATOR, 0, hit) + 1
        newline_index = window.find(_LINE_SEPARATOR, hit)
        yield window[line_start:(len(window) if newline_index < 0 else newline_index)]
        hit = window.rfind(BACKGROUND_OUTPUT_MARKER, 0, line_start)


def _tool_result_bodies(payload: dict) -> Iterator[str]:
    """user 줄의 tool_result 블록마다 본문 하나 — 문자열이면 그대로, text 블록 리스트면 text 들을 줄바꿈으로 잇는다."""
    if payload.get("type") != "user":
        return
    for block in _content_blocks(payload):
        if block.get("type") != "tool_result":
            continue
        content = block.get("content")
        if isinstance(content, str):
            yield content
        elif isinstance(content, list):
            texts = [
                part["text"] for part in content
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
            ]
            if texts:
                yield "\n".join(texts)


def _valid_output_path(body: str, session_id: str) -> str | None:
    """본문에서 호스트 문구의 출력 경로를 찾아 형태 검증 5조건(결정 LA6)을 모두 통과하면 돌려준다.

    ① 위치(user 줄의 tool_result 블록 안)는 호출자가 보장한다. ② 문구 ③ 모양(절대경로·빈/./.. 조각 없음·NUL 없음·
    파일 이름 줄기 [A-Za-z0-9_-]{1,64}) ④ 위치 규칙(부모 디렉터리 tasks, 조부모 디렉터리 == 이 세션) ⑤ 짝(같은 본문에
    `ID: <줄기>`). NUL 은 파일 상태를 보는 쪽에서 예외를 내므로 여기서 거른다.
    """
    match = _OUTPUT_PHRASE_PATTERN.search(body)
    if match is None or "\x00" in match.group(1):
        return None
    path = match.group(1)
    pieces = path.split("/")[1:]
    if len(pieces) < _MINIMUM_PATH_PIECES or any(piece in _PATH_PIECES_TO_REJECT for piece in pieces):
        return None
    grandparent, parent, file_name = pieces[-3:]
    stem = file_name[:-len(_OUTPUT_FILE_SUFFIX)]
    if not _OUTPUT_STEM_PATTERN.fullmatch(stem):
        return None
    if parent != _TASKS_DIRECTORY_NAME or grandparent != session_id:
        return None
    if re.search(r"(?<![\w-])ID: " + re.escape(stem) + r"(?![\w-])", body) is None:
        return None
    return path


def _output_paths_backwards(window: bytes, session_id: str) -> Iterator[str]:
    for line in _marker_lines_backwards(window):
        payload = _json_object_or_none(line)
        if payload is None:
            continue
        for body in _tool_result_bodies(payload):
            path = _valid_output_path(body, session_id)
            if path is not None:
                yield path


def _distinct(items: Iterable[str]) -> Iterator[str]:
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            yield item


def background_output_paths(window: bytes, session_id: str) -> tuple[str, ...]:
    """창에서 이 세션의 백그라운드 작업 출력 파일 경로를 찾는다 — 파일에서 뒤의 것부터, 중복 제거, 최대 8개(결정 LA6).

    반환은 **내부 값**이다 — I/O 층이 파일 상태를 보는 데에만 쓰고 어떤 데이터 클래스에도 담지 않는다.
    예외를 던지지 않는다.
    """
    distinct_paths = _distinct(_output_paths_backwards(window, session_id))
    return tuple(itertools.islice(distinct_paths, BACKGROUND_OUTPUT_MAX_FILES))


def summarize_background_outputs(file_stats: Sequence[tuple[int, int]]) -> BackgroundOutputView | None:
    """(수정 시각 ms, 크기) 들을 (파일 수, 최신 시각, 크기 합) 으로 접는다. 파일이 없으면 None."""
    if not file_stats:
        return None
    return BackgroundOutputView(
        file_count=len(file_stats),
        updated_at_ms=max(modified_at_ms for modified_at_ms, _ in file_stats),
        total_bytes=sum(size for _, size in file_stats),
    )


def with_stall_suspect_at(activity: SubagentActivity, run_started_at_ms: int) -> SubagentActivity:
    """「새 기록 없음」을 띄울 정적 시각을 채운 새 활동을 돌려준다(결정 LA8). 입력은 바꾸지 않는다.

    결과를 기다리는 호출이 있으면 None. 아니면 max(마지막 기록, 실행 시작) + 임계다 — 재개되면 시작 시각이 재개
    시각으로 덮이므로(TF7) 일시정지 동안 비어 있던 기록 시각으로 재개 직후 바로 표지가 뜨는 것을 막는다.
    """
    if activity.pending_count > 0:
        return dataclasses.replace(activity, stall_suspect_at_ms=None)
    quiet_since_ms = max(activity.last_record_at_ms, run_started_at_ms)
    return dataclasses.replace(activity, stall_suspect_at_ms=quiet_since_ms + SUBAGENT_STALL_SUSPECT_AFTER_MS)
