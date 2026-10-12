# 허브 티어 1 클램프 잘림 수정 + 세션 모델·effort 표시

> 결정 접두: **TC**(Tier1 Clamp, 요구 1) · **MD**(Model Display, 요구 2).
> `LT`·`IL` 은 [`dashboard-lead-tooltip-and-interaction-lockdown.md`](dashboard-lead-tooltip-and-interaction-lockdown.md) 가 이미 썼다.

---

## 1. 요구사항 요약

허브 카드에서 두 가지를 고친다. **둘은 서로 독립이다.**

1. **(요구 1)** 티어 1 진행 단계 줄(`.tier1-active`)의 텍스트 하단이 잘려 보인다. 1줄짜리
   텍스트조차 필요 높이 18px 대신 12~13px 로 렌더돼 글자의 아랫부분이 깎인다. 원래 의도인
   "최대 2줄 클램프"는 유지한 채 잘림만 없앤다.
2. **(요구 2)** 카드의 세션 줄에 그 세션이 **지금 쓰고 있는 모델과 노력(effort)** 을
   보여준다. 실측상 세션마다 모델이 다르고(한 세션 안에서 바뀌기도 한다) 지금은 그것을
   화면에서 알 방법이 전혀 없다.

---

## 2. 요구 1 — 원인 규명

### 2.1 메인 세션의 실측과 그 해석의 정정

착수 지시는 원인을 **blockification**(`display:-webkit-box` 가 `flow-root` 로 계산되며
`-webkit-box` 포매팅 컨텍스트가 사라진다)으로 지목했다. 관측치(`display: flow-root`)는
정확하지만 **그것은 잘림의 원인이 아니다.** 설계 단계에서 헤드리스 Chrome 151 로 재현·격리한
결과 원인은 다른 데 있었고, 원인을 잘못 잡으면 고치는 곳도 달라진다.

### 2.2 진짜 원인 — flex 축소(`flex-shrink`)

```
.card{ … height:340px; display:flex; flex-direction:column; overflow:hidden }
  └ .tier1-active{ … display:-webkit-box; -webkit-line-clamp:2; overflow:hidden }   ← flex 아이템
```

`.tier1-active` 는 `.card`(세로 flex 컨테이너)의 **직계 자식이므로 flex 아이템**이다
(`hub_template.html` 의 `renderProject` 가 `renderTier1()` 의 반환 div 3개를 카드 바로 밑에
붙인다 — 중간 래퍼가 없다). flex 아이템은 기본값 `flex-shrink:1` 로 줄어들 수 있고, 보통은
`min-height:auto`(자동 최소 크기 = 콘텐츠 높이)가 그 축소를 막아 준다.

**그런데 `overflow:hidden` 이 그 자동 최소 크기를 0 으로 만든다.** 그래서 카드 내용이 고정
높이 340px 를 넘기는 순간(= 세션이 몇 건만 쌓여도) `.tier1-active` 만 0 까지 짓눌릴 수 있는
유일한 형제가 되고, 실제로 짓눌린다.

`display:flow-root` 는 blockification 의 결과가 맞지만 **무해하다** — Chrome 은 블록 컨테이너에도
`-webkit-line-clamp` 를 적용하므로 클램프 자체는 정상 동작한다(§2.3 의 `f-webkit` 3줄 = 36px 이
그 증거다). 잘림의 원인은 오직 축소다.

### 2.3 실측 (헤드리스 Chrome 151.0.7922.174, 카드 구조 재현)

`sess1` = 카드가 넘치지 않는 경우, `sess6` = 넘치는 경우. `want` 는 1줄 18px · 2줄 이상 36px.

| 후보 | CSS | sess1 1줄 | sess6 1줄 | sess6 2줄 | sess6 3줄 | 판정 |
|---|---|---|---|---|---|---|
| **현행** | `-webkit-box` + clamp + `overflow:hidden` | 18px OK | **11.28px 잘림** | **11.28px 잘림** | **21.55px 잘림** | 결함 |
| **A. `flex-shrink:0` 추가** | 현행 + `flex-shrink:0` | 18px | **18px** | **36px** | **36px** | **전 케이스 정상** |
| B. `flex:0 0 auto` | 현행 + `flex:0 0 auto` | 18px | 18px | 36px | 36px | 정상(A 와 동일) |
| C. 표준 `line-clamp:2` | `line-clamp:2;overflow:hidden;flex-shrink:0` | 18px | 18px | 36px | **54px 클램프 안 됨** | 기각 |
| D. `max-height:3em` | `max-height:3em;overflow:hidden;flex-shrink:0` | 18px | 18px | 36px | 36px | 동작하나 말줄임표 없음 |
| E. `-webkit-box` 제거 | clamp + `overflow:hidden;flex-shrink:0` | 18px | 18px | 36px | **54px 클램프 안 됨** | 기각 |
| F. `overflow:hidden` 제거 | `-webkit-box` + clamp | 18px | 18px | 36px | 36px(scroll 54) | 기각 — 넘친 3번째 줄이 밖으로 새어 나온다 |

**실제 `~/.claude/hub/hub.html` 로 교차 검증** (설치본 복사본에 CSS 한 줄만 패치, 동일 브라우저):

| | `.tier1-active` 높이 | clientHeight | scrollHeight | 판정 |
|---|---|---|---|---|
| 수정 전 | **12.63px** | 13 | 18 | **잘림** |
| 수정 후(`flex-shrink:0`) | **18.00px** | 18 | 18 | 정상 |

스크린샷으로 3줄 이상 케이스가 **2줄 + 말줄임표(`…`)** 로 정확히 잘리는 것까지 육안 확인했다.

### 2.4 결정

- **TC1 — `.tier1-active` 에 `flex-shrink:0` 을 추가한다.** 한 속성, 한 줄. 다른 무엇도 건드리지
  않는다(수술적 변경).

  > → **걷힘(2026-09-30)** — 카드의 직계 자식이던 `.tier1-active` 인스턴스(프로젝트 단위 진행률)가 카드에서 사라져 이 선언은
  > 효력을 잃었다(hub-session-modal-cleanup.md 결정 MX5). TC2 는 카드 목록의 세션 줄에 그대로 유효하고, 카드 상세보기의 세션
  > 카드만 클램프를 푼다(MX9).
- **TC2 — 걷힘(LM4) — 대상 `.tier1-active` 소멸(hub-session-row-layout-and-modal-size.md).** ~~`display:-webkit-box`·`-webkit-box-orient:vertical` 을 그대로 둔다.~~ (아래는 걷히기 전의 기록이다.) 후보 E 가
  보여주듯 `-webkit-box` 를 빼면 3줄 케이스가 54px 로 **클램프 자체가 사라진다.** "계산값이
  `flow-root` 이니 죽은 선언"으로 보고 정리하고 싶어지는 자리인데, 실측상 살아 있다.
  이 오해를 막는 주석과 역방향 회귀 검사(T25-148)를 함께 둔다.
- **TC3 — `flex:0 0 auto`(후보 B)가 아니라 `flex-shrink:0`(후보 A)을 쓴다.** 결과는 같지만
  `flex-basis`·`flex-grow` 까지 함께 고정하는 것은 이번 결함과 무관한 변경이다. 저장소에
  `flex:0 0 auto` 선례(`.project-head .badge`·`.last-activity`)가 있으나 그쪽은 가로 flex 에서
  **늘어남까지** 막아야 했던 자리라 사정이 다르다.
- **TC4 — 클램프를 버리지 않는다**(후보 D 기각). 카드 높이 340px 고정이 이 저장소의 불변
  전제이므로 2줄 상한은 유지돼야 하고, D 는 말줄임표를 잃어 "잘렸다"는 사실이 화면에서
  사라진다. 이 저장소는 잘림을 반드시 드러내는 관례를 갖고 있다(`PROMPT_TRUNCATION_MARK`,
  `excerptDisplayText`).
- **TC5 — 표준 `line-clamp`(후보 C)는 기각한다.** Chrome 151 에서 3줄 케이스가 54px 로
  **클램프되지 않았다**(계산값도 `clamp=none`). 이 저장소는 CDN·빌드 단계 없는 단일 HTML
  이라 폴리필·전처리기를 쓸 수 없으므로, 브라우저가 실제로 처리하지 못하는 속성은 선택지가
  아니다.

### 2.5 형제 요소 전수 확인 (같은 함정이 더 없는가)

`.card` 의 flex 아이템 6종 전부를 확인했다.

| 자식 | `overflow` | 자동 최소 크기 | 위험 |
|---|---|---|---|
| `.project-head` | 없음 | 콘텐츠 높이 | 안전 |
| `.path` | 없음 | 콘텐츠 높이 | 안전 |
| `.tier1-pct` | 없음 | 콘텐츠 높이 | 안전 |
| **`.tier1-active`** | **`hidden`** | **0** | **결함 — 이번 수정 대상** |
| `.tier1-impl` | 없음 | 콘텐츠 높이 | 안전(사용자가 관측한 대조군 17.25px 이 이 때문이다) |
| `.sessions` | `overflow-y:auto` + **명시적 `min-height:0`** + `flex:1 1 auto` | 0 | **의도된 축소 대상** — 넘치는 세션을 흡수하라고 만든 자리다 |

즉 결함은 `.tier1-active` 한 줄에 격리돼 있고, 축소분은 원래 설계대로 `.sessions` 가
받는다. 수정 후 실측에서도 `.sessions` 높이는 224px → 206px 로 정상 흡수됐다.

---

## 3. 요구 2 — 데이터 소재와 수집 경로

### 3.1 확인된 사실 (설계 단계 재검증 완료)

- 훅 이벤트(`~/.claude/hub/events/*.jsonl`)의 실제 키 분포는 `t·e·s·c` + `so·r·ai·at·p`
  뿐이다(오늘자 110줄 전수). **model·effort 는 없다.**
- Claude Code transcript(`~/.claude/projects/<인코딩>/<session_id>.jsonl`)의 `type:"assistant"`
  줄에 있다:
  - `message.model` — 예: `"claude-opus-5"`
  - **줄 최상위** `effort` — 예: `"xhigh"` (`message` 안이 아니다)

### 3.2 결정 MD1 — 안 B(수집 시 transcript 꼬리 읽기)를 채택한다

| 안 | 판정 | 사유 |
|---|---|---|
| A. 훅이 payload 에서 뽑아 이벤트에 기록 | **기각** | ① 훅 payload 에 model·effort 가 있다는 근거가 없다(Claude Code 훅 payload 는 `session_id`·`transcript_path`·`cwd`·`hook_event_name` 계열이다). ② 있더라도 **새 이벤트부터만** 채워져 기존 세션은 영구히 빈다. ③ 사용자가 `/hub install` 로 훅을 재설치해야 한다. ④ 훅은 "세션을 절대 막지 않는다"가 유일한 절대 규칙인 자리라 일을 늘리는 것 자체가 역행이다. |
| **B. 수집 시 transcript 꼬리 읽기** | **채택** | 즉시 **모든 기존 세션에 소급 적용**된다. 재설치 불필요. 비용은 실측으로 통제 가능(§3.5). |

### 3.3 결정 MD2 — 파일 위치는 디렉토리 스캔 없이 `observed_cwds` 로 직접 조립한다

`hub_project.encode_project_dir_name`(이미 있는 순수 함수)으로 각 `observed_cwds` 를 인코딩해
`PROJECTS_DIR/<인코딩>/<session_id>.jsonl` 후보를 만들고, 먼저 존재하는 것을 쓴다.

- `observed_cwds` **전부**를 후보로 삼는 이유: 워크트리로 이동한 세션은 transcript 디렉토리가
  최초 cwd 기준으로 남는다(결정 WT19 가 이 튜플을 만든 것과 같은 사정). 워크트리가 없는
  프로젝트는 `observed_cwds == (cwd,)` 라 완전한 무동작이다.
- 세션당 `stat` 1~2회뿐이다. `PROJECTS_DIR` 전체 열거(760개)를 하지 않는다.
- `_tier3_activity_by_encoded_name` 의 디렉토리 순회에 얹는 안도 검토했으나 **기각한다** —
  그 함수는 "티어 3 활동 시각"이라는 한 가지 책임을 갖고 있고, 세션→파일 색인을 겸하게 하면
  두 일을 하게 된다. 절약되는 것은 stat 십수 회뿐이다.

**실측 검증**: 최근 2일 이벤트의 세션 42건 중 transcript 가 존재하는 12건을 이 방식이
**12/12 전부** 찾아냈다.

### 3.4 결정 MD3 — 꼬리 128KiB 만 읽고, EOF 에서 역방향으로 첫 유효 assistant 줄을 쓴다

세션 파일은 수십 MB 까지 커진다(실측 최대 19.4MB). 전체를 읽지 않는다.

**상수 근거 (실측)** — 활성 세션 12건의 "EOF 에서 마지막 assistant 줄까지의 바이트 깊이":

| 세션 | 파일 크기 | EOF 로부터의 깊이 |
|---|---|---|
| 1e003839 | 11.5MB | **103,742B (최악)** |
| 9dbd335d | 2.9MB | 94,033B |
| 14872b0e | 8.5MB | 84,230B |
| 08f326ec | 620KB | 47,435B |
| 나머지 8건 | — | 2,305 ~ 11,175B |

`TRANSCRIPT_TAIL_BYTES = 131072`(128KiB)는 실측 최악값의 **1.26배**다. 꼬리 크기별 해결률
실측: 32KiB → 8/12, 64KiB → 9/12, **128KiB → 12/12**, 256KiB → 12/12. 128KiB 가 전건을
해결하는 최소 2의 거듭제곱이다.

**읽기 절차** (I/O 는 `hub_collect`, 판정은 순수 모듈):
1. `size = stat().st_size`; `size > TAIL` 이면 `seek(-TAIL, SEEK_END)`, 아니면 처음부터.
2. `errors="replace"` 로 디코딩한다 — 꼬리 경계에서 멀티바이트가 찢기고, 활성 세션이 동시에
   append 하는 파일이다. `read_rate_limit_capture` 의 검수 M1 선례와 같은 이유:
   `UnicodeDecodeError` 는 `ValueError` 서브클래스라 `except OSError` 를 뚫는다.
3. 줄 단위로 **뒤에서 앞으로** 훑는다. 첫 줄은 잘려 있을 수 있으나 JSON 파싱 실패로 자연히
   탈락한다(별도 처리 불필요).
4. 조건을 만족하는 첫 줄에서 `(model, effort)` 를 **같은 줄에서 함께** 뽑는다 — 서로 다른 줄에서
   뽑으면 모델은 바뀌었는데 effort 는 옛 값인 조합이 나온다.
5. 꼬리 안에 유효한 줄이 없으면 `None`(경고 없음 — 정상 상태다, §3.7).

### 3.5 성능 분석

| 항목 | 실측 |
|---|---|
| 현행 `collect_snapshot` 1회 | **5.9 ~ 7.6 ms** (프로젝트 3 · 세션 21) |
| 추가되는 꼬리 읽기 12건 (128KiB) | **~6.0 ms**, 읽기량 ~1.5MB |
| 예상 수집 1회 총량 | ~12 ms |

**결정 MD4 — 캐시를 두지 않는다(YAGNI).** 근거:

- 수집은 **요청이 이끈다**(개정 2) — 열린 탭의 60초 폴링과, 훅 spawn(5초 쓰로틀)이 전부다.
  상주 서버의 유지보수 티커는 하트비트만 찍고 수집하지 않는다. 즉 최악에도 5초에 1회다.
- 우리가 읽는 파일은 **바로 그 순간 활성 세션이 append 하고 있는 파일**이다 — 정의상 페이지
  캐시에 뜨거운 상태이며, 그래서 1.5MB 가 6ms 에 읽힌다.
- 영속 캐시(`session_models.json` + mtime·size 무효화)는 새 파일·새 스키마·손상 처리·경합
  처리를 전부 데려온다. 6ms 를 아끼려고 그것을 도입하는 것은 이 저장소가 금지하는
  "측정 없는(정확히는, 측정했더니 필요 없는) 최적화"다.
- **에스컬레이션 조건을 명시해 둔다**: `collect_snapshot` 이 50ms 를 넘기 시작하면 그때
  캐시를 설계한다. 그 시점의 판단 근거가 될 수 있도록 위 실측치를 주석에 남긴다.

### 3.6 결정 MD5 — 모델 이름 정규화는 표가 아니라 규칙이다

**하드코딩 표를 만들지 않는다** — 새 모델이 나오면 조용히 깨진다.

**실측된 전체 모델 ID 집합** (transcript 760개 꼬리 전수 조사):

| 원문 ID | 건수 | 표시 |
|---|---|---|
| `claude-fable-5` | 683 | `Fable 5` |
| `claude-opus-5` | 274 | `Opus 5` |
| `claude-opus-4-6` | 262 | `Opus 4.6` |
| `claude-sonnet-5` | 72 | `Sonnet 5` |
| `claude-opus-4-8` | 67 | `Opus 4.8` |
| **`claude-haiku-4-5-20251001`** | 20 | `Haiku 4.5` (날짜 접미 제거) |
| **`<synthetic>`** | 5 | **모델이 아니다 — 거부하고 계속 탐색** |

**정규화 규칙**:
1. `<synthetic>` 이거나 `claude-` 로 시작하지 않으면 → 모델로 인정하지 않는다.
2. `claude-` 를 벗기고 `-` 로 나눈다.
3. 첫 토큰이 **순수 알파벳이 아니면** → 정규화를 포기하고 **원문 ID 를 그대로** 돌려준다
   (구세대 `claude-3-5-sonnet-20241022` 형태 대비). 잘못 줄이는 것보다 못생겨도 정직한 편이 낫다.
4. 나머지 토큰 중 **8자리 전부 숫자**(YYYYMMDD)는 버린다.
5. 남은 숫자 토큰을 `.` 으로 잇는다. → `"{Family} {version}"`, 버전이 없으면 `"{Family}"`.

미지의 미래 모델이 같은 관례를 따르면 자동으로 잘 나오고(`claude-opus-6` → `Opus 6`),
관례를 벗어나면 원문으로 폴백해 **조용히 틀리지 않는다.**

### 3.7 결정 MD6 — 세션에 모델이 여럿 섞이면 **마지막 값**을 쓴다

실측: 한 세션 파일(c1548563)에 `fable-5` 1466건 · `opus-5` 1425건 · `opus-4-8` 10건이 섞여
있었다. `isSidechain` 은 표본 40개 파일 전부에서 0건이었으므로 **서브에이전트 혼입이 아니라
사용자의 세션 중 모델 전환**이다.

- 화면이 답해야 하는 질문은 "이 세션이 **지금** 무엇을 쓰는가"다 → **마지막 assistant 줄**.
- 최빈값은 기각한다 — 방금 Opus 로 바꾼 세션이 한동안 Sonnet 으로 보인다.
- 전부 나열은 기각한다 — 340px 카드에 담을 자리가 없고, 이력은 화면의 질문이 아니다.
- 꼬리를 EOF 에서 역방향으로 훑으므로 "마지막"이 **가장 먼저** 발견된다. 규칙과 구현이 일치한다.

### 3.8 결정 MD7 — 값이 없을 때의 표현

| 상황 | 실측 빈도 | `SessionView.model` | 화면 |
|---|---|---|---|
| transcript 없음 | 최근 2일 세션 42건 중 **30건** | `None` | 아무것도 그리지 않는다 |
| transcript 는 있으나 꼬리에 assistant 줄 없음 | 드묾 | `None` | 아무것도 그리지 않는다 |
| 모델은 있고 `effort` 가 `null` | `claude-opus-4-6` 121건 | `effort=None` | 모델만, `· effort` 생략 |

**transcript 가 없는 30건은 결함이 아니다.** 전수 확인 결과 그 30건은 **예외 없이
`SessionStart`+`SessionEnd` 2건만 있는 세션**이다(비대화형 일회성 기동). 실제로 프롬프트를
주고받은 세션 12건은 **12/12 전부** transcript 를 갖는다. 즉 화면에 의미 있게 보이는 세션의
커버리지는 사실상 100% 다.

`started_at_ms` 주석의 "정체성 필드에 기본값을 두지 않는다"는 관례는 여기에 적용되지
**않는다** — 모델은 정체성 필드가 아니라 **정당하게 부재할 수 있는 부가 정보**다. 그래서
`ProjectView.dashboard_key: str | None = None`·`HubSnapshot.usage: UsageSample | None = None`
과 같은 계열로 취급한다(빈 문자열이 아니라 `None`, 기본값 있음).

### 3.9 결정 MD8 — 표시 위치는 기존 `.session-meta` 줄에 **세 번째 항목**으로 얹는다

**세로 비용 0px.** 새 줄을 만들지 않으므로 카드에 보이는 세션 수가 줄지 않는다.

실측(Chrome 151, 카드 콘텐츠 폭 280px = 최소 트랙 320px − 좌우 padding 40px, 그리고 416px):

| `.session-meta` 내용 | 높이 | 줄바꿈 |
|---|---|---|
| `시작 10:30` + `1fc46114` (현행) | **16.5px** | 1줄 |
| + `Opus 5 · xhigh` | **16.5px** | 1줄 |
| + `Sonnet 5 · high` | 16.5px | 1줄 |
| + `Haiku 4.5 · xhigh` | 16.5px | 1줄 |
| + `Opus 4.6` (effort 없음) | 16.5px | 1줄 |

**즉 증분은 0px 이고, 340px 카드의 세션 3건 표시 능력은 그대로다.**

`.session-line` 이 아니라 `.session-meta` 를 고른 이유: `.session-line` 은 `flex-wrap:wrap` 에
배지·경과시간·에이전트 칩이 이미 접히는 줄이라 항목을 더하면 접힘 거동이 바뀐다.
`.session-meta` 는 `flex-wrap` 이 없는 짧은 식별 줄이고, 모델·effort 는 "이 세션이 무엇인가"를
말하는 식별 정보라 의미상으로도 그쪽이 맞다.

### 3.10 결정 MD9 — 길이 상한은 CSS 가 아니라 JS 가 건다

폭이 넘칠 때 CSS(`text-overflow:ellipsis` + `white-space:nowrap` + `min-width:0`)로 막으려
했으나 **실패한다**: `.session-meta` 는 가로 flex 라 긴 항목이 형제(`시작 10:30`)를 짓눌러
**그쪽이 2줄로 접히며 줄 높이가 16.5px → 33px 로 늘어난다**(실측).

**모델 이름 표시 상한 실측** (280px, 모노스페이스 `M` = 최악 폭):

| 모델 이름 길이 | 줄 높이 |
|---|---|
| 18자 + ` · xhigh` | **16.5px (1줄)** |
| 20자 + ` · xhigh` | 33px (2줄) — 붕괴 |

→ **`MODEL_LABEL_MAX_CHARS = 18`**. 상한을 넘으면 `TRUNCATION_MARK`(`…`)를 붙여 자르고
원문 ID 를 `data-tooltip` 으로 넘긴다 — `renderSessionExcerpt`·`excerptDisplayText` 가 이미
쓰는 저장소 고유 관례를 그대로 재사용한다(새 개념 0개). 정규화가 성공한 이름은 전부
18자 미만이라 이 경로는 §3.6 규칙 3의 원문 폴백에서만 쓰인다.

> **GOTCHA — 요구 1과 같은 함정의 사촌.** `.session-meta` 안에서 `overflow:hidden` 으로 폭을
> 다스리려는 시도는 요구 1과 **같은 계열의 덫**이다(flex 아이템의 자동 최소 크기 0). 세로가
> 아니라 가로라 증상만 다르다. CSS 로 밀지 말고 JS 로 자른다.

### 3.11 결정 MD10 — 접근성

- 표기는 **텍스트**다. 색·글리프에만 의존하는 채널이 없다(`.badge.state-*` 주석의 3채널 관례를
  새로 위반하지 않는다).
- **새 색 토큰을 만들지 않는다.** `.session-meta` 의 `--muted` 를 상속한다
  (`.session-id` 가 이미 같은 선택을 했다).
- 보조기술용 라벨을 붙인다 — `<span class="sr-only">모델 </span>`
  (`.session-id` 의 `<span class="sr-only">세션 ID </span>` 와 같은 형태).
- 글꼴은 `.session-id`·`.agent-chip` 과 같은 모노스페이스 스택을 쓴다 — 버전 숫자(4.5/4.6/4.8)가
  헷갈리면 안 되는 것이 식별자와 같은 사정이다.

---

## 4. 영향 범위

### Phase A — 요구 1 (단독으로 배포 가능)

| 파일 | 조치 | 이유 |
|---|---|---|
| `hub/bin/hub_template.html` | 수정 (CSS 1줄 + 주석) | `.tier1-active` 에 `flex-shrink:0` 추가. TC1~TC2 근거 주석 |
| `tests/run.sh` | 추가 (T25-147·T25-148) | 정/역 회귀 검사 |

**Phase A 는 이것으로 끝이다.** 데이터 계층·문서·설치 스크립트를 건드리지 않는다.

### Phase B — 요구 2

| 파일 | 조치 | 이유 |
|---|---|---|
| `hub/bin/hub_transcript.py` | **신규 (★순수)** | transcript 줄 계약 파싱 + 모델 이름 정규화 |
| `hub/bin/hub_session.py` | 수정 | `SessionView.model` 필드 추가, `compute_session_view` 에 인자 추가 |
| `hub/bin/hub_project.py` | 수정 | `compose_project_views` 가 `model_by_session_id` 를 받아 통과시킨다 |
| `hub/bin/hub_collect.py` | 수정 | I/O — 파일 위치 조립 + 꼬리 읽기 + 실패 흡수 |
| `hub/bin/hub_template.html` | 수정 | `.session-model` CSS + `renderSessionMeta` 확장 + 상수 |
| `hub/install.sh` | 수정 | `HUB_FILE_COUNT=15` → `16` |
| `hub/README.md` | 수정 | 「프라이버시 고지」·「화면 배치」·「파일 배치」 |
| `tests/hub/test_hub_transcript.py` | **신규** | 정규화·꼬리 파싱 단위 테스트 |
| `tests/hub/test_hub_session.py` | 수정 | 새 필드·인자 |
| `tests/hub/test_hub_project.py` | 수정 | `model_by_session_id` 통과 |
| `tests/hub/test_hub_collect.py` | 수정 | 꼬리 읽기·부재·손상 |
| `tests/run.sh` | 추가 (T25-149~T25-152) | 배포 파일 수·데이터 모델·템플릿·문서 정합 |

### 새 모듈을 만드는 이유 (`hub_transcript.py`)

`hub_parse.py` 가 **`/dashboard` 생성물의 DOM 계약** 하나 때문에 독립 모듈로 존재하는 것과
정확히 같은 사정이다 — Claude Code transcript JSONL 은 **우리가 소유하지 않는 외부 파일
형식**이고, 그 계약이 바뀌면 이 모듈 하나만 고치면 된다. `hub_session.py` 에 얹으면 그 모듈이
"훅 이벤트 → 세션 사실"이라는 단일 입력원 계약을 잃는다.

**대가는 명시한다**: 배포 파일 수 15 → 16, `HUB_FILE_COUNT` 와 README 「파일 배치」·
「bin 15개 파일」 서술을 함께 고쳐야 한다(T25-1·T25-2 가 이 정합을 강제한다).

---

## 5. 데이터 모델

### 5.1 신규 — `hub_transcript.py` (★순수)

```python
@dataclass(frozen=True)
class SessionModel:
    """세션이 마지막으로 사용한 모델과 노력 수준. 화면 표시용 투영이다."""

    model_label: str        # 정규화된 표시명. 예: "Opus 5", "Haiku 4.5". 정규화 실패 시 원문 ID
    raw_model_id: str       # 원문. 예: "claude-opus-5". 툴팁·디버깅용
    effort: str | None      # 예: "xhigh". transcript 에 없으면 None
```

`model_label` 과 `raw_model_id` 를 **둘 다** 싣는 이유: 상한(18자)에서 잘렸을 때 툴팁이
보여줄 원문이 필요하고, 정규화가 미래에 잘못 동작해도 원문이 화면에서 사라지지 않는다.

### 5.2 변경 — `hub_session.SessionView`

```python
@dataclass(frozen=True)
class SessionView:
    session_id: str
    short_id: str
    started_at_ms: int
    state: SessionState
    base_state: Literal["working", "idle", "done"]
    last_event_at_ms: int
    task_excerpt: str | None
    agent_runs: tuple[SubagentRunView, ...]
    # ▼ 신규
    model: SessionModel | None = None
```

- **기본값 `None` 을 둔다** — 정체성 필드가 아니라 정당하게 부재하는 부가 정보다(§3.8).
  `started_at_ms` 의 "기본값 금지" 관례와 충돌하지 않는다는 사실을 필드 주석에 명시한다.
- **맨 뒤에 둔다** — 기본값 없는 필드 뒤에 기본값 있는 필드가 와야 한다(dataclass 규칙).
  `ProjectView` 가 `dashboard_key`·`tier1_is_previous_task` 를 뒤에 둔 것과 같은 배치다.
- `snapshot_content_key` 안정성: 모델·effort 는 세션당 준안정 값이라 매 수집마다 바뀌지
  않는다. transcript 가 자라도 마지막 모델이 같으면 키가 같아 `hub.html` 재작성 억제가
  유지된다(결정 D2 불변).

---

## 6. 인터페이스

### 6.1 `hub_transcript.py` (★순수 — 파일시스템·시각·환경변수에 닿지 않는다)

```python
TRANSCRIPT_TAIL_BYTES: int = 131072
SYNTHETIC_MODEL_ID: str = "<synthetic>"
MODEL_ID_PREFIX: str = "claude-"
DATE_SUFFIX_LENGTH: int = 8

def normalize_model_name(raw_model_id: str) -> str | None:
    """모델 ID 를 표시명으로 정규화한다. 모델이 아니면(<synthetic> 등) None.

    정규화할 수 없는 형태는 원문 ID 를 그대로 돌려준다 — 조용히 틀리지 않기 위해서다.
    """

def parse_session_model_from_tail(tail_text: str) -> SessionModel | None:
    """transcript 꼬리에서 마지막 assistant 줄의 (모델, effort)를 뽑는다. 없으면 None.

    뒤에서 앞으로 훑는다 — 꼬리의 첫 줄은 잘려 있을 수 있고, 그 줄은 JSON 파싱 실패로
    자연히 탈락한다. 모델과 effort 는 반드시 같은 줄에서 함께 뽑는다.
    """
```

### 6.2 `hub_collect.py` (I/O)

```python
def read_session_model(session_id: str, observed_cwds: Sequence[str]) -> SessionModel | None:
    """세션의 transcript 꼬리를 읽어 모델·effort 를 판다. 이 함수는 절대 예외를 던지지 않는다."""

def read_session_models(
    sessions_by_path: dict[str, tuple[hub_session.SessionFacts, ...]]
) -> dict[str, SessionModel]:
    """수집 대상 세션 전부의 모델을 모은다. 값을 못 얻은 세션은 키 자체를 넣지 않는다."""
```

### 6.3 변경되는 기존 시그니처

```python
# hub_session.py
def compute_session_view(
    facts: SessionFacts,
    now_ms: int,
    stale_after_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,
    model: SessionModel | None = None,          # ▼ 신규(기본값 있어 기존 호출부 무해)
) -> SessionView: ...

# hub_project.py
def compose_project_views(
    tier1_by_path: dict[str, Tier1Snapshot],
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    tier3_last_activity_by_path: dict[str, int],
    now_ms: int,
    stale_after_ms: int,
    model_by_session_id: dict[str, SessionModel] | None = None,   # ▼ 신규
) -> tuple[ProjectView, ...]: ...
```

두 순수 함수는 **여전히 순수하다** — 딕셔너리를 인자로 받을 뿐 파일을 열지 않는다.
`tier3_last_activity_by_path` 를 이미 이 방식으로 넘기고 있어 새 패턴이 아니다.

### 6.4 템플릿 (`hub_template.html`)

```js
var MODEL_LABEL_MAX_CHARS = 18;   // §3.10 실측 — 20자부터 .session-meta 가 2줄로 붕괴한다
var MODEL_EFFORT_SEPARATOR = ' · ';
var SESSION_MODEL_SR_LABEL = '모델 ';

// 순수 함수 — DOM 에 닿지 않는다. 예: "Opus 5 · xhigh", "Opus 4.6"
function sessionModelLabel(model){ … }

// 세션 모델 칸. model 이 없으면 빈 문자열(줄 자체가 생기지 않는다).
function renderSessionModel(model){ … }
```

`renderSessionMeta` 가 `renderSessionModel(session.model)` 을 **세 번째 항목**으로 덧붙인다.

```css
.session-model{font-family:ui-monospace,monospace;letter-spacing:-.2px}
```

---

## 7. 설계 결정과 근거 (요약표)

| # | 결정 | 근거 / 기각한 대안 |
|---|---|---|
| TC1 | `.tier1-active{…;flex-shrink:0}` | 원인은 blockification 이 아니라 flex 축소. 실제 hub.html 실측 12.63px → 18.00px → **걷힘(2026-09-30)** — 카드 직계 인스턴스 소멸(hub-session-modal-cleanup.md 결정 MX5). TC2 는 유지, 카드 상세보기는 MX9 로 해제 |
| TC2 | `-webkit-box` 계열 선언 유지 | 빼면 3줄이 54px 로 클램프가 사라진다(실측). 죽은 선언으로 오해되기 쉬워 주석+역검사를 둔다 → **걷힘(LM4)** — 대상 `.tier1-active` 소멸(hub-session-row-layout-and-modal-size.md) |
| TC3 | `flex:0 0 auto` 가 아니라 `flex-shrink:0` | 결함과 무관한 `flex-basis`·`flex-grow` 를 건드리지 않는다(수술적 변경) |
| TC4 | 클램프 유지 | 340px 고정 카드의 불변 전제. `max-height` 안은 말줄임표를 잃는다 |
| TC5 | 표준 `line-clamp` 기각 | Chrome 151 에서 클램프되지 않았다(실측). 빌드 단계가 없어 폴리필 불가 |
| MD1 | transcript 꼬리 읽기(안 B) | 안 A 는 payload 근거 없음 + 소급 적용 불가 + 재설치 요구 |
| MD2 | `observed_cwds` 인코딩으로 경로 조립 | 세션당 stat 1~2회. 실측 12/12 적중. 디렉토리 순회 재사용은 책임 혼합이라 기각 |
| MD3 | 꼬리 128KiB 고정 | 실측 최악 깊이 103,742B 의 1.26배. 128KiB 가 전건 해결 최소값 |
| MD4 | 캐시 없음 | 추가 비용 실측 ~6ms. 대상 파일은 정의상 페이지 캐시가 뜨겁다. 50ms 초과 시 재검토 |
| MD5 | 규칙 기반 정규화 + 원문 폴백 | 하드코딩 표는 새 모델에서 조용히 깨진다. `<synthetic>`·날짜 접미 실존 |
| MD6 | 마지막 값 | 세션 중 모델 전환이 실존(실측 3종 혼재). 최빈값·전체 나열 기각 |
| MD7 | 부재는 `None`, 화면에서 생략 | 정체성 필드가 아니다. 의미 있는 세션 커버리지는 실측 12/12 |
| MD8 | `.session-meta` 3번째 항목 | **세로 증분 0px**(실측 16.5px 불변). `.session-line` 은 wrap 거동이 바뀐다 |
| MD9 | JS 상한 18자 + 툴팁 | CSS 로는 형제가 접혀 줄이 2배가 된다(실측). 기존 발췌 관례 재사용 |
| MD10 | 텍스트 채널 + `sr-only` + 새 색 토큰 없음 | 3채널 관례 유지, `.session-id` 선례 |

---

## 8. 테스트 계획

### 8.1 `tests/run.sh` — Phase A

**T25-147 (정, TC1)** — `.tier1-active` 규칙에 `flex-shrink:0` 이 있다.

```
grep -qF '.tier1-active{' … && 그 규칙 본문에 'flex-shrink:0' 포함
```

**T25-148 (역, TC2 — 가장 값진 검사)** — `.tier1-active` 규칙에서 `display:-webkit-box` 와
`-webkit-line-clamp:2` 가 사라지지 않았다. 계산값이 `flow-root` 라는 관측 때문에 "죽은
선언"으로 오해하고 정리하는 것이 이 결함의 **재발 경로**다. 문자열 존재 검사만으로도
그 정리를 막을 수 있다.

**T25-147 보조 (역, §2.5)** — `.card` 의 자식 규칙 중 `overflow:hidden` 을 새로 가지면서
`flex-shrink`/`min-height` 가드가 없는 것이 `.tier1-active` 외에 늘어나지 않았다.
(`.sessions` 는 `min-height:0` 을 가진 의도된 예외로 화이트리스트.)

### 8.2 `tests/run.sh` — Phase B

| 번호 | 방향 | 내용 |
|---|---|---|
| **T25-149** | 정+교차 | `hub/install.sh` 의 `HUB_FILE_COUNT` 가 16 이고 `hub/bin` 실제 파일 수와 일치(T25-1·T25-2 가 이미 강제 — 값만 갱신). `hub/README.md` 「파일 배치」의 파일 수 서술도 16 |
| **T25-150** | 정+역 | `hub_session.py` 에 `model: SessionModel | None = None` 이 있고 **필드 순서가 맨 뒤**다. 역: `hub_transcript.py` 에 `open(`·`Path`·`time.` 이 0건(★순수 계약) |
| **T25-151** | 정+역 | 템플릿에 `.session-model`·`MODEL_LABEL_MAX_CHARS`·`sessionModelLabel`·`renderSessionModel` 이 있다. 역: `.session-model` 규칙에 `#` 색 리터럴 0건(G9) **및 `overflow:hidden` 0건**(§3.10 GOTCHA) |
| **T25-152** | 정+역 | 문서 정합 — `hub/README.md` 「프라이버시 고지」에 transcript 읽기 조항, 「화면 배치」에 모델·effort 서술. 역: 「알려진 한계」에 "transcript 없는 세션은 표시되지 않는다" 조항 |

### 8.3 `tests/hub/test_hub_transcript.py` (신규, 순수 로직 — 가장 값진 단위 테스트)

**`normalize_model_name`** — 표 전체가 실측에서 나온 실제 ID 다.

| 입력 | 기대 | 이유 |
|---|---|---|
| `claude-opus-5` | `Opus 5` | 기본형 |
| `claude-fable-5` | `Fable 5` | 기본형 |
| `claude-sonnet-5` | `Sonnet 5` | 기본형 |
| `claude-opus-4-6` | `Opus 4.6` | 2단 버전 |
| `claude-opus-4-8` | `Opus 4.8` | 2단 버전 |
| `claude-haiku-4-5-20251001` | `Haiku 4.5` | **날짜 접미 제거** |
| `<synthetic>` | `None` | 모델이 아니다 |
| `` (빈 문자열) | `None` | 경계 |
| `claude-opus-6` | `Opus 6` | **미지의 미래 모델이 규칙을 따르는 경우** |
| `claude-newfamily-7-2-20990101` | `Newfamily 7.2` | 미지 + 날짜 |
| `claude-3-5-sonnet-20241022` | `claude-3-5-sonnet-20241022` | **구세대 형태 → 원문 폴백** |
| `gpt-4o` | `None` | `claude-` 접두 아님 |
| `claude-` | `None` | 접두만 있음 |
| `claude-opus` | `Opus` | 버전 토큰 없음 |

**`parse_session_model_from_tail`**

| 케이스 | 입력 | 기대 |
|---|---|---|
| 정상 | assistant 줄 1건 | `SessionModel(model_label="Opus 5", raw_model_id="claude-opus-5", effort="xhigh")` |
| **마지막 값 우선** | opus-5 → fable-5 순서 | `Fable 5` (MD6) |
| **같은 줄에서 뽑는다** | 마지막 줄 model=fable/effort=high, 그 앞 줄 model=opus/effort=xhigh | `(Fable 5, high)` — `(Fable 5, xhigh)` 조합이 나오면 실패 |
| effort 부재 | `effort` 키 없음 | `effort=None` |
| effort 가 `message` 안 | `message.effort` 만 있음 | `effort=None` — 최상위만 본다 |
| `<synthetic>` 건너뛰기 | 마지막이 synthetic, 그 앞이 opus-5 | `Opus 5` |
| **잘린 첫 줄** | 첫 줄이 중간부터 시작 | 무시하고 뒤 줄에서 성공 |
| assistant 줄 없음 | user/attachment 줄만 | `None` |
| 빈 문자열 | `""` | `None` |
| 깨진 JSON 혼재 | 유효 줄 + 깨진 줄 | 유효 줄로 성공 |
| `message` 가 dict 아님 | `"message": "x"` | `None`(예외 없음) |
| `type` 이 assistant 아님 | `type:"user"` 에 model 있음 | `None` — assistant 만 본다 |

### 8.4 `tests/hub/test_hub_collect.py` (I/O)

| 케이스 | 기대 |
|---|---|
| transcript 존재 | 값을 돌려준다 |
| 파일 없음 | `None`, **경고 없음**(정상 상태) |
| 두 번째 `observed_cwd` 에만 존재 | 찾아낸다(워크트리, MD2) |
| 파일 크기 > 128KiB | `seek` 로 꼬리만 읽는다 — 읽은 바이트 수를 검증 |
| 파일 크기 < 128KiB | 처음부터 읽는다(`seek` 예외 없음) |
| 권한 없음(`OSError`) | `None`, 예외를 올리지 않는다 |
| 찢긴 멀티바이트 | `errors="replace"` 로 통과 — `UnicodeDecodeError` 가 새지 않는다 |
| `read_session_models` | 값 없는 세션은 **키 자체가 없다** |

### 8.5 `tests/hub/test_hub_session.py` / `test_hub_project.py`

- `compute_session_view(…)` 를 `model` 없이 호출하면 `view.model is None`(기존 호출부 무해).
- `compose_project_views` 가 `model_by_session_id` 의 값을 **해당 session_id 의 뷰에만** 싣는다.
- `snapshot_content_key` — 모델이 같으면 키가 같고, 모델이 바뀌면 키가 바뀐다.

### 8.6 브라우저 실측 (메인 세션 담당 — `tests/run.sh` 로는 불가)

`tests/run.sh` 는 CSS 를 **문자열로만** 검사할 수 있다. 아래는 메인 세션이 브라우저로 확인한다.

- [ ] 티어 1 활성 단계 1줄 텍스트의 아랫부분이 잘리지 않는다(세션이 여러 건 쌓인 카드에서)
- [ ] 3줄 이상 텍스트가 2줄 + `…` 로 잘린다
- [ ] 카드 높이 340px·그리드 열 수가 불변
- [ ] 세션 줄에 모델·effort 가 보이고, `.session-meta` 가 1줄을 유지한다
- [ ] 모델이 없는 세션(비대화형)은 그 칸이 비고 레이아웃이 흔들리지 않는다
- [ ] 다크 테마에서도 대비가 유지된다

---

## 9. 경계 조건 표

| # | 상황 | 동작 |
|---|---|---|
| E1 | 티어 1 활성 단계가 없다 | `renderTier1ActiveStep` 이 `''` — `.tier1-active` 자체가 없다. Phase A 무관 |
| E2 | 활성 단계 텍스트가 정확히 2줄 | 36px, 잘리지 않는다, 말줄임표 없음 |
| E3 | 카드에 세션이 0건 | 카드가 넘치지 않아 축소가 애초에 없다 — 수정 전에도 정상이던 경우 |
| E4 | 세션이 10건 이상 | `.sessions` 가 축소를 전부 흡수, `.tier1-active` 는 18/36px 고정 |
| E5 | transcript 파일 없음 | `model=None`, 화면에서 생략, 경고 없음 |
| E6 | transcript 가 1464B 스텁(assistant 줄 0) | `None` (실측 30/42 세션이 이 경우) |
| E7 | 꼬리 128KiB 안에 assistant 줄이 없다 | `None` — 더 읽지 않는다(상한이 곧 예산이다) |
| E8 | 세션 중 모델 전환 | 마지막 값(MD6) |
| E9 | `effort` 가 `null` | 모델만 표시, `· xhigh` 생략 |
| E10 | 미지의 모델 ID | 규칙으로 정규화 시도 → 실패 시 원문, 18자 초과면 `…`+툴팁 |
| E11 | `<synthetic>` 만 있는 꼬리 | 건너뛰고 계속 탐색, 끝까지 없으면 `None` |
| E12 | transcript 를 읽는 도중 세션이 append | 꼬리 첫 줄이 찢겨도 JSON 파싱 실패로 탈락, 뒤 줄로 성공 |
| E13 | 워크트리로 이동한 세션 | `observed_cwds` 전부를 후보로 시도(MD2) |
| E14 | 같은 세션 ID 의 파일이 두 디렉토리에 | 먼저 발견한 것을 쓴다(결정적: `observed_cwds` 순서) |
| E15 | `PROJECTS_DIR` 자체가 없다 | 전 세션 `None`, 수집은 정상 완료 |

> → **전제 변화(2026-09-30 실측)** — E13 의 이유(「transcript 디렉토리가 최초 cwd 기준으로 남는다」)는 더 이상 사실이 아니다: 호스트는 워크트리
> 진입 때 세션 기록 파일(과 `<session>/` 디렉토리)을 **새 cwd 의 프로젝트 폴더로 옮긴다**(`relocated` 메타 줄). 「`observed_cwds` 전부를 후보로
> 시도하고 먼저 존재하는 것을 쓴다」는 규칙 자체는 그대로 맞다 — 옮긴 뒤의 폴더도 후보에 있기 때문이다(재개 요약을 읽는 창도 같은 규칙을 쓴다,
> hub-agent-title-and-excerpt-freshness.md 결정 TF9).

---

## 10. GOTCHA

1. **`display:-webkit-box` 는 죽은 선언이 아니다.** 계산값이 `flow-root` 로 나와서 그렇게
   보이지만, 빼면 클램프가 사라진다(실측 54px). 정리하지 마라 — T25-148 이 막는다.
2. **원인은 blockification 이 아니라 flex 축소다.** 착수 시점의 가설과 다르다. `display` 를
   되돌리려는 시도(`!important` 등)는 원리적으로 무효다 — blockification 은 캐스케이드
   **이후** 레이아웃 단계에서 적용된다. 고칠 곳은 `flex-shrink` 다.
3. **`.session-meta` 폭 제어를 CSS 로 하지 마라.** 가로 flex 에서 긴 항목이 형제를 짓눌러
   `시작 10:30` 이 2줄로 접히고 줄 높이가 16.5 → 33px 가 된다. JS 상한(MD9)을 써라.
4. **`effort` 는 `message` 안이 아니라 줄 최상위에 있다.** `message.effort` 를 읽으면
   전 세션이 조용히 `None` 이 된다.
5. **model 과 effort 는 반드시 같은 줄에서 뽑아라.** 따로 뽑으면 전환 직후 잘못된 조합이 뜬다.
6. **꼬리를 앞에서 뒤로 훑지 마라.** MD6(마지막 값)이 깨지고, 잘린 첫 줄 처리도 복잡해진다.
7. **`errors="replace"` 를 빼지 마라.** `UnicodeDecodeError` 는 `ValueError` 서브클래스라
   `except OSError` 를 뚫는다(`read_rate_limit_capture` 검수 M1 과 같은 함정).
8. **`SessionView` 의 새 필드는 반드시 맨 뒤**여야 한다 — 기본값 없는 필드 앞에 두면
   dataclass 정의 자체가 `TypeError` 로 죽는다.
9. **`HUB_FILE_COUNT` 를 잊지 마라.** 15 → 16. T25-1·T25-2 가 즉시 실패하므로 조용히
   넘어가지는 않지만, README 「파일 배치」의 서술은 사람이 고쳐야 한다.
10. **`hub_transcript.py` 를 오염시키지 마라.** `open()`·`Path`·`time` 을 넣는 순간
    `tests/hub/` 의 ★순수 전제가 깨진다. 파일 접근은 전부 `hub_collect.py` 다.
11. **`template_stamp` 는 추가 조치가 필요 없다.** `read_template_stamp()` 가 매 수집마다
    `hub_template.html` 바이트를 다시 해시하므로(메모이즈 없음), 템플릿을 고치면 열린 탭이
    스스로 리로드한다(결정 SH3). 다만 **`hub/install.sh` 재실행으로 배포본을 갱신해야**
    그 스탬프가 바뀐다.

---

## 11. 문서 정합 체크리스트

| 문서 | Phase | 반영할 것 |
|---|---|---|
| `hub/README.md` 「프라이버시 고지」 | B | **새 항목** — 허브가 `~/.claude/projects/*/*.jsonl`(Claude Code transcript)의 **꼬리 128KiB** 를 수집 시 읽는다. 읽는 값은 **모델 ID 와 effort 뿐**이고 대화 내용은 읽지 않으며 어디에도 저장하지 않는다. 이미 존재하는 파일을 읽기만 한다(새로 만들거나 늘리지 않는다) |
| `hub/README.md` 「화면 배치」 | B | 세션 식별 줄(시작 시각·short_id) 서술에 **모델·effort** 를 추가. 없는 세션은 그 칸이 빈다는 점 명시 |
| `hub/README.md` 「알려진 한계」 | B | transcript 가 없는 세션(비대화형 일회성 기동)은 모델이 표시되지 않는다 |
| `hub/README.md` 「파일 배치」 | B | `bin/` 15개 → **16개**, `hub_transcript.py` 언급 |
| `hub/install.sh` | B | `HUB_FILE_COUNT=16` |
| `README.md`(루트) | — | **불필요.** 허브 내부 구조를 서술하지 않는다(`hub/README.md` 로 위임). 단 320행의 "설계 문서 38개"는 이 PRP 추가로 39개가 되므로 확인할 것 |
| `commands/hub.md` | — | **불필요.** 설치 동의 문구는 프롬프트 발췌 500자에 대한 것이고, 이번 변경은 새로 **기록**하는 것이 없다. 단 「프라이버시 고지」를 인용하는 문장이 있으면 교차 확인 |
| `hub/bin/hub_template.html` 머리 주석 | A·B | `.tier1-active` 결함 이력(TC1~TC2)과 `.session-model` 조항 |

> `README.md`·`commands/hub.md` 는 **판단 결과 불필요**로 결론지었다. 구현 시 실제 문자열을
> 확인하고, 어긋나면 PRP 수정을 먼저 제안한다.

---

## 12. 구현 순서 (두 요구는 분리한다)

### Phase A — 요구 1 (독립, 먼저 배포 가능)

1. `hub_template.html:250` 의 `.tier1-active` 규칙 끝에 `flex-shrink:0` 추가
   → **검증**: 규칙 문자열에 `flex-shrink:0`·`-webkit-box`·`-webkit-line-clamp:2` 가 모두 있다
2. 결함 이력 주석 작성(계산값 `flow-root` 는 무해하다 · 원인은 flex 축소 · 실측 12.63→18.00px)
   → **검증**: 주석에 실측 수치와 "flex 축소" 가 들어 있다
3. `tests/run.sh` T25-147·T25-148 추가
   → **검증**: `tests/run.sh` 통과. 일부러 `flex-shrink:0` 을 지우면 T25-147 이 실패한다
4. `hub/install.sh` 재실행 후 브라우저 실측(§8.6 앞 3항목)

**Phase A 는 여기서 완결된다. Phase B 없이 커밋·배포해도 안전하다.**

### Phase B — 요구 2

5. `hub_transcript.py` 신규 (★순수) + `tests/hub/test_hub_transcript.py`
   → **검증**: 단위 테스트 전건 통과. 모듈에 `open(`·`Path`·`time.` 0건
6. `hub_session.py` — `SessionView.model` + `compute_session_view` 인자
   → **검증**: `tests/hub/test_hub_session.py` 통과. 인자 없는 호출이 여전히 동작
7. `hub_project.py` — `compose_project_views` 인자 통과
   → **검증**: `tests/hub/test_hub_project.py` 통과
8. `hub_collect.py` — `read_session_model`·`read_session_models` + `collect_snapshot` 배선
   → **검증**: `tests/hub/test_hub_collect.py` 통과. `collect_snapshot` 실측 < 50ms
9. `hub_template.html` — `.session-model` CSS + 상수 + `renderSessionModel` + `renderSessionMeta`
   → **검증**: T25-151 통과
10. `hub/install.sh` `HUB_FILE_COUNT=16` + `hub/README.md` 3개 절 + T25-149·T25-150·T25-152
    → **검증**: `tests/run.sh` 전체 통과
11. `hub/install.sh` 재실행 후 브라우저 실측(§8.6 뒤 3항목)

### 검증 명령

```bash
tests/run.sh                                  # 전체 (T22-* · T25-* 포함)
python3 -m pytest tests/hub/ -q               # 허브 순수 로직 단위 테스트
python3 -m mypy hub/bin/                      # 타입 체크
python3 -m ruff check hub/bin/ tests/hub/     # lint
bash hub/install.sh                           # 배포본 갱신(template_stamp 세대 갱신)
```

> 구현자는 위 명령이 이 저장소에서 실제로 쓰이는 형태인지 먼저 확인한다
> (`.mypy_cache`·`.ruff_cache`·`.pytest_cache` 의 존재로 세 도구 사용은 확인했으나,
> 정확한 인자는 `tests/run.sh` 안의 호출부를 정본으로 삼는다).

---

## 13. 리스크와 대안

| # | 리스크 | 영향 | 완화 |
|---|---|---|---|
| R1 | Claude Code 가 transcript 스키마를 바꾼다(`effort` 위치·`message.model` 키) | 모델 칸이 조용히 빈다 | 부재는 `None` 으로 안전하게 흡수돼 **화면이 깨지지 않는다**. 계약을 `hub_transcript.py` 한 곳에 격리했다. 단위 테스트 표가 회귀 시점을 알려 준다 |
| R2 | 브라우저가 `-webkit-line-clamp` 지원을 끊는다 | 3줄 이상이 잘리지 않고 카드 밖으로 나간다 | `.card` 의 `overflow:hidden` 이 최종 방어선이라 레이아웃은 붕괴하지 않는다. 표준 `line-clamp` 가 실제로 동작하게 되면 그때 교체(TC5 재검토 조건) |
| R3 | 세션 수가 크게 늘어 꼬리 읽기가 비싸진다 | 수집 지연 | 세션당 128KiB 상한이 곧 예산이다(선형·유계). 50ms 초과 시 캐시 도입(MD4 에 조건 명시) |
| R4 | transcript 를 읽는 것이 프라이버시 기대와 어긋난다 | 신뢰 문제 | 「프라이버시 고지」에 명시(§11). 읽는 값은 모델 ID·effort 뿐이고 저장하지 않는다. **필요하면 `config.json` 스위치를 추가**할 수 있으나, 지금은 요청되지 않았고 `show_usage_panel` 처럼 실제 요구가 생기면 그때 만든다(YAGNI) |
| R5 | `HUB_FILE_COUNT`·README 갱신 누락 | 테스트 실패 | T25-1·T25-2 가 즉시 잡는다. §11 체크리스트 |

### 검토했으나 채택하지 않은 대안

- **대안 1 — 요구 1을 `.tier1-active` 를 래퍼 `<div>` 로 감싸 해결한다.** 실측상 동작한다
  (래퍼가 flex 아이템이 되고 안쪽은 축소를 면한다). 기각 이유: DOM 을 늘리고
  `renderTier1` 의 반환 구조를 바꿔야 하는데, **CSS 한 속성으로 끝나는 문제**다. 게다가
  래퍼는 `overflow` 가 없어 자동 최소 크기가 콘텐츠 높이가 되므로 340px 예산을 조용히
  더 먹는다.
- **대안 2 — 요구 2를 `hub_hook.py` 가 `transcript_path` 를 이벤트에 기록하는 방식으로.**
  훅 payload 에 `transcript_path` 는 실제로 있다. 기각 이유: 경로를 알아도 **model·effort 는
  여전히 그 파일을 읽어야** 나오므로 안 B 의 읽기 비용이 전혀 줄지 않는다. 줄어드는 것은
  경로 조립뿐인데 그건 이미 stat 1~2회다(MD2, 실측 12/12 적중). 훅에 필드를 늘리는 대가
  (재설치 요구·기존 세션 미소급)만 남는다.
- **대안 3 — 모델 표기를 원문 ID 그대로.** 기각: `claude-haiku-4-5-20251001` 은 26자로
  §3.10 실측 상한(18자)을 훌쩍 넘겨 `.session-meta` 를 2줄로 붕괴시킨다. 정규화는 미관이
  아니라 레이아웃 요건이다.
