# `/dashboard` 스킬 문서 슬림화 (PRP)

> 대상: `commands/dashboard.md` (77,531자 / 118,619바이트 / 1,746줄)
> 목표: 스킬 주입 토큰과 `init` 출력 토큰을 함께 줄인다. **동작·DOM 계약은 바이트 단위로 불변.**

---

## 1. 요구사항 요약

`/dashboard` 를 부르면 `commands/dashboard.md` 전문이 컨텍스트에 주입된다(실측 58,449 토큰).
주입된 뒤에는 세션이 끝날 때까지 매 턴 cache read 로 재청구되며, 직전 세션(주입 후 163턴)에서
대시보드 귀속 비용이 세션 전체 청구 가중 스펜드의 **21~24%** 였다. 게다가 문서의 33.8%를 차지하는
「템플릿 전문」(26,220자)은 **이중 비용**이다 — 주입 시 입력으로 한 번, `init` 1단계가 "한 글자도
고치지 않고 그대로 Write" 하므로 **출력 토큰으로 다시 한 번**(출력 단가는 입력의 5배).

이 작업은 두 가지를 한다.

- **A. 템플릿 외부화** — 템플릿 HTML을 별도 파일로 분리해 배포하고, `init` 은 Write 대신
  Bash `cp` 로 복사한다. 문서에서 26,220자가 빠지고, `init` 의 출력 토큰 ~19,800개가 사라진다.
- **B. 근거 서술 이관** — "왜 이 설계인가" 류 서술을 `docs/prps/` 쪽 전용 문서로 옮기고,
  원래 자리에는 **한 줄 요약 + 링크**만 남긴다. 절차·불변식·폐쇄 어휘 표는 문서에 남긴다.

**하지 않는 것**: 대시보드의 기능 변경, DOM 계약 변경, 템플릿 HTML/CSS/JS 의 단 한 바이트 수정,
`step`·`log`·`impl`·`serve`·`on`/`off` 의 절차 변경, 허브(`/hub`) 측 코드 변경.

---

## 2. 실측 근거

### 2.1 섹션별 크기 (전량 실측, 합계 = 77,531자로 검산됨)

| 섹션 | 자 수 | 비중 | 성격 |
|------|------:|-----:|------|
| **템플릿 전문** | **26,220** | **33.8%** | 산출물 원본 (A의 대상) |
| 자동 발행 (9개 소절 합) | 10,243 | 13.2% | 절차 + 임베드 스크립트 + 근거 |
| 데이터 모델 (12개 소절 합) | 11,045 | 14.2% | 계약 표 + 불변식 + 근거 |
| `init` | 5,717 | 7.4% | 절차 (A로 개정) |
| `log` | 5,093 | 6.6% | 절차 |
| 진행 시각화 규격 (6개 소절 합) | 3,948 | 5.1% | 계약 + 마크업 + 중복 CSS |
| `impl` (3개 소절 합) | 3,375 | 4.4% | 절차 |
| 헤더 + 호출 규약 + CLAUDE.md 트리거 | 3,091 | 4.0% | 계약 |
| `step` | 2,666 | 3.4% | 절차 |
| `serve` | 2,142 | 2.8% | 절차 |
| `on` / `off` | 1,650 | 2.1% | 절차 |
| 로그 UI 규격 | 1,470 | 1.9% | 대부분 템플릿 CSS/HTML 중복 |
| 소유권 검증 | 871 | 1.1% | 절차 |

### 2.2 산문 구성 (템플릿 제외 51,311자)

| 유형 | 자 수 | 비중 | 이관 가능성 |
|------|------:|-----:|------------|
| 일반 산문 (번호 절차 본문 + 근거 단락) | 29,324 | 57.1% | 부분 (근거 단락만) |
| 코드 펜스 (임베드 스크립트·마크업) | 8,653 | 16.9% | **불가** — 절차 자체 |
| 표 | 7,943 | 15.5% | **불가** — 폐쇄 어휘·계약 |
| 인용(`>`) 블록 | 4,071 | 7.9% | **대부분 가능** — 근거 서술 |
| 헤딩 | 1,321 | 2.6% | 부분 |

### 2.3 템플릿 경계 (정확)

```
commands/dashboard.md
  1243: ## 템플릿 전문
  1244: (빈 줄)
  1245: `init` 절차 1단계에서 이 내용을 그대로 `.claude/dashboard.html` 로 Write 한다.
  1246: (빈 줄)
  1247: ```html          ← 펜스 열기
  1248: <!doctype html>   ← 템플릿 본문 시작
  ...
  1744: </html>          ← 템플릿 본문 끝
  1745: ```              ← 펜스 닫기
  1746: (파일 끝)
```

검증 완료: `sed -n '1248,1744p' commands/dashboard.md` → 26,133자(본문 26,132 + 개행 1),
497줄, `<!doctype html>\n` 으로 시작해 `</html>\n` 으로 끝나며, 원본의 **연속 부분 문자열**이다.
→ 템플릿 파일 생성은 무손실·무편집 추출로 가능하다.

### 2.4 `init` 이 실제로 바꾸는 바이트 (라이브 산출물 대조 실측)

이 저장소의 실제 `.claude/dashboard.html` 과 템플릿 본문을 diff 한 결과 **변경 줄은 20줄뿐**이다.
`init` 이 건드리는 지점은 **정확히 6줄 + 삽입된 N개 `<li>`** 다. 이것이 개정 절차의 완전한 명세다.

| 템플릿 원본 줄 (본문 기준 줄번호) | 원본 값 | `init` 후 |
|---|---|---|
| 209 `<span class="project-name" id="dz-project-name">` | `프로젝트` | `coding-harness` |
| 219 `<h1 id="dz-title">` | `세션 제목` | 실제 제목 |
| 220 `<div … id="dz-progress-bar" style="width:0%">` | `width:0%` | **변화 없음** |
| 221 `<div class="pct" id="dz-progress-pct">` | `0/0 · 0%` | `0/4 · 0%` |
| 222–223 `<ol class="steps" id="dz-steps">` / `</ol>` | 빈 `<ol>` | `<li>` N개 삽입 (선두 공백 **6칸**) |
| 236 `<ul class="log" id="dz-log" data-owner-token="" data-server-port="">` | 빈 두 속성 | 토큰 각인 (포트는 「자동 발행」이 별도로 각인) |
| 238 `<div class="foot" id="dz-updated">` | `갱신: -` | `갱신: 2026-08-24 17:28` |

실측으로 드러난 **현행 문서의 두 가지 모호성** (개정이 함께 제거한다):

1. **진행률 바는 치환 대상이 아니다.** 현행 6단계는 "`style` 을 `width:0%` 로 치환"이라 지시하지만
   템플릿 원본이 이미 `width:0%` 다 — `old_string == new_string` 인 Edit 은 실패한다. 라이브
   산출물에서도 이 줄은 변경되지 않았다. 개정 절차는 이 줄을 **건드리지 않는다**고 명시한다.
2. **`<li>` 들여쓰기가 문서에 없다.** 문서 5단계의 예시는 중첩 코드펜스 안이라 선두 공백이
   5칸으로 보이지만, 실제 산출물은 **6칸**이다. 지금까지는 세션이 템플릿 문맥에서 추론해 맞춰
   왔을 뿐 문서가 정한 값이 아니다. 개정 절차는 6칸을 **명시**한다.

### 2.5 소비자 (DOM 계약)

- `hub/bin/hub_parse.py` — 줄 단위 정규식으로 `dz-title`·`dz-progress-pct`·`dz-updated`·
  `dz-step-{n}`·`dz-cell-{g}-{p}`·`dz-impl-{k}` 를 읽는다(티어 1).
- `hub/bin/hub_collect.py` — `.claude/dashboard.html` 을 경로로 읽는다
  (`PROJECT_DASHBOARD_RELATIVE_PATH`).
- 허브 상세 패널 — 이 파일을 iframe 으로 직접 서빙한다.

**템플릿 바이트가 동일하고 `init` 의 치환 결과가 바이트 동일하면 이 세 소비자에 영향은 0이다.**
그럼에도 §9 에 회귀 검증을 넣는다.

---

## 3. 영향 범위 (파일 목록)

| 파일 | 조작 | 이유 |
|------|------|------|
| `commands/dashboard_template.html` | **신설** | 템플릿 본문 26,132자를 무편집 추출 (A) |
| `commands/dashboard.md` | 수정 | 「템플릿 전문」 절 제거 + 포인터 삽입(A), `init` 절차 개정(A), 근거 이관(B) |
| `docs/prps/dashboard-rationale.md` | **신설** | B의 이관 목적지 (§6) |
| `install.sh` | 수정 | `COMMANDS_FILE_COUNT` 9→10, `report_global_command_overlap` 의 `*.md` 글롭 확장 |
| `tests/run.sh` | 수정 | T22 블록의 grep 대상을 합본 파일로 전환 + 신규 회귀 4건 (§9) |
| `README.md` | 수정 | commands 파일 수 9→10, 합계 51→52, `dashboard` 줄 수 표기, 디렉토리 트리 |
| `docs/prps/dashboard-md-slimming.md` | 신설 | 이 문서 |

**미영향 (변경하지 않는다)**

- `hub/**` 전체 — 템플릿 바이트가 같으므로 파서·수집기·서버 모두 무변경
- `tests/hub/**` — 픽스처는 산출물 `dashboard.html` 이며 `dashboard.md` 를 참조하지 않는다
  (전수 확인: `tests/hub/` 안의 `dashboard.md`·템플릿 참조는 0건)
- `commands/hub.md`, `commands/harness-update.md` — `dashboard.md` 를 참조하지 않는다
- `CLAUDE.md` — `/dashboard` 호출 규약이 바뀌지 않으므로 무변경
- `docs/prps/session-dashboard.md` — 과거 시점 스냅샷이므로 **손대지 않는다** (근거 §5.3)
- `.gitignore` — `commands/*.html` 을 제외하지 않으므로 추가 조치 불필요 (확인 완료)

---

## 4. 파일 구조

```
coding-harness/
├── commands/
│   ├── dashboard.md                 # 슬림화된 절차 문서 (목표 ~39,800자)
│   ├── dashboard_template.html       # 신설. 26,132자. 무편집 추출본
│   └── … (기존 8개 .md)
├── docs/prps/
│   ├── dashboard-md-slimming.md      # 이 PRP
│   ├── dashboard-rationale.md        # 신설. B의 이관 목적지
│   └── session-dashboard.md          # 손대지 않음 (역사적 스냅샷)
├── install.sh                        # COMMANDS_FILE_COUNT 10
└── tests/run.sh                      # T22 합본 전환
```

**설치본 배치** — 기존 메커니즘을 그대로 탄다. `install.sh` 는 `cp -R commands/. <target>/` 로
`commands/` **전체**를 복사하므로 `.html` 파일은 코드 변경 없이 함께 배포된다.

| scope | 배치 경로 |
|-------|----------|
| `--scope user` | `~/.claude/commands/dashboard.md` + `~/.claude/commands/dashboard_template.html` |
| `--scope project` | `<project>/.claude/commands/dashboard.md` + `…/dashboard_template.html` |

`install.sh` 의 검증(`verify_managed_files_installed`)은 `diff -rq` 기반이라 신규 `.html` 도
자동으로 "누락·불일치" 검사 대상이 된다 — **문서와 템플릿이 따로 배포될 수 없다**는 보장이
공짜로 따라온다. 이것이 새 디렉토리를 만들지 않고 `commands/` 에 두는 결정적 이유다(§5.1).

---

## 5. 설계 결정과 근거

### 5.1 D1 — 템플릿은 `commands/dashboard_template.html` 에 둔다

- 이름은 기존 선례 `hub/bin/hub_template.html` 을 따른다(같은 저장소, 같은 역할, 같은 명명).
- 위치를 `commands/` 로 잡으면 `cp -R commands/.` 가 이미 전량 복사하므로 **install.sh 에
  구조적 변경이 없다**. 새 최상위 디렉토리(`templates/` 등)를 만들면 `install_directory` 호출 추가,
  새 타깃 경로, 새 상수, 새 테스트, README 트리 갱신이 전부 딸려 온다 — 얻는 것 없이 표면만 늘어난다(YAGNI).
- `diff -rq` 기반 검증이 문서·템플릿의 **동반 배포를 강제**한다(§4).
- 필요한 `install.sh` 변경은 두 줄뿐이다.
  - `readonly COMMANDS_FILE_COUNT=9` → `=10` (로그 문구·manifest `files_count.commands` 용)
  - `report_global_command_overlap` 의 `for command_file in "$REPO_ROOT/commands"/*.md` →
    `…/commands"/*` — 템플릿이 전역/프로젝트 사이에서 어긋났을 때 경고가 나가야 한다.
    현행 글롭은 `.md` 만 보므로 템플릿 드리프트가 조용히 넘어간다.

**감수하는 리스크**: `~/.claude/commands/` 에 `.md` 아닌 파일이 놓인다. Claude Code 는 커맨드로
`.md` 만 등록하므로 `.html` 은 무시될 것으로 보이나, **이것은 문서로 확인한 사실이 아니다** —
롤아웃 체크리스트(§10)에 "설치 후 커맨드 목록에 `dashboard_template` 이 나타나지 않는지 눈으로
확인"을 넣는다. 만약 나타난다면 D1을 폐기하고 `~/.claude/dashboard/` 로 옮긴다(되돌리기 비용은
경로 문자열 1개 + install.sh 블록 1개).

### 5.2 D2 — `init` 은 `cp` + **Bash 내 python 치환**으로 바꾼다 (후보 (a) 채택)

**문제**: `cp` 로 만든 파일은 이 세션에서 Read 한 적이 없으므로 **Edit 도구가 거부한다.**

| 후보 | 내용 | 판정 |
|------|------|------|
| **(a)** | `cp` 후 Bash 1회로 python 치환 (앵커 등장 횟수 == 1 검증 포함) | **채택** |
| (b) | `cp` 후 앵커 근처만 `offset/limit` Read 하고 Edit | 기각 |
| (c) | `cp` 후 파일 전체 Read 하고 기존 Edit 6회 유지 | 기각 |

**(b) 기각 근거**: 앵커 6개가 파일 전역에 흩어져 있다(본문 줄 209·219·221·222·236·238). 209~238은
좁지만 `<li>` 삽입까지 포함하면 창(window)이 여러 개 필요하고, Read 호출 수가 앵커 수에 비례해
늘어난다. 결정적 절차를 만들려면 "어디를 몇 줄 읽어라"를 앵커마다 문서에 못 박아야 하는데, 그
줄 번호는 템플릿을 한 줄이라도 고치면 전부 거짓이 된다 — **문서가 템플릿의 줄 번호에 결합된다.**

**(c) 기각 근거**: 이 방식은 출력 19,800 토큰을 입력 ~19,800 토큰으로 바꾼다. 단가만 보면
5배 이득이지만, 그 20K가 **세션이 끝날 때까지 컨텍스트에 남아 매 턴 cache read 로 재청구된다** —
우리가 지금 고치려는 바로 그 병목이다(§2 의 21~24%). 163턴 기준으로 계산하면 (c)는 (a)보다
비싸다(§8.2). 템플릿을 **컨텍스트에 한 번도 들이지 않는 것**이 이 작업의 핵심이며, (a)만 그렇게 한다.

**(a) 채택의 추가 근거**: 메인 세션이 오늘 실제로 이 방식으로 `init` 을 수행해 동작을 확인했다.
추측이 아니라 실행된 경로다.

### 5.3 D3 — 근거 이관 목적지는 **새 문서** `docs/prps/dashboard-rationale.md`

`docs/prps/session-dashboard.md` 에 합치지 않는다. 그 문서는 **1라운드 시점의 스냅샷**이고 현재
사실과 이미 어긋나 있다 — 확인된 불일치:

- 제목: `### 동적(치환 대상) — 7 셀렉터 (변동 없음)` → 현재는 **6 셀렉터**
- `### 세션 구분 항목`·`### 7. 탭 바는 두 번째 세션부터 만든다`·`#dz-log[data-current-session]`
  → 세션 탭 UI 는 이후 **전면 삭제**됐고, `tests/run.sh` T22-8·T22-14·T22-18 이 그 부활을 막고 있다

역사적 PRP 를 현재 사실로 덮어쓰면 "그때 무엇을 결정했는가"라는 기록 가치가 사라진다. 저장소에는
이미 `docs/prps/dashboard-availability-check-gap.md` 처럼 라운드 PRP 가 아닌 **분석·참조 문서**를
`docs/prps/` 에 두고 `CLAUDE.md` 에서 링크하는 선례가 있다. 같은 자리에 같은 방식으로 둔다.

새 문서의 구조: 대시보드 관련 PRP 14건에 흩어진 근거의 **색인 + 이관된 서술 본문**. 앵커를 안정적으로
유지해야 하므로(dashboard.md 가 절 단위로 링크한다) 헤딩은 이관 대상 절 이름을 그대로 쓴다.

### 5.4 D4 — 남기는 것과 옮기는 것의 판정 기준

이 문서는 **과거 실패(검수 지적·실측 사고)를 막으려고 근거를 인라인한 역사**가 있다. 근거를 걷어내는
작업은 그 역사를 되감을 위험을 안는다. 그래서 기준을 먼저 고정한다.

**남긴다 (문서에서 제거하면 절차가 비결정적이 되는 것)**

1. **불변식 1~6, 8, 9, 10 의 진술문** — 다만 진술 뒤에 붙은 여러 단락의 정당화는 옮긴다.
2. **폐쇄 어휘 표 전부** — `ABSENT`/`RECENT`/`STALE`, `MINE`/`FOREIGN`/`SKIP`,
   `REUSE`/`FREE`/`NONE`, `HUB`/`NOHUB`, `FOCUSED`/`NOTFOUND`/`UNSUPPORTED`.
   이 표들이 절차의 결정성을 담보한다.
3. **모든 임베드 스크립트·마크업 원문** — 포트 스캔 python, 허브 생존 판정 python, AppleScript,
   `pkill` 명령, 매트릭스 마크업, 로그 항목 스키마, `log` 워크드 예시.
4. **셀렉터 계약 표**(동적 6 + impl 3 + 정적 요소) — 소비자(`/hub`)와의 계약이다.
5. **번호 붙은 절차 본문 전체** — `init`·`step`·`impl`·`log`·`serve`·`on`/`off`.
6. **"지우지 마라" 류의 한 줄 경고** — `|| true` 를 지우지 마라, `sleep 61` 을 지우지 마라,
   `is running` 검사를 지우지 마라, `--bind 127.0.0.1` 생략 금지. 한 줄이고, 그 자리에 없으면
   지워진다.

**옮긴다 (읽지 않아도 절차를 정확히 수행할 수 있는 것)**

- "왜 이 구조인가" 설계 정당화 단락
- 특정 검수 회차·PRP 를 인용한 이력 서술 (`검수 m2`, `R1 GOTCHA 3`, `§3.2 후방 호환 불변식` 등)
- 템플릿 내부 CSS/JS 의 동작 설명 — **템플릿이 외부 파일이 된 이상 그 파일 쪽 관심사다**
- 대안을 기각한 이유의 서술

**이관 자리마다 남기는 것**: `> 근거: <한 줄 요약> — [dashboard-rationale.md#앵커](…)`
한 줄. 요약문은 링크를 열지 않아도 "무엇을 조심해야 하는지"가 전달되게 쓴다. 링크만 남기면
근거를 인라인했던 이유가 무력화된다.

### 5.5 D5 — 디자인 패턴을 도입하지 않는다

새 추상화·새 레이어·새 간접층을 만들지 않는다. 변경의 실체는 (i) 파일 하나 쪼개기,
(ii) 절차의 도구 선택 교체(Write→cp+치환), (iii) 산문 이동 세 가지뿐이다. 템플릿 버전 관리,
템플릿 변수 엔진, 다중 템플릿 지원 같은 것은 요구에 없다(YAGNI).

---

## 6. 이관 대상 — 섹션별 목록 (무엇을 어디로)

`→ RAT` = `docs/prps/dashboard-rationale.md` 로 이관 후 한 줄 요약 + 링크 잔류.
`절감` 은 현행 자 수 - 잔류 자 수의 추정치다.

| 현행 절 | 현행 자 수 | 처분 | 절감(추정) |
|---|---:|---|---:|
| **템플릿 전문** | 26,220 | **삭제 → `commands/dashboard_template.html`**. 자리에 포인터 절(경로·해결 순서·"바이트 무편집" 불변식·링크) ~600자 | **25,620** |
| 폴링 동기화 계약 | 1,869 | → RAT. 템플릿 JS 와 DOM 사이 계약이고 어떤 절차도 이 표를 조회하지 않는다. 「grep 유일성 불변식」 진술문은 **잔류** | 1,600 |
| 로그 UI 규격 (접기/펼침/필터) | 1,470 | 「펼침 정책」(`log` 1단계의 전제)만 잔류. CSS·HTML 스니펫은 템플릿 중복이므로 → RAT | 1,100 |
| 매트릭스 CSS | 1,067 | → RAT. 템플릿 `<style>` 의 **글자 단위 사본**이다. 자리에 "매트릭스 CSS 는 템플릿에 상주한다" 1줄 | 950 |
| 정적 요소 추가 (표 + 「왜 `.wrap` 바깥인가」) | 1,494 | 표는 압축 잔류, 인용 블록 → RAT | 900 |
| 갱신 모드 | 1,251 | `UpdateMode` 정의 블록 + 플로팅 가능 조건 잔류. PiP 창 높이 측정·`NotAllowedError` 실측 서술 → RAT | 900 |
| 불변식 8·9·10 정당화 | 1,281 | 진술문 잔류, 정당화 단락 → RAT | 830 |
| `data-server-port`·`data-owner-token` 해설 2단락 | 950 | 값 도메인·"빈 문자열 == 부재" 규칙 잔류, 나머지 → RAT | 700 |
| 자동 발행 — 근거 산문 | 10,243 중 | 스크립트·표·"지우지 마라" 전량 잔류. 티어 폴백 정당화·경합 설명 → RAT | 2,000 |
| `init` — 인용 블록 및 근거 | 5,717 중 | 절차 전량 잔류(단, §7로 개정). "왜 항상 새로 만드는가"·"왜 이 순서인가" → RAT | 900 |
| `step`·`impl`·`log` 인용 블록 | 11,134 중 | 절차·표·워크드 예시 전량 잔류. 도입 인용 블록 → RAT | 1,200 |
| 개념 모델·열 확정 부속 설명 | 847 중 | 정의 잔류, 관례 서술 → RAT | 400 |
| **합계** | | | **≈ 37,100** |

### 6.1 크기 목표와 주입 토큰 추정

실측 환산비 **1.32자/토큰** (77,531자 ÷ 58,449토큰) 기준.

| 단계 | 본문 자 수 | 주입 토큰 | 현행 대비 |
|---|---:|---:|---:|
| 현행 | 77,531 | 58,449 | — |
| A만 (템플릿 외부화) | ~51,900 | ~39,300 | **−32.7%** |
| **A + B (목표)** | **~39,800** | **~30,200** | **−48.3%** |

**의뢰서의 "A+B ≈ 60~65%" 추정은 달성하지 못한다고 판단한다 — 이것이 승인 필요 사항이다.**
60% 절감은 본문 30,900자를 뜻하는데, §2.2 실측에 따르면 **코드 펜스 8,653 + 표 7,943 + 헤딩
1,321 = 17,917자가 절차 자체**이고 여기에 번호 절차 본문이 더해진다. 30,900자까지 내려가려면
절차 산문을 대량으로 깎아야 하고, 그것은 요구 5(스킬 문서의 자기완결성)와 정면으로 충돌한다.
48%를 채택하고 자기완결성을 지키는 쪽을 권한다. §11.2 에 60%까지 가는 대안(C안)과 그 기각 근거를 적었다.

---

## 7. `init` 절차 개정 (상세 명세)

### 7.1 데이터 모델 / 인터페이스 변화 — **없음**

- `/dashboard` 의 호출 규약(frontmatter `argument-hint` 포함) **무변경**
- DOM 계약(동적 6 셀렉터 + impl 3 + 정적 요소 + 불변식 1~10) **무변경**
- 산출물 `.claude/dashboard.html` **바이트 동일**
- `hub_parse.py`·`hub_collect.py`·허브 상세 패널의 입력 **무변경**

바뀌는 것은 **동일한 바이트를 만드는 도구 선택**뿐이다: Write 1회 + Edit 6회 → Bash 2회.

### 7.2 개정된 1단계 — 자리 비우기 + 템플릿 복사 + 이름·토큰 획득 (Bash 1회)

```bash
mkdir -p .claude && rm -f .claude/dashboard.html
dz_template=""
for dz_candidate in "$HOME/.claude/commands/dashboard_template.html" \
                    ".claude/commands/dashboard_template.html"; do
  if [ -f "$dz_candidate" ]; then dz_template="$dz_candidate"; break; fi
done
if [ -z "$dz_template" ]; then echo NOTEMPLATE; else
  cp "$dz_template" .claude/dashboard.html \
    && basename "$PWD" \
    && od -An -N4 -tx1 /dev/urandom | tr -d ' \n' && echo
fi
```

**출력 계약 (현행과 동일한 앵커를 유지한다)**

| 출력 | 의미 | 행동 |
|------|------|------|
| `NOTEMPLATE` (1줄) | 두 경로 모두에 템플릿이 없다 | **보고 후 중단.** `install.sh --scope user` 또는 `--scope project` 재실행을 안내한다. 추측해서 템플릿을 손으로 만들지 않는다 |
| 2줄 | 첫 줄 = 프로젝트 표시 이름, **마지막 줄의 8글자** = 소유 토큰 | 2단계로 |

- **해결 순서가 전역 우선인 이유**: 커맨드 우선순위 자체가 전역 > 프로젝트다(README 「커맨드
  우선순위는 전역이 프로젝트를 이긴다」). 실행 중인 `dashboard.md` 가 전역 사본일 가능성이 높으므로
  템플릿도 전역을 먼저 본다 — 문서와 템플릿이 서로 다른 설치본에서 짝지어지는 경우를 최소화한다.
- 출력 줄 수와 "첫 줄 = 이름 / 마지막 줄 = 토큰" 앵커는 **현행과 글자 하나까지 같다**. 템플릿
  경로를 출력에 추가하지 않는 이유가 이것이다 — 앵커가 흔들리면 2단계 이후가 전부 흔들린다.
- `rm -f` 를 유지한다. `cp` 는 기존 파일을 덮어쓰지만, 「먼저 비우고 새로 만든다」는 절차의
  불변식(`init` 은 보존하지 않는다)을 명령 자체로 표현하는 쪽이 낫다.

### 7.3 개정된 2단계 — 모든 값 치환을 한 번에 (Bash 1회)

현행 2·5·6·7·8단계(Edit 6회)를 아래 **단일 호출**로 대체한다. 3·4단계(인자 파싱, 열/칸 수 확정)는
순수 판단이므로 그대로 남되 이 호출보다 앞선다.

```bash
python3 - <<'PY'
import html, pathlib

# 세션이 채우는 유일한 부분. 문자열은 JSON 규칙으로 이스케이프한다(\\ 와 \").
values = {
    "project_name": "coding-harness",
    "title": "dashboard.md 슬림화",
    "progress_text": "0/4 · 0%",
    "updated_text": "갱신: 2026-08-24 17:28",
    "owner_token": "40fc3c16",
    # <ol>/</ol> 또는 <table>/</table> 을 포함한 완성된 교체 블록. 선두 공백까지 그대로.
    "steps_block_lines": [
        "    <ol class=\"steps\" id=\"dz-steps\">",
        "      <li id=\"dz-step-1\" class=\"active\"><span class=\"num\">1</span>설계<span class=\"chip\">진행중</span><span class=\"step-detail\"></span></li>",
        "      <li id=\"dz-step-2\" class=\"wait\"><span class=\"num\">2</span>검수<span class=\"chip\">대기</span><span class=\"step-detail\"></span></li>",
        "    </ol>",
    ],
}

def escaped(key):
    return html.escape(values[key], quote=False)

replacements = [
    ('  <span class="project-name" id="dz-project-name">프로젝트</span>',
     '  <span class="project-name" id="dz-project-name">%s</span>' % escaped("project_name")),
    ('    <h1 id="dz-title">세션 제목</h1>',
     '    <h1 id="dz-title">%s</h1>' % escaped("title")),
    ('    <div class="pct" id="dz-progress-pct">0/0 · 0%</div>',
     '    <div class="pct" id="dz-progress-pct">%s</div>' % values["progress_text"]),
    ('    <ol class="steps" id="dz-steps">\n    </ol>',
     "\n".join(values["steps_block_lines"])),
    ('    <ul class="log" id="dz-log" data-owner-token="" data-server-port=""></ul>',
     '    <ul class="log" id="dz-log" data-owner-token="%s" data-server-port=""></ul>'
     % values["owner_token"]),
    ('  <div class="foot" id="dz-updated">갱신: -</div>',
     '  <div class="foot" id="dz-updated">%s</div>' % values["updated_text"]),
]

path = pathlib.Path(".claude/dashboard.html")
text = path.read_text(encoding="utf-8")
for anchor, replacement in replacements:
    found = text.count(anchor)
    if found != 1:
        print("ANCHOR-FAIL %d %s" % (found, anchor.strip()[:56]))
        raise SystemExit(1)
    text = text.replace(anchor, replacement)
path.write_text(text, encoding="utf-8")
print("OK")
PY
```

**설계 근거 (문서에 함께 적을 것)**

- **`<<'PY'` 인용 heredoc** — 셸이 확장을 **전혀** 하지 않는다. 사용자 제목에 `$`·`` ` ``·`"`·`'`
  이 들어와도 셸 주입 경로가 생기지 않는다. Write→Edit 방식에는 없던 위험을 이 한 가지 선택으로 없앤다.
  값은 python 이중 인용 문자열이므로 이스케이프 규칙은 `\\` 와 `\"` 둘뿐이다.
- **`html.escape(s, quote=False)`** — `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;` 를 그 순서로 수행한다.
  현행 문서가 사람에게 지시하던 규칙과 **정확히 같은 변환**이며, 순서 실수의 여지를 없앤다.
- **앵커 등장 횟수 == 1 검증** — 하나라도 어긋나면 `ANCHOR-FAIL <횟수> <앵커>` 를 출력하고
  **파일을 쓰지 않고** 종료한다. 부분 치환된 대시보드가 남지 않는다. 폐쇄 어휘는 `OK` 와
  `ANCHOR-FAIL` 둘뿐이다(문서의 기존 관례와 동일).
- **진행률 바를 건드리지 않는다** — 템플릿이 이미 `width:0%` 다(§2.4).
- **선형/매트릭스 분기가 스크립트에서 사라진다** — `steps_block_lines` 라는 **값**의 차이로
  흡수된다. 코드 경로가 하나이므로 검증할 분기가 줄어든다. 이는 폴링 동기화가
  `#dz-steps,#dz-matrix` 셀렉터 하나로 두 분기를 흡수하는 것과 같은 구조다.
- **들여쓰기를 값에 명시**한다 — `<ol>`/`</ol>` 은 4칸, `<li>` 는 6칸(§2.4 실측).

`ANCHOR-FAIL` 처리 규칙(문서에 명시): 템플릿이 손상됐거나 설치본이 낡은 것이다. **다른 앵커를
추측해서 고치지 않고** 보고 후 중단하며, 재설치를 안내한다.

### 7.4 후속 단계

- 9단계 「자동 발행」, 10단계 「보고」는 **무변경**. `data-server-port` 각인은 지금처럼 「포트 각인」
  하위 절차가 별도로 수행한다(이 절차는 `grep` + Edit 을 쓰며, 그 시점에는 파일이 이미
  §7.3 에 의해 존재하나 **Read 되지 않았다**).
  → **주의**: 「포트 각인」 2단계의 Edit 도 같은 제약에 걸린다. 다만 그 절차는 1단계에서
  `grep -n 'id="dz-log"'` 로 **줄 전문을 읽고** 그것을 `old_string` 으로 쓴다. Edit 도구의 제약은
  "세션이 Read 하지 않은 파일"이므로, `grep` 만으로는 충족되지 않을 수 있다.
  **이 항목은 구현 전 확인이 필요하다 — §12 미결 질문 Q1.**

---

## 8. 기대 효과

### 8.1 `init` 1회당 출력 토큰

| | 출력 문자 | 출력 토큰(1.32자/토큰) |
|---|---:|---:|
| 현행 (템플릿 전문 Write) | 26,132 | ~19,800 |
| 개정 (치환 스크립트 + 값) | ~2,400 | ~1,800 |
| **절감** | | **~18,000** |

### 8.2 (c)안을 기각한 산술

기준 단가비: 출력 = 기본 입력의 5배, cache write = 1.25배, cache read = 0.1배.

| 방식 | 비용 성분 | 163턴 세션의 기본 입력 환산 |
|---|---|---:|
| (a) 채택 — 템플릿을 컨텍스트에 안 들인다 | 출력 1,800 × 5 | ~9,000 |
| (c) 전체 Read — 20K 가 컨텍스트에 상주 | 19,800 × (1.25 + 163×0.1) | ~347,000 |

(c)는 (a)보다 한 자릿수 이상 비싸다. "출력이 입력의 5배"만 보면 (c)가 이득처럼 보이는 것이
이 결정의 함정이며, **cache read 가 턴 수만큼 누적된다**는 사실이 결론을 뒤집는다.

### 8.3 주입 토큰

§6.1 참조 — 58,449 → ~30,200 (−48.3%). 163턴 기준 cache read 절감분은 기본 입력 환산
28,249 × 16.3 ≈ **460,000** 으로, 이 작업의 지배적 이득이다.

---

## 9. 테스트 계획

### 9.1 현황 실측 — T22 의 노출 범위

`tests/run.sh` 의 `test_dashboard_template_integrity()`(1048~2195행, 하위 검증 T22-1~T22-133)가
`commands/dashboard.md` 를 grep 한다. 실측 분류:

| 분류 | 건수 | 템플릿 외부화 시 |
|---|---:|---|
| 패턴이 **템플릿 본문에만** 존재 | **51** | dashboard.md 를 계속 grep 하면 **전부 실패** |
| 패턴이 산문에만 존재 | 40 | 영향 없음 |
| 양쪽에 존재 | 37 | 통과는 유지(단, 계수형은 §9.3) |
| 역방향(매칭되면 실패) | **24** | dashboard.md 만 grep 하면 **전부 공허해진다** |

역방향 24건이 가장 위험하다. `class="legend"`·`session-head`·`label[for^="dzs-"]`·
`DZ:SESSION-RULES`·`dz-gate-`·`0.0.0.0`·`[id="dz-`·`dz-subtitle`·`setItem('dzh-theme'`·
`ol.impl-tasks`·`body.dz-pip #dz-impl-card` 등은 **템플릿 내용의 부활을 막는** 감시자다. 템플릿이
파일을 떠난 뒤에도 `dashboard.md` 만 본다면 그 감시는 영원히 통과하며 아무것도 지키지 않는다.
이것은 `rules/common/karpathy-guidelines.md` 가 실패 사례로 기록한 바로 그 형태
(「검증을 추가할 때 그 검증이 실제 환경에서 성립하는지 먼저 확인한다」)다.

`T23`(2196행~)·`T25`(2312행~)의 `dashboard.md` 참조는 **전부 산문 대상**임을 실측 확인했다
(2238·2260·2266·2272·2387·2390행 + 비-grep 3건). **수정 불필요.**

### 9.2 채택 방침 — 합본(union) 파일 1개로 전환

T22 블록 선두에 합본을 만들고, 블록 안의 `"$dashboard_command_file"` 를 **기계적으로**
`"$dashboard_union_file"` 로 바꾼다.

```bash
local dashboard_command_file="./.claude/commands/dashboard.md"
local dashboard_template_file="./.claude/commands/dashboard_template.html"
local dashboard_union_file="$sandbox/dashboard_union.txt"
cat "$dashboard_command_file" "$dashboard_template_file" > "$dashboard_union_file"
```

**이 변환이 동치임을 보장하는 근거** (각각 확인 완료)

1. 합본의 내용은 분리 전 단일 파일과 **같은 문자 집합**이다(순서도 문서→템플릿으로 동일).
   → 정방향 91건, 역방향 24건 모두 판정이 보존된다.
2. **계수형 검증**의 총합이 보존된다(§9.3).
3. **줄 번호 순서 비교** 검증(T22-37 `.wrap` 범위, T22-113 `<head>`↔`<body>`, T22-114,
   T22-121/122 헤더 순서)은 전부 `| tail -1` 또는 `| head -1` 로 얻은 값들의 **상대 비교**이고,
   해당 앵커가 **모두 템플릿 영역에만** 존재한다(§9.1 의 51건 목록에 포함). 템플릿이 합본의
   뒤쪽에 통째로 들어가므로 상대 순서는 그대로다.
4. T22-132 의 `sed -n '/^### 로그 항목 스키마/,/^### 갱신 모드/p'` 구간 추출은 두 마커가 모두
   문서 영역에 있으므로 합본에서도 같은 구간을 뽑는다.

이 방침을 택한 이유: 152개 assertion 을 손으로 "이건 문서, 이건 템플릿"으로 나누면 51+24건에서
판정 실수가 나기 쉽고, 실수는 **조용한 통과**로 나타나 발견되지 않는다. 합본은 변경량이
`local` 3줄 + 변수명 일괄 치환으로 끝나고 동치가 위 4개 근거로 증명된다.

### 9.3 계수형 검증 — 분리 전후 실측치

| 검증 | 기대값 | 산문 | 템플릿 | 합본 | 판정 |
|---|---:|---:|---:|---:|---|
| T22-120 `box-shadow:inset 0 0 0 1px var(--accent)` | 3 | 1 | 2 | **3** | 합본으로 보존 |
| T22-32 `requestWindow` | 1 | 0 | 1 | **1** | 합본으로 보존 |
| T22-99 `isEmbedded` | 2 | 0 | 2 | **2** | 합본으로 보존 |
| T22-133 후방 호환 `.detail` 예시 | 2 | 2 | 0 | **2** | 합본으로 보존 |

주의: T22-120 의 기대값 3은 "매트릭스 done 셀 사본 2"를 전제하며, 그 사본 하나가 §6 에서
**이관 대상인 「매트릭스 CSS」 절**이다. B를 수행하면 산문 쪽 1건이 사라져 합본 계수가 **2**가 된다.
→ **T22-120 의 기대값을 3에서 2로 내리고, 주석의 근거 문장("li.done .num 1 + 매트릭스 done 셀
사본 2" → "li.done .num 1 + 매트릭스 done 셀 1, 문서 사본은 dashboard-rationale.md 로 이관")을
함께 고친다.** 기대값만 고치고 주석을 남기면 다음 사람이 사본 누락으로 오독한다.

### 9.4 신규 회귀 검증 (T22 에 추가)

| ID | 검증 | 실패 시 막는 회귀 |
|---|---|---|
| T22-134 | `commands/dashboard_template.html` 이 설치본에 존재하고 `<!doctype html>` 로 시작해 `</html>` 로 끝난다 | 템플릿 미배포 / 잘린 추출 |
| T22-135 | `dashboard.md` 에 `<!doctype html>` 이 **없다** (역방향) | 템플릿을 문서로 되돌리는 회귀 |
| T22-136 | `dashboard.md` 가 문자열 `dashboard_template.html` 을 포함하고, 그 파일명이 실제 배포 파일명과 같다 | 파일명 드리프트 (T23 의 3문서 키 정합성 검증과 같은 형태) |
| T22-137 | `dashboard.md` 에 `NOTEMPLATE`·`ANCHOR-FAIL`·`OK` 폐쇄 어휘 3종이 존재 | 개정 절차의 실패 경로 문서화 누락 |
| T22-138 | `install.sh` 의 `COMMANDS_FILE_COUNT` == `commands/` 최상위 **전체** 파일 수 | T22-5 를 `*.md` → `*` 로 확장. 상수 미갱신 재발 방지 |
| T22-139 | 템플릿 파일에 `init` 이 치환하는 앵커 6종이 **각각 정확히 1회** 등장 | 앵커 유일성 붕괴 → `ANCHOR-FAIL` 상시화 |

T22-5 는 T22-138 로 확장 대체한다(현행은 `ls "$REPO_ROOT/commands"/*.md | wc -l` 이라 `.html`
추가 후 `COMMANDS_FILE_COUNT=10` 과 어긋나 **반드시 실패한다**).

### 9.5 바이트 동일성 검증 (일회성, 구현 중 필수)

**(i) 템플릿 추출이 무편집인가**

```bash
git show HEAD:commands/dashboard.md | sed -n '1248,1744p' \
  | diff - commands/dashboard_template.html && echo IDENTICAL
```
EXPECT: 차이 0줄. (`HEAD` 는 이 변경 이전 커밋)

**(ii) 개정 `init` 의 산출물이 현행과 같은가**

1. 변경 전 상태에서 `/dashboard init "T" "설계|승인|구현|검수"` 수행 → `before.html` 로 보관
2. 변경 후 같은 인자로 수행 → `after.html`
3. `diff before.html after.html` — 차이는 **소유 토큰 8글자와 `갱신:` 시각뿐**이어야 한다
   (두 값은 호출마다 달라지는 것이 정상이다). 그 외 1줄이라도 다르면 개정이 잘못됐다.

**(iii) 소비자 회귀**

```bash
bash tests/run.sh          # 전체 스위트 (T1~T25)
python3 -m pytest tests/hub -q   # 허브 단위 테스트 (T24 가 감싸고 있음)
```
EXPECT: 신규/수정 항목 외 실패 0. 특히 `tests/hub/test_hub_parse.py` 가 티어 1 파싱 회귀를 잡는다.

**(iv) 허브 소비자 수동 확인**

`/dashboard init` 후 `/hub` 를 열어 (a) 카드에 제목·진행률·활성 단계가 뜨는지(티어 1 성공),
(b) 카드를 눌러 상세 패널에서 대시보드가 렌더되는지 확인한다. 파서가 조용히 티어를 강등하면
카드가 뜨긴 하지만 내용이 빈다 — grep 으로 잡히지 않는 유일한 실패 모드다.

### 9.6 문서 정합성

- `README.md`: `| commands/ | 9 |` → `10`, `합계 51개` → `52개`, `commands 9개` → `10개`,
  커맨드 표의 `| dashboard | 1745 |` → 실제 줄 수, 디렉토리 트리에 `dashboard_template.html` 추가.
  (`README` 의 수치를 `install.sh` 상수와 대조하는 테스트는 **없음**을 확인했다 — 그래서 사람이 챙겨야 한다.)
- `T17`(`test_commands_installed`)의 `test_desc` "커맨드 9종"은 `.md` 9개를 확인하는 루프이므로
  기능상 무변경이다. 문구만 오해를 부르지 않게 다듬는다.

---

## 10. 롤아웃 (저장소 → 설치본)

순서를 지킨다. 3번 이전에 설치본을 갱신하면, 새 `dashboard.md` 와 없는 템플릿이 만나
`NOTEMPLATE` 로 `init` 이 중단된다.

| # | 작업 | 검증 |
|---|---|---|
| 1 | `commands/dashboard_template.html` 추출 생성 (§9.5-i) | `diff` 0줄 |
| 2 | `commands/dashboard.md` 에서 「템플릿 전문」 제거 + 포인터 삽입 + `init` 절차 개정(§7) | T22-134/135/136/137/139 |
| 3 | `install.sh` 상수·글롭 수정 | T22-138 |
| 4 | `tests/run.sh` T22 합본 전환 + 신규 회귀 + T22-120 기대값 조정 | `bash tests/run.sh` 전량 통과 |
| 5 | B(근거 이관) 수행 — `docs/prps/dashboard-rationale.md` 생성 + 한 줄 요약·링크 잔류 | `bash tests/run.sh` 재통과 |
| 6 | `README.md` 수치·트리 갱신 | 눈으로 확인 |
| 7 | **저장소 커밋** (검수 통과 후) | — |
| 8 | 설치본 갱신: `./install.sh --scope user` | `~/.claude/commands/` 에 `.md` 9 + `.html` 1. 커맨드 목록에 `dashboard_template` 이 **없음**(§5.1 리스크) |
| 9 | 이 저장소에도 `./install.sh --scope project` | `.claude/commands/` 동일 확인 |
| 10 | 실제 `/dashboard init` 1회 + `/hub` 확인 (§9.5-ii, iv) | 산출물 diff 가 토큰·시각뿐 |

**되돌리기**: 8번까지는 `git revert` 1회 + `install.sh --scope user` 재실행으로 완전 복구된다.
템플릿 파일이 남아도 낡은 `dashboard.md` 는 그것을 참조하지 않으므로 무해하다.

---

## 11. 리스크와 대안

### 11.1 리스크

| # | 리스크 | 영향 | 완화 |
|---|---|---|---|
| R1 | 역방향 assertion 24건이 조용히 공허해진다 | 삭제된 UI(세션 탭 등)가 템플릿에 부활해도 아무도 모른다 | §9.2 합본 전환. 동치 근거 4개로 증명 |
| R2 | T22-120 계수 기대값이 B 수행 시 3→2로 바뀐다 | 테스트 실패 또는(더 나쁘게) 기대값만 고치고 근거 주석이 남아 오독 | §9.3 — 기대값과 주석을 **함께** 고친다 |
| R3 | 근거를 걷어내며 「지우지 마라」 류 경고를 함께 잃는다 | 과거 사고(`sleep 61` 제거, `is running` 제거, `--bind` 생략)가 재발 | §5.4 의 "남긴다" 6번을 명시적 체크리스트로 사용. 이관 후 해당 문구 6종을 grep 으로 확인 |
| R4 | `~/.claude/commands/` 의 `.html` 이 커맨드로 오인된다 | 커맨드 목록 오염 | §10-8 눈 확인. 발생 시 `~/.claude/dashboard/` 로 이전(비용 작음) |
| R5 | 「포트 각인」·`step`·`log`·`impl` 의 Edit 이 "Read 안 한 파일" 제약에 걸린다 | `init` 직후 첫 갱신이 실패 | **해소** — Q1(§12) 실측으로 제약이 걸리지 않음을 확인. 절차 무변경 |
| R6 | 문서와 템플릿이 서로 다른 설치본에서 짝지어진다 | 앵커 불일치 → `ANCHOR-FAIL` | 전역 우선 해결 순서(§7.2) + `report_global_command_overlap` 글롭 확장(§5.1) + T22-139 |
| R7 | `init` 스크립트를 세션이 매번 새로 타이핑하다 오타를 낸다 | `ANCHOR-FAIL` 로 중단(조용한 오염은 아님) | 앵커 검증이 곧 완화책이다. 실패가 **감지된 중단**으로 나타나는 것이 설계 목표 |

### 11.2 검토했으나 채택하지 않은 대안

**대안 C — 하위 명령별 문서 분할(점진적 공개)**
`dashboard.md` 를 디스패처(호출 규약 + 데이터 모델 + 포인터 표, ~13,000자)로 줄이고
`dashboard_init.md`·`dashboard_log.md` 등을 호출 시 Read 하게 한다. 주입 토큰만 보면 **−83%** 로
의뢰서의 60~65% 목표를 유일하게 넘긴다.

**기각 근거(정량)**: 전체 경로 세션은 `init`·`step`·`impl`·`log` 를 **모두** 부른다. 그러면 네
파일이 순차적으로 Read 되어 결국 컨텍스트에 다 들어오고, 총량은 A+B와 거의 같아진다 —
`init`+자동발행(~12,000자)이 세션 초반에 들어와 끝까지 상주하므로 절감의 대부분이 사라진다.
이득이 실재하는 것은 `/dashboard off` 나 `serve` 만 쓰는 부분 사용 세션뿐이고, 대가로 파일 4~6개,
install 표면, 테스트 표면, "어느 파일을 언제 Read 하는가"라는 새 결정 지점이 늘어난다.
지금 필요 없는 구조다(YAGNI). **A+B 를 먼저 적용해 실측한 뒤, 그때도 부족하면 별건으로 재검토한다.**

**대안 D — 템플릿을 `hub/bin/` 에 통합**
기각. 대시보드는 프로젝트 로컬 자산이고 허브는 머신 전역 자산이다(`hub/install.sh` 가 `--scope`
없이 `~/.claude/hub/bin` 하나만 쓰는 이유). 대시보드가 허브 설치에 의존하게 되면
"coding-harness 를 설치했다고 허브가 함께 설치되지 않는다"는 기존 요구(R-5)를 역방향으로 깨뜨린다.

**대안 E — 템플릿을 심볼릭 링크로 배포**
기각. `install.sh` 는 심링크 대상을 **명시적으로 거부**한다(`check_no_symlink_targets`,
`is_symlinked_path`). 기존 안전장치와 충돌한다.

---

## 12. 미결 질문 (구현 착수 전 확인 필요)

**Q1 (차단성) — 해소됨 (메인 세션 실측, 2026-08-24)** — 적용되지 않는다. 메인 세션이 비파괴
실험 2회로 확인했다: ① Bash `printf` 로 만든 파일에 Read 없이 Edit 성공, ② 개정 `init` 과 동일한
시퀀스(`cp` 로 템플릿 사본 생성 → Bash python 치환 → `grep` 으로 줄 전문 확보 → 그 전문을
`old_string` 으로 Edit)에서도 성공. **Edit 도구의 "Read 먼저" 제약은 세션 안에서 Bash 로 생성한
파일에는 걸리지 않는다.** 따라서 「포트 각인」·`step`·`log`·`impl` 은 무변경으로 유효하고,
개정안을 그대로 진행한다(R5 해소).

**Q2 — 해소됨 (사용자 결정, 2026-08-24)** — 구현 실측 결과 근거 이관(B)의 계획 절감분 중
약 80%가 tests/run.sh 의 grep 핀에 문구 단위로 고정돼 있어, 핀 무수정 안전분은 약 1,000자에
불과했다(1회차 검수 적합성 렌즈의 정량 평가). 사용자가 검증력 보존을 우선해 **최종 48,893자
(주입 약 37,000 토큰, −36.9%)를 승인**했다 — §13 의 자 수 기준은 이 값으로 개정됐다.
(승인 시점 값은 48,950자였고, R1 MEDIUM 수정 — 링크 19곳 `../../`→`../` — 으로 57자가 더 줄었다.)
40,000자 이하 재도전은 절차 본문 침범 + 핀 15~30건 재작성이 필요한 별도 설계로 남긴다.

**Q3 — 해소됨** — PRP 승인(2026-08-24)에 파일명 확정이 포함됐다. `docs/prps/dashboard-rationale.md`.

---

## 13. 완료 기준

- [ ] `commands/dashboard_template.html` 이 이전 커밋의 1248~1744행과 `diff` 0줄
- [x] `dashboard.md` 본문 48,893자 — 원래 기준(≤40,000)은 §12 Q2 해소로 개정됨(사용자 승인, 2026-08-24): 테스트 핀 보존을 우선해 안전 이관분만 수행
- [ ] `dashboard.md` 에 `<!doctype html>` 이 없다
- [ ] `bash tests/run.sh` 전량 통과 (T22 합본 전환 + 신규 6건 포함)
- [ ] `python3 -m pytest tests/hub -q` 전량 통과
- [ ] `init` 산출물 diff 가 소유 토큰·`갱신:` 시각 2곳뿐 (§9.5-ii)
- [ ] `/hub` 카드에 티어 1 정보가 정상 표시되고 상세 패널이 렌더된다 (§9.5-iv)
- [ ] 「지우지 마라」 6종 문구가 `dashboard.md` 에 남아 있다 (R3)
- [ ] `README.md` 수치 4곳과 트리가 실측과 일치
- [ ] 설치본(`~/.claude/commands/`)에 `.md` 9 + `.html` 1이 배포되고 커맨드 목록이 깨끗하다
