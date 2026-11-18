# Plan: 백엔드 스택 지원 보완 (backend-stack-support)

- 설계 모델: opus(기본 — fable 승격 기준 1~4 미해당: 배포 자산 문서 개편, 동시성·데이터 모델 개편 아님)
- 기준: develop `21498d7`(v1.5.0), 브랜치 `feat/backend-stack-support`
- 산출 범위: 설계만. 구현은 승인 뒤 `implementer`
- **승인(2026-11-17, 사용자)**: 추천안 — J1(`rules/java/` 2파일)·「Backend Changes」 칸 채택. 보완 1건: 테스트가
  아직 없는 새 프로젝트의 기본값을 둔다(Python → pytest, Java → JUnit 5). 프론트 규칙이 「새 Vite 프로젝트는
  Vitest」로 기본값을 주는 것과 같은 방식이다(`rules/react/testing.md`). 아래 `rules/python/testing.md`·
  `rules/java/testing.md` 초안에 반영했다.
- **구현 중 달라진 점(2026-11-17, 검수 3회 PASS)**: ① README 「백엔드 지원」 절 마지막 문장은 「허브 폴더의
  `CLAUDE.md` 에 있다(아래 파일 구조 참고)」로 썼다 — 초안대로 `hub/CLAUDE.md` 를 적으면 README 의 "hub" 줄이
  15줄이 돼 T25-22(14줄 이하)가 깨진다. 임계값은 올리지 않았다. ② 검수 권고로 `agents/code-reviewer.md` 절차 6
  과 두 Validation 표(에이전트·`commands/code-review.md` Phase 4)에 `Blocked (env: …)` 를 더하고, T31-11
  `evidence_contract_pairs` 에 `agents/code-reviewer.md`·`Blocked (env` 쌍을 더했다(상수 불변). ③ 환경 실패 때
  우회 금지 문구를 네 곳(검수자 에이전트·`code-review`·`prp-implement`·`rules/java/coding-style.md`)에서 「빌드
  파일·빌드 설정 전체(wrapper·language level·dependency/plugin 버전·저장소 URL·JVM 옵션 등)」로 맞췄다.
  ④ T26 실측은 56,789B(초안 추정 56,774B).

## 요구사항 요약 (Summary)

지금까지 배포 자산(rules/agents/commands)은 프론트(React/TS) 위주로 다듬어졌다. 백엔드 프로젝트에 대
보니 세 군데가 어긋난다. ① 배포되는 `rules/python/` 5파일이 이 저장소 허브(`hub/bin/*.py`) 코드에서
귀납한 관례라서, FastAPI+pytest 프로젝트에서도 「stdlib unittest 기본·표준 라이브러리 우선」으로 끌고 간다.
② Java(Gradle/Maven)는 검증 명령 감지가 없어 검수·구현 때 `./gradlew test` 가 자동으로 돌지 않고,
Java 규칙도 없다. ③ 트랜잭션·동시 갱신·API 하위 호환·DB 마이그레이션 안전성은 설계서·검수 어디에도
자리가 없다. 이 PRP 는 Python 규칙을 「프로젝트가 이미 쓰는 것을 따른다」는 범용 규칙으로 다시 쓰고
허브 관례는 저장소 전용 `hub/CLAUDE.md` 로 옮기며, Java 감지·검증 명령과 최소 Java 규칙(2파일)을 넣고,
백엔드 주제를 설계·구현·검수 자산의 기존 자리에 최소한으로 넣는다.

## User Story

백엔드(Python/FastAPI, Java/Spring) 프로젝트에서 이 하네스를 쓰는 개발자로서, 규칙과 검증 명령이 그
프로젝트가 이미 고른 도구·버전을 따르기를 원한다 — 그래야 에이전트가 프로젝트에 없는 테스트 방식이나
컴파일되지 않는 문법으로 코드를 끌고 가지 않는다.

## Problem → Solution

| 지금 | 바뀐 뒤 |
|---|---|
| `*.py` 를 열면 허브 관례(unittest 기본·stdlib 우선·훅 exit 0·`hub_*.py` 예시)가 모든 프로젝트에 로드 | 범용 규칙(프로젝트의 `requires-python`·테스트 프레임워크·린터·의존성을 따름) + 허브 관례는 `hub/` 를 열 때만 |
| Gradle/Maven 프로젝트에서 검증 명령 미감지 | `./gradlew`·`./mvnw` 래퍼 우선 감지, 타입체크·테스트·빌드 태스크 대응 |
| Java 규칙 없음(이 PC 에는 하네스 관리 밖의 옛 ECC 규칙이 Java 16+ 문법을 권함) | `rules/java/` 2파일 — 빌드 파일의 언어 수준이 쓸 수 있는 문법을 정한다 |
| 백엔드 고유 위험(트랜잭션·호환·마이그레이션) 칸 없음 | 설계서 「Backend Changes」 칸, 검수 「백엔드 패턴」 4항목, `Database Validation` 예시 |

## Metadata

- **Complexity**: Large(파일 23개, 대부분 문서·가드 장부의 기계적 갱신)
- **Source PRD**: N/A
- **PRD Phase**: N/A
- **Estimated Files**: 생성 4(이 문서 포함) · 수정 19

---

## 확인한 사실

메인 세션이 넘긴 사실(재측정 안 함)에 이번 탐색에서 직접 확인한 것을 더했다. **업무 저장소 두 곳은
이 문서에서 익명으로 적는다** — 이 저장소는 공개 저장소라 `docs/prps/` 가 그대로 공개된다(D7).

| # | 사실 | 근거 |
|---|---|---|
| F1 | `rules/python/` 5파일은 커밋 `4be8f58` 이 허브 코드에서 귀납해 다시 쓴 것이다 | `NOTICE.md` §3 「상류 유래 경로·본문 재작성」 |
| F2 | 서브에이전트가 `.py` 파일을 Read 하면 user scope `~/.claude/rules/python/*.md` 5개가 즉시 system-reminder 로 붙는다 | 이번 설계 세션에서 `hub/bin/hub_server_state.py` 를 Read 해 직접 관측 |
| F3 | 업무 백엔드 A: FastAPI 0.130 · pytest 8.4 · pytest-asyncio(`asyncio_mode = "auto"`) · `uv.lock` · `[tool.ruff]`. CLAUDE.md 는 `@AGENTS.md` 한 줄이고 AGENTS.md 는 테스트 규칙을 `tests/AGENTS.md`(pytest)로 **가리키기만** 한다 | 읽기 전용 확인 |
| F4 | F3 때문에 옛 규칙의 「pytest 는 프로젝트 CLAUDE.md 에 명시했을 때만」 조건이 충족됐는지 애매하다 — 가리키는 줄이 있지만 결정 기록은 아니다. 애매한 조건은 세션마다 다르게 판정된다 | F3 |
| F5 | 업무 백엔드 B: Spring Boot 2.3.9 · `sourceCompatibility = '1.8'` · Gradle 7.1.1 래퍼 · MyBatis(mapper XML) · Lombok · `useJUnitPlatform()` · 테스트 파일 1개 · 수동 SQL 패치 디렉토리(Flyway/Liquibase 없음) · 사설 Maven 저장소 · CLAUDE.md 없음 | 읽기 전용 확인 |
| F6 | Gradle 7.1 은 JDK 17 이상에서 Gradle 자체가 돌지 않는다(17 지원은 7.3부터) — 최신 JDK 만 있는 PC 에서 B 의 `./gradlew test` 는 코드와 무관하게 실패한다 | Gradle 호환 표 |
| F7 | 이 PC 의 `~/.claude/rules/` 에는 하네스가 관리하지 않는 옛 ECC 규칙 10개 언어 디렉토리(java 포함, 2026-04)가 남아 있다. `java/` 5파일은 `record`(16+)·`var`(10+)·sealed(17+)·`List.copyOf`(10+)를 권한다 — Java 8 프로젝트에서 컴파일되지 않는 조언이다 | `~/.claude/.coding-harness.json` 대장(58개)에 java 없음 |
| F8 | `install.sh` 는 대상에 이미 있는 같은 경로의 비관리 파일을 대장 해시가 없으므로 **modified** 로 분류해 `--force` 를 요구한다(`classify_differing_file`). `--force` 는 `.bak-<시각>` 백업 후 덮어쓴다 | `install.sh` |
| F9 | `commands/code-review.md` PR 모드 Python 블록은 이미 `pytest` 를 쓴다 — 배포 규칙(unittest 기본)과 커맨드가 서로 어긋나 있었다 | `commands/code-review.md` Phase 4 |
| F10 | 상류 ECC 는 `rules/java/` 5파일(coding-style·hooks·patterns·security·testing)을 배포한다. 이 저장소는 `5f9552f` 큐레이션(79→37)에서 java 트랙을 뺐다 | 로컬 ECC 사본 · `NOTICE.md` §4 |
| F11 | 아래 계약 토큰 후보는 로컬 ECC 사본의 해당 파일에 0건이다: `requires-python`·`Never Block the Event Loop`·`test framework the project already uses`·`sourceCompatibility`·`JUnit generation`·`build.gradle`·`gradlew`·`## Backend Changes`·`마이그레이션 안전성` | `grep -cF` (사본의 시점은 미상 — 리스크 R5) |
| F12 | `.claude/rules` 를 커밋하면 T31-4 가 실패한다(자기 설치 차단). `hub/install.sh` 는 `hub/bin` 최상위 파일과 `hub/rules/*.md` 만 복사한다 | `tests/run.sh` T31-4 · `hub/install.sh` |
| F13 | 상시 컨텍스트 T26 집합은 `CLAUDE.md`(루트)·`rules/README.md`·`rules/common/*.md`·`rules/workflow/*.md` 다. 하위 디렉토리 CLAUDE.md 는 들지 않는다 | `test_always_on_context_budget` T26-1 공식 |
| F14 | 다음 새 가드 번호: 그룹 마지막 T41(T42 미사용), T31 마지막 T31-13, T38 마지막 T38-5. 동시 워크트리 없음 | `git worktree list` · `tests/run.sh` |

---

## UX Design

N/A — 화면이 바뀌지 않는다(규칙·커맨드·에이전트 문서와 가드). 프리뷰 목업 대상 아님.

### Interaction Changes

| 접점 | 전 | 후 |
|---|---|---|
| `/code-review`(Gradle 프로젝트) | 검증 명령 없음 → Skipped | `./gradlew testClasses`·`test`·`build -x test` |
| `/prp-implement`(uv 프로젝트) | `uv run` 또는 `python -m` 중 애매 | `uv.lock` → `uv run` |
| 빌드 환경 실패(JDK 불일치 등) | 「테스트 실패 = HIGH」로 기록되거나 빌드 파일을 고쳐 우회 | `Blocked (env: …)` 로 따로 기록, 빌드 파일 수정 금지 |
| 설계서(PRP) | 백엔드 칸 없음 | 「Backend Changes」 — 해당 없으면 N/A 한 줄 |
| 다음 `/harness-update`(이 PC) | — | java 2파일이 옛 ECC 사본과 겹쳐 `--force` 확인 1회(백업 남음) |

---

## 설계 결정과 근거

### D1. Python 규칙: 5파일 유지, 본문을 범용으로 다시 쓴다

- **결정**: 파일명·개수(5)는 그대로 두고 본문 전체를 「프로젝트가 이미 고른 것을 따른다」 규칙으로
  바꾼다. 허브 예시·`hub_*.py` 인용을 모두 뺀다. 테스트 프레임워크는 **감지해서 따른다**(pytest 신호:
  `[tool.pytest.ini_options]`·`pytest.ini`·`conftest.py`·dev 의존성 / unittest 신호: `unittest.TestCase`
  하위 클래스 + pytest 설정 없음). 실행은 프로젝트의 환경 관리자(`uv run`·`poetry run`·`python -m`)로.
- **근거**: 옛 규칙의 문제는 예시가 아니라 **기본값**이다 — 「stdlib unittest 기본, pytest 는 CLAUDE.md
  에 적었을 때만」은 대부분의 Python 백엔드에서 거꾸로다(F3·F4). 감지 규칙은 허브(unittest, 루트 CLAUDE.md
  §4)와 A(pytest) 둘 다에서 옳은 답을 낸다. 파일을 줄이면 개수·툼스톤·가드 갱신이 늘고 다른 언어 디렉토리
  형식(README 「Adding a New Language」)에서도 벗어나므로 5파일을 유지한다. `hooks.md` 는 「프로젝트가
  설정한 포매터·린터를 훅에서 돌린다」 한 절로 줄인다.
- **허브와 충돌하지 않음**: 허브 세션에는 범용 규칙과 `hub/CLAUDE.md`(D2)가 함께 로드된다. 범용 규칙은
  「프로젝트가 고른 것」을 가리키고, 허브가 고른 것(stdlib 전용·unittest·`X | None`·frozen dataclass)은
  `hub/CLAUDE.md` 와 루트 CLAUDE.md §2·§4 가 말한다 — 서로 같은 방향이다.
- **보안 항목 보존**: 옛 `security.md` 4항목(argv 리스트·요청 문자열로 경로 조립 금지·토큰은 지역 변수·
  로그 마스킹)은 범용 문장으로 남기고, SQL 바인딩·안전한 로더 2항목을 더한다. `hub/bin` 주석 3곳
  (`hub_release_read.py`·`hub_notify_send.py`·`hub_usage_fetch.py`)이 가리키는 「argv 리스트」·「상수의
  근거 주석」 항목이 범용 규칙에도 남으므로 그 주석은 고치지 않는다.

### D2. 허브 관례는 `hub/CLAUDE.md`(신설, 배포 안 됨)로 옮긴다

| 후보 | 이 저장소에만 적용 | 상시 예산(T26) | 가드·원칙 | 판정 |
|---|---|---|---|---|
| **`hub/CLAUDE.md`** | O — `hub/` 아래 파일을 열 때만 로드(하위 디렉토리 CLAUDE.md) | 영향 없음(F13) | `hub/install.sh` 가 복사하지 않음(F12) | **채택** |
| 루트 `CLAUDE.md` 에 절 추가 | O | +약 2.5KB 상시 | §3 근거 필요 | 기각 — 허브를 안 만지는 세션까지 매번 싣는다 |
| 프로젝트 `.claude/rules/hub-python.md`(`paths: hub/**`) | O | 영향 없음 | **T31-4 가 커밋을 막는다**, §1(a) 의도(이중 로드 차단)를 깨려면 가드를 약화해야 함 | 기각 |
| `hub/rules/` 채널 | **X** — `~/.claude/rules/hub/` 로 user scope 배포 | — | 지금 고치려는 누수를 재현 | 기각 |
| `hub/README.md` 절 | O | 영향 없음 | 자동 로드되지 않음 | 기각 — 읽힐 보장이 없다 |

- **보강**: 루트 CLAUDE.md §2 「허브 런타임」 줄 끝에 포인터 1문장을 둔다(+약 72B 상시). 이유: 하위
  CLAUDE.md 는 `hub/` 아래 파일을 열 때만 붙어서 `tests/hub/*.py` 만 여는 작업에는 안 붙는다. 포인터가
  있으면 자동 로드가 안 되는 경우에도 상시 컨텍스트에서 그 파일을 찾아갈 수 있다. 가장 중요한 두 관례
  (stdlib 전용, unittest)는 이미 루트 §2·§4 에 있다.
- **전제 확인(Task 0)**: F2 는 `paths` 조건부 규칙이 서브에이전트의 Read 로 붙는다는 것까지만 보였다.
  하위 디렉토리 CLAUDE.md 도 같은 Read 기반 로드인지는 구현 첫 단계에서 직접 관측한다(아래 Task 0).
  안 붙어도 포인터가 있으므로 설계는 바뀌지 않는다.

### D3. Java 감지·검증 명령 — 래퍼 우선, 환경 실패는 따로 기록

- `commands/prp-implement.md` Phase 0 표에 `gradlew`/`build.gradle(.kts)` → `./gradlew`,
  `mvnw`/`pom.xml` → `./mvnw` 행을 넣고, `commands/code-review.md` Phase 3 예시·감지 목록·Phase 4 에
  JVM 블록을 넣는다. `agents/implementer.md` 1단계의 「검증 명령 찾는 곳」 목록에도 빌드 파일을 더한다.
- 명령 대응(Gradle | Maven):
  - 타입 체크(main+test 컴파일): `./gradlew testClasses` | `./mvnw -q test-compile`
  - 테스트: `./gradlew test [--tests '<클래스>']` | `./mvnw test [-Dtest=<클래스>]`
  - 빌드 + 설정된 정적 검사: `./gradlew build -x test` | `./mvnw -q verify -DskipTests`
- **래퍼 우선**: 래퍼가 프로젝트가 맞춘 빌드 도구 버전을 고정한다. 시스템 Gradle 8.x 로 7.1 프로젝트를
  돌리면 플러그인 호환이 깨질 수 있다.
- **환경 실패 규칙(신설, 스택 무관)**: JDK·빌드 도구 불일치(F6), 의존성 저장소 접근 불가(F5 의 사설 저장소)
  처럼 코드와 무관하게 명령이 못 도는 경우는 `Blocked (env: <첫 오류 줄>)` 로 기록한다. 통과로 치지 않고,
  테스트 실패(HIGH)와 구분하며, **래퍼·언어 수준·의존성 버전을 고쳐 우회하지 않는다**. 이 규칙이 없으면
  구현자가 빌드를 통과시키려고 래퍼나 `sourceCompatibility` 를 올리는 것이 가장 그럴듯한 실패다.
- Python 감지 행도 함께 바로잡는다: `uv.lock` → `uv run`, `poetry.lock` → `poetry run`, 둘 다 없으면
  `python -m`. 지금 행(「uv / pip — `uv run` or `python -m`」)은 어느 쪽인지 정하지 않는다.

### D4. `rules/java/` — 2파일만 신설(안 J1, 추천)

| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| J0 | 규칙 없음, 커맨드 감지(D3)만 | 개수·문서 변경 0 | Java 8 프로젝트에서 모델의 기본 성향과(이 PC 에서는) 옛 ECC 규칙이 `record`·`var` 를 쓰게 둔다 — Python 에서 고치려는 것과 같은 종류의 어긋남이 남는다 |
| **J1** | `coding-style.md`·`testing.md` 2파일 | 문제의 핵심(언어·프레임워크 버전 게이트, 기존 스택 따르기, 래퍼, JUnit 세대)을 정확히 겨냥. `*.java`·빌드 파일을 열 때만 로드 | 규칙 수 46→48 이 문서·가드 여러 곳에 퍼진다. 이 PC 의 다음 `/harness-update` 에서 `--force` 확인 1회(F8) |
| J5 | 상류 java 5파일 반입 | 내용이 많다 | Java 16~21 전제(F7)라 구버전 프로젝트에 해롭다. 반입·로컬 패치 추적 부담 |

- **J1 근거(YAGNI 판단)**: 대상 프로젝트(B)가 실재하고, 해악도 실재한다(F7 — 컴파일 안 되는 조언).
  추측성 확장이 아니라 관측된 어긋남 하나를 막는 최소 단위다. `patterns`·`security`·`hooks` 는 만들지
  않는다 — Spring 트랜잭션·MyBatis `${}` 두 항목만 `coding-style.md` 의 한 절로 둔다.
- **파일명을 상류와 같게 두는 이유**: README 「Adding a New Language」 형식을 따르고, 옛 ECC 사본이 있는
  PC 에서는 가장 해로운 `coding-style.md`(record·sealed 권장)를 대체한다. 대가로 `NOTICE.md` 에 「상류와
  같은 경로를 쓰는 원저작」으로 적고, 재동기화가 덮어쓰면 T38-1 이 잡게 한다(D6).
- **남는 옛 ECC 파일**(`patterns.md`·`security.md`·`hooks.md`)은 하네스 소유가 아니라 건드리지 않는다
  (소유권 원칙). 대신 새 `coding-style.md` 첫 절에 「빌드 파일의 언어 수준이 다른 어느 규칙·예시의 기능
  권고보다 우선한다」를 적어 같이 로드돼도 결론이 정해지게 한다. 정리 여부는 사용자 결정(질문 2).
- `paths`: `**/*.java`·`**/build.gradle`·`**/build.gradle.kts`·`**/pom.xml`(빌드 파일을 읽을 때도
  버전 게이트가 필요하다). Kotlin(`*.kt`)은 범위 밖.

### D5. 백엔드 고유 주제의 배치 — 규칙이 아니라 설계·구현·검수 자산

- **규칙(rules/)에 두지 않는 이유**: 백엔드 코드는 경로 glob 으로 가려낼 수 없어 조건부 로드가 안 되고,
  상시 규칙(`rules/common`)에 두면 모든 세션이 매번 싣는다(T26). 이 주제가 필요한 시점은 설계·구현·검수
  세 단계뿐이고, 그 단계의 자산은 그 단계에만 로드된다.
- **자리**(기존 자리 우선):
  1. `agents/code-reviewer.md` §5 「Node.js/백엔드 패턴」 → 「백엔드 패턴」으로 스택 중립화하고 4항목
     (트랜잭션 경계·동시 갱신·API 하위 호환·마이그레이션 안전성)을 더한다. 기존 7항목과 예시는 그대로.
     §1 SQL 인젝션 줄에 보간 형태 예시(템플릿 리터럴·f-string·MyBatis `${}`)를 더한다.
  2. `commands/prp-plan.md` 템플릿: 「Security Considerations」 다음에 「Backend Changes」 절(4행 표,
     해당 없으면 `N/A — 이유 한 줄`), 빈칸이던 「Database Validation」에 도구별 예시와 기대 결과, 검증
     체크리스트 1줄.
  3. `agents/design-architect.md` 필수 항목에 「백엔드 고려」 1항목(2와 같은 4축).
  4. `commands/prp-implement.md` Phase 1 LOAD 추출 목록에 「Backend Changes」 1줄.
  5. `commands/code-review.md`: 로컬 모드 HIGH 목록 1줄, PR 모드 표의 Correctness·Completeness 칸 보강.
- 보안 지침(SQL 인젝션·rate limit·최소 권한·백엔드 음성 테스트)은 이미 `rules/common/security.md` 와
  각 자산에 있으므로 늘리지 않는다. role-separation 의 전체 경로 기준은 「데이터 모델·공개 인터페이스(API
  스펙) 변경」이 이미 스키마·API 변경을 덮으므로 고치지 않는다.

### D6. 가드 — 새 그룹 없이 기존 그룹 2곳에 서브체크 1개씩

| ID | 그룹 | 잡는 것 | 원장 |
|---|---|---|---|
| **T38-1 개정** | T38 | `PATCH_CONTRACT_PAIRS` 의 python 토큰 5개 교체 + java 2쌍 추가. case 를 `rules/python/* \| rules/java/*` 로 넓히고 메시지를 「rules 언어 트랙 로컬 계약 토큰 부재」로 | 기존 변조행 sed·토큰 갱신 |
| T38-3(표만) | T38 | 이번에 로컬 패치가 늘어난 벤더링 파일 4개의 새 토큰 4쌍 — 재동기화가 Java 감지·Backend Changes 를 조용히 지우는 것 | 행 추가 없음(T38 헤더가 자백한 표 구동 한계와 같음) |
| **T38-2 개정** | T38 | `UPSTREAM_PYTEST_TOKENS` 에서 `conftest.py` 를 빼고(범용 규칙이 감지 신호로 정당하게 쓴다) 상류 강제 문장 `Use **pytest** as the testing framework` 를 넣는다 | 기존 변조행 sed 갱신(`## Mocking` 절이 사라짐) |
| **T38-6 신설** | T38 | `rules/python/*.md`·`rules/java/*.md` 에 이 저장소 내부 참조(`hub/bin`·`tests/hub`·`hub_<이름>`·`coding-harness`·`★순수`) 0건 — 이번 결함의 재발(허브 코드에서 규칙을 다시 귀납) 차단 | 변조행 1 |
| **T31-14 신설** | T31 | `rules/` 의 스택 디렉토리 파일(common·workflow·README 제외)은 모두 `---` 로 시작하고 frontmatter 에 `paths:` 가 있다 — 없으면 조건부 규칙이 조용히 상시 로드로 바뀌고 T26 도 못 본다. T31-2(workflow 에 `paths:` 없음)의 짝 | 면제행 1(T31-10~13 선례: 사용자 결정 2026-10-08, 전체 검사 시간 보호 — 구현 시 수동 변조 1회) |
| T39-4 원장만 | T39 | 변조 대상 소제목 `## Cross-Module Contracts` 가 사라져 sed 재조준 | 변조행 sed 갱신 |

- 새 그룹 T42 는 쓰지 않는다 — 그룹 레지스트리·`total_tests` 를 건드리지 않는다.
- 상수: `SOURCE_GUARD_ID_FLOOR` 577→579, `LEDGER_MUTATION_ROW_FLOOR` 153→154, `LEDGER_EXEMPT_ROW_RATCHET`
  368→369, `ALWAYS_ON_CONTEXT_BUDGET_BYTES` 56532→편집 뒤 실측(추정 56,774, +242B). 각 상수 위 헤더의
  변경 이력 줄과 `tests/mutations.tsv` 헤더의 인용 사슬, T99-6 의 sed 리터럴을 함께 옮긴다.

### D7. 업무 저장소는 익명으로 적는다

이 저장소는 공개 저장소이고 `docs/prps/` 는 커밋된다. 사용자 업무 저장소 이름·경로·사설 저장소 주소를
이 PRP·배포 파일·커밋 메시지에 적지 않는다(A·B 로만 적는다). 배포되는 규칙의 예시도 일반 명칭
(`OrderServiceTest`, 「SQL 패치 파일」)만 쓴다.

### D8. 하지 않는 단순화

- `readme_prose_actual_count` 의 `agg:conditional` 을 「전체 − 상시」로 일반화하지 않는다 — java 한 줄만
  더한다(수술적 변경).
- `rules/web/hooks.md` 의 `hub/bin/hub_settings.py` 인용은 관찰만 하고 고치지 않는다(이번 범위 밖, T38-6
  범위도 python·java 로 한정).

---

## 파일 구조와 모듈 경계

```
rules/python/{coding-style,hooks,patterns,security,testing}.md   # 배포 · 범용 Python (본문 재작성)
rules/java/{coding-style,testing}.md                             # 배포 · 신설
hub/CLAUDE.md                                                    # 배포 안 함 · 허브 Python 관례 (신설)
agents/{code-reviewer,design-architect,implementer}.md           # 배포 · 백엔드 항목
commands/{code-review,prp-implement,prp-plan}.md                 # 배포 · JVM 감지 · Backend Changes
```

- 레이어 경계(CLAUDE.md §2)는 그대로다: 배포 자산 3종 ↔ install.sh 는 manifest 해시 대장으로만 통신한다.
  새 파일 2개(`rules/java/`)는 `cp -R rules/.` 가 그대로 싣는다 — install.sh 로직 변경은 상수 1개뿐.
- `hub/CLAUDE.md` 는 배포 채널 어디에도 들지 않는다(F12). 삭제·개명 파일이 없으므로 `removals.txt` 는
  바뀌지 않는다.

## 데이터 모델 · 인터페이스(문서 자산의 계약)

이 변경에 실행 코드 타입은 없다. 대신 자산 사이의 계약이 바뀐다.

1. **스택 규칙 파일 계약**(T31-14 가 강제): 첫 줄 `---`, frontmatter 에 `paths:` 목록, 둘째 블록 첫 줄
   `> This file extends [common/<x>.md](../common/<x>.md) with <Lang> specific content.`
2. **T38 계약 토큰 표**(`PATCH_CONTRACT_PAIRS`, (경로, 토큰) 평탄 배열) — 바뀐 뒤 21쌍:

| 경로 | 토큰 | 상태 |
|---|---|---|
| `rules/python/coding-style.md` | `requires-python` | 교체(옛 `Standard Library First`) |
| `rules/python/hooks.md` | `the Project Configures` | 교체(옛 `Entry Points Always Exit 0`) |
| `rules/python/patterns.md` | `Never Block the Event Loop` | 교체(옛 `Pure Modules vs. I/O Modules`) |
| `rules/python/security.md` | `argv List, Never a Shell` | 유지 |
| `rules/python/testing.md` | `test framework the project already uses` | 교체(옛 `Use stdlib`) |
| `rules/java/coding-style.md` | `sourceCompatibility` | 추가 |
| `rules/java/testing.md` | `JUnit generation` | 추가 |
| `commands/code-review.md` | `build.gradle` | 추가 |
| `commands/prp-implement.md` | `gradlew` | 추가 |
| `commands/prp-plan.md` | `## Backend Changes` | 추가 |
| `agents/code-reviewer.md` | `마이그레이션 안전성` | 추가 |
| (나머지 10쌍) | — | 그대로 |

3. **`UPSTREAM_PYTEST_TOKENS`**: `pytest.fixture` · `@pytest.mark` · `import pytest` ·
   `Use **pytest** as the testing framework`(`conftest.py` 제거).
4. **T38-6 패턴**(ERE): `hub/bin|tests/hub|(^|[^[:alnum:]_])hub_[a-z_]+|coding-harness|★순수`
   — `github_` 같은 낱말 안의 `hub_` 는 앞 글자 조건으로 거른다.
5. **커맨드 감지 표 행**(인터페이스): 아래 「커맨드·에이전트 편집 초안」의 표 행 그대로.
6. **PRP 템플릿 절**: `## Backend Changes` — 열 `Area | Applies? | Decision → how it is verified`, 4행.

---

## 규칙 본문 초안 (구현자는 이 문안을 그대로 쓰고, 고칠 때는 PRP 수정 제안부터)

### `rules/python/coding-style.md`

````markdown
---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Python specific content.

## The Project's Toolchain Comes First

Read what the project already pins before writing code, and follow it over any default here:

- **Python version** — `requires-python` in `pyproject.toml` (or `.python-version`) bounds the syntax
  you may use: `X | None` and `match` need 3.10+, `typing.Self` 3.11+. Below 3.10, write `Optional[X]`.
- **Formatter, linter, type checker** — whatever `pyproject.toml` configures (`[tool.ruff]`,
  `[tool.black]`, `[tool.isort]`, `[tool.mypy]`, …). Run those; don't add a second tool or reformat
  code you didn't change.
- **Libraries** — use what the project already depends on (its model library, HTTP client, settings
  loader) instead of re-implementing it with the standard library. A *new* dependency is still an
  explicit, justified proposal — the standard library or an existing dependency first.

## Type Hints

Annotate every public function signature, in the style the codebase already uses.

## Immutability

Make value objects immutable by construction with the model type the project already uses —
`@dataclass(frozen=True)`, a frozen pydantic model, or `NamedTuple`.

## Constants and Private Helpers

- Module-level constants in `UPPER_SNAKE_CASE`. When the value isn't self-evident, say *why* it was
  chosen — a bare number invites someone to change it without knowing what breaks.
- Prefix module-private helper functions with a leading underscore.

## Paths

Use `pathlib.Path` for filesystem paths, not string concatenation.
````

### `rules/python/testing.md`

````markdown
---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Testing

> This file extends [common/testing.md](../common/testing.md) with Python specific content.

## Framework

Use the test framework the project already uses — don't convert existing tests or add a second runner.

- **pytest** — `[tool.pytest.ini_options]` in `pyproject.toml`, a `pytest.ini`, a `conftest.py`, or
  pytest in the dev dependencies.
- **unittest** — test classes subclass `unittest.TestCase` and no pytest configuration exists.

A project with no tests yet: default to **pytest**, and record the choice in the project's
`CLAUDE.md` so later sessions don't decide it again.

## Running

Run through the project's environment manager so the pinned dependencies are used — `uv run …` when
`uv.lock` exists, `poetry run …` when `poetry.lock` exists, otherwise `python -m …` (`python -m pytest`,
`python -m unittest discover -s <dir> -t <root>`). Narrow to the affected path first, then run the
whole suite.

## Async Tests

Follow the async plugin and mode the configuration already sets (e.g. pytest-asyncio's
`asyncio_mode`); don't add event-loop fixtures the configuration already provides.

## Isolation

- Replace the narrowest seam — an attribute of the module under test (pytest `monkeypatch`,
  `unittest.mock.patch.object`) — and restore it after the test.
- Unit tests make no real network or database calls; reach those only through the project's existing
  integration-test setup (its fixtures, containers, or test database).

## Structure

Follow the AAA (Arrange-Act-Assert) structure defined in
[common/testing.md](../common/testing.md).
````

### `rules/python/patterns.md`

````markdown
---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Patterns

> This file extends [common/patterns.md](../common/patterns.md) with Python specific content.

## Expected Failures Get Their Own Exception

Give an expected failure its own exception class instead of letting a raw `OSError`, `KeyError`, or
driver error propagate. At an API boundary, translate it once (e.g. a FastAPI exception handler) into
the error format the API already uses — never send the internal message or traceback to the client.

## Validate at the Boundary

Parse request bodies, configuration, and external responses into typed models at the edge (pydantic
where the project uses it); inner layers take those models, not raw dicts.

## Never Block the Event Loop

Inside `async def`, never call blocking I/O — `requests`, `time.sleep`, a synchronous DB driver, large
file reads. Use the async client the project already has, or offload the call (`asyncio.to_thread`,
Starlette's `run_in_threadpool`). In FastAPI a plain `def` endpoint already runs in a thread pool; an
`async def` endpoint does not.

## Dependencies Through the Framework

Get DB sessions, clients, and settings through the framework's injection mechanism (FastAPI `Depends`,
etc.) rather than module-level globals, so tests can override them.

## Leaf Modules Break Import Cycles

If two modules would otherwise import each other, move the shared piece into a module that imports
neither of them.
````

### `rules/python/security.md`

````markdown
---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

> This file extends [common/security.md](../common/security.md) with Python specific content.

## Subprocess: argv List, Never a Shell

Pass a list of arguments to `subprocess.run`/`subprocess.Popen` and keep `shell=False`. Never build a
command string out of input (shell injection, and portability loss).

## SQL: Bind Parameters

Use the driver's or ORM's parameter binding — `cursor.execute(sql, params)`, SQLAlchemy
`text("... WHERE id = :id")` with bound values. Never format input into SQL with f-strings, `%`, or
`.format()`. An identifier that must vary (a sort column) comes from a fixed whitelist.

## No Path Assembly From Request Strings

Never build a filesystem path directly from request data. Either map a constrained token (a
fixed-length key) to a whitelisted path, or resolve the joined path and confirm it stays under the
base directory (`resolved.is_relative_to(base)`, 3.9+).

## Untrusted Data: Safe Loaders Only

`yaml.safe_load`, never `yaml.load`, `pickle`, or `eval` on data from outside the process.

## Secrets and Logs

- Read secrets from the environment or the project's settings object inside the function that needs
  them; don't keep them in module-level variables.
- Never log credentials. If a tool logs user prompts or other free text, mask token-shaped values
  before writing, and disclose the size cap, retention, and opt-out where the tool is installed.
````

### `rules/python/hooks.md`

````markdown
---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

> This file extends [common/hooks.md](../common/hooks.md) with Python specific content.

## Run the Formatter and Linter the Project Configures

If you add an edit-time hook (PostToolUse) for Python files, have it run the tools the project
configures in `pyproject.toml` — e.g. `ruff format` + `ruff check --fix`, or black + isort — through
its environment manager (`uv run`, `poetry run`). Don't introduce a formatter the project doesn't use.
````

(T38 토큰 `the Project Configures` 는 제목 줄에만 있다 — 본문은 소문자로 둔다.)

### `rules/java/coding-style.md`

````markdown
---
paths:
  - "**/*.java"
  - "**/build.gradle"
  - "**/build.gradle.kts"
  - "**/pom.xml"
---
# Java Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) with Java specific content.

## The Build File Sets the Language Level

Read the project's Java level before writing code — `sourceCompatibility` / `targetCompatibility` /
`java { toolchain { languageVersion } }` in Gradle, `maven.compiler.source` / `maven.compiler.release`
in Maven — and use only what that level compiles. This overrides feature advice from any other rule or
example. On Java 8, for instance: no `var` (10), `List.of`/`Map.of` (9), `List.copyOf` (10),
`Optional.isEmpty()` (11), switch expressions (14), text blocks (15), `record` (16).

The framework version gates APIs the same way: Spring Boot 2.x uses `javax.*` (servlet, validation,
persistence), 3.x uses `jakarta.*`. Don't raise the Java, Spring Boot, or build-tool version as a side
effect of a feature change — that is a decision of its own.

## Follow the Stack Already Chosen

Use what the project already uses instead of introducing an alternative: persistence (MyBatis mapper
XML, JPA, or JdbcTemplate), Lombok or plain accessors, the logging facade and backend, the JSON
library, and the injection style (constructor injection unless the module consistently does otherwise).

## Immutability

`final` fields set through the constructor; return unmodifiable views from public APIs
(`Collections.unmodifiableList` on Java 8, `List.copyOf` on 10+).

## Transactions and SQL

- Spring's `@Transactional` works through a proxy: it does not apply to a call from another method of
  the same class, nor to a private method. By default it rolls back only on unchecked exceptions — set
  `rollbackFor` when a checked exception must roll back. Keep remote calls (HTTP, messaging) out of the
  transaction.
- Bind parameters only: MyBatis `#{}`, never `${}` with request data (`${}` is string substitution);
  JPA/JDBC parameters, never string concatenation. A dynamic identifier (a sort column) comes from a
  fixed whitelist.

## Build Tool

Use the wrapper — `./gradlew`, `./mvnw` — so the build-tool version the project targets is the one
that runs. If the build fails because the JDK or build tool doesn't match (e.g. an old Gradle wrapper
on a newer JDK), report it as an environment problem; don't edit the wrapper, the language level, or
plugin versions to get past it.
````

### `rules/java/testing.md`

````markdown
---
paths:
  - "**/*.java"
  - "**/build.gradle"
  - "**/build.gradle.kts"
  - "**/pom.xml"
---
# Java Testing

> This file extends [common/testing.md](../common/testing.md) with Java specific content.

## Framework

Use the JUnit generation the existing tests use — JUnit 5 (`org.junit.jupiter.api.Test`, with
`useJUnitPlatform()` in Gradle) or JUnit 4 (`org.junit.Test`). Don't mix generations in one test class
or migrate existing tests as part of a feature. A project with no tests yet: default to JUnit 5 (Spring
Boot 2.2+ `spring-boot-starter-test` ships it; on older Spring Boot, use the JUnit 4 the starter brings). Mock with the Mockito the build already provides
(`spring-boot-starter-test` bundles it); on Spring Boot 3.4+ use `@MockitoBean` instead of the
deprecated `@MockBean`.

## Scope

Prefer the narrowest test that covers the change: a plain unit test with constructor-injected mocks,
then a slice test (`@WebMvcTest`, `@JdbcTest`, `@DataJpaTest`, or `@MybatisTest` when its test starter
is on the classpath), and `@SpringBootTest` only when the wiring itself is under test — a full context
starts every connection (database, broker) the application configures.

## Running

- One class: `./gradlew test --tests 'com.example.OrderServiceTest'`, or
  `./mvnw test -Dtest=OrderServiceTest`.
- Whole suite: `./gradlew test`, or `./mvnw test`.
- Tests that need a real database or broker go through the project's existing integration setup
  (Testcontainers, an embedded database, a test profile) — never a shared environment.
````

### `hub/CLAUDE.md`(한국어, 배포 안 함)

현 `rules/python/` 5파일의 허브 관례를 **빠짐없이** 옮긴다. 코드 블록은 줄이고 앵커(함수·상수·클래스
이름)만 남긴다 — 줄 번호를 쓰지 않는다.

````markdown
# hub/ — 허브 Python 관례 (이 저장소 전용)

`hub/` 아래 파일을 열면 Claude Code 가 이 파일을 자동으로 불러온다(하위 디렉토리 CLAUDE.md). 배포 대상이
아니다 — `hub/install.sh` 는 `hub/bin`·`hub/rules` 만 복사한다. 배포되는 범용 Python 규칙(`rules/python/`)은
「프로젝트가 이미 쓰는 것을 따른다」가 기본이고, 아래가 이 프로젝트가 쓰는 것이다(예전에 `rules/python/` 에
있던 관례를 옮겨 왔다 — docs/prps/backend-stack-support.md). 인용은 이름에 건다, 줄 번호를 쓰지 않는다.

## 의존성·버전·테스트
- 표준 라이브러리 전용 — 서드파티 import 0(루트 CLAUDE.md §2, 새 의존성 추가 금지).
- 최소 python 3.10 — `X | None` 유니온을 쓴다(`hub_collect.read_server_heartbeat_mtime_ms`).
- 테스트는 stdlib `unittest` 전용(`tests/hub/test_*.py`, 실행은 루트 CLAUDE.md §4). pytest 를 들이지 않는다.

## 구조
- 순수 모듈/I·O 모듈 분리 — 순수 모듈은 머리말에 `★순수` 를 적는다. `tests/run.sh` T25-10 이 그 모듈의
  `open`·`Path`·`os` 임포트를 막는다(`hub_model.py` 머리말).
- 모듈 간 계약은 `@dataclass(frozen=True)` 로만 — 임시 dict 금지. 머리말에 어떤 dataclass 가 누구와의 계약인지
  적는다(`hub_model.HubConfig`·`HubSnapshot`, 그 밖에 `hub_parse`·`hub_session`·`hub_usage`).
- 예상된 실패는 전용 예외 — 하위 폴백이 흡수하지 않는 `OSError` 를 그대로 올리지 않는다(`hub_collect.HubCollectError`).
- 순환 임포트는 잎 모듈로 끊는다 — 어떤 허브 모듈도 임포트하지 않는 모듈(`hub_server_state.py`).
- 상수 주석은 그 값을 고른 이유를 적는다(`hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS`).
- 모듈 비공개 helper 는 `_` 접두. `_clip_to_length` 는 `hub_workflow`·`hub_transcript`·`hub_subagent` 에 각자
  3줄 사본으로 둔다 — 이유는 `hub_subagent.py` 머리말.

## 훅·statusline 진입점
- 진입점 `main()` 은 항상 0 을 반환한다 — 최상위에서만 `except Exception` 으로 삼키고 helper 안에서는 삼키지
  않는다(`hub_hook.main`·`hub_statusline.main`). 관찰용 훅이 세션 진행을 막으면 안 되기 때문이다.
- 진입점 자체는 밀리초 단위(append + 가벼운 장부)로 끝내고 무거운 일은 분리된 하위 프로세스로 넘긴다
  (`hub_hook.py` 머리말).

## 보안
- 프롬프트 등 자유 텍스트를 기록하면 설치 고지에 상한·보관 기간·끄는 법을 적고(`commands/hub.md` 훅 설치
  고지), 쓰기 전에 `hub_redact.redact_secret_tokens` 로 토큰 모양 값을 가린다.
- subprocess 는 argv 리스트, 셸 문자열 금지(`hub_usage_fetch.py` 의 키체인 조회 호출).
- 요청 문자열로 파일 경로를 만들지 않는다 — 고정 형식 토큰만 뽑아 화이트리스트의 조회 키로 쓴다
  (`hub_server.ALLOWED_REQUEST_PATHS`·`PROJECT_DASHBOARD_PATH_PATTERN`).
- 자격 증명·토큰은 모듈 전역 변수에 두지 않고 쓰는 함수의 지역 변수로 둔다.

## 테스트 관례
- 모듈 상태를 건드리는 테스트는 `setUp` 에서 모듈 상수를 바꿔 끼우고 `tearDown` 에서 되돌린다 — 모듈을 통째로
  mock 하지 않는다(`test_hub_hook.HubHookScenarioTest`).
- 특정 함수 교체는 `mock.patch.object`, 점 경로(`subprocess.Popen`·`sys.stdin`)는 `mock.patch`
  (`test_hub_hook.SpawnsBackgroundCollectTest`).
- 구조는 AAA.
````

---

## 커맨드·에이전트 편집 초안

### `commands/prp-implement.md`

1. Phase 0 표 — 기존 `pyproject.toml or requirements.txt | uv / pip | uv run or python -m` 1행을 아래 3행으로
   바꾸고, `go.mod` 행 뒤에 JVM 2행을 더한다:

   | File Exists | Package Manager | Runner |
   |---|---|---|
   | `uv.lock` | uv | `uv run` |
   | `poetry.lock` | poetry | `poetry run` |
   | `pyproject.toml` or `requirements.txt` (no lock above) | pip | `python -m` |
   | `gradlew` or `build.gradle` / `build.gradle.kts` | gradle | `./gradlew` (wrapper first; `gradle` only when there is none) |
   | `mvnw` or `pom.xml` | maven | `./mvnw` (wrapper first; `mvn` only when there is none) |

2. 「Validation Scripts」 Node 블록 뒤:
   > JVM builds have no scripts block — map the plan's validation levels to lifecycle tasks: type check
   > `./gradlew testClasses` / `./mvnw -q test-compile`; tests `./gradlew test [--tests '<Class>']` /
   > `./mvnw test [-Dtest=<Class>]`; build `./gradlew build -x test` / `./mvnw -q verify -DskipTests`.
   > Python: the tools `pyproject.toml` configures (`[tool.pytest.ini_options]`, `[tool.ruff]`,
   > `[tool.mypy]`), run through the runner above.
3. Phase 1 LOAD 추출 목록, `Security Considerations` 줄 뒤:
   `- **Backend Changes** — transaction, concurrency, compatibility, and migration decisions to build and verify (skip if N/A)`
4. 「Handling Failures → Build Fails」 맨 앞:
   `0. If the cause is the environment — JDK or build-tool version mismatch, dependency repository unreachable — stop and report the first error line. Don't edit the wrapper, the language level, or dependency versions to get past it.`

### `commands/code-review.md`

1. 로컬 Phase 2 Security: `- SQL injection vulnerabilities` →
   `- SQL injection vulnerabilities (queries built by concatenation or interpolation — template literals, f-strings, MyBatis \`${}\`)`
2. 로컬 Phase 2 Code Quality(HIGH), `Missing error handling` 뒤:
   `- Backend changes: writes that must succeed together outside one transaction, check-then-act updates on shared rows, breaking API changes, migrations that break while old and new code run together`
3. Phase 3 표 축약 경로 예시 끝에 `, \`./gradlew test --tests '<관련 테스트 클래스>'\`` 추가.
4. Phase 3 감지 문장: `(\`package.json\`, \`Cargo.toml\`, \`go.mod\`, \`pyproject.toml\`, \`build.gradle\`·\`pom.xml\` 등)`.
5. Phase 3 기록 규칙 끝에:
   `- 빌드 환경 때문에 명령이 돌지 못하면(JDK·빌드 도구 버전 불일치, 의존성 저장소 접근 불가) \`Blocked (env: <첫 오류 줄>)\` 로 기록한다 — 테스트 실패와 구분하되 통과로 치지 않고, 빌드 파일을 고쳐 우회하지 않는다`
6. PR Phase 3 표: Correctness 칸 끝에 `, transaction boundaries`; Completeness 칸 `incomplete migrations` →
   `incomplete or non-backward-compatible migrations and API changes`.
7. PR Phase 4 감지 문장에 `` `build.gradle(.kts)`, `pom.xml` `` 추가. Go 블록 뒤에:

   ````markdown
   **Java / JVM** (has `build.gradle` / `build.gradle.kts` → Gradle, `pom.xml` → Maven) — use the wrapper
   (`./gradlew`, `./mvnw`) when present, `gradle` / `mvn` otherwise:
   ```bash
   ./gradlew testClasses       # Compile main + test (type check)  — Maven: ./mvnw -q test-compile
   ./gradlew test              # Tests                              — Maven: ./mvnw test
   ./gradlew build -x test     # Build + configured static checks   — Maven: ./mvnw -q verify -DskipTests
   ```
   ````
8. PR Phase 4 Python 블록을 다음으로 바꾼다:

   ````markdown
   **Python** (has `pyproject.toml` / `setup.py`) — prefix with `uv run` / `poetry run` when `uv.lock` /
   `poetry.lock` exists:
   ```bash
   pytest  # Tests — `python -m unittest discover` when the project uses unittest
   ```
   Also run the linter / type checker `pyproject.toml` configures (`[tool.ruff]`, `[tool.mypy]`).
   ````
9. `Run only the commands that apply…` 줄 뒤:
   `A command that can't run because of the environment (JDK or build-tool mismatch, dependency repository unreachable) is recorded as \`Blocked (env: <first error line>)\` — neither Fail nor Pass.`

### `commands/prp-plan.md`

1. 템플릿의 `## Security Considerations` 절(음성 테스트 형식 문단까지) 뒤, `## Testing Strategy` 앞:

   ```markdown
   ## Backend Changes

   `N/A — [one-line reason]` when no server, API, or database code changes; otherwise fill only the rows that apply.

   | Area | Applies? | Decision → how it is verified |
   |---|---|---|
   | Transaction boundary — which writes commit together, what a partial failure leaves behind; no remote calls inside the transaction | | |
   | Concurrent updates — two requests changing the same row/resource (conditional update, lock, unique constraint) | | |
   | API compatibility — changed request/response fields, status codes, error format; how existing clients keep working (additive change, versioning, deprecation window) | | |
   | Migration safety — old and new code both run against the schema during rollout (expand → migrate → contract); lock/size impact on large tables; rollback path | | |
   ```

2. 「Database Validation (if applicable)」 블록:

   ````markdown
   ### Database Validation (if applicable)
   ```bash
   # Apply the migration to a scratch copy of the current schema with the project's own tool, then roll it back —
   # Alembic: alembic upgrade head / alembic downgrade -1; Flyway or Liquibase: the project's migrate/validate task;
   # hand-written SQL patch files: apply them in order to a scratch database
   [project-specific db command]
   ```
   EXPECT: Migration applies and rolls back on a scratch database; the currently deployed code still works against the migrated schema
   ````
3. 「Verification → Context Completeness」 끝에 `- [ ] Backend Changes filled, or N/A with a one-line reason`.

### `agents/code-reviewer.md`

1. §1 `**SQL 인젝션** — 파라미터화 쿼리 대신 문자열 연결로 쿼리 구성` →
   `**SQL 인젝션** — 파라미터화 쿼리 대신 문자열 연결·보간으로 쿼리 구성(템플릿 리터럴, f-string, MyBatis \`${}\`)`
2. §5 제목 `### 5. Node.js/백엔드 패턴 (HIGH — 해당 스택일 때만)` → `### 5. 백엔드 패턴 (HIGH — 서버·API·DB 코드일 때만)`.
   기존 7항목·TS 예시 유지, `CORS` 항목 뒤에 4항목:
   ```markdown
   - **트랜잭션 경계** — 함께 성공해야 할 쓰기가 한 트랜잭션에 묶이지 않음(부분 실패 시 불일치), 트랜잭션 안의 외부 호출·긴 작업,
     프록시 기반 트랜잭션이 적용되지 않는 호출(Spring 의 같은 클래스 내부 호출·private 메서드, 체크 예외 롤백 규칙 — `rules/java/coding-style.md`)
   - **동시 갱신** — 조회 후 갱신(check-then-act)으로 같은 행을 바꾸는 경쟁. 조건부 UPDATE·락·유니크 제약으로 막는다
   - **API 하위 호환** — 기존 응답 필드 삭제·개명·타입 변경, 새 필수 요청 필드, 상태 코드·에러 형식 변경을 버전·폐기 기간 없이.
     PRP 「Backend Changes」에 없던 변경이면 「설계문서 불일치」도 함께 적는다
   - **마이그레이션 안전성** — 배포 중 구·신 코드가 함께 도는 동안 깨지는 변경(컬럼 삭제·개명을 한 번에, 기본값·백필 없는
     NOT NULL 추가), 큰 테이블을 오래 잠그는 변경, 되돌릴 방법 없음, 마이그레이션 도구·패치 파일 밖의 스키마 변경. 데이터를 잃는 변경은 CRITICAL
   ```

### `agents/design-architect.md`

「설계 문서에 반드시 포함할 항목」의 `보안 고려` 항목 뒤:

```markdown
- **백엔드 고려**: 서버·API·DB 코드를 바꿀 때만 — 트랜잭션 경계(함께 커밋할 쓰기, 부분 실패 시 남는 상태)·
  동시 갱신(같은 행을 두 요청이 바꿀 때)·API 하위 호환(기존 클라이언트가 계속 동작하는 방법)·DB 마이그레이션
  안전성(배포 중 구·신 코드 공존, 큰 테이블 잠금, 되돌리기) 중 해당하는 것에 결정과 검증 방법을 적는다.
  해당하지 않으면 「해당 없음 — 근거 한 줄」로 끝낸다.
```

### `agents/implementer.md`

구현 절차 1단계 `(테스트 러너, package.json/Makefile/pyproject, README 의 검증 절)` →
`(테스트 러너, package.json/Makefile/pyproject/build.gradle·pom.xml — 래퍼 \`./gradlew\`·\`./mvnw\` 우선, README 의 검증 절)`.

---

## Files to Change (영향 범위)

| 파일 | 동작 | 이유 |
|---|---|---|
| `docs/prps/backend-stack-support.md` | CREATE | 이 설계 |
| `hub/CLAUDE.md` | CREATE | 허브 관례의 새 자리(D2) |
| `rules/java/coding-style.md` | CREATE | D4 |
| `rules/java/testing.md` | CREATE | D4 |
| `rules/python/{coding-style,hooks,patterns,security,testing}.md` | UPDATE ×5 | 본문 범용화(D1) |
| `commands/code-review.md` | UPDATE | JVM 감지·Python 블록·Blocked(env)·백엔드 1줄(D3·D5) |
| `commands/prp-implement.md` | UPDATE | 감지 표·Validation Scripts·LOAD·Build Fails(D3·D5) |
| `commands/prp-plan.md` | UPDATE | Backend Changes·Database Validation·체크 1줄(D5) |
| `agents/code-reviewer.md` | UPDATE | §1 SQL 예시·§5 일반화 + 4항목(D5) |
| `agents/design-architect.md` | UPDATE | 「백엔드 고려」 항목(D5) |
| `agents/implementer.md` | UPDATE | 검증 명령 찾는 곳에 빌드 파일(D3) |
| `CLAUDE.md` | UPDATE | §2 `rules/` 46→48개, 허브 런타임 줄 끝 `hub/CLAUDE.md` 포인터(+약 72B) |
| `rules/README.md` | UPDATE | 첫 문단(「recovered Python ruleset」→ Python·Java 백엔드), 구조도 `java/` 줄, 굵은 목록 `**java/**`, `All 46`→48, `Conditionally loaded (30 files)`→32, `java/` (2 files) 불릿(+약 170B) |
| `README.md` | UPDATE | 20행 표(46→48, Java), 100행(46→48·30→32 조건부), 104행 합계 58→60, 109·244행 `실측 <n>B`(T26 실측값), 230행 문장, 「rules 구성」 표에 `java/ \| 2 \| 조건부` 행, 파일 구조도 `rules/` 46→48·`java/` 줄·`hub/` 줄에 `hub/CLAUDE.md` 언급·`docs/prps/` 96→97, 「rules 구성」 아래 짧은 「백엔드 지원」 절(4행 표 + 허브 관례 위치 1줄) |
| `NOTICE.md` | UPDATE | 아래 「NOTICE.md 편집 목록」 |
| `install.sh` | UPDATE | `RULES_FILE_COUNT=46` → 48 |
| `tests/run.sh` | UPDATE | 아래 「tests/run.sh 편집 목록」 |
| `tests/mutations.tsv` | UPDATE | T38-1·T38-2·T39-4 행 sed/토큰 갱신, T38-6 변조행·T31-14 면제행 추가, 헤더 인용 사슬 3곳, T99-6 sed 리터럴 |
| `tests/hub/test_hub_session_cost.py` | UPDATE | 4행 docstring 의 `rules/python/testing.md 의 Test Isolation 관례` → `hub/CLAUDE.md 의 테스트 관례`(이 변경이 만든 낡은 포인터, 주석 1줄) |

**고치지 않는 참조(확인함)**: `hub/bin/hub_release_read.py`·`hub_notify_send.py`(argv — 범용 규칙에 남음),
`hub/bin/hub_usage_fetch.py`(상수 근거 주석 — 범용 규칙에 남음), `tests/run.sh` 의 역사 주석(202·1019·
9076·10768행 부근 — 그 시점 기록), `docs/prps/*.md`(이력), `removals.txt`(삭제·개명 없음).

### NOTICE.md 편집 목록

1. §3 「상류 유래 경로·본문 재작성」 문단: 끝에 「이후 `docs/prps/backend-stack-support.md` 가 본문을 범용
   Python 규칙(프로젝트의 버전·테스트 프레임워크·도구·의존성을 따른다)으로 다시 썼고, 허브 관례는 배포되지
   않는 `hub/CLAUDE.md` 로 옮겼다」를 더하고, 44.4% 매칭 수치 문단에 「(`4be8f58` 판본 기준 — 재작성 전)」을
   붙인다.
2. 같은 위치에 `rules/java/` 2개 문장: 「상류에 같은 경로(`rules/java/coding-style.md`·`testing.md`)가 있으나
   상류 본문을 반입한 적이 없는 원저작이다 — 상류 java 트랙은 Java 16~21 전제라 이 저장소의 구버전 지원
   목적과 반대다. 재동기화 보호 대상(§5)」.
3. 「원저작」 문단의 `rules/` 46개 집계 → 48개(파생 36 + python 5 + java 2 + 원저작 5).
4. §5 표: `rules/README.md` 행 수량 `(37→42→46)` → `(37→42→46→48)`·java 반영. python 5행의 「패치 요지」를
   범용 규칙 요지로, 근거에 이 PRP 추가. `commands/code-review.md`·`prp-implement.md`·`prp-plan.md`·
   `agents/code-reviewer.md` 행 「패치 요지」에 이번 로컬 패치(JVM 감지·Blocked(env)·Backend Changes·
   Database Validation·백엔드 패턴 일반화) 추가.
5. §5 「재동기화 규칙」에 문단 1개: 「상류 `rules/java/` 트랙은 반입하지 않는다 — 이 저장소의 `rules/java/`
   2개는 같은 경로의 원저작이라 반입하면 덮인다. T38-1 이 계약 토큰(`sourceCompatibility`·`JUnit generation`)
   으로 덮어쓰기를 잡는다.」
6. 「커버리지 상태」 표: python 5행 「잠기는 성분」을 새 토큰으로, 커맨드 3·code-reviewer 행에 새 토큰(T38-3)
   추가, python 행들에 「내부 참조 부재(T38-6)」 추가. 행 수(26)·세 버킷 합은 그대로.

### tests/run.sh 편집 목록

1. T1·T4·T5(`test_scope_project_new_install`·`test_partial_damage_recovery`·
   `test_scope_project_ignores_existing_claude_md`): `assert_equals 46` 과 메시지·주석의 46 → 48(3곳).
2. `ALWAYS_ON_CONTEXT_BUDGET_BYTES` 56532 → 편집 뒤 실측값. 위 헤더에 이력 1항목(무엇이 왜 늘었나:
   rules/README.md 의 java 트랙 반영 + CLAUDE.md 허브 관례 포인터). README.md `실측 <n>B` 2곳을 같은 값으로.
3. `README_PROSE_DECLARATIONS` 에 `` '`java/` \([0-9]+ files\)' "dir:java" `` 행 추가,
   `readme_prose_actual_count` 의 `agg:conditional` 합에 `java_count` 추가.
4. T38(`test_vendor_patch_contract_tokens` 와 그 앞 배열·헤더 주석):
   - `PATCH_CONTRACT_PAIRS` — 「데이터 모델」 2절의 표대로(교체 4·추가 6).
   - `UPSTREAM_PYTEST_TOKENS` — `conftest.py` → `Use **pytest** as the testing framework`. 바로 위 「네 토큰
     모두 0건」 주석을 새 목록 기준으로.
   - case `rules/python/*)` → `rules/python/* | rules/java/*)`, 메시지 `T38-1: rules 언어 트랙 로컬 계약 토큰 부재 — …`.
   - T38-6 신설(T38-2 블록 뒤): 「데이터 모델」 4절의 패턴으로 `rules/python/*.md`·`rules/java/*.md` 를 `grep -nE`,
     걸리면 `note_failure "T38-6: rules 언어 트랙에 이 저장소 내부 참조가 있음 — <상대경로>:<첫 일치 줄>"`.
   - `test_desc`·헤더 주석(항목 2 설명, 기제 (a)(b), 한계 문단)에 java·T38-6 반영. **헤더는 함수 정의 바로 앞의
     연속 주석 블록으로 유지한다**(T37-13 이 그 블록만 본다).
5. T31(`test_rules_workflow_guardrails`): T31-2 뒤에 T31-14 —
   `find "$REPO_ROOT/rules" -mindepth 2 -type f -name '*.md' ! -path "*/rules/common/*" ! -path "*/rules/workflow/*"`
   각 파일의 첫 줄이 `---` 이고 frontmatter(첫 `---` ~ 다음 `---`) 안에 `^paths:` 가 있는지. 아니면
   `note_failure "T31-14: 스택 규칙에 paths: frontmatter 가 없음(상시 로드로 전락) — <상대경로>"`.
   `test_desc` 를 `(T31-1~T31-14)` 로. 헤더 주석에 T31-14 한 문단.
6. `SOURCE_GUARD_ID_FLOOR` 577→579, `LEDGER_MUTATION_ROW_FLOOR` 153→154, `LEDGER_EXEMPT_ROW_RATCHET` 368→369 —
   각 헤더에 이력 1항목(신설 T31-14·T38-6, 개정 T38-1·T38-2 는 같은 ID).

### tests/mutations.tsv 편집 목록

| ID | 대상 | sed | 기대 그룹 | 기대 토큰 |
|---|---|---|---|---|
| T38-1(갱신) | `rules/python/testing.md` | `s/test framework the project already uses/pytest framework/` | T38 | `T38-1: rules 언어 트랙 로컬 계약 토큰 부재` |
| T38-2(갱신) | `rules/python/testing.md` | `s/^## Framework$/## Framework\nimport pytest/` | T38 | 그대로 |
| T39-4(갱신) | `rules/python/patterns.md` | `s/^## Validate at the Boundary$/## Validate at the Boundary (models.py:999)/` | T39 | 그대로 |
| **T38-6(신설)** | `rules/python/patterns.md` | `s/^## Leaf Modules Break Import Cycles$/## Leaf Modules Break Import Cycles (see hub_server_state.py)/` | T38 | `T38-6: rules 언어 트랙에 이 저장소 내부 참조` |
| **T31-14(신설, 면제)** | `tests/run.sh` | `-` | `-` | `-`(면제 사유: T31-10~13 과 같은 사용자 결정 2026-10-08 — 변조 검증은 구현 시 수동 1회) |

헤더: `LEDGER_EXEMPT_ROW_RATCHET(368 — …→368` 사슬에 `→369`, `LEDGER_MUTATION_ROW_FLOOR(153 — …→153` 에
`→154`, `SOURCE_GUARD_ID_FLOOR(577 — …` 에 `→579`. T99-6 sed `s/LEDGER_MUTATION_ROW_FLOOR(153/…(154/` →
`s/LEDGER_MUTATION_ROW_FLOOR(154/LEDGER_MUTATION_ROW_FLOOR(155/`. 변조 sed 에 작은따옴표가 든 제목을 쓰지
않으려고 python 규칙 제목을 그렇게 골랐다(`Never Block…` 등).

## NOT Building

- Kotlin·Go·Node 백엔드 전용 규칙(Node 백엔드는 기존 TS 규칙·검수 §5 로 충분), 상류 java 트랙의
  `patterns`·`security`·`hooks` — 관측된 문제가 없다.
- FastAPI·Spring·JPA 심화 가이드 — 규칙은 어긋남을 막는 최소 단위만.
- Python/Java 편집 시 자동 포매팅 훅(PostToolUse) 배포.
- 검수 단계에서 DB 마이그레이션 실제 실행 — DB 가 필요하고 공유 환경을 건드릴 위험이 있다. 설계서의
  Database Validation 이 맡는다.
- 이 PC 에 남은 옛 ECC 규칙 10개 디렉토리 정리 — 하네스 소유가 아니다(소유권 원칙). 사용자 결정.
- 업무 백엔드 A·B 의 CLAUDE.md 작성 — 각 프로젝트의 몫(권고: §4 검증 명령, B 는 쓸 JDK 경로 명시).
- `docs/coding-harness-intro.html`(게시된 소개 페이지 원본)의 「46개」 3곳 — 고치면 재게시가 필요하다. 사용자 판단.
- `VERSION` 올리기 — 릴리스 때만(CLAUDE.md §5).
- 상류 ECC 재동기화.

---

## Step-by-Step Tasks

권장 커밋 단위: ①Task 0~2(Python 분리) ②Task 3~4(Java·백엔드 자산) ③Task 5~6(수량·문서·가드). 각 커밋 뒤
스위트가 녹색이어야 하므로 ①에서도 T38 토큰·원장(Task 6 의 python 부분)을 함께 고친다.

### Task 0: 하위 디렉토리 CLAUDE.md 로드 관측(전제 확인)
- **ACTION**: `hub/CLAUDE.md` 를 먼저 만든 뒤, **그 파일을 아직 읽지 않은 새 서브에이전트**(예: Explore)에게
  `hub/bin/hub_model.py` 를 Read 하게 하고, 그 서브에이전트의 응답이 아니라 **세션 기록(JSONL)** 에서 그 Read
  직후 `hub/CLAUDE.md` 내용이 첨부로 붙었는지 grep 한다. 또는 구현자 자신이 같은 조건(해당 파일 미열람)에서
  Read 해 system-reminder 로 붙는지 직접 본다(F2 와 같은 관측법).
- **GOTCHA**: 서브에이전트에게 「지침을 인용하라」고 묻는 확인은 API 에 막힌다 — 관측은 기록이나 자기 컨텍스트로.
- **VALIDATE**: 붙으면 그대로 진행. 안 붙으면 설계 변경 없이 진행하되(루트 포인터가 대체) 완료 보고에 결과를 적는다.

### Task 1: `hub/CLAUDE.md` 생성 + 루트 포인터 + 테스트 주석
- **IMPLEMENT**: 위 초안. 루트 CLAUDE.md §2 「허브 런타임」 줄 끝에 ` 코드 관례는 \`hub/CLAUDE.md\`(hub/ 파일을 열면 자동 로드).`
  `tests/hub/test_hub_session_cost.py` 4행 docstring 의 참조 교체.
- **MIRROR**: 옛 `rules/python/*.md` 의 「이름에 건 앵커, 줄 번호 없음」 관례.
- **GOTCHA**: 옛 5파일 관례를 하나도 빠뜨리지 않는다 — 옮기기 전 옛 5파일의 소제목 20개를 체크리스트로 쓴다.
- **VALIDATE**: `python3 -B -m unittest discover -s tests/hub -t .`(주석만 바뀜 — 회귀 없음). `__pycache__` 를 남기지 않는다.

### Task 2: `rules/python/` 5파일 재작성 + T38 python 부분
- **IMPLEMENT**: 위 초안 그대로. `tests/run.sh` T38 표의 python 토큰 4개 교체, `UPSTREAM_PYTEST_TOKENS` 갱신,
  T38-6 신설, 원장 T38-1·T38-2·T39-4 갱신 + T38-6 행, 상수(`SOURCE_GUARD_ID_FLOOR`·`LEDGER_MUTATION_ROW_FLOOR`)·헤더·T99-6.
- **GOTCHA**: 새 본문에 `파일명.py:<숫자>` 꼴을 쓰지 않는다(T39-4 래칫 1). `planner`·`architect` 같은 미배포
  에이전트 이름을 쓰지 않는다(T29). T38-6 패턴에 걸리는 `hub_` 낱말이 없는지 `grep -nE` 로 먼저 본다.
- **VALIDATE**: `bash tests/run.sh --only T12,T13,T29,T38,T39` 녹색. 원장 변조 2건(T38-6·T39-4)은 K6 가 판정.

### Task 3: `rules/java/` 2파일 생성 + 수량 전파
- **IMPLEMENT**: 위 초안. `install.sh` `RULES_FILE_COUNT=48`, CLAUDE.md §2 48개, T1·T4·T5 의 46→48,
  `rules/README.md`·`README.md` 수량·구조도, `README_PROSE_DECLARATIONS`·`agg:conditional`, T38 java 2쌍과 case 확장.
- **GOTCHA**: 수량 문자열은 여러 곳에 박혀 있다 — 편집 뒤 `grep -rn '\b46\b' README.md rules/README.md CLAUDE.md install.sh`
  와 `grep -n 'assert_equals 46' tests/run.sh` 가 0건이어야 한다(`T25-46` 등 무관한 ID 제외). `30개 조건부`·`(30 files)`·
  `58개 파일` 도 같이.
- **VALIDATE**: `bash tests/run.sh --only T1,T4,T5,T12,T13,T29,T30,T38,T39`.

### Task 4: 커맨드 3 · 에이전트 3 편집
- **IMPLEMENT**: 「커맨드·에이전트 편집 초안」 그대로. T38 표에 커맨드·code-reviewer 토큰 4쌍.
- **GOTCHA**: T31-13 이 잠근 토큰(`Mandatory Security Checks`·`malicious-input negative test`·`Reproduction`·
  `## Security Considerations` 등)을 지우거나 바꾸지 않는다 — 덧붙이기만 한다. `commands/` 안에 `/prp-xxx`·
  `/code-review` 를 새로 쓰면 실재하는 커맨드여야 한다(T17).
- **VALIDATE**: `bash tests/run.sh --only T17,T22,T31,T38`.

### Task 5: T31-14 + NOTICE.md + README 「백엔드 지원」 절
- **IMPLEMENT**: T31-14(위 목록), 원장 면제행, `LEDGER_EXEMPT_ROW_RATCHET` 369, `SOURCE_GUARD_ID_FLOOR` 579 확정.
  NOTICE.md 편집 목록 1~6. README 절.
- **VALIDATE**: 수동 변조 1회 — 저장소 사본(미러)에서 `rules/java/testing.md` 의 `paths:` 줄을 지우고
  `--only T31` 이 `T31-14` 로 실패함을 확인한 뒤 되돌린다(실제 `$HOME` 에 설치하지 않는다).

### Task 6: T26 실측·확정
- **IMPLEMENT**: `cat CLAUDE.md rules/README.md rules/common/*.md rules/workflow/*.md | wc -c` 를 재고 상수·
  헤더 이력·README 2곳을 그 값으로(추정 56,774).
- **VALIDATE**: `bash tests/run.sh --only T26,T39`.

---

## Security Considerations (보안 고려)

| Area | Applies? | Threats → mitigation → negative test |
|---|---|---|
| Trust boundary | 간접 — 실행 코드는 없지만 **보안 지침 자체**가 바뀐다 | ① 범용화하며 Python 보안 항목이 빠짐 → 옛 4항목을 범용 문장으로 유지하고 SQL 바인딩·안전 로더를 더함, `argv List` 토큰은 T38-1 이 계속 잠금 → 검수자가 옛 `security.md` 4절과 새 절을 1:1 대조. ② 구현자가 빌드 실패를 빌드 파일 수정으로 우회(래퍼·저장소 설정을 느슨하게) → 「환경 실패는 보고, 빌드 파일 수정 금지」 규칙(D3) → 음성 확인: 규칙 문안에 `Don't edit the wrapper` 류 문장이 `prp-implement`·`code-review`·`java/coding-style` 세 곳에 있음 |
| Sensitive data | 예 — 공개 저장소 문서 | 업무 저장소 이름·경로·사설 Maven 저장소 주소가 PRP·배포 규칙·커밋 메시지에 새어 나감 → 익명 표기(D7) → 음성 테스트: 검수자는 오케스트레이터가 따로 알려준 두 업무 저장소 이름과 사설 저장소 주소로 이 PRP·변경 파일 전체를 `grep -n` 해 0건을 확인한다(이름을 이 문서에 적지 않는다) |
| AuthN/AuthZ | 아니오 | 인증·권한 코드 변경 없음 |
| New dependencies | 아니오 | 새 패키지·스크립트 없음(문서·bash 가드만) |

음성 테스트는 아래 테스트 계획 TP-9·TP-10 으로 옮겼다.

## Backend Changes

N/A — 이 저장소의 서버·API·DB 코드는 바뀌지 않는다(배포 문서와 테스트 가드만).

---

## Testing Strategy (테스트 계획)

이 변경의 「순수 로직」은 bash 정적 가드다. 케이스:

| # | 대상 | 입력/상황 | 기대 |
|---|---|---|---|
| TP-1 | T38-1 | python 5·java 2 토큰이 모두 있는 현재 트리 | 통과 |
| TP-2 | T38-1(원장) | `testing.md` 의 `test framework the project already uses` 를 지움 | `T38-1: rules 언어 트랙…` 로 실패 |
| TP-3 | T38-1(수동) | `rules/java/coding-style.md` 의 `sourceCompatibility` 를 지운 사본 | T38-1 로 실패(java 가 case 확장으로 T38-1 에 들어갔는지) |
| TP-4 | T38-2 | `## Framework` 아래 `import pytest` 삽입 | T38-2 로 실패 |
| TP-5 | T38-2 | 범용 문안의 `conftest.py` 언급 | 통과(토큰 목록에서 뺐다) |
| TP-6 | T38-6 | python 규칙 제목에 `hub_server_state.py` 삽입 | T38-6 로 실패 |
| TP-7 | T38-6 | 본문에 `github_token` 같은 낱말(사본에서) | 통과(앞 글자 조건) |
| TP-8 | T31-14(수동) | `rules/java/testing.md` 의 `paths:` 줄 삭제 | T31-14 로 실패. 스택 파일 32개(설계 중 확인한 기존 30개 + java 2) 전부 통과 |
| TP-9 | 보안 지침 보존(검수 대조) | 옛 `security.md` 4절 ↔ 새 `security.md` | 4절 모두 대응 문장 존재 |
| TP-10 | 비공개 표기(검수) | 업무 저장소 이름·사설 주소로 grep | 0건 |
| TP-11 | T39-1 | `rules/README.md` 의 `java/` (2 files)·`(32 files)`·`All 48` | 실측과 일치 |
| TP-12 | T30-1·T1·T4·T5 | 설치 샌드박스 | 48개 |
| TP-13 | T26 | 편집 뒤 | 상수 = 실측, README 2곳 = 같은 값 |
| TP-14 | T13 | java 2파일의 `../common/*.md` 상대 링크 | 설치 뒤에도 해석됨 |
| TP-15 | Task 0 | 하위 CLAUDE.md 로드 관측 | 결과 기록(붙음/안 붙음) |

허브 단위 테스트는 주석 1줄만 바뀌므로 회귀 확인으로 1회 돌린다.

## Validation Commands

### 정적·단위
```bash
bash -n install.sh && bash -n hub/install.sh
python3 -m py_compile hub/bin/*.py      # 돌린 뒤 생긴 __pycache__ 는 지운다(T22-138 거짓 실패 방지)
python3 -B -m unittest discover -s tests/hub -t .
```
EXPECT: 오류 0

### 영향 그룹
```bash
bash tests/run.sh --only T1,T4,T5,T12,T13,T17,T22,T26,T29,T30,T31,T38,T39
```
EXPECT: 전부 통과

### 전체(메인 세션이 커밋 직전 1회 — 백그라운드 실행 + 완료 알림, sleep 폴링 금지)
```bash
bash tests/run.sh
```
EXPECT: 회귀 없음, K6 가 T38-1·T38-2·T38-6·T39-4 변조행을 판정

### Manual Validation
- [ ] Task 0 관측 결과를 완료 보고에 적었다
- [ ] TP-3·TP-8 수동 변조를 저장소 사본에서 확인하고 되돌렸다
- [ ] (설치 뒤, 사용자 `/harness-update` 이후) Python 백엔드에서 `.py` 를 열면 붙는 규칙에 `hub_`·unittest 기본 문구가 없고,
      Java 프로젝트에서 `.java` 를 열면 `rules/java/` 2파일이 붙는다

## Acceptance Criteria
- [ ] 모든 Task 완료, 위 검증 명령 통과
- [ ] `rules/python/*.md`·`rules/java/*.md` 에 저장소 내부 참조 0건(T38-6)
- [ ] 옛 `rules/python/` 의 허브 관례가 `hub/CLAUDE.md` 에 빠짐없이 있다(소제목 체크리스트)
- [ ] 수량 46/30/58 문자열이 문서·상수·테스트에 남지 않았다(무관한 ID 제외)
- [ ] 업무 저장소 식별 정보 0건

## Completion Checklist
- [ ] 문안은 PRP 초안과 같다(달라졌으면 PRP 수정 제안을 먼저 했다)
- [ ] T31-13 잠금 토큰을 건드리지 않았다
- [ ] 상수 변경마다 헤더 이력 1항목이 있다
- [ ] 범위 밖 항목에 손대지 않았다

---

## 리스크와 대안

| # | 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|---|
| R1 | 하위 디렉토리 CLAUDE.md 가 서브에이전트 Read 로 붙지 않음 | 낮음(F2 와 같은 Read 기반 로드로 판단) | 허브 작업 때 관례 누락 | Task 0 관측 · 루트 포인터 · 핵심 2개(stdlib·unittest)는 루트 §2·§4 에 이미 있음 · T25-10 의 기계적 강제는 그대로 |
| R2 | 이 PC 의 다음 `/harness-update` 가 java 2파일 충돌로 `--force` 를 요구(F8) | 확실 | 확인 1회, `.bak-<시각>` 사본 2개가 남음(`.md` 로 끝나지 않아 규칙으로 로드되지 않는다) | 완료 보고·릴리스 노트에 미리 안내 |
| R3 | 옛 ECC `java/patterns.md` 등이 계속 Java 16+ 를 권함 | 이 PC 에서 확실 | 같은 컨텍스트에 상충 조언 | 새 `coding-style.md` 의 우선 문장 · 사용자 정리 결정(질문 2) |
| R4 | 범용화로 허브 세션이 예시를 잃음 | 중간 | 허브 코드 스타일 표류 | `hub/CLAUDE.md` 가 앵커를 그대로 보존 |
| R5 | 계약 토큰의 상류 부재를 시점 미상의 로컬 ECC 사본으로만 확인(F11) | 낮음 | 재동기화 되돌림을 못 잡음 | 구현 때 네트워크가 되면 상류 raw 원문으로 재확인(선택) · 토큰은 상류 문체에 없는 문구로 골랐다 |
| R6 | 수량 문자열 하나를 놓쳐 스위트가 빨개짐 | 중간 | 재작업 | Task 3 의 grep 확인 · T39·T30 이 바로 알려준다(의도된 신호) |
| R7 | 모든 PRP 에 「Backend Changes」 N/A 한 줄이 늘어남 | 확실 | 문서 잡음 소폭 | 보안 절과 같은 「N/A 한 줄」 형식 · 사용자 결정(질문 3) |
| R8 | 규칙 문안의 버전 사실 오류(예: 기능 도입 버전) | 낮음 | 잘못된 게이트 | 검수자가 문안의 버전 표기를 공식 문서와 대조 |

**검토했으나 채택하지 않은 대안**
- **A1 — 옛 Python 규칙을 두고 「프로젝트 설정이 우선」 한 줄만 추가**: 변경은 작지만, 허브 예시가 계속
  「기본값」으로 읽히고 「stdlib 우선」 문장이 FastAPI 프로젝트의 기존 의존성(pydantic 등) 사용과 정면으로
  부딪힌다. 우선 문장 하나로 다섯 파일의 기본값을 뒤집는 구조는 세션마다 판정이 갈린다(F4 와 같은 문제).
- **A2 — 허브 관례를 프로젝트 `.claude/rules/hub-python.md`(`paths: hub/**`)로**: 경로 조건부라 가장 정밀하지만
  T31-4 를 약화해야 하고, 그 가드가 막는 자기 설치·이중 로드의 구멍을 다시 연다.
- **B — 백엔드 주제를 `rules/common/backend.md` 로**: 경로로 가려낼 수 없어 상시 로드가 되고(T26 +약 1.5KB, 모든
  세션), 벤더링 공통층에 새 파일을 더하게 된다.
- **J0·J5** — D4 표.

## 사용자 결정 필요 사항

1. **Java 규칙 2파일 신설(J1, 추천) vs 커맨드 감지만(J0)** — J1 이면 규칙이 46→48개가 되고, 이 PC 의 다음
   `/harness-update` 에서 덮어쓰기 확인을 한 번 묻는다(옛 ECC java 2파일은 백업으로 남는다). J0 이면 그 확인은
   없지만 Java 8 프로젝트에서 `record`·`var` 같은 컴파일 안 되는 문법을 막을 규칙이 없다.
2. **이 PC 에 남은 옛 ECC 규칙 10개 언어 디렉토리**(하네스 관리 밖) — 그대로 두면 `java/patterns.md` 등의
   Java 16+ 권고가 계속 같이 로드된다(새 규칙의 우선 문장으로 완화). 지우면 깔끔하지만 하네스가 대신 지우지는
   않는다 — 사용자가 직접.
3. **모든 설계서에 「Backend Changes」 칸 추가** — 백엔드가 아닌 작업에서는 `N/A` 한 줄이 늘어난다.

## Notes

- 메인 세션 브리프의 「업무 백엔드 A 의 CLAUDE.md 에 테스트 언급이 없다」는 정확히는 「CLAUDE.md → AGENTS.md 가
  pytest 문서를 가리키기만 한다」였다(F3). 결론(옛 규칙이 애매하게 이긴다)은 같다.
- 관찰(범위 밖): `rules/web/hooks.md` 가 `hub/bin/hub_settings.py` 를 참조 구현으로 인용한다 — 같은 종류의
  「저장소 내부 참조가 배포 규칙에 있음」이지만 이번 범위(python·java)가 아니다.
- 관찰(범위 밖): `commands/code-review.md` PR 모드는 프로젝트 CLAUDE.md 의 검증 명령을 먼저 보라는 문장이 없다.
  감지 표가 그 대체인데, 프로젝트 지침이 있으면 그것이 정본이다 — 필요하면 별도 작업.
