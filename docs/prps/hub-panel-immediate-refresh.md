# 허브 — 즉시 폴링 3종이 **열린 상세 패널의 대시보드도 함께** 갱신한다 (PRP)

- **대상**: `hub/bin/hub_template.html`, `commands/dashboard_template.html`
- **결정 접두**: `IR`(Immediate Refresh) — 기존 접두(SP·OC·GN·PV·DG·RV·ZG·UT·EX·LG·MD·MS·ON·TR·WT)와 충돌 없음(전수 확인)
- **선행 정본**: [hub-detail-side-panel.md](hub-detail-side-panel.md)(SP1~SP15) · [hub-panel-empty-state-and-open-card.md](hub-panel-empty-state-and-open-card.md)(OC1~OC12) · [hub-panel-polish-and-icons.md](hub-panel-polish-and-icons.md)(PV1~PV13)
- **검증 명령**: `bash tests/run.sh` (기대: 24/24)

---

## 요구사항 요약

허브의 상세 패널이 열려 있으면 그 안의 iframe 은 프로젝트 대시보드를 **자기만의 60초 폴링**으로
갱신한다. 그래서 사용자가 허브에서 새로고침을 눌러도 **왼쪽 카드만 즉시 갱신되고 오른쪽 패널은
최대 1분을 더 기다린다** — 같은 화면의 두 영역이 서로 다른 시각을 보여준다. 이 PRP 는 허브의
"즉시 폴링" 트리거 3종(① `#dzh-refresh` 클릭 ② `window` focus ③ `visibilitychange` 로 visible
복귀)이 발생할 때 **열린 패널의 대시보드도 그 자리에서 갱신**되게 한다. 갱신 수단은 대시보드
템플릿이 iframe `window` 에 노출하는 함수 훅이며(같은 오리진이므로 `typeof` 기능 감지가 성립),
훅이 없는 옛 세대 파일에는 문서 재로딩 폴백을 둔다.

### 사용자 스토리

```
허브에서 여러 프로젝트를 지켜보는 사람으로서,
새로고침을 누르거나 다른 창을 갔다 돌아왔을 때 카드와 열린 패널이 같은 시각을 보여주기를 바란다.
그래야 "카드는 검수 단계인데 패널은 아직 구현 중"이라는, 데이터가 아니라 폴링 주기가 만든
불일치를 보고 판단을 그르치지 않는다.
```

### 성공 기준 (검증 가능한 형태)

| # | 기준 | 확인 방법 |
|---|------|-----------|
| S1 | 패널을 연 채 `#dzh-refresh` 를 누르면 iframe 이 `dashboard.html` 을 1회 fetch 한다 | DevTools 네트워크 (현재 실측: 0회) |
| S2 | 그 갱신에서 iframe 의 **스크롤 위치가 유지**된다 | 로그 카드를 아래로 스크롤한 뒤 새로고침 |
| S3 | 창 포커스 복귀(②)에서도 S1·S2 가 성립한다 | 다른 앱 갔다 오기 |
| S4 | 패널이 닫혀 있으면 3종 어느 것도 iframe 요청을 만들지 않는다 | 네트워크 0회 |
| S5 | 빈 상태 패널(대시보드 없는 프로젝트)에서도 요청 0회 | 티어 2 카드를 열고 새로고침 |
| S6 | 허브의 60초 인터벌 폴링은 iframe 을 건드리지 않는다 | 2분 방치 — iframe 요청은 자체 폴링분(2회)뿐 |
| S7 | 같은 카드 재클릭 시 iframe 재로딩 0회(OC2)가 그대로다 | 네트워크 0회 |
| S8 | 훅 없는 옛 세대 `dashboard.html` 에서 새로고침 버튼을 누르면 문서가 다시 실린다 | 훅 줄을 지운 사본으로 실측 |
| S9 | `bash tests/run.sh` 가 24/24 | 명령 실행 |

---

## 확정된 전제 (재론하지 않는다)

사전 조사에서 **실측으로 확정된 사실**이다. 구현 중 다시 검증하지 않는다.

1. **새로고침 버튼은 `poll()` 만 부른다**(`hub_template.html:1486`). 네트워크 실측: `hub.html` 만
   fetch, iframe 요청 0회.
2. **iframe 은 served 모드에서 무조건 60초 자체 폴링**을 한다(`dashboard_template.html:360`,
   실측 60초 간격 확인). 갱신 방식은 부분 치환(`apply()` → `sync*` 함수들, 337~347행)이라
   **스크롤이 유지된다**.
3. **같은 카드 재클릭 시 iframe 재요청 0회**(OC2 `isSameDocument` 정상 동작 실측).
4. **허브와 대시보드는 같은 오리진**이다 — `/project/<16hex>/dashboard.html` 을 허브 서버가
   서빙한다(`hub_server.py`). 따라서 `contentWindow` 의 프로퍼티 읽기가 `SecurityError` 를
   던지는 시나리오가 **존재하지 않는다**.
5. 그 경로의 응답에는 `Cache-Control: no-store` 가 붙는다(`hub_server.py:35,138`) — 폴백
   재로딩이 캐시된 사본을 싣지 않는다.
6. **`visibilitychange` 는 iframe 문서에도 발화한다**(HTML 명세: 프레임 트리의 모든 Document).
   즉 트리거 ③ 에서는 iframe 이 오늘도 이미 자기 자신을 폴링한다. 반면 `focus` 는 포커스를 얻은
   창에만 발화하므로 트리거 ② 는 오늘 iframe 에 전혀 닿지 않는다 — **이번 기능의 실질 이득은
   ①·② 에 있다**(③ 은 정합성을 위해 함께 태운다, 결정 IR2 참조).

### 비목표 (이번 범위 밖 — 명시적으로 건드리지 않는다)

- 허브의 **60초 인터벌 폴링**에 nudge 를 태우지 않는다(iframe 자체 60초 폴링과 이중 폴링이 된다).
- **사용량 패널 토글의 즉시 폴링**(`hub_template.html:1376` 부근)은 대상이 아니다 — 사용량은
  패널 대시보드와 무관한 데이터다.
- iframe 의 **60초 자체 폴링을 끄지 않는다**. 백스톱으로 그대로 둔다(허브 탭을 보지 않는 동안의
  유일한 갱신 경로).
- `dashboard_template.html` 의 **`file://` 분기(갱신 경로 A, 276~285행)는 한 줄도 바꾸지 않는다**.
- 허브의 `file://` 분기(`hub_template.html:1443~1450`)도 바꾸지 않는다 — 그 모드에서는 모든
  카드가 빈 상태이므로(결정 OC6) 갱신할 iframe 자체가 없다.
- 옛 세대 대시보드 파일을 허브가 **고쳐 쓰지 않는다**(읽기 전용 소비, hub/README.md 「알려진 한계」).

---

## 영향 범위

### 수정 파일 (6개 + 이 문서)

| 파일 | 변경 | 이유 |
|------|------|------|
| `commands/dashboard_template.html` | 훅 1줄 + 주석, 머리 주석(DZ:DASHBOARD) 1블록 | 갱신 훅 노출(경로 B 전용) |
| `hub/bin/hub_template.html` | 렌더 IIFE(상수 1 + `pollNow` + 리스너 3), 패널 IIFE(상수 2 + 함수 1 + 리스너 1), 머리 주석 | 발행·구독 |
| `hub/README.md` | 「프로젝트 상세 패널」 절 1항목 개정 + 「알려진 한계」 1줄 | 갱신 규칙이 바뀐다 |
| `commands/dashboard.md` | 「폴링 동기화 계약」 절에 훅 1문단 | 템플릿 스크립트의 외부 계약이 새로 생긴다 |
| `README.md` | 커맨드 표(139행)의 줄 수 실측값 갱신 | 저장소 관례(0ba6f8c) |
| `tests/run.sh` | T22-145~147 · T25-131~136 신설 | 회귀 기계 검사 |

### 미영향 — 건드리지 않는 이유 (직접 확인함)

| 대상 | 왜 안 건드리나 |
|------|----------------|
| `hub/bin/hub_server.py` | 이미 같은 오리진으로 서빙하고 `no-store` 를 붙인다. 서버 변경이 필요한 부분이 없다 |
| `hub/bin/hub_model.py` 등 파이썬 전부 | 순수 템플릿 JS 변경이다. 스냅샷 스키마·렌더 함수가 그대로다 |
| `tests/hub/*.py` | 파이썬 단위 테스트의 대상(모델·세션·수집)에 변경이 없다. **신설 없음** |
| `dashboard_template.html` 의 PiP 블록 | 훅은 PiP 진입 여부와 무관하다. `.wrap` 이 PiP 창으로 이동해도 `poll()` 은 같은 노드를 갱신한다 |
| 패널의 `about:blank` 지연 비우기(SP14/OC3) | 대기 타이머가 존재하면 `openPanelTarget === null` 이므로 새 코드의 첫 가드에서 끝난다 |

---

## 결정 기록

### 결정 IR1 — 통신은 **`document` 커스텀 이벤트 1개**. 두 IIFE 의 분리를 유지한다

즉시 폴링 트리거는 **렌더 IIFE** 소관이고(1483~1486행), 패널 iframe 은 **패널 IIFE** 소관이다
(1489~1692행). 두 IIFE 는 서로의 변수를 모른다 — 렌더 IIFE 는 패널을, 패널 IIFE 는 `snapshot` 을
모르며 `tests/run.sh` 의 T25-89 가 이 분리를 기계 검사한다.

선례가 이미 있다: 결정 OC8 이 "재렌더했다"는 사실을 `dzh:rendered` 커스텀 이벤트로 넘긴다
(`hub_template.html:785, 1363, 1512, 1691`). 같은 관용구를 그대로 재사용한다.

```
IMMEDIATE_REFRESH_EVENT_NAME = 'dzh:refresh-requested'
  발행: 렌더 IIFE — 즉시 폴링 3종의 리스너에서만
  구독: 패널 IIFE — 열린 패널이 있을 때만 반응
```

렌더 IIFE 는 여전히 "누가 듣는지"를 모르고, 패널 IIFE 는 여전히 "왜 폴링했는지"를 모른다.

### 결정 IR2 — 발행 지점은 **즉시 폴링 3종뿐**. 60초 인터벌은 발행하지 않는다

현재 코드는 4개 지점이 모두 `poll` 을 부른다(1483~1486행). 그중 인터벌만 남기고 나머지 3개를
`pollNow(isExplicitRequest)` 래퍼로 바꾼다.

```js
function pollNow(isExplicitRequest){
  poll();
  document.dispatchEvent(new CustomEvent(IMMEDIATE_REFRESH_EVENT_NAME,
                                         {detail:{isExplicitRequest:isExplicitRequest}}));
}
setInterval(function(){ if(document.visibilityState==='visible') poll(); }, POLL_INTERVAL_MS);
document.addEventListener('visibilitychange', function(){ if(document.visibilityState==='visible') pollNow(false); });
window.addEventListener('focus', function(){ pollNow(false); });
refreshButton.addEventListener('click', function(){ pollNow(true); });
```

**인터벌을 제외하는 이유**: iframe 은 이미 자기 60초 폴링을 한다(전제 2). 인터벌까지 nudge 를
태우면 같은 주기의 요청이 2배가 되고, 두 타이머의 위상이 어긋나 평균 30초마다 요청이 나간다 —
얻는 게 없이 요청만 늘어난다.

**③(`visibilitychange`)을 포함하는 이유**: 전제 6 대로 iframe 도 같은 이벤트를 받아 스스로
폴링하므로 중복으로 보인다. 그러나 두 호출은 같은 이벤트 루프 턴에서 일어나고 `poll()` 의
`busy` 가드(`dashboard_template.html:349-350`)가 둘째를 즉시 반환시킨다 — **fetch 는 1회다**.
"세 트리거 중 하나만 규칙이 다르다"는 예외를 만드는 비용이 중복 제거 이득보다 크다.

### 결정 IR3 — 이벤트는 `detail:{isExplicitRequest:boolean}` **한 필드만** 싣는다

결정 OC8 은 `dzh:rendered` 에 대해 "값을 싣지 않는다"고 못 박았다. 그 취지는 **스냅샷 데이터가
패널 IIFE 로 새는 것을 막는 것**이다(T25-89 가 검사하는 것도 `snapshot` 문자열 0건이다). 트리거의
종류는 스냅샷 데이터가 아니라 **렌더 IIFE 가 이미 알고 있는 자기 사건의 성격**이므로 그 취지에
저촉되지 않는다. 이 한 필드가 필요한 이유는 결정 IR5 하나뿐이며, 그 이상은 싣지 않는다.

`dzh:rendered` 는 지금처럼 `new Event(...)` 로 남긴다 — 실을 값이 없기 때문이다.

### 결정 IR4 — 대시보드 훅은 **`window.dzRequestRefresh = poll`**. 이름이 계약이다

```js
// commands/dashboard_template.html — 갱신 경로 B(서버 모드) 안, 트리거 리스너 바로 뒤
window.dzRequestRefresh = poll;
```

- **이름**: 대시보드 쪽 접두 `dz` + 축약 없는 동사구. 허브 쪽 상수
  `DASHBOARD_REFRESH_HOOK_NAME = 'dzRequestRefresh'` 와 **문자 단위로 같아야** 하며 T25-136 이
  이를 기계 검사한다(오타는 조용한 폴백으로 나타나므로 사람 눈으로는 못 잡는다).
- **시그니처**: 인자 없음, 반환값 없음. `poll()` 을 그대로 대입한다 — 래퍼를 두면 "훅이 하는 일"이
  `poll()` 과 갈라질 여지가 생긴다. 연속 호출은 `poll()` 의 `busy` 가 흡수한다(멱등).
- **위치**: `if(!isServed){ … return; }`(276~285행) **뒤** — 그래야 갱신 경로 A 가 회귀 금지 대상인
  채로 남는다. 동시에 `if(!hasPipSupport){ … return; }`(365~370행) **앞** — 뒤로 가면 Document PiP
  미지원 브라우저(Safari·Firefox)에서 훅이 영영 노출되지 않는다(GOTCHA 1).
- **기능 감지가 성립하는 근거**: 같은 오리진(전제 4)이므로 허브가 `typeof frameWindow['dzRequestRefresh']`
  를 그냥 읽을 수 있다. `postMessage` 핸드셰이크가 필요 없다(대안 A1 참조).

`grep 유일성 불변식`(dashboard.md) 저촉 여부 — **없음**: 이 줄은 `id="…"` 형태 문자열을 만들지
않는다. `getElementById`/`#셀렉터`만 쓰라는 규칙도 그대로 지킨다(이 줄은 DOM 조회를 하지 않는다).

### 결정 IR5 — 옛 세대 폴백 재로딩은 **명시적 요청(새로고침 버튼)에만** 적용한다 ★ 승인 항목 1

요구서는 "훅이 없으면 재로딩으로 폴백한다 — **명시적 갱신 요청이므로** 스크롤 손실 용인"이라고
근거를 달았다. 그 근거는 ①(버튼)에는 그대로 성립하지만 ②·③(포커스·탭 복귀)에는 성립하지 않는다.
②·③ 까지 재로딩하면 이런 회귀가 생긴다:

> 옛 세대 대시보드를 패널에 띄워 둔 채 터미널을 갔다 올 때마다 iframe 이 통째로 다시 실려
> **읽던 위치가 매번 맨 위로 돌아간다.** 오늘은 그런 일이 없다(iframe 이 자체 폴링으로 부분
> 치환만 한다). 즉 **암묵 트리거에 폴백을 붙이면 옛 세대 사용자에게는 순손실**이다.

게다가 옛 세대 파일이 남아 있는 프로젝트는 정의상 **`/dashboard init|step|log` 가 그 파일을 다시
쓴 적 없는 프로젝트**(=활동이 멎은 이전 작업)이므로, 재로딩해도 새 내용이 없을 확률이 높다.

그래서:

| 훅 | 트리거 | 동작 |
|----|--------|------|
| 있음 | ①·②·③ | `dzRequestRefresh()` — 부분 치환, 스크롤 유지 |
| 없음 | ①(버튼) | `loadPanelDocument(url)` — 문서 재로딩, 스크롤 손실 용인 |
| 없음 | ②·③ | **no-op** — 오늘과 완전히 같은 동작(회귀 0) |

이것이 이벤트에 `isExplicitRequest` 를 싣는 유일한 이유다(결정 IR3).

### 결정 IR6 — **로딩 중인 iframe(load 이벤트 전)에는 아무것도 하지 않는다**

게이트는 이미 있는 `PANEL_FRAME_LOADED_CLASS`(`detail-frame-loaded`)다. `loadPanelDocument()` 가
`location.replace()` 직전에 떼고 `load` 리스너가 다시 붙이므로(1560~1563 · 1669~1671행),
**클래스가 붙어 있다 ⟺ 지금 보이는 문서의 `load` 가 끝났다**가 정확히 성립한다.

이 가드는 편의가 아니라 **기능적 필요**다:

- 로딩 중이면 그 문서가 곧 최신 내용을 실어 온다 — 지금 갱신을 요청할 이유가 없다.
- 로딩 중인 문서에는 훅이 아직 없다(스크립트 미실행). 가드가 없으면 **훅 있는 최신 대시보드조차
  "옛 세대"로 오판**되어 폴백 재로딩을 타고, 그 재로딩 중에 다음 포커스가 오면 또 재로딩한다 —
  포커스를 연타하면 재로딩이 꼬리를 문다(GOTCHA 3).

### 결정 IR7 — `try`/`catch` 를 쓰지 않는다. **`typeof` 기능 감지 하나가 방어의 전부**다

요구서는 `contentWindow` 접근을 방어하라고 했고, 전역 지침(Karpathy 2)은 일어날 수 없는 상황에
대한 에러 처리를 금지한다. 두 요구는 다음 사실로 동시에 만족된다:

- **크로스 오리진 예외는 불가능하다**: iframe 에 실리는 URL 은 `projectDashboardUrl()`(같은 오리진)
  아니면 `about:blank`(오리진 상속) 둘뿐이다(1549~1552, 1637~1640행). 외부 URL 이 들어갈 경로가 없다.
- **`contentWindow` 가 `null` 일 수 없다**: `#dzh-detail-frame` 은 `#dzh-detail-panel` 의 정적
  자식이며 폴링·틱이 절대 교체하지 않는다(불변식 H1⁗). 문서에서 분리되는 순간이 없다.
- **훅 부재는 예외가 아니라 정상 경로다**: 옛 세대 파일에서는 프로퍼티가 그냥 `undefined` 다.
  `typeof … === 'function'` 이 이것을 정확히 가른다.

`try`/`catch` 를 두면 위 세 사실 중 어느 것이 깨져도 **조용히 삼켜져** 아무도 모르게 된다. 방어를
빼는 쪽이 오히려 실패를 드러낸다.

### 결정 IR8 — 폴백은 **`loadPanelDocument()` 를 재사용**한다

흰 플래시 방지 계약(로드 완료 클래스를 `replace()` 직전 같은 동기 태스크에서 뗀다, 커밋 `abef2bf`
· T25-129)은 그 함수 안에 있다. 별도 경로를 만들면 그 계약이 두 벌이 되고 T25-129 의 범위 검사도
한쪽만 지킨다. URL 은 `projectDashboardUrl(openPanelTarget.dashboardKey)` — `openDetailPanel` 이
쓰는 것과 같은 순수 함수다.

### 결정 IR9 — 주석·문서 정합 (거짓말을 남기지 않는다)

| 위치 | 지금 문장 | 개정 |
|------|-----------|------|
| `hub_template.html` 머리 주석 16~19행 | "두 모드 모두 `#dzh-refresh` 버튼과 포커스 복귀 시에도 같은 즉시 갱신 경로를 탄다" | 그 즉시 갱신 경로가 **열린 패널의 iframe 도 함께** 태운다는 조항 추가(결정 IR1·IR5 참조) |
| `dashboard_template.html` 머리 주석 | 갱신 훅 언급 없음 | "정적(불가침)" 목록에 `window.dzRequestRefresh` 계약 1블록 추가 |
| `hub/README.md:263-264` | "패널 안 대시보드는 원본 화면과 똑같이 **1분마다 스스로 갱신**된다 … 이 갱신 메커니즘 자체는 한 줄도 바뀌지 않는다" | 60초 자체 갱신은 백스톱으로 유지되고, 허브의 즉시 갱신 3종에도 함께 갱신된다(스크롤 유지)로 개정. 마지막 절은 **삭제**한다(더는 사실이 아니다) |
| `hub/README.md` 「알려진 한계」 | 구세대 노출 항목 | 구세대 파일은 새로고침 버튼에서만, 문서 재로딩으로 갱신된다(스크롤 초기화)는 1줄 추가 |
| `commands/dashboard.md` 「폴링 동기화 계약」 | 훅 언급 없음 | 서버 모드 스크립트가 `window.dzRequestRefresh` 를 노출한다는 1문단 추가 |

**새 불변식 번호는 만들지 않는다**(dashboard.md 의 불변식은 10번까지). 불변식 목록은
`init`/`step`/`log` **오케스트레이터가 지켜야 할 것**을 모아 둔 곳인데, 훅 줄은 오케스트레이터가
편집하지 않는 템플릿 본문이고 `id="…"` 문자열도 만들지 않는다 — 지킬 것이 없는 곳에 규칙을
만들지 않는다(YAGNI).

---

## 계약 (변경 후)

### 새로 생기는 계약 3개

| 이름 | 사는 곳 | 값/형식 | 짝 |
|------|---------|---------|-----|
| `IMMEDIATE_REFRESH_EVENT_NAME` | `hub_template.html` 렌더 IIFE + 패널 IIFE | `'dzh:refresh-requested'` | 같은 파일 안 두 선언이 문자 단위로 같아야 한다 |
| `DASHBOARD_REFRESH_HOOK_NAME` | `hub_template.html` 패널 IIFE | `'dzRequestRefresh'` | `dashboard_template.html` 의 `window.dzRequestRefresh` 와 같아야 한다 |
| `window.dzRequestRefresh` | `dashboard_template.html` 갱신 경로 B | `() => void`, 멱등 | 위 상수 |

### 이벤트 페이로드 (모듈 간 통신의 유일한 형식)

```
CustomEvent<'dzh:refresh-requested'>
  detail: { isExplicitRequest: boolean }
              // true  = 사용자가 #dzh-refresh 를 눌렀다
              // false = 포커스 복귀 · 탭 복귀 같은 암묵 트리거
```

발행 지점은 `pollNow()` **1곳뿐**이며 T25-134 가 이를 기계 검사한다. 따라서 구독 측에서
`event.detail` 의 존재를 다시 확인하지 않는다(결정 IR7 과 같은 이유).

### 공개 함수 시그니처 (템플릿 JS)

```js
// hub_template.html — 렌더 IIFE
function pollNow(isExplicitRequest: boolean): void
  // 즉시 폴링 1회 + 즉시 갱신 이벤트 1건 발행. 60초 인터벌은 이 함수를 쓰지 않는다.

// hub_template.html — 패널 IIFE
function refreshOpenPanelDocument(isExplicitRequest: boolean): void
  // 열린 패널의 대시보드를 즉시 갱신한다. 훅이 있으면 부분 치환, 없으면 명시적 요청일 때만 재로딩.

// dashboard_template.html — 갱신 경로 B (iframe window 에 노출)
window.dzRequestRefresh(): void
  // = poll. 인자·반환값 없음. 진행 중이면 busy 가드가 즉시 반환한다.
```

### 구독 측 본문 (권고 형태)

```js
function refreshOpenPanelDocument(isExplicitRequest){
  if(openPanelTarget === null) return;                   // 닫혀 있다(대기 타이머 중이면 여기서 끝난다, OC3)
  if(openPanelTarget.dashboardKey === null) return;      // 빈 상태 — iframe 은 about:blank 다
  if(!panelFrameEl.classList.contains(PANEL_FRAME_LOADED_CLASS)) return;   // 로딩 중(결정 IR6)
  var frameWindow = panelFrameEl.contentWindow;
  if(typeof frameWindow[DASHBOARD_REFRESH_HOOK_NAME] === 'function'){
    frameWindow[DASHBOARD_REFRESH_HOOK_NAME]();          // 메서드 호출 형태 — this 가 iframe window 다
    return;
  }
  if(isExplicitRequest) loadPanelDocument(projectDashboardUrl(openPanelTarget.dashboardKey));
}
document.addEventListener(IMMEDIATE_REFRESH_EVENT_NAME, function(event){
  refreshOpenPanelDocument(event.detail.isExplicitRequest);
});
```

---

## 경계 조건 표

| # | 상황 | 판정 지점 | 동작 | 근거 |
|---|------|-----------|------|------|
| E1 | 패널이 닫혀 있다 | `openPanelTarget === null` | no-op | 요구서 |
| E2 | 닫는 중(about:blank 지연 창) | 같음 — 대기 타이머 ⇒ `openPanelTarget === null` | no-op | 불변식 SP15/OC3 |
| E3 | 빈 상태(대시보드 없는 프로젝트) | `dashboardKey === null` | no-op | 요구서 |
| E4 | 패널을 막 열어 iframe 이 로딩 중 | 로드 완료 클래스 부재 | no-op | 결정 IR6 |
| E5 | 훅 있음 + 어떤 트리거든 | `typeof … === 'function'` | 훅 호출(부분 치환) | 결정 IR4 |
| E6 | 훅 없음 + ①(버튼) | `isExplicitRequest === true` | `loadPanelDocument()` | 결정 IR5·IR8 |
| E7 | 훅 없음 + ②·③ | `isExplicitRequest === false` | no-op | 결정 IR5 |
| E8 | 훅 호출 시 iframe 이 이미 fetch 중 | 훅 안쪽 `busy` | 즉시 반환(요청 1회) | 전제 2 |
| E9 | ③에서 iframe 이 자체 `visibilitychange` 로도 폴링 | 같은 `busy` | fetch 총 1회 | 결정 IR2 |
| E10 | 허브가 `file://` 로 열렸다 | 렌더 IIFE 가 1449행에서 조기 return | 이벤트 발행 자체가 없다 | 비목표 |
| E11 | 열린 프로젝트가 스냅샷에서 사라졌다 | `openPanelTarget` 은 그대로 | 여전히 갱신 시도(404 는 iframe 의 실패 처리 소관) | 엣지 E6(OC 정본) — 패널을 강제로 닫지 않는다 |
| E12 | 패널 안에서 PiP 를 열어 `.wrap` 이 이동했다 | 훅은 여전히 같은 `poll` | 정상 갱신 | 구세대 파일에서만 가능(임베드 시 PiP 버튼은 숨는다) |

---

## GOTCHA (구현자가 틀리기 쉬운 함정)

1. **훅 노출 줄의 위치** — `if(!hasPipSupport){ … return; }`(365~370행) **앞**에 두어야 한다.
   뒤에 두면 Safari·Firefox 에서 훅이 노출되지 않아 그 브라우저 사용자 전원이 "옛 세대"로
   판정된다. 갱신 트리거 리스너 3줄(360~362행) 바로 뒤가 정위치다.
2. **`pollNow` 를 리스너에 직접 넘기면 안 된다** — `window.addEventListener('focus', pollNow)` 로
   쓰면 첫 인자로 `FocusEvent` 객체가 들어가 `isExplicitRequest` 가 **항상 truthy** 가 된다.
   그러면 포커스가 돌아올 때마다 옛 세대 대시보드가 통째로 재로딩되어 결정 IR5 가 정확히
   무력화된다. 반드시 익명 함수로 감싸 `pollNow(false)` / `pollNow(true)` 를 명시한다.
3. **로드 완료 클래스 가드를 빼면 재로딩이 꼬리를 문다** — 결정 IR6 참조. 특히 훅 있는 최신
   대시보드에서도 로딩 중에는 훅이 없으므로 오판이 일어난다.
4. **훅 호출은 메서드 형태로** — `var hook = frameWindow[NAME]; hook();` 로 떼어내 부르면 느슨한
   모드의 `this` 치환 규칙에 기대게 된다. `frameWindow[NAME]()` 로 부르면 `this` 가 iframe
   window 로 확정되어 그 미묘함이 아예 사라진다.
5. **60초 인터벌 줄은 `poll` 그대로** — 1483행을 `pollNow` 로 바꾸면 결정 IR2 가 깨진다.
   T25-133 이 역방향으로 검사한다.
6. **패널 IIFE 에 `snapshot` 문자열을 들이지 말 것** — 새 코드도 T25-89 의 범위(패널 IIFE 시작 ~
   파일 끝) 안에 들어간다. 대시보드 URL 은 카드 DOM 에서 온 `dashboardKey` 로만 조립한다.
7. **`refreshButton.addEventListener('click', reloadOnce)`(1448행)는 `file://` 분기의 것**이다.
   1486행과 혼동해 그쪽을 고치면 안 된다.
8. **`dzh:rendered` 는 `new Event` 그대로** — 새 이벤트만 `CustomEvent` 다. 통일한다고 옛 것을
   바꾸면 무관한 변경이 된다(Karpathy 3).

---

## 테스트 계획 — `tests/run.sh`

### 기존 검사에 대한 영향 (전수 확인 결과)

| 검사 | 영향 | 확인 |
|------|------|------|
| T22-29 (`if(!isServed){` 분기 비퇴화) | 없음 — 분기를 건드리지 않는다 | 훅은 분기 **뒤**에 산다 |
| T22-31 (`'documentPictureInPicture' in window` 기능 감지) | 없음 | 그대로 |
| T22-129 (`POLL_INTERVAL_MS = 60000`) | 없음 | 값 불변 |
| T25-41 (허브 `POLL_INTERVAL_MS = 60000`) | 없음 | 값 불변 |
| T25-80 (`panelFrameEl.src` 대입 금지) | 없음 — 폴백도 `loadPanelDocument()` 경유 | 결정 IR8 |
| T25-81 (README 패널 토큰 · '모달' 부재) | 없음 — 문구 추가만 | 삭제 문장에 '모달' 없음 |
| T25-89 (패널 IIFE 에 `snapshot` 0건) | **자동 재검사됨** — 새 코드가 그 범위 안이다 | GOTCHA 6 |
| T25-129 (흰 플래시 계약, `loadPanelDocument` 범위) | 없음 — 함수 본문 불변 | 결정 IR8 |
| 파이썬 단위 테스트(`tests/hub/`) | **없음. 신설도 없음** | 파이썬 코드 무변경 |

### 신규 검사 (정방향 + 역방향 쌍)

**T22 그룹**(`test_dashboard_template_integrity()`, 현재 T22-1~144 → 147까지) — 판정 대상은
`$dashboard_union_file`(설치본 `dashboard.md` + `dashboard_template.html` 합본).

| ID | 방향 | 검사 |
|----|------|------|
| T22-145 | 정 | `window.dzRequestRefresh = poll;` 이 정확히 1건 존재 |
| T22-145 | 역 | 그 줄 번호가 `if(!isServed){` 줄보다 **뒤**다 — 갱신 경로 A 오염 금지(선례: T25-83 의 줄 번호 비교) |
| T22-146 | 역 | 그 줄 번호가 `if(!hasPipSupport){` 줄보다 **앞**이다 — GOTCHA 1 회귀 검출 |
| T22-147 | 정 | `dashboard.md` 에 `dzRequestRefresh` 문서 토큰이 있다(문서 정합) |

**T25 그룹**(`test_hub_docs_and_constants()`, 현재 T25-1~130 → 136까지) — `$REPO_ROOT` 원본을 본다.
`local dashboard_template_file="$REPO_ROOT/commands/dashboard_template.html"` 선언을 추가한다.

| ID | 방향 | 검사 |
|----|------|------|
| T25-131 | 정 | `hub_template.html` 에 `'dzh:refresh-requested'` 리터럴이 정확히 2건(렌더 IIFE·패널 IIFE 각 1) — `RENDERED_EVENT_NAME` 관용구와 동형 |
| T25-132 | 정 | `dispatchEvent(new CustomEvent(IMMEDIATE_REFRESH_EVENT_NAME` 이 존재하고, `pollNow` 함수 범위 안이다(범위 추출 후 검사, 선례: T25-130 의 `staleBadgeTooltipText()` 범위 추출) |
| T25-133 | 역 | `POLL_INTERVAL_MS` 를 쓰는 `setInterval` 줄에 `pollNow` 가 **없다** — 이중 폴링 회귀(결정 IR2·GOTCHA 5) |
| T25-134 | 정+역 | `pollNow(` 호출이 정확히 3건이고 그중 `pollNow(true)` 가 1건 `pollNow(false)` 가 2건이다. 리스너 인자 자리에 맨 `pollNow` 가 오는 형태(`, pollNow)`)가 0건이다 — GOTCHA 2 회귀 검출 |
| T25-135 | 정+역 | `refreshOpenPanelDocument(` 범위를 추출해 ① 가드 3종(`openPanelTarget === null`, `dashboardKey === null`, `PANEL_FRAME_LOADED_CLASS`) 존재 ② `typeof` 기능 감지 존재 ③ `loadPanelDocument(` 호출이 `if(isExplicitRequest)` 뒤에 있다(줄 번호 비교) ④ `try` 가 0건이다(결정 IR7) |
| T25-136 | 정 | **교차 파일 일치** — `hub_template.html` 의 `DASHBOARD_REFRESH_HOOK_NAME = '<X>'` 에서 뽑은 `<X>` 가 `dashboard_template.html` 의 `window.<X> =` 와 같다. 값을 하드코딩 비교하지 않고 **양쪽에서 추출해 비교**한다(선례: T25-1 의 `HUB_FILE_COUNT` vs 실제 파일 수, T25-84 의 3중 시간 일치) |
| T25-136 | 정 | `hub/README.md` 에 즉시 갱신 서술 토큰이 있고, 옛 단정 문구 "이 갱신 메커니즘 자체는 한 줄도 바뀌지 않는다" 가 **사라졌다**(LG1 계열 역방향) |

### 뮤테이션 검증 (구현 중 1회 — 검사가 실제로 실패할 수 있는지 확인)

각각 주입 → 해당 검사 1건만 실패 → 되돌림:

1. 훅 노출 줄을 `if(!hasPipSupport)` 뒤로 옮긴다 → T22-146 실패
2. `refreshButton.addEventListener('click', pollNow)` 로 바꾼다(익명 래퍼 제거) → T25-134 실패
3. `setInterval(function(){ … pollNow(false); }, POLL_INTERVAL_MS)` 로 바꾼다 → T25-133 실패
4. 허브 쪽 상수를 `'dzRefreshNow'` 로 오타 낸다 → T25-136 실패
5. `if(isExplicitRequest)` 를 지워 폴백을 무조건으로 만든다 → T25-135 실패

### 수동 확인 (자동화 불가 — 브라우저 실측)

DevTools 네트워크 탭을 열고 `dashboard.html` 요청만 필터한다.

- [ ] S1: 패널 열고 새로고침 1회 → `dashboard.html` 요청 **1회**
- [ ] S2: 로그 카드를 끝까지 스크롤 → 새로고침 → **스크롤 위치 유지**
- [ ] S3: 다른 앱 갔다 오기 → 요청 1회, 스크롤 유지
- [ ] S4: 패널 닫고 새로고침 3회 → `dashboard.html` 요청 **0회**
- [ ] S5: 티어 2 카드(빈 상태) 열고 새로고침 → 요청 0회
- [ ] S6: 2분 방치 → iframe 요청이 자체 폴링분(2회)뿐
- [ ] S7: 같은 카드 재클릭 3회 → 요청 0회(OC2 유지)
- [ ] E9: 탭을 숨겼다 되살리기 → 요청이 **2회가 아니라 1회**(`busy` 흡수 확인)
- [ ] S8: 사본에서 훅 줄만 지운 `dashboard.html` 을 띄우고 ⓐ 새로고침 → 재로딩(흰 플래시 없음)
      ⓑ 포커스 복귀 → **아무 일도 없음**
- [ ] E4: 카드를 누른 직후(로딩 중) 새로고침 연타 → 재로딩이 반복되지 않는다

---

## 리스크와 완화책

| # | 리스크 | 완화 |
|---|--------|------|
| R-1 | 훅 이름 오타 → 전 사용자가 조용히 폴백 경로로 떨어진다(화면상 티가 안 난다) | T25-136 교차 추출 비교. 하드코딩 비교를 쓰지 않는 이유이기도 하다 |
| R-2 | ③에서 요청이 2배가 된다 | `busy` 가 흡수함을 수동 확인 항목(E9)으로 실측. 결정 IR2 에 근거 기록 |
| R-3 | 옛 세대 파일에서 새로고침이 스크롤을 날린다 | 의도된 트레이드오프. ①에만 한정(IR5)하고 README 「알려진 한계」에 명시 |
| R-4 | `pollNow` 직결로 IR5 가 무력화 | GOTCHA 2 + T25-134 역방향 + 뮤테이션 2 |
| R-5 | iframe 안에 포커스를 둔 채 창을 떠났다 오면 top window 가 `focus` 를 못 받아 **허브 카드**가 갱신되지 않는다 | 기존 동작이며 이번 범위 밖(그 경우 iframe 은 자기 `focus` 로 갱신된다). 인터벌 폴링이 최대 60초 안에 따라잡는다 |
| R-6 | 패널 IIFE 가 커져 T25-89 의 `snapshot` 스캔 범위가 넓어진다 | 검사 방식이 "범위 안 0건"이라 범위가 넓어질수록 **더 엄격해진다**. 완화 불필요 |

---

## YAGNI 보류 (지금 만들지 않는다 + 재방문 트리거)

| 보류 항목 | 재방문 트리거 |
|-----------|---------------|
| 훅에 반환값(갱신 성공 여부)·인자 추가 | 허브가 갱신 결과에 따라 화면을 바꿔야 할 요구가 생기면 |
| `postMessage` 기반 양방향 프로토콜 | 패널 iframe 이 크로스 오리진이 될 일이 생기면(현재 구조상 없음) |
| 훅 호출 실패 시 재시도 | 실패가 관측되면. 지금은 실패할 수 있는 지점 자체가 없다 |
| 사용량 패널 토글의 즉시 폴링에도 nudge | 사용자가 요청하면(요구서에서 명시적으로 범위 밖) |
| iframe 자체 60초 폴링 제거 | 요청 부담이 실제로 측정되면. 지금은 백스톱으로 필요하다 |
| 옛 세대 대시보드 자동 갱신 안내 배너 | 구세대 파일이 실사용에서 문제를 일으키면 |

---

## 검토했으나 채택하지 않은 대안

| 대안 | 기각 이유 |
|------|-----------|
| **A1. `postMessage` 핸드셰이크** | 같은 오리진이라 함수 노출로 충분하다(전제 4). 양쪽에 리스너·메시지 스키마·타임아웃이 생기고, 기능 감지가 "응답이 왔는가"라는 비동기 판정이 되어 폴백 시점을 정하기 어려워진다 |
| **A2. 패널 IIFE 가 트리거 3종을 직접 구독** | 이벤트 없이 끝나 단순해 보이지만, "무엇이 즉시 폴링인가"의 출처가 두 IIFE 로 갈라진다. 한쪽만 바뀌면 조용히 발산하고, 렌더 IIFE 의 `visibilityState` 조건 같은 세부가 복제된다 |
| **A3. 훅 없이 항상 iframe 재로딩** | 구현이 가장 짧지만 스크롤 손실이 **상시화**된다. 부분 치환이라는 대시보드의 기존 장점을 버린다 |
| **A4. 이벤트 무페이로드 + 폴백을 3종 모두에** | `dzh:rendered` 관용구와 완전히 같아진다는 이점이 있으나, 옛 세대 사용자에게 "탭 전환마다 스크롤 초기화"라는 순회귀를 만든다(결정 IR5) — 승인 항목 1 의 대안 |
| **A5. `MutationObserver` 로 허브 갱신을 감지** | 결정 OC8 이 이미 같은 이유로 기각했다(무엇이 왜 바뀌었는지 알 수 없고, 폴링·틱·드래그 재렌더를 구분하지 못한다) |

---

## 구현 순서 (마일스톤)

각 단계는 **검증 가능한 기준**을 갖는다.

| # | 작업 | 검증 |
|---|------|------|
| M1 | `commands/dashboard_template.html` — 훅 1줄 + 주석, 머리 주석 블록 | `/dashboard init` 로 파일 생성 → 서버 모드로 열고 콘솔에서 `typeof window.dzRequestRefresh === 'function'` 가 `true`. `file://` 로 열면 `'undefined'` |
| M2 | `hub/bin/hub_template.html` 렌더 IIFE — 상수 + `pollNow` + 리스너 3 | 콘솔에서 `document.addEventListener('dzh:refresh-requested', e=>console.log(e.detail))` 후 버튼/포커스/탭 전환 → `{isExplicitRequest:true/false/false}` |
| M3 | `hub/bin/hub_template.html` 패널 IIFE — 상수 2 + 함수 + 리스너 | 수동 확인 S1~S7·E9 통과 |
| M4 | 옛 세대 폴백 실측 | 훅 줄만 지운 사본으로 S8 통과 |
| M5 | 문서 4종(`hub_template.html` 머리 주석 · `dashboard_template.html` 머리 주석 · `hub/README.md` · `commands/dashboard.md`) + `README.md` 줄 수 실측 갱신 | `wc -l commands/dashboard_template.html commands/dashboard.md` 값이 README:139 와 일치 |
| M6 | `tests/run.sh` — T22-145~147 · T25-131~136 신설, 그룹 헤더의 범위 표기(`T22-1~T22-144` → `~147`, `T25-1~T25-130` → `~136`) 갱신 | `bash tests/run.sh` → 24/24 |
| M7 | 뮤테이션 검증 5건 | 각 주입에서 해당 검사 1건만 실패 |

커밋은 저장소 관례대로 주제별로 나눈다 — 템플릿 변경(M1~M4)과 문서(M5)를 묶고, `tests/run.sh`
신설(M6~M7)을 별도 커밋으로 두는 것이 선례(0ba6f8c)와 일치한다.

---

## 승인 요청 항목

### 한눈에 보기

| # | 항목 | 권고 |
|---|------|------|
| 1 | 훅 없는 옛 세대 파일의 **폴백 재로딩 범위** | **새로고침 버튼(①)에만.** ②·③ 은 no-op |
| 2 | 이벤트에 `detail:{isExplicitRequest}` **페이로드를 싣는다** | 싣는다(항목 1 을 위한 최소 정보) |
| 3 | 훅 이름 | `window.dzRequestRefresh` |

### 승인 항목 1 — 폴백 재로딩을 **새로고침 버튼에만** 한정한다 (결정 IR5)

요구서는 "훅이 없으면 재로딩으로 폴백한다"를 3종 전체에 적용하는 것으로 읽힌다. 그대로 하면
옛 세대 대시보드를 띄운 사용자는 **탭·창을 전환할 때마다 읽던 위치를 잃는다** — 오늘은 일어나지
않는 일이므로 순수한 회귀다. 그래서 요구서의 근거 문장("명시적 갱신 요청이므로 스크롤 손실
용인")이 실제로 성립하는 ①에만 폴백을 둘 것을 권고한다.

- **채택 시**: 옛 세대에서 ②·③ 은 오늘과 동일(회귀 0), ①은 확실히 갱신됨. 이벤트에 boolean 1개 필요.
- **미채택 시(요구서 문면 그대로)**: 코드가 조금 더 짧아지고(페이로드 불필요, 승인 항목 2 도 함께
  소멸) 옛 세대도 모든 트리거에서 최신이 된다. 대신 위 회귀를 받아들인다.

### 승인 항목 2 — 이벤트 페이로드 도입 (결정 IR3)

결정 OC8 이 `dzh:rendered` 에 대해 세운 "값을 싣지 않는다" 관용구에서 벗어난다. 취지(스냅샷
데이터 격리)는 유지되지만 **관용구 자체는 깨진다.** 승인 항목 1 을 채택하지 않으면 이 항목도
자동으로 소멸한다(`new Event` 로 통일).

### 승인 항목 3 — 훅 이름 `window.dzRequestRefresh` (결정 IR4)

대시보드 접두 `dz` + 축약 없는 동사구. 이 이름은 **한 번 배포되면 되돌리기 어렵다** — 이미 배포된
`dashboard.html` 파일들이 옛 이름을 갖고 있고, 허브는 새 이름을 못 찾아 전부 폴백으로 떨어지기
때문이다. 대안: `dzRefreshNow`(더 짧다), `dzRequestImmediateRefresh`(더 명시적, 다소 길다).
