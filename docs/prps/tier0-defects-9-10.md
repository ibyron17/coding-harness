# Tier-0 잔여 결함 9·10 + LOW 2건 (PRP)

> **상태: §2·§3(결함 9·10)은 실행하지 않기로 결정됐다. §4(LOW 2건)만 실행됐다.**
> 이 문서는 설계 산출물이자 **「하지 않은 이유」의 기록**이다. 되살리려면 아래 기각 근거를
> 먼저 반박해야 한다.

## 기각 결정 (2026-08-28)

결함 9·10 은 같은 조사가 찾아낸 1~8 과 **성격이 다르다.** 1~8 은 재현 가능한 오작동이었고
(삭제 경로 부재 → 폐기 규칙 영구 주입 / 시크릿 평문 보관 / 검수 루프 무한 반복),
9·10 은 **관측된 실패 경로가 없는 분량 문제**다 — 고치지 않아도 아무것도 깨지지 않는다.

기각 근거 셋:

1. **효과를 측정한 적이 없다.** 결함 9 는 18,154B(≈4.5k 토큰)를 아끼려고 RN 규칙의 발동률을
   깎는데, 그 교환이 남는지 잰 근거가 없다. 전역 지침 「측정 없는 최적화는 하지 않는다」에
   정면으로 걸린다.
2. **결함 10 의 이득이 비대칭이고 대가가 크다.** −74% 는 `step`/`log` 전용 세션 한정이고
   `init` 을 부르면 −9% 다. 그 대가로 1,315줄짜리 동작 명세를 6조각으로 쪼개며, 핵심 수용
   기준(§8-3 「`/dashboard step` 이 다른 참조 파일을 Read 하지 않는가」)은 **자동 테스트로
   만들 수 없다** — 사람이 세션을 돌려 눈으로 확인해야 한다. 검증할 수 없는 수용 기준은
   이 조사가 발견한 결함 형태 그 자체다.
3. **설계 과정에서 전제가 세 번 뒤집혔다** — LOW-2 의 공허성 진단(§4.2), `.claude/commands/`
   하위 디렉토리 등록 여부(§3.2), 9-a 의 D/E 선택(§2.3). 셋 다 잡아냈지만, 근거가 튼튼한
   문제는 이렇게 흔들리지 않는다.

되살릴 조건: 9 는 컨텍스트 바이트가 실제 비용으로 관측될 때, 10 은 `dashboard.md` 주입이
실제 문제를 일으킨 사례가 나올 때. 그 전까지는 열지 않는다.

> 대상 브랜치: `fix/tier0-defects` · 기준 커밋 `4be8f58`
> 선행: `docs/prps/harness-landscape-survey.md` §4 (결함 10건 중 8건은 4be8f58 로 종결)
> **이 문서의 모든 수치는 직접 실행한 명령의 출력이다.** 각 표에 재현 명령을 병기한다.

---

## 0. 결론 요약 (승인이 필요한 3건)

| # | 결함 | 판정 | 근거 |
|---|------|------|------|
| 9-a | `rules/react-native/` 8개가 `**/*.ts`·`**/*.tsx` 로 로드 | **고친다 (부분)** | 순수 웹 프로젝트에 RN 규칙 18,154B 무상 적재 |
| 9-b | `rules/react/`·`web/`·`typescript/` 의 `.tsx` 매칭 | **고치지 않는다** | 의도된 동작. 결함 아님 |
| 9-c | 재발 방지 기계 부재 | **고친다** | T26 패턴 복제로 시나리오별 래칫(T28) 신설 |
| 10 | `commands/dashboard.md` 87,305B | **고친다 (지연 로드 분할)** | 배치는 **비-`.md` 평면 파일** — 하위 디렉토리는 기각, §3.2 |
| L-1 | T27-4 실패 메시지 중복 | **고친다** | 자명 |
| L-2 | `grep -qF '[보호]'` 가 무조건 참 | **전제가 틀렸다 — 고치되 다른 이유로** | 실측 반증, §4.2 |

**핵심 트레이드오프(9-a)**: 글롭만으로 RN 프로젝트를 식별하는 것은 **불가능하다**. 어떤 선택지도
「웹에 새는 것」과 「RN에서 안 뜨는 것」 중 하나를 고르는 문제다. §2.3 에서 정면으로 다룬다.

---

## 1. 요구사항 요약

coding-harness 의 상시/조건부 컨텍스트 예산이 설계 의도와 실측에서 벌어져 있다. `rules/` 의 조건부
로딩은 평범한 `.tsx` 프로젝트에서 사실상 무력화돼 있고(§2), `commands/dashboard.md` 는 상시
컨텍스트 전체의 1.74배인 단일 파일이면서 전체 경로 작업 1건마다 주입된다(§3). 두 결함 모두
**규범은 있는데 그것을 지키게 하는 기계가 없어서** 생겼으므로, 수정과 함께 결정적 검사를 남긴다.
부수적으로 4be8f58 가 남긴 테스트 품질 결함 2건(§4)을 같은 회차에 정리한다.

---

## 2. 결함 9 — 조건부 로딩 설계의 실측 붕괴

### 2.1 실측 (재현 명령 포함)

상시 컨텍스트 (T26 정의 = `CLAUDE.md` + `rules/README.md` + `rules/common/*.md`):

```bash
cat CLAUDE.md rules/README.md rules/common/*.md | wc -c
# => 50314        (ALWAYS_ON_CONTEXT_BUDGET_BYTES 와 정확히 일치)
```

`paths:` frontmatter 를 fnmatch 로 실제 평가한 시나리오별 적재량
(단순 `grep -l '\*\*/\*\.tsx'` 는 `**/*.test.tsx` 를 오검출해 25개/72,703B 를 낸다 —
아래는 frontmatter 를 파싱해 glob 을 평가한 값이며, 조사 문서의 24개/65,676B 와 일치한다):

| 시나리오 (Claude 가 읽는 파일) | 조건부 파일 | 조건부 B | **총 적재 B** |
|---|---:|---:|---:|
| `src/App.tsx` (평범한 웹) | 24 | 65,676 | **115,990** |
| `src/App.tsx` + `src/util.ts` | 24 | 65,676 | **115,990** |
| `src/index.ts` (Node, React 없음) | 13 | 24,945 | **75,259** |

`src/App.tsx` 시나리오의 디렉토리별 내역:

| 디렉토리 | 파일 | 바이트 | 정당한가 |
|---|---:|---:|---|
| `react/` | 4 | 24,675 | ✅ 의도됨 |
| `web/` | 7 | 16,056 | ✅ 의도됨 |
| `typescript/` | 5 | 6,791 | ✅ 의도됨 |
| **`react-native/`** | **8** | **18,154** | ❌ **결함** |

`rules/react-native/*.md` 8개 전부의 frontmatter 가 동일하다 (`sed -n '1,5p' rules/react-native/*.md`):

```yaml
---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---
```

### 2.2 9-b — react/·web/·typescript/ 는 결함이 아니다 (고치지 않는다)

`rules/README.md:5` 는 이 배포판을 "curated for a JavaScript/TypeScript + React + web stack"
이라고 선언한다. `.tsx` 를 읽는 프로젝트에서 React·web·TypeScript 규칙이 뜨는 것은 **선언된 의도의
정확한 실현**이다. 47,522B 는 크지만 그것은 「분량 문제」이지 「조건부 로딩의 오작동」이 아니다.
**결함이 아닌 것을 결함으로 고치지 않는다** — 이번 회차에서 건드리지 않는다.

`rules/react/testing.md` 가 `**/*.test.tsx` 로 이미 좁혀져 있는 것은 "테스트 파일을 열 때만 테스트
규칙" 이라는 별개의 정당한 축이지, react/ 전체를 좁혀야 한다는 선례가 아니다.

### 2.3 9-a — react-native: 트레이드오프를 정면으로

**핵심 제약**: `rules/README.md:31` 이 규정하듯 `paths:` 는 "Claude 가 그 glob 에 맞는 파일을
**읽거나 편집할 때**" 로드한다. 프로젝트에 파일이 존재하는지가 아니다. 따라서 **마커 파일
(`app.json`·`metro.config.js`·`app.config.ts`)로 프로젝트 정체성을 식별하는 방식은 성립하지
않는다** — 그 파일들은 평소 읽히지 않으므로 규칙이 사실상 죽는다.

검토한 선택지:

| 안 | 웹 누수 | RN 발동 | 평가 |
|---|---|---|---|
| A. 현행 유지 | 18,154B 항상 | 항상 | 결함 그대로 |
| B. 마커 파일 글롭만 | 0 | **거의 안 뜸** | 규칙 사망 |
| C. `screens/`·`components/` 등 경로 | 여전히 누수 | 보통 | 웹도 같은 디렉토리명을 쓴다 — 무의미 |
| D. **RN 배타 글롭 + 마커 병기** | **0** | 부분 | 아래 채택 |
| E. 기본 배포에서 제외(opt-in) | 0 | 사용자가 켤 때만 | 정직하지만 RN 사용자에게 회귀 |

**채택: D.** RN 에만 존재하고 웹에는 존재하지 않는 경로/확장자로 좁힌다:

```yaml
paths:
  - "**/app.json"
  - "**/app.config.ts"
  - "**/app.config.js"
  - "**/metro.config.js"
  - "**/*.native.ts"
  - "**/*.native.tsx"
  - "ios/**"
  - "android/**"
  - "app/**/*.tsx"          # Expo Router 규약 디렉토리
```

**이 선택의 정직한 비용**: RN 개발자가 `src/Foo.tsx` 를 편집하는 평범한 순간에는 RN 규칙이 뜨지
않는다. 발동률이 100%에서 부분으로 떨어진다. 그럼에도 D 를 고르는 이유는 **현행이 「웹 사용자
100% 오적재」이고 D 는 「RN 사용자 부분 미적재」인데, 전자는 전원에게 부과되는 비용이고 후자는
소수에게 부과되는 기회손실**이기 때문이다. 이 비대칭이 근거의 전부다.

> **사용자 판단 요청**: "가끔만 뜨는 규칙은 죽은 규칙" 이라고 본다면 **E(opt-in 제외)** 가 더
> 정직하다. 4be8f58 의 `removals.txt` 툼스톤 기계가 이미 있어 안전한 제거 경로도 존재한다.
> D 와 E 중 어느 쪽인지 승인 시 지정해 달라. **기본 제안은 D.**

효과 (D 채택 시):

| 시나리오 | 현행 | D 적용 후 | 절감 |
|---|---:|---:|---:|
| `src/App.tsx` | 115,990B | **97,836B** | −18,154B (−15.7%) |
| `src/index.ts` | 75,259B | **57,105B** | −18,154B (−24.1%) |

### 2.4 9-c — 재발 방지 기계 (T28)

T26 은 **상시** 컨텍스트만 지킨다. 조건부 적재는 아무도 안 본다 — 그래서 무너졌다. T26 과 **동일한
패턴**(상수 vs 실측 비교 + 문서 선언 정합성)으로 시나리오 래칫을 신설한다. 새 메커니즘을 발명하지
않는다.

```bash
readonly TSX_SCENARIO_CONTEXT_BUDGET_BYTES=97836   # src/App.tsx
readonly TS_SCENARIO_CONTEXT_BUDGET_BYTES=57105    # src/index.ts
```

실측은 `tests/lib/context_budget.py`(신설, python3 stdlib 전용 — 외부 의존 0 원칙 준수)가
frontmatter 를 파싱해 fnmatch 로 평가하고 합계 바이트를 stdout 에 낸다. `tests/run.sh` 의 T28 이
이를 호출해 상수와 비교한다.

---

## 3. 결함 10 — `commands/dashboard.md` 87,305B

### 3.1 실측과 선행 작업의 경계

```bash
wc -c commands/dashboard.md   # => 87305
wc -l commands/dashboard.md   # => 1315   (skills 스펙 권고 500줄의 2.6배)
```

**중요**: `docs/prps/dashboard-md-slimming.md` 가 **이미 실행됐다**. 그 PRP 는 118,619B 를
대상으로 (A) 템플릿 HTML 외부화 → `commands/dashboard_template.html`, (B) 근거 서술 →
`docs/prps/dashboard-rationale.md` 이관을 수행해 **118,619B → 87,305B** 를 달성했다.
**따라서 「덩어리를 잘라 밖으로 빼는」 쉬운 수단은 이미 소진됐다.** 남은 87,305B 는 절차·계약·
폐쇄 어휘표이며 삭제 대상이 아니다. 이번 회차의 수단은 **삭제가 아니라 지연 로드**뿐이다.

섹션별 바이트 (`## ` 헤딩 기준, 합계 87,306B ≈ 파일 크기로 검산):

| 섹션 | B | 줄 | 성격 |
|---|---:|---:|---|
| (머리말) | 1,262 | 18 | 코어 |
| 호출 규약 | 1,678 | 25 | 코어 |
| CLAUDE.md 트리거 (참고) | 2,478 | 34 | 이관 가능 |
| 보고 최소화 | 2,052 | 34 | 코어 |
| **데이터 모델 — DOM 상 표현 규격** | **16,790** | 225 | `init` 전용 |
| 진행 시각화 규격 | 4,455 | 98 | `init`·`step` |
| **`init`** | **12,361** | 184 | `init` 전용 |
| 소유권 검증 | 1,601 | 20 | 코어 (step·log·impl 공통) |
| `step` | 4,327 | 60 | `step` 전용 |
| `impl` | 8,748 | 115 | `impl` 전용 |
| `log` | 8,636 | 115 | `log` 전용 |
| **자동 발행** | **14,473** | 255 | `init` 전용 |
| `serve` | 4,384 | 57 | `serve` 전용 |
| `on`/`off` | 2,571 | 46 | 전용 |
| 로그 UI 규격 | 502 | 15 | `log` |
| 템플릿 파일 | 988 | 15 | 코어 |

섹션 간 결합도 실측 — `step`·`log`·`impl` 이 「데이터 모델」·「진행 시각화」를 참조하는지:

```
step : 내부 앵커=[소유권 검증]              '데이터 모델' 언급 0회
impl : 내부 앵커=[소유권 검증]              '데이터 모델' 언급 0회
log  : 내부 앵커=[로그 항목 스키마, 소유권 검증]  '데이터 모델' 언급 0회
```

→ **빈발 서브커맨드(step·log·impl)는 최대 덩어리 3개(데이터 모델·자동 발행·init, 합 43,624B)와
결합돼 있지 않다.** 분할 축이 서브커맨드라는 근거가 여기 있다.

### 3.2 분할 방식 — 참조 파일을 어디에 어떤 확장자로 둘 것인가

**정정 (이 절은 1차 설계에서 틀렸다).** 1차 설계는 "`.claude/commands/` 는 하위 디렉토리를 커맨드로
스캔하지 않는다(skills.md:168, :382)" 를 하중 주장으로 삼았다. **이 주장은 철회한다.** 출처를 추적한
결과:

- 실제 출처는 로컬 파일이 아니라 WebFetch 캐시다: `https://code.claude.com/docs/en/skills.md`
  (`https://code.claude.com/docs/en/slash-commands` 가 이 문서로 리다이렉트된다 — 커맨드 문서가
  스킬 문서로 **병합**됐다). 내 머신에 `skills.md` 라는 파일은 없다(`find ~/.claude -name 'skills.md'` → 0건).
- 인용한 두 대목의 **원문 그대로**는 다음과 같다.

  > (`:168`) Files in `.claude/commands/` support the same [frontmatter](#frontmatter-reference),
  > except `name` and `paths`, which Claude Code ignores in a command file. **You invoke a command
  > file by its file name.** Skills are recommended since they support additional features like
  > [supporting files](#add-supporting-files).

  > (`:382`) \| File under `.claude/commands/` \| File name without extension \|
  > `.claude/commands/deploy.md` → `/deploy` \|

- **두 대목 어디에도 하위 디렉토리를 스캔하지 않는다는 말은 없다.** "File under `.claude/commands/`"
  는 재귀를 배제하지 않는 표현이다. 문서 전체를 훑어도 `.claude/commands/` 하위 디렉토리를 다루는
  문장은 없다(`grep -n 'claude/commands/[a-z-]*/' → 0건`). 하위 디렉토리 기술은 전부 `.claude/skills/`
  와 플러그인 쪽이다. 구 판본에는 커맨드 하위 디렉토리를 네임스페이싱해 등록한다는 기술이 있었다.

→ **문서는 이 점을 부정하지 않는다. 침묵한다.** 하중 주장을 침묵 위에 세울 수 없다.

#### 확증된 사실 하나 (이 저장소에서 이미 돌아가는 배치)

`commands/dashboard_template.html` 은 `commands/` 최상위에 있고 배포되지만 **슬래시 커맨드로
등록되지 않는다.** 확장자가 `.md` 가 아니기 때문이다.

```bash
ls -la ~/.claude/commands/ | grep -i dashboard
# -rw-r--r--  87305  dashboard.md
# -rw-r--r--  55372  dashboard_template.html    <- 설치돼 있으나 /dashboard_template 은 없다
```

이것이 추측이 아닌 유일한 앵커이므로, 설계는 여기에 정박한다.

#### 3안 비교 — 「등록되는가」를 무엇으로 확증했는가

| 안 | 배치 | 등록되는가 | **확증 수단** |
|---|---|---|---|
| (a) | `commands/dashboard/*.md` | **불확정** | 문서 침묵. 구 판본은 네임스페이싱 등록을 기술 |
| (b) | `commands/dashboard_*.md` (평면) | **된다 (확실)** | `:382` 표 행이 정확히 이 경우 |
| **(c)** | **`commands/dashboard_*.txt` (평면·비-`.md`)** | **안 된다 (실증)** | **`dashboard_template.html` 현행 배치** |

- **(a) 기각.** 요구 3(등록 여부를 이번 회차에 결정적으로 확인할 수단)을 충족할 수 없다. 슬래시 커맨드
  등록 목록은 대화형 UI 상태이지 파일시스템 산출물이 아니라서, `tests/run.sh` 가 돌릴 수 있는 결정적
  검사로 만들 수 없다. **검증 불가능한 전제 위에 설계하지 않는다.**
- **(b) 기각.** 등록이 확실하다는 점은 좋지만 그 등록이 곧 비용이다 — `/dashboard_init`·`/dashboard_step`
  등 **6개가 자동완성에 노출**된다. 이들은 사용자가 직접 부를 것이 아니라 `dashboard.md` 가 Read 할
  내부 조각이므로, 커맨드로 보이는 것은 순전한 노이즈이자 오사용 유인이다.
- **(c) 채택.** 등록되지 않음이 현행 배치로 실증됐고, 하위 디렉토리를 만들지 않으므로 §3.4 의 계수
  문제도 발생하지 않는다. 세 축(확실성·네임스페이스 청결·배포 무영향) 모두에서 우세하다.

> "md = 실행 명세" 원칙과 충돌하지 않는가 — 충돌하지 않는다. 그 원칙은 **실행 명세가 md 라는 것**이지
> 참조 조각까지 반드시 `.md` 확장자를 달아야 한다는 뜻이 아니다. 파일 **내용은 그대로 마크다운**이고,
> 확장자만 커맨드 스캐너를 피한다. `dashboard_template.html` 이 이미 같은 규약 위에 있다.

또한 문서에서 확인된 비용 모델 (`:506`, `:511`):

> the rendered SKILL.md content enters the conversation as a single message and **stays there
> across later turns**

→ 호출 횟수만큼 곱해지지 않는다. 첫 주입 후 세션 끝까지 **상주**하며 매 턴 cache read 로 재청구된다
(선행 PRP 실측: 주입 58,449 토큰, 세션 청구 가중 스펜드의 21~24%). 목표 지표는 **「세션 종료 시점의
상주 바이트」**다.

`docs/prps/` 배치는 여전히 불가하다 — 실측:

```bash
grep -n 'install_directory "' install.sh
# rules / agents / commands 뿐 — docs/ 는 배포되지 않는다
```

근거 문서는 안 읽어도 무해했지만, **런타임에 반드시 Read 해야 하는 절차 문서는 배포 대상 안**에 있어야 한다.

### 3.3 목표 구조

```
commands/
├── dashboard.md                  # 코어 디스패처 (~10KB): 호출 규약 · 보고 최소화 ·
│                                 #   소유권 검증 · 템플릿 파일 · 서브커맨드→참조파일 표
├── dashboard_template.html       # (기존, 선례)
├── dashboard_init.txt            # init + 자동 발행 + 데이터 모델 + 진행 시각화
├── dashboard_step.txt            # step + 진행 시각화
├── dashboard_log.txt             # log + 로그 UI 규격
├── dashboard_impl.txt            # impl
├── dashboard_serve.txt           # serve + on/off
└── dashboard_trigger.txt         # 「CLAUDE.md 트리거(참고)」 — 어느 서브커맨드도 Read 하지 않음
```

내용은 마크다운 그대로다. 확장자만 `.txt` 이며, 그 이유를 `dashboard.md` 상단과 각 파일 첫 줄에
한 줄로 남긴다(왜를 설명하는 주석).

**절감이 실현되는가 (수용 기준의 핵심)** — 상주 바이트 기준:

| 세션 유형 | 현행 | 분할 후 | 절감 |
|---|---:|---:|---:|
| `step`·`log` 만 (기존 대시보드에 접속) | 87,305B | **~22,246B** | **−74%** |
| `init` 포함 전체 경로 1건 | 87,305B | ~79,073B | −9% |

**정직한 한계**: `init` 세션의 절감은 9%에 그친다. `init` 이 데이터 모델·자동 발행을 실제로 필요로
하기 때문이다. 이익은 **`init` 이 작업당 1회인 반면 `step`·`log` 는 6~10회이고, 재개 세션은 `init` 을
아예 부르지 않는다**는 호출 분포에서 나온다. `dashboard_init.txt` 내부 재분할은 범위 밖이다(§7).

### 3.4 install.sh / 테스트 영향 — 안 (c) 기준 재실측

안 (c) 는 **하위 디렉토리를 만들지 않는다.** 이 사실이 1차 설계의 결론을 뒤집는다.

```
(c) 평면:  ls commands/* | wc -l = 9    find commands -type f = 9   -> 일치
(a) 하위:  ls commands/* | wc -l = 11   find commands -type f = 9   -> 불일치
```
(파일 9개 = 최상위 3 + 참조 6 인 모형 디렉토리로 실측)

| 함수 | 안 (c) 에서 | 판정 |
|---|---|---|
| `copy_directory_contents` (`cp -R`) | 평면 파일 그대로 복사 | ✅ 무영향 |
| `list_missing_managed_files` (`diff -rq`) | 평면 비교 | ✅ 무영향 |
| `build_files_ledger_json` (`find -type f`) | 6개 항목 추가 | ✅ 자동 반영 |
| `install_directory` | `managed_count` 는 로그 문구 전용 | ✅ 무영향 |
| **`tests/run.sh:1170` (T22-138) `ls commands/*`** | **평면이므로 정상 작동** | ✅ **교체 불필요** |
| `COMMANDS_FILE_COUNT=10` | 10 → **16** | ⚠️ 갱신 필요 |

**1차 설계의 「`find` 로 교체」 권고는 철회한다.** 그것은 안 (a) 를 전제한 결론이었다. 안 (c) 에서는
`ls` 가 정상 동작하므로, 무관한 테스트를 건드리지 않는다(수술적 변경 원칙).

> 다만 잠재적 불일치는 기록해 둔다: `RULES_FILE_COUNT=42` 는 `find rules -type f` 와 같은 **재귀**
> 카운트인데(`rules/` 는 이미 하위 디렉토리 구조다) `commands/` 만 `ls` 기반이다. 장래 `commands/` 에
> 하위 디렉토리가 생기면 T22-138 과 T27-1(대장=재귀)이 **동시 만족 불가능**해진다. 이번엔 그런
> 디렉토리를 만들지 않으므로 **고치지 않고 §7 제외 항목에 남긴다.**

## 4. LOW 2건

### 4.1 L-1 — `tests/run.sh:5489` 중복 문구

```bash
note_failure "T27-4 (D-4): 보호는 실패가 아닌데 exit ${d4_exit}로 중단됨 — D-4 보호 중 설치가 중단됨"
```
뒷 절이 앞 절의 반복. `— D-4 보호 중 설치가 중단됨` 삭제. (`:5502` 의 manifest v2 단언은 같은
문구를 쓰지만 **거기서는 유일한 설명**이므로 유지.)

### 4.2 L-2 — `grep -qF '[보호]'` — **제기된 전제는 실측으로 반증됐다**

조사서는 `install.sh:648` 의 CLAUDE.md skip 로그 때문에 `[보호]` 가 항상 찍혀 단언이 무조건
참이라고 봤다. **틀렸다.** `:648` 은 `log_installation_plan()` 안, 즉 **DRY-RUN 경로 전용**이고
T27-4·T27-5 는 실제 설치를 돌린다.

T27-4 시나리오를 그대로 재현해 확인:

```
--- lines containing [보호]:
  [보호] rules/common/__t27_d4_modified.md — 수정된 파일이라 삭제하지 않습니다(…)
--- count: 1
```

유일한 `[보호]` 는 `install.sh:366`, 곧 **D-4 보호 그 자체**다. 단언은 공허하지 않다.

**그럼에도 고친다 (다른 이유로)**: 이 단언은 *어떤 경로가* *어떤 이유로* 보호됐는지 구분하지
못한다. D-3(`:360`)과 D-4(`:366`)가 서로의 로그를 내도 통과한다 — T27-4/T27-5 를 가르는 바로
그 축이다. T27-8 방식으로 좁힌다:

```bash
# T27-4
grep -qF "$d4_relative_path — 수정된 파일이라 삭제하지 않습니다"
# T27-5
grep -qF "$d3_relative_path — 설치 이력을 확인할 수 없어"
```

삭제하지 않는 이유: 인접한 `'툼스톤 처리: 제거 0건, 보호 1건'` 단언은 **건수**만 고정하고
**사유 문자열**은 고정하지 않으므로 흡수 관계가 아니다.

---

## 5. 영향 범위

| 파일 | 변경 | 사유 |
|---|---|---|
| `rules/react-native/*.md` (8) | frontmatter `paths:` 교체 | 9-a |
| `rules/README.md` | 조건부 로딩 절에 RN 글롭 근거 명시 | 9-a 문서화 |
| `README.md` | 시나리오 예산 2건 선언 추가 | 9-c (T28 정합) |
| `commands/dashboard.md` | 코어 디스패처로 축소 (~10KB) | 10 |
| `commands/dashboard_*.txt` (6, 신규) | 서브커맨드 참조 문서 (비-`.md` = 커맨드 미등록) | 10 |
| `install.sh:14` | `COMMANDS_FILE_COUNT` 10 → 16 | 10 |
| `tests/lib/context_budget.py` (신규) | 조건부 적재 실측기 | 9-c |
| `tests/run.sh` | T28 신설 · T27-4/5 단언 · L-1 (T22-138 은 **불변** — §3.4) | 9·10·L |

**변경하지 않는 것**: `rules/react/`·`web/`·`typescript/` frontmatter(9-b), 템플릿 HTML,
대시보드 DOM 계약·절차 의미, `docs/prps/dashboard-rationale.md`, 매니페스트 스키마 v2,
`removals.txt` 툼스톤 로직.

---

## 6. 데이터 모델 · 인터페이스

### 6.1 `tests/lib/context_budget.py` (신규, python3 stdlib 전용)

```python
Rule = NamedTuple("Rule", [("path", str), ("globs", list[str]), ("size", int)])

def parse_frontmatter_globs(path: str) -> list[str]:
    """rules 파일의 paths: frontmatter 글롭 목록. 없으면 빈 리스트(=상시 로드)."""

def load_rules(rules_root: str) -> list[Rule]:
    """rules/ 하위 모든 .md 를 Rule 로 수집한다."""

def scenario_bytes(rules: list[Rule], touched_files: list[str]) -> int:
    """touched_files 중 하나라도 매칭하는 조건부 규칙 + 상시 규칙의 총 바이트."""
```

CLI: `python3 tests/lib/context_budget.py --rules-root rules --claude-md CLAUDE.md src/App.tsx`
→ stdout 에 정수 바이트 1줄. (exit 0 성공 / 1 실패, `run.sh` 가 판정)

### 6.2 `commands/dashboard.md` 디스패치 표 (코어에 상주)

| 서브커맨드 | 실행 전 반드시 Read | 
|---|---|
| `init` | `commands/dashboard_init.txt` |
| `step` | `commands/dashboard_step.txt` |
| `impl` | `commands/dashboard_impl.txt` |
| `log` | `commands/dashboard_log.txt` |
| `serve`·`on`·`off` | `commands/dashboard_serve.txt` |

지시문은 **명령형·단수 지정**이어야 한다 ("아래 표에서 **해당 행 1개만** Read 한다. 나머지는
읽지 않는다."). 여러 개를 읽으면 절감이 소멸하므로 이것이 수용 기준이다(§8-3).

---

## 7. 제외 항목 (이번에 하지 않는 것과 이유)

1. **`rules/react/`·`web/`·`typescript/` 글롭 축소** — 결함이 아니다(§2.2). 47,522B 는 분량
   문제이고 별도 과제다.
2. **`init.md` 내부 재분할** — 데이터 모델↔자동 발행↔init 의 결합도를 실측하지 않았다. 근거 없이
   자르면 DOM 계약이 깨진다.
3. **`commands/` → `skills/` 마이그레이션** — 문서상 skills 가 디렉토리·지연 로드를 정식 지원하고
   동명 skill 이 command 를 이긴다. 그러나 `install.sh` 에 `skills/` 관리 경로·카운트·매니페스트·
   테스트를 신설해야 하는 별개 규모의 작업이다. §3.2 방식으로 목표가 달성되므로 지금은 불필요
   (YAGNI). 달성되지 않으면 그때 재검토한다.
4. **`rules/react-native/` 완전 제거(안 E)** — 사용자 승인 사항으로 남긴다(§2.3).
5. **`docs/` 배포 대상 편입** — 이번 설계는 `docs/` 를 런타임 의존시키지 않으므로 불필요.
6. **T22-138 의 `ls` → `find` 전환** — 안 (c) 는 하위 디렉토리를 만들지 않아 `ls` 가 정상 동작한다
   (§3.4 실측). 잠재적 불일치는 기록만 하고 고치지 않는다 — 무관한 테스트를 건드리지 않는다.
7. **`commands/dashboard/` 하위 디렉토리 채택** — 등록 여부가 문서로 확정되지 않는다(§3.2). 결정적
   검사로 만들 수단이 없어 기각했다.

---

## 8. 작업 순서 (implementer 용)

각 단계 끝에 `bash tests/run.sh` 를 돌려 **그 단계에서 의도한 것 외에 깨진 것이 없는지** 확인한다.

**A. LOW 정리 (가장 독립적 — 먼저 끝낸다)**
1. `tests/run.sh:5489` 의 ` — D-4 보호 중 설치가 중단됨` 삭제.
2. `:5494` 를 `grep -qF "$d4_relative_path — 수정된 파일이라 삭제하지 않습니다"` 로 교체.
3. `:5528` 을 `grep -qF "$d3_relative_path — 설치 이력을 확인할 수 없어"` 로 교체.
4. 검증: `bash tests/run.sh` 전량 통과. 추가로 두 단언이 **실제로 좁혀졌는지** 확인 —
   `install.sh:366` 문구를 일시 변조하면 T27-4 가 FAIL 해야 한다(확인 후 되돌린다).

**B. 결함 9**
5. `rules/react-native/*.md` 8개의 `paths:` 를 §2.3 의 글롭으로 교체. 본문은 손대지 않는다.
6. `tests/lib/context_budget.py` 작성 (§6.1). 순수 함수 + `if __name__ == "__main__"` 의 얇은 CLI.
7. 로컬 실행으로 §2.3 표의 수치(97,836 / 57,105)를 재현. **불일치하면 멈추고 보고** —
   상수를 실측에 맞춰 조용히 바꾸지 않는다.
8. `tests/run.sh` 에 `TSX_SCENARIO_CONTEXT_BUDGET_BYTES`·`TS_SCENARIO_CONTEXT_BUDGET_BYTES`
   상수와 T28 그룹 추가 (T26 의 구조를 그대로 복제: 실측≤상수, README 선언==상수==실측).
9. `README.md` 에 시나리오 예산 2건을 T28 이 grep 할 수 있는 고정 문구로 선언.
   **주의**: T26-2 는 `'실측 <n>B'` 매칭이 **정확히 2건**일 것을 요구한다. 새 문구는 이 패턴과
   충돌하지 않는 별도 표현을 쓰거나, T26-2 의 카운트를 함께 갱신해야 한다 — 둘 중 하나를 반드시
   선택하고 어느 쪽인지 보고한다.
10. `rules/README.md` 조건부 로딩 절에 RN 글롭 축소와 그 트레이드오프를 2~3줄로 기록.

**C. 결함 10**
11. §3.3 매핑대로 섹션을 `commands/dashboard_<이름>.txt` 6개로 **바이트 단위 그대로 이동**한다.
    문구를 다듬거나 재작성하지 않는다 — 이번 작업은 배치 변경이지 개정이 아니다.
    각 파일 첫 줄에 `<!-- 확장자가 .txt 인 이유: commands/ 의 .md 는 슬래시 커맨드로 등록된다.
    이 파일은 dashboard.md 가 Read 하는 참조 조각이므로 등록되면 안 된다. -->` 를 남긴다.
12. `commands/dashboard.md` 를 코어 + §6.2 디스패치 표로 축소.
13. `install.sh:14` `COMMANDS_FILE_COUNT` 를 `find commands -type f | wc -l` 실측치(16 예상)로 갱신.
14. **`tests/run.sh:1170` 은 건드리지 않는다.** 평면 배치이므로 `ls commands/*` 가 그대로 맞다 —
    이 단계에서 T22-138 이 통과하는지만 확인한다. 실패하면 배치가 평면이 아니라는 뜻이니 멈추고 보고.
15. 검증: 샌드박스 설치 후 (a) `dashboard_*.txt` 6개가 설치본 `commands/` 최상위에 존재,
    (b) 매니페스트 `files` 대장에 6개 항목 존재, (c) T27-1·T22-138 통과.
16. 절감 실측: §8-3 수용 기준.

**D. 마무리**
17. `bash tests/run.sh` 전량 통과.
18. 변경 요약 + 갱신된 수치표를 보고. 커밋은 검수 통과 후.

### 8-3. 수용 기준 (절감이 실현되는지 — 이것을 통과하지 못하면 분할은 무의미)

- **정량**: `wc -c commands/dashboard.md` ≤ **12,000B**, `wc -l` ≤ **300줄**.
- **정량**: `commands/dashboard.md` + `commands/dashboard_*.txt` 합계가 현행 87,305B 대비
  **+5% 이내**(이동이지 증식이 아님을 보증).
- **행동**: 실제 세션에서 `/dashboard step` 을 호출했을 때 `dashboard_init.txt`·`dashboard_impl.txt`·
  `dashboard_serve.txt` 를 **Read 하지 않는지** 확인한다. 하나라도 읽으면 디스패치 지시문이 실패한
  것이며, 표현을 더 강한 명령형으로 고쳐 재검증한다.
- **등록**: 새 세션에서 자동완성에 `/dashboard_init` 등이 **뜨지 않는지** 확인한다
  (`dashboard_template.html` 과 동일한 취급을 받아야 한다). 뜬다면 비-`.md` 전제가 깨진 것이므로
  즉시 멈추고 보고한다 — 이것이 안 (c) 의 유일한 잔여 가정이다.
- **불변**: 대시보드 산출 HTML 이 분할 전후로 동일해야 한다(DOM 계약 무변경).

---

## 9. 테스트 계획

| ID | 대상 순수 로직 | 케이스 |
|---|---|---|
| T28-1 | `scenario_bytes` (tsx) | 실측 ≤ `TSX_SCENARIO_CONTEXT_BUDGET_BYTES` |
| T28-2 | `scenario_bytes` (ts) | 실측 ≤ `TS_SCENARIO_..._BYTES` |
| T28-3 | 문서 정합 | README 선언 == 상수 == 실측 (T26-2 패턴) |
| T28-4 | `parse_frontmatter_globs` | frontmatter 없음 → `[]`(상시); 글롭 다수 → OR |
| T28-5 | 회귀 | `rules/react-native/*` 가 `src/App.tsx` 시나리오에 **불포함** |
| T22-138 | 카운트 | **기존 그대로** `ls commands/*` == `COMMANDS_FILE_COUNT`(=16). 평면 배치라 유효 |
| T27-1 | 기존 | 대장 항목 수 == rules+agents+commands+1 (참조 6개 포함) |
| T27-4/5 | 기존(강화) | 보호 사유 문자열이 D-3/D-4 로 **구별**되는지 |

T28-4·T28-5 가 순수 로직 단위 테스트의 본체다 — 글롭 평가기가 틀리면 예산 전체가 거짓이 된다.

---

## 10. 리스크와 롤백

| 리스크 | 완화 |
|---|---|
| 비-`.md` 파일이 장래에 커맨드로 등록되도록 바뀌면 `/dashboard_init` 등 6개 노출 | 현행 `dashboard_template.html` 이 같은 위험을 이미 지고 있으므로 **새로 지는 위험이 아니다**. §8-3 등록 기준으로 회차 내 확인 |
| `.txt` 확장자 때문에 참조 파일이 마크다운으로 렌더되지 않아 편집성 저하 | 내용은 마크다운 그대로. 각 파일 첫 줄 주석이 이유를 설명한다 |
| 디스패치 지시를 무시하고 참조 파일을 전부 Read → 절감 0 | §8-3 행동 기준으로 **구현 완료 전에** 검증. 실패 시 지시문 강화 |
| RN 글롭 축소로 RN 사용자에게 규칙 미발동 | 의도된 트레이드오프(§2.3). `rules/README.md` 에 명시 |
| 섹션 이동 중 절차 문구 유실 | 8-11 에서 **바이트 단위 이동**만 허용. 합계 +5% 이내 기준이 증식·유실을 동시에 잡는다 |
| T26-2 의 "정확히 2건" 단언이 README 추가로 깨짐 | 8-9 에서 명시적으로 선택·보고하게 강제 |

**롤백**: 모든 변경이 단일 브랜치 `fix/tier0-defects` 위의 커밋이므로 `git revert` 로 원복된다.
주의점 1건 — 되돌리면 **이미 설치한 사용자의 `~/.claude/commands/dashboard_*.txt` 6개가 고아로
남는다.** 되돌릴 때는 그 6개 경로를 `removals.txt` 툼스톤에 등록해야 4be8f58 의 D-1~D-5 보호
경로를 타고 안전하게 정리된다. 단계 B(결함 9)와 C(결함 10)는 서로 독립이므로 개별 revert 가능.
