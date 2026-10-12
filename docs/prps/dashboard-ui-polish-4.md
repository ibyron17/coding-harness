# PRP — dashboard-ui-polish-4

허브/프로젝트 대시보드 UI 결함 4건. 브라우저 이중 URL · pulse 디자인 순화 · 보기 토글 버튼
통합 · `head-row` 고정.

- **작업 경로**: 전체 경로(설계 → 구현 → 검수). 3개 이상 파일 · 공개 DOM 계약(정적 노드 id) 변경 해당.
- **규모**: Medium — 파일 7개(코드 3 · 문서 2 · 검증 2), 신규 의존성 0.
- **브랜치**: `worktree-dashboard-ui-fixes`
- **기준 커밋**: `fcf65fe`

---

## 1. 요구사항 요약

허브(`/hub`)와 프로젝트 대시보드(`/dashboard`)의 화면 결함 4건을 고친다. ①「자동 발행」이
브라우저에 URL 을 두 개 여는 문제를 **절차 문서의 모호성**으로 규정해 하나만 열도록 못
박고, ② 최근 도입한 두 pulse 애니메이션(허브 작업중 카드 · 대시보드 진행중 단계)의 진폭·주기·
경계 처리를 **하나의 모션 언어**로 순화하며, ③ 보기 전환 버튼 2개를 테마 버튼과 같은 관용구의
토글 버튼 1개로 합치고, ④ 트리 보기에서 스크롤 시 사라지던 헤더 행을 `sticky` 로 고정한다.
넷 다 사용자가 실제로 보고 불편을 말한 지점이며, 새 기능이 아니라 **기존 표현의 교정**이다.

### 문제 → 목표

| # | 지금 | 목표 |
|---|------|------|
| 1 | 워크트리 세션에서 자동 발행이 `http://localhost:{허브포트}/hub.html` 과 `file://…/{세션ID}.html` 두 URL 을 브라우저에 함께 띄운다 | 브라우저 열기 호출은 **정확히 1회**, 대상은 3-a 가 정한 열기 대상 URL 하나뿐 |
| 2 | 두 pulse 가 opacity 를 `.3↔1`·`.35↔1` 로 2.4s 마다 왕복해 "깜빡임"으로 읽힌다. 하드 엣지(3px 막대의 반경 클램프 · 카드 테두리와 겹치는 2px inset 링)가 겹쳐 있다 | 진폭 `.6↔1` · 주기 4s · 하드 엣지 제거 — 두 파일이 **같은 두 숫자**를 공유한다 |
| 3 | `#dzh-view-cards`·`#dzh-view-tree` 2버튼 + `role="group"` 래퍼 + `aria-pressed` | `#dzh-view-toggle` 1버튼. `#dzh-theme-toggle` 과 **문자 그대로 같은 관용구**(아이콘 2개 + CSS 스와핑 + 상태 속성 + 동작 라벨) |
| 4 | `.head-row` 가 문서 흐름에 있어 스크롤하면 화면 밖으로 나간다(트리 모드에서 특히 치명적 — 전폭 섹션이 길다) | `position:sticky;top:0` — 카드·트리 두 모드 모두 |

---

## 2. 영향 범위

| 파일 | 액션 | 이유 | 요구 |
|---|---|---|---|
| `commands/dashboard.md` | UPDATE | §3·§3-a·§4 의 "URL 두 개" 모호성 제거 + 단일 열기 불변식 명문화 | 1 |
| `commands/dashboard_template.html` | UPDATE | `ol.steps li.active::before` 의 진폭·주기·그라데이션 + 주석 | 2 |
| `hub/bin/hub_template.html` | UPDATE | `card-working` glow · 보기 토글 통합 · `.head-row` sticky | 2·3·4 |
| `hub/README.md` | UPDATE | 작업중 카드 서술(링→bloom) · 보기 토글 서술(2버튼→1버튼) | 2·3 |
| `tests/run.sh` | UPDATE | T25-59 유지 · T25-65/T22-163/T22-164/T25-159 개정 · T22-166/T25-169/T25-170 신설 · 상수 4종 · T25 그룹 함수에 한계 표기 신설 | 전부 |
| `tests/mutations.tsv` | UPDATE | 개정 4행 면제→변조 승급 · 신설 3행 등록 · 헤더 인용 6종 갱신 | 전부 |
| `README.md` | 손대지 않음 | 커맨드 표의 줄 수 인용(`dashboard` 1405·`dashboard_template.html` 766)은 **이미 낡았다**(실측 1355·778). `rules-docs-sync` PRP 의 이관 항목이라 이번 회차 밖이다 — 언급만 하고 고치지 않는다 | — |

**손대지 않는 것(명시)**: `hub/bin/hub.py` · `hub/bin/hub_daemon.py` · `hub/bin/hub_hook.py` ·
`~/.claude/settings.json` 훅. 조사 결과 브라우저를 여는 파이썬 경로는 URL 을 **하나만** 조립해
넘긴다(`hub.py:78-124` 의 배타적 분기, `hub_daemon.py:355-370`) — 결함은 코드가 아니라 절차
문서에 있다. 코드에 손대면 요구 1의 원인과 무관한 변경이 된다.

---

## 3. 요구 1 — 브라우저 이중 URL

### 3.1 원인 (조사 결론)

**URL 을 두 개 여는 코드는 없다.** 두 개를 여는 주체는 `commands/dashboard.md` 「자동 발행」을
수행하는 **메인 세션 모델 자신**이고, 원인은 그 절차가 **의미 있는 URL 두 개를 동시에 손에
쥐게 만드는 구조**다.

```
§3   URL 확정과 포트 각인   → 「대시보드 URL」 (보고·각인용)
§3-a 열기 대상 확정         → 「열기 대상 URL」 (브라우저용)
§4   브라우저 열기          → "여기서 <URL> 은 3-a 가 정한 열기 대상 URL 이다"
§5   보고                   → "대시보드: {대시보드 URL}"  ← §3 의 것
```

허브 서버가 살아 있으면 두 값이 **반드시** 갈린다. 그리고 **워크트리 격리 세션에서는 이
어긋남이 항상 발생한다**: §2-a 의 기동 명령 `trap 'exit 0' TERM; python3 -m http.server …` 이
워크트리 Bash 관문에 항상 거부되어(실측: "runs a string through trap, which can't be verified
to stay inside the worktree") 티어 2 로 강등되고, 그 결과가 정확히 사용자가 말한
「서버 URL + 로컬 경로 URL」 조합이다.

절차를 엄격히 따르면 1개만 열린다(실측: `navigate` 1회 호출 시 `tabs_context` 가 탭 1개만
보고). 즉 **문서가 두 URL 을 다 "열 수 있는 것"처럼 남겨 둔 것**이 흔들림의 원인이고, 고칠
곳은 그 서술이다.

부차 후보: §4-1 의 "탭 선택 도구를 함께 제공하면 navigate 직후 전면으로 올리는 호출을 한 번만
더 한다" — Claude Desktop Browser pane 에서 그 "호출"이 무엇인지 문서가 특정하지 않아, 모델이
`navigate` 재호출로 해석하면 탭이 하나 더 생긴다. 함께 못 박는다.

### 3.2 설계 — 단일 열기 불변식

**결정 U1**: 「자동 발행」의 브라우저 열기는 **정확히 1회**이고 대상은 §3-a 의 열기 대상 URL
**하나뿐**이다. §3 의 대시보드 URL 은 **보고·각인 전용**이며 절대 열지 않는다. 두 값이 다른
것은 **정상**이다(허브 생존 시 · 티어 2 강등 시).

**결정 U2**: 같은 사실을 §3·§3-a·§4 세 곳에 나눠 적던 것을 **§4 한 곳으로 모은다.** §3 의
괄호와 §3-a blockquote 의 중복 문장을 지워 그 자리를 만든다 — 지금은 셋이 서로를 가리키느라
"어느 것이 진짜 여는 것인가"가 흐려져 있다.

**결정 U3**: §4-1 의 "전면으로 올리는 호출"을 **탭 선택 계열 도구 1회**로 한정하고,
`navigate` 재호출이 그에 해당하지 않음을 명시한다.

### 3.3 편집 지점 (정확한 위치)

| 위치 | 편집 | 방향 |
|---|---|---|
| §3 말미 (`이 URL 이 **대시보드 URL** 이다(…)` 줄) | 괄호 `(보고·각인용 — 실제로 브라우저에 여는 URL 은 아래 3-a 가 별도로 정한다)` 삭제 | **−** |
| §3-a blockquote 첫 문장 | `3번이 확정한 것은 **대시보드 URL**(보고·각인용)이다. 이 단계는 **브라우저로 열 URL** 만 따로 정한다.` → `이 단계는 **브라우저로 열 URL** 하나만 정한다.` | **−** |
| §4 도입부 (`여기서 <URL> 은 …` + 다음 문단) | U1 불변식 문장으로 교체(아래 문안) | **+** |
| §4-1 두 번째 하위 불릿 | U3 문안으로 교체 | ≈ |

§4 도입부 목표 문안(구현자는 자구를 다듬되 **세 요소를 모두 남긴다**):

> 여는 것은 3-a 가 정한 **열기 대상 URL 하나뿐**이다 — 3번의 **대시보드 URL** 은 보고·각인
> 전용이라 열지 않는다(둘이 다른 것이 정상이다). **이 절차 전체에서 브라우저 열기 호출은
> 성공하든 실패하든 1회다.** 아래 순서로 한 번씩만 시도하고, 성공하면 즉시 5번으로 간다 —
> 재시도·루프 없이, 실패를 에러로 보고하지 않는다.

세 요소 = (a) 대상은 하나, (b) 대시보드 URL 은 열지 않는다, (c) 열기 호출은 총 1회.

### 3.4 바이트 예산 (경성 제약)

`commands/dashboard.md` 는 현재 **95,973 B** 이고 `tests/run.sh` 의
`DASHBOARD_MD_BUDGET_BYTES=95973` 과 **정확히 같다 — 헤드룸 0 이다.** T22-163 은 초과 시
`record_failure` + `return 1`(그룹 즉시 중단)이다.

- **목표: 순증 ≤ 0 B.** 위 표의 두 삭제(합계 약 200 B — 한글 1자 = 3 B)가 §4 추가분(약
  120~150 B)을 덮는다.
- 구현 후 `wc -c < commands/dashboard.md` 를 반드시 실측하고, 값이 95,973 미만이면
  `DASHBOARD_MD_BUDGET_BYTES` 를 **그 값으로 내린다**(래칫을 조이는 방향 — 프로젝트
  CLAUDE.md §3 「내리는 것은 자유」).
- **상수를 올리지 않는다.** T22-163 주석이 "설계 상한은 96,000B" 라고 못 박아 헤드룸이
  구조적으로 27 B 뿐이고, 그 이상은 설계 상한 자체와 충돌한다.
- T26(상시 컨텍스트 55,457 B 래칫)은 `CLAUDE.md`·`rules/README.md`·`rules/common/*.md`·
  `rules/workflow/*.md` 만 센다 — `commands/dashboard.md` 는 **대상이 아니다**. 이번 작업에서
  T26 은 움직이지 않는다.

### 3.5 배포 계약 — 「템플릿 파일」 불변식과의 관계

`commands/dashboard.md` 「템플릿 파일」 절의 불변식:

> 이 템플릿의 HTML/CSS/JS 는 이 문서(`dashboard.md`)를 고치는 어떤 작업도 단 한 바이트
> 건드리지 않는다. 템플릿 자체를 바꿔야 하면 `commands/dashboard_template.html` 을 직접
> 편집한다.

**충돌하지 않는다.** 이 불변식은 **방향성** 규칙이다 — "`dashboard.md` 수정이 템플릿 수정을
유발하지 않는다". 이번 회차의 요구 1(문서)과 요구 2(템플릿)는 **서로 독립한 두 요구**이고,
템플릿을 고치는 근거는 요구 2 자신이지 요구 1 이 아니다. 불변식의 후단("템플릿 자체를 바꿔야
하면 직접 편집한다")이 정확히 이 경우를 허용한다.

**구현 규칙(불변식 준수의 기계적 증거)**: 요구 1 커밋과 요구 2 커밋을 **분리한다.** 요구 1
커밋의 diff 에 `commands/dashboard_template.html` 이 등장하면 안 된다. 그러면 "dashboard.md 를
고쳤더니 템플릿도 바뀌었다"는 형태가 커밋 단위로 성립하지 않는다.

---

## 4. 요구 2 — pulse 디자인 순화

### 4.1 현재 상태와 "세련되지 않음"의 실체

커밋 `094ea41` 가 도입한 두 모션:

```css
/* commands/dashboard_template.html L144-148 */
ol.steps li.active{position:relative;background:var(--accent-soft)}
ol.steps li.active::before{…width:3px;border-radius:8px 0 0 8px;background:var(--accent);
                           animation:dz-step-active-pulse 2.4s ease-in-out infinite}
@keyframes dz-step-active-pulse{0%,100%{opacity:.3}50%{opacity:1}}

/* hub/bin/hub_template.html L327-331 */
.card.card-working{border-color:var(--accent);box-shadow:var(--shadow),0 0 18px -4px var(--accent)}
.card.card-working::after{…box-shadow:inset 0 0 0 2px var(--accent);
                          animation:card-working-glow 2.4s ease-in-out infinite}
@keyframes card-working-glow{0%,100%{opacity:.35}50%{opacity:1}}
.card.card-open.card-working::after{box-shadow:inset 0 0 0 3px var(--accent)}
```

세 가지가 겹쳐 "촌스럽다"를 만든다:

1. **진폭이 너무 크다.** `.3→1`·`.35→1` 은 65~70 %p 스윙이다. 신호가 절반 이상 사라졌다가
   돌아오므로 시야 주변부에서 "깜빡임(flicker)"으로 지각되고, 눈이 계속 끌려간다 — 스캔
   **보조** 신호가 아니라 경고등이 된다.
2. **주기가 짧다.** 2.4 s 는 사람의 안정 호흡 주기(3.5~5 s)보다 빨라 "숨쉬기"가 아니라
   "점멸"의 대역에 있다.
3. **하드 엣지가 겹친다.**
   - 대시보드: 폭 3 px 에 `border-radius:8px` 라 CSS 반경 축소 규칙(한 변의 반경 합이 변
     길이를 넘으면 f = 3/8 로 전부 축소)이 걸려 3 px 반경으로 클램프된다 — 의도한 "옅게 둥근
     끝"이 아니라 **둥근 막대기**로 읽히고, 그 하드한 위·아래 끝이 행의 `border-bottom` 과
     충돌한다.
   - 허브: `.card.card-working` 의 accent 테두리(1 px) **위에** `::after` 의 accent inset
     링(2 px)이 겹쳐 같은 색 하드 링이 2겹이다. 그 2겹 중 안쪽 것만 opacity 가 왕복하니
     렌더링 아티팩트처럼 보인다.

**사용자 확인 (2026-09-08, 설계 승인 시점)** — pulse 값 `.6`·`4s` 는 **제안대로 승인**됐다.
다만 사용자가 지목한 촌스러움의 실체는 위 3종 중 **③ 하드 엣지**, 그중에서도
**「`.card.card-working` 의 테두리가 너무 두껍다」** 였다(원문). 실측하면:

- `.card{border:1px solid var(--line)}` 에 `.card.card-working{border-color:var(--accent)}` 가
  얹혀 accent 테두리 **1 px**, 그 위에 `::after{box-shadow:inset 0 0 0 2px}` 하드 링 **2 px**
  → 시각적 총 두께 **3 px**
- `.card.card-open.card-working::after{inset 0 0 0 3px}` 조합에서는 **4 px**

아래 (b) 의 bloom 교체가 하드 링을 없애 accent 테두리 1 px 만 남기므로 방향은 일치한다.
**요구 2 구현 시 이 지점(두께 축소)이 최우선 수용 기준이다** — 진폭·주기 조정은 부차적이다.

### 4.2 채택안 — "저진폭 숨쉬기(breathe)" 단일 모션 언어

**결정 D5**: 두 파일이 **같은 두 숫자**를 쓴다 — 진폭 하한 `.6`, 주기 `4s`. 값이 갈리면 두
화면(허브 카드 → 상세 패널 안 대시보드)이 나란히 보일 때 리듬이 어긋난다. 이 둘은 실제로
동시에 보인다(허브 상세 패널이 대시보드를 iframe 으로 띄운다).

**결정 D6**: 애니메이션되는 요소에서 **하드 경계를 제거한다.** 움직이는 것은 "빛"이어야지
"막대"·"링"이어서는 안 된다.

#### (a) 대시보드 — `ol.steps li.active::before`

```css
ol.steps li.active{position:relative;background:var(--accent-soft)}
ol.steps li.active::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
  background:linear-gradient(180deg,transparent,var(--accent) 22%,var(--accent) 78%,transparent);
  animation:dz-step-active-pulse 4s ease-in-out infinite}
@keyframes dz-step-active-pulse{0%,100%{opacity:.6}50%{opacity:1}}
@media (prefers-reduced-motion:reduce){ol.steps li.active::before{animation:none;opacity:1}}
```

- `border-radius:8px 0 0 8px` **삭제**. 세로 그라데이션이 위·아래 끝을 투명으로 페이드시키므로
  하드한 끝 자체가 없어진다.
- **부수 효과가 하나 해결된다**: 원 주석이 `border-radius:8px` 를 넣은 이유는 PiP 압축뷰의
  `body.dz-pip ol.steps li.active{border-radius:8px}` 를 바가 뚫지 않게 하려던 것이었다.
  투명한 끝은 어떤 모서리도 뚫지 않으므로 그 보정 자체가 불필요해진다. 주석에서 그 근거
  문단을 지우고 새 근거로 바꾼다.
- **채널 수는 건드리지 않는다.** `li.active` 는 지금 굵은 글씨 · `--head` 색 · `.num` 반전 ·
  `.chip` 반전 · `--accent-soft` 밴드 · 좌측 바로 6채널이다. 밴드는 `prefers-reduced-motion`
  폴백의 본체(T22-164 계약의 정신)이고 `.num`/`.chip` 반전은 이 파일의 기존 관용구다 —
  **모션 채널만 순화하고 정적 채널은 손대지 않는다**(수술적 변경).

#### (b) 허브 — `.card.card-working`

```css
.card.card-working{border-color:var(--accent);box-shadow:var(--shadow),0 0 18px -4px var(--accent)}
.card.card-working::after{content:"";position:absolute;inset:0;border-radius:inherit;
  pointer-events:none;box-shadow:inset 0 0 14px -6px var(--accent);
  animation:card-working-glow 4s ease-in-out infinite}
@keyframes card-working-glow{0%,100%{opacity:.6}50%{opacity:1}}
.card.card-open.card-working::after{box-shadow:inset 0 0 20px -4px var(--accent)}
@media (prefers-reduced-motion:reduce){.card.card-working::after{animation:none;opacity:1}}
```

- 하드 링 `inset 0 0 0 2px` → **확산 inset bloom** `inset 0 0 14px -6px`. 하드 링 역할은
  이미 있는 `.card.card-working{border-color:var(--accent)}` 가 단독으로 맡는다(링 2겹 → 1겹).
- `card-open` 조합의 판별: 두께 2 px→3 px 대신 **bloom 을 깊고 넓게**(`20px -4px`). 1 px
  두께 차이는 눈으로 잴 수 없었고, 지금은 판별자가 하나 더 있다 — `card-open` 단독은
  **정적**이고 `card-open + card-working` 은 **숨쉰다**. 모션 유무가 실질 판별자다.
- **레이아웃 영향 0**: `box-shadow` 만 바꾸므로 `.card{height:340px}` 도 `border-width` 도
  움직이지 않는다. (`border-width` 를 굵히는 안은 `*{box-sizing:border-box}` 때문에 카드
  **내부** 폭을 줄여 텍스트 리플로우를 유발하므로 기각했다.)
- `@keyframes card-working-glow` **이름 유지**(T25-65 계약). `.card.card-working{` 셀렉터
  토큰도 유지된다.

### 4.3 채택하지 않은 안

| 안 | 기각 이유 |
|---|---|
| 모션 전면 제거(정적 신호만) | 사용자가 「은은한 pulse」를 명시적으로 선택한 결정 D3 을 되돌리는 것이다. 요구는 "세련되게"이지 "없애라"가 아니다 |
| `transform:scale` 기반 링 확대·축소 | 컴포지터 친화적이지만 `.card{overflow:hidden}` 에 잘려 안쪽으로만 자라 "떨림"으로 읽힌다. 이득 없이 위험만 는다 |
| 대시보드 `li.active` 의 정적 채널(밴드·`.num`/`.chip` 반전) 축소 | 요구 범위 밖이고, 밴드를 지우면 `prefers-reduced-motion` 환경에서 신호가 통째로 사라진다 |
| 진폭 `.5`·주기 `3s` | 방향은 같으나 근거가 임의적이다. `.6`(스윙 40 %p — 깜빡임 대역 아래)·`4s`(호흡 대역 중앙)는 왜 그 값인지 말할 수 있다 |

### 4.4 검증할 수 없는 것 (정직한 경계)

"세련되어 보이는가"는 기계가 판정하지 못한다. 이 절의 근거는 **왜 지금이 촌스러운가**에
대한 기전 설명(진폭·주기·하드 엣지 3종)이고, 그 기전을 각각 제거했다는 것까지만 검증
가능하다. 착지 후 사용자 눈으로 확인받는다.

`linear-gradient(180deg,transparent,…)` 의 회색 프린지 우려: CSS Images 명세가 그라데이션
보간을 **premultiplied alpha** 로 규정하므로 `transparent`(=`rgba(0,0,0,0)`)를 지나도 검은
프린지가 생기지 않는다. 대상 환경이 Chromium 계열(Claude Code 내장 브라우저)이라 명세대로
동작한다 — 그래도 수동 확인 항목에 넣는다.

---

## 5. 요구 3 — 보기 토글 버튼 통합

### 5.1 따라야 할 관용구 — `#dzh-theme-toggle`

`hub_template.html` 의 테마 토글은 **4요소 관용구**다. 그대로 복제한다.

| 요소 | 테마(현행) | 보기(설계) |
|---|---|---|
| 마크업 | `<button id="dzh-theme-toggle" class="icon-btn theme-toggle" type="button" aria-label="다크 테마로 전환" data-tooltip="다크 테마로 전환">` + SVG 2개 | `<button id="dzh-view-toggle" class="icon-btn view-toggle" type="button" data-view-mode="cards" aria-label="트리 보기로 전환" data-tooltip="트리 보기로 전환">` + SVG 2개 |
| 상태 속성 | `:root[data-theme]` | `#dzh-view-toggle[data-view-mode]` |
| CSS 아이콘 스와핑 (3줄) | `.theme-toggle .theme-icon-sun{display:none}` / `:root[data-theme="dark"] .theme-toggle .theme-icon-moon{display:none}` / `…sun{display:inline}` | `.view-toggle .view-icon-cards{display:none}` / `.view-toggle[data-view-mode="tree"] .view-icon-tree{display:none}` / `.view-toggle[data-view-mode="tree"] .view-icon-cards{display:inline}` |
| JS 적용 함수 | `applyTheme(theme)` — 속성 3개(`data-theme`·`aria-label`·`data-tooltip`) | `applyViewModeButton(mode)` — 속성 3개(`data-view-mode`·`aria-label`·`data-tooltip`) |
| 라벨 규약 | **동작**을 말한다 — 보이는 아이콘·라벨은 "지금"이 아니라 **전환될 대상**(결정 Y4) | 동일 — 카드 모드에서 **트리 아이콘** + "트리 보기로 전환" |
| 순환 | `THEME_CYCLE = ['light','dark']`, `indexOf+1 % length` | `VIEW_MODE_CYCLE = [VIEW_MODE_CARDS, VIEW_MODE_TREE]`, 같은 식 |

**결정 V1 — 상태 속성은 `:root` 가 아니라 버튼 자신에 둔다.** 테마가 `:root[data-theme]` 를
쓰는 이유는 테마가 문서 전역의 색 토큰을 바꾸기 때문이다. 보기 모드는 CSS 가 아니라 JS
(`renderProjectEntry` 분기)가 소비하므로 전역 CSS 훅이 필요 없고, 필요한 유일한 CSS 소비자는
아이콘 스와핑 하나뿐이다. 전역 속성을 새로 만드는 것은 필요 없는 확장성이다(YAGNI).

**결정 V2 — 마크업에 `data-view-mode="cards"` 를 정적 기본값으로 적는다.** 테마 버튼이
`aria-label` 정적 기본값을 마크업에 갖고 JS 가 즉시 교정하는 것과 같은 형태다. JS 실행 전
1프레임 아이콘 불일치(저장값이 `tree` 인 경우)는 `<head>` 사전 스크립트를 만들 만한 비용이
아니다 — 테마가 그 스크립트를 가진 이유는 **페이지 전체 색**의 FOUC 였다.

### 5.2 마크업 (현행 `hub_template.html` L671-690 → 교체)

```html
<button id="dzh-view-toggle" class="icon-btn view-toggle" type="button" data-view-mode="cards"
        aria-label="트리 보기로 전환" data-tooltip="트리 보기로 전환">
  <svg class="view-icon-cards" viewBox="0 0 24 24" … aria-hidden="true" focusable="false">
    <!-- 기존 dzh-view-cards 의 rect 4개 그대로 -->
  </svg>
  <svg class="view-icon-tree" viewBox="0 0 24 24" … aria-hidden="true" focusable="false">
    <!-- 기존 dzh-view-tree 의 rect 3개 + path 2개 그대로 -->
  </svg>
</button>
```

- `.view-toggle-group`(`role="group" aria-label="보기 방식"`) 래퍼는 **삭제**한다. 버튼이
  하나면 그룹이 없다.
- 아이콘 path 는 **한 획도 바꾸지 않는다** — 기존 두 SVG 를 그대로 옮긴다(lucide 유래,
  출처 표기가 `<style>` 앞 머리 주석에 있다).

### 5.3 CSS

```css
/* 삭제 */
.view-toggle-group{display:inline-flex;gap:4px}
.view-toggle[aria-pressed="true"]{color:var(--accent-ink);border-color:var(--accent);background:var(--accent-soft)}

/* 신설 — 테마 아이콘 스와핑(L481-483)과 같은 3줄 관용구.
   보이는 아이콘은 "지금"이 아니라 "전환될 대상"이다(결정 Y4). */
.view-toggle .view-icon-cards{display:none}
.view-toggle[data-view-mode="tree"] .view-icon-tree{display:none}
.view-toggle[data-view-mode="tree"] .view-icon-cards{display:inline}
```

기본(속성 없음·`cards`) → `.view-icon-tree` 가 보인다 = "트리로 갈 수 있다". `tree` →
`.view-icon-cards` 가 보인다. 속성이 통째로 없는 상태(JS 이전)도 `cards` 와 같은 화면이 되어
**빈손 상태가 없다**(테마의 `data-theme` 설계와 같은 성질).

### 5.4 JS

```js
// 상수 — L1077-1079 VIEW_MODE_* 옆
var VIEW_MODE_CYCLE = [VIEW_MODE_CARDS, VIEW_MODE_TREE];
var VIEW_MODE_ACTION_LABEL = {cards:'트리 보기로 전환', tree:'카드 보기로 전환'};

// 참조 — L1110-1111 두 줄을 한 줄로
var viewToggleButton = document.getElementById('dzh-view-toggle');

// L1754-1757 applyViewModeButtons → applyViewModeButton
// 정적 노드는 속성만 갱신한다(불변식 H1⁗) — applyTheme 과 같은 3속성.
function applyViewModeButton(mode){
  viewToggleButton.setAttribute('data-view-mode', mode);
  viewToggleButton.setAttribute('aria-label', VIEW_MODE_ACTION_LABEL[mode]);
  viewToggleButton.setAttribute('data-tooltip', VIEW_MODE_ACTION_LABEL[mode]);
}

// L1941-1949
function setViewMode(nextMode){
  viewMode = nextMode;
  persistViewMode(viewMode);
  applyViewModeButton(viewMode);
  render();
}
viewToggleButton.addEventListener('click', function(){
  setViewMode(VIEW_MODE_CYCLE[(VIEW_MODE_CYCLE.indexOf(viewMode) + 1) % VIEW_MODE_CYCLE.length]);
});
```

**결정 V3 — `setViewMode` 의 `if(nextMode === viewMode) return;` 가드를 제거한다.** 호출자가
하나뿐이고 그 호출자가 항상 **반대** 모드를 넘기므로 그 분기는 도달 불가능하다. 일어날 수
없는 상황에 대한 처리는 의도를 흐린다(user rules — karpathy #2). 제거해도 중복 클릭 시
불필요한 `render()` 는 발생하지 않는다(순환이 항상 값을 바꾼다).

**리스너 등록 위치 불변**: `if(!isServed){ … return; }` **앞**에 남긴다. 뒤로 가면 `file://`
모드에서 보기 전환이 통째로 죽는다(GOTCHA 4, T25-66 이 같은 함정을 다른 리스너에서 강제).

`applyViewModeButton(viewMode)` 최초 호출 위치(L1118, `var viewMode = readStoredViewMode();`
직후)도 그대로 둔다.

### 5.5 접근성 결정

**결정 V4 — `aria-pressed` 를 쓰지 않는다. 동작 라벨을 가진 단순 버튼이다.**

근거:

1. **기존 2버튼 구조가 이미 의미상 어색했다.** 상호 배타적인 두 선택지는 `aria-pressed`
   버튼 2개가 아니라 `role="radiogroup"` + `aria-checked` 가 맞다. 하나로 합치면서 그
   어색함이 통째로 사라진다 — 지금은 "누르면 전환되는 동작"이 정확한 의미론이다.
2. **이 파일에 이미 선례가 있다.** 테마 버튼도 `aria-pressed` 없이 동작 라벨만 쓴다(결정
   Y4). 같은 헤더 클러스터에 사는 두 토글이 서로 다른 규약을 쓰는 것이 더 나쁘다.
3. **키보드**: Tab 정지가 2개 → 1개로 준다. Enter/Space 로 활성화, `:focus-visible` 링은
   `.icon-btn` 이 이미 준다(`outline:2px solid var(--accent);outline-offset:3px`).
4. **스크린리더 낭독**: "트리 보기로 전환, 버튼". 아이콘 두 개는 `aria-hidden="true"
   focusable="false"` 이므로 이름은 `aria-label` 이 단독으로 정한다.

**남는 트레이드오프(명시)**: 동작 라벨은 **현재 상태**를 낭독하지 않는다. 테마 버튼과 정확히
같은 성질이며, 실질 상태는 화면 내용 자체(카드 목록 vs 조직도)가 말한다. 채택하지 않은 보완책
둘: `aria-live` 상태 안내(새 기제 도입 — 테마 버튼에도 없다, YAGNI) · `role="switch"` +
`aria-checked`(켜짐/꺼짐 이분법이 "카드↔트리"라는 **대등한 두 표현**에 맞지 않는다).

### 5.6 계약·주석 갱신

| 위치 | 지금 | 바꿀 것 |
|---|---|---|
| L36 (불변식 H1⁗ 정적 노드 목록) | `… #dzh-theme-toggle, #dzh-view-cards, #dzh-view-tree, #dzh-tooltip, …` | `… #dzh-theme-toggle, #dzh-view-toggle, #dzh-tooltip, …` |
| L54 (결정 ST18 서술) | `… VIEW_MODE_STORAGE_KEY + 토글 버튼의 aria-pressed 에 살고` | `… VIEW_MODE_STORAGE_KEY + 토글 버튼의 data-view-mode 에 살고` |
| L477-479 (보기 토글 CSS 주석) | `눌린 쪽만 .card-open 과 같은 채널로 구분한다` | 아이콘 스와핑 관용구 서술로 교체(테마 주석 PV10 을 참조) |
| L1752-1753 (JS 주석) | `토글 두 <button> 의 aria-pressed 만 갱신한다` | `토글 버튼의 3속성만 갱신한다(applyTheme 과 같은 형태)` |
| `hub/README.md` L363 | `헤더의 보기 토글(카드 \| 트리)로 전환하면` | `헤더의 보기 토글 버튼을 누르면 카드 ↔ 트리가 번갈아 바뀌고` (문구는 구현자 재량, "버튼 하나"임이 드러나야 한다) |

**손대지 않을 낡은 주석(언급만)**: L461-462 `.top-actions` 주석의 "새로고침·테마 버튼을
묶는다" 와 L466 `.icon-btn` 주석의 "헤더 클러스터의 **두** 버튼이 공유한다" 는 **이번 변경
이전에 이미 낡았다**(현재 4버튼). 이번 변경은 4→3 으로 줄일 뿐 그 서술을 새로 거짓으로 만들지
않으므로, 수술적 변경 원칙(무관한 것을 "개선"하지 않는다)에 따라 건드리지 않는다. 검수자가
지적하면 별도 커밋으로 뺀다.

---

## 6. 요구 4 — `.head-row` 고정

### 6.1 레이아웃 사실 (조사 결과)

- 스크롤 컨테이너는 **뷰포트**다. `.wrap{max-width:1440px;margin:32px auto;padding:0 16px}` 은
  `overflow` 를 설정하지 않고, `html{}`(L200)도 `overflow` 가 없다 → `position:sticky` 의
  포함 블록은 `.wrap`, 스크롤 포트는 뷰포트. **sticky 가 성립한다.**
- `.head-row` 와 `#dzh-app` 은 `.wrap` 의 형제이고 **같은 좌우 패딩 안**에 있다 → 헤더의
  불투명 배경이 카드를 좌우로 새게 하지 않는다.
- 트리 모드의 `overflow-x:auto` 는 `.tree-section`(=`#dzh-app` 의 자식)에 있어 `.head-row` 의
  조상이 아니다 → 간섭 없음.

### 6.2 기존 z-index 층

| 레이어 | z-index |
|---|---|
| 카드 / 트리 섹션 | (없음) |
| **`.head-row` (신설)** | **10** |
| `.usage` (사용량 패널, `position:fixed`) | 20 |
| `.detail-panel` (상세 패널, `position:fixed`) | 30 |
| `.tooltip` | 40 |

**결정 S1**: `z-index:10`. 카드 위, 사용량 패널 아래. 상세 패널이 헤더를 덮는 것이 맞다
(좁은 화면에서 패널은 전면 오버레이다).

### 6.3 CSS 변경

```css
/* 지금 */
.head-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:18px}
.wrap{max-width:1440px;margin:32px auto;padding:0 16px}

/* 설계 */
.head-row{display:flex;align-items:center;flex-wrap:wrap;gap:12px;
          position:sticky;top:0;z-index:10;background:var(--bg);padding:10px 0;margin-bottom:8px}
.wrap{max-width:1440px;margin:22px auto 32px;padding:0 16px}
```

**결정 S2 — `display:flex` 를 선언 목록의 첫 자리에 유지한다.** T25-59 가
`grep -qF ".head-row{display:flex"` 로 이 행을 앵커한다. 새 선언을 앞에 끼우면 그 회귀 검사가
깨진다 — **뒤에 붙여** T25-59 를 손대지 않고 통과시킨다(검사 개정·원장 승급이 3건 줄어든다).

**결정 S3 — 여백 산술을 보존한다.**

| 구간 | 지금 | 설계 | 등식 |
|---|---|---|---|
| 페이지 상단 → h1 | `.wrap` margin-top 32 | `.wrap` margin-top 22 + `.head-row` padding-top 10 | **22 + 10 = 32** |
| head-row → 첫 카드 | `.head-row` margin-bottom 18 | padding-bottom 10 + margin-bottom 8 | **10 + 8 = 18** |

스크롤 최상단의 화면은 **픽셀 단위로 지금과 같다.** 스크롤하면 그 padding 10 px 이 고정
바의 상하 숨 쉴 공간이 된다.

**결정 S4 — `background:var(--bg)`** (카드의 `--surface` 가 아니다). 헤더는 "카드"가 아니라
"페이지"이고, 그 아래로 지나가는 카드를 가려야 한다. `.detail-panel` 이 같은 근거로
`--bg` 를 쓴다(PV1).

### 6.4 두 모드·모든 상태에서의 동작

| 상황 | 동작 |
|---|---|
| 카드 모드 | 헤더가 상단 고정. 카드가 그 아래를 지나가며 `--bg` 에 가려진다 |
| 트리 모드 | 동일. 전폭 `.tree-section` 이 길어도 헤더가 남는다(요구의 본체) |
| 상세 패널 열림, `<1024px` | `body.dzh-panel-open{overflow:hidden}` — 배경 스크롤 자체가 잠긴다. 패널(z 30)이 헤더(z 10)를 덮는다 |
| 상세 패널 열림, `≥1024px` | `body{padding-right:var(--dzh-panel-width)}` 로 `.wrap` 이 좁아진다. sticky 는 뷰포트 기준이지만 헤더 박스는 `.wrap` 폭 안에 있어 패널 밑으로 들어가지 않는다 |
| 사용량 패널 | `position:fixed;bottom;z-index:20` — 하단·상위층이라 무간섭 |
| 툴팁 | `z-index:40` — 헤더 위에 정상 표시 |
| 극단적으로 좁은 화면(~360 px) | `flex-wrap:wrap` 으로 버튼 클러스터가 2줄이 되고 고정 바가 그만큼 높아진다. 요구 3 이 버튼을 4→3 으로 줄이므로 **지금보다 덜 자주** 발생한다 |
| `body.has-usage .wrap{padding-bottom:…}` | `padding-bottom` 만 쓰므로 무영향 |

### 6.5 채택하지 않은 것

- **"붙었을 때만 그림자"**: `IntersectionObserver` 나 스크롤 리스너로 stuck 상태를 감지해
  `box-shadow` 를 넣는 안. 순수 장식에 새 런타임 기제를 도입하는 것이라 기각(YAGNI). 상시
  `border-bottom` 은 스크롤 최상단의 현재 디자인을 바꾸므로 역시 기각.
- **트리 모드에서만 sticky**: `body` 나 `#dzh-app` 에 모드 클래스를 새로 만들어야 한다.
  보기 모드는 지금 CSS 훅이 없고(결정 V1) 그것을 만들 이유가 이 장식 하나뿐이다. 두 모드
  모두 고정하는 쪽이 단순하고, 카드 모드에서도 목록이 길면 같은 불편이 있다.

---

## 7. 데이터/DOM 계약 영향

| 계약 | 지금 | 변경 후 | 정본 |
|---|---|---|---|
| 정적 노드 목록(불변식 H1⁗) | `#dzh-view-cards`·`#dzh-view-tree` 2개 | `#dzh-view-toggle` 1개 | `hub_template.html` L36 |
| 보기 모드 사용자 상태(결정 ST18) | `localStorage['dzh-view-mode']` + 버튼 `aria-pressed` | `localStorage['dzh-view-mode']` + 버튼 `data-view-mode` | `hub_template.html` L54 |
| `localStorage` 키 | `dzh-view-mode` (변경 없음) | 동일 | T25-159 가 리터럴 1건을 강제 |
| `@keyframes` 이름 | `card-working-glow` · `dz-step-active-pulse` | **동일**(유지 계약) | T25-65 · T22-164 |
| `.head-row{display:flex` 앵커 | 존재 | **존재 유지**(선언 순서 고정) | T25-59 |
| 열기 대상 URL vs 대시보드 URL | 둘 다 "열 수 있는 것"처럼 읽힌다 | 열기 대상 URL 만 연다(불변식 U1) | `dashboard.md` §4 |

**저장값 마이그레이션 불필요**: 키도 값 어휘(`cards`/`tree`)도 그대로다. 기존 사용자의
`localStorage` 가 그대로 살아난다.

---

## 8. 테스트 계획

### 8.1 이 저장소의 검사 기계가 거는 제약 (구현자 필독)

1. **K5 양방향 완비 검사** — `tests/run.sh` 에서 추출된 모든 서브체크 ID 는
   `tests/mutations.tsv` 에 행이 있어야 한다. **신규 ID 는 반드시 원장 행을 동반한다.**
2. **면제행 승급 래칫(§4.4-(4))** — 기존 면제행의 사유는 "S3 이전에 존재한 가드 — **개정·
   수정 시 변조행으로 승급**" 이다. 손댄 가드는 변조행으로 올려야 한다.
3. **`expect_token` 유일성** — 변조행의 토큰은 `tests/run.sh` 안에서 **정확히 1건**이어야
   한다. 등록 전 `grep -cF -- '<토큰>' tests/run.sh` 로 확인한다.
4. **한계 표기(T37-13)** — 변조행 가드가 사는 **함수 바로 위 주석 블록**에 「실측한 범위」·
   「비망라」·「전수 증명이 아니」 중 하나가 있어야 한다.
   - `test_dashboard_template_integrity`(T22): **이미 있다**(L2090-2094 「한계(비망라, …)
     전수 증명이 아니다.」) → 추가 작업 없음.
   - `test_hub_docs_and_constants`(T25): **없다**(L3770 한 줄 주석뿐) → **T25 를 변조행으로
     올리려면 이 함수 위에 한계 표기 주석 블록을 먼저 신설해야 한다.** 이 회차의 필수 작업이다.
5. **원장 헤더 인용 대조(`verify_ledger_header_citations`)** — 헤더가 인용한 상수 4종
   (`LEDGER_EXEMPT_ROW_RATCHET`·`LEDGER_MUTATION_ROW_FLOOR`·`SOURCE_GUARD_ID_FLOOR`·
   `NOTE_FAILURE_ID_LESS_RATCHET`)과 면제 바구니 계수 2종을 실측과 대조한다. **행을
   추가·승급하면 헤더 숫자를 함께 고쳐야 사전 점검이 통과한다.**
6. **그룹 범위 표기** — 새 ID 를 넣으면 `# T22: … (하위 검증 T22-1~T22-N)` 과
   `local test_desc="… (T22-1~T22-N)"` **두 곳**을 함께 올린다. T25 도 동일.

### 8.2 다음 ID (실측)

- T22 최대 = **T22-165** → 신설 **T22-166**
- T25 최대 = **T25-168** → 신설 **T25-169**, **T25-170**

### 8.3 개정하는 검사

| ID | 지금 | 개정 | 원장 |
|---|---|---|---|
| **T25-59** | `.head-row{display:flex` 존재 | **손대지 않는다** — 결정 S2 로 앵커가 살아남는다 | 변경 없음 |
| **T25-159** | `id="dzh-view-cards"`·`id="dzh-view-tree"` 가 `id="dzh-app"` 앞 | ① 두 줄 앵커 → `id="dzh-view-toggle"` 한 줄. ② **이빨 추가**: `grep -c 'dzh-view-cards'` == 0 · `grep -c 'dzh-view-tree'` == 0 · `grep -c 'aria-pressed'` == **0**(현재 7건 — 통합 후 이 파일에서 완전히 사라진다). `dzh-view-mode` 리터럴 1건·줄 앵커 선언 검사는 그대로 | 면제 → **변조 승급** |
| **T25-65** | `.card.card-working{` · `card-working'` · `@keyframes card-working-glow` · `prefers-reduced-motion` | 네 토큰 **그대로 통과**한다(설계가 이름을 보존). **이빨 추가**: `@keyframes card-working-glow{0%,100%{opacity:.6}` 존재 — 진폭을 옛 `.35` 로 되돌리는 회귀를 문다 | 면제 → **변조 승급** |
| **T22-164** | `@keyframes dz-step-active-pulse` · `ol.steps li.active::before{` · `animation:dz-step-active-pulse` · `prefers-reduced-motion` + reduced-motion `animation:none` 정규식 | 다섯 단정 **그대로 통과**. **이빨 추가**: `@keyframes dz-step-active-pulse{0%,100%{opacity:.6}` 존재 | 면제 → **변조 승급** |
| **T22-163** | `dashboard.md` 바이트 ≤ `DASHBOARD_MD_BUDGET_BYTES` | 로직 불변. **상수를 실측치로 내린다**(순감 시). 상수는 이 가드의 계약이므로 보수적으로 승급 | 면제 → **변조 승급** |

### 8.4 신설하는 검사

**T25-169 — 보기 토글이 테마 토글 관용구를 따른다** (`hub_template.html`)

| # | 단정 | 무엇을 무는가 |
|---|---|---|
| a | `id="dzh-view-toggle"` 정확히 1건, `id="dzh-app"` **앞**(정적 노드) | 버튼을 `#dzh-app` 안으로 옮기면 폴링이 지워 버린다(H1⁗ 위반) |
| b | `class="view-icon-cards"`·`class="view-icon-tree"` 각 1건 | 아이콘 하나를 지우면 한 모드에서 버튼이 빈 원이 된다 |
| c | CSS 3줄 존재: `.view-toggle .view-icon-cards{display:none}` · `.view-toggle[data-view-mode="tree"] .view-icon-tree{display:none}` · `.view-toggle[data-view-mode="tree"] .view-icon-cards{display:inline}` | 스와핑 규칙 하나를 지우면 두 아이콘이 동시에 보이거나 둘 다 사라진다 |
| d | `function applyViewModeButton(` 존재 + 그 본문에 `data-view-mode`·`aria-label`·`data-tooltip` 3속성 `setAttribute` | 속성 하나를 빠뜨리면 아이콘·라벨·툴팁 중 하나가 상태와 어긋난다(조용한 실패) |
| e | `.view-toggle-group` 0건 | 래퍼 잔재 |
| f | `viewToggleButton.addEventListener('click'` 정확히 1건 | 리스너 중복 등록 시 클릭 1회에 모드가 2번 돌아 제자리로 온다 |
| g | 그 `addEventListener` 줄 번호 < `if(!isServed){` **마지막** 등장 줄 번호 | GOTCHA 4 — 뒤로 가면 `file://` 모드에서 전환이 죽는다. T25-66 의 관용구를 그대로 복제 |

**T25-170 — `.head-row` 가 상단에 고정된다** (`hub_template.html`)

| # | 단정 | 무엇을 무는가 |
|---|---|---|
| a | `.head-row{` 행에 `position:sticky`·`top:0`·`z-index:10`·`background:var(--bg)` 네 토큰이 모두 있다 | 배경을 빼면 카드가 헤더를 관통해 보인다(가장 눈에 띄는 회귀). sticky/top 을 빼면 요구 자체가 무산 |
| b | `.head-row{display:flex` 로 시작한다(T25-59 앵커 보존 재확인) | 선언 순서를 흔들면 T25-59 가 깨진다 — 두 검사가 같은 사실을 서로 다른 각도에서 잡는다 |
| c | `.wrap{max-width:1440px;margin:22px auto 32px` 존재 | 여백 산술(22+10=32)의 한쪽만 되돌리면 상단 여백이 어긋난다 |
| d | `.head-row{` 의 z-index 값 < `.usage{` 의 z-index 값 (두 값을 추출해 수치 비교) | 헤더가 사용량 패널·상세 패널을 덮는 층 역전 |

**T22-166 — 자동 발행의 단일 열기 불변식** (`commands/dashboard.md`)

| # | 단정 | 무엇을 무는가 |
|---|---|---|
| a | §4 에 「열기 대상 URL 하나뿐」 계열 토큰 존재 | 불변식 문장이 조용히 지워지는 것 |
| b | 「브라우저 열기 호출은 … 1회」 계열 토큰 존재 | 횟수 못 박기가 사라지는 것 |
| c | 옛 문구 `여기서 \`<URL>\` 은 3-a 가 정한` 0건 | 두 문장이 공존해 다시 모호해지는 것 |

> 토큰 문자열은 구현 시 확정한다. 확정 후 **각 토큰이 `dashboard.md` 에서 1건**인지
> `grep -cF` 로 확인하고, 그 토큰을 §3.3 최종 문안과 함께 이 문서에 되적는다.

**구현 시 되적음 — 확정한 토큰과 최종 문안 (요구 1 구현 완료, 2026-09-08)**

원장 헤더가 `expect_token` 에 추가로 강제하는 제약(§8.1-3 — "이 토큰은 **가드가 사는
파일**(`tests/run.sh`) 안에서 1건만 등장해야 한다")을 구현 중 발견해, `dashboard.md` 를
검색하는 grep 패턴과 원장·한계 표기 앵커로 쓰는 `expect_token` 을 **서로 다른 문자열**로
분리했다(같은 문자열을 쓰면 grep 조건 줄과 `note_failure` 메시지 줄 양쪽에 리터럴이 남아
`tests/run.sh` 안에서 2건이 되어 앵커 자격을 잃는다).

| # | `dashboard.md` 검색 토큰(grep 조건) | 원장 `expect_token`(= `note_failure` 메시지의 정적 부분) | guard_id |
|---|---|---|---|
| a | `열기 대상 URL 하나뿐` | `열기 대상 단일성 불변식` | `T22-166a` |
| b | `브라우저 열기 호출은 성공하든 실패하든 1회다` | `브라우저 열기 호출 횟수 못박기` | `T22-166b` |
| c | (옛 문구, 개수 0 기대) `여기서 \`<URL>\` 은 3-a 가 정한` | `대시보드 URL·열기 대상 URL 재분리 서술` | `T22-166c` |

**guard_id 를 `a`/`b`/`c` 두 번째 하이픈 없이 붙인 이유**: `validate_guard_id_token` 의
포맷 정규식이 `^T[0-9]+-[0-9a-z]+$`(하이픈 정확히 1개)라 `T22-166-a` 는 거부된다.
`T22-166a` 는 통과하고, `collect_guard_ids` 의 추출 정규식도 이 접미를 통째로 한
ID 로 읽는다 — 그래서 `tests/run.sh` 의 `note_failure` 호출도 `"T22-166a: …"`처럼
접미까지 포함해 직접 써야 한다(공통 `"T22-166: …"` 접두 하나로 3개 단정을 묶으면 소스
추출 ID 가 1개로 뭉개져 원장의 3행과 짝이 맞지 않는다 — K5 완비 검사가 이를 즉시 잡는다).

**§3.3 최종 문안 — PRP 제안 문안에서 두 곳을 조정했다(둘 다 바이트 예산 압박 + 기존
회귀 검사 보존이 이유):**

- §4 도입부: 제안 문안의 "3번의 **대시보드 URL** 은 보고·각인 전용이라 열지 않는다
  (둘이 다른 것이 정상이다)"를 "**대시보드 URL** 은 열지 않는다"로 압축했다(요소 b 는
  그대로 남기고 "정상이다" 부연만 뺐다). 뒤따르는 "아래 순서로 …" 문단은 **원문을 한
  글자도 바꾸지 않고 그대로 두었다** — 이 문단이 `tests/run.sh` 의 기존 회귀 검사
  T22-76(`재시도하지 않고` 앵커)가 참조하는 자리라는 것을 검사 실행 후에 발견했고, 제안
  문안대로 축약했더니 T22-76 이 즉시 깨졌다.

  ```
  여는 것은 3-a 가 정한 **열기 대상 URL 하나뿐**이고, **대시보드 URL** 은 열지 않는다.
  **이 절차 전체에서 브라우저 열기 호출은 성공하든 실패하든 1회다.**

  아래 순서로 **한 번씩만** 시도한다. **재시도하지 않고, 루프를 돌지 않고, 실패를 에러로 보고하지
  않는다.** 성공하면 즉시 5번으로 간다.
  ```

- §4-1 두 번째 하위 불릿(U3): "전면으로 올리는 호출을 한 번만 더 한다"라는 원문 어구도
  `tests/run.sh` 의 기존 회귀 검사 T22-94(`전면으로 올리는` 앵커, §4 범위 안에서 검색)가
  요구하는 리터럴이라 **그대로 보존**했다. U3 이 요구하는 "`navigate` 재호출이 아니다"
  라는 한정은 그 문장 뒤에 짧은 괄호 `(`navigate` 아님)` 으로만 덧붙였다 — 원안(전체
  문장을 갈아 끼우는 것)은 이 앵커를 지워 T22-94 를 깨뜨렸다.

  ```
  - 그 도구가 탭 목록 조회·탭 선택(select/activate/focus 계열) 도구를 **함께 제공하면**,
    navigate 직후 방금 연 탭을 **전면으로 올리는 호출을 한 번만** 더 한다(`navigate` 아님).
    navigate 만으로는 탭이 백그라운드에 열려 사용자가 보던 화면이 그대로일 수 있다.
  ```

**교훈(다음 회차용)**: 문서 산문을 고칠 때 그 산문의 정확한 부분 문자열을 리터럴로
앵커하는 기존 회귀 검사가 있는지 `grep -F <바꿀 문구> tests/run.sh` 로 먼저 확인하는
쪽이, 편집 후 `--only <그룹>` 을 돌려 뒤늦게 발견하는 것보다 싸다. 이번 회차는 후자로
발견했고(§3.3 원안 그대로 적용 → `--only T22` 2건 FAIL → 원인이 T22-76·T22-94 앵커
삭제였음을 역추적) 결과적으로 순감 목표(§3.4, ≤0B)는 지켰다(95,973B → 95,955B, −18B).

### 8.5 "일부러 깨뜨려 확인" (커밋 `7ec39d7` 의 배포 규칙 — 이 회차 필수)

신설·개정한 모든 단정에 대해 **각각** 아래를 수행하고 결과를 구현 보고에 표로 남긴다.

```
1. 사본에 그 단정만 무력화하는 최소 변조를 넣는다(원장의 mutation_sed 와 같은 형태).
2. bash tests/run.sh --only <그룹> 을 돌린다.
3. 그 단정의 note_failure 가 발화하는지 확인한다.  ← 발화하지 않으면 그 검사는 이빨이 없다.
4. 변조를 되돌리고 전체가 통과함을 확인한다.
```

특히 확인할 것:

- T25-169-f(리스너 1건) — 리스너를 **2개**로 늘리는 변조에서 발화하는가.
- T25-170-a — `background:var(--bg)` **만** 지운 변조에서 발화하는가(나머지 세 토큰이
  남아 있어도 잡아야 한다).
- T25-170-d — z-index 를 `10` → `50` 으로 바꾼 변조에서 발화하는가.
- T25-65/T22-164 의 진폭 핀 — `.6` → `.35`/`.3` 으로 되돌린 변조에서 발화하는가.
- T22-166-c — 옛 문구를 되살린 변조에서 발화하는가.

### 8.6 원장(`tests/mutations.tsv`) 회계

| 항목 | 지금 | 변화 | 후 |
|---|---|---|---|
| 면제행 | 394 | −4 (T25-159·T25-65·T22-164·T22-163 승급) | **390** |
| 변조행 | 24 | +4 승급 +3 신설 | **31** |
| 공통 면제 사유 바구니(「아래 372개는」) | 372 | −4 | **368** |
| 소스 서브체크 ID 수 | ≥411 | +3 신설 | 실측 후 확정 |

상수 갱신(전부 **조이는/올리는** 방향 — 근거 요구 없음, 그래도 커밋에 한 줄 남긴다):

- `LEDGER_EXEMPT_ROW_RATCHET` 394 → **390** (상한을 내린다)
- `LEDGER_MUTATION_ROW_FLOOR` 24 → **31** (하한을 올린다)
- `SOURCE_GUARD_ID_FLOOR` 411 → **실측치** (하한을 올린다)
- `DASHBOARD_MD_BUDGET_BYTES` 95973 → **실측치**(순감 시)
- `NOTE_FAILURE_ID_LESS_RATCHET` 110 → **변경 없음** (신규 호출은 전부 ID 접두를 갖는다)

> **위 숫자를 믿고 그대로 쓰지 마라.** 편집이 끝난 뒤 파일에서 **기계적으로 다시 세고**,
> 헤더 인용 문자열의 이력 화살표(`(24 — 4→8→…→24)` 형태)까지 함께 갱신한다.
> `verify_ledger_header_citations` 는 괄호 안 **첫 숫자**만 대조하지만, 이력 꼬리가 낡으면
> 다음 회차가 같은 함정을 밟는다.

계수 명령:

```bash
cd <worktree>
awk -F'\t' '!/^#/ && NF>=7 && $3=="-"'  tests/mutations.tsv | wc -l   # 면제행
awk -F'\t' '!/^#/ && NF>=7 && $3!="-"'  tests/mutations.tsv | wc -l   # 변조행
awk -F'\t' '!/^#/ && NF>=7 && $3=="-" && $7 ~ /^S3 이전에 존재한 가드/' tests/mutations.tsv | wc -l
wc -c < commands/dashboard.md
```

### 8.7 검증 명령 (프로젝트 정본 — CLAUDE.md §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

**금지**: 이 저장소 안에서 `install.sh --scope project` 실행 · 실제 `$HOME` 대상 설치.

### 8.8 수동 확인 (기계가 못 보는 것)

허브를 임시로 띄워(`python3 -m http.server` 를 **레포 밖**에서, 또는 기존 허브 서버) 육안 확인:

- [ ] 작업중 카드의 bloom 이 "숨쉬기"로 읽히고 "깜빡임"으로 읽히지 않는다
- [ ] 작업중 + 열린 카드가 열리기만 한 카드와 구분된다(모션 유무 + bloom 깊이)
- [ ] 진행중 단계 바의 위·아래 끝이 부드럽게 사라진다(회색 프린지 없음) — 라이트·다크 **양쪽**
- [ ] PiP 압축뷰(`body.dz-pip`)에서 바가 `border-radius:8px` 모서리를 뚫지 않는다
- [ ] 보기 토글: 카드 모드에서 **트리 아이콘**, 트리 모드에서 **카드 아이콘**이 보인다
- [ ] 보기 토글 Tab 도달 시 포커스 링, Enter/Space 로 전환, 새로고침 후 모드 유지
- [ ] 트리 모드에서 아래로 스크롤 — 헤더가 상단에 남고 트리가 그 아래로 **가려진 채** 지나간다
- [ ] 카드 모드에서도 동일. 스크롤 최상단의 여백이 변경 전과 같다
- [ ] 상세 패널을 연 상태(좁은 화면 / 1024px 이상 양쪽)에서 헤더가 패널을 덮지 않는다
- [ ] OS 「동작 줄이기」 켠 상태에서 두 pulse 가 멈추고 정적 신호는 남는다
- [ ] `file://` 로 직접 연 허브에서도 보기 전환이 동작한다

**실측 결과 (2026-09-08, 요구 2~4 착지 시점)** — 실행 중인 허브의 실제 데이터를 새 템플릿에
얹어 로컬에서 렌더하고, 계산된 스타일·기하를 직접 쟀다. 11개 항목 중 **9개 확인 · 2개 미검증**.

| 항목 | 실측 |
|---|---|
| 테두리 두께 | 작업중 카드 `border-width: 1px`, `::after` 는 `0 0 14px -6px inset` — 하드 링 소멸 |
| 진폭·주기 | 두 파일 모두 keyframes `0%,100% → 0.6 / 50% → 1`, `4s` |
| reduced-motion | 두 파일 모두 `animation:none; opacity:1` |
| 회색 프린지 | 그라데이션을 40 px 로 확대해 라이트·다크 양쪽 관찰 — 프린지 없음 |
| PiP 모서리 | 아래 「인과 정정」 참조 — 뚫지 않음(기제는 그라데이션) |
| 보기 토글 | 버튼 1개, 카드 모드 → 트리 아이콘 / 트리 모드 → 카드 아이콘, 라벨·툴팁 동기, `localStorage` 유지, 문서 전체 `aria-pressed` 0건 |
| sticky | 스크롤 600 px 후 `headTop=0`, `elementFromPoint` 가 헤더 반환(관통 없음) |
| 상세 패널 ≥1024 px | `body{padding-right:550px}` 상태에서 헤더 right 534 < 패널 left 550 — 겹치지 않음 |
| 여백 산술 | `.wrap` 계산값 `22px 0 32px` — 하단 32 px 보존 확인 |

**미검증 2건(통과로 적지 않는다)**:

- **키보드 Enter/Space 활성화** — 내장 브라우저의 키 입력이 `click` 을 합성하지 않아 확인 불가.
  **손대지 않은 기존 `#dzh-theme-toggle` 로 대조 실험**했고 동일하게 실패하므로 이번 변경의
  회귀는 아니다. 버튼은 `<button type="button">` + click 리스너로 테마 토글과 같은 형태다.
- **`file://` 모드 보기 전환** — 내장 브라우저가 로컬 파일을 조작하지 못한다. 정적 검사
  T25-169g 가 리스너 등록이 `if(!isServed){` 앞인지만 강제한다.

**인과 정정 — PiP 모서리 안전성 (다음 회차가 같은 실수를 하지 않도록 남긴다)**

이 한 지점의 「왜 안전한가」가 **두 회차에 걸쳐 반대 방향으로 두 번 틀렸다.**

1. 구현 1회차 주석: 「그라데이션이 하드한 끝을 없애 옛 `border-radius` 보정이 불필요해졌다」
2. 검수 렌즈 A: 「아니다 — `padding-left:8px` 가 `border-radius:8px` 와 같아 곡선이 x=8 에서
   접하는 것이 근거다」 → 이 지적을 받아 주석을 고쳤다
3. 검수 렌즈 B: 「그것도 아니다 — `left:0` 은 패딩 에지 기준인데 `li` 에 `border-left` 가 없어
   그 자리가 테두리 상자 좌변이다. `padding-left` 는 바를 옮기지 못한다」

**실측으로 결판냈다**(브라우저 2회):

- PiP 의 `padding-left` 를 8 px → 40 px 로 바꿔도 바의 오프셋은 **0 으로 고정**이었다 →
  3번(렌즈 B)이 옳다. 바는 x=0 에 있고, `overflow:visible` 이라 8 px 모서리를 **기하학적으로
  뚫는다**.
- 기하를 10배로 키운 대조 렌더(그라데이션 vs 솔리드)에서 솔리드 대조군만 각진 모서리가
  삐져나왔다 → 그것을 가리는 것은 **그라데이션의 투명한 끝**이다(1번이 옳았다).

즉 **기하학적으로는 뚫고, 시각적으로는 가려진다** — 두 사실이 모두 참이라 한쪽만 말하면
틀린다. 최종 주석은 셋을 다 적는다(바의 위치 · 패딩이 무관하다는 사실 · 가리는 기제).

**교훈**: CSS 박스 모델 위의 「왜 안전한가」는 세 명이 각자 추론하면 세 답이 나온다.
`getBoundingClientRect` 한 번이 그 논쟁 전체보다 싸다 — 주석에 인과를 단정하기 전에 잰다.

---

## 9. 구현 순서 (커밋 단위)

`.head-row` 와 보기 토글이 같은 마크업 블록에 있어 3 → 4 순으로 붙는 것이 충돌이 적다.

| # | 커밋 | 파일 | 검증 |
|---|---|---|---|
| 1 | 요구 1 — 자동 발행 단일 열기 불변식 | `commands/dashboard.md` + T22-166 + `tests/run.sh` 상수 + 원장 | `wc -c` 순감 확인 · `--only T22` · 뮤테이션 3건 |
| 2 | 요구 2 — 두 pulse 순화 | `dashboard_template.html` · `hub_template.html` · `hub/README.md` + T22-164/T25-65 이빨 + 원장 승급 | `--only T22` · `--only T25` · 뮤테이션 2건 · 육안 |
| 3 | 요구 3 — 보기 토글 통합 | `hub_template.html` · `hub/README.md` + T25-159 개정 + T25-169 + T25 한계 표기 + 원장 | `--only T25` · 뮤테이션 7건 · 육안 |
| 4 | 요구 4 — `.head-row` sticky | `hub_template.html` + T25-170 + 원장 | `--only T25` · 뮤테이션 4건 · 육안 |
| 5 | 원장 헤더·상수 정합 마무리 | `tests/mutations.tsv` 헤더 · `tests/run.sh` 상수 4종 | `bash tests/run.sh` 전체 |

각 커밋마다 **전체** `bash tests/run.sh` 를 돌린다(사전 점검 3종은 그룹 실행 전에 전부 돈다 —
`--only` 만으로는 헤더 인용 불일치를 늦게 발견한다).

커밋 메시지: `type: 한국어 서술형`(프로젝트 컨벤션). 요구 1 커밋에는 **바이트 순감치**를,
상수를 움직인 커밋에는 **그 이유**를 본문에 남긴다.

---

## 10. 리스크와 완화

| # | 리스크 | 심각도 | 완화 |
|---|---|---|---|
| R1 | `dashboard.md` 바이트 헤드룸 0 — 문안이 조금만 길어도 T22-163 이 그룹을 중단시킨다 | **High** | 삭제 2곳(약 200 B)을 **먼저** 적용하고 추가분을 그 예산 안에서 쓴다. 커밋 전 `wc -c` 필수 |
| R2 | 요구 1 이 근본 원인을 못 잡을 수 있다 — 원인이 절차 모호성이 아니라 호스트 도구의 동작일 가능성 | **High** | 실측은 "절차를 엄격히 따르면 1개"였고 문서만이 흔들림의 원인 후보였다. 착지 후 **워크트리 세션에서 `/dashboard init` 을 실제로 돌려 탭이 1개인지 확인**한다. 재발하면 다음 회차는 호스트 도구 로그 수집으로 간다(이번 범위 밖) |
| R3 | T25 그룹에 한계 표기가 없어 변조행 승급이 T37-13 에서 막힌다 | **High** | §8.1-4 에서 명시 — `test_hub_docs_and_constants` 위 주석 블록 신설을 **T25 원장 작업의 선행 조건**으로 못 박았다 |
| R4 | 원장 계수 6종이 어긋나 `verify_ledger_header_citations` 가 **그룹을 하나도 못 돌리고** 멈춘다 | Medium | §8.6 의 `awk` 계수 명령을 그대로 쓴다. 이 실패는 fail-loud 라 조용히 새지 않는다 |
| R5 | bloom 전환으로 `card-open + card-working` 판별이 약해진다 | Medium | 모션 유무가 실질 판별자이고, 정지 상태(reduced-motion)에서도 bloom 깊이 차(14/−6 vs 20/−4)가 남는다. 육안 확인 항목으로 고정 |
| R6 | sticky 헤더가 좁은 화면에서 2줄이 되어 세로 공간을 먹는다 | Low | 요구 3 이 버튼을 4→3 으로 줄여 오히려 완화된다. `flex-wrap` 은 유지(제거하면 겹침이 재발) |
| R7 | `linear-gradient` 의 `transparent` 보간 프린지 | Low | 명세상 premultiplied 보간이라 없다. 육안 확인 항목(라이트·다크 양쪽) |
| R8 | 보기 토글이 현재 상태를 낭독하지 않는다 | Low | 테마 버튼과 동일한 기존 트레이드오프(결정 Y4). 화면 내용이 상태를 말한다. §5.5 에 명시 |
| R9 | 요구 2·3·4 가 같은 파일(`hub_template.html`)을 건드려 커밋 간 충돌 | Low | §9 의 순서(3 → 4)가 마크업 블록 충돌을 없앤다. 워크트리 단독 작업이라 외부 동시 편집 없음 |

---

## 11. 사용자 승인이 필요한 핵심 결정

1. **요구 1 의 처방을 "문서 교정"으로 한정한다.** 코드는 손대지 않는다 — 브라우저를 여는
   파이썬 경로는 URL 을 하나만 넘긴다는 것이 조사 결론이다. 이 진단이 틀리면 처방 전체가
   무효이므로, 착지 후 워크트리 세션에서 실제 재현 확인이 필요하다(R2).
2. **요구 2 의 채택안: 진폭 `.6` · 주기 `4s` · 하드 엣지 제거.** 두 파일이 같은 숫자를
   공유한다. 다른 값을 원하면 지금 말해 달라 — 착지 후에는 회귀 검사가 그 값을 핀으로 박는다.
3. **요구 3 에서 `aria-pressed` 를 버리고 "동작 라벨" 규약으로 간다.** 테마 버튼과 같은
   관용구이며, `role="switch"` 나 상태 낭독을 원하면 설계를 바꿔야 한다.
4. **T25 그룹 함수에 「한계 표기」 주석 블록을 신설한다.** 검사 기계의 요구지만 T25 그룹
   전체의 계약 문서에 손대는 것이므로 승인 대상으로 올린다.
