> ⚠️ **실험 원본 — 승인된 설계가 아니다.**
> 이 문서는 모델·프롬프트 A/B 실험의 **실험 2 · ON(opus + 무스캐폴딩) · 42/50 · 1위** 산출물이다.
> 여기 설계된 기능은 구현되지 않았고, 앞으로 구현할 계획도 없다.
> **저장소 선례로 인용하지 않는다.** 실험 설계·채점·결론은
> [`../model-scaffolding-ab-experiments.md`](../model-scaffolding-ab-experiments.md) 를 본다.
> 본문은 이 배너 블록 아래부터 서브에이전트 원본 그대로다(내용 무수정).

---

# 단계별 소요 시간 (PRP) — `/dashboard`

> 대상 저장소: `/Users/dev/private/project/coding-harness` (기준 커밋 `07857ef`)
> 산출물 경로(구현 시): `docs/prps/dashboard-step-timing.md`

---

## 0. 착수 전 필수 — 이 기능은 저장소가 **이미 기각한 기능**과 겹친다

**구현에 착수하기 전 사용자 승인이 반드시 필요하다.** 아래는 추측이 아니라 코드·커밋·테스트에 남은 기록이다.

| 근거 | 내용 |
|------|------|
| 커밋 `1b199cb` 메시지 | "「지금」 카드를 경과/마지막 기록/다음 3행으로 재설계했다가, **검증 스크린샷 검토 후 정보 자체가 불필요하다는 판단**으로 카드와 전용 코드(렌더 함수 4종, `data-started-at` 각인 로직, 불변식 7)를 완전히 제거 — 현재 작업 내용은 단계 목록의 활성 항목 상세(`.step-detail`) 한 줄로 충분하다." |
| `docs/prps/impl-panel-dispatch-unit-and-session-meta-chips.md:290-297` | **결정 DU6 — 경과 시간·타이머·「지금」 카드를 재도입하지 않는다.** "이미 만들었다가 사용자 판단으로 제거된 자산" |
| 같은 문서 `:54` | 성공 기준 **S5 — 「지금」 카드·경과 타이머가 부활하지 않았다** (기존 T22-61·T22-96 통과 유지) |
| 같은 문서 `:111` | 비목표 표: **경과 시간·타이머·「지금」 카드** — "T22-61·T22-96 이 부활을 막는 역방향 검사다" |
| `tests/run.sh:1779-1786` | **T22-96(역방향)** — `dz-now-card`·`dz-now-elapsed`·`dz-now-since`·`dz-now-next`·`renderNowCard`·**`data-started-at`**·`now-row`·`now-label`·`now-value`·`now-title` 중 어느 문자열도 파일에 있으면 실패 |
| `tests/run.sh:1514-1523` | **T22-61(역방향)** — `dz-current` 계열 셀렉터·규약 인자 부활 시 실패 |

DU6 은 이번 요청(`/dashboard` 에 단계별 소요 시간)을 **정면으로 금지**한다. 그러므로 이 PRP 의 첫 결정은 기능 설계가 아니라 **DU6 의 부분 번복 제안**이다. 이 저장소는 전제가 바뀌면 결정을 공개적으로 뒤집는 관례를 갖고 있다(`dashboard.md:772-773`: `SP19`가 `SP4`를, `hub-session-revival`의 `RV1`이 `done` 터미널 가정을 번복).

### 결정 ST1 — DU6 을 **부분** 번복한다: 「살아 있는 타이머」는 계속 금지, 「끝난 구간의 기록」은 허용

번복이 정당한 이유는 **기각된 것과 요청된 것이 같은 물건이 아니라는 점** 하나다.

| | 기각된 것 (커밋 `1b199cb`) | 이번 요청 |
|---|---|---|
| 값의 시제 | **현재 진행 중** 단계의 실시간 경과 (`42분 경과`, 30초 틱) | **끝난** 단계의 확정 소요 시간 |
| 답하는 질문 | "지금 무엇을 하고 있나 / 얼마나 됐나" | "설계·구현·검수에 각각 얼마가 걸렸나" |
| 대체재 존재 | **있었다** — `.step-detail` 한 줄이 같은 질문에 더 잘 답했다(그래서 기각) | **없다.** 화면의 어떤 요소도 완료 단계의 소요를 알려주지 않는다 |
| 구현 형태 | `renderNowCard()` + 전용 카드 + 30초 틱 스크립트 | 오케스트레이터가 쓰는 **정적 텍스트**. 스크립트 0줄 추가 |

기각 사유("정보 자체가 불필요 — `.step-detail` 로 충분")는 **"지금"에 대한 판정**이었다. `.step-detail` 은 과거 단계의 소요를 표현할 수 없으므로, 그 판정이 이번 요구까지 덮지 않는다.

**살아남는 부분(계속 금지)**: 실시간 틱, 전용 「지금」 카드, `dz-now-*` 네임스페이스, `renderNowCard`. → 신설 **불변식 13** 이 이것을 기계적으로 고정한다.

### 승인이 필요한 항목 (3건)

1. **ST1 — DU6 부분 번복.** 승인하지 않으면 이 PRP 전체가 폐기된다.
2. **T22-96 의 개정.** 유물 목록에서 `data-started-at` **한 개만** 뺀다(§11.1). 나머지 9개는 그대로 남는다.
3. **표시 위치** — 단계별 소요는 각 단계 줄 오른쪽(`.step-time`), 총 경과는 하단 갱신 줄(`#dz-updated`)에 붙인다(§7.4). 별도 카드를 만들지 않는다.

---

## 1. 요구사항

### 1.1 문제

`.claude/dashboard.html` 은 단계 상태(`done`/`active`/`wait`)만 담고 **시간 축이 전혀 없다**. `#dz-updated`(`commands/dashboard_template.html:292`)가 "마지막으로 갱신된 시각" 한 점을 보여줄 뿐이라, 작업이 끝난 뒤 "구현이 47분, 검수가 두 회차 합쳐 12분" 같은 회고가 불가능하다.

### 1.2 사용자 서술

> 단계가 `active` 로 바뀐 시점과 `done` 으로 바뀐 시점을 기록해, 대시보드 화면에서 **단계별 소요 시간**과 **총 경과**를 볼 수 있게 하려 한다.

### 1.3 성공 기준 (검증 가능한 형태)

| # | 기준 | 확인 방법 |
|---|------|-----------|
| S1 | `step <n> active` → `step <n> done` 을 거친 단계 줄에 소요 시간 텍스트가 보인다 | `#dz-step-{n}` 안에 비어 있지 않은 `.step-time` 이 있다 |
| S2 | 총 경과가 화면에 보인다 | `#dz-updated` 텍스트가 `갱신: … · 총 경과 …` 형태다 |
| S3 | **구현↔검수 회귀(`active`→`wait`→`active`→`done`)에서 대기 시간이 소요에 섞이지 않는다** | 두 `active` 구간의 합만 누적된다(§7.3 전이표, U-4 단위 테스트) |
| S4 | `step` 을 반복 호출해도(같은 단계에 `active` 를 여러 번) 시작 시각이 재각인되지 않는다 | §7.3 전이표 3행, U-3 |
| S5 | **살아 있는 타이머가 부활하지 않았다** | 템플릿 `<script>` 의 `setInterval` 은 폴링 1개뿐. T22-160(역방향) |
| S6 | `step`·`impl` 의 Bash 호출 수가 늘지 않았다 | 각각 **Bash 1회** 유지(§8) |
| S7 | 폴링 스크립트가 **한 줄도** 바뀌지 않았다 | `commands/dashboard_template.html:294-478` diff 0줄 |
| S8 | 허브(`/hub`) 티어 1 파싱이 그대로 동작한다 | `python3 -m pytest tests/hub/test_hub_parse.py` 전건 통과 + U-8 |
| S9 | `bash tests/run.sh` 가 24/24 | 명령 실행 |
| S10 | 옛 세대 대시보드(시간 속성 없음)가 예외 없이 동작한다 | `.step-time` 미존재 시 삽입 경로(§8.2 1단계), U-7 |

---

## 2. 선행 조사 — 재사용할 자산과 피할 함정

기각됐던 `docs/prps/dashboard-current-next-card.md` 는 **불변식 호환성 분석을 이미 마쳐 두었다.** 그 분석은 그대로 유효하며 이번 설계가 승계한다.

| 승계하는 분석 | 출처 | 내용 |
|---|---|---|
| 속성 추가가 불변식 2 를 깨지 않는다 | `dashboard-current-next-card.md:166` | "기존 `<li>` **같은 줄 안의 속성**이다. 줄 수·줄 경계 불변" |
| 감사용 `grep -c` 가 안전하다 | 같은 문서 `:174` | "속성을 `class` **뒤**에 붙이므로 `dz-step-.*class="done"` 매칭에 영향 없다" |
| `step` 0단계 "결과는 항상 N줄" 이 유지된다 | 같은 문서 `:172` | "grep 패턴·대상 요소 수 불변" |
| `syncVisualization` 이 자동으로 옮겨 준다 | 같은 문서 `:176` | "`data-started-at` 은 HTML 의 일부라 자동으로 함께 옮겨온다" |
| 동적 셀렉터 표의 **행 수를 늘리지 않고** 기존 행을 수정한다 | 같은 문서 `:264` | `#dz-step-{n}` 행 1개 수정 |

**피할 함정 — 그 설계가 기각된 이유는 「값」이 아니라 「그릇」이었다.** 전용 카드 + 렌더 함수 4종 + 틱 스크립트라는 무게가 화면 가치를 넘었다. 이번 설계는 **새 요소·새 스크립트·새 카드를 0개** 만든다.

---

## 3. 결정

| # | 결정 | 근거 |
|---|------|------|
| **ST1** | DU6 을 부분 번복한다 (§0) | 기각 사유가 "현재 진행 상황"에 대한 판정이고, `.step-detail` 이 과거 소요를 표현할 수 없다 |
| **ST2** | **시간 값은 오케스트레이터가 쓰는 정적 텍스트다.** 브라우저가 계산하지 않는다 | ① 티어 2(`file://`)에서도 동작 ② 허브가 DOM 을 텍스트로 읽으므로(`hub_parse.py`) 정적 값만 허브에 도달할 수 있다 ③ `snapshot_content_key`(`hub_model.py:80-84`)가 "지금" 파생값에 오염되지 않는다 — `hub_template.html:89` 가 같은 이유를 이미 기록한다: "실리는 값은 정적 정수뿐이고 '지금' 파생값은 넣지 않는다" |
| **ST3** | **선형 모드 전용.** 매트릭스(`#dz-cell-{g}-{p}`)에는 시간을 기록하지 않는다 | 확립된 선례: `.step-detail` 도 "선형 모드 전용"이다(`dashboard.md:661`, 매트릭스에서는 인자를 무시하고 한 줄 보고 — `:675-677`). 표준 전체 경로·축약 경로는 **둘 다 선형**이다(`dashboard.md:42`). `hub_parse._CELL_LINE_PATTERN`(`hub_parse.py:75-78`)을 건드리지 않는 이득이 크다 |
| **ST4** | **누적 방식**을 쓴다(`active` 구간의 합). 첫 `active`~`done` 스팬이 아니다 | `dashboard.md:13` — "축약 경로도 **구현↔검수 회귀가 여러 회차 반복**될 수 있어". 검수 FAIL 시 `step 4 wait` 후 재검수하는 표준 트리거(`dashboard.md:54`)가 있으므로, 스팬 방식은 검수 소요에 **재구현 시간 전체**를 섞는다. 회귀는 가설이 아니라 표준 경로다 |
| **ST5** | 저장 단위는 **epoch 초**(정수), 표시 단위는 사람이 읽는 라벨 | LLM 의 `YYYY-MM-DD HH:MM` 산술은 시·일 경계에서 틀린다. 정수 뺄셈만 남긴다 |
| **ST6** | **모든 산술과 라벨 조립을 step/impl 0단계의 Bash 안으로 넣는다.** 오케스트레이터는 나눗셈을 하지 않는다 | 확립된 선례: `init` 4단계가 `python3 - <<'PY'` 로 값 치환 전체를 한 호출에 넣는다(`dashboard.md:538-591`). 0단계는 이미 Bash 1회를 쓰므로 **호출 수가 늘지 않는다**(S6) |
| **ST7** | 세션 시작 시각은 `#dz-log` 의 새 속성 `data-session-start` 에 각인한다 | `dashboard.md:156-165` 가 확립한 판단의 재적용: "두 속성 모두 별도 행이 아니라 `#dz-log` 행에 얹은 이유 — **Bash 호출 추가 없이** 가능해짐". `step`·`impl` 0단계의 grep 이 **이미 그 줄을 가져온다**(소유권 검증용, `dashboard.md:646`·`:782`) |
| **ST8** | 동적 셀렉터 표(6행)의 **행 수를 늘리지 않는다.** 기존 `#dz-step-{n}`·`#dz-updated` 두 행을 수정하고, 상세는 별도 하위 절에 둔다 | `tests/run.sh:1738-1739` (T22-92)가 리터럴 `동적(치환 대상) — 6 셀렉터` 를 검사한다. 확립된 선례: `impl` 슬롯도 별도 하위 절을 만들고 "「동적(치환 대상) — 6 셀렉터」 표는 위 그대로 무수정이다"라고 못 박았다(`dashboard.md:167-177`) |
| **ST9** | `data-started-at` 이라는 **이름을 재사용하지 않는다.** 새 이름 `data-active-since`·`data-elapsed-s` 를 쓴다 | ① 옛 픽스처(`tests/hub/fixtures/linear_hub_dashboard.html:128-130`)가 그 이름에 `"2026-08-10 18:12"` 형식을 담고 있어, epoch 초를 같은 이름에 넣으면 세대 간 **형식이 모호**해진다 ② `hub_parse.py:63` 의 선택 그룹이 옛 픽스처를 위해 살아 있어야 한다(그 자체가 `impl-panel…md:112` 의 명시적 비목표) |

### 결정 ST9 의 정직성 부기 — 테스트 회피가 아니다

`data-started-at` 을 안 쓰면 T22-96 이 **손대지 않고도 통과**한다. 그러나 그러면 그 검사는 "스탬핑 금지"를 지킨다고 주장하면서 실제로는 아무것도 막지 않는 **죽은 검사**가 된다. 그래서 §11.1 은 T22-96 의 **주석과 목록을 명시적으로 개정**한다 — 유물 목록에서 `data-started-at` 을 빼고(이름은 새 이름으로 갈렸으므로 옛 마크업 가드로서의 의미가 사라진다), 그 자리를 **신설 T22-160(살아 있는 타이머 역방향)** 이 대신 지킨다. 금지의 **목적**(타이머·카드 부활 차단)은 강화되고, 금지의 **대상**(타임스탬프라는 개념)만 풀린다.

---

## 4. 비목표 (명시적으로 건드리지 않는다)

| 제외 항목 | 사유 |
|---|---|
| **살아 있는 경과 타이머·「지금」 카드** | 결정 ST1 이 살려 둔 DU6 의 절반. 불변식 13 + T22-160 이 기계적으로 막는다 |
| **매트릭스 모드의 칸별 소요 시간** | 결정 ST3 |
| **`impl` 패널(`#dz-impl-{k}`)의 항목별 소요 시간** | `impl` 은 fan-out 전용 예외 경로로 표준 경로에서 **호출되지 않는다**(`dashboard.md:59-64`). 쓰지 않는 패널에 시간 축을 더하는 것은 YAGNI. 단, `impl` 도 `#dz-updated` 를 쓰므로 **총 경과 suffix 는 함께 유지한다**(§8.4) — 안 하면 `impl` 호출이 suffix 를 지워 값이 깜빡인다 |
| **허브(`/hub`) 화면에 소요 시간 노출** | 결정 ST2 로 데이터는 파일에 있지만, 허브 렌더(`hub_template.html:1233-1242` `renderTier1ActiveStep`)는 건드리지 않는다. `hub_parse` 변경은 **비캡처 그룹만** 추가해 `StepView`·`Tier1Snapshot`·`#dzh-data` 페이로드를 **무변경**으로 둔다(§9.2) |
| **`log` 절차** | `log` 는 `#dz-updated` 를 쓰지 않는다(`dashboard.md:814-886` 전 단계 확인). 시간 축과 접점이 없다 |
| **`#dz-progress-pct` 에 시간 병기** | **금지.** `hub_parse._PROGRESS_PATTERN`(`hub_parse.py:55-58`)이 `(\d+)/(\d+)\s*·\s*(\d+)%</div>` **완전 형태**를 요구한다 — 텍스트를 덧붙이면 `parse_dashboard_html` 이 **None** 을 반환해 허브 티어가 통째로 강등된다 |
| **옛 세대 대시보드 마이그레이션** | `.claude/dashboard.html` 은 임시 산출물이다(`dashboard.md:750`). 시간 속성이 없으면 그 단계에 시간이 안 보일 뿐이고, 절차는 예외 없이 진행된다(S10) |

---

## 5. 영향 범위

### 5.1 경로 분류

**전체 경로**(설계 → 구현 → 검수). 판정 근거: 로직 변경이 3개 파일 이상(`commands/dashboard.md`, `commands/dashboard_template.html`, `hub/bin/hub_parse.py`)에 걸치고, 외부 소비자와의 **공개 DOM 계약**을 바꾼다(`dashboard.md:116-117`: "이 DOM 계약에는 외부 읽기 소비자(`/hub`)가 있다").

### 5.2 파일별 영향

| 파일 | 변경 | 비고 |
|---|---|---|
| `commands/dashboard.md` | 하위 절 1개 신설 · 기존 표 2행 수정 · 불변식 3개 신설 · `init` 1·4단계 · `step` 0·1·3단계 · `impl` 0·3단계 | 유일한 실행 주체 |
| `commands/dashboard_template.html` | 헤더 주석 맵 · `<style>` 3줄 · `#dz-log` 여는 태그 1속성 | **`<script>` 0줄**(S7) |
| `hub/bin/hub_parse.py` | `_STEP_LINE_PATTERN` 에 **비캡처** 선택 그룹 3개 | `StepView`·`Tier1Snapshot` 무변경 |
| `tests/run.sh` | T22-96 개정 · T22-159~162 신설 | `total_tests=24` 유지 |
| `tests/hub/test_hub_parse.py` | U-5~U-8 신설 | |
| `tests/hub/fixtures/timed_dashboard.html` | 신규 픽스처 | |
| `README.md` | `/dashboard` 설명 1문장 · L139 줄 수 실측 갱신 | 줄 수는 테스트 대상이 아니지만 저장소 관례(커밋 `0b814b4`) |
| `docs/prps/dashboard-rationale.md` | `<a id="step-timing"></a>` 절 신설 | `dashboard.md` 가 링크로 참조 |

### 5.3 영향 **없음**을 확인한 것

| 대상 | 근거 |
|---|---|
| 폴링 스크립트 | `.step-time` 과 두 속성은 `#dz-steps` 서브트리 안 → `syncVisualization`(`dashboard_template.html:355-359`)이 `outerHTML` 로 통째 대입. `#dz-updated` 는 `syncText(fresh,'dz-updated')`(`:403`)가 이미 동기화. **새 sync 호출 0개** |
| `#dz-impl-card` 계열 | `_IMPL_LINE_PATTERN`·`#dz-impl-count`·불변식 5·6 무변경 |
| 매트릭스 | `_CELL_LINE_PATTERN`·매트릭스 CSS·마크업 무변경 (ST3) |
| `grep 유일성 불변식` (`dashboard.md:303-309`) | 스크립트를 안 건드리므로 `id="…"` 문자열이 새로 생기지 않는다 |
| `PiP` | `.step-time` 은 `<li>` 안 요소라 `.wrap` 이동에 자동 승계. `body.dz-pip` 규칙 추가 불필요 |
| T22-80 / T22-105 | 두 검사 모두 `grep -qF 'id="dz-log" data-owner-token="" data-server-port=""'` **부분일치**다(`tests/run.sh:1617`·`:1866`). 새 속성을 `data-server-port=""` **뒤에** 붙이면 리터럴이 보존돼 **개정 불필요** |
| T22-107 | `'항상 4줄'` 리터럴을 검사한다(`tests/run.sh:1900`). §8.2 의 출력 계약이 "**grep 결과는 항상 4줄**" 문구를 그대로 유지해 **개정 불필요** |
| T22-92 | `'동적(치환 대상) — 6 셀렉터'` 리터럴 유지(ST8) → **개정 불필요** |
| T22 line 2270 | 템플릿의 `<div class="foot" id="dz-updated">갱신: -</div>` **플레이스홀더**를 검사한다. 우리가 바꾸는 것은 `step` 이 **런타임에 쓰는 값**이다 → 개정 불필요 |

---

## 6. 파일 구조

신규 파일 2개뿐이고, 실행 코드 파일은 새로 만들지 않는다.

```
coding-harness/
├── commands/
│   ├── dashboard.md                     # 개정 (절차·계약)
│   └── dashboard_template.html          # 개정 (주석·CSS·#dz-log 태그)
├── hub/bin/
│   └── hub_parse.py                     # 개정 (정규식 1개)
├── tests/
│   ├── run.sh                           # 개정 (T22-96) + 신설 (T22-159~162)
│   └── hub/
│       ├── test_hub_parse.py            # 신설 (U-5~U-8)
│       └── fixtures/
│           └── timed_dashboard.html     # ★신규
├── docs/prps/
│   ├── dashboard-step-timing.md         # ★신규 (이 문서)
│   └── dashboard-rationale.md           # 개정 (근거 절 1개)
└── README.md                            # 개정
```

---

## 7. 데이터 모델

### 7.1 개념 모델

```
StepTiming                       # 단계 하나의 시간 상태. DOM 이 유일한 저장소다.
  activeSince : int | None       # 지금 진행 중인 active 구간의 시작 (epoch 초).
                                 #   None = 지금 active 가 아니다(또는 한 번도 아니었다)
  elapsedSec  : int              # 이미 끝난 active 구간들의 합 (초). 기본 0
  timeLabel   : str              # elapsedSec 의 사람이 읽는 표현. **파생 표시값**

SessionTiming
  sessionStart : int | None      # init 시각 (epoch 초). None = 이 기능 도입 이전 대시보드
  totalLabel   : str             # (지금 − sessionStart) 의 라벨
```

**불변**: `timeLabel` 과 `totalLabel` 은 파생값이지만 **파일에 정적으로 쓰인다**(ST2). 브라우저는 이 둘을 계산하지 않는다.

### 7.2 DOM 표현

#### 동적 셀렉터 표 — **기존 6행 중 2행을 수정한다** (행 수 6 유지, ST8)

| 셀렉터 | 치환 대상 (개정) | 값 (개정) |
|--------|----------------|-----------|
| `#dz-step-{n}` **(그룹 1개)** | `class` 속성 + **`data-active-since`·`data-elapsed-s` 속성** + 자식 `.chip` 텍스트 + **자식 `.step-time` 텍스트** + 자식 `.step-detail` 텍스트 | `done`\|`active`\|`wait` / **epoch 초 또는 빈 문자열** / **누적 초** / `완료`\|`진행중`\|`대기` / **소요 라벨(빈 문자열 허용)** / 한 줄 상세 |
| `#dz-updated` | 텍스트 | **`갱신: {YYYY-MM-DD HH:MM}` 또는 `갱신: {YYYY-MM-DD HH:MM} · 총 경과 {라벨}`** |

#### 신설 하위 절 — 「단계 소요 시간 슬롯 — 속성 2 + 표시 1 + 세션 1」

> **「동적(치환 대상) — 6 셀렉터」 표는 위 두 행을 고친 것 외에 무수정이다.** (선례: `dashboard.md:169`)

| 이름 | 소속 | 치환 주체 | 값 |
|------|------|----------|-----|
| `data-active-since` | `#dz-step-{n}` 의 속성 | `step` | epoch 초 순수 숫자 또는 빈 문자열. **빈 문자열과 속성 부재는 같은 뜻**(지금 active 아님) |
| `data-elapsed-s` | `#dz-step-{n}` 의 속성 | `step` | 누적 초 순수 숫자 또는 빈 문자열. **빈 문자열·부재 = 0** |
| `.step-time` | `#dz-step-{n}` 의 자식 `<span>` | `step` | 소요 라벨. 비면 CSS `:empty` 가 숨긴다 |
| `data-session-start` | `#dz-log` 의 속성 | **`init` 만** 각인. `step`·`impl` 은 읽기만 | epoch 초 순수 숫자 또는 빈 문자열. **빈 문자열·부재 = 세션 시작 미상**(이 기능 도입 이전 대시보드 → 총 경과를 붙이지 않는다) |

`data-session-start` 는 `data-server-port`·`data-owner-token` 과 같은 계열의 **`#dz-log` 행 하위 개념**이다(ST7).

#### `<li>` 마크업 (선형 모드)

**속성은 반드시 `class` 뒤**, **`.step-time` 은 `.chip` 과 `.step-detail` 사이**, **한 줄에 하나**(불변식 2·3 승계).

```html
      <li id="dz-step-1" class="active" data-active-since="1787795652" data-elapsed-s="0"><span class="num">1</span>설계<span class="chip">진행중</span><span class="step-time"></span><span class="step-detail">design-architect 디스패치 — PRP 작성</span></li>
      <li id="dz-step-2" class="done" data-active-since="" data-elapsed-s="2820"><span class="num">2</span>승인<span class="chip">완료</span><span class="step-time">47분</span><span class="step-detail">사용자 승인 수령</span></li>
      <li id="dz-step-3" class="wait"><span class="num">3</span>구현<span class="chip">대기</span><span class="step-detail"></span></li>
```

- 3번처럼 **한 번도 `active` 가 아니었던 항목에는 시간 속성도 `.step-time` 도 없다.** `init` 은 1번에만 각인하고(§8.1), 나머지는 `step` 이 필요할 때 같은 Edit 안에서 삽입한다 — `.step-detail` 삽입과 같은 방식(`dashboard.md:673-674`).
- `.step-time` 이 비면 CSS 가 숨기므로 마크업에 있어도 화면에 아무것도 안 나온다.

#### `#dz-log` 여는 태그 (템플릿 플레이스홀더)

```html
    <ul class="log" id="dz-log" data-owner-token="" data-server-port="" data-session-start=""></ul>
```

**속성 순서 고정**: `id` → `data-owner-token` → `data-server-port` → `data-session-start`. 새 속성을 **맨 뒤**에 두는 이유는 T22-80·T22-105 의 리터럴 부분일치를 보존하기 위해서다(§5.3).

### 7.3 상태 전이 규칙 (이 표가 `step` 1단계의 계약이다)

`이전 상태`는 0단계 grep 이 가져온 줄에 그대로 적혀 있다 — **기억에 의존하지 않는다**(`dashboard.md:685` 와 같은 원칙).

| # | 이전 → 새 상태 | `data-active-since` | `data-elapsed-s` | `.step-time` |
|---|---------------|--------------------|------------------|--------------|
| 1 | ≠`active` → `active` | `{NOW_S}` 로 설정 | 건드리지 않음 | 건드리지 않음 |
| 2 | `active` → `done` | `""` 로 비움 | `{BANKED_S}` | `{BANKED_LABEL}` |
| 3 | `active` → `wait` | `""` 로 비움 | `{BANKED_S}` | `{BANKED_LABEL}` |
| 4 | `active` → `active` | **건드리지 않음** | 건드리지 않음 | 건드리지 않음 |
| 5 | `done` → `wait`, `wait` → `done`, `done` → `done`, `wait` → `wait` | 건드리지 않음 | 건드리지 않음 | 건드리지 않음 |

- **4행이 S4 의 전부다.** 표준 트리거는 같은 단계에 `active` 를 **두 번 이상** 부른다(`dashboard.md:51-52`: 디스패치 직전 · 결과 보고 직후). 재각인하면 소요가 매번 0으로 리셋된다.
- **3행이 S3 의 전부다.** 검수 FAIL(`step 4 wait`)이 그 회차 소요를 은행에 넣고 시계를 멈춘다. 재검수(`step 4 active`)가 새 구간을 시작하고, `done` 에서 두 구간의 합이 남는다. **`wait` 로 보낸 시간은 절대 포함되지 않는다.**
- **5행 `wait` → `done`**: `active` 를 거치지 않은 단계는 소요가 **비어 있다.** 관측하지 않은 것을 만들어 내지 않는다 — `impl` 패널의 확립된 원칙과 같다(`dashboard.md:701-704`: "오케스트레이터가 직접 관측한 두 시점만 기록한다").

### 7.4 라벨 규칙 `D(seconds)` — 유일 정의

```
D(s):
  s < 60      →  "1분 미만"
  s < 3600    →  "{s // 60}분"
  else        →  "{s // 3600}시간 {(s % 3600) // 60}분"
```

| 초 | 라벨 |
|----|------|
| 0 | `1분 미만` |
| 59 | `1분 미만` |
| 60 | `1분` |
| 2820 | `47분` |
| 3600 | `1시간 0분` |
| 4020 | `1시간 7분` |

허브의 `elapsedLabel`(`hub/bin/hub_template.html:1030-1036`)이 쓰는 어휘(`N분` / `N시간 M분`)와 **같은 모양**이고, "전" 접미어만 없다(경과가 아니라 소요이므로). 두 화면의 시간 표기가 같은 계열로 읽히게 하기 위한 선택이며, 사본이 아니라 **어휘의 일치**다.

**이 함수는 §8.2 의 Bash 안에만 구현된다.** 오케스트레이터가 손으로 나눗셈하지 않는다(ST6).

### 7.5 총 경과 = `D(NOW_S − data-session-start)`

- `data-session-start` 가 비어 있거나 없으면 **suffix 를 붙이지 않는다**(`갱신: {시각}` 그대로).
- **총 경과는 「마지막 갱신 시점의 경과」다** — 살아 있는 값이 아니다(ST1·불변식 13). 세션이 유휴면 값이 멈추며, 그것이 정상이다.
- **단계 소요의 합 ≤ 총 경과** 는 정상이다(`wait` 구간·`active` 를 거치지 않은 단계 때문). 두 값을 일치시키려 하지 않는다.

### 7.6 신설 불변식 (기존 1~6, 8, 9, 10 에 이어. **7 은 결번**)

> **11.** `data-session-start` 는 `init` 만 쓴다. `step`·`impl` 은 읽기만 하고, 스크립트(폴링·PiP)는 읽지도 쓰지도 않는다.
> — 불변식 9 와 문장 구조가 같다(대상만 다르다).

> **12.** 시간 속성(`data-active-since`·`data-elapsed-s`)은 반드시 `class="…"` **뒤에** 오고, `.step-time` 은 `.chip` 과 `.step-detail` **사이에** 온다. `<li>` 를 여러 줄로 쪼개지 않는다.
> — 앞 절은 감사용 `grep -c 'dz-step-.*class="done"'`(`dashboard.md:696`)을, 뒷 절은 `hub_parse._STEP_LINE_PATTERN` 의 그룹 순서를 고정한다. 줄바꿈 금지는 불변식 2·3 의 승계다.

> **13.** **시간 표시는 정적 텍스트뿐이다.** 템플릿 `<script>` 에 경과 시간을 계산하거나 주기적으로 갱신하는 코드를 넣지 않는다. `setInterval` 은 폴링(`POLL_INTERVAL_MS`) 하나뿐이다.
> — 결정 DU6 에서 **살아남은 절반**을 기계적으로 고정한다. 이 불변식이 T22-160 의 검사 대상이다.

---

## 8. 인터페이스 (절차 개정)

**호출 규약(`dashboard.md:21-31`)은 무변경이다. 새 인자가 0개다.** 시간은 기존 호출의 부산물로 기록된다.

### 8.1 `init` — 2곳

**1단계 Bash 개정** — 출력이 2줄 → **3줄**. `date` 를 프로젝트 이름과 토큰 **사이**에 넣어 기존 앵커 두 개("첫 줄"·"마지막 줄")를 **둘 다 보존**한다. `dashboard.md:516-517` 이 명문화한 앵커 안정성 원칙의 재적용이다.

```bash
mkdir -p .claude && rm -f .claude/dashboard.html
dz_template=""
for dz_candidate in "$HOME/.claude/commands/dashboard_template.html" \
                    ".claude/commands/dashboard_template.html"; do
  if [ -f "$dz_candidate" ]; then dz_template="$dz_candidate"; break; fi
done
if [ -z "$dz_template" ]; then echo NOTEMPLATE; else
  cp "$dz_template" .claude/dashboard.html \
    && basename "$PWD" \
    && date '+%s %Y-%m-%d %H:%M' \
    && od -An -N4 -tx1 /dev/urandom | tr -d ' \n' && echo
fi
```

| 출력 | 의미 | 행동 |
|------|------|------|
| `NOTEMPLATE` (1줄) | 두 경로 모두에 템플릿이 없다 | 종전과 같음 (보고 후 중단) |
| **3줄** | 첫 줄 = 프로젝트 표시 이름 / **둘째 줄 = `{epoch 초} {YYYY-MM-DD HH:MM}`** / 마지막 줄의 8글자 = 소유 토큰 | 2번으로 |

> 둘째 줄이 해소하는 기존 약점: 종전 절차는 `#dz-updated` 에 넣을 "현재 시각"의 **출처를 지정하지 않았다**(`dashboard.md:547`). 이제 셸이 이번 호출에서 방금 출력한 값을 쓴다.

**4단계 `values` 개정** — 2개 값 추가, 앵커 1개 수정.

```python
values = {
    ...
    "session_start": "{1단계 둘째 줄의 첫 필드}",   # epoch 초
    "steps_block_lines": [
        "    <ol class=\"steps\" id=\"dz-steps\">",
        # 1번만 시간 속성을 갖는다. .step-time 은 비운다(아직 끝난 구간이 없다).
        "      <li id=\"dz-step-1\" class=\"active\" data-active-since=\"{epoch 초}\" data-elapsed-s=\"0\"><span class=\"num\">1</span>{단계명1}<span class=\"chip\">진행중</span><span class=\"step-time\"></span><span class=\"step-detail\"></span></li>",
        # 2번 이상은 시간 속성도 .step-time 도 없다.
        "      <li id=\"dz-step-{n}\" class=\"wait\"><span class=\"num\">{n}</span>{단계명n}<span class=\"chip\">대기</span><span class=\"step-detail\"></span></li>",
        "    </ol>",
    ],
}
```

`replacements` 의 `#dz-log` 항목 개정 (**앵커와 템플릿을 반드시 함께 고친다** — GOTCHA 1):

```python
    ('    <ul class="log" id="dz-log" data-owner-token="" data-server-port="" data-session-start=""></ul>',
     '    <ul class="log" id="dz-log" data-owner-token="%s" data-server-port="" data-session-start="%s"></ul>'
     % (values["owner_token"], values["session_start"])),
```

**`#dz-updated` 항목은 무변경**(`갱신: {시각}`). `init` 시점의 총 경과는 0이므로 suffix 를 붙이지 않는다(§7.5).

**매트릭스 모드**: `steps_block_lines` 가 `<table>` 이 될 때 시간 속성을 **넣지 않는다**(ST3). `data-session-start` 는 두 모드 공통으로 각인한다 — 총 경과는 매트릭스에서도 동작한다.

### 8.2 `step` — 0·1·3단계 (**Bash 1회 + Edit 3회 유지**)

#### 0단계 개정 — 같은 Bash 호출에 계산 블록을 잇는다

```bash
grep -n -e 'id="dz-step-{n}"' -e 'id="dz-progress-bar"' -e 'id="dz-progress-pct"' -e 'id="dz-log"' .claude/dashboard.html
python3 - <<'PY'
import pathlib, re, time

STEP_INDEX = {n}          # 세션이 채우는 유일한 값. 정수다.

def label(seconds):
    if seconds < 60:   return "1분 미만"
    if seconds < 3600: return "%d분" % (seconds // 60)
    return "%d시간 %d분" % (seconds // 3600, (seconds % 3600) // 60)

def number(line, name):
    found = re.search(r'%s="(\d+)"' % name, line)
    return int(found.group(1)) if found else None

lines = pathlib.Path(".claude/dashboard.html").read_text(encoding="utf-8").splitlines()
def find(needle):
    return next((one for one in lines if needle in one), "")

step_line = find('id="dz-step-%d"' % STEP_INDEX)
log_line = find('id="dz-log"')
now = int(time.time())
since = number(step_line, "data-active-since")
banked = (number(step_line, "data-elapsed-s") or 0) + ((now - since) if since else 0)
session_start = number(log_line, "data-session-start")

print("NOW_S=%d" % now)
print("NOW_TEXT=%s" % time.strftime("%Y-%m-%d %H:%M"))
print("BANKED_S=%d" % banked)
print("BANKED_LABEL=%s" % label(banked))
print("TOTAL_LABEL=%s" % (label(now - session_start) if session_start else "-"))
PY
```

**출력 계약**

| 부분 | 형태 |
|------|------|
| 앞부분 | 각 요소는 한 줄에 하나씩 생성되므로 **grep 결과는 항상 4줄이다**(대상 1 + 진행률 2 + 소유 토큰 1) |
| 뒷부분 | `KEY=값` **5줄**. 키는 `NOW_S`·`NOW_TEXT`·`BANKED_S`·`BANKED_LABEL`·`TOTAL_LABEL` 다섯 개뿐인 **폐쇄 어휘**다 |

- `KEY=값` 형태를 쓰는 이유: 라벨에 공백이 들어간다(`1시간 7분`). 공백 구분 필드로는 파싱이 모호해진다.
- `TOTAL_LABEL=-` 는 세션 시작 미상이라는 뜻이다 → 3단계에서 suffix 를 붙이지 않는다.
- **`BANKED_S`·`BANKED_LABEL` 은 새 상태와 무관하게 계산된다.** "지금 시계를 멈추면 얼마인가"는 요청된 상태가 무엇이든 같은 값이며, 새 상태는 **그것을 은행에 넣을지만** 결정한다(§7.3). 그래서 계산을 상태 판정 전에 할 수 있다.
- python3 이 없거나 이 블록이 실패하면 **`KEY=` 5줄이 안 나온다** → 시간 기록만 건너뛰고 종전 동작(상태·진행률·갱신 시각)을 그대로 수행하며, 그 사실을 한 줄 보고한다. **`step` 을 중단시키지 않는다** — 「자동 발행」의 실패 비차단 원칙과 같다(`dashboard.md:935-936`).
- 소유권 검증(`FOREIGN` → 중단)은 종전과 동일하게 grep 4번째 줄로 수행한다.

#### 1단계 개정 — 같은 Edit 안에서 시간까지 처리한다

기존 `.step-detail` 갱신 규칙 표는 **무변경**이다. 그 아래에 §7.3 전이표를 추가한다.

- 대상 `<li>` 에 시간 속성이나 `.step-time` span 이 **없으면** 이 Edit 안에서 삽입한다. 속성은 `class="…"` 바로 뒤, `.step-time` 은 `.chip` 닫는 태그 바로 뒤(불변식 12).
- 값은 **0단계 출력의 `BANKED_S`·`BANKED_LABEL`·`NOW_S` 를 그대로 옮긴다.** 계산하지 않는다.
- `.step-time` 텍스트는 이스케이프가 필요 없다 — 라벨 어휘가 숫자와 `분`·`시간`·`1분 미만` 뿐이다.
- **매트릭스 모드(`<g>.<p>`)에서는 이 단계 전체를 건너뛴다**(ST3). 보고하지 않는다 — 사용자가 요청한 인자가 없으므로 알릴 것이 없다(「보고 최소화」).

#### 2단계 — **무변경**

진행률 전이 산술(±1)에 손대지 않는다.

#### 3단계 개정 — `#dz-updated` 텍스트

```
TOTAL_LABEL 이 "-" 가 아니면  →  갱신: {NOW_TEXT} · 총 경과 {TOTAL_LABEL}
TOTAL_LABEL 이 "-" 이면       →  갱신: {NOW_TEXT}
```

Edit 1회 유지. 시각의 출처가 "기억"에서 "0단계의 `NOW_TEXT`"로 바뀐다.

#### 감사(audit)용 재계수 — 1줄 추가

```bash
grep -o 'id="dz-step-[0-9]*"[^>]*data-elapsed-s="[0-9]*"' .claude/dashboard.html   # 단계별 누적 초
```

### 8.3 `impl set` — **무변경**

시간 속성을 만들지 않는다(§4). 3·4단계도 그대로다.

### 8.4 `impl <k>` — 0·3단계 (**Bash 1회 유지**)

`#dz-updated` 를 쓰는 유일한 다른 절차이므로, suffix 가 깜빡이지 않게 총 경과만 맞춘다.

**0단계**: grep(3줄, 종전과 동일) 뒤에 아래를 같은 Bash 호출로 잇는다.

```bash
python3 - <<'PY'
import pathlib, re, time

def label(seconds):
    if seconds < 60:   return "1분 미만"
    if seconds < 3600: return "%d분" % (seconds // 60)
    return "%d시간 %d분" % (seconds // 3600, (seconds % 3600) // 60)

lines = pathlib.Path(".claude/dashboard.html").read_text(encoding="utf-8").splitlines()
log_line = next((one for one in lines if 'id="dz-log"' in one), "")
found = re.search(r'data-session-start="(\d+)"', log_line)
now = int(time.time())
print("NOW_TEXT=%s" % time.strftime("%Y-%m-%d %H:%M"))
print("TOTAL_LABEL=%s" % (label(now - int(found.group(1))) if found else "-"))
PY
```

출력 계약: **grep 결과는 항상 3줄**(문구 유지 → T22-108 무영향) + `KEY=값` **2줄**.

**3단계**: `#dz-updated` 를 `step` 3단계와 **같은 형식**으로 쓴다.

**1·2단계**: 무변경. 항목별 소요 시간을 기록하지 않는다.

### 8.5 템플릿 개정

**CSS** — `.step-detail` 규칙(`dashboard_template.html:134-135`) **바로 뒤**에 3줄:

```css
  .step-time{font-size:12px;font-weight:700;color:var(--muted);flex:none;font-variant-numeric:tabular-nums}
  .step-time:empty{display:none}
  li.done .step-time{color:var(--accent-ink)}
```

- `.chip` 이 `margin-left:auto`(`:131`)로 오른쪽으로 밀리므로, 그 뒤의 `.step-time` 은 칩 오른쪽에 붙는다: `1  설계 ······ [완료] 47분`.
- `flex:none` — `.chip` 과 같은 이유(줄바꿈 시 눌리지 않게).
- `tabular-nums` — 여러 줄의 숫자 폭이 흔들리지 않게. 라이트/다크 모두 기존 토큰만 쓰므로 새 색 토큰이 없다.
- `body.dz-pip` 규칙을 **추가하지 않는다.** 압축 뷰에서도 소요는 보일 값이다.

**`#dz-log` 여는 태그** (`:290`) — 맨 뒤에 ` data-session-start=""` 추가.

**헤더 주석 맵** (`:7-68`) — `#dz-step-{n}` 줄에 시간 속성·`.step-time` 을, `#dz-log` 줄에 `data-session-start` 를 각각 한 줄씩 덧붙인다. **`dashboard.md` 의 계약 문구와 어긋나면 안 된다.**

**`<script>`** — **한 줄도 바꾸지 않는다**(S7·불변식 13).

### 8.6 `hub/bin/hub_parse.py` — 정규식 1개

```python
_STEP_LINE_PATTERN = re.compile(
    r'<li id="dz-step-(?P<index>\d+)" class="(?P<state>done|active|wait)"'
    # 옛 세대(1b199cb 이전) 픽스처 호환. 새 대시보드는 이 이름을 쓰지 않는다(결정 ST9).
    r'(?:\s+data-started-at="(?P<started_at>[^"]*)")?'
    # 단계 소요 시간(docs/prps/dashboard-step-timing.md 결정 ST9). **비캡처**다 — 허브는 이
    # 값을 그리지 않으므로 StepView·#dzh-data 페이로드를 늘리지 않는다(YAGNI, 결정 ST2 부기).
    r'(?:\s+data-active-since="[^"]*")?'
    r'(?:\s+data-elapsed-s="[^"]*")?>'
    r'<span class="num">\d+</span>(?P<name>.*?)<span class="chip">.*?</span>'
    r'(?:<span class="step-time">[^<]*</span>)?'
    r'(?:<span class="step-detail">(?P<detail>.*?)</span>)?</li>'
)
```

**`StepView`·`Tier1Snapshot`·`hub_model.py`·`hub_template.html` 무변경.** 이 정규식 하나가 이 기능이 허브에 남기는 유일한 발자국이다.

> 왜 정규식을 꼭 고쳐야 하는가: 고치지 않아도 `<span class="chip">.*?</span>` 의 역추적이 새 span 을 삼켜 **우연히** 매칭될 수 있다. 그러나 `data-active-since` 속성이 `class` 뒤에 붙는 순간 `(?:...data-started-at...)?>` 의 `>` 요구가 깨져 **줄 전체가 매칭 실패**한다 → `steps` 가 빈 튜플이 되고 허브의 활성 단계 줄(`renderTier1ActiveStep`)이 조용히 사라진다. `dashboard.md:116-117` 이 경고하는 "조용한 티어 강등"이 바로 이것이다.

---

## 9. 폴링·허브 영향 분석

### 9.1 폴링 (변경 0줄)

| 대상 | 동기화 경로 | 상태 |
|------|-----------|------|
| `.step-time`, `data-active-since`, `data-elapsed-s` | `syncVisualization` 이 `#dz-steps` 를 `outerHTML` 로 통째 대입(`dashboard_template.html:355-359`) | **자동** |
| `#dz-updated`(총 경과 포함) | `syncText(fresh,'dz-updated')`(`:403`) | **자동** |
| `#dz-log` 의 `data-session-start` | 동기화 대상 아님 | **문제 없음** — `init` 이 한 번 쓰고 아무도 안 바꾼다(불변식 11). 라이브 DOM 과 파일이 발산할 여지가 없다 |

> `#dz-impl-card` 가 겪었던 함정("`.wrap` 안이지만 `#dz-steps` 동기화 대상이 아니다 — 별도 대입이 없으면 **영구히 stale** 된다", `dashboard_template.html:365`)을 이번 요소들은 **구조적으로 피한다** — 전부 이미 동기화되는 서브트리 안에 있기 때문이다. 새 요소를 `.wrap` 안 다른 곳에 두는 대안은 이 함정을 되살리므로 기각했다.

### 9.2 허브

| 관심사 | 결과 |
|--------|------|
| `parse_dashboard_html` 반환 | `Tier1Snapshot` 필드 구성 **무변경** |
| `#dzh-data` 페이로드 | **무변경** (비캡처 그룹이므로) |
| `snapshot_content_key`(`hub_model.py:80-84`) | `updated_text` 가 총 경과를 포함하게 되지만, 그 값은 `step`·`impl` 이 **어차피 `#dz-updated` 를 쓸 때만** 바뀐다 → **새 재렌더 churn 0** |
| 허브 화면 | 무변경. `updated_text` 는 파싱만 되고 렌더되지 않는다(전수 grep: 소비자 0) |

---

## 10. GOTCHA (구현자가 반드시 읽을 것)

1. **`#dz-log` 앵커는 3곳을 동시에 고쳐야 한다.** 템플릿의 여는 태그(`dashboard_template.html:290`), `init` 4단계 `replacements` 의 `anchor`, 같은 항목의 `replacement`. 하나라도 어긋나면 `ANCHOR-FAIL 0` 이 나고 `init` 이 **중단**된다(`dashboard.md:599-602`).
2. **새 속성은 반드시 `data-server-port=""` 뒤에 붙인다.** 앞이나 중간에 넣으면 T22-80·T22-105 의 리터럴 부분일치가 깨진다(`tests/run.sh:1617`·`:1866`).
3. **`#dz-progress-pct` 에 어떤 텍스트도 덧붙이지 않는다.** `_PROGRESS_PATTERN` 이 완전 형태를 요구해 허브가 **None** 을 받는다(§4).
4. **`'항상 4줄'`·`'항상 3줄'`·`'동적(치환 대상) — 6 셀렉터'` 세 리터럴을 문서에서 지우지 않는다.** T22-107·T22-108·T22-92 가 각각 이 문자열을 직접 검사한다.
5. **`step` 1단계에서 `data-active-since` 를 재각인하지 않는다**(§7.3 4행). 표준 트리거가 같은 단계에 `active` 를 두 번 이상 부른다.
6. **`hub_parse` 의 새 그룹은 비캡처(`(?:...)`)다.** 캡처로 만들면 `StepView` 에 필드를 더해야 하고, 그러면 `#dzh-data`·`snapshot_content_key`·기존 `StepView(...)` 생성 지점 전부에 파급된다(테스트 8개 파일이 `StepView`/`Tier1Snapshot` 을 키워드로 생성한다).
7. **템플릿 `<script>` 에 손대지 말라.** 불변식 13 이고, `dashboard.md:1313-1315` 의 기존 불변식("이 템플릿의 HTML/CSS/JS 는 `dashboard.md` 를 고치는 어떤 작업도 단 한 바이트 건드리지 않는다")은 **반대 방향**의 규칙이라 이번 CSS·태그 변경은 템플릿 파일을 직접 편집하는 것으로 정당하다 — 다만 그 변경이 「데이터 모델」 계약과 어긋나지 않는지 확인하라는 같은 절의 지시를 따른다.
8. **`python3` 부재 환경에서 `step` 이 죽지 않게 하라.** 계산 블록 실패는 시간 기록만 건너뛰는 **비차단** 경로다(§8.2).
9. **매트릭스 모드에서 `.step-time` 을 만들지 말라.** `_CELL_LINE_PATTERN` 이 `<td class="cell" id="…" data-state="…">텍스트</td>` 완전 형태를 요구한다 — 칸에 속성이나 span 을 넣으면 `matrix_done` 이 `None` 이 되고 허브의 매트릭스 진행률이 사라진다.

---

## 11. 테스트 계획

### 11.1 `tests/run.sh` — T22 그룹 (개정 1건 + 신설 4건, `total_tests=24` 유지)

**T22-96 개정** (`tests/run.sh:1779-1786`) — 유물 목록에서 `data-started-at` **하나만** 제거하고, 주석에 번복 근거를 남긴다.

```bash
  # T22-96(역방향): 「지금」 카드 잔재 전무 확인 — dz-now-card·renderNowCard·now-row 중 어느
  # 문자열도 파일에 남아있지 않아야 한다(카드 자체를 제거하기로 한 결정).
  #
  # 개정(docs/prps/dashboard-step-timing.md 결정 ST1) — 목록에서 data-started-at 을 뺐다.
  # 커밋 1b199cb 가 금지한 것은 「살아 있는 경과 타이머를 그리는 전용 카드」이고, 그 금지의
  # 목적은 아래 T22-160 이 이어받는다(스크립트에 틱 코드가 없음을 직접 검사한다 — 문자열
  # 하나를 금지하는 것보다 강한 검사다). 타임스탬프 「개념」은 ST1 이 명시적으로 번복했으며,
  # 새 대시보드는 data-started-at 이라는 이름을 재사용하지 않는다(결정 ST9: 옛 세대 픽스처가
  # 그 이름에 "YYYY-MM-DD HH:MM" 형식을 담고 있어 형식이 모호해진다).
  local now_card_relic
  for now_card_relic in 'dz-now-card' 'dz-now-elapsed' 'dz-now-since' 'dz-now-next' \
    'renderNowCard' 'now-row' 'now-label' 'now-value' 'now-title'; do
    if grep -qF -- "$now_card_relic" "$dashboard_union_file"; then
      note_failure "T22-96: 「지금」 카드 잔재 발견: $now_card_relic"
    fi
  done
```

| # | 방향 | 검사 |
|---|------|------|
| **T22-159** | 정 | 계약 어휘 8종이 union 파일에 모두 있다: `data-active-since` · `data-elapsed-s` · `data-session-start` · `class="step-time"` · `.step-time:empty{display:none}` · `총 경과` · `1분 미만` · `불변식 13` |
| **T22-160** | **역 (가장 값진 검사)** | **불변식 13 의 기계적 강제.** ① 템플릿(`$dashboard_template_file`)의 `setInterval(` 등장 횟수가 **정확히 1**(폴링뿐) ② `dz-now-`·`renderNowCard`·`data-started-at` 이 템플릿에 없다 ③ `.step-time` 을 `textContent`/`innerHTML` 로 쓰는 스크립트 줄이 없다(`grep -E 'step-time.*(textContent\|innerHTML)'` 무매칭) ④ 템플릿 `<script>` 범위에 `Date.now()` 가 없다 |
| **T22-161** | 정+역 | **속성 순서 계약.** ① `id="dz-log" data-owner-token="" data-server-port="" data-session-start=""` 리터럴 존재 ② 역방향: `data-session-start` 가 `data-owner-token` **앞**에 오는 형태(`data-session-start="" data-owner-token`)가 없다 ③ `step` 절 범위에 `class="{state}"` 뒤 각인 지시 문구가 있다 |
| **T22-162** | 정+역 | **출력 계약 보존.** ① `step` 절 범위에 `NOW_S`·`BANKED_S`·`BANKED_LABEL`·`TOTAL_LABEL` 4종과 `'항상 4줄'` 이 모두 있다 ② `impl` 절 범위에 `TOTAL_LABEL` 과 `'항상 3줄'` 이 있다 ③ 역방향: `#dz-progress-pct` 에 시간을 병기하는 형태(`dz-progress-pct">` 와 `총 경과` 가 같은 줄)가 없다 |

> **T22-160 이 이 PRP 의 안전장치다.** ST1 이 DU6 을 부분 번복하는 대가로, 남은 절반을 **문자열 금지보다 강한 검사**(스크립트에 틱 코드가 실제로 없음을 확인)로 바꿔 갚는다.

### 11.2 `tests/hub/test_hub_parse.py` — 신설 4건

신규 픽스처 `tests/hub/fixtures/timed_dashboard.html`: 4단계 선형. 1번 `done`+시간, 2번 `done`+시간+상세, 3번 `active`+`data-active-since`만, 4번 `wait`+속성 없음. `#dz-log` 에 `data-session-start` 있음. `#dz-updated` 에 `· 총 경과 1시간 7분` 있음.

| # | 검사 | 왜 이것이 값진가 |
|---|------|-----------------|
| **U-5** | `timed_dashboard.html` 의 `steps` 길이가 4이고 state 순서가 `done,done,active,wait` | 시간 속성이 붙은 줄이 **여전히 매칭된다**(조용한 티어 강등 차단) |
| **U-6** | 같은 픽스처에서 2번 단계의 `detail` 이 비어 있지 않다 | **`.step-time` 이 `.step-detail` 앞에 끼어들어도 상세를 잃지 않는다** — 정규식 역추적에 우연히 의존하지 않음을 증명 |
| **U-7** | `new_generation_dashboard.html`·`old_generation_dashboard.html`·`linear_hub_dashboard.html` 이 개정 후에도 종전 결과를 낸다(기존 단언 전건 유지 + `started_at` 값 보존) | 3세대 후방 호환(S10) |
| **U-8** | `timed_dashboard.html` 의 `Tier1Snapshot` 필드 집합이 `new_generation_dashboard.html` 과 **같다**(`dataclasses.fields` 비교) | 비캡처 그룹 계약 — 페이로드가 늘지 않았다(GOTCHA 6) |

**추가 단위 검사 (`updated_text` 관용성)**: `#dz-updated` 에 `· 총 경과 …` 가 붙어도 `_UPDATED_PATTERN`(`.*?`)이 파싱에 성공하고 `updated_text` 에 그대로 담긴다.

### 11.3 라벨 규칙 `D()` 검증

`D()` 는 절차 문서 안의 Bash 에만 존재해 파이썬 단위 테스트로 잡히지 않는다. **셸 단위 검사로 대신한다** — T22-159 에 라벨 경계 4종 문자열(`1분 미만`, `%d분`, `%d시간 %d분`, `// 3600`)이 `step` 절 코드블록에 있는지 확인하고, 아래를 **수동 검증 절차**로 명시한다.

```bash
python3 - <<'PY'
def label(s):
    if s < 60:   return "1분 미만"
    if s < 3600: return "%d분" % (s // 60)
    return "%d시간 %d분" % (s // 3600, (s % 3600) // 60)
expected = {0:"1분 미만",59:"1분 미만",60:"1분",2820:"47분",3600:"1시간 0분",4020:"1시간 7분"}
for seconds, want in expected.items():
    assert label(seconds) == want, (seconds, label(seconds), want)
print("D() OK")
PY
```

### 11.4 수동 실측 (구현 완료 후 필수)

| # | 시나리오 | 기대 |
|---|---------|------|
| M1 | `init "t" "설계\|승인\|구현\|검수"` → 파일 확인 | 1번 `<li>` 에 `data-active-since`·`data-elapsed-s="0"`·빈 `.step-time`, `#dz-log` 에 `data-session-start`, 2~4번에 시간 속성 없음 |
| M2 | 60초 이상 대기 후 `step 1 done` | 1번 `.step-time` 이 `1분` 이상, `data-active-since=""`, `#dz-updated` 에 `· 총 경과` |
| M3 | `step 3 active "a"` → `step 3 active "b"` → `step 3 done` | **`data-active-since` 가 두 번째 호출에 바뀌지 않는다**(S4). 소요는 첫 `active` 부터의 시간 |
| M4 | `step 4 active` → (60초) → `step 4 wait` → (120초 대기) → `step 4 active` → (60초) → `step 4 done` | `.step-time` ≈ `2분`. **대기 120초가 포함되지 않는다**(S3) |
| M5 | 브라우저에서 티어 1 URL 로 열고 60초 폴링 대기 | 소요·총 경과가 갱신된다. **어떤 값도 초 단위로 틱하지 않는다**(S5) |
| M6 | 허브 서버 기동 후 카드·상세 패널 확인 | 활성 단계 줄과 상세가 **종전과 동일**하게 보인다(S8) |
| M7 | 라이트·다크 두 테마에서 완료 단계 줄 육안 | `.step-time` 대비 WCAG AA. 세로 증분 0px(같은 flex 행) |
| M8 | 매트릭스 모드 `init "t" "A:설계,구현\|B:설계,구현"` 후 `step 1.1 done` | 칸에 시간 속성이 **없고**, `#dz-updated` 에는 총 경과가 **있다** |
| M9 | 시간 속성이 없는 옛 대시보드에 `step 2 done` | 예외 없이 동작. 속성·span 이 새로 삽입된다(S10) |
| M10 | `bash tests/run.sh` + `python3 -m pytest tests/hub/` | 24/24 + 전건 통과(S9) |

---

## 12. 작업 순서 (검증 게이트 포함)

| # | 단계 | 검증 |
|---|------|------|
| 1 | `hub/bin/hub_parse.py` 정규식 + `timed_dashboard.html` 픽스처 + U-5~U-8 **먼저** | `pytest tests/hub/test_hub_parse.py` — 신규 4건 통과, 기존 전건 통과 |
| 2 | `dashboard_template.html`: `#dz-log` 속성 · CSS 3줄 · 헤더 주석 | `grep -c setInterval` == 1. T22-80·T22-105 리터럴 여전히 매칭 |
| 3 | `dashboard.md`: 데이터 모델(§7) · 불변식 11·12·13 | T22-92 의 `6 셀렉터` 리터럴 보존 확인 |
| 4 | `dashboard.md`: `init` 1·4단계 | 임시 디렉토리에서 실제 `init` 실행 → `ANCHOR-FAIL` 없이 `OK`, M1 통과 |
| 5 | `dashboard.md`: `step` 0·1·3단계 | §11.3 `D()` 검증 + M2·M3·M4 |
| 6 | `dashboard.md`: `impl` 0·3단계 | `'항상 3줄'` 리터럴 보존 확인 |
| 7 | `tests/run.sh`: T22-96 개정 + T22-159~162 | `bash tests/run.sh` 24/24 |
| 8 | `docs/prps/dashboard-rationale.md` `<a id="step-timing">` + `README.md` | 링크 유효성 · `wc -l` 실측 반영 |
| 9 | 수동 실측 M5~M10 | 전건 통과 |

**에스컬레이션 조건**: 5단계에서 오케스트레이터가 `KEY=값` 5줄을 잘못 옮기는 사례가 관측되면(예: `BANKED_LABEL` 대신 `BANKED_S` 를 `.step-time` 에 넣음), 절차를 더 손대지 말고 **`step` 0단계 전체를 grep 대신 python3 한 덩어리로 바꾸는 설계 변경**을 제안하고 승인을 받는다(그 형태는 `<li>` 줄 전문까지 python 이 출력해 Edit 앵커로 넘긴다). 문구를 조금씩 다듬어 버티지 않는다.

---

## 13. 남는 한계 (문서에 남길 것)

| 한계 | 왜 감수하는가 |
|------|--------------|
| 총 경과가 **마지막 갱신 시점**에 멈춘다 | 살아 있는 값은 DU6 의 살아남은 절반(불변식 13)에 정면 위배. `step` 은 몇 분 간격으로 불리므로 실사용에서 지연이 작다 |
| 단계 소요의 **합 < 총 경과** | `wait` 구간과 `active` 를 거치지 않은 단계 때문. 두 값을 억지로 맞추면 관측하지 않은 시간을 발명하게 된다 |
| 매트릭스 모드에 칸별 소요가 없다 | ST3. `.step-detail` 이 이미 선형 전용인 확립된 선례 |
| `impl` 항목에 소요가 없다 | 표준 경로가 `impl` 을 부르지 않는다(`dashboard.md:59-64`). YAGNI |
| 시간 정밀도가 **초**이고 표시는 **분** | 이 워크플로우의 단계 소요 실측 중앙값이 5.8분, p90 29.1분이다(`dashboard.md:713-714` 의 훅 이벤트 6일분 분석). 초 단위 표시는 정보가 아니라 소음이다 |
| 허브 화면에는 소요가 안 보인다 | §4 비목표. 데이터는 파일에 있으므로 나중에 별도 판단으로 노출할 수 있다 |
