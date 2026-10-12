# CLAUDE.md 배포용/프로젝트용 분리 — 배포 채널 이관 (PRP)

> 입력 정본: `docs/prps/claude-md-split-decision-brief.md` (4앵커 독립 설계 + 3렌즈 심판, 승자
> 「안 3 — 배포 채널 이관(deploy-to-rules)」 만장일치 8점·치명 결함 0건).
> 브리프의 수치는 `9145ef3` 시점이라 **이 문서의 모든 수치·줄 번호는 현재 체크아웃
> `46ecb5b` 로 재실측했다.** 브리프와 어긋난 곳은 §2.3 에 명시했다.

> 각주(2026-09-02, 검수 2회차) — 본문의 산술·명명 착오 2건을 여기서 정정한다(아래 §5.5·
> §5.6 등 본문 표기는 소급 수정하지 않는다 — 관행은 `docs/prps/coding-harness.md` 각주 참조):
> 1. §5.5 "56항목"·§5.6 "합계 57→56"은 산술 착오다. `46+4+10 = **60**` 이 맞고,
>    구현·README·manifest 실측이 전부 60 으로 일치한다(검수자 e2e 확인). §5.6 오류는
>    "57 − CLAUDE.md 1(제거) = 56"까지만 계산하고 rules 42→46 증분(+4)을 반영하지 않은
>    것으로 보인다 — 올바른 값은 57 → **60**.
> 2. 본문 전체(§3·§5.1·§5.2·§5.4·§8·§11·§12·§13)의 "T28"(및 T28-1~T28-5)은 이 문서
>    작성 시점의 계획명이다. 구현 착수 전에 `audit-remediation` 의 Q4·R1·R2 가 먼저
>    병합되며 `tests/run.sh` 의 T28·T29·T30 을 이미 선점했고, 그 결과 이 설계의 검사
>    그룹은 실제로 **T31**로 명명됐다(`tests/run.sh` 의 `test_rules_workflow_guardrails`
>    함수 — 이후 편집으로 줄 번호가 이동하므로 줄 번호 대신 함수명으로 가리킨다) —
>    본문의 T28-1~T28-5 는 구현의 T31-1~T31-5 에 대응한다.

## 0. 결론 요약 (승인이 필요한 5건)

| # | 결정 | 요지 |
|---|------|------|
| A-1 | 착수 순서 | `feature/audit-remediation` 의 **Q5 까지 머지된 뒤** 착수 (경성 선행). R1~R3 은 병행 허용 — 후행자가 T26 상수를 재실측한다 (§10) |
| A-2 | 은퇴 절차 | `~/.claude/CLAUDE.md` 는 **`mv` 원자 개명**으로 백업=삭제를 한 동작으로 처리. 판정은 manifest 대장 해시 1차, 레거시는 이중 센티널 2차, 불일치는 fail-closed 보호 (§5.4) |
| A-3 | manifest v3 | `MANIFEST_VERSION` 2→3. **브리프의 "2로 올린다"를 번복** — `46ecb5b` 에서 이미 2 다 (§2.3, 결정 5) |
| A-4 | 새 루트 CLAUDE.md 골자 | 프로젝트 전용 ~70줄. 금지사항 2건 포함: 이 저장소에 `--scope project` 자기 설치 금지 · 실제 `$HOME` 대상 설치 실행 금지 (§5.2) |
| A-5 | 약점 4 수용 | 이관은 "이동만" — 「코드 품질 가이드라인」과 `rules/common/coding-style.md` 의 중복은 이번에 제거하지 않는다 (§9 약점 4) |

---

## 1. 요구사항 요약

레포 루트 `CLAUDE.md`(232줄, 16,661B)는 **범용 개발 지침**인데 배포 대상이면서 동시에
이 저장소 자신의 프로젝트 지침 자리를 점유한다. 이로 인해 (1) 이 저장소에서 같은 내용이
이중 로드되고, (2) 루트가 배포물이라 정작 이 저장소의 프로젝트 지침(아키텍처·병목·검증
명령)을 쓸 자리가 없고, (3) `--scope project` 설치가 대상 프로젝트의 `./CLAUDE.md` 를
파괴할 수 있다(충돌 exit 1 / `--force` 덮어쓰기). **배포 목적지를 옮긴다**: 범용 지침
223줄을 `rules/workflow/` 4파일로 내보내고(frontmatter 없음 → launch 로드, user scope
전역 적용), 루트 `CLAUDE.md` 는 coding-harness 전용 프로젝트 지침(~70줄)으로 교체하며,
`install.sh` 는 CLAUDE.md 배포를 중단하고 기존 배포본(`~/.claude/CLAUDE.md`)을 안전하게
은퇴시킨다.

**사용자 확정 승인 (2026-08-28)**: `~/.claude/CLAUDE.md` 는 **백업 후 삭제한다.**
남기면 같은 내용이 위치만 바꿔 이중 로드되기 때문이다. 이 문서는 그 삭제를 "이 저장소가
해 본 적 없는 종류의 쓰기"로 취급하고 §5.4 에서 방어를 설계한다.

## 2. 확정 전제

### 2.1 규격 사실 (브리프의 심판이 공식 문서를 WebFetch 로 재확인한 것 — 인용)

- `~/.claude/rules/` 의 frontmatter 없는 규칙은 `~/.claude/CLAUDE.md` 와 네 성질(전 프로젝트
  적용 · launch 로드 · user < project 우선순위 · 컴팩션 후 디스크 재주입)이 전부 같다.
- 서브에이전트도 계층 전체를 상속한다.
- 발견 이름은 고정 — `CLAUDE.md`/`CLAUDE.local.md`/`.claude/CLAUDE.md`/`.claude/rules/*.md` 뿐.
  따라서 **레포의 `rules/` 트리는 구조적으로 미발견**이다(이 저장소에서 삼중 실측).
- `/init`·`/doctor`·`/memory` 는 모두 루트 CLAUDE.md 에 내용을 써 넣도록 능동 제안한다 —
  루트를 배포물로 유지하는 설계는 하네스 중력과 싸운다(지속성 심판의 결정적 논거).

### 2.2 현재 baseline 실측 (46ecb5b)

| 항목 | 실측 |
|------|------|
| `CLAUDE.md` | 232줄 · 16,661B (9145ef3 대비 +9줄: 검수 3회차 상한 :100-106 · `/prp-plan` 산출 경로 :72-74) |
| `rules/` | **42파일** (common 11 + README 1 + python 5 + react-native 8 + react 5 + typescript 5 + web 7) |
| `install.sh` | 703줄 · `RULES_FILE_COUNT=42`(:12) · **`MANIFEST_VERSION=2`(:17)** · 툼스톤 `validate_removals_file`(:297-324)·`process_removals`(:343-385) |
| `removals.txt` | 헤더 3줄뿐 — `rules/|agents/|commands/` 아래만 허용 명시 |
| `tests/run.sh` | 5,704줄 · 26그룹(T1~T27, T11 결번) · `ALWAYS_ON_CONTEXT_BUDGET_BYTES=50314`(:17) — 실측과 정확히 일치 |
| HOME 치환 선례 | `tests/run.sh` :304 · :940 · :977 · :2672 (+hub :2977·:2982) — 브리프 정정("이미 4곳") 재확인 |
| `commands/harness-update.md` | :24 manifest `version ∈ {1, 2}` 검증 · :184 `--force` 가 CLAUDE.md 를 `.bak-` 백업한다는 서술 |

### 2.3 브리프와 어긋난 곳 (재실측으로 정정)

1. **`MANIFEST_VERSION` 은 이미 2 다** (`fix/tier0-defects` 가 올렸다). 브리프의 "2로
   올린다"는 낡았다 → 이 설계는 **3으로 올린다** (결정 5).
2. **rules 는 41→46 이 아니라 42→46** (`rules/python/` 5파일 재도입 반영).
3. 브리프의 "깨지는 것 11건" 줄 번호는 전부 밀렸다 → §7 에서 **12건**으로 재산출.
4. `commands/harness-update.md` 의 「작은 diff 허위 문구」는 이미 제거돼 겹침이 없다. 이 설계가
   건드릴 곳은 :24(version 집합)와 :184(백업 서술) 2곳뿐이다.
5. 툼스톤 신설로 **약점 9(롤백 orphan)의 해법이 생겼다** — 단 네임스페이스 확장 없이 (§5.4).

## 3. 영향 범위 (신설 4 + 수정 9 = 13파일)

| 파일 | 동작 | 이유 |
|------|------|------|
| `rules/workflow/role-separation.md` | 신설 | 응답 언어 + 위임 승인(원문 보존) + 작업 분류 + 1~3단계 + 공통 규칙 (~130줄) |
| `rules/workflow/model-routing.md` | 신설 | 모델 운용 원칙 (~50줄) |
| `rules/workflow/code-quality-baseline.md` | 신설 | 구조·가독성·설계 원칙·성능·강제 수단 (~52줄) |
| `rules/workflow/project-instructions-checklist.md` | 신설 | 프로젝트 CLAUDE.md 5항목 체크리스트 (~15줄) |
| `CLAUDE.md` | 교체 | 전역 지침 → coding-harness 프로젝트 지침 (~70줄) |
| `install.sh` | 수정 | CLAUDE.md 배포 제거(−약 75줄) + 은퇴 함수(+약 55줄) + 상수 2건 |
| `tests/run.sh` | 수정 | 파손 12건 재조준(§7) + T28 신설(§8) + `total_tests` 26→27 |
| `README.md` | 수정 | 설치 표·안전장치 절·트리·실측 수치 2곳·트러블슈팅 (§5.6) |
| `rules/README.md` | 수정 | 구조도에 workflow/ 추가 · 42→46 · Always loaded 12→16 |
| `commands/harness-update.md` | 수정 | :24 `{1,2}`→`{1,2,3}` · :184 은퇴로 재서술 |
| `agents/design-architect.md` | 수정 | "두 CLAUDE.md" 서술 최소 정정 (§5.7) |
| `agents/implementer.md` | 수정 | "전역·프로젝트 CLAUDE.md" 서술 최소 정정 |
| `agents/code-reviewer.md` | 수정 | 동일 |

`removals.txt` 는 **이번에 변경 없음** (롤백 시에만 사용 — §9 약점 9).
`docs/prps/coding-harness.md` 등 기존 PRP 는 역사 문서로 무수정 (R2 와의 충돌 회피 겸함).

## 4. 구현 전 필독 (구현자용)

| 우선순위 | 파일:줄 | 이유 |
|---|---|---|
| P0 | `install.sh:295-385` | 툼스톤 계약(D-1~D-5) — 은퇴 함수가 같은 로그·반환 계약을 따른다 |
| P0 | `install.sh:200-216` | `read_installed_ledger_hash` — 은퇴 판정이 재사용하는 대장 조회 |
| P0 | `install.sh:663-689` | `perform_installation` 순서 계약("갱신 전 대장" 주석 :672-677) |
| P0 | `tests/run.sh:404-535` | T5·T6·T7 현행 문면 — 재조준 대상 |
| P1 | `tests/run.sh:5437-5449` | T27-2 의 대장 주입 기법 — 은퇴 테스트가 그대로 복제 |
| P1 | `tests/run.sh:5350-5403` | T26 공식·상수·README 선언 3중 일치 구조 |
| P1 | `CLAUDE.md` 전문 | 이관 원문 — 특히 :20-44 위임 승인 문단은 **원문 보존** |
| P2 | `docs/prps/tier0-defect-fixes.md` §4.4·§6 | manifest v2·툼스톤의 원 설계와 결정 관행 |

## 5. 항목별 설계

### 5.1 `rules/workflow/` 4파일 — 이관 매핑 (현재 CLAUDE.md 줄 기준)

| 신설 파일 | 이관 원문 (CLAUDE.md 줄) | 규모 |
|---|---|---|
| `role-separation.md` | :10-12 응답 언어 · :16-18 워크플로우 서두 · :20-44 위임 승인(**원문 보존**) · :46-67 작업 분류 · :68-106 1~3단계 · :107-131 공통 규칙 | ~130줄 |
| `model-routing.md` | :132-175 모델 운용 원칙 | ~50줄 |
| `code-quality-baseline.md` | :177-223 코드 품질 가이드라인 | ~52줄 |
| `project-instructions-checklist.md` | :225-232 체크리스트 | ~15줄 |

원칙: **이동만 한다.** 문장 재작성·중복 제거·개선 금지(결정 9). 예외 4가지:

1. **서문 교체**: 원문 :1-6 의 "# 전역 개발 지침 (~/.claude/CLAUDE.md)" 헤더는 각 파일의
   새 제목으로 바뀐다. `role-separation.md` 서문에 다음 두 문장을 넣는다 (약점 2·3 완화):
   - "이 규칙은 coding-harness 가 user scope 로 배포한다. **프로젝트 CLAUDE.md·프로젝트
     rules 와 충돌하면 프로젝트 쪽을 따른다** (user-level rules 는 project rules 보다
     먼저 로드돼 우선순위가 낮다)."
   - "`common/agents.md` 의 에이전트 로스터·`common/development-workflow.md` 의 5단계
     서술과 겹치는 부분은 이 문서가 우선한다."
2. **`paths:` frontmatter 를 절대 넣지 않는다** — launch 로드가 설계의 성립 조건이다
   (T28-2 가 고정). 안 2 가 탈락한 이유가 정확히 이것이다(카브아웃을 `paths:` 뒤에 둠).
3. 파일 간 상호 참조는 상대 링크(`[model-routing.md](model-routing.md)`)로 — rules 간
   로드 순서는 규격이 보장하지 않으므로 순서 의존 서술 금지.
4. 이관 본문 안의 「전역 CLAUDE.md」 참조는 `agents/*.md` 와 동일하게 치환한다(은퇴 대상을
   가리키는 서술은 이관 후 거짓이 된다) — §5.7 이 `agents/` 3파일에 적용하는 최소 치환을
   이관 본문 자신에도 그대로 적용한다.

위임 승인 문단(:20-44)의 "`~/.claude/CLAUDE.md`·`settings.json`… 전수 확인" 문구는
역사 서술이므로 그대로 둔다(그때 그 파일들을 확인했다는 기록이다).

### 5.2 새 루트 `CLAUDE.md` (~70줄) — 자기 체크리스트 5항목을 실제로 채운다

```
# coding-harness — 프로젝트 지침

1. 개요와 목적
   - Claude Code 배포 자산(rules/agents/commands) + 세션 허브(hub/)를 관리·배포하는 저장소
   - 하지 말 것: (a) 이 저장소 안에서 `install.sh --scope project` 실행 금지
     (자기 설치 = .claude/rules 이중 로드 재발 — T28-4 가 커밋을 차단),
     (b) 세션이 실제 $HOME 을 대상으로 설치 실행 금지 — 검증은 bash -n · tests/run.sh
     (샌드박스 HOME 치환)로 한다. --scope user 실설치는 사용자가 명시 요청할 때만.
   - 범용 워크플로우 규칙의 본체는 rules/workflow/*.md 다 — 이 저장소를 clone 만 한
     기여자에게는 자동 적용되지 않으므로(레포 rules/ 트리는 구조적 미발견),
     install.sh --scope user 로 설치해 적용한다.
2. 아키텍처 (레이어와 책임)
   - 배포 채널: install.sh — 순수 bash, 외부 의존 0. 소유권 원칙(레포가 배포한 파일만 관리)
   - 배포 자산: rules/ 46 · agents/ 4 · commands/ 10 — 3종. 레이어 간 통신은 manifest
     (.coding-harness.json v3)의 해시 대장뿐
   - 허브 런타임: hub/ — python3 표준 라이브러리 전용 (문서화된 결정)
   - 검증: tests/run.sh (T 그룹) · tests/hub (unittest)
3. 성능 (병목)
   - 이 저장소의 병목은 실행 성능이 아니라 **세션 컨텍스트 예산**이다 — 상시 로드
     바이트를 T26 래칫이 강제한다. 상시 컨텍스트를 늘리는 변경은 근거를 커밋에 남긴다
4. 빌드/검증 명령 (정본)
   - bash tests/run.sh
   - python3 -m unittest discover -s tests/hub -t .
   - python3 -m py_compile hub/bin/*.py
   - bash -n install.sh && bash -n hub/install.sh
5. 컨벤션
   - 커밋: `type: 한국어 서술형` (git log 관행)
   - 함수 50줄 제한의 프로젝트 예외: tests/run.sh 의 T 그룹 함수 — 시나리오 나열이
     본질이라 분할이 오히려 가독성을 해친다 (user rules 의 50줄 규칙에 대한 정당한
     프로젝트 우선 적용)
   - 레포에서 관리 파일을 지우거나 개명하는 커밋은 removals.txt 에 옛 경로를 추가한다
   - 설계 문서(PRP)는 docs/prps/{기능명}.md
```

이관 전에는 쓸 수 없던 "함수 50줄 예외"를 **정당하게** 쓸 수 있게 된다 — 규격상
프로젝트 지침이 user rules 를 이기기 때문이다(브리프 「세 피해 전부 해소」의 피해 2).

### 5.3 `install.sh` 변경 — 제거 목록과 잔여 구조

제거 (현재 줄 실측):

| 줄 | 대상 |
|---|---|
| :3 | 헤더 주석 "CLAUDE.md + rules/ + agents/ 를 …" → "rules/ + agents/ + commands/ 를 …" |
| :26 | `target_claude_md` → `retired_claude_md_path` 로 개명, user scope 에서만 설정 |
| :47 | usage 의 `--force` 설명에서 CLAUDE.md 백업 서술 제거 |
| :93 | project 분기의 `target_claude_md="$PWD/CLAUDE.md"` **삭제** — project scope 는 CLAUDE.md 를 아예 모른다 |
| :156-173 | `claude_md_is_identical` · `check_claude_md_conflict` 삭제 |
| :330 | `check_preconditions` 의 `check_claude_md_conflict` 호출 삭제 |
| :495-527 | `backup_existing_claude_md` · `install_claude_md` 삭제 |
| :538 | `build_files_ledger_json` 의 `echo "CLAUDE.md"` 삭제 |
| :572 | manifest `files_count` 의 `"CLAUDE_md": 1,` 삭제 |
| :647-652 | dry-run 계획의 CLAUDE.md 분기 → 은퇴 계획 출력으로 교체 |
| :683 | `install_claude_md` 호출 → `retire_user_claude_md` (아래 §5.4) |
| :687 | `log_done` 카운트의 `+ 1` 삭제 |

변경: `:12 RULES_FILE_COUNT=42→46` · `:17 MANIFEST_VERSION=2→3`.
순증감: −약 75줄 +약 55줄 ≈ **−20줄**.

### 5.4 은퇴 절차 — 사용자 파일 삭제의 방어 설계 (민감 영역, 명시 규칙)

**결정 2: 툼스톤 네임스페이스를 확장하지 않고 별도 은퇴 함수를 둔다.** 실측 근거 3가지:

1. **경로 모델 불일치** — `process_removals` 의 대상 경로는
   `$target_base_dir/.claude/$line`(:352)이다. 옛 project scope 배포본은 `$PWD/CLAUDE.md`
   로 `.claude/` 밖이라 이 모델로 표현할 수 없다.
2. **영구 D-5 위반** — `validate_removals_file`(:318-321)은 레포에 실존하는 파일의
   툼스톤을 레포 버그로 보고 fail-closed(exit 1)한다. 루트 `CLAUDE.md` 는 이 설계 후에도
   프로젝트 지침으로 **레포에 영원히 존재**하므로, `CLAUDE.md` 툼스톤은 네임스페이스를
   넓혀도 영구히 설치를 죽인다. 확장하려면 D-5 계약 자체를 헐어야 한다 — 하지 않는다.
3. **T27-6(:5539) 이 `CLAUDE.md` 를 네임스페이스 위반의 고정 예제로 사용한다** — 확장하면
   이 테스트의 의미가 뒤집힌다.

두 메커니즘의 관계: **툼스톤** = 3 네임스페이스 관리 자산의 잔재 청소(영구 메커니즘, 레포
커밋과 동행) / **은퇴** = CLAUDE.md 배포 채널 폐지의 1회성 마이그레이션(user scope 전용,
manifest v3 도달 후 영구 침묵). 둘 다 `save_manifest_file` **이전**에 "갱신 전 대장"을
읽는 같은 순서 계약(:672-677 주석)을 공유한다 — 그 주석에 은퇴를 추가한다.

#### 인터페이스 (bash, 각 함수 50줄 이내)

```bash
# 은퇴 판정 상수 — 매직 문자열 금지
readonly RETIRED_BACKUP_SUFFIX_FORMAT="retired-%Y%m%d-%H%M%S"
readonly LEGACY_CLAUDE_MD_TITLE_SENTINEL='# 전역 개발 지침 (~/.claude/CLAUDE.md)'
readonly LEGACY_CLAUDE_MD_BODY_SENTINEL='서브에이전트 위임은 사용자가 상시 요청한 것이다'

# ~/.claude/CLAUDE.md 의 은퇴 판정 1건을 출력한다: retire|protect_modified|protect_unknown|skip
classify_user_claude_md_retirement() { local previous_manifest_path="$1"; ...; }

# 판정에 따라 mv 개명 실행. dry-run 지원. 보호는 0, mv 실패만 1(설치 중단).
retire_user_claude_md() { local previous_manifest_path="$1"; ...; }
```

#### 판정 규칙 (위에서 아래로, 첫 일치가 승리)

| 순서 | 조건 | 판정 | 동작 |
|---|---|---|---|
| 1 | `--scope project` | (호출 없음) | project scope 는 이 함수에 도달하지 않는다 |
| 2 | `$HOME/.claude/CLAUDE.md` 없음 | skip | 조용히 통과 (멱등) |
| 3 | 대상이 심볼릭 링크(`-L`) | protect_unknown | `log_protected` + 수동 안내 — mv 는 링크만 옮겨 원본 위치가 남으므로 의도 판정 불가 |
| 4 | 이전 manifest `version` ≥ 3 | skip | **로그 없음** — 이미 이관 완료. 그 자리의 CLAUDE.md 는 사용자가 새로 만든 소유물이다 (경로 F) |
| 5 | 대장에 `"CLAUDE.md"` 해시 있음 · 대상 해시 일치 | retire | 우리가 설치한 그대로 — 삭제 가능 증명 완료 (경로 B) |
| 6 | 대장 해시 있음 · 불일치 | protect_modified | 사용자 수정 — **`--force` 로도 삭제하지 않는다** (D-4 와 동일 원칙, 경로 C) |
| 7 | 대장 해시 없음(v1/manifest 부재) · 제목 센티널(1행 정확 일치) **AND** 본문 센티널 포함 | retire | 레거시 설치본의 자동 이관 (경로 E) |
| 8 | 그 외 전부 | protect_unknown | "지울 수 있음을 증명 못 하면 지우지 않는다" — 소유권 원칙의 삭제판 (tier0 결정 2 인용) |

#### 실행·실패 시 동작

- **retire**: `mv "$path" "$path.$(date +$RETIRED_BACKUP_SUFFIX_FORMAT)"` — **개명이 곧
  백업이자 삭제**다. 복사 후 삭제 방식의 "백업 성공·삭제 실패" 창이 구조적으로 없다.
  mv 실패 → `log_error` + return 1 → `perform_installation` 중단 (manifest 미갱신 —
  다음 실행이 같은 판정을 재시도한다).
- **retire, 동일-초 충돌**: mv 직전 백업 후보 경로가 이미 존재하면(같은 초 안의 재실행
  등) mv 를 시도하지 않고 곧바로 `log_error` + return 1 — **fail-closed**. `mv -n`(대상
  있으면 조용히 스킵)은 쓰지 않는다: 그건 "성공 로그 + 파일 잔존 + 규칙 4 로 다음 실행부터
  영구 침묵"이라는 더 나쁜 무성 실패이기 때문이다. manifest 미갱신(다음 실행이 재시도한다).
- **protect_***: `log_protected "$path — …. 확인 후 수동 이관: mv <경로> <경로>.retired-manual"`
  + return 0 — **보호는 실패가 아니다** (툼스톤 D-3/D-4 와 동일 계약, T27-4/5 가 잠근 문면
  관행을 따른다).
- **dry-run**: `log_plan "mv $path $path.retired-<ts> (CLAUDE.md 배포 채널 은퇴)"` 만 출력.
- 백업 이름을 `.bak-` 이 아니라 **`.retired-`** 로 구별한다: `.bak-` 은 "덮어쓰기 직전
  백업"의 의미로 T6/T7·README·harness-update 의 역사와 결합돼 있다. 은퇴 백업은 덮어쓸
  본체가 없다 — 의미가 다르면 이름도 다르게.

#### 접근 범위 (읽는 경로 3 + 쓰는 경로 2)

쓰는 경로는 `$HOME/.claude/CLAUDE.md` 와 mv 직전 충돌 검사가 그 순간 계산하는 백업 후보
경로(같은 파일 + 지금 타임스탬프) **둘뿐이다.** 읽는 경로는 그 둘에 인자로 받은 이전
manifest(`.coding-harness.json`)가 더해져 **셋** — 판정 규칙 4(version)·5·6(대장 해시)의
입력이다. `CLAUDE.local.md` · `~/.claude/rules/**` · 프로젝트 `./CLAUDE.md` · 기존
`.bak-*` 는 읽지도 쓰지도 않는다. 기존 `.retired-*` 파일 대부분도 마찬가지이나, 위 백업
후보 경로와 이름이 우연히 겹치는 경우(동일-초 재실행)에는 그 존재 여부만 확인한다(`-e`)
— 겹치면 fail-closed 로 중단하고 덮어쓰지 않는다(위 「실행·실패 시 동작」 참고). 은퇴
로직은 `$REPO_ROOT/CLAUDE.md` 를 참조하지 않는다(레포 원본과의
비교가 아니라 대장·센티널 판정이므로) — 이것이 T28-3(리터럴 0건)이 성립하는 이유다.

### 5.5 manifest v3 (데이터 모델)

```json
{
  "version": 3,                     // 2→3: 대장에서 CLAUDE.md 항목 소멸 + files_count 축소
  "repo_path": "...", "scope": "...", "installed_at": "...",
  "installed_from_commit": "...", "target_base_dir": "...",
  "files_count": { "rules": 46, "agents": 4, "commands": 10 },   // CLAUDE_md 키 삭제
  "files": { "<상대경로>": "<sha256>", ... }                      // 56항목 (46+4+10 — CLAUDE.md 없음)
}
```

승급 기준은 tier0 결정 3 의 재적용이다: 소비자의 해석 의무가 바뀌는 변경(은퇴 판정 4번
규칙이 version ≥ 3 을 "이관 완료" 신호로 읽는다)은 version 을 올린다. 동반 수정:
`commands/harness-update.md:24` 의 `version ∈ {1, 2}` → `{1, 2, 3}`.

### 5.6 `README.md` 재작성 지점 (실측 줄)

| 줄 | 현행 | 변경 |
|---|---|---|
| :37-41 | 트러블슈팅 "exit 1 이고 CLAUDE.md 충돌인 경우" | CLAUDE.md 충돌은 소멸 — 절 삭제, 은퇴 보호 안내로 교체(수동 이관 1줄 + **경로 D 안내**: 과거 `--scope project` 로 병합한 프로젝트는 `./CLAUDE.md` 에서 범용 지침 부분을 손으로 걷어낼 것) |
| :95 | `--force`: "CLAUDE.md 백업 후 덮어쓰기…" | rules/agents/commands 전용 서술로 축소. **"자동으로 `--force` 를 붙이지 않는다" 문구는 유지** (T23-3 이 잠근다 — 수정된 rules 에 여전히 유효한 원칙) |
| :105 | 설치 대상 표의 CLAUDE.md 행 | 행 삭제. rules 행 42→46, "12개 항상"→"16개 항상". 합계 57→56 |
| :112 | "CLAUDE.md 1개 + rules 12개 = 13개(실측 50,314B)" | "rules 16개(실측 <재실측>B)" — T26-2 가 잠근다 |
| :117-129 | "### CLAUDE.md 구성" 절 | "### rules/workflow 구성" 으로 개편 — 배포 지침의 본체가 어디로 갔는지 + 은퇴 정책 요약 |
| :236 | "항상 로드되는 rules: 12개 (CLAUDE.md 포함 시 13개, 실측 50,314B…)" | "16개 (실측 <재실측>B…)" — T26-3 이 잠근다 |
| :267-277 | "### CLAUDE.md (프로젝트 고유 지침)" 안전장치 절 | "### ~/.claude/CLAUDE.md 은퇴" 절로 교체 — §5.4 판정표의 사용자용 요약 |
| :302- | 파일 구조 트리 | CLAUDE.md 주석을 "프로젝트 지침(배포 대상 아님)"으로, `workflow/` 4개 추가 |

부수 해소(브리프 확인): README(자동 `--force` 금지) vs `harness-update.md`(자동 `--force`)의
온도차 충돌은 CLAUDE.md 특수 케이스가 사라지면서 소멸한다.

### 5.7 `agents/` 3파일 최소 정정

은퇴 후 "전역 CLAUDE.md 자동 로드" 서술이 거짓이 된다 — 이 설계가 만든 낡음이므로 이
설계가 치운다(내 변경이 만든 고아 정리). 각 파일 1~2문구만:

- `agents/design-architect.md:13,17` · `agents/implementer.md:22` · `agents/code-reviewer.md:13`:
  "전역·프로젝트 CLAUDE.md 와 `rules/`" → "사용자 rules(workflow 포함)·프로젝트 CLAUDE.md 와
  `rules/`" 취지로 치환. 그 외 문장(예: implementer :74 "전역·프로젝트 CLAUDE.md의 코드 품질
  가이드라인" → "user rules·프로젝트 CLAUDE.md의")도 같은 최소 치환. 내용 개선 금지.

`commands/dashboard.md` 의 "## CLAUDE.md 트리거" 절 이름은 **건드리지 않는다** —
T22(:2181·:2469)가 절 이름을 sed 앵커로 쓰고, Q5 가 그 파일을 편집 중이다 (§10).

## 6. 마이그레이션 6경로 (A~F)

| 경로 | 대상 상태 | 판정(§5.4 규칙) | 결과 |
|---|---|---|---|
| A | 신규 머신 — `~/.claude/CLAUDE.md` 없음 | 2 → skip | rules/workflow 설치만. 흔적 없음 |
| B | v2 설치본, 대장 해시 일치 | 5 → retire | `CLAUDE.md.retired-<ts>` 로 개명. 재실행 시 A 와 동일(멱등) |
| C | v2 설치본, 대장 불일치(설치 후 사용자 수정) | 6 → protect_modified | 파일 잔존 + 수동 안내. 이중 로드는 사용자가 정리할 때까지 잔존(의도된 보수성) |
| D | 과거 `--scope project` + 손 병합한 `<proj>/CLAUDE.md` | (접근 없음) | 자동 해결 불가 — 팀 소유 커밋 파일. README 트러블슈팅이 수동 절차 안내 (§9 약점 6 수용) |
| E | v1 설치본/manifest 부재 + 센티널 2종 일치 | 7 → retire | 레거시 자동 이관. 센티널 하나라도 불일치 → 8 → protect_unknown |
| F | manifest v3 이후 재실행 (사용자가 자기 CLAUDE.md 를 새로 만든 경우 포함) | 4 → skip | **로그 없음** — 매 설치마다 보호 경고가 반복되면 소음이고, 그 파일은 사용자 소유물이다 |

**보충(검수 2회차)**: 경로 C 를 포함해 `protect_*` 로 끝나는 모든 경로의 안내는 **그
실행에서 최초 1회만** 뜬다 — 이 실행이 끝나면 manifest 가 v3 로 갱신되므로, 재실행부터는
경로 F(규칙 4 skip)가 먼저 이겨 조용해진다. 동작은 의도된 그대로이며(반복 통지는 별도
설계 변경 대상 — 아래 리스크에서 다루지 않음), README.md 「은퇴」 절에 이 사실과 수동
정리 절차(`mv ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.retired-manual`)를 명시했다.

## 7. 기존 테스트 파손 분석 — 12건 전수 (tests/run.sh 실측 줄)

| # | 위치 | 현행 기대 | 재조준 |
|---|---|---|---|
| 1 | :261 (T1) | rules 42개 | 46 |
| 2 | :283-286 (T1) | `./CLAUDE.md` **존재** | `./CLAUDE.md` **부재** 단언으로 반전 — `--scope project` 비파괴의 증명 |
| 3 | :395 (T4) | rules 42개 | 46 |
| 4 | :404-452 (T5) | 선재 CLAUDE.md → exit 1·전자산 미설치 | **exit 0·기존 파일 불변·`.bak` 0개·rules 46 설치** — 기대 결과의 반전 (§7.1) |
| 5 | :454-497 (T6) | `--force` → `.bak-*` 1개 | 은퇴 B 경로 테스트로 재조준 (§7.1) |
| 6 | :499-535 (T7) | `--force` 2회 → `.bak-*` 2개 | 은퇴 보호 3분기 테스트로 재조준 (§7.1) |
| 7 | :1011 (T20) | `"version": 2` | `"version": 3` |
| 8 | :2503-2508 (T22-158) | `$REPO_ROOT/CLAUDE.md` 에 '디스패치·결과 수령 시점마다' | `$REPO_ROOT/rules/workflow/role-separation.md` 로 경로 재조준 (문구 동일) |
| 9 | :2569-2576 (T23-7) | 3문서 중 `$REPO_ROOT/CLAUDE.md` 에 `dashboard_enabled` | 루프 목록에서 CLAUDE.md → `rules/workflow/role-separation.md` 교체 |
| 10 | :17 상수 · :5361 공식 · README:112·:236 (T26) | 3파일군 합 50,314B | 공식에 `rules/workflow/*.md` 추가 · 상수는 **구현 완료 시점 실측치로 고정**(선례: :11-16 주석 관행) · README 2곳 동기 |
| 11 | :5427 (T27-1) | 대장 항목 = 상수합 **+1** | `+1` 제거 (CLAUDE.md 대장 항목 소멸) |
| 12 | :5500 (T27-4) · :5534 (T27-5) | `"version": 2` | `"version": 3` |

**비파손 확인** (재실측): T2(:292 — CLAUDE.md 무단언) · T3(:344 — `./.claude` 만 스캔,
루트 CLAUDE.md 는 범위 밖) · T8 · T12(frontmatter **보존** 검사라 부재 검사와 무충돌) ·
T15/T16(rules 전용) · T17 · T21(:1062 — `files_count` 필드 존재만) · T23-3(README 문구
유지 조건부 — §5.6) · **T27-6(:5539 — 네임스페이스를 확장하지 않으므로 `CLAUDE.md` 는
여전히 위반 예제로 유효)** · T27-8(dry-run 의 `"version": 1` 은 v1 시임이라 그대로).

### 7.1 T5·T6·T7 재조준 상세 — 경로가 아니라 기대 결과가 바뀐다

- **T5 → "선재 `./CLAUDE.md` 무간섭"**: sandbox 에 `./CLAUDE.md` 사전 생성 →
  `--scope project` (force 없음) → 단언: exit **0** (현행 1 의 반전) · 내용 불변(기존 단언
  재사용) · `.bak-*` 0개 · `./.claude/rules` 46개 생성(현행 "미생성" 단언의 반전).
- **T6 → "은퇴 경로 B (대장 일치 → mv)"**: HOME 치환(선례 :304·:940·:977·:2672) sandbox 에
  옛 CLAUDE.md 사본 배치 + manifest 에 `"CLAUDE.md": <실해시>` 줄 주입(T27-2 :5444-5450 의
  주입 기법 그대로 — grep 기반 조회라 줄 추가로 충분, 한계 각주 포함 관행 유지) →
  `--scope user` → 단언: exit 0 · `CLAUDE.md` 부재 · `CLAUDE.md.retired-*` 정확히 1개 ·
  백업 내용 == 원본 · **재실행 시 `.retired-*` 증가 없음**(경로 F 멱등).
- **T7 → "은퇴 보호 3분기"**: (a) 경로 C — 대장 주입 후 파일 변조 → 파일 잔존 ·
  `log_protected` 문구 · exit 0 · `--force` 를 줘도 동일(D-4 원칙), (b) 경로 E 양성 —
  manifest 없음 + 센티널 2종 포함 파일 → retire, (c) 경로 E 음성 — manifest 없음 +
  무관 내용("my own notes") → 잔존 + protect_unknown 문구, (d) dry-run — `.retired` 미생성 ·
  `log_plan` 문구 존재.

함수 이름(`test_claude_md_conflict` 등)은 새 의미에 맞게 개명하되 **호출 순서 슬롯은
유지**한다 — `register_and_run_tests`(:5619-) 의 목록 위치가 곧 T 번호 관행이다.

## 8. 신규 검사 — T28 (rules/workflow 고정 래칫)

브리프의 후보 5건을 현재 baseline 으로 재검토했다:

| 후보 | 판정 | 근거 |
|---|---|---|
| 1. `RULES_FILE_COUNT` 파리티 | **기각 (중복)** | T27-1(:5422-5432)이 이미 "대장 항목 수(레포 find 실측) == 선언 상수 합"을 강제한다 — `+1` 제거 후 그 자체가 파리티 검사다. T26·T27 과 중복 금지 지시 이행 |
| 2. `rules/workflow/` 4파일 존재 | **채택 T28-1** | 파일명 4개를 경로 리터럴로 고정 — 개명·누락이 곧 실패 |
| 3. workflow `paths:` 0건 | **채택 T28-2** | launch 로드가 설계의 성립 조건. T12 는 frontmatter **보존**을 검사하지 **부재**를 검사하지 않는다 — 중복 아님 |
| 4. `install.sh` 에 `$REPO_ROOT/CLAUDE.md` 리터럴 0건 | **채택 T28-3** | CLAUDE.md 배포 부활의 문면 차단. §5.4 보호 경로 절이 "은퇴 로직은 레포 원본을 안 읽는다"를 보장하므로 0건이 성립 |
| 5. `git ls-files .claude/rules` 공백 | **채택 T28-4** | 자기 설치 커밋 방지(이중 로드 재발 차단). 현재 실측 공백(exit 0·출력 없음) |
| (추가) 루트 CLAUDE.md 에 '전역 개발 지침' 0건 | **채택 T28-5** | 루트가 다시 전역 지침으로 회귀하는 것을 문면으로 차단 — T22-158 의 역방향 grep, 같은 패턴 |

그룹 신설 근거는 tier0 결정 6 의 재적용: T22(대시보드)·T27(manifest)에 얹으면 실패
메시지의 소속이 거짓말을 한다. `total_tests` 26→27 (:5695 — 총합 계약 주석 :84 도 동반 갱신), 러너 목록(:5619-)에 1행 추가.
T28-1·2 는 1단계에, T28-3·5 는 해당 단계(§11)에 나눠 도입한다.

## 9. 안 3 의 자기 신고 약점 9건 — 항목별 판정

| # | 약점 | 판정 | 처리 |
|---|---|---|---|
| 1 | 전역 컨텍스트 비용이 1바이트도 안 준다 (4파일 분할로 주입 헤더 3개 증가) | **(c) 수용** | 이 설계의 목표는 이중 로드 제거·루트 해방·`--scope project` 비파괴화이지 바이트 절감이 아니다. 바이트 절감은 별도 과제(결함 9 계보 — 기각 이력 있음). 헤더 증가분은 T26 재실측에 포함돼 수치로 드러난다 |
| 2 | 같은 우선순위 충돌이 기계적으로 해결되지 않는다 (팀의 `./CLAUDE.md` vs `./.claude/rules/workflow/*` — 규격: "may pick one arbitrarily") | **(b) 완화 + 잔여 명시** | `role-separation.md` 서문에 프로젝트 우선 문장 명시(§5.1). **잔여 위험**: 조정 장치가 산문 1문장뿐인 것은 사실이다. 단 현행 CLAUDE.md :6 의 "충돌하면 프로젝트 우선"도 같은 산문 장치였다 — 악화가 아니라 현상 유지다 |
| 3 | 모순의 동거 가시화 (`common/agents.md` 옛 로스터·`development-workflow.md` 5단계와 같은 디렉토리·우선순위) | **(b) 완화** | 서문 우선 선언 1줄(§5.1). 두 파일의 근본 정리는 R1(rules/common 6파일)의 몫 — §10 순서표로 위임. 이 설계에서 그 파일들을 고치면 R1 과 정면 충돌한다 |
| 4 | 중복을 옮기기만 한다 (「코드 품질 가이드라인」 ≈ `coding-style.md`) | **(c) 수용** | 이관은 의도적 "이동만"(결정 9) — diff 검토 가능성과 위임 승인 문단의 원문 보존이 우선한다. 중복 제거는 이관 안착 후 별도 축약 과제로 명시 (승인 A-5) |
| 5 | 테스트 재작성이 가장 큰 위험 | **(a) 해소** | §7 의 12건 전수(실측 줄) + §7.1 재조준 설계 + HOME 치환 선례 4곳 실측. 브리프의 자기 과대평가("HOME 오버라이드 없음")는 사실과 다름을 재확인 |
| 6 | 경로 D(과거 project 설치 + 손 병합) 자동 해결 불가 | **(c) 수용** | 팀 소유 커밋 파일 — 소유권 원칙상 접근 자체가 금지다. README 트러블슈팅에 수동 절차 안내(§5.6 :37-41). 그쪽 이중 로드는 사람이 정리할 때까지 잔존 |
| 7 | 은퇴 판정의 센티널 의존 (문구 개정 시 조용한 실패) | **(b) 완화 — 사실상 해소** | 1차 판정을 **manifest 대장 해시**로 교체(§5.4 규칙 5·6) — 브리프 시점엔 없던 수단이다(v2 대장이 `4be8f58` 신설). 센티널은 레거시(v1/manifest 부재) 전용 2중 확인으로 강등. 센티널 개정의 최악 결과 = 레거시 설치본이 자동 은퇴 대신 수동 안내를 받는 것 — **조용한 오삭제는 구조적으로 불가능** (fail-closed) |
| 8 | 갓 clone 한 기여자는 워크플로우를 못 본다 | **(b) 완화 + 잔여 명시** | 새 루트 CLAUDE.md 개요가 규칙의 위치와 적용 방법(`--scope user`)을 안내(§5.2). **잔여**: 미설치 기여자에게 자동 적용 불가 — 레포 `rules/` 트리 미발견은 규격이다(§2.1). 구조적 한계로 수용 |
| 9 | 롤백 orphan (`~/.claude/rules/workflow/` 잔존 → 이중 로드 재발) | **(a) 해소 (대부분)** | 되돌리는 커밋이 `removals.txt` 에 workflow 4경로를 추가하면 기존 툼스톤 계약 그대로 배포본이 청소된다 — `rules/` 네임스페이스 안이라 확장 불요, 롤백 커밋이 레포에서 4파일을 지우므로 D-5 도 통과. `~/.claude/CLAUDE.md` 는 배포 로직 복원으로 재생성. **잔여**: `.retired-*` 백업 파일은 남는다 — 이름이 `CLAUDE.md` 가 아니라 로드되지 않는 불활성 파일이므로 수용 |

## 10. `feature/audit-remediation` 과의 순서 — 파일별 확정

브리프의 "audit-remediation 먼저" 권고를 현재 상태(Q1·Q2 커밋, Q3 진행, Q4·Q5·R1~R3
대기)로 재검토한 결과 — **부분 유지로 정정**한다: 경성 선행은 Q5 까지로 좁히고, R1~R3
전체를 기다리지 않는다(문서 정리 3건을 기다리면 착수가 무기한 밀린다).

| 겹치는 파일 | audit-remediation | 이 설계 | 순서 | 근거 |
|---|---|---|---|---|
| `CLAUDE.md` | **Q5** — 대시보드 트리거 문단 제자리 편집 | 그 문단을 `role-separation.md` 로 이관 | **Q5 먼저 (경성)** | 분할은 git 에게 delete+add 라 자동 병합이 안 된다 — 뒤에 오는 쪽이 수동 재적용을 진다. Q5 가 먼저면 이관은 "편집 완료된 최종 문면을 복사"라는 기계 작업이고, 반대면 Q5 의 diff 를 새 파일로 손수 재조준해야 한다. 문면 잠금(T22-158·T23-7)도 같은 방향 — Q5 가 CLAUDE.md 기준으로 잠근 것을 이 설계가 한 번에 재조준하는 쪽이 왕복이 적다. 브리프 논거는 현재도 성립 |
| `commands/dashboard.md` | Q5 | 무접촉 (§5.7 — 절 이름 유지) | Q5 먼저 | 같은 커밋 단위로 움직인다 |
| `rules/common/performance.md` 등 | Q4·R1 | 무접촉 — 단 상시 바이트가 변해 T26 에 간접 영향 | **연성 (병행 가능)** | 나중에 병합되는 쪽이 T26 상수·README 2곳을 재실측한다 — 기계적 1커밋. Q4 는 Q5 앞이므로 실질적으론 선행됨 |
| `README.md` | R2 | 설치 계약 절 개정(§5.6) | 연성 | 절이 다르면 git 이 병합. 충돌 시 후행자 재조준 |
| `hub/install.sh`·`hub/README.md`·`docs/prps/coding-harness.md` | R2 | **무접촉** (coding-harness.md 는 역사 문서 보존) | 무관 | |
| `rules/common/*` 나머지 | R1 | 무접촉 — 약점 3 의 근본 정리(agents.md 로스터·development-workflow.md)를 **R1 에 위임** | 연성 | R1 이 그 파일들의 소유자다. 이 설계는 서문 우선 선언만(§5.1) |
| `LICENSE`·`NOTICE.md` | R3 | 무접촉 | 무관 | |

착수 조건 판정 명령: `git log --oneline main` 에 Q5 커밋이 보일 것.
같은 저장소 동시 세션 주의(메모리 기록)가 이 결정의 배경이기도 하다 — 미커밋 변경이
섞이지 않도록 이 작업은 전용 워크트리(`claude-md-split`)에서만 진행한다.

## 11. 단계 분할 — 각 단계는 독립 커밋·검증 가능

검증 정본(모든 단계 공통): `bash tests/run.sh` ·
`python3 -m unittest discover -s tests/hub -t .` · `python3 -m py_compile hub/bin/*.py` ·
`bash -n install.sh` · `bash -n hub/install.sh`. 아래 "검증"은 단계별 핵심 통과 기준만 적는다.

### 0단계 — 선행 조건 확인 (커밋 없음)
- Q5 머지 확인(§10). rebase 후 이관 원문(CLAUDE.md)의 최신 문면 재확인.

### 1단계 — `rules/workflow/` 신설 (선행: 0)
- 수정: `rules/workflow/*.md` 4개 신설(그 시점 CLAUDE.md 문면 복사 + §5.1 서문) ·
  `install.sh:12` 46 · `tests/run.sh:261`·`:395` 46 · T28 그룹 신설(T28-1·T28-2,
  `total_tests` 27) · `rules/README.md`(구조도 + 42→46 + Always loaded 12→16)
- 검증: 전 스위트 green. T26 은 불변(공식이 workflow 를 아직 안 세고 CLAUDE.md 도 불변).
- 주의: 이 시점 신규 설치는 워크플로우 내용이 CLAUDE.md 와 rules 양쪽에 실리는 과도
  상태다 — 브랜치 내부에서만 존재하고 main 머지는 전체 단위이므로 수용(bisect 각주만).

### 2단계 — 배포 계약 변경 + 은퇴 (선행: 1)
- 수정: `install.sh`(§5.3 제거 전부 · `MANIFEST_VERSION=3` · §5.4 은퇴 함수 2개+상수 3개) ·
  `commands/harness-update.md:24`·`:184` · `tests/run.sh`(T1 존재→부재 :283-286 · T5·T6·T7
  재조준 §7.1 · T20 :1011 · T27-1 :5427 · T27-4/5 :5500·:5534 · T28-3 추가)
- 검증: 전 스위트 green — 특히 T5 의 exit 0 반전, T6 의 `.retired-*` 1개, T7 의 보호
  3분기, T27 전 판정(D-1~D-5) 무회귀, T27-6 이 여전히 `CLAUDE.md` 를 위반으로 거부.
- 이 단계 이후 루트 CLAUDE.md 는 **배포되지 않는 파일**이 된다(내용은 아직 옛 전역 지침).

### 3단계 — 루트 CLAUDE.md 교체 (선행: 2)
- 수정: `CLAUDE.md`(§5.2 골자로 교체, ~70줄) · `tests/run.sh`(T22-158 :2506 경로 재조준 ·
  T23-7 :2572 목록 교체 · T26 공식 :5361 에 `"$REPO_ROOT/rules/workflow/"*.md` 추가 ·
  상수 :17 재실측 고정 + :11-16 주석 갱신 · T28-5 추가) · `README.md:112`·`:236` 수치 동기
- 검증: 전 스위트 green — T26 의 상수·README 2선언·실측 3중 일치.
  예상 실측: 50,314 − 16,661(구 CLAUDE.md) + ~17,100(workflow 4파일) + ~3,500(새 루트)
  ≈ **54,000B 안팎** — 정확한 값은 구현 완료 시점 실측으로 고정(래칫 관행 :11-16).
- 2단계가 먼저인 이유: 순서를 뒤집으면 "프로젝트 지침 ~70줄이 `~/.claude/CLAUDE.md` 로
  배포되는" 중간 상태가 생긴다 — 잘못된 내용의 배포는 과도 상태로도 허용하지 않는다.

### 4단계 — 문서·에이전트 정리 (선행: 3)
- 수정: `README.md` 나머지(§5.6 :37-41·:95·:105·:117-129·:267-277·:302-) ·
  `agents/` 3파일 최소 치환(§5.7)
- 검증: 전 스위트 green — T23-3(자동 `--force` 금지 문구 잔존)·T23-7·T26 재확인.

## 12. 설계 결정과 근거

1. **배포 채널 이관(안 3) 채택** — 브리프 심판 만장일치 + §2.1 규격 사실. 탈락안의 사유
   (안 1: `claudeMdExcludes` 의 문서화된 용도가 반대 방향 / 안 2: 컴팩션 지속성 규격이
   `paths:` 카브아웃과 상충)도 브리프에서 재확인.
2. **툼스톤 네임스페이스 불확장 — 별도 은퇴 함수** — §5.4 의 실측 근거 3가지(경로 모델
   불일치 · 루트 CLAUDE.md 영속으로 인한 영구 D-5 위반 · T27-6 의 위반 예제 사용).
   T27 의 기존 계약을 1비트도 바꾸지 않는다.
3. **은퇴 판정 = 대장 해시 1차, 센티널 2차(레거시 전용), 나머지 fail-closed** — "지울 수
   있음을 증명 못 하면 지우지 않는다"(tier0 결정 2)의 재적용. 약점 7 의 처리이기도 하다.
4. **`mv` 원자 개명 = 백업이자 삭제** — 복사 후 삭제의 실패 창 제거. 접미사 `.retired-` 는
   `.bak-`(덮어쓰기 전 백업)과 의미가 달라 이름을 구별한다.
5. **`MANIFEST_VERSION` 2→3 — 브리프 번복** — `46ecb5b` 에서 이미 2(§2.3). 승급 기준은
   tier0 결정 3 의 재적용(소비자 해석 의무 변경 — version ≥ 3 이 은퇴 판정의 입력이 된다).
   `harness-update.md:24` 의 수용 집합 동반 확장.
6. **후보 검사 1(파리티) 기각** — T27-1 과 중복(§8). "T26·T27 과 중복되지 않게" 지시 이행.
7. **T5·T6·T7 슬롯 재사용 + T28 신설** — 러너 계약(`register_and_run_tests` 순서 ·
   `total_tests`) 변화 최소화. 그룹 신설 판단은 tier0 결정 6(이름이 곧 검사 대상) 재적용.
8. **이관은 "이동만"** — 중복 제거·문장 개선 배제. diff 검토 가능성과 위임 승인 문단의
   원문 보존(그 문단은 존재 이유 자체가 "기록"이다)이 우선. 약점 4 의 수용과 짝이다.
9. **Q5 경성 선행, R1~R3 연성** — §10. 브리프의 "audit-remediation 먼저"를 파일 단위로
   정밀화한 **부분 번복**(전체 대기 → Q5 까지만 대기)이며 사유를 §10 에 적었다.
10. **패턴 재사용, 새 메커니즘 0** — 은퇴 로그는 `log_protected`/`log_plan` 기존 채널,
    테스트는 HOME 치환·대장 주입·`note_failure`/`finish_group` 기존 패턴의 복제.
    tier0 결정 4(YAGNI)의 재적용.

## 13. 테스트 계획 (요약표)

| 검증기 | 대상 | 케이스 |
|---|---|---|
| T1/T4 갱신 | 46개 배포·복원 + 루트 CLAUDE.md 미배포 | rules 46 · `./CLAUDE.md` 부재 |
| T5 재조준 | `--scope project` 비파괴 | 선재 CLAUDE.md → exit 0·불변·46 설치 |
| T6 재조준 | 은퇴 경로 B | 대장 일치 → `.retired-*` 1개·내용 보존·멱등(F) |
| T7 재조준 | 은퇴 보호 | C(수정본, `--force` 무시)·E 양성/음성(센티널)·dry-run 무부작용 |
| T20/T27 갱신 | manifest v3 | `"version": 3` · 대장 56항목(+1 제거) · D-1~D-5 무회귀 |
| T22-158/T23-7 재조준 | 문면 잠금 이관 추적 | `role-separation.md` 에 트리거·`dashboard_enabled` 존재 |
| T26 확장 | 상시 컨텍스트 래칫 | 공식 4항(CLAUDE.md+rules/README+common+**workflow**) · 상수·README 2선언 3중 일치 |
| T28 신설 | 설계 고정 래칫 | 4파일 존재 · `paths:` 0건 · `$REPO_ROOT/CLAUDE.md` 리터럴 0건 · `.claude/rules` 미커밋 · 루트에 '전역 개발 지침' 0건 |
| 전 스위트 | 회귀 | tests/run.sh 27그룹 + tests/hub 전부 통과 |

순수 로직 단위 테스트: bash 판정 함수는 관행대로 시나리오 테스트(T6·T7)로 대신한다.

## 14. 리스크와 대안

- **리스크 1 — 병행 브랜치와 T26 상수 경합**: Q4·R1 이 rules/common 바이트를 바꾸면
  T26 등식이 깨진다. 완화: "후행 병합자가 재실측" 규약(§10) — 1커밋짜리 기계 작업.
- **리스크 2 — 실기기 manifest 가 대장 이전(v1) 세대**: 자동 은퇴가 경로 E(센티널)로
  넘어간다. 배포본을 손대지 않았다면 센티널 2종이 일치해 자동 이관된다. 그래도 보호로
  떨어지면 안내되는 수동 1줄(`mv ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.retired-manual`)로
  종결 — 사용자 승인(백업 후 삭제)의 수동 이행이다.
- **리스크 3 — 4파일 분할로 인한 문서 간 순서 의존**: rules 로드 순서는 규격 미보장.
  완화: §5.1 예외 3(상호 참조는 상대 링크, 순서 의존 서술 금지).
- **리스크 4 — 옛 `install.sh` 사본이 새 manifest(v3)를 만나면**: 읽는 곳은 멱등 비교
  (`grep -v installed_at`)와 대장 grep 조회뿐 — 크래시 없음, CLAUDE.md 를 다시 배포하고
  v2 로 재기록한다(구식 동작 복원). 구 `/harness-update` 는 `version ∈ {1,2}` 검증에 걸려
  중단 — tier0 §10-2 와 같은 "재설치 먼저" 절차로 복구. 롤백 절차는 §9 약점 9.

검토했으나 채택하지 않은 대안:

- **대안 1 — 툼스톤 네임스페이스에 `CLAUDE.md` 허용**: 결정 2 의 근거 3가지로 기각.
  특히 루트 CLAUDE.md 가 레포에 영속하는 한 D-5 fail-closed 와 영구 모순이다.
- **대안 2 — `~/.claude/CLAUDE.md` 를 포인터 스텁("rules/workflow 로 이동")으로 교체**:
  파일이 남는 한 발견 이름 계약상 계속 로드되고 `/init`·`/doctor` 중력의 표적으로
  잔존한다. 사용자 승인(삭제)과도 불일치. 기각.
- **대안 3 — 은퇴를 별도 스크립트(`migrate.sh`)로 분리**: 실행 진입점이 2개가 되고
  사용자가 순서를 기억해야 한다. 설치와 은퇴는 같은 트랜잭션(같은 대장을 읽는다)이므로
  한 스크립트가 맞다. YAGNI 겸 KISS 로 기각.
- **대안 4 — 이관하면서 `coding-style.md` 와의 중복을 즉시 제거**: diff 가 "이동+개작"으로
  섞여 검토 불가능해지고, 위임 승인 문단류의 원문 보존 요구와 충돌. 후속 과제로 분리(A-5).

## 15. 승인 요청 항목

§0 의 A-1~A-5. 특히:

1. **A-1 (착수 시점)**: Q5 머지 대기가 경성 조건이다 — audit-remediation 의 Q 시퀀스가
   길어지면 이 작업 전체가 밀린다. 수용 여부 판단 필요.
2. **A-2 (은퇴 판정)**: protect_modified(경로 C)는 `--force` 로도 삭제하지 않는 설계다 —
   "어떤 경우에도 스크립트가 사용자 수정본을 지우지 않는다"가 의도된 계약인지 확인 필요.
3. **A-3 (manifest v3)**: 어제 v2 출시 직후의 재승급이다. 외부 소비자는
   `commands/harness-update.md` 뿐임을 확인했고 동반 수정하지만, 승급 자체의 승인 필요.
