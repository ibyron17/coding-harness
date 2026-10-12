# PRP: 허브 UI/기능 결함 4건 — 카드 트리 기본화 · 세션 행 선택 표시 · 칩 툴팁 정보량 · 끝난 대시보드 숨김

- **작성**: 2026-09-11 (design-architect, opus) · **2회차 2026-09-11 (design-architect, fable — 이슈 2·3 재설계. 1회차의 이슈 2·3 이 사용자 검토에서 반려돼 model-routing 기준 4 로 승격)**
- **판정 상태**: 이슈 1(TR1~TR8) **승인** · 이슈 4(FT1~FT7) **승인** — 두 절은 1회차 원문 그대로다. 이슈 3(§4 → WT1~WT8) **승인**(툴팁 제거 + 서버 필드 4개 제거). **이슈 2(§3 → SM1~SM7) 는 미채택 — 사용자가 현재 상태 유지를 선택했다**(2026-09-11, 2회차 목업 검토: "승인 요청 건 1번은 그냥 현재 상태 유지하는걸로 해. 제안한 것들이 모두 마음에 들지 않아"). §3 은 기록으로만 남고 **구현 범위에서 빠진다** — 네 안(A 윤곽·B 레일·C 헤더 밑줄·D 연결선 경로) 전부 미채택이고, `.card.card-open`(284행)·`.session-row.card-open`(424행)·`applyOpenCardMarking` 은 **한 바이트도 바뀌지 않는다**. **선택 항목 E(§4.5) 채택**(2026-09-11) — 실패 칩 색 상태를 넣으므로 `state` 필드가 남고 이슈 3 의 뷰 필드 제거는 **4개 → 3개**(`prompt_preview`·`result_preview`·`phase_title`)다. **승인 대기 항목은 더 없다 — 구현 착수 가능.**
- **기준 커밋**: `a07ce44` (깨끗한 `main`). **2회차 주의**: 2회차 작성 중 다른 세션의 커밋으로 HEAD 가 `cd0cea8` 로 전진했다(`tests/run.sh`·`tests/mutations.tsv`·문서만 변경, `hub/` 무변경). 이 문서의 `hub_template.html`·`hub_workflow.py` 행 번호는 HEAD 에서도 그대로지만 **`tests/run.sh` 행 번호는 `a07ce44` 기준이라 HEAD 에서 약 +17 이다** — 가드는 행 번호가 아니라 `# T25-164(` 같은 머리 주석·함수명으로 찾는다. 래칫 상수 값도 `readonly` 선언에서 읽는다(HEAD: `LEDGER_MUTATION_ROW_FLOOR=93` · `SOURCE_GUARD_ID_FLOOR=486`).
- **대상**: `hub/bin/hub_template.html` · `hub/bin/hub_workflow.py` · `hub/bin/hub_session.py` · `hub/README.md` · `tests/`
- **복잡도**: Large (파일 6개 · 이슈 1 CSS 규칙 약 30개 재배치 · 이슈 3 툴팁 제거 + 뷰 필드 4개 삭제 · 이슈 4 순수 함수 1개 + 뷰 필드 1개 · 테스트 그룹 4개 개정. **이슈 2 는 미채택이라 범위 밖**)
- **프리뷰 목업 (1회차)**: `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/d0e8c16b-e61e-45e8-a40b-96489604dfaf/scratchpad/hub-ui-4-issues-mockup.html`
  (PNG: `mock-a.png` · `mock-sec2.png` · `mock-sec3.png` · `mock-sec4.png` — 같은 디렉터리). 이슈 1·4 절은 이것으로 승인됐다. 이슈 2·3 절은 반려됐고 기록으로만 남는다.
- **프리뷰 목업 (2회차 — 이슈 2·3)**: `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/d0e8c16b-e61e-45e8-a40b-96489604dfaf/scratchpad/hub-ui-issue2-3-mockup.html`
  (PNG, 같은 디렉터리: `mock2-sec1.png` 한눈 비교 현재|A|B|C|D · `mock2-sec2.png` 카드 열림과의 구별 · `mock2-sec3.png` 작업중 겹침 · `mock2-sec4.png` 다크 · `mock2-sec5.png` 320px · `mock2-sec6.png` hover 충돌 · `mock2-sec7.png` 카드 높이 제한 없는 참고 렌더 · `mock2-sec8.png` 이슈 3 세 갈래 실측 문자열 23건 + 선택 항목 E · `mock2-v12.png`/`mock2-v12b.png` §14 관찰)

---

## 0. 요구사항 요약

허브(`hub.html`)의 프로젝트 카드에서 사용자가 제기한 UI/기능 결함 4건을 고친다. ①
카드의 접힘/펼침이 실질적으로 같은 화면을 보여주므로 **펼침 시각을 기본값으로 올리고**
카드 높이를 고정해 세션 목록만 스크롤한다. ② 세션 행을 열면 어느 카드 소속인지 알 수
없으므로 **행은 지금처럼 면색으로 두고, 그 행이 속한 카드에는 다른 채널의 신호(왼쪽 변의
3px 레일)를 CSS 만으로 얹는다**(2회차 — 1회차의 「카드 면색+테두리 · 행 1px 링」은 반려).
③ 워크플로우 `agent-chip` 툴팁은 형제끼리 같은 401자 프롬프트이고 결과는 84%가 잘린 raw
JSON 이라 읽을 수 있는 정보가 없으므로 **툴팁을 제거하고**, 그 툴팁만 읽던 서버 필드도 함께
뺀다(2회차 — 1회차의 「결과·실패·마지막 도구 앞세우기」는 반려). ④ 세션이 대시보드 작업을 끝낸 뒤 다른 일을 계속하면 끝난 대시보드가 계속
클릭되므로 **세션 수준 세대 판정**을 신설해 클릭 대상에서 뺀다.

### User Story

```
허브에서 여러 프로젝트의 세션을 훑는 사람으로서,
나는 카드를 열지 않고도 세션별 진행 상황과 소속을 알아보고,
읽을 수 없는 칩 툴팁에 시달리지 않고,
끝난 대시보드에 속지 않기를 원한다.
그래야 허브가 「지금 무슨 일이 어디서 벌어지고 있나」를 한 화면에서 답한다.
```

### Problem → Solution

| 이슈 | 현재 | 바뀐 뒤 |
|---|---|---|
| 1 | 카드를 펼쳐야 트리·세션 진행률이 보인다. 안 펼치면 접힘과 펼침이 같아 보인다 | 트리·세션 진행률이 기본값. 카드 340px 고정, `ul.sessions` 만 스크롤 |
| 2 | 세션 행을 열면 카드 표시가 사라져 소속을 잃는다 | 행은 면색 그대로, 소속 카드의 왼쪽 변에 3px `--accent` 레일(`:has()` — JS 0). 카드 자체 열림(면색+테두리)과 갈라진다 |
| 3 | 툴팁 앞 401자가 형제끼리 동일하고 결과는 잘린 raw JSON 이라 읽을 수 없다 | 워크플로우 칩 툴팁 제거(라벨만) + 그 툴팁만 쓰던 뷰 필드 4개 제거. 다른 툴팁 17개는 그대로 |
| 4 | 끝난 대시보드가 영원히 클릭된다 | 완료(100%) + 30분 이상 방치 판정 시 클릭 불가 + 패널 사유 |

---

## 1. 조사 방법과 실측 (설계 판단의 근거)

이 절의 숫자는 전부 이번 설계에서 **직접 측정**했다. 재현 스크립트는 세션
스크래치패드에 있다(`analyze.py` · `measure_tooltip.py` · `measure_rows.py` ·
`build_mockup.py` · 2회차 `analyze3.py` · `branches3.py` · `contrast2.py` · `build_mockup2.py`). 측정 대상은 `~/.claude/hub/hub.html` 의 `#dzh-data`(실 스냅샷),
`~/.claude/projects/*/*/workflows/wf_*.json` 66개 파일 450개 에이전트 항목, 그리고
헤드리스 Chrome(`--dump-dom`) 렌더다.

> **외부 조사 불필요** — 이 기능은 전부 내부 확립 패턴(순수 모듈 + 뷰 투영 + CSS 상태
> 클래스)만 쓴다. 새 라이브러리·API 없음. 대신 위 실데이터 계측이 「연구」를 대신한다.

### 1.1 이슈 1 — 접힘/펼침 차이의 실제 크기

| 프로젝트 | 카드H | ul 보임H | ul 내용H | 세션수 | 완전히 보임 | 행높이 min/중앙/max | 「없음」줄 | tier1 보유 |
|---|---|---|---|---|---|---|---|---|
| **현행 접힘** | | | | | | | | |
| NotebookWiki | 340 | 228 | 228 | 1 | 1 | 93/93/93 | 0 | 1 |
| coding-harness | 340 | 207 | 590 | 7 | 1 | 56/**75**/122 | 4 | 3 |
| atlas-…-micro | 340 | 228 | 228 | 2 | 2 | 75/**78**/78 | 2 | 0 |
| daily-brief | 340 | 254 | 254 | 2 | 2 | 115/**115**/115 | 2 | 0 |
| **제안(트리 + 340px 고정)** | | | | | | | | |
| NotebookWiki | 340 | 228 | 228 | 1 | 1 | 116/**116**/116 | 0 | 1 |
| coding-harness | 340 | 207 | **823** | 7 | 1 | 80/**99**/170 | 4 | 3 |
| atlas-…-micro | 340 | 228 | 228 | 2 | 2 | 99/**103**/103 | 2 | 0 |
| daily-brief | 340 | 254 | 274 | 2 | **1** | 137/**137**/137 | 2 | 0 |

- **행 높이 증분: 중앙값 +23~25px** (75→99 · 78→103 · 93→116 · 115→137).
- **340px 안에 완전히 보이는 세션 수: 1~2개 → 1~2개.** daily-brief 만 2→1. 나머지
  3개 카드는 변화 0 — 접힘 상태에서도 이미 1~2개만 보였기 때문이다(`ul` 보임 높이
  207~254px vs 행 75~115px). **「보이는 세션 수가 줄어든다」는 우려의 실제 크기는
  전체 4개 카드 중 1개에서 1개**다.
- **렌더된 세션 12개 중 8개(67%)가 `tier1` 이 없다** — 이 8개는 펼침에서
  `대시보드 없음` 한 줄을 얻는다(§2.1 선택 사항 X4).

### 1.2 이슈 1 — 사용자 관찰의 정확도 (부정확한 부분 명시)

사용자 원문: "`li::before` 노드 말고 다른점이 없는거 같아."

**이것은 부정확하다.** 접힘/펼침의 차이는 최소 5종이다:

| 차이 | 규칙 | 접힘에서 |
|---|---|---|
| 트리 연결선 | 452~459 · 470~474행 (`::before`/`::after`) | 없음 |
| 1단 들여쓰기 | 450행 `padding-left:24px` | 없음 |
| 2단 들여쓰기 | 468~469행 `margin-left:16px` | 없음 |
| 세션 행 축 전환 | 461행 `flex-direction:column` + 462~464행 `order` | `display:block` |
| **세션별 진행률** | **412행 `.card:not(.card-expanded) .session-tier1{display:none}`** | **숨김** |
| 카드 높이 | 331~332행 `height:auto` · `overflow-y:visible` | 340px + 스크롤 |

**메인 세션이 넘긴 진단(「34개 세션 중 tier1 을 가진 세션은 6개뿐이라 대부분의 카드에서
차이가 안 보인다」)은 방향은 맞지만 원인 한 겹을 빠뜨렸다 — 이 설계의 재측정 결과:**

`renderSessionProgress`(1567~1572행)는 **`tier1` 이 없어도 `.session-tier1` div 를 항상
출력한다**(`session.tier1 ? renderTier1(...) : '<div class="session-no-dashboard">대시보드
없음</div>'`). 따라서 412행이 접힘에서 숨기는 것은 tier1 보유 세션 6개의 진행률만이
아니라 **모든 세션 행의 한 줄**이다. 그런데도 사용자가 차이를 못 본 이유는 데이터
분포가 아니라 **시각적 위계**다 — 숨겨지는 것이 「진행률 줄 1개」뿐이고 연결선·들여쓰기는
카드 왼쪽 8px 폭의 얇은 선이라, 두 상태를 나란히 두지 않으면 눈에 「같은 목록」으로
읽힌다. 실제로 나란히 두면 명확히 다르다(목업 이슈 1 절 1열 vs 2열).

> 스냅샷 세션 수도 정정한다: 스냅샷에는 **세션 36개 / tier1 보유 6개**(메인 세션 진단은
> 34/6), 그중 **실제로 렌더되는 것은 4개 카드의 12개**다(`shouldRenderSession` +
> `STALE_SESSION_HIDE_AFTER_MS` 12시간 컷오프).

### 1.3 이슈 2 — 색 대비 실측 (WCAG 상대휘도 · CIE L*)

> **2회차 정정** — 이 표가 뒷받침한 1회차 결론(행 1px `--accent` 링, RM4)은 사용자 판정으로
> **번복됐다**(§3, 결정 SM1). 수치는 유효하며 §3.3 의 안 A~D 대비 표가 같은 산식(`contrast2.py`)
> 으로 재계산해 재사용한다.

| 쌍 | 라이트 | 다크 |
|---|---|---|
| 링 `--accent` 대 카드 기본면 `--surface` | **5.19:1** (ΔL* 54.0) | **7.12:1** (ΔL* 57.9) |
| 링 `--accent` 대 **열린 카드면** `--accent-soft` | **4.19:1** (ΔL* 45.7) | **5.76:1** (ΔL* 50.2) |
| 링 `--accent` 대 hover 면 `--soft` | **4.83:1** (ΔL* 51.1) | **6.63:1** (ΔL* 55.1) |
| (현행) 행 면색 `--accent-soft` 대 카드면 `--surface` | 1.24:1 (ΔL* 8.36) | 1.24:1 (ΔL* 7.74) |
| (참고) 행 구분선 `--soft` 대 `--surface` | 1.07:1 (ΔL* 2.89) | 1.07:1 (ΔL* 2.86) |
| (참고) 연결선 `--muted`@50% 대 `--accent-soft` | 1.96:1 (ΔL* 23.4) | 2.42:1 (ΔL* 24.8) |
| (본문 하한) `--muted` 대 `--accent-soft` | 4.60:1 | 5.27:1 |

**결론: 1px `--accent` 링은 세 가지 가능한 배경(기본면·열린 카드면·hover 면) 전부에서
비텍스트 최소 대비 3:1 을 넘는다**(최저 4.19:1, 라이트 열린 카드면). 4.19:1 은
263~283행 주석이 이미 「비텍스트 3:1 을 넉넉히 넘는다」고 기록한 그 값과 같다 — 새 근거가
아니라 같은 실측의 재확인이다. 다크는 손댈 이유가 없다(전 구간 5.76:1 이상).

또한 **현행 행 면색(1.24:1 / ΔL* 8.36)은 식별 한계 ΔL*≈2 를 넘는다** — 사용자 불만은
「행 표시가 안 보인다」가 아니라 「카드 표시가 사라진다」다. 행 표시는 지금도 보인다.

### 1.4 이슈 3 — 프롬프트 동일성과 툴팁 절단 (2건은 진단 정정)

> **2회차 정정** — (d) 표의 「채택」 판정(`resultPreview`·`lastToolSummary`·`error`)은 **번복됐다**
> (§4, 결정 WT1). 고유성은 높지만 **읽을 수 있는 형태가 아니다** — `resultPreview` 350/417 이 raw
> JSON 이고 그중 346 이 잘려 파싱 불가(§4.1). (a)~(c) 의 실측(형제 동일성 · 절단 0건 · 전문 복구
> 불가)은 그대로 유효하고, 그중 (c) 는 제거 판정의 근거 절반이다.

**(a) 형제 간 `prompt_preview` 동일성** — 스냅샷의 워크플로우 보유 세션 4건 전수:

| 세션 | 에이전트 | prompt 고유값 | prompt **LCP** | 접두사 제거 후 남는 것 | result 고유값 | result LCP |
|---|---|---|---|---|---|---|
| coding-harness/1fc9c845 | 9 | **1종** | **401자** | **빈 문자열** | 8종 | 0자 |
| coding-harness/de319e3b | 8 | **1종** | **401자** | **빈 문자열** | 8종 | 0자 |
| atlas…/efd964d1 | 3 | 3종 | **3자** | 398자 (= 거의 무변화) | 3종 | 2자 |
| claude-agents-manager/b07e0470 | 3 | **1종** | **401자** | **빈 문자열** | 3종 | 1자 |

**(b) 툴팁 절단 — 메인 세션 진단을 정정한다.** 넘겨받은 진단은 "401자 프롬프트가 앞을
차지하면 뒤의 `result_preview` 가 잘려 보이지 않을 수 있다"였다. **실측 결과 절단은
일어나지 않는다.** 실 CSS(`.tooltip`, 605~610행)로 실데이터 23개 툴팁을 헤드리스 Chrome
에 렌더해 자연 높이를 쟀다:

| 뷰포트 높이 | `max-height` = `calc(100vh - 16px)` | 툴팁 자연 높이 최대 | 절단 발생 |
|---|---|---|---|
| 1013px | 997px | 445px | **0 / 23** |
| 813px | 797px | 445px | **0 / 23** |
| 613px | 597px | 445px | **0 / 23** |

절단이 시작되려면 뷰포트 높이가 **461px 이하**여야 한다(445 + 16). 허브 창에서 현실적이지
않다. → **「결과가 잘려 안 보인다」는 원인이 아니다.** 진짜 원인은 순서와 비율이다: 툴팁
전체 830~850자 중 앞 **401~440자(개행 8~14개 · 자연 높이의 약 절반)** 가 형제끼리 완전히
동일한 공통 컨텍스트라, 눈이 매번 같은 글자 벽에 먼저 닿는다.

**(c) 프롬프트 전문은 복구 불가능하다 (요구의 데이터 부재).** 세 경로 전부 실측으로 닫혔다:

| 경로 | 실측 | 판정 |
|---|---|---|
| wf json 의 다른 필드 | `promptPreview` 말미 39자가 **파일 전체에서 0회** 등장 | 전문 없음 |
| `script`(워크플로우 스크립트 전문) | `promptPreview[100:200]` 은 있으나 **`label` 4종 전부 `script` 에 리터럴로 없음**(배열에서 파생) | 조인 키 없음 · 임의 JS 파싱 필요 |
| 메인 세션 transcript | `agentId`(`adf63bf41b202c935`)가 `~/.claude/projects/*/*.jsonl` **전체에서 0건** | 조인 키 없음 |

→ **「어떤 작업 지시를 내렸는지」를 툴팁에 싣는 것은 가용 데이터로 불가능하다.** 이
설계는 목표를 **「이 에이전트가 무슨 일을 했는지」**로 옮긴다(결정 TT1). **→ 2회차: TT1 은 번복됐다(WT1) — 「무슨 일을 했는지」도 가용 데이터(`resultPreview` 84% raw JSON · 98.9% 잘림)로는 답할 수 없어 툴팁을 제거한다.**

**(d) 대안 데이터원 전수 실측** (66파일 · 450 항목):

| 필드 | 존재 | 고유성 | 길이 | 판정 |
|---|---|---|---|---|
| `resultPreview` | 417/450 (92.7%) | LCP 0~2자 → **사실상 전부 고유** | 32~401 | **채택** |
| `lastToolSummary` | 327/450 (72.7%) | **292종 / 327** | 중앙 44 · max 60 | **채택** |
| `lastToolName` | 405/450 | **330건(73%)이 `StructuredOutput`** | 짧음 | **기각** (정보량 ≈ 0) |
| `error` | **33/33 (error 항목 전수)** | 사유 종류 구분됨 | 55~94 · 중앙 58 | **채택** (신규 발견) |
| `durationMs`·`toolCalls`·`tokens` | 427/450 | 수치 | — | 기각 (YAGNI — 「무슨 일」이 아니라 「얼마나」) |

`lastToolName` 분포: `StructuredOutput` 330 · `Bash` 61 · `Read` 10 · `Write` 2 ·
`Monitor` 1 · `Edit` 1.
`error` 실측 예: `"You've hit your session limit · resets 4pm (Asia/Seoul)"` ·
`"agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output"`.

> **`error` 가 이번 설계의 가장 값진 발견이다.** 오늘 `state=="error"` 인 에이전트의 툴팁은
> `result_preview` 가 없어(`workflowChipTooltipText` 1503행이 생략) **동일한 401자
> 프롬프트만** 뜬다 — 에이전트별 정보량이 정확히 0이다. `error` 를 실으면 그 자리가
> 「왜 실패했는가」로 채워진다.

### 1.5 이슈 4 — Δ 분포와 임계값 근거

`session.last_event_at_ms - session.tier1.file_mtime_ms` (tier1 보유 세션 6건 전수):

| Δ (분) | 프로젝트 | 세션 | state | base | tier1 percent | 세션 무소식(분) | 파일 나이(분) | 신판정 |
|---|---|---|---|---|---|---|---|---|
| **0.8** | coding-harness | d0e8c16b | working | working | **0** | 0 | 1 | **거짓** (살아 있다) |
| 4.6 | coding-harness | af5c0abe | idle | idle | 100 | 29 | 34 | 거짓 (Δ<30) |
| 8.1 | NotebookWiki | 76d1d3a0 | idle | idle | 100 | 3 | 11 | 거짓 (Δ<30) |
| 56.3 | coding-harness | 1fc9c845 | stale | idle | 100 | 1262 | 1318 | **참** |
| 1564.6 | NotebookWiki | 34a5e900 | stale | idle | 100 | 1294 | 2858 | **참** |
| 2444.9 | atlas-…-micro | 16d428bc | done | done | 100 | 1804 | 4249 | **참** |

- Δ > 30분: 3/6. **살아 있는 세션(0.8분)은 임계값의 1/37** — 두 배 이상의 안전 여유.
- 프로젝트 수준 `tier1_is_previous_task` 는 **6개 프로젝트 전부 False** — 메인 세션의
  진단(같은 세션 케이스에서 항상 False)을 실데이터가 그대로 확인한다.

**임계값 근거 — 새 상수를 만들지 않고 `stale_after_minutes`(30분)를 재사용한다:**

1. 이 값은 이미 **두 도구가 공유한다.** `hub_config.py:29` 의 `stale_after_minutes`,
   클라이언트 하드코딩 `STALE_AFTER_MINUTES = 30`(T25-130 이 고정), 그리고
   `commands/dashboard.md:540` — **「`30`분(허브의 `stale_after_minutes` 기본값과 같은 값)
   이내 갱신이면 `RECENT`」**. 즉 `dashboard.md` 는 이미 **「30분 안에 갱신된 대시보드는
   지금 쓰이는 중」**이라고 판정한다. 이 설계의 판정은 그 명제의 대우다.
2. 세 번째 리터럴 30 을 만들면 T25-130 계열의 결합을 하나 더 늘린다.

**측정 한계(정직한 경계)**: 「정상 작업 중 `step`/`log` 호출 간격의 분포」는 **측정할 수
없었다.** 대시보드 파일은 타임스탬프를 `#dz-updated` 하나만 보관하고(실측 5개 파일 전부
`data-seq` 는 있으나 항목별 시각 없음), 허브 이벤트 로그는 대시보드 쓰기를 기록하지
않는다. 따라서 「30분이 정상 간격을 넘는가」는 **살아 있는 세션 1건(Δ 0.8분)의 관측과
위 문서 근거로만** 지지된다. 이 한계가 결정 FT3(두 번째 연접)의 존재 이유다.

---

## 2. 이슈 1 — 카드 트리 기본화 (결정 TR1~TR8)

### 2.1 채택안과 대안

| | **안 A (권고)** | 안 B (대안) |
|---|---|---|
| 트리·세션 진행률 | 상시 | 상시 |
| `.card-expand-toggle` | **삭제** | 유지, 의미 변경 |
| 토글이 하는 일 | — | `height:340px` ↔ `height:auto` 만 |
| localStorage · 헬퍼 4개 · 리스너 | **삭제** | 유지 |
| 카드 높이 | 340px 고정 | 340px ↔ auto |
| 사용자 원문과의 일치 | 일치 | 부분 |
| CSS 삭제 줄 | 약 9줄 + 스코프 제거 13곳 | 스코프 제거 13곳 |
| JS 삭제 줄 | 약 60줄 | 0 |

**권고: 안 A.** 근거:

- **결정 U1~U7 의 전제가 사라진다.** U1~U7 은 「펼침이 트리를 보여준다」를 전제로 한
  설계다(`hub-unified-card-tree-ui.md`). 트리가 상시가 되면 토글이 보여줄 것이 남지
  않는다. `expandToggleLabel`(1292행)의 문구 `'세션 N개 트리로 보기'` 는 그때 **거짓**이
  된다 — 이미 트리로 보이고 있으므로.
- **안 B 는 사용자가 요청하지 않은 새 기능이다.** 「카드 높이 고정 해제」는 U5 가 만든
  컨트롤과 다른 기능이고, 새 라벨·새 aria 의미·새 승인이 필요하다. YAGNI
  (`rules/workflow/code-quality-baseline.md` — 「지금 필요 없는 확장성을 미리 만들지 않는다」).
- **340px 안에서 못 보는 세션의 대피로가 사라지는 대가는 실측상 작다**(§1.1 — 4개 카드 중
  1개에서 1개). `.sessions` 는 이미 스크롤 컨테이너다(418행 `overflow-y:auto`) — 사용자
  원문이 지목한 그 장치가 이미 있다.

> **결정 TR1 — U1·U2·U3·U4·U5·U6·U7·U9 를 번복한다.**
> 번복 근거: 위 세 항목. 선례 — `SP19` 가 `SP4` 를(패널 폭), `RV1` 이 done 터미널 가정을,
> `DU5` 가 `DU4` 를 번복한 형태와 같다. **U10·U11·U14 는 번복하지 않는다** —
> `CARD_SELECTOR`(U10)는 드래그 3리스너가 계속 쓰고, `.card[data-tier1-previous]>`
> 자식 결합자(U11)는 §4 가 더 필요해지며, 「확장 여부와 무관하게 세션 행은 항상 클릭
> 대상」(U14)은 이 변경 후 **무조건 참**이 되어 오히려 강화된다.
> **V2~V12 는 전부 유지한다** — 트리의 기하(레일 +4 · 갈고리 8 · 단당 16 · 갈고리 y 17)는
> 그대로고, 바뀌는 것은 그 규칙이 적용되는 **조건**뿐이다.

### 2.2 CSS 재배치 — 스코프 제거 vs 클래스 상시 부착

| | **스코프 제거 (권고)** | 클래스 상시 부착 |
|---|---|---|
| 변경 | 13개 규칙에서 `.card.card-expanded ` 접두 삭제 | `renderProject` 가 항상 `card-expanded` 를 붙인다 |
| CSS diff | 13줄 | 0줄 |
| 기존 가드 | **T25-185·T25-187·T25-191·T25-191a·T25-194 개정 필요** | 전부 통과 |
| 정직성 | 규칙이 무조건 적용된다는 사실을 그대로 표현 | 항상 켜진 「확장」 클래스 = 마크업의 거짓 |

> **결정 TR2 — 스코프를 제거한다.**
> 「클래스 상시 부착」은 **가드를 초록으로 유지하려고 의미 없는 클래스를 남기는** 형태다 —
> `tests/run.sh` 의 T32-7 선례가 경고한 「빨개지면 검사를 지운다」의 거울상이고, 더
> 나쁘다(검사는 남지만 검사하는 대상이 허구가 된다). 규칙의 **조건이 사라졌으면 가드도
> 그 사실을 반영해 개정하는 것이 옳다** — 이 저장소에 선례가 있다: **T25-186 은 사용자가
> halo 를 되돌리라고 해 단언이 정확히 반대로 뒤집히자 삭제되고, 역가드 T25-190 이 그
> 자리를 이었다**(tests/run.sh 8447~8456행 주석).

**역스코프 처리** — 412행 `.card:not(.card-expanded) .session-tier1{display:none}` 은
**삭제한다**(결정 TR3). 이 규칙의 존재 이유는 「접힘에서 숨긴다」였고 접힘이 없어진다.

### 2.3 카드 높이 340px

> **결정 TR4 — 340px 를 유지한다.**
> 근거: (a) 263행 주석이 고정값의 이유를 「카드 높이를 프로젝트마다 다르게 만들지 않기
> 위한」이라고 적었고 그 요구는 변하지 않았다(결정 W2). (b) 실측(§1.1)에서 완전히 보이는
> 세션 수 감소는 4개 카드 중 1개에서 1개뿐이다. (c) 값을 올리면 3열 그리드에서 한 화면에
> 보이는 **프로젝트 수**가 줄어 훑기가 나빠진다 — 340px 는 「헤더 블록 + 세션 약 3개」로
> 고른 값이고(263행 주석), 트리에서 그 수가 2개대로 내려가는 것은 스크롤이 흡수한다.
> 340 을 바꾸는 것은 이 PRP 의 범위 밖이다(사용자 승인 항목 §9-1 로 올린다).

### 2.4 선택 사항 X4 — 「대시보드 없음」 줄

렌더된 세션 12개 중 **8개(67%)** 가 대시보드를 갖지 않고, 상시 펼침에서 그 8개는
`대시보드 없음` 한 줄을 얻는다. 실측 효과(§1.1 네 번째 표):

| | 안 A 그대로 | 안 A + X4(숨김) |
|---|---|---|
| atlas 행 높이 중앙 | 103px | **77px** |
| daily-brief 행 높이 중앙 | 137px | **111px** |
| daily-brief 완전히 보임 | 1개 | **2개** (현행 복원) |
| coding-harness `ul` 내용 높이 | 823px | **719px** |

> **결정 TR5 — 기본은 「표시 유지」(변경 없음)로 두고, X4 는 사용자 승인 항목으로 올린다.**
> 근거: 이 줄은 사용자 요청 범위 밖이고(수술적 변경 — `karpathy-guidelines.md` #3),
> 정보를 없애는 방향이라 조용히 넣지 않는다. 다만 실측상 값이 있으므로 목업에서 나란히
> 보여 사용자가 고르게 한다(목업 이슈 1 절 두 번째 행). 채택 시에도 사유는 사라지지
> 않는다 — `data-panel-empty-reason`(`SESSION_NO_DASHBOARD_REASON`)이 패널에서 답한다
> (불변식 OC-A · 결정 ST25).

### 2.5 변경 상세

**CSS (`hub/bin/hub_template.html`)**

| 행 | 현재 | 변경 |
|---|---|---|
| 331 | `.card.card-expanded{height:auto}` | **삭제** (TR4 — 높이는 항상 340px) |
| 332 | `.card.card-expanded .sessions{overflow-y:visible}` | **삭제** (418행 `overflow-y:auto` 가 상시) |
| 345~347 | `.card-expand-toggle{…}` | **삭제** (TR1) |
| 348 | `.card-expand-toggle:hover{…}` | **삭제** |
| 349 | `.card-expand-toggle:focus-visible{…}` | **삭제** |
| 350 | `.card-expand-toggle svg{…transform:rotate(-90deg)}` | **삭제** |
| 351 | `.card.card-expanded .card-expand-toggle svg{transform:none}` | **삭제** |
| **412** | `.card:not(.card-expanded) .session-tier1{display:none}` | **삭제** (TR3) |
| 450 | `.card.card-expanded .sessions{padding-left:24px}` | → `.sessions{…;padding:0 8px 0 24px}` **로 418행에 합친다** (TR6) |
| 451 | `.card.card-expanded .sessions li{position:relative;border-top:0}` | → 419행을 `.sessions li{padding:2px 0;position:relative}` 로 교체 (TR7) |
| 452~459 | 연결선 4규칙 + `:first-child` + `::after` + `:last-child` | 접두 `.card.card-expanded ` 제거 |
| 461~465 | 행 축 전환 · `order` 2개 · `excerpt` · `session-meta` | 접두 제거 |
| 468~474 | 2단 자식 · `session-tier1::before/::after` · `~` 결합자 · `workflow-runs::before` | 접두 제거 |

> **결정 TR6 — 450행의 `padding-left:24px` 을 418행 `.sessions` 의 `padding` 에 병합한다.**
> 두 규칙이 같은 요소의 같은 프로퍼티를 두 줄에 나눠 쓰는 형태가 되면 T25-193(가로 번짐
> 네 숫자 일치)의 정규식 `padding:0 (\d+)px` 이 **더 이상 매치하지 않는다.** 병합하면
> 좌우 번짐 8px 이 한 선언 안에 남아 그 가드를 살릴 수 있다 — 다만 정규식은 개정해야
> 한다(§7). 값은 `padding:0 8px 0 24px`(상 0 · 우 8 · 하 0 · **좌 24**) — 8(번짐) +
> 16(1단 들여쓰기), 450행 주석의 산술 그대로다.

> **결정 TR7 — `.sessions li` 의 `border-top:1px solid var(--soft)` 를 삭제한다.**
> 451행이 이미 펼침에서 `border-top:0` 으로 지웠다 — 「구분선 대신 연결선이 형제를
> 가른다」(결정 V2). 상시 트리에서는 구분선이 그려질 상태가 없으므로 선언 자체를 지우고
> `position:relative` 만 남긴다. 이것이 결정 G8(이 파일 `border-bottom` 0건)과 같은 계열의
> 정리이고, **이슈 2 의 링과 충돌하지 않는다**(§3.4).

**JS (`hub/bin/hub_template.html`)**

| 행 | 대상 | 변경 |
|---|---|---|
| 53~57 | 머리 주석의 카드 확장 문단 + `EXPANDED_PROJECTS_STORAGE_KEY` 언급 | 「트리가 기본이다」로 개정 (T25-159 가 리터럴 수를 세므로 §7 참조) |
| 1112~1115 | `EXPANDED_PROJECTS_STORAGE_KEY` · `MAX_STORED_EXPANDED_PROJECTS` · `EXPANDED_CARD_CLASS` · `EXPAND_TOGGLE_SELECTOR` | **삭제 4개** |
| 1121~1124 | `EXPAND_TOGGLE_ICON_SVG` | **삭제** |
| 1190 | `var expandedProjectPaths = readStoredExpandedProjects();` | **삭제** |
| 1259~1266 | `readStoredExpandedProjects()` | **삭제** |
| 1268~1274 | `persistExpandedProjects()` | **삭제** |
| 1276~1279 | `isProjectExpanded()` | **삭제** |
| 1281~1288 | `nextExpandedProjects()` | **삭제** |
| 1290~1295 | `expandToggleLabel()` | **삭제** |
| 1297~1304 | `renderExpandToggle()` | **삭제** |
| 1306~1314 | `applyCardExpandedState()` | **삭제** |
| 1696~1697 | `isExpanded` · `expandedClass` 지역변수 | **삭제** |
| 1698 | `'<div class="card' + stateClass + expandedClass + '"'` | → `'<div class="card' + stateClass + '"'` |
| 1705 | `+ renderExpandToggle(isExpanded, visibleSessions.length)` | **삭제** |
| 2026~2040 | 확장 토글 클릭 리스너(document 위임) | **삭제** |
| **2382** | 패널 IIFE `if(event.target.closest('.card-expand-toggle')) return;` | **삭제** (버튼이 없으므로 가드할 대상이 없다) |

> **결정 TR8 — `PROJECT_PATH_ATTRIBUTE`(1117행)는 삭제하지 않는다.** 확장 리스너만 쓰던
> 것처럼 보이지만 `CARD_SELECTOR`(1108행) 주석이 근거로 삼은 드래그 경로와 엮여 있다 —
> 삭제 전에 렌더 IIFE 안의 참조 수를 `grep -c` 로 확인하고 0이면 삭제, 아니면 유지한다
> (「내 변경이 만든 고아만 치운다」 — `karpathy-guidelines.md` #3).

**문서**: `hub/README.md` 367~374행 — 「셰브론을 누르면 카드가 트리로 펼쳐진다」 문단을
「세션 목록은 항상 트리로 보인다 · 카드 높이는 340px 고정이고 넘치면 세션 목록만
스크롤된다 · 셰브론과 localStorage 영속은 없다」로 교체.

---

## 3. 이슈 2 — 세션 행 선택 표시 (결정 SM1~SM7 · 2회차 — RM1~RM6 번복) — **미채택 · 기록 보존**

> **이 절은 구현되지 않는다.** 2026-09-11 사용자 판정: 2회차의 네 안(A 윤곽 · B 좌측 레일 ·
> C 헤더 밑줄 · D 연결선 경로)과 1회차 안(RM1~RM6), 그리고 사용자 자신의 최초 제안까지
> **전부 미채택**이고 **현재 상태를 유지**한다 — "제안한 것들이 모두 마음에 들지 않아".
> 따라서 `.card.card-open`(284행) · `.card.card-open.card-working::after`(317행) ·
> `.session-row.card-open`(424행) · `applyOpenCardMarking`(2287~2304행) · `OPEN_CARD_CLASS`
> 는 무변경이고, T25-199 는 신설하지 않는다(§7.2). 아래 본문과 SM1~SM7 은 **왜 네 채널이
> 모두 기각됐는지의 기록**으로 남긴다 — 이 저장소는 결정을 조용히 지우지 않는다(§14 관례).
> 같은 요구가 다시 오면 §3.1 의 실패 진단과 §3.3~§3.6 의 대비 실측이 출발점이다.
>
> **재개 시 주의**: SM1~SM7 은 이슈 1(TR1~TR8) 적용 **후**의 행 상자를 전제로 계산됐다
> (`flex-direction:column` 상시 · `.session-tier1` 상시 · `border-top` 삭제 · 행 높이
> +23~25px). 이슈 1 은 이번에 구현되므로 그 전제는 유효해진다 — 재개할 때 다시 계측할
> 필요는 없다.

> **1회차(RM1~RM6)와 사용자의 최초 제안(카드에 `.card-open` 효과 + 행은 테두리만)은 모두
> 반려됐다.** 사용자 원문: "처음 내가 제안했던 ui와 목업에서 너의 제안 안 모두 별로인거 같네.
> 더 좋은 방안을 검토해줘." 「카드도 선택 효과, 행은 테두리만」은 더 이상 구속이 아니고, 남은
> 목표는 하나다 — **열린 세션 행이 어느 프로젝트 카드에 속하는지, 그 카드 안에서 어느 행이
> 열렸는지가 한눈에 읽혀야 한다.**

### 3.1 1회차가 실패한 이유 (1회차 목업 `mock-sec2.png` 재판정)

| 관찰 | 진단 |
|---|---|
| 카드 전체 `--accent-soft` 면색 + `--accent` 테두리 + 열린 행에 같은 `--accent` 1px 링 | **세 신호가 같은 색 언어(파랑)를 강도만 달리해 쓴다.** 면색 위의 같은 색조 1px 선은 대비 계산(4.19:1)은 통과하지만 시선이 잡지 못한다 — 「테두리가 하나 더 있다」로 읽힌다 |
| 「현재」 열(흰 카드 + 면색 행)과 비교 | **행 신호가 1회차 제안에서 오히려 약해졌다.** 현행 행 면색은 흰 카드 위 ΔL* 8.4 의 면적 신호인데, 제안은 그것을 면색 위 1px 선으로 바꿨다. 시선의 무게가 표적(행)에서 배경(카드)으로 옮겨 갔다 — 목표와 반대 방향 |
| 「카드(프로젝트 대시보드)를 열었을 때」 열과 비교 | **두 상태의 차이가 행 안 1px 선 하나뿐**이다. 카드 열림과 행 열림이 거의 같은 그림이 된다 |
| 사용자가 왜 「행은 테두리만」이라고 했는가 | 카드에 면색을 주면 행 면색(같은 `--accent-soft`)이 묻히기 때문이었다 — 그 문구는 카드 면색의 **결과**였다. 카드에 면색을 주지 않으면 그 제약은 저절로 풀린다 |

> **결정 SM1 — 시각 언어 분리 원칙.** 행(표적)은 지금처럼 **면색**(424행
> `.session-row.card-open{background:var(--accent-soft)}` — 무변경)으로 두고, 카드(맥락)에는
> **면색·행과 다른 채널**의 신호를 준다. 카드에 면색을 주지 않으므로 `.card.card-open`(284행,
> 카드 자체를 열었을 때의 면색+테두리)은 행 열림과 **자동으로 갈라진다.**
> **RM4(행 1px inset 링) 번복 · RM6(`.card.card-open` 무변경) 유지 · 사용자 최초 제안(카드에
> `.card-open` 효과) 불채택.**

### 3.2 조상 카드를 어떻게 표시하는가 — JS 가 아니라 CSS `:has()`

1회차(RM1)는 `applyOpenCardMarking` 이 행의 조상 카드에도 `card-open` 을 얹는 JS 변경이었다.
그러면 「카드 자체가 타깃」과 「카드가 조상」이 **같은 클래스**가 되어 CSS 가 둘을 구분할 수
없다 — SM1 이 요구하는 「조상은 면색 없이」가 불가능하다. 구분하려면 두 번째 클래스
(`card-open-ancestor`)를 JS 로 붙여야 하고, 그러면 OC8 의 「적용 지점 하나」가 실제로 둘이 된다.

> **결정 SM2 — 조상 카드(안 D 는 경로)의 표시는 CSS `:has()` 로 DOM 구조에서 파생한다. JS 변경 0.**
> `.card:has(.session-row.card-open)` 은 「열린 행을 품은 카드」를 마크업 변경 없이 고른다.
> - **OC8 이 문자 그대로 유지된다** — `applyOpenCardMarking`(2287~2304행)은 손대지 않고, 표시의
>   적용 지점은 여전히 세션 행 하나다. 「표시가 둘에 남았다」는 상태는 조상 표시가 행 표시의
>   CSS 함수라 원리적으로 존재할 수 없다.
> - **OC9·ST23 그대로** — `card-open` 클래스와 `aria-current="true"` 는 지금처럼 행에만 붙는다.
>   조상 카드는 클래스도 ARIA 도 갖지 않는다(1회차 RM3 의 「`aria-current` 는 한 곳만」과 결론은
>   같지만 그 분기 자체가 필요 없다).
> - **RM1·RM2·RM3 번복** — 셋 다 「JS 가 조상에 클래스를 얹는다」는 전제 위의 결정이라 전제와
>   함께 소멸한다. `OPEN_CARD_ANCESTOR_SELECTOR` 상수도 만들지 않는다.
> - **브라우저 지원(결정 SM6)**: `:has()` 는 Baseline 2023(Chrome 105 · Safari 15.4 · Firefox
>   121). 이 파일에서 처음 쓰는 선택자다(`grep -c ':has(' hub_template.html` = 0). 허브는 사용자
>   본인의 Chrome 에서 열리고(헤드리스 실측도 Chrome 152), 미지원 환경의 폴백은 **현재 동작
>   그대로**(규칙이 무시돼 행 면색만 남는다)라 깨지는 것이 없다. 규칙 옆 주석에 적는다.

### 3.3 후보 4안 — 카드 쪽 채널이 서로 다른 안들

「같은 효과의 강도 차이」가 1회차의 실패 원인이므로 네 안은 **카드 쪽 신호의 채널 자체가
다르다.** 행은 넷 다 면색(SM1). 목업 2회차: `mock2-sec1.png`(한눈 비교) · `sec2`(카드 열림과의
구별) · `sec3`(작업중 겹침) · `sec4`(다크) · `sec5`(320px) · `sec6`(hover 충돌) · `sec7`(카드
높이 제한을 푼 참고 렌더). 전부 **이슈 1 적용 후 CSS**(§2.5 를 프로그램으로 적용 · 트리 상시 ·
`border-top` 없음 · 340px + `ul` 스크롤) 위에 그렸고, 열린 행은 형제에 둘러싸인 **가운데 행**이다.

| | **안 A — 역전(윤곽)** | **안 B — 좌측 레일 (권고)** | **안 C — 헤더 밑줄** | **안 D — 연결선 경로** |
|---|---|---|---|---|
| 카드 쪽 채널 | 카드 테두리 `--accent` | 카드 왼쪽 변 안쪽 3px 세로 바 `--accent` | `.project-name` 아래 2px 밑줄 `--accent` | 열린 행까지의 트리 연결선(그 행의 갈고리 + 위쪽 형제들의 레일)만 `--accent` |
| CSS | `.card:has(.session-row.card-open){border-color:var(--accent)}` | `.card:has(.session-row.card-open)::before{…3px 바…}` (§3.4) | `.card:has(.session-row.card-open) .project-name{text-decoration:…}` (§3.6) | 3규칙 (§3.6) |
| 규칙 수 / 새 토큰 | 1 / 0 | 1 / 0 | 1 / 0 | 3 / 0 (단 `color-mix()` 필요) |
| hover(카드 테두리 `--accent`)와 충돌 | **충돌** — hover 된 이웃 카드와 같은 모양(`sec6`) | 없음 | 없음 | 없음 |
| `card-working`(테두리 `--accent` + bloom)과 겹칠 때 | **카드 신호 소멸** — 작업중 테두리와 동색(`sec3`) | 유지 — 바는 bloom 위에서도 보인다 | 유지 | 유지 |
| 카드 자체 열림(`.card.card-open` 면색+테두리)과의 구별 | 면색 유무만 | 바 vs 면색 — 명확 | 밑줄 vs 면색 — 명확 | 경로 vs 면색 — 명확 |
| 스크롤과의 관계 | 무관 | 무관(카드 변) | 무관(헤더) | **목록과 함께 스크롤** — 열린 행이 아래에 있으면 경로 위쪽이 잘린다 |
| 320px | 문제 없음 | 문제 없음 | 프로젝트명이 말줄임되면 밑줄도 짧아진다 | 문제 없음 |
| 멀리서 보이는 정도(목업 육안) | 중(1px 테두리) | **강**(3px 불투명 바) | 약~중(15px 글자 밑 2px) | 약(1px 선) |
| 의미 | 「이 카드가 관여한다」 | 「이 카드가 관여한다」 | 「이 카드의 제목이 활성」 | 「이 노드가 이 루트에 매달려 있다」 — 소속을 **경로**로 답한다 |
| 한 줄 트레이드오프 | 가장 작은 diff 이나 기존 두 상태와 색이 겹쳐 유일하지 않다 | 유일한 채널·강한 가시성·스크롤 무관 — 대가는 새 시각 요소 1개(바) | 조용하고 우아하지만 약하다 | 의미가 가장 정확하나 얇고 스크롤에 잘리며 `color-mix()` 의존이 늘어난다 |

**대비 실측** (`contrast2.py`, 토큰은 `hub_template.html` 원문에서 읽음 · WCAG 1.4.11 비텍스트
3:1 · CIE ΔL*):

| 쌍 | 라이트 CR / ΔL* | 다크 CR / ΔL* | 판정 |
|---|---|---|---|
| A 테두리 · B 레일 · C 밑줄 · D 경로선 `--accent` 대 카드면 `--surface` | **5.19:1** / 54.0 | **7.12:1** / 57.9 | 3:1 통과 |
| A 테두리 `--accent` 대 페이지 `--bg` | 4.64:1 / 49.6 | 7.88:1 / 62.8 | 통과 |
| D 경로선 `--accent` 대 열린 행 면색 `--accent-soft`(갈고리 꼬리가 행 상자에 걸치는 4px) | 4.19:1 / 45.7 | 5.76:1 / 50.2 | 통과 |
| D 경로선 `--accent` 대 이웃 연결선 `--muted`@50%(근사) | 2.45:1 / 26.7 | 2.70:1 / 28.8 | 선-대-선 판별은 색상(hue) 차가 답한다 — 참고치 |
| 공통: 행 면색 `--accent-soft` 대 카드면 `--surface` | 1.24:1 / **8.4** | 1.24:1 / **7.7** | 면적 신호(식별 한계 ΔL*≈2 의 4배). 색 단독이 아니다 — `aria-current` + 카드 신호가 함께 답한다(D4 다중 채널) |
| 행 면색 `--accent-soft` 대 hover 면색 `--soft` | 1.15:1 / 5.5 | 1.15:1 / 4.9 | 1회차 §1.3 그대로 |
| **`card-working` 겹침** — 카드 가장자리 bloom(`--accent` 를 `--surface` 위에 α 0.3~0.5 로 얹은 근사) 대 불투명 `--accent`(B 레일·C 밑줄·D 경로) | 3.35~**2.41**:1 / 37.4~26.1 | 3.93~**2.53**:1 / 39.0~27.1 | 펄스 정점 부근(α 0.5)에서 3:1 아래. 다만 (a) 바는 3px 불투명 면, (b) 행 면색이 함께 답하고, (c) bloom 은 숨쉬고 바는 정적 — **모션 유무가 판별자**(291~296행의 설계 언어 그대로) |
| A 테두리 대 hover · `card-working` 테두리 | 1.00:1 | 1.00:1 | **동색 — A 기각 사유** |

### 3.4 권고 — 안 B(좌측 레일)

> **결정 SM3 — 안 B 를 채택한다.** 규칙 1개 · JS 0 · 새 토큰 0. 284행 `.card.card-open` 규칙
> 바로 뒤에 둔다(카드 상태 규칙끼리 모은다 — T25-110 의 리터럴 검사는 그 한 줄만 보므로 뒤에
> 줄을 더해도 무관하다):
> ```css
> /* 열린 세션 행을 품은 카드(결정 SM2·SM3, docs/prps/hub-ui-4-issues.md §3). 행 자신은 면색
>    (.session-row.card-open)이고, 카드는 다른 채널 — 왼쪽 변 안쪽 3px --accent 바 — 로 소속을
>    말한다. 카드 면색·테두리를 쓰지 않는 이유: 면색은 .card.card-open(카드 자체가 열렸을 때)의
>    채널이고, 테두리는 hover·card-working 과 동색(1.00:1)이라 유일하지 않다(2회차 목업
>    sec3·sec6 실측). :has() 로 DOM 구조에서 파생하므로 applyOpenCardMarking 의 적용 지점은
>    여전히 행 하나다(OC8 유지). ::before 를 쓰는 이유: ::after 는 card-working 의 bloom
>    오버레이가 쓰고, box-shadow 는 .card.card-working 의 선언과 캐스케이드가 겹친다.
>    top/bottom 14px = 카드 border-radius — 모서리 곡선을 피해 직선 바로 둔다. 3px 는
>    2026-09-08 「테두리가 너무 두껍다」(2px 링) 피드백과 다른 요소다 — 링은 사방을 감싸지만
>    바는 한 변에만 있어 두께의 인상이 다르다(목업 sec1 확인). 이 파일 최초의 :has() 다 —
>    Baseline 2023(Chrome 105+), 미지원 브라우저의 폴백은 현재 동작(행 면색만)이다. */
> .card:has(.session-row.card-open)::before{content:"";position:absolute;left:0;top:14px;bottom:14px;
>   width:3px;background:var(--accent);border-radius:0 2px 2px 0}
> ```
> 근거: (a) **채널이 유일하다** — 카드 왼쪽 변의 바는 어떤 카드 상태도 쓰지 않는다(525행
> `.warnings` 의 `border-left:3px` 는 카드 안 경고 블록이라 담체·위치가 다르다). hover ·
> `card-working` · `card-open` 과 겹치는 프로퍼티가 없어 조합 규칙이 필요 없다. (b) **멀리서
> 보인다** — 5.19:1(라이트) · 7.12:1(다크)의 3px 불투명 면. 3열 그리드에서 어느 카드인지 훑어
> 찾는 데 충분하다(`sec1`·`sec4`). (c) **스크롤과 무관** — 열린 행이 `ul.sessions` 아래로
> 스크롤돼 안 보여도 카드 신호는 남는다. (d) **카드 열림과 갈라진다** — 카드 자체를 열면
> 면색+테두리, 행을 열면 흰 카드 + 바 + 면색 행(`sec2`). (e) diff 가 규칙 1개다. `.card` 는
> 이미 `position:relative;overflow:hidden`(263행)이라 `::before` 의 기준·클리핑이 갖춰져 있고,
> `.card::before` 는 이 파일에서 미사용이다(`grep -c '.card::before'` = 0).

> **결정 SM4 — 안 A 는 기각, 안 C·D 는 대안으로 남긴다.** A 는 hover·`card-working` 과
> 동색(1.00:1)이라 「어느 카드」를 유일하게 답하지 못한다(`sec3`·`sec6` 에서 실제로 사라진다).
> C 는 채널이 유일하고 조용하지만 15px 글자 밑 2px 선이라 3열 그리드에서 약하다. D 는 의미가
> 가장 정확하지만 1px 선이 목록과 함께 스크롤돼 잘리고, 형제 갈고리의 가로선을 `--muted` 50%
> 로 유지하려면 `color-mix()`(Chrome 111+)가 하나 더 필요하다. 사용자가 목업에서 C 또는 D 를
> 고르면 §3.6 의 규칙을 그대로 쓴다 — 나머지 결정(SM1·SM2·SM5~SM7)은 안과 무관하다.

### 3.5 `card-working` 과 겹칠 때

> **결정 SM5 — 317행(`.card.card-open.card-working::after`)과 `.card.card-working` 규칙은 손대지
> 않는다(RM5 계승).** 조합은 「숨쉬는 카드 + 정적인 바 + 정적인 행 면색」이다. 바(`::before`)와
> bloom(`::after`)은 다른 의사요소라 캐스케이드 경합이 없고, 페인트 순서상 bloom 이 위에 오지만
> 저투명이라 바가 비쳐 보인다(`sec3`·`sec4` 실측 — 라이트·다크 모두 식별된다). 대비는 §3.3 표의
> 「겹침」 행 — 펄스 정점 부근에서 3:1 아래로 내려가지만, 바는 3px 불투명 면이고 행 면색이 함께
> 답하며, 모션 유무가 판별자다.

### 3.6 대안 C·D 의 규칙 (채택 시 그대로 쓴다)

```css
/* 안 C */
.card:has(.session-row.card-open) .project-name{text-decoration:underline;text-decoration-color:var(--accent);
  text-decoration-thickness:2px;text-underline-offset:3px}
/* 안 D — 열린 행의 갈고리 + 위쪽 형제들의 레일. 형제 갈고리의 가로선은 --muted 50% 로 남겨야
   하므로 opacity 대신 color-mix() 로 색 자체를 만든다(새 토큰 0). 이슈 1(TR2) 스코프 제거 뒤의 셀렉터다. */
.sessions li:has(> .session-row.card-open)::before{border-left-color:var(--accent);box-shadow:inset 0 -1px 0 0 var(--accent);opacity:1}
.sessions li:has(~ li > .session-row.card-open)::after{border-left-color:var(--accent);opacity:1}
.sessions li:has(~ li > .session-row.card-open)::before{border-left-color:var(--accent);opacity:1;
  box-shadow:inset 0 -1px 0 0 color-mix(in srgb,var(--muted) 50%,transparent)}
```

C 의 `text-underline-offset:3px` 는 `.project-name`(`overflow:hidden`, 15px · line-height 1.5 =
22.5px 상자) 안에서 잘리지 않음을 목업으로 확인했다. **D 는 이슈 1 의 스코프 제거(TR2)에 코드로
의존한다** — `.card.card-expanded` 스코프가 남아 있으면 이 셀렉터가 맞지 않는다(§8.1).

### 3.7 가드

> **결정 SM7 — T25-199 를 아래 내용으로 신설한다**(1회차가 예정한 RM4 가드는 폐기).
> - 정: `.session-row.card-open{background:var(--accent-soft)}` 리터럴 존재 — 행 면색이 링으로
>   되돌아가지 않는다(RM4 회귀 방지).
> - 정: `.card:has(.session-row.card-open)::before{` 존재 + 그 규칙 본문에 `width:3px` ·
>   `background:var(--accent)` 존재 + `#` 색 리터럴 0건(G9).
> - 역: `applyOpenCardMarking` 본문(awk `function applyOpenCardMarking(){` ~ `function
>   openDetailPanel(`)에 `closest(` 0건 · 파일 전체에 `OPEN_CARD_ANCESTOR_SELECTOR` 0건 — 조상
>   표시가 JS 로 되돌아가지 않는다(SM2).
> - `.card.card-open{background:var(--accent-soft);border-color:var(--accent)}` 는 T25-110 이
>   이미 문자 그대로 고정한다 — 중복 검사하지 않는다.
> 1회차의 T25-200(RM1·RM3 가드)은 **신설하지 않는다** — 검사할 JS 변경이 없다.

**변경 파일**: `hub/bin/hub_template.html` 284행 `.card.card-open` 뒤에 규칙 1개 + 주석 ·
`hub/README.md` 358~359행(「지금 패널에 열려 있는 프로젝트의 카드는 배경색과 강조색 테두리로
표시된다」) 뒤에 세션 행 케이스 1문장 추가(『세션 행을 열면 그 행은 배경색으로, 행이 속한 카드는
왼쪽 변의 강조색 바로 표시된다 — 카드 자체를 열었을 때의 배경색 카드와 구별된다』 — T25-109 의
토큰 '배경색'·'어느 카드든' 은 그대로 남는다) · `tests/run.sh` T25-199 · `tests/mutations.tsv`
변조행 1건. **JS · `hub_*.py` 변경 없음.**

---

## 4. 이슈 3 — 워크플로우 칩 툴팁 제거 (결정 WT1~WT8 · 2회차 — TT1~TT8 번복)

> **1회차(TT1~TT8 — 결과·실패·마지막 도구를 앞세우고 지시는 120자 클램프)는 반려됐다.** 사용자
> 원문: "「결과」 내용도 정리가 안되고 json string 형태 그대로 보여서 딱히 정보를 얻을 수 있는
> 구조는 아닌거 같아. 필요 정보만 보여줄 수 있는 구조가 아니면 그냥 툴팁 ui는 제거하는게
> 좋겠어." 이것은 **조건문**이다 — 「필요 정보만 보여줄 수 있는 구조」가 있으면 그것, 없으면
> 제거. 이 절은 그 조건을 먼저 판정하고(§4.1~4.2), 불성립이므로 제거의 범위를 그린다(§4.3~4.7).

### 4.1 조건 판정 — `result_preview` 는 읽을 수 있는 형태가 아니다

`~/.claude/projects/*/*/workflows/wf_*.json` 66개 파일 · 450개 에이전트 항목 전수(`analyze3.py`):

| 구분 | 건수 |
|---|---|
| `resultPreview` 없음(전부 `state=="error"`) | 33 |
| **raw JSON 으로 시작**(`{`·`[`) | **350 / 417 (84%)** |
| 마크다운(헤딩·표) | 46 |
| 그 밖 평문 | 21 |
| 400자 이상(호스트 절단) | **411 / 417 (98.6%)** |
| raw JSON 중 `json.loads` 성공 | **4 / 350** → **346 (98.9%) 이 잘려서 파싱 불가** |

실물(스냅샷 세션 1fc9c845 · efd964d1):

```
ground:official-docs → '{"findings":[{"question":"Q1 — CLAUDE.md 발견 경로 전체와 우선순위(managed policy / user …'  ← 401자에서 끊김
implementer          → '{"summary":"public/word/js/script/speech_to_text.js 한 파일만 스펙대로 수정했다. (1) start() 안에 …'  ← 401자에서 끊김
gap:memory-layer     → '## 실측 메타\n\n| 레포 | ★ | 최종 push | 라이선스 | 배포 방식 | 자산 규모 |\n|---|---|---|---|…'  ← 표가 중간에 끊김
review:R1            → '{"findings":[],"verdict":"PASS"}'  ← 32자, 온전 (4/350 의 하나)
```

→ 결과의 84%가 **스키마 출력의 raw JSON** 이고 그중 98.9%가 **잘려서 파싱조차 안 된다.**
마크다운 46건은 표가 중간에 끊긴다. 툴팁에 무엇을 넣어도 키 이름·이스케이프·파이프 문자가
화면을 채운다 — 사용자 판정이 데이터와 일치한다. (1회차 §1.4-(d) 가 `resultPreview` 를 「LCP
0~2자 → 사실상 전부 고유」로 채택한 것은 **고유성**만 봤고 **가독성**을 보지 않았다 — 고유하지만
읽을 수 없는 문자열이었다.)

### 4.2 세 갈래 평가 — 스냅샷이 실제로 렌더한 4개 세션 · 23 에이전트에 적용한 문자열

23건 전체의 실제 문자열은 목업 `mock2-sec8.png`(표: 에이전트 · 현재 툴팁 앞 100자 · B · C)에
있다. 아래는 그 표에서 판정을 가르는 대표 행이다(`branches3.py` 출력 그대로).

| 세션 / 에이전트 | **(A) 제거** — 칩 라벨만 | **(B) 메타** — 자유 텍스트 0 | **(C) 휴리스틱** — 결과에서 첫 문자열 리프 / 첫 의미 줄 |
|---|---|---|---|
| 1fc9c845 / ground:official-docs | `ground:official-docs` | `ground:official-docs · Ground · done · Opus 5 · 9분 49초 · 162k 토큰 · 도구 38회` | `question: Q1 — CLAUDE.md 발견 경로 전체와 우선순위(managed policy / user / project / local), 각각의 정확한 경로와 로드 시점` ← **입력(질문)의 재진술** — 결과가 아니다 |
| 1fc9c845 / propose:minimal-ripple | `propose:minimal-ripple` | `… · done · Opus 5 · 9분 35초 · 145k 토큰 · 도구 18회` | `name: 루트 고정 + claudeMdExcludes 분리 (root-pinned exclude)` ← 읽힌다 |
| 1fc9c845 / propose:clean-break (error) | `propose:clean-break` | `… · error · Opus 5 · 28분 32초 · 180k 토큰 · 도구 37회`<br>`— 실패 —`<br>`agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid output` | `(결과 없음 — state=error)` |
| 1fc9c845 / judge:spec | `judge:spec` | `… · done · Opus 5 · 5분 46초 · 184k 토큰 · 도구 14회` | `lens: 공식 규격 정합성. 세 가지 공식 페이지를 WebFetch 로 직접 받아 전문 grep 했다(memory · context-window …` ← **관점 설명** — 판정 결과가 아니다 |
| 1fc9c845 / decide:final (error) | `decide:final` | `… · error · Opus 5 · 34초 · 165k 토큰 · 도구 10회`<br>`— 실패 —`<br>`You've hit your session limit · resets 9pm (Asia/Seoul)` | `(결과 없음 — state=error)` |
| de319e3b / gap:mattpocock-skills | `gap:mattpocock-skills` | `… · Gap-Dossier · done · Opus 5 · 7분 56초 · 128k 토큰 · 도구 20회` | `실측 메타` ← **표 제목** (마크다운 8건 중 5건이 `실측 메타`/`실측한 것`) |
| de319e3b / gap:ruler-safetynet | `gap:ruler-safetynet` | `… · done · Opus 5 · 7분 37초 · 155k 토큰 · 도구 46회` | `(추출 실패: 문자열 리프 없음) ← [harness: subagent output matched instruction-shaped pattern` |
| b07e0470 / fix:수치·문서 | `fix:수치·문서` | `fix:수치·문서 · 수정 · done · Sonnet 5 · 6분 57초 · 168k 토큰 · 도구 35회` | `완료 보고` ← **절 제목** (3건 중 2건) |
| efd964d1 / implementer | `implementer` | `implementer · 구현 · done · Sonnet 5 · 1분 37초 · 72k 토큰 · 도구 12회` | `summary: public/word/js/script/speech_to_text.js 한 파일만 스펙대로 수정했다. (1) start() 안에 있던 …` ← 읽힌다 |
| efd964d1 / verify:R1 | `verify:R1` | `… · 검증·검수 · done · Sonnet 5 · 6분 13초 · 113k 토큰 · 도구 8회` | `name: R1_재시작_재배달_루프` ← 첫 시나리오 **이름**, 통과 여부는 없다 |
| efd964d1 / review:R1 | `review:R1` | `… · done · Sonnet 5 · 4분 22초 · 85k 토큰 · 도구 13회` | `verdict: PASS` ← 읽힌다 |

**갈래 (B) 메타** — 필드 존재율(450건): `model` 450/450 · `durationMs`·`tokens`·`toolCalls`·
`attempt` 427/450(결측 23건은 전부 `cached` 항목) · `error` 33/33(error 항목 전수). **읽을 수
있고 에이전트별로 다르다** — 문자열이 증명한다. 그러나 답하는 질문이 **「얼마나」**(소요·토큰·
도구 호출)이고, 사용자가 원한 **「무슨 작업을 했나」**에는 한 글자도 답하지 않는다. `label` 은
이미 칩에 보이고, `phase`·`state` 는 라벨(`judge:`·`fix:`)과 칩 위치가 이미 말한다. 유지 비용은
작지 않다 — 서버 뷰 필드 5개 추가(수치 3 + `model` + `error`), 포맷 함수(분·초·k 토큰), 그리고
**툴팁이라는 UI 자체의 존속**. 「필요 정보만 보여줄 수 있는 구조」의 「필요 정보」가 사용자 문맥에서
작업 내용이었으므로 조건을 채우지 못한다. → **기각(대안으로 기록)**.

**갈래 (C) 휴리스틱** — raw JSON 350건에 「첫 문자열 리프」 추출기를 돌린 결과: **254/350
(72.6%)** 이 10자 이상의 문자열을 냈고 나머지 96건은 리프가 없거나(`[harness: …]` 알림 등) 10자
미만(`verdict: PASS` · `severity: medium` 류)이다. 그러나 성공률이 문제가 아니라 **추출된 것이
무엇인가**가 문제다. 첫 키 분포(350건): `reason` 73 · `severity` 41 · `summary` 27 · `lens` 24 ·
`title` 17 · `reasoning` 16 · `repo` 13 · `verdict` 12 … — **스키마가 스크립트마다 달라 첫 키의
뜻을 알 수 없다.** 위 표에서 보듯 `question`(입력의 재진술) · `lens`(관점 설명) · `name`(시나리오
이름)이 「결과」 자리에 들어오고, 마크다운은 첫 줄이 거의 항상 절 제목(`실측 메타` · `완료 보고`)
이다. 스냅샷 23건 중 「무슨 일을 했나」로 읽히는 것은 **5~6건(약 25%)** — `name` 3건(제안
이름) · `summary` 1건 · `verdict` 1건(+ `조사 완료. dossier를 작성한다.` 1건). 실패 시 화면은
`(추출 실패) ← [harness: subagent output matched …` 같은 잔해 또는 표 제목 한 단어다. 350건 중
346건이 잘려 있어 값이 문장 중간에서 끊기는 것도 그대로다. → **기각.** 성공률 72.6%의 「성공」이
정보를 담는 비율은 4건 중 1건이고, 어떤 키가 결과인지 아는 방법이 없다.

> **결정 WT1 — 조건 불성립 → 갈래 (A) 툴팁 제거.** 칩은 `label` 만 남는다.
> **TT1~TT8 전부 번복** — TT1(목표 전환 「무슨 일을 했나」)·TT3(절 순서)·TT4(120자 클램프
> 상수)·TT5(머리말 상수 4개)·TT6(서버 필드 `last_tool_summary`·`error_reason` 추가)·TT7(`str`
> 관례)은 툴팁이 없으므로 대상이 없고, TT2((a) 공통 접두사 제거 기각)·TT8(`.tooltip` CSS 무변경)
> 은 결론(하지 않는다)만 같은 이유로 남는다. **WF9 의 「칩별 툴팁」 부분을 번복한다** — 칩 행
> 자체(세션 줄 안의 `.workflow-runs`)는 WF9 그대로다.
> 근거: (1) §4.1 — 결과 84% raw JSON · 98.9% 파싱 불가. (2) 1회차 §1.4-(c) — 에이전트별 지시는
> 어떤 파일에도 없다(세 경로 전부 실측으로 닫혔다). 「무엇을 지시받았나」도 「무엇을 했나」도 가용
> 데이터로 답할 수 없다면 툴팁은 **읽을 수 없는 글자 벽을 hover 마다 띄우는 장치**다. (3) 갈래
> B·C 는 위와 같이 조건을 채우지 못한다.

### 4.3 제거 범위 — 무엇을 지우고 무엇을 남기는가 (잘못 지우면 무관한 툴팁이 죽는다)

> **결정 WT2 — 클라이언트 제거 범위는 아래 표의 「제거」 행 넷뿐이다.** `hub_template.html`
> 기준 행 번호(`a07ce44`).

| 대상 | 행 | 처분 | 이유 |
|---|---|---|---|
| `renderWorkflowChip` 의 `data-tooltip="' + escapeHtml(workflowChipTooltipText(agent)) + '"` | 1531~1532 | **속성 제거** — `'<span class="agent-chip">' + escapeHtml(workflowChipDisplayLabel(agent)) + '</span>'` | 사용자 불만의 대상 |
| `renderWorkflowChip` 위 주석(「data-tooltip 은 항상 붙는다 … 범주가 다른 정보」) | 1524~1528 | **개정** — 「툴팁을 붙이지 않는다(WT1) — 프롬프트·결과는 읽을 수 있는 형태가 아니었다(§4.1)」 | 근거가 뒤집혔다 |
| `workflowChipTooltipText(agent)` + 주석 | 1494~1505 | **삭제** | 유일한 호출자가 1532행 |
| `WORKFLOW_STATE_ERROR` | 1071 | **삭제** | 유일한 사용처가 1503행 |
| `WORKFLOW_RESULT_TOOLTIP_SEPARATOR` | 1072 | **삭제** | 유일한 사용처가 1504행 |
| 1065행 주석 「워크플로우 서브에이전트 지시 보기(… WF9)」 · 516행 CSS 주석 같은 문구 | 1065 · 516 | **문구 개정** — 「워크플로우 서브에이전트 칩 행(WF9 → WT1 로 툴팁 부분 개정)」 | 「지시 보기」가 거짓이 된다 |
| `renderAgentChip`(1388~1397) · `agentRunTooltipText`(1381~1385) | — | **불변** | **다른 툴팁이다** — `agent_runs` 칩(훅이 기록한 서브에이전트 타입)의 「{phase} 단계 · 진행 중/종료」. 사용자 불만의 대상이 아니다. **두 칩이 같은 `.agent-chip` 클래스를 공유**하므로 클래스명으로 찾아 지우면 이것이 함께 죽는다 |
| 그 밖의 트리거 전부 | 734 · 743 · 773 · 780 · 827 · 1302 · 1373 · 1448 · 1473 · 1489 · 1560 · 1639 · 1686 · 1702 · 1845 · 1908 · 2325 | **불변** | 새로고침 · 테마 토글 · 패널 닫기 · `#dzh-detail-note` · 드래그 핸들 · stale 배지 · `.excerpt` 전문 · `.session-model` 원문 ID · `.session-id` 전체 ID · file:// 안내(카드·행) · 티어 배지 · 사용량 만료 · 패널 제목 |
| 전역 툴팁 싱글턴 `#dzh-tooltip`(862~980, T1~T3) · `.tooltip` CSS(596~611) | — | **불변** | 다른 트리거 17개가 계속 쓴다 |
| `MAX_VISIBLE_WORKFLOW_CHIPS` · `WORKFLOW_LABEL_MAX_CHARS` · `workflowChipDisplayLabel` · `visibleWorkflowAgents` · `renderWorkflowRun` · `shouldRenderSession` 의 경유 | — | **불변** | 칩 행(WF9)은 그대로다 |

파일 전체의 `data-tooltip="` 리터럴은 **18건 → 16건**(2 감소 — 이슈 3 이 지우는 워크플로우
칩 툴팁 1건 + 이슈 1(확장 셰브론 삭제)이 함께 지우는 1건)이어야 한다 — 이 수치가 가드
T25-201 의 상수다(§4.6).

### 4.4 서버 — 툴팁만 읽던 뷰 필드의 제거 (데이터 최소화)

전수 확인(`grep -n 'agent\.' hub_template.html`): 클라이언트의 `WorkflowAgentView` 필드 참조는
`label`(1509, `workflowChipDisplayLabel`) · `phase_title`(1497) · `state`(1503) ·
`prompt_preview`(1498) · `result_preview`(1503~1504) 이고 **`index` 는 0건**이다. 1497~1504행은
전부 `workflowChipTooltipText` 안이다 — 툴팁을 지우면 클라이언트가 읽는 필드는 **`label` 하나**가
된다.

> **결정 WT3 — `WorkflowAgentView` 에서 `prompt_preview`·`result_preview`·`phase_title`·`state`
> 4개를 제거한다. `index` 는 남긴다.**
> - 넷은 **내 변경(툴팁 제거)이 만든 고아**다 — `karpathy-guidelines.md` #3 「내 변경 때문에 쓰이지
>   않게 된 것은 제거한다」. 이 저장소의 선례가 정확히 이 형태다: `hub_workflow.py` docstring
>   「루프 밖 보완」— `hub_template.html` 참조 0건인 `run_id`·`workflow_name`·`status`·
>   `started_at_ms` 4개를 데이터 최소화 근거로 제거(`hub-workflow-visibility.md` §19).
> - **`index` 는 이번 변경 전부터 클라이언트 참조 0건**이었다(정렬은 `_parse_agents` 가 raw dict
>   에서 끝낸다). 원래 있던 죽은 필드는 요청 없이 지우지 않는다 — §11 에 언급만 남긴다.
> - 효과: 실 스냅샷(23 에이전트)에서 항목당 약 816자 → hub.html 인라인 **약 19KB 감소**(235KB
>   의 8%). 인라인되는 **자유 텍스트 필드가 `label` 하나로 줄어 시크릿 유출 표면도 준다**(계약 A
>   의 방어 대상이 넷에서 하나로).
> - **선택 항목 E(§4.5)를 채택하면 `state` 는 남는다**(칩의 error 상태를 그것으로 판정한다).

> **결정 WT4 — 계약 A 를 재서술하고 상수 이름은 유지한다.**
> - 경로 1(스크럽 + 401자, `_scrubbed_and_clipped`) 대상: **`label`** 만. 경로 2(128자, 스크럽
>   없음, `_metadata_field`) 대상: **없음** → `_metadata_field`·`WORKFLOW_METADATA_MAX_CHARS`·
>   `_optional_scrubbed_and_clipped` 는 고아 → **삭제**(E 채택 시 `_metadata_field`·
>   `WORKFLOW_METADATA_MAX_CHARS` 는 `state` 를 위해 남는다).
> - docstring 의 「promptPreview 497/503(98.8%)이 이미 정확히 401자라 여유가 0 … 실사용 데이터
>   에서도 발동하는 방어선」 서술은 **근거 필드가 사라지므로 삭제**하고, 「`label` 실측 max 60자
>   — 401 상한은 병리적 입력(검수 재현 5,000자 label)에 대한 방어선이며 정상 데이터에서는 발동하지
>   않는다」로 **정정**한다(있는 그대로 적는다 — 1회차 정정의 정정).
> - `WORKFLOW_PREVIEW_MAX_CHARS` 는 **이름·값(401) 유지**. 개명하면 `test_hub_workflow.py`
>   (300행 등)와 주석 참조가 바뀔 뿐 동작 이득이 없다 — 「preview 는 역사적 이름(프롬프트·결과
>   발췌에서 유래, WT3 으로 대상이 label 만 남았다)」 1줄을 상수 주석에 남긴다.

**영향 범위** (`WT5` — 처방은 §7):

| 파일 | 영향 |
|---|---|
| `hub/bin/hub_workflow.py` | dataclass 필드 4개 삭제 · `_parse_agent_item` 4줄 삭제 · 헬퍼 3개 삭제 · 모듈/클래스 docstring·상수 주석 재서술 |
| `tests/hub/test_hub_workflow.py` | 삭제 약 11건 · 개정(대상 필드를 `label` 로 교체) 약 7건 · 신설 2건 — §7.2-A |
| `tests/hub/test_hub_model.py:361` · `test_hub_collect.py:181` | `WorkflowAgentView(...)` 생성 kwargs 를 `index`·`label` 로 축소 |
| `tests/hub/test_hub_collect.py:175~225` | 서로게이트 테스트의 `prompt_preview` 어서션 삭제(`label` 어서션이 같은 것을 이미 검사한다) |
| `tests/hub/test_hub_collect.py:1485` · `test_hub_workflow_read.py:40` | 픽스처의 호스트 키(`promptPreview` 등)는 그대로 둬도 파서가 무시한다 — 변경 불필요 |
| `tests/run.sh` T25-164 · T25-166 | 앵커·정규식·승인 목록 개정 — §7.1 |
| `hub/README.md` 199~206 · 212~222 | 인라인 값 목록·스크럽 대상 서술 — §4.7 |
| `hub_model.snapshot_content_key` | `asdict` 기반이라 필드가 줄면 키가 바뀐다 → 배포 직후 수집 1회에서 hub.html 이 다시 쓰인다(무해, 1회) |
| **T25-150** | **영향 없음** — `SessionView` 는 손대지 않는다. 1회차와 같다(이슈 4 만 `[-1].name` 을 옮긴다) |

### 4.5 실패한 에이전트의 사유 — 선택 항목 E — **채택됨 (2026-09-11 사용자 승인)**

> **이 절은 구현된다.** 아래 「채택 시」로 적힌 모든 조건절이 **발효된다** — `state` 필드 ·
> `_metadata_field` · `WORKFLOW_METADATA_MAX_CHARS` · `WORKFLOW_STATE_ERROR` 는 **남고**,
> 뷰 필드 제거는 `prompt_preview`·`result_preview`·`phase_title` 3개다. 이 문서 안에서
> 「E 채택 시」로 조건이 붙은 서술(§4.3 · §4.6 의 T25-200·T25-202·T25-164·T25-166 · §6.1 ·
> §7.2-A · §8.2 GOTCHA)은 전부 그 조건 분기를 따른다. **`sr-only` " 실패" 텍스트를 함께
> 넣는다** — 색 단독 금지(D4 다중 채널).
>
> **§7.2-A 의 테스트 이름 주의**: `test_agent_view_fields_are_exactly_index_and_label` 은
> E 채택으로 필드가 `index`·`label`·`state` 3개가 되므로 **이름과 단언을 함께 고친다**
> (예: `test_agent_view_fields_are_exactly_index_label_state`).

1회차가 「가장 값진 추가」로 판정한 `error` 필드(33/33 보유, 55~94자)는 툴팁이 없으면 실을 자리가
없다. 실측: `.agent-chip` 의 상태 CSS 는 `.agent-chip-running`(514행) 하나이고 **error 상태 CSS 는
없다** — 지금 `propose:clean-break`(error)와 `propose:minimal-ripple`(done)의 칩은 똑같이 보인다.

> **결정 WT7 — 선택 항목 E: 실패한 에이전트 칩에 시각 상태를 준다. 사용자 요청 범위 밖이므로
> 승인 항목으로 올리고 기본값은 「하지 않음」이다.**
> 채택 시(전부 기존 토큰·관용구):
> ```js
> var errorClass = agent.state === WORKFLOW_STATE_ERROR ? ' agent-chip-error' : '';   // renderAgentChip 의 runningClass 와 같은 형태
> // + '<span class="sr-only"> 실패</span>' — 색 단독 금지(D4 다중 채널), AGENT_RUN_RUNNING_LABEL 관용구
> ```
> ```css
> .agent-chip-error{color:var(--attention);background:var(--attention-soft)}   /* .badge.state-stale 과 같은 attention 쌍 */
> ```
> 대비: `--attention` 대 `--attention-soft` **4.39:1(라이트) · 6.06:1(다크)** — 라이트가 AA 4.5 에
> 0.11 못 미치지만 `.badge.state-stale`(376행)이 같은 쌍을 이미 쓰는 기존 수용치다. 면색끼리는
> 약하다(`--attention-soft` 대 일반 칩 `--soft` ΔL* 2.4 라이트 / 4.0 다크) — 글자색이 주 채널이고
> `sr-only` 텍스트가 보조기술 채널이다. 목업 `mock2-sec8.png` 맨 아래(라이트·다크). 채택하면
> `state` 필드·`_metadata_field`·`WORKFLOW_METADATA_MAX_CHARS`·`WORKFLOW_STATE_ERROR` 가 남고
> T25-164 의 정규식이 `agent\.(label|state)` 가 된다. **사유 문구(`error` 값) 자체는 어느 안에서도
> 화면에 싣지 않는다** — 필요하면 `wf_*.json` 원문을 본다.

### 4.6 가드 — 되돌림 방지와 「무관한 툴팁이 함께 죽었는가」

> **결정 WT6 — 가드 3개 신설 + 2개 개정.** 회귀의 조용한 방향은 「함께 죽는다」 쪽이므로 그
> 검사(T25-201)를 먼저 만든다.

| ID | 방향 | 검사 |
|---|---|---|
| **T25-201** | **정 (무관 툴팁 생존 — 가장 중요)** | (a) `renderAgentChip` 본문(awk `function renderAgentChip(run){` ~ `function visibleAgentRuns(`)에 `data-tooltip="' + escapeHtml(agentRunTooltipText(run))` 존재 · `function agentRunTooltipText(run){` 존재. (b) `class="session-id" data-tooltip="' + escapeHtml(session.session_id)` 존재. (c) `renderSessionExcerpt` 의 `' data-tooltip="' + escapeHtml(fullText) + '"'` 존재. (d) 파일 전체 `data-tooltip="` 리터럴 **정확히 16건**(18 − 2, 이슈 3 의 워크플로우 칩 1건 + 이슈 1 의 확장 셰브론 1건 — T25-107 「정확히 N회」 관용구 — 다른 트리거가 함께 죽으면 15 이하, 제거가 되돌아오면 17). 기존 T25-44(싱글턴 토큰 4종)·T25-67(usage-meta)·T25-96(detail-note)·T25-130(stale 배지)이 덮는 트리거는 중복 검사하지 않는다 |
| **T25-200** | 역 (되돌림 방지) | `renderWorkflowChip` 본문(awk `function renderWorkflowChip(agent){` ~ `function renderWorkflowRun(`)에 `data-tooltip` 0건. 파일 전체에 `workflowChipTooltipText`·`WORKFLOW_RESULT_TOOLTIP_SEPARATOR`·`WORKFLOW_STATE_ERROR` 0건(E 채택 시 마지막 하나는 예외) |
| **T25-202** | 역 (서버 되돌림 방지) | `hub_workflow.py` 에 `promptPreview`·`resultPreview`·`prompt_preview`·`result_preview`·`phaseTitle`·`phase_title`·`_optional_scrubbed_and_clipped` 0건 · `_metadata_field`·`WORKFLOW_METADATA_MAX_CHARS` 0건(E 채택 시 예외). 필드 **목록** 자체는 단위 테스트가 고정한다(§7.2-A `test_agent_view_fields_are_exactly_index_and_label`) |
| T25-164 | 개정 | 앵커 시작을 `function workflowChipDisplayLabel(agent){` 로(끝 `function renderWorkflowChip(agent){` 유지). 긍정 검사 ① `escapeHtml(workflowChipTooltipText(` **삭제**(그 함수가 없다), ② `escapeHtml(workflowChipDisplayLabel(` **유지**. 필드 정규식 `agent\.(label\|phase_title\|prompt_preview\|result_preview)` → `agent\.(label)`(E 채택 시 `agent\.(label\|state)`). 머리 주석의 「4개 필드」 서술 개정 |
| T25-166 | 개정 | 승인 헬퍼 목록에서 `_metadata_field`·`_optional_scrubbed_and_clipped` 제거(E 채택 시 `_metadata_field` 유지). 주석 8007~8008행의 목록도 함께 |

**원장 규약**: T25-164·T25-166 은 `mutations.tsv` 에 「S3 이전에 존재한 가드 — 개정·수정 시
변조행으로 승급」 면제행으로 있다(427·429행). 이번 개정으로 **둘 다 변조행으로 승급**해야 한다 —
T25-164: `escapeHtml(workflowChipDisplayLabel(` → `workflowChipDisplayLabel(` 치환이 실패를 재현 ·
T25-166: `_parse_agent_item` 에 `label=item.get("label")` 주입이 실패를 재현. 신설 3개와 합쳐
**변조행 +5**(§7.1 래칫 문단).

### 4.7 문서

> **결정 WT8 — 갱신 목록.**

| 파일 | 위치 | 변경 |
|---|---|---|
| `hub/README.md` | 199~206 | 「서브에이전트에게 준 지시·결과의 앞부분도 화면에 보인다」 → 「위임한 서브에이전트의 **라벨 칩**이 세션 줄에 보인다(칩에 툴팁은 없다 — 지시·결과 발췌는 읽을 수 있는 형태가 아니어서 2회차에 제거)」. 인라인 값 목록 「`index`·`label`·`phase_title`·`state`·프롬프트 앞 400자·결과 앞 400자」 → 「`index`·`label`」 |
| `hub/README.md` | 212~222 | 스크럽 대상 「`label`·`phase_title`·프롬프트·결과 네 값」 → 「`label`」. 「promptPreview 98.8%가 401자 …」 발동 빈도 서술 삭제(정정 — `label` max 60자). 「`state` … 128자 상한」 문장 삭제(E 채택 시 유지) |
| `hub/README.md` | 292~296 | 툴팁 트리거 목록 — 워크플로우 칩 언급 없음, **변경 없음**(확인) |
| `hub/bin/hub_template.html` 머리 주석 | 62~68 | WF9 문단은 「칩 행」만 말한다 — **변경 없음**(확인) |
| `hub/bin/hub_template.html` | 516 · 1065 | 「지시 보기」 → 「칩 행」(§4.3) |
| `docs/prps/hub-workflow-visibility.md` | — | **편집하지 않는다** — 설계 기록이다. 번복은 이 PRP 가 기록한다 |
| `hub/bin/hub_atomic_write.py:34` docstring | — | 「wf_*.json 의 promptPreview」 예시는 서로게이트의 **출처**(호스트 파일)를 말하는 문장이라 여전히 참 — **변경 없음** |

---

## 5. 이슈 4 — 끝난 대시보드 숨김 (결정 FT1~FT7)

### 5.1 판정 축

> **결정 FT1 — 판정 = `tier1.percent >= 100` **그리고**
> `last_event_at_ms - tier1.file_mtime_ms > stale_after_ms`.**

두 연접의 역할이 다르다:

| 연접 | 무엇을 말하는가 | 근거 |
|---|---|---|
| `percent >= 100` | **그 대시보드가 기록한 작업은 끝났다** | `commands/dashboard.md:42` — **「검수 완료가 곧 100% 다」**. 이 도구 자신의 어휘로 100% = 종료다. 사용자 원문의 「(대시보드 종료)」에 대응하는 유일한 관측 가능 신호 |
| `Δ > stale_after_ms` | **세션은 그 뒤로도 일했다** | 대시보드가 갱신을 멈춘 뒤 세션이 계속 이벤트를 냈다 = 그 대시보드는 현재 작업이 아니다 |

> **결정 FT2 — 새 임계값 상수를 만들지 않고 `stale_after_ms` 를 재사용한다.**
> 근거 §1.5: `hub_config.stale_after_minutes`(30) · 클라이언트 `STALE_AFTER_MINUTES = 30`
> (T25-130) · `commands/dashboard.md:540`(「30분 이내 갱신이면 RECENT」) — **세 곳이 이미
> 같은 값을 쓰고, 그중 하나는 「이 대시보드가 지금 쓰이는 중인가」라는 똑같은 질문에
> 답한다.** 네 번째 리터럴을 만들 근거가 없다. `compute_session_view` 는 이미
> `stale_after_ms` 를 받는다(357~366행) — 새 배관도 필요 없다.

### 5.2 오탐 방어 (가장 중요한 요구)

「살아 있는 대시보드가 사라지는」 회귀는 이슈 4 자체보다 나쁘다. 네 겹으로 막는다:

1. **`percent >= 100` 연접** — 진행 중인 대시보드는 100% 가 아니다. 실측: 유일하게 살아
   있는 세션(d0e8c16b)의 대시보드는 **0%** 다. 이 연접 하나로 「긴 서브에이전트가 40분
   돌아 Δ가 30분을 넘는」 시나리오(§1.5 의 측정 불가 구간)가 **거의 전부** 차단된다 —
   그 40분 동안 대시보드는 진행 중이므로 100% 가 아니다.
2. **Δ 여유** — 살아 있는 세션의 Δ 는 0.8분, 임계값의 **1/37**.
3. **워크플로우 자신의 터미널 동작이 파일을 되살린다** — `dashboard.md:61` 은 커밋·푸시
   단계에서 `log commit` 을 요구하고 그것이 대시보드 파일을 쓴다. 100% 도달 후의 정리
   구간도 정상 절차를 따르면 mtime 이 갱신돼 Δ 가 리셋된다.
4. **경계는 엄격한 `>`** — `is_tier1_from_previous_task`(300~310행)의 `>` 관례를 따른다.
   같은 밀리초는 판정을 켜지 않는다(오탐 회피 방향).

> **결정 FT3 — `percent >= 100` 연접은 오탐 방어 장치이며, 그 대가로 「60%에서 방치된
> 대시보드」는 판정에서 빠진다(의도된 미검출).** 그 경우 보이는 것은 「그 세션이 실제로
> 한 만큼」의 정직한 기록이므로, 끝난 작업을 현재로 오인시키는 이슈 4 와 성질이 다르다.
> 측정 불가 구간(§1.5 한계)이 있는 상태에서 **미검출과 오탐 중 미검출을 택한다.**

### 5.3 판정이 참일 때의 동작

| | **(A) 클릭 불가 + 사유 (권고)** | (B) 안내 줄 + 대시보드 유지 | (C) 기타 |
|---|---|---|---|
| 사용자 원문 「보이지 않아야 할거 같아」 | **일치** | 어긋남 | — |
| 정보 손실 | **없음** — 사유 문구가 답한다 | 없음 | — |
| 새 UI 부품 | **0개** (`.detail-empty` + `#dzh-detail-empty-reason` 재사용) | 0개 | — |
| 기존 문구 재사용 | 새 사유 문구 1개 | **불가** — GN6 문구가 세션 케이스에 거짓 | — |
| 오탐 시 대가 | 완료된 대시보드 1개를 못 본다 | 잘못된 안내 줄 | — |

> **결정 FT4 — (A) 를 채택한다.**
> 근거: (a) 사용자 원문과 일치. (b) **(B) 의 「정보를 없애지 않는다」는 이점이 (A) 에도
> 있다** — (A) 는 패널을 비우는 것이 아니라 **사유를 띄운다**(결정 OC4·OC7 의 기존 빈 상태
> 장치, 불변식 OC-A). 「이 세션이 발행한 대시보드는 완료된 이전 작업입니다 — 세션은 그
> 뒤로도 작업을 계속했습니다.」 (c) **(B) 는 문구를 하나 더 만들어야 한다** — 779~781행의
> GN6 문구 「지금 진행 중인 세션이 시작된 뒤 갱신되지 않았습니다」는 *다른* 세션 케이스를
> 설명하는 문장이라 **같은** 세션이 발행한 경우에 사실과 어긋난다. (B) 를 「기존 장치의
> 자연스러운 확장」으로 보이게 했던 것이 바로 그 문구 재사용 가능성인데, 그것이 성립하지
> 않는다. (d) 오탐 대가는 §5.2 의 네 겹이 감당한다.
> **목업 이슈 4 절에 (A)·(B)·정상 케이스 3종을 실 패널 마크업으로 나란히 두었다.**

> **결정 FT5 — 「그래도 열기」 우회 수단을 만들지 않는다.** 요청 범위 밖이고(YAGNI),
> 파일은 여전히 서버에 등록돼 있으므로 필요하면 프로젝트 카드 경로로 도달할 수 있다.

### 5.4 기존 프로젝트 수준 판정과의 관계

> **결정 FT6 — 별도 순수 함수를 신설한다. `is_tier1_from_previous_task` 를 재사용하지 않는다.**

| | `is_tier1_from_previous_task` (기존, 프로젝트) | `is_session_tier1_from_finished_task` (신설, 세션) |
|---|---|---|
| 질문 | *다른* 세션이 남긴 대시보드인가 | *자기* 대시보드의 작업이 끝났고 그 뒤로도 일했나 |
| 입력 | 살아 있는 세션들의 **시작 시각** 목록 | 그 세션의 **마지막 이벤트 시각** 1개 |
| 한정사 | `all()` | 단일 |
| 연접 | 없음 | `percent >= 100` |
| 실데이터 결과 | 6개 프로젝트 전부 False | 6건 중 3건 True |

두 판정은 독립적으로 참/거짓이 될 수 있고 담체도 다르다(카드 vs 세션 행).

> **결정 FT7 — 이름은 `is_session_tier1_from_finished_task`, 뷰 필드는
> `SessionView.tier1_is_finished_task` 로 한다.**
> `stale` 을 피한 기존 근거(세션의 stale=30분 무소식 · 사용량 is_stale 과 뜻이 다르다)를
> 그대로 계승하고, 축이 다르므로 `previous`(이전) 대신 **`finished`(완료)** 를 쓴다 —
> 이름만 읽고 두 판정을 혼동하지 않게 한다.

```python
def is_session_tier1_from_finished_task(
    tier1_percent: int, tier1_file_mtime_ms: int, last_event_at_ms: int, stale_after_ms: int
) -> bool:
    """세션이 발행한 자기 대시보드가 **끝난 작업**의 것인가(결정 FT1).

    두 연접의 역할이 다르다. `tier1_percent >= 100` 은 「그 대시보드가 기록한 작업이
    끝났다」를 말한다 — `commands/dashboard.md` 가 「검수 완료가 곧 100% 다」라고 정의한
    그 종료 신호다(대시보드 파일에는 별도의 완료/종료 필드가 없다). Δ 조건은 「세션이 그
    뒤로도 일했다」를 말한다.

    `is_tier1_from_previous_task`(위)와 별개 함수인 이유: 그 함수는 *다른* 세션이 남긴
    대시보드를 겨냥해 살아 있는 세션들의 **시작 시각**을 `all()` 로 본다. 사용자 케이스는
    *같은* 세션이 발행한 것이라 시작 시각 < 파일 mtime 이 되어 그 판정은 **항상 False** 다
    (실측: 스냅샷의 6개 프로젝트 전부 False). 여기서 보는 것은 **마지막 이벤트** 시각이다.

    임계값은 새 상수를 만들지 않고 `stale_after_ms` 를 재사용한다(결정 FT2) — 허브의
    `stale_after_minutes`·클라이언트 STALE_AFTER_MINUTES·`commands/dashboard.md` 의
    「30분 이내 갱신이면 RECENT」가 이미 공유하는 값이고, 마지막 것은 「이 대시보드가 지금
    쓰이는 중인가」라는 같은 질문에 답한다.

    경계는 엄격한 `>` 다(`is_tier1_from_previous_task` 와 같은 관례 — 오탐 회피 방향).
    `percent >= 100` 연접은 오탐 방어 장치다: 진행 중인 대시보드는 100% 가 아니므로,
    긴 서브에이전트 실행으로 Δ 가 임계값을 넘는 구간에서도 판정이 켜지지 않는다. 그 대가로
    「중간에 방치된 대시보드」는 검출하지 않는다(결정 FT3 — 의도된 미검출).
    """
    if tier1_percent < TIER1_FINISHED_PERCENT:
        return False
    return last_event_at_ms - tier1_file_mtime_ms > stale_after_ms
```

새 상수(`hub_project.py` 또는 `hub_session.py` 모듈 상단):
```python
# 대시보드가 「끝났다」고 볼 진행률(결정 FT1). commands/dashboard.md 의 「검수 완료가 곧
# 100% 다」가 이 값의 출처다 — 대시보드 파일에는 완료/종료 상태 필드가 없어서 진행률이
# 유일한 관측 가능 종료 신호다.
TIER1_FINISHED_PERCENT = 100
```

> **배치**: 함수는 **`hub_session.py`** 에 둔다(`hub_project.py` 가 아니다). 호출자가
> `compute_session_view`(357행) 한 곳이고, 그 함수가 이미 `facts.last_event_at_ms` ·
> `stale_after_ms` · `tier1` 셋을 모두 쥐고 있다. `hub_project.py` 에 두면 값을
> 계산해 넘기는 배관이 새로 필요해진다.

### 5.5 `SessionView` 필드와 클라이언트

```python
    workflow: WorkflowRunView | None = None
    # 이 세션이 발행한 자기 대시보드가 끝난 작업의 것인가(결정 FT1·FT7). tier1 이 없으면
    # 항상 False. ProjectView.tier1_is_previous_task 와 **다른 판정**이다 — 그쪽은 다른
    # 세션이 남긴 대시보드를 겨냥한 프로젝트 수준 장치다(is_session_tier1_from_finished_task
    # docstring 참조). model·workflow 와 같은 계열의 부가 정보라 기본값을 둔다.
    tier1_is_finished_task: bool = False
```

**T25-150 이 깨진다** — `dataclasses.fields(SessionView)[-1].name == "workflow"` 를
`"tier1_is_finished_task"` 로 갱신한다. 선례: 같은 검사가 `model` → `workflow` 로 이미
한 번 갱신됐다(SessionView 주석이 그 경위를 기록하고 있다).

`compute_session_view` 의 `SessionView(...)` 생성에 한 줄 추가:
```python
        tier1_is_finished_task=(
            tier1 is not None
            and is_session_tier1_from_finished_task(
                tier1.percent, tier1.file_mtime_ms, facts.last_event_at_ms, stale_after_ms
            )
        ),
```

**클라이언트** — 서버는 사실(bool)만 주고 클릭 가능 여부는 클라이언트가 정한다(결정 GN4
의 관례 — `tier1_is_previous_task` 도 bool 만 받아 속성/CSS 로 투영한다). `dashboard_key`
와 `_session_dashboard_key`(335~346행)는 **손대지 않는다** — 파일은 여전히 서빙 가능하고,
키를 None 으로 만들면 `hub_model._register_dashboard` 와의 불변식(등록은 되는데 키가
없거나 반대)을 다시 따져야 한다.

`sessionRowAttributes`(1549~1562행):
```js
    // 결정 FT4 — 끝난 작업의 대시보드는 클릭 대상에서 뺀다. 서버는 사실(bool)만 주고
    // 클릭 가능 여부는 여기서 정한다(GN4 와 같은 관례).
    var isClickable = Boolean(session.dashboard_key) && isServed && !session.tier1_is_finished_task;
```
```js
    // 아래 file:// 안내 툴팁도 함께 가려야 한다 — 끝난 대시보드에 「서버를 켜면 볼 수
    // 있습니다」를 띄우면 사유 문구와 정면으로 어긋난다.
    if(session.dashboard_key && !isClickable && !session.tier1_is_finished_task){
      attrs += ' data-tooltip="' + escapeHtml(FILE_MODE_DASHBOARD_HINT) + '"';
    }
```

`sessionPanelEmptyReason`(1714~1718행) — 분기 1개 추가, **순서가 중요하다**(끝난 작업
판정이 `dashboard_key` 존재 판정보다 앞):
```js
  function sessionPanelEmptyReason(session, isClickable){
    if(isClickable) return '';
    // 결정 FT4 — dashboard_key 판정보다 **앞**에 온다. 뒤로 가면 키가 있는 끝난
    // 대시보드가 FILE_MODE_DASHBOARD_HINT(서버를 켜라)로 잘못 설명된다.
    if(session.tier1_is_finished_task) return SESSION_FINISHED_TASK_REASON;
    if(session.dashboard_key) return FILE_MODE_DASHBOARD_HINT;
    return SESSION_NO_DASHBOARD_REASON;
  }
```
신설 상수(1153행 `SESSION_NO_DASHBOARD_REASON` 옆):
```js
  // 결정 FT4. 「이전 작업」 어휘는 프로젝트 카드의 안내 줄(GN6)과 공유하되, 이 문구는
  // **같은 세션**이 발행한 경우를 설명한다 — GN6 문구("지금 진행 중인 세션이 시작된 뒤
  // 갱신되지 않았습니다")는 다른 세션 케이스 전용이라 여기 재사용할 수 없다.
  var SESSION_FINISHED_TASK_REASON = '이 세션이 발행한 대시보드는 완료된 이전 작업입니다 — '
    + '세션은 그 뒤로도 작업을 계속했습니다.';
```

> **알려진 한계 (범위 밖)**: 세션의 대시보드 파일이 동시에 **프로젝트 티어 1 승자**이면,
> 세션 행은 막히지만 **프로젝트 카드는 같은 파일을 계속 연다.** 카드 쪽은 기존
> `ProjectView.tier1_is_previous_task` + `#dzh-detail-note` 장치의 영역이고(결정 GN1~GN7),
> 사용자가 제기한 것은 세션 행이다. 이 PRP 는 카드 쪽 판정을 바꾸지 않는다.

---

## 6. 데이터 모델 · 인터페이스 (모듈 경계별)

### 6.1 순수 계층 (`hub/bin/hub_workflow.py` — ★파일시스템·시각·환경변수 미접촉)

```python
WORKFLOW_PREVIEW_MAX_CHARS: int = 401      # 이름·값 유지 (WT4 — 대상은 label 만, 「preview」는 역사적 이름)
# 삭제 (WT4, 고아): WORKFLOW_METADATA_MAX_CHARS · _metadata_field · _optional_scrubbed_and_clipped
#   (선택 항목 E 채택 시 WORKFLOW_METADATA_MAX_CHARS · _metadata_field 는 state 를 위해 남는다)

@dataclass(frozen=True)
class WorkflowAgentView:
    index: int                    # 유지 — 이번 변경 전부터 클라이언트 미참조(§11 언급만)
    label: str                    # 스크럽 + 401자 — 계약 A 경로 1 의 유일한 대상
    # 삭제 (WT3): phase_title · state · prompt_preview · result_preview — 툴팁만 읽던 필드
    # (선택 항목 E 채택 시 state: str 만 남는다 — 128자 상한, 스크럽 없음)
```
공개 함수 시그니처 변경 없음 — `parse_workflow_run(text: str) -> WorkflowRunView | None`.
`_parse_agent_item` 은 `index`·`label` 두 kwarg 만 남는다. **T25-165 의 순수 계약(`open(`·`Path(`·
`time.`·`os.` 0건)이 유지된다** — 삭제만 있고 추가는 없다.

### 6.2 순수 계층 (`hub/bin/hub_session.py`)

```python
TIER1_FINISHED_PERCENT: int = 100          # 신설 (FT1)

def is_session_tier1_from_finished_task(
    tier1_percent: int,
    tier1_file_mtime_ms: int,
    last_event_at_ms: int,
    stale_after_ms: int,
) -> bool: ...                             # 신설 (FT6)

@dataclass(frozen=True)
class SessionView:
    ...
    workflow: WorkflowRunView | None = None
    tier1_is_finished_task: bool = False   # 신설 (FT7) — 반드시 맨 뒤 (T25-150)
```
`compute_session_view` 시그니처 **변경 없음** — 기존 인자로 새 필드를 계산한다.

### 6.3 표시 계층 (`hub/bin/hub_template.html`)

| 심볼 | 변경 |
|---|---|
| CSS `.card:has(.session-row.card-open)::before{…}` | 신설 규칙 1개 (SM3) — 284행 `.card.card-open` 뒤 |
| CSS `.session-row.card-open{background:var(--accent-soft)}` (424행) | **무변경** (SM1) |
| `SESSION_FINISHED_TASK_REASON` | 신설 (FT4) |
| `renderWorkflowChip(agent) -> string` | `data-tooltip` 속성 제거 (WT2) |
| `workflowChipTooltipText(agent)` · `WORKFLOW_RESULT_TOOLTIP_SEPARATOR` · `WORKFLOW_STATE_ERROR` | **삭제** (WT2, 고아) |
| `sessionRowAttributes(project, session) -> string` | `isClickable` 산식 + 툴팁 가드 (FT4) |
| `sessionPanelEmptyReason(session, isClickable) -> string` | 분기 1개 (FT4) |
| `applyOpenCardMarking() -> void` | **무변경** (SM2 — 1회차의 2줄 추가 철회) |
| `renderProject(project) -> string` | 확장 관련 3줄 삭제 (TR1) |
| `EXPANDED_*` 상수 4개 · `EXPAND_TOGGLE_ICON_SVG` · 헬퍼 7개 · 리스너 1개 · 패널 가드 1줄 | **삭제** (TR1) |

**서버 → 클라이언트 계약 (JSON)**: `session.tier1_is_finished_task: boolean` 1개 추가 · `agent`
객체는 `{index, label}` 로 축소(`phase_title`·`state`·`prompt_preview`·`result_preview` 제거 — WT3).
`hub_model.snapshot_content_key` 는 `dataclasses.asdict` 기반이라 필드 증감을 자동으로 반영한다 —
`collected_at_ms` 만 제외하는 기존 동작 그대로고, 배포 직후 수집 1회에서 키가 바뀌어 hub.html 이
한 번 다시 쓰인다(무해 · 새 필드는 파생 「지금」 값이 아니므로 쓰기 억제를 무력화하지 않는다).

---

## 7. 테스트 계획

### 7.1 깨지는 기존 테스트 (전수 확인 결과)

| ID | 파일:행 | 무엇을 단정하나 | 왜 깨지나 | 처방 |
|---|---|---|---|---|
| **T25-185** | `run.sh:8438-8442` | `.card.card-expanded{height:auto}` 존재 · `.card:not(.card-expanded) .session-tier1{display:none}` 존재 | 두 규칙 모두 삭제(TR3·TR4) | **삭제**하고 **역가드로 교체**: `card-expanded` 리터럴이 0건 · `.session-tier1{display:none}` 형태가 0건. (T25-186 → T25-190 선례) |
| **T25-187** | `mutations.tsv:507` | `EXPANDED_CARD_CLASS` 상수 사용 | 상수 삭제 | **삭제** (변조행도 제거) |
| **T25-191 / 191a** | `run.sh:8551-8568` | 연결선 규칙이 `.card.card-expanded` 스코프 **안**에 있고 스코프 밖 유출이 **0건** | 스코프 제거로 유출 카운트가 13이 된다(역방향이 정확히 뒤집힌다) | **개정** — 역방향(유출 0) 삭제, 정방향만 남긴다: `.sessions li::before{top:0;height:18px` 같은 **스코프 없는** 리터럴 존재 검사. 삭제 이유를 그룹 머리 주석에 적는다(T25-186 선례) |
| **T25-193** | `run.sh:8500-8526` | `.sessions{…margin:10px -Npx 0;padding:0 Npx` 정규식으로 번짐 네 숫자 일치 | TR6 이 `padding:0 8px 0 24px` 로 바꿔 정규식 불일치 | **정규식 개정**: `padding:0 (\d+)px 0 (\d+)px` 로 받고 우측 8 과 좌측 24 = 8 + 16 산술을 함께 검사 |
| **T25-194** | `run.sh:8570-8576` | `.card.card-expanded .session-row{display:flex…}` 등 3종 리터럴 | 접두 제거 | **리터럴 3개 갱신** (`.session-row{display:flex;flex-direction:column}` 등) |
| **T25-182** | `run.sh:8404-8412` | 패널 IIFE 에 `closest('.card-expand-toggle')` 조기 반환이 `CLICKABLE_CARD_SELECTOR` 판정보다 앞 | 버튼·가드 모두 삭제 | **삭제**하고 역가드로 교체: `card-expand-toggle` 리터럴 0건 |
| **T25-159** | `run.sh:7848-7854` | `'dzh-expanded-projects'` 리터럴 **정확히 1건** + 줄 앵커 선언 1건 | 상수 삭제로 0건 | **개정** — 기대값을 0 으로 뒤집는다(잔재 역가드). 머리 주석의 `EXPANDED_PROJECTS_STORAGE_KEY` 언급도 함께 제거해야 한다 |
| **T25-150** | `test_hub_session.py:695` | `fields(SessionView)[-1].name == "workflow"` | 필드 추가 | `"tier1_is_finished_task"` 로 갱신 (`model`→`workflow` 선례) |
| **T25-164** | `run.sh:7951-7985` | 긍정 검사 `escapeHtml(workflowChipTooltipText(` 존재 · awk 앵커 `workflowChipTooltipText`~`renderWorkflowChip` · `agent.(label\|phase_title\|prompt_preview\|result_preview)` 접근이 헬퍼 밖 0건 | `workflowChipTooltipText` 삭제(WT2)로 **긍정 검사 ①이 실패하고 awk 앵커가 깨져 `record_failure`** | **개정** — 긍정 검사 ① 삭제(② `escapeHtml(workflowChipDisplayLabel(` 유지), 앵커 시작을 `function workflowChipDisplayLabel(agent){` 로, 정규식을 `agent\.(label)` 로(E 채택 시 `\|state`), 머리 주석 개정. **면제행 → 변조행 승급** |
| **T25-166** | `run.sh:8000-8101` | `WorkflowAgentView` 생성자 kwarg 전부가 승인 헬퍼 5종으로 시작 | kwarg 가 `index`·`label` 둘로 줄어 검사는 통과하지만 승인 목록에 **삭제된 헬퍼 2개**(`_metadata_field`·`_optional_scrubbed_and_clipped`)가 남는다 | **개정** — 목록에서 둘 제거(E 채택 시 `_metadata_field` 유지) + 8007~8008행 주석. 죽은 이름을 목록에 남기면 「승인된 헬퍼」가 허구가 된다(TR2 와 같은 판단). **면제행 → 변조행 승급** |
| `test_hub_workflow.py` | 전역 | 삭제되는 필드 4개·헬퍼 3개에 대한 어서션·픽스처 약 18건 | 필드 제거(WT3·WT4)로 `AttributeError` | **삭제 약 11건 · 개정 약 7건 · 신설 2건** — §7.2-A 표 |
| `test_hub_model.py:361` · `test_hub_collect.py:181` | — | `WorkflowAgentView(index=…, label=…, phase_title=…, state=…, prompt_preview=…, result_preview=…)` 직접 생성 | 삭제된 kwarg 로 `TypeError` | kwargs 를 `index`·`label` 로 축소. `test_hub_collect.py:218~220` 의 `prompt_preview` 어서션 2줄 삭제(`label` 어서션이 같은 정규화를 이미 검사) |
| `test_hub_project.py:48-63,72-217` | — | `is_tier1_from_previous_task` · `tier1_is_previous_task` (13건) | **손대지 않는다** (별도 함수 — FT6) | 변경 없음 |
| `hub/README.md` 가드 | `run.sh:5480,5752,6306,…` | `'이전 작업'`·`'구세대'`·`'/dashboard init'`·`'작업중'`·`'1~3열'` 등 토큰 존재 | README 367-374 문단 교체 | 위 토큰은 다른 절에 있어 **유지된다.** 교체 후 `bash tests/run.sh` 로 확인 |

**깨지지 않는 것 (확인 완료)**: T25-108·T25-110(`.card.card-open{` 존재 · 색 리터럴 없음 ·
면색+테두리 리터럴 — SM1 이 그 규칙을 그대로 두므로 통과; SM3 의 새 규칙은 그 뒤 줄이다) ·
T25-107(`applyOpenCardMarking` 존재 · `dzh:rendered` 2회 · MutationObserver 2회 — SM2 는 JS 를
건드리지 않는다) · T25-126(`started_at_ms` 기본값 없음) · T25-130(`STALE_AFTER_MINUTES = 30` ·
stale 배지 `data-tooltip` — WT2 범위 밖) · T25-87(ProjectView 필드 순서) ·
T25-65·T25-171·T25-195(`card-working-glow` 진폭 `.6` · 주기 `4s` · `@keyframes` 2개 — SM3 은
`@keyframes` 를 추가하지 않는다) · T25-85(G8 `border-bottom` 0건 — SM3 은 `border-radius` 만 쓴다) ·
T25-183(OC-A 쌍) · T25-184(`>` 결합자) · T25-192(세로 여백 합 14 — `.sessions li{padding:2px 0` 과
`.session-row{…padding:5px 8px` 둘 다 유지) · T25-165(순수 계약 — 삭제만 있다) ·
T25-43(`renderAgentRuns`·`agent-chip`·`MAX_VISIBLE_AGENT_CHIPS` 토큰 — 칩 행은 남는다) ·
T25-44(툴팁 싱글턴 토큰 4종 · 네이티브 `title` 0건) · T25-67(usage-meta 툴팁) · T25-96(detail-note
툴팁) — **툴팁 싱글턴과 다른 트리거 17개는 WT2 범위 밖이다.**

> **래칫 상수**: 신규 가드를 붙이면 `LEDGER_MUTATION_ROW_FLOOR` · `SOURCE_GUARD_ID_FLOOR` 를
> 올려야 하고(값은 `tests/run.sh` 의 `readonly` 선언에서 읽는다 — 1회차가 적은 87·480 은 `a07ce44`
> 의 실제 값이 아니다, 2회차 확인), **`mutations.tsv` 의 `T99-6` 행 sed 리터럴
> `LEDGER_MUTATION_ROW_FLOOR(93`** 도 같은 커밋에서 함께 옮겨야 한다(그 행의 사유 칼럼이 이
> 함정의 재현 기록을 갖고 있다 — 옮기지 않으면 T37-15 가 「가드 무력화」로 잡는다). **이슈 3 은
> 면제행 2개(T25-164·T25-166)를 변조행으로 승급시킨다(§4.6)** — 변조행 +2 가 여기에 더해진다.
> 가드를 **삭제**하는 쪽이 더 많으므로(T25-182·185·187 + 191 의 역방향) 순증가는 음수일
> 수 있다 — 하한 래칫은 내리는 것이 자유이지만, `tests/run.sh` 의 상수 주석에 **왜
> 줄었는지**를 적는다(올릴 때와 같은 기록 의무).

### 7.2 새로 추가할 테스트

**A. `tests/hub/test_hub_workflow.py` (순수 파서 — 계약 A, WT3·WT4 반영)**

| 처분 | 테스트 | 이유 / 새 내용 |
|---|---|---|
| **신설** | `test_agent_view_fields_are_exactly_index_and_label` | `[f.name for f in dataclasses.fields(WorkflowAgentView)] == ["index", "label"]` — WT3 되돌림 방지(T25-150 의 `[-1].name` 관용구를 목록 전체로). E 채택 시 `["index", "label", "state"]` |
| **신설** | `test_host_preview_fields_are_not_inlined` | 실측 형태 항목(`promptPreview`·`resultPreview`·`phaseTitle`·`state` 전부 채움)을 파싱한 뒤 `json.dumps(dataclasses.asdict(view))` 에 그 네 **값의 문자열이 등장하지 않는다** — 이름이 아니라 값으로 검사해 「이름만 바꿔 다시 인라인」을 잡는다 |
| **개정 (담체를 `label` 로)** | `test_key_value_secret_keeps_key_name` · `test_truncation_mark_is_preserved` · `test_scrubbing_happens_before_clipping_not_after` · `test_exactly_401_chars_is_not_clipped` · `test_unpaired_surrogate_in_prompt_preview_is_preserved_without_raising`(→ `…_in_label_…`) · `test_every_string_field_is_bounded_against_pathological_payload`(오버라이드를 `label` 만으로) · `test_minimal_valid_run_parses_all_fields`(어서션을 `index`·`label` 로) | 검사하는 동작(스크럽→절단 순서 · 401 경계 · 서로게이트 보존 · 상한 래칫)은 그대로 유효하고 담체만 바뀐다 |
| **삭제** | `test_error_state_missing_result_preview_is_none` · `test_prompt_preview_secret_is_redacted` · `test_result_preview_secret_is_redacted` · `test_oversized_prompt_preview_is_clipped_to_401_chars` · `test_oversized_result_preview_is_clipped_to_401_chars` · `test_oversized_phase_title_is_clipped_to_401_chars` · `test_phase_title_secret_is_redacted` · `test_null_prompt_preview_falls_back_to_empty_string`(`test_non_string_label_falls_back_to_empty_string` 이 같은 경로를 검사) · `test_unknown_state_value_is_preserved_verbatim` · `test_oversized_agent_state_is_clipped_to_128_chars` · `test_metadata_field_is_not_scrubbed` | 검사 대상 필드·헬퍼가 사라진다(마지막 셋은 E 채택 시 유지) |
| **유지** | `BoundedIndexTest` 4건 · `AgentCountLimitTest` · `ParserNeverRaisesOnPathologicalInputTest` · `test_label_secret_is_redacted` · `test_oversized_label_is_clipped_to_401_chars` · `test_agents_are_sorted_by_index_ascending` 등 | `index`·`label`·계약 B 는 그대로다 |

1회차의 `test_tt1~tt8`(신설 필드 2개 검증)은 **만들지 않는다**(TT6 번복).

**B. `tests/hub/test_hub_session.py` (세대 판정 순수 함수)**

| 테스트 | 입력 (percent, mtime, last_event, stale) | 기대 | 근거 |
|---|---|---|---|
| `test_ft1_below_100_percent_is_false` | 99, T, T+10h, 30m | `False` | 연접 1 |
| `test_ft2_100_percent_and_delta_over_threshold_is_true` | 100, T, T+31m, 30m | `True` | 기본 |
| `test_ft3_delta_under_threshold_is_false` | 100, T, T+29m, 30m | `False` | 기본 |
| `test_ft4_boundary_exactly_threshold_is_false` | 100, T, T+30m, 30m | `False` | 엄격한 `>` |
| `test_ft5_negative_delta_is_false` | 100, T, T−1, 30m | `False` | 파일이 마지막 이벤트보다 새롭다 |
| `test_ft6_live_session_real_shape_is_false` | **0, T, T+48s, 30m** | `False` | **실측 d0e8c16b** |
| `test_ft7_stale_session_real_shape_is_true` | **100, T, T+56.3m, 30m** | `True` | **실측 1fc9c845** |
| `test_ft8_idle_finished_recent_real_shape_is_false` | **100, T, T+4.6m, 30m** | `False` | **실측 af5c0abe** |
| `test_ft9_compute_session_view_without_tier1_is_false` | `tier1=None` | 필드 `False` | 결측 |
| `test_ft10_compute_session_view_sets_field` | 실측 형태 | 필드 `True` | 통합 |
| `test_ft11_session_view_last_field_is_the_new_flag` | — | `fields(SessionView)[-1].name` | T25-150 이전 |

**C. `tests/run.sh` 신규 가드 (문자열·구조 래칫)**

| ID | 검사 | 방향 |
|---|---|---|
| **T25-196** | `card-expanded` · `card-expand-toggle` · `dzh-expanded-projects` · `EXPAND_TOGGLE_ICON_SVG` 리터럴이 각각 **0건** | 역 (TR1 되돌림 방지) |
| **T25-197** | 연결선 4규칙이 **스코프 없이** 존재(`.sessions li::before{top:0;height:18px` 등 5개 리터럴) + `.sessions{…padding:0 8px 0 24px` | 정 (TR2·TR6·TR7) |
| **T25-198** | `.sessions li{` 규칙 본문에 `border-top` 이 **0건** | 역 (TR7 — 구분선 부활 방지) |
| ~~**T25-199**~~ | ~~`.session-row.card-open{background:var(--accent-soft)}` 리터럴 존재 · `.card:has(.session-row.card-open)::before{` 존재 + 그 규칙에 `width:3px`·`background:var(--accent)` 존재 + `#` 색 리터럴 0건 · `applyOpenCardMarking` 본문에 `closest(` 0건 · 파일 전체 `OPEN_CARD_ANCESTOR_SELECTOR` 0건~~ | **신설하지 않는다 — 이슈 2 미채택(§3).** 기존 T25-108·110 이 현재 상태를 계속 고정한다. 신규 가드 수는 9 → **8**, 변조행 증가는 +5 → **+4** |
| **T25-200** | `renderWorkflowChip` 본문(awk ~`function renderWorkflowRun(`)에 `data-tooltip` 0건 · 파일 전체 `workflowChipTooltipText`·`WORKFLOW_RESULT_TOOLTIP_SEPARATOR`·`WORKFLOW_STATE_ERROR` 0건(E 채택 시 마지막 하나 예외) | 역 (WT2 되돌림 방지) |
| **T25-201** | `renderAgentChip` 본문에 `escapeHtml(agentRunTooltipText(run))` 존재 · `function agentRunTooltipText(run){` 존재 · `class="session-id" data-tooltip="' + escapeHtml(session.session_id)` 존재 · `' data-tooltip="' + escapeHtml(fullText) + '"'` 존재 · 파일 전체 `data-tooltip="` **정확히 16건**(현재 18 − 2, 이슈 3 워크플로우 칩 1건 + 이슈 1 확장 셰브론 1건) | **정 (WT6 — 무관 툴팁이 함께 죽지 않았다; 회귀 방향이 조용해 가장 중요)** |
| **T25-202** | `hub_workflow.py` 에 `promptPreview`·`resultPreview`·`prompt_preview`·`result_preview`·`phaseTitle`·`phase_title`·`_optional_scrubbed_and_clipped` 0건 · `_metadata_field`·`WORKFLOW_METADATA_MAX_CHARS` 0건(E 채택 시 예외) | 역 (WT3·WT4 되돌림 방지) |
| **T25-203** | `sessionPanelEmptyReason` 본문에서 `tier1_is_finished_task` 분기가 `session.dashboard_key` 분기보다 **앞줄** | 정 (FT4 — 순서가 뒤집히면 사유가 거짓이 된다) |
| **T25-204** | `def is_session_tier1_from_finished_task(` 존재 · `TIER1_FINISHED_PERCENT` 존재 · `hub_session.py` 에 `stale_after_ms` 재사용(새 `30` 리터럴 0건) | 정+역 (FT2·FT6) |

각 신규 가드에 `tests/mutations.tsv` 변조행 1건씩(총 9건) + 개정으로 승급되는 면제행 2건(T25-164 ·
T25-166 → 변조행) = **변조행 +11** — 등록 규약대로 `anchor` 칼럼에 가드 함수명을 적는다.

### 7.3 검증 명령 (프로젝트 정본 — `CLAUDE.md` §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```
기대: 전부 통과. **이 저장소 안에서 `install.sh --scope project` 를 실행하지 않는다**
(자기 설치 금지 — T31-4 가 차단). **실제 `$HOME` 대상 설치도 하지 않는다.**

### 7.4 수동·시각 검증

- [ ] 2회차 목업(이슈 2 절 7개 · 이슈 3 절 1개)을 사용자에게 보이고 승인받는다(§9). 이슈 1·4 는
      1회차 목업으로 승인 완료.
- [ ] 구현 후 `~/.claude/hub/hub.html` 을 재수집해 실데이터로 확인:
      카드 트리 기본 · **세션 행 면색 + 소속 카드 왼쪽 변 3px 레일**(카드 자체를 열면 면색+테두리,
      레일 없음) · **워크플로우 칩에 hover 해도 툴팁이 뜨지 않고 `agent_runs` 칩·발췌·short_id·stale
      배지에는 여전히 뜬다** · 끝난 대시보드 3건이 클릭 불가(§1.5 표의 1fc9c845 · 34a5e900 ·
      16d428bc) · **d0e8c16b 는 여전히 열린다**.
- [ ] 최소 폭(320px 트랙) · 다크 테마 · `prefers-reduced-motion` · `card-working` 카드에서 레일이 보인다.
- [ ] 재수집된 `hub.html` 의 `#dzh-data` 에 `prompt_preview`·`result_preview`·`phase_title` 키가 0건이다.
- [ ] `.sessions` 에 **가로 스크롤바가 생기지 않는다**(TR6 이 T25-193 의 번짐 짝을
      유지하는지 육안 확인 — 이 결함은 직전 회차가 0으로 만든 것의 재발 경로다).

---

## 8. 구현 순서와 상호 의존

```
이슈 3 (툴팁 제거) ──┐
                      ├─→ 이슈 1 (CSS 재편)          [이슈 2 는 미채택 — §3]
이슈 4 (세대 판정) ───┘
```

> **이슈 2 가 미채택되어 구현은 3 → 4 → 1 세 단계로 끝난다.** 1회차·2회차가 모두 요구한
> 「이슈 1 → 2」 검증 의존은 **소멸한다** — 검증할 링·레일이 없다. 이슈 1 이 마지막 단계이고,
> 그 완료가 곧 구현 완료다. 아래 §8.1 은 미채택된 이슈 2 에 대한 분석이라 함께 보류된다.

| 순서 | 이슈 | 건드리는 것 | 왜 이 자리인가 |
|---|---|---|---|
| **1** | **3 (툴팁 제거)** | JS: `renderWorkflowChip` 속성 1개 + 고아 3개 삭제 · 서버: `hub_workflow.py` 필드 4개·헬퍼 3개 삭제 + 테스트·README | **CSS 규칙을 건드리지 않는다**(주석 2곳만). 다른 셋과 교집합 0 이고 diff 가 음수라 맨 앞이 자연스럽다 — 뒤의 셋이 더 작은 파일 위에서 시작한다 |
| **2** | **4 (세대 판정)** | `hub_session.py` + JS 속성 3곳 | **CSS 를 전혀 건드리지 않는다.** 이슈 3 과도 교집합 0(다른 파일·다른 함수) |
| **3** | **1 (CSS 재편)** | CSS 331~474행 · JS 확장 관련 전부 · README · 가드 7개 | 가장 큰 diff. 3·4 가 끝난 뒤에 시작해 CSS 회귀 조사 범위를 이 단계로 격리한다 |
| ~~4~~ | ~~**2 (선택 표시)**~~ | ~~CSS 규칙 1개(284행 뒤) + README 1문장 + T25-199~~ | **미채택(§3) — 이 단계는 없다.** Task 7 도 함께 보류된다(§8.2) |

### 8.1 이슈 1 과 이슈 2 의 충돌 지점 (밝혀 둘 것) — **보류(이슈 2 미채택)**

| 지점 | 이슈 1 | 이슈 2 | 충돌인가 |
|---|---|---|---|
| **419행 `.sessions li`** | `border-top` 삭제 (TR7) | — | 아니오 — 이슈 2 는 행에 테두리를 쓰지 않는다(SM1). 1회차의 「`border-top` 충돌」 물음은 대상이 없다 |
| **424행 `.session-row.card-open`** | 손대지 않음 | 손대지 않음 (SM1) | 아니오 |
| **461행 `.session-row{display:flex;flex-direction:column}`** | 스코프 제거 → 상시 flex | 행 면색이 그 상자를 채운다(현행 그대로) | **코드 충돌 아니오, 검증 의존만**: 행 상자가 이슈 1 로 +23~25px 커지고 그 상자를 면색이 채운다 — 목업은 이슈 1 적용 후 CSS 위에서 승인됐으므로 구현도 같은 순서로 육안 대조한다 |
| **284·317행 `.card.card-open` · `.card.card-working`** | 손대지 않음 | 손대지 않음 (SM1·SM5) — 284행 **뒤에** 새 규칙 1개 삽입 | 아니오 — T25-110 은 284행 리터럴만 본다 |
| **`.card::before`** | — | SM3 이 처음 쓴다 | 아니오 — 이 파일에서 `.card::before` 0건, `::after` 는 `card-working` 전용 |
| **안 D 채택 시** | `.sessions li::before/::after` 스코프 제거(TR2) | `.sessions li:has(…)::before` 3규칙이 그 셀렉터를 전제 | **코드 의존** — 이슈 1 이 먼저여야 셀렉터가 맞는다 |
| **가드** | T25-185·187·191·191a·193·194·182·159 개정 | T25-108·110 유지 + T25-199 신설 | **아니오** — 겹치는 가드 ID 없음 |

> **핵심**: 두 이슈는 **같은 CSS 파일**을 건드리지만 **같은 줄·같은 프로퍼티를 건드리지 않는다.**
> 안 B 의 의존은 코드가 아니라 **검증**이다 — 이슈 2 의 승인(레일 + 면색 행)이 이슈 1 이 만든 새 행
> 상자·트리 위에서 이루어졌으므로 구현 대조도 같은 순서로 한다. 1회차의 「1 → 2」는 유지되되 근거가
> 약해졌고(코드 의존 → 검증 의존), 안 D 를 고르면 다시 코드 의존이 된다.

### 8.2 단계별 작업 (Task 형식)

**Task 1 — 이슈 3 클라이언트** (`hub_template.html`) — **서버보다 먼저**: 클라이언트가 필드를 안
읽게 된 뒤에 서버가 필드를 빼야 「서버는 뺐는데 클라이언트는 읽는」 중간 상태가 없다
- **ACTION**: `renderWorkflowChip` 의 `data-tooltip` 속성 제거 + 주석 개정 · `workflowChipTooltipText`
  삭제 · `WORKFLOW_RESULT_TOOLTIP_SEPARATOR`·`WORKFLOW_STATE_ERROR` 삭제 · 516·1065행 주석 문구(§4.3)
- **GOTCHA**: `renderAgentChip`(1388~1397)·`agentRunTooltipText` 는 **손대지 말 것** — 같은
  `.agent-chip` 클래스를 쓰는 **다른** 툴팁이다. 클래스명으로 검색해 지우면 함께 죽는다(T25-201 이 잡는다)
- **VALIDATE**: 신규 T25-200·T25-201 + T25-164 개정본 · `grep -c 'data-tooltip="' hub_template.html` = 17

**Task 2 — 이슈 3 서버 + 테스트 + 문서** (`hub/bin/hub_workflow.py` · `tests/hub/*` · `hub/README.md`)
- **ACTION**: 필드 4개 · `_parse_agent_item` 4줄 · 헬퍼 3개 · 상수 1개 삭제 + docstring 재서술(WT4) ·
  §7.2-A 표대로 테스트 삭제/개정/신설 · `test_hub_model.py:361`·`test_hub_collect.py:181` kwargs 축소 ·
  README 199~206·212~222(§4.7) · T25-166 승인 목록
- **MIRROR**: `hub_workflow.py` docstring 「루프 밖 보완」 문단(미사용 필드 4개 제거 기록)과 같은 형태로
  이번 제거를 기록한다
- **GOTCHA**: `index` 는 지우지 말 것(WT3 — 원래 있던 미참조 필드, §11). 선택 항목 E 가 채택됐으면
  `state`·`_metadata_field`·`WORKFLOW_METADATA_MAX_CHARS` 를 남기고 T25-164 정규식에 `|state`
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_workflow tests.hub.test_hub_model tests.hub.test_hub_collect -v` ·
  신규 T25-202 · `bash tests/run.sh`

**Task 3 — 이슈 4 서버** (`hub/bin/hub_session.py`)
- **ACTION**: `TIER1_FINISHED_PERCENT` + `is_session_tier1_from_finished_task` +
  `SessionView.tier1_is_finished_task`(**맨 뒤**) + `compute_session_view` 1항목
- **MIRROR**: `is_tier1_from_previous_task`(`hub_project.py:300-310`) — 엄격한 `>` ·
  docstring 에 경계 근거
- **GOTCHA**: `SessionView` 필드는 **반드시 `workflow` 뒤**. T25-150 의 `[-1].name` 을
  같은 커밋에서 갱신할 것
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_session -v` (7.2-B 11건)

**Task 4 — 이슈 4 클라이언트** (`hub_template.html`)
- **ACTION**: `SESSION_FINISHED_TASK_REASON` + `isClickable` 산식 + 툴팁 가드 +
  `sessionPanelEmptyReason` 분기
- **GOTCHA**: `sessionPanelEmptyReason` 의 새 분기는 `dashboard_key` 분기 **앞**.
  불변식 OC-A 의 if/else 구조를 건드리지 말 것
- **VALIDATE**: 신규 T25-203 · `bash tests/run.sh`

**Task 5 — 이슈 1 CSS** (`hub_template.html` 331~474행)
- **ACTION**: 삭제 9줄 · 스코프 제거 13곳 · 418~419행 병합·교체 (§2.5 표 그대로)
- **GOTCHA**: 450행 → 418행 병합 시 `padding:0 8px 0 24px` 의 **우측 8** 을 유지할 것 —
  어긋나면 접힘 카드에 가로 스크롤바가 생긴다(T25-193 이 무는 것)
- **VALIDATE**: 헤드리스 렌더로 `.sessions` 의 `scrollWidth == clientWidth` 확인

**Task 6 — 이슈 1 JS + 문서** (`hub_template.html` · `hub/README.md`)
- **ACTION**: §2.5 JS 표의 삭제 전부 + 머리 주석 개정 + README 367~374 교체
- **GOTCHA**: 패널 IIFE 2382행 가드도 함께 삭제. `PROJECT_PATH_ATTRIBUTE`(1117행)는
  참조 수를 `grep -c` 로 확인한 뒤 결정(TR8)
- **VALIDATE**: `bash tests/run.sh` 전체 (가드 8개 개정 반영)

**Task 7 — 이슈 2** (`hub_template.html` 284행 뒤 · `hub/README.md` 358~359행 뒤)
- **ACTION**: CSS 규칙 1개(`.card:has(.session-row.card-open)::before{…}`) + 주석(§3.4 그대로) · README 1문장
- **GOTCHA**: 424행 `.session-row.card-open` 과 `applyOpenCardMarking` 은 **손대지 말 것**(SM1·SM2 — JS 변경 0).
  사용자가 안 C/D 를 골랐으면 §3.6 의 규칙으로 대체(D 는 TR2 이후에만 셀렉터가 맞는다)
- **VALIDATE**: 신규 T25-199 · T25-108·110·107 통과 확인 · 목업 `mock2-sec1~6` 과 실 hub.html 육안
  대조(라이트·다크·320px·작업중 카드·카드 자체 열림)

**Task 8 — 래칫·원장**
- **ACTION**: `mutations.tsv` 변조행 9건 추가 + **T25-164·T25-166 면제행 → 변조행 승급(2건)** + 삭제분
  제거 · `LEDGER_MUTATION_ROW_FLOOR` · `SOURCE_GUARD_ID_FLOOR` 갱신(현재 값은 `readonly` 선언에서 읽는다)
- **GOTCHA**: **`T99-6` 행의 sed 리터럴(현재 `LEDGER_MUTATION_ROW_FLOOR(93`)을 같은 커밋에서
  함께 옮길 것** — 그 행의 사유 칼럼이 이 함정을 5회 재현 기록으로 갖고 있다
- **VALIDATE**: `bash tests/run.sh --only T37` · 그 뒤 전체

---

## 9. 사용자 승인이 필요한 핵심 결정

**승인 완료 (1회차 목업으로) — 건드리지 않는다**
- 이슈 1 — 안 A(토글·localStorage 완전 삭제, 트리 상시, 340px 유지). 선택 사항 X4 는 기본값 「표시 유지」.
- 이슈 4 — 판정 `percent>=100 AND Δ > stale_after_ms`, 동작 「클릭 불가 + 패널 사유」(안 A).

**승인 완료 (2회차 목업으로, 2026-09-11)**
- **이슈 2 — 미채택.** 네 안 전부 거부, **현재 상태 유지**. §3 은 기록으로만 남고 구현 범위에서
  빠진다(§3 머리말·§8·§7.2 참조). `:has()` 는 이 파일에 도입되지 않는다.
- **이슈 3 — 툴팁 제거(갈래 A) + 툴팁만 읽던 서버 필드 4개
  (`prompt_preview`·`result_preview`·`phase_title`·`state`) 제거.** 갈래 B(메타)·C(휴리스틱)는
  23건 실측 문자열로 기각됐다(목업 마지막 절).

- **선택 항목 E(§4.5) — 채택.** 실패한 에이전트 칩에 `--attention` 쌍 색 상태 + `sr-only`
  " 실패" 텍스트. 근거: `.agent-chip` 의 상태 CSS 는 `.agent-chip-running`(514행) 하나이고
  **error 상태 CSS 가 없어** 실패 칩과 성공 칩이 똑같이 보인다(실측 450건 중 error 33건 = 7.3%)
  — 툴팁을 제거하면 실패를 알 수단이 화면에서 완전히 사라진다. 그 대가로 `state` 필드가 남아
  이슈 3 의 뷰 필드 제거가 **4개 → 3개**가 된다.

**승인 대기 — 없다. 구현 착수 가능.**

---

## 10. 리스크와 대안

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| **이슈 4 오탐** — 살아 있는 대시보드가 사라진다 | 낮음 | **높음** (이슈 4 보다 나쁜 회귀) | 4겹(§5.2): 100% 연접 · Δ 여유 37배 · `log commit` 의 mtime 갱신 · 엄격한 `>`. 실측 6건에서 살아 있는 세션은 두 조건 모두 미달 |
| **이슈 4 임계값 근거 부족** — step/log 간격 분포를 측정할 수 없었다 | 확실 (측정 불가) | 중 | §1.5 에 한계를 명시. 100% 연접이 이 불확실성을 대신 흡수한다(결정 FT3) |
| **T25-191 개정이 접힘 픽셀 동일 계약의 역가드를 잃는다** | 확실 | 중 | 그 계약 자체가 사라진다(접힘 상태가 없다). 대신 T25-196(잔재 0)·T25-197(스코프 없는 규칙 존재)·T25-198(`border-top` 0)이 세 방향에서 되돌림을 막는다 |
| **340px 안에 보이는 세션이 줄어든다** | 확실 | 낮음 | 실측 4개 카드 중 1개에서 1개 감소(§1.1). X4 로 복구 가능 |
| **레일이 `card-working` bloom 위에서 3:1 아래로 내려간다**(펄스 정점 근사 2.4:1 라이트 · 2.5:1 다크) | 중 | 낮음 | 3px 불투명 면 + 행 면색이 함께 답한다 · 모션 유무가 판별자(SM5). 목업 sec3·sec4 에서 식별 확인 |
| **`:has()` 미지원 브라우저** | 낮음(Baseline 2023) | 낮음 | 규칙이 무시돼 현재 동작(행 면색만)으로 폴백 — 깨지지 않는다. 주석에 기록(SM6) |
| **무관한 툴팁이 함께 죽는다**(같은 `.agent-chip` 클래스의 `agent_runs` 칩 등) | 중 | 중(조용한 회귀) | T25-201 이 `renderAgentChip`·session-id·발췌 툴팁의 존재와 `data-tooltip="` 정확히 16건을 고정. Task 1 GOTCHA |
| **툴팁 제거로 error 사유가 화면에서 사라진다** | 확실 | 낮음 | 지금도 error 칩 툴팁은 형제와 같은 프롬프트만 보여 정보량 0 이었다(§1.4). 선택 항목 E 가 「어느 칩이 실패했나」를 색으로 부분 보완한다 |
| **서버 필드 제거가 테스트 약 20건을 건드린다** | 확실 | 낮음 | 전부 기계적 삭제·담체 교체(§7.2-A). 신설 2건 + T25-202 가 되돌림을 막는다 |
| **래칫 상수 3종의 동시 갱신 누락** | 중 | 낮음 (fail-loud) | Task 8 의 GOTCHA. T37-15 가 잡는다 |

### 검토했으나 채택하지 않은 대안

1. **이슈 3 — 워크플로우 `script` 를 파싱해 에이전트별 프롬프트를 복원한다.**
   기각: `label` 4종 전부가 `script` 에 리터럴로 없다(배열 파생). 임의 JS/TS 소스를
   파싱해야 하고, 그것은 「우리가 소유하지 않는 외부 형식」(결정 WF2)에 대한 의존을 한 겹
   더 깊게 만든다. 파일 크기도 7.6KB~24KB 로 hub.html 인라인 대상이 아니다.
2. **이슈 3 — 메인 세션 transcript 에서 Task 호출의 전문 프롬프트를 조인한다.**
   기각: `agentId` 가 어떤 transcript 에도 없다(실측 0건) — 조인 키가 존재하지 않는다.
   `hub_transcript.py` 라는 I/O 선례는 있지만 키 없이는 무의미하다.
3. **이슈 1 — 340px 를 420px 로 올려 트리에서도 세션 3개를 보인다.**
   기각: 3열 그리드에서 한 화면의 프로젝트 수가 줄어 「훑기」라는 허브의 목적과 상충한다.
   결정 W2 의 고정값 근거를 바꾸는 변경이라 별도 승인 사안으로 §9-1 에 올렸다.
4. **이슈 2 — JS 로 조상 카드에 클래스를 얹는다(1회차 RM1: 같은 `card-open` / 대안: 2종 클래스).**
   기각: 같은 클래스면 CSS 가 「카드 자체 열림」과 「조상」을 구분할 수 없어 SM1(조상은 면색 없이)이
   불가능하고, 2종이면 OC8 의 적용 지점이 실제로 둘이 된다. `:has()` 는 둘 다 피한다(SM2) — JS 0.
5. **이슈 4 — `dashboard_key` 를 서버에서 None 으로 만든다.**
   기각: `hub_model._register_dashboard` 와의 불변식(「등록은 거부되는데 키는 채워진다」를
   금지하는 `_session_dashboard_key` 의 `UNSET_SOURCE_PATH` 가드)을 다시 따져야 하고,
   사유 분기가 `SESSION_NO_DASHBOARD_REASON`(대시보드가 없다)으로 잘못 낙착한다.
   서버는 사실(bool)만, 클릭 가능 여부는 클라이언트(결정 GN4 관례).
6. **이슈 2 — 안 A(카드 테두리만) · C(헤더 밑줄) · D(연결선 경로).** A 기각(hover·`card-working` 과
   동색 1.00:1 — 목업 sec3·sec6 에서 실제로 사라진다). C·D 는 대안으로 남긴다(§3.3 표) — C 는 약하고
   D 는 스크롤에 잘리며 `color-mix()` 의존이 늘어난다.
7. **이슈 3 — 갈래 B(메타 툴팁: model·소요·토큰·도구 호출).** 기각: 읽을 수 있고 고유하지만 「얼마나」에만
   답한다 — 사용자의 조건(「필요 정보」 = 무슨 작업)을 채우지 못하고, 툴팁 UI·서버 필드 5개·포맷 함수를
   유지하는 비용이 든다. 실제 문자열 23건은 목업 sec8.
8. **이슈 3 — 갈래 C(잘린 JSON 의 첫 문자열 리프 추출).** 기각: 350건 중 254건(72.6%)이 10자 이상을
   내지만 그중 「결과」로 읽히는 것은 4건 중 1건 — 첫 키가 `question`(입력 재진술)·`lens`(관점)·
   `severity` 인 스키마가 많고 어떤 키가 결과인지 알 방법이 없다. 마크다운은 첫 줄이 거의 항상 절 제목.
9. **이슈 3 — 툴팁만 지우고 서버 필드는 남긴다.** 기각(기본값): `hub_template.html` 참조 0건 필드를
   남기는 것은 §19 선례(미사용 필드 4개 제거)와 어긋나고, 인라인 자유 텍스트(시크릿 유출 표면)를 이유
   없이 유지한다. 사용자가 원하면 §9-2 에서 선택할 수 있다.

---

## 11. NOT Building (범위 밖 — 명시)

- 카드 고정 높이 340px 의 값 변경 (§9-1 승인 사안)
- 프로젝트 카드 수준의 세대 판정 변경 (`ProjectView.tier1_is_previous_task` · GN1~GN7 그대로)
- 끝난 대시보드에 대한 「그래도 열기」 우회 수단 (FT5)
- 대시보드 파일에 완료/종료 상태 필드 신설 (`commands/dashboard.md` 데이터 모델 변경)
- `lastToolName` · `lastToolSummary` · `error` · `durationMs` · `toolCalls` · `tokens` · `model` 수집 — 갈래 B·C 기각(§4.2)으로 전부 범위 밖
- 툴팁 싱글턴(`#dzh-tooltip`) · `.tooltip` CSS · 워크플로우 칩 외 트리거 17개 — 전부 무변경(WT2)
- 실패한 에이전트의 사유 문구(`error` 값) 표시 — 어느 안에서도 화면에 싣지 않는다(WT7 — E 는 색 상태만)
- `WorkflowAgentView.index` 제거 — 이번 변경 전부터 클라이언트 참조 0건인 필드다. 내 변경이 만든 고아가 아니므로 언급만 한다(karpathy #3); 지우려면 별건
- `.card.card-open` 면색·테두리 변경 · `.session-row.card-open` 면색 변경 (SM1) · `card-working` 모션 변경 (SM5) · `applyOpenCardMarking` 변경 (SM2)
- 툴팁 위치 계산(`tooltipPosition`) · 트리 기하(V2~V12 의 px 값) 변경
- 허브 서버·수집기·사용량 패널 전반

---

## 12. Mandatory Reading (구현 전 필독)

| 우선 | 파일 | 행 | 왜 |
|---|---|---|---|
| P0 | `hub/bin/hub_template.html` | 255~360 | 카드 CSS 전체 + `card-open`·`card-working` 대비 근거 주석 |
| P0 | `hub/bin/hub_template.html` | 400~480 | 세션·트리 CSS + V2~V12 기하 주석 (링·스코프 제거의 무대) |
| P0 | `hub/bin/hub_template.html` | 1380~1400, 1490~1580 | `renderAgentChip`(**건드리지 않는** 다른 툴팁) · 워크플로우 칩 3함수 + `sessionRowAttributes` |
| P0 | `hub/bin/hub_template.html` | 2280~2310 | `applyOpenCardMarking` + OC8 주석 — **손대지 않음을 확인**(SM2) |
| P1 | `tests/hub/test_hub_workflow.py` | 전체 | 삭제·개정 대상 테스트(§7.2-A) |
| P0 | `hub/bin/hub_workflow.py` | 1~60 | **계약 A** (스크럽→절단 순서) — 위반하면 시크릿 유출 |
| P0 | `hub/bin/hub_session.py` | 90~135, 357~392 | `SessionView` 필드 규약 + `compute_session_view` |
| P1 | `hub/bin/hub_project.py` | 300~346 | `is_tier1_from_previous_task`(미러 대상) + `_session_dashboard_key` |
| P1 | `tests/run.sh` | 8395~8580 | T25-182~T25-195 — 이번에 개정할 가드 본문 |
| P1 | `tests/run.sh` | 7840~7860, 7948~7990 | T25-159 · T25-164 (awk 앵커) |
| P1 | `tests/mutations.tsv` | 헤더 + `T99-6` 행 | 래칫 3종의 동시 갱신 규약 |
| P2 | `docs/prps/hub-unified-card-tree-ui.md` | U1~U14 | 번복 대상 결정의 원문 |
| P2 | `docs/prps/hub-tree-view-and-signal-fixes.md` | V1~V12 | 유지 대상 트리 기하의 원문 |
| P2 | `docs/prps/hub-panel-empty-state-and-open-card.md` | OC1~OC11 | 표시·빈 상태 불변식 |
| P2 | `commands/dashboard.md` | 42, 61, 540 | 「100% = 완료」·`log commit`·30분 RECENT |

---

## 13. Acceptance Criteria

- [x] 이슈 1·4 승인(1회차) · 이슈 2 **미채택**(현재 상태 유지) · 이슈 3 제거 + 필드 제거 승인(2회차) · **선택 항목 E 채택**
- [x] 승인 대기 항목 없음 — 구현 착수 가능
- [ ] 선택 항목 E 반영: `.agent-chip-error` CSS 1규칙 + `renderWorkflowChip` 의 `errorClass` + `sr-only` " 실패" · `state` 필드·`_metadata_field`·`WORKFLOW_METADATA_MAX_CHARS`·`WORKFLOW_STATE_ERROR` **유지**
- [ ] Task 1~6 + 8 완료, 순서 준수 (3 → 4 → 1). **Task 7(이슈 2)은 보류** — 이슈 2 미채택
- [ ] `bash tests/run.sh` 통과 (개정 가드 11개 — T25-164·166 포함 — + 신규 가드 **8개** 반영. T25-199 는 신설하지 않는다)
- [ ] `python3 -m unittest discover -s tests/hub -t .` 통과 (신규 13건 = 이슈 4 11건 + 이슈 3 2건 · 이슈 3 삭제 약 11건·개정 약 7건 반영)
- [ ] 실 hub.html 에서 무관한 툴팁 4종(`agent_runs` 칩 · 발췌 · short_id · stale 배지)이 여전히 뜬다 (육안 + T25-201)
- [ ] `python3 -m unittest discover -s tests/commands -t .` 통과
- [ ] `python3 -m py_compile hub/bin/*.py` · `bash -n install.sh && bash -n hub/install.sh`
- [ ] 실데이터 재수집 후 §7.4 육안 항목 전부 확인 — 특히 **d0e8c16b(살아 있는 세션)의
      대시보드가 여전히 열린다**
- [ ] `hub/README.md` 갱신 + 머리 주석 갱신 + 결정 번호(TR·WT·FT)를 해당 코드 주석에 기록. **RM·SM 은 미채택이라 코드에 기록하지 않는다**
- [ ] 번복한 결정(U1~U7·U9 · TT1~TT8 · WF9 의 툴팁 부분)의 번복 근거가 코드 주석과 이 PRP 양쪽에 있다. RM1~RM6·SM1~SM7 은 **구현되지 않았으므로 코드 주석 대상이 아니다** — 기록은 이 PRP §3 뿐이다
- [ ] 상시 컨텍스트(T26) 무영향 확인 — 이번 변경은 `hub/`·`tests/`·`docs/` 범위다

---

## 14. Notes

- **`/prp-plan` 스킬의 구조를 따르되 산출 경로는 지시받은 `docs/prps/hub-ui-4-issues.md`**
  다(`.claude/PRPs/plans/` 를 쓰지 않았다 — `rules/workflow/role-separation.md` 1단계 규약).
- **2회차(이슈 2·3 재설계, fable — model-routing 기준 4)**: 이슈 1·4 의 서술과 결정 번호는 1회차 원문
  그대로다. 이슈 2 는 RM1~RM6 → SM1~SM7(행 면색 유지 · 카드는 `:has()` 로 다른 채널 · JS 0), 이슈 3 은
  TT1~TT8 → WT1~WT8(툴팁 제거 · 뷰 필드 4개 제거). 2회차 목업은 이슈 1 의 §2.5 를 프로그램으로 적용한
  CSS 위에 그렸다(`build_mockup2.py` 가 각 치환의 1회 매치를 단언한다). 2회차 신뢰도: 이슈 2 는 규칙
  1개라 9, 이슈 3 은 삭제라 8(테스트 개정 폭이 넓지만 기계적).
- **관찰(이슈 1 범위 — 결정은 바꾸지 않고 기록만)**: 이슈 1 은 332행 `.card.card-expanded
  .sessions{overflow-y:visible}` 을 삭제해 `ul.sessions` 가 항상 스크롤 컨테이너가 된다. 그러면 첫
  세션의 위쪽 레일 연장 `li:first-child::before{top:-10px;height:28px}`(V12, 「루트 본문까지 레일
  연장」)의 **위 10px 이 `overflow-y:auto` 에 잘린다** — 2회차 목업으로 확인했다(`mock2-v12.png` 는
  -10px 그대로라 육안 차이가 작고, `mock2-v12b.png` 는 -40px 로 과장해 잘림 여부를 판정: auto 에서는
  ul 위 경계에서 끊기고 visible 에서는 루트 본문을 뚫는다). 화면 효과는 루트 본문과 첫 갈고리 사이의
  레일이 10px 짧아지는 것(ul 의 `margin-top:10px` 구간이 빈다). 고치려면 `.sessions` 의 위 10px 을
  margin 에서 padding 으로 옮기는 식의 이슈 1 변경이 필요하고 T25-193 정규식(`margin:10px -Npx 0`)도
  따라간다 — **이슈 1 결정은 승인된 대로 두고, 구현 시 사용자에게 고칠지 묻는다.**
- **관찰(이슈 1 범위)**: §2.2 는 「13개 규칙에서 접두 삭제」라 적었으나 `.card.card-expanded ` 접두를
  가진 **셀렉터 줄은 23개**(콤마로 이어진 셀렉터 목록 포함)이고, 450·451·351행 삭제분을 빼면 **20개**다
  — §2.5 표의 행 범위(452~459 · 461~465 · 468~474 = 8+5+7)와 일치한다. 구현자는 셀렉터 단위로 전부
  제거한다(2회차 목업 생성기의 `re.subn` 실측).
- **단일 통과 신뢰도(1회차): 7/10.** 이슈 3·4 는 순수 함수 + 실측 케이스가 갖춰져 높다(8~9).
  이슈 1 이 신뢰도를 끌어내린다(6) — 가드 8개 개정이 걸려 있고, T25-193 정규식 개정과
  T25-191 역방향 삭제는 구현 중 실제 출력을 보며 조정해야 한다.
- 이 PRP 는 메인 세션이 넘긴 진단 중 **2건을 정정한다**: ① 툴팁 절단은 일어나지 않는다
  (실측 0/23) — 재배치의 근거는 절단 구제가 아니라 읽기 순서다. ② 접힘이 숨기는
  `.session-tier1` 은 tier1 보유 6개 세션의 진행률만이 아니라 **모든 세션 행의 한 줄**이다
  (`renderSessionProgress` 가 「대시보드 없음」도 그 div 에 넣는다). 또 **1건을 추가한다**:
  `error` 필드(33/33 보유)가 후보 목록에 없었으나 error 항목 툴팁의 정보량 0 을 메우는
  가장 값진 추가다.
- 실측 재현 스크립트·목업 생성기는 세션 스크래치패드에 있다(저장소에 커밋하지 않는다):
  `analyze.py` · `measure_tooltip.py` · `measure_rows.py` · `build_mockup.py`.
