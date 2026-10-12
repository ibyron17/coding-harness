# 티어 0 결함 수정 — 설계 문서 (PRP)

> 입력: [`docs/prps/harness-landscape-survey.md`](harness-landscape-survey.md) §4(결함 10건)·§5(적용 권고)·§6(환경 오염)·§7(이진 판정).
> 이 문서는 그중 **결함 1~8** 과 이진 판정 7-1·7-2 의 수정 설계다. 결함 9·10 은 제외한다(§제외 항목).
>
> 작성일: 2026-08-28 · 기준 커밋: `9145ef3` · 브랜치: `fix/tier0-defects`
> 본문 file:line 은 전부 이 워크트리에서 직접 실측했다.

---

## 1. 요구사항 요약

지형 조사가 발견한 자기 결함 8건을 수정한다. 성격은 셋으로 갈린다 — **규범의 구멍**(결함 1·2·6:
산문 규정이 서로 모순이거나 종결 조건이 없다), **선언과 실측의 괴리를 잡는 기계의 부재**(결함
3·4·5: 상시 컨텍스트 예산·삭제 경로·낡음 판정이 전부 사람 손 또는 LLM 판단에 걸려 있다),
**실제 피해가 진행 중인 것**(결함 7: 하네스가 자기 원칙 위반을 지시 / 결함 8: 전 프로젝트
프롬프트가 시크릿 스크럽 없이 평문 보관). 조사 보고서의 한 줄 결론 — "규범을 확인할 기계가
없다" — 에 따라, 수정의 무게중심은 새 산문이 아니라 `tests/run.sh` 에 붙는 결정적 검증기와
`install.sh` 의 결정론적 판정이다.

## 2. 모호한 부분 — 사용자 판단이 필요한 질문

1. **결함 1 경로 방향** — 아래 §4.1 의 세 선택지 중 **C(역할 분리 공존)를 권고**한다.
   A(전부 `docs/prps/`)·B(전부 `.claude/PRPs/`)를 원하면 영향 범위가 크게 달라진다.
2. **툼스톤 삭제의 강제 불가 원칙** — 사용자가 수정한 파일은 `--force` 로도 삭제하지 않는
   설계다(§4.4 D-4). 「`--force` 면 백업 후 삭제」를 원하면 알려달라 — 권고는 강제 불가다.
3. **검수 루프 상한 3회** — spec-kit(max 3)·BMAD(>5 HALT)·superpowers(5라운드) 중 최소값
   채택이다(§4.2). 5회를 원하면 수치만 바꾸면 된다.
4. **테스트 그룹 수 24→26** — T26(예산 래칫)·T27(해시 대장·삭제 경로) 신설로
   `total_tests` 계약이 26 이 된다. 그룹 신설 없이 기존 그룹에 얹는 안은 기각했다(§8 결정 6).

## 3. 영향 범위

| 파일 | 변경 | 결함 |
|------|------|------|
| `CLAUDE.md` | 1단계에 PRP 경로 규칙 1줄, 3단계에 검수 종결 규약 ~6줄 | 1, 2 |
| `agents/code-reviewer.md` | :59 뒤에 회차 표기·상한 도달 판정 어휘 ~4줄 | 2 |
| `commands/prp-plan.md` | :208·:212·:430·:444·:454 산출 경로에 호출자 지정 규칙 | 1 |
| `commands/prp-implement.md` | :283-284 아카이브 절에 `docs/prps/` 예외 | 1 |
| `commands/harness-update.md` | :161-168 LLM 판정 절 삭제 → 결정론적 절차로 대체, Phase 1 version ∈ {1,2} | 5, 4 |
| `commands/hub.md` | :147-148 프라이버시 고지에 시크릿 마스킹 문구 | 8 |
| `hub/README.md` | :142-154 프라이버시 고지 동일 갱신 | 8 |
| `rules/common/development-workflow.md` | :10-15 Context7/Exa 고유명사 의존 제거(능력 기반 재서술) | 6 |
| `rules/python/` **신설 5파일** | coding-style·testing·patterns·hooks·security (오염본과 동일 파일명) | 7 |
| `rules/README.md` | :35 카운트 37→42, 구조 트리·조건부 목록에 python/ 추가 | 7 |
| `README.md` | :20·:106·:110·:222·:224-230표·:300 카운트/표/트리, :112·:233 예산 수치 정정, 파일 구조에 `removals.txt` | 3, 7 |
| `install.sh` | `MANIFEST_VERSION` 1→2, `RULES_FILE_COUNT` 37→42, 해시 대장 생성, removals 처리, 충돌 분류 | 4, 5, 7 |
| `removals.txt` **신설** | 툼스톤 목록(초기엔 헤더 주석 + 빈 목록) | 4 |
| `tests/run.sh` | :245·:379 리터럴 37→42, :975 version 1→2, T12 확장, T20/T21 확장, **T26·T27 신설**, `total_tests` 24→26 | 3, 4, 5, 7 |
| `hub/bin/hub_hook.py` | `redact_secret_tokens()` 순수 함수 + `_project_fields` 배선 | 8 |
| `tests/hub/test_hub_hook.py` | `SecretRedactionTest` 클래스 신설 | 8 |
| `docs/prps/coding-harness.md` | :390 「미해결 불일치」 기록에 해소 각주 1줄 | 1 |

건드리지 않는 것: `commands/code-review.md`(루프 정의가 아니라 단발 검수 실행 명세 — §4.2),
`commands/prp-prd.md`·`prp-pr.md` 의 `.claude/PRPs/` 참조(선택지 C 에서 정상 경로),
`~/.claude/rules/` 의 python 외 오염 10개 디렉토리(이 저장소 원칙과 충돌하는 것은 python 뿐 — §12).

## 4. 결함별 설계

### 4.1 결함 1 — PRP 산출 경로 분열: 선택지와 권고

**전제가 되는 실측.** 커맨드 쪽 경로 `.claude/PRPs/` 는 이 저장소 안에서는 죽어 있지만
(실제 문서 44개 전부 `docs/prps/`), **다른 두 프로젝트에서 살아 있다** —
`atlas-ui-notebook-micro/.claude/PRPs/`(plans 18건 + reports + reviews),
`daily-brief/.claude/PRPs/`(plans 14건 + prds). 즉 이것은 「죽은 경로 제거」가 아니라
**「두 소비자를 가진 경로의 관계 규정」** 문제다. 또 `docs/prps/` 는 테스트가 물고 있다 —
T22-144 가 `docs/prps/dashboard-rationale.md` 앵커를, T25 가 `docs/prps/hub-dashboard.md` 를
직접 검사한다(tests/run.sh:2308-2317·2612).

| 선택지 | 내용 | 비용 |
|--------|------|------|
| A. 전부 `docs/prps/` | prp-plan/implement/prd/pr/code-review 의 경로 전부 교체 | 외부 2 프로젝트의 산출 경로가 갑자기 바뀜(로컬 작업물이 커밋 대상 트리로 이동 — 배포 대상 프로젝트에 결정을 강요). 기존 32+ 개 plan 문서가 고아가 됨 |
| B. 전부 `.claude/PRPs/` | CLAUDE.md:72·agents 4곳·문서 44개 이관 | 이 저장소 문서 44개 이동 + T22-144·T25 파손 + CLAUDE.md 내 링크 2곳 파손. 커밋 대상이던 설계 정본이 로컬 디렉토리로 강등 |
| **C. 역할 분리 공존 (권고)** | 워크플로우 정본 = `docs/prps/`(커밋 대상), prp-* 커맨드 로컬 산출물 = `.claude/PRPs/`(프로젝트 로컬). 관계를 양쪽에 명문화 | 문서 수정 3파일 ~8줄. 이동·파손 0건 |

**C 의 구현.** 모순의 정체는 "두 경로의 존재"가 아니라 "design-architect 가 `/prp-plan` 스킬을
쓰는 순간 산출 경로가 규정 충돌한다"는 것이다. 이 한 지점만 닫는다:

1. `CLAUDE.md` 1단계(:70-73 부근)에 1줄: *"design-architect 가 `/prp-plan` 스킬을 쓸 때도
   산출 경로는 `docs/prps/{기능명}.md` 로 지정해 넘긴다 — 커맨드의 기본 경로
   `.claude/PRPs/plans/` 는 이 워크플로우 밖에서 커맨드를 단독 호출할 때의 기본값이다."*
2. `commands/prp-plan.md` Phase 6(:208): *"Save to `.claude/PRPs/plans/{name}.plan.md`
   **unless the caller specifies an output path** (the coding-harness workflow's design-architect
   passes `docs/prps/{feature}.md`)."* — :430·:444·:454 의 출력 예시에도 같은 단서.
3. `commands/prp-implement.md` 아카이브 절(:283-284): 입력 plan 이 `docs/prps/` 아래이면
   **이동하지 않는다**(커밋된 정본은 아카이브 대상이 아니다). `.claude/PRPs/plans/` 아래일
   때만 기존대로 `completed/` 로 이동.
4. `docs/prps/coding-harness.md:390` 의 「미해결 불일치 (기록)」 끝에 해소 참조 1줄 추가
   (기록 자체는 보존 — 역사 문서는 고치지 않는다).

**검증**: 산문 규정이므로 자동 검증은 걸지 않는다(위트니스 마커는 이번 라운드 제외 — §12).
수동 검증: `grep -rn "PRPs" CLAUDE.md commands/prp-plan.md commands/prp-implement.md` 로
호출자 지정 규칙이 세 파일에서 서로를 가리키는지 확인.

### 4.2 결함 2 — 검수 루프 종결 규약

5개 레포(superpowers·spec-kit·BMAD·GSD·deepagents)가 수렴한 형태를 이식한다:
**회차 상한 + 정체 감지 + 상한 도달 = 「통과」가 아니라 「미해결 종결」**.

**`CLAUDE.md` 3단계에 추가 (~6줄):**

- 같은 작업의 구현↔검수 왕복은 **3회차 상한**. 상한 도달, 또는 **정체**(재검수 FAIL 의 지적
  항목이 직전 회차와 동일)가 감지되면 루프를 멈춘다.
- 중단 시의 상태는 **미해결 종결**이다 — PASS 로 간주하지 않고 커밋하지 않는다. 남은 지적
  항목·시도한 수정·막힌 이유를 붙여 **사용자에게 판단을 요청**한다.
- 3회 FAIL 은 대개 구현이 아니라 설계 문제다 — 재설계로 돌아가는 경우 모델 운용 원칙의
  승격 기준 4(직전 설계 반려 회차)가 발동한다. (기존 규정과의 접속점을 명시해 규칙이
  섬으로 남지 않게 한다.)

**`agents/code-reviewer.md`:59 보강 (~4줄):** "라운드를 반복한다" 문장 뒤에 —
회차 상한과 종결의 **관리 주체는 요청자(메인 세션)** 다(검수자는 라운드 간 컨텍스트가 없어
자기 회차를 모른다 — 같은 파일 재검수 모드 절의 전제와 동일). 재검수 요청에 회차(`N/3`)가
명시돼 있으면 Verdict 줄에 그대로 표기하고, 3회차 FAIL 이면 판정을
`FAIL — 상한 도달, 미해결 종결(사용자 판단 필요)` 로 쓴다.

**`commands/code-review.md` 는 고치지 않는다** — 이 파일은 검수 1회의 실행 명세이지 루프의
정의가 아니다. 루프는 CLAUDE.md 3단계에만 존재하므로 종결 규칙도 거기 한 곳에 둔다
(같은 규칙의 사본이 늘면 결함 1 과 같은 분열이 재생산된다).

**상한 3회의 근거**: 경쟁군 수렴 구간(3~5)의 최솟값. 이 저장소는 1인 순차 워크플로우라
대기 비용이 없고, 3회 FAIL 시점이면 이미 검수 보고서 3장이 쌓여 사용자 판단 재료가 충분하다.

### 4.3 결함 3 — 상시 컨텍스트 예산 래칫 (T26 신설)

실측 49,110B vs 선언 "약 45KB"(README.md:112·:233). 잡는 장치를 **기존 패턴 복제**로 만든다 —
새 메커니즘 금지 원칙에 따라 T22-138(선언 상수 vs 실측 수 비교)·T25(문서·상수 정합성)·
`note_failure`/`finish_group`(독립 서브체크 묶음) 패턴을 그대로 쓴다.

**`tests/run.sh` 신규 그룹 `test_always_on_context_budget` (T26):**

```bash
# 상단 상수부에 추가. 래칫이다 — 내리는 것은 자유, 올리는 것은 이 줄을 고치는 커밋에
# 근거(무엇이 왜 늘었는지)를 요구한다. 값은 구현 완료 시점의 실측치로 고정한다.
readonly ALWAYS_ON_CONTEXT_BUDGET_BYTES=<구현 마지막 단계에서 실측>
```

- 서브체크 1: `actual=$(cat "$REPO_ROOT/CLAUDE.md" "$REPO_ROOT/rules/README.md" "$REPO_ROOT/rules/common/"*.md | wc -c | tr -d ' ')`
  — `actual > BUDGET` 이면 `note_failure`. (측정식은 조사 보고서 §4-3 의 실측식과 동일하게 고정 —
  rules/python 은 `paths` 조건부라 측정 대상이 아니다.)
- 서브체크 2·3: `README.md` 의 두 선언 지점(:112·:233)에서 바이트 수치를 `grep -oE` 로 추출해
  상수와 비교 — T25 문서·상수 정합성 패턴의 복제. README 쪽 문구는 기계 추출 가능한 형태로
  고정한다(예: `실측 49,110B` → 패턴 `[0-9,]+B`).
- 등록: `register_and_run_tests` 에 1줄, `total_tests=24 → 26`(T27 포함), 주석
  `# T1~T27 (T11 결번)` 갱신.

**`README.md` 정정**: :112 "약 45KB" → 상수와 같은 실측 수치 + "이 수치는 `tests/run.sh` T26
이 예산 상한으로 강제한다" 1줄. :233 "~33KB/~45KB" 도 같은 방식으로 정정.

**순서 제약**: 이번 라운드 자체가 상시 컨텍스트를 바꾼다(결함 2 가 CLAUDE.md 를 늘리고,
결함 6 이 development-workflow.md 를 다듬는다). 따라서 **T26 의 상수 고정은 전체 작업의
마지막**이어야 한다(§9 작업 순서).

### 4.4 결함 4·5 — manifest v2: 설치 시점 해시 대장 + 툼스톤 삭제 경로

두 결함은 한 스키마를 공유한다. **해시 대장이 먼저다** — 삭제 판정("우리가 설치한 내용
그대로인가")과 낡음 판정("사용자 수정인가 낡은 사본인가")이 둘 다 대장을 조회한다.

#### 데이터 모델

**manifest v2** (`.claude/.coding-harness.json`):

```json
{
  "version": 2,
  "repo_path": "...", "scope": "project|user",
  "installed_at": "...", "installed_from_commit": "...",
  "target_base_dir": "...",
  "files_count": { "CLAUDE_md": 1, "rules": 42, "agents": 4, "commands": 10 },
  "files": {
    "CLAUDE.md": "<sha256>",
    "rules/common/testing.md": "<sha256>",
    "...(관리 파일 전수, 정렬 순)": "..."
  }
}
```

- `files` 대장은 **설치 직후의 레포 원본 해시**다(복사 검증 `verify_managed_files_installed`
  통과 후 기록하므로 대상 파일 해시와 동일). 키는 레포 루트 기준 상대경로, 정렬 고정
  (멱등성 비교 `grep -v installed_at` 로직이 그대로 성립해야 한다).
- BMAD `files-manifest.csv` 의 sha256 3분류 기법 이식이되, 별도 파일이 아니라 기존 manifest
  의 필드다 — 자산 클래스를 늘리지 않는다.

**`removals.txt`** (레포 루트, 배포 대상 아님 — install.sh 가 rules/·agents/·commands/·
CLAUDE.md 만 배포하므로 자동으로 제외된다):

```
# coding-harness 툼스톤 — 레포에서 제거된 관리 파일의 대상측 잔재를 삭제하기 위한 목록.
# 형식: 한 줄에 상대경로 1개. rules/|agents/|commands/ 아래만 허용.
# 규칙: 레포에서 파일을 지우거나 이름을 바꾸는 커밋은 옛 경로를 여기 추가해야 한다.
```

초기 내용은 헤더 주석뿐이다(현재 폐기된 파일이 없다). 항목 형식 제약: `..`·절대경로·글롭·
`CLAUDE.md`·세 네임스페이스 밖 경로 금지.

#### 삭제 판정 (민감 영역 — 명시 규칙)

`process_removals()` 는 항목별로 다음을 판정한다. **지우는 것**과 **절대 안 지우는 것**:

| # | 조건 | 행동 |
|---|------|------|
| D-1 | 대상에 파일 없음 | 조용히 skip (멱등) |
| D-2 | 갱신 전 manifest(v2)의 대장에 항목이 있고 `sha256(대상) == 대장 해시` | **삭제** + `[OK] 제거` 로그. 빈 부모 디렉토리는 `rmdir … 2>/dev/null \|\| true` |
| D-3 | 대장에 항목 없음 (v1 설치본, 또는 대장 이전 파일) | **보호** — 삭제하지 않고 `[보호] <경로> — 설치 이력을 확인할 수 없어 남겨둡니다. 확인 후 수동 삭제하십시오` |
| D-4 | 대장 해시와 불일치 (= 사용자가 수정한 파일 = 툼스톤이 우리가 배포했던 내용과 다른 경우) | **보호** — `--force 로도 삭제하지 않는다`. 수정된 순간 그 내용은 순수한 우리 소유가 아니다(소유권 원칙). 로그로 경로·사유 보고 |
| D-5 | 항목이 형식 제약 위반, 또는 레포에 아직 존재하는 파일을 가리킴(살아있는 파일의 툼스톤 = 레포 버그) | **설치 전체 중단**(fail-closed, 파일 하나도 건드리기 전 — `check_preconditions` 에 검증 편입) |

보호(D-3·D-4)는 설치 실패가 아니다 — 설치는 완주하고 요약에 보호 건수를 싣는다. 삭제가
아니라 잔류가 안전한 기본값이기 때문이다. dry-run 은 D-1~D-4 의 계획만 출력한다.

#### 결함 5 해소 — 충돌의 결정론적 분류

`check_directory_conflict` 가 찾은 「내용이 다른 관리 파일」을 대장으로 분류한다:

- `sha256(대상) == 갱신 전 대장 해시` → **낡은 사본**(우리가 설치한 그대로인데 레포가 전진).
  충돌이 아니다 — `--force` 없이 갱신 대상으로 통과시키고 `[갱신] <경로> (낡은 사본)` 로그.
- 불일치 또는 대장 없음 → **사용자 수정(의심)** — 기존과 동일하게 `--force` 요구.
  (v1 설치본 첫 갱신은 전부 이 분기다 — 보수적 하위호환. 한 번 v2 로 설치되면 이후부터
  자동 분류가 작동한다.)

이로써 `commands/harness-update.md:161-168` 의 두 불릿("Looks like plain staleness…" /
"Looks like a deliberate local customization…") — 결정 가능한 사실을 모델의 문서 해석에
맡기던 절 — 을 **통째로 삭제**하고 다음으로 대체한다: *"install.sh 가 대장으로 자동 분류한다.
exit 1 로 남는 것은 사용자 수정(의심) 파일뿐이다 — 목록과 diff 요약을 보여주고 `--force`
일괄 덮어쓰기 여부를 한 번 묻는다. 내용 해석으로 낡음/커스터마이징을 판정하지 않는다."*
harness-update Phase 1 의 manifest 검증도 `version == 1` → `version ∈ {1, 2}` 로 완화한다.

#### 인터페이스 (bash, 각 함수 50줄 이내)

```bash
# 관리 파일 전수의 "상대경로": "sha256" JSON 오브젝트 본문을 stdout 으로 낸다 (정렬 고정).
build_files_ledger_json()

# manifest 에서 상대경로의 대장 해시를 꺼낸다. 없으면 빈 문자열 (bash 3.2 — grep/sed 조회).
read_installed_ledger_hash(manifest_path, relative_path)

# removals.txt 형식·안전 제약 검증. 위반 시 1 (check_preconditions 에서 호출 — 쓰기 전 중단).
validate_removals_file(removals_path)

# 툼스톤 처리 본체. D-1~D-4 판정. dry-run 지원. 항상 0 (보호는 실패가 아니다).
process_removals(removals_path, previous_manifest_path)

# 내용이 다른 관리 파일 1개를 "stale" | "modified" 로 분류해 stdout.
classify_differing_file(relative_path, target_file_path, previous_manifest_path)
```

테스트 시임: `REMOVALS_FILE="${CODING_HARNESS_REMOVALS_FILE:-$REPO_ROOT/removals.txt}"` —
레포의 실제 removals.txt 는 비어 있으므로, 삭제 시나리오 테스트는 이 환경변수로 임시
툼스톤을 주입한다. 기존 스위트가 `HOME` 치환으로 하는 것과 같은 성격의 시임이다.

#### 실행 순서 (perform_installation 내)

`check_preconditions(+ validate_removals_file)` → 갱신 전 manifest 를 변수에 보관 →
`install_directory` ×3 (충돌 분류는 이 앞의 check 단계에서) → `process_removals` →
`install_claude_md` → `save_manifest_file`(v2, 새 대장). 대장은 removals 처리 **후** 레포
현재 파일로만 기록되므로 제거된 파일은 자연히 대장에서 사라진다.

#### v1 → v2 마이그레이션·하위호환

- install.sh 는 manifest 를 읽어 동작을 바꾸지 않고 매 실행 재생성한다(기존 구조 유지).
  v1 설치본 위에서 새 install.sh 를 돌리면: 충돌 분류·삭제 판정이 전부 보수 분기(D-3)로
  빠지고, 완료 시 manifest 가 v2 로 재기록된다. **마이그레이션 코드가 따로 없다** — 첫
  재설치가 곧 마이그레이션이다.
- 소비자는 harness-update 하나뿐(실측: `grep -rn coding-harness.json` — install.sh·harness-update.md·
  README·tests). version ∈ {1,2} 완화로 양쪽을 받는다.

### 4.5 결함 6 — development-workflow.md 의 도구 고유명사 의존 제거 (판정 7-1)

`rules/common/development-workflow.md:10-15` 의 0단계를 능력 기반으로 재서술한다.
배포판이 깔아주지 않는 도구(Context7 = MCP, Exa)를 "필수 절차"로 규정하는 문장만 고친다:

- *"Library docs second: Use Context7 or primary vendor docs…"* →
  *"Library docs second: confirm API behavior against primary vendor docs before implementing —
  via a docs-lookup tool if one is installed (e.g. an MCP docs server), otherwise by fetching
  the official docs directly."*
- *"Exa only when the first two are insufficient…"* →
  *"Broader web research only when the first two are insufficient, using whatever search
  capability the session has."*

나머지 항목(GitHub search·registries)은 `gh`·웹 접근만 요구하므로 유지한다. `.mcp.json`
배포는 하지 않는다(§7-1 판정 그대로 — npx/uvx 기동은 「외부 의존 0」 위반). 이 파일은 상시
로드분이므로 재서술이 바이트를 늘리지 않게 다듬고, 최종 크기는 T26 측정에 흡수된다.

### 4.6 결함 7 — `rules/python/` 신설 (판정 7-2: 오염 회수)

`~/.claude/rules/python/` 5파일(2026-04-15, pytest 지시)이 이 저장소에서 `.py` 를 여는 순간
로드돼 자기 원칙(stdlib unittest — tests/run.sh:2577)과 충돌한다. 소유권 원칙상 install.sh 는
남의 파일을 건드리지 않으므로, **같은 파일명 5개를 레포가 배포**해 관리 파일로 재분류시킨다
— 그러면 기존 오염본은 「관리 파일의 수정본」이 되어 `--force` 덮어쓰기 대상이 되고, 이후
해시 대장 아래로 들어온다. 회수 시 1회 `--force` 가 필요함을 harness-update 절차 문서에 명시한다.

**파일 구조**: `rules/typescript/` 5개의 구조를 그대로 따른다 — frontmatter
`paths: ["**/*.py", "**/*.pyi"]`(오염본과 동일 glob → 조건부 로드, 상시 예산 49,110B 불변),
첫 줄 `> This file extends [common/xxx.md](../common/xxx.md) with Python specific content.`,
영어, 분량은 typescript 총 319줄 규모(파일당 20~60줄, coding-style 만 그 이상 허용).

**내용은 창작하지 않는다** — `hub/bin/*.py` 15개·`tests/hub/*.py` 16개에서 귀납한 관측 사실만
싣는다(전 항목 실측 검증 완료):

| 파일 | 실릴 관측 사실 (근거) |
|------|----------------------|
| `coding-style.md` | stdlib 우선·제3자 의존은 명시적 결정으로만(15파일 전수: 3rd-party import 0건) · 모든 시그니처에 타입 힌트, `int \| None` 3.10+ 문법(hub.py:25, hub_collect.py:99) · `@dataclass(frozen=True)` 로 불변 강제(hub_model.py:22·46 외 8곳) · UPPER_SNAKE 상수 + 근거 주석(hub_hook.py:29-49) · `_` 접두사 프라이빗 헬퍼(hub_hook.py:85) · pathlib 사용 |
| `testing.md` | **stdlib `unittest` 가 기본값 — pytest 채택은 프로젝트 CLAUDE.md 에 기록된 명시적 결정일 때만**(common/testing.md 의 Language note 관례로 오버라이드 명시) · `python3 -m unittest discover -s <dir> -t <root>`(tests/run.sh:2577) · setUp/tearDown 에서 모듈 상수 치환 후 원상복구로 격리(test_hub_hook.py:28-49) · `unittest.mock.patch.object`(test_hub_hook.py:96-99) · AAA 는 common/testing.md 따름 |
| `patterns.md` | 순수 모듈/I-O 모듈 분리 — 순수 모듈은 모듈 docstring 에 ★순수 표기, 파일시스템·시각·환경 미접근(hub_model.py:1-3, T25-10 이 기계 검증: tests/run.sh:2691-2698) · 모듈 간 통신은 frozen dataclass 계약으로만(hub_model.py 헤더) · 예상된 실패는 명시적 예외 클래스(HubCollectError, hub_collect.py:60-65) · 순환 의존은 잎 모듈 분리로 차단(hub_server_state.py:1) |
| `hooks.md` | 훅·상태줄 진입점은 **항상 exit 0**(hub_hook.py:179-185, hub_statusline.py 동일 패턴) · 최상위 `except Exception` 삼킴은 진입점 1곳에만 허용 · 무거운 작업은 분리 프로세스로 spawn, 훅 자신은 수 ms(hub_hook.py 헤더) |
| `security.md` | 프롬프트·자격 증명을 평문 로그에 남기지 않는다 — 남길 땐 상한·리텐션·옵트아웃 고지 필수(hub.md:147-148) + 시크릿 마스킹(결함 8 배선 후 hub_hook.redact_secret_tokens 를 선례로 인용) · subprocess 는 argv 리스트, 셸 미경유(hub_usage_fetch.py:61-63) · 요청 문자열로 경로 조립 금지, 화이트리스트 조회 키로만(hub_server.py:28-33) · 토큰은 지역 변수로만 |

**카운트 상수 동반 수정 — 전수 실측 결과** (이 표가 곧 수정 목록이다):

| 위치 | 현재 | 수정 |
|------|------|------|
| `install.sh:12` | `RULES_FILE_COUNT=37` | `42` |
| `tests/run.sh:245` | `assert_equals 37`(T1) | `42` |
| `tests/run.sh:379` | `assert_equals 37`(T4) | `42` |
| `README.md:20` | "큐레이션 37개" + 스택 서술 | `42` + Python 언급 |
| `README.md:106` | rules 37 · "12개 항상 · 25개 조건부" | `42` · "12개 항상 · 30개 조건부" |
| `README.md:110` | "합계 52개 파일" | `57` |
| `README.md:222` | "37개 규칙 파일…스택" | `42` + Python |
| `README.md:224-230` | 분류 표 | `python/ (5, 조건부, **/*.py)` 행 추가 |
| `README.md:300-306` | 파일 구조 트리 "37개 규칙" | `42` + `python/` 줄 + 루트에 `removals.txt` 줄 |
| `rules/README.md:35` | "All 37 rules" | `42` |
| `rules/README.md:47-55` | "Conditionally loaded (17 files)" | `22` + python/ 불릿 |
| `rules/README.md` 상단 트리·서두 | "curated for a JS/TS + React + web stack" | python/ 반영 |

manifest `files_count.rules` 는 상수를 참조하므로 자동 추종. `tests/run.sh` 의 다른 37 리터럴은
없음을 grep 으로 전수 확인했다(:245·:379 두 곳뿐).

**T12 확장**: react/coding-style.md 의 frontmatter 검사와 같은 형태로
`./.claude/rules/python/coding-style.md` 의 `---`/`paths:` 검사를 서브체크로 추가한다.

### 4.7 결함 8 — 훅 로그 시크릿 스크럽 (선형 시간)

**적용 지점**: `hub_hook.py` 의 `_project_fields` 안, 파이프라인을
`strip_auto_injected_blocks → redact_secret_tokens → _clip_prompt` 로 고정한다.
**스크럽이 자르기보다 먼저**여야 하는 이유 — 잘린 뒤에 스크럽하면 500자 경계에 걸린
시크릿이 패턴 불일치로 살아남아 앞부분이 유출된다. 전체 입력에 대한 선형 스캔이므로
"세션을 막지 않는다" 절대 규칙과도 충돌하지 않는다.

**순수 함수 1개** (`_clip_prompt` 옆):

```python
SECRET_REDACTION_MARK = "[REDACTED]"

def redact_secret_tokens(prompt: str) -> str:
    """알려진 시크릿 토큰 형태를 기록 전에 마스킹한다. 선형 시간 — 백트래킹 폭발 형태 금지."""
```

**패턴 설계 — 선형성 논증이 핵심 요구사항이다** (ECC 원본의 catastrophic backtracking
CPU 100% 고착 이슈가 이식 조건): 각 대안을 **리터럴 접두사 + 단일 문자클래스 한정 수량자**
로만 구성한다. 중첩 수량자(`(a+)+`)·패턴 내 백레퍼런스·인접 모호 수량자를 금지하고, 이
제약을 함수 옆 주석으로 명문화해 패턴 추가 시의 가드로 삼는다.

```python
SECRET_TOKEN_PATTERN = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{10,}"                      # Anthropic
    r"|sk-[A-Za-z0-9]{20,}"                            # OpenAI 계열
    r"|AKIA[0-9A-Z]{16}"                               # AWS access key
    r"|gh[pousr]_[A-Za-z0-9]{36}"                      # GitHub 토큰
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"                   # Slack
    r"|AIza[0-9A-Za-z_-]{35}"                          # Google API
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"  # JWT
    r"|-----BEGIN [A-Z ]{0,24}PRIVATE KEY-----[A-Za-z0-9+/=\s]*"
    r"(?:-----END [A-Z ]{0,24}PRIVATE KEY-----)?"
    r"|[Bb]earer +[A-Za-z0-9._~+/=-]{16,}"
)
KEY_VALUE_SECRET_PATTERN = re.compile(      # api_key=..., token: "..." — 키 이름은 보존
    r"(?i)\b(api[_-]?key|secret|token|password|passwd)(\s*[:=]\s*)"
    r"(\"[^\"\n]{6,}\"|'[^'\n]{6,}'|[A-Za-z0-9_/+.\-]{6,})"
)
```

치환: 전자는 전체를 `[REDACTED]` 로, 후자는 `\1\2[REDACTED]` 로(키 이름을 남겨야 툴팁
발췌가 문맥을 유지한다). 과잉 마스킹은 허용한다 — 이것은 관측 로그 발췌이지 원문 보존이
아니며, 원문은 사용자 세션에 그대로 있다.

**기존 원자성 논거와의 정합**: `[REDACTED]`(10 ASCII자)는 마스킹 대상 최소 길이(6자
값 + 키)보다 길 수 있으나, 마스킹 후 `_clip_prompt` 가 500자로 자르므로 줄 길이 상한
논거(단일 write 버퍼, test_recorded_line_stays_within_single_write_buffer)는 변하지 않는다
— 최악 문자는 여전히 제어문자다.

**테스트** (`tests/hub/test_hub_hook.py` 에 `SecretRedactionTest(HubHookScenarioTest)` 신설,
기존 클래스들의 `_record_prompt` 헬퍼 관례를 따름):

1. Anthropic 키가 마스킹되고 앞뒤 산문은 보존된다
2. `AKIA…`·`ghp_…`·JWT 각 1건 마스킹
3. `api_key=abc12345` → `api_key=[REDACTED]` (키 이름 보존)
4. **경계 유출 방지** — 490자 산문 + 시크릿으로 500자 경계에 걸치게 구성 → 기록된 발췌에
   시크릿 접두사가 없어야 한다 (스크럽-후-자르기 순서의 회귀 가드)
5. 단어 "token"·"secret" 만 있는 일반 산문은 건드리지 않는다
6. `record_prompt_excerpt:false` 경로와의 무간섭 (필드 자체가 없음)
7. **선형성 회귀 가드** — 준-일치 문자열 대량 반복(예: `"sk-" * 50000`) 입력이 넉넉한
   상한(2초) 안에 끝난다. 시간 기반 테스트의 flake 위험은 상한을 재앙적 소요(분 단위)와
   정상 소요(ms)의 중간 훨씬 아래가 아닌 넉넉한 값으로 두어 흡수한다

**고지 문구 동반 수정** — `hub_hook.py` 상수 주석이 명시한 동기화 대상 그대로:
- `commands/hub.md:147-148`: "…평문으로 최대 7일 보관됩니다" 뒤에 *"알려진 시크릿
  패턴(API 키·토큰·개인키 등)은 기록 전에 `[REDACTED]` 로 마스킹됩니다"* 추가.
- `hub/README.md:142-154` 프라이버시 고지 절: 동일 문구 추가.

## 5. 파일 구조와 모듈 경계

레이어 원칙(외부 세계 코드와 순수 로직 분리) 준수 지점:

- `redact_secret_tokens` 는 **순수 함수**로 hub_hook.py 에 둔다 — 별도 모듈로 빼지 않는다
  (사용처가 1곳, hub_hook 은 진입점이지만 이 함수 자체는 입력→출력 뿐이라 단위 테스트 가능.
  파일은 189줄 → 약 230줄로 800줄 한도에 여유).
- install.sh 신규 함수 5개는 전부 기존 함수들과 같은 층위(검증/판정/실행 분리)로, 각 50줄
  이내·중첩 3단계 이내로 설계했다.
- `removals.txt` 는 md 실행 명세가 아니라 install.sh 의 **데이터**다 — 실행 로직을 md 밖으로
  빼는 것이 아니므로 자산 클래스 우려에 해당하지 않는다(로직은 전부 install.sh 안).
- `rules/python/` 은 기존 `rules/<stack>/` 모듈 경계를 그대로 따른다.

## 6. 설계 결정과 근거

1. **결함 1 을 통일이 아니라 역할 분리로 푼다** — "커맨드 경로는 죽었다"는 조사 보고서의
   판정이 이 저장소 밖에서 반증됐다(외부 2 프로젝트 실사용 32+ 문서). 반증된 전제 위의
   통일은 더 큰 분열을 만든다.
2. **삭제는 대장 일치 시에만, 강제 불가** — 민감 영역 원칙. "지울 수 있음을 증명 못 하면
   지우지 않는다"가 소유권 원칙의 삭제판이다.
3. **manifest v2 는 필드 추가 + version 승급** — 선례(`docs/prps/hub-dashboard.md:670`)는
   "필드 추가는 version 을 안 올린다"였으나, 이번엔 **소비자의 해석 의무가 생기는 추가**
   (대장 조회·removals 판정)라 승급이 맞다. harness-update 의 `version == 1` 검증이 실제로
   막아서기 때문에 양쪽({1,2}) 수용으로 완화한다.
4. **새 메커니즘 0** — T26·T27 은 전부 기존 패턴(T22-138 상수 비교·T25 문서 정합·T12
   frontmatter·note_failure 묶음·HOME 치환식 시임)의 복제다. YAGNI: 위트니스 마커 프레임워크
   같은 범용 장치는 만들지 않는다.
5. **스크럽은 차단이 아니라 마스킹** — 훅의 절대 규칙("세션을 막지 않는다")상 시크릿 발견
   시에도 이벤트 기록은 계속돼야 한다. 마스킹 후 기록이 유일하게 양립하는 형태다.
6. **T26·T27 을 기존 그룹에 얹지 않고 신설** — T22(대시보드)·T25(허브)는 이름이 곧 검사
   대상이다. 예산·설치기 삭제 검사를 거기 얹으면 실패 메시지의 소속이 거짓말을 한다.
   `total_tests` 계약 갱신(24→26)이 더 싼 비용이다.
7. **removals 테스트 시임을 env 변수로** — 대안(테스트가 레포 사본을 뜨는 것)은 실행 시간과
   디스크를 크게 늘린다. `HOME` 치환과 같은 성격의 주입점 1개가 최소 비용이다.

## 7. 작업 순서와 의존

```
1. 결함 1 (CLAUDE.md·prp-plan·prp-implement·coding-harness.md 각주)   — 독립
2. 결함 2 (CLAUDE.md 3단계·code-reviewer.md)                      — 독립, CLAUDE.md 는 1과 같은 파일
3. 결함 6 (development-workflow.md)                                — 독립
4. 결함 7 (rules/python 5파일 → 카운트 전수 12곳 → T12 확장)      — install.sh 상수 포함
5. 결함 4·5 (해시 대장 → 삭제 경로 → 충돌 분류 → harness-update.md → T20/T21 갱신 → T27)
   ※ 대장이 먼저다 — 삭제 판정·낡음 판정이 대장을 조회한다
   ※ 4(RULES_FILE_COUNT=42) 이후여야 T1/T4 와 manifest files_count 가 정합
6. 결함 8 (redact 함수 → 배선 → 테스트 → hub.md·hub/README.md 고지)  — 독립
7. 결함 3 (T26 + README 수치)  — **반드시 마지막**: 1·2·3 이 상시 컨텍스트 바이트를 바꾼 뒤
   실측치로 상수를 고정한다
8. 전체 검증: bash tests/run.sh (26그룹) + python3 -m unittest discover -s tests/hub
```

## 8. 테스트 계획

| 검증기 | 대상 | 케이스 |
|--------|------|--------|
| T26 (신설) | 결함 3 | 실측 ≤ 예산 상수 · README :112/:233 수치 == 상수 (3 서브체크) |
| T27 (신설) | 결함 4·5 | v2 대장 항목 수 == 관리 파일 수 · 툼스톤 D-2 삭제 · D-4 보호(수정본) · D-3 보호(v1 manifest) · D-5 중단(형식 위반·살아있는 파일) · dry-run 무부작용 · 빈 removals no-op · 대장 일치 낡은 사본은 --force 없이 갱신(대상·대장을 함께 조작해 시뮬레이션) |
| T1/T4 갱신 | 결함 7 | rules 42개 설치·복원 |
| T12 확장 | 결함 7 | python/coding-style.md frontmatter 보존 |
| T20/T21 갱신 | 결함 4 | `"version": 2`(:975) · `files` 대장 필드 존재 · dry-run 미생성(기존) |
| T14 (무변경 확인) | 결함 5 | 사용자 수정 파일은 여전히 --force 요구 — 회귀 없음을 기존 케이스가 보증 |
| SecretRedactionTest (신설) | 결함 8 | §4.7 의 7케이스 |
| 기존 스위트 전체 | 회귀 | tests/run.sh 26그룹 + tests/hub 16모듈 전부 통과 |

순수 로직 단위 테스트 대상: `redact_secret_tokens`(입력→출력), install.sh 판정 함수들은
bash 라 T27 시나리오 테스트로 대신한다(기존 스위트의 방식 그대로).

## 9. 제외 항목과 사유

| 항목 | 사유 |
|------|------|
| 결함 9 (`.tsx` 조건부 로딩 붕괴 — 24개 65,676B) | rules glob 체계 재설계는 독립 과제 — react-native/ 8개의 매칭 전략 자체를 다시 정해야 한다. 별도 PRP |
| 결함 10 (`commands/dashboard.md` 87,305B 분할) | 디렉토리 구조 변경 + `COMMANDS_FILE_COUNT` 동반 수정 — 전체 경로 별도 회차 |
| §5 티어 2 전부 (차단형 훅·SessionStart 재주입·PreCompact·검수 렌즈 분할·dashboard 분할·핸드오프 규약·writing-for-agents) | 조건부 판정 자체가 "전제조건 검토 후" — 결함 수정이 아니다 |
| 위트니스 마커 | 결함 수정이 아니라 검증 기능 추가. 이번 라운드의 산문 수정(결함 1·2·6)이 안착한 뒤 별도 도입 판단 |
| `install.sh --check` | 진단 기능 추가 — 결함 수정 아님 |
| 안정 요구사항 ID (FR-###) | PRP 양식 개편 — 결함 수정 아님 |
| statusline payload 수확 | 수확 누락은 결함이 아니라 미구현 기능 |
| 거절 기록 디렉토리 (`.out-of-scope/`) | 신규 자산 클래스 — 기능 추가 |
| §7-3 (eval 도구화) | 판정이 "안 한다" — 작업 없음 |
| `~/.claude/rules/` 의 python 외 오염 10개 디렉토리 | 이 저장소 원칙과 정면 충돌하는 것은 python 뿐. 나머지는 소유권 원칙상 건드리지 않고, 회수 여부는 별도 판단 |

## 10. 롤백 가능성 — manifest v2 를 되돌릴 때 깨지는 것

1. **v1 install.sh 가 v2 manifest 를 만나면**: 읽는 것은 `grep -v installed_at` 멱등 비교뿐
   → 불일치로 판정하고 v1 로 재기록. 크래시 없음. **단, 되돌린 뒤 반드시 install.sh 를 1회
   실행해야** manifest 가 v1 로 돌아온다.
2. **구(舊) harness-update.md 가 v2 manifest 를 만나면**: `version == 1` 검증 실패로 중단 —
   위 1회 재설치 전까지 `/harness-update` 가 죽는다. 롤백 절차에 "재설치 먼저"를 명시할 것.
3. **이미 수행된 툼스톤 삭제**: 레포 롤백이 해당 파일을 레포에 되살리면 다음 설치가 누락
   파일로 간주해 자동 복원한다 — 데이터 손실 없음(우리가 배포한 내용만 지웠으므로).
4. **rules/python 회수의 롤백**: 레포에서 5파일을 지우면 대상측 사본은 다시 「남의 파일」로
   재분류돼 영구 잔류한다 — 정확히 결함 4 의 상태로 회귀. 롤백하려면 removals.txt 에 5파일을
   올려야 한다(이 상호작용이 툼스톤의 존재 이유를 재확인한다).
5. **이미 마스킹돼 기록된 이벤트**: 원문은 복구 불가하나 이것은 의도된 방향(시크릿 비보관)
   이다. 코드 롤백은 hub_hook.py·테스트 2파일 revert 로 끝난다.

## 11. 리스크와 대안

- **리스크 1 — bash 3.2 에서의 대장 조회 성능**: 파일 57개 × grep 조회는 재설치 1회당 수십 ms
  수준으로 무시 가능하나, 관리 파일이 수백 개로 늘면 재검토. 대안(python3 로 JSON 파싱)은
  install.sh 의 "순수 bash" 선언(README:297)을 깨므로 기각.
- **리스크 2 — 시간 기반 선형성 테스트의 flake**: 상한 2초는 재앙적 백트래킹(분 단위)과
  3자릿수 여유가 있다. 그래도 CI 부하로 흔들리면 케이스를 입력 크기 2단 비교(2배 입력 ≤
  ~2배 시간)로 교체한다 — 채택하지 않은 이유는 첫 형태가 더 단순해서다(KISS).
- **리스크 3 — 스크럽 과잉 마스킹의 사용성 손상**: `token: <일반 단어>` 류 오탐 가능.
  발췌는 관측 보조 데이터라 수용하고, 불만이 실측되면 패턴을 좁힌다(측정 없는 선제 완화 금지).
- **검토 후 기각한 대안 1 — removals 를 manifest 안의 `removed` 배열로**: 대상측 파일(사용자
  영역)에 레포의 폐기 이력을 싣게 돼 소유권 방향이 역전된다. 툼스톤은 레포 자산이어야
  레포 커밋과 함께 움직인다.
- **검토 후 기각한 대안 2 — 시크릿 스크럽을 별도 모듈(hub_scrub.py)로**: 사용처 1곳에 파일
  1개는 추측성 추상화(YAGNI). hub/bin 파일 수 증가는 HUB_FILE_COUNT(T25-1)·hub/install.sh
  동반 수정까지 부른다.
