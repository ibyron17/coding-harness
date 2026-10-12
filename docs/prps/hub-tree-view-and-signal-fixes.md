# 허브 UI — 확장부 트리 뷰 · 배지 halo 제거 · 세션 행 선택 여백 (hub-tree-view-and-signal-fixes)

> 상태: **설계(미승인) — 재설계 회차.** 직전 설계 `docs/prps/hub-unified-card-tree-ui.md`(opus 작성,
> 구현·검수·머지 완료, PR #12)의 **산출물을 사용자가 보고 반려**했다(3건, §1.1). 이 문서는 코드를
> 바꾸지 않는다 — §14 의 열린 질문(특히 안 A/안 B 선택)에 대한 사용자 승인 전에는 구현을 시작하지
> 않는다.
> 설계 모델: **fable(기준 4 — 직전 설계가 반려된 재설계 회차)**.
>
> **프리뷰 목업(사용자 요구, 이번 회차의 1순위 산출물)**:
> `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/af5c0abe-fd76-4e66-b192-db8330617b7a/scratchpad/preview_tree.html`
> — 단독 실행 HTML 1개(외부 의존성 0). 현재(반려 상태) 카드 1장 + 제안 화면 (a)접힘·(b)펼침 2세션·
> (c)펼침 4세션+에이전트/워크플로우·(d)세션 행 선택, 안 A/안 B 나란히, 최소 폭(320px 트랙), 다크 테마.
> 실구현이 만들 DOM·클래스명과 같다(목업 전용 장치는 `.mock-*` 접두로 격리, 파일 머리 주석 참조).
>
> 대상: `hub/bin/hub_template.html` 의 **CSS 계층**(+ JS 문자열 리터럴 2개) · `tests/run.sh` ·
> `tests/mutations.tsv` · `hub/README.md` · 직전 PRP 의 번복 주석. **스냅샷 JSON 계약(`hub/bin/*.py`)은
> 한 줄도 바꾸지 않는다.** `commands/dashboard_template.html` 도 건드리지 않는다(§2.1).

---

## 1. 요구사항 요약

직전 회차는 카드/트리 두 화면을 카드 하나로 통합하면서 (i) 진행중 세션 신호를 세션 배지의 정적
halo 로, (ii) 카드 확장을 세로 아코디언 리스트로, (iii) 세션 행을 `<button>` 으로 만들었다. 사용자는
산출물을 보고 세 가지를 반려했다 — halo 가 붙은 자리가 틀렸고, 확장은 「트리 뷰」가 아니라 「리스트를
아래로 늘린 것」이며, 행 선택 배경이 콘텐츠에 붙어 답답하다. 이 PRP 는 그 셋을 고친다: **배지 halo 를
제거**하고(과제 A), **확장부를 세로 들여쓰기 트리(연결선 `├─ └─` + 들여쓰기)로 다시 설계**하며(과제 B),
**선택/hover 배경에 여백과 모서리를 주되 행 높이는 늘리지 않는다**(과제 C). 세 과제 모두 **CSS 계층
안에서 끝나고 DOM·JS 는 문자열 2개 외에 바뀌지 않는다** — 그래서 프리뷰 목업이 실구현과 같은 DOM 위에
같은 CSS 를 얹어 만들 수 있었다.

### 1.1 사용자 반려 원문 → 근인 → 해법

| # | 반려(요지) | 근인 | 해법 | 결정 |
|---|-----------|------|------|------|
| 1 | halo 는 **대시보드의 `span.chip`** 에 걸라는 것이었는데 허브의 `div.card span.badge.state-working` 에 걸었다. `span.badge` 에는 glow 불필요. 대시보드 `ol.steps li` 진행중 효과도 안 고쳐진 듯 | 허브 쪽: 직전 결정 **U8** 이 `.sessions .badge.state-working{box-shadow:…}` 를 만들었다(hub_template.html `.badge.state-done` 규칙 바로 아래). 대시보드 쪽: **코드 결함이 아니다** — 오케스트레이터 확정(§2.1) | 그 규칙 1개와 그 주석 블록을 삭제한다. 대시보드 템플릿은 무변경 | **V1** |
| 2 | 셰브론을 누르면 **트리 뷰**가 나올 줄 알았는데 리스트를 아래로 늘린 UI 다. 프리뷰 없이 설계만 하니 결과를 예측할 수 없다 → 프리뷰 이미지를 만들어라 | 직전 결정 **U2** 가 「연결선·들여쓰기」를 조직도 은유와 함께 통째로 버렸다. 남은 것은 x 원점이 같은 균일한 행 + 구분선 = 리스트 | 펼친 카드에서만 세션 목록을 **세로 들여쓰기 트리**로 그린다 — 레일·갈고리(`├─ └─`)·2단 자식(진행·위임). 전부 `.card.card-expanded` 스코프 CSS, DOM 변경 0. 프리뷰 목업 동봉 | **V2~V8** |
| 3 | `button.session-row` 선택 배경이 안의 콘텐츠·테두리와 너무 붙어 보인다 → 여백을 | `.sessions li{padding:7px 0}` 이 세로 여백을 li 가 갖고 버튼은 `padding:0` 이라 배경이 텍스트에 딱 붙고, 가로는 콘텐츠 폭 끝까지 간다 | 세로 패딩을 li 2px + 버튼 5px 로 **재배분**(합 14px 불변 → 행 높이 증분 0), 버튼을 좌우 8px **번지게**(`margin:0 -8px`) 하고 모서리 8px. hover 도 같은 요소라 같은 기하 | **V9** |

### 1.2 성공 기준

1. `hub_template.html` 의 `.badge.state-working` 계열 규칙 어디에도 `box-shadow`·`animation` 이 없다. `@keyframes` 는 여전히 2개다.
2. 펼친 카드가 **연결선과 들여쓰기**를 가진 트리로 보인다(§5.1 의 네 요소). 가로 스크롤 컨테이너는 `#dzh-app` 안에 0개다.
3. 접힌 카드는 **셰브론과 hover/선택 배경의 기하를 제외하고 픽셀 단위로 오늘과 같다** — 특히 한 카드에 보이는 세션 수·텍스트 x 좌표 불변.
4. 세션 행 선택/hover 배경이 콘텐츠와 위아래 5px·좌우 8px 떨어져 있고 모서리가 둥글며, 두 배경의 모양이 같다.
5. 기존 계약 전부 유지: `CARD_SELECTOR` 드래그 3리스너 · 세션 행 클릭 = 그 세션 대시보드 · 셰브론 클릭은 패널을 열지 않음 · `localStorage['dzh-expanded-projects']` · 스냅샷 JSON 무변경 · 새 외부 의존성 0 · 새 `@keyframes` 0.
6. `bash tests/run.sh` · `tests/hub` · `tests/commands` 전부 통과. 새 색 토큰 0.

---

## 2. 착수 전 확인

### 2.1 오케스트레이터가 확정한 사실 (재조사하지 않았다)

- 지적 1 의 **대시보드 쪽은 코드 결함이 아니다.** `commands/dashboard_template.html` 에 `ol.steps li.active .chip::after` halo 가 이미 있다. 사용자가 본 것은 옛 템플릿으로 구워진 생성물(`.claude/dashboards/*.html` — `init` 시점에 `<style>` 이 통째로 복사돼 굳는다)이다. **대시보드 템플릿과 생성물 재발행은 이번 범위 밖**이다.
- 지적 1 의 **허브 쪽만 실제 결함**이다: `.sessions .badge.state-working{box-shadow:0 0 10px -1px var(--accent)}`. `.card.card-working` 의 카드 bloom(정적 바깥 bloom + `::after` 맥동)은 **유지**한다 — 사용자가 지목한 것은 `span.badge` 뿐이다.

### 2.2 이 회차의 실측 (main `5f1809f`)

| 항목 | 실측 | 함의 |
|------|------|------|
| `collect_guard_ids tests/run.sh` (같은 규칙으로 재현) | **474** = `SOURCE_GUARD_ID_FLOOR` | 하한이 실측과 일치 — 이번 순증가가 그대로 새 하한이 된다(§11.3) |
| 원장 변조행(3열 ≠ `-`) / 면제행(3열 = `-`) | **81** / **400** | `LEDGER_MUTATION_ROW_FLOOR=81` 과 일치, `LEDGER_EXEMPT_ROW_RATCHET=404` 에 여유 4 |
| 가드 ID 최대 | T25-**189** · T22-**170** | 신규 가드는 **T25-190** 부터 |
| `@keyframes` (허브 문서 전체) | 2 (`card-working-glow` · `dzh-refresh-spin`) | 이번 설계는 0개 추가 — 그 수를 가드로 고정한다(T25-195) |
| halo 규칙을 무는 가드 | **T25-186 하나** | 삭제 대상. 다른 가드는 `.badge.state-working` 을 보지 않는다 |
| `.sessions li{` · `.session-row{` · `.sessions{` 를 무는 가드 | **없음**(T25-147 보조가 `.sessions{…}` 에 `overflow:hidden` 이 없는지만 본다 — 유지) | 과제 C 는 기존 가드를 깨지 않는다. 대신 새 계약(합 14·번짐 짝)을 가드로 세운다 |
| 펼침 계약 가드 T25-185 | `.card.card-expanded{height:auto}` · `.card:not(.card-expanded) .session-tier1{display:none}` | 둘 다 **그대로 살아남는다**(트리는 이 두 규칙 위에 얹힌다) |
| 세션 행 가드 T25-127 | `function renderSession(project, session){` 앵커 + `.session-line` 첫 줄 구성 | **무변경**(DOM 을 안 바꾸므로) |
| 트리 잔재 가드 T25-178 | `tree-section`·`tree-node`·`tree-root`·`tree-leaf`·`renderProjectTree`·`renderTreeRoot`·`renderSessionNode`·`initializeTreeRootScrollPositions` 0건 | 이번 설계는 **새 클래스명·새 함수를 하나도 만들지 않는다** — 충돌 불가 |
| T25-161 | `'data-session-id'` 리터럴 정확히 2회 | 새 CSS 에 `[data-session-id]` 속성 선택자를 쓰지 않는다(쓰면 3회가 된다) |
| T25-188 | README 에 `확장`·`세션 행` 있음 / `트리 모드`·`보기 토글` 없음 | README 갱신 문구는 「트리 모드」를 쓰지 않는다(「트리로」·「연결선」을 쓴다) |
| 격자 트랙 폭 | `.wrap` 1440 − 거터 32 = 1408 → 트랙 (1408−24)/3−1 ≈ **460px**, 최소 **320px** | 카드 콘텐츠 폭(테두리 2 + 패딩 40 제외) **418px ~ 278px** — 들여쓰기 예산의 분모(§5.3) |

---

## 3. 영향 범위 (파일별)

| 파일 | 조치 | 내용 |
|------|------|------|
| `hub/bin/hub_template.html` | UPDATE | `<style>`: halo 규칙+주석 삭제(A) · `.sessions`/`.sessions li`/`.session-row` 3규칙 개정(C) · `.card.card-expanded` 스코프 트리 규칙 신설(B, 안 A 약 20줄 / 안 B 약 25줄). 렌더 IIFE: `expandToggleLabel` 의 문자열 2개(V10). 머리 주석: 확장 문장에 후계 PRP 포인터 1구. **그 외 JS 0줄** |
| `tests/run.sh` | UPDATE | T25-186 삭제 → T25-190(역가드) · 신규 T25-191~T25-195 · T25-188 개정(`연결선` 토큰) · 래칫 2종 상수+역사 주석 · T25 그룹 desc |
| `tests/mutations.tsv` | UPDATE | T25-186 행 삭제 · 신규 변조행 6건(T25-190~195) · 헤더 인용 2줄(`LEDGER_MUTATION_ROW_FLOOR(`·`SOURCE_GUARD_ID_FLOOR(`) · **T99-6 행의 sed 리터럴 `(81`→`(86`** |
| `hub/README.md` | UPDATE | 「셰브론을 누르면 카드가 펼쳐진다」 불릿을 트리 서술로 교체(연결선·자식 노드) |
| `docs/prps/hub-unified-card-tree-ui.md` | UPDATE(주석만) | 상태 배너에 후속 반려 1문단 · 결정 U8 행에 「번복」 · §12 질문 1 행에 후속 1구. 본문은 당시 판단의 기록으로 보존(공개 번복 관례: SP19→SP4, ST17→U1) |
| `hub/bin/hub_model.py`·`hub_project.py`·`hub_session.py` 등 `hub/bin/*.py` | **무변경** | §8 |
| `commands/dashboard_template.html`·`.claude/dashboards/*` | **무변경** | §2.1 |
| `tests/hub/*.py`·`tests/commands/*.py` | **무변경** | 직전 PRP 전수 확인 유지 — CSS 셀렉터를 무는 파이썬 테스트 없음 |

---

## 4. 과제 A — 세션 배지 halo 제거

### 4.1 근인

직전 결정 **U8**(「진행중 세션 신호는 행 배지의 정적 halo」)이 대시보드 `li.active .chip` 의 halo 기하를
허브 `span.badge.state-working` 으로 옮겼다. 사용자의 원 요청은 대시보드 칩에 대한 것이었고, 허브 배지에는
필요 없다는 판정이다. 대시보드 쪽 지적은 옛 생성물 문제다(§2.1).

### 4.2 해법 (결정 V1)

`hub_template.html` `<style>` 에서 다음을 삭제한다 — 규칙 1줄과 그 위 「진행중 세션 신호(결정 U8, …)」
주석 블록(7줄, 앵커: `/* 진행중 세션 신호(결정 U8` 로 시작해 `.sessions .badge.state-working{…}` 로 끝나는
연속 구간). `.badge.state-working{background:var(--accent-ink);color:var(--bg)}` 와 그 주석은 **그대로**
둔다(그것이 남는 채널이다).

### 4.3 halo 를 없앤 뒤 「이 카드 안 어느 세션이 도는가」를 답하는 채널 — **3개(보장) + 1개(조건부)**

| # | 채널 | 어디 | 성질 |
|---|------|------|------|
| 1 | 텍스트 「작업중」 | `STATE_LABEL.working` | 보장 — 배지 본문 |
| 2 | 글리프 `●` | `STATE_GLYPH.working` | 보장 — 색각 무관 형태 채널 |
| 3 | **반전 채움** `background:var(--accent-ink);color:var(--bg)` | `.badge.state-working` | 보장 — 4개 상태 중 **유일한 채움 배지**다(idle = `--soft` 플랫, stale = `--attention` 점선 윤곽, done = 투명 윤곽). 세션 목록 안에서 채도 있는 면은 이것뿐이라 전주의(pre-attentive)로 튄다 |
| 4 | 실행중 에이전트 칩 `.agent-chip-running` (`●` + `--accent-ink`/`--accent-soft`) | `renderAgentChip` | **조건부** — 그 세션이 지금 서브에이전트를 돌리고 있을 때만 |

충분성의 근거: 「어느 **프로젝트**가 도는가」(격자를 훑을 때)는 `.card.card-working` 의 bloom+테두리가
그대로 답하고, 「이 카드 안 어느 **세션**인가」는 카드 하나를 읽는 동안 답하면 되는 질문이라 배지 3채널로
족하다 — 이는 U8 자신의 §9.4 관찰(두 질문은 같은 순간에 필요하지 않다)을 그대로 따른 것이고, 다른 것은
「두 번째 신호에 halo 조차 필요 없다」는 사용자의 판정이다. 트리(과제 B)에서는 배지가 갈고리 `├─` 바로
오른쪽에 놓이므로 레일 한 줄을 따라 내려가며 `●` 를 찾는 스캔 경로가 생긴다 — 리스트보다 오히려 낫다.

### 4.4 딸린 것 — 전수

| 대상 | 조치 |
|------|------|
| `tests/run.sh` **T25-186** (`.sessions .badge.state-working{…}` 규칙 존재 + `animation` 없음) | **삭제.** 규칙이 사라지므로 「존재」 단언이 정확히 반대로 뒤집힌다. 그 자리를 **역가드 T25-190**(§11.2)이 잇는다 — 「배지 halo 가 검토 없이 되살아나지 않는다」는 사용자 결정의 기계적 표현 |
| `tests/mutations.tsv` **T25-186 행**(`animation` 을 끼워 넣는 변조) | **삭제** → T25-190 변조행(halo 규칙을 다시 끼워 넣는 변조) 신설. 변조행 수 −1+1 = 0 |
| `docs/prps/hub-unified-card-tree-ui.md` §9.1 U8 행 · §9.4 · §12 질문 1 | **번복 주석**(§3 의 3곳). 「정적 halo, 새 애니메이션 없음」 승인 중 **「새 애니메이션 없음」은 유효**하고 「정적 halo」만 반려됐다 — 그 구분을 §12 질문 1 행에 한 구로 적는다 |
| `hub_template.html` 머리 주석 | `.card.card-working` 주석의 「대시보드 진행중 단계 칩의 halo 와 같은 두 숫자」 문장은 **대시보드** 칩 이야기라 참으로 남는다 — 무변경 |
| 래칫 3종 | A 단독으로는 **전부 0 이동**(ID 접두 −1+1, 변조행 −1+1, 면제행 0). B·C 와 합산은 §11.3 |
| `hub/README.md` | halo 서술 없음(「카드 glow」 언급 1건은 카드 bloom 이라 참) — 무변경 |

---

## 5. 과제 B — 확장부를 세로 들여쓰기 트리로

### 5.1 무엇이 「리스트로 보이는가」와 「트리로 보이는가」를 가르는가

리스트는 **x 원점이 같은 균일한 행을 구분선으로 쌓은 것**이다 — 행 사이의 관계는 「이웃」뿐이고 부모는
암시된다. 트리는 네 가지가 있어야 한다: ① **들여쓰기**(깊이가 x 원점의 이동으로 인코딩된다), ② **연결선**
(레일과 `├─ └─` 갈고리가 부모→자식 변을 *그린다*), ③ **레일이 내려오는 보이는 루트**, ④ **끝나는 잎**(`└─`).
직전 확장부는 넷 다 없었다 — 행의 x 원점이 카드 본문과 같고, 형제는 구분선으로만 갈리고, 루트(프로젝트
머리)와 행 사이에 그려진 변이 없었다. 「트리 뷰」의 시각적 정본은 연결선과 들여쓰기이지 가로 배치가 아니다
(사용자가 아코디언과 트리를 구별한 지점이 정확히 이것이다). 이 설계는 ①~④ 를 전부 넣되 **가로 배치는
쓰지 않는다** — 그것은 직전 회차가 해결한 문제 2·3·4 의 원인이었다.

### 5.2 계층 설계 — 무엇이 노드이고 무엇이 본문인가 (결정 V3·V4)

판정 기준: **세션이 *산출하거나 위임한* 것(자기 수명을 가진 개체)은 자식 노드, 세션 *자신을 서술하는* 것
(신원·상태 속성)은 노드 본문.** 세션 행이 지금 담는 7가지를 이 기준으로 가른다.

| 지금 세션 행의 구성 | 렌더 함수 | 판정 | 근거 |
|--------------------|-----------|------|------|
| 상태 배지 · 경과시간 | `renderStateBadge` · `elapsedLabel` | **노드 라벨 줄**(첫 줄) | 세션의 상태다. 갈고리가 이 줄 중앙에 닿는다 |
| 실행중 에이전트 칩 (≤2) | `renderAgentRuns` | **노드 라벨 줄에 잔류** | 「지금 돌고 있는가」의 **라이브 상태**(● 글리프·accent 색)다 — 배지와 같은 성질. 접힘 화면과 T25-127 이 이 줄의 구성을 고정한다 |
| 시작 시각 · short_id · 모델 | `renderSessionMeta` | **본문** | 세션의 신원 속성 |
| 발췌 | `renderSessionExcerpt` | **본문** | 세션이 받은 과제 — 자기 서술 |
| 세션별 진행률 (tier1 / 대시보드 없음) | `renderSessionProgress` | **자식 노드 「진행」(항상 1개)** | 세션이 *발행한* 대시보드라는 개체의 요약. 없으면 「대시보드 없음」이 그 자리의 잎이다 |
| 워크플로우 칩 행 (≤12) | `renderWorkflowRun` | **자식 노드 「위임」(있을 때)** | 세션이 *위임한* 서브에이전트들의 기록 — 옛 조직도(ST19)의 3단째가 정확히 이것이다. 라이브 칩과 달리 수명이 끝난 항목까지 실린 **기록**이라 라벨 줄이 아니라 자식이다 |
| 세션 행 자체 | `renderSession` | **1단 노드**(루트=카드) | 클릭 단위(= 패널 대상)와 노드가 일치한다 |

「전부 노드로 펴면 소음」의 경계선: 메타 3칸·발췌를 노드로 올리면 세션마다 4~5개의 잎이 생기고 그중 어느
것도 개체가 아니다(시작 시각에 자식이 있을 수 없다). 「전부 뭉치면 트리가 아님」의 경계선: 진행·위임을
본문에 남기면 세션 아래에 아무것도 매달리지 않아 1단 트리(사실상 `├─` 가 붙은 리스트)가 된다. 자식 2종은
그 사이의 최소다.

**「위임」 노드의 두 표현 — 안 A(권고) / 안 B(대안). DOM 은 같고 CSS 5줄이 다르다(목업에 나란히 있다).**

| | 안 A — 위임 = 노드 1개, 본문은 칩 행 | 안 B — 위임 = 에이전트마다 잎 1개(칩을 세로로) |
|---|---|---|
| 모양 | `└─ [설계 — …][구현 — …][검수 R1]` | `├─ [설계 — …]` / `├─ [구현 — …]` / `└─ [검수 R1]` |
| 세션당 높이(에이전트 n) | 진행 노드 + 칩 행(줄바꿈 시 2~3줄) — n 에 거의 무관 | 진행 노드 + n × 22px(상한 `MAX_VISIBLE_WORKFLOW_CHIPS`=12 → 최대 264px) |
| 트리다움 | 자식 2개 고정 — 「폴더」 느낌의 집합 노드 | 옛 ST19 3단(프로젝트→세션→서브에이전트)을 세로로 복원 — 가장 문자 그대로의 트리 |
| 정보 | 같다(칩 툴팁 = 프롬프트/결과 미리보기 그대로) | 같다 |
| 권고 이유 | 세션 4개 × 워크플로우 5~6개짜리 카드가 1,000px 를 넘지 않는다. 확장이 「한눈에」를 위한 것(직전 U4)이라 높이를 아끼는 쪽이 원 목적에 맞는다. **사용자가 목업을 보고 B 를 고르면 CSS 5줄 교체로 끝난다** | 채택 시 U3(3단→2단 강등)을 펼침 상태에 한해 번복하는 것으로 기록한다 |

### 5.3 깊이 상한과 기하 (결정 V5·V6)

- **깊이 상한 = 루트 아래 2단**(세션, 자식). 근거 ① 데이터에 그 아래 구조가 없다 — `agent_runs`·`workflow.agents` 항목은 스냅샷에 자식이 없고, 실행 단위 타임라인은 ST19 §19 이래 보류(NOT Building). ② 비용: 단당 16px 는 최소 카드 콘텐츠 278px 의 5.8%, 2단 32px 는 11.5% 다. 자식 콘텐츠에 남는 **246px** 는 이 트리에 실리는 가장 넓은 고정폭 항목(워크플로우 칩 라벨 18자 모노 ≈131px, `tier1-pct` 는 블록이라 줄바꿈)을 다 담는다. ③ 3단째를 두면 48px = 17% 가 되고 담을 데이터가 없다.
- **단당 들여쓰기 16px** = 레일 오프셋 4 + 갈고리 8 + 간격 4. 파일 탐색기 관례(16~20px)의 하단이고, 폭 예산 때문에 18 이 아니라 16 이다.
- **좌표(카드 콘텐츠 왼끝 = x 0)**: 1단 레일 x=4 · 갈고리 4→12 · 노드 콘텐츠 x=16(선택 배경 상자는 x=8 부터 — 과제 C 의 번짐 8px). 2단 레일 x=20 · 갈고리 20→28 · 자식 콘텐츠 x=32. 두 단이 같은 규칙(「레일은 부모 콘텐츠 왼끝 +4」)을 쓴다.
- **갈고리 y = 17px**(노드 상단 기준). 1단: li 패딩 2 + 버튼 패딩 5 + 첫 줄 중앙 ≈10(배지 19px 상자·`align-items:baseline` 줄상자 ≈20px). 2단 진행 노드: `.tier1-pct`/`.session-no-dashboard` 의 `margin-top:8px` + 12px 글자 줄(18px) 중앙 9 = 17. 안 A 위임 노드: 간격 4 + 칩 첫 줄 중앙 9 = 13. 안 B 잎: `calc(50% + 4px)` (칩 자신의 높이 절반 + 간격 — 매직 넘버 없음). 17·13 은 이 파일의 타이포 상수(11~13px 글자, 패딩 2/5/8)에서 유도된 값이라 주석에 산술을 남기고 구현 시 헤드리스로 ±1px 를 확인한다(§11.6).
- **그리는 방법**: `└` 는 「`border-left` + 바닥선 1px 을 가진 상자 1개」(바닥선은 구현에서 `box-shadow:inset` 이다 — §5.4 편차 절)(`::before`, 노드 상단→갈고리 y)로, `├` 는 그 상자 아래에 레일(`::after`, 갈고리 y→노드 하단)을 이어 붙여 만든다. 마지막 형제는 `::after` 를 끈다. 첫 세션의 상자는 위로 10px(`.sessions` 의 `margin-top`) 더 뻗어 **루트 본문(프로젝트 진행률 줄)에 닿는다** — 레일이 허공에서 시작하지 않게(V12).
- **연결선 색 = `var(--muted)` + `opacity:.5`**. `--line` 이 아닌 이유: 라이트 테마에서 `--line`(#D9E2EC)은 열린 카드 면 `--accent-soft`(#DAE9F7) 위에서 ΔL\* ≈2 로 **사라진다**(카드 여백을 눌러 프로젝트 요약을 연 채 펼치면 트리가 없어진다). `--muted` 50% 는 네 조합 모두 보인다 — 라이트: `--surface` 위 ≈27 · `--accent-soft` 위 ≈22, 다크: ≈29 · ≈24(선형 근사, 프리뷰 다크 열에서 눈으로 확인). 새 색 토큰 0.

### 5.4 CSS 전문 (구현이 그대로 옮긴다)

> **구현 편차 1건(검수 1회차 도입 · 3회차에서 높이 보정 반영, 2026-09-10)** — 트리 갈고리(└)의
> 바닥선을 설계 원안의 `border-bottom` 대신 `box-shadow:inset 0 -1px 0 0 var(--muted)` 로 그린다
> (`.sessions li::before` · `.session-tier1::before` · `.workflow-runs::before` 3줄). **아래 §5.4
> 코드블록의 그 3줄은 실제 구현에 맞춰 이미 고쳐 뒀다** — 문서가 코드와 어긋난 채 남으면 다음
> 회차가 원안을 그대로 옮겼다가 같은 하드 스톱을 다시 맞는다.
> **왜**: `hub_template.html` 전체에서 `border-bottom:` 선언이 0건이어야 한다는 **T25-85(결정 G8)**가
> 이미 하드 스톱으로 걸려 있었다 — 원출처는 `docs/prps/hub-detail-side-panel.md` R2 승인 항목 6
> (1801~1814행, 시안 C 탈락으로 토큰을 좁힐 이유가 사라져 0건으로 확정)이고,
> `hub-panel-polish-and-icons.md`(G2·536행)는 그것을 승계·재확인만 한다 — 이 절의 CSS 를 그대로 넣으면
> 스위트가 즉시 실패한다. 이 충돌은 **§2.2 의 가드 전수 조사에서 T25-85 가 빠져** 설계 시점에 잡히지
> 않았다. **기하 영향**: `box-sizing:border-box`(186행 `*` 리셋)는 의사요소에 적용되지 않아, 원안
> (`border-bottom`)이었다면 렌더 높이가 border 폭만큼 밖으로 늘어 바닥선이 host 기준 y=17 에
> 그려졌을 것이다. `box-shadow` 는 상자 안쪽에 그리므로 높이를 원안 값 그대로 두면 바닥선이 y=16
> — 1px 위다. 그래서 상자 높이 자체를 1px 올렸다(`.sessions li::before`·`.session-tier1::before`
> 17→18, `.sessions li:first-child::before` 27→28, `.workflow-runs::before` 13→14) — 이제 바닥선이
> y=17, **원안과 같은 자리**다. §5.3 의 「갈고리 y = 17px」는 이 보정 덕에 문자 그대로 참이다.
> §11.6-4 실측 갈고리↔배지 정렬(1단 ±0.5px — 배지 테두리 유무로 부호가 갈린다: state-stale·
> state-done −0.5px, state-working·state-idle +0.5px / 2단 진행 노드 0px — `.tier1-pct` 의
> margin-top 8 + 줄상자 중앙 9 = 17 이 바닥선 y 와 정확히 만난다(line-height 가 정수 18px 로
> 계산돼 반올림 여지가 없고 dsf 1·2 에서 같다) / 2단 위임 노드 −0.1484px, 헤드리스 Chrome 152·
> 실데이터 실측)이 이
> 문서의 허용치(≤1px, §11.6-4·§13 위험1) 안이다. **되돌리지 않는다** — 되돌리면 T25-85 가 다시
> 걸린다. 이 대체는 `docs/prps/hub-detail-side-panel.md` 1810~1814행이 지목한 「함께 막아야 할
> 우회로」(철자 가드를 `box-shadow` 로 우회)와 같은 형태이지만, 거기 G8 이 막던 것은 헤더/본문을
> 가르는 전폭 하드 디바이더(`--line`)이고 여기는 8px 폭 트리 연결선(`--muted` 50%)이라 목적·색·
> 굵기 인상이 달라 별개로 판단했다(코드 주석: `hub/bin/hub_template.html` 425~449행).

**과제 C 3규칙**(§6)이 먼저, 그 뒤에 아래 트리 블록이 `.session-row.card-open{…}` 규칙 뒤에 들어간다.
전 규칙이 `.card.card-expanded` 로 시작한다 — 접힘 카드에 닿는 선택자가 하나도 없다(가드 T25-191).

```css
/* ── 펼친 카드 = 세로 들여쓰기 트리(결정 V2~V8, docs/prps/hub-tree-view-and-signal-fixes.md §5) ──
   전부 .card.card-expanded 스코프 — 접힘 카드는 픽셀 단위로 그대로다. DOM·JS 변경 0.
   기하(px): 레일 = 부모 콘텐츠 왼끝 +4, 갈고리 8, 자식 = 부모 +16(단당 16, 상한 2단 = 32).
   갈고리 y 17 = li 2 + 버튼 5 + 첫 줄 중앙 ≈10 / 진행 노드는 .tier1-pct margin-top 8 + 줄 중앙 9.
   └ 는 border-left+box-shadow(inset 바닥 1px) 상자(::before) 하나, ├ 는 그 아래 레일(::after)
   — 마지막 형제는 끈다(원안은 border-bottom 이었다, 위 편차 절).
   색은 --muted 50% — --line 은 열린 카드 면(--accent-soft) 위에서 ΔL* ≈2 로 사라진다(라이트). */
.card.card-expanded .sessions{padding-left:24px}                      /* 8(번짐) + 16(1단 들여쓰기) */
.card.card-expanded .sessions li{position:relative;border-top:0}      /* 구분선 대신 연결선이 형제를 가른다 */
.card.card-expanded .sessions li::before,
.card.card-expanded .sessions li::after,
.card.card-expanded .session-tier1::before,
.card.card-expanded .session-tier1::after{content:"";position:absolute;left:-12px;border-left:1px solid var(--muted);opacity:.5}
.card.card-expanded .sessions li::before{top:0;height:18px;width:8px;box-shadow:inset 0 -1px 0 0 var(--muted)}
.card.card-expanded .sessions li:first-child::before{top:-10px;height:28px}     /* 루트 본문까지 레일 연장(V12) */
.card.card-expanded .sessions li::after{top:17px;bottom:0}
.card.card-expanded .sessions li:last-child::after{display:none}
/* 본문(첫 줄·메타·발췌) 뒤에 자식(진행·위임)이 오도록 시각 순서만 바꾼다 — DOM 순서(접힘 화면)는 불변(V7). */
.card.card-expanded .session-row{display:flex;flex-direction:column}
.card.card-expanded .session-row>.excerpt{flex-basis:auto}
.card.card-expanded .session-row>.session-tier1{order:1}
.card.card-expanded .session-row>.workflow-runs{order:2}
.card.card-expanded .session-meta{flex-wrap:wrap}                      /* 최소 폭에서 들여쓰기 16px 만큼 잃은 자리 보전 — 펼침 한정 */
/* 2단 자식. 진행 노드는 항상 있고(대시보드 없음 포함), 위임 노드가 뒤따를 때만 레일을 잇는다(~ 결합자 —
   DOM 에서 .workflow-runs 가 .session-tier1 앞에 있다). */
.card.card-expanded .session-tier1,
.card.card-expanded .workflow-runs{position:relative;margin-left:16px}
.card.card-expanded .session-tier1::before{top:0;height:18px;width:8px;box-shadow:inset 0 -1px 0 0 var(--muted)}
.card.card-expanded .session-tier1::after{display:none;top:17px;bottom:-4px}    /* -4 = .workflow-runs margin-top */
.card.card-expanded .workflow-runs ~ .session-tier1::after{display:block}
/* 안 A(권고) — 위임 노드 1개, 본문은 칩 행 그대로. 13 = 간격 4 + 칩 첫 줄 중앙 9. */
.card.card-expanded .workflow-runs::before{content:"";position:absolute;left:-12px;top:-4px;height:14px;width:8px;
  border-left:1px solid var(--muted);box-shadow:inset 0 -1px 0 0 var(--muted);opacity:.5}
```

**안 B 채택 시** 마지막 `.workflow-runs::before` 규칙을 다음 5규칙으로 **교체**한다(나머지는 동일):

```css
.card.card-expanded .workflow-runs{flex-direction:column;align-items:flex-start;gap:4px}
.card.card-expanded .workflow-runs>.agent-chip{position:relative}
.card.card-expanded .workflow-runs>.agent-chip::before,
.card.card-expanded .workflow-runs>.agent-chip::after{content:"";position:absolute;left:-12px;border-left:1px solid var(--muted);opacity:.5}
.card.card-expanded .workflow-runs>.agent-chip::before{top:-4px;height:calc(50% + 4px);width:8px;box-shadow:inset 0 -1px 0 0 var(--muted)}
/* ↑ 기각안이지만 되살린다면 여기도 box-shadow 여야 한다 — border-bottom 은 T25-85 가 막는다(위 편차 절). */
.card.card-expanded .workflow-runs>.agent-chip::after{top:50%;bottom:-4px}
.card.card-expanded .workflow-runs>.agent-chip:last-child::after{display:none}
```

왜 `order` 인가(V7): DOM 순서는 `.session-line → .session-meta → .workflow-runs → .session-tier1(접힘에서
숨김) → .excerpt` 다. 트리에서는 본문(발췌)이 자식보다 앞에 와야 하는데 DOM 을 바꾸면 접힘 화면에서
워크플로우 칩 행과 발췌의 순서가 뒤집혀 제약 5(접힘 픽셀 동일)를 깬다. `display:flex;flex-direction:column`
+ `order` 는 펼침에서만 시각 순서를 바꾸고 DOM·접힘을 건드리지 않는다. 대가는 보조기술의 읽기 순서가 DOM
순서(발췌가 진행률 뒤)로 남는 것 — 세션 행은 `<button>` 하나라 접근 가능 이름이 어차피 연결 문자열이다
(위험 §13-2). `.excerpt{flex-basis:100%}` 는 세로 flex 컨테이너의 주축(높이)에 대한 백분율이 되는데,
컨테이너 높이가 부정(auto)이라 명세상 `content` 로 낙착한다 — 그래도 Safari 계열의 세로 flex 백분율 이력
때문에 `flex-basis:auto` 1줄로 명시한다.

### 5.5 DOM·JS — 변경 0 + 문자열 2개 (결정 V10)

`renderSession`·`renderProject`·`sessionRowAttributes`·리스너·패널 IIFE 전부 **무변경**. 유일한 JS 변경은
`expandToggleLabel` 의 반환 문자열이다 — 셰브론이 여는 것이 「목록 전부」가 아니라 「트리」가 됐으므로:

```js
function expandToggleLabel(isExpanded, sessionCount){
  return isExpanded ? '트리 접기' : '세션 ' + sessionCount + '개 트리로 보기';
}
```

(옛: `'세션 목록 접기'` / `'세션 N개 모두 보기'`. 무는 가드 없음 — §2.2.)

### 5.6 넘을 수 없는 제약 7건 대조

| # | 제약 | 이 설계 |
|---|------|--------|
| 1 | 가로 조직도로 회귀 금지(문제 2·3·4 의 원인). 가로 스크롤 컨테이너 0개 유지 | 가로 배치 없음. 새 `overflow` 선언 0. 새 규칙은 전부 세로 축 pseudo-element·패딩·`order` 다. 과제 C 의 번짐은 스크롤 컨테이너(`.sessions`)의 **패딩 박스 안**에 머문다(§6.3, 가드 T25-193) |
| 2 | 세로 들여쓰기 트리, 정본은 연결선+들여쓰기 | §5.1·§5.3 |
| 3 | 폭이 좁다 — 들여쓰기 상한과 근거 | 2단·32px(§5.3). 최소 폭 카드가 목업에 있다 |
| 4 | 무엇을 노드로 올리고 무엇을 본문에 남기나 | §5.2 표 |
| 5 | 접힘 상태 픽셀 동일(340px, 셰브론 외 변화 없음) | 트리 규칙 전부 `.card.card-expanded` 스코프(가드 T25-191). 과제 C 는 hover/선택 **배경 기하만** 바꾸고 텍스트 x·행 높이는 불변(가드 T25-192) — 사용자가 요청한 변화다 |
| 6 | `CARD_SELECTOR` 드래그 3리스너 · `data-project-path` 확산 금지 · 세션 노드 클릭 = 그 세션 대시보드 · 셰브론은 패널을 안 연다 · `localStorage` 확장 유지 · 스냅샷 계약 불변 · 새 의존성 0 | 자식 노드는 **버튼 안의 기존 요소**라 새 속성이 0개다 — 자식 어디를 눌러도 `closest(CLICKABLE_CARD_SELECTOR)` 가 그 세션 행을 고른다. 자식을 버튼 밖 형제로 빼는 안은 **기각**했다: 그러면 자식 클릭이 카드(프로젝트 요약)로 새거나, 막으려면 자식에 `data-project-path` 를 뿌려야 한다(T25-181 이 지키는 결함의 재발) |
| 7 | 새 `@keyframes` 금지(현재 2개) | 0개 추가. **개수 2 를 가드로 고정**(T25-195) |

### 5.7 선택/hover 상자 = 서브트리 전체 (결정 V8)

자식이 버튼 안에 있으므로 hover/선택 배경은 노드 라벨·본문·자식을 한 상자로 감싼다. 이것은 결함이 아니라
**클릭 단위의 정직한 표시**다 — 그 상자 어디를 눌러도 같은 세션 대시보드가 열린다. 2단 연결선은 상자 안에
그려지고(`--muted` 50% 는 `--accent-soft` 위에서도 보인다, §5.3), 1단 갈고리의 끝(x 8→12)은 상자 아래로
들어가 「`├─[노드 상자]`」로 읽힌다. 목업 (c)·(c′) 의 첫 세션이 이 상태다.

---

## 6. 과제 C — 세션 행 선택/hover 배경의 여백

### 6.1 지금의 기하

`.sessions li{padding:7px 0;border-top:1px solid var(--soft)}` · `.session-row{…padding:0}` ·
`.session-row.card-open{background:var(--accent-soft)}` · `.session-row:hover{background:var(--soft)}`.
세로 여백 14px 는 전부 **li** 가 갖고 버튼은 0 이라 배경 상자가 배지 윗변·발췌 밑변에 딱 붙는다. 가로로는
버튼이 콘텐츠 폭 100% 라 카드 본문의 x 원점에서 시작해 콘텐츠 끝에서 끊긴다 — 여백도 모서리도 없다.

### 6.2 두 안의 높이 산술 → 안 1 권고 (결정 V9)

| 안 | 규칙 | 행당 높이 증분 | 세션 3건 기준 | 평가 |
|----|------|---------------|--------------|------|
| **1. 재배분(권고)** | `.sessions li{padding:2px 0}` + `.session-row{padding:5px 8px}` | **0px** (2+5 = 7 위·아래 그대로) | 0px | 배경이 콘텐츠에서 위아래 5px 떨어지고, 구분선과 2px 간격이 남는다. 접힘 카드에 보이는 세션 수 불변 |
| 2. 추가 | `.sessions li{padding:7px 0}` 유지 + `.session-row{padding:p px 8px}` | **+2p** (p=5 → +10px) | +30px | 세션 영역(≈340 − 머리 블록 ≈150 = 약 190px, 미실측)에서 30px 는 행 하나(≈60px)의 절반 — 3건이 2건으로 줄 위험이 크다(MC1~MC5 가 같은 계열에서 실측한 함정). 배경-구분선 간격은 7px 로 더 넓지만 그 차이는 5px 도 충분히 낸다 |

안 1 을 택한다. 세로 5px·가로 8px·모서리 8px(카드 14, 칩 5~6 사이의 위계). 두 배경(`:hover`·`.card-open`)은
**같은 요소의 배경**이라 기하가 정의상 같다 — 규칙을 더 쓰지 않는다.

### 6.3 가로 번짐과 스크롤 컨테이너 (★놓치면 가로 스크롤바가 되살아난다)

텍스트 x 원점을 지키면서 배경을 좌우로 넓히려면 버튼을 **카드 패딩 쪽으로 8px 번지게** 해야 한다:
`margin:0 -8px;width:calc(100% + 16px)` (버튼은 `display:block` 이어도 폭이 자동으로 늘지 않아 `width` 를
명시한다 — 지금 `width:100%` 가 있는 이유와 같다). 문제는 `.sessions{overflow-y:auto}` — 접힘 카드에서
스크롤 컨테이너다. `overflow-y:auto` 는 `overflow-x` 를 `auto` 로 강제하므로 버튼이 ul 의 패딩 박스를 넘으면
**가로 스크롤바**가 생긴다(직전 회차가 0개로 만든 바로 그것). 그래서 ul 에 같은 값으로 **패딩을 주고 마진을
되돌린다**: `.sessions{margin:10px -8px 0;padding:0 8px}`. 버튼의 테두리 상자가 정확히 ul 의 패딩 박스와
일치해 넘침이 0 이다. 카드 패딩 20px > 8px 라 `.card{overflow:hidden}` 에도 걸리지 않는다. 구분선(`li`
`border-top`)은 콘텐츠 폭에 남고 배경만 8px 더 넓다(macOS 사이드바 관용구). **네 숫자(ul 마진·ul 패딩·
버튼 마진·버튼 폭 초과분/2)가 같아야 하는 계약**을 가드 T25-193 이 잠근다.

```css
/* 세션 행 선택/hover 배경 여백(결정 V9, docs/prps/hub-tree-view-and-signal-fixes.md §6) — 세로 패딩을
   li 7 → li 2 + 버튼 5 로 재배분(합 14 불변, 행 높이 증분 0). 가로는 버튼을 좌우 8px 번지게 하고(텍스트
   x 원점 불변) ul 의 padding/margin 을 같은 값으로 짝지어 스크롤 컨테이너(overflow-y:auto) 안에 가둔다 —
   이 짝이 어긋나면 접힘 카드에 가로 스크롤바가 생긴다(T25-193). */
.sessions{list-style:none;margin:10px -8px 0;padding:0 8px;font-size:13px;flex:1 1 auto;min-height:0;overflow-y:auto}
.sessions li{padding:2px 0;border-top:1px solid var(--soft)}
.session-row{display:block;width:calc(100% + 16px);margin:0 -8px;font:inherit;color:inherit;text-align:left;
             background:none;border:0;padding:5px 8px;border-radius:8px;cursor:pointer}
.session-row:hover{background:var(--soft)}                                /* 무변경 */
.session-row:focus-visible{outline:2px solid var(--accent);outline-offset:2px}   /* 무변경 — 둥근 상자를 따라간다 */
.session-row.card-open{background:var(--accent-soft)}                     /* 무변경 */
```

### 6.4 접힘 화면에서 바뀌는 것 — 정확히 셋

hover/선택 배경 상자의 **위치·크기·모서리**(요청된 변화) · 첫 li 위 구분선과 배경 사이 2px 간격 · 세로
스크롤바가 있을 때 스크롤바가 콘텐츠 대신 번짐 8px 를 먼저 먹는다(개선). 텍스트의 x·y, 행 높이, 보이는
세션 수, 구분선 위치는 불변 — §11.6-1 이 헤드리스로 전후 비교한다.

---

## 7. 파일 구조와 모듈 경계 — 무변경

```
hub_template.html
├── <style>              … 과제 A 삭제 1규칙 · 과제 C 개정 3규칙 · 과제 B 신설 약 20규칙(전부 .card.card-expanded 스코프)
├── 머리 주석            … 확장 문장에 후계 PRP 포인터 1구
├── 테마·툴팁·잠금 IIFE  … 무변경
├── 렌더 IIFE            … expandToggleLabel 문자열 2개. 렌더 함수·리스너·상수 무변경
└── 패널 IIFE            … 무변경
```

두 IIFE 가 서로를 모른다는 원칙(OC8·SP1·G8), 확장 상태가 렌더 IIFE 에만 산다는 원칙(U1~U4) 전부 그대로다.
트리는 **표현 계층(CSS) 안의 변화**이고 상태·데이터·이벤트 경계를 하나도 건드리지 않는다 — 이것이 이 설계의
가장 단순한 구조이며, 패턴 도입은 없다.

## 8. 데이터 모델 — 무변경 (판정)

| 트리에 필요한 값 | 이미 있는가 | 출처 |
|-----------------|------------|------|
| 세션별 진행률(진행 노드) | 있다 | `SessionView.tier1` → `renderSessionProgress` (`.session-tier1`) |
| 위임 기록(위임 노드) | 있다 | `SessionView.workflow.agents` → `renderWorkflowRun` (`.workflow-runs`) |
| 라이브 에이전트(라벨 줄) | 있다 | `SessionView.agent_runs` → `renderAgentRuns` |
| 노드 순서·깊이 | **CSS 가 결정** | `order` · `margin-left` — 데이터가 아니다 |
| 확장 여부 | 있다(클라이언트 상태) | `localStorage['dzh-expanded-projects']` (U1~U4) |

스냅샷 JSON·`hub/bin/*.py`·`tests/hub` 무변경.

## 9. 인터페이스

- JS: `expandToggleLabel(isExpanded: boolean, sessionCount: number): string` — 시그니처 불변, 반환 문자열만 §5.5.
  신설 함수 0, 삭제 함수 0.
- CSS 계약(가드가 문자열로 잠그는 선택자): `.card.card-expanded .sessions li::before{` · `.card.card-expanded .session-row{display:flex;flex-direction:column}` · `.card.card-expanded .session-row>.session-tier1{order:1}` · `.card.card-expanded .session-row>.workflow-runs{order:2}` · `.sessions{…margin:10px -8px 0;padding:0 8px…}` · `.sessions li{padding:2px 0` · `.session-row{…padding:5px 8px;border-radius:8px…}`.

---

## 10. 설계 결정

### 10.1 신규 결정 (V 계열)

| ID | 결정 | 근거 |
|----|------|------|
| **V1** | `.sessions .badge.state-working` halo 규칙과 주석을 삭제. 남는 채널은 배지 3개(+칩 1 조건부) | §4 — 사용자 명시 반려. U8 번복 |
| **V2** | 펼친 카드의 세션 목록은 **세로 들여쓰기 트리**다: 레일 + `├─ └─` 갈고리 + 단당 16px 들여쓰기. 가로 배치 없음 | §5.1 — 리스트/트리를 가르는 네 요소를 넣되 문제 2·3·4 의 원인(가로)은 되살리지 않는다 |
| **V3** | 노드/본문 판정 기준: 세션이 산출·위임한 개체 = 자식 노드, 세션 자신의 속성 = 본문 | §5.2 |
| **V4** | 자식은 2종 — 「진행」(항상, `.session-tier1`) · 「위임」(있을 때, `.workflow-runs`). 위임의 표현은 안 A(노드 1개+칩 행, 권고) / 안 B(에이전트마다 잎) 중 사용자 선택 | §5.2 |
| **V5** | 깊이 상한 루트 아래 2단, 단당 16px, 갈고리 y 17px | §5.3 |
| **V6** | 연결선 색 `var(--muted)` + `opacity:.5` | `--line` 은 열린 카드 면에서 사라진다(§5.3). 새 토큰 0 |
| **V7** | 자식을 본문 뒤로 보내는 것은 `display:flex;flex-direction:column` + `order`(펼침 스코프) — DOM 순서 불변 | §5.4 — DOM 을 바꾸면 접힘 화면이 바뀐다 → **개정(LM2)** — 접힘 화면 소멸로 근거가 없어져 DOM 순서를 시각 순서로 맞춘다(hub-session-row-layout-and-modal-size.md) |
| **V8** | hover/선택 배경 = 서브트리 전체 상자 | §5.7 — 자식을 버튼 밖으로 빼면 클릭 계약이 깨진다 |
| **V9** | 과제 C = 패딩 재배분(li 2 + 버튼 5, Δ0) + 좌우 8px 번짐(ul padding/margin 짝) + 모서리 8px | §6.2·§6.3 |
| **V10** | 셰브론 문구 `'세션 N개 트리로 보기'` / `'트리 접기'` | 셰브론이 여는 것이 트리다. JS 유일 변경 |
| **V11** | T25-186 을 지우고 그 자리에 **역가드 T25-190**(halo 잔재 0) + **T25-195**(`@keyframes` == 2) 를 세운다 | 「새 애니메이션 없음」 승인은 유효하고 「정적 halo」만 반려됐다 — 두 사실을 각각 기계로 표현한다 |
| **V12** | 첫 세션의 레일을 위로 10px 연장해 루트 본문에 닿게 한다 | 레일이 허공에서 시작하면 「루트」(③)가 사라진다 |

### 10.2 뒤집는·개정하는 기존 결정 (공개 번복)

| 결정 | 원문 요지 | 처분 | 전제가 어떻게 바뀌었나 |
|------|-----------|------|---------------------|
| **U8** | 진행중 세션 신호는 행 배지의 정적 halo | **전면 번복**(V1) | 사용자가 산출물을 보고 「`span.badge` 에는 glow 불필요」로 판정. U8 이 옮겨온 대시보드 칩 기하는 대시보드에만 맞았다 |
| **U2** | 가로 조직도 은유를 버리고 세션은 카드 안의 세로 행. 연결선 8규칙 전부 삭제 | **부분 번복**(V2) — 조직도(가로) 폐기는 유지, **연결선은 세로 형태로 복귀** | U2 는 「연결선」을 가로 은유의 부속물로 봤다. 사용자는 연결선·들여쓰기를 「트리」의 정본으로 봤다 — 둘은 분리 가능했다 |
| **U3** | 3단→2단, 서브에이전트 타입은 칩으로 강등 | **안 A: 유지** / **안 B: 펼침 한정 번복** | 안 B 는 옛 3단(프로젝트→세션→서브에이전트)을 세로로 복원한다. 접힘 화면에서는 어느 안이든 칩 그대로 |
| **U4** | 확장 = 340px 해제 + 세션 전부 + 세션별 진행률 | **개정(확장)** — 확장 = 위 + **트리 표현** | 「내부 스크롤 없이 전부」는 그대로 필요하고 그 위에 구조를 그린다 |
| **U9** | 세션별 진행률은 항상 렌더하고 CSS 가 감춘다 | **개정(확장)** — CSS 가 감추기만 아니라 **순서·들여쓰기·연결선**도 정한다(V7) | 같은 원칙(JS 는 분기하지 않는다)의 적용 범위가 넓어진다 |
| 직전 §4.3 「접힘에서 새로 생기는 차이는 hover 와 halo 둘뿐」 | — | **개정** — halo 삭제(V1), hover/선택 배경 기하 변경(V9) | 사용자 요청 |
| **ST19**(직전 PRP 가 부분 번복) | 3단 트리 | 안 B 채택 시 **3단 구조 재채택**(세로) | 「깊이감」이 다시 평가 기준에 들어온다 — 사용자가 트리를 원했다 |

### 10.3 유지하는 결정 (그리고 그것이 이 설계를 제약하는 방식)

U1(한 화면) · U5(셰브론, 패널 IIFE 조기 반환 — `closest('.card-expand-toggle')` 무변경) · U6(세션 ≥1 이면 셰브론)
· U7(재렌더 없는 토글 — 트리 CSS 는 클래스 하나로 켜지므로 그대로 성립) · U10(`CARD_SELECTOR`) · U11(톤다운
자식 결합자 `>` — 진행 노드가 `renderTier1(session.tier1,false)` 를 그리므로 **더 중요해졌다**) · U12·U13·U14
· W1·W2(3열 산술·340px) · D6·D8~D11(모션 언어·bloom — `.card.card-working` 무변경) · PV9(외부 리소스 0)
· IL1~IL7 · N2 · OC5·OC11·ST26 · ST23~ST25(패널 신원·제목).

---

## 11. 테스트 계획

이 저장소는 템플릿 CSS/JS 를 **문자열·산술 가드**(T25)와 **뮤테이션 원장**(K6)으로 잠근다. JS 러너는 없고
도입하지 않는다.

### 11.1 (a) 기존 가드 — 전수 판정

| 가드 | 지금 무는 것 | 처분 | 원장 |
|------|-------------|------|------|
| **T25-186** | `.sessions .badge.state-working{…}` 규칙 **존재** + `animation` 없음 | **삭제**(존재 단언이 뒤집힌다) → T25-190 으로 대체 | 변조행 삭제(−1) |
| **T25-188** | README 에 `확장`·`세션 행` 있음, `트리 모드`·`보기 토글` 없음 | **개정** — 첫 서브체크에 `연결선` 토큰 추가. 메시지 「확장·세션 행·연결선 서술이 없음」 | 기존 변조행(「트리 모드」 삽입) 그대로 문다 — 무변경 |
| T25-185 | `.card.card-expanded{height:auto}` · `.card:not(.card-expanded) .session-tier1{display:none}` | 무변경(둘 다 유지) | — |
| T25-127 | `renderSession(project, session){` 앵커 · `.session-line` 구성 · `.session-meta{`·`.session-id{` CSS 존재 | 무변경(DOM·해당 CSS 불변) | — |
| T25-147 보조 | `.sessions{…}` 에 `overflow:hidden` 없음 | 무변경(`overflow-y:auto` 유지) | — |
| T25-178·T25-159·T25-160 | 잔재 0 | 무변경 — 새 식별자 0개 | — |
| T25-179~T25-184·T25-187 | 리스너 위치·중복·드래그 스코프·패널 가드·OC-A·`>`·상수 단일화 | 무변경 — JS 불변 | — |
| T25-161·T25-107·T25-131 | 리터럴 「정확히 2회」 | 무변경 — 새 CSS/주석에 `data-session-id`·`dzh:rendered`·`dzh:refresh-requested` 를 적지 않는다(GOTCHA) | — |
| T25-65·T25-171·T25-176·T25-189 | `card-working` 진폭·주기·bloom 부등식 | 무변경 | — |
| `tests/hub` 655건 · `tests/commands` | — | 무변경 | — |

### 11.2 (b) 신규 가드 — 6종 (ID 는 T25-190 부터, 각각 변조행 1건)

| ID | 성격 | 무는 것 | 없으면 조용히 통과하는 것 | 변조(sed 요지) | 판별 토큰 |
|----|------|---------|--------------------------|----------------|----------|
| **T25-190** | 역(V1·V11) | 선택자에 `.badge.state-working` 이 든 규칙 본문에 `box-shadow`·`animation` 이 **0건**: `grep -oE '[^{}]*\.badge\.state-working\{[^}]*\}' \| grep -E 'box-shadow\|animation'` 빈 결과 | 사용자가 되돌리라 한 halo(또는 맥동)가 다른 선택자 이름으로 되살아나는 것 | `.badge.state-done{…}` 줄 뒤에 `.sessions .badge.state-working{box-shadow:0 0 10px -1px var(--accent)}` 삽입 | `state-working 규칙에 halo` |
| **T25-191** | 역+정(V2, 제약 5) | 연결선 규칙이 `.card.card-expanded` 스코프 밖에 없다: `grep -cE '^[[:space:]]*\.(sessions li\|session-tier1\|workflow-runs)[^{]*::(before\|after)'` == 0 **AND** `grep -qF '.card.card-expanded .sessions li::before{top:0;height:17px'` | 접힘 카드에 연결선·들여쓰기가 새어 픽셀 동일 계약이 깨지는 것 | li::before 규칙 줄에서 `.card.card-expanded ` 접두를 지운다 | `접힘 카드에 연결선` |
| **T25-192** | 정(V9) | `.sessions li{padding:(N)px 0` 과 `.session-row{…padding:(M)px (H)px` 를 추출해 **2N+2M == 14** (T25-177 의 python 산술 관용구) | 누가 패딩을 올려 접힘 카드에 보이는 세션이 3→2 로 조용히 주는 것 | `padding:5px 8px;border-radius:8px` → `padding:7px 8px;border-radius:8px` | `세션 행 세로 여백 합` |
| **T25-193** | 정(V9, ★) | `.sessions{…margin:10px -(B1)px 0;padding:0 (B2)px…}` · `.session-row{…width:calc(100% + (W)px);margin:0 -(B3)px…}` 에서 **B1==B2==B3 && W==2·B1** | 번짐 짝이 어긋나 접힘 카드의 `.sessions` 에 **가로 스크롤바**가 생기는 것(직전 회차가 0개로 만든 것의 재발) | `margin:10px -8px 0;padding:0 8px;` → `margin:10px 0 0;padding:0;` | `가로 번짐 불일치` |
| **T25-194** | 정(V7) | `.card.card-expanded .session-row{display:flex;flex-direction:column}` **AND** `…>.session-tier1{order:1}` **AND** `…>.workflow-runs{order:2}` 세 문자열 존재 | 자식 노드가 발췌(본문) 앞에 그려져 트리 의미가 깨지는 것 | `.card.card-expanded .session-row>.session-tier1{order:1}` 줄을 비운다 | `자식 노드 순서` |
| **T25-195** | 역(제약 7·V11) | `grep -c '@keyframes' hub_template.html` **== 2** | 「정적, 새 애니메이션 없음」 승인(2026-09-10)을 어기는 `@keyframes` 가 조용히 추가되는 것 | `@keyframes card-working-glow{` 앞에 `@keyframes x{0%{opacity:1}}` 한 줄 삽입 | `@keyframes 개수` |

원장 행은 8열 규약을 따른다(2열 `hub/bin/hub_template.html`, 4열 `T25`, 7열 빈칸, 8열
`test_hub_docs_and_constants`). 판별 토큰은 실패 보고 줄에서 1건만 나타나야 한다(T37-13) — 위 토큰은
현재 소스에 없는 문구다(구현 시 재확인). sed 는 `s/…/…/` 단일 형태·`/` 구분자·쓰기 플래그 없음
(`mutation_sed_is_write_safe`), `\n` 삽입은 T25-160 행의 선례를 따른다.

### 11.3 (c) 원장과 래칫 — 산술 (★놓치면 커밋이 막힌다)

`collect_guard_ids` 는 `note_failure`/`record_failure` 로 시작하는 줄에서 `"T그룹-번호` 접두를 `sort -u`
로 센다 — 한 가드를 서브체크로 쪼개도 접두 종수만큼만 는다. 아래 신규 6종은 접두가 전부 다르다.

| 상수 | 현재(=실측) | 이동 | 새 값 | 산술 |
|------|-------------|------|-------|------|
| `SOURCE_GUARD_ID_FLOOR` | 474 | −1(T25-186) +6(T25-190~195) | **479** | 올리는 방향 — 역사 주석에 1문단 |
| `LEDGER_MUTATION_ROW_FLOOR` | 81 | −1(T25-186 행) +6 | **86** | 올리는 방향 — 역사 주석에 1문단 |
| `LEDGER_EXEMPT_ROW_RATCHET` | 404(실측 400) | 0 (승급·면제 등록 없음) | **404** | 무변경 |
| `NOTE_FAILURE_ID_LESS_RATCHET` | 110 | 0 (신규 호출은 전부 ID 있음) | 110 | 무변경 |
| `LINE_CITATION_RATCHET_SUITE` | 5 | 0 | 5 | 새 `tests/run.sh` 주석에 `파일:줄` 인용을 쓰지 않는다(앵커 인용, D17) |

**함께 움직여야 하는 인용(`verify_ledger_header_citations` 가 실행마다 상수와 대조한다):**

1. `tests/mutations.tsv` 헤더 「하한은 `LEDGER_MUTATION_ROW_FLOOR(81 —` / `4→8→…→80→81)`」 → `(86 —` · 사슬 끝에 `→86`.
2. 헤더 「`SOURCE_GUARD_ID_FLOOR(474 — 394→…→470→474)`」 → `(479 — …→470→474→479)`.
3. **원장 행 `T99-6`**: sed 리터럴 `s/LEDGER_MUTATION_ROW_FLOOR(81/…(99/` → `(86` 으로. 이 행은 자기참조라 옛
   값으로 두면 sed 가 헤더에 닿지 못해 **T37-15 가 「가드 무력화」로 오진**한다(그 행의 서술 자체가 5회
   반복된 실측이다). 그 서술 끝에 이번 이동 1문장을 덧붙인다(관례).
4. `tests/run.sh` 두 상수의 역사 주석에 「81 → 86 …」「474 → 479 …」 문단(§12-5 에 문안).
5. T25 그룹 `test_desc` `(T25-1~T25-189)` → `(T25-1~T25-195)` (그룹 머리 주석의 `~T25-188` 은 이미 낡아 있다 — 같이 고치되 필수는 아니다).

### 11.4 순수 로직 검증

| 대상 | 케이스 | 기대 |
|------|--------|------|
| `expandToggleLabel(false, 4)` / `(true, 4)` / `(false, 1)` | 세 문구 | `'세션 4개 트리로 보기'` / `'트리 접기'` / `'세션 1개 트리로 보기'` — 서로 다르고 개수를 담는다 |
| T25-192 산술 | li 2 + 버튼 5 | 14 ✓ / 변조(7) → 18 ✗ |
| T25-193 산술 | 8·8·8·16 | ✓ / 변조(0·0·8·16) ✗ |
| 갈고리 y(1단) | 2 + 5 + 첫 줄 중앙 | 17 ±1 (헤드리스 실측, §11.6-4) |

### 11.5 검증 명령 (프로젝트 정본)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

### 11.6 사람이 눈으로·헤드리스로 확인할 것 (자동 가드가 못 잡는 몫)

메모리 「허브·대시보드 CSS 시각 확인」 절차 — 실데이터 생성물(`~/.claude/hub/hub.html` 사본)의 `<style>`
블록만 갈아끼워 로컬 HTTP 서버로 서빙한다. 측정은 스크린샷보다 `getComputedStyle`·`getBoundingClientRect`.

| # | 확인 | 통과 기준 |
|---|------|----------|
| 1 | **접힘 무회귀** | 변경 전후로 `.sessions li` 각 `clientHeight` 동일, `.session-line` 첫 배지의 `left` 동일, 카드에 보이는 세션 수 동일 |
| 2 | **가로 스크롤 0** | 접힘: `.sessions.scrollWidth === .sessions.clientWidth`. 펼침: `#dzh-app` 의 모든 후손에서 `scrollWidth > clientWidth` 인 요소 0개 |
| 3 | 선택/hover 기하 | `.session-row.card-open` 배경이 배지 위 5px·아래 5px·좌우 8px, 모서리 8px, 첫 구분선과 2px 간격. hover 상자와 같은 모양 |
| 4 | 갈고리 정렬 | `li::before` 의 바닥선 y 와 첫 배지 중앙 y 의 차 ≤ 1px(1단·2단 모두) — 헤드리스 Chrome 152·실데이터 6프로젝트 11세션 실측 통과(1단 ±0.5px, 배지 테두리 유무로 부호가 갈린다: state-stale·state-done −0.5px / state-working·state-idle +0.5px. 2단 진행 노드 0px. 2단 위임 노드 −0.1484px. 최대 절대편차 0.5px). 마지막 세션 아래에 레일 꼬리가 없다. 위임 노드가 없는 세션에서 진행 노드 아래에 레일 꼬리가 없다 |
| 5 | 순서 | 펼침에서 `.excerpt` 의 `top` < `.session-tier1` 의 `top` < `.workflow-runs` 의 `top`. `.excerpt` 높이가 글자 줄 수와 일치(늘어나 있으면 `flex-basis` 확인) |
| 6 | 연결선 대비 | 라이트·다크 × 카드 열림(`--accent-soft` 면)·기본 네 조합에서 레일이 보인다 |
| 7 | 최소 폭 | 뷰포트를 줄여 320px 트랙에서 펼침 — 2단 자식이 잘리지 않고 메타 줄이 줄바꿈된다 |
| 8 | 상호작용 계약 | 자식 노드(진행률·워크플로우 칩) 클릭 → **그 세션** 대시보드가 열린다(프로젝트 요약이 아니다). 셰브론 클릭 → 패널 불변. 트리 위로 카드 드래그 → 콘솔 `NotFoundError` 없음. `file://` 에서 셰브론 동작 |
| 9 | 지속성 | 펼친 채 30초 틱·폴링 뒤에도 트리 유지(localStorage) |
| 10 | 모션 | 새로 움직이는 것 0 — `prefers-reduced-motion` 에서 카드 bloom 만 정적으로 남는다 |

---

## 12. 구현 순서 (각 단계 끝에 `bash tests/run.sh` 녹색 — 빨간 상태를 남기지 않는다)

| # | 단계 | 파일 | 검증 |
|---|------|------|------|
| 1 | **과제 A**: halo 규칙+주석 삭제 · run.sh 의 T25-186 블록을 T25-190 으로 교체 · 원장 T25-186 행 삭제·T25-190 행 추가 · 직전 PRP 번복 주석 3곳 | template · run.sh · tsv · 직전 PRP | 스위트 녹색(래칫 이동 0 — 상수·헤더 무변경). `grep -c 'box-shadow' ` 로 배지 규칙 무halo 확인 |
| 2 | **과제 C**: `.sessions`·`.sessions li`·`.session-row` 3규칙 + 주석 · T25-192·T25-193 + 변조행 2건 | template · run.sh · tsv | 스위트 녹색(실측 476/83 ≥ 하한 474/81 — 상수는 아직 안 올린다). §11.6-1·2·3 헤드리스 전후 비교 |
| 3 | **과제 B**: 트리 CSS 블록(사용자가 고른 안) + 주석 · `expandToggleLabel` 문자열 2개 · 머리 주석 포인터 · T25-191·T25-194·T25-195 + 변조행 3건 | template · run.sh · tsv | 스위트 녹색. §11.6-2·4·5·6·7·8·9·10 |
| 4 | **문서**: README 셰브론 불릿 교체(§12-4 문안) · T25-188 개정(`연결선`) | README · run.sh | T25-188 통과. 사람이 읽어 거짓 없음 |
| 5 | **래칫**: `SOURCE_GUARD_ID_FLOOR=479` · `LEDGER_MUTATION_ROW_FLOOR=86` + 역사 주석 2문단 · 원장 헤더 인용 2줄 · **T99-6 sed 리터럴 `(81`→`(86` + 서술 1문장** · T25 `test_desc` | run.sh · tsv | 스위트 녹색 — `verify_ledger_header_citations`·T37-11·T37-14·T37-15 통과. `collect_guard_ids` 479 · 변조행 86 재실측 |
| 6 | **시각 확인**: §11.6 전 항목 | — | 표 기준 전부 통과. 스크린샷을 검수 보고에 첨부 |

**단계 4 README 문안**(「셰브론을 누르면 카드가 펼쳐진다」 불릿 교체 — `확장`·`세션 행` 토큰은 이웃 불릿에 남고, 「트리 모드」는 쓰지 않는다):

> - **셰브론을 누르면 카드가 트리로 펼쳐진다.** 세션이 1개 이상인 카드에는 헤더 오른쪽 끝에 확장 셰브론이 있다 — 누르면 카드의 고정 높이(340px)가 풀리고 세션 목록이 세로 들여쓰기 트리로 바뀐다: 프로젝트가 루트, 세션이 연결선(`├─ └─`)으로 매달린 노드, 각 세션 아래에 그 세션의 진행률(대시보드가 없으면 「대시보드 없음」)과 위임한 서브에이전트(워크플로우)가 자식으로 달린다. 내부 스크롤 없이 한눈에 보이고, 자식 어디를 눌러도 그 세션의 대시보드가 열린다. 펼침·접힘은 프로젝트별로 `localStorage` 에 저장돼 새로고침해도 유지되고, 접힌 카드의 화면·동작은 펼침 기능과 무관하게 그대로다.

**단계 5 역사 주석 문안**(`tests/run.sh`):

> `# 81 → 86 으로 올린 이유(hub-tree-view-and-signal-fixes PRP — 카드/트리 통합 설계의 사용자 반려 회차): T25-186(세션 배지 halo 에 animation 금지)의 변조행 1건을 지웠다 — 사용자가 halo 자체를 되돌리라고 해 무는 대상이 사라졌다. 그 자리를 역가드 T25-190(halo 잔재 0)이 잇고, 신규 가드 5종(T25-191~T25-195 — 트리 스코프·행 여백 합·가로 번짐 짝·자식 순서·@keyframes 개수)의 변조행을 붙였다. 순증가 5(−1+6).`
>
> `# 474 → 479 로 올린 이유(hub-tree-view-and-signal-fixes PRP): T25-186 의 ID 접두가 사라지고 T25-190~T25-195(6종)가 추가됐다. 순증가 5.`

---

## 13. 위험과 완화

| # | 위험 | 가능성 | 영향 | 완화 |
|---|------|--------|------|------|
| 1 | 갈고리 y(17px)가 실제 줄상자 중앙과 1px 이상 어긋난다(baseline 정렬·폰트 대체) | 중 | 낮음(미관) | §11.6-4 실측 후 값 조정. 유도 산술을 주석에 남겨 다음 사람이 재계산할 수 있게 한다. T25-192 가 7px 합을 고정해 입력이 조용히 바뀌지 않게 한다 |
| 2 | `order` 로 시각 순서와 DOM 순서가 갈린다(보조기술 읽기 순서: 발췌가 진행률 뒤) | 확정 | 낮음 | 세션 행은 `<button>` 하나 — 접근 가능 이름이 연결 문자열이라 순서 차가 의미를 바꾸지 않는다. 대안(DOM 재배열)은 접힘 화면을 바꿔 기각. 기록만 한다 |
| 3 | 선택 상자가 서브트리 전체라 세션이 길면 큰 면이 칠해진다 | 중 | 낮음(취향) | 목업 (c)에서 사용자가 본다. 대안(자식을 버튼 밖으로)은 클릭 계약·T25-181 을 깬다 — 기각 근거 §5.6-6 |
| 4 | 연결선이 열린 카드(`--accent-soft` 면)에서 안 보인다 | `--line` 이면 확정 | 중 | V6(`--muted` 50%). 목업 다크 열 + §11.6-6 |
| 5 | 안 B 에서 워크플로우 12개 세션이 카드를 매우 길게 만든다 | 낮음 | 낮음 | 상한 12 × 22px = 264px/세션. 확장은 카드별 옵트인이고 접기는 클릭 1회. 안 A 가 기본 권고 |
| 6 | 번짐 짝(8px ×4)이 어긋나 접힘 카드에 가로 스크롤바 | 코드를 안 고치면 0, 후속 수정에서 중 | 심각(직전 회차의 핵심 성과 회귀) | T25-193 + §11.6-2 |
| 7 | 래칫 상수만 올리고 헤더 인용·T99-6 리터럴을 안 옮겨 `verify_ledger_header_citations`/T37-15 가 막는다 | 중(5회 반복된 함정) | 낮음(막히지만 조용하지 않다) | §11.3 의 5항목을 단계 5 에 묶는다 |
| 8 | 세로 flex 컨테이너에서 `.excerpt{flex-basis:100%}` 가 브라우저에 따라 높이를 늘린다 | 낮음 | 중(빈 공간) | `flex-basis:auto` 명시(§5.4) + §11.6-5 |
| 9 | 최소 폭(278px)에서 메타 줄(최장 ≈274px)이 들여쓰기 16px 를 잃고 넘친다 | 중(좁은 뷰포트·다른 날 날짜 형식·긴 모델명) | 낮음 | `.card.card-expanded .session-meta{flex-wrap:wrap}` — 펼침 한정이라 접힘 행 높이(MD §3.10 의 함정)에 영향 없음. 목업 최소 폭 카드 |
| 10 | `li::before/::after` 가 이미 다른 용도로 쓰일 가능성 | 없음(확인) | — | `.sessions li` 의 pseudo 규칙은 현재 0개 |

---

## 14. 열린 질문 — **3건 모두 해소(사용자 승인 2026-09-10)**

사용자가 프리뷰 이미지 3장(헤드리스 Chrome 152 실렌더)을 보고 **세 질문 모두 권고안을 선택**했다.
따라서 구현은 아래 표의 「권고」 열을 그대로 따른다 — 대안 열은 기각 근거의 기록으로만 남긴다.

| # | 결정 | 상태 |
|---|------|------|
| 1 | 「위임」 노드 = **안 A**(노드 1개 + 칩 행) | 승인 — 안 B(에이전트별 잎)는 기각. U3 부분 번복은 **발동하지 않는다** |
| 2 | 연결선 색 = **`var(--muted)` + `opacity:.5`** | 승인 |
| 3 | 셰브론 문구를 **「세션 N개 트리로 보기 / 트리 접기」**로 변경 | 승인 — JS 문자열 2개 변경(결정 V10) |

원 질문표(근거 보존):


| # | 질문 | 권고 | 대안의 비용 |
|---|------|------|------------|
| **1** | **「위임」 노드 표현 — 안 A(노드 1개 + 칩 행) vs 안 B(에이전트마다 잎)** — 목업 (c)/(c′) 나란히 | **안 A** — 높이를 아끼고(확장의 원 목적 「한눈에」), 자식 2종이 고정돼 모양이 예측 가능하다 | 안 B 는 더 문자 그대로의 트리(옛 3단 복원). 세션당 최대 +264px. CSS 5줄 교체로 전환 가능 — 후에 바꿔도 DOM·가드는 그대로 |
| **2** | 연결선 색 `--muted` 50%(권고) vs `--line` | `--muted` 50% | `--line` 은 라이트 테마 열린 카드에서 사라진다(§5.3) |
| **3** | 셰브론 문구를 「트리로 보기/트리 접기」로 바꾼다(V10) | 바꾼다 | 유지하면 문구(「모두 보기」)와 화면(트리)이 어긋난다. JS 변경 0 이 된다는 것 외 이점 없음 |

## NOT Building (범위 밖 — 명시적으로 안 만든다)

- `commands/dashboard_template.html` 수정 · `.claude/dashboards/*.html` 생성물 재발행 메커니즘(§2.1 — 사용자가 요청하지 않았다)
- 3단째 노드(실행 단위 `agent_id` 타임라인, 에이전트별 프롬프트/결과 본문) — 툴팁이 이미 답한다
- 자식 노드의 개별 접기/펼치기, 세션 노드별 확장 상태
- 트리용 새 DOM 래퍼·새 클래스·새 렌더 함수 — CSS 만으로 충분함이 확인됐다
- 세션 행을 열면 카드를 자동으로 펼치는 규칙(직전 위험 10 그대로 유지)
- 새 `@keyframes` · 새 색 토큰 · 새 외부 의존성 · 스냅샷 JSON 변경
