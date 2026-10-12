"""hub_redact.py — 알려진 시크릿 토큰 형태를 마스킹하는 순수 함수.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_redact.py 대상).

docs/prps/tier0-defect-fixes.md 는 이 함수를 "사용처가 1곳뿐이라 별도 모듈로 빼지 않는다"고
적었으나, docs/prps/hub-workflow-visibility.md 결정 WF3 에서 그 전제가 소멸했다 — 사용처가
hub_hook.py(훅 로그 스크럽)와 hub_workflow.py(워크플로우 발췌 스크럽) 2곳이 되면서, 후자가
전자에서 직접 임포트하면 hub_collect → hub_workflow → hub_hook → hub_collect 순환이 생겼다
(hub_hook.py 는 임포트 시점에 Path.home() 을 계산해 환경변수에 닿으므로, 순수 레이어가 그것을
끌어들이면 ★순수 표기 자체가 거짓이 된다). 패턴을 두 곳에 복제하면 한쪽만 갱신되는 보안
드리프트가 나므로(DRY 가 여기서는 보안 요구다) 공유 모듈로 추출했다.

**결정 PS4(docs/prps/hub-agent-runs-and-prompt-source.md)로 hub_hook.py 는 더 이상 이
모듈을 쓰지 않는다** — 훅이 프롬프트를 아예 기록하지 않으므로 스크럽할 문자열이 없다.
지금의 사용처는 hub_workflow.py(워크플로우 label)·hub_transcript.py(last-prompt 줄의 값 —
결정 PS9, 사람 프롬프트 줄에서 유도한 값 — 결정 TF4)·hub_subagent.py(서브에이전트 제목·재개 요약,
결정 AR10·TF10) 3곳이다 — 위 순환 회피 근거는 그대로 유효하다(어느 쪽도 hub_hook.py 를 끌어들이지 않는다).
"""

import re

SECRET_REDACTION_MARK = "[REDACTED]"
# 각 대안은 "리터럴 접두사 + 단일 문자클래스 한정 수량자"로만 구성한다 — ECC 원본 구현이
# catastrophic backtracking 으로 CPU 100% 에 고착됐던 이슈(#2278)의 이식 조건이다. 패턴을
# 추가할 때 이 제약을 지켜라: 중첩 수량자(`(a+)+` 형태)·패턴 내 백레퍼런스·값 클래스와
# 겹치는 인접 모호 수량자를 넣지 않는다 — 위반하면 이 함수를 쓰는 호출부의 절대 규칙("세션을
# 막지 않는다"·"수집을 막지 않는다")이 깨진다. 이 제약이 막는 것은 지수 시간이다 — 접두가 값
# 클래스의 글자로 이뤄진 대안(JWT 의 `eyJ`)은 그 접두가 반복되는 긴 글에서 시작 위치마다 값
# 클래스를 끝까지 훑고 물러나 길이의 제곱에 비례해 느려지므로(128KiB 에 8초), 입력이 길 수
# 있는 호출자는 길이를 먼저 제한해야 한다(redact_secret_tokens 참고). 고정·최소 길이가 40자를
# 넘는 패턴을 추가하면 hub_transcript.BOUNDARY_FRAGMENT_MAX_CHARS 를 같이 올린다 — 사람 프롬프트 줄
# 유도 경로는 제한한 입력의 끝에서 한 글자 모자라게 잘린 조각이 마스킹되지 않는데, 그 상수가 조각의
# 최대 길이를 덮는다(hub_subagent 의 제목 경로와 hub_workflow 의 label 경로는 제한을 넘는 글을
# 통째로 버려 이 문제가 없다).
SECRET_TOKEN_PATTERN = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{10,}"                      # Anthropic
    r"|sk-[A-Za-z0-9]{20,}"                            # OpenAI 계열
    r"|AKIA[0-9A-Z]{16}"                               # AWS access key
    r"|gh[pousr]_[A-Za-z0-9]{36}"                      # GitHub 토큰
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"                   # Slack
    r"|AIza[0-9A-Za-z_-]{35}"                          # Google API
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"  # JWT
    r"|-----BEGIN [A-Z ]{0,24}PRIVATE KEY-----[A-Za-z0-9+/=\s]*"
    r"(?:-----END [A-Z ]{0,24}PRIVATE KEY-----)?"
    r"|[Bb]earer +[A-Za-z0-9._~+/=-]{16,}"
)
# 키 이름(api_key=… 의 "api_key")은 보존하고 값만 지운다 — 발췌가 "무엇이 새고 있었는지"의
# 문맥을 유지해야 툴팁이 쓸모가 있다.
KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd)(\s*[:=]\s*)"
    r"(\"[^\"\n]{6,}\"|'[^'\n]{6,}'|[A-Za-z0-9_/+.\-]{6,})"
)


def redact_secret_tokens(prompt: str) -> str:
    """알려진 시크릿 토큰 형태를 마스킹한다. 지수 시간 백트래킹 형태는 금지한다 — 다만 선형 시간은 아니다.

    JWT 대안(`eyJ…` 뒤에 점 둘)은 점 없이 `eyJ` 가 반복되는 긴 글에서 길이의 제곱에 비례해 느려진다(128KiB 에 8초, 검수
    실측). 패턴은 모든 호출자가 공유하는 보안 표면이라 그대로 두고, **입력이 길 수 있는 호출자가 길이를 먼저 제한해 넘긴다**
    — hub_transcript.py 의 사람 프롬프트 줄 유도 경로는 앞 2,000자만 스크럽하고(결정 TF4,
    DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS — 그 제한 경계의 잔존 위험은 상수 주석에 있다),
    hub_subagent.py 의 제목 경로(description·재개 요약)는 1,200자를 넘는 글을 잘라 스크럽하지 않고
    통째로 버린다(SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS — 제목이 아닌 글이고, 잘라서 스크럽하면 자른
    자리에 걸린 시크릿의 머리가 마스킹되지 않기 때문이다). hub_workflow.py 의 label 경로도 같다 —
    제한(WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS)을 넘는 글은 label 이 아니라 스크럽 없이 통째로 버리고,
    이하는 전체를 스크럽한 뒤 자른다(호스트가 label 길이를 보장하지 않기 때문이다 — 스크립트가 준
    값은 자르지 않는다).

    가능하면 호출자가 문자열을 자르기 전에 이 함수를 불러야 한다 — 자른 뒤에 스크럽하면
    절단 경계에 걸친 시크릿이 패턴 불일치로 살아남아 접두사가 그대로 유출된다(hub_subagent.py 의
    제목 경로와 hub_transcript.py 의 사람 프롬프트 줄 유도 경로가 그 순서를 지키는 사례다). 호스트가
    이미 잘라 놓은 문자열을 받는 호출자는 그 순서를 지킬 수 없어 이 잔존 위험을 그대로 안는다 —
    hub_transcript.py 의 last-prompt 값(호스트가 실측 최대 201자로 잘라 적는다. 이 경로의 입력 길이는
    코드가 아니라 그 호스트 절단에 기대므로, 호스트가 자르기를 멈추면 다른 경로처럼 코드로 묶어야
    한다)과 hub_workflow.py 의 label 중 스크립트가 주지 않아 호스트가 프롬프트 머리를 잘라 만든
    것(실측 최장 60자)이 그렇다. docs/prps/hub-workflow-visibility.md 결정 WF7 이 같은 위험을 먼저
    적었다(그 호출자였던 워크플로우 발췌 필드는 이슈 3 의 WT3 으로 빠졌다). 과잉 마스킹은
    허용한다 — 이것은 관측 로그 발췌이지 원문 보존이 아니며, 원문은 사용자 세션에 그대로 있다.
    """
    redacted = SECRET_TOKEN_PATTERN.sub(SECRET_REDACTION_MARK, prompt)
    return KEY_VALUE_SECRET_PATTERN.sub(r"\1\2" + SECRET_REDACTION_MARK, redacted)
