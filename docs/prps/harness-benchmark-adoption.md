# 하네스 벤치마킹 채택 — 즉시 적용 12건과 서브에이전트 통제 기능 판정

검수자는 앞으로 "고쳐라"는 제안 대신 문제를 실제로 재현한 명령을 붙여야 하고, 재현하지 못한 중대 지적은 한 단계 낮춰 보고한다. 구현자는 테스트를 먼저 실패시킨 증거와 설계 대조 결과를 보고한다. 세 작업 에이전트는 각자 정해진 사고 깊이(effort)로 돌고 하위 에이전트는 탐색 에이전트만 띄운다는 지침이 본문에 적힌다(기계 강제는 아니다 — 서브에이전트 정의에서는 `Agent(...)` 괄호 목록이 무시된다). 허브 세션 줄에는 그 세션의 추정 비용과 컨텍스트 사용률이 작은 칩으로 붙는다.
승인하면 에이전트 파일 4개·검수 커맨드·허브 코드가 6개 커밋으로 바뀌고, 상시 로드되는 규칙(T26 예산)은 1바이트도 늘지 않는다. 설치 반영은 병합·푸시 뒤 사용자가 `/harness-update` 를 직접 실행할 때 일어난다.

**승인 때 함께 정할 것**

1. **effort 고정값** — 설계 `xhigh` · 구현 `high` · 검수 `high`(탐색은 haiku 라 없음). 지금은 세션 값이 그대로 복제된다(xhigh 세션이면 셋 다 xhigh, max 세션이면 셋 다 max).
2. **⑨ 화면 위치** — 안 A(식별 줄의 네 번째 칩, 권고) 또는 안 B(첫 줄 끝). 목업 대조는 §7-4.
3. **새 정적 가드의 원장 등록 방식** — 변조행 대신 면제행 2건으로 등록한다(전체 검사 시간 보호). 면제행 상한(`LEDGER_EXEMPT_ROW_RATCHET`)을 넘으면 상수를 올리는 커밋에 그 사유를 남긴다.

설계 모델: opus(승격 기준 1~4 해당 없음 — 데이터 모델 전면 개편·3개 이상 서브시스템 구조 변경·동시성·재설계 회차 아님). 기준 커밋 `5553737`. 범위 변경 2건 반영(사용자 결정 2026-10-08): 커밋 게이트 제외, 항목별 속도·비용 영향과 도입 전후 비교 계획 추가.

---

## 1. 요구사항 요약

외부 하네스 벤치마킹 조사 결과, 품질을 실제로 움직이는 것은 역할 분리 자체가 아니라 **실행 가능한 검증 신호로 결과를 거르는 것**과 **컨텍스트를 작게 유지하는 것**이었다. coding-harness 는 규약은 보수적인데 그 규약을 뒷받침하는 장치가 산문뿐이다. Claude Code 가 그사이 추가한 서브에이전트 통제 기능(frontmatter `effort`·`tools: Agent(...)`·`omitClaudeMd` 등)도 하나도 쓰지 않는다. 이 설계는 즉시 적용 12건(①~⑫)을 이 저장소에 맞게 구체화한다. 네이티브 통제 기능 후보 13종은 **이 저장소의 실측 문제를 실제로 줄이는가**를 기준으로 하나씩 채택하거나 보류한다. 상시 컨텍스트(T26)를 늘리지 않는 자리(에이전트 파일·커맨드·허브)에만 둔다. 새 검사는 정적 grep 으로만 두고, 무거운 변조행(K6)은 늘리지 않는다.

### 1-1. 이 설계가 근거로 삼는 실측 수치 (재측정하지 않는다)

| ID | 실측 문제 | 수치 | 출처 |
|---|---|---|---|
| P1 | 서브에이전트 effort 가 세션 값을 그대로 복제 | xhigh 세션의 서브 9/9 가 xhigh, 9월 max 세션은 서브 전부 max | 메모리 `subagent-effort-inherits-session` (2026-10-02) |
| P2 | 서브에이전트 디스패치마다 CLAUDE.md 계층 재적재 | 1회당 55,382B (T26 상시 예산 54,238B + 허브 규칙 1,345B 와 같은 계열) | 오케스트레이터 측정 |
| P3 | 과제 시간 구성 | 모델 59%·도구 28%·공백 12%, 생각이 긴 턴 2%, 재호출 라운드 25%(47회·986분 → 회당 약 21분), 구현자 120턴 중 18턴째 첫 수정, 캐시 미스 94회(턴의 1%) | 메모리 `workflow-time-baseline-2026-10` (2026-10-07) |
| P4 | 과제·검사 시간 기준선 | 과제당 가동 중앙값 270분(9월 하순), 전체 검사 27분(그중 K6 23분), 기본 검사 49초 | 같은 메모리 (2026-10-02) |
| P5 | 검수자에게 수정안 텍스트를 요구 | `agents/code-reviewer.md` 보고 양식의 `[제안]   구체적인 수정 방향` 줄 | 저장소 실물 |
| P6 | 하위 스폰 무제한 | 세 작업 에이전트의 `tools:` 에 `Task`(v2.1.63 에 `Agent` 로 개명된 옛 이름) — 어떤 서브에이전트든 띄울 수 있다(이 능력을 `tools:` 로 좁힐 수는 없다 — D3) | 저장소 실물 |

외부 근거는 각 행에 URL 로 단다. 조사 보고서 원문은 세션 임시 폴더에 있어 이 문서는 그것을 인용하지 않는다.

### 1-2. 범위 밖 (NOT building)

- **커밋 게이트**(`git commit` PreToolUse 차단): 보류 — 사용자 결정(2026-10-08).
- **커밋·완료를 막는 모든 훅**(세션 범위 `Stop`·`SubagentStop`·`TaskCompleted` 차단, 에이전트 범위 차단 훅): 보류.
- `commands/code-review.md` 의 **PR Review Mode**(Phase 6 보고 양식): 이 워크플로우는 로컬 모드만 쓴다. 손대지 않는다.
- 렌즈 분할 실행 자산·메인의 심각도 재판정·깊이 신호·compact 복귀 지시 등 보고서의 조건부 묶음(B~K, 아래 §3-2 에서 판정하는 J 제외).
- 상시 규칙(`rules/common`·`rules/workflow`·`CLAUDE.md`·`rules/README.md`) 문구 변경 — 0건(§9-1).

---

## 2. 결정 요약

| 결정 | 내용 | 근거 |
|---|---|---|
| D1 | 모든 변경을 디스패치 때만 로드되는 자리(에이전트 파일·커맨드)와 허브 코드에 둔다. T26 변화 0B | CLAUDE.md §3(병목은 세션 컨텍스트 예산) |
| D2 | ⑤ 의 「디스패치 보고에 effort 한 줄」은 채택하지 않는다. frontmatter `effort` 로 역할별 값을 고정하고, 실제 값은 서브에이전트 기록에서 확인한다 | 고정 후에는 역할별 effort 가 결정적이다. 실제 값은 기록 줄 최상위 `effort` 필드에 남는다. 규칙 문구 수정은 +17B ⚠T26 인데 새 정보가 없다 |
| D3 | ④ 는 **표기 정리 + 지침 문장**이다(기계 강제 없음, 사용자 결정 2026-10-08). 세 작업 에이전트 `tools:` 는 괄호 없는 정식 이름 `Agent` 로 두고(옛 이름 `Task` 는 별칭), 「하위 에이전트는 Explore 만 띄운다」는 본문 지침 한 문장으로 남긴다. 검수자에게는 「다른 검수자를 띄워 판정을 맡기지 않는다」를 덧붙인다 | **2회차 개정 — 왜 바뀌었나.** 처음 설계는 `tools: Agent(Explore)` 로 스폰을 기계로 막으려 했다. 그러나 문서([Subagents](https://code.claude.com/docs/en/sub-agents) 506행)는 「`Agent(agent_type)` 허용 목록 문법은 `claude --agent` 로 메인 스레드를 돌릴 때만 적용되고, 서브에이전트 정의에서는 괄호 안의 타입 목록이 무시된다」고 적는다(486행: `Task` 는 `Agent` 의 별칭). 무시되는 표기를 남기면 막힌 것처럼 읽히는 거짓 안심이 된다 |
| D4 | ② 「검수 입력 패키지」는 **검수자 쪽 축소형**으로 둔다 — 기준 SHA 를 기록하고 diff 를 1회만 수집한다. 메인이 미리 묶어 넘기면 그것을 읽는다 | 메인에게 패키징을 시키려면 상시 규칙(⚠T26 약 +100B)에 써야 한다. 축소형은 T26 0B 로 SHA 고정·재수집 방지를 얻는다. 보고서가 인용한 "검수자 출력 −41%"(자기 보고)는 기대하지 않는다 |
| D5 | ⑫ 는 **사유 범주만** 새로 기록한다. 경로(전체/축약)는 `init` 의 단계 목록에서, 회차는 허브의 자동 누적에서 이미 파생된다 | 같은 사실을 두 번 적지 않는다. 기록 규약 변경은 허브 규칙 1행 |
| D6 | 새 정적 가드는 T38(`PATCH_CONTRACT_PAIRS`)이 아니라 T31 그룹 함수 안에 둔다 | T38 의 표는 `tests/run.sh` **최상위 배열**이다. 이 배열을 바꾸면 증분 K6 선택기가 전체 재확인(모든 변조행 약 23분)으로 전환한다(`tests/k6_selection.py` 머리 주석 FULL 트리거 3). 그룹 함수 안 지역 배열은 그 트리거가 아니다 |
| D7 | 새 가드 ID(T31-10·T31-11)는 원장에 **면제행**으로 등록한다. 「일부러 깨뜨려 실패 확인」은 구현 시 수동 1회로 대신한다 | K6 변조행 1행은 그룹 재실행 2회와 미러 1개를 상시로 더한다. 사용자 결정(전체 검사 시간 보호) |
| D8 | ⑨ 의 순수 파서는 `hub_usage.py`(statusLine 입력 계약 파서)에 더한다. I/O 는 새 모듈 `hub_session_cost.py` 에 둔다 | `hub_collect.py` 가 773줄이라 I/O 를 더하면 800줄 상한(T25-100)을 넘는다. 파서는 이미 같은 외부 포맷(statusLine stdin)을 다루는 모듈이 맞다 |
| D9 | ⑨ 에는 설정 스위치를 새로 두지 않는다. 끄는 수단은 기존 `/hub statusline off` 다 | 내용이 없는 숫자 4개다. 이미 옵트인인 statusLine 경로에서만 생긴다(YAGNI) |
| D10 | ⑨ 화면은 안 A(식별 줄 칩)를 권고한다 | 목업 실측: 최소 폭 320px 에서 안 A 는 추가 줄 0, 안 B 는 백그라운드 세션에서 1줄 추가 → 카드(340px 고정)에 보이는 세션 수가 준다 |

---

## 3. 채택/보류 표

속도·비용 부호: **+** 과제당 시간·토큰 증가 · **−** 감소 · **0** 무관. 크기는 P3 의 턴 속도(출력 200토큰 미만 도구 호출 턴이 93%, 컨텍스트 100K 미만 3.6초 · 300K 초과 9.1초)로 환산한 추정이다. 측정은 §11 에서 도입 뒤에 한다.

### 3-1. 즉시 적용 ①~⑫

| # | 판정 | 바뀌는 곳 | 줄이는 실측 문제 | 속도·비용 영향 (부호 · 크기 · 근거) | 완화책 |
|---|---|---|---|---|---|
| ① 검수 지적에 재현 증거 의무화 | **채택** | `agents/code-reviewer.md` 보고 양식 `[제안]`→`[재현]`, 하향 규칙 · `commands/code-review.md` Phase 4 | P5. 거짓 FAIL 이 만드는 왕복(P3 재호출 라운드 25%). 근거: 수정안 요구 프롬프트가 정답을 틀렸다고 하는 비율(FNR)을 73~88% 로 올리고, 실행 검증 필터가 54.8→16.3% 로 내렸다 — [arXiv 2603.00539](https://arxiv.org/abs/2603.00539) | **검수 회차당 +, 과제당 −가능.** CRITICAL/HIGH 지적 1건당 +1~3턴(+5~30초). 회차당 0~3건이면 +2분 이내. 거짓 HIGH 하나가 없애는 왕복 1회는 약 21분(P3: 986분/47회) | CRITICAL/HIGH 만 의무. MEDIUM/LOW 는 재현 불요. 「설계 대조」(PRP 불일치)는 명령 없이 PRP 절 + 코드 위치. 경량 검증에서 이미 실패한 테스트는 그 자체가 재현이다(추가 실행 없음) |
| ② 검수 입력 패키지 | **채택(축소형, D4)** | `agents/code-reviewer.md` 절차 2 · `commands/code-review.md` Phase 1 | 같은 diff 재수집, 낡은 diff 로 검수할 위험. 근거: superpowers v6 "Read the diff file once" — [task-reviewer-prompt](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/task-reviewer-prompt.md) | **0~−.** 재수집 1~2턴 절감(−10초 안팎) | — |
| ③ 「주장을 믿지 말라」 순서 | **채택** | `agents/code-reviewer.md` 절차 재배열(결함 탐색 → 주장·설계 대조) | 구현자 보고서·PRP 에 의한 앵커링. 근거: BMAD edge-case-hunter "Do NOT read it before Step 5" — [링크](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-build/review-prompts/edge-case-hunter.md), 자기선호 편향 [arXiv 2410.21819](https://arxiv.org/abs/2410.21819) | **0.** 같은 읽기의 순서만 바뀐다 | — |
| ④ 하위 스폰 표기 정리 + 지침(2차 검수자 금지) | **채택(표기 정리 + 지침 문장, D3 — 기계 강제 없음)** | 세 작업 에이전트 `tools:` 의 `Task` → `Agent`(정식 이름) · 본문 지침 한 줄 | P6. 근거: [Subagents](https://code.claude.com/docs/en/sub-agents) 486행(`Task` 는 `Agent` 의 별칭)·506행(서브에이전트 정의의 `Agent(...)` 괄호 목록은 무시된다) | **0.** 능력은 이전과 같고 지침 문장이 한 줄 늘 뿐이다. 탐색 외 스폰 1회는 최소 55,382B(P2) 재적재이지만 관측된 빈도가 없고 이 변경이 막지도 않는다 | — |
| ⑤ effort 명시 | **채택(frontmatter 고정, D2)** | 세 작업 에이전트 frontmatter `effort:` | P1 | **토큰 −(구현·검수), 설계 0/+.** xhigh·max 세션에서 구현·검수의 생각 토큰이 high 수준으로 준다. 설계는 xhigh 세션 기준 현상 유지이고, high 세션이면 설계만 xhigh 로 오른다. **속도 ≈0** — 생각이 긴 턴이 2%(P3)라 effort 로는 거의 빨라지지 않는다 | 사용자가 다른 값을 원하면 디스패치 인자 `effort` 로 그 회차만 바꾼다 |
| ⑥ 계획 리마인더 | **채택(전체 경로만)** | `agents/implementer.md` 구현 절차 | PRP 이탈. 근거: 21,120 궤적에서 주기적 계획 리마인더가 위반을 줄였다 — [arXiv 2604.12147](https://arxiv.org/abs/2604.12147) | **+소.** PRP 「구현 단계 분할」 경계마다 절 단위 재읽기 1턴. 단계 4~6개면 +4~6턴(+1분 안팎), 누적 컨텍스트 +20~60KB | 단계 경계에서만, 해당 절만(offset/limit), 전체 경로만. 축약 경로에는 PRP 가 없어 적용하지 않는다 |
| ⑦ RED 증거 보고 | **채택** | `agents/implementer.md` 완료 보고 형식 · 검수자 절차 7 | 자작 테스트가 대상 동작을 물지 않는 문제. 근거: [arXiv 2602.07900](https://arxiv.org/abs/2602.07900) | **≈0.** RED 실행은 기존 TDD 절차(절차 4)에 이미 있다. 출력 1~3줄을 옮겨 적을 뿐이다 | — |
| ⑧ 스펙 유도 테스트 | **채택(전체 경로만)** | `agents/implementer.md` 절차 4 | 테스트가 구현을 따라 쓰이는 문제. 근거: 버그 검출 +9.8pp(p=0.0352) — [arXiv 2608.17177](https://arxiv.org/abs/2608.17177) | **+소.** 대상당 2~5줄, 과제당 +1~3턴 | 전체 경로만, 공개 함수·모듈 단위만 |
| ⑨ statusline 비용·컨텍스트 캡처 | **채택(안 A 권고, D8·D9·D10)** | `hub/bin/hub_statusline.py`·`hub_usage.py`·새 `hub_session_cost.py`·`hub_session.py`·`hub_project.py`·`hub_collect.py`·`hub_template.html`·문서 | 허브에 비용·토큰 축이 없다. 전후 비교(§11)의 세션 단위 데이터 원천. 필드: [statusline 문서](https://code.claude.com/docs/en/statusline) | **세션 실행 중 0.** statusLine 호출마다 작은 파일 읽기 1회(<1ms), 값이 바뀔 때만 쓰기. 수집은 세션 수만큼 작은 파일 읽기. **구현 회차 +(일회성):** 이 커밋의 전체 검사에서 증분 K6 가 닿은 파일의 기존 변조행 약 130행(`hub_template.html` 82 · `hub_session.py` 16 · `hub/README.md` 12 · `hub/install.sh` 12 · `hub_collect.py` 6 등)을 고른다 → 그 1회 +10~15분 | ⑨ 를 마지막 커밋(C6)으로 떼어 그 커밋에서만 1회 치른다. 검수자는 닿은 그룹만 돌린다(`--only T24 T25`) |
| ⑩ null-op 비용 1회 측정 | **채택(구현 단계 1회)** | 측정만, 결과는 이 문서 부록 B | P2 의 외부 보정치. J 의 실제 절감 폭 확인. 측정법: [practicalsystems](https://www.practicalsystems.io/blog/measure-your-subagent-token-cost) | **일회성 ~1분**, haiku 호출 2회(몇 센트 이하) | — |
| ⑪ `/doctor prompt-audit` 1회 | **채택(사용자 수행)** | 없음(결과 검토만, 자동 수정 없음) | 구모델용 프롬프트 패턴 점검. [releases](https://github.com/anthropics/claude-code/releases) | **사용자 일회성** | 대화형 패널이라 세션이 실행할 수 없다(§12) |
| ⑫ 기준선 확장(FAIL 사유 범주) | **채택(D5)** | `agents/code-reviewer.md` Verdict 줄 · `commands/code-review.md` · `hub/rules/dashboard-recording.md` 1행 · `hub/README.md` | 「3회 FAIL = 설계 문제」 가설을 자체 데이터로 검증. 근거: Terminal-Bench 실패 3분류 — [arXiv 2601.11868](https://arxiv.org/abs/2601.11868) | **0.** Verdict 에 단어 몇 개, fail 상세에 몇 글자. 허브 규칙 +약 60B(허브 사용자 상시 컨텍스트, T26 밖) ≈ 세션당 15토큰 | — |

### 3-2. Claude Code 네이티브 서브에이전트 통제 기능

| 후보 | 판정 | 근거(실측 문제와의 관계) | 보고서 판정과 다른 점 | 속도·비용 영향 |
|---|---|---|---|---|
| frontmatter `effort` | **채택** (⑤) | P1 을 직접 없앤다 | 같음(⑤). 단 디스패치 보고 한 줄은 미채택(D2) | 위 ⑤ |
| `tools: Agent(...)` 하위 스폰 제한 | **미채택 — 표기만 정리**(④) | 서브에이전트 정의에서는 괄호 목록이 무시된다(문서 506행) — 기계 제한이 안 되므로 `Agent` 정식 이름 + 지침 문장으로 둔다 | 보고서는 채택(제한)으로 판정했다 — 문서가 허용하지 않는 용법이었다 | 위 ④ |
| `omitClaudeMd` | **Explore 만 채택(J)**, 나머지 셋은 보류 | P2(디스패치당 55,382B)는 이미 잰 수치다. Explore 는 읽기 전용·수집 전용이라 지침이 없어도 위험이 작다. 내장 Explore 도 같은 동작이다([Subagents](https://code.claude.com/docs/en/sub-agents)). 나머지 셋은 본문이 「규칙은 이미 자동 로드돼 있다」를 전제한다 | 보고서는 J 를 「⑩ 측정 뒤 조건부」로 뒀다. 이 설계는 측정 전에 채택한다. 판단에 필요한 수치(P2)가 이미 있고, 되돌리기가 frontmatter 1줄이다. 실제 절감 폭(규칙까지 빠지는지)은 ⑩ 에서 확인해 부록 B 에 적는다 | **−.** Explore 디스패치마다 약 2.2만 토큰(부록 B 실측 약 21.9K) |
| `maxTurns` | 보류 | 실측 폭주 사례가 없다. 구현자는 정상 작업에 120턴을 쓴다(P3). Terminal-Bench 2.0 에서 턴 수와 성공률은 무상관이다 | 같음(F, 조건부). 재개 조건: 한 디스패치가 정상 분포를 크게 넘는 폭주가 관측될 때 | 채택 시 0, 상한이 낮으면 정상 작업을 끊는다 |
| `isolation: worktree` | 보류 | 실측 문제(동시 세션의 미커밋 혼입)는 세션 단위 워크트리가 이미 다룬다. 구현자 사본은 메인 반영 단계를 더하고, 격리 셸 제약(`python3 "$HOME/…"`·heredoc 거부)이 검증 명령을 막을 수 있다. 허브 cwd 귀속도 확인되지 않았다 | 같음(E, 조건부) | 채택 시 + (반영 단계) |
| `permissionMode` | 보류 | 실측 문제 없음. `plan` 은 검수자의 경량 검증(테스트 실행)을 막고, 권한 우회 모드는 `rules/common/hooks.md` 와 충돌한다 | 보고서 판정 없음 | — |
| `disallowedTools` | 보류 | `tools:` 허용 목록이 이미 같은 것을 표현한다(중복) | 보고서 판정 없음 | — |
| 에이전트 범위 `hooks` | 보류 | 검수자 쓰기 차단(Bash `sed -i` 등) 용도는 실측 사고가 0건이다. 훅 스크립트를 배포할 통로가 rules·agents·commands 3종에 없다. 막는 훅은 이번 범위 밖이다(사용자 결정) | 보고서 판정 없음. 재개 조건: 검수자가 파일을 바꾼 사례 | — |
| `background` | 보류 | 10분 넘는 공백 48회가 전부 직렬 대기(P3)다. 배경 실행은 다음 단계가 결과를 기다리는 구조를 없애지 않는다 | 보고서 판정 없음 | — |
| `memory` | 보류 | 자동 학습 루프 기각(자가증식 사고의 자동화판)과 같은 축 | 같음(§4-3) | — |
| `skills` 프리로드 | 보류 | 절약은 디스패치당 1턴(<1%)이다. 축약 경로에서 쓰지 않는 전문(`prp-implement` 390줄)까지 실어 P2 를 키운다 | 같음(§4-3) | 채택 시 + (컨텍스트) |
| `experimental.cacheTtl` | 보류 | 캐시 미스가 턴의 1%(94회, P3)라 줄일 문제가 없다. 1시간 캐시 쓰기는 2배 단가다 | 보고서 판정 없음 | 채택 시 + (단가) |
| 세션 범위 `Stop`·`SubagentStop`·`TaskCompleted` 차단 훅 | 보류 — 사용자 결정(2026-10-08) | 커밋·완료를 막는 훅은 이번 범위에서 채택하지 않는다. 기술적으로도 승인 대기·미해결 종결처럼 정상적으로 턴을 끝내야 하는 흐름을 막는 오작동 위험이 있다 | 보고서는 언급만 했다 | — |

### 3-3. 조건부 A

| 후보 | 판정 |
|---|---|
| A 커밋 PreToolUse 게이트(허브 원장 기반) | **보류 — 사용자 결정(2026-10-08)** |

---

## 4. 영향 범위

| 파일 | 변경 | 항목 | 커밋 |
|---|---|---|---|
| `agents/implementer.md` | frontmatter 2줄(`tools`·`effort`) + 절차 4 확장 + 계획 리마인더 + 완료 보고 3항목 + 탐색 위임 1줄 | ④⑤⑥⑦⑧ | C1·C3 |
| `agents/code-reviewer.md` | frontmatter 2줄 + 서두 1문장 + 절차 재배열 + 재현 의무 + 보고 양식 + 사유 범주 + 재검수 모드 상호참조 번호 | ①②③④⑤⑫ | C1·C2 |
| `agents/design-architect.md` | frontmatter 2줄 | ④⑤ | C1 |
| `agents/explore.md` | frontmatter `omitClaudeMd: true` + description 1구 | J | C1 |
| `commands/code-review.md` | Phase 1 에 기준 SHA·1회 수집 · Phase 4 의 `Suggested fix` → 재현 의무·하향 · 사유 범주 | ①②⑫ | C2 |
| `NOTICE.md` | §5 정본 목록의 `agents/code-reviewer.md`·`commands/code-review.md` 행(패치 요지·누적 커밋 수) + §5 커버리지 표 두 행 | ①②③⑫ | C2 |
| `README.md` | 「agents 구성」 표의 모델 열에 effort, 아래 목록에 3줄(effort 고정·스폰 지침·Explore 의 CLAUDE.md 미적재) | ④⑤J | C1 |
| `hub/rules/dashboard-recording.md` | 「검수 결과」 행에 fail 상세의 사유 범주 | ⑫ | C4 |
| `hub/README.md` | 진행 기록 `fail` 행 · 프라이버시 고지 · 파일 배치(33개·`session_costs/`) · 세션 줄 설명 · 제거 시 보존 목록 | ⑫⑨ | C4·C6 |
| `hub/bin/hub_usage.py` | `SessionCost`·`SessionCostCapture`·`StatusLineCaptures` + 파서 3개 + 판정 1개(★순수 유지) | ⑨ | C6 |
| `hub/bin/hub_session_cost.py` (신규, I/O) | 캡처 파일 경로·읽기·쓰기·보관 기간 정리 | ⑨ | C6 |
| `hub/bin/hub_statusline.py` | stdin 1회 파싱으로 두 캡처, 세션 비용 캡처 쓰기 | ⑨ | C6 |
| `hub/bin/hub_session.py` | `SessionView.session_cost`(맨 뒤) + `compute_session_view` 인자 | ⑨ | C6 |
| `hub/bin/hub_project.py` | `compose_project_views`·`_project_view_for_path`·`_session_views_for_path` 통과 배선 | ⑨ | C6 |
| `hub/bin/hub_collect.py` | 새 헬퍼 `_prune_and_read_session_costs`(14줄)와 `compose_project_views` 인자 한 줄 — `collect_snapshot` 이 이미 50줄이라 호출은 기존 인자 줄에 얹었다. 790줄 | ⑨ | C6 |
| `hub/bin/hub_template.html` | CSS 1규칙 + JS 상수 3개·함수 3개 + `renderSessionMeta` 1줄 | ⑨ | C6 |
| `hub/install.sh` | `HUB_FILE_COUNT` 32→33 · 제거 완료 보존 목록에 `session_costs/` 1줄 | ⑨ | C6 |
| `commands/hub.md` | `/hub statusline on`·`/hub install` 고지에 세션별 숫자 캡처 1문장씩 | ⑨ | C6 |
| `tests/run.sh` | T31-10·T31-11 신설(그룹 함수 안), T31 그룹 설명·머리 주석 · T25-104·T25-149·T25-150 갱신 · `HUB_DASHBOARD_RULE_BUDGET_BYTES` · T25-201(툴팁 트리거 20→21) · `SOURCE_GUARD_ID_FLOOR` 537→539 (`LEDGER_EXEMPT_ROW_RATCHET` 은 올리지 않았다 — 면제행 313 ≤ 372) | 가드 | C1~C6 |
| `tests/mutations.tsv` | T31-10·T31-11 면제행 2건 · T25-104·T25-149 변조행의 sed·토큰 갱신(행 수 불변) | 가드 | C1·C3·C6 |
| `tests/hub/test_hub_usage_session_cost.py`(신규 — `test_hub_usage.py` 가 800줄을 넘지 않게 나눴다) · `tests/hub/test_hub_session_cost.py`(신규) · `tests/hub/test_hub_statusline.py` · `tests/hub/test_hub_session.py` · `tests/hub/test_hub_project.py` · `tests/hub/test_hub_collect.py` · `tests/hub/test_hub_template_dom_session_row.py` · `tests/hub/__init__.py`(SESSION_COSTS_DIR 중화) | 단위 테스트 | ⑨ | C6 |
| `docs/prps/harness-benchmark-adoption.md` | 부록 B(⑩ 측정)·부록 C(⑪ 결과, 사용자가 전해 준 경우) 채우기 | ⑩⑪ | C5 |

`install.sh` 의 `AGENTS_FILE_COUNT`(4)·`COMMANDS_FILE_COUNT`(8)·`RULES_FILE_COUNT`(46)는 바뀌지 않는다(파일 추가·삭제 없음). 그래서 `removals.txt` 도 손대지 않는다.

---

## 5. 파일별 변경 내용

### 5-1. frontmatter (C1)

```yaml
# agents/design-architect.md
tools: Read, Grep, Glob, Bash, Write, Agent, Skill
model: opus
effort: xhigh

# agents/implementer.md
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, Skill
model: sonnet
effort: high

# agents/code-reviewer.md
tools: Read, Grep, Glob, Bash, Agent, Skill
model: sonnet
effort: high

# agents/explore.md — effort 줄을 두지 않는다(haiku 에는 effort 레벨이 없다, rules/common/performance.md)
tools: Read, Grep, Glob
model: haiku
omitClaudeMd: true
```

- `tools:` 는 괄호 없는 정식 이름 `Agent` 다. 서브에이전트 정의에서는 `Agent(타입)` 괄호 목록이 무시된다 — 그 문법은 `claude --agent` 로 메인 스레드를 돌릴 때만 적용된다(문서 506행). 그래서 제한처럼 보이는 표기를 남기지 않는다. 「Explore 만 띄운다」는 본문 지침이고, `explore.md` 의 `name: Explore` 는 내장 Explore 를 가리는 사용자 에이전트라 그 Explore 도 이 파일을 뜻한다.
- `explore.md` description 끝에 한 구를 더한다: 「프로젝트 지침(CLAUDE.md 계층)은 받지 않으므로 필요한 규칙·경로는 요청에 담는다.」 이 설명은 Explore 를 부르는 세 에이전트의 도구 목록에 실린다. 부르는 쪽이 이 사실을 알아야 요청에 필요한 맥락을 담는다.
- frontmatter 키의 철자와 값은 [Subagents 문서](https://code.claude.com/docs/en/sub-agents) 기준이다(`omitClaudeMd` v2.1.271+, `effort` 값 `low|medium|high|xhigh|max`). 세션 런타임은 설계 시점 기록에서 2.1.293(데스크톱)이다. **PATH 의 `claude` 는 2.1.108 이다** — 리스크 R2 참조.

### 5-2. `agents/code-reviewer.md` (C1 frontmatter, C2 본문)

서두 괄호 문장: 「수정 제안은 텍스트로만 전달한다」 → 「지적은 수정안이 아니라 **재현 증거**로 전달한다 — 고치는 방법은 implementer 가 정한다」.

**검수 절차(1회차) 재배열** — 번호와 내용:

1. 프로젝트 컨텍스트 파악 — 현행 그대로.
2. 변경 수집(②) — 기준 커밋을 정한다(요청에 있으면 그것, 없으면 `git rev-parse HEAD` + 미커밋 변경). 보고서 머리에 그 SHA 를 적는다. diff 는 **한 번** 수집한다(`--stat` 먼저, 그다음 본문). 요청이 diff 파일 경로를 주면 그것을 읽고 git 을 다시 돌리지 않는다. 같은 diff 를 다시 수집하지 않는다. diff 가 없으면 현행대로 최근 커밋을 본다.
3. 범위 이해 — **diff 만으로** 정한다. 요청에 실린 구현자 보고서는 이 단계의 근거로 쓰지 않는다(절차 7 까지 미검증 주장).
4. 주변 코드 읽기 — 현행 그대로(「파일 읽기」 절이 「절차 4」를 인용하므로 번호를 유지한다).
5. 결함 탐색 — 현행 절차 6(체크리스트)의 내용.
6. 경량 검증 — 현행 절차 7 의 내용 그대로. 끝에 한 문장을 더한다: 「여기서 실패한 테스트는 그 자체가 재현 증거다(별도 실행 불요).」
7. 주장·설계 대조(③⑦) — 이제 PRP 와 구현자 보고서를 읽는다. 보고서의 주장(테스트 통과·설계와 다른 점 없음·RED 증거)은 **미검증 주장**이다. 절차 5·6 결과와 대조해 어긋나면 지적한다. RED 증거가 없는 새 테스트는 그 assertion 이 대상 동작을 실제로 무는지 코드로 확인한다. 설계 문서 대조(설계에 없는 변경 지적)는 현행 절차 5 의 내용이다.
8. 보고 — 아래 형식. 재현 의무를 적용하고, FAIL 이면 Verdict 에 사유 범주를 적는다.

**재검수 모드** 상호참조: 「범위 규칙은 절차 7 과 같다」 → 「절차 6 과 같다」. 「절차 2 의 diff」는 번호가 그대로라 바꾸지 않는다.

**「노이즈 필터링」에 「재현 의무」 소절 추가(①)**:

- CRITICAL/HIGH 지적에는 `[재현]` 을 붙인다. 형태는 셋이다.
  - **동작 결함** — 실행해서 잘못된 결과를 보이는 명령(실패하는 기존 테스트, 또는 저장소 밖 임시 경로·인라인으로 돌리는 짧은 실행)과 출력 1~3줄.
  - **규칙 수치 위반**(함수 길이·중첩 등) — 그 수치를 보이는 측정 명령과 출력.
  - **설계 대조** — PRP 절과 코드 위치. 명령은 필요 없다.
- 정적 지적(함수 50줄 초과 같은 정적 지표, 하드코딩 자격 증명 같은 정적 보안 패턴)은 「규칙 수치 위반」 형태(그 수치·패턴을 보이는 측정·grep 명령과 출력 1~3줄)이고 사유 범주는 `정합` 이다. 실행으로 오동작·악용이 재현되면 「동작 결함」 형태이고 범주는 `실행` 이다(2회차 M3).
- 셋 다 붙일 수 없으면 한 단계 낮춘다(CRITICAL→HIGH, HIGH→MEDIUM). `[재현]` 칸에는 「없음 — 하향」이라고 쓴다.
- MEDIUM/LOW 에는 재현 의무가 없다.
- 재현하려고 저장소 파일을 쓰거나 테스트를 추가하지 않는다(「새 테스트를 작성하지 않는다」와 같은 경계). 실행이 캐시·임시 파일을 저장소에 남기지 않게 한다(예: `python3 -B`, 임시 파일은 저장소 밖 경로에 — 2회차 LOW).

**보고 양식** — `[제안]` 줄을 바꾼다:

```
[심각도] CRITICAL | HIGH | MEDIUM | LOW
[분류]   보안 | 구조 | 가독성 | 설계 | 성능 | 테스트 | 설계문서 불일치
[위치]   파일 경로:줄 번호
[문제]   무엇이 왜 문제인지 (가이드라인의 어떤 항목 위반인지 명시)
[재현]   명령 + 출력 1~3줄 | 설계 대조: PRP 절 ↔ 위치 | 없음 — 하향   (CRITICAL/HIGH 필수)
```

Verdict 예시 줄: `Verdict: FAIL [실행,검증] — HIGH 2건 수정 후 재검수 필요.` 그 아래에 **사유 범주** 정의를 둔다(§6-2). 판정 기준 절의 PASS/FAIL 조건은 바뀌지 않는다. 하향된 지적은 그 하향된 심각도로 판정에 들어간다.

**탐색 위임** 절에 한 구를 더한다: 「하위 에이전트는 Explore 만 띄운다 — 다른 검수자를 띄워 판정을 맡기지 않는다.」(지침 문장 — 기계 강제 없음, D3)

- `재검수 모드` 토큰(T38-3 계약)은 그대로 둔다.
- 배포 트리에서 `파일명.확장자:숫자` 형태로 인용하지 않는다(T39-4 상한 1, 이미 찼다). `파일 경로:줄 번호` 같은 한글 자리표시는 해당하지 않는다.

### 5-3. `commands/code-review.md` (C2, 벤더링 파일)

- Phase 1 GATHER 끝에 한 단락: 기준 SHA(`git rev-parse HEAD`)를 보고서 머리에 기록한다. diff 는 한 번만 수집한다. 호출자가 diff 파일을 넘기면 그것을 읽는다.
- Phase 4 REPORT 의 `- Suggested fix` 를 바꾼다(2회차 M3 — 에이전트 쪽과 같은 **세 형태**로 맞췄다):
  - `- Reproduction for CRITICAL/HIGH — one of three forms: 「동작 결함」 (a command that shows the wrong result, 1–3 output lines), 「규칙 수치 위반」 (a measuring/grep command that shows the number or pattern, 1–3 output lines), or 「설계 대조」 (PRP section ↔ location). Static findings (function > 50 lines, hardcoded credentials) use 「규칙 수치 위반」 and cause category `정합`. Without a reproduction, downgrade the finding one level (MEDIUM/LOW need none).`
  - `- Verdict line with FAIL cause categories [실행|검증|정합|설계] (definitions: agents/code-reviewer.md 「사유 범주」).`
- `### Phase 3 — VALIDATE (light)` 머리글(T38-3 계약 토큰 `VALIDATE (light)`)은 그대로 둔다.

### 5-4. `agents/implementer.md` (C1 frontmatter, C3 본문)

**구현 절차 4**를 세 하위 단계로 바꾼다(문서·설정만 바꾸는 변경에는 해당하지 않는다는 단서는 유지).

- a. (⑧, 전체 경로) 테스트를 쓰기 전에, 대상 공개 함수·모듈마다 **사전 조건·사후 조건·정의하지 않는 입력**을 2~5줄로 적는다. 테스트 케이스는 이 줄과 PRP 테스트 계획에서 유도한다. 이 줄은 코드 주석이 아니라 완료 보고 「테스트 스펙」에 옮긴다.
- b. (⑦) 테스트를 돌려 실패를 확인한다(RED). 그 **RED 실행 명령**과 실패 출력 1~3줄을 보고용으로 남긴다.
- c. 구현해 통과시킨다(GREEN).

**새 절차 3-1(⑥, 전체 경로)**: PRP 의 구현 순서·단계 절(제목은 PRP 마다 다르다 — 「구현 단계 분할」이라는 제목에 기대지 않는다, 2회차 M2)의 단계 하나를 끝낼 때마다 다음 단계에 들어가기 전에 두 절을 다시 읽는다 — PRP 의 그 단계 절, 그 단계가 닿는 인터페이스·데이터 모델 절. 그리고 지금 diff 와 대조한다(**계획 리마인더**). 어긋나면 「준수 사항」대로 멈추고 PRP 수정안을 보고한다. 이 재읽기는 「파일 읽기」 절의 재읽기 금지의 예외다. 목적이 내용 확인이 아니라 계획 대조이고, 절 단위로만 읽는다.

**탐색 위임** 절에 한 줄: 「하위 에이전트는 Explore 만 띄운다.」(지침 문장 — 기계 강제 없음, D3)

**완료 보고 형식**에 세 항목을 더한다.

- 테스트 스펙(전체 경로): 대상별 사전·사후 조건·정의하지 않는 입력 2~5줄.
- RED 증거: 새 테스트마다 「RED 실행 명령 · 실패 출력 1~3줄 · GREEN 실행 명령」. 검수자는 이것을 미검증 주장으로 받는다.
- 계획 대조(전체 경로): 단계별 「일치 / 어긋남 → 보고한 수정안」.

- 기존 예시 `src/module.py:42`(T39-4 래칫 1건의 그 인용)는 건드리지 않는다. 새 문장에 `파일.확장자:숫자` 형태를 쓰지 않는다.
- 관찰(언급만, 이번에 고치지 않는다): `commands/prp-implement.md` 「Handling Deviations」는 이탈 시 계속 진행하라고 하고, `agents/implementer.md` 「준수 사항」은 멈추고 제안하라고 한다. 구현자에게는 에이전트 본문이 우선이라 실제 충돌은 없다. 다만 메인이 `/prp-implement` 를 직접 부르면 계속 진행 쪽이 적용된다.

### 5-5. `README.md` (C1)

- 「agents 구성」 표의 모델 열 → 「모델 · effort」: `opus · xhigh (조건부 fable)` / `sonnet · high` / `sonnet · high (민감 시 opus · 「전수 검사」 시 fable)` / `haiku (effort 없음)`.
- 표 아래 목록에 3줄:
  - effort 는 에이전트 frontmatter 로 고정한다 — 세션 effort 를 물려받지 않는다. 환경변수 `CLAUDE_CODE_EFFORT_LEVEL` 은 frontmatter 보다 우선한다.
  - 작업 에이전트 3종은 하위 에이전트로 Explore 만 띄운다 — 본문 **지침**이다. `tools` 에는 정식 이름 `Agent` 를 쓰고, 서브에이전트 정의에서는 `Agent(...)` 괄호 목록이 무시되므로 기계 강제는 없다고 적는다.
  - explore 는 CLAUDE.md 계층을 받지 않는다(`omitClaudeMd`) — 부르는 쪽이 필요한 규칙을 요청에 담는다.
- `실측 <n>B` 패턴(T26-2 가 정확히 2건을 센다)은 건드리지 않는다.

### 5-6. ⑫ 기록 규약 (C4)

- `hub/rules/dashboard-recording.md` 「검수 결과」 행을 다음으로 바꾼다:
  `log pass '<요약>' ['<상세>']` 또는 `log fail '<요약>' '[<사유 범주>] <상세>'`(범주는 검수 Verdict 의 것) — 회차는 자동
  증가는 약 +60B(정확한 값은 편집 후 `wc -c` 실측). `HUB_DASHBOARD_RULE_BUDGET_BYTES` 를 그 실측치로 올린다. 커밋 사유: 「3회 FAIL = 설계 문제」 가설의 자체 데이터 수집(⑫). 이 파일은 허브 사용자에게만 상시 로드되고 T26 밖이다.
- `hub/README.md` 「데이터 모델 — JSONL 이벤트」 표의 `fail` 행에 한 문장: 「`detail` 머리의 `[실행,검증]` 은 검수 Verdict 의 사유 범주(실행·검증·정합·설계)다 — 기록 규약이며 허브는 해석하지 않는다.」
- 코드 변경은 없다. 파서는 `detail` 을 원문 그대로 둔다. 분석은 사후에 JSONL 을 읽어 한다(§11).

### 5-7. ⑨ 허브 (C6)

**흐름**

```
statusLine stdin ─▶ hub_statusline._run
                     ├─ hub_usage.parse_status_line_captures(text, now)   # json.loads 1회
                     ├─ print(format_status_line_summary(rate_limits))     # 기존 — 먼저 출력
                     ├─ (기존) rate_limits 캡처 비교·쓰기
                     └─ session_cost 가 있으면:
                          previous = hub_session_cost.read_session_cost(id)
                          같지 않으면 hub_session_cost.write_session_cost(id, cost)
collect_snapshot ─▶ hub_session_cost.prune_old_session_cost_files(now, retention_days)
                 ─▶ hub_session_cost.read_session_costs(세션 ID 들) → dict
                 ─▶ compose_project_views(..., session_cost_by_session_id) → … → compute_session_view(session_cost=…)
                 ─▶ SessionView.session_cost ─▶ (asdict 직렬화) ─▶ renderSessionMeta → renderSessionCost
```

**`hub_statusline.py`**: 모듈 docstring 의 실행 순서 서술(「stdin 을 한 번만 파싱」)을 유지한다. `parse_status_line_captures` 하나로 두 캡처를 만든다. 출력이 먼저이고 파일 작업은 그 뒤다. 두 캡처가 다 없으면 파일 I/O 0회다. 예외는 기존 `main()` 이 삼킨다(`rules/python/hooks.md`).

**화면(안 A 권고)**

- CSS — **기존 공유 규칙 `.session-id,.session-model{…}` 는 건드리지 않는다.** T25-153 이 그 셀렉터 리터럴을 문다. 별도 규칙을 하나 더한다:
  `.session-cost{background:var(--soft);border-radius:5px;padding:0 6px;white-space:nowrap}`
  새 색 토큰은 0개다. 세로 패딩이 없어 줄 높이는 그대로다(MC 결정과 같은 이유).
- JS — `renderSessionMeta` 끝에 `+ renderSessionCost(session.session_cost)`. 값이 없으면 빈 문자열이라 줄이 생기지 않는다. 첫 줄(`.session-line`)에는 넣지 않는다. T25-127 의 「첫 줄로 새지 않는다」 불변과 맞는다.
- 안 B 를 고르면 같은 함수를 `renderSessionContent` 의 `.session-time` 뒤에 붙인다. CSS 는 `.session-cost{font-size:11px;color:var(--muted);white-space:nowrap}` 로 바뀐다. 이때 T25-127 의 첫 줄 금지 목록(`session-id|session-meta|renderSessionMeta`)에는 걸리지 않는다.

---

## 6. 데이터 모델

### 6-1. ⑨ 세션 비용 캡처

```python
# hub/bin/hub_usage.py (★순수 — 파일시스템·시각·환경변수에 닿지 않는다)

@dataclass(frozen=True)
class SessionCost:
    """statusLine 이 한 세션에 대해 마지막으로 알려 준 누적 비용·API 시간·컨텍스트 사용률(⑨).
    내용(프롬프트·응답)은 없다. 화면 투영 타입을 겸한다(SessionModel 이 hub_transcript 에 있는 것과 같은 관례)."""

    captured_at_ms: int                  # 이 값들을 처음 관측한 시각(RateLimitCapture 와 같은 뜻 — 결정 S3)
    total_cost_cents: int | None         # cost.total_cost_usd × 100 을 내림한 정수. 정가 기준 추정 — 구독 과금과 무관
    api_duration_minutes: int | None     # cost.total_api_duration_ms 를 분으로 내림
    context_used_percent: int | None     # context_window.used_percentage 를 내림한 정수(0~100)


@dataclass(frozen=True)
class SessionCostCapture:
    """statusLine stdin 1건에서 판 세션 비용 — 어느 세션의 것인지를 함께 나른다."""

    session_id: str                      # UUID 형식 검증을 통과한 값만(파일 이름 키로 쓰인다)
    cost: SessionCost


@dataclass(frozen=True)
class StatusLineCaptures:
    """statusLine stdin 을 한 번 파싱해 만든 두 캡처. 각각 독립적으로 없을 수 있다."""

    rate_limits: RateLimitCapture | None
    session_cost: SessionCostCapture | None
```

**상수**(같은 모듈, 이름 있는 상수 — 「왜」 주석과 함께)

| 상수 | 값 | 이유 |
|---|---|---|
| `CENTS_PER_USD` | 100 | 센트 정수로 내려 부동소수 잡음을 없애고 쓰기 억제 비교를 단순하게 한다 |
| `SESSION_COST_MAX_USD` | 100000 | 외부 값 검증 상한 — 단위 혼동(센트를 달러로 보낸 값 등)과 NaN·무한대를 버린다. 정확한 크기는 중요하지 않다(`RATE_LIMIT_MAX_HORIZON_DAYS` 와 같은 성격) |
| `SESSION_COST_MAX_CENTS` | `SESSION_COST_MAX_USD × CENTS_PER_USD` | 캡처 파일 쪽 상한(구현 중 추가) |
| `CENTS_FLOAT_NOISE_DIGITS` | 6 | `0.29 * 100 == 28.999999999999996` 이라 그대로 내림하면 1센트를 잃는다 — 내림 전에 이 자릿수로 반올림해 곱셈 잡음만 걷는다(구현 중 추가) |
| `MILLISECONDS_PER_MINUTE` | 60000 | API 시간 분 단위 내림 |
| `SESSION_API_DURATION_MAX_DAYS` · `_MS` · `_MINUTES` | 365일 · 파생 · 파생 | `SESSION_COST_MAX_USD` 와 같은 성격의 외부 값 상한 — 1e308 같은 값이 그대로 저장·표시되지 않게 한다(2회차 LOW) |
| `SESSION_ID_PATTERN` | `[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}` (`fullmatch`, 앵커 없음) | `hub_dashboard_log._SESSION_ID_PATTERN` 과 같은 정의의 작은 사본(경로 탈출 차단 — `/`·`..` 가 매치될 수 없다). 그 모듈은 I/O 층이라 순수 모듈이 임포트하지 않는다 |

**검증 규칙**(필드별 독립 탈락 — `parse_status_line_rate_limits` 와 같은 태도)

- `session_id` 가 패턴 불일치면 `session_cost` 전체가 None 이다.
- `cost.total_cost_usd`: 유한한 수 · 0 이상 · `SESSION_COST_MAX_USD` 이하 → `floor(×100)`. `bool` 은 거부한다.
- `cost.total_api_duration_ms`: 유한한 수 · 0 이상 · `SESSION_API_DURATION_MAX_MS` 이하 → 분 단위 내림. 터무니없이 큰 정수는 `isfinite` 에 넘기지 않는다(`OverflowError`).
- `context_window.used_percentage`: 기존 `_valid_used_percentage`(실수 허용 후 내림 — rate_limits 와 같은 추출기) 재사용. 처음 설계가 적은 `_is_valid_percent` 는 엄격 정수라 실수가 오면 필드를 버린다 — 캡처 파일 쪽에만 쓴다(구현 이탈 기록 7).
- 세 값이 전부 None 이면 `session_cost` 는 None 이다.

**캡처 파일** — `~/.claude/hub/session_costs/<session_id>.json`, 원자적 쓰기(`hub_atomic_write.atomic_write_text`, 접두 `session_cost.`)

```json
{"captured_at_ms": 1759900000000, "total_cost_cents": 1284, "api_duration_minutes": 31, "context_used_percent": 62}
```

- 파일 계약 위반(필드 타입 불일치·범위 밖 — 센트는 `SESSION_COST_MAX_CENTS`, 분은 `SESSION_API_DURATION_MAX_MINUTES` 이하, 퍼센트는 엄격 정수)이면 `parse_session_cost_capture` 가 None 을 낸다. 수집은 그 세션의 칩을 그리지 않는다(경고는 내지 않는다 — 세션별 파일이라 경고가 세션 수만큼 늘 수 있다).
- 보관: 수집이 `config.event_retention_days`(기본 7일) 보다 오래된 파일(mtime 기준)을 지운다.
- 쓰기 억제: `captured_at_ms` 를 뺀 세 값이 이전과 같으면 쓰지 않는다(결정 P4 와 같은 이유 — 0.3초 주기의 쓰기가 정상 상태에서 0회).

**뷰** — `SessionView` 맨 뒤에 `session_cost: SessionCost | None = None`. 맨 뒤 자리를 `background_wait` 에서 넘겨받는다. T25-150 이 마지막 필드 이름을 고정 검사하므로 함께 갱신한다(§9). `asdict` 직렬화라 `hub_model` 은 바뀌지 않는다. 값은 파일 내용의 함수라 「지금」 파생값이 아니다. content key 가 바뀌는 것은 값이 실제로 바뀔 때뿐이다.

### 6-2. ⑫ FAIL 사유 범주 어휘 (폐쇄 어휘, 정의의 정본은 `agents/code-reviewer.md`)

| 범주 | 뜻 | 흔한 `[분류]` | Terminal-Bench 축 |
|---|---|---|---|
| `실행` | 실행하면 잘못된 결과가 나온다 — 테스트·빌드 실패, 재현된 버그·보안 동작 | 보안 · 성능 · 테스트(실패) | Execution |
| `검증` | 검증이 모자라다 — 테스트 누락, 대상 동작을 물지 않는 테스트, RED 증거와 실제의 불일치 | 테스트 | Verification |
| `정합` | 동작은 하지만 PRP·규칙과 어긋난다 — 설계에 없는 변경, 구조·가독성 규칙 위반, 정적 지표·정적 보안 패턴 | 설계문서 불일치 · 구조 · 가독성 · 설계 | Coherence |
| `설계` | 원인이 PRP 자체다 — 모호·누락·모순이라 구현만 고쳐서는 해소되지 않는다 | — | (coding-harness 추가 — 「3회 FAIL = 설계 문제」 검증용) |

- 사유 범주 `설계` 는 보고 양식 `[분류]` 의 `설계`(구현의 패턴·YAGNI 위반)와 이름만 같다 — 구현의 설계 문제는 사유 범주로는 `정합` 이고, `설계` 는 PRP 를 고쳐야 풀릴 때만 쓴다. 이 구분과 위 「흔한 `[분류]`」 대응을 `agents/code-reviewer.md` 「사유 범주」에 그대로 적었다(2회차 M1 — 범주 이름은 바꾸지 않았다).
- 표기: `[실행,검증]` — 쉼표로 구분하고 공백은 두지 않는다. FAIL 을 만든 CRITICAL/HIGH 지적들의 범주 합집합이다.
- PASS 에는 붙이지 않는다.
- 기록: 메인은 `log fail '<요약>' '[실행,검증] <상세>'` 로 Verdict 의 대괄호를 그대로 옮긴다.
- 파생(새로 기록하지 않는다): **경로** = `init` 의 단계 목록에 `설계` 가 있으면 전체, 없으면 축약. **회차** = 허브의 pass/fail 누적.

---

## 7. 인터페이스

### 7-1. Python (⑨)

```python
# hub/bin/hub_usage.py — ★순수
def parse_status_line_captures(text: str, captured_at_ms: int) -> StatusLineCaptures:
    """statusLine stdin 을 한 번 파싱해 한도 캡처와 세션 비용 캡처를 함께 만든다(JSON 이 아니면 둘 다 None)."""

def parse_status_line_rate_limits(text: str, captured_at_ms: int) -> RateLimitCapture | None:
    """기존 시그니처·동작 그대로. 내부를 dict 입력 헬퍼(_rate_limits_from_payload)로 옮겨 위 함수와 공유한다."""

def parse_session_cost_capture(text: str) -> SessionCost | None:
    """캡처 파일 본문을 SessionCost 로 판다. 계약 위반이면 None(예외 없음)."""

def same_session_cost_values(previous: SessionCost | None, current: SessionCost) -> bool:
    """captured_at_ms 를 뺀 세 값이 모두 같은가 — 같으면 다시 쓰지 않는다."""

def is_valid_session_id(value: object) -> bool:
    """UUID 소문자 형식인가 — 파일 이름 키로 쓸 수 있는 값만 True."""


# hub/bin/hub_session_cost.py — I/O 층(새 모듈). 임포트: hub_atomic_write, hub_usage(둘 다 hub_collect 를 임포트하지 않는다 — 순환 없음)
HUB_HOME = Path.home() / ".claude" / "hub"          # hub_server_state_read 와 같은 지역 선언 관례
SESSION_COSTS_DIR = HUB_HOME / "session_costs"

def read_session_cost(session_id: str) -> SessionCost | None:
    """세션 하나의 캡처를 읽는다. 형식이 틀린 ID·부재·읽기 실패·계약 위반은 전부 None(예외 없음)."""

def write_session_cost(session_id: str, cost: SessionCost) -> None:
    """원자적으로 쓴다(hub_statusline 전용 쓰기 경로). 형식이 틀린 ID 면 아무것도 하지 않는다."""

def read_session_costs(session_ids: Iterable[str]) -> dict[str, SessionCost]:
    """수집용 — 캡처가 있는 세션만 담은 dict."""

def prune_old_session_cost_files(now_ms: int, retention_days: int) -> None:
    """보관 기간을 넘긴 캡처 파일을 지운다. 파일 단위로 실패를 흡수한다(_cleanup_stale_session_dashboards 와 같은 태도)."""


# hub/bin/hub_session.py
def compute_session_view(..., last_human_prompt_at_ms: int | None = None,
                         session_cost: SessionCost | None = None) -> SessionView: ...
# hub/bin/hub_project.py — 세 함수에 session_cost_by_session_id: dict[str, SessionCost] 통과 인자 추가
#   compose_project_views(...) → _project_view_for_path(...) → _session_views_for_path(...)
#   _session_views_for_path 는 session_cost=session_cost_by_session_id.get(facts.session_id) 로 넘긴다
# hub/bin/hub_collect.py
def _prune_and_read_session_costs(sessions_by_path, now_ms, config) -> dict[str, SessionCost]:
    """보관 기간이 지난 캡처 파일을 지우고(이름에 정리 부작용을 드러냈다 — 2회차 LOW), 보이는 세션들의 캡처를 읽는다."""
```

### 7-2. JS (`hub_template.html`, 순수 함수 3 + 렌더 1 — `sessionCostAmountLabel` 을 구현 중 더했다)

```js
var SESSION_COST_SR_LABEL = '세션 비용 ';
var SESSION_CONTEXT_LABEL = '컨텍스트 ';
var SESSION_COST_TOOLTIP_PREFIX = 'statusLine 이 알려 준 세션 누적값 — 정가 기준 추정, 구독 요금과 무관';
// (구현 중 더한 상수: SESSION_API_TIME_TOOLTIP_LABEL · SESSION_API_TIME_UNDER_ONE_MINUTE · SESSION_COST_APPROX_PREFIX ·
//  SESSION_COST_LABEL_SEPARATOR · CENTS_PER_DOLLAR · SESSION_COST_WHOLE_DOLLAR_FROM)
// 순수. 센트 정수 → "≈$12.84"(100달러 미만) · "≈$123"(100달러 이상은 정수). 정수 연산만 쓴다.
function sessionCostAmountLabel(totalCostCents) {}

// 순수. 예: "≈$12.84 · 컨텍스트 62%", "≈$123 · 컨텍스트 91%"(100달러 이상은 정수), "≈$0.03", "컨텍스트 62%". 둘 다 없으면 ''.
function sessionCostLabel(cost) {}
// 순수. 접두 + (api_duration_minutes 가 있으면 " · API 시간 N분", 0 이면 "1분 미만").
function sessionCostTooltip(cost) {}
// cost 가 없거나 label 이 '' 면 ''. 아니면 <span class="session-cost" data-tooltip="…"><span class="sr-only">세션 비용 </span>라벨</span>
function renderSessionCost(cost) {}
```

### 7-3. 에이전트 보고 계약(프롬프트 인터페이스)

| 생산자 | 소비자 | 계약 |
|---|---|---|
| implementer 완료 보고 | 메인 → code-reviewer | `테스트 스펙` · `RED 증거`(명령·출력 1~3줄·GREEN 명령) · `계획 대조` 3항목 추가(전체 경로) |
| code-reviewer 보고 | 메인 → implementer | `[재현]` 칸(CRITICAL/HIGH 필수) · 보고서 머리 기준 SHA · `Verdict: FAIL [범주,…] — …` |
| 메인 | 허브 원장 | `log fail '<요약>' '[범주,…] <상세>'` |

### 7-4. ⑨ 프리뷰 목업

- 목업 HTML: `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/d6fb3cf9-f0ef-48b5-977c-96f85f9eec39/scratchpad/mockups/session-cost-preview.html`
- 렌더 PNG: 같은 폴더의 `session-cost-preview.png`
- 생성 스크립트: 같은 세션 폴더의 `mockup-tools/build_session_cost_mockup.py` — `hub_template.html` 의 `<style>` 블록을 그대로 싣는다.
- 구성: 「현재 | 안 A | 안 B」를 라이트 320px(그리드 최소 트랙)·라이트 461px(1440px 화면 3열)·다크 320px 세 줄로 놓았다. 각 카드의 첫 세션은 hover 강제, 셋째 세션은 열린 카드 상태다. 둘째 세션은 데이터가 많은 경우다(백그라운드 대기 + 출력 갱신 + 긴 모델명 + `$123` + 91%).
- 관측(헤드리스 Chrome): 320px 에서 식별 줄은 이미 모델 칩에서 줄바꿈된다. 안 A 의 칩은 그 둘째 줄에 들어가 **추가 줄 0** 이다. 안 B 는 백그라운드 세션의 첫 줄이 넘쳐 **1줄 추가**된다. 461px 에서는 둘 다 추가 줄 0 이다.
- 목업 전용 장치는 `.mock-` 접두다(제목·라벨·격자·다크 래퍼·hover 강제·변형 범위 접두 `.mock-variant-a/-b`). 범위 접두 뒤의 선언이 구현 CSS 그대로다.
- 이 경로는 세션 임시 폴더라 사라진다. 승인 판단용이고 구현은 §5-7 의 CSS·JS 명세를 따른다.

---

## 8. 설계 결정의 근거 — 패턴과 단순성

- 새 디자인 패턴은 없다. ⑨ 는 기존 「파서(★순수) + 캡처 파일 + 수집 통과 배선」 관례를 그대로 따른다(rate_limits 캡처·WF1 통과 배선과 같은 모양).
- 새 모듈은 `hub_session_cost.py` 하나다. 800줄 상한 때문에 강제된 분리다(D8).
- 설정 스위치·새 이벤트 종류·파서 해석은 만들지 않는다(D5·D9, YAGNI).
- 에이전트 변경은 산문 계약이라 단위 테스트할 순수 로직이 없다. 회귀 방지는 정적 토큰 가드(§9)로만 하고, 효과는 도입 전후 비교(§11)로 본다.

---

## 9. T 그룹·상수 영향

### 9-1. 상시 컨텍스트

| 대상 | 변화 | 근거 |
|---|---|---|
| T26(`ALWAYS_ON_CONTEXT_BUDGET_BYTES`=54,238) | **0B** | CLAUDE.md·rules/README.md·rules/common·rules/workflow 를 건드리지 않는다(D1·D2·D4) |
| T26-2(README 「실측 <n>B」 2건) | 0 | README 편집이 그 패턴을 건드리지 않는다 |
| T40-5(`HUB_DASHBOARD_RULE_BUDGET_BYTES`=1345) | **+약 60B** → 편집 후 실측치로 갱신 | ⑫ 1행. 허브 사용자에게만 상시 로드된다. 사유는 커밋에 남긴다 |

### 9-2. 바뀌는 토큰별 가드 대조 (개명·삭제 전 grep 결과)

| 바뀌는 토큰 | 걸리는 가드 | 조치 |
|---|---|---|
| agents 의 `Task` | `tests/run.sh`·`tests/mutations.tsv`·README 에 0건(설계 시 grep) | 없음. `hub_activity.py` 의 `"Task": "delegate"` 는 도구 이름 매핑이라 무관하다 |
| frontmatter 새 키(`effort:`·`omitClaudeMd:`)와 `Agent` 정식 이름 | 기존 가드 0건 | 새 T31-10 이 문다 |
| `agents/code-reviewer.md` 의 `[제안]`·절차 번호 | T38-3 은 `재검수 모드` 만 본다. 「절차 7」 인용은 같은 파일 재검수 모드와 `NOTICE.md` §5 행에만 있다 | 재검수 모드 상호참조와 NOTICE 문구를 함께 고친다 |
| `commands/code-review.md` 의 `Suggested fix` | 0건(T38-3 은 `VALIDATE (light)` 만 본다) | 없음 |
| 배포 트리의 `파일명.확장자:숫자` 인용 | T39-4(`LINE_CITATION_RATCHET_DEPLOYED`=1, 이미 1건) | 새 문장에 쓰지 않는다 |
| rules/ 안의 미배포 에이전트 이름 | T29-1(rules/ 만 스캔) | 무관(rules/ 를 건드리지 않는다) |
| `SessionView` 마지막 필드 | **T25-150** — 마지막 필드 = `background_wait` 고정 검사 | 마지막 필드 단언을 `session_cost: SessionCost | None = None` 으로 바꾼다. `background_wait` 는 존재 단언으로 남긴다. 원장 T25-150 변조행(`model:` 줄 대상)은 그대로 유효하다 |
| `HUB_FILE_COUNT` 32→33 | T25-1(선언=실제) · **T25-104**(「32개 파일」 고지 + 옛 수 부재) · **T25-149**(값 32 고정 + README 「32개 파일」) | T25-104: 「33개 파일」 존재 + 「32개 파일」 부재를 옛 수 목록에 추가. T25-149: 기대 33. 원장 T25-104 sed `s/33개 파일을,/33개 파일을(구 12개 파일),/`, T25-149 sed `s/33개 파일/32개 파일/` 과 기대 토큰의 숫자. 행 수는 바뀌지 않는다 |
| 칩 공유 규칙 `.session-id,.session-model{…}` | T25-153(셀렉터 리터럴) | 건드리지 않는다 — 별도 `.session-cost{…}` 규칙(§5-7) |
| 첫 줄 구성 | T25-127(첫 줄에 `session-id|session-meta|renderSessionMeta` 금지) | 안 A 는 첫 줄을 건드리지 않는다. 안 B 도 금지 토큰을 쓰지 않는다 |
| 순수 모듈 목록 | T25-10(`hub_usage.py` 이미 포함) | 새 I/O 모듈은 순수가 아니라 목록에 넣지 않는다. `hub_usage.py` 에 `open(`·`Path(`·`os.` 를 쓰지 않는다 |
| 800줄 상한 | T25-100 | `hub_collect.py` 773 → 790줄(헬퍼 14줄 + 인자 줄 — 처음 추정 777 은 `collect_snapshot` 50줄 상한을 고려하지 않았다) |
| `/hub` argument-hint · 「전역 훅 7」 | T23-6·T25-48·T25-241 | 서브커맨드·훅 수를 바꾸지 않는다 |
| `AGENTS_FILE_COUNT`·`COMMANDS_FILE_COUNT`·`RULES_FILE_COUNT` | T30·T22-138·T39-2 | 불변 |
| `data-tooltip="` 리터럴 20건 고정 | **T25-201** | **설계 때 놓쳤다** — 새 칩의 툴팁이 +1 이라 구현 중 실패로 발견했다. 기대를 21 로 올리고 `hub/README.md` 툴팁 트리거 서술에 반영한다 |
| 서브 `tests/hub` 의 실제 홈 접촉 | `tests/hub/__init__.py` | `collect_snapshot` 이 이제 캡처 파일을 지우고 읽는다 — `SESSION_COSTS_DIR` 을 존재하지 않는 경로로 중화한다(`CLAUDE_GLOBAL_CONFIG_PATH` 선례) |
| `SOURCE_GUARD_ID_FLOOR` | T37-11 + 원장 헤더 인용 | 537 → 539(새 ID 2개의 여유 회수 — 저장소 관례) · 헤더 `SOURCE_GUARD_ID_FLOOR(…)` 인용도 맞춘다 |

### 9-3. 새 정적 가드 (T31 그룹 함수 `test_rules_workflow_guardrails` 안 — D6)

| ID | 검사(전부 grep, 실행 시간 <0.1초) | 실패 메시지 판별 토큰(보고 줄에서 유일) |
|---|---|---|
| **T31-10** 서브에이전트 frontmatter 계약 | (a) `design-architect`·`implementer`·`code-reviewer` 의 frontmatter `tools:` 줄에 정식 이름 `Agent` 토큰이 있고, 옛 이름 `Task` 와 괄호 목록 `Agent(…)` 토큰이 없다(표기 일관성 가드 — 서브에이전트 정의에서는 괄호 목록이 무시된다, 문서 506행. 스폰이 기계로 막힌다는 보증이 아니다). (b) 같은 세 파일 frontmatter 에 `^effort: (low|medium|high|xhigh|max)$` 가 있다(값은 잠그지 않는다 — 조정은 설계 결정이다). (c) `explore.md` frontmatter 에 `omitClaudeMd: true` 가 있고 `effort:` 가 없다. frontmatter 범위는 첫 `---` 쌍 사이로 자른다 | `T31-10:` 접두 + (a)·(b)·(c) 별 다른 문구 |
| **T31-11** 증거 계약 토큰 | 그룹 함수 안 **지역** 평탄 배열(경로, 토큰): `agents/code-reviewer.md` → `[재현]` · `미검증 주장` · `사유 범주` / `commands/code-review.md` → `Reproduction` / `agents/implementer.md` → `사전 조건` · `RED 실행 명령` · `계획 리마인더` | `T31-11:` 접두 + 경로·토큰 |

- T31 그룹 설명 문자열 `(T31-1~T31-9)` → `(T31-1~T31-11)`.
- 머리 주석에 두 가드의 기제와 한계를 쓴다(기존 T31-6~9 문단과 같은 형식). 한계 예시: 같은 뜻을 다른 낱말로 되돌리는 편집, 토큰은 남기고 의미를 뒤집는 편집, 에이전트가 계약을 실제로 지키는지는 보지 못한다. 위양성이 나면 고칠 것은 대상 문단이 아니라 토큰 목록이다.
- 원장: 두 ID 를 **면제행**으로 등록한다(D7). 사유 문구 「정적 grep 가드 — 변조 검증은 구현 시 수동 1회(docs/prps/harness-benchmark-adoption.md §10-3)로 대신한다. K6 시간 예산 보호(사용자 결정 2026-10-08)」, `anchor_function` 은 `-`. 공통 사유(「S3 이전에 존재한 가드」)를 쓰지 않으므로 헤더의 「아래 269개는」 인용(T99-6)은 변하지 않는다.
- 면제행 상한: 등록 뒤 T37-14 가 세는 면제행 수가 `LEDGER_EXEMPT_ROW_RATCHET`(372)를 넘으면 그 상수를 실측치로 올린다(단일 줄 `readonly` 라 K6 FULL 트리거가 아니다). 사유: 「정적 가드 2건 — 변조행 미등록은 사용자 결정(K6 시간 보호)」.
- **T38 `PATCH_CONTRACT_PAIRS` 에는 넣지 않는다.** 최상위 배열 변경은 증분 K6 를 전체 재확인(약 23분)으로 바꾼다. 이 저장소 원장이 정한 정본 경로이고, 이번 설계가 피하려는 시간이다.
- `NOTICE.md` §5 커버리지 표: `agents/code-reviewer.md` 행의 잠기는 성분에 「재현 형식 · 미검증 주장 순서 · 사유 범주(T31-11)」를, `commands/code-review.md` 행에 「Reproduction 요구(T31-11)」를 더한다. 검사 칸에도 T31-11 을 덧붙인다. 정본 목록 두 행의 패치 요지에 이번 성분을 더하고 누적 커밋 수를 고친다(구현이 `git log --oneline -- <파일>` 로 센다).

### 9-4. K6 영향 (증분 선택기 기준)

| 커밋 | 고르는 기존 변조행(대략) | 이유 |
|---|---|---|
| C1·C2·C3 | T31-7(design-architect) · T38-3(code-reviewer) · T31 그룹 블록 안 행(R3·R5) | 대상 파일·그룹 블록 변경 |
| C4 | T40 의 `dashboard-recording.md` 대상 4행 + `HUB_DASHBOARD_RULE_BUDGET_BYTES` 참조 행(R4) + `hub/README.md` 대상 12행 | 대상 파일·상수 변경 |
| C6 | 약 130행(§3-1 ⑨ 행) | 대상 파일 변경. 일회성 |

새 변조행은 0행이다. 전체 재확인(`CODING_HARNESS_K6_FULL=1`)의 소요(27분)는 이 설계로 늘지 않는다(정적 가드 2건 <1초).

---

## 10. 테스트 계획

### 10-1. 단위 테스트 (⑨, stdlib unittest — `python3 -m unittest discover -s tests/hub -t .`)

| 대상 | 케이스 | 무엇이 실패하면 잡히나 |
|---|---|---|
| `parse_status_line_captures` | ① 세 필드 정상 → 센트 내림(12.849 → 1284)·분 내림·퍼센트 내림 ② `rate_limits` 만 / `cost` 만 / 둘 다 / 둘 다 없음 ③ JSON 아님·배열 → 둘 다 None ④ `session_id` 가 UUID 아님(`../x`, 대문자, 빈 값) → `session_cost` None ⑤ `total_cost_usd` 가 음수·NaN·무한대·`True`·`SESSION_COST_MAX_USD` 초과 → 그 필드만 None ⑥ 세 값 전부 무효 → `session_cost` None ⑦ 기존 `parse_status_line_rate_limits` 결과와 `.rate_limits` 가 같은 입력에서 동일 | 단위 혼동·경로 탈출·한 번 파싱 계약 회귀 |
| `parse_session_cost_capture` | 정상 왕복(asdict→json→parse) · 필드 누락 · 타입 불일치 · 범위 밖 퍼센트 → None | 파일 계약 위반 시 예외 전파 |
| `same_session_cost_values` | 이전 None → False · `captured_at_ms` 만 다름 → True · 한 필드 다름 → False | 0.3초 주기 쓰기 폭주(P4 회귀) |
| `hub_session_cost` (임시 `HUB_HOME`·`SESSION_COSTS_DIR` 교체 — `rules/python/testing.md` 관례) | 쓰기→읽기 왕복 · 디렉터리 없음에서 쓰기 · 잘못된 ID 쓰기 무동작 · 깨진 파일 읽기 None · `read_session_costs` 가 있는 것만 · 보관 기간 넘은 파일만 정리(mtime 조작) | 사용자 데이터 경로 오류·정리 과잉 |
| `hub_statusline._run` | stdin 에 `cost` 포함 → 출력 줄은 기존과 같고 세션 파일 생성 · 같은 값 두 번 → 두 번째 쓰기 없음(mtime 불변) · 둘 다 없으면 파일 I/O 0회 · `main()` 이 예외에도 0 | 상태줄 깨짐·쓰기 억제 회귀 |
| `compute_session_view` | `session_cost` 를 넘기면 뷰에 실리고 기본은 None | 배선 누락 |
| DOM(`test_hub_template_dom_session_row.py` 에 1메서드) | `session_cost` 가 있으면 `.session-meta` 안에 `.session-cost` 1개·라벨 문구·`data-tooltip` 존재 · null 이면 0개 · `.session-line` 안에는 0개(안 A) | 화면 배치 회귀 |

### 10-2. 정적 가드 (§9-3)

T31-10·T31-11 은 `bash tests/run.sh --only T31` 로 돈다(수 초).

### 10-3. 새 가드를 일부러 깨뜨려 실패하는지 확인 (구현 시 수동 1회, 결과를 구현 보고에 적는다)

격리 사본(`git worktree` 또는 임시 복사본)에서 아래 변조를 하나씩 적용한다. `bash tests/run.sh --only T31` 이 **해당 ID 로** 실패하는지 확인하고, 사본을 버린다. 원본 체크아웃은 건드리지 않는다.

| 변조 | 기대 |
|---|---|
| `agents/implementer.md` 의 `Agent` → `Task` / `agents/design-architect.md` 의 `Agent` 옆에 `Task` 추가 / `agents/code-reviewer.md` 의 `Agent` 옆에 `Agent(Explore)` 추가 / `agents/implementer.md` 에서 `Agent` 삭제 | T31-10 (a) 각각(2회차에 4건 모두 확인) |
| `agents/code-reviewer.md` 의 `effort: high` 줄 삭제 | T31-10 (b) |
| `agents/explore.md` 의 `omitClaudeMd: true` 삭제 / `effort: low` 추가 | T31-10 (c) 각각 |
| `agents/code-reviewer.md` 의 `[재현]` → `[제안]` | T31-11 |
| `commands/code-review.md` 의 `Reproduction` → `Suggested fix` | T31-11 |
| `agents/implementer.md` 의 `계획 리마인더` 삭제 | T31-11 |

⑨ 의 수정된 기존 가드(T25-104·T25-149·T25-150)는 기존 변조행이 K6 에서 확인한다(행 내용만 갱신, §9-2).

### 10-4. 프롬프트 계약(①③⑥⑦⑧⑫)

정적 토큰 말고는 기계 검사가 없다. 실제로 지켜지는지는 첫 전체 경로 과제의 검수·구현 보고를 메인이 확인하고, 효과는 §11 로 잰다.

### 10-5. 검증 명령 (CLAUDE.md §4 정본)

```bash
bash tests/run.sh                                  # 메인이 커밋 직전 1회(C6 는 증분 K6 약 +10~15분)
python3 -m unittest discover -s tests/hub -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

검수자는 닿은 그룹만 돌린다 — C1~C3 `--only T31 T38 T39`, C4 `--only T40 T25`, C6 `--only T24 T25`.

---

## 11. 도입 전후 비교 계획

측정은 **도입 뒤**에 한다. 이 설계 단계에서는 재측정하지 않는다. 체감 보고는 근거로 쓰지 않는다(숙련 개발자의 체감과 실제가 40pp 어긋났다 — [METR 2025](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)).

| 지표 | 기준선(이미 측정) | 도입 후 측정 방법 | 기대 방향 |
|---|---|---|---|
| 과제당 에이전트 가동 시간 중앙값 | 270분(9월 하순) | 기준선과 같은 방법 — 대화 기록의 서브에이전트 실행(subagents/*.jsonl) 시각 집계 | ↓ 또는 유지(①의 왕복 감소 vs ⑥⑧의 소폭 증가) |
| 재호출 라운드 비중 | 가동의 25%(47회·986분) | 같은 방법 — 메인의 재디스패치 라운드 분류 | ↓ (①: 거짓 HIGH 감소) |
| 전체 검사 시간 | 27분(`CODING_HARNESS_K6_FULL=1`, K6 23분) | 1회 실행 | 유지(±1분 — 변조행 0행 추가) |
| 서브에이전트 effort 분포 | 세션 값 복제(9/9) | 서브 기록 줄 최상위 `effort` 집계 | 설계 xhigh·구현/검수 high 로 고정 |
| 회차당 FAIL 사유 범주 분포 | 없음(새 데이터) | `.claude/dashboards/*.jsonl` 의 `fail` 상세 대괄호 집계 × 회차 × 경로 | 「3회차 FAIL 에서 `설계` 비중이 높은가」 판정 |
| CRITICAL/HIGH 중 하향 비율 | 없음 | 검수 보고의 「없음 — 하향」 수 / CRITICAL·HIGH 수 | 기록만(높으면 ① 의 하향 기준 재검토) |
| 세션당 추정 비용·API 시간 | 없음 | ⑨ 캡처(`session_costs/*.json`) | 새 기준선(첫 데이터) |

- **시점**: `/harness-update` 반영 뒤 전체 경로 과제 5건 이상 또는 2주 중 늦은 쪽. 사용자 요청 시 메인이 수행한다.
- **기록**: 결과는 이 문서 부록 C 와 메인의 작업 시간 기준선 메모리에 남긴다.
- **해석 한계**: 과제 구성이 달라 인과를 단정하지 않는다. 중앙값과 n 을 함께 적는다. n<10 이면 방향만 적는다.
- **되돌림 조건**: 과제당 가동 또는 재호출 라운드가 기준선보다 15% 넘게 나빠지고, 대화 기록에서 그 증가가 ①(재현 턴)·⑥(재읽기 턴)에 귀속되면 해당 항목의 완화책을 강화한다(예: ① 을 CRITICAL 만 의무, ⑥ 을 마지막 단계 전 1회로). 그 개정은 별도 축약 경로 과제다.

---

## 12. 구현 단계 분할 (커밋 단위)

각 커밋은 「구현 → 검수(닿은 그룹만) → 메인 전체 검증 1회 → 커밋」이다. 순서는 위험이 작고 K6 비용이 작은 것부터다.

| 커밋 | 내용 | 검증 |
|---|---|---|
| **C1** `feat: 작업 에이전트가 정해진 사고 깊이로 돌고 탐색 에이전트만 부를 수 있게 한다` | §5-1 frontmatter 4파일 + implementer·code-reviewer 탐색 위임 1구 + explore description + README §5-5 + T31-10 + 원장 면제행 1 | `--only T31 T30 T39` · §10-3 의 T31-10 변조 4건 |
| **C2** `feat: 검수자가 중대 지적에 재현 증거를 붙이고 실패 사유를 범주로 적는다` | §5-2 본문 · §5-3 · NOTICE §5 두 행·커버리지 두 행 · T31-11(code-reviewer·code-review 토큰) + 원장 면제행 1 · 필요 시 `LEDGER_EXEMPT_ROW_RATCHET` | `--only T31 T38 T39` · §10-3 의 T31-11 변조 2건 |
| **C3** `feat: 구현자가 실패 증거·설계 대조 결과를 보고하고 단계마다 설계를 다시 맞춘다` | §5-4 본문 · T31-11 에 implementer 토큰 3개 | `--only T31 T39` · §10-3 의 implementer 변조 1건 |
| **C4** `feat: 허브 진행 기록에 검수 실패 사유 범주를 남긴다` | §5-6 · `HUB_DASHBOARD_RULE_BUDGET_BYTES` 실측 갱신 | `--only T40 T25 T33 T34` |
| **C5** `docs: 서브에이전트 기본 비용을 한 번 재서 기록한다` | ⑩ 측정(§13-1) → 부록 B. ⑪ 결과는 사용자가 전해 주면 부록 C | 측정 출력 원문을 부록에 붙인다 |
| **C6** `feat: 허브 세션 줄에 추정 비용과 컨텍스트 사용률을 보여 준다` | §5-7 · §6-1 · §7-1·7-2 · 문서·`HUB_FILE_COUNT`·T25-104/149/150·원장 2행 갱신 · 단위·DOM 테스트 · 안 A/B 중 승인된 쪽 | `--only T24 T25 T40` + unittest + py_compile. 메인 전체 검증은 증분 K6 약 +10~15분(일회성) |

- C1~C3 은 같은 PR 묶음이어도 된다. C6 는 마지막에 단독으로 둔다(K6 비용을 한 번만 치른다).
- 동시 세션 주의: 다른 세션이 같은 저장소에 커밋 중이다. 각 커밋 직전에 `git log origin/main..` 과 `git status` 로 섞임을 확인한다. 원장·`tests/run.sh` 의 새 ID 번호(T31-10·T31-11)가 다른 세션과 겹치지 않는지 병합 직전 main 을 다시 센다.

---

## 13. 사용자 수행 항목과 측정 절차

### 13-1. ⑩ null-op 측정 (구현 단계 C5, 세션이 수행)

1. **버전 맞추기**: 세션 런타임은 2.1.293(데스크톱 진입점)인데 PATH 의 `claude` 는 **2.1.108** 이다(설계 시 확인). 그대로 재면 다른 버전을 잰다. 데스크톱 번들 CLI 경로를 찾거나 사용자가 CLI 를 갱신한 뒤 잰다. 둘 다 안 되면 버전 불일치를 부록에 적고 근사치로 취급한다.
2. 빈 임시 디렉터리와 저장소 루트에서 각각 `claude -p "ok" --model haiku --output-format json` 을 1회 실행한다. 출력의 `usage` 에서 `input_tokens`·`cache_creation_input_tokens`·`cache_read_input_tokens` 와 그 합을 적는다. 두 위치의 차이가 프로젝트 CLAUDE.md 몫이다.
3. Explore 를 한 번 디스패치한다(사소한 검색 1건). 그 서브 기록의 첫 요청 입력 토큰과 CLAUDE.md·규칙 문구 포함 여부를 확인한다. `omitClaudeMd` 가 규칙(`~/.claude/rules`)까지 빼는지 이 자리에서 판정한다.
4. 부수 효과: `claude -p` 실행도 허브 훅을 발화시켜 허브에 짧은 세션 줄이 하나 생긴다(무해, 7일 뒤 정리).

### 13-2. 사용자가 직접 하는 것

| 항목 | 무엇을 | 언제 |
|---|---|---|
| ⑪ `/doctor prompt-audit` | 터미널 대화형 패널에서 1회 실행(세션이 실행할 수 없다). 결과 중 coding-harness 자산(rules·agents·commands)에 대한 지적만 메인에게 전한다. 메인은 부록 C 에 요약만 적는다. 수정은 하지 않는다 — 고칠 것이 있으면 별도 과제다 | C1~C3 반영 뒤 아무 때나 |
| 설치 반영 | 병합·푸시 뒤 `/harness-update` 직접 실행(에이전트·커맨드·허브 재설치). 세션은 `install.sh` 를 직접 실행하지 않는다 | 병합 뒤 |
| ⑨ 활성 확인 | `/hub statusline on` 이 이미 켜져 있어야 칩이 생긴다. 다른 statusLine 을 쓰고 있다면 칩은 생기지 않는다(정당한 부재) | 반영 뒤 |
| effort 환경변수 | `CLAUDE_CODE_EFFORT_LEVEL` 을 쓰고 있다면 frontmatter 고정이 무시된다. 쓰지 않는지 확인 | 반영 뒤 |

---

## 14. 리스크와 대안

| ID | 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|---|
| R1 | ① 재현 의무 때문에 검수자가 재현 실행에 턴을 많이 쓴다 | 중 | 회차당 +수 분 | CRITICAL/HIGH 만 의무 · 설계 대조 예외 · 경량 검증 실패는 그대로 재현으로 인정 · §11 되돌림 조건 |
| R2 | 실행 환경 버전이 섞인다 — 데스크톱 2.1.293 vs PATH CLI 2.1.108. 오래된 런타임이 `effort`·`omitClaudeMd` 를 무시할 수 있다 | 중(터미널 세션을 옛 CLI 로 띄울 때) | 고정이 조용히 무효가 된다 | ⑩ 1단계에서 버전을 기록한다. 반영 뒤 첫 위임에서 서브 기록의 `effort` 를 확인한다(§11 effort 분포 지표). 옛 CLI 는 갱신을 권한다 |
| R3 | `omitClaudeMd` 가 규칙까지 빼면 Explore 가 한국어 응답 규칙 등을 모른다 | 중 | Explore 출력이 영어일 수 있다(내부 산출물이라 영향 작음) | description 에 「필요한 규칙은 요청에 담는다」를 쓴다. ⑩ 3단계에서 실제 범위를 확인한다 |
| R4 | ⑨ `cost.total_cost_usd` 는 정가 기준이라 구독 사용자에게 실제 과금이 아니다 | 확실 | 숫자를 청구액으로 오해한다 | `≈` 접두 + 툴팁 「정가 기준 추정, 구독 요금과 무관」 + README 고지 |
| R5 | statusLine 은 메인 대화가 갱신될 때만 돈다. 서브만 도는 동안은 값이 늦다 | 확실 | 진행 중 수치가 몇 분 늦다 | 표시는 「마지막 관측값」 의미다. 세션 종료 시점 값은 정확하다 |
| R6 | 데스크톱·IDE 진입점에서는 statusLine 이 실행되지 않을 수 있다 | 중 | 그 세션에는 칩이 없다 | 정당한 부재로 설계했다(None → 빈 문자열). 전후 비교의 비용 지표는 statusLine 이 있는 세션만으로 계산한다고 명시한다 |
| R7 | 정적 가드를 면제행으로 등록하면 K6 가 그 가드의 회귀를 기계로 확인하지 않는다 | 확실 | 가드가 조용히 무력화될 수 있다 | §10-3 수동 1회 확인과 그 결과 기록. 사용자 결정(시간 보호)의 대가로 명시한다 |
| R8 | ⑥ 재읽기가 「파일 읽기」 절의 재읽기 금지와 섞여 과도한 재읽기로 번진다 | 낮음 | 컨텍스트 증가 | 예외의 범위를 「단계 경계 · 해당 절만」으로 문장에 고정한다 |

**검토했으나 채택하지 않은 대안**

1. **새 가드를 T38 `PATCH_CONTRACT_PAIRS` 에 행으로 추가** — 가장 적은 코드다. 그러나 최상위 배열 변경이 증분 K6 를 전체 재확인(약 23분)으로 바꾼다. 그 비용이 그 브랜치의 모든 검증 실행에 붙는다. T31 그룹 안 지역 배열로 같은 검사를 한다.
2. **⑨ 를 새 순수 모듈(`hub_session_cost` 하나에 파서까지)로** — 응집은 좋다. 그러나 statusLine 입력 계약 파서가 두 모듈로 갈라져 「stdin 한 번 파싱」 계약을 두 모듈이 나눠 진다. 파서는 `hub_usage.py`, I/O 만 새 모듈에 둔다.
3. **⑤ 의 effort 를 상시 규칙(`model-routing.md`)에 명문화** — 착수 보고에 effort 가 보인다. 그러나 frontmatter 고정 후에는 값이 결정적이다. 실제 값은 기록에 남으므로 +17B ⚠T26 의 근거가 서지 않는다.

---

## 15. 구현 이탈 기록

구현 중 이 문서와 달라진 곳과 그 한 줄 근거다. 1회차 검수 결과와 사용자 결정(2026-10-08)을 반영한 2회차 변경도 함께 적는다. 메인 세션은 이 변경을 **커밋 1개**로 묶는다(§12 의 6개 커밋 분할은 적용하지 않는다 — 한 파일 `tests/run.sh`·`tests/mutations.tsv` 가 여러 단계에 걸쳐 있어 쪼개기 어렵다).

### 15-1. 1회차(구현)

| # | 이탈 | 근거 |
|---|---|---|
| 1 | `SOURCE_GUARD_ID_FLOOR` 537 → 539, 원장 헤더 인용 동기화 | 새 가드 ID 2개의 여유를 회수한다(저장소 관례, 410→411 선례) |
| 2 | `LEDGER_EXEMPT_ROW_RATCHET` 은 올리지 않았다 | 면제행 313 ≤ 상한 372 — 올릴 이유가 없다 |
| 3 | T25-201(`data-tooltip="` 리터럴 20건 고정)을 21 로 | 설계 때 놓친 가드 — 새 칩의 툴팁이 +1. README 툴팁 트리거 서술에도 반영 |
| 4 | `tests/hub/__init__.py` 에 `SESSION_COSTS_DIR` 중화 | `collect_snapshot` 이 캡처 파일을 지우고 읽는다 — 격리를 잊은 테스트가 실제 홈을 건드리지 못하게(`CLAUDE_GLOBAL_CONFIG_PATH` 선례) |
| 5 | `test_hub_session.py` 기존 단언 3곳(마지막 필드 `background_wait`)을 `session_cost` 기준으로 | T25-150 과 같은 이유 |
| 6 | `collect_snapshot` 에 줄을 더하지 않고 헬퍼 `_read_session_costs`(2회차에 `_prune_and_read_session_costs` 로 개명)를 둠 | `collect_snapshot` 이 이미 50줄 상한 — 호출은 기존 인자 줄에 얹었다. `hub_collect.py` 790줄(2회차 개명 뒤) |
| 7 | `context_window.used_percentage` 는 `_valid_used_percentage`(실수 허용 후 내림), 센트 변환은 내림 전 소수 6자리 반올림 | 실수가 올 수 있고 PRP 도 「내림」이라 적었다 · `0.29 * 100` 이 28 센트로 내려가는 곱셈 잡음 방지 |
| 8 | 3회차 FAIL 판정 문구를 `FAIL [사유 범주] — 상한 도달…` 로 | ⑫ 의 목적(「3회 FAIL = 설계 문제」 검증) — 3회차에 범주가 없으면 데이터가 빈다 |
| 9 | NOTICE 의 code-reviewer 누적 커밋 수 | 이전 표기 「7」은 이미 `git log` 와 어긋나 있었다. 2회차에 커밋 1개 기준 9 + 1 = 10 으로 |
| 10 | JS 함수 4개(`sessionCostAmountLabel` 헬퍼 추가) | 금액 포맷을 정수 연산 헬퍼로 분리해 함수 길이를 지킨다 |

### 15-2. 2회차(검수 반영 · 사용자 결정)

| 항목 | 변경 | 근거 |
|---|---|---|
| HIGH ④ | `tools:` 를 정식 이름 `Agent` 로, 「도구 목록 제한」 주장 삭제, T31-10 (a) 재정의, ④ 판정·D3·§5-1 수정 | 서브에이전트 정의에서는 `Agent(...)` 괄호 목록이 무시된다(문서 506행). 사용자 결정 「문구만 바로잡기」 |
| M1 | 사유 범주 `설계` 와 `[분류] 설계` 를 가르는 한 줄 + 「흔한 `[분류]`」 대응 | 이름 겹침 해소 — 범주 이름은 바꾸지 않았다 |
| M2 | 계획 리마인더가 「구현 단계 분할」 제목에 기대지 않게 | 다른 PRP 에는 그 제목이 없다 |
| M3 | `commands/code-review.md` Phase 4 재현 형태를 셋으로, 정적 지적의 형태·범주 명시 | 에이전트 쪽과 어긋나 있었다 |
| M4 | 새 usage 테스트를 `tests/hub/test_hub_usage_session_cost.py` 로 분리 | `test_hub_usage.py` 805줄 → 666줄. 테스트 파일 수를 세는 가드는 없다 |
| M5 | 이 절 추가, §6-1·§7-1·§7-2·§9-2·§3-2 정정 | 문서와 구현의 어긋남 해소 |
| LOW | NOTICE 누적 10 · 재현 의무에 부산물 방지 · J 행 수치 정정 · 부록 B 부수 효과 · `hub_usage.py` docstring·정렬 공백 원복 · `_prune_and_read_session_costs` 개명 · API 시간 상한(`SESSION_API_DURATION_MAX_*`)과 파일 쪽 센트·분 상한 + 테스트 · 프라이버시 고지에 「끈 뒤에도 보관 기간까지 남는다」 | 검수 지적 |
| 재검수 M | `agents/design-architect.md` 「탐색 위임」에 「하위 에이전트는 Explore 만 띄운다.」 한 줄 | README·§5-5 가 작업 에이전트 3종 모두에 이 지침이 있다고 적는데 설계자 본문에만 없었다(메인 세션이 문서 수정으로 반영) |
| 재검수 LOW | 이 표와 §4·§9-2 의 `hub_collect.py` 수치를 790줄·헬퍼 14줄로, §6-2 `정합` 행에 「정적 지표·정적 보안 패턴」 | 2회차 개명으로 1줄 늘었다 |
| 알려진 한계 | T31-10 (a) 는 옛 이름에 괄호를 붙인 `Task(Explore)` 표기를 잡지 못한다 | 재검수 LOW — 그런 표기를 넣을 동기가 거의 없어 패턴을 넓히지 않았다 |

---

## 부록 A. 외부 근거 목록

- 수정안 요구와 과잉 교정: [arXiv 2603.00539](https://arxiv.org/abs/2603.00539)
- 계획 리마인더: [arXiv 2604.12147](https://arxiv.org/abs/2604.12147) · 에이전트 자작 테스트: [arXiv 2602.07900](https://arxiv.org/abs/2602.07900) · 스펙 유도 테스트: [arXiv 2608.17177](https://arxiv.org/abs/2608.17177)
- Terminal-Bench 2.0 실패 분류·턴 무상관: [arXiv 2601.11868](https://arxiv.org/abs/2601.11868)
- Claude Code 문서: [Subagents](https://code.claude.com/docs/en/sub-agents) · [Hooks](https://code.claude.com/docs/en/hooks) · [statusline](https://code.claude.com/docs/en/statusline) · [Worktrees](https://code.claude.com/docs/en/worktrees) · [Costs](https://code.claude.com/docs/en/costs) · [releases](https://github.com/anthropics/claude-code/releases)
- 서브에이전트 고정비 측정법: [practicalsystems](https://www.practicalsystems.io/blog/measure-your-subagent-token-cost)
- 검수 패킷·주장 불신: [superpowers task-reviewer-prompt](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/task-reviewer-prompt.md) · [BMAD edge-case-hunter](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/skills/bmad-build/review-prompts/edge-case-hunter.md)
- 체감 보고의 한계: [METR 2025](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)

## 부록 B. ⑩ 측정 기록 (C5 에서 채운다)

| 날짜 | CLI 버전(런타임 / 측정) | 위치 | input | cache_creation | cache_read | 합 | 비고 |
|---|---|---|---|---|---|---|---|
| 2026-10-08 | 2.1.293 / 2.1.293 (데스크톱 번들 CLI) | 빈 디렉터리 | 2 | 77,329 | 0 | 77,331 | `claude -p "ok" --model haiku --output-format json`. 같은 조건 반복 1회는 2 / 45,172 / 22,768 = 67,942 — 캐시 분할이 달라 합이 약 9.4K 흔들린다 |
| 2026-10-08 | 2.1.293 / 2.1.293 | 저장소 루트(워크트리 루트) | 2 | 73,182 | 0 | 73,184 | 빈 디렉터리보다 **작다**(-4.1K). 두 위치 차이가 프로젝트 CLAUDE.md(3,072B) 몫이라는 가정은 이 측정법으로 분리되지 않았다 — 반복 변동(약 9.4K)이 그 몫보다 크다. 사용자 상시 규칙(약 55KB)은 두 위치에 똑같이 실린다 |
| 2026-10-08 | 2.1.293 / 2.1.293 | Explore 디스패치 대용 프로브 2종(서브 첫 요청) | 2 / 2 | 2,379 / 22,828 | 0 / 1,467 | 2,381 (`omitClaudeMd: true`) / 24,297 (없음) | **`omitClaudeMd` 가 규칙까지 뺀다: 예.** 프로브 응답: omit 쪽은 프로젝트 CLAUDE.md 표지 문자열·사용자 규칙 두 문구(「Karpathy 지침」·「응답 언어」)가 모두 no, 없는 쪽은 전부 yes. 디스패치 1회 절감 약 21.9K 토큰. 프로브는 haiku·`tools: Read` 로 Explore 와 같은 모양이며 임시 프로젝트의 `.claude/agents/` 에 둬서 `$HOME` 설치 없이 측정했다. 서브 기록의 `effort` 필드는 두 프로브 모두 `medium` |

- 부수 효과: `claude -p` 5회가 허브에 짧은 세션 줄을 만들었고(무해, 7일 뒤 정리), `~/.claude/projects/` 에 그 호출들의 대화 기록(세션 기록 파일)을 남겼다(자동 정리 없음 — 필요하면 직접 삭제). 비용은 1회 약 1.5센트.
- 해석: ⑩ 의 목적(J 의 실제 절감 폭)은 세 번째 행으로 확인됐다. 첫 두 행은 변동이 커서 「프로젝트 CLAUDE.md 몫」을 가르지 못하므로 그 용도로 인용하지 않는다.

## 부록 C. ⑪ 결과 · 도입 후 측정 (사용자 전달 시 / §11 시점에 채운다)
