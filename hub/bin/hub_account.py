"""hub_account.py — 로그인 계정 표시용 3값의 외부 계약 파서(순수 · 잎 모듈).

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_account.py 대상).
어떤 허브 모듈도 임포트하지 않는 **잎 모듈**이다. 다루는 외부 포맷은 하나다 — Claude Code 가
관리하는 전역 설정 파일(`~/.claude.json`)의 `oauthAccount` 객체. 우리가 만들지 않는 포맷이라
`hub_usage.py` 와 같은 fail-open 태도다: 계약이 안 맞으면 예외가 아니라 (None, 사유)를 돌려주고,
호출자(hub_collect.py)가 그 실패를 경고로 흡수한다.

꺼내는 키는 **정확히 셋**이다 — `organizationType`(요금제 판정) · `organizationName` ·
`emailAddress`(결정 AC1). 나머지 값은 꺼내지 않고, 파싱한 dict 를 돌려주거나 보관하지 않으며,
사유 문자열에도 입력 값을 넣지 않는다 — 이것이 이 모듈이 보장하는 "추출 경계"다
(tests/hub/test_hub_account.py AT13·AT14 가 센티넬 전수로 고정한다). 설계 근거는
docs/prps/hub-usage-panel-account.md 결정 AC1·AC3·AC4·AC9 가 정본이다.
"""

import json
from dataclasses import dataclass

# 256 = 이메일 경로 상한(254)을 덮는 최소 2의 거듭제곱. 조직 이름에도 같은 상한을 쓴다 —
# 규칙이 하나면 설명도 테스트도 하나다(hub_usage._is_valid_epoch_ms 의 선례). 초과 값은
# 자르지 않고 버린다 — 잘린 이메일은 틀린 이메일이다(결정 AC4).
ACCOUNT_FIELD_MAX_CHARS = 256

# organizationType → 표시명. Claude Code CLI 가 `/status` 에 보이는 이름과 같은 낱말이다
# (결정 AC3). 모르는 값은 대응표에 없으므로 그 줄이 생략된다 — CLI 처럼 "Claude API" 로
# 떨어뜨리면 새 요금제 종류를 거짓으로 부르게 된다.
ACCOUNT_PLAN_LABELS: dict[str, str] = {
    "claude_pro": "Claude Pro",
    "claude_max": "Claude Max",
    "claude_team": "Claude Team",
    "claude_enterprise": "Claude Enterprise",
}

# 계약 불일치 사유 — 고정 문구다. 경로와 입력 값은 담지 않는다(경로는 호출자가 붙인다, 결정 AC9).
REASON_UNREADABLE_DOCUMENT = "JSON 계약 불일치 — 계정 정보를 표시하지 않습니다"
REASON_ACCOUNT_NOT_OBJECT = "oauthAccount 가 객체가 아님 — 계정 정보를 표시하지 않습니다"
REASON_NO_DISPLAYABLE_VALUE = "계정 표시값이 하나도 없음 — 키 이름이 바뀌었을 수 있습니다"


@dataclass(frozen=True)
class AccountInfo:
    """로그인 계정의 표시용 3값 — ~/.claude.json oauthAccount 의 투영(결정 AC1). 각각 없을 수 있다.

    불변식: 세 필드가 모두 None 인 AccountInfo 는 만들지 않는다(그 경우는 None 자체).
    """

    plan_label: str | None          # organizationType 대응표 결과("Claude Team" 등). 모르는 값이면 None
    organization_name: str | None   # oauthAccount.organizationName (공백 제거, 1~256자)
    email: str | None               # oauthAccount.emailAddress (공백 제거, 1~256자)


def _valid_account_text(value: object) -> str | None:
    """문자열이고 공백을 뗀 길이가 1~256자이면 그 값, 아니면 None(결정 AC4)."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > ACCOUNT_FIELD_MAX_CHARS:
        return None
    return stripped


def _plan_label(value: object) -> str | None:
    """organizationType 값을 표시명으로 바꾼다. 문자열이 아니거나 모르는 값이면 None(결정 AC3)."""
    if not isinstance(value, str):
        return None
    return ACCOUNT_PLAN_LABELS.get(value)


def parse_account_info(text: str) -> tuple[AccountInfo | None, str | None]:
    """~/.claude.json 본문에서 계정 3값을 꺼낸다. (결과, 계약 불일치 사유) — 예외를 던지지 않는다.

    사유는 경로·입력 값을 담지 않는 고정 문구다(경로는 호출자가 붙인다). 정상적인 부재
    (oauthAccount 없음·null)는 (None, None) — 로그아웃·API 키 로그인의 정상 상태다(결정 AC9).
    """
    try:
        document = json.loads(text)
    except (ValueError, TypeError):
        # JSONDecodeError 는 ValueError 의 하위 — 4300자리를 넘는 정수 리터럴은 순수 ValueError 를 던진다.
        return None, REASON_UNREADABLE_DOCUMENT
    if not isinstance(document, dict):
        return None, REASON_UNREADABLE_DOCUMENT
    oauth_account = document.get("oauthAccount")
    if oauth_account is None:
        return None, None
    if not isinstance(oauth_account, dict):
        return None, REASON_ACCOUNT_NOT_OBJECT
    info = AccountInfo(
        plan_label=_plan_label(oauth_account.get("organizationType")),
        organization_name=_valid_account_text(oauth_account.get("organizationName")),
        email=_valid_account_text(oauth_account.get("emailAddress")),
    )
    if info.plan_label is None and info.organization_name is None and info.email is None:
        return None, REASON_NO_DISPLAYABLE_VALUE
    return info, None
