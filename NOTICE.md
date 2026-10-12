# NOTICE

이 문서는 MIT 라이선스가 요구하는 상류 저작권 고지·허가 고지의 이행이며, **선택 사항이
아니다.** 아래 각 절은 이 저장소가 포함하는 상류·제3자 저작물의 출처와 라이선스, 그리고
이 저장소가 그 위에 가한 변경을 기록한다.

## 1. 이 저장소의 라이선스

MIT. 전문은 [`LICENSE`](LICENSE) 참조.

## 2. 상류: Everything Claude Code (ECC)

이 절의 상류 저작권 고지·허가 고지 재수록은 MIT 라이선스가 요구하는 조건의 이행이며,
**선택 사항이 아니다.**

- 프로젝트: Everything Claude Code (ECC)
- URL: https://github.com/affaan-m/ECC — **현재 정칭**(조회일 2026-09-02, `GET
  /repos/affaan-m/ECC` 직접 조회 → HTTP 200, `full_name: affaan-m/ECC`, `id: 1136590548`).
  이전 명칭 `affaan-m/everything-claude-code` 에서 개명됐다 — 구 URL 은 같은 조회에서
  HTTP 301 로 새 이름에 리다이렉트되어 지금도 열리지만, 그 슬러그를 제3자가 새 저장소
  이름으로 재사용하면 리다이렉트는 끊긴다(그 시점부터 이 절의 URL 이 낡는다). 아래
  T32-4 는 URL 문자열이 파일에 있는지만 보는 정적 검사라 실제로 그 URL 이 살아있는지는
  확인하지 못하므로, 지금 시점에 유효한 정칭을 앵커로 쓴다. 불변 식별자는 저장소 id
  `1136590548`(`GET /repositories/1136590548` — 개명과 무관하게 항상 같은 저장소를
  가리키지만, 사람이 읽는 URL 로는 쓸 수 없다).
- 라이선스: MIT
- Copyright (c) 2026 Affaan Mustafa

아래는 상류 MIT 라이선스의 저작권 고지와 허가 고지 전문이다:

```
MIT License

Copyright (c) 2026 Affaan Mustafa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

(이 저장소 자신의 라이선스 조건은 §1·`LICENSE` 이며, 위 인용은 상류 조건의 보존일 뿐
이 저장소에 별도 조건을 얹지 않는다.)

## 3. 파생 파일 목록

**산출 방법**: 상류 GitHub 저장소(§2)의 git 트리를 재귀 조회해(`GET
/repos/affaan-m/ECC/git/trees/main?recursive=1`, 조회일 2026-09-02, HTTP 200,
`truncated: false`, blob 3,519개) 이 저장소의 각 후보 경로가 그 트리에 동일 경로로
존재하는지 직접 대조했다 — 존재하면 "상류 유래", 존재하지 않으면 "원저작"으로
분류한다. (이전 버전은 이 저장소 자신의 git 이력에서 두 벤더링 커밋 — 최초 반입
`602e377`, 재동기화 `5f9552f` — 을 제외한 나머지 이력 유무로 판별했는데, 그 방법은
파일이 삭제됐다 벤더링이 아닌 커밋에서 재작성돼 들어오면 "이력에 벤더링 커밋이
없다 = 원저작"으로 오분류하는 사각지대가 있었다 — `rules/python/` 5개(재작성 커밋
`4be8f58`)가 그 자리였다(아래 별도 문단 참조). §5 의 로컬 패치 판정도 이번 회차부터
같은 이유로 git-이력 방법을 버리고 이 상류 원문 내용 대조로 교체했다(아래 §5의
「산출 방법」) — 로컬 이력이 벤더링 커밋 하나뿐인 파일(`rules/common/coding-style.md`·
`commands/prp-commit.md`)에서 간접 증거(이력)가 옅어져 패치를 놓치는, 같은 종류의
사각지대가 있었기 때문이다.)

**한계**: 이 판정은 조회 시점(2026-09-02, ref `main`, commit sha `ca185ef5f7…`, 그
commit 이 가리키는 tree sha `c31300c76…`)의 스냅샷 1장이다 — 상류가 그 이후 경로를 옮기거나(rename) 삭제하거나 새로 추가해도 이
절은 다시 조회하기 전까지 낡는다. 또한 "경로가 존재한다"는 "내용이 같다"는 뜻이
아니다 — 상류에 같은 경로가 있어도 본문은 이 저장소에서 전면 재작성됐을 수 있다
(`rules/python/`, 아래 별도 표기). **비망라 예시**: 상류가 `rules/react-native/` 를
삭제하거나 `rules/web/` 을 다른 이름으로 옮기면 이 절의 분류는 그 변경을 반영하지
못한 채로 남는다. **전수 증명이 아니다** — 이 방법이 확인하는 것은 "그 경로가 조회
시점에 상류에 있었는가" 뿐이며, 우연히 같은 경로명을 쓰는 다른 목적의 파일일 가능성
까지 배제하지는 않는다(다만 이번 조사에서는 typescript·react·react-native·web·python
5개 트랙의 파일명 전체를 상류와 직접 대조해 그 우려가 낮음은 확인했다).

| 그룹 | 파일 수 | 비고 |
|---|---|---|
| `rules/README.md` | 1 | 상류 템플릿에서 출발 — 이 저장소의 큐레이션(스택 구성·설치 수량)을 설명하도록 문장 단위로 재작성돼 있다. 로컬 패치 이력은 §5 |
| `rules/common/` | 10 | `karpathy-guidelines.md` 는 상류 트리에 경로 자체가 없어 제외(원저작, 아래 참조) |
| `rules/typescript/` | 5 | |
| `rules/react/` | 5 | |
| `rules/react-native/` | 8 | |
| `rules/web/` | 7 | |
| `agents/code-reviewer.md` | 1 | **상류 기반 재작성** — 누적 로컬 패치(§5)로 상류 대비 다수 줄이 달라져 있으나, 상류 파일에서 출발했으므로 고지 대상에 남긴다. "파생" 단독 표기는 기여도를 오도하고, 목록에서 빼면 고지 의무가 흐려진다 |
| `commands/` | 6 | `code-review.md`·`prp-commit.md`·`prp-implement.md`·`prp-plan.md`·`prp-pr.md`·`prp-prd.md` |

**소계 43**(rules 36[= README 1 + common 10 + typescript 5 + react 5 + react-native 8 +
web 7] + agents 1 + commands 6).

**상류 유래 경로·본문 재작성(위 소계 43 에는 넣지 않는다)**: `rules/python/` 5개
(`coding-style`·`hooks`·`patterns`·`security`·`testing.md`)는 상류 트리에 지금도
같은 경로가 존재한다(상류는 이 디렉토리에 `fastapi.md` 를 1개 더 배포하지만, 이
저장소는 JS/TS 스택 전제라 설치하지 않았다 — 나머지 5개는 파일명까지 상류와
일치한다). 그러나 본문은 상류에서 옮겨온 것이 아니라 이 저장소가 자신의
`hub/bin/*.py` 코드 패턴에서 귀납해 전면 재작성했다(커밋 `4be8f58`, 커밋 메시지 원문:
"내용은 지어내지 않고 hub/bin/*.py 에서 귀납했다" — 그 앞서 `602e377`이 상류 원문을
반입했다가 `5f9552f`가 79→37 큐레이션에서 전량 삭제한 이력이 있다).

**직접 대조 방법과 한계**: 상류 원문과 줄 단위 매칭 블록(difflib `SequenceMatcher`,
공백만 있는 줄은 제외하고 비교)으로 대조했다. 이 방법에서 곧바로 따라오는 한계 —
매칭 블록은 "본문이 재작성됐는가"가 아니라 "같은 줄 시퀀스가 어디에 있는가"만 보므로,
개편 여부와 무관하게 구조적으로 반복되는 줄(프런트매터·부제목·코드펜스 구분자)도
함께 잡힌다. 그래서 축자로 남는 부분은 제목 줄과 상류 관례 문장 두 줄에 그치지
않는다. **비망라 예시** — 5파일 공통으로 프런트매터 5줄(`---`·`paths:`·
`- "**/*.py"`·`- "**/*.pyi"`·`---`)과 상류 관례 문장(`> This file extends
[common/xxx.md](../common/xxx.md) with Python specific content.`)이 남아 있고,
파일별로도 남는 줄이 있다(`coding-style.md` 의 `## Immutability` 소제목과
`from dataclasses import dataclass`·`@dataclass(frozen=True)` 예시 코드 2줄,
`testing.md` 의 `## Framework` 소제목, 각 파일의 코드펜스 구분자 ` ``` `). 이 지표
(상류 비공백 행 대비 매칭 비율)로 재는 값은 44.4%(상류 비공백 117행 중 52행)다 —
**이 수치는 이 지표에서만 유효하다**: 프런트매터·코드펜스를 세는지, 분모를 상류
쪽 행수로 두는지 로컬 쪽으로 두는지에 따라 다른 값이 나온다(같은 대상을 다른
기준으로 잰 값이 이 PRP 의 이전 검수 회차들에도 보고된 적이 있다). **전수 대조가
아니다** — 매칭되지 않은 나머지 구간이 상류와 다르다는 것만 확인했고, 그 구간을
한 줄씩 다시 읽어 의미까지 대조한 것은 아니다.

"파생"(위 표)과도 아래 "원저작"과도 다른 중간 성질이라 별도로 표기하며, §5 로컬
패치 목록·재동기화 규칙의 보호 대상에도 포함한다 — 상류가 이 경로를 지금도
배포하므로, 재동기화가 이 5개 파일을 상류 pytest 규칙으로 되돌릴 위험이 실재한다.

**원저작(상류 트리에 그 경로 자체가 없음)**: `rules/` 46개 중 위 표의 36개(README·
common·typescript·react·react-native·web)는 상류 유래(파생)이고, `rules/python/`
5개는 상류 유래이나 본문 재작성(바로 위 문단), 나머지 5개는 상류 트리를 조회해도
경로 자체가 없다 — 이 저장소가 처음부터 새로 썼다:

- `rules/common/karpathy-guidelines.md` — 한국어 82줄. 「실패 사례(실제 관측)」 절이
  이 저장소 자신의 `install.sh` 개발 중 사고(`set -e` 가 조건문에서 호출된 함수
  내부에는 적용되지 않는 문제, "관리 4개 vs 실제 51개" 파일 수 검증의 공허 통과)를
  서술한다.
- `rules/workflow/` 4개(`role-separation.md`·`model-routing.md`·
  `code-quality-baseline.md`·`project-instructions-checklist.md`) — 상류에서 온
  것이 아니라 이 저장소의 옛 루트 `CLAUDE.md`에서 이관됐다(2026-09-02, 커밋
  `0b0281d`, "CLAUDE.md 의 배포 목적지를 rules/workflow 로 옮기고...").

또한 `agents/`의 나머지 3개(`design-architect.md`·`implementer.md`·`explore.md`)도
이 저장소가 자신의 설계→구현→검수 워크플로우를 위해 새로 작성한 것으로, 상류 트리에
같은 경로가 없다(§2 인용 상류 저작권 고지의 대상이 아니다). `commands/` 는 로컬에
9개(.md 기준)가 있는데, 그중 `dashboard.md`·`harness-update.md`·`hub.md` 3개도 상류 트리에
경로가 없어 같은 사정이다(위 표의 6개만 상류 유래) — 상류 트리 조회로 재확인,
2026-09-02.

## 4. 이 저장소가 한 변경

- **79 → 37 큐레이션**: 상류가 배포하는 12개 언어 트랙을 포함한 79개 규칙 파일 중,
  JS/TS·React·React Native·web 스택에 맞는 37개만 남기고 나머지를 제외했다(커밋
  `5f9552f`).
- **한국어화**: 워크플로우·설계 문서·커밋 규약 등 이 저장소가 직접 작성하는 문서를
  한국어 중심으로 재작성했다.
- **워크플로우 재구성**: 설계(`design-architect`)→구현(`implementer`)→검수
  (`code-reviewer`) 역할 분리, `/dashboard`·`/hub` 등 이 저장소 고유 도구를 추가했다.
- **로컬 패치**: 상류 파생 파일(`rules/README.md` 포함)과 상류 유래·본문 재작성으로
  표기한 `rules/python/`을 합쳐 25개 파일에 이 저장소 고유의 수정이 있다 — 목록·근거는
  §5.
- **CLAUDE.md 배포 채널 이관**(2026-09-02): 루트 `CLAUDE.md`가 배포물과 이 저장소 자신의
  프로젝트 지침을 동시에 겸하던 것을, 배포되는 범용 워크플로우 지침은
  `rules/workflow/`(4파일)로 옮기고 루트 `CLAUDE.md`는 이 저장소 전용 지침(53줄)으로
  되돌렸다.

## 5. 로컬 패치된 벤더링 파일 (정본 목록)

**산출 방법(검수 R3 3회차 지적 ①로 교체)**: §3 과 같은 방식 — 상류 원문을 직접 가져와
(`https://raw.githubusercontent.com/affaan-m/ECC/main/<경로>`, 조회일 2026-09-02)
로컬 파일과 바이트 단위로 대조(`cmp`) — 으로 §3 의 48개 후보(파생 43 + `rules/python/`
5) 전부를 다시 대조해 다른 파일 26개를 추렸다. 이전 버전(`git log --oneline -- <파일>`
로 전체 커밋 이력을 뽑고 최초 반입 `602e377`·재동기화 `5f9552f`를 "벤더링 이벤트"로
제외한 뒤 남는 커밋 유무로 판별하던 방법)을 버린 이유는 §3 이 이미 서술한 사각지대와
같다 — 로컬 이력이 벤더링 커밋 하나였던 `rules/common/coding-style.md`·
`commands/prp-commit.md` 는 그 방법으로는 놓쳤다(이력만으로는 그 한 커밋 자체가 상류와
다른 내용을 들여왔는지 구분할 간접 증거가 남지 않는다).

**한계**: 조회 시점 스냅샷 1장이라는 것과 상류가 경로를 옮기면 판정이 흔들린다는 것은
§3 의 한계와 같다. 이 판정에 **더해지는** 한계 하나 — 내용이 다르다는 것과 "우리가
고쳤다"는 것은 별개다: 상류가 벤더링 이후 스스로 그 경로를 바꿔도 diff 는 똑같이
나타난다. 그래서 다른 파일마다 상류의 해당 경로 최종 커밋 시각을
(`GET /repos/affaan-m/ECC/commits?path=<경로>&sha=main`) 벤더링 시점과 대조했다 —
상류 최종 변경이 벤더링보다 앞서면 diff 는 우리 쪽 편집일 수밖에 없고, 벤더링보다
뒤면 diff 가 상류 변경만으로 설명될 수 있어 벤더링 시점 판본과 다시 대조해야 한다 — 그 판정
순서는 아래 「파일별 판정 순서」에 있고, 절차는 그 목록 한 곳에만 둔다. 시점만
보고 제외하면 위음성이 난다 — 한 파일에 로컬 패치와 상류 표류가 함께 있을 수 있다(아래
`rules/common/git-workflow.md` 각주). 다른 파일의 diff 26건 중 이 시점 대조가 실제로
필요했던 것은 상류 최종 변경이 벤더링보다 뒤인 세 파일(`rules/common/code-review.md`·`rules/common/coding-style.md`·`git-workflow.md`,
전부 상류 커밋 `60e27fe5`·`569b1d5b`)이었고, 판정이 갈린 것은 git-workflow.md
하나다. `prp-commit.md` 는 상류 최종 변경이 `2e5e94cb`(2026-04-08)로 벤더링보다
앞서 시점 대조가 필요하지 않았다 — 나머지 23개는
아래 표의 「근거」 열이 가리키는 PRP 결정(AR 번호)·감사 항목·커밋으로 우리 편집임이
이미 별도 확인돼 있어 시점 대조가 다시 필요하지 않았다. **전수 증명이 아니다** — 아래
목록은 이 방법으로 지금까지 실측한
결과이며, 새 로컬 패치가 추가되거나 상류가 더 바뀌면 갱신이 필요하다.

| 파일 | 패치 요지 | 근거(PRP/감사 항목) |
|---|---|---|
| `rules/README.md` | `rules/python/` 재도입과 `rules/workflow/` 신설을 구조도·상시로드 목록·설치 수량(37→42→46)에 반영 | 커밋 `4be8f58`·`0b0281d` |
| `rules/common/agents.md` | 로스터를 배포 4종(`design-architect`·`implementer`·`code-reviewer`·`Explore`)으로 교체, 미배포 10종 제거 | F-3(AR11) |
| `rules/common/code-review.md` | 미배포 리뷰어 5종 참조를 `code-reviewer` 위임 표현으로 교체 · 중첩 한도 `>4 levels`→`>3 levels` 2곳 · **Review Checklist 에 「새 검사·보호 분기를 일부러 깨뜨려 실패를 확인했다」 항목 1줄 추가**(상류에 없는 신규 항목) | F-3(AR11) · tests-hardening 승인 4 |
| `rules/common/coding-style.md` | 중첩 한도를 `>4 levels`→`>3 levels`로 강화, 에러 처리 절을 "실제 발생 가능한 실패만 처리"하는 `karpathy-guidelines.md` #2 참조로 교체(추측성 에러 처리 배제) | 검수 R3 3회차 지적 ①(§5 누락 보완 — 상류 원문 diff 로 신규 확인) |
| `rules/common/development-workflow.md` | 0단계를 "필수"에서 "도구(gh/MCP) 미설치 시 스킵"으로 완화, Context7·Exa 고유명사 의존 완화, `planner`/`tdd-guide` → `design-architect`/`implementer` 치환 | F-3(AR11)·F-4(AR12)·harness-landscape-survey |
| `rules/common/performance.md` | 모델 선택·thinking 절을 공식 문서 출처 기반으로 재작성(adaptive reasoning 반영), `/effort` 지속성 서술 정정, 미배포 `build-error-resolver` 제거 | A-3(AR3)·F-3(AR11)·기존 로컬 패치(품질 트랙) |
| `rules/common/security.md` | 미배포 `security-reviewer` → `code-reviewer` 보안 렌즈 위임으로 교체 | F-3(AR11) |
| `rules/common/testing.md` | 미배포 `tdd-guide` → `implementer`가 TDD를 직접 수행하는 것으로 교체 | F-3(AR11) |
| `rules/typescript/security.md` | 미배포 `security-reviewer` 참조 제거 | F-3(AR11) |
| `rules/typescript/testing.md` | 미배포 `e2e-runner` 참조 제거 | F-3(AR11) |
| `rules/react/patterns.md` | "React Native 트랙 부재" 단정을 정정(`rules/react-native/` 실재 8파일로 갱신), 미배포 `skills/` 참조에 상류 URL 명시(현재 정칭 `affaan-m/ECC`) | A-2(AR2) |
| `rules/react/security.md` | 미배포 `security-reviewer`·`react-reviewer` 참조를 `code-reviewer` 위임으로 교체 | F-3(AR11) |
| `rules/react/testing.md` | CRA(Create React App) 지원 종료 명시, 미배포 `skills/` 참조에 상류 URL 명시(현재 정칭 `affaan-m/ECC`) | F-3(AR11)·F-4(AR12) |
| `rules/react-native/testing.md` | 미배포 `tdd-guide` → `implementer` 직접 수행으로 교체 | F-3(AR11) |
| `rules/web/hooks.md` | 훅 JSON 6블록을 공식 3계층 스키마(`hooks` 배열 + `type: "command"`)로 교정 | A-1(AR1) |
| `agents/code-reviewer.md` | 재검수 모드 신설, 검수 루프 종결 규약(3회 상한 + 정체 감지), 파일 재읽기 절 신설(같은 범위 재읽기 방지), CLAUDE.md 재-Read 제거, 경량 검증(절차 6)·재검수 규칙 4 의 실행 범위를 「변경이 닿은 테스트만」으로 좁힘(전체 스위트는 검수자가 돌리지 않고 메인 세션이 커밋 직전에 1회 — docs/prps/t37-incremental-k6.md §12), 보고 양식의 `[제안]` → `[재현]`(CRITICAL/HIGH 에 재현 증거 의무, 못 붙이면 한 단계 하향), 기준 커밋 SHA 기록과 diff 1회 수집, 절차 재배열(결함 탐색 → 구현자 보고서·PRP 를 미검증 주장으로 대조), FAIL 사유 범주 4종, frontmatter 의 `effort` 고정과 `tools` 의 `Task` → 정식 이름 `Agent`(docs/prps/harness-benchmark-adoption.md) — 누적 10개 커밋 | F-2(AR15) 재작성 표기 대상·품질 트랙 다수 |
| `commands/code-review.md` | VALIDATE 경량 단계(Phase 3) 신설 — 기존 테스트 실행·기록, 실패 시 HIGH 이슈로 등록, 실행 범위를 변경이 닿은 테스트로 좁힘(전체 스위트는 검수 단계에서 돌리지 않음), Phase 1 에 기준 SHA 기록·diff 1회 수집, Phase 4 의 `Suggested fix` → `Reproduction`(CRITICAL/HIGH 재현 의무·하향 규칙)과 FAIL 사유 범주(docs/prps/harness-benchmark-adoption.md) | 기존 로컬 패치(검수 워크플로우) |
| `commands/prp-commit.md` | 커밋 컨벤션 해석 우선순위(프로젝트 CLAUDE.md → commitlint 설정 파일 → 기본 형식) 절 신설 | 검수 R3 3회차 지적 ①(§5 누락 보완 — 상류 원문 diff 로 신규 확인) |
| `commands/prp-implement.md` | `docs/prps/` 아래 산출물은 아카이브 이동을 생략(커밋된 정본 보호) | harness-landscape-survey(tier0-defect-fixes) |
| `commands/prp-plan.md` | 호출자 지정 출력 경로(`docs/prps/{feature}.md`)를 지원, 기본 경로(`.claude/PRPs/plans/`)는 유지 | harness-landscape-survey(tier0-defect-fixes) |
| `rules/python/coding-style.md` | 표준 라이브러리 우선·`X \| None` 타입힌트·`@dataclass(frozen=True)` 불변성·이름 있는 상수를 이 저장소 자신의 `hub/bin/*.py` 코드에서 귀납해 새로 작성 | 커밋 `4be8f58`·검수 R3 2회차 ②(§3 "상류 유래·본문 재작성" 재분류) |
| `rules/python/hooks.md` | 훅·statusline 진입점은 예외를 삼키고 항상 exit 0 을 반환한다는 규칙을 `hub_hook.py`/`hub_statusline.py`의 `main()` 형태에서 귀납 | 〃 |
| `rules/python/patterns.md` | 순수 모듈/I·O 모듈 분리, 프로즌 dataclass 로만 모듈 간 통신, 예상된 실패 전용 예외 클래스, 잎 모듈로 순환 참조 차단을 `hub_model.py`·`hub_collect.py`·`hub_server_state.py`에서 귀납 | 〃 |
| `rules/python/security.md` | 프롬프트·자격증명 평문 로깅 금지(보관기한·옵트아웃 고지 + 시크릿 마스킹)·`subprocess` 리스트 인자 강제·요청 문자열로 경로 조립 금지를 `hub_hook.py`·`hub_usage_fetch.py`·`hub_server.py` 패턴에서 귀납 | 〃 |
| `rules/python/testing.md` | stdlib `unittest` 를 기본 프레임워크로 명시(pytest 금지)·`setUp`/`tearDown` 모듈 상태 스왑·`mock.patch.object` 관례를 `tests/hub/*.py` 실제 패턴에서 귀납 | 〃 |

**상류가 벤더링 이후 갱신했으나 아직 취하지 않은 파일**: `rules/common/git-workflow.md`
는 위 표에 넣지 않는다 — 로컬 파일은 상류가 `569b1d5b`(2026-08-12, "disable Claude
co-author attribution by default")로 갱신하기 **전** 상태(그 부모 커밋 `ff2280a3`)와
바이트 동일하다(로컬 편집 0줄, 직접 대조 확인). 이 파일의 diff 는 우리가 만든 것이
아니라 상류가 벤더링 이후 스스로 바꾼 결과이므로 로컬 패치가 아니다. 다음 재동기화
때 이 상류 변경(공동 저자 표기 기본 비활성화)을 받아들일지 판단하는 참고로만 남긴다.

**`rules/python/` 5개가 새로 들어온 경위**: 2회차 검수(②)가 상류 트리를 직접 조회해
이 5개 경로가 지금도 상류에 있음을 확인했다(§3). 1회차는 git 이력만으로 "상류에서 온
적이 없다"고 잘못 분류해 이 표에서 빠져 있었다 — 경로가 상류에 있는 한 재동기화가
이 5개를 상류 pytest 규칙으로 되돌릴 수 있으므로, 아래 재동기화 규칙의 보호 대상에
포함한다.

### 재동기화 규칙

ECC 재동기화 시 이 목록의 파일은 **통째로 덮어쓰지 않는다.** 파일별로 상류 diff 를 검토해 로컬
패치를 보존·재적용하고, 완료 후 `bash tests/run.sh` 로 패치 존재 검사를 통과시킨다. 아래
「커버리지 상태」 표의 「검사」 칸이 `—` 인 행은 그 통과가 아무것도 보증하지 않으므로 상류 diff 를
사람이 직접 읽는다. `T26-2 간접` 인 1행도 총량이 상쇄되면 통과하므로 같이 읽는다.

**파일별 판정 순서**(0항: 벤더링보다 **앞선** 파일 / 1~3항: **뒤인** 파일): 아래에서 「벤더링」은
**현재 이 표를 도출한 벤더링 이벤트**
(§3 의 최초 반입 `602e377` · 큐레이션 `5f9552f`)를 가리키며, 지금 수행 중인 재동기화가 아니다 —
재동기화를 마칠 때마다 이 기준을 그 커밋으로 갱신한다.

0. 상류 최종 변경이 벤더링보다 **앞선** 파일은 diff 가 우리 쪽 편집이므로 시점 대조 없이 이 표에
   넣는다. 1~3항은 **뒤인** 파일에만 적용된다.
1. 벤더링 시점 판본을 받는다 — 기준은 상류 최종 커밋이 아니라 **벤더링 경계**다.
   `GET /repos/affaan-m/ECC/commits?path=<경로>&sha=main&until=<벤더링 커밋 시각>` 의 `[0].sha`
   (그 시각 이하 최신 상류 커밋)로 `https://raw.githubusercontent.com/affaan-m/ECC/<[0].sha>/<경로>`
   를 받아 로컬과 대조하고, 훅 단위로 로컬 편집분과 상류 변경분을 갈라 적는다. sha 를 별도 호출로
   얻는 이유: raw URL 은 **해석된 ref** 만 받아 `<sha>^` 표기가 통하지 않는다. 경계로 쓸 시각은
   위 두 커밋 중 **그 경로의 현재 내용을 확립한 쪽**이다 — 파생 파일은 `5f9552f`, `rules/python/`
   5개는 `602e377`. 그 시각은 이 저장소 커밋 시각이라 상류 fetch 시각의 **대리**이고, 오차는 그
   커밋 직전 창에 한한다 — 경계를 더 오래된 쪽으로 잡으면 diff 가 과대해져 파일이 표에 남으므로
   (위양성) 3항이 금지한 위음성 방향으로는 틀리지 않는다.
2. 그 대조로 **로컬 편집분이 0줄임이 확인된 파일만** 이 표에 넣지 않는다(이미 있으면 뺀다) —
   `rules/common/git-workflow.md` 가 그 사례이고, 근거는 위 「상류가 벤더링 이후 갱신했으나 아직
   취하지 않은 파일」 문단이다.
3. 시점 비교만으로 파일을 이 표에서 빼거나 「상류 표류」로 분류하지 않는다 — 위 「한계」가 자백한
   위음성이 그 자리에서 난다.

이 순서는 **기계로 강제되지 않는다** — 판정에 상류 원문 조회가 필요하고 `tests/run.sh` 는 네트워크를
쓰지 않는다. 로컬 `git show <벤더링 커밋>:<경로>` 로 대신할 수도 없다: 벤더링 커밋이 담은 것은 상류
원문이 아니라 재동기화가 로컬 패치를 보존한 결과이고, 상류 클론을 두지 않아 로컬 객체만으로 상류
원문에 닿는 경로가 보이지 않는다. 그러므로 `bash tests/run.sh` 가 그린인 것은 이 순서를 지켰다는
증거가 아니다.

### 커버리지 상태 (위 표 25행)

계수 기준: **「열림」**은 어떤 검사의 판정이 그 파일의 바이트에 의존한다는 뜻, **「잠긴다」**는 그
성분을 상류값으로 되돌리는 편집이 실제로 검사를 발화시킨다는 뜻이다. 설치·트리 복사·해시 대조·파일
수 계수처럼 내용이 무엇이든 통과하는 사용은 「열림」에 넣지 않는다(예: T30-2 의 `ls agents/*` 계수,
T4·T15·T18·T19·T27 이 이 표의 파일을 픽스처로 쓰는 자리). 아래 표는 위 25행과 1:1 로 대응하고
행 순서도 같다. `—` 는 해당 없음, `〃` 는 윗행과 같음이다. 성분 열거의 단위는 위 표의
「패치 요지」가 파일별로 구분한 항목이다 — 재동기화 담당자가 그 열을 체크리스트로 쓰므로 단위를
거기 맞췄다. 그 항목보다 더 잘게 쪼개 적는 것은 무방하다. 다만 그 아래 단위의 전수는 이 표가
보증하지 않는다. **비망라 예시**: `rules/react/patterns.md` 행의 다섯 번째 성분(두 트랙 동시 로드
서술)이 검수 3회차에서야 드러났다. **전수 증명이 아니다.**

| 파일 | 잠기는 성분 | 잠기지 않는 성분 | 검사 |
|---|---|---|---|
| `rules/README.md` | 집합 총 바이트만(직접 없음) | 구조도·상시로드 목록·설치 수량 | T26-2 간접 |
| `rules/common/agents.md` | 미배포 13종 이름의 부재 | 배포 4종 로스터의 정확성 | T29-1 |
| `rules/common/code-review.md` | 〃 · `>3 levels` 존재 + `>4 levels` 부재 | 위임 표현 문안 · **뮤테이션 확인 체크리스트 줄**(그 줄만 지운 사본으로 36그룹을 돌려 T26 하나만 발화함을 확인했다 — 재동기화가 지우면 집합 총 바이트만 움직이고 그 줄의 존재를 직접 보는 검사는 이 실측 범위에서 나오지 않았다) | T29-1 · T28-4 |
| `rules/common/coding-style.md` | `>3 levels` 존재 + `>4 levels` 부재 | 에러 처리 절의 `karpathy-guidelines.md` #2 참조(파일 전체가 `602e377` 이후 무변경이라 `5f9552f` 대조로 잠글 토큰이 없다) | T28-4 |
| `rules/common/development-workflow.md` | 미배포 13종 이름의 부재 · 0단계 완화 문구 존재 | 고유명사 의존 완화 문구 | T29-1 · T38-4 |
| `rules/common/performance.md` | 미배포 13종 이름의 부재 · `persist across sessions` 존재 · adaptive reasoning 도입 문장 존재 | adaptive reasoning 재작성 중 도입 문장 밖의 나머지(effort 표·모델별 지원 등) | T29-1 · T28-3 · T38-4 |
| `rules/common/security.md` | 미배포 13종 이름의 부재 | 보안 렌즈 위임 문안 | T29-1 |
| `rules/common/testing.md` | 〃 | `implementer` 의 TDD 직접 수행 문안 | T29-1 |
| `rules/typescript/security.md` | 〃 | — | T29-1 |
| `rules/typescript/testing.md` | 〃 | — | T29-1 |
| `rules/react/patterns.md` | 「not yet present」 부재 · 상류 `skills/` URL 명시 존재 · react-native 파일 수(8) 산문 정합 | Error Boundary 클래스 컴포넌트 예외 조항 · 두 트랙 동시 로드(`**/*.tsx`) 서술 | T28-2 · T38-4 · T39-3 |
| `rules/react/security.md` | 미배포 13종 이름의 부재 | `code-reviewer` 위임 문안 | T29-1 |
| `rules/react/testing.md` | CRA 지원 종료 명시 존재 · 상류 `skills/` URL 명시 존재 | e2e 스킬 링크 완화 표현 | T38-4 |
| `rules/react-native/testing.md` | 미배포 13종 이름의 부재 | `implementer` 직접 수행 문안 | T29-1 |
| `rules/web/hooks.md` | 훅 json 블록의 3계층 스키마 · `$FILE_PATH` 부재 | — | T28-1 |
| `agents/code-reviewer.md` | 재검수 모드 절 존재 · 재현 형식(`[재현]`) · 미검증 주장 순서 · 사유 범주(T31-11) | 루프 종결 규약 · 파일 재읽기 절 · 검증 범위 문안(「변경이 닿은 테스트만」 — 상류 재동기화가 되돌려도 「검수자가 전체를 돌린다」로 돌아갈 뿐 안전 문제가 아니다. 메인 세션의 커밋 직전 전체 검증 의무는 `rules/workflow/role-separation.md` 의 T31-9 가 잠근다) · 기준 SHA 기록·diff 1회 수집 · 하향 규칙 문안 | T38-3 · T31-11 |
| `commands/code-review.md` | VALIDATE 경량 단계 존재(T17 은 상호참조 토큰만 봄) · `Reproduction` 요구(T31-11) | Phase 3 표의 실행 범위 문안(위와 같은 이유) · Phase 1 의 기준 SHA·1회 수집 문안 | T38-3 · T31-11 |
| `commands/prp-commit.md` | Message style 절(커밋 메시지 문체 규칙) 존재 | 커밋 컨벤션 해석 우선순위 절(상류 대비로는 로컬 패치이나 최초 반입 `602e377`에 이미 있어 `5f9552f` 대조로는 못 잠근다) | T38-3 |
| `commands/prp-implement.md` | 아카이브 이동 생략 문구 존재 | — | T38-3 |
| `commands/prp-plan.md` | 호출자 지정 출력 경로 문구 존재 | — | T38-3 |
| `rules/python/coding-style.md` | 표준 라이브러리 우선 절 존재(T12 는 frontmatter 만 봄) | 타입힌트·불변성 본문 | T38-1 |
| `rules/python/hooks.md` | 훅 진입점의 exit 0 규칙 절 존재 | — | T38-1 |
| `rules/python/patterns.md` | 순수/IO 분리 절 존재 | 프로즌 dataclass 본문 | T38-1 |
| `rules/python/security.md` | subprocess 리스트 인자 절 존재 | 평문 로깅 금지 본문 | T38-1 |
| `rules/python/testing.md` | stdlib `unittest` 기본 문구 존재(T38-1) · 상류 pytest 관례 부재(T38-2) | — | T38-1 · T38-2 |

**세 버킷의 합**(위 표 「검사」 열을 세면 나온다): 직접 커버 24 + T26 간접만 1 + 미커버 0 = 25행
이고 서로 겹치지 않는다. T26 계수 집합과 겹치는 8행은 그 24+1 안이라 네 번째 값이 아니다.

### 이 커버리지 판정의 근거와 한계

**T26 이 간접으로 받는 기제와 그 한계**: T26-2 가 `README.md` 의 선언값을 집합의 실측 총 바이트와
**등식**으로 비교하므로, 되돌림이 총량을 바꾸는 한 직접 커버가 없는 `rules/README.md` 도 스위트를
빨갛게 만든다(이 파일은 벤더링 판본 5,033B ↔ 현재 6,075B). 여기서 곧바로 따라오는 한계 둘 —
(i) **길이 중립 패치는 원리적으로 안 잡힌다**(`>4 levels`↔`>3 levels` 는 같은 9바이트다. 그래서
T28-4 가 따로 필요했다), (ii) 보는 것이 **집합의 총합**이라 상쇄되는 변경(한 파일의 되돌림 + 다른
파일의 상류 추가)은 총량을 유지해 통과할 수 있다. 진단 문구도 예산·선언 불일치를 말하므로 어느
패치가 사라졌는지 가리키지 않는다.

이 표의 도출 방법·증거 등급·「검사 없음」 판정의 근거는 `docs/prps/tests-hardening.md` §21 에 있다
— 표를 검수하는 독자용 산출 기록이라 재동기화 절차의 행동을 바꾸지 않는다.

**판정 전체의 한계(비망라)**: 판정은 이 저장소 안에서만으로 냈다 — 상류 원문을 다시 받지 않았으므로
「되돌림이 어떤 리터럴을 재도입하는가」는 위 표의 「패치 요지」, T28·T29 헤더 주석의 기록, 그리고
§21 로 옮긴 두 문단의 git 판본 대조에 의존한다. 또 T28-2~T28-4·T29-1·T38-1~T38-4 는 리터럴 문자열의 존재·부재를
보는 정적 검사라, 같은 뜻을 다른 낱말로 되돌리는 편집이나 토큰만 남기고 주변 의미를 뒤집는 편집은
잡지 못한다(회피 경로의 더 긴 예시는 각 그룹의 헤더 주석에 있다). **전수 증명이 아니다.** 이 격차를
메우는 신규 테스트 작성은 이번 회차 범위 밖이다(후속 `tests-hardening`).

## 6. 제3자 고지

### lucide

`hub/bin/hub_template.html`의 아이콘은 [lucide](https://lucide.dev)의 SVG path
좌표를 정적으로 옮겨 적은 인라인 마크업이다(CDN 로드 대신 인라인을 택한 근거는 같은
파일:60 참조).

**원문 확인**: `https://raw.githubusercontent.com/lucide-icons/lucide/main/LICENSE`
(조회일 2026-09-02, HTTP 200) 에서 직접 가져왔다. lucide는 ISC를 기본으로 하되, Feather
아이콘 프로젝트에서 유래한 일부 아이콘에는 그 출처의 MIT 고지가 별도로 함께 적용된다 —
아래 두 고지 전문을 그대로 옮긴다.

**기본 라이선스 (ISC)**:

```
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

**Feather 유래 아이콘에 추가 적용되는 고지 (MIT)** — lucide `LICENSE` 원문은 이 고지
앞에 대상 아이콘 이름을 전부 나열한다(콤마 구분 115개, 실측 — 이 저장소와 무관한 것이
대부분이라 그 목록 자체는 옮기지 않는다, 원문 URL 에서 확인 가능). 그중 이 저장소가
실제로 쓰는
것은 `chevrons-right`·`moon` 2종이다(아래 매핑 참조). 아래는 그 목록 다음에 오는
고지 본문을 그대로 옮긴 것이다(제목 줄 포함, 원문 그대로):

```
The MIT License (MIT) (for the icons listed above)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**이 저장소가 쓰는 아이콘과 라이선스 귀속** — 산출 방법: `hub/bin/hub_template.html`에
`<svg>` 는 총 6개 있다(실측, 2026-09-02) — 그중 1개(:11 의 favicon, `<rect>` + 원 4개,
`rgb(0,114,178)`)는 이 저장소 자체 도안이라 제외하고, 나머지 5개를 path 데이터로
식별해 위에서 가져온 lucide `LICENSE`의 Feather 유래 목록과 이름을 대조했다. 한계:
식별은 이 5개 SVG 각각의 path 좌표를 눈으로 lucide 아이콘과 비교한 결과다 — lucide
쪽 아이콘 이름 변경이나 path 개정이 있었다면(원문 조회 시점 이후) 이 매핑이 낡을 수
있다.

| 사용처 | lucide 아이콘 이름 | Feather 유래(추가 MIT 적용) |
|---|---|---|
| 새로고침 버튼 | `refresh-cw` | 아니오 — ISC만 |
| 테마 토글(다크) | `moon` | **예 — ISC + MIT(Cole Bemis)** |
| 테마 토글(라이트) | `sun` | 아니오 — ISC만 |
| 패널 접기 화살표(PV12) | `chevrons-right` | **예 — ISC + MIT(Cole Bemis)** |
| 리사이즈 그립 | `grip-vertical` | 아니오 — ISC만 |
