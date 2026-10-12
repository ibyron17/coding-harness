# 허브: 사용량 한도로 끊긴 세션을 「작업중」 대신 「한도 초과」로 보여 준다

> 산출: `docs/prps/hub-rate-limit-interruption.md` · 설계 모델: opus(디스패치 기본값)
> 상태: **승인됨(2026-09-23)** — §11 쟁점 1~5 전부 권고안대로. 단 쟁점 5 의 「순서」는 승인 직후
> 사용자 질문("main 이랑 다른 워크트리 작업이 오래 걸릴 것 같은데 계속 기다려야 하나?")으로 **착수는
> 지금(이 워크트리), 합치기만 늦춘다**로 바꿨다(§10 결정). 수동 검증 V1 은 승인 직후 메인 세션이
> 1회 수행해 **메인 스레드 실발화를 확인**했다(§8.2 결과).
> 결정 접두 **RI**(미사용 확인 — `docs/prps/*.md` 전수 + `hub-session-modal` 워크트리 PRP).
> 신설 정적 가드는 이름(RI-G1~G4)으로 적고 번호는 구현 착수 시 배정한다(§8.3 — 번호 공간에
> 이미 충돌이 있다, §10).
> 프리뷰 목업(현재 | 안 A | 안 B, 라이트·다크·최소 폭·hover·선택):
> `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/b9e7ab09-6076-480f-9d39-31dcb8072397/scratchpad/hub-rate-limit-mockup.html`

## 0. 요구사항 요약

세션이 사용량 한도(rate limit)에 걸려 턴이 끊기면 호스트는 `Stop` 훅을 보내지 않는다. 허브는
`UserPromptSubmit`→running, `Stop`→ended 로 턴을 접으므로 그 세션을 계속 **「작업중」**으로
그리고(한도 오류로 죽은 서브에이전트도 `SubagentStop` 이 없어 「진행 중」으로 남는다), 30분
뒤에는 **「소식 없음 · 직전 작업중」**으로 바꾼다 — 어느 쪽도 "한도 때문에 멈췄고 언제 다시
되는가"를 말하지 않는다. 이 설계는 ① 한도로 끊긴 턴을 사실로 기록하고(호스트 훅 `StopFailure`
\+ transcript 의 API 오류 줄), ② 그 세션을 새 상태 **「한도 초과」**로 보여 주며(초기화 예정
시각을 알면 함께), ③ 사용자가 다시 지시하면 원래 판정으로 돌아가게 한다. 한도는 계정 단위라
한 번 걸리면 여러 세션이 함께 멈추는데, 그것이 「작업중」으로 보이면 사용자는 기다릴지 다시
지시할지를 판단할 수 없다 — 이것이 고치려는 실패다.

---

## 1. 실측 (2026-09-23, 판단 근거)

측정은 전부 스크래치패드의 `python3 -B` 스크립트로 했고 **구조 필드만** 읽었다(대화 본문 미열람).
스크립트(`survey_errors.py`·`xref.py`·`replay.py`)는 세션 스크래치패드에 있어 영구 보존되지 않는다
— 방법은 아래에 재현 가능하게 적는다.

### 1.1 재현 사례를 **현재 코드**로 재생

세션 `7429bac9`(atlas-ui-notebook-micro). `~/.claude/hub/events/2026-09-22·23.jsonl` 을
`hub_session.parse_event_line` → `build_session_facts`(`now_ms` 이전 이벤트만) →
`compute_session_view` 로 재생했다. 미종료 서브에이전트의 활동 시각은 그 실행 transcript 의
`timestamp` 중 `now_ms` 이전 최댓값(= 그 순간의 mtime)으로 넣었다. 명부는 기록이 16:32:44 에
덮여 당시 값을 알 수 없어 3가지로 모두 돌렸다.

| now (KST) | turn_state | 실행 중 서브에이전트 | 명부 unknown | 명부 busy | 명부 idle |
|---|---|---|---|---|---|
| 15:38:05(한도 직전) | ended | 3 | working | working | working |
| 15:38:40 | running | aad2ad69(좀비) | working | working | working |
| 15:50:00 · 16:08:32 | running | aad2ad69 | working | working | working |
| 16:08:35 · 16:20 · **16:30(초기화)** · 16:32:40 | running | aad2ad69 | stale/working | stale/working | stale/working |
| 16:32:50(재개) | running | aad2ad69 | working | working | working |

**결론**: 사용자는 30분간 「작업중」, 이어서 24분간 「소식 없음 · 직전 작업중」을 봤다. 원인은
둘이다 — (a) 한도 오류로 끝난 턴에 `Stop` 이 없어 `turn_state` 가 running 에 남았고, (b) 15:38:07
에 한도 오류로 죽은 검수 에이전트 `aad2ad69` 가 `SubagentStop` 을 남기지 않아 ZG 가드(90분)가
놓아줄 때까지 S(실행 중 서브에이전트)로 남았다. **명부가 idle 이어도 working 이다**(LS5 idle 행의
S 항) — 턴만 닫아서는 이 사례가 고쳐지지 않는다(→ 결정 RI3·RI11 의 근거).

### 1.2 훅 쪽 신호

- 이벤트 보존 창(09-16~09-23) 안의 메인 스레드 API 오류 **고유 10건(4세션)** — 오류 뒤 다음
  `UserPromptSubmit` 전까지 `Stop` **0/10**. 오류로 끝난 서브에이전트 실행 **7건** — 그 실행의
  `SubagentStop` **0/7**.
- 호스트 코드 판독(데스크톱 번들 2.1.280, 난독화 이름): 쿼리 루프가 마지막 메시지가
  `isApiErrorMessage` 면 `return fRe(B,M),{reason:"api_error",errorKind:B.error,isTransient:…,quotaLimits:B.quotaLimits}`
  로 **Stop 훅 실행(`mc(...)`) 앞에서 빠져나간다** — 위 0/10 의 기전이다. `fRe` 는 await 되지 않는다.
- `fRe` 의 첫 줄 `if(ps(n.agentContext)||settingsHooksOff)return` 의 `ps` 는
  `e?.agentType==="subagent"&&e.delegatedObservation===!0` 이다 — **"서브에이전트 문맥이면 발화하지
  않는다"가 아니라 "위임 관찰용 서브에이전트만 건너뛴다"**. Stop/SubagentStop 발송 함수(`Fte`)도
  같은 가드를 쓰는데 일반 서브에이전트의 `SubagentStop` 은 실제로 오므로, `StopFailure` 도 일반
  서브에이전트에서 발화하고 공통 필드 조립(`jl`)이 `agent_id`·`agent_type` 를 싣는다고 본다
  (**코드 판독 — 실발화 미관측**, §1.5).
- 입력: 공통 필드 + `hook_event_name:"StopFailure"`, `error`(= 그 오류 메시지의 `error` 필드,
  없으면 `"unknown"`), `error_details?`, `last_assistant_message?`. matcher 대상은 `error`.

### 1.3 transcript 쪽 신호

`~/.claude/projects/**/*.jsonl` 전수에서 `isApiErrorMessage:true` 줄 **194개**(95파일, 사본 포함)를
구조 필드로 집계했다.

| 위치 | rate_limit | server_error | invalid_request | authentication_failed |
|---|---|---|---|---|
| 메인 transcript(120줄) | 117 | 0 | 0 | 3 |
| 서브에이전트 transcript(74줄) | 62 | 10 | 2 | 0 |

- 194/194 줄에 `type:"assistant"`·`error`(문자열)·`isApiErrorMessage:true`, `message.model:"<synthetic>"`.
  `apiErrorStatus` 는 rate_limit 에서 179/179 가 429.
- **`quotaLimits` 가 있다** — rate_limit 줄 중 2.1.237 이상 **153/153**(`rateLimitType:"five_hour"`
  153, `status:"rejected"` 153, `resetsAt` 초 단위 153), 2.1.219~2.1.229 **0/26**. 사례의
  `resetsAt:1790148600` = 16:30 KST 로 본문 문구("resets 4:30pm")와 일치한다. 모델별 한도
  ("You've reached your Fable 5 limit")는 구버전 1줄뿐이라 그 `rateLimitType` 은 모른다.
- 오류 줄 뒤 **다음 대화 줄은 항상 `user`**(132/132) — 오류 뒤에 같은 턴이 이어지는 경우는 없다.
  대화 줄이 더 없으면(62) 뒤에 붙는 것은 비대화 줄뿐이고(`queue-operation`·`last-prompt`·
  `custom-title`·`agent-name`·`mode`·`atis-latch`·`bridge-session`·`relocated`·`worktree-state`)
  그 합계가 최대 **493B** — 기존 128KiB 꼬리 읽기로 항상 닿는다.
- 시각 순서(사례 4/4): `user` 줄 timestamp < `UserPromptSubmit` 훅 `t` < 오류 줄 timestamp.
  예) 15:38:33.257 < 15:38:33.378 < 15:38:33.931. 오류는 프롬프트 훅이 끝난 뒤의 API 호출에서
  나오므로 "오류 시각 ≥ 마지막 프롬프트 시각"은 인과적으로 성립한다(→ RI4 의 가드).

### 1.4 명부(`~/.claude/sessions/<pid>.json` 의 `status`) 쪽

- 호스트 코드: SDK(데스크톱) 경로는 `{running:"busy",requires_action:"waiting",idle:"idle"}` 매핑이며
  `idle` 은 "heldBackResult 가 비고 백그라운드 에이전트 루프가 끝난 뒤" 온다. TUI 경로는
  `isLoading||delegatedActive ? "busy" : "idle"`, 대화상자가 있으면 `"waiting"`. 즉 한도 턴이
  끝나면 백그라운드 작업이 없는 한 `idle` 이 될 것이다 — 그래도 §1.1 처럼 좀비 S 가 working 을
  만든다. (`waiting` 은 현재 파서가 미지값 → `listed` 로 접는다. 이 설계의 범위 밖이다.)

### 1.5 측정하지 못한 것

1. `StopFailure` 의 **실발화** — 메인 스레드는 V1 로 **확인됨**(§8.2 결과). 일반 서브에이전트
   문맥의 발화(RI11)는 여전히 코드 판독뿐이다.
2. 오류 뒤 사용자가 로컬 슬래시 명령(`/usage`·`/model` 등)만 쳤을 때 transcript 줄 모양.
3. `rateLimitType` 의 `five_hour` 외 값(주간·모델별).
4. 사례 당시의 명부 `status` 값.

---

## 2. 비목표

| # | 하지 않는 것 | 이유 |
|---|---|---|
| N1 | 설정 스위치 신설 | LS12 와 같은 판단 — 고장 대비는 구조(두 관측 중 하나만 있어도 동작, 둘 다 없으면 오늘과 동일)가 맡는다 |
| N2 | 계정 전체 "한도 초과" 배너 | 사용량 패널이 이미 창별 사용률·초기화 시각을 보인다 |
| N3 | 한도 외 API 오류의 별도 라벨(「오류로 중단」) | 메인 스레드 실측 3건(인증 실패)뿐 — RI6, 쟁점 4 |
| N4 | 서브에이전트 transcript 판독 | 프라이버시 고지(「대화 기록은 읽지 않는다」) 유지 |
| N5 | 자동 재개·알림 | 허브는 읽기 전용 표시 도구다 |
| N6 | `rate_limits.json`·사용량 패널 변경 | RI5 |
| N7 | 기존 설치의 훅 자동 이행 | RI12 |

> **개정됨(2026-10-07, [`hub-live-activity.md`](./hub-live-activity.md) 결정 LA1·LA6) — N4 옆.** N4(서브에이전트 transcript 판독 안 함)는 부분적으로 뒤집혔다 — 도는 실행의 기록 끝 1MiB 를 수집 때마다 읽어 도구 종류·시각·개수만 표시한다(내용은 싣지 않는다). 이 표의 원문은 작성 시점의 결정 기록이다.

---

## 3. 영향 범위

| 파일 | 조치 | 규모(추정) |
|---|---|---|
| `hub/bin/hub_transcript.py` | `TranscriptTurnFailure`·`normalize_error_kind` 신설, `parse_session_tail` 역방향 스캔에 「마지막 메인 대화 줄」 판독 추가, `SessionTail.turn_failure` | +60 (182→~240) |
| `hub/bin/hub_session.py` | `SessionState` 5값, `HookEvent.error_kind`, `FailedTurn`, `SessionFacts.failed_turn`, `SessionInterruption`, `SessionView.interruption`, StopFailure 접기, `effective_interruption`·`_display_state`, `compute_session_view` 인자 1 | +100 (650→~750) |
| `hub/bin/hub_hook.py` | StopFailure 전용 `er` 투영 | +8 |
| `hub/bin/hub_settings.py` | `HOOK_EVENTS` 에 `"StopFailure"`, docstring 「6개」 5곳 | ~6 |
| `hub/bin/hub_project.py` | `PROJECT_STATE_PRIORITY` 5값, `tail.turn_failure` 전달 | +3 |
| `hub/bin/hub.py` | `cmd_install_hooks` docstring 「6개」 | 1 |
| `hub/bin/hub_template.html` | `STATE_LABEL`·`STATE_GLYPH` 키, CSS 1규칙, 라벨 접미·툴팁 순수 함수 2개, `renderStateBadge` 인자 1, `SESSION_STATE_ORDER` | +35 |
| `hub/README.md` | 훅 6→7(4곳), 프라이버시 고지 2항, 화면 배치 3항(정렬 순서·좀비 가드 문장·툴팁 목록) | ~+15 |
| `commands/hub.md` | 6→7(3곳), 설치 고지 ① 1문장, `/hub status` 이행 안내 1문장, 구현 노트 1줄 | ~+6 |
| `docs/prps/hub-dashboard.md` | 「상태 판정 규칙」 개정 블록, §4 우선순위, 훅 목록·이벤트 스키마 개정 한 줄씩 | +16 |
| `tests/hub/test_hub_session.py` | 접기 표 F1~F8 · 사다리 표 I1~I13 | +220 |
| `tests/hub/test_hub_transcript.py` | 꼬리 판독 표 T1~T12 | +120 |
| `tests/hub/test_hub_hook.py` | 투영·프라이버시 H1~H4 | +50 |
| `tests/hub/test_hub_settings.py` | 7개·이행 S1~S3 | +30 |
| `tests/hub/test_hub_project.py` | 우선순위·배선 P1~P2 | +40 |
| `tests/hub/test_hub_collect.py` | 종단 배선 W1 | +40 |
| `tests/run.sh` | T25-150 갱신(마지막 필드 · `time\.` 정규식, GOTCHA 1), RI-G1~G4 신설, `SOURCE_GUARD_ID_FLOOR` | +60 |
| `tests/mutations.tsv` | 신설 가드 변조행 4 + T25-150 행 점검 | +5 |

**건드리지 않는 것**: `hub_collect.py`(꼬리는 이미 읽고 `SessionTail` 이 새 필드를 실어 나른다 —
`record_prompt_excerpt:false` 의 `dataclasses.replace(tail, last_prompt=None)` 도 `turn_failure` 를
보존한다) · `hub_model.py`(스냅샷 계약 불변 — `asdict` 가 중첩 필드를 싣는다) · `hub_server.py` ·
`hub_daemon.py` · `hub_live_session*.py` · `hub_subagent*.py` · `hub_usage*.py` · `hub_config.py` ·
`hub/install.sh`(배포 파일 수 26 불변 — T25-104·T25-149 무영향). 상시 컨텍스트(`CLAUDE.md`·`rules/`)
변경 0 — T26 무영향.

---

## 4. 필독 파일 (구현 전)

| 우선 | 파일 | 무엇을 |
|---|---|---|
| P0 | `hub/bin/hub_session.py` | `_apply_tracked_event`·`_compute_base_state`(LS5 표)·`compute_session_view`·`SessionView` 의 D2 주석 |
| P0 | `hub/bin/hub_transcript.py` | `parse_session_tail` 의 역방향 스캔·조기 종료 조건 |
| P0 | `hub/bin/hub_hook.py` | `_project_fields` — 투영 허용 목록 |
| P1 | `docs/prps/hub-live-session-native-source.md` LS4·LS5·LS9 | 판정 입력 확장의 선례와 stale 의 역할 |
| P1 | `docs/prps/hub-zombie-subagent-guard.md` ZG4 | 이번에 개정하는 "상태와 칩은 어긋날 수 없다" |
| P1 | `docs/prps/hub-dashboard.md` 「상태 판정 규칙」 | 개정 블록을 붙일 정본 |
| P2 | `tests/run.sh` T25-150·T25-190·T25-219 | 이번 변경이 닿는 기존 가드 |
| P2 | `tests/mutations.tsv` 머리(8열 규약) | 신설 가드 변조행 형식 |

---

## 5. 설계 결정

### RI1. 신호원 — 훅 `StopFailure`(사실) + transcript 꼬리(보강·폴백), 역할을 나눠 둘 다 쓴다

| 관점 | (a) `StopFailure` 훅(7번째) | (b) transcript 꼬리의 오류 줄 |
|---|---|---|
| 기존 설치 이행 | `/hub install` 1회 재실행(멱등 — StopFailure 만 추가됨) | 불필요 |
| 서버 꺼짐(file 모드) | 오류 순간 훅이 발화 → 폴백 수집 spawn → `hub.html` 즉시 갱신 | 오류 순간 발화하는 훅이 없어 `hub.html` 이 다음 훅까지 그대로다 — 그 다음 훅이 대개 해제 신호(`UserPromptSubmit`)라 **사실상 한 번도 안 보인다** |
| 과거 세션 소급 | 불가(설치 이후 오류만) | 가능 — 지금 막힌 세션이 배포 후 첫 수집에 보인다 |
| 서브에이전트 한도 오류 | `agent_id` 와 함께 발화(코드 판독) → 좀비 실행을 닫는다 | 불가 — 서브에이전트 transcript 는 읽지 않는다 |
| 초기화 시각 | 없음(입력에 없다) | `quotaLimits.resetsAt`(2.1.237+ 153/153) |
| 한도 외 오류의 턴 종료 | 모든 종류에서 턴을 닫는다 | 쓰지 않는다(RI6) |
| 호스트 형식 의존 | 공개 훅 계약(호스트가 스키마를 기술) | 비공개 형식 — 단 모델·effort·last-prompt 로 이미 의존 중이고 같은 모듈에 가둔다(MD1·PS1) |
| 실측 근거 | 코드 판독뿐 | 194줄 전수 |

**결정: 둘 다 쓴다.** 역할 —

- **훅 `StopFailure` = 사실.** `SessionFacts` 는 여전히 100% 훅 유래다(LS4 1항 유지).
- **transcript = 표시 보강(초기화 시각) + 폴백 검출**(미이행 설치·훅 유실·소급).
- **번복 범위(LS4 2항)**: 「표시 상태 판정은 훅 사실 + 호스트 명부 **+ transcript 의 마지막 턴
  결과** 3입력이다. 셋째 입력은 `interrupted` 여부와 초기화 시각에만 쓰이고 working/idle/done
  사다리(`_compute_base_state`)에는 닿지 않는다.」

한쪽만 쓰지 않는 이유: **(a)만** — 실발화를 관측하지 못한 신호를 유일한 근거로 삼으면
`hub-dashboard.md` 가 `needs_input` 을 기각한 이유("영원히 켜지지 않는 등불")와 같은 위험을
지고, 초기화 시각도 없다. **(b)만** — file 모드에서 사실상 보이지 않고, 서브에이전트 좀비를
닫지 못하며, 한도 외 API 오류의 「작업중」 고착은 그대로다.

### RI2. 상태 모델 — `SessionState` 에 `"interrupted"`, stale 보다 앞선 오버레이

```
state = "done"         if base_state == "done"
        "interrupted"  elif interruption is not None and roster != "not_listed"
        "stale"        elif is_stale                       # 계산식은 오늘 그대로(LS9·SL4)
        base_state     otherwise
```

- **이름은 소문자 a-z 만** — T25-219 가 서버·클라이언트 두 순서를 `"[a-z]+"`·`'[a-z]+'` 로 뽑는다.
  `rate_limited` 같은 밑줄 이름은 양쪽에서 조용히 빠져 대조가 공허 통과한다(GOTCHA 3). CSS
  클래스(`state-interrupted`)의 kebab 규칙과도 맞는다. 라벨이 「한도 초과」로 좁은 것은 RI6 이다.
- `base_state` 는 3값 그대로다 — 클라이언트가 `base_state` 를 읽는 곳은 stale 라벨뿐이고
  interrupted 는 stale 로 덮이지 않는다.
- 기각: (i) 별도 필드만 두고 배지는 그대로 — 사용자가 본 「작업중」을 고치지 못한다. (ii) stale
  **아래** 오버레이 — 30분 뒤 「소식 없음」이 덮는다(사례: 16:08, 초기화 16:30 보다 앞이다).
  (iii) `base_state` 의 값 — `base_state` 는 훅+명부 판정이고 이것은 턴 결과라 층이 다르다.

### RI3. `interrupted` 는 `working` 을 이긴다(S·명부 busy 포함)

- 근거 1: §1.1 — 명부가 idle 이어도 한도로 죽은 서브에이전트(좀비)가 S 로 working 을 붙잡는다.
- 근거 2: 관측된 한도는 전부 계정 단위(`five_hour`·`rejected` 153/153) — 그 창 안에서는 어떤
  서브에이전트도 새 API 호출을 못 한다.
- 근거 3: 서브에이전트 종료 신호(RI11)는 미실측이고, transcript 경로는 서브에이전트를 못 본다.
- **대가**: 배지는 「한도 초과」인데 서브에이전트 칩이 「진행 중」인 조합이 생길 수 있다(모델별
  한도에서 다른 모델의 서브에이전트가 실제로 도는 경우, 또는 RI11 이 발화하지 않은 좀비).
  결정 ZG4 의 「상태와 칩은 어긋날 수 없다」를 개정한다 — **「working 배지 ⇔ (턴 진행 ∨ 실행 중
  칩)은 interrupted 가 아닐 때만 성립한다. interrupted 는 '메인 턴이 멈췄다'는 사실이고 칩은
  '서브에이전트가 도는가'라는 다른 질문이라 함께 보일 수 있다.」** `hub/README.md` 「화면 배치」의
  같은 문장(「카드는 대기인데 칩만 ● 로 남는 모순은 생기지 않는다」)도 함께 고친다.

### RI4. 해제·유지 조건

| 이벤트·관측 | 훅 사실(`FailedTurn`) | transcript 사실 | 표시 |
|---|---|---|---|
| `UserPromptSubmit`(작업 알림 배달 포함) | **지운다** | 가드 `failed_at_ms ≥ last_prompt_at_ms` 가 무효화 | 오늘의 판정 |
| `Stop` | 지운다 | 뒤이은 assistant 줄이 무효화 | 오늘의 판정 |
| 메인 `StopFailure` | 최신 종류·시각으로 갱신 | 새 오류 줄 | 재판정 |
| `SessionStart`(resume 등) | **유지** | 유지(resume 은 user 줄을 쓰지 않는다) | interrupted 유지 |
| `SessionEnd` | 유지 | 유지 | 명부가 살아 있지 않으면 `done` 이 이긴다 |
| 명부 `not_listed` | — | — | **취소**(프로세스가 없다 — LS6 의 정신) |
| 초기화 시각 경과 | 유지 | 유지 | 라벨만 「초기화됨」(클라이언트) |
| `SubagentStart`/`Stop` | 유지 | 유지 | 유지 |

`SessionStart` 로 지우지 않는 이유: resume 은 transcript 에 user 줄을 쓰지 않아 두 관측이 어긋나고,
대화의 마지막 턴이 끊긴 채라는 것은 사실이다. 사용자가 지시하면(`UserPromptSubmit`) 풀린다.

### RI5. 초기화 시각 — transcript `quotaLimits.resetsAt` 만

- 검증: 엄격 int(bool 배제) → 초×1000 → `failed_at_ms < resets_at_ms ≤ failed_at_ms + 8일`
  (`hub_usage.RATE_LIMIT_MAX_HORIZON_MS` 와 같은 근거 — 단위 혼동·과거 값 차단). 실패하면 시각만
  None 이고 상태는 유지한다.
- `rate_limits.json` 재사용 기각 — 계정 창의 투영이라 **어느 창이 막았는지 모르고**, statusLine
  미설치·폴링 off 면 없으며, 사용량 패널이 이미 같은 값을 보인다.
- 오류 문구 파싱 기각 — 호스트 자유 텍스트("resets 4:30pm (Asia/Seoul)")는 로캘·문구 변경에 무방비.
- 한도 종류(`rateLimitType`)는 싣지 않는다(YAGNI — 2.1.237 이후 `five_hour` 외 관측 0).
  모델별 한도도 `resetsAt` 가 오면 같은 방식이다.
- 「초기화됨」 판정은 **클라이언트**가 30초 틱에 한다. 사용량 패널(`drop_passed_resets`)은 지난
  시각을 버리지만 여기서는 「초기화됨」을 그려야 하므로 버리지 않는다.

### RI6. 범위 — `rate_limit` 만 `interrupted`

- `INTERRUPTING_ERROR_KINDS = frozenset({"rate_limit"})`. 다른 종류의 메인 `StopFailure` 는 턴을
  닫기만 한다(→ 대기). 이것은 "Stop 대신 오는 훅"을 Stop 과 같게 접는 것이라 범위 확장이 아니라
  같은 결함(턴 고착)의 수정이다.
- 확장 비용은 집합 1원소 + 라벨 1개(쟁점 4).

### RI7. 프라이버시 — 닫힌 값만 남긴다

- **훅**: `StopFailure` 일 때만 이벤트 로그에 `er` 1키. 값은 `normalize_error_kind` —
  `\A[a-z_]{1,32}\Z` 를 통과한 문자열, 아니면 `"unknown"`. 호스트 enum 의 복사본을 두지 않는다
  (형태 검사만으로 자유 텍스트가 새지 않고, 호스트가 종류를 늘려도 유지 비용 0).
  `error_details`·`last_assistant_message` 는 **기록하지 않는다** — 범용 `optional_keys` 에 `error`
  를 넣지 않고 이벤트 이름으로 분기한다(다른 훅에 같은 이름의 자유 텍스트 필드가 생겨도 새지
  않게, GOTCHA 8).
- **transcript**: 읽는 필드는 `type`·`isSidechain`·`isMeta`·`isApiErrorMessage`·`error`·`timestamp`·
  `quotaLimits.resetsAt` 뿐. `message.content`(오류 문구 포함)는 읽지 않는다.
- **`hub.html` 에 새로 인라인되는 값**: 정수 2개(`interrupted_at_ms`·`resets_at_ms`). 종류 문자열도
  싣지 않는다.
- 고지 갱신: README 「프라이버시 고지」 transcript 항에 판독 필드를 더하고, 「훅 옵트인」에
  "StopFailure 입력의 오류 설명·마지막 응답 문구는 기록하지 않고 오류 종류 하나만 남긴다"를
  더한다. `commands/hub.md` 설치 고지 ①에 같은 한 문장 + 7개.

### RI8. 뷰 계약

- `SessionView.interruption: SessionInterruption | None = None` 을 **맨 뒤**에 둔다 — T25-150 의
  마지막 필드 고정 검사를 `interruption` 으로 갱신한다(model→workflow→tier1_is_finished_task 선례).
- 불변식: `interruption is not None ⇔ state == "interrupted"`(`compute_session_view` 가 강제, 테스트 I12).
- 정적 값만(D2 — `snapshot_content_key` 안정). "지났는가"는 싣지 않는다.
- `ProjectView` 필드 불변(`state` 의 값 범위만 는다).

### RI9. 프로젝트·정렬·숨김·glow

- `PROJECT_STATE_PRIORITY = ("working", "interrupted", "idle", "stale", "done")`, 템플릿
  `SESSION_STATE_ORDER` 같은 순서(T25-219 가 대조). working 이 앞인 이유 — 살아 있다는 증거가 가장
  강한 신호이고 SO1(진행 중 세션이 맨 위)의 원칙이다. idle 보다 앞인 이유 — 사용자의 판단이
  필요한 상태다.
- glow(`card-working`)는 working 전용 그대로(결정 D2 — "지금 돈다"로 오해되면 안 된다).
- 12시간 숨김은 stale 전용 그대로 — interrupted 는 숨기지 않는다(이어서 지시할 대상이다).
- `LIVE_SESSION_STATES({"working"})` 불변 — interrupted 세션은 GN2 의 "지금 일하는 세션"이 아니다.
- **stale 면제의 상한**: LS9 가 stale 을 "명부 오판의 독립 상한"이라 한 것은 working 에 대한
  말이다. interrupted 는 명부 `not_listed` 가 취소하고, SessionEnd 는 done 으로 넘긴다. 명부가
  unknown(열거 실패)인 채 프로세스가 크래시한 경우에만 이벤트 창(오늘+어제, 최대 약 48시간)이
  상한이 된다 — 이 상한을 명시적으로 수용한다(R6).

### RI10. 표시 — 배지 상태 1개 추가(채움 amber)

§7 이 정본이다. 새 색 토큰 0, 새 CSS 규칙 1, 애니메이션 0(T25-190 의 정신).

### RI11. 서브에이전트 `StopFailure` — 이미 아는 실행만 닫는다

- `agent_id` 가 있으면: 그 실행이 `SubagentStart` 로 알려져 있고 미종료면 `ended_at_ms = t`.
  모르면 무시한다(유령 실행 방지 — `is_untracked_internal_subagent_stop` 과 같은 정신). 메인
  턴(`turn_state`·`failed_turn`)은 건드리지 않는다.
- 같은 `agent_id` 가 나중에 다시 `SubagentStart` 로 재개되면(실측: 한도 뒤 SendMessage 재개 2건)
  기존 `_handle_subagent_start` 가 실행을 새로 연다 — 추가 규칙 없음.
- 실발화하지 않아도 배지는 RI3 이 지키고, 칩만 ZG 가드(90분)가 상한이다.

### RI12. 이행 — 수동, 한 번

- `HOOK_EVENTS` 끝에 `"StopFailure"`(기존 순서 보존). `merge_hub_hooks` 가 이벤트별로 멱등이라
  기존 설치에서 `/hub install` 을 다시 부르면 `installed == ["StopFailure"]` 만 나온다.
- 자동 이행은 만들지 않는다(`HOOK_TIMEOUT_SECONDS` 주석의 선례 — 남의 엔트리를 읽지 않는다는
  선언과 가까이 붙는 작업이다). 대신 `commands/hub.md` 「/hub status」에 "`hooks_installed` 에
  false 가 있으면 표 앞 한 줄로 `/hub install` 재실행을 안내한다"를 더한다.
- 이행 전에도 서버 모드에서는 transcript 경로가 동작한다(RI1).

### RI13. 모듈 배치 — 새 모듈 없음

| 무엇 | 어디 | 근거 |
|---|---|---|
| transcript 오류 줄 판독·`TranscriptTurnFailure` | `hub_transcript.py` | 같은 128KiB 꼬리의 다른 줄이다(PS1 판단 기준 "같은 외부 계약인가") |
| `normalize_error_kind` | `hub_transcript.py` | 훅의 `error` 와 transcript 의 `error` 는 호스트의 **같은 어휘**다(판독: `g=e.error??"unknown"`). `hub_session`·`hub_hook` 이 모두 임포트할 수 있는 유일한 무순환 위치 |
| StopFailure 접기·표시 사다리 | `hub_session.py` | LS2 — 상태 판정 사다리는 한 파일에 있어야 한다 |
| 우선순위 | `hub_project.py` | 기존 자리 |

- 새 임포트 간선: `hub_hook` → `hub_session`·`hub_transcript`(둘 다 ★순수이고 `hub_collect` 경유로
  이미 로드된다). `hub_transcript` 는 표준 `re`·`datetime` 만 더한다 — 초기화 지평선 상수는
  `hub_usage` 를 임포트하지 않고 같은 근거의 지역 상수로 둔다(작은 사본 선례: `_clip_to_length`).
  T25-102(임포트 방향)가 `hub_hook` 의 임포트를 열거한다면 함께 갱신한다.
- `hub_session.py` 는 ~750/800줄이 된다 — 다음 확장 때 분리가 필요하다는 에스컬레이션 조건을
  모듈 머리 주석에 남긴다(R4).

---

## 6. 데이터 모델과 인터페이스

### 6.1 `hub/bin/hub_transcript.py` (★순수)

```python
ERROR_KIND_PATTERN = re.compile(r"\A[a-z_]{1,32}\Z")   # 호스트 API 오류 종류 어휘의 형태(RI7)
UNKNOWN_ERROR_KIND = "unknown"
# 8일 = 가장 긴 한도 창(7일) + 하루 — hub_usage.RATE_LIMIT_MAX_HORIZON_MS 와 같은 근거의 지역 사본
TURN_FAILURE_RESET_MAX_HORIZON_MS = 8 * 24 * 60 * 60 * 1000

@dataclass(frozen=True)
class TranscriptTurnFailure:
    """transcript 의 마지막 메인 대화 줄이 API 오류 줄일 때의 구조 필드(결정 RI1·RI5·RI7).
    message.content 는 읽지 않는다."""
    error_kind: str            # normalize_error_kind 통과값
    failed_at_ms: int          # 그 줄의 timestamp(ISO 8601, UTC "Z") → epoch ms
    resets_at_ms: int | None   # quotaLimits.resetsAt(초) → ms. 부재·검증 실패면 None

@dataclass(frozen=True)
class SessionTail:
    model: SessionModel | None
    last_prompt: str | None
    turn_failure: TranscriptTurnFailure | None = None   # RI1. 기본값 — 기존 생성 지점 무해

def normalize_error_kind(value: object) -> str:
    """호스트 API 오류 종류(StopFailure 훅의 error · transcript 줄의 error)를 닫힌 형태로 만든다.
    문자열이 아니거나 ERROR_KIND_PATTERN 을 벗어나면 "unknown"."""

def parse_session_tail(tail_text: str) -> SessionTail:
    """(개정) 한 번의 역방향 스캔으로 모델·effort, last-prompt, **마지막 메인 대화 줄**을 판다.
    대화 줄 = type ∈ {user, assistant} 이고 isSidechain·isMeta 가 True 가 아닌 줄. 그 줄이
    isApiErrorMessage 인 assistant 줄이면 turn_failure 를 채운다(timestamp 가 깨졌으면 None)."""
```

- 오류 줄은 `message.model == "<synthetic>"` 이라 모델 추출은 이미 그 줄을 건너뛴다(E11) —
  대화 줄 판독은 모델 추출과 독립이다(GOTCHA 5).
- 마지막 대화 줄은 모델을 주는 줄과 같거나 그보다 뒤에 있으므로 조기 종료 조건에
  `conversation_checked` 를 더해도 스캔 비용이 늘지 않는다(GOTCHA 4). 본문을 50줄 안에 두려고
  `_turn_failure_from_line(payload) -> TranscriptTurnFailure | None` 을 뽑는다.

### 6.2 `hub/bin/hub_session.py` (★순수)

```python
SessionState = Literal["working", "idle", "stale", "done", "interrupted"]
STOP_FAILURE_EVENT_NAME = "StopFailure"
INTERRUPTING_ERROR_KINDS: frozenset[str] = frozenset({"rate_limit"})     # RI6

@dataclass(frozen=True)
class HookEvent:
    ...                                   # 기존 8필드
    error_kind: str | None = None         # 이벤트 로그 "er" — StopFailure 에만 있다(RI7)

@dataclass(frozen=True)
class FailedTurn:
    """메인 턴이 API 오류로 끝났다는 훅 사실(StopFailure, agent_id 없음, RI1·RI4)."""
    error_kind: str
    failed_at_ms: int

# SessionFacts 맨 뒤: failed_turn: FailedTurn | None = None   (last_prompt_at_ms 선례)

@dataclass(frozen=True)
class SessionInterruption:
    """「한도 초과」 표시의 근거(RI8). 정적 값만 — 초기화 경과 판정은 클라이언트 몫."""
    interrupted_at_ms: int          # transcript 오류 줄 시각, 없으면 StopFailure 훅 시각
    resets_at_ms: int | None        # transcript quotaLimits.resetsAt. 없으면 None

# SessionView 맨 뒤: interruption: SessionInterruption | None = None   (T25-150 갱신)

def effective_interruption(
    facts: SessionFacts, transcript_turn_failure: TranscriptTurnFailure | None
) -> SessionInterruption | None:
    """메인 턴이 한도 오류로 끝났고 그 뒤 새 프롬프트가 없는가 — 두 관측의 OR(RI1·RI4·RI6)."""

def compute_session_view(..., live_roster=None,
                         transcript_turn_failure: TranscriptTurnFailure | None = None) -> SessionView:
```

`effective_interruption` 의 정본 규칙:

```
hook = facts.failed_turn        (error_kind ∈ INTERRUPTING_ERROR_KINDS 일 때만)
tail = transcript_turn_failure  (error_kind ∈ INTERRUPTING_ERROR_KINDS 이고
                                 last_prompt_at_ms is None 또는 failed_at_ms ≥ last_prompt_at_ms 일 때만)
둘 다 없으면 None
interrupted_at_ms = (tail 이 있으면 tail, 없으면 hook).failed_at_ms     # 결정적 — 스냅샷 키 안정
resets_at_ms      = tail.resets_at_ms if tail else None
```

`_apply_tracked_event` 변경: `UserPromptSubmit`·`Stop` 분기에 `failed_turn = None` 한 줄씩,
`StopFailure` 분기 → `_handle_stop_failure(session, event)`(RI11 의 `agent_id` 분기 / 메인이면
`turn_state="ended"`·`failed_turn=FailedTurn(event.error_kind or UNKNOWN_ERROR_KIND, t)`).
표시 사다리는 `_display_state(base_state, interruption, roster, is_stale) -> SessionState` 로 뽑아
`compute_session_view` 를 짧게 둔다. `parse_event_line` 은 `"er"` 를 `normalize_error_kind` 로 다시
거른다(방어 재검증 — 이벤트 로그는 우리 파일이지만 옛 줄·찢긴 줄이 섞인다).

### 6.3 `hub/bin/hub_hook.py`

```python
if payload.get("hook_event_name") == hub_session.STOP_FAILURE_EVENT_NAME:
    fields["er"] = hub_transcript.normalize_error_kind(payload.get("error"))
```

이벤트 줄 예: `{"t":…,"e":"StopFailure","s":…,"c":…,"er":"rate_limit"}`(서브에이전트면 `ai`·`at` 동반).

### 6.4 `hub/bin/hub_settings.py` · `hub/bin/hub_project.py`

- `HOOK_EVENTS = (…6개…, "StopFailure")`.
- `PROJECT_STATE_PRIORITY` 5값(RI9) · `_session_views_for_path` 가
  `transcript_turn_failure=tail.turn_failure if tail else None` 을 넘긴다(판단 0, 배선만).

### 6.5 GOTCHA

1. **T25-150 의 역검사 `grep -qE 'open\(|Path\(|time\.|os\.' hub_transcript.py` 는 `datetime.` 에도
   걸린다**("date**time.**fromisoformat"). 가드 의도는 `time` 모듈이므로 정규식을
   `(^|[^A-Za-z_])time\.` 로 고치고 원장의 T25-150 행이 여전히 무는지 확인한다(별칭 임포트로 피하는
   것은 가드 회피라 쓰지 않는다). `hub_usage.py` 가 이미 ★순수 모듈에서 `datetime` 을 쓴다.
2. 템플릿 `STATE_LABEL`·`STATE_GLYPH` 에 키가 없는 상태는 배지에 `undefined` 로 그려진다 — 파이썬만
   먼저 착지할 수 없다(§10).
3. 상태 이름은 a-z 만(RI2 — T25-219 추출 정규식).
4. `parse_session_tail` 의 조기 종료 조건에 대화 줄 판독 완료를 명시적으로 넣는다.
5. 대화 줄 판독은 `<synthetic>` 모델 건너뛰기와 독립이어야 한다.
6. `read_session_tails` 의 `record_prompt_excerpt:false` 치환은 `last_prompt` 만 지운다 — `turn_failure`
   는 프롬프트 콘텐츠가 아니다(PS7·SL7 과 같은 분류).
7. `SessionView` 새 필드는 반드시 맨 뒤 + T25-150 갱신을 한 커밋에.
8. `er` 는 범용 `optional_keys` 루프에 넣지 않는다(RI7).

---

## 7. 표시 사양 (`hub_template.html`)

| 항목 | 값 |
|---|---|
| `STATE_LABEL.interrupted` | `'한도 초과'` |
| `STATE_GLYPH.interrupted` | `'■'` — ●○▲✓ 와 같은 기하 도형 계열. `⏸` 는 플랫폼에 따라 이모지로 그려져 기각 |
| CSS | `.badge.state-interrupted{background:var(--attention);color:var(--surface)}` — 대비 라이트 5.02:1·다크 7.3:1(계산). `--bg` 글자는 라이트 4.50:1 로 AA 경계라 쓰지 않는다. 채움 = "지금의 상태"(working 과 같은 문법), 점선 amber(stale)와 형태로 갈린다 |
| 세션 배지(안 A) | `'한도 초과'` + 초기화 시각이 미래면 `' · 초기화 ' + absoluteTimeLabel(resets)`, 지났으면 `' · 초기화됨'`, 없으면 접미 없음. 어순은 사용량 패널 `usageResetText`(「초기화 18:32 · …」)와 같다 — `USAGE_RESET_LABEL` 재사용 |
| 프로젝트 배지 | `'한도 초과'`만(카드 머리는 nowrap) |
| 세션 툴팁 | `'사용 한도에 걸려 {HH:MM} 에 턴이 멈췄습니다. '` + (미래: `'초기화 {HH:MM} · {남은 시간} — 그 뒤 이 세션에 이어서 지시하면 계속됩니다.'` / 지남: `'한도가 초기화됐습니다 — 이 세션에 이어서 지시하면 계속됩니다.'` / 없음: `'초기화 시각이 기록되지 않았습니다.'`). `absoluteTimeLabel`·`remainingLabel` 재사용 |
| 프로젝트 툴팁 | `'사용 한도에 걸려 멈춘 세션이 있습니다.'` |
| 시그니처 | `renderStateBadge(state, baseState, lastActivityAtMs, interruption)` · `stateLabel(state, baseState, interruption, nowMs)` · 신설 순수 함수 `interruptedLabelSuffix(interruption, nowMs)` · `interruptedBadgeTooltipText(interruption, nowMs)` |
| 호출부 | `renderSession` 의 배지 호출에 `session.interruption` 인자 1개. `renderProject` 호출 불변 |
| 정렬 | `SESSION_STATE_ORDER = ['working','interrupted','idle','stale','done']` |
| 전환 | 30초 틱이 다시 그리므로 「초기화됨」 전환에 추가 코드가 없다 |

**안 B**(대안): 세션 배지도 `'한도 초과'`만 두고 초기화 시각은 툴팁에만 — 라벨 로직이 없어지는
대신 hover 해야 시각이 보인다(쟁점 3). 목업의 장면 1~5 가 현재 | 안 A | 안 B 를 나란히 둔다
(장면 4: 다크·320px·세션 4개·선택 카드·행 hover·툴팁, 장면 5: 최장 라벨 「초기화 9/27 09:00」).

---

## 8. 테스트 계획

### 8.1 단위(`tests/hub`, stdlib unittest, AAA)

**접기 — `test_hub_session.py::StopFailureFoldingTest`**

| # | 입력 | 기대 | 잡는 변조 |
|---|---|---|---|
| F1 | UPS → StopFailure(er=rate_limit) | `turn_state=="ended"`, `failed_turn==("rate_limit", t)` | StopFailure 분기 삭제 |
| F2 | … → UPS | `failed_turn is None`, running | UPS 해제 줄 삭제 |
| F3 | … → Stop | `failed_turn is None` | Stop 해제 삭제 |
| F4 | … → SessionStart(resume) | `failed_turn` 유지 | SessionStart 에 해제 추가 |
| F5 | SubagentStart(a1) → StopFailure(ai=a1) | a1 `ended_at_ms==t`, 메인 턴·`failed_turn` 불변 | agent_id 분기를 메인 분기와 합침 |
| F6 | StopFailure(ai=모르는 id) | 실행 추가 0, `last_event_at_ms` 갱신 | 모르는 id 로 실행 생성 |
| F7 | StopFailure(er 없음) | `error_kind=="unknown"`, ended | 기본값을 rate_limit 로 |
| F8 | `parse_event_line` 의 er: `"rate_limit"` / `"Bad Text!"` / 부재 | `"rate_limit"` / `"unknown"` / None | 재검증 삭제 |

**사다리 — `test_hub_session.py::InterruptionLadderTest`**

| # | 훅 사실 | transcript | 명부 | 기타 | 기대 state / base |
|---|---|---|---|---|---|
| I1 | rate_limit | — | unknown | — | interrupted / idle |
| I2 | rate_limit | — | unknown | 좀비 아닌 미종료 실행 | interrupted / working (RI3) |
| I3 | rate_limit | — | busy | — | interrupted / working |
| I4 | rate_limit | — | not_listed | — | idle / idle |
| I5 | rate_limit | — | unknown | 뒤이은 SessionEnd | done |
| I6 | rate_limit | — | idle | now = +2시간 | interrupted(stale 면제) |
| I7 | authentication_failed | — | unknown | — | idle(턴만 닫힘) |
| I8 | — | rate_limit, failed ≥ last_prompt | unknown | turn running | interrupted / working |
| I9 | — | rate_limit, failed < last_prompt | unknown | turn running | working |
| I10 | rate_limit | rate_limit(resets 있음) | unknown | — | 시각·resets 가 transcript 값 |
| I11 | rate_limit | — | unknown | — | `resets_at_ms is None` |
| I12 | 위 표 전체 | | | | `interruption is not None ⇔ state == "interrupted"` |
| I13 | 재현 사례 이벤트열(익명 fixture, 가짜 cwd) | 오류 줄 fixture | unknown/idle | now 15:50·16:20·16:32:50 | interrupted·interrupted·working |

**꼬리 — `test_hub_transcript.py::ParseSessionTailTurnFailureTest`**(`_assistant_line` 헬퍼 재사용)

| # | 꼬리 | 기대 |
|---|---|---|
| T1 | 마지막 대화 줄 = rate_limit 오류 줄(quotaLimits 포함) | kind·failed_at·resets(=resetsAt×1000) |
| T2 | 오류 줄 뒤 비대화 줄 9종(§1.3 실측 목록) | 여전히 검출 |
| T3 | 오류 줄 뒤 user 줄 | None |
| T4 | 오류 줄 뒤 정상 assistant 줄 | None |
| T5 | 마지막이 `isSidechain:true` 오류 줄 | 무시, 그 앞 메인 줄이 결정 |
| T6 | 오류 줄 뒤 `isMeta:true` user 줄 | 여전히 검출 |
| T7 | quotaLimits 부재(구버전) | 검출 + resets None |
| T8 | resetsAt 이 bool·float·문자열·ms 단위·과거·8일 초과 | resets None |
| T9 | timestamp 부재·깨짐 | None |
| T10 | error 가 비문자열 / 형태 위반 | None / `"unknown"` |
| T11 | 같은 꼬리의 모델·last-prompt | 기존 기대 불변(E11) |
| T12 | 오류 줄 본문(`message.content`)에 시크릿 모양 문자열 | 결과 어느 필드에도 없음 |

**훅 — `test_hub_hook.py::StopFailureProjectionTest`**: H1 StopFailure 페이로드(error·error_details·
last_assistant_message 포함) → 기록 줄의 키 = `{t,e,s,c,er}` 이고 두 자유 텍스트 원문이 줄 어디에도
없다 · H2 형태 위반 error → `"unknown"` · H3 서브에이전트 페이로드 → `ai`·`at` 기록 · H4 다른 이벤트
페이로드에 `error` 키가 있어도 `er` 없음.

**설정 — `test_hub_settings.py`**: S1 `HOOK_EVENTS` 에 StopFailure(7개) · S2 기존 6개 설치 → 설치 결과
`installed==["StopFailure"]`, 기존 엔트리 불변 · S3 제거가 StopFailure 도 지운다.

**프로젝트 — `test_hub_project.py`**: P1 세션 (idle, interrupted) → 프로젝트 interrupted, (working,
interrupted) → working · P2 `tail_by_session_id` 의 `turn_failure` 가 세션 뷰까지 배선된다.

**종단 — `test_hub_collect.py`**: W1 임시 `PROJECTS_DIR` 에 오류 줄로 끝나는 transcript + 그 앞
`UserPromptSubmit` 이벤트 → `collect_snapshot` 의 세션 `state=="interrupted"`, `resets_at_ms` 일치
(LS W1 과 같은 이유 — 배선 한 군데 누락은 순수 층 테스트로 못 잡는다).

### 8.2 수동 검증 V1 — `StopFailure` 실발화(구현 중 1회, **사용자 동의 후**)

`claude -p --settings <scratchpad>/v1-settings.json …` 처럼 실제 `settings.json` 을 건드리지 않는
경로로 StopFailure command 훅(stdin 을 스크래치패드 파일에 쓰기)만 얹고, 해 없는 API 오류(예:
존재하지 않는 모델)를 한 번 일으켜 `hook_event_name:"StopFailure"`·`error` 를 확인한다. 실제 CLI 를
호출하므로 동의가 필요하다. **발화하지 않으면** 훅 부분(RI1 의 (a)·RI11·문서의 7개)을 빼고
transcript 경로만 착지한다 — 그 판단을 사용자에게 보고한다.

**결과(2026-09-23, 메인 세션, 사용자 동의 후 1회)** — 데스크톱 번들 CLI 2.1.280 을
`-p --input-format stream-json --output-format stream-json --verbose --settings <스크래치패드>/settings.json
--model claude-nonexistent-model-v1` 로 1회 호출했다(fire-and-forget 발화가 프로세스 종료에 잘리지
않도록 오류 뒤 20초 살려 둠). 같은 settings 에 `StopFailure`·`Stop` 두 훅을 걸고 stdin 을 파일로 받았다.

- `StopFailure` **발화함**, `Stop` **발화 안 함**(Stop 캡처 파일이 생기지 않았다) — 「Stop 대신 온다」가
  실측으로 성립한다.
- 입력 키: `cwd`·`effort`·`error`·`hook_event_name`·`last_assistant_message`·`prompt_id`·
  `scratchpad_dir`·`session_id`·`transcript_path`. `error = "model_not_found"`, `error_details` 키 없음,
  `agent_id` 없음(메인 스레드).
- `last_assistant_message` 는 호스트 오류 문구 원문("There's an issue with the selected model …")이었다 —
  RI7 대로 기록하지 않는다.
- 판단: 훅 부분(RI1 (a)·RI11·문서의 7개)을 **유지**한다. 서브에이전트 문맥 발화(RI11)는 미관측 그대로라
  칩의 상한은 ZG 가드(90분)가 맡는다(RI11 마지막 항).

### 8.3 정적 가드(`tests/run.sh` T25 그룹)와 원장

번호는 착수 시점 main 의 최대 T25 번호 다음부터 배정한다(작성 시점 main 최대 T25-228, hub-session-modal
PRP 가 T25-228~239 선점 — §10). **착수가 그쪽 머지보다 앞서게 됐으므로**(§10 결정) 선점 구간과 그쪽의
재번호 여지(T25-228 충돌을 풀면서 한 칸 밀릴 수 있다)를 피해 **T25-241 부터** 쓴다. 번호 공백을
금지하는 검사가 있으면 그 규칙을 따르고, 따른 방식을 구현 보고에 적는다.

| 가드 | 정/역 | 검사 | 원장 변조행 |
|---|---|---|---|
| RI-G1 | 정 | `HOOK_EVENTS` 에 `"StopFailure"` · README 「전역 훅 7」 · `commands/hub.md` 「전역 훅 7개」+ StopFailure 표기 | HOOK_EVENTS 에서 StopFailure 삭제 |
| RI-G2 | 역(프라이버시) | `hub_hook.py` 에 `"error_details"`·`"last_assistant_message"` 문자열 리터럴 0 + StopFailure 분기가 `normalize_error_kind(` 경유 | `fields["er"] = payload.get("error")` |
| RI-G3 | 정 | 템플릿 `STATE_LABEL`·`STATE_GLYPH` 에 `interrupted:` 키 · `.badge.state-interrupted{` 존재 + 본문에 animation·box-shadow 0 | 규칙에 animation 추가 |
| RI-G4 | 역(프라이버시) | `_turn_failure_from_line` 본문에 `"content"`·`"message"` 접근 0 | 본문에 `payload.get("message")` 추가 |

- 기존 T25-150: 마지막 필드 기대값 `interruption: SessionInterruption | None = None`, `time\.` 정규식
  개정(GOTCHA 1). 원장 행의 판별 토큰이 여전히 유일한지 확인.
- `SOURCE_GUARD_ID_FLOOR`: 편집 후 `collect_guard_ids` 실측치로 올리고 주석에 근거 문단을 단다.
- T25-219: 코드 변경 불요 — 두 리터럴을 함께 고치면 통과, 한쪽만 고치면 실패한다.
- T25-7(Notification 미설치)·T25-152(README transcript 조항)·T25-211(훅의 프롬프트 흔적 0): 무영향 —
  문구는 추가만 한다.

---

## 9. 리스크와 대안

| # | 리스크 | 대응 |
|---|---|---|
| R1 | `StopFailure` 실발화 미관측 | V1. 미발화여도 서버 모드는 transcript 경로가 동작, 배지는 RI3 이 지킨다 |
| R2 | 오류 뒤 로컬 명령이 user 줄을 남기면 transcript 신호가 먼저 꺼진다 | 훅 사실이 있으면 무영향. 미이행 설치에서는 오늘 동작(작업중 고착)으로 돌아갈 뿐 더 나빠지지 않는다. 구현 중 구조 필드로 그 줄 모양을 표본 확인(§1.5-2) |
| R3 | transcript 형식 변경 | 검출이 조용히 멈춘다(오탐 방향 아님). 한 모듈에 가둔다 |
| R4 | `hub_session.py` ~750/800줄 | 머리 주석에 분리 조건 명시 |
| R5 | RI3 의 배지·칩 조합 | ZG4·README 문장 개정으로 명시 |
| R6 | stale 면제로 최악 상한이 이벤트 창(~48시간) | 명부 unknown + 크래시가 겹칠 때만. 수용 |
| R7 | T25-150 `time\.` 정규식 | datetime 도입과 한 커밋에 고친다 |

검토했으나 채택하지 않은 대안:

- **A1 transcript 만**(훅 추가 없음) — 이행 0이 장점이나 file 모드 공백·좀비 칩·한도 외 오류 고착.
  사용자가 "`/hub install` 재실행 없이"를 원하면 이것이 최소안이다(쟁점 1).
- **A2 훅만** — 실측 근거가 없고 초기화 시각이 없다.
- **A3 interrupted 를 working 아래에**(좀비 S 가 이기게) — §1.1 사례를 그대로 못 고친다.
- **A4 초기화 시각을 `rate_limits.json` 에서** — 어느 창이 막았는지 모른다.

---

## 10. 다른 세션과의 겹침 · 구현 순서

- `hub-session-modal` 워크트리(미커밋, 19bca3a 기준)는 `hub_template.html`(+231: 폴링·틱 맞대기 M1),
  `tests/run.sh`(+105: 6005~6020 집계, 8777 이후 신설 블록), `tests/mutations.tsv`(머리 개수 줄·끝
  행), `hub/README.md`(「화면 배치」 부근)를 고친다. 파이썬은 건드리지 않는다.
- 이 설계와 겹치는 곳: 템플릿의 `renderSession` 배지 호출 줄(그쪽 수정 줄과 한 줄 떨어짐),
  `SESSION_STATE_ORDER`(그쪽 `compareSessionsForDisplay` 주석 개정과 약 9줄 떨어짐) · `run.sh` 의
  `SOURCE_GUARD_ID_FLOOR` 한 줄과 T 번호 공간 · 원장 머리 개수 줄과 끝 행 · README 「화면 배치」.
  그쪽이 선점한 결정 접두 PU·SC 와 이 설계의 RI 는 겹치지 않는다.
- **이미 있는 충돌**: main 9f23534 의 **T25-228**(harness-update 사전 비교 가드)과 그 워크트리의
  **T25-228**(render 맞대기)이 같은 번호다 — 그쪽이 리베이스할 때 재번호가 필요하다. 그래서 이
  설계는 번호를 확정하지 않는다(§8.3).
- **권고: 그쪽 머지 후 착수.** 겹치는 곳이 전부 "한 줄 핫스팟"(래칫 상수·원장 머리·T 번호)이라
  먼저 가면 그쪽이 다시 풀어야 하고, 이 설계의 파이썬은 템플릿과 함께만 착지할 수 있다(GOTCHA 2
  — 분할 착지 불가).
- 대안: 급하면 이쪽 먼저 — 그쪽이 리베이스하며 래칫·원장 머리·README 한 문단을 기계적으로
  다시 맞춘다.
- **결정(2026-09-23, 승인 직후)**: 그쪽 작업이 오래 걸릴 것이라 **착수는 지금 이 워크트리에서** 하고
  **합치기만 늦춘다**. hub-session-modal 이 먼저 main 에 들어가면 **이쪽이 리베이스**하며 핫스팟(래칫
  상수·원장 머리·T 번호·템플릿 배지 호출 줄·`SESSION_STATE_ORDER`·README 「화면 배치」)을 맞춘다 — 이
  설계의 템플릿 변경(+35)이 그쪽(+231)보다 작아 다시 얹는 비용이 작다. 리베이스 뒤에는 그쪽 부분 갱신
  (`data-render-key` 맞대기) 아래에서도 30초 틱이 「초기화됨」 전환을 다시 그리는지 확인한다(§7 「전환」).
  이쪽이 먼저 끝나면 합치는 순서는 그때 사용자가 정한다.

---

## 11. 사용자 확인 쟁점

1. **신호원** — 훅(StopFailure) + transcript 둘 다(권고, RI1) / transcript 만(A1 — `/hub install`
   재실행 불필요, 대신 서버를 끈 채 쓰면 거의 안 보이고 죽은 서브에이전트 칩이 90분 남는다).
2. **기존 설치 이행** — 배포 후 `/hub install` 을 한 번 다시 실행(권고, 자동 이행 없음, RI12).
3. **초기화 시각 표기** — 안 A: 배지에 「· 초기화 16:30」/「· 초기화됨」(권고) / 안 B: 배지는
   「한도 초과」만, 시각은 툴팁. 목업 참조.
4. **범위** — 한도 초과만 새 상태, 다른 API 오류는 턴만 닫아 「대기」(권고, RI6) / 「오류로 중단」
   라벨도 추가.
5. **순서·검증** — hub-session-modal 머지 후 착수(권고, §10), 구현 중 StopFailure 실발화 확인(V1,
   실제 CLI 1회 호출)을 해도 되는가.

---

## 12. 검증 명령 (정본 — 프로젝트 CLAUDE.md §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

`__pycache__` 가 `commands` 파일 수를 흔들지 않도록 임포트 실험은 `python3 -B` 로 한다.
