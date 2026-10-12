> ⚠️ **실험 원본 — 승인된 설계가 아니다.**
> 이 문서는 모델·프롬프트 A/B 실험의 **실험 2 · FN(fable + 무스캐폴딩) · 36/50 · 3위** 산출물이다.
> 여기 설계된 기능은 구현되지 않았고, 앞으로 구현할 계획도 없다.
> **저장소 선례로 인용하지 않는다.** 실험 설계·채점·결론은
> [`../model-scaffolding-ab-experiments.md`](../model-scaffolding-ab-experiments.md) 를 본다.
> 본문은 이 배너 블록 아래부터 서브에이전트 원본 그대로다(내용 무수정).

---

# 대시보드 단계별 소요 시간 — `data-started-at`·`data-ended-at` 각인과 파생 시간 뷰 (PRP)

- **산출물 예정 경로**: `docs/prps/dashboard-step-elapsed-time.md` (이번 작업은 반환 전용 — 파일 미생성)
- **기준 커밋**: `07857ef` (main)
- **경로 분류**: 전체 경로 대상 설계 문서. 대상 파일이 `commands/dashboard.md` + `commands/dashboard_template.html` + `hub/bin/hub_parse.py` + `tests/` 4계열에 걸치고(3개 파일 초과), DOM 계약(공개 인터페이스)이 바뀐다.
- **결정 ID**: `ET1`~`ET12` (Elapsed Time)

---

## 배경 — 왜 지금, 왜 다시

### 현행의 공백

`/dashboard` 는 진행 단계의 상태(`done|active|wait`)와 한 줄 상세만 기록한다. 동적 셀렉터 표의 `#dz-step-{n}` 행이 치환 대상으로 정의하는 것은 `class` 속성 + `.chip` 텍스트 + `.step-detail` 텍스트뿐이며(`commands/dashboard.md:130`), 시각 정보는 문서 전체에서 `#dz-updated`(갱신 시각, `dashboard.md:134`)와 로그 항목의 `HH:MM`(`dashboard.md:849`) 둘뿐이다. 단계가 **언제 시작해 언제 끝났는지, 그래서 얼마나 걸렸는지**는 어디에도 남지 않는다.

### 전사(前史) — 이 기능은 두 번 만들어졌고 두 번 제거됐다

| 커밋 | 내용 |
|------|------|
| `08f3a01` | 대시보드 최초 도입(「현재 위치 카드」 포함) |
| `56229a1` | 현재 위치 카드 제거 |
| `be89947` | 「지금」 카드 + `data-started-at` 각인 + 경과 시간 표시 도입 (PRP: `docs/prps/dashboard-current-next-card.md`) |
| `1b199cb` | 「지금」 카드·`data-started-at` 각인 로직·불변식 7 **완전 제거** |

`1b199cb` 의 제거 사유(커밋 본문): *"검증 스크린샷 검토 후 정보 자체가 불필요하다는 판단으로 카드와 전용 코드(렌더 함수 4종, data-started-at 각인 로직, 불변식 7)를 완전히 제거 — 현재 작업 내용은 단계 목록의 활성 항목 상세(.step-detail) 한 줄로 충분하다."*

그때 제거된 것은 **표시 형식(단계 목록과 중복되는 별도 카드)** 과 그에 딸린 데이터였다. 이번 요구는 다른 질문이다 — "지금 무엇을 하는가"(당시 `.step-detail` 로 충분하다고 판정)가 아니라 **"각 단계가 얼마나 걸렸는가"(회고적 소요 시간)와 총 경과**다. 당시 PRP 자체가 축소 대안으로 *"활성 `<li>` 안에 경과 시간만 붙이는 안(카드 없음)"*(`dashboard-current-next-card.md:893~895`)을 언급했고, 이번 설계는 정확히 그 방향(단계 행 안에 시간을 싣는다)으로 간다 — 중복 카드를 만들지 않으므로 `1b199cb` 의 제거 근거와 충돌하지 않는다. 전제가 바뀌면(사용자가 소요 시간을 명시 요청) 결정을 공개적으로 번복하는 것이 이 저장소의 선례다(`dashboard.md:766~773` DU5, `hub-session-revival` RV1).

### 재사용 가능한 유산

- **허브 파서는 이미 `data-started-at` 을 읽는다.** `hub/bin/hub_parse.py:61~67` 의 `_STEP_LINE_PATTERN` 이 선택 그룹으로 수용하고, `StepView.started_at`(`hub_parse.py:32`)에 담는다(구세대 대시보드 후방 호환용으로 존치). 값 형식 `YYYY-MM-DD HH:MM` 은 픽스처와 테스트에 고정돼 있다(`tests/hub/fixtures/linear_hub_dashboard.html:128~131`, `tests/hub/test_hub_parse.py:39`).
- **파싱·포맷 함수의 검증된 구현**이 구세대 픽스처에 보존돼 있다: `parseStamp`(`linear_hub_dashboard.html:210~213` — `new Date(문자열)` 의 구현 정의 파싱을 피해 필드를 직접 뽑는다), `formatDuration`(`:214~219` — 음수·비유한 값에 빈 문자열), 30초 틱(`NOW_TICK_MS`, `:186`). 이 함수들은 그대로 되살린다.
- **역방향 테스트 T22-96**(`tests/run.sh:1779~1787`)이 `data-started-at` 을 「지금」 카드 잔재로 금지하고 있다 — 이번 설계의 유일한 정면 충돌 지점이며, 계획적으로 개정한다(테스트 계획 참조).

---

## 요구사항

### 기능 요구

| ID | 요구 | 수용 기준 |
|----|------|----------|
| R1 | 단계가 `active` 로 전이한 시각과 `done` 으로 전이한 시각을 대시보드 파일에 기록한다 | 선형 모드 `<li id="dz-step-{n}">` 에 `data-started-at`·`data-ended-at` 속성(`YYYY-MM-DD HH:MM`)이 전이 시점에 각인된다. `init` 이 만드는 1번 단계(즉시 active)에도 시작 시각이 각인된다 |
| R2 | 완료된 단계는 그 단계의 소요 시간을 단계 행에서 읽을 수 있다 | `done` 행 우측에 `17분`·`1시간 3분` 형식 표시. 시작 관측이 없는 wait→done 직행 단계(표준 전체 경로의 「승인」)는 직전 단계의 종료 시각을 시작으로 삼아 계산한다 |
| R3 | 진행 중 단계는 현재까지의 경과가 표시되고 스스로 갱신된다 | `active` 행 우측에 경과 표시, 30초 주기 재계산. `file://`(리로드 모드)에서도 틱이 돈다 |
| R4 | 세션 총 경과를 한 줄로 보여준다 | 진행률 아래 `총 경과 N` — 모든 단계 `done` 이면 마지막 종료 시각으로 고정되고 라벨이 `총 소요 N` 으로 바뀐다 |
| R5 | 호출 규약(인자)은 바꾸지 않는다 | `/dashboard init·step·impl·log` 의 인자 문법 무변경(`dashboard.md:21~31` 그대로). 각인은 상태 전이의 부수 효과다 |
| R6 | 타임스탬프는 추정이 아니라 셸 시계에서 온다 | `init` 1단계·`step` 0단계의 기존 Bash 호출에 `date '+%Y-%m-%d %H:%M'` 을 합류시키고, 그 출력만 각인에 쓴다(신규 Bash 호출 0회) |
| R7 | 외부 소비자(`/hub`)의 파싱이 깨지지 않는다 | `hub_parse._STEP_LINE_PATTERN` 이 새 속성 조합 4종(무/시작만/종료만/둘 다)을 모두 파싱한다. 갱신 없이는 활성 단계 줄이 허브 카드에서 사라진다(영향 범위 참조) — 같은 변경에 포함한다 |

### 비기능 요구

- **절차 비용 불변**: `step` = Bash 1회 + Edit 3회(`dashboard.md:639`), `init` = 기존 호출 수 그대로. 새 도구 호출 0회.
- **파일이 곧 상태**: 별도 상태 파일(JSON) 금지 원칙(`dashboard.md:10`) 유지 — 상태는 두 속성, 표시는 파생.
- **모델 산술 금지**: 오케스트레이터는 소요 시간을 **계산하지 않는다**(±1 전이 산술 외의 시간 뺄셈은 전부 브라우저 몫). LLM 산술 오류를 원천 차단한다.
- **불변식 2·3·5 유지**: 속성은 기존 `<li>` 줄 **안**에 얹힌다 — 줄 수·줄 경계 불변(`dashboard.md:149~152`). 감사용 `grep -c 'dz-step-.*class="done"'`(`dashboard.md:696`)은 속성이 `class` 뒤에 오므로 계수 불변.

### 비목표 (전부 선례 있는 기각)

| 항목 | 근거 |
|------|------|
| `#dz-impl-{k}` 항목별 시간 | `dashboard-current-next-card.md:95` — impl-substeps 비목표에서 기각된 것을 그대로 유지. impl 은 fan-out 전용 예외 경로다(`dashboard.md:59~64`) |
| 매트릭스 모드(`#dz-cell-*`) 각인·표시 | `dashboard-current-next-card.md:516` — `<td>` 각인은 소비자 없는 YAGNI 로 기각됐다. 이번에도 선형 전용 |
| 「지금」 카드·`마지막 기록 N분 전` 부활 | `1b199cb` 가 중복 표시로 제거. 이번 설계는 카드를 만들지 않는다 |
| 허브 티어 1 카드에 시간 표시 | 허브 상세 패널은 대시보드 문서 자체를 iframe 으로 렌더하므로(`dashboard.md:244~247`) 스크립트가 실행돼 시간이 **자동으로 보인다**. 카드(`renderTier1ActiveStep`, `hub/bin/hub_template.html:1233~1242`) 확장은 별도 결정 |
| 초 단위 정밀도 | 실측 단계 소요가 분~시간 규모다(구현 단계 중앙값 5.8분·p90 29.1분, `dashboard.md:714`). `#dz-updated`·허브 `stale_after_minutes` 와 같은 분 단위 어휘를 유지한다 |
| `impl`·`log` 절차의 시계 통일 | 두 절차는 시간 속성을 각인하지 않고, `#dz-updated` 는 이 기능의 계산에 쓰이지 않는다. `impl set` 0단계의 "결과 3/2/0~1줄" 판정(`dashboard.md:745~750`)에 date 줄이 섞이면 판정 어휘를 전부 고쳐야 한다 — 가치 없는 파급이다 |

---

## 설계 결정

| ID | 결정 | 근거 · 기각한 대안 |
|----|------|------------------|
| ET1 | **상태는 속성 2개, 표시는 파생 뷰.** 파일에는 `data-started-at`·`data-ended-at` 만 쓰고, `17분`·`총 경과` 같은 계산 결과 텍스트는 스크립트만 그린다 | "DOM 자체가 상태"(`dashboard.md:10`) + 오케스트레이터 산술 금지. 대안(done 전이 때 오케스트레이터가 소요 문자열을 각인)은 모델 시간 뺄셈이라 기각. 구세대 불변식 7(파생 뷰)의 부활이다 |
| ET2 | **시간은 단계 행 안에 싣는다**(`.chip` 왼쪽 `.step-time` 스팬) + 진행률 아래 `#dz-total-elapsed` 한 줄. 카드를 만들지 않는다 | `1b199cb` 의 제거 근거(중복 카드)를 존중. `dashboard-current-next-card.md:893~895` 의 축소 대안 채택 |
| ET3 | **스크립트가 시각을 각인하는 안은 기각**(구세대와 동일 판정) | 브라우저를 연 시점에 종속돼 값이 리셋되고 파일에 되쓸 수 없다(`dashboard-current-next-card.md:489, 859`) |
| ET4 | **active 재진입(done→active 회귀 등)은 시작 시각을 덮어쓰고 종료 시각을 지운다** — 그 단계의 표시는 마지막 회차 소요다 | 회차별 이력은 작업 추적 로그의 `--round N` 배지가 담당(`dashboard.md:214`). 누적 합산은 모델 산술이라 기각. active→active(상세만 갱신)는 구세대 규칙대로 리셋 금지(`dashboard-current-next-card.md:340~341`) |
| ET5 | **wait→done 직행 단계의 시작 = 직전 단계의 `data-ended-at`** (표시 쪽 파생 규칙, 파일 각인 없음) | 표준 전체 경로에서 「승인」은 active 를 거치지 않는다(트리거 표, `dashboard.md:49~50`: PRP 완료 → `step 1 done`, 승인 수령 → `step 2 done`). 직전 단계 종료~자신의 완료가 곧 그 단계의 실구간이다. 직전 단계에 종료 관측이 없으면 표시하지 않는다(추측 금지) |
| ET6 | **시계는 기존 Bash 호출에 합류한 `date` 출력이다.** `init` 1단계는 이름/토큰 사이 가운데 줄, `step` 0단계는 마지막 줄 | 현행 절차는 "현재 시각"의 출처를 정의하지 않는다(`dashboard.md:547, 689` — 명령 없음). 소요 시간의 가치는 스탬프 정확도에 정비례하므로 출처를 셸로 못 박는다. 프로젝트 이름을 "방금 출력한 것을 그대로 쓴다"(`dashboard.md:509~511`)와 같은 원칙. 신규 Bash 0회 |
| ET7 | **`init` 1단계 출력은 3줄이 된다**(이름 / 시각 / 토큰). date 를 **가운데**에 넣는다 | 기존 앵커 2개("첫 줄 = 이름", "마지막 줄 8글자 = 토큰", `dashboard.md:499~502, 509~517`)가 둘 다 살아남는 유일한 삽입 위치다 |
| ET8 | **`step` 0단계 출력은 5줄이 된다**(grep 4 + date 1). `&&` 연결이라 grep 전면 실패(대상 0건) 시 date 도 안 나온다 | 그 경로는 어차피 보고 후 중단이다(`dashboard.md:653~655`). grep 줄은 `NN:` 접두어, date 줄은 무접두어라 식별이 결정적이다 |
| ET9 | **속성 순서 고정: `class` → `data-started-at` → `data-ended-at`** | 허브 정규식이 순서 있는 선택 그룹 2개로 4조합을 전부 수용하는 전제다. 순서가 계약이다(`data-owner-token`·`data-server-port` 가 `#dz-log` 행에 순서 있는 속성으로 계약된 것과 같은 방식, `dashboard.md:132`) |
| ET10 | **`init` 의 1번 단계 시작 각인은 li-1 템플릿 문자열에 값을 직접 넣는다**(별도 치환 쌍 없음) | 치환 쌍(`data-started-at=""` → 값)을 추가하면 매트릭스 모드에서 앵커 0회 매칭 → `ANCHOR-FAIL` 로 init 전체가 죽는다(`dashboard.md:599~602` 의 검증 루프). "분기가 값의 차이로 흡수된다"(`dashboard.md:604~605`) 원칙 유지 |
| ET11 | **렌더 코드는 폴링 IIFE 안, `if(!isServed)` 조기 return 앞에 둔다.** `apply()` 말미(`resizePipToFit()` 앞)에서 재호출한다 | 구세대와 동일 배치(`linear_hub_dashboard.html:251~252` 가 이 배치로 실동작했다). 뒤에 두면 `file://` 에서 죽는다 — 구세대 PRP 가 "설계 결정 6의 함정"으로 명시(`dashboard-current-next-card.md:203`). 별도 IIFE 안은 `#dz-steps` 가 outerHTML 로 통째 교체되는(`dashboard_template.html:355~359`) 탓에 MutationObserver 재배선이 필요해져 더 크다 |
| ET12 | **분 단위 표시, `formatDuration`·`parseStamp` 는 구세대 구현을 자구대로 재사용**(0분은 `0분` 으로 표시) | 검증된 코드다(음수·미래 시각 가드 포함). 이름은 재사용하되 `NOW_TICK_MS` 는 `ELAPSED_TICK_MS` 로 개명 — T22-96 잔재 목록의 `renderNowCard` 등과 어휘를 분리한다 |

---

## 데이터 모델

### 1. 파일 각인 — 시간 속성 2종 (상태의 전부)

```
StepTimestamps                       # <li id="dz-step-{n}"> 의 속성. 선형 모드 전용
  data-started-at : "YYYY-MM-DD HH:MM" | 부재     # active 전이 시각
  data-ended-at   : "YYYY-MM-DD HH:MM" | 부재     # done 전이 시각
```

- 값 문자는 `[0-9 :-]` 뿐이라 이스케이프가 필요 없다. 형식은 `#dz-updated` 와 자구 동일(`2026-08-27 10:42`).
- **부재와 빈 문자열은 같은 뜻이 아니다** — 빈 문자열을 쓰지 않는다(각인하거나 속성째 지운다). `data-server-port` 의 "빈 문자열 = 부재" 규약(`dashboard.md:157~158`)과 다른 점이므로 명시한다.
- 속성 순서는 ET9 로 고정.

**각인 규칙 (선형 모드 전용, 인자 없음)** — `step` 1단계의 `.step-detail` 규칙 표(`dashboard.md:662~667`) 바로 뒤에 삽입한다. 이전 상태는 0단계 grep 줄에 적혀 있다(진행률 전이 산술과 같은 출처, `dashboard.md:685`).

| 전이(이전→새) | `data-started-at` | `data-ended-at` |
|--------------|-------------------|-----------------|
| ≠active → active | **0단계 date 시각으로 각인**(있으면 값 교체 — 재진입은 새 회차다, ET4) | **제거** |
| active → active (상세만 갱신) | 유지 — **리셋 금지**(경과가 0으로 되돌아간다, 구세대 규칙) | 유지 |
| ≠done → done | 유지(없으면 없는 대로 둔다 — wait→done 직행은 ET5 가 표시 쪽에서 해결) | **0단계 date 시각으로 각인**(있으면 값 교체) |
| done → done | 유지 | 유지 — 리셋 금지 |
| any → wait | **제거** | **제거** (회귀로 무효화된 회차의 낡은 시각이 다음 wait→done 직행과 짝지어지는 것을 막는다) |

- 같은 Edit 1회 안에서 처리한다(줄 전문 치환이므로 비용 0 추가).
- 매트릭스 모드(`<g>.<p>`)는 각인하지 않고 보고도 하지 않는다(구세대 규칙 자구 유지).
- `init` 은 li-1(즉시 active)에 `data-started-at` 을 각인하고 `data-ended-at` 은 만들지 않는다.

### 2. 파생 뷰 (표시의 전부 — 스크립트 전용)

```
StepTime(li, prev, now)              # 단계 행 하나의 표시 문자열. '' 이면 스팬 자체를 제거
  started = parse(li.data-started-at)
            ?? (li.data-ended-at 존재 && prev 존재 ? parse(prev.data-ended-at) : null)   # ET5
  state=done   → started && ended ? formatDuration(started, ended) : ''
  state=active → started ? formatDuration(started, now) : ''
  state=wait   → ''

TotalElapsed(steps, now)             # #dz-total-elapsed 텍스트. '' 이면 :empty 로 숨음
  start = 각 li 의 started 최솟값 (없으면 '')
  frozen = 모든 li 가 done && ended 가 하나 이상 존재
  end   = frozen ? ended 최댓값 : now
  라벨  = frozen ? "총 소요 " : "총 경과 "
```

**워크드 예시** (구세대 픽스처의 실제 시각, `linear_hub_dashboard.html:128~131`):

```
설계  started 18:12, ended 18:29(가정)          → 17분
승인  started 없음, ended 18:36  → 시작 := 직전 ended 18:29 → 7분   (ET5)
구현  started 18:36, active, now 19:20          → 44분 (30초마다 갱신)
검수  wait                                       → 표시 없음
총    시작 18:12, 미완료 → "총 경과 1시간 8분"
```

- 손상·미래 시각·시계 되감김(DST 포함)은 `formatDuration` 이 빈 문자열을 반환해 그 조각만 조용히 빠진다(구세대 가드 계승, `linear_hub_dashboard.html:214~219, 233~237`).
- 구세대 대시보드(속성 전무)·매트릭스 세션은 아무것도 표시되지 않는다(우아한 무동작).

### 3. 불변식 개정

- **불변식 7 부활** (현행 "7은 결번" — `dashboard.md:282~283`): *단계별 소요 시간과 총 경과는 파생 뷰다. `init`·`step` 은 두 시간 속성만 파일에 쓰고, 시간 계산 결과 텍스트를 파일에 각인하지 않는다. 스크립트는 두 속성과 `#dz-steps` 를 읽기만 하고(8·9와 같은 편대) `.step-time` 스팬·`#dz-total-elapsed` 텍스트만 쓴다.* 결번의 부활임을 명기한다(원 불변식 7도 "「지금」 카드는 파생 뷰"였다 — 같은 개념의 재사용).
- **불변식 11 신설** (기존 1~6, 8, 9, 10에 이어): *시간 속성과 그 호출이 함께 쓰는 `#dz-updated` 의 시각 값은 그 호출의 Bash 가 방금 출력한 `date` 값이다(init = 1단계 출력 가운데 줄, step = 0단계 출력 마지막 줄). 기억·추정으로 시각을 쓰지 않는다. 이 불변식은 init·step 에만 적용된다(impl·log 는 비목표 참조).*
- 불변식 2·3(줄 단위·줄바꿈 금지)은 무수정 유지 — 속성은 같은 줄 안이다.

### 4. 허브 쪽 데이터 모델

`StepView` 에 `ended_at: str | None` 을 추가한다(`hub_parse.py:24~33`). `started_at` 선례와 대칭 — 파서는 DOM 계약 전체를 데이터 모델로 옮기는 모듈이고(모듈 docstring, `hub_parse.py:1~7`), 렌더러는 붙이지 않는다(비목표). 페이로드는 `asdict` 일괄 직렬화(`hub_model.py:88~100`)라 필드가 자동으로 실리며, 템플릿 JS 는 모르는 필드를 무시한다.

---

## 인터페이스

### 1. 호출 규약 — **변경 없음** (인자 0개 추가)

| 호출 | 종전 | 이후 | 인자 |
|------|------|------|------|
| `/dashboard init "…" "A\|B\|C"` | 1번 active | 동일 + 1번 `<li>` 에 `data-started-at` | 무변경 |
| `/dashboard step <n> <state> ["상세"]` | 상태 + 상세 | 동일 + 전이에 따른 시간 속성 각인(위 규칙 표) | 무변경 |
| `/dashboard step <g>.<p> <state>` | 칸 상태 | **완전히 동일** | 무변경 |
| `impl` · `log` · `serve` · `on/off` | — | **완전히 동일** | 무변경 |

보고 최소화 절(`dashboard.md:78~108`)도 무변경 — 시간 각인은 침묵 경로다.

### 2. DOM 계약 변경 (`dashboard.md` 데이터 모델 절)

**동적 표(6 셀렉터, 행 수 유지)** — `dashboard.md:130` 행만 수정:

| 셀렉터 | 치환 대상 | 값 |
|--------|----------|-----|
| `#dz-step-{n}` (그룹 1개) | `class` 속성 + **`data-started-at`·`data-ended-at` 속성** + 자식 `.chip` 텍스트 + 자식 `.step-detail` 텍스트 | `done\|active\|wait` / **`YYYY-MM-DD HH:MM`(전이 시에만 — `step` 1단계 각인 규칙 표)** / `완료\|진행중\|대기` / 한 줄 상세 |

**정적 요소 추가 표**(`dashboard.md:262~271`)에 1행:

| 요소 | 역할 |
|------|------|
| `#dz-total-elapsed` | 총 경과/총 소요 텍스트 `<div>`. `.pct` 아래. **스크립트(`renderStepTimes`)만 쓴다** — `init`/`step`/`log` 도, 폴링 동기화도 치환하지 않는다. 비면 `:empty` 가 숨긴다 |

**폴링 동기화 계약**(`dashboard.md:296~301`)에 1행: *`.step-time` 스팬은 라이브 DOM 전용이다 — `syncVisualization` 의 outerHTML 교체가 지워도 `apply()` 말미의 `renderStepTimes()` 가 같은 프레임에 복원한다. `#dz-total-elapsed` 는 치환 제외 목록에 든다.*

### 3. 절차 인터페이스 변경

**`init` 1단계** (`dashboard.md:491~494`) — `basename` 뒤에 date 합류:

```bash
     cp "$dz_template" .claude/dashboard.html \
       && basename "$PWD" \
       && date '+%Y-%m-%d %H:%M' \
       && od -An -N4 -tx1 /dev/urandom | tr -d ' \n' && echo
```

출력 계약 표(`dashboard.md:499~502`): `2줄` → **`3줄`** — 첫 줄 = 프로젝트 표시 이름(불변), **가운데 줄 = 이번 호출의 시각**, 마지막 줄 8글자 = 소유 토큰(불변). `NOTEMPLATE` 1줄 경로 무변경.

**`init` 4단계** (`dashboard.md:555`) — li-1 예시 한 줄 개정(값은 1단계 가운데 줄을 그대로, ET10):

```python
"      <li id=\"dz-step-1\" class=\"active\" data-started-at=\"{1단계 출력 가운데 줄}\"><span class=\"num\">1</span>{단계명1}<span class=\"chip\">진행중</span><span class=\"step-detail\"></span></li>",
```

`updated_text`(`dashboard.md:547`)의 "{현재 시각}"도 같은 값을 쓴다고 명기(불변식 11). 치환 앵커 6종은 전부 무수정 — `ANCHOR-FAIL` 경로 불변.

**`step` 0단계** (`dashboard.md:644~649`) — date 합류, 4줄 → 5줄:

```bash
grep -n -e 'id="dz-step-{n}"' -e 'id="dz-progress-bar"' -e 'id="dz-progress-pct"' -e 'id="dz-log"' .claude/dashboard.html && date '+%Y-%m-%d %H:%M'
```

문구 개정: *"결과는 항상 5줄이다(대상 1 + 진행률 2 + 소유 토큰 1 + 시각 1). grep 줄은 `NN:` 접두어로, 시각 줄은 무접두어로 식별한다."* 매트릭스 변형(첫 패턴 교체)도 동일하게 date 를 붙인다(각인은 없지만 3단계 `#dz-updated` 가 이 시각을 쓴다).

**`step` 1단계** — 각인 규칙 표 삽입(데이터 모델 절 참조). **`step` 3단계**(`dashboard.md:689`) — "현재 시각" → "0단계 date 줄의 시각".

### 4. 템플릿 파생 뷰 (`commands/dashboard_template.html`)

**마크업** — `dashboard_template.html:275`(`.pct`) 바로 뒤 1줄:

```html
    <div class="elapsed-total" id="dz-total-elapsed"></div>
```

(뒤따르는 `<ol id="dz-steps">` 2줄 앵커(`dashboard.md:571~572`)는 연속성이 깨지지 않으므로 무수정.)

**CSS** — `.pct`(`:122`) 뒤에 2줄, `.step-detail:empty`(`:135`) 뒤·`#dz-impl-card:not(:has(…))`(`:136`) 앞에 3줄:

```css
  .elapsed-total{font-size:12px;color:var(--muted);margin-top:2px}
  .elapsed-total:empty{display:none}
```
```css
  .step-time{margin-left:auto;font-size:11px;font-weight:700;color:var(--muted);flex:none}
  .step-time+.chip{margin-left:0}
  li.active .step-time{color:var(--accent-ink)}
```

(`.step-time` 이 `margin-left:auto` 를 가져가고 인접 `.chip` 의 auto 를 끈다 — auto 마진 2개가 여백을 나눠 갖는 flex 동작을 막는다. 간격은 li 의 `gap:12px`(`:124`)가 준다. `.chip` 규칙(`:131`) 자체는 무수정이라 impl 카드의 chip 정렬이 그대로다.)

**스크립트** — 폴링 IIFE 안, `setHint`(`:333`) 뒤 · `// ── 갱신 경로 A` 주석(`:335`) 앞에 삽입(ET11):

```js
  // ── 단계별 소요 시간 — #dz-steps 의 시간 속성 2종에서 파생되는 표시 전용 뷰(불변식 7) ──
  var ELAPSED_TICK_MS = 30000;   // 구세대 「지금」 카드의 NOW_TICK_MS 와 같은 값·같은 이유
  var MS_PER_MINUTE = 60000, MINUTES_PER_HOUR = 60;
  var totalElapsedEl = document.getElementById('dz-total-elapsed');

  // new Date(문자열) 은 ISO 8601 이 아닌 형식에서 파싱 결과가 구현 정의다 — 필드를 직접 뽑는다.
  function parseStamp(text){
    var f = /(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(text || '');
    return f ? new Date(+f[1], +f[2]-1, +f[3], +f[4], +f[5]) : null;
  }
  function formatDuration(from, now){
    var minutes = Math.floor((now - from) / MS_PER_MINUTE);
    if(!isFinite(minutes) || minutes < 0) return '';
    return minutes < MINUTES_PER_HOUR ? minutes + '분'
      : Math.floor(minutes / MINUTES_PER_HOUR) + '시간 ' + (minutes % MINUTES_PER_HOUR) + '분';
  }
  // wait→done 직행 단계(승인 등)는 자신의 시작 관측이 없다 — 직전 단계의 종료를 시작으로 삼는다(ET5).
  function stepTimeLabel(item, previousItem, now){
    var started = parseStamp(item.getAttribute('data-started-at'));
    var ended = parseStamp(item.getAttribute('data-ended-at'));
    if(!started && ended && previousItem) started = parseStamp(previousItem.getAttribute('data-ended-at'));
    if(!started) return '';
    if(item.classList.contains('done')) return ended ? formatDuration(started, ended) : '';
    if(item.classList.contains('active')) return formatDuration(started, now);
    return '';
  }
  function renderStepTimes(){
    var list = wrap.querySelector('#dz-steps');
    if(!list){ if(totalElapsedEl) totalElapsedEl.textContent = ''; return; }   // 매트릭스 세션
    var items = list.querySelectorAll('li');
    var now = Date.now();
    var allDone = items.length > 0, firstStarted = null, lastEnded = null;
    Array.prototype.forEach.call(items, function(item, index){
      var label = stepTimeLabel(item, index > 0 ? items[index - 1] : null, now);
      var span = item.querySelector('.step-time');
      if(label){
        if(!span){
          span = document.createElement('span');
          span.className = 'step-time';
          item.insertBefore(span, item.querySelector('.chip'));
        }
        span.textContent = label;
      } else if(span){ span.remove(); }
      if(!item.classList.contains('done')) allDone = false;
      var started = parseStamp(item.getAttribute('data-started-at'));
      if(started && (!firstStarted || started < firstStarted)) firstStarted = started;
      var ended = parseStamp(item.getAttribute('data-ended-at'));
      if(ended && (!lastEnded || ended > lastEnded)) lastEnded = ended;
    });
    if(!totalElapsedEl) return;
    var frozen = allDone && lastEnded;
    var total = firstStarted ? formatDuration(firstStarted, frozen ? lastEnded : now) : '';
    totalElapsedEl.textContent = total ? (frozen ? '총 소요 ' : '총 경과 ') + total : '';
  }
  renderStepTimes();
  setInterval(renderStepTimes, ELAPSED_TICK_MS);
```

`apply()`(`:397~406`)에는 `syncLog(fresh);` 뒤·`resizePipToFit();` 앞에 `renderStepTimes();` 1줄. **grep 유일성 불변식 준수 확인**: 이 코드는 `id="` 문자열을 만들지 않고(`dashboard.md:303~309`), 조회는 `getElementById`/`querySelector('#dz-steps')` 허용 형태뿐이다. PiP 는 `.wrap` 이동 방식이라 캡처된 `wrap` 참조·타이머가 그대로 동작하고, `file://` 는 조기 return 앞 배치로 렌더+틱이 살아 있다.

**헤더 주석 갱신 맵**(`:12~13` 및 정적 목록): `#dz-step-{n}` 항목에 두 속성(각인 주체 = init·step, 스크립트는 읽기만, 선형 전용)을, 정적 목록에 `#dz-total-elapsed` 를 추가.

### 5. 허브 파서 (`hub/bin/hub_parse.py`)

```python
_STEP_LINE_PATTERN = re.compile(
    r'<li id="dz-step-(?P<index>\d+)" class="(?P<state>done|active|wait)"'
    r'(?:\s+data-started-at="(?P<started_at>[^"]*)")?'
    r'(?:\s+data-ended-at="(?P<ended_at>[^"]*)")?>'
    r'<span class="num">\d+</span>(?P<name>.*?)<span class="chip">.*?</span>'
    r'(?:<span class="step-detail">(?P<detail>.*?)</span>)?</li>'
)
```

`StepView` 에 `ended_at: str | None` 추가(기본값 없음 — `started_at` 과 동일 관례), `_parse_steps`(`hub_parse.py:81~94`)에 `ended_at=match["ended_at"]` 1줄.

---

## 영향 범위

### 파일별 변경

| 파일 | 변경 | 크기 감 |
|------|------|--------|
| `commands/dashboard.md` (1316줄) | ① 동적 표 `#dz-step` 행 수정(행 수 6 유지, :130) ② 정적 표 1행(:262~271) ③ 불변식 7 부활 + 11 신설(:282~294 인근) ④ 폴링 계약 1행(:296~301) ⑤ `init` 1단계 명령·출력 계약(:491~502, 509~517) ⑥ `init` 4단계 li-1 예시(:555)·updated_text 주석(:547) ⑦ `step` 0단계 명령·5줄 계약(:644~649) ⑧ `step` 1단계 각인 규칙 표(:667 뒤) ⑨ `step` 3단계 문구(:689) ⑩ 갱신 모드 절에 file:// 틱 1줄(:231~254) | +40줄 내외 |
| `commands/dashboard_template.html` (766줄) | 마크업 1줄(:275 뒤) · CSS 5줄(:122 뒤, :135 뒤) · 스크립트 ~55줄(:333~335 사이) + `apply()` 1줄(:405 앞) · 헤더 주석 ~4줄 | +65줄 내외 |
| `hub/bin/hub_parse.py` (136줄) | `StepView.ended_at` · 정규식 선택 그룹 1개 · `_parse_steps` 1줄 · docstring 갱신 | +4줄 |
| `tests/run.sh` | T22-96 잔재 목록에서 `data-started-at` 제거(:1782) · 신설 T22-159~165 · T22 헤더 범위 문자열(:1053) 갱신 | +50줄 내외 |
| `tests/hub/test_hub_parse.py` | 신규 클래스 1개(인라인 HTML, 4조합) · 기존 픽스처 테스트에 `ended_at is None` 단언 보강 | +40줄 내외 |
| `README.md` | :139 의 두 줄 수(1315·766)를 구현 후 `wc -l` 실측으로 갱신 + 설명에 "단계별 소요 시간" 어절 반영 | 2줄 |
| 변경 없음 | `hub_model.py`(asdict 자동 직렬화) · `hub_template.html`(렌더 무변경) · `hub_collect.py` · `install.sh`(`COMMANDS_FILE_COUNT` — 파일 수 불변, run.sh:1122~1130) · 픽스처 5종(세대 문서로 동결) | — |

### 세대 조합 매트릭스 (배포 순서 리스크)

| 대시보드 세대 \ 허브 세대 | 구허브(파서 미갱신) | 신허브 |
|---|---|---|
| 구세대 파일(속성 없음) | 현행 그대로 | 정상 — 새 선택 그룹은 전부 옵션이다 |
| **신세대 파일(속성 있음)** | **`_STEP_LINE_PATTERN` 불일치 → `steps=()`.** 티어 강등은 아니다(`parse_dashboard_html` 은 title/progress/updated 로만 None 판정 — `hub_parse.py:112~118`) — 진행률은 남고 **활성 단계 줄(`renderTier1ActiveStep`, `hub_template.html:1233~1242`)만 조용히 사라진다** | 정상 |

완화: `hub_parse.py` 갱신을 **같은 커밋**에 담고, 커밋 메시지·README 에 허브 재설치(`hub/install.sh` 또는 `/harness-update`) 필요를 명기한다. 허브 상세 패널의 iframe 표시는 파서와 무관하게 신기능이 즉시 보인다.

### 불변식·기존 검사와의 정합 (전수 점검)

| 계약 | 판정 |
|------|------|
| 불변식 2·3·5 (한 줄 하나·줄바꿈 금지) | 유지 — 속성은 기존 줄 안 |
| `step` 0단계 grep 앵커 `id="dz-step-{n}"` | 유지 — 속성이 뒤에 붙는다 |
| 감사 `grep -c 'dz-step-.*class="done"'` (`dashboard.md:696`) | 계수 불변 — 속성이 `class` 뒤 |
| 진행률 전이(±1) 산술 (`dashboard.md:680~687`) | 무접촉 — 같은 grep 줄의 이전 상태를 한 번 더 읽을 뿐 |
| grep 유일성 불변식 (`dashboard.md:303~309`) | 스크립트는 `id="` 를 생성하지 않는다(위 코드로 보장, T22-38 이 감시) |
| 갱신 훅 `dzRequestRefresh` (`:311~318`) | 무접촉 — `poll` 대입 그대로, `apply` 내부만 1줄 |
| 소유권 검증·`data-owner-token`·`data-server-port` | 무접촉 |
| `impl`·`log`·`serve`·`on/off` 절차 | 무접촉 |
| PiP (`measureCompactHeight`·`.wrap` 이동) | `#dz-total-elapsed` 가 `.wrap` 안이라 함께 이동·측정된다. 코드 무변경 |
| 임베드(`body.dz-embedded`) | 시간 표시는 숨기지 않는다 — 패널 안에서도 유효한 정보다 |
| T22-96 역방향 (`tests/run.sh:1779~1787`) | **계획된 충돌** — 잔재 목록에서 `data-started-at` 1개만 제거. `dz-now-*`·`renderNowCard`·`now-row` 등 카드 잔재 금지는 전부 유지(이번 코드는 그 문자열을 쓰지 않는다) |

---

## 파일 구조

새 런타임 파일은 없다. 상태 파일 금지 원칙(`dashboard.md:10`) 그대로다.

```
coding-harness/
├── commands/
│   ├── dashboard.md                  # [수정] 절차·DOM 계약·불변식 (변경 지점 10곳, 위 표)
│   └── dashboard_template.html       # [수정] 마크업 1 + CSS 5 + 파생 뷰 스크립트 + 헤더 주석
├── hub/bin/
│   └── hub_parse.py                  # [수정] StepView.ended_at + _STEP_LINE_PATTERN
├── tests/
│   ├── run.sh                        # [수정] T22-96 개정 · T22-159~165 신설
│   └── hub/test_hub_parse.py         # [수정] 시간 속성 4조합 파싱 테스트
├── README.md                         # [수정] 줄 수 2건 실측 갱신 + 기능 어절
└── docs/prps/
    └── dashboard-step-elapsed-time.md  # [신규] 이 문서. dashboard.md 의 새 절이
                                        #        "근거: 결정 ET1~ET12" 로 링크한다
```

템플릿 내부 배치 지도(삽입 위치 고정):

```
dashboard_template.html
  7~68   헤더 주석 갱신 맵      ← #dz-step 항목에 속성 2종, 정적 목록에 #dz-total-elapsed
  122    .pct                   ← 바로 뒤에 .elapsed-total 2규칙
  131    .chip                  (무수정)
  135    .step-detail:empty     ← 바로 뒤에 .step-time 3규칙 (#dz-impl-card :has 앞)
  275    .pct div               ← 바로 뒤에 #dz-total-elapsed div 1줄
  333    setHint 정의           ← 바로 뒤에 파생 뷰 블록(상수 4·함수 3·기동 2줄)
  335    갱신 경로 A 분기        (파생 뷰가 이 앞이어야 file:// 에서 산다 — ET11)
  405    resizePipToFit() 호출  ← 바로 앞에 renderStepTimes() 1줄
```

---

## 구현 순서 (마일스톤 · 각자 검증 게이트)

1. **M1 — 허브 파서 선행**: `hub_parse.py` + `test_hub_parse.py`. 검증: `python3 -m unittest discover -s tests/hub -t .` 전건 통과(신·구 픽스처 동시).
2. **M2 — 템플릿**: 마크업·CSS·스크립트·헤더 주석. 검증: 속성을 손으로 넣은 임시 사본을 `file://` 와 `/dashboard serve` 양쪽으로 열어 R2~R4 실측(30초 틱, 폴링 후 스팬 복원, 매트릭스 세션 무표시, PiP 진입/복귀).
3. **M3 — 절차서**: `dashboard.md` 10개 지점. 검증: 표·불변식 번호·앵커 문자열이 템플릿과 자구 일치하는지 대조.
4. **M4 — 테스트 하네스**: T22-96 개정 + T22-159~165. 검증: `bash tests/run.sh` 24/24(T24 가 M1 을 포함 실행, `tests/run.sh:2568~2581`).
5. **M5 — 문서·배포**: README 실측 갱신, `install.sh --scope user` + `hub/install.sh` 재설치 안내를 커밋 메시지에 명기.

---

## 테스트 계획

### 1. `tests/run.sh` — T22 하위 검증 (합본 = dashboard.md + 템플릿, `run.sh:1090~1091`)

| 번호 | 검사 | 방식 | 막는 회귀 |
|------|------|------|----------|
| T22-96 **개정** | 잔재 목록에서 `data-started-at` 제거(목록 10→9개, `run.sh:1782`) — 나머지 9개 문자열 금지는 유지 | 기존 루프 그대로 | 「지금」 카드 부활 감시는 계속, 새 기능만 통과 |
| T22-159 | 각인 규칙 표 존재 — `data-ended-at` 와 "리셋 금지" 문구 | `grep -qF` ×2 | 각인 시점이 흐려져 매 호출 리셋되는 회귀(구 T22-62 계승) |
| T22-160 | `id="dz-total-elapsed"` 가 템플릿에 정확히 1줄 + `.elapsed-total:empty{display:none}` 존재 | `grep -c` == 1 · `grep -qF` | 총 경과 요소 소실·빈 값 노출 |
| T22-161 | `parseStamp`·`formatDuration`·`ELAPSED_TICK_MS`·`renderStepTimes` 4식별자 존재 | `grep -qF` ×4 | 파생 뷰 소실 |
| T22-162 | `renderStepTimes` 기동이 `if(!isServed)` **앞** | `grep -n` 줄 번호 비교(T22-153 문체, `run.sh` 선례) | file:// 에서 시간이 죽는 ET11 함정 |
| T22-163 | `apply()` 안에서 `renderStepTimes();` 가 `resizePipToFit();` 앞 | 줄 번호 비교 | 폴링 직후 시간 스팬이 최대 30초 사라지는 깜빡임 |
| T22-164 | `step` 0단계 명령에 `date '+%Y-%m-%d %H:%M'` + "결과는 항상 5줄" 문구 | `grep -qF` ×2 | 시계 없는 추정 시각 회귀(불변식 11) |
| T22-165 | `init` 4단계 li-1 예시에 `data-started-at=` + `init` 1단계에 date 합류 | `grep -qF` ×2 | 1번 단계 시작 관측 누락 → 총 경과 전멸 |

T22 헤더의 범위 문자열(`run.sh:1053`)을 `T22-1~T22-165` 로 갱신. `total_tests=24`(`run.sh:5382`) 불변(하위 검증은 총계에 안 든다).

### 2. `tests/hub/test_hub_parse.py` — 단위 테스트 (T24 우산이 실행)

인라인 HTML 방식(`ParseEscapedDetailTest` 선례, `test_hub_parse.py:129~145`). 픽스처 5종은 세대 기록물로 동결한다.

| 케이스 | 입력 li | 단언 |
|--------|---------|------|
| 둘 다 | `class="done" data-started-at="2026-08-27 10:00" data-ended-at="2026-08-27 10:17"` | `started_at`·`ended_at` 자구 일치, `state=="done"`, `detail` 정상 |
| 시작만 | `class="active" data-started-at="…"` | `ended_at is None` — 진행 중 형태 |
| 종료만 | `class="done" data-ended-at="…"` | `started_at is None` — wait→done 직행 형태(ET5 의 입력) |
| 무속성 | 현행 신세대 형태 | 둘 다 None — **기존 4개 픽스처 테스트가 이 회귀를 이미 담당**(`test_hub_parse.py:77~79, 107~109` 는 무수정 통과해야 한다) |
| 보강 | `ParseLinearDashboardTest` (구세대 픽스처) | `first.ended_at is None` 1줄 추가 — started-at 단독 세대의 후방 호환 |

### 3. 수동 실측 체크리스트 (M2 게이트 — 이 저장소의 실측 주석 관례를 따라 결과를 템플릿 주석 또는 PRP 에 남긴다)

1. 선형 4단계 사본에 속성을 심고 `file://` 로 열기 → done 행 `N분`, active 행 경과, `총 경과` 표시. 31초 대기 → active 값 증가(R3).
2. `/dashboard serve` 로 열고 파일의 active 행을 done+`data-ended-at` 으로 편집 → `dzRequestRefresh()` 강제 → 스팬이 지워졌다가 같은 프레임에 복원되는지(육안 깜빡임 없음)·`총 소요` 로 고정되는지(R4).
3. 매트릭스 사본 → `.step-time`·총 경과 전무, 콘솔 에러 0(우아한 무동작).
4. 구세대 사본(속성 전무) → 표시 전무, 기존 기능 무손상.
5. PiP 진입/복귀 → 시간 유지·틱 지속. 허브 상세 패널 iframe → 시간 표시 + 허브 카드의 활성 단계 줄 잔존(M1 파서 확인).
6. wait→done 직행(승인 패턴) 사본 → 직전 ended 기준 소요 표시(ET5 워크드 예시 값과 대조).

### 4. 회귀 전건

`bash tests/run.sh` 24/24 + `python3 -m unittest discover -s tests/hub -t .` 전건. 특히 T22-38(grep 유일성)·T22-96(개정 후 9종 잔재)·T22-152~153(상호작용 잠금 배치) 무손상 확인.

---

## 리스크와 완화

| 리스크 | 완화 |
|--------|------|
| 세션이 date 출력을 안 읽고 시각을 추정 각인 | 불변식 11 + 절차 문구를 프로젝트 이름 선례("방금 출력한 것을 그대로 쓴다", `dashboard.md:509~511`)와 같은 강도로 명기. T22-164/165 가 명령 존재를 강제 |
| 구허브 × 신대시보드 조합에서 허브 활성 단계 줄 소실 | 같은 커밋에 파서 포함 + 재설치 안내(영향 범위 매트릭스). 소실 모드가 "조용한 강등"이 아니라 표시 1줄 결락임을 커밋 메시지에 명기 |
| active 재진입으로 1회차 소요가 화면에서 사라짐 | ET4 명문화 — 회차 이력은 로그 `R{N}` 배지가 정본. 표시 의미를 "마지막 회차 소요"로 정의 |
| 시계 되감김·DST 로 음수 구간 | `formatDuration` 가드가 그 조각만 비운다(구세대 검증 코드 계승) |
| 폴링 outerHTML 교체로 스팬 소실 | `apply()` 말미 재렌더(T22-163) + 30초 틱의 이중 안전망 |
| `ANCHOR-FAIL` 유발 | 템플릿 앵커 6종 무수정(ET10). 삽입은 전부 앵커 줄 "뒤"라 등장 횟수 불변 |

## 완료 기준

- R1~R7 수용 기준 전부 충족, 비목표 미침범.
- `bash tests/run.sh` 24/24 · 허브 단위 테스트 전건 통과.
- 수동 실측 6항목 결과 기록.
- README 줄 수 실측 일치, `install.sh`/`hub/install.sh` 재설치로 전역 배포 확인.

---

**구현 착수 전 필독**: `commands/dashboard.md:112~333`(DOM 계약·불변식), `:639~697`(step 절차), `:482~610`(init 1·4단계), `commands/dashboard_template.html:294~344`(폴링 IIFE 머리·file:// 분기), `hub/bin/hub_parse.py` 전문(136줄), `tests/run.sh:1779~1787`(T22-96), `tests/hub/fixtures/linear_hub_dashboard.html:186~252`(재사용할 구세대 구현), `git show 1b199cb`(제거 이력).
