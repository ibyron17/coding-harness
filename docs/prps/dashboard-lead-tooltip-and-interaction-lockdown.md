# 작업 추적 제목의 말줄임 툴팁 + 허브·대시보드 상호작용 잠금 (PRP)

- **대상**: `commands/dashboard_template.html`, `hub/bin/hub_template.html`, `commands/dashboard.md`,
  `docs/prps/dashboard-rationale.md`, `hub/README.md`, `README.md`, `tests/run.sh`
- **결정 접두**: `LT`(Lead Tooltip) · `IL`(Interaction Lockdown) — 기존 접두 전수 확인 결과
  사용 중인 것은 `A B C D DG E EX F G GN IR K L LG M MD MS N O OC ON P PV Q R RV S SH SP T TR U UT V W WT X Y Z ZG`
  이며 `LT`·`IL` 둘 다 비어 있다
- **선행 정본**: [hub-session-activity-and-tooltip.md](hub-session-activity-and-tooltip.md)(T1~T6 — 허브 툴팁 싱글턴) ·
  [hub-detail-side-panel.md](hub-detail-side-panel.md)(SP1~SP15) ·
  [hub-panel-immediate-refresh.md](hub-panel-immediate-refresh.md)(IR1~IR9) ·
  [dashboard-pip-floating.md](dashboard-pip-floating.md)(PiP `.wrap` 이동) ·
  [dashboard-md-slimming.md](dashboard-md-slimming.md)(템플릿 외부화)
- **검증 명령**: `bash tests/run.sh` — **착수 전 실측 baseline 24/24 통과 확인함**(이 문서 작성 중 1회 실행)

---

## 요구사항 요약

두 가지 UI 요구다. **서로 다른 파일을 건드리지만 한 쌍으로 묶여 있다** — 요구 2가 텍스트
선택(=드래그 복사로 전문을 읽는 유일한 우회로)을 없애므로, 요구 1의 툴팁이 잘린 제목을 읽는
**유일한 수단**이 된다.

1. **작업 추적 항목 제목의 말줄임 툴팁** — 허브 상세 패널(폭 550px, iframe 549px)에서 대시보드
   작업 추적 카드의 `<span class="lead">` 가 `text-overflow:ellipsis` 로 잘린다. 마우스를 올리면
   전문을 볼 수 있어야 한다.
2. **우클릭 메뉴 차단 + 텍스트 선택 차단** — 허브와 프로젝트 대시보드 양쪽에서 브라우저 네이티브
   컨텍스트 메뉴가 뜨지 않고, 마우스 드래그로 텍스트가 선택되지 않아야 한다.

### 사용자 스토리

```
허브 상세 패널로 여러 프로젝트의 작업 추적을 훑는 사람으로서,
"…" 로 잘린 제목에 마우스를 올리면 그 자리에서 전문을 읽고 싶다.
그리고 이 화면들이 브라우저 문서가 아니라 하나의 도구처럼 동작하기를 바란다 —
우클릭에 브라우저 메뉴가 튀어나오거나 드래그가 텍스트를 파랗게 칠하지 않기를 바란다.
```

### 성공 기준 (검증 가능한 형태)

| # | 기준 | 확인 방법 |
|---|------|-----------|
| S1 | 허브 상세 패널에서 **잘린** `.lead` 에 마우스를 올리면 120ms 뒤 전문 툴팁이 뜬다 | 패널 폭 550px 에서 긴 제목 항목 hover |
| S2 | **잘리지 않은** `.lead` 에는 툴팁이 뜨지 않는다 | 짧은 제목 항목 hover — 0건 |
| S3 | 툴팁이 iframe(549px) 밖으로 나가지 않는다 — 좌우·상하 8px 여백 안에서 줄바꿈된다 | 패널 최하단 항목 hover |
| S4 | 단독 탭(`http://localhost:{포트}/dashboard.html`)에서도 S1~S3 이 성립한다 | 단독 탭 hover |
| S5 | 1분 폴링이 로그를 갱신한 직후에도 툴팁이 정상 동작한다(고아 툴팁 없음) | 툴팁을 띄운 채 `/dashboard log` 1건 추가 |
| S6 | 허브·대시보드(단독/패널)·PiP 창 **네 문서 전부**에서 우클릭이 네이티브 메뉴를 띄우지 않는다 | 각 문서에서 우클릭 |
| S7 | 같은 네 문서에서 드래그가 텍스트를 선택하지 않는다 | 본문 텍스트 드래그 |
| S8 | 허브의 **카드 드래그 재정렬이 그대로 동작**한다 | 핸들로 카드 이동 후 순서 유지 확인 |
| S9 | 대시보드의 필터 라디오 3종·`<details>` 토글·버튼 포커스가 그대로 동작한다 | 클릭·Tab 이동 |
| S10 | `bash tests/run.sh` 가 24/24 | 명령 실행 |

---

## 확정된 전제 (재론하지 않는다)

사전 조사에서 **파일을 직접 읽어 확정한 사실**이다. 구현 중 다시 검증하지 않는다.

1. **「상세보기 패널의 작업 추적 항목 타이틀」이 사는 곳은 허브가 아니라 대시보드 템플릿이다.**
   `hub_template.html:505` 의 `#dzh-detail-frame` 은 iframe 이고, 그 안 문서가
   `commands/dashboard_template.html` 로 만들어진 `.claude/dashboard.html` 이다. 대상 CSS 는
   `commands/dashboard_template.html:131`
   `.entry .lead{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;color:var(--ink)}`
   → **요구 1은 허브 템플릿을 한 바이트도 건드리지 않는다.**
2. **폴링은 `#dz-log` 의 자식을 통째로 교체한다.** `syncLog()`(`dashboard_template.html:307~310`)가
   `live.innerHTML = next.innerHTML` 을 쓴다. 따라서 **런타임에 `<li>`·`.lead` 에 붙인 속성은
   폴링 1회로 전부 소멸한다.** 반대로 `#dz-log` **노드 자신은 살아남는다**(innerHTML 대입은
   컨테이너를 바꾸지 않는다) — MutationObserver 를 한 번 걸면 재등록이 필요 없다.
3. **대시보드에는 툴팁 시스템이 없다.** `title=` 은 `#dz-theme-toggle` 한 곳뿐이다(214행).
   `user-select`·`contextmenu` 문자열은 두 템플릿 어디에도 없다(전수 grep).
4. **허브 템플릿에는 전역 커스텀 툴팁 싱글턴이 이미 있다** — `#dzh-tooltip`,
   트리거 `[data-tooltip]`, IIFE `hub_template.html:583~703`, CSS `328~333`.
   그리고 **"실제로 잘렸을 때만 붙인다"는 선례**가 `renderSessionExcerpt`(1019~1025)에 있다.
5. **iframe 경계**: 허브 문서의 `document` 리스너는 iframe 안 문서의 이벤트를 받지 못하고,
   허브의 CSS 도 iframe 문서에 상속되지 않는다 → 요구 2는 **두 문서에 각각** 넣어야 한다.
6. **PiP 창의 승계 방식**(`dashboard_template.html:385~424`):
   `<style>` 은 `textContent` 를 **복사**한다(392~397) → CSS 는 자동 승계된다.
   `.wrap` 은 **`appendChild` 로 이동**한다(403) → 그 서브트리는 PiP document 소속이 되고,
   **메인 문서의 `document` 리스너는 그 이벤트를 받지 못한다** → `contextmenu` 는 PiP 문서에
   따로 걸어야 한다.
7. **PiP 에서 `#dz-log-card` 는 CSS 로 숨는다**(`body.dz-pip #dz-log-card{display:none}`, 186행)
   → **요구 1은 PiP 창에 영향이 없다.** 요구 2만 PiP 를 신경 쓰면 된다.
8. **두 IIFE 를 결합하지 않는 것이 이 파일의 확립된 관례**다. 테마 IIFE 는 폴링 IIFE 의
   `pipWindow` 지역 변수를 공유하지 않고 표준 API(`window.documentPictureInPicture.window`)로
   PiP 문서를 찾는다(465~473행 주석에 그 이유가 명시돼 있다).
9. **폴링 IIFE 는 두 번 조기 return 한다** — `file://`(290행), PiP 미지원(383행). 그래서 테마
   코드가 별도 IIFE 로 나와 있다(427~429행 주석). **새 코드도 같은 이유로 폴링 IIFE 밖에 둬야
   한다.**
10. **`template_stamp` 는 `hub_template.html` 의 SHA-256** 이다(`hub_collect.py:411
    read_template_stamp`). 허브 템플릿을 고치면 스탬프가 자동으로 바뀌고 열린 허브 탭이 1회
    자가 리로드한다(SH6~SH9) — **이번 변경에 추가 조치가 필요 없다.**
11. **대시보드에는 그런 자가 치유가 없다.** `.claude/dashboard.html` 은 `/dashboard init` 이
    템플릿을 **바이트 단위 무편집 복사**해 만든다(`dashboard.md` 「템플릿 파일」). 이미 만들어진
    파일은 다음 `init` 전까지 옛 세대 그대로다.
12. **테스트 baseline 24/24**(이 문서 작성 중 `bash tests/run.sh` 1회 실행으로 실측).
    현재 그룹 범위는 `T22-1~T22-147`(대시보드 템플릿 무결성) · `T25-1~T25-143`(허브 문서·상수).

### 비목표 (이번 범위 밖 — 명시적으로 건드리지 않는다)

- **`.step-detail` 의 말줄임**(`dashboard_template.html:100`, 진행 단계·구현 세부 작업의 한 줄
  상세)도 같은 방식으로 잘리지만 **요청 범위 밖이다.** 요청은 「작업 추적 항목의 타이틀」로
  한정돼 있고, 수술적 변경 원칙(전역 지침 3번)을 따라 넓히지 않는다. 재방문 트리거: 사용자가
  단계 상세도 안 보인다고 말하면 그때 같은 툴팁 시스템에 트리거 셀렉터 하나를 더한다(비용 1줄).
- **허브의 `.detail-title`**(패널 헤드 프로젝트명, `hub_template.html:390`)도 말줄임되지만 같은
  이유로 범위 밖이다. 더구나 그 이름은 패널 뒤 카드에 온전히 보인다 — 정보 손실이 실재하지 않는다.
- **대시보드의 `#dz-project-name`**(`.project-name`, 159행)도 같다.
- **`#dz-theme-toggle` 의 네이티브 `title`**(214행)을 커스텀 툴팁으로 바꾸지 않는다 — 동작하는
  것을 건드리지 않는다(수술적 변경). 임베드 시에는 CSS 로 숨는 버튼이기도 하다.
- **로그 항목 스키마(`dashboard.md` 「로그 항목 스키마」)와 `log` 절차의 이스케이프 규약을
  개정하지 않는다.** 결정 LT2 의 직접 귀결이다.
- **허브의 `[data-tooltip]` 시스템을 대시보드로 옮기거나 공유하지 않는다** — 두 파일은 각각
  단일 파일 문서라 코드를 공유할 수단이 없다(결정 LT3 참조).
- **구세대 `.claude/dashboard.html` 을 허브가 고쳐 쓰지 않는다**(hub/README 「알려진 한계」의
  기존 원칙 유지).
- **선택 차단의 우회 장치**(Alt 누르면 선택 허용 등)를 만들지 않는다(결정 IL7).

---

## 영향 범위

### 수정 파일 (7개 + 이 문서)

| 파일 | 요구 | 변경 내용 |
|------|------|-----------|
| `commands/dashboard_template.html` (511줄) | 1·2 | `#dz-tooltip` 마크업 1줄 · `.tooltip` CSS 2규칙 · `html{user-select:none}` 1규칙 · **툴팁 IIFE 신설** · **상호작용 잠금 IIFE 신설** |
| `hub/bin/hub_template.html` (1801줄) | 2 | `html{user-select:none}` 1규칙 · **상호작용 잠금 IIFE 신설** · 머리 주석 1문단 |
| `commands/dashboard.md` (1258줄) | 1·2 | 「정적 요소 추가」 표에 `#dz-tooltip` 행 · 「로그 항목 스키마」에 "각인하지 않는다" 1줄 · 「상호작용 잠금 계약」 소절 신설 |
| `docs/prps/dashboard-rationale.md` | 1 | `<a id="lead-tooltip">` 앵커 + 근거 절 신설 |
| `hub/README.md` (455줄) | 1·2 | 「프로젝트 상세 패널」에 툴팁 1줄 · 우클릭/선택 차단 서술 · 「알려진 한계」의 구세대 대시보드 조항 확장 |
| `README.md` (339줄) | — | `commands` 표의 `dashboard` 줄 수(1258)와 `dashboard_template.html`(511줄) 갱신 |
| `tests/run.sh` (5075줄) | 1·2 | T22-148~154 · T25-144~146 신설 + 두 그룹 `test_desc` 범위 문자열 갱신 |

### 미영향 — 건드리지 않는 이유 (직접 확인함)

| 대상 | 이유 |
|------|------|
| `install.sh` | 파일이 추가·삭제되지 않는다 → `COMMANDS_FILE_COUNT`(T22-138)·`HUB_FILE_COUNT`(T25-1) 불변 |
| `hub/bin/*.py` | 서버·수집·모델은 HTML 을 만들지 않는다(`render_hub_html` 은 `#dzh-data` 블록 1개만 치환) |
| `commands/hub.md` | UI 상호작용을 서술하지 않는다(전수 grep: 「툴팁」·「우클릭」 0건). 서버·훅·설정 절차서다 |
| `tests/hub/*.py` | 파이썬 순수 모듈 대상. 템플릿 문자열 검사는 `tests/run.sh` 소관 |
| `hub_template.html` 의 요구 1 | 전제 1 — 대상이 iframe 안 문서다 |
| `template_stamp` 메커니즘 | 전제 10 — 파일 해시라 자동으로 새 세대가 된다 |
| `syncLog`·`apply`·`poll` | 결정 LT2 로 폴링 재동기화와의 상호작용 자체가 사라진다 |

---

## 결정 기록

### 결정 LT1 — 요구 1이 손볼 파일은 **대시보드 템플릿 하나**다

사용자 요구가 "허브의 상세보기 패널"이라 허브 템플릿을 고칠 것처럼 읽히지만, 그 패널의 본문은
iframe 이고 그 안 문서는 대시보드다(전제 1·5). 허브에 무엇을 넣어도 iframe 안 `.lead` 의 hover 를
받을 수 없다.

> **귀결**: 이 툴팁은 **단독 탭에서도 함께 켜진다.** 패널 전용으로 좁힐 수단이
> (`body.dz-embedded` 스코프) 있긴 하지만 쓰지 않는다 — 단독 탭도 `.wrap{max-width:860px}` 안에서
> 긴 제목이 잘리고, 요구 2가 단독 탭의 텍스트 선택도 함께 없애므로 같은 문제가 그대로 있다.

### 결정 LT2 — 툴팁 부착 시점은 **런타임 hover 감지**. 마크업 각인을 하지 않는다 ★ 승인 항목 1

두 안이 있었다.

| 안 | 방식 | 판정 |
|----|------|------|
| A. 마크업 각인 | `/dashboard log` 절차가 `<span class="lead" title="…">` 을 쓴다 | **기각** |
| B. 런타임 감지 | 스크립트가 hover 시점에 넘침을 재고 툴팁을 띄운다 | **채택** |

**A 를 기각한 이유 4가지**:

1. **잘림 여부는 생성 시점에 알 수 없다.** 같은 문자열이 단독 탭(860px)에서는 안 잘리고
   패널(549px)에서는 잘린다. 오케스트레이터는 렌더 폭을 모른다 → A 는 **항상** 각인해야 하고,
   그러면 잘리지 않은 항목에도 툴팁이 뜬다(결정 LT6 위반).
2. **이스케이프 규약을 개정해야 한다.** 현행 `log` 절차의 규약은 `&`→`&amp;`, `<`→`&lt;`,
   `>`→`&gt;` **세 가지뿐**이다(`dashboard.md` 793행). 속성값에 넣으려면 `"`→`&quot;` 가
   추가돼야 하고, 그 순간 `.lead` 텍스트 노드용 규약과 속성용 규약이 **두 벌**이 된다 —
   `log` 절차가 이미 "이스케이프가 두 모드가 되면 안 된다"(796행)를 명시적으로 경계하고 있다.
3. **폴링과 무관해진다는 이점이 A 에만 있는 것이 아니다.** B 도 속성을 남기지 않으므로
   `syncLog` 의 innerHTML 교체(전제 2)와 애초에 충돌하지 않는다.
4. **구세대 파일이 영원히 못 받는다.** A 는 새로 쓰는 `<li>` 에만 붙으므로 이미 쌓인 로그
   항목에는 툴팁이 없다. B 는 파일이 새 템플릿으로 다시 만들어지는 순간 **과거 항목까지 전부**
   동작한다.

**B 의 부수 효과 — 폴링·필터·`<details>` 토글 재부착 시점을 설계할 필요가 없다.** 속성을
남기지 않기 때문이다. 넘침 판정은 **포인터가 올라온 그 순간의 실제 레이아웃**을 재므로
패널 폭 변화·창 리사이즈·PiP 전환 어디에도 훅을 걸지 않는다. 이것이 B 를 고른 가장 큰 이유다.

> **`dashboard.md` 에 남길 것**: 「로그 항목 스키마」에 *"`.lead` 의 말줄임 툴팁은 런타임 감지다 —
> 이 스키마에 `title`·`data-tooltip` 을 각인하지 않는다"* 한 줄. 미래에 스키마를 고치는 사람이
> 같은 유혹에 빠지는 것을 막는 유일한 장치다.

### 결정 LT3 — 툴팁 구현은 **대시보드 자체의 커스텀 싱글턴**. 네이티브 `title` 을 쓰지 않는다 ★ 승인 항목 2

| 안 | 코드량 | 판정 |
|----|--------|------|
| a. 네이티브 `title` 을 hover 시점에 lazy set | ~8줄 | 기각 |
| b. 커스텀 툴팁 싱글턴 신설 | ~55줄 + 주석 | **채택** |

**a 를 기각한 결정적 이유**: **요구 2가 텍스트 선택을 없앤다.** 그러면 잘린 제목을 읽는 수단이
툴팁 하나뿐인데, 네이티브 툴팁은 ① 약 1초 지연 후 뜨고 ② 약 5초 뒤 **저절로 사라지며**
③ 포인터를 올려 붙잡아 둘 수 없다. 긴 제목을 다 읽기 전에 사라지는 툴팁은 "유일한 읽기 수단"의
자격이 없다. 부차 이유: ④ OS 기본 글꼴·라이트 배경이라 다크 테마에서 이질적이고, ⑤ 같은
뷰포트의 허브 카드(세션 발췌)는 어두운 커스텀 툴팁을 띄우는데 패널 안만 OS 툴팁이 뜬다.

**b 의 비용을 정직하게 적는다**: 허브에 이미 있는 것과 **같은 종류의 코드가 두 파일에 존재하게
된다.** 두 템플릿은 CDN·번들러 없이 각각 단독으로 열려야 하는 단일 파일 문서라(허브 머리 주석
60~61행: "CDN·런타임 라이브러리를 쓰지 않는다") **공유할 수단이 구조적으로 없다.** 이 저장소는
이미 같은 이유로 테마 토큰·테마 토글 IIFE·폴링 골격을 두 파일에 중복으로 갖고 있다
([dashboard-hub-visual-parity.md](dashboard-hub-visual-parity.md)). 이번 중복은 그 관례의 연장이며,
DRY 위반이 아니라 **배포 단위가 파일 1개라는 제약의 결과**다.

**대시보드판이 허브판보다 작은 이유(그대로 베끼지 않는다)**:

| 허브에 있는 것 | 대시보드 | 이유 |
|---------------|---------|------|
| `[data-tooltip]` 속성 트리거 시스템 | 없음 | 트리거가 `.entry .lead` 하나뿐이다(결정 LT2) |
| `accessibleNameOf`/`shouldDescribe`/`aria-describedby` | 없음 | 결정 LT5 |
| `focusin`/`focusout` 트리거 | 없음 | 결정 LT7 |
| `data-tooltip` 속성 변경 감시 observer | 없음 | 문구가 트리거 자신의 `textContent` 라 "낡은 문구"가 생길 수 없다 |
| `click` 시 숨김 | 없음 | 결정 LT9 |
| `#dzh-app`·`#dzh-usage-body` 2중 observer | `#dz-log` 1개 | 로그 목록이 유일한 교체 대상이다 |

### 결정 LT4 — `.tooltip` CSS 는 복사가 아니다: `white-space:pre-wrap` 을 **빼고** `overflow-wrap:anywhere` 만 가져온다

허브의 `.tooltip{...white-space:pre-wrap...}` 은 주석(318~327행)이 밝히듯 **세션 발췌 프롬프트의
개행을 살리려고** 들어왔다. `.lead` 는 한 줄 요약이고 `log` 절차가 개행을 넣지 않으므로 `pre-wrap`
이 사는 값이 없다 — 오히려 앞뒤 공백을 그대로 렌더해 손해다. 반면 `overflow-wrap:anywhere` 는
**반드시 가져온다**: 549px 패널에서 가운뎃점으로 이은 식별자 사슬이 상자를 뚫고 나간 사고가
이 파일에서 실제로 있었고(`.entry .detail` 주석 132~138행, 회귀 검사 T22-128), 툴팁 안에서도 같은
문자열을 렌더한다. `max-width:min(420px,calc(100vw - 32px))` 도 그대로 가져온다 — 549px 뷰포트에서
420px 로 낙착돼 패널을 다 가리지 않는다.

### 결정 LT5 — 접근성 배선을 하지 않는다: `aria-hidden="true"`, `aria-describedby` 없음

`text-overflow:ellipsis` 는 **렌더링만 자른다** — DOM 텍스트 노드는 온전하고 접근성 트리에도
전문이 그대로 있다. 즉 **스크린리더 사용자는 이미 전문을 듣고 있고**, 이 툴팁은 오직 시각적
중복이다. 허브의 `shouldDescribe()` 규칙("툴팁 문구가 접근성 이름과 같으면 연결하지 않는다")을
이 경우에 적용하면 **항상 false** 다(툴팁 문구 = 트리거 `textContent` = 접근성 이름). 그러므로
연결 코드를 두는 것 자체가 죽은 코드다. `role="tooltip"` 도 참조되지 않으면 의미가 없으므로
`aria-hidden="true"` 로 장식 요소임을 명시한다.

### 결정 LT6 — 잘리지 않은 항목에는 툴팁을 띄우지 않는다

허브 선례를 그대로 따른다(`renderSessionExcerpt` 주석 1014~1018행: *"보이는 텍스트와 같은 툴팁은
정보 손실이 없어 소음이며, 카드 이름에서 이미 같은 판단을 했다(결정 R4)"*). 판정은
`element.scrollWidth - element.clientWidth > TOOLTIP_OVERFLOW_TOLERANCE_PX`.

**허용 오차 1px 을 두는 이유**: `scrollWidth`·`clientWidth` 는 정수로 반올림되는데 `.lead` 는
`flex:1` 로 소수점 폭을 갖는 flex 아이템이다. 딱 맞는 텍스트에서 두 값이 1 차이 나면 잘리지도
않은 항목에 툴팁이 뜬다(S2 위반). 상수 이름을 붙여 매직 넘버로 두지 않는다.
**구현자는 짧은 제목 항목에서 툴팁이 0건임을 실측해 그 결과를 주석에 남긴다.**

### 결정 LT7 — 마우스 전용. `focusin` 트리거를 만들지 않는다

허브는 `focusin` 으로도 툴팁을 띄우지만(결정 T3), 여기서는 만들지 않는다. 이유 둘:
① `.lead` 는 포커스를 받지 않는다 — 포커스 대상은 부모 `<summary>` 이고, 그것을 트리거로 삼으면
로그 항목 **전부**가 Tab 정류장마다 툴팁을 띄운다(잘림 여부와 무관하게 `<summary>` 의 넘침을
재게 되므로 판정도 어긋난다). ② 결정 LT5 대로 키보드·AT 사용자는 이미 전문을 얻는다.
**대가**: 마우스를 쓰지 않는 시력 있는 사용자는 전문을 화면에서 못 본다 — 수용한다.

### 결정 LT8 — `#dz-tooltip` 은 `.wrap` **바깥**, `#dz-page-head` 와 `.wrap` **사이**에 둔다

`.wrap` 은 PiP 진입 시 **다른 document 로 이동**한다(전제 6). 툴팁을 그 안에 두면 PiP 를 열자마자
메인 문서에서 사라진다 — `#dz-page-head` 가 `.wrap` 바깥에 있는 것과 정확히 같은 이유다
(`dashboard-rationale.md#wrap-outside`).

**`.wrap` 앞에 두는 이유는 따로 있다**: 폴링 IIFE 가 `var wrapReturnAnchor = wrap.nextSibling;`
(262행)로 PiP 복귀 지점을 잡아 둔다. `.wrap` **뒤**에 넣으면 그 앵커가 새 노드로 바뀐다 —
결과는 같지만(복귀한 `.wrap` 이 툴팁 앞에 놓임) **검증해야 할 것이 하나 늘어난다.** 앞에 넣으면
그 줄이 참조하는 노드가 바이트 단위로 그대로다. 건드릴 이유가 없는 코드를 건드리지 않는 쪽을
고른다.

### 결정 LT9 — 툴팁 IIFE·잠금 IIFE 는 **폴링 IIFE 밖 · 테마 IIFE 뒤**에 둔다

폴링 IIFE 는 `file://` 과 PiP 미지원에서 조기 return 한다(전제 9) — 그 안에 넣으면 두 환경에서
툴팁이 죽는다. 테마 IIFE 가 이미 같은 이유로 분리돼 있고 그 사유가 427~429행 주석에 적혀 있다.
**테마 IIFE 뒤**로 못 박는 이유는 회귀 검사를 위해서다 — "폴링 IIFE 밖"은 문자열로 검사하기
어렵지만 "`var THEME_STORAGE_KEY` 보다 뒤"는 줄 번호 비교 한 줄로 검사된다(T22-151, 선례 T22-37).

**툴팁 IIFE 안의 MutationObserver**: `#dz-log` 의 `childList` 를 감시해 갱신이 일어나면 툴팁을
숨긴다. 허브 결정 T6 이 기록한 실제 사고("트리거 노드가 파괴되는데 포인터가 멈춰 있으면 마우스
이벤트가 안 와 낡은 문구가 남는다")가 여기서도 성립한다 — 1분 폴링이 `#dz-log` 자식을 통째로
바꾼다(전제 2). `#dz-log` 노드 자신은 살아남으므로 **한 번만 observe 하면 된다.**

> `getElementById('dz-log')` 는 grep 유일성 불변식이 명시적으로 허용하는 형태다
> (`dashboard.md` 295~301행: *"스크립트에서는 `getElementById('dz-log')` 나
> `querySelector('#dz-log')` 만 쓰고"*). **`[id="dz-log"]` 형태는 절대 쓰지 않는다**(T22-38).

---

### 결정 IL1 — 적용 지점은 **문서 3개**: 허브 · 대시보드 · PiP

| 문서 | 선택 차단 | 우클릭 차단 |
|------|----------|------------|
| 허브(`hub.html`) | 허브 `<style>` | 허브 `document` 리스너 |
| 대시보드(단독 탭 **및** 패널 iframe — 같은 문서다) | 대시보드 `<style>` | 대시보드 `document` 리스너 |
| PiP 창 | **자동 승계** — `<style>` 전문이 복사된다(전제 6) | **수동 배선 필요**(결정 IL4) |

허브 패널 안에서 우클릭했을 때 어느 문서가 받는지는 **포인터가 iframe 위인지**로 갈린다. 패널
헤드·닫기 버튼은 허브 문서, iframe 본문은 대시보드 문서다. 그래서 **양쪽 다** 필요하다.

### 결정 IL2 — 선택 차단은 `html` 셀렉터 **한 규칙**. `-webkit-` 프리픽스를 함께 쓴다

```css
html{-webkit-user-select:none;user-select:none}
```

- **`body` 가 아니라 `html` 인 이유 둘**: ① 두 파일 모두 `body{...}` 규칙이 이미 있고 `:root{...}`
  는 테마 토큰이 점유했다 — 기존 규칙에 끼워 넣으면 "왜"를 적을 자리가 없고, 같은 셀렉터를 두 번
  쓰면 미래의 grep 검사가 어느 쪽을 볼지 모호해진다. `html{` 은 두 파일 어디에도 없는
  **유일한 셀렉터**라 검사(T22-152·T25-144·T25-145)가 명확해진다. ② `user-select` 는 상속
  프로퍼티이므로 `html` 하나로 문서 전체(대시보드의 `#dz-page-head`·`#dz-tooltip`·`.wrap` 전부)를
  덮는다.
- **PiP 승계 확인**: PiP 문서에도 `<html>` 과 `<body class="dz-pip">` 가 있고 `<style>` 전문이
  복사되므로 이 규칙이 그대로 적용된다.
- **프리픽스를 함께 쓰는 이유**: 구버전 WebKit 은 프리픽스만 인식한다. 선언 한 개의 비용으로
  커버리지를 산다. 이 파일에는 이미 `::-webkit-details-marker`(128행) 선례가 있다.
  **정확한 지원 버전을 주석에 적지 않는다** — 확인할 수 없는 숫자를 근거처럼 적지 않는다.

### 결정 IL3 — `contextmenu` 는 `document` 버블 단계 리스너 **1개**. `capture` 를 쓰지 않는다

```js
document.addEventListener('contextmenu', function(event){ event.preventDefault(); });
```

두 문서 어디에도 `contextmenu` 리스너가 없고(전제 3) `stopPropagation` 을 부르는 코드도 없으므로
버블 단계로 충분하다. `capture:true` 는 "언젠가 누가 전파를 멈출지도 모른다"에 대비하는
추측성 방어다(karpathy #2) — 쓰지 않는다.

`preventDefault()` 만 하고 `return false` 나 `stopPropagation()` 을 쓰지 않는다 — 네이티브 메뉴를
막는 데 필요한 것은 기본 동작 취소뿐이고, 전파를 멈추면 미래에 우클릭을 쓰려는 코드가
설명 없이 죽는다.

### 결정 IL4 — PiP 문서 배선은 `documentPictureInPicture` 의 **`enter` 이벤트**로. 폴링 IIFE 를 건드리지 않는다

```js
window.documentPictureInPicture.addEventListener('enter', function(){
  // enter 시점엔 window.documentPictureInPicture.window 가 이미 설정돼 있다
  window.documentPictureInPicture.window.document
    .addEventListener('contextmenu', preventNativeContextMenu);
});
```

- **폴링 IIFE 의 `requestWindow().then()` 안에 한 줄 끼워 넣지 않는 이유**: 그 IIFE 는 이미 조기
  return 이 둘이고, 무엇보다 **이 파일이 "두 IIFE 사이에 새 결합을 만들지 않는다"는 원칙을 명시적
  코드 주석으로 갖고 있다**(465~473행). 테마 IIFE 가 `pipWindow` 대신
  `window.documentPictureInPicture.window` 를 쓰는 것과 **정확히 같은 패턴**을 재사용한다.
- **이벤트 객체의 `.window` 프로퍼티를 쓰지 않는 이유**: `DocumentPictureInPictureEvent.window`
  대신 이미 이 파일이 쓰고 있는 접근 경로(`window.documentPictureInPicture.window`)를 쓴다 —
  검증된 관용구가 파일 안에 있는데 새 API 표면을 들이지 않는다.
- **`'documentPictureInPicture' in window` 기능 감지로 감싼다** — Safari·Firefox 에서
  `addEventListener` 대상이 `undefined` 가 되면 IIFE 전체가 죽어 `contextmenu` 차단까지 함께
  사라진다. **감지 실패 시에도 메인 문서 차단은 반드시 살아 있어야 하므로 리스너 등록 순서는
  `document` 먼저, PiP 배선 나중이다.**
- **매 `enter` 마다 등록한다** — PiP 문서는 열 때마다 새로 만들어지고 닫히면 리스너도 함께
  사라진다. 중복 등록이 생기지 않는다.

### 결정 IL5 — 예외 규칙을 만들지 않는다. 드래그 동작은 **실측으로 확인**한다

`input`/`textarea` 예외(`user-select:text`)를 넣지 않는다 — 두 문서에 텍스트 입력 요소가
하나도 없다(대시보드의 `input` 3개는 `opacity:0;pointer-events:none` 인 라디오다).
없는 상황에 대한 방어를 넣지 않는다(karpathy #2).

**허브 카드 드래그 재정렬(`<span class="card-drag-handle" draggable="true">`, 1095행)은 예외 규칙
없이 그대로 둔다.** 이유: 그 핸들은 텍스트가 없는 인라인 SVG 컨테이너라 선택 차단이 지울 것이
애초에 없다. 다만 **일부 WebKit 계열에서 `-webkit-user-select:none` 이 `draggable` 요소의 드래그
시작을 막는다는 보고가 있다.**

> **구현자 지시(필수)**: S8 을 **Chrome 에서 반드시 실측**한다(이 저장소의 주 대상 브라우저다 —
> PiP·허브 서버 안내가 모두 Chrome 기준이다). 실측 결과를 잠금 규칙 주석에 한 줄로 남긴다.
> **동작하면 아무것도 추가하지 않는다.** 실측에서 깨진 경우에만
> `.card-drag-handle{-webkit-user-drag:element}` 를 넣고, 그때 주석에 "무엇이 어떻게 깨졌는지"를
> 적는다. **미실측 상태로 예방 선언을 넣지 않는다** — 확인하지 않은 방어는 이 저장소가 금지하는
> 추측성 코드다.

### 결정 IL6 — 구세대 대시보드는 잠기지 않는다. 고쳐 쓰지 않고 「알려진 한계」에 적는다

`.claude/dashboard.html` 은 이미 만들어진 파일이라 새 템플릿의 CSS/JS 를 갖지 못한다(전제 11).
그 프로젝트의 상세 패널 **iframe 안에서만** 네이티브 메뉴와 텍스트 선택이 살아 있다. 허브는 그
파일을 **읽기 전용으로만 소비**한다는 기존 원칙(hub/README 「알려진 한계」)을 유지한다 —
`/dashboard init`(또는 `step`·`log`)을 한 번 더 실행하면 저절로 해소된다.

`hub/README.md` 「알려진 한계」의 **구세대 대시보드 조항에 한 문장을 덧붙인다**(새 항목을 만들지
않는다 — 같은 원인·같은 해소법이다).

### 결정 IL7 — 복사 불가·검사 메뉴 차단은 **수용된 비용**이다. 우회 장치를 만들지 않는다 ★ 승인 항목 3

이 변경이 실제로 없애는 것을 숨기지 않고 적는다.

**잃는 것**

| 잃는 것 | 어디서 아팠나 |
|---------|--------------|
| 텍스트 드래그 복사 | 허브 카드의 프로젝트 경로·세션 ID(`.session-id`), 대시보드 로그 상세 전문·명령어 조각(`<code>`) |
| 네이티브 우클릭 메뉴 | "새 탭에서 열기", "검사", "이미지 저장", 브라우저 번역, 뒤로 가기 |
| 터치 길게 누르기 메뉴 | 모바일·태블릿에서 우클릭에 대응하는 제스처가 함께 막힌다 |

**남는 것 / 완화책**

1. **요구 1이 요구 2의 완화책이다.** 잘린 제목은 툴팁으로 **읽을 수** 있다(복사만 못 한다).
   두 요구를 한 PRP 로 묶은 이유가 이것이다.
2. **찾기(Ctrl+F)는 그대로 동작한다** — `user-select:none` 은 브라우저 페이지 내 찾기와 하이라이트를
   막지 않는다.
3. **개발자 도구는 키보드 단축키·브라우저 메뉴로 그대로 열린다** — 우클릭 「검사」만 막힌다.
4. **원문은 언제나 디스크에 있다.** `hub.html` 과 `.claude/dashboard.html` 은 평범한 로컬 파일이며
   `~/.claude/hub/events/YYYY-MM-DD.jsonl` 도 그대로다. 브라우저는 표시 창구일 뿐이다.
5. **허브에는 `<a href>` 링크가 하나도 없다**(전수 grep) — "링크를 새 탭에서 열기" 손실은
   실재하지 않는다.

**우회 장치(Alt 누르면 선택 허용, 특정 영역만 선택 허용 등)를 만들지 않는다.** 사용자가 명시적으로
요청한 동작이고, 예외를 두는 순간 "어디는 되고 어디는 안 되는지"라는 새 규칙이 생긴다(YAGNI).
필요해지면 그때 `user-select:text` 예외를 한 셀렉터 추가하는 것으로 되돌릴 수 있다 —
**되돌리기 비용이 낮다는 점이 지금 단순하게 가는 근거다.**

---

## 계약 (변경 후)

### 새로 생기는 DOM 계약 1개

| 요소 | 성격 | 계약 |
|------|------|------|
| `#dz-tooltip` | **정적(불가침)** | `<body>` 직계, `#dz-page-head` 와 `.wrap` 사이. `init`/`step`/`log`/`impl` 이 치환하지 않고 **폴링도 동기화하지 않는다.** 내용은 사용자 hover 만 바꾼다. `.wrap` 안에 있으면 안 된다(PiP 이동 대상) |

### 마크업 (대시보드 템플릿)

```html
<div id="dz-page-head"> … </div>
<div id="dz-tooltip" class="tooltip" aria-hidden="true"></div>
<div class="wrap"> … </div>
```

### CSS (신규 규칙 3개)

| 파일 | 규칙 | 목적 |
|------|------|------|
| 대시보드 | `.tooltip{position:fixed;left:0;top:0;z-index:40;max-width:min(420px,calc(100vw - 32px));max-height:calc(100vh - 16px);overflow:hidden;padding:6px 9px;border-radius:8px;font-size:11.5px;line-height:1.45;font-weight:600;color:var(--bg);background:var(--ink);box-shadow:var(--shadow);overflow-wrap:anywhere;visibility:hidden}` | 툴팁 본체(결정 LT4) |
| 대시보드 | `.tooltip.tooltip-visible{visibility:visible}` | 표시 토글 |
| 대시보드 · 허브 | `html{-webkit-user-select:none;user-select:none}` | 선택 차단(결정 IL2) — **두 파일에서 문자 단위로 동일해야 한다**(T25-145) |

> `z-index:40` 은 허브의 `.tooltip` 과 같은 값이다. 대시보드에는 다른 `z-index` 가 없어 어떤 양수든
> 되지만, 두 파일을 나란히 읽을 때 같은 층위로 읽히도록 값을 맞춘다.

### 내부 함수 시그니처 (대시보드 템플릿, 툴팁 IIFE)

```js
/** 트리거 사각형·툴팁 크기·뷰포트로 {left, top} 을 계산한다. 순수 함수 — DOM 에 닿지 않는다. */
function tooltipPosition(
  triggerRect: DOMRect, tooltipWidth: number, tooltipHeight: number,
  viewportWidth: number, viewportHeight: number
): {left: number, top: number}

/** 말줄임으로 실제로 잘렸는지 판정한다. 반올림 오차 1px 을 허용한다(결정 LT6). */
function isLeadTruncated(element: HTMLElement): boolean

/** 문구를 채우고 위치를 잡아 표시한다. */
function showTooltip(trigger: HTMLElement): void

/** 표시를 끄고 지연 타이머를 취소한다. 언제 불려도 안전하다. */
function hideTooltip(): void

/** 표시 요청. 이미 다른 트리거를 보여주는 중이면 지연 없이 즉시 교체한다. */
function requestTooltip(trigger: HTMLElement): void
```

### 내부 함수 시그니처 (양쪽 템플릿, 상호작용 잠금 IIFE)

```js
/** 네이티브 컨텍스트 메뉴를 막는다. 전파는 멈추지 않는다(결정 IL3). */
function preventNativeContextMenu(event: MouseEvent): void
```

### 상수 (대시보드 툴팁 IIFE — 매직 넘버 금지)

| 상수 | 값 | 근거 |
|------|-----|------|
| `TOOLTIP_SHOW_DELAY_MS` | `120` | 목록을 훑을 때 행마다 툴팁이 번쩍이지 않게 하는 hover-intent. 허브 결정 T3 과 같은 값·같은 이유 |
| `TOOLTIP_GAP_PX` | `8` | 트리거와 툴팁 사이 간격 |
| `TOOLTIP_VIEWPORT_MARGIN_PX` | `8` | 뷰포트 경계 최소 여백. CSS 의 `calc(100vh - 16px)` 이 이 값의 2배다 — 클램프와 맞물린다 |
| `TOOLTIP_OVERFLOW_TOLERANCE_PX` | `1` | flex 소수점 폭의 정수 반올림 오차(결정 LT6) |
| `TOOLTIP_VISIBLE_CLASS` | `'tooltip-visible'` | |
| `LEAD_TRIGGER_SELECTOR` | `'.entry .lead'` | 작업 추적 항목 제목만 트리거다 |

### 리스너 목록 (대시보드 툴팁 IIFE — 전부 `document` 위임)

| 이벤트 | 동작 | 왜 필요한가 |
|--------|------|-------------|
| `mouseover` | 트리거면 `requestTooltip`, 툴팁 위면 무시, 그 밖이면 `hideTooltip` | 표시·전환·숨김의 본체. 툴팁 위 무시가 hoverable(WCAG 1.4.13)을 만든다 |
| `mouseleave`(document) | `hideTooltip` | 포인터가 창 밖으로 나가면 `mouseover` 가 더 오지 않는다 |
| `keydown` (Escape) | `hideTooltip` | dismissible(WCAG 1.4.13) |
| `scroll` (capture, passive) | `hideTooltip` | `position:fixed` 라 스크롤하면 트리거와 어긋난다 |
| `resize`(window) | `hideTooltip` | 패널 폭이 바뀌면 잘림 판정 자체가 달라진다 |
| MutationObserver(`#dz-log`, childList) | `hideTooltip` | 폴링이 트리거 노드를 파괴한다(결정 LT9) |

> **`click` 에서 숨기지 않는다**(허브와 다른 점). `.lead` 아래의 유일한 클릭 대상은 `<summary>`
> 토글이고, 그것은 `.lead` 의 폭도 텍스트도 바꾸지 않는다 — 숨기면 사용자가 이유 없이 다시
> hover 해야 한다.

---

## 경계 조건 표

| 상황 | 기대 동작 | 근거 |
|------|----------|------|
| `file://` 로 연 대시보드 | 툴팁·잠금 모두 동작 | 두 IIFE 가 폴링 IIFE 밖이다(결정 LT9) |
| PiP 미지원 브라우저(Safari·Firefox) | 툴팁·잠금 모두 동작, PiP 배선만 생략 | 결정 IL4 의 기능 감지 |
| PiP 창 | 우클릭·선택 차단 O / 툴팁 무관 | 전제 6·7 |
| 로그가 비어 있음(`#dz-log` 자식 0개) | 아무 일도 없음 | 트리거가 없다 |
| 필터를 「구현」으로 바꿔 일부 항목이 `display:none` | 숨은 항목은 hover 불가 → 툴팁 없음 | CSS 필터가 이미 처리한다 |
| `<details>` 를 펼친 상태의 `.lead` | 동일하게 동작 | `<summary>` 폭은 펼침과 무관하다 |
| 툴팁 표시 중 폴링이 로그를 교체 | 툴팁이 즉시 사라진다 | MutationObserver(결정 LT9) |
| 툴팁 표시 중 PiP 진입(`.wrap` 이동) | `#dz-log-card` 가 숨어 hover 가 끊기고, `.wrap` 이동이 `#dz-log` childList 를 건드리지 않아도 다음 `mouseover` 에서 정리된다 | 결정 LT8 로 `#dz-tooltip` 은 메인 문서에 남는다 |
| 구세대 `.claude/dashboard.html` | 패널 안에서만 잠금·툴팁 없음 | 결정 IL6 |
| 좁은 화면(<1024px) 패널 = 뷰포트 전폭 | `max-width:calc(100vw - 32px)` 로 낙착 | 결정 LT4 |
| 허브 카드 드래그 중 우클릭 | 드래그가 취소되고 메뉴는 안 뜬다(브라우저 기본) | `dragend` 가 모든 경로에서 발화한다(기존 주석) |

---

## GOTCHA (구현자가 틀리기 쉬운 함정)

1. **`.wrap` 안에 `#dz-tooltip` 을 넣으면 PiP 진입 시 사라진다.** 반드시 `<body>` 직계다(결정 LT8).
2. **툴팁 IIFE 를 폴링 IIFE 안에 넣으면 `file://` 과 PiP 미지원에서 죽는다**(전제 9). 이 파일이
   똑같은 사고를 이미 한 번 겪고 주석으로 남겨 뒀다(427~429행).
3. **`showTooltip` 은 측정 전에 `left/top` 을 `0px` 로 리셋해야 한다.** 이전 위치가 남아 있으면
   `offsetWidth` 가 클램프된 값으로 측정돼 위치가 어긋난다(허브 GOTCHA 3).
4. **`tooltipEl.textContent` 를 쓴다. `innerHTML` 이 아니다.** 로그 제목에는 이스케이프된 코드
   조각이 들어온다 — `innerHTML` 로 넣으면 이중 해석된다(허브의 같은 자리 주석 참조).
5. **`[id="dz-log"]` 형태의 셀렉터를 쓰지 않는다**(grep 유일성 불변식, T22-38). `getElementById` 만.
6. **`data-tooltip` 이라는 문자열을 대시보드 템플릿에 넣지 않는다.** 결정 LT2 로 각인 방식을
   기각했는데 속성 이름만 흉내 내면 미래의 독자가 "허브와 같은 시스템"으로 오해한다.
   회귀 검사 T22-150 이 이것을 역방향으로 막는다.
7. **`html{...}` 규칙을 두 파일에 **다르게** 적으면 T25-145 가 실패한다.** 문자 단위로 같아야 한다
   (프리픽스 순서·공백 포함).
8. **PiP 배선을 `document` 리스너보다 **앞에** 두면 안 된다.** `documentPictureInPicture` 기능 감지가
   어떤 이유로든 던지면 메인 문서 차단까지 함께 죽는다(결정 IL4).
9. **`.entry .detail` 규칙을 건드리지 않는다.** T22-128 이 그 규칙이
   `white-space:pre-wrap;overflow-wrap:anywhere}` 로 **끝날 것**을 요구한다. 새 CSS 는 그 규칙
   **바깥**에 새 줄로 넣는다(파일의 140~142행 주석이 같은 경고를 하고 있다).
10. **두 그룹의 `test_desc` 범위 문자열을 갱신하지 않으면** 검사는 통과하지만 요약이 거짓말을
    한다 — `"dashboard 템플릿 무결성 (T22-1~T22-147)"` · `"허브 문서·상수 정합성 (T25-1~T25-143)"`.

---

## 테스트 계획 — `tests/run.sh`

### 기존 검사에 대한 영향 (전수 확인 결과)

| 기존 검사 | 영향 | 근거 |
|-----------|------|------|
| T22-38 (`[id="dz-` 금지) | 없음 | 새 코드는 `getElementById` 만 쓴다 |
| T22-41 (`id="dz-log"` 매칭 줄 수 == 1) | **없음** | 새로 넣는 id 는 `dz-tooltip` 이라 `id="dz-log"` 문자열과 겹치지 않는다 |
| T22-42 (`dz-log-card` 를 스크립트가 참조 금지) | 없음 | 우리가 참조하는 것은 `dz-log` 다 |
| T22-37 (플로팅 버튼이 `.wrap` 바깥) | 없음 | `#dz-tooltip` 은 `wrap_open_line` 앞이라 그 범위 판정과 무관 |
| T22-128 (`.entry .detail` 규칙 끝) | **주의** — GOTCHA 9 | 새 CSS 를 그 규칙 안에 넣으면 깨진다 |
| T22-129 (`POLL_INTERVAL_MS = 60000`) | 없음 | |
| T22-138 (`COMMANDS_FILE_COUNT`) | 없음 | 파일 수 불변 |
| T22-145/146 (갱신 훅 위치) | **주의** | 훅 줄(`window.dzRequestRefresh = poll;`)은 폴링 IIFE 안 `if(!hasPipSupport)` **앞**에 그대로 있어야 한다 — 새 IIFE 는 그 IIFE 밖이므로 영향 없다 |
| T25-1 (`HUB_FILE_COUNT`) | 없음 | |
| T25-136 (훅 이름 교차 일치) | 없음 | |
| T25-138~142 (`template_stamp`) | 없음 | 해시 자동 갱신(전제 10) |

### 신규 검사 — 대시보드 그룹 `test_dashboard_template_integrity` (T22)

`test_desc` → `"dashboard 템플릿 무결성 (T22-1~T22-154)"`

| # | 성격 | 검사 |
|---|------|------|
| **T22-148** | 정+역 | `id="dz-tooltip"` 이 템플릿에 정확히 1줄 존재한다(정). 그 줄 번호가 `.wrap` 여는 줄(`<div class="wrap">`)보다 **앞**이다(역 — `.wrap` 안에 들어가면 PiP 진입 시 소멸, 결정 LT8). 선례: T22-37 의 줄 번호 비교 |
| **T22-149** | 정 | `.tooltip{` 규칙에 뷰포트 클램프(`max-width:min(420px,calc(100vw - 32px))`)와 `overflow-wrap:anywhere` 가 있다. 549px 패널 넘침 회귀 방지(T22-128 계열) |
| **T22-150** | 역 | **템플릿 파일 자체**에 `data-tooltip` 문자열이 0건이다 — 각인 방식(결정 LT2 기각안)으로의 퇴행 검출. `dashboard_union_file` 이 아니라 `dashboard_template_file` 을 대상으로 한다(선례: T22-41 이 같은 이유로 대상을 좁힌다) |
| **T22-151** | 정 | `getElementById('dz-tooltip')` 줄 번호 > `var THEME_STORAGE_KEY = 'dz-theme';` 줄 번호 — 툴팁 IIFE 가 폴링 IIFE 밖에 있음의 대리 판정(결정 LT9) |
| **T22-152** | 정 | `html{-webkit-user-select:none;user-select:none}` 존재 + `contextmenu` preventDefault 리스너 존재 |
| **T22-153** | 정+역 | `documentPictureInPicture` 의 `'enter'` 리스너가 존재하고(정), 그 줄이 `var THEME_STORAGE_KEY` 보다 뒤다(역 — 폴링 IIFE 의 `requestWindow().then()` 안으로 들어가면 결정 IL4 위반) |
| **T22-154** | 정+역 | 문서 정합: `dashboard.md` 「정적 요소 추가」 표에 `#dz-tooltip` 행이 있고(정), 「로그 항목 스키마」 코드블록 안에 `title=`·`data-tooltip` 이 없다(역 — 선례 T22-132 가 같은 코드블록을 이미 범위로 잘라 검사한다) |

### 신규 검사 — 허브 그룹 `test_hub_docs_and_constants` (T25)

`test_desc` → `"허브 문서·상수 정합성 (T25-1~T25-146)"`

| # | 성격 | 검사 |
|---|------|------|
| **T25-144** | 정 | `hub_template.html` 에 `html{-webkit-user-select:none;user-select:none}` 과 `contextmenu` preventDefault 가 있다 |
| **T25-145** | 교차 파일 | 두 템플릿에서 `html{...user-select...}` 선언을 각각 뽑아 **문자 단위로 같은지** 비교한다. 한쪽만 프리픽스를 잃는 표류 방지. 선례: T25-136(훅 이름 교차 추출)·T25-1(파일 수 교차) |
| **T25-146** | 정+역 | 문서 정합: `hub/README.md` 에 우클릭·선택 차단 서술 토큰이 있고(정), 「알려진 한계」 구세대 대시보드 조항에 잠금 미적용 문장이 있다(정). 선례: T25-137·T25-142 가 같은 형태다 |

### 뮤테이션 검증 (구현 중 1회 — 검사가 실제로 실패할 수 있는지 확인)

각 신규 검사가 **실패할 수 있음**을 1회씩 확인하고 되돌린다. 이 저장소의 관례이며,
「검증을 추가할 때 그 검증이 실제 환경에서 성립하는지 먼저 확인한다」(karpathy 실패 사례 2번)의
직접 적용이다.

| 검사 | 주입할 변형 | 기대 |
|------|------------|------|
| T22-148 | `#dz-tooltip` 을 `.wrap` 안으로 옮긴다 | 실패 |
| T22-149 | `overflow-wrap:anywhere` 를 지운다 | 실패 |
| T22-150 | 템플릿에 `data-tooltip="x"` 한 개를 넣는다 | 실패 |
| T22-151 | 툴팁 IIFE 를 폴링 IIFE 앞으로 옮긴다 | 실패 |
| T22-152 / T25-144 | `user-select` 선언을 지운다 | 실패 |
| T22-153 | `'enter'` 리스너를 지운다 | 실패 |
| T25-145 | 허브 쪽 프리픽스만 지운다 | 실패 |
| T22-154 / T25-146 | 문서 토큰을 지운다 | 실패 |

### 수동 확인 (자동화 불가 — 브라우저 실측, 결과를 코드 주석에 남긴다)

| # | 확인 | 기록할 곳 |
|---|------|----------|
| M1 | S1·S2 — 잘린 항목에서만 툴팁이 뜬다(짧은 제목 0건) | `TOOLTIP_OVERFLOW_TOLERANCE_PX` 주석에 실측 `scrollWidth`/`clientWidth` 값 |
| M2 | S3 — 패널 최하단 항목에서 툴팁이 위쪽으로 뒤집히고 좌우가 클램프된다 | `tooltipPosition` 주석 |
| M3 | S5 — 툴팁 표시 중 폴링이 로그를 갱신하면 툴팁이 사라진다 | MutationObserver 주석 |
| M4 | S6·S7 — 네 문서(허브·단독 대시보드·패널 iframe·PiP) 전부에서 우클릭·선택 차단 | 잠금 IIFE 주석 |
| M5 | **S8 — 허브 카드 드래그 재정렬(Chrome 필수)** | 잠금 CSS 규칙 주석(결정 IL5) |
| M6 | S9 — 필터 라디오·`<details>` 토글·버튼 포커스 링 정상 | 잠금 CSS 규칙 주석 |

---

## 문서 정합 체크리스트

| 파일 | 반영할 것 |
|------|----------|
| `commands/dashboard_template.html` 머리 주석 | 「정적(불가침)」 목록에 `#dz-tooltip` 항목 추가(형식은 `#dz-log-card` 항목을 따른다). 상호작용 잠금 1문단 |
| `commands/dashboard.md` 「정적 요소 추가」 표 | `#dz-tooltip` 행 — *"작업 추적 제목의 말줄임 툴팁 싱글턴. `.wrap` **바깥**(`<body>` 직계). `init`/`step`/`log` 도, 폴링도 치환하지 않는다"* |
| `commands/dashboard.md` 「로그 항목 스키마」 | *"`.lead` 의 말줄임 툴팁은 런타임 감지다 — 이 스키마에 `title`·`data-tooltip` 을 각인하지 않는다"* 1줄 + 근거 링크 |
| `commands/dashboard.md` 「상호작용 잠금 계약」(신설, 「갱신 훅 계약」 옆) | 선택 차단은 `html` 규칙 1개, 우클릭 차단은 `document` 리스너 1개, PiP 문서는 `enter` 이벤트로 배선 |
| `docs/prps/dashboard-rationale.md` | `<a id="lead-tooltip"></a>` + *「`.lead` 툴팁 — 왜 각인이 아니라 런타임 감지인가」* 절(결정 LT2 요약) |
| `hub/bin/hub_template.html` 머리 주석 | 상호작용 잠금 1문단 — *"우클릭·선택 차단은 이 문서에만 적용된다. 상세 패널 iframe 안 문서는 자기 잠금을 갖는다"* |
| `hub/README.md` 「프로젝트 상세 패널」 | 툴팁 1줄 + 우클릭·선택 차단 1줄(패널 안 잠금은 대시보드 파일 세대에 달렸다는 사실 포함) |
| `hub/README.md` 「알려진 한계」 | 구세대 대시보드 조항에 *"잠금 CSS/JS 도 없어 패널 안에서만 네이티브 메뉴·텍스트 선택이 살아 있다"* 한 문장 추가 |
| `README.md` `commands` 표 | `dashboard` 줄 수(현재 1258)와 `dashboard_template.html(511줄)` 을 **구현 후 실측값**으로 갱신 |
| `tests/run.sh` | T22·T25 `test_desc` 범위 문자열 |

> **거짓말을 남기지 않는다**(IR9 계열). 특히 `hub/README.md` 「프로젝트 상세 패널」에 *"패널 안
> 대시보드는 원본 화면과 똑같이…"* 라는 서술이 있다 — 잠금 세대 차이로 **똑같지 않을 수 있는**
> 조건이 하나 늘었으므로 그 문단에서 「알려진 한계」로 넘기는 링크가 이미 있는지 확인한다.

---

## 리스크와 완화책

| # | 리스크 | 심각도 | 완화 |
|---|--------|--------|------|
| R1 | **WebKit 계열에서 `user-select:none` 이 `draggable` 드래그를 막는다는 보고** — 카드 재정렬이 조용히 죽을 수 있다 | 중 | S8 을 Chrome 에서 필수 실측(결정 IL5). 깨지면 `.card-drag-handle{-webkit-user-drag:element}` 한 줄. **되돌리기 비용이 1줄**이라는 점이 지금 예방 코드를 넣지 않는 근거다 |
| R2 | `documentPictureInPicture` 의 `'enter'` 이벤트가 대상 브라우저에서 발화하지 않으면 PiP 문서 잠금이 안 걸린다 | 낮 | M4 로 실측. 미발화 시 폴백은 폴링 IIFE 의 `.then(function(win){…})` 안 1줄(결합이 생기므로 **실측으로 필요가 증명될 때만**) |
| R3 | 잘림 판정 오차로 짧은 제목에 툴팁이 뜬다 | 낮 | `TOOLTIP_OVERFLOW_TOLERANCE_PX` + M1 실측 |
| R4 | 구세대 대시보드에서 요구 2가 부분 적용돼 "왜 여기만 우클릭이 되지?"로 보인다 | 낮 | 결정 IL6 + README 「알려진 한계」. 해소법(`/dashboard init` 재실행)이 이미 문서화돼 있다 |
| R5 | 템플릿이 511 → 약 610줄로 커진다 | 낮 | 전역 지침의 파일 상한(800줄) 안이다. 넘기 시작하면 그때 분할을 논한다 — 지금 나누면 단일 파일로 열려야 한다는 제약과 충돌한다 |
| R6 | 사용자가 나중에 "경로만은 복사하고 싶다"고 말한다 | 중 | 셀렉터 1개에 `user-select:text` 를 더하면 끝난다. **지금 예외를 만들지 않는 것이 그 대화를 쉽게 만든다**(예외가 없으면 "어디를 열어줄까"만 결정하면 된다) |
| R7 | 툴팁이 iframe 밖으로 못 나가 긴 제목이 여러 줄로 접힌다 | 낮 | 의도된 동작이다. 420px × 최대 `100vh-16px` 면 500자도 담긴다(허브 실측: 500자 한글이 420px 폭에서 179px 높이) |

---

## YAGNI 보류 (지금 만들지 않는다 + 재방문 트리거)

| 보류 | 재방문 트리거 |
|------|--------------|
| `.step-detail` 툴팁 | 사용자가 단계 상세도 안 읽힌다고 말할 때. 비용: 트리거 셀렉터 1개 추가 |
| 허브 `.detail-title` 툴팁 | 패널 헤드 이름이 실제로 안 읽힌다는 보고. 비용: `data-tooltip` 1개(허브는 시스템이 이미 있다) |
| 키보드(`focusin`) 툴팁 | 마우스 없는 시력 있는 사용자 보고 |
| 선택 차단 예외 규칙 | R6 |
| 툴팁 코드의 두 파일 공유 | 두 템플릿을 빌드하는 단계가 생길 때(지금은 없다) |
| `#dz-tooltip` 을 허브 툴팁과 시각적으로 픽셀 일치시키는 검사 | 두 툴팁이 실제로 어긋나 보인다는 보고 |

---

## 검토했으나 채택하지 않은 대안

1. **`.lead` 의 말줄임을 없애고 여러 줄로 흘린다** (`white-space:normal`)
   → 툴팁 자체가 필요 없어지지만, 로그 항목의 높이가 제목 길이마다 달라져 목록을 훑는 리듬이
   깨지고 `<summary>` 의 flex 배치(시각·배지·제목)가 무너진다. 무엇보다 **사용자가 툴팁을
   요청했다** — 요청과 다른 것을 조용히 주지 않는다.
2. **툴팁 대신 클릭하면 전문을 `.detail` 위에 펼친다**
   → `<details>` 토글과 클릭 대상이 겹쳐 두 동작이 한 클릭을 다툰다. hover 가 요청이다.
3. **허브가 iframe 안 `.lead` 를 읽어 허브 툴팁으로 띄운다**(같은 오리진이므로 기술적으로 가능)
   → 허브가 대시보드 DOM 내부 구조에 결합된다. 지금 허브는 iframe 문서를 **URL 과 훅 이름
   하나로만** 안다(IR4·SP1). 그 경계를 무너뜨리는 대가가 툴팁 하나보다 훨씬 크고, 단독 탭에서는
   아무 효과가 없다.
4. **`user-select:none` 대신 `selectstart` 이벤트를 preventDefault**
   → CSS 한 줄로 되는 것을 JS 리스너로 한다. PiP 문서에 별도 배선이 필요해지고(CSS 는 자동 승계)
   이득이 없다.
5. **`contextmenu` 차단을 `capture:true` 로**
   → 막을 대상이 없다(결정 IL3).
6. **잠금을 허브에만 넣고 iframe 은 `sandbox` 속성으로 제어**
   → `sandbox` 는 컨텍스트 메뉴를 제어하지 않으며, 대시보드의 스크립트·같은 오리진 접근
   (테마 동기화·갱신 훅)을 함께 죽인다.

---

## 구현 순서 (마일스톤)

각 단계 끝에 `bash tests/run.sh` 를 돌려 24/24 를 유지한다.

1. **요구 2 먼저 — 대시보드 템플릿**: `html{...}` 규칙 + 잠금 IIFE(메인 문서 → PiP 배선 순서).
   → 검증: M4(단독 탭·PiP)
2. **요구 2 — 허브 템플릿**: 같은 `html{...}` 규칙(문자 단위 동일) + 잠금 IIFE + 머리 주석.
   → 검증: M4(허브·패널 iframe), **M5(카드 드래그, Chrome 필수)**, M6
3. **요구 1 — 마크업·CSS**: `#dz-tooltip` 삽입(`.wrap` 앞) + `.tooltip` 2규칙.
   → 검증: `wrapReturnAnchor` 가 참조하는 노드가 그대로인지 PiP 열고 닫아 확인
4. **요구 1 — 툴팁 IIFE**(테마 IIFE 뒤): 상수 → 순수 함수(`tooltipPosition`·`isLeadTruncated`)
   → 표시/숨김 → 리스너 → MutationObserver.
   → 검증: M1·M2·M3
5. **문서 정합 8건** (위 체크리스트)
6. **테스트 신설 10건** + 두 `test_desc` 갱신 → **뮤테이션 검증 1회전**
7. `README.md` 줄 수 실측 갱신

---

## 승인 요청 항목

### 한눈에 보기

| # | 결정 | 요지 |
|---|------|------|
| 1 | LT2 | 툴팁 문구를 **마크업에 각인하지 않는다** — `/dashboard log` 절차와 이스케이프 규약은 한 글자도 바뀌지 않는다 |
| 2 | LT3 | 네이티브 `title` 이 아니라 **대시보드에 커스텀 툴팁 싱글턴을 신설**한다(약 55줄, 허브 코드와 같은 종류의 중복이 생긴다) |
| 3 | IL7 | **경로·세션 ID·로그 전문의 텍스트 복사가 두 화면 전체에서 불가능해진다.** 우회 장치를 만들지 않는다 |

### 승인 항목 1 — 마크업 각인을 하지 않는다 (결정 LT2)

각인 방식을 고르면 `dashboard.md` 의 「로그 항목 스키마」와 이스케이프 규약(`&`,`<`,`>` 3종 →
`"` 포함 4종, 그리고 텍스트용·속성용 2벌)을 개정해야 한다. 런타임 감지를 고르면 그 문서가
**바뀌지 않고**, 이미 쌓인 과거 로그 항목도 파일이 새 템플릿으로 다시 만들어지는 순간 함께
동작한다. 대신 대시보드 템플릿에 스크립트 약 55줄이 는다.

**승인이 필요한 이유**: 이 선택이 「어느 파일이 변하는가」를 통째로 가른다.

### 승인 항목 2 — 커스텀 툴팁 싱글턴 신설 (결정 LT3)

허브에 있는 것과 **같은 종류의 코드가 대시보드에도 생긴다.** 두 템플릿은 단일 파일로 배포되므로
공유 수단이 없고, 이 저장소는 이미 테마 토큰·테마 IIFE·폴링 골격을 같은 이유로 중복 보유한다.
네이티브 `title` 로 가면 약 8줄로 끝나지만, **약 5초 뒤 저절로 사라지는 툴팁**이 (요구 2로
텍스트 선택이 사라진 뒤) 긴 제목을 읽는 유일한 수단이 된다.

**승인이 필요한 이유**: 코드 중복을 받아들이는 판단이다.

### 승인 항목 3 — 복사·네이티브 메뉴 손실 (결정 IL7)

요구 2는 명시적 요청이므로 **구현한다.** 다만 대가를 확인받는다:
허브 카드의 프로젝트 경로·세션 ID, 대시보드 로그 상세의 명령어 조각을 **드래그로 복사할 수
없게 된다.** 우클릭 「검사」·「새 탭에서 열기」도 막힌다. 완화는 ① 요구 1의 툴팁(읽기는 된다)
② Ctrl+F 는 그대로 ③ 개발자 도구는 단축키로 열림 ④ 원문은 `hub.html`·`.claude/dashboard.html`
로컬 파일에 그대로 있다 — 네 가지다.

**되돌리기 비용**: 셀렉터 1개에 `user-select:text` 를 더하면 특정 영역만 복사 가능해진다.

---

## 부록 — 요구 1의 대상 확정 근거 (사용자 가설 검증 결과)

사용자가 *"요구 1이 손볼 곳은 허브가 아니라 대시보드 템플릿 쪽일 가능성이 높다 — 다만 그 판단
자체를 검증해 달라"* 고 했다. **검증 결과: 가설이 맞다.** 근거 세 가지를 파일에서 직접 확인했다.

1. `hub_template.html:505` 의 `#dzh-detail-frame` 은 `<iframe>` 이며, 패널 IIFE 가
   `location.replace` 로 `/project/<16hex>/dashboard.html` 을 싣는다.
2. `.lead` 클래스는 `hub_template.html` 전체에 **존재하지 않는다**(전수 grep). 오직
   `commands/dashboard_template.html:131` 에만 있다.
3. 이벤트·스타일 모두 문서 경계를 넘지 못한다 — 허브의 `document` 위임 리스너
   (`hub_template.html:663~680`)는 iframe 안 `mouseover` 를 받지 못하고, 허브 `<style>` 은 iframe
   문서에 상속되지 않는다.

**따라서 요구 1의 코드 변경은 `commands/dashboard_template.html` 단일 파일이며,
`hub/bin/hub_template.html` 은 요구 2 때문에만 열린다.**
