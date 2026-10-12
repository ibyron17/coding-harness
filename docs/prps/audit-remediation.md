# 전수검사 MAJOR 수정 설계 — audit-remediation (PRP)

> **입력 정본**: [`docs/prps/full-audit-2026-08.md`](full-audit-2026-08.md) (2026-08-28 전수검사, 생존 91건 중 MAJOR 14건).
> **추가 입력(설계 중 수령, 2026-08-28)**: 상류 프로젝트 확정 — 메인 세션이 `gh api` 와 파일 diff 로 실측 대조했다.
> 이 문서는 그 위에서 **MAJOR 15건**(14 + 신규 F-6)의 수정을 설계한다. **구현하지 않는다.**
>
> 작업 위치: 워크트리 `coding-harness-worktrees/audit-remediation` (브랜치 `feature/audit-remediation`, `main`@`9145ef3` 분기).

---

## 0. 이 문서를 쓰면서 직접 재검증한 것

감사 보고서의 인용을 그대로 믿지 않고 아래를 직접 열어 대조했다. **감사 결론과 어긋난 곳은 없었고**, 서술 정정 1건만 있다(§4 AR11 — `react-reviewer` 는 유령이 아니라 상류 실재·부분 설치).

| 항목 | 직접 확인한 것 | 일치 |
|---|---|---|
| A-1 | `rules/web/hooks.md` 6블록 전부 matcher 그룹에 `command` 직접 배치, `hooks` 배열·`type` 없음. `$FILE_PATH` 31·49·90행 | ✅ |
| A-2 | `rules/react/patterns.md:189` "`rules/react-native/` is not yet present" — 실물 8파일 존재 | ✅ |
| A-3 | `rules/common/performance.md:79` "Per-session: `/effort`, the `/model` effort slider, or the `--effort` launch flag" | ✅ |
| B-1 | `_run_usage_api_poll_cycle`(hub_server.py:294-319)에 자기 예외 경계 없음, 유일 경계는 `_maintenance_loop:357` — 예외 시 상태 대입 무산. `_collect_once`(:257-276)의 `finally` 패턴 실재. `hub_usage_fetch.py:139-142` 파싱 2줄이 try 밖. `parse_usage_api_response`(:364)·`describe_json_key_structure`(:414)의 except 는 `(json.JSONDecodeError, TypeError)` 뿐 — `RecursionError` 관통 | ✅ |
| B-2 | TTL = `max(주기×3, 15초)`(hub_server_state.py:71-77, hub_model.py:39) vs 최악 블로킹 = HTTP 10 + Keychain 5(hub_usage_fetch.py:24-25). `is_server_alive` 는 엄격 부등호 — 정확히 15초면 사망 판정 | ✅ |
| C-1 | `commands/dashboard.md:116-117` "불변식 2·5(요소 1줄 1개)를 깨면 허브 파서가 조용히 티어를 강등한다". 실제 파서: `_STEP_LINE_PATTERN` = `<li id="dz-step-(\d+)" class="(done\|active\|wait)"`, `_CELL_LINE_PATTERN` = `<td class="cell" id="dz-cell-…"` — **속성 순서·공백 1칸이 계약**, 줄 앵커 없음 | ✅ |
| C-2 | `test_hub_parse.py` 는 픽스처 5종만 읽음(dashboard.md 미개봉). `tests/run.sh:2664-2670`(T25-6)은 산문 리터럴 `<li id="dz-step-…">`·`<li id="dz-impl-…">` 존재만 검사하며 스스로 "티어 1 파서의 전제"라 선언 | ✅ |
| D-1 | `CLAUDE.md:103-104` 트리거 원문, `commands/dashboard.md` = 1,315줄·87,305바이트 | ✅ |
| E-1 | `install_hooks`/`uninstall_hooks`(hub_settings.py:229-265) — `tests/hub` 에 이름 참조 0건. statusline 쪽 I/O 테스트 선례 `InstallStatuslineForeignConflictIoTest`(test_hub_settings.py:238-283) 실재 | ✅ |
| F-1 | `LICENSE` 부재 + `README.md:342-344` 「## 라이선스」 제목 아래 "사용자 개인 워크플로우 패키징이다" 한 줄 | ✅ |
| F-2 | `ECC` 외부 지칭 6개 파일 실물 확인(git-workflow.md:12 · react-native/production-readiness.md:8 · react-native/hooks.md:28 · web/design-quality.md:53 · prp-prd.md:433 · coding-harness.md 79개 서술) | ✅ |
| F-3 | `rules/common/agents.md:5` "Located in `~/.claude/agents/`" + 10종 로스터 + :22-26 "No user prompt needed" | ✅ |
| F-4 | `development-workflow.md:9` "_(mandatory before any new implementation)_" + gh·Context7·Exa. `react/testing.md:186` `../../skills/e2e-testing/SKILL.md` 상대 링크 | ✅ |
| F-5 | 두 README 에 `python` 0회, `hub/install.sh` 버전 가드 0건, `HUB_FILE_COUNT=16`·대상 총량 계수 검증(:95-103) | ✅ |
| F-6 | 재동기화 선례 커밋 `5f9552f` "refactor: rules를 JS/TS·React·RN 스택으로 큐레이션 (79→37, ECC 최신 반영)" 실재 | ✅ |
| 테스트 파손 | `tests/run.sh` 가 내용을 검사하는 파일 변수 전수 추출 — **rules/ 산문 어서션은 coding-style 3종의 상대 링크 검사뿐**(650·689·702행). CLAUDE.md 내용 검사는 T22-158 1건, dashboard.md 산문 중 이번 편집 구간 검사는 T25-6·T22-126·T22-127 | ✅ |

**감사에 대한 이견**: 없음. 단 F-3 의 "`react-reviewer` 는 배포물에도 저자 머신에도 없다"는 서술은 상류 확정으로 갱신된다 — 상류 ECC 에 `react-reviewer.md` 가 실재하고, 저자 머신은 67종 중 51종만 깔린 부분 설치다. 결함의 본질(순수 클론에서 실행 불가 지시)은 변하지 않고, "유령 참조"라는 표현만 "부분 설치에서도 재현되는 참조"로 바뀐다.

---

## 1. 요구사항 요약

전수검사가 확정한 MAJOR 14건 + 설계 중 확정된 F-6(로컬 패치 추적 부재) 1건, 합계 **15건**을 두 트랙으로 나눠 수정한다. **품질 트랙(A~E, 5단계)** 은 릴리스와 무관하게 진행하고, **릴리스 트랙(F, 3단계)** 은 공개 배포물 요건을 채운다 — 사용자가 릴리스 시점을 따로 관리하므로 트랙 간 병합 순서는 자유다. 같은 파일을 어차피 여는 MINOR 15건을 편승시키고, 나머지 62건은 후속 PRP 3건으로 명시 이관한다(§9).

### 성공 기준 (검증 가능한 형태)

1. 정본 검증 4명령이 모든 단계 커밋 시점에 전부 통과한다:
   `bash tests/run.sh` · `python3 -m unittest discover -s tests/hub -t .` · `python3 -m py_compile hub/bin/*.py` · `bash -n install.sh` (+ 이번 범위에서 `bash -n hub/install.sh`)
2. B-1: 폴링 사이클이 **어떤 경로로 끝나도** `last_attempt_at_ms` 가 찍힌 상태를 반환한다 — 깊은 중첩 응답(RecursionError 유발)을 실제 파싱 경로에 태우는 신규 테스트가 이를 고정한다.
3. C-2: `commands/dashboard.md` 의 예시 줄과 `hub_parse` 정규식을 **직접 잇는** 정·역방향 테스트가 생기고, 예시의 `id`↔`class` 순서를 뒤집으면 그 테스트가 실패한다(뮤테이션 검증).
4. F-6: A-1·A-2·F-3 의 로컬 패치가 상류 재동기화로 되돌아가면 `tests/run.sh` 가 실패한다.
5. 순수 클론 사용자 관점: LICENSE·NOTICE.md 가 존재하고, rules 가 지시하는 에이전트·도구가 배포물과 일치하거나 조건부로 표기된다.

---

## 2. 확정된 전제 (재론하지 않는다)

1. **저장소 정체 = 공개 배포물** (사용자 결정, 2026-08-28). 모든 사용자가 순수 클론한다는 전제이며, 이것이 F-1~F-5 를 MAJOR 로 만들었다. 이 설계는 그 전제를 약화시키지 않는다.
2. **상류 확정** (사용자 확인 + 메인 세션 `gh api`·diff 실측, 2026-08-28):

   ```
   레포     : https://github.com/affaan-m/everything-claude-code  (ECC, "Everything Claude Code")
   라이선스 : MIT (SPDX: MIT) — Copyright (c) 2026 Affaan Mustafa
   상태     : 활발히 유지 중 (마지막 푸시 2026-08-28)
   ```

   - **파생 43개**: `rules/` 36(README + common 10 + typescript 5 + react 5 + react-native 8 + web 7 — `karpathy-guidelines.md` 제외) · `agents/code-reviewer.md` 1 · `commands/` 6(`code-review`·`prp-commit`·`prp-implement`·`prp-plan`·`prp-pr`·`prp-prd`).
   - **원저작**: `agents/design-architect.md`·`implementer.md`·`explore.md`, `commands/dashboard.md`·`dashboard_template.html`·`harness-update.md`·`hub.md`, `rules/common/karpathy-guidelines.md`, `CLAUDE.md`, `install.sh`, `hub/` 전체, `tests/` 전체, `docs/prps/` 전체, `README.md`.
   - **결함 귀속**: A-1·A-2·F-3·F-4 와 stack MINOR 다수는 **상류 결함**(해당 파일 diff 0줄), A-3·`rules/README.md` 산술은 **로컬**, B·C·D·E·F-1·F-2·F-5 는 **원저작 영역**.
3. **F-2 는 선택이 아니라 MIT 조건의 이행이다.** MIT 는 "저작권 고지와 허가 고지를 사본 또는 실질적 부분에 포함"을 요구한다 — 파생 43개 파일을 재배포하는 이 저장소는 그 조건을 지금 이행하지 않고 있다. F-1(이 저장소 자체의 라이선스 선택)은 자유가 있다. (법률 자문이 아니라 라이선스 조항의 문언이다.)
4. **벤더링 파일의 로컬 패치는 이 저장소의 기존 관행이다.** 실측: `performance.md` 124줄, `agents/code-reviewer.md` 386줄, `rules/README.md` 113줄, `commands/code-review.md` 34줄, `coding-style.md` 8줄, `git-workflow.md` 2줄이 이미 상류와 갈라져 있다. 따라서 A-1·A-2·F-3 을 로컬 패치로 고치는 것은 관행 위반이 아니고, MIT 도 허용한다. **문제는 그 목록이 어디에도 없다는 것**(F-6)이다.

   **사후 각주(R3 3회차 검수 정정, 2026-09-02)**: 위 "이미 갈라져 있다" 목록의 `coding-style.md` 는 `rules/common/coding-style.md` 를 가리키며, 상류 원문과의 직접 대조로 **진짜 로컬 패치**임이 확인됐다(NOTICE.md §5 목록에 편입). 같은 목록의 `git-workflow.md` 는 로컬 패치가 아니다 — 로컬 파일은 상류가 벤더링 이후 자체 커밋(`569b1d5b`)으로 갱신하기 **전** 상태와 바이트 동일하다(로컬 편집 0줄). 이 항목이 "상류와 갈라져 있다"는 관측만으로 두 파일을 같은 범주("이미 로컬 패치된 파일")로 묶은 것이 §5 로컬 패치 표에 무엇을 넣을지를 둘러싼 R3 3회차 검수의 혼란의 출처였다 — "갈라져 있다"는 관측은 원인이 우리 편집인지 상류 표류인지까지는 말해주지 않는다. 자세한 사실관계는 NOTICE.md §5 「상류가 벤더링 이후 갱신했으나 아직 취하지 않은 파일」 각주 참조.
5. **상류 PR 은 이번 범위 밖이다.** A-1·A-2·F-4(및 F-3 로스터의 "Located in" 단정)는 상류 PR 후보로 §9 에 목록만 남긴다 — 우리 통제 밖이고 시점을 보장할 수 없으므로 로컬 패치로 완결한다.
6. **`hub/` 는 표준 라이브러리 전용** — 문서화된 결정(`hub-dashboard.md:863-864`). 린터·포매터를 도입하지 않는다.
7. **검증 정본**: `bash tests/run.sh` · `python3 -m unittest discover -s tests/hub -t .` · `python3 -m py_compile hub/bin/*.py` · `bash -n install.sh`.

### 비목표 (이번 범위 밖 — 명시적으로 건드리지 않는다)

- **상류 PR 제출** (전제 5).
- **CLAUDE.md 이중 역할 해소**(전역 배포본 ↔ 프로젝트 지침 분리) — §7 충돌 2 참조, 후속 PRP.
- **`tests/run.sh` 한글 산문 어서션 99건의 일괄 재작성** — §7 충돌 3 에서 기준만 세우고, 신설 테스트에만 적용한다.
- **루트 `install.sh` 의 shell MINOR 군**(121·201·360·429·88행) — 후속 PRP `shell-hardening`.
- **`tests/run.sh` 구조 결함 군**(trap 덮어쓰기·2,717줄 함수·공허 통과류) — 후속 PRP `tests-hardening`.
- **`hub_usage_fetch` 네트워크 경계 MINOR 군**(리다이렉트 재전송·무제한 읽기·429 대기시간 무시·TLS 접힘) — 후속 PRP `shell-hardening` 또는 별건.

---

## 3. 단계 분할 — 2트랙 8단계

각 단계는 독립적으로 커밋·검증 가능하다. 표의 검증 명령은 해당 커밋 전에 전부 통과해야 한다.

### 품질 트랙 (릴리스와 무관하게 진행 가능)

| 단계 | 항목 | 수정 파일 | 선행 | 검증 명령 | 통과 기준 |
|---|---|---|---|---|---|
| **Q1** | B-1 · B-2 (+편승: 주기 하한) | `hub/bin/hub_server.py` · `hub/bin/hub_usage_fetch.py` · `hub/bin/hub_usage.py` · `hub/bin/hub_collect.py` · `tests/hub/test_hub_server.py` · `tests/hub/test_hub_usage.py` · `tests/run.sh`(T25-122 재작성) | 없음 | `py_compile` + `unittest` + `run.sh` | 신규 회귀 테스트 GREEN + T25-122 재작성분 GREEN + 뮤테이션 1회 확인 |
| **Q2** | C-1 · C-2 (+편승: dashboard.md :146·:149·:11, hub_parse docstring) | `commands/dashboard.md` · `tests/hub/test_hub_dashboard_contract.py`(신설) · `hub/bin/hub_parse.py`(docstring) · `tests/run.sh`(T25-6 주석 재규정) | 없음 | `unittest` + `run.sh` | 정·역방향 테스트 GREEN + 역방향 뮤테이션 확인 |
| **Q3** | E-1 | `tests/hub/test_hub_settings.py` | 없음 | `unittest` | I/O 테스트 3개 GREEN |
| **Q4** | A-1 · A-2 · A-3 (+편승: performance.md:83, react/patterns.md:82·:194) — **F-6 이빨 ①** | `rules/web/hooks.md` · `rules/react/patterns.md` · `rules/common/performance.md` · `tests/run.sh`(신설 3검사) | 없음 | `run.sh` | 신설 훅 JSON 스키마 검사·부재단정 가드·effort 앵커 GREEN |
| **Q5** | D-1 (+편승: CLAUDE.md:154) | `CLAUDE.md` · `commands/dashboard.md`(호출 규약 절 1문단) | Q2 권장(같은 파일 순차 편집) | `run.sh` | T22-158·T22-126·T22-127·T23-7 전부 GREEN(파손 없음 확인) |

### Q1 검수 종결 (2회차 PASS, 2026-08-28) — Q2 로 이관된 후속 2건

**Q1 은 검수 2회차에서 PASS 했다.** 1회차 MAJOR 3 · MINOR 3 이 전부 해소되고 뮤테이션 8건으로 재현 검증됐다(검증: `py_compile` · 유닛 500 · `bash -n` · `run.sh` 24/24). 2회차가 새로 만든 MINOR 2건은 **커밋을 막지 않는다**는 검수 판정에 따라 커밋했고, 아래로 **Q2 범위에 편입**한다 — Q2 가 이미 `tests/run.sh` 를 여는 단계라 같은 파일을 다시 열지 않는다.

- **N-1 (MINOR, 회귀)** — `tests/run.sh` T25-122: `ast.parse` 가 `SyntaxError` 를 던지면 python 이 마커를 하나도 출력하지 못해 `__MISSING__` 가드가 발동하지 않고, **부재 방향 검사 ①③ 이 공허하게 통과**한다. `main` 에는 네 본문 전부에 대한 `-z` 빈 문자열 가드가 있었으므로 이것은 **잃어버린 성질의 회귀**다. 조용하지는 않다(②④ 와 T24 가 실패한다) — 그래서 MINOR 다. **수정**: `hub_server_ast_output=$(...)` 직후에 `[[ -z "$hub_server_ast_output" ]]` → `record_failure`+`return 1` 한 줄. 잃은 자리가 가장 안전이 중요한 두 검사이므로 **Q2 에서 반드시 넣는다.**
- **N-2 (MINOR, 거짓 커버리지 주장)** — `tests/hub/test_hub_collect.py:886-893` 케이스 (c)가 `CONFIG_PATH` 를 쓰지 않아 `load_config` 의 조기 반환을 타고 **clamp 코드를 한 줄도 실행하지 않는다**(검수자 실측: clamp 첫 줄에 `raise` 를 심어도 통과). 실제 검출 구멍은 다른 4케이스가 메우므로 무해하지만, docstring 이 덮지 않는 경로를 덮었다고 주장한다. **수정**: `hub_collect.CONFIG_PATH.write_text("{}")` 한 줄 추가.
- **N-3 (INFO)** — 새 하한값이 README 에 있으나 기계적으로 고정되지 않았다(상수를 60→120 으로 바꿔도 문서 정합 검사가 하나도 실패하지 않는다). T25 관례에 비춘 빈자리 — 후속 `tests-hardening` 으로 넘긴다.
- **N-4 (INFO)** — `__MISSING__` 실패 메시지가 AST 덤프 전체(80줄)를 싣는다. 함수 이름만 싣도록 좁힌다 — Q2 편승 후보.

### Q2 검수 종결 (1회차 PASS, 2026-08-28) — Q5 로 이관된 후속 1건

**Q2 는 검수 1회차에서 PASS 했다**(MAJOR 0 · MINOR 1). 검증: `py_compile` · 유닛 **511**(기준선 507 → +4) · `bash -n` · `run.sh` **26/26**. 뮤테이션 5종이 전부 의도대로 작동함을 검수자가 재현했다 — 추출 0건 방지, 정규식 느슨화 감지, N-1 새 가드 메시지, N-2 케이스 (c) error 전환, N-4 함수명 표기.

- **Q2-N1 (MINOR, 문서 정확성) → Q5 로 이관.** `commands/dashboard.md` 신설 불변식 머리글이 **불변식 1(모드 배타성)을 「허브 파서가 전제로 삼는다」로 분류**했으나 실측 반증됐다 — 선형(`dz-step`)·매트릭스(`dz-cell`) 마크업을 한 텍스트에 공존시켜 `parse_dashboard_html` 을 호출하면 예외 없이 `Tier1Snapshot` 이 반환되고 `.steps`·`.matrix_done` 둘 다 채워진다. `hub_template.html` 은 `matrix_done` 을 읽지도 않는다(grep 0건). **즉 C-1 의 존재 이유(파서가 요구하지 않는 것을 파서 요구로 서술하는 과장 제거)를 축소판으로 재현한 형태**이고, 같은 문단 위쪽이 불변식 3·속성 순서만 「파서가 실제 요구하는 것」으로 정확히 서술한 것과 내적으로 어긋난다. **수정**: 불변식 1을 「`init` 의 생성 규칙(모드 배타적 생성) — 위반 시 결과는 현재 코드로 실측되지 않음」으로 재분류하거나 파서 요구군에서 뺀다. Q5 가 같은 파일을 여므로 그때 처리한다.

**PRP 계수 오차 1건 기록** — §9 편승 표의 「dashboard.md:11 `../../` 링크 **4건**」은 실제로 **2건**(11행·117행)이다. 4건은 `dashboard.md` 2 + `commands/hub.md` 2 를 합친 수였고 PRP 가 한 파일로 귀속시켰다. 구현자가 실측대로 2건만 고친 판단이 옳다. **`commands/hub.md` 의 2건은 어느 단계도 열지 않으므로 후속 `rules-docs-sync` 로 이관한다.**

### Q3 검수 종결 (1회차 PASS, 2026-08-29)

**PASS** — CRITICAL/HIGH/MEDIUM 0 · LOW 2 · INFO 1. 검증: 유닛 **514**(기준선 511 → +3) · `run.sh` **26/26** · 사용자 실제 `~/.claude/settings.json` mtime·크기 불변(작업 전후 2회 확인). 뮤테이션 3종 + 「치환 라인 제거」 1종이 전부 RED 로 재현됐다 — 자기 검증 단정이 죽은 코드가 아님이 실측됐다.

**메인 세션이 제기했다가 기각된 우려 1건(기록)**: `_backup_timestamp()` 의 해상도가 낮아 같은 초에 두 번 호출되면 백업이 덮어써져 (c)의 「새 백업이 안 생긴다」 단정이 약해진다고 봤다. **틀렸다** — 그 함수는 밀리초까지 포함하고, 게다가 (c) 경로는 `if installed:` 가드로 `_write_settings_atomically` 가 두 번째에 호출조차 되지 않는다. 두 겹으로 무효한 우려였다.

LOW 2건은 선택적 스타일이므로 이관하지 않는다 — (a) 테스트가 두 진입점을 한 메서드에 병합한 것(검수 판정: 실패 시 install 단정이 uninstall 호출보다 먼저 완주하므로 마스킹 없음), `ensure_ascii=False` 표기 불일치.

**INFO → 후속 `tests-hardening` 이관 1건**: `hub_settings.py:238·258` 의 `HubHooksSchemaError` catch 분기 — outer JSON 은 유효하나 `hooks` 필드 스키마가 깨진 경우의 **I/O 진입점 레벨 반환 계약이 테스트되지 않는다**. 순수 함수 레벨(`MergeHubHooksTest`/`StripHubHooksTest`)에서는 덮였고 §8-3 설계 범위 밖이므로 이번 결함은 아니다.

**A-1 범위 확인 (Q4 착수 전 메인 세션 실측)**: 무효 훅 JSON 블록은 `rules/web/hooks.md` **한 파일에만** 있다(6블록·`$FILE_PATH` 3곳). `rules/` 전체를 기계 판정한 결과 다른 `hooks.md`(typescript·react·react-native·**python** — tier0 가 새로 넣은 것 포함)에는 훅 설정 JSON 블록이 없다. **A-1 의 범위 산정이 정확하고, 신설 스키마 검사가 다른 파일에서 오탐하지 않는다.**

### 릴리스 트랙 (사용자가 시점 관리)

| 단계 | 항목 | 수정 파일 | 선행 | 검증 명령 | 통과 기준 |
|---|---|---|---|---|---|
| **R1** | F-3 · F-4 (+편승: react/testing.md:18 CRA) — **F-6 이빨 ②** | `rules/common/agents.md`·`testing.md`·`security.md`·`performance.md`(:138)·`code-review.md`·`development-workflow.md` · `rules/typescript/testing.md` · `rules/react/security.md`·`testing.md` · `rules/react-native/testing.md` · `tests/run.sh`(denylist 검사) | Q4 권장(performance.md 순차 편집) | `run.sh` | denylist 검사 GREEN + 미배포 에이전트 참조 0건 |
| **R2** | F-5 (+편승: README:280·:122, hub/install.sh:97·:206, coding-harness.md rev4 각주, install.sh 카운트 파리티 테스트) | `hub/README.md` · `README.md` · `hub/install.sh` · `docs/prps/coding-harness.md` · `tests/run.sh` | 없음 | `bash -n install.sh` + `bash -n hub/install.sh` + `run.sh` | hub/install.sh 를 실행하는 기존 T군(샌드박스 설치·제거) 전부 GREEN |
| **R3** | F-1 · F-2 · F-6(문서부) | `LICENSE`(신설) · `NOTICE.md`(신설) · `README.md`(라이선스 절) · `tests/run.sh`(존재+앵커 검사) | Q4·R1 이후(로컬 패치 목록 확정을 위해) | `run.sh` | LICENSE·NOTICE 검사 GREEN |

**총 수정 파일 30개** (수정 27 + 신설 3: `LICENSE`·`NOTICE.md`·`tests/hub/test_hub_dashboard_contract.py`).

같은 파일을 두 단계가 만지는 곳은 두 곳뿐이다 — `commands/dashboard.md`(Q2 → Q5, 절이 다르다: DOM 계약 절 vs 호출 규약 절)와 `rules/common/performance.md`(Q4 → R1, effort 절 vs :138 에이전트 참조). 권장 순서만 지키면 충돌이 없다.

---

## 4. 항목별 수정 설계

### A-1 — `rules/web/hooks.md` 훅 JSON 6블록 (결정 AR1)

**결정 AR1**: 6블록 전부를 공식 3단 스키마로 재작성하고, `$FILE_PATH` 를 stdin JSON 파싱으로 대체한다. 정답 참조로 이 저장소 자신의 `hub/bin/hub_settings.py` 의 `_hub_hook_entry()` 를 **백틱 경로 산문**으로 지목한다(마크다운 링크가 아니라 — 설치 3루트에서 링크 해석이 갈라지는 문제는 감사 MINOR 로 확인된 별건이므로, 링크를 새로 만들지 않는다).

정형(matcher 있는 이벤트):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const p=JSON.parse(d).tool_input?.file_path;if(p)require('child_process').spawnSync('pnpm',['prettier','--write',p],{stdio:'inherit'})})\""
          }
        ]
      }
    ]
  }
}
```

- 파일 경로가 필요한 3블록(prettier 25행·eslint 43행·stylelint 84행): 위 형태로 — `spawnSync` 인자 배열이라 경로에 공백·따옴표가 있어도 셸 인젝션이 없다. **stdin 파싱의 관용구는 같은 파일 104행 PreToolUse 블록이 이미 갖고 있다** — 그 선례를 따른다.
- tsc 블록(61행): `$FILE_PATH` 를 안 쓰므로 명령은 그대로, JSON 형태만 3단으로.
- PreToolUse 블록(104행): stdin 처리는 이미 옳다 — JSON 형태만 3단으로.
- Stop 블록(122행): matcher 없이 `{"hooks":[{"type":"command","command":"pnpm build"}]}` 그룹.
- 각 블록의 `description` 은 JSON 에서 빼고 블록 위 산문 제목으로 옮긴다(이미 제목이 있으므로 대부분 삭제로 충분).
- 파일 안에 한 줄 추가: "이 형태의 정답 참조는 이 저장소의 `hub/bin/hub_settings.py` `_hub_hook_entry()` 다 — `type: \"http\"` 미발동 실측 근거는 `docs/prps/hub-dashboard.md` 에 있다."

**재발 방지(F-6 이빨 ①-a)** — `tests/run.sh` 신설 검사: python3 로 `rules/web/hooks.md` 의 ```` ```json ```` 펜스를 전부 추출·`json.loads` 하고, 최상위 `hooks` 이벤트 맵의 모든 matcher 그룹이 `hooks` 배열을 갖고 각 엔트리가 `type == "command"` 와 `command` 를 가짐을 단정한다. 추가로 파일 전체에 `$FILE_PATH` 문자열이 0건임을 단정한다. **이 검사가 상류 재동기화로 무효 블록이 부활하는 것을 즉시 잡는다.**

### A-2 — `rules/react/patterns.md:189` RN 부재 단정 (결정 AR2)

**결정 AR2**: 186-190행의 React Native 절을 실물로 향하는 포인터로 교체한다:

> React Native has its own rules track — see `../react-native/` (8 files: coding-style, patterns, hooks, testing, performance, security, production-readiness, accessibility). Both tracks load together on `**/*.tsx` matches; React core hooks/patterns from this file still apply.

(정확한 파일명 열거는 구현 시 `ls rules/react-native/` 로 재확인한다.)

**재발 방지(F-6 이빨 ①-b)** — `tests/run.sh` 신설 검사: `rules/` 전체에 `not yet present` 문자열이 0건임을 단정한다. 배포 트리에 대한 부재 단정은 rules 본문에 두지 않는다는 결정의 기계화다 — 미래에 정당한 용례가 생기면 이 검사를 그때 개정한다(YAGNI: 지금은 예외 목록을 만들지 않는다).

**편승 (같은 파일)**:
- `:82` — Error Boundary 클래스 컴포넌트 서술이 `coding-style.md:97`("Forbidden in new code")과 충돌해 보이는 문제: `:82` 에 "prefer `react-error-boundary`; a class component is the exception `coding-style.md` §Class Components already carves out" 취지의 한 줄 상호 참조를 넣어 해소한다(두 파일 다 고치지 않고 예외 관계만 명시).
- `:194` Skill Reference 절 — 존재하지 않는 `skills/react-patterns/SKILL.md` 류 3건: F-4 와 같은 처방(AR12)을 이 파일에는 이 단계에서 적용한다 — 상대 링크·경로 서술을 제거하고 "상류 ECC(`https://github.com/affaan-m/everything-claude-code`)의 skills 를 쓰는 환경이라면 참조하라"는 조건부 산문으로 바꾼다.

### A-3 — `rules/common/performance.md:79` `/effort` 지속성 (결정 AR3)

**결정 AR3**: 79-80행의 분류를 공식 문서대로 교체한다. 정본 근거는 감사가 WebFetch 로 확보한 원문이다:

> "`low`, `medium`, `high`, and `xhigh` persist across sessions when you set them in an interactive session." — <https://code.claude.com/docs/en/model-config>

교체 문안(설계 초안 — 구현자는 해당 공식 문서를 다시 열어 원문과 대조 후 확정한다):

> Set interactively, `/effort` (levels `low`/`medium`/`high`/`xhigh`) **persists across sessions**. Session-scoped only: the `--effort` launch flag, and `/effort` in non-interactive (`-p`) runs. The docs do not state whether the `/model` effort slider persists — do not assume either way.

**편승 (같은 파일)**: `:83-84` "— `max` and `ultracode` are session-only" 단정(감사 MINOR·CONFIRMED — 둘 다 문서상 지속 경로가 있고 `ultracode` 는 effort 레벨이 아님)을 함께 고친다. `effortLevel` settings 필드가 4레벨만 받는다는 문장은 유지하고, session-only 단정만 제거한 뒤 문서 원문에 맞는 서술로 교체한다 — **구현자는 이 두 문장을 쓸 때 반드시 공식 model-config 문서를 열어 원문을 인용 확인한다**(이 PRP 는 감사의 인용까지만 보증한다).

**앵커(F-6 이빨 ①-c)** — `tests/run.sh` 신설 검사: `rules/common/performance.md` 에 `persist across sessions` 토큰이 존재함을 단정한다(§7 충돌 3 의 기준 적용 — 산문 전문이 아니라 계약 토큰만).

### B-1 — 폴링 예외로 백오프 상태 유실 (결정 AR4)

**결정 AR4**: `_run_usage_api_poll_cycle` 이 **어떤 경로로 끝나도 시도가 반영된 상태를 반환**하도록 재구성한다. `_collect_once` 의 판단("실패해도 시각을 갱신한다")을 옮기되, 형태는 `finally` 가 아니라 **내부 except + 단일 return** 이다 — 여기 상태는 가변 속성이 아니라 불변 dataclass 반환값이라, `finally` 안의 `return` 은 예외를 삼키는 안티패턴이 되기 때문이다(GOTCHA 1).

```python
# hub_server.py — 설계 스케치 (모듈 상수 신설)
USAGE_API_UNEXPECTED_ERROR_REASON = "internal_error"   # fetch 계약 밖에서 샌 예외의 실패 사유

def _run_usage_api_poll_cycle(now_ms, poll_state, config):
    if not (config.show_usage_panel and config.usage_api_enabled):
        return poll_state
    if not hub_usage.should_attempt_usage_api_poll(now_ms, poll_state, config.usage_api_poll_interval_seconds):
        return poll_state

    # 게이트를 통과했으면 이 아래는 무슨 일이 있어도 "시도 1회"로 집계된다(_collect_once 와 같은 판단).
    failure_reason: str | None = USAGE_API_UNEXPECTED_ERROR_REASON
    try:
        capture, fetch_failure_reason, failure_detail = hub_usage_fetch.fetch_rate_limit_capture(now_ms)
        if capture is not None:
            _write_usage_api_capture(capture)
            hub_collect.clear_usage_api_failure()
            failure_reason = None          # 부수 효과까지 끝난 뒤에만 성공으로 친다
        else:
            hub_collect.record_usage_api_failure(fetch_failure_reason, failure_detail)
            failure_reason = fetch_failure_reason
    except Exception as error:
        # 관측 가능성 복구: /hub status 의 usage_api_last_failure 가 비지 않게 한다.
        # record_usage_api_failure 는 "자신은 절대 예외를 던지지 않는다"가 문서화돼 있다(hub_collect.py:609).
        hub_collect.record_usage_api_failure(USAGE_API_UNEXPECTED_ERROR_REASON, None)
        print(f"사용량 API 폴링 사이클에서 분류되지 않은 예외: {error}", file=sys.stderr)
    return hub_usage.next_usage_api_poll_state(now_ms, poll_state, failure_reason)
```

- 성공 후 `clear_usage_api_failure()` 의 OSError(unlink EACCES 등)로 새는 경우: `failure_reason` 이 아직 `internal_error` 라 **실패한 시도로 집계**된다 — 원격은 성공했지만 백오프가 자란다. 의도된 보수성이다: 이 결함의 피해 모델이 "자격증명 읽기 + 원격 호출의 무한 반복"이므로, 애매하면 호출 빈도를 줄이는 쪽으로 눕힌다.
- `"internal_error"` 는 `FailureReason` Literal(fetch 의 반환 계약)에 넣지 않는다 — 이 사유는 fetch 가 반환하는 것이 아니라 사이클이 집계하는 것이고, `next_usage_api_poll_state(failure_reason: str | None)` 는 임의 문자열을 받아 `http_rate_limited` 외에는 동일하게 지수 백오프한다(hub_usage.py:458-473 실측).

**동반 수정 (hub_usage_fetch.py / hub_usage.py)**:
- `hub_usage_fetch.py:139-142` 의 `parse_usage_api_response`·`describe_json_key_structure` 호출 2줄을 기존 try 경계 안으로 옮긴다(A-SEC 경계 주석의 취지 그대로 — 이 함수의 마지막 방어선이 파싱까지 덮게 한다). 반환 구조는 불변.
- `hub_usage.py:364`·`:414` 의 `except (json.JSONDecodeError, TypeError)` 에 `RecursionError` 를 추가한다 — 깊은 중첩 응답에서 `json.loads` 가 던지는 실측 경로다. 다른 except(146·185·347행)는 신뢰 로컬 파일 경로이므로 **건드리지 않는다**(카프시 #2 — 비신뢰 원격 입력이 닿는 두 곳만).

**회귀 테스트**: §8-2. fetch 자체를 mock 하지 않고 그 아래 층(urlopen·Keychain 판독)만 mock 해 실제 파싱 경로를 태운다 — 기존 3개 테스트가 fetch 를 mock 해서 이 경로를 못 덮는다는 감사 지적의 직접 반영이다.

### B-2 — 하트비트 TTL 여유 0 (결정 AR5)

**결정 AR5**: 감사가 제시한 두 갈래 중 **(a) 폴링을 자기 데몬 스레드로 분리**를 택한다.

**(b) TTL 하한 상향을 기각하는 근거**: TTL 은 상수이고 최악 블로킹은 상수가 아니다 — `urlopen` 의 timeout 은 전체 시간이 아니라 소켓 연산별 상한이라(감사 실측) 병리적 응답에서 10초 설정으로 수십 초가 가능하고, 같은 사이클의 배경 상한 수집이 얹힌다. 어떤 하한을 골라도 docstring 의 "일하는 서버를 죽었다고 오판하지 않는다"는 약속을 **참으로 만들 수 없고**, 약속을 "대체로 오판하지 않는다"로 약화시켜야 한다. (a)는 산술 자체를 제거한다 — 원격 지연이 하트비트 티커에서 사라지므로 TTL 15초가 그대로 성립한다.

**(a)의 비용과 그 수용 근거**: 스레드 1개 추가. 이 모듈은 이미 `ThreadingHTTPServer`(요청 스레드) + 유지보수 데몬 스레드의 다중 스레드 설계이고, 폴링 상태는 새 스레드의 **지역 변수로 그대로 남아** "전역 가변 상태 금지"(결정 A3)를 유지한다. 파일 쓰기 경합은 이미 다중 **프로세스** 전제로 설계돼 있다(`_write_usage_api_capture` 의 공존 게이트, 결정 A2) — 스레드 분리가 새 동기화 문제를 만들지 않는다.

**명시적 번복**: `hub-dashboard.md` 결정 A3 계열의 배치 서술("사용량 API 폴링 게이트는 유지보수 티커가 수행하고, 백오프 상태는 그 함수의 지역 변수로 남긴다") 중 **배치 부분을 번복**한다 — 폴링은 전용 스레드 `_usage_api_poll_loop` 로 옮긴다. 번복 사유: 티커에 원격 지연을 태우면 하트비트 TTL 산술이 성립하지 않음이 실측됐다(감사 B-2). 상태의 지역성·게이트 조건·백오프 규칙은 그대로다.

```python
# hub_server.py — 설계 스케치 (_maintenance_loop 뒤, run_server 앞에 배치)
def _usage_api_poll_loop(config, stop_event):
    """사용량 API 폴링 전용 데몬 스레드(결정 AR5 — 결정 A3 의 배치 번복).

    유지보수 티커에서 분리한 이유: 원격 호출(최악 HTTP 10 + Keychain 5초, 소켓 연산별 상한이라
    상수 상한 없음)이 하트비트와 같은 스레드에 있으면 TTL(15초) 산술이 성립하지 않는다.
    백오프 상태는 이 함수의 지역 변수로만 산다(전역 가변 상태 금지는 유지).
    """
    usage_api_poll_state = hub_usage.UsageApiPollState()
    while not stop_event.is_set():
        try:
            usage_api_poll_state = _run_usage_api_poll_cycle(
                int(time.time() * 1000), usage_api_poll_state, config
            )
        except Exception as error:
            # AR4 이후 이 경로는 이론상 도달하지 않지만, 스레드 사망 = 폴링 영구 정지이므로
            # _maintenance_loop 와 같은 최후선을 둔다(stderr 만, 추가 I/O 없음).
            print(f"사용량 API 폴링 루프에서 처리되지 않은 예외: {error}", file=sys.stderr)
        stop_event.wait(config.server_heartbeat_interval_seconds)
```

- 깨우기 주기는 현행과 동일하게 `server_heartbeat_interval_seconds` 를 쓴다(게이트 판정 입도 보존 — 실제 호출 간격은 `should_attempt_usage_api_poll` 이 지금처럼 결정한다). 새 설정 키를 만들지 않는다(YAGNI).
- `run_server` 에서 두 데몬 스레드를 함께 띄운다. 폴링 스레드는 조건 없이 띄운다 — 게이트가 사이클 첫 줄에서 끝나므로 꺼진 설정에서의 비용은 5초당 불리언 검사 2회다(조건부 기동으로 절약할 것이 없다).
- `_maintenance_loop` docstring 재작성: 임무를 (1) 하트비트 (2) 배경 수집 상한 둘로 줄이고, "(3) 폴링" 항목과 "사이클 안의 사용량 API 호출이 최악 15초" 근거 문장을 제거한다. 앞뒤 이중 touch 는 유지하되 근거를 "배경 수집이 파일시스템 상황에 따라 느릴 수 있다"로 고쳐 **실제 보장 범위**(원격 지연은 이 티커에 없음, 로컬 수집 지연은 이중 touch 로 완화)를 적는다.
- `hub/README.md` 는 수정 불요를 실측으로 확인했다 — 폴링 주체를 "상주 서버가"로만 서술한다(:346). 구현 중 `grep -n '티커' hub/README.md` 로 재확인만 한다.

**T25-122 재작성** (§6 참조): 계약을 강화 방향으로 확장한다 — "폴링은 요청 경로에 없다" 에서 "폴링은 요청 경로에도, 하트비트 티커에도 없다 — `_usage_api_poll_loop` 에만 있다" 로. 재작성은 검사 내용만이 아니라 **sed 추출 앵커의 교체를 포함한다** — maintenance 본문 앵커의 종료 경계를 `run_server` → `_usage_api_poll_loop` 로 바꾸고, `run_server` 본문은 마지막 함수이므로 `$`(파일 끝)까지 추출한다(앵커 상세는 §6 표의 T25-122 행).

### B 편승 — 폴링·하트비트 주기 하한 (결정 AR6)

감사 §3 이 MINOR 로 강등한 `hub_collect.py:87` 계열(주기 0 → busy loop)을 **Q1 에 편승**시킨다. 근거: AR5 가 `stop_event.wait(주기)` 루프를 하나 더 만들어 **busy-loop 표면이 1→2 로 늘어난다** — 같은 단계에서 하한을 넣는 것이 맞다. 설계: `load_config`(hub_collect.py:120) 의 값 적용 지점에서 `server_heartbeat_interval_seconds`·`usage_api_poll_interval_seconds` 에 이름 있는 하한 상수(예: `MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS = 1`, `MIN_USAGE_API_POLL_INTERVAL_SECONDS = 60`)로 clamp 하고, clamp 발생 시 기존 config 경고 채널(`load_config` 의 warnings 반환)에 한 줄 남긴다. 하한값 자체는 구현 시 기존 기본값(5초·300초)과 훅 쓰로틀(5초) 관계를 보고 확정하되 위 예시를 기본안으로 한다.

### C-1 — 파서 계약 서술 역전 (결정 AR7)

**결정 AR7**: `commands/dashboard.md` 의 소비자 경고(:116-117)와 불변식 절을 실측 계약으로 교체한다. 세 가지를 정확히 반영한다 — 감사 실측 표(§2 C-1) 그대로.

① :116-117 교체 문안(초안):

> 이 DOM 계약에는 외부 읽기 소비자(`/hub`)가 있다. 파서가 실제로 요구하는 것은 **(i) 요소 하나가 한 줄 안에 온전히 있을 것**(불변식 3)과 **(ii) 아래 「정규 속성 순서」**다. 이를 깨면 티어가 강등되는 것이 아니라 **그 요소가 허브에서 조용히 사라진다** — 티어는 1로 유지되고 경고도 없다(예: `#dz-step-*` 의 속성 순서를 뒤집으면 진행률 줄은 멀쩡한데 활성 단계 줄만 사라진다). 불변식 2·5(1줄 1개)는 파서가 아니라 `step` 절차의 `grep -c` 계수가 요구하는 전제다.

② **정규 속성 순서를 계약으로 명문화** — 불변식 절에 신설 항목:

> **정규 속성 순서(허브 파서 계약)** — 아래 형태에서 속성 순서와 공백 1칸을 바꾸지 않는다:
> - `<li id="dz-step-{n}" class="{state}">`
> - `<li id="dz-impl-{k}" class="{state}">`
> - `<td class="cell" id="dz-cell-{g}-{p}" data-state="{state}">`
>
> 이 순서는 `hub/bin/hub_parse.py` 의 정규식과 `tests/hub/test_hub_dashboard_contract.py` 가 고정한다.

`step`·`impl` 절차의 줄 재작성 단계(0·1단계)에도 같은 순서 유지 지시를 한 줄씩 넣는다.

③ **편승 (같은 파일)**:
- `:146` 불변식 머리글 "이 두 가지가 깨지면 `step` 의 결정성이 무너진다" → 실제 개수(6개)와 각 불변식의 소비자(파서/grep 계수/스크립트 경계/진행률 분모)를 맞춘 머리글로 교체.
- `:149`(불변식 2 본문) `<td id="dz-cell-…">` 축약형 → `<td class="cell" id="dz-cell-…">` 로 정규 순서와 일치시킨다. **주의**: 같은 줄의 `<li id="dz-step-…">` 리터럴은 T25-6 이 고정하므로 유지한다(GOTCHA 2).
- `:11` 부근 `../../` 링크 4건 → 정본 깊이 `../` 로 수정(감사 MINOR — 정본 깊이는 PRP 결정으로 문서화돼 있고 테스트에 리터럴로 박혀 있다).
- `hub/bin/hub_parse.py` — `matrix_done`·`StepView.started_at` 파싱 지점 docstring 에 "현재 렌더 소비자 없음(hub_template 에 matrix 렌더 경로 부재) — 보존은 문서화된 결정" 한 줄(감사 보충 MINOR 의 처방 그대로, 코드 변경 없음).

### C-2 — 생산자↔파서 정·역방향 테스트 (결정 AR8)

**결정 AR8**: 픽스처를 늘리지 않고 두 끝을 직접 잇는 테스트 파일 1개를 신설한다 — `tests/hub/test_hub_dashboard_contract.py`. 상세 설계는 §8-1. 핵심 성질: `commands/dashboard.md` 에서 예시 줄을 **추출**해 `hub_parse` 의 **실물 패턴**에 태우므로, 문서와 파서 어느 쪽이 움직여도 함께 드리프트할 수 없다.

**T25-6 재규정**: 검사 자체(산문 리터럴 존재)는 유지하되, 주석의 "(티어 1 파서의 전제)"를 "(불변식 문구의 존재 — 파서 계약 자체는 test_hub_dashboard_contract.py 가 고정한다)"로 고친다. 산문 존재 검사와 계약 검사의 책임을 분리하는 것이며, §7 충돌 3 의 기준 적용 사례다.

### D-1 — `/dashboard` 재주입 (결정 AR9)

**결정 AR9**: `CLAUDE.md:103-104` 트리거를 "스킬 호출은 세션 최초 1회, 이후는 절차 직접 수행"으로 고친다. 규격 자체가 스킬 내용을 standing instructions 로 쓰라고 안내하고, 감사 세션이 이 운용을 실증했다.

교체 문안(초안 — T22-158 의 고정 리터럴 `디스패치·결과 수령 시점마다` 를 보존한다):

> - **전체 경로·축약 경로 작업은 진행 상황을 `/dashboard` 로 기록한다**: `Skill(dashboard)` **호출은 세션 최초 1회(`init` 시점)만** 한다 — 인자가 바뀌면 스킬 전문(~37k 토큰)이 호출마다 컨텍스트에 다시 주입되기 때문이다. 이후 단계 전환과 **서브에이전트 디스패치·결과 수령 시점마다** `step`·`log` 는 이미 로드된 절차를 **스킬 재호출 없이 직접 수행**한다(대시보드 파일을 직접 갱신). compact 이후 절차가 컨텍스트에 남아 있지 않으면 그때 1회만 재호출한다.

이하 기존 문단(갱신 주체·끄는 방법·가용성 사전 확인 금지·보고 규칙)은 그대로 둔다 — `dashboard_enabled` 참조(T23-7)와 그 문단들의 계약은 불변이다.

**동반 수정**: `commands/dashboard.md` 「호출 규약」 절 끝에 같은 규칙 1문단을 추가한다(생산자 문서가 자기 호출 비용 규칙을 스스로 앎). 「CLAUDE.md 트리거」 표는 **시점 계약**이므로 그대로 둔다 — 바뀌는 것은 시점이 아니라 수행 방식이다. T22-126 의 절 추출 앵커(`^## 호출 규약` ~ `^## CLAUDE.md 트리거`)와 토큰 4종은 추가 문단의 영향을 받지 않는다(추가만 하고 기존 문장은 건드리지 않는다).

**대안 재기각**: 슬리밍 PRP §13 에서 기각했던 서브커맨드 파일 분리(주입 −83%)를 재평가한 결과 다시 기각한다 — AR9 는 재주입 횟수를 N회→세션당 1회로 줄이므로(−83% 가 아니라 사실상 −(N−1)/N), 구조 변경 없이 더 큰 절감을 얻는다. 슬리밍 PRP 의 승인 전제였던 1회 주입 비용 모델은 규격과 달랐음을 이 PRP 가 기록한다(감사 D-1) — 해당 PRP 를 고치지는 않는다(실측 기록 보존).

**편승 (같은 파일)**: `CLAUDE.md:154` 부근 §6 인용 과대 서술(감사 MINOR·CONFIRMED — "검출이 서로 겹치지 않았다"·"메인 세션 = opus" 는 원문에 없음)을 원문 범위로 수축한다. 모델 운용 절의 다른 문장은 건드리지 않는다.

### E-1 — settings.json 쓰기 경로 I/O 테스트 (결정 AR10)

**결정 AR10**: statusline 쪽 선례(`InstallStatuslineForeignConflictIoTest`, test_hub_settings.py:238-283)와 **대칭인** I/O 테스트 클래스를 `install_hooks`/`uninstall_hooks` 에 추가한다. 프로덕션 코드는 건드리지 않는다 — 감사도 코드 결함이 아니라 검증 부재를 지적했다. 상세는 §8-3. 세 성질:

- (a) 깨진 JSON → `ok is False` + `reason == SETTINGS_PARSE_ERROR` + **파일 바이트 불변** (install·uninstall 각각)
- (b) 정상 설치 → `settings.json.bak-*` 정확히 1개 + 백업이 원본과 바이트 동일
- (c) 재호출 멱등 → `installed == []` + **백업이 새로 생기지 않음** (실측: `install_hooks` 는 `installed` 가 비면 `_write_settings_atomically` 를 부르지 않으므로 이 성질은 현행 코드에서 성립한다 — 테스트가 그것을 고정한다)

### F-3 — 미배포 에이전트 로스터 (결정 AR11)

**결정 AR11**: `rules/common/agents.md` 의 로스터를 **배포 4종으로 교체**한다. "상류 번들 전제" 디스클레이머만 붙이는 대안은 기각 — 공개 배포물 전제에서 "Located in `~/.claude/agents/`" 단정 + "No user prompt needed" 지시의 조합이 순수 클론 사용자에게 실행 불가 지시로 남기 때문이다(감사 §2 F-3 의 결론 그대로).

- 로스터 표를 `design-architect`·`implementer`·`code-reviewer`·`Explore` 4종으로 교체하고, 각 행을 CLAUDE.md 워크플로우(설계→구현→검수·탐색)와 정합하게 적는다.
- "Immediate Agent Usage" 절(:22-26)을 4종 기준으로 재작성한다(예: 전체 경로 분류 → design-architect, 코드 작성 후 → code-reviewer).
- 절 서두에 조건부 문장 1줄: "상류 ECC 번들을 함께 설치한 환경이라면 이 외의 에이전트(67종)가 있을 수 있다 — 이 표는 **이 저장소가 배포하는 것**만 적는다."
- "Parallel Task Execution"·"Delegation Completion Contract"·"Multi-Perspective Analysis" 절은 에이전트명 비의존이므로 유지한다.

**참조 파일 정리 표** (각 파일에서 미배포 에이전트 지목을 제거·대체):

| 파일:행 | 현재 | 처리 |
|---|---|---|
| `rules/common/testing.md:22·29` | "Use **tdd-guide** agent" | 에이전트 지목 삭제, "TDD 절차를 직접 따른다(implementer 가 구현 단계에서 수행)"로 재서술 |
| `rules/common/security.md:26` | "Use **security-reviewer** agent" | "code-reviewer 에게 보안 렌즈를 지정해 검수 위임(민감 변경은 opus 승격 — CLAUDE.md 모델 운용)"으로 대체 |
| `rules/common/performance.md:138` | "Use **build-error-resolver** agent" | 에이전트 지목 삭제, 일반 절차 서술로 |
| `rules/common/code-review.md:66-71` | 에이전트 표 6종 | 배포 1종(code-reviewer) + "언어별 리뷰어는 상류 ECC 번들 설치 시" 조건부 1줄로 축약 |
| `rules/common/development-workflow.md:18·24` | planner·tdd-guide | design-architect·implementer 로 대체(워크플로우 단계 의미 보존) |
| `rules/typescript/testing.md:18` | tdd-guide | testing.md 와 동일 처방 |
| `rules/react/security.md:179-180` | security-reviewer·react-reviewer | security.md 와 동일 처방. **서술 정정**: react-reviewer 는 유령이 아니라 상류 실재(부분 설치 문제) — 조건부 표기로 |
| `rules/react-native/testing.md:52` | tdd-guide | 동일 처방 |

**재발 방지(F-6 이빨 ②)** — `tests/run.sh` 신설 검사: 미배포 에이전트 13종(`planner`·`architect`·`tdd-guide`·`security-reviewer`·`build-error-resolver`·`e2e-runner`·`refactor-cleaner`·`doc-updater`·`rust-reviewer`·`python-reviewer`·`go-reviewer`·`typescript-reviewer`·`react-reviewer`)이 **이름의 어휘 경계 매칭**(`(?<![\w-])이름(?![\w-])`, 대소문자 무시 — 하이픈·단어문자를 모두 경계로 취급)으로 `rules/` 전체에 0건임을 단정한다. 형태(볼드·표 행·백틱·평문) 구분 없이 이름이 단독 토큰으로 나타나는 모든 경우를 잡으면서, 하이픈·단어문자 경계 검사 덕분에 `design-architect` 내부의 `architect`, `architecture` 내부의 `architect` 를 구조적으로 피한다 — **검수 3회차 실측으로 정정**: 2회차의 "볼드·표 행·'Use `이름`' 백틱" 세 패턴 한정은 실제 표기 12형태 중 4개만 잡았다(백틱형이라도 "Use " 접두가 없으면 놓쳤고, 평문형·문장 내장 볼드형도 마찬가지였다 — 이 저장소가 이번 회차에 스스로 채택한 "Delegate to **code-reviewer** with a ... lens" 어투가 그 미검출 계열과 같은 모양이었다). 이름 경계 매칭은 이 12형태 전부를 실측으로 검출한다. **R1 4회차 정정(사용자 승인 A 안 — 예외 장치 제거)** — 3회차가 넣었던 `upstream ECC bundle` 줄 예외는 고지 산문 2곳(`rules/common/code-review.md:68`·`rules/react/security.md:180`)이 미배포 에이전트 이름을 직접 나열했기 때문에만 필요했다. 4회차는 예외를 추가하는 대신 그 두 문장에서 이름 자체를 삭제했다(문장이 전하는 "이 리뷰어들은 상류 번들에만 있다"는 의미는 보존) — 그래서 이 검사는 **예외 0개**다. 잔존 위험은 완전성 주장이 아니다 — 이름이 그 리터럴 그대로 경계 조건을 만족하며 나타나지 않으면 이 검사는 걸지 못한다는 한계가 실측한 범위에서 확인된 것이다. 그 범위에서 확인된 회피 경로는 표기 변형·유니코드·인코딩 치환(비하이픈 하이픈류·제로폭·소프트 하이픈·전각·HTML 엔티티)·마크업 분절·단어문자·하이픈 인접 결합·줄바꿈 분리 등이며(비망라 예시, 상세는 `tests/run.sh` T29 주석), 전수 증명은 아니다.

### F-4 — 미배포 skills·MCP·gh 를 mandatory 요구 (결정 AR12)

**결정 AR12**: `development-workflow.md:9` 의 `_(mandatory before any new implementation)_` 를 조건부로 완화한다:

> 0. **Research & Reuse** _(recommended; steps requiring tools not installed in your environment — `gh`, Context7/Exa MCP — are skipped, not blocked)_

이어지는 불릿의 도구 지목은 유지하되 "이 저장소는 이 도구들을 배포·설정하지 않는다 — 선택 사항"임을 절 서두 한 줄로 명시한다. `rules/react/testing.md:186` 의 `../../skills/e2e-testing/SKILL.md` 상대 링크는 어느 설치 루트에서도 배포물이 없으므로(영구 깨진 링크) 링크를 걷어내고, 상류 ECC 저장소 URL + 경로를 산문으로 표기한다(AR2 편승의 :194 와 같은 처방). **감사 §5 의 폐기 판정과의 정합**: `rules/README.md:62` 의 skills 개념 대조는 폐기된 오탐이므로 건드리지 않는다 — 처방 대상은 "설치 경로 상대 링크"와 "mandatory 단정" 두 가지뿐이다.

**편승 (같은 파일)**: `rules/react/testing.md:18` — deprecate 된 CRA 를 현행 선택지와 같은 층에 두는 서술(감사 INFO)을 "legacy — 신규 프로젝트에 선택하지 않는다"로 강등 표기.

### F-5 — python3 3.10+ 요구 표기와 설치 가드 (결정 AR13)

**결정 AR13**:
- `hub/README.md` 에 「요구사항」 절 신설(「설치」 절 바로 앞): `python3` **3.10 이상** — 근거(PEP 604 `X | None` 어노테이션이 dataclass 클래스 본문에서 즉시 평가, `from __future__ import annotations` 미사용 — 14모듈 82곳), macOS Keychain 의존은 기존 옵트인 서술 유지.
- 루트 `README.md` 「요구사항」(:336-340) 에 한 줄 추가: "- (허브 사용 시) `python3` 3.10 이상 — 루트 설치(`install.sh`)에는 불필요".
- `hub/install.sh` 도입부에 가드 함수 신설, **install 경로에서만** 호출한다:

  ```bash
  readonly REQUIRED_PYTHON_MAJOR=3
  readonly REQUIRED_PYTHON_MINOR=10
  require_python() {
    if ! command -v python3 >/dev/null 2>&1; then
      log_error "python3 이 필요합니다 (${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 이상)"; return 1
    fi
    if ! python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (${REQUIRED_PYTHON_MAJOR},${REQUIRED_PYTHON_MINOR}) else 1)"; then
      log_error "python3 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ 필요 — 현재: $(python3 -V 2>&1)"; return 1
    fi
  }
  ```

  uninstall 경로에는 걸지 않는다 — 구버전 파이썬 머신에서 제거까지 막을 이유가 없다(uninstall-hooks 의 파이썬 실패는 기존 경로가 처리한다).

**편승 (같은 파일 `hub/install.sh`)**:
- `:95-103` `verify_installed_file_count` — 대상 디렉토리 **총량 계수**를 폐기하고 **소스 파일명 기반 존재 확인**으로 교체(§7 충돌 1 의 해소): `find "$SOURCE_BIN_DIR" -maxdepth 1 -type f` 각각에 대해 `$TARGET_BIN_DIR/$(basename …)` 존재를 확인. 남의 파일이 대상에 공존해도 실패하지 않는다 — 소유권 원칙("이 스크립트는 hub/bin 이 배포하는 파일만 관리한다", hub/install.sh:7)과 정합해진다. `HUB_FILE_COUNT` 상수와 **소스측** 계수 대조(tests/run.sh:2617 기존 검사)는 유지한다.
- `:203-215` main 의 uninstall 분기 — `--uninstall --dry-run` 조합이 dry-run 을 조용히 무시하는 결함(감사 MINOR·CONFIRMED): uninstall 분기에서 `dry_run` 이 참이면 제거 계획만 출력하고 반환하도록 분기 추가.

**편승 (README·coding-harness.md — §7 충돌 4 의 해소)**:
- `README.md:280` "배포 대상 6개" → 10개(같은 문서 :113·:312 와 정합).
- `docs/prps/coding-harness.md` 의 79개 서술(:54·:106 등) 옆에 각주 1줄: "79 는 rev4(큐레이션 전) 시점 수 — 커밋 5f9552f 이후 배포는 37개. 이 문서는 실측 기록이라 본문을 소급 수정하지 않는다."
- `README.md:122` 모델 정책 요약이 fable 조건부 승격 이전 서술인 문제(감사 MINOR·CONFIRMED) — 현행 CLAUDE.md 모델 운용 절과 정합하게 한 문단 갱신.

**신설 테스트**: `tests/run.sh` 에 `RULES_FILE_COUNT`(37)·`AGENTS_FILE_COUNT`(4)와 실제 소스 파일 수의 파리티 검사(COMMANDS·HUB 에는 이미 있는 형태를 복제 — install.sh:12 INFO 의 처방).


**R2 구현 시 실측으로 정정한 것 (사후 기록, 2026-09-02)** — 이 절의 문안 두 곳을 구현자가 실측 근거로 바꿨고 검수(렌즈 H)가 「PRP 문안을 그대로 옮겼다면 부정확했을 것」으로 판정했다. 결과물이 아니라 절차를 남기는 기록이다.
1. **근거 서술의 범위** — 이 절은 3.10 필요 근거를 「dataclass 클래스 본문에서 즉시 평가」로 적었으나, 실측하니 `X | None` 은 대부분 **함수 파라미터·반환 타입 어노테이션**이고 dataclass 필드는 소수였다(`hub_parse.py` 2건). `hub/README.md` 는 「정의 시점에 즉시 평가」로 일반화했다.
2. **개수를 문서에 넣지 않았다** — 이 절의 「82곳」은 재현되지 않았다. 측정 기준마다 값이 갈린다(구현자 실측 107·49, 검수자 실측 100). 코드가 바뀔 때마다 낡는 값이라 `hub/README.md` 에는 메커니즘만 적었다. **모듈 수 14 는 실측과 일치했다.**
3. **`coding-harness.md` 각주** — 이 절은 「37개」만 지시했으나 재동기화 직후(`5f9552f`)가 37, 현재가 42 이므로 두 시점을 함께 적었다. 「37개」만 쓰면 그 각주가 곧 낡는다.
### F-1 — LICENSE (결정 AR14)

**결정 AR14**: **MIT 를 채택할 것을 권고**한다(승인 항목 1). 근거: (i) 상류가 MIT 라 파생 43개를 포함한 저장소 전체를 단일 조항으로 덮을 수 있고 고지 의무가 단일화된다, (ii) README 의 clone 안내·공개 origin·`harness-update` 원격 pull 과 정합한다, (iii) 감사 F-1 의 선택지 (a) 에 해당한다. 산출물:

- 루트 `LICENSE` 신설 — MIT 전문 + `Copyright (c) 2026 pascal`. **(승인 완료 2026-08-28: 저작권자 표기 = `pascal`)**
- `README.md:342-344` 「## 라이선스」 절 재작성: "MIT — [LICENSE](LICENSE) 참조. 상류 파생·제3자 고지는 [NOTICE.md](NOTICE.md)." + 기존 "사용자 개인 워크플로우 패키징" 문장은 라이선스 서술이 아니므로 저장소 성격 설명으로 남기되 라이선스 문장과 분리한다.

이 항목은 더 이상 사용자 입력에 게이트되지 않는다 — 상류(MIT)가 확정돼 "모르는 원 라이선스 위에 허용형을 붙이는" 실패 모드가 소멸했다. **2026-08-28 사용자 승인: MIT 채택 + 저작권자 표기 `pascal`.** R3 착수를 막는 조건은 해소됐다.

### F-2 — 상류 출처 고지 = MIT 조건 이행 (결정 AR15)

**결정 AR15**: 루트 `NOTICE.md` 신설. 절 구성:

1. **이 저장소의 라이선스** — MIT, `LICENSE` 참조 (한 줄).
2. **상류: Everything Claude Code (ECC)** — URL(`https://github.com/affaan-m/everything-claude-code`) · `Copyright (c) 2026 Affaan Mustafa` · MIT. **상류 MIT 의 저작권 고지와 허가 고지 전문을 이 절에 포함한다** — 이것이 MIT 조건의 이행이며, "선택"이 아님을 절 서두에 명시한다.
3. **파생 파일 목록** — 43개를 그룹으로: `rules/` 36(디렉토리별 계수), `agents/code-reviewer.md`(**"상류 기반 재작성"으로 표기** — 상류 대비 386줄 차이로 실질 재작성이지만 상류 파일에서 출발했으므로 파생 고지 대상에 남긴다. "파생" 단독 표기는 기여도를 오도하고, 목록 제외는 고지 의무를 흐린다 — 중간 표기가 정확하다), `commands/` 6종 열거.
4. **이 저장소가 한 변경** — 79→37 큐레이션 · 한국어화 · 워크플로우 재구성 · 로컬 패치(아래 5절) 각 한 줄.
5. **로컬 패치된 벤더링 파일 (정본 목록)** — F-6 의 문서부. §4 AR16 참조.
6. **제3자 고지** — lucide: ISC, 저작권 고지 문구를 lucide 저장소 LICENSE 원문에서 옮겨 적는다(구현 시 확인 — `hub-panel-polish-and-icons.md:275` 가 스스로 세운 조건 "저작권 고지 유지"의 이행이며, 현재 `hub/bin/hub_template.html:60-62` 의 출처 참조만으로는 미달이라는 감사 판정의 해소).

`docs/prps/coding-harness.md` 의 79개 각주는 R2 에서 처리한다(같은 사실의 표면이 두 곳이라 단계가 갈리지만, R3 의 NOTICE 4절이 정본이 된다).

### F-6 (신규 MAJOR) — 로컬 패치 추적 장치 (결정 AR16)

**문제**: 로컬 수정된 벤더링 파일이 이미 6개 있고 이번 PRP 가 최소 10개를 더한다(A-1·A-2 의 web/hooks.md·react/patterns.md, F-3 의 8개 파일). 그 목록이 저장소 어디에도 없는 채로 재동기화 선례(`5f9552f` "ECC 최신 반영")가 존재한다 — **다음 재동기화가 이번 패치를 조용히 되돌려 결함을 부활시킨다.** 게다가 지금도 `agents.md` 가 상류보다 1줄(`harmonyos-app-resolver`) 뒤처져 있어 재동기화 압력은 실재한다.

**결정 AR16**: 3층 장치. 새 파일 포맷·도구를 만들지 않는다(YAGNI) — 문서 1절 + 기존 테스트 하네스의 검사들로 해결한다.

1. **정본 목록** — `NOTICE.md` 5절에 로컬 패치된 벤더링 파일을 표로 유지한다: `파일 | 패치 요지 | 근거(PRP/감사 항목)`. 이번 PRP 완료 시점 기준 수록 대상: 기존 6(performance.md·code-reviewer.md·rules/README.md·code-review.md·coding-style.md·git-workflow.md) + 신규(web/hooks.md, react/patterns.md, agents.md, testing.md, security.md, code-review.md(추가 패치), development-workflow.md, typescript/testing.md, react/security.md, react/testing.md, react-native/testing.md). 구현자는 커밋 직전 `git diff --name-only` 로 목록을 실측 대조한다.
2. **재동기화 규칙** — 같은 절에 절차 규칙을 명문화한다: "ECC 재동기화 시 이 목록의 파일은 통째로 덮어쓰지 않는다. 파일별로 상류 diff 를 검토해 로컬 패치를 보존·재적용하고, 완료 후 `bash tests/run.sh` 로 패치 존재 검사를 통과시킨다."
3. **테스트 이빨** — Q4·R1·R3 의 신설 run.sh 검사가 패치의 **내용 존재** 자체를 고정한다: 훅 JSON 스키마 검사(AR1)·부재단정 가드(AR2)·effort 앵커(AR3)·에이전트 denylist(AR11)·NOTICE/LICENSE 존재+앵커(R3: `NOTICE.md` 존재 + ECC URL 토큰 + `Affaan Mustafa` 토큰 + lucide 토큰, `LICENSE` 존재 + `MIT` 토큰). 재동기화가 패치를 되돌리면 **목록을 안 봤더라도** 테스트가 실패한다 — 문서(1·2)는 사람 절차를, 테스트(3)는 기계 강제를 맡는다.

**배치**: 이빨은 Q4·R1 에 동반(코디네이터 지시 — A-1·A-2·F-3 단계의 동반 항목), 문서부는 R3. Q4·R1 커밋 시점부터 재동기화 부활은 즉시 검출된다.

---

## 5. 데이터 모델 · 공개 인터페이스 변경 요약

```
데이터 모델 변경 없음: HubConfig · UsageApiPollState · Tier1Snapshot · FailureReason Literal
                        (B-1 의 "internal_error" 는 소비 측 문자열 상수 — Literal 에 넣지 않는다)
함수 시그니처 변경 없음: _run_usage_api_poll_cycle(now_ms: int, poll_state, config) -> UsageApiPollState 유지
신설 (hub_server.py):
  USAGE_API_UNEXPECTED_ERROR_REASON: str = "internal_error"
  def _usage_api_poll_loop(config: hub_model.HubConfig, stop_event: threading.Event) -> None
신설 (hub_collect.py): MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS: int, MIN_USAGE_API_POLL_INTERVAL_SECONDS: int (AR6)
신설 (hub/install.sh): require_python(), verify_installed_file_count → 소스 기반 검사로 대체
삭제: _maintenance_loop 본문의 폴링 호출 (AR5 — T25-122 재작성과 동기)
```

문서 계약 변경: `commands/dashboard.md` 에 「정규 속성 순서」 명문화(AR7 — 실질은 기존 파서 계약의 문서화이지 계약 변경이 아니다), `CLAUDE.md` 트리거의 수행 방식 변경(AR9 — 시점 계약은 불변).

---

## 6. 기존 테스트 파손 분석 (실측)

`tests/run.sh`(5,391줄, 한글 산문 grep 어서션 99건)에 대해, 이번 편집이 건드리는 문장마다 어서션을 `grep -n` 으로 실측 대조했다. **run.sh 가 내용을 검사하는 파일 변수 전수 추출 결과가 근거다**(§0 마지막 행).

| 편집 항목 | 건드리는 문장/파일 | 걸리는 어서션 (실측) | 처리 |
|---|---|---|---|
| A-1 `rules/web/hooks.md` | JSON 6블록 전체 | **0건** — run.sh 는 이 파일을 열지 않는다 | 파손 없음. 신설 검사만(AR1) |
| A-2 `rules/react/patterns.md` | RN 절·Skill Reference | **0건** | 파손 없음. 신설 가드만(AR2) |
| A-3 `rules/common/performance.md` | effort 절 | **0건** (`grep -n 'performance\.md\|effort'` 매칭은 hub/README 대상 T25-152 뿐) | 파손 없음. 신설 앵커만(AR3) |
| B-2 `hub_server.py` 폴링 이동 | `_maintenance_loop` 본문 | **T25-122 (run.sh:4650-4670) 파손 확정** — "maintenance_loop 본문에 `_run_usage_api_poll_cycle(` 호출이 있어야 한다"를 명시 검사 | **재작성**(계약 강화): ① maintenance 본문에 `_run_usage_api_poll_cycle`·`hub_usage_fetch` **부재** — **추출 앵커도 함께 교체한다**: `/^def _maintenance_loop(/,/^def _usage_api_poll_loop(/` (기존 종료 경계 `run_server` 를 그대로 두면 추출 범위가 새 함수 본문까지 삼켜 이 검사가 확정 실패한다 — 검토 세션이 가상 삽입으로 실측) ② 신설 `_usage_api_poll_loop` 본문에 호출 **존재** — 앵커 `/^def _usage_api_poll_loop(/,/^def run_server(/` ③ 요청 경로 부재(기존 유지) ④ `run_server` 본문에 `target=_usage_api_poll_loop` 존재 — `run_server` 는 이 모듈의 **마지막 함수**라(실측) 종료 앵커가 없으므로 `sed -n '/^def run_server(/,$p'` 로 파일 끝까지 추출하고, 기존 T25-122 의 「추출 결과가 빈 문자열이면 `record_failure`」 가드를 ④에도 적용한다(그 가드가 앵커 파손을 잡는 유일한 장치다). 함수 배치 순서(GOTCHA 4)가 ①·② 앵커의 전제 |
| C-1 `dashboard.md:116-117` 교체 | 소비자 경고 2줄 | **0건** — "티어를 강등"·"1줄 1개" 를 고정하는 어서션 없음(실측). T25-6 은 별도 리터럴만 검사 | 파손 없음 |
| C-1 편승 `:149` td 축약형 | 불변식 2 본문 | **T25-6 (run.sh:2664-2670)** — `<li id="dz-step-…">`·`<li id="dz-impl-…">` 리터럴 존재 검사 | 두 리터럴을 **보존**하는 편집으로 설계했다(td 부분만 교체). 파손 없음 + 주석 재규정(AR8) |
| D-1 `CLAUDE.md:103-104` | 트리거 문장 | **T22-158 (run.sh:2461-2465)** — 리터럴 `디스패치·결과 수령 시점마다` | 신 문안이 리터럴을 **보존**한다(AR9 문안에 포함). 파손 없음 |
| D-1 `dashboard.md` 호출 규약 문단 추가 | 호출 규약 절 | **T22-126 (run.sh:2136-2150)** — 절 추출 앵커(`^## 호출 규약`~`^## CLAUDE.md 트리거`) + 토큰 4종. **T22-127** — 리터럴 2종 | 추가만 하고 기존 문장·헤더 불변 → 파손 없음 |
| D-1 관련 문서 정합 | `dashboard_enabled` 3문서 참조 | **T23-7 (run.sh:2531-2532)** | 참조 불변 → 파손 없음 |
| F-3 `rules/common/agents.md` 외 | 로스터·참조 8파일 | **0건** — run.sh 가 여는 rules 파일은 coding-style 3종(650·689·702행, 상대 링크 검사)뿐이고 이번 편집 대상이 아니다 | 파손 없음. denylist 신설만(AR11) |
| F-5 `hub/install.sh` 가드·검증 교체 | install·uninstall 경로 | hub/install.sh 를 **실행**하는 T군(run.sh:2636, 2935 등 샌드박스 설치·제거) + `HUB_FILE_COUNT` 소스측 파리티(run.sh:2617) | 가드는 python3.10+ 머신에서 무해(테스트 환경 3.11+). 소스측 파리티는 유지 대상이라 무영향. **총량 계수 함수 교체 후 전체 T군 1회 완주로 확인**(교체 함수명을 검사하는 어서션은 실측 0건) |
| R2 `README.md` 편집 | :280·:122·:340 | run.sh 의 readme_file 검사는 dashboard/hub 연동 절 대상 — 이번 행 **0건** (구현 시 `grep -n 'README' tests/run.sh` 재확인 지시) | 파손 없음 예상 + 재확인 |
| R3 `README.md` 라이선스 절 | :342-344 | **0건** | 파손 없음 |

### §6 개정 1 — T25-122 의 본문 추출을 `sed` 앵커에서 `ast` 추출로 교체한다 (검수 R1 지시, 2026-08-28)

**번복 대상**: 위 표의 T25-122 행이 지정한 `sed -n '/^def X(/,/^def Y(/p'` 방식 3개.

**번복 사유** — Q1 검수(opus)가 양방향으로 실측했다.

- **오탐**: `_maintenance_loop` docstring 에 설명용 토큰 `hub_usage_fetch.py` 한 단어를 재삽입하면(코드 변경 0) 검사 ① 이 FAIL 한다. `sed` 추출 본문에 docstring 이 포함되기 때문이다. 그 결과 **PRP §4 B-2 가 그 docstring 에 남기라고 지시한 근거를 남길 수 없다** — 테스트가 문서를 지시하는 상태다.
- **미탐(더 나쁘다)**: `_usage_api_poll_loop` docstring 에 `_run_usage_api_poll_cycle(` 을 언급하면서 **본문의 실제 호출을 삭제**하면 검사 ② 가 **여전히 통과**한다. 같은 과대 추출 범위가 존재 방향 검사를 조용히 무력화한다.

즉 §7 충돌 3 의 기준("어서션은 산문 전문이 아니라 기계 계약 토큰을 고정한다")에서 **토큰 선택은 옳았고 추출 범위가 틀렸다.**

**개정 내용**: `hub_server.py` 를 `ast` 로 파싱해 이름으로 `FunctionDef` 를 찾고, **docstring 을 제거한 본문만** `ast.unparse` 로 뽑아 grep 대상으로 삼는다. `tests/run.sh` 는 이미 python3 히어독을 쓰므로(T25-121 의 `PYEOF` 선례) 새 의존성이 없다. 이 한 수로 오탐과 미탐이 **동시에** 사라지고, **GOTCHA 4 의 함수 배치 의존성도 제거된다**(이름으로 찾으므로 배치가 자유롭다).

`sed` 를 유지하는 저비용 변형(`grep -v '^\s*#'` + `"""` 블록 필터)은 ① 만 고치고 ② 의 공허 통과를 남기므로 **채택하지 않는다** — 물지 않는 검증기를 남기는 것은 이 PRP 가 F-6·C-2 로 고치려는 바로 그 실패 모드다.

**동반 작업**: 추출이 docstring 을 보지 않게 된 뒤 `_maintenance_loop` docstring 의 `hub_usage_fetch.py` 근거를 §4 B-2 지시대로 **복원**한다.

**GOTCHA 4 의 지위**: 함수 배치 권고(`_maintenance_loop` → `_usage_api_poll_loop` → `run_server`)는 **가독성 관례로만 유지**한다 — 더 이상 테스트의 전제가 아니다.

**전체 관측**: 이번 편집과 99건 산문 어서션의 교차는 T22-158·T25-6·T22-126/127·T25-122·T23-7 로 좁혀지고, 그중 실제 파손은 **T25-122 하나**다(의도된 재작성). 나머지는 리터럴 보존 설계로 회피했다 — 이 보존은 우연이 아니라 §7 충돌 3 의 기준("계약 토큰은 보존, 산문은 자유")을 편집 문안에 적용한 결과다.

---

## 6-A. §6 방법론의 사각지대 (Q4 검수에서 발견 — Q5·R1 착수 전 필독)

**§6 의 판정 방법이 원리적으로 볼 수 없는 어서션 종류가 있다.** §6 은 "이번 편집이 건드리는 문장마다 어서션을 `grep -n` 으로 실측 대조"했다. 그 방법은 **특정 문장을 고정하는** 어서션만 찾는다. **글롭으로 파일 전체를 모아 바이트 합을 상수와 비교하는 어서션(T26)은 어떤 문장도 고정하지 않으므로 이 방법에 절대 걸리지 않는다.**

실제로 틀렸다 — §6 표는 A-3(`rules/common/performance.md`) 편집을 **「0건 파손」**으로 판정했으나, T26 이 그 파일을 `rules/common/*.md` 글롭으로 합산한다. A-3 이 +494B(8514 → 9008B, 실측) 늘리자 T26-2·T26-3 이 깨졌고, `ALWAYS_ON_CONTEXT_BUDGET_BYTES`(50314 → 50808)와 `README.md` 의 「실측 N B」 선언 **2곳**을 함께 올려야 통과했다. 검수자가 `README.md` 만 되돌려 재현했다 — T26-2 2건 + T26-3 1건 동시 실패.

**이 사각지대가 남은 §6 행 (전수 확인 결과)**

| 단계 | 여는 파일 | T26 글롭 대상인가 | §6 의 판정 |
|---|---|---|---|
| **Q5** | `CLAUDE.md` | **그렇다** (T26 합산 대상) | D-1 행이 T22-158 만 검사, **T26 언급 없음** |
| **R1** | `rules/common/agents.md`·`testing.md`·`security.md`·`performance.md`·`code-review.md`·`development-workflow.md` | **6개 전부 그렇다** | F-3 행이 「0건 — run.sh 가 여는 rules 파일은 coding-style 3종뿐」 |
| R2 | `README.md` | 선언 2곳이 T26-2·T26-3 의 대조 대상 | 「0건 예상 + 재확인」 |

**R1 의 위험이 가장 크다** — 에이전트 로스터 표 전체 교체를 포함하므로 A-3(494B)보다 훨씬 큰 바이트 델타가 예상된다.

**따라서 Q5·R1·R2 의 구현 지시에는 다음을 반드시 넣는다.**

1. 편집 **전** `bash tests/run.sh` 로 T26 의 현재 실측치를 기록한다.
2. 편집 **후** 실측치를 다시 재고, 상한을 넘으면 `ALWAYS_ON_CONTEXT_BUDGET_BYTES` 와 `README.md` 선언 2곳을 **같은 커밋에서** 동기화한다(T26 자신의 주석이 이 절차를 예정해 뒀다).
3. **바이트를 늘리는 편집은 최소여야 한다** — 이 저장소는 상시 컨텍스트 예산을 자기 병목으로 선언했고, 상시 로드 파일의 증가는 **모든 프로젝트의 모든 세션에 과금**된다. 사실 정정에 예산을 쓰는 것은 정당하나 낭비 없이 써야 한다(Q4 검수 MEDIUM 참조 — A-3 문안의 41%가 낭비였다).
4. **§6 의 「0건 파손」 판정을 T26 에 대한 보증으로 읽지 마라.** 그 판정은 "산문 리터럴 어서션은 안 깨진다"만 보증한다.

---

## 6-B. Q4 검수 1회차 (FAIL, 2026-08-29)

**FAIL** — CRITICAL 0 · **HIGH 1** · MEDIUM 1 · LOW 2. 검증 4종은 전부 통과했다(유닛 514 유지 · `run.sh` **27/27**, T28 신설로 26 → 27).

- **HIGH — `rules/react/patterns.md:82` 가 존재하지 않는 카브아웃을 있다고 단정한다.** 새 문장이 "hand-written Error Boundary class 는 `coding-style.md` 의 Class Components 규칙이 **이미 카브아웃한** 예외"라고 주장하지만, `rules/react/coding-style.md` 의 「## Class Components」 절 전문은 *"Forbidden in new code. Convert legacy class components to function components when touching them for non-trivial changes."* 뿐이다. `error boundary`·`exception`·`carve` 류 단어가 그 파일 전체에 **0건**이다. **Q4 의 목적이 rules 의 사실 오류 제거인데 그 작업 중에 새 사실 오류를 심은 것**이므로 되돌려 고친다. 이 문면은 **§4 AR2 편승 지시를 거의 그대로 옮긴 것** — 설계 단계의 전제 오류다. **수정 방향(b)**: `patterns.md:82` 의 "already carves out" 을 낮춰 존재하지 않는 내용을 단정하지 않게 한다(범위 5파일을 넘지 않는다). 방향 (a)(`coding-style.md` 에 예외를 실제로 추가)는 범위 이탈이라 채택하지 않는다.
- **MEDIUM — A-3 문안이 최소가 아니다.** 검수자가 같은 사실을 **815B**(현재 1016B, −201B·−20%)로 재작성 가능함을 실측했다. 증가분 494B 중 **약 201B(41%)가 낭비**다. 문안을 줄이면 T26 상한과 README 선언 2곳을 **낮은 값으로 재동기화**한다 — 래칫을 조이는 방향이라 항상 안전하고, Q5·R1 의 예산 압력을 정직하게 만든다.
- **LOW 2건** — `test_rules_vendor_patch_guards`(114줄)가 50줄 가이드를 넘지만 파이썬 히어독 임베딩 관례이고 §2 비목표가 `tests/run.sh` 구조를 `tests-hardening` 으로 이관했다 / GOTCHA 5 순서 이탈은 검수자의 독립 재검증(`json.loads` + **실제 node 실행으로 stdin 파싱·spawnSync 배열 인자·800줄 가드 exit 2 확인**)으로 충분히 대체됐다.

**통과 판정된 것**: A-1(6블록 3단 스키마 전환 + `$FILE_PATH` 0건 — 검수자가 실제 커맨드를 mock stdin 으로 **실행**해 경로 추출·셸 인젝션 부재·가드 동작 확인) · A-3(공식 문서 원문 독립 재확인, `/model` 슬라이더 미단정 확인 — **감사 초안보다 정확해졌다**: `max` 는 `CLAUDE_CODE_EFFORT_LEVEL` 예외, `ultracode` 는 effort 레벨이 아니라 자체 지속 키를 가진 설정) · T28 3종(전부 물고, 무해한 어순 다듬기에는 GREEN 유지) · `README.md` 터치(T26 설계가 강제하는 기계적 결합이므로 범위 위반 아님) · 예산 래칫 상향의 정당성(델타가 A-3 하나에 정확히 귀속).

**INFO 수용** — T28-2 의 `not yet present` 블랭킷 금지는 문구가 사실인 경우까지 막지만, §4 AR2 가 "YAGNI — 정당한 용례가 생기면 그때 개정"으로 명시 승인한 설계다.

---

## 6-C. Q4 검수 2회차 (PASS, 2026-08-29)

**PASS** — CRITICAL 0 · HIGH 0 · MEDIUM 0 · LOW 1(정보성). 1회차 HIGH·MEDIUM **둘 다 해소**. 검증 유닛 514 · `run.sh` 27/27.

- **HIGH 해소** — `patterns.md:82` 가 이제 `coding-style.md:97` 의 실제 문장(*"Forbidden in new code…"*)만 괄호로 인용하고, 예외 판단의 주체를 `patterns.md` 자신으로 옮겼다. `coding-style.md` 는 무변경(방향 (a) 기각 유지).
- **MEDIUM 해소** — `performance.md` 9,008 → **8,813B**(−195B). 상시 컨텍스트 **50,613B**, 순증 +299B. 검수자가 공식 문서를 직접 페치해 **문장 단위로** 4가지 사실을 대조했고 전부 정확히 보존됐다 — 특히 **`/model` 슬라이더 미단정**(GOTCHA 10)과 `--effort` 플래그·비대화형 `-p` `/effort` 의 구분이 압축 표기 안에서 살아 있음을 확인했다. 남은 +299B 는 정당(더 줄일 여지는 미미).
- T26 3곳(상수 `tests/run.sh` + `README.md` 선언 2곳) = **50613**. 정확히 그 값일 때만 27/27.

**검수자 LOW 1건은 메인 세션이 기각한다** — "구현자의 T26 뮤테이션 조합 보고가 실측과 다르다"는 지적인데, **두 사람이 서로 다른 대상을 변형했다.** 구현자는 `run.sh` 의 **상한 상수**를, 검수자는 **`performance.md` 파일 내용**을 ±1B 했다. 발동 검사가 다른 것이 정상이다: 상수 낮춤 → 실측>예산 → T26-1 / 상수 높임 → 선언≠상수 → T26-2·3 / 파일 +1B → T26-1·2 / 파일 −1B → 선언≠실측 → T26-2. **넷 다 정합하므로 보고 부정확이 아니라 비교 대상의 착오다.** 후속으로 이관하지 않는다.

---

## 6-D. Q5 검수 (1회차 PASS, 2026-08-29) — 품질 트랙 종료

**PASS** — CRITICAL 0 · HIGH 0 · MEDIUM 1 · LOW 1. 검증 유닛 514 · `run.sh` 27/27. **Q1~Q5 로 품질 트랙(A~E)이 끝났다.**

통과 판정: D-1 신 문안(T22-158 리터럴 보존, tier0 가 머지로 넣은 새 내용 무훼손) · 편승 1 §6 인용 수축(세 방향 전부 통과 — 원문 대조·잔여 과장 없음·정책 근거 자체 성립) · 편승 2 불변식 1 재분류(검수자가 `hub_parse` 직접 import 해 재현) · T26 = **51195** 정확(4콤보 재현) · `dashboard.md` 동반 수정이 T22-126/127·T22-155·T23-7 무훼손.

**§6 인용에 관한 부수 소득**: 검수자가 §6 이 기술한 사건(심판이 메인 세션의 오판을 **교정**함)이 원래 인용의 주장("서로 겹치지 않는 독립 검출")과 **사실상 반대 방향**임을 지적했다. 과대 인용이 아니라 방향이 뒤집힌 인용이었다.

### 분리 작업(`claude-md-split`)으로 이관하는 2건

지금 고치지 않는다 — **분리 3단계가 루트 `CLAUDE.md` 를 통째로 교체하고 D-1 문단을 `rules/workflow/role-separation.md` 로 옮긴다.** 옮기면서 다듬는 것이 맞고, T26 동기화도 한 번으로 끝난다.

- **MEDIUM → 분리 1단계(이관 시 다듬기)**: 검수자가 대안 문안을 실측했다 — D-1 문단 +380B → **+247B 가능(−133B, 35%)**, 편승 1 문단 +202B → **+96B 가능(−106B, 52%)**. 합계 582B 중 **239B(41%)가 절감 가능**하다. **Q4 의 A-3 에서 잡은 비율(41%)과 거의 동일** — 같은 결함이 반복됐다. 상시 로드 파일이므로 낭비는 모든 프로젝트의 모든 세션에 누적 과금된다. **이관 시 반드시 다듬고, 줄어든 만큼 T26 상한을 낮춰 래칫을 조인다.**
- **LOW → 분리 4단계(`dashboard.md` 제목 개정과 함께)**: 불변식 1 재분류 문면의 「위반 시 결과는 **현재 코드로 실측되지 않는다**」가 자기모순이다 — 바로 뒤 괄호가 실제로 측정된 결과("예외 없이 두 필드를 채워 반환하고 템플릿은 읽지 않는다")를 서술한다. **「위반해도 파서는 무너지지 않는다(실측)」**로 고친다.

### 이빨 없는 정정 1건 (기록)

편승 1 의 정정된 §6 인용을 옛 과대 서술로 되돌려도 **그것을 잡는 전용 어서션이 `tests/run.sh` 에 0건**이다(검수자 grep 재확인). 되돌림이 우연히 T26-2 를 발동시켰으나 그것은 바이트 델타의 부작용일 뿐 — **두 문안이 같은 바이트였다면 아무것도 못 잡았다.** Q4 가 A-1·A-2·A-3 에 T28 이빨을 달아 준 것과 대조된다. 후속 `tests-hardening` 후보로 남긴다.

---

## 7. 충돌 4쌍의 해소 (감사 §6)

1. **개수 검증** — **소스측 상수 대조는 유효, 대상 디렉토리 총량 계수는 무효**로 확정한다. 근거: 소유권 원칙("배포하는 파일만 관리")은 대상 디렉토리의 타인 파일을 실패 사유로 삼는 것과 양립할 수 없고, 반대로 소스↔상수 파리티는 저장소 내부 정합이라 원칙과 무관하다. 실행: `hub/install.sh:95-103` 을 소스 파일명 기반 존재 검사로 교체(R2·AR13 편승), `install.sh:12` 의 RULES/AGENTS 상수에 소스측 파리티 테스트 신설(R2).
2. **CLAUDE.md 이중 역할** — 감사의 판정("첫째를 고치면 둘째가 사라진다")을 수용하되 **이번 범위 밖**으로 명시 이관한다. 갈라내기는 배포 계약(install.sh 가 CLAUDE.md 를 `~/.claude/CLAUDE.md` 로 복사) 전체에 파급되는 구조 변경이라 별도 PRP 감이다. 이번 D-1(AR9)은 그 결정과 독립인 국소 수정임을 확인했다 — 트리거 문단은 어느 분리안에서도 전역 배포본에 남는 내용이다. 후속 PRP: `claude-md-split`(§9).
3. **grep 앵커 기준** — 기준을 결정으로 명문화한다: **어서션은 산문 전문이 아니라 기계 계약 토큰을 고정한다. 가능하면 두 끝(생산자 실물 ↔ 소비자 실물)을 직접 잇는다.** C-2 의 정·역방향 테스트가 그 모범이다 — 앵커가 "문서의 예시 줄"과 "파서의 실물 정규식"이라 어느 쪽이 움직여도 검출되고, 무해한 산문 다듬기에는 반응하지 않는다. 적용 범위: **이번 PRP 의 신설 검사 전부**(AR1 스키마 검사 = JSON 파싱 기반, AR2·AR3·AR11 = 최소 토큰, AR8 = 두 끝 직결). 기존 99건의 일괄 재작성은 비목표 — 후속 `tests-hardening` 에서 이 기준으로 심사한다.
4. **README 6개 대 rev4** — 표면과 원천을 같은 단계(R2)에서 함께 수정한다: `README.md:280` 의 6→10 (표면), `docs/prps/coding-harness.md` 에 rev4 각주(원천 — 실측 기록이므로 본문 소급 수정 대신 각주). 별건 처리 시 "숫자만 고쳐지고 원천이 남는다"는 감사 경고의 직접 반영이다.

---

## 8. 신규 테스트 설계

### 8-1. `tests/hub/test_hub_dashboard_contract.py` (신설 — AR8)

```python
"""commands/dashboard.md 의 예시 줄 ↔ hub_parse 정규식 양방향 계약 테스트 (PRP audit-remediation AR8).

픽스처가 아니라 생산자 문서 원문을 읽으므로 문서·파서 어느 쪽이 움직여도 함께 드리프트할 수 없다.
hub_parse 의 밑줄 패턴 상수를 직접 쓴다 — 계약 대상이 '정규식 그 자체'이므로 사본을 만들면
사본이 드리프트한다(이 결정은 AR8 에 기록).
"""
DOC_PATH = <레포 루트>/commands/dashboard.md   # tests/hub 기준 상대 경로로 해석

def _extract_example_lines(marker: str) -> list[str]:
    # 1) 각 줄에서 \" → " 정규화 (문서의 JSON 이스케이프 예시 줄 대응)
    # 2) <li|td ... id="{marker}<숫자>" 를 포함하는 줄만 수집
    #    — 산문 속 축약형(dz-step-… 말줄임)은 숫자 요구로 자연 배제된다
```

| 테스트 | 대상 | 단정 |
|---|---|---|
| 정방향 — 추출 건수 | `dz-step-`·`dz-impl-`·`dz-cell-` 각각 | `len(lines) > 0` (앵커 소실 시 공허 통과 방지 — 감사 권고 그대로) |
| 정방향 — 전량 매칭 | 추출된 각 줄 | `_STEP_LINE_PATTERN`/`_IMPL_LINE_PATTERN`/`_CELL_LINE_PATTERN.search(line)` 전부 not None |
| 역방향 — 속성 순서 역전 | 각 줄의 `id=`↔`class=` 순서 교환 변형 | `search(...) is None` (선형·impl·매트릭스 3종 전부 — 감사의 우선순위 정보는 "하나만 넣는다면"의 조건부였고, 셋 다 넣는 비용이 무시할 수준이라 전부 넣는다) |
| 역방향 — 공백 2칸 | dz-step 대표 1줄의 속성 구분 공백 2칸 변형 | `search(...) is None` (감사 실측 NOMATCH 의 고정) |

정방향 추출의 실물 근거(이 문서를 쓰면서 확인): 구체 번호 예시 줄이 실재한다 — `dashboard.md:556`(`dz-step-1`), `:758`(`dz-impl-1`, `\"` 이스케이프 없음), `:409-423`(`dz-cell-1-1` 등 10줄), `:555-557`(이스케이프된 선형 블록).

### 8-2. B-1 회귀 (tests/hub/test_hub_server.py · test_hub_usage.py 추가 — AR4)

| 테스트 | 배치 | 방법 | 단정 |
|---|---|---|---|
| 깊은 중첩 응답이 상태를 유실시키지 않는다 | test_hub_server.py | `urllib.request.urlopen`(hub_usage_fetch 참조 경로)과 Keychain 판독 함수만 mock — **`fetch_rate_limit_capture` 자체는 mock 하지 않는다**. 응답 본문 = 3,000단 중첩 JSON(`'[' * 3000 + ']' * 3000`). `_run_usage_api_poll_cycle(now, UsageApiPollState(), 활성 config)` 호출 | 반환 상태의 `last_attempt_at_ms == now` · `consecutive_failures == 1` · 예외 미전파 |
| 실패가 기록된다 (관측 가능성) | 〃 (같은 테스트 내) | `LAST_USAGE_API_ERROR_PATH` 를 임시 경로로 치환 | 실패 기록 파일 존재 + `reason` 채워짐 |
| 성공 후 정리 실패도 시도로 집계 | test_hub_server.py | 정상 캡처 응답 + `clear_usage_api_failure` 를 OSError 로 mock | 반환 상태 `last_attempt_at_ms == now` · `consecutive_failures == 1`(보수적 집계) |
| parse 가 깊은 중첩에 안전 | test_hub_usage.py | `parse_usage_api_response(깊은 본문, now)` · `describe_json_key_structure(깊은 본문)` 직접 호출 | 예외 없이 `None` 반환 |

### 8-3. E-1 (tests/hub/test_hub_settings.py 추가 — AR10)

`InstallStatuslineForeignConflictIoTest` 와 동일한 setUp/tearDown 골격(SETTINGS_PATH 임시 치환)을 복제한 클래스 1개:

| 테스트 | 사전 상태 | 호출 | 단정 |
|---|---|---|---|
| (a) 파싱 실패 시 불변 | `settings.json` = `"{broken"` | `install_hooks()` · `uninstall_hooks()` 각각 | `ok is False` · `reason == SETTINGS_PARSE_ERROR` · **파일 바이트 불변** |
| (b) 백업 생성 | 정상 JSON(예: `{"model":"opus"}`) | `install_hooks()` | `settings.json.bak-*` 정확히 1개 · 백업 바이트 == 설치 전 원본 |
| (c) 멱등 재호출 | (b) 직후 | `install_hooks()` 재호출 | `installed == []` · **백업 개수 여전히 1** |

### 8-4. `tests/run.sh` 신설·재작성 (T번호는 구현 시 현행 최댓값 다음으로 부여)

| 검사 | 단계 | 내용 | §7-3 기준 적합성 |
|---|---|---|---|
| 훅 JSON 스키마 (AR1) | Q4 | python3 로 ` ```json ` 펜스 추출 → 전 블록 3단 스키마·`type=="command"` 단정 + `$FILE_PATH` 0건 | JSON 파싱 기반 — 산문 비의존 |
| 부재 단정 가드 (AR2) | Q4 | `rules/` 전체 `not yet present` 0건 | 최소 토큰 |
| effort 앵커 (AR3) | Q4 | performance.md 에 `persist across sessions` 존재 | 최소 토큰 |
| 미배포 에이전트 denylist (AR11) | R1 | 13종 이름 경계 매칭(`(?<![\w-])이름(?![\w-])`, 형태 무관, 예외 없음 — R1 4회차) `rules/` 0건 | 이름 토큰(형태 무관) |
| T25-122 재작성 (AR5) | Q1 | §6 표의 4단정 | 함수 본문 추출 + 심볼 토큰 |
| T25-6 주석 재규정 (AR8) | Q2 | 검사 불변, 주석의 "파서의 전제" 문구를 8-1 로 이양 | — |
| 카운트 파리티 (충돌 1) | R2 | RULES=37·AGENTS=4 상수 ↔ 소스 실측 계수 | 상수↔실물 직결 |
| LICENSE·NOTICE (R3) | R3 | 존재 + 앵커 토큰(`MIT` / ECC URL / `Affaan Mustafa` / `lucide`) | 최소 토큰 |

### 8-5. 뮤테이션 검증 (구현 중 1회 — 검사가 실제로 무는지 확인 후 되돌린다)

| 뮤테이션 | 기대 실패 |
|---|---|
| dashboard.md 예시 1줄의 `id`↔`class` 역전 | 8-1 역방향 아님 — **정방향** 매칭 실패 (T25-6·T22 계열은 통과함을 함께 확인 — C-2 가 잡던 구멍의 재현) |
| hooks.md 한 블록을 구형(matcher+command 직접)으로 되돌림 | AR1 스키마 검사 실패 |
| agents.md 에 `**planner**` 행 재삽입 | AR11 denylist 실패 |
| `_maintenance_loop` 에 폴링 호출 재삽입 | T25-122 재작성분 실패 |
| AR4 의 except 블록 제거(예외 재전파) | 8-2 첫 테스트 실패 |

---

## 9. 편승 MINOR 와 의도적 미룸

### 편승 (15건 — 전부 "이번에 어차피 여는 파일" 기준)

| # | 감사 항목 | 파일 | 단계 |
|---|---|---|---|
| 1 | dashboard.md:146 불변식 머리글 "이 두 가지" | commands/dashboard.md | Q2 |
| 2 | dashboard.md:149 `<td id=…>` 축약형 순서 | 〃 | Q2 |
| 3 | dashboard.md:11 `../../` 링크 4건 | 〃 | Q2 |
| 4 | hub_parse `matrix_done`·`started_at` "렌더 소비자 없음" docstring | hub/bin/hub_parse.py | Q2 |
| 5 | 주기 하한 부재 (hub_collect.py:87 계열, §3 강등건) | hub/bin/hub_collect.py | Q1 (AR6 — busy-loop 표면 확대 방지) |
| 6 | performance.md:83 max·ultracode session-only 단정 | rules/common/performance.md | Q4 |
| 7 | react/patterns.md:82 클래스 컴포넌트 충돌 | rules/react/patterns.md | Q4 |
| 8 | react/patterns.md:194 skills 상대 참조 | 〃 | Q4 |
| 9 | CLAUDE.md:154 §6 인용 과대 서술 | CLAUDE.md | Q5 |
| 10 | react/testing.md:18 CRA 노후 서술 | rules/react/testing.md | R1 |
| 11 | README.md:280 "6개" | README.md | R2 |
| 12 | README.md:122 구 모델 정책 요약 | 〃 | R2 |
| 13 | hub/install.sh:206 `--uninstall --dry-run` 무시 | hub/install.sh | R2 |
| 14 | hub/install.sh:97 총량 계수 (충돌 1) | 〃 | R2 |
| 15 | coding-harness.md 79개 rev4 물림 (충돌 4 원천) + install.sh:12 파리티 테스트 | docs/prps/coding-harness.md · tests/run.sh | R2 |
| +  | lucide ISC 고지 미달 | NOTICE.md 6절 | R3 (파일 신설이라 "편승"이 아니라 F-2 의 구성 요소) |

### 의도적 미룸 (후속 PRP 3건으로 이관 — 조용히 빠뜨리지 않는다)

| 후속 PRP (제안) | 이관 항목 | 미룬 이유 |
|---|---|---|
| **`shell-hardening`** | install.sh:121(grep 미이스케이프)·:201(--force 백업 편중)·:360(심링크 가드 누락)·:429(매니페스트 비원자)·:88($PWD 무검증), hub/install.sh:179(\|\| true 삼킴 — 제거 순서 재설계 필요), hub_settings.py:88(비객체 최상위 AttributeError), harness-update.md:162(diff 허위 기술)·disable-model-invocation 3건, hub_usage_fetch 네트워크 경계 4건(리다이렉트·무제한 읽기·429 대기·TLS 접힘) | 이번에 열지 않는 파일(루트 install.sh)이거나, 단순 편승 범위를 넘는 동작 재설계(제거 순서·리다이렉트 정책)가 필요 |
| **`tests-hardening`** | run.sh:1823(무는 힘 없는 앵커)·:1195(불변식 1 무검사)·:5382(passed+failed 무대조)·:327(공허 멱등)·:724(trap 덮어쓰기)·:2590(2,717줄 함수), test_hub_daemon:206·test_hub_hook:100·test_hub_statusline:136(공허 테스트), 기존 산문 어서션 99건의 §7-3 기준 심사 | 테스트 하네스 구조 개편은 이번 15건과 독립인 대규모 작업 — §7-3 이 기준을 먼저 세웠으므로 후속이 그 기준으로 심사한다 |
| **`rules-docs-sync`** | rules/README.md:5·:52(RN 누락·산술), react/hooks.md:160(useFormState), react-native 3파일 extends 오지향, typescript/coding-style.md:79(중복 서술 갈림), react/testing.md:2(글롭이 네이밍 규약 못 잡음), rules/README.md:39(`./install.sh` 지시)·:96(펜스 밖 링크), CLAUDE.md:90(검수 어휘 Critical/Major vs CRITICAL/HIGH — 검수자·커맨드 연쇄 정합 필요), CLAUDE.md:117·dashboard.md:108(설치본 죽은 링크 — 링크 정책 일괄 결정 필요), README.md:144-154 commands 표 줄 수 실측 불일치 5건(`prp-plan` 502/512·`prp-implement` 385/390·`harness-update` 319/327·`dashboard` 1315/1344·`hub` 284/285)·README.md:365 "설계 문서 42개" vs 실측 50개(검수 R3 3회차 지적 ⑧ — 이번 범위 밖 기록만), **CLAUDE.md 이중 역할 해소(충돌 2 → `claude-md-split` 로 독립시켜도 좋다)** | 이번에 열지 않는 파일이거나, 파일 1곳 수정으로 끝나지 않는 정책 결정(링크 정책·어휘 통일·문서 분리)이 필요 |
| (범위 밖 기록) | hub_template.html:1254 이중 이스케이프(코드 결함 — hub 렌더링), hub_server.py:117 iframe sandbox, .gitignore 3줄, 절대경로 INFO 11건 | 각각 독립 소품 — 다음 hub 계열 PRP 에 편승 권장 |

### 상류 PR 후보 (기록만 — 이번 범위 밖, 전제 5)

A-1(무효 훅 스키마 6블록 + `$FILE_PATH`) · A-2(자기 레포에 있는 `rules/react-native/` 를 "not yet present" 로 서술) · F-4(mandatory 도구 요구) · F-3 일부("Located in" 단정은 상류의 부분 설치 사용자에게도 같은 문제). 우리 수정은 로컬 패치로 완결되며, 상류가 고치면 F-6 목록에서 해당 항목을 제거하는 것으로 수렴한다.

---

## 10. GOTCHA (구현자가 틀리기 쉬운 함정)

1. **`finally` 안의 `return` 금지 (AR4)** — 예외를 조용히 삼키는 파이썬 안티패턴이다. 설계는 "내부 except + 함수 끝 단일 return"이다. `_collect_once` 의 `finally` 를 문자 그대로 복제하지 마라 — 거기는 가변 속성 갱신이라 성립하는 형태다.
2. **T25-6 리터럴 (Q2)** — `<li id="dz-step-…">` 와 `<li id="dz-impl-…">` 리터럴(말줄임 포함)은 불변식 2·5 본문에 반드시 남긴다. :149 에서 고치는 것은 `<td …>` 쪽뿐이다.
3. **T22-158 리터럴 (Q5)** — 신 트리거 문안에 `디스패치·결과 수령 시점마다` 를 정확히 그 표기로 보존한다(가운뎃점 포함).
4. **함수 배치 순서 (Q1)** — `_usage_api_poll_loop` 는 `_maintenance_loop` 와 `run_server` **사이**에 둔다. 재작성된 T25-122 의 sed 본문 추출 앵커가 이 순서를 전제한다. 이 배치는 **두 앵커 모두**의 전제다 — maintenance 앵커의 종료 경계가 `run_server` 에서 `_usage_api_poll_loop` 로 바뀐다(바꾸지 않으면 추출 범위가 새 함수를 삼켜 검사 ① 이 확정 실패한다).
5. **`spawnSync` 인자 배열 (Q4·AR1)** — node 원라이너에서 파일 경로를 셸 문자열로 연결하지 마라(공백·따옴표 인젝션). 마크다운의 JSON 문자열 안 이스케이프(`\"`)가 이중으로 들어가므로 작성 후 반드시 python3 `json.loads` 로 6블록 전부 기계 검증한다(신설 스키마 검사가 곧 그 검증이다 — 검사를 먼저 쓰고 문서를 고치면 RED→GREEN 이 된다).
6. **파서 패턴의 밑줄 접근 (Q2·AR8)** — `hub_parse._STEP_LINE_PATTERN` 등 모듈 프라이빗 상수를 테스트가 직접 쓴다. 정규식 사본을 테스트에 두면 사본이 드리프트하므로 의도된 결정이다 — 테스트 docstring 에 남긴다.
7. **예시 줄 추출은 구체 번호 줄만 (Q2)** — `{n}`·`{k}` 플레이스홀더 줄은 `\d` 요구로 자연 배제된다. 추출 0건 방지 단정(건수 > 0)을 빼먹지 마라.
8. **hub/install.sh 는 테스트가 실행한다 (R2)** — run.sh 의 T군이 샌드박스 HOME 으로 실제 실행한다. 가드·검증 교체 후 반드시 `bash tests/run.sh` 완주로 확인한다(`bash -n` 만으로는 부족).
9. **dashboard.md 는 Q2→Q5 순차 편집** — 두 단계가 다른 절을 만진다. Q5 를 먼저 하면 Q2 의 diff 기준이 흔들릴 뿐 기능 문제는 없다 — 권장 순서만 지킨다.
10. **A-3·performance.md 편승은 공식 문서 재확인 후 서술 (Q4)** — 이 PRP 는 감사의 WebFetch 인용까지만 보증한다. `max`/`ultracode` 문장은 구현 시점의 model-config 문서 원문으로 확정한다.
11. **NOTICE 의 로컬 패치 목록은 커밋 직전 실측 (R3)** — 이 PRP 의 목록을 그대로 베끼지 말고 `git diff main --name-only` 교집합(파생 43개 목록)으로 재산출한다.

---

## 11. 리스크와 완화책

| 리스크 | 완화 |
|---|---|
| **상류 재동기화가 패치를 되돌린다** (F-6 의 본질) | 3층 장치(AR16). 특히 테스트 이빨은 Q4·R1 커밋 시점부터 작동 — R3(문서부)이 늦어져도 기계 검출은 선행한다 |
| 폴링 스레드 분리가 미지의 동기화 결함을 만든다 | 상태는 스레드 지역 변수 유지, 파일 경합은 기존 다중 프로세스 공존 규칙이 커버(AR5 근거). T25-122 재작성 + 8-2 테스트. 스레드 부팅 실패류는 기존 `run_server` 의 스레드 기동 코드와 동일 관용구 사용 |
| 문서 대량 편집의 의미 드리프트(15개 md 파일) | 편집 문안을 PRP 에 초안으로 고정(AR1·2·3·7·9·11·12), 뮤테이션 검증 5종(8-5), 검수 단계에서 렌즈 분할(규칙 내용 / 코드 / 테스트) 권장 |
| `internal_error` 사유가 `/hub status` 소비자를 놀래킨다 | `record_usage_api_failure` 는 임의 reason 문자열을 이미 수용(hub_collect.py:608 시그니처 실측). 표시 경로는 문자열 그대로 노출 — 새 enum 을 요구하는 소비자 없음 |
| MIT 채택이 사용자 의사와 다를 수 있다 | 승인 항목 1 로 게이트. R3 는 승인 전 착수하지 않는다 — 단 F-2(상류 고지)는 어느 라이선스를 골라도 이행 의무이므로 NOTICE 설계는 선택과 독립 |
| run.sh 완주 시간이 길어 단계별 검증이 느슨해질 유혹 | 단계 표(§3)의 검증 명령을 커밋 게이트로 명시 — 부분 실행으로 대체하지 않는다 |

---

## 12. 검토했으나 채택하지 않은 대안

1. **B-2 (b) TTL 하한 상향** — 어떤 상수도 소켓 연산별 timeout 의 비상수 최악값을 덮지 못해 docstring 약속을 복원할 수 없다. 오판 빈도만 낮추는 반쪽 수정 (AR5 에 상술).
2. **D-1 서브커맨드 파일 분리 재채택** — 트리거 수정이 더 큰 절감을 무변경으로 얻는다 (AR9 에 상술).
3. **F-3 디스클레이머만 추가** — "Located in" 단정이 남아 순수 클론 전제를 위반 (AR11 에 상술).
4. **A-1 에 `jq` 사용** — 배포 대상 환경에 jq 존재를 전제할 수 없고, 같은 파일에 node stdin 선례가 이미 있다.
5. **F-6 을 별도 기계 매니페스트(`.upstream-patches.json`)로** — 소비자가 사람(재동기화 수행자)뿐인데 파일 포맷·검증 도구를 새로 만드는 것은 추측성 구조다. NOTICE.md 한 절 + 기존 하네스의 내용 검사로 같은 보증을 얻는다 (YAGNI).
6. **F-1 을 "배포 제한 명시"(감사 선택지 b)로** — clone 안내·공개 origin·harness-update 원격 pull 과 정면 충돌해 README 재설계가 필요해진다. 상류가 MIT 로 확정된 지금, 제한 라이선스를 골라야 할 근거가 없다.
7. **에이전트 참조를 단어 경계 grep 으로 전수 금지 (AR11 대안) — 정정: R1 3~4회차에 재채택됨** — `\barchitect\b` 가 `design-architect` 내부에 매칭되는 위양성. 참조 형태(볼드·표 행) 검사로 대체했다. **정정(R1 3~4회차)** — 하이픈도 경계로 취급하는 변형(`(?<![\w-])이름(?![\w-])`)으로 이 위양성을 해소해 재채택했다: 형태별 검사가 실측 표기 12형태 중 4개만 잡는 것으로 드러나 대체가 불가피했다(§4 F-3 참조).

---

## 13. 승인 요청 항목

> **전체 승인 완료 — 2026-08-28.** 항목 1 의 저작권자 표기는 `pascal` 로 확정됐고, 항목 2~5 는 원안(설계자 권고)대로 승인됐다.
> 기각 권고된 대안(§12-1 TTL 상향 · §12-3 디스클레이머 · §12-6 배포 제한 · §12-2 파일 분리)은 채택하지 않는다.
> 승인 범위에 **`CLAUDE.md` 이중 역할 해소는 포함되지 않는다**(§7 충돌 2 → 후속 `claude-md-split`) — 사용자에게 명시 확인받았다.

### 승인 항목 1 — 라이선스: **MIT 채택** + 저작권자 표기 문자열 (AR14) — ✅ 승인
`Copyright (c) 2026 pascal` 로 확정. 대안(배포 제한)은 §12-6 으로 기각.

### 승인 항목 2 — B-2 해법: **폴링 전용 스레드 분리** (AR5, 결정 A3 의 배치 번복) — ✅ 승인
TTL 상수 조정 대안은 §12-1 로 기각 권고. T25-122 재작성이 동반된다.

### 승인 항목 3 — F-3: 로스터를 **배포 4종으로 교체** + 참조 8파일 정리 (AR11) — ✅ 승인
상류 문서와의 diff 가 커진다(F-6 목록·이빨로 관리). 디스클레이머 대안은 §12-3 으로 기각 권고.

### 승인 항목 4 — D-1: CLAUDE.md 트리거 문안 (AR9) — ✅ 승인
"세션 최초 1회 Skill 호출 + 이후 직접 수행 + compact 후 1회 재호출" 문안 그대로 승인 여부.

### 승인 항목 5 — 편승 15건·미룸(후속 PRP 3건) 목록 (§9) — ✅ 승인
특히 AR6(주기 하한)의 편승 승인 — 감사 §3 이 MINOR 로 강등한 건이지만 AR5 가 busy-loop 표면을 늘리므로 동반 수정을 권고한다.
