"""hub_usage_fetch.py — 사용량 API I/O 전용(R1, docs/prps/hub-card-interactions-and-usage.md).

OAuth accessToken 이 존재하는 **유일한 파일**이다 — "누가 토큰을 볼 수 있는가"를 이 파일
하나의 질문으로 만들기 위해 격리했다.

불변식 A-SEC(양보 불가): accessToken 은 이 모듈의 **지역 변수로만** 존재한다. 로그·stderr·
server.log·rate_limits.json·last_usage_api_error.json·hub.html·warnings 그 어디에도
나타나지 않는다. `failure_reason_message()` 가 이 고정 어휘(및 그 밖의 미등록 값에 대한
고정 기본 문구)를 사람이 읽는 문장으로 바꿔 `record_usage_api_failure` 의 payload 에 함께
싣는다 — 이 경로도 예외 객체나 URL·헤더 파편을 끌어오지 않는다. 예외 객체를 문자열로 바꿔
반환값에 섞는 일은 절대 하지 않는다(예외 메시지에 URL·헤더 파편이 섞여 나올 여지를 원천
차단한다). Keychain 호출은 인자를 리스트로 넘기고 셸을 거치지 않는다(T25-61 이 검사한다).
"""

import json
import ssl
import subprocess
import urllib.error
import urllib.request
from typing import Literal

import hub_usage

USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"   # SP3 생략 개정 — 1차 대응표(커뮤니티 알려진 엔드포인트)
KEYCHAIN_SERVICE_NAME = "Claude Code-credentials"
FETCH_TIMEOUT_SECONDS = 10
KEYCHAIN_TIMEOUT_SECONDS = 5
ANTHROPIC_BETA_HEADER_VALUE = "oauth-2025-04-20"

# H11(docs/prps/shell-hardening.md §7-2·§15 남은 질문 3) — 이 값은 실제 응답을 재서 정하지
# 않았다: 크기 하나를 재려면 사용자의 OAuth 토큰으로 실제 API 를 호출해야 하는데, 그 목적을
# 위해 자격증명을 네트워크로 보내는 것은 정당화되지 않는다(구현 결정 A). 대신 파서가 실제로
# 읽는 필드 구조에서 유도한다 — `parse_usage_api_response` 가 쓰는 것은 최상위 `five_hour`·
# `seven_day` 두 객체뿐이고 각각 `utilization`(숫자)·`resets_at`(ISO 8601 문자열) 두 필드라
# 알려진 스키마는 수백 바이트 안쪽이다. `SERVER_LOG_MAX_BYTES`(256*1024, hub_server.py)보다
# 작게 잡는다 — 그 값은 신뢰하는 로컬 파일의 상한이고, 이 값은 신뢰하지 않는 원격 응답의
# 상한이라 더 좁게 가둬야 한다. 64KiB 는 알려진 스키마의 수백 배 여유를 주면서도 캡티브
# 포털의 HTML 로그인 페이지 같은 "명백히 병리적" 응답을 가른다.
USAGE_API_MAX_RESPONSE_BYTES = 64 * 1024
# response_keys 자기 진단 목록(§7-2 둘째 갈래)의 항목 수 상한 — 알려진 스키마는 리프 4개
# (five_hour.utilization·five_hour.resets_at·seven_day.utilization·seven_day.resets_at)뿐이라
# 100 은 스키마가 크게 늘어도 남는 여유다. 넘으면 잘렸다는 표지를 마지막에 남긴다(조용히
# 자르면 자기 진단 창구가 거짓말을 한다).
USAGE_API_MAX_RESPONSE_KEY_ENTRIES = 100
# 구현 2회차(검수 접지 MEDIUM) — 항목 수 상한만으로는 총 바이트를 막지 못한다:
# describe_json_key_structure 의 각 항목은 조상 키 경로 전체를 문자열로 담으므로 총 바이트는
# 항목 수 × 경로 길이로 증폭된다(검수자 실측 — 깊이 60·키 길이 1000 의 중첩 체인 바닥에 리프
# 100개를 둔 61,440바이트 본문이 last_usage_api_error.json 에 6,007,530바이트를 썼다. 본문
# 자체는 USAGE_API_MAX_RESPONSE_BYTES 이내였고 항목 수도 상한과 정확히 같았다 — 개수 상한이
# 이 증폭을 원리적으로 못 막는다는 뜻). 알려진 스키마의 response_keys 총 바이트는 리프 4개 ×
# 경로 30자 안팎이라 200바이트를 넘지 않는다 — 8KiB 는 그 수십 배 여유를 주면서 위 재현 같은
# 병리적 증폭을 자른다. USAGE_API_MAX_RESPONSE_BYTES(64KiB)보다 작게 잡은 이유도 같다 — 이
# 목록은 원 응답에서 유도된 2차 산출물이라 원 응답보다 더 좁게 가둬야 한다.
USAGE_API_MAX_RESPONSE_KEY_BYTES = 8 * 1024

_HTTP_STATUS_UNAUTHORIZED = 401
_HTTP_STATUS_FORBIDDEN = 403
_HTTP_STATUS_RATE_LIMITED = 429
_HTTP_STATUS_REDIRECT_RANGE_START = 300
_HTTP_STATUS_REDIRECT_RANGE_END = 400   # 배타적 상한 — 400(Bad Request)부터는 리다이렉트가 아니다

FailureReason = Literal[
    "credential_unavailable",   # Keychain 항목 없음·잠김·명령 부재·플랫폼 미지원
    "credential_unparsable",    # 항목은 읽었으나 토큰 필드가 없다
    "http_unauthorized",        # 401/403 — 토큰 만료. 재로그인 필요
    "http_rate_limited",        # 429 — 즉시 백오프 상한
    "http_error",                # 그 외 4xx/5xx
    "network_error",             # 타임아웃·DNS·연결 실패
    "schema_mismatch",           # 200 인데 우리가 아는 모양이 아니다
    "redirect_blocked",          # H10 — 3xx 를 받았고 따라가지 않았다(§5-3)
    "tls_verify_failed",         # H13 — 인증서 검증 실패(§9-8)
    "response_too_large",       # H11 — 응답 본문이 상한을 넘었다(§7-2)
]

FAILURE_REASON_MESSAGES: dict[str, str] = {
    "credential_unavailable": "Keychain 에서 자격증명을 읽을 수 없습니다",
    "credential_unparsable": "Keychain 항목에서 토큰 필드를 찾을 수 없습니다",
    "http_unauthorized": "인증이 만료됐습니다 — 재로그인이 필요합니다",
    "http_rate_limited": "요청이 제한됐습니다(429)",
    "http_error": "사용량 API 가 오류를 반환했습니다",
    "network_error": "사용량 API 에 연결할 수 없습니다",
    "schema_mismatch": "사용량 API 응답 형식이 예상과 다릅니다",
    "redirect_blocked": "사용량 API 가 리다이렉트를 요청해 응답을 거부했습니다",
    "tls_verify_failed": "사용량 API 서버의 인증서를 확인할 수 없습니다",
    "response_too_large": "사용량 API 응답이 너무 커서 거부했습니다",
}
# N1(§7-1·§8-3) — 위 표에 없는 사유(예: hub_server.py 의 "internal_error", FailureReason 밖의
# 값)를 위한 기본 문구. failure_reason_message 를 총함수로 만든다 — 모르는 값에 KeyError 를
# 내면 그 자체가 관측 가능성을 해치는 새 실패 형태가 된다.
_UNKNOWN_FAILURE_REASON_MESSAGE = "사용량 API 호출에 실패했습니다"


def failure_reason_message(reason: str) -> str:
    """고정 어휘 사유를 사람이 읽는 문장으로 바꾼다 — `FAILURE_REASON_MESSAGES` 의 유일한
    소비자(N1). `record_usage_api_failure` 의 payload 에 원어휘 키와 함께 실려
    `/hub status` 의 `usage_api_last_failure` 소비자가 문장까지 보게 한다."""
    return FAILURE_REASON_MESSAGES.get(reason, _UNKNOWN_FAILURE_REASON_MESSAGE)


def _read_oauth_access_token_with_reason() -> tuple[str | None, FailureReason | None]:
    """Keychain 에서 토큰을 읽고 실패 사유까지 함께 돌려준다(내부 전용).

    `read_oauth_access_token()`(공개 인터페이스, 사유를 버린다)과 `fetch_rate_limit_capture()`
    가 이 함수를 공유한다 — 후자는 `credential_unavailable`(Keychain 접근 자체 실패)과
    `credential_unparsable`(접근은 됐으나 토큰 필드가 없음)을 구분해야 한다.
    """
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE_NAME, "-w"],
            capture_output=True, text=True, timeout=KEYCHAIN_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "credential_unavailable"
    if result.returncode != 0:
        return None, "credential_unavailable"
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None, "credential_unparsable"
    claude_oauth = payload.get("claudeAiOauth") if isinstance(payload, dict) else None
    token = claude_oauth.get("accessToken") if isinstance(claude_oauth, dict) else None
    if isinstance(token, str) and token:
        return token, None
    return None, "credential_unparsable"


def read_oauth_access_token() -> str | None:
    """macOS Keychain 에서 Claude Code OAuth accessToken 을 읽는다. 실패하면 None.

    반환값은 절대 로그·파일·hub.html 에 남기지 않는다(불변식 A-SEC).
    """
    token, _reason = _read_oauth_access_token_with_reason()
    return token


def _classify_http_error(status_code: int) -> FailureReason:
    """HTTP 응답 코드를 고정 어휘 사유로 접는다."""
    if status_code in (_HTTP_STATUS_UNAUTHORIZED, _HTTP_STATUS_FORBIDDEN):
        return "http_unauthorized"
    if status_code == _HTTP_STATUS_RATE_LIMITED:
        return "http_rate_limited"
    if _HTTP_STATUS_REDIRECT_RANGE_START <= status_code < _HTTP_STATUS_REDIRECT_RANGE_END:
        # H10(§5-3) — 차단된 리다이렉트를 "그 외 4xx/5xx"(http_error)로 접지 않는다. 응답
        # 자체는 정상이고 우리가 거부한 것이다 — 캡티브 포털의 302 가 실제로 발화하는 자리다.
        return "redirect_blocked"
    return "http_error"


def _classify_transport_error(error: Exception) -> FailureReason:
    """`ssl.SSLCertVerificationError`·`URLError`·`OSError` 계열을 tls_verify_failed 대
    network_error 로 가른다(H13, §9-8).

    두 경로를 함께 다룬다 — TLS 검증 실패가 그대로 올라오는 경우와 `URLError(reason=...)`
    로 감싸진 경우(실측 확인: 자체 서명 인증서로 만든 로컬 HTTPS 서버에 urllib 으로 접속해
    올라온 예외를 관측했다 — 표준 urllib 의 실제 경로는 이쪽이다). 세
    예외 계열을 한 except 절에서 함께 잡고(호출부) 이 함수가 내부에서 isinstance 로
    가르므로, `SSLCertVerificationError` 가 `OSError` 하위라는 사실 때문에 따로 두면
    필요했던 except 절 순서 문제(GOTCHA 9)가 애초에 생기지 않는다."""
    if isinstance(error, ssl.SSLCertVerificationError):
        return "tls_verify_failed"
    if isinstance(error, urllib.error.URLError) and isinstance(error.reason, ssl.SSLCertVerificationError):
        return "tls_verify_failed"
    return "network_error"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """리다이렉트를 따라가지 않는다(불변식 A-SEC — §5-3). `redirect_request` 가 `None` 을
    돌려주면 urllib 의 에러 처리 체인이 그 3xx 응답을 최종적으로 `HTTPError` 로 승격시킨다
    (로컬 스텁 서버로 실측 확인 — §9-8 "구현 시 실측할 것", RedirectBlockedStubServerTest)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_usage_api_request(request: urllib.request.Request):
    """리다이렉트를 따라가지 않는 opener 로 1회 보낸다(불변식 A-SEC — §5-3).

    `urllib.request.install_opener()`(전역 설치)는 쓰지 않는다 — 전역 가변 상태 금지
    (GOTCHA 11, rules/workflow/code-quality-baseline.md). opener 는 호출마다 지역으로 새로
    만든다. 테스트의 모킹 이음선은 이 함수 하나다 — `urllib.request.urlopen` 을 더 이상
    호출하지 않는다(§5-4, 기존 테스트 이전 대상).
    """
    opener = urllib.request.build_opener(_NoRedirectHandler)
    return opener.open(request, timeout=FETCH_TIMEOUT_SECONDS)


def _capped_response_key_structure(key_structure: list[str] | None) -> list[str] | None:
    """`describe_json_key_structure` 결과를 항목 수와 누적 바이트 양쪽으로 자른다(H11, §7-2 ·
    구현 2회차 — 항목 수만으로는 각 항목이 조상 키 경로 전체를 담아 총 바이트가 항목 수 ×
    경로 길이로 증폭되는 경로를 막지 못했다, `USAGE_API_MAX_RESPONSE_KEY_BYTES` 주석 참고).

    개수·바이트 둘 중 하나라도 넘으면 표지 항목을 마지막에 **하나만** 남긴다 — 둘 다 넘겨도
    표지는 하나다. 개수·바이트 모두 상한 이내(정확히 상한인 경우 포함)면 표지를 붙이지
    않는다. 조용히 자르면 이 목록 자체가 자기 진단 창구라는 약속이 거짓말이 된다."""
    if key_structure is None:
        return None

    was_over_entry_count = len(key_structure) > USAGE_API_MAX_RESPONSE_KEY_ENTRIES
    candidate_entries = key_structure[:USAGE_API_MAX_RESPONSE_KEY_ENTRIES]

    kept_entries: list[str] = []
    accumulated_bytes = 0
    was_over_byte_budget = False
    for entry in candidate_entries:
        entry_bytes = len(entry.encode("utf-8"))
        if accumulated_bytes + entry_bytes > USAGE_API_MAX_RESPONSE_KEY_BYTES:
            was_over_byte_budget = True
            break
        kept_entries.append(entry)
        accumulated_bytes += entry_bytes

    if not was_over_entry_count and not was_over_byte_budget:
        return key_structure
    truncation_marker = "…(상한 초과로 나머지 생략됨 — 개수는 세지 않는다)"
    return [*kept_entries, truncation_marker]


def fetch_rate_limit_capture(
    now_ms: int,
) -> tuple[hub_usage.RateLimitCapture | None, FailureReason | None, list[str] | None]:
    """사용량 API 를 1회 호출해 캡처를 만든다.

    반환은 `(캡처, 실패사유, 실패상세)` 3-튜플이다(개정 반영 — SP3 생략과 함께). 캡처 또는
    실패사유 중 정확히 하나가 채워진다. 실패상세는 `schema_mismatch` 일 때만 응답의 키
    구조 목록(값은 없다, 불변식 A-SEC)을 담아 자기 진단 창구가 된다 — 그 외 사유는 항상 None.

    길이를 헬퍼로 더 쪼개지 않은 이유(구현 2회차, 검수 확정) — 이 함수 길이의 상당 부분은
    실행문이 아니라 이 저장소 규칙(rules/python/coding-style.md)이 요구하는 근거 주석과
    docstring 이다(세는 방법: 함수 본문에서 `^\s*#` 로 시작하는 줄 수를 grep -c 로 세면
    실행문과의 비율을 알 수 있다 — 정확한 총 줄 수를 여기 적지 않는 이유는 이 문단 자체가
    그 수를 계속 바꾸기 때문이다). 파싱 호출을 헬퍼로 뽑아도 그 호출을 같은 try 절 안에
    두면 "파싱은 이 함수의 try 경계 안에서 일어난다"(결정 AR4/B-1)는 보장은 지금과 똑같이
    구조적이다 — 이 보장은 "그 줄들이 try 안에 배치돼 있다"는 사실 자체가 전부이지 주석에
    기대는 것이 아니다. 그런데도 쪼개지 않는 이유는 그 보장과 무관하다 — 줄 수 규칙 준수
    자체를 목적으로 호출부 1곳뿐인 헬퍼를 새로 만드는 것은 추측성 추상화(YAGNI,
    karpathy-guidelines.md #2)다.
    """
    token, credential_failure_reason = _read_oauth_access_token_with_reason()
    if token is None:
        return None, credential_failure_reason, None

    request = urllib.request.Request(
        USAGE_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": ANTHROPIC_BETA_HEADER_VALUE,
        },
        method="GET",
    )
    try:
        with _open_usage_api_request(request) as response:
            # H11(§9-8, GOTCHA 10) — 상한+1 을 읽어 초과를 판정한다. 상한만 읽으면 "정확히
            # 상한"과 "초과"를 구분할 수 없다(정확히 상한이면 cap+1 을 읽어도 cap 바이트만
            # 나온다).
            body = response.read(USAGE_API_MAX_RESPONSE_BYTES + 1)
        if len(body) > USAGE_API_MAX_RESPONSE_BYTES:
            return None, "response_too_large", None
        text = body.decode("utf-8", errors="replace")
        # 파싱 2줄을 이 try 경계 안으로 옮긴다(결정 AR4/B-1) — 이 함수가 자기 계약의
        # "마지막 방어선"이라는 취지(아래 except Exception 주석)가 원래 파싱까지
        # 덮어야 성립하는데, 이 두 줄이 경계 밖에 있으면 파싱이 분류되지 않은 예외를
        # 던질 때(예: 병리적으로 깊은 중첩 응답의 RecursionError) 그대로 호출자까지
        # 샌다. 반환 계약은 그대로다.
        capture = hub_usage.parse_usage_api_response(text, now_ms)
        if capture is None:
            return None, "schema_mismatch", _capped_response_key_structure(
                hub_usage.describe_json_key_structure(text)
            )
        return capture, None, None
    except urllib.error.HTTPError as error:
        return None, _classify_http_error(error.code), None
    except (ssl.SSLCertVerificationError, urllib.error.URLError, OSError) as error:
        # H13 — TLS 검증 실패(직접 또는 URLError 로 감싸진 경우)는 tls_verify_failed, 그 외
        # (타임아웃·DNS 등, 여전히 network_error — U-R6 회귀 방지)는 _classify_transport_error
        # 가 가른다.
        return None, _classify_transport_error(error), None
    except Exception:
        # 이 함수는 토큰을 지역 변수로 쥔 채로 원격 호출을 한다(불변식 A-SEC 경계) — 여기서
        # 분류하지 못한 예외를 그대로 밖으로 새어나가게 두면 호출자(실제 호출 경로는
        # `_usage_api_poll_loop` → `_run_usage_api_poll_cycle`)의 범용 핸들러가 그 예외를
        # 문자열로 바꿔 server.log 에 남긴다. http.client.IncompleteRead·
        # BadStatusLine 처럼 OSError 가 아닌 http.client.HTTPException 계열이 실제로 이
        # 경계를 뚫는 사례다(검수 지적). 이런 예외들이 우연히 토큰을 담지 않더라도, "토큰
        # 보유 함수에서 미분류 예외가 경계를 넘는다"는 구조 자체가 A-SEC 이 없애려는 형태라
        # 이 함수만은 마지막 방어선으로 광범위하게 잡는다 — 다른 모듈에는 이 관례를 적용하지
        # 않는다(카프시 #2, 이유가 있는 곳에만 예외 처리를 둔다).
        return None, "network_error", None
