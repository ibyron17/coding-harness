# 허브 — 폴링·틱 부분 갱신 + 카드 상세보기 모달 (PRP)

> 상태: **승인됨(2026-09-23)** — §14 승인 항목 1~6 전부 권고안대로 확정, §13 쟁점 1~4 수용(1024px
> 패널 열림 시 세션 카드 1장 포함). 구현은 **M1(PU)부터**. 승인 시점에 브랜치를 `main` `19bca3a` 로
> 빨리 감았다 — 추가된 두 커밋(`42f0dc1`·`19bca3a`)은 `hub/` 를 건드리지 않아 아래 `hub_template.html:N`
> 인용은 그대로 유효하고, `tests/run.sh` 행 번호·`tests/mutations.tsv` 머리 계수는 재확인 대상이다.
> **M1 착지 때 재정렬(2026-09-24)**: `main` 이 `8f520de` 까지 5커밋 나아가며 **T25-228 을 먼저 썼다**(`9f23534`, harness-update 사전 비교 순서). 그래서 이 문서의 신규 가드 번호를 전부 **+1** 옮겼다 — M1 은 T25-229~232, M2 예정은 T25-233~240(main 의 T25-241~244 와 겹치지 않는다). 원장 머리 계수 기준도 main 의 승급 4건으로 291 → 287 이 되어 M1 뒤 286, M2 예상 282 다(M2 구현 때 실측으로 다시 센다).
>
> 대상: `hub/bin/hub_template.html` 한 파일의 UI 계층 + 그 계약을 잠그는 `tests/run.sh`(T25)·
> `tests/mutations.tsv` + 신규 `tests/hub/test_hub_template_dom.py` + `hub/README.md`.
> **스냅샷 계약(`hub_model`·`hub_project`·`hub_session`)과 허브 파이썬은 한 줄도 바꾸지 않는다.**
>
> 기준 커밋: `33d5cea`(브랜치 `worktree-hub-session-modal`). 이 문서의 `hub_template.html:N` 행
> 번호는 전부 그 커밋 기준이다. 결정 접두 **PU**(Partial Update, 1단계)·**SC**(Session Card
> modal, 2단계) — `grep -rhoE "결정 [A-Z]{1,3}[0-9]+" docs/prps/*.md` 로 미사용 확인.
>
> 설계 모델: opus(디스패치 기본값). 목업: §15.

---

## 0. 한눈에

| 항목 | 내용 |
|------|------|
| 요구 | ① 30초 틱·1분 폴링이 `#dzh-app` 을 통째로 갈아엎어 스크롤·포커스·glow·툴팁이 초기화되는 것을 **바뀐 것만 고치는 부분 갱신**으로 바꾼다. ② 카드(세션 줄 밖)를 누르면 그 프로젝트의 세션 전체를 **세션 카드 가로 한 줄**로 보여주는 **모달**을 띄우고, 세션 카드를 누르면 상세 패널이 함께 열린다 |
| 마일스톤 | **M1(1단계, PU)** 부분 갱신 — 화면 모양 변화 0, 단독 배포 가능 → **M2(2단계, SC)** 모달 — M1 의 맞대기 위에 얹는다 |
| 핵심 결정 | PU1 키 기반 자식 맞대기 **자체 구현**(≈70줄, 라이브러리 0) · PU2 키는 전용 속성 `data-render-key` 하나 · PU3 속성은 렌더 결과가 진실(예외 `aria-describedby` 하나) · PU5 툴팁 해제 옵저버를 `.wrap` 하위 전체로 · SC1 모달은 **`.head-row` 안** 정적 싱글턴(헤더 아래·패널 왼쪽을 CSS 만으로) · SC2 비모달 dialog + **목록만 inert** · SC4 카드 = 모달 / 세션 줄 = 패널(지름길 유지) / 모달 루트 = 패널(프로젝트 요약) · SC8 ESC 는 **패널 먼저**(`defaultPrevented` 규약) · SC9 가로 **앵커 보정**(브라우저는 세로만 보정 — 실측) · SC12 연결선 안 B |
| 설계 단계 실측 | 헤드리스 Chrome 153 로 현재 템플릿과 맞대기 시제품에 같은 폴링·틱을 흘렸다 — 현재는 8개 항목 모두 초기화·교체, 시제품은 8개 모두 유지 + 모달 가로 앵커 실측 1건(§2.2). 모달 목업 11장면(§15) |
| 변경 규모(추정) | `hub_template.html` M1 약 +95/−15 · M2 약 +240/−45 · `tests/run.sh` M1 +45 · M2 +120 · `tests/mutations.tsv` M1 +5행 · M2 +15행 · 신규 DOM 검사 모듈 약 350줄 · `hub/README.md` M1 +4 · M2 +35/−12 |
| 기존 테스트 개정 | T25-81·T25-105·T25-107·T25-108·T25-127·T25-163·T25-218·T25-223 (8건, §10.1) |
| 신규 가드 | T25-229~T25-240 (12건, T25-240 는 승인 4 조건부) + DOM 행동 검사 모듈 1개 |
| 승인 필요 | **6개** (§14) |

---

## 1. 요구사항 요약

허브는 30초마다(데이터 변화와 무관한 틱) 그리고 폴링이 새 문서를 받을 때마다 `#dzh-app` 의
자식을 `innerHTML` 로 통째로 교체한다(`hub_template.html:2031`). 그래서 사용자가 카드 안 세션
칸을 내려 보고 있으면 다음 틱에 맨 위로 돌아가고, 작업중 카드의 glow 가 매번 처음부터 다시
뛰고, 키보드 포커스와 떠 있던 툴팁이 사라진다 — 작업 중에는 1분에 약 3회다. **1단계**는 넣는
순간만 「새 결과 ↔ 현재 DOM」을 노드 단위로 맞대어 바뀐 텍스트·속성만 고치고 순서가 바뀐
형제는 노드째 옮기는 부분 갱신으로 이 초기화를 없앤다. **2단계**는 340px 고정 카드로는 세션이
2~3개만 넘어도 한눈에 볼 수 없는 문제를, 카드를 누르면 뜨는 **카드 상세보기 모달**(프로젝트가
위, 그 아래 메인 세션이 세션 카드로 가로 한 줄)로 푼다. 모달의 세션 카드를 누르면 상세 패널이
그 세션의 대시보드로 열리고, 넓은 화면에서는 모달과 패널이 동시에 보인다. 모달 내용도 1단계
맞대기로 갱신되므로 가로 스크롤 위치가 30초마다 되돌아가지 않는다 — 옛 조직도 트리를 폐기하게
만든 결함 4(갱신마다 보던 카드가 사라짐)가 이 설계의 출발 조건이다.

### 1.1 사용자가 확정한 결정 (재론하지 않는다)

| # | 확정 | 이 문서에서의 자리 |
|---|------|-------------------|
| 1 | 카드 안 **세션 줄** 클릭 = 지금처럼 상세 패널이 그 세션 대시보드로 바로 열린다(지름길) | SC4 |
| 2 | 카드의 **그 밖의 영역**(여백·프로젝트명·진행 줄 등) 클릭 = **모달**. 모달은 한 프로젝트의 세션 전체 | SC4 |
| 3 | 모달 안에서 프로젝트는 위(루트), 그 아래 **메인 세션을 가로 한 줄**. 넘치면 **가로 스크롤**(줄바꿈 아님) | SC5 |
| 4 | 모달 안 세션은 **카드 형태** | SC6 |
| 5 | 모달 세션 카드 클릭 = 상세 패널에 그 세션 대시보드. 패널과 모달이 **동시에** 보인다 | SC1·SC4·SC14 |
| 6 | 서브에이전트는 3단 노드가 아니라 지금처럼 세션 카드 안 칩(실행 줄) | SC6 |
| 7 | **1단계(부분 갱신) 먼저**, 2단계(모달)를 그 위에 — 한 문서, 마일스톤 둘, 각각 독립 배포 | §11 |

**해석 명시(확정 3).** 「가로 한 줄」은 메인 세션이 "가로 리스트"를 원한다고 해석한 것이고
사용자는 이의 없이 진행을 지시했다. 이 해석의 대가 — 1024px 에서 패널을 열면 세션 카드가 한
장만 보인다 — 는 §2.3 수용 표와 목업 (d) 로 사용자에게 다시 보여 확인받는다(§13 쟁점 1).
**「세션 전체」의 해석**: 카드와 같은 필터(`visibleSessionsOf` — 완료+발췌·칩 없음 숨김, 12시간
넘은 소식 없음 숨김)를 통과한 세션 **전부**다. 카드의 340px 칸에 잘려 안 보이던 것이 다
보인다는 뜻이지, 필터에 걸린 세션까지 되살린다는 뜻이 아니다(T25-160 계약 유지).

---

## 2. 실측 (출발점 + 설계 단계 실측)

### 2.1 메인 세션 실측 (2026-09-23, 설치본 허브, 1024×768 — 재조사하지 않고 출발점으로 쓴다)

- 카드 340px 고정, 세션 칸(`.sessions`, `overflow-y:auto`) clientHeight 154~228px. 세션 3개인
  coding-harness 는 1개만 온전히 보임(scrollHeight 481 / clientHeight 171), atlas 는 0개.
- 패널을 열면 `#dzh-app` 폭 992 → 442px. 프로젝트 4개(2줄)일 때 `#dzh-app` 높이 692px.
- 틱 재렌더: 세션 칸 scrollTop 150 → 0, `.card-working::after` 애니메이션 currentTime 3149ms → 0
  (재시작), 툴팁 닫힘(`hub_template.html:985`).
- 데이터 변경 빈도: 작업 중 10초 간격 7회 비교 중 6회 변경. 사용량만 바뀌어도 카드 전부 재생성 →
  작업 중 1분에 약 3회(틱 2 + 폴링 1) 전체 교체.
- 패널 안 대시보드(`commands/dashboard_template.html` 의 apply)는 이미 변경 시에만 구역 단위 부분
  치환 — **범위 밖**.

### 2.2 설계 단계 실측 — 현재 템플릿 대 맞대기 시제품 (헤드리스 Chrome 153)

방법: 워크트리 템플릿 사본 두 벌(현재 그대로 / §7 알고리즘을 얹은 시제품)에 같은 실데이터 스냅샷
A 를 넣고, 사전 스크립트가 `fetch`·`setInterval`·`Date.now` 를 가로채 폴링이 스냅샷 B(coding-harness
의 작업중·대기 세션 상태를 맞바꿔 **정렬이 뒤집히는** 다음 수집)를 받게 한 뒤 `#dzh-refresh` 를
눌렀다. 30초 틱은 가로챈 콜백을 "61초 뒤" 시계로 직접 불렀다. **제품 코드는 바꾸지 않았다.**
시제품은 5회 연속 같은 결과(결정적).

| 무엇을 봤나 | 현재 (innerHTML 통째 교체) | 시제품 (키 기반 맞대기) |
|-------------|---------------------------|------------------------|
| 폴링(정렬 뒤집힘) 뒤 카드 노드 | 새 노드 | **같은 노드** |
| 세션 칸 스크롤 | scrollTop 120 → **0** | 보던 줄의 화면 위치 −120 → **−120** (브라우저 스크롤 앵커링이 scrollTop 을 120 → 235 로 스스로 보정 — §7 PU2 의 보너스) |
| 세션 줄 `<li>` | 새 노드 | 같은 노드가 **자기 세션을 들고** 자리만 옮김 |
| 작업중 glow(`::after` CSSAnimation) | 새 객체(재시작) | **같은 객체**(끊김 없음) |
| 키보드 포커스(`.project-name`) | 잃음 | 유지 |
| 30초 틱(글자만 바뀜) | 카드 재생성 · scrollTop 0 | 같은 노드 · 글자만 `30분 전`→`31분 전` · scrollTop 유지 |
| 드래그 취소(라이브 이동 되돌림) | 순서 복원 · 새 노드 | 순서 복원 · **같은 노드**(키 이동) |
| 패널 선택 표시 `.card-open` | 새 노드에 다시 붙음 | **같은 노드에 남음**(동기 구간에서 지웠다 되붙임, PU3) |
| 모달 가로 칸에 앞쪽 카드가 끼어들 때(M2 시제품) | — | 보정 없음: 보던 카드 x 415 → **707**(한 칸 292px 밀림) · 가로 앵커(SC9) 적용: 430 → **430** |

**측정 중 얻은 함정 4건**(DOM 검사 설계에 그대로 반영 — §10.3):
1. `--user-data-dir`(임시 프로필)를 주면 헤드리스 Chrome 이 **무한 대기**한다(`--use-mock-keychain`
   으로도 동일, 40초 타임아웃 재현). 플래그 없이 쓰면 2~9초에 끝나고, 가짜 HOME·가짜 TMPDIR 에
   남기는 파일 **0개**(실측) — 스위트의 샌드박스 HOME·누수 검사와 충돌하지 않는다. 가짜 HOME
   에서는 `--use-mock-keychain` 이 없으면 macOS 키체인 접근에서 멈춘다(2026-09-23 메인 세션 실측).
2. 창 `focus` 이벤트가 로드 직후 **진짜 폴링**을 쏘고(`hub_template.html:2220`), 그 요청이 `busy`
   를 쥔 동안 시험의 새로고침 클릭이 버려져 스냅샷 A 가 한 번 더 그려졌다 → fetch 가로채기는
   허브 스크립트보다 **먼저** 설치해야 한다.
3. `new Response(...)` 의 본문 스트림 읽기가 가상 시간에서 태스크 경계를 넘어 고정 대기(1.5초)가
   1/5 헛돌았다 → `text()` 가 즉시 해소되는 가짜 응답 객체로 바꾸자 5/5 결정적.
4. 가상 시간 예산을 90초로 주면 무한 CSS 애니메이션과 겹쳐 끝나지 않았다 → 틱은 기다리지 않고
   가로챈 콜백을 직접 부른다(5초 예산으로 충분).

### 2.3 모달 가로 수용 (세션 카드 280px + 간격 12px + 모달 좌우 패딩 20px, 모달 폭 = 목록 폭)

| 뷰포트 | 1024 | 1280 | 1440 | 1728 | 1920 |
|--------|------|------|------|------|------|
| 패널 닫힘 — 한 줄에 온전히 | 3 | 4 | 4 | 4 | 4 |
| 패널 열림(밀어내기) — 한 줄에 온전히 | **1** | 2 | 2 | 3 | 4 |

동시 메인 세션 실측 최대 atlas 5·coding-harness 4(`docs/prps/hub-session-tree-and-per-session-dashboards.md`
§2 F4). 1440 이상에서 `.wrap` 은 1440px 로 멈추므로 1728·1920 의 패널 닫힘 값이 같다. 모든
칸에서 다음 카드가 잘려 보이는 **엿보기**가 생긴다(1440 패널 닫힘 212px, 1024 패널 열림 110px)
— 이것 자체가 넘침 단서다(SC11).

> → **개정(2026-09-30)** — 세션 카드 폭이 280→320px 로 넓어졌다(hub-session-modal-cleanup.md 결정 MX8).
> 이 표의 수용 수는 그 문서 §2.4 의 표가 새 정본이다 — 1440 패널 닫힘은 4장을 그대로 두고, 1280·1024 패널
> 닫힘은 한 장씩 준다.

---

## 3. 영향 범위

| 파일 | M | 조치 | 이유 |
|------|---|------|------|
| `hub/bin/hub_template.html` | M1 | UPDATE | 렌더 IIFE 에 맞대기 함수군(PU1) · `render()` 전환(PU6) · 키 3곳(PU2) · 툴팁 옵저버 대상(PU5) · 본문 주석 개정 9곳 + 머리 주석 H1⁗ 개정(PU8, §9.1) |
| 〃 | M2 | UPDATE | `<style>` 모달·세션 카드·단서·연결선 규칙 + 카드 커서 규칙 교체 · `.head-row` 안 모달 마크업 · 렌더 IIFE 모달 함수군·리스너 · 렌더 함수 분리(`renderSessionContent`·`projectPanelAttributes`·`tier1ScopeAttributes`·`projectTier1Label`) · 패널 IIFE 2곳(ESC `preventDefault`, 표시 대상 전부) · 주석·머리 주석 M2 분(§9.1) |
| `tests/hub/test_hub_template_dom.py` | M1·M2 | **CREATE** | 헤드리스 Chrome DOM 행동 검사(PU9, 승인 2). Chrome 없으면 SKIP. T24(`tests/run.sh`)의 unittest discover 가 자동으로 줍는다 |
| `tests/hub/template_dom_harness.py` · `tests/hub/test_hub_template_dom_modal.py` | M2 | **구현 단계 개정(2026-09-24)** | 800줄 상한 때문에 하네스(Chrome 탐색·서버·사전 스크립트·프로브·픽스처 빌더)와 M2 시나리오(D8~D17)를 `test_hub_template_dom.py` 에서 분리했다 — D1~D7 은 그 파일에 그대로 남는다(§3·§10.3 각주) |
| `tests/run.sh` | M1·M2 | UPDATE | T25 구역만: 기존 8건 개정(§10.1) · 신규 T25-229~240(§10.2). 래칫 상수는 **건드리지 않는다**(§10.5) |
| `tests/mutations.tsv` | M1·M2 | UPDATE | 신규 가드 변조행 · 개정 가드 5건 면제→변조 승급 · 머리 주석 「아래 287개는」 계수 287 → 286(M1) → 282(M2) |
| `hub/README.md` | M1·M2 | UPDATE | M1: 갱신이 스크롤·포커스를 지킨다는 한 줄, 드래그 억제 이유 문구 · M2: 「카드 상세보기」 절 신설 + 「프로젝트 상세 패널」 절 5곳 개정(§9.2) |
| `docs/prps/*.md` 4개 | M2 | UPDATE(표기 1줄씩) | 공개 번복·이관 표기(§9.3) — 원문을 지우지 않고 화살표만 덧붙인다 |
| `hub/bin/*.py` · `hub/install.sh` · `commands/**` · `removals.txt` | — | **무변경** | 스냅샷 계약 불변. `hub/bin/` 파일 수 불변(T25-1 의 파일 수 문구 그대로). 관리 파일 삭제·개명 없음 → 툼스톤 불필요 |
| 상시 컨텍스트(`CLAUDE.md`·`rules/**`) | — | **무변경** | T26 예산 영향 0 |

**재사용하는 기존 모듈**(새로 만들지 않는다): `renderStateBadge`·`renderSessionMeta`·
`renderAgentRunList`·`renderWorkflowRun`·`renderSessionProgress`·`renderSessionExcerpt`·
`displayableExcerpt`·`visibleSessionsOf`·`sessionRowAttributes`·`isTier1OwnerVisible`·
`panelEmptyReason`·`renderTier1`·`elapsedLabel`·`escapeHtml`·`TIER_LABEL`/`TIER_DESCRIPTION`
(렌더 IIFE), `readCardTarget`·`openDetailPanel`·`closeDetailPanel`·`applyBackgroundInert`(패널
IIFE — 앞 둘은 **무수정**으로 모달 요소를 연다), `@keyframes card-working-glow`, `.detail-close`
(닫기 버튼 위계), `.badge.tier`(세션 수 배지), `--usage-clearance`(사용량 패널 비켜 주기).

---

## 4. 파일 구조와 모듈 경계

단일 HTML 템플릿(빌드 단계 없음, 결정 PV9 — `file://` 로도 열려야 해 CDN 불가)이라 "모듈"은
IIFE 다. 경계를 넘는 통신은 **DOM 속성·body 클래스·값 없는 이벤트**뿐이다(SP1·OC8 원칙 유지).

```
<head> <style>
  … 기존 규칙 …
  [M2] .card[data-project-path]{cursor:pointer}   ← 카드 커서 규칙 교체(269~270행)
  [M2] 카드 상세보기 규칙 블록(.session-modal* · .session-strip* · .session-card*) — </style> 직전,
       즉 @media (min-width:1024px) 블록(656~663행)보다 **뒤**(SC2 스크롤 잠금이 이기는 조건)
<body>
  .wrap
    .head-row (sticky, z 10)
      h1 · .top-actions
      [M2] #dzh-session-modal.session-modal            ← 정적 싱글턴(스크림)
             section.session-modal-dialog[role=dialog][aria-labelledby=dzh-session-modal-title]
               button#dzh-session-modal-close           ← 정적
               #dzh-session-modal-body.session-modal-body ← 자식만 렌더 소유(맞대기)
    #dzh-app                                             ← 자식만 렌더 소유(맞대기) · [M2] 모달 열림 중 inert
  #dzh-usage · #dzh-tooltip · #dzh-detail-panel (무변경)

<script> IIFE 순서
  1 테마 · 2 새로고침 회전 · 4 우클릭 잠금          — 무변경
  3 툴팁                                            — [M1] 해제 옵저버 대상 #dzh-app 직계 → .wrap 하위 전체
  5 렌더(스냅샷의 유일한 소유자)
      상수 · 상태 · 순수 헬퍼 · 렌더 함수들
      [M1] 렌더 맞대기 절 — reconcileChildren 외 7함수
      [M2] 렌더 함수 분리 — renderSessionContent · projectTier1Label · tier1ScopeAttributes · projectPanelAttributes
      [M2] 카드 상세보기 절 — 상태 3변수 · 렌더 6함수 · 가로 앵커·드러내기·단서 · 열기/닫기
      render()                                      — [M1] 맞대기 1회 · [M2] + renderSessionModal()
      리스너(사용량 토글 · 바깥 클릭 · 드래그 4) · [M2] 모달 리스너 · ResizeObserver
      render(); setInterval(render, TICK_MS)
      if(!isServed){ … return; }                     ← [M2] 모달 리스너는 반드시 이 줄 앞(T25-235)
      poll …
  6 패널(스냅샷을 모른다 — T25-89)                  — [M2] ESC 가 실제로 닫았을 때 preventDefault · 표시 대상 전부
```

**경계 규칙**(변경 후):

| IIFE | 안다 | 모른다 | 이번 변경이 새로 기대는 공개 계약 |
|------|------|--------|-------------------------------|
| 렌더 | 스냅샷, 자기 마크업(`.session-row`·`.session-card`…), 패널이 읽는 속성 이름(기존) | 패널의 변수·열림 여부 | `.card-open` 을 **읽기만** 한다(모달의 1회 드러내기) — H1⁗ ③ 이 이미 공개한 선택 표시 계약이며 CSS 가 읽는 것과 같은 자격이다. ESC 는 DOM 표준 `defaultPrevented` 규약만 본다(SC8) |
| 패널 | 속성 계약(`data-project-path`·`data-dashboard-key`\|`data-panel-empty-reason`·세션 식별 속성·`data-tier1-previous`) | 스냅샷(T25-89), **모달의 존재** — 모달 루트·세션 카드도 같은 속성을 달 뿐이다 | ESC 를 실제로 썼을 때 `event.preventDefault()` (1줄) |
| 툴팁 | `data-tooltip`, `.wrap`·`#dzh-usage-body` | 모달 id — `.wrap` 하위 관찰이 모달 본문을 저절로 덮는다 | 없음 |

**왜 모달 코드가 렌더 IIFE 안인가.** 모달 본문은 스냅샷으로 그린다 → 스냅샷의 유일한 소유자가
그려야 한다. 별도 IIFE 로 떼면 스냅샷을 이벤트로 넘기는 새 계약이 생기고, 그 IIFE 를 패널 IIFE
뒤에 두면 T25-89(「`var PANEL_OPEN_BODY_CLASS` 줄 ~ 파일 끝 `snapshot` 0건」)가 깨진다. 렌더 IIFE
는 이미 사용자 상태(`storedProjectOrder`·`isUsageCollapsed`)를 모듈 변수로 쥐고 있어 모달 열림
상태를 같은 방식으로 쥐는 것이 기존 관례다. 파일은 2501 → 약 2850줄이 된다 — 단일 HTML 은 800줄
상한의 문서화된 예외(빌드 단계 없음, PV9)이고 함수 50줄 상한은 지킨다(가장 긴 새 함수
`patchChildren` 약 30줄).

---

## 5. 데이터 모델

JS 에는 타입 시스템이 없으므로 아래 타입은 **문서화 타입**이다 — 구현은 각 함수 머리의 한 줄
문서 주석에 같은 이름으로 적는다(코드 품질 기준 「공개 함수에 타입 명시와 한 줄 문서 주석」).

```ts
// ── 기존·불변 ──
type PanelTarget = {                     // 패널 IIFE 의 입력 경계(readCardTarget, 2286행) — 무변경
  projectPath: string | null; sessionId: string | null; sessionShortId: string | null;
  dashboardKey: string | null; displayName: string; emptyReason: string;
  isPreviousTask: boolean; openerElement: Element;
};

// ── [M1] 렌더 맞대기 ──
type RenderKey = string;                 // data-render-key 값. **형제 사이에서만** 유일하면 된다
// 다는 곳: .card = project.path · 카드 ul.sessions 의 <li> = session.session_id ·
//          .agent-run = run.agent_id · [M2] 모달 ul.session-strip 의 <li> = session.session_id
// 키 없는 형제의 짝 = (nodeType, tagName, class 첫 토큰) 이 같은 첫 노드(커서 이후 선행 탐색)
type PreservedAttributeName = 'aria-describedby';   // RECONCILE_PRESERVED_ATTRIBUTES 의 원소(PU3)

// ── [M2] 렌더 함수 분리 ──
type Tier1LabelView = { text: string; tooltip: string; isOrphan: boolean };  // projectTier1Label 반환(CG9·GN5)

// ── [M2] 카드 상세보기 — 렌더 IIFE 모듈 스코프 상태(사용자 상태, 비영속) ──
type SessionModalState = {
  openModalProjectPath: string | null;   // 열림 상태의 유일한 진실. body.dzh-session-modal-open 은 투영
  modalOpenerElement: HTMLElement | null;// 닫을 때 포커스를 돌려줄 카드의 .project-name
  lastModalBodyWidth: number;            // ResizeObserver 가 폭 변화만 골라내는 기준(SC10)
};
type StripAnchor = { key: RenderKey; x: number } | null;   // 맞대기 전 기준 카드의 키·화면 x(SC9)
type StripHiddenSides = { left: boolean; right: boolean }; // 숨은 쪽(SC11)
```

**DOM 속성 계약**(렌더가 쓰고 누가 읽나 — M2 기준, 굵게가 이번 변경):

| 요소 | 렌더가 다는 속성 | 읽는 쪽 |
|------|------------------|---------|
| `.card[data-project-path]` | `data-project-path` · **`data-render-key`** · `data-tier1-previous`·`data-tier1-orphan`(CSS 스코프) — **`data-dashboard-key`·`data-panel-empty-reason`·파일 모드 `data-tooltip` 은 더 이상 달지 않는다** | 드래그(`CARD_SELECTOR`) · **모달 클릭 리스너** · 패널 표시(프로젝트 요약이 열렸을 때 `.card-open`) · CSS |
| 카드 `<li>` > `button.session-row` | `<li>`: **`data-render-key`** / 버튼: `sessionRowAttributes`(무변경) | 패널(`CLICKABLE_CARD_SELECTOR`) · 맞대기 |
| **`.session-modal-root`** | `projectPanelAttributes`(옛 카드의 패널 속성 전부) + `tier1ScopeAttributes` | 패널(프로젝트 요약) · CSS |
| **모달 `<li>` > `button.session-card`** | `<li>`: `data-render-key` / 버튼: `sessionRowAttributes`(카드 세션 줄과 **글자 그대로 같은 집합**) + `card-working` 클래스 | 패널(세션) · 모달 드러내기(`.card-open` 읽기) |
| **`#dzh-session-modal-body`**(정적) | 클래스 `session-strip-hidden-left`·`-right`(JS 가 스크롤·렌더·크기 변화 때) | CSS 가장자리 단서 |
| **`body`** | `dzh-session-modal-open`(열림 투영) | CSS(스크림 표시·스크롤 잠금) |

---

## 6. 인터페이스 (공개 함수 시그니처)

모두 IIFE 안 함수 선언이다. "순수"는 DOM·저장소·시계에 닿지 않는다는 뜻이다.

```js
// ── [M1] 렌더 맞대기 (렌더 IIFE) ──
/** 새 HTML 을 템플릿으로 파싱만 하고 liveParent 의 자식을 그 결과와 같게 맞춘다. */
function reconcileChildren(liveParent /*: Element */, nextHtml /*: string */) /*: void */
/** 형제 목록 맞대기 — 키 짝은 이동, 키 없는 짝은 선행 탐색, 남은 것은 제거. */
function patchChildren(liveParent /*: Node */, nextParent /*: Node */) /*: void */
/** 짝지어진 두 노드 — 텍스트면 nodeValue, 요소면 속성 동기화 후 자식 맞대기. */
function patchNode(liveNode /*: Node */, nextNode /*: Node */) /*: void */
/** 새 결과의 속성을 쓰고 현재에만 있는 속성을 지운다(RECONCILE_PRESERVED_ATTRIBUTES 제외). */
function syncAttributes(liveElement /*: Element */, nextElement /*: Element */) /*: void */
/** 커서부터 뒤로, 키 없고 모양이 같은 첫 형제. 없으면 null. */
function findUnkeyedMatch(cursor /*: Node|null */, nextNode /*: Node */) /*: Node|null */
function isUnkeyedSameShape(liveNode /*: Node */, nextNode /*: Node */) /*: boolean */   // 순수(노드 읽기만)
function renderKeyOf(node /*: Node */) /*: RenderKey|null */                             // 순수
/** #dzh-app 에 들어갈 전체 HTML((빈 상태 또는 카드들) + 경고 블록 — 경고는 두 경우 모두 붙는다). */
function appContentHtml() /*: string */
/** 데이터 블록 파손 시의 안내 블록(지금 2019~2021행의 인라인 문자열 그대로). */
function parseErrorHtml(error /*: Error */) /*: string */

// ── [M2] 렌더 함수 분리 (렌더 IIFE) ──
/** 세션 줄·세션 카드 공통 내용(첫 줄·메타·실행·워크플로·진행·발췌). T25-127 이 여기서 첫 줄을 문다. */
function renderSessionContent(session /*: SessionView */) /*: string */
function renderSession(project, session) /*: string */          // <li data-render-key> + button.session-row + 위 내용
/** 진행률 경고 라벨 — orphan 이 이전 작업보다 강하다(CG9). 순수. */
function projectTier1Label(project, visibleSessions) /*: Tier1LabelView */
/** CSS 톤다운 스코프 겸 패널 안내 인계 속성(GN4·CG11). 순수. */
function tier1ScopeAttributes(project, tier1Label /*: Tier1LabelView */) /*: string */
/** 프로젝트 요약을 여는 요소의 패널 속성 — 불변식 OC-A(키 부재 ⇒ 사유)의 강제 지점. 순수. */
function projectPanelAttributes(project) /*: string */

// ── [M2] 카드 상세보기 (렌더 IIFE) ──
function renderSessionModalRoot(project, visibleSessions) /*: string */
function renderSessionCard(project, session) /*: string */      // <li data-render-key> + button.session-card
function renderSessionStrip(project, visibleSessions) /*: string */
/** 모달 본문 전체. 프로젝트가 사라졌으면(null) 사유 한 줄. */
function sessionModalBodyHtml(project /*: ProjectView|null */) /*: string */
/** 현재 스냅샷에서 경로가 같은 프로젝트. 없으면 null(SC15). */
function findProjectByPath(projectPath /*: string */) /*: ProjectView|null */
/** 열려 있을 때만: 앵커 포착 → 본문 맞대기 → 앵커 복원. render() 가 매번 부른다. */
function renderSessionModal() /*: void */
function openSessionModal(projectPath /*: string */, openerElement /*: HTMLElement|null */) /*: void */
function closeSessionModal() /*: void */
function captureStripAnchor() /*: StripAnchor */
/** 기준 카드가 움직인 만큼 scrollLeft 를 따라 옮긴다(자르기는 브라우저 몫). 순수. */
function anchoredScrollLeft(scrollLeft, anchorXBefore, anchorXAfter) /*: number */
function restoreStripAnchor(anchor /*: StripAnchor */) /*: void */
/** 칸의 어느 쪽에 숨은 카드가 있는가. 순수. */
function stripHiddenSides(scrollLeft, clientWidth, scrollWidth) /*: StripHiddenSides */
function updateStripEdgeCues() /*: void */
/** 항목을 칸 안에 온전히 보이게 하는 최소 scrollLeft(이미 보이면 그대로). 순수. */
function stripScrollLeftToReveal(scrollLeft, clientWidth, itemLeft, itemWidth) /*: number */
function revealStripItem(item /*: HTMLElement */) /*: void */
function revealOpenSessionCard() /*: void */

// ── [M2] 패널 IIFE — 개명 1 ──
/** 신원(projectPath, sessionId)이 같은 요소 전부(목록 + 모달). 0개면 빈 배열(엣지 E6). */
function findOpenTargetElements(projectPath /*: string|null */, sessionId /*: string|null */) /*: Element[] */
```

**맞대기 알고리즘**(구현이 따를 정본 — 설계 단계 시제품으로 §2.2 를 재현했다):

```
patchChildren(live, next):
  keyed ← { renderKeyOf(c): c  for c in live.children if 키 있음 }
  cursor ← live.firstChild                    # 불변식: cursor 앞 = 배치 끝난 노드, cursor 이후 = 미배치
  for n in 정적 복사(next.childNodes):
    k ← renderKeyOf(n)
    m ← k ≠ null ? keyed[k] 를 꺼냄(tagName 이 다르면 짝 없음) : findUnkeyedMatch(cursor, n)
    if m = null: live.insertBefore(n, cursor); continue      # 새 노드(템플릿 조각에서 입양)
    if m = cursor: cursor ← cursor.nextSibling else live.insertBefore(m, cursor)   # 이동
    patchNode(m, n)
  cursor 부터 끝까지 제거                      # 짝 없는 옛 노드(키 중복·태그 불일치 포함)
```
파싱은 `template.innerHTML = nextHtml` 로 한다 — 템플릿 내용물은 비활성 문서라 스크립트가 돌지
않고 레이아웃·스타일 계산도 없다. 키 중복·키 부재는 정확성을 해치지 않는다(뒤의 중복은 새로
삽입될 뿐 — 정체성만 덜 지켜진다).

---

## 7. 1단계 설계 결정 — 부분 갱신 (PU)

### PU1 — 갱신 방식: **키 기반 자식 맞대기, 자체 구현** (승인 1)

| 안 | 평가 |
|----|------|
| **A. 자체 맞대기(권고)** | 렌더 함수들은 지금처럼 HTML 문자열을 만들고, 넣는 순간만 노드 단위 비교. 약 70줄·함수 8개(각 ≤30줄). 이 DOM 에는 입력 폼이 없고(값·선택 영역 보존이라는 라이브러리의 어려운 몫이 없다) 이벤트가 전부 `document` 위임이라(결정 T2 — 956행) 리스너 재부착 문제도 없다 — 남는 것은 "키 짝짓기 + 속성·텍스트 동기화"뿐이다. §2.2 로 8/8 확인 |
| B. morphdom·idiomorph 인라인 벤더링 | `file://` 에서도 열려야 해 CDN 불가(PV9) → 수백 줄을 템플릿에 복사해야 한다. 「새 의존성은 표준으로 불가능할 때만」(code-quality-baseline) — A 가 가능하므로 해당 없음. 라이선스 표기·업데이트 추적·grep 가드 생태계와의 마찰까지 떠안는다 |
| C. 블록 단위 문자열 비교(카드별 HTML 이 같으면 건너뛰기) | 「N분 전」이 1분마다 거의 모든 카드 블록을 바꾼다 — 비교에 걸려 결국 대부분 교체되어 이득이 사라지고, 바뀐 카드 안의 스크롤은 여전히 초기화된다 |
| D. 틱은 시간 라벨만 고치고 폴링은 지금대로 | 틱의 초기화(1분 2회)는 사라지지만 폴링 변경(작업 중 1분 1회)은 여전히 전체 교체 — 문제의 1/3 이 남고, 시간 라벨 갱신이라는 두 번째 렌더 경로가 생긴다 |

### PU2 — 키는 전용 속성 `data-render-key` 하나, 「순서가 바뀔 수 있는 반복 형제」에만

- 상수 `RENDER_KEY_ATTRIBUTE = 'data-render-key'` — **리터럴은 파일 전체에 이 선언 1곳**(T25-230).
  렌더 함수는 `' ' + RENDER_KEY_ATTRIBUTE + '="' + escapeHtml(값) + '"'` 로 단다.
- 다는 곳: 카드(`project.path`) · 카드 세션 `<li>`(`session.session_id`) · 실행 줄 `.agent-run`
  (`run.agent_id` — 실행 중 우선 정렬(K2)이 끝나는 순간 순서를 바꾼다) · [M2] 모달 세션 `<li>`.
  워크플로 칩은 `index` 순서라 바뀌지 않으므로 키가 없다. 카드 안 블록(`.project-head`·`.path`·
  `.tier1-*`·`ul.sessions`)은 키 없이 "태그 + 첫 클래스"로 짝지어진다 — 진행률 줄이 생기거나
  사라져도 `ul.sessions` 가 제 짝을 찾아 스크롤이 살아남는다.
- **왜 기존 속성(`data-project-path`·`data-session-id`)을 키로 쓰지 않나**: ① 세션 ID 는
  `<li>` 가 아니라 안쪽 `<button>` 에 있다(1612~1613행) — 형제 단위인 `<li>` 에 열쇠가 없으면
  정렬이 바뀔 때(작업중 우선, 1721행) A 줄이 B 내용으로 **변신**해 hover·애니메이션 정체성이 엉뚱한
  줄로 넘어간다. ② `<li>` 에 `data-session-id` 를 더 달면 T25-161 의 리터럴 계수가 흔들리고
  `findOpenTargetElement` 의 담체 의미가 섞인다. ③ `readCardTarget`(2286행)이 버튼 속성을 읽으므로
  버튼 속성은 그대로 둬야 한다. 전용 속성은 맞대기를 도메인과 무관하게 만든다.
- **보너스(실측)**: 키 이동은 브라우저 스크롤 앵커링(`overflow-anchor`, 세로 축)과 합쳐져 세션
  칸에서 정렬이 바뀌어도 **보던 줄이 화면 제자리에 남는다**(scrollTop 120 → 235 자동 보정).
  Safari 는 앵커링이 없어 한 줄 밀릴 수 있다(R9). 가로 축은 어느 브라우저도 보정하지 않는다 →
  SC9 가 모달에서 손으로 보정한다.

### PU3 — 속성 동기화: 렌더 결과가 진실, 예외는 `aria-describedby` 하나

- 새 결과에 있는 속성은 값이 다르면 쓰고, **현재 DOM 에만 있는 속성은 지운다** —
  `class` 도 통째로 맞춘다. 그래서 패널이 붙인 `.card-open`·`aria-current` 도 렌더마다 지워진다.
  그 표시는 **기존 경로 그대로** 렌더 끝의 값 없는 이벤트(OC8)를 들은 패널 IIFE 가 **같은 동기
  구간**에서 되붙인다 — 페인트가 끼지 않아 깜빡임이 없다(§2.2 「같은 노드에 남음」 실측).
  `.card-dragging` 은 dragend 재렌더의 class 동기화가 지운다 — 「재렌더가 청소한다」(325~328행)는
  이유만 바뀌고 동작은 같다.
- **예외 목록 `RECONCILE_PRESERVED_ATTRIBUTES = ['aria-describedby']`**: 툴팁 IIFE 가 표시 중인
  트리거에 붙이는 속성이다(945행). 렌더가 만들지 않고 렌더 뒤 복원 경로도 없어, 지우면 툴팁이 떠
  있는 채 보조기술 연결만 끊긴다(부분 갱신이 툴팁을 살려 두기 때문에 새로 생기는 결함).
- **보존 목록을 더 늘리지 않는 이유**: `.card-open` 을 보존하면 렌더 IIFE 가 패널의 표시 규약을
  알아야 하고(SP1·OC8 위반), 열림의 진실이 `openPanelTarget` 과 DOM 두 곳에 산다. 지금 구조는
  "렌더는 렌더 결과만, 표시는 패널이 매번 다시"라 적용 지점이 하나다(OC9 의 원칙 그대로).
- **새 제약(주석으로 남긴다)**: `.card-open` 이 바꾸는 속성(background·border-color·box-shadow)에
  `transition` 을 걸지 않는다. 지웠다 되붙이는 사이에 `renderUsagePanel` 의 `offsetHeight` 읽기
  (1919행)가 강제 스타일 계산을 끼워 넣어, 전이가 있으면 그 사이 값으로 전이가 발화한다. 지금은
  그런 전이가 없어 무해하다(렌더 순서 — 연결 상태·사용량·발행 — 는 바꾸지 않는다, PU6).

### PU4 — 텍스트는 `nodeValue` 대입으로만 고친다

텍스트 노드를 교체하지 않는다. 대입은 `characterData` 변이라 `childList` 만 보는 툴팁 해제
옵저버(PU5)가 반응하지 않는다 — 30초 틱(글자만 바뀜)에 **툴팁이 살아남는** 근거다.

### PU5 — 툴팁 해제 옵저버: `#dzh-app` 직계 → `.wrap` 하위 전체

- 지금(984~986행): `#dzh-app` 을 `{childList: true}`(직계만)로 보고 발화하면 무조건 닫는다.
  통째 교체에서는 매 렌더 직계가 바뀌어 "렌더 = 닫기"였다. 부분 갱신에서는 카드 안 깊은 곳의 세션
  줄이 사라져도 직계가 그대로라 **고아 툴팁**(결정 T6 이 막던 것)이 된다.
- 개정: `.wrap` 을 `{childList: true, subtree: true}` 로 관찰, 콜백은 그대로 `hideTooltip()`.
  의미가 "**구조가 바뀌면(삽입·삭제·이동) 닫고, 글자·속성만 바뀌면 둔다**"가 된다 — 이동도 닫는
  이유는 트리거 위치가 바뀌었을 수 있어서다(툴팁은 표시 순간의 좌표로 고정된다). 드래그 라이브
  이동이 툴팁을 닫는 오늘의 동작도 그대로다. `.wrap` 은 M2 의 모달 본문까지 덮는다 — 툴팁 IIFE 는
  모달 id 를 알 필요가 없다. `#dzh-usage-body` 관찰(986행)은 그대로(T25-71).
- `new MutationObserver` 개수 2 유지(T25-107). 변수명 `appElForTooltipObserver` →
  `wrapElForTooltipObserver`(이 이름을 무는 검사 없음 — grep 확인).
- 잔여 한계: 글자만 바뀌어 트리거 크기가 달라지면 툴팁 위치가 몇 px 어긋난 채 남는다(다음 hover
  에서 교정) — 수용(R3). `tooltipTextRefreshObserver`(991~997행)는 `data-tooltip` 변경을 이미
  그 자리에서 다시 그리므로(stale 배지 문구 등) 변경하지 않는다.

### PU6 — `render()` 흐름

```js
function render(){
  if(isReordering) return;                                 // 불변(결정 O6)
  if(initialParseError){ reconcileChildren(app, parseErrorHtml(initialParseError)); return; }  // 조기 반환 불변
  reconcileChildren(app, appContentHtml());               // ← T25-107·T25-229 의 새 앵커
  // [M2] renderSessionModal();
  renderConnectionStatus();
  renderUsagePanel(snapshot.usage, snapshot.rate_limit_resets);
  document.dispatchEvent(new Event(RENDERED_EVENT_NAME)); // 위치·의미 불변(OC8)
}
```
`appContentHtml()` 은 (빈 상태 또는 카드들) + 경고 블록을 **한 문자열**로 만든다 — 경고는
두 경우 모두 붙는다(조기 반환으로 건너뛰면 안 된다, 검수 2회차 HIGH). `insertAdjacentHTML`
로 경고를 따로 붙이던 2단계(2033~2037행)가 사라진다. 호출처(틱 2123행·
폴링 2187행·dragend 2116행·즉시 갱신 3종)는 하나도 바뀌지 않는다(사용량 펼침 2054행은
`render()` 가 아니라 `renderUsagePanel` 만 부른다 — 그대로).

### PU7 — 드래그: `isReordering` 가드 유지, 취소 복원 = 키 이동

드래그 중 재렌더를 막는 이유가 "카드가 사라져 드롭이 취소된다"에서 "**재렌더가 라이브 이동을 저장
순서로 되돌려 버린다**"로 바뀐다(맞대기는 노드를 살리지만 순서는 렌더 결과로 맞춘다). 취소·카드
밖 드롭은 dragend 재렌더가 키 이동으로 되돌린다(§2.2 실측: 같은 노드, 순서 복원) — H1⁗ ② 의
문장은 그대로 성립한다.

### PU8 — 불변식 H1⁗ 개정 (이름 유지 — 조항 단위 개정, PV5·OC10 선례)

정확한 개정문은 §9.1-1. 요지: ① 첫 문장의 `#dzh-app(자식 전체 교체)` → `#dzh-app(자식 맞대기 …)`,
② 조항 ③ 의 "카드는 렌더마다 전멸하므로" → "맞대기가 class·속성을 렌더 결과로 되돌리므로",
③ **새 조항 ⑤ 노드 정체성** — "키가 같은 형제는 렌더를 넘어 같은 노드다. 스크롤·포커스·hover·
진행 중 애니메이션이 그 노드에 산다. 이것은 보존의 부수 효과이지 저장 장소가 아니다 — 사용자
상태의 진실은 여전히 재렌더 대상 밖에 둔다."

### PU9 — 검증: 정적 가드 + **DOM 행동 검사** (승인 2)

grep 가드는 "맞대기를 부른다"까지만 증명한다 — "노드가 살아남는다"는 브라우저에서만 보인다.
§2.2 의 방법을 `tests/hub/test_hub_template_dom.py` 로 옮긴다(§10.3). 핵심 오라클은 **맞대기 =
새로 그리기**: 스냅샷 A 에서 B 로 폴링한 결과의 `#dzh-app` 정규화 직렬화가 B 를 처음부터 그린
결과와 같아야 한다 — 짝짓기 오류는 전부 여기서 드러난다. 대안(선례대로 설계·구현 단계 실측만)은
회귀를 지키지 못한다.

---

## 8. 2단계 설계 결정 — 카드 상세보기 모달 (SC)

### SC1 — 위치: `.head-row` 안 마지막 자식, 정적 싱글턴 (승인 3)

```html
<div class="head-row">
  <h1>…</h1><div class="top-actions">…</div>
  <div id="dzh-session-modal" class="session-modal">                       <!-- 스크림: 가려진 목록 -->
    <section class="session-modal-dialog" role="dialog" aria-labelledby="dzh-session-modal-title">
      <button id="dzh-session-modal-close" class="detail-close session-modal-close" type="button"
              aria-label="세션 목록 닫기" data-tooltip="닫기 (Esc)"><svg …lucide x…/></button>
      <div id="dzh-session-modal-body" class="session-modal-body"></div>  <!-- 자식만 렌더 소유 -->
    </section>
  </div>
</div>
```
```css
.session-modal{position:absolute;top:100%;left:0;right:0;height:calc(100vh - 100%);
               visibility:hidden;opacity:0;pointer-events:none}
```
근거 4가지 — ① `.head-row` 는 sticky 라 그 안의 절대 위치 자식의 `top:100%` 가 **언제나 헤더 아래
가장자리**다(스크롤 중에도). 헤더가 좁은 폭에서 두 줄로 접혀도 따라간다 — 높이 측정 JS 0줄.
`height:calc(100vh - 100%)` 의 100% 는 포함 블록(헤더) 높이다. ② 폭이 `.head-row` 패딩 상자
= `.wrap` 테두리 상자라, 밀어내기 모드(body `padding-right:550px`, 661행)에서 **CSS 만으로 패널
왼쪽으로 좁아진다**(목업 b·d·e2 — 180ms 전이도 그대로 따라간다). ③ `.wrap` 안이라 1024px 미만
패널 오버레이의 `.wrap` inert(`applyBackgroundInert`, 2339행)가 **모달까지 덮는다** — 패널 IIFE
수정 0. ④ Tab 순서가 헤더 버튼 → 모달 → (잠긴) 목록으로 자연스럽다.
`#dzh-app` 상자에 맞추지 않는다 — 프로젝트 3개 이하면 그 상자는 카드 한 줄(340px)뿐이다.

기각: **body 직계 `position:fixed`** — 헤더 높이를 JS 로 재야 하고(`--usage-clearance` 식 실측 +
resize 추적), 밀어내기 폭을 `body.dzh-panel-open .session-modal{right:…}` 로 다시 적어야 하며,
`.wrap` 밖이라 오버레이 패널 뒤에서 모달에 Tab 이 들어가 패널 IIFE 의 inert 목록을 고쳐야 한다.

### SC2 — 성격: 비모달 dialog + **목록만 잠금** + 스크롤 잠금

- `role="dialog"` + `aria-labelledby`(루트의 프로젝트명 버튼 id). **`aria-modal` 은 달지 않는다** —
  패널·헤더(새로고침·테마)·사용량 패널이 계속 조작 가능하므로 "바깥 전부가 비활성"이라고 말하면
  스크린리더에 거짓말이다(SP1 이 세운 원칙).
- 열리면 `#dzh-app.inert = true`(목록만 — 가려진 카드에 Tab·클릭이 들어가지 않는다), 닫히면 false.
  패널 IIFE 가 오버레이 모드에서 쓰는 `.wrap.inert` 와 **다른 요소**라 서로 덮어쓰지 않는다.
- `body.dzh-session-modal-open{overflow:hidden}` — 덮인 목록이 휠로 흘러가 닫았을 때 읽던 위치가
  바뀌는 것을 막는다(SP3 의 오버레이 근거와 같다). 밀어내기 모드의 `body.dzh-panel-open{overflow:
  visible}`(661행)과 명세도가 같으므로 **소스 순서상 그 미디어 쿼리 블록보다 뒤**에 둬야 이긴다
  (T25-239). 대가: 클래식 스크롤바 환경에서 스크롤바 폭만큼 폭이 변한다 — 오버레이 패널과 같은
  기존 성질이라 보정하지 않는다(R11).
- 기각: **`<dialog>`+`showModal()`** — 바깥 전부를 inert 로 만들어 패널까지 못 쓴다(확정 5 위반).
  T25-76 이 옛 모달 토큰(`<dialog id="dzh-dashboard-modal"`·`showModal(`·`dzh-modal-frame`·
  `#dzh-dashboard-modal`)을, T25-77 이 `.modal::backdrop{`·`@keyframes backdrop-fade` 를 금지한다 —
  재사용하지 않으며, 새 `<dialog`·`showModal(`·`popover=` 도 0건으로 막는다(T25-237).
  **`popover="auto"`** — light-dismiss 가 패널 클릭에도 모달을 닫고, top layer 라 툴팁(z 40)이 뒤로
  숨는다(SP1 안 C 와 같은 이유).

### SC3 — 상태·소유: 렌더 IIFE 의 `openModalProjectPath`

- 열림 상태의 유일한 진실은 렌더 IIFE 모듈 변수 `openModalProjectPath`(사용자 상태 — 재렌더
  대상 밖). `body.dzh-session-modal-open` 은 그 CSS 투영(패널의 `dzh-panel-open` 과 같은 관례).
  **영속하지 않는다** — 새로고침·자가 치유 리로드·`file://` 의 포커스 복귀 리로드(2129행)에서 닫힌다
  (패널과 같다).
- 본문은 `render()` 가 열려 있을 때마다 `renderSessionModal()` 로 맞대기 갱신한다(PU1) — 폴링·틱·
  dragend·즉시 갱신 3종 전부. 열기는 상태를 세우고 `render()` 를 한 번 부른다 → 본문이 그려지고
  같은 렌더 끝의 이벤트로 패널 선택 표시까지 받은 뒤 1회 드러내기(SC10)가 돈다. `render()` 가
  이벤트를 발행하는 곳은 여전히 한 곳이라 T25-107 의 "첫 발행 줄" 판정이 흔들리지 않는다.
- IIFE 경계는 §4 표. 모달 요소는 패널과 **같은 속성 계약**을 달 뿐이라 패널 IIFE 는 모달을
  모른다(`readCardTarget`·`openDetailPanel` 무수정).

### SC4 — 클릭 계약 개정 (확정 1·2·5)

| 누르는 곳 | 결과 | 누가 처리 |
|-----------|------|----------|
| 카드 세션 줄(`.session-row`) | 패널 — 그 세션 대시보드(**무변경**) | 패널 IIFE(`closest(CLICKABLE_CARD_SELECTOR)`) |
| 카드의 그 밖(여백·`.project-name`·진행 줄·배지) | **모달** | 렌더 IIFE 새 리스너 |
| 드래그 핸들 | 없음(N6 가드) | — |
| 모달 루트(`.session-modal-root` 어디든) | 패널 — **프로젝트 최신 대시보드**(옛 카드 클릭의 결과) | 패널 IIFE(무수정) |
| 모달 세션 카드(`.session-card`) | 패널 — 그 세션 대시보드 | 패널 IIFE(무수정) |
| 스크림(다이얼로그 바깥의 모달 영역) | 모달 닫기 | 렌더 IIFE |
| 헤더·사용량 패널·상세 패널 | 모달은 그대로 | — |

- **카드는 패널 속성을 잃는다**: `renderProject`(1753~1798행)가 달던 `data-dashboard-key`|
  `data-panel-empty-reason` 과 파일 모드 안내 `data-tooltip` 을 모달 루트로 옮긴다
  (`projectPanelAttributes`). 그래서 카드 여백 클릭은 `CLICKABLE_CARD_SELECTOR` 에 걸리지 않고
  패널 IIFE 는 **코드 변경 없이** 카드 클릭에서 손을 뗀다. 카드는 CSS 스코프용
  `data-tier1-previous`·`data-tier1-orphan` 만 계속 단다(`tier1ScopeAttributes` — 톤다운 규칙
  398~406행과 T25-88·T25-184 리터럴 불변).
- **OC5**(클릭 가능 ⇔ 두 속성 OR, 2239행) — **식은 한 글자도 안 바뀐다.** 그 속성을 다는 담체가
  카드 → 모달 루트로 옮겨 갈 뿐이다. 카드 커서 규칙(269~270행)은 모달을 여는 조건에 맞춰
  `.card[data-project-path]{cursor:pointer}`·`:hover` 로 바꾸고(T25-108 개정), 모달 루트에는 OC5
  형태의 두 속성 OR 커서 규칙을 새로 둔다.
- **OC11**(모든 카드 `.project-name` 이 `<button>`) — 유지. Enter/Space 가 이제 모달을 연다 →
  `aria-haspopup="dialog"` 를 더한다(스크린리더가 "대화상자 열림 단추"로 읽는다).
- **ST26**(「노드 아닌 여백 = 프로젝트 요약」) → 개정: 카드 여백 = 모달, **모달 루트 여백 = 프로젝트
  요약**. `closest` 가 가장 안쪽을 고르는 규칙은 그대로라 세션 카드 클릭은 세션, 루트는 요약이다.
- 새 리스너(렌더 IIFE, `document` 위임, **`if(!isServed){` 마지막 등장 앞** — 뒤로 가면 `file://`
  에서 모달이 통째로 죽는다, GOTCHA — T25-235):
  ```js
  document.addEventListener('click', function(event){
    if(event.target.closest(DRAG_HANDLE_SELECTOR)) return;                  // N6
    if((window.getSelection() || {}).toString()) return;                    // N6
    if(event.target.closest(SESSION_ROW_SELECTOR)) return;                  // 확정 1 — 패널 IIFE 몫
    var sessionCard = event.target.closest(SESSION_CARD_SELECTOR);
    if(sessionCard && modalBodyEl.contains(sessionCard)){ revealStripItem(sessionCard.parentNode); return; } // SC10
    var card = event.target.closest(CARD_SELECTOR);
    if(card && app.contains(card)){ openSessionModal(card.getAttribute('data-project-path'),
                                                     card.querySelector('.project-name')); return; }
    if(openModalProjectPath !== null && event.target === modalEl) closeSessionModal();   // 스크림
  });
  ```
  두 `document` 클릭 리스너(렌더·패널)는 대상이 서로소라 등록 순서와 무관하다.
- **결과(쟁점 2)**: 프로젝트 최신 대시보드는 카드 → 모달 → 루트, **두 번 누르는 거리**가 된다.
  확정 2(프로젝트명 포함 그 밖 = 모달)의 직접 귀결이다.
- **구현 단계 개정(2026-09-28, 결함 ③)**: 위 클릭 수 자체는 그대로다 — 달라지는 것은
  **어느 요소가 그 두 번째 클릭을 받는가**다. 주인 세션 카드가 이미 화면에 보이는 통상
  경우에는 루트와 그 카드가 같은 대시보드를 여는 버튼 둘이 되어 중복이었다. 루트는 그
  대시보드를 여는 **유일한 길**일 때만(보이는 세션이 없거나, 레거시 단일 파일이거나, 주인
  세션이 orphan) 클릭 가능하도록 좁힌다(`isRootOnlyDashboardPath`, `hub_template.html`).
  그 세 경우에는 위 서술이 그대로 유효하다.

> → **개정(2026-09-30)** — 위 표의 「모달 루트」 행은 폐기됐다: 루트는 어떤 경우에도 누를 수 없다. 2026-09-28
> 개정이 만든 「유일한 길일 때만 클릭」 게이트와 그 판정(`isRootOnlyDashboardPath`)도 함께 사라졌다(hub-session-modal-cleanup.md
> 결정 MX1). 「카드의 그 밖」 행은 **보일 세션이 있는 카드**에만 적용된다 — 보일 세션이 없는 카드는 눌러도 아무 일이 없다
> (MX2). OC11 은 「카드 상세보기를 열 수 있는 카드의 제목만 `<button>`」으로 좁혀졌다(MX2). 프로젝트 최신 대시보드를 여는
> 길은 없어졌고 대시보드는 그것을 기록한 세션의 줄·카드로만 열린다(MX1·MX4).

### SC5 — 배치·폭·스크롤 (확정 3 의 해석)

- 루트(프로젝트 요약 블록)는 스크롤 칸 **밖, 위에 고정** — 가로로 넘겨도 어느 프로젝트인지 늘 보인다.
  내용: `.project-head`(프로젝트명 버튼 · 티어 배지 · 상태 배지 · **세션 N개 배지** · 마지막 활동) +
  `.path` + `renderTier1`(이전 작업/주인 없음 라벨 포함). 카드와 같은 클래스라 같은 모양이다.
- 세션 카드: `ul.session-strip>li{flex:0 0 280px;max-width:100%}` — 옛 조직도 노드 200px 은
  "너무 작다"로 반려됐다(U 보고 2). 최소 폭(320px 화면)에서는 칸 폭으로 줄어든다.
- **구현 단계 개정(2026-09-28, 결함 ②)**: 위 규칙은 `min-width:0` 이 빠진 채 착지했다 — flex
  아이템의 기본 `min-width:auto`(자동 최소 크기 = 내용의 min-content)가 줄바꿈 없는 실행 줄
  제목(`.agent-run-title`, nowrap+ellipsis)의 min-content 에 밀려, 그 제목이 있는 카드만
  280px 보다 넓어지고(1440px 뷰포트 실측 328.4px vs 280px) 말줄임이 죽는 것으로 실측됐다.
  `.session-strip>li` 규칙에 `min-width:0` 을 추가해 고친다.
- `ul.session-strip{display:flex;gap:12px;overflow-x:auto;overscroll-behavior-x:contain}` —
  **줄바꿈하지 않는다**. `overscroll-behavior-x:contain` 은 맥 트랙패드 가로 스와이프가 칸 끝에서
  **브라우저 뒤로 가기로 새는 것**을 막는다. 칸은 다이얼로그 패딩 끝까지 번지고(음수 여백 + 같은
  값의 안쪽 패딩 — `.sessions` 8px 번짐 V9 와 같은 관례) 왼쪽 정렬이라 옛 `safe center` 우회가
  필요 없다(넘침이 음수 영역으로 밀리지 않는다).
- 가로 이동 수단: 트랙패드·Shift+휠·스크롤 막대·Tab(포커스가 카드를 칸 안으로 데려온다). 세로
  휠을 가로로 바꾸는 가공은 하지 않는다(YAGNI — 다이얼로그 세로 스크롤과 다투고, 이 사용자의 맥
  트랙패드는 가로를 그대로 준다).

> → **개정(2026-09-30)** — 루트 내용에서 프로젝트 단위 진행률(`renderTier1`, 이전 작업·주인 없음 라벨 포함)이 빠졌다:
> 루트는 이름·배지·세션 수·경로뿐이다(hub-session-modal-cleanup.md 결정 MX4). 세션 카드 폭은 280→320px(MX8)이고
> 칸은 다이얼로그 높이를 채운다(MX7).

### SC6 — 세션 카드 내용·높이·정렬·강조 (확정 4·6)

- 내용 = 카드 세션 줄과 **같은 조각을 같은 순서로**: `renderSession` 의 안쪽을 `renderSessionContent
  (session)` 로 추출하고(DRY) 세션 줄·세션 카드가 공유한다. 시각 순서 규칙(`order`)은 세션 줄 것
  (458~461행)을 `.session-card>` 로 복제한다 — T25-194 가 세션 줄 리터럴을 물고 있어 셀렉터를
  합치지 않는다(T25-88 선례). 서브에이전트는 기존 실행 줄·워크플로 칩 그대로(확정 6). 칸 안의
  2단 연결선(`.session-tier1::before` 등)은 스코프가 없는 규칙이라 카드 안에서도 같은 기하로 그려진다.
- **`.session-card>.excerpt{flex-basis:auto}` 필수**(GOTCHA) — 세로 flex 에서 `flex-basis:100%`
  (540행 `.excerpt`)는 카드 **높이**의 100% 가 되어 발췌가 카드를 채운다(세션 줄이 이미 겪은 것,
  459행).
- 높이: 한 줄의 가장 큰 카드에 맞춘다(`align-items:stretch`, 목업 e1 — 카드 밑단이 가지런하다).
  다이얼로그가 `max-height` 를 넘으면 **다이얼로그가 세로로 스크롤**한다 — 카드마다 세로 스크롤을
  두지 않는다(가로·세로 스크롤 칸이 겹치면 휠 방향이 헷갈린다). 최악 조합(실행 5줄 + 칩 12개 +
  진행 3줄 + 발췌 120자)도 추정 약 400px 라 768px 화면에서는 들어간다(미실측 — §10.4 에서 확인).
- 정렬·필터: `visibleSessionsOf(project)`(1734행) 그대로 — `sessionModalBodyHtml` 도 이 함수를
  반드시 경유한다(T25-160 계약을 모달에 확장, T25-234).
- 작업중 강조: `session.state === 'working'` 이면 `card-working` 클래스. 규칙은
  `.card.card-working` 과 **같은 값·같은 keyframes**(`card-working-glow` — T25-195 가 keyframes
  개수 2 를 고정)로 `.session-card.card-working`·`::after`·`.card-open.card-working::after`·
  reduced-motion 무효화 4규칙을 **따로** 둔다(T25-65·T25-221 이 카드 규칙 리터럴을 물고 있어
  셀렉터를 합치지 않는다). 파일의 첫 `inset 0 0 Npx -Npx` 선언은 여전히 카드의 14px -1px 다(T25-221).
  stale 은 강조하지 않는다(D2 그대로).

> → **개정(2026-09-30)** — 높이: 다이얼로그는 내용이 정하는 크기가 아니라 가용 높이 전부다(모달 영역에서 아래쪽 여백 16px 만
> 뺀다, 사용량 패널이 있으면 그 위까지). 세션이 1개든 5개든 같은 크기이고 세션 카드가 그 높이를 채운다. 내용이 그보다 길면
> 여전히 다이얼로그만 세로로 스크롤한다(hub-session-modal-cleanup.md 결정 MX7). 모달 세션 카드는 진행중 단계와 실행 줄
> 제목을 잘라 내지 않는다(MX9).

### SC7 — 선택 표시: 신원이 같은 요소 **전부**

같은 (projectPath, sessionId)가 목록의 세션 줄과 모달의 세션 카드 두 곳에 생긴다(프로젝트 요약이면
카드와 모달 루트). `findOpenTargetElement`(2353행)는 첫 일치만 돌려줘 모달 쪽 표시가 빠진다 →
`findOpenTargetElements` 로 개명하고 배열을 돌려주며, `applyOpenCardMarking` 은 전부에 표시한다.
해제 루프(2368~2376행)는 이미 `.card-open` 전부를 돌므로 그대로. `aria-current` 는 요소 안에
`.project-name` 이 있으면 그것(모달 루트), 없으면 요소 자신(세션 카드)에 — 기존 분기 그대로.
CSS: `.session-card.card-open`·`.session-modal-root.card-open`(면색 `--accent-soft` + 테두리
`--accent` — 다이얼로그 면 `--surface` 위라 목록 카드(`--bg` 위, OC9 계산)보다 대비가 넉넉하다).

> → **개정(2026-09-30)** — `.session-modal-root.card-open` 규칙은 삭제됐다: 루트는 신원 속성을 달지 않아 선택 표시
> 대상이 될 수 없다(hub-session-modal-cleanup.md 결정 MX1). 표시되는 요소는 카드 안 세션 줄과 모달 세션 카드뿐이다 —
> 위 「프로젝트 요약이면 카드와 모달 루트」 경우는 없어졌다.

### SC8 — ESC: **패널 먼저, 다음 ESC 에 모달** — 등록 순서가 아니라 이벤트 단계로

- 패널 IIFE(2454~2456행) 개정 — 실제로 닫았을 때만 표시한다:
  ```js
  document.addEventListener('keydown', function(event){
    if(event.key !== 'Escape' || openPanelTarget === null) return;
    closeDetailPanel();
    event.preventDefault();          // 이 ESC 는 패널이 썼다 — 다음 소비자는 건너뛴다
  });
  ```
- 모달(렌더 IIFE)은 **`window`** 버블 단계에서 듣는다: `if(event.key !== 'Escape' ||
  event.defaultPrevented) return; closeSessionModal();`. DOM 명세상 버블은 `document` → `window`
  순이라 모달 리스너는 **문서의 모든 리스너 뒤**에 돈다 — 어느 IIFE 가 먼저 등록되든 순서가 같다.
  렌더 IIFE 는 패널 변수·클래스를 읽지 않는다(`defaultPrevented` 라는 표준 "처리됨" 신호만 본다).
- 툴팁의 ESC(970행)는 표시하지 않으므로 툴팁과 모달은 한 번에 함께 닫힌다(무해). iframe 안에
  포커스가 있으면 둘 다 ESC 를 못 받는다 — 기존 한계 E5 그대로(닫기 버튼이 1차 수단).
- 기각: 모달이 캡처 단계에서 `body.dzh-panel-open` 을 읽고 비켜서기 — 등록 순서와는 무관하지만
  렌더 IIFE 가 패널의 클래스를 알게 된다(경계 위반).

### SC9 — 가로 앵커 보정 (실측이 요구한 것)

브라우저 스크롤 앵커링은 블록 축(세로)만 보정한다 — 모달 칸에서 앞쪽에 카드가 끼어들면(뒤쪽
세션이 작업중이 되어 맨 앞으로) 보던 카드가 **한 칸(292px) 밀린다**(§2.2). 1024 패널 열림(한 장)
에서는 보던 카드가 화면에서 **사라진다** — 옛 결함 4(「뒤쪽 세션을 보고 있는데 화면이 갱신되면
스크롤이 이동해 보던 카드가 사라짐」)의 재발이다. 그래서 `renderSessionModal()` 이 맞대기 앞뒤로:
- `captureStripAnchor()`: 칸이 맨 앞(`scrollLeft ≤ 1px`)이 아니면, 칸 왼쪽 끝에서 **처음 보이는**
  카드의 키와 화면 x 를 잡는다. 맨 앞이면 잡지 않는다 — 새로 작업중이 된 세션이 맨 앞에 끼어들면
  그것이 보이는 편이 맞다.
- 맞대기 뒤 `restoreStripAnchor()`: 같은 키 카드의 새 x 로 `scrollLeft = anchoredScrollLeft(…)`
  (브라우저가 0~최대로 자른다 — 칸 끝에 붙어 있으면 보정이 잘릴 수 있다).
- 기준 카드 자신이 앞으로 옮겨 가면 칸이 그 카드를 따라간다(보던 것이 계속 보인다).
- 실측: 보던 카드 x 430 → 430(scrollLeft 300 → 592). 대안(모달이 열려 있는 동안 순서 고정)은
  승인 5.

### SC10 — 1회성 드러내기만, 매 렌더 재정렬·재중앙정렬 금지

옛 `initializeTreeRootScrollPositions` 가 매 렌더 중앙정렬로 결함 4 를 직접 만들었다
(`docs/prps/hub-unified-card-tree-ui.md` §1.2 원인 4). 이 설계는 스크롤을 **세 순간에만** 건드린다:
1. **열 때 1회**(`openSessionModal` 끝): 패널에 이 프로젝트의 세션이 열려 있으면 그 카드가 온전히
   보이게(`revealOpenSessionCard`, 목업 e2). 아니면 0 에서 시작 — 작업중이 앞에 정렬돼 있다.
2. **칸 폭이 바뀔 때**(`ResizeObserver` on `#dzh-session-modal-body`): 패널이 밀어내며 칸이 좁아지면
   방금 고른 카드가 오른쪽으로 밀려날 수 있다 → 선택 카드를 다시 들인다. **폭 변화만** 본다
   (`lastModalBodyWidth` 비교) — 높이는 내용 갱신(실행 줄 추가·글자 증감)이 바꾸고, 그때마다
   끌어당기면 사용자가 옮겨 둔 스크롤이 갱신마다 되돌아간다(결함 4 재발 — 설계 중 시제품에서 발견해
   고쳤다). 창 크기 변화도 같은 경로라 `resize` 리스너가 필요 없다.
3. **모달 세션 카드를 누른 직후**: 잘려 보이던 카드를 눌렀으면 칸 안으로 들인다(포커스 스크롤과 같은
   기대 — Safari 는 버튼 클릭에 포커스를 주지 않아 저절로는 안 된다).
`render()` 는 `revealOpenSessionCard` 를 부르지 않는다(T25-238 역가드).

### SC11 — 넘침 단서

- **숨은 쪽 가장자리 흐림**: `.session-strip-frame::before/::after` 32px 그라데이션
  (`linear-gradient(to right, var(--surface), transparent)` — 새 색 0개). 정적 컨테이너
  `#dzh-session-modal-body` 의 두 클래스 `session-strip-hidden-left`·`-right` 로만 켠다 — 그 요소는
  맞대기 대상이 아니라(자식만 맞댄다) 렌더가 클래스를 지우지 않는다. 갱신 시점: 칸 스크롤(`document`
  캡처 리스너 — 스크롤 이벤트는 버블하지 않는다, 툴팁 974행과 같은 방식) · 렌더 뒤 · 크기 변화
  (SC10-2 와 같은 옵저버). 판정은 순수 `stripHiddenSides`(1px 여유 — 서브픽셀 반올림).
- **엿보기**: 다음 카드가 칸 끝에서 잘려 보이는 것 자체가 단서다(§2.3).
- **세션 N개 배지**: 루트 머리의 `.badge.tier` 재사용 — 몇 장이 있는지를 스크롤 전에 안다.
- 기각: `@container scroll-state()`(Chrome 전용), 스크롤 구동 애니메이션(새 `@keyframes` — T25-195),
  배경 고정 그림자 기법(불투명 카드가 그림자를 덮는다).

### SC12 — 루트↔세션 연결선: 안 B (승인 4) — 결정 U2 의 모달 범위 공개 번복

- **안 B(권고)**: 루트 아래 줄기(스크롤 칸 밖, 제자리) → 가로 버스(스크롤 칸 안, 카드와 함께 흐름)
  → 각 카드로 떨어지는 드롭. 선 언어는 카드 안 세로 트리(V2~V8)와 같다 — 1px · `--muted` · 투명도
  .5. 버스는 형제 간격(12px = 좌우 −6px 두 번)을 이어 칸 어디서나 줄기와 만난다(목업 a2·e3). 세로
  증분 +14px, 규칙 7개. 사용자는 "프로젝트는 위(루트), 그 아래 세션"이라고 말했고, V2 에서 연결선
  없는 목록을 「트리가 아니다」로 반려한 이력이 있다(`docs/prps/hub-tree-view-and-signal-fixes.md`
  §1.1 반려 2) — 관계를 선으로 보이는 쪽이 그 기대에 맞다.
- **안 A**: 연결선 없음(목업 a·b·e1) — 루트와 카드의 위계는 배치(위/아래)와 표면(루트는 면 없음,
  카드는 테두리)만으로 전한다. 더 조용하다.
- **공개 번복 기록**: 결정 U2(`docs/prps/hub-unified-card-tree-ui.md` §2 변형 ②)의 **잔존 조항 —
  가로 조직도 은유 폐기**(V2 가 연결선을 세로로 되살리며 "조직도(가로) 폐기는 유지"로 남긴 절반,
  TR1 은 펼침 관련 조항만 번복)을 **모달 범위에서** 번복한다. U2 의 폭 근거는 두 몫이었다 —
  ① 3열 그리드와 나눠 쓰는 폭 ② 550px 패널 몫. 모달은 그리드 위에 떠 목록 폭 전부를 쓰므로 ① 이
  사라지고(1440 패널 닫힘 4장), ② 는 남는다(1024 패널 열림 1장) — 그래서 가로 스크롤을 감수한다
  (확정 3). U2 가 지목한 두 겹 우회 중 강제 중앙정렬은 쓰지 않고(SC10) `safe center` 도 필요 없다
  (SC5). **카드 안 세션 목록은 그대로 세로 트리다**(V2~V8·TR1 무변경).
- 옛 트리 이름은 쓰지 않는다: T25-178 이 `tree-section`·`tree-node`·`tree-root`·`tree-leaf`·
  `renderProjectTree`·`renderTreeRoot`·`renderSessionNode`·`initializeTreeRootScrollPositions` 를
  **주석 포함 파일 전체**에서 0건으로 막는다 — 새 이름(`session-modal-root`·`session-strip`·
  `session-card`·`renderSessionModalRoot`)은 겹치지 않고, 새 주석에도 그 토큰을 적지 않는다.

> → **개정(2026-09-30)** — 안 B 채택은 유지하되, 연결선의 기하는 이 절이 서술한 리터럴(줄기 길이·세로 증분·규칙 수)이 아니라
> `.session-modal-body` 의 사용자 정의 속성 5개에서 파생된다(hub-session-modal-cleanup.md 결정 MX6): 줄기·드롭·버스·칸
> 번짐이 같은 값을 쓰므로 줄기 x = 첫 드롭 x, 줄기 아랫끝 = 버스가 구성으로 성립하고 가로로 넘겨도 버스 아래 줄기 조각이
> 남지 않는다. 옛 리터럴은 1px 어긋남과 버스 아래 31px 조각을 낳았다.

### SC13 — 닫기 경로·포커스·모션

- 닫기: 닫기 버튼(`.detail-close` 위계 재사용 — "이 구역의 컨트롤", SP11·PV12, 아이콘 lucide `x`
  정적 인라인 SVG) · 스크림 클릭 · ESC(SC8). 헤더·사용량 패널·상세 패널 클릭은 닫지 않는다.
- 포커스: 열면 닫기 버튼으로(패널 선례 — 그래야 키보드 사용자가 모달을 만난다), 닫으면
  **먼저 `app.inert = false`** 한 뒤 카드의 `.project-name` 으로 되돌린다(inert 안의 요소는 포커스를
  못 받는다 — 2434행과 같은 순서 함정). 1단계 덕분에 그 버튼은 폴링을 넘어 같은 노드라 `isConnected`
  복귀가 대부분 성공한다. 포커스 트랩은 만들지 않는다(목록은 inert, 나머지는 원래 쓸 수 있는 것들).
- 닫으면 본문을 비운다(`replaceChildren()`) — 다음 열기는 가로 스크롤 0 에서 새로 그린다.
- 모션: 열기만 180ms 불투명도 전이(패널 슬라이드와 같은 시간·이징), 닫기는 즉시 — 전이 선언을
  열린 상태 규칙에만 두는 SP5 기법(타이머 0개). `prefers-reduced-motion` 에서 무효화. 새
  `@keyframes` 0개(T25-195).

### SC14 — 좁은 화면(< 1024px, 패널 오버레이 모드)

모달은 목록 폭 그대로 뜬다(목업 f, 820px — 카드 2장 + 엿보기). 세션 카드를 누르면 패널이 모달까지
**덮고**(`.wrap` inert 가 모달을 포함 — SC1-③), 패널을 닫으면 모달로 돌아와 포커스가 누른 세션
카드로 복귀한다. 두 표면이 동시에 보이는 것은 밀어내기 모드(≥1024)뿐이다(확정 5 의 "넓은 화면").

### SC15 — 사라진 프로젝트·빈 목록

- 열린 프로젝트가 스냅샷에서 사라지면 모달을 **닫지 않고** 본문에 사유 한 줄
  (「이 프로젝트는 최신 목록에 없습니다 — 닫고 다시 선택하세요.」) — 패널의 N8·SP7("읽던 화면을
  빼앗지 않는다")을 승계한다. 루트가 사라지므로 패널로 가는 문도 함께 사라진다(거짓 링크가 없다).
- 보일 세션이 0개(티어 3 등)면 루트 + 「화면에 보일 세션이 없습니다.」 — 루트는 여전히 패널에
  사유를 보여준다(OC6·OC7 경로).

> → **개정(2026-09-30)** — 「루트는 여전히 패널에 사유를 보여준다」는 폐기됐다: 루트는 어떤 경우에도 누를 수 없다(hub-session-modal-cleanup.md
> 결정 MX1). 열린 채 폴링으로 보일 세션이 0개가 되어도 모달은 닫히지 않고 이 문구를 그대로 보인다(MX3 — 「읽던 화면을 빼앗지
> 않는다」 승계). 처음부터 보일 세션이 0개인 카드는 모달을 열지 않는다(MX2).

### SC16 — 사용량 패널·쌓임 순서

- 사용량 패널 바깥 클릭 접기(2061~2069행): 모달 안 클릭도 **페이지 클릭으로 본다**(목록 카드
  클릭과 같은 규칙 — 코드 무변경). 상세 패널 클릭만 예외인 Q4 는 그대로.
- 모달은 `.head-row`(z 10)의 쌓임 맥락 안이라 사용량(20)·패널(30)·툴팁(40) **아래**다 — 툴팁이
  모달 위에 뜨고, 패널이 오버레이 모드에서 모달을 덮는다. 사용량 패널이 다이얼로그 아랫부분에
  얹히지 않도록 `body.has-usage .session-modal-dialog{max-height:calc(100% - var(--usage-clearance,
  218px))}`(585행과 같은 변수·같은 폴백).

> → **개정(2026-09-30)** — 다이얼로그의 `max-height` 는 `height` 로 바뀌었다(사용량 패널이 있는 변형도 같은 변수·폴백으로 `height`,
> hub-session-modal-cleanup.md 결정 MX7).
> → **개정(2026-10)** — 사용량 패널은 떠 있는 컴포넌트라 창의 자리·최대 높이에 관여하지 않는다: 오버레이의 아래 여백은 16px 고정이고
> `body.has-usage .session-modal` 규칙은 삭제됐다(hub-session-row-layout-and-modal-size.md 결정 LM8 개정). 쌓임 순서(패널이 창 위) 서술은 그대로다 —
> 큰 창의 아랫변이 패널 밑으로 들어갈 수 있다. `--usage-clearance` 는 카드 목록(`.wrap`)의 아랫 여백만 쓴다.

### SC17 — 이름: 사용자에게는 「카드 상세보기」 (승인 6)

- 사용자 원문(이 세션의 첫 요청)은 "**카드 상세보기 모달**"이었다 → README 제목 「카드 상세보기」,
  본문 첫 문장에서 "(모달)"로 한 번 밝힌다. 기존 「프로젝트 상세 패널」과 "상세"가 겹치지만 절
  첫 줄에서 둘의 관계(카드 상세보기 → 루트·세션 카드 → 상세 패널)를 적어 구분한다.
- README 에 "모달"을 쓰므로 T25-81 역검사(README `모달` 0건)를 **옛 기능의 이름 「대시보드 모달」
  0건**으로 좁힌다 — 그 검사가 막으려던 것(옛 `<dialog>` 대시보드 모달 서술의 잔존)은 그대로 막는다
  (옛 절 제목이 「프로젝트 대시보드 모달」이었다, 커밋 `2352c69`).
- 코드 이름: `#dzh-session-modal`·`.session-modal*`·`.session-strip*`·`.session-card`·
  `SESSION_MODAL_OPEN_BODY_CLASS = 'dzh-session-modal-open'`. T25-76·T25-77·T25-159·T25-178·
  T25-196 금지 토큰과 겹치지 않음을 확인했다.

---

## 9. 주석·README·이관 표기

### 9.1 `hub_template.html` 주석 (M1·M2)

**9.1-1 머리 주석 H1⁗ (32~61행) — 정확한 개정문**

(M1) 32~34행 첫 문장을 다음으로 바꾼다:
```
  불변식 H1⁗(정본: docs/prps/hub-detail-side-panel.md 결정 SP6 → 조항 개정 docs/prps/
  hub-session-modal-and-partial-update.md 결정 PU8). 폴링·틱이 내용을 갱신하는 대상은
  #dzh-app(자식 맞대기 — 새 렌더 결과를 노드 단위로 비교해 바뀐 텍스트·속성만 고치고,
  렌더 키(RENDER_KEY_ATTRIBUTE)가 같은 형제는 노드째 옮긴다) · #dzh-usage-body(innerHTML) ·
  #dzh-usage-summary(textContent) · #dzh-refresh 의 data-tooltip·class 속성뿐이다.
```
(M2) 위 목록의 `#dzh-app(…)` 뒤에 `· #dzh-session-modal-body(같은 맞대기 — 카드 상세보기가
열려 있을 때만)` 을 더하고, 정적 노드 목록(35~36행)에 `#dzh-session-modal(과 그 정적 자식 —
다이얼로그 틀·닫기 버튼. 본문의 자식은 제외)` 을 더한다.

(M1) 조항 ③ 의 49~51행 "카드는 렌더마다 전멸하므로 그 표시는 렌더 뒤에 다시 붙어야 한다 —"를:
```
  맞대기는 카드 노드를 살려 두지만 class·속성을 렌더 결과와 똑같이 맞추므로(렌더 결과에 없는
  표시는 지운다 — 예외는 툴팁 IIFE 가 붙이는 aria-describedby 하나, 결정 PU3) 그 표시는 렌더
  뒤에 다시 붙어야 한다 —
```
그리고 같은 조항 끝에 한 문장: "그래서 .card-open 이 바꾸는 속성에는 transition 을 걸지 않는다
— 지워졌다 되붙는 사이에 강제 레이아웃이 끼면 그 사이 값으로 전이가 발화한다."

(M2) 52~53행 원칙 문장의 사용자 상태 목록 "(포커스·접힘·선택·순서·열린 상세 패널)" →
"(포커스·접힘·선택·순서·열린 상세 패널·열린 카드 상세보기)".

(M1) ④ 뒤(61행 다음)에 새 조항:
```
  ⑤ 노드 정체성(결정 PU1·PU2): 렌더 키(RENDER_KEY_ATTRIBUTE)가 같은 형제는 렌더를 넘어 같은 DOM 노드다 —
  스크롤 위치·키보드 포커스·hover·진행 중 애니메이션이 그 노드에 산다(설계 단계 실측, 헤드리스
  Chrome 153). 이것은 보존의 부수 효과이지 저장 장소가 아니다 — 사용자 상태의 진실은 여전히
  재렌더 대상 밖(모듈 변수·localStorage·body 클래스)에 둔다.
```

(M2) 패널 문단(95~102행) 뒤에 카드 상세보기 문단 신설:
```
  카드 상세보기(#dzh-session-modal, docs/prps/hub-session-modal-and-partial-update.md 결정
  SC1~SC17)는 .head-row 안의 정적 싱글턴이다 — 헤더 아래 가장자리에 붙고 폭은 목록을 따라
  밀어내기 모드에서 CSS 만으로 패널 왼쪽에 선다. 열림 상태의 유일한 진실은 렌더 IIFE 의
  openModalProjectPath 이고 body.dzh-session-modal-open 은 그 CSS 투영이다. 본문
  (#dzh-session-modal-body)의 자식만 렌더가 맞대기로 그린다. 모달 루트·세션 카드는 패널과 같은
  속성 계약(data-project-path · data-dashboard-key 또는 data-panel-empty-reason …)을 달 뿐이라
  패널 IIFE 는 모달을 모른다. 열려 있는 동안 #dzh-app 은 inert 다(목록만 — 헤더·사용량·패널은
  산다). ESC 는 패널이 먼저 쓴다 — 패널이 닫았으면 defaultPrevented 이고, 모달은 window 버블
  단계에서 표시 없는 ESC 만 받는다(결정 SC8).
```
같은 문단 95~97행의 "카드 클릭이 iframe 문서와 제목만 바꾸고" → "세션 줄·모달 루트·모달 세션 카드
클릭이 iframe 문서와 제목만 바꾸고".

**GOTCHA — 주석에 적으면 검사가 깨지는 리터럴**: `data-session-id`·`data-session-short-id`·
`data-project-name`(T25-161 이 파일 전체 **정확히 2건**), `data-render-key`(T25-230 **정확히 1건** —
주석은 상수 이름 `RENDER_KEY_ATTRIBUTE` 로 쓴다), 카드 패널 속성 이름을 `renderProject` 본문 주석에
다시 적는 것(T25-233 가 그 본문에서 0건을 본다), 렌더 완료 이벤트 이름 문자열(T25-107
**정확히 2건** — 주석은 "렌더 완료 이벤트"로 쓴다), `tree-root` 등 옛 트리 토큰 8종(T25-178 0건),
`<style>` 안의 `https://`(T25-162), `border-bottom:`(T25-85), 패널 IIFE 범위의 `snapshot`
(T25-89). 위 개정문은 이 조건을 지키도록 썼다.

**9.1-2 본문 주석 개정 목록**

| # | 행 | 지금 | 개정 | M |
|---|----|------|------|---|
| 1 | 63~65 | "#dzh-app 은 폴링이 자식 전체를 교체하는 정당한 영역" | "…자식을 맞대기로 갱신하는 정당한 영역" | M1 |
| 2 | 265~268 | 카드 커서 OC5 주석 | 카드 = 모달을 여는 조건(`data-project-path`), 두 속성 OR 은 모달 루트로 이관(SC4) | M2 |
| 3 | 325~328 | "dragend 가 render() 를 불러 카드를 재생성하므로 …" | "dragend 재렌더(맞대기)가 class 를 렌더 결과로 되돌려 청소한다" | M1 |
| 4 | 956~957 | "폴링이 #dzh-app.innerHTML 을 통째로 교체하므로 …" | "맞대기가 노드를 살려도 키가 새로 생기는 노드(새 카드·새 세션)는 새로 만들어지므로 위임이 여전히 유일하게 안전하다" | M1 |
| 5 | 977~981 | 툴팁 해제 옵저버 근거 | PU5 의 "구조 변화 = 닫기, 글자·속성 = 유지" + `.wrap` 하위 관찰 이유(모달 포함) | M1 |
| 6 | 1576~1579 | `sessionRowAttributes` | "모달 세션 카드도 이 속성 집합을 그대로 쓴다(SC4) — 패널 IIFE 무수정의 근거" | M2 |
| 7 | 1609~1611 | `renderSession` | 첫 줄 구성은 `renderSessionContent` 로 옮겼다(T25-127 앵커 이동) | M2 |
| 8 | 1682~1685·1696~1698 | "사유를 카드에 실어" · "모든 카드가 패널을 열므로" | "모달 루트에 실어" · "모든 카드가 모달을 연다(OC11 유지)" | M2 |
| 9 | 1717~1720 | "30초마다 innerHTML 을 통째로 교체하므로 비결정 정렬은 카드 깜빡임" | "비결정 정렬은 매 틱 헛 노드 이동(툴팁 닫힘·앵커 흔들림)이 된다" | M1 |
| 10 | 1729~1733 | "소비자가 renderProject 하나뿐" | "소비자 둘(카드·카드 상세보기)" | M2 |
| 11 | 2040~2041 | "카드가 방금 전멸·재생성됐다(위 insertAdjacentHTML 앞 로직)" | "카드 DOM 이 방금 렌더 결과와 맞춰졌다(맞대기가 표시 class 를 지웠다)" | M1 |
| 12 | 2071~2072 | "#dzh-app 자식은 렌더마다 전멸하므로 전부 document 위임" | #4 와 같은 근거 | M1 |
| 13 | 2225~2229 | 패널 IIFE 머리 "카드를 누르면 …" | "세션 줄·모달 루트·모달 세션 카드를 누르면 …" | M2 |
| 14 | 2347~2352 | `findOpenTargetElement` "담체가 하나(카드+세션 행)뿐" | "담체 넷(카드·세션 줄·모달 루트·모달 세션 카드), 같은 신원이 목록과 모달에 둘씩 — 전부 표시" | M2 |
| 15 | 2363~2366 | "DOM 은 렌더마다 새 노드라 … 첫 루프가 0회" | "렌더 직후에는 맞대기가 표시 class 를 이미 지워 첫 루프가 0회" | M1 |
| 16 | 2469~2470 | "#dzh-app 을 통째로 교체하면 표시도 함께 사라진다" | "맞대기가 class 를 렌더 결과로 되돌리면 표시도 지워진다 — 같은 동기 구간에서 복원" | M1 |

### 9.2 `hub/README.md`

**M1**
- 「화면 배치」(241행~)에 한 항목: "30초 틱·1분 폴링은 **바뀐 글자·속성만** 고친다 — 세션 목록의
  스크롤 위치·키보드 포커스·작업중 강조의 움직임이 갱신 때문에 처음으로 돌아가지 않는다. 떠 있던
  툴팁도 글자만 바뀌면 남고, 줄이 생기거나 사라지면 닫힌다."
- 342행 드래그: "드래그 중인 카드가 갑자기 사라져" → "드래그 중인 카드가 저장된 자리로 되돌려져".

**M2 — 「카드 상세보기」 절 신설**(「카드 순서」와 「프로젝트 상세 패널」 사이) 필수 내용:
카드를 누르면(세션 줄 제외) 그 프로젝트의 세션을 모아 보는 카드 상세보기(모달)가 헤더 아래·목록
위에 뜬다 · 위는 프로젝트(누르면 상세 패널에 프로젝트 최신 대시보드), 아래는 세션 카드 가로 한 줄
(280px, 카드 안 세션 줄과 같은 내용 — 서브에이전트 실행 줄·진행률·발췌) · 한 줄에 다 안 들어가면
가로 스크롤(트랙패드 좌우·Shift+휠·스크롤 막대), 숨은 쪽 가장자리가 흐려지고 머리에 세션 수가
보인다 · 세션 카드를 누르면 상세 패널이 그 세션 대시보드로 열리고 넓은 화면(1024px 이상)에서는
카드 상세보기가 패널 왼쪽으로 좁아져 **둘이 함께** 보인다, 좁은 화면에서는 패널이 덮고 닫으면
돌아온다 · 같은 세션은 목록과 카드 상세보기 **두 곳 다** 선택 표시 · 작업중 세션 카드는 카드와
같은 강조 · 갱신돼도 가로 위치를 지키고, 상태가 바뀌어 순서가 달라져도 보던 카드가 밀려나지
않는다 · 닫기: ✕·Esc(**상세 패널이 열려 있으면 패널이 먼저 닫힌다**)·흐려진 목록 클릭 · 열려
있는 동안 뒤의 목록은 누르거나 끌 수 없다 · 새로고침하면 닫힌다(저장하지 않는다).

**M2 — 「프로젝트 상세 패널」 절 개정 5곳**

| 행 | 지금 | 개정 |
|----|------|------|
| 347 | "**어느 카드든** 클릭하면 상세 패널이 열린다" | "**어느 카드든** 클릭하면 카드 상세보기가 열리고, 그 머리(프로젝트)나 세션 카드·카드의 세션 행을 누르면 상세 패널이 열린다" |
| 356 | 티어 2·3·`file://` 안내 "모든 카드가 … 패널과 툴팁 두 곳에서" | "카드 상세보기의 머리·세션 카드·세션 행이 … 패널과 툴팁 두 곳에서" |
| 386 | "다른 카드를 누르면 표시가 그 카드로 옮겨간다" | "같은 세션이 목록과 카드 상세보기 두 곳에 있으면 둘 다 표시된다" |
| 390~399 | "세션 행이 아닌 카드 여백을 누르면 카드와 똑같이 그 프로젝트의 요약이 열린다" | "세션 행이 아닌 카드 여백을 누르면 카드 상세보기가 열린다(프로젝트 요약은 그 머리에서)" |
| 400~410 | "카드도 같은 판정을 받는다 … 카드도 클릭이 막히고" · "카드를 눌러도 대시보드는 똑같이 열린다" | 주어를 "카드 상세보기의 머리"로 — 굵은 문구 「카드도 같은 판정을 받는다」는 **그대로 둔다**(T25-218) |

**보존해야 할 README 토큰**(검사가 문다): `상세 패널`·`밀`·`덮`·`나간다`(T25-81) · `어느 카드든`·
`사유`·`배경색`(T25-109) · `카드도 같은 판정을 받는다`(T25-218) · `주인 세션 없음`(T25-223) ·
`작업중`(T25-65) · `서브에이전트`·`툴팁`(T25-45) · `바깥`(T25-66) · `확장`·`세션 행`·`연결선`
(T25-188) · `즉시`·`스크롤`. **쓰면 안 되는 토큰**: `트리 모드`·`보기 토글`(T25-188), `클릭 대상이
아니다`(T25-109), `대시보드 모달`(개정 T25-81).

### 9.3 이관 표기 (원문을 지우지 않고 화살표 한 줄 — SP6 표의 관례)

| 문서 | 지점 | 덧붙일 표기 |
|------|------|-------------|
| `hub-unified-card-tree-ui.md` | 결정 U2(105행 인용문) | `→ **부분 번복(2026-09-23, 카드 상세보기 모달 범위)** — hub-session-modal-and-partial-update.md 결정 SC12. 카드 안 세로 목록은 유지` |
| `hub-session-tree-and-per-session-dashboards.md` | 결정 ST26(797행 절) | `→ **개정** — 카드 여백 = 카드 상세보기, 프로젝트 요약은 모달 루트(결정 SC4)` |
| `hub-panel-empty-state-and-open-card.md` | 결정 OC5·OC9·OC11 | OC5 `→ 식 유지, 담체가 카드 → 모달 루트(SC4)` · OC9 `→ 표시 대상 전부(SC7)` · OC11 `→ 유지, 동작은 모달 열기 + aria-haspopup(SC4)` |
| `hub-detail-side-panel.md` | 결정 SP6 표 머리 | `→ **조항 개정(2026-09-23)** — 첫 문장·조항 ③·신설 ⑤, hub-session-modal-and-partial-update.md 결정 PU8` |

---

## 10. 테스트 계획

### 10.1 기존 테스트 영향 (전수)

| ID | 지금 무엇을 보나 | 개정 | 원장 |
|----|------------------|------|------|
| **T25-107** (M1) | `dzh:rendered` 2회 · `new MutationObserver` 2회 · 발행 줄이 `app.insertAdjacentHTML('beforeend', extra);` 뒤·패널 IIFE 앞 | 앵커를 `reconcileChildren(app, appContentHtml());` 로. M2 에서 "발행 줄 > `renderSessionModal();` 줄"을 더한다. 계수 조건은 그대로 | 면제 → **변조 승급**(발행 줄 삭제 변조) |
| **T25-81** (M2) | README 토큰 · 머리 주석 `H1⁗` · 역: README `모달` 0 | 역검사를 `대시보드 모달` 0 으로 좁히고 정방향 `카드 상세보기` 추가 | 면제 → 변조 승급(README 에 `대시보드 모달` 삽입) |
| **T25-105** (M2) | `else cardAttrs += ' data-panel-empty-reason=…'` 리터럴(파일 전체) | 그 리터럴을 `function projectPanelAttributes(` 본문 안에서 찾는다(변수명 `attrs` — `sessionRowAttributes` 의 같은 줄과 구분되도록 **본문 한정**이 필수) | 면제 → 변조 승급(주소 범위 `s` — 그 본문의 `else` 를 `else if(emptyReason)` 로) — **구현 단계 개정(2026-09-24)**: 원장 write-safe 형태가 주소 범위를 받지 않아 변수 이름을 고유하게 하고 평문 `s` 로 |
| **T25-108** (M2) | `.card[data-panel-empty-reason]{cursor:pointer}` 존재 · 옛 단독 셀렉터 부재 | 정: `.card[data-project-path]{cursor:pointer}` · `.session-modal-root[data-dashboard-key],.session-modal-root[data-panel-empty-reason]{cursor:pointer}` / 역: 카드의 두 속성 커서 규칙 부재 | 면제 → 변조 승급 |
| **T25-163** (M2) | 패널 IIFE 에 `function findOpenTargetElement(` | `function findOpenTargetElements(` + 역: 단수형 0 + `applyOpenCardMarking` 본문이 루프(`targets.length`) | 면제 → 변조 승급 |
| **T25-127** (M2) | `renderSession()` 본문의 첫 줄 구성 | 앵커를 `function renderSessionContent(session){` 로 + **공허 통과 방지**: 추출 본문에 `class="session-line"` 이 없으면 실패("앵커가 깨졌다") | 변조행 유지(행 텍스트가 새 함수로 따라가 그대로 적용된다) |
| **T25-218** (M2) | `renderProject()` 본문의 `tier1_is_finished_task` | 범위를 `projectPanelAttributes()` 본문으로 | 변조행 유지(`panelEmptyReason` 대상) |
| **T25-223** (M2) | `renderProject()` 의 `var isClickable = ` 줄·`data-tier1-orphan` | `var isClickable` 은 `projectPanelAttributes()`, `data-tier1-orphan` 은 `tier1ScopeAttributes()` 본문 | 변조행 유지(CSS 대상) |
| T24 | `python3 -m unittest discover -s tests` 종료 코드 | 무변경 — 신규 DOM 검사 모듈을 **자동으로 줍는다**(런타임 +10~20초, Chrome 없으면 SKIP) | — |

**건드리지 않지만 새 코드가 지켜야 하는 제약**: T25-44(`title="` 0) · T25-65(`.card.card-working{`
유지) · T25-71(`#dzh-usage-body` 관찰 유지) · T25-76·T25-77(옛 모달 토큰 0) · T25-78(첫 `@media
(min-width:…)` 이 1024 — 새 min-width 쿼리를 앞에 두지 않는다) · T25-79(첫 `.detail-panel,` 줄
위치 — 새 규칙에 그런 줄을 만들지 않는다) · T25-85(`border-bottom:` 0) · T25-88·T25-184(카드 톤다운
리터럴) · T25-89·T25-105(패널 IIFE 범위 `snapshot`·티어 문구 0) · T25-109(머리 주석
`data-panel-empty-reason`·`aria-current` 유지) · T25-159·T25-196(옛 보기 모드·확장 토큰 0 —
`aria-pressed` 금지) · T25-160(`function renderProject(project){` 시그니처·`visibleSessionsOf(`) ·
T25-161(세 신원 속성 리터럴 **정확히 2** — 새 코드는 상수만, `escapeHtml(session.session_id)` ≥ 2) ·
T25-162(`<style>` 안 `https://` 0) · T25-178(옛 트리 토큰 0) · T25-183(`sessionRowAttributes` 본문
쌍) · T25-193·T25-194·T25-197·T25-198(세션 줄 기하 리터럴) · T25-195(`@keyframes` 정확히 2) ·
T25-221(첫 inset bloom 14px -1px).

### 10.2 신규 정적 가드 (T25 구역, `test_hub_docs_and_constants`)

변조 설명은 "무엇을 흉내 내는가"다 — 정확한 sed 는 구현 뒤 실제 줄로 쓴다. 한 줄 `s` 로 흉내 낼 수
없는 순서 검사만 앵커 파손 변조로 대신한다(기존 관례).

| ID | M | 방향 | 검사 | 변조가 흉내 내는 결함 |
|----|---|------|------|----------------------|
| T25-229 | M1 | 정·역 | `render()` 본문에 `reconcileChildren(app,` / 역: `app.innerHTML`·`insertAdjacentHTML` 0 | 통째 교체로의 회귀 |
| T25-230 | M1 | 정 | `'data-render-key'` 리터럴 파일 전체 **정확히 1**(상수 선언) · `renderProject`·`renderSession`·`renderAgentRunRow` 본문에 `RENDER_KEY_ATTRIBUTE` | 세션 `<li>` 키 누락(정렬 때 줄 변신) |
| T25-231 | M1 | 정 | `RECONCILE_PRESERVED_ATTRIBUTES` 선언에 `'aria-describedby'` · `syncAttributes` 본문이 그 상수를 본다 · `patchNode` 본문이 `nodeValue` 대입을 쓰고 `replaceChild` 0 | 보존 예외 삭제(떠 있는 툴팁의 보조기술 연결 끊김) |
| T25-232 | M1 | 정 | 툴팁 해제 옵저버의 `.wrap` 관찰 호출에 `subtree: true` | 직계 관찰로의 회귀(깊은 트리거 제거 시 고아 툴팁) |
| T25-233 | M2 | 정·역 | `renderProject()` 본문에 `projectPanelAttributes(`·`data-dashboard-key`·`data-panel-empty-reason` 0 / `renderSessionModalRoot()` 본문에 `projectPanelAttributes(` | 카드가 다시 패널을 여는 회귀(확정 2 위반) |
| T25-234 | M2 | 정 | `renderSessionCard()` 본문에 `sessionRowAttributes(`·`RENDER_KEY_ATTRIBUTE`·`renderSessionContent(` · `sessionModalBodyHtml()` 이 `visibleSessionsOf(` 경유, `.filter(shouldRenderSession)` 직접 0 | 모달이 필터를 우회해 카드와 다른 세션 집합을 보임 |
| T25-235 | M2 | 정 | `openSessionModal(` 을 부르는 리스너 줄 < 마지막 `if(!isServed){` 줄(T25-66 관용구) | `file://` 에서 모달 소실 |
| T25-236 | M2 | 정 | 패널 keydown 처리에 `closeDetailPanel();` 다음 `event.preventDefault();` · 모달 ESC 가 `window.addEventListener('keydown'` 이고 본문에 `event.defaultPrevented` | ESC 한 번에 패널·모달 동시 닫힘 |
| T25-237 | M2 | 역 | `<dialog`·`showModal(`·`popover=` 파일 전체 0 | 네이티브 모달 도입(패널까지 inert) |
| T25-238 | M2 | 정·역 | `renderSessionModal()` 본문이 `captureStripAnchor(` → `reconcileChildren(` → `restoreStripAnchor(` 순 · `render()` 본문에 `revealOpenSessionCard(` 0 · ResizeObserver 콜백이 `contentRect.width` 를 비교 | 매 렌더 재중앙정렬(결함 4 재발) · 앵커 누락 |
| T25-239 | M2 | 정 | 모달 규칙 블록(`.session-modal`·`.session-strip`·`.session-card` 셀렉터 규칙)에 `#` 색 리터럴 0 · `body.dzh-session-modal-open{overflow:hidden}` 줄 > `body.dzh-panel-open #dzh-usage{transform:` 줄 · reduced-motion 무효화 2종(모달 전이·세션 카드 glow) · `.session-card.card-working::after` 가 `card-working-glow 2s` | 밀어내기 모드에서 스크롤 잠금이 지는 순서 회귀 · 새 색 리터럴 |
| T25-240 | M2 | 정 | (승인 4 = 안 B 일 때만) `.session-strip-linked>li::before`·`::after`·`.root-linked::after` 존재 | 연결선 부분 삭제 |

원장: 12행 모두 변조행이 기본(면제 상한 382 에 여유 55가 있지만 신규 면제는 사유가 약하다).
각 변조행은 구현 보고에 "그 변조로 해당 ID 가 실제로 실패함"을 한 줄씩 남긴다(code-review
「새 검사는 일부러 깨뜨렸을 때 실패함을 확인」).

### 10.3 DOM 행동 검사 — `tests/hub/test_hub_template_dom.py` (승인 2)

> **구현 단계 개정(2026-09-24)**: 800줄 상한 때문에 하네스·M2 시나리오를 분리했다 —
> 공용 하네스는 `tests/hub/template_dom_harness.py`, D1~D7 은 `test_hub_template_dom.py`
> 그대로, D8~D17(M2)은 `tests/hub/test_hub_template_dom_modal.py` 신설.

**구조**(stdlib 만 — `unittest`·`http.server`·`threading`·`subprocess`·`tempfile`·`json`):
- Chrome 탐색: `DZH_TEST_CHROME` 환경변수 → macOS 기본 경로 → `shutil.which('google-chrome'|
  'chromium'|'chromium-browser')`. 없으면 `unittest.skipUnless` — **SKIP 사유를 출력**한다.
- 페이지: `hub/bin/hub_template.html` 을 읽어 **실제 dataclass 픽스처 + `hub_model.render_hub_html`**
  로 굽는다(이스케이프 계약까지 실물 — `tests/hub/test_hub_model.py` 의 스냅샷 빌더 관례). 사전
  스크립트(`<body>` 직후)와 프로브(`</body>` 앞)를 끼운 사본을 `TemporaryDirectory` 에 쓴다. 대상
  템플릿 경로는 `DZH_DOM_TEST_TEMPLATE` 로 바꿀 수 있다 — **"일부러 깨뜨렸을 때 실패" 확인용**
  (구현자는 `33d5cea` 템플릿으로 돌려 M1 시나리오가 실패함을 보고에 남긴다 — §2.2 가 그 예고편).
- 서버: `ThreadingHTTPServer(('127.0.0.1', 0))` 를 데몬 스레드로, `tearDownClass` 에서
  `shutdown()` — 백그라운드 프로세스가 남지 않는다. Chrome 은 시나리오마다
  `--headless=new --disable-gpu --use-mock-keychain --window-size=W,H --virtual-time-budget=5000 --dump-dom URL` 1회,
  결과는 프로브가 붙인 `<pre id="probe-result">` 의 JSON.
- 사전 스크립트가 반드시 할 것(§2.2 함정 1~4): `--user-data-dir` 를 **주지 않는다** · `fetch` 를
  허브 스크립트보다 먼저 가로채 모든 폴링(포커스 복귀 폴링 포함)이 시험이 정한 문서를 받게 한다
  (빈 문자열이면 `lastHtml` 과 같아 렌더하지 않는다) · 응답은 `{ok:true, text:()=>Promise.resolve(…)}`
  가짜 객체 · `setInterval` 등록을 기록해 30초 틱 콜백을 직접 부른다 · `Date.now` 에 오프셋을
  건다(오라클 비교용으로 **고정**도 가능) · 고정 대기 대신 렌더 완료 이벤트를 기다린다.
- 정규화 직렬화: 속성을 이름순으로, 패널 표시(`card-open` 클래스 토큰·`aria-current`)와
  `aria-describedby` 를 뺀 트리 문자열.

**시나리오와 단언**

| # | M | 시나리오 | 단언 |
|---|---|----------|------|
| D1 | M1 | A 로드 → 폴링 B(정렬 뒤집힘) | 카드·`ul.sessions` 같은 노드 · `<li>` 가 자기 세션을 들고 이동 · scrollTop 이 0 으로 돌아가지 않음 · glow `CSSAnimation` 같은 객체 · 포커스 유지 — **구현 단계 개정(2026-09-23)**: 원안의 「보던 줄의 화면 top ±1px」은 단언하지 않는다. 정렬이 바뀌면 브라우저 스크롤 앵커링이 **자기 규칙으로 고른 앵커**(재정렬 당사자일 수 있다)를 지키므로 특정 줄의 픽셀 고정은 이 코드의 계약이 아니다(PU2 가 「보너스」로 적은 성질). 통째 교체 회귀는 노드 동일성·scrollTop 0 복귀로 잡힌다 |
| D2 | M1 | **오라클** — A→B 폴링 결과 대 B 새로 그리기(시계 고정) | `#dzh-app` 정규화 직렬화가 **완전히 같다** |
| D3 | M1 | 틱(시계 +61초) | 같은 노드 · `.last-activity` 글자만 변경 · scrollTop 유지 |
| D4 | M1 | 라이브 이동 흉내(마지막 카드를 맨 앞) → 틱 | 저장 순서 복원 · 같은 노드 |
| D5 | M1 | 세션 줄 클릭(패널) → 틱 | 같은 노드에 `.card-open`·`aria-current="true"` 유지 |
| D6 | M1 | 트리거에 합성 `mouseover` → 틱(글자만) → 폴링(그 세션 줄 제거) | 틱 뒤 툴팁 표시 유지 + `aria-describedby` 유지 · 제거 뒤 툴팁 숨김 |
| D7 | M1 | 경고 있는 스냅샷 · 프로젝트 0개 · 데이터 블록 파손 | `.warnings` 가 마지막 · `.empty` 문구 · 파싱 오류 문구(각각 새로 그리기와 동일) |
| D8 | M2 | 카드 `.path` 클릭 · 세션 줄 클릭 | 전자: `body.dzh-session-modal-open` · `#dzh-app.inert` · 포커스 닫기 버튼 / 후자: 모달 안 열림 · 패널 열림 |
| D9 | M2 | 모달 세션 카드 클릭 | 패널 제목 `{프로젝트} · 세션 {short_id}` · 목록 세션 줄과 모달 카드 **둘 다** `.card-open` |
| D10 | M2 | 모달 루트 클릭 | 패널 제목 = 프로젝트명(요약) · 카드와 루트 둘 다 표시 |
| D11 | M2 | 패널·모달 열림 → ESC ×2 | 1회: 패널만 닫힘 · 2회: 모달 닫힘 · 포커스가 카드 `.project-name` |
| D12 | M2 | 스크림 클릭 · 새로고침 버튼 클릭 | 전자만 닫힌다 |
| D13 | M2 | 모달 열림(세션 5, 1024) scrollLeft 300 → 폴링(뒤 세션이 작업중) | 칸 같은 노드 · 보던 카드 x ±1px(SC9) · 가장자리 클래스가 `stripHiddenSides` 와 일치 |
| D14 | M2 | 패널에 3번째 세션 → 모달 열기 / 모달에서 잘린 카드 클릭 → 패널 밀어내기 | 두 경우 모두 그 카드가 칸 안에 온전히(SC10) |
| D15 | M2 | 열린 프로젝트가 빠진 스냅샷 폴링 | 모달 열린 채 사유 문구 |
| D16 | M2 | `file://` 로 열기 | 모달 열림 · 세션 카드에 `data-panel-empty-reason`(서버 안내) · 누르면 패널 빈 상태 사유 |
| D17 | M2 | 820px 세션 카드 클릭 → 패널 닫기 | 패널이 덮는 동안 `.wrap.inert` · 닫은 뒤 모달 유지 · 포커스가 그 세션 카드 |

**순수 함수**(`stripHiddenSides`·`stripScrollLeftToReveal`·`anchoredScrollLeft`·
`projectTier1Label`·`tier1ScopeAttributes`·`projectPanelAttributes`)는 IIFE 클로저 안이라 직접
호출할 수 없다 — 테스트 훅을 제품 코드에 만들지 않고 위 시나리오가 경계값을 친다: 맨 앞/끝/중간
스크롤(D13), 이미 보임/왼쪽 잘림/오른쪽 잘림(D14), orphan·이전 작업·둘 다(D7 변형 픽스처),
서버/`file://` × 키 있음/없음/끝난 작업(D16 + 픽스처 변형).

### 10.4 수동 확인 (구현 완료 시 1회)

목업(§15)과 실물 대조 스크린샷: 1440·1024·820 × 라이트·다크, 모달 열림·패널 열림·세션 5개 가로
스크롤. `/hub` 서버에서 실제 작업 중 5분 관찰(틱 10회) — 세션 칸·모달 가로 스크롤이 그대로인지.

### 10.5 원장·래칫 — 다른 세션과의 충돌 지점

메인 체크아웃에서 다른 세션이 `tests/run.sh`(290~313·735~749·9808~9944행 부근)와
`tests/mutations.tsv` 를 고치고 있다(대시보드 셸 관문 — T22-161·163·T33·T37·T39).

| 대상 | 이 작업 | 충돌 가능성·대응 |
|------|---------|------------------|
| `tests/mutations.tsv` 머리 주석 「아래 **287**개는 … 공통 사유」 | 승급 5건으로 286(M1) → 282(M2). 사전 점검(`assert_ledger_header_citation`)이 실측과 대조하므로 **반드시** 고친다 | **높음** — 상대도 같은 줄을 고칠 수 있다. 상대 머지 뒤 리베이스하고 실측으로 다시 센다 |
| 원장 행 추가 위치 | T25 블록(기존 `T25-2xx` 행 뒤)에만 | 낮음 — 상대는 T22·T33·T37·T39 행 |
| `SOURCE_GUARD_ID_FLOOR`(457, 738행) | **올리지 않는다** — 하한이라 신규 가드로 실측이 웃돌아도 통과("올리는 것은 자유") | 상대가 735~749 를 고친다 — 건드리지 않아 충돌 0 |
| `LEDGER_EXEMPT_ROW_RATCHET`(382, 591행) | 건드리지 않는다 — 승급은 실측(327)을 내릴 뿐 | 0 |
| `LEDGER_MUTATION_ROW_FLOOR`(100, 526행) | 건드리지 않는다 — 변조행이 늘 뿐 | 0 |
| `NOTE_FAILURE_ID_LESS_RATCHET`(110, 329행) | 새 `note_failure` 전부 `T25-2xx:` 접두 → 올리지 않는다 | 상대가 290~313 을 고친다 — 0 |
| T25 구역 본문 | T25 그룹 함수 안에만 추가·개정 | 낮음 |

---

## 11. 구현 순서 (마일스톤별, 각 단계의 검증)

**M1 — 부분 갱신** (단독 배포 가능, 화면 모양 변화 0)
1. `tests/hub/test_hub_template_dom.py` 골격 + D1~D7 → `33d5cea` 템플릿에서 **실패(RED)** 확인·기록.
2. 렌더 맞대기 절(§6 알고리즘) + `appContentHtml` + `render()` 전환 + 키 3곳 → D1~D5·D7 GREEN.
3. 툴팁 옵저버 전환 + 보존 예외 → D6 GREEN.
4. 주석 개정(§9.1 M1 분) + H1⁗ 개정문.
5. `tests/run.sh` T25-107 개정 + T25-229~232 · 원장 5행(신규 4 + T25-107 승급) + 머리 주석 287→286 →
   각 변조행이 실제로 실패시키는지 확인.
6. README M1 두 곳.
7. 검증 5종(프로젝트 CLAUDE.md §4) 전부 통과.

**M2 — 카드 상세보기** (M1 위)
1. D8~D17 추가(RED).
2. CSS(§8, 연결선은 승인 4 결과대로) + 마크업(SC1) + 카드 커서 규칙 교체.
3. 렌더 함수 분리(`renderSessionContent`·`projectTier1Label`·`tier1ScopeAttributes`·
   `projectPanelAttributes`) — 카드 속성 축소, 모달 루트로 이관.
4. 모달 절(상태·렌더·앵커·드러내기·단서·열기/닫기) + 리스너(`if(!isServed){` 앞) + ResizeObserver.
5. 패널 IIFE: ESC `preventDefault` · `findOpenTargetElements` + 표시 루프.
6. 주석 M2 분 · 머리 주석 카드 상세보기 문단 · README 신설 절 + 5곳 개정 · 이관 표기 4건.
7. `tests/run.sh` 개정 7건(T25-81·105·108·127·163·218·223) + T25-107 보강 + T25-233~240 · 원장(신규 + 승급 4) + 머리 주석 286→282.
8. 검증 5종 + §10.4 수동 대조.

---

## 12. 리스크와 대안

| # | 리스크 | 완화 / 수용 근거 |
|---|--------|------------------|
| R1 | 맞대기 짝짓기 결함이 화면을 **조용히 틀리게** 그릴 수 있다 — 통째 교체에는 없던 실패 형태 | D2 오라클(맞대기 결과 = 새로 그리기)이 모든 짝짓기 오류를 잡는다. 키 중복·부재는 정확성을 해치지 않도록 알고리즘이 설계됐다(§6) |
| R2 | DOM 검사가 Chrome 없는 환경에서 SKIP → 조용한 약화 | SKIP 사유 출력. 이 저장소의 개발 머신(macOS + Chrome)에서는 항상 돈다. 정적 가드 12건이 최소 방어선을 따로 친다 |
| R3 | 글자만 바뀌어 트리거 크기가 달라지면 툴팁 위치가 몇 px 어긋난 채 남는다 | 다음 hover·스크롤에서 교정. 구조 변화는 닫으므로 엉뚱한 요소를 가리키는 일은 없다 — 수용 |
| R4 | **가로 스크롤 부활**(U 보고 3 「좌우 스크롤, 한눈에 파악 안 됨」) — 1024 패널 열림 1장 | 확정 3 의 대가. 엿보기·숨은 쪽 흐림·세션 수 배지·가로 앵커·선택 카드 드러내기로 완화. 목업 d 로 사용자 재확인(쟁점 1) |
| R5 | 모달이 목록을 덮어 다른 프로젝트로 가려면 닫고 다시 열어야 한다 — SP1 이 옛 모달을 버린 이유와 같은 성질 | 대시보드 읽기(패널)는 모달 밖에 살아 있어 SP1 의 핵심 불만("읽는 동안 목록이 사라진다")은 재발하지 않는다. 한 번의 ESC·✕·스크림으로 닫힌다 — 쟁점 3 |
| R6 | 프로젝트 최신 대시보드가 2클릭으로 멀어진다 | 확정 2 의 귀결 — 쟁점 2 로 명시 |
| R7 | 원장 머리 주석 계수 충돌(§10.5) | 래칫 상수는 건드리지 않고, 계수 한 줄만 리베이스 때 재계산 |
| R8 | Safari 는 세로 스크롤 앵커링이 없어 세션 칸에서 보던 줄이 한 줄 밀릴 수 있다 | Chrome·Firefox 는 보정(실측 Chrome). 가로(모달)는 SC9 가 모든 브라우저에서 같게 보정 |
| R9 | `.card-open` 속성에 전이를 더하는 미래 변경이 지웠다-되붙임 사이에서 전이를 발화시킨다 | 머리 주석 ③ 과 CSS 주석에 제약을 적는다(PU3) |
| R10 | 모달 열림 중 body 스크롤 잠금이 클래식 스크롤바 환경에서 폭을 스크롤바만큼 바꾼다 | 오버레이 패널과 같은 기존 성질 — 수용 |
| R11 | 앵커 보정이 사용자의 관성 스크롤 도중(30초에 한 번) 겹치면 한 번 튈 수 있다 | 렌더 빈도가 낮고 보정량은 한 칸 이하 — 수용 |
| R12 | 템플릿이 2501 → 약 2850줄 | 단일 HTML 은 문서화된 800줄 예외(PV9). 함수 50줄 상한은 지킨다 |

**검토했으나 채택하지 않은 대안**
1. **PU — morphdom·idiomorph 벤더링**(PU1 안 B): 검증된 알고리즘이지만 수백 줄 인라인 복사·
   라이선스·`file://` 제약을 떠안는다. 이 DOM 은 폼·리스너 재부착이 없어 라이브러리의 어려운 몫이
   비어 있다 — 70줄 자체 구현과 D2 오라클로 같은 신뢰를 얻는다.
2. **SC — 모달이 열려 있는 동안 세션 순서 고정**(SC9 의 대안, 승인 5): 아무것도 움직이지 않아
   단순하고 예측 가능하다. 그러나 카드 목록(작업중 먼저, SO1)과 모달의 순서가 어긋나고, 새로 작업을
   시작한 세션이 뒤쪽에 머문다. 앵커 보정은 SO1 을 지키면서 "보던 카드가 사라짐"만 없앤다.
3. **SC — body 직계 고정 오버레이**(SC1 기각안): 헤더 높이 측정 JS + 밀어내기 폭 재기술 + 오버레이
   패널 뒤 Tab 누수 수정(패널 IIFE 변경)이 따라온다.

---

## 13. 사용자에게 확인이 필요한 쟁점 (오케스트레이터가 목업과 함께 물을 것)

1. **가로 스크롤 해석(확정 3)** — 1024px 에서 패널을 열면 세션 카드가 **한 장**만 보이고 나머지는
   옆으로 넘겨야 한다(목업 d). 옛 트리에 대한 불만 「좌우 스크롤이 생겨 한눈에 파악이 안 된다」와
   같은 조건이 모달 안에서 되살아난다. 목업으로 괜찮은지 확인받는다.
2. **프로젝트 최신 대시보드가 두 번 누르는 거리** — 지금은 카드 한 번이면 열렸다. 확정 2 에 따라
   카드 → 카드 상세보기 → 프로젝트 머리 순서가 된다.
3. **모달이 목록을 덮는다** — 다른 프로젝트로 가려면 닫고(✕·Esc·바깥 클릭) 다시 연다. 대시보드를
   읽는 상세 패널은 모달 밖이라 그대로 쓸 수 있다.
4. **「세션 전체」의 범위** — 카드와 같은 필터를 거친 세션 전부(끝나고 흔적 없는 세션·12시간 넘게
   소식 없는 세션은 모달에서도 숨는다).

---

## 14. 승인 항목

1. **부분 갱신 방식** — 권고: 키 기반 자식 맞대기 **자체 구현**(PU1). 대안: morphdom·idiomorph
   인라인 벤더링 / 틱만 시간 라벨 갱신(폴링은 지금대로).
   승인하면: 30초마다 화면을 통째로 새로 그리던 것이 바뀐 글자만 고치게 되어, 세션 목록 스크롤·
   키보드 위치·작업중 반짝임이 갱신 때문에 처음으로 돌아가지 않습니다.
2. **실제 브라우저 행동 검사 도입** — 권고: `tests/hub/test_hub_template_dom.py`(헤드리스 Chrome,
   없으면 SKIP)를 추가해 T24 가 함께 돌린다(PU9). 대안: 지금까지처럼 설계·구현 단계에서만 실측하고
   자동 검사는 문자열 검사로 둔다.
   승인하면: 테스트가 실제 브라우저로 "갱신 뒤에도 같은 화면 요소가 남는지"까지 확인합니다(테스트
   시간 약 10~20초 증가).
3. **모달의 위치와 성격** — 권고: 헤더 줄 안에 붙는 비모달 대화상자로 **목록만 잠그고**, 새로고침·
   테마·사용량·상세 패널은 계속 쓸 수 있게(SC1·SC2). 대안: 화면 전체에 고정된 별도 오버레이(헤더
   높이를 코드로 재고 패널 코드도 고쳐야 함).
   승인하면: 카드 상세보기가 헤더 바로 아래, 패널이 열려 있으면 그 왼쪽에 뜨고, 떠 있는 동안에도
   패널·새로고침·테마 버튼을 그대로 쓸 수 있습니다.
4. **프로젝트와 세션 카드를 잇는 선** — 권고: 안 B(루트에서 내려온 선이 각 카드로 이어짐, 목업 a2·
   e3). 대안: 안 A(선 없음, 목업 a·e1).
   승인하면: 카드 상세보기에서 "이 프로젝트 아래 이 세션들"이라는 관계가 선으로 보입니다(카드 안
   세션 목록의 선과 같은 모양).
5. **순서가 바뀔 때의 처리** — 권고: 세션 순서는 카드 목록과 같게(작업중 먼저) 계속 갱신하되, 보고
   있던 세션 카드의 화면 위치를 지켜 준다(SC9). 대안: 카드 상세보기가 열려 있는 동안은 세션 순서를
   열 때 그대로 고정한다.
   승인하면: 다른 세션의 상태가 바뀌어 순서가 달라져도 지금 보고 있던 세션 카드가 옆으로 밀려
   화면에서 사라지지 않습니다.
6. **이름과 설명서** — 권고: 사용자에게 보이는 이름은 「카드 상세보기」(첫 요청의 표현), README 에
   "(모달)"을 함께 적고 옛 검사는 옛 기능 이름 「대시보드 모달」만 막도록 좁힌다(SC17). 대안: README 에서
   "모달"이라는 낱말을 아예 쓰지 않는다(검사 개정 불필요).
   승인하면: README 에 새 화면이 「카드 상세보기(모달)」로 소개되고, 여는 법·닫는 법·Esc 순서가
   적힙니다.

---

## 15. 목업·설계 단계 산출물

세션 스크래치패드(영구 보존 아님 — 이 문서의 표·결정이 정본이다):
`/private/tmp/claude-501/-Users-dev-private-project-coding-harness/c8888fc8-49cc-469d-9212-b88dda909232/scratchpad/hub-session-modal/`

| 파일 | 내용 |
|------|------|
| `hub-session-modal-mockup.html` | **단일 파일 갤러리**(외부 의존성 0, PNG 내장) — 현재 \| 제안 나란히 11장면 + §2.2 실측 표 |
| `proposal.html` · `current.html` | 실물 목업 — 워크트리 템플릿 사본 + 제안 CSS·마크업·JS(구현과 같은 클래스·함수명). 해시로 상태 선택(`#project=…&session=…&theme=dark&linked=1`). 서버로 열어야 패널에 대시보드가 뜬다(`project/<키>/dashboard.html` 은 설치본 허브에서 읽기 전용으로 받은 사본) |
| `png/*.png` | 장면별 캡처(1440×900·1024×768·820×700, 라이트·다크) |
| `proposal-reconcile.js` · `proposal-modal.js` · `proposal-modal.css` | 시제품 조각(§6 알고리즘·§8 규칙의 실행본) |
| `probe_*.py`·`probe_*.js`·`strip_probe.py` | §2.2 실측 프로브(제품 코드 무수정, fetch·setInterval·Date.now 가로채기) |
