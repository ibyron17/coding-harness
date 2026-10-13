# Claude Code 개발 환경 배포

개인 Claude Code 워크플로우, 코드 품질 규칙, 에이전트 설정을 독립 git 레포로 패키징했다. 어느 프로젝트든 동일한 개발 환경을 재구성할 수 있다.

**주요 특징**

- md 문서가 곧 실행 명세다 — 커맨드·에이전트·규칙이 모두 마크다운 파일이고, Claude가 그 파일을 그대로 읽어 수행한다
- 설치는 순수 bash 스크립트 하나(`install.sh`)이며 외부 의존성이 없다
- manifest(`.coding-harness.json`) 기반 자동 업데이트 — 설치 이후에는 `/harness-update` 한 줄로 실행한다
- 레포가 배포한 파일만 관리하는 소유권 원칙 — 대상 디렉토리에만 있는 다른 파일은 건드리지 않는다(예외: `__pycache__`)
- 작업 규모에 따라 설계→구현→검수(전체 경로)와 구현→검수(축약 경로)로 나뉘는 개발 워크플로우를 규정한다

**기능 요약**

| 구성 | 내용 |
|------|------|
| 설치/업데이트 | `install.sh`(project/user scope, dry-run, force) · `/harness-update` |
| 워크플로우 커맨드 | `prp-prd → prp-plan → prp-implement → prp-pr` 체인 + `prp-commit`·`code-review` |
| 에이전트 | `design-architect`(설계)·`implementer`(구현)·`code-reviewer`(검수)·`explore`(탐색) |
| 규칙 | JS/TS·React·웹·RN·Python 스택 큐레이션 46개(공통·workflow 16개 항상 로드, 나머지 조건부) |
| 허브 | `/hub` — 여러 프로젝트 진행 상황을 한 페이지에 집계, 진행 기록(대시보드) 포함(별도 설치) |

## 설치

### AI 에이전트로 설치 (대화형)

> **이 절은 에이전트에게 주는 지시문이다.** 사람이 셸에서 직접 설치하려면 아래 「기본 사용법」으로.
> 사용자가 이 레포 URL을 붙여넣고 "설치해줘"라고 하면 아래 순서대로 수행한다.

1. **레포 확보** — 이미 로컬에 clone 돼 있으면 그 경로를 쓴다. 없으면 **설치 대상 프로젝트
   바깥에 clone 한다**(예: `~/works/coding-harness`). 대상 프로젝트 안에 clone 하면 남의 레포가
   프로젝트 트리에 그대로 남는다.
2. **계획 확인** — 대상 프로젝트 루트에서 `<repo>/install.sh --scope project --dry-run` 을 실행하고
   출력을 사용자에게 보고한다. `--scope` 는 생략할 수 없다.
3. **설치** — `--dry-run` 없이 재실행한다. exit 0 이면 4단계로.
   - **exit 1 인 경우**: 이전에 설치한 rules/agents/commands 파일이 그 뒤 수정됐다는 뜻이다
     (`CLAUDE.md` 는 배포 대상이 아니라서 충돌 대상도 아니다).
     **자동으로 `--force` 를 붙이지 않는다.** 차이 파일 목록을 그대로 보여주고 `--force`
     여부를 확인받는다.
4. **진행 기록(대시보드)은 허브 기능이다** — 허브는 coding-harness 와 별도로 설치한다.
   진행 상황 기록이 필요하면 `hub/README.md` 를 안내한다. 허브 사용자가
   `install.sh` 를 손으로 돌렸다면 `hub/install.sh` 도 함께 돌린다 — `/harness-update` 는 이 둘을
   자동으로 함께 갱신하지만, `install.sh` 를 직접 재실행하는 경로는 허브 자산을 갱신하지 않는다.
5. **최종 보고** — 반영된 파일 수를 한 줄로 보고한다. 3단계에서 install.sh 가 **전역 커맨드
   불일치 경고**를 냈다면, 이 머신에서는 전역 사본이 우선하므로 `install.sh --scope user` 로
   전역도 갱신하라고 함께 안내한다.

### 기본 사용법

**레포 받기** (한 번만)

```bash
# 설치 대상 프로젝트 바깥에 clone 한다 — 프로젝트 안에 두면 이 레포가 그 트리에 섞인다
git clone https://github.com/ibyron17/coding-harness.git ~/works/coding-harness
```

**프로젝트 레벨 설치** (현재 프로젝트에 적용)

```bash
# 설치하려는 프로젝트 디렉토리에서 실행
cd /path/to/my-project
/path/to/coding-harness/install.sh --scope project
```

**사용자 레벨 설치** (`~/.claude` 에 전역 적용)

```bash
/path/to/coding-harness/install.sh --scope user
```

**계획만 확인 (파일시스템 변경 없음)**

```bash
./install.sh --scope project --dry-run
```

**기존 파일 덮어쓰기**

```bash
./install.sh --scope project --force
```

### 플래그 상세

| 플래그 | 필수 | 동작 |
|--------|------|------|
| `--scope project` | 택1 필수 | 현재 디렉토리(`$PWD`)에 설치 |
| `--scope user` | 택1 필수 | `~/.claude/` 에 설치 |
| `--force` | 아니오 | rules/agents/commands 차이가 있어도 덮어쓰기 |
| `--dry-run` | 아니오 | 계획만 출력. 파일시스템 변경 없음 |
| `--help` | 아니오 | 사용법 출력 후 종료 |

**중요**: `--scope` 를 생략하면 오류 발생. 잘못된 대상에 설치하는 사고를 방지하기 위해 항상 명시해야 한다.

## 설치 대상

| 항목 | 파일 수 | project 경로 | user 경로 | 로드 시점 |
|------|--------|-------------|----------|----------|
| rules/ | 46 | `./.claude/rules/` | `~/.claude/rules/` | 16개 항상 · 30개 조건부 |
| agents/ | 4 | `./.claude/agents/` | `~/.claude/agents/` | 호출 시 |
| commands/ | 8 | `./.claude/commands/` | `~/.claude/commands/` | 호출 시 |

**합계**: project·user 모두 58개 파일. (`CLAUDE.md` 는 배포 대상이 아니다 — project
scope 는 대상 프로젝트의 `./CLAUDE.md` 를 건드리지 않고, user scope 는 예전 설치가 남긴
`~/.claude/CLAUDE.md` 를 안전하게 은퇴시킨다. 판정 규칙은 아래
「`~/.claude/CLAUDE.md` 은퇴」 절 참고.)

상시 컨텍스트를 차지하는 것은 **CLAUDE.md 1개 + rules 16개 = 17개(실측 54,660B)** 뿐이다.
이 수치는 `tests/run.sh` 의 T26 이 예산 상한으로 강제한다(래칫 — 내리는 것은 자유, 올리려면
그 값을 고치는 커밋에 근거를 남겨야 한다).
나머지는 조건이 맞을 때(rules 30개) 또는 호출할 때(agents 4개, commands 8개)만 로드된다.

### rules/workflow 구성

배포되는 **범용 개발 워크플로우**는 `rules/workflow/` 4개 파일이다 —
`install.sh --scope user` 로 설치하면 user-level rules 로 항상 로드된다
(레포 자체의 `rules/` 트리는 구조적으로 미발견이므로 clone 만 해서는 자동 적용되지
않는다). 저장소 루트의 `CLAUDE.md` 는 **coding-harness 자신의 프로젝트 지침**이며 배포
대상이 아니다. 각 프로젝트는 자체 CLAUDE.md 에 프로젝트 고유 내용(아키텍처, 성능 병목,
빌드 명령, 팀 커밋 컨벤션)을 채운다 — 프로젝트 CLAUDE.md·프로젝트 rules 가 이 워크플로우
규칙과 충돌하면 프로젝트 쪽이 우선한다(user-level rules 는 project rules 보다 우선순위가 낮다).

- **`role-separation.md`** — 응답 언어, 서브에이전트 위임 승인, 작업 분류(전체 경로 /
  축약 경로 / 생략), 설계→구현→검수 3단계, 공통 규칙(보고 형식 등).
  어느 경로든 **검수는 생략하지 않는다**
- **`model-routing.md`** — 모델 운용 원칙: 설계 opus(고난도·재설계 회차는 fable 조건부
  승격) / 구현 sonnet / 검수 sonnet(민감 영역 opus, 「전수 검사」 요청 시 fable) / 탐색 haiku
- **`code-quality-baseline.md`** — 구조와 모듈화, 가독성, 설계 원칙, 성능, 강제 수단.
  함수 50줄·중첩 3단계 이내, 외부 I/O와 순수 로직 분리, YAGNI, 매직 넘버 상수화 등
- **`project-instructions-checklist.md`** — 각 프로젝트 CLAUDE.md가 최소한 채워야 할
  5항목(개요·아키텍처·성능·빌드/검증 명령·컨벤션) 체크리스트

### commands 구성

`prp-prd` → `prp-plan` → `prp-implement` → `prp-pr` 워크플로우와 그 의존 대상이다.

| 커맨드 | 역할 |
|--------|------|
| `prp-prd` | 문제 정의 우선 PRD 작성 (대화형) |
| `prp-plan` | 코드베이스 분석 기반 구현 계획 수립 |
| `prp-implement` | 계획 실행 + 검증 루프 |
| `prp-pr` | 브랜치 변경 분석 후 GitHub PR 생성 |
| `prp-commit` | 자연어로 파일 지정해 커밋 (컨벤션: 프로젝트 CLAUDE.md > commitlint 설정 > 기본 형식) |
| `code-review` | 로컬 변경 또는 PR 검수 |
| `harness-update` | coding-harness 레포 업데이트 (manifest 기반 자동 갱신) |
| `hub` | 로컬 모든 프로젝트 진행 상황을 한 페이지에 집계, 진행 기록(대시보드) 스위치 포함 (**별도 설치** — [hub/README.md](hub/README.md)) |

각 커맨드의 동작:

- **`/prp-prd`** — 대화형 질문으로 문제 정의부터 시작해 PRD 문서를 생성한다.
  결과물의 Implementation Phases 표가 `/prp-plan` 의 입력이 된다.
- **`/prp-plan`** — PRD 또는 기능 설명을 받아 코드베이스를 분석하고,
  단계별 검증 기준이 포함된 구현 계획 문서를 만든다.
- **`/prp-implement`** — 계획을 순서대로 실행하며 단계마다 테스트·lint 검증 루프를 돈다.
- **`/prp-pr`** — 브랜치의 전체 커밋을 분석해 요약과 테스트 계획이 담긴 GitHub PR을 생성한다.
- **`/prp-commit`** — "the auth changes" 같은 자연어로 커밋 대상을 지정하면
  스테이징부터 메시지 작성까지 수행한다. 메시지 형식은
  **프로젝트 CLAUDE.md 컨벤션 > commitlint 설정(`.commitlintrc*` 등) > 기본 `{type}: {description}`**
  순으로 해석한다. 어느 컨벤션이든 메시지 본문은 비개발자도 이해할 수 있는 평이한 말로
  단답형으로 쓴다.
- **`/code-review`** — 로컬 미커밋 변경 또는 GitHub PR을 보안(CRITICAL)부터
  베스트 프랙티스(LOW)까지 심각도별로 검수하고, CRITICAL/HIGH 발견 시 커밋·머지 차단을 권고한다.
- **`/harness-update`** — 설치된 coding-harness를 최신 버전으로 업데이트한다.
  manifest 파일에서 레포 경로·scope를 읽어 자동으로 pull 후 재설치한다.
  변경이 있으면 사용자 확인을 받고, 로컬 수정 충돌 시 `--force` 여부를 묻는다.
- **`/hub`** — 로컬 머신에서 돌고 있는 **모든** 프로젝트의 진행 상황을 한 페이지에서
  **읽기 전용**으로 본다. **coding-harness 설치와 별개로 설치한다** — 실행 코드·상주 서버·
  전역 훅·프라이버시 고지·설정·진행 기록(대시보드) 스위치 전부는
  [`hub/README.md`](hub/README.md) 를 참고한다.

**의존 사슬 7종 + 독립 커맨드 1종.** `prp-implement` 가 `/code-review`·`/prp-commit`·`/prp-pr` 을,
`prp-pr` 이 `/code-review`·`/prp-commit` 을 호출한다. 일부만 설치하면 사슬이 끊기므로 전부 배포한다.
배포되는 `agents/code-reviewer.md` 도 `/code-review` 를 참조한다. `hub` 는 이 사슬을
호출하지도, 호출받지도 않는 독립 커맨드다.

`--scope project` 로 설치하면 전역(`~/.claude/commands/`)과 비교해 상황을 보고한다.
`--scope user` 는 설치 대상이 곧 전역이므로 비교를 생략한다.

**주의 — 커맨드 우선순위는 전역이 프로젝트를 이긴다** ([skills 문서](https://code.claude.com/docs/en/skills):
"personal overrides project"). rules·agents 와 방향이 반대다:

| 자산 | 같은 이름일 때 이기는 쪽 |
|------|------------------------|
| rules | 프로젝트 |
| agents | 프로젝트 |
| commands | **전역** |

따라서 전역에 같은 이름의 커맨드가 **다른 내용**으로 존재하면, 프로젝트 사본은 무시되고
전역 버전이 실행된다. install.sh 가 이 상황을 감지해 경고하며, 프로젝트 사본을 쓰려면
`install.sh --scope user` 로 전역을 갱신하면 된다. 전역에 커맨드가 없는 새 머신에서는
프로젝트 사본이 그대로 동작한다.

같은 이름이 양쪽에 있어도 **토큰 이중 비용은 없다** — 이긴 쪽 하나만 커맨드 목록에
등재되고(description 한 줄), 본문은 호출할 때 이긴 쪽 것만 로드된다.

### agents 구성

`rules/workflow/role-separation.md` 「개발 워크플로우」의 3단계(설계 → 구현 → 검수)를
역할별 서브에이전트가 분담한다.

| 에이전트 | 모델 · effort | 역할 |
|---------|------|------|
| `design-architect` | opus · xhigh (조건부 fable) | **설계 전담.** 전체 경로 작업에서 구현 전에 설계 문서(PRP)를 생성. 구현 코드는 작성하지 않음 |
| `implementer` | sonnet · high | **구현 전담.** 승인된 PRP 기반(전체 경로) 또는 접근 방식 보고 후(축약 경로) 코드 작성. 테스트·lint·type check 전부 통과가 완료 기준 |
| `code-reviewer` | sonnet · high (민감 시 opus · 「전수 검사」 시 fable) | **검수 전담.** 코드를 직접 수정하지 않고 보고만 — Edit/Write 권한이 의도적으로 없음. CRITICAL/HIGH 지적마다 재현 증거(실패하는 테스트, 또는 명령과 출력 몇 줄)를 붙이고 수정안은 쓰지 않음(증거를 못 붙이면 한 단계 낮춤). PASS/FAIL 판정이 커밋 게이트이며, FAIL 에는 사유 범주(실행·검증·정합·설계)를 붙임 |
| `explore` | haiku (effort 없음) | **탐색·수집 전용** 저비용 에이전트. 판단이 필요한 작업(설계·구현·검수 판정)에는 사용하지 않음 |

- 작업 에이전트 3종은 `Skill` 도구를 보유해, 설치된 `/prp-plan`·`/prp-implement`·`/code-review`
  커맨드를 직접 로드해 절차대로 수행한다. 커맨드 미설치 환경에서는 각자의 내장 체크리스트로
  동작한다 (fallback).
- effort 는 에이전트 frontmatter 로 고정한다 — 세션 effort 를 물려받지 않는다. 환경변수
  `CLAUDE_CODE_EFFORT_LEVEL` 은 frontmatter 보다 우선한다.
- 작업 에이전트 3종은 하위 에이전트로 Explore 만 띄운다 — 에이전트 본문의 **지침**이다. `tools` 에는
  `Agent` 를 쓴다. 서브에이전트 정의에서는 `Agent(...)` 괄호 목록이
  무시되므로 기계 강제는 없다.
- explore 는 CLAUDE.md 계층을 받지 않는다(`omitClaudeMd`) — 부르는 쪽이 필요한 규칙을 요청에 담는다.
- 모델 배분은 `rules/workflow/model-routing.md` 「모델 운용 원칙」을 따른다: 판단 오류의
  파급이 가장 큰 설계에 opus, 토큰 소비가 가장 큰 구현에 sonnet, 수집 전용에 haiku.
- 위 표의 모델은 **기본값**이다. 승격 조건(설계의 fable 4개 기준, 검수의 「전수 검사」)은
  같은 절에 정의돼 있고, 승격은 에이전트 frontmatter 가 아니라 **디스패치 시점의 `model`
  인자**로 지정한다.

### rules 구성

46개 규칙 파일은 JS/TS + React + 웹 + React Native/Expo + Python 스택 큐레이션에, 범용
개발 워크플로우를 더한 구성이다:

| 분류 | 파일 수 | 로드 방식 | 설명 |
|------|--------|----------|------|
| common/ | 11 | **항상** | 언어 무관 원칙 (coding-style, testing, git-workflow, karpathy-guidelines 등) |
| workflow/ | 4 | **항상** | 범용 개발 워크플로우 (role-separation, model-routing, code-quality-baseline, project-instructions-checklist) |
| README.md | 1 | **항상** | rules 구조·우선순위 안내 |
| typescript/ | 5 | **조건부** | `paths`(ts/tsx/js/jsx) 매칭 시 로드 |
| react/ | 5 | **조건부** | `paths`(tsx/jsx, components·hooks 디렉토리의 ts/js) 매칭 시 로드 |
| web/ | 7 | **조건부** | `paths`(tsx/jsx/vue/svelte/css/scss/sass/less/html) 매칭 시 로드 |
| react-native/ | 8 | **조건부** | React Native/Expo 확장 (accessibility·production-readiness 포함) |
| python/ | 5 | **조건부** | `paths`(py/pyi) 매칭 시 로드 |

**항상 로드되는 rules**: 16개 (CLAUDE.md 포함 시 17개, 실측 54,660B — `tests/run.sh` T26 예산 상한으로 강제)

`common/karpathy-guidelines.md` 는 Andrej Karpathy의 관찰에서 파생된, LLM 코딩의 흔한 실패(추측성
코드·과잉 수정·불명확한 목표)를 줄이기 위한 행동 지침이며, `paths` frontmatter가 없어 **설치된
모든 프로젝트에서 자동 적용**된다. 4개 원칙(Think Before Coding·Simplicity First·Surgical
Changes·Goal-Driven Execution)의 상세는 그 파일을 참조한다. `common/coding-style.md` 의 에러
처리 정책(실제 발생 가능한 실패만 처리)도 이 지침과 정렬되어 있다.

**조건부 로드 방식**: `paths` 규칙은 Claude가 **매칭되는 파일을 실제로 Read/Edit하는 시점**에 동적으로 로드된다 ([공식 문서](https://code.claude.com/docs/en/memory) — "Path-scoped rules trigger when Claude reads files matching the pattern"). 예: `.tsx` 파일을 편집하는 순간 react/ 규칙이 붙는다. 매칭 파일을 다루지 않는 세션에서는 로드되지 않아 컨텍스트를 절약한다.

**주의 — react-native/ 와 웹 규칙의 glob 겹침**: RN 소스도 `.ts(x)`라서 react-native 규칙 역시 `**/*.ts(x)`를 사용한다(확장자로는 구분 불가). 따라서 순수 웹 프로젝트에서도 TS 파일 편집 시 RN 규칙이 함께 로드된다. 웹 전용 프로젝트라면 설치 후 `.claude/rules/react-native/` 를 삭제한다 (RN 프로젝트에서는 반대로 web/ 삭제 가능). 단, 재설치하면 누락 파일로 간주되어 자동 복원되므로 그때 다시 삭제해야 한다.

자세한 구조는 [`rules/README.md`](./rules/README.md)를 참조한다.

## 환경 업데이트

설치된 프로젝트 또는 전역 디렉토리 어디서든 `/harness-update` 로 실행한다. project 는
`./.claude/.coding-harness.json`, user 는 `~/.claude/.coding-harness.json` manifest 에서 레포 경로와
scope 를 읽어, 원격에 새 커밋이 있으면 `git pull --ff-only` 후 install.sh 를 재실행하고
manifest 를 갱신한다. **레포는 최신인데 설치본만 낡은 경우**(레포에 직접 커밋한 뒤 재설치를
잊은 경우)에는 pull 없이 재설치만 한다.

- **manifest 없는 구버전 설치**: 첫 실행 때 레포 경로를 물어보고, 입력하면 이후부터 자동으로 동작한다.
- **project + user 동시 설치**: 각각의 위치에서 따로 실행해야 한다 — scope 별로 manifest 가 다르다.
- **설치본을 로컬에서 고쳤을 때**: 단순히 낡은 사본으로 보이면 확인 없이 `--force` 로 재설치하고,
  이 머신에서 의도적으로 커스터마이징한 것으로 보이는 파일만 이름을 짚어 물어본다.
- **멱등**: 같은 명령을 여러 번 실행해도 안전하다. 이미 최신이면 그대로 종료하고, 재설치가
  필요해도 배포 파일만 다시 복사해 부작용이 없다.

## 안전장치

### `~/.claude/CLAUDE.md` 은퇴

`install.sh` 는 CLAUDE.md 를 배포하지 않는다. **project scope 는 CLAUDE.md 를
건드리지 않는다** — 대상 프로젝트의 `./CLAUDE.md` 는 있든 없든 항상 그대로다.
**`--scope user` 는 예전 설치가 남긴 `~/.claude/CLAUDE.md` 를 아래 절차로 정리한다**
(대상은 이 경로 하나뿐 — `CLAUDE.local.md`·`~/.claude/rules/**`·프로젝트
CLAUDE.md 는 이 절차가 읽지도 쓰지도 않는다).

| 대상 상태 | 판정 | 동작 |
|-----------|------|------|
| 파일 없음 | skip | 조용히 통과 (신규 머신, 또는 이미 정리된 머신) |
| 심볼릭 링크 | protect_unknown | 안내만 하고 유지 — mv 로는 의도를 판정할 수 없다 |
| 이전 manifest `version` ≥ 3 | skip | 로그 없음 — 이미 정리가 끝났고, 그 자리 파일은 사용자가 새로 만든 소유물이다 |
| manifest 대장 해시 일치 | **retire** | `CLAUDE.md.retired-<타임스탬프>` 로 원자 개명(mv) — 개명 자체가 백업이자 삭제다 |
| manifest 대장 해시 불일치(사용자 수정) | protect_modified | **`--force` 로도 은퇴시키지 않는다** — 안내만 하고 유지 |
| 대장 없음(v1/manifest 부재) + 레거시 제목·본문 문구 2종 일치 | retire | 구버전 자동 설치본으로 판단해 자동 은퇴 |
| 그 외 전부 | protect_unknown | "지울 수 있음을 증명 못 하면 지우지 않는다" |

**보호 안내는 최초 1회만 표시된다**: `protect_modified`·`protect_unknown` 으로 남은
파일은 그 실행에서 manifest 가 v3 로 갱신되므로, 다음 실행부터는 위 표의 "이전 manifest
version ≥ 3 → skip" 규칙이 먼저 이겨 안내 없이 조용히 넘어간다. 안내를 놓쳤거나 나중에
정리하고 싶다면 내용을 직접 확인한 뒤 수동으로 옮긴다: `mv ~/.claude/CLAUDE.md
~/.claude/CLAUDE.md.retired-manual` (이중 로드까지 없애려면 그 뒤에 `rm` 으로 완전히
지운다).

**이유**: 배포하지 않는 파일을 무단으로 지우는 것도, 판정 없이 방치하는 것도 사고다.
`mv` 원자 개명은 "백업 성공·삭제 실패" 같은 중간 실패 창을 구조적으로 없앤다.

### rules/ · agents/ · commands/ (벤더링 자산)

**소유권 원칙**: 이 스크립트는 **레포가 배포하는 파일만** 관리한다. 대상 디렉토리에만 있는 파일은 손대지 않는다(예외: `__pycache__` — 아래 표).

이 구분이 중요한 이유는 대상 디렉토리가 보통 우리 것이 아니기 때문이다. 예를 들어 `~/.claude/agents/` 에는 이 레포가 배포하는 4개 외에 수십 개가 공존하고, `~/.claude/commands/` 에도 배포 대상 8개 외 수십 개가 있다.

| 대상 상태 | 판정 | 동작 |
|-----------|------|------|
| 대상 디렉토리 없음 | — | 생성 후 복사 |
| 관리 파일이 대상에 없음 | 누락 | **자동 복원** (`--force` 불필요 — 파괴 위험이 없음) |
| 관리 파일 내용이 다름 | 사용자 수정 의심 | 차이 **파일명 출력**(최대 20건) 후 **중단**(exit 1). `--force` 요구 |
| 대상에만 있는 파일 | **우리 소유 아님** | 충돌로 보지 않음. 삭제하지 않음 |
| `__pycache__` (관리 디렉토리 안) | **예외 — 소유권 판단 대상 아님** | 매 설치마다 무조건 삭제(파이썬 바이트코드 캐시, `.py` 원본에서 재생성됨) |

설치 후에는 배포한 파일이 전부 반영됐는지 `diff -rq` 로 검증한다. 대상에만 있는 파일은 검증 대상이 아니다(`__pycache__` 는 위 표의 예외라 이 검증에서도 제외된다).

**이유**: 단일 출처는 이 레포다. 업데이트가 필요하면 레포에서 수정하고 재설치한다. 다만 대상 디렉토리 전체를 레포 소유로 간주하면 사용자의 다른 자산을 오판하거나 파괴한다.

## 파일 구조

```
coding-harness/
├── README.md                      # 이 파일
├── install.sh                     # 배포 스크립트 (순수 bash, 외부 의존 없음)
├── CLAUDE.md                      # 프로젝트 지침(배포 대상 아님) — coding-harness 자신의 아키텍처·검증 명령
├── removals.txt                   # 툼스톤 목록 — 레포에서 제거된 관리 파일의 대상측 삭제 대상 (배포 대상 아님)
├── rules/                         # 46개 규칙 (JS/TS·React·웹·RN/Expo·Python 스택 큐레이션 + workflow)
│   ├── README.md                  # rules 구조 설명
│   ├── common/                    # 언어 무관 (11개, karpathy-guidelines 포함)
│   ├── workflow/                  # 범용 개발 워크플로우 (4개, 항상 로드)
│   ├── typescript/                # TS/JS 전용 (5개, 조건부 로드)
│   ├── react/                     # React 전용 (5개, 조건부 로드)
│   ├── react-native/              # React Native/Expo 전용 (8개, 조건부 로드)
│   ├── web/                       # 웹 프론트엔드 전용 (7개, 조건부 로드)
│   └── python/                    # Python 전용 (5개, 조건부 로드)
├── agents/                        # 4개 에이전트
│   ├── design-architect.md
│   ├── implementer.md
│   ├── code-reviewer.md
│   └── explore.md
├── commands/                      # .md 커맨드 8종(의존 사슬 7종 + 독립 커맨드 1종) = 8개 파일
│   ├── prp-prd.md
│   ├── prp-plan.md
│   ├── prp-implement.md
│   ├── prp-pr.md
│   ├── prp-commit.md
│   ├── code-review.md
│   ├── harness-update.md
│   └── hub.md
├── hub/                            # 통합 허브 — 별도 설치(hub/README.md). 진행 기록(대시보드)
│                                   #   자산도 이 안에서 배포된다(hub/bin·hub/rules)
├── docs/prps/                      # 설계·조사 문서 85개 — coding-harness.md·hub-dashboard.md·
│   │                               #   dashboard-rationale.md 등
│   └── ab-artifacts/               # 모델×스캐폴딩 A/B 실험 원본 6건 — 승인된 설계가 아니다
├── docs/images/                    # hub/README.md 의 스크린샷 3장 — 허브 화면 2장은 가상 데이터, 진행 기록 화면 1장은 이 저장소 자신의 작업 기록
├── docs/coding-harness-intro.html  # 소개 페이지(claude.ai artifact) 원본 — 그림은 docs/images 의 것을 함께 쓴다
└── tests/
    ├── run.sh                     # 테스트 스크립트 (install.sh·문서 정합성)
    ├── mutations.tsv              # 뮤테이션 원장 — 가드를 일부러 깨뜨려 실패하는지 확인하는 변조 목록 (배포 대상 아님)
    ├── k6_selection.py            # 전체 검사가 이번 변경과 관련된 행만 다시 확인하도록 고르는 순수 로직
    └── hub/                       # 허브 순수 로직 단위 테스트 (stdlib unittest)
```

## 설계 문서

전체 설계 원리와 리스크 분석은 [`docs/prps/coding-harness.md`](./docs/prps/coding-harness.md)를 참조한다.

## 요구사항

- bash 3.2 이상 (macOS 기본 `/bin/bash` 로 검증됨 — 별도 설치 불필요)
- `cp`, `mkdir`, `find`, `diff`, `date` (표준 유틸리티)
- 대상 디렉토리에 쓰기 권한
- (허브 사용 시) `python3` 3.10 이상 — 루트 설치(`install.sh`)에는 불필요

## 라이선스

MIT — [LICENSE](LICENSE) 참조. 상류 파생·제3자 고지는 [NOTICE.md](NOTICE.md).
