# Plan: 허브 macOS 알림 — 세션이 작업중에서 벗어나는 순간 시스템 알림을 띄운다

> 설계 문서(PRP). 결정 ID 접두는 **MN**(macOS Notification). 구현 전 사용자 승인 필요.
> 설계 모델: opus(승격 기준 미해당 — 3개 서브시스템 이하·데이터 모델 전면 개편 아님).
> **개정(2026-10-15, 사용자 결정 「역할 나누기」)**: 알림 종류를 「승인 대기·한도 초과」 둘로 줄였다 — 대기·백그라운드 대기 알림은 삭제.
> 질문·허락 요청·작업 완료는 데스크톱 앱 알림이 맡는다. 개정 근거와 내용은 [hub-notify-answer-wait.md](hub-notify-answer-wait.md)(AN1~AN6)이고, 아래 MN1·MN2·MN3·MN4·MN8·MN9·MN12·§16 쟁점 2 에 개정 줄을 붙였다. 본문 표·문구는 개정 전 기록이다.

## Summary

허브 상주 서버가 수집할 때마다 세션 상태를 직전 수집과 비교해, **작업중이던 세션이 대기·백그라운드 대기·승인 대기·한도 초과로
바뀌는 순간** macOS 시스템 알림(`osascript` 의 `display notification`)을 띄운다. 탭이 닫혀 있어도 몇 초 안에 울리도록, 알림을 켜면
유지보수 티커가 훅 이벤트 파일·세션 명부 파일의 변화를 보고 즉시 수집한다. 「승인 대기」 판정은 지금 화면(JS)에만 있으므로 서버
(Python) 한 곳으로 옮기고 화면은 그 결과만 읽는다 — 같은 규칙이 두 벌 생기지 않는다.

## User Story

여러 세션을 띄워 두고 다른 창에서 일하는 사용자로서, 세션이 내 입력·승인을 기다리게 되거나 한도로 멈추면 허브 탭을 보고 있지
않아도 macOS 알림으로 알고 싶다 — 그래야 세션이 몇십 분씩 나를 기다리며 노는 일이 없다.

## Problem → Solution

지금: 세션이 기다리는지는 허브 탭을 열어 배지를 봐야 안다. 탭이 닫혀 있으면 서버는 최대 5분 + 티커 주기마다만 수집한다.
→ 제안: 서버가 수집 결과의 상태 전이를 판정해 macOS 알림을 띄우고, 알림이 켜져 있으면 이벤트 파일 변화로 수집을 앞당겨 지연을
티커 주기(기본 5초) + 확인 지연 수준으로 줄인다. 허브는 계속 읽기 전용이고 쓰기 엔드포인트는 생기지 않는다.

## Metadata

- **Complexity**: Medium-Large (새 모듈 2 + 기존 8 파일 수정 + 문서·정적 가드)
- **Source PRD**: N/A (메인 세션 지시문)
- **PRD Phase**: N/A
- **Estimated Files**: 새 4(모듈 2·테스트 2) · 수정 약 14

---

## 1. 요구사항 요약

허브 상주 서버가 세션 상태 변화를 macOS 시스템 알림으로 알린다(브라우저 Notification API 는 쓰지 않는다 — 사용자가 고른 방식,
서버가 켜져 있을 때만 동작해도 된다). 허브는 읽기 전용을 유지한다 — 세션 제어(중단·지시·승인)와 쓰기 엔드포인트는 범위 밖이다.
알림 대상은 「작업중 → 대기(턴 끝)」·「◆ 승인 대기 진입」·「한도 초과로 멈춤」이고, 이 설계에서 「백그라운드 대기 진입」을 더한다
(MN4). 짧은 턴마다 울리지 않도록 소음 기준(MN2)과 확인 지연(MN3)을 둔다. 문자열은 AppleScript 소스에 끼워 넣지 않고 argv 로만
넘기며(MN8), 알림 문구에 프롬프트 발췌를 싣지 않는다(MN9).

**범위 밖**: 브라우저 카드의 「안 읽음」 점, 휴대폰·원격 알림, 알림 클릭 동작, 세션 제어.

## 2. 이미 확인된 사실 (설계의 전제 — 재측정하지 않았다)

| 사실 | 출처 |
|---|---|
| 수집 경로는 `_SnapshotRefresher` 하나다 — 요청(신선도 창 2초)과 유지보수 티커(배경 상한 5분)가 같은 락을 공유한다 | `hub/bin/hub_server.py:281-352`, `:419-452` |
| 티커는 `server_heartbeat_interval_seconds`(기본 5초, 하한 1초)마다 깬다 | `hub_server.py:452`, `hub_config.py:51-57` |
| 표시 사다리 done > interrupted > background(base idle 일 때) > stale > base_state, base_state 는 working·idle·done 3값 | `hub_session.py:365-395` |
| 백그라운드 대기는 보고 뒤 90분 상한이 지나면 스스로 거둬진다 — 「백그라운드 → 대기」 직행은 상한 만료·명부 이탈뿐이다(새 보고는 턴이 있어야 온다) | `hub_session.py:234-262` |
| 「승인 대기」 = `tier1.is_approval_step_active` ∧ `base_state == "idle"` ∧ `state != "interrupted"` — 지금은 **JS `isAwaitingApproval` 에만** 있다 | `hub_template.html:1801-1809`, `docs/prps/hub-approval-wait-badge.md` AW1·AW2 |
| 서버는 `config` 를 기동 때 한 번 받는다(`run_server(config)`). `update_check_enabled` 도 기동 시점 값이다 | `hub_server.py:522`, `hub.py:350-351` |
| 서버는 `start_new_session=True` 로 터미널과 분리돼 돈다 | `hub_daemon.py:180-185` |
| 세션 명부 `~/.claude/sessions/<pid>.json` 은 호스트가 상태(busy/idle)가 바뀔 때 다시 쓴다(키 `status`·`statusUpdatedAt`). 몇 초마다 다시 쓰이지는 않는다(설계 중 `ls -lT` 로 mtime 확인 — 1시간 넘게 그대로인 파일 존재). 같은 폴더에 `*.key` 도 있다 | 설계 중 관측 |
| **`osascript` 는 스크립트 뒤의 `-e` 를 옵션으로 다시 읽는다** — `osascript -e 'on run argv' … -e 'end run' '-e' 'x'` 는 구문 오류(exit 1). `--` 를 넣으면 `-e` 가 argv 항목 1 로 그대로 넘어간다. `" & (do shell script "…") & "` 같은 인젝션 문자열도 argv 로 넘기면 데이터로만 남는다 | 설계 중 실험(알림을 띄우지 않는 `return` 스크립트로 확인) |
| 허브 I/O 모듈은 경로 상수를 `Path.home()` 로 스스로 선언하고 `hub_collect` 를 임포트하지 않는다(순환 방지) | `hub_release_read.py:32-33`, `hub_server_state_read.py:33-44` |

---

## 3. 결정

### MN1 — 알림 규칙 하나: 「작업중에서 벗어나는 순간에만 울린다」

세션마다 수집 결과를 6개 국면(phase) 중 하나로 접는다(`hub_notify.notify_phase`, 위에서부터 먼저 맞는 것):

| 국면 | 조건(SessionView) | 비고 |
|---|---|---|
| `done` | `state == "done"` | 끝난 세션 — 울리지 않는다 |
| `interrupted` | `state == "interrupted"` | 한도 초과 |
| `awaiting_approval` | `is_awaiting_approval`(MN5) | 백그라운드 대기 + 승인 active 도 여기다(AW1 표 그대로) |
| `background` | `state == "background"` | 백그라운드 대기 |
| `working` | `base_state == "working"` | 「소식 없음」이 덮은 작업중(stale·base working)도 작업중이다 |
| `waiting` | 그 밖(base idle) | 「소식 없음 · 직전 대기」 포함 |

**알림은 직전 국면이 `working` 이고 지금 국면이 아래 넷 중 하나일 때만** 후보가 된다.

> **개정(2026-10-15, AN1)**: 아래 표의 `waiting`·`background` 두 행은 삭제됐다 — 알림은 `interrupted`·`awaiting_approval` 둘뿐이다. 후보는 working 에서 벗어난 모든 전이에서 만들고 종류는 확정 때 정한다(MN3 개정, [hub-notify-answer-wait.md](hub-notify-answer-wait.md) AN2).

| 지금 국면 | 알림 종류(`NotifyKind`) | 제목 어휘(화면 배지와 같다) |
|---|---|---|
| `interrupted` | `interrupted` | `■ 한도 초과` |
| `awaiting_approval` | `awaiting_approval` | `◆ 승인 대기` |
| `waiting` | `turn_ended` | `○ 대기` |
| `background` | `background_wait` | `◐ 백그라운드 대기` |

- **왜 「working 에서」만인가**: 사용자에게 의미 있는 사건은 「세션이 일을 멈췄다」 하나다. 다른 출발점(대기 → 소식 없음, 백그라운드 →
  대기 상한 만료, 작업중 → 완료)은 새 정보가 없거나(만료는 90분 늦은 알림이다) 사용자가 이미 아는 일(세션을 직접 닫았다)이다.
  한 줄 규칙이라 테스트 표가 작고, 「같은 전이로 두 번 울리지 않는다」가 구조로 성립한다 — 알림을 낸 뒤 국면이 바뀌어 다음 수집의
  직전 국면은 더 이상 `working` 이 아니다.
- 사용자가 제안한 「작업중 → 대기」·「승인 대기 진입」·「한도 초과」는 이 규칙의 세 행이다. `awaiting_approval` 은 `waiting` 보다 먼저
  판정되므로 승인 대기 진입은 「대기」 알림과 겹쳐 두 번 울리지 않는다(한 세션·한 전이에 알림 하나).
- **승인 대기의 재진입**: 수정 요청 → 작업중 → 다시 승인 대기는 다시 울린다(수정된 설계가 준비됐다 — AW1 의 켜짐·꺼짐 흐름과 같다).
  짧은 질의응답 턴은 MN2 가 걸러 낸다.

### MN2 — 소음 기준: 「바쁜 구간」이 2분 이상일 때만 (한도 초과는 예외)

> **개정(2026-10-15, AN2)**: 「백그라운드 대기를 거쳐도 끊기지 않는다」는 **승인 대기를 위해 유지**한다 — 백그라운드 대기 알림은 사라졌어도 짧은 마무리 턴의 승인 알림이 소음 기준에 지워지면 안 된다. `_BUSY_PHASES` 는 그대로다.

- **바쁜 구간(busy episode)** = 세션이 `working` 또는 `background` 로 이어 있는 시간. 시작은 그 세션이 비(非)바쁜 국면에서 `working` 으로
  들어온 것을 **처음 본 수집 시각**이고, 백그라운드 대기를 거쳐도 끊기지 않는다(MN4 — 깨어나 마무리한 턴이 짧아도 전체 일의 끝을
  놓치지 않게).
- 알림 후보의 바쁜 구간이 `NOTIFY_MIN_BUSY_EPISODE_MS = 2 * 60 * 1000` 미만이면 울리지 않는다. `interrupted` 는 길이와 무관하게 울린다 —
  한도는 계정 단위라 사용자가 보고 있지 않은 세션까지 한꺼번에 멈추고, 드물며, 「언제 다시 되는가」가 판단에 필요하다.
- **왜 기준이 필요한가**: 사용자가 키보드 앞에서 주고받는 짧은 질의응답 턴은 사용자가 이미 화면을 보고 있다 — 매번 울리면 알림 전체를
  끄게 된다(소음이 신호를 죽인다). 이 워크플로우의 위임 턴(설계·구현·검수 서브에이전트 실행, 백그라운드 검사)은 대개 수 분~수십 분이다.
- **왜 2분인가**: 측정한 값이 아니다(이력 재측정은 하지 않는다는 지시). 「질의응답 한 번(대개 1분 안쪽)은 거르고, 사용자가 다른 창으로
  갔을 법한 길이부터 울린다」는 판단의 하한이다. 이름 있는 상수 하나라 사용 후 조정이 한 줄이다. 설정 키로 열지 않는다(MN10 — YAGNI).
- 시작 시각을 「처음 본 수집 시각」으로 잡는 이유: `SessionView` 에는 턴 시작 시각이 없다(`task_started_at_ms` 는 작업 시작이라 몇 시간
  전일 수 있다). 알림이 켜져 있으면 `UserPromptSubmit` 이 MN6 의 즉시 수집을 부르므로 관측 시각은 실제보다 최대 티커 주기만큼 늦다.

### MN3 — 확인 지연: 전이를 한 번 더 본 뒤에 울린다

> **개정(2026-10-15, AN2)**: 후보는 working 에서 working 이 아닌 국면으로 나가는 **모든 전이**에서 만들고(`PendingNotice` 에서 `kind` 삭제), 종류는 확정 때 `NOTIFY_KIND_BY_PHASE.get(확정 국면)` 으로 정한다 — None(대기·백그라운드·완료)이면 알림 없이 후보만 거둔다. C1 의 「다른 알림 국면으로 바뀌면 후보를 다시 시작」은 「working 이 아닌 다른 국면」으로 넓어졌다.

- 「작업중 → X」를 처음 보면 **후보(pending)** 로만 둔다. 이후 `NOTIFY_SETTLE_MS = 3_000` 이상 지난 수집에서도 국면이 여전히 X 면 확정해
  울린다. 그 사이 국면이 작업중으로 복귀하면 후보를 버리고, **다른 알림 국면(대기·백그라운드 대기·승인 대기·한도 초과)으로 바뀌면 보존한 바쁜 구간 시작으로 그 국면의 후보를 다시 시작한다**(앞 후보는 확정 전에 사라지므로 한 전이에 알림은 하나다). 어느 쪽이든 **바쁜 구간 시작 시각은 그대로 둔다**. (2026-10-15 검수 1회차 C1 로 개정, 사용자 승인)
- **왜**: 백그라운드로 띄운 서브에이전트가 끝나면 `SubagentStop` → (호스트가 메인을 깨움) `UserPromptSubmit` 이 잇달아 온다. MN6 의 즉시
  수집이 그 틈에 걸리면 「작업중 → 대기 → 작업중」이 관측돼 **사용자가 자리를 비운 바로 그 순간에 가짜 「대기」 알림**이 간다(알림을 믿지
  못하게 만드는 오탐). 틈의 길이는 재지 않았다 — 같은 호스트 프로세스의 연속 동작이라 짧다고 보고, 「다음 수집에서 한 번 더 확인」이라는
  구조로 막는다. 3초는 티커 기본 주기(5초) 안에 들어가 확인이 대개 다음 틱 한 번에 끝나는 값이다.
- 후보가 있는 동안 티커는 `collect_if_older_than(now, NOTIFY_SETTLE_MS)` 로 확인 수집을 부른다(MN6). 그래서 알림 지연은 「이벤트 →
  수집(≤ 티커 주기)」 + 「확인(≥3초, 보통 다음 틱)」 ≈ 5~10초다.
- `interrupted` 도 같은 확인을 거친다(한도 초과는 끈적한 상태라 확인 비용이 없다 — 규칙을 하나로 둔다).

### MN4 — 백그라운드 대기 진입도 울린다

> **번복(2026-10-15, AN1)**: 백그라운드 대기 진입은 울리지 않는다. 데스크톱 세션의 「턴이 끝났다」는 앱의 「작업 완료」 알림이 알리고, 모니터를 건 세션에서 같은 문구가 반복됐다(약 59건/일). 터미널 세션은 그 알림을 잃는다 — 한계로 문서화했다([hub-notify-answer-wait.md](hub-notify-answer-wait.md) AN1·AN3).

- **포함한다.** 근거: 서브에이전트가 남긴 `tail -f`·개발 서버 같은 백그라운드 작업이 세션 전체의 목록에 남으면(호스트 목록은 세션
  단위라 누가 띄웠는지 모른다 — BW 결정), 메인이 일을 마치고 사용자를 기다려도 상태는 「백그라운드 대기」다. 이 진입을 빼면 그런 세션은
  **영영 울리지 않는다**(90분 뒤 상한 만료는 MN1 이 울리지 않는다). 알림 기능의 최악의 실패는 「기다리는데 침묵」이므로 이쪽을 막는다.
- **대가**: 메인이 자기 백그라운드 검사(전체 스위트 등)를 기다리며 턴을 끝낸 경우에는 진입 때 한 번(`◐ 백그라운드 대기 · 작업 1개를
  기다립니다`), 깨어나 마무리한 뒤 한 번(`○ 대기`) — 두 번 울린다. 문구가 「백그라운드 작업을 기다린다」고 말하므로 첫 알림은 훑고 넘길
  수 있다. 바쁜 구간이 백그라운드에서 끊기지 않으므로(MN2) 마무리 턴이 짧아도 두 번째 알림은 빠지지 않는다.
- 승인 active + 백그라운드면 국면이 `awaiting_approval` 이라(MN1 표) 설계 끝에 남은 잔여 작업이 승인 알림을 가리지 않는다.
- **사용자 확인 항목**(아래 「미결 쟁점」 2) — 반대 선택(빼기)도 한 줄 변경이다.

### MN5 — 「승인 대기」 판정을 서버 한 곳으로 옮긴다 (AW2 판정 위치의 부분 번복)

- **문제**: 알림은 서버가 내야 하는데 승인 대기 규칙은 화면(JS `isAwaitingApproval`)에만 있다. 서버에 같은 규칙을 다시 쓰면 두 벌이
  되고, 어긋나면 「표지는 떴는데 알림이 없다」(또는 반대)가 된다.
- **결정**: ★순수 `hub_session.is_awaiting_approval(state, base_state, tier1) -> bool` 을 신설하고, `compute_session_view` 가 그 결과를
  `SessionView.is_awaiting_approval: bool = False` 에 싣는다. JS `isAwaitingApproval(session)` 은 `return session.is_awaiting_approval ===
  true;` 한 줄이 된다. 규칙의 정본은 Python 하나, 소비자는 화면 표지와 알림 둘이다.
- **AW2 와의 관계**: AW2 는 「서버는 사실, 표시 판단은 화면」(GN4·FT4 관례)으로 P2(서버 완결)를 기각했다. 그때 기각 사유는 ① 표시 정책이
  서버로 간다 ② T25-150 을 흔든다 ③ 머리 집계를 안 한다였다. 지금은 ① 이 성립하지 않는다 — 이 판정은 더 이상 표시 전용이 아니라 알림의
  발화 조건이기도 한 **도메인 판정**이고, 서버는 이미 `state`·`tier1_is_finished_task` 같은 판정을 싣는다. ② 는 새 필드를 `session_cost`
  **앞**에 두어 피한다(T25-150 이 무는 것은 맨 뒤 = `session_cost`). AW2 의 장점(「승인」 리터럴을 `hub_parse` 한 곳에만 둔다, 핵심 규칙이
  Chrome 없는 빠른 단위 검사로 잠긴다)은 오히려 강해진다 — 상태 표까지 Python 단위 검사로 옮겨 온다.
- `snapshot_content_key` 안전: 이미 실린 `state`·`base_state`·`tier1` 의 함수라 「지금」 파생값이 아니다.
- 옛 서버 페이로드(키 없음)는 `undefined === true` → false — 오늘의 페일 클로즈 그대로.
- `Tier1Snapshot.is_approval_step_active` 는 그대로 둔다(이제 Python 판정의 입력). 화면은 더 이상 읽지 않는다.

### MN6 — 지연 대응: 알림이 켜져 있으면 「이벤트·명부 파일 변화」로 즉시 수집한다

- 유지보수 티커가 매 틱 **두 디렉터리의 서명**을 읽는다: `~/.claude/hub/events/*.jsonl`(훅 append)과 `~/.claude/sessions/*.json`(호스트
  상태 기록). 서명 = `(디렉터리 이름, 파일 이름, 크기, mtime_ns)` 의 frozenset. 직전 틱과 다르면 신선도 창과 무관하게 수집한다
  (`ACTIVITY_COLLECT_MAX_AGE_MS = 0` — 창 안의 캐시는 그 변화 **이전**에 만든 것일 수 있다). 강제 수집이 락을 기다리는 동안 다른 수집이 끝나도, 그 수집이 진입 **전에 시작**했다면 인정하지 않고 다시 수집한다(검수 1회차 C2 — 진입 뒤에 시작한 수집만 대신한다).
- **서명을 수집보다 먼저 읽는다** — 읽은 뒤 수집 사이에 온 이벤트는 그 수집에 포함되거나 다음 틱의 서명 변화로 다시 잡힌다(놓침 없음).
  첫 틱(직전 서명 없음)은 비교만 시작한다 — 기동 첫 수집은 배경 상한 경로가 이미 한다.
- **명부 폴더도 보는 이유**: `_compute_base_state` 는 명부 `busy` 가 훅의 `Stop` 을 이긴다(LS5). 호스트가 상태 파일을 `Stop` 훅보다 늦게
  쓰면 `Stop` 직후 수집은 여전히 작업중을 본다 — 명부 파일 변화도 수집을 부르면 어느 순서로 와도 마지막 쪽이 수집을 부른다.
- **`~/.claude/hub/` 자체는 보지 않는다(GOTCHA)** — `hub.html`·`notify_status.json` 쓰기가 다시 수집을 부르는 자기 유발 루프가 된다.
- 비용: 틱(5초)마다 디렉터리 2개 `scandir`(이벤트 ≤8개 + 명부 수십 개 stat). 훅은 턴·서브에이전트 경계에만 발화하므로 즉시 수집은 바쁜
  때도 틱당 최대 1회다.
- **알림이 꺼져 있으면 이 감시를 하지 않는다** — 오늘의 서버 동작(요청 구동 + 5분 상한)이 한 글자도 바뀌지 않는다.
- 후보(MN3)가 있으면 같은 틱에서 `collect_if_older_than(now, NOTIFY_SETTLE_MS)` 를 한 번 더 부른다(확인 수집).
- 기각한 방법: `select.kqueue` 파일 감시(표준 라이브러리지만 fd 수명·날짜 바뀜 새 파일·macOS 전용 분기 — 틱 주기 폴링으로 충분하다),
  훅이 서버에 HTTP 로 찌르기(새 엔드포인트 = 노출 표면 증가 + 훅 지연, 읽기 전용 원칙과 충돌).

### MN7 — 상태는 서버 메모리에만, 첫 관측은 기준선

- 세션별 직전 관측(`SessionTrack`)은 `SessionNotifier` 인스턴스(서버 프로세스 메모리)에만 있다. 디스크에 남기지 않는다.
- **서버 기동 후 첫 수집은 기준선만 잡고 울리지 않는다.** **처음 보는 세션도** 그 세션의 첫 관측은 기준선이다. 재기동·반복 수집에서 같은
  전이로 두 번 울리지 않는 근거가 이 둘 + MN1(「working 에서」만)이다.
- 수집에서 사라진 세션은 추적에서 지운다(메모리가 세션 창 크기를 넘지 않는다).
- **훅 폴백 경로(서버가 꺼졌을 때 훅이 spawn 하는 1회 수집)는 알리지 않는다.** 그 프로세스에는 직전 관측이 없고, 디스크에 상태를 두면
  폴백 수집끼리·서버와의 경합·잠금이 생긴다. 지시문의 「서버가 켜져 있을 때만 동작해도 된다」에 맞춘다.
- 동시성: `observe` 는 `_SnapshotRefresher` 락 안(`_collect_once`)에서만 불린다 — 수집과 같은 직렬화를 공유해 따로 락을 두지 않는다.
  티커가 읽는 `has_pending()` 은 통째로 교체되는 불변 매핑의 참조 하나를 읽을 뿐이라 경합이 생겨도 결과는 「확인 수집이 한 틱 늦거나
  한 번 더 일어남」뿐이다.

### MN8 — 전달: 고정 AppleScript + `--` + argv, 셸 없음, 별도 스레드

- 실행: `("/usr/bin/osascript", "-e", "on run argv", "-e", "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of
  argv)", "-e", "end run", "--", message, title, subtitle)` — `subprocess.run(argv, stdin=DEVNULL, capture_output=True, timeout=10, check=False)`.
  **스크립트 소스는 모듈 상수이고 사용자 문자열이 들어가는 자리가 없다.** 사용자 문자열은 `--` 뒤 argv 로만 간다(§2 실험: `--` 가 없으면
  `-` 로 시작하는 프로젝트 이름이 옵션으로 읽힌다).
- 셸을 거치지 않는다(`shell=` 없음, 리스트 argv) — `hub_release_read._run_git_ls_remote` 와 같은 규칙(T25-275 관례).
- 정제(`sanitize_notification_text`): C0 제어문자·DEL(줄바꿈 포함)을 공백으로, 연속 공백 1개로, 앞뒤 공백 제거, 길이 상한 + `…`.
  NUL 은 argv 에 들어가면 `ValueError: embedded null byte` 라 이 정제가 그 예외도 막는다.
- **별도 데몬 스레드에서 보낸다**(배치마다 1개, `threading.Thread(daemon=True)`). 수집 락 안에서 기다리면 요청 응답이 늦어지고, 티커가
  막히면 하트비트 TTL(15초)을 넘겨 훅이 서버를 죽었다고 보고 폴백 수집을 띄운다. 알림은 시간당 몇 건이라 배치당 스레드로 충분하다.
- 한 배치 안의 알림은 같은 스레드에서 차례로 보낸다(순서: 한도 초과 → 승인 대기 → 대기 → 백그라운드 대기). *(개정 2026-10-15, AN4: 대기·백그라운드 대기가 없어져 순서는 「한도 초과 → 승인 대기」 둘이다.)*
- 시간 초과 10초(`NOTIFY_SEND_TIMEOUT_SECONDS`) — `subprocess.run` 이 시간 초과 시 자식을 죽인다. osascript 는 손자를 만들지 않는다.

### MN9 — 문구와 프라이버시: 무엇을 싣고 무엇을 싣지 않나

> **개정(2026-10-15, AN1)**: 아래 표의 「대기」·「백그라운드 대기」 두 행과 싣는 것의 「백그라운드 작업 수」는 삭제됐다(`background_task_count` 필드째). 한 수집의 알림은 종류 수 최대 2건이다.

**싣는 것**: 상태 어휘(글리프 + 라벨) · 프로젝트 표시 이름(카드 머리와 같은 값) · 바쁜 구간 길이(분) · 한도 초기화 예정 시각 · 백그라운드
작업 수 · (`record_prompt_excerpt: true` 일 때만) 그 세션 진행 기록의 작업 제목(`tier1.title`, 시크릿 마스킹 `hub_redact.redact_secret_tokens`
→ 40자 상한)(공백 정규화 뒤 2,000자를 넘는 제목은 자르지 않고 통째로 버린다 — 검수 1회차 S1).

**싣지 않는 것**: 프롬프트 발췌 · 서브에이전트 제목·재개 요약 · 워크플로 라벨 · 세션 ID · 경로 · 계정 정보 · 모델.

작업 제목을 `record_prompt_excerpt` 에 묶는 이유: README 가 이미 「내용성 텍스트(서브에이전트 제목·워크플로 라벨)는 이 스위치 하나로
끈다」는 관례를 세웠다. 새 스위치를 만들지 않는다.

| 종류 | 제목(title) | 부제(subtitle) | 본문(message) |
|---|---|---|---|
| 한도 초과 | `■ 한도 초과 · {프로젝트}` | 작업 제목 또는 빈 값 | `사용량 한도로 멈췄습니다 · {HH:MM} 초기화 예정` (초기화 시각이 없으면 앞 절만) |
| 승인 대기 | `◆ 승인 대기 · {프로젝트}` | 작업 제목 또는 빈 값 | `{23분} 작업 뒤 승인을 기다립니다` |
| 대기 | `○ 대기 · {프로젝트}` | 작업 제목 또는 빈 값 | `{1시간 5분} 작업을 마치고 입력을 기다립니다` |
| 백그라운드 대기 | `◐ 백그라운드 대기 · {프로젝트}` | 작업 제목 또는 빈 값 | `{23분} 작업 뒤 백그라운드 작업 {N}개를 기다립니다` |
| 같은 종류 여러 세션(한 수집) | `{글리프} {라벨} · 세션 {N}개` | 빈 값 | `{프로젝트1} · {프로젝트2} · {프로젝트3} 외 {K}` (중복 이름은 한 번) |

- **같은 수집의 같은 종류는 한 알림으로 묶는다** — 한도는 계정 단위라 도는 세션이 한꺼번에 멈춘다. 한 수집에서 나가는 알림은 종류 수(최대 4)를
  넘지 않는다.
- 시간 표기: `HH:MM`(오늘) / `M/D HH:MM`(다른 날) — 화면과 같은 규칙. 길이: `N분` / `N시간 M분`(2분 미만은 MN2 로 나오지 않는다).
- 글리프·라벨은 화면 어휘(`STATE_GLYPH`·`STATE_LABEL`·`BACKGROUND_SESSION_LABEL`·`APPROVAL_WAIT_*`)와 같은 글자를 쓴다 — 규칙이 아니라
  어휘라 두 벌이 허용되고, 정적 가드 T25-287 가 화면에 같은 글자가 있는지 교차 확인한다.
- 길이 상한: 제목 60 · 부제 60 · 본문 120 · 작업 제목 40 · 묶음에 나열하는 프로젝트 3.

**hub/README.md 「프라이버시 고지」에 넣을 문장(초안)**:

> - **macOS 알림**(`notify_enabled: true`, 기본 꺼짐)은 세션이 작업중에서 대기·백그라운드 대기·승인 대기·한도 초과로 바뀔 때 시스템 알림을
>   띄운다. 알림에는 상태 이름·프로젝트 표시 이름·작업 시간(분)·한도 초기화 예정 시각·백그라운드 작업 수와, `record_prompt_excerpt` 가 켜져
>   있으면 진행 기록의 작업 제목(시크릿 마스킹 후 40자)만 실린다 — 프롬프트 발췌·서브에이전트 제목·세션 ID·경로·계정 정보는 싣지 않는다.
>   **알림 문구는 화면 배너와 macOS 알림 센터 기록에 남고, 잠금 화면에도 보일 수 있다**(시스템 설정 › 알림의 「미리보기 보기」가 정한다).
>   알림은 macOS 기본 도구 `osascript` 로 보내므로 출처가 「스크립트 편집기」로 보이고 그 앱의 알림 설정을 따른다. 허브는 알림 문구를 파일에
>   남기지 않는다 — `notify_status.json` 에는 시각·실패 사유·종료 코드만, `server.log` 에는 실패 사유·종료 코드와 AppleScript 오류 번호만 남는다(osascript 오류문은 알림 문구를 인용할 수 있어 옮기지 않는다 — 검수 1회차 S2).
>   끄는 수단은 `notify_enabled: false` 와 `/hub server restart` 다.

### MN10 — 설정: `notify_enabled`(기본 **false**), 서버 기동 때 읽는다

- `HubConfig.notify_enabled: bool = False`(맨 뒤), `hub_config._CONFIG_FIELD_TYPES["notify_enabled"] = bool`.
- **기본 꺼짐(옵트인) 근거**: ① 이 저장소는 공개 배포물이라 업데이트만으로 모든 설치 머신에 OS 배너가 갑자기 뜨면 놀랍다 ② 첫 알림에
  macOS 권한 질문이 뜰 수 있다 ③ 프로젝트 이름이 잠금 화면·알림 센터에 남는다 — 사용자가 알고 켜야 하는 노출이다. 선례: 사용량 API 폴링
  (`usage_api_enabled`, 기본 off), 훅 설치(옵트인). 이 PC 는 `config.json` 에 한 줄 + `/hub server restart` 로 켠다.
- **기동 시점 값**: `update_check_enabled` 와 같다 — 바꾸면 `/hub server restart`. `/hub status` 의 `notify_active`(MN11)가 「켰는데 아직 재기동
  안 함」을 드러낸다.
- macOS 가 아니거나 `/usr/bin/osascript` 가 없으면 알림기를 만들지 않고 `server.log` 에 한 줄 남긴다.
- **열지 않는 설정**(YAGNI): 종류별 스위치, 2분 임계값, 확인 지연. 사용 후 소음이 실제로 문제가 되면 그때 연다.

### MN11 — 관측: `notify_status.json` · `server.log` · `/hub status`

- `~/.claude/hub/notify_status.json`(`NotifyStatusRecord`): `active_since_ms`(알림기를 만든 서버 기동 시각) · `last_attempt_at_ms` ·
  `last_success_at_ms` · `last_failure_reason`(`osascript_missing`·`timeout`·`exit_nonzero`) · `last_failure_exit_code`. 기동 때 1회, 배치마다
  1회 원자적으로 쓴다(`hub_atomic_write`, `release_check.json` 과 같은 모양). 기동 때는 직전 기록의 나머지 필드를 보존하고 `active_since_ms`
  만 바꾼다. 쓰기 실패는 `server.log` 한 줄로 흡수한다(알림기는 그대로 돈다).
- `server.log`: 전송 실패마다 `알림 전송 실패({reason}, exit {code}): AppleScript 오류 번호 {-NNNN}`(번호가 없으면 고정 문구 — stderr 의 글은 알림 문구를 인용할 수 있어 싣지 않는다, 검수 1회차 S2). 비 macOS·osascript 부재 시 기동 때 한 줄.
- `/hub status` 에 3필드: `notify_enabled`(config 값) · `notify_active`(서버가 살아 있고 `active_since_ms ≥ server.json.started_at_ms`) ·
  `notify_status`(기록 그대로 또는 null). `commands/hub.md` 의 상태 필드 문단에 같은 3필드를 설명한다.
- **관측할 수 없는 실패(알려진 한계)**: macOS 알림 설정에서 「스크립트 편집기」 알림이 꺼져 있거나 집중 모드면 `osascript` 는 exit 0 으로
  끝나고 배너만 안 뜬다 — 허브는 성공으로 기록한다. README 에 확인 방법(터미널에서 `osascript -e 'display notification "test"'`)을 적는다.

### MN12 — 하지 않는 것

브라우저 Notification API · 「안 읽음」 점 · 휴대폰·원격 알림 · 알림 클릭 동작(누르면 스크립트 편집기가 열릴 수 있다 — 한계) · 종류별 스위치 ·
임계값 설정 키 · 테스트 알림 명령(`/hub notify test`) · 쓰기 엔드포인트 · `terminal-notifier` 등 새 의존성 · 훅 폴백 경로의 알림 · 「완료」·
「소식 없음」 진입 알림 · 탭이 보고 있을 때 알림 억제(화면 → 서버 쓰기 경로가 필요하다) · *(개정 2026-10-15, AN1)* 대기·백그라운드 대기 진입 알림 — 데스크톱 앱의 작업 완료 알림과 겹치고 모니터 세션에서 반복됐다.

### MN13 — 문서 갱신

`hub/README.md`(새 절 「macOS 알림」, 「서버」 1문장, 「화면 배치」 승인 대기 문장 정정, 「프라이버시 고지」 1항, 「알려진 한계」 3항, 「설정」
표 1행, 「파일 배치」 `notify_status.json`·「37개 파일」 2곳, 「설계 근거」 문서 이름) · `commands/hub.md`(상태 3필드) · 루트 `README.md`
(`docs/prps/` 문서 수 88 → 89, 병합 직전 재계수) · `hub_template.html` 머리 데이터 계약 주석(168~169행) 1문장.

---

## 4. UX Design

### Before
```
┌ 다른 앱에서 작업 중 ───────────────────────┐
│  (허브 탭은 닫혀 있거나 뒤에 있다)            │
│  세션 A: 23분 전에 설계 끝 → 승인 대기 중      │  ← 아무도 모른다
│  세션 B: 한도 초과로 멈춤                     │  ← 아무도 모른다
└──────────────────────────────────────────┘
  허브 탭을 열어야 배지(◆ 승인 대기·■ 한도 초과)로 안다. 탭이 닫혀 있으면 수집도 최대 5분 늦다.
```

### After
```
┌ 다른 앱에서 작업 중 ──────────────┐  ┌ macOS 배너(우상단) ─────────────────────┐
│                                  │  │ [스크립트 편집기 아이콘]           지금 │
│                                  │  │ ◆ 승인 대기 · coding-harness           │
│                                  │  │ 허브 macOS 알림 설계                    │
│                                  │  │ 23분 작업 뒤 승인을 기다립니다           │
└──────────────────────────────────┘  └───────────────────────────────────────┘
  이벤트 → 5~10초 안에 배너. 허브 탭 화면은 바뀌지 않는다(승인 대기 표지 판정 위치만 서버로 이동, 그려지는 결과 동일).
```

목업(배너 문구 · 라이트/다크 · 묶음 · 긴 이름 · 작업 제목 끔): 최종 보고의 목업 경로 참조.

### Interaction Changes

| Touchpoint | Before | After | Notes |
|---|---|---|---|
| 세션 턴 끝(≥2분 작업) | 없음 | `○ 대기` 배너 | MN1·MN2 |
| 설계 끝 → 승인 대기 | 탭의 표지만 | `◆ 승인 대기` 배너 | MN1·MN5 |
| 한도 초과 | 탭의 배지만 | `■ 한도 초과` 배너(초기화 시각) | 묶음 MN9 |
| 백그라운드 대기 진입(≥2분) | 탭의 배지만 | `◐ 백그라운드 대기` 배너 | MN4 |
| 허브 탭 화면 | — | **변화 없음** | 표지 판정 위치만 이동(MN5) |
| `/hub status` | — | `notify_enabled`·`notify_active`·`notify_status` | MN11 |
| 알림 클릭 | — | 스크립트 편집기가 켜지며 파일 열기 창이 뜸(M6 실측) | 한계 |

---

## 5. 영향 범위 (Files to Change)

| 파일 | 동작 | 이유 |
|---|---|---|
| `hub/bin/hub_notify.py` | **CREATE** ★순수 | 국면 판정·전이·확인 지연·문구 조립·argv 조립·상태 기록 갱신(MN1~MN3·MN8·MN9·MN11) |
| `hub/bin/hub_notify_send.py` | **CREATE** I/O | `osascript` 실행·전송 스레드·`notify_status.json` 읽기/쓰기·활동 서명 읽기·`SessionNotifier`(MN6~MN8·MN11) |
| `hub/bin/hub_session.py` | UPDATE | `is_awaiting_approval()` ★순수 + `SessionView.is_awaiting_approval: bool = False`(`session_cost` **앞**) + `compute_session_view` 가 채움(MN5) |
| `hub/bin/hub_server.py` | UPDATE | `_run_collect_cycle(…, notifier=None)` → 성공 시 관측 전달 · `_SnapshotRefresher(httpd, notifier=None)` · `_maintenance_loop(…, notifier=None, activity_directories=())` 활동·확인 수집 · `run_server` 가 알림기 생성, 스레드 기동은 `_start_background_threads` 로 분리(MN6·MN7, 검수 1회차 D4) — 577 → 약 690행 |
| `hub/bin/hub_model.py` | UPDATE | `HubConfig.notify_enabled: bool = False`(맨 뒤) |
| `hub/bin/hub_config.py` | UPDATE | `_CONFIG_FIELD_TYPES` 에 `"notify_enabled": bool` |
| `hub/bin/hub.py` | UPDATE | `cmd_status` 3필드(MN11) |
| `hub/bin/hub_template.html` | UPDATE(최소) | `isAwaitingApproval` 본문 1줄 + 그 위 주석 · 머리 데이터 계약 주석 1문장(MN5). **CSS·마크업 무변경** |
| `hub/install.sh` | UPDATE | `HUB_FILE_COUNT=35` → `37`(배포는 `hub/bin` 최상위 glob 이라 목록 수정 없음) |
| `hub/README.md` | UPDATE | MN13 |
| `commands/hub.md` | UPDATE | `/hub status` 3필드 설명(MN11) |
| `README.md`(루트) | UPDATE | `docs/prps/` 문서 수 88 → 89(병합 직전 재계수) |
| `docs/prps/hub-approval-wait-badge.md` | UPDATE(1줄) | AW2 「판정 위치」가 MN5 로 부분 번복됐다는 표기 |
| `tests/hub/test_hub_notify.py` | **CREATE** | 순수 로직(§9.1) |
| `tests/hub/test_hub_notify_send.py` | **CREATE** | I/O·알림기(§9.2) |
| `tests/hub/test_hub_session.py` | UPDATE | `is_awaiting_approval` 표(§9.3) |
| `tests/hub/test_hub_server.py` | UPDATE | 관측 배선·티커 활동 수집(§9.4) |
| `tests/hub/test_hub_config.py` | UPDATE | `notify_enabled` 기본·타입 |
| `tests/hub/test_hub_template_dom_approval.py` | UPDATE | 픽스처가 `is_awaiting_approval` 을 Python 함수로 채움 · 옛 페이로드 흉내가 지우는 키를 `is_awaiting_approval` 로(§9.5) |
| `tests/run.sh` | UPDATE | T25-10 순수 목록 + `hub_notify.py` · T25-104/T25-149 35→37 · T25-280 ①② 재조준 · 신설 T25-285~287 · 그룹 설명 범위 문자열 · `SOURCE_GUARD_ID_FLOOR`·`LEDGER_MUTATION_ROW_FLOOR` |
| `tests/mutations.tsv` | UPDATE | 신설 가드 3건의 변조행 |

**영향 없음(확인함)**: 상시 로드 컨텍스트(T26 — `CLAUDE.md`·`rules/README.md`·`rules/common`·`rules/workflow` 무변경) · `hub/rules/dashboard-recording.md`
(진행 기록 규칙·`HUB_DASHBOARD_RULE_BUDGET_BYTES` 무변경) · 훅(`hub_hook.py` 무변경 — append 만 하는 계약 그대로) · `install.sh`(루트) ·
`removals.txt`(지우거나 개명하는 관리 파일 없음).

### 동시 작업 주의 (병합 직전 필수)

- 설계 시점에 다른 세션이 브랜치 `feat/hub-light-theme-sunset` 에서 `hub/bin/hub_template.html`·`hub/README.md`·`tests/run.sh`·`tests/mutations.tsv`
  를 고치고 있었다 — 그 작업은 PR #6 으로 develop 에 먼저 들어갔고, 이 브랜치는 병합 커밋 `0c1bcca` 로 따라잡았다.
- **템플릿 수정은 JS 함수 본문 1곳 + 주석 2곳으로 최소화한다**(CSS·토큰 무변경 — 라이트 테마 작업과 겹치지 않는 구역).
- **새 검사 번호(T25-285~287)와 `SOURCE_GUARD_ID_FLOOR`(565)·`LEDGER_MUTATION_ROW_FLOOR`(139)·T25 그룹 설명의 범위 문자열(`T25-1~T25-287`)·루트 README 문서
  수(90)는 develop 병합 뒤 다시 세어 확정했다**(라이트 테마 PR #6 이 T25-282~284 를 먼저 썼다). 본문의 T25-285~287 은 확정 번호다.
- `hub/README.md` 는 절 단위로 넣어 충돌 구역을 줄인다(새 절은 「새 버전 알림」 뒤·「설정」 앞).

---

## 6. 파일 구조와 모듈 경계

```
hub/bin/
├── hub_notify.py        ★순수 (새) — 입력: HubSnapshot·직전 추적·시각. 출력: 추적·확정 알림·문구·argv·상태 기록.
│                         임포트: hub_model(타입)·hub_session(타입)·hub_redact. 파일시스템·시각·환경변수 없음(T25-10 편입).
├── hub_notify_send.py   I/O (새) — subprocess·threading·파일·시각. 임포트: hub_notify·hub_atomic_write·hub_model.
│                         hub_collect·hub_server 를 임포트하지 않는다(순환 방지 — hub_server 가 이 모듈을 부른다, T25-279 관례).
├── hub_session.py       ★순수 (수정) — is_awaiting_approval 의 정본.
└── hub_server.py        I/O (수정) — 배선만: 수집 성공 → notifier.observe, 티커 → 서명·확인 수집.
```

- 레이어 원칙(rules/workflow/code-quality-baseline.md · hub 관례 「★순수 규칙 + I/O 호출자」): `hub_release.py`/`hub_release_read.py`,
  `hub_usage.py`/`hub_usage_fetch.py` 쌍과 같은 모양이다. I/O 모듈의 동사형 접미(`_send`)는 `hub_usage_fetch.py` 선례를 따른다.
- 레이어 간 통신은 아래 §7 의 frozen dataclass 로만 한다.
- 순환 없음: `hub_session` ← `hub_notify` ← `hub_notify_send` ← `hub_server`. `hub_session`·`hub_model` 은 `hub_notify` 를 모른다.

## 7. 데이터 모델 (hub_notify.py ★순수, 전부 `@dataclass(frozen=True)`)

```python
NotifyPhase = Literal["working", "background", "waiting", "awaiting_approval", "interrupted", "done"]
NotifyKind = Literal["turn_ended", "background_wait", "awaiting_approval", "interrupted"]
NotifyFailureReason = Literal["osascript_missing", "timeout", "exit_nonzero", "invalid_text"]   # invalid_text: NUL·고립 서로게이트 등 argv 로 만들 수 없는 문구(검수 1회차 S3)

class SessionObservation:           # 수집 1회에서 세션 1개를 알림 관점으로 접은 값
    session_id: str
    phase: NotifyPhase
    project_name: str               # ProjectView.display_name
    task_title: str | None          # session.tier1.title 원문(마스킹·자르기는 문구 조립 때)
    resets_at_ms: int | None        # phase == "interrupted" 일 때 interruption.resets_at_ms, 아니면 None
    background_task_count: int      # phase == "background" 일 때 task_count + wakeup_count, 아니면 0

class PendingNotice:                # 확인 대기 중인 후보(MN3)
    kind: NotifyKind
    observed_at_ms: int             # 전이를 처음 본 수집 시각
    busy_duration_ms: int           # 그 시각까지의 바쁜 구간 길이

class SessionTrack:                 # 세션별 직전 관측(MN7)
    phase: NotifyPhase
    busy_since_ms: int | None       # 바쁜 구간 시작(MN2). 비바쁜 국면이 확정되면 None
    pending: PendingNotice | None = None

class NotifyEvent:                  # 확정된 알림 1건(세션 1개)
    kind: NotifyKind
    project_name: str
    task_title: str | None
    busy_duration_ms: int
    resets_at_ms: int | None
    background_task_count: int

class NotificationText:             # osascript 로 넘길 세 문자열(정제 끝난 값)
    title: str
    subtitle: str
    message: str

class NotifyStatusRecord:           # notify_status.json(MN11)
    active_since_ms: int | None
    last_attempt_at_ms: int | None
    last_success_at_ms: int | None
    last_failure_reason: NotifyFailureReason | None
    last_failure_exit_code: int | None
```

`SessionView`(hub_session.py) 추가 필드: `is_awaiting_approval: bool = False` — `background_wait` 다음, `session_cost` 앞. 주석에 「알림과 화면
표지의 단일 판정(MN5). 맨 뒤가 아니다 — 맨 뒤는 T25-150 이 무는 session_cost」.

`HubConfig`(hub_model.py) 추가 필드: `notify_enabled: bool = False` — 맨 뒤, 주석 「macOS 알림 스위치, 기본 off(MN10). 서버 기동 때 읽는다」.

## 8. 인터페이스 (공개 시그니처)

### hub_session.py (★순수)
```python
def is_awaiting_approval(state: SessionState, base_state: Literal["working", "idle", "done"], tier1: Tier1Snapshot | None) -> bool:
    """승인 대기 표지·알림의 단일 판정(MN5 — AW1 규칙): 승인 단계 진행중 ∧ base idle ∧ 한도 초과 아님."""
```

### hub_notify.py (★순수)
```python
NOTIFY_MIN_BUSY_EPISODE_MS = 2 * 60 * 1000
NOTIFY_SETTLE_MS = 3_000
NOTIFY_KIND_BY_PHASE: Mapping[NotifyPhase, NotifyKind]          # waiting→turn_ended 등 4행(MN1 표)
NOTIFY_KIND_ORDER: tuple[NotifyKind, ...]                       # interrupted, awaiting_approval, turn_ended, background_wait
NOTIFY_TITLE_LABEL_BY_KIND: Mapping[NotifyKind, str]            # "■ 한도 초과" … (화면 어휘와 같은 글자)
NOTIFY_TITLE_MAX_CHARS = 60; NOTIFY_SUBTITLE_MAX_CHARS = 60; NOTIFY_MESSAGE_MAX_CHARS = 120
NOTIFY_TASK_TITLE_MAX_CHARS = 40; NOTIFY_LISTED_PROJECT_MAX = 3
OSASCRIPT_PATH = "/usr/bin/osascript"
NOTIFY_APPLESCRIPT_LINES = ("on run argv",
    "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of argv)", "end run")

def notify_phase(session: SessionView) -> NotifyPhase:
    """세션 표시 상태를 알림 국면 6값으로 접는다(MN1 표, 위에서부터 먼저 맞는 것)."""
def observe_sessions(snapshot: HubSnapshot) -> tuple[SessionObservation, ...]:
    """스냅샷의 모든 프로젝트·세션을 관측값으로 펼친다."""
def advance_session_track(previous: SessionTrack | None, observation: SessionObservation, now_ms: int) -> tuple[SessionTrack, NotifyEvent | None]:
    """세션 1개의 추적을 한 수집만큼 전진시키고, 확정된 알림이 있으면 함께 돌려준다(MN1~MN3·MN7)."""
def advance_tracks(previous: Mapping[str, SessionTrack] | None, observations: Sequence[SessionObservation], now_ms: int) -> tuple[Mapping[str, SessionTrack], tuple[NotifyEvent, ...]]:
    """previous 가 None(서버 첫 수집)이면 기준선만 잡고 알림 0건. 사라진 세션은 결과에서 빠진다."""
def has_pending(tracks: Mapping[str, SessionTrack]) -> bool:
    """확인 대기 후보가 하나라도 있으면 True — 티커의 확인 수집 게이트(MN3·MN6)."""
def compose_notifications(events: Sequence[NotifyEvent], include_task_title: bool, clock_label: Callable[[int], str]) -> tuple[NotificationText, ...]:
    """종류별로 묶어 NOTIFY_KIND_ORDER 순서의 알림 문구를 만든다(MN9 표). clock_label 은 I/O 층이 주입한다."""
def duration_label(duration_ms: int) -> str:
    """'23분' / '1시간 5분'."""
def sanitize_notification_text(text: str, max_chars: int) -> str:
    """제어문자·NUL → 공백, 공백 접기, 앞뒤 공백 제거, 상한 초과 시 '…'(MN8)."""
def osascript_argv(text: NotificationText) -> tuple[str, ...]:
    """고정 스크립트 + '--' + (message, title, subtitle). 사용자 문자열은 '--' 뒤에만 온다(MN8)."""
def next_notify_status_record(previous: NotifyStatusRecord | None, now_ms: int, failure_reason: NotifyFailureReason | None, exit_code: int | None) -> NotifyStatusRecord:
    """배치 1회의 결과로 새 기록을 돌려준다. 배치에 실패가 있으면 마지막 실패의 사유·코드를 남기고 last_success_at_ms 는
    보존, 모두 성공이면 실패 필드를 지운다(hub_release.next_release_check_record 와 같은 의미). active_since_ms 는 보존."""
def is_notifier_active(record: NotifyStatusRecord | None, server_started_at_ms: int | None) -> bool:
    """지금 도는 서버가 알림기를 켜고 시작했는가(active_since_ms ≥ 서버 기동 시각)."""
```

`advance_session_track` 의 판정 순서(구현 계약 — 50줄 상한을 위해 `_confirm_pending`·`_start_pending`·`_next_busy_since` 로 나눈다):

1. `previous is None` → `SessionTrack(phase, now if phase in BUSY else None)`, 알림 없음.
2. `previous.pending` 이 있고 `phase == previous.phase`:
   - `now - pending.observed_at_ms < NOTIFY_SETTLE_MS` → `previous` 그대로, 알림 없음.
   - 아니면 확정: `kind == "interrupted" or busy_duration_ms ≥ NOTIFY_MIN_BUSY_EPISODE_MS` 이면 `NotifyEvent`(관측값의 이름·제목·시각·수로 채움).
     새 추적은 `pending=None`, `busy_since_ms` 는 `phase ∈ BUSY` 면 유지·아니면 None.
3. `previous.pending` 이 있고 국면이 바뀌었으면: 새 국면이 `NOTIFY_KIND_BY_PHASE` 에 있으면 보존한 `busy_since_ms` 로 새 국면의 후보를 다시 시작하고(4 와 같은 처리 — 후보는 working 에서만 생기므로 「후보가 있다」는 「작업중에서 막 나왔다」와 같다), 새 국면이 working 이면 후보를 버린다(바쁜 구간 시작은 유지). (검수 1회차 C1 로 개정, 사용자 승인)
4. `previous.phase == "working"` 이고 `phase ∈ NOTIFY_KIND_BY_PHASE` → `pending = PendingNotice(kind, now, now - previous.busy_since_ms)`,
   `busy_since_ms` 유지, 알림 없음.
5. 그 밖: `busy_since_ms = (previous.busy_since_ms or now) if phase in BUSY else None`, 알림 없음.

`BUSY = frozenset({"working", "background"})`. `previous.phase == "working"` 이면 `busy_since_ms` 는 항상 채워져 있다(1·5 가 보장).

### hub_notify_send.py (I/O)
```python
NOTIFY_STATUS_PATH = Path.home() / ".claude" / "hub" / "notify_status.json"
NOTIFY_SEND_TIMEOUT_SECONDS = 10
NO_ERROR_NUMBER_LOG = "AppleScript 오류 번호 없음"
_APPLESCRIPT_ERROR_NUMBER = re.compile(r"\((-\d{1,6})\)")
ACTIVITY_FILE_SUFFIXES = (".jsonl", ".json")

def is_notify_supported() -> bool:
    """macOS 이고 /usr/bin/osascript 가 실재하는가."""
def send_notification(text: hub_notify.NotificationText) -> tuple[hub_notify.NotifyFailureReason | None, int | None]:
    """osascript 1회. 성공이면 (None, 0). 실패 사유·종료 코드를 돌려주고 AppleScript 오류 번호만 server.log(stderr)에 남긴다."""
def deliver_notifications(texts: Sequence[hub_notify.NotificationText], now_ms: int) -> None:
    """배치를 차례로 보내고 notify_status.json 을 1회 갱신한다. 예외를 올리지 않는다(최후선은 stderr)."""
def dispatch_in_background(texts: Sequence[hub_notify.NotificationText], now_ms: int) -> None:
    """deliver_notifications 를 데몬 스레드 1개로 띄운다(MN8 — 수집 락·하트비트 비차단)."""
def read_notify_status() -> hub_notify.NotifyStatusRecord | None:
    """없거나 깨졌으면 None."""
def write_notify_status(record: hub_notify.NotifyStatusRecord) -> None:
    """원자적 쓰기. OSError 는 호출측이 받는다."""
def read_activity_signature(directories: Sequence[Path]) -> frozenset[tuple[str, str, int, int]]:
    """(디렉터리 이름, 파일 이름, 크기, mtime_ns) 집합. 디렉터리 부재·읽기 실패는 그 디렉터리만 빈 것으로 본다."""
def local_clock_label(epoch_ms: int, now_ms: int) -> str:
    """'HH:MM'(오늘) / 'M/D HH:MM'(다른 날) — 로컬 시간대."""

class SessionNotifier:
    """수집 결과를 받아 전이를 판정하고 확정된 알림을 내보낸다. 왜 클래스인가: 수집과 수집 사이에 살아야 하는
    직전 관측(추적 매핑)이 있고 전역 가변 상태는 금지다 — _SnapshotRefresher 와 같은 이유·같은 자리(서버 인스턴스)."""
    def __init__(self, include_task_title: bool,
                 dispatch: Callable[[Sequence[hub_notify.NotificationText], int], None] = dispatch_in_background) -> None: ...
    def observe(self, snapshot: HubSnapshot) -> None:
        """_SnapshotRefresher 락 안에서만 부른다. 첫 호출은 기준선."""
    def has_pending(self) -> bool:
        """티커가 확인 수집을 부를지 정한다."""
```

### hub_server.py (수정)
```python
ACTIVITY_COLLECT_MAX_AGE_MS = 0      # 변화가 보이면 창과 무관하게 수집(MN6)

def _run_collect_cycle(last_content_key: str | None, notifier: hub_notify_send.SessionNotifier | None = None) -> tuple[str | None, dict[str, str] | None]:
    # 반환 모양 불변. 성공 경로 끝에서 _observe_for_notification(notifier, snapshot) — 자체 try/except 로
    # 알림 쪽 예외가 수집 실패(record_collect_failure)로 잘못 기록되지 않게 한다.
def _observe_for_notification(notifier: hub_notify_send.SessionNotifier | None, snapshot: hub_model.HubSnapshot) -> None:
    """None 이면 아무것도 안 한다. 예외는 stderr 한 줄로 흡수(수집 사이클을 깨지 않는다)."""
class _SnapshotRefresher:
    def __init__(self, httpd, notifier: hub_notify_send.SessionNotifier | None = None) -> None: ...
def _collect_for_notification(refresher, notifier, activity_directories: Sequence[Path], last_signature: frozenset | None) -> frozenset | None:
    """서명 읽기(먼저) → 바뀌었으면 강제 수집 → 후보가 있으면 확인 수집. 다음 틱에 쓸 서명을 돌려준다."""
def _maintenance_loop(config, stop_event, refresher, notifier=None, activity_directories: Sequence[Path] = ()) -> None:
    # 하트비트 → _collect_for_notification(notifier 가 있을 때만) → 배경 상한 수집 → 하트비트. 기존 최후선 그대로.
def _start_notifier(config: hub_model.HubConfig, now_ms: int) -> hub_notify_send.SessionNotifier | None:
    """notify_enabled ∧ is_notify_supported() 일 때만 만들고 active_since_ms 를 기록한다. 아니면 None(+필요 시 server.log 한 줄)."""
```
`run_server` 는 `_start_notifier` 결과를 `_SnapshotRefresher` 와 `_start_background_threads(config, stop_event, refresher, notifier)` 에 넘기고, 이 함수가 유지보수 티커·사용량 폴링·릴리스 확인 스레드를 띄우며 `_maintenance_loop` 에 알림기와 디렉터리(`(hub_collect.EVENTS_DIR, hub_collect.SESSIONS_DIR)`)를 넘긴다(검수 1회차 D4 — `run_server` 50줄 규칙).

### hub.py (수정)
`cmd_status` 의 보고 dict 에 `"notify_enabled": config.notify_enabled`, `"notify_active": hub_notify.is_notifier_active(record, server_started_at_ms)`,
`"notify_status": asdict(record) or None`. `server_started_at_ms` 는 `server.record.started_at_ms`(서버가 죽었으면 None → False).

### hub_template.html (수정)
```js
  function isAwaitingApproval(session){
    return session.is_awaiting_approval === true;
  }
```
위 주석: 「판정은 서버(hub_session.is_awaiting_approval)가 한 곳에서 한다 — macOS 알림과 같은 규칙(MN5). 키가 없는 옛 페이로드는 false」.

---

## 9. 테스트 계획

### 9.1 `tests/hub/test_hub_notify.py` (순수 — 이 기능의 핵심)

| 케이스 | 입력 | 기대 |
|---|---|---|
| 국면 표 | done·interrupted·승인(idle)·승인(background)·background·stale(base working)·stale(base idle)·idle·working | MN1 표 그대로(승인+background → awaiting_approval, stale+working → working) |
| 첫 수집은 기준선 | previous=None, 대기 세션·한도 초과 세션 | 알림 0, 추적만 생김 |
| 처음 보는 세션 | previous 에 없는 세션이 승인 대기로 등장 | 알림 0 |
| 작업중→대기 확정 | t0 working, t0+5분 waiting, t0+5분+3초 waiting | 둘째 수집 0건(후보), 셋째 `turn_ended` 1건, busy 5분 |
| 확인 전 복귀(틈) | working → waiting → (2초 뒤) … / (5초 뒤) working | 알림 0, busy_since 유지 |
| 확인 지연 경계 | 후보 후 2,999ms / 3,000ms | 미확정 / 확정 |
| 2분 미만 | busy 1분 59초 → 대기 확정 | 알림 0, busy_since None |
| 2분 경계 | busy 정확히 2분 | 알림 1 |
| 한도 초과는 짧아도 | busy 30초 → interrupted 확정 | `interrupted` 1 |
| 승인 대기 우선 | working → awaiting_approval | `awaiting_approval` 1, `turn_ended` 0 |
| 승인 재진입 | 승인 확정 → working(4분) → awaiting_approval | 두 번째도 1(바쁜 구간 4분) |
| 백그라운드 이어짐 | working 10분 → background(확정, 알림 1) → working 1분 → waiting | 마지막 `turn_ended` 의 busy ≈ 11분 이상(끊기지 않음) |
| 백그라운드 상한 만료 | background → waiting | 알림 0 |
| 작업중→완료 | working → done | 알림 0 |
| 반복 수집 중복 없음 | 확정 뒤 같은 국면으로 3회 더 | 추가 알림 0 |
| 사라진 세션 | 다음 관측에 없음 | 추적에서 빠짐 |
| `has_pending` | 후보 유무 | True/False |
| 묶음 | 같은 수집 `interrupted` 3건(프로젝트 a,a,b) + `turn_ended` 1 | 알림 2개, 순서 한도→대기, 한도 제목 `세션 3개`, 본문 `a · b` |
| 나열 상한 | 프로젝트 5개 | `p1 · p2 · p3 외 2` |
| 작업 제목 끔 | include_task_title=False | 부제 빈 값 |
| 작업 제목 마스킹·상한 | 제목에 `sk-ant-…` 토큰·60자 | `[REDACTED]` 포함·40자+`…` |
| 초기화 시각 없음 | resets_at None | `사용량 한도로 멈췄습니다` 만 |
| 정제 | 줄바꿈·탭·NUL·DEL·연속 공백·앞뒤 공백·상한 초과 | 공백 1개·NUL 없음·`…` |
| **argv 안전** | 제목 `-e`, 본문 `" & (do shell script "x") & "` | argv[:8] == 고정 접두(경로 + `-e` 3쌍 + `--`), 사용자 문자열은 그 뒤에 원문 그대로, 스크립트 줄에 사용자 문자열 없음 |
| 길이 표기 | 2분·59분·60분·65분 | `2분`·`59분`·`1시간`·`1시간 5분` |
| 상태 기록 | 성공/실패/성공 후 실패 | 시각·사유·코드 갱신 규칙 |
| `is_notifier_active` | 기록 없음 / active_since < 기동 / ≥ 기동 / 서버 없음 | F / F / T / F |

### 9.2 `tests/hub/test_hub_notify_send.py` (I/O — `subprocess.run`·경로 상수를 `mock.patch.object`)

- `send_notification`: 인자가 `hub_notify.osascript_argv(text)` 그대로·`shell` 인자 없음·`stdin=DEVNULL`·`timeout=10` / 종료 코드 1 → `exit_nonzero` + stderr 한 줄이
  stderr 로 / `TimeoutExpired` → `timeout` / `FileNotFoundError` → `osascript_missing` / `ValueError`(고립 서로게이트·NUL) → `invalid_text`.
- `deliver_notifications`: 2건 중 1건 실패 → 기록 1회 쓰기·실패 사유 남음 / 기록 쓰기 `OSError` → 예외 없이 stderr 한 줄.
- `read_activity_signature`(임시 디렉터리): append → 서명 바뀜 / `*.key` 추가 → 안 바뀜 / 디렉터리 부재 → 빈 집합·예외 없음.
- `SessionNotifier`(가짜 `dispatch`): 첫 `observe` 0회 호출 / 전이·확인 뒤 1회 / 같은 스냅샷 반복 0회 / 확정 0건이면 `dispatch` 를 부르지 않음 /
  `include_task_title=False` 전파.
- `local_clock_label`: 오늘·다른 날(시간대 고정 — `time.localtime` 패치 또는 TZ 고정).

### 9.3 `tests/hub/test_hub_session.py`

- `is_awaiting_approval` 표 — AW1 표의 행 전부(idle·background·stale(idle)·stale(working)·working·interrupted·done·사실 꺼짐·tier1 없음). 이 표가 그동안
  DOM D43 이 지던 규칙의 정본 검사가 된다.
- `compute_session_view` 가 그 값을 싣는다(승인 active + Stop 뒤 idle → True, interrupted → False).
- `dataclasses.fields(SessionView)[-1].name == "session_cost"` 유지(T25-150 과 같은 단언 — 새 필드가 맨 뒤로 가지 않았다).

### 9.4 `tests/hub/test_hub_server.py`

- `_run_collect_cycle(None, notifier=가짜)`: 성공 → `observe` 1회(그 스냅샷) / 수집 예외 → `observe` 0회 / `observe` 예외 → 반환값 정상·
  `last_collect_error.json` 없음.
- `_maintenance_loop`(가짜 refresher, 서명 함수 패치, 한 틱 뒤 `stop_event.set`): 서명 변화 → `collect_if_older_than(_, 0)` / 불변 → 그 호출 없음 /
  첫 틱 → 없음 / `has_pending` True → `collect_if_older_than(_, NOTIFY_SETTLE_MS)` / `notifier=None` → 서명 함수를 부르지 않음(오늘 동작 무변경).
- `_start_notifier`: 꺼짐 → None·기록 안 씀 / 켜짐+미지원 → None + stderr / 켜짐+지원 → 인스턴스 + `active_since_ms` 기록.
- 기존 `_run_collect_cycle(None)`·`_SnapshotRefresher(_DummyHttpd())`·`_maintenance_loop(config, stop_event, refresher)` 호출은 무수정 통과해야 한다.

### 9.5 DOM·설정·정적 가드

- `test_hub_template_dom_approval.py`: 픽스처 세션에 `is_awaiting_approval=hub_session.is_awaiting_approval(state, base_state, tier1)` 를 채워 D43~D45 를
  그대로 통과시킨다(표지 위치·기하·툴팁 무변경 확인). 옛 페이로드 흉내는 `is_awaiting_approval` 키를 지운다 → 표지 없음.
  **RED 확인**: 변경 전 템플릿(`DZH_DOM_TEST_TEMPLATE`)으로 돌리면 「키는 true 인데 tier1 사실이 없는」 신설 케이스 1건이 실패해야 한다(화면이 서버 판정을
  읽는다는 증명).
- `test_hub_config.py`: `notify_enabled` 기본 False · `true` 수용 · 문자열이면 기본값 + 경고.
- `tests/run.sh`(번호는 병합 직전 재계수):
  - T25-10 순수 목록에 `hub_notify.py`.
  - T25-104·T25-149: `37개 파일`·`HUB_FILE_COUNT=37`, 역방향에 `35개 파일`.
  - T25-280 ① 에 `hub_session.py` 의 `is_awaiting_approval: bool = False` 선언 추가, ② 를 `session.is_awaiting_approval` 읽기로 재조준(필드 개명에 눈멀지 않게).
  - **T25-285(보안, MN8)**: `hub_notify.py` 의 `NOTIFY_APPLESCRIPT_LINES` 블록에 `on run argv` 가 있고 `{`·`%`·`format(` 이 없다 · `osascript_argv` 본문에
    `"--"` 가 있다 · `hub_notify_send.py` 에 `shell=` 가 없고 `subprocess.run(` 의 첫 인자가 `hub_notify.osascript_argv(` 다. 변조행: `"--"` 를 지운다.
  - **T25-286(경계, MN6·MN7)**: `hub_notify_send.py` 가 `hub_collect`·`hub_server` 를 임포트하지 않는다 · `hub_server.py` 의 활동 디렉터리 튜플이
    `hub_collect.EVENTS_DIR, hub_collect.SESSIONS_DIR` 이고 `HUB_HOME` 이 아니다(자기 유발 루프 방지). 변조행: 디렉터리를 `hub_collect.HUB_HOME` 으로.
  - **T25-287(문서·어휘, MN9·MN11·MN13)**: `hub/README.md` 에 `notify_enabled`·`notify_status.json`·`스크립트 편집기`·`알림 센터` · `commands/hub.md` 에
    `notify_status` · `NOTIFY_TITLE_LABEL_BY_KIND` 의 라벨 4개(`한도 초과`·`승인 대기`·`대기`·`백그라운드 대기`)가 템플릿에도 있다. 변조행: README 의
    `notify_status.json` 을 지운다.
  - `tests/mutations.tsv` 변조행 3건, `SOURCE_GUARD_ID_FLOOR`·`LEDGER_MUTATION_ROW_FLOOR` 를 그만큼 올리고 그 근거 주석 1줄(기존 관례).

### Edge Cases Checklist

- [x] 빈 스냅샷(세션 0) → 알림 0, 추적 비움
- [x] 긴 이름·제어문자·NUL·`-` 로 시작하는 이름 → 정제·`--`
- [x] 동시 접근 → `observe` 는 refresher 락 안에서만, `has_pending` 은 불변 참조 읽기
- [x] 전송 실패(부재·시간 초과·비 0) → 기록·로그, 수집·티커 영향 없음
- [x] 권한 거부(조용한 성공) → 관측 불가 — 한계로 문서화
- [x] 서버 재기동 → 기준선

---

## 10. Mandatory Reading

| 우선 | 파일 | 행 | 이유 |
|---|---|---|---|
| P0 | `hub/bin/hub_server.py` | 225-352, 419-452, 522-577 | 수집 사이클·refresher 락·티커·기동 — 배선 지점 |
| P0 | `hub/bin/hub_session.py` | 109-196, 365-395, 481-599 | SessionView 필드 순서 규칙·표시 사다리·compute_session_view |
| P0 | `hub/bin/hub_template.html` | 160-172, 1801-1816 | 데이터 계약 주석·isAwaitingApproval |
| P0 | `docs/prps/hub-approval-wait-badge.md` | 48-100, 360-385 | AW1 표·AW2·P2 기각 사유(MN5 가 부분 번복) |
| P1 | `hub/bin/hub_release_read.py` | 105-190 | 기록 읽기/쓰기·argv 리스트 subprocess·사유 문자열 관례 |
| P1 | `hub/bin/hub_parse.py` | 60-71, 232-295 | `is_approval_step_active` 사실 |
| P1 | `hub/bin/hub_config.py` · `hub/bin/hub_model.py` | 25-39 · 24-41 | 설정 키 추가 관례 |
| P1 | `hub/bin/hub.py` | 243-290 | `/hub status` 필드 관례 |
| P1 | `tests/run.sh` | 4316-4337, 6229-6275, 7313-7330, 10459-10600 | T25-10·104·149·275·279·280·281 |
| P2 | `tests/hub/test_hub_server.py` | 40-200, 366-520, 555-680 | 더미 httpd·티커 테스트 패턴 |
| P2 | `tests/hub/test_hub_template_dom_approval.py` · `template_dom_harness.py` | 전체 · 291-311 | DOM 픽스처 |

## 11. Patterns to Mirror

- **순수/I-O 쌍**: `hub_release.py`(순수, `next_release_check_record`) ↔ `hub_release_read.py`(I/O, `RELEASE_CHECK_PATH = Path.home() / …`,
  `write_release_check_record` 가 `hub_atomic_write.atomic_write_text(path, path.parent, "release_check.json.", json.dumps(asdict(record), ensure_ascii=False))`).
- **subprocess**: `hub_release_read._run_git_ls_remote` — 리스트 argv · `stdin=subprocess.DEVNULL` · 시간 초과 상수 · 실패를 짧은 사유 문자열로.
- **최후선 로깅**: `print(f"…: {error}", file=sys.stderr)` — 서버의 stderr 는 `server.log` 로 리다이렉션된다(`hub_server.py:327`, `:451`).
- **상태를 가진 클래스의 근거 주석**: `_SnapshotRefresher` docstring(「왜 클래스인가 … 결정 A3 전역 가변 상태 금지」).
- **설정 키**: `update_check_enabled` — `HubConfig` 맨 뒤 + `_CONFIG_FIELD_TYPES` + 테스트 3종(`test_hub_release_wiring.py:37-46`).
- **SessionView 부가 필드**: 기본값 + 주석에 「맨 뒤가 아니다 — 맨 뒤는 session_cost(T25-150)」.
- **테스트 시계**: `now_ms` 를 인자로(★순수 모듈 관례) — 순수 테스트는 시계를 패치하지 않는다.

## 12. Step-by-Step Tasks (구현 단계 — TDD)

| # | 작업 | 검증 |
|---|---|---|
| M1 | `hub_session.is_awaiting_approval` + `SessionView` 필드 + `compute_session_view` 배선 / `hub_template.html` `isAwaitingApproval` 1줄·주석 / DOM 픽스처 / T25-280 ①② 재조준 | `test_hub_session`·`test_hub_template_dom_approval`(단독 실행 — 메모리 「DOM 테스트는 동시 부하에 약하다」) |
| M2 | `hub_notify.py` 데이터 모델·국면·전이·확인 지연·문구·argv·기록 | `test_hub_notify` 전부(§9.1) |
| M3 | `hub_notify_send.py` 전송·기록·서명·`SessionNotifier` | `test_hub_notify_send` |
| M4 | `HubConfig.notify_enabled`·`hub_config` / `hub_server` 배선 / `hub.py` 상태 3필드 | `test_hub_config`·`test_hub_server`, 기존 서버 테스트 무수정 통과 |
| M5 | 문서(MN13) · `HUB_FILE_COUNT=37` · run.sh 가드·원장 · 번호·하한 재계수(develop 재수신 후) | `bash tests/run.sh`(메인 세션이 커밋 직전 1회) |
| M6 | **실기 확인(구현 단계, 사람 눈)**: 이 PC 에서 `notify_enabled:true` → `hub/install.sh --force` → `/hub server restart` → 2분 넘는 턴을 끝내 배너 확인, 첫 권한 질문·출처 표기(스크립트 편집기)·클릭 동작·잠금 화면 미리보기를 기록해 README 한계 문구를 확정. **실측(2026-10-15)**: 설치·서버 재기동 대신 워크트리 코드의 `send_notification` 으로 시험 알림 2건(승인 대기 · 빈 부제의 대기)을 보냄 → 둘 다 표시, 권한 질문 없음, 빈 부제 정상, 클릭 시 스크립트 편집기의 파일 열기 창이 뜸, 출처 표기는 사용자가 확인하지 못함. 실제 서버 경로(전이 감지 → 전송)는 설치 뒤 확인 | 관측 결과를 PR 설명에 남긴다 |

GOTCHA:
- `~/.claude/hub/` 를 감시 디렉터리에 넣지 않는다(자기 유발 수집 루프).
- 서명은 수집 **전에** 읽는다.
- 알림기 예외가 `_run_collect_cycle` 의 `except Exception` 에 잡히면 수집 실패로 기록된다 — 별도 try 로 감싼다.
- `SessionView` 새 필드를 맨 뒤에 두면 T25-150 이 깨진다.
- `isAwaitingApproval`·`renderApprovalWaitBadge` 의 함수 머리 줄(`  function isAwaitingApproval(session){`)과 닫는 `  }` 를 그대로 둔다 — T25-280 이 그 줄로 본문을 sed 추출한다.
- ★순수 `hub_notify.py` 는 주석에도 `open(`·`Path(`·`os.` 를 쓰지 않는다(T25-10 이 문다). 시간대 처리(`time.localtime`)는 `hub_notify_send.py` 에.
- `python3 -m py_compile` 뒤 `__pycache__` 를 지운다(메모리 — commands 파일 수 거짓 실패).
- 실 `$HOME` 대상 설치·서버 재기동은 사용자가 요청할 때만(프로젝트 CLAUDE.md §1(b)) — M6 은 사용자 확인 뒤.

## 13. Validation Commands

```bash
python3 -m py_compile hub/bin/*.py            # 뒤에 find hub/bin -name __pycache__ -prune -exec rm -rf {} + (절대경로 /usr/bin/find)
python3 -m unittest discover -s tests/hub -t .
bash -n install.sh && bash -n hub/install.sh
bash tests/run.sh                              # 메인 세션이 커밋 직전 1회(수십 분 — 백그라운드 + 완료 알림)
```
EXPECT: 전부 통과. 구현자는 변경이 닿은 테스트 모듈만 돌린다(DOM 모듈은 단독).

## 14. Acceptance Criteria

- [ ] 서버 기동 첫 수집·처음 보는 세션에서 알림 0
- [ ] 2분 넘는 턴이 끝나면 5~10초 안에 배너 1개(탭이 닫혀 있어도)
- [ ] 같은 전이로 두 번 울리지 않음(반복 수집·재기동)
- [ ] 승인 대기 진입은 「대기」가 아니라 「◆ 승인 대기」 하나
- [ ] 허브 탭 화면 무변화(D43~D45 통과), 판정은 Python 한 곳
- [ ] 사용자 문자열이 AppleScript 소스에 들어가지 않음(T25-285, argv 단위 테스트)
- [ ] `notify_enabled:false`(기본)면 서버 동작이 오늘과 같음(감시·스레드·파일 쓰기 없음)
- [ ] `/hub status` 로 켜짐·실제 동작·마지막 실패를 구분 가능
- [ ] 정본 검증 명령 4종 통과

---

## 15. 리스크와 대안

### 리스크

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| macOS 가 `osascript` 알림을 조용히 막음(권한·집중 모드·「스크립트 편집기」 알림 꺼짐) | 중 | 알림이 안 오는데 성공으로 기록 | README 확인 방법·한계 명시, M6 실기 확인 |
| 출처가 「스크립트 편집기」, 클릭 시 그 앱이 열림 | 높음 | 혼란 | 한계로 문서화 — 새 의존성 금지라 대안 없음(대안 B 참조) |
| 서브에이전트 완료→깨우기 틈 오탐 | 낮음(MN3 후) | 가짜 「대기」 | 확인 지연 3초 + 다음 수집 확인 |
| 백그라운드 대기 진입 알림이 자기 검사를 기다리는 세션에서 소음 | 중 | 작업 1회에 2번 울림 | 문구가 「백그라운드 작업을 기다립니다」라고 말함, 사용자 확인 항목 |
| 좀비 서브에이전트(90분 가드)가 작업중을 붙잡았다 풀리면 늦은 「대기」 | 낮음 | 90분 늦은 알림 | 한계 문서화(SubagentStop 미발화는 허브 밖 원인) |
| 프로세스가 죽은 세션(명부 이탈)도 작업중→대기로 보여 「대기」가 울림 | 낮음 | 오해 소지 | 한계 문서화 — 사용자가 봐야 할 세션이라는 점은 같다 |
| 재기동 직후 2분 안에 끝난 턴은 바쁜 구간이 짧게 잡혀 안 울림 | 낮음 | 알림 누락 | 한계 문서화(기동 시각부터 잼) |
| 즉시 수집 빈도 증가 | 낮음 | CPU | 훅은 턴·서브에이전트 경계에만 발화, 틱당 최대 1회, 꺼져 있으면 0 |
| 동시 세션의 README·run.sh·원장 충돌 | 높음 | 병합 충돌·번호 겹침 | 절 단위 삽입, 번호·하한은 병합 직전 재계수 |
| 2분·3초 상수가 실사용에 안 맞음 | 중 | 소음 또는 누락 | 이름 있는 상수 한 줄 — 사용 후 조정 |

### 검토했으나 채택하지 않은 대안

- **대안 A — 서버에 승인 대기 규칙을 한 벌 더 두고 run.sh 교차 가드로 묶기**: 템플릿 무변경이라 동시 작업과 안 겹친다. 기각 — 지시문이 두 벌을
  금했고, 규칙이 바뀌면 두 곳을 같이 고쳐야 하며 교차 가드는 글자 일치만 볼 뿐 의미 일치를 보지 못한다(AW2 가 피하려던 `SESSION_STATE_ORDER`·
  T25-219 식 비용).
- **대안 B — `terminal-notifier`·Swift 헬퍼로 출처·클릭 동작 해결**: 출처가 「허브」로 보이고 누르면 허브 URL 을 열 수 있다. 기각 — 새 의존성 금지
  (프로젝트 CLAUDE.md §2), 서명·배포 부담.
- **대안 C — 디스크에 추적 상태를 두고 훅 폴백 수집도 알림**: 서버가 꺼져도 울린다. 기각 — 폴백 수집끼리·서버와의 경합 잠금이 필요하고, 지시문이
  서버 한정을 허용했다.
- **대안 D — 턴 길이 대신 「사용자가 허브를 안 보고 있을 때만」**: 탭 포커스 정보를 서버로 보내야 한다 = 쓰기 경로. 기각(읽기 전용 원칙).
- **대안 E — `select.kqueue` 로 이벤트 파일 감시**: 지연이 0 에 가깝다. 기각 — 틱 폴링으로 5초 안이면 충분하고, fd 수명·날짜별 새 파일·macOS 전용
  분기 비용이 이득보다 크다(YAGNI).

## 16. 미결 쟁점 (사용자 확인)

1. **기본값**: `notify_enabled` 기본 **꺼짐**(옵트인) — 이 PC 는 `config.json` 한 줄 + 서버 재기동으로 켠다. 기본 켜짐을 원하면 근거 ①~③(MN10)을 감수.
   - **확정(2026-10-15, 사용자 승인)**: 설계안 그대로 — 기본 꺼짐(옵트인).
2. **백그라운드 대기 진입 알림**(MN4): 넣으면 자기 검사를 기다리는 세션에서 한 번 더 울리고, 빼면 남은 `tail -f` 때문에 끝난 세션이 영영 안 울린다. 설계는 「넣는다」.
   - **확정(2026-10-15, 사용자 승인)**: 설계안 그대로 — 백그라운드 대기 진입도 알린다.
   - **번복(2026-10-15, 사용자 결정 「역할 나누기」)**: 백그라운드 대기·대기 알림을 걷는다 — [hub-notify-answer-wait.md](hub-notify-answer-wait.md) AN1.
3. **작업 제목을 알림에 실을지**(MN9): 실으면 어느 일인지 바로 알지만 잠금 화면·알림 센터에 남는다. 설계는 「`record_prompt_excerpt` 가 켜져 있으면 싣는다」.
   - **확정(2026-10-15, 사용자 승인)**: 설계안 그대로 — `record_prompt_excerpt` 가 켜져 있을 때만 작업 제목을 싣는다.
4. (조정 가능) 소음 기준 2분 · 확인 지연 3초.
   - **확정(2026-10-15, 사용자 승인)**: 설계값 그대로 — 2분(MN2)·3초(MN3).

## Notes

- 외부 조사: 웹 조사 없음 — `osascript` 인자 처리는 설계 중 알림을 띄우지 않는 스크립트로 직접 확인했다(§2). `display notification` 의 출처 표기·
  클릭·권한 거동은 macOS 버전마다 달라 구현 단계 M6 에서 실기로 확인한다.
- AW2(hub-approval-wait-badge.md)의 「판정 위치」를 MN5 가 부분 번복한다 — 구현 시 그 문서에 번복 사실을 한 줄 덧붙인다(「MN5 로 판정이 서버로
  옮겨졌다」).
