허브와 세션 대시보드의 라이트 테마를 파란색에서 **반짝이는 금빛**으로 바꾼다. 바탕은 크림색이고, 작업중 배지·진행 막대·진행중 칩·검수 통과 배지는 밝은 금색 그라데이션 위에 짙은 글자로 그린다.
「소식 없음」·「한도 초과」·「승인 대기」 같은 경고는 남보라로 옮긴다. 경고까지 금색 계열에 두면 색약이 있는 사람에게 평소 표시와 경고가 같은 색으로 보이기 때문이다.
승인하면 화면 파일 두 개에서 색 값과 색 이름표 3개를 추가하고 바꾸며, 배지·막대 규칙 8줄과 그 설명 주석을 고친다. 「경고와 평소 색이 갈리는가」·「두 화면 색이 같은가」·「다크 화면이 그대로인가」를 지키는 검사 3개도 더한다.
다크 테마(화면이 픽셀 단위로 그대로다)·화면 배치·파비콘(탭 아이콘)·서버 동작은 바뀌지 않는다.

> 상태: **승인됨 — 광택 강도 「화려」** (2026-10-15, 사용자 결정 LT15). 설계 모델: opus(기본 — 승격 기준 미해당).
> 이력: 설계 개정 1 — 사용자 결정 반영(2026-10-15).
> 화려 적용 시 본문의 절제 기준 서술은 다음처럼 읽는다: 새 토큰 3개 → 4개(`--gloss-edge` 포함), 채움 위 글자 최저 대비 7.40:1 → 6.41:1, 가장 진한 채움 정지점 `#F2B300` → `#E3A600` — 값은 LT15 표의 화려 열이 정본이다.
> **최종 선택: 안 A 「골드」 + 글로시(화려)** — 사용자가 A 를 골랐고, 광택 강도는 권고(절제) 대신 화려를 승인했다. 그리고 원문으로 다음을 요청했다: 「골드 테마의 골드 색상을 좀더 글로시하고 쨍한 금빛 느낌으로 수정해볼래?」
> 문서 파일명의 「sunset」은 첫 요청(「노란색이나 골드, 선셋 느낌」)의 흔적이다. 안 B 「선셋」은 검토 대안으로 §11 에 남긴다.
> 개정 1 이 바꾼 결정: LT1·LT3·LT5·LT8·LT9·LT10(「개정 1」 표기), 신설 LT11~LT15. 사용자 결정 2(다크 경고는 주황 유지)·3(파비콘 파랑 유지)·4(변조행)는 확정됐다.
> 작업 위치: 워크트리 `.claude/worktrees/hub-light-sunset`(브랜치 `feat/hub-light-theme-sunset`, develop `0108c6c` 기준).
> 목업(실제 템플릿을 실제 렌더러로 구운 페이지에 §6 의 라이트 전용 덮어쓰기 블록만 끼운 것, 4열 「현재 | A 직전 | A 글로시 절제(권고) | A 글로시 화려」, 각 열 = 허브 + 대시보드):
> `/private/tmp/claude-501/-Users-byron-private-project-coding-harness/78af0cc6-ca1f-4841-a7b4-e8b1ed7085c7/scratchpad/mock2/mock-compare-gloss.html`
> (PNG `…/scratchpad/mock2/mock-compare-gloss.png`, 확대 비교 `…/mock2/zoom.png`(작업중 배지·진행 막대·진행중 칩·필터·PASS), 단독 `…/mock2/hub-*-light.png`·`dash-*-light.png`.
> 다크 무변경 증거 `…/mock2/{hub,dash}-{current,impl_soft,impl_vivid}-dark.png`. 생성기 `…/scratchpad/build_mock2.py`, CSS 단일 출처 `…/scratchpad/gloss_css.py`,
> 검산 `…/scratchpad/colorlib.py`·`evaluate.py`·`palettes_gloss.json`). 개정 전 목업(현재 | B | A)은 `…/scratchpad/mock/mock-compare.png`.
>
> 대상: `hub/bin/hub_template.html`·`hub/bin/hub_dashboard_template.html`(라이트 `:root` 값 + 새 토큰 3 + 다크 별칭 + 규칙 8 + 주석) · `tests/run.sh`(T25 신설 3)·
> `tests/mutations.tsv` · `hub/README.md`(색 이름 문구) · `README.md`(설계 문서 수) · 이전 PRP 1개의 개정 표기.
> **바꾸지 않는 것**: 다크 블록의 기존 토큰 값(두 파일)·JS·파비콘·파이썬 전부·훅·설치 스크립트·`docs/images`(다크 스크린샷)·작업중 glow·테두리 규칙.

---

## 1. 요구사항 요약

- 사용자 요구 1(원문): 「대시보드의 라이트 테마의 색상을 블루 계열 컬러가 아니라 노란색이나 골드, 선셋 느낌의 테마로 수정해줘.」
- 사용자 요구 2(안 A 선택 후, 원문): 「골드 테마의 골드 색상을 좀더 글로시하고 쨍한 금빛 느낌으로 수정해볼래?」

허브(`hub_template.html`)와 세션 대시보드(`hub_dashboard_template.html`)는 같은 라이트 토큰 13개를 쓰고, 화면 색은 거의 전부 토큰을 거친다.
개정 전 안 A 는 토큰 **값만** 바꿨다. 그런데 금색은 글자·테두리에 필요한 명도(L* 37~50)까지 내리면 청동·갈색이 된다.
그 결과 작업중 배지·진행 막대·진행중 칩이 「금」이 아니라 「갈색」으로 읽혔다(사용자 평가: 쨍하지 않다).

개정 1 은 **밝은 금을 글자가 아니라 채움 면에** 쓴다. 그 위의 글자를 흰색 계열이 아니라 **짙은 금갈색으로 뒤집고**, 그 채움에 위→아래 금속 광택 그라데이션을 준다.
이 처리는 토큰 값만으로는 할 수 없다. 그래서 새 토큰 3개와 규칙 8줄이 생긴다.
다크 테마는 사용자 결정대로 **화면이 그대로여야 한다.** 새 토큰은 다크에서 기존 토큰의 별칭이 되고, 이를 검사로 고정한다.

## 2. 이미 확인한 사실(출발점)

- 토큰 블록: 허브 `hub_template.html:192-212`(맨몸 `:root{`), 대시보드 `hub_dashboard_template.html:70-77`. 다크는 각 파일의 `@media (prefers-color-scheme:dark)
  :root:not([data-theme="light"])`·`:root[data-theme="dark"]` 두 벌이다. 두 파일의 라이트 값은 지금 **`--accent-soft` 하나만 다르다**(허브 `#DAE9F7`·대시보드 `#E4F0F8`).
- 두 템플릿 모두 머리 IIFE 가 `data-theme` 를 **항상** 붙인다(허브 990행대, 대시보드 276행대).
- **「`--accent-ink` 채움 + `--bg` 글자」 규칙 6개** — 개정 1 이 바꾸는 대상이다.
  - 허브 `.badge.state-working`(413행).
  - 대시보드 `li.active .num`(128), `li.active .chip`(133), `.matrix td.cell[data-state="active"]`(184), `.badge.pass`(189), `.dzf:checked + label`(194).
- **「`--accent` 채움」 막대 2개**: 허브 `.usage-bar>span`(687), 대시보드 `.bar-inner`(121).
- **작업중 배지에는 box-shadow·animation 을 둘 수 없다.** T25-190 역가드가 막는다(결정 V1·V11, 사용자 결정 2026-09-10 「halo 를 되돌려라」).
  그래서 이 배지의 광택은 **배경 그라데이션만으로** 낸다(LT11).
- 작업중 glow·열린 카드 테두리는 `var(--accent)` 리터럴을 가드가 문다. T25-189(바깥 bloom 정규식)·T25-221(안쪽 bloom 리터럴)이고 둘 다 변조행이다.
  `.card.card-open{background:var(--accent-soft);border-color:var(--accent)}` 는 T25-110 이 리터럴로 문다.
  → glow·테두리·열린 카드 면은 **규칙을 바꾸지 않는다**(LT14).
- 대비 계약이 걸린 다른 조합
  - `.badge.state-interrupted` 는 `--attention` 채움 + `--surface` 글자다.
  - `.badge.approval-wait` 는 `--surface` 면 + `--attention` 글자·링이다.
  - `.badge.state-stale`·`.agent-chip-error`·`.badge.fail` 는 `--attention-soft` 면 + `--attention` 글자다.
  - `.agent-run-activity-stall`·`.warnings`·`.detail-note`·`.usage-stale-note` 는 `--attention` 글자만 쓴다(열린 카드 `--accent-soft` 위에도 놓인다).
  - `.agent-chip-running`·`.state-background`·`.update-btn`·`li.done .chip`·`.badge.impl` 는 `--accent-soft` 면 + `--accent-ink` 글자다.
  - `--accent` 는 테두리·포커스 링·glow 에만 쓴다.
- **지금 팔레트의 잠복 AA 미달 3건**: `--attention` 이 `--attention-soft` 위 4.39:1, `--accent-soft` 위 4.06:1, `--bg` 위 4.50:1(경계). 새 팔레트는 셋 다 6.8:1 이상이다.
- `tests/run.sh` T25-110(6457~6532행, 원장 **면제행**)은 첫 맨몸 `:root{…}` 에서 `--이름:#6자리` 만 뽑아 세 부등식을 본다.
  세 부등식은 muted/accent-soft ≥ 4.5, L*(bg)−L*(accent-soft) ≥ 2.0, accent/bg ≥ 3.0 이고, `.card.card-open` 리터럴도 고정한다.
  이 파서는 `:root\{(.*?)\}` 로 첫 `}` 까지를 블록으로 본다. 그라데이션 값(`--x:linear-gradient(…)`)은 `--이름:#` 꼴이 아니라 걸리지 않는다(검산).
- 색 리터럴 금지 가드: T25-29·T22-27③ 은 `#1F8A70`·`#C2410C`·`#F59E0B` 를, T22-117 은 `#E5F3EE`·`#EAF2FB`·`#FBE9E2`·`#E7EAF3`·`#2D78C8`·`#4B5A6D` 를 막는다.
  새 값(그라데이션 정지점 포함)은 아홉 개 중 어느 것도 쓰지 않는다.
- 이번에 바꾸는 규칙(fill 6·막대 2)을 리터럴로 무는 테스트는 없다. 확인한 곳은 `tests/run.sh`·`tests/mutations.tsv`·`tests/hub/*.py` 이고, DOM 테스트는 색을 읽지 않는다.
- 원 팔레트 결정(`docs/prps/hub-theme-and-usage-panel.md` 「확정된 전제 1」·「팔레트 — 파랑–주황 축」): 사용자 Claude Code 테마가 `dark-daltonized` 다.
  그래서 **파랑–주황 축 + 색 이외 채널(글리프·형태·글자)**로 설계했다.

## 3. 결정

### LT1 (개정 1) — 범위: 라이트 값 교체 + 새 토큰 3개 + 채움·막대 규칙 8개. 다크는 화면 무변경

- **개정 전**: 「두 템플릿의 라이트 `:root` 값만 바꾼다(규칙 0줄)」.
- **개정 사유**: 사용자 요구 2. 「쨍한」 금(L* 78~92)은 글자·테두리 토큰의 대비 하한을 못 넘는다. 이런 금은 **채움 면 + 짙은 글자**로만 화면에 올릴 수 있다(LT13).
  기존 6개 규칙은 채움과 글자를 `--accent-ink`·`--bg` 로 묶어 두었다. 다크에서 같은 화면을 지키면서 라이트에서만 둘을 바꾸려면 **역할 이름(토큰)이 새로 필요하다.**

| 항목 | 개수 | 내용 |
|---|---|---|
| 라이트 토큰 값 교체 | 13 | 두 파일의 맨몸 `:root`(§4.1). 이름·개수는 그대로다. |
| **새 토큰** | **3** | `--accent-fill`(채움 바탕 — 라이트는 금 그라데이션) · `--on-accent-fill`(채움 위 글자) · `--accent-bar`(막대 — 라이트는 금 그라데이션). 두 파일 × (라이트 값 1 + 다크 별칭 2) |
| **바뀌는 CSS 규칙** | **8** | 허브 2: `.badge.state-working`·`.usage-bar>span`. 대시보드 6: `li.active .num`·`li.active .chip`·`.matrix td.cell[data-state="active"]`·`.badge.pass`·`.dzf:checked + label`·`.bar-inner`. 바뀌는 선언은 `background`·`color` 뿐이다. |
| 바뀌지 않는 것 | — | 다크 블록의 기존 13개 토큰 값, 작업중 glow·테두리·포커스 링·열린 카드 규칙(LT14), JS, 파비콘(LT7) |

화려 강도(LT15, 권고 아님)를 고르면 토큰 1개(`--gloss-edge`)가 더 생기고, 막대 규칙 2개에 `box-shadow` 선언이 하나씩 붙는다.

### LT2 — 허브와 대시보드의 라이트 값을 같게 한다(옛 `--accent-soft` 차이도 없앤다)

대시보드는 허브 상세 패널 안 iframe 으로 허브 카드 바로 옆에 그려진다. 허브만 바꾸면 패널 안만 다른 색으로 남는다. 실제로 이미 한 번 어긋났다(§2).
새 토큰 3개(그라데이션 포함)도 두 파일이 **문자 단위로 같은 값**을 쓴다. T25-283 이 이를 고정한다(LT9).

### LT3 (개정 1) — 역할 분리: 면 · 글자 · 비텍스트 · **채움**

| 역할 | 토큰 | 기준 |
|---|---|---|
| 넓은 면 | `--bg` `--surface` `--soft` `--line` `--accent-soft` `--attention-soft` | 명도는 현행과 같은 급이다(bg L*≈95, surface ≈99, soft ≈97, line ≈88). 열린 카드 면 무게 ΔL* ≈ 4(현행 3.96). |
| 글자 | `--ink` `--head` `--muted` `--accent-ink` `--attention` | 11px 굵은 글자 기준 AA 4.5:1 이상. |
| 비텍스트 | `--accent` | 테두리·포커스 링·glow. 3:1 이상(bg·surface·accent-soft·soft 모두). |
| **채움(신설)** | `--accent-fill` + `--on-accent-fill`, `--accent-bar` | 밝은 금. 채움 위 글자는 **모든 그라데이션 정지점에서** 4.5:1 이상. 막대는 정지점 중 하나 이상이 트랙(`--soft`)과 3:1 이상. |

개정 1 은 글자·비텍스트 토큰도 **같은 대비 하한 안에서 덜 붉고 더 노란 쪽**으로 다시 골랐다.

| 토큰 | 개정 전 | 개정 1 | 바뀐 점 |
|---|---|---|---|
| `--accent` | `#A66B00` | `#A97300` | h 73.8°→77.1°, L* 50.2→52.6. 대비 하한 3:1 안에서 가장 밝은 쪽 |
| `--accent-ink` | `#7A4F00` | `#805700` | h 75.0°→77.8°, L* 37.4→40.3 |
| `--accent-soft` | `#F6E5B0` | `#FCE596` | 채도 C* 28.1→41.5. 무게 ΔL* 4.09→4.01 은 그대로다 |

### LT4 — 평상(accent)과 경고(attention)를 가르는 법: 경고를 **남보라 `#4B3F99`** 로 옮긴다

- **명도로는 못 가른다.** 둘 다 글자 역할이라 대비 때문에 L* 32~53 띠에 묶인다.
- **색상만 남는다.** 적록 색각이상(1형·2형, 남성 약 8%)은 빨강–초록 축(CIELAB a*)을 잃고 파랑–노랑 축(b*)을 남긴다.
  금색 계열은 b*>0 이므로, 경고는 **b*<0 쪽**에 있어야 이 사람들에게도 다른 색으로 남는다.
- 근거는 Machado·Oliveira·Fernandes(2009) 시뮬레이션(심도 1.0, 선형 sRGB)의 CIEDE2000 ΔE00 이다. 클수록 잘 갈리고, 약 10 아래는 작은 글자에서 혼동권이다.
  아래 표는 **개정 1 값으로 다시 계산했다.**

| 쌍 | 팔레트 | 정상 | 1형(P) | 2형(D) | 3형(T) |
|---|---|---|---|---|---|
| `--accent` ↔ `--attention` | 현행(파랑↔호박) | 47.3 | 49.2 | 53.3 | 52.1 |
| | **A 글로시** | 56.9 | 56.1 | 59.3 | 41.8 |
| `--accent-ink` ↔ `--attention` | 현행 | 46.4 | 46.3 | 52.3 | 57.9 |
| | **A 글로시** | 51.8 | 51.6 | 53.3 | 37.2 |
| 작업중 채움(`#FFC21A`) ↔ 한도 초과 채움(`#4B3F99`) | **A 글로시** | 75.4 | 72.1 | 75.8 | 56.0 |
| `--accent-soft` ↔ `--attention-soft`(실행중 칩 면 ↔ 실패 칩 면) | 현행 | 16.7 | 16.0 | 17.8 | 20.3 |
| | **A 글로시** | 31.1 | 30.2 | 29.0 | 13.8 |
| 기각안 X1: 경고를 호박 `#B45309` 로 둠 — 개정 전 A 의 accent `#A66B00` 기준 | | 12.6 | 5.5 | **2.3** | 7.1 |

- CIELAB b*(개정 1)
  - `--accent` +59.2, `--accent-ink` +48.5, `--accent-fill` 정지점 최소 +47.4(절제)·+31.4(화려), `--attention` −47.8.
  - 다크(무변경): accent −34.8, attention +74.7.
  - 평상·채움과 경고가 b* 축의 반대편에 있다. T25-282 ⑥ 이 이를 고정한다.
- 색 이외 채널은 그대로다. 글리프(● ○ ▲ ■ ◐ ✓ ◆ ⚠)·글자·형태(채움·점선·안쪽 링·윤곽)가 1차 채널이고 색은 훑어보기용 중복 채널이다.
  개정 1 은 채널 하나를 더한다. **평상·진행은 광택(그라데이션), 경고는 평면 단색**이다(LT11).
- **기존 결정과의 관계 — 부분 번복**: 「확정된 전제 1」(색각 안전 + b* 축 + 비색 채널)은 유지한다.
  번복하는 것은 라이트 테마의 역할 배정(파랑=평상·주황=경고 → 금=평상·남보라=경고)이다. 다크는 그대로라 **경고색이 테마마다 다르다**(사용자 결정 2 로 수용 확정).

### LT5 (개정 1) — 최종안: **A 「골드」 + 글로시(절제)**. B 「선셋」은 검토 대안

- **개정 전**: B 선셋 권고, A 골드 대안.
- **개정 사유**: 사용자가 A 를 고르고 「더 글로시하고 쨍한 금빛」을 요청했다. 개정 전 문서가 A 의 약점으로 적은 「금이 글자·테두리 명도에서 갈색이 된다」(옛 R3)를 LT13 이 직접 푼다.
  B 의 기록(토큰·대비·시뮬레이션)은 §11 에 보존한다.

### LT6 — 그림자 틴트: 남색 → 짙은 갈색, **휘도를 맞춘다**

`--shadow` 를 `0 8px 24px rgba(74,46,10,.06)` 로 바꾼다. 상대 휘도는 0.0326 → 0.0343 으로 같은 급이고, 같은 알파에서 그림자 꼬리 ΔL* 는 2.81 → 2.74 다.
그래서 299행 주석(그림자 꼬리 ΔL* 약 0.35, 식별 한계 아래)은 **수정 없이 참으로 남는다.**

### LT7 — 파비콘은 바꾸지 않는다(사용자 결정 3 — 확정)

파비콘(11행 `rgb(0,114,178)` 타일)은 두 테마 공통의 탭 표지다. `hub/README.md:259` 「파란 타일」은 참으로 남는다.

### LT8 (개정 1) — 주석 갱신 원칙과 위치(개정 1 값 기준)

- **원칙**
  - 「지금 규칙이 왜 이 값인가」를 말하는 수치는 새 값으로 다시 계산해 바꾼다.
  - 「옛 값·기각안이 왜 실패했나」를 말하는 이력 수치는 남기고 「(파랑 팔레트 시절)」을 붙인다.
  - 렌더 실측값(Blink)은 재측정하지 않고 같은 표기를 붙인다.
- **`:root`·다크 블록 안 주석의 함정**
  - T25-110·T25-282·T25-283 의 파서는 `:root\{(.*?)\}` 로 첫 `}` 까지를 블록으로 본다. 그러니 주석에 `{`·`}` 를 쓰면 안 된다.
  - `--토큰:#RRGGBB` 꼴 인용은 실제 선언을 덮어쓴다(dict 의 뒤 값이 남는다).
  - **T25-284 가 세는 별칭 리터럴(`--accent-fill:var(--accent-ink)` 등)을 주석에 인용하면 개수가 틀어진다.**
  - 옛 값을 말해야 하면 hex 만 쓰고 토큰은 이름만 쓴다.

| 파일:행 | 지금 주석이 말하는 것 | 처리(개정 1 값) |
|---|---|---|
| 허브 196-198(`:root` 주석) | accent-soft 공유·제약은 카드 | 그대로 둔다. 아래에 2~3줄을 더한다: 「라이트는 금빛 팔레트(결정 LT1~LT15, docs/prps/hub-light-theme-sunset.md) — 면은 밝게, 글자·테두리는 같은 계열의 깊은 값, 밝은 금은 채움 토큰(accent-fill·accent-bar)에만 싣고 그 위 글자를 짙게 뒤집는다(LT13). 경고는 b* 축 반대편 남보라. 값은 대시보드 템플릿과 같아야 한다(T25-283), 다크에서 새 토큰은 기존 토큰의 별칭이다(T25-284).」 위 함정을 지킨다. |
| 허브 319-320 | 옛 `#E4F0F8` 1.038:1·ΔL* 1.47 실패 | 이력 — 「(파랑 팔레트 시절)」. |
| 허브 321-323 | 천장: `#DAE9F7`(muted 4.60, ΔL* 3.96) / `#D2E4F5` 부터 4.38 | 「금빛 팔레트의 값은 `#FCE596`(muted 5.26:1, ΔL* 4.01)이다 — 천장(4.5:1)까지 여유가 있지만 면 무게를 파랑 팔레트(ΔL* 3.96)와 같은 급으로 맞췄다(결정 LT3)」. |
| 허브 324-326 | 「ΔL* 3.96 은…」·테두리 대비 4.64:1·4.19:1 | ΔL* 4.01, 테두리 배경 3.62:1·면색 3.27:1 — 결론(테두리를 함께 준다, 3:1 초과)은 그대로다. |
| 허브 330 | 다크 ΔL* 12.6 | 그대로 둔다. |
| 허브 405-412(상태 배지·작업중 배경 근거) | 「배경은 --accent-ink 를 쓴다 — `--accent(#0072B2)` 는 `--bg` 글자와 4.6:1…」 | **다시 쓴다**: 「배경은 `--accent-fill`(라이트: 밝은 금 그라데이션, 다크: `--accent-ink` 의 별칭), 글자는 `--on-accent-fill`(라이트: 짙은 금갈색, 다크: `--bg` 의 별칭)이다. 밝은 금은 밝은 글자와 대비가 안 나와(가장 진한 정지점 `#F2B300` 대 `--bg` 1.66:1) 글자를 짙게 뒤집는다 — 정지점 최저 7.40:1. 광택은 배경 그라데이션만으로 낸다. box-shadow·animation 은 T25-190(결정 V1)이 금지한다(결정 LT11·LT13).」 |
| 허브 416-420 | interrupted: 라이트 5.02:1·다크 7.3:1 / `--bg` 4.50:1 이라 안 씀 | 라이트 8.36:1·다크 7.3:1. `--bg` 문장은 「(파랑 팔레트 시절 4.50:1 로 AA 경계였다 — 지금은 7.54:1 이지만 규칙은 그대로 `--surface` 를 쓴다)」로 바꾼다. 경고는 광택 없는 평면 채움이다(LT11) — 한 구절을 더한다. |
| 허브 427 | state-background 라이트 5.87:1 | 5.12:1. 다크 7.52:1 은 그대로 둔다. |
| 허브 432-434 | 승인 대기: 흰 면의 근거 = 대비(4.06·4.39 미달) | 「흰 면을 고른 처음 이유는 대비였다(파랑 팔레트에서 투명 4.06:1·`--attention-soft` 4.39:1). 금빛 팔레트에서는 `--surface` 8.36·열린 행 6.80·`--attention-soft` 7.07(라이트)로 모두 넘지만, 흰 면 + 실선 링은 채움·점선과 갈리는 세 번째 형태라 그대로 둔다(결정 AW4)」. 다크 7.29 는 그대로 둔다. |
| 허브 487 | `--line` 이 열린 카드 면 위 ΔL* ≈2 로 사라진다 | 「ΔL* 약 2.9 로 식별 한계(약 2)를 간신히 넘을 뿐이라 약하다」 — 결론(`--line` 은 면 구분에 못 쓴다)은 같다. |
| 허브 1826·1949(JS 주석) | 「주황 안쪽 링」·「주황 글자 모양」 | 「경고색 안쪽 링」·「경고색 글자 모양」 — 라이트에서 경고가 남보라라 거짓이 됐다. 주석 단어만 바꾸고 JS 동작은 무변경이다. |
| 허브 553-555 | 기각안 근거 ΔL* 2.15·`--line` 면 글자 4.35:1 | 이력 — 「(파랑 팔레트 시절 실측)」. |
| 허브 555-556 | 열린 카드에서 ΔL* 5.47 / muted on soft 5.30:1·6.07:1 | 5.74 / 6.10:1·6.07:1. |
| 허브 686-687(`.usage-bar>span`) | (주석 없음) | 규칙 위에 1줄을 더한다: 「막대는 `--accent-bar`(라이트: 밝은 금 → 깊은 금 광택 — 아래 띠는 트랙과 3:1, T25-282 ⑦; 다크: `--accent` 별칭) — 결정 LT11·LT13.」 |
| 허브 299 | 그림자 꼬리 ΔL* 약 0.35 | 그대로 둔다(LT6). |
| 대시보드 72-77 | (주석 없음) | 값 교체 + 새 토큰 2줄. 위에 1줄: 「라이트 값은 hub_template.html 의 라이트 :root 와 같아야 한다(T25-283, 결정 LT2)」. 다크 두 블록에 별칭 1줄씩 더한다. |
| 대시보드 121(`.bar-inner`) | (주석 없음) | 허브 막대와 같은 1줄 주석. |
| 대시보드 151-152 | 「li.active .chip 은 --accent-ink 채움에 --bg 글자라…」 | 「…`--accent-fill` 채움에 `--on-accent-fill` 글자라…」 — 결론(배경·글자색을 애니메이션하지 않는다)은 그대로다. |
| 대시보드 158-159 | 「칩의 반전 채움(--accent-ink 바탕 + --bg 글자)」 | 「칩의 반전 채움(`--accent-fill` 바탕 + `--on-accent-fill` 글자 — 라이트는 광택 금)」. |
| 대시보드 162-163 | glow 실측 ΔL* 약 6.4 대 5.86 | 「(파랑 팔레트 시절 실측)」. glow 색 규칙은 바꾸지 않는다(LT14). |
| 대시보드 113 | 다크 `--accent` rgb | 그대로 둔다. |

### LT9 (개정 1) — 새 정적 가드 3개. T25-110 은 건드리지 않는다

T25-110 은 원장 **면제행**이다. 개정하면 변조행 승급 의무가 생기므로 그대로 두고, 새 관계는 별도 ID 로 T25-110 바로 뒤(`test_hub_docs_and_constants` 안)에 둔다.
판정 함수(상대 휘도·대비비·b*) 약 20줄이 T25-110 heredoc 과 일부 겹치는데, 승급을 피하는 값으로 감수한다(§9 X7).
세 가드는 **python heredoc 하나**에서 두 파일을 읽고 `pairs=…`·`parity=…`·`alias=…` 세 줄을 출력한다. 발화 줄은 가드마다 하나다.

- **T25-282 「라이트 의미 쌍 관계」** — 허브 첫 맨몸 `:root` 를 읽는다.
  - hex 토큰은 T25-110 과 같은 방식으로 뽑는다.
  - 그라데이션 토큰(`--accent-fill`·`--accent-bar`)은 `--이름:([^;]+);` 로 값을 잡은 뒤 그 안의 `#RRGGBB` 를 **정지점 목록**으로 뽑는다.

  | # | 관계 | 하한 | 지키는 규칙 |
  |---|---|---|---|
  | ① | contrast(`on-accent-fill`, `accent-fill` 의 **모든** 정지점) | 4.5 | 작업중 배지·진행중 번호·진행중 칩·PASS·필터 선택·매트릭스 진행 칸(개정 1 — 옛 ①「accent-ink/bg」 대체) |
  | ② | contrast(`accent-ink`, `accent-soft`) | 4.5 | 실행중 칩·백그라운드 배지·새 버전 버튼·대시보드 완료 칩 |
  | ③ | contrast(`attention`, `surface`) | 4.5 | 승인 대기 표지·한도 초과(반전) |
  | ④ | contrast(`attention`, `attention-soft`) | 4.5 | 소식 없음 배지·실패 칩·검수 FAIL |
  | ⑤ | contrast(`attention`, `accent-soft`) | 4.5 | 열린 카드 안 ▲ 새 기록 없음·⚠ 경고 |
  | ⑥ | b*(`accent`)·b*(`accent-ink`)·b*(`accent-fill` 정지점 전부) 와 b*(`attention`)의 **부호가 반대**이고, 모두 \|b*\| ≥ 20 | — | LT4 — 적록 색각이상에서도 평상·진행과 경고가 갈린다 |
  | ⑦ | max over `accent-bar` 정지점 contrast(정지점, `soft`) | 3.0 | 막대의 한 띠(아래쪽 깊은 금)가 트랙과 비텍스트 3:1 — 밝은 금만으로 된 막대가 트랙에 녹지 않게 |

  - 정지점이나 토큰을 못 찾으면 공허 통과가 아니라 실패로 보고한다(T25-189 관례).
  - 실패 메시지는 문제 목록을 `; ` 로 이은 한 줄이다.
  - 다크는 이 가드가 아니라 T25-284 가 맡는다.
- **T25-283 「허브·대시보드 라이트 토큰 불일치」** — 두 파일의 첫 맨몸 `:root` 에서 `--이름:값;` 선언을 **전부** 뽑아(이름이 `dzh-` 로 시작하는 허브 배치 토큰은 제외) 공백을 정규화한 dict 로 비교한다.
  값이 다른 이름과 한쪽에만 있는 이름을 나열한다. 그라데이션 문자열도 문자 단위로 같아야 한다.
- **T25-284 「다크 별칭」** — 두 파일 각각에서 다음 세 리터럴이 정확히 **2번씩**(다크 블록 두 벌) 나와야 한다.
  - `--accent-fill:var(--accent-ink)`
  - `--on-accent-fill:var(--bg)`
  - `--accent-bar:var(--accent)`

  화려를 고르면 `--gloss-edge:0 0 transparent` 도 같은 규칙으로 센다. 이 별칭이 있으면 바뀐 규칙 8개가 다크에서 **옛 규칙과 같은 계산값**으로 풀린다(LT12).
- 현행 값에서는 셋 다 실패한다. T25-282 는 새 토큰이 없고 ④·⑤ 도 미달이며, T25-283 은 accent-soft 가 불일치하고, T25-284 는 별칭이 0개다. 가드를 먼저 쓰면 자연히 RED 가 된다(§7).

**원장·상수 파급**: 번호는 병합 직전 develop 을 다시 센다(메모리 「동시 세션 주의」).

| 대상 | 변경 |
|---|---|
| 변조행 T25-282 | target `hub/bin/hub_template.html`, sed `s/--attention:#4B3F99;/--attention:#805700;/`. 경고를 평상 글자색과 같게 되돌리는 「의미 붕괴」 흉내다. 이때 ③ 6.29·④ 5.32·⑤ 5.12 는 통과하고 ⑥ 만 실패한다(검산). 그룹 `T25`, 토큰 `라이트 의미 쌍 관계`, 앵커 `test_hub_docs_and_constants`. 결함: 「라이트 --attention 이 금색 계열로 돌아가도 평상과 경고가 적록 색각이상에서 한 색으로 붙는 것을 잡지 못하는 것(결정 LT4 회귀)」 |
| 변조행 T25-283 | target `hub/bin/hub_dashboard_template.html`, sed `s/--accent:#A97300;/--accent:#0072B2;/`. 다크 줄은 `#56B4E9` 라 라이트 줄만 맞는다. 토큰 `허브·대시보드 라이트 토큰 불일치`. 결함: 「허브만 새 팔레트로 바꿔도 상세 패널 iframe 안만 옛 색으로 남는 것을 잡지 못하는 것(결정 LT2 회귀)」 |
| 변조행 T25-284 | target `hub/bin/hub_dashboard_template.html`, sed `s/--accent-fill:var(--accent-ink);//`. 줄마다 적용되므로 다크 두 블록에서 모두 빠진다. 그러면 다크 대시보드의 진행중 칩·PASS·필터가 라이트 금 그라데이션으로 그려진다. 토큰 `다크 별칭`. 결함: 「새 채움 토큰의 다크 별칭이 빠져 다크 화면이 바뀌어도 잡지 못하는 것(결정 LT12 회귀)」 |
| `LEDGER_MUTATION_ROW_FLOOR` | 133 → **136**. 이력 주석: 「133 → 136(hub-light-theme-sunset.md, 결정 LT2·LT4·LT9·LT12): 신규 가드 T25-282·T25-283·T25-284 의 변조행 3건. 순증가 3.」 |
| `SOURCE_GUARD_ID_FLOOR` | 559 → **562**. 같은 형식(collect_guard_ids 재현으로 편집 전 559·후 562 재측정) |
| `tests/mutations.tsv` 머리 인용 | 189-190행 `LEDGER_MUTATION_ROW_FLOOR(136 — …→133→136)`, 199행 `SOURCE_GUARD_ID_FLOOR(562 — …→559→562)` |
| T99-6 | sed 리터럴을 `s/LEDGER_MUTATION_ROW_FLOOR(136/LEDGER_MUTATION_ROW_FLOOR(138/` 로 옮긴다(옮기지 않으면 아무것도 바꾸지 않는 행이 된다) |
| `LEDGER_EXEMPT_ROW_RATCHET` | 무변경 |

### LT10 (개정 1) — 문서 갱신

- `hub/README.md`
  - 「화면 배치 › 전체 틀」(259행 근처)에 한 문장을 더한다: 「라이트 테마는 금빛 계열(크림 바탕·광택 있는 금색 채움·경고 남보라), 다크 테마는 남색 계열(강조 하늘·경고 주황)이다. 경고색은 테마마다 다르고, 상태는 색과 함께 글리프·글자·모양으로 갈린다.」
  - 색 이름 문구는 테마 중립으로 바꾼다. 43행·304행 「주황 테두리」 → 「경고색 테두리」, 320행 「주황 글씨」 → 「경고색 글씨」, 620행 「파란 알림 버튼」 → 「강조색 알림 버튼」.
  - 259행 파비콘 문구는 그대로 둔다.
- `docs/prps/hub-theme-and-usage-panel.md` 「팔레트 — 파랑–주황 축」 표 아래에 개정 표기를 단다. 그 PRP 의 「확장됨」과 같은 관례이고, 원문 줄은 지우지 않는다.
  「> **개정됨.** 라이트 팔레트는 hub-light-theme-sunset.md(결정 LT4·LT5·LT13)가 금빛 글로시로 바꿨다 — 축(b*)과 비색 채널 전제는 유지하고, 라이트에서 평상=금·경고=남보라로 역할을 뒤집었으며, 라이트 전용 채움 토큰 3개를 더했다(다크에서는 기존 토큰의 별칭). 다크는 이 표 그대로다.」
- `README.md:394` 설계 문서 수 88 → **89**. `VERSION` 은 건드리지 않는다.

### LT11 (신설) — 광택(글로시)을 어디에 쓰고 어디에 안 쓰는가

**쓴다** — 평상·진행·통과를 뜻하는 **작은 채움**과 **진행 막대**. 위→아래 `linear-gradient(180deg, …)` 이고, 밝은 띠 → 쨍한 금 → 깊은 금 순서다(위에서 빛이 드는 금속).

| 대상 | 규칙 | 토큰 |
|---|---|---|
| 작업중 배지(허브) | `.badge.state-working` | `--accent-fill` / `--on-accent-fill` |
| 진행중 번호·진행중 칩(대시보드) | `li.active .num` · `li.active .chip` | 같음 |
| 매트릭스 진행 칸 | `.matrix td.cell[data-state="active"]` | 같음 |
| 검수 PASS 배지 | `.badge.pass` | 같음 |
| 필터 선택 알약 | `.dzf:checked + label` | 같음(테두리는 `--accent-ink` 그대로 → 금화 테두리처럼 보인다) |
| 사용량 막대·진행 막대 | `.usage-bar>span` · `.bar-inner` | `--accent-bar` |

**안 쓴다**
- **경고 표지 전부**(한도 초과 채움·소식 없음·승인 대기·실패 칩·FAIL·⚠). 평면 단색이 경고의 형태 채널이 된다.
- **넓은 면**(열린 카드·세션 행·패널). 340px 카드에 그라데이션을 깔면 번들거리고 촌스럽다. 열린 카드 면은 T25-110 이 `background:var(--accent-soft)` 와 hex 값을 고정하는 자리이고, `--muted` 본문 대비도 걸려 있다.
- **옅은 면 위 작은 글자 칩**(실행중 칩·백그라운드 배지·새 버전 버튼·완료 칩).
- **테두리·포커스 링·glow**(LT14).
- **작업중 배지의 box-shadow**(T25-190 — 결정 V1). 그래서 광택은 배경 그라데이션만으로 낸다.

### LT12 (신설) — 다크 화면 무변경의 보장 방식

1. **구조**: 새 토큰 3개는 다크 블록 두 벌(두 파일)에서 **기존 토큰의 별칭**이다.
   - 정의: `--accent-fill:var(--accent-ink);--on-accent-fill:var(--bg);--accent-bar:var(--accent)`
   - 바뀐 규칙 8개의 다크 계산값은 별칭 때문에 옛 규칙과 정확히 같다.
     - `background:var(--accent-fill)` → `var(--accent-ink)` → `#8ACBF0`
     - `color:var(--on-accent-fill)` → `var(--bg)` → `#0E1621`
     - 막대 `var(--accent-bar)` → `#56B4E9`
   - 사용자 정의 속성은 `:root` 에서 계산된 값으로 상속되므로, 하위 요소가 받는 값은 다크 블록의 기존 토큰 값이다.
   - hex 를 복제하지 않고 `var()` 로 가리키는 이유가 있다. 나중에 다크 팔레트를 바꿔도 별칭이 따라가서 **어긋날 수 없다.**
2. **정적 가드**: T25-284(LT9)가 별칭 리터럴이 파일마다 2번씩 있는지 고정한다.
3. **설계 단계 실증(완료)**: §5 의 구현형을 목업에 넣고 다크로 그려 현행 다크와 비교했다. 허브(작업중 배지·사용량 막대 포함)와 대시보드(진행중 칩·PASS·필터·진행 막대 포함) 스크린샷이 **SHA-1 까지 같았다.**
   - 허브: `a0dfc175…` = 현행 = 절제 = 화려
   - 대시보드: `fd9b3211…` 셋 다 같다
   - 같은 구현형의 라이트 렌더는 §6 미리보기 블록의 라이트 렌더와도 해시가 같았다. 즉 §5 와 §6 이 같은 화면을 만든다.
4. **구현 단계 1회 확인**: 같은 방식(`build_mock2.py` 의 다크 페이지 해시 비교)을 **실제 고친 템플릿**으로 한 번 더 돌려 구현 보고에 적는다. 영구 DOM 테스트는 만들지 않는다 — 다크 값을 동결하는 테스트가 되기 때문이고, 구조 보장은 1·2 가 맡는다.

### LT13 (신설, §9 옛 X2 「밝은 금 전용 토큰」 기각의 번복) — 밝은 금은 채움에, 그 위 글자는 짙게 뒤집는다

- **옛 기각 사유**: 「YAGNI — 규칙 수정과 다크 값 정의가 따라오는데 지금 역할 분리로 대비가 충족된다」.
  사용자 요구 2 가 그 「필요」를 만들었고, 다크 값 문제는 LT12 의 별칭으로 비용 없이 풀린다.
- **쨍한 금(L* 78~92)과 글자 대비**
  - 흰 계열 글자와는 1.0~1.8:1 이다(가장 진한 정지점 `#F2B300` 대 `--bg` 1.66:1).
  - 짙은 금갈색 `#3B2A00` 을 올리면 7.4~11.1:1 이다.
  - 그래서 6개 채움 규칙의 글자를 `--bg` 에서 `--on-accent-fill` 로 바꾼다.
- `--on-accent-fill` 을 `--ink` 로 대신하지 않는 이유: 다크에서 `--ink` 는 밝은 글자(`#E6EDF5`)라 다크 채움 위 글자를 바꿔 버린다. 다크 별칭이 `--bg` 인 별도 이름이 필요하다.
- `--accent-bar` 를 `--accent-fill` 과 나누는 이유는 두 가지다.
  - 다크 별칭이 다르다(막대 `--accent` · 채움 `--accent-ink`).
  - 라이트 정지점 조건도 다르다. 채움은 글자가 놓이므로 **가장 진한 정지점도 글자와 4.5:1** 이어야 하고, 막대는 글자가 없어 아래 띠를 `--accent` 까지 내려 **트랙과 3:1** 을 만든다.
- 작업중 배지의 경계 대비(금 채움 대 흰 카드 1.2~1.8:1)는 낮다. 정보는 배지 안 글자(7.4:1 이상)·글리프·채도가 운반하므로 WCAG 1.4.11 대상이 아니다.
  작업중 상태는 카드 테두리(3.62:1)와 glow 가 함께 신호한다.

### LT14 (신설) — 작업중 glow·테두리·포커스는 `--accent`(깊은 금) 그대로 — 밝은 금 glow 는 기각

- 밝은 금 glow(`#F5B700`)는 크림 바탕과 ΔL* 17 이다. 깊은 금 `--accent`(`#A97300`)는 ΔL* 43 이라, 밝은 glow 로 바꾸면 「지금 작업중인 카드」 스캔 신호(R3·결정 D4)가 **약해진다.**
- glow 규칙의 `var(--accent)` 는 T25-189(정규식)·T25-221(리터럴)이 무는 변조행 대상이다. 바꾸면 두 가드의 본문과 원장 sed 를 함께 고쳐야 한다.
  신호가 약해지는 변경에 그 비용을 쓰지 않는다. 목업에서 깊은 금 glow 는 「금빛 후광」으로 읽힌다.

### LT15 (신설) — 광택 강도: **절제(권고)** / 화려

| | 절제(권고) | 화려 |
|---|---|---|
| `--accent-fill` | `linear-gradient(180deg,#FFE58A 0%,#FFC21A 55%,#F2B300 100%)` | `linear-gradient(180deg,#FFF0B3 0%,#FFD54A 30%,#F5B700 62%,#E3A600 100%)` |
| `--accent-bar` | `linear-gradient(180deg,#FFD54A 0%,#F2B300 55%,#A97300 100%)` | `linear-gradient(180deg,#FFF0B3 0%,#FFC21A 40%,#E3A600 75%,#A97300 100%)` |
| 막대 윗면 하이라이트 | 없음 | `--gloss-edge:inset 0 1px 0 rgba(255,255,255,.65)` 를 막대 2개에 `box-shadow` 로(작업중 배지에는 T25-190 때문에 못 붙인다). 다크 별칭 `0 0 transparent` |
| 채움 위 글자 최저 대비 | 7.40:1 | 6.41:1 |
| 추가 비용 | — | 토큰 +1, 막대 규칙 2개에 선언 +1, T25-284 리터럴 +1 |

절제를 권고한다. 확대 비교(`mock2/zoom.png`)에서 두 강도의 차이는 알약 윗부분의 흰 띠와 막대 윗선 정도로 작다.
화려는 칩마다 흰 반사띠가 생겨 화면 전체가 번들거리고, 그만큼 사람이 「촌스럽다」고 느끼기 쉬운 쪽으로 간다. 글자 대비 여유도 줄어든다(7.40 → 6.41).
「더 반짝여야 한다」면 같은 구조에서 정지점만 바꾸면 되므로 나중에 올리기 쉽다.

## 4. 데이터 모델 — 토큰 표와 대비표

### 4.1 라이트 토큰(최종: A 글로시 절제)

| 토큰 | 현행 | A 직전 | **A 글로시** | 역할 |
|---|---|---|---|---|
| `--bg` | `#EEF3F8` | `#F8F1DE` | `#F8F1DE` | 크림 바탕 |
| `--surface` | `#FFFFFF` | `#FFFDF7` | `#FFFDF7` | 아이보리 면 |
| `--ink` | `#172033` | `#2B2214` | `#2B2214` | 본문 |
| `--head` | `#12335B` | `#4A2E0A` | `#4A2E0A` | 제목(짙은 갈색) |
| `--muted` | `#5A6879` | `#6A5B44` | `#6A5B44` | 보조 글자 |
| `--line` | `#D9E2EC` | `#E8DDC2` | `#E8DDC2` | 테두리 |
| `--soft` | `#F4F7FB` | `#FBF6E9` | `#FBF6E9` | 칩·막대 트랙 면 |
| `--accent` | `#0072B2` | `#A66B00` | **`#A97300`** | 테두리·포커스·glow(깊은 금) |
| `--accent-ink` | `#005B8F` | `#7A4F00` | **`#805700`** | 강조 글자(금갈) |
| `--accent-soft` | `#DAE9F7`(대시보드 `#E4F0F8`) | `#F6E5B0` | **`#FCE596`** | 열린 카드·실행중 칩 면(쨍한 연금) |
| `--attention` | `#B45309` | `#4B3F99` | `#4B3F99` | 경고(남보라) |
| `--attention-soft` | `#FBEEDC` | `#ECE8F8` | `#ECE8F8` | 경고 면 |
| `--shadow` | `0 8px 24px rgba(19,51,91,.06)` | 같은 틴트 | `0 8px 24px rgba(74,46,10,.06)` | 카드 그림자(LT6) |
| **`--accent-fill`** | — | — | `linear-gradient(180deg,#FFE58A 0%,#FFC21A 55%,#F2B300 100%)` | 채움 바탕(LT11·LT13) |
| **`--on-accent-fill`** | — | — | `#3B2A00` | 채움 위 글자 |
| **`--accent-bar`** | — | — | `linear-gradient(180deg,#FFD54A 0%,#F2B300 55%,#A97300 100%)` | 막대 |

다크(두 블록, 두 파일)에서 기존 13개는 무변경이다. 새 3개는 `--accent-fill:var(--accent-ink);--on-accent-fill:var(--bg);--accent-bar:var(--accent)` 별칭이다.

### 4.2 대비표(WCAG 대비비, 계산 — `!` 는 하한 미달)

| 쌍 | 하한 | 현행 | **A 글로시** | 쓰임 |
|---|---|---|---|---|
| ink / bg | 7 | 14.57 | 13.88 | 본문 |
| ink / surface | 7 | 16.27 | 15.39 | 카드 본문 |
| muted / surface | 4.5 | 5.69 | 6.47 | `.path`·`.session-time` |
| muted / bg | 4.5 | 5.10 | 5.83 | `.foot`·패널 본문 |
| muted / soft | 4.5 | 5.30 | 6.10 | 칩·`state-idle` |
| muted / accent-soft | 4.5 | 4.60 | 5.26 | 열린 카드 본문(T25-110 ①) |
| head / bg | 7 | 11.40 | 11.05 | h1 |
| head / surface | 7 | 12.72 | 12.24 | 프로젝트명 |
| head / accent-soft | 7 | 10.29 | 9.95 | 열린 카드의 프로젝트명 |
| accent / bg | 3 | 4.64 | 3.62 | 테두리(T25-110 ③) |
| accent / surface | 3 | 5.19 | 4.02 | hover 테두리·포커스 링 |
| accent / accent-soft | 3 | 4.19 | 3.27 | 열린 카드 테두리 vs 면 |
| accent-ink / surface | 4.5 | 7.26 | 6.29 | 진행률·사용량 % 글자 |
| accent-ink / bg | 4.5 | 6.50 | 5.68 | 패널 안 강조 글자 |
| accent-ink / accent-soft | 4.5 | 5.87 | 5.12 | 실행중 칩·백그라운드 배지 |
| **on-accent-fill / fill 정지점** `#FFE58A`·`#FFC21A`·`#F2B300` | 4.5 | (옛 bg/accent-ink 6.50) | 11.09 · 8.56 · **7.40** | 작업중 배지·진행중 칩·PASS·필터 |
| **bar 정지점 / soft** `#FFD54A`·`#F2B300`·`#A97300` | 3(최댓값) | (옛 accent/soft 4.83) | 1.31 · 1.73 · **3.79** | 막대 아래 띠 vs 트랙 |
| 필터 테두리 accent-ink / fill 최진 정지점 | — | — | 3.42 | 금화 테두리(장식) |
| attention / surface | 4.5 | 5.02 | 8.36 | 승인 대기·한도 초과(반전) |
| attention / bg | 4.5 | 4.50 | 7.54 | 패널 안내 줄 |
| attention / attention-soft | 4.5 | 4.39 ! | 7.07 | 소식 없음·실패 칩·FAIL |
| attention / accent-soft | 4.5 | 4.06 ! | 6.80 | 열린 카드 안 경고 글자 |

- **T25-110 세 부등식**: 현행 4.60 / ΔL* 3.96 / 4.64. **A 글로시 5.26 · 4.01 · 3.62 — 그대로 통과한다.** 그라데이션 토큰은 이 파서에 걸리지 않는다.
- T25-282 ①~⑦ 은 A 글로시에서 모두 통과한다. 화려도 ① 최저 6.41·⑦ 3.79 로 통과한다.
- 장식 대비는 현행과 같은 급이다: line/surface 1.33, soft/surface 1.06.
- 제목 hover(`--head` → `--accent-ink`) ΔE00 은 16.8 이다(현행 14.5).

## 5. 인터페이스 — 구현형

공개 함수·데이터 계약(`#dzh-data`)·파이썬 시그니처는 변경이 없다. 바뀌는 인터페이스는 CSS 사용자 정의 속성(값 13 + 신설 3)과 아래 규칙 8개다.
**두 파일에 같은 글자로** 넣는다(허브에는 대시보드 셀렉터가, 대시보드에는 허브 셀렉터가 없으므로 해당 파일에 있는 규칙만 고친다).

라이트 맨몸 `:root`(현재 줄 배치를 유지하고, 새 토큰은 accent 줄 다음에 둔다):
```css
    --bg:#F8F1DE;--surface:#FFFDF7;--ink:#2B2214;--head:#4A2E0A;--muted:#6A5B44;
    --line:#E8DDC2;--soft:#FBF6E9;
    --accent:#A97300;--accent-ink:#805700;--accent-soft:#FCE596;
    --accent-fill:linear-gradient(180deg,#FFE58A 0%,#FFC21A 55%,#F2B300 100%);--on-accent-fill:#3B2A00;
    --accent-bar:linear-gradient(180deg,#FFD54A 0%,#F2B300 55%,#A97300 100%);
    --attention:#4B3F99;--attention-soft:#ECE8F8;
    --shadow:0 8px 24px rgba(74,46,10,.06);
```

다크 두 블록 각각(기존 줄은 그대로 두고 1줄을 더한다):
```css
      --accent-fill:var(--accent-ink);--on-accent-fill:var(--bg);--accent-bar:var(--accent);
```

규칙(바뀌는 선언만 — 나머지 선언은 원문 그대로):
```css
/* 허브 */
.badge.state-working{background:var(--accent-fill);color:var(--on-accent-fill)}
.usage-bar>span{display:block;height:100%;background:var(--accent-bar);border-radius:999px}
/* 대시보드 */
.bar-inner{height:100%;background:var(--accent-bar);border-radius:999px;transition:width .4s}
li.active .num{background:var(--accent-fill);color:var(--on-accent-fill)}
li.active .chip{position:relative;background:var(--accent-fill);color:var(--on-accent-fill)}
.matrix td.cell[data-state="active"]{background:var(--accent-fill);color:var(--on-accent-fill)}
.badge.pass{background:var(--accent-fill);color:var(--on-accent-fill)}
.dzf:checked + label{background:var(--accent-fill);color:var(--on-accent-fill);border-color:var(--accent-ink)}
```

화려를 고르면 다음이 바뀐다.
- `--accent-fill`·`--accent-bar` 를 LT15 의 화려 값으로 바꾼다.
- 라이트에 `--gloss-edge:inset 0 1px 0 rgba(255,255,255,.65)`, 다크 두 블록에 `--gloss-edge:0 0 transparent` 를 더한다.
- 막대 규칙 2개에 `box-shadow:var(--gloss-edge)` 를 붙인다.

새 가드 3개는 `tests/run.sh` 안 bash + `python3 -` heredoc 하나다. 새 파일·새 모듈·새 의존성은 없다.

## 6. 실화면 미리보기용 덮어쓰기 블록(복사해 그대로 주입)

허브·대시보드 페이지의 `</head>` 앞에 `<style>` 로 끼운다. 모든 셀렉터에 `:root:not([data-theme="dark"])` 접두가 붙어 **라이트에만** 걸린다.
- 접두 규칙의 명시도는 원 규칙보다 높다(예: (0,4,0) > (0,2,0)).
- 머리 IIFE 가 `data-theme` 를 항상 붙이므로 다크에는 닿지 않는다(localStorage 가 막혀 속성이 비면 시스템 다크에서 걸릴 수 있다 — 미리보기만의 한계).
- 허브에 대시보드 셀렉터가, 대시보드에 허브 셀렉터가 섞여 있어도 무해하다. 한 블록을 양쪽에 그대로 넣으면 된다.
- 목업이 정확히 이 글자를 썼다(출처 `…/scratchpad/gloss_css.py`). §5 구현형과 라이트 렌더 해시가 같다(LT12-3).

**절제(권고)**:
```css
:root:not([data-theme="dark"]){--bg:#F8F1DE;--surface:#FFFDF7;--ink:#2B2214;--head:#4A2E0A;--muted:#6A5B44;--line:#E8DDC2;--soft:#FBF6E9;--accent:#A97300;--accent-ink:#805700;--accent-soft:#FCE596;--attention:#4B3F99;--attention-soft:#ECE8F8;--shadow:0 8px 24px rgba(74,46,10,.06);--on-accent-fill:#3B2A00;--accent-fill:linear-gradient(180deg,#FFE58A 0%,#FFC21A 55%,#F2B300 100%);--accent-bar:linear-gradient(180deg,#FFD54A 0%,#F2B300 55%,#A97300 100%)}
:root:not([data-theme="dark"]) .badge.state-working{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .usage-bar>span{background:var(--accent-bar)}
:root:not([data-theme="dark"]) li.active .num{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) li.active .chip{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .matrix td.cell[data-state="active"]{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .badge.pass{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .dzf:checked + label{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .bar-inner{background:var(--accent-bar)}
```

**화려**:
```css
:root:not([data-theme="dark"]){--bg:#F8F1DE;--surface:#FFFDF7;--ink:#2B2214;--head:#4A2E0A;--muted:#6A5B44;--line:#E8DDC2;--soft:#FBF6E9;--accent:#A97300;--accent-ink:#805700;--accent-soft:#FCE596;--attention:#4B3F99;--attention-soft:#ECE8F8;--shadow:0 8px 24px rgba(74,46,10,.06);--on-accent-fill:#3B2A00;--accent-fill:linear-gradient(180deg,#FFF0B3 0%,#FFD54A 30%,#F5B700 62%,#E3A600 100%);--accent-bar:linear-gradient(180deg,#FFF0B3 0%,#FFC21A 40%,#E3A600 75%,#A97300 100%);--gloss-edge:inset 0 1px 0 rgba(255,255,255,.65)}
:root:not([data-theme="dark"]) .badge.state-working{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .usage-bar>span{background:var(--accent-bar);box-shadow:var(--gloss-edge)}
:root:not([data-theme="dark"]) li.active .num{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) li.active .chip{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .matrix td.cell[data-state="active"]{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .badge.pass{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .dzf:checked + label{background:var(--accent-fill);color:var(--on-accent-fill)}
:root:not([data-theme="dark"]) .bar-inner{background:var(--accent-bar);box-shadow:var(--gloss-edge)}
```

## 7. 테스트 계획

이 변경의 「순수 로직」은 색 관계다. 정적 가드 T25-282~284 가 이를 맡는다. 새 파이썬 모듈이 없으므로 새 단위 테스트 파일도 없다.

1. **RED**: T25-282·283·284 를 먼저 쓰고 `bash tests/run.sh --only T25` 를 돌린다. 현행 값에서 다음 세 실패가 나야 한다.
   - T25-282: `accent-fill` 토큰 없음 · ④ 4.39 · ⑤ 4.06
   - T25-283: `accent-soft` 불일치
   - T25-284: 별칭 0개
2. **GREEN**: §5 대로 두 템플릿을 고치고 `--only T25`·`--only T22` 를 돌린다. 다음 기존 가드는 **무변경으로 통과해야 한다.**
   - T25-110(세 부등식 + card-open 리터럴)
   - T25-190(작업중 배지에 box-shadow·animation 없음 — 그라데이션은 걸리지 않는다)
   - T25-189·T25-221(glow 규칙 무변경)
   - T25-29·T22-27·T22-117(금지 리터럴·토큰 이름)
   - T25-47(파비콘), T25-274, T25-280·281, T22-164·167·170a·170b(진행중 칩 halo·밴드 — `li.active .chip` 의 `position:relative` 유지)
3. **일부러 깨뜨려 확인**(구현 보고에 결과를 적는다)
   - 원장 세 sed 를 각각 사본에 적용한다. T25-282 변조는 T25-282 의 ⑥ 만 발화하되 허브만 바뀌어 T25-283 도 함께 발화한다(구조상 불가피 — 실측), T25-283 변조는 T25-283 만, T25-284 변조는 T25-284 만 발화해야 한다.
   - 손으로 확인할 것 두 가지.
     - `--on-accent-fill` 을 `#F8F1DE` 로 바꾸면 ① 이 발화해야 한다.
     - `--accent-bar` 의 마지막 정지점을 `#F2B300` 으로 바꾸면 ⑦ 이 발화해야 한다.
   - 원장 행 자격은 T37-13 으로 확인한다. 전체 T37 은 커밋 직전 메인 세션의 전체 검증 1회에 맡긴다.
4. **다크 무변경 1회 확인(LT12-4)**: `build_mock2.py` 의 다크 페이지를 고친 템플릿으로 다시 구워, 현행 다크와 스크린샷 해시가 같은지 구현 보고에 적는다.
5. **주석 수치**: LT8 표의 새 수치를 같은 식으로 다시 계산해 일치를 확인한다(검수자 대조 항목). 검산은 `…/scratchpad/evaluate.py palettes_gloss.json` 이다.
6. **DOM·단위 스위트**: 색을 단언하는 테스트가 없어 영향이 없을 것으로 본다. 전체 `python3 -m unittest discover -s tests/hub -t .` 는 커밋 직전 메인 세션이 1회 돌린다.
7. **실화면 확인**(자동화 대상 아님): 메인 세션이 실데이터 허브에 §6 블록을 끼워 확인한다.
   볼 곳은 작업중 glow·열린 카드·상세 패널 안 대시보드·사용량 막대·연결 끊김 버튼·hover·포커스 링이다. 목업에는 hover·포커스·연결 끊김이 없다.

## 8. 마일스톤

| M | 내용 | 결정 | 검증 |
|---|---|---|---|
| M1 | T25-282·283·284 신설(RED) + 원장 3행·바닥 상수·머리 인용·T99-6 | LT9 | `--only T25` RED(§7-1) · T37-13 |
| M2 | 두 템플릿: 라이트 값 + 새 토큰 + 다크 별칭 + 규칙 8 | LT1~LT6·LT11~LT15 | `--only T25`·`--only T22` GREEN · §7-3 · §7-4 |
| M3 | 템플릿 주석(LT8 표) | LT8 | 검수자 대조 |
| M4 | `hub/README.md` 문구 · 이전 PRP 개정 표기 · `README.md` 문서 수 | LT10 | 문서 grep |

## 9. 위험과 대안

### 9.1 위험

- **R1 테마 간 경고색 불일치**: 라이트는 남보라, 다크는 주황이다. 사용자 결정 2 로 수용했다. 각 테마 안에서는 일관되고, 글리프·글자·형태가 같으며, README 에 밝힌다.
- **R2 남보라가 「경고」로 읽히는가**: 금빛 화면에서 유일한 차가운 색이고, 개정 1 에서는 유일한 **평면** 채움이라 오히려 두드러진다. 의미는 글리프·글자가 1차 채널이다.
- **R3 (개정 1) 광택이 촌스러워질 위험**: LT11 의 「안 쓴다」 목록으로 범위를 작은 채움·막대로 제한했다. 강도도 절제를 권고한다. 넓은 면에는 쓰지 않는다.
- **R4 주석 수치 썩음**: LT8 표가 전수이고(두 템플릿에서 `:1`·`ΔL*`·hex·`--accent-ink 채움` 류 서술을 grep 으로 확인), 검수 대조 항목으로 둔다.
- **R5 검사 시간**: 변조행 3개가 전체 검사의 T37 미러 실행을 3회 늘린다(사용자 결정 4 — 변조행 확정).
- **R6 번호 충돌**: T25-282~284 는 병합 직전 develop 을 다시 센다.
- **R7 작업중 배지의 경계가 옅어진다**: 금 채움 대 흰 카드 1.2~1.8:1 이다. 배지 정보는 안쪽 글자 7.4:1 이상이 운반하고, 카드 테두리·glow 가 함께 신호한다(LT13).
- **R8 별칭의 가정**: 새 토큰을 나중에 다른 규칙이 쓰기 시작하면, 다크에서 별칭 값(옛 `--accent-ink`·`--bg`·`--accent`)이 그 규칙에 맞는지 다시 봐야 한다.
  토큰 이름에 라이트 의미(채움·막대)를 실었고, `:root` 주석에 「다크에서는 기존 토큰의 별칭」을 적어 둔다.

### 9.2 검토했으나 채택하지 않은 대안

- **X1 경고는 호박으로 두고 형태 채널에만 기댄다** — 기각. 평상과 경고가 1형·2형 시뮬레이션에서 ΔE00 2.3~5.5 로 같은 색이 된다(LT4 표). 글자색만 쓰는 경고 자리도 있다.
- **X2 (번복됨 → LT13)** 밝은 금 전용 토큰: 개정 전 YAGNI 로 기각했다. 사용자 요구 2 로 필요가 생겼고, 다크 비용은 별칭으로 0 이 됐다.
- **X3 허브만 바꾸기** — 기각(LT2).
- **X6 경고를 진홍·자두로** — 기각. b* 가 0 근처라 진홍 `#A3245C` 가 금색 글자 `#805700` 과 2형에서 ΔE00 19.6, 3형에서 12.1 로 붙는다(남보라는 53.3·37.2).
- **X7 새 관계를 T25-110 heredoc 에 합치기** — 기각. T25-110 을 개정하면 변조행 승급 의무가 생긴다.
- **X8 파비콘 `media` 속성** — 기각(LT7).
- **X9 (신설) 밝은 금 glow** — 기각(LT14). 크림 위 ΔL* 17 대 43 으로 작업중 신호가 약해지고, 변조행 가드 2개(T25-189·221)의 개정이 따라온다.
- **X10 (신설) 열린 카드 면에도 금 그라데이션** — 기각. T25-110 이 면을 hex 토큰·리터럴로 고정하고, `--muted` 본문의 대비가 가장 진한 정지점에 묶이며, 넓은 면의 광택은 촌스럽다(LT11).
- **X11 (신설) 글자·테두리 토큰을 밝은 금으로(값만 교체 유지)** — 불가. 밝은 금은 bg 대비 1.0~1.7:1 이라 T25-110 ③(3:1)·AA(4.5:1)를 못 넘는다.

## 10. 사용자 결정

확정됨: ① 안 A 골드(+ 글로시) · ② 경고색 라이트 남보라 / 다크 주황 유지 · ③ 파비콘 파랑 유지 · ④ 새 검사는 변조행.

⑤ 광택 강도 **화려**(2026-10-15 승인 — 권고는 절제였다). 구현은 §5 구현형에 「화려를 고르면」 목록(LT15 값·`--gloss-edge` 토큰·막대 2개 `box-shadow`)을 적용한 형태다.

남은 결정: 없음.

## 11. 부록 — 검토 대안 안 B 「선셋」(채택하지 않음, 개정 전 권고안의 기록)

| 토큰 | B 값 |
|---|---|
| `--bg` `--surface` `--ink` `--head` `--muted` | `#FBF0E8` `#FFFCF9` `#2D1C17` `#5A2330` `#6E5A55` |
| `--line` `--soft` | `#EED9CB` `#FDF5EF` |
| `--accent` `--accent-ink` `--accent-soft` | `#C8501F` `#8F3412` `#FAE0CF` |
| `--attention` `--attention-soft` | `#4B3F99` `#ECE8F8` |
| `--shadow` | `0 8px 24px rgba(90,35,48,.06)` |

- 살구 바탕·노을 주황 강조·와인 제목·남보라 경고로, 토큰 값만 바꾸는 안이었다.
- T25-110 은 5.11 / ΔL* 4.59 / 4.05 다.
- 평상↔경고 ΔE00(정상/P/D/T): accent 45.7/51.4/57.7/47.2, accent-ink 40.6/47.5/50.9/42.4.
- 기각안 X6 의 근거 수치: 진홍 `#A3245C` 대 B accent-ink 는 2형 18.2·3형 5.3 이다.
- 개정 전 비교 목업은 `…/scratchpad/mock/mock-compare.png` 이다.
- 사용자가 A 를 골라 채택하지 않았다.
