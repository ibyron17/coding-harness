허브 세션 줄의 정보를 위에서 아래로 「누가 → 무엇을 → 지금 어느 단계 → 누가 하고 있나」 순서로 다시 놓고, 지금 단계를 진행률 줄 앞의 작은 표시(칩)로 접어, 백그라운드를 기다리는 세션도 어느 단계인지 보이게 한다.
따로 있던 「진행중 단계」 줄은 없앤다. 카드 상세보기 창은 화면을 꽉 채우지 않고 내용만큼만 커지며 남는 공간의 가운데에 뜬다(→ 이후 재개정: 윗변이 영역 높이의 12.5% 에 걸린다, 아래 LM8).
승인하면 허브 화면 파일 한 개와 진행 기록을 읽는 파이썬 모듈 한 개(「커밋 전」 표시용 사실 하나)를 고치고, 그 계약을 잠그는 검사와 안내 문서를 함께 맞춘다. 수집·훅·서버 동작은 바뀌지 않는다.

> 상태: **승인·구현 완료(검수 중)** — 2026-10-02. 설계 모델: opus(기본 — 승격 기준 미해당).
> 목업: `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/a74d3843-b65b-47c6-b041-80695c649cf5/scratchpad/hub-session-row-layout-mock.html`
> (PNG `…/scratchpad/hub-session-row-layout-mock.png`, 생성기 `…/scratchpad/build_mock.py` — 템플릿 `<style>` 를 그대로 읽어
> 바뀌는 규칙만 현재/제안 스코프로 가른다).
>
> 대상: `hub/bin/hub_template.html`(렌더 IIFE·CSS·머리 주석) · `hub/bin/hub_parse.py`(사실 1개, M3) · `tests/run.sh`(T25)·
> `tests/mutations.tsv` · `tests/hub`(DOM·단위) · `hub/README.md` · 이전 PRP 4개의 개정 표기.
> **바꾸지 않는 것**: 훅·수집(`hub_collect`)·`SessionView`·`BackgroundWait`·서버·패널 IIFE·세션 대시보드 템플릿.

---

## 0. 먼저 짚을 사실 — 전체 검사를 돌리는 쪽은 메인 세션이다

사용자 전제 「전체 검사(T37)는 검수 세션이 하는 것」은 규칙과 다르다. `rules/workflow/role-separation.md` 3단계는
「전체 검증은 **메인 세션이 커밋 직전에 1회** 돌린다, 검수자는 변경이 닿은 테스트만 돌린다」로 정한다(T31-9 가 그 토큰을 문다).
그래서 T37 이 도는 동안 허브에는 **메인 세션 줄**이 「◐ 백그라운드 대기」로 보이고(`hub_session.effective_background_wait`),
검수자(서브에이전트)는 별도 실행 줄로 이미 끝나 있다. 실제로 풀어야 할 문제는 전제가 아니라 증상이다 —
**「백그라운드 대기」인 세션이 지금 설계·승인·구현·검수 중 어디에 있는지 화면이 말하지 않는다.**

더 나아가, 규칙상 이 구간은 `log pass`(검수 통과) **뒤**·`log commit` **앞**이다. `hub_parse.derive_phase_states` 는
`pass` 에서 모든 단계를 완료로 만들므로(4/4 · 100%) 이 구간에는 **진행중 단계 자체가 없다** — 지금 화면의 `.tier1-active`
줄도 이 구간에서는 비어 있다. 요구 3 은 「단계명을 어디에 보이나」만으로는 풀리지 않고 「100% 인데 아직 커밋 전」이라는
사실을 하나 더 읽어야 풀린다(결정 LM6).

### 0.1 지시문 수치의 정정(코드 정독 결과)

| 지시문 | 실제 | 근거 |
|---|---|---|
| 시각 순서 line, meta, **excerpt, agent-run-list**, tier1, workflow-runs | line, meta, **agent-run-list, excerpt**, tier1, workflow-runs | `order` 를 받지 않은(0) 형제는 DOM 순서를 따른다 — DOM 이 `…meta → agent-run-list → workflow-runs → tier1 → excerpt` 라 order 0 묶음은 `line·meta·agent-run-list·excerpt` 순이다. 목업 「현재」 열이 그대로 보여 준다 |
| `SOURCE_GUARD_ID_FLOOR=517` | **524** | `tests/run.sh` 866행(t37-incremental-k6 가 517→524) |

원인도 드러난다: V7(docs/prps/hub-tree-view-and-signal-fixes.md)은 「본문(첫 줄·메타·발췌) 뒤에 자식(진행·위임)」을 `order` 로
만들었는데, 뒤에 들어온 `.agent-run-list`(AR8)가 `order` 를 받지 않아 본문 쪽(0)에 끼었다. **발췌가 2단 가지 사이로 튀어나온 것은
설계가 아니라 그 누락의 결과다.**

---

## 1. 요구사항 요약

허브 카드 목록의 세션 줄(`button.session-row`)과 카드 상세보기의 세션 카드(`.session-card`)는 같은 조각(`renderSessionContent`)을
그린다. ① 그 안의 정보 순서가 트리 문법(1단 본문 → 2단 가지)을 깨고 발췌가 가지 사이에 끼어 있다. ② 진행중 단계 줄(`.tier1-active`)과
실행 줄(`.agent-run`)이 같은 단계명을 겹쳐 말한다. ③ 그런데 실행 줄이 없는 상태(메인이 백그라운드를 기다리는 상태)에서는
단계를 말하는 곳이 그 줄뿐이고, 검수 통과 뒤 커밋 전 구간에서는 그 줄마저 비어 「어느 단계인지」가 안 보인다.
④ 카드 상세보기 창이 내용과 무관하게 화면 높이를 다 써서 카드 아래가 빈 면이다. 이 넷을 서로 충돌 없이 고친다 —
정보는 줄이지 않고(겹침만 걷고) 순서는 DOM 그대로 읽히게 한다.

---

## 2. 요구별 결론

| 요구 | 결론 | 결정 |
|---|---|---|
| 1 순서 | **채택** — line → meta → 발췌 → 진행률(+단계 칩) → 실행 줄 → 워크플로 칩. DOM 순서로 직접 그리고 CSS `order` 를 걷는다. 카드 목록·상세보기 같은 순서 | LM2·LM3 |
| 2 `.tier1-active` 제거 | **수정 채택** — 줄은 걷되 단계명은 진행률 줄 맨 앞 칩으로 남긴다. 「`.tier1-pct` 만」은 요구 3 의 바로 그 상황에서 단계를 잃어 기각 | LM4·LM5 |
| 3 백그라운드 대기의 단계 | **채택(재정의)** — 단계 칩이 상태와 무관하게 늘 보인다 + 검수 통과·커밋 전 구간에 「커밋 전」 칩. 서버는 사실 1개만 더한다 | LM5·LM6·LM7 |
| 4 창 높이 | **채택** — 내용 높이 + 남는 세로 공간의 가운데. 넘치면 지금처럼 최대 높이에서 창만 스크롤. 결정 MX7 개정 (→ 재개정: 윗변이 영역의 12.5% 지점 — 가운데 아님) | LM8·LM9 |

---

## 3. 결정

### LM1 — 문제를 「어느 세션이 어느 단계인가」로 다시 세운다
§0. 화면이 「T37 을 돌리는 중」을 말할 수는 없다 — 훅은 자유 텍스트(명령어)를 기록하지 않는다(프라이버시 계약). 알 수 있는 것은
세션 상태(백그라운드 대기·작업 수)와 세션이 기록기로 남긴 단계뿐이고, 이 설계는 그 둘만 쓴다.

### LM2 — 새 순서와 DOM 일치 (요구 1)

**새 순서(카드 목록 줄 = 상세보기 카드, DOM = 시각)**:

```
1단 본문 │ .session-line   ◐ 백그라운드 대기 · 2분 전            ← 상태(지금 어떤가)
         │ .session-meta   시작 14:02 [63ad8669] [Opus 5.5 · xhigh] ← 신원(어느 세션인가)
         │ .excerpt        허브 화면의 세션 줄 순서와 …            ← 무엇을 시켰나
2단 가지 ├ .session-tier1  [검수] 허브 세션 줄 정리 — 3/4 · 75%    ← 작업이 어디까지 왔나(항상 있는 노드)
         ├ .agent-run-list [검수] 허브 레이아웃 변경 검수   6분     ← 그 단계를 누가 하고 있나
         │                 [구현] 세션 줄 순서·단계 칩 구현  18분
         └ .workflow-runs  [lint-sweep] [type-check]               ← 보조 실행(가장 드묾)
```

**왜 이 순서가 읽기에 맞나**
- 트리 문법: 발췌는 세션 노드 **자신**의 내용(1단)이다. 1단 내용이 2단 가지 사이에 끼면 레일이 끊기고(지금 실행 줄 └ 와 진행률 └ 가
  따로 매달린다) 발췌가 어느 가지에 속하는지 헷갈린다. 본문을 다 말한 뒤 가지를 연다.
- 일반 → 구체: 세션(상태·신원) → 과제(발췌) → 과제의 위치(진행률·단계) → 그 단계의 실행자(실행 줄). 단계 칩과 실행 줄 칩이
  위아래로 붙어 「검수 단계 / 검수 실행 2건」이 한눈에 이어진다.
- 스캔 정렬: 첫 두 줄(상태·메타)은 모든 세션에 늘 있는 고정 구조라, 카드 안 여러 세션을 훑을 때 눈이 같은 자리를 찾는다. 발췌는
  없을 수 있어 그 아래에 둔다.

**DOM 을 바꾸고 `order` 를 걷는 이유** — V7 이 DOM 을 고정한 근거는 「DOM 을 바꾸면 접힘 화면이 바뀐다」였는데 접힘 상태는 TR1 로
삭제됐다(근거 소멸). 반대로 지금의 DOM/시각 불일치는 실해가 있다: 세션 줄은 `<button>` 이라 화면 낭독기가 자식 텍스트를 **DOM 순서로**
이어 읽는다(지금은 「… 실행 줄 … 워크플로 … 진행률 … 발췌」로 화면과 다르게 읽힌다, WCAG 1.3.2), 그리고 레일 결합자
(`.workflow-runs ~ .session-tier1`)가 DOM 순서에 기대 시각 순서와 반대 방향으로 쓰여 있다. `.session-row{display:flex;flex-direction:column}`
과 두 `>.excerpt{flex-basis:auto}` 는 남긴다 — 발췌가 `<span>` 이라 flex 아이템으로 블록화되는 것이 지금의 줄 모양을 만든다(수술적 변경).

**카드 목록과 상세보기는 같은 순서** — 같은 렌더러를 공유하는 것이 DRY 이고(SC6), 다르게 하려면 `order` 를 다시 들여 DOM/시각 불일치를
되살려야 한다. 340px 고정 카드의 높이 압박은 순서가 아니라 줄 수로 오는데, LM4 가 진행률 있는 세션마다 18~36px 를 덜어 오히려 보이는
세션이 늘어난다(구현 측정 R1).

**기각**
- (1b) line → 발췌 → meta → … — 발췌는 없을 수 있어 첫 두 줄의 고정 구조가 세션마다 흔들린다.
- (1c) 발췌를 맨 끝(각주) — 1단 내용이 2단 가지 뒤에 와 트리 문법이 같은 방식으로 깨진다(지금 문제의 거울상).
- (1d) CSS 만 고치기(`.agent-run-list{order:1}` 추가) — 한 줄로 시각은 맞지만 낭독 순서 불일치·DOM 의존 결합자를 그대로 남긴다.
- (1e) 상세보기만 다른 순서 — 위 「같은 순서」 근거.

### LM3 — 2단 레일은 「각 가지 갈고리 + 마지막이 아니면 레일」 (요구 1 의 기하)

지금 레일은 진행률 노드 하나만 `::after` 레일을 가지며 그것도 `.workflow-runs ~ .session-tier1`(DOM 에서 워크플로가 앞일 때)로만 켜진다.
가지 순서가 바뀌면 이 결합자는 성립하지 않는다. `.sessions li` 가 이미 쓰는 관용구로 바꾼다 — 가지는 버튼의 **마지막 자식들**이고
진행률 노드는 늘 있으므로(대시보드 없음 포함) `:last-child` 가 「마지막 가지」와 정확히 같다.

```css
/* 공통 선언 목록(.sessions li::before … .session-tier1::after)에 두 의사요소를 더한다 */
.agent-run-list::after, .workflow-runs::after { content:""; position:absolute; left:-12px; border-left:1px solid var(--muted); opacity:.5 }
.session-tier1::after{top:17px;bottom:0}                       /* display:none 을 걷는다. 17 = 갈고리 바닥선 y(기존 값) */
.agent-run-list::after,.workflow-runs::after{top:9px;bottom:0} /* 9 = 갈고리 상자(top -4, 높이 14)의 바닥선 y */
.session-tier1:last-child::after,.agent-run-list:last-child::after,.workflow-runs:last-child::after{display:none}
/* 삭제: .workflow-runs ~ .session-tier1::after{display:block} */
```

- `bottom:0` — 레일은 가지 바닥에서 끝나고, 다음 가지의 갈고리 상자(`top:-4px`)가 그 바닥에서 시작해 맞닿는다. 처음 안은 `bottom:-4px` 였으나 구현 단계 실측(R3)에서 4px 겹쳐 그 구간만 진해졌다 — 옛 산식에 있던 겹침을 그대로 옮긴 오류여서 정정했다(LM3 정정).
- 진행률 노드가 첫 가지가 되면서 그 갈고리(`top:0`, 높이 18, 바닥선 17 = `.tier1-pct` margin-top 8 + 줄 중앙 9)는 무변경이다.
  단계 칩이 그 줄 **안**의 인라인이라 줄상자 높이(18px)가 그대로여야 이 정렬이 유지된다(구현 측정 R2).
- 새 기하 상수 0개(9·17·−4 는 기존 갈고리 산식에서 나온다). 상세보기 카드에도 같은 규칙이 그대로 적용된다(스코프 없음).

**기각**: 가지를 감싸는 새 래퍼(`.session-branches`) — 마크업·맞대기 대상이 늘고, `:last-child` 가 래퍼 없이도 성립한다.
`:has()` 로 다음 형제를 보고 레일 켜기 — 같은 일을 더 무거운 선택자로 한다.

### LM4 — `.tier1-active` 줄을 걷는다 (요구 2)
- 겹침은 사실이다: 서브에이전트가 돌 때 진행중 단계 줄의 단계명과 실행 줄 칩이 같은 말(「검수」)을 한다.
- 다만 두 줄의 **나머지**는 다른 정보다: `.tier1-active` 의 꼬리(`— …`)는 `latest_log_summary`, 즉 **직전 기록의 요약**(과거)이고 실행 줄
  제목은 지금 돌고 있는 위임의 설명이다. 그래서 「줄을 지우고 끝」이 아니라 「겹치는 단계명은 한 곳(LM5)으로 접고, 과거 요약은 툴팁으로」다.
- 지우는 것: JS 의 `<div class="tier1-active">` 출력, CSS 기본 규칙(TC2 의 `-webkit-box` 클램프 3선언 포함)과 상세보기 해제 규칙
  `.session-card .tier1-active{…}`, 머리 주석의 TC 문단. TC2 가 지키던 대상(2줄 클램프)이 사라지므로 그 방어도 함께 걷는다(YAGNI —
  T25-147 이 MX5 때 같은 이유로 주 검사를 지운 선례).
- `.tier1-impl`(구현 세부 n/m)·`.session-no-dashboard` 는 무변경.

### LM5 — 단계 칩: 진행률 줄 맨 앞 (요구 2·3 의 단일 해법)

```html
<div class="tier1-pct"><span class="agent-chip tier1-step" data-tooltip="구현 1회차 완료 — …"><span class="sr-only">현재 단계 </span>검수</span> 허브 세션 줄 정리 — 3/4 · 75%</div>
```
- 칩은 `.agent-chip` 을 **클래스째 재사용**한다 — 실행 줄의 단계 칩과 같은 시각 어휘(「칩 = 단계」), 새 색 토큰·새 색 조합 0개.
  강조색(`agent-chip-running`)은 쓰지 않는다 — 그 색은 「서브에이전트가 지금 돈다」의 뜻이라 단계 칩에 쓰면 백그라운드 대기 세션이
  실행 중처럼 읽힌다. 새 규칙은 `.tier1-step{margin-right:3px;white-space:nowrap}` 하나(칩 뒤의 실제 공백 ≈3px 과 합쳐 간격 6px, 접근 가능한 이름이 칩과 제목을 공백으로 나눠 읽는다)(「커밋 전」이 두 줄로 찢어지지 않게).
- 칩을 **앞**에 두는 이유: 제목 길이가 세션마다 달라 뒤에 두면 칩 x 가 흔들린다. 앞에 두면 세션들을 위아래로 훑을 때 단계가 같은 열에 선다.
  긴 제목은 칩 뒤에서 자연 줄바꿈한다(목업 「긴 제목」 — 클램프 없음, 카드 목록·상세보기 같음 → MX9 「덜 보여 주지 않는다」 자동 충족).
- 툴팁: 단계의 `detail`(직전 기록 요약)이 있을 때만 `data-tooltip` 을 단다 — 화면에서 사라지는 정보라 R4(정보 손실 없는 툴팁은 소음)를
  만족한다. `.session-id` 칩이 버튼 안에서 툴팁을 갖는 선례 그대로. 칩 텍스트 앞 `.sr-only` 「현재 단계 」는 `.session-model` 의
  `SESSION_MODEL_SR_LABEL` 관례다 — 버튼 이름이 「… 현재 단계 검수 허브 세션 줄 정리 — 3/4 · 75% …」로 읽힌다.
- 서버 변경 없음 — `tier1.steps[].state`·`name`·`detail` 은 이미 직렬화돼 있다.

**상태별 표시표**(목업 3·4절이 그대로 그린다)

| 세션 상태 | 진행 기록 | 서브에이전트 | 첫 줄 배지 | 진행률 줄(첫 가지) | 실행 줄 |
|---|---|---|---|---|---|
| 작업중 | 검수 중(3/4) | 실행 중 | ● 작업중 | `[검수]` 제목 — 3/4 · 75% | `[검수]`(강조색) 제목 · 경과 |
| 작업중 | 구현 중 | 없음 | ● 작업중 | `[구현]` 제목 — 2/4 · 50% | 끝난 실행만(중립색) 또는 없음 |
| **백그라운드 대기** | 검수 중 | 끝남 | ◐ 백그라운드 대기 | `[검수]` 제목 — 3/4 · 75% | 중립색 |
| **백그라운드 대기** | 100% · 커밋 기록 없음 (T37 구간) | 끝남 | ◐ 백그라운드 대기 | `[커밋 전]` 제목 — 4/4 · 100% (LM6) | 중립색 |
| 대기 | 승인 중(1/4) | 없음 | ○ 대기 | `[승인]` 제목 — 1/4 · 25% — 「사용자 승인을 기다림」으로 읽힌다 | 없음 |
| 대기·완료 | 100% · 커밋 기록 있음 | – | ○ / ✓ | 제목 — 4/4 · 100% (칩 없음) | – |
| 아무 상태 | 끝난 작업의 대시보드(`tier1_is_finished_task`) | – | – | 제목 — 4/4 · 100% (칩 없음) | – |
| 소식 없음·한도 초과 | 진행중 단계 있음 | – | ▲ 소식 없음 · 직전 … / ■ 한도 초과 … | `[구현]` 등 마지막 기록 기준 | – |
| 아무 상태 | **대시보드 없음**(기록기 미사용·꺼짐) | 있음/없음 | 상태 그대로 | `대시보드 없음` (단계 알 수 없음) | 단계 칩은 실행 줄에만 |

대시보드가 없는 세션의 단계는 이 설계로도 알 수 없다 — 단계의 유일한 출처가 세션이 남긴 기록이다(LM1). 그 세션의 실행 줄 칩이
(있다면) 위임 단위의 단계를 말한다.

**기각**
- (A) 사용자 원안 그대로 — `.tier1-active` 를 지우고 `.tier1-pct` 만: 서브에이전트 줄이 없는 상태(바로 요구 3 의 상황)에서 단계를 말하는
  곳이 사라진다. 요구 2 를 풀며 요구 3 을 악화시킨다.
- (C) 상태 배지 옆(첫 줄)에 「◐ 백그라운드 대기 · 검수」 — 가장 눈에 띄지만 ① 첫 줄 구성은 문자 단위 불변 계약(T25-127, SC6 — 이후 session-time 이 「소요 시간」으로 바뀌어 지금 T25-127 은 meta 누출만 문다)이고
  ② 320px 최소 폭에서 배지 라벨이 이미 최장 조합에 가까우며(BW10 R8) ③ 진행률 줄과 단계를 두 번 말한다. 단계는 「작업의 위치」라
  진행률 옆이 의미상 맞다. 첫 줄 수준의 눈띔이 필요하다는 보고가 오면 그때 다시 본다.
- (D) `.tier1-active` 를 두되 실행 중 줄이 있을 때만 숨김(`:has(.agent-chip-running)`) — 실행 줄이 생기고 사라질 때마다 줄이
  나타났다 사라져 340px 카드가 덜컥인다. 단계명은 여전히 두 군데다.
- (E) 진행률 줄 **뒤**에 「· 검수 중」 텍스트 — 칩보다 덜 훑어지고 칩 x 정렬 이점이 없다.

### LM6 — 검수 통과·커밋 전 구간: 「커밋 전」 칩 + 서버 사실 1개 (요구 3 의 나머지)
§0 대로 사용자가 겪은 T37 구간은 진행중 단계가 없다(4/4 · 100%). 그 구간을 「커밋 전」 칩으로 말한다.

- **서버**: `Tier1Snapshot` 에 `is_committed: bool = False` 하나를 맨 뒤에 더한다 — 「마지막 `pass` 기록 뒤에 `commit` 기록이 있다」
  (`pass` 가 없으면 False). `snapshot_from_events` 가 이벤트 열에서 순수 함수로 유도한다. 사실만 주고 표시 여부는 클라이언트가 정한다
  (GN4·FT4 관례). 이벤트 `kind` 는 폐쇄 어휘라 자유 텍스트를 싣지 않는다. 직렬화는 `asdict` 라 자동이고, 정적 값이라
  `snapshot_content_key` 를 흔들지 않는다(D2).
- **클라이언트**: 진행중 단계가 없고 `percent >= 100` 이고 `!tier1.is_committed` 이고 `!session.tier1_is_finished_task` 면
  `[커밋 전]` 칩(툴팁 「전 단계를 마쳤습니다 — 아직 커밋 기록이 없습니다.」). 세션 상태로는 거르지 않는다 — 대기(○)+커밋 전은
  「검수 통과, 커밋 승인을 기다림」으로 정확히 읽힌다.
- **왜 서버까지 가나(클라이언트 단독 대안 기각)**: 「100% 이고 세션이 작업중·백그라운드면 마무리 중」으로 추정하면 서버 변경 0 이지만,
  커밋 뒤 같은 세션에 기록기 없이 이어지는 질문·작은 수정(워크플로 생략 작업 — 흔하다) 동안 「마무리 중」이 거짓으로 뜬다. `commit`
  기록은 이미 규칙(hub/rules/dashboard-recording.md)이 남기는 사실이라 그것을 읽는 것이 정확하다.
- 한계: 사용자가 커밋하지 않기로 해 `log commit` 이 끝내 없으면 「커밋 전」이 남는다 — `tier1_is_finished_task`(100% 뒤 Δ 이상 더 일함)가
  켜지면 거둔다. 표시가 남는 동안에도 「검수 통과 뒤」라는 사실은 참이다.
- **분리 가능**: 이 결정은 M3 한 마일스톤이다. 사용자가 서버 변경을 원치 않으면 M3 만 빼도 M1·M2·M4 는 성립한다(그 경우 T37 구간은
  「4/4 · 100%」만 보인다 — 핵심 결정 질문 2).

### LM7 — 백그라운드 작업 종류(shell/monitor/workflow)는 더하지 않는다
`BackgroundWait` 는 since/until/task_count/wakeup_count 만 가진다. 종류별 개수를 배지·툴팁에 보이려면 `SessionView` 계열 담체와
`hub_session` 판정이 바뀐다(T25-150 의 마지막 필드 계약도 닿는다). 사용자가 물은 것은 「어느 단계」이지 「무슨 종류의 작업」이 아니고,
「셸 1개」는 T37 이라는 이름을 말해 주지 못한다(LM1). YAGNI — 툴팁의 작업 수로 충분하다.

### LM8 — 카드 상세보기 창: 내용 높이 + 남는 세로 공간의 가운데 (요구 4, **결정 MX7 개정**)

> → **재재개정(2026-10, 창 위치 12.5%)** — 아래 30% 재개정의 값만 바꾼다: 스페이서 `flex:0 1 30%` → `flex:0 1 12.5%`. 30% 는 「영역(헤더 아래 ~ 화면 아래 16px) 높이의
> 30%」인데, 창 높이가 280~350px 인 일반 화면에서는 30% 오프셋이 가운데 정렬의 간격((영역 − 창 높이) / 2)에 가까워 **사실상 세로 가운데와 같은 자리**가
> 됐다(실측: 화면 924px · 창 278px 에서 윗변 ≈324px — 가운데 정렬의 간격 273px 에 가깝다). 사용자 스크린샷 기준 「약간만 위로」는 창 윗변이 화면의 20%(185px), 곧 **창 아랫변이
> 화면 세로 중앙선에 닿는 자리**다. 역산: 영역 827px(= 924 − 헤더 81 − 아래 여백 16)의 12.5% = 103px → 창 윗변 ≈ 185px(화면 768px 에서 ≈ 159~165px, 화면의 약 20%). 구조(줄어드는
> 스페이서·창 `flex-shrink:0`·`max-height:100%`·세로 margin 0)는 그대로라 넘칠 때의 안전 정렬(윗변이 헤더 밑으로 잘리지 않음)도 그대로다. 검사: D29(정확히 영역의 12.5% +
> 가운데 정렬 간격의 절반 이하)·D21·T25-258. 아래 30% 서술은 이 재재개정이 대체한 이력이다.
>
> → **재개정(2026-10, 창 위치 30%)** — 아래 ②(가운데에서 약간 위)를 **대체**한다: 창 윗변은 영역(헤더 아래 ~ 화면 아래 16px) 윗변에서 **영역 높이의 30% 아래**다(사용자
> 「top: 30% 정도」, 가운데 정렬이 아니다). 구현은 `.session-modal::after{content:"";order:-1;flex:0 1 30%}` 가 창 앞의 첫 flex 아이템이 되고 창의 세로 margin 을 `0`
> (`margin:0 var(--dzh-wrap-gutter)`, 자동 여백은 남는 공간을 위아래로 나눠 가운데로 돌아간다)으로 두는 것이다. 창은 `flex-shrink:0` 이라 30% 오프셋이면 창이 영역 아래를 넘을 때
> 스페이서가 먼저 0 까지 줄어 창을 영역 안(아래 16px 유지)에 들이고, 그래도 넘치면 창이 최대 높이에서 멈춰 창 안에서 스크롤한다 — 윗변이 헤더 밑으로 잘리지 않는다(LM9 유지).
> `::before` 가 아니라 `order:-1` 을 쓴 이유: `::before` 는 배경 가림막(absolute, `inset:0`)이 쓰고 있어, 스페이서로 쓰려면 가림막을 `::after` 로 옮겨야 하는데
> 그러면 DOM 순서상 창 뒤에 와 창을 덮는다(z-index 곡예가 필요). 기각은 그대로(창에 `transform`·`top` 오프셋 — 넘칠 때 창이 영역 밖으로 나간다). 옛 값(영역 5%·32px 상한,
> `_LIFT_AREA_FRACTION`·`_LIFT_CAP_PX`)은 폐기, 검사는 D29·D21·T25-258 이 새 사실을 문다. 아래 「가운데」 서술은 이 재개정이 대체한 이력이다.
>
> → **개정(2026-10, 카드 상세보기 모달 조정)** — ① 사용량 패널은 화면에 떠 있는 컴포넌트다: `body.has-usage .session-modal{padding-bottom:var(--usage-clearance,218px)}`
> 를 삭제해 창의 자리·최대 높이가 패널 상태(없음·접힘·펼침)에 의존하지 않는다(아래 「사용량 패널 펼침」 행·「가운데 영역」 괄호 서술은 폐기). ② 가운데에서
> **약간 위** — `.session-modal::after{content:"";flex:0 1 min(10%,64px)}`(영역 높이의 10%, 64px 상한)가 창의 자동 여백 중심을 위로 옮겨 창이 영역 높이의
> 5%(32px 상한)만큼 위로 간다. 창은 `flex-shrink:0` 이라 내용이 영역을 채우면 이 아이템이 먼저 0 으로 줄어 최대 높이·윗변 접근성은 그대로다.
> 기각: 창에 `transform`·`top` 오프셋(넘칠 때도 올라가 윗변이 헤더 밑으로 잘린다), 오버레이 `padding-bottom` 키우기(넘칠 때 최대 높이를 깎는다).
> ③ 칸의 스크롤 막대를 숨긴다(`scrollbar-width:none` + `::-webkit-scrollbar{display:none}`) — 위·아래 안쪽 패딩은 그대로.

MX7 은 「가용 높이 전부, 상한은 두지 않는다 — 보고되면 그때 잰다」였다. 그 보고가 들어왔다(1440×900 에서 창 759px, 카드 약 400px —
아래 절반이 빈 면). MX7 의 출발 요구(「답답하니 크게」)는 카드 폭 320px(MX8)·잘림 해제(MX9)가 이미 풀었고, 높이 채움은 빈 면만 남겼다.

```css
.session-modal{position:absolute;top:100%;left:0;right:0;height:calc(100vh - 100%);
               visibility:hidden;opacity:0;pointer-events:none;
               display:flex;flex-direction:column;padding-bottom:16px}          /* 뒤 세 선언 추가(앞부분 불변 — T25-239 앵커) */
body.has-usage .session-modal{padding-bottom:var(--usage-clearance,218px)}      /* 다이얼로그 규칙에서 옮겨 온다(SC16 같은 변수·폴백) */
.session-modal-dialog{…;margin:auto var(--dzh-wrap-gutter);max-height:100%;overflow-y:auto;…}
                       /* margin:0 → auto(세로), height:calc(100% - 16px) → max-height:100% */
/* 삭제: body.has-usage .session-modal-dialog{height:calc(100% - var(--usage-clearance,218px))} */
```

- **가운데 영역 = 헤더 아랫변 ~ 화면 아래 16px**(사용량 패널이 있으면 그 위 `--usage-clearance`). 아래 여백을 다이얼로그 높이 산식이 아니라
  오버레이의 `padding-bottom` 이 가지므로 「가운데」와 「사용량 패널을 가리지 않음」이 한 규칙에서 함께 성립한다. 전체 영역 기준으로
  가운데에 두고 최대 높이만 깎으면, 긴 내용일 때 창 아래가 `clearance/2` 만큼 사용량 패널(z-index 20) 밑으로 들어간다.
- `margin:auto`(세로)를 쓰고 `justify-content:center` 를 쓰지 않는다 — 자동 여백은 넘칠 때 음수로 가지 않는다(안전 정렬). 지금은
  `max-height:100%` 라 넘칠 일이 없지만, 한쪽이 바뀌어도 창 머리가 헤더 밑으로 잘려 올라가지 않는다. 가로 여백은 거터 그대로라
  `align-self:stretch` 로 폭은 지금과 같다.
- 오버레이(`::before`, inset 0)는 패딩 상자를 덮으므로 아래 여백까지 그대로 흐려진다. 열기 전이(opacity 180ms)는 무변경.
- **연결선 기하 MX6 와의 관계**: 무관하다. MX6 의 등식(루트 아랫변 = 프레임 윗변, 칸 위 패딩 = stem + drop, 루트 왼끝 = 첫 카드 왼끝)은 전부
  본문 **안쪽**의 관계이고 창의 세로 위치·높이를 쓰지 않는다. D20 은 무수정으로 통과해야 한다(구현 측정 R7).

**거동**

| 경우 | 창 | 비고 |
|---|---|---|
| 1440×900 · 세션 3개(실측 카드 ≈400px) | 내용 높이(≈500px), 헤더 아래 남는 공간 가운데 | 위아래 어두운 띠가 같다 |
| 세션 1개 | 더 낮은 창, 가운데 | 폭은 지금처럼 다이얼로그 전폭 — 카드 1장 + 오른쪽 빈 칸(폭은 이번 범위 밖) |
| 세션 5개 | 높이는 가장 긴 카드가 정한다(가로 한 줄) — 세션 수가 아니라 내용이 정한다 | 칸의 `align-items:stretch` 로 카드 밑단 가지런(SC6) |
| 사용량 패널 펼침 | 가운데 영역에서 `--usage-clearance` 를 뺀다 | 목업 5절 셋째 틀 |
| 좁은 높이(1024×420 등)·내용 넘침 | `max-height:100%` = 헤더 아래 ~ 화면 아래 16px, 창만 세로 스크롤 | 지금과 같은 거동 — 칸은 자체 세로 스크롤 안 함(LM9) |
| 밀어내기(≥1024, 패널 열림) | 가로로 좁아질 뿐 세로 정렬 동일 | SC1 무변경 |
| 폴링으로 실행 줄이 늘어남 | 창이 자라며 윗변이 절반만큼 올라간다 | 갱신은 최대 분당 1회·줄 단위라 받아들인다(위험 R-3 — 재개정으로 윗변이 고정돼 창은 아래로만 자란다) |

**기각**
- (4A) 내용 높이 + 위 정렬(옛 SC6) — 바뀔 때 윗변이 고정이라 덜 흔들리지만 사용자가 명시한 조건(동적 높이면 가운데)과 다르다.
- (4C) 비율 상한(`min(가용, 70vh)` 등) — 근거 없는 수이고, 내용이 적으면 여전히 카드 아래 빈 면이 남는다.
- (4D) 내용 높이 + 최소 높이(`min-height`) — 바닥값이 근거 없는 수이고, 그 바닥까지 늘어난 카드 안에 다시 빈 면이 생긴다.

### LM9 — 세로 flex 사슬의 `flex:1 0 auto` 는 그대로 둔다
창 높이가 내용에서 나오면 사슬이 나눠 받을 「남는 높이」가 없어 grow(1)는 비활성이 된다. 그러나 shrink(0)는 여전히 하중을 진다 —
창이 `max-height` 에 닿아 넘치는 순간 shrink 가 1 이면 칸(스크롤 컨테이너, 자동 최소 높이 0)이 줄어 **자기 안에서 세로 스크롤**한다
(SC6 이 기각한 가로·세로 스크롤 겹침, GOTCHA 8). 선언을 바꾸면 동작은 같고 가드·변조행만 늘어나므로 선언은 두고 주석만 「grow 는
비활성, shrink 0 이 넘칠 때의 하중」으로 고친다.

### LM10 — 발췌 길이는 손대지 않는다
발췌를 진행률 위로 올리면 긴 발췌(상한 120자)가 가지를 아래로 민다. 실측 중앙값은 23자(hub/README.md)라 보통 1줄이고, 카드 목록에서
2줄 클램프를 걸면 CSS 잘림은 JS 가 몰라 툴팁 규칙(R4 — 실제로 잘렸을 때만 툴팁)이 깨진다. 요청 범위 밖 — 후속 후보로만 남긴다.

### LM11 — 세션 첫 줄의 시간은 「작업을 시작한 순간부터」다 (사후 결정, 2026-10)
세션 줄 첫 줄의 소요 시간(`N분 소요`)은 처음에 「세션이 처음 시작된 때부터」였다. 같은 세션을 며칠 이어 쓰면 새 작업을 시작해도 시간이 계속 이어져 의미가 없었다.
이제 **해당 작업을 시작한 순간부터**이고, 같은 세션에서 다른 작업을 시작하면 시작 시각이 새로 정해진다.
- **서버**: `SessionView.task_started_at_ms: int | None = None`(`tier1_is_finished_task` 바로 뒤, `background_wait` 는 계속 맨 뒤 — T25-150). 값은 이미 있는
  `previous_task_boundary_ms`(진행 중 대시보드 작업 = 작업 시작(init) 시각 · 끝난 작업 = max(작업 시작, 마지막 프롬프트) · 대시보드 없음 = 마지막 프롬프트 · 대시보드를
  껐으면 None)를 `compute_session_view` 가 한 번만 계산해 실행 목록 경계와 이 필드가 같이 쓴다. 그 값이 None 이면 마지막 프롬프트로, 그것도 없으면 None 이다.
  정적 정수라 `snapshot_content_key` 의 「지금 파생값 금지」 규칙에 어긋나지 않는다. 직렬화는 `dataclasses.asdict` 라 스냅샷 JSON 에 자동으로 실린다.
- **클라이언트**: `sessionElapsedLabel` — 시작 = `task_started_at_ms`, 없으면 `started_at_ms`(세션 시작). 끝 = 세션이 도는 중(`working`·`background`)이면 지금,
  그 밖(`idle`·`done`·`stale`·`interrupted`)이면 `last_event_at_ms` 로 **고정**한다 — 멈춘 세션의 시간이 계속 불어나면 의미가 없다(예전에는 `done` 만 고정이었다).
  음수는 durationLabel 이 「1분 미만」으로 처리한다. 화면 낭독기 앞말은 「세션 시작부터 」 → 「작업 시작부터 」. 둘째 줄 메타의 「시작 …」(세션 시작의 절대 시각)은 그대로다.
- **한계**: 대시보드 없이 프롬프트만 있는 세션은 마지막 프롬프트가 작업 시작이라, 한 작업 안에서 사용자가 추가 프롬프트를 보내면 시간이 그 시점으로 다시 시작한다
  (작업 단위의 유일한 선언자는 대시보드 기록기 `init` 이고, 대시보드가 없으면 프롬프트가 가장 가까운 대용이다 — 결정 RL8·RL10 과 같은 판단).
- **개정(2026-10-08, 결정 RL11 — [`hub-card-gate-and-run-list-reset.md`](hub-card-gate-and-run-list-reset.md))**: 위의 「마지막 프롬프트」는 훅 시각이 아니라 transcript 꼬리에서 읽은 **마지막 사람 입력 시각**이다
  (`compute_session_view(last_human_prompt_at_ms=…)`). 훅은 백그라운드 완료 알림·서브에이전트 보고에도 발화해, 끝난 작업·대시보드 없는 세션의 시작 시각이 알림마다 알림 시각으로 바뀌고
  시간이 「1분 미만」이 됐다. **한계**: 꼬리(128KiB)보다 긴 자율 작업에서는 사람 입력이 꼬리 밖이라 값이 None 일 수 있다 — 그때 이 필드는 (대시보드 경계가 없으면) None 이고
  화면은 세션 시작부터 센다(잘못된 시작 시각을 보이느니 더 이른 쪽으로 물러나는 페일오픈).
- **개정(2026-10-08)**: `task_started_at_ms` 는 세션 시작(`facts.started_at_ms`)보다 앞서지 않는다(`max`로 당김, 후보가 None 이면 None). 끝나지 않은 채 남은 옛 대시보드 파일의 init 이 세션보다 오래돼 「139시간」 같은 값이 나왔다. 실행 목록 경계(`previous_task_boundary_ms` 반환값)는 그대로다. **한계**: 세션을 이어받아 같은 작업을 계속하면 이어받은 시점부터 센다(수용). 이벤트 창(오늘+어제) 밖에서 시작한 오래된 세션은 `facts.started_at_ms` 가 창 안 첫 이벤트라 늦으므로, 이틀 넘게 이어진 작업은 실제보다 짧게 센다(기존 「세션 시작」 폴백과 같은 한계).
- 검사: `test_hub_session.py` `SessionTaskStartedAtFieldTest`, DOM D32(작업 시작 기준·도는 세션은 흐르고 멈춘 세션은 고정·세션 시작 폴백·음수·낭독기 문구).

### LM12 — 진행률 줄 맨 앞 단계 칩을 걷는다 (개정, 2026-10-08 — 결정 LM5·LM6 폐기)
- **사유**: 그 칩(`.agent-chip tier1-step`)이 바로 아래 서브에이전트 실행 줄의 칩(`.agent-chip`)과 같은 모양이라 둘이 헷갈렸다(LM5 가 「새 색 0개」를 장점으로 삼은 바로 그 재사용이 원인).
- **사라지는 정보**: 진행중 단계 이름 · 「커밋 전」 표지(검수 통과 뒤 커밋 기록 전 구간) · 단계 칩의 툴팁(직전 기록 요약). 진행률 줄은 「제목 — 완료/전체 · %」 글자뿐이다. 단계별 상태·요약은 세션 줄·카드를 눌러 여는 상세 패널의 세션 대시보드(서버 모드, 끝난 작업 제외)에서만 본다.
- **화면 쪽**: `renderTier1ActiveStep`·`tier1StageChipContent`·칩 전용 상수·`.tier1-step` CSS 를 걷고 `renderTier1(tier1)` 은 한 인자가 됐다(끝난 작업 여부 인자는 칩만 읽었다). 검사: DOM D27 은 「칩이 없다·진행률 줄은 글자뿐·실행 칩 수 그대로」로 반전, T25-263 은 옛 이름·클래스·상수의 부재 가드, T25-201 의 툴팁 리터럴 기대값 21 → 20.
- **남긴 것**: 서버 쪽은 그대로다 — `tier1.steps`·`is_committed`·`tier1_is_finished_task`(`SessionView`) 필드와 그 단위 검사는 지우지 않는다(`tier1_is_finished_task` 는 클릭 게이트·빈 패널 사유가 읽는다). 허브 화면은 `steps`·`is_committed` 를 더는 읽지 않지만 서버가 계속 만들어 스냅샷에 싣는다 — 정리는 별도 결정이다.

---

## 4. 영향 범위

### 4.1 코드

| 파일 | 변경 | 결정 |
|---|---|---|
| `hub/bin/hub_template.html` JS | `renderSessionContent` — 호출 순서 meta → `renderSessionExcerpt` → `renderSessionProgress` → `renderAgentRunList` → `renderWorkflowRun`. 주석(「첫 줄·메타·실행·워크플로·진행·발췌」)도 새 순서로 | LM2 |
| 〃 | `renderSessionProgress` — `renderTier1(session.tier1, session.tier1_is_finished_task)` | LM5·LM6 |
| 〃 | `renderTier1` — `.tier1-pct` 안 맨 앞에 칩, 뒤의 `renderTier1ActiveStep` 별도 줄 출력 제거 | LM4·LM5 |
| 〃 | `renderTier1ActiveStep` — **이름 유지**(T25-12 면제행 보존), `.tier1-active` div 대신 칩 HTML 반환. 신설 순수 함수 `tier1StageChipContent` | LM5·LM6 |
| 〃 | 상수 신설 `TIER1_STAGE_SR_LABEL`·`STAGE_AWAITING_COMMIT_LABEL`·`STAGE_AWAITING_COMMIT_TOOLTIP`·`TIER1_COMPLETE_PERCENT`(100) | LM5·LM6 |
| 〃 CSS | 삭제: `.session-row>.session-tier1{order:1}`·`.session-row>.workflow-runs{order:2}`·`.session-card>` 같은 2줄·`.workflow-runs ~ .session-tier1::after{display:block}`·`.tier1-active{…}`·`.session-card .tier1-active{…}`·`body.has-usage .session-modal-dialog{…}` | LM2·LM3·LM4·LM8 |
| 〃 CSS | 변경: 레일 공통 선언 목록에 `.agent-run-list::after`·`.workflow-runs::after` 추가, `.session-tier1::after` 의 `display:none` 제거, `.session-modal{…}` 끝에 3선언, `.session-modal-dialog` 의 margin·height | LM3·LM8 |
| 〃 CSS | 신설: 두 가지의 레일 위치 규칙, `:last-child::after{display:none}` 3선택자, `.tier1-step{…}`, `body.has-usage .session-modal{…}` | LM3·LM5·LM8 |
| 〃 주석 | 머리 주석 TC 문단(159~169행) → 「.tier1-active 는 LM4 로 걷혔다」 한 줄 묘비, 트리 주석의 V7 문장(약 502행)·`.agent-run-list` 주석, 모달 높이 주석(MX7 → LM8), flex 사슬 주석(LM9) | — |
| `hub/bin/hub_parse.py` | `Tier1Snapshot.is_committed: bool = False`(맨 뒤) · 순수 함수 `is_commit_logged_after_last_pass` · `snapshot_from_events` 가 채움. ★순수 모듈 — 주석에도 `open(`·`Path(`·`time.`·`os.` 금지(T25 가드) | LM6(M3) |

`hub_collect`·`hub_model`(asdict 자동)·`hub_session`·`hub_project`·훅·패널 IIFE·`hub_dashboard_template.html` 은 무변경.

### 4.2 정적 가드(T25)와 원장

| 가드 | 지금 무는 것 | 처리 | 원장 |
|---|---|---|---|
| T25-194 | `.session-row>.session-tier1{order:1}`·`…workflow-runs{order:2}` 리터럴 존재 | **개정**: `.session-row{display:flex;flex-direction:column}` 존재 유지 + `renderSessionContent` 본문에서 다섯 호출의 등장 순서(meta < excerpt < progress < runs < workflow) + 역: `>.session-tier1{order`·`>.workflow-runs{order` 0건 | 변조행 유지·sed 교체(발췌 호출을 진행률 뒤로 옮기는 변조) |
| T25-147 | `.tier1-active{` 추출(T25-148 이 이어 씀) + 보조(카드 직계 자식 overflow) | **개정**: 주 추출 삭제, 보조만 남김 | 변조행 유지(sed 가 보조의 `.path` 를 문다 — 무변경) |
| T25-148 | `.tier1-active` 의 `-webkit-box`·`line-clamp:2` | **삭제**(대상 소멸, T25-187·191 선례의 묘비 주석) — 역방향은 T25-263 이 흡수 | 면제행 제거 → `LEDGER_EXEMPT_ROW_RATCHET` 373→372 |
| T25-259 | `.session-card .tier1-active` 4선언·소스 순서 + `.session-card .agent-run-title` 2선언 | **개정**: 실행 줄 제목 2선언만 | 변조행 sed 교체(`-webkit-line-clamp:none` 리터럴이 사라진다 → `.session-card .agent-run-title` 의 `white-space:normal` 을 지우는 변조) |
| T25-258 | `height:calc(100% - 16px)`·사용량 변형 `height`·`max-height` 0건·flex 사슬·li 320px | **개정**: 다이얼로그 `max-height:100%` + `margin:auto` + `height:calc(` 0건, `.session-modal` 의 `display:flex`·`flex-direction:column`·`padding-bottom:16px`, `body.has-usage .session-modal` 의 `padding-bottom:var(--usage-clearance,218px)`, 옛 `body.has-usage .session-modal-dialog{height` 0건. flex 사슬 ②·li ③ 무변경 | 변조행 sed 교체(`max-height:100%` → `height:100%`) |
| T25-12 | `renderTier1ActiveStep` 이름 존재 | 무변경(이름 유지) | 면제행 그대로 |
| T25-127 · T25-250 · T25-239 · T25-197 | 첫 줄 구성 · background_wait 전달 · 모달 블록 앵커 `^  .session-modal{position:absolute` · 1단 레일·진행률 갈고리 리터럴 | 무변경 — `.session-modal{` 는 앞부분을 그대로 두고 뒤에 선언을 붙인다 | — |
| **T25-262**(신설) | 2단 레일 | 정: `.agent-run-list::after`·`.workflow-runs::after` 의 `top:9px;bottom:0`, 세 가지의 `:last-child::after{display:none}`, `.session-tier1::after{top:17px;bottom:0}`(display 없음). 역: `.workflow-runs ~ .session-tier1` 0건 | 변조행 신설 |
| **T25-263**(신설) | 단계 칩 | 정: `renderTier1` 이 `tier1-pct` 문자열 안에서 `renderTier1ActiveStep(` 을 부르고 그 함수가 `agent-chip tier1-step` 을 내며 라벨·툴팁이 `escapeHtml(` 을 거친다, `TIER1_STAGE_SR_LABEL` 사용. 역: `class="tier1-active"` · `^  \.tier1-active\{` 0건(TC 부활 방지) | 변조행 신설 |

래칫(구현 단계가 `collect_guard_ids` 재현으로 재측정해 확정): `SOURCE_GUARD_ID_FLOOR` 524 → **525**(−T25-148 +T25-262 +T25-263) ·
`LEDGER_EXEMPT_ROW_RATCHET` 373 → **372** · `LEDGER_MUTATION_ROW_FLOOR` 100 → **102** · `test_hub_docs_and_constants` 의 설명
「T25-1~T25-261」→「T25-1~T25-263」. 각 상수 주석에 이 PRP 와 증감 사유를 남긴다. **동시 세션 주의**: 신설 번호(262·263)는 가번호다 —
병합 직전 main 의 최대 T25 번호를 다시 센다.

### 4.3 DOM·단위 테스트

| 파일 | 처리 |
|---|---|
| `tests/hub/test_hub_template_dom_modal_cleanup.py` D21 3건 | 개정 — 「높이 = 모달 영역 − 16」·「세션 수 무관 같은 높이」를 「내용이 들어가면 창 = 내용(스크롤 0)·가운데(위아래 간격 차 ≤ 1px)」로. 칸·카드 채움(gapBelowStrip≈0, li 높이 = 칸 내용 높이)·넘침 시 창만 스크롤은 그대로 성립 |
| 〃 D22 | 개정 — `.tier1-active` 측정 삭제, 실행 줄 제목 측정 유지, 긴 제목의 진행률 줄이 두 곳 모두 세로 넘침 0 |
| 〃 D24 | `PROJECT_LEVEL_LINES` 에서 `.tier1-active` 제거(죽은 선택자) |
| 신설 D25·D26·D27 | §6 |
| `tests/hub/test_hub_parse.py` | `is_commit_logged_after_last_pass`·`snapshot_from_events` 의 `is_committed`(M3) |

### 4.4 문서

| 문서 | 갱신 |
|---|---|
| `hub/README.md` 36행 | 「진행률 줄 — … 직전 단계 요약」→「… 단계 진행 앞에 **지금 단계 칩**(마우스를 올리면 직전 기록 요약)」 |
| 〃 「화면 배치」 세션 줄 문단들 | 세션 줄 안의 순서(상태 → 시작·ID·모델 → 발췌 → 진행률 → 실행 줄 → 워크플로 칩) 한 줄 추가, 「세션 줄 아래 발췌」 서술의 위치 표현 정리 |
| 〃 448~454행 카드 상세보기 | 「창은 세션이 몇 개든 같은 크기 … 높이 상한은 두지 않아」→ LM8 거동. 「진행중 단계 … 2줄」 문장 → 실행 줄 제목만 |
| 〃 데이터 모델 표 `commit` 행 | 「허브 표시: 마지막 `pass` 뒤에 있으면 진행률 줄의 『커밋 전』 칩을 거둔다」(M3) |
| `docs/prps/hub-session-modal-cleanup.md` | MX7·MX9 절 끝에 `→ **개정(2026-10)** — hub-session-row-layout-and-modal-size.md 결정 LM8 / LM4` |
| `docs/prps/hub-tier1-clamp-fix-and-session-model.md` | TC2 → `걷힘(LM4) — 대상 .tier1-active 소멸` |
| `docs/prps/hub-tree-view-and-signal-fixes.md` | V7 → `개정(LM2) — 접힘 화면 소멸로 근거가 없어져 DOM 순서를 시각 순서로 맞춘다` |
| `docs/prps/hub-agent-runs-and-prompt-source.md` | AR8 의 「.workflow-runs 와 같은 2단 자식 자리」에 `순서·레일은 LM2·LM3` 한 줄 |
| `docs/images/hub-card-multi-agent-dark.png`·`hub-sample-dark.png` | (선택) 재촬영 — `.tier1-active` 줄이 찍혀 있다. **합성 픽스처로만** 찍는다(옛 이미지 이력의 실데이터 문제) |

상시 컨텍스트(`CLAUDE.md`·`rules/`)는 무변경 — T26 무관.

### 4.5 구현 단계가 헤드리스 Chrome 으로 잴 것(설계는 재지 않았다)

| # | 측정 | 합격 |
|---|---|---|
| R1 | 340px 카드(320 트랙)에서 세션 줄 높이 전후 · 보이는 세션 수 | 보이는 세션 수 ≥ 지금 |
| R2 | 칩이 든 `.tier1-pct` 첫 줄상자 높이 · 진행률 갈고리 바닥선 y vs 그 줄 중앙(목록·상세보기, dsf 1·2, 라이트·다크) | 18px 불변 · ≤ 1px |
| R3 | 레일 접합: 진행률 `::after` 아랫끝 = 실행 줄 `::before` 윗끝, 실행 줄 `::after` 아랫끝 = 워크플로 `::before` 윗끝, 마지막 가지 `::after` 없음 | ≤ 0.5px |
| R4 | 메타 → 발췌, 발췌 → 진행률 간격(발췌에 margin 이 필요한지) | 지금 메타 → 실행 줄 리듬과 시각상 동등. 필요하면 PRP 개정 제안 |
| R5 | 1440×900 세션 1·3·5개, 사용량 패널 유무: 창 높이 = 내용, 위·아래 간격(사용량 있으면 아래는 clearance 기준) | 차 ≤ 1px · 사용량 패널과 겹침 0 |
| R6 | 1024×560 긴 픽스처(D21 기존): 창 = 영역 최대, 창 스크롤, 칸 세로 스크롤 0, 카드 잘림 0 | 지금과 같은 판정 |
| R7 | D20 연결선 접합(스크롤 처음·끝) | 무수정 통과 |
| R8 | 밀어내기(1440 패널 열림)·오버레이(<1024) | 세로 정렬 동일 |
| R9 | 폴링으로 실행 줄 1개가 늘 때 창 윗변 이동량(기록만) | 수치 기록 |

---

## 5. 데이터 모델 · 인터페이스

### 5.1 서버(M3)

```python
@dataclass(frozen=True)
class Tier1Snapshot:
    ...                                   # 기존 필드 무변경
    task_started_at_ms: int | None = None
    # 마지막 pass 기록 뒤에 commit 기록이 있는가(결정 LM6). pass 가 없으면 False. 정적 — D2 안전.
    is_committed: bool = False


def is_commit_logged_after_last_pass(events: tuple[DashboardEvent, ...]) -> bool:
    """마지막 pass 기록 뒤에 commit 기록이 있는가(결정 LM6). pass 가 없으면 False."""
```

`snapshot_from_events` 는 `is_committed=is_commit_logged_after_last_pass(later_events)` 를 넘긴다. 스냅샷 JSON 의
`sessions[].tier1.is_committed`·`projects[].tier1.is_committed` 로 자동 직렬화된다(템플릿은 세션 쪽만 읽는다 — MX4).

### 5.2 템플릿(JS — 모든 공개 함수에 한 줄 주석)

```js
// 순수 — 진행률 줄 앞 단계 칩의 내용. 진행중 단계 → {label: 단계명, tooltip: detail}, 진행중 단계가 없고
// 100% · 커밋 기록 없음 · 끝난 작업 아님 → {label: STAGE_AWAITING_COMMIT_LABEL, tooltip: STAGE_AWAITING_COMMIT_TOOLTIP}, 그 밖 null.
function tier1StageChipContent(tier1, isFinishedTask)   // → {label: string, tooltip: string} | null
// 단계 칩 HTML — 내용이 없으면 ''. tooltip 이 빈 문자열이면 data-tooltip 을 달지 않는다(R4).
function renderTier1ActiveStep(tier1, isFinishedTask)   // → string   (이름 유지 — T25-12)
// 진행률 줄(칩 + 제목 — 완료/전체 · %) + 구현 세부.
function renderTier1(tier1, isFinishedTask)              // → string
function renderSessionProgress(session)                  // → string   시그니처 불변
function renderSessionContent(session)                   // → string   순서만 변경(LM2)
```

```js
var TIER1_STAGE_SR_LABEL = '현재 단계 ';
var STAGE_AWAITING_COMMIT_LABEL = '커밋 전';
var STAGE_AWAITING_COMMIT_TOOLTIP = '전 단계를 마쳤습니다 — 아직 커밋 기록이 없습니다.';
var TIER1_COMPLETE_PERCENT = 100;   // 서버 산식 round(완료/전체 × 100) 의 완료값
```

M3 를 빼는 경우 `tier1StageChipContent` 의 둘째 분기만 없다(`tier1.is_committed` 를 읽지 않는다) — 나머지 시그니처는 같다.

---

## 6. 테스트 계획

**DOM 행동(헤드리스 Chrome, `template_dom_harness`)** — 단독 실행으로 먼저 가른다(동시 부하에 약하다).
- D25 순서: 카드 목록 줄·상세보기 카드에서 자식 클래스 순서가 `session-line, session-meta, excerpt, session-tier1, agent-run-list, workflow-runs`
  (있는 것만)이고, 각 자식의 `getBoundingClientRect().top` 이 DOM 순서대로 증가한다(DOM = 시각). 발췌 없음·실행 줄 없음·워크플로 없음 조합.
- D26 레일: §4.5 R3 의 접합을 세 조합(진행률만 / 진행률+실행 / 진행률+실행+워크플로 / 진행률+워크플로)에서. 마지막 가지 `::after` 의
  `display` 가 `none`.
- D27 단계 칩(§3 LM5 표의 행마다 픽스처 1개): 칩 텍스트(`검수`/`승인`/`커밋 전`/없음), `data-tooltip` 유무(detail 빈 값이면 없음),
  `.sr-only` 「현재 단계 」, 대시보드 없음이면 칩 0개·`대시보드 없음` 1개, `tier1_is_finished_task` 면 칩 0개, 단계명에 `<b>` 가 든
  픽스처가 텍스트로 그려진다(escape). 백그라운드 대기 세션 + 실행 줄 없음에서 칩이 보인다(요구 3 의 핵심 회귀).
- D21(개정) §4.3 · D22(개정) · D24(선택자 정리) · D20(무수정 통과 확인).

**단위(stdlib unittest, M3)** — `is_commit_logged_after_last_pass`:
pass 없음 → False · pass → False · pass, commit → True · pass, note, commit → True · pass, commit, note → True ·
pass, commit, fail, impl, pass → False(재검수 뒤 커밋 전) · commit 만(pass 없음) → False. `snapshot_from_events` 가 그 값을 담고,
`asdict` 결과에 키가 있다.

**정적(T25)** — §4.2 의 개정 4건(T25-194·147·259·258)·삭제 1건(T25-148)·신설 2건(T25-262·263). 원장 변조행은 「가드를 고의로 깨면
실패한다」를 T37-15 가 확인한다(K6 증분이 해당 행을 고른다). 전체 검증은 메인 세션이 커밋 직전 1회.

---

## 7. 마일스톤

| M | 내용 | 결정 | 검사 |
|---|---|---|---|
| M1 | 순서(DOM)·레일 | LM2·LM3 | T25-194 개정 · T25-262 · D25·D26 · README 순서 · V7·AR8 표기 |
| M2 | `.tier1-active` 걷기 · 단계 칩 | LM4·LM5 | T25-147·T25-259 개정 · T25-148 삭제 · T25-263 · D22·D24·D27(커밋 전 제외) · README 36·454행 · TC2·MX9 표기 |
| M3 | 「커밋 전」 사실·칩 | LM6 | test_hub_parse · D27 커밋 전 행 · README 데이터 모델 표 |
| M4 | 창 높이 | LM8·LM9 | T25-258 개정 · D21 · README 448~452행 · MX7 표기 |

---

## 8. 위험과 대안

| # | 위험 | 대응 |
|---|---|---|
| R-1 | 칩이 진행률 줄상자를 키워 2단 갈고리(17px)가 어긋난다 | 인라인 세로 패딩은 줄상자에 기여하지 않고 칩 글꼴(11px·1.3)이 줄 높이(12px·1.5=18)보다 작다 — 목업 2배 확대에서 정렬 확인. R2 로 수치 확정 |
| R-2 | `:last-child` 가 마지막 가지가 아닌 요소를 가리킨다 | 진행률 노드가 늘 렌더되고 발췌 뒤에 오므로 버튼의 마지막 요소는 항상 가지다 — D26 이 문다. 버튼 끝에 새 형제를 더하는 변경은 이 전제를 깬다(T25-262 주석에 남긴다) |
| R-3 | (재개정 전 서술 — 지금은 윗변 고정, 아래로만 자란다) 가운데 정렬 창이 갱신 때 위아래로 움직인다 | 높이를 바꾸는 갱신은 실행 줄·워크플로 칩 증감뿐(경과 텍스트는 높이 불변), 최대 분당 1회. R9 로 기록. 거슬린다는 보고가 오면 위 정렬(4A)로 되돌리는 것이 한 줄 변경이다 |
| R-4 | 「커밋 전」이 커밋을 안 하는 흐름에서 오래 남는다 | `tier1_is_finished_task` 가 켜지면 거둔다. 남는 동안의 서술(검수 통과 뒤)은 참이다 |
| R-5 | 긴 발췌가 340px 카드에서 가지를 민다 | 중앙값 23자. 후속 후보(LM10) |
| R-6 | 가드 번호 충돌(동시 세션) | §4.2 가번호 — 병합 직전 재계산 |

검토했으나 채택하지 않은 큰 대안: (i) 단계명을 상태 배지 옆으로(LM5-C), (ii) 클라이언트 단독 「마무리 중」 추정(LM6), (iii) 창 높이 바닥값(LM8-4D).

## 9. 미결 질문(최소)

1. LM6(M3) — 검수 통과 뒤 커밋 전 구간에 「커밋 전」 칩을 넣기 위해 진행 기록 파서에 사실 하나(`is_committed`)를 더한다. 넣을지
   (권고: 넣는다 — 사용자가 본 T37 구간이 바로 이 구간이다). 빼면 그 구간은 「4/4 · 100%」만 보인다.
2. 칩 라벨 「커밋 전」 — 대안 「마무리」(커밋을 단정하지 않음). 권고는 「커밋 전」(기록된 사실과 같은 말).
