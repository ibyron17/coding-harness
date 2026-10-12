# 허브 — 폴링 가시성 게이트 제거 + 낡은 탭의 세대 자가 치유 (PRP)

- **대상**: `hub/bin/hub_template.html`, `hub/bin/hub_model.py`, `hub/bin/hub_collect.py`, `hub/README.md`, `tests/run.sh`, `tests/hub/test_hub_model.py`, `tests/hub/test_hub_collect.py`
- **결정 접두**: `SH`(Self-Heal) — 기존 접두(SP·OC·GN·PV·DG·RV·ZG·UT·EX·LG·MD·MS·ON·TR·WT·IR)와 충돌 없음(`docs/prps/` 전수 확인)
- **선행 정본**: [hub-panel-immediate-refresh.md](hub-panel-immediate-refresh.md)(IR1~IR9) · [hub-dashboard.md](hub-dashboard.md)(서버·요청 구동 수집) · [hub-detail-side-panel.md](hub-detail-side-panel.md)(불변식 H1⁗)
- **검증 명령**: `bash tests/run.sh` (기대: 24/24)

---

## 요구사항 요약

독립적인 갱신 안정성 결함 2건을 함께 고친다. 둘 다 "화면에 떠 있는 허브 탭이 실제로는 갱신되지
않는다"는 같은 증상으로 나타나지만 원인은 다르다.

**결함 1 — 보이는 탭이 폴링을 멈춘다.** 60초 인터벌 폴링에는
`if(document.visibilityState==='visible')` 게이트가 걸려 있다(`hub_template.html:1500`). 일부
환경(내장 브라우저에서 재현 확인)이 **실제로 보이는 탭을 `'hidden'` 으로 오보고**하여, 듀얼
모니터 보조 화면에 띄워 둔 허브가 폴링 0회로 영구히 멎는다. 게이트를 제거해 인터벌이 가시성과
무관하게 항상 폴링하게 한다.

**결함 2 — 탭이 옛 스크립트에 영구히 갇힌다.** 허브 폴링은 받아온 HTML 에서 `#dzh-data` JSON 만
꺼내 쓰고 스크립트는 페이지 리로드 전까지 불변이다(`hub_template.html:1471-1473`). 설치본을
갱신하면(`hub/install.sh --force` → `/hub server restart`) 열려 있던 탭은 새 `hub.html` 의
데이터만 받아먹으면서 **옛 세대 스크립트로 계속 돈다** — 지금까지는 사용자가 수동 새로고침으로
해결했다. 렌더한 템플릿의 세대 스탬프를 `#dzh-data` 에 실어, 폴링이 받아온 스탬프가 실행 중인
문서의 것과 다르면 `location.reload()` 로 1회 자가 치유한다.

### 사용자 스토리

```
허브를 보조 모니터에 상시 띄워 두는 사람으로서,
탭이 화면에 보이는 한 계속 갱신되고, 허브를 업데이트하면 그 탭이 스스로 새 코드로
갈아타기를 바란다. 그래야 "화면은 켜져 있는데 값은 30분 전 것"이라거나
"새 기능을 넣었는데 이 탭에서만 안 보인다"를 사람이 눈치채고 손으로 고칠 필요가 없다.
```

### 성공 기준 (검증 가능한 형태)

| # | 기준 | 확인 방법 |
|---|------|-----------|
| S1 | 탭을 숨긴 채 3분 방치하면 `hub.html` 요청이 **3회 안팎** 발생한다 | DevTools 네트워크 (현재 실측: 0회) |
| S2 | `visibilityState` 를 `'hidden'` 으로 오보고하는 환경에서도 S1 이 성립한다 | 내장 브라우저 실측 |
| S3 | 즉시 폴링 3종(버튼·focus·visibilitychange)의 동작이 한 글자도 바뀌지 않는다 | `pollNow(true/false)` 호출 3건 유지, T25-134 |
| S4 | `hub_template.html` 을 1바이트 고치고 서버를 재기동하면, 열려 있던 탭이 **60초 안에 스스로 리로드**된다 | 탭 방치 후 관찰 |
| S5 | 템플릿을 고치지 않은 재설치(`install.sh --force` 재실행)로는 **아무 탭도 리로드되지 않는다** | 스탬프가 내용 기반이므로 불변 |
| S6 | 스탬프가 계속 불일치해도 리로드는 **대상 스탬프당 1회**로 끝난다 | 서버가 옛 HTML 을 고정 서빙하도록 조작 |
| S7 | 오프라인(fetch 실패) 중에는 어떤 리로드도 일어나지 않는다 | 서버 종료 후 5분 방치 |
| S8 | 스탬프 없는 구세대 응답을 받은 신세대 탭은 리로드하지 않는다 | `template_stamp` 를 지운 `hub.html` 사본 |
| S9 | 열린 상세 패널의 즉시 갱신 계약(IR1~IR8)이 그대로다 | T25-131~137 전부 통과 |
| S10 | `bash tests/run.sh` 가 24/24 | 명령 실행 |

---

## 확정된 전제 (재론하지 않는다)

코드를 직접 읽어 확정한 사실이다. 구현 중 다시 검증하지 않는다.

1. **인터벌 게이트는 한 곳뿐이다** — `hub_template.html:1500`. 즉시 폴링 3종(1505~1507행)은
   별도 리스너이며 게이트를 공유하지 않는다.
2. **`file://` 분기는 이 변경의 사정권 밖이다** — 렌더 IIFE 는 1450~1457행에서 조기 return
   하므로 `poll`·`pollNow`·자가 치유 코드가 아예 존재하지 않는 실행 경로다. 그 모드는 이미
   포커스 복귀 때마다 `location.reload()` 를 한다(1452~1455행).
3. **`poll()` 은 응답 텍스트를 `DOMParser` 로 파싱해 `#dzh-data` 만 꺼낸다**(1471~1473행).
   스크립트·CSS·마크업은 그 어떤 경로로도 교체되지 않는다 — 이것이 결함 2 의 구조적 원인이다.
4. **`snapshot` 변수는 폴링 성공마다 통째로 재대입된다**(1473행). 문서 자신의 스탬프를 그
   변수에서 뒤늦게 읽으면 이미 덮어써진 값을 읽는다(결정 SH7 의 근거).
5. **`render_hub_html` 은 `#dzh-data` 블록 하나만 치환한다**(`hub_model.py:97-99`). 템플릿의
   머리 주석 13~15행이 이것을 "나머지는 정적이다"로 명시한 계약이다.
6. **`#dzh-data` 의 내용은 `HubSnapshot` 을 `asdict` 한 것 그 자체다**(`hub_model.py:89`).
   머리 주석 14행이 "HubSnapshot 을 그대로 담는다(snake_case 그대로)"로 못 박았다.
7. **쓰기 게이트는 스냅샷만 본다** — `_run_collect_cycle` 의
   `content_key = snapshot_content_key(snapshot)`(`hub_server.py:180-181`)은 템플릿을 전혀
   모른다. 즉 **템플릿만 바뀐 경우 `hub.html` 은 다시 쓰이지 않는다**(잠복 결함, 결정 SH4 가
   부수적으로 해소한다).
8. **템플릿은 렌더할 때마다 디스크에서 새로 읽힌다**(`hub_collect.py:473`) — 상주 서버가 옛
   파이썬 코드를 메모리에 들고 있어도 템플릿만은 최신본이 쓰인다.
9. **서버 응답에는 `Cache-Control: no-store` 가 붙고 본문은 디스크에서 직접 나온다**
   (`hub_server.py:111,138`). 정상 경로에서 리로드는 1회로 수렴한다.
10. **저장소 접근은 감싸는 것이 이 파일의 관례다** — `readStoredProjectOrder`(826~833행) ·
    `persistProjectOrder`(836~841행) · `readStoredUsageCollapsed`(1220~1227행) 전부
    `try/catch` 다. 사유도 코드에 적혀 있다("저장소 차단", "`file://` 등에서 던질 수 있어").
11. **업데이트 절차는 2단계로 문서화돼 있다** — `hub/install.sh --force` 다음
    `/hub server restart`(`hub/README.md:86-92`). 재기동하면 `_SnapshotRefresher._last_content_key`
    가 `None` 으로 초기화되므로 **첫 사이클이 반드시 `hub.html` 을 다시 쓴다**.
12. **파이썬 단위 테스트는 `HubSnapshot` 을 여러 파일에서 생성한다**(7개 파일 17곳). 기본값을
    가진 필드를 **끝에** 추가하는 것은 그 전부에 무해하다(전수 확인). 렌더 결과를 통째로
    문자열 비교하는 테스트는 없다(`test_hub_model.py:39-82` 확인).

### 비목표 (이번 범위 밖 — 명시적으로 건드리지 않는다)

- **`commands/dashboard_template.html` 은 한 줄도 바꾸지 않는다.** 대시보드는 자기 폴링에 원래
  게이트가 없었고 세대 문제도 다른 방식(`/dashboard` 재실행)으로 해소된다.
- **SSE·WebSocket 등 푸시 방식은 기각됐다**(사용자 결정). 폴링 구조 자체를 바꾸지 않는다.
- **즉시 폴링 3종(`pollNow`)의 배선을 건드리지 않는다** — `IMMEDIATE_REFRESH_EVENT_NAME` ·
  `pollNow(isExplicitRequest)` · `refreshOpenPanelDocument` · `window.dzRequestRefresh` 는 전부
  현행 유지(결정 IR1~IR8).
- **패널 IIFE 는 한 줄도 바꾸지 않는다**(결정 SH10).
- **리로드 후 상태 복원(열린 패널·스크롤 위치)을 하지 않는다.** 템플릿 갱신 시 1회성 비용으로
  수용된 트레이드오프다(사용자 결정).
- **30초 틱(`setInterval(render, TICK_MS)`)은 대상이 아니다** — 로컬 재계산이라 네트워크를 쓰지
  않고, 애초에 게이트가 없다.
- **사용량 패널 토글의 즉시 폴링**(1383행)도 대상이 아니다.

---

## 영향 범위

### 수정 파일 (6개 + 이 문서)

| 파일 | 변경 | 이유 |
|------|------|------|
| `hub/bin/hub_model.py` | `HubSnapshot` 에 필드 1개 + 주석 | 스탬프의 계약상 자리(결정 SH4) |
| `hub/bin/hub_collect.py` | `import hashlib`, 상수 1 + 함수 1(`read_template_stamp`), `collect_snapshot` 에서 1필드 채움 | 스탬프 계산(I/O 레이어) |
| `hub/bin/hub_template.html` | 렌더 IIFE: 상수 1 + 포획 변수 1 + 함수 3 + `poll()` 성공 경로 3줄 + `setInterval` 1줄 개정, 머리 주석 1블록, 게이트 주석 블록 재작성 | 게이트 제거 + 자가 치유 |
| `hub/README.md` | 특징 1항목 · 서버 절 2항목 개정 + 자가 치유 서술 1항목 + 「알려진 한계」 1항목 | 서술이 거짓이 된다(결정 SH11) |
| `tests/run.sh` | T25-119 개정(역방향화) · T25-133 앵커 재고정 · T25-138~T25-142 신설 · 그룹 헤더 범위 표기 | 회귀 기계 검사 |
| `tests/hub/test_hub_model.py`, `tests/hub/test_hub_collect.py` | 케이스 신설(순수 로직) | 스탬프 결정성·쓰기 게이트 참여 |

### 미영향 — 건드리지 않는 이유 (직접 확인함)

| 대상 | 왜 안 건드리나 |
|------|----------------|
| `hub/bin/hub_server.py` | `snapshot_content_key` 를 그대로 부르는데, 스탬프가 `HubSnapshot` 필드라 **호출부 수정 없이** 쓰기 게이트에 자동 편입된다(결정 SH4) |
| `commands/dashboard_template.html` · `commands/dashboard.md` | 비목표. 갱신 훅 계약(IR4)의 양쪽 모두 불변 |
| 패널 IIFE(1510~1749행) | 자가 치유는 렌더 IIFE 안에서 완결된다(결정 SH10). T25-89 의 `snapshot` 스캔 범위에 새 코드가 들어가지 않는다 |
| `hub/bin/hub_parse.py`·`hub_project.py`·`hub_session.py`·`hub_usage.py` | 스냅샷 조립 로직이 그대로다. 스탬프는 프로젝트 데이터가 아니다 |
| `hub/install.sh` | 파일 수(`HUB_FILE_COUNT=10`)가 그대로다 — 새 파일이 없다 |
| 저장소 루트 `README.md` | 허브 파일의 줄 수를 싣지 않는다(커맨드 표만 있다) |
| `hub_daemon.py` · `hub_hook.py` | 서버 수명·훅 경로에 변화가 없다 |

---

## 결정 기록

### 결정 SH1 — 게이트 제거는 **인터벌 한 줄**에서만. 형태는 맨몸 함수 참조다

```js
// 변경 전 (1500행)
setInterval(function(){ if(document.visibilityState==='visible') poll(); }, POLL_INTERVAL_MS);
// 변경 후
setInterval(poll, POLL_INTERVAL_MS);
```

맨몸 참조가 안전한 이유: `setInterval` 은 추가 인자를 주지 않는 한 콜백을 **인자 없이** 부른다.
`poll()` 은 매개변수가 없으므로 GOTCHA 2(IR 정본 — 리스너에 `pollNow` 를 직접 넘기면 이벤트
객체가 첫 인자로 들어간다)가 성립하지 않는다. 같은 파일 1448행의 `setInterval(render, TICK_MS)`
가 이미 세운 관용구이므로 새 형태를 만들지 않는다.

**즉시 폴링 3종(1505~1507행)은 손대지 않는다.** 그쪽 `visibilityState` 검사는 게이트가 아니라
"visible 로 **복귀**했다"는 사건 판별이다 — 지우면 숨겨질 때도 폴링하게 되어 의미가 뒤집힌다.

### 결정 SH2 — 비용 근거를 코드가 아니라 이 문서에 남긴다

게이트 제거의 비용은 셋이고, 전부 상한이 잡혀 있다.

| 항목 | 상한 | 근거 |
|------|------|------|
| 브라우저 타이머 | 분당 1회를 **넘을 수 없다** | Chrome 의 intensive throttling 은 숨은 페이지의 타이머를 5분 뒤 분당 1회로 제한한다. 우리 주기가 이미 60초라 스로틀링은 우리를 **늦출 수만 있고 빠르게 하지 못한다** |
| 네트워크 | 루프백 fetch 1회/분(`hub.html` 약 136KB) | 같은 머신, `no-store`, 압축 없음 |
| 서버 | 수집 사이클 1회/분/탭 | 요청 구동 수집(신선도 창 2초). 탭이 없을 때의 배경 바닥은 5분이므로, 열린 탭 1개당 시간당 12회 → 60회로 는다. 한 사이클은 수십 ms(`hub/README.md` 서버 절) |

**선례가 판단을 뒷받침한다**: 상세 패널의 `dashboard_template.html` 폴링은 처음부터 게이트 없이
돌았고 문제가 보고된 적이 없다(`hub/README.md:263-264`).

부수 효과 하나를 인지하고 받아들인다 — **숨은 탭이 서버 수집을 계속 이끈다.** 이는 손실이
아니라 이득이다: 배경 수집 상한(5분)까지 떨어지던 신선도가 60초로 유지되고, "서버 연결 끊김"
표시도 탭이 숨겨진 동안 즉시 나타난다(오늘은 폴링이 멎어 감지 자체가 안 된다).

### 결정 SH3 — 스탬프의 원천은 **템플릿 파일 바이트의 SHA-256 앞 16자리**

```python
TEMPLATE_STAMP_LENGTH = 16

def read_template_stamp() -> str:
    """hub_template.html 바이트의 SHA-256 앞 16자리. 이 파일이 곧 '세대'다."""
```

세 후보를 실제 실패 모드로 비교했다.

| 후보 | 결정성 | 치명적 실패 모드 | 판정 |
|------|--------|------------------|------|
| **파일 내용 해시** | 완전 결정적 — 같은 바이트면 같은 값 | 없음 | **채택** |
| 파일 mtime | **비결정적** — `install.sh` 의 `cp` 가 내용과 무관하게 mtime 을 현재 시각으로 갱신한다 | 내용이 한 글자도 안 바뀐 재설치가 `content_key` 를 흔들어 `hub.html` 을 다시 쓰고, **열려 있던 모든 탭을 이유 없이 리로드**시킨다(성공 기준 S5 의 정확한 반대) | 기각 |
| 수동 버전 상수 | 결정적 | **올리는 것을 잊으면 기능이 조용히 죽는다.** "올렸는가"는 기계 검사가 불가능하다 — 훅 이름 오타(리스크 R-1, IR 정본)와 같은 부류의, 화면상 티가 안 나는 결함이다 | 기각 |

- **바이트를 해싱한다**(`read_text` 아님) — "같은 세대"의 정의는 바이트 동일성이다. 인코딩·개행
  해석이 끼어들 여지를 없앤다.
- **16자리로 자르는 이유는 크기가 아니라 가독성**이다(64→16자, 48바이트 절감은 무의미하다).
  DevTools 에서 눈으로 대조할 수 있는 길이이면서, 실제로 공존하는 템플릿 세대가 많아야 수십 개인
  상황에서 충돌 확률은 사실상 0 이다.
- **메모이즈하지 않는다.** 디스크의 변화를 재기동 없이 감지하는 것이 목적이므로 매 수집마다
  다시 읽는다. 비용은 이미 프로젝트마다 `dashboard.html` 전체를 읽는 `collect_snapshot` 안에서
  잡음 수준이다(측정 없는 최적화를 하지 않는다는 전역 지침의 적용).

### 결정 SH4 — 스탬프의 자리는 **`HubSnapshot.template_stamp`**(=`#dzh-data` JSON 필드)

```python
@dataclass(frozen=True)
class HubSnapshot:
    ...
    usage: UsageSample | None = None
    rate_limit_resets: RateLimitResets | None = None
    template_stamp: str = ""    # 이 페이지를 렌더한 hub_template.html 의 세대(결정 SH3)
```

세 후보가 있었고, **두 개의 문서화된 계약**이 선택을 결정했다(전제 5·6).

| 후보 | 계약 A: `#dzh-data` == `HubSnapshot` | 계약 B: `render_hub_html` 은 이 블록 **하나만** 치환 | 판정 |
|------|---|---|------|
| **`HubSnapshot` 필드** | 지킨다 | 지킨다 | **채택** |
| `render_hub_html` 이 payload 에 키를 덧붙임 | **깬다**(스냅샷에 없는 키가 생긴다) | 지킨다 | 기각 |
| `<html data-…>` 속성 · 별도 `<script>` 요소 | 지킨다 | **깬다**(두 번째 치환 마커가 생긴다) | 기각 |

추출 방식도 이 선택으로 함께 정해진다 — **기존 `#dzh-data` 추출 경로를 그대로 쓴다.** `poll()`
은 이미 `DOMParser` 로 응답을 파싱해 `#dzh-data` 를 꺼내고 있으므로(전제 3) 새 추출 관용구가
0개다. 정규식으로 원문에서 긁는 두 번째 방식을 만들지 않는다.

**부수 효과 — 잠복 결함 하나가 함께 닫힌다.** 전제 7 대로 `snapshot_content_key` 는 템플릿을
모른다. 즉 "템플릿만 바뀐" 경우 서버가 `hub.html` 을 영영 다시 쓰지 않는다. 스탬프가
`HubSnapshot` 필드가 되면 `asdict` 를 거쳐 그 키에 자동 편입되므로(`hub_model.py:81-83` 은
`collected_at_ms` 만 pop 한다) **`hub_server.py` 를 한 줄도 고치지 않고** 이 구멍이 막힌다.
`hub.html` 의 내용은 사실 `f(템플릿, 스냅샷)` 인데 키가 스냅샷만 보던 것이 원래 부정확했던
것이므로, 이것은 우회가 아니라 정정이다.

### 결정 SH5 — 템플릿 읽기 실패는 `""` 로 흡수한다. 보고 지점은 `write_hub_html` 하나다

```python
    try:
        return hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest()[:TEMPLATE_STAMP_LENGTH]
    except OSError:
        return ""
```

예외를 올리면 **행동이 퇴행한다**: 오늘은 템플릿이 없어도 "쓸 필요가 없는 사이클"은 성공한다
(`needs_write` 가 거짓이면 `write_hub_html` 을 아예 부르지 않는다). 여기서 던지면 그 사이클까지
실패로 뒤집힌다.

"조용히 삼킨다"는 비판이 성립하지 않는 이유: **`""` 는 렌더된 `hub.html` 에 도달할 수 없다.**
쓰기가 실제로 일어나는 경로는 반드시 `write_hub_html` 을 지나고, 그 함수는 같은 파일을 다시
읽어 실패하면 `HubCollectError` 로 사유를 명시한다(`hub_collect.py:472-475`). 실패는 그대로
`record_collect_failure` → `/hub status` 로 드러난다. 보고 창구를 둘로 늘리지 않을 뿐이다.

### 결정 SH6 — 비교 규칙: **받아온 스탬프가 비어 있지 않고, 문서의 것과 다를 때만** 리로드

세대 전환기에는 스탬프의 유무가 양방향으로 어긋난다. 진리표로 규칙을 고정한다.

| 문서 스탬프 | 받아온 스탬프 | 동작 | 왜 |
|---|---|---|---|
| `'abc'` | `'abc'` | no-op | 같은 세대 |
| `'abc'` | `'xyz'` | **리로드** | 서버가 다른 세대를 서빙한다 — 목표 상황 |
| `'abc'` | 없음/`''` | **no-op** | 서버가 자기 세대를 말해 주지 못한다(구세대 파이썬). **정보 없음은 사건이 아니다** |
| 없음/`''` | `'xyz'` | **리로드** | 실재하는 조합이다 — `install.sh --force` 만 하고 재기동을 안 하면 새 템플릿(=자가 치유 코드 있음)이 구세대 파이썬(=필드 없음)의 데이터와 함께 실린다. 재기동 뒤 이 탭이 영구 미치유로 남는 것을 막는다 |
| 없음/`''` | 없음/`''` | no-op | 양쪽 다 구세대 — 할 일 없음 |

한 줄로: `freshStamp !== '' && freshStamp !== loadedTemplateStamp`. 비대칭이 의도적이며, 대칭
비교(`!==` 만)를 쓰면 3행에서 **불필요한 리로드 1회**가 발생한다.

**부트스트랩 한계를 명시한다**: 이 기능을 처음 배포하는 순간 **이미 열려 있던 탭들은 치유되지
않는다**(그 탭의 스크립트에 비교 코드 자체가 없다). 자가 치유는 이번 세대 이후의 업데이트부터
효력이 있다. `hub/README.md` 에 이 한계를 적는다(결정 SH11).

### 결정 SH7 — 문서 자신의 스탬프는 **IIFE 초기화 시점에 1회 포획**한다

```js
var snapshot = initialDataParse.snapshot;
// 이 문서를 렌더한 템플릿의 세대. snapshot 은 폴링 성공마다 통째로 갈리므로(1473행) 여기서
// 한 번 포획해 둔다 — 뒤늦게 snapshot 에서 읽으면 방금 받아온 값을 자기 값으로 착각한다.
var loadedTemplateStamp = snapshot.template_stamp || '';
```

전제 4 가 이 결정의 전부다. 포획하지 않고 비교 시점에 `snapshot.template_stamp` 를 읽으면, 그
시점의 `snapshot` 이 이미 새 값일 수 있어 **항상 자기 자신과 비교하게 되어 기능이 조용히
죽는다.** 포획 변수를 두면 비교 코드가 `poll()` 안 어디에 놓이든 정확하다.

`|| ''` 로 정규화하는 이유: 구세대 데이터에서는 `undefined` 이고, `parseSnapshotJson` 이 실패한
경우엔 `{}` 라 역시 `undefined` 다(816~823행). 이후 로직이 `''` 하나만 "없음"으로 다루게 한다.

### 결정 SH8 — 비교 지점은 `poll()` 성공 경로의 **`#dzh-data` 파싱 직후 · `snapshot` 재대입 직전**

```js
      .then(function(html){
        consecutiveFailureCount = 0;
        connectionLost = false;
        lastPollSuccessAtMs = Date.now();
        if(html === lastHtml){ renderConnectionStatus(); return; }   // 기존 그대로
        lastHtml = html;
        var fresh = new DOMParser().parseFromString(html, 'text/html');
        var freshData = fresh.getElementById('dzh-data');
        if(freshData){
          var freshSnapshot = JSON.parse(freshData.textContent || '{}');
          if(reloadForNewTemplateGeneration(freshSnapshot.template_stamp || '')) return;   // 결정 SH6·SH9
          snapshot = freshSnapshot;
        }
        render();
      })
```

- **성공 경로 안에만 둔다** — `.catch` 에는 비교할 응답이 없다. 오프라인·서버 다운 중에는
  리로드가 구조적으로 불가능하다(성공 기준 S7).
- **`if(html === lastHtml)` 조기 반환보다 뒤**여도 정확하다. 응답이 직전과 같다면 스탬프도 같고,
  그 값은 이미 비교를 마친 것이다. 첫 폴링은 `lastHtml === ''` 이라 반드시 통과한다.
- **`freshData` 가 있을 때만** 비교한다. 데이터 블록이 없는 응답은 정보가 없는 응답이다.
- **즉시 갱신 계약(IR1~IR8)과 간섭하지 않는다.** `pollNow` 는 `poll()` 을 부른 **직후 동기적으로**
  이벤트를 발행한다(1488~1492행) — 그 시점에 fetch 는 아직 미해결이다. 즉 패널 갱신은 항상
  리로드 판정보다 **먼저** 끝나 있다. 리로드가 그 뒤에 페이지를 버리는 것은 순서상 무해하다.
- **`busy` 가드와 무관하다.** `busy` 는 꼬리 `.then` 에서 해제되고(1481행), 그 사이 페이지는
  이미 이동 중이다. 리로드 경로에서 `busy` 를 따로 조작하지 않는다.

### 결정 SH9 — 루프 가드는 **sessionStorage 1키에 "리로드 대상 스탬프"를 적는** 방식

```js
var TEMPLATE_STAMP_RELOAD_KEY = 'dzh-template-stamp-reload-target';
```

같은 대상 스탬프를 향해 **두 번 리로드하지 않는다.** 그것이 규칙의 전부다.

```
받아온 스탬프 S 가 문서와 다르다
  → sessionStorage[KEY] === S 이면: 이미 S 를 향해 리로드해 봤고 도달하지 못했다 → 아무것도 안 한다
  → 아니면: KEY 에 S 를 쓴다. 쓰기가 성공했을 때만 location.reload() 한다
```

대안과 비교했다.

| 대안 | 문제 |
|------|------|
| **세션당 1회 제한**(불리언 마커) | 한 번 치유한 탭은 그 세션 내내 다시 치유되지 않는다. sessionStorage 는 리로드를 넘어 살아남으므로, **첫 업데이트 이후 두 번째 업데이트부터 원래 문제가 그대로 재발한다** |
| 리로드 횟수 카운터 + 상한 | 상태가 둘(횟수·시점)로 늘고 "언제 리셋하나"라는 새 질문이 생긴다. 대상 스탬프 방식은 그 질문 자체가 없다 |
| 메모리 변수 | 리로드로 소멸한다 — 루프를 막는다는 목적을 원리적으로 달성할 수 없다 |
| `localStorage` | 탭 간 공유라 한 탭의 실패가 다른 탭의 정상 치유를 막는다. 탭별 격리가 필요하다 |

**성공 시 키를 지우지 않는다.** 정상적으로 S 에 도달하면 문서 스탬프가 S 가 되어 S 와는 다시
불일치할 수 없다 — 남은 값은 무해한 잔여물이고, 다음 세대 S′ 은 저장값 S 와 다르므로 정상적으로
리로드된다. **정리 코드를 두지 않는 것이 상태를 하나 덜 만든다.**

**쓰기 성공을 리로드의 전제조건으로 삼는다.** 저장소가 막힌 환경(쿠키/저장소 차단 정책)에서
기록 없이 리로드하면 루프 종료를 보장할 수단이 사라진다. 기록에 실패하면 리로드하지 않고
오늘과 같은 상태(수동 새로고침)로 남는다 — 회귀 0, 루프 0. 저장소 접근을 `try/catch` 로 감싸는
것은 전제 10 의 관례이며, 여기서는 그 catch 가 **동작을 바꾸는 분기**이지 침묵이 아니다.

이 마커에는 부수 이득이 하나 있다: 리로드 시작 직후 다른 폴링이 같은 응답으로 다시 판정에
들어와도 저장값이 이미 S 라 두 번째 `location.reload()` 가 나가지 않는다(중복 호출 억제).

### 결정 SH10 — 자가 치유는 **렌더 IIFE 안에서 완결**한다. 이벤트를 새로 만들지 않는다

렌더 IIFE ↔ 패널 IIFE 분리(T25-89 가 기계 강제)에 저촉되는 지점이 하나도 없다:

- 새 코드는 전부 `poll()` 주변, 즉 렌더 IIFE(701~1508행) 안에 산다. **패널 IIFE(1510행 이후)에
  단 한 줄도 추가하지 않는다** — T25-89 의 `snapshot` 스캔 범위가 넓어지지 않는다.
- 패널에 알릴 것이 없다. 리로드는 문서 전체를 버리는 행위라 "패널을 갱신하라"가 무의미하다.
  `dzh:refresh-requested` 같은 새 이벤트를 만들지 않는다(YAGNI).
- `IMMEDIATE_REFRESH_EVENT_NAME` 리터럴 개수(정확히 2건, T25-131)에 영향이 없다.

### 결정 SH11 — 주석·문서 정합 (거짓말을 남기지 않는다)

게이트 제거는 **기존 문서 5곳을 즉시 거짓으로 만든다.** 전부 개정 대상이다.

| 위치 | 지금 문장 | 개정 |
|------|-----------|------|
| `hub/README.md:14-15` | "탭이 보이는 동안만 화면을 갱신하고 숨겨지면 조용히 멈춘다" | 탭 가시성과 무관하게 1분마다 갱신한다로 개정 |
| `hub/README.md:117-121` | "**탭이 보이지 않는 동안은 이 1분 타이머가 폴링 자체를 건너뛴다**(`document.visibilityState` 기준…)" | **삭제하고** 게이트를 없앤 사유(가시성 오보고 환경 실측)로 대체 |
| `hub/README.md:127-129` | "**브라우저 채널은 폴링이 도는 동안(탭이 보이는 동안)만 나타난다**" | 폴링이 항상 도므로 숨은 탭에서도 연결 끊김이 드러난다로 개정 |
| `hub/README.md:86-92`(업데이트 절차) | 재기동만 안내 | 재기동 후 열려 있던 탭이 60초 안에 스스로 새 코드로 갈아탄다는 1줄 추가 |
| `hub/README.md` 「알려진 한계」 | — | 자가 치유의 두 한계 추가: ① 이 기능 배포 이전에 열린 탭은 치유되지 않는다(결정 SH6) ② 리로드로 열린 패널·스크롤이 초기화된다 |
| `hub_template.html` 머리 주석 13~21행 | "`#dzh-data`: HubSnapshot 을 그대로 담는다", "1분 폴링(자기 URL 을 받아 문자열 전체 비교)" | `template_stamp` 가 세대 스탬프라는 조항 + 폴링에 가시성 게이트가 없다는 조항 추가 |
| `hub_template.html:1493-1499` 주석 블록 | 가시성 게이트의 도입 사유를 길게 설명 | 재작성. `hasWorkingProject` 폐기 이력은 **보존**하고(T25-119 가 그 회귀를 계속 검사한다), 가시성 게이트도 폐기됐음과 그 사유(오보고 실측)를 잇는다 |

`hub_collect.py`·`hub_model.py` 에는 각각 새 함수·새 필드의 한 줄 주석만 붙인다.

---

## 계약 (변경 후)

### 새로 생기는 계약 3개

| 이름 | 사는 곳 | 값/형식 | 짝 |
|------|---------|---------|-----|
| `HubSnapshot.template_stamp` | `hub_model.py` | `str`, 기본값 `""`. 소문자 hex 16자 또는 `""` | `#dzh-data` JSON 의 `template_stamp` 키 |
| `read_template_stamp()` | `hub_collect.py` | `() -> str`. 순수 함수가 아니다(파일을 읽는다). 예외를 던지지 않는다 | `TEMPLATE_PATH` |
| `TEMPLATE_STAMP_RELOAD_KEY` | `hub_template.html` 렌더 IIFE | `'dzh-template-stamp-reload-target'`, sessionStorage | 자기 자신(탭 로컬) |

### 공개 함수 시그니처

```python
# hub_collect.py
def read_template_stamp() -> str:
    """hub_template.html 바이트의 SHA-256 앞 16자리. 읽기 실패면 ""(결정 SH5)."""
```

```js
// hub_template.html — 렌더 IIFE, 전부 if(!isServed) return 뒤에 산다
function readReloadedTemplateStamp(): string
  // 이 탭이 직전에 리로드를 시도한 대상 스탬프. 저장소가 막혔으면 ''.

function rememberReloadTemplateStamp(stamp: string): boolean
  // 리로드 대상을 기록한다. 기록에 성공했을 때만 true — 리로드의 전제조건이다(결정 SH9).

function reloadForNewTemplateGeneration(freshTemplateStamp: string): boolean
  // 세대가 바뀌었으면 1회 자가 리로드하고 true. 아무것도 안 했으면 false.
  // true 를 받은 호출부는 그 자리에서 return 한다(결정 SH8).
```

### 구독 측 본문 (권고 형태)

```js
function reloadForNewTemplateGeneration(freshTemplateStamp){
  if(freshTemplateStamp === '') return false;                       // 정보 없음(결정 SH6)
  if(freshTemplateStamp === loadedTemplateStamp) return false;      // 같은 세대
  if(readReloadedTemplateStamp() === freshTemplateStamp) return false;   // 이미 이 대상으로 시도했다(결정 SH9)
  if(!rememberReloadTemplateStamp(freshTemplateStamp)) return false;     // 기록 실패 → 리로드하지 않는다
  location.reload();
  return true;
}
```

---

## 경계 조건 표

| # | 상황 | 판정 지점 | 동작 | 근거 |
|---|------|-----------|------|------|
| E1 | 탭이 숨겨져 있다 | 인터벌에 게이트가 없다 | 정상 폴링 | 결정 SH1 |
| E2 | 브라우저가 숨은 탭 타이머를 스로틀한다 | 브라우저 | 최대 분당 1회로 늦춰질 뿐 | 결정 SH2 |
| E3 | 허브가 `file://` 로 열렸다 | 1450행 조기 return | 게이트도 자가 치유도 존재하지 않는다 | 전제 2 |
| E4 | 오프라인·서버 다운 중 | `.catch` 경로 | 스탬프 비교 자체가 없다 | 결정 SH8 |
| E5 | 응답이 직전과 완전히 동일 | `html === lastHtml` 조기 반환 | no-op(이미 비교한 스탬프) | 결정 SH8 |
| E6 | 응답에 `#dzh-data` 가 없다 | `if(freshData)` | no-op | 결정 SH8 |
| E7 | 구세대 응답(스탬프 필드 없음) + 신세대 탭 | `freshTemplateStamp === ''` | **no-op** | 결정 SH6 3행 |
| E8 | 스탬프 없는 문서(구세대 파이썬 렌더) + 신세대 응답 | `'' !== 'xyz'` | **리로드 1회** | 결정 SH6 4행 |
| E9 | 구세대 탭(자가 치유 코드 없음) + 신세대 응답 | 코드 부재 | 아무 일도 없다 — 수동 새로고침이 필요하다 | 결정 SH6 부트스트랩 한계 |
| E10 | 리로드했는데 여전히 불일치 | `readReloadedTemplateStamp() === fresh` | 두 번째부터 no-op | 결정 SH9 |
| E11 | sessionStorage 접근이 차단됐다 | `rememberReloadTemplateStamp` 이 `false` | 리로드하지 않는다(오늘과 동일) | 결정 SH9 |
| E12 | 티어 강등(1→2)·프로젝트 소멸 등 스냅샷 변화 | 스탬프는 템플릿 바이트만의 함수 | **리로드 없음** — 데이터 변화는 세대 변화가 아니다 | 결정 SH3 |
| E13 | 템플릿 내용 그대로 재설치(`--force`) | 해시 불변 | 리로드 없음 | 결정 SH3, 성공 기준 S5 |
| E14 | `cp` 로 템플릿을 덮어쓰는 도중 부분 읽기 | 그 사이클만 다른 해시 | 최악 리로드 2회. 대상 스탬프별 1회 제한이 발산을 막는다 | 결정 SH9 |
| E15 | 템플릿 파일이 아예 없다 | `read_template_stamp` 이 `""` | 스탬프 없이 진행. 쓰기가 필요해지면 `write_hub_html` 이 사유를 명시하며 실패 | 결정 SH5 |
| E16 | `#dzh-data` 파싱 실패로 `snapshot = {}` | `loadedTemplateStamp === ''` | 신세대 응답을 만나면 리로드 1회 — 깨진 문서를 정상 세대로 되돌리는 방향이라 바람직하다 | 결정 SH7 |
| E17 | 상세 패널을 연 채 리로드된다 | — | 패널이 닫히고 스크롤이 초기화된다 | 수용된 트레이드오프 |
| E18 | 리로드 직전에 `dzh:refresh-requested` 가 발행돼 있다 | 이벤트는 동기, 판정은 비동기 | 패널 갱신이 항상 먼저 끝난다 — 간섭 없음 | 결정 SH8 |
| E19 | 같은 브라우저에 허브 탭이 여러 개 | sessionStorage 는 탭별 | 각자 독립적으로 1회씩 치유된다 | 결정 SH9 |
| E20 | `install.sh --force` 만 하고 재기동을 안 했다 | `content_key` 에 스탬프가 포함됨 | 다음 수집에서 `hub.html` 이 다시 쓰이고 탭이 치유된다 | 결정 SH4 부수 효과 |

---

## GOTCHA (구현자가 틀리기 쉬운 함정)

1. **`snapshot.template_stamp` 를 비교 시점에 읽으면 기능이 조용히 죽는다.** 그 시점의
   `snapshot` 은 이미 새 값일 수 있다(전제 4). 반드시 초기화 시점의 `loadedTemplateStamp` 와
   비교한다(결정 SH7). 화면상 아무 증상이 없는 종류의 결함이다 — T25-140 이 기계 검사한다.
2. **`setInterval` 의 `visibilityState` 만 지우고 1505행까지 건드리면 안 된다.** 1505행의
   검사는 게이트가 아니라 "visible 로 복귀"라는 사건 판별이다(결정 SH1).
3. **T25-133 의 앵커가 깨진다.** 그 검사는 `setInterval(function(){ if(document.visibilityState`
   문자열로 인터벌 줄을 찾는다(`tests/run.sh:4760`). 게이트를 지우면 **검사가 "줄을 찾지 못함"
   으로 실패한다.** 지우지 말고 새 형태에 맞춰 재고정한다 — 그 검사가 지키는 계약(IR2: 인터벌은
   `pollNow` 를 쓰지 않는다)은 여전히 유효하다.
4. **T25-119 는 게이트의 *존재*를 단언한다**(`tests/run.sh:4426`). 이번 변경으로 그 단언은
   뒤집혀야 한다. 검사를 삭제하지 말고 **역방향으로 개정**한다(게이트 부재 + `hasWorkingProject`
   부재 유지) — 삭제하면 게이트가 슬그머니 돌아와도 아무도 모른다.
5. **README 문구 토큰 2개가 T25-119 에 하드코딩돼 있다.** `'탭이 보이지 않는 동안은 이 1분
   타이머가 폴링 자체를 건너뛴다'`(존재 요구)와 `'카드가 하나도 없으면…'`(부재 요구). 앞의
   것을 README 에서 지우면서 검사도 함께 뒤집지 않으면 T25 가 실패한다.
6. **`template_stamp` 필드는 반드시 dataclass 의 맨 끝에 둔다.** 기본값 없는 필드 앞에 오면
   `TypeError` 로 임포트 자체가 깨진다. 기본값 `""` 은 기존 테스트 17곳을 살리는 조건이다(전제 12).
7. **`read_text` 가 아니라 `read_bytes` 로 해싱한다**(결정 SH3). 텍스트로 읽으면 세대의 정의가
   인코딩·개행 처리에 의존하게 된다.
8. **`rememberReloadTemplateStamp` 의 반환값을 무시하면 안 된다.** 저장 실패 시에도 리로드하면
   루프 종료 보장이 사라진다(결정 SH9).
9. **`reloadForNewTemplateGeneration` 이 `true` 면 호출부는 즉시 `return` 한다.** `snapshot` 을
   덮고 `render()` 까지 진행하면 곧 버려질 DOM 을 그리느라 리로드 직전에 한 프레임이 깜빡인다.
10. **패널 IIFE 에 아무것도 추가하지 않는다**(결정 SH10). 자가 치유는 렌더 IIFE 안에서 끝난다.

---

## 테스트 계획 — `tests/run.sh` · `tests/hub/`

### 기존 검사에 대한 영향 (전수 확인 결과)

| 검사 | 영향 | 대응 |
|------|------|------|
| **T25-119**(가시성 게이트 존재 + README 문구) | **깨진다** — 단언이 뒤집힌다 | 역방향으로 개정(GOTCHA 4·5) |
| **T25-133**(인터벌이 `pollNow` 를 쓰지 않는다) | **깨진다** — 앵커 문자열 소실 | 앵커 재고정(GOTCHA 3) |
| T25-41(`POLL_INTERVAL_MS = 60000`) | 없음 — 값 불변 | — |
| T25-131(`'dzh:refresh-requested'` 정확히 2건) | 없음 | — |
| T25-132(발행이 `pollNow` 범위 안) | 없음 — `pollNow` 본문 불변 | — |
| T25-134(`pollNow(` 3건·true 1·false 2·맨몸참조 0) | 없음 — 1505~1507행 불변 | — |
| T25-135~137(패널 갱신·훅 이름·README 토큰) | 없음 — 패널 IIFE 와 대시보드 템플릿 불변 | — |
| T25-89(패널 IIFE 에 `snapshot` 0건) | 없음 — 패널 IIFE 에 추가 코드 0줄 | 결정 SH10 |
| T25-56(`HubSnapshot` 의 usage·rate_limit_resets 필드 계약) | 없음 — 필드 추가는 그 두 줄을 건드리지 않는다 | — |
| T25-1(`HUB_FILE_COUNT=10`) | 없음 — 새 파일 없음 | — |
| T24(파이썬 단위 테스트 전체) | 없음 — 기본값 필드라 17곳의 생성자 호출이 전부 유효 | 전제 12 |
| T22 그룹(대시보드 템플릿) | 없음 — `dashboard_template.html` 불변 | 비목표 |

### 신규 검사 (정방향 + 역방향 쌍)

**T25 그룹**(`test_hub_docs_and_constants()`, T25-1~137 → 142). 그룹 헤더의 범위 표기
(`tests/run.sh:2474,2478`)를 함께 갱신한다.

| ID | 방향 | 검사 |
|----|------|------|
| T25-119(개정) | 역 | 인터벌 등록 줄에 `visibilityState` 가 **없다**(파일 전체가 아니라 그 줄로 범위를 좁힌다 — 1453·1505행의 정당한 사용을 오탐하면 안 된다). `hasWorkingProject` 부재 검사는 그대로 유지 |
| T25-119(개정) | 역 | `hub/README.md` 에서 옛 게이트 문구 2종이 **사라졌다** |
| T25-119(개정) | 정 | `hub/README.md` 에 게이트 제거 사유(가시성 오보고) 서술 토큰이 있다 |
| T25-133(개정) | 정+역 | `setInterval(poll, POLL_INTERVAL_MS)` 가 정확히 1건이고, `setInterval(pollNow` 가 0건이다(결정 IR2 를 새 형태로 계속 강제) |
| T25-138 | 정 | 3자 교차 일치 — `hub_model.py` 의 `template_stamp` 필드, `hub_collect.py` 의 `template_stamp=` 대입, `hub_template.html` 의 `template_stamp` 참조가 모두 존재한다. 이름을 **한 곳에서 뽑아 나머지에서 찾는다**(하드코딩 3중 비교를 하지 않는다 — 선례: T25-136 의 훅 이름 교차 추출) |
| T25-139 | 정+역 | `read_template_stamp()` 범위를 추출해 ① `sha256` 사용 ② `read_bytes` 사용(`read_text` 0건 — GOTCHA 7) ③ `except OSError` 로 `""` 반환(결정 SH5) 를 확인 |
| T25-140 | 정+역 | GOTCHA 1 회귀 검출 — `loadedTemplateStamp` 대입이 정확히 1건이고 그 줄 번호가 `function poll(){` 보다 **앞**이며(줄 번호 비교, 선례: T22-145/146), `reloadForNewTemplateGeneration` 범위 안에 `snapshot.template_stamp` 가 **0건**이다 |
| T25-141 | 정+역 | `reloadForNewTemplateGeneration()` 범위를 추출해 ① 빈 문자열 가드 존재(결정 SH6) ② `readReloadedTemplateStamp()` 호출 존재 ③ `location.reload()` 줄 번호가 `rememberReloadTemplateStamp(` 줄보다 **뒤**다(GOTCHA 8) ④ `location.reload()` 가 그 범위 안에 정확히 1건 |
| T25-142 | 정+역 | 문서 정합 — `hub/README.md` 에 자가 치유 서술 토큰과 「알려진 한계」 2항목 토큰이 있고, `hub_template.html` 머리 주석에 `template_stamp` 조항이 있다 |

**T24 그룹**(`tests/hub/`, 순수 로직) — 기계 검사로는 못 잡는 **행동**을 여기서 잡는다.

| 파일 | 케이스 | 검증 |
|------|--------|------|
| `test_hub_model.py` | `template_stamp` 만 다른 두 스냅샷의 `snapshot_content_key` 가 **다르다** | 결정 SH4 의 부수 효과(쓰기 게이트 편입). 선례: `test_hub_collect.py:955` 의 `is_stale` 케이스 |
| `test_hub_model.py` | `render_hub_html` 결과의 `#dzh-data` 를 파싱하면 `template_stamp` 가 그대로 나온다 | `#dzh-data` == `HubSnapshot` 계약(전제 6) |
| `test_hub_collect.py` | 같은 내용의 임시 템플릿을 두 번 읽으면 스탬프가 **같고**, 한 바이트 바꾸면 **다르다** | 결정 SH3 의 결정성 — mtime 방식이었다면 첫 단언이 깨진다 |
| `test_hub_collect.py` | `TEMPLATE_PATH` 가 없을 때 `read_template_stamp()` 가 `""` 를 돌려주고 **던지지 않는다** | 결정 SH5 |

### 뮤테이션 검증 (구현 중 1회 — 검사가 실제로 실패할 수 있는지 확인)

각각 주입 → 해당 검사 1건만 실패 → 되돌림.

1. `setInterval` 에 가시성 게이트를 되살린다 → T25-119 실패
2. `setInterval(pollNow, POLL_INTERVAL_MS)` 로 바꾼다 → T25-133 실패
3. `read_bytes` 를 `read_text().encode()` 로 바꾼다 → T25-139 실패
4. `loadedTemplateStamp` 포획을 지우고 비교를 `snapshot.template_stamp` 로 바꾼다 → T25-140 실패
5. `rememberReloadTemplateStamp` 의 반환값 검사를 지운다(호출만 하고 무조건 리로드) → T25-141 실패
6. 빈 문자열 가드를 지워 대칭 비교로 만든다 → T25-141 실패
7. `snapshot_content_key` 가 `template_stamp` 도 pop 하게 만든다 → T24 실패
8. `read_template_stamp` 이 mtime 을 쓰게 바꾼다 → T24(결정성 케이스) 실패

### 수동 확인 (자동화 불가 — 브라우저 실측)

- [ ] S1: 탭을 다른 탭 뒤로 숨기고 3분 → `hub.html` 요청 3회 안팎(현재 0회)
- [ ] S2: 가시성을 오보고하는 내장 브라우저에서 같은 절차 → 요청이 발생한다
- [ ] S3: 새로고침 버튼·포커스 복귀·탭 복귀 각각에서 열린 패널이 그 자리에서 갱신된다(IR 회귀 0)
- [ ] S4: `hub_template.html` 에 공백 1개 추가 → `hub/install.sh --force` → `/hub server restart`
      → 방치한 탭이 60초 안에 스스로 리로드된다
- [ ] S5: 템플릿을 되돌리지 않은 채 `install.sh --force` 를 한 번 더 → **리로드 없음**
- [ ] S6: `hub.html` 을 옛 사본으로 고정해 두고 스탬프만 다른 응답을 만든다 → 리로드 1회 뒤 정지
- [ ] S7: 서버를 끄고 5분 방치 → 리로드 0회, "서버 연결 끊김" 표시만
- [ ] S8: `template_stamp` 키를 지운 `hub.html` 사본 → 리로드 0회
- [ ] E17: 패널을 연 채 S4 를 반복 → 리로드 후 패널이 닫혀 있다(기대된 동작임을 확인)
- [ ] E19: 허브 탭 2개를 열고 S4 → 두 탭이 각각 1회씩 리로드된다

---

## 리스크와 완화책

| # | 리스크 | 완화 |
|---|--------|------|
| R-1 | 자가 치유가 조용히 죽는다(GOTCHA 1 — 자기 자신과 비교) | 화면상 증상이 없는 결함이라 사람 검수로는 못 잡는다. T25-140 + 뮤테이션 4 로 기계 강제 |
| R-2 | 리로드 루프 | 대상 스탬프별 1회 제한(SH9) + 저장 실패 시 리로드 금지 + `no-store` 직접 서빙(전제 9). 수동 확인 S6 로 실측 |
| R-3 | 숨은 탭이 수집을 계속 이끌어 부하가 는다 | 상한이 분당 1회로 브라우저가 강제한다(SH2). 탭당 시간당 60회 수집, 사이클당 수십 ms — 측정된 병목이 아니다 |
| R-4 | 사용자가 작업 중 갑자기 페이지가 리로드돼 놀란다 | 템플릿 업데이트 시 1회성이며 사용자가 명시적으로 `install.sh` 를 실행한 직후에만 일어난다. README 에 명시(SH11) |
| R-5 | 스탬프가 `content_key` 에 들어가 쓰기가 잦아진다 | 스탬프는 템플릿 바이트의 함수라 **업데이트할 때만** 바뀐다. 정상 운영 중에는 상수다(E12·E13) |
| R-6 | 부트스트랩 — 이번 배포로는 이미 열린 탭이 안 고쳐진다 | 원리적 한계다. 「알려진 한계」에 적고, 이번 한 번은 수동 새로고침을 안내한다 |
| R-7 | T25-119/133 을 "실패하니까" 삭제해 버린다 | GOTCHA 3·4 에 명시. 두 검사는 개정 대상이지 삭제 대상이 아니다 |

---

## YAGNI 보류 (지금 만들지 않는다 + 재방문 트리거)

| 보류 항목 | 재방문 트리거 |
|-----------|---------------|
| 리로드 전 사용자 확인 배너("새 버전이 있습니다 — 새로고침") | 자동 리로드가 실제로 작업을 방해했다는 보고가 나오면 |
| 리로드 후 열린 패널·스크롤 복원 | 위와 같은 보고가 나오면. `sessionStorage` 에 열린 프로젝트 경로를 적는 방식이 후보 |
| 스탬프를 `/hub status` 에 노출 | 세대 불일치를 CLI 로 진단할 필요가 생기면 |
| 폴링 주기를 가시성에 따라 다르게(보이면 60초·숨으면 5분) | 부하가 실제로 측정되면. 지금은 두 값을 두는 복잡도가 이득보다 크다 |
| 대시보드(`dashboard_template.html`)에도 같은 자가 치유 | 대시보드 템플릿 갱신이 실사용 문제를 일으키면(현재는 `/dashboard` 재실행이 해결한다) |
| 리로드 실패 사실을 화면에 표시 | 실패가 관측되면. 지금은 조용히 오늘의 동작으로 남는 것이 옳다 |

---

## 검토했으나 채택하지 않은 대안

| 대안 | 기각 이유 |
|------|-----------|
| **A1. 폴링이 스크립트까지 교체** | `#dzh-data` 만 갈아 끼우는 구조(전제 3)를 버리고 DOM 전체를 바꾸게 된다. 사용자 상태(순서·접힘·열린 패널·스크롤)를 지키는 불변식 H1⁗ 전체가 무너진다. 리로드가 오히려 정직하다 |
| **A2. mtime 스탬프** | 결정 SH3 — 내용이 같은 재설치가 전 탭을 리로드시킨다 |
| **A3. 수동 버전 상수** | 결정 SH3 — 올리는 것을 잊으면 조용히 죽고, 잊었는지 기계로 검사할 수 없다 |
| **A4. `<html data-…>` 속성에 스탬프** | 결정 SH4 — 두 번째 치환 마커가 생겨 "이 블록 하나만 치환한다" 계약이 깨지고, 추출 관용구도 둘이 된다 |
| **A5. 서버가 `ETag`/`Last-Modified` 로 세대를 알림** | 헤더는 `#dzh-data` 파싱 경로 밖이라 `fetch` 응답 객체를 따로 다뤄야 하고, 프록시·브라우저 캐시가 헤더를 변형할 여지가 있다. 본문 안의 값이 오해의 여지가 없다 |
| **A6. 가시성 게이트를 유지하고 `document.hasFocus()` 등으로 보강** | 오보고하는 것은 가시성 API 자체다. 같은 종류의 신호를 하나 더 얹어도 신뢰도가 오르지 않는다. 게이트가 주는 이득(분당 fetch 1회 절감)이 원래 작다 |
| **A7. SSE·WebSocket 푸시** | 사용자 결정으로 기각됨. 상주 서버에 연결 수명 관리·재연결·백프레셔가 새로 생긴다 |
| **A8. 리로드 대신 `location.replace(location.href)`** | 히스토리 항목을 남기지 않는 차이뿐인데, 폴링이 만든 리로드는 원래 히스토리를 늘리지 않는다(같은 URL). 표준적이고 읽기 쉬운 `location.reload()` 를 쓴다 |

---

## 구현 순서 (마일스톤)

각 단계는 **검증 가능한 기준**을 갖는다.

| # | 작업 | 검증 |
|---|------|------|
| M1 | `hub_model.py` — `HubSnapshot.template_stamp` 필드 + 주석 | `python3 -m unittest discover -s tests/hub -t .` 통과(기존 17곳 무영향) |
| M2 | `hub_collect.py` — `import hashlib`, `TEMPLATE_STAMP_LENGTH`, `read_template_stamp()`, `collect_snapshot` 에서 대입 | `python3 hub/bin/hub.py collect` 후 `~/.claude/hub/hub.html` 의 `#dzh-data` 에 16자 hex 가 실린다 |
| M3 | 게이트 제거 — `hub_template.html:1500` 1줄 + 1493~1499 주석 블록 재작성 | 탭을 숨기고 2분 → `hub.html` 요청 2회(수동 확인 S1) |
| M4 | 자가 치유 — 상수 1 + 포획 변수 1 + 함수 3 + `poll()` 성공 경로 개정 | 수동 확인 S4~S8 통과 |
| M5 | 문서 — `hub_template.html` 머리 주석 + `hub/README.md` 5곳(결정 SH11 표) | 옛 문구 2종이 `grep` 으로 0건 |
| M6 | `tests/hub/` — 파이썬 케이스 4건 신설 | T24 통과, 뮤테이션 7·8 로 실패 확인 |
| M7 | `tests/run.sh` — T25-119·133 개정, T25-138~142 신설, 그룹 헤더 범위 표기 갱신 | `bash tests/run.sh` → 24/24 |
| M8 | 뮤테이션 검증 8건 | 각 주입에서 해당 검사 1건만 실패 |

커밋은 저장소 관례대로 주제별로 나눈다 — **게이트 제거(M3)와 자가 치유(M1·M2·M4)는 원인도
검증 방법도 다른 별개의 변경이므로 커밋을 나눈다.** 문서(M5)는 각 커밋에 해당 부분을 함께 싣고,
`tests/run.sh`·`tests/hub/`(M6~M8)를 별도 커밋으로 두는 것이 선례(`0ba6f8c`)와 일치한다.

---

## 승인 요청 항목

### 한눈에 보기

| # | 항목 | 권고 |
|---|------|------|
| 1 | 스탬프를 **`HubSnapshot` 필드**로 둔다 — 쓰기 게이트(`snapshot_content_key`)의 의미가 함께 바뀐다 | 그렇게 한다 |
| 2 | 스탬프 없는 응답(구세대 서버)은 **리로드하지 않는다**(비대칭 규칙) | 그렇게 한다 |
| 3 | 루프 가드는 **대상 스탬프별 1회**(세션당 1회가 아니다) | 그렇게 한다 |

### 승인 항목 1 — 스탬프가 쓰기 게이트에 편입된다 (결정 SH4)

`template_stamp` 를 `HubSnapshot` 필드로 두면 `snapshot_content_key` 가 자동으로 그것을
포함하게 되어, **"템플릿만 바뀌었을 때도 `hub.html` 을 다시 쓴다"** 로 서버 동작이 바뀐다.

- **채택 시**: `hub_server.py` 수정 0줄로 잠복 결함(전제 7)이 닫히고, `install.sh --force` 만
  하고 재기동을 잊은 경우에도 탭이 치유된다(E20). 대신 `collect_snapshot` 이 매 사이클
  템플릿(약 136KB)을 한 번 더 읽는다.
- **미채택 시**: 스탬프를 `render_hub_html` 이 payload 에 덧붙이거나 별도 DOM 마커로 싣는다.
  템플릿 읽기가 늘지 않는 대신 문서화된 계약 하나가 깨지고(A4·결정 SH4 표), 자가 치유는
  `/hub server restart` 를 반드시 거친 경우에만 동작한다.

### 승인 항목 2 — 비대칭 비교 규칙 (결정 SH6)

"다르면 리로드"라는 대칭 규칙이 더 단순해 보이지만, 스탬프 없는 구세대 응답을 받은 신세대 탭이
**아무 이득 없이 1회 리로드**된다(E7). "정보 없음은 사건이 아니다"를 규칙으로 못 박아 그
리로드를 없앤다. 비용은 조건 한 줄이다.

### 승인 항목 3 — 루프 가드의 단위 (결정 SH9)

"세션당 1회"가 가장 짧지만, **한 번 치유한 탭이 그 세션 내내 다시 치유되지 않아** 두 번째
업데이트부터 원래 문제가 재발한다(sessionStorage 는 리로드를 넘어 살아남는다). "대상 스탬프별
1회"는 코드 길이가 같으면서 그 재발이 없다. 저장소가 막힌 환경에서는 리로드를 아예 하지 않는
쪽(fail-safe)을 택했다 — 회귀 0, 루프 0, 대신 그 환경에서는 기능이 없다.
