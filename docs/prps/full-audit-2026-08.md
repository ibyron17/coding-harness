# 전수검사 보고 — 공식 Claude 문서 대조 감사 (2026-08-28)

> **이 문서는 PRP(설계 문서)가 아니라 실측 감사 보고서다.**
> 수정 설계는 별도 PRP(`audit-remediation.md`)가 담고, 이 문서는 그 입력이 되는 근거 기록이다.
> 선례로 인용할 때는 「지적」과 「검증 판정」을 함께 본다 — 폐기된 지적 4건이 §5 에 있다.

## 0. 결론

| 축 | 결과 |
|---|---|
| 원시 발견 | 95건 |
| 적대적 검증 폐기 | 4건 (§5) |
| **생존** | **91건 — MAJOR 14 · MINOR 48 · INFO 29** |
| 감사 자원 | 서브에이전트 27개 · 4.8M 토큰 · 640 도구 호출 |
| 소요 | 2026-08-28, 세션 사용량 한도 2회 도달(캐시 재개로 복구) |

핵심 판정 5개.

1. **`rules/` 조건부 로딩은 실재하는 공식 기능이다.** `paths` frontmatter, `~/.claude/rules/`, "매칭 파일을 읽을 때 발동", 글롭 문법이 모두 공식 문서 원문과 일치한다. 37개가 죽은 스캐폴딩일 가능성은 배제됐다. (감사 중 실증됐다 — `.claude/dashboard.html` 편집이 `rules/web/*` 를 메인 세션 컨텍스트로 실제로 끌어왔다.)
2. **배포되는 규칙 3곳이 사실과 다른 것을 가르친다** — MAJOR. 훅 JSON 스키마(6블록), React Native 디렉토리 부재 서술, `/effort` 지속성.
3. **`hub/` 런타임에 조용한 오작동 2건이 있다** — MAJOR. 폴링 예외로 백오프 상태가 유실되고, 하트비트 TTL 여유가 0이다.
4. **생산자·소비자 계약 문서가 계약을 반대로 서술한다** — MAJOR. 그리고 그 계약을 고정하는 테스트가 정·역 모두 없다.
5. **공개 배포물로서의 메타데이터가 비어 있다** — MAJOR. `LICENSE` 부재, 상류 출처 표기 전무, `python3 3.10+` 요구가 두 README 어디에도 없음.

**저장소 정체는 「공개 배포물」로 확정됐다**(사용자 결정, 2026-08-28). 주 사용자는 팀원이지만 저장소를 공개로 두므로 **모든 사용자가 클론한다는 것을 전제**한다. 이 결정이 5건의 심각도를 정했다(§4).

## 1. 방법론

9개 렌즈를 병렬로 돌리고, 각 렌즈의 지적을 **반박을 전제로 한** 독립 검증자에게 넘겼다. 그 뒤 완전성 비평가가 미커버 영역을 지목하고, 그 과제로 보충 6라운드를 돌렸다.

```
감사 9렌즈 (fable)  →  렌즈별 적대적 검증 (opus)  →  완전성 비평 (opus)
                                                    →  보충 6라운드 (opus)  →  종합
```

**렌즈 배정**: `agents`(에이전트 규격) · `commands-skills`(커맨드/스킬 규격) · `hooks`(훅 규격) · `memory-rules`(CLAUDE.md·rules 로딩) · `model-facts`(모델·effort·설정 사실성) · `coherence`(내부 정합성) · `shell`(설치 스크립트) · `python`(hub 코드) · `tests`(테스트 신뢰성). 보충 6: `keychain-oauth-network-path` · `python-unittest-suite-content` · `stack-rule-content-25-files` · `two-root-link-and-cwd-integrity` · `dashboard-producer-consumer-contract` · `public-artifact-hygiene`.

**규칙**: 모든 지적에 (a) 실제로 읽은 파일의 인용된 줄과 (b) WebFetch 로 확인한 공식 문서 URL·원문을 요구했다. 문서 URL 발명 금지, 도메인 차단 시 `fetched=false` 기록 후 확신도 하향. `docs/prps/` 를 먼저 grep 해 **문서화된 의도적 결정을 결함으로 신고하지 않도록** 했다 — 폐기된 4건 중 3건이 이 규칙으로 걸러졌다.

**미실행**: `install.sh` · `hub/install.sh` · `tests/run.sh` 는 사용자 `~/.claude` 에 쓰므로 실행하지 않고 읽어서 판정했다. `tests/hub` pytest 와 `hub_parse` import 는 읽기 전용이라 실행했다.

## 2. 확정 MAJOR 14건

### A. 배포되는 규칙이 틀린 것을 가르친다

#### A-1. `rules/web/hooks.md` — 훅 JSON 예제 **6블록 전부** 무효 스키마

공식 규격은 3단 중첩(이벤트 → matcher 그룹 → 그룹 안 `hooks` 배열의 `{type:"command", command}`)을 요구한다. 이 파일의 6블록은 matcher 그룹에 `command`·`description` 을 직접 놓고 `hooks` 배열과 `type` 을 생략한다 — **핸들러 없는 matcher 그룹이라 훅이 실행되지 않고, 실패가 에러로 드러나지 않는다.** 사용자는 포맷·린트·타입체크가 돌고 있다고 믿는다.

기계 판정 결과(`json.loads` 후 스키마 검사):

| 줄 | 이벤트 | 키 | 판정 |
|---|---|---|---|
| 25 | PostToolUse | matcher, command, description | 무효 |
| 43 | PostToolUse | matcher, command, description | 무효 |
| 61 | PostToolUse | matcher, command, description | 무효 |
| 84 | PostToolUse | matcher, command, description | 무효 |
| 104 | PreToolUse | matcher, command, description | 무효 |
| 122 | Stop | command, description | 무효 |

두 번째 결함이 겹친다: `$FILE_PATH`(31·49·90행)는 **존재하지 않는 변수**다. 훅에 주어지는 것은 stdin JSON(`tool_input.file_path`)과 `${CLAUDE_PROJECT_DIR}` 계열뿐이다. 중첩을 고쳐도 `prettier --write ""` 가 된다.

- **규격**: <https://code.claude.com/docs/en/hooks> — matcher 객체에 `command` 를 직접 두는 형태를 명시적으로 무효로 표기한다.
- **저장소 자체 표준과의 이탈**: `hub/bin/hub_settings.py:75` 의 `_hub_hook_entry()` 는 `{"hooks":[{"type":"command","command":...}]}` 를 정확히 반환하고, `docs/prps/hub-dashboard.md:416` 은 "`type` 은 반드시 `command` 다 — `type:"http"` 는 v2.1.108 에서 발동하지 않음이 **실측**됐다"까지 기록했다. 실측으로 확인한 사실이 배포 규칙에 반영되지 않았다.
- **권고**: 6블록을 `{"matcher":"Write|Edit","hooks":[{"type":"command","command":"..."}]}` 로 고친다(Stop 은 matcher 없이). `description` 은 JSON 밖 산문으로 옮긴다. `$FILE_PATH` 를 stdin 파싱으로 대체한다. `_hub_hook_entry()` 를 정답 참조로 파일 안에 링크해 재발을 막는다.

> **선행 감사의 정정**: 보충 렌즈는 이를 5블록으로 셌다. `PreToolUse`(104) 블록을 "stdin 계약을 올바르게 쓴 대조 사례"로 분류했기 때문인데, 그 블록은 stdin 처리만 옳고 **JSON 형태는 똑같이 무효**다. `Stop`(122)도 누락됐다. 정확한 수는 6이다.

#### A-2. `rules/react/patterns.md:189` — 존재하는 디렉토리를 없다고 단정

> `- Treated as a separate track — \`rules/react-native/\` is not yet present`

`rules/react-native/` 에는 8개 파일이 있고 전부 `paths: ["**/*.ts","**/*.tsx"]` 를 선언한다. `react/patterns.md` 도 `**/*.tsx` 를 선언한다 — **임의의 `.tsx` 를 열면 두 파일이 같은 컨텍스트에 나란히 들어온다.** 즉 지금 함께 로드된 8개 파일을 없다고 말하는 오정보다. 그 8개가 정확히 이 문장이 없다고 한 주제를 다룬다(`coding-style.md:36` Platform Differences, `:22` StyleSheet, `patterns.md:13` Expo Router).

- **규격**: <https://code.claude.com/docs/en/memory> — "if two rules contradict each other, Claude may pick one arbitrarily" 이며 `.claude/rules/` 를 주기적으로 점검해 outdated·conflicting 지시를 제거하라고 명시한다.
- **권고**: 186-190행의 RN 절을 `../react-native/` 로 향하는 포인터로 대체한다. 구조적 재발 방지: 「배포 트리에 대해 단정하는 문장」을 rules 본문에 두지 않고 `rules/README.md` 한 곳으로 모으거나, `tests/run.sh` 에 "`rules/<dir>/ is not yet present` 류를 주장하면 그 디렉토리가 실제로 없어야 한다"는 어서션을 추가한다.

#### A-3. `rules/common/performance.md:79` — `/effort` 지속성을 거꾸로 적었다

"Per-session: `/effort`, `/model` 슬라이더, `--effort`" 로 분류했다. 공식 문서는 `low·medium·high·xhigh` 를 **대화형 세션에서 설정하면 세션 간 지속된다**고 명시한다. 세션 한정은 `--effort` 플래그와 비대화형(`-p`) `/effort` 뿐이다.

- **규격**: <https://code.claude.com/docs/en/model-config> — "`low`, `medium`, `high`, and `xhigh` persist across sessions when you set them in an interactive session."
- **피해**: 상시 로드 파일이라 다음 세션이 사용자에게 "이 세션에만 적용된다"고 답하거나, 일시적일 줄 알고 낮춘 effort 가 이후 모든 세션에 조용히 남는다.
- **권고**: 지속/세션 한정 분류를 문서대로 수정한다. `/model` 슬라이더는 문서가 지속 여부를 명시하지 않으므로 단정하지 않는다.

### B. hub 런타임의 조용한 오작동

#### B-1. `hub_server.py:353` — 예외 1회로 Keychain·OAuth 호출이 5초마다 영구 반복

`_run_usage_api_poll_cycle` 에 자기 예외 경계가 없고, 유일한 경계는 호출자 `_maintenance_loop:357` 의 `except Exception` 이다. 거기서 잡히면 `usage_api_poll_state = _run_usage_api_poll_cycle(...)` **대입문 자체가 성립하지 않아** `last_attempt_at_ms` 가 영구히 갱신되지 않는다. 결과: `should_attempt_usage_api_poll` 이 매 틱 True → 하트비트 주기(기본 5초)마다 Keychain subprocess 1회 + OAuth 토큰을 실은 원격 호출 1회 = **시간당 720회**. 결정 A3 의 지수 백오프와 429 상한이 이 실패 등급에서 전혀 작동하지 않는다.

관측 가능성도 함께 무너진다 — `record_usage_api_failure` 를 건너뛰므로 `/hub status` 의 `usage_api_last_failure` 는 비어 있고, 흔적은 `server.log` 에 5초 간격 한 줄씩만 쌓인다(런타임 중 잘라내기 없음 — `_truncate_log_if_oversized` 는 `run_server` 시작 시 1회다).

**발동 트리거는 실재한다**: `clear_usage_api_failure()` 의 `unlink` OSError, 캡처 쓰기 실패, 그리고 `hub_usage_fetch.py:138·140` 의 파싱 2줄이 try **밖**에 있어 깊은 중첩 응답의 `RecursionError` 가 그대로 빠져나간다.

- **저장소가 이미 푼 문제다**: 같은 파일의 `_collect_once`(:266-275)는 `finally: self._last_attempt_at_monotonic_ms = _monotonic_ms()` 와 "**실패해도 시각을 갱신한다.**" 주석을 갖고 있다. 요청 경로에만 적용됐다.
- **권고**: `_collect_once` 형태를 옮긴다 — fetch 이후 구간을 `try/finally` 로 감싸 **어떤 경로로 끝나도** 시도 시각을 남기고 상태를 반환한다. 함께: 파싱 2줄을 `hub_usage_fetch.py:119-136` 의 try 안으로 옮기고, `parse_usage_api_response`·`describe_json_key_structure` 의 except 에 `RecursionError` 를 추가한다. 테스트는 `fetch_rate_limit_capture` 를 mock 하지 않고 3,000단 중첩 본문을 태워 상태 반환을 단정한다(현재 `test_hub_server.py` 의 3개 테스트는 모두 fetch 를 mock 해 이 경로를 덮지 못한다).

#### B-2. `hub_server.py:335` — 하트비트 TTL 15초 = 최악 블로킹 15초, 여유 0

docstring 이 "사이클 앞에 한 번 찍어야 외부 관찰자가 일하는 서버를 죽었다고 오판하지 않는다"고 단정한다. 산술이 맞지 않는다.

```
TTL      = max(5 × 3, 15) = 15초        hub_server_state.py:71-72, hub_model.py:39
최악 블로킹 = HTTP 10 + Keychain 5 = 15초  hub_usage_fetch.py:24-25 (docstring 이 스스로 명시)
is_server_alive = (나이 < TTL)          ← 정확히 15초면 이미 사망 판정
```

같은 사이클 앞쪽의 배경 상한 수집(5분마다 프로젝트 전수 스캔)이 얹히면 초과가 확정되고, `urlopen` 의 timeout 은 전체 시간이 아니라 소켓 연산별 상한이라 최악값은 15초를 넘는다.

- **피해 2가지**: (1) `/hub status` 가 `server_alive:false` + `maintenance_stalled:true` + `log_tail` 로 **존재하지 않는 크래시를 보고**한다 — 사람이든 다음 세션이든 없는 사고를 추적한다. (2) 훅 폴백이 서버를 죽은 것으로 보고 `hub.py collect` 를 분리 프로세스로 spawn 한다(5초 쓰로틀이라 스톨 1회당 최대 3개).
- **권고**: (a) 폴링을 티커 사이클에서 빼내 자기 스레드로 옮긴다 — 하트비트 주기와 원격 호출 지연이 무관해져 이 산술이 사라진다. 또는 (b) `SERVER_HEARTBEAT_MIN_TTL_SECONDS ≥ FETCH_TIMEOUT_SECONDS + KEYCHAIN_TIMEOUT_SECONDS + 여유`. 어느 쪽이든 그 관계를 테스트로 고정하고 docstring 의 단정문을 실제 보장 범위에 맞춘다.

### C. 생산자·소비자 계약

#### C-1. `commands/dashboard.md:116-117` — 허브 파서 계약을 사실과 반대로 서술

생산자 문서가 소비자(`/hub`)를 언급하는 **유일한 지점**이고, 두 줄의 주장 둘 다 실측과 반대다. 측정 방법: `hub_parse` 를 import 해 실제 정규식에 문자열을 태웠다.

| 문서의 주장 | 실측 |
|---|---|
| 불변식 2(1줄 1개)를 깨면 파서가 깨진다 | **거짓.** 한 줄에 `<li id="dz-step-1">`·`<li id="dz-step-2">` 를 나란히 넣어도 `steps=2`. 패턴에 줄 앵커가 없고 `finditer` 가 둘 다 찾는다 |
| 조용히 **티어를 강등**한다 | **거짓.** 속성 순서 역전·줄 분할 3종 모두 `None` 이 아니라 정상 `Tier1Snapshot` 을 반환한다. `hub_parse.py:117-118` 의 `None` 은 title·progress·updated 셋이 모두 실패할 때만이다 |
| (문서에 없는 진짜 제약) | **속성 순서와 공백 1칸이 계약이다.** `<li class="active" id="dz-step-1">` → NOMATCH · 공백 2칸 → NOMATCH · `class="active step"` → NOMATCH · `<td id="dz-cell-1-1" class="cell" …>` → NOMATCH |

실제 실패 양상은 강등이 아니라 **부분 침묵**이다. 실물 파일에서 `id`↔`class` 순서만 뒤집으면 `steps=0` 인데 진행률 줄은 멀쩡히 렌더되고(`hub_template.html:1254-1255`), 사라지는 것은 활성 단계 줄 하나뿐이다(`renderTier1ActiveStep` 이 `if(!activeStep) return ''`). 경고도 티어 배지 변화도 없다.

- **왜 무거운가**: 이 계약의 생산자는 코드가 아니라 **이 산문을 읽는 LLM** 이다. 그 LLM 은 소비자에게 무해한 규칙을 "파서가 깨진다"는 근거로 지키라고 듣고, 정작 파서를 깨뜨리는 규칙은 듣지 못한다. 진단 방향도 오염된다 — 허브에서 단계 줄이 사라졌을 때 다음 세션은 문서가 지목한 "1줄 1개"와 "티어 강등"을 먼저 의심하고, 둘 다 정상인 것을 확인하고 길을 잃는다.
- **권고**: ① 파서가 요구하는 것은 "1줄 1개"가 아니라 "요소 하나가 한 줄 안에 온전히"(= 불변식 3)임을 명확히 하고, 불변식 2·5 는 `grep -c` 감사 명령의 전제로만 남긴다. ② **정규 속성 순서를 계약으로 명시**한다 — `<li id="dz-step-{n}" class="{state}">`, `<td class="cell" id="dz-cell-{g}-{p}" data-state="{state}">`, 구분은 공백 정확히 1칸. `step` 절차 1단계가 줄을 재작성하므로 그 절에도 넣는다. ③ "티어를 강등한다"를 "그 요소가 허브에서 조용히 사라진다(티어는 1로 유지되고 경고도 없다)"로 고친다.

#### C-2. 생산자 예시와 파서 정규식을 잇는 테스트가 정방향·역방향 모두 없다

파서 테스트는 정적 픽스처 5개만 읽고 `commands/dashboard.md` 를 열지 않는다. 생산자 쪽 `run.sh` 테스트는 전부 헐거운 부분문자열 확인(`grep -q 'dz-step-{n}'` 류)이라 속성 순서를 고정하지 못한다. 가장 아픈 것은 **T25-6** 이다 — 스스로를 "티어 1 파서의 전제"라고 선언하면서 검사하는 것은 불변식 **산문 문장**이다(`tests/run.sh:2664-2665`).

**실증**: `dashboard.md:555` 예시의 `id`↔`class` 순서만 뒤집으면 허브의 활성 단계 줄이 죽는데, T22-2·T22-24·T25-6 이 전부 통과하고 `test_hub_parse.py` 는 **20/20 green** 이다.

- **저장소는 이 패턴을 이미 안다**: `#dz-log` 행에는 T22-80 이 있고 그 PRP 는 "각인 슬롯 유실 **및** 속성 순서 역전(T22-11 파손). 한 줄로 둘을 동시에 고정한다"(`dashboard-auto-stop-on-commit.md:427`)고 적었다. 그 장치가 `#dz-step`·`#dz-impl`·`#dz-cell` 3종에는 적용되지 않았다.
- **권고**: 픽스처를 늘리지 말고 두 끝을 직접 잇는 테스트를 `tests/hub/` 에 1파일 추가한다. **정방향** — `dashboard.md` 에서 `<li id="dz-step-`·`<li id="dz-impl-`·`<td class="cell" id="dz-cell-` 로 시작하는 예시 줄을 추출해 `hub_parse` 의 해당 패턴에 태워 전부 MATCH 를 요구(추출 건수 > 0 도 함께 단정 — 앵커가 사라져 0건이 되면 공허하게 통과한다). **역방향** — 각 줄의 `id`/`class` 순서를 뒤집은 변형에 NOMATCH 를 요구(정규식이 헐거워지는 반대 방향 퇴행도 잡는다). 이 테스트는 `hub_parse` 를 import 하므로 픽스처처럼 함께 드리프트할 수 없다.
- **우선순위 정보**: `matrix_done` 과 `StepView.started_at` 은 파싱되지만 **렌더 소비자가 없다**(`hub_template.html` 에 `matrix` 문자열 자체가 없다). 따라서 매트릭스 모드 드리프트는 오늘 사용자에게 보이지 않는다 — 역방향 테스트를 하나만 넣는다면 **선형·impl 을 먼저** 덮어야 한다.

### D. 컨텍스트 비용

#### D-1. `commands/dashboard.md` — 호출마다 ~37k 토큰이 다시 쌓인다

공식 규격: 스킬 재호출 시 렌더된 내용이 **동일할 때만** 중복 주입이 생략되고, 인자가 바뀌면 전문이 다시 덧붙는다. `dashboard.md` 는 87,305바이트(1,315줄)이고 `CLAUDE.md:103-104` 는 "착수 시 `init`, 단계 전환과 서브에이전트 디스패치·결과 수령 시점마다 `step`·`log`" 를 명령한다 — 매번 다른 인자다. 전체 경로 1건(init 1 + step/log 6~10회)이면 주입만 26만~44만 토큰이다.

- **규격**: <https://code.claude.com/docs/en/skills> — "When the rendered content differs, because the arguments changed …, Claude Code appends the full content again." / compaction 재부착은 스킬당 첫 5,000토큰·합산 25,000토큰 / "Keep SKILL.md under 500 lines."
- **승인의 전제가 규격과 달랐다**: `dashboard-md-slimming.md` 는 "주입된 뒤에는 매 턴 cache read 로 재청구되며"라는 **1회 주입** 비용 모델로 크기를 승인했다. 규격의 호출당 재주입 곱셈이 그 모델에 없었다.
- **권고**: `CLAUDE.md` 트리거를 "세션 최초 1회만 `Skill` 호출, 이후 `step`/`log` 는 이미 컨텍스트에 있는 절차를 상비 지침으로 직접 수행"으로 고친다 — 규격 자체가 스킬 내용을 standing instructions 로 쓰라고 안내하고, `dashboard.md` 는 이미 전 서브커맨드 절차를 담고 있다. **이 감사 세션이 실증이다**: `Skill(dashboard)` 를 init 때 1회만 부르고 이후 갱신은 절차를 직접 수행해 정상 동작했다. 대안으로 슬리밍 PRP §13 에서 기각했던 서브커맨드 파일 분리(주입 −83%)를 재평가한다.

### E. 안전망 부재

#### E-1. `hub_settings.py` 의 settings.json 쓰기 경로에 테스트 0건

사용자의 `~/.claude/settings.json` 을 통째로 다시 쓰는 저장소의 유일한 코드다. PRP 리스크 7「settings.json 손상」의 완화책 3개 중 검증이 붙은 것은 1개뿐이다.

| 완화책 (`hub-dashboard.md:910`) | 테스트 |
|---|---|
| 파싱 실패 시 손대지 않고 중단 | `SETTINGS_PARSE_ERROR` 참조 **0건**(`tests/` 전체) |
| 타임스탬프 백업 | `settings.json.bak` 검사 **0건** |
| `os.replace` 원자적 교체 | 파일 모드 보존 1항목만 |

`install_hooks`/`uninstall_hooks` 는 `tests/hub` 에서 **이름조차 나오지 않는다**. 덮인 것은 순수 함수 `merge_hub_hooks`/`strip_hub_hooks` 뿐이다.

- **저장소가 기준을 이미 세웠다**: `test_hub_settings.py:239-242` 는 statusline 쪽에 대해 "자체 `statusline_owner` 검사로 단락하므로 순수 함수 테스트만으로는 이 기능의 최대 안전 주장을 보증하지 못한다"고 **명시하고** 전용 I/O 테스트 2개를 붙였다. `install_hooks` 는 구조가 동일하고 더 위험한데(6개 이벤트 배열 vs 단일 키) 그 기준이 적용되지 않았다.
- **권고**: statusline 과 대칭인 I/O 테스트 3개. (a) 깨진 JSON 을 쓴 뒤 `install_hooks()`·`uninstall_hooks()` 를 부르고 `ok is False`·`reason == SETTINGS_PARSE_ERROR` 와 함께 **파일 바이트가 한 글자도 안 바뀌었음**을 확인. (b) 정상 파일로 부른 뒤 `settings.json.bak-*` 가 정확히 1개 생기고 원본과 바이트 동일한지. (c) 이미 설치된 상태에서 다시 부르면 `installed == []` 이고 **백업이 새로 생기지 않는지**(현재 멱등성 테스트는 순수 dict 수준이라 이 성질을 못 잡는다).

### F. 공개 배포물 메타데이터

#### F-1. `LICENSE` 부재

`LICENSE`·`COPYING`·`NOTICE` 가 공집합인데 `origin` 은 공개 저장소이고 `README.md:31-33` 이 clone 을 지시하며 `commands/harness-update.md` 는 그 원격에서 pull 하도록 설계됐다. 저작권 기본값은 "명시적 허가 없음 = 모든 권리 유보"이므로 **실질적 결과는 제3자에게 복제·수정·재배포 권한이 없다**는 것이다.

더 오도적인 것은 **「## 라이선스」 제목이 존재하는데 라이선스가 없다**는 점이다(`README.md:342-344`, 본문은 "사용자 개인 워크플로우 패키징이다" 한 줄). 제목만 보고 스크롤한 사람은 조건이 명시됐다고 읽고, 빈 라이선스 절은 "제한 없음"으로 오독되지만 법적 기본값은 그 반대다.

- **법률 자문이 아니다.** 선택지만 적는다: (a) 허용형(MIT/ISC/Apache-2.0) — 현재 README 안내와 정합. (b) 배포 제한 명시 — 이 경우 clone 안내와 공개 origin 을 함께 조정해야 한다. (c) 어느 쪽이든 `LICENSE` 1개 + 「## 라이선스」 절에 그 파일을 가리키는 한 줄.
- **선행 조건**: **F-2 의 상류 출처 확정이 라이선스 선택보다 앞선다.** 모르는 원 라이선스 위에 허용형을 붙이면 부여할 수 없는 권한을 부여한다.

#### F-2. 상류 출처·저작자 표기가 전무한데 파생 흔적은 6개 파일에 남아 있다

전수 grep 결과 상류 출처·저작자·저작권 표기가 **한 건도 없다**(`출처` 매칭 40여 건은 전부 "단일 출처(single source of truth)"라는 무관한 용법). 반면 `ECC`(Everything Claude Code)를 **자기 것이 아닌 외부 체계로 지칭하는 문장**이 6개 파일에 있다.

```
rules/common/git-workflow.md:12            … ECC does not ship this setting).
rules/react-native/production-readiness.md:8   > Extends the ECC philosophy to ship-grade concerns …
rules/react-native/hooks.md:28             … consistent with ECC hook runtime controls (ECC_HOOK_PROFILE, …).
rules/web/design-quality.md:53             5. Use ECC design/frontend skills where relevant.
commands/prp-prd.md:433                    ## Integration with ECC
docs/prps/coding-harness.md:249            ### (a) rules/ 는 zh/ 를 제외한 79개 전량 배포
```

즉 제3자 저작물을 큐레이션한 파생물인데 `README.md:344` 는 "사용자 개인 워크플로우 패키징이다"로 서술한다. `agents/`(4개)·`commands/`(10개)에도 출처 표기가 없고, **어느 파일이 원저작이고 어느 것이 파생인지 저장소에서 판별할 근거가 없다** — 이것이 지적의 핵심이다.

- **권고**: 루트에 `NOTICE.md`(또는 README 「## 라이선스」 절 확장)를 두고 ① 상류 프로젝트명·URL ② 그 프로젝트의 라이선스 ③ 이 저장소가 한 변경(79→37 큐레이션, 한국어화, 워크플로우 재구성)을 각 한 줄로 적는다. `docs/prps/coding-harness.md` 의 79 는 37 로 갱신하거나 상류 원본 수라는 각주를 붙인다.
- **한계**: 상류 프로젝트의 정체는 이 저장소만으로 확정할 수 없었다. `ECC` 약칭과 79개라는 규모가 흔적으로 남아 있을 뿐이다. **그 확인은 저자만 할 수 있고, 그것이 이 지적의 요지다.**

#### F-3. `rules/` 가 배포되지 않는 에이전트 12종을 "존재한다"고 단정하고 사용을 지시

`rules/common/agents.md:5` 는 `~/.claude/agents/` 에 에이전트 10종이 "Located in" 이라고 단정하고 표로 열거한 뒤 `:22-26` 에서 "No user prompt needed" 로 즉시 사용을 지시한다. 이 저장소가 배포하는 것은 **4종**(`code-reviewer`·`design-architect`·`explore`·`implementer`)뿐이다.

미배포이면서 참조되는 것은 **12종**: `planner`·`architect`·`tdd-guide`·`security-reviewer`·`build-error-resolver`·`e2e-runner`·`refactor-cleaner`·`doc-updater`·`rust-reviewer`·`python-reviewer`·`go-reviewer`·`typescript-reviewer`. 반대로 배포되는 `design-architect`·`implementer`·`explore` 는 로스터에 없다. 같은 패턴이 `testing.md:22·29`, `security.md:26`, `performance.md:138`, `code-review.md:66-71`, `development-workflow.md:18·24`, `typescript/testing.md:18`, `react/security.md:179`, `react-native/testing.md:52` 에 있고, `react/security.md:180` 의 `react-reviewer` 는 배포물에도 저자 머신에도 없다.

**왜 저자가 관측할 수 없는가**: 저자 머신 `~/.claude/agents/` 에 51개가 있고 그 12종이 전부 실재한다 — 우연이 아니라 `rules/` 를 벤더링한 **같은 상류 번들**이다. 따라서 이 결함은 **순수 클론한 제3자 환경에서만 드러난다.** `testing.md` 의 "MANDATORY workflow / Use **tdd-guide** agent" 와 `security.md` 의 "STOP immediately → Use **security-reviewer** agent" 는 그 환경에서 실행 불가능한 지시가 된다.

> **검증자와 보충 렌즈가 정면으로 갈린 지점이다.** 적대적 검증자는 "`agents.md:5` 가 명시적으로 user scope 를 가리키고 README:280 이 그 디렉토리를 '우리 소유 아님'으로 규정하므로 상류 번들 참조이지 배포물의 오산이 아니다" 며 MINOR 로 강등했고, 보충 렌즈는 "바로 그것이 저자가 관측할 수 없는 이유" 라며 MAJOR 로 올렸다. 둘 다 사실관계가 맞고, 갈린 것은 **감사 대상이 저자인가 제3자인가**다. **저장소 정체가 「공개 배포물」로 확정됐으므로 MAJOR 로 확정한다.**

- **권고**: ① 로스터를 배포 4종으로 교체하고 나머지 참조 파일의 에이전트 지목을 정리한다. 또는 ③ 해당 절 서두에 "이 표는 상류 번들을 전제하며 이 저장소는 4종만 배포한다"를 넣는다. 어느 쪽이든 **"Located in" 단정과 "No user prompt needed" 지시의 조합**을 먼저 손댄다. 재발 방지: `tests/run.sh` 에 "rules 가 참조하는 에이전트는 `agents/` 에 실재해야 한다" 검사를 추가한다.

#### F-4. 미배포 `skills/`·MCP 서버·`gh` 를 "mandatory" 로 요구

`rules/common/development-workflow.md:9-13` 의 0단계는 스스로를 "_(mandatory before any new implementation)_" 로 규정하면서 `gh` CLI·Context7·Exa MCP 를 요구한다. 셋 다 이 저장소가 배포·설정하지 않고 「요구사항」에도 없다. `rules/react/testing.md:186` 의 `../../skills/e2e-testing/SKILL.md` 는 project 설치 후 `.claude/skills/…` 로 해석되는 상대 링크인데 그 경로에 아무것도 배포되지 않는다(`rules/react/patterns.md:194` 도 동일).

- **심각도 조정**: 보충 렌즈는 MINOR 로 냈다. **공개 배포물 확정으로 MAJOR 로 승격했다** — 순수 클론에서 "필수" 단계가 수행 불가이고, F-3 과 같은 계열이다.
- **권고**: F-3 과 함께 처리한다. `skills/` 상대 링크는 제거하거나 상류 URL 로 바꾼다(로컬 상대 링크로 두면 영구히 깨진 링크다). MCP·`gh` 는 「요구사항」에 "선택 — 없으면 0단계를 건너뛴다"로 명시하거나 `:9` 의 `_(mandatory …)_` 를 조건부로 완화한다.

#### F-5. `hub/` 는 Python 3.10+ 를 하드 요구하는데 두 README 어디에도 `python` 이 없다

```
README.md 의 python 언급 : 0회        hub/README.md : 0회
from __future__ import annotations 보유 : 0 / 15 모듈
hub_model.py:54  usage: UsageSample | None = None   ← dataclass 필드, 클래스 생성 시 즉시 평가
두 install.sh 의 version_info 가드 : 0
```

`from __future__ import annotations` 가 없으므로 클래스 본문 어노테이션은 클래스 생성 시점에 즉시 평가된다. Python 3.9 에서는 `import hub_model` 자체가 `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` 로 죽고, 같은 문법이 14개 모듈에 82곳 있다. 가드가 없어 **실패가 설치 시점이 아니라 실행 시점의 트레이스백으로** 나타난다 — 사용자는 "허브가 안 켜진다"만 본다.

공정하게 적으면 `README.md:8` 의 "외부 의존성이 없다"는 `install.sh` 범위에서는 정확하고, `hub/README.md` 는 macOS Keychain 의존성을 옵트인·플랫폼 한정으로 성실히 명시했다 — python3 누락은 의도가 아니라 빠뜨림으로 보인다.

- **권고**: `hub/README.md` 에 「요구사항」 절을 신설해 `python3 3.10 이상`을 근거(PEP 604 어노테이션, `__future__` 미사용)와 함께 명시하고, 루트 `README.md:340` 뒤에 한 줄을 추가한다. `hub/install.sh` 도입부에 `python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'` 가드를 두면 실패가 설치 시점으로 앞당겨진다.

## 3. 심각도 조정 2건 (원시 판정과 다른 곳)

투명하게 남긴다. 이 두 건은 렌즈·검증자의 판정을 종합 단계에서 바꿨다.

| 지적 | 원시 | 최종 | 사유 |
|---|---|---|---|
| `hub_collect.py:87` — 폴링·하트비트 주기에 하한 없음(0 → busy loop) | MAJOR | **MINOR** | 발동에 사용자의 `config.json` 편집이 필요하다. 발동 시 피해는 B-1 과 같으나(시간당 720회 자격증명 읽기, 또는 `stop_event.wait(0)` 로 CPU 1코어 점유) 트리거가 사용자 행위에 달렸다. "0 = 끄기" 직관이 흔하고 README 가 하한을 적지 않으므로 무해하지는 않다 |
| 미배포 `skills/`·MCP·`gh` 를 mandatory 로 요구 | MINOR | **MAJOR** | 저장소 정체가 「공개 배포물」로 확정돼 순수 클론 환경이 감사 대상에 들어왔다(F-4) |

## 4. 저장소 정체 결정이 정한 것

감사 중 저장소가 자기 정체를 두 가지로 말하고 있음이 드러났다 — `README.md:344` "사용자 개인 워크플로우 패키징이다" 대(對) `README.md:3` "어느 프로젝트든 동일한 개발 환경을 재구성" + `:31-33` clone 안내 + 공개 origin + `harness-update` 의 원격 pull.

**사용자 결정(2026-08-28): 공개 배포물.** 주 사용자는 팀원이지만 저장소를 공개로 두므로 모든 사용자가 클론한다는 것을 전제한다.

이 결정으로 다음 5건이 MAJOR 로 확정됐다: **F-1(라이선스) · F-2(상류 출처) · F-3(미배포 에이전트 12종) · F-4(미배포 skills·MCP·gh) · F-5(python3 3.10+).** 다섯 건 모두 **저자 머신에서는 정상으로 보인다** — 라이선스는 본인에게 필요 없고, 상류 출처는 본인이 알고, 에이전트 12종과 python 3.11 은 이미 깔려 있다. 결함이 관측되는 유일한 지점은 순수 클론한 제3자의 환경이고, 그 환경은 저장소를 공개로 두는 순간부터 존재한다.

**부수 확인**: 위생 렌즈가 실제 비밀값 유출 **0건**을 확인했다(`sk-ant-`·`ghp_`·`AKIA`·JWT 전수 스캔). 유일한 매칭은 `tests/hub/test_hub_usage.py:540` 의 `secret_looking_value = "sk-ant-should-never-leak-1234567890"` 으로, **토큰 유출을 막는 것을 검증하는 테스트 픽스처**다. 회사 이메일도 tracked 파일과 git 이력 양쪽에 유입되지 않았다. 지금 공개돼 있는 것 자체로 인한 피해는 없다.

## 5. 적대적 검증이 폐기한 오탐 4건

되살리지 않는다. 폐기 사유가 이 저장소의 문서화 관행이 실제로 작동한다는 증거이기도 하다.

| 지적 | 폐기 사유 |
|---|---|
`agents/explore.md:2` 의 `name: Explore` 대문자가 규격 위반 | 공식 문서가 **내장 Explore 오버라이드에 대해 대문자 이름을 직접 권장**한다("A user or project subagent named Explore overrides the built-in and keeps its own model field, so define one with `model: haiku`"). 규격 이탈이 아니라 규격이 처방한 패턴이다 |
`rules/README.md:62` 가 없는 `skills/` 참조 | 설치 위치(`~/.claude/skills`)에 18개 이상 실존한다. `:62` 는 「Rules vs Skills」 절의 개념 대조 정의이고 `:81` 은 "if available" 조건절이다. (단 예시 스킬명 `python-patterns`·`golang-testing` 노후화와 `skills/` **상대 링크** 문제는 F-4 로 별건 생존) |
`CLAUDE.md:125` 에 `CLAUDE_CODE_SUBAGENT_MODEL` 경고 누락 | 설정된 적 없는(전수 확인) 환경 변수에 대한 방어 문구를 미리 넣자는 제안. `karpathy-guidelines.md` #2「일어날 수 없는 상황에 대한 에러 처리 금지」·#3「변경된 모든 줄이 사용자 요청으로 추적돼야 한다」와 정면 충돌 |
린터·type checker·CI 설정 전무 | `docs/prps/hub-dashboard.md:863-864` 가 "새 의존성을 도입하지 않기 위해 `ruff`/`black` 을 추가하지 않고 표준 라이브러리로 가능한 `py_compile` 만 게이트로 쓴다"는 결정을, `:854-860` 이 검증 명령 4개를 이미 문서화했다 |

## 6. 서로 충돌하는 지적 4쌍

수정 순서를 정할 때 반드시 본다.

1. **개수 검증** — `hub/install.sh:97` "폐지하라" 대 `install.sh:12` "`RULES_FILE_COUNT` 일치 테스트를 늘려라". 양립하는 해가 있다: **소스측 상수 대조는 유효, 대상 디렉토리 총량 계수는 무효.**
2. **`CLAUDE.md` 이중 역할** — "프로젝트용으로 갈라라"(전역과 바이트 동일) 대 "`tests/run.sh` 2,717줄 함수가 자기 50줄 규칙 위반". 두 번째 피해는 배포 문서가 프로젝트 지침을 겸하는 그 결합에서만 발생한다 — **첫째를 고치면 둘째가 사라진다.**
3. **grep 앵커** — "너무 느슨해 실패하지 않는다"(`run.sh:1823`) 대 "너무 빡빡해 무해한 편집에도 깨진다"(한글 산문 99건). 어떤 앵커가 어느 쪽이어야 하는지 **기준이 없다.** C-2 의 정·역 테스트가 이 기준의 한 예를 제공한다.
4. **README 6개 대 `coding-harness.md` rev4** — 같은 원천이다. `README.md:280` 의 "6개"는 rev4 의 커맨드 6종을 물려받은 값이고 같은 README `:113`·`:312` 는 10 으로 갱신돼 있다. **별건으로 처리하면 숫자만 고쳐지고 원천(rev4 물림)이 남는다.**

## 7. 이 저장소가 잘 하고 있는 것

감사가 균형을 잃으면 신뢰를 잃으므로 함께 적는다.

1. **전제가 바뀌면 결정을 공개적으로 뒤집는다** — `SP19`가 `SP4`를, `RV1`이 `done` 터미널 가정을, 커밋 `3c5c7bc`이 `harness-update.md` §6.5·§9.5 를 명시적으로 번복했다. 이번 감사에서 오탐 4건 중 3건이 죽은 이유도 그 기록들이 존재했기 때문이다.
2. **실측을 근거로 쓴다** — `type:"http"` 미발동 실측, `SubagentStart` 236건 전수 판정, 신호 종료 코드 144 실측. 추측으로 쓴 규격이 거의 없다.
3. **올바른 패턴을 이미 갖고 있다** — `_collect_once` 의 `finally`, `_hub_hook_entry()`, `_write_settings_atomically`, T22-80 의 속성 순서 고정. MAJOR 5건의 수정안이 "이 저장소의 다른 곳을 복제하라"다.
4. **자체 노이즈 필터가 작동한다** — `agents/code-reviewer.md:63-69`("80% 이상 확신하는 실제 문제만")가 검증 단계에서 실제로 사변적 지적을 걸러냈다.
5. **소유권 원칙이 일관된다** — "남의 파일은 건드리지 않는다"가 `install.sh` 전반에 관철된다. 위반은 hub 개수 검증 1곳뿐이다.
6. **자격증명 취급이 견고하다** — 토큰을 Keychain 에서 읽어 `Authorization` 헤더로만 쓰고 로그·에러 메시지에 싣지 않으며, 실패 사유를 열거형으로 분리했다. 누출 회귀 테스트도 붙어 있다.
7. **플랫폼 전제를 적는 습관이 있다** — `hub/README.md` 가 macOS Keychain·사용량 API 의 옵트인·플랫폼 한정 성격을 성실히 명시한다(F-5 의 python3 누락과 대비된다).

## 8. 커버리지와 한계

정직하게 남긴다.

- **종합 단계는 서브에이전트가 아니라 메인 세션이 했다.** `synthesize:final` 이 세션 사용량 한도로 실패했다. 중복 제거·심각도 확정·수정 순서는 메인 세션의 판단이다.
- **워크플로우 스크립트에 커버리지 절단이 있었다.** 완전성 비평가가 보충 과제 6개를 지목했는데 스크립트가 `.slice(0, 4)` 로 2개를 잘랐다. 그 2개(`dashboard-producer-consumer-contract`·`public-artifact-hygiene`)를 별도로 실행해 복구했고 — **MAJOR 6건이 거기서 나왔다**(C-1, C-2, F-1, F-2, F-3, F-5). 절단을 알아채지 못했다면 이 감사의 MAJOR 절반이 누락됐다.
- **보충 라운드 44건은 적대적 검증을 거치지 않았다.** MAJOR 8건은 메인 세션이 직접 코드·문서를 열어 확인했고(그 과정에서 A-1 의 블록 수를 5→6 으로 정정했다), MINOR·INFO 36건은 미검증이다 — 확신도가 한 단계 낮다.
- **대형 파일은 전문이 아니라 표본으로 읽혔다** — `tests/run.sh` 5,391줄, hub 파이썬 16모듈. 각 렌즈가 `coverage_note` 에 범위를 남겼다.
- **상류 프로젝트 정체 미확정** — F-2 참조. 저자만 확인할 수 있다. **(2026-08-28 해소: ECC = https://github.com/affaan-m/everything-claude-code, MIT, © 2026 Affaan Mustafa. 파생 43개 / 원저작 분리는 `audit-remediation.md` §2 전제 2 에 실측 기록.)**
- **이 보고의 수치는 `main`@`9145ef3` 시점이다.** 2026-08-28 저녁 병행 세션의 `fix/tier0-defects`(`46ecb5b`, 2커밋·24파일)가 완료·푸시되면서 일부가 이미 해소됐다. 실측 대조: **해소** — `commands/harness-update.md` 의 「작은 diff 는 실제 내용까지 보여준다」 허위 괄호(§2 F 계열 shell 지적), `rules/README.md` 의 산술 불일치(§9 `memory-rules` MAJOR — 이제 `12 + 30 = 42` 로 정합). **미해소(그대로 유효)** — `README.md:283` 의 「배포 대상 6개」(실제 10), `hub/install.sh:96-99` 의 대상 총량 계수 검증. 또 `rules/` 가 **37 → 42** 로 늘었다(`rules/python/` 5파일 재도입) — §2 F-2 의 「파생 43개」 산정과 §9 표의 파일 수는 그만큼 갱신이 필요하다.
- **놓친 결함 1건 (사후 확인)** — 이 감사가 발견하지 못한 것을 병행 세션(`fix/tier0-defects`, `docs/prps/harness-landscape-survey.md`)이 찾았다: **허브가 전 프로젝트의 프롬프트를 시크릿 스크럽 없이 평문 보관한다.** 위생 렌즈(`public-artifact-hygiene`)는 **tracked 파일**의 시크릿만 훑었고, 허브가 런타임에 **수집·저장하는 데이터**의 내용은 어느 렌즈의 범위에도 없었다. 9개 렌즈 배정이 「저장소에 있는 것」축으로만 짜였고 「저장소가 만들어 내는 것」축이 없었던 결과다 — 다음 감사에서 렌즈를 짤 때의 교훈으로 남긴다.
- **법률 판단 배제** — F-1 은 배포 조건 부재의 실질적 결과를 사실로 서술하고 선택지만 제시한다. 특정 라이선스를 지목하지 않는다.

## 9. 지적 전량 (91건)

MAJOR 14건은 §2 에 전문이 있다. 아래 표는 9개 렌즈 + 보충 4라운드의 78건이고, 보충 2라운드(`dashboard-producer-consumer-contract` 5건 · `public-artifact-hygiene` 8건)의 13건은 §2 의 C·F 절과 아래 「보충 2라운드」에 있다.

「검증」 열: `CONFIRMED`/`UNCERTAIN` = 적대적 검증 통과 · `미검증` = 보충 라운드(검증 단계 없음).

### MAJOR (8건)

| 렌즈 | 위치 | 지적 | 검증 |
|---|---|---|---|
| `commands-skills` | [`commands/dashboard.md:15`](commands/dashboard.md#L15) | /dashboard 는 인자가 매번 달라 호출할 때마다 ~37k 토큰 전문이 컨텍스트에 다시 쌓인다 | CONFIRMED |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_collect.py:87`](hub/bin/hub_collect.py#L87) | 폴링 주기·하트비트 주기에 범위 하한이 없어 config 한 줄로 백오프 전체가 0 이 되고 티커가 busy loop 가 된다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_server.py:353`](hub/bin/hub_server.py#L353) | 폴링 사이클에서 예외가 새면 백오프 상태 대입이 무효가 돼, Keychain 읽기 + OAuth 원격 호출이 5초마다 무한 반복된다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_server.py:335`](hub/bin/hub_server.py#L335) | docstring 이 약속한 「앞에 한 번 찍어 오판을 막는다」가 성립하지 않는다 — 하트비트 TTL 15초 ≤ 사이클 최악 블로킹 15초+ | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/test_hub_settings.py:298`](tests/hub/test_hub_settings.py#L298) | 사용자 settings.json 을 다시 쓰는 유일한 경로(install_hooks·uninstall_hooks·백업·파싱실패 중단)에 테스트가 0건 — statusline 쌍둥이만 I/O 테스트를 받았다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react/patterns.md:189`](rules/react/patterns.md#L189) | react/patterns.md 가 「rules/react-native/ 는 아직 없다」고 단정 — 실제로는 8개 파일이 존재하고 같은 트리거에서 함께 로드된다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/web/hooks.md:31`](rules/web/hooks.md#L31) | web/hooks.md 의 훅 JSON 예제 5개가 전부 무효 스키마 — 그대로 붙이면 훅이 조용히 등록되지 않고, 존재하지 않는 $FILE_PATH 를 인자로 넘긴다 | 미검증 |
| `model-facts` | [`rules/common/performance.md:79`](rules/common/performance.md#L79) | /effort 를 'per-session' 으로 분류 — 공식 문서는 대화형 /effort 선택이 세션 간 지속된다고 명시 | CONFIRMED |

### MINOR (42건)

| 렌즈 | 위치 | 지적 | 검증 |
|---|---|---|---|
| `coherence` | [`CLAUDE.md:90`](CLAUDE.md#L90) | CLAUDE.md 의 검수 게이트 어휘(Critical/Major)가 검수자·커맨드·rules 가 실제로 쓰는 어휘(CRITICAL/HIGH/MEDIUM/LOW)와 다르다 | CONFIRMED |
| `coherence` | [`README.md:280`](README.md#L280) | README 소유권 절이 커맨드 배포 대상을 6개라고 말하는데 같은 문서의 다른 세 곳과 install.sh 는 10개다 | CONFIRMED |
| `coherence` | [`README.md:122`](README.md#L122) | README 의 CLAUDE.md 요약(122행)이 fable 조건부 승격 도입 이전의 모델 정책을 서술해, 같은 문서의 에이전트 표(206-218행)와 CLAUDE.md 본문에 어긋난다 | CONFIRMED |
| `coherence` | [`rules/common/agents.md:9`](rules/common/agents.md#L9) | 상시 로드되는 rules 가 배포되지 않는 에이전트 9종을 '쓰라'고 지시하고, 실제 배포되는 4종 중 3종은 로스터에 없다 | CONFIRMED |
| `coherence` | [`rules/common/development-workflow.md:17`](rules/common/development-workflow.md#L17) | 상시 로드되는 CLAUDE.md 와 rules/common 3개 파일이 서로 다른 워크플로우·테스트 기준·의존성 정책을 동시에 명령하며, 충돌 시 우선순위가 어디에도 없다 | CONFIRMED |
| `coherence` | [`tests/run.sh:2590`](tests/run.sh#L2590) | 이 저장소에서 활성인 자기 CLAUDE.md 의 「함수 50줄」 규칙을 tests/run.sh 의 2,717줄·1,423줄 함수가 위반한다 | CONFIRMED |
| `commands-skills` | [`commands/harness-update.md:2`](commands/harness-update.md#L2) | 부작용 커맨드(harness-update·prp-commit·prp-pr)에 disable-model-invocation 이 없어 모델이 자율 호출할 수 있다 | CONFIRMED |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_server.py:354`](hub/bin/hub_server.py#L354) | 폴링 게이트가 벽시계로 간격을 재, 저장소가 수집 게이트에서 이미 고친 「시계 역행하면 게이트가 영구 미발동」 결함이 이 경로에만 남아 있다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_usage_fetch.py:111`](hub/bin/hub_usage_fetch.py#L111) | OAuth Bearer 토큰이 리다이렉트를 따라 다른 호스트·평문 http 로 재전송될 수 있다 — A-SEC 이 로컬 노출만 막고 네트워크 egress 는 열어 뒀다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_usage_fetch.py:121`](hub/bin/hub_usage_fetch.py#L121) | 원격 응답을 무제한으로 읽고 그 키 구조를 무제한으로 디스크에 쓴다 — 저장소가 로컬 신뢰 파일에는 다 걸어 둔 상한이 정작 비신뢰 원격 경로에만 없다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_usage_fetch.py:42`](hub/bin/hub_usage_fetch.py#L42) | A-SEC 불변식 문장과 PRP 가 반환값이라고 지목한 FAILURE_REASON_MESSAGES 를 코드 어디서도 읽지 않는다 | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/test_hub_daemon.py:206`](tests/hub/test_hub_daemon.py#L206) | stop_server 의 「PID 재사용 → 죽이지 않는다」 분기와 SIGKILL 승격에 행위 테스트가 없다 — os.kill 을 모킹하는 테스트가 저장소에 0건 | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/test_hub_hook.py:100`](tests/hub/test_hub_hook.py#L100) | 훅의 「spawn 하지 않는다」 테스트 2건이 assert_not_called 단독 — main() 이 모든 예외를 삼키므로 훅이 통째로 깨져도 통과한다 | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/test_hub_parse.py:11`](tests/hub/test_hub_parse.py#L11) | 파서 테스트는 2026-08-13 에 손으로 쓴 픽스처 5종만 읽는다 — 실제 생성물(dashboard_template.html + dashboard.md 의 li 생성 문자열)을 파서에 넣는 테스트가 어디에도 없다 | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/test_hub_statusline.py:136`](tests/hub/test_hub_statusline.py#L136) | statusline 테스트의 `assertEqual(exit_code, 0)` 4건은 구조적으로 실패 불가능 — main() 은 0 이외를 반환할 수 없다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react-native/hooks.md:28`](rules/react-native/hooks.md#L28) | 배포되는 stack 규칙 4곳이 이 배포에 존재하지 않는 환경변수·슬래시 커맨드·에이전트를 쓰라고 지시한다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react-native/performance.md:8`](rules/react-native/performance.md#L8) | 3개 파일의 'extends common/X.md' 선언이 주제가 전혀 다른 파일을 가리킨다 — common/performance.md 는 앱 성능이 아니라 Claude 모델·effort 선택 문서다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react/hooks.md:160`](rules/react/hooks.md#L160) | 「React 19 Additions」가 React 19 에서 개명돼 사라진 이름 useFormState 를 신규 추가 API 로 먼저 제시한다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react/patterns.md:82`](rules/react/patterns.md#L82) | 같은 트리거로 동시 로드되는 react/ 두 파일이 클래스 컴포넌트를 한쪽은 금지, 한쪽은 필수라고 지시한다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react/testing.md:2`](rules/react/testing.md#L2) | react/ 의 조건부 글롭이 같은 디렉토리가 규정한 파일 네이밍 규약을 못 잡는다 — 훅 테스트(.test.ts)와 camelCase 훅 파일(useUser.ts)에는 React 규칙이 로드되지 않는다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/typescript/coding-style.md:79`](rules/typescript/coding-style.md#L79) | 3개 디렉토리가 같은 주제를 중복 서술하며 기본값이 서로 갈라진다 — prop 타이핑 3종, Tabs API 2종이 같은 .tsx 편집에서 동시 로드된다 | 미검증 |
| `gap-two-root-link-and-cwd-integrity` | [`commands/dashboard.md:11`](commands/dashboard.md#L11) | `../../` 링크 4건이 레포·설치본 양쪽에서 깨진다 — 정본 깊이(`../`)는 PRP에 결정으로 남고 테스트에 리터럴로 박혀 있는데, 오답만 무검사로 남았다 | 미검증 |
| `gap-two-root-link-and-cwd-integrity` | [`commands/dashboard.md:108`](commands/dashboard.md#L108) | commands/ 의 근거 링크 28건이 설치본에서 전멸한다 — docs/ 는 배포되지 않아 어떤 깊이로도 정답이 없고, 이 저장소가 T13 으로 문서화한 「상대경로 참조 보존」 기준이 rules/ 밖에서는 검증된 적이 없다 | 미검증 |
| `gap-two-root-link-and-cwd-integrity` | [`rules/README.md:39`](rules/README.md#L39) | 상시 로드되는 배포 파일이 `./install.sh` 실행을 지시하지만, 배포 위치에는 install.sh 가 없다 — 같은 저장소의 harness-update.md 는 같은 호출을 절대경로로 올바르게 처리한다 | 미검증 |
| `gap-two-root-link-and-cwd-integrity` | [`rules/README.md:96`](rules/README.md#L96) | rules/README.md:96 의 예시 링크만 펜스 밖에 있어 세 루트에서 죽는 실제 링크로 렌더된다 — 17줄 위의 같은 구조(79행)는 펜스로 비활성화돼 있다 | 미검증 |
| `hooks` | [`hub/bin/hub_settings.py:88`](hub/bin/hub_settings.py#L88) | settings.json 최상위가 객체가 아닌 유효 JSON 이면 정중한 중단 대신 AttributeError 트레이스백으로 죽는다 | CONFIRMED |
| `memory-rules` | [`CLAUDE.md:216`](CLAUDE.md#L216) | 프로젝트 CLAUDE.md 가 전역 ~/.claude/CLAUDE.md 와 바이트 동일 — 이 저장소의 모든 세션에서 같은 223줄이 두 번 로드되고, 자기 자신의 프로젝트 체크리스트 5항목을 0개 충족한다 | CONFIRMED |
| `memory-rules` | [`rules/README.md:52`](rules/README.md#L52) | rules/README.md 의 조건부 로드 목록(17개)에서 react-native/ 8개가 누락 — 12+17=29 ≠ 37 로 같은 파일 안에서 산술이 깨진다 | CONFIRMED |
| `model-facts` | [`CLAUDE.md:154`](CLAUDE.md#L154) | §6 인용이 원문을 과대 서술 — '검출이 서로 겹치지 않았다' 와 '메인 세션 = opus' 는 §6 에 없는 내용 | CONFIRMED |
| `model-facts` | [`rules/common/performance.md:83`](rules/common/performance.md#L83) | 'max 와 ultracode 는 session-only' 단정 — 둘 다 문서상 지속 경로가 있고, ultracode 는 effort 레벨 자체가 아님 | CONFIRMED |
| `python` | [`hub/bin/hub_template.html:1254`](hub/bin/hub_template.html#L1254) | 티어1 제목·단계명·상세가 허브에서 이중 이스케이프돼 HTML 엔티티가 그대로 보인다 | CONFIRMED |
| `shell` | [`commands/harness-update.md:162`](commands/harness-update.md#L162) | harness-update 가 install.sh 가 diff 내용을 보여준다고 허위 기술하고, 그 정보를 전제로 무확인 --force(백업 없음)를 지시한다 | CONFIRMED |
| `shell` | [`hub/install.sh:97`](hub/install.sh#L97) | 설치 검증이 대상 전체 파일 수를 세어 소유권 원칙과 모순 — 외부 파일 1개로 모든 설치가 복사 성공 후 영구 실패 | CONFIRMED |
| `shell` | [`hub/install.sh:206`](hub/install.sh#L206) | --uninstall --dry-run 조합이 dry-run 을 조용히 무시하고 실제 제거를 수행한다 | CONFIRMED |
| `shell` | [`install.sh:121`](install.sh#L121) | 누락 파일 검출 grep 패턴에 저장소 경로가 미이스케이프로 삽입돼, 정규식 메타문자가 든 경로에서 검증이 조용히 무력화된다 | CONFIRMED |
| `shell` | [`install.sh:360`](install.sh#L360) | 심볼릭 링크 가드가 디렉토리 3개에만 적용되고 CLAUDE.md 대상 파일에는 없다 — 링크를 관통해 대상 밖 파일을 덮어쓴다 | CONFIRMED |
| `tests` | [`tests/run.sh:1823`](tests/run.sh#L1823) | 전체 파일 대상 단어 1개 grep 어서션 — 지키려는 회귀가 일어나도 절대 실패하지 않는다 | CONFIRMED |
| `tests` | [`tests/run.sh:1195`](tests/run.sh#L1195) | DOM 계약 불변식 1(dz-step-*/dz-cell-* 배타)만 아무 검사가 없다 — 템플릿 초기 상태 검증으로 닫을 수 있는 구멍 | CONFIRMED |
| `tests` | [`tests/run.sh:5382`](tests/run.sh#L5382) | passed+failed == total 을 아무도 검사하지 않는다 — 등록 누락·미기록 테스트가 「모든 테스트 통과」로 끝난다 | CONFIRMED |
| `tests` | [`tests/run.sh:327`](tests/run.sh#L327) | T3 멱등성 검사는 두 상태가 모두 빈 문자열이어도 통과한다 — 캡처 실패·설치 실패가 공허 통과로 귀결 | CONFIRMED |
| `tests` | [`tests/run.sh:724`](tests/run.sh#L724) | 테스트마다 trap ... EXIT 를 다시 걸어 이전 트랩을 전부 덮어쓴다 — 마지막 샌드박스만 청소되고, 코드가 트랩 누적을 전제하고 있다 | CONFIRMED |
| `tests` | [`tests/run.sh:2590`](tests/run.sh#L2590) | run.sh 5391줄, 단일 bash 함수 2,717줄 — 규모가 이미 주석·라벨 드리프트를 만들고 있다 | CONFIRMED |

### INFO (28건)

| 렌즈 | 위치 | 지적 | 검증 |
|---|---|---|---|
| `agents` | [`agents/code-reviewer.md:4`](agents/code-reviewer.md#L4) | code-reviewer 의 읽기 전용 설계가 무제한 Task 부여로 도구 수준에서는 강제되지 않는다 | CONFIRMED |
| `agents` | [`agents/code-reviewer.md:4`](agents/code-reviewer.md#L4) | 세 에이전트의 tools 가 v2.1.63에서 Agent 로 개명된 구 도구명 Task 를 쓴다 | CONFIRMED |
| `agents` | [`agents/code-reviewer.md:100`](agents/code-reviewer.md#L100) | code-reviewer 의 「모델 운용 참고」가 CLAUDE.md 에 최근 추가된 「전수 검사」 fable 승격을 반영하지 않는다 | CONFIRMED |
| `agents` | [`agents/implementer.md:3`](agents/implementer.md#L3) | implementer 의 description 이 전체 경로(PRP 기반)만 서술해 본문이 정의한 축약 경로 역할을 누락한다 | CONFIRMED |
| `coherence` | [`CLAUDE.md:117`](CLAUDE.md#L117) | 배포되는 CLAUDE.md 가 coding-harness 저장소에만 존재하는 docs/prps 문서 2건을 상대 경로로 링크한다 | CONFIRMED |
| `coherence` | [`docs/prps/coding-harness.md:81`](docs/prps/coding-harness.md#L81) | README 가 '전체 설계 원리'로 지목하는 coding-harness.md 가 rules 79개·커맨드 6종·총 90파일 시절(rev4)에 멈춰 현재 실물(37·10·52)과 어긋난다 | CONFIRMED |
| `coherence` | [`rules/README.md:62`](rules/README.md#L62) | 배포되는 rules 가 존재하지 않는 skills/ 디렉토리와 5종 SKILL.md 를 가리킨다 | CONFIRMED |
| `coherence` | [`rules/README.md:5`](rules/README.md#L5) | rules/README 의 큐레이션 자기서술이 React Native 를 빠뜨려 최상위 README·실물 트리와 어긋나고, RN glob 격리의 문서화된 우회책은 재설치가 되돌린다 | CONFIRMED |
| `commands-skills` | [`commands/code-review.md:1`](commands/code-review.md#L1) | code-review 커맨드가 번들 /code-review 스킬을 가리는 사실과 /review 별칭 우회가 문서화돼 있지 않다 | CONFIRMED |
| `gap-keychain-oauth-network-path` | [`hub/README.md:346`](hub/README.md#L346) | README 는 폴링이 동작한다고 단정하는데, 엔드포인트·스키마 실재 확인(SP3)이 생략됐다는 사실은 PRP 안에만 있다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_usage_fetch.py:93`](hub/bin/hub_usage_fetch.py#L93) | 429 에서 서버가 알려주는 대기 시간을 버리고 고정 60분 상한으로 점프한다 — 방향은 보수적이지만 패널이 최대 60분 얼어붙는다 | 미검증 |
| `gap-keychain-oauth-network-path` | [`hub/bin/hub_usage_fetch.py:124`](hub/bin/hub_usage_fetch.py#L124) | TLS 인증서 검증 실패가 단순 연결 실패와 같은 network_error 로 접혀, 보안 이벤트를 가릴 수 있는 유일한 진단 창구가 없다 | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/fixtures/old_generation_dashboard.html:13`](tests/hub/fixtures/old_generation_dashboard.html#L13) | old_generation 픽스처가 주장하는 세대와 마크업이 어긋난다 — 자기 DZ 맵·CSS 는 .step-detail 을 아는데 테스트는 「이 기능 도입 이전」이라고 설명한다 | 미검증 |
| `gap-python-unittest-suite-content` | [`tests/hub/test_hub_session.py:27`](tests/hub/test_hub_session.py#L27) | 이벤트 픽스처의 기본 cwd 에 개발자 절대경로가 박혀 있다 — 판정: 어떤 assertion 도 읽지 않는 죽은 값이라 다른 경로 클론에서도 영향 없다 | 미검증 |
| `gap-stack-rule-content-25-files` | [`rules/react/testing.md:18`](rules/react/testing.md#L18) | Library Choice 절이 2025-02 에 deprecate 된 CRA 를 현행 선택지와 같은 층에 놓는다 | 미검증 |
| `gap-two-root-link-and-cwd-integrity` | [`rules/react/testing.md:186`](rules/react/testing.md#L186) | 역방향 사례 1건 — `../../skills/e2e-testing/SKILL.md` 는 규격상 두 설치 루트에서 모두 정답이고 레포에서만 깨진다. 「skills/ 가 없으니 링크를 걷어내라」는 처방은 이 줄에서는 오답이다 | 미검증 |
| `hooks` | [`hub/bin/hub_settings.py:75`](hub/bin/hub_settings.py#L75) | 설치되는 훅 엔트리에 timeout 이 없어 행(hang)에 대한 방어가 규격 기본값 600초에 맡겨진다 | CONFIRMED |
| `hooks` | [`hub/install.sh:179`](hub/install.sh#L179) | --uninstall 이 uninstall-hooks 실패를 `\|\| true` 로 삼키고 bin/ 을 삭제해, 잔존 훅 엔트리의 제거 수단이 함께 사라진다 | CONFIRMED |
| `memory-rules` | [`CLAUDE.md:117`](CLAUDE.md#L117) | 배포되는 CLAUDE.md 의 근거 링크 2곳이 저장소 상대경로(docs/prps/…)라 ~/.claude/CLAUDE.md 로 설치되면 모든 다른 프로젝트에서 죽은 링크가 된다 | CONFIRMED |
| `memory-rules` | [`docs/prps/coding-harness.md:440`](docs/prps/coding-harness.md#L440) | 큐레이션(79→37)으로 배포에서 빠진 규칙이 설치본에 영구 잔존하는 리스크의 완화책으로 PRP 가 약속한 'README에 수동 제거 안내'가 README 에 없다 | CONFIRMED |
| `model-facts` | [`CLAUDE.md:125`](CLAUDE.md#L125) | 디스패치 model 인자 우선 주장은 정확하나, CLAUDE_CODE_SUBAGENT_MODEL 이 그보다 우선한다는 사실이 누락됨 | CONFIRMED |
| `python` | [`hub/bin/hub_server.py:117`](hub/bin/hub_server.py#L117) | 발견된 프로젝트 dashboard.html 을 sandbox 없이 동일 출처 iframe 으로 실행 — 클릭 유발 능동 콘텐츠 실행 벡터 | CONFIRMED |
| `shell` | [`hub/install.sh:179`](hub/install.sh#L179) | uninstall 이 훅·statusLine 제거 실패를 \|\| true 로 삼킨 채 bin/ 을 삭제한다 — 자체 주석이 경고한 고아 훅 상태를 허용 | CONFIRMED |
| `shell` | [`install.sh:201`](install.sh#L201) | --force 는 CLAUDE.md 만 백업하고 rules/agents/commands 의 사용자 수정본은 목록 표시도 백업도 없이 덮어쓴다 | CONFIRMED |
| `shell` | [`install.sh:429`](install.sh#L429) | 매니페스트가 비원자적 리다이렉트로 쓰이고 경로가 JSON 이스케이프 없이 삽입된다 — 저장소 자체 표준(hub_settings.py)에 미달 | CONFIRMED |
| `shell` | [`install.sh:12`](install.sh#L12) | RULES_FILE_COUNT·AGENTS_FILE_COUNT 는 COMMANDS·HUB 와 달리 실제 파일 수와의 일치 테스트가 없다 | CONFIRMED |
| `shell` | [`install.sh:88`](install.sh#L88) | --scope project 가 $PWD 를 무검증 수용 — $HOME 에서 실행하면 user 스코프 매니페스트를 project 스코프로 덮어쓴다 | CONFIRMED |
| `tests` | [`tests/run.sh:1480`](tests/run.sh#L1480) | 한글 산문 문장을 고정하는 grep 어서션 99건 — 문서화된 의도적 설계지만, 문장 다듬기 비용과 의미-불변 미검출이라는 양면 비용은 남는다 | CONFIRMED |

### 보충 2라운드 (13건)

#### `dashboard-producer-consumer-contract` (5건)

| 심각도 | 위치 | 지적 |
|---|---|---|
| MAJOR | `commands/dashboard.md:116-117` | 허브 파서 계약을 사실과 반대로 서술 — §2 C-1 |
| MAJOR | `tests/hub/test_hub_parse.py`, `tests/run.sh:2665` | 생산자 예시↔파서 정규식 정·역 테스트 부재 — §2 C-2 |
| MINOR | `commands/dashboard.md:149` | 불변식 2 의 `<td id="dz-cell-…">` 축약형이 파서가 요구하는 속성 순서와 반대(`<td class="cell" id="…">` 가 정답). 권위 예시(`:409-423`)는 순서가 맞아 오늘 깨지지는 않는다 |
| MINOR | `commands/dashboard.md:146` | 불변식 머리글이 "이 두 가지"인데 실제 6개(1~4 + 5·6). 머리글의 사유("`step` 의 결정성")도 6개 전부에 해당하지 않는다 — 4는 스크립트/CSS 경계, 6은 진행률 분모 분리 |
| MINOR | `hub/bin/hub_parse.py:32,75-78,97-103` | `matrix_done`·`StepView.started_at` 은 파싱되지만 렌더 소비자가 없다(`hub_template.html` 에 `matrix` 문자열 부재). 둘 다 문서화된 보존 결정이므로 코드 변경은 권고하지 않고, docstring 에 "현재 렌더 소비자 없음" 한 줄을 남긴다. **역방향 테스트 우선순위 정보**: 선형·impl 이 먼저다 |

> 부수 확인: 격리된 실험물 `docs/prps/ab-artifacts/exp2-opus-bare.md:560` 은 "`matrix_done` 이 `None` 이 되고 **허브의 매트릭스 진행률이 사라진다**"고 적었으나 **그런 렌더 경로가 없다**. 같은 실험 묶음의 `exp2-fable-scaffolded.md:198`("소비자가 없다")이 맞다. `ab-artifacts/` 를 향후 설계 근거로 재활용할 때 주의한다 — 커밋 `b13f9c7` 가 실험물로 격리한 이유의 실례다.

#### `public-artifact-hygiene` (8건)

| 심각도 | 위치 | 지적 |
|---|---|---|
| MAJOR | 루트(부재), `README.md:342-344` | `LICENSE` 부재 — §2 F-1 |
| MAJOR | 전역(부재), 흔적 6파일 | 상류 출처·저작자 표기 전무 — §2 F-2 |
| MAJOR | `rules/common/agents.md:1-25` 외 5파일 | 미배포 에이전트 12종을 "존재한다"고 단정하고 사용 지시 — §2 F-3 |
| MAJOR | `hub/bin/hub_model.py:54-55`, `README.md:336-340` | `python3 3.10+` 하드 요구가 두 README 에 부재, 버전 가드 없음 — §2 F-5 |
| MAJOR | `rules/common/development-workflow.md:9-13`, `rules/react/testing.md:186` | 미배포 `skills/`·Context7·Exa·`gh` 를 mandatory 로 요구 — §2 F-4 (MINOR→MAJOR 승격, §3) |
| MINOR | `.gitignore:14-16` | `.mypy_cache/`·`.pytest_cache/`·`.ruff_cache/` 가 커밋을 면한 유일한 이유는 각 도구가 그 안에 `*` 만 담긴 `.gitignore` 를 스스로 써 준 덕이다(`git check-ignore -v` 로 확인). `.gitignore:5` 는 "사용자 전역 gitignore 에 의존하지 않고 레포 자체에서 제외한다"는 원칙을 명문화했는데, 그 원칙이 "도구가 써 주는 파일에 의존한다"로 대체됐을 뿐 통제권이 레포 밖이라는 성질은 같다. `__pycache__` 는 직접 막는데 이 3개는 위임한 **비대칭**이다. 3줄 추가로 해소 |
| MINOR | `hub/bin/hub_template.html:60-62` | lucide 고지가 PRP 스스로 적은 조건에 미달. `hub-panel-polish-and-icons.md:275` 는 "ISC 라이선스이고 **저작권 고지 유지**가 조건이다"라고 적었는데 구현된 것은 **출처 참조**(프로젝트명·라이선스명·URL)다. 판정 기준이 외부 해석이 아니라 저장소 자신의 문서다. F-1 의 `NOTICE.md` 제3자 고지 절에 넣으면 함께 해소된다. **잘한 점**: 이 저장소에서 제3자 저작물을 표기한 유일한 자리이고, CDN 대신 인라인 SVG 를 택한 근거까지 남겼다 |
| INFO | `docs/prps/` 4파일, `tests/hub/test_hub_session.py:27` 등 6파일 11건 | tracked 파일의 `/Users/dev` 절대경로. **11건 전부 비실행 값**이라 다른 환경에서 오작동하지 않는다 — `test_hub_session.py:27` 은 `HookEvent.cwd` 에 넣는 불투명 데이터이고 어떤 assertion 도 값을 읽지 않는다. 실제 영향은 사용자명·레이아웃 노출뿐이며 git 이력이 이미 저자 identity 를 공개한다. 차단 사유가 아니다. 줄이려면 테스트 1건만 `/repo` 로 바꾸는 것이 비용 대비 효과 최대(같은 파일이 이미 `/repo` 를 쓴다) — `docs/prps/` 는 실측 기록이라 치환하면 재현 근거가 훼손된다 |

## 10. 원시 데이터

이 감사의 서브에이전트 원시 산출물(렌즈별 findings + 검증 판정 전문)은 세션 스크래치패드에 있고 저장소에 커밋되지 않는다. 재현이 필요하면 §1 의 렌즈 배정과 규칙으로 다시 돌린다.

- 워크플로우 저널: `~/.claude/projects/-Users-dev-private-project-coding-harness/<세션>/subagents/workflows/wf_8aa78896-b23/journal.jsonl`
- 렌즈별 구조화 결과: 스크래치패드 `audit-raw2.json`(9렌즈 + 보충 4라운드 · 검증 판정 51건 포함)

