# 허브: 아티팩트 실시간 감시 같은 끝나지 않는 구독을 「백그라운드 대기」로 세지 않는다

> 산출: `docs/prps/hub-bg-wait-passive-watch.md` · **설계 모델: opus(승격 기준 미해당)**
> 상태: **승인 (2026-10-21)** — 사용자 선택: 판별 방식 (e) monitor 종류 통째로 제외. V0(PW4) 는 메인이 착수 전 확인(통과, §PW4 끝).
> 기준: `origin/develop` `06c2b06`, 브랜치 `fix/hub-bg-wait-artifact-watch`(워크트리 `.claude/worktrees/hub-bg-wait-watch`) · 작업 경로: 전체 경로
> 결정 접두 **PW**(미사용 확인 — `docs/prps`·`hub`·`tests`·`commands`·`rules`·`agents`·README·CLAUDE.md grep 0건).
> 신설 정적 가드 예정 번호 **T25-294**(이 브랜치의 최대 T25-293). 병합 직전 develop 의 최대 번호·`SOURCE_GUARD_ID_FLOOR`·
> `LEDGER_MUTATION_ROW_FLOOR`·루트 README 의 PRP 수를 다시 센다 — 다른 워크트리(`hub-dashboard-multi-task`)가 같은 자리를 쓸 수 있다.
> **목업 없음** — 새 마크업·클래스·색·배치가 0이다. 바뀌는 것은 영향받는 세션이 이미 있는 두 배지 중 어느 것을 받느냐뿐이다
> (「◐ 백그라운드 대기」 → 「○ 대기」, 30분 뒤 「▲ 소식 없음」). 두 배지의 모습은 BW 목업(장면 1)이 승인받은 그대로다.

## 0. 요구사항 요약

허브는 메인 턴이 끝난 세션에 진행 중인 백그라운드 작업이 남아 있으면 「백그라운드 대기」로 그린다(결정 BW1~BW12,
[`hub-subagent-background-pause.md`](./hub-subagent-background-pause.md)). 그런데 호스트는 아티팩트를 게시한 세션에
**아티팩트 실시간 감시**를 걸어 두고 세션을 재개할 때마다 다시 건다 — 끝이 예정된 작업이 아니라 누가 댓글을 달 때만
신호가 오는 수동 구독이다. 허브는 이것을 훅 보고의 `monitor` 1건으로 세어, 그런 세션은 턴이 끝날 때마다 사용자 차례인데도
90분 동안 「백그라운드 대기」로 보이고 그동안 「소식 없음」으로도 넘어가지 않는다. 이 설계는 훅 기록 형식과 프라이버시
약속(BW2)을 그대로 둔 채, **판정이 「깨우는 종류」로 세는 집합에서 `monitor` 를 뺀다**(BW4 개정). Monitor 도구로 거는
스크립트 감시는 호스트가 `shell` 로 보고하므로 정당한 대기 표시가 유지된다 — 이 전제는 착수 전에 한 번 확인한다(V0).
대가는 Monitor 도구의 **WebSocket 감시**(최대 30분 마감)가 그동안 「대기」로 보인다는 점이고, 그것까지 지키려면 작업
설명 첫머리를 비교하는 안 A2(부록 A)로 간다 — 사용자 결정 사항이다.

---

## 1. 사실과 해석

### 1.1 메인 실측(2026-10-21, 재측정하지 않음)

| # | 사실 |
|---|---|
| F1 | 세션 78af0cc6: 사용자가 작업 종료를 선언했고 데스크톱 「백그라운드 작업」 패널의 실행 중 항목은 0개인데 허브는 「백그라운드 대기」 |
| F2 | 이벤트 기록: 그 세션의 Stop·SubagentStop 이 오늘 첫 보고(12:06)부터 계속 `bt={"monitor":1}`(+그때그때 shell·subagent). 10-16 10:28 은 `bt={}`. 세션은 10-16 14:45·10-20 16:53·10-21 10:30 에 재개됐다 |
| F3 | 실제 항목(SubagentStop 훅으로 받음): `{"id":"s3nil8n03","type":"monitor","status":"running","description":"live updates for artifact https://claude.ai/artifact/… (re-armed on session resume)"}` — 키는 `description,id,status,type` 4개뿐(`server`·`tool` 없음) |
| F4 | 정체: 10-13 Artifact 도구로 소개 페이지를 게시하며 걸린 아티팩트 실시간 감시(웹소켓). 프로세스·출력 파일 없음, 패널에 안 나옴. `TaskStop` 결과 `task_type: monitor_ws`, 끄자 「[Monitor stopped]」 알림 |
| F5 | 대조: Monitor 도구로 건 감시의 ID 는 `b…` 꼴(다른 세션의 `bvqlyfrew`). 서브에이전트 항목은 `a…` |

### 1.2 저장소·공식 문서 근거(설계 판단의 근거 — 직접 읽음)

| # | 출처 | 내용 |
|---|---|---|
| D1 | hooks 「Stop input」 필드 표 | `type` = 기능별 라벨(`shell`·`subagent`·`monitor`·`workflow`·`teammate`·`cloud session`·`MCP task`). **`command` 는 `shell` 에만**, **`server`·`tool` 은 `monitor`·`MCP task` 에만** 있다. `description` 은 "Free-text description"(형식 계약 없음) |
| D2 | BW §1.3-3(2.1.281 코드 판독) | 라벨 표 `monitor_mcp`/`monitor_ws` → `"monitor"`, `local_bash` → `"shell"`. **Monitor 도구(`local_bash` + `kind:"monitor"`)도 `"shell"`** |
| D3 | tools-reference 「Monitor tool」 | 모든 감시에 마감이 있다(기본 5분, **최대 30분**, `-p` 10분). 마감에 Claude 가 알림 1건을 받는다. **WebSocket 원천**(`command` 대신 `ws`)도 같은 마감 |
| D4 | changelog | ① "Monitor watches always have a deadline (at most 30 minutes) … replacing the no-timeout `persistent` option" ② "artifact watching: a watch that was armed automatically (not one you asked for) now ends after 3.5 hours with no activity; publishing or watching the artifact again re-arms it" ③ "**Fixed Desktop and web showing a session as busy while it only watches an artifact for updates**" ④ "a local session can now watch up to 25 published artifacts at once" |
| D5 | background-task-orphans §2.4 | Bash 백그라운드 작업 ID 는 `b2l1gdl7h`·`bfrtiwey5` — F5 의 Monitor ID `b…` 와 같은 계열(`local_bash`) |
| D6 | BW §1.3-6 | 호스트 원격 측정의 `idle_background` 는 "parked MCP" 를 뺀다 — 호스트도 일부 감시를 "바쁨 아님"으로 본다 |
| D7 | `hub_session.py` | 판정의 단일 출처는 `WAKING_BACKGROUND_TASK_TYPES`(현 `{"shell","monitor","workflow"}`)와 그것을 합산하는 `waking_background_task_count` 하나다. 표시(`effective_background_wait`)·출력 파일 탐색 게이트(`is_background_output_scan_target`)·툴팁 작업 수(`task_count`)가 모두 이 식을 쓴다. `"monitor"` 문자열은 `hub/bin` 전체에서 이 한 줄뿐이다 |

### 1.3 해석

1. **훅의 `monitor` 라벨은 Monitor 도구의 스크립트 감시가 아니다.** D1(`command` 는 shell 에만)·D2(코드)·D5+F5(ID 계열)가
   같은 방향이다. `monitor` 에 드는 것은 `monitor_ws`·`monitor_mcp` 이고, 알려진 구성원은 셋이다.

   | 구성원 | 내부 종류 | 끝 | 세션을 깨우나 | 「백그라운드 대기」가 맞나 |
   |---|---|---|---|---|
   | 아티팩트 실시간 감시(자동·요청) | `monitor_ws`(F4) | 없음 — 자동 감시는 무활동 3.5시간에 끝나지만 재개·재게시 때 다시 걸린다(D4②, F3) | 누가 댓글을 달 때만 | **아니다** — 호스트 자신도 "바쁨 아님"으로 고쳤다(D4③) |
   | Monitor 도구 WebSocket 감시 | `monitor_ws`(추정 — 같은 웹소켓 감시) | 최대 30분 마감(D3) | 메시지·마감 알림 | 맞다 |
   | MCP 감시 | `monitor_mcp`(`server`·`tool` 있음, D1) | 미상 | 미상 | 미상(호스트는 "parked MCP" 를 바쁨에서 뺀다, D6) |

2. **훅 입력의 구조 필드로는 아티팩트 감시와 Monitor WebSocket 감시를 가를 수 없다.** 둘 다 `type:"monitor"`·키 4개·
   `status:"running"` 이고, ID 접두가 작업 종류를 따른다면(D5) 같은 `monitor_ws` 라 접두도 같을 공산이 크다. 가르는 것은
   호스트가 쓴 **설명 문구**(`live updates for artifact …`)뿐이다.
3. **"영구히"의 정확한 범위**: 상한(BW6)이 보고마다 90분으로 자르므로 무한히 이어지는 한 번의 표시가 아니다. 대신
   아티팩트 감시가 걸린 세션은 **턴이 끝날 때마다**(Stop·SubagentStop 마다 재무장, BW3) 90분씩 「백그라운드 대기」가 되고,
   감시는 재개 때마다 다시 걸리므로 게시한 적 있는 세션은 앞으로 계속 그렇다. 곁가지 영향: 그동안 「소식 없음」이 눌리고,
   그 세션이 live 집합(BW8)에 들어 다른 세션의 대시보드 「이전 작업」 판정에 섞이고, 알림 모듈의 바쁜 구간이 이어지고,
   수집마다 그 세션의 기록 끝 1MiB 를 출력 파일 탐색으로 읽는다(LA7).

---

## 2. 비목표

| # | 하지 않는 것 | 이유 |
|---|---|---|
| N1 | 호스트의 감시를 끄거나(`TaskStop` 자동화) 재무장을 막기 | 허브는 읽기 전용이다. 아티팩트 댓글 자동 답장 같은 사용자 기능을 끈다 |
| N2 | `shell` 로 오는 끝나지 않는 작업(dev 서버·`tail -f`·플러그인 감시) 판별 | 명령줄을 읽어야 한다(BW N5). BW6 의 90분 상한이 그대로 받친다 — §9 R3 |
| N3 | 훅 기록 형식(`bt`·`sw`) 변경 | 판정층에서 풀린다(PW2) |
| N4 | 상한 90분(BW6)·사다리(BW5)·live 집합(BW8)·화면 | 이번 결함과 무관 |
| N5 | 새 설정 스위치 | BW N6 과 같은 판단 |

---

## 3. 판별 근거 비교 (R2)

| 안 | 판별 근거 | 문서 근거 | 취약성(호스트 변경) | BW2 충돌 | 아티팩트 감시 | 스크립트 Monitor | Monitor WebSocket 감시 | MCP 감시 | 틀릴 때의 방향 | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|
| **(a)** description 고정 머리 | `type=="monitor"` ∧ 설명이 `live updates for artifact ` 로 시작 | 없음 — 설명은 자유 텍스트(D1). 관측 1건 | 문구가 바뀌면(이 기능은 changelog 에 개정 다수) 조용히 지금 결함으로 돌아간다 | **있음** — 설명을 읽는다. 최소화: monitor 항목만·고정 머리 일치 1비트·값은 기록 안 함(부록 A) | 해소 | 유지 | 유지 | 오늘과 같음 | 오표시(보고마다 ≤90분) | **대안**(부록 A) |
| (b) id 접두 | 첫 글자 `s` | 없음("Task identifier") | 내부 ID 규칙. 접두가 종류를 따르면(D5) WebSocket 감시도 같은 접두 → (e)와 같은 결과를 더 약한 근거로 | 있음(id 1글자 — 자유 텍스트 아님) | 해소(규칙 유지 동안) | 유지 | 아마 놓침 | 미상 | 양방향 | 기각 |
| (c) status | `status` 값 | 호스트가 running·pending 만 싣는다(BW §1.3-2) | — | 있음 | **판별력 0**(F3 도 running) | — | — | — | — | 기각 |
| (d) 지속 시간 | monitor 만 남은 보고는 Monitor 마감 상한(30분)+여유 뒤 만료 | 있음(D3·D4①) | 마감 상한이 바뀌면 상수 갱신 | 없음 | **부분** — 매 턴 뒤 30분여는 여전히 「백그라운드 대기」 | 유지 | 유지 | 30분 넘는 MCP 감시는 놓침 | 오표시가 줄 뿐 남음 | 기각(R1 미충족) |
| **(e)** monitor 전체 제외 | `WAKING_BACKGROUND_TASK_TYPES` 에서 `"monitor"` 제거 | 있음 — D1·D2·D5 가 스크립트 감시 = `shell` 을 받친다 | 호스트가 스크립트 감시를 `monitor` 로 재라벨하면 정당한 대기를 놓친다 — D1 표와 어긋나는 계약 변경이라 가능성 낮음, 착수 전 V0 | **없음**(훅·기록 무변경) | 해소 | 유지(V0 전제) | **놓침** → 「대기」, 최대 30분 뒤 마감 알림으로 작업중 | 놓침(수동 구독이면 오히려 맞음) | 놓침 = BW 이전 표시 「대기」 | **권고** |
| (f) 키 모양 | monitor 항목에 `server`·`tool` 키가 있나(값 안 읽음) | 있음(D1) | — | 낮음(키 이름만) | **못 가름** — 아티팩트·WebSocket 감시 모두 키 4개 | — | — | — | — | 기각(문제를 풀지 않음) |

- (d) 의 "연속 보고 시간" 변형은 성립하지 않는다 — 항목 ID 를 남기지 않으므로 같은 감시가 이어진 것인지, 마감마다 재무장한
  새 감시인지 구별할 수 없다.
- 오판 방향의 비대칭: (e)의 놓침은 「대기」(BW 이전부터의 표시)로 떨어지고 Monitor 마감(≤30분)이 끝을 보장한다. (a)의 실패는
  사용자 차례인 세션을 바쁜 것처럼 가리는 지금의 결함 그대로다. BW4 가 `mcp_task`·`cloud_session` 을 "제외가 페일오픈"으로 뺀
  것과 같은 방향의 선택이 (e)다.

---

## 4. 설계 결정

| ID | 한 줄 |
|---|---|
| PW1 | 판별 = 안 (e). 깨우는 종류를 `{"shell","workflow"}` 로 줄인다(BW4 개정) |
| PW2 | 훅·이벤트 줄·프라이버시 무변경 — `bt` 는 호스트 라벨 그대로 `monitor` 를 계속 센다. 판정만 바꾼다 |
| PW3 | 같은 식의 소비자(표시·출력 파일 탐색 게이트·툴팁 작업 수)가 함께 바뀐다. 상한·사다리·live 집합은 그대로 |
| PW4 | V0 게이트 — 착수 전 현행 호스트에서 스크립트 Monitor 가 `shell` 로 보고되는지 확인. 실패하면 (e) 를 멈추고 부록 A 로 |
| PW5 | 정적 가드 T25-294(역) 신설 + T25-251 원장 행 리터럴 갱신, FLOOR 2개 +1 |
| PW6 | 문서 — README 「화면 배치」 항목, hub-dashboard.md·BW PRP 개정 블록, 루트 README PRP 수. 프라이버시·설치 고지 무변경 |

### PW1. 판별 — `monitor` 를 깨우는 종류에서 뺀다

- BW4 는 "호스트 keepalive 사유(`bash:`·`monitor:`·`workflow:`)와 같은 집합"을 근거로 `monitor` 를 넣었다. 그러나 훅 라벨
  `monitor` 는 keepalive 의 `monitor:`(Monitor 도구 감시 — 훅에서는 `shell`, D2)와 같은 것이 아니다. 훅의 `monitor` 에 실제로
  드는 것 중 확인된 것은 끝나지 않는 아티팩트 감시뿐이고(F2·F3), 그것은 모든 턴 뒤를 90분씩 가린다.
- 아티팩트 감시만 골라낼 구조 신호가 없다(§1.3-2). 남는 길은 설명 문구(안 a)인데, 그 대가(프라이버시 원칙 변경 + 문구
  의존)가 잃는 것(Monitor WebSocket 감시 중 최대 30분의 「백그라운드 대기」)보다 크다고 판단한다 — 이 판단이 §11 쟁점 1이다.
- **가장 단순한 구조를 골랐다**(YAGNI) — 바뀌는 코드는 상수 원소 1개와 그 주석이다. 패턴·새 함수·새 타입 0.

### PW2. 기록은 충실하게, 판정만 바꾼다

- 훅(`hub_hook.py`)이 `monitor` 항목을 걸러 내면 판정은 같아지지만 하지 않는다. ① 이번 진단이 가능했던 것은 기록에
  `bt={"monitor":1}` 이 남아서다 — 기록에서 지우면 다음 원인 추적의 근거가 사라진다. ② 판정층(`hub_session.py`) 변경은 이미
  쌓인 옛 줄에도 배포 순간 그대로 적용된다(소급 이행 0). ③ 이전 판 허브가 새 줄을 읽는 호환 문제가 생길 여지가 없다.
- 그래서 R3(형식 변경) 항목은 전부 "해당 없음"이다: 재검증 패턴(`BACKGROUND_TASK_TYPE_PATTERN`)·상한 상수
  (`BACKGROUND_TASK_SCAN_MAX`·`KIND_MAX`·`COUNT_MAX`)·`_parse_background_report`·T25-248·T25-249 무변경. 부록 A 를 고르면
  달라진다(그쪽에 정리).

### PW3. 함께 바뀌는 소비자

`waking_background_task_count` 가 단일 출처라(D7) 상수 하나로 아래가 같이 움직인다 — 따로 고칠 곳이 없다.

| 소비자 | 지금(아티팩트 감시만 있는 세션) | 뒤 |
|---|---|---|
| `effective_background_wait` → 세션·프로젝트 배지 | background(보고 뒤 90분) | idle → 30분 뒤 stale |
| `is_background_output_scan_target` → 수집마다 기록 끝 1MiB 읽기 | 참 | 거짓(읽지 않는다) |
| `BackgroundWait.task_count` → 툴팁 「백그라운드 작업 N개」 | 셸이 함께 있으면 셸 + 1 | 셸 수만 |
| `LIVE_SESSION_STATES`·알림 바쁜 구간(`_BUSY_PHASES`) | 이 세션이 live·바쁨 | idle 로 빠진다 |

### PW4. V0 — 착수 전 1회 확인(구현 단계, 설계에서는 재지 않았다)

전제: 현행 호스트(2.1.30x)가 Monitor 도구의 **스크립트 감시**를 훅 `background_tasks` 에 `type:"shell"` 로 싣는다(D2 는 2.1.281
판독). 확인 경로(위에서부터 되는 것 하나):

1. **이미 있는 기록**: Monitor 감시(`b…`)를 건 채 턴을 끝낸 시점의 Stop 줄을 `~/.claude/hub/events/<날짜>.jsonl` 에서 읽는다
   (읽기 전용). 그 시각의 `bt` 에서 늘어난 것이 `shell` 이면 통과, `monitor` 면 실패. 아티팩트 감시가 함께 걸려 있으면
   `monitor` 가 원래 1 이상이므로 **늘어난 쪽**으로 판정한다.
2. 기록이 없으면: 메인이 Monitor 로 짧은 스크립트 감시(마감 1분)를 걸고 곧바로 턴을 끝낸 뒤, 마감 알림으로 깨어나면 직전
   Stop 줄을 같은 방법으로 본다.

- **통과** → PW1 구현. **실패** → (e) 는 R1 의 주 사례(사용자 Monitor)를 놓치므로 구현을 멈추고, 그 사실과 함께 부록 A(안 A2)로
  갈지 사용자에게 다시 묻는다(설계 반려가 아니라 이 문서가 미리 정한 분기다).

**V0 결과(2026-10-21, 메인, 경로 1 — 통과)**: klago 세션 `e5588c1a` 의 10-16 기록. 스크립트 Monitor 2개를 09:42·09:43(KST)에
걸었고(`timeout_ms` 1800000, 둘째가 `bvqlyfrew` — 10:13 에 「Monitor expired after 30m」 알림). 그 세션 Stop 줄의 `bt` 는
09:31~10:24 내내 `monitor: 1` 로 변하지 않았고(이 세션과 같은 상시 구독으로 보인다), 감시가 끝난 10:13:37 에 **`shell` 이 2→1**
로 줄었다. 스크립트 Monitor 는 `shell` 로 보고된다 — 전제 성립. 덧붙여 이 기록은 다른 세션에서도 같은 오표시(`monitor` 상시 1)가
있었음을 보인다.

### PW5. 정적 가드·원장(R4) — §8

### PW6. 문서 — §5 표와 §7.1 문구

---

## 5. 영향 범위

| 파일 | 변경 | 규모 |
|---|---|---|
| `hub/bin/hub_session.py` | `WAKING_BACKGROUND_TASK_TYPES` 를 `frozenset({"shell", "workflow"})` 로, 위 주석을 PW1 근거로 개정(§6) | ±1줄 + 주석 ~4줄 |
| `tests/hub/test_hub_session.py` | 기대값 개정 2건 + 신설 클래스 `PassiveSubscriptionTest`(§7) | +~90 |
| `tests/hub/test_hub_hook.py` | `BackgroundProjectionTest` 에 관측 페이로드 고정 테스트 1건(PW2 고정) | +~25 |
| `tests/run.sh` | T25-294 블록, `test_desc` 범위 `T25-1~T25-294`, `SOURCE_GUARD_ID_FLOOR` 572→573·`LEDGER_MUTATION_ROW_FLOOR` 145→146 과 각 이력 주석 | +~15 |
| `tests/mutations.tsv` | T25-251 행 sed 리터럴 갱신, T25-294 변조행 신설 | ±1 +1 |
| `hub/README.md` | 「화면 배치」 백그라운드 대기 항목(§7.1) | ~+3 |
| `docs/prps/hub-dashboard.md` | 「상태 판정 규칙」의 BW 개정 블록 뒤에 PW 개정 블록 | +3 |
| `docs/prps/hub-subagent-background-pause.md` | BW4 절 끝에 개정 블록(이 저장소의 「개정됨」 관례) | +4 |
| `README.md`(루트) | 「설계·조사 문서 93개」 → 94개(이 PRP) | 1 |

**건드리지 않는 것**: `hub_hook.py`·`hub_session_facts.py`(기록·재검증) · `hub_subagent_read.py`·`hub_activity.py`(게이트 결과만
달라진다) · `hub_notify.py`·`hub_project.py` · `hub_template.html`(배지·툴팁 문구 그대로) · `commands/hub.md`·README 「프라이버시
고지」·「훅 옵트인」(읽고 남기는 것이 그대로) · `hub_handback_guard.py`(셸 시작 문구만 본다 — background-task-orphans 무영향) ·
`rules/`·`CLAUDE.md`(T26 무영향) · `HUB_FILE_COUNT`(새 파일 0) · 템플릿 DOM 테스트(`BackgroundWait` 를 직접 만든다).

---

## 6. 데이터 모델과 인터페이스

타입·시그니처 변경 0. `BackgroundReport`·`BackgroundWait`·`SessionView`·`waking_background_task_count(report) -> int`·
`effective_background_wait(...)`·`is_background_output_scan_target(...)` 그대로. 바뀌는 것은 상수 하나다.

```python
# 깨우는 종류(결정 BW4, 개정 PW1 — docs/prps/hub-bg-wait-passive-watch.md). shell·workflow 만 센다.
# shell 에는 Monitor 도구의 스크립트 감시도 든다(호스트가 local_bash 로 등록 — 마감 최대 30분, 끝나면 세션을 깨운다).
# monitor 는 뺀다 — 훅의 monitor 라벨은 아티팩트 실시간 감시(재개 때마다 다시 걸리는 끝나지 않는 구독)와 Monitor
# WebSocket 감시·MCP 감시를 한데 묶어 종류만으로는 가를 수 없고, 설명 문구는 읽지 않는다(BW2).
# subagent·teammate 는 훅이 이미 실행(S)으로 추적하므로 빼면 이중 계산이고(U3), dream·auto_mode_scan·
# cloud_session·mcp_task·unknown 은 깨움 경로가 확인되지 않아 뺀다(페일오픈 — 오늘과 같은 방향).
WAKING_BACKGROUND_TASK_TYPES: frozenset[str] = frozenset({"shell", "workflow"})
```

GOTCHA:
1. `tests/mutations.tsv` 의 T25-251 행 sed 는 `frozenset({"shell", "monitor", "workflow"})` 리터럴을 문다 — 상수를 바꾸면 변조가
   적용되지 않는다. 같은 커밋에서 새 리터럴로 고친다(§8).
2. 주석 첫 줄에 `monitor` 가 들어가도 T25-251·T25-294 는 `^WAKING_BACKGROUND_TASK_TYPES` **선언 줄만** 뽑아 보므로 무해하다.
   주석을 선언 줄 뒤에 붙이지 않는다(같은 줄 주석 금지).
3. 임포트 실험은 `python3 -B`(pycache 가 commands 파일 수를 흔든다 — 메모리).

---

## 7. 테스트 계획

### 7.1 단위 (`tests/hub`, stdlib unittest, AAA) — RED 먼저

**신설 `test_hub_session.py::PassiveSubscriptionTest`**(명부는 `LiveSessionIndex` 로 주입, 기존 `BackgroundWaitLadderTest` 의
헬퍼 `_event`·`_facts_from`·`_idle_roster` 재사용). 표의 「지금」 열이 RED 근거다.

| # | 사실 | 명부 | now − 보고 | 기대 | 지금 |
|---|---|---|---|---|---|
| PW-L1 | Stop `bt={"monitor":1}` 단독 | idle | 10분 | state `idle`, `background_wait is None` | background |
| PW-L2 | 같음 | idle | 31분 | `stale` | background |
| PW-L3 | Stop `bt={"monitor":1,"shell":2}` | idle | 10분 | `background`, `task_count == 2` | task_count 3 |
| PW-L4 | Stop `bt={"monitor":1}`, `sw=1` | idle | 10분 | `background`, `task_count == 0`, `wakeup_count == 1` | task_count 1 |
| PW-L5 | 사례 재생(가짜 id·cwd): 12:06 Stop `{monitor:1}` → 12:10 UPS → 12:20 Stop `{monitor:1, shell:1}` → 12:40 UPS(작업 알림) → 12:41 Stop `{monitor:1}` | idle | now 12:30 · 12:45 | `background` · `idle` | background · background |
| PW-G1 | `is_background_output_scan_target`(Stop `{monitor:1}`) | — | 10분 | `False` | True |

**개정**(같은 테스트, 기대값만):
- `EffectiveBackgroundWaitTest.test_e4_only_waking_kinds_are_summed`: `(dream 5, monitor 3, shell 2, subagent 7)` → `task_count`
  **5 → 2**, 주석 "shell 2 — monitor·dream·subagent 는 제외(BW4·PW1)".
- `BackgroundOutputScanGateTest.test_waking_count_sums_only_waking_kinds`: `(dream 5, monitor 3, shell 2, subagent 7, workflow 1)` →
  **6 → 3**.
- `test_waking_count_matches_what_effective_background_wait_reports` 는 두 값이 함께 움직여 그대로 통과한다(개정 없음).

**신설 `test_hub_hook.py::BackgroundProjectionTest`** — H-PW1(PW2 고정, 처음부터 GREEN): 관측 페이로드 모양 그대로
`background_tasks=[{"id":"s…","type":"monitor","status":"running","description":"live updates for artifact https://claude.ai/artifact/X (re-armed on session resume)"}, {"id":"a…","type":"subagent","status":"running","agent_type":"bt-probe","description":"…"}]`
인 SubagentStop → 줄의 `bt == {"monitor":1,"subagent":1}`, 설명 문자열·`claude.ai/artifact`·두 id 가 이벤트 파일 어디에도 없다.
누군가 훅에서 monitor 를 걸러 내는 "수정"(PW2 위반)을 하면 이 테스트가 깨진다.

- 종단(`test_hub_collect`)·DOM 테스트는 추가하지 않는다 — 배선이 바뀌지 않았고(같은 함수·같은 호출), 상수의 효과는 순수
  층 테스트가 전부 문다.

### 7.2 수동

- **V0**(PW4) — 착수 전.
- **V1**(배포 뒤): 아티팩트 감시가 걸린 세션에서 턴을 끝내면 허브가 「대기」로 보인다(30분 뒤 「소식 없음」). Monitor 스크립트
  감시를 걸고 턴을 끝낸 세션은 「백그라운드 대기」로 보이고, 툴팁의 작업 수에 아티팩트 감시가 섞이지 않는다.

### 7.3 README·문서 문구(정본 초안)

- **hub/README.md 「화면 배치」 백그라운드 대기 항목**: "(셸·모니터·워크플로우)" → "(셸·워크플로우 — Monitor 도구의 스크립트
  감시는 셸로 센다)". 항목 끝(「…가장 최근 수정 시각이다.」 뒤)에 한 문장: "아티팩트 실시간 감시처럼 호스트가 걸어 두는 끝나지
  않는 구독(종류 `monitor`)은 세지 않는다 — 기다릴 끝이 없어서다. 같은 종류로 보고되는 Monitor 도구의 WebSocket 감시도 그래서
  이 표시에 들지 않는다(최대 30분 뒤 끝나며 세션을 깨운다)."
- **docs/prps/hub-dashboard.md** BW 개정 블록 뒤: "> **개정 →(결정 PW1, `hub-bg-wait-passive-watch.md`)**: 깨우는 종류에서
  `monitor` 를 뺀다 — `shell`·`workflow` 와 1회성 예약 깨우기만 센다. 훅 기록(`bt`)은 그대로다."
- **docs/prps/hub-subagent-background-pause.md** BW4 절 끝: "> **개정됨(2026-10-21, [`hub-bg-wait-passive-watch.md`](./hub-bg-wait-passive-watch.md)
  결정 PW1) — BW4.** `monitor` 를 깨우는 종류에서 뺀다. 훅 라벨 `monitor` 는 keepalive 사유 `monitor:`(Monitor 도구 감시 — 훅에서는
  `shell`, §1.3-3)가 아니라 `monitor_ws`·`monitor_mcp` 이고, 그중 아티팩트 실시간 감시는 재개 때마다 다시 걸리는 끝나지 않는
  구독이라 모든 턴 뒤를 90분씩 「백그라운드 대기」로 가렸다. 집합은 `{"shell","workflow"}` 다. BW2(종류만 읽는다)는 그대로다."

---

## 8. 정적 가드와 원장 (R4)

| 항목 | 내용 |
|---|---|
| **T25-294 PW-G1(신설, 역)** | T25-251 이 이미 뽑은 `waking_background_task_types_line_251` 을 재사용한다. 그 줄이 비어 있지 않고 `"monitor"` 를 담으면 `note_failure "T25-294: WAKING_BACKGROUND_TASK_TYPES 에 monitor 가 있음(끝나지 않는 수동 구독 — 결정 PW1 위반)"`. 줄이 비면 T25-251 이 이미 보고하므로 여기서는 중복 보고하지 않는다. 위치는 T25-251 블록 바로 뒤, 주석에 근거 한 줄 |
| T25-294 원장 변조행 | `T25-294	hub/bin/hub_session.py	s/WAKING_BACKGROUND_TASK_TYPES: frozenset\[str\] = frozenset({"shell", "workflow"})/WAKING_BACKGROUND_TASK_TYPES: frozenset[str] = frozenset({"shell", "monitor", "workflow"})/	T25	WAKING_BACKGROUND_TASK_TYPES 에 monitor 가 있음	<결함: 깨우는 종류에 monitor 가 되돌아오면(BW4 의 keepalive 집합 논리로 "맞추는" 수정) 아티팩트 감시를 건 세션이 턴마다 90분씩 「백그라운드 대기」로 가려진다>		test_hub_docs_and_constants` — `expect_token` 은 실패 보고 줄에서 1건만 나와야 한다(T25-251 의 "subagent/teammate 가 있음" 과 겹치지 않음) |
| T25-251 원장 행 개정 | sed 를 새 리터럴 기준으로: `s/…frozenset({"shell", "workflow"})/…frozenset({"shell", "workflow", "subagent"})/`. 기대 토큰·결함 설명 그대로(GOTCHA 1) |
| `test_desc` | `"허브 문서·상수 정합성 (T25-1~T25-293)"` → `T25-294`(4185행의 낡은 하위 주석 "T25-1~T25-274" 는 이번 범위 밖이라 두고 언급만) |
| `SOURCE_GUARD_ID_FLOOR` | 572 → **573**, 이력 주석 "572 → 573(hub-bg-wait-passive-watch.md, 결정 PW1): 신설 1건 T25-294 …" — `collect_guard_ids` 를 재현해 편집 전·후 재측정해 차집합 +1 을 확인한다 |
| `LEDGER_MUTATION_ROW_FLOOR` | 145 → **146**, 이력 주석(T25-294 변조행 1건) |
| 문서 토큰 가드 | **신설하지 않는다** — README 문장은 설명이고, 행동은 단위 테스트(PW-L1~L5·G1)와 T25-294 가 문다. T25-252 의 기존 토큰은 이번 개정 문구에 닿지 않는다 |
| 비용 | 변조행 1건 ≈ T25 그룹 단독 재실행 1회(원장 머리 환산 6초 남짓). 기본 실행(K6)은 이번에 닿은 행만 판정한다 |

- 가드가 필요한 이유(관례 근거): BW4 의 다른 제외 결정(subagent·teammate)도 T25-251 역검사로 물려 있다. 이번 제외는 BW4 의
  원래 근거("keepalive 집합과 같게")를 그대로 읽은 사람이 되돌리기 쉬운 자리라 같은 장치를 둔다. 단위 테스트만으로도 되돌림은
  잡히지만, 가드 메시지가 결정 ID 를 가리켜 "왜 빠졌는가"를 되돌리는 사람에게 바로 알린다.
- 번호·두 FLOOR 는 병합 직전 develop 기준으로 다시 센다(메모리 「동시 세션 주의」).

---

## 9. 리스크와 대안

| # | 리스크 | 대응 |
|---|---|---|
| R1 | Monitor 도구의 WebSocket 감시를 건 세션이 감시 동안(≤30분) 「대기」로 보인다 | BW 이전과 같은 표시, 마감 알림이 끝을 보장한다. 지키려면 부록 A — §11 쟁점 1 |
| R2 | 호스트가 스크립트 감시를 `monitor` 로 재라벨(또는 V0 가 이미 그렇다고 보임) | V0(PW4) 실패 시 부록 A 로 분기. 착수 뒤 바뀌면 사용자 Monitor 대기가 「대기」로 떨어진다(오표시가 아니라 놓침 방향) |
| R3 | 끝나지 않는 구독이 `shell` 로 오는 경우 — 플러그인 감시(세션 시작 때 자동으로 걸린다, 라벨 미확인)·dev 서버·`tail -f` | 이 설계로는 안 풀린다(N2). BW6 상한 90분이 그대로 받친다. 플러그인 감시를 쓰게 되면 그때 같은 방식으로 다시 본다 |
| R4 | MCP 감시 중 끝이 있는 것이 있다면 놓친다 | 의미가 미상이고(D1·D6) 관측 0건. 놓침 방향 — BW4 의 `mcp_task` 제외와 같다 |
| R5 | 아티팩트 댓글 자동 답장을 기다리는 세션도 「대기」로 보인다 | 의도 — 호스트 자신도 아티팩트만 감시하는 세션을 바쁨으로 보지 않게 고쳤다(D4③). 댓글이 오면 턴이 돌아 작업중이 된다 |
| R6 | 동시 작업과의 핫스팟(T25 번호·두 FLOOR·원장·루트 README PRP 수) | 병합 직전 재계수 |

검토했으나 채택하지 않은 대안:
- **A1 안 (a) — 설명 첫머리 비교**: 셋 중 아티팩트 감시만 정확히 뺀다. 대가는 BW2("설명을 읽지 않는다") 개정과 호스트 문구
  의존(바뀌면 지금 결함이 조용히 돌아온다). 사용자가 WebSocket 감시까지 지키길 원하면 채택 — 명세는 부록 A.
- **A2 안 (d) — monitor 만 남은 보고의 상한을 30분대로**: 문서 근거가 있고 프라이버시 비용이 없지만 아티팩트 세션이 매 턴 뒤
  30분여를 여전히 「백그라운드 대기」로 보인다 — R1(세지 않는다)을 채우지 못한다.
- **A3 훅에서 monitor 를 걸러 기록하지 않기**: 판정은 같지만 원인 추적 기록을 잃고 옛 줄에 소급되지 않는다(PW2).

---

## 10. 단계·검증·배포

한 커밋(`fix: …`)으로 착지한다 — 코드 변경이 상수 하나라 단계를 나눌 이유가 없다.

| 순서 | 내용 | 검증 |
|---|---|---|
| 1 | V0(PW4) | 통과 기록을 구현 보고에 남긴다. 실패면 멈추고 보고 |
| 2 | §7.1 신설·개정 테스트 → 변경 전 코드에서 PW-L1·L2·L3·L4·L5·G1 과 개정 2건이 **실패**함을 확인(RED) | `python3 -B -m unittest tests.hub.test_hub_session tests.hub.test_hub_hook` |
| 3 | 상수·주석 개정 → GREEN | 같은 명령 |
| 4 | T25-294·원장·FLOOR 2개·`test_desc` → T25-294 를 손으로 되돌려(monitor 재추가) 실패, 복원해 통과 | 변조행 수동 1회 |
| 5 | 문서 4곳 | — |
| 6 | 전체 검증(메인이 커밋 직전 1회) | 아래 |

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

`py_compile` 뒤 `__pycache__` 를 지운다(메모리). 전체 검사는 백그라운드로 돌리고 도는 동안 작업 트리를 고치지 않는다.
배포는 기존 관례대로 사용자의 `/harness-update` 뒤 허브 서버 재시작 — 새 훅·설정 0 이라 `/hub install` 재실행은 필요 없다.
배포 순간부터 이미 쌓인 이벤트 줄에도 새 판정이 적용된다(PW2).

---

## 11. 사용자 확인 쟁점

1. **판별 방식** — **권고: (e) `monitor` 종류를 통째로 세지 않는다.** 훅 기록·프라이버시 약속이 그대로이고 호스트 문구가
   바뀌어도 깨지지 않는다. 대가: Monitor 도구의 WebSocket 감시(웹소켓 이벤트를 받는 감시 — 이 작업 흐름에서는 드물다)를 건
   세션은 그 감시가 끝날 때까지(최대 30분) 「대기」로 보인다. / **대안: (a) 작업 설명 첫머리가 아티팩트 감시 문구인지 비교해
   그것만 뺀다**(부록 A) — 모든 정당한 대기를 지키지만 "작업 설명은 읽지 않는다"를 1비트만큼 바꾸고(기록은 여전히 안 함),
   호스트가 문구를 바꾸면 지금 결함이 조용히 돌아온다.

(결정만 알림: 착수 전 V0 로 "스크립트 Monitor = 셸" 전제를 확인하고, 틀리면 (a)로 갈지 다시 묻는다 · 정적 가드 1개 추가.)

---

## 부록 A. 안 (a)(=A2)를 고르면 바뀌는 것

| 항목 | 내용 |
|---|---|
| 판별 | 훅 `_task_type_counts` 에서 정규화 결과가 `monitor` 인 항목에 한해, 신설 `_is_artifact_live_watch(task: dict) -> bool`(설명이 문자열이고 `ARTIFACT_LIVE_WATCH_DESCRIPTION_PREFIX` 로 시작하는가 — 값을 담아 두거나 넘기지 않는다)이 참이면 종류를 `artifact_watch` 로 센다 |
| 상수(`hub_session_facts.py`) | `ARTIFACT_LIVE_WATCH_TASK_TYPE = "artifact_watch"`(패턴 `[a-z_]{1,32}` 통과) · `ARTIFACT_LIVE_WATCH_DESCRIPTION_PREFIX = "live updates for artifact "`(F3 관측 원문, 대소문자 그대로) |
| 판정 | `WAKING_BACKGROUND_TASK_TYPES` 무변경 — `artifact_watch` 는 원래 집합 밖이라 세지 않는다. PW-G1(T25-294 역)은 쓰지 않는다 |
| 이벤트 줄(R3) | `bt` 모양 그대로, 새 키 이름 하나. 재검증(`_parse_background_report`)은 패턴만 보므로 무변경. `KIND_MAX`(8) 의 한 자리를 쓴다. 이전 판 허브가 새 줄을 읽으면 모르는 비깨움 종류 → 올바르게 「대기」. **옛 줄의 `monitor:1` 은 소급되지 않는다** — 배포 뒤 마지막 보고마다 최대 90분 더 오표시(이벤트 창이 지나면 사라진다) |
| BW2 개정 | "각 작업에서 읽는 것은 `type` 한 필드뿐" → "`type`, 그리고 `type` 이 `monitor` 인 항목에 한해 설명이 고정 머리로 시작하는지 1비트. 설명은 기록하지 않는다" |
| 가드 | T25-249 개정(같은 ID): `hub_hook.py` 전역 `"description"` 리터럴 금지에 `_is_artifact_live_watch` 본문 1곳 예외 + 그 본문에 `.startswith(` 가 있고 `fields`·설명 값을 반환하는 줄이 없다는 역검사. T25-294(정, 신설): `_task_type_counts` 가 `_is_artifact_live_watch(` 를 경유. FLOOR·LEDGER +1 은 같다 |
| 고지 | README 「훅 옵트인」·「프라이버시 고지」에 "종류가 `monitor` 인 항목은 설명 첫머리가 아티팩트 실시간 감시 문구인지만 비교하고 설명은 남기지 않는다" · `commands/hub.md` 설치 고지 ① 에 같은 한 구절 |
| 테스트 | 훅 H-A1(아티팩트 문구 → `artifact_watch`, 설명·URL 미기록) · H-A2(다른 문구의 monitor → `monitor`) · H-A3(같은 문구라도 `type:"shell"` → `shell`) · H-A4(설명이 문자열 아님 → `monitor`). 파싱: `artifact_watch` 키 수용. 판정: `artifact_watch` 만 → idle, `monitor` 만 → background(유지) |
| 취약성 | 호스트가 설명 문구를 바꾸면 `monitor` 로 되돌아가 지금 결함이 돌아온다(경보 없음). 문구 변경을 잡는 장치는 두지 않는다 — 호스트 문자열을 감시할 수단이 없다 |
