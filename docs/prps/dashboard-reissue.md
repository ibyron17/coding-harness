# 대시보드 재발행 — 동적 상태를 잃지 않고 정적 골격만 갈아 끼운다

> 설계 모델: opus(model-routing 기준 1~4 미해당 — 단일 서브시스템, 데이터 모델 신설이지만
> 기존 계약 위에 얹는 증분이다)

---

## 1. 요구사항 요약

`/dashboard init` 은 템플릿을 **바이트 단위로 무편집 복사**한 뒤 앵커 6개만 치환한다
(`commands/dashboard_render.py: render_dashboard`). 그래서 발행된 대시보드는 `<style>` ·
`<head>` 테마 IIFE · 카드 골격 · 하단 폴링/PiP 스크립트를 **발행 시점의 사본으로 영구히
굳힌다.** 템플릿을 고쳐도 이미 발행된 파일에는 영원히 닿지 않는다(실측: `1fc9c845` 의 `<body>`
앞 275줄이 현행 템플릿과 86줄 다르다. `af5c0abe` 는 0줄). 문서에 적힌 유일한 회복 수단인
`init` 재발행은 진행 상태와 작업 추적 로그를 **전부 버리므로** 실무에서 아무도 부르지 않는다.

이 설계는 **동적 상태를 한 글자도 잃지 않고 정적 골격만 현재 템플릿으로 교체하는 경로**를
추가한다 — 새 서브커맨드 `reissue` 하나, 수동 호출 전용, 실패하면 원본을 건드리지 않는다.

---

## 2. 영향 범위

| 파일 | 변경 | 이유 |
|---|---|---|
| `commands/dashboard_render.py` (순수, 140줄) | **+약 145줄** — 앵커 상수 9종, `PublishedValues`, `extract_published_values`, `render_reissue`, `verify_preserved`, `_replace_unique` 추출 | 추출·렌더·검증은 전부 문자열→문자열이다. ★순수 층에 속한다(T25-10 대상) |
| `commands/dashboard_helper.py` (I/O, 377줄) | **+약 42줄** — `cmd_reissue`, `_atomic_write_text`, `_project_display_name`, 디스패치 1분기 | 파일 읽기·원자적 쓰기·폐쇄 어휘 출력만 한다 |
| `commands/dashboard.md` (95,955B) | **+약 2,250B** — 호출 규약 1줄, 헬퍼 표 1행, `reissue` 절, 정적 절·불변식 9·`init` 절 각주, **`log` 2단계 앵커 문장 1개(§3.8)** | 서브커맨드 계약의 단일 출처 |
| `tests/commands/test_dashboard_helper.py` (256줄) | **+약 25 케이스** | 순수 로직 전부가 여기서 검증된다 |
| `tests/run.sh` | T34 확장(9→10) · 신규 T22-171·172·173 · `DASHBOARD_MD_BUDGET_BYTES` · `SOURCE_GUARD_ID_FLOOR` · `LEDGER_MUTATION_ROW_FLOOR` | 문면 정합 가드와 래칫 |
| `tests/mutations.tsv` | +3 변조행, T99-6 sed 리터럴 `(87`→`(90` | 모든 가드는 일부러 깨뜨렸을 때 실패해야 한다 |

**변경하지 않는 것**: `commands/dashboard_template.html`(한 바이트도) · `install.sh`
(`COMMANDS_FILE_COUNT` 12 유지 — **새 파일을 만들지 않는다**) · `removals.txt` · `hub/`
(허브 파서 계약을 그대로 지킨다) · `tests/run.sh` 의 `ALWAYS_ON_CONTEXT_BUDGET_BYTES`
(`commands/` 는 상시 로드 예산 밖이다).

---

## 3. 설계 쟁점별 결정

### 3.1 무엇을 보존 대상으로 볼 것인가 (쟁점 1)

「동적 6 셀렉터」 표만으로는 부족하다. **파일 안에서 발행 이후 달라질 수 있는 모든 것**이
보존 대상이다. 실측으로 확정했다 — 발행본 두 개의 `<body>` 영역에서 현행 템플릿과 다른
줄을 전부 뽑아 본 결과, **모든 차이가 아래 9개 슬롯 안에 들어왔다**(다른 줄은 하나도 없었다).

| # | 슬롯 | 보존 대상 | 필수/선택 |
|---|---|---|---|
| 1 | `#dz-project-name` | 자식 텍스트 | 선택 — 없으면 cwd 이름으로 채운다 |
| 2 | `#dz-title` | 자식 텍스트 | **필수** |
| 3 | `#dz-progress-bar` | inline `style="width:N%"` | **필수** |
| 4 | `#dz-progress-pct` | 자식 텍스트 | **필수** |
| 5 | 진행 시각화 블록 | `<ol id="dz-steps">…</ol>` **또는** `<table id="dz-matrix">…</table>` 전문 | **필수**(배타적으로 정확히 하나) |
| 6 | `#dz-impl-count` | 자식 텍스트 | 선택(7과 쌍) |
| 7 | `#dz-impl-tasks` | `<ol>…</ol>` 전문(`#dz-impl-{k}` 목록) | 선택(6과 쌍) |
| 8 | `#dz-log` | `data-owner-token` · `data-server-port` · 자식 `<li class="entry">` 전부(`data-seq`·`<details open>` 상태 포함) | **필수**(속성은 없으면 빈 문자열) |
| 9 | `#dz-updated` | 자식 텍스트 | **필수** |

`#dz-group-{g}`(그룹명)·`#dz-cell-{g}-{p}`·`#dz-step-{n}`·`#dz-impl-{k}` 는 5·7 블록 안에
**줄 단위로 통째로** 실려 옮겨지므로 별도 슬롯이 아니다.

**재발행으로 잃는 것 — 파일에 없는 상태는 복원할 수 없다.** 재발행은 파일을 바꾸므로 열려
있는 탭은 **새로고침해야** 새 골격이 보이고, 그 새로고침이 아래를 지운다:

- 작업 추적 로그 필터 라디오(`#dzf-all`/`#dzf-impl`/`#dzf-review`)의 사용자 선택 — 파일에는
  `checked` 가 `#dzf-all` 에 정적으로 박혀 있고, 사용자의 선택은 DOM 에만 있다
- 사용자가 손으로 접거나 편 `<details>` 상태(파일에 적힌 `open` 은 보존된다 — 잃는 것은
  **파일과 어긋나게 만든 변경**뿐이다)
- 스크롤 위치, 열려 있는 PiP 창(문서가 다시 로드되면 파괴된다), hover 툴팁
- 서버 모드에서는 폴링이 다음 주기에 부분 치환으로 따라잡지만 **`<style>` 은 폴링 대상이
  아니다** — 새 CSS 를 보려면 새로고침이 필요하다

이 목록을 `dashboard.md` 의 `reissue` 절에 한 문장으로 요약해 적는다(사용자가 재발행을
부를지 판단할 근거다).

### 3.2 추출 방식 — 앵커 기반 줄 슬라이스. `render_dashboard` 는 **공유하되 합치지 않는다** (쟁점 2)

**결론: `render_dashboard` 를 그대로 재사용할 수는 없다. 앵커 리터럴과 치환 코어는 공유하고,
값 모델과 빌더는 둘로 둔다.**

재사용이 불가능한 이유는 두 가지이고 둘 다 구조적이다:

1. **이스케이프 방향이 반대다.** `render_dashboard` 는 값을 `escape_for_dom` 으로 이스케이프해
   넣는다(입력이 모델이 쓴 JSON 의 원문 사용자 텍스트이기 때문). 재발행의 입력은 **이미
   이스케이프된 DOM 텍스트**라 다시 이스케이프하면 `&amp;` 가 `&amp;amp;` 가 된다. `html.unescape`
   로 되돌린 뒤 다시 이스케이프하는 길이 있지만, 그것은 「왕복이 항등이다」라는 증명하기 어려운
   전제를 코드 경로 한가운데 심는 일이다.
2. **앵커 수가 다르다.** `init` 은 6개를 채운다. 재발행은 9개다(+ `#dz-progress-bar` ·
   `#dz-impl-count` · `#dz-impl-tasks`). `render_dashboard` 를 9개로 넓히면 `init` 의
   `ANCHOR-FAIL` 의미와 그 계약을 문서화한 `dashboard.md` 4-b 절, 기존 단위 테스트가 함께
   움직인다 — 재발행의 편의를 위해 **가장 하중이 큰 경로**를 흔드는 거래다.

대신 실제 DRY 이득이 있는 곳만 공유한다:

- **앵커 리터럴 9종을 모듈 상수로 승격**한다. 지금 `render_dashboard` 안에 인라인으로 박혀 있는
  6개가 상수가 되고, 두 렌더 함수가 같은 상수를 참조한다. 템플릿의 슬롯 마크업이 바뀔 때
  고칠 자리가 **한 곳**이 된다 — 이것이 「코드 경로가 하나로 합쳐진다」가 실제로 사려던 값이다.
- **치환 코어 `_replace_unique(text, replacements) -> str` 를 추출**한다. 앵커 등장 횟수가 1이
  아니면 `AnchorMismatch` 를 던지고 아무것도 반환하지 않는 규칙이 한 곳에 남는다.
  `render_dashboard` 는 이 코어를 부르는 얇은 껍데기가 된다(동작 불변, 기존 테스트 그대로 통과).

**추출은 정규식 전수 스캔이 아니라 「줄 단위 앵커 슬라이스」다.** 근거는 이 저장소가 이미 그
전제 위에 서 있다는 것이다 — 불변식 2·3·5(요소 하나는 한 줄 안에 온전히), 불변식 10(`.detail`
은 한 줄), 「grep 유일성 불변식」(`id="…"` 문자열은 줄 단위로 유일), 그리고 `step`·`log`·`impl`
절차가 전부 `grep` 한 줄을 `Edit` 앵커로 쓴다. 재발행만 다른 파싱 모델(HTML 파서·정규식 전수
스캔)을 쓰면 **문서가 보증하는 것과 다른 것을 믿는 코드**가 하나 생긴다.

슬라이스 규칙:

| 슬롯 | 시작 마커(줄 단위 유일) | 끝 |
|---|---|---|
| 1·2·3·4·6·9 | `id="dz-…"` 를 담은 그 줄 | 같은 줄 (정규식으로 내부 텍스트/속성만 뽑는다) |
| 5 | `id="dz-steps"` **xor** `id="dz-matrix"` | 이후 첫 번째 «strip 후 정확히 `</ol>`» / «`</table>`» 줄(포함) |
| 7 | `id="dz-impl-tasks"` | 이후 첫 번째 «strip 후 정확히 `</ol>`» 줄(포함) |
| 8 | `id="dz-log"` 줄(속성) + 그 다음 줄부터 | «strip 후 `<li class="entry"` 로 시작» 하는 첫 줄 ~ `#dz-updated` 줄 이전의 마지막 «strip 후 정확히 `</li>`» 줄 |

**슬롯 8의 종료 조건이 `</ul>` 이 아닌 이유 — 실측 결함.** 발행본 `1fc9c845` 에는 **`</ul>` 이
아예 없다**(로그 카드가 `…</li>` 다음에 바로 `</div>` 로 닫힌다). `log` 2단계의 prepend Edit 이
어느 회차엔가 닫는 태그까지 `old_string` 에 넣어 삼킨 흔적이다. 브라우저가 자동으로 닫아 주므로
아무도 눈치채지 못했다. `</ul>` 을 종료 조건으로 삼는 추출기는 이 파일에서 **로그 전부를
잃거나 무한히 삼킨다** — 정확히 이 설계가 막아야 할 사고다. 「마지막 `</li>`」 종료 조건은 그
파일에서도 정확히 동작하고, 재발행 결과는 `</ul>` 을 **복원한다**(덤).

`.detail` 줄에 `</li>`·`</ul>` 이 인라인으로 들어 있는 것은 경계가 되지 않는다 — 판정이
«strip 후 **정확히 일치**»이기 때문이다(실측: 모든 `.detail` 은 `<div class="detail">` 로 시작하는
한 줄이다).

마커가 **한 줄보다 많이** 나오면 `ExtractFailed` 다(`AnchorMismatch` 와 같은 등급의 판정).

### 3.3 실패 안전 — 3중 (쟁점 3)

1. **메모리 안에서 끝낸다.** 추출 → 렌더 → 검증이 전부 `str` 연산이고, 어느 단계에서 실패해도
   그 시점까지 디스크에 아무것도 쓰지 않았다. `init-render` 가 `ANCHOR-FAIL` 에서 파일을 쓰지
   않는 것과 **같은 메커니즘**이다(입력 `str` 는 불변이므로 호출자가 든 원본이 그대로다).
2. **보존 검증(`verify_preserved`) — 쓰기 직전의 계수 대조.** 추출기가 조용히 무언가를 빠뜨리는
   형태를 「조용한 유실」이 아니라 「시끄러운 거부」로 바꾼다. 원본과 렌더 결과에서 네 문자열의
   등장 횟수가 **정확히 같아야** 한다: `data-seq="` · `id="dz-step-` · `id="dz-cell-` ·
   `id="dz-impl-`. 추가로 `data-owner-token="{추출값}"` 과 `data-server-port="{추출값}"` 이 결과에
   각각 1회 있어야 한다(쟁점 7 을 기계로 닫는다). 하나라도 어긋나면 `VerifyFailed` → 쓰지 않는다.
   - 추출기의 정확성을 구조로 증명하려 들지 않고, **결과를 대조**한다. 최악의 경우가
     「재발행 거부, 파일 그대로」 — 곧 현재 상태 — 로 한정된다.
3. **원자적 쓰기.** 임시 파일(`tempfile.mkstemp`, 대상과 같은 디렉토리) → 쓰기 → `replace()`.
   `hub/bin/hub_atomic_write.py: atomic_write_text` 의 관용구를 옮겨 적는다.
   - **왜 여기만 원자적인가**: `init-render` 가 덮어쓰는 대상은 방금 복사한 템플릿 사본이라
     찢어진 쓰기가 잃는 것이 없다(`init` 재실행으로 회복). 재발행이 덮어쓰는 대상은 그 세션
     로그의 **유일한 사본**이다. 디스크 가득 참·프로세스 종료로 절반만 쓰이면 복구 수단이 없다.
     `init-render` 를 함께 바꾸지 않는 것은 수술적 변경 원칙이다.
   - **왜 임포트하지 않고 옮겨 적는가**: `commands/` 는 `~/.claude/commands/` 로,
     `hub/bin/` 은 허브 홈으로 **따로 설치된다**(배포 채널이 다르다). 한쪽만 설치된 머신에서
     임포트가 깨진다. 서로게이트 정규화(`_encode_safe_utf8`)는 **가져오지 않는다** — 그것은
     허브가 호스트 소유 JSON 을 삼키기 때문에 있는 방어이고, 여기서는 우리가 쓴 파일만
     읽으므로 추측성이며 사용자 텍스트를 조용히 바꾸는 부작용이 있다.
4. **백업 사본(`.bak`)은 만들지 않는다.** 1~3으로 최악이 「파일 그대로」에 묶이므로 백업이
   막을 사고가 남지 않고, 아무도 청소하지 않는 파일이 세션마다 쌓인다(YAGNI).

### 3.4 언제 부르는가 — **수동 전용** (쟁점 4)

**동의한다. 다만 근거는 비용이 아니라 구조적 비양립이다.**

`step`·`log`·`impl` 은 전부 **「Bash `grep` 1회 → 그 줄 전문을 `old_string` 으로 쓰는 Edit N회」**
구조다. 자동 재발행을 그 안에 끼우면 grep 과 Edit 사이에서 파일이 통째로 다시 쓰이고, 읽어 둔
앵커가 무효가 된다(줄 번호·`</ul>` 복원·속성 정규화로 텍스트가 달라진다). Edit 이 실패하거나,
더 나쁘게는 **다른 줄에 매치**한다. 감지를 `grep` 심 안에 넣는 길도 막혀 있다 — 그 심의 출력은
`Edit` 앵커라 **바이트 단위로 grep 과 같아야** 한다는 것이 명시된 계약이다.

비용도 덧붙는다: 감지는 매 호출마다 템플릿(약 80KB)과 발행본(약 60~80KB)을 읽어 비교해야 하고,
그것은 `step`/`log` 의 Bash 호출을 1회에서 2회로 늘린다 — 세션에서 가장 자주 불리는 경로다.

따라서 `/dashboard reissue` 수동 전용으로 한다. 대신 **부르는 비용을 0에 가깝게** 만든다:
재발행 결과가 현재 파일과 바이트 단위로 같으면 `SAME` 을 출력하고 **아무것도 쓰지 않는다.**
멱등하고 무해하므로 의심스러우면 그냥 부르면 된다.

`dashboard.md` 의 `reissue` 절 첫 문장에 호출 시점을 적는다 — (a) 사용자가 화면이 낡았다고
말할 때, (b) `install.sh` 재실행으로 템플릿이 갱신된 직후, (c) 이 저장소에서
`dashboard_template.html` 을 고치는 커밋 직후.

**호출 규칙 두 가지**(같은 절에 한 문장):
- 다른 절차의 grep 과 Edit **사이**에서 부르지 않는다.
- 재발행 **후**에는 이전에 읽어 둔 줄 전문을 앵커로 재사용하지 않는다 — 다시 grep 한다.

**소유권 검증을 먼저 한다.** LEGACY 모드에서는 `.claude/dashboard.html` 이 다른 세션의 것일 수
있고, 그 파일을 재발행하면 그 세션의 대기 중인 Edit 앵커까지 깨진다. `reissue` 0단계는
`step`·`log` 와 **같은** 공통 절차를 쓴다 — `grep -n 'id="dz-log"'` 1회 후
[소유권 검증](#) 표 적용, `FOREIGN` 이면 재발행하지 않는다. SESSION 모드에서는 경로가 곧
소유권이라 항상 `MINE` 이다(기존 절 그대로). 헬퍼에 새 어휘(`FOREIGN`)나 새 인자를 만들지
않는 쪽을 골랐다 — 소유권 판정은 지금도 모델이 하는 일이다.

### 3.5 옛 대시보드 호환 — 정적은 자동, 동적은 필수/선택으로 가른다 (쟁점 5)

재발행은 **현재 템플릿을 바탕으로 삼는다.** 따라서 `#dz-page-head` · `#dz-tooltip` ·
`#dz-impl-card` 처럼 나중에 추가된 **정적** 요소는 아무 일도 하지 않아도 결과물에 들어온다 —
그것이 이 기능의 요점이다.

문제는 그 안에 든 **동적 슬롯**이다:

| 없는 슬롯 | 행동 | 근거 |
|---|---|---|
| `#dz-project-name` (`#dz-page-head` 와 함께 추가됨) | **cwd 의 마지막 세그먼트로 채운다** | `init-copy` 가 쓰는 것과 같은 규칙(`hub_model._display_name` 과 같은 값)이라 허브와 대시보드가 같은 문자열을 보인다. 템플릿 기본값 `프로젝트` 로 두면 발행본이 퇴행한다 |
| `#dz-impl-count` **와** `#dz-impl-tasks` **둘 다** | 템플릿 기본값 그대로(`0/0 · 0%`, 빈 `<ol>`) | 그 시점 대시보드에는 세부 작업이 존재할 수 없었다 — 빈 값이 사실이다. CSS `:has()` 가 카드를 숨기므로 화면도 그대로다 |
| 둘 중 **하나만** | `ExtractFailed` — 중단 | 함께 추가된 쌍이다. 하나만 있으면 손상이지 옛 버전이 아니다 |
| `data-owner-token` · `data-server-port` 속성 | 빈 문자열 | 「빈 문자열과 속성 부재는 같은 뜻」이 이미 문서화된 계약이다. 재발행 후에는 속성이 존재하므로 「포트 각인」의 삽입 분기가 덜 쓰이게 된다(덤) |
| `#dz-title` · `#dz-progress-bar` · `#dz-progress-pct` · 진행 블록 · `#dz-log` · `#dz-updated` | `ExtractFailed` — 중단 | 최초 판부터 있던 요소다. 없으면 대시보드가 아니거나 손상됐다. 앞 네 개는 허브 파서(`hub_parse.parse_dashboard_html`)가 요구하는 집합과 정확히 겹친다 — 없으면 허브에서도 이미 티어 1이 아니다 |

**추측해서 만들어 내지 않는다.** 특히 `data-owner-token` 은 **보존만 하고 새로 만들지
않는다** — 불변식 9(「`init` 만 쓴다」)를 재발행이 깨지 않게 하는 선이다. 문서의 불변식 9에
괄호 한 줄을 덧붙인다: *(`reissue` 는 그 값을 옮겨 적을 뿐 값을 만들지 않는다)*.

### 3.6 폐쇄 어휘와 출력 계약 (쟁점 6)

`dashboard.md` 「헬퍼 스크립트」 표에 **1행 추가**(서브커맨드 9종 → 10종):

| 서브커맨드 | 인자 | 출력 | 대체하는 절차 |
|---|---|---|---|
| `reissue` | — | `OK <n>` \| `SAME` \| `ABSENT` \| `NOTEMPLATE` \| `EXTRACT-FAIL <사유>` \| `ANCHOR-FAIL <횟수> <앵커>` \| `VERIFY-FAIL <검사> <기대> <실제>` | (신규) `reissue` 절차 |

| 출력 | 의미 | 모델의 행동 |
|---|---|---|
| `OK <n>` | 재발행 완료. `n` = 보존한 로그 항목(`data-seq`) 수 | 한 줄 보고(새로고침 필요를 함께) |
| `SAME` | 이미 현재 템플릿과 같다 — **아무것도 쓰지 않았다** | 한 줄 보고 |
| `ABSENT` | 대시보드 파일이 없다 | `init` 을 먼저 하라고 안내 |
| `NOTEMPLATE` | 템플릿을 두 경로 모두에서 찾지 못했다 | 재설치 안내(`init-copy` 와 같은 문구) |
| `EXTRACT-FAIL <사유>` | 발행본에서 값을 읽지 못했다 — **파일 그대로** | 사유 보고 후 중단. 손으로 고치지 않는다. 회복은 `init` 재발행(로그 유실을 명시하고 사용자에게 묻는다) |
| `ANCHOR-FAIL <횟수> <앵커>` | 새 템플릿의 앵커가 어긋났다 — **파일 그대로** | 템플릿 손상/설치본 낡음. 재설치 안내 |
| `VERIFY-FAIL <검사> <기대> <실제>` | 보존 검사 불일치 — **파일 그대로** | 이 도구의 결함이다. 값 3개를 그대로 보고 |

**신설 어휘는 3개뿐**(`SAME` · `EXTRACT-FAIL` · `VERIFY-FAIL`). `ABSENT` · `NOTEMPLATE` ·
`ANCHOR-FAIL` · `OK` 는 기존 어휘를 그대로 쓴다 — 뜻이 정확히 같고, G2 가드의 어휘 목록도
그만큼만 늘어난다.

`OK` 에 숫자를 붙이는 이유: 「보고 최소화」는 `init`·`step`·`log`·`impl` 의 **정상 경로 서사**를
금지한다. `reissue` 는 사용자가 직접 부른 정비 명령이라 결과 보고가 정당하고, 그 보고가
「무엇을 잃지 않았는지」를 말하려면 수가 필요하다(`ANCHOR-FAIL <횟수> <앵커>` 와 같은 형태다).

### 3.7 `log commit` 과 `data-server-port` (쟁점 7)

`data-server-port` 는 슬롯 8의 일부로 **원문 그대로** 옮겨진다. 추가로 `verify_preserved` 가
`data-server-port="{추출값}"` 이 결과에 정확히 1회 있음을 쓰기 직전에 확인한다 — 각인이 유실되면
`VERIFY-FAIL` 로 **거부**되고 파일은 그대로 남는다. 살아 있는 서버가 고아가 되는 경로가 기계로
막힌다.

남은 위험은 **타이밍**이다: 「포트 각인」 절차와 `log commit` 3단계는 둘 다
`grep -n 'id="dz-log"'` → 그 줄 전문으로 Edit 하는 구조라, 그 사이에 재발행이 끼면 앵커가
깨진다. §3.4 의 호출 규칙 두 줄이 이것을 다룬다(사이에서 부르지 않는다 / 후에는 다시 grep).

### 3.8 로그 닫는 태그 유실의 **원인**을 함께 막는다 (승인 범위 확대)

> 이 절은 설계자가 §3.2 에서 **증상**으로 발견한 것의 **원인** 쪽이다. 오케스트레이터가
> 결함을 직접 재현하고 `log` 절차 문면을 확인한 뒤 사용자 승인을 받아 범위에 넣었다
> (설계자 본체는 `SendMessage` 가 이 세션에서 비활성이라 되돌리지 못했다) — 구현·검수는
> 이 절을 다른 절과 같은 등급으로 다룬다.

**재현(오케스트레이터 실측)**: `.claude/dashboards/1fc9c845-….html` 은 로그 항목 8건을 담고
있는데 `#dz-log` 의 닫는 태그가 **파일 어디에도 없다** — 421행이 `</li>`, 422행이 바로
`</div>` 다. 파일 안의 `</ul>` 8개는 전부 `.detail` 본문의 `<ul><li>` 마크업이다.

**원인**: 템플릿의 `#dz-log` 는 여는 태그와 닫는 태그가 **한 줄에 함께** 있다
(`dashboard_template.html:329` — `    <ul class="log" id="dz-log" … ></ul>`). `log` 절차
2단계는 *"0-a 에서 읽은 `#dz-log` 여는 태그 **전문**을 `old_string` 앵커로 삼아"* 라고만
적는데, 0-a 의 `grep` 이 돌려주는 것은 **줄 전문**이다. 모델이 「여는 태그」로 읽으면
`</ul>` 이 살고, 「그 줄」로 읽으면 `new_string` 에 되붙이라는 지시가 없어 삼켜진다.
**로그가 빈 첫 `log` 호출에서만** 갈리고, 이후 호출은 닫는 태그가 다른 줄에 있어 안전하다.
같은 절의 표제가 스스로를 「결정적」이라 부르는데 이 자리는 결정적이지 않다.

**수정**: `dashboard.md` 「`log`」 2단계에 불릿 1개를 더한다(약 +150B).

> - **앵커 줄에 `</ul>` 이 함께 있으면**(로그가 비어 있는 첫 호출) `new_string` 은 반드시
>   `</ul>` 로 끝내 되붙인다. 삼키면 목록의 닫는 태그가 **영구히** 사라진다 — 브라우저가
>   자동으로 닫아 주어 화면으로는 드러나지 않는다(실측: `1fc9c845` 발행본).

**재발행과의 관계**: `reissue` 는 이미 손상된 파일에서 `</ul>` 을 **복원한다**(§3.2 슬롯 8의
종료 조건이 `</ul>` 이 아닌 이유이기도 하다). 이 절은 그것과 **다른 것**을 막는다 — 고치지
않으면 `init` 을 새로 부른 세션마다 첫 `log` 에서 결함이 다시 태어난다. 복원과 재발생 방지는
둘 다 필요하다.

**검토했으나 채택하지 않은 대안 — 템플릿을 두 줄로 가른다.**
`<ul …>` 과 `</ul>` 을 각각 다른 줄에 두면 앵커 줄에 닫는 태그가 없어져 모호함이 **구조적으로**
사라진다. 더 나은 수정이지만 이 회차에 넣지 않는다: (i) 이 PRP 의 「변경하지 않는 것」이
`dashboard_template.html` 을 한 바이트도 건드리지 않는다고 못박았고, (ii) `render_dashboard`
앵커 #5 상수와 그 단위 테스트가 함께 움직이며, (iii) 템플릿 전용 가드(T22-167)의 재검토가
붙고, (iv) **이미 설치된 낡은 템플릿은 여전히 한 줄이라 문서 수정이 어차피 필요하다.**
구조적 수정은 템플릿을 건드리는 다음 회차의 후보로 남긴다.

---

## 4. 파일 구조와 모듈 경계

프로젝트 CLAUDE.md 의 레이어 구성을 그대로 따른다 — **순수 층은 `dashboard_render.py`,
I/O 층은 `dashboard_helper.py`.** 새 파일을 만들지 않는다:

- `dashboard_render.py`: 140 → 약 **285줄** (★순수 유지. T25-10 이
  `grep -E 'open\(|Path\(|os\.'` 로 강제한다 — **주석에도 그 문자열을 쓰지 않는다**)
- `dashboard_helper.py`: 377 → 약 **419줄**

**왜 세 번째 파일을 만들지 않는가.** `commands/` 최상위에 파일이 하나 늘면
`install.sh` 의 `COMMANDS_FILE_COUNT`(12) · T22-138 · T27 · T35-3 이 함께 움직이고,
대장(`.coding-harness.json`)의 해시 목록도 바뀐다. 그 비용을 치를 근거가 없다:
`dashboard-worktree-bash-gate.md` §4.2 의 **400줄은 「넘으면 순수 층을 분리한다」는 1회성
트리거**였고 그 분리는 이미 일어났다(`dashboard_render.py` 가 그 산물이다). 영구 파일 상한이
아니다. 419줄은 user rules 의 「200-400 typical, 800 max」 안에 있다. 이 판단은 PRP §4.2 의
문구를 이 문서가 **해석**한 것이므로 승인 항목으로 올린다(§9).

---

## 5. 데이터 모델

```python
# commands/dashboard_render.py

@dataclass(frozen=True)
class PublishedValues:
    """발행된 대시보드에서 읽어낸 동적 값 전부.

    모든 문자열 필드는 **이미 DOM 이스케이프된 텍스트**다(InitValues 와 다른 점 — 그쪽은
    원문 사용자 텍스트이고 render_dashboard 가 escape_for_dom 을 적용한다). None 은
    「그 슬롯이 파일에 없다」를 뜻하며, 채우는 정책은 I/O 층이 정한다.
    """

    project_name_html: str | None      # None → I/O 층이 cwd 이름으로 채운다
    title_html: str
    progress_width: str                # "0%" | "100%" — style="width:{}" 에 그대로 들어간다
    progress_text_html: str
    progress_block_lines: list[str]    # <ol id="dz-steps">…</ol> 또는 <table id="dz-matrix">…</table>
    impl_count_html: str | None        # impl_block_lines 와 쌍 — 둘 다 None 이거나 둘 다 값
    impl_block_lines: list[str] | None
    log_owner_token: str               # 없으면 ""
    log_server_port: str               # 없으면 ""
    log_entry_lines: list[str]         # <li class="entry">…</li> 들. 비어 있을 수 있다
    updated_html: str


class ExtractFailed(Exception):
    """발행본에서 값을 읽지 못했다 — 호출자는 아무것도 쓰지 않는다."""
    def __init__(self, reason: str) -> None: ...


class VerifyFailed(Exception):
    """재발행 결과가 보존 검사를 통과하지 못했다 — 호출자는 아무것도 쓰지 않는다."""
    def __init__(self, check: str, expected: int, actual: int) -> None: ...
```

`InitValues` 는 **손대지 않는다.** 두 모델이 공존하는 이유는 §3.2 의 두 가지(이스케이프 방향,
앵커 수)이고, 그 사실을 `PublishedValues` 의 docstring 첫 문단에 적는다.

---

## 6. 인터페이스

```python
# commands/dashboard_render.py (순수)

def extract_published_values(published_text: str) -> PublishedValues:
    """발행된 대시보드 텍스트에서 동적 슬롯 9종을 읽는다. 계약 위반이면 ExtractFailed."""

def render_reissue(template_text: str, values: PublishedValues) -> str:
    """현재 템플릿의 앵커 9종을 values 로 치환한 새 문자열을 돌려준다.

    앵커 등장 횟수가 1이 아니면 AnchorMismatch(render_dashboard 와 같은 규칙).
    project_name_html 이 None 이면 ValueError — 호출 전에 I/O 층이 채워야 한다.
    """

def verify_preserved(published_text: str, rendered_text: str, values: PublishedValues) -> int:
    """동적 요소 계수가 보존됐는지 확인하고 보존된 로그 항목 수를 돌려준다. 어긋나면 VerifyFailed."""

def _replace_unique(text: str, replacements: list[tuple[str, str]]) -> str:
    """앵커별 등장 횟수 1을 확인하며 순서대로 치환한다(render_dashboard·render_reissue 공용)."""


# commands/dashboard_helper.py (I/O)

def cmd_reissue() -> None:
    """발행된 대시보드의 정적 골격만 현재 템플릿으로 교체한다 — 폐쇄 어휘 1줄을 출력한다."""

def _atomic_write_text(final_path: str, text: str) -> None:
    """같은 디렉토리의 임시 파일에 쓴 뒤 rename 으로 교체한다(hub_atomic_write 관용구)."""

def _project_display_name() -> str:
    """cwd 의 마지막 세그먼트 — cmd_init_copy 와 cmd_reissue 가 공유하는 표시 이름 규칙."""
```

`cmd_reissue` 의 흐름(50줄 제한 안):

```
dz_path = _dashboard_path()
현재 텍스트 읽기 실패 → "ABSENT"
템플릿 없음          → "NOTEMPLATE"
values = extract_published_values(현재)                 → ExtractFailed → "EXTRACT-FAIL <사유>"
project_name 이 None 이면 escape_for_dom(_project_display_name()) 로 채운다
rendered = render_reissue(템플릿, values)                → AnchorMismatch → "ANCHOR-FAIL …"
rendered == 현재 → "SAME" (쓰지 않는다)
n = verify_preserved(현재, rendered, values)            → VerifyFailed → "VERIFY-FAIL …"
_atomic_write_text(dz_path, rendered); "OK n"
```

---

## 7. 설계 결정과 근거 (요약)

| # | 결정 | 근거 |
|---|---|---|
| R1 | 새 서브커맨드 `reissue` 1개, **수동 전용** | 자동 감지는 `step`/`log` 의 grep→Edit 앵커 구조와 **구조적으로 비양립**이다(§3.4). 비용은 부차적 근거 |
| R2 | **줄 단위 앵커 슬라이스** 추출 | 이 저장소의 모든 절차·불변식이 이미 「1줄 1요소」 위에 서 있다. 다른 파싱 모델을 하나 더 들이지 않는다 |
| R3 | 로그 종료 조건은 `</ul>` 이 **아니라** 마지막 `</li>` | **실측**: 발행본 `1fc9c845` 에 `</ul>` 이 없다. `</ul>` 기반 추출기는 그 파일에서 로그를 잃는다 |
| R4 | `render_dashboard` 와 **합치지 않고** 앵커 상수·치환 코어만 공유 | 이스케이프 방향이 반대이고 앵커 수가 다르다. 합치려면 `init` 의 계약·문서·테스트를 흔들어야 한다(§3.2) |
| R5 | 쓰기 직전 **계수 대조**(4종) + 속성 존재 확인(2종) | 추출기 정확성을 구조로 증명하는 대신 결과를 대조한다. 최악이 「파일 그대로」로 묶인다 |
| R6 | **원자적 쓰기**(mkstemp + rename), `init-render` 는 그대로 | 재발행 대상은 로그의 유일한 사본이다. `init-render` 대상은 방금 복사한 템플릿이라 잃을 것이 없다 |
| R7 | `.bak` 백업 없음 | R5·R6 이후 백업이 막을 사고가 남지 않는다. 청소 주체 없는 파일이 쌓인다(YAGNI) |
| R8 | 새 파일 없음 — 기존 2파일에 넣는다 | PRP §4.2 의 400줄은 1회성 분리 트리거였고 이미 소비됐다. 새 파일은 `COMMANDS_FILE_COUNT`·T22-138·T27·T35-3·대장을 함께 움직인다 |
| R9 | 소유권 검증은 **기존 공통 절차 재사용**(모델이 판정) | 헬퍼에 `FOREIGN` 어휘·토큰 인자를 새로 만들지 않는다. 소유권 판정은 지금도 모델의 일이다 |
| R10 | `data-owner-token` 은 **보존만**, 생성하지 않는다 | 불변식 9 를 재발행이 깨지 않게 하는 선 |
| R11 | 로그가 비면 `<ul …></ul>` **한 줄** 형태로 렌더 | `init` 직후 재발행이 바이트 동일(`SAME`)이 되게 한다 — 두 경로가 같은 출력에 수렴함을 테스트로 고정할 수 있다 |

**디자인 패턴은 도입하지 않는다.** 추출기는 함수 하나, 렌더는 함수 하나, 검증은 함수 하나다.
전략/방문자/파서 계층을 두지 않는 이유는 분기가 하나도 없기 때문이다(선형/매트릭스조차
`progress_block_lines` 라는 **값**의 차이로 흡수된다 — `init` 이 `steps_block_lines` 로
이미 확립한 관용구를 그대로 따른다).

---

## 8. 테스트 계획

### 8.1 순수 층 단위 테스트 — `tests/commands/test_dashboard_helper.py` (+약 25 케이스)

`ExtractPublishedValuesTest`
1. 선형 대시보드에서 슬롯 9종 전부를 읽는다
2. 매트릭스 대시보드에서 `<table>` 블록을 그대로 읽는다
3. `#dz-steps` 와 `#dz-matrix` 가 **둘 다** 있으면 `ExtractFailed`(불변식 1)
4. 둘 다 없으면 `ExtractFailed`
5. `id="dz-title"` 이 두 줄에 있으면 `ExtractFailed`(유일성)
6. 필수 슬롯 누락(`#dz-title`·`#dz-log`·`#dz-updated`·`#dz-progress-bar`) 각각 `ExtractFailed`
7. `#dz-project-name` 이 없으면 `project_name_html is None`
8. impl 슬롯 2개가 함께 없으면 둘 다 `None`
9. impl 슬롯이 **하나만** 있으면 `ExtractFailed`
10. **`</ul>` 이 없는 로그에서 항목 전부를 읽는다**(실측 결함 `1fc9c845` 회귀)
11. 빈 로그: `log_entry_lines == []`, 토큰·포트는 보존
12. `data-server-port` 속성 부재 → `""`
13. `data-owner-token` 속성 부재 → `""`
14. `.detail` 안의 인라인 `</li>`·`</ul>` 이 블록 경계가 되지 않는다
15. `style="width:100%"` 에서 `100%` 를 읽는다

`RenderReissueTest`
16. **왕복 항등**: `render_dashboard(템플릿, InitValues)` 의 결과를 추출→재렌더하면 **바이트
    동일**하다 — 두 경로가 같은 출력에 수렴함을 고정하는 가장 강한 한 건(`SAME` 도달 가능성 증명)
17. 빈 로그는 `<ul …></ul>` 한 줄로 렌더된다(R11)
18. 비어 있지 않은 로그는 `</ul>` 이 **복원된** 블록으로 렌더된다
19. **낡은 `<style>` 이 현재 템플릿의 것으로 바뀌고 로그는 그대로다** — 이 기능의 목적 자체
20. 템플릿의 앵커가 0회/2회면 `AnchorMismatch` 이고 반환값이 없다
21. 토큰·포트가 결과에 그대로 실린다
22. `project_name_html` 이 `None` 인 채로 부르면 `ValueError`
23. **이중 이스케이프 없음**: 제목이 `a &amp;lt; b` 인 발행본을 왕복시켜도 문자열이 그대로다

`VerifyPreservedTest`
24. 로그 항목이 하나 빠지면 `VerifyFailed`(기대/실제 값 포함)
25. `#dz-step-` 이 하나 빠지면 `VerifyFailed` / `#dz-cell-`·`#dz-impl-` 각각 1건
26. 계수가 같으면 통과하고 로그 항목 수를 돌려준다

기존 `RenderDashboardTest` 6건은 **무수정으로 통과해야 한다** — `_replace_unique` 추출이
동작을 바꾸지 않았다는 회귀 증명이다.

### 8.2 `tests/run.sh` 문면·계약 가드

| ID | 검사 | 비고 |
|---|---|---|
| **T34**(기존 확장) | 서브커맨드 목록에 `reissue` 추가, 디스패치 분기 수 `9` → **`10`**, 폐쇄 어휘 목록에 `SAME`·`EXTRACT-FAIL`·`VERIFY-FAIL` 추가 | 문서 표 ↔ 디스패치 정합을 기계로 강제한다. T34 는 서브체크 ID 를 쓰지 않으므로 **원장 행이 늘지 않는다**(기존 한계 그대로 — 주석에 명시) |
| **T33**(기존, 무수정) | 새 런처 줄이 관문 거부 구문(비-`$HOME` 환경변수·셸 `for`·heredoc)을 담지 않는다 | 이미 `dashboard.md` 의 모든 코드 블록을 훑으므로 자동 적용된다 |
| **T22-171**(신규) | `dashboard_helper.py` 에 `def _atomic_write_text(` 가 있고 `_atomic_write_text(` 가 2회 이상 등장한다(정의+호출) | 재발행이 직접 쓰기로 퇴행하는 것을 막는다 |
| **T22-172**(신규) | `dashboard_render.py` 에 보존 검증 계수 토큰 4종(`data-seq="` · `id="dz-step-` · `id="dz-cell-` · `id="dz-impl-`)이 전부 있다 | 검증이 조용히 얇아지는 것을 막는다 |
| **T22-173**(신규) | `dashboard.md` 불변식 9 문장에 재발행 예외 문구가 있다 | 문서가 스스로와 모순되는 상태를 막는다(§3.5) |
| **T22-174**(신규) | `dashboard.md` 「`log`」 2단계에 `</ul>` 되붙임 불릿이 있다 | §3.8 — 이 문장이 지워지면 첫 `log` 호출의 비결정성이 되살아난다 |
| **T22-163**(기존) | `DASHBOARD_MD_BUDGET_BYTES` 를 구현 완료 시점 실측치로 올린다 + 주석의 설계 상한 갱신 | §9 승인 항목 |

### 8.3 `tests/mutations.tsv` 변조행 (신규 3)

| guard_id | target_path | mutation_sed | expect_group | expect_token | defect |
|---|---|---|---|---|---|
| `T22-171` | `commands/dashboard_helper.py` | `s/    _atomic_write_text(dz_path, rendered)/    pathlib.Path(dz_path).write_text(rendered, encoding="utf-8")/` | `T22` | `T22-171:` 메시지의 판별 토큰 | 재발행이 원자적 쓰기를 우회해 직접 덮어써도 조용히 통과 |
| `T22-172` | `commands/dashboard_render.py` | 계수 토큰 4종 중 하나(`id="dz-cell-`)를 지우는 치환 | `T22` | 〃 | 보존 검증이 한 종류를 놓쳐도 조용히 통과 |
| `T22-173` | `commands/dashboard.md` | 불변식 9 의 재발행 예외 괄호를 지우는 치환 | `T22` | 〃 | 문서가 재발행과 모순되는 상태로 돌아가도 조용히 통과 |
| `T22-174` | `commands/dashboard.md` | §3.8 의 `</ul>` 되붙임 불릿을 지우는 치환 | `T22` | 〃 | 첫 `log` 호출이 닫는 태그를 삼켜도 조용히 통과 |

**연쇄 래칫(빠뜨리면 T37 이 「가드 무력화」로 잡는다)**:

- `SOURCE_GUARD_ID_FLOOR` 480 → **484** (서브체크 ID 4개 추가 — T22-171·172·173·174)
- `LEDGER_MUTATION_ROW_FLOOR` 87 → **91** (변조행 4개 추가)
- **`tests/mutations.tsv` 의 T99-6 행 sed 리터럴 `LEDGER_MUTATION_ROW_FLOOR(87` → `(91`**
  — 이 행의 주석이 「이 상수가 바뀔 때마다 이 행도 함께 갱신해야 한다」를 다섯 차례의 실측
  사례로 기록하고 있다. 같은 함정에 여섯 번째로 걸리지 않는다
- `LEDGER_EXEMPT_ROW_RATCHET` 404 — **변경 없음**(면제행을 만들지 않는다)
- `COMMANDS_FILE_COUNT` 12 — **변경 없음**(새 파일 없음)
- `ALWAYS_ON_CONTEXT_BUDGET_BYTES` 55509 — **변경 없음**(`commands/` 는 예산 밖)

### 8.4 실사용 검증 (구현 완료 판정)

1. `.claude/dashboards/1fc9c845-….html` 사본에 `reissue` 를 돌려 — `<style>` 이 현재 템플릿과
   0줄 차이가 되고, `data-seq` 8건·`#dz-cell-` 6칸·토큰·포트가 보존되고, `</ul>` 이 복원됨을
   확인한다(이 파일이 **실측 결함을 담은 유일한 재현 픽스처**다 — 사본으로 작업한다)
2. `af5c0abe-….html` 사본에 돌려 `SAME` 이 나오는지 확인한다(멱등성)
2-a. §3.8 — 갓 `init` 한 대시보드에 `log` 를 1회 걸고 결과에 `</ul>` 이 **남아 있는지** 확인한다
3. 정본 검증 5종 전부: `bash tests/run.sh` · `python3 -m unittest discover -s tests/hub -t .` ·
   `python3 -m unittest discover -s tests/commands -t .` · `python3 -m py_compile hub/bin/*.py` ·
   `bash -n install.sh && bash -n hub/install.sh`
4. `wc -c commands/dashboard.md` 실측치를 `DASHBOARD_MD_BUDGET_BYTES` 에 그대로 반영(헤드룸 0 관례)

---

## 9. 리스크와 열린 결정

> **승인 상태(2026-09-11)**: R-A·R-B 와 §10 의 3건 전부 사용자 승인을 받았다 —
> 상한 99,000B 로 상향, 새 파일 없이 `dashboard_helper.py` 확장, 수동 전용. 여기에
> **§3.8(닫는 태그 원인 수정)이 범위로 추가**됐다. 아래 서술은 승인 당시의 근거 기록이다.

### R-A. `dashboard.md` 의 96,000B 설계 상한을 넘는다 — **승인 필요**

현재 95,955B, 상한까지 **여유 45B**. 이 설계의 문서 증분은 약 **+2,250B**(§3.8 포함. 한글은
UTF-8 3바이트다)이므로 약 98,205B 가 된다.

96,000B 는 `hub-session-tree-and-per-session-dashboards.md` **결정 ST8** 이고, 두 차례 실제로
지켜졌다 — `dashboard-worktree-bash-gate` 구현은 중간 97,523B 까지 올라간 것을 **상수를 올리지
않고** 산문 압축으로 95,899B 까지 내렸고(「상수를 올려 통과시키면 그 설계 결정 자체가
무력화된다」), `dashboard-ui-polish-4` 도 같은 이유로 올리지 않았다. 따라서 이것은 **선례를
뒤집는 결정**이며 사용자 승인 사항이다.

- **제안**: 설계 상한 96,000B → **99,000B**, `DASHBOARD_MD_BUDGET_BYTES` 는 구현 완료 시점
  실측치로 고정(헤드룸 0 유지). 근거 — 이 상한의 목적은 `Skill(dashboard)` 1회 로드의 세션
  컨텍스트 비용이고, +2.1KB 는 그 파일의 **+2.2%** 다. 그 대가로 「발행된 대시보드가 영원히
  낡는다」는 유일한 회복 불가 경로가 닫힌다. 상시 로드 예산(T26, 55,509B)에는 영향이 없다.
- **대안(채택하지 않음)**: 기존 산문 2.1KB 압축. 이미 두 차례 압축을 거쳐 여유가 소진됐고,
  T22 그룹이 `dashboard.md` 의 리터럴 문장 다수를 앵커로 고정하고 있어 「무관한 곳을
  개선하지 않는다」(수술적 변경)와 정면으로 부딪힌다.

### R-B. `dashboard_helper.py` 가 400줄을 넘는다(약 419줄) — **승인 필요**

§4 에 적었듯 400줄은 PRP §4.2 의 **1회성 분리 트리거**였고 이미 소비됐다는 것이 내 해석이다.
user rules 기준(200-400 typical, 800 max) 안에 있다. 다만 그 문구를 「영구 상한」으로 읽는
독법도 가능하므로 승인 항목으로 올린다. 상한으로 본다면 세 번째 파일이 필요하고,
`COMMANDS_FILE_COUNT` 12→13 · T22-138 · T27 · T35-3 · 대장 해시가 함께 움직인다.

### R-C. 추출기가 미래의 템플릿 변경과 어긋날 수 있다

슬롯의 마크업(들여쓰기·속성 순서)이 바뀌면 앵커 상수와 추출기를 함께 고쳐야 한다. 완화:
앵커 리터럴이 **모듈 상수 한 곳**에 모이고(§3.2), `render_reissue` 가 `AnchorMismatch` 로
즉시 시끄럽게 실패하며, T34 가 문서↔코드 정합을 계속 강제한다. 조용한 실패 경로는 없다.

### R-D. 재발행이 「최신」을 판정하지는 않는다

`reissue` 는 **현재 설치된 템플릿**에 맞춘다. 설치본이 레포보다 낡았다면 낡은 골격으로 맞춘다
(다운그레이드도 가능하다). 버전 각인을 템플릿에 넣는 방법이 있지만 새 DOM 계약·새 가드·새
문서를 부르는 별건이다. 이름이 `reissue`(재발행)이지 `upgrade` 가 아니라는 점으로 정직하게
남긴다 — `install.sh` 재실행 직후에 부르라는 안내가 이 간극을 실무적으로 메운다.

### 검토했으나 채택하지 않은 대안

1. **`init` 에 보존 모드를 붙인다**(예: SESSION 모드이고 토큰이 같으면 로그를 살린다).
   — `init` 의 문서화된 불변식(「언제나 처음부터 새로 만든다」)을 뒤집는다. 새 작업을 시작하며
   `init` 을 부르는 사용자는 **깨끗한 판**을 기대한다. 두 의미를 한 명령에 겹치면 어느 쪽도
   예측 가능하지 않다.
2. **3구간 스플라이스**(새 `<head>` + 옛 `<body>` + 새 하단 `<script>`). 경계가 2개뿐이라
   훨씬 단순하고 사용자 콘텐츠를 바이트 그대로 보존한다. — 그러나 **카드 골격 변경을 옮기지
   못한다.** `#dz-impl-card` · `#dz-tooltip` · `#dz-page-head` 는 전부 `<body>` 안에 추가된
   요소이고(쟁점 5가 지목한 바로 그 셋), 그것을 못 옮기면 재발행의 절반이 비게 된다.
3. **허브가 낡은 골격을 감지해 배지로 알린다.** 허브는 이미 모든 대시보드를 매 수집 주기에
   파싱한다. — 재발행 자체와는 별건이고, 허브에 템플릿 의존을 새로 만든다. 이 기능이 착지해
   실사용 데이터가 쌓인 뒤 별도로 판단할 일이다.

---

## 10. 승인이 필요한 핵심 결정 (3줄)

1. **`dashboard.md` 의 96,000B 설계 상한(결정 ST8)을 99,000B 로 올린다** — 문서 증분 약 +2,100B.
   두 차례 지켜진 선례를 뒤집는 결정이다(§9 R-A).
2. **새 파일을 만들지 않고 `dashboard_helper.py` 를 약 419줄로 키운다** — PRP §4.2 의 400줄을
   1회성 분리 트리거로 해석한 결과다. 영구 상한으로 보면 세 번째 파일과 설치 상수 연쇄가 붙는다(§9 R-B).
3. **`reissue` 는 수동 전용이고, 실패하면 원본을 한 바이트도 건드리지 않는다** — 자동 감지는
   `step`/`log` 의 grep→Edit 앵커 구조와 구조적으로 비양립이다(§3.4).

**세 건 모두 2026-09-11 승인됐다.** 추가로 **§3.8(로그 닫는 태그 유실의 원인 수정)이 범위에
들어왔다** — 증상은 설계자가, 원인과 수정 문면은 오케스트레이터가 실측해 넣었다.
