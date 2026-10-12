# `/dashboard` 설계 근거 — 이관 문서

> `commands/dashboard.md` 슬림화(PRP: [`dashboard-md-slimming.md`](./dashboard-md-slimming.md))
> 과정에서 옮겨온 "왜 이 설계인가" 서술을 모은 문서다. 절차·표·폐쇄 어휘·"지우지 마라" 경고는
> 옮기지 않는다 — 이 문서를 열지 않아도 `/dashboard`를 정확히 수행할 수 있어야 하기 때문이다.
> 여기 있는 내용은 전부 "왜 그렇게 설계했는지 궁금할 때"만 필요하다.
>
> 각 절의 원래 위치에는 한 줄 요약과 이 문서로의 링크가 남아 있다
> ([`commands/dashboard.md`](../../commands/dashboard.md) 참조).

<a id="init-recreate"></a>
## init — 매번 새로 만드는 이유

`init`은 언제나 대시보드를 처음부터 새로 만든다. 기존 `.claude/dashboard.html`이 있으면
로그를 포함해 전부 버리고 이번 인자로 새로 그린다. 오케스트레이터에게는 "새 메인 세션인지 같은
세션의 다음 작업인지"를 구분할 수단이 없고 — `init` 호출 자체가 유일한 신호다 — 이 파일은
기능 단위로 만들고 끝나면 지우는 임시 산출물이다. 그래서 존재 여부로 분기하지 않는다.

다만 **다른 세션이 지금 쓰고 있을 수 있는 대시보드**는 조용히 지우지 않는다 — 0단계가 그 경우만
골라내 확인을 받는다. 그 외(파일 없음 · 30분 이상 방치 · 내가 발행한 것)에는 종전과 정확히 같이
동작한다.

<a id="step-anchor"></a>
## step — 결정적 grep 앵커로 통일한 이유

기존 절차는 대상 줄의 전문을 LLM이 "알고 있다"고 가정했다. 칸이 16개로 늘면 줄 전문을
기억한다는 가정이 자주 깨진다. 그래서 `log`가 이미 검증한 **grep 앵커** 방식으로
두 분기(선형/그룹)를 통일한다.

<a id="dataport-token"></a>
## data-server-port · data-owner-token — 왜 새 행이 아닌가

`data-server-port`가 `#dz-log` 행의 하위 개념인 이유: `log` 절차가 어차피 매번 grep 하는
`#dz-log` 여는 태그에 얹혀 있어야 `log commit`의 자동 종료가 Bash 호출을 추가하지 않는다.

`data-owner-token`도 같은 이유로 `#dz-log` 행에 얹혀 있다 — `data-server-port`와 **같은 줄**에
있어야 `step`·`impl`이 grep 패턴 하나(`-e 'id="dz-log"'`)만 더해 소유권을 확인할 수 있고,
**Bash 호출은 한 번도 늘지 않는다**.

<a id="poll-contract"></a>
## 폴링 동기화 계약

이 표는 템플릿의 폴링 스크립트와 DOM 사이의 계약이며, 절차 문서 쪽에서 이 표를 조회하는
절차는 없다(스크립트 자체가 이미 이 계약대로 동작한다).

| 대상 | 동기화 연산 | 근거 |
|------|------------|------|
| `#dz-title` · `#dz-progress-pct` · `#dz-updated` | `textContent` 대입 | 순수 텍스트 노드 |
| `#dz-progress-bar` | `style` 속성 대입 | 인라인 `width:N%` 만 바뀐다. 속성 대입이라 CSS transition 이 살아 있다 |
| `#dz-steps, #dz-matrix` (둘 중 존재하는 것) | `outerHTML` 대입 | **선형/매트릭스 분기를 하나의 연산으로 흡수**한다. 한 파일에 하나만 존재한다는 불변식 1 덕분에 셀렉터 하나로 족하다 |
| `#dz-log` | `innerHTML` 대입 | 항목 prepend·`<details open>` 회수까지 파일이 곧 정답이다. **여는 태그의 속성(`data-server-port`)은 `innerHTML` 대입 대상이 아니어서 폴링이 건드리지 않는다** — 라이브 DOM 의 값은 파일보다 낡을 수 있으며, 그래도 되는 이유는 불변식 8 이다 |
| `input[name="dzf"]` · `label[for^="dzf-"]` · `<style>` | **치환하지 않는다** | 라디오를 재삽입하면 사용자가 고른 유형 필터가 1분마다 초기화된다 |
| `#dz-pip-btn` · `#dz-pip-hint` · `#dz-theme-toggle` | **치환하지 않는다** | `.wrap` 바깥 = 동기화 영역 밖 |
| `#dz-project-name` | **치환하지 않는다** | `.wrap` 바깥 = 동기화 영역 밖 + `init` 이 1회만 쓰고 이후 불변 |
| `#dz-impl-card` | `outerHTML` 대입 | 카드 안에 라디오·`<details>` 같은 **사용자 상태가 하나도 없어** 통째 교체가 안전하다. 항목·카운터를 따로 동기화하면 함수가 둘로 늘고, 목록 길이가 바뀌는 `impl set` 순간을 별도로 처리해야 한다 |
| `<html data-theme>` | **치환하지 않는다** | 테마는 별도 IIFE 와 `localStorage`·`storage` 이벤트가 관리한다. 폴링은 `fresh` 문서(파싱만 된 오프스크린 DOM)를 참조할 뿐 `<html>` 자체를 교체하지 않는다 |

**동기화 단위는 "파일 전체 문자열"이다.** 직전 폴링에서 받은 HTML과 **문자열이 같으면 아무것도
하지 않는다.** 라이브 DOM과 비교하지 않는 이유: 사용자가 `<details>`를 손으로 펼치면 라이브 DOM은
파일과 달라지고, 라이브 비교 방식은 그 펼침을 1분마다 되접는다.

<a id="log-ui"></a>
## 로그 UI 규격 — 접기와 필터

### 접기

`<details>`/`<summary>` 로 요약 한 줄과 상세를 분리한다. `.lead`는 1줄로 자른다
(`overflow:hidden; text-overflow:ellipsis; white-space:nowrap`). `.detail`은 펼쳤을 때
줄바꿈을 허용한다.

### 필터 — JS 없이 CSS로

라디오를 `#dz-log`의 **앞 형제**(같은 부모의 직전 형제들)로 두고 `~` 결합자로 제어한다.
래퍼 `div`로 감싸면 `~` 결합자가 `#dz-log`에 닿지 않으므로 감싸지 않는다. 라디오·라벨·
`#dz-log`는 모두 `.card`의 직계 형제여야 하며, `display:contents`로도 우회할 수 없다 —
형제 결합자는 박스 트리가 아니라 DOM 트리로 판정하기 때문이다. 라디오 그룹은 유형 필터
(`name="dzf"`, 전체/구현/검수) 하나뿐이며 템플릿에 고정 3개다.

```html
<div class="log-title">작업 추적</div>
<input type="radio" name="dzf" id="dzf-all" class="dzf" checked><label for="dzf-all">전체</label>
<input type="radio" name="dzf" id="dzf-impl" class="dzf"><label for="dzf-impl">구현</label>
<input type="radio" name="dzf" id="dzf-review" class="dzf"><label for="dzf-review">검수</label>
<ul class="log" id="dz-log" data-server-port="">…</ul>
```

```css
/* 유형 필터 — 템플릿 고정 */
.dzf{position:absolute;opacity:0;pointer-events:none}
#dzf-impl:checked   ~ #dz-log .entry:not([data-kind="impl"]){display:none}
#dzf-review:checked ~ #dz-log .entry:not([data-kind="review"]){display:none}
```

라디오는 시각적으로 숨기되 포커스는 유지한다(`display:none`이 아니라 `opacity:0`).
`:has()` 같은 최신 셀렉터에 의존하지 않으므로 지원 범위가 넓다. 유형 필터는 알약(pill)
형태다.

색 토큰의 정본은 `hub/bin/hub_template.html`이며 그 값을 그대로 쓴다. 골격·단계 리스트 스타일은
원본(`~/Desktop/dashboard.html`)에서 유래한 구조를 그대로 유지한다.

<a id="matrix-css"></a>
## 매트릭스 CSS

`.chip` 규칙 바로 뒤, `.badge` 규칙 앞에 있다. **새 색 토큰을 만들지 않는다** — 상태별 색쌍은
기존 `.chip`/`.num`이 쓰던 것과 글자 하나까지 동일하다.

```css
  table.matrix{width:100%;border-collapse:collapse;margin:14px 0 0;font-size:14px}
  .matrix th,.matrix td{border:1px solid var(--line);padding:9px 10px}
  .matrix thead th{font-size:12px;font-weight:800;background:var(--soft);color:var(--muted);text-align:center}
  .matrix th.corner{text-align:left}
  .matrix th.group{text-align:left;font-weight:700;color:var(--head);width:34%}
  .matrix td.cell{text-align:center;font-size:12px;font-weight:800;background:var(--soft);color:var(--muted)}
  .matrix td.cell[data-state="done"]{background:var(--accent-soft);color:var(--accent-ink);box-shadow:inset 0 0 0 1px var(--accent)}
  .matrix td.cell[data-state="active"]{background:var(--accent-ink);color:var(--bg)}
  .matrix td.cell[data-state="na"]{background:var(--surface);color:var(--line)}
```

`wait`에는 규칙이 없다 — `td.cell` 기본값이 곧 대기 상태다(선형 분기에서 `li` 기본값이 대기인
것과 같은 구조). 이 CSS는 선형 세션에서는 매칭 대상이 없어 아무 일도 하지 않는다.

<a id="wrap-outside"></a>
## 정적 요소 추가 — 왜 .wrap 바깥인가

플로팅은 `.wrap` 서브트리를 **통째로 PiP 창으로 옮기는** 방식이다. 헤더가 `.wrap` 안에 있으면
같이 옮겨가 (a) 좁은 창을 차지하고 (b) opener에는 창을 닫을 수단이 남지 않는다. 헤더가
프로젝트 명 행으로 바뀌어도 이 배치는 그대로이며, **T22-37이 `.wrap` 범위 밖 판정으로 강제**한다
(단순 줄 번호 "뒤" 비교에서, `.wrap` 앞뒤 어느 배치든 안쪽 범위만 배제하는 방식으로 일반화했다).

<a id="pip-height"></a>
## 갱신 모드 — PiP 창 높이 측정

창 높이는 고정값이 아니다. 압축 뷰는 작업 추적 카드가 빠져 콘텐츠가 짧으므로,
`measureCompactHeight()`가 여는 시점에 `.wrap`을 `body.dz-pip` 상태로 순간 측정해 그 실제
높이(+24px 여백 +`PIP_CHROME_ALLOWANCE` 창 여백)를 PiP 창을 여는 호출의 초기 크기로 넘긴다.
`PIP_MIN_HEIGHT`~`PIP_MAX_HEIGHT`(200~720)로 클램프한다. 열린 뒤의 `resizePipToFit()`는
Document PiP의 `resizeTo()`가 사용자 제스처를 요구해(실측: `NotAllowedError`) rAF·폴링에서
호출하면 대개 조용히 실패한다 — 그래서 정확한 크기는 여는 시점 한 번에 정해진다.

<a id="inv8"></a>
## 불변식 8 — 정당화

`syncLog`가 `innerHTML`만 대입하므로 라이브 DOM의 값은 파일과 어긋날 수 있다. 이 속성에
의존하는 JS를 추가하는 순간 "낡은 화면 값"과 "파일의 참값"이 갈라지고, 같은 정보의 출처가
둘이 된다. 파일이 유일한 정답이다.

<a id="inv9"></a>
## 불변식 9 — 정당화

불변식 8과 같은 이유이며 보호 장치도 같다 — `syncLog`가 `innerHTML`만 대입하므로 여는 태그의
속성은 폴링 대상이 아니다. 라이브 DOM의 값이 파일보다 낡아도 무해한 이유는, 이 값을 읽는
유일한 주체가 **파일을 직접 grep하는 오케스트레이터**이기 때문이다. 이 속성에 의존하는 JS를
추가하는 순간 같은 정보의 출처가 둘이 된다.

<a id="inv10"></a>
## 불변식 10 — 정당화

이유는 하나다 — 컨테이너의 `white-space:pre-wrap`이 태그 사이 공백을 **보존**하므로, 개행을
넣으면 문단 사이에 의도하지 않은 빈 줄이 샌다. 불변식 3(`.step-detail`에 줄바꿈 금지)과 목적은
같고 대상이 다르다.

**블록 텍스트 *안*의 단일 개행은 보존한다.** 빈 줄이 아닌 개행으로 줄을 나눈 상세는 한 블록으로
남고(PRP §3.2 3단계), 그 개행은 `pre-wrap`이 그대로 보여준다 — 이것이 `white-space`를 `normal`로
바꾸지 않은 이유이기도 하다(PRP §3.3 기각표). 접어서 공백으로 만들면 기존 다중 줄 상세가 조용히
재배치되고 PRP §3.2의 후방 호환 불변식이 거짓이 된다.

따라서 **로그 항목의 줄 수는 고정되지 않는다.** 상세가 여러 줄이면 항목도 그만큼 길어지고,
`log` 0-c의 `limit=120` 재Read 분기는 계속 실제 경로다(PRP §8.4).

<a id="log-seq"></a>
## log — data-seq 앵커를 쓰는 이유

`data-seq`는 항상 증가하는 순서로 로그 맨 앞에 prepend되므로, 최댓값과 `S-2` 항목은 로그
길이와 무관하게 항상 맨 앞부분에 있다. 파일 전체를 Read할 필요가 없어, 세션이 길어져 로그가
수십~수백 건으로 늘어나도 이 단계의 비용은 늘지 않는다(기존 설계가 안고 있던 "가변 비용" 문제
해결).

<a id="autopublish"></a>
## 자동 발행 — URL 표기와 열기 대상 확정의 근거

스캔은 `127.0.0.1`로 확인하고 안내는 `localhost`로 한다. 스캔은 **바인딩한 그 주소**를 정확히
찔러야 하고, 사용자 대면 URL은 `serve` 5단계가 이미 쓰던 표기와 같아야 하기 때문이다.
브라우저에서 `localhost`가 안 열리면 `http://127.0.0.1:{포트}/dashboard.html`을 안내한다.

3번(URL 확정과 포트 각인)이 확정한 것은 **대시보드 URL**(보고·각인용)이다. 3-a는 **브라우저로
열 URL**만 따로 정한다. 통합 허브(`/hub`) 서버가 살아 있으면 프로젝트 대시보드 대신 **허브
페이지**를 연다 — 허브에서 이 프로젝트 카드를 클릭하면 같은 대시보드가 상세 패널로 열리므로,
여러 프로젝트를 함께 보는 화면이 진입점이 되는 편이 낫다.

허브 페이지를 열거나 새로고침하면 그 자리에서 반영된다(허브가 요청 시 수집한다). **강제 수집을
부르지 않는다** — 허브 상주 서버가 스스로 따라잡는다.

**브라우저 열기는 티어와 직교한다.** 티어 1·2 어느 쪽이든 열기 대상 URL에 대해 「브라우저
열기」를 시도하고, 그마저 불가능하면 URL을 출력해 사용자가 직접 열게 한다. 즉 최악의 결과가
**현재 동작과 정확히 같다** — 이 기능은 어떤 환경에서도 기존 경험을 나쁘게 만들지 않는다.

허브 생존 판정이 실패하거나 예상치 못한 출력이 나오면 `NOHUB`로 본다 — 이 단계의 어떤 실패도
`init`을 중단시키지 않으며, 실패하면 변경 전과 정확히 같은 동작이 남는다. 로컬 서버 기동과
포트 각인은 이 판정과 무관하게 그대로 수행한다 — 허브 상세 패널은 디스크의
`.claude/dashboard.html`을 허브 서버가 직접 읽어 서빙하므로 로컬 서버와 무관하고, 로컬 서버는
여전히 플로팅 창·단독 탭 열람·`log commit`의 자동 종료에 쓰인다.

브라우저 열기 시도의 성공 여부는 **깊이 판정하지 않는다.** 종료 코드가 0이 아니면 열지 못한
것으로 보고 넘어간다. 브라우저가 실제로 떴는지 확인할 방법은 없고, 확인하려 들면 절차가
비결정적이 된다.

포트 각인 절차는 `data-owner-token`을 읽지도 바꾸지도 않는다 — `old_string`이 grep으로 읽은
줄 전문이므로 토큰은 그대로 보존된다(불변식 9).

<a id="gate-convention"></a>
## 열 확정 규칙 — 게이트 배치 관례

관례(강제 아님): 게이트처럼 단계가 1개인 그룹은 인자 목록 맨 뒤에 둔다. 그래야 그 그룹만의
고유 열이 표의 오른쪽 끝에 생겨 `na` 칸이 한곳에 모인다.

<a id="report-min"></a>
## 보고 최소화 — 왜 침묵이 기본값인가

절차 서사("이번 세션이 발행한 대시보드이므로 묻지 않고 진행합니다" 류)는 사용자가 그 정보로
당장 취할 행동이 없다 — 판정은 이미 끝났고 되돌릴 선택지도 없다. 토큰 절감도 근거가 못
된다: 응답 프로즈가 세션 전체 지출에서 차지하는 비중은 실측상 몇 % 대에 불과하므로, 서사
몇 줄을 줄이는 효과는 세션 전체 지출의 0.05% 에도 못 미친다. 그래서 이 절의 목적은 비용
절감이 아니라 **응답 청결**이다 — 매 호출마다 같은 절차 설명이 반복되면 사용자가 실제로
필요한 신호(URL·토큰·실패 사유)를 서사 속에서 걸러내야 한다.

토큰을 URL 과 같은 줄에 싣는 이유는 비용이 아니라 **생존**이다. 소유 토큰의 유일한 사본은
대화 컨텍스트뿐이다 — 파일에는 8자리 hex 로만 남고, 세션이 compact 되면 응답에 없던 값은
요약에서 사라진다. 사라지면 이후 `step`·`log`·`impl` 의
[소유권 검증](../../commands/dashboard.md#소유권-검증--step--log--impl-의-공통-0단계)이
"이 세션에 토큰이 없다"로 판정해 `SKIP` 으로 강등되고, `FOREIGN` 오염을 잡아내는 안전장치가
그만큼 무력해진다.

`serve`·`log commit`·예외 경로(`NOTEMPLATE`·`ANCHOR-FAIL`·`FOREIGN`·`SKIP`·포트 스캔 `NONE`·
0단계 확인 질문)의 보고는 이 절과 무관하게 남긴다. `serve` 는 사용자가 명시적으로 부르는
opt-in 명령이라 응답 자체가 그 호출의 결과물이고, `log commit` 의 서버 종료 보고는 pkill
종료 코드에 따라 문구가 갈리는 **사실성 보고**다 — "종료했습니다"와 "이미 꺼져 있었습니다"는
사용자에게 다른 의미다. 예외 경로 보고는 판정 결과를 알려야만 사용자가 다음 행동(재발행·
`/dashboard off` 등)을 고를 수 있는 경우들이라, 침묵이 오히려 정보 손실이다.

<a id="lead-tooltip"></a>
## `.lead` 툴팁 — 왜 각인이 아니라 런타임 감지인가

작업 추적 항목 제목(`.entry .lead`)은 `text-overflow:ellipsis` 로 잘린다. 허브 상세 패널
(폭 549px)에서는 자주 잘리고, 단독 탭(`.wrap{max-width:860px}`)에서는 같은 문자열이 대체로
안 잘린다 — 잘림 여부가 **렌더 폭에 달려 있고, `/dashboard log` 절차는 렌더 폭을 모른다.**

두 안을 검토했다.

- **마크업 각인** — `log` 절차가 `<span class="lead" title="…">` 을 쓴다. 기각한 이유 넷:
  1. 잘림 여부를 생성 시점에 알 수 없으므로 **항상** 각인해야 하고, 그러면 잘리지 않은
     항목에도 툴팁이 뜬다(잘리지 않은 항목에는 띄우지 않는다는 요구 위반).
  2. 이스케이프 규약을 개정해야 한다 — 현행은 `&`·`<`·`>` 세 가지뿐인데 속성값에 넣으려면
     `"`→`&quot;` 가 추가돼야 하고, 그 순간 텍스트 노드용과 속성용 규약이 두 벌이 된다.
  3. 각인이 아니어도 폴링 재동기화(`#dz-log` 의 자식을 통째로 교체)와 충돌하지 않는다 —
     이 이점은 런타임 감지에도 그대로 있다.
  4. 새로 쓰는 `<li>` 에만 붙으므로 이미 쌓인 과거 로그 항목은 영원히 툴팁을 못 받는다.
- **런타임 hover 감지** — 스크립트가 hover 시점에 실제 레이아웃(`scrollWidth`
  대 `clientWidth`)을 재고, 잘렸을 때만 툴팁을 띄운다. **채택.** 속성을 남기지 않으므로
  폴링·필터·`<details>` 토글의 재부착 시점을 설계할 필요가 없고, 파일이 새 템플릿으로 다시
  만들어지는 순간 과거 로그 항목까지 전부 동작한다.

구현은 대시보드 템플릿 자체의 커스텀 툴팁 싱글턴이다(허브의 `[data-tooltip]` 싱글턴과 같은
종류의 코드) — 네이티브 `title` 은 약 1초 지연 후 뜨고 약 5초 뒤 저절로 사라지며 포인터로
붙잡아 둘 수 없어, 텍스트 선택이 함께 없어진(상호작용 잠금) 화면에서 "유일한 읽기 수단"의
자격이 없다. 두 템플릿은 각각 단독 파일로 배포돼야 해 코드를 공유할 수단이 없으므로, 이
중복은 DRY 위반이 아니라 배포 단위 제약의 결과다(테마 토큰·테마 IIFE·폴링 골격이 이미 같은
이유로 중복이다).

> 전문: [`docs/prps/dashboard-lead-tooltip-and-interaction-lockdown.md`](./dashboard-lead-tooltip-and-interaction-lockdown.md) 결정 LT1~LT9

<a id="session-path"></a>
## 대시보드 경로 규칙 — 세션 ID·폴백·토큰·리텐션의 근거

**왜 세션 ID 인가(ST1).** 파일명 후보는 세 가지였다 — 세션 ID, 8자리 랜덤 토큰, 토큰 파일명 +
별도 `data-session-id` 각인. 세션 ID 를 채택한 이유는 허브가 **추가 데이터 없이** 파일을 세션에
붙일 수 있어서다 — `SessionFacts.session_id`(`hub_session.py` L60)가 이미 키이고,
`read_session_model`(`hub_collect.py` L280-299)이 transcript 를 찾는 방식과 정확히 같다. 토큰
파일명은 허브가 파일 → 세션을 연결할 수단이 없고, 토큰 + `data-session-id` 각인은 허브가 세션을
알려고 파일마다 열어야 해 `stat` 로 끝나는 세션 ID 안보다 비싸다.

**왜 폴백이 단일 파일인가(ST2).** 변수가 없을 때 `.claude/dashboards/<랜덤 8자리>.html` 을 만드는
안을 기각했다 — 그 파일은 허브가 어느 세션에도 붙일 수 없는 "무귀속 세션 파일"이라는 새 개념을
만든다. 레거시 단일 파일은 어차피 호환을 위해 계속 읽어야 하므로(허브가 옛 방식 대시보드도
발견해야 한다), 무귀속 파일의 자리는 그 하나로 충분하다. 폴백 경로의 `ABSENT`/`RECENT`/`STALE`
판정·확인 절차·8자리 랜덤 토큰은 오늘과 바이트 단위로 같다 — 회귀 시험(`tests/run.sh` 의
T22-106)이 이 어휘들을 계속 요구한다.

**왜 앞 8자리인가(ST3).** SESSION 모드의 `data-owner-token` 은 세션 ID 36자 전체가 아니라 앞
8자리다. 전체를 쓰면 기존 형식 규격(`[0-9a-f]{8}`)이 깨지고 「소유권 검증」 표의 비교 대상이 두
형식이 된다. 앞 8자리는 형식을 그대로 유지하면서, 값 자체가 허브의 `short_id`
(`hub_session.py` L374 `facts.session_id[:SHORT_ID_LENGTH]`)와 같아져 카드의 세션 칩과 눈으로
대조할 수 있다.

**왜 `init` 이 7일 초과 파일을 지우는가(ST5).** 대안은 셋이었다 — 허브가 정리(허브는 옵트인
자산이라 없는 환경에서는 아무도 안 지운다), `log commit` 이 자기 파일을 삭제(끝난 작업의
대시보드도 허브가 `done` 세션과 함께 보여주는 것이 가치이므로 기각), 수동만(상한이 없어 무한
성장). `init` 1단계에 `find … -mtime +7 -delete` 를 더하는 것은 이미 있는 Bash 호출에 조각 하나를
더하는 것뿐이라 호출 수가 늘지 않는다. 7일은 `HubConfig.event_retention_days` 기본값과 같은
수지만 두 값은 서로 참조하지 않는다 — 대시보드는 허브 없이도 동작해야 하기 때문이다. 레거시
`.claude/dashboard.html` 은 다른 세션의 것일 수 있어 건드리지 않는다.

**왜 파이썬 블록에 환경변수로 넘기는가(§6.1).** `init` 4단계·포트 스캔은 `python3 - <<'PY'` 인용
heredoc 을 쓴다. 인용 heredoc 은 셸이 내부를 전혀 확장하지 않으므로, 경로 규칙을 파이썬 코드
안에 다시 옮겨 적으면 같은 판정 로직이 셸과 파이썬 두 언어에 중복해서 살고 둘이 어긋날 경로가
생긴다. `DZ_PATH="$dz_path" python3 …` 로 셸에서 계산한 값을 환경변수 하나로 넘기면 판정 로직은
셸에만 있고, 파이썬은 `os.environ["DZ_PATH"]` 로 그 결과값만 읽는다.

> 전문: [`docs/prps/hub-session-tree-and-per-session-dashboards.md`](./hub-session-tree-and-per-session-dashboards.md) 결정 ST1~ST5, §6.1
