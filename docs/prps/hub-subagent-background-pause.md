# 허브: 백그라운드 작업을 기다리며 멈춘 세션을 「대기」·「소식 없음」 대신 「백그라운드 대기」로 보여 준다

> 산출: `docs/prps/hub-subagent-background-pause.md`(이번만 세션 스크래치패드에서 작성 — 메인이 전체 검사가
> 끝난 뒤 옮긴다) · 설계 모델: opus(디스패치 기본값)
> 상태: **승인**(2026-09-28) — §11 쟁점 1~3 모두 권고안: 안 B(「◐ 백그라운드 대기」) · 상한 90분 · 착수 전 V0 실측.
> 결정 접두 **BW**(미사용 확인 — `docs/prps/*.md`·`hub/`·`tests/`·`commands/` 전수 grep 0건).
> 신설 정적 가드 예정 번호 **T25-248~T25-253**(T25-245 = main b81ddaa, T25-246·247 = 이 브랜치의 UI 작업
> e89b892). 착수 시점 main 의 최대 번호를 다시 세고 겹치면 뒤로 민다.
> 프리뷰 목업(현재 | 안 A | 안 B — 라이트·다크·최소 트랙 320px 실측·열린 카드·행 hover·툴팁·끝나지 않는
> 셸·상한 경과):
> `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/a74d3843-b65b-47c6-b041-80695c649cf5/scratchpad/prp/hub-subagent-background-pause-mockup.html`
> (전체 PNG 같은 폴더 `hub-subagent-background-pause-mockup.png`, 장면별 `scene-1.png`·`scene-3.png`·`scene-3b.png`·`scene-4.png`)

## 0. 요구사항 요약

서브에이전트가 25~40분짜리 전체 검사(이 저장소의 `bash tests/run.sh`는 Bash 전경 상한 10분을 넘는다)를
백그라운드 셸로 걸어 두고 자기 턴을 끝내면, 호스트는 그 서브에이전트를 「멈춘 채 살려 두었다가」 셸이
끝나는 순간 같은 `agent_id` 로 스스로 재개한다. 그 사이 메인도 턴을 끝내므로 허브가 받는 훅은 하나도 없고,
허브는 그 세션을 「대기」(사용자 지시를 기다림)로, 마지막 이벤트 30분 뒤부터는 「소식 없음」으로 그린다 —
둘 다 틀렸다. 사용자가 할 일은 없고, 세션은 곧 스스로 이어서 일한다. 호스트는 이 구분을 위해 `Stop`·
`SubagentStop` 훅 입력에 `background_tasks`·`session_crons` 배열을 공개 계약으로 싣는다("session is done" vs
"session is paused waiting for background work to wake it back up"). 이 설계는 ① 그 두 배열을 **종류별 개수**로만
이벤트 로그에 남기고(자유 텍스트 0), ② 메인 턴은 끝났지만 세션을 깨울 백그라운드 작업이나 1회성 예약 깨우기가 남아 있으면
새 표시 상태 **「백그라운드 대기」**(◐)로 그리며, ③ 끝나지 않는 작업(dev 서버·`tail -f`)이 세션을 붙잡지
않도록 그 보고 뒤 **90분**까지만 믿는다. 첫 단계로 800줄 상한에 닿은 `hub_session.py` 를 사실 접기(신설
`hub_session_facts.py`)와 표시 판정으로 나눈다(RI13 의 에스컬레이션 이행). 배열이 오지 않는 호스트에서는
오늘과 완전히 같다(페일오픈).

---

## 1. 실측 (2026-09-28, 판단 근거)

측정은 전부 스크래치패드의 `python3 -B` 읽기 전용 스크립트로 했다. transcript 는 **구조 필드만** 출력했다
(`type`·`timestamp`·`origin.kind`·도구 이름·`run_in_background` 불리언·태그 이름) — 대화 본문·명령줄은
보고서에 싣지 않는다. 스크립트(`bw_events.py`·`bw_resume_gaps.py`·`bw_transcript_*.py`·`bw_bundle_*.py`)는
세션 스크래치패드에 있어 영구 보존되지 않으므로 방법을 아래에 재현 가능하게 적는다.

### 1.1 사례 재생 — 세션 768e8a38(데스크톱, 2.1.281)

| 시각(KST) | 훅(이벤트 로그) | 호스트 쪽 사실(transcript 구조 필드) | 허브 표시(오늘) |
|---|---|---|---|
| 13:09:58 | `SubagentStart a91d5… implementer` | 메인이 Agent 도구를 `run_in_background` 로 호출 | 작업중(S) |
| 13:10:10 | `Stop` | — | 작업중(S) |
| 13:34:17·13:35:18 | — | 서브에이전트 transcript: Bash `run_in_background:true` 2회(전체 검사 + 완료 감시 셸) | 작업중 |
| 13:35:34 | `SubagentStop a91d5…` | 서브에이전트 마지막 줄 | 대기(2초 — T·S 모두 없음) |
| 13:35:36 | `UserPromptSubmit` | 메인에 `user` 줄, `origin.kind:"task-notification"`, 태그 `<task-id>a91d5…</task-id>`·`<status>completed</status>`·`<note>This agent stopped with background work of its own still running…</note>` | 작업중(T) |
| 13:36:03 | `Stop` | `system/stop_hook_summary` | **대기** — 명부 `idle` |
| 13:36:03~14:08:30 | **없음** | 메인·서브에이전트 transcript 모두 줄 0 | 14:06:03 부터 **소식 없음 · 직전 대기** |
| 14:08:30 | `SubagentStart a91d5…`(같은 id, SendMessage 없음) | 메인 `queue-operation enqueue`(task-notification) → `remove reason=delivered_to_agent` | 작업중(S) |
| 14:11:04 | `UserPromptSubmit` | `origin.kind:"peer"`·`handback:true`(SubagentHandback 보고 도착) | 작업중 |
| 14:11:11 | `SubagentStop a91d5…` | — | … |

**결론**: 33분 동안 허브가 가진 근거는 "메인 턴 끝남(Stop) + 서브에이전트 끝남(SubagentStop) + 명부 idle"
뿐이었다 — 오늘의 사다리(LS5 idle 행: S 가 없으면 idle)로는 「대기」가 정답이다. 결함은 판정이 아니라
**입력 부재**다. 13:36:03 의 `Stop` 입력에는 호스트 계약상 `background_tasks` 가 실려 있었지만(§1.3) 허브
훅(`_project_fields`)이 `e/s/c/so/r/ai/at`(+StopFailure 의 `er`)만 옮기고 버렸다.

### 1.2 반복 빈도 — 이벤트 로그 전 보존 창(09-21~09-28)

"같은 `agent_id` 의 `SubagentStop` → 다음 `SubagentStart`(재개)" 50쌍 중, 그 공백 동안 **마지막 메인
이벤트가 `Stop`** 인 것(메인이 턴을 끝낸 조용한 구간에서 호스트가 스스로 재개 — SendMessage 재개는 메인 턴
안에서 일어나므로 제외된다) **25건**:

| 항목 | 값 |
|---|---|
| 에이전트 종류 | implementer 22 · code-reviewer 3 |
| 공백 길이(분) | 최소 11.0 · 중앙 25.0 · 최대 **40.1** |
| 30분(stale 문턱) 초과 | **7/25(28%)** — 31.4·32.0·32.0·32.3·32.9·33.2·40.1 |
| 오늘(09-28) | 5건 — 09:32→10:04 · 10:27→10:50 · 10:58→11:31 · 13:35→14:08 · 14:34→15:14 |

25건 모두 공백 전체가 「대기」로, 그중 7건은 끝부분이 「소식 없음」으로 그려졌다. **메인 자신이 띄운
백그라운드 셸**도 같은 결함을 낸다 — 같은 세션 12:04:58 메인이 Bash `run_in_background` → 12:05:11 `Stop` →
12:38:35 `UserPromptSubmit`(task-notification) — 33.4분 공백(이 경우는 서브에이전트 재개가 아니라 메인 알림이라
위 25건에 들지 않는다).

### 1.3 호스트 코드 판독 — 데스크톱 번들 2.1.281

`~/Library/Application Support/Claude/claude-code/2.1.281/claude.app/Contents/MacOS/claude` 에 든 JS 원문을
정규식으로 찾아 읽었다(난독화 이름 — 버전마다 바뀐다).

1. **Stop·SubagentStop 입력 조립(`Y7`)** — 두 배열을 **조건 없이** 싣는다:
   `ve={background_tasks:qIt(h.taskRegistry.all()),session_crons:YIt()}` → `{...Ee,hook_event_name:"SubagentStop",…,...ve}` /
   `{...Ee,hook_event_name:"Stop",…,...ve}`. StopFailure(`bIe`)·SubagentStart 입력에는 없다.
2. **배열 필터(`qIt`)** — `rm(r)`(= `status` 가 `running`·`pending` 이고 `isBackgrounded===false` 가 아님)인 작업만,
   항목은 `{id, type:JWe(type), status, description(≤1000)}` + 종류별(`local_bash`→`command`, `local_agent`→`agent_type`,
   `monitor_mcp`·`mcp_task`→`server`·`tool`, `local_workflow`→`name`). **소유자 필드는 없다.**
3. **종류 라벨(`kpr`)** — `local_agent:"subagent"`·`local_workflow:"workflow"`·`local_bash:"shell"`·`monitor_mcp`/`monitor_ws:"monitor"`·
   `mcp_task:"MCP task"`·`in_process_teammate:"teammate"`·`dream:"dream"`·`auto_mode_scan:"auto-mode scan"`·`remote_agent:"cloud session"`,
   모르면 원 판별자 그대로. Monitor 도구(`local_bash` + `kind:"monitor"`)도 `"shell"` 이다.
4. **작업 등록소는 세션 하나** — 백그라운드 셸 등록(`BSe`)은 `{type:"local_bash",status:"running",isBackgrounded:!0,agentId:<소유 서브에이전트>,…}`를
   호출 문맥의 `taskRegistry` 에 넣고, 자식(서브에이전트) 도구 문맥 팩토리는 `agentId:n?.agentId??…`·
   `isBackgroundAgent`·`queryTracking.depth+1` 과 함께 `taskRegistry:e.taskRegistry` 를 **덮어쓸 수 없게 물려준다**
   (재정의 인자 `n` 에 이 키가 없다). 그래서 메인 `Stop` 의 배열에도 서브에이전트가 띄운 셸이 보인다(문서의 "scoped to the parent
   session"과 일치).
5. **멈춘 서브에이전트** — 제 백그라운드 자식(keepalive 사유 `bash:`·`monitor:`·`workflow:`)이 남은 채 끝나면 작업
   상태는 `completed` 로 바뀌고(`Ch(e)` = completed ∧ keepalive>0), 알림 `<note>`가 위 1.1 의 문장이 된다(`Har(e)`).
   `completed` 는 `rm` 을 통과하지 못하므로 **메인 `Stop` 배열에 그 서브에이전트 자신은 없고 셸만 남는다.**
6. **명부는 이 상태를 구별하지 않는다** — `Tw={running:"busy",requires_action:"waiting",idle:"idle"}`. 호스트 원격
   측정만 `idle` 을 `idle_background`(rm ∧ ¬remote_agent ∧ ¬ambient ∧ ¬parked MCP ∧ ¬idle teammate)로 나눈다 —
   **호스트 스스로 이 상태를 "idle 의 변종"으로 분류한다**(→ 결정 BW5).

### 1.4 transcript 쪽 — 보조 신호 판단용

- 오늘 이 세션의 서브에이전트 멈춤 5건 전부, 메인 transcript 에 `origin.kind:"task-notification"` 줄이 남았고
  본문 태그 `<task-id>` 가 훅 `agent_id` 와 같았다. 반면 서브에이전트가 SubagentHandback 으로 끝나면
  `origin.kind:"peer"`·`handback:true`·`senderTaskId`(구조 필드)가 남는다.
- 그러나 "멈춤"과 "끝남"을 가르는 것은 `<note>` **본문 문장**뿐이다(구조 필드 아님). `handback` 은 auto 모드에서만
  생긴다. `origin.body` 에는 보고 전문이 들어 있다 — **읽으면 안 되는 필드**다.
- README 「프라이버시 고지」는 transcript 판독 필드를 `model·effort·type·isSidechain·isMeta·isApiErrorMessage·
  error·timestamp·quotaLimits.resetsAt` 로 못박고 "`message.content` 는 읽지 않는다"고 약속한다(RI7).

### 1.5 재개 시 시작 시각

`subagents/agent-<id>.meta.json` 은 **재개 때마다 다시 쓰인다** — mtime 이 마지막 `SubagentStart` 와 같다
(a91d5… 15:14:32, a112… 10:53:54, ac6e… 11:31:42). 훅 쪽 `_handle_subagent_start` 도 같은 id 의 시작 시각을
덮어쓴다. 즉 오늘 재개된 실행은 **같은 줄**(agent_id 키)로 이어지고, 표시 시작 시각·경과는 재개 시각부터다.

### 1.6 측정하지 못한 것(→ §8.4 V0·V1)

| # | 전제 | 근거 수준 | 확인 방법 |
|---|---|---|---|
| U1 | 두 배열이 이 기계 2.1.281 의 허브 훅 입력에 실제로 온다 | 코드 판독(1.3-1) | V0 캡처, 또는 배포 뒤 `events/*.jsonl` 의 Stop 줄에 `"bt"` |
| U2 | 서브에이전트가 멈춘 뒤의 **메인** `Stop` 배열에 그 셸이 `"shell"` 로 보인다 | 코드 판독(1.3-4·5) | V0 시나리오 B |
| U3 | 서브에이전트 자신의 `SubagentStop` 배열에 자기 자신이 `subagent` 로 섞인다 | 추정(판정에 쓰지 않음) | V0 |
| U4 | VS Code 진입점(명부에 2.1.283 존재)도 같은 조립 코드 | 미판독 | 배포 뒤 로그 |
| U5 | ScheduleWakeup 이 `session_crons`(recurring=false)로 보인다 | 문서 + 코드(`YIt`) | V0(선택) |

**V0 결과(2026-09-28 16:41~16:42, 데스크톱 번들 2.1.281 CLI · 스크래치패드 cwd · haiku, §8.4 절차 그대로)** —
첫 시도(16:30)는 계정 5시간 사용량 한도로 요청이 거부돼 16:40 초기화 뒤 다시 했다.
- **U1(C1) 확인**: 두 배열 키는 `Stop`·`SubagentStop` 에만 있고 `UserPromptSubmit`·`SubagentStart` 에는 없다.
- **U2(C2) 확인**: 시나리오 B 에서 서브에이전트가 멈춘 뒤(`SubagentStop` 16:42:03) 메인 `Stop`(16:42:06)의
  `background_tasks` 가 `[["shell","running"]]` 이었다. 시나리오 A(메인이 띄운 셸)도 `Stop` 이 `[["shell","running"]]`,
  알림 턴 뒤 `Stop` 은 `[]`.
- **C3 관측**: 같은 `agent_id` 의 `SubagentStart` 가 셸이 끝난 순간(16:42:46) 다시 왔다.
- **U3 확인**: 서브에이전트 자신의 `SubagentStop` 배열에 `["subagent","running"]` 으로 섞였다 — BW4 가 `subagent` 를
  세지 않으므로 판정과 무관하다. 메인 `Stop`(16:42:01, 서브에이전트 실행 중)에도 `subagent` 가 보였다.
- U4·U5 는 관측하지 않았다(배포 뒤 V1 에서 본다).

---

## 2. 비목표

| # | 하지 않는 것 | 이유 |
|---|---|---|
| N1 | 서브에이전트 **실행 줄(칩)** 상태 변경 | 배열이 세션 범위라 소유자를 모른다 — BW7 |
| N2 | transcript `<note>`·`origin` 판독 | `message.content` 미판독 약속(RI7) — BW1 |
| N3 | 새 훅 이벤트(PostToolUse `SubagentHandback` 등) | 이미 설치된 Stop·SubagentStop 이 공개 계약으로 신호를 준다 — `/hub install` 재실행 0 |
| N4 | 백그라운드 작업 출력 파일(`/private/tmp/claude-<uid>/…/tasks/<id>.output`) mtime 생존 판정 | 호스트 비공개 경로 + 작업 id 기록 필요, `tail -f` 는 그래도 영원히 자란다 — 대안 A3 |
| N5 | 끝나지 않는 셸의 식별(명령줄 판독) | 자유 텍스트 — 프라이버시 |
| N6 | 설정 스위치 | RI N1 과 같은 판단 — 고장 대비는 구조(필드 없으면 오늘과 동일)가 맡는다 |
| N7 | 명부 화해 표(LS5)·`is_stale` 계산식 변경 | 새 신호는 사다리의 오버레이로만 들어간다 — BW5 |
| N8 | 재개된 실행의 "첫 시작 시각" 보존 | BW7(b) |

> **개정됨(2026-10-07, [`hub-live-activity.md`](./hub-live-activity.md) 결정 LA6·LA7) — N4 옆.** N4 는 출력 파일 mtime 을
> **생존 판정**에 쓰지 않는다는 비목표이고, 그 판정 쪽은 그대로다. 개정되는 것은 같은 파일의 stat(수정 시각·크기)을
> **판정이 아닌 표시**에 쓴다는 점이다 — 「백그라운드 대기」 세션 첫 줄의 「출력 N분 전 갱신」과 배지 툴팁이다. 경로는
> 호스트가 transcript 의 도구 결과에 적은 문구에서 형태 검증 5조건을 통과한 것만 쓰고, 파일은 열지 않고 `lstat` 만 본다.
> 「`tail -f` 는 그래도 영원히 자란다」는 우려도 그대로이므로 이 값으로 배지 상태나 표시 시한(90분)을 늘리거나 거두지 않는다.

---

## 3. 영향 범위

| 파일 | 조치(단계) | 규모(추정) |
|---|---|---|
| `hub/bin/hub_session_facts.py` **(신설, ★순수)** | M1: `hub_session.py` 의 입력·사실·필터·파싱·접기 절 이동 / M2: `BackgroundReport`·`normalize_background_task_type`·`bt`/`sw` 파싱·접기 규칙 | ~290 이동 + ~75 |
| `hub/bin/hub_session.py` | M1: 위 절 제거·임포트 / M3: `SessionState` 6값, `BackgroundWait`, `effective_background_wait`, `_display_state`, `SessionView.background_wait`, 머리 docstring(RI13 해소) | 799 → ~510 → ~585 |
| `hub/bin/hub_hook.py` | M1: `import hub_session` → `hub_session_facts` / M2: `_background_fields`·`_task_type_counts`, 이벤트 이름 게이트 | 139 → ~180 |
| `hub/bin/hub_project.py` | M1: 임포트 분리 / M3: `PROJECT_STATE_PRIORITY` 6값, `LIVE_SESSION_STATES` | +3 |
| `hub/bin/hub_collect.py` | M1: `hub_session.<사실 심볼>` 8곳 → `hub_session_facts.`, 안 쓰게 된 `import hub_session` 제거 | ±0 |
| `hub/bin/hub_subagent_read.py` · `hub_workflow_read.py` | M1: `from hub_session import SessionFacts[, SubagentFact]` 출처 교체 | 1줄씩 |
| `hub/bin/hub_parse.py`(3곳)·`hub_transcript.py`(1)·`hub_subagent.py`(1) | M1: 주석 속 "`hub_session.py`(훅 이벤트 → 세션 사실)"·`hub_session.parse_event_line`·`EVENT_TIME_MAX_MS` 서술을 새 모듈로 정정 — 동작 무관(`hub_workflow.py`·`hub_live_session.py` 의 서술은 분리 뒤에도 참이라 그대로) | 주석 |
| `hub/bin/hub_template.html` | M4: `STATE_LABEL`·`STATE_GLYPH` 키, 상수 2, CSS 1규칙, 툴팁 순수 함수 1, `stateLabel`·`renderStateBadge` 분기, `SESSION_STATE_ORDER` | +~30 |
| `hub/install.sh` | M1: `HUB_FILE_COUNT` 29 → 30 | 1 |
| `hub/README.md` | M1: 「30개 파일」·파일 배치 / M4: 훅 옵트인·프라이버시 고지·화면 배치(정렬·상태 설명·툴팁 목록·좀비 가드 문단·이전 작업 라벨 문장) | ~+22 |
| `commands/hub.md` | M4: 설치 고지 ① 한 문장, 구현 노트 한 항목 | +3 |
| `docs/prps/hub-dashboard.md` | M1: 모듈 구성표 / M4: 「이벤트 스키마」·「상태 판정 규칙」 개정 블록 | +~18 |
| `tests/hub/test_hub_session_facts.py` **(신설)** | M1: 접기 전용 테스트 클래스 이관(MS9 — 소스 1:테스트 1) / M2: P·N·F 표 | 이관 + ~220 |
| `tests/hub/test_hub_session.py` | M1: 참조 갱신·이관 / M3: L·E 표, 실사례 재생 | +~260 |
| `tests/hub/test_hub_hook.py` | M2: H 표 | +~100 |
| `tests/hub/test_hub_project.py` · `test_hub_collect.py` · `test_hub_template_dom.py` | M1 참조 / M3: P1·P2·W1 / M4: D-BW1 | +~150 |
| `tests/hub/` 참조 갱신 7파일(`test_hub_session` 28줄·`test_hub_project` 26·`test_hub_collect` 8·`test_hub_subagent_read` 8·`test_hub_model` 3·`test_hub_workflow_read` 2·`test_hub_parse` 1) | M1: `hub_session.{HookEvent,SessionFacts,SubagentFact,FailedTurn,parse_event_line,build_session_facts,STOP_FAILURE_EVENT_NAME,EVENT_TIME_MAX_MS}` → `hub_session_facts.`(실측 76줄, `import hub_session_facts` 추가). `template_dom_harness.py` 는 뷰 심볼만 써서 무변경 | 기계적 |
| `tests/run.sh` | M1: 기존 가드 재조준 10건 + T25-253 / M2: T25-248·249 / M3: T25-251·T25-150 기대값 / M4: T25-250·252 / `SOURCE_GUARD_ID_FLOOR` +6 | +~150 |
| `tests/mutations.tsv` | 신설 변조행 6, T25-211·T25-219 행 개정, 머리 인용 개수 | +6 |

**건드리지 않는 것**: `hub_model.py`(스냅샷 계약 불변 — `asdict` 가 새 필드를 싣는다) · `hub_settings.py`(`HOOK_EVENTS`
불변 — 새 훅 없음) · `hub_server*.py`·`hub_daemon.py`·`hub_live_session*.py`·`hub_usage*.py`·`hub_dashboard_*` ·
`rules/`·`CLAUDE.md`(T26 무영향).

---

## 4. 파일 구조와 모듈 경계

```
                       ┌──────────────────────────────────────────────────────────┐
 hub_hook.py (I/O 엔트리) │ _project_fields: 호스트 키 → 짧은 키. bt·sw 는 Stop·SubagentStop 만 │
                       └───────────────┬──────────────────────────────────────────┘
                                       │ 공유 상수·정규화(단일 출처)
 events/*.jsonl ──▶ hub_session_facts.py (★순수, 신설)  parse_event_line → HookEvent
                    │  build_session_facts → SessionFacts   ← 계약(frozen dataclass)
                    ▼
                  hub_session.py (★순수)  compute_session_view: SessionFacts → SessionView
                    │   (_compute_base_state 무변경 · effective_* 오버레이 · _display_state)
                    ▼
                  hub_project.py → hub_model.py → hub_template.html(#dzh-data)
```

- **분리선**: 모듈 머리 첫 줄이 이미 두 책임을 적고 있다 — "훅 이벤트를 세션 사실로 **접고**, 그 사실을 표시
  상태로 **판정**". 앞 절반(입력·사실·필터·파싱·접기, 현 27행·42~105행·202~424행)이 `hub_session_facts.py` 로
  간다. 두 모듈의 계약은 `SessionFacts` 하나다.
- **임포트 방향**: `hub_transcript ← hub_session_facts ← hub_session ← hub_project ← hub_model`.
  `hub_session_facts` 는 `hub_transcript`(오류 종류 정규화) 외 허브 모듈을 임포트하지 않는다(T25-253).
  `hub_hook`·`hub_collect`·`hub_subagent_read`·`hub_workflow_read` 는 사실 심볼을 정의 모듈에서 직접 임포트한다 —
  **파사드·재노출 없음**(MS2 와 같은 원칙). `hub_session.py` 는 자기가 실제로 쓰는 `SessionFacts`·`SubagentFact`
  만 임포트한다.
- **이벤트 로그 짧은 키의 단일 출처**: 쓰는 쪽(`hub_hook`)과 읽는 쪽(`parse_event_line`)이 같은 상수·정규화
  함수를 `hub_session_facts` 에서 가져다 쓴다(RI13 이 `normalize_error_kind` 를 공유 가능한 무순환 위치에 둔
  것과 같은 이유).
- 분리 뒤 줄 수: `hub_session_facts.py` ~365, `hub_session.py` ~585 — 둘 다 T25-100(800) 아래, 이후 확장
  여유 ~200줄씩.

---

## 5. 설계 결정

### 결정 ID 목록

| ID | 한 줄 |
|---|---|
| BW1 | 신호원 = `Stop`·`SubagentStop` 입력의 `background_tasks`·`session_crons`(공개 계약). transcript `<note>`·handback 보조 신호는 기각 |
| BW2 | 기록 = 이벤트 이름으로 가둔 종류별 개수 `bt` + 1회성 예약 수 `sw`. 자유 텍스트·id·status 는 읽지도 않는다 |
| BW3 | 사실 = 가장 최근 **추적** 이벤트가 Stop/SubagentStop 이면 그 보고, 그 밖의 추적 이벤트는 지운다 |
| BW4 | 깨우는 종류 = `shell`·`monitor`·`workflow` + 1회성 예약. `subagent`·`teammate` 는 훅이 이미 추적, 반복 예약은 제외 |
| BW5 | 표시 = 여섯 번째 상태 `"background"`, 사다리 done > interrupted > background(base idle 일 때) > stale > base |
| BW6 | 상한 = 보고 뒤 90분(`BACKGROUND_WAIT_MAX_MS`), 명부 `not_listed` 면 취소 |
| BW7 | 실행 줄은 귀속하지 않는다. 재개는 같은 줄·재개 시각부터(현 동작 유지) |
| BW8 | 프로젝트 우선순위·정렬·live 집합에 편입, glow 는 working 전용 그대로 |
| BW9 | 뷰 계약 = `SessionView.background_wait`(맨 뒤, 정적 정수 4개), 불변식 ⇔ state == background |
| BW10 | 화면 = 프로젝트 「◐ 백그라운드」 / 세션 「◐ 백그라운드 대기」 + 툴팁, 새 색 토큰 0 |
| BW11 | `hub_session.py` 분리를 동작 불변 첫 단계(M1)로 |
| BW12 | 이행 없음 — 새 훅 0, 설정 0, 배열 없으면 오늘과 같다 |

### BW1. 신호원 — 훅 배열(1차), transcript 보조 신호 기각

| 관점 | (a) Stop·SubagentStop 배열 | (b) 메인 transcript 의 task-notification `<note>` | (c) handback(`origin.peer`) |
|---|---|---|---|
| 계약 | 공개 훅 스키마(호스트 문서가 이 용도를 명시) | 비공개, **영문 문장** 일치 | 비공개 구조 필드 |
| 프라이버시 | 종류·개수만(자유 텍스트 무판독) | `message.content` 판독 — README·RI7 약속 위반 | 구조 필드지만 옆 필드 `body` 에 보고 전문 |
| 귀속 | 세션 범위(소유자 없음) | 실행 단위 정확(호스트 `Har` 판정) | auto 모드에서만 존재 |
| 창 | 훅이 오는 순간 | 128KiB 꼬리 — 메인이 계속 일하면 밀려난다 | 같음 |
| 이행 | 없음(이미 설치된 훅) | 없음 | 없음 |

**결정: (a)만.** (b)는 실행 귀속이 정확한 유일한 신호지만 프라이버시 고지의 명시 약속을 깨고 호스트 문구
변경에 무방비다 — 실패 방향이 조용한 미검출이라 안전하긴 하나, 그 대가로 고지를 바꿀 만큼의 효용이 없다(세션
배지가 결함 전체를 고친다, §1.1). (c)는 "끝남"만 알려 주고 auto 모드 밖에서는 없다. 둘 다 사용자가 실행 줄
표시를 원할 때의 후속 후보로 남긴다(§9 A2).

### BW2. 기록 — 종류별 개수만, 이벤트 이름으로 가둔다

- `Stop`·`SubagentStop` 일 때만(`BACKGROUND_REPORTING_EVENT_NAMES`) 이벤트 줄에 두 키를 더한다. 범용
  `optional_keys` 루프에 넣지 않는다(RI7 GOTCHA 8 — 다른 훅에 같은 이름의 필드가 생겨도 새지 않게).
  - `bt`: `{정규화된 종류: 개수}` — `background_tasks` 가 목록일 때만. 빈 목록이면 `{}`("진행 중인 것 없음"을
    명시적으로 기록).
  - `sw`: `session_crons` 중 `recurring` 이 정확히 `false` 인 항목 수(1회성 예약 깨우기 — ScheduleWakeup 등) —
    목록일 때만. 반복 예약은 세지 않는다(BW4).
  - 키가 없거나 목록이 아니면 그 키를 싣지 않는다(구버전 호스트 — 페일오픈).
- 각 작업에서 읽는 것은 **`type` 한 필드**뿐이다. `id`·`status`·`description`·`command`·`agent_type`·`server`·
  `tool`·`name` 은 읽지 않는다. 예약에서 읽는 것은 `recurring` 불리언 하나뿐이고 `id`·`schedule`·`prompt` 는
  읽지 않는다(T25-249).
- 종류 정규화(`normalize_background_task_type`): 문자열이면 소문자화, 공백·하이픈 → 밑줄, 그 뒤
  `\A[a-z_]{1,32}\Z` 를 통과해야 한다 — 아니면 `"unknown"`. 호스트 라벨 목록의 사본을 두지 않는다(RI7 의
  형태 검사 선례 — 호스트가 종류를 늘려도 유지 비용 0, 자유 텍스트는 모양 검사에서 탈락).
  예: `shell`·`subagent`·`MCP task`→`mcp_task`·`cloud session`→`cloud_session`·`auto-mode scan`→`auto_mode_scan`.
- 병리적 입력 방어선(이벤트 줄이 짧아야 동시 append 가 안전하다 — `hub-dashboard.md` 「이벤트 스키마」):
  분류는 앞 **256개**(`BACKGROUND_TASK_SCAN_MAX`)만, 나머지는 `unknown` 으로 센다 · 종류는 **8개**
  (`BACKGROUND_TASK_KIND_MAX`, `unknown` 자리 포함)까지 · 예약도 앞 256개만 본다 · 개수·`sw` 는
  **999**(`BACKGROUND_COUNT_MAX`)로 자른다.
- 이벤트 줄 예: `{"t":…,"e":"Stop","s":…,"c":…,"bt":{"shell":2},"sw":0}` ·
  `{"t":…,"e":"SubagentStop","s":…,"c":…,"ai":"a91d…","at":"implementer","bt":{"shell":2,"subagent":1},"sw":0}`.
- `parse_event_line` 은 두 키를 다시 검증한다(방어 재검증 — 옛 줄·찢긴 줄이 섞인다). 하나라도 형태 위반이면
  보고 전체를 버린다(→ 오늘의 판정). 한쪽 키만 있으면 없는 쪽은 비어 있는 것으로 본다.

### BW3. 사실 — "지금 유효한 보고"는 가장 최근 추적 이벤트가 정한다

`SessionFacts.background_report` 는 `_apply_tracked_event` **맨 앞 한 줄**로 정한다:

```python
session.background_report = (
    event.background_report if event.hook_event_name in BACKGROUND_REPORTING_EVENT_NAMES else None
)
```

| 추적 이벤트 | 결과 | 이유 |
|---|---|---|
| `Stop`·`SubagentStop`(추적됨) | 그 줄의 보고(없으면 None) | 배열은 세션 범위라 누가 보고해도 같은 등록소의 사진이다 |
| `UserPromptSubmit`(작업 알림 배달 포함) | None | 턴이 다시 돈다(T). 다음 Stop 이 새 사진을 준다 |
| `SubagentStart`(재개 포함) | None | 서브에이전트가 돈다(S). 그 SubagentStop 이 새 사진을 준다 |
| `SessionStart`(비 compact) | None | 새 프로세스 — 옛 등록소는 사라졌다 |
| `SessionEnd`·`StopFailure`(메인·서브) | None | 끝났거나 배열이 없는 이벤트 — 페일오픈 |
| 필터된 내부 이벤트(compact `SessionStart`, 미추적 내부 `SubagentStop`) | **변화 없음** | 필터가 `_apply_tracked_event` 앞에서 거른다(T25-86) — compact 는 작업을 죽이지 않고, 프롬프트 제안 등 내부 에이전트의 Stop 은 메인 Stop 몇 초 뒤에 온다 |

분기마다 흩어 쓰지 않고 한 줄로 두는 이유: 분기 하나를 빠뜨리면 낡은 보고가 살아남는다(GOTCHA 12).

### BW4. 깨우는 종류 — 호스트의 keepalive 집합과 같게

`WAKING_BACKGROUND_TASK_TYPES = frozenset({"shell", "monitor", "workflow"})` — 호스트가 "제 백그라운드 작업이
남은 채 멈췄다"고 판정하는 keepalive 사유(`bash:`·`monitor:`·`workflow:`, §1.3-5)와 같은 집합이다. 메인이 띄운
경우도 이 셋은 끝날 때 메인에 알림을 보낸다(§1.2 의 12:05→12:38).

| 제외한 종류 | 이유 |
|---|---|
| `subagent`·`teammate` | 훅이 이미 실행(S)으로 추적한다 — 세면 이중 계산이고, 서브에이전트 자신의 SubagentStop 배열에 자기 자신이 섞인다(U3) |
| `dream`·`auto_mode_scan` | 호스트 내부 ambient 작업 — 끝나도 세션을 깨우지 않는다(`skipTranscript`/`ambient`) |
| `cloud_session`·`mcp_task`·`unknown` | 깨움 경로 미확인 — 제외가 페일오픈(오늘과 같음) 방향. 관측되면 원소 1개 추가로 확장 |

`session_crons` 는 **1회성**(`recurring:false`)만 센다 — ScheduleWakeup 처럼 "이 작업을 곧 이어서 한다"는
예약이다(이 기계의 최근 10일 메인 transcript 15개가 ScheduleWakeup 을 쓴다, CronCreate 는 0). 반복 예약(`/loop`
고정 주기·CronCreate 반복)은 세션이 사용자를 기다리는 동안에도 늘 걸려 있는 상시 일정이라, 세면 답을 줄 때마다
(Stop 마다) 「백그라운드 대기」가 된다 — 제외한다(오늘과 같음). 발화하면 그 프롬프트가 `UserPromptSubmit` 으로
와서 어차피 작업중이 된다. `recurring` 은 닫힌 불리언이라 프라이버시 비용이 없다.

### BW5. 표시 상태 — 안 B: 여섯 번째 상태 `"background"`

```
state = "done"         if base_state == "done"
        "interrupted"  elif interruption is not None and roster != "not_listed"
        "background"   elif base_state == "idle" and background_wait is not None
        "stale"        elif is_stale                  # 계산식 무변경(LS9·SL4)
        base_state     otherwise
```

- `_compute_base_state`(LS5 화해 표)와 `is_stale`·`last_known_activity_at_ms` 는 **한 글자도 바뀌지 않는다.**
  `base_state` 는 3값 그대로다. 새 신호는 idle 을 덧칠하는 오버레이로만 들어온다.
- **왜 working 으로 세지 않는가(안 A 기각)**: ① 호스트 자신이 이 상태를 idle 의 변종(`idle_background`)으로
  분류하고 명부도 `idle` 이다(§1.3-6). ② 훅 입력으로는 34분짜리 검사와 끝나지 않는 dev 서버·`tail -f` 를
  구별할 수 없다(명령줄은 읽지 않는다) — working 이면 dev 서버를 띄워 둔 세션이 사용자를 기다리는 동안에도
  「작업중」 + glow 로 보인다(목업 장면 4). 「백그라운드 대기」는 두 경우 모두에 참인 서술이다(세션 배지 라벨에
  "대기"가 남는다). ③ 안 A 는 LS5 표 세 행(idle·listed·unknown)과 `is_stale` 을 함께 고쳐야 한다 — 안 B 는 사다리 한 줄.
- **이름은 소문자 a-z 만** — T25-219 가 `"[a-z]+"`·`'[a-z]+'` 로 뽑는다(RI2 와 같은 제약). CSS `state-background`.
- **stale 과의 관계**: 사다리에서 background 가 stale 보다 앞서므로 상한(BW6) 안에서는 「소식 없음」으로
  뒤집히지 않는다(§1.2 의 7/25 건이 고쳐지는 지점). LS9("명부는 stale 에 섞이지 않는다")는 그대로다 — 명부는
  background 를 **취소**(not_listed)할 수만 있고 만들 수는 없다. 그래서 명부 오판이 stale 을 막는 길은 여전히
  없고, 이 세션들에 대한 독립 상한이 30분에서 max(30, 90)분으로 **명시적으로** 늘어날 뿐이다(RI9 의 stale 면제
  선례와 같은 형태, 상한 있음).
- interrupted 가 먼저인 이유: 한도로 멈춘 턴은 사용자의 판단이 필요하다(RI9). 실제로는 StopFailure 가 보고를
  지워(BW3) 둘이 겹칠 일이 거의 없다.

### BW6. 상한 — 보고 뒤 90분

- `BACKGROUND_WAIT_MAX_MS = 90 * 60 * 1000`. 근거: §1.2 조용한 공백 25건의 최장 40.1분의 **2.2배** —
  `SUBAGENT_ZOMBIE_AFTER_MS`(ZG2: 최장 정상 실행 47.3분의 1.9배)와 같은 증거 지평이다. 두 상수는 **따로 둔다** —
  근거 표본이 다르다(하나가 바뀌어도 다른 하나가 딸려 가지 않게).
- 경계: `now − reported_at_ms >= 상한` 이면 만료(`is_running_subagent` 의 `<` 와 같은 관례).
- 만료 뒤는 오늘의 판정이다 — 대개 `idle` → 마지막 활동 30분 초과라 `stale`(목업 장면 5).
- 끝나지 않는 작업: 마지막 Stop 뒤 90분이면 풀린다. 세션이 계속 쓰이면 Stop 마다 다시 무장하지만, 그때는 세션이
  실제로 쓰이는 중이다.
- 30분(stale 과 같게)은 7/25 건을 못 고치고, 60분(최장의 1.5배)은 성립하는 대안이다 — 쟁점 2.

### BW7. 실행(run) — 귀속하지 않는다, 재개는 오늘처럼 같은 줄

- (a) **칩·실행 줄 무변경**(멈춘 서브에이전트는 「종료」). 배열이 부모 세션 범위이고 소유자 필드가 없다(§1.3-2).
  이 저장소 흐름에서는 메인 자신이 전체 검사를 백그라운드로 도는 일이 흔해(§1.2 12:05, 이 설계 세션 자체도 메인이
  검사를 돌리는 중에 디스패치됐다) SubagentStop 배열에 메인의 셸이 섞인다 — "그 SubagentStop 때 셸이 있었다"로
  귀속하면 방금 끝난 **아무** 서브에이전트가 「백그라운드 대기」가 된다. ZG4·RI3 의 "배지 ⇔ 칩" 문장은 개정한다:
  **배지가 백그라운드 대기일 때 칩이 전부 「종료」인 것이 정상이다.**
- (b) **재개 = 같은 줄**: 같은 `agent_id` 라 `SubagentFact` 하나로 이어진다. `_handle_subagent_start` 가 시작
  시각을 재개 시각으로 덮고 `ended_at_ms` 를 비우며, 호스트도 `meta.json` 을 재개 때 다시 쓴다(§1.5). 바꾸지
  않는 이유: 재개 뒤 보이는 경과("재개하고 3분째")가 지금 행동에 쓰이는 값이고, 첫 시작을 보존하면 ZG 나이 상한
  (시작 뒤 90분)이 재개 구간을 일찍 좀비로 돌리며, `meta.json` 으로는 첫 시작을 복원할 수도 없다.

### BW8. 프로젝트·정렬·live·glow

- `PROJECT_STATE_PRIORITY = ("working", "interrupted", "background", "idle", "stale", "done")` — 템플릿
  `SESSION_STATE_ORDER` 같은 순서(T25-219 가 대조). background 는 "사용자 판단 필요"(interrupted) 뒤, "사용자
  차례"(idle) 앞 — 할 일은 없지만 일이 진행 중이다.
- `LIVE_SESSION_STATES = frozenset({"working", "background"})` — GN2 의 "지금 그 작업을 하는 세션". 빼면: 대시보드를
  쓴 세션 A 가 백그라운드 대기 중이고 뒤에 시작한 세션 B 가 working 일 때 살아 있는 세션이 B 뿐이라
  `tier1_is_previous_task` 가 켜져 A 의 진행 중 대시보드가 「이전 작업」으로 톤다운된다(T25-87 은 stale·done
  부재만 검사 — 통과).
- glow(`card-working`)는 working 전용 그대로(결정 D2 — "지금 돈다"로 오해되면 안 된다). 12시간 숨김은 stale 전용
  그대로.

### BW9. 뷰 계약

- `SessionView.background_wait: BackgroundWait | None = None` 을 **맨 뒤**에 둔다 — T25-150 의 마지막 필드 기대값을
  `interruption` → `background_wait` 로 갱신(model→workflow→tier1_is_finished_task→interruption 선례).
- 불변식 `background_wait is not None ⇔ state == "background"` — `compute_session_view` 가 강제(테스트 L14).
- 정적 값만(D2 — `snapshot_content_key` 안정): `since_ms`·`until_ms`(= since + 상한, 서버가 계산한 상수)·
  `task_count`·`wakeup_count`. "몇 분째인가"는 클라이언트가 틱마다 그린다(지금의 `session-time`).
- `hub.html` 에 새로 인라인되는 값은 **정수 4개**뿐이다. 종류 이름은 싣지 않는다.

> **개정됨(2026-10-07, [`hub-live-activity.md`](./hub-live-activity.md) 결정 LA10·LA11) — BW9 옆.** `BackgroundWait` 는 맨
> 뒤에 `output: BackgroundOutputView | None = None` 을 더한다(정수 3개 — 파일 수·최근 수정 시각·크기 합). 「정적 값만」·
> 「정수 4개뿐」은 이 필드에 한해 개정된다: `output` 은 **파일 stat 의 함수**라 출력이 늘어나는 동안에는 수집마다 값이 바뀐다
> (그동안만 `hub.html` 을 다시 쓴다 — 아무것도 안 돌면 오늘과 같다). 판정에는 쓰이지 않는 표시 전용 값이다. 불변식
> `background_wait is not None ⇔ state == "background"` 는 그대로다(`output` 은 그 안에서만 실린다). 인라인 값은
> 「정수 4개 + (출력이 확인되면) 정수 3개」다.

### BW10. 화면 — §7 이 정본

새 색 토큰 0(`.agent-chip-running` 의 `--accent-soft`/`--accent-ink` 쌍 + `.card.card-open` 의 `--accent` 테두리),
새 CSS 규칙 1, 애니메이션 0(T25-190·T25-243 의 정신).

### BW11. 모듈 분리 — 동작 불변 첫 단계

`hub_session.py` 머리 docstring 의 에스컬레이션(RI13: "다음 확장 전에 분리를 먼저 한다")을 이행한다. M1 은
**동작이 한 글자도 바뀌지 않는** 이동·참조 갱신·가드 재조준만 담고 단독 커밋으로 둔다 — 검수가 "옮겼을 뿐"을
확인하기 쉽고, 뒤 단계의 diff 가 분리 소음에 묻히지 않는다. 테스트는 MS9(소스 1:테스트 1)를 따라
`compute_session_view` 를 부르지 않는 접기 전용 클래스(`ParseEventLineTest`·`StopFailureFoldingTest`·
`InternalEventFilterTest`·`ObservedCwdsTest`·`LastPromptAtMsFieldTest` 등 — 구현자가 호출 여부로 확정)를
`test_hub_session_facts.py` 로 옮긴다.

### BW12. 이행·설정

`HOOK_EVENTS` 불변 → `/hub install` 재실행 불필요. 바뀌는 것은 배포된 `hub_hook.py`·새 모듈 파일뿐이라
`hub/install.sh` 재배포 + `/hub server restart`(기존 관례 — README 「서버」 절)면 된다. 스위치 없음(N6). 배열이
오지 않는 호스트·옛 이벤트 줄은 보고 None → 오늘과 같다.

---

## 6. 데이터 모델과 인터페이스

### 6.1 `hub/bin/hub_session_facts.py` (★순수, 신설)

```python
STOP_FAILURE_EVENT_NAME = "StopFailure"                       # (이동)
BACKGROUND_REPORTING_EVENT_NAMES: frozenset[str] = frozenset({"Stop", "SubagentStop"})   # BW2
BACKGROUND_TASK_TYPE_PATTERN = re.compile(r"\A[a-z_]{1,32}\Z")   # ERROR_KIND_PATTERN 과 같은 모양(BW2)
UNKNOWN_BACKGROUND_TASK_TYPE = "unknown"
BACKGROUND_TASK_SCAN_MAX = 256      # 훅이 분류하는 작업 수 상한 — 훅은 수 ms 안에 끝나야 한다
BACKGROUND_TASK_KIND_MAX = 8        # 이벤트 줄에 싣는 종류 수 상한(unknown 포함) — 줄이 짧아야 append 가 안전
BACKGROUND_COUNT_MAX = 999          # 개수·1회성 예약 수 상한 — 자릿수 폭탄 방어(재검증 쪽도 같은 값)

@dataclass(frozen=True)
class BackgroundReport:
    """Stop·SubagentStop 이 보고한, 세션(부모) 범위 진행 중 백그라운드 작업의 종류별 개수와 1회성 예약 수(BW2·BW3).
    SubagentStop 이 실어도 그 서브에이전트 것만이 아니다."""
    reported_at_ms: int                       # 그 이벤트 줄의 t
    task_counts: tuple[tuple[str, int], ...]  # (정규화된 종류, 개수 1..999) — 종류 오름차순(결정적)
    wakeup_count: int                         # session_crons 중 recurring 이 false 인 항목 수 0..999

def normalize_background_task_type(value: object) -> str:
    """호스트 background_tasks[].type 라벨을 닫힌 모양으로 — 소문자화·공백/하이픈→밑줄 뒤 패턴 밖이면 unknown."""

@dataclass(frozen=True)
class HookEvent:                               # (이동) 기존 9필드 + 맨 뒤
    ...
    background_report: BackgroundReport | None = None   # bt·sw 가 있는 줄만(BW2)

@dataclass(frozen=True)
class SessionFacts:                            # (이동) 기존 필드 + 맨 뒤
    ...
    background_report: BackgroundReport | None = None   # BW3 — 가장 최근 추적 이벤트가 정한다

# (이동, 시그니처 불변) SubagentFact · FailedTurn · is_internal_session_start · is_untracked_internal_subagent_stop
#                      · EVENT_TIME_MAX_MS · _Mutable* · _handle_* · _new_session_builder · _freeze_session
def parse_event_line(line: str) -> HookEvent | None: ...          # + _parse_background_report(payload, t)
def build_session_facts(events: Sequence[HookEvent]) -> dict[str, SessionFacts]: ...   # + BW3 한 줄
```

`_parse_background_report(payload: dict, received_at_ms: int) -> BackgroundReport | None` — `bt` 는 dict·키 수 ≤
KIND_MAX·키가 패턴 통과·값이 bool 아닌 int 1..999, `sw` 는 bool 아닌 int 0..999. 둘 다 없으면 None, 하나라도 위반이면
None, 한쪽만 있으면 다른 쪽은 빈 값.

### 6.2 `hub/bin/hub_session.py` (★순수)

```python
SessionState = Literal["working", "idle", "stale", "done", "interrupted", "background"]
WAKING_BACKGROUND_TASK_TYPES: frozenset[str] = frozenset({"shell", "monitor", "workflow"})   # BW4
BACKGROUND_WAIT_MAX_MS = 90 * 60 * 1000       # BW6 — 조용한 공백 25건 최장 40.1분의 2.2배

@dataclass(frozen=True)
class BackgroundWait:
    """「백그라운드 대기」 표시의 근거(BW9). 정적 값만 — 경과 판정은 클라이언트 몫(D2)."""
    since_ms: int          # 보고한 Stop/SubagentStop 시각
    until_ms: int          # since_ms + 상한 — 이 시각까지 소식이 없으면 표시를 거둔다
    task_count: int        # WAKING_BACKGROUND_TASK_TYPES 에 드는 진행 중 작업 수
    wakeup_count: int      # 1회성 예약 깨우기(session_crons 중 recurring:false) 수

# SessionView 맨 뒤: background_wait: BackgroundWait | None = None   (T25-150 갱신)

def effective_background_wait(
    facts: SessionFacts, now_ms: int, roster: RosterState,
    max_age_ms: int = BACKGROUND_WAIT_MAX_MS,
) -> BackgroundWait | None:
    """세션을 "백그라운드 작업이 깨워 주기를 기다리며 멈춘" 상태로 볼 근거(BW4·BW6).
    보고 없음·명부 not_listed·now − reported ≥ max_age·깨우는 작업과 예약이 모두 0 이면 None."""

def _display_state(base_state, interruption, background_wait, roster, is_stale) -> SessionState:
    """표시 사다리(BW5) — done > interrupted > background(base idle 일 때) > stale > base_state."""
```

`compute_session_view` 변경(시그니처 불변 — 새 인자 없음): `roster` 계산 뒤
`background_candidate = effective_background_wait(facts, now_ms, roster)` → `_display_state(...)` →
`background_wait = background_candidate if state == "background" else None`(RI8 의 `interruption` 되접기와 같은 모양).
상한은 기본 인자로만 흐른다(ZG3 — `HubConfig` 키를 만들지 않는다). 상한 경계 테스트는 `effective_background_wait`
를 직접 부른다.

### 6.3 `hub/bin/hub_hook.py`

```python
def _project_fields(payload: dict) -> dict:
    ...                                                   # 기존 그대로
    if payload.get("hook_event_name") in hub_session_facts.BACKGROUND_REPORTING_EVENT_NAMES:
        fields.update(_background_fields(payload))
    return fields

def _background_fields(payload: dict) -> dict:
    """Stop·SubagentStop 의 두 배열을 bt(종류별 개수)·sw(1회성 예약 수)로만 줄인다(BW2). 목록이 아니면 싣지 않는다."""

def _one_shot_wakeup_count(crons: list) -> int:
    """예약 목록 → recurring 이 정확히 False 인 항목 수(앞 SCAN_MAX 개만, COUNT_MAX 로 자른다). 다른 키는 읽지 않는다."""

def _task_type_counts(tasks: list) -> dict[str, int]:
    """작업 목록 → {정규화된 종류: 개수}. 앞 SCAN_MAX 개만 분류하고 나머지·종류 상한 초과는 unknown 으로 센다."""
```

### 6.4 `hub/bin/hub_project.py`

`PROJECT_STATE_PRIORITY` 6값·`LIVE_SESSION_STATES` 2값(BW8). 임포트 `from hub_session_facts import SessionFacts`
분리. 그 밖의 판단 0.

### 6.5 GOTCHA

1. **파이썬(M3)과 템플릿(M4)은 한 커밋에 착지한다** — `STATE_LABEL` 에 키가 없으면 배지에 `undefined` 가 그려지고,
   `PROJECT_STATE_PRIORITY` 에 `"background"` 가 없으면 `_project_state` 의 `.index()` 가 **ValueError 로 수집 자체를
   죽인다.** `SessionState`·`PROJECT_STATE_PRIORITY`·`SESSION_STATE_ORDER`·`STATE_LABEL`·`STATE_GLYPH` 를 함께 고친다.
2. **T25-219 원장 행의 sed 는 5값 튜플 리터럴을 문다** — 6값으로 바꾸면 변조가 적용되지 않는다. 행의 패턴·치환·
   설명("5값"→"6값")을 새 튜플로 개정한다.
3. 상태 이름은 a-z 만(BW5).
4. `SessionView` 새 필드는 반드시 맨 뒤 + T25-150 갱신을 한 커밋에.
5. **M1 에서 T25-126·T25-150 의 끝 앵커가 사라진다** — 두 가드는 `^# ---- 내부 이벤트 필터 ----`(SessionView 바로
   뒤 절 머리)까지를 추출하는데, 그 절이 새 모듈로 간다. 분리 뒤 SessionView 다음 절 머리인
   `^# ---- 세션 표시 상태 ----` 로 끝 앵커를 바꾼다. 안 바꾸면 sed·awk 범위가 파일 끝까지 늘어 거짓 결과가 난다.
6. **옮긴 코드를 물던 역방향 가드는 눈이 먼다**(메모리 「개명하면 정적 가드가 눈이 먼다」) — 새 위치에 대상이
   없으면 "없음"이 곧 통과가 된다. 분리 전에 `run.sh`·`mutations.tsv` 를 옮길 심볼 이름과 `hub_session_file` 로
   grep 해 재조준 목록(§8.3 표)을 확정하고, 역방향 검사는 **본문 추출 실패를 실패로 보고**하게 고친다(T25-211 은
   지금 빈 본문을 통과시킨다).
7. `hub_hook.py` 는 새 모듈을 **모듈 맨 위에서** 임포트한다 — 그 파일이 없으면 `main()` 의 예외 흡수 이전에
   ImportError 로 죽어 이벤트가 0건 기록된다(세션은 `|| true` 로 막히지 않는다). `hub/install.sh` 가 bin 30개를
   함께 복사하므로 성립하지만, 파일 하나만 손으로 복사하지 않는다.
8. `bt`·`sw` 는 범용 `optional_keys` 루프에 넣지 않는다(BW2).
9. `hub_hook.py` 에 `"Notification"` 문자열을 쓰지 않는다(T25-7) — 주석의 "task-notification"은 소문자라 무해.
   `"p"` 리터럴도 금지(T25-211).
10. `_task_type_counts` 는 각 작업에서 `type` 외 키를 읽지 않는다 — `task.get("status")` 로 거르고 싶어도 호스트가
    이미 running·pending 만 싣는다(§1.3-2).
11. **최소 폭 320px 의 프로젝트 머리는 줄바꿈 없는 flex** 다 — 가장 긴 조합(티어 1 「대시보드 추적」 + 경과
    「1시간 29분 전」)에서 오늘의 「▲ 소식 없음」도 이미 이름을 2px 로 누른다. 실측(목업 장면 3b): 프로젝트 배지
    「◐ 백그라운드 대기」는 머리가 **26px 넘쳐** 경과 시각이 카드 밖으로 잘리고, 「◐ 백그라운드」는 5px 가 카드
    안쪽 여백(20px)으로 들어갈 뿐 잘리지 않는다. 그래서 **프로젝트 배지 = `STATE_LABEL`(짧은 「백그라운드」),
    세션 배지 = `stateLabel` 의 긴 라벨** 로 가른다(stale 의 「소식 없음」/「소식 없음 · 직전 X」와 같은 짜임).
12. BW3 규칙은 `_apply_tracked_event` 맨 앞 한 줄이다 — 분기마다 두지 않는다.
13. M1 뒤 `hub_collect.py`·`hub_hook.py` 의 `import hub_session` 은 안 쓰이게 된다 — 지운다(고아 임포트).
14. 임포트 실험은 `python3 -B`(pycache 가 commands 파일 수를 흔든다 — 메모리).

---

## 7. 표시 사양 (`hub_template.html`)

| 항목 | 값 |
|---|---|
| `STATE_LABEL.background` | `'백그라운드'` — 프로젝트 배지(모달 루트 포함, `renderStateBadge(project.state, null, …)` 두 곳) |
| `BACKGROUND_SESSION_LABEL` | `'백그라운드 대기'` — 세션 배지. `stateLabel` 에 `if(state === 'background') return BACKGROUND_SESSION_LABEL;` |
| `STATE_GLYPH.background` | `'◐'`(U+25D0) — ●○▲✓■ 와 같은 기하 도형 계열, 이모지 표현 없음. "절반만 도는" 은유 |
| CSS | `.badge.state-background{background:var(--accent-soft);color:var(--accent-ink);border:1px solid var(--accent)}` — 대비(계산) 라이트 5.87:1·다크 7.52:1. 테두리는 열린 카드·열린 행(면색 `--accent-soft`) 위에서 윤곽을 지킨다(목업 장면 3). 테두리 있는 배지의 트리 갈고리 정렬 −0.5px 는 기존 허용치(≤1px) 안(state-stale·state-done 과 같다) |
| 세션 툴팁 | 순수 함수 `backgroundBadgeTooltipText(backgroundWait, nowMs)` → `'이 세션은 ' + absoluteTimeLabel(since) + ' 부터 ' + parts.join('·') + '를 기다리고 있습니다. 끝나거나 알림이 오면 이어서 진행합니다 — ' + absoluteTimeLabel(until) + ' 까지 소식이 없으면 이 표시를 거둡니다.'`, `parts` = `'백그라운드 작업 N개'`(task_count>0)·`'예약된 깨우기 M개'`(wakeup_count>0). 불변식상 `parts` 는 비지 않는다 |
| 프로젝트 툴팁 | `BACKGROUND_TOOLTIP_PROJECT = '백그라운드 작업이 끝나기를 기다리는 세션이 있습니다.'` |
| 시그니처 | `renderStateBadge(state, baseState, lastActivityAtMs, interruption, backgroundWait)` — `data-tooltip` 분기에 background 추가(세션은 `baseState` 유무로 가른다 — interrupted 와 같은 관례). 호출부: `renderSessionContent` 에 `session.background_wait` 인자 1개. 프로젝트 호출 두 곳 불변 |
| 정렬 | `SESSION_STATE_ORDER = ['working','interrupted','background','idle','stale','done']` |
| glow | 불변 — `project.state === 'working'`·`session.state === 'working'` 두 곳 그대로 |
| 전환 | 서버가 상한 경과를 다음 수집(폴링 ≤60초)에서 반영한다. 라벨·툴팁에 틱 의존 값이 없다(시각은 전부 절대 시각) |

**안 A**(대안, 목업 가운데 열): 상태는 `working`, 세션 배지만 `'작업중 · 백그라운드'` 접미 — glow·채움 파랑이 그대로라
dev 서버 세션도 「작업중」이 된다(장면 4).

### 7.1 문서 문구(정본 초안 — T25-252 가 무는 토큰 포함)

- **README 「훅 옵트인」 끝에 한 문장**: "`Stop`·`SubagentStop` 입력에 호스트가 싣는 진행 중 백그라운드 작업 목록
  (`background_tasks`)과 예약 목록(`session_crons`)은 **종류별 개수**(예: `{"shell":2}`)와 1회성 예약 깨우기 수만
  남긴다 — 작업 설명·명령줄·예약 프롬프트·작업 ID 는 기록하지 않는다(결정 BW2, docs/prps/hub-subagent-background-pause.md)."
- **README 「프라이버시 고지」 transcript 항 뒤에 한 문장**: "백그라운드 대기 표시(아래 「화면 배치」)를 위해 `hub.html`
  에 새로 인라인되는 값은 정수 4개(기다리기 시작한 시각·표시를 거둘 시각·작업 수·예약 수)뿐이다."
- **README 「화면 배치」 정렬 문장**: "세션 줄은 **작업중 > 한도 초과 > 백그라운드 대기 > 대기 > 소식 없음 > 완료** 순으로…"
- **README 「화면 배치」 새 항목**: "메인 턴은 끝났지만 그 세션에 진행 중인 백그라운드 작업(셸·모니터·워크플로우)이나
  1회성 예약 깨우기가 남아 있으면 세션 배지가 **백그라운드 대기**(◐, 프로젝트 배지는 `백그라운드`)로 보인다 —
  서브에이전트가 긴 검사를 백그라운드로 걸어 두고 멈춘 경우가 대표적이다. 그 작업이 끝나 세션(또는 그 작업을 띄운
  서브에이전트)이 스스로 다시 일하면 `작업중`으로 돌아간다. 호스트가 그 목록을 알려 준 뒤 **90분**까지만 이렇게
  보이고(개발 서버·`tail -f` 처럼 끝나지 않는 작업이 세션을 붙잡지 않게), 그동안에는 `소식 없음`으로 뒤집히지 않는다.
  카드 glow 는 켜지지 않는다. 서브에이전트 실행 줄은 호스트가 알려 준 대로 `종료`로 남는다 — 목록이 세션 전체의
  것이라 누가 띄운 작업인지 알 수 없기 때문이다(재개되면 같은 줄이 다시 `진행 중`이 되고 경과는 재개 시각부터 센다)."
- **README 좀비 가드 문단**: "…배지가 **백그라운드 대기**일 때 칩이 전부 종료로 보이는 것도 정상이다(결정 BW7)." 한 문장 추가.
- **README 툴팁 목록**: "**백그라운드 대기(background) 상태 배지**" 추가, "백그라운드 대기 배지 툴팁은 기다리기 시작한 시각·
  남은 작업 수·표시를 거둘 시각을 알려준다".
- **README 「이전 작업」 라벨 문장**: "지금 **작업중**(또는 **백그라운드 대기**)인 세션이 전부 …" (BW8 의 live 집합과 일치).
- **commands/hub.md 설치 고지 ①** 끝: "`Stop`·`SubagentStop` 입력의 진행 중 백그라운드 작업·예약 목록은 종류별 개수만
  남기고 작업 설명·명령줄·예약 프롬프트는 기록하지 않습니다." · **구현 노트**: "`Stop`·`SubagentStop` 은 `bt`(종류별
  개수)·`sw`(1회성 예약 수)를 함께 남긴다 — `hub_session_facts.normalize_background_task_type` 경유(결정 BW2)."
- **docs/prps/hub-dashboard.md**: 「이벤트 스키마」 표 뒤 개정 블록(`bt`·`sw` 두 키, RI7 블록과 같은 모양) · 「상태 판정
  규칙」 개정 블록 "`SessionState` 에 여섯 번째 값 `"background"` … 정본은 결정 BW1~BW12" · 모듈 구성표에
  `hub_session_facts.py`(★순수, 훅 이벤트 → 세션 사실) 행.

---

## 8. 테스트 계획

### 8.1 단위 (`tests/hub`, stdlib unittest, AAA)

**파싱 — `test_hub_session_facts.py::BackgroundReportParseTest`**

| # | 입력 줄 | 기대 | 잡는 변조 |
|---|---|---|---|
| P1 | Stop `"bt":{"shell":2},"sw":0` | `BackgroundReport(t, (("shell",2),), 0)` | 파싱 삭제 |
| P2 | 두 키 없음 | `None` | 부재를 빈 보고로 접음 |
| P3 | `"bt":{},"sw":0` | 빈 보고(`()`, 0) — None 아님 | 빈 dict 를 부재로 접음 |
| P4 | 키 `"Bad Key!"`·33자·비문자열 | `None` | 키 재검증 삭제 |
| P5 | 값 `true`·0·-1·1000·1.5·`"2"` | `None` | bool/범위 검사 삭제 |
| P6 | 종류 9개 | `None` | 종류 상한 삭제 |
| P7 | `"sw"` 가 `true`·-1·1000 | `None` | sw 검사 삭제 |
| P8 | `"bt"` 가 list·str | `None` | 타입 검사 삭제 |
| P9 | `{"workflow":1,"shell":2}` | `task_counts` 가 종류 오름차순 | 정렬 삭제(스냅샷 키 흔들림) |

**정규화 — `NormalizeBackgroundTaskTypeTest`**: N1 `"shell"`→`shell` · N2 `"MCP task"`→`mcp_task` · N3 `"auto-mode scan"`→
`auto_mode_scan` · N4 `""`·`None`·5·`"x"*33`·`"셸"`·`"a/b"` → `unknown`.

**접기 — `BackgroundFoldTest`**(BW3 표 전 행)

| # | 이벤트열 | 기대 `background_report` |
|---|---|---|
| F1 | Stop(r) | r |
| F2 | Stop(r) → UserPromptSubmit | None |
| F3 | Stop(r) → SubagentStart | None |
| F4 | Stop(r) → SessionStart(compact) | r(필터 통과 못 함) |
| F5 | Stop(r) → SessionStart(resume) | None |
| F6 | Stop(r) → 미추적 내부 SubagentStop(빈 타입·모르는 id) | r |
| F7 | Stop(r1) → 추적 SubagentStop(r2) | r2 |
| F8 | Stop(r) → StopFailure(메인) / StopFailure(ai=알려진 id) | None / None |
| F9 | Stop(r) → Stop(키 없음, 옛 호스트) | None |
| F10 | Stop(r) → SessionEnd | None |
| F11 | 이관된 기존 접기 테스트 전부 | 기존 기대 불변(M1 — 동작 불변 증명) |

**훅 — `test_hub_hook.py::BackgroundProjectionTest`**

| # | 페이로드 | 기대 |
|---|---|---|
| H1 | Stop + `background_tasks:[{id,type:"shell",status,description:"<시크릿 모양>",command:"<시크릿 모양>"}]` + `session_crons:[{id,schedule,recurring:false,prompt:"<시크릿 모양>"}]` | 줄 키 = `{t,e,s,c,bt,sw}`, `bt=={"shell":1}`, `sw==1`, 세 자유 텍스트·id 가 이벤트 파일 어디에도 없음 |
| H2 | SubagentStop(같은 배열 + ai·at) | `ai`·`at`·`bt`·`sw` |
| H3 | UserPromptSubmit·SubagentStart 에 `background_tasks` 키 | `bt`·`sw` 없음 |
| H4 | Stop, 두 키 없음 / 값이 dict·str | `bt`·`sw` 없음 |
| H4b | `session_crons` 에 `recurring:true`·`recurring` 없음·dict 아닌 항목 | `sw==0`(1회성만 센다) |
| H5 | 300개(`shell` 250 + 이상한 것) | 합계 300(나머지 unknown), 종류 ≤ 8 |
| H6 | 종류 12가지 서로 다름 | 키 8개, 초과분 unknown |
| H7 | 항목이 dict 아님·`type` 없음 | unknown 으로 센다 |

**판정 — `test_hub_session.py::BackgroundWaitLadderTest`**(명부는 `LiveSessionIndex` 로 주입)

| # | 사실 | 명부 | now − 보고 | 기대 state / base |
|---|---|---|---|---|
| L1 | 턴 끝남, `shell:2` | unknown | 10분 | background / idle, `BackgroundWait(since, since+90분, 2, 0)` |
| L2 | 같음 | idle | 10분 | background |
| L3 | 같음 | busy | 10분 | working, `background_wait is None` |
| L4 | 같음 | not_listed | 10분 | idle(취소) |
| L5 | 같음 | listed | 10분 | background |
| L6 | + 도는 서브에이전트(S) | idle | 10분 | working |
| L7 | 같음(L2) | idle | **31분** | **background**(오늘은 stale — 사례의 14:06) |
| L8 | 같음 | idle | 90분 정각 | stale / idle(만료, 경계 `>=`) |
| L9 | 같음 | idle | 89분 59초 | background |
| L10 | `subagent:1,teammate:1,dream:1,unknown:1` 만 | idle | 10분 | idle |
| L11 | 작업 0, `wakeup_count:1` | idle | 10분 | background, `(…, 0, 1)` |
| L12 | `failed_turn`(rate_limit) + 보고(사실 직접 구성) | unknown | 10분 | interrupted |
| L13 | `ended_at_ms` + 보고 | unknown | 10분 | done |
| L14 | 위 전부 | | | `background_wait is not None ⇔ state == "background"` |
| L15 | **사례 재생**(§1.1 이벤트열, 가짜 cwd·id) | idle | now 13:40·14:06·14:08:40·(재개 없다고 가정) 15:07 | background·background·working·stale |
| L16 | **메인 소유 셸 재생**(12:05:11 Stop `shell:1` → 12:38:35 UPS → 12:39 Stop `{}`) | idle | 12:30·12:38:40·12:40 | background·working·idle |

`EffectiveBackgroundWaitTest`: E1 `max_age_ms` 인자 경계 · E2 `until_ms == since + max_age` · E3 보고 None → None ·
E4 WAKING 교집합 합산.

**프로젝트 — `test_hub_project.py`**: P1 (background, idle)→background · (interrupted, background)→interrupted ·
(working, background)→working · P2 대시보드를 쓴 세션이 background 이고 더 늦게 시작한 working 세션이 있을 때
`tier1_is_previous_task is False`(BW8 의 빼면 생기는 결함).

**종단 — `test_hub_collect.py::W1`**: 임시 `EVENTS_DIR` 에 사례 이벤트열(bt 포함) → `collect_snapshot` 의 세션
`state=="background"`, `background_wait` 정수 4개 일치(배선 한 군데 누락은 순수 층 테스트로 못 잡는다 — LS·RI W1 선례).

### 8.2 DOM 행동 (`tests/hub/test_hub_template_dom.py`, 기존 하네스 — Chrome 없으면 건너뜀)

D-BW1: background 세션 1개 + working·idle 세션이 섞인 스냅샷을 굽는다 → ① 세션 배지 `.badge.state-background` 텍스트
`'◐백그라운드 대기'`, `data-tooltip` 에 since·until 절대 시각과 `'백그라운드 작업 2개'` ② 프로젝트 배지 텍스트
`'◐백그라운드'`·정적 툴팁 ③ 카드에 `card-working` 없음(working 세션이 없을 때) ④ 세션 순서 working → background →
idle ⑤ 틱(61초 뒤) 후에도 배지 노드가 같다(부분 갱신 PU1).

### 8.3 정적 가드(`tests/run.sh` T25)와 원장

**신설**(변조행은 예시 — 구현자가 미러에서 PASS→FAIL·토큰 유일성을 증명하고 확정한다, T25-245 선례)

| 가드 | 정/역 | 검사 | 원장 변조행(예) |
|---|---|---|---|
| T25-248 BW-G1 | 정 | `_project_fields` 본문에 `BACKGROUND_REPORTING_EVENT_NAMES` · `_task_type_counts` 본문에 `normalize_background_task_type(` · 줄 머리 `fields["bt"] = _task_type_counts(`·`fields["sw"] = _one_shot_wakeup_count(` · `_one_shot_wakeup_count` 본문에 `"recurring"` | 정규화 호출을 벗긴다 |
| T25-249 BW-G2 | 역(프라이버시) | `hub_hook.py` 에 `"description"`·`"command"`·`"prompt"`·`"schedule"` 리터럴 0(두 따옴표) · `_background_fields`·`_task_type_counts`·`_one_shot_wakeup_count` 본문에 `"id"`·`"status"`·`"agent_type"` 0 | `fields["sp"] = [c.get("prompt") for c in crons]` 삽입 |
| T25-250 BW-G3 | 정 | `STATE_LABEL`·`STATE_GLYPH` 에 `background:` · `BACKGROUND_SESSION_LABEL` 과 `stateLabel` 의 background 분기 · `.badge.state-background{` 존재 + 본문에 animation·box-shadow 0 · `renderSessionContent` 호출이 `session.background_wait` 를 넘김 | 규칙에 animation 추가 |
| T25-251 BW-G4 | 정+역 | `^WAKING_BACKGROUND_TASK_TYPES` 줄에 `"subagent"`·`"teammate"` 0 · `BACKGROUND_WAIT_MAX_MS = 90 * 60 * 1000` · `_display_state` 본문에서 `return "background"` 줄이 `return "interrupted"` 뒤·`return "stale"` 앞 · `^LIVE_SESSION_STATES` 줄에 `"background"` | 집합에 `"subagent"` 추가 |
| T25-252 BW-G5 | 정(문서) | README `'종류별 개수'`·`'작업중 > 한도 초과 > 백그라운드 대기 > 대기 > 소식 없음 > 완료'` · commands/hub.md `'종류별 개수'` · hub-dashboard.md `'결정 BW1~BW12'` | README `s/종류별 개수/개수/g` |
| T25-253 BW-G6 | 정+역(분리 계약) | `hub_session_facts.py` 존재·★순수 표지 · `hub_transcript` 외 허브 모듈 임포트 0 · `hub_session.py` 에 `def parse_event_line(`·`def build_session_facts(`·`class HookEvent:`·`class SessionFacts:` 0(재정의 없음) · `tests/hub/test_hub_session_facts.py` 존재 | facts 모듈에 `from hub_session import SessionView` 삽입 |

**재조준·갱신**(M1 은 동작 불변이므로 전부 "같은 검사, 새 위치")

| 가드 | 지금 | 뒤 |
|---|---|---|
| T25-10 | ★순수 목록 | + `hub_session_facts.py`(안 넣으면 순수 계약이 조용히 빠진다) |
| T25-43 | `active_agent_types` 역검사(템플릿·hub_session) | + facts 모듈 |
| T25-86 | SessionStart 부활 분기·`ended_at_ms = None`·필터→적용 순서 | facts 모듈 |
| T25-115 | `observed_cwds` 선언·기본값 금지(역) | facts 모듈(역검사가 눈머는 자리) |
| T25-126·T25-150 | SessionView 끝 앵커 `# ---- 내부 이벤트 필터 ----` | `# ---- 세션 표시 상태 ----`, T25-150 마지막 필드 `background_wait: BackgroundWait \| None = None`(M3) |
| T25-211 | `parse_event_line` 본문 `"p"` 역검사 | facts 모듈 + 본문 추출 실패를 `record_failure` 로 · 메시지 `hub_session_facts.parse_event_line 에` · 원장 행 target_path·expect_token 개정 |
| T25-222 | `last_prompt_at_ms` 필드·대입(5검사 중 2) | facts 모듈(나머지 3은 그대로) |
| T25-104·T25-149 | 29개 파일 | 30 · 모듈 구성표에 `hub_session_facts.py` |
| T25-219 | (코드 무변경) | 원장 행 튜플 리터럴 6값(GOTCHA 2) |

- `SOURCE_GUARD_ID_FLOOR`: 편집 후 `collect_guard_ids` 실측으로 올리고(+6) 근거 주석을 단다. 원장 머리 인용 개수
  (T37 대조)도 함께.
- T25-7·T25-242·T25-243·T25-224 계열: 무영향(추가만 한다).

### 8.4 수동 검증

- **V0 — 호스트 신호 캡처(M0, 착수 전 1회, 사용자 동의 후 — 실제 CLI 호출)** — **완료, C1·C2 통과(결과는 §1.6)**. 사용자 `settings.json` 을 건드리지
  않는다. 스크래치패드에 ① `capture_hook.py`(stdin → 한 줄: `e`·키 이름 목록·`agent_id`·`[type, status]` 쌍 목록·
  `session_crons` 의 `recurring` 목록·수신 시각 — **description·command·prompt·schedule 은 쓰지 않는다**, 항상 exit 0) ② `settings.json`
  (`Stop`·`SubagentStop`·`SubagentStart`·`UserPromptSubmit` 에 그 스크립트)을 두고, **스크래치패드(=`/private/tmp`,
  허브 기본 무시 경로)를 cwd 로** `claude -p --settings <절대경로> --model haiku --output-format stream-json --verbose`
  를 두 번 부른다(RI V1 처럼 알림·재개가 프로세스 종료에 잘리면 `--input-format stream-json` 으로 살려 둔다) — A: "Bash 로 `sleep 30` 을 run_in_background 로 실행하고 기다리지 말고 턴을 끝내라", B: "general-purpose
  서브에이전트를 백그라운드로 띄워라. 그 에이전트는 Bash 로 `sleep 45` 를 run_in_background 로 실행하고 기다리지 말고
  즉시 턴을 끝낸다. 띄운 뒤 너도 즉시 턴을 끝내라".
  - 판정: C1 Stop·SubagentStop 줄에 두 배열 키가 있고 다른 이벤트에는 없다(U1) · C2 **B 의 메인 Stop(멈춤~재개 사이)에
    `["shell","running"]` 이 있다**(U2) · C3 같은 id 의 SubagentStart 가 sleep 끝에 온다(참고 — `-p` 가 백그라운드
    작업을 기다리지 않고 끝나면 관측 불가, 실사용 25건이 이미 증거). U3·U5 는 관측되는 대로 기록.
  - C1 실패 → 이 호스트에서는 기능이 비활성(페일오픈)이므로 착수를 멈추고 보고. C2 실패 → **재설계**(메인 Stop 이
    서브에이전트 작업을 못 싣는다 — 대안 A4 재검토, 설계 모델 승격 기준 4).
  - 동의하지 않으면: M1·M2 만 먼저 배포(화면 무변화, `bt`·`sw` 만 기록)하고, 다음 번 서브에이전트가 전체 검사로
    멈췄을 때 `events/<날짜>.jsonl` 의 메인 Stop 줄에 `"bt":{"shell":…}` 가 있는지 보고 M3·M4 로 간다.
- **V1 — 배포 뒤 실사용**: 다음 멈춤에서 허브가 13:36 에 해당하는 순간부터 「◐ 백그라운드 대기」, 재개 순간 「작업중」인지.
- **V2 — 시각**: 실데이터 `hub.html` 의 style 블록만 갈아 끼워 로컬 서버로 서빙해(메모리 「허브·대시보드 CSS 시각
  확인」) 라이트·다크·320px 를 본다. 목업 장면 3b 의 실측 스크립트(`.mock-measure`)를 그대로 쓸 수 있다.

---

## 9. 리스크와 대안

| # | 리스크 | 대응 |
|---|---|---|
| R1 | 끝나지 않는 백그라운드 셸(dev 서버·`tail -f`·서브에이전트가 남긴 고아 — 메모리 「서브에이전트가 남긴 백그라운드」)이 사용자 차례인 세션을 「백그라운드 대기」로 보이게 한다 | 마지막 보고 뒤 90분 상한(BW6) · 라벨에 "대기"가 남고 glow 가 없다(BW5) · 툴팁이 거둘 시각을 알린다. 안 A 였다면 같은 경우가 「작업중」+glow 다 |
| R2 | 호스트 필드 미도착·형식 변경 | 파서가 보고를 버리고 오늘의 판정으로 돌아간다(오탐 아닌 미검출 방향). V0·V1 |
| R3 | 배열이 세션 범위 → 실행 귀속 불가 | BW7 — 실행 줄을 바꾸지 않는다. 문서화 |
| R4 | LS9 독립 상한이 이 세션들에서 30→90분 | 명부는 취소만 가능, 상한 고정. RI9 R6 과 같은 형태로 명시 수용 |
| R5 | 분리(M1)의 기계적 변경량(참조 약 85줄 — 테스트 7파일 76줄 + hub/bin 5파일, 가드 재조준 10건) | 동작 불변 단독 커밋, 테스트 전부 통과 + 재조준 가드마다 변조 증명(GOTCHA 6) |
| R6 | 동시 작업과의 한 줄 핫스팟 | `SOURCE_GUARD_ID_FLOOR`·원장 머리 개수·T25 번호(245 = 다른 브랜치) · 템플릿 `renderSessionContent`·`renderStateBadge`(이 브랜치 UI 작업) · README 「화면 배치」 — §10 |
| R7 | 명부 unknown(열거 실패) + 프로세스 크래시 + 보고 | 최대 90분 「백그라운드 대기」 후 stale — RI R6 과 같은 계열, 수용 |
| R8 | 320px 최악 조합에서 프로젝트 머리가 5px 여백을 먹는다 | 잘림 없음(실측), 짧은 라벨 선택(GOTCHA 11). 더 줄이려면 테두리 제거(−2px, 열린 카드 윤곽을 잃는다) |

검토했으나 채택하지 않은 대안:

- **A1 안 A — working 으로 센다**(`「작업중 · 백그라운드」` 접미, glow): 사다리가 아니라 LS5 표 세 행과 `is_stale` 을 고쳐야
  하고, dev 서버 세션이 「작업중」+glow 가 된다(장면 4). 호스트 분류(`idle_background`)와도 어긋난다.
- **A2 transcript `<note>`·handback 으로 실행 귀속**: 정확하지만 `message.content` 미판독 약속을 깨고, 영문 문장·128KiB
  창·auto 모드 한정에 묶인다. 사용자가 실행 줄 표시를 원하면 고지 개정과 함께 후속 PRP 로.
- **A3 작업 출력 파일 mtime 으로 생존 판정**(SL1 처럼): 호스트 비공개 경로(`/private/tmp/claude-<uid>/<인코딩>/<세션>/tasks/<id>.output`)
  + 작업 id 기록 필요, `tail -f` 는 출력이 계속 자라 상한이 여전히 필요하다.
- **A4 SubagentStop 사진만 쓴다**(메인 Stop 무시): 메인 소유 셸(§1.2 12:05→12:38)을 놓치고, 알림 턴의 UPS 가 곧바로
  지운다. V0 의 C2 가 실패할 때만 재검토.
- **A5 상한 30분 / 60분**: 30분은 7/25 건을 못 고친다. 60분은 성립 — 쟁점 2.
- **A6 `subagent`·`teammate` 도 깨우는 종류로**: S 와 이중 계산, SubagentStop 자기 포함(U3).

---

## 10. 단계 · 다른 작업과의 겹침

| 단계 | 내용 | 검증 | 착지 |
|---|---|---|---|
| **M0** | V0 캡처(동의 시) — C1·C2 확인. 실패하면 멈추고 보고 | §8.4 | 코드 없음 |
| **M1** | `hub_session_facts.py` 분리(동작 불변), 임포트·테스트 참조 갱신·접기 테스트 이관, 가드 재조준 10건 + T25-253, HUB_FILE_COUNT 30, README·hub-dashboard.md 모듈 표·파일 수 | 전체 검사·unittest 전부 통과, 재조준 가드 변조 증명 | **단독 커밋** |
| **M2** | `BackgroundReport`·정규화·`bt`/`sw` 파싱·BW3 접기, 훅 투영, T25-248·249, P·N·F·H 표 | 〃 | 단독 가능 — 뷰가 무시하므로 화면 무변화(V0 대신 실로그 확인 경로) |
| **M3** | `SessionState` 6값·`BackgroundWait`·`effective_background_wait`·`_display_state`·`SessionView.background_wait`·프로젝트 우선순위·live 집합, T25-150 기대값·T25-219 원장·T25-251, L·E·P·W 표 | 〃 | **M4 와 한 커밋**(GOTCHA 1) |
| **M4** | 템플릿(§7)·README·commands/hub.md·hub-dashboard.md 개정 블록, T25-250·252, D-BW1 | 〃 + V2 | M3 와 함께 |

- **이 브랜치의 UI 작업**(모달 카드 폭·루트 클릭, 미커밋, T25-246·247)이 먼저 커밋된 뒤 착수한다 — 겹치는 곳은
  `renderSessionContent` 의 배지 호출 줄과 원장·`SOURCE_GUARD_ID_FLOOR` 핫스팟이다.
- **ledger-and-name-guard 브랜치**(T25-245)와는 T25 번호·원장 머리 개수·`SOURCE_GUARD_ID_FLOOR` 가 겹친다 — 먼저 들어간
  쪽을 기준으로 뒤에 들어가는 쪽이 번호·개수를 다시 센다(메모리 「동시 세션 주의」 — 병합 직전 main 을 다시 센다).
- 배포 뒤 `/hub server restart` 가 필요하다(새 파이썬을 상주 프로세스에 싣기 — README 「서버」 절). 열린 허브 탭은
  템플릿 세대(SH3)로 60초 안에 스스로 갈아탄다.

---

## 11. 사용자 확인 쟁점

1. **표시 방식** — 안 B: 새 배지 「◐ 백그라운드 대기」, 카드 반짝임 없음(권고, BW5) / 안 A: 「● 작업중 · 백그라운드」,
   반짝임 있음(dev 서버를 띄워 둔 세션도 작업중으로 보인다). 목업 장면 1~4.
2. **믿는 시간** — 보고 뒤 90분(권고 — 실측 최장 40분의 2.2배, 서브에이전트 좀비 상한과 같은 지평) / 60분(끝나지 않는
   작업의 오표시가 30분 짧다, 최장의 1.5배).
3. **착수 전 실측** — 실제 CLI 를 스크래치패드에서 두 번(haiku, 각 1분 안팎) 불러 훅 입력을 확인한다(권고, V0) /
   생략하고 먼저 기록만 배포해 실제 로그로 확인한 뒤 화면을 바꾼다(M1·M2 → 확인 → M3·M4).

(결정만 알림: 서브에이전트 실행 줄은 지금처럼 「종료」로 남는다 — BW7.)

**사용자 결정(2026-09-28)**: 1 → 안 B · 2 → 90분 · 3 → V0 실측 후 착수(모두 권고안).

---

## 12. 검증 명령 (정본 — 프로젝트 CLAUDE.md §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

임포트 실험은 `python3 -B` 로 한다(`__pycache__` 가 commands 파일 수를 흔든다). 전체 검사는 25~40분 걸리므로
백그라운드로 돌리고, 도는 중에 작업 트리를 고치지 않는다(T37 이 행마다 작업 트리를 복사한다 — 메모리).
