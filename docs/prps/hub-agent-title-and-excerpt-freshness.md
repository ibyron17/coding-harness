# 허브 — 재개된 서브에이전트의 제목 · 프롬프트 발췌 지연 (PRP)

> 상태: **구현 완료(2026-10-01)** — M1 `99a8c22` · M2 `5110b10` · M3(이 문서를 고친 커밋과 같다). 승인(2026-09-30)은 §13 전부 권고안:
> Q1 안 A(제목만 바꿈, 재개 횟수는 툴팁) · Q2 8MiB · Q3 입력 줄 직접 읽기 + 자동 새로고침 1분 유지. 구현 중 설계와 달라진 것은 §6.4(M1)·§7.4(M2)·
> §8(M3)의 「구현 이탈 모음」에 모았다. 별건 N1(밑줄 경로 인코딩)은 이 작업 뒤 같은 세션에서 축약 경로로 이어서 고친다.
>
> 대상: 허브 파이썬 4개 모듈(`hub_transcript`·`hub_session_facts`·`hub_subagent`·`hub_subagent_read`) +
> `hub_session.SubagentRunView` 필드 2개 + `hub_template.html` 실행 줄 렌더 함수 2개 + `tests/hub` + `tests/run.sh`
> (T25 신설 2·주석 갱신 1)·`tests/mutations.tsv`(+2행) + `hub/README.md` + PRP 2개 이관 표기.
> **훅(`hub_hook.py`)·서버(`hub_server*.py`)·수집 배선(`hub_collect.py`)·프로젝트 합성(`hub_project.py`)은 한 줄도
> 바꾸지 않는다**(결정 TF5·TF13). `commands/hub.md` 설치 고지는 이미 「transcript 에서 읽혀 인라인된다」고 적고
> 있어 무변경(문구 대조 확인, §10).
>
> 기준 커밋: `95dd4db`(브랜치 `worktree-hub-agent-title-and-excerpt-freshness`, main 과 같다). 코드 위치는 함수·상수
> 이름으로 가리킨다. 결정 접두 **TF**(Title·Freshness) — 워크트리의 `*.md`·`*.py`·`*.sh`·`*.html`·`*.tsv`·`*.txt`·
> `*.json` 전수에서 0건 확인.
>
> 설계 모델: opus(디스패치 기본값 — model-routing 승격 기준 1~4 해당 없음). 목업: §14.
> 개인정보: 이 문서의 실측은 시각·길이·해시·필드 이름만 싣는다. 사용자 프롬프트 글자는 옮기지 않았다(목업의 발췌·
> 제목 문구는 지어낸 값이다).

---

## 0. 한눈에

| 항목 | 내용 |
|------|------|
| 요구 | ① SendMessage 로 **재개**한 서브에이전트의 실행 줄이 첫 작업 제목(M1)으로 남는다 ② 새 프롬프트를 입력해도 `span.excerpt` 가 늦게 바뀐다(새로고침해도 안 되다가 조금 지나서 바뀐다) |
| 원인 ① | 허브의 제목은 `meta.json` 의 `description`(띄울 때 `Agent` 도구 인자) 하나다. 호스트는 재개 때 `SubagentStart` 를 같은 id 로 다시 내고 meta.json 도 다시 쓰지만 **`description` 은 원래 값 그대로**다(실측 9/9). 재개 작업의 짧은 이름은 **부모 기록의 `SendMessage.input.summary` 에만** 있다 |
| 원인 ② | 발췌 출처 `last-prompt` 줄은 호스트가 **메시지마다 쓰지 않고, 대화 기록이 32KiB 더 쌓일 때마다 다시 붙이는 메타 줄**이다(2.1.284 번들: `bytesSinceMetadataReAppend >= J_/2`, `J_=65536`). 사람 프롬프트 314건(3일): 새 값이 실리기까지 **중앙 22.8초 · p90 65초 · p99 662초**, 5%는 다음 프롬프트까지 끝내 안 실림. 허브 수집·서버·폴링은 원인이 아니다(요청 시 동기 수집 24~37ms) |
| 핵심 결정 | TF1 발췌 = 꼬리에서 「사람 프롬프트 줄에서 호스트 규칙으로 뽑은 값」과 「`last-prompt` 값」 중 **파일에서 더 뒤의 것**(추가 I/O 0) · TF3 호스트 규칙 부분 사본(실측 일치 94.7%) · TF6 한 줄 = 에이전트 1개 유지 · TF7 재개 횟수 = `SubagentStart` 재발화 수 · TF8 재개 제목 = `SendMessage.summary` ⋈ `toolUseResult.resumedAgentId` · TF9 재개가 있는 세션만 부모 기록 끝 최대 **8MiB** 1회 읽기 · TF13 제목은 `SubagentMeta` 보강 필드로 실어 배선 무변경 |
| 설계 단계 실측 | 이 세션(a74d3843) 재개 9건·사람 프롬프트 6건 전수 대조(§2) · 30일 `SendMessage` 225건 형태 조사 · 14일 사람 프롬프트 453건 유도 충실도 · 스캔 원형 비용(4/8/16MiB) · 헤드리스 Chrome 목업(현재 대 시제품) |
| 변경 규모(추정) | 파이썬 +약 190줄(transcript +80 · subagent +70 · subagent_read +35 · facts +6 · session +8) · 템플릿 +약 15줄 · tests/hub +약 480줄(DOM 모듈 1개 신설) · run.sh +약 50 · 원장 +2행 · README 약 ±30 |
| 가드 | 신설 2(T25-260·T25-261) · 주석 갱신 1(T25-206, 논리 무변경) · 하한 `SOURCE_GUARD_ID_FLOOR` 515 → 517 |
| 커밋 | 3개(M1~M3, §12) |
| 승인 필요 | 3건(§13) — Q1 제목 표시안(권고 A) · Q2 읽기 범위 8MiB(권고) · Q3 발췌 방식 + 자동 새로고침 1분 유지(권고) |

---

## 1. 요구사항 요약

허브 세션 줄의 서브에이전트 실행 목록은 실행 1건의 제목으로 그 에이전트를 **띄울 때** 붙인 설명(`description`)을 쓴다.
오케스트레이터가 같은 에이전트를 `SendMessage` 로 재개해 다음 마일스톤 일을 시키면(이 세션: 검수 에이전트 1개가
M1→M2→M3, 구현 에이전트 1개가 M1→M2→M3), 호스트는 같은 id 로 실행을 다시 시작하지만 그 설명은 바꾸지 않아 허브는
M3 를 검수하는 동안에도 「Review M1 …」을 보여 준다. 또 세션 줄의 발췌는 호스트가 대화 기록에 남기는 `last-prompt`
메타 줄을 읽는데, 호스트가 그 줄을 **32KiB 마다 한 번** 다시 적기 때문에 방금 입력한 프롬프트가 수십 초~수 분 뒤에야
나타난다(새로고침은 아직 파일에 없는 값을 가져올 수 없다). 이 PRP 는 재개 작업의 짧은 이름을 부모 기록의 재개 요청에서
찾아 제목으로 쓰고, 발췌는 이미 읽는 꼬리 안의 **사람 프롬프트 줄 자체**에서 호스트와 같은 규칙으로 뽑아 즉시
보여 준다. 훅은 새 자유 텍스트를 기록하지 않는다는 원칙, 계약 A(스크럽 + 상한), `record_prompt_excerpt` 오프
스위치는 그대로 지킨다.

### 1.1 요구 2건과 성공 기준

| # | 요구(원문 요지) | 성공 기준(검증 가능) | 결정 | 검사 |
|---|----------------|--------------------|------|------|
| ① | M3 검수·구현이 도는데 허브는 M1 검수 중으로 보인다 | (a) `SendMessage`(요약 S)로 재개된 실행은 다음 수집의 스냅샷에서 `resume_title == 계약A(S)`·`resume_count == 재개 횟수` 이고 `.agent-run-title` 이 S 를 보인다(카드·카드 상세보기 둘 다) (b) 그 재개에 요약이 없으면 `resume_title` 은 null 이고 제목은 `description` 폴백 — **더 옛 요약으로 대체하지 않는다** (c) 재개된 적 없는 실행은 오늘과 한 글자도 같다 (d) 이 세션 재현: 22:30 기준 재개 6개 에이전트 6/6 이 3.1MB 스캔 안에서 풀린다 | TF6~TF13 | S1~S11·R1~R7·F1~F4·V1~V3 · D25~D28 · T25-206·T25-261 |
| ② | 프롬프트를 입력해도 발췌가 늦게 바뀐다. 새로고침해도 안 되다가 조금 지나서 바뀐다 | (a) 꼬리에서 사람 프롬프트 줄이 마지막 `last-prompt` 줄보다 뒤에 있으면 `SessionTail.last_prompt` 는 그 줄에서 유도한 값이다 — **사용자 줄이 기록된 순간(호스트 드레인 ≤0.1초)부터** (b) 유도값은 호스트가 나중에 적는 `lastPrompt` 와 같다 — 14일 재생 453건 중 **≥94%(실측 429건) 글자 단위 일치**, 나머지는 명령·bash 턴 포기(오늘과 같은 지연) (c) 새로고침·창 복귀·새로고침 버튼은 즉시, 가만히 두면 다음 폴링(≤60초)에 반영 (d) 추가로 읽는 파일 0, 훅 무변경 | TF1~TF5 | H1~H19 · T25-260 |

### 1.2 해석 명시 (추측하지 않고 적는다)

- **① 「M1 검수 중으로 보인다」** — 허브는 재개를 이미 「같은 줄이 다시 진행 중, 경과는 재개 시각부터」로 다룬다
  (`hub/README.md` 「화면 배치」 문단, 오늘의 계약). 틀린 것은 **제목 하나**다(경과 5분·진행 중 표시는 맞았다 — 사용자
  캡처의 「5분」 = M3 재개 16:57:30 부터). 그래서 행 단위(한 줄 = 에이전트 1개)는 바꾸지 않는다(TF6).
- **② 「늦게 업데이트」** — 원인은 허브가 아니라 입력 데이터의 시점이다(§2.2). 폴링 주기·서버 창을 줄여도 파일에 없는
  값은 나오지 않는다(§2.3 가설 판정). 고치는 것은 「무엇을 읽는가」다.
- **두 건을 한 PRP 로** — 사용자가 한 묶음으로 요청했다. 서로 독립이라 커밋은 나눈다(M1 = ②, M2·M3 = ①).

### 1.3 하지 않는 것 (범위 밖 — 명시)

- 훅에 새 필드를 기록하지 않는다(요약·프롬프트 모두). `hub_hook.py` 무변경.
- 재개 구간(M1·M2·M3)별 이력을 화면에 따로 그리지 않는다(TF6 — 안 C 기각).
- 서브에이전트 자신의 대화 기록(`agent-<id>.jsonl`) 내용은 여전히 읽지 않는다(mtime 만 — 결정 SL1 그대로).
  > **개정됨(2026-10-07, [`hub-live-activity.md`](./hub-live-activity.md) 결정 LA1·LA6)** — 지금 도는 실행의 기록 끝은 이제 수집 때마다 읽는다(도구 종류·시각·개수만 쓰고 내용은 싣지 않는다). 위 줄은 작성 시점의 결정 기록이다.
- 폴링 주기(60초)·서버 신선도 창(2초)은 바꾸지 않는다(TF5, Q3 에서 선택지로만).
- §16 의 부수 발견(밑줄 경로 인코딩 등)은 고치지 않는다 — 별건.

---

## 2. 원인 실측

### 2.1 요구 ① — 재개된 실행의 제목

**허브의 현재 경로.** `hub_subagent.parse_subagent_meta` 가 `payload["description"]` 을 제목으로 판다(계약 A). 훅 쪽
`hub_session_facts._handle_subagent_start` 는 같은 `agent_id` 의 `SubagentStart` 가 다시 오면 그 항목을 **덮어써**
시작 시각을 재개 시각으로 바꾸고 종료를 지운다 — 한 줄이 재개 구간을 따라가는 구조가 이미 있다. 시작 시각은
`summarize_agent_runs` 가 meta.json mtime(결정 AR7)을 우선한다.

**호스트 계약(문서).** 훅 문서 「SubagentStart」: *"Runs when Claude spawns a subagent with the Agent tool, **when Claude
resumes a subagent**, and each time an in-process agent team teammate handles a new message."* 입력은 `agent_id`·
`agent_type` 뿐 — 재개인지 구분하는 필드도, 설명 필드도 없다.

**이 세션(a74d3843)의 재개 9건 전수**(부모 기록 `SendMessage` tool_use/tool_result · 이벤트 로그 · meta.json stat):

| SendMessage | 결과(`resumedAgentId`) | SubagentStart 재발화 | 간격 | meta.json mtime | summary 길이 |
|---|---|---|---|---|---|
| 14:45:56.365 | 14:45:57.365 · adf3494d(구현) | 14:45:57.631 | 1.3s | (다음 재개가 덮음) | 26 |
| 15:28:30.237 | 15:28:31.549 · a048ed50(검수) | 15:28:31.626 | 1.4s | (다음 재개가 덮음) | 27 |
| 16:12:22.695 | 16:12:23.651 · adf3494d | 16:12:23.720 | 1.0s | 16:12:23.737 | 26 |
| 16:57:28.933 | 16:57:30.483 · a048ed50 | 16:57:30.564 | 1.6s | 16:57:30.585 | 27 |
| 19:27:51.541 | 19:27:52.545 · a15a507d(M4 구현) | 19:27:52.640 | 1.1s | (다음 재개가 덮음) | 30 |
| 19:42:35.349 | 19:42:36.475 · a15a507d | 19:42:36.546 | 1.2s | 19:42:36.569 | 30 |
| 20:31:28.774 | 20:31:49.386 · a3ba5bd2(M4 검수) | 20:31:49.461 | 20.7s | 20:31:49.478 | 28 |
| 21:12:26.130 | 21:12:27.596 · aea8db83(M5 구현) | 21:12:27.665 | 1.5s | 21:12:27.682 | 21 |
| 21:25:52.780 | 21:25:53.915 · a0c1cff2(M5 검수) | 21:25:53.986 | 1.2s | 21:25:54.003 | 23 |

- 재개마다 같은 id 로 `SubagentStart` 가 다시 온다(9/9). meta.json 은 재개 때 **다시 쓰이고**(mtime = 마지막 재개 +17~23ms,
  재개된 에이전트 6/6) **내용의 `description`·`toolUseId` 는 첫 띄움 값 그대로**다(예: a048ed50 = 「Review M1 chip glyph
  removal」, M3 재개 뒤에도). → 옛 PRP 의 「meta.json mtime 은 시작 때 1회 쓰이고 갱신되지 않는다」(hub-agent-runs-and-
  prompt-source §1.3)는 지금 호스트에서 거짓이다. 경과 표시(마지막 재개부터)는 그 덕에 이미 맞았다.
- 사용자 캡처(검수 경과 5분으로 보아 17:02 무렵 — 추정)의 세 줄 — 검수 「Review M1 …」 5분(M3 재개 16:57:30 부터) · 구현 「Implement M1 …」 44분
  (M3 구간 16:12:23→16:56:31) · 설계 59분 — 이 표와 정확히 맞는다.

**재개 작업의 짧은 이름은 어디에 있나.**

| 후보 | 실측 | 판정 |
|---|---|---|
| 부모 기록 `SendMessage` tool_use `input` | 키 `to`·`summary`·`message`(+ 구형 `recipient`·`content`·`type`). **30일 225건**: `summary` 있음 220(10~50자, 중앙 25자 — `description` 과 같은 성격의 짧은 라벨), 없음 5 | **채택**(TF8) |
| 같은 tool_use_id 의 tool_result `toolUseResult` | 「Resuming agent X」 → `resumedAgentId` 있음(**189/189**, 전부 `to` 와 같음) · 「Message queued for delivery to X」(실행 중 에이전트에 전달, 재개 아님) → 없음 20건(+ 기타 1) · 도구 비활성 오류 → 문자열 15건 — 합 225 | **짝 판정에 채택** — 「이 요청이 X 를 재개했다」의 호스트 신호 |
| 서브에이전트 기록의 재개 턴 | `origin:{kind:"coordinator"}`·`isMeta:true`, 첫 줄은 호스트 고정 봉투(54자), 이어서 **메시지 본문 전문**(첫 줄 115~458자), `summary` 없음(7/7). 파일 최대 7MB, 재개 턴이 파일 끝에서 멀다 | 기각(TF15) |
| meta.json | 재개 때 다시 쓰이지만 새 값이 없다(위) | 해당 없음 |
| 훅 | `SubagentStart` 입력에 없음. `PreToolUse(SendMessage)` 로 받을 수는 있으나 자유 텍스트 기록 금지 원칙 위반 | 기각(TF15) |

**그 줄이 부모 기록 끝에서 얼마나 먼가**(기존 128KiB 꼬리로 충분한가):

| 재개 | 구간 끝 시점의 거리 | 22:30 시점 거리 |
|---|---|---|
| 8건 | 35~80KB — 128KiB 안 | 0.5~3.3MB |
| a048ed50 M3 검수(**사용자 캡처 건**) | **210KB — 128KiB 밖**(17:05 에 90KB 이미지 프롬프트가 들어왔다) | 3.0MB |

→ 꼬리 128KiB 만 보면 캡처한 바로 그 순간에 실패하고, 끝난 실행은 곧 원래 제목으로 되돌아간다. 전용 창이 필요하다(TF9).

**스캔 원형 비용**(스크래치 `freshness/resume_scan_proto.py`·`resume_scan_marker.py`, 이 세션 14MB 기록, page cache):

| 예산 | 결과 | 시간 |
|---|---|---|
| 128KiB | 0/6 | 0.3ms |
| 1MiB | 3/6 | 1.7ms |
| 4MiB·8MiB·16MiB | **6/6 — 3.1MB 에서 조기 종료** | 4.8~5.9ms |
| 8MiB, 못 찾는 id 1개 포함(끝까지 훑음 — 최악) | 6/7 | 10.9~17.3ms |

> → **구현 정정(M2) — 창·파서 입출력을 `bytes` 로** — 첫 구현은 설계 인터페이스(§7.2·7.3) 그대로 창을 `str` 로 디코딩해 파서에 넘겼고, 그러면 위 표의
> 5ms 가 나오지 않았다: 창 전체를 먼저 디코딩(3ms)하고 줄로 나누기 때문에 조기 종료가 효과가 없었다(읽기 1 + 디코딩 3 + 해석 9ms = 세션당 **15~16ms**,
> 재개 세션이 3개인 이 기계에서 `collect_snapshot` 13ms → **52ms** — TF9 에스컬레이션 조건 초과). 사용자 승인 고지(「한 번에 보통 5ms·최악 15ms」)의 경계 밖이라
> 창을 **`bytes` 로 들고**, 파서가 결과 표지(`"resumedAgentId"`)를 품은 줄만 `rfind` 로 건너뛰며 뒤에서부터 디코딩·해석하고, 풀어야 할 에이전트의 결과를
> 만나면 **그 줄 앞에서만** 요청 표지(`"SendMessage"`)를 품은 줄을 찾도록 고쳤다(화면에 보이는 거동·에이전트별 「마지막 재개 1건」·「요약 없으면 null」·스크럽
> 입력 상한·게이트는 그대로 — 내부 함수 입출력만 바뀐다). 같은 bytes 창에서 줄마다 `rfind(b"\n")` 로 경계를 거슬러 찾고 줄마다 표지 둘을 검사하는 변형은 세션당
> 5~7ms(읽기 포함)였고, 표지 위치로 건너뛰는 이 방식은 2.5~3.3ms 다(빠른 이유는 재 보지 않았다 — 측정값만 따랐다). 요청 줄은 결과 줄 바로 앞에 있다(실측 225쌍
> 전부 짝 성립 · 간격 중앙 6.5KB·최대 30KB) — 그래서 요청 탐색은 짧다.
>
> | 같은 프로세스·같은 실제 데이터(이 세션 기록 15.9MB 의 끝 8MiB, 재개 에이전트 9개 전부 풀림) | 첫 구현(str 창) | bytes 창 |
> |---|---|---|
> | 세션 하나: 읽기 + (디코딩) + 해석, 조기 종료 | 0.7 + 3.1 + 8.5 = **14.2ms** | 0.7 + 1.8 = **2.7ms** |
> | 세션 하나: 해석, 못 찾는 id 포함(창 끝까지 — 최악) | 10.6ms | 2.7ms |
> | 재개 세션 3개(에이전트 13개, 13/13 해소) `read_subagent_metas` (보강 끔 1.0ms) | 37.8ms | **7.4ms** |
> | `collect_snapshot` 전체, prune·캡처 읽기 제외 (보강 끔 14.3ms) | 50.4ms | **20.4ms** |
>
> 정확도는 그대로다: 독립 참조 구현과 대조해 최근 14일 기록의 재개 에이전트 51/51 · 60일 89개(86 제목 + 요약 없음 3) 불일치 0·예외 0, 끝 512KiB·4MiB 창
> (글자 한가운데서 잘리는 머리 10·13개 포함)에서도 18·29개 전부 일치. 강등 경로의 비용: 요청을 못 찾는 결과 줄(호스트 형식이 바뀐 경우)은 처음에는 그 줄 앞 요청 줄 전부를
> 결과마다 다시 해석해 결과 수 × 요청 수로 느려졌다(검수 LOW-1: 합성 결과 100개 × 요청 2000줄에서 **604ms**) — 첫 미스 때 그 훑기가 본 요청을 색인으로 남기고 이후는 조회만 하도록 고쳐
> **6.8ms**(결과 100 × 요청 200줄 60→1.0ms, 8 × 2000줄 48→6.4ms)가 됐다. 정상 경로(첫 시도에 짝을 찾음)는 색인 없이 그대로다: 조기 종료 1.8ms·최악 2.7ms 불변. 그때도 제목 없음으로
> 안전하게 강등된다.

### 2.2 요구 ② — 발췌 지연

**허브의 현재 경로.** 발췌 = `hub_transcript.parse_session_tail` 이 꼬리 128KiB 를 역방향으로 훑어 처음 만나는
`type:"last-prompt"` 줄의 `lastPrompt`(결정 PS1·PS9). 훅은 프롬프트를 기록하지 않는다(PS4).

**호스트(Claude Code 2.1.284) 번들에서 읽은 것**(`/Users/dev/Library/Application Support/Claude/claude-code/2.1.284/…`,
읽기 전용 grep — 스크래치 `freshness/bundle_grep.py`):

| 항목 | 번들 원문(요지) | 뜻 |
|---|---|---|
| 쓰기 지연 | `FLUSH_INTERVAL_MS=100` · `enqueueWrite → scheduleDrain → drainWriteQueue` | 메시지 줄은 기록 대기열에 들어가면 **0.1초 안에** 디스크에 닿는다 |
| 메타 재부착 | 드레인 끝: `if(this.bytesSinceMetadataReAppend>=J_/2) … reAppendSessionMetadataAsync(…)` · `var J_=65536` | `last-prompt`(와 `custom-title`·`relocated`·`worktree-state`… 묶음)은 **마지막 재부착 이후 32KiB 가 쌓였을 때만** 다시 붙는다(호스트의 64KiB 꼬리 읽기 창을 위한 장치로 보인다) |
| 값 갱신 | `insertMessageChain` 끝: `let Fe=Ztn(e);if(Fe)this.currentSessionLastPrompt=this.normalizeLastPrompt(Fe)` | 값은 사용자 줄을 기록하는 순간 바뀌지만, **파일에 나타나는 것은 다음 재부착 때**다 |
| 값 규칙 | `Ztn`: `type==="user"`·비`isMeta`·비`isCompactSummary` 의 텍스트 블록을 순서대로 — `xue`(`<pasted_content id="hhhh">` 벗기기) → `<command-name>` 이면 내장 명령은 건너뛰고 사용자 명령은 `/cmd args` → `<bash-input>` 이면 `! cmd` → `l7t=/^(?:\s*<[a-z][\w-]*[\s>]\|\[Request interrupted by user[^\]]*\])/` 면 건너뜀 → 아니면 그 블록. `normalizeLastPrompt`: 줄바꿈→공백·trim·200자 넘으면 200자+`…` | TF3 이 옮길 규칙 |

**실측이 번들을 받친다.**

- 연속 `last-prompt` 줄 간격(최근 3일 22개 기록, 2,749 간격): 중앙 39KB · p10 34KB · **97% 가 32KiB 이상**(나머지 3%는
  압축·종료·제목 변경 같은 다른 재부착 계기).
- 사람 프롬프트(`origin.kind=="human"`, 압축 재삽입 제외) → 그 값을 담은 첫 `last-prompt` 줄까지(쓰인 시각 ≈ 그 줄 바로
  앞 항목의 timestamp — 같은 드레인에 쓰이므로):

| 창 | 프롬프트 | 실린 것 | 지연 중앙 | p75 | p90 | p99 | ≤1초 | 다음 프롬프트까지 끝내 안 실림 | 실린 값 = 그 프롬프트 |
|---|---|---|---|---|---|---|---|---|---|
| 3일 | 314 | 298 | **22.8s** | 43.1s | **65.0s** | 661.9s | 83(이미지·큰 첫 턴 — 한 줄로 32KiB 초과) | **15(5%)** — 그 턴이 짧아(중앙 14KB) | 297/298 |
| 14일 | 448 | 430 | 22.7s | 43.1s | 69.2s | 578.4s | 124 | 17 | 429/430 |

- 이 세션의 사람 프롬프트 6건(UPS = UserPromptSubmit 훅 `t`):

| 사용자 줄 | UPS 훅 | `last-prompt` 에 실린 시각 ≈ | 지연 | 그때까지 쌓인 바이트 |
|---|---|---|---|---|
| 09-28 14:00:05.708 | +0.17s | 같은 드레인 | 0.0s | 248KB(첫 턴 첨부) |
| 09-28 14:14:17.742 | +0.12s | 14:15:21.160 | **63.4s** | 32,089 |
| 09-28 16:25:37.434 | +0.13s | 16:26:39.277 | **61.8s** | 33,510 |
| 09-29 09:18:05.523 | +0.18s | 09:20:41.577 | **156.1s** | 6,767(다른 재부착 계기) |
| 09-30 12:00:55.848 | +0.27s | 같은 드레인 | 0.0s | 58KB(재개 첨부) |
| 09-30 17:05:31.756 | +0.11s | 같은 드레인 | 0.0s | 92KB(이미지 첨부) |

→ 짧은 텍스트 프롬프트는 거의 항상 1분 안팎 늦는다. 사용자가 본 「새로고침해도 안 되다가 조금 지나서 바뀐다」와 같다.

**허브 쪽은 원인이 아니다.** 서버는 인식된 경로 요청마다 `_SnapshotRefresher.collect_if_older_than(now, 2000ms)` 로
**동기 수집한 뒤** hub.html 을 서빙한다(`_HubRequestHandler.do_GET`) — 설치본 서버에 GET 24~37ms, 수집 성공 스탬프
(`last_collect_success`)가 그 응답 시간 안에서 갱신됨을 확인(스크래치 `freshness/get_collect_check.py`).
페이지는 60초 폴링 + 새로고침 버튼·포커스·탭 복귀 때 즉시 폴링이며 받은 스냅샷을 그대로 다시 그린다(`poll`·`render`).
설치본 `~/.claude/hub/bin` 의 관련 8개 모듈은 워크트리와 바이트 동일.

### 2.3 가설 판정 (디스패치가 제시한 것)

| 가설 | 판정 | 근거 |
|---|---|---|
| (a) UserPromptSubmit 훅이 부른 수집이 호스트가 새 프롬프트를 쓰기 **전에** 돌아 옛 발췌로 굳힌다 | **이 환경에서는 무관** | 서버가 살아 있으면 훅은 수집을 띄우지 않는다(`should_spawn_collect` — server_alive → False). 게다가 문제의 값(`last-prompt`)은 사용자 줄보다 수십 초 늦게 쓰이므로, 훅 시점을 늦춰도 소용없다. 서버가 꺼진 폴백 모드의 순서는 §15 A1 |
| (b) 서버가 지금 파일을 먼저 돌려주고 수집은 뒤에서 한다 / 수집 최소 간격 | **거짓** | 동기 수집 후 서빙. 최소 간격은 2초 창뿐 |
| 실제 원인 | 입력 데이터 시점 | 호스트가 `last-prompt` 를 32KiB 마다만 다시 적는다(§2.2) |

**회귀였다.** 2026-09-16 이전에는 훅이 UserPromptSubmit 시점에 발췌(`p`)를 적어 즉시 보였다. PS4 가 그것을 지우고
`last-prompt` 로 옮길 때 **위치**(꼬리 128KiB 안, 30/30)는 확인했지만 **시점**은 재지 않았다 — 지연은 그때 들어왔다.

### 2.4 부수 발견 (§16 에 정리)

- 호스트는 워크트리 진입 때 세션 기록 파일(과 `<session>/` 디렉터리)을 **새 cwd 의 프로젝트 폴더로 옮긴다**(`relocated`
  메타 줄 145건 · 4개 경로 — 이 세션은 지금 `-…-hub-agent-title-and-excerpt-freshness/` 아래에 있다). 옛 결정 E13 의
  전제(「최초 cwd 기준으로 남는다」)가 바뀌었지만 허브의 규칙(`observed_cwds` 순으로 먼저 존재하는 파일)은 여전히 맞다.
- `encode_project_dir_name` 은 `/`·`.` 만 `-` 로 바꾸는데 호스트는 `replace(/[^a-zA-Z0-9]/g,"-")`(+200자 초과 시 해시) —
  밑줄 경로(`…/notebook_wiki/…`)의 세션은 발췌·모델·실행 제목이 늘 비어 있다(실측: 89ab77d8, 기록엔 `last-prompt` 있음).

---

## 3. 설계 결정과 근거

### 요구 ② — 발췌

#### TF1. 발췌 = 꼬리에서 **파일상 더 뒤에 있는 것** — 사람 프롬프트 줄의 유도값 vs `last-prompt` 값

`parse_session_tail` 의 역방향 스캔 1회(PS2 유지) 안에서, 발췌를 **확정하는 줄**을 둘로 늘린다 — (1) `last-prompt` 줄
(오늘 그대로: `lastPrompt` 가 문자열이면 스크럽·클립, 아니면 None 으로 확정) (2) 유도 가능한 사람 프롬프트 줄(TF2·TF3).
뒤에서 먼저 만나는 쪽이 이긴다. 근거: `last-prompt` 는 사용자 줄 **뒤에만** 쓰이고 그때의 최신 값을 담으므로(§2.2
「값 갱신」 — 297/298 일치), 사용자 줄이 마지막 `last-prompt` 보다 뒤에 있으면 그 줄이 더 새롭고, 앞에 있으면
`last-prompt` 가 이미 그것(또는 그 이후 값)을 담는다. **추가 I/O 0** — 같은 128KiB 문자열이다.

- 사용자 줄이 꼬리 창에 걸려 잘리면 JSON 이 깨져 자연 탈락한다(MD6) — 그런 큰 줄(32KiB 초과)은 호스트가 같은 드레인에서
  `last-prompt` 를 바로 붙이므로 폴백이 이미 새 값이다.
- 유도를 포기한 사람 줄(TF3)은 **확정하지 않고 계속 훑는다** — 더 앞의 유도 가능한 사람 줄 또는 `last-prompt` 가 정한다.
  호스트도 내장 명령·빈 텍스트 턴에서는 이전 값을 유지하므로(Ztn 이 건너뜀) 같은 방향이다.

#### TF2. 사람 프롬프트 줄 판정 — 호스트가 붙인 표지만 믿는다

`type=="user"` · `origin.kind=="human"` · `isMeta`·`isSidechain`·`isCompactSummary` 가 참이 아님 · `tool_result` 블록 없음.
`origin` 이 없는 줄(구버전 호스트·SDK 세션)은 판정하지 않는다 → 오늘과 같은 `last-prompt` 경로. 이 표지 덕에 서브에이전트
보고 전달(`queued_command`·`origin.kind=="task-notification"`)·조정자 메시지(`coordinator`)·도구 결과가 섞이지 않는다
(이 세션 9/30: UserPromptSubmit 36회 중 사람 입력 2회 — 나머지는 보고 전달).

#### TF3. 유도 규칙 = 호스트 `Ztn`+`normalizeLastPrompt` 의 **부분 사본**

텍스트 블록(문자열 content 는 블록 1개)을 순서대로:

1. `<pasted_content id="hhhh">\n` · `\n</pasted_content id="hhhh">` 를 벗긴다(호스트 `xue`).
2. `<command-name>` 또는 `<bash-input>` 이 있으면 **포기**(None) — 내장 명령 목록을 모르므로 흉내 내지 않는다(TF1: 계속 훑음).
3. 호스트 `l7t` 와 같은 모양(태그로 시작 · `[Request interrupted by user…]`)이면 그 블록을 건너뛴다.
4. 처음 남는 비어 있지 않은 블록이 원문이다.

정규화는 TF4. 번들 원문을 옮긴 사본이라 **출처를 상수 주석에 적는다**(버전·함수명). 호스트 규칙이 바뀌어 어긋나면
「다음 재부착 때 호스트 값으로 바뀐다」로 스스로 되돌아온다(최악 = 오늘의 지연).

**충실도(설계 단계 재생 — `freshness/derive_fidelity.py`, 14일 사람 프롬프트 중 호스트 값이 나중에 실린 453건)**:
글자 단위 일치 **429(94.7%)** · 포기 23(5.1% — 명령·bash, 오늘처럼 지연) · 불일치 1(둘 다 201자 절단 — 호스트 `re(n,200)`
의 절단 단위와 파이썬 코드포인트 슬라이스 차이로 보인다, §15 A2).

#### TF4. 스크럽 → 호스트식 200자 절단 → 400자 클립 — 노출량은 오늘 이하

유도 경로: 줄바꿈→공백·strip → **`redact_secret_tokens`** → 200자 넘으면 앞 200자(strip)+`…` → `_clip_to_length(…,
LAST_PROMPT_MAX_CHARS)`(단일 최종 관문, 정상 데이터에서는 무발동). 200자 절단을 흉내 내는 이유 둘: (1) 나중에 오는
호스트 값과 같아 화면이 깜박이지 않는다(94.7%) (2) hub.html 에 실리는 프롬프트 양이 오늘(호스트 201자)과 같다 — 400자로
늘리지 않는다. 원문 전체를 **자르기 전에** 스크럽하므로 PS9 의 잔존 위험(호스트 절단 경계에 걸린 시크릿)이 유도
경로에서는 사라진다. `last-prompt` 경로는 오늘과 한 글자도 같다.
→ **구현 정정(M1)** — 「원문 전체」가 아니라 **앞 2,000자**를 스크럽한다(검수 MEDIUM — §6.4 이탈 모음·GOTCHA 11). 화면에 나가는
앞 200자는 여전히 절단 전에 스크럽된다. 창 끝(2,000자 경계)에 걸려 잘린 시크릿 조각은 스크럽 결과가 짧게 접히면 화면에 닿을 수 있어,
잘린 창의 결과가 화면 + 조각 상한보다 짧으면 끝 낱말을 버린다(낱말이 하나뿐이면 유도 포기 — 검수 LOW-A).

#### TF5. 바꾸지 않는 것

훅(`hub_hook.py`) · 서버 · `hub_collect.read_session_tails`(`record_prompt_excerpt:false` 면 `last_prompt=None` — 유도값도
같이 버려진다) · 템플릿의 발췌 렌더와 방어 필터 `displayableExcerpt`(PS6) · 폴링 60초 · 신선도 창 2초.

### 요구 ① — 재개된 실행의 제목

#### TF6. 한 줄 = 에이전트 1개 — 오늘의 계약을 유지한다 (안 C 기각)

경과는 마지막 재개부터(오늘과 같다), 제목만 그 재개의 것으로. 「재개마다 한 줄」(안 C)은 기각: (1) `SessionFacts` 계약이
실행 1건 → 구간 목록으로 바뀌고 좀비·생존 판정(ZG·SL)·정렬(K2)·DOM 키(`agent_id` 가 더는 유일하지 않다)를 모두 다시 짜야
한다 (2) 옛 구간의 시작 시각은 meta.json mtime 이 덮여 훅 값밖에 없다 (3) 5줄 상한(AR11)을 한 에이전트의 회차가 먹어
다른 실행이 「+N건 더」로 밀린다 — 이 세션을 재현한 목업(§14 ①④)에서 설계 줄이 사라진다.

#### TF7. 재개 횟수 = 같은 `agent_id` 의 `SubagentStart` 재발화 수 → `SubagentFact.resume_count`

`_handle_subagent_start` 가 기존 항목이 있으면 `resume_count + 1`, 없으면 0 으로 새 항목을 만든다(덮어쓰기 자체는 그대로).
훅 사실만으로 계산되므로 `SessionFacts`(훅 이벤트 → 사실) 계약 안이다(AR1). 새 훅 필드 0. 이벤트 창(오늘+어제) 밖에서
띄워진 실행은 창 안 재개만 센다(과소 집계) — 첫 띄움까지 창 밖이면 창 안 첫 재개를 띄움으로 보아 그 재개의 제목은
찾지 않는다(이틀 넘게 이어진 에이전트 — 원래 제목으로 남는다).

#### TF8. 재개 제목 = `SendMessage` tool_use `input.summary` ⋈ 같은 tool_use_id 의 `toolUseResult.resumedAgentId`

- 짝은 **결과의 `resumedAgentId`** 로 맺는다 — `to` 가 아니다(이름으로 보낼 수 있고, 「Message queued」 전달은 재개가 아니다).
- 에이전트마다 **파일상 마지막 재개 1건**이 확정값이다. 그 재개에 `summary` 가 없거나 비었으면 그 에이전트는 제목 없음
  → `description` 폴백. **더 옛 재개의 요약으로 대체하지 않는다**(옛 작업 이름이 새 작업을 가리키는 오늘의 결함을
  다른 모양으로 되살리지 않는다).
- 한 줄에 `tool_result` 블록이 정확히 1개일 때만 매핑한다(방어 — `toolUseResult` 는 줄 단위라 여럿이면 누구 것인지 모른다).

#### TF9. 읽기 범위 — 재개된 실행이 있는 세션만, 부모 기록 끝 **최대 8MiB** 1회

- 트리거: 그 세션의 추적 실행 중 `resume_count ≥ 1` 이고 meta 를 읽은 것이 있을 때만. 없으면 파일을 열지 않는다(대부분의
  세션 증분 0).
- 경로: `read_session_tail` 과 같은 규칙 — `observed_cwds` 순으로 `PROJECTS_DIR/<인코딩>/<session_id>.jsonl` 을 조립,
  먼저 존재하는 파일(E13 규칙; 호스트의 파일 이전(§2.4)에도 맞다). 조립 전 `session_id` 안전성 검사(C-7).
- 읽기: `seek(max(0, size − RESUME_TITLE_SCAN_MAX_BYTES))` 한 번 + `errors="replace"` 디코딩(GOTCHA 7), 파서는 대상이
  모두 정해지면 멈춘다. → **구현 정정(M2)**: 창은 디코딩하지 않고 `bytes` 로 넘긴다 — 파서가 재개 표지를 품은 줄만 골라 그 줄만
  `errors="replace"` 로 디코딩한다(§2.1 「구현 정정(M2)」).
- **8MiB 의 근거**: 가장 바쁜 날의 이 세션(14MB, 약 1.4MB/h)에서 22:30 기준 화면에 보이는 재개 실행 4건의 요청 줄이 끝에서
  0.5~2.4MB, 같은 날 재개된 6개 에이전트의 **마지막** 재개 요청 전부가 3.1MB 안(더 옛 재개 요청은 필요 없다) —
  8MiB 는 그 2.6배(약 5~6시간치). 비용: 조기 종료 5ms 안팎, 최악(끝까지
  훑음) 11~17ms. 범위 밖의 오래된 재개는 원래 제목으로 돌아간다(툴팁에 재개 횟수는 남는다).
  → **실측 갱신(M2)**: 설계 인터페이스(str 창)로는 세션당 15ms·`collect_snapshot` 52ms 였고, bytes 창으로 고친 뒤 세션당 **2.7ms(최악 3.4ms)**,
  재개 세션 3개의 `collect_snapshot` **20ms** 다(§2.1 표). 에스컬레이션 조건(`collect_snapshot` 50ms 초과)은 그대로 유효하다.
- 캐시를 두지 않는다(MD4·WF10 판단 유지). **에스컬레이션 조건**: 재개 세션이 여럿이라 `collect_snapshot` 이 50ms 를 넘기면
  `(경로, 크기, mtime)` 키 캐시를 재검토한다.
- 경고를 돌려주지 않는다(SL8 과 같은 이유 — 실패와 정상 부재의 결과가 같다: 폴백 = 오늘의 제목).

#### TF10. 계약 A · PS7 게이트 — `description` 과 완전히 같은 취급

재개 제목은 `hub_subagent._scrubbed_and_clipped`(스크럽 + `SUBAGENT_TITLE_MAX_CHARS` 120)를 거친다(요약 실측 max 50자).
`record_prompt_excerpt:false` 면 meta.json 과 함께 읽지 않는다 — 보강이 `read_subagent_metas` 의 조기 반환 **뒤에**
있으므로 게이트를 구조적으로 물려받는다(TF13). 메시지 본문(`message`)은 줄을 풀 때 메모리에 올라오지만 어디에도 싣지 않는다.

#### TF11. 뷰 — `SubagentRunView` 에 `resume_title`·`resume_count` 추가, `title` 의 뜻은 그대로

`title` 은 계속 `meta.description`(AR9 무변경). 새 필드 둘은 맨 뒤·기본값(`None`·`0`) — 기존 생성 지점 무해, 필드 순서를
무는 검사 없음(SubagentRunView 주석). 둘 다 **정적 값**이라 `snapshot_content_key` 를 흔들지 않는다(D2 안전).

#### TF12. 화면 — 제목 우선순위 `resume_title → title → agent_type`, 툴팁에 재개 표시 (안 A 권고)

- `agentRunDisplayTitle` 한 줄 개정. 호출부 `escapeHtml(agentRunDisplayTitle(run))`(T25-11)는 그대로.
- `agentRunTooltipText`: 재개된 실행이면 시작 라벨을 「재개 HH:MM」으로(오늘도 그 시각은 마지막 재개였는데 「시작」이라
  적혀 오해를 샀다) 하고 끝에 「 · 재개 N회」를 붙인다. `run.is_running` 참조를 늘리지 않는다(T25-93 = 3).
- 보이는 표식(안 B: 경과 칸 앞 「재개 N회 · 」)은 선택지 — 320px 에서 제목이 더 잘린다(목업 ②). 「N회차」라는 말은 쓰지
  않는다 — 워크플로우의 「검수 N회차」(재검수 왕복)와 헷갈린다(이 세션의 재개는 재검수가 아니라 다음 마일스톤이었다).

#### TF13. 배치 — 파서는 `hub_subagent.py`, 보강은 `read_subagent_metas` 안, 값은 `SubagentMeta.resume_title`

- **훅 사실은 `SessionFacts`(resume_count), 호스트 파일 보강은 `SubagentMeta`(resume_title)** — 기존 두 계약의 경계에
  그대로 얹힌다. `SubagentMeta` 를 「meta.json 1건의 투영」에서 「실행 1건의 호스트 기록 투영(meta.json + 마지막 재개
  요청)」으로 docstring 을 넓힌다.
- 그 덕에 `hub_collect._read_session_annotations`·`hub_project.compose_project_views`·`_project_view_for_path`·
  `_session_views_for_path`·`compute_session_view` 시그니처가 **전부 무변경**이다(보강 맵을 5개 함수에 흘리는 안 대비).
  `summarize_agent_runs` 는 이미 받는 `meta` 에서 `resume_title` 을, `sub` 에서 `resume_count` 를 읽는다.
- T25-206(계약 A 산술: `SubagentMeta` 문자열 필드 수 == 파일 안 `_scrubbed_and_clipped(`·`_metadata_field(` 호출 줄 수)이
  **재조준 없이** 성립한다 — 필드 4(title·agent_type·model·resume_title) == 호출 4(parse_subagent_meta 3 + parse_resume_titles
  1). 스크럽을 빼먹으면 3 ≠ 4 로 기존 가드가 잡는다(주석만 갱신).
- PS1 의 「같은 외부 계약이면 같은 모듈」 기준의 예외다: `SendMessage` 줄은 부모 transcript 의 줄이지만 (1) 뽑는 것이 실행
  제목(계약 A 의 유일한 거처가 `hub_subagent.py`) (2) 창(8MiB)·게이트(`record_prompt_excerpt`)·트리거(재개 있을 때만)가
  `hub_transcript` 의 꼬리 스캔(128KiB, 항상)과 모두 다르다. `hub_transcript` 에 두면 제목 상한 상수를 사본으로 두거나
  모듈 간 임포트가 늘어난다.
- 부모 기록 창 읽기(seek+read+decode 10줄)는 `hub_subagent_read.py` 에 작은 사본으로 둔다 — `hub_collect._read_transcript_tail`
  을 쓰려면 `hub_subagent_read → hub_collect` 순환이 생긴다(모듈 머리 주석이 이미 같은 이유로 `PROJECTS_DIR` 을 인자로 받는다).

### 공통

#### TF14. 문서·가드·원장

- README 3곳(발췌 정의·프라이버시 고지 2항목·실행 줄 설명) + 「알려진 한계」 2줄, PRP 2개 이관 표기(§10).
- 가드 신설 2: **T25-260**(README 발췌 서술 정합 — 새 규칙·원인 토큰, 옛 정의문 부재) · **T25-261**(README 의 재개 요약
  읽기 상한 == `RESUME_TITLE_SCAN_MAX_BYTES`, 고지가 `SendMessage`·`summary` 를 말함). T25-206 은 주석만 갱신. 하한 515 → 517.
- 새 가드가 없는 부분은 단위·DOM 검사가 문다: 유도 규칙(H), 파서(S), 게이트·예산(R), 뷰(V), 화면(D).

#### TF15. 기각안

| 안 | 요구 | 기각 이유 |
|---|---|---|
| 훅이 수집을 몇 초 늦게 한 번 더 띄운다 | ② | 서버가 살아 있으면 훅은 수집하지 않는다. 늦춰도 `last-prompt` 는 수십 초 뒤에나 쓰인다 |
| 서버가 요청 때 오래된 스냅샷이면 잠깐 기다렸다 다시 수집 | ② | 기다릴 대상이 파일에 없다(중앙 22.8초). 응답만 느려진다 |
| 새로고침 직후 빠른 재폴링·폴링 주기 단축 | ② | 같은 이유. 주기 단축은 SH2 비용 분석을 다시 연다 — Q3 에서 선택지로만 |
| 훅이 프롬프트 발췌를 다시 적는다(PS4 되돌리기) | ② | 무자유텍스트 원칙·7일 보관 사본 부활 |
| 유도값을 200자로 자르지 않고 400자까지 | ② | hub.html 에 싣는 프롬프트 양이 늘고 호스트 값과 달라 깜박인다 |
| 서브에이전트 기록의 재개 턴 첫 줄을 제목으로 | ① | 요약이 없고 첫 줄이 115~458자 본문(오케스트레이터 지시 전문 — 사용자 프롬프트 인용 가능), 파일 7MB 까지·재개 턴이 끝에서 멀다 |
| 훅(PreToolUse SendMessage)이 요약을 기록 | ① | 무자유텍스트 원칙 위반 |
| 128KiB 꼬리만 본다 | ① | 캡처한 순간 실패(210KB), 끝난 실행은 곧 원래 제목 |
| 시각 기준 이분 탐색으로 요청 줄을 찾는다 | ① | 압축 재삽입이 시각 단조성을 깬다(§11 GOTCHA 7). 복잡도 대비 이득(8MiB 선형 5~17ms)이 없다 |
| 찾은 제목을 캐시 파일에 남긴다 | ① | 새 상태·새 자유 텍스트 사본·무효화 경로. MD4 조건 미도달 |
| 보강 맵을 별도 인자로 5개 함수에 흘린다 | ① | TF13 이 같은 결과를 시그니처 무변경으로 낸다 |
| 재개마다 한 줄(안 C) | ① | TF6 |

---

## 4. 영향 범위

| 파일 | 변경 | 결정 | 마일스톤 |
|---|---|---|---|
| `hub/bin/hub_transcript.py` | 호스트 규칙 상수 6개 · `_human_prompt_text`·`_derived_last_prompt`·`_last_prompt_candidate` 신설 · `parse_session_tail` 이 후보 함수를 경유(50줄 유지) · 모듈·`SessionTail` docstring | TF1~TF4 | M1 |
| `tests/hub/test_hub_transcript.py` | `ParseSessionTailHumanPromptTest`(H1~H19) | TF1~TF4 | M1 |
| `tests/hub/test_hub_collect.py` | 게이트 확인 1건(유도값도 `record_prompt_excerpt:false` 에 버려짐) | TF5 | M1 |
| `hub/bin/hub_session_facts.py` | `SubagentFact.resume_count`·`_MutableSubagent.resume_count` · `_handle_subagent_start` 증가 · `_freeze_session` 전달 | TF7 | M2 |
| `hub/bin/hub_subagent.py` | `SubagentMeta.resume_title` · 재개 요청 상수 · `parse_resume_titles`(+ 사적 헬퍼 2) · docstring(계약 A 경로에 resume_title 추가) | TF8·TF10·TF13 | M2 |
| `hub/bin/hub_subagent_read.py` | `RESUME_TITLE_SCAN_MAX_BYTES` · `_parent_transcript_path`·`_read_parent_transcript_window`·`_with_resume_titles` · `read_subagent_metas` 가 세션별로 보강 | TF9·TF10·TF13 | M2 |
| `hub/bin/hub_session.py` | `SubagentRunView.resume_title`·`resume_count` · `summarize_agent_runs` 가 두 값을 채움 | TF11 | M2 |
| `tests/hub/test_hub_session_facts.py` · `test_hub_subagent.py` · `test_hub_subagent_read.py` · `test_hub_session.py` | F1~F4 · S1~S11 · R1~R7 · V1~V3 | TF7~TF11 | M2 |
| `hub/bin/hub_template.html` | 상수 3 · `agentRunResumeCountLabel` · `agentRunDisplayTitle`·`agentRunTooltipText` 개정 · 관련 주석 | TF12 | M3 |
| `tests/hub/test_hub_template_dom_resume.py`(신설) | D25~D28 | TF12 | M3 |
| `tests/run.sh` | T25-260(M1) · T25-261(M2) · T25-206 주석(M2) · `SOURCE_GUARD_ID_FLOOR` 515→516→517 + 근거 주석 | TF14 | M1·M2 |
| `tests/mutations.tsv` | T25-260·T25-261 변조행 | TF14 | M1·M2 |
| `hub/README.md` | 발췌 정의·프라이버시 고지(M1) · 재개 요약 고지(M2) · 실행 줄 제목·툴팁(M3) · 알려진 한계 | TF14 | M1~M3 |
| `docs/prps/hub-agent-runs-and-prompt-source.md` · `docs/prps/hub-tier1-clamp-fix-and-session-model.md` | 이관 표기(§10.2) | TF14 | M1~M3 |
| **무변경** | `hub_hook.py`·`hub_collect.py`·`hub_project.py`·`hub_server*.py`·`hub_model.py`·`commands/hub.md`·상시 컨텍스트(T26 무관) | TF5·TF13 | — |

파일 크기(추정, 800 상한): transcript 308→약 390 · subagent 125→약 195 · subagent_read 187→약 225 · session 586→약 596 ·
facts 398→약 405 · 템플릿 +15.

---

## 5. 파일 구조와 모듈 경계

```
                        (호스트 소유, 읽기 전용)
 부모 transcript <sid>.jsonl ─┬─ 꼬리 128KiB ──────────► hub_transcript.parse_session_tail   ★순수  (TF1~TF4)
                              │                            └ SessionTail.last_prompt = 사람 줄 유도값 | last-prompt
                              └─ 끝 ≤8MiB(재개 있을 때만) ─► hub_subagent.parse_resume_titles     ★순수  (TF8·TF10)
 subagents/agent-<id>.meta.json ──────────────────────────► hub_subagent.parse_subagent_meta      ★순수
 hub/events/*.jsonl ──► hub_session_facts.build_session_facts ★순수  SubagentFact.resume_count (TF7)

 I/O: hub_subagent_read.read_subagent_metas  = meta 읽기(기존) → _with_resume_titles(facts, metas)  (TF9·TF13)
                                                 └ _read_parent_transcript_window → parse_resume_titles
      hub_collect.read_session_tails (무변경)

 배선(무변경): hub_collect._read_session_annotations → hub_project.compose_project_views
            → hub_session.compute_session_view → summarize_agent_runs
                 SubagentRunView.title        = meta.title          (AR9 그대로)
                 SubagentRunView.resume_title = meta.resume_title   (TF11)
                 SubagentRunView.resume_count = sub.resume_count    (TF11)
 화면: hub_template.html agentRunDisplayTitle = resume_title || title || agent_type (TF12)
```

임포트 방향 무변경: `hub_subagent → hub_redact` · `hub_subagent_read → hub_project, hub_subagent, hub_session_facts` ·
`hub_session_facts → hub_transcript`(T25-253 — 이것만). 새 모듈 없음(DOM 테스트 모듈 1개만 신설).

---

## 6. 데이터 모델

### 6.1 `hub_session_facts.py` (★순수)

```python
@dataclass(frozen=True)
class SubagentFact:
    """서브에이전트 실행 1건."""

    agent_id: str
    agent_type: str
    started_at_ms: int          # 마지막 (재)시작 — 재개되면 그 시각으로 덮인다(오늘과 같다)
    ended_at_ms: int | None
    # 같은 agent_id 의 SubagentStart 재발화 수(결정 TF7) — 호스트는 SendMessage 재개 때도 SubagentStart 를
    # 같은 id 로 다시 낸다(훅 문서 SubagentStart). 0 = 재개된 적 없음. 맨 뒤·기본값(기존 생성 지점 무해).
    resume_count: int = 0
```

`_MutableSubagent` 에 `resume_count: int = 0`(맨 뒤).

### 6.2 `hub_subagent.py` (★순수)

```python
@dataclass(frozen=True)
class SubagentMeta:
    """실행 1건의 호스트 기록 투영 — meta.json(title·agent_type·model·started_at_ms) + 재개됐으면 부모 transcript 의
    마지막 재개 요청 요약(resume_title, 결정 TF8·TF13). 전부 계약 A 를 거친 값이다."""

    title: str
    agent_type: str
    model: str | None
    started_at_ms: int
    resume_title: str | None = None   # 스크럽 + SUBAGENT_TITLE_MAX_CHARS. 재개 아님·요약 없음·창 밖이면 None
```

상수(값의 근거는 주석에 — §2.1):

```python
RESUME_REQUEST_TOOL_NAME = "SendMessage"          # 부모 transcript 의 재개 요청 tool_use 이름
RESUMED_AGENT_ID_KEY = "resumedAgentId"          # 그 tool_result 의 toolUseResult 키 — 있으면 재개, 없으면 전달
# json.loads 전에 줄을 거르는 부분 문자열 — 창이 수 MiB 라 모든 줄을 풀면 느리다(§2.1 비용 표)
RESUME_LINE_MARKERS = ('"' + RESUMED_AGENT_ID_KEY + '"', '"' + RESUME_REQUEST_TOOL_NAME + '"')
```

> → **구현 정정(M2)** — 위 `RESUME_LINE_MARKERS`(str 튜플)는 구현에서 **bytes 상수 둘**로 나뉘었다: `RESUME_RESULT_LINE_MARKER = b'"resumedAgentId"'` ·
> `RESUME_REQUEST_LINE_MARKER = b'"SendMessage"'` (+ 줄 구분 `LINE_SEPARATOR = b"\n"`). 창을 bytes 로 들고 결과 표지 줄을 먼저, 요청 표지 줄은 풀어야 할 결과를
> 만난 뒤 그 줄 앞에서만 찾기 때문에 둘을 따로 쓴다(§2.1 「구현 정정(M2)」).

### 6.3 `hub_session.py` (★순수) — `SubagentRunView` 맨 뒤 2필드

```python
    # 재개된 실행이면 마지막 재개 요청(SendMessage)의 요약 — 계약 A. 없으면 None → 화면은 title 로 폴백(결정 TF11·TF12).
    # title 의 뜻(meta.description)은 그대로다(AR9). 정적 값 — D2 안전.
    resume_title: str | None = None
    # 같은 agent_id 의 SubagentStart 재발화 수(결정 TF7). 툴팁의 「재개 N회」. 정적 값 — D2 안전.
    resume_count: int = 0
```

### 6.4 `hub_transcript.py` (★순수) — 상수

```python
# 호스트(Claude Code 2.1.284) lastPrompt 규칙의 부분 사본(결정 TF2·TF3) — 번들의 Ztn·normalizeLastPrompt·l7t·xue 를
# 옮겼다. 어긋나면 다음 last-prompt 재부착 때 호스트 값으로 돌아온다(최악 = 오늘의 지연).
HUMAN_PROMPT_ORIGIN_KIND = "human"
# l7t — 태그로 시작하는 블록(자동주입·명령 출력)과 인터럽트 표식은 프롬프트가 아니다. JS 의 \w 는 ASCII 라 명시 클래스로 쓴다
HOST_PROMPT_SKIP_PATTERN = re.compile(r"\A(?:\s*<[a-z][A-Za-z0-9_-]*[\s>]|\[Request interrupted by user[^\]]*\])")
# 호스트가 다른 모양으로 바꿔 적는 블록(/cmd args·! cmd) — 내장 명령 목록을 모르므로 흉내 내지 않고 포기한다
HOST_PROMPT_GIVE_UP_MARKERS = ("<command-name>", "<bash-input>")
PASTED_CONTENT_OPEN_PATTERN = re.compile(r'<pasted_content id="[0-9a-f]{4}">\n')
PASTED_CONTENT_CLOSE_PATTERN = re.compile(r'\n?</pasted_content id="[0-9a-f]{4}">')
# normalizeLastPrompt 의 절단 — 이 값에서 자르고 말줄임표를 붙인다(호스트 실측 max 201 = 200 + '…')
HOST_LAST_PROMPT_MAX_CHARS = 200
```

> → **구현 정정(M1)** — 위 `PASTED_CONTENT_OPEN_PATTERN`·`PASTED_CONTENT_CLOSE_PATTERN` 은 구현에서 각각
> `\n{0,2}<pasted_content id="[0-9a-f]{4}">\n` · `\n?</pasted_content id="[0-9a-f]{4}">\n{0,2}` 로 개정했다 — 호스트 `xue` 가
> 표지 안쪽 줄바꿈뿐 아니라 바깥쪽(여는 표지 앞·닫는 표지 뒤 각 최대 2개)도 함께 벗기고 조각을 구분자 없이 잇기 때문이다.
> 원인은 절단 단위가 아니라 붙여넣기 표지 바깥 줄바꿈 흡수(§15 A2) — 패턴 개정, 14일 재생 430/453 일치·불일치 0.

> → **구현 이탈 모음(M1)** — PRP 원문과 다르게 한 것을 한 줄로: README 고친 곳이 3곳이 아니라 5곳(프라이버시 고지의 transcript
> 꼬리 항목 — 「대화 내용은 읽지 않는다」가 사람 줄 텍스트를 읽게 되어 거짓이 됐다 — 과 「실측상 … 자동주입 블록」 항목 — 「그 값을 누가
> 만드는지 허브가 모른다」가 사람 줄 경로에는 거짓이 됐다) · 상수 7개(위 6개 + `_NON_PROMPT_LINE_FLAGS`)와 헬퍼 8개 · 원장 sed 에
> `g` 플래그 · C1 에 스위치를 켠 대조 + 스냅샷 배선 통합 테스트(`CollectSnapshotExcerptWiringTest`) · **스크럽 입력 상한 2,000자**
> (`DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS` — 검수 MEDIUM, TF4·GOTCHA 11 정정) 와 그 상한의 README 고지(마스킹 시점을 경로별로) ·
> **스크럽 창 끝 조각 처리**(창이 잘렸고 스크럽 결과가 화면 + 조각 상한 `BOUNDARY_FRAGMENT_MAX_CHARS`(40)보다 짧으면 끝 낱말을 버리고,
> 낱말이 하나뿐이면 유도를 포기해 `last-prompt` 로 물러난다 — 검수 LOW-A, `_without_boundary_fragment`) · T25-260 의 4번째
> 서브체크(README 의 「앞 N자 안에서」 == 코드 상수, 새 ID·원장 행 없음).

`SessionTail` 필드는 무변경(`last_prompt` 의 **출처** 설명만 docstring 에서 넓힌다).

### 6.5 스냅샷 JSON (`#dzh-data`, `asdict` 직렬화)

`projects[].sessions[].agent_runs[]` 에 `"resume_title": str|null`·`"resume_count": int` 두 키가 붙는다. 그 밖의 키·
순서·값은 무변경. 템플릿은 두 키가 없어도(구버전 서버 + 신버전 템플릿) `undefined` 로 폴백한다 — 세대가 어긋나면
template_stamp 자가 리로드(SH6)가 먼저 수습한다.

---

## 7. 인터페이스

### 7.1 `hub_transcript.py`

```python
def parse_session_tail(tail_text: str) -> SessionTail:
    """(유지) 한 번의 역방향 스캔. 발췌는 _last_prompt_candidate 가 확정하는 첫 줄의 값이다(결정 TF1)."""

def _last_prompt_candidate(payload: dict) -> tuple[bool, str | None]:
    """이 줄이 발췌를 확정하는가(TF1) — last-prompt 줄: (True, 스크럽·클립값 | None) · 유도 가능한 사람 프롬프트 줄:
    (True, _derived_last_prompt 값) · 그 밖(유도 포기 포함): (False, None)."""

def _human_prompt_text(payload: dict) -> str | None:
    """사람이 입력한 프롬프트 줄(TF2)이면 호스트 규칙(TF3)으로 고른 블록 원문(스크럽·절단 전), 아니면 None."""

def _derived_last_prompt(raw_text: str) -> str:
    """줄바꿈→공백·strip → redact → 200자+… → LAST_PROMPT_MAX_CHARS 클립(TF4). 스크럽이 자르기보다 먼저다."""
```

### 7.2 `hub_subagent.py`

```python
def parse_resume_titles(window_text: str, wanted_agent_ids: frozenset[str]) -> dict[str, str]:
    """부모 transcript 창에서 에이전트별 **마지막** 재개 요청의 요약을 판다(결정 TF8·TF10).

    뒤에서 앞으로 훑는다 — RESUME_LINE_MARKERS 가 없는 줄은 json 으로 풀지 않는다. tool_result 줄(블록 정확히 1개,
    toolUseResult.resumedAgentId ∈ wanted)로 「tool_use_id → 재개된 agent_id」를 먼저 알고, 그보다 앞의 SendMessage
    tool_use 에서 그 id 의 input.summary 를 꺼낸다. 에이전트마다 처음 만난(가장 늦은) 재개가 확정값이다 — 그 요약이
    문자열이 아니거나 비었으면 결과에 넣지 않는다(더 옛 요약으로 대체하지 않는다). wanted 가 모두 확정되면 멈춘다.
    계약 A: 요약은 _scrubbed_and_clipped 를 **정확히 한 호출 줄**로 거친다(T25-206 산술). 계약 B: 예외를 던지지 않는다.
    """
```

사적 헬퍼(이름은 구현 재량): tool_result 줄 → `(tool_use_id, agent_id) | None`, assistant 줄 → `[(tool_use_id, summary 원값)]`.

> → **구현 정정(M2): 창·파서 입출력 `bytes`** — 위 시그니처의 `window_text: str` 은 구현에서 **`window_bytes: bytes`** 다(이유·실측: §2.1 「구현 정정(M2)」 — str 창은 세션당
> 15ms·`collect_snapshot` 52ms 로 승인된 비용 설명의 경계 밖이었고 bytes 창은 2.7ms·20ms). 알고리즘은 「뒤에서 앞으로 줄마다」가 아니라 **표지 위치 건너뛰기**다: ① 결과
> 표지 줄만 `rfind` 로 뒤에서부터 차례로 꺼내(`_lines_with_marker_backwards`) 디코딩·해석 ② 풀 대상 에이전트의 결과면 **그 줄 앞에서만** 요청 표지 줄을 같은 방식으로
> 찾아 tool_use id 가 같은 요청의 summary 를 꺼낸다(`_request_summary`) ③ 그 에이전트는 그 자리에서 확정 — 더 옛 결과 줄은 무시되고(`unsettled`), 다 확정되면 멈춘다.
> 그래서 「결과 줄 → 요청 줄 짝 대기표」가 사라졌다. 줄은 개행 **바이트**로만 가른다(UTF-8 에서 0x0A 는 다중 바이트 글자 안에 나오지 않는다 · U+2028 등은 줄 경계가
> 아니다). 표지가 없는 줄은 디코딩하지 않고, 표지 줄은 `errors="replace"` 로 디코딩해 창 머리의 찢긴 줄도 예외 없이 JSON 실패로 탈락한다. `_request_summary` 는 요청을 못 찾은
> 첫 미스 때 그 훑기가 본 요청을 `{tool_use id: (줄 시작, summary)}` 색인으로 돌려주고 파서가 이후 조회에 그 색인을 넘긴다(M2 검수 LOW-1 — 결과 수 × 요청 수로 느려지던 강등 경로를
> 묶는다; 위치 조건 「요청 줄 시작 < 결과 줄 시작」 유지, 정상 경로는 색인 없음). 또 `_scrubbed_and_clipped` 는 상한(1200자)을 넘는 글을 잘라 스크럽하지 않고 빈 제목으로 버린다(M2 검수 MEDIUM — 이탈 모음).

> → **구현 정정(M3)** — 위 요청 색인의 값 `{tool_use id: (줄 시작, summary)}` 는 구현에서 **id 별 (줄 시작, summary) 목록** `{tool_use id: [(줄 시작, summary), …]}`(줄 시작 내림차순)이 됐다
> (M2 검수 LOW): 같은 tool_use id 의 줄이 여럿일 수 있어(대화 기록 재부착 — 최근 90일 재개 요청 263건 중 44개 id 가 2~7번) 파일에서 가장 뒤의 사본 하나만 남기면, 그 사본이 자기
> 결과 줄보다 뒤이고 더 앞에 짝 사본이 있을 때 색인 경로만 제목을 잃는다(합성 재현: 요청(t1,옛) → 결과(t1→a1) → 요청(t1,새) → 짝 없는 결과(→a2) 에서 a1·a2 를 함께 찾으면 `{}`, a1 만
> 찾으면 `{a1: 옛}`). 이제 색인은 줄 시작이 bound 보다 앞인 첫 사본 — 정상 경로와 같은, 결과 줄에 가장 가까운 앞 사본 — 을 고른다(`test_the_index_answers_like_the_fast_path_even_when_a_tool_use_id_repeats`
> 네 배열로 색인 경로 == 정상 경로를 고정). 비용은 그대로다(합성 최악 결과 100 × 요청 2000줄 6.7ms · 정상 경로 조기 종료 1.8ms·최악 2.7ms 불변; 같은 id 사본 2,000개 × 결과 100 은 9.4ms —
> 사본 목록 선형 탐색은 결과(에이전트)당 한 번이라 실데이터 최대 7회 사본에서는 무시된다). 실데이터(최근 90일, 재개가 든 기록 24개 · 재개된 에이전트 90개)에서는 이전 구현도 색인 경로와 정상 경로가 같았다(갈림 0) —
> 합성 재현으로만 드러난 잠재 결함의 보강이다.

### 7.3 `hub_subagent_read.py`

```python
RESUME_TITLE_SCAN_MAX_BYTES = 8 * 1024 * 1024    # 근거 주석: §2.1 거리·비용 표 (T25-261 이 README 와 대조)

def read_subagent_metas(sessions_by_path, record_prompt_excerpt, projects_dir):   # 시그니처·반환 무변경
    """(유지) … 세션마다 읽은 meta 에 _with_resume_titles 로 재개 요약을 얹는다(결정 TF13). record_prompt_excerpt 가
    거짓이면 둘 다 읽지 않는다(PS7 — 조기 반환이 앞에 있다)."""

def _with_resume_titles(
    facts: SessionFacts, session_metas: dict[str, hub_subagent.SubagentMeta], projects_dir: Path
) -> dict[str, hub_subagent.SubagentMeta]:
    """resume_count ≥ 1 이고 meta 가 있는 실행이 없으면 파일을 열지 않고 그대로 돌려준다. 있으면 부모 기록 창을 한 번
    읽어 해당 meta 를 dataclasses.replace(meta, resume_title=…) 로 바꾼다(결정 TF9)."""

def _parent_transcript_path(session_id: str, cwd: str, projects_dir: Path) -> Path: ...

def _read_parent_transcript_window(session_id: str, observed_cwds: Sequence[str], projects_dir: Path) -> str | None:
    """observed_cwds 순으로 먼저 존재하는 <session_id>.jsonl 의 끝 RESUME_TITLE_SCAN_MAX_BYTES 를 errors="replace" 로
    디코딩해 돌려준다. session_id 가 안전한 경로 조각이 아니면 None. 절대 예외를 던지지 않는다(OSError → 다음 후보)."""
```

> → **구현 정정(M2): 창·파서 입출력 `bytes`** — `_read_parent_transcript_window` 의 반환은 `str | None` 이 아니라 **`bytes | None`** 이다: 디코딩하지 않고 창을 그대로 돌려준다
> (디코딩은 파서가 재개 표지를 품은 줄에만 한다 — §7.2 정정). 내부 읽기 헬퍼 이름도 `_read_transcript_window_text` 에서 `_read_transcript_window_bytes` 로 바뀌었다. 나머지
> (경로 조립·안전 검사·후보 순회·예외 없음)와 `read_subagent_metas`·`_with_resume_titles` 시그니처는 무변경.

### 7.4 `hub_session.py`

`summarize_agent_runs` 시그니처 무변경. `SubagentRunView(...)` 생성에 `resume_title=(meta.resume_title if meta else None)`·
`resume_count=sub.resume_count` 두 인자 추가. `compute_session_view` 무변경.

> → **구현 이탈 모음(M2)** — PRP 원문과 다르게 한 것을 한 줄로: **제목 스크럽 입력 상한**(`SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS` 1200 = 제목 상한의
> 10배, 가용성 이유는 M1 의 `DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS` 와 같다)을 새 요약 경로에만 두지 않고 **공유 헬퍼 `_scrubbed_and_clipped` 안에** 넣어 meta.json 의
> `description`(64KiB 까지 읽는다)도 함께 보호했다(TF10 「description 과 완전히 같은 취급」과 같은 방향) · **상한을 넘는 글은 잘라 스크럽하지 않고 스크럽 없이 빈 제목으로
> 버린다**(`""` → 요약이면 제목 없음, `description` 이면 타입명 폴백; 실측 제목은 max 51자라 잃는 것이 없다; 상한 이하는 기준 커밋과 같다 — 전체 스크럽 뒤 120자). 처음에는 M1 처럼
> 앞 1200자만 스크럽하고 「결과가 160자보다 짧게 접히면 빈 제목」 규칙(`SUBAGENT_TITLE_BOUNDARY_FRAGMENT_MAX_CHARS` 40)을 뒀으나, M2 검수 MEDIUM 이 재현했듯 그 규칙은 고정 길이 조각만
> 덮는다 — 서명이 창 밖인 JWT·닫는 따옴표가 창 밖인 `password="…"` 값의 머리가 마스킹되지 않은 채 제목 앞 120자로 나가 **기준 커밋(전체 스크럽 뒤 120자)보다 마스킹이 약해졌다**.
> M1 의 `last-prompt` 동치 논거(호스트 값이 같은 머리를 이미 보인다)는 description·summary 에 해당하지 않는다. 버리면 창 경계의 잔존 위험이 전부 닫히므로 조각 상수와 160 규칙은
> **삭제**했고, `hub_redact.py`·`hub_transcript.py` 의 그 상수에 대한 교차 참조를 정리했다(`hub_transcript.BOUNDARY_FRAGMENT_MAX_CHARS` 자체는 M1 경로라 유지) ·
> **요청 색인**(검수 LOW-1): 요청을 못 찾는 결과 줄이 앞의 요청 줄 전부를 매번 해석해 결과 수 × 요청 수로 느려졌다(합성 결과 100개 × 요청 2000줄에서 604ms → 6.8ms) — 첫 미스 때 그 훑기가 본 요청을
> `{tool_use id: (줄 시작, summary)}` 색인으로 남기고(다시 해석하지 않는다) 이후 조회는 색인만 본다(요청이 결과 줄보다 앞이어야 한다는 위치 조건 유지; 정상 경로는 색인 없이 그대로) ·
> **창·파서 입출력 `bytes`**(§2.1·§7.2·§7.3 「구현 정정(M2)」 — 사용자 승인 고지 「보통 5ms·최악 15ms」를 지키려는 비용 정정, 거동 불변) · `parse_resume_titles` 는 줄을
> `splitlines()` 가 아니라 **개행 바이트로만** 가른다(JSON 문자열 안의 U+2028 등에서 갈라 줄을 찢는다) · 사적 헬퍼 8개
> (`_json_object_or_none`·`_lines_with_marker_backwards`·`_content_blocks`·`_resumed_agent_of_result_line`·`_resume_requests_of_assistant_line`·`_resume_summary_title`·
> `_resume_requests_backwards`·`_request_summary`)와 I/O 쪽 추가 2개(`_read_transcript_window_bytes`·`_read_session_metas`) · 요약 스크럽의 한 호출 줄(T25-206 산술)은 `_resume_summary_title` 안에 있다 ·
> T25-261 은 서브체크 2개(① 「끝에서 최대 N MiB」 == 코드 상수 ② 그 수가 든 **같은 불릿**(고지 문단)이 `SendMessage`·`요약(summary)` 를 말한다 — 검수 LOW-2: README 전체에서 찾으면 「알려진 한계」
> 문단이 같은 토큰을 말해 고지에서 지워도 통과했다), 원장 행은 ① 만 문다(sed 는 이스케이프 없는 `s/RESUME_TITLE_SCAN_MAX_BYTES = 8 /… = 16 /`) · 테스트는 F·S·R·V 에 더해
> **스냅샷 배선 통합 테스트**(`CollectSnapshotResumeTitleWiringTest` — `collect_snapshot()` 을 훅 이벤트 + meta.json + 부모 transcript 입력부터, 배선 무변경 주장을 문다)와
> 공용 픽스처 모듈 `tests/hub/resume_transcript_fixtures.py`(세 테스트 파일이 같은 줄 모양을 쓴다), 그리고 상한·색인 경계 테스트 파일 `tests/hub/test_hub_subagent_bounds.py`
> (`test_hub_subagent.py` 가 800줄 상한에 가까워 나눴다; 기존 `test_oversized_description_is_clipped_to_120_chars` 는 입력을 상한 길이로 바꿨다 — 5000자 입력은 이제 버려지는 경우다) ·
> README 는 서브에이전트 항목(고지 본문 + 「뿐」 문구 보정)·꼬리 항목(별도 읽기 안내 한 줄)·알려진 한계 두 항목(검색 범위·요약 없음 / **훅 이벤트 창 밖에서 처음 띄운 에이전트는 재개 횟수가 모자라게 세어져
> 새 작업 이름을 찾지 않는다 — TF7 의 한계**)을 고쳤다 · M1 검수가 넘긴 것: `BOUNDARY_FRAGMENT_MAX_CHARS` 주석(「고정 길이 패턴 조각」 + 잔존
> 위험에 잘린 JWT 머리)·`hub_redact` 역참조 주석 · **미착지: 잘린 JWT 끝 마스킹** — 호스트의 `last-prompt` 값(200자에서 자른 값)이 같은 이유로 같은 머리를
> 이미 보이고 곧 이 값을 덮으므로 여기서만 마스킹해도 지속되는 이득이 없다(`last-prompt` 경로까지 고치는 것은 별건 보안 항목).

---

## 8. 렌더링 (`hub_template.html`, 안 A 기준)

```js
  var AGENT_RUN_RESUMED_AT_LABEL = '재개';          // 재개된 실행의 툴팁 시각 라벨(시작 시각이 곧 마지막 재개 시각이다)
  var AGENT_RUN_RESUME_COUNT_PREFIX = '재개 ';
  var AGENT_RUN_RESUME_COUNT_SUFFIX = '회';         // 「N회차」가 아니다 — 워크플로우의 검수 회차와 헷갈린다(결정 TF12)
  function agentRunResumeCountLabel(run){
    return AGENT_RUN_RESUME_COUNT_PREFIX + run.resume_count + AGENT_RUN_RESUME_COUNT_SUFFIX;
  }

  // 실행 목록의 제목(결정 AR9 → TF12) — 재개된 실행이면 마지막 재개 요청의 요약, 아니면 meta.description, 없으면
  // agent_type. 빈 줄을 만들지 않는다.
  function agentRunDisplayTitle(run){
    return run.resume_title || run.title || run.agent_type;
  }

  // agentRunTooltipText — 재개된 실행: "code-reviewer · 검수 단계 · sonnet · 재개 16:57 · 진행 중 · 재개 2회"
  //                       그 밖(오늘과 같다): "… · 시작 16:57 · 진행 중"
```

`renderAgentRunRow`·`renderAgentRunList`·CSS 는 무변경(안 A). 안 B 를 고르면 `renderAgentRunRow` 의 경과 칸만
`(재개면 agentRunResumeCountLabel(run) + ' · ' : '') + agentRunElapsedLabel(run, nowMs)` 로 바뀐다(새 CSS 0). 시제품
(스크래치 `freshness/mock/proto_a.html`·`proto_b.html`)에서 `run.is_running` 참조 수 3 유지 확인.

> → **구현 이탈 모음(M3)** — PRP 원문과 다르게 한 것을 한 줄로: 템플릿은 위 §8 그대로다(상수 셋 · `agentRunResumeCountLabel` · 제목 사슬 `resume_title → title → agent_type` · 툴팁 「재개 HH:MM … · 재개 N회」, 새 CSS·새 색 토큰 0,
> `run.is_running` 참조 수 3 유지) — 다만 `agentRunResumeCountLabel` 을 상수 옆이 아니라 쓰는 `agentRunTooltipText` 바로 앞에 뒀고(함수는 함수끼리), 재개 판정은 `run.resume_count > 0` 하나다(두 필드를 싣기 전 서버의
> 페이로드는 `undefined > 0` 이라 오늘 문구 그대로 — §6.5) · **DOM 검사가 표의 4건(D25~D28)이 아니라 9건**이다(`test_hub_template_dom_resume.py` 신설: D25 제목(카드·상세보기) · D25 경과 칸은 경과 시간뿐 —
> 승인된 안 A 를 고정(안 B 를 들이는 변조를 잡는다) · D25 폴링으로 같은 에이전트가 또 재개되면 같은 줄이 제자리에서 새 제목·새 툴팁·실행 중 표시로 바뀐다 — 사용자가 본 M2→M3 장면 · D25 가장 좁은 카드에서 긴
> 재개 요약이 한 줄 말줄임으로 줄 안에 머문다 · D26 요약 없는 재개는 설명 → 타입명 · D26 키 없는 구버전 서버 페이로드는 재개된 실행까지 오늘 화면 그대로 · D26 재개된 적 없는 줄 마크업은 두 필드 유무와 무관하게
> 한 글자도 같다 · D27 · D28). RED: 수정 전 템플릿에서 새 동작을 묻는 5건(D25 제목·폴링·좁은 카드, D27, D28)이 실패하고, 나머지 4건(D26 3건 · 경과 칸)은 오늘 동작을 고정하는 특성화 검사라 수정 전후 모두 통과한다.
> 템플릿 변조 9종(제목 무시·순서 뒤집기·툴팁 라벨·횟수 누락·재개 판정 두 갈래·「회차」·이스케이프 제거·경과 칸 횟수)은 전부 잡는다 · **가장 좁은 카드 검사는 창 폭이 아니라 카드 트랙을 320px 로 묶는다** — 헤드리스 Chrome 창은 `--window-size=320` 에서도 innerWidth 가 500 이다(실측 320·360·500 모두 500) ·
> **M1 이월**: 템플릿 주석 3곳(발췌 출처 — 사람 입력 줄 경로와 `last-prompt` 경로 둘) · **M2 검수 이월 LOW 2건**: 요청 색인의 값을 id 별 (줄 시작, summary) 목록으로(§7.2 구현 정정 M3) · README 「알려진 한계」 TF7 문구에
> 「창 안에서 시작 이벤트가 하나뿐이면」 조건(시작 이벤트 앞에 종료 이벤트가 먼저 보이면 앞선 시작이 있었다고 보아 재개로 센다는 F3 까지) · 정적 가드 신설 없음(PRP 와 같다) — T25-11·201·93 은 그대로 통과 · 화면 대조:
> 같은 합성 페이로드·같은 다섯 장면(§14)을 안 A 시제품과 구현으로 구워 스크립트 실행 뒤 DOM 이 글자 단위로 같음을 확인했다 · 이관 표기: `hub-agent-runs-and-prompt-source.md` AR9 개정 화살표(§10.2).

---

## 9. 테스트 계획

`bash tests/run.sh` · `python3 -m unittest discover -s tests/hub -t .` · `python3 -m py_compile hub/bin/*.py` ·
`bash -n install.sh && bash -n hub/install.sh`(정본, CLAUDE.md §4). 파이썬 임포트는 `-B`(`__pycache__` 가 T22-138 을
흔든다). TDD 순서: 각 마일스톤의 표를 먼저 빨갛게.

### 9.1 `test_hub_transcript.py` — 발췌 유도 (M1, ★순수 입력→출력)

픽스처: `_human_line(text | blocks, **overrides)`(`origin:{"kind":"human"}` 기본) · 기존 `_last_prompt_line`·`_assistant_line`.

| ID | 입력 꼬리(파일 순서) | 기대 `last_prompt` |
|---|---|---|
| H1 | LP("옛") → human("새") | "새" — **요구 ② 회귀 검사** |
| H2 | human("새") → LP("새") | "새"(LP 가 확정 — 두 경로 같은 값) |
| H3 | human("새")만 | "새" |
| H4 | LP("옛") → origin 없는 user("새") | "옛"(TF2 — 구버전 호스트) |
| H5 | LP("옛") → user origin task-notification / coordinator | "옛" |
| H6 | LP("옛") → human 이지만 isMeta / isSidechain / isCompactSummary | "옛" |
| H7 | LP("옛") → tool_result user 줄 | "옛" |
| H8 | human([text `<ide_opened_file>…`, text "본문"]) | "본문"(l7t 건너뜀) |
| H9 | human([text "[Request interrupted by user]", text "다시"]) | "다시" |
| H10 | LP("옛") → human("A") → human(`<command-name>/x</command-name>…`) | "A"(포기 줄 건너뛰고 더 앞 사람 줄) |
| H11 | LP("옛") → human(`<bash-input>ls</bash-input>`) | "옛" |
| H12 | human(`<pasted_content id="1a2b">\n붙인 글\n</pasted_content id="1a2b">`) | "붙인 글" |
| H13 | human("줄1\n줄2" + 긴 본문 300자) | 호스트식: 줄바꿈→공백, 앞 200자(strip)+"…" — 기대값은 **독립 계산 리터럴**(순환 검증 방지) |
| H14 | human(시크릿이 180~230자 경계에 걸침) | 결과에 시크릿 접두 없음(스크럽이 절단보다 먼저 — `test_scrubbing_happens_before_clipping_not_after` 와 같은 판별력 설계: 순서를 뒤집으면 실패해야 한다) |
| H15 | human(문자열 content) | 그대로 |
| H16 | human([image, text "그림 설명"]) | "그림 설명" |
| H17 | human(이미지만) → 앞에 LP("옛") | "옛"(텍스트 없음 = 포기) |
| H18 | error 줄 → human("새") | turn_failure None(대화 줄 판정 무변경) · 모델 탐지 무변경 · last_prompt "새" |
| H19 | 첫 줄이 잘린 human 줄(꼬리 경계) → LP("옛") 없음 | None(깨진 JSON 탈락) |

`test_hub_collect.py` C1: 꼬리에 human 줄만 있는 기록 + `record_prompt_excerpt:false` → `read_session_tails` 결과의
`last_prompt is None`(유도값도 버려진다, TF5).

### 9.2 M2 — 사실·파서·읽기·뷰

| ID | 대상 | 케이스 | 기대 |
|---|---|---|---|
| F1 | `build_session_facts` | Start(a) → Stop(a) → Start(a) | resume_count 1 · started = 둘째 Start · ended None |
| F2 | 〃 | Start·Stop 을 세 번 | resume_count 2 |
| F3 | 〃 | Stop(a, agent_type 있음, Start 없음) → Start(a) | 첫 항목 0 → 재개 1(Stop 은 앞선 Start 를 뜻한다) |
| F4 | `SubagentFact(...)` 4인자 생성 | resume_count 0(하위 호환) |
| S1 | `parse_resume_titles` | SendMessage(id=u1, summary S) → result(u1, resumedAgentId=a) | {a: S} |
| S2 | 〃 | 같은 a 에 재개 2쌍(S_old, S_new) | {a: S_new} |
| S3 | 〃 | result 에 resumedAgentId 없음(「Message queued」) | {} |
| S4 | 〃 | 최신 재개의 summary 없음/빈 문자열/비문자열 + 더 옛 쌍 S_old | {}(옛 요약으로 대체 안 함) |
| S5 | 〃 | tool_use 만(결과가 창 밖 뒤쪽이 아니라 아직 없음) / 결과만(tool_use 가 창 앞에서 잘림) | {} |
| S6 | 〃 | resumedAgentId ∉ wanted | {} |
| S7 | 〃 | summary 에 시크릿 · 130자 | 마스킹 · 120자+"…"(스크럽 → 자르기) |
| S8 | 〃 | 깨진 JSON·잘린 첫 줄·비 dict·content 비리스트·4,300자리 정수·깊은 중첩 | 예외 없음(계약 B) |
| S9 | 〃 | tool_result 블록 2개인 줄 | 매핑 안 함 |
| S10 | 〃 | `to`="reviewer"(이름) · resumedAgentId=a | {a: S}(짝은 결과로) |
| S11 | 〃 | toolUseResult 가 문자열(도구 비활성 오류) | {} |
| R1 | `read_subagent_metas` | 재개 없는 세션 | `_read_parent_transcript_window` 미호출(`mock.patch.object` + `assert_not_called`) |
| R2 | 〃 | `record_prompt_excerpt=False` + 재개 있음 | ({}, ()) · 창 읽기 미호출 |
| R3 | 〃 | 임시 PROJECTS_DIR 에 meta + 부모 기록(쌍 포함) | 해당 meta.resume_title = S, 나머지 meta 무변경 |
| R4 | 〃 | `RESUME_TITLE_SCAN_MAX_BYTES` 를 작은 값으로 바꾸고 쌍을 그보다 앞에 둔다 | resume_title None(창 밖 — 파일 전체를 읽지 않는다는 행동 증거) |
| R5 | 〃 | 부모 기록이 둘째 observed_cwd 에만 있다(호스트 이전) | 찾는다 |
| R6 | 〃 | session_id 가 `..`·`/` 포함 | 읽지 않음 |
| R7 | 〃 | 부모 기록 열기 OSError | meta 그대로, 예외 없음 |
| V1 | `summarize_agent_runs` | meta.resume_title=S, sub.resume_count=2 | view.resume_title S · resume_count 2 · **title = description 그대로** |
| V2 | 〃 | meta 없음 · resume_count 1 | resume_title None · resume_count 1 |
| V3 | 〃 | 재개 필드가 있어도 정렬(K2)·is_running·is_previous_task 무변경 | 기존 기대 그대로 |

### 9.3 M3 — DOM 행동 검사 (`test_hub_template_dom_resume.py`, `template_dom_harness`)

| ID | 검사 |
|---|---|
| D25 | resume_title 이 있는 실행: 카드 목록과 카드 상세보기 둘 다 `.agent-run-title` 텍스트 == resume_title |
| D26 | resume_title 이 null/키 없음: 오늘의 폴백 사슬(title → agent_type) 그대로 |
| D27 | 툴팁(`data-tooltip`): resume_count 2 → 「재개 HH:MM」·끝 「 · 재개 2회」 · resume_count 0 → 「시작 HH:MM」·「재개」 없음 |
| D28 | resume_title 에 `<img src=x onerror=…>` → 텍스트로만(요소 0개) — T25-11 과 이중 방어 |

### 9.4 정적 가드 (`tests/run.sh` T25, `test_hub_docs_and_constants`)

| ID | 마일스톤 | 무엇을 문다 | 원장 변조행(8열 — sed 는 `s/…/…/`, `mutation_sed_is_write_safe` 통과 형태) |
|---|---|---|---|
| **T25-260**(신설) | M1 | 정: `hub/README.md` 에 발췌 새 규칙 토큰(예: `사람이 입력한 프롬프트 줄`)과 원인 토큰 `32KiB` 가 있다. 역: 옛 정의문 조각 ``프롬프트(`last-prompt`)다`` 가 없다 | 대상 `hub/README.md` · 원인 토큰을 지우는 sed(예: `s/32KiB/32 KiB/`) · expect_token = 이 가드의 note_failure 문구 고유 조각 · anchor `test_hub_docs_and_constants` |
| **T25-261**(신설) | M2 | `hub_subagent_read.py` 의 `RESUME_TITLE_SCAN_MAX_BYTES = N * 1024 * 1024` 에서 N 을 뽑아 README 에 `NMiB` 가 있고, 같은 README 가 `SendMessage`·`summary` 를 말한다(교차 파일 동치 — 읽는 범위를 바꾸면 고지도 바꿔야 한다) | 대상 `hub/bin/hub_subagent_read.py` · `s/RESUME_TITLE_SCAN_MAX_BYTES = 8 \* 1024 \* 1024/RESUME_TITLE_SCAN_MAX_BYTES = 16 * 1024 * 1024/` · 〃 |
| T25-206(주석만) | M2 | 논리 무변경. 주석의 「필드 4개(title·agent_type·model·started_at_ms)」를 「문자열 필드 4(…·resume_title) == 헬퍼 호출 4(parse_subagent_meta 3 + parse_resume_titles 1)」로 갱신 | 기존 변조행 그대로 — M2 뒤 미러 실행으로 여전히 발화(3 ≠ 4)하는지 확인 |

- 두 신설 행의 expect_token 은 `tests/run.sh` 실패 보고 줄 중 1건만 등장해야 한다(T37-13). T37 미러 실행으로 각 행이 실제로
  실패를 만드는지 확인한다.
- `SOURCE_GUARD_ID_FLOOR`: M1 515 → 516, M2 516 → 517. 근거 주석은 기존 형식 그대로(「515 → 516(hub-agent-title-and-
  excerpt-freshness.md M1, 결정 TF1·TF14 — 신규 가드 1건: T25-260 …). collect_guard_ids 를 그대로 재현해 편집 후 재측정한
  실측치다(516).」). `LEDGER_EXEMPT_ROW_RATCHET`(373)·`NOTE_FAILURE_ID_LESS_RATCHET`(103) 무변경(신설이 모두 변조행·ID 있음).
- 이 변경이 **그대로 통과해야 하는** 기존 가드(M 마다 확인): T25-11(제목 escapeHtml 호출부) · T25-201(툴팁 호출부·함수 존재) ·
  T25-93(`run.is_running` 3 · zombie 기본 인자 2) · T25-92/207/208/222/225(`summarize_agent_runs` 본문) · T25-150/205(★순수
  부분 문자열) · T25-224(생존 신호 호출 줄) · T25-253(facts 임포트) · T25-120(`displayableExcerpt`).

---

## 10. 문서 개정

### 10.1 `hub/README.md`

| 위치 | 개정 | M |
|---|---|---|
| 「프라이버시 고지」 첫 항목(발췌) | 「transcript 꼬리의 마지막 **사람이 입력한 프롬프트 줄**을 호스트와 같은 규칙으로 200자까지 줄여 보여 준다 — Claude Code 는 그 값을 `last-prompt` 로 옮겨 적기는 하지만 대화 기록이 **32KiB** 쯤 더 쌓여야 다시 적기 때문이다(그 전에는 이 줄이, 그 뒤에는 `last-prompt` 가 발췌가 된다)」 · 「추가로 읽는 파일이 없다」·마스킹이 자르기보다 먼저·오프 스위치는 그대로 | M1 |
| 「화면 배치」 발췌 항목 | 옛 정의문(``…마지막 프롬프트(`last-prompt`)다``) → 새 출처 규칙 한 문장 + 명령·`!` 턴은 호스트가 다시 적을 때까지 이전 값 | M1 |
| 「프라이버시 고지」 서브에이전트 항목 | 「**다시 불러낸(재개한) 실행**이 있는 세션은 그 세션의 transcript 끝에서 최대 **8MiB** 를 한 번 읽어 재개 요청(`SendMessage`)의 요약(`summary`)만 뽑아 제목으로 쓴다 — 요청 본문은 싣지 않고, 같은 마스킹 + 120자 상한, 같은 `record_prompt_excerpt:false` 로 꺼진다. 그 에이전트 자신의 대화 기록은 여전히 읽지 않는다」 | M2 |
| 「화면 배치」 실행 줄 | 제목 = 「재개된 실행이면 마지막 재개 요청의 요약, 아니면 호스트가 남긴 실행 설명, 없으면 타입명」 · 툴팁에 「재개 HH:MM」·「재개 N회」 · 기존 「재개되면 같은 줄이 다시 진행 중이 되고 경과는 재개 시각부터 센다」 유지 | M3 |
| 「알려진 한계」 | ① 명령·`!` 턴의 발췌 지연(호스트 규칙을 흉내 내지 않는 5%) ② 끝에서 8MiB 밖의 재개·요약 없는 재개는 원래 제목 | M1·M2 |

`commands/hub.md` 설치 고지: 「세션의 마지막 프롬프트와 서브에이전트 실행 제목이 … 기록(transcript·`subagents/*.meta.json`)
에서 읽혀 … 인라인」 — 두 변경 모두 transcript 출처라 문구가 이미 참이다. **무변경**.

### 10.2 PRP 이관 표기 (원문을 지우지 않고 화살표 한 줄 — SP6·MX 관례)

| 문서 | 항목 | 표기 | M |
|---|---|---|---|
| `hub-agent-runs-and-prompt-source.md` | §1.4 「위치 30/30 이 꼬리 128KiB 안」 | `→ 보강(TF1) — 위치는 맞지만 시점이 늦다: 호스트는 32KiB 마다 재부착(지연 중앙 22.8s·p90 65s). 발췌는 사람 프롬프트 줄 우선` | M1 |
| 〃 | PS3 「잃는 성질 하나」 | `→ 실제로 잃은 것은 즉시성이었다 — TF1 이 되살린다` | M1 |
| 〃 | §1.3 표 meta.json mtime 행 | `→ 개정(TF7 근거) — 2.1.284 는 재개 때마다 meta.json 을 다시 쓴다(6/6): mtime = 마지막 재개 시각, description 불변` | M2 |
| 〃 | AR9 | `→ 개정(TF12) — 재개된 실행은 resume_title 우선, title 의 뜻은 그대로` | M3 |
| `hub-tier1-clamp-fix-and-session-model.md` | E13 행 | `→ 전제 변화(2026-09-30 실측) — 호스트가 워크트리 진입 때 기록을 새 cwd 폴더로 옮긴다(relocated). 「먼저 존재하는 것」 규칙은 그대로 맞다(TF9 도 같은 규칙)` | M2 |

---

## 11. 리스크 · GOTCHA

1. **T25-206 산술** — `hub_subagent.py` 안의 `_scrubbed_and_clipped(`·`_metadata_field(` 호출 **줄** 수를 센다. 재개 요약
   스크럽은 정확히 한 호출 줄로 쓰고, docstring·주석에 그 두 이름 바로 뒤 `(` 를 쓰지 않는다(세면 4 ≠ 5).
2. **T25-93** — 템플릿 `run.is_running` 참조 수 3 고정. 툴팁 개정에서 새 참조를 만들지 않는다(`isResumed` 는
   `run.resume_count` 로만 판정).
3. **★순수 부분 문자열 가드**(T25-150 transcript: `open(`·`Path(`·`time.`(앞이 글자가 아닐 때)·`os.` / T25-205 subagent:
   `time.` 앞 조건 없음) — `pos.`·`repos.`·`datetime.` 같은 이름·주석 조각도 걸린다. `hub_subagent.py` 에 `datetime` 금지.
4. **함수 50줄** — `parse_session_tail` 은 이미 한계 근처다. 줄 단위 판정을 `_last_prompt_candidate` 로 뽑는다.
   `read_subagent_metas` 는 보강을 `_with_resume_titles` 로 뽑는다.
5. **T25-224** — `_read_session_annotations` 는 이번에 건드리지 않는다(TF13). 건드리게 되면 생존 신호 호출 줄에
   `record_prompt_excerpt` 가 들어가지 않게 한다.
6. **호스트의 기록 파일 이전**(§2.4) — 워크트리 진입 직후 새 cwd 가 훅 이벤트로 들어오기 전까지는 어느 후보에도 파일이
   없다 → 그 짧은 동안 발췌·모델·제목이 폴백(오늘과 같은 과도 현상).
7. **압축 재삽입** — 압축 뒤 호스트가 옛 메시지를 옛 timestamp 로 다시 붙이는 경우가 있다(768e8a38 실측, 이때 호스트
   자신의 `last-prompt` 도 옛 프롬프트로 돌아갔다). 재삽입 구간이 마지막 `last-prompt` 뒤에 놓이면 발췌·재개 제목이 옛 값을
   보일 수 있다 — 호스트 값과 같은 방향의 오류라 따로 막지 않는다(새 활동이 곧 덮는다).
8. **요약 없는 재개**(2.2%) — 그 재개는 원래 제목. 옛 요약으로 대체하지 않는 것이 의도다(S4).
9. **`to` ≠ agent_id** — 짝은 결과의 `resumedAgentId` 로만(S10).
10. **팀·teammate** — 문서상 teammate 는 메시지마다 `SubagentStart` 를 낸다 → resume_count 는 커지지만 `SendMessage` 짝이
    없어 매 수집 8MiB 를 끝까지 훑을 수 있다(최악 11~17ms). 이 기계에는 팀 사용 기록이 없다(§15 A5).
11. **스크럽 비용** — 유도 경로는 사람 줄 원문 전체(꼬리 ≤128KiB)를 스크럽한다. `hub_redact` 는 선형이라 최악 수 ms.
    → **구현 정정(M1, 검수 MEDIUM)** — 선형이 아니다: JWT 대안(`eyJ…`)이 점 없이 `eyJ` 가 반복되는 긴 글에서 이차 시간이라 128KiB
    에 8초(사람 줄 10만 자 꼬리의 `parse_session_tail` 4.64초, 변경 전 0.18ms)였다. 스크럽 입력을 앞 2,000자로 먼저 제한한다
    (`DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS`) — 병리적 입력 10종의 꼬리 파싱이 최악 4ms. `hub_redact` 정규식은 공유 보안 모듈이라
    바꾸지 않는다.
12. **동시성** — 공유 상태 추가 0. 수집은 서버 락(`_SnapshotRefresher`)이 직렬화한다. 활성 세션이 append 중인 파일을 읽으므로
    마지막 줄이 찢겨 있을 수 있다 → JSON 실패로 탈락(두 파서 모두 계약 B).
13. **설치본** — 구현은 워크트리 코드만 바꾼다. 실제 화면 반영은 사용자가 `hub/install.sh` 로 설치하고 서버를 다시 띄운 뒤다
    (`/hub server restart`). 이 작업에서 설치·재기동하지 않는다(CLAUDE.md §1).
14. **T37 미러 비용** — 원장 행마다 트리를 복사해 도는 무거운 그룹이다. 실행 중 작업 트리를 고치지 않는다(메모리 기록).

---

## 12. 마일스톤 (커밋 단위 — 각 커밋이 스위트 녹색)

| M | 내용 | 가드·래칫 | 커밋 제목(한국어 서술형) |
|---|---|---|---|
| M1 | 요구 ②: `hub_transcript` 유도 경로 + H1~H19·C1 + README 발췌 2곳·알려진 한계 ① + PRP 이관 표기(§1.4·PS3) | T25-260 신설 · 원장 +1 · 하한 515→516 | `fix: 허브 발췌가 방금 입력한 프롬프트를 바로 보여 주게 한다` |
| M2 | 요구 ① 데이터: facts `resume_count` · subagent `resume_title`·`parse_resume_titles` · subagent_read 보강 · session 뷰 2필드 + F·S·R·V + README 프라이버시(재개 요약)·알려진 한계 ② + PRP 이관 표기(§1.3·E13) | T25-261 신설 · T25-206 주석 · 원장 +1 · 하한 516→517 | `feat: 허브가 다시 불러낸 서브에이전트의 새 작업 이름을 읽어 둔다` |
| M3 | 요구 ① 화면: 템플릿 제목·툴팁(Q1 선택안) + D25~D28 + README 실행 줄 + PRP 이관 표기(AR9) | 신설 없음(기존 T25-11·201·93 확인) | `feat: 허브 실행 목록이 다시 불러낸 서브에이전트의 지금 작업 이름을 보여 준다` |

M2 만 착지한 상태에서도 화면은 오늘과 같다(템플릿이 새 키를 아직 읽지 않는다) — 롤백 경계가 깨끗하다.

**구현 후 확인(수동, 설치본 무접촉)**: 스크래치의 `freshness/resume_scan_proto.py` 방식으로 워크트리 코드의
`parse_resume_titles` 를 이 세션 기록에 돌려 6/6·≤6ms 재현 · `freshness/derive_fidelity.py` 의 규칙을 구현 함수로 바꿔
14일 재생 일치율 ≥94% 재현.

---

## 13. 사용자 승인 요청

승인하면 허브에서 두 가지가 달라진다. **다시 불러낸 서브에이전트 줄은 첫 작업 이름 대신 지금 하는 작업 이름으로 보이고,
방금 입력한 프롬프트가 세션 줄 아래에 바로 나타난다**(지금은 보통 20초~1분, 길면 몇 분 늦다). 훅이 새로 기록하는 것은 없다.

| # | 정할 것 | 선택지 | 권고 |
|---|---|---|---|
| Q1 | 다시 불러낸 에이전트 줄을 어떻게 보일까 | **안 A** 제목만 지금 작업 이름으로 바꾸고, 몇 번 다시 불렀는지는 마우스를 올리면 뜨는 설명에만 적는다 · **안 B** 안 A + 줄 끝 경과 시간 앞에 「재개 2회」를 늘 보이게(좁은 화면에서 제목이 더 잘린다) · **안 C** 다시 부를 때마다 줄을 새로 만든다(한 에이전트가 줄 여러 개를 차지해 다른 작업이 「+N건 더」로 밀린다) | **안 A** |
| Q2 | 지금 작업 이름을 찾으려고 대화 기록 끝에서 얼마나 읽을까 | 4MiB · **8MiB**(약 5~6시간치, 한 번에 약 5ms·최악 15ms, 다시 부른 에이전트가 있는 세션만) · 16MiB. 범위보다 오래된 것은 원래 이름으로 돌아간다(설명에 「재개 N회」는 남는다) | **8MiB** |
| Q3 | 발췌를 어떻게 바로 보이게 할까 | **사람이 입력한 프롬프트 줄을 직접 읽어 Claude Code 와 같은 규칙으로 줄여 보여 준다**(이미 읽는 부분이라 읽는 파일이 늘지 않는다. 슬래시 명령·`!` 명령 5%는 지금처럼 늦다). 자동 새로고침 주기는 **1분 유지**(새로고침·창 전환·새로고침 버튼은 즉시) 또는 15초로 줄이기 | **줄 직접 읽기 + 1분 유지** |

별건 제안(이번 범위 밖): 경로에 밑줄(`_`) 등이 있는 프로젝트(예: `notebook_wiki`)는 발췌·모델·실행 제목이 늘 비어 있다 —
따로 작은 수정으로 처리할지(§16 N1).

---

## 14. 프리뷰 목업 (요구 ① — 요구 ②는 화면 모양이 바뀌지 않아 장면이 없다)

- **HTML**(단독 실행, 외부 의존성 0, 2.4MB): `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/a74d3843-b65b-47c6-b041-80695c649cf5/scratchpad/freshness/mock/hub-agent-title-mock.html`
- **PNG**(2000×2900): `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/a74d3843-b65b-47c6-b041-80695c649cf5/scratchpad/freshness/mock/hub-agent-title-mock.png`
- 만드는 법: 실제 `hub_template.html`(현재)과 §8 변경을 문자열 치환으로 얹은 시제품(`proto_a.html`·`proto_b.html`)을 합성
  페이로드(`fixtures_tf.py` — 실제 dataclass 로 만든 스냅샷 + 제안 필드)로 굽고, 헤드리스 Chrome(`tests/hub/template_dom_harness`
  의 `--dump-dom` 경로)이 스크립트를 실행한 뒤의 DOM 을 iframe 에 넣었다 — 보이는 마크업·클래스·CSS 가 곧 구현 결과다.
  목업 장치는 `.mock-` 접두(파일 머리에 명시). 빌더: 같은 폴더 `build_mock_tf.py`·`shoot_tf.py`.
- 장면(각 칸 = 현재 | 안 A | 안 B | 안 C): ① 사용자 캡처 순간 재현(1440 다크) ② 최소 폭 320 라이트 ③ 실행 중 줄 hover 툴팁
  ④ 실행이 많은 세션 + 요약 없는 재개(폴백) ⑤ 카드 상세보기(모달).

---

## 15. 확인하지 못한 가정

| # | 가정 | 영향 | 확인 방법 |
|---|---|---|---|
| A1 | 호스트가 사람 줄을 UserPromptSubmit 훅 **완료 뒤에** 쓰는지 앞에 쓰는지(번들 순서 추적 안 함) | 서버가 꺼진 폴백 모드에서만 — 훅이 띄운 수집이 줄보다 먼저 돌면 다음 훅 이벤트(5초 쓰로틀)까지 옛 발췌. 서버 모드(이 사용자)는 무관 | 폴백 모드 재현(임시 HOME) |
| A2 | 호스트 `re(n,200)` 의 절단 단위(UTF-16/그래핌) | 1/453 불일치 — 이모지 경계에서 1글자 차이 후 호스트 값으로 교체 | 이모지 프롬프트 재현 → **구현 정정(M1)**: 원인은 절단 단위가 아니라 붙여넣기 표지 바깥 줄바꿈 흡수 — 패턴 개정(§6.4), 14일 재생 430/453 일치·불일치 0 |
| A3 | `SendMessage` 입력 `summary`·결과 `resumedAgentId` 는 호스트 소유·비문서 형식(도구이지 훅이 아니다) | 이름이 바뀌면 원래 제목으로 안전 강등 | 30일 실측으로만 뒷받침(220/225·189/189) |
| A4 | `origin.kind=="human"` 표지 | 없으면 오늘 경로 | 297/298 일치로 뒷받침 |
| A5 | teammate·팀 세션의 재개 모양 | GOTCHA 10 의 매 수집 최악 비용 | 이 기계에 사용 기록 없음 |
| A6 | 8MiB 가 다른 사용 패턴에도 충분한가 | 부족하면 오래된 재개가 원래 이름 | 가장 바쁜 세션 1개 기준 |
| A7 | 32KiB 재부착이 호스트 다음 버전에서도 유지되는가 | 바뀌어도 TF1 은 「더 뒤의 것」 규칙이라 무해 | — |

---

## 16. 범위 밖 발견 (언급만 — 고치지 않는다)

- **N1 프로젝트 폴더 인코딩 불일치** — `hub_project.encode_project_dir_name` 은 `/`·`.` 만 `-` 로 바꾸지만 호스트는
  `e.replace(/[^a-zA-Z0-9]/g,"-")`(+200자 초과 시 `-<해시>`). 밑줄·공백·한글 등이 든 경로의 세션은 transcript·meta.json 을
  못 찾아 발췌·모델·실행 제목·생존 신호가 늘 폴백이다(실측: `/Users/dev/works/notebook_wiki/NotebookWiki` 의 89ab77d8 —
  기록엔 `last-prompt` 가 있는데 허브 발췌 None). 축약 경로 후보.
  → **해결(2026-10-01, 축약 경로)** — 인코더를 호스트 규칙(비영숫자 → `-`, 200자 초과 시 앞 200자 + `-` + 자바식 해시
  36진수, UTF-16 단위)으로 이식하고, 그 규칙이 `*` 까지 바꿔 티어 3 무시 패턴이 죽는 결합을 막으려 glob 전용 인코더
  (`encode_path_glob_to_project_dir_glob`)를 더했다. 실제 폴더 21/21 일치(옛 규칙 18/21), 번들 원문 오라클 대조 불일치 0.
- **N2 E13 전제 변화** — §2.4. `hub_collect.read_session_tail` docstring 의 「최초 cwd 기준으로 남기 때문이다」는 사실과
  다르지만 규칙은 맞다(이관 표기만, 코드 주석 무변경).
- **N3 RL1 전제** — `last_prompt_at_ms`(UserPromptSubmit 훅 시각)를 「사람이 말을 걸었다와 1:1」로 두지만, 서브에이전트
  보고 전달·작업 알림도 UserPromptSubmit 을 낸다(이 세션 9/30: 36회 중 사람 2회). 실행 목록 경계의 폴백 갈래(RL8-(b)(c))가
  보고 도착마다 앞으로 당겨질 수 있다 — 별도 검토 필요.
- **N4 PS4 회귀** — §2.3. 이 PRP 가 고친다.
