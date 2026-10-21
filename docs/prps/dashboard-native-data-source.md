# 대시보드 기록을 「호스트 기본 데이터 + JSONL 한 줄」로 옮긴다 (PRP)

> 결정 접두: **DN**(Dashboard Native). `grep -rhoE "결정 DN[0-9]+" docs/prps/*.md` 로 미사용임을 확인했다(2026-09-21).
> 상태: **설계안 — 사용자 승인 대기.** 기준 커밋 `9b6d1a1`(`main`, 작업 트리 clean). 구현 코드는 이 문서에 없다.
> 수치는 전부 이 세션의 실측이며, 실측이 아닌 값은 **「추정」**으로 표시했다. 사전 감사(메인 세션)의 수치와
> 다른 곳은 그 사실을 적었다.
>
> 목업(「현재 | 제안」 나란히, 라이트·다크, 860px·549px):
> `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/768e8a38-ef92-4a4b-a356-e96efbcc80f2/scratchpad/dashboard-native-data-source-mock.html`
> (PNG: 같은 디렉터리의 `dashboard-native-data-source-mock.png`). 이 목업의 iframe 내용은 실제 템플릿을
> 0바이트 변경 없이 코드로 렌더한 산출물이라(§12), 보이는 것이 곧 나올 것이다.

---

## 0. 한눈에

| 항목 | 값 |
|------|-----|
| 사용자 질문 | 대시보드를 그리는 데이터를 오케스트레이터가 **직접 만드는** 대신 Claude Code 가 **자동으로 남기는** 데이터로 대체할 수 있는가. 큰 차이가 없다면 기본 데이터를 쓰자 |
| 답 | **부분 대체.** 대체 가능한 것(단계 실행·시각·모델·생존·팬아웃)은 허브에 **이미 끝나 있다**(§1.1). 남은 것(작업 제목·계획된 단계·검수 판정·요약 한 줄)은 의미 판단이라 호스트 기록에 없다(§2.1 — todo 파일 0건, 자동 제목 신뢰 불가). **그런데 비용의 정체는 그 데이터가 아니라 그것을 기록하는 메커니즘이다** — 60KB 절차 문서의 재주입과 60KB HTML 에 대한 DOM 수술(§2). 그래서 이 설계는 데이터 출처가 아니라 **기록 메커니즘**을 바꾼다 |
| 핵심 결정 | 상태 = `.claude/dashboards/<세션 ID>.jsonl` **append 한 줄**(DN2) · 화면 = 헬퍼(코드)가 **전체 재렌더**(DN3) · 오케스트레이터의 의무 = **`log` 이벤트 5~8건**(단계 상태는 파생, DN4) · 프로토콜은 **상시 규칙**에 두고 `Skill(dashboard)` 재주입 **0회**(DN7) · 허브·템플릿 **0변경**(DN11, 힌트 문자열 2줄 제외) |
| 목표 수치 | `commands/dashboard.md` 59,851자 → **≤ 4,000자(−93%)** · 상시 규칙 문단 2,335B → **1,432B(실측)** · 스킬 주입 세션당 1.8회 → **0회** · 대시보드 갱신 도구 호출 세션당 ≈60회(Edit 48 + Bash 12) → **≤ 10회(Bash 만, 추정)** |
| 잃는 것 | §3 표. 폐기 7항목(자동 발행·로컬 서버·`serve`·`impl` 패널·매트릭스 모드·LEGACY 쓰기 모드·디스패치 시점 상세). 검수 판정·상세 마크업·필터·접기·테마·PiP(허브 URL 경유)는 유지 |
| 폭발 반경 | commands/ 4파일 · rules 1문단 · README 수치 2곳+서술 · `tests/run.sh` 155건 중 **≈60~70건 삭제/재작성 + T34 재작성**(추정, §7.2) · `tests/commands` 56건 중 ≈2/3 재작성 · `tests/hub` 계약 테스트 5건 재작성 · **허브 코드·허브 유닛 테스트 879건 0변경** |
| 권고 | **구현할 가치가 있다 — 이 문서의 1단계 범위까지.** 허브가 JSONL 을 직접 읽고 HTML 파이프라인을 버리는 2단계(DN14)는 별도 PRP(그 회차는 model-routing 기준 2 에 해당해 fable 대상) |

---

## 1. 요구사항 요약

`/dashboard` 는 메인 세션이 작업 진행(제목·단계·검수 결과·커밋)을 프로젝트 로컬 HTML 로 남기는 스킬이다.
사용자는 "그 데이터를 직접 만들지 말고 Claude 가 자동으로 남기는 데이터로 대체할 수 있는지, 큰 차이가
없다면 토큰·메모리 효율을 위해 기본 데이터를 쓰자"고 물었고, 사전 감사 결과를 보고 「진행」을 승인했다.
이 문서는 **무엇을 어떻게 바꿀지**를 정한다. 오케스트레이터가 요구한 5개 질문에 정면으로 답한다 —
Q1 비용 비대칭 해결 여부(§2.3·§6.4) · Q2 잃는 것 전수(§3) · Q3 마이그레이션(§8) · Q4 폭발 반경(§7.2) ·
Q5 더 싼 대안 기각(§9).

### 1.1 이미 끝난 것 (재조사하지 않았다 — 반증 없음)

허브는 호스트가 남기는 세 출처를 이미 소비한다: `~/.claude/sessions/<pid>.json`(생존·busy/idle) →
`hub_live_session*.py`, `subagents/agent-<id>.meta.json`(agentType·description·model) →
`hub_subagent*.py`, `agent-<id>.jsonl` mtime(생존 신호) → 커밋 `9b6d1a1`. `SubagentRunView` 가
실행 1건당 단계(`PHASE_BY_AGENT_TYPE`)·실행중·시작/종료·제목·모델을 들고 있고 카드가 실행 칩으로
그린다(`hub_template.html` `renderAgentRunList`). **따라서 이 설계의 대상은 허브가 아니라 `/dashboard`
쪽이다** — 오케스트레이터가 무엇을 언제 어떻게 기록하는가.

---

## 2. 실측 — 무엇이 비용인가

### 2.1 호출 실측 (이 세션, `~/.claude/projects/-Users-dev-private-project-coding-harness/*.jsonl` 27개, `tool_use` id 로 중복 제거)

| 항목 | 실측 | 사전 감사 대비 |
|------|-----:|------|
| `Skill(dashboard)` 호출 | **49회**, 인자 **전부 `init`**, 최대 9회/세션 | 48회(21파일) → 파일 27개로 늘어 +1. 해석 동일 — `step`·`log` 재호출은 0건, 전부 compact 뒤의 재`init` |
| 대시보드 파일 `Edit`/`Write` | **1,298회 / 882,618자** | 1,327 / 1,040,655 — 경로 필터 차이(`.claude/` 하위 `.html`/`.json` 만). 같은 자릿수 |
| Edit 종류(old_string 기준) | 단계 줄 283 · 진행률 200 · 갱신 시각 279 · 로그 prepend 221 · `<details>` 접기 74 · 포트 각인 68 · impl 줄 40 · init-values Write 27 · 기타 118 | — |
| 로그 종류(new_string 기준) | impl 71 · **pass 41 · fail 37** · commit 42 | — |
| `init` 단계 목록(49건 중 파싱 34건) | 표준 전체 `설계\|승인\|구현\|검수` **18** · 표준 축약 `구현\|검수` **10** · 비표준 선형 3(`원인 분석\|…`, `조사\|설계\|…`, `설계\|구현\|검수`) · **그룹(매트릭스) 3** | 15건은 멀티라인 인자로 파싱 실패 — 비율은 파싱분 기준 |
| 헬퍼 Bash | 337회 (grep 심 중 `dz-step-` 22 · `dz-log` 23 …) | 334 |
| 경로 모드 | **09-14 이후 세션 7개 전부 SESSION(`init-check` 출력 27/27)**, LEGACY 쓰기 0. 그 전 `RECENT`/`STALE` 31건은 세션별 파일(ST) 배포 전 | 신규 |
| `TodoWrite` 사용 | **0회**, `~/.claude/todos/` 부재 | 신규 — 「계획된 단계 목록」의 네이티브 후보가 없음을 확정 |
| 네이티브 제목 | `custom-title.json` 1/24 세션(사용자 수동 rename) · `sessions/*.json` 의 `name`/`nameSource`(user\|derived) 는 살아있는 세션만 | 신규 — 대체 불가. `last-prompt` 발췌(허브가 이미 표시)만 근사치 |
| `ANCHOR-FAIL` | 실 발생 1건(구세대 템플릿의 `dz-updated` 앵커) | 참고 |

### 2.2 문서 크기 추이 (`git show <h>:commands/dashboard.md | wc -c`)

| 날짜 | 커밋 | 바이트 | 비고 |
|------|------|-------:|------|
| 08-05 | 8d61d32 | 26,630 | 창립 |
| 08-19 | 821cc65 | 113,179 | 최대 |
| 08-24 | 2e08a37 | 79,829 | **슬림화 커밋**(템플릿·근거 외부화, "주입 58k→37k 토큰") |
| 09-03 | 1887f2e | 89,886 | +10K — 워크트리 관문·세션별 파일 |
| 09-11 | 172538e | **98,885** | +19,056B(**+24%**) / 18일 — 재발행·소유권·상호작용 잠금 등 5개 PRP |

슬림화는 한 번 됐고, **되돌아갔다.** 절차를 남겨두는 한 기능마다 절차 본문이 붙는다(§9-(a)).

### 2.3 비용의 해석 — Q1 「5:1 비대칭을 설계가 해결하는가」에 대한 정면 답

재주입 2,872,848자 : 편집 1,040,655자 ≈ 2.8:1(사전 감사 수치), 청구 가중으로는 재주입이 더 크다 —
주입된 문서는 세션이 끝날 때까지 **매 턴 cache read** 로 다시 읽힌다(`rules/common/performance.md`:
cache_read ≈ 70%). 지출 비중의 유일한 실측은 슬림화 PRP 의 "58K 토큰일 때 세션 지출의 21~24%" 다.
지금 문서는 ≈35K 토큰이라 선형 스케일하면 **≈13~15%(추정)** — 이것이 「하지 않았을 때」의 값이다.

**상태 표현만 JSONL 로 바꾸면 이 비용은 남는다.** 문서가 50KB 인 채 "JSONL 을 append 하라"고 적어도,
compact 뒤 `init` 이 그 50KB 를 다시 주입한다. 그래서 이 설계는 세 겹으로 자른다:

1. **절차를 코드로 옮긴다(DN3)** — grep 앵커·Edit 치환·이스케이프·상세 마크업·펼침 회수·진행률 산술·
   소유권 검증·불변식 10개는 LLM 이 읽고 따르는 텍스트가 아니라 `dashboard_render.py` 의 함수가 된다.
   문서에서 **55,000자**(§6.4 표)가 사라지는 근거다.
2. **프로토콜을 상시 규칙에 둔다(DN7)** — 남는 "무엇을 언제 기록하나" 표(≤1,500B)는
   `rules/workflow/role-separation.md` 에 있다. 규칙은 compact 뒤에도 시스템 프롬프트로 다시 들어오므로
   `Skill(dashboard)` 을 부를 이유가 **구조적으로** 사라진다 — 오늘 48회 전부가 compact 재`init` 이었다.
3. **기록 의무를 줄인다(DN4)** — 디스패치·결과 시점의 `step active "…"`(283회의 대부분)는 허브 실행
   칩과 중복이라 삭제한다. 남는 것은 오케스트레이터만 아는 사실 5~8건이다.

결과: 세션당 대시보드 귀속 토큰은 Bash 한 줄 × ≤10회(≈2,000자, 추정)로 내려간다 — 오늘의
재주입 63K 토큰 + cache-read 꼬리 + 편집 출력 ≈11K 토큰 대비 **>95% 감소(추정)**. 이 추정은 구현
뒤 §2.1 과 같은 스크립트로 재측정한다(§7.4).

---

## 3. 네이티브 대체 판정표 — Q2 「무엇을 잃는가」 (전수)

| 대시보드 요소 | 네이티브 출처 | 판정 | 근거·대체 |
|---|---|---|---|
| 단계 실행 여부·시각·모델(설계/구현/검수) | `meta.json` + 훅 → `SubagentRunView` | **완전 대체(이미 됨)** | 허브 실행 칩. 대시보드는 이를 다시 그리지 않는다(DN13) |
| 구현 세부 작업(동시 디스패치) 패널 `impl` | 동시 실행 = 실행 칩 2개 이상 | **폐기** | 27세션 impl 줄 Edit 40회. DU1 이 전제(병렬 10~15개)가 이 저장소에서 거짓임을 실측했다. 템플릿의 `#dz-impl-card` 는 비어 있어 `:has()` 로 숨는다(오늘과 같은 기본 상태) |
| 디스패치·결과 시점의 단계 상세(`step n active "…디스패치 — 범위"`) | `meta.description` | **폐기** | 허브가 같은 문자열(description)을 이미 보인다. 결과 요약은 `log impl '<요약>'` 의 `.lead` 로 남는다 |
| 활성 단계의 한 줄 상세(`.step-detail`) | — | **축소 → 파생** | 가장 최근 로그 요약을 자동으로 채운다(DN6). 허브 카드의 `tier1-active` 줄이 계속 살아 있다 |
| 작업 제목 | 없음(§2.1) | **유지** | `init '<제목>'` 1회 |
| 계획된 단계 목록·진행률 분모 | 없음(todo 0건) | **유지** | `init` 2번째 인자(표준 문자열 2종은 규칙에 있다). 비표준 목록은 `step <n> <state>` 로 명시 갱신 가능 |
| 매트릭스(그룹×단계) 모드 | 동시 실행 칩 | **폐기** | 34건 중 3건. 허브 `hub_template` 은 `matrix_done` 을 렌더하지 않는다(hub_parse 주석 실측). `hub_parse._CELL_LINE_PATTERN` 은 구파일 호환으로 그대로 둔다 |
| 검수 PASS/FAIL·요약·회차 | 없음 | **유지**(회차는 자동) | `log pass\|fail '<요약>' ['<상세>']`. 회차 = 누적 pass/fail 수(DN5) |
| 상세 마크업(문단·목록·인라인 코드, 불변식 10) | — | **유지(코드로)** | `render_detail_html` — 문서의 4단계 규칙을 함수로 옮긴다. 결정성이 텍스트 준수에서 코드로 바뀐다 |
| 커밋 기록 | `.git/logs/HEAD`(reflog) | **유지(`log commit` 1줄)** | 42회 사용. reflog 파생은 2단계 후보(DN13) — 허브에 새 외부 형식을 들이는 일이라 이번엔 안 한다 |
| 필터(전체/구현/검수)·접기·최신 3건 펼침 | — | **유지** | 템플릿 불변. 펼침은 렌더러가 최신 3건에 `open` |
| 다크 테마·임베드 모드·상호작용 잠금·`.lead` 툴팁 | — | **유지** | 템플릿 불변 |
| PiP 플로팅 | — | **축소** | 대시보드 자체 http.server(8791~8793)가 사라진다. 허브가 서빙하는 `/project/<key>/dashboard.html` 을 **최상위 탭**으로 열면 `isServed && !isEmbedded` 라 오늘과 같이 동작한다. 허브 없는 환경은 `file://`(포커스 시 갱신)만 |
| 자동 발행 티어(포트 스캔·기동·포트 각인·`log commit` 자동 종료·focus-tab AppleScript·브라우저 열기) | 허브가 상주 서버 | **폐기** | 문서 14,072자 + 헬퍼 ≈150줄. 49회 `init` 마다 탭을 열거나 앞으로 가져오는 부작용이 사라진다. 기록 프로토콜에는 UI 부작용이 없어야 한다 |
| `serve` | 허브 | **폐기** | 5,186자. 위와 같은 이유 |
| 소유권 가드(`data-owner-token`·FOREIGN/SKIP·0단계 확인 질문) | 경로 = 세션 ID | **축소** | SESSION 모드는 항상 MINE(문서 자신의 서술). 어휘·확인 절차·랜덤 토큰을 지운다. 속성 값은 렌더러가 세션 ID 앞 8자리로 계속 채운다(템플릿·`reissue` 계약 안정) |
| LEGACY 단일 파일 **쓰기** 모드 | — | **폐기** | 09-14 이후 0회(§2.1). `CLAUDE_CODE_SESSION_ID` 가 UUID 가 아니면 헬퍼가 `NOSESSION` 을 내고 오케스트레이터는 한 줄 보고 후 생략. 허브의 레거시 **읽기**는 그대로다 |
| `reissue` | — | **유지(`render`)** | JSONL → HTML 전체 재렌더가 곧 재발행이다. 추출·보존 검사 200줄이 필요 없어진다 |
| 7일 리텐션(ST5) | — | **유지** | 패턴에 `*.jsonl` 추가 |
| `on`/`off` | — | **유지(헬퍼 `switch`)** | 판정(`DISABLED`)은 헬퍼가 한다 — 오케스트레이터가 `settings.local.json` 을 Read·파싱하지 않는다 |
| 허브의 작업 시작 경계(RL8 사이드카 `{토큰}.init-values.json` mtime) | — | **유지(무변경)** | 헬퍼 `init` 이 같은 이름의 사이드카를 계속 쓴다(DN11) |
| 보고 최소화 절(2,276자) | — | **축소(1줄)** | 성공 무보고, 실패·`NOSESSION`·`DISABLED` 1줄 |
| `--round N` | — | **폐기(자동)** | DN5 |
| 「이전 대시보드 덮어쓰기」 확인(AskUserQuestion) | — | **폐기** | LEGACY 모드와 함께 사라진다 |

---

## 4. 설계 결정과 근거 (DN1~DN16)

### DN1 — 대상은 허브가 아니라 오케스트레이터의 **기록 메커니즘**이다
§1.1·§2. 네이티브 대체가 가능한 요소는 허브에 이미 있고, 남은 요소는 네이티브에 없다. 남은 요소의
비용은 데이터가 아니라 메커니즘이다. **기각**: 「완전 네이티브(오케스트레이터 기록 0)」 — 검수 판정·
제목·계획을 잃고(§3), 허브 카드가 이를 추정하려면 휴리스틱(「implementer 시작 = 승인」)이 필요하다.
판정은 이 워크플로우에서 가장 중요한 의미 상태(「검수 통과 전 커밋 금지」, 3회차 상한)다.

### DN2 — 상태의 단일 출처를 DOM 에서 **append-only JSONL** 로 바꾼다
`.claude/dashboards/<세션 ID>.jsonl`. HTML 은 그 파일의 **파생 산출물**이며 매 이벤트마다 통째로
다시 그린다. `session-dashboard.md` 결정 2("상태 파일을 두지 않는다 — DOM 이 곧 상태")와
`hub-dashboard.md` 쟁점 1(b) 기각을 **공개적으로 번복**한다. 그 결정들이 막으려던 것은 「LLM 이 HTML
과 JSON 두 곳에 같은 정보를 각각 쓰는 이중 진실」이었다. 여기서는 LLM 이 쓰는 곳이 JSONL **하나**이고
HTML 은 코드가 만든 빌드 산출물이라 어느 쪽이 진실인지 정할 규칙이 필요 없다(빌드 산출물은 진실이
아니다). 부수 효과: `reissue` 가 재렌더 한 줄로 환원되고, 2단계에서 허브가 기계 판독할 형식이 생긴다.
**기각**: 「DOM 유지 + 헬퍼가 in-place 수술」(§9-(b)).

### DN3 — 실행 주체를 LLM 에서 **코드(`dashboard_helper.py`/`dashboard_render.py`)** 로 옮긴다
`session-dashboard.md` 결정 1("실행 주체는 LLM, 셸 스크립트를 만들지 않는다")과
`dashboard-worktree-bash-gate.md` D2("grep 은 얇은 심, DOM 셀렉터는 문서에만")를 번복한다. D2 의
전제는 "문서가 실행되므로 셀렉터가 문서에 있어야 읽기 좋다"였다. 문서가 실행되지 않으면 그 소비자가
없다. 셀렉터의 유일한 **생산자**는 렌더러, 유일한 **소비자**는 `hub_parse` 가 되고, 둘은
`test_hub_dashboard_contract.py` 가 렌더 결과에 파서 정규식을 직접 대어 묶는다(오늘의 문서 예시 줄
추출보다 강한 계약). 결정 1 의 근거였던 "셸 자산은 `COMMANDS_FILE_COUNT`·jq 의존"은 이미 헬퍼
도입(관문 PRP)으로 소멸했다.

### DN4 — 오케스트레이터의 기록 의무는 `log` 이벤트 5~8건이다. **단계 상태는 파생한다**
오늘의 트리거 표 8행 중 4행(디스패치 직전·결과 직후 `step active "…"`, 구현 완료·검수 결과의
`step done|wait`)은 허브 실행 칩 또는 같은 순간의 `log` 와 중복이다. 새 규칙: `log` 의 종류가 단계
전이를 **함의**한다 — `design`→설계 완료, `approve`→승인 완료, `impl`→구현 완료, `pass`→전부 완료,
`fail`→마지막 단계 대기 + 직전 단계(구현) 재개. 완료 표시는 그 단계까지 앞 단계를 모두 완료로 본다.
활성 = 첫 미완료 단계. 비표준 목록(`원인 분석|…`)만 `step <n> done|active|wait` 로 명시한다(같은
reducer 의 한 갈래 — 두 메커니즘이 아니다). 축약기는 순수 함수 `derive_phase_states` 하나다.
**기각**: `--phase n` 플래그(종류가 배지 라벨도 결정하므로 종류 쪽이 자기 설명적이다).

### DN5 — 검수 회차는 **자동 번호**다
`--round` 를 없앤다. 회차 = 그 항목까지의 pass/fail 누적 수. 첫 검수부터 `R1` 이 붙는다(오늘은 인자
생략 시 배지 없음 — 작은 화면 변화, §12).
**개정(docs/prps/hub-dashboard-multi-task.md MT4):** 회차는 **작업별** 누적 수다 — 이름표(`--task`)가 붙은 작업은 자기 pass/fail 만 센다. 이름표 없는 기록만 있는 세션(작업 하나)은 이 결정 그대로다.

### DN6 — 활성 단계의 `.step-detail` = **가장 최근 로그 요약**
허브 카드의 `tier1-active` 줄("구현 — <상세>")이 오케스트레이터의 추가 호출 0 으로 계속 정보를 갖는다.
디스패치 서술은 실행 칩이 대신한다.

### DN7 — 프로토콜은 **상시 규칙**에 두고 `Skill(dashboard)` 은 기록 경로에서 부르지 않는다
`rules/workflow/role-separation.md` 의 대시보드 문단(2,335B, 120~141행)을 §6.3 의 표(1,432B 실측)로 바꾼다.
규칙은 compact 뒤에도 재주입되므로 "절차가 컨텍스트에서 빠져 `init` 이 스킬을 다시 부른다"는 경로가
없어진다. `dashboard.md` 는 `/dashboard on|off` 를 사용자가 직접 칠 때와 사람이 읽을 때만 로드된다.
**기각**: 「dashboard.md 를 4,000자로 줄이고 계속 스킬로 부른다」 — compact 마다 ≈1,500 토큰이 다시
들어온다. 작지만 0 이 아니고, 규칙 문단은 어차피 존재해야 한다(트리거 표는 규칙의 몫).

### DN8 — 자동 발행·로컬 http.server·포트 각인·자동 종료·focus-tab·`serve` 를 **폐기**한다
허브가 상주 서버다(포트 8794 고정, 요청 구동 수집). 대시보드가 자기 서버를 띄우던 설계는 허브 이전
것이다. 남는 폴백은 `file://`(오늘의 티어 2). PiP 는 허브 URL 최상위 탭에서 그대로 된다(§3). 템플릿의
힌트 문자열 2줄(381·454행, `/dashboard serve`·`8791` 안내)만 허브 안내로 바꾼다 — **이것이 템플릿의
유일한 변경**이다. **기각**: `serve` 만 수동 opt-in 으로 남기기 — 5,186자 + `serve-prepare`·포트
검증·`trap`·`pkill` 복제 규칙이 문서에 남아 목표 수치(≤4,000자)를 넘긴다. 허브 없는 사용자의 PiP 손실은
승인 항목(§11-1)으로 올린다.

### DN9 — LEGACY 단일 파일 **쓰기** 모드를 폐기한다
근거 §2.1. `CLAUDE_CODE_SESSION_ID` 가 UUID 가 아니면 `NOSESSION`. `init-check`(`ABSENT|RECENT|STALE`),
확인 질문, `os.urandom` 토큰, FOREIGN/SKIP 어휘가 사라진다. 허브 `read_tier1_snapshot`(레거시 읽기)은
무변경 — 옛 파일은 계속 보인다. **기각**: 폴백 유지 — 코드 2경로·문서 1,900자를 실측 0회 경로에 쓴다.

### DN10 — 매트릭스(그룹) 모드를 폐기한다
§3. 병렬 트랙의 진행은 허브 실행 칩(실행 1건당 1줄, 실행 중 표시)이 이미 보여준다. 렌더러는 선형만
만든다. `hub_parse` 의 셀 패턴은 구파일 호환으로 남긴다(허브 무변경 원칙).

### DN11 — 1단계에서 **허브는 0변경**이다. 사이드카는 이름·의미 그대로 유지한다
헬퍼 `init` 이 `{세션 ID 앞 8자리}.init-values.json` 을 오늘과 같은 위치에 쓴다(내용은 init 이벤트
JSON — 허브는 mtime 만 본다, RL8). 이로써 `hub_parse`·`hub_collect`·`hub_project`·`hub_session`·
`hub_template`·허브 유닛 879건·T25-222 ⑨⑩ 이 무변경이다. **기각**: 사이드카를 JSONL 첫 줄 시각으로
대체 — 더 깔끔하지만 허브 3모듈 + 유닛 ≈10건 + T25-222 를 건드린다. 그 방향은 2단계(DN14)의 첫
걸음이라 거기서 한다. 「수술적 변경」 원칙.

### DN12 — 인자 전달은 **홑따옴표 argv** 다
관문 PRP M13 실측: `python3 <경로> init '제목 with $HOME and \`date\`' '설계|승인|구현|검수'` 가 관문을
통과하고 `$HOME`·백틱이 확장되지 않는다. 규칙 문구: "인자는 홑따옴표로 감싼다. 본문에 `'` 가 필요하면
`’` 로 바꾼다". 상세의 줄바꿈은 따옴표 안에서 유효하다(관문이 거부하는 것은 heredoc 이다). 헬퍼는
`shell=True` 를 쓰지 않으며 argv 를 그대로 JSONL 에 넣고 **렌더 시점에만** 이스케이프한다(관문 PRP D3
의 "삽입 시점 이스케이프 1회" 원칙 유지). **기각**: `Write` 로 JSON 파일을 쓰고 경로를 넘기는 D3 방식 —
호출마다 도구 2회. D3 가 그 방식을 고른 이유(`steps_block_lines` 의 여러 줄 HTML)는 렌더러가 마크업을
만들면서 사라졌다.

### DN13 — 두 화면의 분업: 대시보드 = 오케스트레이터의 **선언**, 허브 = 호스트 기록의 **관측**
대시보드 HTML 은 JSONL 만 그린다 — 렌더러가 자기 세션의 `meta.json` 을 읽어 단계에 실행 정보를
얹지 않는다. 같은 파생을 두 곳(허브 `summarize_agent_runs` 와 렌더러)이 하면 드리프트한다. 병합 뷰는
허브의 몫이며 2단계에서 JSONL 을 허브가 읽으면 카드에 판정 배지가 생긴다. 커밋의 reflog 파생도 같은
이유로 2단계 후보다.

### DN14 — 2단계(별도 PRP)의 경계
(a) `hub_parse` 에 JSONL 파서 → `SessionView` 에 최근 판정/로그 → 카드 배지 「검수 R2 PASS」;
(b) 허브가 세션 페이지를 JSONL + 실행 뷰로 직접 렌더 → HTML 파일 생성·`Tier1Snapshot` HTML 파싱·템플릿
폴링 제거; (c) 커밋 reflog. (b) 는 `Tier1Snapshot` 을 소비하는 hub_project(테스트 73/85 건이 tier1 을
만짐)·hub_session·hub_model·hub_server·hub_template 을 가로지르는 데이터 모델 개편이다 — model-routing
기준 2. 이번 회차에 섞지 않는다.

### DN15 — 보고는 1줄 규칙으로 축소
`init` 성공: 보고 없음(URL·토큰 줄의 존재 이유였던 「토큰 생존」이 DN9 로 사라졌다). `OK` 가 아닌
출력(`NOSESSION`·`DISABLED`·`NOTEMPLATE`·`MKDIR-FAILED`·`NOINIT`)은 그 한 줄을 착수 보고에 남기고
이후 호출을 생략한다 — `role-separation.md` 「호출을 생략했거나 실패했으면 한 줄 남긴다」 그대로.

### DN16 — `on`/`off` 판정·쓰기를 헬퍼 `switch` 로 옮긴다
`.claude/settings.local.json` 을 `json.loads` → 필드 하나 설정 → `json.dumps(indent=2)` 원자적 쓰기.
파싱 실패 시 `INVALID-SETTINGS` 를 내고 **쓰지 않는다**(권한 허용 목록 보호 — 오늘 절차의 핵심
불변). 다른 필드는 값·유무 그대로다(공백 서식은 바뀔 수 있다 — Claude Code 자신도 이 파일을
재직렬화한다). 문서의 `## \`on\` / \`off\`` 절은 T23-5~10 이 요구하는 문장을 헬퍼의 보증으로 그대로
담는다(T23 무변경).

---

## 5. 영향 범위 (파일 목록)

| 파일 | 조작 | 이유 |
|------|------|------|
| `commands/dashboard.md` | **재작성** (98,885B → ≤ 4,000자) | §6.4 |
| `commands/dashboard_helper.py` | 재작성 (449줄 → ≈220줄, 추정) | 서브커맨드 10→5(DN3·DN8·DN9). `_atomic_write_text`·리텐션·`sys.dont_write_bytecode` 유지 |
| `commands/dashboard_render.py` | 재작성 (474줄 → ≈350줄, 추정) | 이벤트 파서·축약기·로그/상세 렌더 추가, 추출·보존검사·`InitValues`·`pick_port` 삭제. `PublishedValues`·`render_reissue`·`_replace_unique`·앵커 9종·`escape_for_dom` **그대로 재사용**(§12 실측) |
| `commands/dashboard_template.html` | 문자열 2줄 | DN8 힌트 문구. 마크업·CSS·JS 구조 0변경 |
| `rules/workflow/role-separation.md` | 문단 1개 교체 | DN7 — §6.3 문안. 상시 컨텍스트 **감소** |
| `README.md` | 수치 2곳 + 서술 | `실측 56,455B` 2곳(T26-2·3), commands 표의 `dashboard` 줄 수·설명, `/dashboard` 문단(174~183행), 트리 주석(364~367행) |
| `commands/hub.md` | 1문장 | 305행 "commands/dashboard.md 의 DOM 계약" → 계약 생산자를 `dashboard_render.py` 로 |
| `tests/run.sh` | T22 정리 · T34 재작성 · T25-6 재앵커 · `DASHBOARD_MD_BUDGET_BYTES` 하향(T22-163) | §7.2 |
| `tests/mutations.tsv` | 행 삭제·재조준 | §7.2 |
| `tests/commands/test_dashboard_helper.py` | 재작성 | §7.1 |
| `tests/hub/test_hub_dashboard_contract.py` | 예시 출처 교체 | 문서 예시 줄 → 렌더러 출력(DN3) |
| `docs/prps/dashboard-native-data-source.md` | 신설 | 이 문서 |
| `docs/prps/dashboard-rationale.md` | 머리 2줄(선택) | "절차 근거 다수는 DN 으로 대체됨" 배너. 본문은 손대지 않는다 |

**무변경(의도적)**: `hub/**` 전체 · `tests/hub/*`(계약 테스트 1개 제외) · `install.sh`(`COMMANDS_FILE_COUNT=12`
그대로 — 파일 추가·삭제 없음) · `removals.txt`(툼스톤 불필요) · `hub/README.md`(사이드카 서술이 그대로
참) · `docs/prps/session-dashboard.md`(역사적 스냅샷 — 슬림화 PRP §5.3 선례).

---

## 6. 파일 구조 · 데이터 모델 · 인터페이스

### 6.1 런타임 배치 (프로젝트 로컬)

```
<project>/.claude/dashboards/
  <세션 ID>.jsonl                 # 상태의 단일 출처 (append-only, 세션 1개 = 파일 1개)
  <세션 ID>.html                  # 파생 산출물 — 매 이벤트마다 전체 재렌더 (경로 규칙 ST1 그대로)
  <세션 ID 앞 8자리>.init-values.json   # 허브 RL8 사이드카 — 이름·mtime 의미 그대로 (DN11)
```

리텐션: `init` 이 이 디렉터리의 7일 초과 `*.html`·`*.jsonl`·`*.init-values.json` 을 최선 노력으로
지운다(ST5 확장). `init` 은 같은 세션의 이전 작업 기록을 **보존하지 않는다**(오늘과 같다 — JSONL 을
새로 쓰고 사이드카 mtime 이 새 경계가 된다).

### 6.2 데이터 모델 — JSONL 이벤트 (한 줄 = JSON object, UTF-8, `ensure_ascii=False`)

```
DashboardEvent
  time_ms : int                       # 헬퍼가 append 시점에 찍는다. 렌더는 이 값만 쓴다(결정적 재렌더)
  kind    : "init" | "design" | "approve" | "impl" | "pass" | "fail" | "commit" | "note" | "step"
  # kind == "init"
  title   : str                       # 원문(이스케이프는 렌더 시점)
  phases  : list[str]                 # 순서 있음, len >= 1. 예 ["설계","승인","구현","검수"]
  project : str                       # cwd 마지막 세그먼트 — 재렌더가 cwd 에 의존하지 않게 저장
  # kind in design|approve|impl|pass|fail|commit|note
  summary : str                       # .lead
  detail  : str                       # 선택. 빈 문자열 = "(상세 없음)". 문단/목록/백틱 규칙은 렌더가 적용
  # kind == "step"  (비표준 단계 목록 전용 명시 갱신)
  index   : int                       # 1-based
  state   : "done" | "active" | "wait"
```

- 렌더러는 **줄 단위 fail-open** 이다 — 파싱 안 되는 줄·모르는 `kind`·타입이 어긋난 필드는 그 줄만
  건너뛴다(허브 파서들의 계약 B 와 같은 태도). `init` 이 하나도 없으면 렌더 불가 → `NOINIT`.
  `init` 이 여러 개면 **마지막 `init` 이후**만 유효하다(그 앞은 `init` 이 파일을 새로 쓰므로 실제로는
  생기지 않지만, 손으로 이어 붙인 파일에도 결정적으로 답한다).
- 표본 크기: `fail` 1줄 265B(§12). 세션당 5~10줄 → 3KB 미만.

### 6.3 인터페이스 ① — 상시 규칙 문단 (`rules/workflow/role-separation.md`, 오늘 2,335B 문단(120~141행)을 통째로 교체)

```markdown
- **전체 경로·축약 경로 작업은 진행 상황을 대시보드에 기록한다** — `Skill(dashboard)` 을 부르지
  않는다. 아래 헬퍼를 Bash 로 직접 부른다(인자는 홑따옴표. 본문의 `'` 는 `’` 로 바꾼다):
  `if [ -f "$HOME/.claude/commands/dashboard_helper.py" ]; then python3 -- "$HOME/.claude/commands/dashboard_helper.py" <서브커맨드> …; else python3 -- .claude/commands/dashboard_helper.py <서브커맨드> …; fi`

  | 시점 | 호출 |
  |------|------|
  | 착수 보고 | `init '<제목>' '설계|승인|구현|검수'` (축약 경로: `'구현|검수'`) |
  | PRP 작성 완료 | `log design '<요약>'` |
  | 사용자 승인 수령 | `log approve '<요약>'` |
  | 구현 완료(회차마다) | `log impl '<요약>' ['<상세>']` |
  | 검수 결과 | `log pass '<요약>' ['<상세>']` 또는 `log fail …` — 회차는 자동 |
  | 커밋·푸시 | `log commit '<커밋 제목>'` |

  단계 상태·진행률·활성 단계 상세는 위 기록에서 파생된다 — 서브에이전트 디스패치·결과 시점에는
  아무것도 기록하지 않는다(허브가 호스트 기록으로 그린다). 출력이 `OK` 가 아니면(`NOSESSION`·
  `DISABLED`·`NOTEMPLATE`·`NOINIT`…) 그 한 줄만 착수 보고에 남기고 이후 호출을 생략한다.
  끄기: `/dashboard off` — `.claude/settings.local.json` 의 `dashboard_enabled`(나만·커밋 안 됨).
```

**1,432B(실측 — 위 블록을 UTF-8 로 잰 값), −903B.** T25-222 ⑬·T23-7 이 요구하는 `dashboard_enabled`·`.claude/settings.local.json` 리터럴을
포함한다. 대시보드 파일에 접근하는 Bash 는 이 런처 한 형태뿐이며 `$HOME` 외 변수를 쓰지 않는다(T33 규약).

### 6.4 인터페이스 ② — `commands/dashboard.md` (≤ 4,000자) 절 구성과 삭제 항목

| 오늘 절 | 자 수 | 새 문서 | 어디로 갔나 |
|---|---:|---:|---|
| 데이터 모델 — DOM 상 표현 규격(불변식 1~10·셀렉터 표·로그 스키마·갱신 모드·폴링 계약·잠금 계약) | 18,710 | ≈600 (JSONL 스키마 표) | 셀렉터·불변식 → `dashboard_render.py` 상수·`test_hub_dashboard_contract.py`. 폴링·PiP·잠금 계약 → 템플릿 자체 + 기존 PRP 링크 1줄 |
| 자동 발행 | 14,072 | 0 | 폐기(DN8) |
| `init` | 11,977 | ≈250 | 헬퍼 1줄 + 출력 어휘 |
| `impl` | 9,561 | 0 | 폐기 |
| `log` | 9,163 | ≈350 | 종류 표 + 함의하는 단계 전이 1줄. 상세 마크업 규칙 → `render_detail_html` |
| `step` | 5,416 | ≈150 | 명시 갱신 1줄 |
| `serve` | 5,186 | 0 | 폐기 |
| 진행 시각화 규격(그룹×단계) | 4,455 | 0 | 폐기(DN10) |
| `on`/`off` | 2,565 | ≈450 | 헬퍼 `switch` + T23 보증 문장 3개 |
| CLAUDE.md 트리거 | 2,472 | 0 | 규칙 문단(§6.3) |
| 헬퍼 스크립트 표 | 2,370 | ≈700 | 새 표(G2) |
| 보고 최소화 | 2,276 | ≈120 | DN15 1줄 |
| 호출 규약 | 2,211 | ≈350 | 축약 |
| 소유권 검증 | 1,925 | 0 | 폐기(DN9) |
| `reissue` | 1,891 | ≈120 | `render` |
| 대시보드 경로 규칙 | 1,831 | ≈250 | `.claude/dashboards/<세션 ID>.*`·`NOSESSION`·사이드카 1줄(T25-158·T25-222 ⑨ 리터럴 유지) |
| 템플릿 파일 | 1,015 | ≈150 | 해결 순서 1줄 |
| 로그 UI 규격 | 502 | 0 | 템플릿 자체 |
| frontmatter | — | ≈400 | `argument-hint` 에 `\| on \| off` 유지(T23-6) |
| **합계** | **98,885B / 59,851자** | **≈3,900자** | T22-163 의 `DASHBOARD_MD_BUDGET_BYTES`(현재 98,885 = 실측과 같은 순수 래칫)를 새 실측값으로 내려 잠근다. 원장 행 T22-163(+10B 뮤테이션)은 새 문서의 문구로 재조준한다 |

### 6.5 인터페이스 ③ — 헬퍼 서브커맨드 (G2 표 · T34 가 디스패치와 대조한다)

> 각주(2026-09-21, 검수 1회차 H1) — 아래 표의 `init`\|`log`\|`step` 행에 `ANCHOR-FAIL <횟수> <앵커>`
> 가 빠져 있었다(네 서브커맨드 모두 `_render_dashboard_html` 을 거쳐 이 실패를 낼 수 있다). 설계
> 단계부터 있던 갭이 구현 검수에서 드러나 여기서 정정한다.

| 서브커맨드 | 인자 | 출력(폐쇄 어휘) | 한다 |
|---|---|---|---|
| `init` | `'<제목>' '<단계1\|단계2\|…>'` | `OK <html 절대경로>` \| `NOSESSION` \| `DISABLED` \| `NOTEMPLATE` \| `MKDIR-FAILED` \| `ANCHOR-FAIL <횟수> <앵커>` | 리텐션 → JSONL 새로 쓰기(init 1줄) → 사이드카 쓰기 → 렌더·원자적 쓰기 |
| `log` | `<design\|approve\|impl\|pass\|fail\|commit\|note> '<요약>' ['<상세>']` | `OK` \| `NOSESSION` \| `DISABLED` \| `NOINIT` \| `BADKIND` \| `NOTEMPLATE` \| `ANCHOR-FAIL <횟수> <앵커>` | append 1줄 → 렌더 |
| `step` | `<n> <done\|active\|wait>` | `OK` \| `NOSESSION` \| `DISABLED` \| `NOINIT` \| `BADINDEX` \| `NOTEMPLATE` \| `ANCHOR-FAIL <횟수> <앵커>` | append 1줄 → 렌더 |
| `render` | — | `OK` \| `NOSESSION` \| `NOINIT` \| `NOTEMPLATE` \| `ANCHOR-FAIL <횟수> <앵커>` | JSONL → HTML 재렌더(옛 `reissue`) |
| `switch` | `on\|off` | `ON` \| `OFF` \| `INVALID-SETTINGS` | `.claude/settings.local.json` 의 `dashboard_enabled` |

- 삭제: `path` `exists` `init-check` `init-copy` `init-render` `reissue` `grep` `port-scan` `serve-prepare`
  `focus-tab`(10종 전부). 어휘 삭제: `SESSION ABSENT RECENT STALE VALUES-INVALID REUSE FREE NONE EXISTS
  FOCUSED NOTFOUND UNSUPPORTED PREPARE-FAIL SAME EXTRACT-FAIL VERIFY-FAIL`.
- `DISABLED` 판정은 `read_dashboard_enabled` 와 같은 페일 방향(파일·필드 없음·파싱 실패 = 켜짐)이다.
- 모든 쓰기는 `_atomic_write_text`(현행 유지). `shell=True`·`subprocess` 사용 0.

### 6.6 인터페이스 ④ — `commands/dashboard_render.py` (★순수) 공개 함수

```python
@dataclass(frozen=True)
class DashboardEvent: ...                                   # §6.2 그대로. phases 는 tuple[str, ...]

def parse_event_lines(text: str) -> tuple[DashboardEvent, ...]:
    """JSONL 본문 → 이벤트 열. 줄 단위 fail-open. 마지막 init 이후만 돌려준다."""

def derive_phase_states(phases: tuple[str, ...], events: tuple[DashboardEvent, ...]) -> tuple[str, ...]:
    """DN4 축약기. 각 단계의 'done'|'active'|'wait'. 활성은 첫 미완료 하나뿐."""

def render_detail_html(detail: str) -> str:
    """상세 마크업 규칙(이스케이프 → 빈 줄로 블록 → `- ` 블록은 <ul>, 그 밖은 <p>, 단일 비목록 블록은
    맨 텍스트 → 블록 안에서만 백틱 짝짓기 → 태그 사이 개행 없음). 빈 입력은 '(상세 없음)'."""

def render_log_entry_lines(events: tuple[DashboardEvent, ...]) -> list[str]:
    """최신이 위. data-seq 1부터, 최신 3건만 <details open>. pass/fail 에 누적 회차 R{n}."""

def build_published_values(events: tuple[DashboardEvent, ...], session_id: str) -> PublishedValues:
    """이벤트 → 앵커 9종 값. impl 슬롯은 None(카드 비움). owner_token = 세션 ID 앞 8자리, server_port = ''."""

def render_from_events(template_text: str, events: tuple[DashboardEvent, ...], session_id: str) -> str:
    """= render_reissue(template_text, build_published_values(events, session_id)). AnchorMismatch 전파."""

def resolve_dashboard_paths(session_id: str | None) -> DashboardPaths | None:
    """UUID 면 (jsonl, html, sidecar) 경로 3종, 아니면 None(→ NOSESSION). LEGACY 경로 없음."""
```

유지: `PublishedValues`, `render_reissue`, `_replace_unique`, `ANCHOR_*` 9종, `escape_for_dom`, `AnchorMismatch`.
삭제: `InitValues`·`parse_init_values`·`render_dashboard`·`extract_published_values` 와 `_extract_*`·
`_slice_block`·`verify_preserved`·`pick_port`·`ValuesInvalid`·`ExtractFailed`·`VerifyFailed`·
`LEGACY_DASHBOARD_PATH`. 파일은 800줄 상한 안이고(추정 350줄) 순수/IO 쌍 관례를 유지한다.

**렌더가 만드는 줄 형태(허브 파서 계약 — 오늘과 문자 단위로 같다):**
`      <li id="dz-step-{n}" class="{state}"><span class="num">{n}</span>{이름}<span class="chip">{라벨}</span><span class="step-detail">{상세}</span></li>`
한 줄에 하나(구 불변식 2·3), 속성 순서·공백 1칸(정규 속성 순서). `hub_parse._STEP_LINE_PATTERN` 이 그대로 읽는다(§12 실측).

### 6.7 종류 → 표현 대응 (템플릿 무변경 안에서)

| kind | `data-kind` | 배지 class | 라벨 | 함의하는 전이 |
|---|---|---|---|---|
| design | `note` | `.badge.impl` | 설계 | 「설계」까지 완료 |
| approve | `note` | `.badge.impl` | 승인 | 「승인」까지 완료 |
| impl | `impl` | `.badge.impl` | 구현 | 「구현」까지 완료 |
| pass | `review` | `.badge.pass` | 검수 PASS | 전부 완료(100%) |
| fail | `review` | `.badge.fail` | 검수 FAIL | 마지막 단계 대기, 직전 단계 재개 |
| commit | `commit` | `.badge.commit` | 커밋 | 없음 |
| note | `note` | `.badge.impl` | 메모 | 없음 |

`note` 는 템플릿 필터에서 「전체」에만 보인다(예비 값의 원래 용도). 새 CSS 클래스를 만들지 않으므로
템플릿이 바뀌지 않는다 — 설계·승인 배지가 「구현」과 같은 파랑 틴트인 것은 의도된 타협(§12 목업에서
확인 가능).

---

## 7. 테스트 계획과 폭발 반경 — Q4

### 7.1 순수 로직 단위 테스트 (`tests/commands/test_dashboard_helper.py` 재편)

| 대상 | 케이스 |
|---|---|
| `derive_phase_states` | 표준 전체(init→design→approve→impl→pass = 4/4) · 축약(init→impl→pass) · **fail 회귀**(impl→fail→ 구현 active·검수 wait → impl→pass) · 앞 단계 생략(`impl` 만 기록해도 설계·승인 완료) · 비표준 목록에 `step` 명시(done/active/wait 각 의미) · 목록에 없는 단계명 종류는 무시 · 이벤트 0건 = 첫 단계 active · 같은 이벤트 반복 멱등 |
| `render_detail_html` | 빈 문자열 → `(상세 없음)` · 단일 문단 = 맨 텍스트 · 문단 2개 → `<p>` · `- ` 블록 → `<ul>` · 혼합 · 백틱 짝짓기가 **블록 경계를 넘지 않음** · 홀수 백틱은 글자 그대로 · `<`·`&` 이스케이프가 마크업보다 먼저 · 공백만 있는 줄도 블록 경계 · 결과에 `>\n<` 없음(구 불변식 10) |
| `render_log_entry_lines` | 순서(최신 위)·`data-seq` 연속·최신 3건만 `open`·pass/fail 만 `R{n}`·회차 누적·종류→배지 대응 7종·요약 이스케이프·`</ul>` 되붙임 |
| `parse_event_lines` | 깨진 줄 건너뜀 · 모르는 kind 건너뜀 · 타입 어긋남(요약이 수) 건너뜀 · init 없음 → 빈 튜플 · init 2회 → 마지막 이후만 |
| `build_published_values`/`render_from_events` | 진행률 `M/N · P%` 와 `width:P%` 일치 · impl 슬롯 None → 템플릿 기본 앵커 유지 · owner_token = 앞 8자리 · 갱신 시각 = 마지막 이벤트 |
| `resolve_dashboard_paths` | UUID 소문자만 통과 · `..`·`/` 거부 · None |
| 헬퍼 I/O(샌드박스 cwd·`HOME`) | `NOSESSION`(변수 부재) · `DISABLED`(settings false) · `NOINIT`(jsonl 없이 log) · `BADKIND` · `BADINDEX` · 리텐션이 8일 파일만 지움(3패턴) · 원자적 쓰기(임시 파일 잔재 없음) · `switch` 가 다른 필드 보존·파싱 실패 시 무기록 |
| 생산자↔소비자 계약(`tests/hub/test_hub_dashboard_contract.py` 재작성) | 표본 이벤트 3세트를 렌더 → `hub_parse.parse_dashboard_html` 이 제목·진행률·단계 상태·상세를 그대로 읽는다 · 역방향 2건(속성 순서 뒤집기·공백 2칸)은 렌더러 출력 줄에 적용해 파서가 거부함을 확인(현행 두 테스트의 입력 출처만 교체) |

오늘 56건 중 유지 ≈10(경로·이스케이프·원자적 쓰기), 삭제 ≈36(추출·보존검사·재발행 호환·`pick_port`·
`InitValues`), 신규 ≈30(추정).

### 7.2 폭발 반경 산정 (실측 + 추정)

| 대상 | 실측 | 재작성·삭제 추정 | 방법 |
|---|---|---|---|
| `tests/run.sh` T22 `test_dashboard_template_integrity` | 1,674줄, **155개 서브체크 ID** | **A** `$dashboard_command_file` 직접 17건 → 삭제/재작성 · **B** 합본+문서 문구(한글·`/dashboard`·`{포트}`) 39건 → 삭제/재작성 · **C** 합본+마크업 토큰 71건 → 대부분 유지, **8~12건 검토**(문서에만 있던 토큰: `dz-cell-` 예시·`dz-step-{n}`·`/dashboard serve` 등) · **D** 헬퍼/렌더 2건 재작성 · **E** 템플릿 전용 13건 유지 · **F** 무관 13건 | 각 ID 의 첫 등장~다음 ID 구간에서 참조 파일 변수와 grep 패턴 분류(스크래치패드 스크립트) |
| `tests/run.sh` T25 `test_hub_docs_and_constants` | 대시보드 파일 참조 ID 13개 | **T25-6** 재앵커(`<li id="dz-step-…">` 문구 → 렌더러 줄 템플릿 상수) · T25-136·145·158·222 는 리터럴 유지로 통과 · T25-143(`trap`/`http.server` 서술 검사) **검토** | ID 본문 직접 확인 |
| `tests/run.sh` T34 | 147줄 | 재작성(서브커맨드 5·어휘 12·URL 템플릿 검사 삭제) | — |
| `tests/run.sh` T33·T23·T26 | — | T33 무변경(새 문서 코드 블록도 `$HOME` 만) · T23 무변경(보증 문장 유지) · T26 README 수치 2곳 갱신, 상수는 하향 가능 | — |
| `tests/run.sh` 합계 | 13,813줄 | **≈700~900줄 변경(5~7%)** | 추정 |
| `tests/mutations.tsv` | 524행 · `commands/dashboard.md` 대상 7행 · 헬퍼/렌더 2행 · 템플릿 7행 | 문서 7행 재조준/삭제 · T22-172(보존 토큰) 삭제 · T22-171(원자적 쓰기) 유지 · 삭제되는 T22 ID 의 self 행 ≈50 삭제 | — |
| 래칫 | `SOURCE_GUARD_ID_FLOOR=495`(현 569) · `LEDGER_MUTATION_ROW_FLOOR=100` · `LEDGER_EXEMPT_ROW_RATCHET=382` · `NOTE_FAILURE_ID_LESS_RATCHET=110` | 서브체크 ID ≈60 감소 → **≈509 ≥ 495(여유 ≈14, 좁다)**. 밑돌면 하한을 내리는 커밋에 사유를 적는다(T26 관용구) | 구현 중 실측 필수 |
| `tests/commands` | 56건 | ≈2/3 재작성 | §7.1 |
| `tests/hub` | 879건 | **계약 테스트 5건 재작성, 나머지 0** | 허브 0변경(DN11) |
| 문서 | README 4곳 · hub.md 1문장 · rationale 배너(선택) | — | — |

**총량(추정)**: ≈2,000~2,500줄 변경. 헬퍼·렌더 −450/+350, dashboard.md −1,300/+80, run.sh ≈800,
tests/commands ≈900, rules·README ≈60.

### 7.3 정본 검증 명령 (변경 없음)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

주의: 이 저장소 안에서 `install.sh --scope project` 금지(T31-4), `$HOME` 대상 실설치 금지,
`python3 hub/bin/hub.py collect` 금지(실제 hub.html 을 덮어쓴다). 검증은 위 명령만으로 한다.

### 7.4 사후 측정 (구현 완료 기준의 일부)

배포 뒤 세션 5개 이상 지난 시점에 §2.1 의 스크립트를 다시 돌려 (i) `Skill(dashboard)` 호출 수 =
`/dashboard on|off` 사용자 호출만 (ii) 대시보드 파일 Edit/Write = 0 (iii) 헬퍼 Bash ≤ 10/작업 을
확인한다. 이 셋이 이 설계의 성공 기준이다.

---

## 8. 마이그레이션 — Q3

**한 PR, 커밋 3개(각각 §7.3 전부 통과)**:

1. `commands/` 4파일 + `tests/commands` + `tests/hub/test_hub_dashboard_contract.py` — 새 메커니즘이
   동작하고 허브 파서가 산출물을 읽는다.
2. `rules/workflow/role-separation.md` 문단 + README(수치·서술) + `tests/run.sh`(T22 정리·T34·T25-6·
   `DASHBOARD_MD_BUDGET_BYTES`) + `tests/mutations.tsv` — 프로토콜 전환과 가드 정리.
3. `commands/hub.md` 1문장 + `dashboard-rationale.md` 배너(선택).

**기존 산출물**: 이미 발행된 `.claude/dashboards/*.html`·`.claude/dashboard.html` 은 변환하지 않는다.
허브는 오늘의 파서로 계속 읽고(0변경), 세션별 파일은 7일 리텐션이 지운다. 레거시 단일 파일은 아무도
지우지 않는다(오늘과 같다).

**전환 중인 세션(알려진 1회성 단절)**: 배포 전에 시작해 옛 절차를 컨텍스트에 든 세션은 `grep`
서브커맨드가 없어 `unknown subcommand` 를 받는다 → 규칙에 따라 한 줄 보고 후 생략. 새 프로토콜로
이어가려면 `init` 부터(그 작업의 옛 로그는 새 파일에 없다). 호환 심을 남기지 않는다 — 배포 시점에
살아 있는 세션 수만큼만 발생하는 단절이다.

**설치**: `install.sh --scope user` 는 사용자가 직접 실행한다(이 저장소의 규칙). 4파일 모두 `commands/`
에 그대로 있어 파일 수·툼스톤 변화가 없다.

---

## 9. 더 싼 대안을 먼저 기각한다 — Q5

**(a) `dashboard.md` 를 그냥 압축한다 — 기각.** 이미 한 번 했다(08-24, 113K→80K). 18일 뒤 99K(§2.2).
절차가 남아 있는 한 기능마다 절차 본문이 붙는다 — 관문 대응·세션별 파일·소유권·재발행·잠금 PRP 가
각각 +2~10K 를 더했다. 또 하한이 있다: 절차 절(`init`·`log`·`impl`·`step`·`serve`·자동 발행)만 55K 로,
LLM 이 실행해야 하는 결정 내용이라 산문 압축으로는 줄지 않는다. 무엇보다 문서가 얼마든 compact 뒤
`init` 마다 다시 들어온다 — 구조적 비용은 문서 크기와 무관하게 남는다.

**(b) 절차를 헬퍼로 더 밀어넣되 DOM 을 상태로 유지한다(헬퍼가 in-place 수술) — 기각.** 문서 절감은
이 설계와 비슷하게 얻는다. 그러나 (i) 60KB HTML 에서 줄을 찾아 바꾸는 앵커·추출 기계가 필요하다 —
오늘 `extract_published_values` 200줄이 정확히 그것이고 `EXTRACT-FAIL`·`VERIFY-FAIL` 경로를 낳았다.
append + 전체 재렌더는 "출력 = f(이벤트 목록)"이라 검증할 것이 함수 하나다. (ii) 소유권 토큰 각인·읽기
왕복이 남는다. (iii) 2단계에서 허브가 읽을 기계 판독 형식이 생기지 않는다. DN2 가 이 안을 지배한다.

**(c) 아무것도 안 한다 — 기각(단, 조건부 유효).** 남는 비용: 세션당 재주입 1.8회 × 35K 토큰 + 매 턴
cache read 꼬리 + 편집 출력 ≈11K 토큰 — 유일한 지출 비중 실측(21~24% @58K)을 스케일하면 세션 지출의
**≈13~15%(추정)**. 사용자 조건 "큰 차이가 없다면"에서 이 차이는 크다. 다만 사용자가 ≈15% 지출보다
회귀 위험 0 을 택한다면 (c) 는 정당하다 — 그 판단은 §11 로 올린다.

**(d) 완전 네이티브(오케스트레이터 기록 0) — 1단계 기각, 방향은 DN14.** 검수 판정·제목·계획을 잃는다.
카드에서 그것을 추정하려면 휴리스틱이 필요하고, 그 정확도는 실측할 수 없다.

**(e) 허브가 세션 페이지를 직접 렌더한다(HTML 파이프라인 즉시 폐기) — 이번 회차 기각, DN14-(b).**
대시보드가 허브(별도 설치 채널, 옵트인)에 의존하게 되고, `Tier1Snapshot` 을 소비하는 허브 5모듈과
유닛 테스트 수백 건이 움직인다. 토큰 절감은 (이 설계와) 같고 위험만 크다 — 절감을 먼저 확정하고
구조 정리는 다음 회차가 맞다.

---

## 10. 리스크

| # | 리스크 | 대비 |
|---|---|---|
| 1 | **홑따옴표 인용 실수** — 요약에 `'` 가 들어가 셸이 깨진다 | 규칙에 `’` 치환 1줄. 실패는 Bash 오류로 즉시 보이며 파일은 바뀌지 않는다(append 전 실패). 관문 PRP M13 이 `$`·백틱 안전성을 실측 |
| 2 | **허브 파서 계약 드리프트** — 렌더러가 줄 형태를 바꾸면 허브에서 조용히 사라진다(오늘의 위험과 같은 종류) | 계약 테스트가 렌더 출력에 파서 정규식을 직접 댄다(§7.1). 오늘의 "문서 예시 줄 추출"보다 생산자에 가깝다 |
| 3 | **서브체크 ID 하한(495)** 에 근접 | 구현 중 실측. 밑돌면 하한을 내리는 커밋에 사유 — T26 관용구 |
| 4 | **PiP·라이브 갱신이 허브 의존**이 된다(허브 없는 사용자) | §11-1 승인 항목. `file://` 폴백은 남는다 |
| 5 | 배지 색 타협(설계·승인 = 구현 색) | 목업(§12)으로 사전 확인. 후속에 CSS 2규칙으로 분리 가능(템플릿 변경이지만 허브 파서와 무관) |
| 6 | `switch` 가 `settings.local.json` 공백 서식을 바꾼다 | 값·필드는 보존. 파싱 실패 시 무기록. Claude Code 자신도 이 파일을 재직렬화한다 |
| 7 | 전환 중 세션의 1회성 단절(§8) | 한 줄 보고 규칙으로 흡수 |
| 8 | 오케스트레이터가 `log` 종류를 잘못 골라 단계가 어긋남(예: PRP 완료를 `impl` 로) | 표준 목록에서 `impl` 은 「구현까지 완료」라 설계·승인도 완료 처리된다 — 진행률이 과대해질 뿐 멈추지 않는다. 규칙 표가 시점별 종류를 1:1 로 준다 |

---

## 11. 사용자 승인이 필요한 결정

1. **폐기 목록 승인(DN8~DN10)**: 자동 발행(포트 스캔·로컬 서버·브라우저 열기·focus-tab)·`serve`·`impl`
   세부 작업 패널·매트릭스 모드·LEGACY 쓰기 모드. 특히 **PiP 플로팅이 허브 URL 경유로만** 남는 것.
2. **1단계 범위 확정(DN11·DN14)**: 허브 0변경으로 가고(HTML 파이프라인 유지), 허브가 JSONL 을 직접
   읽는 것은 2단계 PRP 로 미룬다 — 아니면 지금 함께 간다(허브 3모듈 + 유닛 ≈10건 추가).
3. **(c) 아무것도 안 함**이 아니라 이 설계로 가는 것 — 추정 절감 ≈세션 지출 13~15%(§9-(c)) 대
   §7.2 의 변경량.

---

## 12. 프로토타입 실측과 목업

스크래치패드 `proto_render.py` 가 이 설계의 핵심 주장을 실행으로 확인했다(저장소에 넣지 않았다):

- **템플릿 0바이트 변경으로 렌더 가능** — `dashboard_render.render_reissue` 의 앵커 9종이 템플릿에
  각 1회 존재하고, 이벤트 목록 → `PublishedValues` → 완전한 HTML 이 나온다(60~63KB, 오늘 실발행본
  60,050B 와 같은 크기).
- **허브 파서가 그대로 읽는다** — 표본 3상태(전체 경로 완료 4/4·100%, FAIL 직후 2/4·50% 구현
  active, 축약 경로 1/2·50%)와 이 세션의 실발행본 모두 `hub_parse.parse_dashboard_html` 이 제목·진행률·
  단계 상태·상세를 정확히 돌려줬다. 단계 `<li>` 는 한 줄에 하나, 속성 순서는 정규 순서다.
- **JSONL 1줄 ≈265B**(fail 이벤트, 상세 포함).

목업 `dashboard-native-data-source-mock.html`(외부 의존 0, iframe `srcdoc` 4개 = 위 렌더 산출물과
실발행본):

| 패널 | 내용 |
|---|---|
| 현재 | 이 세션의 실발행본 — 설계 진행중, 단계 1 상세가 디스패치 서술(허브 칩과 중복), 헤더 힌트가 `/dashboard serve`·8791 안내 |
| 제안 — FAIL 직후(라이트, 860px) | 구현 다시 진행중·검수 대기, 활성 상세 = 최근 로그 요약, 설계·승인 배지, `R1` |
| 제안 — 완료(다크, 허브 패널 폭 549px) | 4/4, 로그 8건, 최신 3건만 펼침 |
| 제안 — 축약 경로(다크, 549px) | 2단계, `impl` 카드는 비어 숨음 |

`.mock-*` 접두 요소와 테마 결정 1줄·`dz-embedded` 부여 1줄의 고정만 목업 장치이고(파일 머리에 명시),
마크업·CSS 는 손대지 않았다. 힌트 문자열 2줄(DN8)은 목업에 반영하지 않았다.

---

## 13. 참고

- 실측 스크립트·프로토타입·목업 빌더: 스크래치패드 `proto_render.py`·`build_mock.py`(세션 종료 시 사라진다 — 재현은 §2.1·§12 의 방법 서술로 충분하다).
- 번복한 결정: `session-dashboard.md` 결정 1·2, `hub-dashboard.md` 쟁점 1(b) 기각 근거, `dashboard-worktree-bash-gate.md` D2·D3(전달 방식), `hub-session-tree-and-per-session-dashboards.md` ST2(폴백)·ST6(서버).
- 유지한 결정: ST1(세션 ID 파일명)·ST3(토큰 앞 8자리)·ST5(리텐션)·ST9~ST14(허브 발견·라우트)·RL8(사이드카)·RL10(오프 스위치)·AR1~AR14(실행 뷰).
