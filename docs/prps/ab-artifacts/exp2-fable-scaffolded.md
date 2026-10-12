> ⚠️ **실험 원본 — 승인된 설계가 아니다.**
> 이 문서는 모델·프롬프트 A/B 실험의 **실험 2 · FS(fable + 스캐폴딩) · 38/50 · 2위** 산출물이다.
> 여기 설계된 기능은 구현되지 않았고, 앞으로 구현할 계획도 없다.
> **저장소 선례로 인용하지 않는다.** 실험 설계·채점·결론은
> [`../model-scaffolding-ab-experiments.md`](../model-scaffolding-ab-experiments.md) 를 본다.
> 본문은 이 배너 블록 아래부터 서브에이전트 원본 그대로다(내용 무수정).

---

# PRP: `/dashboard` 단계별 소요 시간 — 시각 스탬프와 경과 렌더러

- **문서 위치(구현 시 저장 경로)**: `docs/prps/dashboard-step-durations.md`
- **복잡도**: Medium (수정 6 + 신설 2 파일, 코드 ~200줄 + 문서 개정)
- **결정 ID**: DT1~DT13
- **선행 문서**: [`docs/prps/session-dashboard.md`](../prps/session-dashboard.md)(창립), [`docs/prps/dashboard-ui-cleanup.md`](../prps/dashboard-ui-cleanup.md)(구세대 경과 표시 제거), [`docs/prps/hub-dashboard.md`](../prps/hub-dashboard.md)(허브 파서 계약), [`docs/prps/dashboard-group-matrix.md`](../prps/dashboard-group-matrix.md)(매트릭스 모델)

---

## 1. 요구사항 요약

대시보드는 진행 단계의 상태(done/active/wait)만 기록하고 각 단계가 얼마나 걸렸는지는 남기지 않는다(`commands/dashboard.md:123-134` — 동적 셀렉터 계약에 시각 정보가 없다). 단계가 **active 로 바뀐 시점**과 **done 으로 바뀐 시점**을 생성물 `.claude/dashboard.html` 의 DOM 속성으로 기록하고, 대시보드 화면에서 **단계별 소요 시간**(완료 단계는 확정 구간, 진행 단계는 지금까지의 경과가 틱)과 **총 경과**(발행 시점부터, 전 단계 완료 시 확정값으로 동결)를 보이게 한다. 사용자용 호출 규약(`/dashboard init|step|log|impl|serve|on|off`)은 한 글자도 바뀌지 않는다 — 스탬프는 기존 `init`·`step` 호출의 내부 동작으로 얹힌다.

**User Story**: 오케스트레이터 세션을 지켜보는 사용자로서, 각 단계가 실제로 얼마나 걸렸고 지금 단계가 얼마나 지체되고 있는지를 대시보드에서 바로 읽어, 개입(에스컬레이션·중단) 판단을 할 수 있다.

## 2. 이력 — 이것은 신규가 아니라 근거 있는 재도입이다

이 저장소에는 같은 계열 기능이 **있다가 제거된 이력**이 있다. 설계가 이 이력을 모르면 테스트 1건이 구현을 차단한다.

- 구세대 대시보드는 `data-started-at="2026-08-10 18:36"`(사람이 읽는 형식)을 선형 `<li>` 에 각인하고, 「지금」 카드가 활성 단계의 경과를 30초 틱(`NOW_TICK_MS = 30000`)으로 그렸다 — 실물: `tests/hub/fixtures/linear_hub_dashboard.html:129-130`, `tests/hub/fixtures/impl_dashboard.html:166,195-232`(`formatDuration`·`renderNowCard` 원문).
- 커밋 `1b199cb`(2026-08-12)가 「지금」 카드 전체(렌더 함수 4종 · `data-started-at` 각인 로직 · 불변식 7)를 제거했다. 커밋 메시지의 사유: *"검증 스크린샷 검토 후 정보 자체가 불필요하다는 판단 … 현재 작업 내용은 활성 항목 상세(.step-detail) 한 줄로 충분"*. 불변식 7이 결번인 이유가 이것이다(`commands/dashboard.md:282`).
- 그 제거를 회귀 테스트가 고정하고 있다: `tests/run.sh:1779-1787`(T22-96)의 잔재 금지 목록에 **`data-started-at` 문자열 자체가 들어 있다.**
- 허브 파서는 구세대 파일 관용을 위해 그 속성을 지금도 선택 그룹으로 파싱한다: `hub/bin/hub_parse.py:63` `(?:\s+data-started-at="(?P<started_at>[^"]*)")?`, `StepView.started_at: str | None`(`hub_parse.py:32`).

**이번 요구는 제거된 것과 다른 정보다.** 제거된 것은 "활성 단계 하나의 경과 + 마지막 기록 + 다음 단계"를 보여주는 별도 카드였고, 이번 요구는 **모든 단계의 구간 소요와 총 경과**다. 결정 번복의 선례는 이 저장소의 명시적 관행이다 — `commands/dashboard.md:735-743`(DU5)이 *"전제가 바뀌면 결정을 공개적으로 뒤집는다(SP19·RV1 선례)"* 를 기록한다. 이번 번복의 트리거는 사용자의 명시 요청이다. T22-96 개정이 그 공개 기록이 된다(결정 DT12).

## 3. 전제와 확인 요청 (구현 착수 전 사용자 확인 항목)

추측하지 않고 기본값을 정해 두었다. 어긋나면 해당 결정만 갈아끼우면 된다.

| # | 전제 (기본값) | 대안 |
|---|--------------|------|
| Q1 | 단계가 **재활성화**되면(검수 FAIL 후 구현 재개 등) 소요 시간은 **마지막 회차만** 잰다 — `data-started-at` 을 재각인한다(결정 DT8). 회차 이력은 작업 추적 로그의 `R{N}` 배지가 이미 담당한다 | 누적 합산(제3 속성 + 산술 필요 — §10 기각 대안 3) |
| Q2 | 표시 형식: 완료 `12분`·`1시간 4분`, 진행 `12분 경과`, 총계 진행 중 `총 경과 …` / 전 단계 완료 시 `총 소요 …`(동결), 1분 미만 `1분 미만` | 초 단위 표시(틱 30초와 안 맞아 기각) |
| Q3 | `step` 의 `#dz-updated` 시각원을 0단계 `date` 관측값으로 교체한다(부수 변경 1줄). 지금은 시각원이 미규정이라, 관측된 epoch 와 추정된 갱신 시각이 화면에서 어긋날 수 있다 | 현행 유지(어긋남 감수) |
| Q4 | `impl` 세부 작업 패널에는 스탬프를 넣지 않는다(결정 DT11) | 포함(§10 기각 대안 4) |
| Q5 | 허브에는 **파서 호환만** 반영하고 허브 카드에 소요 시간을 표시하지 않는다(결정 DT13). 허브 상세 패널(iframe)은 대시보드 문서 자체를 렌더하므로 자동으로 보인다 | 허브 카드 표시(후속 PRP) |

## 4. 필독 지도 (Mandatory Reading)

| 우선 | 파일:라인 | 왜 |
|------|-----------|-----|
| P0 | `commands/dashboard.md:112-165` | 동적 셀렉터 6종 계약 + 불변식 1~4. 스탬프 속성이 이 계약의 확장이다 |
| P0 | `commands/dashboard.md:639-697` | `step` 절차 전문 — 0단계 grep("결과는 항상 4줄", :648)·상태 치환(:657)·진행률 전이 산술(:679)·갱신 시각(:689) |
| P0 | `commands/dashboard.md:535-608` | `init` 4단계 python 히어닥 — `values`(:543)·`steps_block_lines`(:553)·앵커 검증 루프(:583)·"값의 차이로 흡수" 철학(:604) |
| P0 | `commands/dashboard_template.html:295-478` | 폴링 IIFE — `syncVisualization` 이 `#dz-steps/#dz-matrix` 를 **outerHTML 로 통째 치환**(:355-359, :404). 라이브 표시가 매 폴마다 지워지는 이유이자 MutationObserver 가 필요한 이유 |
| P0 | `hub/bin/hub_parse.py:61-78` | `_STEP_LINE_PATTERN`·`_CELL_LINE_PATTERN` — 속성 **순서**까지 정규식이 고정한다. 새 속성은 반드시 이 순서 규칙 안에서 삽입 |
| P0 | `tests/run.sh:1779-1787` | T22-96 잔재 금지 목록 — `data-started-at` 을 빼지 않으면 구현이 테스트에 차단된다 |
| P1 | `commands/dashboard_template.html:296-311` + `commands/dashboard.md:305-311` | grep 유일성 불변식 — 스크립트가 `id="…"` 형태 문자열·`class="done"` 류 감사 패턴과 겹치는 문자열을 만들면 안 된다 |
| P1 | `commands/dashboard_template.html:480-489` | "폴링 IIFE 는 file://·PiP 미지원에서 조기 return 하므로 별도 IIFE" 배치 원칙 — 새 렌더러 IIFE 가 따라야 할 선례 |
| P1 | `tests/hub/fixtures/impl_dashboard.html:195-232` | 제거된 구세대 `formatDuration`·경과 렌더러 원문 — 음수/미래 스탬프 가드("숫자 없는 라벨만 남지 않도록")의 선례 |
| P2 | `docs/prps/dashboard-group-matrix.md:203` | 매트릭스 `init` 초기 상태: **각 그룹의 첫 단계 칸이 active** — init 스탬프 주입 대상 |
| P2 | `.claude/dashboard.html:277` | 현행 세대 `<li>` 실물 — `<li id="dz-step-1" class="done"><span class="num">1</span>설계<span class="chip">완료</span><span class="step-detail">…</span></li>` |

## 5. 영향 범위

| 파일 | 작업 | 이유 |
|------|------|------|
| `commands/dashboard.md` | 수정 | 데이터 모델(스탬프 속성·`#dz-elapsed`)·불변식 11 신설·`init` 4단계 python 개정·`step` 0/1/3단계 개정·매트릭스 예시 갱신 |
| `commands/dashboard_template.html` | 수정 | 헤더 갱신 맵 주석 · CSS 4규칙 · `#dz-elapsed` 마크업 1줄 · 소요 시간 렌더러 IIFE 신설(맨 뒤) |
| `hub/bin/hub_parse.py` | 수정 | `_STEP_LINE_PATTERN`·`_CELL_LINE_PATTERN` 에 `data-done-at` 선택 그룹, `StepView.done_at` 필드 — 안 하면 done 단계 줄이 파싱에서 탈락해 허브 카드의 활성 단계 줄이 조용히 빈다 |
| `tests/hub/test_hub_parse.py` | 수정 | P10(스탬프 선형)·P11(스탬프 매트릭스) 신설, 기존 P1/P9 에 `done_at` 기본값 단언 추가 |
| `tests/hub/fixtures/timed_linear_dashboard.html` | 신설 | epoch 스탬프 세대 선형 픽스처 |
| `tests/hub/fixtures/timed_matrix_dashboard.html` | 신설 | epoch 스탬프 세대 매트릭스 픽스처 |
| `tests/run.sh` | 수정 | T22-96 잔재 목록에서 `data-started-at` 제외(사유 주석), T22-159~163 신설, T22 헤더 범위(`tests/run.sh:1053` "T22-1~T22-158") 갱신 |
| `README.md` | 수정 | `README.md:139` 의 두 줄 수(1315·766)를 실측으로 갱신 |

**변경하지 않는 것**: `hub/bin/hub_template.html`(허브 카드는 `tier1.steps` 의 state/name/detail 만 쓴다 — `hub/bin/hub_template.html:1233-1242`), `hub_collect.py`(파일→파서 통로 무변경, `hub_collect.py:305`; `dataclasses.asdict` 직렬화가 새 필드를 자동 통과 — `hub_collect.py:435`), `install.sh`(파일 수 불변, `COMMANDS_FILE_COUNT=10` — `install.sh:14`), CLAUDE.md 트리거 표(`commands/dashboard.md:44-56` — 호출 시점·형식 무변경).

## 6. 파일 구조와 모듈 경계

기존 레이어 경계를 그대로 따른다. 새 파일·새 레이어 없음.

```
쓰기(오케스트레이터, LLM 절차)   commands/dashboard.md
  init 4단계 python  ──┐            시각 스탬프를 "언제" 기록하는가(데이터만. epoch 초)
  step 0·1단계        ──┘
        │  .claude/dashboard.html 의 DOM 속성 (파일이 곧 상태 — 별도 상태 파일 금지 원칙 유지)
        ▼
읽기 1(브라우저)      commands/dashboard_template.html 렌더러 IIFE
                        스탬프 → 소요 시간 "표시"로 변환(순수 계산 + 라이브 DOM 전용 스팬)
읽기 2(허브)          hub/bin/hub_parse.py (순수 파서) → Tier1Snapshot → (표시는 이번 범위 밖)
```

- **데이터와 표시의 경계가 이번 설계의 축이다**: 파일에는 스탬프(데이터)만 있고, 소요 시간 문자열(표시)은 어느 절차도 파일에 쓰지 않는다. 티킹은 표시의 속성이므로 표시 계층(스크립트)의 전담이다(결정 DT4).
- 순수 로직(`formatDuration`·`durationText`·파서 정규식)은 입력→출력 함수로 유지 — `hub_parse.py` 는 창립부터 순수 레이어다(`hub_parse.py:1-6`).

## 7. 데이터 모델

### 7-1. DOM 계약 확장 — 시각 스탬프 속성 2종

| 속성 | 붙는 곳 | 값 | 쓰는 주체 | 읽는 주체 |
|------|--------|-----|----------|----------|
| `data-started-at` | `#dz-step-{n}` `<li>` · `#dz-cell-{g}-{p}` `<td>` · 시각화 루트(`#dz-steps` `<ol>` \| `#dz-matrix` `<table>`) | **epoch 초** 정수 문자열 (`^\d{1,12}$`) | `init`(생성 시 active 요소 + 루트), `step`(active 전이 시) | 템플릿 렌더러 IIFE · `hub_parse` |
| `data-done-at` | `#dz-step-{n}` · `#dz-cell-{g}-{p}` | 같음 | `step`(done 전이 시) | 같음 |

- 루트의 `data-started-at` 이 **총 경과의 기준점**(= 발행 시각)이다. 루트에 두는 이유: `step` 이 그 줄을 절대 건드리지 않고(치환 대상은 `<li>`/`<td>` 줄뿐 — `commands/dashboard.md:657`), 폴링이 루트를 outerHTML 로 통째 동기화하므로(`dashboard_template.html:355-359`) 열린 탭 위에서 `init` 재발행이 일어나도 라이브 값이 낡지 않는다. 반면 `#dz-log` 의 속성은 `syncLog` 가 innerHTML 만 대입해(`dashboard_template.html:361-364`) 라이브 DOM 에 동기화되지 않는다 — 그래서 그쪽에 두지 않는다(결정 DT6).
- 구세대 값(`YYYY-MM-DD HH:MM`)과 형식이 다르지만 충돌하지 않는다: 그 값을 해석하는 소비자가 없다 — 허브는 `[^"]*` 로 통과만 시키고(`hub_parse.py:63`) 표시에 쓰지 않으며(`hub_template.html:1233-1242`), 구세대 스크립트는 구세대 파일 안에만 있다(스크립트와 데이터는 같은 파일이라 세대가 항상 일치한다).

### 7-2. 정규 속성 순서 (허브 정규식과의 계약)

```
선형   <li id="dz-step-{n}" class="{state}" [data-started-at="…"] [data-done-at="…"]>…
매트릭스 <td class="cell" id="dz-cell-{g}-{p}" data-state="{state}" [data-started-at="…"] [data-done-at="…"]>…
루트   <ol class="steps" id="dz-steps" data-started-at="…">  |  <table class="matrix" id="dz-matrix" data-started-at="…">
```

허브 정규식이 속성 순서를 고정 매칭하므로(`hub_parse.py:61-67, 75-78`) 이 순서는 임의가 아니라 계약이다. `step` 이 줄을 재작성할 때 항상 이 순서로 쓴다.

### 7-3. `step` 상태 전이 시 스탬프 규칙 (선형·매트릭스 공통)

| 새 상태 | `data-started-at` | `data-done-at` | 의미 |
|--------|------------------|----------------|------|
| `active` | **이번 epoch 로 설정** (이미 있으면 갱신 — 재활성화는 새 회차 재측정, Q1) | **제거** | 회차 시작 |
| `done` | **유지** (없으면 추가하지 않는다 — wait→done 직행 단계는 구간이 없다. 예: 승인 단계, `commands/dashboard.md:48` 트리거) | **이번 epoch 로 설정** | 구간 확정 |
| `wait` | **유지** | **제거** (done 이탈 시 낡은 확정값이 남으면 안 된다) | 회수(regression) |

이 표가 폐쇄 어휘다 — 세 상태 밖의 동작을 만들지 않는다. epoch 는 아래 §9 태스크 2의 `date` 출력에서만 온다(기억·추정 금지).

### 7-4. 표시 계층 데이터 (파일에 존재하지 않음)

| 요소 | 위치 | 채우는 주체 |
|------|------|-------------|
| `.dz-dur` `<span>` | 라이브 DOM 전용 — 선형은 `.chip` 바로 뒤(같은 줄), 매트릭스는 `<td>` 마지막(상태어 아래 블록 줄) | 렌더러 IIFE 만. **파일에는 절대 나타나지 않는다** |
| `#dz-elapsed` `<div class="elapsed">` | 템플릿 상주(진행 카드, `bar-outer` 와 `.pct` 사이) — 파일에서는 항상 빈 요소 | 내용은 렌더러 IIFE 만. `init`/`step`/`log`/폴링 모두 불가침 |

### 7-5. 불변식 11 (신설 — 기존 1~6, 8, 9, 10 에 이어)

> 11. **시각 스탬프는 데이터, 소요 시간은 표시다.** ① 스탬프 속성은 §7-2 정규 순서로만 쓴다. ② 값은 epoch 초 정수뿐이다. ③ 스크립트(렌더러·폴링·PiP)는 스탬프를 **읽기만** 한다 — `setAttribute` 로 쓰지 않는다(불변식 8·9와 같은 소유권 원칙). ④ 생성물 파일에는 소요 시간 표시 문자열(`.dz-dur` 스팬, `#dz-elapsed` 내용)이 존재하지 않는다 — 오케스트레이터는 표시를 쓰지 않고, 스크립트는 파일을 쓰지 않는다.

### 7-6. 허브 파서 모델 확장

```python
@dataclass(frozen=True)
class StepView:                      # hub_parse.py:24-33
    index: int
    name: str
    state: StepState
    detail: str
    started_at: str | None           # 기존 — 구세대·신세대 값 모두 문자열 그대로
    done_at: str | None              # 신설 — 유일 생성처는 _parse_steps (hub_parse.py:86)
```

`dataclasses.asdict` 경유 JSON(`hub_collect.py:435`)에 `done_at` 이 자동 포함되고, 허브 템플릿은 모르는 필드를 무시한다.

## 8. 인터페이스

**사용자 호출 규약 무변경** — `/dashboard init|step|impl|log|serve|on|off` 의 인자·의미 동일(`commands/dashboard.md:19-31`). 절차 내부 계약만 아래처럼 확장된다.

### 8-1. `step` 0단계 Bash (시각원 추가)

```bash
grep -n -e 'id="dz-step-{n}"' -e 'id="dz-progress-bar"' -e 'id="dz-progress-pct"' -e 'id="dz-log"' .claude/dashboard.html \
  && date '+%s %Y-%m-%d %H:%M'
```

- grep 결과는 종전대로 **항상 4줄**이고(문구 보존 — `tests/run.sh:1889-1904` T22-107 이 이 리터럴을 검사한다), 뒤에 date 출력 1줄이 붙는다. **첫 토큰이 epoch 초**(스탬프 값), **나머지가 사람 시각**(`#dz-updated` 용, Q3).
- Bash 호출 수 불변(1회, 복합 명령). `date` 는 POSIX 유틸리티 — 새 의존성 없음.

### 8-2. 템플릿 렌더러 IIFE 공개 계약

전역 노출 없음(훅 불필요 — `window.dzRequestRefresh` 같은 외부 소비자가 없다). 내부 순수 함수의 시그니처(문서 주석에 명기):

```js
function parseEpochSeconds(value /*: string|null */) /*: number|null */
function formatDuration(totalSeconds /*: number */) /*: string */   // ''|'1분 미만'|'N분'|'H시간[ M분]'
function unitState(unit /*: Element(li|td) */) /*: 'done'|'active'|'wait'|'na'|'' */
function durationText(unit /*: Element */, nowSeconds /*: number */) /*: string */
```

### 8-3. 허브 파서 정규식 (전문)

```python
_STEP_LINE_PATTERN = re.compile(
    r'<li id="dz-step-(?P<index>\d+)" class="(?P<state>done|active|wait)"'
    r'(?:\s+data-started-at="(?P<started_at>[^"]*)")?'
    r'(?:\s+data-done-at="(?P<done_at>[^"]*)")?>'
    r'<span class="num">\d+</span>(?P<name>.*?)<span class="chip">.*?</span>'
    r'(?:<span class="step-detail">(?P<detail>.*?)</span>)?</li>'
)
_CELL_LINE_PATTERN = re.compile(
    r'<td class="cell" id="dz-cell-(?P<group>\d+)-(?P<col>\d+)"'
    r' data-state="(?P<state>done|active|wait|na)"'
    r'(?:\s+data-started-at="[^"]*")?(?:\s+data-done-at="[^"]*")?'
    r'>(?P<text>.*?)</td>'
)
```

셀 쪽은 캡처하지 않는다 — 소비자가 없다(`_count_matrix_done` 은 state 만 센다, `hub_parse.py:97-102`). `StepView` 는 `started_at` 선례와의 대칭으로 캡처한다.

## 9. 상세 설계 — 구현 태스크

### 태스크 1: `commands/dashboard.md` — `init` 4단계 python 개정

- **ACTION**: 히어닥 python 에 시각 스탬프 **후처리 주입**을 추가한다. `values`(모델이 채우는 부분)는 무수정 — 모델은 타임스탬프를 쓰지 않는다(결정 DT10).
- **IMPLEMENT** (`commands/dashboard.md:539-583` 블록 개정 — 변경분만):

```python
import html, pathlib, time            # time 추가

# … values, escaped 는 오늘과 동일 …

# 시각 스탬프 주입(불변식 11) — 모델이 아니라 이 스크립트가 시계를 읽는다.
# 네 앵커는 steps_block_lines 규격에서만 나타난다: 루트 2종(선형/매트릭스)과
# 생성 시 active 인 요소 2종(선형 1번 li · 매트릭스 각 그룹 첫 칸 — group-matrix PRP :203).
now_epoch = str(int(time.time()))
steps_block = "\n".join(values["steps_block_lines"])
for stamp_anchor in (' id="dz-steps">', ' id="dz-matrix">',
                     ' class="active">', ' data-state="active">'):
    steps_block = steps_block.replace(
        stamp_anchor, '%s data-started-at="%s">' % (stamp_anchor[:-1], now_epoch))

replacements = [
    # … 나머지 5개 항목 동일. 아래 한 항목만 교체값이 바뀐다:
    ('    <ol class="steps" id="dz-steps">\n    </ol>',
     steps_block),
    # …
]
```

- **MIRROR**: "선형/매트릭스 분기가 값의 차이로 흡수된다" 철학(`commands/dashboard.md:604`) — 주입 앵커 4개가 두 모드를 무분기로 덮는다.
- **GOTCHA**: ① 앵커 검증 루프는 **원본 텍스트**에서 앵커를 세므로 주입 결과와 충돌하지 않는다(주입은 교체값 쪽에만 일어난다). ② 단계명은 html 이스케이프 대상이라 `="active">` 같은 문자열이 이름에서 태그로 성립할 수 없다. ③ `steps_block_lines` 예시 주석에 "시각 스탬프는 후처리가 주입한다 — 값에 쓰지 않는다" 한 줄을 추가한다.
- **VALIDATE**: 신설 T22-161(§11).

### 태스크 2: `commands/dashboard.md` — `step` 절차 개정

- **ACTION**: 0단계 명령에 `&& date '+%s %Y-%m-%d %H:%M'` 추가(§8-1), 1단계에 §7-3 전이 표 삽입, 3단계 문구를 "0단계 date 출력의 사람 시각 부분으로 치환한다"로 교체(Q3).
- **IMPLEMENT**: 1단계(상태 치환, `commands/dashboard.md:657-677`)에 덧붙일 규칙 — *"같은 Edit 1회 안에서 §7-3 표대로 스탬프 속성을 재작성한다. 속성 순서는 §7-2 정규 순서. epoch 는 0단계 date 출력의 첫 토큰만 쓴다. 스탬프가 없던 구세대 대시보드에서도 같은 규칙으로 삽입한다(`.step-detail` 소급 삽입과 같은 방식 — `commands/dashboard.md:672-673` 선례)."*
- **GOTCHA**: ① Edit·Bash 횟수 불변(Bash 1 + Edit 3) — 절차 제목의 비용 표기를 바꾸지 않는다. ② "결과는 항상 4줄" 리터럴을 지우지 않는다(T22-107). ③ 매트릭스 `<td>` 도 동일 표 적용 — "상세 인자 무시" 규칙(:674-677)과 무관하게 스탬프는 상태 갱신의 일부다. ④ 진행률 전이 산술(:679-687)은 무변경.
- **VALIDATE**: T22-160, T22-107 기존 통과 유지.

### 태스크 3: `commands/dashboard.md` — 데이터 모델·불변식·매트릭스 예시

- **ACTION**: §7-1~7-5 를 문서에 반영한다. 동적 셀렉터 표(:123-134)의 `#dz-step-{n}`·`#dz-cell-{g}-{p}` 행에 스탬프 속성 추가, 「시각 스탬프」 하위 절 신설(§7-1~7-3 내용), 정적 요소 표(:256-274)에 `#dz-elapsed` 행 추가("폴링도 동기화하지 않는다 — 내용은 렌더러 IIFE 만 바꾼다"), 불변식 11 신설(:288 불변식 10 뒤), 매트릭스 마크업 예시(:390-427)의 active 칸 2곳에 `data-started-at` 예시값 반영.
- **GOTCHA**: 근거 링크는 이 PRP(`docs/prps/dashboard-step-durations.md`)로 건다 — `dashboard-rationale.md` 에 절을 늘리지 않는다(상호작용 잠금이 자기 PRP 를 직접 링크한 선례 — `commands/dashboard.md:334`).

### 태스크 4: `commands/dashboard_template.html` — 마크업·CSS

- **ACTION**: `#dz-elapsed` 1줄 + CSS 4규칙 + 헤더 갱신 맵 주석.
- **IMPLEMENT**:
  - 마크업 — `bar-outer`(현 :274)와 `.pct`(현 :275) **사이**에: `    <div class="elapsed" id="dz-elapsed"></div>`. float 요소는 소스에서 앞서야 `.pct` 와 같은 시각 줄(오른쪽 끝)에 얹힌다.
  - CSS — `.pct`(현 :122) 뒤: `.elapsed{float:right;font-size:12px;font-weight:700;color:var(--muted);margin-top:7px}` + `.elapsed:empty{display:none}`. `.step-detail:empty`(현 :135) 뒤: `.dz-dur{flex:none;font-size:11px;font-weight:700;color:var(--muted)}` + `li.active .dz-dur{color:var(--accent-ink)}`. 매트릭스 na 규칙(현 :146) 뒤: `.matrix td.cell .dz-dur{display:block;font-size:10px;font-weight:400;margin-top:2px;color:inherit;opacity:.85}`.
  - 헤더 주석(:7-27) — `#dz-step-{n}`·`#dz-cell-{g}-{p}` 행에 스탬프 속성, 정적 목록에 `#dz-elapsed`("렌더러 IIFE 전용 — init/step/log/폴링 불가침")와 `.dz-dur`("라이브 DOM 전용 — 파일에 없음") 추가.
- **GOTCHA**: ① `init` python 앵커 3개(`#dz-project-name`·`h1`·`.pct`·ol 블록·`#dz-log`·`#dz-updated` 줄)는 한 글자도 건드리지 않는다 — 낡은 설치본 `dashboard.md` 와 새 템플릿이 만나면 `ANCHOR-FAIL` 로 `init` 이 전면 중단된다(`commands/dashboard.md:583-608`). 새 줄 **삽입**은 안전하고 기존 줄 **수정**은 위험하다. ② 새 CSS·마크업 줄에 `dz-step-`·`dz-cell-`·`dz-impl-` 시퀀스를 넣지 않는다 — 감사 계수 grep(`commands/dashboard.md:691-696`)의 오염원이 된다.
- **VALIDATE**: T22-162, 기존 T22-2(셀렉터 6종)·T22-105(`#dz-log` 태그 순서) 통과 유지.

### 태스크 5: `commands/dashboard_template.html` — 렌더러 IIFE (전문)

- **ACTION**: 툴팁 IIFE 뒤(스크립트 블록 맨 뒤)에 아래 IIFE 를 추가한다. 위치가 계약이다 — 기존 순서 검사(T22-153 등)는 상대 순서를 보므로 맨 뒤 추가가 가장 안전하다.
- **IMPLEMENT** (참조 구현 — 이대로 옮겨도 된다):

```js
(function(){
  // 단계별 소요 시간·총 경과 렌더러(docs/prps/dashboard-step-durations.md 결정 DT4·DT5·DT9).
  // 파일의 data-started-at/data-done-at(epoch 초)만 읽어 라이브 DOM 의 .dz-dur 스팬과
  // #dz-elapsed 를 채운다 — 파일에는 표시 문자열이 존재하지 않는다(불변식 11).
  // 폴링 IIFE 와 별도인 이유: 그 IIFE 는 file:// 와 PiP 미지원 환경에서 조기 return 하는데
  // (테마 IIFE 머리 주석과 같은 이유) 소요 시간은 갱신 모드와 무관하게 보여야 한다.
  var DURATION_TICK_MS = 30000;        // 표시 단위가 '분'이라 30초면 충분 — 구세대 NOW_TICK_MS 와 같은 값
  var SECONDS_PER_MINUTE = 60, MINUTES_PER_HOUR = 60;
  var EPOCH_SECONDS_PATTERN = /^\d{1,12}$/;   // epoch 초만 유효. 구세대(YYYY-MM-DD HH:MM) 값 방어
  var wrap = document.querySelector('.wrap'); // PiP 이동 후에도 유효한 노드 참조 캐시(폴링 IIFE 와 같은 방식)

  /** data-*-at 속성값을 epoch 초 정수로. 형식이 어긋나면 null. */
  function parseEpochSeconds(value){
    return (value && EPOCH_SECONDS_PATTERN.test(value)) ? parseInt(value, 10) : null;
  }
  /** 초 → '1분 미만'|'N분'|'H시간[ M분]'. 음수·비유한은 빈 문자열(시계 되감김 방어 — 구세대 가드 승계). */
  function formatDuration(totalSeconds){
    if(!isFinite(totalSeconds) || totalSeconds < 0) return '';
    if(totalSeconds < SECONDS_PER_MINUTE) return '1분 미만';
    var minutes = Math.floor(totalSeconds / SECONDS_PER_MINUTE);
    if(minutes < MINUTES_PER_HOUR) return minutes + '분';
    var restMinutes = minutes % MINUTES_PER_HOUR;
    return Math.floor(minutes / MINUTES_PER_HOUR) + '시간' + (restMinutes ? ' ' + restMinutes + '분' : '');
  }
  /** 선형 li 와 매트릭스 td 의 상태 어휘를 하나로 좁힌다. */
  function unitState(unit){
    if(unit.tagName === 'TD') return unit.getAttribute('data-state') || '';
    if(unit.classList.contains('done')) return 'done';
    return unit.classList.contains('active') ? 'active' : 'wait';
  }
  /** 단위 하나의 표시 문자열. done=확정 구간, active=지금까지 + ' 경과', 그 외는 빈 문자열. */
  function durationText(unit, nowSeconds){
    var startedAt = parseEpochSeconds(unit.getAttribute('data-started-at'));
    if(startedAt === null) return '';
    var state = unitState(unit);
    if(state === 'done'){
      var doneAt = parseEpochSeconds(unit.getAttribute('data-done-at'));
      return doneAt === null ? '' : formatDuration(doneAt - startedAt);
    }
    if(state !== 'active') return '';
    var runningText = formatDuration(nowSeconds - startedAt);
    return runningText ? runningText + ' 경과' : '';
  }
  /** .dz-dur 스팬을 만들거나 갱신하거나 제거한다. 동일값이면 쓰지 않는다(MutationObserver 수렴 가드). */
  function setDurationSpan(unit, text){
    var span = unit.querySelector('.dz-dur');
    if(!text){ if(span) span.remove(); return; }
    if(!span){
      span = document.createElement('span');
      span.className = 'dz-dur';
      var chip = unit.querySelector('.chip');   // 선형 li: 칩 뒤 같은 줄. 매트릭스 td: 상태어 아래 블록 줄
      if(chip){ chip.insertAdjacentElement('afterend', span); } else { unit.appendChild(span); }
    }
    if(span.textContent !== text) span.textContent = text;
  }
  /** 총 경과/총 소요 한 줄. 루트 스탬프가 없으면(구세대 파일) 조용히 비운다. */
  function renderTotal(root, units, nowSeconds){
    var out = document.getElementById('dz-elapsed');
    if(!out) return;
    var startedAt = root ? parseEpochSeconds(root.getAttribute('data-started-at')) : null;
    var text = '';
    if(startedAt !== null){
      var allDone = units.length > 0, lastDoneAt = null;
      for(var i = 0; i < units.length; i++){
        var state = unitState(units[i]);
        if(state === 'na') continue;
        if(state !== 'done'){ allDone = false; break; }
        var doneAt = parseEpochSeconds(units[i].getAttribute('data-done-at'));
        if(doneAt !== null && (lastDoneAt === null || doneAt > lastDoneAt)) lastDoneAt = doneAt;
      }
      // 확정 조각이 비면(음수 등) 라벨만 남기지 않고 진행형으로 낙착한다(구세대 elapsedLabel 가드 승계).
      var frozenText = (allDone && lastDoneAt !== null) ? formatDuration(lastDoneAt - startedAt) : '';
      text = frozenText ? '총 소요 ' + frozenText
                        : '총 경과 ' + formatDuration(Math.max(0, nowSeconds - startedAt));
    }
    if(out.textContent !== text) out.textContent = text;
  }
  function render(){
    var nowSeconds = Math.floor(Date.now() / 1000);
    var root = wrap.querySelector('#dz-steps,#dz-matrix');
    var units = root ? root.querySelectorAll('li, td.cell') : [];
    Array.prototype.forEach.call(units, function(unit){
      setDurationSpan(unit, durationText(unit, nowSeconds));
    });
    renderTotal(root, units, nowSeconds);
  }
  render();
  setInterval(render, DURATION_TICK_MS);
  // 폴링의 outerHTML 치환이 라이브 .dz-dur 를 지운다(파일에는 스팬이 없다) — 치환 직후 즉시
  // 복원한다. setDurationSpan/renderTotal 의 동일값 가드 덕에 이 옵저버는 자기 쓰기에 수렴한다:
  // 값이 바뀔 때만 1회 재발화하고 두 번째 render 는 무변경이라 멈춘다.
  new MutationObserver(render).observe(wrap, {childList: true, subtree: true});
})();
```

- **MIRROR**: 별도 IIFE 배치·조기 return 회피(테마 IIFE 머리 주석, `dashboard_template.html:480-489`), `wrap` 참조 캐시(폴링 IIFE `:312`), MutationObserver 사용(툴팁 IIFE `:756-760`), 음수 가드(`impl_dashboard.html:195-215`).
- **GOTCHA**: ① 스크립트에 `id="…"`·`class="done"`·`dz-cell-`·`dz-step-` 문자열을 만들지 않는다(grep 유일성 불변식 + 감사 계수 — `#dz-steps`(셀렉터 표기)·`classList.contains('done')`·`getElementById('dz-elapsed')` 는 전부 허용 형태다). ② `document.querySelector('.wrap')` 를 render 안에서 매번 부르면 PiP 이동 후 null 이 된다 — 반드시 IIFE 초기화 시 1회 캐시. ③ `root`/step 노드는 폴마다 교체되므로 render 가 매번 재조회한다(노드 캐시 금지 — `.wrap` 과 반대). ④ 임베드(허브 상세 패널 iframe)·PiP·file:// 모두에서 그대로 동작해야 하며 분기를 만들지 않는다.
- **VALIDATE**: T22-162·T22-163 + §11 수동 실측.

### 태스크 6: `hub/bin/hub_parse.py`

- **ACTION**: §8-3 정규식 2개 교체 + `StepView.done_at: str | None` 추가(`started_at` 바로 뒤, 기본값 없음 — 생성처가 `hub_parse.py:86` 한 곳뿐임을 확인했다) + `_parse_steps` 에 `done_at=match["done_at"]` + 모듈 docstring 에 한 줄("신세대 시각 스탬프는 epoch 초 — 값 해석은 이 모듈의 일이 아니다").
- **VALIDATE**: `python3 -m unittest discover -s tests/hub -t .` — 기존 P1~P9 무수정 통과(선택 그룹이므로), 신설 P10·P11 통과.

### 태스크 7: 픽스처 2종 신설 + `tests/hub/test_hub_parse.py`

- **ACTION**: `timed_linear_dashboard.html`(done 2 · active 1 · wait 1, done 에 `data-started-at`+`data-done-at`, active 에 `data-started-at` 만, wait 하나는 무스탬프, 루트 `<ol>` 에 스탬프)·`timed_matrix_dashboard.html`(스탬프 있는 done/active 칸 + na 칸). 파서 게이트 3요소(title·progress·updated — `hub_parse.py:114-118`)를 갖춘 축약 픽스처로 만들고, 머리 주석에 세대 표기(기존 픽스처 관례).
- **IMPLEMENT** (테스트 케이스):
  - P10: `steps[0].started_at == "1756270000"` 류 epoch 문자열 캡처, done 단계의 `done_at` 값, active 단계 `done_at is None`, 무스탬프 단계 둘 다 None.
  - P11: 스탬프 붙은 매트릭스에서 `matrix_done` 카운트가 정확(정규식 관용 검증).
  - 기존 P1 클래스에 `assertIsNone(first.done_at)` 1줄 추가(구세대 파일에서 새 필드 기본값).
- **MIRROR**: AAA 구조·서술형 테스트명(기존 `test_four_steps_with_state_detail_started_at`, `test_hub_parse.py:35`).

### 태스크 8: `tests/run.sh` + `README.md`

- **ACTION**:
  - **T22-96 개정**(:1782): 목록에서 `'data-started-at'` 제거. 주석에 — *"data-started-at 은 docs/prps/dashboard-step-durations.md 가 다른 의미(단계 시각 스탬프, epoch 초)로 재도입했다. 나머지 9개 잔재가 「지금」 카드 부활을 계속 차단한다."*
  - **신설**: T22-159 union 파일에 `data-done-at` 존재(문서 전이 표 + 템플릿 정규식/IIFE — `grep -c` ≥ 2). T22-160 `dashboard.md` step 절에 `date '+%s %Y-%m-%d %H:%M'` 존재. T22-161 init python 에 `import html, pathlib, time` 과 `data-started-at="%s">' % (stamp_anchor[:-1], now_epoch)` 존재. T22-162 템플릿에 `DURATION_TICK_MS`·`.dz-dur{`·`id="dz-elapsed"` 존재. T22-163(역방향, 불변식 11-③) union 파일에 `setAttribute('data-started-at'`·`setAttribute('data-done-at'` **부재**.
  - T22 헤더 서술(:1049, :1053)의 범위를 새 최댓값으로 갱신. `README.md:139` 의 1315·766 두 줄 수를 구현 후 실측값으로 갱신.
- **GOTCHA**: T25-75(:3623-3633)는 허브 소스의 `data-owner-token` 만 금지한다 — `data-done-at` 은 저촉되지 않는다(`data-started-at` 이 이미 `hub_parse.py:63` 에 있는 것과 같은 상태).

## 10. 설계 결정과 근거

| ID | 결정 | 근거 (요지) |
|----|------|------------|
| DT1 | 저장은 생성물 DOM 의 `data-*` 속성 | "별도 상태 파일(JSON)은 두지 않는다 — DOM 자체가 상태"가 창립 결정이다(`commands/dashboard.md:9`). 속성은 같은 줄에 얹혀 불변식 2·5(1줄 1요소)를 깨지 않는다 |
| DT2 | `data-started-at` 이름 재사용 + `data-done-at` 신설 | 허브 정규식이 그 이름을 그 위치(class 뒤)에 이미 관용한다(`hub_parse.py:63`). 새 이름 2개를 쓰면 선택 그룹이 3개가 되고 구세대 관용도 별도로 유지해야 한다 |
| DT3 | 값은 epoch 초 | 산술(빼기)이 목적인 값이다. 구세대 사람 형식은 분 단위 절사(구간당 ±1분 오차 — 구현 중앙값 5.8분에서 최악 30%대 오차, `commands/dashboard.md:712` DU1 실측)에 브라우저 파싱이 비표준이다. 값 해석 소비자가 없음은 전수 확인했다(§7-1) |
| DT4 | 표시는 템플릿 스크립트 전담, 절차는 데이터만 기록 | active 경과와 총 경과는 **틱**해야 한다 — 오케스트레이터의 기록 시점은 이산적이고 구현 단계는 최장 54분 무갱신이다(DU1 실측). LLM 이 표시 문자열까지 조립하면 Edit 페이로드와 오류면만 는다 |
| DT5 | `.dz-dur` 는 라이브 DOM 전용(파일에 없음), `#dz-elapsed` 는 템플릿 상주 | 파일에 표시 스팬을 넣으면 허브 `_STEP_LINE_PATTERN` 의 꼬리(`chip → step-detail? → </li>`)가 깨져 정규식 개정 범위가 배가된다. 스팬이 파일에 없으면 grep 앵커·감사 계수·Edit old_string 모두 무영향 |
| DT6 | 총 경과 기준점은 시각화 루트의 `data-started-at` | §7-1 표 아래 서술 — `step` 불가침 + outerHTML 동기화 편승. 1번 단계의 스탬프에서 파생하면 재활성화(DT8)가 기준점을 파괴한다 |
| DT7 | 시각원은 관측만: `step` 은 0단계 `date`, `init` 은 python `time.time()` | 절차의 "현재 시각"은 지금껏 출처 미규정이었다(`commands/dashboard.md:547,689`). 표시가 산술이 되는 순간 추정 시각은 화면 모순(갱신 시각 vs 경과)으로 드러난다. Bash 횟수는 늘지 않는다(복합 명령) |
| DT8 | 재활성화는 재각인(마지막 회차 재측정), done 이탈은 `data-done-at` 제거 | 누적은 제3 속성 + LLM 덧셈을 요구한다 — 진행률도 덧셈 대신 전이(±1)로 설계된 저장소다(`commands/dashboard.md:679-687`). 회차 이력은 로그의 `R{N}` 배지가 담당(:205) |
| DT9 | 별도 IIFE + 30초 틱 + `wrap` MutationObserver(동일값 쓰기 가드) | 폴링 IIFE 는 file:// 에서 조기 return(`dashboard_template.html:337-343`) — 그 안에 넣으면 file:// 에서 죽는다(테마 IIFE 와 같은 배치 이유, :481-484). 폴링의 outerHTML 치환(:355-359)이 스팬을 지우므로 옵저버 없이는 최대 30초 공백이 보인다. 두 IIFE 간 결합 금지 원칙(:520-522) 때문에 `apply()` 에서 직접 부르지 않는다 |
| DT10 | init 스탬프는 python 후처리 주입 — 모델은 쓰지 않는다 | 모델이 epoch 를 "아는" 척 쓰는 순간 조용히 틀린 데이터가 된다(감지 불가). 주입 앵커 4개는 `steps_block_lines` 규격 문자열에서만 성립함을 확인했다(§9 태스크 1 GOTCHA) |
| DT11 | `impl` 패널 제외 | 표준 경로에서 impl 은 호출 자체가 금지된 fan-out 전용 예외다(D≥2, 6일 실측 1건 — `commands/dashboard.md:60-64,705-719`). 렌더러가 루트(`#dz-steps/#dz-matrix`) 스코프로만 조회하므로 구조적으로도 배제된다 |
| DT12 | T22-96 잔재 목록에서 `data-started-at` 제외 | §2. 나머지 잔재 9종은 유지 — 차단 대상은 "지금 카드"이지 속성이 아니다 |
| DT13 | 허브는 파서 호환만(`done_at` 캡처), 카드 표시는 범위 밖 | 요구가 "대시보드 화면"이다. 허브 상세 패널은 대시보드 문서를 iframe 으로 그대로 렌더하므로 추가 코드 없이 보인다. 카드 표시는 후속 판단(파생 "지금" 값을 스냅샷에 넣지 않는 허브 원칙 — `hub_template.html:89` — 과의 조율이 필요하다) |

**검토했으나 기각한 대안**
1. **오케스트레이터가 소요 시간 문자열을 파일에 기록** — 틱 불가(DT4), 갱신 없는 54분 동안 화면이 거짓말을 한다.
2. **작업 추적 로그(`#dz-log`)의 시각에서 파생** — 로그 시각은 `HH:MM` 표시 전용(날짜 없음, `commands/dashboard.md:849`)이고, 로그 `<li>` 는 여러 줄이라 허브가 파싱하지 않기로 창립부터 결정된 영역이다(`hub_parse.py:5-6`).
3. **누적 소요(제3 속성)** — DT8 근거로 기각.
4. **`#dz-progress-pct` 에 총 경과 병기** — `step` 2단계가 그 텍스트를 `M/N · P%` 로 재파싱하고(`commands/dashboard.md:679`) 허브 `_PROGRESS_PATTERN`(`hub_parse.py:55-58`)도 같은 형식을 게이트로 쓴다 — 둘 다 깨진다.
5. **초 단위 실시간 틱(1초 interval)** — 분 단위 표시에 과잉. 구세대도 30초였다(`impl_dashboard.html:166`).

## 11. 테스트 계획

이 저장소의 검증 체계 그대로: 템플릿·문서는 `tests/run.sh` 의 정합성 grep(런타임 Edit 결과는 자동 검증 대상이 아님 — `tests/run.sh:1048-1049`), 순수 로직은 `tests/hub` 의 stdlib unittest(T24 가 실행 — `tests/run.sh:2568-2581`), 화면 동작은 실측 체크리스트(주석에 실측 기록을 남기는 관례).

**단위 테스트 (순수 로직 — `tests/hub/test_hub_parse.py`)**

| 케이스 | 입력 | 기대 |
|--------|------|------|
| P10-1 | 스탬프 선형 픽스처 | done 단계: `started_at`·`done_at` 둘 다 epoch 문자열 캡처 |
| P10-2 | 〃 | active 단계: `started_at` 있음, `done_at is None` |
| P10-3 | 〃 | 무스탬프 wait 단계: 둘 다 None |
| P10-4 | 〃 | 4단계 전부 파싱(스탬프가 이름·상태·상세 캡처를 훼손하지 않음) |
| P11-1 | 스탬프 매트릭스 픽스처 | `matrix_done` 이 스탬프 유무와 무관하게 정확 |
| P1 회귀 | 구세대 픽스처(무수정) | 기존 단언 전부 유지 + `done_at is None` |

**정합성 테스트 (`tests/run.sh` T22)** — §9 태스크 8의 신설 5건(T22-159~163)과 개정 1건(T22-96). 기존 T22-2·T22-105·T22-107 이 무수정 통과해야 한다(앵커·리터럴 보존의 검증).

**수동 실측 체크리스트** (구현 후 커밋 전, 실측 기록은 코드 주석 관례대로)
- [ ] `init` 직후: 1번 단계에 `1분 미만 경과`, `총 경과 1분 미만`, 파일에 `data-started-at` 3곳(루트+1번 li — 선형) 각인 확인
- [ ] `step 1 done` + `step 2 active` 후: 1번에 확정 구간, 2번에 틱 시작, 총 경과 계속 진행
- [ ] 마지막 단계 done 후: `총 소요 …` 로 동결(30초 틱에도 불변)
- [ ] 폴링 치환 직후(`window.dzRequestRefresh()` 강제) `.dz-dur` 가 즉시 복원(MutationObserver 경로), 콘솔 무한 루프 없음
- [ ] file:// 티어에서 표시·틱 동작(폴링 없이)
- [ ] 허브 상세 패널(iframe)·PiP 창에서 표시 유지, PiP 복귀 후 정상
- [ ] 스탬프 없는 구세대 파일(git 의 옛 생성물)에서: 아무 표시 없음·에러 없음
- [ ] 매트릭스 세션(`init "…" "A:설계,구현|B:검수"`)에서 칸 아래 줄 표시·na 칸 무표시
- [ ] 감사 grep 2종(`commands/dashboard.md:691-696`)의 계수가 스탬프 추가 전후 동일

**검증 명령**

```bash
bash tests/run.sh                                   # T22(정합) · T24(허브 단위) · T25(허브 템플릿) 전부
python3 -m unittest discover -s tests/hub -t .      # 허브 단위만 빠르게
```

## 12. 리스크와 대안

| 리스크 | 발생 가능성 | 영향 | 완화 |
|--------|------------|------|------|
| **허브 구버전 스큐**: 새 대시보드(`data-done-at`) + 갱신 안 된 허브 | 중 | 낮음 — done 단계 줄만 `_STEP_LINE_PATTERN` 매칭 탈락. 허브 카드는 **active 단계만** 그리므로(`hub_template.html:1233-1242`) 화면 손실이 사실상 없다. 진행률은 별도 패턴이라 무관 | 릴리스 노트에 `hub/install.sh` 재실행 안내. 파서 테스트가 신·구 픽스처 동시 통과를 고정 |
| **LLM 이 전이 표를 어겨 속성 순서·값이 어긋남** | 중 | 중 — 허브 파싱 탈락(조용한 강등) | 폐쇄 전이 표(§7-3) + 정규 순서(§7-2) + epoch 는 관측값만(DT7). 어긋나도 대시보드 자체 표시는 되고(렌더러는 순서 무관 `getAttribute`), 감사 grep 은 무영향 |
| **MutationObserver 자기 발화 루프** | 낮음 | 중(CPU) | 모든 쓰기에 동일값 비교 가드 — 수렴 논증을 코드 주석에 각인(§9 태스크 5). 실측 체크리스트에 루프 부재 확인 항목 |
| **시계 이상**(되감김·원격 뷰어 스큐·미래 스탬프) | 낮음 | 낮음 — 음수 구간 | `formatDuration` 음수→빈 문자열, 라벨 조각 미출력(구세대 가드 승계, `impl_dashboard.html:210-214`) |
| **낡은 설치본 조합**(새 dashboard.md + 옛 템플릿) | 낮음 | 낮음 | init 앵커 불변(태스크 4 GOTCHA ①)이라 `ANCHOR-FAIL` 전면 중단은 없다. 옛 템플릿이면 스탬프는 기록되고 표시만 없다 — 재설치 시 소급 표시된다 |
| **T22-96 미개정 상태로 구현 선행** | — | 확실한 테스트 실패 | 태스크 8을 태스크 4·5 와 같은 커밋에 묶는다(테스트와 대상 변경의 동커밋 관례 — `.claude/dashboard.html` 로그의 선례) |

## 13. 만들지 않는 것 (NOT Building)

- 허브 카드/목록의 소요 시간 표시(DT13 — 후속 판단)
- `impl` 세부 작업 패널의 스탬프(DT11)
- 회차별 누적·이력 소요(DT8 — 로그 `R{N}` 이 담당)
- `log`·`impl` 절차의 시각원 교체(`step`/`init` 만 — Q3 범위)
- 단계별 예상 시간·지연 경고 등 파생 신호

## 14. 완료 기준

- [ ] 태스크 1~8 완료, `bash tests/run.sh` 전부 통과(신설 T22 5건·개정 1건·P10/P11 포함)
- [ ] 수동 실측 체크리스트 9항목 통과, 실측 기록을 코드 주석에 남김
- [ ] 사용자 호출 규약·Bash/Edit 호출 횟수·기존 앵커 리터럴 무변경 확인
- [ ] `README.md:139` 줄 수 실측 갱신

---

## 사용자 승인이 필요한 핵심 결정 (3줄)

1. **재활성화된 단계는 마지막 회차만 잰다**(누적 아님 — Q1/DT8). 회차 이력은 로그 배지가 담당.
2. **`data-started-at` 재도입에 따라 회귀 테스트 T22-96 의 잔재 금지 목록을 개정한다**(DT12 — 1b199cb 제거 결정의 부분 번복, 사용자 요청이 트리거).
3. **`step` 의 갱신 시각도 `date` 관측값으로 교체한다**(Q3/DT7 — 경과 표시와의 화면 모순 방지, 부수 변경 1줄).
