설계를 마치고 사용자 승인을 기다리는 세션에, 허브 카드의 세션 줄 첫 줄(상태 배지 바로 뒤)에 주황 테두리의 「◆ 승인 대기」 표지를 붙인다.
지금은 그 세션이 그냥 쉬는 세션과 똑같이 「○ 대기 · 제목 — 1/4 · 25%」로 보여, 상세 패널을 열어야만 승인을 기다린다는 것을 알 수 있다.
승인하면 허브 화면 파일 한 개와 진행 기록을 읽는 파이썬 모듈 한 개(「승인 단계가 진행 중」이라는 사실 하나)를 고치고, 그 계약을 잠그는 검사와 안내 문서를 함께 맞춘다.
수집·훅·서버 동작·기록 규칙은 바뀌지 않는다.

> 상태: **설계 — 사용자 승인됨** (2026-10-14). 설계 모델: opus(기본 — 승격 기준 미해당).
> 작업 위치: 워크트리 `.claude/worktrees/hub-approval-wait-badge`(브랜치 `feat/hub-approval-wait-badge`, develop `4ad7ee8` 기준).
> 목업: `/private/tmp/claude-501/-Users-byron-private-project-coding-harness/78af0cc6-ca1f-4841-a7b4-e8b1ed7085c7/scratchpad/hub-approval-wait-mockup.html`
> (PNG 전체 `…/scratchpad/hub-approval-wait-mockup.png`, 잘라 낸 것 `…-compare-light.png`·`…-compare-dark.png`·`…-states-light.png`·`…-interaction-dark.png`,
> 생성기 `…/scratchpad/build_mockup.py` — 템플릿 `<style>` 를 주석만 걷어 그대로 싣고 제안 규칙 1줄을 얹는다).
>
> 대상: `hub/bin/hub_parse.py`(사실 1개) · `hub/bin/hub_template.html`(렌더 IIFE·CSS 1규칙·머리 주석) · `tests/hub`(단위·계약·DOM) ·
> `tests/run.sh`(T25)·`tests/mutations.tsv` · `hub/README.md` · `README.md`(설계 문서 수) · 이전 PRP 1개의 개정 표기.
> **바꾸지 않는 것**: 훅·수집(`hub_collect`)·`SessionView`·`ProjectView`·상태 사다리(`_display_state`)·세션 정렬·숨김 규칙·서버·패널 IIFE·
> 세션 대시보드(`hub_dashboard_render`·`hub_dashboard_template.html`)·기록 규칙(`hub/rules/dashboard-recording.md`)·기록기.

---

## 1. 요구사항 요약

사용자 요구(원문): 「설계 단계 완료 후 승인 대기 시 대시보드 허브에서 승인 대기 중인 상태를 알 수 있으면 좋겠어. 상세보기 패널을 열지 않은
상태에서는 프로젝트 카드만 보고 대기 중인 상태를 알 수 없어.」

전체 경로 작업은 설계 PRP 를 쓴 뒤 `log design` 을 남기고 사용자 승인을 기다린다(`hub/rules/dashboard-recording.md`). 그 순간 진행 기록은
「설계=done, 승인=active」(`hub_parse._apply_log_kind_transition`)인데, 카드 세션 줄은 `○ 대기` 배지와 `제목 — 1/4 · 25%` 글자만 보인다 —
그냥 쉬는 세션과 같은 모양이다. 단계별 상태는 세션 줄을 눌러 여는 상세 패널(세션 대시보드)에서만 보인다. **카드를 열지 않고 한눈에 「이 세션은
내 승인을 기다린다」가 보여야 한다.** 범위는 이 한 신호다 — 다른 「사용자 판단 대기」(검수 미해결 종결·커밋 확인 등)로 넓히지 않는다(§8 대안 Q).

## 2. 이미 확인한 사실(출발점, 코드 정독)

| 사실 | 근거 |
|---|---|
| `log design` → 설계 done·승인 active, `log approve` → 승인 done·구현 active. 축약 경로(`구현\|검수`)에는 「승인」 단계가 없다 | `hub_parse._PHASE_NAME_BY_COMPLETION_KIND`(`approve → "승인"`)·`_apply_log_kind_transition` |
| 서버는 `tier1.steps[]`(이름·상태·detail)·`is_committed` 를 스냅샷에 싣지만 화면은 결정 LM12 뒤 둘 다 읽지 않는다 | `hub_parse.Tier1Snapshot`·`hub_template.html` `renderTier1` 주석 |
| 세션 줄 첫 줄 = `renderStateBadge(...)` + `.session-time`(+백그라운드 출력 갱신). `.session-line{display:flex;align-items:baseline;flex-wrap:wrap}` | `renderSessionContent`, CSS 510행 |
| 카드 목록 세션 줄과 카드 상세보기 세션 카드는 같은 조각(`renderSessionContent`)을 그린다 | 결정 SC6 |
| 서브에이전트 실행 칩의 단계 어휘는 `설계`·`구현`·`검수` 셋뿐이다 — 「승인」 칩은 존재할 수 없다 | `hub_session.Phase = Literal["설계","구현","검수"]` |
| 표시 사다리: done > interrupted > background(base idle 일 때만) > stale > base_state. base_state 는 working·idle·done 3값 | `hub_session._display_state` |
| LM5 의 기각안 (C) 「상태 배지 옆에 단계」는 「첫 줄 수준의 눈띔이 필요하다는 보고가 오면 그때 다시 본다」로 닫혔다 — **이번 요구가 바로 그 보고다** | `docs/prps/hub-session-row-layout-and-modal-size.md` LM5 기각 (C) |
| 라이트 테마 `--attention`(#B45309) 대비: `--surface` 위 5.02:1 · `--accent-soft`(열린 행) 위 4.06:1 · `--attention-soft` 위 4.39:1. 다크 `--attention`(#E69F00): `--surface` 위 7.29:1 | 계산(sRGB 상대 휘도) — 앞 두 값은 템플릿 `.badge.state-interrupted` 주석의 5.02·7.3 과 일치 |

설계 단계 실측(목업, 헤드리스 Chrome, 320px 트랙): §5 AW4 표.

---

## 3. 결정

### AW1 — 신호의 정의: 「승인 단계가 진행 중」 ∧ 「세션이 사용자 입력을 기다린다」

표지는 다음 셋이 모두 참일 때만 켜진다.

1. 세션이 자기 진행 기록을 갖고(`session.tier1` 존재) 그 기록에서 **「승인」이라는 이름의 단계가 `active`** 다(서버 사실, AW2).
2. 세션의 **`base_state` 가 `idle`** 이다 — 메인 턴이 끝나 사용자 차례다.
3. 표시 상태가 **`interrupted` 가 아니다.**

| 표시 상태 | base_state | 승인 active | 표지 | 이유 |
|---|---|---|---|---|
| `idle` 대기 | idle | ✓ | **있음** | 정형 사례 — 설계 보고 뒤 사용자 답을 기다린다 |
| `background` 백그라운드 대기 | idle | ✓ | **있음** | 메인 턴은 끝났다(사용자 차례). `log design` 뒤의 백그라운드는 설계 중 남은 잔여일 가능성이 크다(서브에이전트가 남긴 `tail -f` 류) — 그 작업이 끝나도 승인은 여전히 사용자 몫이다 |
| `stale` 소식 없음 | idle | ✓ | **있음** | 30분 넘게 답이 없다 = 승인 대기가 길어졌다. 오히려 가장 보여야 할 때다. 「▲ 소식 없음 · 직전 대기」 배지와 나란히 선다 |
| `stale` 소식 없음 | working | ✓ | 없음 | 마지막으로 알려진 상태가 「턴 진행 중」 — 사용자가 이미 답했거나 설계를 고치던 중에 조용해졌다 |
| `working` 작업중 | working | ✓ | 없음 | 사용자가 답했고(승인·수정 요청) 세션이 처리 중이다. `log approve` 직전 구간·설계 수정 구간이 여기다 |
| `interrupted` 한도 초과 | (무관) | ✓ | 없음 | 한도로 멈춘 턴은 대개 사용자 답을 처리하던 턴이다. 「한도 초과」 배지가 이미 사용자 조치를 말한다 |
| `done` 완료 | done | ✓ | 없음 | 세션이 끝났다 — 답할 세션이 없다 |
| 아무 상태 | — | ✗ | 없음 | 승인 단계가 아니다(설계 중·승인 뒤·축약 경로·「승인」 이름이 없는 목록) |
| 아무 상태 | — | 필드 없음·`tier1` 없음 | 없음 | 페일 클로즈 — 옛 서버 스냅샷(키 없음 → `undefined`)·대시보드 없는 세션은 오늘 화면 그대로 |

- **켜짐·꺼짐의 실제 흐름**: `log design` → (보고 턴이 끝나 대기) 표지 켜짐 → 사용자가 답해 작업중 → 꺼짐 → `log approve` → 승인 done, 이후 다시
  대기가 돼도 켜지지 않음. 사용자가 수정을 요청하면 작업중 동안 꺼졌다가 수정 보고 뒤 대기가 되면 다시 켜진다(승인은 여전히 active) — 정확하다.
- **비표준 단계 목록**: 이름이 정확히 「승인」인 단계만 본다. `조사|설계|승인|구현|검수` 처럼 「승인」이 든 목록은 `log design`(이름 기반)이나 `step <n> active`
  어느 쪽으로 active 가 돼도 켜진다. 「승인」이 여럿이면 어느 하나라도 active 면 켜진다(예: `설계|승인|구현|승인|배포` 에서 `log impl` 뒤 둘째
  승인). 「승인」이 없는 목록(`구현|검수`, `분석|확인|실행` 등)에서는 절대 켜지지 않는다 — 「사용자 확인」 같은 다른 이름을 승인으로 추정하지
  않는다(YAGNI·오탐 방지, 기록 규칙의 어휘가 「승인」 하나다).
- **판단 근거로 base_state 를 쓰는 이유**: `stale` 은 원래 상태를 가리는 오버레이라, 「사용자 차례인가」는 표시 상태가 아니라 그 아래의 base_state 가
  답한다. `background` 는 정의상 base idle 이다(`_display_state`). 그래서 규칙은 상태 나열이 아니라 「base idle ∧ interrupted 아님」 한 줄이다.

### AW2 — 판정 위치: 사실은 서버(★순수 `hub_parse`), 표시 판단은 클라이언트

> **MN5 로 판정이 서버로 옮겨졌다**(docs/prps/hub-macos-notification.md) — 아래 「표시 판단은 클라이언트」 중 승인 대기 판정(사실 ∧ base_state idle ∧ 한도 초과 아님)은 이제 서버(`hub_session.is_awaiting_approval`)가 하고 화면은 그 결과(`session.is_awaiting_approval`)만 읽는다. 사실 필드(`is_approval_step_active`)는 그대로다.

- **서버**: `Tier1Snapshot` 에 `is_approval_step_active: bool = False` 를 **맨 뒤**(`is_committed` 다음)에 더한다. `snapshot_from_events` 가 이미
  만든 `steps` 에서 순수 함수 `is_approval_step_active(steps)` 로 채운다. 단계 이름 리터럴 「승인」은 `hub_parse` 안 **한 곳**
  (`_APPROVAL_PHASE_NAME`)에만 두고 `_PHASE_NAME_BY_COMPLETION_KIND` 의 `approve` 값도 그 상수를 쓴다 — `log approve` 가 끄는 단계와 이 사실이
  보는 단계가 구성으로 같다. 직렬화는 `dataclasses.asdict` 라 자동이고, 이벤트 열의 함수라 「지금」 파생값이 아니어서 `snapshot_content_key` 에
  안전하다(LM6 의 `is_committed` 와 같은 모양).
- **클라이언트**: `isAwaitingApproval(session)` 이 그 사실과 `base_state`·`state`(AW1)를 합쳐 표시 여부를 정한다 — 「서버는 사실(bool)만, 표시 판단은
  화면」(결정 GN4·FT4·LM6 관례).
- **왜 서버까지 가나**: 클라이언트 단독(아래 대안 P1)도 가능하다 — `tier1.steps` 가 이미 실린다. 그래도 서버 사실을 고른 이유는 셋이다.
  ① 단계 이름은 진행 기록 어휘이고 그 어휘의 주인은 `hub_parse` 다 — 화면이 「승인」 리터럴을 두 번째로 갖지 않는다(두 번째 리터럴 + 교차 가드라는
  `SESSION_STATE_ORDER`·T25-219 식 비용을 만들지 않는다). ② 이 기능의 핵심 규칙(어느 기록 열에서 승인이 active 인가 — `step`·`fail`·이름 중복 등)이
  헤드리스 Chrome 없이 도는 빠른 단위 검사로 잠긴다(DOM 검사는 동시 부하에 약하다 — 메모리 「DOM 테스트는 동시 부하에 약하다」). ③ LM12 이후 화면은
  `steps` 를 읽지 않는다 — 다시 읽기 시작하면 「단계 이름을 화면이 해석한다」는 길이 다시 열린다(T25-281 ③ 이 그 길을 닫는다).

### AW3 — 표시 위치: 세션 줄 첫 줄, 상태 배지 바로 뒤

```html
<div class="session-line"><span class="badge state-idle"><span class="glyph" aria-hidden="true">○</span>대기</span><span class="badge approval-wait" data-tooltip="진행 기록이 「승인」 단계에 있고 세션이 사용자 입력을 기다리고 있습니다. 세션에 답하면(승인·수정 요청) 이 표시가 거둬집니다."><span class="glyph" aria-hidden="true">◆</span>승인 대기</span><span class="session-time"><span class="sr-only">작업 시작부터 </span>14분 소요</span></div>
```

- `renderSessionContent` 의 `renderStateBadge(...)` 호출 **바로 뒤**에 `renderApprovalWaitBadge(session)` 를 끼운다. 카드 목록 세션 줄과 카드 상세보기
  세션 카드가 같은 조각이라 두 화면에 함께 나온다(새 소비자 0).
- **첫 줄인 이유**: 사용자는 카드를 훑을 때 첫 줄의 배지 열을 읽는다. 진행률 줄은 세션 줄 아래쪽(발췌 뒤)이고 서브에이전트 실행 칩 바로 위라 LM12 의
  혼동 구역이다. **상태 배지 바로 뒤인 이유**: 「상태 + 그 상태의 이유(내 차례)」로 한 덩어리로 읽히고, 320px 에서 시간 글자가 줄바꿈되더라도 표지는
  배지와 같은 줄에 남는다(실측 §5).
- 상태 배지 자체·`STATE_LABEL`·정렬(`SESSION_STATE_ORDER`)·숨김(`shouldRenderSession`)·프로젝트 머리 배지·카드 glow 는 그대로다.
- `.session-meta` 는 여전히 첫 줄 밖이다(T25-127 불변 계약 무변경). 버튼 끝에 새 형제를 더하지 않으므로 2단 레일 전제(T25-262)도 그대로다.

### AW4 — 모양: `.badge` 어휘 + 주황 안쪽 링 + ◆ + 글자 + 기준 툴팁 (새 색 토큰 0, 세로 증분 0)

```css
.badge.approval-wait{background:var(--surface);color:var(--attention);box-shadow:inset 0 0 0 1px var(--attention)}
```

- **다중 채널(D4)**: 색(주황) + 형태(◆, 흰 면에 주황 실선 링) + 글자(「승인 대기」). 의미가 보이는 글자에 있으므로 `.sr-only` 보강은 필요 없다(색만으로
  뜻을 싣는 `.agent-chip-error` 와 다르다). 글리프는 `aria-hidden` — 낭독은 「대기, 승인 대기, 작업 시작부터 14분 소요」.
- **글리프 ◆(U+25C6)**: 상태 글리프 ●■◐○▲ 와 같은 기하 도형 블록이라 이모지로 그려질 위험이 없다(■ 를 고른 RI10 과 같은 기준). 상태 글리프와 겹치지 않는다.
- **주황(`--attention`) 계열인 이유**: 「사용자 조치가 필요하다」는 뜻 — 한도 초과(채움)·소식 없음(점선)과 같은 계열에서 **흰 면 + 실선 링**으로 형태가
  갈린다. 파랑(`--accent`) 계열은 작업중·백그라운드·열린 카드가 이미 쓴다.
- **면을 `--surface` 로 칠하는 이유(대비)**: 글자 `--attention` 은 `--surface` 위 5.02:1(라이트)·7.29:1(다크)로 WCAG AA(4.5:1) 통과. 면이 투명이면 열린 행
  (`--accent-soft`) 위에서 4.06:1, `--attention-soft` 면이면 4.39:1 로 둘 다 11px 글자에 미달이다. 링 자체(비텍스트)는 열린 행 위 4.06:1·다크 5.9:1 로 3:1 을 넘는다.
- **`border` 가 아니라 안쪽 링(`box-shadow:inset`)인 이유 — 실측**: 목업(320px 트랙)에서 「대기」 배지(테두리 없음, 19px) 옆에 1px `border` 표지를 두면
  첫 줄이 19→21px 로 자라고 상태 배지 중심이 +1.00px 내려간다(트리 갈고리 정렬 허용치 ≤1px 를 소진 — 템플릿 트리 주석 §11.6-4). 안쪽 링은 높이 19.00px·
  배지 중심 16.50px 로 **표지 없는 줄과 같다.** 링은 흐림·바깥 번짐·애니메이션이 없는 1px 테두리 대용이라 halo 금지(T25-190·243·250 의 정신)와 무관하다.
- **툴팁**: 판정 기준과 거둬지는 조건을 말한다 — 보이는 글자에 없는 정보라 R4 를 만족한다(소식 없음·백그라운드 배지 툴팁과 같은 관례). 정적 문구이며 직전 기록
  요약은 싣지 않는다(YAGNI — LM12 가 걷은 요약 툴팁을 되살리지 않는다). 버튼 안 요소라 hover 로만 뜬다(`.session-id` 칩과 같은 한계).
- **애니메이션 0**: glow 는 working 전용(T25-190 계열).

### AW5 — 결정 LM12 와의 관계: 걷힌 「진행중 단계 칩」을 되살리는 것이 아니다

LM12 가 칩을 걷은 이유는 「진행률 줄 맨 앞 단계 칩(`.agent-chip tier1-step`)이 바로 아래 서브에이전트 실행 칩(`.agent-chip`)과 **같은 모양·같은 단어**
(검수·구현)라 헷갈렸다」이다. 이번 표지는 그 혼동의 세 원인을 모두 비켜 간다.

| LM12 혼동의 원인 | 옛 단계 칩 | 이번 표지 |
|---|---|---|
| 자리 | 진행률 줄 맨 앞 — 실행 줄 바로 위(2단 가지 이웃) | 첫 줄(상태 배지 옆) — 실행 줄과 두 단 떨어진 1단 본문 |
| 모양 | `.agent-chip` 클래스째 재사용(모노스페이스·6px 모서리·`--soft` 면) | `.badge`(알약·비례 글꼴 800·999px 모서리) + 주황 링 — 상태 배지 어휘 |
| 단어 | 단계 이름 그대로(설계·구현·검수 — 실행 칩 라벨과 같은 집합) | 고정 문구 「승인 대기」 — 실행 칩 어휘(`Phase` = 설계·구현·검수)에 「승인」이 없어 겹칠 수 없다 |
| 빈도 | 대시보드가 있는 모든 세션에 늘 | 한 조건(AW1)에서만. 그때 세션은 사용자 차례라 강조색(실행 중) 칩이 없다 |

- 진행률 줄은 그대로 「제목 — 완료/전체 · %」 글자뿐이다 — T25-263(정+역)·DOM D27 은 **무변경으로 통과해야 한다.** D27 의 `idle-approval` 픽스처는 사실을
  켜도(AW2) 진행률 줄에 자식 요소가 0 임을 계속 단언하도록 고친다(§6).
- 새 역가드 T25-281 이 ① 표지가 `agent-chip` 을 쓰지 않음 ② `renderTier1` 이 표지를 부르지 않음 ③ 화면이 「승인」 리터럴로 단계를 해석하지 않음을 문다.
- LM5 기각 (C) 의 세 사유에 대한 답: ① 첫 줄 문자 단위 계약은 이후 meta 누출 금지(T25-127)로만 남았고 그것을 지킨다 ② 320px 최장 조합에서도 표지는 배지와 같은
  줄에 서고 가로로 넘치지 않는다(시간 글자만 둘째 줄로 감긴다 — §5 실측) ③ 「진행률과 단계를 두 번 말한다」 — 이번 것은 단계 이름이 아니라 「사용자 차례」
  하나라 진행률 줄과 겹치지 않는다.

### AW6 — 하지 않는 것 (YAGNI — 이번 요구는 승인 대기 하나다)

- **카드 머리(프로젝트 이름 줄) 표지 — 안 D, 기각(사용자 확인 항목 4)**: 320px 머리에 「◆ 승인 대기」를 더하면 프로젝트 이름이 사라지고 마지막 활동 시각이
  카드 밖으로 잘린다(목업 실측). 글리프만 두면 글자 채널이 빠진다. 머리 배지는 서버가 세션들을 우선순위로 접은 상태라(`_project_state`) 다른 세션이 작업중이면
  어차피 「작업중」이다. 세션 줄은 같은 카드에 늘 보인다(접힘 없음, TR1). 다시 볼 조건: 「세션이 많아 승인 대기 줄이 카드 스크롤 밖에 숨는다」는 보고.
- **세션 정렬 변경 없음** — 승인 대기 세션을 위로 올리지 않는다(`SESSION_STATE_ORDER`·T25-219 의 서버 대조를 흔들지 않는다).
- **12시간 숨김 예외 없음(사용자 확인 항목 5)** — 마지막 이벤트로부터 12시간 넘게 조용한 소식 없음 세션 줄은 지금처럼 숨긴다(결정 Z1). 그래서 밤을 넘긴
  승인 대기는 아침에 카드에서 사라질 수 있다. 예외를 두면 버려진 설계가 이벤트 창(오늘+어제) 동안 주황 표지로 남는다. 원하면 `shouldRenderSession` 의 한 조건
  (`&& !isAwaitingApproval(session)`)으로 바꿀 수 있다 — 결정 Z1 의 개정이라 사용자 확인을 받는다.
- **승인 대기 경과 시간 없음** — `design` 기록 시각은 스냅샷에 없다(`StepView.started_at` 은 늘 None). 첫 줄의 「N분 소요」로 갈음한다.
- **비표준 이름 인식·일반화 없음** — 「사용자 확인」 등 다른 이름, 검수 미해결 종결·커밋 확인 같은 다른 「사용자 판단 대기」는 다루지 않는다(§8 대안 Q).
- **기록 규칙·기록기 무변경** — `log design`·`log approve` 는 이미 규칙에 있다. 상시 로드 규칙 바이트(T26 계열)도 그대로다.

### AW7 — 문서 갱신

- `hub/README.md`: 「카드 한 장에…」의 세션 줄·진행률 줄 서술, 「화면 배치」에 **승인 대기** 항목 신설, 「툴팁」 트리거 목록에 승인 대기 표지, 「알려진 한계」 2줄
  (`log approve` 누락 시 / 12시간 숨김).
- `docs/prps/hub-session-row-layout-and-modal-size.md`: LM12 절 끝과 LM5 기각 (C) 끝에 `→ **후속(2026-10)** — hub-approval-wait-badge.md 결정 AW3·AW5(승인 대기
  한 가지만 첫 줄 표지로 — 단계 칩 부활 아님)` 한 줄씩.
- `README.md`: 「설계·조사 문서 87개」 → 88개(이 PRP).
- `hub_template.html` 머리 주석(데이터 계약 블록)의 「.tier1-active … 걷혔다」 문단 끝에 한 문장, `renderTier1` 주석에 한 구절(「승인 대기 표지는 첫 줄에
  산다 — AW3」).

---

## 4. 영향 범위

### 4.1 코드

| 파일 | 변경 | 결정 |
|---|---|---|
| `hub/bin/hub_parse.py` ★순수 | `_APPROVAL_PHASE_NAME = "승인"` 신설, `_PHASE_NAME_BY_COMPLETION_KIND["approve"]` 가 그 상수를 쓴다 · 순수 함수 `is_approval_step_active(steps)` · `Tier1Snapshot.is_approval_step_active: bool = False`(맨 뒤) · `snapshot_from_events` 가 채움. **주석에도 `open(`·`Path(`·`time.`·`os.` 를 쓰지 않는다(★순수 가드 T25-10 이 `open(`·`Path(`·`os.` 를 문다 — `time.` 은 같은 계열 가드의 관례)** | AW2 |
| `hub/bin/hub_template.html` JS | 상수 `APPROVAL_WAIT_LABEL`·`APPROVAL_WAIT_GLYPH`·`APPROVAL_WAIT_TOOLTIP` · 순수 함수 `isAwaitingApproval(session)` · `renderApprovalWaitBadge(session)` · `renderSessionContent` 의 상태 배지 호출 뒤 1호출 | AW1·AW3·AW4 |
| 〃 CSS | `.badge.approval-wait{…}` 1규칙(+ 왜 주석: 대비·안쪽 링 실측·LM12 관계). `.badge.state-done` 다음 자리 | AW4 |
| 〃 주석 | 머리 데이터 계약 블록 1문장 · `renderTier1` 주석 1구절 | AW7 |

### 4.2 정적 가드(T25)와 원장 — 번호는 병합 직전 develop 을 다시 세어 겹치면 다시 매긴다

| ID | 종류 | 내용 | 원장 행 |
|---|---|---|---|
| T25-280 신설 | 정(AW1~AW4·AW7) | ① `hub_parse.py` 에 `is_approval_step_active: bool = False` 선언 ② `isAwaitingApproval` 본문이 `tier1.is_approval_step_active` 를 읽는다(서버 필드 개명에 눈멀지 않게 — 메모리 「개명하면 정적 가드가 눈이 먼다」) ③ `renderSessionContent` 의 첫 줄 구간(T25-127 과 같은 awk 추출 — `class="session-line"` 뒤 첫 `</div>` 앞)에 `renderApprovalWaitBadge(session)` 가 있다 ④ `.badge.approval-wait{` 규칙이 있고 그 본문에 `animation` 이 없다 ⑤ `hub/README.md` 「화면 배치」에 `승인 대기` 서술(T25-36·T25-152 관례) | 변조행: ③ 의 호출을 지운다 → 「승인 대기 표지 호출이 첫 줄(session-line) 구성 안에 없음」 |
| T25-281 신설 | 역(AW5 — LM12 관계) | ① `renderApprovalWaitBadge` 본문에 `agent-chip` 이 없다 ② `renderTier1` 본문에 `approval-wait`·`renderApprovalWaitBadge` 가 없다 ③ 템플릿에 `'승인'`(따옴표로 닫힌 정확한 리터럴) 이 없다 — 화면이 단계 이름으로 승인을 다시 판정하지 않는다(라벨 `'승인 대기'` 는 걸리지 않는다) | 변조행: `class="badge approval-wait"` → `class="agent-chip approval-wait"` → 「승인 대기 표지가 실행 칩 클래스(agent-chip)를 씀」 |
| T25-201 개정 | 정 | `data-tooltip="` 리터럴 기대값 20 → **21**(표지 툴팁 +1) — 주석 이력에 한 줄 | 기존 행 그대로 |
| T25-127·T25-130·T25-262·T25-263 | — | **무변경으로 통과해야 한다**(첫 줄 meta 누출 금지·상태 배지 호출 리터럴·2단 레일 전제·진행률 줄 칩 부재) | — |

- 원장(`tests/mutations.tsv`) 2행 추가, 머리의 행 수 이력 주석 갱신, `tests/run.sh` 머리 「순증가 2」 이력 주석. 메시지는 반복문 밖 고정 문구(T25-263 관례 —
  판별자 자격, T37-13). 각 행의 `anchor_function` 은 가드가 사는 함수.

### 4.3 단위·계약·DOM 테스트

| 파일 | 변경 |
|---|---|
| `tests/hub/test_hub_parse.py` | 신설 `IsApprovalStepActiveTest`(§6.1) · `SnapshotFromEventsTest` 에 2건(설계 뒤 True·승인 뒤 False / 직렬화 키 존재·기본 False) |
| `tests/hub/test_hub_dashboard_contract.py` | 신설 `ApprovalWaitRoundTripTest` 1건 — 기록기가 실제로 쓴 `init '…' '설계\|승인\|구현\|검수'` → `log design` → 수집 스냅샷 True → `log approve` → False(기록 규칙 어휘 ↔ 파서 왕복) |
| `tests/hub/test_hub_template_dom_approval.py` **신규** | D43~D45(§6.2). 세션 줄 모듈(438행)에 붙이지 않는 이유: 표지 전용 픽스처·프로브(조건표·기하·폴링)를 더하면 한 모듈이 600행 안팎으로 커져 주제가 섞인다 |
| `tests/hub/test_hub_template_dom_session_row.py` | D27 개정 — `idle-approval` 픽스처에 `is_approval_step_active=True`(`_tier1` 에 인자 1개), 머리 주석의 「단계 이름은 어디에도 그려지지 않는다」를 「진행률 줄에는 …, 승인 대기 표지는 첫 줄(AW3)」로 정정. 단언 무변경 |

### 4.4 문서 — AW7 그대로.

---

## 5. 데이터 모델 · 인터페이스

### 5.1 서버 — `hub/bin/hub_parse.py`(★순수)

```python
# 진행 기록 어휘의 「승인」 단계 이름 — log approve 가 끝내는 단계와 is_approval_step_active 가 보는 단계를
# 한 리터럴로 묶는다(결정 AW2, docs/prps/hub-approval-wait-badge.md).
_APPROVAL_PHASE_NAME = "승인"
_PHASE_NAME_BY_COMPLETION_KIND = {"design": "설계", "approve": _APPROVAL_PHASE_NAME, "impl": "구현"}


def is_approval_step_active(steps: tuple[StepView, ...]) -> bool:
    """「승인」이라는 이름의 단계가 진행중(active)인가(결정 AW2). 그런 단계가 없으면 False."""
    return any(step.name == _APPROVAL_PHASE_NAME and step.state == "active" for step in steps)


@dataclass(frozen=True)
class Tier1Snapshot:
    ...
    is_committed: bool = False
    # 진행 기록의 「승인」 단계가 진행중인가(결정 AW2). 사실만 싣는다 — 세션 상태와 합쳐 표지를 보일지는 화면
    # (isAwaitingApproval)이 정한다(GN4·FT4·LM6 관례). 이벤트 열의 함수라 snapshot_content_key 에 안전하다.
    is_approval_step_active: bool = False
```

`snapshot_from_events` 의 반환에 `is_approval_step_active=is_approval_step_active(steps)` 한 줄. 스냅샷 JSON(`#dzh-data`)의
`projects[].sessions[].tier1` 에 키 하나가 늘고(프로젝트 단위 `projects[].tier1` 에도 실리지만 화면은 그리지 않는다 — MX4), 그 밖의 계약은 그대로다.

### 5.2 템플릿 — `hub/bin/hub_template.html`(렌더 IIFE)

```js
var APPROVAL_WAIT_LABEL = '승인 대기';
var APPROVAL_WAIT_GLYPH = '◆';   // 상태 글리프(●■◐○▲)와 같은 기하 도형 블록 — 이모지로 그려지지 않는다(RI10 기준)
var APPROVAL_WAIT_TOOLTIP = '진행 기록이 「승인」 단계에 있고 세션이 사용자 입력을 기다리고 있습니다. 세션에 답하면(승인·수정 요청) 이 표시가 거둬집니다.';

/** 승인 대기 표지를 보일 세션인가(결정 AW1) — 서버 사실 ∧ base_state idle ∧ 한도 초과 아님. 순수, 키가 없는 옛 스냅샷은 false. */
function isAwaitingApproval(session){
  if(!session.tier1 || !session.tier1.is_approval_step_active) return false;
  return session.base_state === 'idle' && session.state !== 'interrupted';
}

/** 첫 줄 상태 배지 뒤의 승인 대기 표지(결정 AW3·AW4). 해당 없으면 빈 문자열 — 첫 줄이 오늘과 같다. */
function renderApprovalWaitBadge(session){
  if(!isAwaitingApproval(session)) return '';
  return '<span class="badge approval-wait" data-tooltip="' + escapeHtml(APPROVAL_WAIT_TOOLTIP) + '">'
    + '<span class="glyph" aria-hidden="true">' + APPROVAL_WAIT_GLYPH + '</span>' + APPROVAL_WAIT_LABEL + '</span>';
}

// renderSessionContent — 첫 줄:
//   + renderStateBadge(session.state, session.base_state, session.last_event_at_ms, session.interruption, session.background_wait)
//   + renderApprovalWaitBadge(session)
//   + '<span class="session-time">…
```

폴링·틱 갱신은 기존 맞대기(H1⁗·PU1)가 맡는다 — 세션이 작업중이 되면 다음 렌더 결과에 표지가 없어 그 `span` 이 지워지고 세션 줄 노드는 그대로다.

### 5.3 설계 단계 실측(목업 측정 스크립트, 헤드리스 Chrome, 320px 트랙, 라이트)

| 경우 | 첫 줄 높이 | 상태 배지 중심(li 기준) | 표지가 배지와 같은 줄 | 가로 넘침 |
|---|---|---|---|---|
| 대기(표지 없음) | 19.00 | 16.50 | — | 없음 |
| 대기 + 표지(안쪽 링, **채택**) | 19.00 | 16.50 | 예 | 없음 |
| 대기 + 표지(1px border, 기각) | 21.00 | 17.50 | 예 | 없음 |
| 백그라운드 대기 + 표지 | 21.00(배지 자체 테두리) | 17.50 | 예 | 없음 |
| 소식 없음(표지 없음) | 21.00 | 17.50 | — | 없음 |
| 소식 없음 · 직전 대기 + 표지 + 「1시간 23분 소요」 | 45.50(시간 글자가 둘째 줄로 감김) | 17.50 | 예 | 없음 |

마지막 줄이 320px 최악 조합이다 — `.session-line` 의 `flex-wrap:wrap` 이 원래 맡는 거동이고(백그라운드 대기 + 출력 갱신 조합도 감긴다), 표지·배지 위치는 그대로다.
460px(1440 화면 3열의 실제 폭)에서는 모든 조합이 한 줄이다(목업 2번째 줄).

---

## 6. 테스트 계획

### 6.1 순수 로직 — `tests/hub/test_hub_parse.py`(빠름, Chrome 불필요)

`IsApprovalStepActiveTest` — 이벤트 열 → `snapshot_from_events(...).steps` → `is_approval_step_active`(AAA, 이름이 곧 사례):

| 사례 | 기대 |
|---|---|
| 4단계 init 만(설계 active) | False |
| `design` | **True** |
| `design`, `note` | True(note 는 전이 없음) |
| `design`, `approve` | False |
| `design`, `impl`(approve 누락) | False(구현까지 done) |
| `design`, `approve`, `impl`, `fail` | False(구현 active) |
| 축약 `구현\|검수` — 이벤트 없음·`impl`·`fail`·`pass` 각각 | 전부 False(승인 단계 없음) |
| 비표준 `조사\|승인\|실행` + `step 1 done` + `step 2 active` | True → 이어서 `step 2 done` 이면 False |
| 비표준 `분석\|확인\|실행` + `step 2 active` | False(이름이 「승인」이 아님) |
| `설계\|승인\|구현\|승인\|배포` + `design`·`approve`·`impl` | True(둘째 승인) |
| 표준 4단계 `pass` | False |

`SnapshotFromEventsTest` 2건: `design` 뒤 스냅샷 필드 True·`approve` 뒤 False / `dataclasses.asdict` 에 키가 있고 기본 False.
`ApprovalWaitRoundTripTest`(계약): 기록기 실제 호출 → 수집 → True/False — 「기록 규칙의 단계 이름」과 「파서가 보는 이름」이 어긋나면 여기서 깨진다.

### 6.2 화면 — `tests/hub/test_hub_template_dom_approval.py`(신규, 헤드리스 Chrome, 없으면 SKIP)

- **D43 표시 조건표** — AW1 표의 행마다 세션 1개(대기·백그라운드·소식 없음(직전 대기)·소식 없음(직전 작업중)·작업중·한도 초과·완료(발췌 있어 보이는)·사실 꺼짐·
  `tier1` 없음·**키 없는 옛 스냅샷**(픽스처 JSON 에서 키를 지운 것)) × 두 화면(카드 목록 줄·카드 상세보기 세션 카드). 표지 개수 1/0.
- **D44 자리·모양·LM12** — 표지가 있는 세션마다: `.session-line` 안이고 상태 배지의 `nextElementSibling` 이다 · 클래스에 `badge`·`approval-wait` 가 있고
  `agent-chip` 이 없다 · 글자 = `◆승인 대기`, 글리프 `aria-hidden="true"` · `data-tooltip` = 상수 문구 · `.tier1-pct` 의 자식 요소 0·글자 =
  「제목 — 완료/전체 · %」(LM12 유지) · `.agent-run-list .agent-chip` 수 불변.
- **D45 기하·갱신** — ① 320px 트랙(`#dzh-app` 의 `gridTemplateColumns='320px'`, D-LA6 관례)에서 「대기」 줄과 「대기 + 표지」 줄의 첫 줄 높이·상태 배지 중심 y 가
  같다(허용 0.5px) · 「소식 없음 · 직전 대기 + 표지 + 긴 소요」 줄에서 표지 top = 배지 top 이고 행에 가로 넘침이 없다 ② 폴링(`__triggerPoll`, 응답 스냅샷에서
  같은 세션이 `working`)으로 표지가 사라지고 세션 줄 노드가 같은 노드다(맞대기).
- D27 개정(§4.3) — 사실을 켠 `idle-approval` 에서도 진행률 줄 자식 요소 0.

### 6.3 일부러 깨뜨려 실패를 확인한다(구현 단계 — 결과를 구현 보고에 적는다)

| 변조 | 실패해야 하는 검사 |
|---|---|
| `is_approval_step_active` 의 `state == "active"` → `state != "done"` | `IsApprovalStepActiveTest`(init 만·축약 경로 사례) |
| 이름 조건 삭제(아무 active 나 True) | init 만(설계 active) 사례 |
| `snapshot_from_events` 가 필드를 채우지 않음 | `SnapshotFromEventsTest`·계약 왕복 |
| `isAwaitingApproval` 의 `base_state === 'idle'` 삭제 | D43 작업중·소식 없음(직전 작업중) 행 |
| `state !== 'interrupted'` 삭제 | D43 한도 초과 행 |
| 표지 호출을 `renderTier1` 끝으로 옮김 | D44·D27(진행률 줄 자식 요소)·T25-280 ③·T25-281 ② |
| 클래스를 `agent-chip` 으로 | T25-281 ①(원장 변조행)·D44 |
| 안쪽 링 → `border:1px solid` | D45 ①(첫 줄 높이·배지 중심) |
| 서버 필드만 개명 | T25-280 ②·D43 |
| 표지 호출 삭제 | T25-280 ③(원장 변조행)·D43 |

- **RED 확인**: 새 DOM 모듈을 변경 전 템플릿으로 돌린다(`DZH_DOM_TEST_TEMPLATE` — 기존 DOM 모듈 머리의 관례) → D43~D45 가 실패해야 한다.
- 원장 2행은 T37-13(판별자 자격·앵커)으로 확인한다. 전체 T37 은 커밋 직전 메인 세션의 전체 검증 1회에 맡긴다.
- 도구 함정(메모리): `python3 -B` 로 임포트(그렇지 않으면 `__pycache__` 가 T22-138 을 흔든다), `py_compile` 뒤 `__pycache__` 정리, DOM 모듈은 전체 스위트와
  겹쳐 돌리지 않는다(Chrome watchdog 거짓 실패), 긴 검사는 백그라운드 + 완료 알림(sleep 폴링 금지).
- 구현 완료 기준: 위 단위·계약·DOM 모듈 통과 + `bash tests/run.sh --only T25` + `python3 -m py_compile hub/bin/hub_parse.py`. 전체 검증(CLAUDE.md §4 네 명령)은
  메인이 커밋 직전 1회.

---

## 7. 마일스톤

| M | 내용 | 결정 | 검사 |
|---|---|---|---|
| M1 | 서버 사실 — `hub_parse` 상수·함수·필드 | AW2 | `test_hub_parse` · 계약 왕복 |
| M2 | 화면 표지 — JS 2함수·상수·CSS 1규칙·첫 줄 1호출·주석 | AW1·AW3·AW4 | DOM D43~D45 · D27 개정 · T25-280·281 · T25-201 |
| M3 | 문서 — hub/README·LM12 후속 표기·README 문서 수 | AW7 | T25-280 ⑤ |

M1 만으로는 화면이 바뀌지 않는다(사실만 실린다). M2 는 M1 에 의존한다.

---

## 8. 위험과 대안

### 8.1 위험

- **`log approve` 누락** — 사용자가 승인했는데 오케스트레이터가 기록을 빠뜨리면 승인은 active 로 남고, 구현 중 세션이 대기가 되는 짧은 구간마다 표지가 거짓으로 뜬다.
  첫 `log impl` 이 승인까지 done 으로 만들어 끝난다(`_apply_log_kind_transition`). 기록 규칙 위반의 증상이라 규칙 쪽은 바꾸지 않고 「알려진 한계」에 적는다.
- **`fail` 의 위치 규칙** — 비표준 3단계 `설계|승인|구현` 에서 `fail` 은 「완료 수 = 단계 수 − 2 = 1」이라 승인을 active 로 되돌려 표지가 뜬다. 검수 단계 없는 목록은
  워크플로 규칙(검수 생략 금지)과 어긋나는 드문 경우라 받아들인다(이번 표지는 기존 축약기의 결과를 그대로 비출 뿐이다).
- **밤을 넘긴 승인 대기** — 12시간 숨김(Z1)이 표지 있는 세션 줄도 숨긴다(AW6, 사용자 확인 항목 5).
- **320px 에서 줄 감김** — 「소식 없음 · 직전 대기」 + 표지 + 긴 소요 시간 조합은 시간 글자가 둘째 줄로 감겨 세션 줄이 약 24px 높아진다(§5.3). 340px 고정 카드에서 보이는
  세션 수가 그만큼 줄 수 있다. 표지·배지 위치와 가로 넘침은 문제없다.
- **툴팁은 hover 전용** — 표지는 버튼 안 요소라 키보드 포커스로 툴팁이 뜨지 않는다(`.session-id` 칩·발췌와 같은 기존 한계). 판정의 핵심(「승인 대기」)은 보이는 글자다.
- **곁가지 발견(이번 범위 밖, 언급만)**: 기존 `.badge.state-stale` 은 라이트 테마에서 글자 `--attention` 이 `--attention-soft` 면 위 4.39:1 로 11px 글자의 AA(4.5:1)에
  조금 못 미친다(계산). 이번 표지는 그 면을 쓰지 않는다. 고칠지는 별도 결정이다.

### 8.2 검토했으나 채택하지 않은 대안

**표시 위치·모양**(목업에 「현재 | 안 A | 안 B | 안 C | 안 D」로 나란히 있다)

- **안 B — 상태 배지 자체를 「◆ 승인 대기」로 바꾼다**: 한 칸으로 짧고 「대기 · 승인 대기」 중복이 없다. 기각 — ① 「소식 없음 · 직전 대기」(30분 넘게 무응답)·「백그라운드
  대기」라는 사실이 배지에서 사라진다(목업 2번째 줄 오른쪽) ② 배지가 말하는 상태와 정렬 키(`session.state`)·프로젝트 머리 배지가 어긋난다 ③ 상태 배지의 1:1 계약
  (`renderStateBadge(session.state, …)` 호출 리터럴 T25-130·`STATE_LABEL`/`STATE_GLYPH` 사전)에 화면 전용 의사 상태를 끼워야 한다.
- **안 C — 진행률 줄 끝에 「· 승인 대기」 글자**: 서버 사실만 읽고 요소를 더하지 않는다. 기각 — LM5 기각 (E)(「칩보다 덜 훑어진다」)와 같은 약점이고, 진행률 줄은 LM12 가
  정리한 자리이자 실행 칩 바로 위(혼동 구역)이며, D27 의 「진행률 줄 글자 = 제목 — 완료/전체 · %」 계약을 바꿔야 한다.
- **안 D — 카드 머리에도 표지**: AW6 첫 항목.

**판정 위치**

- **P1 — 클라이언트 단독(`tier1.steps` 에서 이름 「승인」 · active 를 찾는다)**: 서버 변경 0. 기각 — 단계 이름 리터럴이 화면에 두 번째로 생기고(교차 가드 필요), 핵심 규칙이
  Chrome 의존 DOM 검사로만 잠기며, LM12 이후 닫힌 「화면이 단계 이름을 해석한다」 길을 다시 연다(AW2).
- **P2 — 서버 완결(`SessionView.is_awaiting_approval` = 사실 ∧ 세션 상태)**: 프로젝트 머리 집계까지 서버에서 할 수 있다. 기각 — 「어느 상태에서 보일까」라는 표시 정책이
  서버로 간다(GN4·FT4 관례 위반), `SessionView` 맨 뒤 필드를 고정 검사하는 T25-150(`session_cost`)을 흔든다, 머리 집계는 AW6 에서 하지 않기로 했다.

**범위**

- **Q — 「사용자 판단 대기」 일반화**: 검수 미해결 종결(3회 FAIL)·커밋 확인 등 사용자가 답해야 하는 모든 구간을 같은 표지로. 기각(지금은) — 그 구간들은 진행 기록에 전용
  사실이 없어(새 `log` 종류가 필요하다) 기록 규칙·기록기·상시 로드 규칙 바이트까지 번진다. 요구는 승인 대기 하나다. 표지 함수가 「사실 ∧ base idle」 모양이라 나중에 사실을
  하나 더 받는 식으로 넓힐 수 있다.

---

## 9. 사용자 확인 항목 (쉬운 말)

1. **표시 위치와 모양(안 A)** — 설계를 마치고 내 승인을 기다리는 세션 줄의 첫 줄, 「○ 대기」 배지 바로 옆에 흰 바탕·주황 테두리의 「◆ 승인 대기」 표지를 붙입니다.
   **승인하면**: 카드를 열지 않아도 그 세션 줄에 주황 표지가 보이고, 세션에 답해 다시 일하기 시작하면 표지가 사라집니다. 카드 상세보기 창의 세션 카드에도 똑같이 나옵니다.
   진행률 줄(「제목 — 1/4 · 25%」)과 다른 배지·칩은 지금 그대로입니다.
2. **표지 문구** — 요청하신 말 그대로 「승인 대기」로 씁니다(다른 말을 원하시면 알려 주세요 — 예: 「승인 요청」).
   **승인하면**: 표지 글자가 「◆ 승인 대기」로 나옵니다.
3. **30분 넘게 답이 없을 때도 표시** — 답을 오래 미뤄 세션이 「▲ 소식 없음」이 돼도 표지를 계속 붙입니다. 반대로 한도 초과로 멈췄거나 세션이 끝났으면 붙이지 않습니다.
   **승인하면**: 「▲ 소식 없음 · 직전 대기」 옆에 「◆ 승인 대기」가 나란히 보입니다(좁은 화면에서는 시간 글자가 다음 줄로 내려갈 수 있습니다).
4. **카드 머리(프로젝트 이름 줄)에는 붙이지 않음** — 좁은 화면에서 프로젝트 이름이 아예 가려지기 때문입니다.
   **승인하면**: 카드 맨 위 줄은 지금과 같고, 승인 대기는 세션 줄에서만 보입니다.
5. **12시간 넘게 조용한 세션은 지금처럼 숨김** — 밤새 승인을 미루면 아침에는 그 세션 줄이 카드에서 사라질 수 있습니다. 원하시면 「승인 대기인 세션만은 숨기지 않기」로
   바꿀 수 있습니다(대신 버려진 설계도 이틀가량 주황 표지로 남습니다).
   **승인하면(지금처럼)**: 숨김 규칙은 바뀌지 않습니다.
6. **허브가 진행 기록에서 「승인 단계 진행 중」이라는 사실 하나를 더 읽어 화면에 넘깁니다** — 화면에는 보이지 않는 내부 변경입니다.
   **승인하면**: 위 표지가 이 사실을 근거로 켜지고 꺼집니다. 기록 방법(설계 뒤 `log design`, 승인 뒤 `log approve`)은 지금 그대로입니다.
