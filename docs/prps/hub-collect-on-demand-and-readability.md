# 허브 요청 구동 수집 + 대시보드 상세 가독성 + 세션 식별

> 상태: 설계 (구현 전, 사용자 승인 대기)
> 대상 저장소: `/Users/dev/private/project/coding-harness`
> 기준 커밋: `04f9d96` (작업 트리 clean)
> 성격: 서로 독립인 요구 3건. **커밋은 주제별로 3개로 나눈다.**

---

## 0. 이 문서를 읽는 방법

세 요구는 코드 경로가 겹치지 않는다.

| 절 | 요구 | 주요 대상 파일 | 커밋 |
|----|------|---------------|------|
| [§2 Q1](#2-q1--허브-상주-서버의-수집을-요청-구동으로-바꾼다) | 5초 수집 주기 제거 | `hub/bin/*.py`, `hub/README.md`, `commands/hub.md` | 커밋 1 |
| [§3 Q2](#3-q2--대시보드-작업-추적-상세의-가독성) | 로그 상세 가독성 | `commands/dashboard.md` | 커밋 2 |
| [§4 Q3](#4-q3--허브-카드-세션-목록에서-세션을-구분한다) | 세션 구분 | `hub/bin/hub_template.html`, `hub/bin/hub_session.py` | 커밋 3 |

각 절은 **독립 커밋 단위**다. 한 절만 구현하고 멈춰도 저장소는 정합 상태로 남는다
(§5 「구현 순서」의 주의 1건만 지키면 된다).

### 0.1 확정된 결정 (2026-08-21, 사용자 승인)

이 문서가 「사용자 승인이 필요」로 올린 갈림길 3건은 아래로 확정됐다. **재논의하지 않는다.**

| 갈림길 | 확정 | 근거 |
|--------|------|------|
| config 필드 `server_collect_interval_seconds` | **제거 + 폐기 안내**(`server_heartbeat_interval_seconds` 신설) — §2.7 | 이름 부채(TTL 의 입력인데 이름이 collect). 사용자의 `~/.claude/hub/config.json` 에 이 필드가 없어(실측: `usage_api_enabled`·`ignore_globs` 만) 폐기 경고에 실제로 노출되지 않는다 |
| `/hub status` 공개 출력 계약 | **rename + 2필드 추가** — `server_collect_stalled` → `server_maintenance_stalled`, `server_collect_health`·`last_collect_success_age_ms` 신설. §2.6 | 죽은 필드를 조용히 남기지 않는다. 옛 이름 별칭은 두지 않는다(같은 사실의 출처가 둘이 되는 것을 피한다) |
| done 세션 7일 누적 | **후속 제안으로만 남긴다** — §8.1·§8.2 무수정 | 요청 범위 밖. daily-brief 8건은 스케줄 반복 실행으로 보여 진짜 요구가 "구분"이 아니라 "반복 실행 접기"일 수 있고, 그 판정 규칙은 별도 설계가 필요하다 |

### 0.2 초안 정정 2건 (메인 세션 검증)

설계 초안에서 발견해 **이미 이 문서에 반영한** 수정이다. 구현자는 정정된 서술을 따른다.

1. **불변식 10 의 범위** — "「.detail 은 항상 한 줄」·항목 줄 수 고정"은 §3.2 3단계와 §3.3
   기각표(단일 개행 상세 보호)와 동시에 성립하지 않았다. 「**태그 사이** 개행 금지」로 좁히고,
   블록 텍스트 안의 단일 개행은 보존한다. 보장은 "고정"이 아니라 "**증가하지 않음**"이다.
   → §3.2 (b), §3.5, §8.4 반영 완료.
2. **핸들러의 refresher 접근** — `self.server.snapshot_refresher` 직접 접근을
   `getattr(self.server, "snapshot_refresher", None)` + None 가드로 바꿨다.
   `dashboard_paths_by_key`(`hub_server.py:71`)가 세운 관례이며, refresher 없이 핸들러를
   단독 구성하는 테스트에서 `AttributeError` → 500 이 되는 것을 막는다. → §2.10 반영 완료.

### 0.3 검수 1회차 정정 3건 (2026-08-21, code-reviewer 지적 반영)

구현 1회차 검수에서 **설계 자체의 오류**로 판정된 것이다. 구현자의 이탈이 아니므로 설계를
먼저 고쳤다. 재검수는 정정된 서술을 기준으로 한다.

3. **`log_tail` 게이트에서 `maintenance_stalled` 가 빠져 있었다 (Major).** §2.8 이 지정한
   `crashed_evidence or collect_health == "failing"` 은 **유지보수 티커만 죽은 상태를 놓친다** —
   티커가 죽어도 수집은 요청 구동으로 계속 성공하므로 성공 스탬프가 갱신되고 실패 파일이 없어
   `collect_health` 는 `ok` 가 된다. 그런데 바로 그 순간이 스레드 사망 트레이스백이
   `server.log` 에 남아 있는 유일한 시점이다. `crashed_evidence`(완전 사망)·
   `maintenance_stalled`(티커만 사망)·`collect_health == "failing"`(수집만 실패) 셋 모두가
   "무언가 죽었다"이고 원인 규명 창구가 같다 — 이것이 개정 전 주석(검수 M2-3)의 논거였고
   그 논거는 지금도 유효하다. → §2.8 정정 완료. `commands/hub.md:121-124` 의 보고 지시와
   `tests/hub/test_hub_daemon.py` 의 단정(`assertIsNotNone`)도 이 게이트에 맞춘다.
4. **신선도 창의 시계는 벽시계가 아니라 단조 시계여야 한다 (Minor).** §2.10 의
   `_is_within` 은 `now_ms - _last_attempt_at_ms < max_age_ms` 이고, 벽시계가 NTP 스텝·수동
   변경으로 X ms 뒤로 점프하면 그 X 동안 **요청 구동 수집도 5분 배경 상한도 전혀 발동하지
   않는다.** 성공 스탬프는 그대로라 `collect_health` 는 계속 `ok` 를 보고해 사용자가 알 방법이
   없다. 간격 측정은 단조 시계로 하고, 성공 스탬프(파일 mtime, `collect_health` 의 입력)는
   벽시계 그대로 둔다 — 두 시계의 용도가 다르다. **음수를 「낡음」으로 바꾸는 식의 수정은 하지
   않는다** — 그러면 락 대기 스레드가 재수집해 버스트 합치기가 깨진다(§2.10 의 이중검사 논거).
5. **`_collect_once` 의 시도 스탬프 갱신이 예외 경로를 덮지 않았다 (Minor).** 스탬프 대입이
   `_run_collect_cycle` **뒤**에 있어, 그 안에서 예외가 새면 스탬프가 안 찍히고 예외가
   `do_GET` 까지 올라간다 — 응답 없이 연결이 끊기고 **다음 요청도 무한히 같은 실패를 반복**한다.
   `_collect_once` docstring 이 막으려던 것이 바로 그것이고, `collect_if_older_than` 의
   "예외를 올리지 않는다"는 약속도 코드로 강제되지 않았다. `finally` 로 스탬프를 옮기고
   `_maintenance_loop` 와 같은 형태의 최종 방어선을 요청 경로에도 둔다.

---

## 1. 요구사항

### 요구 1 (Q1) — 수집 주기

> "5초마다 데이터 수집을 할 필요가 있나? 화면 갱신 시에 하면 되지 않나?"

**완료 판정 기준**

1. `hub/bin/hub_server.py` 에 고정 주기 수집 루프가 없다 — 수집은 HTTP 요청이 이끈다.
2. 브라우저를 아무도 열지 않은 1시간 동안 `collect_snapshot` 호출 횟수가 **12회 이하**다
   (배경 상한 5분 × 12). 현행은 720회다.
3. 허브 페이지를 열면 응답 본문이 그 요청 시점 기준 **2초 이내**에 수집된 스냅샷이다.
4. `/hub server status` 가 "수집이 실제로 되고 있는가"에 답한다 — 영구 `false` 인 죽은
   필드를 남기지 않는다.
5. `bash tests/run.sh` 전부 통과 + `python3 -m unittest discover -s tests/hub -t .` 전부 통과.

### 요구 2 (Q2) — 상세 가독성

> "div.detail 작성 시 문단 개행 처리 및 ul 스타일 등을 사용해서 가독성을 높일 수 있게 해줘."

**완료 판정 기준**

1. `commands/dashboard.md` 의 `log` 절차가 상세 문자열을 문단(`<p>`)·목록(`<ul><li>`)·
   인라인 코드(`<code>`)로 바꾸는 **결정적** 규약을 갖는다(LLM 재량 태그 조립 없음).
2. 그 세 태그에 대응하는 CSS 규칙이 `commands/dashboard.md` 의 `<style>` 에 있다.
3. **기존 형태의 상세(한 블록·목록 없음·백틱 없음)의 결과 HTML 이 종전과 문자 단위로 같다.**
4. 조립 결과가 태그 사이 개행 없는 한 줄이므로 **같은 입력의 항목 줄 수가 이 변경 때문에 늘지
   않는다.** 고정되는 것은 아니다 — 블록 텍스트 안의 단일 개행은 보존되므로 여러 줄 상세는
   지금과 똑같이 여러 줄 항목을 만든다(§3.5·§8.4).
5. `tests/run.sh` 의 T22-128(`.entry .detail` 규칙 꼬리 고정)이 계속 통과한다.

### 요구 3 (Q3) — 세션 구분

> "여러 개의 세션 리스트가 보이는 경우 어떤 세션인지 구분이 안 된다. session id 외에 세션을
> 나타내고 구분할 수 있는 방법이 있을까?"

**완료 판정 기준**

1. 허브 카드의 세션 줄마다 **시작 시각(절대)** 과 **`short_id`** 가 보인다.
2. 실측 최악 사례(daily-brief 카드, 표시 세션 9개, 발췌 해시 distinct 1, 칩 distinct 1)에서
   9개가 서로 구분된다 — 시작 시각 distinct 9 로 이미 충족된다.
3. `.session-line`(첫 줄)의 구성 요소가 종전과 같다 — 좁은 카드의 `flex-wrap` 거동 불변.
4. 스냅샷에 `Date.now()` 파생값이 들어가지 않는다 → `snapshot_content_key` 안정성 유지
   (같은 스냅샷을 두 번 직렬화하면 같은 키).
5. `tests/run.sh` T25-11 통과(동적 값은 `escapeHtml` 경유).

---

## 2. Q1 — 허브 상주 서버의 수집을 요청 구동으로 바꾼다

### 2.1 현행 동작과 근거

| 사실 | 근거 |
|------|------|
| 수집 루프가 `server_collect_interval_seconds`(기본 5) 마다 돈다 | `hub_model.py:37`, `hub_server.py:237` |
| 한 사이클 = 하트비트 touch → 수집 → 사용량 API 게이트 → 하트비트 touch | `hub_server.py:223-237` |
| `collect_snapshot` 1회 = 8~11ms, `os.stat()` **635회**, 파일 열기 6, 디렉토리 스캔 20 (프로젝트 3개) | 실측 5회 |
| 비용은 `scan_roots_for_projects(config.roots, scan_depth=3)` 트리 크기에 선형 | `hub_collect.py:408` |
| 브라우저 폴링은 60초 주기 + 탭 가시성 게이트 | `hub_template.html:672`, `:1389` |
| 응답 본문이 직전과 같으면 렌더 자체를 건너뛴다 | `hub_template.html:1362-1374` |
| **즉 사용자가 얻는 신선도 상한은 이미 60초이고, 탭이 숨으면 0회다** | 위 두 항목 |
| HTTP 핸들러는 인메모리 스냅샷이 아니라 **디스크의 `hub.html` 을 `read_bytes`** 로 서빙한다. 없으면 404 | `hub_server.py:60-66` |
| 프로젝트 대시보드 경로는 수집이 만든 레지스트리 조회로만 서빙된다. 기동 직후 레지스트리는 `{}` → 전부 404 | `hub_server.py:68-82`, `:252` |
| 레지스트리 갱신은 딕셔너리 통째 교체라 GIL 하 동시 읽기가 이미 안전 | `hub_server.py:147-148` |
| `hub.html` 쓰기는 `mkstemp` + `Path.replace` 로 원자적 | `hub_collect.py:443-457`, `:460-472` |
| 하트비트를 찍는 코드는 **수집 루프 안에만** 있다 | `hub_server.py:225`, `:234` |
| TTL = 주기 × 3, 하한 15초 | `hub_server_state.py:57-68` |
| TTL 소비 지점 4곳 | `hub_hook.py:137`, `hub.py:67`, `hub_daemon.py:163`, `hub_daemon.py:295` |
| `collect_stalled = process_present and not alive` | `hub_daemon.py:303` |
| `start_server` 는 spawn 후 **하트비트 신선화**를 폴링해 기동 성공을 판정한다 | `hub_daemon.py:172-182` |
| 사용량 API 폴링은 최악 **15초 블로킹**(HTTP 10s + Keychain subprocess 5s) | `hub_usage_fetch.py:24-25`, `:61-65`, `:120` |
| 백오프 상태는 `_collect_loop` 의 **지역 변수** — 그것이 결정 A3(전역 가변 상태 금지) | `hub_server.py:216-222` |
| `prune_old_event_files` 는 훅도 매 이벤트마다 독립적으로 부른다 — 수집이 멎어도 리텐션 고지는 지켜진다 | `hub_collect.py:404`, `hub_hook.py:173` |
| `/hub`(인자 없음)는 서버가 죽었거나 `hub.html` 이 없으면 그 자리에서 수집해 `file://` 를 연다 | `hub.py:83-105` |
| `_validate_config_overrides` 는 `_CONFIG_FIELD_TYPES[key]` 를 직접 인덱싱한다 — 새 필드를 넣고 타입표를 안 채우면 KeyError 로 config 읽기가 통째로 터진다 | `hub_collect.py:105`, `:69-81` |
| 폐기 안내(`_DEPRECATED_CONFIG_FIELD_GUIDANCE`)는 dataclass 에 **없는** 키에만 발동한다 | `hub_collect.py:86-103`, `:101-104` |
| 성공한 수집은 `clear_collect_failure()` 를 부른다 — 호출부는 정확히 2곳 | `hub_server.py:132`, `hub.py:42` |

### 2.2 미확인 지점의 해소 (직접 읽어 확정)

메인 세션이 남긴 유일한 미해결 질문:

> 허브 페이지를 로드하지 않고 `/project/<key>/dashboard.html` 만 폴링하는 경로(상세 패널을
> 열어 둔 채 허브 탭을 숨긴 상태)에서 레지스트리가 갱신되지 않는 창이 생기는가.

**결론: 그런 경로가 실제로 존재한다. 그러나 그 경로의 응답 정확성은 레지스트리 신선도에
의존하지 않는다.** 근거:

1. 상세 패널은 모달이 아니라 **iframe** 이다 — `panelFrameEl.contentWindow.location.replace(url)`
   로 `/project/<key>/dashboard.html` 을 로드한다(`hub_template.html:1462`,
   `:1405` `PROJECT_DASHBOARD_PATH_SUFFIX`).
2. 그 iframe 안의 문서는 `/dashboard` 생성물이고, **자기 폴링을 따로 돈다**:
   `setInterval(poll, POLL_INTERVAL_MS)` — `commands/dashboard.md:1546`, 주기 60000
   (`:1423`).
3. 결정적 차이: 허브의 폴링은 가시성 게이트가 있고(`hub_template.html:1389`)
   **대시보드의 폴링에는 게이트가 없다**(`commands/dashboard.md:1546` 는 `poll` 을 그대로
   넘긴다). 따라서 허브 탭을 숨기면 **허브는 폴링을 멈추지만 iframe 안 대시보드는 계속
   `/project/<key>/dashboard.html` 을 때린다.** → 질문의 경로는 실재한다.
4. 그런데 `_serve_project_dashboard` 는 스냅샷을 서빙하지 않는다. 레지스트리에서 **경로만**
   찾고 그 파일을 매 요청 `Path(target_path).read_bytes()` 로 새로 읽는다
   (`hub_server.py:71-80`). 즉 응답 **내용은 항상 최신**이고, 레지스트리가 낡아서 생길 수
   있는 유일한 오류는 "새로 생긴 티어 1 프로젝트의 키를 모른다" 뿐이다. 그런데 그 키는
   허브 페이지 렌더에서만 나오므로, 허브 페이지를 열지 않은 사용자가 그 키를 요청할 방법이
   없다.
5. **남는 실제 위험은 하나다**: 패널을 열어 둔 채 서버가 재기동되면 레지스트리가 `{}` 로
   초기화되고, iframe 의 다음 폴링이 404 를 받는다. 그 창은 허브 탭을 다시 볼 때까지 닫히지
   않는다(허브 폴링이 멈춰 있으므로).

→ **설계 반영**: 신선도 게이트를 **두 라우트 모두**에 건다. 4번 때문에 필수는 아니지만
5번을 자기 치유로 만들고, 호출 지점이 `do_GET` 한 곳으로 모여 분기가 줄어든다. 비용은
"패널을 열어 둔 숨은 탭"에서 60초당 수집 1회이며, 현행 60초당 12회 대비 12배 감소다.

### 2.3 채택안 — 요청 구동 수집 + 유지보수 티커

```
[HTTP 요청 스레드 N개]                      [유지보수 티커 스레드 1개]
        │                                            │
  do_GET: 경로 화이트리스트 판정                     5초마다:
        │                                              ├ 하트비트 touch
        ├─ 인식 못 함 → 404 (수집하지 않는다)          ├ 배경 수집 상한(5분) 보장
        │                                              │   → 같은 refresher 를 부른다
        └─ 인식함                                      ├ 사용량 API 게이트(최악 15초 블로킹)
             └ refresher.collect_if_older_than(        └ 하트비트 touch
                   now, 2초)
                  ├ 창 안 → 즉시 반환(캐시 서빙)
                  └ 창 밖 → 락 획득 → 이중 검사 → 1회 수집
             └ 본문 생산(hub.html read_bytes / 레지스트리 조회)
```

핵심 설계 4개:

**(a) 신선도 창 = 2초.** 근거 셋을 문서·주석에 남긴다.
- 한 페이지 로드가 만드는 요청 버스트(`/hub.html` + 열려 있던 패널의
  `/project/<key>/dashboard.html`)를 한 번으로 합치기에 충분하다.
- 사람이 인지하지 못할 만큼 짧다.
- **30초 같은 큰 값을 쓸 수 없는 이유**: `hub/README.md:110-111` 이 "즉시 보고 싶으면
  우상단 새로고침 버튼을 누른다"를 약속한다. 창이 30초면 그 버튼이 최대 30초 낡은 데이터를
  돌려주고 문서화된 약속이 깨진다. 2초는 그 약속을 지킨다.
- **0(항상 수집)을 쓰지 않는 이유**: 새로고침 버튼 연타·패널 열기 같은 버스트가 매번
  8~11ms + stat 635회를 낸다. 창은 그 버스트를 공짜로 만든다.
- 이 값은 **config 필드로 만들지 않는다**(YAGNI) — 사용자가 조정할 이유가 없고, config
  필드 하나는 타입표 1행 + 문서 1행 + 경고 표면 1개를 영구히 늘린다.

**(b) 유지보수 티커.** `_collect_loop` → `_maintenance_loop` 로 역할을 바꾼다. 하는 일:
하트비트 touch, 배경 수집 상한 보장, 사용량 API 게이트. **사용량 API 는 절대 요청 경로에
올리지 않는다** — 최악 15초 블로킹(`hub_usage_fetch.py:120`)을 HTTP 응답에 실으면 브라우저가
15초 멈춘다. 백오프 상태(`usage_api_poll_state`)는 이 함수의 지역 변수로 남긴다(결정 A3).

**(c) 배경 수집 상한 = 5분.** `file://` 신선도와 관측 가능성을 위한 것이며 브라우저 신선도를
위한 값이 아니다(§2.5).

**(d) `collect_stalled` 를 3상태 건강도로 재정의한다.** §2.6.

### 2.4 기각안과 그 이유

| 기각안 | 이유 |
|--------|------|
| **주기값만 5→30초로 올리고 TTL 을 분리한다**(조사 에이전트 권고) | 사용자 질문은 비용이 아니라 "아무도 소비하지 않는 데이터를 왜 만드나"다. 30초는 그 질문에 답하지 않는다. 그리고 **주기 > TTL 이 되는 순간 루프 자신의 하트비트가 만료되므로 하트비트 분리 개정이 어느 안에서도 필수**다 — 그 개정을 치른 뒤 요청 구동의 추가 비용은 락 하나뿐이라, 보수안의 "구조 리스크 0" 이라는 장점 자체가 성립하지 않는다 |
| **인메모리 스냅샷을 응답에 직접 렌더한다** | `hub.html` 은 `file://` 소비자(§2.5)와 `cmd_open` 의 `HUB_HTML_PATH.exists()` 판정(`hub.py:84`)이 함께 쓰는 산출물이다. 디스크를 정본에서 빼면 두 소비자를 동시에 잃는다. 지금 구조(디스크 정본 + 원자적 교체)는 이미 옳다 |
| **신선도 창을 `hub.html` 의 mtime 으로 판정한다** | `_run_collect_cycle` 은 내용이 같으면 쓰지 않는다(`hub_server.py:129`) — mtime 은 "마지막 **변화** 시각"이지 "마지막 수집 시각"이 아니다. 이 혼동은 이미 `hub_template.html:1044` 부근 주석이 경고하고 있는 함정이다 |
| **락 없이 각 요청이 독립 수집** | 한 페이지 로드가 만드는 동시 요청이 각자 수집하고 각자 `last_content_key` 를 갱신해, 쓰기 억제 판정이 깨진다(내용이 같은데도 매번 쓴다). 락 + 이중 검사가 그 버스트를 1회로 합친다 |
| **404 경로에도 신선도 게이트** | favicon 등 인식 못 하는 요청이 수집을 유발한다. 화이트리스트 밖 요청에 비용을 주지 않는다 |
| **`collect_stalled` 를 그대로 둔다** | 하트비트가 수집에서 분리되면 `process_present and not alive` 는 "수집이 멎었다"를 뜻하지 않게 되고, 필드는 영구 `false` 인 죽은 관측 창구가 된다. 조용히 죽은 필드로 남기지 않는다 |

### 2.5 `file://` 신선도 회귀 — 세 갈래 중 (b) 채택

**노출 범위 확정.** 요청 구동으로 바꾸면 브라우저를 열지 않는 동안 디스크 `hub.html` 이
낡는다. 영향을 받는 사람은 **`/hub` 를 쓰지 않고 `file:///Users/…/.claude/hub/hub.html`
북마크를 직접 여는 사용자**로 한정된다. 근거:

- `cmd_open`(`hub.py:83-105`)은 서버가 살아 있고 `hub.html` 이 실재하면 `http://` URL 을
  열고, 그 외에는 **그 자리에서 1회 수집**한 뒤 `file://` 를 연다. 어느 분기에서도 낡은
  파일을 보여주지 않는다.
- 훅 폴백도 막힌다: `should_spawn_collect` 는 `server_alive` 면 항상 `False`
  (`hub_server_state.py:120-121`)이고, 티커가 하트비트를 찍으므로 `server_alive` 는 계속
  참이다. 즉 훅이 대신 신선하게 해 주지 않는다. → 이것은 **진짜 회귀**다.

| 갈래 | 판정 | 이유 |
|------|------|------|
| (a) 감수하고 문서에 명시 | 기각 | 회귀를 문서로 무마하는 것이고, 무엇보다 **`collect_health` 가 관측 불가능해진다**(아래) |
| **(b) 유지보수 티커에 저빈도(5분) 수집을 얹는다** | **채택** | 하루 288회 ≈ 2.9초 CPU. 현행 17,280회 대비 **98.3% 감소**이면서 기존 보장을 하나도 잃지 않는다. 그리고 아무도 브라우저를 열지 않는 서버가 `collect_health` 를 영구히 `never_collected` 로 보고하는 문제를 함께 없앤다 — 그 상태에서는 사용자가 "건강한데 한가한 것"과 "고장난 것"을 구분할 수 없다 |
| (c) 훅 폴백을 되살린다(`should_spawn_collect` 가 `server_alive` 대신 `hub.html` 나이를 본다) | 기각 | 수집 비용을 세션 훅으로 되돌리는 것이고(검수 M4 가 명시적으로 분리한 지점), 신선도가 "세션 활동 유무"에 매이며, spawn 버스트 디바운스(`SPAWN_STAMP_PATH`) 로직이 두 소비자를 갖게 된다 |

(b)의 상한값은 **주기가 아니라 상한**이라는 점이 중요하다. 티커도 같은 refresher 를
`collect_if_older_than(now, 5분)` 으로 부르므로, 사용자가 페이지를 보고 있는 동안에는
요청 구동 수집이 이미 나이를 갱신해 티커가 아무것도 하지 않는다. **수집 경로는 하나다.**

### 2.6 `collect_stalled` 의 정직한 재정의

하트비트가 수집에서 분리되면 하트비트는 "유지보수 티커가 살아 있다"만 뜻한다. 그것도 여전히
관측 가치가 있다(티커가 죽으면 하트비트가 멎어 훅 폴백이 켜지고 사용량 패널이 언다). 그래서
**필드를 지우지 않고 이름을 사실에 맞춘다**:

- `collect_stalled: bool` → `maintenance_stalled: bool` — 판정식은 **그대로**
  (`process_present and not alive`). 이름만 사실에 맞춘 rename 이다.
- 새 필드 `collect_health: Literal["ok", "failing", "never_collected"]` — "수집이 실제로
  되고 있는가"에 답한다.
- 새 필드 `last_collect_success_age_ms: int | None` — "마지막으로 수집이 성공한 게 언제인가".
  요청 구동에서는 고정 주기에서 유추할 수 없으므로 이 값이 유일한 답이다.

판정식은 **순수 함수**로 잎 모듈에 둔다. 시각·상태는 호출자가 주입한다.

```python
# hub_server_state.py — 잎·순수. 시각도 상태도 인자로만 받는다.
CollectHealth = Literal["ok", "failing", "never_collected"]

def evaluate_collect_health(
    last_success_at_ms: int | None,
    last_failure_at_ms: int | None,
) -> CollectHealth:
    """마지막 성공·실패 시각으로 수집 건강도를 판정한다(순수).

    요청 구동 수집(개정 2)에서는 "최근에 수집이 없었다"가 고장이 아니다 — 아무도 페이지를
    열지 않았다는 뜻일 수 있다. 그래서 나이(age)로 판정하지 않고 **성공과 실패의 순서**만
    본다. 동시각(둘이 같음)은 성공으로 접는다 — 한 사이클이 성공하면
    `clear_collect_failure()` 가 실패 기록을 지운 뒤 성공 스탬프를 찍으므로, 같은 ms 에
    둘이 잡히면 성공이 나중이다.
    """
    if last_failure_at_ms is None:
        return "ok" if last_success_at_ms is not None else "never_collected"
    if last_success_at_ms is None:
        return "failing"
    return "failing" if last_failure_at_ms > last_success_at_ms else "ok"
```

성공 시각의 출처는 새 스탬프 파일이다. `hub.html` 의 mtime 을 쓸 수 없는 이유는 §2.4 표
3행과 같다(쓰기 억제 때문에 "마지막 변화 시각"이다). 기존 `SERVER_HEARTBEAT_PATH`·
`SPAWN_STAMP_PATH` 와 **완전히 같은 모양**이라 새 개념이 0개다.

> **주의 (구현 체크리스트)**: `tests/run.sh:2366-2372`(T25-10)은 순수 모듈 파일에서
> `open(`·`Path(`·`os.` 라는 **문자열 자체**를 금지한다. 주석에도 못 쓴다 — 위 docstring 에
> "`os.stat`" 이나 "`Path(`" 를 예로 적으면 그 자리에서 테스트가 깨진다.

### 2.7 config 필드 처리 — 결론

`server_collect_interval_seconds` 는 **제거하고** `server_heartbeat_interval_seconds` 를
신설한다. 저울질은 이렇다.

- **이름 부채가 실재한다.** 필드를 남겨 "티커 주기"라는 새 뜻을 주면 전역 지침의
  「이름만 읽고 역할을 알 수 있어야 한다」를 정면으로 어긴다. 그리고 이 값은 TTL 의
  입력(`server_heartbeat_ttl_ms`)이기도 해서, 이름이 "collect" 인 채로는 TTL 이 무엇의 3배인지
  아무도 설명할 수 없다.
- **"알 수 없는 필드" 경고가 나는 건 맞지만, 이 저장소에는 그 경우를 위한 안내 채널이 이미
  있다.** `_DEPRECATED_CONFIG_FIELD_GUIDANCE`(`hub_collect.py:86-88`)는 dataclass 에 **없는**
  키에만 발동하도록 설계돼 있고, `serve_port_candidates` 가 정확히 같은 이주를 거쳤다.
  거기에 한 줄 넣으면 사용자는 "오타인지 확인하십시오" 가 아니라
  "`server_heartbeat_interval_seconds` 로 대체됐습니다" 를 본다. 이것이 설계된 이주 경로다.
- TTL 공식은 **바꾸지 않는다**(×3, 하한 15초). 인자 이름만 `heartbeat_interval_seconds` 로
  바꾼다. 기본값 5 도 유지 → **TTL 은 종전과 정확히 같은 15초**다.

> **관측 정정 (메인 세션 방향 지시에 대한 이견 아님, 사실 정정)**: 브리핑은
> `tests/hub/test_hub_server_state.py:95-104`(ttl(1)=15000·ttl(5)=15000·ttl(60)=180000)이
> "TTL 분리 시 정면으로 깨진다"고 적었다. **이 설계에서는 깨지지 않는다.** 공식이 그대로이고
> 세 호출이 모두 위치 인자이기 때문이다(`server_heartbeat_ttl_ms(1)`). 클래스 docstring 의
> "수집 주기 3배" 문구만 "하트비트 주기 3배"로 고친다. 이는 채택안의 장점이므로 기록한다.

**신선도 창(2초)과 배경 수집 상한(5분)은 config 필드로 만들지 않는다** — 모듈 상수다(YAGNI).

### 2.8 변경할 파일과 변경 내용

| 파일 | 변경 |
|------|------|
| `hub/bin/hub_server.py` | `SNAPSHOT_FRESHNESS_WINDOW_MS`·`BACKGROUND_COLLECT_MAX_AGE_MS` 상수 신설 / `_SnapshotRefresher` 클래스 신설 / `do_GET` 을 "경로 판정 → 게이트 → 본문 생산" 3단으로 재구성 / `_collect_loop` → `_maintenance_loop`(수집 호출을 refresher 로 위임) / `_run_collect_cycle` 에 성공 스탬프 touch 추가 / `run_server` 가 refresher 를 만들어 `httpd` 에 싣고 티커에 넘김 / `log_message` 의 "5초 폴링" 주석 정정 / 모듈 docstring 갱신 |
| `hub/bin/hub_server_state.py` | `CollectHealth` Literal + `evaluate_collect_health` 신설 / `ServerStatus.collect_stalled` → `maintenance_stalled`, `collect_health`·`last_collect_success_age_ms` 추가 / `server_heartbeat_ttl_ms` 인자명·docstring / 상수 주석(`SERVER_HEARTBEAT_TTL_MULTIPLIER`) |
| `hub/bin/hub_model.py` | `HubConfig`: `server_collect_interval_seconds` 제거, `server_heartbeat_interval_seconds: int = 5` 추가(주석에 "하트비트 touch 주기 — TTL 의 입력" 명시) |
| `hub/bin/hub_collect.py` | `_CONFIG_FIELD_TYPES` 1행 교체(**필수 — 안 채우면 KeyError 로 config 읽기가 통째로 실패한다**) / `_DEPRECATED_CONFIG_FIELD_GUIDANCE` 1행 추가 / `COLLECT_SUCCESS_STAMP_PATH` 상수 + `touch_collect_success_stamp()` + `read_collect_success_stamp_mtime_ms()` / `clear_server_state` 에서 이 스탬프는 **지우지 않는다**(서버 생애가 아니라 수집 이력이다 — 주석으로 근거) |
| `hub/bin/hub_daemon.py` | `:163`·`:295` 의 config 필드명 / `server_status()` 가 새 3필드를 채움 / `log_tail` 게이트를 **`crashed_evidence or maintenance_stalled or collect_health == "failing"`** 으로 (↓ 정정 3) |
| `hub/bin/hub.py` | `_server_is_alive` 의 config 필드명 / `_collect_and_write` 에 성공 스탬프 touch / `cmd_status` 출력 `server_collect_stalled` → `server_maintenance_stalled` + `server_collect_health`·`last_collect_success_age_ms` 추가 |
| `hub/bin/hub_hook.py` | `:137` config 필드명 / 모듈 docstring 의 "서버가 5초 주기로 수집을 전담" → 요청 구동 서술 |
| `hub/README.md` | `:14`, `:99`, `:110-112`, `:121`, `:402` (§6) |
| `commands/hub.md` | `:63`, `:121-124`, `:219-220` (§6) |
| `commands/dashboard.md` | `:915` (§6) |
| `tests/hub/test_hub_server.py` | §2.11 |
| `tests/hub/test_hub_server_state.py` | §2.11 |
| `tests/hub/test_hub_daemon.py` | §2.11 |
| `tests/hub/test_hub.py` | §2.11 |
| `tests/hub/test_hub_collect.py` | §2.11 |
| `tests/run.sh` | T25-121~T25-124 (§2.11) |

**갱신하지 않는 것**: `docs/prps/*.md`(과거 결정의 정본 — 인용만), `README.md`(§6 오폭 주의).

### 2.9 데이터 모델·인터페이스 변경

```python
# hub_model.py — HubConfig (변경분만)
-   server_collect_interval_seconds: int = 5       # 수집 루프 주기
+   # 유지보수 티커가 하트비트를 찍는 주기. 수집 주기가 아니다(개정 2 — 수집은 요청이 이끈다).
+   # server_heartbeat_ttl_ms 의 입력이기도 하다: TTL = max(이 값 × 3, 15초).
+   server_heartbeat_interval_seconds: int = 5
```

```python
# hub_server_state.py (신설·변경)
CollectHealth = Literal["ok", "failing", "never_collected"]

def evaluate_collect_health(
    last_success_at_ms: int | None, last_failure_at_ms: int | None
) -> CollectHealth: ...

def server_heartbeat_ttl_ms(heartbeat_interval_seconds: int) -> int: ...   # 공식·값 불변

@dataclass(frozen=True)
class ServerStatus:
    record: ServerRecord | None
    process_present: bool
    heartbeat_age_ms: int | None
    alive: bool
    http_ok: bool
    crashed_evidence: bool
    log_tail: str | None
    orphaned_evidence: bool
    maintenance_stalled: bool                 # (구) collect_stalled — 판정식 동일, 이름만 사실에 맞춤
    collect_health: CollectHealth             # 신설
    last_collect_success_age_ms: int | None    # 신설
```

```python
# hub_collect.py (신설)
COLLECT_SUCCESS_STAMP_PATH = HUB_HOME / "last_collect_success"

def touch_collect_success_stamp() -> None: ...
def read_collect_success_stamp_mtime_ms() -> int | None: ...
```

```python
# hub_server.py (신설·변경)
SNAPSHOT_FRESHNESS_WINDOW_MS = 2000
BACKGROUND_COLLECT_MAX_AGE_MS = 5 * 60 * 1000

class _SnapshotRefresher:
    def __init__(self, httpd: http.server.ThreadingHTTPServer) -> None: ...
    def collect_if_older_than(self, now_ms: int, max_age_ms: int) -> None: ...

def _maintenance_loop(
    config: hub_model.HubConfig,
    stop_event: threading.Event,
    refresher: _SnapshotRefresher,
) -> None: ...
```

`/hub status` 공개 출력 계약 변경(`commands/hub.md:219-220`):

| 종전 | 신규 |
|------|------|
| `server_collect_stalled` | `server_maintenance_stalled` |
| — | `server_collect_health` (`ok`\|`failing`\|`never_collected`) |
| — | `last_collect_success_age_ms` (ms 또는 null) |

### 2.10 코드 스니펫

```python
# ---- 요청 구동 수집 (개정 2) ----
# 창 안이면 캐시된 결과를 그대로 서빙하고, 넘으면 락을 잡고 1회만 수집한다.
# 2000ms 인 근거: (1) 한 페이지 로드가 만드는 요청 버스트(/hub.html + 열려 있던 패널의
# /project/<key>/dashboard.html)를 한 번으로 합치기에 충분하다 (2) 사람이 인지하지 못할 만큼
# 짧다 (3) 이보다 크게 잡으면 "즉시 보고 싶으면 새로고침 버튼"이라는 hub/README.md 의
# 약속이 그 차이만큼 거짓이 된다.
SNAPSHOT_FRESHNESS_WINDOW_MS = 2000
# 요청과 무관하게 수집을 보장하는 상한. **브라우저 신선도를 위한 값이 아니다** — 브라우저는
# 자기 요청으로 위 창을 통해 신선도를 얻는다. 이 값이 존재하는 이유는 둘뿐이다:
# (1) `/hub` 를 거치지 않고 file:// 북마크로 hub.html 을 직접 여는 경로의 신선도
# (2) collect_health 가 계속 관측 가능하도록 — 아무도 페이지를 열지 않는 서버가 영구히
#     "never_collected" 를 보고하면 사용자가 정상과 고장을 구분할 수 없다.
BACKGROUND_COLLECT_MAX_AGE_MS = 5 * 60 * 1000


class _SnapshotRefresher:
    """요청 구동 수집의 임계 구역(개정 2).

    왜 클래스인가: ThreadingHTTPServer 의 여러 요청 스레드가 공유하는 가변 상태(마지막 수집
    시도 시각·last_content_key)와 그것을 지키는 락이 한 덩어리로 묶여야 한다. 모듈 전역
    변수로 두면 결정 A3(전역 가변 상태 금지)를 어기므로, 기존 `dashboard_paths_by_key`
    (결정 N3)와 같은 관례로 서버 인스턴스에 실어 둔다.

    수집 경로는 이 클래스 하나다 — 요청도, 유지보수 티커도 `collect_if_older_than` 만
    부르고 창 크기만 다르게 준다. 그래서 두 경로가 동시에 수집해 `last_content_key` 를
    각자 갱신하는(쓰기 억제 판정이 깨지는) 일이 구조적으로 생길 수 없다.
    """

    def __init__(self, httpd: http.server.ThreadingHTTPServer) -> None:
        self._httpd = httpd
        self._lock = threading.Lock()
        self._last_attempt_at_ms: int | None = None
        self._last_content_key: str | None = None

    def collect_if_older_than(self, now_ms: int, max_age_ms: int) -> None:
        """마지막 수집 시도가 max_age_ms 보다 오래됐으면 1회 수집한다. 예외를 올리지 않는다."""
        if self._is_within(now_ms, max_age_ms):
            return
        with self._lock:
            # 이중 검사. 진입 시점의 시각을 그대로 다시 쓴다 — 락을 기다리는 동안 다른
            # 스레드가 수집을 마쳤다면 이 요청은 그 결과를 쓰면 된다.
            # (검수 2회차 Minor B 정정) 초안은 "여기서 시계를 다시 읽으면 버스트가 합쳐지지
            # 않는다"고 적었으나 **사실이 아니다** — 스탬프는 수집 **완료 후**(`finally`)에
            # 찍히므로 락을 놓은 직후 재읽는 시계는 스탬프와 거의 같고, 재읽어도 나이 ≈ 0 으로
            # 창 안이라 버스트는 그대로 합쳐진다(실증: 이 줄을 시계 재읽기로 변이해도
            # SnapshotRefresherTest 8건 전부 통과). 진입 시각 재사용은 관측 가능한 효과가
            # 아니라 "이 요청은 자기가 본 시점 기준으로 판정한다"는 뜻을 분명히 하는 선택이다.
            if self._is_within(now_ms, max_age_ms):
                return
            self._collect_once()

    def _is_within(self, now_ms: int, max_age_ms: int) -> bool:
        if self._last_attempt_at_ms is None:
            return False
        return (now_ms - self._last_attempt_at_ms) < max_age_ms

    def _collect_once(self) -> None:
        """한 사이클을 돌리고 시도 시각을 갱신한다.

        **실패해도 시각을 갱신한다.** 성공에만 스탬프를 찍으면 수집이 계속 실패하는 동안 매
        요청이 재시도를 물고 응답이 그만큼 느려진다 — `touch_spawn_stamp`
        (hub_collect.py:475-482)가 "Popen 이 실패해도 스탬프는 남긴다"로 같은 판단을 이미
        내렸다. 실패 사실은 last_collect_error.json 이 따로 보존한다.
        """
        self._last_content_key, registry = _run_collect_cycle(self._last_content_key)
        _apply_dashboard_registry(self._httpd, registry)
        self._last_attempt_at_ms = int(time.time() * 1000)
```

```python
    def do_GET(self) -> None:
        """경로 판정 → 신선도 게이트 → 본문 생산. 게이트는 **인식된 경로에만** 건다 —
        favicon 처럼 화이트리스트 밖 요청이 수집을 유발하면 안 된다."""
        is_hub_path = self.path in ALLOWED_REQUEST_PATHS
        dashboard_match = None if is_hub_path else PROJECT_DASHBOARD_PATH_PATTERN.match(self.path)
        if not is_hub_path and dashboard_match is None:
            self.send_error(404)
            return
        # getattr 로 받는다 — `dashboard_paths_by_key`(:71)가 세운 관례와 같다.
        # `self.server` 의 정적 타입(BaseServer)에는 이 속성이 없고, refresher 가 실리지
        # 않은 서버로 핸들러를 단독 구성하는 테스트에서 AttributeError → 500 이 되면
        # 안 된다. None 이면 게이트를 건너뛰고 디스크에 있는 것을 그대로 서빙한다.
        refresher = getattr(self.server, "snapshot_refresher", None)
        if refresher is not None:
            refresher.collect_if_older_than(
                int(time.time() * 1000), SNAPSHOT_FRESHNESS_WINDOW_MS
            )
        if is_hub_path:
            self._serve_hub_html()
            return
        self._serve_project_dashboard(dashboard_match.group(1))
```

```python
def _maintenance_loop(
    config: hub_model.HubConfig,
    stop_event: threading.Event,
    refresher: _SnapshotRefresher,
) -> None:
    """데몬 스레드 본체(개정 2). 수집은 요청이 이끌고, 이 루프는 셋만 한다.

    (1) 하트비트 touch — 사이클 앞뒤로 두 번 찍는다(사이클 안의 사용량 API 호출이 최악
        15초 걸리므로, 그 앞에 한 번 찍어야 외부 관찰자가 일하는 서버를 죽었다고 오판하지
        않는다). 하트비트의 뜻은 이제 "이 티커가 살아 있다"다 — "수집이 성공했다"는
        collect_health 가 따로 답한다.
    (2) 배경 수집 상한 보장 — 요청이 이미 갱신했으면 아무것도 하지 않는다.
    (3) 사용량 API 폴링 게이트 — **절대 요청 경로에 올리지 않는다.** HTTP 타임아웃 10초 +
        Keychain subprocess 5초로 최악 15초 블로킹이다(hub_usage_fetch.py). 백오프 상태는
        이 함수의 지역 변수로 남긴다(결정 A3 — 전역 가변 상태 금지).

    사이클 전체를 try/except 로 감싸는 최종 방어선은 종전과 같은 이유로 유지한다(검수 M2-1).
    """
    usage_api_poll_state = hub_usage.UsageApiPollState()
    while not stop_event.is_set():
        try:
            hub_collect.touch_server_heartbeat()
            refresher.collect_if_older_than(int(time.time() * 1000), BACKGROUND_COLLECT_MAX_AGE_MS)
            usage_api_poll_state = _run_usage_api_poll_cycle(
                int(time.time() * 1000), usage_api_poll_state, config
            )
            hub_collect.touch_server_heartbeat()
        except Exception as error:
            print(f"유지보수 티커 사이클에서 처리되지 않은 예외: {error}", file=sys.stderr)
        stop_event.wait(config.server_heartbeat_interval_seconds)
```

```python
# run_server 안 (변경분)
    httpd.dashboard_paths_by_key = {}
    # 요청 핸들러와 유지보수 티커가 같은 refresher 를 공유한다 —
    # dashboard_paths_by_key 와 같은 관례로 서버 인스턴스에 싣는다(결정 N3).
    httpd.snapshot_refresher = _SnapshotRefresher(httpd)
    ...
    maintenance_thread = threading.Thread(
        target=_maintenance_loop, args=(config, stop_event, httpd.snapshot_refresher), daemon=True
    )
    maintenance_thread.start()
```

```python
# hub_daemon.server_status() (변경분)
    maintenance_stalled = process_present and not alive        # 판정식 불변, 이름만 사실에 맞춤
    success_at_ms = hub_collect.read_collect_success_stamp_mtime_ms()
    failure = hub_collect.read_last_collect_failure()
    collect_health = hub_server_state.evaluate_collect_health(
        last_success_at_ms=success_at_ms,
        last_failure_at_ms=(failure or {}).get("at_ms"),
    )
```

### 2.11 이 절의 테스트 계획

**깨지는 기존 테스트와 대응**

| 위치 | 왜 깨지는가 | 어떻게 고치는가 |
|------|------------|----------------|
| `test_hub_server.py:258`·`:290`·`:317` | `HubConfig(server_collect_interval_seconds=0)` — 필드가 없어져 `TypeError` | `server_heartbeat_interval_seconds=0` 으로 교체 |
| `test_hub_server.py:264-279` `test_successful_cycle_fills_dashboard_paths_by_key` | `_collect_loop` 가 더 이상 직접 수집하지 않는다 | 레지스트리 적용은 이제 `_SnapshotRefresher._collect_once` 의 책임이므로 새 `SnapshotRefresherTest` 로 **이동**. 티커 쪽에는 "티커가 `collect_if_older_than` 을 배경 상한으로 부른다"만 남긴다 |
| `test_hub_server.py:281-295` `test_failed_cycle_keeps_previous_registry` | 같음 | 같은 이유로 `SnapshotRefresherTest` 로 이동(검증 대상은 `_apply_dashboard_registry(None)` 계약이며 그대로 유효) |
| `test_hub_server.py:298-323` `CollectLoopResilienceTest` | `_collect_loop` 이름 소멸 + 루프가 수집을 안 부르므로 `collect_snapshot` mock 이 안 걸린다 | `_maintenance_loop` 로 대상 변경. 상관 실패 재현은 `refresher.collect_if_older_than` 이 예외를 던지게 해서 유지한다(최종 방어선의 요구는 그대로다) |
| `test_hub_daemon.py:135-161` `ServerStatusCollectStalledTest` | `status.collect_stalled` 필드명 소멸 | 클래스명 `ServerStatusMaintenanceStalledTest`, 단정 `status.maintenance_stalled`. **판정식이 같으므로 기대값은 그대로다** |
| `test_hub.py:223-228` `_make_status` | `ServerStatus` 생성 kwargs 3개 변화(frozen dataclass, 기본값 없음) | `maintenance_stalled=`, `collect_health="ok"`, `last_collect_success_age_ms=None` 추가 |
| `test_hub.py:239-245` | `payload["server_collect_stalled"]` 키 소멸 | `server_maintenance_stalled` 로 교체 + `server_collect_health` 단정 추가 |
| `test_hub_server_state.py:94-104` `ServerHeartbeatTtlMsTest` | **깨지지 않는다** (§2.7 정정) | docstring "수집 주기 3배" → "하트비트 주기 3배" 만 |

**신규 단위 테스트**

| 파일 | 클래스 / 케이스 |
|------|----------------|
| `test_hub_server_state.py` | `EvaluateCollectHealthTest` — ① 둘 다 None → `never_collected` ② 성공만 → `ok` ③ 실패만 → `failing` ④ 실패가 더 최신 → `failing` ⑤ 성공이 더 최신 → `ok` ⑥ 동시각 → `ok`(동시각 규약 고정) |
| `test_hub_server.py` | `SnapshotRefresherTest` — ① 창 안 2회 호출 → `collect_snapshot` 1회 ② 창 밖 2회 호출 → 2회 ③ 첫 호출(스탬프 없음) → 반드시 수집 ④ **버스트 합치기**: `threading.Barrier` 로 N개 스레드를 동시 진입시키고 느린 fake collect 를 물려 `collect_snapshot` 호출이 정확히 1회임을 확인 ⑤ 수집 실패 후 창 안 재호출 → 재시도하지 않음(시도 스탬프가 실패에도 갱신됨) ⑥ 성공 사이클이 레지스트리를 채움(이동) ⑦ 실패 사이클이 직전 레지스트리를 보존(이동) |
| `test_hub_server.py` | `RequestFreshnessGateTest` — ① `/hub.html`·`/`·`/project/<16hex>/dashboard.html` 은 게이트를 부른다 ② **인식 못 하는 경로는 게이트를 부르지 않는다**(404 경로 비용 0) ③ 게이트가 본문 생산 **전에** 호출된다(첫 요청이 `hub.html` 을 만들어 404 창을 닫는다) |
| `test_hub_server.py` | `MaintenanceLoopTest` — ① 하트비트를 사이클 앞뒤로 찍는다 ② `collect_if_older_than` 을 `BACKGROUND_COLLECT_MAX_AGE_MS` 로 부른다 ③ **사용량 API 폴링이 이 루프에서만 일어난다**(요청 경로 mock 에서는 `hub_usage_fetch` 미호출) |
| `test_hub_collect.py` | ① `server_collect_interval_seconds` 를 담은 config.json → **폐기 안내 문구가 담긴 warning** 이 나오고 나머지 필드는 정상 적용 ② `server_heartbeat_interval_seconds` 타입 오류 시 기본값 폴백 ③ `touch_collect_success_stamp` → `read_collect_success_stamp_mtime_ms` 왕복 ④ 스탬프 부재 시 `None` |
| `test_hub_daemon.py` | `ServerStatusCollectHealthTest` — 실패 기록만 있을 때 `failing` + `log_tail` 채워짐 / 성공 스탬프만 있을 때 `ok` + `log_tail` None / `last_collect_success_age_ms` 가 채워짐 |

**신규 `tests/run.sh` 검사** (T25 그룹, `test_hub_docs_and_constants` 안. ID 는 T25-120 다음)

| ID | 검사 |
|----|------|
| T25-121 | `hub_server.py` 에 `SNAPSHOT_FRESHNESS_WINDOW_MS`·`BACKGROUND_COLLECT_MAX_AGE_MS`·`class _SnapshotRefresher`·`collect_if_older_than` 토큰이 있다. **역방향**: `hub/bin/` 어디에도 `server_collect_interval_seconds` 리터럴이 남지 않았다(이주 완료 증명) |
| T25-122 | 사용량 API 가 요청 경로에 없다. `_maintenance_loop` 본문 범위를 앵커로 추출해 `_run_usage_api_poll_cycle` 호출이 그 안에 있음을 확인하고, `do_GET`·`_serve_hub_html`·`_serve_project_dashboard` 본문에 `hub_usage_fetch`·`_run_usage_api_poll_cycle` 이 **없음**을 확인한다(T25-112 의 줄번호 비교 방식과 같은 관례) |
| T25-123 | `hub_server_state.py` 에 `evaluate_collect_health`·`maintenance_stalled`·`CollectHealth` 가 있다. **역방향**: `hub/bin/` 에 `collect_stalled` 리터럴이 남지 않았다(죽은 필드 회귀 방지) |
| T25-124 | 문서 정합. `hub/README.md` 에 "요청 구동" 이 있고 "5초마다 모든 프로젝트를 다시 수집" 이 없다 / `commands/hub.md` 에 "5초마다 갱신" 이 없다 / `commands/dashboard.md` 에 "기본 5초" 가 없다. **그리고 `README.md` 에 "5초 간격 폴링" 이 여전히 있다** — 그 문장은 `/dashboard` PiP 폴링이며 일괄 치환 오폭의 표적이다(§6) |

### 2.12 이 절의 독립 커밋 메시지 초안

```
perf: 허브 수집을 5초 고정 주기에서 요청 구동으로 바꾼다 — 소비자 신선도 상한은 이미 60초다

상주 서버가 5초마다 collect_snapshot(8~11ms, os.stat 635회)을 돌렸지만 브라우저 폴링은
60초 주기에 탭 가시성 게이트가 걸려 있어, 대부분의 수집 결과는 아무도 읽지 않고 버려졌다.
수집을 HTTP 요청이 이끌게 바꾸고(신선도 창 2초 + 락 이중 검사로 페이지 로드 버스트를 1회로
합침), 고정 주기 루프에는 하트비트·사용량 API 게이트·배경 수집 상한(5분)만 남긴다.

하트비트가 수집에서 분리되면서 collect_stalled(=process_present and not alive)는 더 이상
"수집이 멎었다"를 뜻하지 않는다. 죽은 필드로 남기지 않고, 판정식이 실제로 관측하는 사실에
맞춰 maintenance_stalled 로 이름을 고치고, "수집이 실제로 되고 있는가"는 성공 스탬프와
last_collect_error.json 의 순서를 보는 순수 함수 evaluate_collect_health 로 새로 답한다.

server_collect_interval_seconds 는 뜻이 달라졌으므로 제거하고
server_heartbeat_interval_seconds 를 신설한다 — 기존 config.json 사용자는
_DEPRECATED_CONFIG_FIELD_GUIDANCE 가 대체 필드를 안내한다(serve_port_candidates 와 같은
이주 경로). TTL 공식(주기×3, 하한 15초)과 기본값 5는 그대로라 TTL 은 종전과 같은 15초다.

부수 효과: 기동 직후 첫 요청이 hub.html 을 만들므로, 첫 수집 사이클 전까지 404 가 나던 창이
닫힌다.
```

---

## 3. Q2 — 대시보드 「작업 추적」 상세의 가독성

### 3.1 현행 동작과 근거

| 사실 | 근거 |
|------|------|
| `.detail` CSS 는 한 줄뿐이다: `margin:6px 0 0 48px;font-size:12.5px;color:var(--muted);white-space:pre-wrap;overflow-wrap:anywhere` | `commands/dashboard.md:1331` (발행물 `.claude/dashboard.html:133` 과 문자열까지 동일 — 실측 확인) |
| **T22-128 이 이 규칙이 정확히 `white-space:pre-wrap;overflow-wrap:anywhere}` 로 끝날 것을 요구한다** | `tests/run.sh:2124-2130` |
| `ul.log{list-style:none}` 가 로그 목록에 걸려 있다 | `commands/dashboard.md:1316` |
| 로그 항목 1건은 정확히 11줄(회차 배지 없으면 10줄) | `commands/dashboard.md:163-175` 스키마 |
| `log` 0-b 는 `offset=L, limit=60` 창으로 최신 3~4건을 읽고, 못 찾으면 `limit=120` 재Read | `commands/dashboard.md:706-711` |
| 이스케이프는 `&`→`<`→`>` 순서 **단일 모드**, 상세 미지정 시 `(상세 없음)` | `commands/dashboard.md:729-731`, `:727` |
| `hub_parse.py` 는 `#dz-log` 의 `<li>` 를 파싱하지 않는다 → `.detail` 내부 구조 변경은 허브 티어 강등을 일으키지 않는다 | `hub_parse.py:1-6` 모듈 docstring |
| 허브가 대시보드에서 읽는 상세는 단계 상세(`activeStep.detail`)뿐이다 | `hub_template.html:953` |
| PiP 압축 뷰는 로그 카드를 통째로 숨긴다 → 420px 뷰 검토 대상 아님 | `commands/dashboard.md:1366`, `tests/run.sh` T22-40 |
| 허브 상세 패널(550px)에서 `.detail` 실측 텍스트 폭 399px. 목록 `padding-left:16px` 를 줘도 383px 남는다 | `commands/dashboard.md:1324-1330` 주석의 실측치 |
| 유형 필터는 `.entry` 단위 `display:none` — `.detail` 내부와 무관 | `commands/dashboard.md:1314-1315` |
| 폴링은 `#dz-log` 를 `innerHTML` 로 통째 교체하고 **`<style>` 은 치환하지 않는다** → 열려 있는 창은 새 CSS 를 새로고침 전까지 못 받는다 | `commands/dashboard.md:263-264` |
| 템플릿에 마진 리셋이 없다(`*{box-sizing:border-box}` + `body{margin:0}` 뿐) | `commands/dashboard.md` `<style>` 전수 |
| 발행물 `.claude/dashboard.html` 은 gitignore 대상 — **정본은 `commands/dashboard.md` 하나** | `.gitignore:9` |
| `--soft` 토큰 존재 / `ui-monospace` 는 dashboard.md 에 아직 없다 | `commands/dashboard.md:1250` / grep 결과 0건 |

### 3.2 채택안 — 경량 마크업 규약 (2줄) + 백틱 코드

**규약**
- **빈 줄 = 문단 경계**
- **줄 앞 `- ` = 목록 항목**
- **백틱 쌍 = 인라인 코드**

**변환 순서를 고정한다.** 순서가 규약의 본체다.

1. 상세 전문을 **지금 규칙 그대로** 이스케이프한다(`&`→`<`→`>`). 단일 모드 유지.
2. 빈 줄(공백만 있는 줄 포함)을 경계로 블록을 나눈다.
3. 각 블록을 변환한다.
   - **모든 줄이 `- ` 로 시작하는 블록** → `<ul><li>…</li>…</ul>` 하나. 각 줄의 선행 `- ` 제거.
   - 그 밖의 블록 → `<p>…</p>`.
   - **블록이 하나뿐이고 목록이 아니면 감싸지 않는다** — 텍스트만 넣는다(종전과 동일).
4. 백틱으로 감싼 구간을 `<code>…</code>` 로 바꾼다. 왼쪽부터 짝지어 치환하고, 짝이 없는
   마지막 백틱은 글자 그대로 남긴다.

**조립은 한 줄로 한다** — 태그 사이 개행·들여쓰기 금지. 사유 둘:

- (a) 컨테이너의 `white-space:pre-wrap` 이 태그 사이 공백을 보존해 문단 사이에 빈 줄이 샌다.
- (b) **줄 수가 이 변경 때문에 늘지 않는다.** 문단·목록 마크업이 개행 없이 태그로만 붙어
  들어가므로, 같은 입력이 만드는 항목의 줄 수는 변경 전과 **같다**. `log` 0-b 의 `limit=60`
  창과 0-c 의 `limit=120` 재Read 분기가 지금과 정확히 같은 빈도로 동작한다.
  → **불변식 10 으로 승격한다**(§3.5).

  > **초안 정정(메인 세션 검증).** 이 항은 원래 "줄 수가 상세 길이와 무관하게 10~11줄로
  > **고정**된다"고 적혀 있었다. 그것은 §3.2 3단계("블록이 하나뿐이고 목록이 아니면 감싸지
  > 않는다 — 텍스트만 넣는다")와 §3.3 기각표("단일 개행으로 줄을 나눈 기존 상세"를 보호
  > 대상으로 인정)와 동시에 성립할 수 없다. 블록 텍스트 안의 단일 개행은 보존되므로
  > 여러 줄 상세는 여전히 여러 줄 항목을 만든다. 이 변경이 주는 보장은 "고정"이 아니라
  > "**증가하지 않음**"이다.

**인라인 코드는 도입한다.** 사용자가 "ul 스타일 **등**" 이라 했고, 치환이 이스케이프
**이후**에 일어나므로 안전성이 유지된다(`` `Foo<T>` `` → `` `Foo&lt;T&gt;` `` →
`<code>Foo&lt;T&gt;</code>`). 비용은 CSS 1줄 + 변환 규칙 1줄이다.

**후방 호환 불변식**: 한 블록·목록 없음·백틱 없음인 상세는 결과가 **문자 단위로 종전과 같다**
(3단계 마지막 항). 이것이 이 변경의 안전 근거이고 테스트로 못 박는다.

### 3.3 기각안과 그 이유

| 기각안 | 이유 |
|--------|------|
| **허용 태그를 LLM 재량으로 조립** (`<p>`·`<ul>`·`<code>` 를 직접 쓰게 한다) | 이스케이프가 2모드가 된다 — "사용자 텍스트는 이스케이프, 내가 쓴 태그는 통과"를 LLM 이 매번 판단해야 하고, 그 판단이 틀리는 두 방향이 동시에 생긴다: `Foo<T>` 가 태그로 새고, 자기 `<p>` 가 `&lt;p&gt;` 로 샌다. `log` 절차가 "결정적"이라는 계약(`commands/dashboard.md:691` 제목)과 정면으로 어긋난다 |
| **`<br>` 로 문단 처리** | `pre-wrap` 이 이미 개행을 보존하므로 아무 것도 개선하지 않고 마크업만 늘어난다 |
| **`.detail` 을 여러 줄로 예쁘게 조립** | `log` 0-b 의 60줄 창을 소진해 `limit=120` 재Read 가 상시 경로가 된다. 그리고 `pre-wrap` 이 들여쓰기 공백을 화면에 뿌린다 |
| **`ul.log{list-style:none}` 을 `#dz-log>li` 로 좁힌다** | 망가지지 않은 것을 리팩토링하는 것이고(Karpathy #3), T22 계열이 이 규칙 문자열에 의존할 수 있다. 필요한 것은 중첩 목록에 **자기 선언을 주는 것**뿐이다 |
| **`white-space` 를 `normal` 로 바꾸고 문단만 쓴다** | T22-128 이 `pre-wrap` 을 고정한다. 그리고 단일 개행(빈 줄 아닌)으로 줄을 나눈 기존 상세가 전부 한 줄로 붙어 버린다 |

### 3.4 변경할 파일과 변경 내용

| 파일 | 변경 |
|------|------|
| `commands/dashboard.md` | ① `<style>` 에 4개 규칙 추가(§3.6) ② `log` 2단계에 변환 규약 + 워크드 예시 추가(§3.6) ③ 「로그 항목 스키마」에 `.detail` 한 줄 조립 명시 ④ 불변식 10 신설(§3.5) |
| `.claude/dashboard.html` (발행물) | **커밋 대상 아님**(gitignore). 처리 방침은 §3.7 |

**데이터 모델·인터페이스 변경 없음** — `.detail` 의 DOM 계약은 `hub_parse.py` 의 파싱 대상이
아니고(§3.1), `log` 의 인자 형태(`log <종류> "요약" ["상세"]`)도 그대로다. 바뀌는 것은
"상세 문자열 → `.detail` innerHTML" 변환 규칙 하나다.

### 3.5 불변식 10 (신설)

`commands/dashboard.md` 의 불변식 목록은 1~6, 8, 9 가 있고 **7은 결번**이다(`:246`).
다음 번호는 10이다.

```
### 불변식 10 (신설 — 기존 1~6, 8, 9에 이어)

10. **`.detail` 의 *태그 사이* 에는 개행·들여쓰기를 넣지 않는다.** `<div class="detail">`,
    `<p>`, `<ul>`, `<li>`, `</…>` 는 전부 붙여 쓴다. 이유는 하나다 — 컨테이너의
    `white-space:pre-wrap` 이 태그 사이 공백을 **보존**하므로, 개행을 넣으면 문단 사이에
    의도하지 않은 빈 줄이 샌다. 불변식 3(`.step-detail` 에 줄바꿈 금지)과 목적은 같고
    대상이 다르다.

    **블록 텍스트 *안* 의 단일 개행은 보존한다.** 빈 줄이 아닌 개행으로 줄을 나눈 상세는
    한 블록으로 남고(§3.2 3단계), 그 개행은 `pre-wrap` 이 그대로 보여준다 — 이것이
    `white-space` 를 `normal` 로 바꾸지 않은 이유이기도 하다(§3.3 기각표). 접어서 공백으로
    만들면 기존 다중 줄 상세가 조용히 재배치되고 §3.2 의 후방 호환 불변식이 거짓이 된다.

    따라서 **로그 항목의 줄 수는 고정되지 않는다.** 상세가 여러 줄이면 항목도 그만큼
    길어지고, `log` 0-c 의 `limit=120` 재Read 분기는 계속 실제 경로다(§8.4).
```

### 3.6 코드 스니펫

**CSS** — `.entry .detail` 규칙 **바로 뒤**에 4줄 추가. `.entry .detail{…}` 규칙 자체는
한 글자도 건드리지 않으므로 T22-128 이 그대로 통과한다(그 정규식은 `[^}]*` 로 규칙 하나
안만 훑는다).

```css
  .entry .detail{margin:6px 0 0 48px;font-size:12.5px;color:var(--muted);white-space:pre-wrap;overflow-wrap:anywhere}
  /* 경량 마크업(문단·목록·인라인 코드). 새 선언을 위 규칙 **안에** 넣어야 할 때는 반드시
     white-space 앞에 둔다 — tests/run.sh T22-128 이 그 규칙이 
     `white-space:pre-wrap;overflow-wrap:anywhere}` 로 끝날 것을 요구한다. */
  .entry .detail>*{margin:0}
  .entry .detail>*+*{margin-top:6px}
  /* 목록 글리프와 들여쓰기를 UA 기본에 맡기지 않고 못 박는다. 중첩 ul 은 UA 스타일시트의
     `ul ul` 선언값을 갖기 때문에 ul.log{list-style:none} 이 상속되지는 않지만, 그 기본값이
     브라우저마다 다르고(disc/circle) 우리가 원하는 글리프도 아니다. padding-left:16px 는
     허브 상세 패널(550px)의 실측 텍스트 폭 399px 에서 383px 를 남긴다 — 위 overflow-wrap
     규칙 주석의 실측 근거와 같은 상자다. */
  .entry .detail ul{list-style:disc;padding-left:16px}
  .entry .detail code{font-family:ui-monospace,monospace;font-size:11.5px;background:var(--soft);border-radius:4px;padding:1px 4px}
```

**`log` 2단계에 추가할 절차 문구** (기존 「이스케이프」 항 바로 뒤)

```
   - **상세 마크업 — 아래 네 단계를 이 순서로 적용한다.** 순서를 바꾸면 이스케이프가 두
     모드가 되어 `Foo<T>` 가 태그로 새거나 우리가 만든 `<p>` 가 `&lt;p&gt;` 로 샌다.
     1. 위 이스케이프를 **상세 전문에 먼저** 적용한다(단일 모드 유지).
     2. 빈 줄(공백만 있는 줄 포함)을 경계로 블록을 나눈다.
     3. 각 블록을 변환한다.
        - 모든 줄이 `- ` 로 시작하는 블록 → `<ul><li>…</li>…</ul>` 하나. 선행 `- ` 는 지운다.
        - 그 밖의 블록 → `<p>…</p>`.
        - **블록이 하나뿐이고 목록이 아니면 감싸지 않는다** — 텍스트만 넣는다(종전과 동일).
     4. 백틱으로 감싼 구간을 `<code>…</code>` 로 바꾼다. 왼쪽부터 짝지어 치환하고, 짝이
        없는 마지막 백틱은 글자 그대로 남긴다.
   - **태그 사이에 개행·들여쓰기를 넣지 않는다 — `.detail` 은 한 줄로 조립한다**(불변식 10).
```

**워크드 예시** (같은 자리에 이어 붙인다 — 규약이 "결정적"이라는 주장을 감사 가능하게 만든다)

입력 상세:

```
재현 조건 두 가지를 확인했다.

- 32px → 12px 전환에서만 발생
- `buildChipBadge` 는 통과
```

결과(한 줄):

```html
    <div class="detail"><p>재현 조건 두 가지를 확인했다.</p><ul><li>32px → 12px 전환에서만 발생</li><li><code>buildChipBadge</code> 는 통과</li></ul></div>
```

후방 호환 예시(한 블록·목록 없음):

```html
    <div class="detail">검수자 32px→12px 재현. buildChipBadge·runBottom 은 통과. margin 누적으로 전환 지시.</div>
```

→ `commands/dashboard.md:172` 의 현행 스키마 예시와 **문자 단위로 동일**하다.

### 3.7 발행물 `.claude/dashboard.html` 처리 — 결론

**정본(`commands/dashboard.md`)만 커밋한다. 발행물은 커밋하지 않는다**(`.gitignore:9`).

그런데 이 세션은 지금 그 파일을 쓰고 있다(소유 토큰 `76498cb6`, 로컬 서버 포트 8791).
폴링은 `<style>` 을 치환하지 않으므로(`commands/dashboard.md:264`), 이 세션이 다음 `log`
호출에서 새 마크업을 써 넣으면 **옛 CSS 로 렌더된다.** 실제로 무엇이 보이는가:

- `<p>` — UA 기본 마진(1em)으로 문단이 과하게 벌어진다. 읽을 수는 있다.
- `<ul>` — UA `ul ul` 선언값(circle)으로 불릿은 보인다. 들여쓰기는 UA 기본 40px.
- `<code>` — 배경·모노스페이스 없이 평문으로 보인다.
- **HTML 이 깨지지는 않는다** (템플릿에 마진 리셋이 없다는 사실을 확인 — §3.1).

**권고**: 정본 변경 후, **메인 세션이** 발행물의 `.entry .detail` 한 줄 뒤에 새 4줄을
붙여 넣는다. 근거 둘 — (1) 전역 지침이 대시보드 파일의 갱신 주체를 메인 세션으로 한정한다
("서브에이전트는 대시보드 파일에 접근하지 않는다"), 그래서 이 패치를 implementer 에게
주지 않는다 (2) 추적 대상이 아니므로 커밋 파급이 0이고, 다음 `init` 이 정본에서 재발행하니
발산이 남지 않는다.

### 3.8 이 절의 테스트 계획

이 변환은 **코드가 아니라 LLM 절차**다. 순수 함수가 없으므로 단위 테스트 대상이 없다 —
검증 표면은 (a) 명세 문구의 존재 (b) CSS 규칙의 존재 (c) 워크드 예시의 형태다. 이것을
정직하게 기록하고, 그 셋을 `tests/run.sh` 로 못 박는다.

**신규 `tests/run.sh` 검사** (T22 그룹, `test_dashboard_template_integrity` 안. T22-129 다음)

| ID | 검사 |
|----|------|
| T22-130 | CSS 규칙 존재. `.entry .detail ul{list-style:disc` / `.entry .detail>*{margin:0}` / `.entry .detail code{` / `ui-monospace`. **불릿 상속 사고 재발 방지의 본체**다 |
| T22-131 | 절차 문구 존재. "빈 줄" · "목록 항목" 또는 "선행 `- `" · "이스케이프를 **상세 전문에 먼저**" 계열 토큰 · "태그 사이에 개행" |
| T22-132 | 한 줄 조립 불변식. ① `commands/dashboard.md` 에 "불변식 10" 이 있다 ② 워크드 예시의 결과 HTML 이 **한 줄**이다 — `<div class="detail"><p>` 로 시작하고 같은 줄에서 `</div>` 로 끝나는 줄이 존재한다 ③ 「로그 항목 스키마」 코드블록 안 `class="detail"` 등장 줄 수가 1이다 |
| T22-128 | **변경 없이 계속 통과해야 한다**(회귀 감시). 새 선언을 규칙 안에 끼워 넣지 않았음을 이 검사가 그대로 증명한다 |

### 3.9 이 절의 독립 커밋 메시지 초안

```
feat: 대시보드 로그 상세에 문단·목록·인라인 코드 경량 마크업을 도입한다

.detail 은 CSS 한 줄(white-space:pre-wrap)뿐이라 여러 문단이 든 상세가 벽처럼 보였다.
허용 태그를 재량으로 조립하게 하는 안은 이스케이프가 두 모드가 되어 Foo<T> 가 태그로 새는
실패와 자기 <p> 가 &lt;p&gt; 로 새는 실패를 동시에 만들고, log 절차가 "결정적"이라는 계약과
어긋나므로 채택하지 않았다. 대신 규약 두 줄(빈 줄=문단, 줄 앞 "- "=목록)과 백틱 코드로
좁히고, 변환 순서를 이스케이프→블록 분할→감싸기→코드 치환으로 고정한다 — 이스케이프가
언제나 먼저이므로 단일 모드가 유지된다.

조립은 태그 사이 개행 없이 한 줄로 한다 — pre-wrap 이 그 공백을 문단 사이 빈 줄로 뿌리는
것을 막는다(불변식 10 신설). 블록 텍스트 안의 단일 개행은 보존하므로 로그 항목의 줄 수는
고정되지 않지만, 이 변경 때문에 늘지도 않는다. 한 블록·목록 없음·백틱 없음인 기존 상세는
결과가 종전과 문자 단위로 같다.
```

---

## 4. Q3 — 허브 카드 세션 목록에서 세션을 구분한다

### 4.1 현행 동작과 근거

| 사실 | 근거 |
|------|------|
| `renderSession()` 은 상태 배지 + 경과시간 + 에이전트 칩 + 발췌만 그리고 **식별자를 아예 싣지 않는다** | `hub_template.html:922-928` |
| `SessionView.short_id`(앞 8자)는 **이미 스냅샷 JSON 에 실려 있다** — `render_hub_html` 이 `asdict(snapshot)` 를 그대로 직렬화한다 | `hub_model.py:87`, `hub_session.py:337`, `SHORT_ID_LENGTH = 8`(`hub_session.py:17`) |
| 실측(7일치 이벤트 1474개·196세션) 접힌 루트별 동시 표시 세션 최대: daily-brief 9, coding-harness 7, atlas-ui-notebook-micro 6 | 실측 |
| **done 세션은 시간 경과로 숨겨지지 않는다** — 12시간 숨김은 `state==='stale'` 에만 걸리고, done 은 "발췌 없음 + 보이는 칩 0개" 일 때만 숨는다 | `hub_template.html:937-944`, `:720` |
| 최악 사례(daily-brief): 표시 9개 중 8개가 발췌 앞 40자 해시 동일(distinct 1), 칩 조합 distinct 1(전부 빈 칩), 배지 done 8 + idle 1 → 유일한 구분자가 경과시간 | 실측 |
| atlas 카드: 표시 6개의 경과분 distinct 4 — **경과시간마저 두 쌍이 겹친다** | 실측 |
| **워크트리 접힘 가설 기각**: 다중 세션 루트 5곳 모두 distinct cwd == 1 | 실측 |
| `started_at_ms` 는 `SessionFacts` 에만 있고 `SessionView` 에는 없다 | `hub_session.py:65` vs `:87-97` |
| `task_excerpt` 는 "마지막으로 입력한 프롬프트"로 매번 덮어써진다 — 안정적 정체성이 아니다 | `hub_session.py:191-199` |
| T25-11 이 `+ session.short_id +` 리터럴을 금지한다 — 되살릴 때 반드시 `escapeHtml()` 경유 | `tests/run.sh:2376-2386` |
| 배지 관례는 색 + 형태(글리프) + 텍스트 3채널, 보조기술용 텍스트는 `.sr-only` | `hub_template.html:843-848`, `:862-864`, `:219-220` |
| `data-tooltip` 은 **정보 손실이 있을 때만** 붙인다(결정 R4) | `hub_template.html:909-919`, `:994-996` |
| `snapshot_content_key` 는 `collected_at_ms` 만 제외한 전체 내용 해시 → **정적 불변 필드 추가는 안전, "지금" 파생값은 금지** | `hub_model.py:77-81` |
| 카드 높이 340px 고정 + `.sessions` 내부 스크롤 + `.session-line` flex-wrap → 요소를 더해도 카드 높이·그리드는 불변, "한 화면에 보이는 세션 수"만 줄어든다 | `hub_template.html:129`, `:210`, `:212` |
| 세션 정렬: 서버가 오래된 것부터 주고 클라이언트가 최신순 재정렬 | `hub_template.html:1002-1005`, `hub_project.py:275-277` |
| `commands/hub.md` 에 세션 뷰 스키마 서술이 없다 → `SessionView` 필드를 늘려도 갱신 대상 아님 | grep 0건 |
| `SessionView(` 생성 지점은 전부 4곳 | `hub_session.py:335`, `test_hub_model.py:25`·`:150`, `test_hub_session.py:421` |
| `pad2` 는 사용량 초기화 줄 안의 **지역 함수**다 | `hub_template.html:1099` |
| 같은 자리에 "오늘이면 HH:MM, 아니면 M/D HH:MM" 규칙이 이미 있다 | `hub_template.html:1096-1101` |
| 옛 `.short-id` 클래스·CSS 는 완전히 제거된 상태다(grep 0건) | 실측 |
| 배경 정본: 세션 줄 재구성 경위·short_id 렌더가 사라진 이력·340px 고정 | `docs/prps/hub-session-activity-and-tooltip.md:55-66` |
| 접힘 규칙 정본 | `docs/prps/hub-worktree-fold.md` |

### 4.2 채택안 — 시작 시각 + `short_id` 를 둘째 줄에 함께 싣는다

**왜 둘을 함께 싣는가.** 실측이 근거다.
- **시작 시각**은 daily-brief 9개를 전부 갈라낸다(9개 모두 다름). 발췌·칩·배지가 전부
  같은 카드에서 유일하게 작동하는 구분자다.
- **`short_id`** 는 서버 변경 0이고(이미 스냅샷에 있다) 영구 안정 식별자이며,
  트랜스크립트(`~/.claude/projects/<enc>/<session_id>.jsonl`)·훅 이벤트의 `s` 필드와
  교차 참조된다.
- 하나만으로는 부족하다: 시작 시각은 같은 분 기동에서 겹칠 수 있고, `short_id` 는
  "서로 다르다"만 알려주고 "어떤 세션인지"를 답하지 않는다.

**절대 시각을 렌더하고 `Date.now()` 파생값을 스냅샷에 넣지 않는다.** `SessionView` 에는
정적 `started_at_ms`(정수)만 추가하고, `HH:MM` 포맷은 클라이언트가 만든다. 그래야
`snapshot_content_key` 가 안정적이다(§4.1 표).

**7일 보존을 고려해 날짜를 함께 준다.** 이벤트 보존이 7일이고 done 세션이 누적되므로
(§4.6), "어제 14:32" 와 "오늘 14:32" 가 한 화면에 공존한다. `HH:MM` 만으로는 그 둘을
구분하지 못한다. 사용량 초기화 줄이 이미 같은 문제를 풀어 놨으므로(`hub_template.html:1096-1101`)
그 규칙을 공용 함수로 올려 재사용한다: **오늘이면 `HH:MM`, 다른 날이면 `M/D HH:MM`.**

**배치 — 첫 줄을 건드리지 않는다.** 세션 줄 요소가 늘면 좁은 카드에서 `flex-wrap` 이
잦아진다. 그래서 새 요소를 `.session-line` 안에 넣지 않고 **형제 블록**으로 둔다.
`.session-line` 의 자식 구성이 종전과 완전히 같으므로 첫 줄의 wrap 거동이 **정의상**
불변이다.

```
[첫 줄  .session-line]  ● 작업중   3분 전   implementer  code-reviewer     ← 종전과 동일
[둘째 줄 .session-meta]  시작 14:32   a1b2c3d4
[셋째 줄 .excerpt     ]  허브 카드의 세션 목록에서 세션을 구분할 방법…      ← 종전과 동일
```

**툴팁**: `.session-id` 에 전체 `session_id` 를 `data-tooltip` 으로 붙인다. 결정 R4 는
"정보 손실이 있을 때만"이고 `short_id` 는 문자 그대로 `session_id` 의 절단이므로 조건을
충족한다. 실익도 있다 — 트랜스크립트 파일명 교차 참조.

**보조기술**: `short_id` 는 라벨 없는 hex 문자열이라 스크린리더에서 무의미한 글자열로
읽힌다. `.sr-only` 로 "세션 ID " 접두를 준다 — `renderAgentChip` 의 `runningSrText`
(`hub_template.html:864`)가 세운 관례와 같은 형태다.

### 4.3 기각안과 그 이유

| 기각안 | 이유 |
|--------|------|
| **서수(#1·#2…)** (조사 에이전트 권고) | ① 이벤트 보존 창(7일)에서 옛 세션이 빠지면 번호가 밀려 **같은 세션이 다른 번호로 보인다** ② 렌더는 최신순인데 번호는 시작순이라 화면이 #9→#1 로 내려간다 ③ 시작 시각이 같은 정보를 밀리지 않게 준다. **반대 근거 없음 — 이 기각에 동의한다** |
| **`short_id` 만 싣는다** | "서로 다르다"만 답하고 "어떤 세션인지"를 답하지 않는다. 실측 최악 카드에서 사용자는 여전히 9개 중 무엇이 방금 그 작업인지 모른다 |
| **시작 시각만 싣는다** | 같은 분 기동에서 겹친다. 그리고 트랜스크립트·훅 이벤트와 교차 참조할 고리가 없어진다 |
| **`cwd` 나 워크트리 경로를 싣는다** | 실측으로 기각됐다 — 다중 세션 루트 5곳 모두 distinct cwd == 1. 화면만 넓히고 구분에 기여하지 않는다 |
| **`.session-line` 안에 넣는다** | 좁은 카드에서 첫 줄 wrap 거동이 바뀐다. 요구 3-3(첫 줄 불변)을 지킬 수 없다 |
| **`.session-meta` 를 `.session-line` 자식 + `flex-basis:100%` 로 둔다** | 형제 블록보다 우회적이고, `.excerpt` 의 `flex-basis:100%`(§4.7 관찰)가 이미 그 기법이 오해를 낳은 전례다 |
| **`task_excerpt` 를 세션 정체성으로 쓴다** | 매 프롬프트마다 덮어써진다(`hub_session.py:191-199`) — 정체성이 아니다 |
| **done 세션 누적을 함께 고친다** | **사용자 요청 범위 밖.** §4.6 「후속 제안」으로 넘긴다 |

### 4.4 변경할 파일과 변경 내용

| 파일 | 변경 |
|------|------|
| `hub/bin/hub_session.py` | `SessionView` 에 `started_at_ms: int` 추가(**기본값 없음** — 결정 WT19 관례) / `compute_session_view` 가 `facts.started_at_ms` 를 옮김 |
| `hub/bin/hub_template.html` | `SESSION_START_LABEL` 상수 / `pad2` 를 IIFE 스코프로 올리고 `absoluteTimeLabel(atMs, nowMs)` 신설(사용량 초기화 줄이 이 함수를 재사용) / `renderSessionMeta()` 신설 / `renderSession()` 에 한 줄 추가 / CSS `.session-meta`·`.session-id` 2줄 / 머리 주석에 결정 기록 |
| `tests/hub/test_hub_model.py` | `:25`·`:150` 생성 kwargs + 신규 케이스 |
| `tests/hub/test_hub_session.py` | `:421` 생성 kwargs + 신규 케이스 |
| `tests/run.sh` | T25-125~T25-127 (§4.5) + T25-11 주석 갱신 |

**갱신하지 않는 것**: `commands/hub.md`(세션 뷰 스키마 서술이 없다 — §4.1 확인),
`hub/README.md`(세션 줄 구성을 서술하지 않는다), `docs/prps/*`(인용만).

**데이터 모델 변경**

```python
# hub_session.py
@dataclass(frozen=True)
class SessionView:
    """세션 사실로부터 판정한 화면 표시 상태."""

    session_id: str
    short_id: str
+   # 세션 시작 시각(정적). 화면은 절대 시각(HH:MM 또는 M/D HH:MM)으로 그린다 — 실측에서
+   # 발췌·칩·배지가 전부 같은 카드(daily-brief 표시 9개)를 유일하게 갈라낸 값이다.
+   # **기본값을 두지 않는다**(결정 WT19 와 같은 이유 — 정체성 필드가 조용히 0 으로 채워지면
+   # 화면에 1970년이 뜨고 그 원인을 추적할 수 없다).
+   # 파생값(경과 시간 등)을 여기 넣지 않는다: snapshot_content_key 가 collected_at_ms 만
+   # 제외하므로, "지금" 파생값은 매 수집마다 키를 바꿔 hub.html 쓰기 억제를 무력화한다.
+   started_at_ms: int
    state: SessionState
    base_state: Literal["working", "idle", "done"]
    last_event_at_ms: int
    task_excerpt: str | None
    agent_runs: tuple[SubagentRunView, ...]
```

**인터페이스 (JS)**

```js
function absoluteTimeLabel(atMs, nowMs): string   // "14:32" | "8/20 14:32"
function renderSessionMeta(session): string       // 한 줄 HTML
```

### 4.5 코드 스니펫

**CSS** — `.session-time`(`hub_template.html:213`) 바로 뒤에 삽입.

```css
  .session-time{font-size:11px;color:var(--muted)}
  /* 세션 식별 줄(요구 3). .session-line 의 **형제 블록**이라 첫 줄의 flex-wrap 거동을
     건드리지 않는다 — 좁은 카드에서 배지·경과시간·칩이 접히는 방식이 종전과 정의상 같다.
     340px 고정 카드에서 세션 1건이 약 20px 높아지므로 카드 높이·그리드는 불변이고
     "한 화면에 보이는 세션 수"만 줄어든다
     (docs/prps/hub-session-activity-and-tooltip.md 전제 2). */
  .session-meta{display:flex;align-items:baseline;gap:6px;margin-top:3px;font-size:11px;color:var(--muted)}
  /* 식별자는 글자 모양이 헷갈리면 소용이 없다(0/O, 1/l) — .agent-chip 과 같은 모노스페이스
     스택을 쓴다. 새 색 토큰은 만들지 않는다(.session-meta 의 --muted 를 물려받는다). */
  .session-id{font-family:ui-monospace,monospace;letter-spacing:-.2px}
```

**JS**

```js
  var SESSION_START_LABEL = '시작';

  // 두 자리 0 패딩. 사용량 초기화 줄의 지역 함수였던 것을 이 스코프로 올렸다 — 세션 식별
  // 줄이 같은 포맷을 쓰므로 사본을 두지 않는다.
  function pad2(n){ return (n < 10 ? '0' : '') + n; }

  // 절대 시각 라벨. 오늘이면 HH:MM, 다른 날이면 M/D HH:MM.
  // 날짜를 함께 주는 이유: 이벤트 보존이 7일이고 done 세션은 시간 경과로 숨겨지지 않으므로
  // (shouldRenderSession 참조), "어제 14:32" 와 "오늘 14:32" 가 한 카드에 공존한다.
  // 사용량 초기화 줄이 먼저 이 규칙을 갖고 있었고, 그 함수가 이제 이것을 재사용한다.
  function absoluteTimeLabel(atMs, nowMs){
    var target = new Date(atMs);
    var now = new Date(nowMs);
    var timePart = pad2(target.getHours()) + ':' + pad2(target.getMinutes());
    var sameDay = target.getFullYear() === now.getFullYear()
      && target.getMonth() === now.getMonth()
      && target.getDate() === now.getDate();
    return sameDay ? timePart : (target.getMonth() + 1) + '/' + target.getDate() + ' ' + timePart;
  }

  // 세션 식별 줄(요구 3). 시작 시각과 short_id 를 함께 싣는다 — 하나만으로는 부족하다:
  // 시작 시각은 같은 분 기동에서 겹칠 수 있고, short_id 는 "서로 다르다"만 알려주고
  // "어떤 세션인지"를 답하지 않는다. 서수(#1·#2…)는 쓰지 않는다: 보존 창에서 옛 세션이
  // 빠지면 번호가 밀려 같은 세션이 다른 번호로 보이고, 최신순 렌더와 시작순 번호가 역행한다.
  // data-tooltip 은 결정 R4 를 충족한다 — short_id 는 session_id 의 절단이라 정보 손실이
  // 실재하고, 전체 id 는 트랜스크립트(~/.claude/projects/<enc>/<id>.jsonl) 교차 참조에 쓰인다.
  function renderSessionMeta(session){
    return '<div class="session-meta"><span class="session-start">'
      + SESSION_START_LABEL + ' ' + absoluteTimeLabel(session.started_at_ms, Date.now())
      + '</span><span class="session-id" data-tooltip="' + escapeHtml(session.session_id) + '">'
      + '<span class="sr-only">세션 ID </span>' + escapeHtml(session.short_id) + '</span></div>';
  }

  function renderSession(session){
    return '<li><div class="session-line">'
      + renderStateBadge(session.state, session.base_state)
      + '<span class="session-time">' + elapsedLabel(session.last_event_at_ms) + '</span>'
      + renderAgentRuns(session.agent_runs)
      + '</div>' + renderSessionMeta(session)
      + renderSessionExcerpt(displayableExcerpt(session.task_excerpt)) + '</li>';
  }
```

**렌더 결과 HTML**

```html
<li>
  <div class="session-line"><span class="badge state-working"><span class="glyph" aria-hidden="true">●</span>작업중</span><span class="session-time">3분 전</span><span class="agent-runs">…</span></div>
  <div class="session-meta"><span class="session-start">시작 14:32</span><span class="session-id" data-tooltip="a1b2c3d4-5e6f-7890-abcd-ef1234567890"><span class="sr-only">세션 ID </span>a1b2c3d4</span></div>
  <span class="excerpt">…</span>
</li>
```

`absoluteTimeLabel` 의 반환값은 `escapeHtml` 을 거치지 않는다 — 숫자에서 자기가 만든
문자열이고, 같은 자리의 `elapsedLabel(...)`(`hub_template.html:925`)도 그렇다. 스냅샷에서
온 값(`session_id`·`short_id`)만 escape 한다.

**Python**

```python
    return SessionView(
        session_id=facts.session_id,
        short_id=facts.session_id[:SHORT_ID_LENGTH],
        started_at_ms=facts.started_at_ms,
        state="stale" if is_stale else base_state,
        ...
    )
```

### 4.6 이 절의 테스트 계획

**깨지는 기존 테스트와 대응**

| 위치 | 왜 깨지는가 | 어떻게 고치는가 |
|------|------------|----------------|
| `test_hub_model.py:25-28` | `SessionView` frozen dataclass 에 기본값 없는 필드가 추가돼 `TypeError` | `started_at_ms=BASE_TIME_MS` 추가 |
| `test_hub_model.py:150-153` | 같음 | 같음 |
| `test_hub_session.py:421-424` | 같음 | 같음 |
| `test_hub_model.py:167-178` `SnapshotContentKeyTest` | **깨지지 않는다** — `started_at_ms` 는 정적이라 `collected_at_ms` 만 다른 두 스냅샷의 키는 여전히 같다. 생성 kwargs 만 추가 | 위와 같음 |
| `tests/run.sh` T25-11 | **깨지지 않는다.** 부정 검사(`+ session.short_id +` 금지)는 `escapeHtml(session.short_id)` 를 쓰면 통과하고, 긍정 검사(`escapeHtml(run.agent_type)`)도 그대로다 | 주석만 갱신 — "short_id 렌더가 폐기됐다"는 서술이 사실과 달라졌다 |
| `tests/run.sh` T25-41 | **깨지지 않는다** — 토큰 존재만 본다(`usage-reset`·`rate_limit_resets`·`초기화 `·`renderUsageResetRow`). `pad2` 를 올리고 `absoluteTimeLabel` 을 쓰게 바꿔도 네 토큰은 그대로다 | 없음 |

**신규 단위 테스트**

| 파일 | 케이스 |
|------|--------|
| `test_hub_session.py` | `compute_session_view` 가 `facts.started_at_ms` 를 뷰로 그대로 옮긴다 / `started_at_ms != last_event_at_ms` 인 사실로 둘이 섞이지 않음을 확인 |
| `test_hub_model.py` | ① `started_at_ms` 만 다른 두 스냅샷의 `snapshot_content_key` 가 **다르다**(필드가 실제로 페이로드에 실렸다는 증명) ② 같은 스냅샷을 두 번 직렬화하면 키가 **같다**("지금" 파생값이 섞이지 않았다는 증명) ③ 렌더된 `#dzh-data` JSON 의 세션 객체에 `started_at_ms` 가 있다 |

**신규 `tests/run.sh` 검사** (T25 그룹. ID 는 §5 에서 미리 배분한 T25-125~127)

| ID | 검사 |
|----|------|
| T25-125 | 세션 식별 렌더 존재. `escapeHtml(session.short_id)` (긍정) / `escapeHtml(session.session_id)` / `renderSessionMeta` / `absoluteTimeLabel` / `session.started_at_ms`. `+ session.short_id +` 부정 검사는 T25-11 이 계속 담당한다 |
| T25-126 | `hub_session.py` 의 `SessionView` 에 `started_at_ms: int` 선언이 있고 **기본값이 붙어 있지 않다**(T25-115 의 `observed_cwds` 검사와 같은 형태) |
| T25-127 | 첫 줄 불변 계약. `.session-meta{` · `.session-id{` CSS 규칙이 있고, `renderSession()` 범위를 앵커로 추출해 그 안의 `class="session-line"` 문자열 뒤 `</div>` 앞 구간에 `session-id`·`session-meta` 가 **없음**을 확인한다(식별 줄이 첫 줄로 새어 들어가 wrap 거동을 바꾸는 회귀 방지) |

### 4.7 이 절의 관찰 — 고치지 않고 기록만 한다

`hub_template.html:221` 의 `.excerpt{…;flex-basis:100%}` 는 현재 DOM 에서 **효력이 없다.**
`renderSession` 이 `.excerpt` 를 `.session-line` 밖(`</div>` 뒤)에 놓으므로 부모는
`<li>` 이고, `.sessions li`(`:211`)는 flex 컨테이너가 아니다. 세션 줄이 재구성되던 시기의
잔재로 보인다(`docs/prps/hub-session-activity-and-tooltip.md:59-62` 가 그 재구성을 기록한다).

**이번 변경으로 생긴 것이 아니므로 삭제하지 않는다**(Karpathy #3 — 무관한 죽은 코드는
언급만 한다). 다만 `.session-meta` 를 같은 기법(`flex-basis:100%`)으로 만들지 **않은** 이유가
여기에 있음을 §4.3 에 남겼다.

### 4.8 이 절의 독립 커밋 메시지 초안

```
feat: 허브 세션 줄에 시작 시각과 short_id 를 실어 세션을 구분 가능하게 한다

세션 줄은 상태 배지·경과시간·칩·발췌만 그리고 식별자를 아예 싣지 않았다. 실측(7일치
이벤트 1474개·196세션)에서 daily-brief 카드는 표시 세션 9개 중 8개가 발췌 해시까지 같고
칩도 전부 비어 있어, 유일한 구분자가 경과시간뿐이었다 — atlas 카드는 그 경과분마저 두 쌍이
겹쳤다.

SessionView 에 정적 started_at_ms 를 추가하고(파생값은 넣지 않는다 — snapshot_content_key
가 collected_at_ms 만 제외하므로 "지금" 파생값은 hub.html 쓰기 억제를 무력화한다), 화면은
절대 시각과 short_id 를 둘째 줄에 함께 그린다. 하나만으로는 부족하다: 시작 시각은 같은 분
기동에서 겹치고, short_id 는 "서로 다르다"만 알려준다. 서수(#1·#2…)는 쓰지 않는다 — 보존
창에서 옛 세션이 빠지면 번호가 밀려 같은 세션이 다른 번호로 보인다.

식별 줄은 .session-line 의 형제 블록이라 첫 줄의 flex-wrap 거동이 종전과 정의상 같다.
날짜는 다른 날일 때만 붙이며(오늘 HH:MM / 다른 날 M/D HH:MM), 그 규칙을 이미 갖고 있던
사용량 초기화 줄과 pad2·absoluteTimeLabel 을 공유한다.
```

---

## 5. 구현 순서

**주제 간 코드 의존은 없다.** 세 절이 건드리는 소스 파일 집합이 서로소다.

| | Q1 | Q2 | Q3 |
|---|----|----|----|
| `hub/bin/*.py` (서버·데몬·collect·model·hook) | ● | | |
| `hub/bin/hub_session.py`, `hub_template.html` | | | ● |
| `commands/dashboard.md` | `:915` 1줄 | ● | |
| `hub/README.md`, `commands/hub.md` | ● | | |
| `tests/hub/*.py` | server/state/daemon/hub/collect | | model/session |
| `tests/run.sh` | T25-121~124 | T22-130~132 | T25-125~127 |

주의 2건:

1. **`tests/run.sh` 의 T25 검사 ID 를 미리 배분한다** — Q1 은 **T25-121~124**, Q3 은
   **T25-125~127**. 두 절이 같은 함수(`test_hub_docs_and_constants`)에 검사를 더하므로,
   ID 를 선점해 두면 **어느 순서로 커밋해도 충돌하지 않는다.** Q2 는 다른 그룹
   (`test_dashboard_template_integrity`, T22-130~132)이라 애초에 독립이다.
2. **`commands/dashboard.md:915`("최대 1 수집 주기(기본 5초)")는 Q1 의 몫이다.** Q2 도 같은
   파일을 고치지만 `<style>`·`log` 절이라 줄 범위가 겹치지 않는다. 두 커밋이 같은 파일을
   건드리는 유일한 지점이므로, 뒤에 오는 쪽이 리베이스 충돌을 만나면 이 한 줄만 확인한다.

**권장 순서: Q1 → Q3 → Q2.** 이유는 의존이 아니라 검수 밀도다 — Q1 이 유일하게 동시성
(락·스레드)을 도입하므로 가장 먼저·가장 신선한 상태에서 검수받는 것이 좋다. 순서를 바꿔도
무관하다.

각 절이 끝날 때마다 **`bash tests/run.sh` 전체 + `python3 -m unittest discover -s tests/hub -t .`**
를 통과시키고 커밋한다.

---

## 6. 문서 갱신 목록

### 6.1 Q1

| 파일:줄 | 현행 | 새 문구 방향 |
|---------|------|-------------|
| `hub/README.md:14-15` | "서버의 5초 수집 루프는 별개로 계속 돈다" | 서버는 요청이 올 때 수집한다는 서술로. "탭이 숨으면 폴링이 멈추고, 폴링이 없으면 수집도 없다" 가 이제 참이 됐다는 것이 요점 |
| `hub/README.md:99` | "5초마다 모든 프로젝트를 다시 수집한다" | "요청이 올 때 수집한다(신선도 창 2초). 요청이 전혀 없어도 5분마다 한 번은 수집해 `file://` 사본과 건강도 관측을 유지한다" |
| `hub/README.md:110-112` | "서버의 수집 주기(5초)와 브라우저의 폴링 주기(60초)는 별개다 … 5초 주기가 디스크를 계속 두드리지는 않는다" | **단락 재작성.** 이제 둘은 별개가 아니라 **폴링이 수집을 이끈다.** 새로고침 버튼이 곧 강제 수집이라는 점(창 2초)과, 쓰기 억제는 그대로라는 점을 남긴다 |
| `hub/README.md:121` | "하트비트 TTL(수집 주기의 3배, 최소 15초)" | "하트비트 TTL(하트비트 주기의 3배, 최소 15초)" — 값은 15초 그대로 |
| `hub/README.md:402` | \| `server_collect_interval_seconds` \| `5` \| 수집 루프 주기 \| | \| `server_heartbeat_interval_seconds` \| `5` \| 유지보수 티커가 하트비트를 찍는 주기. TTL 의 입력(TTL = 이 값 × 3, 하한 15초). **수집 주기가 아니다** \| |
| `commands/hub.md:63` | "상주 서버가 5초마다 갱신 중입니다." | "상주 서버가 화면을 열 때마다 갱신합니다." |
| `commands/hub.md:121-124` | `collect_stalled=true` 면 "프로세스는 살아 있지만 수집이 멈췄습니다" | `maintenance_stalled` 로 필드명 교체 + `collect_health` 3값별 보고 문구(`failing` → 실패 사유·`log_tail` 동반 / `never_collected` → "아직 한 번도 수집하지 않았습니다(정상일 수 있습니다)") + `last_collect_success_age_ms` 를 참고 필드에 추가 |
| `commands/hub.md:219-220` | `server_collect_stalled`(서버 요약) | `server_maintenance_stalled`·`server_collect_health`·`last_collect_success_age_ms` |
| `commands/dashboard.md:915` | "최대 1 수집 주기(기본 5초) 걸린다" | "허브 페이지를 열거나 새로고침하면 그 자리에서 반영된다(허브가 요청 시 수집한다). **강제 수집을 부르지 않는다**" — 사용자에게 노출되는 유일한 수치 약속이므로 수치를 없애고 조건으로 바꾼다 |

### 6.2 Q2

`commands/dashboard.md` 만 고친다: `<style>` 4줄 추가(`:1331` 뒤), `log` 2단계 절차 문구 +
워크드 예시(`:731` 뒤), 「로그 항목 스키마」 주석 1줄, 불변식 10 신설(`:252` 뒤).

### 6.3 Q3

문서 갱신 없음. 근거: `commands/hub.md` 에 세션 뷰 스키마 서술이 없고(grep 0건),
`hub/README.md` 는 세션 줄 구성을 서술하지 않는다.

### 6.4 오폭 금지 — `README.md:170`

> `README.md:170` 의 **"5초 간격 폴링"** 은 `/dashboard` 의 Document Picture-in-Picture
> 플로팅 창 폴링이며 **허브 수집 주기가 아니다. 건드리지 마라.**

이것을 사람의 주의력에 맡기지 않는다 — **T25-124 에 그 문장이 여전히 존재한다는 긍정
검사를 넣는다.** 일괄 치환이 이 줄을 지우면 테스트가 그 자리에서 실패한다.

같은 이유로 `README.md:130,139` 의 커맨드 표(`dashboard` 1684줄)는 Q2 가 `dashboard.md`
줄 수를 바꾸므로 함께 갱신한다(테스트 강제는 없지만 `e75dbc2` 가 세운 관례다).
Q1 은 `commands/hub.md`(280줄)의 줄 수를 바꿀 수 있으므로 같은 확인이 필요하다.

---

## 7. 리스크와 완화

### 7.1 Q1

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| **락 보유 중 수집(8~11ms)이 다른 요청을 지연시킨다** | 낮음 | 창 안 요청은 락을 잡지 않는다(`_is_within` 이 락 밖). 락을 잡는 것은 창을 넘긴 첫 요청 하나뿐이고, 뒤따르는 요청은 이중 검사에서 즉시 반환한다. 8~11ms 는 로컬 HTTP 응답 예산 안이다 |
| **수집이 느려진 환경(roots 가 큼)에서 요청이 그만큼 블로킹** | 중간 | 현행에서도 같은 비용을 배경 스레드가 내고 있었고, 그때는 사용자가 "왜 느린지"를 볼 수 없었다. 요청 경로로 오면 오히려 관측 가능해진다. 그리고 창(2초)이 버스트를 합치므로 페이지 로드당 1회다. 임계값을 넘는 환경이 보고되면 `scan_depth`·`roots` 축소가 기존 처방 그대로 유효하다 |
| **사용량 API(최악 15초)가 실수로 요청 경로에 올라간다** | 높음 | 코드 리뷰만으로 막지 않는다 — **T25-122** 가 `_run_usage_api_poll_cycle`·`hub_usage_fetch` 가 요청 경로 함수 본문에 없음을 기계적으로 검사한다 |
| **하트비트 TTL(15초) 경계와 사용량 API 블로킹(최악 15초)이 겹쳐 `maintenance_stalled` 오탐** | 중간 | **선재 결함이다** — 현행 `_collect_loop` 도 같은 자리에서 같은 15초를 블로킹한다. 이번 범위에서 고치지 않고 §8 후속 제안으로 넘긴다. 현행 완화(사이클 앞뒤 두 번 touch)는 그대로 유지한다 |
| **`_CONFIG_FIELD_TYPES` 를 안 채우고 필드를 추가** | 높음 | `_validate_config_overrides` 가 `_CONFIG_FIELD_TYPES[key]` 를 직접 인덱싱하므로 **KeyError 로 config 읽기 자체가 터진다**(`hub_collect.py:105`). §2.8 표에 "필수"로 못 박았고, `test_hub_collect.py` 신규 케이스 ②가 새 필드를 실제로 통과시킨다 |
| **`hub_server_state.py` 새 주석에 `os.`·`Path(`·`open(` 문자열을 쓴다** | 중간 | T25-10 이 그 자리에서 실패한다. §2.6 에 경고를 박아 뒀다 |
| **`/hub status` 의 HTTP 프로브(`_check_http_ok` → `/hub.html`)가 수집을 유발한다** | 낮음 | 감수하고 문서화한다. 상태 조회가 수집을 일으키는 것은 순수하지 않지만 8~11ms 이고, 사용자가 상태를 읽는 바로 그 순간에 스냅샷을 갱신하는 것이 실용적으로 옳다. 대안(게이트 없는 `/healthz` 신설)은 결정 N3 의 좁은 화이트리스트에 미용 목적으로 표면을 더하는 것이라 기각 |
| **`file://` 북마크 사용자의 신선도** | 중간 | (b) 채택으로 상한 5분. 그리고 `hub/README.md` 에 "`/hub` 로 열면 항상 최신"을 명시 |
| **되돌리기가 필요해지는 상황** | — | §7.2 |

### 7.2 Q1 되돌리기 경로

Q1 은 3개 절 중 유일하게 런타임 동작을 바꾼다. 되돌리기는 **3단으로 준비한다** —
전부 원복하지 않고도 멈출 수 있게.

**1단 (즉시, 재배포 없음)**: `~/.claude/hub/config.json` 에
`"server_heartbeat_interval_seconds": 1` 을 넣고 `/hub server restart`.
티커가 1초마다 돌고 TTL 은 하한 15초로 유지된다 → 하트비트·사용량 게이트가 가장 촘촘해진다.
**단, 이것은 수집 주기를 되돌리지 않는다**(배경 상한 5분은 상수다). 즉 1단으로 고칠 수
있는 것은 "하트비트·사용량 API 가 느리다"류 증상뿐이다. 그 한계를 문서에 적는다.

**2단 (한 줄 수정 + restart)**: `hub_server.py` 의
`BACKGROUND_COLLECT_MAX_AGE_MS = 5 * 60 * 1000` 을 `5 * 1000` 으로 바꾼다.
그 순간 **티커가 5초마다 수집을 보장하므로 현행과 실질적으로 같은 동작이 된다**(요청 구동
경로는 그대로 남지만 창 2초 안에서 대부분 no-op 이 된다). 코드 한 줄로 옛 거동을 복원할 수
있다는 것이 이 설계의 안전판이고, 그 사실을 상수 주석에 남긴다.

**3단 (커밋 되돌리기)**: `git revert <커밋1>`. 세 커밋이 독립이므로 Q2·Q3 를 잃지 않는다.
단 되돌리면 `config.json` 에 남은 `server_heartbeat_interval_seconds` 가 "알 수 없는 필드"
경고를 내므로, revert 후 그 키를 지우라는 안내를 커밋 메시지 본문에 미리 적어 둔다.

### 7.3 Q2

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| **T22-128 을 깨뜨린다**(새 선언을 `white-space` 뒤에 넣음) | 중간 | 새 선언을 규칙 **안에 넣지 않고 별도 규칙 4개로** 둔다. CSS 주석에 그 이유를 남긴다. T22-128 이 그대로 감시한다 |
| **중첩 목록의 불릿이 사라진다** | 중간 | `.entry .detail ul{list-style:disc}` 를 명시하고 **T22-130** 으로 못 박는다. (브리핑의 "`ul.log{list-style:none}` 가 상속되므로 사라진다"는 진단은 정확하지 않다 — §9 미확인 3 참조. 그러나 처방은 같고, 처방을 그대로 채택한다) |
| **문단 사이에 빈 줄이 샌다**(`pre-wrap` + 태그 사이 개행) | 높음 | 한 줄 조립 규칙 + 불변식 10 + **T22-132** 의 한 줄 검사 |
| **`log` 0-b 의 60줄 창이 소진된다** | 낮음 | 문단·목록 마크업이 개행 없이 태그로만 붙으므로 같은 입력의 항목 줄 수가 **늘지 않는다**(§3.2 (b)). 줄 수가 고정되는 것은 아니다 — 블록 텍스트 안의 단일 개행은 보존되므로 여러 줄 상세는 지금과 똑같이 여러 줄 항목을 만들고, `limit=120` 재Read 분기가 지금과 같은 빈도로 그것을 받는다(§8.4) |
| **열려 있는 창이 새 CSS 를 못 받는다** | 낮음 | 폴링이 `<style>` 을 치환하지 않는 것은 의도된 계약이다(`:264`). 다음 새로고침에 반영된다. §3.7 이 이 세션의 발행물 처리를 정한다 |
| **기존 상세에 백틱이 들어 있으면 렌더가 바뀐다** | 낮음 | 의도된 개선이다. 다만 "결과가 종전과 같다"는 후방 호환 주장은 **백틱 없음**을 조건으로 함을 §3.2 에 명시했다 |
| **변환이 코드가 아니라 LLM 절차라 단위 테스트가 없다** | 중간 | 정직하게 인정하고(§3.8), 워크드 예시 + T22-130~132 로 명세를 감사 가능하게 만든다. 이것이 이 저장소가 `step`·`impl` 절차에 이미 쓰는 검증 형태다 |

### 7.4 Q3

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| **한 화면에 보이는 세션 수가 줄어든다** | 중간 | 340px 고정 + 내부 스크롤이라 카드 높이·그리드는 불변(`hub_template.html:129`, `:210`). 세션 1건당 약 20px 증가 추정 → 보이는 세션 약 4개 → 약 3개. **실측이 아니라 추정이다**(§9 미확인 2). 스크롤은 살아 있으므로 정보 손실은 없다 |
| **첫 줄 wrap 거동 변화** | 낮음 | 형제 블록이라 정의상 불변. **T25-127** 이 식별 줄이 첫 줄로 새어 들어가는 회귀를 감시 |
| **`content_key` 불안정화** | 높음 | 정적 필드만 추가한다. `test_hub_model.py` 신규 케이스 ②(같은 스냅샷 2회 직렬화 → 같은 키)가 감시 |
| **`SessionView` 생성 지점 누락 → `TypeError`** | 낮음 | 생성 지점이 정확히 4곳이고 전부 열거했다(§4.1). 기본값을 주지 않는 것이 오히려 안전하다 — 누락이 조용히 1970년을 렌더하지 않고 즉시 터진다 |
| **`pad2` 를 스코프로 올릴 때 사용량 초기화 줄을 깨뜨린다** | 낮음 | 같은 IIFE 안이므로 이동만으로 충족된다. T25-41 의 네 토큰은 그대로. **이것이 이 커밋의 유일한 인접 코드 수정**이므로 검수자가 미리 알 수 있게 커밋 메시지 본문에 적는다 |
| **`data-tooltip` 추가가 툴팁 소음이 된다** | 낮음 | 결정 R4(정보 손실이 있을 때만)를 문자 그대로 충족한다 — `short_id` 는 `session_id` 의 절단이다 |

---

## 8. 후속 제안 (이번 범위 밖)

### 8.1 done 세션이 7일간 카드에 영구 누적된다 — "9개가 쌓인" 근본 원인

`shouldRenderSession`(`hub_template.html:937-944`)의 숨김 규칙은 비대칭이다.

- `stale` 세션: 마지막 이벤트로부터 12시간(`STALE_SESSION_HIDE_AFTER_MS`, `:720`) 넘으면 숨는다.
- `done` 세션: **시간 조건이 없다.** "발췌 없음 + 보이는 칩 0개" 일 때만 숨는다.

따라서 발췌나 칩이 하나라도 있는 done 세션은 **이벤트 보존 기간(7일) 내내 카드에 남는다.**
실측 최악 사례(daily-brief 표시 9개 중 done 8개)가 정확히 이 상태다. 요구 3 이 해결하려는
"구분이 안 된다"는 증상의 **원인**이 여기에 있다 — 9개가 없었다면 구분 문제도 없었다.

**이번에 고치지 않는다** — 사용자 요청 범위 밖이고, 숨김 규칙 변경은 "지난 작업을 못 찾겠다"는
반대 방향 불만을 만들 수 있어 사용자 판단이 필요하다. 선택지 셋을 제시한다.

1. done 에도 시간 조건을 준다(예: `STALE_SESSION_HIDE_AFTER_MS` 재사용 — 새 상수 0개).
2. 카드당 표시 세션 상한을 둔다(`MAX_VISIBLE_AGENT_CHIPS` 가 세운 "화면 상한은 화면의 몫"
   관례 그대로).
3. 아래 8.2 의 접기.

### 8.2 daily-brief 의 8개는 "반복 실행"으로 보인다 — 그 카드의 진짜 요구는 접기일 수 있다

daily-brief 카드의 done 세션 8개는 **발췌 앞 40자 해시가 전부 동일**하고 칩 조합도 동일하다
(distinct 1). 서로 다른 사람이 같은 프롬프트를 8번 입력했을 가능성보다, **스케줄 반복 실행**
(같은 프롬프트로 주기적으로 기동되는 세션)이 훨씬 그럴듯하다.

그렇다면 그 카드에 필요한 것은 "9개를 구분하는 것"이 아니라 **"같은 작업의 반복 실행을 한 줄로
접는 것"**(예: `일일 요약 · 8회 · 마지막 3분 전`)이다. 요구 3 의 해결(시작 시각 + `short_id`)은
이 접기와 상충하지 않는다 — 접힌 줄을 펼치면 그 안에서 개별 세션을 구분하는 데 같은 정보가
쓰인다. 워크트리 접기(`docs/prps/hub-worktree-fold.md`)가 이미 "같은 것을 하나로 접는" 선례다.

**사용자 판단이 필요하다**: 반복 실행 접기를 원하는가, 아니면 8.1 의 단순한 시간 숨김으로
충분한가.

### 8.3 하트비트 TTL 하한(15초)과 사용량 API 블로킹(최악 15초)이 같은 값이다

`server_heartbeat_ttl_ms` 의 하한 15초와 `hub_usage_fetch` 의 최악 블로킹 15초
(HTTP 10s + Keychain 5s)가 정확히 같다. 사용량 API 가 최악으로 느린 사이클에서
하트비트 나이가 TTL 경계에 닿아 `maintenance_stalled`(구 `collect_stalled`)가 오탐하고,
훅 폴백이 불필요하게 켜질 수 있다. **선재 결함이며 이번 변경이 만든 것이 아니다.**
처방 후보: TTL 하한을 20~30초로 올리거나, 사용량 API 호출 전후로만 하트비트를 찍는
현행 방식을 유지하되 하한을 `usage API 최악 시간 + 여유` 로 유도한다.

### 8.4 `log` 0-c 의 `limit=120` 재Read 분기는 그대로 살아 있다

**초안 정정(메인 세션 검증).** 이 절은 원래 "불변식 10 이후 항목이 항상 10~11줄이라 재Read
분기가 도달 불가가 된다"고 적혀 있었다. **틀렸다.** 불변식 10 은 *태그 사이* 개행만 금지하고
블록 텍스트 *안* 의 단일 개행은 보존하므로(§3.5 개정), 여러 줄 상세는 여전히 여러 줄
항목을 만든다. 이 변경으로 줄 수가 **늘지는** 않는다는 것이 정확한 서술이다 — 문단·목록
마크업이 태그로 붙어 들어가므로, 같은 입력의 줄 수는 변경 전과 같다.

→ `commands/dashboard.md:709-711` 의 재Read 분기는 **손대지 않는다.** 지금과 정확히 같은
빈도로 발동한다.

---

## 9. 미확인 항목

1. **브라우저 실측을 하지 못했다.** 이 세션에는 렌더링 환경이 없다. Q2 의 `<p>`·`<ul>`·
   `<code>` 렌더와 Q3 의 세션 줄 높이는 **CSS 명세와 코드 독해에 근거한 추론**이며 실제
   픽셀을 보지 않았다. 구현 후 다음 셋을 눈으로 확인해야 한다: (a) 문단 사이 간격이 6px 로
   보이는가(빈 줄이 새지 않는가) (b) 중첩 목록의 불릿과 들여쓰기 (c) 허브 카드에서 세션이
   몇 개까지 스크롤 없이 보이는가.

2. **Q3 의 "보이는 세션 4개 → 3개" 는 추정이다.** `.session-meta` 높이를 `font-size:11px`
   × 기본 `line-height` + `margin-top:3px` ≈ 20px 로 잡고, `.sessions` 가용 높이를
   340px 에서 헤더 블록을 뺀 약 240px 로 잡은 계산이다. 실측이 아니다.

3. **「`ul.log{list-style:none}` 가 중첩 목록에 상속된다」는 브리핑의 진단은 정확하지 않을
   가능성이 높다.** CSS 캐스케이드에서 **상속은 그 요소에 선언값이 하나도 없을 때만** 쓰이고,
   중첩 `<ul>` 에는 UA 스타일시트의 `ul ul{list-style-type:circle}`(Chromium `html.css`
   계열)이라는 선언값이 이미 있다. 따라서 불릿이 사라지는 것이 아니라 **UA 기본 글리프
   (circle)로 보일** 것이다. 브라우저 실측을 하지 못해 단정하지 않는다.
   **결론은 바뀌지 않는다** — 어느 쪽이든 글리프를 UA 에 맡기지 않고
   `.entry .detail ul{list-style:disc;padding-left:16px}` 로 못 박고, T22-130 으로 감시한다.
   브리핑의 처방을 그대로 채택하되 CSS 주석의 **사유 문구만** 사실에 맞게 적는다.

4. **`server_heartbeat_interval_seconds` 기본값 5가 최적인지 검증하지 않았다.** TTL 하한이
   15초여서 5는 여유 3배를 준다. 티커가 하는 일이 `touch()` 1회 + 게이트 판정 2회로
   극히 싸므로 그대로 두었으나, 10초로 늘려도 TTL 하한 15초와 여유 1.5배로 성립한다.
   측정 근거가 없어 바꾸지 않았다(측정 없는 최적화 금지).

5. **`/project/<key>/dashboard.html` 라우트에도 게이트를 거는 선택의 실사용 비용을 측정하지
   못했다.** "패널을 열어 둔 채 허브 탭을 숨긴" 상태를 재현해 60초당 수집 1회를 확인하지
   않았다. 코드 독해로는 확실하다(§2.2). 실측이 필요하면 구현 후
   `last_collect_success` 스탬프의 mtime 변화를 1분 간격으로 관찰하면 된다.

6. **기존 `config.json` 을 가진 사용자 수를 모른다.** `server_collect_interval_seconds` 를
   실제로 설정해 둔 사용자가 있으면 §2.7 의 폐기 안내를 보게 된다. `~/.claude/hub/config.json`
   은 개인 파일이라 이 세션에서 열지 않았다.

7. **Q2 의 발행물 패치(§3.7)를 실제로 적용할지는 사용자 결정이다.** 커밋 파급은 0이지만
   이 세션이 그 파일을 소유하고 있어(토큰 `76498cb6`) 갱신 주체 규칙상 메인 세션의 몫으로
   남겼다.
