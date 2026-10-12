"""hub_subagent.py — subagents/agent-<id>.meta.json 실행 기록의 순수 파서 + 표시용 뷰.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_subagent.py 대상).
subagents/agent-<agentId>.meta.json(~/.claude/projects/<인코딩>/<session_id>/subagents/)은
우리가 소유하지 않는 외부 파일 형식이다 — hub_transcript.py·hub_workflow.py 가 세운 선례와
같은 이유로, 그 계약이 바뀌면 이 모듈 하나만 고치면 되도록 hub_session_facts.py("훅 이벤트 →
세션 사실"이라는 단일 입력원 계약)에 얹지 않고 분리했다(결정 AR1·AR2,
docs/prps/hub-agent-runs-and-prompt-source.md). 파일 접근(stat·읽기)은 전부
hub_subagent_read.py 가 맡는다 — 이 모듈은 이미 읽힌 텍스트와 I/O 층이 구한 mtime 만 받는다.

**결정 TF8·TF10·TF13(docs/prps/hub-agent-title-and-excerpt-freshness.md)** — 재개된 실행의 새 작업
이름(`resume_title`)도 이 모듈이 판다. 그 이름은 meta.json 이 아니라 **부모 transcript** 의 재개 요청
(`SendMessage` tool_use 의 `input.summary`)에만 있다. 부모 transcript 줄인데도 이 모듈에 둔 이유
(PS1 의 「같은 외부 계약이면 같은 모듈」 기준의 예외): (1) 뽑는 것이 실행 제목이고 계약 A 의 유일한 거처가
여기다 (2) 읽는 창(수 MiB)·게이트(`record_prompt_excerpt`)·트리거(재개된 실행이 있을 때만)가
hub_transcript.py 의 꼬리 스캔(128KiB, 항상)과 모두 다르다. 창 읽기는 역시 hub_subagent_read.py 가 맡는다.

**계약 A(hub_workflow.py 머리의 계약 A 를 그대로 적용 — 결정 AR10)**: hub.html 에 인라인되는
이 모듈의 문자열 필드는 예외 없이 아래 둘 중 하나의 경로를 거친다.

1. **스크럽 + 120자 상한** (`_scrubbed_and_clipped`, SUBAGENT_TITLE_MAX_CHARS) — `title`
   (=`description`)과 `resume_title`(=재개 요청의 `summary`)만. 사용자 프롬프트에서 파생된 자유
   텍스트라 시크릿이 섞일 수 있다(`label` 이 같은 경위로 스크럽 대상이 됐다, hub_workflow.py 결정
   WF7). SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS 를 넘는 글은 제목이 아니라 스크럽 없이 버린다(상수 주석).
2. **32자 상한만, 스크럽 없음** (`_metadata_field`/`clip_metadata`, SUBAGENT_METADATA_MAX_CHARS)
   — `model`·`agent_type`. 닫힌 값 집합 성격(실측 sonnet·opus·haiku·fable 4종, max 6자)이라
   스크럽을 생략하지만 상한은 예외 없이 건다.

`_clip_to_length` 는 hub_workflow.py 의 것과 동작이 같다. **복제하지 않고 임포트도 하지
않는다**(사적 심볼 임포트 금지) — 두 모듈이 각자 3줄짜리 동일 구현을 갖는 것과 공용 모듈을
하나 더 만드는 것 중 전자를 택했다(결정 AR2 근거 문단 — 문자열 자르기에는 hub_redact.py
추출의 근거였던 "패턴 복제 = 보안 드리프트" 성질이 없다).
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass

from hub_redact import redact_secret_tokens

SUBAGENT_DIR_NAME = "subagents"                 # <session_id>/ 아래 메타 디렉터리
SUBAGENT_META_FILE_PREFIX = "agent-"
SUBAGENT_META_FILE_SUFFIX = ".meta.json"
# 서브에이전트 자신의 transcript 접미사(결정 SL1, docs/prps/hub-subagent-liveness-signal.md) —
# 실행 내내 append 되는 파일이라 그 mtime 이 생존 신호다(죽은 프로세스는 파일에 쓸 수 없다).
# 내용은 읽지 않으므로(stat 1회) 파서 함수는 추가하지 않는다 — 파일 형식 상수만 이 모듈의
# 관례(SUBAGENT_META_FILE_SUFFIX 선례)를 따라 여기 둔다.
SUBAGENT_TRANSCRIPT_FILE_SUFFIX = ".jsonl"
# 64KiB — 실측 max 약 300B(§1.1)의 200배 방어선. 크기 검사 자체는 I/O 층(hub_subagent_read.py)
# 이 하지만, hub_workflow.WORKFLOW_RUN_MAX_BYTES 와 같은 이유로 상수는 파서 모듈에 둔다.
SUBAGENT_META_MAX_BYTES = 64 * 1024
# description 실측 max 51자(818건 전수, §1.1)의 2.35배 — 병리적 입력 방어선(결정 AR10).
SUBAGENT_TITLE_MAX_CHARS = 120
# 제목(description·재개 요약)으로 받아들이는 글의 최대 길이 — 제목 상한의 10배. 이걸 넘는 글은 제목이 아니므로 스크럽(redact_secret_tokens)에
# 넘기지 않고 통째로 버린다(빈 제목, _scrubbed_and_clipped). 이유 둘. (1) 가용성: 두 제목 모두 호스트 소유 파일의 자유 텍스트라 길이 보장이
# 없다(meta.json 은 64KiB 까지 읽고, 재개 요청은 줄 하나가 수 MiB 여도 읽힌다). 스크럽의 JWT 대안(`eyJ…` 뒤에 점 둘)은 점 없이 `eyJ` 가 반복되는
# 긴 글에서 길이의 제곱에 비례해 느려진다(128KiB 에 8초 — hub_redact 참고). 이 길이까지는 최악도 1ms 안팎이다. (2) 마스킹: 상한에서 잘라
# 스크럽하면 자른 자리에 걸린 시크릿 — 서명이 창 밖인 JWT, 닫는 따옴표가 창 밖인 password="…" 값 — 이 패턴을 못 채워 마스킹되지 않은 머리가 제목
# 앞 120자로 나간다(M2 검수 MEDIUM; 기준 커밋은 전체를 스크럽해 둘 다 마스킹했다). 잘라 쓰지 않고 버리면 이 경계 위험이 전부 닫힌다 — 실측 제목은
# max 51자(description)·50자(재개 요약 225건)라 버려서 잃는 것이 없고, 상한 이하는 기준 커밋과 같다(전체 스크럽 뒤 120자).
SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS = 1200
# model·agent_type·agent_id 공용(결정 AR10) — 닫힌 값 집합 성격(model 실측 max 6자)에
# 넉넉한 여유를 둔 상한이다.
SUBAGENT_METADATA_MAX_CHARS = 32
SUBAGENT_TRUNCATION_MARK = "…"

# 서버측 방어선(결정 AR11, docs/prps/hub-agent-runs-and-prompt-source.md) — 세션당 화면에
# 실을 실행 뷰 개수의 상한. "화면에 몇 개 보일까"(클라이언트 MAX_VISIBLE_AGENT_RUNS=5)가
# 아니라 "병리적 페이로드가 뷰 직렬화를 얼마나 부풀릴 수 있는가"를 막는다. 2일 창 실측
# 세션당 최대 45건의 2.2배 — hub_workflow.WORKFLOW_RUN_MAX_AGENTS 와 같은 역할·같은 값이다.
# hub_session.summarize_agent_runs(표시 절단)와 hub_subagent_read.read_subagent_metas(읽기
# 예산) 둘 다 이 값을 쓴다 — SUBAGENT_META_MAX_BYTES 와 같은 이유로 상수는 파서 모듈에
# 둔다(재검수 1회차 L1 — hub_session.py 에 있던 것을 이곳으로 옮겼다).
SUBAGENT_RUN_MAX_PER_SESSION = 100

# ---- 재개 요청 (결정 TF8, docs/prps/hub-agent-title-and-excerpt-freshness.md) ----
# 호스트가 SendMessage 로 재개한 에이전트의 새 작업 이름은 meta.json 이 아니라 부모 transcript 의 재개 요청(tool_use 의 input.summary)에만 있다
# — 재개 때 meta.json 이 다시 쓰여도 description 은 첫 띄움 값 그대로다(실측 6/6). 그 요청이 정말 재개였는지는 같은 tool_use_id 의 결과 줄
# (toolUseResult.resumedAgentId)이 알려 준다 — 실행 중인 에이전트에게 메시지를 「전달」만 한 요청에는 그 키가 없다(실측 189/189 대 20).
RESUME_REQUEST_TOOL_NAME = "SendMessage"
RESUMED_AGENT_ID_KEY = "resumedAgentId"
# 줄을 디코딩·json 으로 풀기 전에 거르는 부분 바이트열 — 창이 수 MiB 라 모든 줄을 풀면 느리다(창은 bytes 로 들고 있다: PRP §2.1 구현 측정).
# 따옴표째 적어 본문 속 언급(JSON 안에서는 따옴표가 이스케이프돼 이 모양이 아니다)은 걸러진다. 결과 줄은 첫째로 찾고, 요청 줄은 풀어야 할
# 결과를 만난 뒤 그 줄 앞에서만 찾는다(parse_resume_titles).
RESUME_RESULT_LINE_MARKER = ('"' + RESUMED_AGENT_ID_KEY + '"').encode("ascii")
RESUME_REQUEST_LINE_MARKER = ('"' + RESUME_REQUEST_TOOL_NAME + '"').encode("ascii")
LINE_SEPARATOR = b"\n"   # transcript 는 JSONL — 줄은 개행 바이트로만 가른다(JSON 문자열 안의 U+2028 등은 줄 경계가 아니다)


@dataclass(frozen=True)
class SubagentMeta:
    """실행 1건의 호스트 기록 투영 — meta.json 1건(title·agent_type·model·started_at_ms)과, 재개됐으면 부모 transcript 의 마지막
    재개 요청 요약(resume_title, 결정 TF8·TF13). 전부 계약 A 를 거친 값이다."""

    title: str          # description. 스크럽 + SUBAGENT_TITLE_MAX_CHARS. 없으면 ""
    agent_type: str     # 32자 상한만. 없으면 ""
    model: str | None   # 별칭(sonnet/opus/haiku/fable). 32자 상한만. 키 부재 실측 18.7% → None
    started_at_ms: int  # 파일 수정 시각(ms). 파서가 아니라 I/O 층이 채운다(★순수 — stat 을 부를 수 없다)
    # 마지막 재개 요청의 summary(스크럽 + SUBAGENT_TITLE_MAX_CHARS). 재개 아님·요약 없음·읽는 창 밖이면 None. meta.json 만으로는 만들 수 없다 —
    # I/O 층이 부모 transcript 창을 읽어 얹는다(parse_subagent_meta 는 항상 None)
    resume_title: str | None = None


# ---- 타입 방어 (호스트 소유 형식이라 타입 보장이 없다) ----
def _string_or_empty(value: object) -> str:
    """값이 문자열이면 그대로, 아니면 빈 문자열(hub_workflow._string_or_empty 와 같은 모양)."""
    return value if isinstance(value, str) else ""


def _clip_to_length(value: str, max_chars: int) -> str:
    """value 가 max_chars 를 넘으면 잘라 말줄임표를 붙인다(hub_workflow._clip_to_length 와 동형)."""
    if len(value) <= max_chars:
        return value
    keep_length = max_chars - len(SUBAGENT_TRUNCATION_MARK)
    return value[:keep_length] + SUBAGENT_TRUNCATION_MARK


def clip_metadata(value: str) -> str:
    """32자 상한만 적용한다(스크럽 없음) — 훅 유래 agent_type·agent_id 에도 쓰도록 공개한다
    (hub_session.summarize_agent_runs 가 재사용, 결정 AR10 소급 적용)."""
    return _clip_to_length(value, SUBAGENT_METADATA_MAX_CHARS)


def _metadata_field(value: object) -> str:
    """문자열이면 clip_metadata 로 자르고, 아니면 빈 문자열 — agent_type 경로(계약 A)."""
    return clip_metadata(_string_or_empty(value))


def _scrubbed_and_clipped(value: str) -> str:
    """title·resume_title 이 거치는 경로 — 스크럽 후 SUBAGENT_TITLE_MAX_CHARS 로 자른다. SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS 를 넘는 글은
    제목이 아니므로 스크럽도 하지 않고 빈 문자열(제목 없음)로 버린다.

    순서 고정: 스크럽 → 자르기. 자르기부터 하면 절단 경계에 걸린 시크릿이 패턴 불일치로
    살아남아 접두사가 샌다(hub_redact.redact_secret_tokens 문서, hub_workflow.py 의
    _scrubbed_and_clipped 와 같은 이유). 상한에서 잘라 스크럽하는 것도 같은 구멍이다 — 자른 자리에 걸린 JWT·따옴표 값의 머리가 마스킹되지
    않는다(M2 검수 MEDIUM) — 그래서 잘라 쓰지 않고 통째로 버린다. 길이가 상한 이하이면 기준 커밋과 같다(전체 스크럽 뒤 제목 상한으로 자른다).
    """
    if len(value) > SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS:
        return ""
    return _clip_to_length(redact_secret_tokens(value), SUBAGENT_TITLE_MAX_CHARS)


def parse_subagent_meta(text: str, started_at_ms: int) -> SubagentMeta | None:
    """meta.json 본문을 표시용 뷰로 판다. 형식이 아니면 None(호출자가 건너뛴다).

    **계약 B(hub_workflow.parse_workflow_run 과 동형) — 어떤 입력에도 예외를 던지지 않는다.**
    json.loads 는 ValueError(구문 오류 + 4,300자리 초과 정수 리터럴)와 RecursionError 를
    함께 잡는다. isinstance 로만 방어하고 agent_type·model 값을 표로 좁히지 않는다 —
    실측에 없는 값이 나와도 화면이 죽지 않아야 한다.
    """
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None

    title = _scrubbed_and_clipped(_string_or_empty(payload.get("description")))
    agent_type = _metadata_field(payload.get("agentType"))
    raw_model = payload.get("model")
    model = _metadata_field(raw_model) if isinstance(raw_model, str) else None

    return SubagentMeta(title=title, agent_type=agent_type, model=model, started_at_ms=started_at_ms)


# ---- 재개 요청 파서 (결정 TF8·TF10) ----
def _json_object_or_none(line: bytes) -> dict | None:
    """한 줄(bytes)을 디코딩해 JSON 객체로 푼다. 깨졌거나 객체가 아니면 None — 예외를 던지지 않는다(계약 B: ValueError 는 구문 오류 +
    4,300자리 초과 정수 리터럴, RecursionError 는 깊은 중첩).

    `errors="replace"` (GOTCHA 7) — 창은 파일 한가운데서 시작하고(멀티바이트 글자가 찢긴 첫 줄) 활성 세션이 동시에 append 중이라
    엄격한 디코딩은 줄을 통째로 버린다. 깨진 바이트는 U+FFFD 가 될 뿐 JSON 구조를 깨지 않는 한 줄은 그대로 풀린다.
    """
    try:
        payload = json.loads(line.decode("utf-8", errors="replace"))
    except (ValueError, RecursionError):
        return None
    return payload if isinstance(payload, dict) else None


def _lines_with_marker_backwards(window: bytes, marker: bytes, bound: int) -> Iterator[tuple[int, int]]:
    """window[:bound] 안에서 marker 를 품은 줄의 (시작, 끝) 을 파일에서 뒤에 있는 것부터 차례로 낸다. bound 는 줄의 시작이어야 한다.

    표지를 rfind 로 건너뛰며 찾는다 — 각 구간을 한 번만 훑고 표지 없는 줄은 만지지 않는다. 줄마다 개행을 거슬러 찾는 방식은 창 전체를 바이트
    단위로 거슬러 읽어 3배 느렸다(PRP §2.1 구현 측정). UTF-8 에서 개행 바이트(0x0A)는 다중 바이트 글자 안에 나오지 않아 줄 경계가 안전하다.
    한 줄에 표지가 여럿이어도 그 줄은 한 번만 낸다. 창 머리의 찢긴 첫 줄도 다른 줄처럼 나오고, 풀리지 않아 탈락한다.
    """
    hit = window.rfind(marker, 0, bound)
    while hit >= 0:
        line_start = window.rfind(LINE_SEPARATOR, 0, hit) + 1
        newline_index = window.find(LINE_SEPARATOR, hit)
        yield line_start, (len(window) if newline_index < 0 else newline_index)
        hit = window.rfind(marker, 0, line_start)


def _content_blocks(payload: dict) -> list[dict]:
    """줄의 message.content 가 리스트면 그 안의 객체 블록들, 아니면 빈 목록."""
    message = payload.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _resumed_agent_of_result_line(payload: dict) -> tuple[str, str] | None:
    """결과 줄이 「이 요청이 이 에이전트를 재개했다」를 알리면 (tool_use_id, resumedAgentId), 아니면 None.

    tool_result 블록이 정확히 1개인 줄만 매핑한다 — toolUseResult 는 줄 단위라 블록이 여럿이면 누구 결과인지 알 수 없다(결정 TF8 방어).
    """
    tool_use_result = payload.get("toolUseResult")
    if not isinstance(tool_use_result, dict):
        return None
    result_blocks = [block for block in _content_blocks(payload) if block.get("type") == "tool_result"]
    if len(result_blocks) != 1:
        return None
    request_id = result_blocks[0].get("tool_use_id")
    resumed_agent_id = tool_use_result.get(RESUMED_AGENT_ID_KEY)
    if not (isinstance(request_id, str) and isinstance(resumed_agent_id, str)):
        return None
    return request_id, resumed_agent_id


def _resume_requests_of_assistant_line(payload: dict) -> list[tuple[str, object]]:
    """assistant 줄의 SendMessage tool_use 들의 (tool_use id, input.summary 원값). 본문(input.message)은 꺼내지 않는다."""
    requests = []
    for block in _content_blocks(payload):
        request_id = block.get("id")
        tool_input = block.get("input")
        is_resume_request = block.get("type") == "tool_use" and block.get("name") == RESUME_REQUEST_TOOL_NAME
        if is_resume_request and isinstance(request_id, str) and isinstance(tool_input, dict):
            requests.append((request_id, tool_input.get("summary")))
    return requests


def _resume_summary_title(raw_summary: object) -> str | None:
    """재개 요청의 summary 를 계약 A 로 제목으로 만든다. 문자열이 아니거나 공백뿐이거나 스크럽 뒤 비면 None(제목 없음)."""
    if not isinstance(raw_summary, str) or not raw_summary.strip():
        return None
    return _scrubbed_and_clipped(raw_summary.strip()) or None


# 요청 색인(_request_summary) — tool_use id 마다 그 id 를 가진 요청 줄 모두의 (줄 시작, input.summary 원값), 줄 시작이 큰 것(파일에서 뒤)부터
_RequestIndex = dict[str, list[tuple[int, object]]]


def _resume_requests_backwards(window: bytes, bound: int) -> Iterator[tuple[str, int, object]]:
    """window[:bound] 의 재개 요청(SendMessage tool_use)을 파일에서 뒤에 있는 것부터 (tool_use id, 줄 시작, input.summary 원값) 으로 차례로 낸다."""
    for line_start, line_end in _lines_with_marker_backwards(window, RESUME_REQUEST_LINE_MARKER, bound):
        payload = _json_object_or_none(window[line_start:line_end])
        if payload is None:
            continue
        for request_id, raw_summary in _resume_requests_of_assistant_line(payload):
            yield request_id, line_start, raw_summary


def _request_summary(
    window: bytes, request_id: str, bound: int, request_index: _RequestIndex | None
) -> tuple[object, _RequestIndex | None]:
    """결과 줄(시작 bound) 앞에서 tool_use id 가 request_id 인 재개 요청의 input.summary 원값을 찾는다(없으면 None). 둘째 반환값은 다음
    조회에 넘길 요청 색인({tool_use id: [(줄 시작, summary 원값), …]}, 줄 시작 내림차순) — 아직 없으면 None.

    요청 줄은 자기 결과 줄보다 앞에 있다(인과). 실측 225쌍 전부 짝이 맞았고 요청 줄이 결과 줄 앞 중앙 6.5KB·최대 30KB 에 있어 정상 경로의 탐색은
    짧다 — 색인 없이 결과 줄 앞을 뒤에서부터 훑어 첫 짝에서 멈춘다. 요청을 못 찾았다면(호스트 형식이 바뀐 드문 경우) 그 훑기는 bound 앞 전체였고,
    결과 줄마다 그 훑기를 되풀이하면 결과 수 × 요청 수로 느려진다(검수 LOW-1; 합성 결과 100개 × 요청 2000줄에서 604ms → 색인 뒤 6.8ms). 그래서
    첫 미스 때 훑으며 본 요청을 그대로 색인으로 남기고(다시 해석하지 않는다) 이후 조회는 색인만 본다. 결과 줄은 뒤에서 앞으로 차례로 오므로 이후 조회의 bound 는 색인을 만든
    bound 이하다 — 색인이 빠뜨리는 요청은 없다. 색인은 자기 결과 줄 뒤의 요청도 담고 있어 위치 조건(줄 시작 < bound)으로 거른다. 그때도 제목 없음으로
    안전하게 강등된다.

    같은 tool_use id 의 줄이 여럿일 수 있다(대화 기록 재부착이 같은 줄을 다시 붙인다: 최근 90일 재개 요청 263건 중 44개 id 가 2~7번). 색인이 id 마다
    파일에서 가장 뒤의 사본 하나만 남기면, 그 사본이 자기 결과 줄보다 뒤이고 더 앞에 짝 사본이 있을 때 색인 경로만 제목을 잃어 정상 경로와 답이 갈린다(M2 검수 LOW).
    그래서 id 마다 모든 사본을 줄 시작 내림차순으로 남기고, 줄 시작이 bound 보다 앞인 첫 사본 — 정상 경로와 같은, 결과 줄에 가장 가까운 앞 사본 — 을 고른다.
    """
    if request_index is not None:
        copies = request_index.get(request_id, ())   # 색인에 없으면 빈 목록 → None
        return next((raw_summary for line_start, raw_summary in copies if line_start < bound), None), request_index
    seen_requests: _RequestIndex = {}
    for found_id, line_start, raw_summary in _resume_requests_backwards(window, bound):
        if found_id == request_id:
            return raw_summary, None
        seen_requests.setdefault(found_id, []).append((line_start, raw_summary))   # 뒤에서 앞으로 훑으니 덧붙이면 줄 시작 내림차순이다
    return None, seen_requests


def parse_resume_titles(window_bytes: bytes, wanted_agent_ids: frozenset[str]) -> dict[str, str]:
    """부모 transcript 창(bytes)에서 에이전트별 **마지막** 재개 요청의 요약을 판다(결정 TF8·TF10).

    결과 줄(RESUME_RESULT_LINE_MARKER 를 품은 줄)만 파일에서 뒤에 있는 것부터 본다 — 표지 없는 줄은 디코딩도 json 해석도 하지 않는다.
    결과 줄(tool_result 블록 정확히 1개, toolUseResult.resumedAgentId ∈ wanted)이 「tool_use_id → 재개된 agent_id」를 알려 주면, 그 줄
    앞에서만 SendMessage tool_use 를 찾아 그 id 의 input.summary 를 꺼낸다. 에이전트마다 처음 만난(파일에서 가장 늦은) 재개가 확정값이다 —
    그 요약이 문자열이 아니거나 비었거나 요청 줄이 창 밖이면 결과에 넣지 않는다(더 옛 재개의 요약으로 대체하지 않는다: 옛 작업 이름이 새
    작업을 가리키는 오늘의 결함을 다른 모양으로 되살리지 않는다). wanted 가 모두 확정되면 멈춘다. 요청을 못 찾는 결과 줄의 비용은 첫 미스 때
    만든 요청 색인으로 묶는다(_request_summary — 창 훑기 1회 + 결과 줄당 조회).

    계약 A: 요약은 _scrubbed_and_clipped 를 거친다(_resume_summary_title 의 한 호출 줄 — T25-206 산술). 계약 B: 예외를 던지지 않는다.
    """
    titles: dict[str, str] = {}
    unsettled = set(wanted_agent_ids)              # 마지막 재개를 아직 만나지 못한 에이전트
    if not unsettled:
        return titles
    request_index = None                           # 요청을 한 번 못 찾은 뒤에만 생긴다(_request_summary)
    for line_start, line_end in _lines_with_marker_backwards(window_bytes, RESUME_RESULT_LINE_MARKER, len(window_bytes)):
        payload = _json_object_or_none(window_bytes[line_start:line_end])
        resumed = _resumed_agent_of_result_line(payload) if payload is not None else None
        if resumed is None:
            continue
        request_id, agent_id = resumed
        if agent_id not in unsettled:
            continue
        unsettled.discard(agent_id)
        raw_summary, request_index = _request_summary(window_bytes, request_id, line_start, request_index)
        title = _resume_summary_title(raw_summary)
        if title is not None:
            titles[agent_id] = title
        if not unsettled:
            break
    return titles
