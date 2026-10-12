# 허브 — 카드 상세보기 정리 7건 (PRP)

> 상태: **구현 완료(2026-09-30)** — M1 `a313cd4` · M2 `f645779` · M3 `0793335` · M4 `8844f12` · M4 검수 후속 보강 `e4b6c40`(test:) ·
> M5 문서 정리(이 문서·PRP 8개 이관 표기·`hub/README.md`·README 이미지 2장 — 커밋 제목 「docs: 허브 상세보기 정리 내용을 안내 문서에 맞춘다」).
> 설계와 달라진 점은 §17, 확정된 래칫·원장 수치는 §10.2.
> 승인(2026-09-30): §15 A~E 전부 권고안 — B 안 A(모두 뺀다) · C 320px·가용 높이 전부(상한 없음) ·
> D 글리프만 빼기 · E 진행중 단계 + 실행 줄 제목.
>
> 대상: `hub/bin/hub_template.html` 한 파일의 **렌더 계층**(렌더 IIFE·CSS·머리 주석) + 그 계약을 잠그는
> `tests/run.sh`(T25)·`tests/mutations.tsv` + `tests/hub` DOM 행동 검사 + `hub/README.md` + 관련 PRP 8개의
> 이관 표기. **스냅샷 계약(`hub_model`·`hub_project`·`hub_session`)·허브 파이썬·패널 IIFE 의 코드는 한 줄도
> 바꾸지 않는다**(결정 MX11·MX12). `commands/hub.md` 는 해당 서술이 없어 무변경(grep 0건 확인).
>
> 기준 커밋: `09b3966`(브랜치 `worktree-hub-modal-cleanup`, main 과 같다). 이 문서의 `hub_template.html:N`
> 행 번호는 전부 이 커밋 기준이다. 결정 접두 **MX** — docs/prps·README·템플릿·run.sh·원장 전수에서 0건 확인.
>
> 설계 모델: opus(디스패치 기본값 — model-routing 승격 기준 1~4 해당 없음). 목업: §16.

---

## 0. 한눈에

| 항목 | 내용 |
|------|------|
| 요구 | 카드 상세보기(#dzh-session-modal)와 카드의 7가지 정리 — ① 루트는 항상 누를 수 없게 ② 보일 세션 없는 카드는 모달을 열지 않게 ③ 루트↔세션 연결선 정렬 ④ 카드·루트의 프로젝트 진행률 제거 ⑤ 모달 높이·세션 카드 크기 확대 ⑥ 모달 세션 카드의 잘림 해제 ⑦ 실행중 칩 글리프 제거 |
| 핵심 결정 | MX1 루트는 패널 타깃이 아니다(항상) · MX2 카드는 **보일 세션이 있을 때만** 모달을 연다 — 새 표지 `data-opens-session-modal`, 드래그 셀렉터는 그대로 · MX4 카드·루트의 프로젝트 진행률 제거(서버 계약 유지) · MX6 연결선 기하를 **사용자 정의 속성 5개**에서 파생 · MX7 다이얼로그 = 가용 높이 전부 + 카드가 채움(넘치면 여전히 다이얼로그가 세로 스크롤) · MX8 카드 폭 280→**320px** · MX9 모달 한정 잘림 해제 · MX10 글리프 제거(보조기술 텍스트 유지) · MX11 패널 IIFE 코드 0줄 |
| 설계 단계 실측 | 헤드리스 Chrome 154 로 현재 템플릿 대 **시제품**(제안을 문자열 치환으로 얹은 사본, 스크래치) — 줄기/드롭 x 60/59 → 59/59, 줄기 아랫끝−버스 +31px → 0, 다이얼로그 445px → 672px(1440×900), 모달 진행중 단계 넘침 36px → 0, 실행 줄 제목 가로 넘침 141px → 0, ● 6 → 0. **미러 T25 실행**으로 깨지는 가드 10개 전수 확인, 기존 DOM 검사 25건 중 D10 1건만 실패(의도된 번복) — §2 |
| 변경 규모(추정) | 템플릿 코드 −120줄(시제품 실측 3167→3047) + 주석 개정 → 순 약 −100줄 · run.sh 약 +170/−150 · 원장 +6/−2행·재조준 7행·승급 2행 · DOM 검사 신규 모듈 약 380줄 + 기존 모듈 약 −20 · README 약 ±45 · PRP 8개 이관 표기 |
| 가드 | 재조준·개정·역전환 10 · 원장만 1 · 폐기 2 · 신설 6(T25-254~259) — §10.1 |
| 커밋 | 5개(M1~M5, §12) |
| 승인 필요 | 5건(§15) — 특히 B(주인 세션이 목록에 없는 대시보드가 허브에서 사라진다) |

---

## 1. 요구사항 요약

카드 상세보기(모달)는 도입(2026-09-23)과 결함 수정(2026-09-28) 뒤에도 사용자가 쓰며 7가지 거슬리는 점을 찾았다.
모달 머리(루트)가 어떤 경우에는 눌리고 어떤 경우에는 안 눌려 예측할 수 없고, 보일 세션이 없는 카드도 모달을
열어 머리 한 줄만 보여 주며, 루트와 세션 카드를 잇는 선이 1px 어긋나고 줄기가 버스 아래로 31px 삐져나와 가로로
넘기면 카드 사이 틈에 선 조각이 남는다. 카드와 루트의 프로젝트 진행률 3줄은 그 대시보드를 기록한 세션 줄이
이미 보여 주는 정보의 중복이고, 모달은 내용 높이만큼만 커서 답답하며, 오히려 모달 세션 카드가 카드 목록보다
좁아 진행중 단계와 실행 줄 제목을 **더 많이** 자른다. 실행중 칩의 ● 는 칩 색이 이미 말하는 것을 되풀이한다.
이 PRP 는 7건을 **템플릿 한 파일의 렌더 계층**에서 고치고, 그 결과 쓰이지 않게 된 판정 함수·상수·CSS 를
걷으며, 정적 가드·DOM 행동 검사·문서를 새 계약에 맞춘다. 서버 스냅샷과 패널 IIFE 는 건드리지 않는다.

### 1.1 요구 7건과 성공 기준

| # | 요구(원문 요지) | 성공 기준(검증 가능) | 결정 | 검사 |
|---|----------------|--------------------|------|------|
| ① | `div.session-modal-root` 는 **항상** 클릭 불가 | 어떤 스냅샷(주인 보임·주인 없음(orphan)·tier1 없음·끝난 작업·**열린 채 폴링으로 세션 0개**)에서도 루트와 자손에 `data-project-path`·`data-dashboard-key`·`data-panel-empty-reason` 0개 · 루트·제목 클릭 뒤 `body.dzh-panel-open` 없음 · 루트 계산 커서 ≠ `pointer` · `#dzh-session-modal-title` 이 `<button>` 이 아님(글자는 비지 않음) | MX1·MX3 | T25-233·T25-247 · D10 |
| ② | 메인 세션이 없어 보여 줄 게 없는 `div.card` 는 눌러도 모달이 안 열림 | `visibleSessionsOf(project).length === 0` 인 카드: `data-opens-session-modal` 없음 · `.project-name` 이 `<span>` · 계산 커서 ≠ `pointer` · 여백·경로·제목 어디를 눌러도 `body.dzh-session-modal-open` 없음 · **드래그 재정렬은 그대로**(순서·저장 둘 다) | MX2 | T25-108·T25-109·T25-256 · D18·D19 |
| ③ | 루트 `::after` 와 첫 `li::before` 선이 틀어짐, 가로 스크롤 시 더 두드러짐 | scrollLeft 0: \|줄기 x − 첫 드롭 x\| ≤ 0.5px · \|줄기 아랫끝 − 버스 윗변\| ≤ 0.5px · \|드롭 아랫끝 − 카드 윗변\| ≤ 0.5px. 끝까지 넘긴 뒤: 줄기 x 불변 · 버스 구간 안 · 줄기 아랫끝 = 버스(버스 아래 줄기 조각 0px) | MX6 | T25-257 · D20 |
| ④ | `div.card`·`div.session-modal-root` 의 `.tier1-pct`·`.tier1-active` 제거(세션 안에서 보여 주므로 중복) | 카드·루트에 프로젝트 단위 `.tier1-pct`/`.tier1-active`/`.tier1-impl` 0개 · 「이전 작업」·「주인 세션 없음」 칩 0개 · 세션 줄·모달 세션 카드의 **자기** 진행률은 그대로 | MX4·MX5 | T25-88·T25-223·T25-255 · D24 |
| ⑤ | 모달 높이를 내부 크기와 무관하게 더 크게, `li` 도 더 크게 | 다이얼로그 높이 = 모달 영역 − 16px(사용량 패널이 있으면 − `--usage-clearance`) — 세션 1개·5개 스냅샷에서 **같다** · li 높이 = 칸 높이(채움) · li 폭 320px · 내용이 넘치면 **다이얼로그만** 세로 스크롤(칸 scrollHeight = clientHeight) · 밀어내기(≥1024)·오버레이(<1024) 그대로 | MX7·MX8 | T25-258·T25-246 · D21 |
| ⑥ | 모달 세션 카드의 `.tier1-active` 가 잘림 — 상세보기가 카드보다 덜 보여 주는 건 오류 | 모달 세션 카드의 모든 `.tier1-active`(세로)·`.agent-run-title`(가로) 넘침 ≤ 0.5px · 같은 세션의 카드 목록 줄은 여전히 2줄 클램프(TC2 유지) | MX9 | T25-259·T25-148 · D22 |
| ⑦ | `span.agent-chip.agent-chip-running` 의 `span.glyph` 제거 | 목록·모달 양쪽 `.agent-chip-running .glyph` 0개 · 실행중 칩마다 `.sr-only` 「 진행 중」 1개 유지 | MX10 | T25-254·T25-93 · D23 |

### 1.2 해석 명시 (추측하지 않고 적는다)

- **① 「항상」** — 2026-09-28 개정이 만든 「그 대시보드를 여는 유일한 길일 때만 클릭」 게이트(`isRootOnlyDashboardPath`,
  결함 ③)의 세 경우(보이는 세션 0개·레거시 단일 파일·orphan)까지 전부 막는다는 뜻으로 읽는다. 사용자가 본 증상은 그
  첫 경우다(메인 세션 0개 카드 → 모달 → 루트가 눌림).
- **② 「보여줄 내용이 없는」** — 화면에 보이는 세션의 유일한 정의 `visibleSessionsOf`(T25-160·T25-234 계약)가 0개인
  경우다. `project.sessions` 가 비었는지가 아니다(완료+발췌 없음·12시간 넘은 소식 없음은 숨겨진다).
- **④** — 원문 그대로 **전부 제거**(안 A)를 권고한다. 근거로 든 「중복」이 성립하지 않는 경우(대시보드의 주인 세션이
  화면에 없는 orphan)도 함께 사라진다 — 그 귀결은 §2.6·승인 B 로 올린다.
- **⑤ 「좀 더 커도」** — 높이는 가용 높이 전부, 폭은 320px(1440 에서 4장이 그대로 보이는 최대 폭 계열)로 읽는다 — 승인 C.
- **⑥** — 「상세보기가 카드보다 덜 보여 주면 안 된다」를 원칙으로 일반화해, 모달 세션 카드 안의 **폭 의존 잘림 두 가지**
  (`.tier1-active` 2줄 클램프·`.agent-run-title` 한 줄 말줄임)를 푼다. 글자 수 상한(발췌 120·모델 10·칩 12·워크플로 18·
  실행 5줄)은 카드와 모달이 같아 원칙에 걸리지 않으므로 둔다 — 승인 E.
- **⑦** — 글리프를 빼면 실행중/종료의 **시각** 구분이 색 하나만 남는다(WCAG 1.4.1). 요청대로 빼는 것을 권고하되 그
  대가와 무비용 대안(안쪽 1px 링)을 승인 D 로 올린다.

---

## 2. 실측 (설계 단계 — 헤드리스 Chrome 154, `--window-size=1440,900` 은 안쪽 1440×813)

### 2.1 방법

- **시제품**: `scratchpad/modal-cleanup/build_proto.py` 가 저장소 템플릿을 읽어 §8·§7 의 변경을 문자열 치환으로 얹은
  사본(`proto_320.html`·`proto_360.html`·`proto_320_ring.html`)을 스크래치에만 쓴다. 치환 대상이 정확히 1건이 아니면
  멈춘다(실측 전 치환 누락 방지).
- **픽스처**: `fixtures.py` — 실제 허브 dataclass(`SessionView`·`SubagentRunView`·`Tier1Snapshot`·`ProjectView`·
  `UsageSample`)로 만든 합성 스냅샷. coding-harness 세션 5개(작업중 1 — 실행중 검수 3·끝난 구현 1·진행중 단계 설명이 긴 자기
  대시보드 / 대기 2 / 소식 없음 1 / 완료 1) · atlas 1 · **daily-brief 빈 카드**(완료+발췌 없음 1개 → 보이는 세션 0) ·
  **NotebookWiki orphan**(주인 세션이 목록에 없는 대시보드). 사용량 패널 있음(카드를 누르는 순간 허브 원래 동작대로 접혀
  `--usage-clearance` 가 67px 가 된다).
- **측정**: `measure.py`·`measure_push.py`·`probe_drag.py` — `tests/hub/template_dom_harness.run_scenario` 를 그대로
  쓴다(HTTP 서빙 → `isServed` 참). 밀어내기 폭 측정은 전이를 끈다(가상 시간이 180ms 전이를 진행시키지 않는다 — D14b 주석과
  같은 한계, GOTCHA 2).
- **가드 영향**: `mirror_t25.py` — 워크트리를 스크래치 미러로 복사(.git·.claude·__pycache__ 제외)하고 템플릿만 시제품으로
  바꿔 `tests/run.sh --only T25` 를 돌렸다(T37 이 변조 미러를 뜨는 것과 같은 방식 — run.sh 진입부가 HOME 을 샌드박스로
  바꾼다). 미러 run.sh 의 T25 조기 반환만 해제해 실패를 전수로 모았다.
- **기존 DOM 검사**: `DZH_DOM_TEST_TEMPLATE=<proto_320.html> python3 -B -m unittest tests.hub.test_hub_template_dom_modal tests.hub.test_hub_template_dom`.

### 2.2 연결선 기하 (③, coding-harness 모달, 1440×900)

| 측정 | 현재 | 제안(시제품) |
|------|------|------------|
| 줄기 x / 첫 드롭 x (scrollLeft 0) | 60 / 59 — **1px 어긋남** | 59 / 59 |
| 줄기 윗끝 → 아랫끝 / 버스 윗변 | 208 → 244 / 213 — **31px 지나침** | 132.75 → 145.75 / 145.75 — 0 |
| 드롭 아랫끝 / 카드 윗변 | 227 / 227 | 159.75 / 159.75 |
| 끝까지 넘긴 뒤(현재 최대 82px, 제안 260px) | 줄기 60 은 버스 [−23, 1145] 안이지만 아랫끝 244 > 버스 213 — 버스 아래 31px 조각이 카드 사이 틈에 보인다 | 줄기 59 ∈ 버스 [−201, 1127], 아랫끝 = 버스 — T 자 접합 |

원인(현재): 줄기의 원점은 루트 **패딩 상자** 왼끝인데, 루트 상자의 음수 여백·투명 테두리(`margin:-6px 30px 0 -10px;
border:1px`)가 그 원점을 X₀ − 9 에 두어 줄기 x = X₀ − 10 + 1 + 32 = X₀ + 23, 드롭 x = X₀ + 0 + 22 = X₀ + 22 — 1px 차이다.
줄기 길이 36px 는 어떤 기하에도 묶이지 않은 매직 넘버다(버스는 루트 아랫변 + 4px 에 있다).

### 2.3 높이·폭 (⑤)

| 측정 | 현재 | 제안 |
|------|------|------|
| 모달 영역 / 다이얼로그 높이(1440×900) | 739 / **445.44**(내용이 정함) | 739 / **672**(= 739 − 67) |
| 세션 카드 li 폭 × 높이 | 280 × 269.44 | 320 × 563.25(채움) |
| 칸 세로 scrollHeight / clientHeight | 297 / 297 | 600 / 600(칸 안 세로 스크롤 없음) |
| 1024×560(내용 > 가용 높이) 다이얼로그 scroll/client | 443 / 330(다이얼로그 스크롤) | 445 / 330(다이얼로그 스크롤) · 칸 375/375 · li 337.84(내용 높이 — 줄지 않음) |

### 2.4 한 줄에 온전히 보이는 세션 카드 수 + 엿보기 (⑤ 폭 선택의 근거)

| 뷰포트(칸 폭) | 현재 280px | **권고 320px** | 대안 360px |
|---------------|-----------|---------------|-----------|
| 1440 패널 닫힘(1366) | 4 + 218 | **4 + 58** | 3 + 270 |
| 1440 패널 열림(816) | 2 + 252 | 2 + 172 | 2 + 92 |
| 1280 닫힘(1206) | 4 + 58 | 3 + 230 | 3 + 110 |
| 1280 열림(656) | 2 + 92 | 2 + 12 | 1 + 304 |
| 1024 닫힘(950) | 3 + 94 | 2 + 306 | 2 + 226 |
| 1024 열림(400) | 1 + 128 | 1 + 88 | 1 + 48 |
| 820(746) | 2 + 182 | 2 + 102 | 2 + 22 |
| 500(426, 헤드리스 최소 폭) | 1 + 154 | 1 + 114 | 1 + 74 |

1440 이상은 `.wrap` 이 1440 에서 멈춰 1728·1920 도 1440 행과 같다. 동시 메인 세션 실측 최대는 4~5
(hub-session-modal-and-partial-update §2.3) — 320px 는 사용자의 실측 뷰포트(1440)에서 4장을 그대로 한 줄에 둔다.

### 2.5 잘림·글리프·클릭 계약 (⑥⑦②①)

| 측정 | 현재 | 제안 |
|------|------|------|
| 모달 세션 카드 `.tier1-active`(긴 진행중 단계) 넘침 / 보이는 줄 | 36px / 2줄(폭 234) | 0 / 4줄(폭 274) — 360px 대안은 3줄(폭 314) |
| 같은 세션의 카드 목록 줄 `.tier1-active` | 2줄 클램프(폭 387, 넘침 18) | 무변경(TC2 유지) |
| 모달 `.agent-run-title` 가로 넘침 | 141 · 0 · 108 · 0 px(폭 167) — 목록 줄(폭 320)은 0 | 0 전부(긴 제목 2줄) |
| `.agent-chip-running .glyph` / `.sr-only` | 6 / 6 | **0** / 6 |
| 빈 카드(daily-brief) 속성 · 제목 · 커서 · 클릭 | `data-project-path`·`data-render-key` · BUTTON · pointer · **모달 열림** | 같음 · SPAN · auto · **안 열림** |
| 빈 카드 합성 DragEvent 재정렬(dragstart→dragover→drop→dragend) | 맨 앞으로 이동·저장됨 | 같다(드래그 무영향 확인) |
| 모달을 연 채 폴링으로 세션 0개 → 루트 | `data-project-path`·`data-dashboard-key`·`data-tier1-orphan` 이 붙고 제목 클릭이 **패널을 연다** | 속성 `class` 뿐, 패널 안 열림, 모달은 유지(「화면에 보일 세션이 없습니다.」) |

### 2.6 영향 전수 — 미러 T25 · 기존 DOM 검사 · ④ 의 실제 손실

- **미러 T25**(제안 템플릿): 실패 가드 **10개** — T25-88·T25-93(`run.is_running` 4→3)·T25-105·T25-108·T25-147(+보조)·
  T25-201(`data-tooltip="` 21→**19** 확정)·T25-218·T25-223·T25-233·T25-247. 나머지 T25 는 전부 통과(T25-240·T25-246·
  T25-239·T25-12·T25-181·T25-235 포함).
- **통과했지만 틀린 이유로 통과한 것**: T25-184 와 T25-88 의 `.card[data-tier1-previous]>.tier1-pct{…}` 토큰, T25-223 의
  같은 토큰은 시제품이 **CSS 주석**에 남긴 그 문자열 때문에 통과했다. 구현이 주석을 정리하면 깨진다 — 그래서 §10.1 이 이
  토큰들을 파일 전체(주석 포함) 역검사로 돌린다(GOTCHA 1).
- **기존 DOM 검사 25건**: D10(주인 없는 경우 루트 클릭이 패널을 연다) **1건만 실패** — 이번 결정(MX1)이 뒤집는 계약이다.
  D1(포커스 유지)·D8·D11(ESC 순서·포커스 복귀)·D13(가로 앵커, 320px 카드)·D14·D15(aria-labelledby 대상)·D16·D17 포함 나머지
  24건 통과.
- **④ 가 실제로 잃는 것**: 서버는 레거시 단일 파일(`.claude/dashboard.html`)을 이미 읽지 않는다(HD7 — `hub_collect.
  _read_tier1_for_root` docstring) — 그 갈래는 템플릿의 방어 코드로만 남아 있었다. 따라서 잃는 것은 **orphan** 하나다.
  대표 경우: 세션별 대시보드는 7일 보존되지만 허브가 세션을 아는 것은 이벤트 표시 창(오늘+어제)뿐이라, **이틀 넘게 손대지
  않은 프로젝트**의 마지막 대시보드는 주인 없는 대시보드가 된다(README 「세션별 대시보드는 이벤트 표시 창 밖 세션에는 붙지
  않는다」). 지금은 그 진행률이 카드에 「주인 세션 없음」 칩과 함께 보이고 모달 루트를 누르면 열린다. 제안 뒤에는 보이지도
  열리지도 않는다(그 카드는 보일 세션이 0개라 ② 로 모달도 안 열린다). 파일과 서버의 `/project/<프로젝트 키>/dashboard.html`
  경로는 그대로다(키가 화면에 없어 실질적으로는 닿지 못한다). 메인 세션 실측으로는 지금 스냅샷의 tier1 3개가 모두 주인
  세션이 보이는 경우라 오늘 당장 사라지는 화면은 없다.

---

## 3. 설계 결정

### MX1 — 모달 루트는 패널 타깃이 아니다, 항상 (①)

- `renderSessionModalRoot` 는 패널 속성(`data-project-path`·`data-dashboard-key`·`data-panel-empty-reason`·file 모드
  `data-tooltip`)을 **어떤 경우에도** 달지 않는다. 제목은 `<button id="dzh-session-modal-title" class="project-name">` →
  `<span id="dzh-session-modal-title" class="project-name">` — 누를 것이 없는 포커스 가능 버튼은 보조기술에 거짓말이다
  (DG1~DG3·N6 과 같은 근거). 다이얼로그의 `aria-labelledby` 대상은 그대로 산다(D15 가 지킨다). 선례: 패널 제목도
  `<span id="dzh-detail-title">` 다.
- 고아가 되는 것을 걷는다(karpathy 3): `isRootOnlyDashboardPath`·`projectPanelAttributes`·`panelEmptyReason`·
  `PROJECT_FINISHED_TASK_REASON` 과 CSS `.session-modal-root[data-dashboard-key]…{cursor:pointer}`·`:hover`·
  `.session-modal-root.card-open`(루트는 이제 신원 속성이 없어 `findOpenTargetElements` 가 영영 고르지 않는다).
- **루트 상자 단순화**: hover 테두리를 위한 음수 여백·패딩·투명 테두리·모서리가 존재 이유를 잃는다 →
  `.session-modal-root{position:relative;margin:0 30px 0 0}`. 오른쪽 30px 는 따로 필요하다 — 닫기 버튼(24px, `right:14px`)이
  다이얼로그 콘텐츠 상자 안으로 17px 들어와 루트 머리 끝(`.last-activity`)과 겹치지 않게 한다. 이 단순화가 MX6 의 「루트 왼끝 =
  첫 카드 왼끝」을 구성으로 만든다(현재 +1px 은 이 상자에서 나왔다). 글자 위치는 1px 왼쪽·1px 위로 옮겨 간다(시각 식별 한계 밑).
- 기각: (a) 게이트를 남기고 조건만 좁힌다 — 「항상」에 어긋난다. (b) 루트를 비활성 버튼(`aria-disabled`)으로 — 영구히
  비활성인 컨트롤은 Tab 정지점만 늘린다(OC11 안 C 기각과 같은 이유).

### MX2 — 카드는 보일 세션이 있을 때만 모달을 연다 (②)

- `renderProject` 가 `var opensSessionModal = visibleSessions.length > 0;` 을 계산하고, 참일 때만 카드에
  `data-opens-session-modal="1"` 을 단다(`SESSION_MODAL_OPENER_ATTRIBUTE` 상수 한 곳). 클릭 리스너는
  `closest(CARD_SELECTOR)` 대신 `closest(SESSION_MODAL_CARD_SELECTOR)`(`'.card[' + SESSION_MODAL_OPENER_ATTRIBUTE + ']'`)로
  모달을 연다. **`CARD_SELECTOR = '.card[data-project-path]'` 와 카드의 `data-project-path` 는 그대로다** — 드래그 3리스너·
  `currentCardOrder`·저장 순서가 그 셀렉터를 쓴다(T25-181, 결정 U10). 커서·hover CSS 도 새 표지로 옮긴다:
  `.card[data-opens-session-modal]{cursor:pointer}`·`:hover{border-color:var(--accent)}`.
- 제목 요소: `renderProjectNameEl(project, opensSessionModal)` — 열 수 있으면 지금 그대로 `<button … aria-haspopup="dialog">`,
  아니면 `<span class="project-name">`(N6 「없는 기능을 있는 척하지 않는다」). **OC11(모든 카드 제목은 버튼) 개정** — OC11 의
  전제(「모든 카드가 무언가를 연다」)가 빈 카드에서 깨졌다. 분기 조건은 티어·`dashboard_key`·`isServed` 가 아니라 이 한 값뿐이다
  (옛 OC11 회귀 — 티어로 가르던 `? 'button' : 'span'` — 와 구분되는 지점, T25-256 가 문다). `button.project-name` 스코프 CSS 는
  그대로라 span 에는 커서·hover·포커스 링이 붙지 않는다.
- 표지를 DOM 에 싣는 이유: 커서 CSS 가 볼 수 있어야 하고, 보이는 모습(커서)과 클릭 거동이 **같은 렌더 결과 한 곳**에서 나와야
  어긋나지 않는다.
- 기각: (a) 빈 카드에서 `data-project-path` 를 뗀다 — 드래그 재정렬·순서 저장이 깨진다(오케스트레이터 지적 그대로). (b) 클릭
  순간 스냅샷에서 다시 판정 — CSS 가 모르고, 렌더와 클릭 사이 스냅샷이 바뀌면 커서와 거동이 어긋난다. (c) 제목을 버튼으로 두고
  `aria-disabled="true"` — Tab 정지점만 남는 죽은 컨트롤이다.

### MX3 — 열린 채로 세션이 0개가 되면 닫지 않는다

폴링으로 열린 모달의 보이는 세션이 0개가 되면 지금처럼 루트 + 「화면에 보일 세션이 없습니다.」를 보인다(SC15·N8·SP7 「읽던 화면을
빼앗지 않는다」 승계). 달라지는 것은 루트가 더 이상 패널을 열지 않는다는 것뿐이다(실측 §2.5 마지막 행 — 지금 이 경로가 사용자가
본 ① 증상의 두 번째 입구다). 닫힌 뒤 포커스 복귀는 그 카드의 제목이 `<button>`→`<span>` 으로 바뀌며 노드가 교체돼
(`isUnkeyedSameShape` 는 태그가 다르면 다른 노드) `isConnected` 가 거짓이라 복귀하지 않는다 — 드문 경로라 받아들인다(GOTCHA 4).

### MX4 — 카드·루트의 프로젝트 단위 진행률을 걷는다 — 안 A, 원문 그대로 (④)

- `renderProject`·`renderSessionModalRoot` 의 `renderTier1(project.tier1, …)` 호출을 지운다. 그 결과 고아가 되는 것 전부를
  걷는다: `projectTier1Label`·`tier1ScopeAttributes`·`isTier1OwnerVisible`·`TIER1_PREVIOUS_TASK_LABEL`·`TIER1_ORPHAN_LABEL`·
  `TIER1_ORPHAN_TOOLTIP`, `renderTier1` 의 두 라벨 인자와 그 안의 null 가드(남는 호출자 `renderSessionProgress` 는
  `session.tier1` 이 있을 때만 부른다), CSS `.tier1-prev-label`·`::after`·`.card[data-tier1-previous|orphan]>…` 4줄.
  `.tier1-pct`·`.tier1-active`·`.tier1-impl` 규칙은 세션 진행률이 계속 쓰므로 남는다.
- 세션 줄·모달 세션 카드의 `renderSessionProgress`(자기 대시보드 진행률)는 무변경 — 정보는 그 대시보드를 기록한 세션 아래에
  그대로 있다(사용자가 든 중복 근거). 카드에서 세 줄이 빠진 만큼 340px 고정 카드(TR4)의 세션 목록이 자리를 더 받는다.
- 「이전 작업」 라벨(GN5)은 함께 사라진다 — 그것이 막던 오해(며칠 전 진행률이 지금 것처럼 보임)는 진행률이 프로젝트가 아니라
  **그 대시보드를 쓴 세션** 아래에만 뜨게 되어 원리적으로 없어진다.
- **귀결(승인 B)**: orphan 대시보드는 허브에서 보이지도 열리지도 않는다(§2.6). 대안 **안 B** — 주인 세션이 화면에 없을 때만 카드
  (와 루트)에 진행률 한 줄과 「주인 세션 없음」 칩을 남긴다(중복이 아니므로). 누를 수는 없다(①②). 안 B 를 고르면 `isTier1OwnerVisible`·
  `projectTier1Label`(orphan 만)·`TIER1_ORPHAN_*`·`data-tier1-orphan` 톤다운 CSS 와 T25-223 의 정방향 검사 일부가 남고, T25-255·D24 가
  「orphan 일 때만 1블록」으로 바뀐다. 권고는 안 A — 사용자는 그 컴포넌트 자체를 걷자고 했고, 안 B 는 눌러도 열리지 않는 진행률을
  남긴다.

### MX5 — TC1(`.tier1-active{flex-shrink:0}`)을 걷는다 (④ 의 귀결)

TC1 은 `.tier1-active` 가 `.card`(세로 flex)의 **직계 자식**이라 짓눌리던 결함의 수정이었다. MX4 로 그 인스턴스가 사라지면
`.tier1-active` 는 블록 컨테이너(`.session-tier1`) 안에만 살아 flex 아이템이 아니다 — 선언이 효력을 잃는다. 내 변경이 만든 고아라
지운다. TC2(`display:-webkit-box`·`-webkit-line-clamp:2` 유지)는 카드 목록의 세션 줄에 그대로 유효하고 T25-148 도 그대로다.
T25-147 은 주 검사(flex-shrink:0)를 지우고 보조 검사(카드 flex 자식의 overflow:hidden 감시)의 대상 목록을 실제 카드 자식
(`project-head path sessions`)으로 좁힌다. 기각: 선언을 방어용으로 남긴다 — 지킬 대상이 없는 추측성 방어(YAGNI).

### MX6 — 연결선 기하는 단일 출처에서 파생한다 (③)

`.session-modal-body` 에 사용자 정의 속성 5개를 선언하고, 줄기·드롭·버스·칸 번짐이 전부 이 값에서 파생한다(산식 §8.1):

| 속성 | 값 | 뜻 | 쓰는 곳 |
|------|----|----|--------|
| `--session-strip-bleed` | 20px | 칸이 다이얼로그 패딩 끝까지 번지는 폭 = 칸 안쪽 패딩(짝) | 프레임 `margin`·칸 `padding`·`scroll-padding-inline` |
| `--session-strip-gap` | 12px | 세션 카드 간격 | 칸 `gap`·버스 좌우 반폭 |
| `--session-link-x` | 22px | 줄기·드롭의 x(루트·첫 카드 왼끝에서) | 줄기 `left`·드롭 `left`·첫/끝 카드 버스 |
| `--session-link-stem` | 13px | 루트 아랫변 → 버스 | 줄기 `height`·칸 `padding-top` |
| `--session-link-drop` | 14px | 버스 → 카드 윗변 | 드롭 `top`/`height`·버스 `top`·칸 `padding-top` |

- 「루트 왼끝 = 첫 카드 왼끝」은 MX1 의 루트 상자 단순화 + 번짐 짝(`margin:0 calc(-1*B)` ↔ `padding-left:B`)으로 **구성상** 성립하고,
  「줄기 아랫끝 = 버스」는 `칸 padding-top = stem + drop` 과 `버스 top = −drop` 이 같은 두 값에서 나와 성립한다. 13 + 14 = 27 은
  현재의 「루트 본문 아래 → 카드 윗변」 27px(패딩 8 + 테두리 1 + 18)과 같아 세로 리듬이 그대로다.
- 이름에 `tree-` 를 쓰지 않는다 — T25-178 이 `tree-root` 등 옛 트리 토큰을 파일 전체 0건으로 문다(`--session-tree-root-…` 는
  즉시 실패한다). 기존 어휘 `root-linked`·`session-strip-linked` 의 `link` 를 쓴다.
- 기각: (a) 목업 v1 의 땜질값(`left:31px;top:calc(100% - 8px);height:13px`) — 증상은 없애지만 루트 여백이 바뀌면 다시 어긋난다.
  (b) 줄기를 스크롤 칸 안(버스와 함께 흐름)으로 — 가로로 넘기면 루트와 줄기가 떨어진다(SC12 의 「줄기는 제자리」 의도 위반).
  (c) SVG 로 그리기 — 새 마크업·렌더 코드가 필요하고 맞대기 대상이 늘어난다.

### MX7 — 다이얼로그 높이 = 가용 높이 전부, 세션 카드는 그 높이를 채운다 (⑤)

> → **개정(2026-10)** — hub-session-row-layout-and-modal-size.md 결정 LM8 (창은 내용 높이 + 남는 세로 공간의 가운데. 넘치면 가용 높이에서 멈추고 창만 스크롤)
> → **재개정(2026-10)** — 같은 LM8 의 개정: 사용량 패널(떠 있는 컴포넌트)은 창의 자리·최대 높이에 관여하지 않는다(아래 「사용량 변형」은 소멸).
> → **재개정(2026-10, 창 위치 30%)** — 같은 LM8 의 재개정: 창은 가운데가 아니라 윗변이 영역(헤더 아래 ~ 화면 아래 16px) 높이의 30% 아래에 걸린다(길면 오프셋이 줄어 창이 영역 안에 들고, 그래도 넘치면 최대 높이에서 창만 스크롤).
> → **재재개정(2026-10, 창 위치 12.5%)** — 같은 LM8 의 재재개정: 30% 는 일반 화면에서 사실상 세로 가운데와 같은 자리여서 12.5% 로 낮췄다(화면 높이의 약 20% — 창 아랫변이 화면 세로 중앙선에 닿는 자리, 이유는 LM8).

- `.session-modal-dialog` 의 `max-height:calc(100% - 16px)` → `height:calc(100% - 16px)`(사용량 변형도 같은 변수·폴백으로
  `height`). 본문·프레임·칸을 `display:flex;flex-direction:column` 사슬로 잇고 각자 `flex:1 0 auto` — 남는 높이를 칸이 받고,
  칸의 `align-items:stretch` 가 세션 카드를 그 높이로 늘린다(SC6 의 「밑단이 가지런하다」가 다이얼로그 바닥까지 간다).
- **`flex-shrink:0` 이 하중을 진다**: 칸은 `overflow-x:auto` 라 스크롤 컨테이너이고, 스크롤 컨테이너의 자동 최소 높이는 0 이다.
  줄어들 수 있으면 내용이 넘칠 때 칸이 **자기 안에서 세로 스크롤**한다(SC6 이 기각한 「가로·세로 스크롤 칸이 겹침」). 0 이면
  칸은 내용 높이 밑으로 줄지 않고 넘침은 지금처럼 다이얼로그(`overflow-y:auto`)가 받는다(실측 §2.3 1024×560).
  → **정정(M4)**: §13 GOTCHA 7·8 — 칸의 0 은 단독 하중이 아니라 본문·프레임의 0 과 겹치는 중복 방어다(Chrome 154 실측).
- 기각: (a) 상한(`min(…, 760px)` 등) — 근거 없는 값이다. 큰 모니터에서 카드가 매우 길어지는 것은 받아들이고, 보고되면 그때
  상한을 잰다(§13-14). (b) 다이얼로그만 크게 하고 카드는 내용 높이 — 카드 아래에 빈 띠가 생겨 「답답함」 대신 「비어 보임」이
  된다. (c) `min-height` — 여전히 내용에 따라 높이가 달라진다(요구 「내부 크기와 상관없이」 위반).

### MX8 — 세션 카드 폭 280 → 320px (⑤, 승인 C)

> → **개정(2026-10)** — 폭은 고정 320px 가 아니라 같은 화면의 메인 카드(`div.card`, `#dzh-app` 그리드 트랙)와 비슷하다. 다이얼로그가
> `container-type:inline-size` 이고 본문의 `--session-card-width` 가 열 수(메인 그리드와 같은 문턱: 2열 ≥610px · 3열 ≥942px, 창 안쪽 폭 기준)를 따르되
> 폭은 **칸 안쪽 폭** 기준이다 — 2열 `max(320px, (100cqw − 간격)/2)` · 3열 `max(320px, (100cqw − 2·간격)/3)` · 1열 `max(320px, 목록 폭)`.
> 그래서 세션 2·3개가 가로 스크롤 없이 딱 들어가고 메인 카드보다 14~21px(약 3~7%) 좁다. `max-width:calc(100% - 40px)`·`min-width:0` 은 그대로.
> 실측(li / 메인 카드): 1440→447.33 / 461.33, 1024→320(열 최소폭이 걸림) / 322.66, 820→367 / 388, 600→486 / 568(엿보기가 누름).
> 한계: 열 최소폭 320px 를 지키므로 문턱 바로 위 구간(안쪽 폭 610~652px 의 2열, 942~984px 의 3열, 예: 1024 에서 세션 3개)은 최대 42px 가로로 넘친다.
> (첫 개정안은 메인 카드와 같은 폭이었으나 1440 에서 세션 3개가 42px 넘쳐 폐기.) 가드: 새 하위 가드(스페이서·flex-shrink·container-type·컨테이너 쿼리·scrollbar-width·li 폭 변수)는 T25-258 에 두고 격리 사본에서 각각 손으로 깨뜨려 발화함을 확인했다. T25-246 변조행 sed 는 li 규칙 리터럴(`flex:0 0 var(--session-card-width)`)로 갱신했다. 아래 원문은 개정 전 근거다.

`.session-strip>li{flex:0 0 320px;…}`. `max-width:calc(100% - 40px)`·`min-width:0`(결함 ② 수정, T25-246)은 그대로. §2.4 표 —
320px 는 1440(사용자 실측 뷰포트)에서 4장을 그대로 한 줄에 두고(현재와 같은 수), 패널 열림 1440·1024 에서는 360px 와 같은 수를
보인다. 360px 는 1440 닫힘에서 3장으로 줄어 세션 4개 프로젝트가 가로 스크롤을 타게 된다. 대가: 1280·1024 닫힘에서 한 장 줄고,
1280 열림은 엿보기가 12px 로 거의 사라진다(가장자리 흐림 단서 SC11 은 그대로 뜬다).

### MX9 — 상세보기는 카드보다 덜 보여 주지 않는다 (⑥, 승인 E)

> → **개정(2026-10)** — hub-session-row-layout-and-modal-size.md 결정 LM4 (진행중 단계 줄이 걷혀 진행중 단계 해제 규칙은 소멸 — 실행 줄 제목 해제만 남는다)

- 모달 세션 카드 한정 덮어쓰기 2규칙: `.session-card .tier1-active{display:block;-webkit-line-clamp:none;overflow:visible;
  overflow-wrap:anywhere}` · `.session-card .agent-run-title{white-space:normal;overflow-wrap:anywhere}`. 앞의 세 선언이 함께 필요하다 —
  Chrome 은 블록 컨테이너에도 line-clamp 를 적용한다(TC2 실측), 그래서 `display` 만 바꿔서는 클램프가 남는다(GOTCHA 7).
  `overflow-wrap:anywhere` 는 경로 같은 끊을 곳 없는 긴 토큰이 가로로 잘리는 것을 막는다.
  → **정정(M4)**: §13 GOTCHA 7·8 — 세 선언은 각각이 하중을 지는 것이 아니라 한 선언만으로도 풀리는 중복 방어다(Chrome 154 실측).
- 카드 목록의 클램프(TC1~TC5 중 남는 TC2, 340px 고정 카드 때문)는 그대로다 — 명세도 `.session-card .x`(0,2,0) > `.x`(0,1,0)로
  모달만 풀린다. 덮어쓰기 규칙은 소스 순서상 기본 `.tier1-active{` 뒤에 둔다(T25-147/148 이 첫 일치를 앵커로 쓴다, GOTCHA 6).
- 글자 수 상한(발췌 120자·모델 10·칩 12·워크플로 18·실행 5줄 + 「+N건 더」)은 카드와 모달이 같고 툴팁이 전문을 가진다 — 모달이
  덜 보여 주지 않으므로 둔다(발췌 전문 표시는 요구 밖의 개선, 후속 후보).

### MX10 — 실행중 칩의 글리프를 걷고 보조기술 텍스트는 남긴다 (⑦, 승인 D)

- `renderAgentRunRow` 의 `runningGlyph` 와 상수 `AGENT_RUN_RUNNING_GLYPH`, CSS `.agent-chip .glyph{margin-right:2px}` 를 지운다
  (둘 다 이 함수만 썼다 — 워크플로 칩(`renderWorkflowChip`)·상태 배지(`.badge .glyph`, `STATE_GLYPH`)는 무관, grep 확인).
  `.sr-only` 「 진행 중」은 그대로 — 화면 낭독기에는 지금과 같게 읽힌다. 툴팁(행 전체, `agentRunTooltipText`)의 「진행 중」도
  그대로다.
- **접근성 트레이드오프(기록)**: 시각 채널이 「글리프 + 색」에서 「색」 하나로 준다 — WCAG 1.4.1(색만으로 정보 전달 금지)에 걸린다.
  완화: 실행중 칩은 목록 맨 앞에 정렬되고(K2), 세션 배지가 「작업중」을 텍스트+글리프+색으로 말한다. 무비용 대안(승인 D 안 2):
  `.agent-chip-running{box-shadow:inset 0 0 0 1px var(--accent)}` — 모양(테두리 유무) 채널, 높이 증분 0, 새 색 토큰 0(목업 선택지 B).
  권고는 요청 그대로(안 1) — 사용자가 「스타일로 충분히 알 수 있다」고 판단했다.
- GOTCHA 2(hub-agent-runs-and-prompt-source §7.5 「실행 중 표시는 색 단독이 아니다」)를 개정 표기한다(§11.3).

### MX11 — 패널 IIFE 코드는 한 줄도 바꾸지 않는다

MX1·MX4 뒤 패널을 여는 요소는 세션 줄과 모달 세션 카드 둘뿐이다. 패널 IIFE 의 **프로젝트 단위 타깃** 처리 — `readCardTarget` 의
`.project-name` 이름 출처, `data-tier1-previous` → `#dzh-detail-note`(GN6·PV2·PV3), `findOpenTargetElements` 가 카드를 고르는
경우 — 는 그 속성을 다는 요소가 없어 **휴면**한다. 걷지 않는 이유: (1) 패널 IIFE 는 스냅샷·모달을 모르고 속성 계약만 안다
(SP1·CG10) — 그 계약의 한 갈래를 쓰는 요소가 지금 없을 뿐, 코드가 틀린 것은 아니다. (2) `#dzh-detail-note` 의 예약 자리는 패널
헤드와 대시보드 사이 38px 여백을 겸한다(PV2) — 걷으면 패널 기하를 다시 맞춰야 하고 T25-89·T25-96·T25-99 가 함께 움직인다(요구 밖의
패널 변경). 이 휴면 경로는 서버 계약 가지치기(MX12)와 같은 「프로젝트 단위 대시보드 경로」라 후속 PRP 에서 함께 걷는다. 패널 IIFE
안 **주석** 3곳(2876~2883·2909~2911·3004~3006행)은 사실과 맞게 고친다(코드 0줄).

### MX12 — 서버 계약은 유지하고(템플릿 한정), 가지치기는 후속 PRP 로 분리한다

템플릿이 더 읽지 않게 되는 스냅샷 필드: `projects[].tier1`(세션 단위 `sessions[].tier1` 은 계속 읽는다)·`projects[].dashboard_key`·
`tier1_is_previous_task`·`tier1_is_finished_task`. 서버는 여전히 이 값으로 티어(1)·마지막 활동 시각·프로젝트 대시보드 레지스트리
(`/project/<키>/dashboard.html`)를 만든다. 지금 가지치면 `hub_project`·`hub_model`·`hub_server` + tests/hub(`test_hub_project` 의
`is_project_tier1_from_finished_session_task` 6곳 등) + T25-87 등을 함께 바꿔야 하고, 승인 B 의 결과(안 B 면 orphan 필드가 계속 쓰인다)에도
달려 있다. 이번에는 템플릿 머리 주석(데이터 계약 블록)에 「템플릿은 그리지 않는다 — 후속」을 적는다.

### MX13 — 정적 가드 처분 원칙

- 뜻이 사라진 가드는 **제자리에서 역가드로 전환**한다(T25-182·T25-185 선례 — ID 유지, 되살아남 방지). 다른 역가드가 이미 덮는 것은
  **폐기**한다(T25-184 ← T25-88, T25-218 ← T25-247 + tests/hub). 요구마다 정방향 가드를 1개씩 신설한다(T25-254~259).
- 파일 전체 역검사는 **주석까지 센다**(T25-178 선례) — 걷은 식별자를 템플릿 주석에 다시 적지 않는다(설계 문서에는 적어도 된다).
  §2.6 의 「틀린 이유로 통과」가 이 규칙의 근거다.
- 반복문 안의 실패 메시지는 변수를 보간해 원장 판별자 자격(T37-13)을 못 채운다 — 원장 행이 겨누는 검사는 고정 문구 한 줄로 쓴다
  (T25-240·T25-247 관례).

### MX14 — DOM 행동 검사는 새 모듈에 둔다

`test_hub_template_dom_modal.py` 는 536줄이라 8개 시나리오를 더하면 800줄 상한을 넘는다. ① 은 기존 D10/D10b 를 한 시나리오로
고쳐 쓰고(같은 파일, 약 −20줄), ②~⑦ 은 `tests/hub/test_hub_template_dom_modal_cleanup.py`(신규, 약 380줄)에 둔다. 하네스
(`template_dom_harness.py`)는 무변경 — 풍부한 픽스처는 모듈 안에서 `dataclasses.replace` 로 만든다(D10 선례).

---

## 4. 영향 범위

| 파일 | 조치 | 이유 |
|------|------|------|
| `hub/bin/hub_template.html` | 렌더 IIFE: 함수 6개 삭제·3개 개정·상수 5개 삭제·2개 신설, 클릭 리스너 1줄 · CSS: 규칙 약 14개 삭제·약 12개 개정·4개 신설 · 머리 주석 5문단·CSS/JS 주석 개정 · 패널 IIFE 주석 3곳 | 요구 ①~⑦ 전부 |
| `tests/run.sh` | T25 가드 재조준·개정·역전환 10, 폐기 2, 신설 6 · T25 범위 문자열 · `SOURCE_GUARD_ID_FLOOR`·`LEDGER_EXEMPT_ROW_RATCHET` 와 그 주석 | 정적 계약 |
| `tests/mutations.tsv` | 신설 6행·폐기 2행·재조준 7행·승급 2행(T25-147·T25-109) · 머리 인용(바구니 계수·래칫 2종) | 원장 정책 |
| `tests/hub/test_hub_template_dom_modal.py` | D10·D10b → D10 하나(「루트는 어떤 경우에도 패널 타깃이 아니다」, 하위 5경우) | ① |
| `tests/hub/test_hub_template_dom_modal_cleanup.py` | 신규 — D18~D24 | ②~⑦ |
| `hub/README.md` | 「카드 상세보기」 절·「프로젝트 상세 패널」 절·실행중 칩·「이전 작업」·「주인 세션 없음」·「카드도 같은 판정」 서술 개정, 알려진 한계 1줄 추가, 이미지 캡션 | 문서 정합 |
| `docs/prps/*.md` 8개 | 이관 표기(원문을 지우지 않고 화살표 한 줄) | §11.3 |
| `docs/images/hub-card-multi-agent-dark.png`·`hub-sample-dark.png` | (선택) 재촬영 | 카드의 프로젝트 진행률·● 가 찍혀 있다 |
| `hub/bin/*.py`·`commands/hub.md`·`install.sh`·`rules/` | **무변경** | MX12 · grep 0건 · 상시 컨텍스트(T26) 무관 |

---

## 5. 파일 구조와 모듈 경계

템플릿 안 IIFE 경계는 그대로다 — 렌더 IIFE 는 패널을, 패널 IIFE 는 스냅샷·모달을 모른다(SP1·CG10, T25-89 가 패널 IIFE 범위의
`snapshot` 0건을 문다).

| IIFE | 이번 변경 |
|------|----------|
| 렌더 IIFE | 카드·모달 루트·실행 줄 렌더 개정, 판정 함수 삭제, 모달 열기 셀렉터 교체 |
| 패널 IIFE | **코드 0줄** — 주석 3곳만(MX11) |
| 테마·툴팁 IIFE | 0 |

DOM 속성 계약(렌더가 쓰고 누가 읽는가):

| 요소 | 속성 | 지금 | 이후 | 읽는 쪽 |
|------|------|------|------|--------|
| 카드 `.card` | `data-project-path`·`data-render-key` | 항상 | 항상(무변경) | 드래그(CARD_SELECTOR)·맞대기 |
| 카드 | `data-tier1-previous`·`data-tier1-orphan` | 조건부 | **없음**(MX4) | CSS 톤다운(삭제) |
| 카드 | `data-opens-session-modal="1"` | — | 보일 세션 ≥ 1 일 때만(MX2) | 렌더 IIFE 클릭 리스너 · CSS 커서 |
| 카드 제목 `.project-name` | 태그 | 항상 `<button aria-haspopup>` | 열 수 있으면 button, 아니면 `<span>` | 모달 포커스 복귀 · 패널(휴면) |
| 모달 루트 | 패널 속성 3종 + file 모드 툴팁 | 「유일한 길」일 때 | **없음**(MX1) | 패널 IIFE(더는 안 잡힘) |
| 모달 루트 | `data-tier1-*` | 조건부 | **없음** | — |
| 모달 루트 제목 | `id="dzh-session-modal-title"` | `<button>` | `<span>` | 다이얼로그 `aria-labelledby` |
| 세션 줄·모달 세션 카드 | `sessionRowAttributes` | 무변경 | 무변경 | 패널 IIFE |

---

## 6. 데이터 모델

- **스냅샷 JSON(`HubSnapshot`)**: 무변경. 템플릿이 읽지 않게 되는 필드 4개는 §MX12.
- **DOM 속성 계약**: §5 표.
- **연결선 기하 모델**: `.session-modal-body` 의 사용자 정의 속성 5개(§MX6 표) — 모듈(루트 렌더·칸 렌더) 사이의 명시적 계약이다.
  두 쪽이 각자 리터럴을 갖던 것이 어긋남의 원인이었다.
- **새 JS 상수**(렌더 IIFE, `CARD_SELECTOR` 바로 뒤):
  ```js
  // 카드 = 모달을 여는 조건(결정 MX2) — 보일 세션이 있는 카드만 이 속성을 단다. 드래그는 여전히
  // CARD_SELECTOR(모든 카드)를 쓴다 — 빈 카드도 순서를 바꿀 수 있어야 한다.
  var SESSION_MODAL_OPENER_ATTRIBUTE = 'data-opens-session-modal';
  var SESSION_MODAL_CARD_SELECTOR = '.card[' + SESSION_MODAL_OPENER_ATTRIBUTE + ']';
  ```

---

## 7. 인터페이스 (렌더 함수 시그니처)

```js
// ── 개정 ──
/** 진행률 3줄(제목·진행중 단계·구현 세부). 호출자는 tier1 이 있을 때만 부른다 — 세션 줄·세션 카드 전용(결정 MX4). */
function renderTier1(tier1)                                   // 전: renderTier1(tier1, prevLabelText, prevLabelTooltip) — 라벨·null 가드 삭제
/** 카드 제목 — 모달을 열 수 있을 때만 <button aria-haspopup="dialog">, 아니면 <span>(결정 MX2, N6). */
function renderProjectNameEl(project, opensSessionModal)      // 전: renderProjectNameEl(project)
/** 카드 — 보일 세션이 있을 때만 data-opens-session-modal. 프로젝트 진행률은 그리지 않는다(결정 MX2·MX4). */
function renderProject(project)                               // 시그니처 불변(T25-160·T25-230·T25-233 의 sed 앵커)
/** 모달 루트 — 누를 수 없는 머리. 제목 <span> 이 다이얼로그 aria-labelledby 대상(결정 MX1). */
function renderSessionModalRoot(project, visibleSessions)     // 시그니처 불변(T25-233 앵커) — visibleSessions 는 세션 수 배지·줄기 표시에 쓴다
/** 실행 1건 — 단계 칩(실행 중이면 강조색 + 보조기술 텍스트) + 제목 + 경과(결정 MX10). */
function renderAgentRunRow(run, nowMs)                        // 시그니처 불변, 글리프 삭제
function renderSessionProgress(session)                       // 호출만 renderTier1(session.tier1) 로

// ── 삭제(호출자가 모두 사라진다) ──
// projectTier1Label(project, visibleSessions) · tier1ScopeAttributes(project, tier1Label)
// projectPanelAttributes(project) · isRootOnlyDashboardPath(project, visibleSessions)
// isTier1OwnerVisible(project, visibleSessions) · panelEmptyReason(project, isClickable)
```

클릭 리스너(렌더 IIFE, `if(!isServed){` 앞 — T25-235 무변경): `var card = event.target.closest(SESSION_MODAL_CARD_SELECTOR);` 한 줄만
바뀐다. `openSessionModal(card.getAttribute(…), card.querySelector('.project-name'))` 는 그대로(열 수 있는 카드의 제목은 늘 버튼이다).

---

## 8. CSS 기하 산식과 규칙 (③⑤)

### 8.1 산식

기호: X₀ = 다이얼로그 콘텐츠 상자 왼끝, R = 루트 아랫변(테두리 0 이라 패딩 상자 = 테두리 상자), B·G·L·S·D = bleed·gap·link-x·stem·drop,
s = 칸 scrollLeft, w = 카드 폭, n = 카드 수, C = 칸 clientWidth.

- 가로: 루트 왼끝 = X₀(여백·테두리·패딩 0). 프레임 왼끝 = X₀ − B, 칸 = 프레임(세로 flex 늘임), 칸 패딩 B → 첫 카드 왼끝 = X₀ − s.
  **줄기 x = X₀ + L**, **첫 드롭 x = X₀ − s + L** → s = 0 에서 같다. ∎
- 버스: 첫 카드 [L, w + G/2], 가운데 [−G/2, w + G/2], 끝 카드 [−G/2, L](폭 L + G/2) → 간격 G 를 이어 첫 드롭 x ~ 끝 드롭 x 연속.
  스크롤 뒤 버스 = [X₀ + L − s, X₀ + L − s + (n−1)(w+G)] 이고 최대 s = n·w + (n−1)G + 2B − C ≤ (n−1)(w+G) − 40 (li
  `max-width:calc(100% − 40px)` 로 C ≥ w + 2B + 40) 이라 **줄기 x 는 늘 버스 안** — T 자 접합이 구성상 보장된다.
- 세로: 프레임 윗변 = R(본문 세로 flex, 간격·여백 0), 칸 패딩 윗변 = S + D → 카드 윗변 = R + S + D. 버스 윗변 = 카드 윗변 − D = R + S.
  **줄기 = [R, R + S)** → 줄기 아랫끝 = 버스 윗변. ∎ 드롭 = [R + S, R + S + D) → 드롭 아랫끝 = 카드 윗변.
- 높이(MX7): 모달 영역 M = 100vh − 헤더 높이. 다이얼로그 H = M − 16(사용량 있으면 M − `--usage-clearance`, 폴백 218).
  li 높이 = max(내용 높이, H − 2(테두리) − 28(패딩) − 루트 높이 − (S + D) − 10(칸 아래 패딩)). 1440×900 실측 M 739 · H 672 · li 563.25.

### 8.2 규칙 (제안 — 시제품이 실측한 값 그대로)

```css
/* 카드 = 모달을 여는 조건(결정 MX2) */
.card[data-opens-session-modal]{cursor:pointer}
.card[data-opens-session-modal]:hover{border-color:var(--accent)}
/* TC1 선언 삭제(결정 MX5) — TC2 세 선언은 유지 */
.tier1-active{font-size:12px;color:var(--head);margin-top:3px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}

.session-modal-dialog{…;margin:0 var(--dzh-wrap-gutter);height:calc(100% - 16px);overflow-y:auto;…}      /* max-height → height(MX7) */
body.has-usage .session-modal-dialog{height:calc(100% - var(--usage-clearance,218px))}
.session-modal-body{flex:1 0 auto;display:flex;flex-direction:column;
               --session-strip-bleed:20px;--session-strip-gap:12px;
               --session-link-x:22px;--session-link-stem:13px;--session-link-drop:14px}
.session-modal-root{position:relative;margin:0 30px 0 0}                                                 /* MX1 — 오른쪽 30px 는 닫기 버튼 자리 */
.session-strip-frame{position:relative;margin:0 calc(-1 * var(--session-strip-bleed));
               flex:1 0 auto;display:flex;flex-direction:column}
.session-strip{position:relative;display:flex;align-items:stretch;gap:var(--session-strip-gap);list-style:none;
               margin:0;padding:4px var(--session-strip-bleed) 10px;overflow-x:auto;overscroll-behavior-x:contain;
               scroll-padding-inline:var(--session-strip-bleed);flex:1 0 auto}                          /* shrink 0 이 하중을 진다(MX7) → 정정 §13 GOTCHA 8 */
.session-strip>li{flex:0 0 320px;max-width:calc(100% - 40px);min-width:0;display:flex;position:relative}  /* MX8 */
/* ⑥ 상세보기 한정 잘림 해제(MX9) — 기본 .tier1-active{ 뒤에 둔다 */
.session-card .tier1-active{display:block;-webkit-line-clamp:none;overflow:visible;overflow-wrap:anywhere}
.session-card .agent-run-title{white-space:normal;overflow-wrap:anywhere}
/* 연결선(SC12 안 B) — 기하는 .session-modal-body 의 사용자 정의 속성에서만 나온다(MX6) */
.session-strip.session-strip-linked{padding-top:calc(var(--session-link-stem) + var(--session-link-drop))}
.session-strip-linked>li::before{content:"";position:absolute;left:var(--session-link-x);
               top:calc(-1 * var(--session-link-drop));height:var(--session-link-drop);
               border-left:1px solid var(--muted);opacity:.5}
.session-strip-linked>li::after{content:"";position:absolute;top:calc(-1 * var(--session-link-drop));
               left:calc(var(--session-strip-gap) / -2);right:calc(var(--session-strip-gap) / -2);
               border-top:1px solid var(--muted);opacity:.5}
.session-strip-linked>li:first-child::after{left:var(--session-link-x)}
.session-strip-linked>li:last-child::after{right:auto;width:calc(var(--session-link-x) + var(--session-strip-gap) / 2)}
.session-strip-linked>li:only-child::after{display:none}
.session-modal-root.root-linked::after{content:"";position:absolute;left:var(--session-link-x);top:100%;
               height:var(--session-link-stem);border-left:1px solid var(--muted);opacity:.5}
```

삭제 CSS: `.card[data-project-path]{cursor:pointer}`·`:hover` · `.tier1-prev-label{…}`·`::after` · `.card[data-tier1-previous]>.tier1-pct|active` ·
`.card[data-tier1-orphan]>.tier1-pct|active` · `.agent-chip .glyph` · `.session-modal-root[data-dashboard-key],…{cursor:pointer}`·`:hover` ·
`.session-modal-root.card-open` · `.session-modal-root[data-tier1-previous|orphan]>…` 4줄. 모달 CSS 블록에는 색 리터럴 0(T25-239 그대로).

---

## 9. 삭제·개명·신설 식별자 표

| 식별자 | 종류 | 처분 | run.sh / 원장 참조(현재) → 이후 |
|--------|------|------|-------------------------------|
| `isRootOnlyDashboardPath` | JS 함수 | 삭제 | 8 / 2(T25-247·T25-233 sed) → T25-247 역검사 대상 |
| `projectPanelAttributes` | JS 함수 | 삭제 | 20 / 3(T25-105·218·223·233·247) → T25-247 역 |
| `panelEmptyReason` | JS 함수 | 삭제(`sessionPanelEmptyReason` 은 유지 — 대소문자가 달라 겹치지 않는다) | 8 / 1 → T25-105 토큰 교체·T25-247 역 |
| `PROJECT_FINISHED_TASK_REASON` | 상수 | 삭제 | 2 / 1(T25-218) → T25-247 역 |
| `isTier1OwnerVisible` | JS 함수 | 삭제 | 10 / 0(T25-223·247) → T25-223 역 |
| `projectTier1Label`·`tier1ScopeAttributes` | JS 함수 | 삭제 | 0·4 / 0 → T25-223 역 |
| `TIER1_PREVIOUS_TASK_LABEL`·`TIER1_ORPHAN_LABEL`·`TIER1_ORPHAN_TOOLTIP` | 상수 | 삭제 | 2·5 / 0 → T25-88·T25-223 역 |
| `renderTier1(tier1, prevLabelText, prevLabelTooltip)` | 시그니처 | → `renderTier1(tier1)` | T25-12(보조 함수 이름만) 무관 |
| `renderProjectNameEl(project)` | 시그니처 | → `(project, opensSessionModal)` | 0 → T25-256 |
| `AGENT_RUN_RUNNING_GLYPH`·지역 `runningGlyph` | 상수·변수 | 삭제 | 0 → T25-254 역 · T25-93 계수 4→3 |
| `.agent-chip .glyph` | CSS | 삭제 | 0 → T25-254 역 |
| `.tier1-prev-label`·`::after` | CSS | 삭제 | 6 / 0 → T25-88 역 |
| `.card[data-tier1-previous|orphan]>…` 4줄 | CSS | 삭제 | T25-88·184·223 → T25-88 역(`.card[data-tier1-`) |
| `.session-modal-root[data-*]…`·`.card-open` 7줄 | CSS | 삭제 | 3 / 1(T25-108) → T25-247 역 |
| `.card[data-project-path]{cursor:pointer}`·`:hover` | CSS | → `.card[data-opens-session-modal]…` | 2 / 1(T25-108) → T25-108 개정(옛 규칙은 역검사) |
| `.tier1-active{…;flex-shrink:0}` | CSS 선언 | 삭제 | T25-147 개정 |
| `.session-modal-root` 여백·패딩·테두리·모서리 | CSS | 단순화 | 0 |
| `.session-strip>li{flex:0 0 280px` | CSS 값 | 320px | 1 / 1(T25-246 원장 sed 리터럴) → 원장 행만 갱신 |
| 루트 제목 `<button id="dzh-session-modal-title">` | 마크업 | `<span>` | D15(무변경 통과 확인) |
| `data-tier1-previous`·`data-tier1-orphan`(렌더가 다는 것) | DOM 속성 | 렌더에서 사라짐 — 패널 IIFE 의 `TIER1_PREVIOUS_TASK_ATTRIBUTE` 읽기는 휴면으로 남는다(MX11) | T25-89(`TIER1_PREVIOUS_TASK_ATTRIBUTE` 토큰) 무변경 |
| **신설** `data-opens-session-modal`·`SESSION_MODAL_OPENER_ATTRIBUTE`·`SESSION_MODAL_CARD_SELECTOR` | DOM·JS | 신설 | → T25-256 |
| **신설** `--session-strip-bleed`·`--session-strip-gap`·`--session-link-x`·`--session-link-stem`·`--session-link-drop` | CSS 속성 | 신설 | → T25-257(T25-178 토큰과 겹치지 않음 확인) |

---

## 10. 테스트 계획

### 10.1 정적 가드 (T25, `test_hub_docs_and_constants`)

| ID | 처분 | 요구 | 검사 내용(이후) | 원장 행 |
|----|------|------|----------------|--------|
| T25-88 | **역전환** | ④ | 파일 전체(주석 포함) 0건: `tier1-prev-label`·`TIER1_PREVIOUS_TASK_LABEL`·`.card[data-tier1-`. 유지: `.detail-note{…}` 에 `#` 색 리터럴 0(G9 — 패널 안내 줄은 남는다) | 변조행 재조준 — 예: `s/\.tier1-impl{font-size:11.5px;/.tier1-prev-label{color:red}.tier1-impl{font-size:11.5px;/` |
| T25-93 | 개정 | ⑦ | `run.is_running` 참조 **3**(글리프 분기 삭제) — 주석에 이유 | 무변경(대상 hub_session.py) |
| T25-105 | 재조준 | ① | 토큰 `function panelEmptyReason(` → `function sessionPanelEmptyReason(` · 불변식 OC-A 의 무조건 else 검사를 `sessionRowAttributes()` 본문으로(남은 유일한 강제 지점) | 변조행 재조준 — `s/else attrs += ' data-panel-empty-reason/else if(emptyReason) attrs += ' data-panel-empty-reason/`(대상 유일 확인), 토큰 「무조건 else 가 아님」 |
| T25-108 | 개정 | ② | `.card[data-opens-session-modal]{cursor:pointer}` 존재 · 역: `.card[data-project-path]{cursor:pointer}` 0 · 모달 루트 커서 검사 삭제(→T25-247) · `? 'button' : 'span'` 역검사 삭제(OC11 개정 → T25-256 가 올바른 분기를 문다) | 변조행 재조준 — `s/\.card\[data-opens-session-modal\]{cursor:pointer}/…{cursor:default}/` |
| T25-109 | 재조준 | ② | README 토큰 `어느 카드든` → `보일 세션이 있는 카드`(새 README 문구). 판별자용 고정 문구 한 줄로 분리(MX13) | **승급**(면제 → 변조행, README 대상) |
| T25-147 | 개정 | ④ | 주 검사(flex-shrink:0) 삭제 · 보조 목록 → `project-head path sessions` | **승급** — 예: `.path{…}` 에 `;overflow:hidden` 추가 → 「flex-shrink/min-height 가드가 없음」 |
| T25-184 | **폐기** | ④ | (T25-88 의 `.card[data-tier1-` 0 이 덮는다) | 행 삭제 |
| T25-201 | 개정 | ④① | `data-tooltip="` 줄 수 21 → **19**(orphan 칩 툴팁·루트 file 모드 툴팁) — 주석 이력 한 줄 | 무변경 |
| T25-218 | **폐기** | ① | (템플릿·README 부분은 대상 소멸, 서버 부분은 tests/hub `test_hub_project` 가 덮고 후속 가지치기 대상) | 행 삭제 |
| T25-223 | **역전환** | ④ | 파일 전체 0건: `TIER1_ORPHAN_LABEL`·`TIER1_ORPHAN_TOOLTIP`·`isTier1OwnerVisible`·`projectTier1Label`·`tier1ScopeAttributes`·`data-tier1-orphan` · README `주인 세션 없음` 0 | 변조행 재조준 — 예: `s/var SESSION_NO_DASHBOARD_LABEL = /var TIER1_ORPHAN_LABEL = 1; var SESSION_NO_DASHBOARD_LABEL = /` |
| T25-233 | **전환** | ① | `renderProject()` 본문 패널 속성 0(유지) · `renderSessionModalRoot()` 본문에 `projectPanelAttributes(`·`data-project-path`·`data-dashboard-key`·`data-panel-empty-reason`·`<button` 0, `SESSION_MODAL_TITLE_ID` 존재 | 변조행 재조준 — `s/'<div class="session-modal-root' + linkedClass + '">'/'…' + linkedClass + '" data-dashboard-key="x">'/` |
| T25-246 | 원장만 | ⑤ | 가드 무변경(`min-width:0`) | sed 리터럴 280px → 320px |
| T25-247 | **역전환** | ① | 파일 전체(주석 포함) 0건: `isRootOnlyDashboardPath`·`projectPanelAttributes`·`function panelEmptyReason(`·`PROJECT_FINISHED_TASK_REASON`·`.session-modal-root[data-`·`.session-modal-root.card-open` | 변조행 재조준 — 식별자 하나를 주석이나 무해한 선언으로 되살리는 sed |
| **T25-254** | 신설 | ⑦ | `renderAgentRunRow()` 에 `class="glyph"` 0 · `'<span class="sr-only"> ' + AGENT_RUN_RUNNING_LABEL` 존재 · 파일 전체 `AGENT_RUN_RUNNING_GLYPH`·`.agent-chip .glyph` 0 | `s/var AGENT_RUN_RUNNING_LABEL = /var AGENT_RUN_RUNNING_GLYPH = 1; var AGENT_RUN_RUNNING_LABEL = /` → **정정(구현, M1)** — 실제 변조 sed 는 렌더 본문에 글리프 span 을 되살린다: `s/var runningClass = /var runningGlyph = '<span class="glyph"><\/span>'; var runningClass = /`(판별 토큰 「renderAgentRunRow() 본문에 글리프 span 이 되살아남」). T25-93 의 `run.is_running` 계수가 못 잡는 회귀(분기 없이 붙인 글리프)를 이 가드가 잡는다는 것을 원장이 직접 보인다 |
| **T25-255** | 신설 | ④ | `renderProject()`·`renderSessionModalRoot()` 본문에 `renderTier1(`·`project.tier1` 0 · `renderSessionProgress()` 에 `renderTier1(session.tier1)` · `function renderTier1(tier1){` | `s/      + sessionsHtml + '<\/div>';/      + renderTier1(project.tier1) + sessionsHtml + '<\/div>';/` |
| **T25-256** | 신설 | ② | `renderProject()`: `SESSION_MODAL_OPENER_ATTRIBUTE` 가 `visibleSessions.length` 조건식 안에서만 붙음 · `data-project-path` 는 무조건 · `'data-opens-session-modal'` JS 리터럴 정확히 1 · 클릭 리스너가 `closest(SESSION_MODAL_CARD_SELECTOR)` · `CARD_SELECTOR = '.card[data-project-path]'` 유지 · `renderProjectNameEl()` 에 `<span class="project-name">` 와 `aria-haspopup="dialog"` 가 함께 있고 `project.tier`·`dashboard_key`·`isServed` 0 | `s/event.target.closest(SESSION_MODAL_CARD_SELECTOR)/event.target.closest(CARD_SELECTOR)/` |
| **T25-257** | 신설 | ③ | 속성 5개 선언 각 정확히 1(`.session-modal-body{` 안) · 줄기 규칙 `left:var(--session-link-x)`·`top:100%`·`height:var(--session-link-stem)` · 드롭 `left:var(--session-link-x)`·`top:calc(-1 * var(--session-link-drop))` · 버스 `top:calc(-1 * var(--session-link-drop))` · 칸 `padding-top:calc(var(--session-link-stem) + var(--session-link-drop))` · 프레임·칸이 `--session-strip-bleed` · 역: 세 규칙에 `left`/`height` px 리터럴 0 | `s/height:var(--session-link-stem);/height:36px;/`(대상 유일) |
| **T25-258** | 신설 | ⑤ | `.session-modal-dialog{` 에 `height:calc(100% - 16px)`·`max-height` 0 · 사용량 변형 `height:calc(100% - var(--usage-clearance,218px))` · 본문·프레임·칸 `flex:1 0 auto` · `.session-strip>li{flex:0 0 320px;` | `s/height:calc(100% - 16px);overflow-y:auto;/max-height:calc(100% - 16px);overflow-y:auto;/` |
| **T25-259** | 신설 | ⑥ | `.session-card .tier1-active{` 에 `display:block`·`-webkit-line-clamp:none`·`overflow:visible` · `.session-card .agent-run-title{` 에 `white-space:normal` · 덮어쓰기 규칙이 기본 `.tier1-active{` 보다 뒤 | `s/-webkit-line-clamp:none;/-webkit-line-clamp:2;/` |

무변경 확인(미러 T25 통과): T25-12·T25-89·T25-96·T25-99·T25-106·T25-107·T25-148·T25-160·T25-161·T25-178·T25-181·T25-183·T25-230·
T25-234·T25-235·T25-236·T25-238·T25-239·T25-240. T25-90(README `이전 작업`)은 서브에이전트 실행 서술에 토큰이 남아 계속 통과한다 — GN5
라벨 서술이 사라져도 그 가드의 나머지 몫(구세대·기록기 `init`·LG1 역검사)은 유효하다.

원장 행의 sed·판별 토큰은 위가 **스케치**다 — 구현자가 `mutation_sed_is_write_safe`(평문 `s/…/…/`, 줄 번호·정규식 주소 금지)와 T37-13
판별자 자격(실패 보고 줄에서 토큰 1건)을 실측으로 맞춘다.

### 10.2 원장·래칫 (구현자가 실측으로 다시 센다)

| 항목 | 지금 | 이후(예상) | 비고 |
|------|------|-----------|------|
| T25 범위 문자열 | `T25-1~T25-253` | `T25-1~T25-259`(커밋마다 그 시점 최대) | test_desc |
| `SOURCE_GUARD_ID_FLOOR` | 511 | **515**(+6 −2) | 상수 주석에 「511 → 515」 문단 · 원장 머리 인용 「(515 — …→511→515)」 · collect_guard_ids 재현 실측 |
| 변조행 | 210 | 216(+6 신설 −2 폐기 +2 승급) | `LEDGER_MUTATION_ROW_FLOOR`(100) 무변경 |
| 면제행 | 308 | 306 | |
| 공통 사유 바구니 「아래 N개는」 | 272 | **270**(T25-147·T25-109 승급) | 원장 머리 승급 이력 문장에 한 줄 |
| `LEDGER_EXEMPT_ROW_RATCHET` | 375 | 373(권고 — 내리는 방향이라 선택, 관례대로 나란히 적는다) | 상수 주석 + 원장 머리 인용 「(373 — …→375→373)」 |
| `NOTE_FAILURE_ID_LESS_RATCHET` | 103 | 103 | 새 가드는 전부 ID 를 단다 |
| T37-15 소요 | — | 약 +38초(변조행 순증 6 × T25 1회 약 6.3초) | |

**확정값(M5, 2026-09-30 — 워킹트리에서 직접 센 값. 위 「이후(예상)」 열이 그대로 착지했다)**

| 항목 | 확정 | 센 방법 |
|------|------|--------|
| T25 범위 문자열 | `T25-1~T25-259` | run.sh `test_desc` |
| `SOURCE_GUARD_ID_FLOOR` | **515** | `collect_guard_ids` 재현 — 줄 시작이 `note_failure`·`record_failure` 인 줄의 첫 `"T…-…` ID 를 중복 없이 센 값이 515. 상수 주석 「511 → 512 → 515」·원장 머리 인용 「(515 — …→511→512→515)」와 일치 |
| 원장 데이터 행 | **522** | `tests/mutations.tsv` 에서 `#`·빈 줄을 뺀 행, 전부 8열, guard_id 유일 |
| 변조행 | **216** | 3열(mutation_sed)이 `-` 가 아닌 행 — `LEDGER_MUTATION_ROW_FLOOR`(100) 무변경 |
| 면제행 | **306** | 3열이 `-` 인 행 (216 + 306 = 522) |
| 공통 사유 바구니 「아래 N개는」 | **270** | 7열이 「S3 이전에 존재한 가드 …」로 같은 면제행 — 원장 머리 인용 「아래 270개는」과 일치 |
| `LEDGER_EXEMPT_ROW_RATCHET` | **373** | 상수 주석과 원장 머리 인용 「(373 — …→375→374→373)」이 일치. 면제행 실제 수(306) 위의 상한이다 |
| `NOTE_FAILURE_ID_LESS_RATCHET` | **103** | 무변경 — 새 가드는 전부 ID 를 달았다 |
| 신설 가드 6개 | T25-254~259 | 원장에 각 1행 등록(전부 변조행) |
| T37-15 소요 | (측정 안 함) | 전체 스위트를 돌린 메인 세션의 몫이다 |

같은 저장소에 동시 세션이 있다 — 병합 직전 main 의 마지막 T25 번호를 다시 세고 충돌하면 번호를 민다(메모리 「동시 세션 주의」).

### 10.3 DOM 행동 검사 (헤드리스 Chrome — Chrome 이 없으면 SKIP)

| ID | 모듈 | 시나리오 | 단언 |
|----|------|---------|------|
| D10(개정) | `…_dom_modal.py` | 루트는 어떤 경우에도 패널 타깃이 아니다 — 하위 5: 주인 보임 · orphan · tier1 없음 · 끝난 작업(`tier1_is_finished_task`) · **열린 채 폴링으로 세션 0개** | 루트·자손 패널 속성 0 · 루트·제목 클릭 뒤 `dzh-panel-open` 없음·`card-open` 없음 · 루트 커서 ≠ pointer · 제목 tagName ≠ BUTTON · (0개 경우) 모달 유지 + 빈 문구. D10b 흡수 |
| D18 | `…_dom_modal_cleanup.py` | 빈 카드(daily-brief) 대 세션 있는 카드 | 표지 유무 · 제목 SPAN/BUTTON(+aria-haspopup) · 커서 · 여백·경로·제목 클릭 → 빈 카드는 `dzh-session-modal-open`·`#dzh-app.inert` 없음, 있는 카드는 열림 |
| D19 | 〃 | 빈 카드 드래그 재정렬(합성 `DragEvent` + `new DataTransfer()` — 실현 가능성 실측 확인) | DOM 순서·`localStorage['dzh-project-order']` 가 바뀜 · 모달 안 열림 |
| D20 | 〃 | 연결선 기하 — 1440·1024, scrollLeft 0 / 최대, 세션 1개(only-child) 변형 | §1.1 ③ 의 세 등식(≤0.5px) · 스크롤 뒤 줄기 x 불변·버스 구간 안·줄기 아랫끝 = 버스. 의사요소 위치는 `getComputedStyle(el,'::after')` 의 left/top/height + 호스트 rect 로 계산(시제품 측정식 그대로) |
| D21 | 〃 | 다이얼로그 높이·폭 — 세션 1개 대 5개(1440×900) · 1024×560 풍부한 내용 | 두 높이 같고 = 모달 영역 − 16(사용량 없음) · li 높이 = 칸 콘텐츠 높이 · li 폭 320 · 1024×560 에서 다이얼로그 scrollHeight > clientHeight 이고 칸 scrollHeight ≤ clientHeight |
| D22 | 〃 | 긴 진행중 단계·긴 실행 제목 | 모달 `.tier1-active` 세로 넘침 ≤ 0.5·줄 수 ≥ 3 · 모달 `.agent-run-title` 가로 넘침 ≤ 0.5 · 같은 세션의 목록 줄 `.tier1-active` 는 2줄(클램프 유지) |
| D23 | 〃 | 실행중 3·종료 1 | 목록·모달 `.agent-chip-running .glyph` 0 · 실행중 칩마다 `.sr-only` 「 진행 중」 · 종료 칩엔 둘 다 없음 → **정정(구현, M1)** — 실행중 칩과 종료 칩의 색 서명(글자색·배경색)이 서로 겹치지 않는다는 단언을 더했다. 글리프를 뺀 뒤 시각 구분이 색 하나뿐이라(MX10 의 대가) 그 구분이 살아 있음을 문다 |
| D24 | 〃 | 프로젝트 tier1 이 있는 3종(주인 보임·orphan·이전 작업 플래그) | 카드·루트에 `.tier1-pct` 0 · 「이전 작업」·「주인 세션 없음」 칩 0 · 세션 줄·세션 카드의 `.session-tier1 .tier1-pct` 는 존재 |

밀어내기 폭이 걸린 단언은 전이를 끈 스타일을 먼저 넣는다(GOTCHA 2). 좁은 폭은 헤드리스 최소 폭 500(또는 820)으로 잰다(GOTCHA 3).
구현자는 RED 확인을 `DZH_DOM_TEST_TEMPLATE` 로 현재 템플릿에 돌려 D10·D18~D24 가 실패함을 먼저 본다.

### 10.4 수동 확인 (구현 완료 시 1회, 앱 내장 Chromium)

실제 허브(설치본이 아니라 워크트리 템플릿을 실데이터로 구운 사본 — 설치 금지)를 1440×900 다크에서: 연결선 확대 확인(스크롤 전후) ·
빈 카드 hover/클릭 · 모달 높이·카드 폭 · 긴 진행중 단계 · 실행중 칩 · 1024 밀어내기(ResizeObserver 재-드러내기 SC10-2 는 헤드리스로
재현 불가 — D14b 주석) · 라이트 테마.

---

## 11. 문서·주석 개정 목록

### 11.1 `hub_template.html` 주석

| 위치(09b3966) | 개정 |
|--------------|------|
| 16~20 데이터 계약 | `projects[].tier1` 문단 끝에 「템플릿은 프로젝트 단위 tier1·dashboard_key·tier1_is_previous_task·tier1_is_finished_task 를 그리지 않는다(결정 MX4·MX12) — 서버 계약은 유지, 가지치기는 후속」 |
| 84~89 `#dzh-detail-note` | 「지금 렌더는 data-tier1-previous 를 어느 요소에도 달지 않아 안내 줄은 뜨지 않는다 — 패널 IIFE 는 속성 계약만 알고 코드는 그대로다(MX11)」(토큰 `detail-note-visible` 유지 — T25-99) |
| 109~120 패널 문단 | 패널을 여는 요소 = 세션 줄·모달 세션 카드. 「모달 루트(유일한 길일 때만 …)」·「사유의 유일한 출처는 모달 루트의 …」·「2026-09-28 개정: …」 문장 교체. 토큰 `data-panel-empty-reason`·`aria-current` 유지(T25-109) |
| 122~130 모달 문단 | 카드는 보일 세션이 있을 때만 연다(MX2) · 루트는 누를 수 없는 머리(MX1) · 연결선은 사용자 정의 속성 5개(MX6) · 높이 채움(MX7) |
| 149~154 TC 문단 | TC1 은 MX5 로 걷힘, TC2 는 목록 세션 줄에 유효(T25-148), 모달만 해제(MX9) |
| CSS 289~291 `.card` 340px | 「헤더 블록(project-head+path)」 — tier1 삭제 반영 |
| CSS 293~299 카드 커서 | MX2 로 교체 |
| CSS 415~429·432~449 | TC 주석 축약, GN5·CG 주석은 규칙과 함께 삭제 |
| CSS 775~869 모달 블록 | 다이얼로그(MX7)·루트(MX1)·칸(bleed)·li(MX8)·잘림 해제(MX9, 신설)·연결선(MX6) 주석 |
| JS 1301~1307 | 새 상수 두 줄의 이유(§6) |
| JS 1341~1342·2035~2037 | 「카드의 panelEmptyReason 과 같은 관례」 → 세션 사유가 유일한 사유 경로라는 서술로 |
| JS 1652~1653 `renderAgentRunRow` | 「글리프 + 보조기술용 텍스트」 → 「강조색 + 보조기술용 텍스트(MX10)」 |
| JS 1827 | 「renderProject 와 같은 관례」 → 이 else 가 OC-A 의 **유일한** 강제 지점(T25-105) |
| JS 1904~1907·1926~1950·1993~2011·2387~2437·2464~2479 | 삭제·개정된 함수의 주석 |
| JS 2516~2520 `sessionModalBodyHtml` | 「프로젝트명 버튼」 → 「프로젝트명(span)」 |
| JS 2732~2735 클릭 리스너 | 새 셀렉터와 이유 |
| 패널 IIFE 2876~2883·2909~2911·3004~3006 | 주석만 — 패널 타깃은 세션 줄·모달 세션 카드, 프로젝트 단위 갈래는 휴면(MX11) |

주석에 걷은 식별자(§9 삭제 행)를 다시 적지 않는다 — T25-88·T25-223·T25-247 이 주석까지 센다(GOTCHA 1). 시제품은 머리 주석 111·120행과
CSS 주석 800행에 `isRootOnlyDashboardPath` 를 남겨 둔 상태였다.

### 11.2 `hub/README.md`

| 위치 | 개정 |
|------|------|
| 37 「진행률 줄」 캡션 | 세션 아래 그 세션이 기록한 대시보드의 진행률로 |
| 39 「(● = 실행 중)」 | 「(강조색 칩 = 실행 중)」 |
| 345·350·352 칩 ● 서술 | 글리프 → 강조색(보조기술에는 「진행 중」) |
| 362~367 「이전 작업」 라벨 문단 | 삭제 → 「카드에는 프로젝트 단위 진행률이 없다 — 진행률은 그 대시보드를 기록한 세션 아래에만 보인다」 |
| 400~425 「카드 상세보기」 절 | 보일 세션이 있는 카드만 연다 · 머리는 누를 수 없다 · 320px · 가용 높이 전부 · 진행중 단계·실행 제목 전문 · 연결선 |
| 429~433 패널 절 첫 문단 | 「**어느 카드든**…그 머리(프로젝트)도 같은 패널을…」 → 「**보일 세션이 있는 카드**를 누르면 카드 상세보기가 열리고, 세션 카드·세션 행을 누르면 상세 패널이 열린다」(T25-109 새 토큰) |
| 440~442 | 「카드 상세보기의 머리·」 삭제 |
| 476~488 | 「(프로젝트 요약은 그 머리에서)」 삭제 · 「**카드도 같은 판정을 받는다**」 문단 삭제 |
| 489~493 「주인 세션 없음」 문단 | 삭제(T25-223 역검사) |
| 알려진 한계 | 추가: 「주인 세션이 목록에 없는 대시보드(이틀 넘게 손대지 않은 프로젝트의 마지막 대시보드 등)는 허브에서 보이지도 열리지도 않는다 — 파일은 그대로 남는다」(승인 B 결과에 맞춰) |
| 602~604 | 「프로젝트 요약(티어 1)의 후보로만 계속 쓰인다」 → 「…허브에서는 보이지 않는다(위 한계)」 |

### 11.3 PRP 이관 표기 (원문을 지우지 않고 화살표 한 줄 — SP6 표의 관례)

| 문서 | 결정 | 표기 |
|------|------|------|
| `hub-session-modal-and-partial-update.md` | SC4 표 「모달 루트 → 패널」 행·2026-09-28 개정 문단 · SC5(루트 내용·280px) · SC6(높이) · SC7(루트 `card-open`) · SC12(기하) · SC15(루트 사유) · §2.3 표 | `→ **개정(2026-09-30)** — hub-session-modal-cleanup.md 결정 MX1(루트는 누를 수 없다)·MX2(보일 세션 있는 카드만 연다)·MX4·MX6·MX7·MX8` |
| `hub-card-gate-and-run-list-reset.md` | §4 CG1~CG3·CG6·CG8~CG12 | `→ **폐기(2026-09-30)** — 카드·루트가 프로젝트 진행률을 그리지 않는다(hub-session-modal-cleanup 결정 MX4)` |
| `hub-session-revival-and-stale-tier1.md` | GN5 · GN6 | GN5 `→ 폐기(MX4)` · GN6 `→ 휴면 — 다는 요소가 없다(MX11), 코드 유지` |
| `hub-tier1-clamp-fix-and-session-model.md` | TC1 | `→ 걷힘(MX5) — 카드 직계 인스턴스 소멸. TC2 는 유지, 모달은 MX9 로 해제` |
| `hub-agent-runs-and-prompt-source.md` | §7.5 「실행 중 표시는 색 단독이 아니다 — 글리프 ● + .sr-only」(GOTCHA 2)·§7.3 마크업 | `→ 개정(MX10) — 글리프 삭제, 시각 채널은 색, 보조기술은 .sr-only 유지(트레이드오프 기록)` |
| `hub-panel-empty-state-and-open-card.md` | OC11 · OC4 | OC11 `→ 개정(MX2) — 모달을 열 수 있는 카드만 <button>` · OC4 `→ 담체는 세션 줄·모달 세션 카드뿐(MX1)` |
| `hub-session-list-and-glow-fixes.md` | §3 CD1~CD7 | `→ 템플릿 부분 폐기(MX1·MX4), 서버 판정은 후속 가지치기 대상(MX12)` |
| `hub-unified-card-tree-ui.md` | U11 | `→ 대상 소멸(MX4)` |

### 11.4 README 이미지

`hub-card-multi-agent-dark.png`·`hub-sample-dark.png` 는 카드의 프로젝트 진행률 줄과 ● 칩을 보여 준다. M5 에서 실데이터 스냅샷(허브가
서빙 중인 `hub.html` 의 `#dzh-data` 를 읽기 전용으로 가져와)을 새 템플릿에 구워 헤드리스로 재촬영한다(설치 없이 가능 — §16 방식). 어려우면
캡션에 「이전 화면」을 적고 후속으로 돌린다.

→ **정정(구현, M5)** — 재촬영을 마쳤다. 실데이터 스냅샷이 아니라 **합성 픽스처**(중립 이름·경로)를 새 템플릿에 구워 찍었다 — §17 의 M5 항목.

---

## 12. 마일스톤 (커밋 단위 — 각 커밋이 검증 4종을 통과한다)

| # | 범위 | 가드·검사 | 커밋 제목(안) |
|---|------|----------|--------------|
| M1 | ⑦ MX10 — 글리프 제거 (+ README 39·345·350·352) | T25-93(3)·T25-254 신설 · D23 | `fix: 허브 실행중 칩에서 동그라미 표시를 뺀다` |
| M2 | ④ MX4·MX5 — 카드·루트 진행률 제거, TC1 걷기 (+ README 37·362~367·489~493·602~604) | T25-88·T25-223 역전환 · T25-184 폐기 · T25-147 개정·승급 · T25-201(21→20) · T25-255 신설 · D24 | `feat: 허브 카드와 상세보기 머리에서 겹치던 진행률을 뺀다` |
| M3 | ①② MX1·MX2·MX3 — 루트 비활성, 빈 카드 게이트 (+ README 400~407·429~433·440~442·476~488·알려진 한계) | T25-233 전환 · T25-247 역전환 · T25-105·T25-108 개정 · T25-109 재조준·승급 · T25-218 폐기 · T25-201(20→19) · T25-256 신설 · D10 개정 · D18·D19 | `fix: 허브 상세보기 머리는 누를 수 없게, 세션 없는 카드는 열리지 않게 한다` |
| M4 | ③⑤⑥ MX6~MX9 — 연결선·높이·폭·잘림 (+ README 408~414) | T25-257·T25-258·T25-259 신설 · T25-246 원장 리터럴 · D20·D21·D22 | `fix: 허브 상세보기의 연결선을 맞추고 창을 키워 잘리던 글을 다 보여 준다` |
| M5 | 문서 — PRP 8개 이관 표기 · (선택) README 이미지 재촬영 · 래칫·원장 머리 마감 확인 | `SOURCE_GUARD_ID_FLOOR`·`LEDGER_EXEMPT_ROW_RATCHET`·바구니 계수(각 커밋이 이미 맞춘 값의 최종 확인) | `docs: 허브 상세보기 정리 내용을 안내 문서에 맞춘다` |

순서 근거: M1 은 독립이라 가장 작다. M2 가 `renderSessionModalRoot` 의 진행률·톤다운 속성을 먼저 걷어야 M3 의 루트 개정이 한 번에 끝난다.
M4 는 CSS 가 대부분이라 M3 뒤 어디든 된다. 신설 가드 번호는 이 커밋 순서대로 매겼다(M1 T25-254 · M2 T25-255 · M3 T25-256 ·
M4 T25-257~259) — T25 범위 문자열이 커밋마다 실제 최대 번호와 같다. 래칫·바구니 계수는 커밋마다 그 커밋의 실측으로 맞춘다
(`SOURCE_GUARD_ID_FLOOR` 예상: M1 512 · M2 512(+1 −1) · M3 512(+1 −1) · M4 515, 바구니: M2 271 · M3 270). 문서 개정 중
README·템플릿 주석은 **그 동작을 바꾸는 커밋에 함께** 고친다 — 특히 README 토큰이 걸린 것(T25-223 의 「주인 세션 없음」 0 은 M2,
T25-109 의 새 토큰은 M3)은 가드와 같은 커밋이어야 스위트가 녹색이다. M5 는 PRP 이관 표기와 이미지만 남는다.

검증(커밋마다): `bash tests/run.sh` · `python3 -m unittest discover -s tests/hub -t .` · `python3 -m py_compile hub/bin/*.py` ·
`bash -n install.sh && bash -n hub/install.sh`. 파이썬 임포트는 `-B`(T22-138).

---

## 13. 위험·GOTCHA

1. **주석이 역가드를 속인다** — 파일 전체 0건 검사는 주석까지 센다. 시제품 미러에서 T25-184·T25-88·T25-223 의 옛 셀렉터 토큰이 CSS 주석
   덕분에 통과했다. 걷은 식별자를 템플릿 주석에 다시 적지 않는다.
2. **헤드리스 전이** — 가상 시간은 180ms `transition` 을 진행시키지 않는다(밀어내기 폭이 안 바뀐다 — 실측). 패널 열림 폭을 재는 DOM 검사는
   `*{transition:none!important}` 를 먼저 넣는다.
3. **헤드리스 최소 폭 500px** — `--window-size=375,…` 는 안쪽 500 이 된다(실측). 좁은 화면 단언은 500·820 으로.
4. **제목 태그 교체 = 노드 교체** — 보일 세션 수가 0↔1 로 바뀌면 카드 제목이 button↔span 이라 맞대기가 노드를 바꾼다. 그 순간 포커스를
   잃고, 열린 모달의 포커스 복귀 대상(`modalOpenerElement`)이 끊긴다. 드물어 받아들인다(MX3).
5. **T25-178 토큰** — 새 이름에 `tree-root`·`tree-node`·`tree-leaf`·`tree-section` 을 쓰지 않는다(`--session-link-*` 로 정했다).
6. **첫 일치 앵커** — T25-147·T25-148 은 `grep -oE '\.tier1-active\{[^}]*\}' | head -1` 로 기본 규칙을 문다. 모달 덮어쓰기
   `.session-card .tier1-active{` 는 반드시 그 뒤에 둔다.
7. **클램프 해제 3선언** — `display:block` 만으로는 Chrome 의 블록 line-clamp 가 남는다(TC2 실측). `-webkit-line-clamp:none`·
   `overflow:visible` 를 함께.
   → **정정(구현, M4 — Chrome 154.0.8037.59 실측)** — `display:block` 하나만으로도, `-webkit-line-clamp:none` 하나만으로도
   클램프가 풀린다(세로 넘침 0·5줄). `display:-webkit-box` 를 남기고 클램프 값도 2 로 두면 그대로 2줄이다. 세 선언은 블록
   컨테이너의 line-clamp 적용이 버전마다 달랐던 TC2 경험에 대비한 중복 방어이지 각각이 하중을 지는 것이 아니다 — 템플릿과
   T25-259 주석이 그렇게 적는다.
8. **`flex:1 0 auto` 의 0** — 스크롤 컨테이너(칸)의 자동 최소 높이는 0 이다. 1 로 두면 칸이 세로로 스크롤한다(SC6 위반).
   → **정정(구현, M4 — Chrome 154.0.8037.59 실측)** — 칸의 `flex-shrink` 를 1 로 돌리는 것만으로는 칸이 세로로 스크롤하지
   않는다: overflow 가 visible 인 본문·프레임은 `min-height:auto` 가 내용 높이에 묶어 두기 때문이다(세 단계를 `flex:1 1 auto`·
   `flex:1` 로 돌려도 그대로). 칸이 자기 안에서 스크롤하려면 본문·프레임·칸 셋이 모두 줄어들 수 있고 본문·프레임에 `min-height:0` 이
   더해진 사슬이어야 하며, 그 사슬에서도 칸의 0 하나만, 또는 본문·프레임의 0 둘만 남아 있으면 칸은 줄지 않는다. 세 단계의 0 은 서로
   겹치는 중복 방어이고 T25-258 이 셋 모두를 문다.
9. **루트 상자·본문 간격** — 루트에 세로 여백·테두리·패딩이 생기거나 본문 flex 에 `gap` 이 생기면 파생 등식이 깨진다(D20 이 잡는다).
10. **계수 가드** — T25-93(`run.is_running` 4→3)·T25-201(`data-tooltip="` 21→19)은 삭제가 조용히 숫자를 바꾼다. 둘 다 미러로 확정했다.
11. **판별자 자격** — 반복문 메시지는 원장 토큰으로 못 쓴다(T37-13). 원장이 겨누는 검사는 고정 문구 한 줄로.
12. **orphan 손실** — §2.6·승인 B.
13. **README 이미지 낡음** — §11.4.
14. **큰 모니터** — 상한이 없어 세로가 긴 화면에서 카드가 매우 길다. 보고되면 실측 뒤 상한을 더한다(MX7 기각안 a).
15. **T37 시간** — 약 +38초.
16. **동시 세션** — 병합 직전 가드 번호·래칫을 main 에서 다시 센다.

---

## 14. 리스크와 대안 (검토했으나 채택하지 않은 것)

| 대안 | 기각 이유 |
|------|----------|
| ④ 안 B — orphan 일 때만 카드에 진행률 한 줄 | 권고안이 아닐 뿐 승인 B 의 선택지다(§MX4). 눌러도 열리지 않는 진행률을 남긴다 |
| 패널 IIFE 의 휴면 경로(`#dzh-detail-note`·`.project-name` 이름 출처)를 지금 걷는다 | 요구 밖의 패널 기하 변경(PV2 38px)·가드 3개 연쇄. 서버 가지치기와 한 PRP 로 묶는 편이 경계가 맞다(MX11) |
| 서버 계약도 지금 가지치기 | 파이썬 3모듈 + tests/hub + T25 여러 개가 연쇄하고 승인 B 결과에 달려 있다(MX12) |
| 다이얼로그 높이 상한 | 측정 근거가 없다(MX7) |
| 카드 폭 360px | 1440 에서 4장 → 3장(§2.4) — 승인 C 의 대안으로 남긴다 |
| 연결선을 SVG 로 | 새 렌더 코드·맞대기 대상 증가(MX6) |
| 빈 카드에서 `data-project-path` 제거 | 드래그 재정렬 붕괴(MX2) |

**후속 과제(이번 범위 밖)**: ① 프로젝트 단위 대시보드 경로 가지치기 PRP — `ProjectView.tier1_is_previous_task`·`tier1_is_finished_task`·
프로젝트 `dashboard_key`·레지스트리 경로, 관련 헬퍼·tests/hub·T25-87, 패널 IIFE 의 휴면 갈래(MX11). ② orphan 대시보드 접근이 필요하면
새 진입점 설계(예: 모달에 「지난 대시보드」 카드). ③ 모달에서 발췌 전문(400자) 표시.

---

## 15. 사용자 승인 요청

오케스트레이터가 목업(§16)과 함께 묻는다. 괄호 안은 권고.

**승인 결과(2026-09-30, 사용자)**: A 승인 · B 안 A · C 320px·가용 높이 전부 · D 안 1(글리프만 빼기) · E 둘 다 — 전부 권고안.

- **A. 전체 방향** — 승인하면: 카드 상세보기 머리는 어떤 경우에도 눌리지 않고(마우스를 올려도 반응 없음), 세션이 하나도 안 보이는 카드는
  눌러도 아무 일이 없으며(순서 끌어 옮기기는 그대로), 머리와 세션 카드를 잇는 선이 정확히 맞고 옆으로 넘겨도 선 조각이 남지 않는다.
  카드와 상세보기 머리에서 프로젝트 진행률 3줄이 빠지고(각 세션 아래 진행률은 그대로), 상세보기 창이 화면 아래까지 커지며 세션 카드가
  조금 넓어진다. 상세보기에서는 진행중 단계와 실행 줄 제목이 잘리지 않고 다 보이며, 실행중 칩의 ● 가 빠진다.
- **B. 주인 세션이 목록에 없는 대시보드(안 A 권고)** — 안 A(권고, 요청 그대로): 진행률을 모두 뺀다. 잃는 것 — 이틀 넘게 손대지 않은
  프로젝트처럼 그 대시보드를 쓴 세션이 목록에서 사라진 경우, 그 마지막 진행률이 허브 어디에도 안 보이고 열 길도 없어진다(파일은 7일 남는다).
  지금 화면에서는 그런 카드가 없다. 안 B: 그런 경우에만 카드에 진행률 한 줄과 「주인 세션 없음」 표시를 남긴다(눌러서 열리지는 않는다).
- **C. 크기(320px·가용 높이 전부 권고)** — 세션 카드 폭 280→320px: 지금 쓰는 1440 화면에서 네 장이 그대로 한 줄에 보인다. 360px 로 하면 더
  넓지만 한 줄에 세 장이 된다. 높이는 창이 화면 아래(사용량 패널 위)까지 늘고 카드도 그만큼 길어진다 — 큰 모니터에서는 카드가 아주 길어질
  수 있다(상한은 두지 않는다).
- **D. 실행중 칩 표시(글리프만 빼기 권고)** — 요청대로 ● 만 빼면 실행중/종료는 칩 색으로만 구분된다(화면 낭독기는 지금처럼 「진행 중」을
  읽는다). 색 구분이 어려운 사람을 위해 실행중 칩에 얇은 안쪽 테두리를 대신 줄 수도 있다(크기 변화 없음 — 목업 선택지 B).
- **E. 상세보기 잘림 해제 범위(둘 다 권고)** — 진행중 단계와 함께 **실행 줄 제목**도 상세보기에서는 줄바꿈해 전부 보인다. 진행중 단계만 풀
  수도 있다(그러면 상세보기가 카드보다 제목을 더 자르는 것은 남는다).

---

## 16. 목업·설계 단계 산출물

스크래치패드 `…/scratchpad/modal-cleanup/`(저장소 밖):

| 파일 | 내용 |
|------|------|
| `hub-session-modal-cleanup-mock.html` | **프리뷰 목업**(단독 실행, 외부 의존성 0, 21장면) — 행: 카드 목록 · 카드 상세보기 · 루트 클릭 · 빈 카드 클릭 · 연결선 2배(스크롤 0/끝) · 1024 밀어내기(선택 표시) · 820 라이트 · 선택지 A(320/360) · 선택지 B(칩 글리프 제거/링/현재). 각 칸은 실제 템플릿(현재)·시제품(제안)을 합성 스냅샷으로 구워 헤드리스 Chrome 이 스크립트를 실행한 결과 DOM — 누르면 실제 크기 |
| `mock-full.png`·`mock-clicks.png`·`mock-detail.png` | 목업 전체 · 루트 클릭/빈 카드 클릭 · 연결선 확대와 칩 선택지 |
| `build_proto.py`·`proto_320.html`·`proto_360.html`·`proto_320_ring.html` | 시제품 빌더와 산출물 |
| `fixtures.py`·`measure.py`·`measure_push.py`·`probe_drag.py`·`mirror_t25.py`·`build_mock.py`·`shoot.py` | 실측·미러·목업 스크립트, `measure-1440.log`·`measure-1024x560.log`·`mirror-proto_320-T25.log` |

---

## 17. 구현 기록 — 설계와 달라진 점

승인된 결정 MX1~MX14 와 승인 A~E 는 구현 중 하나도 바뀌지 않았다. 아래는 구현 중 실측·검수가 드러낸 **구현 세부의 이탈**이다 — 이 문서의 원문은
그대로 두고, 해당 자리(§3 의 MX7·MX9 · §8.2 의 CSS 주석 · §10.1 의 T25-254 원장 열 · §10.3 의 D23 행 · §11.4 · §13 의 GOTCHA 7·8)에는 정정 표기를 달았다.
확정된 래칫·원장 수치는 §10.2 에 있다.

**M1 — ⑦ 글리프 (`a313cd4`)**
- 원장 T25-254 의 변조 sed 를 상수 되살리기(§10.1 스케치)에서 **렌더 본문에 글리프 span 을 되살리는 것**으로 바꿨다 — T25-93 의 `run.is_running` 계수가
  못 잡는 회귀(분기 없이 붙인 글리프)를 이 가드가 잡는다는 것을 원장이 직접 보이게 한다.
- D23 에 실행중 칩과 종료 칩의 색 서명(글자색·배경색)이 서로 다르다는 단언을 더했다 — 글리프를 뺀 뒤 시각 구분이 색 하나뿐이라(MX10 의 대가) 그 구분이 살아 있음을 문다.

**M2 — ④ 진행률·TC1 (`f645779`)**
- `isTier1OwnerVisible` 삭제를 M3 로 옮겼다 — M2 뒤에도 루트 게이트(`isRootOnlyDashboardPath`)가 그 함수를 불러, 게이트가 사라지는 M3 에서 함께 지웠다.
- T25-88 에 넷째 검사(`.session-modal-root[data-tier1-` 0건)를 더했다가 M3 에서 T25-247 이 `.session-modal-root[data-` 를 덮어 다시 뺐다 — T25-88 은 §10.1 의 셋 + `.detail-note` 색 리터럴이다.
- 안내 줄(`#dzh-detail-note`) 출처를 서술한 머리 주석과 패널 IIFE 의 안내 줄 상수 주석은, `data-tier1-previous` 를 다는 요소가 사라지는 M2 에서 함께 고쳤다.
- README 「알려진 한계」 문장은 M2 에서 임시 서술로 두고 M3 가 새 한계 항목(승인 B 의 귀결)과 함께 확정했다.

**M3 — ①② 루트·빈 카드 (`0793335`)**
- 루트 상자를 단순화(MX1)하면서 연결선의 **임시 리터럴**(줄기·드롭 x 22px · 줄기 높이 13px · 칸 위 패딩 27px)을 함께 넣었다 — 루트가 여백·패딩·테두리를 잃어 옛 값이 맞지 않게 돼서다. M4 가 속성 5개로 대체했다.
- 세션 0개로 열려 있는 모달의 빈 문구에 `margin-top:9px` 를 더했다 — 루트 상자 단순화로 사라진 옛 아랫 여백(패딩 8 + 테두리 1)을 메운다.
- `SESSION_NO_DASHBOARD_REASON` 에서 「(구세대 단일 파일은 프로젝트 요약으로만 보입니다)」 절을 뺐다 — 프로젝트 요약이 열리지 않게 돼 거짓이 됐다(패널 사유 문구가 바뀌는 사용자 가시 변경).
- D10 은 하위 5 한 시나리오가 아니라 세 테스트다: 정적 4(주인 보임·orphan·tier1 없음·끝난 작업) · 열린 채 폴링으로 세션 0개 · **file:// 모드**(§10.3 에 없던 하위 케이스 — 옛 루트가 달던
  「서버를 켜라」 사유 속성·툴팁이 사라졌음을 문다).
- README 를 §11.2 목록 밖에서도 보정했다 — 프라이버시 고지의 패널 iframe 문장(「카드를 클릭해 여는 패널 … 가장 최근 것」)과 사유 안내 문장(「다른 카드·세션 행」).
- T25-256 은 한 덩어리 검사가 아니라 고정 문구의 개별 검사 여러 줄로 나눠 썼다(원장 판별자 자격, MX13).

**M4 — ③⑤⑥ 연결선·높이·잘림 (`8844f12`)**
- GOTCHA 7·8 이 Chrome 154 실측과 달랐다(§13 에 정정): 잘림 해제는 **한 선언만으로도** 풀리고 세 겹은 중복 방어이며, 칸의 세로 스크롤은 shrink 1 만으로는 안 생기고
  조상 `min-height:auto` 때문에 **`min-height:0` 사슬**이어야 생긴다.
- T25-259 가 `overflow-wrap:anywhere` 도 문다(진행중 단계·실행 줄 제목 두 규칙 모두).
- T25-257 의 px 역검사를 넓혔다 — 줄기·드롭·버스·칸 규칙의 `left`·`right`·`width`·`height`·`top`·`padding-top` px 리터럴 0(M3 의 임시 리터럴 셋이 대상).
- 새 헬퍼 `extract_flattened_css_rules`(T25-257~259 공용) — 여러 줄에 걸친 CSS 규칙을 한 줄로 펴서 뽑는다.
- 빈 상태의 9px 는 속성 체계(§8.1) **밖의 리터럴**로 남는다 — 연결선 기하가 아니라 세션이 없을 때의 문구 간격이라 D21 이 문다.
- M3 검수 후속 2건이 이 커밋에 함께 들어갔다 — ① `tests/hub/test_hub_template_dom_modal.py` 의 D10 정적 프로브에 **케이스 격리**(열린 패널 닫기)를 넣었다: 한 케이스의
  루트·제목 클릭이 패널을 열었다면(결함 재현) 그 잔재가 다음 케이스의 사전조건 실패로 번져 원인이 흐려지므로, 케이스 사이에 열린 패널을 닫는다. ② D18·D19 가 카드를
  `data-project-path` 가 아니라 `data-render-key` 로 찾는다 — 검사 대상인 그 속성이 사라진 카드도 찾아야 프로브가 죽지 않고 설계된 단언(드래그·순서 저장에서 빠진다)에 닿는다.

**검수 후속 보강 (M4 검수 뒤 — 커밋 `e4b6c40`(test:) 에 담겼다)**
- T25-257: 속성 5개 선언을 파일 전체에서도 센다(규칙 안 계수만으로는 다른 규칙·@media 의 재선언을 못 잡는다) + 첫 카드·끝 카드·가운데 카드 버스 규칙의 정방향 단언(꼬리 없음·끝 드롭에 닿음·이웃 이음새).
- D20: 버스 양끝(첫 카드 버스 왼끝 = 첫 드롭 x · 끝 카드 버스 오른끝 = 끝 드롭 x)과 이웃 조각 이음새(앞 카드 버스 오른끝 = 뒤 카드 버스 왼끝, 세션 3개 이상) 단언을 더했다.
- 창 높이 주석의 「위쪽 16px」을 「아래쪽 16px」로 바로잡았다(코드 `height:calc(100% - 16px)` 는 무변경).

**M5 — 문서 (이 커밋)**
- §11.3 의 8개 문서에 이관 표기를 달았다(원문 보존). **§11.3 표 밖 추가 표기: SC16·OC5·ST26·U13** — 모달 PRP 의 SC16(`max-height` → `height`), OC 문서의 OC5(기존 화살표
  「담체가 카드 → 모달 루트」가 거짓이 됨), `hub-session-tree-and-per-session-dashboards.md` 의 ST26(개정 화살표의 「프로젝트 요약은 모달 루트」), `hub-unified-card-tree-ui.md` 의
  U13(「프로젝트·세션 두 진입점을 모두 유지」). ST26 때문에 이관 표기를 단 문서는 표의 8개에 `hub-session-tree-and-per-session-dashboards.md` 를 더한 9개다(이 PRP 자신까지 손댄 파일은 10개).
- §11.4 의 재촬영은 **합성 픽스처**로 했다(실데이터 스냅샷을 가져오지 않는다 — 저장소가 GitHub 에 올라가므로 실제 경로·프롬프트·세션 ID 를 이미지에 남기지 않는다).
  이름·경로는 중립값(`demo-app` 등, `/Users/dev/projects/…`)이고, 두 이미지는 원본과 같은 크기(2560×1520 · 455×357)·구도(다크 테마, 카드 3장과 펼친 사용량 패널 / 카드 한 장)다.
  PNG 는 IHDR·IDAT·IEND 청크만 갖는다(메타데이터 없음).
  **문구도 전부 새로 지어냈다** — 1차 촬영은 실제 프롬프트·작업 제목의 어순과 말투를 살린 가공본이라 검수 지적으로 버리고, 가상의 화분 가게 주문 앱·안내 문구 사이트·메모 CLI 를 꾸며
  검수 관점 이름·발췌(존댓말 요청문)·진행률 제목과 단계 설명·실행 줄 제목·예약 실행 프롬프트·사용량 수치와 시각·세션 ID(무작위 UUID)를 실제 작업과 닮지 않게 다시 지어 두 이미지를 다시 구웠다.
- README 캡션(30·35·37~43행)은 M1·M2 가 이미 고쳐 둔 문구가 새 이미지와 맞아 그대로다 — 다만 「병렬 검수」 불릿의 관점 나열은 새 이미지의 제목에 맞춰 (금액 계산·화면 상태·보안·요구사항 충족)으로 바꿨다.
  잔여 서술 8곳(소개문·패널 절 키 서술·작업중 bloom·열린 세션 표시·티어 표 「얻는 것」·로딩 중 iframe 불릿·밀어내기 불릿·사유 안내 문장의 세션 종류)을 실제 동작에 맞췄다. 뒤의 셋은 M5 검수 지적이다:
  프로젝트 카드는 패널 내용을 바꾸지 못하므로 「다른 카드를 눌러」는 「세션 행·세션 카드를 눌러」로, 티어 3 은 세션이 없으므로(`_project_tier`) 사유 안내 문장의 「티어 2·3 프로젝트의 세션」은
  「티어 2 프로젝트의 세션이나 기록기 `init` 을 부르지 않은 세션」으로 고쳤다.
