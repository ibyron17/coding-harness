# 허브 UI — 카드/트리 보기 이원화 통합 (PRP)

> 상태: **설계 (미승인).** 이 문서는 코드를 바꾸지 않는다. §12 의 열린 질문에 대한 사용자
> 승인 전에는 구현을 시작하지 않는다.
>
> 대상: `hub/bin/hub_template.html` 한 파일의 UI 계층 + 그 계약을 잠그는 `tests/run.sh` +
> `hub/README.md`. **스냅샷 JSON 계약(`hub_model`·`hub_project`·`hub_session`)은 바꾸지
> 않는다**(§6 에서 명시적으로 판정한다).
>
> **후속 반려(2026-09-10).** 이 PRP 는 승인·구현·검수·머지를 거쳤다(PR #12). 그 산출물을
> 사용자가 보고 3건을 반려했다 — halo 위치(§9.1 U8), 확장부가 트리가 아니라 리스트로
> 보인 것(§9.1 U2), 세션 행 선택 배경 여백. 처분과 근거는
> `docs/prps/hub-tree-view-and-signal-fixes.md` 에 있다. 아래 본문은 **당시 판단의 기록으로
> 보존**한다(공개 번복 관례 — SP19→SP4, ST17→U1 의 선례를 이 문서 자신이 따른다).

---

## 1. 요구사항 요약

허브는 지금 **카드 보기**와 **트리 보기** 두 화면을 헤더 토글로 오간다(결정 ST17·ST18).
사용자가 트리 보기에서 결함 4건, 카드 보기에서 결함 1건을 보고했고, 두 화면 중 **어느
쪽도 단독으로는 쓸 수 없는 상태**다 — 카드는 세션별 대시보드에 닿지 못하고(문제 5), 트리는
세션이 4개만 넘어도 가로로 흘러 읽을 수 없다(문제 2·3·4). 이 PRP 는 **모드 이원화 자체를
폐기**하고 카드 한 화면으로 통합한다. 세션은 카드 안의 **세로 행**이 되고, 그 행이 곧 세션
대시보드의 진입점이며, 카드는 필요할 때 **펼쳐서** 모든 세션을 한눈에 보여준다.

### 1.1 사용자 보고 (원문 5건)

| # | 보고 | 어디 |
|---|------|------|
| 1 | 어떤 세션이 진행중인지 파악 안됨. 카드 보기처럼 glow 애니메이션 필요 | 트리 |
| 2 | 메인 세션 카드가 너무 작아서 보기 불편함 | 트리 |
| 3 | 메인 세션이 많으면 좌우 스크롤 발생. 한눈에 파악 안됨 | 트리 |
| 4 | 뒤쪽 세션을 보고 있는데 화면이 갱신되면 스크롤이 이동해 보던 카드가 사라짐 | 트리 |
| 5 | 카드 보기에서는 메인 세션이 2개 이상일 때 다른 세션의 대시보드를 볼 수 없음 | 카드 |

### 1.2 원인 (메인 세션 실측 — 재조사하지 않고 출발점으로 쓴다)

| # | 원인 | 근거 |
|---|------|------|
| 1 | `.card-working` 을 붙이는 곳은 `renderProject` 뿐이다. `renderProjectTree`·`renderSessionNode` 는 안 붙이고, CSS 도 `.card.card-working` 스코프라 `.tree-section`·`.tree-node` 에 닿지 않는다 | 실측 |
| 2 | `.tree-node{width:200px;min-height:160px}` 대 `.tree-root{width:460px}`. 실제 노드 높이 160~183px | 실측 |
| 3 | `.tree,.tree ul{display:flex;justify-content:safe center}` + `#dzh-app>.tree-section{overflow-x:auto}`. 뷰포트 820px·패널 닫힘에서 섹션 `clientWidth` 786px, 세션 `<li>` 1개 212px(200 + `.tree li` 좌우 패딩 6px×2) → **3개까지만 들어가고 4개째부터 가로 스크롤**. 패널(`--dzh-panel-width:550px`)이 열리면 더 빨리 넘친다 | 실측 |
| 4 | `render()` 가 매번 `app.innerHTML` 을 통째로 교체하고(불변식 H1⁗), `setInterval(render, TICK_MS)` 가 데이터 변화와 무관하게 30초마다 무조건 부른다. `.tree-section` 이 새 DOM 노드가 되어 `scrollLeft` 가 0 이 되고, 이어서 `initializeTreeRootScrollPositions()` 가 **매 렌더 루트를 다시 중앙정렬**한다 | 실측 |
| 5 | 카드는 `project.dashboard_key` 하나만 싣는다. 그 값은 `hub_project.project_dashboard_key(path)` 이고 서버가 **mtime 최신 대시보드 파일**에 매핑한다(WT6·ST11). 세션별 `session.dashboard_key`(ST12)는 **트리 모드의 `.tree-node` 에만** 실린다 | 실측 |

추가 실측: 트리 모드에서 프로젝트당 섹션 높이가 318~438px 이라 프로젝트 6개면 세로 약 2,200px 다.
스냅샷 실측: coding-harness 6세션 중 자기 대시보드 보유 2 · working 2, NotebookWiki 4세션 중 보유 2 ·
working 1 — **「한 프로젝트에 대시보드를 가진 세션이 2개 이상」은 흔한 상태다.**

### 1.3 성공 기준

1. 보기 모드 토글이 없다. 화면이 하나다.
2. 세션 대시보드가 **확장 여부와 무관하게** 카드에서 도달 가능하다(문제 5).
3. 가로 스크롤 컨테이너가 `#dzh-app` 안에 하나도 없다(문제 3·4).
4. 재렌더가 사용자가 보던 위치를 잃지 않는다 — 잃을 스크롤 상태를 만들지 않는 방식으로(문제 4).
5. 세션 행 하나만 봐도 그 세션이 진행중인지 즉시 안다(문제 1).
6. 세션 표현이 200px 상자가 아니라 카드 폭(320~460px)을 쓴다(문제 2).
7. `tests/run.sh`·`tests/hub`·`tests/commands` 전부 통과. 새 외부 의존성 0, 새 색 리터럴 0.

---

## 2. 사용자 제안에 대한 판정 — **변형 채택**

> 사용자 제안: 「카드/트리 보기 모드의 구분을 없애고, 기본 모드로 카드 보기 형태로 제공하고
> 특정 카드를 클릭 시 2개 이상의 메인 세션이 있는 경우 해당 카드에 대한 트리 뷰를 확장해서
> 보여주는 방식은 어떨까?」

**채택하는 부분**(제안의 핵심):

- 모드 이원화 폐기, 카드 한 화면. → 결정 **U1**
- 프로젝트 단위 **온디맨드 확장**으로 세션 상세를 연다. → 결정 **U4**

**변형하는 부분 3가지와 그 근거**:

### 변형 ① 확장 제스처는 「카드 클릭」이 아니라 전용 셰브론 버튼이다 (결정 U5)

「카드 클릭」은 이미 **상세 패널 열기**에 배정돼 있다. 이것은 우연이 아니라 세 결정이 겹쳐
만든 계약이다 — OC5(클릭 가능 ⇔ 패널에 보여줄 것이 있다), OC11(모든 카드의 `.project-name`
이 `<button>`), ST26(노드 아닌 여백을 눌러도 프로젝트 요약이 열린다). 같은 클릭에 「확장」을
겹치면 두 동작 중 어느 쪽도 예측 불가가 된다.

| 안 | 평가 |
|----|------|
| A. 카드 클릭 = 확장, `.project-name` 클릭 = 패널 | OC5 를 정면으로 뒤집는다. 「카드 어디를 눌러도 대시보드가 열린다」는 이 허브의 **주 동작**이고, 그것을 부 동작(확장)에 내주면 hub-panel-empty-state-and-open-card PRP 가 고친 「클릭이 조용히 실패한다」의 사촌이 된다 |
| B. 클릭 = 패널, 더블클릭/롱프레스 = 확장 | 발견 불가능한 제스처. 이 문서는 우클릭·텍스트 선택까지 잠근 상태(IL1~IL7)라 숨은 제스처를 더할 자리가 아니다 |
| **C. 전용 셰브론 버튼(채택)** | 카드 클릭 계약이 **한 글자도 안 바뀐다.** `.card-drag-handle` 이 이미 세운 선례 그대로다 — 카드 안에 카드 전체 클릭과 겹치지 않는 전용 컨트롤을 두고, 패널 IIFE 의 클릭 리스너가 `closest` 로 조기 반환한다(결정 N6 과 같은 형태) |

> **결정 U5 — 안 C.** 셰브론은 `.project-head` 의 마지막 자리(`.last-activity` 뒤)에 둔다.
> 세로 증분 0px — `.card{height:340px}` 는 **문제 3 이 다투는 바로 그 희소 자원**이라(세션이
> 몇 개 보이는가) 하단 전폭 바(+약 24px, 미실측)를 쓰지 않는다. 세션 개수는 버튼의
> `aria-label`·`data-tooltip` 이 문구로 싣는다(결정 X1·R4 의 관례 — 보이는 텍스트를 늘리지
> 않고 보조 정보를 속성에 둔다).

### 변형 ② 확장은 「트리 뷰」가 아니다 — 가로 조직도 은유를 버린다 (결정 U2)

문제 2·3 의 원인은 트리의 **구현 세부**가 아니라 **은유 자체**다. 가로 조직도는 세션 수에
비례해 가로로 자라는데, 이 화면의 가로 폭은 3열 그리드와 550px 상세 패널이 이미 나눠 쓰고
있어 늘릴 수 없다. 그래서 구현 중에도 우회가 두 겹 필요했다 — `justify-content:safe center`
(원안 `center` 는 넘치는 순간 첫 노드를 음수 스크롤 영역으로 밀어냈다)와
`initializeTreeRootScrollPositions()`(safe center 로도 정지 상태에서 루트가 안 보였다).
**두 겹의 우회가 필요했다는 사실 자체가 은유가 이 화면에 안 맞는다는 신호다.** 그리고 그
두 번째 우회가 지금 문제 4 의 직접 원인이다.

> **결정 U2 — 세션 표현은 카드 안의 세로 행(`.session-row`)이다.** 연결선(`.tree li::before`
> 계열 8규칙)·가로 스크롤(`overflow-x:auto`)·중앙정렬 보정 함수를 전부 삭제한다. 세로 목록은
> 카드가 **이미 갖고 있는 표현**이라(`.sessions` `<ul>`) 새 은유를 도입하지 않는다.
> 아코디언은 카드 자신이 겸한다(§변형 ①·결정 U4).
>
> → **부분 번복(2026-09-23, 카드 상세보기 모달 범위)** — hub-session-modal-and-partial-update.md
> 결정 SC12. 카드 안 세로 목록은 유지

### 변형 ③ 확장 게이팅은 「세션 ≥ 1」이다 (세션 ≥ 2 아님) (결정 U6)

사용자 제안은 「2개 이상의 메인 세션이 있는 경우」였다. 그러나 세션 1개짜리 프로젝트에서도
확장은 할 일이 있다 — 그 세션의 진행률(`session.tier1`)과 잘리지 않은 발췌를 보여준다.
「셰브론이 어떤 카드에는 있고 어떤 카드에는 없다」는 사용자가 외워야 할 규칙이고, 그 규칙의
임계값(2)은 화면 어디에도 안 적혀 있다.

> **결정 U6 — `visibleSessionsOf(project).length >= 1` 이면 셰브론을 그린다.** 0 이면 안
> 그린다(티어 3 프로젝트 — 펼칠 것이 없다). 데이터가 어포던스를 정하는 것은 결정 N2 의 관례고,
> 속성 존재만으로 커서·표시를 정하는 `[data-dashboard-key]{cursor:pointer}` 와 같은 형태다.
> → **열린 질문 2**(사용자 제안대로 2 로 할 것인지).

### 기각한 더 단순한 안

| 안 | 왜 기각했나 |
|----|-------------|
| **확장 없이 세션 행만 클릭 가능하게** (제안보다 단순) | 문제 1·2·5 와 4 의 대부분을 해결하고 확장 개념이 통째로 없다. 그러나 문제 3 의 「한눈에」를 못 푼다 — 340px 카드에 세션 6개면 3~4개가 `.sessions{overflow-y:auto}` 안에 숨고, **그 내부 스크롤이 재렌더마다 초기화돼 문제 4 가 세로 축으로 되살아난다.** 확장의 존재 이유가 정확히 이것이다(§9 결정 U4) |
| **트리를 고쳐 쓰기**(노드 폭 확대 + 세로 배치 + glow 추가) | 두 화면을 유지하므로 문제 5 가 그대로 남는다. 그리고 「세로로 배치된 트리」는 카드의 세션 목록과 같은 것이라, 두 벌을 유지할 이유가 사라진다 |
| **패널 상단 세션 전환기**(ST17 의 옛 안 C) | ST17 이 이미 기각했다 — 패널 IIFE 가 스냅샷을 알아야 해서 G8/SP1 을 깬다. 이 PRP 는 그 결정을 유지한다 |

---

## 3. 영향 범위 (파일별)

| 파일 | 조치 | 이유 |
|------|------|------|
| `hub/bin/hub_template.html` | UPDATE | 이 변경의 전부. 머리 주석(H1⁗ ③·패널 신원 문단·트리 문단) + `<style>`(트리 CSS 삭제, 확장·세션 행 CSS 신설) + 헤더 마크업(`#dzh-view-toggle` 삭제) + 렌더 IIFE(트리 5함수·보기 모드 4함수 삭제, 확장 상태 4함수·세션 행 렌더 개정) + 드래그 3리스너 스코프 수정 + 패널 IIFE(가드 1줄 교체) |
| `tests/run.sh` | UPDATE | T25-159·T25-160·T25-162·T25-127 개정, T25-169a~g 삭제, 신규 가드(§10.2). 래칫 상수 2종 재확인(§10.4) |
| `tests/mutations.tsv` | UPDATE | 삭제 가드의 변조행 7건 제거, 개정 가드의 면제행 → 변조행 승급, 신규 가드마다 변조행 1건 |
| `hub/README.md` | UPDATE | 「화면 배치」의 보기 토글·트리 문단(약 8줄)을 확장·세션 행 서술로 교체. 문서 정합 가드가 `우하단`·`접기`·`그리드`·`서브에이전트`·`툴팁` 토큰을 물고 있으므로 이 낱말들은 남긴다 |
| `hub/bin/hub_model.py`·`hub_project.py`·`hub_session.py` | **무변경** | §6 판정 |
| `tests/hub/*.py`(655건) | **무변경** | 전수 확인: 이 디렉토리의 `tree` 매치는 전부 「워크트리」와 `ast.parse` 다. 트리 UI 셀렉터를 무는 파이썬 테스트는 없다 |
| `commands/hub.md`·`commands/dashboard.md` | **무변경** | 트리 UI 를 언급하지 않는다 |

---

## 4. 화면 설계

### 4.1 Before / After

**Before — 두 화면**

```
[카드 모드]                                      [트리 모드]  ← 헤더 토글로만 오간다
┌ coding-harness  [T1][●작업중]   3분 전 ┐          ┌ coding-harness ────────────────────────────┐
│ /Users/…/coding-harness                │          │        ┌────────────┴────────────┐     │
│ 릴리스 트랙 — 1/9 · 11%             │          │   ┌────┴───┐  ┌────┴───┐  …▸ 가로 스크롤 │
│ ─────────────────────────────────  │          │   │ 200px  │  │ 200px  │              │
│ [●작업중] 3분 전  [design][impl]    │  ← 클릭 불가 │   └────────┘  └────────┘              │
│ 시작 09:52 · 63ad8669 · Opus 5      │          └────────────────────────────────────────┘
│ 「권고안대로 진행해…」               │          · 노드 4개째부터 가로 스크롤(실측)
│ ─────────────────────────────────  │          · glow 없음 — 어느 세션이 도는지 모른다
│ [○대기] 16분 전                     │          · 30초마다 스크롤이 되감긴다
│ ⋮ (내부 스크롤)                     │
└────────────────────────────────────┘
   ↑ 카드 클릭 = 프로젝트 대시보드(mtime 최신 1개)
```

**After — 한 화면, 두 상태**

```
[접힘 — 기본. 오늘 카드와 픽셀 단위로 같다 + 셰브론 1개]
┌ ⠿ coding-harness  [T1][●작업중]   3분 전  ▸ ┐   ← ▸ = 확장 셰브론(전용 버튼)
│ /Users/…/coding-harness                     │
│ 릴리스 트랙 — 1/9 · 11%                  │
│ ────────────────────────────────────── │
│ ▌[●작업중] 3분 전  [design][impl]        │   ← 행 전체가 버튼. 클릭 → 이 세션의 대시보드
│  시작 09:52 · 63ad8669 · Opus 5         │   ← ▌= 진행중 신호(§8 결정 U8)
│  「권고안대로 진행해…」                    │
│ ────────────────────────────────────── │
│  [○대기] 16분 전                         │
│ ⋮ (오늘과 동일한 내부 스크롤)              │
└─────────────────────────────────────────┘

[펼침 — 셰브론 클릭. 카드가 height:auto 로 자라고 세션 전부 + 세션별 진행률]
┌ ⠿ coding-harness  [T1][●작업중]   3분 전  ▾ ┐
│ /Users/…/coding-harness                     │
│ 릴리스 트랙 — 1/9 · 11%                  │
│ ────────────────────────────────────── │
│ ▌[●작업중] 3분 전  [design][impl]        │
│  시작 09:52 · 63ad8669 · Opus 5         │
│  허브 세션 트리 — 2/4 · 50%   ← 펼침 전용 │
│  설계 — PRP 작성 중          ← 펼침 전용 │
│  「권고안대로 진행해…」                    │
│ ────────────────────────────────────── │
│  [○대기] 16분 전                         │
│  시작 10:01 · 4dba59f0 · Opus 5         │
│  대시보드 없음               ← 펼침 전용 │
│ ────────────────────────────────────── │
│  … (전부. 내부 스크롤 없음)                │
└─────────────────────────────────────────┘
```

### 4.2 상태와 전이

상태는 **직교하는 셋**이며 서로를 덮지 않는다.

| 상태 | 사는 곳 | 값 | 시각 채널 |
|------|---------|-----|----------|
| 확장(프로젝트별) | `expandedProjectPaths`(모듈) + `localStorage['dzh-expanded-projects']` | `string[]` | `.card.card-expanded` + 셰브론 회전 + `aria-expanded` |
| 열림(패널 대상) | 패널 IIFE 의 `openPanelTarget`(변경 없음, ST23) | `PanelTarget \| null` | `.card-open` 면색(`--accent-soft`) + `aria-current="true"` |
| 진행중(스냅샷 파생) | 스냅샷. 상태를 저장하지 않는다 | `state === 'working'` | 카드: 기존 `.card-working`(무변경) · 행: 배지 halo(결정 U8) |

전이:

```
접힘 ──셰브론 클릭──▶ 펼침         (상태 저장 + 클래스 토글. render() 를 부르지 않는다 — 결정 U7)
펼침 ──셰브론 클릭──▶ 접힘
어느 상태든 ──폴링/30초 틱──▶ 같은 상태  (renderProject 가 저장된 상태에서 클래스를 다시 그린다)
어느 상태든 ──카드 여백 클릭──▶ 패널: 프로젝트 요약   (신원 sessionId=null)
어느 상태든 ──세션 행 클릭──▶ 패널: 그 세션의 대시보드 (신원 sessionId=세션 ID)
어느 상태든 ──셰브론 클릭──▶ 패널 상태 불변          (패널 IIFE 가 조기 반환 — GOTCHA 2)
```

**클릭 우선순위는 새 개념이 아니다.** `event.target.closest(CLICKABLE_CARD_SELECTOR)` 가 가장
안쪽 요소를 고른다 — 행 안을 누르면 행, 행 밖 카드 여백을 누르면 카드. ST26 이 `.tree-node`
대 `.tree-section` 에 대해 정한 규칙 그대로이며, 담체 이름만 바뀐다.

### 4.3 접힘 상태의 무회귀 성질

접힘 카드는 **셰브론 1개를 뺀 나머지가 오늘과 같아야 한다.** 이것이 이 설계의 안전망이다 —
가장 자주 쓰는 스캔 화면을 바꾸지 않는다.

- `.card{height:340px}`·`#dzh-app` 3열 산술·`gap:12px` 무변경(W1·W2·D10 유지).
- `.sessions{overflow-y:auto}` 무변경 — 접힘에서 넘치는 세션은 오늘처럼 내부 스크롤된다.
- 세션 행이 `<button>` 이 되면서 브라우저 기본 스타일이 들어온다 → `font:inherit;padding:0;
  border:0;background:none;text-align:left;width:100%;display:block` 로 리셋한다(`.project-name`·
  `.usage-toggle` 이 이미 쓰는 관용구). **줄 높이가 1px 이라도 늘면 접힘 카드에 보이는 세션
  수가 줄어든다** — MC1~MC5 가 `.session-id` 칩에서 실측으로 확인한 함정이다. 구현 시 헤드리스
  실측으로 「보이는 세션 수 불변」을 확인한다(§11 검증 1). 현재 값은 미실측.
- 새로 생기는 차이는 의도된 것 둘뿐이다: 행의 `cursor:pointer`·hover, 그리고 진행중 행의 halo.

---

## 5. 파일 구조와 모듈 경계

경계는 **바꾸지 않는다.** 이 변경은 기존 세 IIFE 의 경계 안에서 끝난다.

```
hub_template.html
├── <style>                  … 트리 규칙 삭제, 확장·세션 행 규칙 신설
├── 헤더 정적 마크업          … #dzh-view-toggle 삭제 (H1⁗ 정적 노드 목록에서도 제거)
├── 테마 IIFE                 … 무변경
├── 툴팁 IIFE                 … 무변경 (행 안의 배지·칩·발췌 트리거는 document 위임이라 그대로 동작)
├── 상호작용 잠금 IIFE        … 무변경
├── 렌더 IIFE                 … 확장 상태 소유. 스냅샷을 안다. 패널을 모른다
└── 패널 IIFE                 … 무변경 + 가드 1줄 교체. 스냅샷을 여전히 모른다
```

**두 IIFE 가 서로의 변수를 모른다는 원칙(OC8·SP1·G8)은 유지된다.** 확장 상태는 렌더 IIFE
안에서만 살고, 패널 IIFE 는 그 존재를 모른다 — 패널이 확장 상태에 관심을 가질 이유가 없기
때문이다(열린 행이 접힌 카드 안에 있어도 `.card-open` 표시는 정상적으로 붙는다. 화면에 안
보일 뿐이고, 그것은 오늘 `.sessions` 내부 스크롤 밖의 행과 같은 성질이다).

---

## 6. 데이터 모델 — **변경 없음** (판정)

| 필요한 값 | 이미 있는가 | 출처 |
|-----------|------------|------|
| 세션별 대시보드 서빙 키 | **있다** | `SessionView.dashboard_key`(`hub_project._session_dashboard_key`, ST12) |
| 세션별 진행률 | **있다** | `SessionView.tier1: Tier1Snapshot \| None`(ST12) |
| 세션 신원·표시값 | **있다** | `session_id` · `short_id` · `started_at_ms` · `state` · `base_state` · `last_event_at_ms` · `task_excerpt` · `agent_runs` · `model` · `workflow` |
| 세션별 대시보드 서빙 경로 | **있다** | `hub_model` 이 레지스트리에 `session.dashboard_key` 를 이미 등록한다 — `/project/<key>/dashboard.html` 이 세션 키로도 응답한다(ST14) |
| 프로젝트 확장 여부 | **클라이언트 상태다** | 스냅샷에 넣지 않는다 — 사용자 상태이고, 스냅샷에 넣으면 `snapshot_content_key` 가 사용자 조작마다 바뀌어 `hub.html` 쓰기 억제(R3)를 무력화한다 |

> **판정: 스냅샷 JSON 계약을 바꾸지 않는다.** 서버·파이썬 레이어는 한 줄도 손대지 않는다.
> 이 결함 5건은 전부 **템플릿이 이미 받고 있는 데이터를 안 쓰거나 잘못 배치해서** 생긴 것이다.

클라이언트 상태 타입(모듈 스코프):

```js
// expandedProjectPaths: string[]   — 펼쳐진 프로젝트의 path. 순서는 의미 없다.
//                                    localStorage['dzh-expanded-projects'] 에 JSON 배열로 산다.
//                                    상한 MAX_STORED_EXPANDED_PROJECTS(=200, MAX_STORED_PROJECT_ORDER 와 같은 값·같은 이유).
```

---

## 7. 인터페이스 (함수 시그니처 수준)

### 7.1 삭제

| 함수/상수 | 사유 |
|-----------|------|
| `renderProjectTree(project)` · `renderTreeRoot(project)` · `renderSessionNode(project, session)` · `renderAgentLeaf(run)` | 트리 폐기(U2) |
| `centerTreeRootIfOverflowing(section)` · `initializeTreeRootScrollPositions()` | 가로 스크롤 폐기 → 보정 대상 소멸(문제 4 의 직접 원인) |
| `readStoredViewMode()` · `persistViewMode(mode)` · `applyViewModeButton(mode)` · `setViewMode(nextMode)` | 모드 폐기(U1) |
| `VIEW_MODE_STORAGE_KEY` · `VIEW_MODE_CARDS` · `VIEW_MODE_TREE` · `VIEW_MODE_CYCLE` · `VIEW_MODE_ACTION_LABEL` · `viewToggleButton` | 〃 |
| `SESSION_NO_DASHBOARD_LABEL` · `SESSION_NO_DASHBOARD_REASON` · `sessionPanelEmptyReason(session, isClickable)` | **삭제하지 않는다** — 세션 행이 그대로 쓴다 |

### 7.2 신설 (전부 순수 함수 + 얇은 적용 함수 1개)

```js
// ── 저장소 경계 (readStoredProjectOrder·persistProjectOrder 와 같은 try/catch 관례) ──
function readStoredExpandedProjects(): string[]
    // localStorage 실패·비배열·비문자열 원소는 전부 [] 로 낙착한다(무회귀 기본값 = 전부 접힘)

function persistExpandedProjects(paths: string[]): void

// ── 순수 로직 (단위 테스트 대상, §10.3) ──
function isProjectExpanded(expandedPaths: string[], projectPath: string): boolean

function nextExpandedProjects(expandedPaths: string[], projectPath: string): string[]
    // 토글 결과를 **새 배열**로 돌려준다 — 원본을 변형하지 않는다(user rules 불변성).
    // 있으면 빼고 없으면 앞에 넣는다. slice(0, MAX_STORED_EXPANDED_PROJECTS) 로 자른다.

function expandToggleLabel(isExpanded: boolean, sessionCount: number): string
    // 예: 접힘 → "세션 6개 모두 보기", 펼침 → "세션 목록 접기"
    // aria-label·data-tooltip 이 같은 문자열을 쓴다(applyViewModeButton 이 쓰던 관례).

// ── 렌더 (문자열 반환 순수 함수) ──
function renderExpandToggle(isExpanded: boolean, sessionCount: number): string
    // sessionCount === 0 이면 '' (결정 U6)

function sessionRowAttributes(project: ProjectView, session: SessionView): string
    // ST26 의 속성 집합. renderSessionNode 가 하던 일을 그대로 옮긴다:
    //   data-project-path · data-project-name · data-session-id · data-session-short-id
    //   + (data-dashboard-key | data-panel-empty-reason)  ← if/else 강제 지점(불변식 OC-A)
    //   + data-tooltip(file:// 모드에서 dashboard_key 는 있는데 서버가 꺼진 경우)

function renderSessionProgress(session: SessionView): string
    // <div class="session-tier1"> 로 감싼 renderTier1(session.tier1, false)
    // session.tier1 이 없으면 SESSION_NO_DASHBOARD_LABEL 한 줄.
    // **접힘/펼침 분기를 JS 가 하지 않는다** — 항상 그리고 CSS 가 감춘다(결정 U9)

// ── 적용 (DOM 에 닿는 유일한 신설 함수) ──
function applyCardExpandedState(cardElement: Element, isExpanded: boolean): void
    // 클래스 1개 + 셰브론 버튼의 aria-expanded 1개. applyUsageCollapsedState 와 같은 층위.
```

### 7.3 개정

```js
function renderSession(project, session): string      // ← 시그니처 변경 (session) → (project, session)
    // 반환: '<li><button type="button" class="session-row' + workingClass + '"' + attrs + '>'
    //         <div class="session-line"> …오늘과 문자 단위로 같은 구성… </div>
    //         + renderSessionMeta(session)
    //         + renderWorkflowRun(session.workflow)
    //         + renderSessionProgress(session)          ← 신설. .session-meta 뒤·발췌 앞
    //         + renderSessionExcerpt(displayableExcerpt(session.task_excerpt))
    //       + '</button></li>'
    // 첫 줄(.session-line) 구성은 한 글자도 안 바뀐다 — T25-127 이 그 불변을 문다.

function renderProject(project): string
    // 변경 3곳: ① .project-head 끝에 renderExpandToggle
    //           ② 카드 클래스에 isProjectExpanded 파생 클래스 추가
    //           ③ visibleSessions.map(renderSession) → map(function(s){ return renderSession(project, s); })

function render(): void
    // 변경 2곳: viewMode 분기 삭제(항상 renderProject) · initializeTreeRootScrollPositions() 호출 삭제
```

### 7.4 리스너

```js
// 렌더 IIFE — 확장 토글(문서 위임. 카드는 렌더마다 전멸하므로, 결정 O7 관례)
document.addEventListener('click', function(event){
  var toggle = event.target.closest(EXPAND_TOGGLE_SELECTOR);
  if(!toggle) return;
  var card = toggle.closest(CARD_SELECTOR);
  if(!card) return;
  var projectPath = card.getAttribute(PROJECT_PATH_ATTRIBUTE);
  expandedProjectPaths = nextExpandedProjects(expandedProjectPaths, projectPath);
  persistExpandedProjects(expandedProjectPaths);
  applyCardExpandedState(card, isProjectExpanded(expandedProjectPaths, projectPath));
});
// ★ 이 등록은 반드시 `if(!isServed){ … return; }` **앞**이다 — 뒤로 가면 file:// 모드에서
//   확장이 통째로 죽는다. GOTCHA 4 가 보기 토글·사용량 토글에서 이미 두 번 물린 함정이고,
//   T25-169g 가 그것을 물던 검사다(그 검사의 후계가 필요하다, §10.2).

// 패널 IIFE — 클릭 리스너의 가드 1줄 교체
  if(event.target.closest('.card-drag-handle')) return;   // 유지
- if(event.target.closest('.tree-leaf')) return;          // 삭제 (개념 소멸)
+ if(event.target.closest(EXPAND_TOGGLE_SELECTOR)) return; // 신설 — 없으면 셰브론 클릭이 패널도 연다
```

### 7.5 ★ 드래그 리스너 스코프 수정 (이 설계가 만드는 유일한 신규 결함 위험)

세션 행이 `data-project-path` 를 갖게 되면서 **드래그 재정렬이 조용히 깨진다.**

```js
// 현재 (카드만 이 속성을 갖던 시절의 코드)
document.addEventListener('dragover', function(event){
  var targetCard = event.target.closest('[data-project-path]');   // ← 세션 행을 집는다
  …
  app.insertBefore(draggedCard, draggedIsBefore ? targetCard.nextSibling : targetCard);
  //  ↑ insertBefore 의 부모는 언제나 app 이므로 카드가 <ul class="sessions"> 안으로
  //    들어가지는 않는다. 대신 참조 노드가 app 의 자식이 아니어서 두 갈래로 깨진다:
  //    (a) targetCard.nextSibling 이 다른 세션 <li> 이거나 draggedIsBefore 가 false 면
  //        NotFoundError 를 던져 dragover 핸들러가 죽는다(라이브 이동 정지)
  //    (b) targetCard 가 마지막 세션 행이면 nextSibling 이 null → appendChild 와 같아져
  //        드래그 중인 카드가 조용히 격자 맨 뒤로 튄다
});
document.addEventListener('drop', function(event){
  if(!event.target.closest('[data-project-path]')) return;        // ← 같은 문제
```

> **결정 U10 — `CARD_SELECTOR = '.card[data-project-path]'` 상수를 렌더 IIFE 에 두고
> `dragstart`·`dragover`·`drop` 세 리스너와 확장 토글 리스너가 전부 그것을 쓴다.**
> `currentCardOrder()` 는 이미 `.card[data-project-path]` 로 스코프돼 있었다 — 그 선견지명이
> ST22 에 「트리 요소를 세지 않는다」로 기록돼 있고, 이 변경은 그 스코프를 **나머지 세 곳에도**
> 적용하는 것이다. 리터럴을 네 번 적지 않고 상수 1개로 둔다.
> 회귀 검사가 필수다(§10.2 — 셀렉터가 하나라도 `'[data-project-path]'` 로 되돌아가면 드래그가
> 드래그가 세션 행 위에서 예외로 죽거나 카드를 격자 맨 뒤로 튕긴다).

---

## 8. CSS 설계

### 8.1 삭제 (트리 전용 — 약 20규칙)

`#dzh-app>.tree-section` · `.tree-section[data-dashboard-key]`/`[data-panel-empty-reason]` ·
`.tree,.tree ul` · `.tree>li` · `.tree li` · `.tree li::before/::after`(5변종) · `.tree ul::before` ·
`.tree-root` · `.tree-node` · `.tree-node:hover` · `.tree-node:focus-visible` ·
`.tree-node.card-open` · `.tree-section.card-open .tree-root` · `.tree-node .excerpt` ·
`.tree-leaf` · `.tree-node-no-dashboard` · `.tree-section[data-tier1-previous] .tree-root …` ·
`.view-toggle` 3규칙.

### 8.2 신설

```css
/* 확장 — 340px 고정 해제. W2 가 고정한 값은 "접힘 카드가 프로젝트마다 높이가 다르지 않을 것"
   이고, 펼친 카드는 그 대상이 아니다(사용자가 하나씩 명시적으로 편다). */
.card.card-expanded{height:auto}
.card.card-expanded .sessions{overflow-y:visible}   /* 높이 제한이 사라지면 스크롤 컨테이너도 사라진다 */

/* 세션 행 — <button> 리셋. .project-name·.usage-toggle 과 같은 관용구(font:inherit 를 먼저). */
.session-row{display:block;width:100%;font:inherit;color:inherit;text-align:left;
             background:none;border:0;padding:0;cursor:pointer}
.session-row:hover{…}                 /* 채널 미정 — §11 검증 2 에서 실측으로 확정 */
.session-row:focus-visible{outline:2px solid var(--accent);outline-offset:2px}   /* 기존 관용구 */
.session-row.card-open{background:var(--accent-soft)}   /* OC9 와 같은 채널. .tree-node.card-open 의 후계 */

/* 세션별 진행률 — 항상 렌더하고 접힘에서 감춘다(결정 U9). PV10·OC7 과 같은 관례:
   JS 는 클래스만 만지고 무엇을 보일지는 CSS 가 고른다. */
.card:not(.card-expanded) .session-tier1{display:none}

/* 진행중 세션 신호(결정 U8) — 대시보드의 진행중 칩 halo 와 같은 기하다. */
.sessions .badge.state-working{box-shadow:0 0 10px -1px var(--accent)}

/* 확장 셰브론 — .card-drag-handle 과 같은 계열(작고 사각이고 --muted). */
.card-expand-toggle{width:22px;height:22px;flex:0 0 auto;padding:0;color:var(--muted);
                    background:transparent;border:1px solid var(--line);border-radius:6px;
                    cursor:pointer;display:inline-flex;align-items:center;justify-content:center}
.card-expand-toggle:hover{color:var(--accent-ink);border-color:var(--accent)}
.card-expand-toggle:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.card-expand-toggle svg{width:14px;height:14px;transform:rotate(-90deg)}      /* 접힘 = ▸ */
.card.card-expanded .card-expand-toggle svg{transform:none}                    /* 펼침 = ▾ */
```

### 8.3 ★ 톤다운 스코프 좁히기 (놓치면 조용한 결함)

지금 `.card[data-tier1-previous] .tier1-pct{color:var(--muted)}` 는 **후손 선택자**다. 카드
안에 `.tier1-pct` 가 하나뿐이던 시절에는 안전했지만, 세션 행이 `renderTier1(session.tier1,
false)` 를 그리기 시작하면 프로젝트의 「이전 작업」 톤다운이 **세션 진행률까지 물들인다.**
이것은 검수 1회차가 트리에서 겪은 것과 정확히 같은 함정이다(A-3 → `.tree-section[data-tier1-previous]
.tree-root .tier1-pct` 로 좁혔던 그 수정).

> **결정 U11 — 자식 결합자로 좁힌다:**
> `.card[data-tier1-previous]>.tier1-pct` · `.card[data-tier1-previous]>.tier1-active`.
> `renderTier1(project.tier1, …)` 의 출력은 카드 `<div>` 의 직계 자식이므로 `>` 로 충분하다.
> `>` 가 사라지면 회귀 — 검사가 필요하다(§10.2).
>
> → **대상 소멸(2026-09-30)** — 카드의 프로젝트 진행률(`renderTier1(project.tier1, …)`)과 「이전 작업」 톤 다운이 함께 사라져 이
> 자식 결합자 규칙의 대상이 없어졌다(hub-session-modal-cleanup.md 결정 MX4). 세션 진행률을 물들이지 않는다는 목적은 물들일
> 원천 자체가 없어져 자동으로 성립한다.

### 8.4 새 색 리터럴 0 · 새 토큰 0

위 전부가 `--accent` · `--accent-soft` · `--accent-ink` · `--line` · `--muted` · `--surface` 만
쓴다. 새 CSS 변수도 만들지 않는다.

---

## 9. 설계 결정 목록

### 9.1 신규 결정 (U 계열)

| ID | 결정 | 근거 |
|----|------|------|
| **U1** | 보기 모드 이원화를 폐기하고 카드 한 화면으로 통합한다 | ST17 이 안 B(별도 모드)를 고른 근거는 「무회귀 + 요구 충족의 유일한 교집합」이었다. 그 무회귀가 만든 두 번째 화면이 결함 4건을 낳았고, 두 화면을 유지하는 한 문제 5(카드에서 세션 대시보드에 못 간다)는 구조적으로 해결 불가다 |
| **U2** | 가로 조직도 은유를 버리고 세션은 카드 안의 세로 행이 된다 | §2 변형 ②. 가로 폭은 3열 그리드와 550px 패널이 이미 나눠 썼고, 은유를 유지하려면 우회가 두 겹 필요했다(safe center · 강제 중앙정렬) — 그중 하나가 문제 4 의 원인이다 |
| **U3** | 3단(프로젝트→세션→서브에이전트 타입)을 2단으로 줄인다. 3단째는 삭제가 아니라 **행 안의 칩으로 강등**한다 | 정보는 하나도 안 사라진다 — `renderAgentRuns` 가 이미 카드 세션 줄에 같은 칩을 그린다. 칩 상한 `MAX_VISIBLE_AGENT_CHIPS=2` 는 접힘·펼침 모두 그대로 둔다(상태 의존 차이를 하나 줄인다. K3 가 "+N" 오버플로 칩을 이미 폐기했으므로 상한을 푸는 것이 오히려 새 결정을 요구한다) |
| **U4** | 프로젝트별 **온디맨드 확장**을 둔다. 확장 = `height:340px` 해제 + 세션 전부 + 세션별 진행률 | 확장이 없으면 접힘 카드의 `.sessions{overflow-y:auto}` 가 남고, **그 내부 스크롤이 재렌더마다 초기화돼 문제 4 가 세로 축으로 되살아난다.** 확장은 그 스크롤 컨테이너를 없애는 유일한 수단이다. 동시에 세션별 진행률을 놓을 자리를 만든다(접힘 카드에 넣으면 보이는 세션 수가 줄어 문제 3 을 악화시킨다) |
| **U5** | 확장 제스처는 전용 셰브론 버튼이다. 카드 클릭 계약(OC5·OC11·ST26)은 한 글자도 안 바뀐다 | §2 변형 ① |
| **U6** | 셰브론은 보이는 세션이 1개 이상일 때만 그린다 | §2 변형 ③. → 열린 질문 2 |
| **U7** | 확장 클릭은 `render()` 를 부르지 않는다 — 상태를 저장하고 살아 있는 카드에 클래스를 붙인다 | `render()` 를 부르면 `app.innerHTML` 교체가 클릭 대상을 그 자리에서 떼어내고, 뒤이어 도는 패널 IIFE 의 리스너가 **분리된 DOM 트리** 위에서 `closest` 를 돌게 된다. 동작은 하지만 그 동작에 기대는 것이 곧 다음 회차의 함정이다. 부수적으로 애니메이션 위상 리셋·플래시도 없다. 대가는 클래스를 쓰는 경로가 둘(`renderProject` 인라인 + `applyCardExpandedState`)이라는 것 — 상수 1개를 공유하게 하고 검사로 묶는다(§10.2) |
| **U8** | 진행중 세션 신호는 **행 배지의 정적 halo** `0 0 10px -1px var(--accent)` 다. 모션은 카드 하나가 계속 독점한다 | §9.3 에서 따로 논한다. **[번복, 2026-09-10]** 사용자가 산출물을 보고 이 halo 를 반려했다 — 후속: `hub-tree-view-and-signal-fixes.md` 결정 V1(전면 번복) |
| **U9** | 세션별 진행률은 **항상 렌더하고 CSS 가 감춘다**. JS 는 접힘/펼침 분기를 하지 않는다 | PV10(테마 아이콘 2개 중 CSS 가 고른다)·OC7(빈 상태 클래스 1개 + CSS 가 고른다)의 관례. 그리고 U7(재렌더 없는 토글)이 성립하려면 펼침 전용 콘텐츠가 이미 DOM 에 있어야 한다 — 두 결정이 서로를 요구한다 |
| **U10** | 카드 셀렉터를 `CARD_SELECTOR = '.card[data-project-path]'` 상수로 단일화하고 드래그 3리스너 + 확장 토글이 전부 그것을 쓴다 | §7.5. 이 수정이 없으면 드래그가 카드를 `<ul class="sessions">` 안으로 옮긴다 |
| **U11** | 「이전 작업」 톤다운을 자식 결합자로 좁힌다 | §8.3 → **대상 소멸(2026-09-30)** — hub-session-modal-cleanup.md 결정 MX4 |
| **U12** | 옛 `localStorage['dzh-view-mode']` 는 **무시한다**(삭제 코드를 두지 않는다) | §9.4 |
| **U13** | `project.dashboard_key` 와 `session.dashboard_key` 가 같은 파일을 가리켜도 두 진입점을 모두 유지한다(ST25 무변경) | §9.5 → **개정(2026-09-30)** — 프로젝트 쪽 진입점이 사라졌다, hub-session-modal-cleanup.md 결정 MX1·MX4 |
| **U14** | 세션 행은 확장 여부와 무관하게 **항상** 클릭 대상이다 | 도달 가능성이 UI 상태에 의존하면 문제 5 를 절반만 고친 것이다. 대가는 Tab 정지점 증가(실측 스냅샷 기준 대략 +30, 정확한 수는 미실측) — OC11 이 카드에 대해 이미 같은 대가를 지불하기로 결정한 항목이다. → 열린 질문 4 |

### 9.2 뒤집는 기존 결정 (공개 번복 — SP19→SP4, RV1 선례)

| 결정 | 원문 요지 | 이 PRP 의 처분 | 전제가 어떻게 바뀌었나 |
|------|-----------|---------------|---------------------|
| **ST17** | 배치는 안 B(헤더 보기 토글, 기본값 카드) | **뒤집는다**(U1) | ST17 의 비교표에서 안 B 의 결정적 우위는 「카드 모드 회귀 0」이었다. 그 판단은 옳았다 — 그러나 그 대가로 **세션 대시보드가 트리 모드에만 살게 됐고**, 그것이 지금의 문제 5 다. ST17 은 그 비용을 표에 넣지 않았다 |
| **ST18** | 보기 모드는 사용자 상태다(H1⁗ ③ 개정) | **뒤집는다**(U1) — 모드가 사라지므로 상태도 사라진다 | 그 자리를 확장 상태가 대신한다. H1⁗ ③ 의 「보기 모드(카드/트리)도 사용자 상태다」 문장을 「카드 확장(프로젝트별 접힘)도 사용자 상태다 — `localStorage['dzh-expanded-projects']` + 모듈 변수에 살고, `#dzh-app` 은 그 값을 읽어 그릴 뿐 저장하지 않는다」로 교체 |
| **ST19** | 3단 트리(프로젝트 → 세션 → 서브에이전트 타입). 2단은 「깊이감이 사라진다」로 기각 | **부분 번복**(U3) | 2단 기각 근거는 **조직도 은유를 전제**로 했다. 은유를 버리면(U2) 「깊이감」이 평가 기준에서 사라진다. 정보 자체는 칩으로 남으므로 실질 손실 0 |
| **ST21** | 연결선은 CSS 의사요소, 폭은 섹션 내부 가로 스크롤 | **뒤집는다**(U2) | 가로 스크롤이 문제 3 의 직접 원인이고, 그것을 보정하려 도입한 강제 중앙정렬이 문제 4 의 직접 원인이다 |
| **ST22** | 드래그 재정렬은 카드 모드 전용 | **조건 소멸**(U10) | 모드가 하나뿐이라 「카드 모드 전용」이라는 말이 뜻을 잃는다. 다만 ST22 가 기록한 사실(`currentCardOrder` 는 `.card[data-project-path]` 로 스코프돼 있다)은 이제 **선택이 아니라 필수**가 된다 |

### 9.3 유지하는 결정 (그리고 그것이 이 설계를 제약하는 방식)

| 결정 | 유지 방식 |
|------|----------|
| **OC5·OC11·ST26** (클릭 대상·모두 `<button>`·속성 인계) | 담체 이름만 `.tree-node` → `.session-row`, `.tree-section` → `.card` 로 바뀐다. 규칙·셀렉터·불변식 OC-A 전부 그대로 |
| **ST23·ST24·ST25** (패널 신원 `(projectPath, sessionId)`·제목 형식·3성분 `isSameDocument`) | **한 글자도 안 바뀐다.** T25-163 이 그 계약을 물고 있고, 이 변경 후에도 그대로 통과한다 |
| **ST20** (렌더 함수 재사용·잡음 필터 공유) | `visibleSessionsOf`·`shouldRenderSession` 무변경. 이제 소비자가 하나뿐이라 「공유」의 강제 대상이 바뀐다(§10.1 T25-160) |
| **W1·W2** (3열 산술·`.card{height:340px}`·`.wrap{max-width:1440px}`) | 접힘 상태에서 무변경. 확장은 `height` 만 푼다 |
| **D6** (단일 모션 언어 진폭 `.6`→`1`·주기 `4s`) | **새 모션을 하나도 추가하지 않는다**(U8). 셰브론 회전에도 `transition` 을 두지 않는다 — 두면 `prefers-reduced-motion` 분기를 하나 더 져야 하고, 얻는 것이 없다 |
| **D8~D11** (바깥 bloom `8px -2px`·z-index 금지·gap 불변·안쪽 inset bloom) | `.card.card-working` 규칙을 건드리지 않는다. T25-65·T25-171·T25-176 이 그대로 통과한다 |
| **PV9** (CDN·런타임 라이브러리 금지) | 셰브론은 lucide `chevron-down` 을 좌표째 옮겨 적은 **정적 인라인 SVG 상수 1개**다. 접힘/펼침은 아이콘 2개 스와핑이 아니라 CSS `transform:rotate` 로 한다 — 상수 1개가 2개보다 낫고, 옛 보기 토글의 2아이콘 스와핑 관용구는 어차피 함께 삭제된다 |
| **IL1~IL7** (우클릭·텍스트 선택 잠금) | 무변경. 셰브론은 텍스트 없는 SVG 컨테이너라 선택 차단이 지울 것이 없다(`.card-drag-handle` 과 같은 사정, IL5) |
| **N2** (속성 존재가 곧 화면 상태) | 세션 행의 `cursor:pointer`·hover 는 `.session-row[data-dashboard-key]`/`[data-panel-empty-reason]` 로 준다 — 카드가 쓰는 형태 그대로 |

### 9.4 결정 U8 상술 — glow 의 신호 설계

사용자는 「카드 보기에서처럼 glow 애니메이션」을 요청했다. 그대로 하면 **한 화면에서 숨쉬는
요소가 급증한다.** 실측 스냅샷 기준: 프로젝트 6개 중 working 카드 몇 개 + 그 안의 working
세션(coding-harness 2 · NotebookWiki 1 …) → 대략 10개 안팎이 동시에 4초 주기로 맥동한다(정확한
수는 미실측). 직전 회차 `dashboard-hub-signal-tuning` 이 줄이려 한 것이 정확히 이 「신호
과잉」이다.

**핵심 관찰: 두 신호는 서로 다른 질문에 답한다.**

| 질문 | 언제 | 답하는 신호 |
|------|------|------------|
| 지금 **어느 프로젝트**가 돌고 있나 | 3열 격자를 훑을 때 | 카드 `.card-working`(맥동 bloom + `--accent` 테두리) — **무변경** |
| 이 카드 안 **어느 세션**이 돌고 있나 | 카드 하나를 읽을 때 | 행 배지 halo — **정적** |

두 질문은 같은 순간에 필요하지 않다. 격자를 훑는 동안에는 세션이 안 읽히고, 카드를 읽는
동안에는 격자를 안 훑는다. 그래서 **두 번째 신호에는 모션이 필요 없다.**

기하는 새로 고르지 않는다. `dashboard-hub-signal-tuning` §3.5 가 대시보드의 진행중 단계 칩을
위해 이미 실측으로 고른 값이 그대로 맞는다:

- 시안 a `box-shadow:0 0 10px -1px var(--accent)` — 칩 오른쪽 가장자리 d=1 에서 ΔL\* **10.59**
  (라이트, `--surface` 면 기준), 꼬리 7px. 다크에서 11.86 으로 사실상 대칭.
- **그 측정이 이 자리에 그대로 이전된다**: 대시보드의 `li.active .chip` 은 `--accent-ink` 채움
  이고 halo 가 `--accent` 이며 배경이 `--surface` 다. 허브의 `.badge.state-working` 도 정확히
  같은 세 색 관계다(`background:var(--accent-ink);color:var(--bg)`, 카드 면색 `--surface`).
- 꼬리 7px 는 배지 주변 여백 안에서 끝난다(미실측 — 구현 시 확인).

`prefers-reduced-motion`: **새 분기가 필요 없다.** 새 애니메이션이 0개이기 때문이다. 기존
`@media (prefers-reduced-motion:reduce){.card.card-working::after{animation:none;opacity:1}}` 는
그대로 둔다.

**모션을 원한다면**(→ 열린 질문 1) 승격은 3줄이고 그 형태도 이미 정해져 있다 — 대시보드의
`ol.steps li.active .chip::after` 관용구를 그대로 옮긴다(`position:relative` + `::after` 오버레이
+ `animation:card-working-glow 4s ease-in-out infinite`) + `prefers-reduced-motion` 무효화 1줄.
`@keyframes card-working-glow` 를 재사용하므로 D6 의 두 숫자(.6/4s)를 공유한다. **모션을 넣기로
한다면 그 범위를 「펼친 카드 안」으로 한정하는 것을 권고한다** — 맥동 요소 수가 (펼친 카드 수
× 그 안 working 세션 수)로 묶여 신호 과잉이 구조적으로 방지된다.

### 9.5 결정 U12 상술 — 옛 `dzh-view-mode` 키의 이행

| 안 | 평가 |
|----|------|
| **A. 무시한다(채택)** | 그 키를 읽는 코드가 사라지므로 값이 `tree` 든 `cards` 든 아무 일도 일어나지 않는다. 사용자에게 보이는 결과: **다음 방문에 카드 화면이 뜬다**(그것이 유일한 화면이므로). 비용: 브라우저 저장소에 약 20바이트 고아 |
| B. 1회 `removeItem` 을 넣는다 | 죽은 개념의 이름(`'dzh-view-mode'`)을 소스에 영구히 남긴다. 이 저장소의 관례는 정반대다 — T25-159 는 옛 2버튼 잔재(`dzh-view-cards`·`dzh-view-tree`)의 **개수가 0** 인지를 검사한다. 잔재 리터럴을 남기는 것이 곧 회귀 신호다 |

> **결정 U12 — 안 A.** 그리고 **잔재 0 검사를 세운다**(§10.2) — `dzh-view-mode`·`VIEW_MODE_`·
> `dzh-view-toggle`·`view-icon-`·`.view-toggle`·`tree-node`·`tree-section`·`tree-root`·
> `tree-leaf`·`renderProjectTree`·`initializeTreeRootScrollPositions` 전부 0건.
> `removals.txt` 는 **쓰지 않는다** — 그것은 배포 파일(rules/agents/commands)의 툼스톤이고,
> 이건 파일이 아니라 브라우저 저장소 키다.

### 9.6 결정 U13 상술 — 중복 진입점

`project.dashboard_key` 는 mtime 최신 대시보드(ST11), `session.dashboard_key` 는 그 세션 자신의
파일(ST12)이다. 최신 파일이 마침 세션 X 의 것이면 **카드 클릭과 세션 X 행 클릭이 같은 문서를
띄운다.**

| 안 | 평가 |
|----|------|
| **A. 둘 다 유지(채택)** | ST25 가 이미 이 경우를 다뤘다 — 신원이 다르므로(3성분) iframe 을 다시 싣고 제목이 다르다(`coding-harness` 대 `coding-harness · 세션 63ad8669`). 사용자가 보는 것은 **같은 내용에 다른 이름표**이고, 그 이름표가 곧 「지금 이건 프로젝트 요약이다/세션 X 다」라는 정보다 |
| B. 키가 같으면 카드 쪽 진입을 막는다 | **레거시 단일 파일**(`.claude/dashboard.html`, `session_id` 없음)은 그것을 열 세션 행이 아예 없다 — 그 경우 카드 진입을 막으면 대시보드에 도달할 방법이 사라진다. 게다가 세션이 `shouldRenderSession` 에 걸러진 경우에도 같은 구멍이 난다. 「경우에 따라 클릭이 되기도 안 되기도 하는 카드」는 OC5 가 없애려 한 바로 그 형태다 |
| C. 같은 파일임을 행에 표시한다 | 새 개념 1개(표시)와 새 문구 1개를 추가한다. 지금 그 혼동으로 인한 실제 피해 보고가 없다(YAGNI) |

> **결정 U13 — 안 A(ST25 무변경).** → 열린 질문 5.
>
> → **개정(2026-09-30)** — 프로젝트 쪽 진입점이 사라졌다: 카드와 카드 상세보기 머리는 더는 대시보드를 열지 않아(hub-session-modal-cleanup.md
> 결정 MX1) 진입점은 세션 행·세션 카드뿐이다. 카드가 프로젝트 진행률도 그리지 않으므로(MX4) 「같은 내용에 다른 이름표」 혼동 자체가 없다.

---

## 10. 테스트 계획

### 10.1 (a) 깨질 기존 가드 — 전수

| 가드 | 지금 무는 것 | 처분 | 원장(`tests/mutations.tsv`) |
|------|-------------|------|------|
| **T25-159** | `'dzh-view-mode'` 리터럴 == 1 · `VIEW_MODE_STORAGE_KEY` 선언 줄 앵커 · `id="dzh-view-toggle"` 가 `#dzh-app` 앞 · 옛 2버튼 잔재 == 0 | **개정** — 「보기 모드 저장 키가 1곳」 → 「보기 모드·트리 잔재가 0곳」(U12). 확장 키(`dzh-expanded-projects`)에 대해서는 **같은 2중 검사 형태**(리터럴 수 + 줄 앵커)를 그대로 복제한다. 그 2중 형태의 근거가 T25-159 주석에 실측으로 남아 있다: 리터럴 카운트만으로는 「선언을 주석 처리한」 뮤테이션을 못 잡는다 | 변조행 존재 → 내용 갱신 |
| **T25-160** | `function renderProjectTree(` 존재 + `renderProject`·`renderProjectTree` 둘 다 `visibleSessionsOf(` 호출 | **개정** — `renderProjectTree(` == 0 으로 뒤집고, `renderProject` 의 `visibleSessionsOf(` 호출은 유지. 「공유 강제」의 의미가 「필터를 우회하지 않는다」로 좁아진다 | **면제행 → 변조행 승급**(원장 규칙: 「개정·수정 시 변조행으로 승급」) |
| **T25-162** | `.tree li::before/::after` · `.tree-root{width:460px` · `.tree-section.card-open .tree-root{` · `.tree-section[data-tier1-previous] .tree-root .tier1-pct` · **`<style>` 안에 `@import`·CDN 없음** | **분할.** 트리 셀렉터 핀 4종은 전부 폐기. **마지막 하나(`<style>` 순수성)는 PV9 계약이라 트리와 무관하게 살아남아야 한다** — 그 서브체크만 남기고 앵커를 다시 잡는다 | **면제행 → 변조행 승급** |
| **T25-127** | `.session-meta{`·`.session-id{` CSS + `renderSession()` 본문의 첫 줄(`.session-line`) 구성에 `session-id\|session-meta\|renderSessionMeta` 가 안 샌다 | **앵커 개정만.** `sed -n '/function renderSession(session){/,…'` → `/function renderSession(project, session){/`. **앵커를 안 고치면 범위 추출이 빈손이 되어 `record_failure` 로 즉시 실패한다.** 검사의 의미(첫 줄 wrap 거동 불변)는 그대로 유효하고, 이 설계는 그 첫 줄을 한 글자도 안 바꾼다 | **면제행 → 변조행 승급** |
| **T25-169a~g**(7종) | 보기 토글 버튼의 id·아이콘 2종·CSS 스와핑 3토큰·`applyViewModeButton` 본문 3속성·`.view-toggle-group` 잔재·리스너 1건·리스너가 `if(!isServed){` 앞 | **전부 삭제.** 단, **169g 가 물던 계약(GOTCHA 4 — 리스너 등록 위치)은 확장 토글로 그대로 이전된다**(§10.2 신규) | 변조행 7건 삭제 |

**깨지지 않는 것(확인 완료)**: T25-161(세션 신원 속성 3종 리터럴 == 2 — 렌더·패널 각 1. 세션
행이 같은 상수를 쓰므로 유지) · T25-163(패널 IIFE 계약 — 전부 그대로 참) · T25-107(`dzh:rendered`
== 2) · T25-120(`shouldRenderSession` 앵커) · T25-65·T25-171·T25-176(`card-working` 진폭·주기·
bloom 부등식 — `.card.card-working` 규칙 무변경) · T25-36·T25-45·T25-50·T25-155(hub/README.md
토큰 — 해당 낱말을 남긴다) · T25-156~158(세션 대시보드 경로 상수) · **`tests/hub` 655건 전부**
(전수 확인: 그 디렉토리의 `tree` 매치는 「워크트리」와 `ast.parse` 뿐이다) · `tests/commands`.

### 10.2 (b) 새로 세울 가드의 성격

> 가드 ID 번호는 부여하지 않는다 — 구현 회차가 붙인다. **main 기준으로 `T25-177` 까지 이미
> 쓰였다.** 아래는 성격과 무는 대상만 적는다. **각 신규 가드마다 `tests/mutations.tsv` 변조행이
> 1건씩 필요하다**(§10.4).

| # | 성격 | 무는 것 | 왜 필요한가(이 검사가 없으면 무엇이 조용히 통과하나) |
|---|------|---------|--------------------------------|
| 1 | 잔재 0 (역) | `dzh-view-mode`·`VIEW_MODE_`·`dzh-view-toggle`·`view-icon-`·`.view-toggle`·`tree-section`·`tree-node`·`tree-root`·`tree-leaf`·`renderProjectTree`·`renderTreeRoot`·`renderSessionNode`·`initializeTreeRootScrollPositions` 전부 0건 | 삭제가 부분적이어서 죽은 CSS·죽은 함수가 남는다 |
| 2 | 상태 키 유일성 (정, T25-159 관용구 복제) | `dzh-expanded-projects` 리터럴 정확히 1건 **AND** `^  var EXPANDED_PROJECTS_STORAGE_KEY = 'dzh-expanded-projects';$` 줄 앵커 1건 | 리터럴 카운트 단독은 「선언을 주석 처리한」 뮤테이션을 못 잡는다(T25-159 주석의 실측) |
| 3 | GOTCHA 4 위치 (역, T25-169g 후계) | 확장 토글 `addEventListener` 등록 줄 번호 < `if(!isServed){` 줄 번호 | 리스너가 조기 반환 뒤로 밀려 **`file://` 모드에서 확장이 통째로 죽는다.** 이 함정은 사용량 토글·보기 토글에서 이미 두 번 물렸다 |
| 4 | 리스너 중복 (역) | 확장 토글 `addEventListener('click'` 정확히 1건 | 중복 등록 시 클릭 1회에 상태가 2번 뒤집혀 제자리로 온다(T25-169f 와 같은 실패 모드) |
| 5 | **드래그 스코프 (역, ★최고 위험)** | `dragstart`·`dragover`·`drop` 세 리스너 본문에 `closest('[data-project-path]')` 형태가 **0건**이고 전부 `CARD_SELECTOR` 를 경유한다 | 하나라도 되돌아가면 **드래그가 카드를 `<ul class="sessions">` 안으로 옮긴다.** 조용한 DOM 파괴이고 눈으로는 재정렬을 몇 번 해봐야 나타난다(§7.5) |
| 6 | 패널 가드 순서 (정+역) | 패널 IIFE 클릭 리스너에 확장 토글 조기 반환이 있고 그것이 `closest(CLICKABLE_CARD_SELECTOR)` **앞줄**이다. 옛 `.tree-leaf` 가드는 0건 | 없으면 셰브론 클릭이 패널까지 연다 |
| 7 | 불변식 OC-A (정) | 세션 행 속성 생성부에 `if(isClickable) … data-dashboard-key … else … data-panel-empty-reason` 쌍이 있다 | 키가 없는데 사유도 없으면 클릭이 조용히 실패한다 — hub-panel-empty-state PRP 의 출발점이던 결함 |
| 8 | 톤다운 스코프 (정) | `.card[data-tier1-previous]>.tier1-pct` 에 자식 결합자 `>` 가 있다 | `>` 가 빠지면 프로젝트의 「이전 작업」 회색이 세션 진행률까지 물들인다(§8.3) |
| 9 | 확장 CSS 계약 (정) | `.card.card-expanded{height:auto}` **AND** `.card:not(.card-expanded) .session-tier1{display:none}` | 둘 중 하나만 남으면 접힘 카드에 진행률이 그대로 뜨거나(높이 파열) 펼쳐도 안 뜬다 |
| 10 | **모션 비확산 (역, ★결정 U8 의 기계적 표현)** | `.sessions .badge.state-working` 규칙 본문에 `animation` 이 **없다** | 「세션 행에도 맥동을 넣자」가 검토 없이 되살아나는 것을 막는다. 열린 질문 1 이 채택되면 이 검사를 「펼친 카드 스코프에서만 허용」으로 개정한다 |
| 11 | 클래스 단일 출처 (정) | `card-expanded` 문자열이 상수 선언 1 + 사용 N 이고, `renderProject` 와 `applyCardExpandedState` 가 **같은 상수**를 쓴다 | U7 의 두 경로가 서로 다른 문자열로 갈라지면 폴링 후 확장이 풀린다 |
| 12 | `<style>` 순수성 (역, T25-162 에서 구출) | `<style>` 블록 안에 `@import`·`https://`·`<script src=` 없음 | PV9(`file://` 에서도 열려야 한다) 계약. 트리 검사에 얹혀 있던 것을 독립시킨다 |
| 13 | 문서 정합 (정) | `hub/README.md` 에 확장(펼치기/접기)·세션 행 클릭 서술이 있고, 보기 토글·트리 서술은 0건 | 화면과 문서가 어긋난 채 남는다(T25-36·T25-45 와 같은 관용구) |

### 10.3 순수 로직 단위 테스트

셸은 JS 를 실행하지 않고 이 저장소에 JS 테스트 러너가 없다(그리고 **도입하지 않는다** — 새
의존성 0). 따라서 순수 함수의 검증은 두 층으로 한다:

1. **정적 계약 검사**(§10.2) — 함수 존재·호출 경유·상수 단일화를 문자열로 잠근다. 이 저장소가
   템플릿 JS 에 쓰는 유일한 자동 검증 수단이고, T25 전체가 그 형태다.
2. **수동 콘솔 검증**(§11) — 아래 표의 케이스를 브라우저 콘솔에서 확인한다. 계산 결과가 아니라
   **화면 상태**를 보는 것이라 사람 눈이 필요한 항목과 겹친다.

| 대상 | 케이스 | 기대 |
|------|--------|------|
| `nextExpandedProjects` | 없는 경로 추가 | 새 배열, 원본 불변, 길이 +1 |
| | 있는 경로 재호출 | 새 배열, 그 경로 제거 |
| | 상한(200) 초과 | 뒤가 잘린다 |
| `readStoredExpandedProjects` | 저장소 차단(사파리 프라이빗 등) | `[]` — 예외가 IIFE 를 죽이지 않는다 |
| | 값이 `"tree"`(옛 키 오염 시뮬레이션) / `"{}"` / `"[1,2]"` | 전부 `[]` (비배열·비문자열 원소 방어) |
| `isProjectExpanded` | 빈 배열 | `false`(무회귀 기본값 = 전부 접힘) |
| `expandToggleLabel` | `(false, 6)` / `(true, 6)` / `(false, 1)` | 세 문구가 서로 다르고 개수를 담는다 |
| `renderSessionProgress` | `session.tier1 === null` | `SESSION_NO_DASHBOARD_LABEL` 한 줄 |
| `sessionRowAttributes` | `dashboard_key` 있음 + `isServed` | `data-dashboard-key` 있고 `data-panel-empty-reason` 없음 |
| | `dashboard_key` 없음 | 반대(불변식 OC-A) |
| | 경로에 `"` · `\` 포함 | `escapeHtml` 경유 — 속성이 깨지지 않는다 |

### 10.4 원장과 래칫 (★놓치면 커밋이 막힌다)

| 상수 | 현재값 | 이 변경의 방향 | 조치 |
|------|--------|---------------|------|
| `SOURCE_GUARD_ID_FLOOR` | **464** (하한) | T25-169a~g 삭제로 ID 접두 **7종 감소** | §10.2 의 신규 가드가 7종 이상이면 자동 충족(13종 계획이므로 순증 +6). 미달하면 상수를 내리는 커밋에 이유가 필요하다 |
| `LEDGER_MUTATION_ROW_FLOOR` | **71** (하한) | 변조행 7건 삭제(169a~g) / 승급 3건(T25-127·160·162) / 신설 13건 → 순증 +9 | 자동 충족 |
| `LEDGER_EXEMPT_ROW_RATCHET` | 상한 | 면제행 3건이 변조행으로 올라가 **감소** | 자동 충족(내리는 것은 자유) |
| `LINE_CITATION_RATCHET_SUITE` | **5** (상한) | `tests/run.sh` 새 주석 | 새 주석에 `파일명:줄번호` 형태 인용을 쓰지 않는다(결정 D17) |
| `LINE_CITATION_RATCHET_DEPLOYED` | **1** (상한) | 템플릿은 배포 트리 밖 | 무관. 다만 D17 의 관례(앵커 인용)를 템플릿 새 주석에도 따른다 |
| T26 상시 컨텍스트 예산 | — | `CLAUDE.md`·`rules/` 무변경 | 무관 |

### 10.5 검증 명령 (프로젝트 정본)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

---

## 11. 사람이 눈으로 확인할 것 (자동 검사가 못 잡는 몫)

메모리 「허브·대시보드 CSS 시각 확인」의 절차를 쓴다 — 실데이터 생성물의 `<style>` 블록만
갈아끼워 로컬 서버로 서빙한다.

| # | 확인 | 통과 기준 |
|---|------|----------|
| 1 | **접힘 카드 무회귀** | 셰브론을 뺀 나머지가 오늘과 같다. 특히 **한 카드에 보이는 세션 수가 줄지 않는다**(MC1~MC5 가 실측으로 겪은 함정 — `<button>` 리셋이 줄 높이를 1px 이라도 올리면 3건 → 2건이 된다). 헤드리스로 `.sessions li` 개수·`clientHeight` 를 전후 비교한다 |
| 2 | 세션 행 hover 채널 | `--accent` 테두리는 카드 hover·`card-working`·`card-open` 이 이미 쓴다. 행 안에서 어느 채널이 남는지 실측으로 고른다(면색 옅은 변화 / 좌측 여백 / 텍스트 색). **미실측 — 구현 단계에서 확정** |
| 3 | 진행중 배지 halo | 카드 면색(`--surface`) 위에서 눈에 든다. 꼬리가 이웃 요소를 침범하지 않는다. 라이트·다크 양쪽 |
| 4 | 열린 행 표시 | `.session-row.card-open` 면색이 카드 면색과 구분된다. `.card.card-open` 인 카드 **안의** 열린 행이 이중으로 칠해지지 않는지(면색 겹침) |
| 5 | 확장 레이아웃 | 3열 격자에서 카드 하나만 펼치면 그 카드만 길어지고 형제는 340px 를 유지한다(`align-items:start`). 다른 카드가 **자리를 옮기지 않는다**(구멍이 생기지 않는다) |
| 6 | 확장 유지 | 펼친 채로 30초 이상 두고 폴링·틱이 지나가도 펼침이 유지된다. 새로고침·`file://` 포커스 복귀·세대 자가 치유 리로드 후에도 유지된다(localStorage) |
| 7 | 문제 4 재현 시도 | 페이지를 아래로 스크롤해 뒤쪽 카드의 세션을 열어 두고 30초 틱을 넘긴다 — **보던 위치가 그대로다.** `#dzh-app` 안에 가로 스크롤 컨테이너가 0개임을 콘솔로 확인 |
| 8 | 드래그 재정렬 | 세션 행 **위로** 카드를 끌어도 라이브 이동이 멈추거나 카드가 격자 맨 뒤로 튀지 않는다. 콘솔에 `NotFoundError` 가 없어야 한다(§7.5·§10.2-5 의 사람 확인) |
| 9 | `file://` 모드 | 셰브론이 동작한다. 세션 행 클릭이 「허브 서버를 켜면…」 빈 상태를 띄운다 |
| 10 | 키보드 | Tab 으로 셰브론·세션 행에 도달하고 Enter/Space 가 동작한다. 포커스 링이 보인다 |
| 11 | `prefers-reduced-motion` | 새로 움직이는 것이 하나도 없다(카드 bloom 은 오늘처럼 정적으로 남는다) |

---

## 12. 열린 질문 — **전부 해소됨 (2026-09-10 사용자 승인)**

> **사용자가 이 PRP 를 승인하고 아래 7건을 전부 「권고안대로」로 확정했다.** 1·2·3·4 는
> 명시적 선택으로, 5·6·7 은 전체 승인에 포함되어 확정됐다. 구현은 이 표의 **권고 열**을
> 그대로 따른다 — 대안 열은 「왜 그쪽이 아닌가」의 기록으로만 남긴다.
>
> 특히 **질문 1 은 사용자의 원 요청("glow 애니메이션 필요")을 이 설계가 정적 halo 로
> 되받은 자리다.** 사용자가 그 되받음을 받아들였다 — 구현은 **새 `@keyframes` 를 만들지
> 않는다.** 이 문단이 그 승인의 기록이다.

| # | 질문 | 권고 | 대안의 비용 |
|---|------|------|------------|
| **1** | **진행중 세션 행에 맥동(pulse)을 넣을 것인가.** 사용자는 「glow 애니메이션」을 요청했고, 이 설계는 **정적 halo** 를 제안한다(§9.4) | **정적 halo.** 맥동 요소가 대략 10개(미실측)로 늘어 직전 회차가 줄인 신호 과잉을 되살린다 | 넣으면 +3줄(대시보드 칩 관용구 그대로). 넣되 **「펼친 카드 안」으로 한정**하는 절충안 있음. 이 경우 §10.2-10 가드를 그 범위로 개정. **[후속, 2026-09-10]** 승인된 두 절 중 halo 자체(정적 형태)만 반려됐고 「새 애니메이션 없음」은 유효하게 남았다 |
| **2** | **셰브론 노출 조건**: 세션 ≥ 1(권고) vs 사용자 제안대로 ≥ 2 | ≥ 1 | ≥ 2 면 사용자가 외워야 할 규칙이 하나 늘고, 세션 1개 프로젝트의 진행률·전문 발췌에 도달할 방법이 사라진다 |
| **3** | **펼친 카드 옆의 빈 공간**을 수용할 것인가 | 수용 | 전폭 확장(`grid-column:1/-1`)은 auto-placement 가 앞 카드들의 슬롯을 비워 **격자에 구멍**을 낸다(`dense` 는 사용자 지정 순서 O1·O2 를 깬다). 카드 아래 별도 행으로 빼는 안은 카드와 확장부가 시각적으로 분리돼 「무엇의 확장인지」가 흐려진다 |
| **4** | **세션 행을 항상 클릭 대상으로 둘 것인가** vs 펼쳤을 때만 | 항상(U14) | Tab 정지점이 대략 +30(미실측) 늘어난다. 「펼쳤을 때만」으로 하면 정지점은 오늘과 같지만 도달 가능성이 UI 상태에 의존한다 |
| **5** | **중복 진입점**(프로젝트 요약과 세션 X 가 같은 파일일 때) 유지 | 유지(U13·ST25) | 조건부로 막으면 레거시 단일 파일 프로젝트가 대시보드에 도달할 방법을 잃는다 |
| **6** | **옛 `dzh-view-mode` 키**: 무시(권고) vs 1회 삭제 코드 | 무시(U12) | 삭제 코드는 죽은 개념의 이름을 소스에 영구히 남기고, 이 저장소의 잔재 0 검사 관례와 반대 방향이다 |
| **7** | 접힘 카드에서 **세션별 진행률을 아예 안 보여주는 것**이 맞나 | 맞다(U9) | 보여주면 세션 행이 약 2줄 높아져 접힘 카드에 보이는 세션이 3건 → 2건으로 준다(미실측, MC1~MC5 의 실측 계열) — 문제 3 을 악화시킨다 |

---

## 13. 위험과 완화

| # | 위험 | 가능성 | 영향 | 완화 |
|---|------|--------|------|------|
| 1 | **드래그 재정렬이 세션 행 위에서 깨진다**(§7.5) — `NotFoundError` 로 라이브 이동이 죽거나, 마지막 세션 행 위에서는 카드가 조용히 격자 맨 뒤로 튄다 | 높음(코드를 안 고치면 확정) | 심각(후자는 조용하다) | `CARD_SELECTOR` 단일화(U10) + 가드 §10.2-5 + 사람 확인 §11-8 |
| 2 | `<button>` 리셋이 세션 줄 높이를 올려 접힘 카드에 보이는 세션이 준다 | 중 | 문제 3 악화(역효과) | 헤드리스 전후 실측(§11-1). MC1~MC5 가 같은 함정을 이미 문서화했다 |
| 3 | 셰브론 클릭이 패널까지 연다 | 중(가드 없으면 확정) | 중 | 패널 IIFE 조기 반환(§7.4) + 가드 §10.2-6 |
| 4 | 확장 리스너가 `if(!isServed)` 뒤에 등록돼 `file://` 에서 죽는다 | 중 | 중 — 오프라인 사용자만 겪어 발견이 늦다 | 가드 §10.2-3(T25-169g 의 후계) |
| 5 | 「이전 작업」 톤다운이 세션 진행률까지 물들인다 | 중 | 낮음(오독) | 자식 결합자(U11) + 가드 §10.2-8 |
| 6 | `SOURCE_GUARD_ID_FLOOR` 하한 미달로 커밋이 막힌다 | 중 | 낮음(막히지만 조용하지 않다) | §10.4 의 산술을 구현 전에 확인. 신규 13종 ≥ 삭제 7종 |
| 7 | `<div>` 를 `<button>` 안에 넣는다(HTML 콘텐츠 모델 위반) | 확정 | 낮음 | **선례가 이미 있다** — `.tree-node` `<button>` 이 `.session-line`·`.session-meta`·`.tier1-pct` `<div>` 를 품고 출시돼 있었다. 파서가 깨지는 부류(`<p>` 안 블록)가 아니다. 새로 만드는 문제가 아님을 기록만 한다 |
| 8 | 펼친 카드가 매우 길어진다(세션 10+) | 낮음 | 낮음 | 페이지 세로 스크롤 1축이라 오늘 트리(프로젝트 6개 ≈ 2,200px, 실측)보다 나쁘지 않다. 접기는 클릭 1회 |
| 9 | 재렌더 시 포커스가 `<body>` 로 돌아간다 | 중 | 낮음 | **선행 조건 없이 이미 존재하는 성질**이다(`.project-name` `<button>` 도 같다). 패널을 여는 흐름에서는 포커스가 닫기 버튼으로 옮겨져 있어 체감되지 않는다. 이 PRP 의 범위 밖으로 두고 기록만 한다 |
| 10 | 열린 세션 행이 접힌 카드의 내부 스크롤 밖에 있어 `.card-open` 표시가 안 보인다 | 중 | 낮음 | 오늘 `.sessions` 스크롤 밖 행과 같은 성질. 「행을 열면 그 카드를 자동으로 펼친다」는 규칙을 **넣지 않는다** — 사용자가 안 시킨 상태 변경을 만들지 않는다(YAGNI). 필요해지면 1줄 |

---

## 14. 구현 순서 (검증 가능한 단계로)

각 단계 끝에서 `bash tests/run.sh` 가 통과해야 한다 — **단계 사이에 빨간 상태를 남기지 않는다.**

| # | 단계 | 검증 |
|---|------|------|
| 1 | 드래그 3리스너를 `CARD_SELECTOR` 로 좁힌다(U10). **다른 변경보다 먼저** — 지금 코드에서도 무해하고, 뒤로 미루면 2단계에서 즉시 결함이 된다 | 기존 검사 전부 통과 + 드래그 재정렬 수동 확인 |
| 2 | `renderSession` 을 `(project, session)` 으로 개정: 행을 `<button class="session-row">` 으로 감싸고 ST26 속성 집합·`renderSessionProgress` 를 붙인다. CSS 신설(§8.2 의 행·진행률 규칙) + 톤다운 스코프 좁히기(U11) | T25-127 앵커 개정 후 통과. §11-1(보이는 세션 수 불변) 실측 |
| 3 | 확장: 상수·상태 4함수·셰브론 렌더·`applyCardExpandedState`·리스너(위치 주의) + CSS. 패널 IIFE 가드 1줄 교체 | 확장 토글 동작·`file://` 확인 |
| 4 | 트리·보기 모드 삭제(함수 9개·상수 6개·CSS 약 20규칙·헤더 버튼·`render()` 분기 2곳) | 잔재 0 검사 통과 |
| 5 | 머리 주석 개정: H1⁗ ③ 문장 교체 · 정적 노드 목록에서 `#dzh-view-toggle` 제거 · 패널 신원 문단의 「트리 모드」 서술을 「카드·세션 행」으로 · 트리 CSS 근거 문단 삭제 · 뒤집은 결정(ST17·ST18·ST19·ST21)을 이 PRP 로 가리키는 한 줄 | 사람이 읽어 거짓이 없는지 확인(OC12 의 관례 — 「거짓말을 남기지 않는다」) |
| 6 | `tests/run.sh` 개정·신설 + `tests/mutations.tsv` + 래칫 상수 확인 | 전체 스위트 + 원장 검사(T37-11·T37-14) |
| 7 | `hub/README.md` 갱신 | 문서 정합 가드 통과 |

**NOT Building (범위 밖 — 명시적으로 안 만든다)**

- 잎 = 실행 단위(`agent_id`) 타임라인 (ST19 §19 보류 항목 그대로 유지)
- 세션 행을 열면 그 카드를 자동으로 펼치는 규칙 (위험 10)
- 확장 상태의 서버 동기화 / 스냅샷 반영 (§6)
- 세션 정렬·필터 UI, 「전부 펼치기」 일괄 버튼
- 카드 안 세션의 검색·하이라이트
- DOM diff 렌더러로의 전환 — **명시적 기각**: 문제 4 는 스크롤 컨테이너를 없애서 푼다.
  diff 렌더러는 `render()`·드래그 라이브 이동(O6·DG4)·`applyOpenCardMarking`(OC8)·H1⁗ 전체를
  다시 설계하게 만들고, 얻는 것은 이 설계가 이미 없앤 스크롤 상태의 보존뿐이다
