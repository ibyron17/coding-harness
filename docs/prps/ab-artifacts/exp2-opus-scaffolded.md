> ⚠️ **실험 원본 — 승인된 설계가 아니다.**
> 이 문서는 모델·프롬프트 A/B 실험의 **실험 2 · OS(opus + 스캐폴딩) · 35/50 · 4위** 산출물이다.
> 여기 설계된 기능은 구현되지 않았고, 앞으로 구현할 계획도 없다.
> **저장소 선례로 인용하지 않는다.** 실험 설계·채점·결론은
> [`../model-scaffolding-ab-experiments.md`](../model-scaffolding-ab-experiments.md) 를 본다.
> 본문은 이 배너 블록 아래부터 서브에이전트 원본 그대로다(내용 무수정).

---

# 단계별 소요 시간 — `active`/`done` 전이 시각 각인과 파생 표시 (PRP)

## 0. 착수 전 반드시 알아야 할 두 가지 사전 발견

이 두 가지를 모르고 착수하면 **테스트가 즉시 깨지거나, 허브 티어 1이 조용히 강등된다.** 구현자는 이 절을 먼저 읽는다.

### 발견 1 — 유사 기능이 이미 있었고, 사용자 판단으로 제거됐으며, 역방향 검사가 부활을 막고 있다

커밋 `1b199cb`(`feat: /dashboard UI 정리 — 세션 탭 제거·항상 새로 발행·부제 제거·지금 카드 제거`)가 「지금」 카드를 완전히 제거했다. 제거 사유는 성능·복잡도가 아니라 **정보 가치 판정**이다:

> `docs/prps/dashboard-ui-cleanup.md:718-725`
> "위 2번의 3행 재설계를 실제로 구현해 스크린샷으로 확인한 결과, 사용자가 "경과/마지막 기록/다음 정보 자체가 쓸모없다"고 판단해 **「지금」 카드를 완전히 제거**하기로 최종 결정했다. … `#dz-now-card` 와 그 전용 코드(마크업·CSS·`renderNowCard()` 등 렌더 함수 4종·`step` 절차의 `data-started-at` 각인 규칙)를 전부 제거했고, 불변식 7 … 도 함께 삭제했다"

이후 PRP가 이를 **명시적 비목표**로 승격했다:

> `docs/prps/impl-panel-dispatch-unit-and-session-meta-chips.md:120` (결정 DU6)
> "**경과 시간·타이머·「지금」 카드를 재도입하지 않는다.** … 이미 만들었다가 사용자 판단으로 제거된 자산이다 … T22-61·T22-96 이 그 부활을 막는 역방향 검사로 남아 있다."

그리고 실제 가드가 살아 있다:

- `tests/run.sh:1779-1787` (**T22-96**) — `commands/dashboard.md` + `commands/dashboard_template.html` 합본에서 `dz-now-card`·`dz-now-elapsed`·`dz-now-since`·`dz-now-next`·`renderNowCard`·**`data-started-at`**·`now-row`·`now-label`·`now-value`·`now-title` 10개 문자열 중 **하나라도 나오면 실패**한다.
- `tests/run.sh:1514-1523` (**T22-61**) — `dz-current`·`"현재 위치"` 금지, `step` 호출 규약 원형 문자열 유지 요구.

**그런데 이번 요청은 제거된 기능과 같지 않다.** 제거된 것은 *현재* 단계의 살아 있는 카운터(`42분 경과`) + `마지막 기록 N분 전` + `다음 →` 였다. 그 구조는 **끝난 단계의 소요 시간을 원리적으로 표현할 수 없었다** — 종료 시각을 아예 기록하지 않았기 때문이다(`hub/bin/hub_parse.py:63` 의 유일한 스탬프 슬롯이 `data-started-at` 하나뿐인 것이 그 증거다). 이번 요청은 **회고적 기록**(어느 단계가 몇 분 걸렸는가)이고, 그것을 위해 `done` 전이 시각이라는 **새 정보**를 도입한다.

→ 따라서 이 PRP는 DU6·T22-96 을 **부분적으로 번복하는 제안**이며, 그 번복은 §2 의 사용자 승인 사항이다. 승인 없이는 착수하지 않는다.

### 발견 2 — 허브 파서의 단계 정규식은 속성 1개 추가로 깨진다 (실측)

`hub/bin/hub_parse.py:61-67`:

```python
_STEP_LINE_PATTERN = re.compile(
    r'<li id="dz-step-(?P<index>\d+)" class="(?P<state>done|active|wait)"'
    r'(?:\s+data-started-at="(?P<started_at>[^"]*)")?>'
    r'<span class="num">\d+</span>(?P<name>.*?)<span class="chip">.*?</span>'
    r'(?:<span class="step-detail">(?P<detail>.*?)</span>)?</li>'
)
```

옵션 그룹이 **`data-started-at` 하나만, 그 위치에만** 허용되고 곧바로 `>` 를 요구한다. 실제 모듈을 로드해 측정한 결과:

| `<li>` 형태 | 결과 |
|---|---|
| 속성 없음 | MATCH (`started_at=None`) |
| `data-started-at` 만 | MATCH (`started_at='2026-08-10 18:12'`) |
| `data-started-at` + `data-ended-at` | **NO-MATCH** — 그 단계가 `Tier1Snapshot.steps` 에서 사라진다 |
| `data-dur-min` 만 (다른 이름) | **NO-MATCH** — 동일 |
| `.step-detail` **뒤에** 자식 `<span class="dur">17분</span>` | MATCH 하지만 `detail == 'PRP 작성</span><span class="dur">17분'` (원시 마크업 오염) |
| `.chip` **앞에** 같은 자식 | MATCH 하지만 `name == '설계<span class="dur">17분</span>'` (동일 오염) |

오염된 값의 귀결: `hub/bin/hub_template.html:1240-1241` 이 `escapeHtml(activeStep.name)` · `escapeHtml(activeStep.detail)` 로 그리므로 XSS 는 아니지만 **허브 카드에 원시 태그 문자열이 그대로 보인다.**

**세 가지 강제 결론:**

1. **`<li id="dz-step-*">` 안에 자식 요소를 새로 추가하지 않는다.** 소요 시간은 **속성으로 저장**하고 표시는 스크립트가 런타임에 만든다(§9).
2. **속성을 어떤 이름으로 추가하든 `hub_parse.py` 수정은 불가피하다.** 따라서 "테스트를 안 건드리려고 이름을 우회한다"는 선택지는 실익이 없다 — 이것이 §2 결정 A의 근거다.
3. 정규식을 **속성 나열 방식으로 고치지 않고 일반화**한다(§11 결정 D3). 지금이 이 패턴이 깨진 두 번째 사례다.

---

## 1. 요구사항 요약

`/dashboard` 는 진행 단계의 상태(`done`/`active`/`wait`)만 남기고 시간을 남기지 않는다(`commands/dashboard.md:130` 의 `#dz-step-{n}` 행이 치환 대상으로 `class`·`.chip`·`.step-detail` 셋만 규정한다). 그래서 세션이 끝난 뒤 "설계가 17분, 구현이 54분 걸렸다"를 알 방법이 없다. 이 PRP는 `step` 절차가 **상태를 바꾸는 그 Edit 안에서** 전이 시각 두 개(`active` 진입 시각, `done` 진입 시각)를 `<li>` 속성으로 각인하게 하고, 브라우저 스크립트가 그 두 스탬프에서 **단계별 소요 시간과 총 경과를 파생**해 화면에 그리게 한다. **새 Bash 호출·새 Edit·새 인자는 0개다.**

---

## 2. 사용자 승인이 필요한 결정 (3건)

### 결정 A — DU6·T22-96 의 부분 번복 (필수 승인)

`data-started-at` 문자열을 되살리고 `data-ended-at` 을 신설하려면 **T22-96 의 relic 목록에서 `data-started-at` 한 항목만 제거**해야 한다(`tests/run.sh:1782`). 나머지 9개(`dz-now-card`·`dz-now-elapsed`·`dz-now-since`·`dz-now-next`·`renderNowCard`·`now-row`·`now-label`·`now-value`·`now-title`)는 **그대로 유지한다** — 「지금」 카드 자체는 부활시키지 않는다.

부분 번복이 정당한 이유:

- 가드의 목적은 **「지금」 카드**(단계 이름 중복 + 살아 있는 카운터 3행)의 부활 방지다. 이번 기능은 카드를 만들지 않고, 단계 목록 행 안에 값 하나를 얹는다.
- 제거 사유는 "**현재** 진행 중인 것이 뭔지는 `.step-detail` 로 충분"이었다(`dashboard-ui-cleanup.md:721-722`). 그 문장은 "**끝난** 단계가 몇 분 걸렸는지"에 대해 아무것도 판정하지 않았다 — 당시 구조가 그 값을 가질 수 없었으므로 판정 대상이 아니었다.
- 이 저장소는 전제가 바뀌면 결정을 공개적으로 뒤집는 관례가 있다(`commands/dashboard.md:772-777`: `DU5`가 `SP4`를, `SP19`가 `SP4`를, `hub-session-revival`의 `RV1`이 `done` 터미널 가정을 번복한 선례를 명시).
- 이름을 우회하면(`data-active-at` 등) 가드는 통과하지만 **의미상으로는 같은 것을 몰래 들여오는 것**이고, `hub_parse.py:63` 의 기존 슬롯과 `tests/hub/fixtures/linear_hub_dashboard.html:128-130` 의 기존 스탬프 자산을 버리게 된다. 정직한 재사용이 낫다.

**승인 질문**: `data-started-at` 을 되살려 재사용하는 것에 동의하는가? (거부 시 대안은 §13 대안 1 — 새 이름 도입, T22-96 무수정.)

### 결정 B — 총 경과를 살아 있는 값으로 둘 것인가

- **B-1 (권장)**: 총 경과 = `가장 이른 data-started-at` → (진행 중 단계가 있으면 `지금`, 없으면 `가장 늦은 data-ended-at`). 진행 중에는 30초 틱으로 증가한다.
- **B-2**: 총 경과 = **완료된 단계 소요 시간의 합**. 정적이며 전이 시점에만 변한다. 틱이 필요 없어 "살아 있는 카운터를 두지 않는다"는 제거 결정의 정신에 더 가깝다.

권장은 B-1(사용자 표현 "총 경과"의 자연스러운 의미가 벽시계 경과다)이나, B-2 로 바꾸는 비용은 틱 등록 1줄 삭제 + 합산식 1줄 교체다. **승인 질문**: B-1 / B-2?

### 결정 C — 재진입(회차 반복) 시 무엇을 보여줄 것인가

`CLAUDE.md` 트리거 표(`commands/dashboard.md:60`)는 검수 FAIL 시 `step 4 wait` 를 지시한다. 즉 단계는 `active → wait → active → done` 으로 **재진입한다.**

- **C-1 (권장, YAGNI)**: `data-started-at` 은 `active` 진입마다 덮어쓴다. 표시되는 소요 시간은 **마지막 `active → done` 구간**이다. 요청 문구("`active` 로 바뀐 시점과 `done` 으로 바뀐 시점을 기록")를 문자 그대로 만족한다.
- **C-2**: 구간을 누적한다(`검수` 3회차의 총합). 정보량은 늘지만 **오케스트레이터가 벽시계 뺄셈·누적 산술**을 매 전이마다 수행해야 한다 — 시·일 경계를 넘는 뺄셈은 LLM 절차에서 비결정성의 원천이다. C-1 은 "현재 시각을 속성에 적는다"뿐이어서 산술이 0이다.

**승인 질문**: C-1 로 가고 그 의미("마지막 구간")를 문서에 명시하면 되는가?

---

## 3. 스코프와 비목표

### 스코프 안
- 선형 모드(`#dz-step-{n}`) 단계별 소요 시간 표시.
- 총 경과 1줄.
- `init` 이 1번 단계에 `active` 진입 스탬프를 각인(= 세션 시작 시각의 출처).
- `hub_parse.py` 의 단계 정규식 일반화 + `StepView.ended_at` 신설.

### 비목표 (명시적으로 만들지 않는 것)

| 제외 항목 | 사유 |
|---|---|
| 매트릭스 모드(`#dz-cell-{g}-{p}`)의 스탬프 | `dashboard-current-next-card.md:516` 이 이미 같은 판단으로 기각("`step <g>.<p>` 절차가 커지고, 소비자가 없다(YAGNI)"). 매트릭스는 `.step-detail` 도 지원하지 않는다(`commands/dashboard.md:676-678`) |
| `#dz-impl-{k}`(구현 세부 작업)의 스탬프 | `_IMPL_LINE_PATTERN`(`hub_parse.py:69-73`)에는 속성 슬롯이 아예 없다. 그리고 이 패널은 fan-out 전용 예외 경로다(`commands/dashboard.md:52-58`) |
| 「지금」 카드·`dz-now-*`·`renderNowCard` 부활 | 결정 A. 9개 relic 문자열 가드 유지 |
| `마지막 기록 N분 전`·`다음 →` 부활 | 같은 판정으로 제거된 값이다. 이번 요청 범위 밖 |
| 허브 카드에 소요 시간 표시 | 허브는 활성 단계의 이름+상세만 그린다(`hub_template.html:1233-1241`). 파서는 값을 싣지만 렌더는 하지 않는다 — 별건 |
| `#dz-log` 에 세션 시작 속성 추가 | §11 결정 D2. 파생으로 충분하고, `tests/run.sh:1617·1866·2269` 가 `#dz-log` 여는 태그 문자열을 정확 일치로 3곳에서 고정하고 있어 대가가 크다 |
| 초 단위 해상도 | `#dz-updated`·기존 스탬프가 모두 분 해상도다. 실측 근거: `implementer` 소요 중앙값 5.8분·p90 29.1분·최장 54.1분(`commands/dashboard.md:715-720`) — 분 해상도로 충분하다 |
| 새 파일 추가 | `tests/run.sh:1128`(`COMMANDS_FILE_COUNT`)·`2618`(`HUB_FILE_COUNT`)가 파일 수를 고정한다. 이 설계는 새 파일을 만들지 않으므로 두 상수 무수정 |

---

## 4. 영향 범위 — 수정 파일 6개, 신규 0개

| 파일 | 무엇을 왜 |
|---|---|
| `commands/dashboard.md` | ① 동적 셀렉터 표 `#dz-step-{n}` **행 1개 수정**(치환 대상에 두 속성 추가, **행 수 6 유지** — `tests/run.sh:1738` T22-92 가 "6 셀렉터" 제목을 고정한다) ② 정적 요소 표에 2행 추가(`.step-duration`·`#dz-total-elapsed`) ③ **불변식 11 신설** ④ 폴링 동기화 계약에 1행 ⑤ `init` 4단계 `steps_block_lines` 의 k=1 `<li>` 예시에 스탬프 추가(`:555`) ⑥ `step` 1단계에 각인 규칙 표 1개 추가(`:657`) |
| `commands/dashboard_template.html` | CSS 2줄(`.step-duration`·`#dz-total-elapsed`), body 1줄(`#dz-total-elapsed`), script 상수 2개 + 함수 3개 + 호출 3곳 |
| `hub/bin/hub_parse.py` | `_STEP_LINE_PATTERN` 일반화 + `_STAMP_ATTRIBUTE_PATTERN` 신설 + `StepView.ended_at`. **발견 2로 인해 불가피** |
| `tests/run.sh` | T22-96 relic 목록에서 `data-started-at` 1개 제거(사유 주석 필수) + T22-159~166 신설 |
| `tests/hub/test_hub_parse.py` | P10~P13 신설 (속성 2개·순서 무관·구세대 호환·오염 방지) |
| `README.md` | `:139` 의 줄 수(`1315`·`766`) 실측값 갱신, `:159-169` `/dashboard` 설명에 소요 시간 1문장 |

### 미영향 (전수 확인)

| 대상 | 확인 결과 |
|---|---|
| `hub/bin/hub_model.py` | `asdict(snapshot)`(`:82`,`:90`)가 `StepView` 필드를 자동 직렬화하므로 **코드 변경 0**. `ended_at` 이 `#dzh-data` 에 자동 탑재된다 |
| `snapshot_content_key`(`hub_model.py:80-84`) | 스탬프는 **전이 시점에만** 변하는 원시 값이므로 키가 매 수집마다 흔들리지 않는다. **파생 경과값을 파이썬 쪽에 넣지 않는 이유가 바로 이것이다**(§11 D4) |
| `hub/bin/hub_template.html` | `renderTier1ActiveStep`(`:1233-1241`)은 `state`·`name`·`detail` 만 읽는다. 새 필드는 무해하게 무시된다 |
| 불변식 1~6·8·9·10 | 두 속성은 **기존 `<li>` 같은 줄 안의 속성**이다. 줄 수·줄 경계 불변 → 불변식 2·5 무손상. `.step-detail`·`.detail` 미접촉 → 3·10 무손상. `data-server-port`·`data-owner-token` 미접촉 → 8·9 무손상 |
| 불변식 7 | **결번을 유지한다**(`commands/dashboard.md:282` "**7은 결번**이다"). 새 번호는 **11** |
| `step` 0단계 grep "결과는 항상 4줄" | 패턴·요소 수 불변. 두 속성은 이미 매칭되는 그 줄 안에 있다 |
| `step` 2단계 전이(±1) 산술 | 각인 판정이 **같은 grep 결과 줄의 이전 상태**를 쓴다. 새 Bash 0회 |
| 감사용 `grep -c 'dz-step-.*class="done"'` | 속성은 `class="done"` 부분일치를 방해하지 않는다 |
| `install.sh` 의 `COMMANDS_FILE_COUNT` / `hub/install.sh` 의 `HUB_FILE_COUNT` | 신규 파일 0개 → 무수정 |
| `tests/run.sh:2269` T22-139 앵커 6종 | `#dz-log` 여는 태그·`#dz-progress-pct` 등 미접촉. `#dz-total-elapsed` 는 **새 줄**이라 기존 앵커의 등장 횟수를 바꾸지 않는다 |
| `tests/hub/fixtures/*.html` 5종 | **전부 무수정.** 정규식 일반화는 구세대 3형태(속성 없음/`data-started-at` 1개/`#dz-subtitle` 없음)를 모두 계속 매칭한다 — P10~P13 이 이를 증명한다 |

---

## 5. 파일 구조와 모듈 경계

레이어 경계는 기존 구조를 그대로 따른다. 이 기능은 **새 레이어를 만들지 않는다.**

```
commands/dashboard.md              ← 절차 레이어(오케스트레이터 전용). 스탬프를 "쓰는" 유일한 주체
commands/dashboard_template.html   ← 표현 레이어. 스탬프를 "읽어 파생 표시"하는 유일한 주체
        ↑ 두 레이어 간 계약 = <li> 의 두 속성 (그 외 통신 경로 없음)

hub/bin/hub_parse.py               ← ★순수 파서. 외부 읽기 소비자. 파일시스템·시각에 닿지 않음
hub/bin/hub_model.py               ← asdict 로 자동 전달 (무수정)
hub/bin/hub_template.html          ← 렌더 (무수정)
```

**경계 규칙 2개 (신설):**

1. **각인은 절차만, 파생은 스크립트만.** 오케스트레이터는 소요 시간을 **계산하지 않는다** — 시각만 적는다. 스크립트는 스탬프를 **쓰지 않는다** — 읽어서 그린다. 이것이 불변식 11이다.
2. **`hub_parse.py` 는 순수를 유지한다.** 경과 시간을 계산하지 않는다(`지금`을 알아야 하므로 시각에 닿게 되고, 그 순간 `:3` 의 "★순수" 계약과 `snapshot_content_key` 안정성이 동시에 깨진다).

---

## 6. 데이터 모델

### 6.1 DOM 계약 — `commands/dashboard.md:130` 행 수정 (표의 행 수는 6 유지)

| 셀렉터 | 치환 대상 | 값 |
|---|---|---|
| `#dz-step-{n}` **(그룹 1개)** | `class` 속성 + **`data-started-at` 속성** + **`data-ended-at` 속성** + 자식 `.chip` 텍스트 + 자식 `.step-detail` 텍스트 | `done`\|`active`\|`wait` / **`YYYY-MM-DD HH:MM`(`active` 진입 시 각인)** / **`YYYY-MM-DD HH:MM`(`done` 진입 시 각인)** / `완료`\|`진행중`\|`대기` / 한 줄 상세 |

두 속성의 값 규격:

```
StepStamp
  형식   : "YYYY-MM-DD HH:MM"   (분 해상도. #dz-updated·구세대 data-started-at 과 동일)
  부재   : 속성 없음 == 빈 문자열 == "모름"  (data-server-port·data-owner-token 과 같은 관례)
  위치   : class="…" 바로 뒤, started → ended 순서 (파서는 순서에 의존하지 않는다 — P11)
```

### 6.2 파생 뷰 모델 (스크립트 전용, 파일에 저장되지 않는다)

```
StepDuration
  startedAt : Date | null    # data-started-at 파싱 결과
  endedAt   : Date | null    # data-ended-at 파싱 결과
  minutes   : number | null  # endedAt ?? (state==="active" ? now : null) - startedAt
                             #   startedAt 없음 → null
                             #   음수(시계 되감김·손상) → null
  label     : string         # minutes===null ? "" : "12분" | "1시간 4분"

TotalElapsed
  from    : Date | null      # 모든 단계의 startedAt 중 가장 이른 것
  to      : Date | null      # active 단계가 있으면 now, 없으면 endedAt 중 가장 늦은 것  (결정 B-1)
  label   : string           # from/to 중 하나라도 null 이면 ""  → :empty 로 줄 전체가 사라진다
```

**`label === ""` 이면 요소 텍스트를 빈 문자열로 둔다.** 라벨만 남는 사고를 CSS `:empty` 가 구조적으로 막는다 — 이전 세대가 `.now-row:has(.now-value:empty){display:none}` 이라는 `:has()` 규칙까지 동원해 막아야 했던 문제(`dashboard-ui-cleanup.md:652`, 수동 시나리오 13)를 **라벨과 값을 한 텍스트 노드에 담는 것만으로** 없앤다.

### 6.3 `hub_parse.StepView` (필드 1개 추가)

```python
@dataclass(frozen=True)
class StepView:
    """선형 진행 표시의 단계 하나(#dz-step-{n})."""
    index: int
    name: str
    state: StepState
    detail: str
    started_at: str | None
    ended_at: str | None = None   # 신설. 기본값 None → 구세대 픽스처·유일 생성자(hub_parse.py:86) 무손상
```

`StepView(` 생성자 호출은 저장소 전체에서 `hub_parse.py:86` **1곳뿐**(전수 grep 확인)이므로 필드 추가가 다른 호출부를 깨지 않는다.

---

## 7. 인터페이스

### 7.1 호출 규약 — **변경 없음 (인자 0개 추가)**

```
/dashboard step <n> <done|active|wait> ["상세"]      # 그대로. T22-61 이 이 원형 문자열을 고정한다
```

각인 시점은 절차가 **이미 아는 값**(이전 상태 = grep 결과 줄, 현재 시각 = 3단계에서 `#dz-updated` 에 쓰는 그 값)만으로 결정된다.

### 7.2 `step` 1단계에 추가할 각인 규칙 표 (`commands/dashboard.md:657` 이하)

**`data-started-at`·`data-ended-at` 각인 규칙 (선형 모드 전용, 인자 없음)**

| 이전 상태 → 새 상태 | 같은 Edit 안에서 하는 일 |
|---|---|
| `active` 아님 → `active` | `class` 뒤에 `data-started-at="{현재 시각}"` 을 넣는다(이미 있으면 **값만 바꾼다**). **`data-ended-at` 이 있으면 그 속성을 제거한다** |
| `done` 아님 → `done` | `data-ended-at="{현재 시각}"` 을 넣는다(이미 있으면 값만 바꾼다). `data-started-at` 은 **건드리지 않는다** |
| `done` → `active`\|`wait` | `data-ended-at` 속성을 **제거한다** |
| 그 외(`wait`→`wait` 등) | 두 속성을 **건드리지 않는다** |

- 현재 시각 형식은 `YYYY-MM-DD HH:MM` — 3단계가 `#dz-updated` 에 쓰는 값과 **같은 시각·같은 형식**을 쓴다(두 값이 어긋나면 감사 불가).
- **`active` 진입 시 `data-ended-at` 을 반드시 제거하는 이유**: 남겨 두면 재진입 후 `ended < started` 가 되어 소요 시간이 음수가 된다. 제거하면 그 상태가 **도달 불가능**해진다(스크립트의 음수 가드는 시계 되감김 전용 2차 방어로만 남는다).
- **줄바꿈을 넣지 않는다**(불변식 2). 속성 추가는 같은 줄 안에서 끝난다.
- 대상 `<li>` 에 속성이 없는 구세대 대시보드면 그냥 새로 넣는다. 같은 Edit 1회 안이라 **비용이 늘지 않는다.**

### 7.3 `init` 4단계 — `steps_block_lines` k=1 예시 (`commands/dashboard.md:555` 교체)

```
"      <li id=\"dz-step-1\" class=\"active\" data-started-at=\"{현재 시각}\"><span class=\"num\">1</span>{단계명1}<span class=\"chip\">진행중</span><span class=\"step-detail\"></span></li>",
```

k≥2 줄은 **무수정**(스탬프 없음 = 아직 시작 안 함). 1번의 이 스탬프가 **총 경과의 시작점**이다(§11 D2).

### 7.4 템플릿 스크립트 공개 함수 (3개)

```js
// 상수 — 「지금」 카드와 함께 제거됐으므로 다시 넣는다(현재 템플릿에 부재: grep 0회)
var MS_PER_MINUTE = 60000, MINUTES_PER_HOUR = 60;
var DURATION_TICK_MS = 30000;   // 진행 중 값의 갱신 주기. 폴링(60초)과 독립이다

function parseStamp(text)                  // "YYYY-MM-DD HH:MM" → Date | null
function formatDuration(from, to)          // (Date, Date) → "12분" | "1시간 4분" | ""(음수·비유한)
function renderStepDurations()             // #dz-steps 를 훑어 .step-duration 주입/갱신 + #dz-total-elapsed 갱신. 반환값 없음, 멱등
```

`parseStamp`·`formatDuration` 은 **제거된 구현이 `tests/hub/fixtures/linear_hub_dashboard.html:210-219` 에 글자 그대로 보존돼 있다** — 새로 쓰지 않고 그대로 복원한다:

```js
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
```

---

## 8. 구현 지도 — `commands/dashboard_template.html`

### 8.1 CSS (2줄 추가)

`.step-detail:empty` 규칙 **뒤**(`:135` 다음), `#dz-impl-card` 규칙 앞:

```css
  .step-duration{font-size:12px;font-weight:700;color:var(--muted);flex:none}
  #dz-total-elapsed{font-size:12px;color:var(--muted);margin-top:6px}
  #dz-total-elapsed:empty{display:none}
```

- `.chip{margin-left:auto}`(`:131`)가 이미 오른쪽으로 밀고 있으므로, `.step-duration` 을 **`.chip` 바로 뒤**에 주입하면 칩 오른쪽에 붙는다: `1  구현  [진행중] 12분`. **기존 `.chip`·`.step-detail` 규칙은 건드리지 않는다**(수술적 변경).
- `body.dz-pip`(PiP 압축 뷰)·`body.dz-embedded`(허브 패널) 규칙은 **추가하지 않는다** — 값이 짧아 좁은 폭에서도 문제되지 않는다. 필요해지면 그때 넣는다(YAGNI).

### 8.2 body (1줄 추가)

`:275` `#dz-progress-pct` 다음, `:276` `<ol id="dz-steps">` 앞:

```html
    <div id="dz-total-elapsed"></div>
```

**비어 있는 상태로 템플릿에 상주한다.** `init` 은 이 요소를 치환하지 않는다 — 앵커 6종(T22-139)에 추가되지 않으므로 `init` 의 `ANCHOR-FAIL` 검증에 영향이 없다.

### 8.3 script (배치가 중요하다)

```
:299~309  상수 구역        →  MS_PER_MINUTE · MINUTES_PER_HOUR · DURATION_TICK_MS 추가
:334 근처                  →  parseStamp / formatDuration / renderStepDurations 정의
                              + renderStepDurations();                      (초기 1회)
                              + setInterval(renderStepDurations, DURATION_TICK_MS);
:336      if(!isServed){ … return; }   ←★ 위 3줄은 반드시 이 분기 "앞"에 둔다
:397~406  function apply(html){ … }    →  마지막 줄에 renderStepDurations(); 1줄 추가
```

**`if(!isServed)` 앞에 두는 것이 이 절의 핵심 제약이다.** 뒤에 두면 `file://` 모드(갱신 경로 A)에서 소요 시간이 영구히 비어 있다. 이것은 추측이 아니라 **이전 세대가 수동 시나리오로 못 박아 둔 회귀 지점**이다:

> `dashboard-ui-cleanup.md:650` — "`file://` 로 직접 열기 | 「지금」 카드가 30초 틱으로 갱신된다(렌더러가 `if(!isServed)` 조기 반환 **앞**에 있는지의 런타임 확인)"

**`apply()` 안에서 다시 불러야 하는 이유**: `syncVisualization`(`:356-358`)이 `live.outerHTML = next.outerHTML` 로 `#dz-steps` 를 통째로 교체하므로 주입된 `.step-duration` 노드가 매 폴링마다 파괴된다. `renderNowCard()` 도 같은 이유로 `apply()` 에서 불렸다 — 동일 패턴을 따른다.

### 8.4 헤더 주석 맵 (`:12` 부근)

`#dz-step-{n}` 줄에 두 속성을, 정적 요소 구역에 `.step-duration`·`#dz-total-elapsed` 를 각각 1줄로 적는다.

---

## 9. 구현 지도 — `hub/bin/hub_parse.py`

```python
_STEP_LINE_PATTERN = re.compile(
    r'<li id="dz-step-(?P<index>\d+)" class="(?P<state>done|active|wait)"'
    # 속성 구역을 이름으로 나열하지 않는다 — data-started-at 하나만 옵션 그룹으로 박아 둔 탓에
    # data-ended-at 을 더하는 순간 줄 전체가 NO-MATCH 가 되어 그 단계가 steps 에서 사라졌다
    # (docs/prps/dashboard-step-duration.md 발견 2, 실측). [^>]* 는 여는 태그를 넘지 않으며,
    # 속성값에는 raw '>' 가 들어올 수 없다(값은 상태 어휘와 분 해상도 타임스탬프뿐이다).
    r'(?P<attributes>[^>]*)>'
    r'<span class="num">\d+</span>(?P<name>.*?)<span class="chip">.*?</span>'
    # .step-detail 이 이 기능 도입 이전 세대의 대시보드에는 존재하지 않는다(검수 m3) — 선택 그룹으로 둔다.
    r'(?:<span class="step-detail">(?P<detail>.*?)</span>)?</li>'
)

_STAMP_ATTRIBUTE_PATTERN = re.compile(r'data-(?P<kind>started|ended)-at="(?P<value>[^"]*)"')


def _read_stamps(attributes: str) -> tuple[str | None, str | None]:
    """여는 태그의 속성 구역에서 (시작 시각, 종료 시각) 을 읽는다. 없으면 None. 순서 무관."""
    found = {match["kind"]: match["value"] for match in _STAMP_ATTRIBUTE_PATTERN.finditer(attributes)}
    return found.get("started"), found.get("ended")
```

`_parse_steps`(`:81-94`)에서 `started_at=match["started_at"]` 을 `_read_stamps(match["attributes"])` 의 두 값으로 교체한다. 함수는 6줄, 순수 유지.

**주의**: `_IMPL_LINE_PATTERN`(`:69-73`)과 `_CELL_LINE_PATTERN`(`:75-78`)은 **건드리지 않는다** — 비목표이고, 지금 깨진 것이 아니다(karpathy #3).

---

## 10. 설계 결정과 근거

**D1 — 표시는 파생, 저장은 원시 스탬프.** 오케스트레이터가 "17분"을 계산해 적는 방안을 기각했다. 벽시계 뺄셈(시·일 경계 포함)은 LLM 절차에서 결정성이 낮고, 이 저장소는 `step` 절차의 산술을 전이 ±1 수준으로 억제해 왔다(`commands/dashboard.md:679-687`). 스탬프만 적으면 절차의 새 산술이 **0** 이다.

**D2 — 세션 시작 시각을 위한 새 저장소를 만들지 않는다.** `#dz-log` 에 `data-session-started-at` 을 얹는 방안(`data-server-port`·`data-owner-token` 선례가 있다)을 기각했다. `init` 이 1번 단계를 `active` 로 만들므로(`:555`) **1번의 `data-started-at` 이 이미 세션 시작 시각**이고, 총 경과는 "모든 스탬프 중 가장 이른 것"으로 파생된다. 부수 이득 2개: (a) `tests/run.sh:1617·1866·2269` 가 정확 일치로 고정한 `#dz-log` 여는 태그를 건드리지 않는다, (b) 저장소가 하나 줄어 동기화 대상도 줄어든다. 대가: 1번 단계를 재진입하면 세션 시작이 최초 값에서 밀린다 — 드물고, 그 경우에도 "알려진 가장 이른 시각"이라는 정직한 의미가 유지된다.

**D3 — 파서 정규식을 속성 나열에서 일반 구역으로 바꾼다.** 이것은 추측성 일반화가 아니다. 같은 패턴이 **이미 두 번 문제를 냈다**: 1차로 `data-started-at` 전용 옵션 그룹이 생겼고(그 자산은 지금 렌더 소비자가 없는 유령 필드다 — `hub_model`·`hub_template`·`hub.py`·`hub_collect` 전수 grep 결과 `started_at` 참조 0건), 2차로 이번 속성 추가가 줄 전체를 NO-MATCH 로 만든다(실측). `[^>]*` 한 그룹이 옵션 그룹 사슬보다 **짧고 단순하다** — 복잡도를 늘리는 일반화가 아니라 줄이는 교체다.

**D4 — 경과 계산을 파이썬(허브) 쪽에 두지 않는다.** `snapshot_content_key`(`hub_model.py:80-84`)는 `collected_at_ms` 만 제외한 `asdict` 전체를 키로 쓴다. "지금 기준 경과"를 필드로 넣으면 **매 수집마다 키가 바뀌어 `hub.html` 을 무한히 다시 쓴다.** 원시 스탬프는 전이 시점에만 변하므로 키가 안정적이고, 단계가 끝나면 키가 **바뀌어야 하므로** 오히려 정확하다.

**D5 — `<li>` 안에 자식 요소를 넣지 않는다.** 발견 2의 실측 결과(자식을 넣으면 `name` 또는 `detail` 이 원시 마크업으로 오염되고, 허브가 그것을 `escapeHtml` 로 그려 태그 문자열이 화면에 보인다). 파일은 속성만, 화면은 스크립트가 만든 노드로 — 이 분리가 **DOM 계약과 표시를 독립시킨다.**

**D6 — 패턴을 도입하지 않는다.** 새 클래스·추상화·상태 파일이 없다. 함수 3개와 속성 2개가 전부다. 「지금」 카드가 렌더 함수 4종 + 카드 마크업 + 전용 CSS 6줄 + 불변식 1개로 불어났다가 제거된 이력이 있으므로, **표면적을 의도적으로 최소화한다.**

**D7 — 불변식 번호 11을 쓴다.** `commands/dashboard.md:282` 가 "**7은 결번**이다"라고 못 박았다. 7을 재사용하면 그 문장과 모순되고, 제거된 불변식 7(「지금」 카드는 파생 뷰다)과 혼동된다. 신설 문안:

> **11. 소요 시간은 파생 뷰다.** `data-started-at`·`data-ended-at` 은 `init`·`step` 만 쓰고 스크립트는 **읽기만** 한다. `.step-duration`·`#dz-total-elapsed` 는 스크립트만 쓰고 `init`·`step`·`log`·`impl` 은 **읽지도 쓰지도 않는다.** 두 방향 중 하나라도 섞이면 파일과 라이브 DOM 이 발산한다.

---

## 11. 테스트 계획

### 11.1 순수 로직 단위 테스트 — `tests/hub/test_hub_parse.py` (P10~P13)

실행: `python3 -m unittest discover -s tests/hub -t <repo root>` (`tests/run.sh:2578` T24 가 쓰는 그 명령).

| ID | 케이스 | 기대 |
|---|---|---|
| **P10** | `<li>` 에 `data-started-at` + `data-ended-at` 둘 다 | 파싱 성공, `started_at`·`ended_at` 각 값, **`name`·`detail` 무오염**(`'설계'`·`'PRP 작성'`) |
| **P11** | 두 속성의 **순서를 뒤집은** `<li>` | P10 과 동일 결과 (일반 구역 파싱의 증명) |
| **P12** | 기존 픽스처 3세대 전부 (`linear`=`started_at` 만 / `matrix` / `new_generation`=속성 없음) | **회귀 0**. `linear` 는 `started_at='2026-08-10 18:12'`·`ended_at is None`, `new_generation` 은 둘 다 `None` |
| **P13** | (역방향) `<li>` 에 자식 `<span class="step-duration">` 이 섞인 오염 입력 | `detail` 에 `</span>` 이 **들어 있으면 실패**하는 assertion. 발견 2의 실측 오염(`'PRP 작성</span><span class="dur">17분'`)을 회귀로 고정한다 |

P13 이 이 설계에서 가장 값어치 있는 테스트다 — "파일에는 속성만"이라는 D5 규칙을 **기계가 강제**한다.

### 11.2 문서·템플릿 정합성 — `tests/run.sh` (T22-159~166, `test_dashboard_template_integrity`)

| ID | 방향 | 검증 |
|---|---|---|
| T22-159 | 정 | `step` 절 범위에 `data-started-at`·`data-ended-at` 각인 규칙 표 존재. **전이 문구 고정** — `이전 상태` / `→ ` / `active` 조건 문장을 `grep -qF` 로 못 박는다(T22-62 가 같은 목적으로 쓴 방식). 각인 시점이 흐려져 매 호출마다 시각이 리셋되는 회귀를 막는다 |
| T22-160 | 정 | 템플릿에 `.step-duration`·`#dz-total-elapsed` CSS 와 `#dz-total-elapsed:empty{display:none}` 존재 (라벨 고아 방지 계약) |
| T22-161 | 정 | 템플릿에 `parseStamp`·`formatDuration`·`renderStepDurations` 정의 + `MS_PER_MINUTE`·`MINUTES_PER_HOUR`·`DURATION_TICK_MS` 상수 존재 (매직 넘버 금지) |
| T22-162 | **정, 최우선** | **`renderStepDurations` 초기 호출과 `setInterval` 이 `if(!isServed){` 줄보다 앞의 줄 번호에 있다.** `grep -n` 결과 비교로 판정 — `file://` 모드 무동작 회귀를 막는 유일한 자동 검사다 |
| T22-163 | 정 | `apply(` 함수 본문 범위에 `renderStepDurations();` 1회 — 폴링 후 재주입 누락(영구 stale) 방지 |
| T22-164 | 정 | `init` 4단계 `steps_block_lines` 의 `dz-step-1` 예시 줄에 `data-started-at` 존재 (총 경과의 시작점 유실 방지) |
| T22-165 | **역** | T22-96 잔여 9개(`dz-now-card`·`dz-now-elapsed`·`dz-now-since`·`dz-now-next`·`renderNowCard`·`now-row`·`now-label`·`now-value`·`now-title`)가 여전히 **부재**. 「지금」 카드를 되살리지 않았음의 증명 |
| T22-166 | **역** | 동적 셀렉터 표 제목이 `동적(치환 대상) — 6 셀렉터` 그대로(기존 T22-92 와 중복 방지: 신설 대신 T22-92 유지로 갈음 가능) + `commands/dashboard.md` 에 `불변식 7` 재도입 문자열 부재(결번 유지) |

**T22-96 수정 시 주석 의무**: relic 목록에서 `data-started-at` 을 제거하는 줄 위에 "제거 사유 + 이 PRP 경로 + 나머지 9개는 유지"를 남긴다. 사유 없는 가드 완화는 다음 세션이 되돌린다.

### 11.3 수동 검증 시나리오 (자동화 불가 구간)

**솔직한 한계 명시**: `tests/` 에는 JS 테스트 하네스가 없다(`tests/run.sh` + `tests/hub/*.py` 뿐). 따라서 `formatDuration` 의 실제 산술과 렌더 결과는 아래 시나리오로만 검증된다. 이는 이 저장소의 기존 관례와 같다(`dashboard-ui-cleanup.md:633-657` 이 같은 구조를 썼다).

| # | 조작 | 기대 |
|---|---|---|
| 1 | `init "T" "설계\|구현\|검수"` | 1번 `<li>` 에만 `data-started-at`. 화면에 소요 시간 없음(0분), **`#dz-total-elapsed` 는 `0분`** |
| 2 | 3분 대기 후 `step 1 done` | 1번 행에 `3분`. `data-ended-at` 각인. 총 경과 `3분` |
| 3 | `step 2 active` → 90분 대기 | 2번 행에 `1시간 30분`이 **30초 틱으로** 증가. 총 경과도 함께 증가 |
| 4 | `step 2 done` → `step 3 active` → `step 3 wait`(FAIL) → `step 3 active`(재시도) | 3번 행의 `data-started-at` 이 **재시도 시각으로 갱신**되고 `data-ended-at` 이 **없다**. 소요 시간이 음수·`NaN` 으로 표시되지 않는다 (결정 C-1 의 관측 확인) |
| 5 | `data-started-at` 을 손으로 `2026-99-99 99:99` 로 파괴 | 그 행의 소요 시간이 **빈 문자열**(`NaN분` 아님). 다른 행은 정상 |
| 6 | 모든 속성을 손으로 제거 | `#dz-total-elapsed` **줄 전체가 사라진다**(`:empty`). 라벨만 남지 않는다 |
| 7 | 그룹 문법 `"A:설계,구현\|B:설계,구현"` (매트릭스) | `#dz-step-*` 이 없으므로 소요 시간·총 경과가 **아무것도 그려지지 않고**, 스크립트가 예외를 던지지 않는다 |
| 8 | **`file://` 로 직접 열기** | 소요 시간이 표시되고 30초 틱으로 갱신된다 (T22-162 의 런타임 확인) |
| 9 | `serve` 후 폴링 1주기(60초) 경과 | `#dz-steps` 교체 후에도 소요 시간이 **되살아난다**(`apply()` 재호출 확인) |
| 10 | PiP 플로팅 창 진입 | 소요 시간이 압축 뷰에서도 보이고 줄바꿈으로 레이아웃이 깨지지 않는다 |
| 11 | 허브 상세 패널(iframe)에서 열기 | 대시보드 쪽 표시 정상. **허브 카드의 활성 단계 이름·상세에 원시 태그 문자열이 없다**(D5 의 최종 확인) |

### 11.4 회귀 게이트

```bash
bash tests/run.sh                                                  # 전체 (T22·T24·T25 포함)
python3 -m unittest discover -s tests/hub -t .                     # 순수 파서 단위
python3 -m mypy hub/bin/hub_parse.py                               # StepView 필드 추가 타입 확인
python3 -m ruff check hub/bin/hub_parse.py
wc -l commands/dashboard.md commands/dashboard_template.html       # README:139 줄 수 갱신용 실측
```

`.mypy_cache`·`.ruff_cache` 가 저장소에 있으나 `pyproject.toml`·`setup.cfg` 는 없다 — 두 도구는 설정 없이 ad-hoc 실행되는 관례다.

---

## 12. 리스크와 대안

### 리스크

| # | 리스크 | 가능성/영향 | 완화 |
|---|---|---|---|
| 1 | **결정 A 가 거부되면 설계 전체가 흔들린다** | — / 상 | 착수 전 승인 필수. 거부 시 대안 1로 전환(설계의 나머지 90%는 그대로 재사용된다) |
| 2 | 허브 티어 1 조용한 강등 — 파서 수정을 빠뜨리고 절차만 배포 | 중 / 상 | P10~P13 이 게이트. **구현 순서에서 파서를 먼저** 고친다(§13) |
| 3 | `apply()` 재호출 누락 → 서버 모드에서 60초 후 소요 시간이 영구 소실 | 중 / 중 | T22-163 + 수동 9 |
| 4 | `if(!isServed)` 뒤에 렌더러를 두어 `file://` 무동작 | 중 / 중 | T22-162(줄 번호 비교) + 수동 8. 이전 세대가 실제로 밟은 지점이다 |
| 5 | 오케스트레이터가 각인을 빠뜨림 | 중 / 하 | 값이 없으면 **표시가 조용히 비는** 열화 설계(예외·`NaN` 없음). 진행률 산술과 독립이라 다른 기능을 망가뜨리지 않는다 |
| 6 | 벽시계 신뢰성 — 스탬프는 오케스트레이터 머신의 로컬 시각이고 시계 조정·시간대 변경에 취약 | 하 / 하 | `formatDuration` 의 `minutes < 0` 가드가 빈 문자열로 흡수. `dashboard-current-next-card.md:828` 이 이미 같은 결론을 기록했다 |
| 7 | 분 해상도라 1분 미만 단계가 `0분` 으로 보인다 | 상 / 하 | **수용.** 실측 소요(중앙값 5.8분)에서 문제되지 않고, 초 해상도는 `#dz-updated` 형식과의 통일을 깬다 |

### 검토했으나 채택하지 않은 대안

**대안 1 — 새 속성 이름(`data-phase-entered-at`·`data-phase-done-at`)을 쓰고 T22-96 을 무수정으로 둔다.**
장점: 테스트 1줄을 안 건드린다. 기각 사유: (a) 발견 2 때문에 `hub_parse.py` 수정은 어차피 불가피하므로 "테스트 무수정"의 실익이 거의 없다, (b) 같은 개념에 이름이 둘 생긴다(구세대 픽스처는 계속 `data-started-at` 을 갖는다 — `impl-panel-...:118` 이 그 슬롯을 살려 둔 이유로 명시한다), (c) **가드의 의도를 이름 변경으로 우회하는 것**이어서, 다음 세션이 이유를 모른 채 "지금 카드가 부활했다"고 오판할 위험이 오히려 커진다. **결정 A 가 거부되면 이 대안으로 전환한다.**

**대안 2 — 구간을 누적한다(결정 C-2).**
장점: 검수 3회차의 총 소요를 볼 수 있다. 기각 사유: 오케스트레이터에게 벽시계 뺄셈+누적을 요구한다. 이 저장소의 절차는 산술을 전이 ±1 로 억제해 왔고(`commands/dashboard.md:679-687`), 시·일 경계 뺄셈은 그보다 훨씬 비결정적이다. 누적을 원한다면 **오케스트레이터 산술 없는 형태**(구간 스탬프를 append-only 리스트 속성에 쌓고 JS 가 합산)가 옳은 구현이지만, 요청 문구가 "시점 두 개"이므로 지금 만들지 않는다(YAGNI).

**대안 3 — 소요 시간을 `.step-detail` 텍스트에 문자열로 합쳐 넣는다.**
장점: 새 속성·새 CSS·새 스크립트가 전부 불필요하고 파서도 무손상. 기각 사유: `.step-detail` 은 **사용자가 준 상세**의 자리다(`step` 4번째 인자). 절차가 그 값을 가공하면 "생략 시 기존 값 유지"(`commands/dashboard.md:661-665`) 규약이 깨지고, 상세와 시간이 서로를 덮어쓴다. 또 값이 살아 있지 않아 진행 중 경과를 볼 수 없다.

**대안 4 — 별도 상태 파일(JSON)에 타임라인을 남긴다.**
기각 사유: `commands/dashboard.md:11` 의 대전제("별도 상태 파일(JSON)은 두지 않는다 — DOM 자체가 상태다")를 정면으로 위반한다. `impl-panel-...` 결정 DU7 도 같은 이유로 두 번째 데이터 출처를 금지한다.

---

## 13. 구현 순서 (제안)

각 단계는 **검증까지 끝난 뒤** 다음으로 넘어간다.

1. **`hub/bin/hub_parse.py` 정규식 일반화 + `StepView.ended_at`** → 검증: P10~P13 신설 후 `python3 -m unittest discover -s tests/hub -t .` 통과, 기존 P1~P9 **무회귀**. *(파서를 먼저 고치는 이유: 리스크 2. 이 단계만으로도 기존 동작은 100% 보존되며, 아직 아무도 새 속성을 쓰지 않는다.)*
2. **`tests/run.sh` T22-96 완화 + T22-159~166 신설** → 검증: 새 테스트가 **의도한 대로 RED** 임을 먼저 확인한다(구현 전이므로 실패해야 정상).
3. **`commands/dashboard_template.html`** CSS 2줄 + body 1줄 + script(상수 3, 함수 3, 호출 3) → 검증: T22-160~163 GREEN, 수동 7·8.
4. **`commands/dashboard.md`** 셀렉터 표 1행 수정 · 정적 요소 2행 · 불변식 11 · 폴링 계약 1행 · `init:555` · `step` 각인 규칙 표 → 검증: T22-159·164~166 GREEN, `bash tests/run.sh` 전체 통과.
5. **실사용 1회전 검증** — 실제 세션에서 `init` → `step 1 done` → `step 2 active` → FAIL 회귀 → `done` 까지 돌려 수동 1~6·9 확인.
6. **`README.md`** 줄 수 실측 갱신 + `/dashboard` 설명 1문장 → 검증: `wc -l` 값과 문서 일치.

---

## 14. 미해결 질문 (승인 시 함께 답해 주면 좋다)

1. **결정 A** — `data-started-at` 재사용(T22-96 부분 완화)에 동의하는가? 아니면 대안 1(새 이름)로 가는가?
2. **결정 B** — 총 경과를 살아 있는 값(B-1)으로 둘 것인가, 완료 단계 합(B-2)으로 둘 것인가?
3. **결정 C** — 재진입 시 "마지막 구간"(C-1)으로 충분한가?
4. 소요 시간을 **허브 카드**에도 노출할 필요가 있는가? (현재 비목표. 파서는 이미 값을 실어 보내므로, 원한다면 `hub_template.html:1233-1241` 에 별건으로 1줄 추가 가능)
5. 총 경과 라벨 문구 — `총 경과 1시간 12분` 형태로 좋은가? (라벨과 값을 한 텍스트 노드에 담는 §6.2 결정 때문에 문구가 렌더 코드에 들어간다)

---

## 승인 요약 (3줄)

1. **이 기능은 제거된 「지금」 카드와 겹친다** — `data-started-at` 을 되살리려면 `tests/run.sh:1782`(T22-96)의 금지 목록에서 그 한 항목을 빼야 한다(나머지 9개는 유지, 카드는 부활 안 함). **승인 필요.**
2. **허브 파서 수정은 선택이 아니라 필수** — `hub_parse.py:61-67` 의 정규식은 속성 1개만 더해도 그 단계를 `Tier1Snapshot.steps` 에서 통째로 탈락시킨다(실측). 그래서 `<li>` 안에 자식 요소는 넣지 않고 **속성만 저장, 표시는 스크립트 파생**으로 간다.
3. **절차 비용은 0 증가** — 새 인자·새 Bash·새 Edit 없이 기존 `step` Edit 1회 안에서 시각을 각인하고, 재진입 시에는 "마지막 `active→done` 구간"만 보여준다(누적은 YAGNI로 기각).
