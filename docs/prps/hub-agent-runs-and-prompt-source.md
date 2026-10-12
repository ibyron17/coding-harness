# PRP — 세션 카드의 서브에이전트 **개별 실행** 표시 + 프롬프트 발췌 **출처 이전** (hub-agent-runs-and-prompt-source)

두 요구를 한 문서로 묶는다. 겉보기에는 무관하지만 **같은 파일 하나(세션 transcript 꼬리)와
같은 오프 스위치 하나(`record_prompt_excerpt`)를 건드린다** — 따로 설계하면 두 번째가
첫 번째의 프라이버시 고지·계약을 다시 열어야 한다.

- 요구 1 — 세션 줄의 서브에이전트 표시를 **타입 합계**에서 **개별 실행**으로 바꾼다.
- 요구 2 — 프롬프트 발췌의 출처를 **훅이 만든 평문 사본**에서 **호스트가 이미 남긴 transcript**
  로 옮기고, 그 사본을 만드는 코드를 지운다.

결정 번호는 요구 1이 `AR*`(Agent Runs), 요구 2가 `PS*`(Prompt Source)다.

---

## 0. 요구사항 요약

**요구 1.** `hub_session.summarize_agent_runs`(hub/bin/hub_session.py:450)는 한 세션의 서브
에이전트 실행을 **`agent_type` 단위로 합쳐** 칩 1개로 그린다. 검수를 3회 돌려도 화면에는
`code-reviewer` 칩 하나다. 무엇을 시켰는지(제목)·몇 번 돌았는지·얼마나 걸렸는지·어느 모델로
돌았는지가 전부 화면에 없다. 호스트가 이미 `subagents/agent-<id>.meta.json` 에 그 값을 남기고
있고, 그 파일명의 `agentId` 는 허브 훅 이벤트의 `ai` 필드와 **같은 키**다. 그 조인으로
**실행 1건 = 화면 1줄**을 만든다.

**요구 2.** `hub_hook.py` 가 `UserPromptSubmit` 훅에서 프롬프트 앞 500자를
`~/.claude/hub/events/*.jsonl` 에 평문으로 복사한다. 그 사본 하나를 위해 자동주입 블록 벗기기
정규식·스크럽 순서 계약·상한 버퍼 계산·README 프라이버시 고지 한 항목·설치 동의 문구가 딸려
있다. 그런데 **허브가 모델을 알아내려고 이미 읽는 바로 그 꼬리 128KiB 안에** 호스트가 같은
것(`{"type":"last-prompt","lastPrompt":…}`)을 남긴다. 사본은 이미 읽고 있는 데이터의
재구현이다 — 지운다.

### User Story

> 여러 프로젝트를 한 화면에서 보는 사람으로서,
> 어느 세션이 **무엇을 몇 번 위임했고 지금 어느 실행이 돌고 있는지**를 카드에서 바로 알고 싶다.
> 그래야 "검수가 3회차인데 아직 안 끝났다"를 창을 열지 않고 안다.
>
> 그리고 그 화면을 얻으려고 **내 프롬프트가 평문으로 복사되지는 않았으면** 한다 —
> 이미 호스트가 남긴 것을 읽으면 되는 일이다.

### Problem → Solution

| | 지금 | 뒤 |
|---|---|---|
| 서브에이전트 표시 | 타입 1종 = 칩 1개, 최대 2개. 제목·경과·모델·횟수 없음 | 실행 1건 = 줄 1개, 최대 5줄 + 초과 개수. 단계 칩·제목·경과가 화면에, 타입·모델·시작 시각은 툴팁에 |
| 발췌 출처 | 훅이 프롬프트 앞 500자를 `events/*.jsonl` 에 평문 복사(7일 보관) | 호스트 transcript 의 `last-prompt`(호스트가 이미 최대 201자로 자름). **추가 I/O 0** — 이미 읽는 꼬리다 |
| 평문 보관 | 프롬프트 500자 × 7일 | **없음**(허브가 새로 만드는 프롬프트 사본이 0개가 된다) |

### 하지 않는 것 (범위 밖 — 명시)

1. **프롬프트 전문·도구 호출 목록을 싣지 않는다**(사용자 결정). Cursor UI 에는 있지만 허브에는
   넣지 않는다.
2. **부모-자식(중첩) 트리를 만들지 않는다** — 결정 AR13. 근거는 §3.13.
3. **토큰 사용량을 싣지 않는다** — 결정 AR14. 근거는 §3.14. (사용자 판단 요청 항목, §13-①)
4. **상세 패널을 건드리지 않는다.** 패널은 여전히 대시보드 파일만 보여준다.
5. `SessionEnd`→`done`, `Stop`→`turn_state`, 서버 꺼졌을 때의 재수집 트리거 세 가지는
   **훅에 그대로 남는다**(transcript 에 대체물이 없다 — 실측). 요구 2의 범위는
   `UserPromptSubmit` 의 `p` 필드 **하나**다.
6. **옛 이벤트 파일을 다시 쓰지 않는다** — 결정 PS5.

---

## 1. 호스트 데이터 계약 (실측 — 2026-09-16, 이 머신)

우리가 소유하지 않는 두 외부 형식을 읽는다. 아래는 그 계약을 **문서가 아니라 실물 전수**로
확정한 것이다. 계약이 깨지면 이 절부터 다시 잰다.

### 1.1 `subagents/agent-<agentId>.meta.json`

```
~/.claude/projects/<인코딩된 프로젝트>/<세션ID>/subagents/
    agent-<agentId>.meta.json     # 에이전트 시작 시점에 1회 쓰이고 이후 갱신되지 않는다
    agent-<agentId>.jsonl         # 그 에이전트의 대화. 진행 중 계속 append
```

실물:

```json
{"agentType":"Explore","description":"대시보드 발행·종료 상태 판정 경로",
 "toolUseId":"toolu_01Tuf535i8L3HQXUG3SrWs7M","spawnDepth":1,"model":"haiku"}
```

**전수 818건 (전 프로젝트)**

| 키 | 존재 | 비고 |
|---|---|---|
| `agentType` | 818/818 (100%) | code-reviewer 362 · implementer 298 · design-architect 103 · Explore 22 · general-purpose 21 · claude-code-guide 8 · architect 2 · silent-failure-hunter 1 · security-reviewer 1 |
| `description` | 818/818 (100%) | **길이 min 6 · 중앙 19 · p90 32 · max 51.** 예: `레포 subtree 스코핑 기능 설계` |
| `toolUseId` | 818/818 | 부모 transcript 의 `Agent` tool_use 와 잇는 키. 이 설계는 쓰지 않는다(§3.6) |
| `spawnDepth` | 818/818 | **{1: 788, 2: 30}. 3단은 0건** |
| `model` | **665/818 (81.3%)** | `sonnet` 439 · `opus` 197 · `haiku` 16 · `fable` 13. **없는 것이 153건(18.7%)** |
| `parentAgentId` | 30/818 (3.7%) | `spawnDepth == 2` 인 것과 정확히 같은 집합. 부모는 30/30 이 같은 디렉터리에 존재 |
| `requestShape`·`requestNonInteractive` | 5/818 | 이 설계는 읽지 않는다 |

**중요 — `model` 은 모델 ID 가 아니라 디스패치 별칭이다.** `claude-` 접두가 없으므로
`hub_transcript.normalize_model_name` 에 넣으면 전건 `None` 이 된다. 세션 모델 칸(`Opus 5 · xhigh`,
transcript 유래)과 **다른 값 계열**이라 같은 정규화 경로를 재사용하면 안 된다(§3.9).

**`model` 결손은 낡은 파일 문제가 아니다** — 결손 153건 중 가장 최근 것이 2026-09-14(이틀 전)이고,
결손 타입도 code-reviewer 70 · implementer 42 · general-purpose 16 · design-architect 13 ·
claude-code-guide 8 · Explore 4 로 고르다. **부재를 정상 상태로 설계한다.**

**세션당 개수(전 기간)**: 서브에이전트를 쓴 세션 44개, 중앙 8 · **최대 222**.

### 1.2 훅 `ai` ↔ meta.json 조인 (이 설계의 토대)

허브가 아는 실행은 훅 이벤트가 준 것뿐이다. 그 `ai`(agent_id)로 파일 경로를 **직접 조립**한다
— 디렉터리 열거(glob)를 하지 않는다.

최근 3일 훅 이벤트의 `ai` 30개를 전수 대조한 결과:

| 부류 | 건수 | meta.json 해결 |
|---|---|---|
| `at`(agent_type)가 있는 실행 | 18 | **18/18 = 100%** |
| `at` 가 빈 문자열이고 `SubagentStop` 단독 | 12 | 0/12 |

**후자는 이미 허브가 버리는 이벤트다** — `hub_session.is_untracked_internal_subagent_stop`
(hub_session.py:146)이 "`agent_type` 이 비었고 대응하는 `SubagentStart` 를 본 적 없는
`SubagentStop`"을 필터로 걷어낸다. 즉 **`SessionFacts.subagents` 에 실제로 들어가는 실행의
meta.json 해결률은 실측 100%다.**

**`SubagentStart` 훅은 일부 진입점에서 발화하지 않는다**(주 세션 실측: 9/09 이후 누계
`SubagentStart` 194 vs `SubagentStop` 369). 시작 훅이 없으면 `_handle_subagent_stop`
(hub_session.py:218)이 `started_at_ms = ended_at_ms` 인 합성 실행을 만든다 — **경과가 0이 된다.**
이 결함을 meta.json 이 고친다(§1.3).

**중첩(spawnDepth 2) 30건은 훅 이벤트에 0건 나타난다.** 서브에이전트가 띄운 서브에이전트는
세션 훅을 발화시키지 않는다 → 이 조인으로는 **원리적으로 발견할 수 없다**(결정 AR13 의 근거).

### 1.3 시각 — 무엇을 믿을 수 있고 무엇을 못 믿는가

| 값 | 실측 | 판정 |
|---|---|---|
| `meta.json` 의 **mtime** | agent jsonl 첫 줄 `timestamp` 와 **일치**(예: mtime 2026-09-10 15:34:17 KST = 첫 줄 `06:34:17.378Z`) | **시작 시각으로 신뢰한다.** 시작 시점에 1회 쓰이고 갱신되지 않는다 |
| agent `jsonl` 의 **mtime** | 마지막 줄 `timestamp` 와 **222건 중 70건(31.5%)이 5초 초과로 어긋난다. 최대 10.95일** — 같은 분에 16개 파일이 동시에 찍힌 뭉치가 여러 개 관측됐다(재개·일괄 재기록 흔적) | **종료 시각으로 쓸 수 없다.** 기각 |
| 훅 `SubagentStop` 의 `t` | 허브 자신이 받은 시각 | **종료 시각의 유일한 출처**(오늘과 동일) |

→ **시작은 meta.json mtime(없으면 훅), 종료는 훅.** agent jsonl 은 읽지 않는다.

> → **개정(2026-09-30 실측)** — 위 표 첫 행의 「시작 시점에 1회 쓰이고 갱신되지 않는다」는 2.1.284 호스트에서 **거짓**이다: 호스트는 서브에이전트를
> 재개(`SendMessage`)할 때마다 meta.json 을 다시 쓴다(재개된 에이전트 6/6). mtime = 마지막 재개 시각이고 `description` 은 첫 띄움 값
> 그대로다. 경과 표시(마지막 재개부터)는 그 덕에 맞았고, 틀린 것은 제목 하나였다 — 재개 횟수는 훅의 `SubagentStart` 재발화 수로 세고
> (결정 TF7), 새 작업 이름은 부모 transcript 의 재개 요청에서 읽는다(결정 TF8, hub-agent-title-and-excerpt-freshness.md).

### 1.4 transcript 의 `last-prompt`

```json
{"type":"last-prompt","lastPrompt":"1. 대시보드 허브의 div.card 의 …",
 "leafUuid":"90c389e5-…","sessionId":"768e8a38-…"}
```

| 항목 | 값 |
|---|---|
| 보유 | **30/30 세션(100%)** — 최근 30개 세션 전수(주 세션 조사). 표본 3건 재확인(꼬리 안 존재·키 구조 일치) |
| 길이 | 중앙 **23자** · **최대 201자**(호스트가 이미 자른다) |
| 자동주입 태그(`<ide_selection>` 등)로 시작 | **0건** — 호스트가 이미 벗겨서 기록한다 |
| 위치 | **30/30 이 허브가 이미 읽는 꼬리 128KiB 안**(`hub_collect._read_transcript_tail`, hub_collect.py:193) |
| 부가 키 | `leafUuid`·`sessionId` — `sessionId` 로 "이 줄이 이 세션 것인가"를 확인할 수 있다 |

> → **보강(2026-09-30)** — 위치(꼬리 128KiB 안 30/30)는 맞지만 **시점이 늦다**: 호스트는 `last-prompt` 를 대화 기록이
> 32KiB 쌓일 때마다만 다시 적는다(새 값이 실리기까지 지연 중앙 22.8s·p90 65s). 발췌는 꼬리의 사람 프롬프트 줄을 우선한다
> (hub-agent-title-and-excerpt-freshness.md 결정 TF1).

**추가 I/O 가 0이다.** 세션 모델을 알아내려고 이미 읽는 바로 그 문자열을 한 번 더 훑을 뿐이다.

유일한 기능 손실: 툴팁이 보여주는 최대 길이가 **500자 → 201자**. 카드 표시 상한은
`EXCERPT_DISPLAY_MAX_CHARS = 120`(hub_template.html:1034) 그대로라 **중앙값 23자인 대부분의
카드는 한 글자도 달라지지 않는다.**

---

## 2. 계측 (성능 판단의 근거 — 2026-09-16, 이 머신, 최악 케이스 = 222 에이전트 디렉터리)

기준선: `read_session_models` 의 에스컬레이션 조건은 "`collect_snapshot` 이 50ms 를 넘기기
시작하면 캐시를 재검토한다"(hub_collect.py:234 docstring, 결정 MD4)다.

| 작업 | 222건 기준 | 1건당 | 판정 |
|---|---|---|---|
| meta.json `stat` + agent jsonl `stat` | 6.5 ms | 0.029 ms | 채택 |
| meta.json 읽기 + `json.loads` | 36.8 ms | 0.166 ms | 채택 |
| agent jsonl **전체** 읽기 | **1,013 ms / 148.5 MB** | 4.6 ms | **기각** |
| agent jsonl **꼬리 128KiB** | 120 ms | 0.54 ms | 토큰을 넣을 때만 필요 → §3.14 로 기각 |
| agent jsonl 꼬리 32KiB / 8KiB | 43 ms / 14 ms | — | (참고) |

**그러나 실제 부하는 222가 아니다.** 허브의 이벤트 창은 오늘+어제뿐이고, 그 창에서 실제로
읽을 실행 수는:

| 창 | 값 |
|---|---|
| 전 세션 합계 distinct `ai`(하루) | 7 ~ 16건 |
| **세션당** 최대 실행 수(임의의 2일 창) | n=10 세션, 중앙 **5** · p90 **45** · **최대 45** |

→ **정상 부하에서 meta.json 읽기 총비용은 실행 수 × 0.166ms ≈ 1~8ms.** 최악(45건 세션이
여럿) 가정에서도 한 자릿수 ms 다. 캐시를 만들지 않는다(결정 MD4·WF10 과 같은 판단).

`last-prompt` 는 이미 읽은 문자열의 재스캔이므로 증분 I/O 0, 증분 CPU 는 128KiB 문자열
역방향 순회 1회(모델 스캔과 합쳐 1회로 끝낸다, 결정 PS2).

---

## 3. 설계 결정과 근거

### AR1. 새 티어가 아니라 **티어 2 세션 뷰의 보강**이다 — `SessionFacts` 는 건드리지 않는다

`SessionFacts` 는 "훅 이벤트 → 세션 사실"이라는 **단일 입력원 계약**이다(hub_session.py 머리
주석). meta.json 은 호스트 소유의 다른 입력원이므로 그 계약에 섞지 않는다. 뷰(`SubagentRunView`)
를 만드는 지점에서만 합류시킨다 — `model`(결정 MD7)·`workflow`(결정 WF1)가 이미 세운 관례다.

**구조적 귀결이 하나 있다(중요):** 호스트 파일이 사라지거나 형식이 깨져도
`_compute_base_state`(작업중/대기/완료)와 좀비 가드는 **입력이 바뀌지 않아** 판정이 달라지지
않는다. 카드 상태는 100% 훅 유래로 남는다.

### AR2. 새 모듈 2개 — `hub_subagent.py`(★순수) + `hub_subagent_read.py`(I/O)

`hub_transcript.py`(transcript 꼬리)·`hub_workflow.py`(wf_*.json)가 세운 선례를 그대로 잇는다:
**외부 계약은 모듈 하나에 가둔다. 계약이 깨지면 그 파일만 고친다.** 파일 접근은 순수 파서에
넣지 않는다.

I/O 를 `hub_collect.py` 에 두지 않는 이유는 선례와 같다 — hub_collect.py 는 **728/800줄**이라
여유가 72줄인데, 이 기능의 I/O(경로 조립·stat·읽기·세션 순회)만 약 57줄이고 요구 2가
`read_session_tails` 로 여기에 또 얹는다. `hub_workflow_read.py` 는 정확히 이 압력에서 갈라져
나왔다(구현 2회차 검수 A-1). 800줄 상한은 `tests/run.sh` T25-100 이 강제한다.

`hub_workflow.py` / `hub_workflow_read.py` 쌍과 **파일명·역할·임포트 방향이 동형**이다:
`PROJECTS_DIR` 은 다시 선언하지 않고 호출자(hub_collect.py)가 인자로 넘긴다(순환 회피).

> 배포 파일 수: **21 → 23.** `hub/install.sh` 의 `HUB_FILE_COUNT` 와 `hub/README.md`
> 「파일 배치」의 "21개 파일" 서술을 함께 고친다(T25-149 가 둘의 일치를 강제한다).

### AR3. 파일 경로는 **조립**한다 — 디렉터리 열거(glob)를 하지 않는다

```
PROJECTS_DIR / encode_project_dir_name(cwd) / session_id / "subagents" / f"agent-{agent_id}.meta.json"
```

세 조각이 전부 이미 손에 있다(`observed_cwds`·`session_id`·훅의 `ai`). glob 을 쓰면 222개
디렉터리 항목을 훑고(17ms) 그중 태반이 창 밖 실행이다. 조립하면 **읽는 파일 수가 화면에 실을
실행 수와 정확히 같다.**

`observed_cwds` 전부를 후보로 삼는 것은 `read_session_model`(결정 MD2·E13)과 같은 이유다 —
워크트리로 이동한 세션의 디렉터리는 최초 cwd 기준으로 남는다. 먼저 존재하는 것을 쓴다(결정적).

**경로 조각 방어**: `session_id`·`agent_id` 가 경로 조립에 직접 쓰이므로 `hub_workflow_read.
_existing_workflow_directories`(구현 2회차 검수 C-7)와 **같은 가드**를 건다 — `/` 포함,
빈 문자열, `.`, `..` 는 조립 전에 걷어낸다(`Path` 의 `/` 는 절대경로 피연산자를 만나면 앞을
버린다).

### AR4. `SubagentRunView` 의 의미를 **타입 1종 → 실행 1건**으로 바꾼다 (필드 추가, 이름 유지)

같은 타입을 합치던 `latest_started_at_ms`/`is_running_by_type` 딕셔너리를 버리고
`facts.subagents` 를 1:1로 투영한다. **함수명 `summarize_agent_runs` 는 유지한다** —
`tests/run.sh` 의 T25-52(정렬 키 K2)·T25-92(술어 공유 GOTCHA 4)·T25-93(기본 인자 2개)·
T25-101(재배치 심볼)·5462행(토큰 목록) 다섯 군데가 이 이름에 앵커링돼 있고, 이름이 여전히
"이 세션의 서브에이전트 실행을 화면용으로 요약한다"를 정확히 말한다. 이름 바꾸기는 계약
6곳을 건드리고 얻는 것이 없다.

### AR5. 정렬은 **K2 그대로** — 실행 중 우선, 그 다음 최근 시작 순, 동률은 `agent_id`

```python
key = (0 if run.is_running else 1, -run.started_at_ms, run.agent_id)
```

K2 의 목적(클라이언트 상한 안에서도 지금 진행 중인 것을 놓치지 않는다)이 실행 단위에서
그대로 성립한다. 세 번째 키는 **`snapshot_content_key` 안정성**(결정 D2)을 위한 결정적
타이브레이커다 — 같은 ms 에 시작한 형제 실행이 실제로 있다(팬아웃).

### AR6. 경과 시간은 **서버가 계산하지 않는다** — 시작·종료 시각만 싣는다

`SessionView` docstring 이 명시한 결정 D2: "파생값(경과 시간 등)을 여기 넣지 않는다 —
`snapshot_content_key` 가 `collected_at_ms` 만 제외하므로 '지금' 파생값은 매 수집마다 키를
바꿔 `hub.html` 쓰기 억제를 무력화한다."

→ 뷰에는 `started_at_ms`(정적)·`ended_at_ms`(정적, 미종료면 `None`)만 싣고, **클라이언트가
`elapsedLabel`(이미 있는 함수)로 그린다.** 끝난 실행은 `ended − started`, 도는 실행은
`Date.now() − started` 다.

`is_running` 은 예외로 서버가 계속 판정한다 — 오늘과 같다. 좀비 가드 술어
(`is_running_subagent`)를 서버와 클라이언트가 나눠 가지면 카드 상태와 줄이 어긋나기 때문이다
(결정 ZG4). `is_running` 은 90분 경계에서 한 번 뒤집히는 값이라 D2 에 대한 노출이 경과
시간과 질적으로 다르다(오늘도 같은 이유로 허용돼 있다).

### AR7. 시작 시각 보정은 **뷰에서만** 한다 — `SubagentFact` 에 되먹이지 않는다

`SubagentStart` 미발화 실행은 `SubagentFact.started_at_ms == ended_at_ms` 라 경과가 0으로
보인다. meta.json mtime 이 진짜 시작이다(§1.3). 그러나 그 값을 `SubagentFact` 에 써 넣으면
`_compute_base_state`·좀비 가드의 입력이 호스트 파일에 의존하게 된다 — AR1 이 지키려는
구조가 깨진다.

→ **`SubagentRunView.started_at_ms` 에만** 적용한다: `meta.started_at_ms if meta else
fact.started_at_ms`. 상태 판정은 오늘과 문자 그대로 같은 입력을 본다.

### AR8. 화면의 칩은 **타입이 아니라 단계**(설계·구현·검수) — 320px 실측이 강제한다

> `.workflow-runs` 와 같은 2단 자식 자리 — 순서·레일은 LM2·LM3(hub-session-row-layout-and-modal-size.md).

목업 1차에서 `agent_type` 을 칩에 그대로 쓴 결과, 최소 트랙 320px 에서 **칩 글자가 두 줄로
찢어지고**(`code-` / `reviewer`) 제목이 절반으로 잘렸다. 원인은 flex 기본 `shrink:1` 이다 —
`.session-meta` 가 겪은 것과 같은 계열의 함정(§3.10 GOTCHA, MODEL_LABEL_MAX_CHARS 주석).

채택안:

- 칩 = `PHASE_BY_AGENT_TYPE`(hub_session.py:23)에 있으면 **`설계`/`구현`/`검수`**, 없으면
  `agent_type` 을 `AGENT_RUN_CHIP_MAX_CHARS = 12` 로 자른다. 매핑 없는 타입의 실측 최장은
  `silent-failure-hunter`(21)·`claude-code-guide`(17)·`general-purpose`(15)다.
- 칩에 `flex:0 0 auto; white-space:nowrap` 을 반드시 건다(위 함정의 직접 방어).
- `agent_type` 원문·모델·시작 시각은 **툴팁**으로 간다.
- 경과는 `margin-left:auto` 로 항상 우측 끝 — 제목이 비어도 줄 모양이 흔들리지 않는다.

이 배치로 320px 에서 제목 실측 20자 남짓이 온전히 들어간다(`description` 중앙 19자).

### AR9. 제목은 `description`, 없으면 `agent_type` — 빈 줄을 만들지 않는다

meta.json 을 못 읽은 실행(형식 변경·권한·경합 삭제)에서도 줄은 남아야 한다. 제목 자리가
비면 "왜 빈 줄이 있지"가 되므로 `agent_type` 을 대신 넣는다 — 오늘 화면이 보여주던 것과
같은 정보 수준으로 **강등**되는 것이지 사라지는 것이 아니다.

> → **개정(2026-10-01)** — 재개된 실행은 `resume_title`(부모 transcript 의 마지막 재개 요청 요약)이 먼저다: 화면의 폴백 사슬이
> `resume_title → title → agent_type` 이 됐다(hub-agent-title-and-excerpt-freshness.md 결정 TF12). `title` 의 뜻(`meta.description`)은
> 그대로이고, 재개 요약이 없으면 이 결정의 폴백(`description`, 그것도 없으면 `agent_type`) 그대로다.

### AR10. 프라이버시 — `description`·`model` 에 **계약 A**를 그대로 적용한다

`hub_workflow.py` 머리의 「계약 A」: *hub.html 에 인라인되는 문자열 필드는 예외 없이 아래 둘
중 하나의 경로를 거친다.*

| 필드 | 경로 | 상한 | 근거 |
|---|---|---|---|
| `title`(=`description`) | **스크럽 + 상한** | `SUBAGENT_TITLE_MAX_CHARS = 120` | 사용자 프롬프트에서 파생된 자유 텍스트다(`label` 이 같은 경위로 스크럽 대상이 됐다, WF7). 실측 max 51 → 120 은 병리적 입력 방어선(2.35배) |
| `model` | **상한만, 스크럽 없음** | `SUBAGENT_METADATA_MAX_CHARS = 32` | 닫힌 값 집합 성격(실측 `sonnet`·`opus`·`haiku`·`fable` 4종, max 6자). `state` 가 `WORKFLOW_METADATA_MAX_CHARS` 를 쓰는 것과 같은 판단 |
| `agent_type` | **상한만** | 같은 32 | 오늘은 상한이 없다(훅 원문 그대로) — 이 기회에 계약 A 를 소급 적용한다 |
| `agent_id` | **상한만** | 같은 32 | 정렬 타이브레이커로 뷰에 실린다. 실측 17자 |

**순서 고정: 스크럽 → 자르기.** 자르기부터 하면 절단 경계에 걸린 시크릿이 패턴 불일치로
살아남아 접두사가 샌다(`hub_redact.redact_secret_tokens` docstring). 호스트가 먼저 잘라 둔
값을 받는 처지(WF7 의 잔존 위험)는 여기도 같다 — `description` 은 호스트가 자르지 않으므로
(실측 max 51, 상한 없음) 이 위험은 `description` 에는 적용되지 않는다.

정수 필드(`started_at_ms`·`ended_at_ms`)는 `_bounded_index` 계열의 자릿수 방어가 필요 없다 —
값의 출처가 호스트 JSON 이 아니라 **우리 파일시스템의 `st_mtime` 과 우리 훅의 `t`** 다.

### AR11. 표시 상한 5 + **초과 개수 한 줄** — K3(조용히 버림)의 범위 한정 개정

현행 K3 은 "상한 밖은 화면에도 툴팁에도 나타나지 않는다"다. 타입 합계였을 때는 버려지는 것이
**이미 보이는 타입의 중복**이라 손실이 작았다. 실행 단위가 되면 45건 중 5건만 남아 **버려지는
것이 정보의 대부분**이 된다.

→ `MAX_VISIBLE_AGENT_RUNS = 5` 로 자르되 마지막에 `+N건 더` 한 줄을 둔다. 한 줄 비용으로
"몇 번 돌았는가"라는 이 요구의 핵심 사실을 지킨다. **이 개정은 이 행에만 적용된다** —
워크플로우 칩(`MAX_VISIBLE_WORKFLOW_CHIPS`)과 프로젝트 카드의 다른 상한은 K3 그대로다.

5의 근거: 카드 340px 고정 + `.sessions` 내부 스크롤에서 세션 1건이 약 3줄(기존) → 8줄(5실행+
개수줄)로 늘어난다. 목업 실측상 5줄이 "설계→구현→검수 3회 왕복"의 최근 절반을 담는 자연스러운
경계이고, 6 이상은 한 세션이 카드 한 장을 통째로 먹는다.

서버 상한은 별개다: `SUBAGENT_RUN_MAX_PER_SESSION = 100`(2일 창 실측 max 45의 2.2배).
"화면에 몇 개 보일까"가 아니라 "병리적 페이로드가 뷰 직렬화를 얼마나 부풀릴 수 있는가"를 막는
서버측 방어선이다 — `WORKFLOW_RUN_MAX_AGENTS` 와 같은 역할·같은 값.

### AR12. 첫 줄의 칩 행(`.agent-runs`)은 **제거**한다 — 두 곳에 같은 정보를 두지 않는다

실행 목록이 생기면 첫 줄 칩은 같은 사실의 열화된 사본이다. 남겨 두면 세션 하나가 9줄이 되고
"칩은 2개인데 목록은 5줄"이라는 설명 불가능한 불일치가 생긴다.

연쇄로 고칠 것: `shouldRenderSession`(hub_template.html:1526)이 "보이는 칩 0개"를 판정할 때
`visibleAgentRuns` 를 경유하던 것을 **새 `visibleAgentRunRows`** 로 갈아 끼운다. 이 경유는
GOTCHA 3(직접 `length` 를 보면 칩 유무와 줄 표시가 어긋난다)의 방어이므로 **경유 자체를
없애면 안 된다.**

### AR13. 부모-자식 중첩은 **하지 않는다**

- `spawnDepth == 2` 는 818건 중 **30건(3.7%)**, 3단은 **0건**.
- 그 30건은 **훅 이벤트에 0건 나타난다**(§1.2) — 조립 경로로는 발견 자체가 불가능하다.
- 발견하려면 `subagents/` 디렉터리 전체를 glob 하고 모든 meta 를 파싱해 `parentAgentId` 를
  봐야 한다: 최악 디렉터리에서 glob 17ms + 파싱 37ms. **3.7% 를 위해 정상 부하(1~8ms)의
  6배를 더 쓴다.**
- 트리의 들여쓰기 2단은 이미 세션(1단) → 진행률·위임(2단)으로 다 쓰였다(결정 TR6, 좌 24px).
  3단은 기하 상수를 새로 만들어야 한다.

세 가지가 같은 방향을 가리킨다. YAGNI — 실제로 3단 오케스트레이션을 쓰기 시작하면 그때 연다.

### AR14. 토큰 사용량은 **싣지 않는다** (사용자 판단 요청, §13-①)

넣으려면 실행마다 agent jsonl 을 읽어야 한다. 실측으로 확정한 것:

- 전체 읽기는 **1,013ms / 148.5MB** — 논외.
- 꼬리 128KiB 면 **222건에 120ms**, 1건당 0.54ms. 정상 부하(5~45건)에서는 3~24ms 로
  감당 가능하다. **그리고 꼬리의 최댓값은 전체의 최댓값과 222/222 일치한다**(꼬리로 충분하다).
- 집계는 "마지막 턴"이 아니라 **최댓값**이어야 한다(중단된 에이전트 3%에서 마지막 턴이 0k 로
  무너진다). 전 턴 합산은 `cache_read` 누적 때문에 187M 같은 값이 나온다.

그래서 **기술적으로는 가능하다.** 넣지 않는 이유는 비용이 아니라 **자리**다: 320px 줄은
`[칩][제목][경과]` 로 이미 꽉 찼고(AR8 의 1차 목업이 그것을 보여줬다), 토큰을 넣으려면 제목을
내려야 한다. 제목이 이 요구의 핵심이고 토큰은 부가 정보다.

넣는다면 위치는 **툴팁**이고, 비용은 collect 당 +3~24ms(전체 예산 50ms 의 6~48%)다.
사용자가 원하면 Task 6 로 분리해 붙인다(§11).

---

### PS1. `last-prompt` 파싱은 **`hub_transcript.py` 에 얹는다** — 새 모듈을 만들지 않는다

판단 기준은 "같은 외부 계약인가"다.

- `subagents/*.meta.json` 은 **다른 파일·다른 디렉터리·다른 수명**이라 새 모듈(AR2).
- `last-prompt` 는 `hub_transcript.py` 가 **이미 읽고 있는 바로 그 문자열의 다른 줄**이다.
  새 모듈로 빼면 같은 128KiB 를 두 모듈이 각각 훑거나, 한쪽이 다른 쪽에 텍스트를 넘겨주는
  군더더기 층이 생긴다. 계약이 깨지는 방식도 같다(호스트가 transcript 줄 형식을 바꾼다).

모듈 docstring 의 한 줄 요약을 "(모델, effort)를 판다" → "세션의 표시 정보(모델·effort·마지막
프롬프트)를 판다"로 갱신한다.

### PS2. 역방향 스캔은 **1회** — `parse_session_tail(tail) -> SessionTail`

`parse_session_model_from_tail` 은 뒤에서 앞으로 훑으며 첫 assistant 줄에서 멈춘다(결정 MD6).
`last-prompt` 도 "마지막 값"을 찾는 같은 방향의 스캔이다. 두 함수를 각각 부르면 128KiB 를
두 번 훑는다 — 하나로 합쳐 **둘 다 찾으면 조기 종료**한다.

`parse_session_model_from_tail` 은 **남긴다**(공개 이름 유지) — `tests/hub/test_hub_transcript.py`
의 표 전체가 그 이름에 앵커링돼 있고, 새 함수가 그것을 내부적으로 재사용하는 형태로 두면
기존 회귀 가드가 전부 살아 있다.

### PS3. `task_excerpt` 를 `SessionFacts` 에서 떼어 `compute_session_view` 의 인자로 옮긴다

오늘 `task_excerpt` 는 훅 이벤트가 주는 값이라 `SessionFacts` 에 있다. 출처가 transcript 로
바뀌면 그 자리는 계약 위반이다(`SessionFacts` = 훅 이벤트만). `model`(MD7)·`workflow`(WF1)와
**완전히 같은 관례**로 옮긴다 — "이 함수가 계산하지 않고 뷰에 실어 나르기만 한다".

`SessionView.task_excerpt` 는 **자리·이름·타입이 그대로다**(필드 순서 무변경 → T25-150 무영향).
바뀌는 것은 값이 어디서 오느냐뿐이라 템플릿은 한 글자도 고치지 않는다.

`_apply_tracked_event`(hub_session.py:233)의 `UserPromptSubmit` 분기는 `turn_state = "running"`
한 줄만 남는다. 그 분기의 정교한 주석("발췌는 있을 때만 덮어쓴다 …")은 함께 삭제한다 —
`p` 가 없어지면 그 함정 자체가 사라진다.

> **잃는 성질 하나(명시)**: 오늘의 발췌는 "마지막으로 **입력한** 프롬프트"다(자동주입 알림
> 턴은 직전 값을 유지). `last-prompt` 도 호스트가 같은 의미로 남기는 것으로 보이지만
> (자동주입 태그 시작 0/30), 그 규칙은 **호스트 소유**라 우리가 강제할 수 없다. 깨지면
> 클라이언트 방어 필터(PS6)가 화면에서 가린다.

> → **보강(2026-09-30)** — 실제로 잃은 것은 **즉시성**이었다(오늘의 발췌는 입력 순간에 바뀌었는데 `last-prompt` 는 수십 초
> 늦게 실린다). hub-agent-title-and-excerpt-freshness.md 결정 TF1 이 되살린다 — 사람 프롬프트 줄에서 호스트 규칙으로 유도한 값과
> `last-prompt` 값 중 파일에서 더 뒤의 것이 발췌다.

### PS4. 훅의 `p` 생산·소비를 **전부** 지운다

| 대상 | 처분 | 근거 |
|---|---|---|
| `hub_hook.PROMPT_EXCERPT_MAX_CHARS` (+17줄 근거 주석) | **삭제** | 기록할 프롬프트가 없다 |
| `hub_hook.PROMPT_TRUNCATION_MARK` · `_clip_prompt` | **삭제** | 위와 동반 |
| `hub_hook.AUTO_INJECTED_PROMPT_BLOCK` · `strip_auto_injected_blocks` | **삭제** | 벗길 대상이 없다 |
| `hub_hook` 의 `redact_secret_tokens`·`SECRET_REDACTION_MARK` 임포트(재노출) | **삭제** | 훅이 스크럽할 문자열이 0개가 된다. `hub_redact.py` 자체는 남는다(`hub_workflow.py`·신규 `hub_subagent.py` 가 쓴다) |
| `hub_hook._project_fields` 의 `prompt` 분기 | **삭제** | — |
| `hub_session.HookEvent.prompt_excerpt` · `parse_event_line` 의 `payload.get("p")` | **삭제** | 소비자가 없다 |
| `hub_session.SessionFacts.task_excerpt` · `_MutableSession.task_excerpt` | **삭제** | PS3 |

**남는 것**: `SessionStart`/`Stop`/`SubagentStart`/`SubagentStop`/`SessionEnd` 처리, 리텐션
정리, 재수집 spawn. 훅 6종 설치는 그대로다(`UserPromptSubmit` 도 `turn_state` 때문에 남는다).

### PS5. 이미 쌓인 `p`(최대 7일치)는 **읽지 않고, 지우지도 않는다**

- **읽지 않는다**: 폴백으로 남기면 "허브는 프롬프트 사본을 쓰지 않는다"가 반만 참이 되고,
  옛 기록(자동주입 필터 이전 세대 포함)이 화면에 되살아난다. `last-prompt` 보유율이 30/30
  이라 폴백이 실제로 발동할 경우가 없다 — transcript 없는 세션은 실측 예외 없이
  `SessionStart`+`SessionEnd` 2건뿐인 비대화형 기동이고(hub/README.md 「알려진 한계」),
  거기엔 프롬프트 자체가 없다.
- **지우지도 않는다**: `prune_old_event_files` 의 불변식이 "살아 있는 파일은 절대 다시 쓰지
  않는다"(hub_collect.py:253 docstring)다. 오늘·어제 파일을 재작성하면 동시 append 중인
  훅과 경합한다. 기존 리텐션(`event_retention_days: 7`)으로 **최대 7일 뒤 자연 소멸**한다.
- 이 7일은 **README 에 명시한다**(§9) — "지금 이후로 새로 기록되지 않고, 이미 기록된 것은
  최대 7일 내 삭제된다".

### PS6. 클라이언트 방어 필터 `displayableExcerpt` 는 **남긴다** — T25-120 만 단방향으로 고친다

훅 쪽 정규식이 사라지면 T25-120 의 양방향 태그 집합 대조(hub_hook ↔ hub_template)는 앵커가
깨진다. 두 선택지:

| | 남긴다(채택) | 함께 지운다 |
|---|---|---|
| 비용 | 3줄 유지 + 테스트를 존재 검사로 강등 | 코드 3줄·테스트 1개 감소 |
| 실패 시 | — | 호스트가 `lastPrompt` 에 `<ide_selection>` 을 넣기 시작하면 **선택한 소스코드가 hub.html 평문에 인라인된다** |

비대칭이 크다. 근거 실측이 30건뿐이고 그 규칙은 호스트 소유다. **남긴다.**
T25-120 은 "두 파일의 태그 집합이 같은가"에서 "`displayableExcerpt` 가 존재하고
`renderSession` 이 그것을 경유하는가"로 바꾼다 — 한쪽만 남으면 단방향 검사가 구조적으로 옳다.

### PS7. `record_prompt_excerpt` 는 **이름을 유지하고 의미를 확장한다**

| | 지금 | 뒤 |
|---|---|---|
| `false` 일 때 | 훅이 `p` 를 안 쓴다 + `wf_*.json` 을 안 읽는다(WF8) | **`last_prompt` 를 뷰에 싣지 않는다** + `wf_*.json` 을 안 읽는다 + **`subagents/*.meta.json` 을 안 읽는다** |

세 경로 모두 "프롬프트에서 파생된 자유 텍스트를 hub.html 에 싣는다"는 같은 성격이므로 스위치
하나로 묶는 것이 옳다(WF8 이 이미 내린 판단). **이름은 바꾸지 않는다** — 바꾸면 기존
`config.json` 이 조용히 무시된다.

`false` 일 때도 **transcript 꼬리 자체는 계속 읽는다**(모델·effort 표시는 별도 옵트아웃이
없는 기본 표시 정보다, hub/README.md 프라이버시 고지). 파서가 `last_prompt` 를 **버리는**
방식이지 파일을 안 읽는 방식이 아니다 — 이것이 `wf_*.json`(아예 안 읽음)과 다른 유일한 지점이고,
README 에 그대로 적는다.

실행 목록 자체는 어떻게 되나: `record_prompt_excerpt:false` 면 meta.json 을 안 읽으므로
제목·모델이 빠지고, 줄은 **AR9 의 폴백(제목 자리에 `agent_type`)** 으로 남는다. 즉 오늘 화면과
같은 정보량으로 강등된다 — 기능이 통째로 사라지지 않는다.

### PS8. 발췌 상한은 **서버가 다시 건다** — 호스트 상한(201)을 믿지 않는다

`LAST_PROMPT_MAX_CHARS = 400`. 실측 최대 201의 약 2배 여유. 호스트가 자르기를 멈추면 프롬프트
전문이 `hub.html` 에 인라인된다 — 범위 밖 항목 ①("프롬프트 전문을 싣지 않는다")을 지키는
구조적 방어선이다. 정상 데이터에서는 발동하지 않는다.

### PS9. **`last_prompt` 도 스크럽한다** — 오늘 훅이 하던 일을 파서가 물려받는다

오늘 파이프라인은 `strip → redact → clip` 이다. 출처만 바꾸고 스크럽을 빼면 **프롬프트에 타이핑한
API 키가 `hub.html` 평문에 그대로 인라인된다** — 요구 2가 프라이버시 개선인데 보안이 후퇴한다.

`hub_transcript.py` 가 `hub_redact.redact_secret_tokens` 를 임포트한다. 순환이 없다:
`hub_collect → hub_transcript → hub_redact`, `hub_redact` 는 아무것도 임포트하지 않는다
(`hub_workflow → hub_redact` 가 이미 같은 모양이다). 순서는 **redact → clip**.

**잔존 위험(WF7 과 동형)**: 호스트가 이미 201자로 자른 문자열을 받으므로, 그 절단 경계에
걸린 시크릿은 패턴 불일치로 살아남을 수 있다. 우리가 자르기 전에 스크럽한다는 규칙은
지키지만 호스트의 절단에는 개입할 수 없다. `hub_workflow.py` 가 같은 조건을 이미 문서화된
잔존 위험으로 안고 있다.

---

## 4. 영향 범위

### 4.1 추가

| 파일 | 줄 수(예상) | 이유 |
|---|---|---|
| `hub/bin/hub_subagent.py` (★순수) | ~110 | meta.json 파서 + `SubagentMeta`. 외부 계약 격리(AR2) |
| `hub/bin/hub_subagent_read.py` (I/O) | ~90 | 경로 조립·stat·읽기·세션 순회. hub_collect 800줄 상한(AR2) |
| `tests/hub/test_hub_subagent.py` | ~200 | 파서 표 + 병리적 입력 |
| `tests/hub/test_hub_subagent_read.py` | ~150 | 경로 조립·결손·권한 실패 |

### 4.2 수정

| 파일 | 무엇을 |
|---|---|
| `hub/bin/hub_session.py` | `SubagentRunView` 필드 확장(AR4) · `summarize_agent_runs` 를 실행 단위로(AR4·AR5·AR7·AR11) · `compute_session_view` 에 `task_excerpt`·`subagent_meta_by_agent_id` 인자(PS3) · `HookEvent.prompt_excerpt`·`SessionFacts.task_excerpt`·`_MutableSession.task_excerpt` 삭제(PS4) |
| `hub/bin/hub_transcript.py` | `SessionTail` + `parse_session_tail`(PS1·PS2) · `LAST_PROMPT_MAX_CHARS`(PS8) · `hub_redact` 임포트(PS9) |
| `hub/bin/hub_hook.py` | `p` 생산 코드 일체 삭제(PS4). ~55줄 감소 |
| `hub/bin/hub_collect.py` | `read_session_model(s)` → `read_session_tail(s)` · `collect_snapshot` 에 `hub_subagent_read` 호출 추가 |
| `hub/bin/hub_project.py` | `compose_project_views`·`_session_views_for_path` 에 `tail_by_session_id`(교체)·`subagent_meta_by_agent_id`(추가) 전달 |
| `hub/bin/hub_template.html` | 실행 목록 렌더·CSS 4규칙·상수 4개 추가, 첫 줄 칩 행 제거(AR12) |
| `hub/install.sh` | `HUB_FILE_COUNT` 21 → **23** |
| `hub/README.md` | 프라이버시 고지 2항목 개정 · 「화면 배치」 서브에이전트 서술 개정 · 「파일 배치」 23개 |
| `commands/hub.md` | 설치 동의 문구에서 "프롬프트 앞부분(500자) … 평문 보관" 삭제, 서브에이전트 제목 인라인 고지 추가 |
| `rules/python/coding-style.md` | 「Constants」 예시가 `hub_hook.PROMPT_EXCERPT_MAX_CHARS` 를 인용한다 — 사라지는 상수다. 같은 성격의 살아 있는 상수로 교체(예: `hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS`) |
| `tests/run.sh` | T25-120 단방향화 · T25-149 카운트 23 · 신규 T25-205~T25-212 |
| `tests/hub/test_hub_session.py` · `test_hub_collect.py` · `test_hub_transcript.py` · `test_hub_hook.py` · `test_hub_model.py` | 위 변경에 따른 갱신 |

**T26(상시 컨텍스트 예산 래칫)은 무관하다** — 계수 집합은 `CLAUDE.md` + `rules/README.md` +
`rules/common/*.md` + `rules/workflow/*.md` 이고, 여기서 손대는 `rules/python/coding-style.md` 는
조건부 로딩(`paths: **/*.py`)이라 대상이 아니다. **다만 그 교체가 바이트 중립이 아니어도
T26 은 통과하므로, 커밋 메시지에만 이유를 남긴다.**

### 4.3 반드시 먼저 읽을 파일

| 우선 | 파일 | 범위 | 왜 |
|---|---|---|---|
| P0 | `hub/bin/hub_session.py` | 전체 489줄 | 바꿀 것의 본체. `SessionView` docstring 의 D2·MD7·WF1·FT7 주석이 새 필드의 배치 규칙이다 |
| P0 | `hub/bin/hub_workflow.py` | 1-47(머리 주석), 126-205 | 「계약 A」·타입 방어·`_clip_to_length` — AR10 이 그대로 복제할 원본 |
| P0 | `hub/bin/hub_workflow_read.py` | 전체 145줄 | AR2 의 I/O 위성 모듈이 베낄 원본(경로 가드·OSError 흡수·경고 반환 계약) |
| P0 | `hub/bin/hub_transcript.py` | 전체 116줄 | PS1·PS2 가 얹힐 자리 |
| P1 | `hub/bin/hub_collect.py` | 135-252, 496-548 | 이벤트 읽기·꼬리 읽기·`collect_snapshot` 배선 |
| P1 | `hub/bin/hub_template.html` | 404-520(CSS), 1020-1070(상수), 1310-1530(렌더) | 실행 목록이 들어갈 자리와 GOTCHA 3 경유 규칙 |
| P1 | `tests/run.sh` | 6990-7040(T25-120), 7690-7740(T25-150), 6573-6590(T25-100) | 건드리면 깨지는 계약 3개 |
| P2 | `docs/prps/hub-workflow-visibility.md` | §4(WF1~WF11) | 같은 구조의 선행 설계. 여기서 내린 판단의 대부분이 그 문서의 재적용이다 |
| P2 | `docs/prps/hub-ui-4-issues.md` | §2(TR1~TR8), §4(WT1~WT8) | 트리 기하·칩 툴팁 제거 근거 |

---

## 5. 데이터 모델

### 5.1 `hub_subagent.py` (★순수, 신규)

```python
SUBAGENT_DIR_NAME = "subagents"                 # <session_id>/ 아래 메타 디렉터리
SUBAGENT_META_FILE_PREFIX = "agent-"
SUBAGENT_META_FILE_SUFFIX = ".meta.json"
SUBAGENT_META_MAX_BYTES = 64 * 1024             # 실측 max 약 300B 의 200배 방어선
SUBAGENT_TITLE_MAX_CHARS = 120                  # description 실측 max 51 의 2.35배(AR10)
SUBAGENT_METADATA_MAX_CHARS = 32                # model·agent_type·agent_id 공용(AR10)
SUBAGENT_TRUNCATION_MARK = "…"

@dataclass(frozen=True)
class SubagentMeta:
    """subagents/agent-<id>.meta.json 1건의 표시용 투영. 전부 계약 A 를 거친 값이다."""
    title: str          # description. 스크럽 + SUBAGENT_TITLE_MAX_CHARS. 없으면 ""
    agent_type: str     # 32자 상한만. 없으면 ""
    model: str | None   # 별칭(sonnet/opus/haiku/fable). 32자 상한만. 키 부재 실측 18.7% → None
    started_at_ms: int  # 파일 mtime. 파서가 아니라 I/O 층이 채운다(§6.2 참조)
```

### 5.2 `hub_transcript.py` — 추가

```python
LAST_PROMPT_LINE_TYPE = "last-prompt"
LAST_PROMPT_MAX_CHARS = 400          # 호스트 실측 max 201 의 약 2배 방어선(PS8)

@dataclass(frozen=True)
class SessionTail:
    """세션 transcript 꼬리에서 판 표시 정보 묶음. 둘 다 정당하게 부재할 수 있다."""
    model: SessionModel | None
    last_prompt: str | None          # 스크럽 + LAST_PROMPT_MAX_CHARS 를 거친 값(PS9)
```

### 5.3 `hub_session.py` — `SubagentRunView` 개정

```python
@dataclass(frozen=True)
class SubagentRunView:
    """세션에서 실행된 서브에이전트 **1건**의 표시 상태(결정 AR4 — 타입 합계에서 실행 단위로).

    개정 전에는 같은 agent_type 의 여러 실행을 하나로 합친 뷰였다. 합치면 "검수 3회"가
    화면에서 1회와 구별되지 않는다(이 PRP 의 출발점).
    """
    agent_id: str              # 훅 `ai` == meta.json 파일명의 agentId. 정렬 타이브레이커(AR5)
    agent_type: str            # 훅 원문(없으면 meta.json). 32자 상한
    phase: Phase | None        # PHASE_BY_AGENT_TYPE 에 없으면 None → 칩이 agent_type 으로 폴백(AR8)
    is_running: bool           # is_running_subagent 공유(결정 ZG4 — 카드 상태와 어긋날 수 없다)
    started_at_ms: int         # meta.json mtime, 없으면 훅 SubagentStart(AR7). **정적 — D2 안전**
    ended_at_ms: int | None    # 훅 SubagentStop. 미종료면 None. **정적 — D2 안전**
    title: str | None          # meta.description(스크럽+상한). 없으면 None → 화면은 agent_type 폴백(AR9)
    model: str | None          # meta.model 별칭. 없으면 None(실측 18.7%)
```

`SessionView` 는 **필드가 늘지 않는다** — `agent_runs` 의 원소 타입만 바뀐다.
`task_excerpt` 도 자리·이름·타입이 그대로다. **T25-150(마지막 필드 =
`tier1_is_finished_task`)은 무영향**이다.

### 5.4 `hub_session.py` — 삭제

```python
# HookEvent.prompt_excerpt          (PS4)
# SessionFacts.task_excerpt         (PS3 — compute_session_view 인자로 이동)
# _MutableSession.task_excerpt      (PS3)
```

---

## 6. 인터페이스

### 6.1 `hub/bin/hub_subagent.py` (★순수, 신규)

```python
def parse_subagent_meta(text: str, started_at_ms: int) -> SubagentMeta | None:
    """meta.json 본문을 표시용 뷰로 판다. 형식이 아니면 None(호출자가 건너뛴다).

    **계약 B(hub_workflow.parse_workflow_run 과 동형) — 어떤 입력에도 예외를 던지지 않는다.**
    json.loads 는 ValueError(구문 오류 + 4,300자리 초과 정수 리터럴)와 RecursionError 를
    함께 잡는다. isinstance 로만 방어하고 agent_type·model 값을 표로 좁히지 않는다 —
    실측에 없는 값이 나와도 화면이 죽지 않아야 한다.
    """

def _scrubbed_and_clipped(value: str) -> str: ...     # title 경로: redact → clip(120)
def _metadata_field(value: object) -> str: ...        # model/agent_type 경로: clip(32)만
def clip_metadata(value: str) -> str: ...             # 훅 유래 agent_type·agent_id 에도 쓰도록 공개
```

`_clip_to_length` 는 `hub_workflow.py` 의 것과 동작이 같다. **복제하지 않고**
`from hub_workflow import _clip_to_length` 도 하지 않는다(사적 심볼 임포트는 금지) —
두 모듈이 각자 3줄짜리 동일 구현을 갖는 것과, 공용 모듈을 하나 더 만드는 것 중
**전자를 택한다**: `hub_redact.py` 추출(WF3)은 "패턴을 두 곳에 복제하면 한쪽만 갱신되는
**보안** 드리프트가 난다"가 근거였는데, 문자열 자르기에는 그 성질이 없다.

### 6.2 `hub/bin/hub_subagent_read.py` (I/O, 신규)

```python
def read_subagent_meta(
    session_id: str, observed_cwds: Sequence[str], agent_id: str, projects_dir: Path
) -> tuple[SubagentMeta | None, str | None]:
    """실행 1건의 meta.json 을 읽어 (뷰, 경고) 를 돌려준다. 절대 예외를 던지지 않는다.

    경로는 조립한다(결정 AR3) — glob 하지 않는다. session_id·agent_id 는 조립 전에
    `/`·""·"."·".." 를 걷어낸다(hub_workflow_read._existing_workflow_directories 와 같은 가드).
    observed_cwds 를 순서대로 시도하고 **먼저 존재하는 것**을 쓴다(결정적, MD2·E14 와 동형).
    started_at_ms 는 이 층이 `stat().st_mtime` 으로 채워 파서에 넘긴다 — 파서는 ★순수라
    파일시스템에 닿을 수 없다(결정 AR1·AR2).
    """

def read_subagent_metas(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    record_prompt_excerpt: bool,
    projects_dir: Path,
) -> tuple[dict[str, SubagentMeta], tuple[str, ...]]:
    """수집 대상 세션의 **추적된 실행 전부**의 meta 를 {agent_id: SubagentMeta} 로 모은다.

    `record_prompt_excerpt` 가 거짓이면 파일을 아예 읽지 않고 빈 결과를 돌려준다(결정 PS7,
    read_session_workflows 와 같은 형태). 캐시를 두지 않는다(MD4·WF10 과 같은 판단 —
    §2 계측 근거). 세션당 읽는 실행 수는 SUBAGENT_RUN_MAX_PER_SESSION 으로 제한한다
    (정렬 후 앞에서부터) — 45건 세션이 여럿인 병리적 날에도 읽기 예산이 선형으로 묶인다.
    """
```

### 6.3 `hub/bin/hub_transcript.py`

```python
def parse_session_tail(tail_text: str) -> SessionTail:
    """꼬리에서 (모델·effort)와 마지막 프롬프트를 **한 번의 역방향 스캔**으로 판다(PS2).

    둘 다 "마지막 값"이므로 뒤에서 앞으로 훑고, 둘 다 찾으면 즉시 멈춘다. 꼬리의 첫 줄은
    파일 중간에서 잘렸을 수 있으나 JSON 파싱 실패로 자연히 탈락한다(MD6 와 같다).
    last_prompt 는 redact → clip(LAST_PROMPT_MAX_CHARS) 순서를 지킨다(PS9).
    """

def parse_session_model_from_tail(tail_text: str) -> SessionModel | None:
    """(유지) parse_session_tail(tail_text).model 과 같다 — 기존 테스트 표의 앵커."""
```

### 6.4 `hub/bin/hub_collect.py`

```python
def read_session_tail(session_id, observed_cwds) -> hub_transcript.SessionTail | None: ...
def read_session_tails(sessions_by_path) -> dict[str, hub_transcript.SessionTail]: ...
#  ↑ read_session_model / read_session_models 의 개명. 본문은 파서 호출 한 줄만 바뀐다.
```

`collect_snapshot` 배선:

```python
tail_by_session_id = read_session_tails(sessions_by_path)
subagent_meta_by_agent_id, subagent_warnings = hub_subagent_read.read_subagent_metas(
    sessions_by_path, config.record_prompt_excerpt, PROJECTS_DIR
)
warnings.extend(subagent_warnings)
projects = hub_project.compose_project_views(
    tier1_by_path, sessions_by_path, tier3_by_path, now_ms, stale_after_ms,
    tail_by_session_id, session_dashboards_by_path, workflow_by_session_id,
    subagent_meta_by_agent_id,
)
```

`record_prompt_excerpt:false` 일 때 `last_prompt` 를 버리는 지점은 **`read_session_tails`**
다(파일은 읽되 값을 안 싣는다, PS7).

### 6.5 `hub/bin/hub_session.py`

```python
def summarize_agent_runs(
    facts: SessionFacts,
    now_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,
    subagent_meta_by_agent_id: dict[str, SubagentMeta] | None = None,
) -> tuple[SubagentRunView, ...]:
    """세션의 서브에이전트 **실행 1건당 뷰 1개**를 만든다(AR4).

    정렬은 K2 그대로 — 실행 중 우선, 그 다음 최근 시작 내림차순, 동률은 agent_id(AR5,
    snapshot_content_key 결정성). `is_running` 은 `_compute_base_state` 와 같은 술어
    (`is_running_subagent`)를 쓴다 — 좀비는 여기서도 실행 중이 아니다(ZG1·ZG4).
    meta 는 보강일 뿐이라 없으면 훅 값만으로 뷰가 만들어진다(AR9). 개수는
    SUBAGENT_RUN_MAX_PER_SESSION 으로 자른다(AR11 — 서버측 직렬화 방어선).
    """

def compute_session_view(
    facts, now_ms, stale_after_ms,
    zombie_after_ms=SUBAGENT_ZOMBIE_AFTER_MS,
    model=None, tier1=None, dashboard_key=None, workflow=None,
    task_excerpt: str | None = None,                              # ← PS3
    subagent_meta_by_agent_id: dict[str, SubagentMeta] | None = None,   # ← AR1
) -> SessionView: ...
```

### 6.6 `hub/bin/hub_project.py`

`compose_project_views` 의 `model_by_session_id: dict[str, SessionModel] | None` 를
**`tail_by_session_id: dict[str, SessionTail] | None` 으로 교체**하고(인자 수 유지),
`subagent_meta_by_agent_id` 를 마지막 선택 인자로 **추가**한다(총 9개).

교체를 택한 이유: 모델과 발췌를 딕셔너리 2개로 나르면 같은 출처(한 번의 꼬리 읽기)에서 나온
두 값이 호출부마다 따로 전달돼 드리프트한다. 묶음이 출처를 정직하게 반영한다.

---

## 7. 렌더링 (`hub_template.html`)

### 7.1 상수 (기존 상수 블록 1029행 인접)

```js
var MAX_VISIBLE_AGENT_RUNS = 5;        // 실행 목록 표시 상한(결정 AR11). 초과분은 개수 줄로 알린다
var AGENT_RUN_CHIP_MAX_CHARS = 12;     // 단계 매핑이 없는 타입의 칩 절단(AR8)
var AGENT_RUN_OVERFLOW_SUFFIX = '건 더';
var AGENT_RUN_NO_MODEL_LABEL = '모델 미기록';   // meta.model 부재 18.7%(§1.1)
// MAX_VISIBLE_AGENT_CHIPS 는 삭제(AR12 — 첫 줄 칩 행이 사라진다)
```

### 7.2 함수 (순수 — DOM 에 닿지 않는다)

```js
function agentRunChipLabel(run)      // phase ?? clip(agent_type, AGENT_RUN_CHIP_MAX_CHARS)
function agentRunDisplayTitle(run)   // run.title || run.agent_type   (AR9)
function agentRunElapsedLabel(run, nowMs)
    //  run.ended_at_ms ? durationLabel(ended - started) : durationLabel(nowMs - started)
    //  ★ 서버가 계산하지 않는다(AR6/D2). nowMs 는 호출부가 Date.now() 로 넘긴다.
function agentRunTooltipText(run)    // 기존 함수 확장:
    //  "code-reviewer · 검수 단계 · sonnet · 시작 16:50 · 진행 중"
    //  타입·모델·시작 시각은 화면에 없으므로 여기가 유일한 출처다(결정 R4 충족 — 정보 손실 실재)
function visibleAgentRunRows(runs)   // runs.slice(0, MAX_VISIBLE_AGENT_RUNS). **유일한 판정자**
function renderAgentRunRow(run, nowMs)
function renderAgentRunList(runs)    // 빈 배열이면 '' — 줄 자체가 생기지 않는다
```

`shouldRenderSession` 은 `visibleAgentRuns` → `visibleAgentRunRows` 로 갈아 끼운다.
**`length` 를 직접 보지 않는다**(GOTCHA 3).

### 7.3 마크업

```html
<div class="agent-run-list">
  <div class="agent-run" data-tooltip="…">
    <span class="agent-chip agent-chip-running"><span class="glyph">●</span>검수<span class="sr-only"> 진행 중</span></span>
    <span class="agent-run-title">레포 subtree 스코핑 코드 검수</span>
    <span class="agent-run-meta">6분</span>
  </div>
  …
  <div class="agent-run-more">+4건 더</div>
</div>
```

> → **개정(2026-09-30)** — 실행 중 칩의 글리프(`<span class="glyph">●</span>`)는 삭제됐다. 마크업은
> `<span class="agent-chip agent-chip-running">검수<span class="sr-only"> 진행 중</span></span>` 이다(hub-session-modal-cleanup.md 결정 MX10).

`renderSession` 에서의 자리: `renderSessionMeta` 다음, `renderWorkflowRun` 앞.
(DOM 순서. 시각 순서는 CSS `order` 가 정한다 — `.session-row>.session-tier1{order:1}` 관례.)

### 7.4 CSS (신규 4규칙, **새 색 토큰 0개**)

```css
/* .workflow-runs 와 같은 2단 자식 자리 — 트리 기하(레일 left:-12px, 갈고리 14px)를 그대로
   물려받아 새 기하 상수를 만들지 않는다. */
.agent-run-list{position:relative;margin-left:16px;margin-top:4px;display:flex;flex-direction:column;gap:2px}
.agent-run-list::before{content:"";position:absolute;left:-12px;top:-4px;height:14px;width:8px;
    border-left:1px solid var(--muted);box-shadow:inset 0 -1px 0 0 var(--muted);opacity:.5}
.agent-run{display:flex;align-items:baseline;gap:6px;min-width:0}
/* ★ 칩은 절대 줄지 않는다 — flex 기본 shrink:1 을 두면 320px 에서 칩 글자가 두 줄로 찢어진다
   (목업 1차 실측). .session-meta 가 겪은 것과 같은 계열의 함정이다. */
.agent-run>.agent-chip{flex:0 0 auto;white-space:nowrap}
.agent-run-title{flex:1 1 auto;min-width:0;font-size:11.5px;color:var(--ink);
                 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* 경과는 항상 오른쪽 끝 — 제목이 비어도 줄 모양이 흔들리지 않는다. */
.agent-run-meta{flex:0 0 auto;margin-left:auto;font-size:11px;color:var(--muted);
                font-family:ui-monospace,monospace;letter-spacing:-.2px;white-space:nowrap}
.agent-run-more{font-size:11px;color:var(--muted);margin-top:2px}
```

`.agent-chip`·`.agent-chip-running`·`.sr-only` 는 **그대로 재사용**한다.
`.agent-runs`(inline-flex 칩 행)는 삭제한다(AR12).

### 7.5 접근성

- 실행 중 표시는 색 단독이 아니다 — 글리프 `●` + `.sr-only` "진행 중"(오늘 관례 그대로, GOTCHA 2).

  > → **개정(2026-09-30)** — 글리프 `●` 를 뺐다(hub-session-modal-cleanup.md 결정 MX10, 사용자 승인). 실행 중/종료의 시각 구분은
  > 칩 색 하나이고, 화면 낭독기용 `.sr-only` 「진행 중」과 행 툴팁의 「진행 중」은 그대로다. 「색 단독이 아니다」는 원칙은 시각
  > 채널에서 의도적으로 좁혀졌다 — 그 대가(WCAG 1.4.1)와 완화(실행 중 칩이 목록 맨 앞에 정렬됨·세션 배지가 텍스트+글리프+색으로
  > 작업중을 말함)는 MX10 에 기록돼 있다.
- 툴팁은 `.agent-run` 행 전체에 붙인다(hover 전용, 발췌·워크플로우 칩과 같은 취급).
- 세션 행이 `<button>` 이므로 그 안에 인터랙티브 요소를 넣지 않는다(오늘과 동일).

---

## 8. 미리보기 목업 (승인 대상)

문서와 ASCII 다이어그램으로는 "실행 목록"과 "실행 칩"이 구별되지 않는다. **독립 실행 HTML
목업**을 함께 낸다 — 실제 색 토큰·실제 CSS·실제 마크업·실측 데이터로 그렸다.

```
/private/tmp/claude-501/-Users-dev-private-project-coding-harness/768e8a38-ef92-4a4b-a356-e96efbcc80f2/scratchpad/hub-agent-runs-mockup.html
/private/tmp/claude-501/-Users-dev-private-project-coding-harness/768e8a38-ef92-4a4b-a356-e96efbcc80f2/scratchpad/hub-agent-runs-mockup.png
```

담긴 것: ① 기본(실행 3건) 현재/안 A/안 B 3열 대조 · ② 많을 때(실행 9건, 상한과 오버플로) ·
③ 상호작용 상태(hover · 패널 열림 · meta 결손) · ④ 다크 테마 같은 3열 · ⑤ 요구 2의 발췌
출처 교체 전후. 카드 폭은 전부 **320px**(그리드 최소 트랙 = 최악 폭), 높이는 실제와 같은
**340px 고정**이다.

**목업이 실제로 설계를 바꾼 지점**(이 문서를 쓰는 근거): 1차 목업에서 `agent_type` 칩이
320px 에서 두 줄로 찢어지고 제목이 절반으로 잘렸다 → 칩을 단계 라벨로 바꾸고 모델을 툴팁으로
내렸다(AR8). 문서만으로는 발견되지 않았을 결함이다.

---

## 9. 프라이버시 고지 개정 (`hub/README.md` · `commands/hub.md`)

### 9.1 삭제 — README 「프라이버시 고지」 첫 항목 전체

> ~~프롬프트 앞부분 **500자**가 `~/.claude/hub/events/*.jsonl` 에 평문으로 최대 **7일**
> 보관된다. … 상한을 낮추려면 `hub/bin/hub_hook.py` 의 `PROMPT_EXCERPT_MAX_CHARS` 를 고치고
> 다시 설치한다.~~

대체 문구(요지):

> - **허브는 프롬프트 사본을 만들지 않는다.** 카드의 발췌는 Claude Code 가 자기 transcript 에
>   이미 남긴 마지막 프롬프트(`last-prompt`, 호스트가 최대 201자로 자른 값)를 읽어 보여준다 —
>   허브가 읽는 꼬리 128KiB 안에 이미 있어 **추가로 읽는 파일이 없다.** 이 값은 `hub.html` 에
>   인라인되며, 알려진 시크릿 패턴은 인라인 전에 `[REDACTED]` 로 마스킹된다.
>   끄는 수단은 `config.json` 의 `record_prompt_excerpt: false` (그때도 모델 표시를 위한
>   꼬리 읽기 자체는 계속된다 — 발췌만 싣지 않는다).
> - **옛 기록 안내**: 이 변경 이전 버전이 `events/*.jsonl` 에 남긴 프롬프트 발췌는 **더 이상
>   읽지 않으며**, 기존 보관 기간(`event_retention_days`, 기본 7일)에 따라 최대 7일 안에
>   자동 삭제된다. 즉시 지우려면 `~/.claude/hub/events/` 의 파일을 직접 삭제하면 된다
>   (허브는 살아 있는 이벤트 파일을 다시 쓰지 않는다).

### 9.2 개정 — 「자동주입 블록은 기록하지 않는다」 항목

훅이 벗기던 주체가 사라졌으므로 **호스트가 이미 벗겨 남긴다**는 사실로 다시 쓴다(실측 0/30).
화면 단계 방어 필터(`displayableExcerpt`)가 남아 있다는 것도 함께 적는다(PS6).

### 9.3 추가 — 서브에이전트 실행 항목

> - **세션에서 돌았던 서브에이전트가 실행 단위로 보인다.** 호스트가
>   `~/.claude/projects/<인코딩>/<세션ID>/subagents/agent-<id>.meta.json` 에 실행 시작 시점에
>   남기는 파일을, **화면에 실을 실행 건수만큼만**(디렉터리 열거 없이 경로를 조립해) 읽는다.
>   인라인되는 값은 **제목(`description`)·타입·모델 별칭·시작/종료 시각** 뿐이고, 그 에이전트의
>   대화 기록(`agent-<id>.jsonl`)은 **읽지 않는다.** 제목은 사용자 프롬프트에서 파생될 수 있는
>   자유 텍스트라 시크릿 마스킹 + 120자 상한을 거친다. 오프 스위치는 발췌와 같은
>   `record_prompt_excerpt: false` — 끄면 이 파일 자체를 읽지 않고, 실행 줄은 타입만 보이는
>   형태로 남는다.

### 9.4 개정 — 「화면 배치」의 서브에이전트 서술

현행: *"서브에이전트 타입 칩이 최대 2개까지 … 같은 타입은 하나로 합치고 …"*
→ 실행 목록(최대 5줄 + 초과 개수), 단계 칩, 제목, 경과, 툴팁 내용으로 다시 쓴다.
좀비 가드(90분) 문단은 **그대로 유효**하다(술어가 그대로다).

### 9.5 `commands/hub.md` 설치 동의 문구

- 삭제: "프롬프트 앞부분(500자)이 `~/.claude/hub/events/` 에 평문으로 최대 7일 보관됩니다."
- 삭제: "편집기 선택 블록·서브에이전트 알림처럼 CLI 가 자동으로 덧붙이는 내용은 기록하지 않습니다"
  (훅이 기록하는 것 자체가 없어졌다)
- 추가: "세션의 마지막 프롬프트와 서브에이전트 실행 제목이 `~/.claude/hub/hub.html` 평문
  파일에 인라인되어 허브 화면에 표시되며, `record_prompt_excerpt` 플래그로 끌 수 있습니다."
- 워크플로우 문단(400자·label)은 그대로 둔다.

---

## 10. 테스트 계획

### 10.1 순수 로직 단위 테스트

**`tests/hub/test_hub_subagent.py` (신규)**

| 케이스 | 입력 | 기대 |
|---|---|---|
| 정상 | 실측 전문 6키 | `SubagentMeta(title="…", agent_type="Explore", model="haiku", started_at_ms=전달값)` |
| `model` 키 없음(실측 18.7%) | model 제거 | `model is None`, 나머지 정상 |
| `description` 없음 | 키 제거 | `title == ""` |
| 최상위가 객체가 아님 | `"[]"`, `"3"`, `'"x"'` | `None` |
| JSON 구문 오류 | `"{"` | `None` (예외 없음) |
| 4,300자리 초과 정수 리터럴 | `'{"spawnDepth": ' + '9'*5000 + '}'` | `None` (`ValueError` 흡수 — WF 3회차 재현) |
| 깊은 중첩 | `"["*20000` | `None` (`RecursionError` 흡수) |
| `description` 5,000자 | — | `len(title) == 120`, 끝이 `…` |
| `description` 에 시크릿 | `"key sk-ant-AAAAAAAAAA0"` | `[REDACTED]` 포함, 원문 토큰 미포함 |
| **스크럽이 자르기보다 먼저** | 120자 경계에 걸친 시크릿 | 접두사가 남지 않는다 |
| `model` 200자 | — | 32자로 잘림 |
| `agent_type` 이 숫자·None | — | `""` |

**`tests/hub/test_hub_transcript.py` (갱신)**

| 케이스 | 기대 |
|---|---|
| 모델 줄 + `last-prompt` 줄 | 둘 다 채워진다 |
| `last-prompt` 만 | `model is None`, `last_prompt` 채워짐 |
| `last-prompt` 가 여럿 | **마지막 것**이 이긴다 |
| `lastPrompt` 가 문자열이 아님 | `last_prompt is None` |
| 500자 `lastPrompt` | 400자 + `…` |
| `lastPrompt` 에 시크릿 | 마스킹됨 (PS9) |
| 기존 모델 표 전체 | `parse_session_model_from_tail` 이름으로 **전부 그대로 통과** |

**`tests/hub/test_hub_session.py` (갱신)**

| 케이스 | 기대 |
|---|---|
| 같은 타입 3회 실행 | **뷰 3개**(오늘은 1개) |
| 정렬 | 실행 중이 먼저, 그 다음 `started_at_ms` 내림차순, 동률은 `agent_id` 오름차순 |
| 같은 ms 시작 2건 | 두 번 호출해도 순서가 같다(결정성 — D2) |
| 좀비(90분 초과 미종료) | `is_running == False`, `_compute_base_state` 와 같은 판정 |
| meta 없음 | `title is None`·`model is None`, `agent_type`·시각은 훅 값 |
| meta 있고 `SubagentStart` 없음 | `started_at_ms == meta.started_at_ms`(훅 stop 시각이 아니다, AR7) |
| **meta 는 판정 입력이 아니다(AR1 구조 보증)** | `compute_session_view` 결과의 `state`·`base_state`·`agent_runs[0].is_running` 이 meta 유무와 무관하게 동일하고, `agent_runs[0].started_at_ms` 만 갈린다(재검수 1회차 M1 — `build_session_facts` 는 애초 meta 인자를 받지 않아 그 함수로는 이 보증이 검증되지 않았다) |
| 실행 150건 | 뷰 100건(`SUBAGENT_RUN_MAX_PER_SESSION`), 정렬 앞쪽 유지 |
| `task_excerpt` 인자 | 인자로 준 값이 그대로 `SessionView.task_excerpt` 에 실린다 |

**`tests/hub/test_hub_hook.py` (갱신)**

| 케이스 | 기대 |
|---|---|
| `UserPromptSubmit` + 긴 프롬프트 | 기록된 줄에 **`p` 키가 없다** |
| 시크릿 포함 프롬프트 | 이벤트 파일 어디에도 원문이 없다 |
| 나머지 5종 훅 | 오늘과 문자 단위로 같은 줄 |
| `redact_secret_tokens` 재노출 테스트 | `hub_redact` 직접 임포트로 이관(로직은 그대로 회귀 가드로 남긴다) |

**`tests/hub/test_hub_subagent_read.py` (신규)**: 경로 조립 · `observed_cwds` 다중 후보 ·
`session_id`/`agent_id` 에 `/`·`..` · 파일 없음 · 권한 오류(경고 반환) · 크기 상한 초과 ·
`record_prompt_excerpt:false` → 빈 결과 + 파일 접근 0회(`mock` 으로 호출 수 검증).

**`tests/hub/test_hub_collect.py` (갱신)**: `read_session_tail(s)` 개명 · `false` 일 때
`last_prompt` 가 버려지되 `model` 은 살아 있는지.

**`tests/hub/test_hub_model.py` (갱신)**: `snapshot_content_key` 가 **같은 스냅샷에 대해
시간이 흘러도 동일**한지 — `started_at_ms`/`ended_at_ms` 를 넣었어도 파생값이 없음을 고정한다
(D2 회귀 가드).

### 10.2 `tests/run.sh` 계약 검사

| ID | 검사 |
|---|---|
| **T25-205** | `hub_subagent.py`·`hub_subagent_read.py` 존재. 역: `hub_subagent.py` 에 `open(`·`Path(`·`time.`·`os.` 0건(★순수 계약, T25-150 과 같은 기준) |
| **T25-206** | `hub_subagent.py` 의 모든 인라인 문자열 필드가 두 경로 중 하나를 거친다 — `SubagentMeta` 의 `str` 필드 수 == `_scrubbed_and_clipped`/`_metadata_field` 호출 수(계약 A 의 기계적 강제) |
| **T25-207** | `summarize_agent_runs` 본문에 `is_running_subagent(` 호출 ≥1(GOTCHA 4 유지). 역: 본문에 `ended_at_ms is None` 직접 비교 0건 |
| **T25-208** | `summarize_agent_runs` 정렬 키에 실행 중 우선(K2) + `agent_id` 타이브레이커가 있다 |
| **T25-209** | 템플릿에 `MAX_VISIBLE_AGENT_RUNS`·`visibleAgentRunRows`·`renderAgentRunList`·`.agent-run-list{` 가 있고, `shouldRenderSession` 이 `visibleAgentRunRows` 를 경유한다(GOTCHA 3) |
| **T25-210** | 역: 템플릿에 `MAX_VISIBLE_AGENT_CHIPS`·`.agent-runs{` 가 **남아 있지 않다**(AR12 되돌림 방지) |
| **T25-211** | 역: `hub_hook.py` 에 `PROMPT_EXCERPT_MAX_CHARS`·`strip_auto_injected_blocks`·`AUTO_INJECTED_PROMPT_BLOCK`·`"p"` 키가 **0건**. 역의 역: `hub_session.parse_event_line` 에 `"p"` 0건 |
| **T25-212** | `.agent-run>.agent-chip` 규칙에 `flex:0 0 auto` 가 있다(AR8 의 320px 붕괴 방어선 — 지우면 칩이 두 줄로 찢어진다) |
| **T25-120(개정)** | 양방향 태그 대조 → `displayableExcerpt` 존재 + `renderSession` 경유 단방향 검사 |
| **T25-149(개정)** | `HUB_FILE_COUNT == 23`, `hub/README.md` 에 "23개 파일" |
| **T25-100(무변경)** | 새 모듈 포함 `hub/bin/*.py` 전부 800줄 이하 |
| **T25-150(무변경)** | `SessionView` 마지막 필드 = `tier1_is_finished_task` — 이 설계는 필드를 더하지 않으므로 그대로 통과해야 한다 |
| **문서 정합** | README 프라이버시 고지에 "500자" 문자열 0건, `commands/hub.md` 에 "프롬프트 앞부분(500자)" 0건 |

### 10.3 엣지 케이스 체크리스트

- [ ] 빈 입력(실행 0건 세션 → 목록 자체가 렌더되지 않는다)
- [ ] 최대 입력(45건 세션 → 5줄 + "+40건 더")
- [ ] 잘못된 타입(meta 의 모든 필드가 숫자/None)
- [ ] 동시 접근(수집 중 세션이 meta.json 을 새로 쓴다 → 읽기 실패는 경고 1건, 수집은 계속)
- [ ] 권한 거부(`subagents/` 가 읽기 불가 → 그 실행만 강등)
- [ ] 워크트리 이동 세션(`observed_cwds` 2개 중 뒤의 것에 파일이 있다)
- [ ] `record_prompt_excerpt:false`(제목·모델·발췌 없음, 줄과 상태는 유지)
- [ ] transcript 없는 비대화형 세션(발췌·모델 둘 다 없음, 줄 높이 불변)

---

## 11. 단계별 구현 순서 (각 단계의 검증 명령 포함)

검증 명령 정본은 `CLAUDE.md` §4 다. **이 저장소 안에서 `install.sh --scope project` 를 실행하지
않는다. 실제 `$HOME` 을 대상으로 설치하지 않는다.**

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

### Task 1 — `hub_subagent.py` (★순수 파서) + 테스트

- **ACTION**: 새 모듈과 `tests/hub/test_hub_subagent.py` 를 TDD 로 작성.
- **MIRROR**: `hub/bin/hub_workflow.py` 126-205(타입 방어·`_clip_to_length`·`_metadata_field`·
  계약 B 의 `except (ValueError, RecursionError)`).
- **GOTCHA**: `started_at_ms` 는 인자로 받는다 — 이 모듈은 `stat` 을 부를 수 없다(★순수).
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_subagent -v` · `python3 -m py_compile hub/bin/hub_subagent.py`

### Task 2 — `hub_subagent_read.py` (I/O) + 테스트

- **ACTION**: 경로 조립·stat·읽기·세션 순회.
- **MIRROR**: `hub/bin/hub_workflow_read.py` 전체(가드·`errors="replace"`·경고 반환 계약).
- **GOTCHA**: `UnicodeDecodeError` 는 `ValueError` 서브클래스라 `except OSError` 를 뚫는다(GOTCHA 7).
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_subagent_read -v`

### Task 3 — `hub_transcript.py` 에 `last-prompt` (요구 2의 읽기 쪽)

- **ACTION**: `SessionTail`·`parse_session_tail`·`LAST_PROMPT_MAX_CHARS`·`hub_redact` 임포트.
  `parse_session_model_from_tail` 은 위임 함수로 남긴다.
- **GOTCHA**: 스캔은 1회, 둘 다 찾으면 조기 종료. redact → clip 순서.
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_transcript -v` (기존 표가 전부 통과해야 한다)

### Task 4 — 서버 배선: `hub_session` · `hub_collect` · `hub_project`

- **ACTION**: `SubagentRunView` 확장, `summarize_agent_runs` 실행 단위화, `task_excerpt` 인자화,
  `read_session_tail(s)` 개명, `collect_snapshot` 에 meta 읽기 추가, `compose_project_views` 인자 교체.
- **GOTCHA**: `SessionFacts` 에 meta 를 되먹이지 않는다(AR7). `SessionView` 필드 순서 불변(T25-150).
- **VALIDATE**: `python3 -m unittest discover -s tests/hub -t .` · `python3 -m py_compile hub/bin/*.py`

### Task 5 — 훅에서 `p` 제거 (요구 2의 쓰기 쪽)

- **ACTION**: §PS4 표의 7개 항목 삭제. `hub_hook.py` 약 55줄 감소.
- **GOTCHA**: `hub_redact.py` 자체는 지우지 않는다(`hub_workflow`·`hub_subagent` 가 쓴다).
  `UserPromptSubmit` 훅 **설치**는 그대로 남긴다(`turn_state`).
- **VALIDATE**: `python3 -m unittest tests.hub.test_hub_hook -v`

### Task 6 — 템플릿 (렌더 + CSS)

- **ACTION**: §7 전체. 첫 줄 칩 행 제거, 실행 목록 추가, `shouldRenderSession` 경유 교체.
- **GOTCHA**: `.agent-run>.agent-chip{flex:0 0 auto}` 를 빠뜨리면 320px 에서 칩이 두 줄로
  찢어진다(목업 1차 실측).
- **VALIDATE**: 실데이터로 렌더 후 헤드리스 대조 —
  `python3 hub/bin/hub.py collect` 는 **실제 `$HOME` 을 건드리므로 쓰지 않는다.**
  대신 `tests/hub/fixtures` 의 스냅샷으로 `hub_model.render_hub_html` 을 호출해 임시 파일로
  쓰고, `--headless --screenshot` 으로 320px·1280px 두 폭을 찍어 목업과 대조한다.

### Task 7 — 문서·계약 검사

- **ACTION**: §9 문서 개정, §10.2 의 T25-205~212 신설, T25-120·T25-149 개정,
  `hub/install.sh` `HUB_FILE_COUNT=23`, `rules/python/coding-style.md` 예시 교체.
- **VALIDATE**: `bash tests/run.sh` · `bash -n install.sh && bash -n hub/install.sh`

### Task 8 (선택 — 사용자가 토큰을 원할 때만) — 실행별 토큰

- **ACTION**: `hub_subagent_read` 에 agent jsonl 꼬리 128KiB 읽기 추가, `usage` 최댓값 집계,
  `SubagentRunView.input_tokens_max` 추가, 툴팁에만 표시.
- **GOTCHA**: 전 턴 합산 금지(`cache_read` 누적), "마지막 턴" 금지(3%가 0k 로 무너진다) —
  **최댓값**. 꼬리 최댓값 == 전체 최댓값은 222/222 검증됐다.
- **VALIDATE**: 위와 동일 + collect 시간이 50ms 를 넘지 않는지 계측.

### 전체 검증 (모든 Task 후)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

---

## 12. 리스크와 대안

| # | 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|---|
| R1 | 호스트가 `subagents/*.meta.json` 형식·경로를 바꾼다 | 중 | 제목·모델이 사라진다 | 계약이 `hub_subagent.py` 한 파일에 갇혀 있다(AR2). 줄은 `agent_type` 폴백으로 남고(AR9) **카드 상태는 전혀 영향받지 않는다**(AR1) |
| R2 | 호스트가 `last-prompt` 를 안 남기기 시작한다 | 중 | 발췌가 **전면 실종**된다(폴백을 없앴으므로) | 30/30 보유가 근거지만 보증은 아니다. 발견 즉시 알 수 있게 `collect_snapshot` 이 "발췌를 가진 세션 0개"를 warnings 로 남길지는 §13-③ 판단 항목 |
| R3 | 호스트가 `lastPrompt` 에 자동주입 블록을 넣기 시작한다 | 낮 | 선택한 소스코드가 `hub.html` 평문에 인라인 | `displayableExcerpt` 를 남긴다(PS6) — 태그로 시작하는 발췌를 화면에서 통째로 숨긴다 |
| R4 | 세션에 45건 실행이 쌓여 카드가 스크롤만 남는다 | 중 | 스캔 가치 하락 | 표시 상한 5 + 개수 줄(AR11). 카드 높이 340px 는 불변이라 레이아웃은 안 깨진다 |
| R5 | meta 읽기가 collect 를 느리게 한다 | 낮 | 페이지 응답 지연 | 조립 경로라 읽는 수 = 화면에 실을 수(§2: 1~8ms). 서버 상한 100건으로 선형 고정 |
| R6 | `p` 제거 후 옛 이벤트 파일에 프롬프트가 남아 있다 | **확실** | 최대 7일 평문 잔존 | 리텐션으로 자연 소멸 + README 에 즉시 삭제 방법 명시(PS5·§9.1) |
| R7 | 첫 줄 칩 제거로 "완료 세션이 칩 때문에 보이던" 줄이 사라진다 | 중 | 화면에서 세션이 조용히 준다 | `shouldRenderSession` 이 `visibleAgentRunRows` 를 경유하므로 **실행 목록이 있으면 줄도 남는다** — 판정 입력이 칩에서 목록으로 바뀔 뿐 의미는 같다. T25-209 가 이 경유를 문다 |

### 검토했으나 채택하지 않은 대안

**대안 1 — `subagents/` 디렉터리를 glob 해서 실행을 발견한다 (기각).**
훅 이벤트 없이도 실행을 찾을 수 있고 중첩(depth 2)까지 보인다. 그러나 최악 디렉터리에서
glob 17ms + 전건 파싱 37ms 를 매 수집마다 치르고, 그 대부분이 이벤트 창(오늘+어제) 밖
실행이다 — **읽는 비용이 화면에 실을 양과 무관해진다.** 조립 경로는 그 둘을 같게 만든다.
얻는 것(중첩 3.7%)이 잃는 것(정상 부하 6배)보다 작다.

**대안 2 — 부모 세션 transcript 에서 `Agent` tool_use / `tool_result` 로 상태를 판정한다 (기각).**
이론상 가장 정확하다(`toolUseId` 가 meta.json 에 있다). 그러나 부모 transcript 는 최대 91MB 고
허브는 구조적으로 꼬리 128KiB 만 읽는다 — 세션 초반의 `Agent` 호출은 꼬리에 없다. 전수 스캔은
논외다. 지금의 훅 + 90분 좀비 가드는 **이미 운영 중이고 검증된** 판정기이며, 실패 모드
(`SubagentStop` 미발화)도 이미 문서화돼 있다(hub/README.md 「알려진 한계」).

**대안 3 — 발췌를 transcript 로 옮기되 훅의 `p` 를 폴백으로 남긴다 (기각).**
가장 안전해 보이지만 프라이버시 개선이 **반만 참**이 된다("사본은 계속 만들되 보통은 안 읽는다").
게다가 `last-prompt` 보유율이 30/30 이라 폴백이 발동할 경로가 실측상 없다 — 쓰이지 않는 코드
경로에 프라이버시 부채를 매달아 두는 셈이다.

**대안 4 — 실행 목록을 상세 패널로 보낸다 (기각).**
카드 높이 걱정이 사라진다. 그러나 패널은 대시보드 iframe 전용이고(오늘 계약), 요구는
"**카드에서** 보고 싶다"다 — 창을 열지 않고 아는 것이 허브의 존재 이유다.

---

## 13. 사용자 판단이 필요한 항목

① **토큰을 넣을 것인가** — 기술적으로 가능하다(꼬리 128KiB, collect 당 +3~24ms, 꼬리 최댓값 =
전체 최댓값 222/222 검증). 넣지 않기로 한 이유는 비용이 아니라 **320px 줄에 자리가 없어서**다.
넣는다면 위치는 툴팁이고 Task 8 로 분리돼 있다.

② **표시안 A(실행 목록) vs B(실행 칩)** — 목업 3열 대조가 있다. A 는 제목이 화면에 보이고
세션 하나가 약 3줄 높아진다(카드에 세션 1~2개). B 는 높이가 거의 그대로지만 제목·경과가
툴팁에만 있다(카드에 세션 2~3개). **권고는 A** — 요구의 핵심("무엇을 시켰는가")이 A 에서만
화면에 나온다.

③ **발췌 실종 감지 경고를 둘 것인가** — `last-prompt` 를 가진 세션이 0개면 `warnings` 에
1건 남길지(R2). 오탐 가능성(전부 비대화형 세션인 날)이 있어 기본은 **두지 않음**으로 설계했다.

---

## 14. 완료 기준

- [ ] §11 의 Task 1~7 완료(Task 8 은 ①의 결정에 따름)
- [ ] `bash tests/run.sh` 전체 통과 (T25-205~212 신설 포함)
- [ ] `python3 -m unittest discover -s tests/hub -t .` 통과
- [ ] `python3 -m unittest discover -s tests/commands -t .` 통과
- [ ] `python3 -m py_compile hub/bin/*.py` 통과
- [ ] `bash -n install.sh && bash -n hub/install.sh` 통과
- [ ] `hub_subagent.py` 가 ★순수(파일시스템 접근 0건), `hub/bin/*.py` 전부 800줄 이하
- [ ] `hub_hook.py` 에 프롬프트 관련 심볼 0건, `events/*.jsonl` 새 줄에 `p` 키 0건
- [ ] `hub/README.md`·`commands/hub.md` 에 "500자" 프롬프트 보관 서술 0건
- [ ] 320px·1280px 두 폭의 렌더 결과가 목업과 일치(칩 줄바꿈 0건)
