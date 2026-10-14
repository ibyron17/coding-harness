# 허브 서버 Host 헤더 검사 — DNS 리바인딩 차단

- 경로: **전체 경로**(보안 변경 — 설계 → 사용자 승인 → 구현 → 검수)
- 화면 변화: **없음**(정상 주소로 연 허브는 그대로다) → 프리뷰 목업 대상 아님
- 결정 ID 접두: **HG**

## 1. 요구사항 요약

상주 서버 `hub/bin/hub_server.py` 는 `127.0.0.1` 에만 bind 하므로 원격 호스트는 닿지 못한다. 하지만
사용자 브라우저에 열린 **원격 웹 페이지**는 DNS 리바인딩(공격자 도메인이 TTL 만료 뒤 `127.0.0.1` 로 다시
풀린다)으로 이 포트에 요청을 보내고, 그 응답을 **자기 출처의 응답처럼** 읽을 수 있다. 현재 `do_GET` 은
`self.path` 만 보고 Host 헤더를 전혀 보지 않으므로, 그 페이지가 `hub.html`(프롬프트 발췌·계정 이메일·
조직 이름 인라인)과 프로젝트 대시보드를 읽는다. 리바인딩된 요청의 `Host` 는 언제나 공격자 도메인이므로,
**Host 가 `localhost:<실제 포트>`·`127.0.0.1:<실제 포트>` 가 아니면 경로 판정·수집보다 먼저 403 으로 거절**해
이 경로를 닫는다. 새 설정 키·새 의존성 없이 순수 판정 함수 1개 + `do_GET` 첫머리 3줄로 끝낸다.

## 2. 위협 모델 — 막는 것과 못 막는 것

| 경로 | 이 변경 후 |
|------|-----------|
| 원격 페이지가 DNS 리바인딩으로 `hub.html`·대시보드를 **읽기** | **막힌다** — 그 요청의 Host 는 공격자 도메인 → 403, 본문·수집 없음 |
| 원격 페이지가 `http://localhost:8794/…` 로 요청을 **보내기**(img·no-cors fetch) | 막지 않는다 — Host 가 정상이라 통과한다. 응답은 같은 출처 정책으로 **읽지 못한다**. 부수효과는 신선도 창(2초) 안 1회 수집뿐(§11 R3) |
| 이 포트에 닿는 **로컬의 다른 프로세스** | 막지 않는다 — Host 를 마음대로 적을 수 있다. 종전 고지 그대로 |
| SSH 포트 포워딩·리버스 프록시 경유 접근(다른 이름·포트) | **새로 거절된다** — 의도된 부작용, README 에 고지(§10) |

## 3. 영향 범위

| 파일 | 변경 | 이유 |
|------|------|------|
| `hub/bin/hub_server.py` | 수정(+약 25줄) | 상수 3개 + 순수 판정 함수 `is_allowed_host_header` + `do_GET` 첫머리 거절 3줄 + 클래스·`do_GET` docstring 한 줄씩 |
| `tests/hub/test_hub_server_host_guard.py` | **신규**(약 150줄) | 순수 함수 표 테스트 + 실소켓 통합 테스트. `test_hub_server.py` 는 이미 865줄(800줄 상한 초과)이라 붙이지 않는다 |
| `hub/README.md` | 수정(186~192행 문단 1개) | 노출 고지에 Host 검사·DNS 리바인딩·여전히 못 막는 것·포트 포워딩 거절을 적는다 |
| `commands/hub.md` | **변경 없음** | §10.2 판단 |
| `tests/run.sh` | **변경 없음** | 정적 가드 추가 안 함(결정 HG8) |

상시 컨텍스트 파일(`CLAUDE.md`·`rules/README.md`·`rules/common`·`rules/workflow`)은 건드리지 않는다 — T26 래칫 무관.
`removals.txt` 무관(지우거나 개명하는 관리 파일 없음).

## 4. 파일 구조와 모듈 경계

- 판정 로직은 `hub_server.py` **모듈 수준 순수 함수**로 둔다. 같은 파일의 `ALLOWED_REQUEST_PATHS`·
  `PROJECT_DASHBOARD_PATH_PATTERN`(노출 표면 상수, 테스트가 모듈에서 직접 꺼내 쓴다)과 나란히 놓여
  "이 서버가 무엇을 받아 주는가"가 한 자리에 모인다.
- `hub_server_state.py`(★순수·잎 모듈)로 옮기지 않는다 — 그 모듈의 책임은 "기록 형식과 생존·재수집 판정"이고
  요청 수락 정책은 HTTP 서버의 관심사다. 옮기면 변경 파일이 2개로 늘어 병합 면적만 커진다.
- I/O 경계: 핸들러(`do_GET`)가 헤더 목록과 포트를 꺼내 순수 함수에 넘기고, 그 bool 로 403 여부만 정한다.
  순수 함수는 소켓·파일·시계에 닿지 않는다.

## 5. 데이터 모델

새 dataclass 는 없다. 모듈 간 통신이 생기지 않는다(같은 모듈 안의 함수 호출 1회). 입력은 표준 타입 두 개다.

| 이름 | 타입 | 출처 |
|------|------|------|
| `host_header_values` | `list[str]` | `self.headers.get_all("Host", [])` — 없으면 `[]`, 중복이면 길이 2 이상 |
| `server_port` | `int` | `self.server.server_address[1]` — 실제 bind 된 포트(결정 HG2) |

실측 근거(Python 3.11.5 `http.server`): Host 누락 → `get_all` 이 `[]`. 중복 → `['a', 'b']`. 값 앞 공백은
파서가 벗기지만 **뒤 공백·탭은 남는다**(`'localhost:1  \t'`). absolute-form 요청(`GET http://evil/hub.html`)은
`self.path` 가 URI 전체(`'http://evil.example/hub.html'`)로 남는다. `server_address[1]` 은 포트 0 bind 뒤
실제 포트와 같다.

## 6. 인터페이스

```python
# hub/bin/hub_server.py — 모듈 상수(이름·값은 확정, 주석은 "왜"를 적는다)
ALLOWED_HOST_NAMES = ("localhost", "127.0.0.1")   # [::1] 은 넣지 않는다(HG3)
HTTP_DEFAULT_PORT = 80                             # 기본 포트면 클라이언트가 Host 에서 포트를 생략한다(HG4)
HTTP_OPTIONAL_WHITESPACE = " \t"                   # RFC 9110 OWS — 필드 값 앞뒤 공백·탭은 값이 아니다(HG5)


def is_allowed_host_header(host_header_values: list[str], server_port: int) -> bool:
    """Host 헤더가 정확히 1개이고 그 값이 허용 이름:실제 포트일 때만 True(순수 — DNS 리바인딩 방어)."""
```

동작 계약(구현은 implementer 몫):

1. `len(host_header_values) != 1` 이면 `False`(누락·중복).
2. 값 하나를 `HTTP_OPTIONAL_WHITESPACE` 로 앞뒤만 벗기고 소문자로 바꾼다.
3. 허용 집합 = `{f"{name}:{server_port}" for name in ALLOWED_HOST_NAMES}`, `server_port == HTTP_DEFAULT_PORT`
   일 때만 포트 없는 이름 2개를 더한다. **문자열 전체 일치**로만 판정한다 — 호스트·포트를 쪼개 `int()` 로
   파싱하지 않는다(`int()` 는 `'+8794'`·`'08794'`·`'8_794'` 를 전부 8794 로 받아 준다).

호출부(`_HubRequestHandler.do_GET` 맨 앞, 경로 판정·`_refresh_if_stale` 보다 먼저):

```python
if not is_allowed_host_header(self.headers.get_all("Host", []), self.server.server_address[1]):
    self.send_error(403)
    return
```

`do_GET` docstring 첫 줄을 "Host 판정 → 경로 판정 → 신선도 게이트 → 본문 생산"으로 고친다. 클래스 docstring 에
"Host 가 루프백 이름:실제 포트가 아니면 경로와 무관하게 403" 한 줄을 더한다. 둘 다 이 문서 경로를 인용한다.

## 7. 설계 결정과 근거

**HG1 — 검사 위치: `do_GET` 맨 앞.** 경로 판정보다 먼저여야 ① 위조 요청이 `_refresh_if_stale`(수집)을
부르지 않고(favicon 관례 `RequestFreshnessGateTest` 와 같은 원칙) ② 새 GET 라우트가 생겨도(동시 진행 중인
harness-versioning 작업 포함) 자동으로 덮인다. `parse_request`/`handle_one_request` 오버라이드로 전 메서드를
덮는 안은 기각 — GET 외 메서드는 `BaseHTTPRequestHandler` 가 본문 없는 501 로 이미 거절하므로 막을 정보가 없다(YAGNI).

**HG2 — 포트 출처: `self.server.server_address[1]`(서버 인스턴스의 실제 bind 주소).** 사용자 요구 "기존
상태에서 얻는다"를 **이미 서버 인스턴스에 있는 bind 결과**로 해석했다(열린 질문 Q1).
- 이 값이 "이 요청이 도착한 포트"의 정의 그 자체다. `run_server` 가 `ServerRecord.port` 에 쓰는 값
  (`config.server_port`)과 운영에서 늘 같고, 둘이 어긋나는 경우는 기록 쪽이 틀린 경우뿐이다.
- `ServerRecord.port`(server.json) 기각: 요청마다 파일 읽기+JSON 파싱이 생기고, 파일이 없거나 낡았을 때
  (SIGTERM 핸들러가 `shutdown` 완료 전에 지운다, 다른 인스턴스가 덮어쓴다) **fail-open 이면 보안 구멍,
  fail-closed 면 전면 잠김**이라는 새 정책 결정이 필요해진다. 포트 0 으로 bind 하는 기존 테스트 관용구와도 맞지 않는다.
- `config.server_port` 기각: 핸들러에 config 를 실어 나를 새 서버 속성이 필요하고, 실행 중 config 를 고치면
  실제 bind 포트와 어긋난다.
- `HTTPServer.server_port` 속성도 같은 값이지만 `HubConfig.server_port` 와 이름이 겹쳐 읽는 사람이 설정값으로
  오인한다. 테스트가 이미 쓰는 `server_address[1]` 관용구에 맞춘다.
- 결과적으로 `run_server`·서버 속성·테스트 `setUp` 어디도 바뀌지 않는다(병합 면적 최소).

**HG3 — `[::1]` 미포함.** `BIND_ADDRESS` 가 IPv4 전용(`ThreadingHTTPServer` 기본 `AF_INET`)이라 `[::1]` 로는
연결 자체가 안 된다 — 그 Host 로 정상 도착하는 요청이 없다. IPv6 bind 를 추가하는 변경이 그때 함께 넣는다.

**HG4 — 기본 포트(80)면 포트 없는 Host 도 받는다.** 기능 추가가 아니라 **현재 동작하는 설정의 회귀 방지**다.
`server_port` 는 README 에 문서화된 설정 키이고 범위 검증이 없으며, macOS 는 비루트도 80 에 bind 할 수 있다.
그 설정에서 브라우저·`urllib`(`_check_http_ok`)는 Host 에서 `:80` 을 생략하므로, 이 규칙이 없으면 모든 요청이
403 이 되고 `/hub server status` 의 `http_ok` 까지 거짓이 된다. 비용은 조건 1개.

**HG5 — 대소문자 무관 + 앞뒤 OWS 제거, 그 외는 전부 정확 일치.** 호스트 이름은 RFC 상 대소문자 무관이고
(`LOCALHOST:8794`), 소문자화가 공격자 도메인을 `localhost` 로 바꿀 수는 없으니 안전하다. OWS 는 RFC 9110 상
값이 아니다. `str.strip()`(인수 없음)은 쓰지 않는다 — latin-1 NBSP(`\xa0`) 등까지 벗겨 RFC 보다 넓어진다.

**HG6 — 거절 코드 403, 본문 기본값, 로그 없음.**
- 404 기각: 이 허브는 이미 404 를 "hub.html 이 아직 없다(첫 수집 전)"는 **알려진 일시 상태**로 쓴다
  (`hub.py` 의 `server_ready` 판정 docstring). 포트 포워딩 같은 정당한 오용이 404 를 받으면 "서버가 덜 떴다"로
  오진한다. 403 은 "알아들었지만 정책상 거절"이라 원인이 바로 보인다. 404 의 "정보를 덜 준다"는 이점은 없다 —
  연결이 받아들여진 순간 리스너 존재는 이미 드러나고, Host 검사는 비밀이 아니다.
- 400 기각(RFC 9112 는 Host 누락·중복에 400 을 요구한다): 사용자 요구가 403/404 이고, 코드를 하나로 묶어야
  판정 함수가 bool 로 남는다. 400 에 의존하는 클라이언트는 없다.
- `self.send_error(403)` 에 메시지를 넘기지 않는다 — `message` 는 상태줄에 들어가 latin-1 로만 인코딩되므로
  한국어를 넣으면 `UnicodeEncodeError` 다. 기본 본문은 정적이며 요청 내용을 되비추지 않는다.
- server.log: `send_error` → `log_error` → `log_message`(이미 무음 오버라이드)라 거절이 로그를 부풀리지 않는다.
  일부러 기록하지 않는다 — 공격자가 요청량을 정하는 이벤트이고 server.log 크기 제한은 **기동 시**에만 걸린다.
- 상태 코드는 기존 코드(`send_error(404)`)처럼 정수 리터럴로 쓴다(주변 스타일 일치).

**HG7 — 판정을 순수 함수로 뽑는다.** 경계 사례가 15개를 넘는데 실소켓으로 하나하나 돌리면 느리고, 중복 Host 처럼
`http.client` 로 만들기 번거로운 입력이 있다. 표 테스트로 판정을, 실소켓 테스트로 배선(위치·순서·코드)을 나눠 본다.
**패턴 도입 없음** — 상수 3개 + 함수 1개가 가장 단순한 구조다. 허용 집합을 기동 시 한 번 만들어 서버에 싣는
안은 `run_server`·테스트 `setUp` 을 함께 고쳐야 해서 기각(요청당 비용은 문자열 2~4개 포맷).

**HG8 — `tests/run.sh` 정적 가드 추가 안 함.** 동작은 새 unittest 가 고정하고, `run.sh` T24 가
`unittest discover -s tests` 로 그것을 돌리므로 검사를 지우면 두 검증 명령이 모두 실패한다. 상수 이름 grep 은
그보다 약하고(상수만 남고 호출이 사라져도 통과) 비용이 크다 — 새 가드 ID, `SOURCE_GUARD_ID_FLOOR` 상향과 그
사유 주석, `tests/mutations.tsv` 원장 행이 필요하고, 동시 세션과 충돌하기 가장 쉬운 16,000행 넘는 파일을 건드린다.

## 8. 경계 사례 판정표 (`server_port = 8794` 기준, HG4 행만 예외)

| Host 헤더 입력(`get_all` 결과) | 판정 | 근거 |
|-------------------------------|------|------|
| `["127.0.0.1:8794"]` / `["localhost:8794"]` | 허용 | 정상 |
| `["LOCALHOST:8794"]` / `["Localhost:8794"]` | 허용 | HG5 대소문자 무관 |
| `["localhost:8794  \t"]`(뒤 OWS) | 허용 | HG5 — 파서가 앞 공백만 벗긴다(실측) |
| `[]`(누락 — HTTP/1.0 포함) | 거절 | 브라우저·`http.client`·`urllib`·curl 모두 Host 를 보낸다 |
| `["localhost:8794", "localhost:8794"]`(중복, 둘 다 정상) | 거절 | 어느 쪽을 믿을지 정할 수 없다 |
| `["localhost:8794", "evil.example"]` | 거절 | 위와 같음 |
| `["evil.example:8794"]` / `["evil.example"]` | 거절 | 리바인딩 본체 |
| `["localhost"]` / `["127.0.0.1"]`(포트 생략, 8794) | 거절 | 기본 포트가 아니면 클라이언트는 포트를 적는다 |
| `["localhost"]`·`["localhost:80"]`, `server_port = 80` | 허용 | HG4 |
| `["localhost.:8794"]`(후행 점) | 거절 | 정상 클라이언트(허브 코드·브라우저 북마크)가 쓰지 않는다 — 정확 일치로 충분하다 |
| `["localhost:9999"]`(다른 포트) | 거절 | 포워딩·프록시 경유 — README 고지 |
| `["localhost:08794"]` / `["localhost:+8794"]` | 거절 | 정확 일치(HG 인터페이스 3) |
| `["user@localhost:8794"]` / `["localhost:8794@evil.example"]` | 거절 | userinfo 섞임 |
| `["localhost:8794/hub.html"]` | 거절 | 경로 섞임 |
| `["localhost :8794"]`(가운데 공백) / `[""]` | 거절 | OWS 는 앞뒤만 |
| `["[::1]:8794"]` | 거절 | HG3 |
| `["127.0.0.2:8794"]` / `["0.0.0.0:8794"]` / `["sub.localhost:8794"]` | 거절 | 허용 목록 밖(정확 일치) |
| absolute-form `GET http://evil.example/hub.html` + `Host: localhost:8794` | Host 는 허용 → 경로 화이트리스트가 404 | 브라우저는 프록시가 아닌 서버에 absolute-form 을 보내지 않으므로 리바인딩 경로가 아니다. 수집도 안 부른다(통합 테스트로 고정) |

## 9. 기존 테스트·가드·클라이언트 영향 분석

| 대상 | 영향 |
|------|------|
| `test_hub_server.py` `_RunningHubServerTestCase._get` | `HTTPConnection("127.0.0.1", port)` 가 `Host: 127.0.0.1:<port>` 를 자동으로 붙이고 그 port 가 `server_address[1]` 과 같다 → 기존 U16~U18·라우팅·nosniff·`RequestFreshnessGateTest` 그대로 통과 |
| `test_hub_usage_fetch.py` 실소켓 테스트 | 자기 스텁 핸들러를 쓴다(허브 핸들러 아님) → 무관 |
| `template_dom_harness.py` 의 `server_address` | 별개 정적 서버 → 무관 |
| `hub_daemon._check_http_ok` | `http://localhost:{port}/hub.html` → `Host: localhost:<port>` 허용 |
| `hub_daemon._is_port_occupied` | 소켓 `connect_ex` 만 → 무관 |
| `hub.py`·`start_server` 가 여는 URL | `localhost:<port>` → 허용. README 의 `127.0.0.1:8794` 북마크도 허용 |
| 허브 페이지 폴링(`fetch(location.pathname)`)·상세 패널 iframe(`/project/<key>/dashboard.html` 상대 경로) | 같은 오리진 → 같은 Host → 허용 |
| `run.sh` T25-15·T25-57(토큰 grep)·T25-122(AST: `do_GET` 본문에 `hub_usage_fetch` 없음)·T25-173·T40-14(`_serve_project_dashboard` 본문) | 토큰·함수 이름 유지, 금지 토큰 미추가 → 통과 |
| `run.sh` T25-100(hub/bin/*.py 800줄 상한) | 498 → 약 525줄 → 통과 |
| `mutations.tsv` 의 `hub/README.md` 대상 행(T22-137·T25-104·T25-109·T25-146·T25-149·T25-188·T25-81) | 고칠 문단(186~192행)에 그 sed 대상 문자열이 없다 → 영향 없음. README 노출 문단을 grep 하는 가드는 없음을 확인했다 |

## 10. 문서 변경

### 10.1 `hub/README.md` 186~192행 문단 교체안

> - **서버 가동 중에는 `127.0.0.1:8794` 가 열려 있다.** 루프백 바인딩(원격 불가) + 화이트리스트로 제한돼
>   `events/*.jsonl`·`bin/*.py`·`config.json` 은 노출되지 않는다. 허용 경로는 `/`·`/hub.html` 과, 티어 1 프로젝트의
>   `/project/<16자리 hex>/dashboard.html`(요청 문자열로 파일 경로를 조립하지 않는 결정적 키 조회) 뿐이다.
>   요청의 `Host` 헤더가 `localhost:8794`·`127.0.0.1:8794`(대소문자 무관, `server_port` 를 바꿨으면 그 포트) 중
>   하나가 아니면 경로와 상관없이 403 으로 거절하고 수집도 하지 않는다 — 브라우저에 열린 **원격 웹 페이지**가 DNS
>   리바인딩(자기 도메인 이름이 127.0.0.1 로 다시 풀리게 하는 수법)으로 이 포트의 응답을 읽는 길을 막는다. 그래서
>   다른 이름이나 포트로 바꿔 들어오는 포트 포워딩·프록시 경유 접근도 거절된다. 원격 페이지가 이 주소로 요청을
>   **보내는** 것 자체는 막지 않는다(응답은 브라우저의 같은 출처 정책 때문에 읽지 못한다). 이 검사는 브라우저 경로만
>   막는다 — 이 포트에 닿는 **로컬**의 다른 프로세스는 `Host` 헤더를 마음대로 적을 수 있으므로 여전히 `hub.html` 에
>   인라인된 프롬프트 발췌·계정 이메일과 조직 이름을 읽거나 서빙 중인 프로젝트 대시보드를 열 수 있다. 끄는 수단은
>   `record_prompt_excerpt:false`·`show_account_info:false` 와 `/hub server stop` 이다. 프로젝트 상세 패널(서버
>   모드)의 iframe 도 같은 허브 오리진에서 실행되며 이 노출 범위를 넘지 않는다.

README 방침(현재 상태만 기술, 변경 이력 금지)에 맞춰 "새로 생겼다" 같은 표현을 쓰지 않는다.

### 10.2 `commands/hub.md` — 고치지 않는다

160~168행 설치 고지는 "무엇이 기록·인라인되는가"에 대한 동의 문구이고, "127.0.0.1 로컬 서버가 그 파일을
제공"은 변경 후에도 사실이다. 이 커맨드는 10행에서 "프라이버시 고지 전부는 `hub/README.md`"로 위임한다. 이 변경은
노출을 **좁히기만** 하므로 사용자가 동의할 내용이 늘지 않는다 — 동의 문구를 늘릴 이유가 없다(열린 질문 Q2).

## 11. 테스트 계획 — `tests/hub/test_hub_server_host_guard.py`(신규)

**준비 코드 재사용**: `test_hub_server._RunningHubServerTestCase` 를 import 해 상속한다. 선례는
`test_hub_template_dom_modal_layout.py` 가 `test_hub_template_dom_modal_cleanup` 에서 가져오는 관용구 —
`try: from .test_hub_server import _RunningHubServerTestCase` / `except ImportError: from test_hub_server import …`
(직접 실행 경로). 중복 실행 위험 없음: discover(`-t .` 또는 `-t $REPO_ROOT`)가 그 모듈을 `tests.hub.test_hub_server`
로 한 번 적재하고 상대 import 는 같은 모듈 객체를 받는다. 가져온 `_RunningHubServerTestCase` 는 `test_*` 메서드가
없어 새 모듈에서 0건으로 적재된다. 복제(약 25줄)는 기각 — 준비 코드가 두 벌이 되면 한쪽만 고쳐지는 표류가 생긴다.

새 서브클래스 `setUp` 은 `super().setUp()` 뒤 `hub.html` 을 고유 센티널(`HOST-GUARD-SENTINEL`)을 담은 내용으로
덮어써, 거절 응답 본문에 허브 내용이 섞이지 않았음을 문자열로 단언할 수 있게 한다.

**Host 를 조작하는 요청 헬퍼**: `_get_with_host_values(path: str, host_values: tuple[str, ...]) -> HTTPResponse` —
`connection.putrequest("GET", path, skip_host=True)` 후 `host_values` 의 각 값을 `putheader("Host", value)` 로
보내고 `endheaders()`. 빈 튜플이면 Host 누락, 2개면 중복이다(세 경우를 한 헬퍼로). `request(..., headers={"Host": …})`
는 단일 값만 만들 수 있어 쓰지 않는다.

### 11.1 순수 함수 — `IsAllowedHostHeaderTest`(AAA, `subTest` 표)

- `test_accepts_loopback_names_with_actual_port` — §8 허용 행 전부(정상 2, 대소문자 2, 뒤 OWS 2: 공백·탭).
- `test_rejects_everything_else` — §8 거절 행 전부(누락·중복 2종·위조 2·포트 생략 2·후행 점·다른 포트·`08794`·
  `+8794`·userinfo 2·경로 섞임·가운데 공백·빈 문자열·`[::1]`·`127.0.0.2`·`0.0.0.0`·`sub.localhost`).
- `test_default_port_allows_host_without_port` — `server_port=80` 에서 `["localhost"]`·`["127.0.0.1"]`·
  `["localhost:80"]` 허용, 같은 `["localhost"]` 가 `server_port=8794` 에서는 거절.

### 11.2 실소켓 통합 — `HostHeaderGuardRoutingTest(_RunningHubServerTestCase)`

1. `test_loopback_hosts_are_served` — `/`·`/hub.html` × `127.0.0.1:<port>`·`localhost:<port>` → 200, 본문에 센티널.
2. `test_forged_host_is_403_on_every_path` — `evil.example:<port>` 로 `/`·`/hub.html`·
   `/project/1111111111111111/dashboard.html`(레지스트리에 등록)·`/favicon.ico` → 전부 403, 본문에 센티널 없음.
   등록 키·미인식 경로가 404 가 아니라 403 인 것이 "Host 판정이 경로 판정보다 먼저"의 증거다.
3. `test_missing_host_is_403` — Host 0개로 `/hub.html` → 403.
4. `test_duplicate_host_is_403` — 정상 값 2개로 `/hub.html` → 403.
5. `test_rejected_requests_do_not_call_the_gate` — `snapshot_refresher` 를 `mock.Mock()` 으로 싣고, 위조·누락·중복
   Host 로 인식 경로(`/hub.html`, 대시보드)를 요청 → `collect_if_older_than.assert_not_called()`. 같은 표에
   absolute-form(`putrequest("GET", "http://evil.example/hub.html", skip_host=True)` + 정상 Host) → 404 이고 게이트
   미호출 1행을 넣는다(§8 마지막 행).

### 11.3 검사가 실제로 무는지 확인(구현 단계, 커밋 대상 아님)

`do_GET` 의 거절 3줄을 임시로 지우면 11.2 의 2~5 가 실패하고, `is_allowed_host_header` 가 항상 `True` 를 돌려주게
바꾸면 11.1 거절 표가 실패하는지 손으로 확인하고 되돌린다(`code-review.md` "deliberately broken").

### 11.4 검증 명령

```bash
python3 -m py_compile hub/bin/*.py
PATH="/usr/local/bin:$PATH" python3 -m unittest discover -s tests/hub -t .
bash tests/run.sh
```

## 12. 리스크와 대안

**리스크**

- **R1 — 포트 포워딩·프록시 사용자 잠김.** 다른 이름·포트로 들어오던 접근이 403 이 된다. 의도된 부작용이고
  README 에 고지한다. 우회 설정 키를 만들지 않는다(요구 2 "새 설정 키 금지", YAGNI).
- **R2 — 준비 코드의 비공개 이름 결합.** 동시 세션이 `_RunningHubServerTestCase` 를 개명·이동하면 새 테스트 파일이
  `ImportError` 로 **시끄럽게** 깨진다(조용한 무력화가 아니다). 병합 시 이름 하나만 맞추면 된다.
- **R3 — 원격 페이지의 "보내기"는 남는다.** `<img src="http://localhost:8794/hub.html">` 는 정상 Host 로 도착해
  신선도 창(2초)당 최대 1회 수집을 부를 수 있다. 응답은 읽지 못하므로 기밀성 문제는 아니고 비용은 기존 창이
  묶는다. `Origin`·`Sec-Fetch-Site` 검사로 막는 안은 범위 밖(아래 대안 B).
- **R4 — 동시 세션(harness-versioning)과의 병합.** 이 변경의 `hub_server.py` 접점은 상수 블록(41~46행 근처)과
  `do_GET` 첫머리뿐이다. 그쪽이 `do_GET` 에 라우트를 더하면 같은 함수의 서로 다른 줄이라 기계적 병합으로 풀리고,
  새 라우트는 HG1 덕에 자동으로 Host 검사 뒤에 온다.
- **R5 — RFC 와 다른 상태 코드.** 누락·중복 Host 에 RFC 는 400 을 요구한다(HG6). 의존하는 클라이언트 없음.

**검토했으나 채택하지 않은 대안**

- **A — 접근 토큰(URL 쿼리·쿠키) 인증(Jupyter 방식).** 로컬 다른 프로세스까지 막을 수 있지만 북마크 가능한 고정
  URL(README·`commands/hub.md` 351행 "북마크 가능해야 하므로")을 깨고, 토큰 저장·전달·회전이라는 새 표면을 만든다.
  이번 위협(리바인딩)에는 Host 검사로 충분하다.
- **B — `Origin`/`Sec-Fetch-Site` 검사 추가.** 리바인딩에는 무력하다 — 리바인딩된 요청은 공격자 출처 기준
  same-origin 이라 이 헤더들이 정상처럼 보인다. 효과가 있는 R3("보내기")는 기밀성 문제가 아니라 비용 문제이고
  2초 창이 이미 묶는다. YAGNI.
- **C — 포트를 server.json 에서 읽기.** HG2 참조(요청당 I/O, fail-open/closed 정책 필요, 포트 0 테스트 불일치).

## 13. 구현 순서와 완료 기준

1. 새 테스트 파일 작성 → 실행해 RED 확인(11.1 은 `AttributeError`, 11.2 의 2~5 는 200/404 로 실패).
2. `hub_server.py` 상수·함수·`do_GET` 3줄·docstring 2곳 → GREEN.
3. 11.3 손 확인.
4. `hub/README.md` 문단 교체(10.1).
5. 11.4 세 명령 전부 통과.

커밋 메시지 제안: `fix: 허브 서버가 낯선 주소 이름으로 들어온 요청을 거절한다`

## 14. 사용자 결정(2026-10-13)

- **Q1** — 포트는 서버가 실제로 bind 한 주소(`self.server.server_address[1]`)를 쓴다. HG2 그대로 확정.
- **Q2** — `commands/hub.md` 설치 고지는 고치지 않고 `hub/README.md` 만 고친다. §10.2 그대로 확정.
- **Q3** — SSH 포트 포워딩·프록시로 허브를 보는 사용 방식은 없다. R1 가정 확정.
