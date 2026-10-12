# 에이전트 하네스 지형 조사 — GitHub 경쟁군 분석과 coding-harness 적용 판정

> **이 문서는 기능 설계 PRP가 아니다.** GitHub 에서 coding-harness 와 같은 부류(에이전트
> 코딩 하네스·설정 배포판)를 조사하고, 옮길 수 있는 기법을 판정한 **조사 보고서**다.
> 여기서 판정한 「티어 0 결함」의 수정 설계는 별도 PRP 로 분리한다.
>
> 조사 일자: 2026-08-28 · 기준 커밋: `9145ef3`
> 조사 규모: 서브에이전트 28팔(recon 2 · dossier 18 · 종합 4 · 완결성 비평 1 · 이진 판정 3)
> · 수집 기법 170건 · star·push 일자는 전부 `gh api` 로 개별 실측

---

## 0. 결론 (먼저)

| 질문 | 답 | 근거 |
|------|-----|------|
| 경쟁군에서 배울 **배포 방식**이 있는가 | **없다** | 비교한 설정 배포판 6종 중 파일 단위 내용 비교로 충돌을 판정하는 것은 coding-harness 뿐. 나머지는 존재하면 skip 이거나 전량 y/N |
| 플러그인 마켓플레이스로 옮겨야 하는가 | **아니다 (병행도 기각)** | 규격상 플러그인은 CLAUDE.md 도 rules/ 도 실을 수 없다 — 배포물의 73%(38/52)·상시 컨텍스트의 100%가 배송 경로를 잃는다 |
| skills(SKILL.md) 자산을 도입해야 하는가 | **아니다** | `~/.claude/commands/*.md` 가 **이미** Skill 도구 표면으로 노출되고 description 만 상주한다. progressive disclosure 도 자동 호출도 확보돼 있다 |
| 자동 학습·메모리 루프를 넣어야 하는가 | **아니다 (후보 4종 전부 기각)** | 넷 다 명세와 구현이 어긋나 있고, CLAUDE.md 에 기록된 자가증식 사고의 자동화판이다 |
| **관측(dashboard·hub)**은 경쟁군 대비 어떤가 | **앞서 있다** | 실시간성 하나를 빼면 cwd 파생·워크트리 접기·18필드 진단·마커 기반 소유권·단위테스트 15개가 경쟁군에 없다 |
| 그럼 진짜 공백은 무엇인가 | **규범을 확인할 기계가 없다** | 「검수 생략 금지」·「PRP 승인 전 구현 금지」 같은 최상위 규범이 전부 산문이라 강제력이 0이다 |

**이 조사의 가장 큰 수확은 외부 기법이 아니라 자기 결함이다.** 경쟁군과 대조하는
과정에서 coding-harness 자신의 결함 10건이 드러났고(§4), 그중 하나는 **사용자 머신에서
지금 이 저장소의 원칙을 위반하도록 지시하고 있는 환경 오염**이다(§6).

---

## 1. 조사 방법과 한계

`gh search repos` 를 33개 각도로 실행(`--stars ">=1000" --sort stars`)하고, 상위 40여 개
중 **18개 레포군을 파일 트리와 실제 자산 파일 수준까지** 열어 분석했다. README 만 읽는
것을 금지했다 — README 는 마케팅이고 진짜 기법은 커맨드·스킬·훅 파일 안에 있기 때문이다.
이 판단은 실제로 값을 했다: superpowers-marketplace 의 README 는 존재하지 않는
슬래시 커맨드 3개와 도구 1개를 광고한다(실제 트리에 `commands/` 디렉토리가 없다).

**한계 3가지.**

1. **CJK 소규모 레포 미확인** — 한국어·일본어 키워드 검색이 star 1,000 이상 구간에서
   유효 결과를 내지 못했다. 그 아래 구간은 조사하지 않았다.
2. **후보 30선 중 링크만 확인한 항목이 다수** — 별 수·push 일자는 실측했으나 내용을
   열지 않은 것이 있다.
3. **완결성 비평의 오탐 1건** — 비평자가 「관측 축 산출물이 문장 중간에 끊겼다」고
   치명 등급으로 보고했으나, 이는 워크플로 스크립트가 비평자에게 넘긴 코퍼스를
   `.slice(0, 60000)` 로 자른 탓이었다. 원본은 온전하다. 비평자에게 잘린 입력을 주면
   그 절단 자체를 결함으로 보고한다 — 다음 조사에서 반복하지 말 것.

---

## 2. 지형도 — 6개 부류

star 는 2026-08-28 `gh api` 실측.

| 부류 | 대표 레포 | ★ | 성격 |
|------|----------|---|------|
| 스킬 프레임워크 | `obra/superpowers` | 278,693 | 방법론을 skills 로 배포. SessionStart 부트스트랩 훅이 통합의 전부 |
| 하네스 최적화 | `affaan-m/ECC` | 243,763 | skills 286 + commands 94 + agents 68. 훅 강제의 백과사전 |
| 스킬 번들 | `mattpocock/skills` | 239,220 | SKILL.md 37개. 진짜 자산은 문서 작성 방법론 |
| 공식 규격 | `anthropics/skills` | 172,095 | SKILL.md · marketplace.json 스펙 원본 |
| 스펙 주도 | `github/spec-kit` | 131,899 | 어댑터 38개 · 테스트 158개. GitHub 조직이 떠받쳐 성립 |
| 컨텍스트 엔지니어링 | `gsd-build/get-shit-done` | 64,631 | **아카이브됨** |
| 역할 기반 애자일 | `bmad-code-org/BMAD-METHOD` | 52,393 | 설치기의 sha256 해시 대장이 배울 점 |
| 설정+관측 합본 | `davila7/claude-code-templates` | 30,427 | install.sh + dashboard + hub 를 한 CLI 로 |
| 관측 | `disler/…-observability` | 1,527 | HTTP+SQLite+WebSocket. 6개월 정체 |

### star 를 활성도 신호로 쓰지 말 것

`gsd-build/get-shit-done`(64,631★)과 `gsd-build/gsd-2`(7,767★)는 **둘 다
`archived: true`** 이고 README 전문이 후속 레포로의 리다이렉트 한 줄뿐이다. 실제
후속인 `open-gsd/gsd-core` 는 8,812★ 로 별을 승계하지 못했다. 조사 대상을 star 로만
고르면 죽은 레포를 분석하게 된다.

---

## 3. coding-harness 의 상대적 위치

### 앞서 있는 것

**설치기.** 비교한 설정 배포판 6종(agent-os · ring · CCPlugins · claude-modular ·
SuperClaude · Mizoreww) 중 **관리 파일의 내용을 파일 단위로 비교해 충돌을 판정하는
것은 coding-harness 뿐**이다. 나머지는 「존재하면 skip」이거나 「전량 y/N」이다.
`--scope` 강제 · `--dry-run` · 누락 자동 복원 · 상이 시 exit 1 + `--force` ·
CLAUDE.md 타임스탬프 백업의 조합을 갖춘 곳이 없다.

**관측.** disler 의 풀스택(bun + sqlite3 + vue + vite)이 파는 것 중 이 저장소에
필요한 것은 실시간성 하나인데, 1인 순차 워크플로우에서 1분 폴링 지연이 실제 비용을
낳는 시나리오가 없다. 반대로 coding-harness 만 갖고 있는 것:

- `hub_hook._project_fields` 의 **cwd 파생 프로젝트 식별** — disler 는 사용자가
  `--source-app` 라벨을 손으로 설정해야 한다
- `SessionFacts.observed_cwds` — 한 세션의 모든 cwd 를 순서대로 보관
- `hub_project.fold_worktree_path` — 워크트리를 부모 저장소로 접기
- `hub.py status` 의 **18개 진단 필드**
- `hub_settings` 의 **마커 기반 소유권 판정** — 남의 훅은 읽지도 고치지도 않는다
- `tests/hub/` **15개 단위테스트**

**자산 규모의 절제.** 조사한 대형 레포는 전부 자산 개수 인플레이션 상태다 —
ECC 448개 · ruflo 314개 · spec-kit blob 692개 · GSD v2 단일 디렉토리 1,431파일.
그 규모에서는 저장소 자신이 무엇이 동작하는지 추적하지 못한다(ruflo 는
`hook-handler.cjs` 가 로드하는 `router.js`/`session.js`/`memory.js` 3개 모듈이 실제로는
`.cjs` 확장자라 **죽은 채로 커밋돼 있고**, `safeRequire` 가 콘솔까지 음소거해 아무도
모른다). **배포 파일 52개는 적어서 열등한 것이 아니라 전수 검증이 가능해서 우월하다.**

### 뒤처진 것 — 단 하나

**규범은 완성돼 있고, 그 규범이 참인지 확인할 기계가 없다.** 이 문장이 조사 전체를
관통한다. 같은 형태의 실패를 여러 레포가 독립적으로 증명한다:

- spec-kit 의 「체크리스트 게이트」는 실제로는 모델이 `- [ ]` 개수를 세어
  「미체크 항목이 있습니다. 그래도 진행할까요?(yes/no)」를 묻는 것이다. 사용자가 yes
  하면 그냥 지나간다.
- ruflo 는 병렬 쓰기의 전제(워크트리 격리 · 명시적 파일 소유권)를 CLAUDE.md 에
  적어 놓고 그것을 강제하는 코드를 하나도 넣지 않았다.
- coding-harness 의 「검수를 통과하지 못한 코드는 커밋하지 않는다」도 지금 같은 성질이다.

---

## 4. 티어 0 — 조사가 발견한 자기 결함 10건

외부 기법 도입 이전 문제다. 전부 실측으로 확인했다.

| # | 결함 | 근거 | 무엇이 문제인가 |
|---|------|------|----------------|
| 1 | **PRP 산출 경로 분열** | `CLAUDE.md:72` = `docs/prps/{기능명}.md` / `commands/prp-plan.md:208`·`prp-implement.md:283` = `.claude/PRPs/plans/` | 후자는 이 저장소에 **존재하지 않고** 실제 문서 42개는 전자에 있다. 커맨드 쪽이 죽은 경로다 |
| 2 | **검수 루프 종결 규칙 0건** | `agents/code-reviewer.md:59` = "하나라도 남으면 FAIL 이고 라운드를 반복한다" | `agents/code-reviewer.md`·`CLAUDE.md`·`commands/code-review.md` 세 파일에 상한·HALT·에스컬레이션 문구가 **0건**. 무한 루프 규정 |
| 3 | **상시 컨텍스트 선언과 실측의 괴리** | 실측 `cat CLAUDE.md rules/README.md rules/common/*.md \| wc -c` = **49,110B** vs `README.md:112`·`:233` = "약 45KB" | 이미 9% 초과했고 잡는 장치가 없다 |
| 4 | **삭제 경로 부재** | `install.sh` 에 `rm`·`unlink`·`rmdir` **0건** | 레포에서 rules 파일을 지우거나 이름을 바꾸면 대상에 **영구 잔류**한다. `rules/common/` 은 **항상 로드**라 폐기된 규칙이 매 세션 주입되고, 소유권 원칙상 그 파일은 앞으로 「남의 파일」로 재분류돼 영원히 보호된다 |
| 5 | **결정 가능한 사실을 LLM 판단에 위임** | `commands/harness-update.md:165` | 「단순히 낡은 사본인가 의도적 커스터마이징인가」를 모델의 문서 해석에 맡긴다. BMAD 는 같은 질문을 설치 시점 sha256 대장으로 결정론적으로 답한다 |
| 6 | **배포판이 강제하는 도구를 배포판이 깔지 않음** | `rules/common/development-workflow.md:11` 이 Context7(MCP) 사용을 0단계 필수 절차로 규정 / `grep -ci mcp install.sh` = **0** | §7 이진 판정 참조 |
| 7 | **환경 오염** | `~/.claude/rules/python/` (§6) | 이 저장소의 원칙을 위반하라고 지시한다 |
| 8 | **훅 로그 시크릿 스크럽 0건** | `hub/bin/hub_hook.py` 에 redact/scrub 정규식 0건. `_clip_prompt()` 는 500자 자르기만 | `commands/hub.md` 설치 고지가 「프롬프트 앞부분 500자를 **평문으로** 최대 7일 보관」이라고 스스로 인정한다. hub 는 **전역 훅**이라 모든 프로젝트의 프롬프트를 수집한다 |
| 9 | **조건부 로딩 설계의 실측 붕괴** | `grep -l '"\*\*/\*\.tsx"' rules/*/*.md` = **24개 65,676B** → 상시 포함 총 **114,786B** | `react-native/` 8개가 전부 `**/*.ts`+`**/*.tsx` 라 순수 웹 프로젝트에서도 로드된다. 「12 항상 + 25 조건부」 설계가 「대부분의 TS 프로젝트에서 36개 항상」으로 붕괴 |
| 10 | **`commands/dashboard.md` 87,305B** | 상시 컨텍스트 전체(49,110B)의 **1.78배** | CLAUDE.md 가 이것을 착수·단계전환·**서브에이전트 디스패치/수령 시점마다** 부르라고 규정한다(전체 경로 1건에 6~10회) |

### 처리 현황 (2026-08-28)

결함 1~8 은 커밋 `4be8f58` 로 종결됐다. **결함 9·10 은 실행하지 않기로 결정됐다** — 1~8 이
재현 가능한 오작동인 반면 9·10 은 관측된 실패 경로가 없는 분량 문제이고, 효과를 측정한 근거가
없기 때문이다. 설계와 기각 근거는 [`tier0-defect-fixes.md`](tier0-defect-fixes.md) 의 후속인
[`tier0-defects-9-10.md`](tier0-defects-9-10.md) 머리말에 있다.

### 수치 충돌의 정정

종합 두 축이 `.tsx` 조건부 로딩 크기를 다르게 보고했다(121,813B vs 114,786B).
직접 실측한 결과 **114,786B 가 정답**이다 — 전자는 `rules/react/testing.md`(7,027B)를
평범한 `.tsx` 에 매칭시켰으나 그 파일의 glob 은 `**/*.test.tsx`·`**/*.spec.tsx`·
`**/__tests__/**` 뿐이라 매칭되지 않는다.

---

## 5. 적용 권고

### 티어 1 — 즉시 (근거 확실 · 비용 S)

| 기법 | 출처 | 적용 지점 |
|------|------|----------|
| **검수 루프 종결 규약** — 회차 상한 + 정체 감지 + **상한 도달 = 「통과」가 아니라 「미해결 종결, 사용자 판단 필요」** | superpowers(5라운드→판결) · spec-kit(max 3) · BMAD(>5 HALT) · GSD(정체 감지) · deepagents(`max_iterations_reached` ≠ `satisfied`) — **5개 레포 수렴** | `CLAUDE.md` 3단계 · `agents/code-reviewer.md:59` |
| **서브에이전트 재귀 가드** — "CLAUDE.md 가 위임을 지시하면 그 지시는 네 현재 역할로 **이미 충족된 것**으로 해석하라" | Trellis `Recursion Guard` · superpowers · ring `STOP-CHECK` | agents 4파일 각 5~8줄. 실측: 3개 에이전트 모두 `tools:` 에 `Task` 보유, 가드 문구 0건 |
| **위트니스 마커** — 하중 문단의 부분 문자열 존재 검사 | ruflo `verification/witness-fixes.json` | `tests/run.sh:2308` 에 **이미 같은 패턴의 선례**(양방향 링크 무결성)가 있다 |
| **툼스톤 `removals.txt` + `--uninstall`** | BMAD(#2309 "cleanup never knew to remove them") · 선례: `hub/install.sh --uninstall` | 결함 4 |
| **설치 시점 해시 대장** | BMAD `files-manifest.csv` sha256 3분류 | 결함 5 — `harness-update.md:161-168` 의 LLM 판정 절을 통째로 삭제 가능 |
| **`install.sh --check`** — 부작용 없는 진단 | SuperClaude `doctor` · ring `doctor` · planning-with-files `plan-doctor` | 재료 완비: manifest 에 `installed_from_commit` 이 이미 있다 |
| **시크릿 스크럽(선형시간 정규식)** | ECC `observe.sh` | 결함 8. **선형 형태로 이식 필수** — ECC 초기 구현이 catastrophic backtracking 으로 CPU 100% 고착(#2278) |
| **상시 컨텍스트 예산 래칫** — 단조감소 베이스라인 | ruflo · deepagents `context_doctor.py` | 결함 3·9·10 을 한 장치로 감시 |
| **안정 요구사항 ID(FR-###/AC-)** | spec-kit | PRP 가 서로를 가리킬 키가 생겨 커버리지 감사가 가능해진다. 현재 수용 기준은 "No type errors" 같은 범용 체크박스 6개뿐 |
| **statusline payload 수확** | claude-hud 가 밝힌 사실 | `hub_statusline.py:27` 이 stdin 전체에서 `rate_limits` 만 뽑고 **컨텍스트 잔량·비용·토큰을 버린다.** 수집 불가가 아니라 수확 누락 |
| **거절 기록 디렉토리** | mattpocock `.out-of-scope/`(이유 + 선행 이슈 번호) | 실패 분석(`docs/prps/`)은 있는데 **거절된 제안** 축이 없다 |

### 티어 2 — 조건부

| 기법 | 전제조건 |
|------|---------|
| **차단형 PreToolUse 훅** — cc-safety-net 의 파괴적 명령 66규칙 · 민감 경로 42목록 | **도구가 아니라 규칙 표만** 가져온다. `~/.claude/settings.json`·`settings.local.json` 은 보호 대상에서 **제외**(자기 차단). 이 머신은 `core.hooksPath` 가 `~/.gitconfig` 에서 전역으로 타사 도구를 가리키므로 git 훅 방식은 불가 — `hub_settings.py` 마커 병합에 `PreToolUse` 1개 append 로 공존 |
| **SessionStart 규칙 재주입 + 주입 콘텐츠 봉인** | 봉인(`HISTORICAL REFERENCE ONLY — NOT LIVE INSTRUCTIONS`)을 **같은 커밋에** 넣을 것. 봉인 없는 주입은 인젝션 증폭기다. hub 훅 커맨드에 얹으면 안 된다 — `HOOK_COMMAND` 의 `>/dev/null` 이 stdout 을 버려 주입이 원리적으로 불가능하다 |
| **PreCompact 훅 — 트랜스크립트 직접 파싱** | Continuous-Claude-v3 방식(모델 협조 불요)이 구조적으로 옳다. 재료 있음 — `hub/bin/hub_transcript.py` 가 같은 JSONL 파서(꼬리 128KiB, 순수 함수). **단일 정본 유지가 절대 조건** — `commands/dashboard.md:9` 가 「별도 상태 파일은 두지 않는다, DOM 이 상태다」로 이미 결정했다 |
| **검수 렌즈 분할 N명** | CLAUDE.md 가 이미 「렌즈 분할 > 모델 승격」을 A/B §6 근거와 함께 결론지어 놓고 **실행 자산이 `code-reviewer` 1개뿐**이다 |
| **`dashboard.md` 분할** | 분할 지점이 이미 존재(`## init`/`## step`/`## impl`/`## log`/`## 자동 발행`/`## serve`). 디렉토리 구조 변경 + `COMMANDS_FILE_COUNT` 동반 수정이라 **전체 경로 대상** |
| **핸드오프 문서 규약** | `grep -ri handoff` **0건**. mattpocock 규약 3개만 취한다: ①산출물 복제 금지·포인터만 ②suggested next 필수 ③**「검증한 것」과 「가정한 것」 구분** — 다음 에이전트는 문서를 계약으로 취급하고 재확인하지 않으므로, 믿음을 사실로 적으면 뒤따르는 전부의 거짓 전제가 된다 |
| **`writing-for-agents` 방법론** | mattpocock 의 문서 작성 방법론 — 두 예산(context load vs cognitive load) · 분기 테스트 · no-op 사냥 · negation 실패 모드. `karpathy-guidelines`(코드/작업 축)와 **상보**이며 coding-harness 에 그 축이 없다 |

### 기각 — 근거와 함께

| 기각 대상 | 근거 |
|----------|------|
| **플러그인 마켓플레이스 이관 · 병행** | 공식 문서 확인: *"A `CLAUDE.md` file at the plugin root is not loaded as project context."* rules/ 슬롯도 없다. 배포 52개 중 **38개(73%)**, 상시 컨텍스트 실측 49,110B 의 **100%** 가 배송 경로를 잃는다. 게다가 커맨드는 `coding-harness:dashboard` 로 강제 네임스페이싱되는데 그 이름을 부르는 문장 대부분이 **실을 수 없는 CLAUDE.md 안**에 있어 split-brain 이 된다 |
| **skills(SKILL.md) 자산 클래스 도입** | 실측 반증 — `~/.claude/commands/*.md` 는 **이미** Skill 도구 표면으로 노출되고 카탈로그엔 description 만 상주한다. 스펙을 직접 읽은 결과 `allowed-tools` 는 권한을 **강제하는 것이 아니라 확대**하고, coding-harness 는 이미 agents `tools:` 로 강제를 갖고 있다. 다만 스펙의 **500줄/5,000토큰 본문 권고**는 결함 10 의 외부 근거로 인용할 값이 있다 |
| **자동 학습 루프 4종** (ECC instinct · pro-workflow `[LEARN]` · deepagents remember · claude-mem) | 넷 다 같은 결함이다. ECC 는 SKILL.md 가 confidence 감쇠(-0.02/week)를 표로 규정해 놓고 `instinct-cli.py` 2,262줄에 **해당 코드가 없다** — 숫자는 haiku 자가신고다. pro-workflow 는 자기 `rules/self-correction.mdc` 의 "Wait for approval before persisting" 을 훅이 우회하고, 폐기 컬럼(`times_applied`)을 만들어 놓고 **호출부를 배선하지 않았다**. **전부 CLAUDE.md 에 기록된 자가증식 사고의 자동화판이다.** 대안은 `/replay` 계열 재소환 — 새 지식을 만들지 않으므로 증식 위험이 구조적으로 0 |
| **다중 에이전트 타깃 배포 / `intellectronica/ruler`** | ruler 의 concat 모델이 `paths:` 조건부 로딩을 무력화해 상시 컨텍스트를 49,110B → **106,043B(2.16배)** 로 늘린다. 어댑터 부채를 Node 런타임 + 전이 패키지 25개로 바꿔치기할 뿐이다 |
| **문서 샤딩(shard-doc)** | **BMAD 자신이 HEAD 에서 폐기했다.** 52k★ 프로젝트가 자기 대표 기법을 버린 사실이 「유행이라 도입」을 자르는 실측 근거다 |
| **WebSocket 실시간 관측** | 병목이 서버가 아니다 — `hub_server._SnapshotRefresher.collect_if_older_than` 이 요청마다 2초 신선도 창을 건다. 남는 것은 브라우저 폴링뿐이고 1인 순차 워크플로우에서 1분 지연의 비용이 그려지지 않는다 |
| **스웜 병렬 자동 발동** | 「파일 3개 이상」이라는 **같은 임계값**에서 ruflo 는 8명 병렬을, coding-harness 는 「설계→**사용자 승인**→구현→검수」 순차를 발동한다. 스웜은 승인 게이트·검수자 무권한·재검수 인계를 전부 우회한다 |
| **검수자에게 Edit/Write 부여** | 자기가 고치고 자기가 통과시키면 「검수 미통과 코드 커밋 금지」가 자기 승인으로 무력화된다. `agents/code-reviewer.md` 는 이미 도구 권한으로 강제하고 본문 첫 줄에 의도를 명시한다 |
| **npm/npx · PyPI/uv 설치기** | 「외부 의존 0」 위반. BMAD 가 스킬 진입점을 `uv run` 에 걸어 **uv 가 없으면 스킬 전체가 HALT** 되는 것이 이 방향의 종착점이다 |
| **심볼릭 링크 설치** | `install.sh:170-180 check_no_symlink_targets()` 가 심링크 대상을 **명시적으로 거부**한다. 채택하려면 이 안전장치부터 뒤집어야 한다 |

---

## 6. 환경 오염 1건 — 즉시 조치 대상

`~/.claude/rules/` 에 **coding-harness 가 배포하지 않은 언어 규칙 11개 디렉토리**가 있다
(`cpp`·`csharp`·`dart`·`golang`·`java`·`kotlin`·`perl`·`php`·`python`·`rust`·`swift`,
전부 2026-04-15). 소유권 원칙상 `install.sh` 는 이것을 건드리지 않으므로 **영구히 활성**이다.

문제는 `python/` 이다. frontmatter 가 `paths: ["**/*.py", "**/*.pyi"]` 이므로 이
저장소에서 `hub/bin/*.py` 를 여는 순간 로드되는데, 내용이 이 저장소와 정면으로 충돌한다:

```
~/.claude/rules/python/testing.md
  ## Framework
  Use **pytest** as the testing framework.
  ## Coverage
  pytest --cov=src --cov-report=term-missing
```

그런데 이 저장소는 **stdlib `unittest` 15개 파일**을 `python3 -m unittest discover` 로
돌린다(`tests/run.sh:2577`). 「외부 의존 0」 때문에 의도적으로 선택한 것이다.
**즉 하네스가 에이전트에게 자기 원칙을 위반하라고 지시하고 있다.**

이것이 `rules/python/` 신설 판정의 근거다 — **공백을 메우는 것이 아니라 오염을
소유권 아래로 회수하는 작업**이다. 내용은 지어내지 말고 `hub/bin/*.py` 에서 귀납한다
(stdlib 전용 · unittest · 순수 함수 분리 · 훅은 항상 exit 0).

---

## 7. 이진 판정 3건

### 7-1. MCP 서버 설정 배포 → **(A) 규정을 고친다**

`.mcp.json` 배포를 추가하지 않는다. 모순의 정체가 「배포 누락」이 아니라
**미큐레이션 잔재**다 — `rules/common/development-workflow.md` 0단계의 Context7/Exa
고유명사 의존을 제거하고 「설치돼 있으면 쓴다」식 능력 기반 서술로 완화한다.
MCP 서버는 대부분 npx/uvx 로 뜨므로 배포하는 순간 「외부 의존 0」이 깨진다.

### 7-2. `rules/python/` 신설 → **신설한다**

단 「언어 커버리지 확장」이 아니라 §6 의 오염 회수로서. 5파일 신설 시 동반 수정 지점:
`install.sh` 의 `RULES_FILE_COUNT` 37→42 · `tests/run.sh` 의 리터럴 · `README.md` 표 ·
`rules/README.md`. `paths: ["**/*.py"]` 이므로 상시 예산 49,110B 는 늘지 않는다.

### 7-3. eval · 텔레메트리 하네스 도구화 → **안 한다**

`docs/prps/model-scaffolding-ab-experiments.md` 의 A/B 실험 2시간에서 병목은
**오케스트레이션이 아니라 접지 실측과 채점 판단**이었고, 자동화 가능한 구간이 실측
시간의 10%대다. 1인 저장소에서 재사용 횟수가 도구화 비용을 정당화하지 못한다.

---

## 8. 안티패턴 — 따라하면 안 되는 것

조사 중 관측된 것 중 coding-harness 에 직접적인 경고가 되는 것만 남긴다.

| 안티패턴 | 어디서 | 왜 경고인가 |
|---------|-------|-----------|
| **자산 개수 인플레이션** | ECC 448 · ruflo 314 · GSD v2 1,431파일 | 도구를 쓰는 시간보다 도구를 고치는 시간이 커진다. ruflo 는 배선되지 않은 모듈 3개가 죽은 채로 커밋돼 있고 `safeRequire` 가 그것을 음소거한다 |
| **문서가 구현을 앞질러 가고 그것이 표로 포장됨** | ECC `continuous-learning-v2` | confidence 증감·주간 감쇠를 표로 규정하고 코드에 없다. **「md=실행 명세」를 표방하는 프로젝트에서 이 간극은 문서 신뢰도 전체를 깎는다** |
| **측정 없는 성능 주장** | ECC GateGuard "+2.25점" | 표본 과제 2건 · 채점자·기준·재현 절차 없음. 기법은 옮길 값이 있으나 **숫자는 인용하지 말 것** — 이 저장소가 모델 승격에 6팔 블라인드 채점을 요구한 기준에 미달 |
| **훅 안에 마케팅 퍼널** | ruflo `UserPromptSubmit` | 사용자의 레이트리밋 상태를 읽어 스폰서 홍보 문구를 트랜스크립트에 출력한다 |
| **모든 편집마다 git 자동 커밋·태그** | ruflo `standard-checkpoint-hooks.sh` | `git add` + `commit` + `tag` 를 파일 편집마다 찍는다. `MEMORY.md` 가 경고하는 동시 세션 오염을 **자동화**한다 |
| **권한 전면 개방 settings 배포** | Mizoreww(`Bash(*)`·`skipDangerousModePermissionPrompt`) · ruflo(`Bash(npx:*)`) | 배포판이 수신자 대신 내려도 되는 결정이 아니다. `rules/common/hooks.md` 의 "Never use dangerously-skip-permissions" 와 정면 충돌 |
| **README 를 자산 목록으로 믿기** | superpowers-marketplace | README 가 존재하지 않는 슬래시 커맨드 3개와 도구 1개를 광고한다. **star 최상위 레포의 공식 README 도 실물과 어긋난다** |
| **상시 주입문에 최상급 강제 어법 쌓기** | superpowers `using-superpowers` | `<EXTREMELY-IMPORTANT>` · "YOU DO NOT HAVE A CHOICE" · "1% 가능성이라도 있으면 ABSOLUTELY MUST" 로 사소한 질문에도 의례를 태운다 |
| **페르소나 연극** | BMAD `bmad-agent-dev` | 활성화 8단계 중 4단계를 캐릭터 유지에 쓴다("Do not break character until the user dismisses the persona") |
| **생성물·빌드 산출물을 배포 대상에 포함** | GSD `*.generated.cjs` · Continuous-Claude-v3 `dist/` | sha256 소유권 판정이 「생성 결과가 달라서 다른 것」과 「사용자가 고쳐서 다른 것」을 구별할 수 없게 된다 |

---

## 9. 한 줄 결론

**배울 것은 기법이지 카탈로그가 아니다.** coding-harness 는 배포와 관측에서 경쟁군을
앞서 있고, 진짜 공백은 하나 — 최상위 규범이 전부 산문이라 강제력이 0이라는 것이다.
그 첫 수는 훅 인프라 도입(비쌈)이 아니라 **md 몇 줄짜리 종결 규약·재귀 가드와
`tests/run.sh` 에 붙는 결정적 검증기**다.
