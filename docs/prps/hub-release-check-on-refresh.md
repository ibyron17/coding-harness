# Plan: 허브 새로고침 때 새 릴리스를 바로 확인한다

> 설계 문서(PRP). 결정 ID 접두는 **RR**(Release check on Refresh). 구현 전 사용자 승인 필요.
> 설계 모델: opus(승격 기준 미해당 — 서브시스템 2개(서버·화면), 데이터 모델 개편 아님).
> 개정 1(구현 1회차 검수 반영, 사용자 승인): **RR11** 신설 — 허브 페이지를 다른 출처의 iframe 에 싣지 못하게 한다. RR3 표·RR6·§8.2·§8.3·§9·§11·§15·§16 이 맞춰졌다.
> 선행 결정: `docs/prps/harness-versioning.md` UN1~UN10 · `docs/prps/hub-host-header-guard.md` HG1~HG8 ·
> `docs/prps/hub-panel-immediate-refresh.md` IR1~IR8 · `docs/prps/hub-ungated-poll-and-stale-tab-self-heal.md` SH1~SH9.

## Summary

허브 페이지를 새로 열거나(브라우저 새로고침 포함) 우상단 새로고침 버튼을 누르면, 화면(JS)이 서버에 **새 릴리스 즉시 확인
신호**(`GET /release-check` + 사용자 정의 헤더)를 한 번 보낸다. 서버는 자동 확인(6시간)과 **같은 판정기**(`_ReleaseChecker`,
락 + 마지막 시도 시각 하나)로 최소 간격 1분을 지키며 `git ls-remote` 를 돌리고, 돌았으면 스냅샷을 강제 수집한 뒤 204 로 답한다.
화면은 확인을 기다리지 않고 바로 뜨고, 204 를 받으면 한 번 더 폴링해 버전 표기·알림 버튼을 그 자리에서 갱신한다.
포커스 복귀·탭 복귀·1분 폴링은 신호를 보내지 않는다.

## User Story

coding-harness 를 쓰는 사용자로서, 새 릴리스가 나왔다는 말을 듣고 허브를 새로고침하면 6시간을 기다리지 않고 바로 「새 버전」
알림을 보고 싶다 — 그래야 그 자리에서 `/harness-update` 를 할 수 있다.

## Problem → Solution

지금: 원격 확인은 서버 전용 스레드가 6시간에 한 번만 한다. 브라우저의 모든 갱신(1분 폴링·새로고침 버튼·포커스·탭 복귀·브라우저
새로고침)은 서버 입장에서 똑같은 `GET /hub.html` 이라, 사용자가 일부러 새로고침해도 확인을 앞당길 수 없다.
→ 제안: 사람의 명시적 행위 두 가지(버튼 클릭·페이지 로드)에서만 화면이 별도 신호를 보내고, 서버는 그 신호를 자동 확인과 한 곳에서
판정해 1분 이상 간격으로만 원격에 묻는다. 수동 확인도 시도로 기록돼 다음 자동 확인은 그때부터 6시간 뒤다.

## Metadata

- **Complexity**: Medium (기존 파일 수정 8 + 새 테스트 파일 2 + 정적 가드 4)
- **Source PRD**: N/A (메인 세션 지시문 — 사용자 확정 사항 8개)
- **PRD Phase**: N/A
- **Estimated Files**: 새 2(테스트) · 수정 11(코드 3 · 템플릿 1 · 테스트 3 · 문서 3 · 원장 1 · run.sh 1 — 아래 §5)

---

## 1. 요구사항 요약

사용자가 확정한 것(이 문서는 이것을 뒤집지 않는다):

| # | 확정 사항 | 이 설계의 반영 |
|---|---|---|
| U1 | 6시간 자동 주기는 그대로, 상수(설정 키 없음, UN4) | `RELEASE_CHECK_INTERVAL_MS` 불변 |
| U2 | 새로고침 버튼 클릭과 페이지를 새로 열 때(브라우저 새로고침 포함)만 즉시 확인 요청 | RR1 |
| U3 | 포커스·탭 복귀와 1분 폴링은 확인하지 않는다 | RR1 · T25-289 · D47 |
| U4 | 수동 확인 최소 간격 1분 — 연타 방지 + 다른 웹사이트 단순 GET 증폭 방지 | RR4 · RR8 |
| U5 | 수동 확인도 시도로 기록 — 다음 자동 확인은 그 시각부터 6시간 뒤 | RR4(시도 시각 하나를 공유) |
| U6 | `update_check_enabled: false` 면 수동 확인도 하지 않는다 | RR7 |
| U7 | 화면은 결과를 기다리지 않고 바로 뜨고, 잠시 뒤 결과를 반영(ls-remote 최악 15초) | RR2 · RR5 · RR6 |
| U8 | README 프라이버시 고지·「새 버전 알림」·config 표, `commands/hub.md` 갱신 | RR9 · §11 |

**화면 변화와 목업**: 레이아웃·색·모션은 바뀌지 않는다 — 기존 정적 노드 `#dzh-harness-version`·`#dzh-update` 가 **더 일찍**
갱신될 뿐이다(UN8 갱신 불변식 그대로). 그래서 프리뷰 목업은 만들지 않는다(설계 지침의 「화면이 바뀌지 않는 설계」 범위).

## 2. 이미 확인된 사실 (설계의 전제 — 재측정하지 않았다)

- 확인 주기 판정은 순수 함수 `hub_release.should_attempt_release_check(now, last, interval)`(hub_release.py:103) — 기록 없음·주기
  경과(경계 포함)·벽시계 역행이면 참. **간격을 인자로 받으므로 1분 판정에 그대로 재사용된다.**
- 확인 스레드 `_release_check_loop`(hub_server.py:567)는 하트비트 주기로 깨어 `_run_release_check_gate`(:550)만 본다. 시작 때
  `release_check.json` 의 `last_attempt_at_ms` 를 이어받고, 그 시각은 **지역 변수**에만 산다 — 지금은 요청 스레드가 이 값에 닿을
  길이 없다.
- `run_release_check_cycle(now_ms)`(hub_release_read.py:177)는 설치 기록 → `git ls-remote` → 기록 쓰기 1회, 예외를 올리지 않는
  계약. 쓰는 기록의 `last_attempt_at_ms` 는 인자 `now_ms` 다.
- 서버는 `http.server.ThreadingHTTPServer`(hub_server.py:650) — 요청마다 데몬 스레드. 핸들러는 `do_GET` 하나(`do_OPTIONS`·`do_POST`
  없음 → 그 메서드는 `BaseHTTPRequestHandler.handle_one_request` 가 501 로 답한다).
- `do_GET` 순서: Host 가드(403) → `ALLOWED_REQUEST_PATHS` 정확 일치 → 대시보드 정규식 → 404. 인식 경로는 `_refresh_if_stale()`
  (신선도 창 2초, `SNAPSHOT_FRESHNESS_WINDOW_MS`)를 먼저 부른다.
- 강제 수집 API 가 이미 있다: `_SnapshotRefresher.collect_if_older_than(now, ACTIVITY_COLLECT_MAX_AGE_MS)`(=0) — 진입 **뒤에 시작한**
  수집만 자기 몫으로 인정한다(`_is_covered_after_lock_wait`, 알림 기능 C2).
- 화면: 페이지 초기화 JS 는 매 로드(브라우저 새로고침·`template_stamp` 자가 리로드 포함)마다 돈다. 서버 모드 판정 `isServed`
  (hub_template.html:1611), `file://` 모드는 `if(!isServed){ … return; }`(:3182)로 조기 반환. 즉시 갱신 3종은 `pollNow(bool)`
  (:3258)을 타고, 새로고침 버튼 리스너는 `refreshButton.addEventListener('click', function(){ pollNow(true); });`(:3278).
  1분 인터벌은 `setInterval(poll, POLL_INTERVAL_MS)`(:3271), `poll()` 은 `busy` 가드로 동시 1건.
- DOM 테스트 하네스의 `window.fetch` 모의는 **URL 과 무관하게** 같은 응답을 준다(template_dom_harness.py `_PRE_SCRIPT_HEAD`).
  기존 DOM 테스트는 「페이지 로드가 poll() 을 한 번 조용히 먼저 돌릴 수 있다」에 이미 면역이다(하네스 `PROBE_PRELUDE` 주석,
  test_hub_template_dom.py D1 주석, test_hub_template_dom_update.py D41 주석).
- 정적 가드 현재 최대 번호 T25-287, DOM 시나리오 최대 D45(test_hub_template_dom_approval.py). `tests/run.sh`·원장에
  `_run_release_check_gate`·`_release_check_loop`·`_start_release_check_thread` 를 이름으로 드는 곳은 없다(개명·삭제해도 눈먼
  가드가 생기지 않는다 — grep 으로 확인).

---

## 3. 결정

### RR1 — 신호를 보내는 곳은 두 곳뿐: 새로고침 버튼 클릭 · 페이지 로드(서버 모드)

- 버튼: 기존 리스너 줄을 `refreshButton.addEventListener('click', function(){ pollNow(true); requestReleaseCheck(); });` 로 바꾼다.
- 페이지 로드: 렌더 IIFE 서버 모드 구간 끝에서 `requestReleaseCheck();` 를 1회 부른다. 브라우저 새로고침·`template_stamp` 자가
  리로드도 페이지 로드다 — 서버가 1분 간격으로 거르므로 구분하지 않는다.
- 포커스 복귀·탭 복귀(`pollNow(false)`)와 1분 인터벌(`poll`)은 **부르지 않는다**(U3).

**기각한 대안**

- `pollNow` 안에서 `isExplicitRequest` 가 참일 때 부르기 — `pollNow` 는 「폴링 + 패널 iframe 신호」 래퍼(IR2)라 책임이 섞이고, 그
  인자를 맨몸 리스너가 이벤트 객체로 오염시키는 함정(T25-134 GOTCHA)에 릴리스 확인까지 묶인다. 호출 지점을 리스너 줄에 직접 두면
  정적 가드(T25-289)가 「정확히 두 곳」을 셀 수 있다.
- `GET /hub.html` 폴링 요청에 쿼리·헤더를 실어 겸하기 — 폴링 응답이 확인(최악 15초)만큼 막혀 세션 화면 갱신까지 늦어진다(U7 위반).

### RR2 — 신호 모양: `GET /release-check` + `X-Dzh-Release-Check` 헤더, 확인이 끝난 뒤 204

| 항목 | 값 |
|---|---|
| 메서드·경로 | `GET /release-check` — **정확 일치**(쿼리 문자열·뒤 슬래시가 붙으면 404, `ALLOWED_REQUEST_PATHS` 관례) |
| 필수 헤더 | `X-Dzh-Release-Check`(값 무관, 화면은 `1` 을 보낸다). 없으면 **403** |
| 정상 응답 | **204 No Content**, 본문 없음, `Cache-Control: no-store`. `Content-Length` 는 보내지 않는다(RFC 9110 — 204 에 금지) |
| 응답 시점 | 확인이 끝나거나(강제 수집까지) 건너뛴 **뒤**. 다른 확인이 진행 중이면 그것이 끝날 때까지 기다렸다가 건너뛴다 |
| 수집 게이트 | `_refresh_if_stale()` 를 부르지 않는다 — 확인이 실제로 돌았을 때만 판정기가 강제 수집한다(RR5) |
| 스위치 꺼짐 | 헤더 검사 통과 후 아무것도 하지 않고 204(RR7) |

응답을 확인 뒤로 미루는 이유: 화면이 「언제 다시 폴링하면 새 결과가 보이는가」를 **정확히** 안다. 화면은 이 요청을 기다리지 않으므로
(비동기 fetch) 첫 화면이 늦어지지 않는다(U7). 막히는 것은 이 요청을 맡은 요청 스레드 하나뿐이고, `hub.html`·대시보드 요청은
git 을 기다리지 않는다(아래 §6 락 순서).

**기각한 대안**

- 즉시 202 + 화면이 고정 지연 뒤 재폴링 — 확인 시간이 수백 ms~15초로 퍼져 있어 지연이 짧으면 결과를 놓치고 길면 늦다.
- 요청 스레드가 전용 확인 스레드를 깨우고(Event) 완료를 기다리기(Condition) — 같은 효과에 동기화 장치 두 개와 「몇 번째 확인을
  기다리는가」 세대 번호가 더 든다. RR4 의 락 하나가 단일 실행·대기·건너뛰기를 다 준다.
- `POST` — 아래 RR3. 이득 없이 「서버는 GET 전용」 성질(hub_template.html 복사 IIFE 주석·UN5)만 깨진다.

### RR3 — 교차 출처 방어: 사용자 정의 헤더 필수 + `do_OPTIONS` 를 두지 않는다 (Host 가드는 그대로)

다른 웹사이트가 이 주소로 요청을 **보내는** 길과 각 방어의 성립 여부:

| 공격 경로 | 요청이 도착하나 | 헤더를 실을 수 있나 | 결과 |
|---|---|---|---|
| `<img src="http://localhost:8794/release-check">`·`<link>`·`<script>`·폼, 그리고 `/release-check` 를 `<iframe>` 으로 | 도착(Host 정상) | **불가** — 이 요소들은 요청 헤더를 정할 수 없다 | 403 |
| 허브 **페이지**(`/`·`/hub.html`)를 `<iframe>` 으로 싣는다 — 실린 페이지의 진짜 스크립트는 헤더를 붙일 수 있다 | 브라우저가 응답의 `frame-ancestors 'self'` 를 보고 **표시를 거부**한다 → 그 스크립트가 돌지 않는다 | — | 막힘(RR11) |
| 허브 페이지를 **새 창·최상위 이동**(`window.open`·`location=`)으로 연다 — 허브 스크립트가 헤더를 붙인다 | 도착 | 가능(허브 자신의 스크립트) | **통과** — 막지 않는다: 창이 잠깐이라도 열리고(팝업은 사용자 클릭이 있어야 열린다) 1분 상한(RR4·RR8)이 걸린다(RR11) |
| `fetch(url, {mode:'no-cors', headers:{X-Dzh-…}})` | 도착 | **불가** — no-cors 요청의 Headers 는 안전 목록 밖 헤더를 조용히 버린다(Fetch 표준, guard `request-no-cors`) | 403 |
| `fetch(url, {headers:{X-Dzh-…}})`(cors 모드) | 본 요청 전에 사전 요청 `OPTIONS` 를 보낸다 — 안전 목록 밖 헤더라서 | — | `do_OPTIONS` 가 없어 **501** → 사전 요청 실패 → 본 요청은 **나가지 않는다** |
| `navigator.sendBeacon` | 도착(POST) | 불가 | `do_POST` 없음 → 501 |
| DNS 리바인딩(공격자 도메인이 127.0.0.1 로 풀림 — 같은 출처라 헤더 가능) | 도착 | 가능 | Host 가 `evil:8794` → **403**(HG1, 기존) |
| 허브 페이지 자신(같은 출처 fetch) | 도착 | 가능, **사전 요청 없음**(같은 출처) | 통과 |

- 사전 요청 규칙(안전 목록 밖 요청 헤더 → CORS preflight)과 no-cors 헤더 필터는 Fetch 표준이며 Chrome·Firefox·Safari·Edge 가
  공통으로 따른다. **이 저장소에서 브라우저별 실측은 하지 않았다** — 서버 쪽 전제(OPTIONS → 501, `Access-Control-Allow-*` 헤더를
  절대 보내지 않음)는 단위 테스트 RS7 과 정적 가드 T25-290 으로 고정하고, 브라우저 쪽은 §13 선택 수동 확인으로 남긴다.
- 최소 간격 1분(RR4)은 이 방어와 **독립적으로** 유지한다(U4) — 헤더 방어가 어떤 브라우저에서 새도 git 호출은 시간당 60회가 상한이다.
  표의 마지막 행(새 창으로 허브 페이지를 연다)은 이 상한이 실제로 받치는 경로다 — RR11 이 막지 않는 유일한 남은 길이다.
- 이 경로가 바꿀 수 있는 것은 허브 자신의 캐시(`release_check.json`·`hub.html`)뿐이다 — `GET /hub.html` 이 이미 수집으로
  `hub.html` 을 쓰는 것과 같은 부류이고, 사용자 데이터에 대한 쓰기 경로는 생기지 않는다.

**기각한 대안**

- `Origin` 검사 — 같은 출처 `GET` fetch 에는 브라우저가 `Origin` 을 붙이지 않아(Fetch 표준: GET/HEAD 의 same-origin 요청) 정상
  요청을 가를 수 없다.
- `Sec-Fetch-Site: same-origin` 요구 — Safari 16.4 미만에 이 헤더가 없어 정상 사용자가 막힌다. 사용자 정의 헤더는 모든 브라우저에서 성립.
- 서버 기동마다 만든 토큰(쿠키·쿼리) — HG 대안 A 와 같은 이유(북마크·`file://` 와 충돌)에, 이 위협(보내기만 가능, 결과는 캐시
  갱신)에는 헤더로 충분하다.

### RR4 — 판정·실행은 한 곳: `_ReleaseChecker` 를 자동 루프와 요청이 함께 쓴다

`_SnapshotRefresher`(「수집 경로는 이 클래스 하나다 — 요청도, 유지보수 티커도 `collect_if_older_than` 만 부르고 창 크기만 다르게
준다」)와 같은 모양이다. 서버 인스턴스에 `httpd.release_checker` 로 싣고, 둘 다 `check_if_due(min_interval_ms)` 만 부른다.

| 호출자 | 스레드 | `min_interval_ms` |
|---|---|---|
| `_release_check_loop`(하트비트 주기로 깸) | 전용 데몬 스레드 | `hub_release.RELEASE_CHECK_INTERVAL_MS`(6시간) |
| `_serve_release_check_request` | 요청 스레드 | `hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS`(1분) |

- 시도 시각(`_last_attempt_at_ms`)은 **하나**다 → 수동 확인도 시도로 기록되고 다음 자동 확인은 그때부터 6시간 뒤(U5)가 별도
  코드 없이 성립한다. 자동 확인 직후 1분 안의 수동 요청도 건너뛴다(같은 원격에 연달아 묻지 않는다).
- 판정·확인·강제 수집이 **전부 락 안**이다. 락을 기다린 호출은 앞선 확인이 갱신한 시각을 보고 건너뛴다 — 이중 검사가 따로 필요 없다
  (판정 자체가 락 안이다). git 은 언제나 한 번에 하나만 돈다.
- **시계는 락 안에서 읽는다**(`_wall_clock_ms()`, `_monotonic_ms()` 와 같은 패치용 헬퍼). 호출자가 진입 시각을 넘기면, A 가 now=89 를
  읽고 밀린 사이 B 가 now=90 으로 먼저 확인했을 때 A 의 판정이 `89 < 90` → 「벽시계 역행」 분기로 **참**이 돼 1분 안에 두 번 묻는다.
  락 안에서 읽으면 그 구간이 없다. (`_SnapshotRefresher` 가 진입 시각을 쓰는 것은 단조 시계라 역행 분기가 없기 때문이다.)
- 시도 시각은 **사이클 전에** 갱신한다 — 사이클 계약 밖 예외가 갱신을 무산시키면 같은 예외가 깨어날 때마다 반복된다(AR4·감사 B-1
  선례, 지금 `_run_release_check_gate` 가 `return now_ms` 로 지키는 성질).
- 기동 시 `release_check.json` 의 마지막 시도 시각을 이어받는 일(지금 `_release_check_loop` 첫머리)은 판정기를 만드는
  `_build_release_checker` 로 옮긴다 — 재시작 직후의 수동 요청도 1분 간격을 지킨다.
- `_run_release_check_gate` 는 판정기 메서드로 흡수돼 **삭제**된다(호출자가 루프 하나뿐이었다).

**기각한 대안**

- 요청 쪽에 수동 전용 시각을 따로 두기 — 두 시각을 서로 반영해야 U5 가 성립하고, 두 경로가 동시에 git 을 부르지 않게 하는 락이
  어차피 필요하다.
- 모듈 전역 락·전역 시각 — 결정 A3(전역 가변 상태 금지). `_SnapshotRefresher`·`dashboard_paths_by_key` 와 같은 「서버 인스턴스에
  싣는다」 관례(결정 N3)를 따른다.

### RR5 — 확인이 돌았으면 락 안에서 스냅샷을 강제 수집한다

없으면 **버튼 경로에서 거의 항상** 옛 화면이 나온다: 클릭 → `pollNow(true)` 의 폴링이 t=0 에 수집 → 확인이 t≈1s 에 끝남 → 204 →
후속 폴링 t≈1s 는 신선도 창(2초) 안이라 **확인 전** 캐시를 받는다. 그래서 판정기가 확인 뒤
`refresher.collect_if_older_than(_monotonic_ms(), ACTIVITY_COLLECT_MAX_AGE_MS)` 를 부른다 — 진입 뒤에 시작한 수집만 인정하는 기존
강제 수집 의미(C2)가 「확인 결과를 담은 수집」을 보장한다.

- **락 안에서** 부른다 — 락을 기다리던 다른 탭의 요청이 건너뛰고 204 를 받을 때 그 수집이 이미 끝나 있어야 그 탭의 후속 폴링도
  새 결과를 받는다.
- 자동 경로에도 똑같이 적용된다(한 메서드). 비용은 6시간에 수집 1회 추가이고, 덕분에 자동 확인 결과도 다음 폴링에 바로 실린다.
- 락 순서는 `release_checker._lock → snapshot_refresher._lock` 한 방향뿐이다. 수집 경로(`_run_collect_cycle` →
  `read_harness_version_view`)는 판정기 락을 잡지 않는다(파일만 읽는다) → 교착 없음.
- 사이클이 예외로 끝나도 강제 수집은 한다(무해 — `collect_if_older_than` 은 예외를 올리지 않는 계약).

**기각한 대안**

- 최신 버전이 바뀐 경우에만 수집 — 직전 기록과 비교하려면 `run_release_check_cycle` 의 반환 모양(공개 인터페이스)을 바꾸거나 기록을
  한 번 더 읽어야 한다. 아끼는 것은 시간당 최대 60회(수동 상한)의 수집이라 단순함을 택한다.
- `_SnapshotRefresher` 에 「신선도 무효화」 메서드 추가 — 판정기가 수집기 내부 상태를 만지는 결합이 생기고, 무효화와 다음 요청
  사이 경쟁을 따로 따져야 한다.

### RR6 — 화면: 탭당 진행 중 1건, 204 면 한 번 더 폴링, 실패는 표시하지 않는다

- `requestReleaseCheck()` 는 렌더 IIFE 의 **서버 모드 구간**(`if(!isServed){ … return; }` 뒤)에 둔다. `file://` 모드에는 서버가
  없으므로 보내지 않는 것이 의도다(UN9 의 「가드 바깥에 둔다」와 반대 방향 — 이번에는 서버가 있어야 의미가 있다).
- **진행 중 가드**(`isReleaseCheckInFlight`): 응답이 최대 15초+ 늦을 수 있는데 브라우저의 호스트당 동시 연결 상한(HTTP/1.1,
  크롬 6)이 있어, 느린 확인 중 연타가 연결을 다 점유하면 1분 폴링·버튼 폴링이 그 뒤에 줄 선다. 탭당 1건이면 그 일이 없다.
- 응답 `ok`(204) → `poll()` 한 번. `ok` 가 아니거나(403 등) 네트워크 오류면 아무것도 하지 않는다 — 서버 연결 끊김은 `poll()` 의
  실패 계수가 이미 「서버 연결 끊김」으로 알리고, 확인 실패 사유는 `/hub status` 의 `release_check.last_failure_reason` 이 보인다
  (UN2 — 확인 실패는 화면 경고를 띄우지 않는다). 그래서 이 `catch` 는 조용한 삼킴이 아니라 다른 채널로 넘긴 것이다(주석으로 남긴다).
- 진행 중 가드의 해제는 `.then(성공).catch(삼킴).then(해제)` 순서다(`poll()` 과 같은 관용구) — 성공 핸들러의 **동기 예외**(`res.ok` 를
  읽다 던지는 경우 포함)도 `catch` 가 받아 해제가 반드시 돈다. `.then(성공, 실패)` 두 인자 형태는 성공 핸들러의 예외를 실패 핸들러가
  받지 못해 가드가 영구히 안 풀린다(D52 가 그 변조를 문다).
- 버튼 회전 애니메이션(새로고침 회전 IIFE)·패널 iframe 신호(`dzh:refresh-requested`)는 손대지 않는다.

### RR7 — 스위치 꺼짐: 판정기를 만들지 않는다, 경로는 204 무동작

- `update_check_enabled` 가 거짓이면 `_build_release_checker` 가 `None` 을 돌려주고(기록도 읽지 않는다) 스레드도 뜨지 않는다 —
  지금 「꺼지면 스레드 자체가 없다」(UN4)와 **같은 시점(서버 기동)** 에 정한다.
- `/release-check` 는 그래도 인식 경로다: 헤더 검사(403) → 판정기가 없으면 아무것도 안 하고 204. 404 로 나누지 않는 이유: 화면은
  상태 코드로 분기하지 않고(`ok` 면 폴링, 무해), 코드를 상태별로 나누면 테스트·문서만 늘어난다. 헤더 검사를 스위치보다 먼저 둬
  교차 출처 요청은 스위치 상태와 무관하게 늘 403 이다.
- 문서 정정(기존 동작의 문서화): 확인 여부는 서버 기동 때 정해지므로 `config.json` 을 바꾸면 `/hub server restart` 가 필요하다.
  화면 알림은 수집이 설정을 매번 새로 읽으므로 다음 수집부터 바로 따른다(hub_collect.py:636). README config 표에 한 문장 더한다.

### RR8 — 최소 간격 상수: `hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS = 60 * 1000`

- 6시간 상수 옆(★순수 잎 모듈)에 둔다 — 「얼마나 자주 원격에 묻는가」 규칙이 한 파일에 모인다. 설정 키는 만들지 않는다(UN4 와 같은 판단).
- 1분인 이유: (1) 연타·여러 탭 동시 로드·자가 리로드를 한 번으로 합친다 (2) 헤더 방어가 새도 git 호출이 시간당 60회를 넘지 않는
  상한 (3) 릴리스 직후 확인하려고 1분 안에 다시 누를 일은 드물다(사용자 확정 U4).

### RR9 — 문서

hub/README.md 의 보안 절(허용 경로 목록 — 「뿐이다」가 거짓이 되지 않게), 프라이버시 고지, 「새 버전 알림」의 「언제 확인하나」,
config 표, `commands/hub.md` 의 `release_check` 설명, hub_template.html 머리 주석, hub_server.py 모듈 docstring·상수 주석,
hub_release.py `ReleaseCheckRecord` docstring(「서버 스레드만 쓴다」 → 「판정기 락 안에서만 쓴다」), hub_release_read.py 의 같은
주석, `docs/prps/harness-versioning.md` UN2 에 개정 한 줄. 문안은 §11.

### RR10 — 하지 않는 것

확인 결과 토스트·「확인 중」 표시 · 설정 키(간격·켜기/끄기 분리) · 응답 본문에 결과 싣기 · 포커스·탭 복귀·1분 폴링 확인 ·
`file://` 모드 확인 · 패널 iframe 쪽 신호 · `do_POST`/CORS 허용 · 자동 확인 주기 변경 · 허브 페이지의 최상위 이동·새 창 열기 차단(RR11).

### RR11 — 허브 페이지 응답에 `Content-Security-Policy: frame-ancestors 'self'` (구현 1회차 검수 반영 — 사용자 승인)

- **위협**: 다른 웹사이트가 허브 페이지(`/hub.html`)를 자기 `<iframe>` 에 싣는다. 실린 페이지는 진짜 허브 스크립트라 페이지 로드 때
  `/release-check` 에 헤더를 붙여 보낸다 — 서버는 이것을 위조와 구별할 수 없다(RR3 의 「사용자 정의 헤더」 방어는 위조 스크립트가
  헤더를 **못 붙인다**는 성질에 기댔는데, 진짜 스크립트를 남의 틀에 실으면 그 성질이 빠진다). 결과는 RR3 이 이미 인정한 부류 —
  허브 자신의 캐시를 1분에 한 번까지 새로 쓰는 것 — 이지만, 사용자가 허브를 열지 않았는데 확인이 일어난다는 점이 다르다.
- **결정**: `hub.html` 응답(경로 `/`·`/hub.html`, `_serve_hub_html`)에 `Content-Security-Policy: frame-ancestors 'self'` 를 단다 —
  브라우저가 다른 출처의 틀에 이 문서를 싣는 것을 거부한다. 값은 상수(`HUB_PAGE_CONTENT_SECURITY_POLICY`)로 둔다.
- **프로젝트 대시보드 응답에는 달지 않는다**: 이번 위협과 무관하고(대시보드 문서는 `/release-check` 를 부르지 않는다), 허브 상세 패널이
  대시보드를 같은 출처 iframe 으로 싣는다 — 범위 최소화. 패널 iframe 의 주소는 상대 경로(`/project/<key>/dashboard.html`,
  `loadPanelDocument` 가 `contentWindow.location.replace(url)` 로 넣는다)라 같은 출처이고, 이 결정은 그 경로를 건드리지 않는다.
- **막지 않는 남은 길**: 최상위 이동·`window.open` 으로 허브 페이지를 **새 창**에 여는 것. 창이 잠깐이라도 열리고(팝업은 사용자 클릭이 있어야 열린다), 확인은 1분 상한(RR4)
  이라 원격이 보는 요청은 시간당 최대 60회다. 문서(README 보안 절·프라이버시 고지)에 이 단서를 적는다(§11).
- **기각한 대안**
  - 화면 스크립트에서 `window.top === window` 일 때만 신호를 보내기 — 서버 방어가 아니라 화면 스크립트 안의 조건이라 약하다(서버는 틀에 실린
    요청과 아닌 요청을 구별하지 못하고, 조건 검사는 그 스크립트가 지켜질 때만 성립한다).
  - `X-Frame-Options: SAMEORIGIN` — CSP `frame-ancestors` 로 대체된 헤더다(둘을 함께 보내면 `frame-ancestors` 가 우선). 새 코드에 옛 헤더를 더할 이유가 없다.
  - 모든 응답(대시보드 포함)에 달기 — 이번 위협과 무관한 범위 확장이고 패널 동작과 충돌 위험만 는다.

---

## 4. UX Design

### Before

```
[페이지 열기/새로고침/버튼] ──GET /hub.html──▶ 서버: 수집(release_check.json 캐시를 읽음)
                                            └─ 원격 확인은 6시간 스레드만. 새 릴리스가 6시간 늦게 보일 수 있다
```

### After

```
[페이지 열기·브라우저 새로고침]  ① GET /hub.html → 화면 즉시 표시(지금과 같다)
                                ② GET /release-check (X-Dzh-Release-Check) ─▶ 서버: 1분 지났나?
                                     예 → git ls-remote(≤15s) → 기록 → 강제 수집 → 204
                                     아니오 → 204
                                ③ 204 → poll() → 버전 표기·「새 버전」 버튼이 그 자리에서 갱신
[새로고침 버튼]                 pollNow(true)(지금과 같다) + ②③
[포커스·탭 복귀 / 1분 폴링]      지금과 같다(확인 요청 없음)
[file:// 로 연 허브]            지금과 같다(서버 없음 — 확인 요청 없음)
```

### Interaction Changes

| Touchpoint | Before | After | Notes |
|---|---|---|---|
| 페이지 로드(서버 모드) | 캐시된 최신 버전만 | + 1분 간격 즉시 확인, 끝나면 알림 갱신 | 첫 화면은 기다리지 않는다 |
| 새로고침 버튼 | 폴링 + 패널 갱신 | + 즉시 확인(진행 중이면 생략) | 회전 애니메이션 불변 |
| 포커스·탭 복귀 | 폴링 + 패널 갱신 | 불변 | U3 |
| 1분 폴링 | 폴링 | 불변 | U3 |
| `/hub status` | 6시간 시도 기록 | 마지막 시도가 자동·수동 중 나중 것 | 필드 모양 불변 |

---

## 5. 영향 범위 (Files to Change)

| File | Action | 이유 |
|---|---|---|
| `hub/bin/hub_release.py` | UPDATE | 상수 `MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS` 추가(RR8), `ReleaseCheckRecord` docstring 정정 |
| `hub/bin/hub_server.py` | UPDATE | 상수 3개(RR11 의 `HUB_PAGE_CONTENT_SECURITY_POLICY` 포함) · `_serve_hub_html` 헤더(RR11) · `_wall_clock_ms` · `_ReleaseChecker` · `_build_release_checker` · `_serve_release_check_request` · `do_GET` 라우트 · 루프·스레드 기동 시그니처 · `run_server` 배선. `_run_release_check_gate` 삭제(RR4) |
| `hub/bin/hub_release_read.py` | UPDATE | 주석 1줄(「서버 스레드만 쓴다」 → 「판정기 락 안에서만 쓴다」). 코드 불변 |
| `hub/bin/hub_template.html` | UPDATE | 머리 주석 1문단 · 서버 모드 구간에 상수 2·`requestReleaseCheck()` · 버튼 리스너 줄 · 로드 시 1회 호출 |
| `tests/hub/test_hub_release.py` | UPDATE | 상수 테스트 3(§9.1) |
| `tests/hub/test_hub_release_wiring.py` | UPDATE | `ReleaseCheckGateTest`·`ReleaseCheckLoopTest`·`StartReleaseCheckThreadTest` 를 판정기 기준으로 재작성(§9.2) |
| `tests/hub/test_hub_server_release_check.py` | CREATE | 실소켓 라우트 테스트(§9.3, RR11 헤더 RS9·RS10 포함) — test_hub_server.py 가 이미 1154줄이라 host_guard 처럼 분리 |
| `tests/hub/test_hub_template_dom_release_check.py` | CREATE | DOM D46~D52(§9.4) |
| `tests/run.sh` | UPDATE | `test_hub_docs_and_constants` 끝에 T25-288~T25-293(§9.5) |
| `tests/mutations.tsv` | UPDATE | 변조행 6개(§9.5) |
| `hub/README.md` | UPDATE | §11 |
| `commands/hub.md` | UPDATE | §11 |
| `docs/prps/harness-versioning.md` | UPDATE | UN2 에 개정 표시 한 줄(§11) |

- `hub/install.sh` 의 `HUB_FILE_COUNT`: **불변**(`hub/bin/` 에 새 파일 없음 — 새 파일은 배포 대상이 아닌 테스트뿐).
- 상시 컨텍스트(CLAUDE.md·rules/): 불변 → T26 래칫 무관.
- 크기: hub_server.py 690 → 758줄(800 상한 안). `run_server` 는 49 → 50줄 경계(§10 GOTCHA 4).

### 동시 작업 주의 (병합 직전 필수)

- 새 정적 가드 번호 T25-288~293 · DOM 시나리오 D46~D52 는 이 작업 트리(origin/develop `cdeb6fd`) 기준이다. 다른 세션이 develop 에
  같은 번호를 먼저 쓸 수 있으므로 **병합 직전 develop 의 `tests/run.sh` 최대 T25 번호와 DOM 테스트 최대 D 번호를 다시 세어**
  겹치면 run.sh·원장·이 문서·테스트 docstring 의 번호를 함께 민다.
- `hub_server.py` 의 `do_GET`·`run_server`·`_start_background_threads` 는 다른 기능도 자주 만지는 자리다 — 충돌 시 「Host 가드가
  맨 앞」(HG1)과 「`/release-check` 는 `_refresh_if_stale` 를 부르지 않는다」 두 성질만 지키면 기계적으로 풀린다.

## 6. 파일 구조와 모듈 경계

허브 레이어 관례(★순수 잎 모듈 + I/O 위성 + 서버 배선)를 그대로 따른다. **새 모듈 없음.**

```
hub_release.py (★순수, 잎)      규칙·상수: should_attempt_release_check · RELEASE_CHECK_INTERVAL_MS · MANUAL_…_MIN_INTERVAL_MS(신규)
   ▲
hub_release_read.py (I/O)       run_release_check_cycle · read_release_check_record (불변)
   ▲
hub_server.py (I/O·배선)        _ReleaseChecker(신규) ── 공유 ──┬─ _release_check_loop (전용 스레드, 6시간)
                                                              └─ _HubRequestHandler._serve_release_check_request (요청, 1분)
                                 _ReleaseChecker ──(확인 뒤)──▶ _SnapshotRefresher.collect_if_older_than(…, 0)
hub_template.html (화면)        requestReleaseCheck() ── GET /release-check ──▶ 서버
```

- 임포트 방향 불변: `hub_release`(잎) ← `hub_release_read` ← `hub_server`. T25-279 계약 그대로.
- 판정 규칙(간격 판정)은 순수 함수 하나(`should_attempt_release_check`)에 남고, 서버는 「언제 그 규칙을 부르고 무엇을 잠그는가」만 갖는다.

## 7. 데이터 모델

새 dataclass·계약 필드 **없음**. `ReleaseCheckRecord`·`HarnessVersionView`·`release_check.json`·`#dzh-data.harness_version` 은 모양 그대로다.

새 상수와 값의 이유:

| 상수 | 위치 | 값 | 이유 |
|---|---|---|---|
| `MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS` | hub_release.py | `60 * 1000` | RR8 |
| `RELEASE_CHECK_REQUEST_PATH` | hub_server.py | `"/release-check"` | RR2 — 정확 일치 라우트, 요청 문자열로 경로를 조립하지 않는다 |
| `RELEASE_CHECK_REQUEST_HEADER_NAME` | hub_server.py | `"X-Dzh-Release-Check"` | RR3 — 안전 목록 밖 헤더라 교차 출처는 사전 요청을 피할 수 없다. 접두 `X-Dzh-` 는 템플릿의 `dzh-` 네임스페이스와 같은 계열 |
| `RELEASE_CHECK_PATH` · `RELEASE_CHECK_HEADER_NAME` | hub_template.html(JS) | 위 두 값과 같은 글자 | 두 언어라 공유 스코프가 없다 — T25-288 이 대조 |

서버 내부 가변 상태(새로 생기는 것): `_ReleaseChecker._last_attempt_at_ms: int | None`(벽시계 ms, `release_check.json` 과 같은 시계)
· `_ReleaseChecker._lock: threading.Lock`. 화면 내부: `isReleaseCheckInFlight: boolean`(탭별).

## 8. 인터페이스 (공개 시그니처·모양)

### 8.1 hub_release.py (★순수)

```python
# 사용자가 직접 요청한 확인(새로고침 버튼·페이지 열기) 사이의 최소 간격 — 상수다(설정 키 없음, UN4 와 같은 판단).
# 1분인 이유: 연타·여러 탭 동시 로드를 1회로 합치고, 다른 웹사이트가 이 주소로 요청을 흘려도 git 호출이 시간당 60회를
# 넘지 않는 상한이다(docs/prps/hub-release-check-on-refresh.md RR8). 자동 확인과 같은 시도 시각을 공유한다(RR4).
MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS = 60 * 1000
```

### 8.2 hub_server.py

```python
RELEASE_CHECK_REQUEST_PATH = "/release-check"
RELEASE_CHECK_REQUEST_HEADER_NAME = "X-Dzh-Release-Check"
# RR11 — 허브 페이지를 다른 출처의 iframe 에 싣지 못하게 한다. 프로젝트 대시보드 응답에는 달지 않는다(허브 상세 패널이 싣는다).
HUB_PAGE_CONTENT_SECURITY_POLICY = "frame-ancestors 'self'"

def _wall_clock_ms() -> int:
    """벽시계를 밀리초 정수로 반환한다 — `_ReleaseChecker` 가 락 안에서 읽는다(RR4). `_monotonic_ms` 와 같은 이유로 테스트가
    이 모듈에 한정해 패치할 수 있게 한 곳으로 모은다."""

class _ReleaseChecker:
    """새 릴리스 확인의 임계 구역 — 자동(6시간, 전용 스레드)·수동(최소 1분, 요청 스레드) 두 경로가 공유한다(RR4).
    왜 클래스인가: _SnapshotRefresher 와 같다 — 여러 스레드가 공유하는 가변 상태(마지막 시도 시각)와 그것을 지키는 락이 한
    덩어리다. 서버 인스턴스에 싣는다(결정 N3 관례, 전역 가변 상태 금지)."""

    def __init__(self, refresher: _SnapshotRefresher, last_attempt_at_ms: int | None) -> None: ...

    def check_if_due(self, min_interval_ms: int) -> bool:
        """마지막 시도가 min_interval_ms 이상 지났으면 1회 확인하고 스냅샷을 강제 수집한다. 돌았으면 True. 예외를 올리지 않는다."""
```

`check_if_due` 본문의 순서(전부 `with self._lock:` 안):
1. `now_ms = _wall_clock_ms()`
2. `if not hub_release.should_attempt_release_check(now_ms, self._last_attempt_at_ms, min_interval_ms): return False`
3. `self._last_attempt_at_ms = now_ms` (사이클 **전**, AR4)
4. `try: hub_release_read.run_release_check_cycle(now_ms)` / `except Exception as error: print("릴리스 확인 사이클에서 분류되지 않은 예외: …", file=sys.stderr)`
   — 지금 `_run_release_check_gate` 의 메시지 문구를 그대로 옮긴다(로그 연속성).
5. `self._refresher.collect_if_older_than(_monotonic_ms(), ACTIVITY_COLLECT_MAX_AGE_MS)` (RR5)
6. `return True`

```python
def _build_release_checker(
    config: hub_model.HubConfig, refresher: _SnapshotRefresher
) -> _ReleaseChecker | None:
    """update_check_enabled 가 참일 때만 판정기를 만든다(UN4·RR7 — 꺼지면 기록도 읽지 않는다). 기록의 마지막 시도 시각을
    이어받아, 서버를 자주 재시작해도 6시간·1분 간격이 지켜진다."""

def _release_check_loop(
    config: hub_model.HubConfig, stop_event: threading.Event, checker: _ReleaseChecker
) -> None:
    """(docstring 은 지금 것을 유지하되 「게이트」 → 「판정기」, 「시작 때 기록을 이어받는다」 → 「_build_release_checker 가 이어받는다」)"""
    # while not stop_event.is_set(): try: checker.check_if_due(hub_release.RELEASE_CHECK_INTERVAL_MS)
    #   except Exception as error: print("릴리스 확인 루프에서 처리되지 않은 예외: …", file=sys.stderr)
    #   stop_event.wait(config.server_heartbeat_interval_seconds)

def _start_release_check_thread(
    config: hub_model.HubConfig, stop_event: threading.Event, checker: _ReleaseChecker | None
) -> threading.Thread | None:
    """판정기가 있을 때만(= update_check_enabled) 확인 스레드를 띄운다(UN4)."""

def _start_background_threads(
    config: hub_model.HubConfig,
    stop_event: threading.Event,
    refresher: _SnapshotRefresher,
    notifier: hub_notify_send.SessionNotifier | None,
    release_checker: _ReleaseChecker | None,
) -> None: ...
```

`_HubRequestHandler`:

```python
    def do_GET(self) -> None:
        # Host 가드(403) — 불변, 맨 앞(HG1)
        if self.path == RELEASE_CHECK_REQUEST_PATH:      # 정확 일치. 수집 게이트를 걸지 않는다(RR2·RR5)
            self._serve_release_check_request()
            return
        # 이하 ALLOWED_REQUEST_PATHS → 대시보드 → 404 — 불변

    def _serve_release_check_request(self) -> None:
        """새로고침 버튼·페이지 열기의 즉시 확인 신호(RR2·RR3). 헤더가 없으면 403. 판정기가 있으면 확인(또는 건너뛰기)이 끝난
        뒤, 없으면(update_check_enabled:false, RR7) 바로 204 — 본문 없음·no-store."""
        # 1) if not self.headers.get_all(RELEASE_CHECK_REQUEST_HEADER_NAME): self.send_error(403); return
        #    (get_all 은 헤더가 없으면 None — 대소문자 무관 조회)
        # 2) checker = getattr(self.server, "release_checker", None)   ← _refresh_if_stale 의 getattr 관례(단독 구성 테스트에서 500 방지)
        #    if checker is not None: checker.check_if_due(hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS)
        # 3) self.send_response(204); self.send_header("Cache-Control", CACHE_CONTROL_NO_STORE); self.end_headers()
```

`_serve_hub_html`(RR11): 본문을 읽은 뒤 `self._respond_with_html(body, extra_headers={"Content-Security-Policy": HUB_PAGE_CONTENT_SECURITY_POLICY})`.
`_serve_project_dashboard` 는 그대로(`X-Content-Type-Options: nosniff` 만). `_HubRequestHandler` docstring 에 `/release-check`(헤더 없으면 403, 있으면 204)를 적는다.

`run_server` 배선: `httpd.snapshot_refresher = …` 바로 다음 줄에
`httpd.release_checker = _build_release_checker(config, httpd.snapshot_refresher)`, 그리고
`_start_background_threads(config, stop_event, httpd.snapshot_refresher, notifier, httpd.release_checker)`.
`ALLOWED_REQUEST_PATHS` 위 주석 「이 둘만 200 이다. 나머지는 전부 404」 → 「이 둘만 hub.html 을 서빙한다 — 그 밖의 인식 경로는
프로젝트 대시보드(200)와 새 릴리스 확인 신호(204/403)뿐이고 나머지는 전부 404」.

응답 표(경로 `/release-check`):

| 조건 | 코드 | 판정기 호출 | 수집 |
|---|---|---|---|
| Host 위조·누락·중복 | 403 | 없음 | 없음 |
| 헤더 없음 | 403 | 없음 | 없음 |
| 헤더 있음, 판정기 없음(스위치 꺼짐) | 204 | 없음 | 없음 |
| 헤더 있음, 1분 안 | 204 | `check_if_due` → False | 없음 |
| 헤더 있음, 1분 지남 | 204(확인·강제 수집 뒤) | → True | 강제 1회 |
| `/release-check?…`·`/release-check/` | 404 | 없음 | 없음 |
| `OPTIONS`·`POST` 아무 경로 | 501(표준 라이브러리) | 없음 | 없음 |

### 8.3 hub_template.html (렌더 IIFE, 서버 모드 구간)

`pollNow` 정의 뒤에 둔다:

```js
  // 새 릴리스 즉시 확인 신호(docs/prps/hub-release-check-on-refresh.md 결정 RR1·RR2·RR6). 경로·헤더 이름은 hub_server.py 의
  // RELEASE_CHECK_REQUEST_PATH·RELEASE_CHECK_REQUEST_HEADER_NAME 과 같은 글자다(T25-288). 헤더가 교차 출처 위조를 막는
  // 장치라 빼면 서버가 403 으로 거절한다(RR3).
  var RELEASE_CHECK_PATH = '/release-check';
  var RELEASE_CHECK_HEADER_NAME = 'X-Dzh-Release-Check';
  var isReleaseCheckInFlight = false;   // 탭당 1건 — 느린 확인(최대 15초) 중 연타가 연결 상한을 점유하지 않게(RR6)
  // 새로고침 버튼과 페이지 로드에서만 부른다 — 포커스·탭 복귀·1분 폴링은 부르지 않는다(RR1, T25-289). 서버는 확인이
  // 끝난(또는 건너뛴) 뒤 204 로 답하고 그 사이 스냅샷을 다시 모아 두므로, 그때 한 번 폴링하면 새 결과가 보인다(RR5).
  // 실패는 여기서 표시하지 않는다 — 연결 끊김은 poll() 이, 확인 실패 사유는 /hub status 가 알린다(UN2).
  function requestReleaseCheck(){
    if(isReleaseCheckInFlight) return;
    isReleaseCheckInFlight = true;
    var headers = {};
    headers[RELEASE_CHECK_HEADER_NAME] = '1';
    fetch(RELEASE_CHECK_PATH, {cache:'no-store', headers:headers})
      .then(function(res){ if(res.ok) poll(); })
      .catch(function(){})   // 네트워크 오류와 성공 핸들러의 동기 예외 모두 여기서 삼킨다 — 아래 해제가 반드시 돌게(poll() 과 같은 관용구, RR6)
      .then(function(){ isReleaseCheckInFlight = false; });
  }
```

리스너 줄(:3276~3278 자리):

```js
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState==='visible') pollNow(false); });   // 불변
  window.addEventListener('focus', function(){ pollNow(false); });                                                         // 불변
  refreshButton.addEventListener('click', function(){ pollNow(true); requestReleaseCheck(); });
  requestReleaseCheck();   // 페이지를 새로 열 때 1회(브라우저 새로고침·자가 리로드 포함, RR1)
```

머리 주석(:30~33, 「두 모드 모두 #dzh-refresh 버튼과 …(결정 IR5).」 뒤)에 덧붙일 문장:
`서버 모드에서는 #dzh-refresh 클릭과 페이지 로드만 /release-check 로 새 릴리스 즉시 확인을 요청한다 — 포커스·탭 복귀·1분 폴링은
요청하지 않는다(docs/prps/hub-release-check-on-refresh.md 결정 RR1). 204 를 받으면 한 번 더 폴링한다(RR5·RR6).`
불변식 H1⁗ 의 노드 목록은 바뀌지 않는다.

## 9. 테스트 계획

모두 stdlib unittest. 네트워크·실제 `~/.claude` 를 쓰지 않는다(`tests/hub/__init__.py` 가 `RELEASE_CHECK_PATH` 를 이미 무력화한다).

### 9.1 `tests/hub/test_hub_release.py` (순수)

| 테스트 | 입력 | 기대 |
|---|---|---|
| `test_manual_min_interval_is_one_minute` | 상수 | `== 60 * 1000` |
| `test_manual_interval_is_shorter_than_the_automatic_interval` | 두 상수 | 수동 < 자동(아니면 수동 확인이 무의미) |
| `test_manual_interval_boundary` | `last=5000`, `now=5000+59_999` / `5000+60_000` | False / True |

### 9.2 `tests/hub/test_hub_release_wiring.py` (판정기·루프·기동 — 기존 3개 클래스 대체)

`hub_server._wall_clock_ms` 를 `side_effect` 로, `hub_release_read.run_release_check_cycle` 를 패치, refresher 는 `mock.Mock()`.

| ID | 시나리오 | 기대 |
|---|---|---|
| RC1 | 기록 없음, `check_if_due(MANUAL)` | True · 사이클 1회(인자 = 시계값) · `refresher.collect_if_older_than` 1회, 두 번째 인자 `ACTIVITY_COLLECT_MAX_AGE_MS` |
| RC2 | 직전 시도 T, 시계 T+59_999, MANUAL | False · 사이클 0 · 수집 0 |
| RC3 | 직전 T, 시계 T+60_000, MANUAL | True |
| RC4 | 수동 확인이 자동 주기를 민다(U5): T 에 MANUAL 실행 → 시계 T+6h−1 에 AUTO | False / 시계 T+6h 에 AUTO → True |
| RC5 | 자동 확인 직후 수동: T 에 AUTO 실행 → T+30s 에 MANUAL | False |
| RC6 | 사이클이 `RuntimeError("boom")` | True · stderr 에 `boom` · 다음 MANUAL(같은 시각)은 False(시도로 셌다) · 강제 수집은 됐다 |
| RC7 | 벽시계 역행(직전 T, 시계 T−1000) | True(`should_attempt` 의미 승계) |
| RC8 | 동시성: 스레드 A 의 사이클이 Event 로 막힌 동안 스레드 B 가 MANUAL 호출(대기 확인 Event) → A 해제 | 사이클 1회·수집 1회·B 반환 False. `ForcedCollectRaceTest`(test_hub_server.py:926) 의 Event 3개 모양 |
| RC11 | `_wall_clock_ms` 패치의 side_effect 안에서 `checker._lock.locked()` 를 기록(단일 스레드) | `[True]` — 시계를 락 밖(진입 시각)에서 읽는 변조(RR4)를 문다 |
| RC12 | `refresher.collect_if_older_than` side_effect 안에서 `checker._lock.locked()` 를 기록 | `[True]` — 강제 수집을 락 밖으로 내리는 변조(RR5)를 문다. RC8 은 락의 존재(직렬화)만 물고 이 위치는 못 문다 |
| RC9 | `_build_release_checker`: 스위치 꺼짐 | None · `read_release_check_record` 미호출 |
| RC10 | `_build_release_checker`: 기록 last=T, 시계 T+30s, MANUAL | False(재시작 뒤에도 1분 간격) |
| RL1 | 루프: 깨어날 때마다 `checker.check_if_due(RELEASE_CHECK_INTERVAL_MS)` | wakeups=2 → 2회, 인자 6시간 |
| RL2 | 루프: `check_if_due` 가 예외 | 3회 깨움 → 3회 호출, stderr 에 메시지(스레드 생존) |
| RT1 | `_start_release_check_thread(config, stop, None)` | None · `threading.Thread` 미호출 |
| RT2 | 판정기 있음 | 데몬 스레드 · `_release_check_loop(config, stop, checker)` 1회 |

### 9.3 `tests/hub/test_hub_server_release_check.py` (실소켓 — `_RunningHubServerTestCase` 상속, host_guard 테스트와 같은 임포트)

헤더를 직접 적는 헬퍼 `_request(method, path, headers)`(`http.client.HTTPConnection.request(method, path, headers=…)`).
`self.httpd.release_checker = mock.Mock()`, `self.httpd.snapshot_refresher = mock.Mock()` 로 주입.

| ID | 요청 | 기대 |
|---|---|---|
| RS1 | GET `/release-check` + 헤더 | 204 · 본문 `b""` · `Cache-Control: no-store` · `check_if_due` 1회, 인자 `MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS` |
| RS2 | 헤더 없음 | 403 · `check_if_due` 0회 |
| RS3 | 헤더 있음, `release_checker = None` / 속성 자체 없음 | 둘 다 204, 예외 없음 |
| RS4 | Host 위조(`evil.example:<port>`) + 헤더 | 403 · 0회(HG1 이 먼저) |
| RS5 | `/release-check?x=1` · `/release-check/` + 헤더 | 404 · 0회 |
| RS6 | 헤더 있음 | `snapshot_refresher.collect_if_older_than` 0회(이 경로는 `_refresh_if_stale` 를 부르지 않는다 — 강제 수집은 판정기 몫) |
| RS7 | `OPTIONS /release-check`(Origin·Access-Control-Request-Headers 포함) · `POST /release-check` | 501 · 응답 헤더에 `Access-Control-Allow-` 로 시작하는 것 없음 · 0회 (RR3 의 서버 쪽 전제) |
| RS8 | GET `/hub.html` + 헤더 | 200 · `check_if_due` 0회(헤더는 전용 경로에서만 의미가 있다) |
| RS9 | GET `/` · GET `/hub.html` | 200 · `Content-Security-Policy` 가 정확히 `frame-ancestors 'self'`(RR11) |
| RS10 | GET `/project/<등록된 키>/dashboard.html` | 200 · `Content-Security-Policy` 헤더 없음(RR11 범위 — 허브 상세 패널이 싣는다) |

### 9.4 `tests/hub/test_hub_template_dom_release_check.py` (헤드리스 Chrome — D46~D52)

하네스(`template_dom_harness.py`)는 **고치지 않는다**. 이 파일의 사전 스크립트 확장(`pre_script(None)` 뒤에 이어 붙임)이
`window.fetch` 를 감싸 호출을 기록하고 `/release-check` 응답만 시나리오별로 바꾼다:

```js
window.__fetchCalls = [];
window.__releaseCheckMode = '<ok|forbidden|pending|network_error|broken_response>';   // 시나리오가 파이썬에서 채운다
var __harnessFetch = window.fetch;
window.fetch = function(url, init){
  var headers = (init && init.headers) || {};
  window.__fetchCalls.push({url: String(url), header: headers['X-Dzh-Release-Check'] || null, cache: (init && init.cache) || null});
  if(String(url) !== '/release-check') return __harnessFetch.apply(this, arguments);
  if(window.__releaseCheckMode === 'pending') return new Promise(function(){});
  if(window.__releaseCheckMode === 'forbidden') return Promise.resolve({ok:false, status:403});
  return Promise.resolve({ok:true, status:204});
};
```

| ID | 시나리오 | 기대 |
|---|---|---|
| D46 | 서버 모드 로드, `ok` | `/release-check` 1건 · 헤더 `'1'` · `cache:'no-store'` · 그 뒤 `location.pathname` 폴링 1건이 **뒤따른다**(호출 순서). 같은 페이지를 `forbidden` 으로: `/release-check` 1건, 뒤따르는 폴링 0건 |
| D47 | 로드 뒤(`ok`) 새로고침 버튼 클릭 1회 | `/release-check` 총 2건. 이어서 `__triggerPoll()`·`window.dispatchEvent(new Event('focus'))`·`document.dispatchEvent(new Event('visibilitychange'))` → `/release-check` 총 2건 그대로(U3). 헤드리스의 자발적 focus 이벤트가 섞여도 「확인 요청 수」 단언은 흔들리지 않는다 |
| D48 | `pending`(응답이 끝나지 않음) — 버튼 3회 클릭 | `/release-check` 총 1건(진행 중 가드, RR6). 버튼 회전 클래스는 여전히 붙는다(회귀 확인) |
| D49 | `file://`(`run_scenario_via_file`) 로드 | `/release-check` 0건(버튼은 누르지 않는다 — `file://` 클릭은 `location.reload()` 라 프로브가 사라진다) |
| D50 | `forbidden`(403) — 로드 뒤 새로고침 버튼 클릭 | `/release-check` 총 2건(가드가 풀렸다, RR6) |
| D51 | `network_error`(fetch 거부) — 같은 시나리오 | 총 2건 |
| D52 | `broken_response`(`res.ok` 를 읽으면 던진다 — 성공 핸들러의 동기 예외) — 같은 시나리오 | 총 2건. 구현 1회차의 `.then(성공, 실패).then(해제)` 형태로는 총 1건이라 실패한다(RED) |

판정은 기존 관례대로 트리거 뒤 `__sleep(TRIGGER_SETTLE_MS)` 후 `window.__fetchCalls` 를 읽는다. 동시 부하에서 「Teardown watchdog
expired」 거짓 실패가 나면 **이 모듈만 단독 재실행**으로 가른다.

**기존 DOM 테스트 회귀**: 새 로드 시 호출이 하네스 기본 모의(`ok:true`)를 받아 로드 직후 `poll()` 이 한 번 더 돈다. 기존 시나리오는
이미 「로드가 poll() 을 먼저 한 번 돌릴 수 있다」에 맞춰 응답 문자열을 짜 두었으므로(D1·D41 주석) 영향이 없어야 한다 — 구현 후
`test_hub_template_dom*.py` 를 단독으로 한 번 돌려 확인한다. 깨지는 시나리오가 있으면 하네스를 고치지 말고 PRP 개정을 먼저 제안한다.

### 9.5 정적 가드(`tests/run.sh` `test_hub_docs_and_constants` 끝, T25-287 뒤)와 원장 행

| 가드 | 종류 | 검사 | 원장 변조행이 흉내내는 결함 |
|---|---|---|---|
| **T25-288** | 교차 파일 일치 | hub_server.py 의 `^RELEASE_CHECK_REQUEST_PATH = "…"`·`^RELEASE_CHECK_REQUEST_HEADER_NAME = "…"` 값과 hub_template.html 의 `var RELEASE_CHECK_PATH = '…'`·`var RELEASE_CHECK_HEADER_NAME = '…'` 값이 정확히 같다. 어느 하나라도 추출이 비면 `record_failure` + `return 1`(앵커 실패) | 화면 경로만 바뀌어 모든 확인 요청이 404 로 조용히 죽는 것 |
| **T25-289** | 정+역(호출 지점, RR1) | ① `function requestReleaseCheck(` 정의 줄을 뺀 `requestReleaseCheck(` 호출이 정확히 2건 ② 그중 하나는 `refreshButton.addEventListener('click', function(){ pollNow(true); requestReleaseCheck(); });` 줄 ③ 다른 하나는 `^  requestReleaseCheck\(\);` 줄 ④ T25-132 와 같은 방식으로 뽑은 `pollNow()` 범위에 없다 ⑤ `addEventListener('focus'`·`'visibilitychange'` 가 든 줄에 없다 ⑥ `setInterval(requestReleaseCheck` 0건. ⑤ 는 독립 `note_failure` 문구로 둔다 | 포커스 복귀 리스너에 확인 요청이 붙어 창을 오갈 때마다 원격에 묻는 것(U3 위반) |
| **T25-290** | 역방향(RR3) | hub_server.py 에 `^    def do_(OPTIONS\|POST\|PUT\|PATCH\|DELETE)\(` 정의가 없고 `Access-Control-Allow` 문자열이 없다 | CORS 를 「고치려고」 `do_OPTIONS` 를 넣어 사전 요청이 통과하고 헤더 방어가 무너지는 것 |
| **T25-291** | 문서(RR9) | ① T25-288 이 뽑은 경로 값이 hub/README.md 에 있다(보안 절의 허용 경로 목록이 「뿐이다」를 지킨다) ② hub/README.md 에 `페이지를 열거나 새로고침할 때` 가 있다(프라이버시 고지·「언제 확인하나」) ③ commands/hub.md 에 `새로고침할 때` 가 있다. T25-276 의 기존 토큰 3개는 그대로 통과해야 한다 | README 허용 경로 목록에서 새 경로가 빠져 보안 절이 거짓이 되는 것 |
| **T25-292** | 배선(RR4·RR7) | `run_server()` 이후 본문(`^def run_server(` ~ 파일 끝)에 ① `httpd.release_checker = _build_release_checker(config, httpd.snapshot_refresher)` ② `_start_background_threads(config, stop_event, httpd.snapshot_refresher, notifier, httpd.release_checker)` 가 있다. 독립 `note_failure` 둘 | `run_server` 가 판정기를 서버에 싣는 줄을 잃어도 핸들러가 속성 부재를 204 로 받아(RS3) 수동 확인이 조용히 죽고 아무 테스트도 알리지 못하는 것 |
| **T25-293** | 보안(RR11) | ① `^HUB_PAGE_CONTENT_SECURITY_POLICY = "frame-ancestors 'self'"$` 한 줄이 hub_server.py 에 있다 ② `_serve_hub_html()` 본문이 그 상수를 쓴다 ③ `_serve_project_dashboard()` 본문에 `Content-Security-Policy`·그 상수가 없다. 독립 `note_failure` 셋 | 틀 삽입 차단 정책이 `*` 로 느슨해지는 것 |

원장(`tests/mutations.tsv`) 변조행 초안 — 8열(guard_id · target_path · mutation_sed · expect_group · expect_token · defect · exempt_reason(빈칸) · anchor_function):

| guard_id | target_path | mutation_sed | expect_token |
|---|---|---|---|
| T25-288 | `hub/bin/hub_template.html` | `s/var RELEASE_CHECK_PATH = '\/release-check';/var RELEASE_CHECK_PATH = '\/release-chek';/` | `경로·헤더 이름이 서버와 화면에서 다름` |
| T25-289 | `hub/bin/hub_template.html` | `s/window.addEventListener('focus', function(){ pollNow(false); });/window.addEventListener('focus', function(){ pollNow(false); requestReleaseCheck(); });/` | `포커스·탭 복귀 리스너가 새 릴리스 확인을 요청함` |
| T25-290 | `hub/bin/hub_server.py` | `s/    def log_message(self, _format: str, \*args) -> None:/    def do_OPTIONS(self, _format: str, *args) -> None:/` | `GET 외 요청 처리기` |
| T25-291 | `hub/README.md` | `s/\/release-check/\/release-chek/g` | `허용 경로 목록에 새 릴리스 확인 경로가 없음` |
| T25-292 | `hub/bin/hub_server.py` | `s/    httpd.release_checker = _build_release_checker(config, httpd.snapshot_refresher)/    pass/` | `run_server() 가 새 릴리스 판정기를 서버에 싣지 않음` |
| T25-293 | `hub/bin/hub_server.py` | `s/HUB_PAGE_CONTENT_SECURITY_POLICY = "frame-ancestors 'self'"/HUB_PAGE_CONTENT_SECURITY_POLICY = "frame-ancestors *"/` | `허브 페이지 응답 정책 상수가 frame-ancestors 'self' 가 아님` |

- expect_group 은 전부 `T25`, anchor_function 은 전부 `test_hub_docs_and_constants`. defect_description 은 위 표의 마지막 열을 한 줄로.
- expect_token 은 run.sh 의 실패 보고 줄에서 **정확히 1건**이어야 한다(원장 규칙 5열) — 위 문구를 해당 `note_failure` 문자열에 그대로 넣는다.
- T25-289 변조는 호출 수(3≠2) 검사도 함께 발화시킨다 — 원장 defect 끝에 「(실측: 호출 수 검사도 함께 발화 — 구조상 불가피)」를 T25-282 행처럼 적는다.
- 각 가드가 **일부러 깨면 실패하는지**는 `bash tests/run.sh --only T37`(K6 선택 — 이번 diff 가 닿은 원장 행만 판정)로 확인한다.

### Edge Cases Checklist

- [x] 헤더 없음·Host 위조·쿼리 붙은 경로·뒤 슬래시 (RS2·RS4·RS5)
- [x] 스위치 꺼짐 (RS3·RC9)
- [x] 동시 접근 — 확인 진행 중 두 번째 요청 (RC8), 화면 연타 (D48)
- [x] 원격 실패·사이클 예외 (RC6 — 기록·실패 사유는 기존 `run_release_check_cycle` 테스트가 덮는다)
- [x] 벽시계 역행 (RC7)
- [x] 재시작 직후 (RC10)
- [x] `file://` (D49)
- [x] 사전 요청(OPTIONS)이 실패한다는 서버 쪽 전제 (RS7·T25-290)
- [x] 허브 페이지를 다른 출처의 틀에 싣는 길 (RS9·T25-293), 대시보드·패널 iframe 은 영향 없음 (RS10)
- [x] 진행 중 가드가 실패·예외 뒤에 풀린다 (D50~D52)
- [x] 락 안 시계·락 안 강제 수집 위치 (RC11·RC12)
- [x] `run_server` 의 판정기 배선 (T25-292)

---

## 10. Patterns to Mirror

| 패턴 | SOURCE | 따를 점 |
|---|---|---|
| 공유 임계 구역 클래스 | hub_server.py:308-398 `_SnapshotRefresher` | 「왜 클래스인가」 docstring, 서버 인스턴스에 싣기, 예외를 올리지 않는 공개 메서드 |
| 시도 시각은 예외에도 센다 | hub_server.py:550-564 `_run_release_check_gate` | `except Exception as error: print(f"…: {error}", file=sys.stderr)` — 추가 I/O 없음 |
| 전용 스레드 루프 | hub_server.py:567-582 · 527-547 | `while not stop_event.is_set(): try … except … ; stop_event.wait(heartbeat)` |
| getattr 로 서버 속성 읽기 | hub_server.py:154-163 `_refresh_if_stale` | 속성이 없으면 None — 단독 구성 테스트에서 500 방지 |
| 응답 헤더 | hub_server.py:218-226 `_respond_with_html` | `Cache-Control: no-store` 는 `CACHE_CONTROL_NO_STORE` 상수 |
| 패치용 시계 헬퍼 | hub_server.py:89-98 `_monotonic_ms` | `_wall_clock_ms` 를 같은 모양·같은 이유 docstring 으로 |
| 실소켓 테스트 | tests/hub/test_hub_server.py:219-249 · test_hub_server_host_guard.py:14-18, 84-106 | 상속·이중 임포트(`from .test_hub_server import …` / 폴백) |
| 스레드 경쟁 테스트 | tests/hub/test_hub_server.py:926-973 `ForcedCollectRaceTest` | Event 3개로 순서 고정, `join(timeout=5)` |
| 루프 테스트의 깨움 상한 | tests/hub/test_hub_release_wiring.py:170-186 | `bounded_wait` 로 `stop_event.wait` 대체 |
| DOM 사전 스크립트 확장 | tests/hub/test_hub_template_dom_update.py:150-185 | `pre_script(…) + assignments` 로 페이지 로드 전에 값을 심는다 |
| 정적 가드 교차 추출 | tests/run.sh T25-274(`tool_kinds_in_code_274`) · T25-132(`pollNow()` 범위 sed) · T25-278(앵커 실패는 `record_failure`+`return 1`) | 변수 접미 `_288` 등, 메시지는 반복문 밖 고정 문구 |

## 11. 문서 변경 문안 초안

**(a) hub/README.md 보안 절(≈191행) — 허용 경로 문장 교체**

> 허용 경로는 `/`·`/hub.html` 과, 티어 1 프로젝트의 `/project/<16자리 hex>/dashboard.html`(요청 문자열로 파일 경로를 조립하지 않는
> 결정적 키 조회), 그리고 새 릴리스 즉시 확인 신호 `/release-check`(본문 없는 204 — 허브 페이지가 붙이는 `X-Dzh-Release-Check`
> 헤더가 없으면 403) 뿐이다. 다른 웹사이트가 자기 스크립트로 이 헤더를 붙여 보낼 수는 없다 — 브라우저가 먼저 보내는 확인
> 요청(OPTIONS)을 서버가 받지 않는다. 허브 페이지(`/`·`/hub.html`)를 다른 웹사이트의 틀(iframe)에 싣는 것도 브라우저가 거부한다(응답의
> `frame-ancestors 'self'`, RR11). 막지 않는 길이 하나 남는다 — 다른 웹사이트가 허브 페이지를 **새 창으로 열거나 그 창으로 이동시키면**
> 허브 자신의 스크립트가 헤더를 붙이므로 확인 신호가 통과한다. 창이 잠깐이라도 열리고(새 창은 사용자가 그 사이트에서 클릭해야 열린다) 확인은 1분에 한 번까지라, 원격 저장소에 가는
> 확인 요청이 시간당 최대 60회로 제한되는 것뿐이다.

(이어지는 「원격 페이지가 이 주소로 요청을 **보내는** 것 자체는 막지 않는다」는 `/`·`/hub.html` 에 대해 여전히 참이라 그대로 둔다.)

**(b) hub/README.md 프라이버시 고지(≈220~226행) — 첫 두 문장 교체, 나머지 유지**

> - **서버가 켜져 있으면 새 릴리스 태그를 확인한다(기본 켜짐).** 6시간에 한 번, 그리고 허브 **페이지를 열거나 새로고침할 때**
>   (브라우저 새로고침·우상단 새로고침 버튼) coding-harness 저장소 폴더(설치 기록 `~/.claude/.coding-harness.json` 의 `repo_path`)에서
>   `git ls-remote --tags --refs origin` 을 한 번 실행한다. 새로고침으로 하는 확인은 직전 확인에서 1분이 지났을 때만이라 **1분에 한
>   번까지**이고, 그래서 원격이 보는 요청은 시간당 최대 60회다(컴퓨터 시계가 뒤로 돌아가면 그때 한 번 더 확인할 수 있다). 다른 창·탭에 갔다 돌아오거나 1분 자동 갱신만으로는
>   확인하지 않는다. 다른 웹사이트가 허브 페이지를 새 창으로 열면 그 열기도 같은 확인을 일으킬 수 있다(상한은 같다 — 「서버 가동 중에는…」
>   항목). 이 요청은 `git fetch` 와 같은 상대(…이하 지금 문장 그대로…)

**(c) hub/README.md 「새 버전 알림」 — 「언제 확인하나」 교체**

> - **언제 확인하나**: 서버가 켜져 있는 동안 6시간에 한 번, 그리고 **페이지를 열거나 새로고침할 때**(브라우저 새로고침·우상단
>   새로고침 버튼) 바로 한 번. 바로 확인은 직전 확인(자동이든 바로든)에서 1분이 안 지났으면 건너뛰고, 한 번 하면 다음 자동 확인은
>   그때부터 6시간 뒤다. 다른 창·탭에 갔다 돌아오거나 1분 자동 갱신으로는 확인하지 않는다. 화면은 확인을 기다리지 않고 바로 뜨며,
>   확인이 끝나면(원격이 응답하지 않으면 최대 15초) 알림 버튼이 그 자리에서 나타나거나 사라진다. `file://` 로 연 허브는 서버가 없어
>   바로 확인을 요청하지 못한다. 서버를 자주 재시작해도 간격은 `release_check.json` 의 마지막 시도 시각으로 지켜진다. 비교는 매
>   수집마다 …(이하 지금 문장 그대로)

**(d) hub/README.md config 표 `update_check_enabled` 행**

> `false` 면 새 릴리스 태그 확인(`git ls-remote --tags` — 6시간마다, 그리고 페이지를 열거나 새로고침할 때)을 하지 않는다 — 확인
> 스레드를 띄우지 않고 새로고침의 바로 확인도 하지 않으며, 기록(`release_check.json`)도 읽지 않아 알림이 뜨지 않는다. 확인을 할지는
> 서버가 기동 때 정하므로 바꾸면 `/hub server restart` 가 필요하다(알림 표시는 다음 수집부터 바로 따른다). 설치된 버전 표기는 로컬
> 정보라 계속 보인다. 「새 버전 알림」 참조

**(e) commands/hub.md(≈319~321행)**

> … 서버가 6시간마다, 그리고 허브 페이지를 열거나 새로고침할 때(직전 확인에서 1분이 지났으면) coding-harness 저장소 폴더에서
> `git ls-remote --tags` 로 새 릴리스 태그를 확인한 마지막 결과다(`last_attempt_at_ms` 는 둘 중 나중 시도). …(이하 그대로)

**(f) docs/prps/harness-versioning.md UN2 끝에 한 줄**

> - **개정(docs/prps/hub-release-check-on-refresh.md RR1·RR4)**: 페이지 로드·새로고침 버튼이 최소 1분 간격의 즉시 확인을 요청한다.
>   자동·즉시 확인은 같은 시도 시각을 공유한다 — 「6시간에 한 번」은 자동 확인의 주기다.

**(g) 코드 주석**: hub_server.py 모듈 docstring 의 릴리스 스레드 문장에 「같은 판정기(`_ReleaseChecker`)를 `/release-check`
요청도 쓴다(RR4)」를 더한다. hub_release.py `ReleaseCheckRecord` docstring 과 hub_release_read.py:87 주석의 「서버 스레드만 쓴다」 →
「서버의 판정기(`_ReleaseChecker`) 락 안에서만 쓴다」.

## 12. Step-by-Step Tasks (TDD)

### Task 1: 상수
- **ACTION**: hub_release.py 에 `MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS` 추가(§8.1), docstring 정정.
- **VALIDATE**: §9.1 RED → GREEN. `python3 -B -m unittest tests.hub.test_hub_release`

### Task 2: 판정기와 루프
- **ACTION**: §9.2 테스트 먼저(RC1~RC10·RL·RT) → `_wall_clock_ms`·`_ReleaseChecker`·`_build_release_checker` 추가, 루프·스레드 기동 시그니처 변경, `_run_release_check_gate` 삭제, `run_server`·`_start_background_threads` 배선.
- **MIRROR**: `_SnapshotRefresher`, `_run_release_check_gate` 의 예외 처리 문구.
- **GOTCHA 1**: 시계는 락 **안**에서 읽는다(RR4). 시도 시각은 사이클 **전**에 갱신한다.
- **GOTCHA 2**: 강제 수집도 락 **안**이다(RR5) — 밖으로 빼면 RC8 의 대기 요청이 수집 전에 204 를 받는다.
- **GOTCHA 3**: 판정기는 `_SnapshotRefresher` 를 받는다 — `run_server` 에서 refresher 를 만든 **뒤**에 만든다.
- **GOTCHA 4**: `run_server` 가 50줄을 넘으면 refresher·판정기를 서버에 싣는 두 줄을 `_attach_request_state(httpd, config, notifier)` 같은 헬퍼로 뺀다(사용자 rules 50줄).
- **VALIDATE**: `python3 -B -m unittest tests.hub.test_hub_release_wiring tests.hub.test_hub_server`

### Task 3: 라우트
- **ACTION**: §9.3 새 파일 먼저 → 상수 2개·`_serve_release_check_request`·`do_GET` 분기·`ALLOWED_REQUEST_PATHS` 주석. (개정 1: RS9·RS10 먼저 → `HUB_PAGE_CONTENT_SECURITY_POLICY`·`_serve_hub_html` 헤더, RR11)
- **GOTCHA**: `/release-check` 분기는 Host 가드 **뒤**, `ALLOWED_REQUEST_PATHS` 앞이든 뒤든 무방하나 `_refresh_if_stale` 를 부르지 않는다. 204 에 `Content-Length` 를 보내지 않는다.
- **VALIDATE**: `python3 -B -m unittest tests.hub.test_hub_server_release_check tests.hub.test_hub_server_host_guard`

### Task 4: 화면
- **ACTION**: §9.4 새 DOM 파일 먼저(변경 전 템플릿으로 RED 확인 — `DZH_DOM_TEST_TEMPLATE` 로 원본 지정) → §8.3 적용, 머리 주석.
- **GOTCHA**: 새 함수·호출은 반드시 `if(!isServed){ … return; }` **뒤**(서버 모드 전용). `pollNow` 정의·호출 형태는 건드리지 않는다(T25-132~134). 리스너에 `requestReleaseCheck` 를 맨몸 참조로 넘기지 않는다(익명 함수 안에서 부른다 — 기존 관례).
- **VALIDATE**: `python3 -B -m unittest tests.hub.test_hub_template_dom_release_check`(단독) 뒤 기존 `tests.hub.test_hub_template_dom*` 를 단독으로 한 번.

### Task 5: 문서
- **ACTION**: §11 (a)~(g).
- **GOTCHA**: T25-276 토큰(`update_check_enabled`·`release_check.json`·`git ls-remote --tags`)과 T25-287 등 기존 문서 가드 토큰을 지우지 않는다.

### Task 6: 정적 가드·원장
- **ACTION**: §9.5 T25-288~293 + 원장 6행. 병합 직전 번호 재계수(§5).
- **VALIDATE**: `bash tests/run.sh --only T25` 그리고 `bash tests/run.sh --only T37`(새 원장 행이 실제로 발화하는지).

## 13. Validation Commands

```bash
python3 -m py_compile hub/bin/*.py && find hub/bin -name __pycache__ -type d -prune -exec rm -rf {} +   # py_compile 은 -B 를 무시한다
bash -n install.sh && bash -n hub/install.sh
python3 -B -m unittest tests.hub.test_hub_release tests.hub.test_hub_release_wiring tests.hub.test_hub_server tests.hub.test_hub_server_host_guard tests.hub.test_hub_server_release_check
python3 -B -m unittest tests.hub.test_hub_template_dom_release_check      # DOM 은 단독으로(동시 부하 거짓 실패 회피)
bash tests/run.sh --only T25
bash tests/run.sh --only T37
```

전체 `bash tests/run.sh`·`python3 -m unittest discover -s tests/hub -t .` 은 메인 세션이 커밋 직전에 1회 돌린다(구현자·검수자는 돌리지 않는다).

**선택 수동 확인(브라우저 — RR3 전제의 실측, 실제 `$HOME` 설치 서버가 필요하므로 사용자 요청 시에만)**: 허브를 연 상태에서 다른
출처 페이지(예: `python3 -m http.server` 로 띄운 임시 페이지)의 콘솔에서
`fetch('http://localhost:8794/release-check', {headers:{'X-Dzh-Release-Check':'1'}})` → 콘솔에 CORS 사전 요청 실패,
`/hub status` 의 `release_check.last_attempt_at_ms` 불변. `mode:'no-cors'` 로도 같은 확인(서버는 403).

## 14. Acceptance Criteria

- [ ] 페이지 로드·새로고침 버튼에서만 `/release-check` 가 나간다(D46·D47·T25-289), `file://` 에서는 나가지 않는다(D49).
- [ ] 수동 확인은 직전 시도(자동 포함)에서 1분 안이면 건너뛰고, 수동 시도도 자동 6시간 주기를 민다(RC2~RC5).
- [ ] git 확인은 동시에 하나만 돈다(RC8), 확인이 돌면 후속 폴링이 새 결과를 받는다(RC1 강제 수집 + D46 후속 폴링).
- [ ] 헤더 없는 요청·Host 위조는 403, OPTIONS/POST 는 501, CORS 허용 헤더 없음(RS2·RS4·RS7·T25-290).
- [ ] `update_check_enabled:false` 면 판정기가 없고 경로는 204 무동작(RS3·RC9).
- [ ] 문서 (a)~(g) 반영, T25-276·T25-291 통과.
- [ ] 새 가드 6개(T25-288~293)가 원장 변조로 실제 실패한다(T37).
- [ ] 허브 페이지 응답에만 `frame-ancestors 'self'` 가 있고 대시보드 응답에는 없다(RS9·RS10·T25-293). 진행 중 가드는 403·네트워크 오류·성공 핸들러 예외 뒤에 풀린다(D50~D52). 락 안 시계·수집 위치는 RC11·RC12 가 문다.

## 15. 동시성·보안 분석 요약

**동시성**

| 상황 | 결과 |
|---|---|
| 자동 확인 중 수동 요청 | 요청 스레드가 판정기 락 대기 → 자동 확인·강제 수집 끝 → 1분 안이라 건너뜀 → 204 → 화면 폴링이 새 결과 |
| 탭 두 개가 동시에 로드 | 하나만 확인, 다른 하나는 락 대기 뒤 건너뜀(같은 결과를 받는다) |
| 같은 탭 연타 | 진행 중 가드로 요청 자체가 1건(RR6) |
| 확인 중 `hub.html` 요청 | git 을 기다리지 않는다. 강제 수집 구간에만 refresher 락을 함께 기다린다(지금 어떤 수집과도 같다) |
| 락 순서 | `release_checker` → `snapshot_refresher` 단방향. 역방향 경로 없음 |
| 서버 종료 중 진행 중인 확인 | 기존 전용 스레드와 같다(데몬 스레드, git 은 자기 세션) — 새 위험 아님 |

**보안**: §3 RR3 표. 새로 열리는 표면은 「허브 자신의 캐시를 1분에 한 번까지 새로 쓰게 하는 GET」 하나이고, 교차 출처에서는 헤더
방어로, DNS 리바인딩은 Host 가드로, 남는 로컬 프로세스는 최소 간격으로 묶인다(로컬 프로세스는 git 을 직접 돌릴 수 있으므로 새
능력이 아니다 — HG 문서의 「로컬 다른 프로세스」 한계와 같다). 요청 문자열로 경로를 조립하지 않는다(정확 일치 상수 비교).

**틀 삽입(RR11)**: 허브 페이지를 다른 출처의 iframe 에 싣는 길은 응답의 `Content-Security-Policy: frame-ancestors 'self'` 로 브라우저가 막는다
(RS9). 대시보드 응답에는 달지 않는다(RS10 — 허브 상세 패널의 같은 출처 iframe). 남는 길은 허브 페이지를 새 창·최상위 이동으로 여는 것 하나 —
창이 잠깐이라도 열리고 1분 상한(RR4·RR8)이 걸려 영향은 「원격 확인 요청 시간당 최대 60회」다. 브라우저의 `frame-ancestors` 처리는 이 저장소에서
실측하지 않았다(R3 과 같은 부류 — 표준·주요 브라우저 공통) — 방어가 새도 같은 상한이 받친다.

## 16. 리스크와 대안

### 리스크

| # | 리스크 | 가능성 | 영향 | 대응 |
|---|---|---|---|---|
| R1 | 버튼 경로의 후속 `poll()` 이 앞선 폴링의 `busy` 에 걸려 버려지면 새 결과가 다음 1분 폴링까지(최대 60초) 늦다 | 낮음 — 확인이 성공하려면 네트워크 왕복이 필요하고 그사이 클릭 폴링은 대개 끝난다. 로드 경로는 앞선 폴링이 없어 해당 없음 | 낮음 | 수용. `poll()` 에 재요청 큐를 넣는 안은 폴링 핵심 경로 변경이라 범위 밖 |
| R2 | 요청 스레드가 최대 15초+수집 시간 열려 있다. 탭 6개 이상이 동시에 느린 확인을 기다리면 크롬 연결 상한에 걸려 폴링이 늦어질 수 있다 | 매우 낮음 | 중간 | 탭당 1건 가드(RR6). 서버 쪽 스레드는 상한 없음 |
| R3 | 브라우저별 CORS 동작을 이 저장소에서 실측하지 않았다 | 낮음(표준·주요 브라우저 공통) | 방어가 새도 시간당 60회 상한 | 서버 전제는 RS7·T25-290 으로 고정, §13 선택 수동 확인 |
| R4 | git 원격이 보는 요청 빈도가 사용자 행동에 비례해 늘어난다(최대 시간당 60회). 다른 웹사이트가 허브 페이지를 새 창으로 열어도 같은 상한으로 일어날 수 있다(RR11 이 막지 않는 남은 길) | 중간 | 낮음 | 프라이버시 고지 (b) 에 상한과 새 창 단서를 명시 |
| R5 | hub_server.py 758줄로 800 상한에 근접 | — | 다음 기능이 넘길 수 있다 | 이번에는 분리하지 않는다(판정기를 새 모듈로 빼면 `HUB_FILE_COUNT`·설치 변경까지 번진다). 다음 서버 기능 때 릴리스 확인 묶음 분리를 검토 |
| R6 | 동시 세션이 T25·D 번호를 먼저 쓴다 | 중간 | 병합 충돌·원장 오인 | §5 병합 직전 재계수 |
| R7 | 기존 DOM 테스트가 로드 시 추가 폴링에 영향받는다 | 낮음(이미 면역 설계) | 테스트 실패 | Task 4 VALIDATE 의 기존 DOM 단독 재실행 |
| R8 | 페이지를 틀(iframe)에 넣어 띄우는 IDE 내장 브라우저(VS Code Simple Browser 등)에서는 RR11 때문에 허브가 빈 화면이 될 수 있다(추정, 미실측) | 낮음 — 사용자는 일반 브라우저·Claude 데스크톱 앱에서 본다(2026-10-15 확인). 앱 내장 브라우저는 틀 없이 띄운다(같은 헤더의 시험 페이지로 실측, `window.top === window`) | 중간 | README 「알려진 한계」에 명시 |

### 검토했으나 채택하지 않은 대안

- **A — 즉시 202 + 화면 지연 재폴링**: RR2. 「언제 끝나는가」를 모르는 고정 지연은 놓치거나 늦다.
- **B — 전용 스레드를 깨워 완료를 기다리기(Event+Condition)**: RR2. git 은 늘 한 스레드에서만 돈다는 장점이 있지만, 같은 단일
  실행·대기를 락 하나가 준다.
- **C — `POST` 또는 `Origin`·`Sec-Fetch-Site` 검사**: RR3.
- **D — 바뀐 경우에만 강제 수집**: RR5.

## 17. Notes

- 외부 조사: 새 라이브러리 없음. CORS 사전 요청·no-cors 헤더 필터는 Fetch 표준 지식으로 판단했다(R3 — 실측 아님).
- 설계 중 측정·재현 실험은 하지 않았다(지시문 — 사실은 §2 에 이미 확인된 것만 썼다).

## 사용자 확인 필요

없음. (사용자 확정 8개 안에서 모두 정했다. 참고로 사용자가 다르게 원할 수 있는 작은 선택 두 가지는 권장안대로 반영했다 —
① 자동 확인 뒤에도 강제 수집해 결과가 바로 보이게 한다(RR5, 6시간에 수집 1회 추가) ② config 표에 「스위치를 바꾸면 서버 재시작이
필요하다」를 적는다 — 지금도 그렇게 동작하지만 문서에 없던 사실이다(RR7).)
