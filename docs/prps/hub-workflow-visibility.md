# PRP — 허브에서 Workflow 서브에이전트 지시 보기 (hub-workflow-visibility)

- **상태**: 구현↔검수 3회차 상한 도달 후 **루프 밖 보완 완료** — 사용자 승인 하에 잔여
  지적을 한 번에 정리(§19). 메인 세션의 최종 검증·커밋 대기
- **분류**: 전체 경로 (새 모듈 추가 + 데이터 모델 변경 + 3개 이상 파일)
- **복잡도**: Medium (신규 5 · 수정 13 파일, 새 외부 의존성 0 — 구현 2회차 검수 A-1 지적:
  1회차 헤더는 "신규 2·수정 8"이었으나 실물은 `hub/install.sh`·`tests/run.sh` 가 빠진
  과소집계였다. 아래 §5 표가 정본이며 이 숫자는 §5 를 그대로 센 것이다)
- **설계 모델**: opus (fable 승격 기준 1~4 모두 미해당 — 데이터 모델 전면 개편이 아니라
  기존 세션 뷰에 필드 1개를 더하는 보강이고, 동시성·분산 영역이 아니며 재설계 회차도 아니다)
- **재번호 참고**: 리베이스로 `main`(세션 트리)과 통합되며 `tests/run.sh` 의 T25-156~158
  라벨이 두 벌로 중복됐다. 이 문서가 인용하는 워크플로우 가시성 쪽 트리오는 T25-164/165/166
  으로 재번호됐다(docs/prps/hub-collect-split-for-merge.md 결정 D3). 아래 본문의 라벨
  인용은 재번호 후 값으로 갱신했다.

---

## 1. 요구사항 요약

메인 세션이 Workflow 툴(다중 에이전트 오케스트레이션 스크립트)을 돌릴 때, **각 서브에이전트에게
실제로 어떤 지시가 갔는지**를 `/hub` 화면에서 간략히 볼 수 있게 한다. 지금은 허브의 세션 줄에
`workflow-subagent` 라는 칩 하나만 뜨고(훅이 주는 `agent_type` 이 전부 이 값 하나다), 스크립트가
붙인 개별 `label` 과 프롬프트를 보려면 `~/.claude/projects/.../workflows/wf_*.json` 을 손으로
열어야 한다. 이 PRP 는 그 파일에 이미 들어 있는 `label`·`promptPreview`·`resultPreview` 를
수집 시점에 읽어 세션 뷰에 실어, 세션 줄의 칩 + 호버 툴팁으로 노출한다.

**User story** — 워크플로우를 돌린 개발자로서, 각 팬아웃 에이전트가 받은 지시와 낸 결과의
앞부분을 허브 카드에서 바로 보고 싶다. 파일을 뒤지지 않고도 "누구에게 무엇을 시켰고 뭐가
깨졌는지"를 한눈에 알기 위해서다.

### 하지 않는 것 (범위 밖 — 명시)

- **훅 확장으로 프롬프트를 나르지 않는다.** `SubagentStart`/`SubagentStop` 페이로드에는
  `agent_id`·`agent_type`·타임스탬프만 실린다(`docs/prps/hub-dashboard.md` 실측 이벤트 표).
  Claude Code 가 그 이벤트에 프롬프트를 주지 않으므로 훅 경로로는 이 요구를 채울 수 없다.
- **에이전트 트랜스크립트(프롬프트 전문)를 읽지 않는다.** 근거는 §3 계측 5 — 비용이 예산을
  초과하고, 그것도 이미 있는 발췌보다 더 나은 것을 주지 않는다.
- **스크립트 원문(`workflows/scripts/*.js`)을 읽지 않는다.** "간략히"라는 요구와 어긋나고,
  프롬프트 전문이 미절단으로 들어 있어 프라이버시 노출면만 넓힌다.
- **에이전트별 모델 표시 안 함**(각 항목에 `model` 이 있지만 이번 요구는 "어떤 지시"다).
  나중에 필요해지면 `hub_transcript.normalize_model_name` 을 한 번 부르면 되는 1줄 확장이다.
- **워크플로우 실행 이력(2회차 이전 실행) 표시 안 함** — 세션당 최신 1건만.
- **새 티어를 만들지 않는다**(근거: 결정 WF1).
- **캐시를 만들지 않는다**(근거: 결정 WF10 — 선례 MD4 와 같은 이유).

---

## 2. 호스트 데이터 계약 (실측으로 확정)

`wf_<runId>.json` 은 **우리가 소유하지 않는 외부 파일 형식**이다. 아래는 이 머신의 전수 실측
(파일 73개 · `workflow_agent` 항목 502개, 2026-09-02)이며, 이 표가 파서의 계약 정본이다.

경로: `~/.claude/projects/<encode(cwd)>/<session_id>/workflows/wf_<runId>.json`
(`<session_id>` 는 **디렉터리**다 — 같은 이름의 `<session_id>.jsonl` 트랜스크립트 파일과 별개의
형제 항목이다.)

### 최상위 키 (73/73 존재)

`runId, timestamp, taskId, script, scriptPath, result, agentCount, logs, durationMs, summary,
workflowName, status, startTime, phases, defaultModel, workflowProgress, totalTokens, totalToolCalls`

이 PRP 가 읽는 것은 **`workflowName`·`status`·`startTime`·`runId`·`workflowProgress` 5개뿐**이다.
`script`·`logs`·`result` 는 읽지 않는다(파일 부피의 대부분이 이 3개다 — §7 참조).

### `workflowProgress` — 두 종류가 섞인 배열

| type | 필드 |
|---|---|
| `workflow_phase` | `index`, `title` |
| `workflow_agent` | `index`, `label`, `phaseIndex`, `phaseTitle`, `agentId`, `model`, `state`, `startedAt`, `queuedAt`, `attempt`, `lastToolName`, `lastToolSummary`, `promptPreview`, `lastProgressAt`, `tokens`, `toolCalls`, `durationMs`, `resultPreview` |

### 필드 존재·값 계약 (502개 전수)

| 사실 | 실측 |
|---|---|
| `label` 결측 | **0건** (항상 존재) |
| `agentId` 결측 | **0건** |
| `index` 비정수 | **0건**. 1-based·연속·스크립트 순서 |
| `phaseTitle` 비문자열 | **0건** |
| `state` 값 집합 | `done` 469 · `error` 33. **그 외 관측 없음** |
| `promptPreview` 존재 | **502/502** (state 무관) |
| `resultPreview` 존재 | **469/469 done, 0/33 error** → *`resultPreview` 결측 ⇔ `state == "error"`* |
| `status`(실행) 값 | `completed` 73/73. **그 외 관측 없음** |

### 이미 잘려 있다 — 그러나 스크럽은 안 돼 있다

| 값 | 길이 실측 |
|---|---|
| `promptPreview` | n=502, **max 401** (=400자 + `…`), 평균 400 |
| `resultPreview` | n=469, **max 401**, 평균 395 |
| `label` | n=502, min 2 · median 16 · p90 35 · **max 60** |
| `workflowName` | median 24 · max 37 |

호스트가 400자에서 이미 자른다 — 허브의 `PROMPT_EXCERPT_MAX_CHARS`(500)보다 **작다**. 따라서
길이 재절단은 필요 없다. 반면 **시크릿 마스킹은 전혀 되어 있지 않다**(결정 WF7).

**`label` 은 짧은 식별자가 아닐 수 있다.** 스크립트가 `label` 을 주지 않으면 툴이 프롬프트
머리에서 파생시키며, 실측 최장 60자에는 절대 경로가 들어 있다(예:
`저장소 '/Users/dev/private/project/coding-harness' 에서 방금 'hub/bin`). 즉 **label 도 콘텐츠이며
스크럽·표시 절단 대상이다**(결정 WF7·WF9).

### 미검증 — 라이브인가 회고인가 (승인·검증 필요 항목 ①)

관측된 73개 파일이 **전부 `status: "completed"`** 이고, `mtime − (startTime + durationMs)` 가
73건 전부 **정확히 0.0초**다. 또 `subagents/workflows/wf_*/` 실행 디렉터리와 wf JSON 의 대응이
73:73 으로 완전하다(json 없는 디렉터리 0건, 디렉터리 없는 json 0건).

가장 단순한 설명은 **툴이 진행 상태를 메모리에서 관리하고 종료 시 1회만 flush 한다**는 것이다
(`state`·`lastProgressAt`·`queuedAt`·`attempt` 같은 라이브 성격의 필드가 있는데도 진행 중 파일이
하나도 없다). 정적 데이터만으로는 단정할 수 없다.

**이 미확정은 설계를 바꾸지 않는다** — 읽기 경로는 "세션의 최신 wf JSON 을 읽는다"로 두 경우에
모두 동일하고, 갈리는 것은 **화면 문구뿐**이다(결정 WF6). 구현 Task 0 에서 실측해 문구를 확정한다.

### 기각한 대안 출처: `journal.jsonl`

`subagents/workflows/wf_<runId>/journal.jsonl` 은 실행 재개(resume) 캐시다 — 줄이
`{type: started|result|failed, key: "v2:<sha256>", agentId, result}` 형태이고 **`label` 도 프롬프트도
없다.** 게다가 `result` 가 미절단 전문이라 프라이버시 노출면만 넓힌다. 기각.

---

## 3. 계측 (성능 판단의 근거, 이 머신 2026-09-02)

| # | 항목 | 실측 |
|---|---|---|
| 1 | `collect_snapshot()` 기준선 | **10.6ms**(초회) / **8.8ms**(2회차), 프로젝트 3개 — 문서화된 8~11ms 와 일치 |
| 2 | 활성 세션 수(`sessions_by_path` 전체) | **24개** / 프로젝트 3개 (최근 이벤트 122건) |
| 3 | 활성 세션 중 `workflows/` 보유 | **3/24**. `is_dir()` 음성 판정 24회 = **0.26ms** |
| 4 | wf JSON 전체 규모 | 73개 · 4.9MB · 평균 66.6KB · median 41.7KB · **p90 136KB · max 818KB** |
| 5 | `json.load` 비용 | 73개 전부 = 20.0ms · **최대 파일(818KB) 1건 = 3.33ms** · 세션별 최신 1건씩 25개 = 6.8ms |
| 6 | `scandir(workflows/)` | 28개 디렉터리 = **0.73ms** |
| 7 | 에이전트 트랜스크립트(기각 근거) | 1043개 · **402.8MB** · median 292KB · max 5.0MB. 첫 줄만 읽어도 533개 = **124.9ms**, 첫 줄 크기 median 4.7KB · **max 355KB**(프롬프트 1건이 121,145자) |
| 8 | 실행당 에이전트 수 | 평균 6 · **max 25** |
| 9 | 실행당 파일 수 | 세션당 평균 2.6 · max 10 |

> 브리핑에 있던 "606개 · 6.9MB · 평균 11.6KB" 는 이 머신에서 재현되지 않았다. 실측은
> **73개 · 4.9MB · 평균 66.6KB · max 818KB** 다. 평균이 6배, 최대가 훨씬 크므로 사이징 근거는
> 이 표를 쓴다. 부피의 원인은 `script`(스크립트 전문)·`logs`·`result` 가 같은 파일에 인라인돼
> 있는 것이다 — 우리가 쓰는 `workflowProgress` 는 그중 일부다.
>
> 계측 7 이 **에이전트 트랜스크립트 읽기를 기각하는 결정적 근거**다: 프롬프트 전문은 파일
> *머리*에 있어 tail 읽기 관용구(`TRANSCRIPT_TAIL_BYTES`)를 쓸 수 없고, 첫 줄 하나가 355KB 까지
> 가며, 전체 순회가 124.9ms 로 문서화된 50ms 에스컬레이션 임계를 단독으로 넘긴다.

---

## 4. 설계 결정과 근거

### WF1. 새 티어가 아니라 **티어 2 세션 뷰의 보강(enrichment)** 이다

허브의 티어는 *프로젝트를 어떻게 발견·서열화하는가*의 축이다 —
`hub_project._project_tier` 가 티어 1(=`dashboard.html` 파싱 성공) / 티어 2(=훅 세션 있음) /
티어 3(=`~/.claude/projects` mtime 뿐)을 정한다. 워크플로우 데이터는

- 프로젝트를 **발견하지 못한다**(이미 훅 이벤트로 발견된 세션 밑에서만 존재한다),
- 티어를 **올리거나 내리지 못한다**(값이 있어도 없어도 티어 판정은 동일해야 한다),
- **세션 단위**로 키가 잡힌다(티어는 프로젝트 단위다).

정확히 같은 성격의 선례가 이미 있다: **세션 모델·effort**(`SessionModel`)도 우리가 소유하지 않는
호스트 파일(트랜스크립트)을 수집 시점에 읽어 세션 뷰에 얹지만 티어가 되지 않았다
(`docs/prps/hub-tier1-clamp-fix-and-session-model.md` 결정 MD1~MD10). 이 기능은 그 선례의
2번째 사례이고, 구조를 새로 발명할 이유가 없다.

### WF2. 새 모듈 `hub/bin/hub_workflow.py` (★순수) — `hub_transcript.py` 를 거울삼는다

`hub_transcript.py` 의 자기 문서화된 근거를 그대로 물려받는다: *"Claude Code transcript(JSONL)는
우리가 소유하지 않는 외부 파일 형식이다 — 그 계약이 바뀌면 이 모듈 하나만 고치면 되도록
분리했다."* `wf_<runId>.json` 도 같은 처지다(호스트 소유 · 스키마 통제 불가 · §2 계약이 언제든
바뀔 수 있다). `hub_collect.py`(I/O)나 `hub_session.py`("훅 이벤트 → 세션 사실"이라는 단일 입력원
계약)에 섞지 않는다.

- **파일 접근은 전부 `hub_collect.py`** 가 맡는다. `hub_workflow.py` 는 **이미 읽힌 텍스트만**
  받는다(`hub_transcript.parse_session_model_from_tail` 과 같은 관용구).
- 따라서 `hub_workflow.py` 는 파일시스템·시각·환경변수에 닿지 않는다(★순수,
  `tests/hub/test_hub_workflow.py` 대상).

### WF3. `redact_secret_tokens` 를 `hub/bin/hub_redact.py`(★순수)로 추출한다 — **순환 의존이 강제한다**

선행 결정을 뒤집는다. `docs/prps/tier0-defect-fixes.md:404` 는
*"`redact_secret_tokens` 는 순수 함수로 hub_hook.py 에 둔다 — 별도 모듈로 빼지 않는다
(**사용처가 1곳**, …)"* 라고 적었다. **그 전제가 이번에 소멸한다** — 사용처가 2곳이 된다.

더 강한 강제 조건이 있다. 실측한 import 그래프:

```
hub_hook.py     → import hub_collect, hub_model, hub_server_state
hub_collect.py  → import hub_model, hub_parse, hub_project, hub_server_state,
                           hub_session, hub_transcript, hub_usage
```

`hub_collect` 가 `hub_workflow` 를 임포트해야 하므로, `hub_workflow` 가 `hub_hook` 을 임포트하면
**`hub_collect → hub_workflow → hub_hook → hub_collect` 순환**이 된다. 전역 지침("순환 의존이
생기면 구현을 멈추고 구조를 먼저 재검토한다")이 그대로 발동한다. 게다가 `hub_hook` 은 임포트
시점에 `Path.home()` 을 계산하므로(환경변수 접촉) 순수 레이어가 그것을 끌어들이면 ★순수
표기가 거짓이 된다.

패턴 복제는 선택지가 아니다 — 시크릿 패턴이 두 곳으로 갈라지면 한쪽만 갱신되는 보안 드리프트가
난다(DRY 가 여기서는 보안 요구다).

**수술적 추출 방법**(Karpathy #3):

- `hub_redact.py` 로 **옮기는 것은 3개뿐**: `SECRET_REDACTION_MARK`, `SECRET_TOKEN_PATTERN`,
  `KEY_VALUE_SECRET_PATTERN`, 그리고 함수 `redact_secret_tokens`. 정규식 상단의 긴 주석
  (catastrophic backtracking 이슈 #2278 이식 조건)도 **함께** 옮긴다 — 그 주석이 없으면 제약을
  모르는 사람이 패턴을 추가한다.
- `hub_hook.py` 는 `from hub_redact import redact_secret_tokens` 로 **이름을 그대로 재노출**한다.
  그러면 `hub_hook.redact_secret_tokens` 를 이름으로 참조하는 기존 4곳이 전부 유효하게 남는다:
  `tests/hub/test_hub_hook.py:354`(호출)·`:288`(docstring), `hub/README.md:150`,
  `rules/python/security.md:14`. **기존 테스트를 고치지 않는다.**
- `hub_hook.py` 에 남는 것: `strip_auto_injected_blocks`(훅 고유 — CLI 자동주입 블록 벗기기),
  `_clip_prompt`(훅의 500자 상한), `PROMPT_EXCERPT_MAX_CHARS`, `PROMPT_TRUNCATION_MARK`.

### WF4. 상관관계는 **이미 디렉터리 키로 해결돼 있다** — 새 문제가 아니다

"어떤 wf 파일이 어떤 세션 소속인가"는 경로가 답한다:
`PROJECTS_DIR / encode_project_dir_name(cwd) / session_id / "workflows"`. 조립에 쓰는 두 값
(`cwd`, `session_id`)은 전부 훅 이벤트에서 온 `SessionFacts` 안에 있고, `encode_project_dir_name`
은 순수 함수다. **디렉터리 열거나 역인코딩이 필요 없다** — `read_session_model` 이 이미 쓰는
결정 MD2 의 관용구를 그대로 재사용한다.

`observed_cwds` 전부를 후보로 삼는다(결정 MD2 의 E13 과 같은 이유 — 워크트리로 이동한 세션의
디렉터리는 최초 cwd 기준으로 남는다).

**[구현 2회차 검수 B-1 로 개정]** 1회차는 여기서 "**먼저 존재하는 후보를 쓰고**, 그 안에
유효한 값이 없어도 다음 후보로 넘어가지 않는다"고 적었다. 이는 E13 의 적용 범위를 잘못 넓힌
것이었다 — E13 은 "**transcript** 파일의 위치가 최초 cwd 기준으로 남는다"는 관측이지
"워크플로우 디렉터리가 세션당 하나만 존재한다"는 보장이 아니다. 실측(구현 2회차, 메인 세션이
워크트리로 이동하며 직접 관측): 한 세션이 워크트리 이동 **전후로 각각** 워크플로우를 돌리면
최초 cwd 의 `workflows/` 와 이동 후 cwd 의 `workflows/` 가 **둘 다 존재**한다. 이 상태에서
1회차 규칙은 `observed_cwds` 에서 먼저 순회되는 디렉터리(반드시 최신은 아니다)에서 멈추므로,
**오래된 실행이 이길 수 있다** — "세션당 최신 1건"(결정 WF5)이라는 이 기능의 목적과 정면으로
어긋난다.

**개정**: 존재하는 `workflows/` 디렉터리를 **전부** 모으고, 그 안의 `wf_*.json` 후보를 전부
풀링해 mtime 최댓값 1건을 고른다(동률은 결정 WF5 와 같은 파일명 역순 사전식). 이것은
WF5("세션당 최신 1건")를 디렉터리 경계 너머로 일관되게 적용하는 것일 뿐 새 개념이 아니다.
(구현: `hub_workflow_read._existing_workflow_directories` 가 존재 후보를 전부 모으고,
`_latest_run_path` 가 그 전부에서 풀링해 mtime 최댓값을 고른다.)

`read_session_model` 과는 두 가지가 다르다: **(1)** 파일명에 예측 불가능한 `runId` 가 들어
있어 경로를 바로 조립할 수 없어 활성 세션당 `is_dir()` 음성 체크 1회 + (양성이면) `glob`
1회가 필요하다(계측 3: 그 음성 판정은 사실상 무료, 24회 = 0.26ms). **(2)** 위 개정으로,
존재하는 후보가 여럿이면 **전부** glob 해야 한다 — `read_session_model` 은 "먼저 존재하는
것"에서 멈춰도 안전하지만(트랜스크립트는 세션당 정확히 1개 파일이라 디렉터리 자체가 다중
후보를 낳지 않는다) 워크플로우는 디렉터리 하나에 파일이 여러 개 있을 수 있어 이 대칭이
성립하지 않는다. 비용은 관측 cwd 수만큼의 `is_dir()`+`glob` 이고 실측상 관측 cwd 는
1~2개다(§10 재측정).

### WF5. 세션당 **최신 1건**만 읽는다

세션당 실행이 최대 10건(계측 9)이다. 전부 읽을 이유가 없다 — 화면에 실을 것은 "지금(또는 마지막)
무엇을 시켰나"다. 선택 기준은 **파일 mtime 최대값**이다:

- `startTime`(JSON 내부)으로 고르려면 **전부 파싱해야 한다** — 최대 10 × 66KB.
- mtime 은 `scandir` 이 이미 돌려주는 값이라 추가 syscall 이 없다(계측 6: 28디렉터리 0.73ms).
- 두 기준은 실측상 동순위다(계측: `mtime == startTime + durationMs`, 73/73).

동점(mtime 동일)일 때는 **파일명 역순 사전식**으로 깨서 결정성을 보장한다 —
`snapshot_content_key` 안정성(결정 D2)이 비결정적 선택을 허용하지 않는다.

### WF6. 표시 문구는 "최근 실행"으로 쓰고, 라이브 여부는 Task 0 에서 확정한다

§2 미검증 항목 ①. 읽기 경로는 두 경우에 동일하므로, 기본 문구를 **회고형**("최근 워크플로우")으로
두고, Task 0 의 실측에서 진행 중 파일이 관측되면 `status != "completed"` 일 때만 진행형 표시를
더한다. **추측으로 진행형 문구를 먼저 쓰지 않는다** — 라이브가 아니면 화면이 거짓말을 한다.

### WF7. 마스킹은 **순수 파서 안에서** 한다 (우회 경로 0개) — **[구현 3회차: 필드 열거에서 계약 서술로 개정]**

**개정 사유**: 1·2회차는 이 결정을 "스크럽 대상 필드"의 열거로 적었다(1회차:
label·prompt_preview·result_preview, 2회차 검수 C-2 로 phase_title 을 목록에 추가). 열거
방식 자체가 결함이었다 — 새 필드가 늘 때마다 이 문장을 사람이 기억해서 갱신해야 하고,
2회차 phase_title 누락이 정확히 그 경로로 생겼다(스크럽은 했지만 401자 상한 적용은 또
누락돼, 3회차 재검수에서 100,000자가 그대로 통과하는 것으로 재발했다). 이번엔 필드를
나열하는 대신 파서가 만드는 **모든** 문자열 필드가 예외 없이 따라야 하는 계약을 적는다.

`parse_workflow_run`(과 `_parse_agent_item`)이 만드는 문자열 필드는 dataclass 로 반환되기
전에 반드시 아래 둘 중 하나를 거친다 — 이 둘 밖의 "상한 없는 문자열 필드"는 구조적으로
존재할 수 없다:

1. **스크럽 + 401자 상한**(`_scrubbed_and_clipped`) — `label`·`phase_title`·
   `prompt_preview`·`result_preview`. 자유 텍스트 프롬프트에서 파생될 수 있는 콘텐츠라는
   것이 공통 근거다(label 이 그런 경위로 "짧은 식별자인 줄 알았는데 프롬프트 파생
   콘텐츠"였다, §2).
2. **128자 상한만, 스크럽 없음**(`_metadata_field`) — `run_id`·`workflow_name`·`status`·
   `state`. 닫힌 값 집합/식별자 성격이 스크럽 생략의 근거이지만(§2), 상한 자체는 예외
   없이 건다 — 그 근거가 구조적 보장이 아니라 관측일 뿐이기 때문이다. **`run_id` 관련
   정정**: 이전 판은 "파일명에서 오는 시스템 식별자"라 적어 스크럽 면제의 근거처럼 썼으나
   틀렸다 — 코드가 실제로 읽는 곳은 파일명이 아니라 페이로드 본문의 `runId` 키
   (`payload.get("runId")`)다. 파일명(`wf_<runId>.json`)과 실측상 대체로 일치하지만 그
   일치는 호스트 관례일 뿐 코드가 강제하는 것이 아니어서, "파일명에서 온 값이라 신뢰할
   수 있다"는 근거는 애초에 성립하지 않았다. 128자 상한이 그 빠진 근거를 메우는
   방어선이다.

에이전트 개수에도 같은 논리로 상한을 둔다(`WORKFLOW_RUN_MAX_AGENTS`, 결정 WF13 — §18) —
클라이언트 표시 상한(`MAX_VISIBLE_WORKFLOW_CHIPS`)은 직렬화 자체를 막지 못했다(구현 3회차
검수 재현: 에이전트 30,000개).

파서 밖에서 스크럽/상한을 적용하지 않는 이유는 1회차와 동일하다: 파서가 유일한 생성
지점이면 **이 계약을 어기는 값이 뷰에 도달할 코드 경로가 구조적으로 존재하지 않는다.**
I/O 없이 단위 테스트로 그 불변식을 고정할 수 있다는 것도 이점이다 — 3회차부터는
`tests/hub/test_hub_workflow.py::StringFieldLengthRatchetTest` 가 `dataclasses.fields()`
순회로 이 계약을 기계적으로 강제한다. **[루프 밖 보완 — 과잉 보장 서술 정정]** 바로 위
"필드를 하드코딩하지 않아 새 필드가 추가돼도 자동으로 검사 대상에 들어온다"는 서술은
어서션 쪽만 본 것이었다 — 그 테스트가 쓰는 병리적 페이로드 픽스처가 소스 JSON 키를
하드코딩해, 실제로는 새 필드의 소스 키가 픽스처에 없으면 검사가 조용히 무력화된다(검수가
`notes: str` 로 실증). 새 필드 누락을 실제로 기계적으로 강제하는 것은 `tests/run.sh` 의
정적 가드 `T25-166`(§19)이다 — 픽스처가 아니라 `hub_workflow.py` 의 생성자 호출부 자체를
검사한다.

**잔존 위험(정직하게 기록한다)**: `hub_hook` 의 파이프라인 계약은
`strip → redact → clip` 이며, 그 순서가 *정확성 조건*이다("자른 뒤에 스크럽하면 500자 경계에
걸친 시크릿이 패턴 불일치로 살아남아 앞부분이 그대로 유출된다"). **여기서는 호스트가 이미
400자에서 잘라 놓았으므로 그 순서를 지킬 수 없다.** 400자 경계에 걸친 시크릿은 접두사가
남을 수 있다. 이것은 허브가 자기 절단을 통제하는 다른 모든 경로에는 없는, 이 경로 고유의
잔존 위험이다 — 완화 불가이므로 §9 프라이버시 고지에 **명시**한다. (경계 부근의 토큰 유사
조각을 추가로 지우는 휴리스틱은 검토했으나 기각 — §14 대안 3.)

### WF8. `record_prompt_excerpt: false` 를 이 경로의 오프 스위치로 **재사용**한다 (승인 필요 ②)

새 설정 키를 만들지 않는다. 근거는 `hub/README.md:159-165` 가 이미 그 플래그를 **"hub.html 에
인라인된 프롬프트 발췌"의 오프 스위치**로 문서화하고 있다는 것이다("…끄는 수단은
`record_prompt_excerpt:false` 와 `/hub server stop`"). 플래그 이름이 훅의 이벤트 로그에서
유래했지만, 문서화된 의도는 "내 프롬프트가 허브 파일에 평문으로 남지 않게 한다"이고 이 기능은
정확히 그 범주다. `false` 면 **파일을 아예 읽지 않는다**(`show_usage_panel: false` 가 사용량
파일을 읽지 않는 결정 U4 와 같은 형태 — 읽고 버리는 것이 아니라 접근 자체를 안 한다).

대안(새 키 `show_workflow_prompts`)은 §10 대안 2 에서 기각했다.

### WF9. 렌더는 **세션 줄의 칩 행 + 칩별 툴팁**이다 (상세 패널이 아니다)

두 가지가 상세 패널(`#dzh-detail-panel`)을 배제한다:

1. **불변식 H1** — "다음 노드는 정적이며 폴링이 절대 교체하지 않는다: … `#dzh-detail-panel`(과 그
   자식 전부). 이들의 갱신은 속성·textContent 단위로만 한다." 워크플로우 데이터는 폴링마다
   바뀌는 목록형 콘텐츠라 이 잠금과 정면으로 부딛친다.
2. **스코프 불일치** — 패널은 **프로젝트** 단위이고 그 본문은 `dashboard.html` iframe 이다.
   워크플로우는 **세션** 단위다.

반면 `#dzh-app` 은 폴링이 자식 전체를 교체하는 정당한 영역이고, 세션 줄(`renderSession`)이 이미
`renderAgentRuns`(칩 행) + `renderSessionExcerpt`(툴팁 달린 발췌)를 갖고 있다. 새 개념 0개로
접합된다.

**칩 하나 = 에이전트 하나**, 칩 텍스트 = `label`, 툴팁 = 프롬프트(+결과) 발췌. 정렬은 `index`
오름차순(1-based·연속·스크립트 순서, §2) — 결정적이라 `snapshot_content_key` 안정성에 영향이
없다.

"칩 1개에 전체를 담는 메가 툴팁"은 기각했다(§10 대안 1): `.tooltip` 은
`max-height: calc(100vh - 16px); overflow: hidden` 이고 **스크롤을 주지 않는다**(캡처 단계 scroll
리스너가 툴팁을 즉시 숨긴다). 25 × 400자를 한 툴팁에 넣으면 대부분이 **조용히 잘린다.**
칩별로 나누면 툴팁 하나가 최대 401자 + label 로, 이미 검증된 세션 발췌 툴팁(500자)보다 **작다** —
`.tooltip` 의 420px 폭·`pre-wrap`·max-height 설계는 그 500자 케이스를 위해 들어온 것이라
이 케이스는 기존 봉투 안에 그대로 들어간다.

`.agent-chip` 클래스를 재사용한다(새 색 토큰 0개, 새 CSS 규칙은 행 컨테이너 하나뿐).

### WF10. 캐시를 만들지 않는다

`read_session_models` 의 자기 문서화된 근거를 그대로 승계한다(결정 MD4, YAGNI):
*"`collect_snapshot` 이 50ms 를 넘기 시작하면 그때 캐시를 재검토한다."* §7 의 예상 증분이
그 임계의 10% 수준이다. 캐시는 무효화 규칙이라는 새 상태를 들여오므로, 측정이 요구하기 전에는
만들지 않는다.

### WF11. 파일 크기 상한 `WORKFLOW_RUN_MAX_BYTES` 를 둔다 (방어)

부피의 원인이 `script`·`logs`·`result` 이고 그중 어느 것도 상한이 없다(계측 4: 이미 max 818KB).
병리적으로 큰 파일 1개가 수집을 멈추는 것을 막기 위해 상한을 두고, 넘으면 **읽지 않고
`warnings` 에 남긴다**. 값은 **4MiB**(=4,194,304) — 실측 최대의 약 5.1배다. 선례:
`TRANSCRIPT_TAIL_BYTES` 도 실측 최악(103,742B)의 1.26배로 정한 하드 바이트 상한이다.

---

## 5. 영향 범위

**구현 2회차 검수 A-1 지적**: 1회차 이 표는 `hub/install.sh`·`tests/run.sh` 를 누락했다 —
1회차 헤더 집계("신규 2·수정 8")도 그래서 틀렸었다. 아래가 18개 파일(신규 5·수정 13) 전량이다.

| 파일 | 조치 | 이유 |
|---|---|---|
| `hub/bin/hub_workflow.py` | **CREATE**(1회차) | 호스트 소유 wf JSON 의 순수 파서 + 뷰 dataclass (WF2). 2회차: `phase_title` 스크럽(검수 C-2)·401자 상한(검수 C-1)·`RecursionError` 방어(검수 C-3). 3회차(결정 WF7 개정): `phase_title` 에 401자 상한 합류(2회차는 스크럽만 하고 상한 누락)·`run_id`/`workflow_name`/`status`/`state` 128자 상한 신설(`WORKFLOW_METADATA_MAX_CHARS`)·에이전트 개수 100개 상한 신설(`WORKFLOW_RUN_MAX_AGENTS`, 결정 WF13)·`except` 절을 `(ValueError, RecursionError)` 로 확장 |
| `hub/bin/hub_redact.py` | **CREATE**(1회차) | 시크릿 스크럽 추출 — 순환 의존 회피 (WF3). 2회차 변경 없음(검수 2건 모두 "정상" 판정) |
| `hub/bin/hub_workflow_read.py` | **CREATE**(2회차) | `hub_collect.py` 가 800/800줄 상한에 닿아 워크플로우 I/O 함수 3개(약 47줄)를 분리(WF12, 검수 A-1). 디렉터리 풀링(검수 B-1)·읽기 실패 warnings(검수 C-4)·session_id 방어(검수 C-7) |
| `hub/bin/hub_hook.py` | UPDATE(1회차) | 스크럽 3상수+1함수 제거, `hub_redact` 에서 재노출 (WF3). 2회차 변경 없음 |
| `hub/bin/hub_collect.py` | UPDATE | 1회차: I/O 접합 함수 3개 추가. 2회차: 그 3개를 `hub_workflow_read.py` 로 이동하고 `collect_snapshot` 배선을 새 모듈 호출 + warnings 수집으로 교체(검수 A-1·C-4) |
| `hub/bin/hub_session.py` | UPDATE(1회차) | `SessionView.workflow` 필드 + `compute_session_view` 인자. 2회차 변경 없음 |
| `hub/bin/hub_project.py` | UPDATE(1회차) | `compose_project_views` 가 `workflow_by_session_id` 를 세션 뷰로 전달. 2회차 변경 없음 |
| `hub/bin/hub_template.html` | UPDATE | 칩 행 렌더 함수 + CSS 1규칙 + 상수 + 헤더 주석 불변식 갱신. 2회차: `workflowChipTooltipText` 의 `!agent.result_preview` 판정 근거 주석(검수 D-3) |
| `hub/README.md` | UPDATE | 프라이버시 고지 새 항목 (§6). 2회차: 파일 수 18→19, "읽지 않는다"→"인라인하지 않는다" 정정 + 인라인 필드 목록에 `phase_title` 추가(검수 C-5). 3회차: `phase_title` 401자 상한 반영(2회차는 스크럽만 기술) + 128자 메타 상한·에이전트 100개 상한 신규 서술 추가(결정 WF7 개정·WF13) |
| `commands/hub.md` | UPDATE(1회차) | 설치 고지 문구 1줄 (§6). 2회차 변경 없음 |
| `hub/install.sh` | UPDATE(2회차, 1회차 표 누락) | `HUB_FILE_COUNT` 18→19(검수 A-1) |
| `tests/run.sh` | UPDATE(2회차, 1회차 표 누락) | `HUB_FILE_COUNT`·파일 수 서술 갱신(T25-104·T25-149), `renderWorkflowChip` escapeHtml 회귀 가드 + `hub_workflow.py`·`hub_redact.py` ★순수 회귀 가드 신설(검수 C-6, T25-164·T25-165). 3회차: T25-164 세 번째 부정 검사(사실상 무발화, 검수 3회차 지적)를 실제 사각(에이전트 필드가 두 헬퍼 함수 바깥에서 참조되는지)을 겨냥하도록 재작성 |
| `tests/hub/test_hub_workflow.py` | **CREATE**(1회차) | 순수 파서 단위 테스트. 2회차: 401자 상한·`phase_title` 스크럽·`RecursionError` 테스트 추가. 3회차: `phase_title` 401자 절단·128자 메타 상한·에이전트 100개 상한 테스트 추가 + `dataclasses.fields()` 순회 래칫(`StringFieldLengthRatchetTest`)과 병리적 입력 표 래칫(`ParserNeverRaisesOnPathologicalInputTest`) 신설 |
| `tests/hub/test_hub_workflow_read.py` | **CREATE**(2회차) | `hub_workflow_read.py` I/O 접합 단위 테스트 — 1회차 `test_hub_collect.py::ReadSessionWorkflowTest` 를 이관하고 B-1·C-4·C-7·D-1·D-2 테스트를 더했다 |
| `tests/hub/test_hub_collect.py` | UPDATE | 1회차: `ReadSessionWorkflowTest`(단위)·`CollectSnapshotWorkflowIntegrationTest`(통합) 추가. 2회차: 전자를 위 파일로 이관, 후자는 인터페이스 변경에 영향받지 않아 무수정 잔류 |
| `tests/hub/test_hub_session.py` | UPDATE(1회차) | 뷰 전달 계약. 2회차 변경 없음 |
| `tests/hub/test_hub_project.py` | UPDATE(1회차) | 합성 배선. 2회차 변경 없음 |
| `tests/hub/test_hub_model.py` | UPDATE(1회차) | 중첩 dataclass 직렬화·`snapshot_content_key` 안정성. 2회차 변경 없음 |

`hub_model.py` 는 **수정하지 않는다** — `HubSnapshot` 은 `ProjectView` 를 담고 그 안의
`SessionView` 가 새 필드를 갖는 것이므로 `asdict` 가 자동으로 따라간다(계약 변경은 있으나
코드 변경은 없다. 테스트는 추가한다).

### 반드시 먼저 읽을 파일

| 우선 | 파일 | 줄 | 왜 |
|---|---|---|---|
| P0 | `hub/bin/hub_transcript.py` | 전체(117줄) | 이 모듈이 따를 형태의 정본 — 외부 형식 순수 파서 |
| P0 | `hub/bin/hub_collect.py` | 259-320 | `_read_transcript_tail`·`read_session_model(s)` — I/O 접합 관용구 |
| P0 | `hub/bin/hub_session.py` | 76-115, 341-367 | `SessionView.model` 이 들어간 방식(선례 MD7) |
| P0 | `hub/bin/hub_hook.py` | 40-127 | 스크럽 파이프라인과 정규식 제약 주석 |
| P1 | `hub/bin/hub_project.py` | 263-313 | `compose_project_views` 의 `model_by_session_id` 배선 |
| P1 | `hub/bin/hub_template.html` | 1094-1231 | 칩·툴팁·세션 줄 렌더 |
| P1 | `hub/bin/hub_template.html` | 27-60, 412-431 | 불변식 H1 · `.tooltip` CSS 근거 |
| P2 | `docs/prps/hub-tier1-clamp-fix-and-session-model.md` | 결정 MD1~MD10 | 같은 성격 선례 전체 |
| P2 | `docs/prps/tier0-defect-fixes.md` | 330-410 | 스크럽 도입 당시 결정(WF3 이 뒤집는 대상) |

---

## 6. 데이터 모델

`hub/bin/hub_workflow.py`:

```python
@dataclass(frozen=True)
class WorkflowAgentView:
    """워크플로우 실행 안의 서브에이전트 1개 — 화면 표시용 투영."""

    index: int                    # 1-based, 스크립트 순서. 정렬 키(실측 502/502 연속). [0, WORKFLOW_RUN_MAX_AGENTS] 범위 상한(루프 밖 보완 — 자릿수 폭탄 방어, _bounded_index)
    label: str                    # 스크립트가 붙인 팬아웃 식별자. 스크럽 + 401자 상한(구현 2회차 검수 C-1, 표시 절단은 별도로 클라이언트도 함)
    phase_title: str              # 소속 단계 이름. 실측 502/502 존재하나 빈 문자열은 허용. 스크럽 + 401자 상한(구현 3회차 — 2회차는 스크럽만 하고 401자 상한이 빠져 있었다, 검수 재현)
    state: str                    # 원문 그대로, 128자 상한만(구현 3회차, 스크럽 없음 — 결정 WF7 개정)
    prompt_preview: str           # 호스트가 400자로 자른 프롬프트 머리, 스크럽 + 401자 상한 후(검수 C-1)
    result_preview: str | None    # 같은 형태의 결과 머리. state=="error" 면 None(실측 33/33)
```

```python
@dataclass(frozen=True)
class WorkflowRunView:
    """세션의 최신 워크플로우 실행 1건 — 화면 표시용 투영.

    **[루프 밖 보완]** run_id·workflow_name·status·started_at_ms 4개 필드를 제거했다 —
    hub_template.html 어디에서도 참조되지 않는 미사용 필드였다(데이터 최소화, YAGNI. 근거는
    §19). run_id 를 "파일 교차 참조용"으로 적었던 아래 서술은 그 툴팁이 끝내 구현되지
    않아 무효가 됐다.
    """

    agents: tuple[WorkflowAgentView, ...]    # index 오름차순, 최대 WORKFLOW_RUN_MAX_AGENTS 개(구현 3회차, 결정 WF13)
```

`hub/bin/hub_session.py` — `SessionView` 에 필드 1개 추가:

```python
    model: SessionModel | None = None
    # 이 세션의 최신 워크플로우 실행(결정 WF1). model 과 같은 계열이다 — 이 함수가 계산하지
    # 않고(파일 읽기는 I/O), 정당하게 부재할 수 있는 부가 정보이므로 기본값 None 을 둔다
    # (started_at_ms 의 "정체성 필드에 기본값 금지" 관례는 적용되지 않는다).
    workflow: WorkflowRunView | None = None
```

**`SessionFacts` 에는 넣지 않는다** — 그 dataclass 의 문서화된 계약은 "훅 이벤트를 접어 만든
사실"이고, 워크플로우 파일은 훅 이벤트가 아니다. `SessionModel` 도 같은 이유로
`SessionFacts` 가 아니라 `SessionView` 에 붙었다(결정 MD1).

**의존 방향**: `hub_session` → `hub_workflow` (이미 `hub_session` → `hub_transcript` 가 있는
것과 같은 방향). `hub_workflow` → `hub_redact`. 순환 없음.

---

## 7. 인터페이스

### `hub/bin/hub_redact.py` (★순수, 신규)

```python
SECRET_REDACTION_MARK = "[REDACTED]"
SECRET_TOKEN_PATTERN: re.Pattern[str]        # hub_hook 에서 이동(주석 포함)
KEY_VALUE_SECRET_PATTERN: re.Pattern[str]    # hub_hook 에서 이동

def redact_secret_tokens(prompt: str) -> str:
    """알려진 시크릿 토큰 형태를 마스킹한다. 선형 시간 — 백트래킹 폭발 형태 금지."""
```

### `hub/bin/hub_workflow.py` (★순수)

```python
WORKFLOWS_DIR_NAME = "workflows"          # <session_id>/ 아래 실행 기록 디렉터리
WORKFLOW_RUN_FILE_GLOB = "wf_*.json"
WORKFLOW_RUN_MAX_BYTES = 4 * 1024 * 1024  # 4MiB — 실측 최대(818KB)의 약 5.1배(결정 WF11)
WORKFLOW_PREVIEW_MAX_CHARS = 401          # 400+말줄임표(구현 2회차 검수 C-1, 결정 WF12)
WORKFLOW_PREVIEW_TRUNCATION_MARK = "…"
WORKFLOW_METADATA_MAX_CHARS = 128         # state 전용, 스크럽 없음(구현 3회차, 결정 WF7 개정). 루프 밖 보완으로 run_id·workflow_name·status 는 미사용 필드로 제거됐다(§19)
WORKFLOW_RUN_MAX_AGENTS = 100             # 실측 최대(25, §3 계측 8)의 4배 여유(구현 3회차, 결정 WF13). 루프 밖 보완: index 값 자체의 상한(_bounded_index)으로도 재사용한다

_AGENT_ITEM_TYPE = "workflow_agent"        # workflowProgress 안의 항목 종류 판별값

def parse_workflow_run(text: str) -> WorkflowRunView | None:
    """wf_<runId>.json 본문을 표시용 뷰로 판다. 형식이 아니면 None (호출자가 건너뛴다).

    **계약 B(구현 3회차) — 이 함수는 어떤 입력에도 예외를 던지지 않는다.** label·
    phase_title·prompt_preview·result_preview 는 뷰를 만들기 전에 전부 스크럽하고 401자로
    자른다(결정 WF7 개정 — phase_title 은 2회차에 스크럽만 추가되고 401자 상한이 빠져
    있었다, 검수 3회차 재현). state 는 스크럽 없이 128자로만 자른다
    (WORKFLOW_METADATA_MAX_CHARS, 결정 WF7 개정 — 2회차까지는 상한이 전혀 없었다).
    **루프 밖 보완**: index 는 [0, WORKFLOW_RUN_MAX_AGENTS] 범위로 클램핑한다(_bounded_index
    — 정수 필드는 문자열 상한 계약 A 가 못 덮는 채널이었다). 에이전트 개수도
    WORKFLOW_RUN_MAX_AGENTS 로 상한을 건다(결정 WF13). run_id·workflow_name·status 3개는
    hub_template.html 참조가 0건인 미사용 필드라 제거했다(§19). json.loads 는
    (ValueError, RecursionError) 를 함께 잡는다 — json.JSONDecodeError 가
    ValueError 의 서브클래스라 기존 케이스를 포함하면서, 4,300자리를 넘는 정수 리터럴이
    던지는 순수 ValueError 까지 덮는다(구현 3회차 — 2회차는 json.JSONDecodeError 만 잡아
    이 형제 예외가 여전히 collect_snapshot 전체를 죽일 수 있었다, 검수 3회차 재현).
    RecursionError(구현 2회차 검수 C-3) — 깊게 중첩된 입력은 RecursionError 를 던지는데
    1회차는 JSONDecodeError 만 잡아 이 파일 하나가 collect_snapshot 전체를 죽일 수
    있었다.
    """
```

### `hub/bin/hub_workflow_read.py` (I/O, 구현 2회차 신설 — 검수 A-1)

`hub_collect.py` 가 800/800줄 상한에 닿아 워크플로우 I/O 함수 3개(약 47줄)를 옮겼다(결정
WF12). 순환 임포트를 피하기 위해 `PROJECTS_DIR` 은 이 모듈에 다시 선언하지 않고
`hub_collect.py` 가 자신의 `PROJECTS_DIR` 을 인자로 넘긴다.

```python
def read_session_workflow(
    session_id: str, observed_cwds: Sequence[str], projects_dir: Path
) -> tuple[hub_workflow.WorkflowRunView | None, str | None]:
    """세션의 최신 워크플로우 실행 기록을 읽어 (뷰, 경고) 를 돌려준다. 절대 예외를 던지지 않는다.

    모든 관측 cwd 의 workflows/ 를 훑어 전체에서 mtime 최신인 실행 1건을 고른다(결정 WF4
    개정, 검수 B-1). 상한 초과·읽기 실패면 경고를 채운다(결정 WF11, 검수 C-4). session_id
    는 경로 조립에 쓰이므로 `/`·빈 문자열·`.`·`..` 를 조립 전에 걷어낸다(검수 C-7).
    """

def read_session_workflows(
    sessions_by_path: dict[str, tuple[hub_session.SessionFacts, ...]],
    record_prompt_excerpt: bool,
    projects_dir: Path,
) -> tuple[dict[str, hub_workflow.WorkflowRunView], tuple[str, ...]]:
    """수집 대상 세션 전부의 최신 워크플로우와 경고를 모은다. 값을 못 얻은 세션은 키를 넣지 않는다.

    record_prompt_excerpt 가 거짓이면 **파일을 아예 읽지 않고** 빈 결과를 돌려준다
    (결정 WF8 — show_usage_panel:false 가 사용량 파일을 읽지 않는 결정 U4 와 같은 형태).
    """
```

`collect_snapshot` 안의 배선(1회차: 1줄 추가. 2회차: 호출 대상이 `hub_workflow_read` 로
바뀌고 warnings 수집이 추가됨):

```python
    model_by_session_id = read_session_models(sessions_by_path)
    workflow_by_session_id, workflow_warnings = hub_workflow_read.read_session_workflows(
        sessions_by_path, config.record_prompt_excerpt, PROJECTS_DIR
    )
    warnings.extend(workflow_warnings)
    projects = hub_project.compose_project_views(
        tier1_by_path, sessions_by_path, tier3_by_path, now_ms, stale_after_ms,
        model_by_session_id, workflow_by_session_id,
    )
```

### `hub/bin/hub_session.py` · `hub/bin/hub_project.py`

```python
def compute_session_view(
    facts: SessionFacts, now_ms: int, stale_after_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,
    model: SessionModel | None = None,
    workflow: WorkflowRunView | None = None,      # 추가
) -> SessionView: ...

def compose_project_views(
    tier1_by_path, sessions_by_path, tier3_last_activity_by_path, now_ms, stale_after_ms,
    model_by_session_id: dict[str, SessionModel] | None = None,
    workflow_by_session_id: dict[str, WorkflowRunView] | None = None,   # 추가
) -> tuple[ProjectView, ...]: ...
```

두 함수 모두 **기본값 None 인 마지막 인자**로 더한다 — 기존 호출부가 무해하고, `model` 이
정확히 그 방식으로 들어온 선례가 있다. (7번째 인자가 되는 것에 대한 대안은 §10 대안 4.)

---

## 8. 렌더링 (`hub_template.html`)

### 상수 (기존 상수 블록, 856-882행 인접)

```js
var MAX_VISIBLE_WORKFLOW_CHIPS = 6;     // Task 5 에서 카드 높이 실측으로 확정한다
var WORKFLOW_LABEL_MAX_CHARS = 18;      // 표시 절단. 실측 median 16 · p90 35 · max 60
var WORKFLOW_STATE_ERROR = 'error';
var WORKFLOW_RESULT_TOOLTIP_SEPARATOR = '\n\n— 결과 —\n';
```

`MODEL_LABEL_MAX_CHARS = 10` 이 세운 선례를 따른다: **표시 상한은 CSS 가 아니라 JS 가 건다.**
`.session-meta` 에서 `overflow:hidden` 으로 폭을 다스렸을 때 가로 flex 형제가 짓눌려 줄 높이가
2배로 붕괴한 함정(§3.10 GOTCHA)이 이미 문서화돼 있다.

### 함수 (순수 — DOM 에 닿지 않는다)

```js
function workflowChipTooltipText(agent)   // "label · phaseTitle" + 개행 + prompt (+ 결과)
function workflowChipDisplayLabel(agent)  // 상한 초과 시 TRUNCATION_MARK 로 절단
function visibleWorkflowAgents(agents)    // 표시 목록의 유일한 판정자 (GOTCHA 3 관용구)
function renderWorkflowChip(agent)        // <span class="agent-chip"> + data-tooltip
function renderWorkflowRun(workflow)      // 행 전체. workflow 없으면 '' (줄이 생기지 않는다)
```

`renderSession` 에 한 줄 추가:

```js
      + '</div>' + renderSessionMeta(session)
      + renderWorkflowRun(session.workflow)          // 추가
      + renderSessionExcerpt(displayableExcerpt(session.task_excerpt)) + '</li>';
```

배치 근거: `.session-meta`(식별 줄) **뒤**, 발췌 **앞**. 발췌는 "사용자가 마지막에 입력한 것"이고
워크플로우 칩은 "그 입력이 팬아웃된 결과"라 인과 순서와 맞는다. `.session-line`(첫 줄)의 자식으로
넣지 않는 이유는 `.session-meta` 와 같다 — 좁은 카드의 첫 줄 `flex-wrap` 거동을 바꾸지 않는다.

### 툴팁 문구

```
{label} · {phaseTitle}
{prompt_preview}

— 결과 —
{result_preview}
```

`state == "error"` 면 결과 절이 없다(`result_preview is None`, 실측 33/33). `.tooltip` 이
`white-space: pre-wrap` 이라 개행이 살아난다. 최대 분량 = 60 + 37 + 401 + 구분자 + 401 ≈ 910자로,
이미 검증된 500자 케이스보다 크다 — **Task 5 에서 420px 폭·max-height 안에 들어가는지 실측하고,
넘치면 결과 절을 뺀다**(프롬프트가 요구의 본체다).

### 오버플로 정책

실행당 에이전트가 최대 25개다(계측 8). 상한 밖은 **표시하지 않는다** — `"+N"` 오버플로 칩은
결정 K3 에서 이미 폐기됐다. 상한 안에 무엇이 들어갈지는 `index` 오름차순, 즉 **스크립트가 먼저
띄운 순서**다. (`agent_runs` 는 "실행 중 먼저"로 정렬하지만(결정 K2), 여기서는 실측 데이터가 전부
종료 상태라 그 정렬이 의미를 갖지 않는다. Task 0 에서 라이브가 확인되면 그때 K2 와 같은 정렬로
바꾸고, 그 변경은 **서버의 순수 함수에서** 한다.)

### 불변식 문서 갱신

`hub_template.html` 헤더 주석(27-60행 영역)에 세션 줄 구성 설명이 있다. 새 행이 `#dzh-app`
자식 안에만 살고 `#dzh-detail-panel`·`#dzh-usage`·`#dzh-tooltip` 을 건드리지 않는다는 것을
한 문단으로 명시한다(결정 WF9 의 근거를 코드 옆에 남긴다).

---

## 9. 프라이버시 고지 변경

현재 `hub/README.md:182-188` 의 마지막 항목은 트랜스크립트 읽기를 설명하며
*"대화 내용(프롬프트·응답 본문)은 읽지 않으며 어디에도 저장하지 않는다"* 고 적는다. 그 문장은
트랜스크립트 경로에 대해서는 **여전히 참**이지만, 이 기능은 그 옆에 **프롬프트·결과 본문을 실제로
읽어 `hub.html` 에 인라인하는 새 경로**를 만든다. 항목을 하나 추가하지 않으면 고지가 통째로
오해를 만든다.

**`hub/README.md` 프라이버시 고지에 추가할 항목** (내용 요구사항):

1. [**구현 2회차 검수 C-5 로 정정**] 읽는 파일: `~/.claude/projects/<인코딩>/<session_id>/
   workflows/wf_*.json` 의 **세션당 최신 1건**을 4MiB 상한 안에서 **파일 전체를 읽어
   파싱한다** — `script`(스크립트 전문)·`logs`·`result` 도 이 파싱 과정에서 디스크에서
   읽힌다(그래서 4MiB 상한이 필요하다). 참인 것은 "읽지 않는다"가 아니라 **"hub.html 에
   인라인하지 않는다"**다.
2. [**구현 2회차 검수 C-5 로 정정. 루프 밖 보완으로 실행 메타 항목 제거**] 인라인되는
   콘텐츠: 에이전트별 `index`·**`label`**·`phase_title`(소속 단계 이름)·`state`·
   **프롬프트 앞 400자**·**결과 앞 400자**. (**루프 밖 보완**: 이전 판은 여기에 실행
   메타 `run_id`·`workflow_name`·`status`·`started_at_ms` 4개도 인라인된다고 적었으나,
   그 넷은 hub_template.html 어디에서도 참조되지 않는 미사용 필드였다 — 데이터 최소화
   근거로 제거했다, §19.) 1회차는 `phase_title` 을 이 목록에서 빠뜨렸는데, 그 값은 툴팁
   헤더에 실제로 표시된다(검수 C-2). 이 400자는 우리가 자른 것이 아니라 **호스트가 이미
   잘라 놓은 분량**이고, `label`·`phase_title`·프롬프트·결과 네 값 모두에 서버측 상한
   (401자, 결정 WF7 개정)도 걸려 있다(구현 2회차 검수 C-1. **[루프 밖 보완 — 발동 빈도
   서술 정정]** 이전 판은 여기서 "오늘 데이터에는 발동하지 않는다"고 적었으나 틀렸다 —
   실물 74개 파일·503개 항목 재실측에서 promptPreview 의 497/503(98.8%)이 이미 정확히
   401자라 여유가 0이고, 스크럽이 값을 **늘릴 수 있어**(예: 6자 시크릿 값이 10자
   `[REDACTED]` 로 치환) 이 상한은 실사용 데이터에서도 실제로 발동한다. **구현 3회차
   정정**: 2회차는 이 401자 상한을 `phase_title` 에는 걸지 않아 100,000자가 그대로
   통과했다 — 검수 3회차 재현). `state` 는 스크럽 대상은 아니지만 128자 상한
   (`WORKFLOW_METADATA_MAX_CHARS`, 결정 WF7 개정)이 걸려 있다(구현 3회차 — 2회차까지는
   상한이 전혀 없었다). 에이전트 개수도 세션당 최대 100개(`WORKFLOW_RUN_MAX_AGENTS`,
   결정 WF13)로 제한된다 — 클라이언트 표시 상한(`MAX_VISIBLE_WORKFLOW_CHIPS`)은 화면에 몇
   개 보여줄지를 정할 뿐 뷰 자체의 직렬화 크기를 막지 못했다(구현 3회차 검수 재현: 에이전트
   30,000개). **루프 밖 보완**: `index` 도 [0, `WORKFLOW_RUN_MAX_AGENTS`] 범위 상한
   (`_bounded_index`)이 걸려 있다 — 정수 필드는 문자열 상한 계약이 못 덮는 채널이었다
   (자릿수 폭탄 방어, §19).
3. **새로 노출되는 콘텐츠 종류임을 명시**: 지금까지 인라인된 발췌는 *사용자가 타이핑한 프롬프트*
   뿐이었다. 여기서 늘어나는 것은 **스크립트가 서브에이전트에게 준 지시와 그 결과**다.
4. 마스킹: 시크릿 패턴은 `[REDACTED]` 로 마스킹된다(`hub_redact.redact_secret_tokens`, 훅과 **같은**
   구현).
5. **잔존 위험 명시**(결정 WF7): 훅 경로는 `마스킹 → 자르기` 순서를 보장하지만 이 경로는 호스트가
   이미 잘라 놓은 문자열을 받으므로 **400자 경계에 걸친 시크릿의 접두사가 남을 수 있다.**
6. 오프 스위치: `config.json` 의 `record_prompt_excerpt: false`(결정 WF8) — 켜면 파일을 **읽지
   않는다**. 이 플래그가 이미 "hub.html 인라인 발췌"의 오프 스위치로 문서화돼 있음을(159-165행)
   상호 참조한다.
7. 새 파일을 만들거나 보관 기간을 늘리지 않는다(트랜스크립트 항목과 동일).

**`commands/hub.md:146-151` 설치 고지**: ①번 문단에 한 줄 추가 — 워크플로우를 쓰는 세션은
서브에이전트에게 준 지시·결과의 앞 400자와 각 에이전트의 **label·소속 단계 이름**도
`~/.claude/hub/hub.html` 평문 파일에 인라인되어 허브 화면(127.0.0.1 서버가 그 파일을
제공)에 표시되며, 같은 `record_prompt_excerpt` 플래그로 끌 수 있다. **[루프 밖 보완]**
1~2회차 구현이 실제로 적용한 문구는 label·phase_title 언급과 저장 형태(평문 파일·로컬
서버 제공)를 빠뜨렸다 — ①번 문단의 프롬프트 절이 이미 "평문으로 최대 7일 보관됩니다"까지
밝히는 수준에 맞춰 정정했다(근거는 §19).

> **이 두 문서에는 이미 문서-실물 정합 회귀 검사가 걸려 있다.** `tests/run.sh` 의
> T25-3·T25-8·T25-14·T25-19·T25-22·T25-25·T25-31·T25-36 이 `commands/hub.md`·`hub/README.md`
> 의 특정 토큰 존재/부재를 직접 검사한다(예: T25-8 은 포트 8794 가 두 곳에 있는지, T25-14 는
> 폐기된 `serve` 잔재가 없는지). 문구를 실물과 어긋나게 쓰지 말고, 위 1~7 의 수치를 §2·§3
> 표에서 그대로 가져다 쓴다. 새 항목이 기존 검사를 깨면 **검사를 고치지 말고 문구를 고친다.**

---

## 10. 성능 — 예상 비용과 **검증 절차**

### 예상 증분 (계측 근거)

| 단계 | 호출 수 (현재 실측) | 비용 |
|---|---|---|
| 활성 세션당 관측 cwd 후보의 `workflows/` `is_dir()` | 24회 | **0.26ms** (계측 3) |
| 양성 **디렉터리**당 `glob` 1회(구현 2회차 검수 B-1 — 존재하는 디렉터리 전부를 훑는다) | 3회 | **< 0.1ms** (계측 6: 28회 0.73ms) |
| 양성 디렉터리당 후보 파일 `stat`(mtime) | 3 × ≤10 | 무시 가능 |
| 선택된 파일 1건의 `json.load` | 세션당 최대 1회 | **~0.8ms** (계측 5: 25개 6.8ms) |
| **합계 (기대)** | | **약 +1.2ms** (기준선 8.8~10.6ms → **약 10~12ms**) |
| **합계 (최악)** | 양성 세션 3개가 전부 818KB 급 | **약 +10ms** (3 × 3.33ms) → 약 21ms |

에스컬레이션 임계(문서화된 50ms)의 **20~42%** 다. `record_prompt_excerpt: false` 면 증분 0.

**[구현 2회차 검수 B-1 반영]** 1회차는 "먼저 존재하는 디렉터리에서 멈춘다"였으므로 세션당
`glob` 이 최대 1회였다. 개정 후에는 관측 cwd 마다 존재하는 디렉터리 **전부**를 `glob` 한다
— 위 표의 "양성 세션당" 을 "양성 **디렉터리**당" 으로 고친 것이 그 반영이다. 세션당 관측
cwd 가 실측상 1~2개(§10 재측정)이므로 최악 배수는 최대 2배이고, 그래도 에스컬레이션
임계의 절반에 못 미친다(§16 재측정 결과 참조).

### 검증 절차 (구현 시 **실제로 수행할 것**)

추정으로 끝내지 않는다. 다음을 순서대로 실행하고 수치를 PRP 하단 「측정 결과」에 적는다.

1. **전 기준선 재측정** (구현 착수 전, 현재 커밋):
   ```bash
   cd /Users/dev/private/project/coding-harness-worktrees/hub-workflow-visibility
   python3 -c "
   import sys, time; sys.path.insert(0, 'hub/bin')
   import hub_collect
   now = int(time.time()*1000)
   hub_collect.collect_snapshot(now)                      # 워밍업
   ts = []
   for _ in range(5):
       t0 = time.perf_counter(); hub_collect.collect_snapshot(now)
       ts.append((time.perf_counter()-t0)*1000)
   print('before: min=%.1f median=%.1f max=%.1f ms' % (min(ts), sorted(ts)[2], max(ts)))
   "
   ```
2. **후 측정** — 같은 스크립트를 구현 후 실행. 활성 세션 수와 `workflows/` 양성 수를 함께 기록한다
   (모집단이 다르면 두 수치를 비교할 수 없다).
3. **실제 워크플로우 1회 실행 후 재측정** — 그 세션이 양성이 되므로 양성 표본이 늘어난 상태에서
   한 번 더 측정한다. **이 실행이 Task 0(라이브 여부 판정)과 같은 실행이다.**
4. **판정**: median 이 50ms 를 넘으면 캐시를 재검토한다(결정 WF10 의 에스컬레이션 조건). 넘지
   않으면 캐시를 만들지 않는다.

---

## 11. 테스트 계획

이 저장소는 **`unittest`** 를 쓴다(전역 rules 의 pytest 권고와 다르며 프로젝트 관례가 우선한다).
스타일 정본은 `tests/hub/test_hub_transcript.py` — 각 테스트가 실측에서 나온 실제 값을 쓰고,
docstring 이 어느 결정을 고정하는지 밝힌다.

### `tests/hub/test_hub_workflow.py` (신규 · 순수 · 이 기능의 주력)

| 테스트 | 입력 | 기대 |
|---|---|---|
| 정상 실행 파싱 | §2 계약대로의 최소 JSON | 뷰 필드 전부 일치, agents 는 `index` 오름차순 |
| `workflow_phase` 항목 무시 | phase + agent 혼재 배열 | agent 만 담긴다 |
| `error` 상태 결과 결측 | `state:"error"`, `resultPreview` 없음 | `result_preview is None` (실측 33/33) |
| `index` 역순 입력 | index 3,1,2 | 1,2,3 으로 정렬 |
| 미지의 state 값 | `state:"cancelled"` | 원문 보존(표로 좁히지 않는다 — 계약이 바뀔 수 있다) |
| 깨진 JSON | `"{"` | `None` |
| dict 아님 | `"[]"`, `"3"` | `None` |
| `workflowProgress` 없음 | 최상위만 있는 JSON | agents 빈 tuple, 뷰 자체는 반환 |
| agent 0개 | phase 만 있는 배열 | agents 빈 tuple |
| **프롬프트 스크럽** | `promptPreview` 에 `sk-ant-…` | `[REDACTED]` 포함, 원문 미포함 |
| **결과 스크럽** | `resultPreview` 에 AWS 키 | 동일 |
| **label 스크럽** | `label` 에 `ghp_…` | 동일 (§2 — label 도 콘텐츠다) |
| key=value 스크럽 | `api_key=abcdef123456` | 키 이름 보존, 값만 마스킹 |
| 타입 방어 | `label:123`, `promptPreview:null` | 예외 없이 안전한 기본값 |
| **[구현 2회차 검수 C-1]** 401자 초과 | `promptPreview`/`resultPreview` 104,000자, `label` 5,000자 | 스크럽 후 401자로 절단(`…` 종료). 401자 이하 값은 무변화 |
| **[구현 2회차 검수 C-1]** 절단 경계 근처 시크릿 | 350번째 문자부터 시작하는 시크릿을 포함한 550자 문자열 | 스크럽이 절단보다 먼저 일어나 시크릿 흔적이 잘린 결과에 없다 |
| **[구현 2회차 검수 C-2]** `phase_title` 스크럽 | `phaseTitle` 에 `ghp_…` | `[REDACTED]` 포함(1회차는 스크럽 없이 통과시켰다) |
| **[구현 2회차 검수 C-3]** 깊은 중첩 JSON | `"["*200000 + "]"*200000`(400KB) | `None`, 예외 없음(`RecursionError` 를 `json.JSONDecodeError` 와 함께 잡는다 — 1회차는 여기서 `collect_snapshot` 전체가 죽었다) |
| 절단 마크 보존 | 401자 `…` 종료 | 그대로 보존(잘렸다는 사실이 화면에 남아야 한다) |

### `tests/hub/test_hub_workflow_read.py` (I/O 접합 — `mock.patch` 없이 임시 디렉터리로)

**[구현 2회차 검수 A-1 로 파일명 갱신]** 1회차에는 이 표의 테스트가 `test_hub_collect.py` 에
있었다(그때는 함수가 `hub_collect.py` 소속이었다). 함수를 `hub_workflow_read.py` 로 옮기며
(결정 WF12) 테스트도 함께 옮겼다. `collect_snapshot` 통합 테스트만 `test_hub_collect.py` 에
남았다(그 함수의 소유자가 여전히 `hub_collect.py` 이므로).

| 테스트 | 기대 |
|---|---|
| `workflows/` 없음 | `None`, 예외 없음 |
| 실행 파일 여러 개(단일 디렉터리) | **mtime 최대**가 선택된다 (결정 WF5) |
| mtime 동일 | 파일명 역순 사전식으로 결정적 선택 |
| `observed_cwds` 2개 중 두 번째에만 `workflows/` 존재 | 두 번째에서 찾는다 (워크트리, E13) |
| **[구현 2회차 B-1]** `observed_cwds` 2개 모두 `workflows/` 존재, 서로 다른 mtime | **전체에서 mtime 최신**인 실행이 선택된다(디렉터리 경계를 넘어 풀링, 결정 WF4 개정) — 1회차는 여기서 "먼저 존재하는 후보"가 이겨 오래된 실행을 고르는 결함이 있었다 |
| 첫 후보가 빈 디렉터리, 두 번째에 유효한 파일 | **[구현 2회차 D-2 재작성]** 두 번째 파일이 찾아진다(1회차는 `None` 이었다 — "먼저 존재하는 디렉터리가 이긴다"가 B-1 로 폐기됐다) |
| 풀링된 후보 중 mtime 최신 파일이 파싱 실패, 더 오래된 다른 후보는 유효 | **[구현 2회차 D-2]** `None` — **더 오래된 후보로 넘어가지 않는다**(결정적, 상한이 곧 예산 — 1회차 "다음 후보로 넘어가지 않는다"(결정 MD2 의 E7)의 현대 형태) |
| 파일 > `WORKFLOW_RUN_MAX_BYTES` | 읽지 않고 `(None, 경고)` — **[구현 2회차 C-4]** 1회차는 경고 없이 무음 `None` 이었다(결정 WF11) |
| 읽기 권한 없음(파일) / 깨진 UTF-8 | `(None, 경고 또는 None)`, 예외 없음 (`UnicodeDecodeError` 는 `ValueError` 라 `except OSError` 를 뚫는다 — GOTCHA 7). 파싱 실패는 경고 없음, 읽기 실패(OSError)는 경고 있음 |
| **[구현 2회차 D-1]** `workflows_dir` 의 부모(session_id 디렉터리) 권한 거부 | `None`, 예외 없음(`is_dir()` 의 EACCES 분기 — pathlib 은 ENOENT 는 삼키고 EACCES 는 올린다). root 는 재현 불가라 skip |
| **[구현 2회차 C-7]** `session_id` 에 `/`·`.`·`..`·빈 문자열 | 경로 조립 전에 거부, `None` |
| `record_prompt_excerpt=False` | `({}, ())` 이고 **파일 열기 시도가 0회** (열기 함수를 감싸 호출 수로 검증) |
| `collect_snapshot` 통합(`test_hub_collect.py` 잔류) | 워크플로우 있는 세션의 뷰에 값이 실린다 |

### 기존 파일 보강

- `test_hub_session.py` — `compute_session_view(workflow=…)` 가 뷰에 그대로 실어 나른다;
  인자 없으면 `None`; **워크플로우 값이 `state` 판정을 바꾸지 않는다**(보강일 뿐 상태 입력이
  아님 — 결정 WF1 의 회귀 검사).
- `test_hub_project.py` — `compose_project_views` 가 `workflow_by_session_id` 를 session_id 로
  맞춰 전달; 키 없는 세션은 `None`; 인자 생략 시 기존 동작 불변.
- `test_hub_model.py` — 중첩 dataclass 가 `asdict` 로 직렬화되고 `render_hub_html` 의
  `json.dumps` 를 통과한다; **`snapshot_content_key` 가 같은 입력에 같은 값**을 준다(파생 "지금"
  값이 안 들어갔음을 고정 — 결정 D2).
- `test_hub_hook.py` — **수정하지 않는다.** `hub_hook.redact_secret_tokens` 재노출로 기존 테스트가
  그대로 통과해야 한다. **통과하지 않으면 WF3 의 추출 방식이 틀린 것이다**(회귀 신호로 쓴다).

### 엣지 케이스 체크리스트

- [x] 빈 입력 (`workflowProgress` 없음 / agent 0개)
- [x] 최대 크기 (4MiB 상한, 25 에이전트 오버플로)
- [x] 잘못된 타입 (label/preview 가 문자열 아님)
- [x] 파일 I/O 실패 (권한·깨진 인코딩·경합 중 삭제)
- [ ] 동시 접근 — **해당 없음**: 이 경로는 읽기 전용이고 허브는 파일을 쓰지 않는다
- [x] 옵트아웃 경로 (`record_prompt_excerpt: false`)

---

## 12. 작업 순서

### Task 0 — 라이브 여부 실측 (**다른 모든 Task 보다 먼저**)
- **ACTION**: 실제 Workflow 실행을 1회 띄우고 실행 중에 `workflows/` 를 관찰한다.
  ```bash
  # 실행 중 반복 확인 — 진행 중 파일이 생기는가, status 는 무엇인가
  ls -la ~/.claude/projects/*/*/workflows/
  python3 -c "
  import glob,json,os
  for p in glob.glob(os.path.expanduser('~/.claude/projects/*/*/workflows/wf_*.json')):
      d=json.load(open(p)); print(d.get('status'), os.path.basename(p))
  " | sort | uniq -c
  ```
- **VALIDATE**: 진행 중에 `status != "completed"` 인 파일이 보이면 **라이브**, 실행이 끝난 뒤에야
  파일이 나타나면 **회고**.
- **결과 반영**: 회고면 결정 WF6 의 기본 문구를 그대로 쓴다. 라이브면 §8 오버플로 정책의 정렬을
  결정 K2(실행 중 먼저)와 같게 바꾸고 진행형 문구를 더한다. **어느 쪽이든 §12 의 나머지 Task 는
  변하지 않는다.**
- 같은 실행으로 §10 검증 절차 3번을 함께 처리한다.

### Task 1 — `hub_redact.py` 추출 (결정 WF3)
- **ACTION**: 상수 3개 + 함수 1개 + 정규식 제약 주석을 `hub/bin/hub_redact.py` 로 이동.
- **IMPLEMENT**: `hub_hook.py` 는 `from hub_redact import redact_secret_tokens` 로 재노출.
  `_project_fields` 의 호출부(149행)는 **건드리지 않는다**.
- **MIRROR**: `hub_transcript.py` 모듈 docstring 형식(★순수 선언 + 분리 근거 + 테스트 대상 명시).
- **GOTCHA**: 정규식 위의 catastrophic-backtracking 제약 주석을 **반드시 함께** 옮긴다. 그 주석이
  없으면 다음 사람이 중첩 수량자를 넣는다.
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_hook` — **한 줄도 고치지 않고** 통과.
  `hub/bin/*.py` 를 각각 단독 임포트해 순환 없음 확인.

### Task 2 — `hub_workflow.py` 작성 (결정 WF2·WF7·WF11)
- **ACTION**: dataclass 2개 + `parse_workflow_run` + 상수.
- **MIRROR**: `hub_transcript.parse_session_model_from_tail` — 텍스트만 받고, 형식이 아니면 `None`,
  절대 예외를 던지지 않는다.
- **IMPORTS**: `import json`, `from dataclasses import dataclass`,
  `from hub_redact import redact_secret_tokens`.
- **GOTCHA**: `isinstance` 로 방어한다(호스트 소유 형식이라 타입 보장이 없다). `state` 를
  `Literal` 로 좁히지 않는다 — 실측에 없는 값이 나와도 화면이 죽지 않아야 한다.
- **VALIDATE**: 신규 테스트 파일 전체 통과 + **실물 파일 73개 전부에 대해 파서를 돌려
  `None`·예외가 0건**임을 확인(§2 계약의 실물 검증):
  ```bash
  python3 -c "
  import glob,os,sys; sys.path.insert(0,'hub/bin')
  import hub_workflow
  bad=0
  for p in glob.glob(os.path.expanduser('~/.claude/projects/*/*/workflows/wf_*.json')):
      v=hub_workflow.parse_workflow_run(open(p,encoding='utf-8',errors='replace').read())
      if v is None or not v.agents: bad+=1; print('FAIL', p)
  print('failures:', bad)
  "
  ```

### Task 3 — `hub_collect.py` I/O 접합 (결정 WF4·WF5·WF8)
- **ACTION**: `read_session_workflow` · `read_session_workflows` 추가, `collect_snapshot` 배선.
- **MIRROR**: `read_session_model`/`read_session_models`(259-318행) — 경로를
  `encode_project_dir_name` 으로 조립, `observed_cwds` 순회, `except OSError` 로 전부 삼킴, 캐시 없음.
- **GOTCHA**: `UnicodeDecodeError` 는 `ValueError` 서브클래스라 `except OSError` 를 **뚫는다**
  (GOTCHA 7). `_read_transcript_tail` 처럼 `errors="replace"` 로 디코딩한다.
- **GOTCHA**: 크기 확인은 `stat()` 로 하고, **열기 전에** 상한과 비교한다(결정 WF11).
- **VALIDATE**: `test_hub_collect.py` 신규 케이스 통과 + §10 검증 절차 1·2.

### Task 4 — 뷰 배선 (`hub_session.py` · `hub_project.py`)
- **ACTION**: `SessionView.workflow` 필드, 두 함수의 기본값 None 인자.
- **MIRROR**: 같은 두 파일에서 `model`/`model_by_session_id` 가 들어간 커밋 형태 그대로.
- **GOTCHA**: dataclass 규칙상 기본값 있는 필드는 **맨 뒤**다(`model` 뒤). `_compute_base_state`·
  `summarize_agent_runs` 를 **건드리지 않는다** — 워크플로우는 상태 판정 입력이 아니다(WF1).
- **VALIDATE**: `test_hub_session.py`·`test_hub_project.py`·`test_hub_model.py` 통과.

### Task 5 — 렌더 (`hub_template.html`) + **레이아웃 실측**
- **ACTION**: 상수 4개, 순수 함수 5개, `renderSession` 1줄, CSS 1규칙(행 컨테이너), 헤더 주석.
- **MIRROR**: `renderAgentChip`/`visibleAgentRuns`/`renderSessionExcerpt` — `escapeHtml` 필수,
  `data-tooltip` 은 **실제로 정보 손실이 있을 때만**(결정 R4).
- **GOTCHA**: 표시 상한은 JS 로 건다 — `.session-meta` 계열에 `overflow:hidden` 을 주면 가로 flex
  형제가 짓눌려 줄 높이가 2배로 붕괴한다(§3.10).
- **VALIDATE (실측 3건)**:
  1. **`MAX_VISIBLE_WORKFLOW_CHIPS` 확정** — 카드 높이가 340px 고정이다. 에이전트 25개 세션이
     담긴 스냅샷으로 렌더해 칩 수를 늘려 가며 카드가 넘치기 시작하는 값을 찾고, 그보다 하나 작은
     값으로 고정한다. 초기값 6 은 **가정이며 실측으로 대체할 것**.
  2. **툴팁 최대 분량 검증** — 60+37+401+401자 툴팁이 420px 폭 · `max-height: calc(100vh-16px)`
     안에 들어가는가. 넘치면 결과 절을 뺀다(프롬프트가 요구의 본체다).
  3. **라이트/다크 양 테마**에서 재사용한 `.agent-chip` 면색·글자색 대비 확인.
- **GOTCHA**: `shouldRenderSession` 을 고칠지 판단할 것. 현재 숨김 조건은 "완료 + 발췌 없음 +
  보이는 칩 0개"다. **워크플로우 칩만 있고 나머지가 없는 세션**이 이론적으로 가능하다 — 그러면
  칩이 있는데 줄이 숨는 어긋남(GOTCHA 3 과 같은 계열)이 난다. `visibleWorkflowAgents(...)
  .length > 0` 를 조건에 더할 것. **판정은 `visibleWorkflowAgents` 를 반드시 경유한다**(상한 밖으로
  밀린 에이전트 때문에 칩 없이 줄이 남는 것을 막는다).

### Task 6 — 문서 (§9)
- **ACTION**: `hub/README.md` 프라이버시 항목 추가, `commands/hub.md` 설치 고지 1줄.
- **GOTCHA**: 수치는 §2·§3 표에서 그대로 인용한다. 두 문서에는 `tests/run.sh` 의 T25-* 정합
  검사가 이미 걸려 있다(§9 말미 참조) — 새 문구가 기존 검사를 깨면 검사가 아니라 문구를 고친다.
- **VALIDATE**: `bash tests/run.sh` 전체 — 특히 상시 컨텍스트 예산 래칫(T26,
  `ALWAYS_ON_CONTEXT_BUDGET_BYTES=51195`). `hub/README.md`·`commands/hub.md` 는 상시 로드 대상이
  아니라 이 래칫에 걸리지 않아야 한다. **걸리면 예산을 올리지 말고 왜 걸렸는지 먼저 조사한다.**

---

## 13. 검증 명령

```bash
cd /Users/dev/private/project/coding-harness-worktrees/hub-workflow-visibility

# 허브 순수 모듈 단위 테스트 (이 저장소의 실제 명령 — pytest 가 아니다)
python3 -m unittest discover -s tests/hub -t .
# 기대: 전부 통과, 실패 0

# 특정 모듈만
python3 -m unittest tests.hub.test_hub_workflow -v
python3 -m unittest tests.hub.test_hub_hook -v      # WF3 추출의 회귀 신호

# 전체 스위트 (install.sh 검사 + 허브 테스트 + 문서 사실 검사 + 컨텍스트 예산 래칫)
bash tests/run.sh
# 기대: 실패 0

# 순환 의존 없음 확인
for m in hub_redact hub_workflow hub_transcript hub_session hub_project hub_model hub_collect hub_hook; do
  python3 -c "import sys; sys.path.insert(0,'hub/bin'); import $m" || echo "FAIL $m"
done

# 렌더 산출물 확인 (실제 스냅샷으로 hub.html 생성)
python3 hub/bin/hub.py collect && open ~/.claude/hub/hub.html
```

**수동 검증 체크리스트**
- [ ] 워크플로우를 돌린 세션의 카드에 label 칩 행이 보인다
- [ ] 칩에 호버하면 label · 단계 · 프롬프트 앞부분이 뜬다
- [ ] `error` 에이전트의 툴팁에 결과 절이 없다
- [ ] 워크플로우를 쓰지 않은 세션의 줄 모양이 **이전과 동일**하다(회귀 없음)
- [ ] 카드 높이 340px 를 넘기지 않는다(에이전트 25개 세션 포함)
- [ ] `record_prompt_excerpt: false` 로 두고 재수집하면 칩 행이 사라진다
- [ ] 라이트/다크 양 테마에서 칩이 읽힌다
- [ ] 상세 패널을 열고 닫아도 칩 행이 정상이다(불변식 H1 회귀)

---

## 14. 리스크와 채택하지 않은 대안

### 리스크

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| 호스트가 `wf_*.json` 스키마를 바꾼다 | 중 | 칩 행이 사라짐(허브는 죽지 않음) | 파서를 모듈 1개에 격리(WF2), 전부 `isinstance` 방어, 실패 시 `None` |
| 400자 경계에 걸린 시크릿 접두사 유출 | 저 | 프라이버시 | 완화 불가 — 고지에 명시(WF7·§9-5) + `record_prompt_excerpt` 오프 스위치 |
| 회고 데이터라 "지금"을 못 보여준다 | **미확정** | 요구 충족도 하락 | Task 0 에서 판정, 문구를 실물에 맞춘다(WF6). 회고라도 "파일을 뒤져야 한다"는 문제는 해결된다 |
| 파일이 커져 수집이 느려진다 | 저 | 지연 | 4MiB 상한(WF11) + 최신 1건만(WF5) + 50ms 에스컬레이션 조건(WF10) |
| 카드 높이 초과로 레이아웃 붕괴 | 중 | UI | Task 5 실측으로 상한 확정. 초기값 6 은 가정임을 명시 |
| `hub_redact` 추출이 훅 스크럽을 깬다 | 저 | **보안** | 기존 테스트를 **고치지 않고** 통과시키는 것을 합격 조건으로 삼음(WF3) |

### 대안 1 — 칩 1개 + 전체를 담은 메가 툴팁 (기각)

"간략히"에 가장 부합해 보였다. 기각 이유: `.tooltip` 은 `max-height: calc(100vh - 16px);
overflow: hidden` 이고 **스크롤을 주지 않는다**(캡처 단계 scroll 리스너가 툴팁을 즉시 숨겨
스크롤바가 동작하지 않는다 — CSS 주석 422-425행). 25 × 400자를 넣으면 대부분이 **아무 표시 없이
사라진다.** 칩별로 쪼개면 툴팁 하나가 이미 검증된 500자 케이스보다 작아진다.

### 대안 2 — 새 설정 키 `show_workflow_prompts` (기각)

플래그 이름이 정확해진다는 장점이 있다. 기각 이유: (a) `hub/README.md:159-165` 가 이미
`record_prompt_excerpt` 를 "hub.html 인라인 발췌"의 오프 스위치로 문서화하고 있어 재사용이 문서와
정합적이다, (b) 새 키는 `HubConfig`·`_validate_config_overrides`·문서 3곳·테스트를 늘린다,
(c) 사용자가 "내 프롬프트를 허브에 넣지 마라"를 이미 껐는데 새 종류의 프롬프트가 기본값으로
들어가는 것은 **의도 위반**이다. 두 스위치를 따로 두려면 실제 요구가 생긴 다음이다(YAGNI).
**단, 플래그 의미를 넓히는 것이므로 승인 필요 항목 ②로 올린다.**

### 대안 3 — 절단 경계의 토큰 유사 조각 추가 제거 (기각)

400자 경계 유출(WF7)을 막으려 "말줄임표로 끝나면 마지막 공백 이후를 버린다" 를 검토했다. 기각
이유: 시크릿이 아닌 정상 텍스트를 대부분의 경우에 훼손하고(오탐이 압도적), 시크릿이 공백 없이
긴 산문에 붙어 있으면 여전히 못 막는다. **추측성 방어이며 규칙 위반**("일어날 수 없는/막지 못하는
상황에 대한 에러 처리 금지"). 고지에 명시하는 쪽이 정직하다.

### 대안 4 — 인자 대신 묶음 dataclass (`SessionEnrichment`) 전달 (기각)

`compose_project_views` 가 7인자가 되는 것을 피하려 `model` + `workflow` 를 묶는 것을 검토했다.
기각 이유: 지금 필요 없는 추상화이고(YAGNI), `model` 호출부·기존 테스트 전부를 건드려야 하며
(Karpathy #3 수술적 변경 위반), 확립된 패턴(`tier3_last_activity_by_path`·`model_by_session_id`
가 이미 "미리 모은 딕셔너리를 인자로" 방식)을 이탈한다. **인자가 8개가 되는 시점에 다시
검토한다** — 그 임계를 여기 적어 둔다.

### 대안 5 — 훅 확장 (기각, 재확인)

`SubagentStart` 페이로드에 프롬프트를 실어 티어 2 로 나르는 것. **불가능하다** — Claude Code 가
그 이벤트에 프롬프트를 주지 않고(`agent_id`·`agent_type`·타임스탬프뿐), Workflow 로 뜬 에이전트는
전부 `agent_type="workflow-subagent"` 하나로만 잡혀 `label` 조차 그 경로에 없다.

---

## 15. 승인·검증이 필요한 미해결 항목

| # | 항목 | 설계의 잠정 결론 | 확정 방법 |
|---|---|---|---|
| ① | `wf_*.json` 이 실행 중에 쓰이는가 | **실측 완료(회고 확정)** — 최소 워크플로우(에이전트 1개, `sleep 45`)를 실행 중 3회 관측(12:44:01·12:44:25·12:44:49, 전부 `wf_*.json` 0개) + 종료 후 1회 관측(12:45:11, 1개 생성·`status:"completed"`) — §16 「Task 0 판정」참조 | 실측 완료(메인 세션, 구현 2회차 A-2). 읽기 경로는 두 경우 동일하고 **화면 문구만** 갈리는데, 결정 WF6 의 회고형 문구가 그대로 맞았다 — 코드 변경 없음 |
| ② | `record_prompt_excerpt` 를 이 경로의 오프 스위치로 재사용 | **재사용**(결정 WF8) | **사용자 승인 필요** — 플래그의 문서화된 의미를 넓히는 결정이다 |
| ③ | `MAX_VISIBLE_WORKFLOW_CHIPS` 값 | 초기값 6 (**가정**) | Task 5 레이아웃 실측 |
| ④ | 툴팁에 결과 절을 포함할지 | 포함 | Task 5 툴팁 분량 실측. 넘치면 제외 |
| ⑤ | `hub_redact.py` 추출로 선행 결정(tier0 §5)을 뒤집는 것 | **뒤집는다** — 그 결정의 전제("사용처 1곳")가 소멸하고, 대안이 순환 의존이다 | 설계 승인 |

---

## 16. 측정 결과 (구현 중 채울 것)

**[구현 3회차 로 명시 — LOW 지적]** 아래 표의 회차별 행은 활성 세션 수·`workflows/` 양성
수가 회차마다 자연 증가해 모집단이 다르다(1회차 25/3 → 2회차 25/4 → 3회차 25/4). before/after
를 나란히 두고 차이를 비교하면 "B-1(디렉터리 풀링) 비용이 0" 처럼 실제로는 근거 없는
결론을 오독하기 쉽다 — **판정은 각 회차 after 행의 절대값 단독 기준**이다(예: 13.4ms ≪
에스컬레이션 임계 50ms). 회차 간 차이는 참고용 서술일 뿐 비교 근거로 쓰지 않는다.

| 항목 | 값 | 측정 시각 |
|---|---|---|
| `collect_snapshot()` before (median of 5) | **13.5ms**(min 13.1 · max 15.4) — `git stash` 로 구현 전 커밋을 재구성해 측정 | 2026-09-02 |
| `collect_snapshot()` after — 1회차 (median of 5) | **12.5ms**(min 11.5 · max 14.7) | 2026-09-02 |
| 활성 세션 수 / `workflows/` 양성 수 — 1회차 | **25 / 3** — before·after 동일 모집단 확인(둘 다 이 값) | 2026-09-02 |
| 실제 워크플로우 실행 후 재측정 | **완료(구현 2회차 A-2)** — 메인 세션이 최소 워크플로우(에이전트 1개, `sleep 45`)를 직접 실행해 라이브 관찰과 §10 절차 3 을 함께 처리했다. 아래 「Task 0 판정」 행이 그 관측 기록이다 | 2026-09-02 |
| Task 0 판정 (라이브 / 회고) | **회고로 확정 — 실측 근거를 정적 분석에서 라이브 관찰로 교체(구현 2회차 A-2)**. 최소 워크플로우(에이전트 1개, `sleep 45`) 실행 중 3회 관측(12:44:01·12:44:25·12:44:49) 전부 `wf_*.json` **0개** — 같은 시각 `subagents/workflows/wf_<id>/agent-*.jsonl`(60KB)과 `journal.jsonl` 은 실시간으로 쓰이고 있었다. 종료 후 12:45:11 관측: 1개 생성, `status:"completed"`·`agents=1`·`states:["done"]`, mtime 12:45:01. 결론: **실행 기록은 종료 시점에 1회만, 이미 종료 상태로 쓰인다** — 허브가 진행 중 실행을 관측할 방법은 없다. 결정 WF6 의 회고형 문구와 §8 의 index 오름차순 정렬이 그대로 옳았다(코드 변경 불필요) | 2026-09-02 |
| `MAX_VISIBLE_WORKFLOW_CHIPS` 확정값 + 카드 높이 | **12**(헤드리스 Chrome 151, 카드 최소 트랙 320px 기준 실측 — 칩 13개부터 `.sessions` 가 오버플로 시작, 그보다 하나 작은 값으로 고정). 카드 높이는 CSS 고정값 340px 로 불변(에이전트 25개 세션 포함해도 넘치지 않음, 12개 캡 확인) | 2026-09-02 |
| 툴팁 최대 분량 실측 (px) | 60+3+37+1+401+9+401=**912자** 시나리오, 카드 최소 폭과 같은 뷰포트(툴팁 폭 320px)에서 **높이 462px** — `max-height` 예산 884px(뷰포트 900px 기준) 안에 여유 있게 들어가 잘림 없음(세로·가로 모두 `scrollHeight==clientHeight`). 결과 절 제거는 불필요 | 2026-09-02 |
| `collect_snapshot()` after — 2회차 (median of 5, B-1 디렉터리 풀링 반영) | **13.4ms**(min 12.7 · max 16.0) — 1회차(12.5ms) 대비 증가는 관측 cwd 후보 순회가 늘어난 것과 자연 증가한 활성 세션 수가 섞인 결과다. 여전히 에스컬레이션 임계(50ms)의 **27%** | 2026-09-02 |
| 활성 세션 수 / `workflows/` 양성 수 — 2회차 | **25 / 4** — 1회차(25/3) 대비 세션 하나가 늘었다(시간 경과에 따른 자연 증가, 인위적 조정 아님). 모집단이 완전히 동일하지 않아 1↔2회차 수치를 엄밀 비교할 근거로 쓰지 않는다 — 판정은 절대값(13.4ms ≪ 50ms)으로 한다 | 2026-09-02 |
| `collect_snapshot()` after — 3회차 (median of 5, 계약 A·B 반영) | **13.3ms**(min 12.8 · max 13.6) | 2026-09-02 |
| 활성 세션 수 / `workflows/` 양성 수 — 3회차 | **25 / 4** — 2회차와 **동일 모집단**(자연 경과에도 우연히 같은 값). 그래도 판정은 이 행의 절대값(13.3ms) 단독 기준이다(에스컬레이션 임계 50ms 의 27%) — 위 참고 문단대로 2회차 대비 차이(13.4→13.3ms)를 "계약 A·B 도입 비용이 0"의 근거로 쓰지 않는다 | 2026-09-02 |
| 병리적 입력 재현 확인 (구현 3회차 완료 기준) | `phaseTitle` 100,000자 → 401자로 절단(§7 결정 WF7 개정) · `workflowName` 100,000자 → 128자로 절단 · 에이전트 30,000개(역순 인덱스) → 100개로 절단, index 1~100 유지(결정 WF13) · `{"startTime": "9"*5000}` → 예외 없이 `None`(계약 B). 넷 다 `hub_workflow.parse_workflow_run` 직접 호출로 확인, 실물 wf_*.json 74개 전량 재파싱도 실패 0건 | 2026-09-02 |

---

## 17. 구현 2회차 — 검수 반영 기록

1회차 구현을 검수 2명(보안·프라이버시 렌즈 / 구조·회귀 렌즈)이 모두 FAIL 판정했다. 이 절은
그 지적 전량(HIGH 1·MEDIUM 9·LOW 4, 사용자 승인 설계 변경 2건 포함)의 처리 결과를 기록한다.
코드에 반영한 항목은 위 각 절(결정 WF4 개정·§5·§6·§7·§10·§15·§16)에 이미 실려 있고, 이
절은 그 근거를 모아 항목별로 추적 가능하게 한다.

### 결정 WF12. `hub_workflow_read.py` 분리(검수 A-1) + 서버측 콘텐츠 길이 상한(검수 C-1)

**모듈 분리**: `hub_collect.py` 가 정확히 800/800줄에 닿아 여유가 없었다(1회차 신규 함수의
docstring 을 압축해 겨우 맞춘 것이었다). `read_session_workflow`·`read_session_workflows`·
`_read_latest_workflow_run_text`(약 47줄)를 `hub/bin/hub_workflow_read.py` 로 옮겼다.

이름은 사용자가 제안한 `hub_collect_workflow.py` 대신 **`hub_workflow_read.py`** 를 썼다 —
이 저장소에 이미 "도메인 파서(★순수) + I/O 위성 모듈" 분리 선례가 있다(`hub_usage.py` ↔
`hub_usage_fetch.py`). 그 선례의 I/O 동사는 `fetch`(네트워크 호출 전용 — `hub_usage_fetch.py`
는 `urllib.request` 를 쓴다)이고, 이 모듈이 하는 일은 로컬 파일시스템 읽기이므로 이
저장소가 그 목적에 일관되게 쓰는 동사 `read`(`read_session_model`·`read_recent_events`·
`read_tier1_snapshot`·`read_rate_limit_capture` 등, 전부 `hub_collect.py`)를 따랐다.
`hub_model.py` 분리 선례(`hub_session`·`hub_project`·`hub_server_state`, 원본 이름을
접두어로 쓰지 않음)와도 결이 맞는다. `PROJECTS_DIR` 은 이 모듈에 다시 선언하지 않는다 —
`hub_project.py`(★순수)에 두면 `Path.home()` 계산이 그 모듈의 순수성 선언을 거짓으로
만들고, `hub_collect.py` 에 두고 새 모듈이 그것을 import 하면
`hub_collect → hub_workflow_read → hub_collect` 순환이 생긴다. 대신 `hub_collect.py` 가
자신의 `PROJECTS_DIR` 을 인자로 넘긴다 — 상수 중복도, 순환도 없다(부작용: 자매 함수
`read_session_model(s)` 는 여전히 전역 상수를 직접 참조해 두 I/O 함수군의 스타일이
비대칭이다. 완전한 대칭화는 이번 지적 범위(3개 함수 이동) 밖이라 하지 않았다).

**길이 상한**: `WORKFLOW_PREVIEW_MAX_CHARS = 401`(400자 호스트 실측 최대 + 말줄임표)을
`label`·`prompt_preview`·`result_preview` 세 값에 공통 적용한다. 반드시 스크럽 **뒤**에
자른다(`hub_hook` 의 strip→redact→clip 계약과 같은 이유 — 순서가 바뀌면 절단 경계에 걸친
시크릿이 패턴 불일치로 살아남는다). `label` 은 호스트가 자르지 않아(§2) 이론상 무제한일 수
있는데, 검수가 5,000자 값으로 절단 0을 재현했다 — 별도 상수를 새로 만들지 않고 이미 만든
401자 상한을 그대로 재사용했다(다른 두 필드와 "hub.html 에 인라인되는 발췌성 콘텐츠"라는
성격이 같다는 근거). 오늘 데이터(label 실측 max 60자, prompt/result 실측 max 401자)에는
전혀 발동하지 않아 비용은 0이다.

### 검수 지적 처리 표

| 항목 | 심각도 | 처리 | 반영 위치 |
|---|---|---|---|
| A-1 `hub_collect.py` 모듈 분리 | 사용자 승인 설계 변경 | 완료 | `hub_workflow_read.py`(신규), 결정 WF12, §5 |
| A-2 Task 0 실측(회고 확정) | 사용자 승인 설계 변경 | 완료(재측정 안 함, 기록만 반영) | §15 ①, §16 |
| B-1 워크트리 이동 시 오래된 실행이 이기는 결함 | 발견 결함(설계 변경) | 완료 | 결정 WF4 개정, `hub_workflow_read.py` |
| C-1 400자 경계 강제 부재(HIGH) | HIGH | 완료 | 결정 WF12, `hub_workflow.py` |
| C-2 `phase_title` 미스크럽 | MEDIUM | 완료 | `hub_workflow.py::_parse_agent_item` |
| C-3 `RecursionError` 미포착 | MEDIUM | 완료 | `hub_workflow.py::parse_workflow_run` |
| C-4 WF11 warnings 미구현 | MEDIUM | 완료 | `hub_workflow_read.py::_read_run_text` |
| C-5 README 축소·부정확 서술 | MEDIUM | 완료 | `hub/README.md` |
| C-6 회귀 래칫 부재 | MEDIUM | 완료 | `tests/run.sh` T25-164·T25-165 |
| C-7 `session_id` 경로 합성 미검증 | LOW | 완료 | `hub_workflow_read.py::_existing_workflow_directories` |
| C-8 심볼릭 링크 추적 | LOW | **조치 불필요**(검수 판정 그대로 수용, 기록만) | 이 절 |
| D-1 디렉터리 EACCES 테스트 부재 | MEDIUM | 완료 | `test_hub_workflow_read.py`(부모 디렉터리 chmod로 재현, 실측 근거는 테스트 docstring) |
| D-2 테스트 시나리오가 PRP 표 문구와 불일치 | LOW | 완료(B-1 신규 의미로 재작성 + 문구 그대로의 케이스 추가) | `test_hub_workflow_read.py` |
| D-3 `\|\| !agent.result_preview` 근거 주석 부재 | LOW | 완료 | `hub_template.html::workflowChipTooltipText` |

D-1 관련 실측 메모: 검수는 "`workflows_dir` 자체를 `chmod(0o000)`" 을 제안했으나, 직접
실측한 결과 pathlib 의 `stat()` 은 대상 자체가 아니라 **경로상 부모의 실행 권한**만
요구하므로 대상 자체를 잠가도 `is_dir()` 은 여전히 `True` 를 반환한다(EACCES 가 재현되지
않는다). EACCES 를 실제로 재현하려면 `workflows_dir` 의 **부모**(`session_id` 디렉터리)를
잠가야 한다 — 검수의 의도(EACCES 분기 커버)를 그대로 살리되 실측에 맞게 대상을 바꿨다.

---

## 18. 구현 3회차 — 검수 반영 기록

2회차 구현을 검수 2명(구조·회귀 렌즈 / 보안·프라이버시 렌즈)이 재검수했다. **구조 렌즈는
PASS**(1회차 지적 A-1·D-1·D-2·D-3 + B-1 전부 이행 확인, 되돌아온 항목 0건). **보안 렌즈는
지적 5건 중 3건이 되돌아왔다** — 그리고 되돌아온 방식이 이 절의 핵심이다: 제시된 재현
케이스(400KB 중첩, 특정 시크릿 패턴 등)는 정확히 막혔는데, **같은 결함의 형제 사례**(형제
필드 `phase_title` 의 미절단, 형제 예외 `ValueError`, 반대 방향 서술 오류)가 매번 새로
생겼다. 근본 원인은 구현 실수가 아니라 **결정 WF7 이 계약이 아니라 필드 이름을 열거한
것**이었다 — 명세가 목록이라 구현이 목록만 따라갔다. 이 절이 기록하는 것은 그래서 "필드
3개를 고쳤다"가 아니라 **결정 WF7 을 계약 서술로 개정하고(§4), 그 계약을 기계가 강제하도록
래칫 테스트를 건 것**이다.

### 결정 WF13. 에이전트 개수 상한 초과는 경고 없이 버린다

`WORKFLOW_RUN_MAX_AGENTS`(100) 초과분은 `warnings` 에 사유를 남기지 않는다. 근거: (1)
`parse_workflow_run` 은 순수 함수로 반환 시그니처가 `WorkflowRunView | None` 고정이다 —
경고를 얹으려면 반환 형태 자체를 바꿔야 하는데, 이는 §7 이 이미 확정한 공개 인터페이스의
변경이라 이번 회차의 계약 A·B 범위(길이·예외 방어)를 넘는다. (2) 이미 채택된 설계 선례가
있다 — 클라이언트 표시 상한(`MAX_VISIBLE_WORKFLOW_CHIPS`)도 상한 밖 에이전트를 "+N" 표시
없이 조용히 버린다(결정 K3). 서버측 개수 상한은 그 정책을 "화면에 보여줄 개수"에서
"뷰 자체를 부풀릴 수 있는 크기"로 확장한 것일 뿐 새 종류의 손실이 아니다. (3) C-4(파일
읽기 실패에 경고가 없던 결함)와는 성격이 다르다 — C-4 는 세션 전체가 설명 없이 화면에서
사라지는 **전면적** 정보 손실이었지만, 에이전트 개수 초과는 **부분적** 손실(앞쪽 100개는
정상 표시)이라 이미 채택된 K3 의 논리가 그대로 적용된다. 실측상 정상 데이터의 실행당
에이전트 수는 평균 6·max 25(§3 계측 8)로 상한(100)에 크게 못 미쳐, 이 상한은 병리적
입력에서만 발동한다.

### 검수 지적 처리 표

| 항목 | 심각도 | 처리 | 반영 위치 |
|---|---|---|---|
| phase_title 401자 상한 누락(2회차 C-1 회귀) | HIGH | 완료 — 결정 WF7 개정으로 `_scrubbed_and_clipped` 경로에 phase_title 합류 | `hub_workflow.py::_parse_agent_item` |
| `RecursionError` 만 추가되고 형제 예외 `ValueError`(4,300자리 초과 정수) 는 여전히 셈(2회차 C-3 회귀) | HIGH | 완료 — `except (json.JSONDecodeError, RecursionError)` → `except (ValueError, RecursionError)` | `hub_workflow.py::parse_workflow_run` |
| README 고지가 실물보다 안전하게 서술(2회차 C-5 의 반대 방향 회귀 — "네 값 모두 401자"라 적었으나 실물은 세 값뿐이었다) | MEDIUM | 완료 — phase_title 합류로 서술이 실제로 참이 됨 + 신규 128자·100개 상한 서술 추가 | `hub/README.md` |
| run_id 스크럽 면제 근거("파일명에서 오는 식별자")가 사실과 다름(코드는 `payload.get("runId")` 를 읽는다) | MEDIUM | 완료 — docstring 정정, 128자 상한을 대체 방어선으로 명시 | `hub_workflow.py` 모듈 docstring, PRP 결정 WF7 |
| 미스크럽 필드를 "3개"로 열거(실제로는 `state` 포함 4개) | LOW | 완료 — 필드 열거 자체를 폐기하고 계약 서술로 개정 | 결정 WF7 |
| run_id·workflow_name·status·state·에이전트 개수에 상한 부재 | HIGH(설계 결함 — 계약 A 미비) | 완료 | `hub_workflow.py`(`WORKFLOW_METADATA_MAX_CHARS`·`WORKFLOW_RUN_MAX_AGENTS`) |
| T25-164 세 번째 부정 검사가 사실상 무발화 | LOW | 완료 — 실제 사각(agent 필드가 두 헬퍼 함수 바깥에서 참조되는지)을 겨냥하도록 재작성 | `tests/run.sh` T25-164 |
| §16 측정 결과 표의 before/after 모집단 차이로 인한 오독 가능성 | LOW | 완료 — "판정은 after 절대값 단독 기준" 명시 | §16 |

### 래칫이 실제로 막는 것

- `StringFieldLengthRatchetTest`(`test_hub_workflow.py`) — `dataclasses.fields()` 로
  `WorkflowAgentView`·`WorkflowRunView` 를 순회해 병리적 페이로드(전 필드 100,000자)에서도
  모든 문자열 필드가 상한 이하임을 단언한다. **[루프 밖 보완 — 과잉 보장 서술 정정]**
  "필드 이름을 하드코딩하지 않으므로... 상한을 걸지 않는 한 이 테스트가 자동으로 실패한다
  — 재발할 수 없는 구조다"라는 바로 위 서술은 **사실이 아니었다.** 어서션 자체는
  `dataclasses.fields()` 를 순회하지만, 병리적 값을 채우는 픽스처(`_agent_item`·
  `_run_json`)가 소스 JSON 키를 하드코딩한다 — 새 필드의 소스 키가 그 픽스처 오버라이드
  목록에 없으면 파서가 빈 문자열을 만들어 이 테스트가 **조용히 통과**해 버린다(열거의
  구멍이 어서션에서 픽스처로 옮겨졌을 뿐이다 — 검수가 사본에 상한 없는 `notes: str` 필드를
  추가해 실증했다). 이 구멍은 이 테스트가 아니라 `tests/run.sh` 의 정적 가드(T25-166, §19)
  가 막는다 — 픽스처에 의존하지 않고 `hub_workflow.py` 의 생성자 호출부 자체를 검사해
  모든 키워드 인자가 승인된 상한 헬퍼를 거치는지 확인한다. 이 테스트는 "**기존** 필드가
  실제로 상한 안에 있는가"의 회귀 가드로는 여전히 유효하다(phase_title 을 2회차 상태로
  되돌리면 정확히 실패한다) — "새 필드 누락을 자동으로 잡는다"는 보장은 T25-166 쪽의 몫이다.
- `ParserNeverRaisesOnPathologicalInputTest`(`test_hub_workflow.py`) — 깨진 JSON·빈
  문자열·최상위 스칼라·4,300자리 초과 정수·거대 문자열·널바이트·깊은 중첩을 표로 묶어
  전부 예외 없이 `None` 을 반환하는지 확인한다. 새로운 병리적 입력 유형이 발견되면 이
  표에 행 하나만 추가하면 되고, 예외 유형을 하나씩 `except` 절에 추가하는 대신 애초에
  `ValueError`(상위 클래스)로 넓혀 형제 예외까지 한 번에 방어한다.

---

## 19. 루프 밖 보완 — 3회차 상한 도달 후 정리 회차

구현↔검수 왕복이 3회차 상한에 도달했다(2회차·3회차 모두 재검수 지적 발생, §17·§18). 프로젝트
CLAUDE.md 의 정체 규칙("재검수 FAIL 의 지적 항목이 직전 회차와 동일")에는 해당하지 않았지만
(회차마다 지적의 형태가 달랐다), 3회 상한 자체가 걸려 루프는 공식 종료됐다. **사용자가 남은
지적을 한 번에 정리한 뒤 커밋하는 경로를 승인**했고, 검수자 판정은 "폐기 대상 없음 — 남은
것은 후속 커밋 1건 범위의 국소 수정"이었다. 이 절은 그 처리 결과를 기록한다. 아키텍처·모듈
분리·데이터 모델·결정 WF1~WF13 은 이 회차에서 손대지 않았다(필드 축소는 데이터 모델의
**축소**이지 재설계가 아니다).

### 처리 표

| 항목 | 심각도 | 처리 | 반영 위치 |
|---|---|---|---|
| 고립 서로게이트가 `hub.html` 쓰기를 죽인다 | HIGH | 완료 — `hub_collect._atomic_write_text` 에 `_encode_safe_utf8`(서로게이트 → U+FFFD 정규식 치환, 후속 수정 전에는 `?` 로 치환하는 UTF-8 왕복 방식이었다) 추가 | `hub_collect.py`, `test_hub_collect.py::WriteHubHtmlSurrogateHandlingTest` |
| 계약 A 래칫이 새 문자열 필드를 못 잡는다(픽스처 하드코딩) | HIGH | 완료 — 정적 가드 `T25-166` 신설(생성자 호출부의 모든 키워드 인자가 승인된 상한 헬퍼를 거치는지 검사) + 거짓 보장 서술 3곳(테스트 docstring·결정 WF7·§18) 정정 | `tests/run.sh`, `test_hub_workflow.py`, 결정 WF7, §18 |
| 정수 필드(`index`)가 무제한 | MEDIUM | 완료 — `_bounded_index` 신설([0, `WORKFLOW_RUN_MAX_AGENTS`] 클램핑). `started_at_ms` 는 미사용 필드 제거로 함께 해소 | `hub_workflow.py` |
| "발동 0회 · 넉넉한 여유" 서술이 실측과 다르다 | MEDIUM | 완료 — 동작은 불변, 서술만 정정(497/503 이 이미 401자, 스크럽이 값을 늘릴 수 있음) | `hub_workflow.py` 주석 3곳, `hub/README.md`, §9 |
| `commands/hub.md` 설치 고지가 실물보다 좁다 | MEDIUM | 완료 — label·phase_title·저장 형태(평문 파일·127.0.0.1 서버) 추가 | `commands/hub.md`, §9 |
| 미사용 인라인 필드 4개(`run_id`·`workflow_name`·`status`·`started_at_ms`) | LOW | 완료 — `WorkflowRunView` 에서 제거(YAGNI, 데이터 최소화) | `hub_workflow.py`, §6·§7·§9, 테스트 6개 파일 |

### HIGH-A 위치 판단 — `hub_model.render_hub_html` 이 아니라 `hub_collect._atomic_write_text`

`render_hub_html`(★순수)은 `json.dumps(..., ensure_ascii=False)` 로 서로게이트를 포함한
문자열을 그대로 payload 에 새긴다 — 이 단계 자체는 예외를 던지지 않는다(직접 재현: 서로게이트를
담은 `WorkflowRunView` 로 `render_hub_html` 을 호출해도 정상 반환됨을 확인). 실패는
`_atomic_write_text` 의 `os.fdopen(..., encoding="utf-8")` + `write()` 에서 난다. 이 함수에서
고친 이유:

1. **쓰기 경계가 곧 유일한 인코딩 지점이다.** `render_hub_html` 은 파일에 닿지 않는 순수 함수라
   "안전하게 인코딩 가능한 문자열을 만든다"는 책임이 그 모듈의 정체성(★순수)과 어긋난다.
2. **넓게 덮는다.** `_atomic_write_text` 는 `hub.html` 뿐 아니라 `rate_limits.json`·
   `server.json`·`last_collect_error.json`·`last_usage_api_error.json` 도 쓴다 — 이 함수
   하나를 고치면 다섯 채널이 한 번에 방어되고, 앞으로 호스트 소유 문자열을 담는 새 파일이
   추가돼도 자동으로 적용된다. 이 결함은 워크플로우 기능이 만든 것이 아니다 — 이 쓰기 경계는
   처음부터 호스트·사용자 소유 문자열을 그대로 인코딩해 왔고(훅의 프롬프트 발췌 채널도 같은
   노출면), 워크플로우 인라인이 그 표면을 넓혔을 뿐이다.

**관측성(warnings) 미도입 결정**: 치환이 일어났다는 사실을 `warnings` 파이프라인에 실어 사용자에게
알리는 것은 하지 않았다 — `_atomic_write_text` 는 반환 시그니처가 `-> None` 고정이고 호출부가
5곳이라, 시그니처를 바꾸면 이번 회차의 최소 범위(surgical fix) 원칙을 넘는다. 서로게이트 치환은
화면에 시각적 신호를 이미 남기고, 세션을 죽이지 않는 방어가 목적의 전부이므로 별도 경고 채널이
없어도 기능적으로 완결된다. 이후 실제 필요가 확인되면 그때 확장한다(YAGNI).

**정규화 방식**(후속 수정 반영): 처음에는 `text.encode("utf-8", "replace").decode("utf-8")` 로
구현해 인코딩 불가능한 서로게이트를 `?`(ASCII, UTF-8 'replace' 에러 핸들러의 인코딩측 동작)로
치환했다. 그러나 `?` 는 사용자가 실제로 입력한 물음표와 화면에서 구별되지 않아, 위 문단이 근거로
삼는 "시각적 신호"가 오히려 사용자 입력과 섞이는 문제가 있었다 — 후속 수정에서 치환 문자를
U+FFFD(REPLACEMENT CHARACTER, `�`)로 바꾸고, 구현도 모듈 레벨 컴파일 정규식
(`_LONE_SURROGATE_PATTERN = re.compile(r"[\ud800-\udfff]")`)으로 교체해 바이트 왕복을 없앴다.
이 치환이 기존 왕복 인코딩과 동등하다는 근거(실측): Python str 에서 UTF-8 인코딩이 실패하는
코드포인트는 서로게이트 범위(U+D800~U+DFFF, 2048개) 뿐이며, 0~0x10FFFF 전체 코드포인트를
encode("utf-8") 해 실패 집합이 정확히 이 범위와 일치함을 확인했다(논캐릭터 U+FFFE·U+FFFF 등은
실패하지 않는다). 나머지 문자는 무변화(왕복 검증:
`test_written_file_is_valid_utf8_and_carries_the_rest_of_the_string`, 치환 문자가 U+FFFD 이고
ASCII `?` 가 아님을 함께 고정한다).

### 커밋 분리

이 절이 기록하는 항목들은 **메인 세션이 검증 후 직접 커밋**한다(이 보완 회차 자신은 커밋하지
않는다). 서로게이트 정규화(HIGH-A)는 다른 항목과 파일 범위가 겹치지 않아(`hub_collect.py`·
`tests/hub/test_hub_collect.py`·`tests/hub/test_hub_workflow.py` 의 `UnpairedSurrogateHandlingTest`
전용) 별도 커밋으로 분리 가능하다. 나머지 항목(계약 A 정적 래칫·정수 상한·발동 서술 정정·
설치 고지 보완·미사용 필드 제거)은 `hub_workflow.py` 데이터 모델 축소를 축으로 여러 테스트
파일에 걸쳐 있어 분리하지 않고 한 커밋으로 묶는 편이 자연스럽다 — 최종 커밋 구성은 메인
세션의 판단에 맡긴다.
