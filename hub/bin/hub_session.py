"""hub_session.py — 세션 사실을 표시 상태로 판정하는 순수 로직.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_session.py 대상).
`now_ms` 는 항상 인자로 받는다 — 테스트가 시계에 의존하지 않게 하기 위해서다.
상태 판정 규칙의 근거는 docs/prps/hub-dashboard.md 「상태 판정 규칙」 절이 정본이며,
좀비 서브에이전트 가드는 docs/prps/hub-zombie-subagent-guard.md, 세션 부활 규칙은
docs/prps/hub-session-revival-and-stale-tier1.md, 사용량 한도로 끊긴 턴의 표시(interrupted
오버레이)는 docs/prps/hub-rate-limit-interruption.md(결정 RI1~RI13), 백그라운드 작업을
기다리며 멈춘 세션의 표시(background 오버레이)는 docs/prps/hub-subagent-background-pause.md
(결정 BW1~BW12)가 정본이다.

훅 이벤트를 세션 사실(SessionFacts)로 접는 절반은 hub_session_facts.py 로 분리됐다(결정
RI13 의 에스컬레이션을 이행한 M1, docs/prps/hub-subagent-background-pause.md 결정 BW11) —
이 모듈은 그 결과를 받아 표시 상태로 판정만 한다. 두 모듈의 계약은 `SessionFacts` 하나다.
"""

from dataclasses import dataclass
from typing import Literal, Mapping

from hub_activity import BackgroundOutputView, LiveActivity, SubagentActivity, with_stall_suspect_at
from hub_live_session import LiveSessionIndex, RosterState, roster_state_for_session
from hub_parse import Tier1Snapshot
from hub_session_facts import BackgroundReport, SessionFacts, SubagentFact
from hub_subagent import SUBAGENT_RUN_MAX_PER_SESSION, SubagentMeta, clip_metadata
from hub_transcript import SessionModel, TranscriptTurnFailure
from hub_usage import SessionCost
from hub_workflow import WorkflowRunView

SessionState = Literal["working", "idle", "stale", "done", "interrupted", "background"]
Phase = Literal["설계", "구현", "검수"]

# RI6 — 한도 초과만 interrupted 로 승격한다. 다른 API 오류(server_error·invalid_request·
# authentication_failed 등)의 메인 StopFailure 는 턴을 닫기만 한다(→ 대기) — Stop 대신 오는
# 훅을 Stop 과 같게 접는 것이라 범위 확장이 아니라 같은 결함(턴 고착)의 수정이다.
INTERRUPTING_ERROR_KINDS: frozenset[str] = frozenset({"rate_limit"})

SHORT_ID_LENGTH = 8

PHASE_BY_AGENT_TYPE: dict[str, Phase] = {
    "design-architect": "설계",
    "implementer": "구현",
    "code-reviewer": "검수",
}


@dataclass(frozen=True)
class SessionInterruption:
    """「한도 초과」 표시의 근거(결정 RI8). 정적 값만 — 초기화 경과 판정은 클라이언트 몫
    (D2 — snapshot_content_key 안정)."""

    interrupted_at_ms: int          # transcript 오류 줄 시각, 없으면 StopFailure 훅 시각
    resets_at_ms: int | None        # transcript quotaLimits.resetsAt. 없으면 None


@dataclass(frozen=True)
class BackgroundWait:
    """「백그라운드 대기」 표시의 근거(결정 BW9, docs/prps/hub-subagent-background-pause.md).
    정적 값만 — 경과 판정은 클라이언트 몫(D2 — snapshot_content_key 안정). 개정(결정 LA11): `output` 은 파일 stat 의
    함수다 — 지금 시각이 아니라 파일 상태가 같으면 같은 값이라 D2 를 깨지 않는다."""

    since_ms: int          # 보고한 Stop/SubagentStop 시각
    until_ms: int          # since_ms + 상한 — 이 시각까지 소식이 없으면 표시를 거둔다
    task_count: int        # WAKING_BACKGROUND_TASK_TYPES 에 드는 진행 중 작업 수
    wakeup_count: int      # 1회성 예약 깨우기(session_crons 중 recurring:false) 수
    # 백그라운드 작업 출력 파일의 stat 요약(결정 LA10) — 찾지 못했으면 None. 맨 뒤·기본값이라 기존 생성 지점이 무해하다.
    output: BackgroundOutputView | None = None


# ---- 표시(view) ----
@dataclass(frozen=True)
class SubagentRunView:
    """세션에서 실행된 서브에이전트 **1건**의 표시 상태(결정 AR4 — 타입 합계에서 실행 단위로,
    docs/prps/hub-agent-runs-and-prompt-source.md).

    개정 전에는 같은 agent_type 의 여러 실행을 하나로 합친 뷰였다. 합치면 "검수 3회"가
    화면에서 1회와 구별되지 않는다(이 PRP 의 출발점).
    """

    agent_id: str              # 훅 `ai` == meta.json 파일명의 agentId. 정렬 타이브레이커(AR5). 32자 상한(AR10)
    agent_type: str            # 훅 원문(없으면 meta.json). 32자 상한(AR10)
    phase: Phase | None        # PHASE_BY_AGENT_TYPE 에 없으면 None → 칩이 agent_type 으로 폴백(AR8)
    # "지금 돌고 있다고 볼 수 있으면"(is_running_subagent) True. 좀비(SUBAGENT_ZOMBIE_AFTER_MS
    # 초과 미종료)는 여기서도 False — 상태 판정과 같은 술어를 쓰므로 카드 상태와 어긋날 수
    # 없다(결정 ZG4, docs/prps/hub-zombie-subagent-guard.md).
    is_running: bool
    started_at_ms: int          # meta.json mtime, 없으면 훅 SubagentStart(AR7). **정적 — D2 안전**
    ended_at_ms: int | None     # 훅 SubagentStop. 미종료면 None. **정적 — D2 안전**
    title: str | None           # meta.description(스크럽+상한). 없으면 None → 화면은 agent_type 폴백(AR9)
    model: str | None           # meta.model 별칭. 없으면 None(실측 18.7%)
    # 이 실행이 지금 보이는 작업의 경계보다 먼저 시작됐는가(결정 RL2·RL8 — PT1 번복,
    # docs/prps/hub-card-gate-and-run-list-reset.md §3). 경계는 previous_task_boundary_ms
    # (순수 함수)가 유도하고, compute_session_view 가 tier1 유무와 무관하게 항상 넘긴다 —
    # 옛 FT 게이트(PT1·PT6)는 폐지됐다. ProjectView.
    # tier1_is_previous_task(프로젝트 세대 판정)와 어휘를 공유하되 담체가 실행 1건이라
    # 접두 tier1_ 을 붙이지 않는다. 이 클래스의 필드 순서를 무는 검사는 없다(T25-150 이
    # 무는 것은 SessionView 다) — 맨 뒤에 기본값과 함께 둔다.
    is_previous_task: bool = False
    # 재개된 실행이면 마지막 재개 요청(SendMessage)의 요약 — 계약 A. 없으면 None → 화면은 title 로 폴백한다(결정 TF11·TF12,
    # docs/prps/hub-agent-title-and-excerpt-freshness.md). title 의 뜻(meta.description)은 그대로다(AR9). **정적 — D2 안전**
    resume_title: str | None = None
    # 같은 agent_id 의 SubagentStart 재발화 수(결정 TF7). 화면 툴팁의 「재개 N회」. **정적 — D2 안전**
    resume_count: int = 0
    # 도는 실행의 활동 — 도구 종류·기록 시각·개수만(결정 LA3~LA9, docs/prps/hub-live-activity.md). is_running 일 때만
    # 채워진다. **파일 내용의 함수 — 지금 시각이 아니다(D2 안전).** 맨 뒤·기본값이라 기존 생성 지점이 무해하다.
    activity: SubagentActivity | None = None


@dataclass(frozen=True)
class SessionView:
    """세션 사실로부터 판정한 화면 표시 상태."""

    session_id: str
    short_id: str
    # 세션 시작 시각(정적). 화면은 절대 시각(HH:MM 또는 M/D HH:MM)으로 그린다 — 실측에서
    # 발췌·칩·배지가 전부 같은 카드(daily-brief 표시 9개)를 유일하게 갈라낸 값이다
    # (요구 3, docs/prps/hub-collect-on-demand-and-readability.md §4).
    # **기본값을 두지 않는다**(결정 WT19 와 같은 이유 — 정체성 필드가 조용히 0 으로 채워지면
    # 화면에 1970년이 뜨고 그 원인을 추적할 수 없다).
    # 파생값(경과 시간 등)을 여기 넣지 않는다: snapshot_content_key 가 collected_at_ms 만
    # 제외하므로, "지금" 파생값은 매 수집마다 키를 바꿔 hub.html 쓰기 억제를 무력화한다.
    started_at_ms: int
    state: SessionState
    base_state: Literal["working", "idle", "done"]
    last_event_at_ms: int
    task_excerpt: str | None
    agent_runs: tuple[SubagentRunView, ...]
    # 이 세션이 발행한 자기 대시보드의 진행 스냅샷과 서빙 키(결정 ST12,
    # docs/prps/hub-session-tree-and-per-session-dashboards.md). ProjectView 의 tier1·
    # dashboard_key 쌍(hub_project.py)과 같은 모양이라 템플릿이 같은 렌더 함수를 쓴다.
    # 정체성 필드가 아니라 정당하게 부재할 수 있는 부가 정보이므로 model 과 같은 계열
    # (기본값 None)이다.
    tier1: Tier1Snapshot | None = None
    dashboard_key: str | None = None
    # 세션이 마지막으로 쓴 모델·effort(요구 2, docs/prps/hub-tier1-clamp-fix-and-session-model.md
    # 결정 MD7). started_at_ms 의 "정체성 필드에 기본값을 두지 않는다"는 관례는 여기 적용되지
    # 않는다 — 모델은 정체성 필드가 아니라 정당하게 부재할 수 있는 부가 정보다(transcript가
    # 없는 비대화형 세션이 실측 다수). dashboard_key·tier1_is_previous_task 와 같은 계열로
    # 취급한다. dataclass 규칙은 tier1·dashboard_key(둘 다 기본값 있음) 뒤 어디에 둬도
    # 만족되므로 맨 뒤 배치 자체를 강제하지 않는다 — 실제로 맨 뒤를 강제하는 것은
    # T25-150(GOTCHA 8)이 `dataclasses.fields(SessionView)[-1].name == "model"` 을 고정
    # 검사하기 때문이다(검수 2회차 B-10).
    model: SessionModel | None = None
    # 이 세션의 최신 워크플로우 실행(결정 WF1). model 과 같은 계열이다 — 이 함수가 계산하지
    # 않고(파일 읽기는 I/O), 정당하게 부재할 수 있는 부가 정보이므로 기본값 None 을 둔다
    # (started_at_ms 의 "정체성 필드에 기본값 금지" 관례는 적용되지 않는다).
    workflow: WorkflowRunView | None = None
    # 이 세션이 발행한 자기 대시보드가 끝난 작업의 것인가(결정 FT1·FT7,
    # docs/prps/hub-ui-4-issues.md §5). tier1 이 없으면 항상 False. ProjectView.
    # tier1_is_previous_task 와 **다른 판정**이다 — 그쪽은 다른 세션이 남긴 대시보드를
    # 겨냥한 프로젝트 수준 장치다(is_session_tier1_from_finished_task docstring 참조).
    # model·workflow 와 같은 계열의 부가 정보라 기본값을 둔다. tier1_is_finished_task 는
    # 더 이상 맨 뒤가 아니다 — 존재만 확인되면 된다(아래 interruption 이 새 맨 뒤).
    tier1_is_finished_task: bool = False
    # 지금 작업이 시작된 시각 — 세션 줄 첫 줄의 「작업 시작부터 소요」의 시작점(결정 LM11,
    # docs/prps/hub-session-row-layout-and-modal-size.md). 같은 세션에서 다른 작업을 시작하면
    # 이 값이 새 시작 시각으로 바뀐다. previous_task_boundary_ms 가 정한 경계를 쓰고, 그 값이
    # 없으면(대시보드를 껐을 때 등) 마지막 **사람 입력** 시각(훅의 프롬프트 시각이 아니다 —
    # 알림에도 발화한다), 그것도 없으면 None 이다(화면은 세션 시작으로 되돌아간다). 값은 세션 시작(`started_at_ms`)보다 앞서지 않는다 —
    # 끝나지 않은 옛 대시보드 파일 대비(`_clamp_to_session_start`, LM11 개정). **정적 정수 — 지금 파생값이 아니라 snapshot_content_key 에 안전하다.**
    # model·workflow·tier1_is_finished_task 와 같은 계열의 부가 정보라 기본값을 둔다.
    task_started_at_ms: int | None = None
    # 「한도 초과」 표시의 근거(결정 RI8). `effective_interruption` 이 계산하고, 불변식
    # `interruption is not None ⇔ state == "interrupted"` 를 compute_session_view 가
    # 강제한다(테스트 I12). model·workflow·tier1_is_finished_task 와 같은 계열의 부가
    # 정보라 기본값을 둔다. 더 이상 맨 뒤가 아니다 — 존재만 확인되면 된다(아래
    # background_wait 가 새 맨 뒤).
    interruption: SessionInterruption | None = None
    # 「백그라운드 대기」 표시의 근거(결정 BW9) — `effective_background_wait` 가 계산하고,
    # 불변식 `background_wait is not None ⇔ state == "background"` 를 compute_session_view
    # 가 강제한다(RI8 의 `interruption` 되접기와 같은 모양). interruption 과 같은 계열의
    # 부가 정보라 기본값을 둔다. 더 이상 맨 뒤가 아니다 — 존재만 확인되면 된다(아래
    # session_cost 가 새 맨 뒤).
    background_wait: BackgroundWait | None = None
    # 승인 대기 표지·macOS 알림의 단일 판정(결정 MN5, docs/prps/hub-macos-notification.md) — `is_awaiting_approval` 이
    # state·base_state·tier1 로 계산한다. 이미 실린 필드의 함수라 「지금」 파생값이 아니다(snapshot_content_key 안전).
    # 맨 뒤가 아니다 — 맨 뒤는 T25-150 이 무는 session_cost.
    is_awaiting_approval: bool = False
    # statusLine 이 알려 준 이 세션의 누적 비용·API 시간·컨텍스트 사용률(⑨, docs/prps/
    # harness-benchmark-adoption.md). 이 함수가 계산하지 않는다 — hub_collect 가 캡처 파일에서 읽어
    # 넘긴다(statusLine 을 켜지 않았거나 이 세션의 캡처가 없으면 None — 정당한 부재). 값은 파일 내용의
    # 함수라 「지금」 파생값이 아니다(snapshot_content_key 는 값이 실제로 바뀔 때만 바뀐다). 상태 판정에는
    # 쓰이지 않는다. **반드시 맨 뒤** — T25-150 이 dataclasses.fields(SessionView)[-1].name 을 고정 검사한다
    # (model→workflow→tier1_is_finished_task→interruption→background_wait→session_cost 로 이어지는 선례).
    session_cost: SessionCost | None = None


# ---- 세션 표시 상태 ----
# 서브에이전트가 API 오류 등으로 죽으면 SubagentStop 훅이 발화하지 않는다(실측 E1·E5 — 3일간
# 고아 18건, docs/prps/hub-zombie-subagent-guard.md). 그 좀비 1건이 세션을 영구히 working 으로
# 붙잡는 것을 막는 나이 상한이다. 90분의 근거: 3일간 완료된 정상 실행 90건의 최장이 47.3분
# (p90 18.4분)이며, 90분은 그 1.9배다(결정 ZG2 의 표). 상한을 넘긴 실행은 "죽었다"가 아니라
# "지금 돌고 있다는 근거가 없다"로 본다.
SUBAGENT_ZOMBIE_AFTER_MS = 90 * 60 * 1000

# SUBAGENT_RUN_MAX_PER_SESSION(세션당 실행 뷰 개수 상한, 결정 AR11)은 hub_subagent.py 에
# 있다(재검수 1회차 L1) — 상수는 파서 모듈에 둔다는 그 모듈의 관례를 따른다. 이 모듈은
# summarize_agent_runs 의 표시 절단에 그 값을 그대로 쓴다(위 import).

# 깨우는 종류(결정 BW4, docs/prps/hub-subagent-background-pause.md) — 호스트가 "제
# 백그라운드 작업이 남은 채 멈췄다"고 판정하는 keepalive 사유(bash:·monitor:·workflow:,
# §1.3-5)와 같은 집합이다. subagent·teammate 는 훅이 이미 실행(S)으로 추적하므로 빼면
# 이중 계산이고, 서브에이전트 자신의 SubagentStop 배열에 자기 자신이 섞이는 문제(U3)도
# 피한다. dream·auto_mode_scan(호스트 내부 ambient 작업)·cloud_session·mcp_task·unknown 은
# 깨움 경로가 확인되지 않아 제외한다(페일오픈 — 오늘과 같은 방향).
WAKING_BACKGROUND_TASK_TYPES: frozenset[str] = frozenset({"shell", "monitor", "workflow"})

# 「백그라운드 대기」 표시를 믿는 상한(결정 BW6). 근거: 조용한 공백 25건(§1.2)의 최장
# 40.1분의 2.2배 — SUBAGENT_ZOMBIE_AFTER_MS(위, ZG2: 최장 정상 실행 47.3분의 1.9배)와 같은
# 증거 지평이다. 두 상수는 따로 둔다 — 근거 표본이 달라 하나가 바뀌어도 다른 하나가 딸려
# 가지 않게 한다.
BACKGROUND_WAIT_MAX_MS = 90 * 60 * 1000


def waking_background_task_count(report: BackgroundReport | None) -> int:
    """보고가 말하는 진행 중 작업 중 세션을 깨우는 종류(WAKING_BACKGROUND_TASK_TYPES)의 수. 보고가 없으면 0.

    `effective_background_wait` 의 합산식을 그대로 뽑은 것이다 — 「백그라운드 대기」 판정과 출력 파일 읽기 게이트
    (`is_background_output_scan_target`)가 같은 식을 쓰게 한다(결정 LA7, docs/prps/hub-live-activity.md)."""
    if report is None:
        return 0
    return sum(count for task_type, count in report.task_counts if task_type in WAKING_BACKGROUND_TASK_TYPES)


def is_background_output_scan_target(
    facts: SessionFacts, now_ms: int, max_age_ms: int = BACKGROUND_WAIT_MAX_MS,
) -> bool:
    """이 세션의 백그라운드 작업 출력 파일을 찾으러 기록을 열 가치가 있는가(결정 LA7 게이트, 순수).

    보고가 있고, 깨우는 작업 수 또는 1회성 예약 수가 0 보다 크고, 보고 뒤 `max_age_ms` 가 지나지 않았을 때만 참이다
    (경계는 `>=` 만료 — `effective_background_wait` 와 같다). 명부(roster)는 섞지 않는다 — 판정이 아니라 읽기 범위
    결정이고, 결과는 `state == "background"` 일 때만 뷰에 남는다(BW9 불변식 그대로)."""
    report = facts.background_report
    if report is None or now_ms - report.reported_at_ms >= max_age_ms:
        return False
    return waking_background_task_count(report) > 0 or report.wakeup_count > 0


def effective_background_wait(
    facts: SessionFacts, now_ms: int, roster: RosterState,
    max_age_ms: int = BACKGROUND_WAIT_MAX_MS,
    output: BackgroundOutputView | None = None,
) -> BackgroundWait | None:
    """세션을 "백그라운드 작업이 깨워 주기를 기다리며 멈춘" 상태로 볼 근거(BW4·BW6).

    보고가 없거나, 명부가 `not_listed`(취소, RI4 와 같은 방향 — 프로세스가 없으면 이어서
    지시할 세션 자체가 없다)거나, 마지막 보고로부터 `max_age_ms` 이상 지났거나(경계는
    `>=` — `is_running_subagent` 의 `<` 관례와 대응하는 반대쪽), 깨우는 작업·1회성 예약이
    모두 0 이면(끝나지 않는 dev 서버 등록 종류가 아니라 진짜로 기다릴 것이 없는 경우) None. `output` 은 I/O 층이
    찾은 출력 파일 요약이며(결정 LA7) 판정에 쓰이지 않고 그대로 싣기만 한다."""
    report = facts.background_report
    if report is None or roster == "not_listed":
        return None
    if now_ms - report.reported_at_ms >= max_age_ms:
        return None
    task_count = waking_background_task_count(report)
    if task_count == 0 and report.wakeup_count == 0:
        return None
    return BackgroundWait(
        since_ms=report.reported_at_ms,
        until_ms=report.reported_at_ms + max_age_ms,
        task_count=task_count,
        wakeup_count=report.wakeup_count,
        output=output,
    )


def is_running_subagent(
    subagent: SubagentFact,
    now_ms: int,
    zombie_after_ms: int,
    last_activity_at_ms: int | None = None,
) -> bool:
    """지금 실제로 돌고 있다고 볼 수 있는 실행인가 — 이미 끝났거나 좀비면 False.

    판정은 **덧셈**이다(결정 SL2) — 시작 시각 기준(오늘의 규칙, 한 글자도 바뀌지 않는다)
    또는 transcript 마지막 기록 시각 기준 중 하나라도 살아 있으면 True 다. 단조적이라
    `last_activity_at_ms=None`(기본값 — transcript 부재·stat 실패·구버전 호스트)이면
    오늘의 판정 그대로다.
    """
    if subagent.ended_at_ms is not None:
        return False
    if (now_ms - subagent.started_at_ms) < zombie_after_ms:
        return True
    return last_activity_at_ms is not None and (now_ms - last_activity_at_ms) < zombie_after_ms


# `done` = `SessionEnd` 를 관측했고, 그 뒤로 재부착(`SessionStart`, compact 제외)을 보지
# 못했다(결정 RV3, docs/prps/hub-session-revival-and-stale-tier1.md). `done` 은 여전히
# `stale` 로 덮이지 않는 터미널 표시이지만, 터미널인 것은 표시일 뿐 사실이 아니다 — 세션은
# 되살아날 수 있고, 되살아나면 `done` 은 취소된다(_apply_tracked_event 의 SessionStart 분기가
# ended_at_ms 를 해제한다).
#
# `working` = 메인 턴이 진행 중이거나(`turn_state == "running"`), 또는 `SubagentStop` 없이
# 시작 후 `SUBAGENT_ZOMBIE_AFTER_MS`(90분) 이내인 서브에이전트가 하나라도 있다(결정 ZG7). 90분을
# 넘긴 미종료 실행은 실행 근거에서 제외한다 — 죽었다고 단정하는 것이 아니라, 지금 돌고 있다는
# 근거로 인정하지 않는다는 뜻이다. 같은 술어가 서브에이전트 칩의 `is_running` 도 결정하므로,
# 상태와 칩은 어긋날 수 없다.
#
# `roster`(결정 LS3 의 5값)가 이 사다리를 화해시킨다(결정 LS5, docs/prps/
# hub-live-session-native-source.md) — 호스트의 살아있는 세션 명부가 훅 사실과 어긋날 때 누가
# 이기는지의 표다. 필수 인자다(기본값 없음) — 유일 호출자 compute_session_view 가 항상
# roster_state_for_session 의 결과를 명시적으로 계산해 넘기므로, 기본값을 두면 호출부가
# 하나뿐이라 도달 불가능한 죽은 코드가 된다(재검수 1회차 M2). "unknown"(명부가 이 세션에
# 대해 말해 주는 것이 없을 때)이 **오늘의 판정과 완전히 같은** 것은 아래 마지막 분기 자체가
# 이 함수의 원래 본문 그대로이기 때문이다.
#
# | roster       | 판정                                      | 근거 |
# |--------------|-------------------------------------------|------|
# | busy         | working (E 무시)                           | 호스트 status 가 turn_state 를 대체한다 |
# | idle         | S→working / else idle (E 무시)             | status 가 T 를 대체 — S 만 ZG7 로 살아 있다 |
# | listed       | (T∨S)→working / else idle, E 무시          | 생존만 확인, busy/idle 은 모름 — 부활만 추가 |
# | not_listed   | E→done / else idle (T·S 무시)              | 죽은 프로세스는 턴도 서브에이전트도 못 돌린다 |
# | unknown      | E→done / (T∨S)→working / else idle        | 오늘의 판정과 완전 동일(무동작, 결정 LS7) |
def _compute_base_state(
    facts: SessionFacts, now_ms: int, zombie_after_ms: int, roster: RosterState,
    subagent_activity_by_agent_id: dict[str, int] | None = None,
) -> Literal["working", "idle", "done"]:
    subagent_activity_by_agent_id = subagent_activity_by_agent_id or {}
    has_running_subagent = any(
        is_running_subagent(sub, now_ms, zombie_after_ms, subagent_activity_by_agent_id.get(sub.agent_id))
        for sub in facts.subagents
    )
    if roster == "busy":
        return "working"
    if roster == "idle":
        return "working" if has_running_subagent else "idle"
    if roster == "listed":
        return "working" if (facts.turn_state == "running" or has_running_subagent) else "idle"
    if roster == "not_listed":
        return "done" if facts.ended_at_ms is not None else "idle"
    # roster == "unknown" — 오늘의 판정과 완전 동일(무동작, 결정 LS7의 폴백 경로)
    if facts.ended_at_ms is not None:
        return "done"
    if facts.turn_state == "running" or has_running_subagent:
        return "working"
    return "idle"


def effective_interruption(
    facts: SessionFacts, transcript_turn_failure: TranscriptTurnFailure | None
) -> SessionInterruption | None:
    """메인 턴이 한도 오류로 끝났고 그 뒤 새 프롬프트가 없는가 — 두 관측의 OR(결정 RI1·
    RI4·RI6).

    `hook`(훅 사실)은 `facts.failed_turn` 이 있고 그 `error_kind` 가 `INTERRUPTING_ERROR_KINDS`
    일 때만 산다. `tail`(transcript 사실)은 `transcript_turn_failure` 가 있고 같은 종류
    제한을 통과하며, **그 뒤 새 프롬프트가 없을 때만**(`last_prompt_at_ms` 가 없거나
    `failed_at_ms ≥ last_prompt_at_ms`) 산다 — 오류 뒤 사용자가 이미 다시 지시했다면 그
    transcript 관측은 낡은 것이다(R2). 둘 다 없으면 None. 시각은 `tail` 이 있으면 그 값을
    우선한다(결정적 — snapshot_content_key 안정), 초기화 시각은 `tail` 에만 있다.
    """
    hook = facts.failed_turn
    if hook is not None and hook.error_kind not in INTERRUPTING_ERROR_KINDS:
        hook = None
    tail = transcript_turn_failure
    if tail is not None:
        turn_resumed = facts.last_prompt_at_ms is not None and tail.failed_at_ms < facts.last_prompt_at_ms
        if tail.error_kind not in INTERRUPTING_ERROR_KINDS or turn_resumed:
            tail = None
    if hook is None and tail is None:
        return None
    winner = tail if tail is not None else hook
    return SessionInterruption(
        interrupted_at_ms=winner.failed_at_ms,
        resets_at_ms=tail.resets_at_ms if tail is not None else None,
    )


def _display_state(
    base_state: Literal["working", "idle", "done"],
    interruption: SessionInterruption | None,
    background_wait: BackgroundWait | None,
    roster: RosterState,
    is_stale: bool,
) -> SessionState:
    """표시 사다리(결정 RI2·BW5) — done > interrupted > background(base idle 일 때) >
    stale > base_state 순 오버레이.

    `interrupted` 는 `stale` 보다 앞선다 — 30분 무소식 오버레이가 한도로 멈춘 사실을
    가리면(초기화 시각이 stale 판정 창보다 뒤일 수 있다) 사용자가 판단할 정보를 잃는다.
    `roster == "not_listed"` 면 취소된다(RI4 — 프로세스가 없으면 이어서 지시할 세션 자체가
    없다). `base_state == "done"` 은 그 무엇보다 먼저 이긴다 — 세션이 실제로 끝났다는
    사실(SessionEnd)이 턴 하나의 결과보다 강하다.

    `background` 는 `base_state == "idle"` 일 때만 stale 보다 앞서 끼어든다(결정 BW5) —
    `_compute_base_state`(working/idle/done 3값, 한 글자도 바뀌지 않는다)를 덧칠하는
    오버레이일 뿐, 새 base_state 값을 만들지 않는다. `is_stale`(LS9·SL4, 계산식 무변경)이
    상한(BACKGROUND_WAIT_MAX_MS) 안에서는 뒤집히지 않는 지점이 §1.2 의 7/25 건이 고쳐지는
    자리다.
    """
    if base_state == "done":
        return "done"
    if interruption is not None and roster != "not_listed":
        return "interrupted"
    if base_state == "idle" and background_wait is not None:
        return "background"
    if is_stale:
        return "stale"
    return base_state


def is_awaiting_approval(
    state: SessionState,
    base_state: Literal["working", "idle", "done"],
    tier1: Tier1Snapshot | None,
) -> bool:
    """승인 대기 표지·알림의 단일 판정(결정 MN5 — AW1 규칙): 승인 단계 진행중 ∧ base idle ∧ 한도 초과 아님.

    「사용자 차례인가」는 표시 상태(stale 이 가린다)가 아니라 그 아래 base_state 가 답한다 — 그래서 대기·백그라운드 대기·
    소식 없음(직전 대기)에서 True 이고, 작업중·소식 없음(직전 작업중)·한도 초과·완료·사실 꺼짐·진행 기록 없음에서 False 다.
    """
    if tier1 is None or not tier1.is_approval_step_active:
        return False
    return base_state == "idle" and state != "interrupted"


# 대시보드가 「끝났다」고 볼 진행률(결정 FT1, docs/prps/hub-ui-4-issues.md §5).
# hub/README.md 「진행 기록」 데이터 모델 표의 `pass` = 전부 완료(100%)가 이 값의 출처다 —
# 대시보드 파일에는 완료/종료 상태 필드가 없어서 진행률이 유일한 관측 가능 종료 신호다.
TIER1_FINISHED_PERCENT = 100


def is_session_tier1_from_finished_task(
    tier1_percent: int, tier1_file_mtime_ms: int, last_event_at_ms: int, stale_after_ms: int
) -> bool:
    """세션이 발행한 자기 대시보드가 **끝난 작업**의 것인가(결정 FT1).

    두 연접의 역할이 다르다. `tier1_percent >= 100` 은 「그 대시보드가 기록한 작업이
    끝났다」를 말한다 — `hub/README.md` 「진행 기록」 데이터 모델 표가 `pass` = 전부
    완료(100%)로 정의한 그 종료 신호다(대시보드 파일에는 별도의 완료/종료 필드가
    없다). Δ 조건은 「세션이 그 뒤로도 일했다」를 말한다.

    `is_tier1_from_previous_task`(위)와 별개 함수인 이유: 그 함수는 *다른* 세션이 남긴
    대시보드를 겨냥해 살아 있는 세션들의 **시작 시각**을 `all()` 로 본다. 사용자 케이스는
    *같은* 세션이 발행한 것이라 시작 시각 < 파일 mtime 이 되어 그 판정은 **항상 False** 다
    (실측: 스냅샷의 6개 프로젝트 전부 False). 여기서 보는 것은 **마지막 이벤트** 시각이다.

    임계값은 새 상수를 만들지 않고 `stale_after_ms` 를 재사용한다(결정 FT2) — 허브의
    `stale_after_minutes`·클라이언트 STALE_AFTER_MINUTES 가 이미 공유하는 값이다. 둘 다
    세션이 「지금 쓰이는 중인가」를 가르는 문턱이고, 이 함수는 같은 물음을 대시보드에 던진다.

    경계는 엄격한 `>` 다(`is_tier1_from_previous_task` 와 같은 관례 — 오탐 회피 방향).
    `percent >= 100` 연접은 오탐 방어 장치다: 진행 중인 대시보드는 100% 가 아니므로,
    긴 서브에이전트 실행으로 Δ 가 임계값을 넘는 구간에서도 판정이 켜지지 않는다. 그 대가로
    「중간에 방치된 대시보드」는 검출하지 않는다(결정 FT3 — 의도된 미검출).
    """
    if tier1_percent < TIER1_FINISHED_PERCENT:
        return False
    return last_event_at_ms - tier1_file_mtime_ms > stale_after_ms


def previous_task_boundary_ms(
    tier1: Tier1Snapshot | None,
    last_prompt_at_ms: int | None,
    is_dashboard_enabled: bool,
) -> int | None:
    """실행 목록의 작업 경계(결정 RL8·RL10, docs/prps/hub-card-gate-and-run-list-reset.md
    §3.7). 순수 — 파일·시각에 닿지 않는다. `None`이면 아무 실행도 숨기지 않는다(페일오픈,
    결정 RL4).

    네 갈래:
    (a) 작업이 진행 중이면(`tier1.percent < TIER1_FINISHED_PERCENT`) 경계 = 그 작업의
        시작 시각(`task_started_at_ms`) — 그 작업에 속한 실행은 몇 번의 프롬프트를 거쳐도
        전부 남는다(반례 B).
    (b) 작업이 끝났으면 경계 = `max(작업 시작, 마지막 프롬프트)` — 끝난 작업 뒤의 새 질의가
        경계를 즉시 앞으로 당겨 목록을 비운다(결함 1-(b) 해결, 30분 대기 소멸).

    `last_prompt_at_ms` 는 **마지막 사람 입력 시각**이다(호출부 compute_session_view 가 transcript 꼬리에서 읽은
    값을 넘긴다) — 훅 시각이 아니다. 알림·서브에이전트 보고도 훅을 발화시켜 경계를 밀기 때문이다. None 이면
    프롬프트가 경계에 쓰이지 않는다.
    (c) 작업 시작 시각을 모르면(`tier1` 이 없거나 그 `task_started_at_ms` 가 없으면) 대시보드가
        켜져 있는 한 경계 = 마지막 프롬프트 — 대시보드 파일이 사라진 경우의 폴백(반례 A).
    (d) 대시보드를 껐으면(`is_dashboard_enabled=False`) 경계 없음 — 작업 단위의 유일한
        선언자(기록기 `init`)를 사용자가 스스로 껐으므로 프롬프트로 경계를 추측하지
        않는다(그 추측이 정확히 반려된 RL6 이다).
    """
    if tier1 is None or tier1.task_started_at_ms is None:
        if not is_dashboard_enabled:
            return None                                             # (d) RL10 — 선언자가 없다
        return last_prompt_at_ms                                     # (c) 폴백
    if tier1.percent >= TIER1_FINISHED_PERCENT:
        if last_prompt_at_ms is None:
            return tier1.task_started_at_ms
        return max(tier1.task_started_at_ms, last_prompt_at_ms)      # (b) 끝난 작업
    return tier1.task_started_at_ms                                  # (a) 진행 중


def _clamp_to_session_start(candidate_ms: int | None, session_started_at_ms: int) -> int | None:
    """작업 시작 후보를 세션 시작보다 앞서지 않게 한다(결정 LM11 개정). 후보가 None 이면 None 그대로다.

    왜: 끝나지 않은 채 남은 옛 대시보드 파일의 init 시각은 이 세션이 생기기 전일 수 있다 — 세션 안에서 시작한
    작업이 세션보다 오래될 수는 없다. 세션 시작(`facts.started_at_ms`)은 이벤트 창에서 이 세션의 첫 훅 이벤트
    시각이다. 세션을 이어받은 경우에도 이어받은 시점부터 센다(수용된 차이). 실행 목록 경계에는 쓰지 않는다.
    """
    if candidate_ms is None:
        return None
    return max(candidate_ms, session_started_at_ms)


def compute_session_view(
    facts: SessionFacts,
    now_ms: int,
    stale_after_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,
    model: SessionModel | None = None,
    tier1: Tier1Snapshot | None = None,
    dashboard_key: str | None = None,
    workflow: WorkflowRunView | None = None,
    task_excerpt: str | None = None,
    subagent_meta_by_agent_id: dict[str, SubagentMeta] | None = None,
    subagent_activity_by_agent_id: dict[str, int] | None = None,
    is_dashboard_enabled: bool = True,
    live_roster: LiveSessionIndex | None = None,
    transcript_turn_failure: TranscriptTurnFailure | None = None,
    live_activity: LiveActivity | None = None,
    last_human_prompt_at_ms: int | None = None,
    session_cost: SessionCost | None = None,
) -> SessionView:
    """우선순위 사다리(done > interrupted > background > stale > base_state, 결정 RI2·BW5 —
    `_display_state` 참조)로 표시 상태를 정한다.

    `model`·`workflow`·`tier1`·`dashboard_key`·`task_excerpt`·`subagent_meta_by_agent_id` 는
    이 함수가 계산하지 않는다 — 전부 I/O 라 호출자(hub_collect.py·hub_project.py)가 미리
    읽어 넘기고 여기서는 실어 나르기만 한다(결정 WF1·ST12·PS3). 기본값 None 이라 기존
    호출부는 무해하다.

    `transcript_turn_failure` 도 I/O 산출물이다(결정 RI1) — hub_collect.read_session_tail 이
    미리 읽어 `SessionTail.turn_failure` 로 넘긴 값을 그대로 받는다. `effective_interruption`
    이 훅 사실(`facts.failed_turn`)과 OR 해 `interruption` 을 정하고, `_display_state` 가
    그 결과와 `roster`(명부가 `not_listed` 면 취소)·`is_stale` 을 사다리에 반영한다.

    `subagent_activity_by_agent_id` 도 예외다(결정 SL5, LS10 과 같은 이유) — 미종료
    서브에이전트 실행의 transcript mtime 이며, `live_roster` 처럼 판정에만 쓰고 뷰에는
    싣지 않는다. 초 단위로 갱신되는 값이라 뷰에 실으면 `snapshot_content_key` 가 매
    수집마다 바뀐다(G9).

    `live_roster` 는 예외다 — 다른 보강 인자와 달리 **뷰에 싣지 않고 상태 판정에 쓴다**(결정
    LS4, docs/prps/hub-live-session-native-source.md). `roster_state_for_session` 으로 5값을
    뽑아 `_compute_base_state` 의 화해 표(결정 LS5, 그 함수 정의부 표 참조)에 넘긴다. 기본값
    None → "unknown" 이라 기존 호출부는 무해하다.

    `live_activity` 는 I/O 산출물이다(결정 LA1·LA14, docs/prps/hub-live-activity.md) — hub_subagent_read.
    read_live_activity 가 수집 1회에 읽은 활동 묶음이고, 판단 없이 도는 실행의 `activity`(`summarize_agent_runs`)와
    「백그라운드 대기」의 `output` 으로 실어 나르기만 한다. 상태 사다리는 바꾸지 않는다(결정 LA8). 기본값 None 이라
    기존 호출부는 무해하고 뷰는 오늘과 같다.

    `last_human_prompt_at_ms` 도 I/O 산출물이다 — `SessionTail.last_human_prompt_at_ms`(transcript 꼬리의 마지막
    사람 입력 줄 시각)를 그대로 받는다. 작업 경계(`previous_task_boundary_ms`)와 세션 줄 시작 시각의 폴백에는
    훅의 `facts.last_prompt_at_ms` 가 아니라 이 값을 쓴다 — `UserPromptSubmit` 훅은 백그라운드 완료 알림·서브에이전트
    보고에도 발화해, 끝난 작업의 경계를 알림 시각으로 밀고 세션 줄 시간을 「1분 미만」으로 되돌리기 때문이다.
    None(꼬리에 사람 입력이 없음 — 긴 자율 작업에서는 흔하다)이면 프롬프트를 경계에 쓰지 않는다: (b) 는 작업 시작,
    (c) 는 경계 없음(아무것도 숨기지 않음, 결정 RL4 페일오픈), 시작 시각 폴백은 None 이라 화면이 세션 시작으로
    물러난다. 반면 `effective_interruption` 의 오류 뒤 재개 판정은 훅 값을 그대로 쓴다 — 비사람 입력도 턴을
    되살리는 것이 맞다. 기본값 None 이라 기존 호출부는 무해하다.

    `session_cost` 도 I/O 산출물이다(⑨, docs/prps/harness-benchmark-adoption.md) — hub_session_cost 가 읽은 statusLine 캡처를
    판단 없이 뷰의 같은 이름 필드에 실어 나르기만 한다. 상태 사다리·작업 경계에는 쓰이지 않는다. 기본값 None 이라 기존 호출부는 무해하다.

    `tier1_is_finished_task` 도 예외다(결정 FT1·FT7) — I/O 없이 세 값(tier1.percent·
    tier1.file_mtime_ms·facts.last_event_at_ms)과 이미 받은 stale_after_ms 만으로 끝나는
    순수 계산이라 여기서 직접 판정한다. 소비자는 세션 행 클릭 게이트(FT4)와 프로젝트
    담체로의 승격(CD1)뿐이다 — **실행 목록과는 더 이상 연결되지 않는다**(결정 RL2, PT1
    번복, docs/prps/hub-card-gate-and-run-list-reset.md §3.2). 실행 목록의 경계는
    `previous_task_boundary_ms`(순수 함수, 결정 RL8·RL10)가 대신 유도한다 — tier1 의
    존재·진행 여부와 무관하게 항상 호출하고, 그 결과를 `summarize_agent_runs` 에 그대로
    넘겨 경계 이전에 시작되고 **지금 돌고 있지 않은**(결정 RL3) 실행에만
    `SubagentRunView.is_previous_task` 표시를 남긴다.
    """
    roster = roster_state_for_session(live_roster, facts.session_id)
    base_state = _compute_base_state(facts, now_ms, zombie_after_ms, roster, subagent_activity_by_agent_id)
    # is_stale(결정 LS9·SL4)은 roster 를 섞지 않는다 — 명부 오판의 유일한 독립 상한이다.
    # 기준 시각은 '마지막으로 알려진 활동'(훅 ∪ 미종료 실행 기록)으로 넓어진다(결정 SL4).
    is_stale = base_state != "done" and (now_ms - last_known_activity_at_ms(facts, subagent_activity_by_agent_id)) >= stale_after_ms
    tier1_is_finished_task = tier1 is not None and is_session_tier1_from_finished_task(
        tier1.percent, tier1.file_mtime_ms, facts.last_event_at_ms, stale_after_ms
    )
    # RI8 불변식(테스트 I12): interruption 은 state == "interrupted" 일 때만 싣는다 —
    # roster == "not_listed" 가 취소하거나 base_state == "done" 이 이기면, 계산된 후보가
    # 있어도 None 으로 되접는다.
    interruption_candidate = effective_interruption(facts, transcript_turn_failure)
    # BW9 불변식(테스트 L14): background_wait 는 state == "background" 일 때만 싣는다 —
    # interruption 이 이기거나 base_state 가 idle 이 아니면, 계산된 후보가 있어도 None 으로
    # 되접는다(RI8 의 interruption 되접기와 같은 모양).
    background_output = live_activity.background_output_by_session_id.get(facts.session_id) if live_activity else None
    background_wait_candidate = effective_background_wait(facts, now_ms, roster, output=background_output)
    state = _display_state(base_state, interruption_candidate, background_wait_candidate, roster, is_stale)
    interruption = interruption_candidate if state == "interrupted" else None
    background_wait = background_wait_candidate if state == "background" else None
    task_boundary_ms = previous_task_boundary_ms(tier1, last_human_prompt_at_ms, is_dashboard_enabled)
    agent_runs = summarize_agent_runs(
        facts, now_ms, zombie_after_ms, subagent_meta_by_agent_id,
        task_boundary_ms,
        subagent_activity_by_agent_id,
        live_activity.by_agent_id if live_activity else None,
    )
    task_started_at_ms = _clamp_to_session_start(
        task_boundary_ms if task_boundary_ms is not None else last_human_prompt_at_ms,
        facts.started_at_ms,
    )
    return SessionView(
        session_id=facts.session_id,
        short_id=facts.session_id[:SHORT_ID_LENGTH],
        started_at_ms=facts.started_at_ms,
        state=state,
        base_state=base_state,
        last_event_at_ms=facts.last_event_at_ms,
        task_excerpt=task_excerpt,
        agent_runs=agent_runs,
        tier1=tier1,
        dashboard_key=dashboard_key,
        model=model,
        workflow=workflow,
        tier1_is_finished_task=tier1_is_finished_task,
        task_started_at_ms=task_started_at_ms,
        interruption=interruption,
        background_wait=background_wait,
        is_awaiting_approval=is_awaiting_approval(state, base_state, tier1),
        session_cost=session_cost,
    )


# ---- 서브에이전트 요약 ----
def summarize_agent_runs(
    facts: SessionFacts,
    now_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,
    subagent_meta_by_agent_id: dict[str, SubagentMeta] | None = None,
    previous_task_boundary_ms: int | None = None,
    subagent_activity_by_agent_id: dict[str, int] | None = None,
    activity_by_agent_id: Mapping[str, SubagentActivity] | None = None,
) -> tuple[SubagentRunView, ...]:
    """세션의 서브에이전트 **실행 1건당 뷰 1개**를 만든다(결정 AR4,
    docs/prps/hub-agent-runs-and-prompt-source.md).

    시작 시각은 meta.json mtime 이 있으면 그것을, 없으면 훅 값을 쓴다(결정 AR7 —
    `SubagentFact` 자체는 손대지 않는다). agent_type 은 훅 원문을 우선하고 훅이 비어 있을
    때만 meta.json 값으로 보강한다 — 둘 다 비어 있으면 그 실행은 건너뛴다(빈 줄을 만들지
    않는다). agent_type·agent_id 는 계약 A(AR10)를 소급 적용해 32자 상한을 건다. 제목은
    meta.description, 없으면(또는 빈 문자열이면) None — 화면이 agent_type 으로 폴백한다
    (AR9). 재개된 실행의 제목·횟수(결정 TF11)는 meta.resume_title 과 훅의 resume_count 를
    그대로 별도 필드로 싣는다 — title 의 뜻은 바뀌지 않는다.

    `previous_task_boundary_ms` 가 주어지면(결정 RL8, docs/prps/
    hub-card-gate-and-run-list-reset.md §3) 그 값보다 **엄격히 이전**(`<`)에 시작됐고
    **지금 돌고 있지 않은**(`not is_running`, 결정 RL3 — 실행 중인 실행은 22.7% 가 다음
    프롬프트를 걸치므로 숨기지 않는다) 실행의 `is_previous_task` 를 True 로 채운다 —
    경계는 뷰의 `started_at_ms`(meta 우선, AR7)와 비교하지 훅 원값과 비교하지 않는다.
    `None`이면(기본값) 전부 False — 개수를 잘라내지 않는다(PT3, 표시 정책은 클라이언트의
    몫).

    정렬은 K2 그대로 — 실행 중 우선, 그 다음 최근 시작 내림차순, 동률은 agent_id(결정 AR5,
    snapshot_content_key 결정성). `is_running` 은 `_compute_base_state` 와 같은 술어
    (`is_running_subagent`)를 쓴다 — 좀비는 여기서도 실행 중이 아니다(ZG1·ZG4). meta 는
    보강일 뿐이라 없으면 훅 값만으로 뷰가 만들어진다(AR9). 개수는
    SUBAGENT_RUN_MAX_PER_SESSION 으로 자른다(AR11 — 서버측 직렬화 방어선).

    `activity_by_agent_id`(결정 LA7·LA8)는 `subagent_activity_by_agent_id`(생존 판정용 mtime, 뷰에 싣지 않는다)와 **다른
    통로**다 — 도는 실행(`is_running`)에만 그 활동을 싣고, 「새 기록 없음」 정적 시각을 뷰의 `started_at_ms`(meta 우선,
    AR7)로 채운다. 끝난 실행·좀비는 dict 에 있어도 None 이다.
    """
    subagent_meta_by_agent_id = subagent_meta_by_agent_id or {}
    subagent_activity_by_agent_id = subagent_activity_by_agent_id or {}
    activity_by_agent_id = activity_by_agent_id or {}
    runs = []
    for sub in facts.subagents:
        meta = subagent_meta_by_agent_id.get(sub.agent_id)
        raw_agent_type = sub.agent_type or (meta.agent_type if meta else "")
        if not raw_agent_type:
            continue
        agent_type = clip_metadata(raw_agent_type)
        started_at_ms = meta.started_at_ms if meta else sub.started_at_ms
        is_running = is_running_subagent(sub, now_ms, zombie_after_ms, subagent_activity_by_agent_id.get(sub.agent_id))
        found = activity_by_agent_id.get(sub.agent_id)
        runs.append(SubagentRunView(
            agent_id=clip_metadata(sub.agent_id),
            agent_type=agent_type,
            phase=PHASE_BY_AGENT_TYPE.get(agent_type),
            is_running=is_running,
            started_at_ms=started_at_ms,
            ended_at_ms=sub.ended_at_ms,
            title=(meta.title if meta and meta.title else None),
            model=(meta.model if meta else None),
            is_previous_task=(
                previous_task_boundary_ms is not None
                and started_at_ms < previous_task_boundary_ms
                and not is_running
            ),
            resume_title=(meta.resume_title if meta else None),
            resume_count=sub.resume_count,
            activity=with_stall_suspect_at(found, started_at_ms) if is_running and found is not None else None,
        ))
    ordered = sorted(runs, key=lambda run: (0 if run.is_running else 1, -run.started_at_ms, run.agent_id))
    return tuple(ordered[:SUBAGENT_RUN_MAX_PER_SESSION])


def last_known_activity_at_ms(
    facts: SessionFacts,
    subagent_activity_by_agent_id: dict[str, int] | None = None,
) -> int:
    """stale 판정이 보는 '허브가 이 세션에 대해 아는 가장 새로운 것'의 시각(결정 SL4).

    = max(facts.last_event_at_ms, 미종료 실행들의 마지막 기록 시각들). 살아있는 세션
    명부를 참조하지 않는다 — stale 이 그 명부의 오판에 대한 유일한 독립 상한이라는 결정
    LS9 를 보존한다(T25-224 가 이 함수 본문에 그 명부 관련 식별자가 없음을 기계로
    확인한다).
    """
    activity_by_agent_id = subagent_activity_by_agent_id or {}
    candidates = [facts.last_event_at_ms]
    candidates.extend(
        activity_by_agent_id[sub.agent_id]
        for sub in facts.subagents
        if sub.ended_at_ms is None and sub.agent_id in activity_by_agent_id
    )
    return max(candidates)
