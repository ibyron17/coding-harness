# 허브 실행 목록 초기화 · 카드 대시보드 세대 경고 결함 2건

- 상태: **승인 완료(2026-09-18) — 구현 대기.** 3회차 판정: **RL10 채택**(폴백 = 껐으면 경계 없음 / 켰는데 파일만 없으면 마지막 프롬프트). RL·CG 전 항목 승인됨.
- 개정 이력
  - **1회차**(2026-09-18) — 경계를 마지막 프롬프트로(RL6), 주인 부재 시 카드 클릭 차단(CG2 배선).
    사용자 판정: **RL6 반려**(「보류 — 대안을 더 찾아라」) · **CG2 변경**(「경고만 띄우고 열리게」).
  - **2회차** — 경계를 **대시보드 작업 시작 시각**으로 재유도(RL8 신설, RL6 보존·반려 표기).
    카드 클릭 차단을 철회하고 **카드 경고 표시**로 전환(CG8~CG12 신설, CG4·CG5 철회 표기).
    사용자 판정: **CG 전건 확정** · **RL8-(c) 폴백 보류**(「세 번째 신호를 더 찾아라」).
  - **3회차**(이 문서) — 폴백 대체 신호를 **탐색 공간 전수**로 조사했고 **없다**는 결론에
    도달했다(§1.9~§1.11). 대신 구멍을 **구성 인지로 좁히는** RL10 을 신설한다.
    §4(CG)·§6(UX)은 이번 회차에서 **한 글자도 바뀌지 않았다.**
  - **RL11 개정**(2026-10-08) — RL8-(b)·(c) 의 「마지막 프롬프트」는 훅(`UserPromptSubmit`) 시각이 아니라 transcript 꼬리에서 읽은 **마지막 사람 입력 시각**(`SessionTail.last_human_prompt_at_ms`)이다 — 훅은 백그라운드 완료 알림·서브에이전트 보고에도 발화해 끝난 작업의 경계를 알림 시각으로 밀었다. 꼬리에 사람 입력이 없으면(None) (b) 는 작업 시작, (c) 는 경계 없음(RL4 페일오픈)이다. 오류 뒤 재개 판정은 훅 값을 그대로 쓴다.
- 선행 설계: [`hub-session-list-and-glow-fixes.md`](hub-session-list-and-glow-fixes.md)(FT1~FT7 · PT1~PT7 · CD1~CD7),
  [`hub-session-revival-and-stale-tier1.md`](hub-session-revival-and-stale-tier1.md)(GN1~GN6)
- 프리뷰 목업: 세션 스크래치패드(경로는 §10)
- 복잡도: **Medium** — 파일 7개, 새 의존성 0, 새 모듈 0, `commands/` 접촉 **0**

> **반려·철회된 결정은 지우지 않는다**(이 저장소 관행). 각 결정 아래에 `반려`/`철회` 표기와
> 사유를 붙여 보존한다 — 같은 후보가 다시 제안되는 것을 막는 것이 이 기록의 목적이다.

---

## 0. 요구사항 요약

허브의 세션 카드가 **지금 하는 일**을 정확히 말하지 못하는 결함 2건을 고친다.
(1) 같은 세션에서 새 질의를 시작해도 `div.agent-run-list` 에 이전 작업의 서브에이전트 실행이
그대로 남는다 — 실행 목록의 「작업 경계」가 대시보드 파일의 mtime 에 묶여 있어, 대시보드가
사라진 세션에서는 경계가 아예 없고 살아 있어도 30분을 기다려야 발동한다.
(2) 카드가 가리키는 대시보드의 **주인 세션이 그 카드에 보이지 않는데** 카드가 아무 표시 없이
그 대시보드를 연다 — 두 세대 판정(CD1·GN1)이 모두 「대조할 세션이 없으면 False」로
페일오픈하기 때문이다.

두 결함은 한 설계다. (1)의 경계를 옮기면 `SessionView.tier1_is_finished_task` 의 역할이
바뀌고, 그 값을 프로젝트 담체로 들어 올린 `ProjectView.tier1_is_finished_task` 가 (2)의
현행 클릭 게이트이기 때문이다.

### 사용자 스토리

> 허브를 보는 사람으로서, **카드에 보이는 실행 목록이 지금 진행 중인 작업의 것이기를** 원한다.
> 끝난 작업의 실행이 남아 새 작업의 것처럼 읽히면 화면을 신뢰할 수 없기 때문이다.
>
> 그리고 카드의 진행률이 **이 카드에 보이는 세션의 것인지** 알기를 원한다. 화면에 없는
> 세션의 66시간 전 진행률이 아무 표시 없이 그 프로젝트의 현재 상태처럼 보이면 안 되기
> 때문이다.

---

## 1. 조사와 접지 (설계 판단의 근거)

측정 시점 스냅샷: `collected_at_ms = 1789699586150`(§1.1~1.5, 2026-09-18 11:46) 및
2회차 재측정(§1.6~1.8, 같은 날 12:20). 이벤트 원본은 `~/.claude/hub/events/*.jsonl` 전수
(`UserPromptSubmit` 373 · `Stop` 313 · `SubagentStop` 266 · `SubagentStart` 143 ·
`SessionStart` 121 · `SessionEnd` 93).

### 1.1 결함 1 — 경계가 두 겹으로 실패한다

현행 경계(결정 PT1): `compute_session_view` 가 `is_session_tier1_from_finished_task`
(`percent >= 100` **AND** `last_event_at_ms − tier1.file_mtime_ms > stale_after_ms`)를 먼저 하고,
참일 때만 `previous_task_boundary_ms = tier1.file_mtime_ms` 를 `summarize_agent_runs` 에 넘긴다.
거짓이면 경계가 `None` 이고 아무 실행도 숨겨지지 않는다.

**(a) 대시보드 파일이 없으면 경계가 없다.** 사용자가 지적한 세션 `02185cdc` 는 워크트리에서
대시보드를 발행했고 작업 종료 후 워크트리를 제거해 파일이 함께 사라져 `tier1 = null` 이었다.
`tier1` 이 없으면 술어를 호출할 수조차 없다 — 실행 목록이 세션 수명 전체에 걸쳐 누적된다.

**(b) 대시보드가 있어도 30분을 기다린다.** 같은 프로젝트 `768e8a38` 은 대시보드가 100% 인데
Δ 가 임계값 미만이던 구간에서 실행 **23건**을 전부 표시했고, 사용자가 새 질의를 넣은 뒤
31.4분이 지나서야 게이트가 켜져 23건이 한꺼번에 사라졌다. 「새 프롬프트」는 현행 판정의
입력이 아니다.

### 1.2 프롬프트 시각은 이미 흐르고 있다

전사(transcript)의 `last-prompt` 줄에는 시각이 없다(`hub_transcript.py` 의
`LAST_PROMPT_LINE_TYPE`; `parse_session_tail` 이 `lastPrompt` 만 뽑는다). 그러나 허브 자신의
훅 이벤트에는 밀리초 시각이 붙어 있다:

```
{"t": 1789053172523, "e": "UserPromptSubmit", "s": "af5c0abe-…", "c": "/Users/dev/private/project/coding-harness"}
```

`hub_session._apply_tracked_event` 가 **이 이벤트를 이미 소비한다** — 지금은
`session.turn_state = "running"` 만 세팅하고 `event.received_at_ms` 를 버린다. 같은 함수의
`SubagentStart` 분기는 그 값을 `started_at_ms` 로 쓴다. 같은 정밀도의 시각이 같은 자리에 이미
있다.

`UserPromptSubmit` 은 **메인 세션 전용 훅**이다 — 서브에이전트 디스패치는 `SubagentStart` 를
내고 `UserPromptSubmit` 을 내지 않는다(`commands/hub.md` 의 전역 훅 6종 등록, 그리고
`hub_hook._project_fields` 가 페이로드의 `session_id` 를 그대로 기록한다). 따라서 이 시각은
「사람이 이 세션에 말을 걸었다」와 1:1 이다.

`02185cdc` 의 실제 타임라인(훅 이벤트):

```
09-17 14:27:22  PROMPT        09-18 09:56:10  PROMPT
09-17 14:32:53  RUN 설계       09-18 10:51:33  PROMPT
09-17 15:08:07  RUN 구현       09-18 10:52:37  PROMPT
09-17 16:34:39  RUN 검수       09-18 11:14:52  PROMPT
09-17 16:58:58  PROMPT        09-18 11:18:17  PROMPT
09-17 17:00:48  RUN 구현       09-18 11:35:51  PROMPT   ← 사용자 신고 시점의 마지막 프롬프트
09-17 17:34:53  RUN 검수       09-18 11:42:05  /dashboard init  ← §1.6
09-18 09:10:56  RUN 검수       09-18 11:45:19  RUN 설계
09-18 09:14:51  RUN 구현
```

### 1.3 프롬프트 단독 경계의 실데이터 (1회차 판정 — 기록 보존)

`after_prompt` = 마지막 프롬프트 경계 이후 시작된 실행 수, `after_ft` = 현행 FT 경계,
`after_max` = 두 경계 중 늦은 쪽:

| 세션 | 실행 | 현행 화면 | `after_prompt` | `after_ft` | `after_max` |
|---|---|---|---|---|---|
| `02185cdc` (working) | 7 | **7** | **1** | 7 | 1 |
| `768e8a38` (working) | 23 | 0 | 0 | 0 | 0 |
| `7ba572b2` (atlas) | 3 | 3 | 0 | 3 | 0 |
| `376f3c54` (notebook-model) | 1 | 1 | 0 | 1 | 0 |

- **`after_prompt == after_max` 가 전건 일치한다.** FT 경계를 함께 써도 화면이 같다.
- **간격 기반 대안은 자멸한다.** 「직전 이벤트로부터 30분 넘게 조용했던 프롬프트」를 경계로
  삼으면 `768e8a38` 의 경계가 **09-17 08:52** 로 후퇴해 23건이 전부 남는다(완전 무동작).
  원인: 서브에이전트가 도는 동안 `SubagentStart`·`SubagentStop`·`Stop` 이벤트가 틈을 메워
  프롬프트 앞 간격이 항상 작아진다(프롬프트 간 간격은 p10 0.8분 · median 8.3분 · p90 62.7분,
  n=347).
- **`turn_state` 전이 관찰은 마지막 프롬프트와 같은 값으로 붕괴한다.** `Stop` 은 모든
  어시스턴트 턴 끝에 발화하므로 「직전 Stop 이후 첫 프롬프트」 = 「마지막 프롬프트」다.

### 1.4 실행 중 프롬프트가 22.7% 다 (RL3 의 근거)

완료된 실행 119건 중 **27건(22.7%)** 이 실행 구간 안에 프롬프트를 받았다(사용자가 실행 중에
다음 지시를 큐에 넣는 패턴). 경계가 어떻게 유도되든 이 경우를 막지 않으면 **지금 돌고 있는
서브에이전트가 목록에서 사라진다** — 카드는 `작업중` 인데 목록이 비는 어긋남이다.

### 1.5 결함 2 — 두 세대 판정이 모두 페일오픈한다

`shouldRenderSession`(클라이언트)이 `state === 'stale' && (Date.now() − last_event_at_ms) >=
STALE_SESSION_HIDE_AFTER_MS(12h)` 인 세션을 숨긴다. 그 필터를 적용한 뒤 「주인이 보이는가」를
티어 1 프로젝트 전수로 재면:

| 프로젝트 | tier1 주인 | 명부에 있나 | **보이나** | 현행 클릭 |
|---|---|---|---|---|
| coding-harness | `02185cdc` | O | **O** | 가능 (정상) |
| atlas-ui-notebook-micro | `7ba572b2` | O | **X** (stale 20.3h → 숨김) | **가능 (결함)** |
| notebook-model | `376f3c54` | O | **X** (stale 19.9h → 숨김) | 불가 (FT 가 우연히 덮음) |
| daily-brief | `e717aeea` | **X** (66.8h 전) | **X** | **가능 (결함)** |
| NotebookWiki | `76d1d3a0` | **X** (90.6h 전) | **X** | **가능 (결함)** |

- 티어 1 **5개 중 4개**가 주인이 화면에 없고, 그중 **3개**가 아무 표시 없이 열린다.
- **약한 규칙(명부 존재만 확인)은 부족하다** — atlas·notebook-model 은 명부에 있고 숨겨진
  경우다. 사용자가 든 예(`atlas`)가 바로 그 경우다.
- `7ba572b2` 의 `tier1_is_finished_task = false` 는 판정 오류가 아니다
  (`last_event − mtime = 9분 < 30분`). 판정은 맞고, 게이트가 이 상황을 안 덮는다.
- 근인: `is_project_tier1_from_finished_session_task` 는 `any(...)` 가 일치를 못 찾으면 False,
  `is_tier1_from_previous_task` 는 `if not live_session_start_times_ms: return False`
  (주석에 「오탐 회피 방향」으로 명시된 의도적 페일오픈)다.
- **레거시 단일 파일은 지금도 실재한다**: `coding-harness/.claude/dashboard.html`(09-04) ·
  `NotebookWiki/.claude/dashboard.html`(08-10). 그 파일만 가진 프로젝트에서는
  `tier1.session_id is None` 이고 주인 세션이 **원리적으로** 없다.

### 1.6 2회차 발견 — 작업 시작 시각이 이미 디스크에 있다 (**핵심**)

1회차 §3.6 은 「`/dashboard init` 이 작업 시작을 표시하지만 파일에는 언제 init 됐는가가 남지
않는다」고 적었다. **그 서술이 틀렸다.** `/dashboard init` 은 4-a 단계에서 `Write` 도구로
사이드카 파일을 하나 남긴다(`commands/dashboard.md:620`):

```
.claude/dashboards/{토큰}.init-values.json      토큰 = session_id.split("-", 1)[0] (8자 hex)
```

그 파일은 **`init` 에서만** 쓰이고 `step`·`log`·`impl` 은 건드리지 않는다. 실측 mtime 대조:

| 세션 | 사이드카 mtime (= `init`) | 대시보드 html mtime | 차 |
|---|---|---|---|
| `02185cdc` | 09-18 **11:42:05** | 09-18 12:15:35 | 33분 |
| `768e8a38` | 09-18 **11:57:14** | 09-18 12:19:36 | 22분 |
| `7ba572b2` (atlas) | 09-17 **14:09:07** | 09-17 15:32:39 | 84분 |
| `e717aeea` (daily-brief) | 09-15 **16:14:13** | 09-15 17:02:19 | 48분 |

세션별 대시보드가 있는 프로젝트 전부에서 사이드카가 1:1로 존재했다(coding-harness 5/5 ·
atlas 2/2 · daily-brief 1/1 · NotebookWiki 2/2 · notebook-model 1/1).

**`init` 은 세션 단위가 아니라 작업 단위다.** `commands/dashboard.md:525` 가
「**`init` 은 언제나 대시보드를 처음부터 새로 만든다.** 기존 파일이 있으면 로그를 포함해 전부
버리고 이번 인자로 새로 그린다」라고 정의하고, 같은 파일의 CLAUDE.md 트리거 표가 `init` 을
**착수 보고 시**(전체 경로·축약 경로 모두)에 놓는다. 「`Skill(dashboard)` 호출은 세션당 1회」
제약은 **스킬 전문 주입**을 1회로 묶는 것이고 `init` 절차 자체의 반복을 막지 않는다.
실측이 그것을 확인한다 — `02185cdc` 는 09-17 14:27 에 시작된 세션인데 사이드카는 09-18
11:42 이고 대시보드 제목도 이번 작업의 것이다.

따라서 **사이드카의 mtime = 지금 카드에 보이는 작업이 시작된 시각**이다.

### 1.7 그래서 `data-started-at` 을 되살릴 필요가 없다

코디네이터가 지목한 두 경로를 실측 비교했다.

| | `data-started-at` 되살리기 | 새 속성 각인 | **사이드카 mtime (채택)** |
|---|---|---|---|
| `commands/` 접촉 | 있음 — 템플릿·헬퍼·문서 | 있음 | **없음** |
| T22 영향 | **T22-96 항목 제거 + T22-165 의 목록 길이 10→9** | 없음 | 없음 |
| `hub_parse` 영향 | 없음(정규식·`StepView.started_at` 이 이미 있다) | 정규식·`Tier1Snapshot` 필드·픽스처 | 없음 |
| `install.sh` manifest | 해시 대장 갱신 | 갱신 | **없음** |
| 정밀도 | **분**(픽스처 실측 `"2026-08-10 18:12"`) | 설계 선택 | **밀리초**(`st_mtime`) |
| 의미 | 단계 전이 시각 — 작업 시작은 1단계 값으로 **간접** 유도 | 직접 | **직접**(init 시각) |
| 수집 비용 | 0 | 0 | **0** — `read_session_dashboard_snapshots` 의 `iterdir()` 가 사이드카를 **이미 열거한다** |

`data-started-at` 경로는 문서화된 역방향 가드(T22-96)를 번복하고 그 목록의 완비 검사
(T22-165)의 숫자까지 고쳐야 하는데, 얻는 것이 분 정밀도의 **간접** 신호다. 분 정밀도가
경계로 충분한지도 따져야 한다 — 실측에서 `init` 과 첫 서브에이전트 디스패치 간격은
`02185cdc` 3분 14초, `7ba572b2` 1분 40초였다. 같은 분에 떨어지면 `<` 비교가 뒤집힌다.
사이드카는 이 문제가 없다(ms). **`commands/` 를 건드리지 않고, 가드를 번복하지 않고, 더
정확한 신호를 얻는다** — 비교가 한쪽으로 기운다.

### 1.8 반례 B 의 실례 11건을 찾았다

`design-architect` 실행이 끝나고 → 프롬프트가 들어오고 → `implementer` 가 시작되는 3박자를
훅 이벤트 전수에서 뽑으면 **11건**이다(세션 `76d1d3a0` 5 · `d0e8c16b` 2 · `768e8a38` 1 ·
`376f3c54` 1 · `e717aeea` 1 · `7ba572b2` 1). 그 사이에 들어온 프롬프트 개수의 분포:

| 중간 프롬프트 수 | 1건 | 2건 | 3건 | 4건 | 16건 |
|---|---|---|---|---|---|
| 실례 | 6 | 2 | 1 | 1 | 1 |

승인 뒤 구현 시작까지 프롬프트가 **2건 이상** 끼는 경우가 11건 중 **5건(45%)** 이다. 이 분포가
「직전 프롬프트 1개만큼 유예」 계열 후보를 기각하는 근거다(§3.8 RL-δ).

가장 깨끗한 실례 — 세션 `7ba572b2`(atlas, 작업 「화면 숨김 요소 정리 검토」):

```
09-17 14:09:07  /dashboard init  (사이드카 mtime)
09-17 14:10:47  RUN design-architect 시작
09-17 14:30:08  RUN design-architect 종료
09-17 14:30:10  PROMPT  ← 「승인」 (종료 2초 뒤)
09-17 14:37:53  RUN implementer 시작
```

14:30:10 직후(구현이 아직 안 뜬 순간)가 반례 B 다.

---


### 1.9 3회차 — 탐색 공간 전수 열거

「대시보드가 없을 때 작업 단위를 알 수 있는 신호」를 찾기 위해 허브가 접근할 수 있는 모든
파일·디렉터리·이벤트를 열거했다. 판정 기준은 **세션 하나 안에서 작업이 바뀌는 순간을
가리키는가**다(세션 단위 신호는 반례 B 를 못 푼다 — 한 세션 안의 구분이 문제이기 때문).

**A. `~/.claude/` (사용자 홈, 실측 전수)**

| # | 대상 | 정체 | 작업 단위 신호인가 |
|---|---|---|---|
| 1 | `hub/events/*.jsonl` | 훅 이벤트 **6종 전부**(§1.2) | ✗ 이미 소비. 종류가 6개뿐이고 작업 어휘가 없다 |
| 2 | `hub/{config,server,rate_limits}.json` · `hub.html` · `server.log` · 하트비트 | 허브 자신의 상태 | ✗ 허브가 쓴 것 |
| 3 | `sessions/<pid>.json` | 호스트 명부 19필드 | ✗ **§1.10** |
| 4 | `projects/<enc>/<session>.jsonl` | 전사, line type **15종** | ✗ **§1.11** |
| 5 | `projects/<enc>/<session>/subagents/agent-*.{jsonl,meta.json}` | 서브에이전트 전사·메타 | ✗ 실행 1건의 기록. 이미 AR7 이 `meta.json` 소비 |
| 6 | `projects/<enc>/<session>/tool-results/*.txt` | 도구 출력 캐시 | ✗ 도구 호출 단위 |
| 7 | `projects/<enc>/<session>.desktop-released.json` | `{v, releasedAt, reason:"delete"}` | ✗ 데스크톱 세션 해제 마커 |
| 8 | `projects/<enc>/memory/` | 자동 메모리 | ✗ 사용자 지식, 시각 없음 |
| 9 | `file-history/<session>/<hash>@vN` | 파일 편집 백업 버전 | ✗ 편집 단위. 실측 17세션 · 세션당 6~27개 |
| 10 | `session-env/<session>/` | **빈 디렉터리 584개**, mtime = 세션 시작(실측 `02185cdc` 14:27:21 = 세션 시작 14:27:22) | ✗ 세션 단위 |
| 11 | `shell-snapshots/snapshot-zsh-*.sh` | 셸 환경 스냅샷 | ✗ 셸 초기화 단위 |
| 12 | `ide/<pid>.lock` | IDE 연결 락 | ✗ pid 단위 |
| 13 | `history.jsonl` | 프롬프트 표시 이력 | ✗ 세션 귀속 없음. **08-03 이후 미갱신**(죽은 파일) |
| 14 | `todos/` | — | ✗ **존재하지 않는다**(이 버전은 TodoWrite 를 디스크에 남기지 않는다) |
| 15 | `agents/ commands/ skills/ rules/ plugins/ hooks/ output-styles/ scripts/ .agents/ ecc/ mcp-configs/` | 정적 배포 자산 | ✗ 런타임 사실이 아니다 |
| 16 | `settings.json`(+백업 14개) · `.coding-harness.json` · `policy-limits.json` · `remote-settings.json` · `stats-cache.json` · `mcp-needs-auth-cache.json` · `cache/` · `debug/` · `backups/` | 설정·캐시 | ✗ 작업과 무관 |

**B. 프로젝트 `<repo-root>/.claude/` (실측 전수)**

| # | 대상 | 작업 단위 신호인가 |
|---|---|---|
| 17 | `dashboards/<uuid>.html` + `<token>.init-values.json` | ✅ **RL8 의 신호**(§1.6) — 지금 문제는 이것이 **없을 때**다 |
| 18 | `dashboard.html`(레거시) | ✗ 세션 귀속 불가(토큰이 무작위 hex) |
| 19 | `settings.local.json` | △ **작업 신호는 아니지만 `dashboard_enabled` 오프 스위치가 여기 있다 → RL10** |
| 20 | `worktrees/` | ✗ 워크트리 경로. WT3 가 이미 소비 |

**C. 프로젝트 저장소 자체**

| # | 대상 | 작업 단위 신호인가 |
|---|---|---|
| 21 | `.git/`(HEAD · COMMIT_EDITMSG · `logs/HEAD` 리플로그) | ✗ **§1.12** |
| 22 | `docs/prps/*.md` | ✗ 이 저장소 고유 관행이고 전체 경로에만 있다. 세션 귀속도 없다 |
| 23 | 소스 파일 mtime | ✗ 편집 단위, 세션 귀속 없음 |

### 1.10 호스트 명부의 `name`·`nameSince` — 재측정 결과 세션 단위다

메인의 관측(「3건 전부 `nameSince == startedAt`」)을 **레코드 전수 9건으로 재측정**했다.

```
11030.json  src=derived  Δ=0.0분  atlas-ui-notebook-micro-de
34361.json  src=derived  Δ=0.0분  coding-harness-30
353.json    src=derived  Δ=0.0분  notebook-model-35
53013.json  src=None     Δ=0.0분  현재 브랜치 작업 요약 및 체리픽
55612.json  src=None     Δ=0.0분  대시보드 허브 UI 개선
64395.json  src=derived  Δ=0.0분  coding-harness-1a
64864.json  src=derived  Δ=0.0분  atlas-ui-notebook-micro-8e
72873.json  src=None     Δ=0.0분  원피스 에디터 HTML 생성 프롬프트
85671.json  src=derived  Δ=0.0분  notebookwiki-ad
```

**Δ(`nameSince` − `startedAt`) != 0 인 레코드: 0건 / 9.** 이름은 프로세스 시작 시각에 한 번
정해지고 갱신되지 않는다 — 관측이 뒤집히지 않았으므로 이 후보는 되살아나지 않는다.
`status`·`statusUpdatedAt` 은 턴 단위다. 그리고 이 레코드는 **pid 로 키가 잡혀 살아 있는
프로세스에만 존재**하므로 반례 A 처럼 과거를 보는 판정에는 원리적으로 쓸 수 없다.
`LS3` 의 `RosterState` 5값 계약을 넓히는 비용(명시적 번복 + `hub_session` 이 필드 이름을 알게
된다)을 치를 근거가 없다.

### 1.11 전사의 line type 15종 — `custom-title` 과 `slug` 를 실측으로 기각한다

coding-harness 전사 26개에서 line type 과 키를 전수 추출했다. 작업 이름처럼 보이는 것이 둘 있다.

| line type | 건수 | 판정 |
|---|---|---|
| `custom-title` (`customTitle`) | 2353 | **세션 단위** — 전 프로젝트 전사에서 `custom-title` 을 가진 세션 **55개 중 세션 안에서 제목이 바뀐 것은 1개**이고, 그 변화도 `'X'` → `'X (fork)'`(포크 표시)다. `02185cdc` 는 18번째 줄에 1건뿐 |
| `slug` (assistant·user·attachment·system 에 실림) | 전 라인 | **세션 단위** — `slug` 를 가진 세션 **71개 전부가 세션 내 1개**. 값도 `rustling-bouncing-sloth` 류 무작위 낱말이라 작업 서술이 아니다 |
| `system` (`subtype`) | 1791 | `stop_hook_summary` 3278 · `compact_boundary` 243 · `api_error` 80 · `model_refusal_fallback` 6 · `local_command` 5. 작업 경계 마커가 없다(`compact_boundary` 는 압축, `local_command` 는 슬래시 커맨드 stdout) |
| `mode` · `queue-operation` · `atis-latch` · `bridge-session` · `worktree-state` · `relocated` · `pr-link` · `file-history-{delta,snapshot}` · `last-prompt` · `user` · `assistant` · `attachment` | — | ✗ 각각 권한 모드·메시지 큐·브리지·워크트리·PR·파일 이력·프롬프트·대화 본문. 작업 단위가 아니다 |

**TodoWrite 도 기각**: 도구 호출 전수에서 coding-harness 전사 **26개 중 TodoWrite 를 쓴 세션 0개**
(상위 도구는 Bash 11845 · Edit 1960 · Agent 1065). 이 저장소는 진행 기록을 `/dashboard` 로
하므로 TodoWrite 는 신호로 존재하지 않는다. 있었더라도 전사 안이라 128KB 꼬리 창 한계
(§1.3 실측)에 걸린다.

`wf_*.json` 워크플로우 실행도 기각한다 — `Workflow` 도구의 산출물이고 이 저장소의
설계→구현→검수 흐름은 그것을 쓰지 않는다(표본이 `claude-agents-manager` 8월 것뿐이다).

### 1.12 git 커밋 — 세션 귀속이 없어서 못 쓴다

「마지막 커밋 = 작업 경계」는 이 표본에서 두 반례를 통과하는 것처럼 보인다(반례 A 구간에
`251f727`(10:47:04) 커밋이 있어 실행 6건이 전부 그 앞이다). 그러나 기각한다.

1. **커밋에는 세션 ID 가 없다.** 경계는 세션별이어야 하는데 git 은 저장소별이다. 지금 이
   저장소에서 세션 `02185cdc` 와 `768e8a38` 이 **동시에 `working`** 이다(실측) — 한쪽의
   커밋이 다른 쪽의 실행 목록을 지운다. 이 위험은 이미 문서화돼 있다(auto-memory
   「동시 세션 주의」).
2. **작업 중 커밋이 경계를 앞당긴다.** 워크플로우는 구현 중에도 `log commit` 을 남긴다 —
   구현이 커밋한 뒤 검수 실행이 뜨면 검수 직전에 경계가 전진해 구현 실행이 사라진다(반례 B
   와 같은 계열의 역실패).
3. **커밋 없이 끝나는 작업이 흔하다.** 설계만 하는 회차·분석 작업에는 커밋이 없어 경계가
   영원히 전진하지 않는다(반례 A 재발).
4. `fold_worktree_path` 가 「git 호출도 `.git` 파일 읽기도 하지 않는다」를 결정 WT3 로 못 박았다.

### 1.13 결론 — **세 번째 신호는 없다**

§1.9 의 23개 항목 중 **작업 단위 시각을 주는 것은 17번(대시보드 사이드카) 하나뿐**이다.
구조적으로도 그렇다. 프롬프트가 들어온 순간에 반례 A(새 작업)와 반례 B(승인)를 가르는
정보는 셋뿐이다:

| 정보 | 허브가 볼 수 있나 | 판정 |
|---|---|---|
| 프롬프트의 **의미**(「승인」인가 새 요청인가) | 텍스트는 `task_excerpt` 로 볼 수 있다 | ✗ 한국어 자유 텍스트 분류기다. 사용자가 어떤 말로 승인할지 상한이 없다 |
| **침묵 간격** | 볼 수 있다 | ✗ 사람의 응답 지연에 상한이 없다 — 설계를 12:05 에 받아 14:00 에 승인하면 경계가 켜진다(`RL-γ`·코디네이터 지적과 같은 실패) |
| **그 뒤에 일어난 일**(실행이 떴는가) | 볼 수 있다(30초마다 재수집) | ✗ `RL-β` — 반례 A 는 서브에이전트가 0건인 질의라 경계가 전진하지 않는다(실측: 경계가 09-18 09:12:06 에 머물러 이전 작업 실행이 잔존) |
| **명시적 선언** | `/dashboard init` 뿐 | 이것이 **RL8** 이고, 지금 다루는 것은 그것이 없는 경우다 |

즉 **「작업이 바뀌었다」는 사실은 누군가 선언해 주지 않으면 관측되지 않는다.** 대시보드를
끈 구성에서는 그 선언자가 없다. 약한 신호를 만들어 넣으면 반례 B 가 임계값 바깥에서 재발할
뿐이다. 그래서 신호를 만들지 않고, 대신 **구멍이 열리는 구성 자체를 인지해 좁힌다**(RL10).

## 2. 영향 범위 (파일별)

| 파일 | 조치 | 이유 |
|---|---|---|
| `hub/bin/hub_session.py` | UPDATE | `SessionFacts.last_prompt_at_ms` 신설 · `_apply_tracked_event` 가 채움 · `previous_task_boundary_ms()` 순수 함수 신설(RL8·**RL10**) · `summarize_agent_runs` 의 실행 중 면제 |
| `hub/bin/hub_parse.py` | UPDATE | `Tier1Snapshot.task_started_at_ms` 필드 신설(파서는 채우지 않는다 — `source_path`·`session_id` 와 같은 계열) |
| `hub/bin/hub_project.py` | UPDATE | 사이드카 파일명 → 세션 토큰 정규식·순수 함수 · `SessionFacts` 를 뷰로 접을 때 프로젝트의 대시보드 사용 여부를 실어 나른다(RL10) |
| `hub/bin/hub_collect.py` | UPDATE | `read_session_dashboard_snapshots` 의 기존 `iterdir()` 1회 안에서 사이드카 mtime 수집 · **`<repo-root>/.claude/settings.local.json` 의 `dashboard_enabled` 1회 읽기**(RL10) |
| `hub/bin/hub_template.html` | UPDATE | 라벨 상수 2개 · `isTier1OwnerVisible()` 신설 · `renderTier1` 2번째 인자를 라벨 문자열로 · `renderProject` 가 라벨·속성 부여 · CSS 2줄 |
| `hub/README.md` | UPDATE | 실행 숨김 정책(256~258 부근) · **대시보드를 끈 프로젝트의 동작**(RL10) · 카드 경고 서술(389~394 부근) |
| `tests/run.sh` | UPDATE | T25-222 · T25-223 신설, T25-220 서브체크 ② 개정 |
| `tests/mutations.tsv` | UPDATE | 변조행 2건 추가(T37 완비 검사 요구) |
| `tests/hub/test_hub_session.py` · `test_hub_collect.py` · `test_hub_project.py` | UPDATE | 순수 로직·수집 단위 테스트 추가 |

**변경하지 않는 파일과 그 이유**

- **`commands/` 전체 — 접촉 0.** 3회차에도 그대로다(§1.9·§1.12 의 모든 후보를 기각했고
  RL10 은 `commands/dashboard.md` 가 **이미 정의한** 오프 스위치를 읽기만 한다). 따라서 T22
  그룹 · `test_hub_dashboard_contract.py` · `install.sh` manifest 대장(`.coding-harness.json` v3) ·
  `removals.txt` 전부 영향권 밖이다.
- `hub/bin/hub_live_session*.py` — `RosterState` 5값 계약(LS3)을 넓히지 않는다(§1.10).
- `hub/bin/hub_settings.py` — 이 모듈은 `~/.claude/settings.json`(훅 설치 대상)을 다룬다.
  RL10 이 읽는 것은 **프로젝트 로컬** `.claude/settings.local.json` 이라 다른 파일이다 —
  이 모듈에 손대지 않는다.
- `hub/bin/hub_model.py` — `asdict` 기반 직렬화라 코드 변경이 없다.
- `hub_template.html` 의 패널 IIFE — **한 줄도 바뀌지 않는다**(CG10).
- `hub/bin/hub_transcript.py` — 전사 경로를 쓰지 않는다(§1.11).

---

## 3. 결함 1 — 실행 목록 초기화 (결정 RL1~RL10)

### 3.1 RL1 — 마지막 `UserPromptSubmit` 시각을 사실로 보존한다 (유지)

`SessionFacts` 에 `last_prompt_at_ms: int | None = None` 을 더하고,
`_apply_tracked_event` 의 `UserPromptSubmit` 분기가 `event.received_at_ms` 를 넣는다.
`turn_state = "running"` 세팅은 그대로 둔다(상태 판정의 입력이라 별개 책임이다).

**3회차에도 이 필드는 필요하다** — RL8 의 「끝난 작업」 갈래와 폴백 갈래가 이 값을 쓴다.

기본값 `None` 은 `SessionView.model`·`workflow` 와 같은 계열의 판단이다 — 정체성 필드가
아니라 정당하게 부재할 수 있는 부가 정보다(스냅샷 14세션 중 1세션이 프롬프트 0건).
맨 뒤에 두면 기존 `SessionFacts(...)` 생성 지점 19곳(테스트)이 무해하다.

### 3.2 RL2 — `tier1_is_finished_task` 게이트를 폐지한다 (유지, **결정 PT1 번복**)

`previous_task_boundary_ms` 를 **무조건** 넘긴다. 게이트가 `tier1` 을 요구하면 `tier1 = null`
세션(결함 1-(a))에서 영원히 무동작이다.

PT1 번복 근거: PT1 의 「경계로 쓸 다른 시각이 없다」는 **전사의 `last-prompt` 줄에 대해서만**
맞았다(§1.2). FT2(`stale_after_ms` 재사용)는 번복하지 않는다 — RL5 가 유지하는 클릭 게이트
쪽에서 계속 쓰인다.

### 3.3 RL3 — 실행 중인 실행은 경계 이전에 시작됐어도 숨기지 않는다 (유지)

```
is_previous_task = (previous_task_boundary_ms is not None
                    and started_at_ms < previous_task_boundary_ms
                    and not is_running)          # ← 신설
```

근거는 §1.4 의 22.7%. 판정을 **서버**에 두는 이유: 클라이언트에 두면
`visibleAgentRunRows` 의 필터 리터럴과 `renderAgentRunList` 의 `currentTaskRunCount` 리터럴
두 곳을 같이 고쳐야 하고(T25-220 서브체크가 그 둘의 일치를 검사한다), 원장 행까지 연쇄한다.
서버에 두면 클라이언트 리터럴이 **바이트 단위로 그대로**다.

이 연접은 RL8 에서 **두 번째 역할**을 얻는다 — `init` 보다 먼저 디스패치된 실행을 구제하는
안전판이다(§3.9).

### 3.4 RL4 — 신호가 없으면 경계가 없다 (페일오픈, 유지)

경계 유도의 어느 갈래에서도 입력이 전부 없으면 `None` → 전부 표시. 오늘의 동작과 같다.
이벤트 읽기 창이 「오늘+어제」(`_recent_event_file_paths`)라 창 밖으로 밀린 프롬프트는 경계를
앞으로 당기거나 없앤다 — 숨김이 줄어드는 방향이라 안전하다.

### 3.5 RL5 — `tier1_is_finished_task` 는 그대로 남긴다 (유지)

`compute_session_view` 는 `is_session_tier1_from_finished_task` 를 계속 호출하고
`SessionView.tier1_is_finished_task` 를 계속 채운다. 소비자는 세션 행 클릭 게이트(FT4)와
프로젝트 담체로의 승격(CD1)뿐이다. **실행 목록과의 연결만 끊는다.** FT1~FT3·FT7 · CD1~CD7
전부 유지.

### 3.6 ~~RL6 — 「승인」 프롬프트도 경계다~~ — **반려 (1회차, 사용자 판정)**

> **1회차 권고**: 경계 = 마지막 프롬프트 단독. 「승인」 입력이 끝난 design-architect 실행을
> 목록에서 지우는 것을 그대로 채택하자고 권고했다(근거: 작업 서사는 tier1 진행 블록과
> 워크플로우 칩이 들고 있다 / 작업 단위 경계를 값싸게 만들 방법이 없다).
>
> **사용자 판정: 반려**(「보류 — 대안을 더 찾아라」).
>
> **반려가 정당한 이유(2회차 확인)**: 근거 2(「작업 단위 경계를 값싸게 만들 방법이 없다」)의
> 전제가 **사실과 달랐다.** 1회차는 「파일에 init 시각이 남지 않는다」고 단정했으나, `init`
> 은 `{토큰}.init-values.json` 을 남기고 그 mtime 이 정확히 작업 시작 시각이다(§1.6).
> 값싼 방법이 **있었고**, 그것을 못 찾은 상태에서 트레이드오프를 승인 요청으로 올린 것이
> 1회차의 오류다. §1.8 의 실례 11건에서 RL6 은 **11/11 전건 실패**한다.
>
> 이 결정은 삭제하지 않고 남긴다 — 「마지막 프롬프트 단독」은 가장 단순해서 다시 제안되기
> 쉬운 후보이고, 기각 근거가 실측(11/11)이기 때문이다.

### 3.7 RL8 — 경계 = **대시보드 작업 시작 시각** (2회차 신설, (a)·(b) **사용자 이견 없음**)

순수 함수 하나로 유도한다.

```python
def previous_task_boundary_ms(
    tier1: Tier1Snapshot | None,
    last_prompt_at_ms: int | None,
    is_dashboard_enabled: bool,          # ← 3회차 RL10
) -> int | None:
    """실행 목록의 작업 경계(결정 RL8·RL10). 순수 — 파일·시각에 닿지 않는다."""
    if tier1 is None or tier1.task_started_at_ms is None:
        if not is_dashboard_enabled:
            return None                                             # (d) RL10 — 선언자가 없다
        return last_prompt_at_ms                                    # (c) 폴백
    if tier1.percent >= TIER1_FINISHED_PERCENT:
        if last_prompt_at_ms is None:
            return tier1.task_started_at_ms
        return max(tier1.task_started_at_ms, last_prompt_at_ms)      # (b) 끝난 작업
    return tier1.task_started_at_ms                                  # (a) 진행 중
```

- **(a) 작업이 진행 중이면(`percent < 100`) 경계 = 그 작업의 시작 시각.** 그 작업에 속한
  실행은 몇 번의 프롬프트를 거쳐도 전부 남는다 → **반례 B 통과.**
- **(b) 작업이 끝났으면(`percent >= 100`) 경계 = max(작업 시작, 마지막 프롬프트).** 끝난 작업
  뒤의 새 질의가 **즉시** 목록을 비운다(30분 대기 소멸 → 결함 1-(b) 해결).
- **(c) 대시보드·사이드카가 없고 대시보드가 켜져 있으면 경계 = 마지막 프롬프트** → **반례 A
  통과.** (반례 A 는 워크트리를 제거해 파일이 사라진 경우이고 대시보드는 켜져 있었다.)
- **(d) 대시보드를 껐으면 경계 없음** — 3회차 신설, §3.11 RL10.

`percent >= TIER1_FINISHED_PERCENT` 는 FT 의 첫 연접과 같은 상수를 재사용한다(새 임계값 0개).
FT 의 Δ 연접(30분)은 실행 목록에서 완전히 빠진다.

**실데이터 판정** (2회차 재측정):

| 세션 | 실행 | 현행 | RL6(프롬프트) | **RL8** | `%` | 사이드카 | RL8 경계 |
|---|---|---|---|---|---|---|---|
| `768e8a38` | 24 | **24** | 0 | **1** | 25 | 11:57:14 | 11:57:14 (a) |
| `02185cdc` | 7 | **7** | 1 | **1** | 0 | 11:42:05 | 11:42:05 (a) |
| `376f3c54` | 1 | 1 | 0 | **0** | 100 | 09-16 14:24 | 09-17 15:51 (b) |
| `7ba572b2` | 3 | 3 | 0 | **0** | 100 | 09-17 14:09 | 09-17 15:41 (b) |
| `d0e8c16b` | 0 | 0 | 0 | 0 | 100 | 09-11 14:28 | 09-14 09:53 (b) |

### 3.8 후보 판정표 — 반례 A·B 를 **동시에** 통과하는가

「대시보드 없음」 구성에서의 판정이다(대시보드가 있으면 RL8-(a)/(b)가 이미 둘 다 통과한다).

| 후보 | 경계 유도식 | **반례 A** | **반례 B** | `commands/` 비용 | 판정 |
|---|---|---|---|---|---|
| RL-α = RL6 | 마지막 프롬프트 단독 | ✅ | ❌ 실례 **11/11 실패** | 없음 | **반려**(사용자) |
| RL-β | 프롬프트 뒤 실행 ≥1 일 때만 전진 | ❌ 경계가 09-18 09:12:06 에 머물러 잔존 | ✅ | 없음 | 기각 — 서브에이전트 0건 질의에서 전진 불가 |
| RL-γ | 간격 > 30분 프롬프트 | ❌ `768e8a38` 경계가 09-17 08:52 로 후퇴 | ✅ | 없음 | 기각(§1.3) |
| RL-γ′ | **직전 실행 종료 뒤 N분 침묵한 프롬프트** | ✅ | ❌ **사람의 응답 지연에 상한이 없다** — 설계를 받고 2시간 뒤 승인하면 경계가 켜진다 | 없음 | 기각 — 임계값을 어떻게 잡아도 「사람 대기」와 「작업 사이 대기」를 못 가른다 |
| RL-δ | 직전 프롬프트(1턴 유예) | ✅ | ⚠️ 실례 **5/11 실패** | 없음 | 기각(§1.8) |
| RL-ε/ζ | `data-started-at` / 새 속성 각인 | ✅ 폴백 | ✅ | **큼** | 기각(§1.7) |
| **3회차 신규 후보** | | | | | |
| 명부 `name`·`nameSince` | 개명 시각 | ❌ 살아 있는 pid 만 | ❌ **세션 단위**(Δ=0, 9/9) | 없음 + **LS3 번복** | 기각(§1.10) |
| 전사 `custom-title` | 제목 변경 시각 | ❌ 128KB 창 | ❌ **세션 단위**(55세션 중 변화 1건, 그것도 `(fork)`) | 없음 | 기각(§1.11) |
| 전사 `slug` | 슬러그 변경 | ❌ | ❌ **세션 단위**(71/71 단일), 무작위 낱말 | 없음 | 기각(§1.11) |
| TodoWrite 목록 | 새 목록 = 새 작업 | ❌ 128KB 창 | ❌ **이 저장소 사용 0/26 세션** | 없음 | 기각(§1.11) |
| `SessionStart so:"clear"` | `/clear` 시각 | ❌ `/clear` 를 쓸 때만 | — | 없음 | 기각 — 경계를 **늦추는** 방향뿐이라 반례 B 에 무효 |
| git 마지막 커밋 | 커밋 시각 | ✅(표본) | ❌ 작업 중 커밋이 경계를 앞당긴다 | 없음(단 `.git` 읽기) | 기각 — **세션 귀속 없음**(동시 세션 2개 실측), WT3 위반(§1.12) |
| 프롬프트 텍스트 분류 | 「승인」인지 판정 | — | — | 없음 | 기각 — 자유 텍스트 분류기. 승인 어휘에 상한이 없다 |
| **RL8 + RL10** | **사이드카 mtime · 없으면 폴백 · 껐으면 경계 없음** | ✅ **(c)** | ✅ **(a)/(d)** | **없음** | **채택 권고** |

### 3.9 RL8 의 한계 (전부 명시한다)

- **`init` 을 다시 부르지 않고 새 작업을 시작하면** 경계가 옛 작업 시작에 머물러 이전 실행이
  남는다. FT3 이 이미 「중간에 방치된 대시보드는 검출하지 않는다」를 의도된 미검출로
  선언했고, 이것은 그 계열이다. 갈래 (b)가 대부분을 덮는다.
- **`init` 보다 먼저 서브에이전트를 디스패치하면** 그 실행이 숨겨진다. CLAUDE.md 트리거
  표(`착수 보고 시 init`)를 어긴 경우다. **RL3 이 안전판** — 아직 돌고 있는 실행은 숨지 않는다.
  실측에서 순서는 `02185cdc`(11:42:05 → 11:45:19) · `7ba572b2`(14:09:07 → 14:10:47) 모두 지켜졌다.
- **사이드카가 리텐션(`RETENTION_SECONDS` = 7일)으로 먼저 사라질 수 있다** — 스윕은 `init`
  때만 돌고 사이드카는 자기 html 보다 항상 오래됐다. 그 경우 (c) 또는 (d)로 내려앉는다.
- **토큰 충돌** — 사이드카 이름이 `session_id` 앞 8자 hex다. 같은 프로젝트에 앞 8자가 같은
  두 세션이 있으면 작업 시작이 섞인다. `SHORT_ID_LENGTH = 8` 이 이미 화면 전체에서 쓰는 같은
  키라 **새 위험이 아니다**. 레거시 모드의 무작위 토큰이 우연히 겹칠 확률도 무시 가능하다.

### 3.10 RL9 — 2차 효과: 세션 줄이 사라질 수 있다 (수용, 결정 V2 의 귀결)

`shouldRenderSession` 은 `done` + 표시 발췌 없음 + 보이는 실행·칩 0개면 세션 줄을 숨긴다.

**실측: 라이브 스냅샷에서 새로 사라지는 세션 줄은 0개다.** 실행이 전부 숨겨지는 세션은 모두
`task_excerpt` 를 갖는다. 구조적으로도 그렇다 — `task_excerpt` 는 전사의 `last-prompt` 이고,
프롬프트가 있으면 발췌도 있다.

### 3.11 RL10 — 대시보드를 **끈** 프로젝트에서는 경계를 두지 않는다 (3회차 신설, **권고**)

세 번째 신호가 없다는 것이 §1.13 의 결론이다. 그래서 신호를 만들지 않고, **구멍이 열리는
구성을 인지해 좁힌다.**

코디네이터가 좁힌 대로, 폴백 (c)가 실제로 해를 끼치는 구성은 하나다 —
**`dashboard_enabled: false` 로 대시보드를 껐는데 전체 경로(설계 → 승인 → 구현)로 일하는
세션.** 그 스위치는 이미 존재하고 위치가 정해져 있다(`commands/dashboard.md:1343~1357` ·
`rules/workflow/role-separation.md:131`):

```
<repo-root>/.claude/settings.local.json     {"dashboard_enabled": false}
```

**필드가 없으면 켜짐**이 그 문서들이 정한 기본값이다.

> **결정 RL10 — `dashboard_enabled` 가 명시적으로 `false` 인 프로젝트에서는
> `previous_task_boundary_ms` 가 `None` 을 돌려준다(갈래 (d)). 실행 목록은 오늘과 똑같이
> 아무것도 숨기지 않는다.**

근거:

1. **사용자가 작업 단위의 유일한 선언자를 스스로 껐다.** 그 상태에서 프롬프트로 작업 경계를
   **추측**하는 것이 정확히 RL6 이고, 사용자가 반려한 동작이다. 선언이 없으면 추측하지 않는
   것이 반려의 취지에 맞다.
2. **반례 A 는 이 갈래에 들어오지 않는다.** 반례 A 의 프로젝트(coding-harness)는 대시보드가
   켜져 있고(실측: `settings.local.json` 에 `dashboard_enabled` 필드 자체가 없다) 파일만
   워크트리 제거로 사라졌다. 그래서 (c)를 그대로 타 6건이 숨겨진다.
3. **비용이 거의 없다.** `commands/` 접촉 0(이미 정의된 스위치를 읽기만 한다), 새 임계값 0,
   새 의존성 0. 수집 쪽에 프로젝트당 파일 1개 읽기가 늘어난다.
4. **끄지 않은 사용자에게는 아무 영향이 없다** — 필드가 없으면 오늘과 같은 (c) 경로다.

**판정표** (「대시보드 없음」 구성):

| 구성 | `dashboard_enabled` | 갈래 | 반례 A | 반례 B |
|---|---|---|---|---|
| 워크트리 제거로 파일 소실 (= 반례 A) | 없음(켜짐) | (c) | ✅ 숨김 | — (B 가 안 일어나는 구성) |
| 워크플로우 생략 작업 | 없음(켜짐) | (c) | — | — (서브에이전트를 안 쓴다) |
| **`/dashboard off` 로 끔 + 전체 경로** | `false` | **(d)** | — | ✅ **아무것도 안 숨긴다** |
| 사이드카만 리텐션으로 소실 | 없음(켜짐) | (c) | ✅ | ⚠️ 남는 구멍(아래) |
| `init` 을 아직 안 부른 전체 경로 작업 | 없음(켜짐) | (c) | ✅ | ⚠️ 남는 구멍(아래) |

**남는 구멍을 숨기지 않는다.** 마지막 두 행 — 대시보드가 켜져 있는데 그 작업에 대해
사이드카가 없는 경우 — 에서는 여전히 폴백 (c)가 걸려 반례 B 가 재발할 수 있다. 완화 요소
둘: (i) RL3 이 진행 중 실행을 구제한다, (ii) 그 상태는 워크플로우 규칙(`착수 보고 시 init`)을
어긴 상태이므로 고칠 주체가 있다. **이 구멍을 닫는 신호는 §1.9 전수 조사에 없다** — 닫으려면
`/dashboard init` 을 부르는 것이 유일한 방법이고, 그것이 곧 RL8-(a)다.

기각한 대안적 좁히기:

- **폴백을 「세션의 첫 프롬프트」로** — 아무것도 숨기지 않게 되어 반례 A 가 재발한다.
  RL10 은 그 동작을 **끈 프로젝트에만** 적용해 A 를 살린다.
- **폴백을 「마지막 프롬프트 − 여유」로** — 여유값이 곧 RL-γ′ 의 임계값이고 같은 이유로
  사람의 대기 시간에 깨진다.
- **프로젝트에 대시보드가 하나라도 있으면 켜진 것으로 본다** — 껐어도 옛 파일이 남아 있어
  오판한다. 명시 필드를 읽는 쪽이 정확하고 더 싸다.

---

## 4. 결함 2 — 카드 세대 경고 (결정 CG1~CG12)

> → **폐기(2026-09-30)** — CG1~CG3(주인 세션이 보이는지 판정)·CG6(진행 줄에 경고를 얹는다)·CG8~CG12(「주인 세션 없음」 칩과
> 톤다운)는 대상이 사라졌다: 카드와 카드 상세보기 머리가 프로젝트 단위 진행률을 그리지 않는다(hub-session-modal-cleanup.md
> 결정 MX4). 진행률은 그 대시보드를 기록한 세션 아래에만 보인다. 판정 함수(`isTier1OwnerVisible`)·칩·톤다운 CSS·README 서술은
> 함께 걷혔다. CG4·CG5 의 철회와 CG7(세션 행 무변경)은 그대로다.

### 4.1 CG1 — 판정 규칙 (유지)

> **카드에 보이는 세션 중 `tier1.session_id` 의 주인이 없는가.**

§1.5 의 실측 A(숨겨진 주인)와 B(부재한 주인)를 둘 다 덮는다. 약한 규칙(명부 존재만)은 A 를
못 덮고, 사용자가 든 예가 A 다.

### 4.2 CG2 — 판정을 템플릿에 둔다 (판정 위치는 **유지**, 귀결은 CG8 로 교체)

```js
// 카드가 가리키는 대시보드의 주인 세션이 이 카드에 보이는가(결정 CG1~CG3). 순수 함수 —
// DOM 에 닿지 않는다. visibleSessions 는 renderProject 가 이미 계산한 값이다.
function isTier1OwnerVisible(project, visibleSessions){
  if(!project.tier1) return false;                  // 대시보드 자체가 없다 — 이 판정의 대상이 아니다
  if(!project.tier1.session_id) return true;        // 레거시 단일 파일 — 주인이 원리적으로 없다(CG3)
  for(var i = 0; i < visibleSessions.length; i++){
    if(visibleSessions[i].session_id === project.tier1.session_id) return true;
  }
  return false;
}
```

**왜 파이썬이 아닌가** — (1) 가시성은 클라이언트 전용이다(`shouldRenderSession` 이
`Date.now()` 와 스냅샷에 없는 `STALE_SESSION_HIDE_AFTER_MS` 를 쓴다). (2) 층을 쪼개면 한
질문에 술어가 둘이 되고, 파이썬 쪽 절반은 실측 A 를 못 덮어 단독으로 무용하다. (3)
`renderProject`·`sessionRowAttributes` 주석이 이미 「서버는 사실만, 표시 판정은 여기서」를
관례로 명시한다(GN4·CD3). `project.tier1.session_id` 는 스냅샷 JSON 에 실려 있다(실측 확인).

**대가**: 이 저장소에는 `hub_template.html` 의 JS 를 실행하는 테스트 메커니즘이 없다
(node/jsdom 부재). 커버리지는 grep 가드 + 수동 확인이다(T25-220 MEDIUM-2 선례).

> **1회차의 배선 부분은 반려됐다** — `isClickable` 에 이 술어를 연접해 클릭을 막는 부분.
> 사용자 판정: 「경고만 띄우고 열리게」. CG8 이 그 자리를 대신한다.

### 4.3 CG3 — 레거시 단일 파일은 면제한다 (유지)

`tier1.session_id === null` 이면 주인 세션이 원리적으로 없다. 면제하지 않으면 모든 레거시
프로젝트 카드에 영구히 경고가 붙는다. `is_project_tier1_from_finished_session_task` 도 같은
자리에서 같은 이유로 False 를 준다.

**한계**: 라이브에 `tier1.session_id is None` 인 프로젝트가 0개라 이 분기는 실측 확인 불가.
레거시 파일 2개의 실재는 확인했다(§1.5). 목업에는 합성 카드로 실었다.

### 4.4 ~~CG4 — `panelEmptyReason` 에 orphan 분기를 추가한다~~ — **철회**

> **1회차**: `PROJECT_ORPHAN_DASHBOARD_REASON` 을 만들어 `panelEmptyReason` 의 맨 앞 분기로
> 넣는다(orphan → FT → `dashboard_key` → tier 설명).
>
> **철회 사유**: orphan 이 더 이상 클릭을 막지 않으므로 그 문구가 `panelEmptyReason` 으로 뜰
> 경로가 **없다**(그 함수는 클릭 불가일 때만 호출되고, 클릭 불가 사유는 FT 와 `!isServed`
> 뿐이다). 상수는 삭제하고 카드 쪽 어휘(CG9)로 대체한다.
>
> **따라서 `panelEmptyReason` 은 1회차 전에 있던 3분기 그대로다 — CD5 는 손대지 않는다.**

### 4.5 ~~CG5 — 툴팁 가드를 파생형으로 바꾼다(필수)~~ — **철회**

> **1회차**: `if(project.dashboard_key && !isClickable && !project.tier1_is_finished_task)` 의
> 게이트 열거를 `if(emptyReason === FILE_MODE_DASHBOARD_HINT)` 로 바꾸는 것이 **필수**라고
> 못 박았다. 근거는 「orphan 게이트가 추가되면 그 카드에 『서버를 켜면 볼 수 있습니다』 툴팁이
> 붙어 패널 사유와 어긋난다」였다.
>
> **철회 사유**: 그 근거는 **orphan 이 클릭을 막는다는 전제에서만** 성립한다. CG8 로 막지 않게
> 되면 클릭 불가 사유는 FT 와 `!isServed` 둘뿐이고, 현행 열거는 정확히 그 둘을 가른다 —
> 지금 코드가 맞다. 「망가지지 않은 것을 리팩토링하지 않는다」에 따라 **건드리지 않는다.**
> 같은 형태의 취약함(게이트가 늘면 갱신해야 한다)이 남아 있다는 관측만 남긴다.

### 4.6 CG6 — tier 1 진행 표시 (재해석: 그대로 그리되 **경고를 얹는다**)

1회차 CG6 은 「tier 1 진행 표시는 손대지 않는다」였고, 그 근거는 「클릭이 막히고 패널이 사유를
말하므로 카드에 예고할 필요가 없다」였다. **클릭을 막지 않게 되면 그 근거가 사라진다** —
카드가 오해를 만드는 유일한 지점이 그 진행 줄이고, 클릭해도 대시보드가 그대로 열리므로
경고를 받을 자리가 없다. 그래서 진행 줄 자체는 계속 그리되(값은 참이다) **그 줄에 경고
표지를 붙인다**(CG9).

### 4.7 CG7 — 세션 행은 무변경 (유지, 재확인)

세션 행의 `dashboard_key` 는 `_session_dashboard_key(session_dashboards_by_id.get(session_id))`
에서 오므로 **그 세션 자기 대시보드**이고(결정 ST12), 세션 행은 `visibleSessionsOf` 를 통과한
세션에만 그려진다. 「주인이 화면에 없다」가 원리적으로 성립하지 않는다. 클릭 게이트를 아예
건드리지 않게 된 2회차에서는 더 명확히 무변경이다.

### 4.8 CG8 — 클릭을 막지 않는다 (신설, **사용자 판정 반영**)

`isClickable` 은 **오늘 코드 그대로**다:

```js
var isClickable = Boolean(project.dashboard_key) && isServed && !project.tier1_is_finished_task;
```

orphan 연접을 넣지 않는다. 대시보드는 열린다. 파일도, 직접 URL 도 그대로다.

### 4.9 CG9 — 경고는 **카드의 진행 줄**에 놓는다 (신설)

**어디에 놓는가 — 카드다.** 오해를 만드는 문장이 카드에 있기 때문이다. 카드는
`「화면 숨김 요소 정리 검토 — 4/4 · 100%」` 를 그 프로젝트의 현재 상태처럼 보여주는데,
그것을 쓴 세션은 화면에 없다. 사용자가 클릭하지 않으면 패널의 어떤 문구도 닿지 못한다.

**표현 — 기존 어휘를 그대로 재사용한다(새 CSS 토큰 0개).** GN5 가 만든 두 장치가 정확히 같은
일을 한다:

1. `.tier1-prev-label` 칩 — `color:var(--attention);font-weight:800` + `::after{content:" · "}`.
   **클래스를 그대로 쓰고 텍스트만 바꾼다.**
2. 톤다운 — `.card[data-tier1-previous]>.tier1-pct{color:var(--muted)}` 계열. 카드에
   `data-tier1-orphan="1"` 을 붙이고 **같은 선언을 가진 규칙 2줄을 추가**한다.

```css
/* 주인 세션이 카드에 없는 대시보드(결정 CG9) — GN5 의 톤다운과 같은 선언을 쓴다. 셀렉터
   목록에 합치지 않고 규칙 2줄을 따로 두는 이유: T25-88 이
   '.card[data-tier1-previous]>.tier1-pct{color:var(--muted)}' 를 **리터럴 그대로** 검사하므로
   셀렉터를 합치면 그 가드가 깨진다. 선언 중복은 그 가드를 살리기 위한 의도된 선택이다. */
.card[data-tier1-orphan]>.tier1-pct{color:var(--muted)}
.card[data-tier1-orphan]>.tier1-active{color:var(--muted)}
```

**문안** — 칩은 짧게, 전문은 툴팁으로(PV4 관례: 「접히는 문구의 전문은 `data-tooltip` 이
보존한다」):

```js
var TIER1_PREVIOUS_TASK_LABEL = '이전 작업';          // 기존 인라인 리터럴을 상수로 승격(GN5, 값 불변)
var TIER1_ORPHAN_LABEL = '주인 세션 없음';
var TIER1_ORPHAN_TOOLTIP = '이 진행률은 이 카드에 보이지 않는 세션이 발행한 대시보드의 것입니다 — '
  + '그 세션은 목록에서 사라졌거나 오래돼 숨겨졌습니다. 카드를 누르면 그 대시보드가 열립니다.';
```

툴팁 마지막 문장이 「그래도 열린다」를 말한다 — 경고가 차단으로 오해되지 않게 한다.

**`renderTier1` 의 2번째 인자를 라벨 문자열로 바꾼다.** 지금은 boolean 이고 라벨이 함수 안에
인라인돼 있어 두 번째 라벨을 넣을 자리가 없다.

```js
function renderTier1(tier1, prevLabelText, prevLabelTooltip){ … }
```

호출부는 2곳뿐이다 — `renderProject`(라벨 계산), `renderSessionProgress`(`''`, 오늘과 동일).

**둘이 동시에 참이면 orphan 이 이긴다.** `tier1_is_previous_task`(GN1: 살아 있는 세션보다
오래된 세대)와 orphan 은 독립이고 함께 참일 수 있다. orphan 이 더 강한 진술이다 —
「주인이 화면에 없다」는 「진행 중 세션보다 오래됐다」를 실질적으로 포함하고, GN1 의 패널
안내 문구(「지금 진행 중인 세션이 시작된 뒤 갱신되지 않았습니다」)는 주인이 화면에 없을 때
가리킬 대상이 없다(FT4-(c)·CD4 와 같은 형태의 판단). 칩은 하나만 나온다.

### 4.10 CG10 — 패널에는 아무것도 추가하지 않는다 (신설)

검토한 세 자리 중 둘을 기각한다.

- **기각 — 패널 상단 띠(`#dzh-detail-note`)에 `<p>` 를 하나 더 둔다.** `.detail-note` 는
  `visibility:hidden` 으로 숨긴다(`display:none` 이 아니다) — 토글 시 iframe 리플로우를
  막으려는 의도적 설계다. 따라서 `<p>` 를 하나 더 두면 **경고가 없는 모든 패널에서 약 28px
  이 영구히 사라진다.** 드문 경우를 위해 상시 비용을 내는 거래다.
- **기각 — 같은 `<p>` 의 텍스트를 카드 속성으로 실어 나른다.** GN6 의 기존 기제(정적 텍스트 +
  같은 문자열의 `data-tooltip`)를 속성 전달형으로 바꾸는 개편이고, 패널 IIFE·정적 body·
  관련 가드까지 4곳이 움직인다. 이 경고는 **부차 채널**이라 그 비용을 정당화하지 못한다.
- **채택 — 추가하지 않는다.** 카드 경고(CG9)가 오해가 생기는 지점을 덮는다. 그리고 패널이
  실제로 여는 대시보드는 자기 머리에 「갱신: 2026-09-17 15:26」을 스스로 적고 있어 패널
  안에서는 세대가 이미 보인다. 결과적으로 **패널 IIFE 는 한 줄도 바뀌지 않는다** —
  `readCardTarget` 도 `data-tier1-orphan` 을 읽지 않는다(그 속성은 CSS 스코프 전용이다).

### 4.11 CG11 — CD7 의 번복인가? **아니다 — CD7 이 스스로 열어 둔 문이다** (신설)

직전 라운드의 결정 CD7 원문:

> **결정 CD7 — GN5 의 카드 라벨(`이전 작업` + 톤다운)은 이 판정에 적용하지 않는다.**
> 이유: (a) 사용자 요청은 **클릭 동작**이다. (b) 카드가 보여주는 티어 1 요약은 그 대시보드가
> 실제로 말하는 것 그대로라 거짓이 아니다. (c) `data-tier1-previous` 속성 하나가 CSS 스코프와
> 패널 인계를 겸하고 있어(GN4), 다른 판정을 같은 속성에 얹으면 패널 안내 줄(GN6 문구)까지
> 잘못 딸려 온다. **필요해지면 별도 속성으로 나중에 더한다(YAGNI).**

세 조건을 하나씩 대조한다.

- **(a) 는 이번에 반대로 뒤집혔다** — 사용자 요청이 「경고를 띄우고 열리게」로, 클릭 동작이
  아니라 **표시**가 됐다. CD7 의 전제가 이번 라운드에 성립하지 않는다.
- **(b) 는 좁혀진다** — 요약 문장 자체는 여전히 참이다(그래서 CG9 는 값을 지우거나 고치지
  않는다). 거짓인 것은 **함의**(이것이 이 프로젝트의 현재 상태다)이고, 그 함의를 깨는 최소
  수단이 라벨이다.
- **(c) 는 그대로 존중한다** — `data-tier1-previous` 에 얹지 않고 **별도 속성
  `data-tier1-orphan`** 을 쓴다. 그래서 GN6 문구가 딸려 오지 않는다(CG10 이 패널을 손대지
  않는 것과 같은 결과).

따라서 이것은 **CD7 의 번복이 아니라 CD7 이 명시한 「필요해지면 별도 속성으로 나중에
더한다」의 실행**이다. CD7 은 「지금은 필요 없다」였고, 이번 라운드가 그 「필요해지면」이다.
CD7 은 수정하지 않고 그대로 둔다 — 그 결정이 다룬 FT 판정에는 여전히 카드 라벨을 붙이지
않는다(FT 로 막힌 카드는 클릭 시 사유가 뜨므로 CD7 의 (b)·(c)가 그대로 유효하다).

### 4.12 CG12 — FT 와 orphan 이 동시에 참인 카드 (신설)

`notebook-model` 이 그 카드다(FT true + 주인 숨김). 두 장치가 **다른 채널**로 나타난다:

| 채널 | 무엇이 뜨나 | 누가 켰나 |
|---|---|---|
| 카드 진행 줄 | 「주인 세션 없음 · 도형·차트 객체 지원… — 4/4 · 100%」 + 톤다운 | orphan (CG9) |
| 카드 클릭 → 패널 | 「이 카드가 가리키는 대시보드는 완료된 이전 작업입니다 — 그 세션은 그 뒤로도 작업을 계속했습니다.」 | FT (CD4·CD5, 무변경) |
| 카드 툴팁 | 없음 (`isServed` 이므로) | — |

모순이 아니다 — 카드 라벨은 **누가 썼나**를, 패널 사유는 **끝난 작업인가**를 말한다. 두
문장이 한 화면에 동시에 나오지도 않는다(하나는 카드, 하나는 패널). 우선순위를 정할 필요가
없는 것이 이 배치의 장점이다.

### 4.13 화면 변화 전수 — 무엇이 **새로 보이는가**

클릭 가능 여부는 **어느 카드도 바뀌지 않는다.**

| 프로젝트 | 클릭 | 카드에 새로 보이는 것 | 패널 |
|---|---|---|---|
| coding-harness | 가능 (불변) | **없음** — 주인 `02185cdc` 가 보인다 | 불변 |
| atlas-ui-notebook-micro | 가능 (불변) | 「**주인 세션 없음**」 칩 + 진행 줄 톤다운 | 불변(대시보드 열림) |
| daily-brief | 가능 (불변) | 「**주인 세션 없음**」 칩 + 톤다운 | 불변 |
| NotebookWiki | 가능 (불변) | 「**주인 세션 없음**」 칩 + 톤다운 | 불변 |
| notebook-model | **불가 (불변 — FT)** | 「**주인 세션 없음**」 칩 + 톤다운 | 불변(FT 사유) |
| 레거시 단일 파일 프로젝트 | 가능 (불변) | **없음** — CG3 면제 | 불변 |

5개 티어 1 중 **4개에 칩이 새로 붙는다.** 1회차(3개 차단 + 1개 사유 교체)와 달리 **기능이
줄어드는 카드가 없다.**

---

## 5. 데이터 모델과 인터페이스

### 5.1 서버 (파이썬 — ★순수 계약 유지)

```python
# hub_parse.py  (★순수 — 파서는 이 값을 채우지 않는다)
@dataclass(frozen=True)
class Tier1Snapshot:
    ...
    source_path: str = UNSET_SOURCE_PATH
    session_id: str | None = None
    # 이 대시보드가 기록하는 **작업이 시작된 시각**(결정 RL8) = `{토큰}.init-values.json` 의
    # mtime. source_path·session_id 와 같은 계열이다 — 파서는 채우지 않고 hub_collect 가
    # dataclasses.replace 로 덮어쓴다(결정 ST10 의 선례). 사이드카가 없으면 None(폴백).
    task_started_at_ms: int | None = None


# hub_project.py  (★순수)
INIT_VALUES_FILE_NAME_PATTERN = re.compile(r"\A(?P<token>[0-9a-f]{8})\.init-values\.json\Z")
"""`/dashboard init` 4-a 가 남기는 사이드카 파일명 → 세션 토큰(결정 RL8).
토큰 규칙은 commands/dashboard.md 의 `session_id.split("-", 1)[0]` 과 같아야 한다."""

def session_token_from_init_values_file_name(file_name: str) -> str | None:
    """`<8자리 hex>.init-values.json` 이면 그 토큰, 아니면 None."""

def session_token(session_id: str) -> str:
    """세션 ID → 사이드카 토큰. `split("-", 1)[0]` — 헬퍼의 규칙을 그대로 쓴다."""


# hub_session.py  (★순수)
@dataclass(frozen=True)
class SessionFacts:
    ...
    subagents: tuple[SubagentFact, ...]
    last_prompt_at_ms: int | None = None      # 결정 RL1 — 맨 뒤, 기본값 있음

def previous_task_boundary_ms(
    tier1: Tier1Snapshot | None,
    last_prompt_at_ms: int | None,
    is_dashboard_enabled: bool,
) -> int | None:
    """실행 목록의 작업 경계(결정 RL8·RL10) — §3.7 의 네 갈래."""
```

- `compute_session_view` 에 **`is_dashboard_enabled: bool = True` 인자 1개**가 늘어난다
  (기본값 `True` = 오늘의 동작 → 기존 호출부 무해). 본문에서 경계 유도를
  `previous_task_boundary_ms(tier1, facts.last_prompt_at_ms, is_dashboard_enabled)` 한 줄로
  교체한다. 이 값은 **판정에 쓰고 뷰에 싣지 않는다** — `live_roster` 와 같은 계열(결정 LS4)
  이라 스냅샷 JSON 이 커지지 않는다.
- `hub_project._session_views_for_path`·`_project_view_for_path` 가 그 값을 실어 나른다
  (판단 없이 전달 — `live_roster`·`subagent_meta_by_agent_id` 와 같은 관례).
- `summarize_agent_runs` 의 시그니처는 불변 — `is_previous_task` 산식에 `and not is_running`
  연접만 늘어난다.
- `is_session_tier1_from_finished_task` 는 시그니처·본문 불변(RL5).

### 5.2 수집 (`hub_collect.py` — I/O 레이어)

**(1) 사이드카 mtime** — `read_session_dashboard_snapshots` 의 **기존
`sorted(dashboards_dir.iterdir())` 1회** 안에서 함께 본다. 그 열거는 이미 사이드카 파일을
돌려주고 있다(실측: 같은 디렉토리에 `*.html` 과 `*.init-values.json` 이 나란히 있다) —
**추가 디렉토리 조회 0회**, 사이드카당 `stat()` 1회다.

```
1) 같은 순회에서 token → mtime_ms 맵을 만든다(session_token_from_init_values_file_name 통과분).
2) 스냅샷을 만들 때 dataclasses.replace(..., task_started_at_ms=map.get(session_token(session_id)))
3) stat 실패는 그 항목만 None(경고 1건) — 기존 파일 단위 예외 처리와 같은 형태.
```

**(2) `dashboard_enabled`(RL10)** — 새 함수 하나. 프로젝트 루트당 파일 1개를 읽는다.

```python
PROJECT_LOCAL_SETTINGS_RELATIVE_PATH = ".claude/settings.local.json"

def read_dashboard_enabled(project_path: str) -> bool:
    """프로젝트의 /dashboard 오프 스위치를 읽는다(결정 RL10). 기본값은 **켜짐**이다 —
    파일·필드가 없거나, 읽기·파싱이 실패하거나, 값이 bool 이 아니면 True.
    commands/dashboard.md 「off 스위치」·rules/workflow/role-separation.md 가 정본이다.
    """
```

**페일 방향을 켜짐으로 고정한다** — 읽기 실패로 조용히 `False` 가 되면 그 프로젝트의 실행
목록이 영구히 초기화되지 않는데, 그것은 이 PRP 가 고치려는 결함 자체다.

수집 예산(`collect_snapshot` 50ms 에스컬레이션)에 대한 영향: 프로젝트당 `stat()` 몇 번 +
작은 JSON 1개다. 프로젝트 수는 실측 6개.

### 5.3 클라이언트 (`hub_template.html` — 전부 순수 함수)

3회차에 **변경 없음**. 2회차 확정분 그대로다:

```js
var TIER1_PREVIOUS_TASK_LABEL = '이전 작업';       // 인라인 리터럴 승격(값 불변)
var TIER1_ORPHAN_LABEL = '주인 세션 없음';          // CG9
var TIER1_ORPHAN_TOOLTIP = '…';                    // CG9
function isTier1OwnerVisible(project, visibleSessions){ … }          // CG2
function renderTier1(tier1, prevLabelText, prevLabelTooltip){ … }    // CG9
```

`renderProject` 는 ① `isTier1OwnerVisible` 호출 ② 라벨 계산(orphan 우선) ③
`data-tier1-orphan` 속성 ④ `renderTier1` 호출 인자 — 네 곳이 바뀐다. `isClickable`·
`panelEmptyReason` 호출·툴팁 가드는 **불변**이다.

---

## 6. UX 변화 (프리뷰 목업이 정본)

### 결함 1 — 세션 `02185cdc`

```
현재                                        제안 RL8
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│ ● 작업중   방금                   │        │ ● 작업중   방금                   │
│ 시작 14:27  02185cdc  Opus 5·max │        │ 시작 14:27  02185cdc  Opus 5·max │
│ ┌ 설계  Design hub gen…   1분 ┐  │        │ ┌ ● 설계  Design hub gen…  1분 ┐ │
│ │ 구현  리베이스 충돌 해결  20분 │  │        │ └───────────────────────────────┘ │
│ │ 검수  R2 재검수 — 가드    1분 │  │        │  (11:42 init 이전 실행 6건 빠짐)  │
│ │ 구현  검수 MEDIUM 2건    32분 │  │        │                                  │
│ │ 검수  허브 UI 4건 검수   24분 │  │        │ 설계 — design-architect 디스패치  │
│ └ +2건 더 ──────────────────┘  │        │ 동일 세션에서 새 질의 시작 시…     │
└──────────────────────────────────┘        └──────────────────────────────────┘
```

### 결함 1 — 반례 B (`7ba572b2`, 승인 직후)

```
RL6 (반려)                                  RL8 (권고)
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│ (실행 목록 없음 — 설계가 지워짐)   │        │ ┌ 설계  숨김 요소 제거 설계 19분 ┐│
│                                  │        │ └───────────────────────────────┘ │
│ 설계 — 승인 대기                  │        │ 설계 — 승인 대기                  │
└──────────────────────────────────┘        └──────────────────────────────────┘
```

### 결함 2 — 카드 경고

| 접점 | 현재 | 제안 CG |
|---|---|---|
| 카드 진행 줄 | `제목 — 4/4 · 100%` (강조색) | **`주인 세션 없음 · 제목 — 4/4 · 100%`** (톤다운) |
| 칩 툴팁 | 없음 | 전문 + 「카드를 누르면 그 대시보드가 열립니다」 |
| 카드 커서·hover | pointer / accent 테두리 | **동일** |
| 카드 클릭 | 대시보드 열림 | **동일 — 열림** |
| 패널 | 대시보드 iframe | **동일** |
| 세션 행 | 변화 없음 | 변화 없음 |
| 레거시 단일 파일 | — | **경고 없음**(CG3) |

---

## 7. 테스트 계획

### 7.1 `tests/run.sh` 소스 가드 (신설 2 · 개정 1)

**새 가드 ID 는 `T25-222` 부터** — 현재 최댓값이 `T25-221` 이다.

**T25-222 (신설 — 결정 RL1~RL5 · RL8 · RL10)** · 그룹 T25 / `test_hub_docs_and_constants`

| # | 무는 것 | 검사 |
|---|---|---|
| ① | `SessionFacts` 의 필드 | `grep -qF 'last_prompt_at_ms: int \| None = None'` in `hub_session.py` |
| ② | 훅 분기가 그 값을 채운다 | `_apply_tracked_event` 본문(awk)에 `last_prompt_at_ms = event.received_at_ms` |
| ③ | `Tier1Snapshot` 의 필드 | `grep -qF 'task_started_at_ms: int \| None = None'` in `hub_parse.py` |
| ④ | 경계 유도가 순수 함수 1곳이다 | `hub_session.py` 에 `def previous_task_boundary_ms(` 가 있고 `compute_session_view` 본문이 그것을 호출한다 |
| ⑤ | 네 갈래가 다 있다 | 그 함수 본문(awk)에 `task_started_at_ms` · `TIER1_FINISHED_PERCENT` · `max(` · `is_dashboard_enabled` 가 각 1건 이상 |
| ⑥ | **역** — FT 파생 경계가 되살아나지 않았다 | `compute_session_view` 본문에 `tier1.file_mtime_ms if` 가 **0건** |
| ⑦ | 실행 중 면제(RL3) | `summarize_agent_runs` 본문에 `and not is_running` |
| ⑧ | `tier1_is_finished_task` 는 살아 있다(RL5) | `compute_session_view` 본문에 `is_session_tier1_from_finished_task(` 1건 이상 |
| ⑨ | 사이드카 파일명 규약이 `commands/dashboard.md` 와 같다 | `hub_project.py` 의 `.init-values.json` 리터럴이 `commands/dashboard.md` 에도 있다(T25-158 의 관용구 — 양쪽에서 추출해 대조) |
| ⑩ | 수집이 추가 디렉토리 조회를 하지 않는다 | `read_session_dashboard_snapshots` 본문에 `iterdir()` 가 **1건** |
| ⑪ | **RL10 의 스위치 이름·경로가 정본과 같다** | `hub_collect.py` 의 `dashboard_enabled` · `.claude/settings.local.json` 두 리터럴이 `commands/dashboard.md` 와 `rules/workflow/role-separation.md` 에도 있다 |
| ⑫ | **RL10 의 페일 방향이 켜짐이다** | `read_dashboard_enabled` 본문(awk)에 `return True` 가 있고 `except` 분기에서 `return False` 가 **0건** |
| ⑬ | README 서술 | `hub/README.md` 에 「작업이 시작된 뒤에 시작된 실행만 남는다」 와 「대시보드를 끈 프로젝트」 |

⑥과 ⑫가 이 가드의 핵심이다 — ④만 검사하면 옛 FT 경계를 함께 쓰는 형태로 조용히 되돌아갈 수
있고, ⑫가 없으면 읽기 실패가 조용히 「끈 것」으로 바뀌어 기능 전체가 무음으로 죽는다.

**T25-223 (신설 — 결정 CG1~CG3 · CG8~CG12)** · 그룹 T25 / `test_hub_docs_and_constants`

2회차 확정 그대로다(10개 서브체크 — ①라벨·툴팁 상수 ②`visibleSessionsOf` 가
`isTier1OwnerVisible` 보다 앞줄 ③레거시 면제 분기 ④**역**: `isClickable` 산식에
`isTier1OwnerVisible` 0건 ⑤**역**: `panelEmptyReason` 에 orphan 0건 ⑥톤다운 CSS 2줄 리터럴
⑦**역**: GN5 리터럴 보존 ⑧별도 속성 ⑨**역**: `readCardTarget` 에 `data-tier1-orphan` 0건
⑩README).

**T25-220 개정 (기존 가드 — PT1 번복 반영)**

`compute_session_view` 안에서 「FT 판정이 `summarize_agent_runs` 호출보다 앞줄」을 검사하는
서브체크는 RL2 로 **제약 자체가 사라진다**. 자리를 지우지 않고 **무는 대상을 바꾼다** —
「`summarize_agent_runs` 호출이 `previous_task_boundary_ms(` 로 유도한 경계를 받는다」로.
나머지 서브체크(필드·인자·`visibleAgentRunRows` 경유·`currentTaskRunCount` 일치·`30*60`
리터럴 부재·README)는 **전부 그대로 유효하다**. 기존 원장 행 `T25-220` 도 그대로 유효하다.

### 7.2 `tests/mutations.tsv` 원장 (변조행 2건 추가)

현황 733행 / 변조행 518. 8열 탭 구분, `anchor_function` 은 `test_hub_docs_and_constants`.

| guard_id | target_path | mutation_sed | expect_group | expect_token |
|---|---|---|---|---|
| `T25-222` | `hub/bin/hub_session.py` | `s/if not is_dashboard_enabled:/if False:/` | `T25` | `previous_task_boundary_ms() 에 is_dashboard_enabled 갈래가 없음` |
| `T25-223` | `hub/bin/hub_template.html` | `s/\.card\[data-tier1-orphan\]>\.tier1-pct{color:var(--muted)}//` | `T25` | `.card[data-tier1-orphan]>.tier1-pct 톤다운 규칙이 없음` |

- 두 `mutation_sed` 모두 `[주소]s/…/…/` 형태이고 `w`·`W`·`r`·`R`·`e` 플래그가 없어
  `mutation_sed_is_write_safe` 를 통과한다.
- **판별력**: T25-222 변조는 RL10 갈래를 죽여 서브체크 ⑤(`is_dashboard_enabled` 1건 이상)를
  깨뜨리고 ①②③④⑥⑦⑧⑨⑩⑪⑫는 건드리지 않는다(⑫는 `read_dashboard_enabled` 본문을 보고,
  변조 대상은 `hub_session.py` 다). T25-223 변조는 톤다운 규칙 1줄을 지워 ⑥을 깨뜨리고
  ⑦(GN5 리터럴)은 다른 문자열이라 살아 있다.
- **expect_token 규약**: 각 토큰이 `tests/run.sh` 의 실패 보고 호출 줄에 **정확히 1건**만
  나와야 한다. 위 두 문구는 기존 메시지와 겹치지 않는다.
- T37-13 이 토큰을 `anchor_function` 몸통에서도 찾으므로 두 가드는 반드시
  `test_hub_docs_and_constants()` 안에 둔다.

### 7.3 `tests/hub` 단위 테스트 (stdlib unittest, 순수 로직)

**`test_hub_session.py`** — 경계 유도가 순수 함수라 표 주도 테스트가 가능하다.

| 테스트 | 입력 | 기대 | 대응 |
|---|---|---|---|
| `test_build_session_facts_records_last_prompt_time` | 프롬프트 2건(t=100, 300) | `300` | RL1 |
| `test_build_session_facts_last_prompt_none_without_prompt` | 프롬프트 없음 | `None` | RL4 |
| `test_boundary_uses_task_start_while_task_in_progress` | `task_started_at_ms=200`, `percent=50`, 프롬프트 900 | `200` | **반례 B** |
| `test_boundary_uses_later_of_task_start_and_prompt_when_finished` | `…=200`, `percent=100`, 프롬프트 900 | `900` | RL8-(b) |
| `test_boundary_uses_task_start_when_finished_without_prompt` | `…=200`, `percent=100`, 프롬프트 `None` | `200` | RL8-(b) `max` |
| `test_boundary_falls_back_to_prompt_without_tier1` | `tier1=None`, 프롬프트 900, **enabled=True** | `900` | **반례 A** |
| `test_boundary_falls_back_to_prompt_without_sidecar` | `task_started_at_ms=None`, 프롬프트 900, enabled=True | `900` | RL8-(c) |
| `test_boundary_none_when_dashboard_disabled` | `tier1=None`, 프롬프트 900, **enabled=False** | `None` | **RL10 / 반례 B** |
| `test_boundary_ignores_disabled_flag_when_dashboard_present` | `task_started_at_ms=200`, `percent=50`, enabled=False | `200` | RL10 범위 한정 |
| `test_boundary_none_without_any_signal` | `tier1=None`, 프롬프트 `None`, enabled=True | `None` | RL4 |
| `test_runs_before_task_start_are_previous` | 경계 200, 실행 100~150 | `True` | RL8 |
| `test_running_run_before_boundary_is_not_previous` | 경계 200, 실행 100·미종료·좀비 아님 | `False` | RL3 (22.7%) |
| `test_zombie_run_before_boundary_is_previous` | 위 + 90분 초과 | `True` | RL3 경계 |
| `test_tier1_is_finished_task_unchanged` | FT 참 조건 | `True` | RL5 회귀 |

`test_boundary_ignores_disabled_flag_when_dashboard_present` 가 RL10 의 범위를 고정한다 —
스위치를 껐어도 대시보드가 **있으면** (a)/(b)가 이긴다(사용자가 끈 뒤 남은 파일로 판정하지
않는다는 뜻이 아니라, 그 작업에 대한 선언이 실재하면 그것을 쓴다는 뜻이다).

**`test_hub_project.py`** — `session_token_from_init_values_file_name` 통과·탈락
(`02185cdc.init-values.json` → `"02185cdc"` / `02185cdc-285f-….html` → `None` /
`init-values.json` → `None` / 대문자 hex → `None`), `session_token` 이 헬퍼 규칙과 같다.

**`test_hub_collect.py`** — 임시 디렉토리에
① `{uuid}.html` + `{앞8자}.init-values.json` → `task_started_at_ms` 가 사이드카 mtime,
② 사이드카 없음 → `None`, ③ 무관한 토큰의 사이드카는 join 되지 않음,
④ `read_dashboard_enabled`: 파일 없음 → `True` / `{}` → `True` /
`{"dashboard_enabled": false}` → `False` / `{"dashboard_enabled": "false"}`(문자열) → `True` /
깨진 JSON → `True` / 권한 오류 → `True`.
(`EVENTS_DIR` 치환 관례와 같은 `setUp`/`tearDown` 형태.)

**CG(결함 2)에는 단위 테스트가 없다** — §4.2 의 기록된 한계다.

### 7.4 검증 명령 (정본 — `CLAUDE.md` §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

기대: 전부 rc=0.

### 7.5 수동 확인 (클라이언트 판정 — 단위 테스트 밖)

1. `/hub server start` 후 `http://localhost:8794/hub.html`.
2. coding-harness 카드의 첫 세션 실행 목록이 **이번 작업(`init` 이후) 실행만** 담는지.
3. 새 작업을 `/dashboard init` 으로 시작한 직후 목록이 비고, 첫 디스패치에 다시 채워지는지.
4. **설계 → 승인 → 구현 흐름에서 승인 직후 설계 실행이 남아 있는지**(반례 B).
5. 서브에이전트가 도는 중 메시지를 큐에 넣고 진행 중 실행이 사라지지 않는지(RL3).
6. **`/dashboard off` 한 프로젝트에서 실행 목록이 초기화되지 않는지**(RL10). 확인 후 되돌린다.
7. atlas · daily-brief · NotebookWiki · notebook-model 카드에 「주인 세션 없음」 칩 + 톤다운이
   뜨고, **클릭하면 대시보드가 그대로 열리는지**(notebook-model 만 FT 사유).
8. coding-harness 카드에는 칩이 뜨지 않는지. 320px 최소 트랙에서 칩이 카드를 깨뜨리지 않는지.

---

## 8. 리스크와 대안

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| **대시보드가 켜져 있는데 사이드카가 없는 작업**(리텐션 소실 · `init` 미호출)에서 반례 B 재발 | 낮 | 중 | **남는 구멍임을 명시**(§3.11). RL3 이 진행 중 실행 구제. 닫는 신호가 §1.9 전수에 없다 |
| RL10 의 스위치 읽기 실패가 조용히 「끔」이 된다 | 낮 | **높음**(기능 무음 사망) | 페일 방향을 **켜짐**으로 고정 + T25-222 ⑫가 기계적으로 검사 |
| `init` 보다 먼저 디스패치된 실행이 숨는다 | 낮 | 중 | RL3 안전판. 트리거 표가 `init` 을 착수 보고에 둔다 |
| `init` 없이 새 작업을 시작하면 경계가 머문다 | 중 | 낮 | FT3 계열의 의도된 미검출. 갈래 (b)가 100% 작업을 덮는다 |
| 프로젝트 로컬 설정 읽기가 수집 예산을 먹는다 | 낮 | 낮 | 프로젝트당 작은 JSON 1개(실측 6프로젝트) |
| 「주인 세션 없음」 칩이 진행 줄을 늘려 카드를 압박한다 | — | — | **해소됨** — 2회차 목업 320px 실측에서 한 줄 유지 확인 |
| 클라이언트 판정에 단위 테스트가 없다 | 확실 | 중 | grep 가드 10개 + 원장 변조 1건 + 수동 확인 8항목 |
| 레거시 면제 분기를 실측으로 못 확인했다 | 중 | 중 | T25-223 ③이 분기 존재를 고정. 2회차 목업 합성 카드 |

### 채택하지 않은 대안 (근거 요약)

1. **경계 후보 13종** — §3.8 판정표. 「대시보드 없음」 구성에서 반례 A·B 를 동시에 통과하는
   신호는 **없다**(§1.13).
2. **호스트 명부 `name`/`nameSince`** — 세션 단위(Δ=0, 9/9) + pid 생존 의존 + LS3 번복 비용(§1.10).
3. **전사 `custom-title`·`slug`·TodoWrite** — 전부 세션 단위이거나 미사용(§1.11) + 128KB 창.
4. **git 마지막 커밋** — 세션 귀속 없음(동시 세션 2개 실측), 작업 중 커밋 역실패, WT3 위반(§1.12).
5. **프롬프트 텍스트 분류 · 침묵 간격** — §1.13 의 두 행. 임계값·어휘에 상한이 없다.
6. **`data-started-at` / 새 속성 각인** — §1.7. `commands/` 접촉 + T22 번복 + 분 정밀도.
7. **패널에 경고 띠 추가 · `data-tier1-previous` 재사용 · 1회차 CG2 배선 · 1회차 CG5** —
   §4.4·§4.5·§4.10·§4.11(2회차 확정, 이번 회차 무변경).

---

## 9. 결정 목록

| ID | 결정 | 상태 |
|---|---|---|
| RL1 | 마지막 `UserPromptSubmit` 시각을 `SessionFacts` 에 보존 | 유지 |
| RL2 | FT 게이트 폐지 — 경계를 무조건 넘긴다 | 유지 (**PT1 번복**) |
| RL3 | 실행 중인 실행은 숨기지 않는다 | 유지 (실측 22.7%) |
| RL4 | 신호 없으면 경계 없음(페일오픈) | 유지 |
| RL5 | `tier1_is_finished_task` 는 클릭 게이트용으로 유지 | 유지 |
| ~~RL6~~ | ~~경계 = 마지막 프롬프트 단독~~ | **반려**(1회차 사용자) — 실례 11/11 실패 |
| RL8 | 경계 = 작업 시작 시각(사이드카 mtime) · 끝난 작업은 `max(작업시작, 마지막프롬프트)` · 없으면 폴백 | **(a)·(b) 사용자 이견 없음**, (c)는 RL10 이 좁힌다 |
| RL9 | 세션 줄이 사라질 수 있음을 수용(실측 0건) | 유지 |
| **RL10** | **`dashboard_enabled: false` 인 프로젝트에서는 경계를 두지 않는다(갈래 (d))** | **3회차 신설 · 권고** |
| CG1 | 보이는 세션 중 주인이 없는가 | **확정**(2회차 승인) |
| CG2 | 판정은 템플릿에 둔다 | **확정** (배선은 CG8) |
| CG3 | 레거시 단일 파일 면제 | **확정** |
| ~~CG4~~ | ~~`panelEmptyReason` 에 orphan 분기~~ | **철회** |
| ~~CG5~~ | ~~툴팁 가드를 파생형으로(필수)~~ | **철회** |
| CG6 | tier 1 진행 줄은 그대로 그리되 경고를 얹는다 | **확정** |
| CG7 | 세션 행 무변경 | **확정** |
| CG8 | 클릭을 막지 않는다 | **확정** |
| CG9 | 경고 = 「주인 세션 없음」 칩 + 톤다운, 기존 CSS 재사용 | **확정** |
| CG10 | 패널에는 아무것도 추가하지 않는다 | **확정** |
| CG11 | CD7 의 번복이 아니다 — CD7 이 명시한 별도 속성 경로 | **확정** |
| CG12 | FT·orphan 동시 참은 다른 채널로 공존 | **확정** |

> → **폐기(2026-09-30)** — 위 표의 CG1~CG3·CG6·CG8~CG12 는 §4 머리의 이관 표기를 따른다(hub-session-modal-cleanup.md 결정 MX4).

### 승인이 필요한 판단 1개

**세 번째 신호는 없다**(§1.9~§1.13 전수 조사). 남은 선택은 폴백의 모양이다.

- **권고 = RL10** — 대시보드를 **끈** 프로젝트에서는 아무것도 숨기지 않고, **켜진** 프로젝트에서
  대시보드 파일만 없으면 마지막 프롬프트를 경계로 쓴다. 반례 A(신고한 결함)와 반례 B(보류
  사유)가 **각자의 구성에서** 통과한다. 남는 구멍은 「대시보드를 켜 뒀는데 그 작업에
  `init` 을 안 부른 경우」 하나이고, 그 구멍을 닫는 신호는 존재하지 않는다.
- 대안 A — **폴백을 통째로 수용**(2회차 안): 껐든 켰든 마지막 프롬프트. 끈 프로젝트에서
  반려된 동작이 남는다.
- 대안 B — **대시보드가 없으면 아무것도 숨기지 않는다**: 반례 A, 즉 사용자가 신고한 결함이
  그대로 남는다.

---

## 10. 프리뷰 목업

**3회차에는 화면이 바뀌지 않아 목업을 갱신하지 않았다.** RL10 은 경계 유도식의 갈래 하나를
더하는 서버 측 판정이고, 그 결과는 「실행 줄이 몇 개 보이는가」로 이미 2회차 목업의 결함 1
3열 대조가 표현하는 축이다. CG 절은 이번 회차에 한 글자도 바뀌지 않았다.

2회차 목업(유효, 승인 근거로 그대로 참조):

- 라이트 `…/scratchpad/hub-card-gate-preview-r2.html` · 다크 `…-r2-dark.html`
- 스크린샷 `preview-r2-light.png` · `preview-r2-dark.png` (1400×6400)
- 담은 것: 결함 1 3열(현재 / RL6 반려 / RL8) · 반례 B 2열(`7ba572b2` 승인 직후) ·
  결함 2 프로젝트 5개 현재/제안 짝 + 패널 · 최소 폭 320px · hover · 실제 카드 높이.
- 확인된 것: 칩은 `주인 세션 없음 · {제목} — 4/4 · 100%` 로 렌더되고 라벨만 `--attention`,
  나머지는 `--muted` 다. **320px 에서도 한 줄을 유지한다.**
- 생성기는 `hub_template.html` 의 `<style>` 을 그대로 떼어 얹고 그 뒤에 「제안 CSS」 2줄
  (CG9)을 실제 형태로 붙인다. 마크업은 렌더 함수의 문자열 접합 그대로이며 목업 전용 장치는
  `.mock-` 접두다.
