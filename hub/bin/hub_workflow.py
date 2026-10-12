"""hub_workflow.py — Workflow 툴이 남기는 wf_<runId>.json 실행 기록의 순수 파서 + 표시용 뷰.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_workflow.py 대상).
wf_<runId>.json(~/.claude/projects/<인코딩>/<session_id>/workflows/wf_<runId>.json)은 우리가
소유하지 않는 외부 파일 형식이다 — hub_transcript.py 가 transcript JSONL 에 대해 세운 선례와
같은 이유로, 그 계약이 바뀌면 이 모듈 하나만 고치면 되도록 hub_session.py 에 얹지 않고
분리했다(결정 WF2, docs/prps/hub-workflow-visibility.md). 파일 접근(stat·glob·읽기)은 전부
hub_collect.py 가 맡는다 — 이 모듈은 이미 읽힌 텍스트만 받는다.

**계약 A(구현 3회차로 필드 열거에서 계약 서술로 개정 — 결정 WF7)**: hub.html 에 인라인되는
이 모듈의 문자열 필드는 예외 없이 아래 둘 중 하나의 경로를 거친다. 2회차는 이 계약을
"스크럽 대상 필드"를 하나씩 나열하는 방식으로 적어, 소속 단계 이름 필드가 그 목록에서 빠진
채 누락됐었다(검수 C-2) — 그래서 이번엔 필드를 나열하지 않고 두 경로 자체를 계약으로 적는다.
**루프 밖 보완**: `WorkflowRunView.run_id`·`workflow_name`·`status`·`started_at_ms` 4개는
hub_template.html 어디에서도 참조되지 않는 미사용 필드였다(데이터 최소화 근거로 제거,
docs/prps/hub-workflow-visibility.md §19). 그 결과 2번 경로 대상은 `state` 하나만 남았다.

1. **스크럽 + 401자 상한** (`_scrubbed_and_clipped`, WORKFLOW_PREVIEW_MAX_CHARS) —
   `label` 만(이슈 3, 결정 WT3 — 소속 단계 이름·프롬프트 발췌·결과 발췌 3개 필드는 유일한
   소비처였던 워크플로우 칩 툴팁이 제거되며 함께 빠졌다, `docs/prps/hub-ui-4-issues.md` §4).
   자유 텍스트 프롬프트에서 파생될 수 있는 콘텐츠라는 것이 스크럽 대상인 이유다 — label 이
   그런 경위로 "짧은 식별자인 줄 알았는데 프롬프트 파생 콘텐츠"였다(§2).
   WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS 를 넘는 글은 label 이 아니므로 스크럽 없이 버린다(빈
   문자열 — 상수 주석).
2. **128자 상한만, 스크럽 없음** (`_metadata_field`, WORKFLOW_METADATA_MAX_CHARS) — `state`.
   스크럽을 생략하는 근거는 닫힌 값 집합 성격이라는 관측이다(실측: "done"·"error" 뿐, §2)
   — 이는 지금까지의 실측 근거일 뿐 구조적 보장은 아니므로(호스트 계약이 바뀌면 이 문서부터
   다시 확인한다), 스크럽은 생략해도 **상한만은 예외 없이 건다.** state 는 칩 툴팁 제거
   이후에도 남는다 — 실패한 에이전트 칩의 시각 상태(선택 항목 E, 결정 WT7)가 이 값으로
   판정한다.

정수 필드 `index` 는 `_bounded_index` 로 `[0, WORKFLOW_RUN_MAX_AGENTS]` 범위 상한을 건다
(루프 밖 보완 — 4,300자리 미만 정수 리터럴은 json.loads 자체를 통과하므로 문자열 필드와
같은 계열의 방어가 필요했다). 에이전트 개수도 상한이 있다(`WORKFLOW_RUN_MAX_AGENTS`, index
오름차순으로 앞에서부터 유지) — 클라이언트 표시 상한(`MAX_VISIBLE_WORKFLOW_CHIPS`,
hub_template.html)은 "화면에 몇 개 보여줄까"일 뿐 뷰 자체의 크기를 막지 못한다(구현 3회차
검수 재현: 에이전트 30,000개가 그대로 직렬화됐다).

호스트는 label 길이를 보장하지 않는다 — 스크립트가 준 label 은 자르지 않고, 스크립트가 주지 않으면
호스트가 프롬프트 머리를 잘라 만든다(실측 최장 60자, §2). §2 가 이미 밝혔듯 "우리가 소유하지 않는 외부
형식"이라 그 계약을 강제할 수 없으므로 스크럽 **전에** 길이부터 본다. 파생 label 은 호스트의 절단
경계를 넘겨받아 그 경계에 걸친 시크릿 조각이 남을 수 있다(결정 WF7 과 같은 종류의 잔존 위험).
WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS 를 넘는 글은 스크럽도 하지 않고 빈 문자열로 버린다(이유 —
가용성·마스킹·버려서 잃는 것이 없다는 실측은 그 상수 주석). 이하인 label 은 전체를 스크럽한 뒤
WORKFLOW_PREVIEW_MAX_CHARS 로도 자른다(구현 2회차 검수 C-1) — 입력 상한 이하 label 의 출력
길이를 묶는 방어선은 이 401자 상한이다. 반드시 스크럽 **뒤에** 자른다 —
순서를 바꾸면 절단 경계에 걸린 시크릿이 패턴 불일치로 살아남는다(hub_subagent 의 제목 경로
_scrubbed_and_clipped 와 같은 이유). **[이슈 3, 결정 WT4 — "발동 비용 0" 서술의 정정]**
이전 판은 이 401자 상한이 호스트의 프롬프트 발췌 키 실측(497/503 이 이미 401자)을 근거로
"정상 데이터에서도 발동하는 방어선"이라 적었으나, 그 근거였던 프롬프트 발췌 필드는 WT3
으로 제거됐다. label 실측 max 60자(실측: wf_*.json 66파일 450개 label 전수 — min 2·중앙
16·max 60) — 401 상한은 입력 상한 이하의 병리적 입력(예: 401자를 넘는 label)에 대한
방어선이며 정상 데이터에서는 발동하지 않는다. 검수가 재현한 5,000자 label 은 이제 이 상한에
닿기 전에 입력 상한에서 버려진다.
"""

import json
from dataclasses import dataclass

from hub_redact import redact_secret_tokens

WORKFLOWS_DIR_NAME = "workflows"          # <session_id>/ 아래 실행 기록 디렉터리
WORKFLOW_RUN_FILE_GLOB = "wf_*.json"
# 4MiB — 실측 최대(818KB)의 약 5.1배(결정 WF11). 부피의 원인은 script(스크립트 전문)·logs·
# result 가 같은 파일에 인라인돼 있는 것이다 — 이 셋은 파일에서 읽히지만(4MiB 상한이 그래서
# 필요하다) hub.html 에는 인라인하지 않는다.
WORKFLOW_RUN_MAX_BYTES = 4 * 1024 * 1024

_AGENT_ITEM_TYPE = "workflow_agent"        # workflowProgress 안의 항목 종류 판별값(다른 값: workflow_phase)

# 400자(호스트 실측 최대) + 말줄임표 1자(구현 2회차 검수 C-1). label 을 비롯해 이슈 3(WT3)
# 으로 제거된 세 발췌성 필드(소속 단계 이름·프롬프트 발췌·결과 발췌)도 한때 hub.html 에
# 인라인되는 발췌성 콘텐츠로 같은 상한을 공유했다(소속 단계 이름 필드는 구현 3회차에
# 합류 — 2회차는 스크럽만 하고 이 상한을 걸지 않아 100,000자가 그대로 통과했다, 검수
# 3회차 재현). **[루프 밖 보완 — 발동 빈도 정정, 이슈 3 이전 실측 기록]** 호스트는 그
# 프롬프트·결과 발췌 키들을 실측 전량(502/502) 이 상한 안에서 이미 잘라 보냈지만, 실물
# 74개 파일·503개 항목 재실측에서 그중 497/503(98.8%)이 이미 정확히 401자라 여유가
# 0이었다. 게다가 스크럽이 값을 **늘릴 수 있어**(예: KEY_VALUE_SECRET_PATTERN 이 6자 값을
# 10자 [REDACTED] 로 치환) 401자에 근접한 정상 프롬프트에 시크릿이 여러 개 섞이면 스크럽
# 후 실제로 이 상한이 발동했다 — 지금은 label 만 이 상한을 거치고, label 실측 max 60자라
# 정상 데이터에서는 발동하지 않는다(병리적 입력 방어선, WT4. label 실측 근거: wf_*.json
# 66파일 450개 label 전수 — min 2·중앙 16·max 60).
WORKFLOW_PREVIEW_MAX_CHARS = 401
WORKFLOW_PREVIEW_TRUNCATION_MARK = "…"
# label 로 받아들이는 글의 최대 길이(스크럽 입력 상한) — 서브에이전트 제목의 같은 상한(hub_subagent.SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS)과 같은
# 값이다. hub_subagent 를 임포트하지 않고 이 모듈이 따로 갖는다(파서 모듈끼리 서로 임포트하지 않는다). 이걸 넘는 글은 label 이 아니므로
# 스크럽(redact_secret_tokens)에 넘기지 않고 통째로 버린다(빈 label, _scrubbed_and_clipped). 이유 셋.
# (1) 가용성: wf_*.json 은 4MiB(WORKFLOW_RUN_MAX_BYTES)까지 읽히고 스크립트가 준 label 은 호스트가 자르지 않아 label 하나가 수백만 자일 수 있다. 스크럽의
# JWT 대안(`eyJ…` 뒤에 점 둘)은 점 없이 `eyJ` 가 반복되는 긴 글에서 길이의 제곱에 비례해 느려진다. 실측(길이 600·1,200·2,400·4,800자의 중앙값
# 0.19·0.68·2.7·10.8ms — 계수가 0.47ns/자² 안팎으로 일정하다)을 제곱 법칙으로 늘린 추정은 128KiB 에 약 8초(hub_redact 가 적은 검수 실측과 맞는다)·
# 4MiB 에 약 2.3시간이다(긴 입력은 재지 않았다). 상한이 없던 때는 4MiB 파일의 label 하나가 수집(collect)을 몇 시간 멈출 수 있었다. 상한 길이에서
# label 하나의 최악은 약 0.7ms(실측)이고 실행당 에이전트가 최대 WORKFLOW_RUN_MAX_AGENTS(100)개라 실행 하나의 최악은 약 70ms 다(100개가 전부
# 상한 길이의 eyJ 반복인 127KB 파일을 parse_workflow_run 으로 푼 실측 69.8ms).
# (2) 마스킹: 상한에서 잘라 스크럽하면 자른 자리에 걸린 시크릿 — 서명이 창 밖인 JWT, 닫는 따옴표가 창 밖인 password="…" 값 — 이 패턴을 못 채워
# 마스킹되지 않은 머리가 label 로 나간다. 잘라 쓰지 않고 버리면 이 경계 위험이 전부 닫힌다. (3) 버려서 잃는 것이 없다: 실측 label 은 max 60자다
# (wf_*.json 66파일 450개 전수 — min 2·중앙 16·max 60. 재실측 47파일 272개 — min 3·중앙 13·p90 22·max 60, 401자 초과 0건). 상한 이하는 이전과
# 같다(전체 스크럽 뒤 WORKFLOW_PREVIEW_MAX_CHARS 로 자른다).
WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS = 1200

# 128 — state(닫힌 값 집합, 모듈 docstring 참조)는 스크럽하지 않는다. 실측 최댓값("error"
# 5자, §2)에 넉넉한 여유를 둔 별도의 더 타이트한 상한이다 — 발췌성 콘텐츠
# (WORKFLOW_PREVIEW_MAX_CHARS=401)와 성격이 달라 같은 상수를 재사용하지 않는다.
# 구현 3회차 검수 재현(100,000자)의 방어망 — 오늘 데이터에는 발동하지 않는다(닫힌 값
# 집합이라 실측 최댓값과 상한의 배율이 WORKFLOW_PREVIEW_MAX_CHARS 와 달리 매우 크다).
WORKFLOW_METADATA_MAX_CHARS = 128

# 100 — 실측 최대(§3 계측 8: 실행당 평균 6·max 25)의 4배 여유. 클라이언트 표시 상한
# (MAX_VISIBLE_WORKFLOW_CHIPS=12, hub_template.html)과는 별개다 — 그 상한은 "화면에 몇
# 개 보여줄까"이고 이 상한은 "병리적 페이로드가 뷰 자체를 얼마나 부풀릴 수 있는가"를
# 막는 서버측 방어선이다(구현 3회차 검수 재현: 에이전트 30,000개가 그대로 직렬화됐다).
# 초과분은 index 오름차순 유지한 채 앞에서부터 이 개수만 남기고 버린다 — 클라이언트
# 오버플로 정책(결정 K3, "+N" 표시 없이 조용히 버림)과 같은 설계를 서버 방어선에도
# 적용한 것이라 별도 경고를 남기지 않는다(결정 WF13, docs/prps/hub-workflow-visibility.md).
# 루프 밖 보완: index 값 자체의 상한(_bounded_index)으로도 재사용한다 — 정상 index 는
# 실측 1~25(§3 계측 8)라 에이전트 "개수" 상한을 index "값" 상한으로 겸용해도 정상
# 데이터를 자르지 않는다.
WORKFLOW_RUN_MAX_AGENTS = 100


# ---- 표시(view) ----
@dataclass(frozen=True)
class WorkflowAgentView:
    """워크플로우 실행 안의 서브에이전트 1개 — 화면 표시용 투영.

    **이슈 3(결정 WT3, docs/prps/hub-ui-4-issues.md §4)**: 소속 단계 이름·프롬프트 발췌·
    결과 발췌 3개 필드는 워크플로우 칩 툴팁(유일한 소비처)이 제거되며 함께 빠졌다 —
    프롬프트 발췌는 형제끼리 동일하고(§4.1 실측) 결과 발췌는 84%가 잘린 raw JSON 이라
    읽을 수 있는 형태가 아니었다. state 는 실패 칩 시각 상태(선택 항목 E)가 남아 유지한다.
    """

    index: int                    # 1-based, 스크립트 순서. 정렬 키(실측 502/502 연속). [0, WORKFLOW_RUN_MAX_AGENTS] 범위 상한(루프 밖 보완, _bounded_index)
    label: str                    # 스크립트가 붙인 팬아웃 식별자. 스크럽 + 401자 상한 후(구현 2회차 검수 C-1). 스크럽 입력 상한 초과는 "". 표시 절단은 별도로 클라이언트도 한다
    state: str                    # 원문 그대로, 128자 상한만(구현 3회차, 스크럽 없음). 실측값은 "done"·"error" 뿐이나 표를 만들지 않는다. 실패 칩 시각 상태(선택 항목 E)가 이 필드로 판정한다


@dataclass(frozen=True)
class WorkflowRunView:
    """세션의 최신 워크플로우 실행 1건 — 화면 표시용 투영.

    **루프 밖 보완**: 이전 판은 run_id·workflow_name·status·started_at_ms 4개 필드를 더
    가졌으나, hub_template.html 어디에서도 참조되지 않는 미사용 필드였다(YAGNI, 데이터
    최소화 — docs/prps/hub-workflow-visibility.md §19). agents 하나만 남긴다.
    """

    agents: tuple[WorkflowAgentView, ...]   # index 오름차순, 최대 WORKFLOW_RUN_MAX_AGENTS 개(구현 3회차)


# ---- 타입 방어 (호스트 소유 형식이라 타입 보장이 없다) ----
def _string_or_empty(value: object) -> str:
    """값이 문자열이면 그대로, 아니면 빈 문자열."""
    return value if isinstance(value, str) else ""


def _int_or_zero(value: object) -> int:
    """값이 정수면 그대로, 아니면 0. bool 은 int 의 서브클래스라 함께 걸러낸다.

    정렬 키 계산 전용이다(_parse_agents 의 index 오름차순 정렬) — 값 범위를 제한하지
    않는다. 뷰 필드(WorkflowAgentView.index)에 담기는 값은 이 함수가 아니라
    _bounded_index 를 거친다(루프 밖 보완) — 정렬은 클램핑 없는 원본 값으로 해야 병리적
    으로 큰 index 들이 전부 0으로 뭉개져 순서가 무너지는 것을 피할 수 있다.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _bounded_index(value: object) -> int:
    """index 가 정수이고 [0, WORKFLOW_RUN_MAX_AGENTS] 범위 안이면 그대로, 아니면 0.

    루프 밖 보완 — WorkflowAgentView.index 전용 방어. 4,300자리 미만 정수 리터럴은
    json.loads 자체를 통과하므로(계약 B 의 자릿수 방어는 그 이상만 잡는다), 문자열
    필드(계약 A)와 같은 계열의 값 범위 방어가 필요했다(재현: {"index": "9"*4000} 같은
    자릿수 폭탄이 그대로 뷰에 실려 hub.html 에 인라인될 수 있었다). 상한은
    WORKFLOW_RUN_MAX_AGENTS 를 재사용한다 — 정상 index 는 실측 1~25(§3 계측 8)라 에이전트
    "개수" 상한과 같은 값을 index "값" 상한으로 겸용해도 정상 데이터를 자르지 않는다.
    """
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= WORKFLOW_RUN_MAX_AGENTS:
        return value
    return 0


def _clip_to_length(value: str, max_chars: int) -> str:
    """value 가 max_chars 를 넘으면 잘라 말줄임표를 붙인다.

    WORKFLOW_PREVIEW_MAX_CHARS(401)·WORKFLOW_METADATA_MAX_CHARS(128) 두 상한이 공유하는
    원시 동작이다(구현 3회차 — 필드마다 다른 절단 함수를 새로 만들지 않는다).
    """
    if len(value) <= max_chars:
        return value
    keep_length = max_chars - len(WORKFLOW_PREVIEW_TRUNCATION_MARK)
    return value[:keep_length] + WORKFLOW_PREVIEW_TRUNCATION_MARK


def _clip_scrubbed_value(value: str) -> str:
    """스크럽이 끝난 문자열이 WORKFLOW_PREVIEW_MAX_CHARS 를 넘으면 자른다.

    반드시 스크럽 **뒤에** 호출해야 한다(구현 2회차 검수 C-1) — 자르기부터 하면 절단 경계에
    걸친 시크릿이 패턴 불일치로 살아남아 접두사가 유출된다(hub_redact.redact_secret_tokens
    문서, hub_subagent 의 제목 경로와 같은 이유). 실측 정상 label(max 60자)에는 발동하지
    않는다 — 호스트가 label 길이를 보장하지 않아(스크립트가 준 값은 자르지 않는다) 입력 상한
    이하의 긴 label 이 올 수 있으므로 남겨 둔 방어선이다. 입력 상한
    (WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS)을 넘는 글은 여기까지 오지 않는다
    (_scrubbed_and_clipped 가 먼저 버린다).
    """
    return _clip_to_length(value, WORKFLOW_PREVIEW_MAX_CHARS)


def _scrubbed_and_clipped(value: str) -> str:
    """label 이 거치는 경로 — 스크럽 후 길이 상한을 적용한다(이슈 3 이전에는 소속 단계
    이름·프롬프트 발췌·결과 발췌도 같은 경로를 공유했다, WT3 으로 제거).
    WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS 를 넘는 글은 label 이 아니므로 스크럽도 하지 않고
    빈 문자열로 버린다.

    순서 고정: 길이 검사 → 스크럽 → 자르기. 입력 상한에서 잘라 스크럽하는 것은 자른 자리에 걸린
    JWT·따옴표 값의 머리가 마스킹되지 않는 구멍이라(상수 주석) 잘라 쓰지 않고 통째로 버린다.
    길이가 상한 이하이면 이전과 같다(전체 스크럽 뒤 401자로 자른다).
    """
    if len(value) > WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS:
        return ""
    return _clip_scrubbed_value(redact_secret_tokens(value))


def _metadata_field(value: object) -> str:
    """문자열이면 WORKFLOW_METADATA_MAX_CHARS 안으로 자르고, 아니면 빈 문자열.

    state 필드가 쓰는 경로다(구현 3회차, 계약 A. 루프 밖 보완으로 run_id·workflow_name·
    status 3개가 미사용 필드로 제거돼 이 경로의 대상은 state 하나만 남았다) — state 는
    스크럽하지 않지만(모듈 docstring — 닫힌 값 집합 성격), "hub.html 에 상한 없이
    인라인되는 문자열 필드는 없다"는 계약은 예외 없이 적용된다.
    """
    return _clip_to_length(_string_or_empty(value), WORKFLOW_METADATA_MAX_CHARS)


# ---- 파싱 ----
def _parse_agent_item(item: dict) -> WorkflowAgentView:
    """workflowProgress 안의 workflow_agent 항목 1개를 뷰로 만든다. 스크럽·절단은 여기서 끝낸다."""
    return WorkflowAgentView(
        index=_bounded_index(item.get("index")),
        label=_scrubbed_and_clipped(_string_or_empty(item.get("label"))),
        state=_metadata_field(item.get("state")),
    )


def _parse_agents(raw_progress: object) -> tuple[WorkflowAgentView, ...]:
    """workflowProgress 배열에서 workflow_agent 항목만 골라 index 오름차순으로 최대
    WORKFLOW_RUN_MAX_AGENTS 개까지 돌려준다.

    workflow_phase 항목(단계 제목)은 이 기능이 쓰지 않으므로 걸러낸다. 배열이 아니거나
    없으면 빈 튜플 — 뷰 자체는 여전히 만들어진다(agent 가 없다고 실행 자체를 감출 이유는
    없다). 정렬·상한 적용을 raw dict 에 대해 먼저 하고, 그 다음에만 스크럽 등 비용이 드는
    파싱을 한다(구현 3회차) — 상한 밖으로 밀려날 항목에 스크럽을 낭비하지 않는다. 초과분은
    경고 없이 버린다(WORKFLOW_RUN_MAX_AGENTS 주석 — 결정 WF13).
    """
    if not isinstance(raw_progress, list):
        return ()
    agent_items = [
        item for item in raw_progress
        if isinstance(item, dict) and item.get("type") == _AGENT_ITEM_TYPE
    ]
    agent_items.sort(key=lambda item: _int_or_zero(item.get("index")))
    limited_items = agent_items[:WORKFLOW_RUN_MAX_AGENTS]
    return tuple(_parse_agent_item(item) for item in limited_items)


def parse_workflow_run(text: str) -> WorkflowRunView | None:
    """wf_<runId>.json 본문을 표시용 뷰로 판다. 형식이 아니면 None (호출자가 건너뛴다).

    **계약 B(구현 3회차) — 이 함수는 어떤 입력에도 예외를 던지지 않는다.** label 은 뷰를
    만들기 전에 전부 스크럽한다(결정 WF7 — 입력 상한을 넘는 글은 스크럽 없이 버려 빈
    문자열이 된다) — 스크럽되지 않은 값이 뷰에 도달하는 코드
    경로가 없게 하는 구조적 장치다(이슈 3 이전에는 소속 단계 이름·프롬프트 발췌·결과
    발췌도 같은 스크럽을 거쳤다, WT3 으로 제거). isinstance 로만 방어하고 state 값을 표로
    좁히지 않는다 — 실측에 없는 값이 나와도 화면이 죽지 않아야 한다.
    """
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        # ValueError(구현 3회차) — json.JSONDecodeError(구문 오류)의 상위 클래스라 기존
        # 케이스를 포함하면서, 4,300자리를 넘는 정수 리터럴이 던지는 순수 ValueError(정수
        # 문자열 변환 자릿수 한도, CVE-2020-10735 완화 이후 CPython 기본 동작)까지 함께
        # 잡는다 — 2회차는 json.JSONDecodeError 만 잡아 이 형제 예외가 여전히
        # collect_snapshot 전체를 죽였다(검수 3회차 재현: '{"startTime": ' + '9'*5000 +
        # '}'). RecursionError(구현 2회차 검수 C-3) — 깊게 중첩된 입력(예: "["*n)은
        # json.JSONDecodeError 가 아니라 RecursionError 를 던진다. 예외 유형을 하나씩
        # 추가하는 대신 표로 모아 tests/hub/test_hub_workflow.py 의 병리적 입력 표로
        # 회귀를 고정한다(구현 3회차 래칫).
        return None
    if not isinstance(payload, dict):
        return None
    return WorkflowRunView(agents=_parse_agents(payload.get("workflowProgress")))
