# Plan: 허브 macOS 알림을 「승인 대기·한도 초과」 둘로 줄인다 — 질문·허락·작업 완료는 데스크톱 앱에 맡긴다

> 설계 문서(PRP). 결정 ID 접두는 **AN**. 구현 전 사용자 승인 필요.
> 설계 모델: opus(승격 기준 미해당 — 모듈 하나 안의 축소 변경).
> 작업 위치: 워크트리 `.claude/worktrees/hub-notify-answer-wait`(브랜치 `feat/hub-notify-answer-wait`, `origin/develop` `cdeb6fd` 기준).
> **개정(2026-10-15, 사용자 결정 「역할 나누기」)**: 1차 초안은 허브가 질문(`AskUserQuestion`)·도구 허락 요청도 알리도록 훅 3개를 더하는
> 안이었다. 데스크톱 앱이 같은 것을 이미 배너로 알린다는 사실이 확인돼(§2) 그 부분을 걷었다 — 기각 사유는 §9, 그때 조사한 내용은
> 부록 A(터미널 세션 지원을 다시 꺼낼 때 쓴다). 파일 이름은 1차 초안 그대로다.
> 앞선 설계: `docs/prps/hub-macos-notification.md`(MN1~MN13) — 이 문서가 MN1·MN3·MN4·MN9·MN12 를 부분 개정한다.
> `docs/prps/hub-approval-wait-badge.md`(AW)·`docs/prps/hub-dashboard.md` 는 바뀌지 않는다.
> 목업 없음 — 남는 배너 두 종류의 문구·모양은 오늘과 같고 허브 화면도 바뀌지 않는다.

## Summary

허브 macOS 알림을 **■ 한도 초과**와 **◆ 승인 대기** 두 종류로 줄인다. `○ 대기`(턴 끝)·`◐ 백그라운드 대기` 알림은 끄고 그 코드·문구·
테스트를 지운다 — 10-15 하루 약 59건이 전부 이 둘이었고, 모니터를 건 세션에서 같은 문구가 되풀이된 원인도 이 둘이다. 선택지 질문·
도구 허락 요청·작업 완료는 Claude 데스크톱 앱이 자체 배너로 알린다(앱 설정 3종 기본 「Banners」) — 허브는 그 역할을 맡지 않고 앱
설정도 건드리지 않는다. 바뀌는 코드는 ★순수 모듈 `hub_notify.py` 하나이고, 훅·수집·서버·화면은 그대로다.

## User Story

여러 세션을 띄워 두고 다른 창에서 일하는 사용자로서, 허브 알림은 **데스크톱 앱이 알려 주지 않는 것 — 설계 승인 대기와 한도 초과 —
만** 받고 싶다. 세션이 일을 마치거나 백그라운드 작업을 기다릴 때마다 오는 알림, 특히 같은 문구가 되풀이되는 알림은 신호를 묻는다.

## Problem → Solution

지금: 허브는 「작업중에서 벗어나는 순간」마다 울린다. 하루 약 59건 = `◐ 백그라운드 대기` 52 · `○ 대기` 7 · `◆ 승인 대기` 0. 바쁜 구간이
백그라운드 대기를 지나도 끊기지 않아(`_BUSY_PHASES = {working, background}`) 모니터를 건 세션은 「백그라운드 → (작업 알림으로 깨어남)
작업중 → 백그라운드」를 돌 때마다 「16시간 44분 작업 뒤 백그라운드 작업 1개를 기다립니다」류가 새로 나갔다. 같은 순간 데스크톱 앱도
「작업 완료」 배너를 띄울 수 있어 겹친다.
→ 제안: 허브의 알림 종류를 승인 대기·한도 초과 둘로 줄인다. 두 국면(대기·백그라운드)은 더 이상 알림 국면이 아니므로 순환은
**구조적으로 0건**이 된다. 질문·허락·작업 완료는 데스크톱 앱 몫이라고 문서에 적는다.

## Metadata

- **Complexity**: Small (수정 소스 1 · 테스트 3 · run.sh 가드 1 개정 · 문서 4)
- **Source PRD**: N/A (메인 세션 지시문 — 사용자 결정 확정분)
- **Estimated Files**: 새 1(이 PRP) · 수정 8

---

## 1. 요구사항 요약

사용자 요청(원문): 「알림이 쓸데없이 많이 오는거 같아. 그리고 klago-ui-oneffice-micro 프로젝트에서 같은 내용으로 중복 알림이 계속
들어왔어. 알림은 승인 대기 같은 사용자 확인이 필요한 경우로 제한 할 수 있나?」

사용자가 확정한 것(다시 묻지 않는다):
- **역할 나누기** — 선택지 질문·도구 허락 요청·작업 완료는 데스크톱 앱 알림에 맡긴다. 앱의 「작업 완료」 알림은 그대로 둔다(허브는 앱
  설정을 건드리지 않는다).
- 허브는 **승인 대기**(`awaiting_approval`, 진행 기록 승인 단계 + 턴 끝)와 **한도 초과**(`interrupted`)만 알린다. 문구·소음 기준(MN2)·
  확인 지연(MN3)은 그대로.
- `turn_ended`·`background_wait` 알림은 끈다 — 코드·문구·테스트째 지운다.

**범위 밖**: 새 훅·이벤트 필드, 허브 화면, 훅 설치 목록(`HOOK_EVENTS`), 데스크톱 앱 설정, 터미널 세션의 질문·허락 알림(부록 A).

## 2. 이미 확인된 사실 (설계의 전제 — 재측정하지 않았다)

| 사실 | 출처 |
|---|---|
| 알림 약 59건(15:19 이후) = `background_wait` 52 · `turn_ended` 7 · `awaiting_approval` 0. klago 세션 `e5588c1a` 12회, `39460b18`(재생에서 ai-create-doc 31회 — transcript 는 klago-ui-oneffice-micro 폴더) | 메인 세션 재생(10-15 이벤트 로그, `advance_session_track` 5초 틱) |
| 반복의 원인은 `_BUSY_PHASES = {working, background}` — 백그라운드가 바쁜 구간을 이어 `busy_since` 가 유지되고, 「background → working → background」 순환마다 working 에서 벗어나는 전이가 새로 생긴다 | `hub/bin/hub_notify.py:74`, 지시문 |
| 데스크톱 앱 설정 `permission_request_notifications`·`question_notifications`·`task_complete_notifications` 셋 다 「Banners (default)」 — 앱이 뒤에 있을 때 허락 요청·선택지 질문·세션 완료를 OS 배너로 알린다 | 메인 세션 확인(`ccd_settings get_settings`) |
| 시끄러웠던 세션 `e5588c1a`·`39460b18`·`0cca1d0b` 와 이 세션 `2fe46445` 는 모두 entrypoint `claude-desktop`. 최근 이틀 sdk-cli 179건은 Litmus 앱(177)·daily-pulse(2) | 메인 세션 확인 |
| 승인 대기 0건의 이유: 설계 승인을 선택지 질문으로 물으면 턴이 끝나지 않아 base_state 가 working 으로 남는다 — 그 질문은 데스크톱 앱이 「질문」 배너로 알린다 | 지시문, `hub_session.is_awaiting_approval` |
| 국면 기계: 후보(MN3)는 `NOTIFY_KIND_BY_PHASE` 에 있는 국면으로 나갈 때만 생기고, 후보가 확정 전에 다른 알림 국면으로 바뀌면 보존한 바쁜 구간 시작으로 다시 시작한다(검수 1회차 C1) | `hub/bin/hub_notify.py:189-250` |
| T25-287 ③ 은 알림 라벨 4개(`■ 한도 초과`·`◆ 승인 대기`·`○ 대기`·`◐ 백그라운드 대기`)가 `hub_notify.py` 와 템플릿 화면 어휘에 함께 있는지 교차 확인한다. 원장 행은 ① 의 `notify_status.json`(README)을 문다 | `tests/run.sh:10859-10890`, `tests/mutations.tsv:841` |
| `background_task_count` 는 `hub_notify.py` 와 `tests/hub/test_hub_notify.py` 밖에서 쓰이지 않는다 | `grep` |

---

## 3. 결정

### AN1 — 알림은 두 종류: 한도 초과 · 승인 대기 (MN1·MN4·MN9 부분 개정)

| 종류(`NotifyKind`) | 국면 전이 | 상태 |
|---|---|---|
| `interrupted` `■ 한도 초과` | working → interrupted (바쁜 구간 무관, MN2 예외) | 유지 — 문구 그대로 |
| `awaiting_approval` `◆ 승인 대기` | working → awaiting_approval (바쁜 구간 ≥ 2분) | 유지 — 문구 그대로 |
| ~~`turn_ended` `○ 대기`~~ | working → waiting | **삭제** |
| ~~`background_wait` `◐ 백그라운드 대기`~~ | working → background | **삭제**(MN4 번복) |

- **지우는 것**(YAGNI — 끈 채 남기면 도달 불가 코드이고, 스위치로 남기면 MN10 이 거절한 「종류별 스위치」다. 되살릴 때는 git 이력이 있다):
  `NotifyKind` 두 값 · `NOTIFY_KIND_BY_PHASE` 두 행 · `NOTIFY_KIND_ORDER` 두 항목 · `NOTIFY_TITLE_LABEL_BY_KIND` 두 항목 · `_message_for` 의 두 분기 ·
  내 변경으로 고아가 되는 `SessionObservation.background_task_count`·`NotifyEvent.background_task_count` 와 `_observe_session` 의 그 계산 · 해당 테스트.
- **MN4 번복의 근거**: MN4 는 「남은 `tail -f` 때문에 끝난 세션이 영영 안 울리는」 침묵을 막으려 백그라운드 진입을 울렸다. 데스크톱 세션에서는 그
  「턴이 끝났다」를 앱의 「작업 완료」 배너가 알린다(§2). 터미널 세션은 그 알림을 잃는다 — 한계로 문서화한다(AN3).

### AN2 — 국면 기계는 그대로, 후보만 「작업중에서 벗어난 모든 전이」로 넓힌다 (MN3 개정, C1 보존)

- `NotifyPhase` 6값과 `_BUSY_PHASES = {working, background}` 는 **바꾸지 않는다.** 승인 대기의 바쁜 구간은 여전히 백그라운드를 지나도 이어져야 한다 —
  설계 30분 → 백그라운드 검사를 기다림 → 깨어나 1분 만에 보고하고 턴 끝(승인 단계)인 흐름에서 바쁜 구간이 1분으로 끊기면 MN2 가 승인 알림을 지운다.
- **반복 알림은 구조로 0건이 된다**: 대기·백그라운드가 알림 국면이 아니므로 「background ↔ working」 순환은 알림을 만들 자리가 없다.
- **후보 일반화**: 두 행을 지우기만 하면 「working → waiting →(3초 안에) awaiting_approval」에서 첫 전이가 후보를 만들지 않아 승인 알림을 놓친다(C1 이 막은
  틈이 다시 열린다). 그래서
  - 후보는 **working 에서 working 이 아닌 국면으로 나가는 모든 전이**에서 만든다(`PendingNotice` 에서 `kind` 를 지운다).
  - 후보가 있는 동안 국면이 working 이 아닌 다른 국면으로 바뀌면 보존한 바쁜 구간 시작으로 후보를 다시 시작하고(C1 그대로), working 으로 돌아오면 버린다.
  - 확정 때 종류를 `NOTIFY_KIND_BY_PHASE.get(확정 국면)` 으로 정한다 — None(대기·백그라운드·완료)이면 알림 없이 후보만 거둔다. MN2 판정은 그대로다.
  - 비용은 오늘과 같다 — 오늘도 대기·백그라운드 진입은 후보였고 확인 수집 1회를 불렀다. working → done 도 후보가 되지만 조용히 거둬진다.
- **남는 한계**: 모니터가 종일 돈 세션에서 승인 대기에 들어가면 바쁜 구간이 길게 잡혀 「16시간 … 작업 뒤 승인을 기다립니다」가 될 수 있다 — 그 전이에 1회뿐이라
  남긴다(MN2 의 「백그라운드를 지나도 끊기지 않는다」를 지키는 대가).

### AN3 — 역할 나누기: 질문·허락·작업 완료는 데스크톱 앱 알림이 맡는다

- 허브는 「앱이 알려 주지 않는 것」만 알린다 — 승인 대기(진행 기록이라는 허브만 아는 사실)와 한도 초과.
- 허브는 데스크톱 앱 설정을 읽지도 바꾸지도 않는다. 앱의 「작업 완료」 알림은 사용자가 그대로 두기로 했다.
- **문서에 적는 안내·한계**(`hub/README.md` 「macOS 알림」·「알려진 한계」, `commands/hub.md` 알림 상태 문단):
  - 질문·도구 허락 요청은 허브가 알리지 않는다 — 데스크톱 앱이 자체 알림(설정의 질문·허락 요청 알림)으로 알린다.
  - 세션이 일을 마쳤다는 알림도 데스크톱 앱의 「작업 완료」 알림이 맡는다.
  - 터미널(CLI) 세션은 질문·허락·작업 끝에 대한 허브 알림이 없다(승인 대기·한도 초과는 세션 종류와 무관하게 알린다).

### AN4 — 훅·수집·서버·화면·설정은 바꾸지 않는다

- `HOOK_EVENTS`(7개)·`hub_hook.py`·`hub_session*.py`·`hub_collect.py`·`hub_server.py`·`hub_notify_send.py`·`hub_template.html`·`hub_config.py` 무변경.
  `/hub install` 재실행이 필요 없다 — 반영은 `hub/install.sh`(또는 `/harness-update`) 뒤 `/hub server restart` 다.
- MN5(승인 대기 판정 한 곳 — 표지·알림 공유)·MN6(활동 감시로 즉시 수집)·MN7(기준선)·MN8(전달)·MN10(설정)·MN11(관측)은 그대로다.
- 알림 순서(MN8)는 「한도 초과 → 승인 대기」 둘이 된다. 한 수집의 알림 수는 최대 2.

### AN5 — 가드: T25-287 만 줄이고, 지운 종류의 되살아남은 단위 테스트로 잠근다

- **T25-287 ③ 축소**: `○ 대기`·`◐ 백그라운드 대기` 의 교차 확인 두 개를 걷는다(지우지 않으면 `hub_notify.py` 에서 라벨이 사라져 거짓 실패한다).
  `■ 한도 초과`·`◆ 승인 대기` 두 교차 확인과 ①② 는 그대로. 주석의 「라벨 4개」를 「라벨 2개」로 고친다. 원장 행(① 의 `notify_status.json`)은 무변경.
- **되살아남 방지 run.sh 가드는 두지 않는다.** 판단: 되살아남의 실체는 「대기·백그라운드 국면이 다시 알림을 만든다」는 **행동**이고, 그것은 단위 테스트
  (모니터 순환 0건·종류 집합)가 정확히 문다. run.sh 의 글자 검사(라벨 문자열 부재 등)는 다른 이름으로 되살리면 눈이 멀고(메모리 「개명하면 정적 가드가
  눈이 먼다」), 의도적으로 되살리는 결정은 어차피 테스트를 고치는 커밋이 된다. 새 가드 ID 를 쓰지 않으므로 **T25-294 이후 번호를 쓰지 않는다.**
- **래칫 하한**: 새 가드 ID·원장 행이 없으므로 `SOURCE_GUARD_ID_FLOOR`(565)·`LEDGER_MUTATION_ROW_FLOOR`(139)는 **바꾸지 않는다.** T25 그룹 설명
  (`T25-1~T25-287`)도 그대로다.
- **RED 확인(구현 단계)**: 새 회귀 테스트는 변경 전 코드(또는 `NOTIFY_KIND_BY_PHASE` 에 `"background": …` 행을 되돌린 사본)에서 실패해야 한다.

### AN6 — 문서 갱신과 개정 줄

| 문서 | 갱신 |
|---|---|
| `hub/README.md` | 「서버」 알림 한 문장(「승인 대기·한도 초과를 macOS 알림으로」) · 「프라이버시 고지」 macOS 알림 항(바뀌는 상태를 「승인 대기·한도 초과」로, 실리는 값에서 「백그라운드 작업 수」 삭제) · 「알려진 한계」(`○ 대기` 문장 삭제, 재기동 직후 2분 문장을 승인 대기로 고침, AN3 의 안내 3줄 추가) · 「macOS 알림」(울리는 때 표 두 행, 「승인 대기는 `○ 대기` 와 겹쳐…」 문장 삭제, 소음 기준의 「작업중과 백그라운드 대기가 이어진 시간」은 유지, 확인 지연의 「가짜 `○ 대기`」 예를 일반 문장으로, 「대기·백그라운드 대기 진입은 울리지 않는다 — 데스크톱 앱의 작업 완료 알림과 겹치고 모니터 세션에서 반복됐다(10-15)」 한 줄) · 「설정」 `notify_enabled` 행 · 「설계 근거」에 이 문서 |
| `commands/hub.md` | 알림 상태 문단의 「대기·백그라운드 대기·승인 대기·한도 초과로 바뀔 때」 → 「승인 대기·한도 초과로 바뀔 때」 + 「질문·허락 요청·작업 완료는 데스크톱 앱 알림이 맡는다」 한 문장 |
| `docs/prps/hub-macos-notification.md` | 머리에 개정 블록 1개(이 문서 링크·사용자 결정 날짜) + 한 줄 개정: MN1 표(대기·백그라운드 행 → AN1 로 삭제), MN2(「백그라운드를 지나도 끊기지 않는다」는 승인 대기를 위해 유지 — AN2), MN3(후보는 working 에서 벗어난 모든 전이, 종류는 확정 시 — AN2), MN4(번복 — AN1), MN8(순서 두 종류), MN9 표(두 행 삭제), MN12(「대기·백그라운드 대기 진입」 추가), §16 미결 쟁점 2(번복) |
| `README.md`(루트) | `docs/prps/` 문서 수 +1(병합 직전 재계수) |

`hub-approval-wait-badge.md`·`hub-dashboard.md` 는 바뀌지 않는다(승인 대기 판정·표지·훅 설치 결정 무변경).

---

## 4. UX

```
Before (10-15 하루 약 59건)                         After
◐ 백그라운드 대기 · klago… ×12 (같은 문구 반복)     (없음 — 순환은 알림 자리가 없다)
◐ 백그라운드 대기 · ai-create-doc ×31              (없음)
○ 대기 · … ×7                                      (없음 — 데스크톱 앱 「작업 완료」 배너가 맡는다)
◆ 승인 대기 ×0                                     ◆ 승인 대기 (그대로 — 진행 기록 승인 단계 + 턴 끝)
■ 한도 초과                                         ■ 한도 초과 (그대로)
선택지 질문·도구 허락: 허브 없음 · 앱 배너           선택지 질문·도구 허락: 앱 배너만(허브는 겹치지 않는다)
```

| Touchpoint | Before | After | 결정 |
|---|---|---|---|
| 턴 끝(≥2분) | 허브 `○ 대기` + 앱 「작업 완료」 | 앱 「작업 완료」만 | AN1·AN3 |
| 백그라운드 대기 진입·순환 | 허브 `◐ 백그라운드 대기`(반복) | 없음 | AN1·AN2 |
| 승인 대기 · 한도 초과 | 허브 배너 | 그대로 | AN1 |
| 선택지 질문 · 도구 허락 | 앱 배너 | 그대로(허브 무관) | AN3 |
| 허브 탭 화면 · 훅 · `/hub status` | — | 변화 없음 | AN4 |

## 5. 영향 범위 (Files to Change) — 예상 줄 수 변화

| 파일 | 동작 | 이유 | 줄 수(현재 → 예상) |
|---|---|---|---|
| `hub/bin/hub_notify.py` | UPDATE | 종류 2 삭제 · `background_task_count` 삭제 · 후보 일반화 · 모듈 docstring·어휘 주석의 MN4·`BACKGROUND_SESSION_LABEL` 언급 정리(AN1·AN2) | 408 → 약 395 |
| `tests/hub/test_hub_notify.py` | UPDATE | §8 | 593 → 약 585 |
| `tests/run.sh` | UPDATE | T25-287 ③ 축소·주석(AN5) | 약 −9 |
| `tests/hub/test_hub_notify_send.py` | UPDATE | 알림 입력으로 쓰던 「대기」 세션을 「승인 대기 표지가 붙은 대기 세션」으로 교체(§8) | 약 +13 |
| `tests/hub/test_hub_server.py` | UPDATE | 같은 입력 교체(`_titled_snapshot` 1줄 + docstring) | 약 +2 |
| `hub/README.md` | UPDATE | AN6 | 약 +8 / −10 |
| `commands/hub.md` | UPDATE | AN6 | 약 +1 / −1 |
| `docs/prps/hub-macos-notification.md` | UPDATE | 개정 줄(AN6) | 약 +12 |
| `docs/prps/hub-notify-answer-wait.md` | CREATE | 이 문서 | — |
| `README.md` | UPDATE | 문서 수 +1(병합 직전 재계수) | ±0 |

**바꾸지 않는 파일**: `hub_hook.py`·`hub_settings.py`·`hub_session.py`·`hub_session_facts.py`·`hub_collect.py`(791줄)·`hub_server.py`(PR #9 와 충돌 없음)·
`hub_notify_send.py`·`hub_template.html`·`hub_config.py`·`hub_model.py`·`commands/harness-update.md`·`tests/mutations.tsv`·DOM 테스트(위 두 테스트 파일은 입력만 바꾼다).

## 6. 파일 구조와 모듈 경계

변경은 ★순수 `hub_notify.py` 안에서 끝난다. 입력(`SessionView` → `SessionObservation`)과 출력(`NotifyEvent` → `NotificationText`)의 모양만 줄어들고,
소비자(`hub_notify_send.SessionNotifier` — `advance_tracks`·`compose_notifications`·`has_pending` 만 부른다)는 시그니처가 같아 무변경이다. 새 임포트 없음.
T25-10(순수 모듈 파일시스템 접근 금지) 그대로.

## 7. 데이터 모델과 인터페이스 (`hub_notify.py`, 전부 `@dataclass(frozen=True)`)

```python
NotifyKind = Literal["interrupted", "awaiting_approval"]
NOTIFY_KIND_BY_PHASE: Mapping[NotifyPhase, NotifyKind]      # interrupted·awaiting_approval 2행
NOTIFY_KIND_ORDER: tuple[NotifyKind, ...] = ("interrupted", "awaiting_approval")
NOTIFY_TITLE_LABEL_BY_KIND = {"interrupted": "■ 한도 초과", "awaiting_approval": "◆ 승인 대기"}

@dataclass(frozen=True)
class SessionObservation:
    session_id: str
    phase: NotifyPhase
    project_name: str
    task_title: str | None
    resets_at_ms: int | None        # phase == "interrupted" 일 때만 (background_task_count 삭제)

@dataclass(frozen=True)
class PendingNotice:                # kind 삭제 — 종류는 확정 시점의 국면이 정한다(AN2)
    observed_at_ms: int
    busy_duration_ms: int

@dataclass(frozen=True)
class NotifyEvent:
    kind: NotifyKind
    project_name: str
    task_title: str | None
    busy_duration_ms: int
    resets_at_ms: int | None        # (background_task_count 삭제)
```

`SessionTrack`·`NotificationText`·`NotifyStatusRecord`·`NotifyPhase`(6값)·`NotifyFailureReason` 무변경.

**공개 시그니처는 모두 그대로다** — `notify_phase`·`observe_sessions`·`advance_session_track`·`advance_tracks`·`has_pending`·`duration_label`·
`sanitize_notification_text`·`compose_notifications`·`osascript_argv`·`next_notify_status_record`·`is_notifier_active`. 바뀌는 것은 비공개 함수 둘의 인자·
동작이다:

```python
def _start_pending(previous: SessionTrack, phase: NotifyPhase, now_ms: int) -> SessionTrack:
    """작업중에서 벗어난 수집 — 종류 없이 후보로만 둔다(MN3·AN2). 바쁜 구간 시작은 보존한다."""

def _confirm_pending(previous, observation, pending, now_ms) -> tuple[SessionTrack, NotifyEvent | None]:
    """확인 지연이 지난 후보를 확정한다. 종류는 NOTIFY_KIND_BY_PHASE.get(observation.phase) — None 이거나 소음 기준(MN2)을 못 넘으면 후보만 거둔다."""
```

`advance_session_track` 의 분기 조건: 「`came_from_working` ∧ `phase in NOTIFY_KIND_BY_PHASE`」 → 「`came_from_working` ∧ `phase != "working"`」.

## 8. 테스트 계획 (`tests/hub/test_hub_notify.py` — ★순수, 시계는 인자)

| 구분 | 케이스 | 기대 |
|---|---|---|
| **걷는다** | `test_background_carries_task_and_wakeup_count_only_then` · `test_turn_ended_text` · `test_background_wait_text` · `turn_ended`/`background_wait` 확정을 기대하던 단언 | 삭제 또는 아래로 바꿈 |
| 전이(조용함) | working → waiting, 3초 뒤 확정 / working → background, 확정 / working → done | 알림 0. 앞 둘은 확정 전 `has_pending` True, 확정 뒤 False |
| **모니터 순환 회귀(신설)** | working 10분 → background → working 1분 → background … 5회 | 알림 0 (klago `e5588c1a` 의 재현) |
| 바쁜 구간 이어짐(바꿈) | working 10분 → background(확정) → working 1분 → awaiting_approval(확정) | `awaiting_approval` 1, busy ≈ 11분 이상 |
| **C1 보존(바꿈)** | working 5분 → waiting →(2초 뒤) awaiting_approval →(3초 뒤) 확정 | `awaiting_approval` 1, busy 는 처음 벗어난 시각 기준 |
| C1 — 한도 초과 | working → background →(2초 뒤) interrupted → 확정 | `interrupted` 1 |
| 기존 유지 | 기준선 · 처음 보는 세션 · 확인 지연 경계(2,999/3,000ms) · 2분 경계 · 한도 초과는 짧아도 · 승인 재진입 · 반복 수집 중복 없음 · 사라진 세션 · 결과 매핑 불변 | 오늘 기대값 그대로 |
| 관측 | `_observe_session` 이 `resets_at_ms` 만 채우고 `background_task_count` 가 없다 | `dataclasses.fields(SessionObservation)` 에 그 이름 없음 |
| 상수(신설) | `NOTIFY_KIND_ORDER` · `NOTIFY_TITLE_LABEL_BY_KIND` 키 · `NOTIFY_KIND_BY_PHASE` 값 | 셋 다 `{interrupted, awaiting_approval}` |
| 문구 | 작업 제목 끔·없음·마스킹·상한·창 경계·고립 서로게이트·정제 테스트의 운반 종류를 `turn_ended` → `awaiting_approval` 로 | 부제·정제 기대값 그대로 |
| 묶음·순서 | 같은 수집 `interrupted` 3(a,a,b) + `awaiting_approval` 1 / 다섯 프로젝트 나열 상한 | 알림 2개(한도 → 승인), `a · b`, `p1 · p2 · p3 외 2` |

- `test_hub_notify_send.py`·`test_hub_server.py` 는 지운 종류 이름을 쓰지 않지만(`grep` 0건) 알림을 만드는 입력으로 「작업중 → 대기」 세션을 쓴다 —
  대기는 더 이상 알림 국면이 아니라 그대로는 7건이 깨진다. 입력을 「승인 대기 표지가 붙은 대기 세션」(`is_awaiting_approval=True`)으로 바꾸고 기대 제목을
  `◆ 승인 대기 · proj` 로 고친다(동작·설계 변경이 아니라 테스트 입력 교체).
- **RED 확인**: 모니터 순환·상수 테스트는 변경 전 `hub_notify.py` 로 돌리면 실패해야 한다. C1 보존 테스트는 「두 행만 지우고 후보를 일반화하지 않은」 사본에서
  실패해야 한다(일반화가 필요하다는 증명).
- run.sh: T25-287 개정(§AN5) 뒤 그 그룹(T25)이 통과하고, 원장의 T25-287 변조행(README `notify_status.json`)이 여전히 실패를 만든다.

### Edge Cases Checklist

- [x] 백그라운드 ↔ 작업중 무한 순환 → 0건
- [x] 대기를 거쳐 3초 안에 승인 대기 → 1건(C1)
- [x] 백그라운드를 거친 뒤 짧은 마무리 턴의 승인 대기 → 바쁜 구간 보존으로 1건
- [x] 서버 재기동·처음 보는 세션 → 기준선 0건(MN7)
- [x] 한 수집에 여러 세션 승인 대기 → 1배너(`세션 N개`)

## 9. 리스크와 대안

### 리스크

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| 터미널 세션은 턴 끝·질문·허락 알림이 없다 | 중(이 사용자는 대부분 데스크톱) | 침묵 | README 한계·안내, 부록 A 가 재개 지점 |
| 데스크톱 앱 알림을 사용자가 꺼 두면 질문·허락·작업 완료가 아무 데서도 안 온다 | 낮음 | 침묵 | README 안내가 앱 설정 이름을 가리킨다(허브는 설정을 읽지 않는다) |
| 모니터 세션의 승인 대기 문구에 긴 작업 시간 | 낮음 | 어색한 문구 1회 | 한계로 남김(AN2) |
| 동시 PR #9 와 README·run.sh 겹침 | 중 | 병합 충돌 | §10 |

### 검토했으나 채택하지 않은 대안

- **허브가 질문·허락도 알린다 — 훅 3개(`PreToolUse`·`PostToolUse` 는 `AskUserQuestion`, `Notification` 은 `permission_prompt`) 추가**: 데스크톱 앱이 이미 배너로
  알린다(설정 3종 기본 Banners) — 데스크톱 세션에서 중복이다. (1차 초안 — 조사는 부록 A)
- **새 기록 필드 `tn`·`nt`(허용 목록 값)**: 위 훅이 없으면 기록할 것이 없다 — 데스크톱 앱이 이미 배너로 알린다, 데스크톱 세션에서 중복.
- **`AnswerWait` 에피소드와 그 전이(질문 교체·허락 흡수·10분 재무장)·판정(`effective_answer_wait`)·추적(처리한 시작 시각)**: 데스크톱 앱이 이미 배너로 알린다 —
  데스크톱 세션에서 중복.
- **질문 대기·허락 대기 알림 종류(`◆ 질문 대기`·`◆ 허락 대기`, 질문 60초·허락 0초 문턱)**: 데스크톱 앱이 이미 배너로 알린다 — 데스크톱 세션에서 중복.
- **`HOOK_EVENTS` 10개·matcher 설치(`HOOK_MATCHER_BY_EVENT`)**: 데스크톱 앱이 이미 배너로 알린다 — 데스크톱 세션에서 중복(그리고 사용자 재설치 부담).
- **`commands/harness-update.md` Phase 4b 5번 조건부 안내**: 훅 목록이 바뀌지 않으면 안내할 것이 없다 — 데스크톱 앱이 이미 배너로 알린다, 데스크톱 세션에서 중복.
- **hub-dashboard.md 「`Notification` 은 설치하지 않는다」 번복**: 설치하지 않으므로 번복할 것이 없다(옛 근거는 낡았다 — 부록 A) — 데스크톱 앱이 이미 배너로 알린다,
  데스크톱 세션에서 중복.
- **`/hub install` 재실행**: 훅이 그대로라 필요 없다 — 데스크톱 앱이 이미 배너로 알린다, 데스크톱 세션에서 중복.
- **`_BUSY_PHASES` 에서 background 를 빼 반복의 원인만 고친다(두 종류는 유지)**: 순환마다의 반복은 줄지만 턴 끝·백그라운드 진입 알림이 남아 앱 「작업 완료」와 겹치고,
  승인 대기의 바쁜 구간이 백그라운드에서 끊겨 짧은 마무리 턴의 승인 알림을 놓친다.
- **두 종류를 스위치로 남긴다**: MN10 이 거절한 종류별 스위치이고, 끈 채 남긴 코드는 도달 불가다.
- **지운 종류의 되살아남을 막는 run.sh 가드**: 행동은 단위 테스트가 더 정확히 문다(AN5).

## 10. 병합 직전 재계수 (PR #9 와의 동시 작업)

- 이 작업은 **새 T25 번호·DOM 번호를 쓰지 않는다**(T25-287 개정만). PR #9 의 T25-288~293·D46~D52 와 겹치지 않는다.
- `SOURCE_GUARD_ID_FLOOR`·`LEDGER_MUTATION_ROW_FLOOR` 는 이 작업으로 바뀌지 않는다 — 병합 시점 develop 값을 그대로 둔다.
- T25 그룹 설명의 끝 번호는 PR #9 가 정한 값을 따른다.
- 루트 `README.md` 의 `docs/prps/` 문서 수(+1, PR #9 가 문서를 더했다면 합산).
- `hub/README.md`·`commands/hub.md`·`tests/run.sh` 를 PR #9 도 고쳤다면 절 단위로 합친다. `hub_server.py` 는 이 작업이 건드리지 않는다.

## 11. Mandatory Reading

| 우선 | 파일 | 행 | 이유 |
|---|---|---|---|
| P0 | `hub/bin/hub_notify.py` | 1-60, 84-270, 315-365 | 종류·관측·후보·확정·문구 — 고칠 본체 |
| P0 | `tests/hub/test_hub_notify.py` | 전체 | 걷고 바꿀 테스트 |
| P1 | `tests/run.sh` | 10859-10890 | T25-287 |
| P1 | `docs/prps/hub-macos-notification.md` | 60-260, 733-742 | 개정 줄을 넣을 MN 결정 |
| P1 | `hub/README.md` | 150-157, 225-234, 486-502, 653-699 | 고칠 문단 |

## 12. Step-by-Step Tasks (구현 단계 — TDD)

| # | 작업 | 검증 |
|---|---|---|
| A1 | 새·바뀐 테스트 먼저(모니터 순환·C1 보존·상수·관측) → 변경 전 코드에서 RED 확인 | `python3 -B -m unittest tests.hub.test_hub_notify` |
| A2 | `hub_notify.py` 종류·필드 삭제 + 후보 일반화 + docstring·주석 정리 | 같은 모듈 GREEN, `test_hub_notify_send`·`test_hub_server` 는 입력 교체 뒤 통과 |
| A3 | T25-287 ③ 축소 · 문서(AN6) · 개정 줄 | `bash tests/run.sh`(메인 세션이 커밋 직전 1회, 백그라운드 + 완료 알림) |
| A4 | (사용자 확인 뒤) `hub/install.sh`·`/hub server restart` — 하루 사용 뒤 `notify_status.json`·체감 소음 확인 | PR·메모에 한 줄 |

GOTCHA:
- 테스트 문구 검사의 운반 종류를 `turn_ended` 에서 `awaiting_approval` 로 바꿀 때 기대값에 작업 시간 본문이 붙는다 — 부제·정제 단언만 보는 테스트는 본문을 보지 않게 둔다.
- `hub_notify.py` 머리 docstring 의 「근거: … 백그라운드 대기(MN4)」와 어휘 주석의 `BACKGROUND_SESSION_LABEL` 을 지운다(T25-287 주석과 같이).
- ★순수 모듈 주석에도 `open(`·`Path(`·`os.` 를 쓰지 않는다(T25-10).
- `python3 -B`, 돌린 뒤 `__pycache__` 를 지운다(commands 파일 수 거짓 실패).
- 실 `$HOME` 대상 설치·서버 재기동은 사용자가 요청할 때만(프로젝트 CLAUDE.md §1(b)).

## 13. Validation Commands

```bash
python3 -B -m py_compile hub/bin/*.py      # 뒤에 /usr/bin/find hub/bin -name __pycache__ -prune -exec rm -rf {} +
python3 -B -m unittest discover -s tests/hub -t .
bash -n install.sh && bash -n hub/install.sh
bash tests/run.sh                           # 메인 세션이 커밋 직전 1회(수십 분 — 백그라운드 + 완료 알림, sleep 폴링 금지)
```
구현자·검수자는 `test_hub_notify`(+ 입력을 바꾼 `test_hub_notify_send`·`test_hub_server`)만 돌린다.

## 14. Acceptance Criteria

- [ ] 대기·백그라운드 대기 진입과 그 순환이 어떤 경우에도 알림을 만들지 않는다(모니터 순환 0건)
- [ ] 승인 대기·한도 초과 알림의 문구·소음 기준·확인 지연이 오늘과 같다(C1 틈 포함)
- [ ] `hub_notify.py` 밖의 파이썬 코드 무변경, 훅·`/hub status`·허브 화면 무변화
- [ ] README·`commands/hub.md` 가 질문·허락·작업 완료는 데스크톱 앱이 알린다는 것과 터미널 세션 한계를 말한다
- [ ] 정본 검증 명령 4종 통과

## 15. 미결 쟁점

없음 — 범위·종류·문구·기준값은 사용자가 정했다. 되살아남 방지 가드를 두지 않는 판단(AN5)만 설계 판단이다.

---

## 부록 A — 터미널 세션 지원을 다시 꺼낼 때 (1차 초안 조사 요약, 10-15)

출처: `code.claude.com/docs/en/hooks.md`(전체)·`permission-modes.md`·`tools-reference.md`·`agent-sdk/user-input.md`. 실측은 하지 않았다.

**문서 사실**
- `Notification` matcher `permission_prompt`: 허락 대화상자가 떠서 약 6초 답이 없을 때. 터미널은 마지막 키 입력부터 6초(입력하면 미뤄짐). canUseTool 호스트(데스크톱·
  VS Code)는 요청 6초 뒤, 입력해도 미뤄지지 않고 그 전에 답하면 발화하지 않는다. **v2.1.233 이전에는 canUseTool 호스트에서 발화하지 않았다** — hub-dashboard.md 의
  「`Notification` 은 설치하지 않는다(CAM 실측 2026-08-04)」 근거는 그 이전 호스트의 관측이다(이 PC 는 2.1.295). 다시 꺼내면 그 결정의 개정이 필요하다.
- `agent_needs_input`: 터미널 agent view 의 백그라운드 세션이 입력을 기다릴 때 + 팀원 설정 질문 + auto 모드 분류기 과금 안내 — 데스크톱과 무관.
- `PermissionRequest`: 「물어보려 할 때, 또는 물을 수 없어 자동 거부할 때」. auto 모드에서 분류기 판정 전에도 발화하는지는 문서로 확정되지 않는다(수명 주기 그림은
  PermissionDenied 를 그 곁가지로 그린다).
- `AskUserQuestion`: `PreToolUse`·`PostToolUse` matcher 로 잡힌다(내장 도구 목록에 명시). SDK 호스트는 canUseTool 에서 `allow` + `updatedInput.answers` 로 답한다 →
  도구가 실행되어 `PostToolUse` 가 온다. 어떤 모드도 자동 승인하지 않는다.
- 끝 신호: 질문은 `PostToolUse`. 허락은 없다 — `PostToolUseFailure` 는 권한 거부에 발화하지 않고, `PermissionDenied` 는 auto 분류기 거부만, `Stop` 은 사용자 인터럽트에
  발화하지 않는다.

**설계 스케치(기각됐던 안 — 재사용 가능)**: 훅 3개(`PreToolUse`·`PostToolUse` matcher `AskUserQuestion`, `Notification` matcher `permission_prompt` — matcher 없으면 모든
도구 호출마다 동기 훅) · 기록은 허용 목록 값 `tn`·`nt` 만(tool_input·message 미기록) · 세션당 답 대기 에피소드(종류, 시작 시각 = 알림 1건의 정체성) — 새 질문은
교체, 질문 중 허락 신호는 흡수, 허락은 10분 안 흡수·이후 재무장, 턴 경계·질문 답이 닫음, 신호 이벤트는 백그라운드 보고를 지우지 않음 · 문턱 질문 60초·허락 0초
(호스트 6초를 믿음) · 화면 표지와는 합치지 않음(허락은 끝 신호가 없다).

**설치 후 실측이 필요했던 항목**: U1 데스크톱 `permission_prompt` 실제 발화 · U2 질문 답 뒤 `PostToolUse` 발화 · U3 질문의 `permission_prompt` 메아리 · U4 auto 모드·
`ExitPlanMode` 거동 · U5 서브에이전트 허락의 `session_id`·`agent_id` · U6 질문 닫기(Esc)에 훅 없음 · U7 `CLAUDE_CODE_DISABLE_PERMISSION_PROMPT_NOTIFY_HOOKS`.
