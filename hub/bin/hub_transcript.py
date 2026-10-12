"""hub_transcript.py — Claude Code transcript(JSONL) 꼬리에서 세션의 표시 정보
(모델·effort·마지막 프롬프트·마지막 턴의 API 오류)를 판다.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_transcript.py 대상).
`datetime.fromisoformat` 는 이미 받은 문자열을 파싱만 할 뿐 시계를 읽지 않는다(hub_usage.py 가
같은 ★순수 모듈에서 이미 쓰는 관례 — GOTCHA 1 참조).
Claude Code transcript(~/.claude/projects/<인코딩>/<session_id>.jsonl)는 우리가 소유하지 않는
외부 파일 형식이다 — 그 계약이 바뀌면 이 모듈 하나만 고치면 되도록 hub_session_facts.py("훅
이벤트 → 세션 사실"이라는 단일 입력원 계약)에 얹지 않고 분리했다(결정 MD1,
docs/prps/hub-tier1-clamp-fix-and-session-model.md). 파일 접근(stat·seek·읽기)은 전부
hub_collect.py 가 맡는다 — 이 모듈은 이미 읽힌 텍스트만 받는다.

**결정 PS1(docs/prps/hub-agent-runs-and-prompt-source.md)** — `last-prompt` 줄 파싱도 이
모듈에 얹는다(새 모듈을 만들지 않는다). 판단 기준은 "같은 외부 계약인가"다: `last-prompt` 는
이 모듈이 이미 읽고 있는 바로 그 128KiB 꼬리의 다른 줄일 뿐이다. 새 모듈로 빼면 같은 꼬리를
두 모듈이 각각 훑거나 군더더기 층이 생긴다.

**결정 RI1·RI13(docs/prps/hub-rate-limit-interruption.md)** — 같은 꼬리의 **마지막 메인
대화 줄**이 API 오류 줄인지도 이 모듈이 판다(`TranscriptTurnFailure`). 훅의 `error` 와
transcript 의 `error` 는 호스트의 같은 어휘라 `normalize_error_kind` 도 여기 둔다 —
hub_session_facts·hub_hook 이 모두 임포트할 수 있는 유일한 무순환 위치다.

**결정 TF1~TF4(docs/prps/hub-agent-title-and-excerpt-freshness.md)** — 발췌의 출처를 넓힌다.
호스트는 `last-prompt` 줄을 대화 기록이 32KiB 쌓일 때마다만 다시 적어, 방금 입력한 프롬프트가
파일에 나타나기까지 수십 초~수 분이 걸린다. 같은 꼬리 안의 **사람 프롬프트 줄**에서 호스트와 같은
규칙으로 유도한 값과 `last-prompt` 값 중 파일에서 더 뒤의 것이 발췌다 — 추가로 읽는 파일이 없다
(같은 128KiB 문자열). 호스트 규칙의 사본은 상수 주석에 출처를 적었다.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from hub_redact import redact_secret_tokens

# 128KiB. 활성 세션 12건 실측(§3.4) — EOF 로부터 마지막 assistant 줄까지의 최악 깊이가
# 103,742B 였다. 이 값의 1.26배이자, 꼬리 크기별 해결률(32KiB→8/12, 64KiB→9/12,
# 128KiB→12/12, 256KiB→12/12) 실측에서 전건을 해결하는 최소 2의 거듭제곱이다.
TRANSCRIPT_TAIL_BYTES = 131072

# 이 값은 실제 모델이 아니다(합성 응답 — 예: 사용자 프롬프트 없이 CLI 가 만든 턴). 실측
# 760개 transcript 꼬리 전수 조사에서 5건 관측됐다. 만나면 건너뛰고 더 앞줄을 계속 찾는다.
SYNTHETIC_MODEL_ID = "<synthetic>"

MODEL_ID_PREFIX = "claude-"
DATE_SUFFIX_LENGTH = 8   # YYYYMMDD — 구세대 모델 ID(예: claude-haiku-4-5-20251001)의 날짜 접미

_ASSISTANT_LINE_TYPE = "assistant"
_USER_LINE_TYPE = "user"
# 대화 줄 = type 이 이 둘 중 하나(RI1) — last-prompt 등 비대화 줄은 여기 없다.
_CONVERSATION_LINE_TYPES = (_ASSISTANT_LINE_TYPE, _USER_LINE_TYPE)

LAST_PROMPT_LINE_TYPE = "last-prompt"
# 400 — 호스트 실측 max 201(§1.4, 30/30 세션 전수)의 약 2배 방어선(결정 PS8). 호스트가
# 자르기를 멈추면 프롬프트 전문이 hub.html 에 인라인될 수 있어, 정상 데이터에서는 발동하지
# 않는 병리적 입력 방어선으로 서버가 다시 건다.
LAST_PROMPT_MAX_CHARS = 400
LAST_PROMPT_TRUNCATION_MARK = "…"

# 호스트(Claude Code 2.1.284) lastPrompt 규칙의 부분 사본(결정 TF2·TF3) — 번들의 Ztn·normalizeLastPrompt·l7t·xue 를
# 옮겼다. 호스트는 last-prompt 줄을 대화 기록이 32KiB 쌓일 때마다만 다시 적으므로(J_/2, J_=65536) 새 프롬프트가
# 파일에 나타나기까지 중앙 22.8초·p90 65초가 걸린다(§2.2). 이 사본은 그 사이를 사람 프롬프트 줄로 메운다. 호스트 규칙이
# 바뀌어 어긋나도 다음 재부착 때 호스트 값으로 되돌아온다(최악 = 이 사본이 없던 때의 지연).
HUMAN_PROMPT_ORIGIN_KIND = "human"
# 프롬프트 줄이 아닌 표지 — isMeta·isCompactSummary 는 호스트 Ztn 이 JS 진리값으로 거르는 것이고, isSidechain 은
# 서브에이전트 줄을 확실히 빼려는 이 사본의 방어(결정 TF2)다
_NON_PROMPT_LINE_FLAGS = ("isMeta", "isSidechain", "isCompactSummary")
# l7t — 태그로 시작하는 블록(자동주입·명령 출력)과 인터럽트 표식은 프롬프트가 아니다. JS 의 \w 는 ASCII 라 명시 클래스로 쓴다
HOST_PROMPT_SKIP_PATTERN = re.compile(r"\A(?:\s*<[a-z][A-Za-z0-9_-]*[\s>]|\[Request interrupted by user[^\]]*\])")
# 호스트가 다른 모양으로 바꿔 적는 블록(/cmd args · ! cmd) — 내장 명령 목록을 모르므로 흉내 내지 않고 포기한다
HOST_PROMPT_GIVE_UP_MARKERS = ("<command-name>", "<bash-input>")
# xue — 붙여 넣은 글을 감싼 표지를 벗긴다. 표지 안쪽 줄바꿈(여는 표지 뒤·닫는 표지 앞)과 바깥쪽 줄바꿈(여는 표지 앞·닫는
# 표지 뒤 각 최대 2개)까지 함께 벗기고, 남은 조각은 구분자 없이 이어 붙는다(호스트 kht·xue). 바깥쪽을 남기면 글 한가운데
# 붙여 넣은 줄에서 그 줄바꿈이 공백으로 남아 호스트 값과 어긋난다 — 설계 때 14일 재생의 불일치 1/453 이 이 차이였다
PASTED_CONTENT_OPEN_PATTERN = re.compile(r'\n{0,2}<pasted_content id="[0-9a-f]{4}">\n')
PASTED_CONTENT_CLOSE_PATTERN = re.compile(r'\n?</pasted_content id="[0-9a-f]{4}">\n{0,2}')
# normalizeLastPrompt 의 절단 — 이 값에서 자르고 말줄임표를 붙인다(호스트 실측 max 201 = 200 + '…')
HOST_LAST_PROMPT_MAX_CHARS = 200
# 유도 경로에서 스크럽(redact_secret_tokens)에 넘기는 글의 최대 길이 — 발췌 상한(HOST_LAST_PROMPT_MAX_CHARS)의 10배. 이유:
# 사람 줄은 꼬리 128KiB 까지 길 수 있는데(붙여 넣기) 스크럽의 JWT 대안(`eyJ…` 뒤에 점 둘)은 점 없이 `eyJ` 가 반복되는 긴 글에서
# 길이의 제곱에 비례해 느려져 128KiB 에 8초가 걸린다(검수 실측). 그 줄이 꼬리 창에 있는 동안 요청 시 동기 수집이 매번 수 초
# 걸리므로 호출자가 입력 길이를 제한한다 — hub_redact 는 공유 보안 모듈이라 정규식은 바꾸지 않는다. 이 길이에서는 최악도 수
# ms 다. 화면에는 앞 200자만 나가므로 「스크럽이 절단보다 먼저」(결정 TF4)의 뜻은 그대로다. 창 경계: 창의 끝은 시크릿을 한가운데서
# 가를 수 있다 — 잘린 조각은 패턴 최소 길이에 못 미쳐 마스킹되지 않는다(고정 길이 패턴은 한 글자 모자란 조각까지 그대로 남는다).
# 보통은 결과가 길어 창 끝이 화면(앞 200자) 밖이지만, 앞부분의 시크릿이 마스킹으로 크게 접히면(예: 개인키 블록) 창 끝이 화면에
# 나온다 — 그래서 창이 잘렸고 결과가 짧으면 경계 낱말을 버린다(_without_boundary_fragment · BOUNDARY_FRAGMENT_MAX_CHARS, 검수
# LOW-A). 남는 잔존 위험 둘 — (1) 따옴표로 감싼 여러 낱말 값(닫는 따옴표가 창 밖인 password="a b c" 꼴)은 끝 낱말 하나만 버려져 앞
# 낱말이 보일 수 있다 (2) 서명이 창 밖에 잘린 긴 JWT(`eyJ…` 뒤 점 0~2개)는 세 조각 패턴을 채우지 못해 마스킹되지 않으므로 머리(header +
# payload 앞 200자)가 보일 수 있다 — 서명이 없어 인증에 쓸 수 없는 조각이고, `last-prompt` 경로는 호스트가 200자에서 자른 값에 같은 이유로
# 이미 같은 머리를 보인다(그 값이 곧 이 값을 덮으므로 여기서만 따로 마스킹하지 않는다). README 「프라이버시 고지」가 같은 숫자를 알리며
# T25-260 이 동치를 본다
DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS = 2000
# 스크럽 창 끝에서 잘려 마스킹되지 않는 고정 길이 패턴 조각의 최대 길이 — 고정 길이 패턴 중 가장 긴 것(GitHub 토큰 `ghp_` + 본문 36자,
# hub_redact)이 한 글자 모자라 잘린 39자 + 여유 1. 스크럽 결과가 화면(HOST_LAST_PROMPT_MAX_CHARS) + 이 길이보다 짧으면 창 끝 조각이
# 화면의 앞 200자에 닿을 수 있다 — 결과가 딱 200자를 넘어도 조각이 걸리는 띠가 있어 「결과 < 200」 이 아니라 이 여유를 더한 값이 기준이다.
# 길이가 정해지지 않은 패턴(JWT 등)의 잘린 조각은 이 값이 덮지 않는다(위 잔존 위험 2). hub_redact 에 고정·최소 길이가 40자를 넘는 패턴을
# 더하면 이 값도 올린다
BOUNDARY_FRAGMENT_MAX_CHARS = 40

# 호스트 API 오류 종류(StopFailure 훅의 error · transcript 줄의 error)의 형태 검사(결정
# RI7) — 실측(§1.2·§1.3): rate_limit·server_error·invalid_request·authentication_failed 등
# 소문자 snake_case. 호스트가 종류를 늘려도 형태만 맞으면 그대로 통과시킨다 — enum 사본을
# 두지 않는다.
ERROR_KIND_PATTERN = re.compile(r"\A[a-z_]{1,32}\Z")
UNKNOWN_ERROR_KIND = "unknown"

MILLISECONDS_PER_SECOND = 1000
# 8일 = 가장 긴 한도 창(7일) + 하루 — hub_usage.RATE_LIMIT_MAX_HORIZON_MS 와 같은 근거의
# 지역 사본이다(결정 RI13 — hub_usage 를 임포트하지 않는다, 작은 사본 선례: _clip_to_length).
TURN_FAILURE_RESET_MAX_HORIZON_MS = 8 * 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class SessionModel:
    """세션이 마지막으로 사용한 모델과 노력 수준. 화면 표시용 투영이다."""

    model_label: str        # 정규화된 표시명. 예: "Opus 5", "Haiku 4.5". 정규화 실패 시 원문 ID
    raw_model_id: str       # 원문. 예: "claude-opus-5". 툴팁·디버깅용
    effort: str | None      # 예: "xhigh". transcript 에 없으면 None


@dataclass(frozen=True)
class TranscriptTurnFailure:
    """transcript 의 마지막 메인 대화 줄이 API 오류 줄일 때의 구조 필드(결정 RI1·RI5·RI7).
    message.content 는 읽지 않는다."""

    error_kind: str            # normalize_error_kind 통과값
    failed_at_ms: int          # 그 줄의 timestamp(ISO 8601, UTC "Z") → epoch ms
    resets_at_ms: int | None   # quotaLimits.resetsAt(초) → ms. 부재·검증 실패면 None


@dataclass(frozen=True)
class SessionTail:
    """세션 transcript 꼬리에서 판 표시 정보 묶음. 셋 다 정당하게 부재할 수 있다(결정 PS1·RI1)."""

    model: SessionModel | None
    # 꼬리에서 파일상 더 뒤에 있는 것 — 사람 프롬프트 줄에서 호스트 규칙으로 유도한 값 또는 last-prompt 줄의 값(결정 TF1).
    # 어느 쪽이든 스크럽 + LAST_PROMPT_MAX_CHARS 를 거친 값이다(결정 PS9·TF4)
    last_prompt: str | None
    turn_failure: TranscriptTurnFailure | None = None   # RI1. 기본값 — 기존 생성 지점 무해
    # 꼬리에서 가장 뒤에 있는 **사람 입력 줄**의 시각(epoch ms) — 시각만 읽고 본문은 읽지 않는다. 작업 경계·세션 줄
    # 시작 시각의 근거다(훅의 UserPromptSubmit 은 알림·서브에이전트 보고에도 발화해 경계를 밀기 때문). 꼬리 밖(긴 자율
    # 작업)이거나 시각이 깨졌으면 None — 그때 소비자는 프롬프트를 경계에 쓰지 않는다(페일오픈, 결정 RL4). 기본값 있음.
    last_human_prompt_at_ms: int | None = None


def _is_date_suffix_token(token: str) -> bool:
    """YYYYMMDD 형태(8자리 전부 숫자)인가 — 구세대 모델 ID 의 날짜 접미를 가려낸다."""
    return len(token) == DATE_SUFFIX_LENGTH and token.isdigit()


def normalize_model_name(raw_model_id: str) -> str | None:
    """모델 ID 를 표시명으로 정규화한다. 모델이 아니면(<synthetic> 등) None.

    하드코딩 표 대신 규칙(결정 MD5)을 쓴다 — 표는 새 모델이 나오면 조용히 깨진다. 규칙:
    1. <synthetic> 이거나 "claude-" 접두가 없으면 모델이 아니다.
    2. 접두를 벗긴 나머지가 비어 있으면(순수 접두만, "claude-") 모델로 보지 않는다.
    3. 첫 토큰이 순수 알파벳이 아니면(예: 구세대 "claude-3-5-sonnet-20241022") 정규화를
       포기하고 원문 ID 를 그대로 돌려준다 — 잘못 줄이는 것보다 못생겨도 정직한 편이 낫다.
    4. 나머지 토큰 중 8자리 전부 숫자(YYYYMMDD)는 버린다.
    5. 남은 숫자 토큰을 "."으로 이어 "{Family} {version}"을 만든다(버전 없으면 "{Family}").

    미지의 미래 모델이 이 관례를 따르면 자동으로 잘 나온다(claude-opus-6 → "Opus 6").
    """
    if raw_model_id == SYNTHETIC_MODEL_ID or not raw_model_id.startswith(MODEL_ID_PREFIX):
        return None
    remainder = raw_model_id[len(MODEL_ID_PREFIX):]
    if not remainder:
        return None
    tokens = remainder.split("-")
    if not tokens[0].isalpha():
        return raw_model_id
    family = tokens[0].capitalize()
    version_tokens = [token for token in tokens[1:] if not _is_date_suffix_token(token)]
    if not version_tokens:
        return family
    return f"{family} {'.'.join(version_tokens)}"


def _extract_model_and_effort(payload: dict) -> tuple[str, str | None] | None:
    """assistant 줄 payload 에서 (원문 모델 ID, effort) 를 함께 뽑는다. 조건 불충족이면 None.

    model 과 effort 를 반드시 같은 줄(같은 payload)에서 함께 뽑는다(GOTCHA 5) — 서로 다른
    줄에서 뽑으면 모델 전환 직후 잘못된 조합이 나온다. effort 는 message 안이 아니라 줄
    최상위에 있다(GOTCHA 4) — message.effort 를 읽으면 전 세션이 조용히 None 이 된다.
    """
    if payload.get("type") != _ASSISTANT_LINE_TYPE:
        return None
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    raw_model_id = message.get("model")
    if not isinstance(raw_model_id, str) or not raw_model_id:
        return None
    effort = payload.get("effort")
    return raw_model_id, effort if isinstance(effort, str) else None


def _clip_to_length(value: str, max_chars: int) -> str:
    """value 가 max_chars 를 넘으면 잘라 말줄임표를 붙인다(hub_workflow._clip_to_length 와 동형)."""
    if len(value) <= max_chars:
        return value
    keep_length = max_chars - len(LAST_PROMPT_TRUNCATION_MARK)
    return value[:keep_length] + LAST_PROMPT_TRUNCATION_MARK


def _scrubbed_and_clipped_last_prompt(value: str) -> str:
    """last_prompt 가 거치는 경로 — 스크럽 후 LAST_PROMPT_MAX_CHARS 로 자른다(결정 PS9).

    순서 고정: 스크럽 → 자르기. 자르기부터 하면 절단 경계에 걸린 시크릿이 패턴 불일치로
    살아남아 접두사가 샌다. 호스트가 이미 201자로 잘라 둔 문자열을 받는 처지(WF7 과 동형)라
    그 절단 경계에 걸린 시크릿은 우리가 자르기 전에 스크럽해도 살아남을 수 있다는 잔존
    위험을 안는다.
    """
    return _clip_to_length(redact_secret_tokens(value), LAST_PROMPT_MAX_CHARS)


def _is_human_prompt_line(payload: dict) -> bool:
    """사람이 입력한 프롬프트 줄인가(결정 TF2) — 호스트가 붙인 표지만 믿는다: type=user · origin.kind=human ·
    메타·서브에이전트·압축 요약 줄이 아님. origin 이 없는 줄(구버전 호스트·SDK 세션)은 판정하지 않는다 — 그런 세션은
    last-prompt 경로만 쓴다. 이 표지 덕에 서브에이전트 보고 전달(task-notification)·조정자 메시지·도구 결과가 섞이지 않는다."""
    if payload.get("type") != _USER_LINE_TYPE:
        return False
    origin = payload.get("origin")
    if not isinstance(origin, dict) or origin.get("kind") != HUMAN_PROMPT_ORIGIN_KIND:
        return False
    return not any(payload.get(flag) for flag in _NON_PROMPT_LINE_FLAGS)


def _text_blocks_of_user_line(payload: dict) -> list[str]:
    """user 줄 message.content 의 비어 있지 않은 텍스트 블록들(문자열 content 는 블록 1개). tool_result 블록이 하나라도
    있으면 프롬프트 줄이 아니므로 빈 목록이다(결정 TF2) — content 가 이 모양이 아니어도 빈 목록이다."""
    message = payload.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    blocks = [block for block in content if isinstance(block, dict)]
    if any(block.get("type") == "tool_result" for block in blocks):
        return []
    return [
        block["text"] for block in blocks
        if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"]
    ]


def _first_prompt_block(text_blocks: list[str]) -> str | None:
    """텍스트 블록을 순서대로 호스트 규칙에 건다(결정 TF3): 붙여넣기 감싸기를 벗기고 → 명령·bash 표지가 있으면 그 줄
    전체를 포기(None) → 태그·인터럽트 표식으로 시작하면 그 블록만 건너뛰고 → 처음 남는 비어 있지 않은 블록이 원문이다."""
    for block in text_blocks:
        if any(marker in block for marker in HOST_PROMPT_GIVE_UP_MARKERS):
            return None
        unwrapped = PASTED_CONTENT_CLOSE_PATTERN.sub("", PASTED_CONTENT_OPEN_PATTERN.sub("", block))
        if HOST_PROMPT_SKIP_PATTERN.match(unwrapped):
            continue
        if unwrapped.strip():
            return unwrapped
    return None


def _human_prompt_text(payload: dict) -> str | None:
    """사람이 입력한 프롬프트 줄(결정 TF2)이면 호스트 규칙(TF3)으로 고른 블록 원문(스크럽·절단 전), 아니면 None.
    None 은 「이 줄에서는 발췌를 유도하지 못한다」 — 프롬프트 줄이 아니거나, 명령·bash 턴이거나, 텍스트가 없다."""
    if not _is_human_prompt_line(payload):
        return None
    return _first_prompt_block(_text_blocks_of_user_line(payload))


def _cut_like_host(value: str) -> str:
    """normalizeLastPrompt 의 절단 — HOST_LAST_PROMPT_MAX_CHARS 를 넘으면 앞 그만큼(끝 공백 제거)에 말줄임표를 붙인다."""
    if len(value) <= HOST_LAST_PROMPT_MAX_CHARS:
        return value
    return value[:HOST_LAST_PROMPT_MAX_CHARS].strip() + LAST_PROMPT_TRUNCATION_MARK


def _without_boundary_fragment(scrubbed: str) -> str | None:
    """잘린 스크럽 창의 끝 낱말 — 경계에 걸려 잘린 시크릿 조각일 수 있다 — 을 화면에 닿을 때만 버린다(검수 LOW-A).

    스크럽 결과가 화면(앞 HOST_LAST_PROMPT_MAX_CHARS 자) + BOUNDARY_FRAGMENT_MAX_CHARS 이상이면 조각이 화면 밖이라 그대로
    돌려준다. 그보다 짧으면 마지막 낱말을 버린다. 낱말이 하나뿐이면 결과 전체가 경계 조각일 수 있어 가려낼 수 없으므로
    None — 유도를 포기하고 더 앞 줄(옛 last-prompt 값)로 물러난다. 화면에 잠깐 덜 보이는 편이 시크릿 조각을 싣는 것보다
    낫고, 호스트가 다음에 적는 last-prompt 값이 곧 바로잡는다.
    """
    if len(scrubbed) >= HOST_LAST_PROMPT_MAX_CHARS + BOUNDARY_FRAGMENT_MAX_CHARS:
        return scrubbed
    text_and_boundary_word = scrubbed.rsplit(None, 1)
    if len(text_and_boundary_word) < 2:
        return None
    return text_and_boundary_word[0]


def _derived_last_prompt(raw_text: str) -> str | None:
    """유도 경로의 정규화(결정 TF4) — 줄바꿈→공백·strip → 앞 DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS 자로 제한 → 스크럽 →
    (창이 잘렸으면) 경계 낱말 처리 → 호스트식 200자 절단 → 400자 최종 관문. 경계 조각을 가릴 수 없으면 None(유도 포기).

    스크럽이 절단보다 먼저다: 절단부터 하면 경계에 걸린 시크릿이 패턴 불일치로 살아남아 접두사가 샌다. 호스트가 이미
    잘라 둔 값을 받는 last-prompt 경로가 안는 그 잔존 위험(200자 경계)이 여기서는 없다 — 화면에 나가는 앞 200자는 항상
    스크럽을 거친다. 입력을 먼저 제한하는 이유와 그 창 경계의 잔존 위험은 상수 주석에 있다. 호스트식 절단을 흉내 내는
    이유 둘 — 나중에 오는 호스트 값과 같아 화면이 깜박이지 않고, hub.html 에 실리는 프롬프트 양이 오늘과 같다(400자로
    늘리지 않는다).
    """
    flattened = raw_text.replace("\n", " ").strip()
    scrubbed = redact_secret_tokens(flattened[:DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS])
    if len(flattened) > DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS:
        without_fragment = _without_boundary_fragment(scrubbed)
        if without_fragment is None:
            return None
        scrubbed = without_fragment
    return _clip_to_length(_cut_like_host(scrubbed), LAST_PROMPT_MAX_CHARS)


def _last_prompt_candidate(payload: dict) -> tuple[bool, str | None]:
    """이 줄이 발췌를 확정하는가(결정 TF1)와 그 값. last-prompt 줄은 항상 확정한다 — lastPrompt 가 문자열이 아니면 값은
    None 이고 더 앞 줄로 넘어가지 않는다(가장 뒤의 것이 권위 있는 값). 유도 가능한 사람 프롬프트 줄도 확정한다. 유도를
    포기한 줄(명령·bash 턴, 텍스트 없음, 창 끝 조각을 가릴 수 없는 줄)과 그 밖의 줄은 확정하지 않아 스캔이 더 앞 줄로
    계속된다."""
    if payload.get("type") == LAST_PROMPT_LINE_TYPE:
        raw_last_prompt = payload.get("lastPrompt")
        if isinstance(raw_last_prompt, str):
            return True, _scrubbed_and_clipped_last_prompt(raw_last_prompt)
        return True, None
    human_prompt_text = _human_prompt_text(payload)
    if human_prompt_text is None:
        return False, None
    derived = _derived_last_prompt(human_prompt_text)
    return derived is not None, derived


def normalize_error_kind(value: object) -> str:
    """호스트 API 오류 종류(StopFailure 훅의 error · transcript 줄의 error)를 닫힌 형태로
    만든다. 문자열이 아니거나 ERROR_KIND_PATTERN 을 벗어나면 "unknown"."""
    if isinstance(value, str) and ERROR_KIND_PATTERN.match(value):
        return value
    return UNKNOWN_ERROR_KIND


def epoch_ms_from_iso8601(timestamp: object) -> int | None:
    """ISO 8601(호스트 UTC "Z" 포함) 문자열 → epoch ms. 문자열이 아니거나 파싱에 실패하면
    None. `datetime.fromisoformat` 은 3.11 부터만 트레일링 "Z" 를 받아들인다 — 이 저장소의
    최소 지원 버전 3.10(hub/install.sh·hub/README.md 「요구사항」)에서는 "Z" 가 있으면
    ValueError 를 던져 폴백 검출·초기화 시각이 조용히 꺼진다(검수 1회차 HIGH, 실측:
    /usr/bin/python3 3.9.6). 파싱 전에 트레일링 "Z" 를 "+00:00" 으로 바꿔 최소 지원 버전을
    올리지 않고 고친다. 타임존이 없는 문자열은 UTC 로 간주한다(hub_usage.
    _valid_usage_api_resets_at_ms 와 같은 관례) — 로컬 타임존 환경변수에 기대지 않아야
    ★순수 계약이 유지된다."""
    if not isinstance(timestamp, str):
        return None
    normalized_timestamp = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        parsed = datetime.fromisoformat(normalized_timestamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * MILLISECONDS_PER_SECOND)


def _resets_at_ms_from_quota_limits(quota_limits: object, failed_at_ms: int) -> int | None:
    """quotaLimits.resetsAt(초 단위 epoch) → ms(결정 RI5). 엄격 int(bool 배제) + 지평선
    검사(hub_usage.RATE_LIMIT_MAX_HORIZON_MS 와 같은 근거 — 단위 혼동·과거 값을 함께 잡는다)를
    통과하지 못하면 None. 한도 종류(rateLimitType)는 싣지 않는다(YAGNI, RI5)."""
    if not isinstance(quota_limits, dict):
        return None
    resets_at = quota_limits.get("resetsAt")
    if not isinstance(resets_at, int) or isinstance(resets_at, bool):
        return None
    resets_at_ms = resets_at * MILLISECONDS_PER_SECOND
    if not (failed_at_ms < resets_at_ms <= failed_at_ms + TURN_FAILURE_RESET_MAX_HORIZON_MS):
        return None
    return resets_at_ms


def _is_conversation_line(payload: dict) -> bool:
    """대화 줄인가 — type ∈ {user, assistant} 이고 isSidechain·isMeta 가 True 가 아니다(RI1).
    last-prompt·queue-operation 등 비대화 줄, 서브에이전트(sidechain) 줄, 메타 줄은 전부
    제외된다 — "마지막 메인 대화 줄"의 정의 그 자체다."""
    return (
        payload.get("type") in _CONVERSATION_LINE_TYPES
        and payload.get("isSidechain") is not True
        and payload.get("isMeta") is not True
    )


def _turn_failure_from_line(payload: dict) -> TranscriptTurnFailure | None:
    """마지막 메인 대화 줄이 API 오류 줄이면 구조 필드를 뽑는다(RI1·RI7). message.content 는
    읽지 않는다. error 가 문자열이 아니거나 timestamp 가 깨지면(호스트 실측 194/194 줄의
    형태를 벗어난다) 전체를 None 으로 접는다 — 이 모듈이 이미 쓰는 관례
    (`_extract_model_and_effort` 의 raw_model_id 타입 검사)와 같다. 형태는 맞지만 어휘를
    벗어난 error(예: 공백·대문자 포함)는 normalize_error_kind 가 "unknown" 으로 접을 뿐
    줄 자체를 버리지 않는다 — 둘의 차이가 구조적 이상(None)과 어휘적 이상("unknown")을 가른다.
    """
    if payload.get("type") != _ASSISTANT_LINE_TYPE or payload.get("isApiErrorMessage") is not True:
        return None
    error_value = payload.get("error")
    if not isinstance(error_value, str):
        return None
    failed_at_ms = epoch_ms_from_iso8601(payload.get("timestamp"))
    if failed_at_ms is None:
        return None
    return TranscriptTurnFailure(
        error_kind=normalize_error_kind(error_value),
        failed_at_ms=failed_at_ms,
        resets_at_ms=_resets_at_ms_from_quota_limits(payload.get("quotaLimits"), failed_at_ms),
    )


def parse_session_tail(tail_text: str) -> SessionTail:
    """꼬리에서 (모델·effort)·마지막 프롬프트·**마지막 메인 대화 줄**의 결과를 **한 번의
    역방향 스캔**으로 판다(결정 PS2·RI1).

    셋 다 "마지막 값"이므로 뒤에서 앞으로 훑고, 셋 다 찾으면 즉시 멈춘다(GOTCHA 4). 꼬리의
    첫 줄은 파일 중간에서 잘렸을 수 있으나 JSON 파싱 실패로 자연히 탈락한다(MD6 와 같다).
    발췌(last_prompt)는 뒤에서 먼저 만나는 **확정 줄**의 값이다(결정 TF1, `_last_prompt_candidate`) —
    `last-prompt` 줄 또는 유도 가능한 사람 프롬프트 줄. 호스트가 `last-prompt` 를 32KiB 마다만 다시
    적으므로 사람 줄이 파일에서 더 뒤에 있으면 그 줄이 더 새롭다. 여러 개의 `last-prompt` 줄이 있으면
    (뒤에서부터 훑으므로) 가장 나중에 나온 것이 이긴다 — 그 줄의 `lastPrompt` 가 문자열이 아니면 더
    앞의 줄로 넘어가지 않고 그 자리에서 None 으로 확정한다(가장 최근 것이 권위 있는 값이라는 원칙,
    오래된 값으로 대체하지 않는다).

    대화 줄 = type ∈ {user, assistant} 이고 isSidechain·isMeta 가 True 가 아닌 줄(RI1). 그
    줄이 isApiErrorMessage 인 assistant 줄이면 turn_failure 를 채운다(timestamp 가 깨졌으면
    None). 대화 줄 판독은 `<synthetic>` 모델 건너뛰기와 독립이다(GOTCHA 5) — 오류 줄의
    `message.model` 이 `<synthetic>` 이라 모델 추출은 이미 그 줄을 건너뛰지만, 대화 줄
    판정은 `type`·`isSidechain`·`isMeta` 만 보므로 서로 영향을 주지 않는다.

    `last_human_prompt_at_ms` 는 뒤에서 처음 만나는 사람 입력 줄(`_is_human_prompt_line` 재사용)의 timestamp 다.
    알림·peer·메타 줄은 그 판정에서 이미 걸러진다. 꼬리에 사람 줄이 없거나 그 줄의 timestamp 가 깨졌으면 None 이며,
    꼬리 한계(TRANSCRIPT_TAIL_BYTES)보다 긴 자율 작업에서는 None 이 흔할 수 있다.
    """
    model: SessionModel | None = None
    last_prompt: str | None = None
    turn_failure: TranscriptTurnFailure | None = None
    last_human_prompt_at_ms: int | None = None
    model_found = False
    last_prompt_found = False
    conversation_checked = False
    human_prompt_found = False
    for line in reversed(tail_text.splitlines()):
        if model_found and last_prompt_found and conversation_checked and human_prompt_found:
            break
        stripped_line = line.strip()
        if not stripped_line:
            continue
        try:
            payload = json.loads(stripped_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        if not model_found:
            extracted = _extract_model_and_effort(payload)
            if extracted is not None:
                raw_model_id, effort = extracted
                model_label = normalize_model_name(raw_model_id)
                if model_label is not None:
                    model = SessionModel(model_label=model_label, raw_model_id=raw_model_id, effort=effort)
                    model_found = True

        if not last_prompt_found:
            last_prompt_found, last_prompt = _last_prompt_candidate(payload)

        if not conversation_checked and _is_conversation_line(payload):
            turn_failure = _turn_failure_from_line(payload)
            conversation_checked = True

        if not human_prompt_found and _is_human_prompt_line(payload):
            # 시각이 깨진 줄도 「찾았다」로 확정한다 — 더 오래된 사람 줄로 물러나면 경계가 실제보다 이르게 잡힌다.
            last_human_prompt_at_ms = epoch_ms_from_iso8601(payload.get("timestamp"))
            human_prompt_found = True

    return SessionTail(
        model=model, last_prompt=last_prompt, turn_failure=turn_failure,
        last_human_prompt_at_ms=last_human_prompt_at_ms,
    )


def parse_session_model_from_tail(tail_text: str) -> SessionModel | None:
    """(유지) parse_session_tail(tail_text).model 과 같다 — 기존 테스트 표의 앵커(결정 PS2).

    <synthetic> 처럼 모델로 인정되지 않는 값을 만나면 건너뛰고 더 앞줄을 계속 찾는 동작(E11)은
    parse_session_tail 안으로 그대로 옮겨졌다.
    """
    return parse_session_tail(tail_text).model
