한 세션이 두 작업을 동시에 진행해도 허브가 작업마다 진행률을 따로 보여 주게 한다.
지금은 진행 기록이 세션당 한 덩어리라, 두 작업의 기록이 섞이면 한 작업의 검수 통과가 다른 작업까지 「100% 완료」로 만들고 제목·진행중 단계 설명도 엉뚱한 작업 것이 보인다.
승인하면 진행 기록에 작업 이름표(「결함①」 같은 짧은 이름)를 붙일 수 있게 되고, 상세 패널은 작업마다 진행 카드를 따로 그리며, 커밋까지 끝난 작업은 접힌 줄로 내려간다.
이름표 없는 지금까지의 기록은 지금과 똑같이 한 작업으로 보이고, 대가로 세션이 동시에 두 작업을 할 때는 기록할 때마다 이름표를 붙여야 한다(잊으면 지금처럼 섞인다).

> 상태: **설계 — 사용자 승인 대기** (2026-10-21). 설계 모델: opus(기본 — 승격 기준 미해당: 데이터 모델은 필드 추가뿐이고 전면 개편이 아니다).
> 작업 위치: 워크트리 `.claude/worktrees/hub-dashboard-multi-task`(브랜치 `feat/hub-dashboard-multi-task`, origin/develop `26798f8` 기준).
> 목업: `/private/tmp/claude-501/-Users-byron-private-project-coding-harness/2fe46445-0036-4875-adbf-e75bbdb2bd55/scratchpad/hub-dashboard-multi-task-mockup.html`
> (PNG 전체 `…/scratchpad/hub-dashboard-multi-task-mockup.png`, 잘라 낸 것 `…-panel-light.png`·`…-panel-dark.png`·`…-card-light.png`·`…-card-dark-pip.png`,
> 생성기 `…/scratchpad/build_multitask_mockup.py` — 「현재」는 작업 트리의 실제 렌더러가 실사례 JSONL 로 그린 결과, 「제안」은 같은 템플릿 `<style>` 에
> 제안 규칙만 얹고 §3 MT3~MT5 를 그대로 시험 구현해 그렸다. 규칙 파일 개정안 실측본 `…/scratchpad/proposed-dashboard-recording.md`).
>
> 대상: `hub/bin/hub_parse.py`(★순수) · `hub/bin/hub_dashboard_log.py` · `hub/bin/hub_dashboard_render.py`(★순수) · `hub/bin/hub_dashboard_template.html` ·
> `hub/bin/hub_template.html` · `hub/rules/dashboard-recording.md` · `hub/README.md` · `docs/prps/dashboard-rationale.md`(폴링 계약 표 개정) · `README.md`(설계 문서 수) ·
> `tests/hub`(단위·계약·DOM) · `tests/run.sh`(T22·T25·T34·T40)·`tests/mutations.tsv`.
> **바꾸지 않는 것**: 훅·수집(`hub_collect`)·`hub_session`(경계·끝난 작업·승인 대기 판정 코드)·`hub_notify`·`hub_model`·`hub_project`·`hub_server`·
> 기록 파일 경로·리텐션·오프 스위치·`switch` 서브커맨드·`commands/hub.md`·`hub/install.sh`(규칙 파일 수 그대로).

---

## 1. 요구사항 요약

klago-ui-oneffice-micro 세션 하나가 「결함 ① 수정」과 「9회차 단계 구현」을 동시에 진행했다. 구현·검수 서브에이전트는 각각 돌았고 왼쪽 카드의 실행 줄에는 둘 다
보였지만, 상세 패널의 진행 카드는 한 작업만 그렸고 결함 ①의 재검수 PASS(17:00:57)가 기록 전체를 4/4 · 100% 로 만들었다 — 9회차 구현은 진행 중이었다. 다음 날
9회차의 `log impl` 이 다시 3/4 · 75% 로 되돌렸지만 카드 제목은 여전히 착수 때의 「보고 자동 반영 8회차」였다.

원인은 데이터 모델이다 — 진행 기록은 세션당 `init` 하나 + 그 뒤의 `log` 열이고, 단계 상태는 기록 종류만으로 위치 전이한다(`hub_parse._apply_log_kind_transition`).
「어느 작업의 기록인가」를 담을 자리가 없다. 두 번째 작업을 `init` 으로 시작하면 기록기가 파일을 통째로 새로 써 첫 작업 기록이 지워지므로(`cmd_init`), 세션은
init 없이 한 기록에 이어 썼다.

사용자가 고른 방향(대안 「에이전트가 돌면 100% 막기」는 이번에 하지 않는다):
- 진행 기록마다 **작업 이름표**를 붙일 수 있다.
- 상세 패널은 **작업마다 진행 카드**를 따로 그린다.
- **커밋까지 끝난 작업은 접어 둔다**(사라지지 않는다).
- **이름표 없는 기존 기록은 지금처럼 하나로** 보인다.
- 대가: 동시 작업 중에는 기록마다 이름표를 붙여야 하고, 그 지침을 기록 규칙에 짧게 넣는다. 잊으면 지금처럼 섞이는 것은 수용한다.

## 2. 이미 확인한 사실(출발점 — 메인 세션 실측 + 코드 정독, 재측정하지 않았다)

| 사실 | 근거 |
|---|---|
| 실사례 기록 15줄: init 1회(「보고 자동 반영 8회차 …」, `설계\|승인\|구현\|검수`) 뒤 세 갈래(8회차 QA·9회차·결함 ①)의 log 가 섞였다. 13:16·16:32 줄은 한 요약에 두 작업 이야기가 함께 있다 | `…/klago-ui-oneffice-micro/.claude/dashboards/0cca1d0b-….jsonl`(읽기만) |
| `cmd_init` 은 파일을 init 한 줄로 원자적으로 **새로 쓴다**. `cmd_log`·`cmd_step` 은 읽고 한 줄 덧붙여 원자적으로 다시 쓴다 | `hub_dashboard_log.py` 168~259행 |
| `parse_event_lines` 는 **마지막 init 이후**만 남긴다. `snapshot_from_events` 는 `events[0]` 의 phases 로 `derive_phase_states` 를 돌려 `Tier1Snapshot` 하나를 만든다 | `hub_parse.py` 208~350행 |
| 회차 `R{n}` 은 세션 전체 pass·fail 의 누적 수다 — 실사례에서 결함 ①의 1회차 FAIL 이 `R2` 로 찍혔다(8회차의 PASS 가 R1) | `hub_dashboard_render._collect_log_entries`, 목업 「현재」 |
| 상세 패널 문서는 앵커 9종 치환으로 그려지고, 1분 폴링이 `#dz-title`·`#dz-progress-pct`(textContent)·`#dz-progress-bar`(style)·`#dz-steps`(outerHTML)를 부분 치환한다. `dz-step-{n}` id 를 읽는 코드는 없다(주석·가드만 있다) | `hub_dashboard_render.py` 30~154행, `hub_dashboard_template.html` 393~451행 |
| `Tier1Snapshot` 의 소비자: 세션 줄 진행률(`renderTier1` — title·completed·total·percent), 끝난 작업 판정(`is_session_tier1_from_finished_task` — percent), 실행 목록 경계·소요 시간(`previous_task_boundary_ms` — percent·task_started_at_ms), 승인 대기 표지·알림(`is_awaiting_approval` — is_approval_step_active), 알림 부제(`hub_notify` — title). `is_committed`·`steps` 는 읽는 곳이 없다 | `hub_session.py` 402~485행, `hub_notify.py` 165행, `hub_template.html` 2286~2356행, grep |
| 프로젝트 단위 `project.tier1` 은 화면이 그리지 않는다(결정 MX4). 레지스트리 등록·세대 판정에만 쓰인다 | `hub_template.html` 16~22행, `hub_model.py` 66~93행 |
| 기록 규칙 파일은 1415B, **T40-5 래칫**(`HUB_DASHBOARD_RULE_BUDGET_BYTES=1415`, 1B 라도 늘면 실패)만 받는다. T26(상시 컨텍스트 예산)의 대상은 `CLAUDE.md`·`rules/README.md`·`rules/common`·`rules/workflow` 라 이 파일은 **T26 밖**이다. 다른 제약: `paths:` 금지·`dashboard_enabled`·`.claude/settings.local.json` 리터럴(T40-6), `디스패치·결과 시점에는`(T22-158a), 런처 정규형 정확히 1회(T33-2), 코드 블록 관문 구문 금지(T33) | `tests/run.sh` 322~339·3850·12228~12290·15960~15985행 |
| 「헬퍼 스크립트」 표 ↔ 기록기 정합은 T34(서브커맨드 4종·분기 수 4·폐쇄 어휘 10종)가 문다 | `tests/run.sh` 12293~12350행 |

## 3. 결정

### MT1 — 작업 단위와 이름표: 기록 한 줄에 선택 필드 `task`

- 모든 이벤트(init·log 7종·step)에 선택 문자열 필드 `task`(이름표)를 둔다. 없거나 `""` 이면 **이름표 없음**이다.
- **이름표 없는 기록은 「첫 작업」의 것이다.** 첫 작업 = 세션 기록의 시작점 init(MT3)의 작업. 이름표 없이 `init` 한 보통의 세션은 첫 작업도 이름표가 없고,
  나중에 동시 작업이 생기면 **나중 작업만** 이름표를 단다. 착수 때는 동시 작업을 미리 알 수 없으므로 첫 작업에 거슬러 이름표를 붙이는 수단을 만들지 않는다(YAGNI).
- 이름표 형식(`hub_parse.is_valid_task_label`, 생산자·소비자 공유 — HD14 관례): **1~20자, 앞뒤 공백 없음, `str.isprintable()`**(개행·탭·제어 문자·U+2028 거부 —
  한 줄 렌더 계약 H1 과 같은 이유). 한글·`①`·공백(가운데)·기호는 허용한다. 20자는 실사례 이름표(「결함①」 3자·「9회차」 3자)의 6배 여유이자, 550px 패널 로그 항목에서
  요약 글자를 절반 넘게 먹지 않는 폭이다.
- 이름표는 **주소**다 — 화면의 작업 이름은 그 작업 init 의 제목이고, 이름표는 배지로 함께 보인다(MT7). 비교는 문자열 완전 일치.

### MT2 — 기록기 인터페이스: 서브커맨드 바로 뒤 `--task '<이름표>'`

```
init [--task '<이름표>'] '<제목>' '<단계1|단계2|…>'
log  [--task '<이름표>'] <design|approve|impl|pass|fail|commit|note> '<요약>' ['<상세>']
step [--task '<이름표>'] <n> <done|active|wait>
switch on|off                                   # 바뀌지 않는다
```

- 위치를 **서브커맨드 바로 뒤 첫 인자**로 못 박는다 — `log` 의 선택 위치 인자 `['<상세>']` 와 충돌하지 않고, 요약·상세 본문이 우연히 `--task` 로 시작해도 옵션으로
  오인하지 않는다. `--task=…` 한 덩어리 형태는 받지 않고 **BADTASK** 로 거절한다 — 받지 않으면 `init --task=결함① …` 이 제목 「--task=결함①」인 **무표 init 으로
  해석돼 기존 기록을 통째로 지운다**(모델이 만들 법한 표기 변형이라 실제로 일어날 수 있는 실패 경로다). 그래서 첫 인자가 `--task` 로 시작하면 정확히 `--task` 일 때만
  옵션이고 나머지는 전부 BADTASK 다.
- **init 의미론**
  - 이름표 없는 `init`: **지금 그대로** — 파일을 init 한 줄로 새로 쓴다(이름표 작업까지 전부 지운다 = 「세션 기록을 새로 시작」). 순차 작업의 오늘 동작이 바뀌지 않는다.
  - 이름표 붙은 `init`: 파일이 있으면 init 한 줄을 **덧붙이고**(기존 기록 보존), 없으면 그 한 줄로 만든다. 7일 리텐션 정리는 두 경우 모두 지금처럼 돈다.
    같은 이름표로 다시 `init` 하면 **그 작업만** 새로 시작한다(MT3 의 재시작 규칙 — 무표 init 이 세션 전체를 새로 시작하는 것과 같은 모양을 작업 범위로).
- **log·step**: 이름표가 없으면 첫 작업 몫으로 덧붙인다 — 파일만 있으면 지금처럼 쓴다(**NOTASK 를 내지 않는다** — 하위 호환과 「잊으면 섞일 뿐」을 지킨다).
  이름표가 있으면 그 이름표의 살아 있는 작업이 있어야 쓴다(`hub_parse.live_task_labels` 로 판정), 없으면 **NOTASK** 를 내고 쓰지 않는다 — 오타 이름표가 화면에
  유령 작업 카드를 영구히 만드는 것을 막는다(암묵 생성 대안은 §8.2 기각 C).
- 새 폐쇄 어휘 2개. 검사 순서(앞에서 걸리면 거기서 끝):

| 서브커맨드 | 순서 → 출력 |
|---|---|
| `init` | `NOSESSION` → `DISABLED` → **`BADTASK`** → (디렉터리·쓰기 실패) `MKDIR-FAILED` → `OK` |
| `log` | `NOSESSION` → `DISABLED` → **`BADTASK`** → `NOINIT`(파일 없음) → `BADKIND` → **`NOTASK`** → `OK` |
| `step` | `NOSESSION` → `DISABLED` → **`BADTASK`** → `NOINIT` → `BADINDEX` → **`NOTASK`** → `OK` |

  `BADTASK` = `--task` 뒤 값 없음 · 앞뒤 공백을 걷은 값이 형식 위반 · `--task=…`. `NOTASK` = 이름표가 가리키는 작업의 init 이 살아 있는 기록에 없음.
- 쓰는 줄: 이름표가 있을 때만 `"task"` 키를 넣는다 — 이름표 없는 호출이 쓰는 바이트는 **오늘과 한 글자도 다르지 않다**.
  예: `{"time_ms": …, "kind": "init", "title": "결함 ① 수정 — …", "phases": ["구현", "검수"], "project": "klago-ui-oneffice-micro", "task": "결함①"}`,
  `{"time_ms": …, "kind": "fail", "summary": "…", "detail": "[검증,구조] …", "task": "결함①"}`.

### MT3 — 파서: 「살아 있는 이벤트 열」 (`parse_event_lines` 계약 개정)

1. **줄 파싱**은 지금 그대로 + `task` 필드: 없으면 `""`, 있으면 문자열이고 (`""` 이거나 `is_valid_task_label`) 이어야 한다 — 아니면 **그 줄만** 버린다(계약 B, fail-open).
2. **시작점** = 마지막 **무표** init. 무표 init 이 없으면 첫 init(이름표). init 이 하나도 없으면 `()` — 「init 없음」 경고 경로 그대로.
   (기록기가 만든 파일에서 무표 init 은 항상 1행이다 — 무표 init 이 파일을 새로 쓰므로. 손으로 만든 파일도 「무표 init = 세션 새 시작」으로 같게 읽는다.)
3. **정규화** — 무표 이벤트의 `task` 를 시작점 init 의 이름표로 채운다(첫 작업 몫, MT1). 시작점이 무표면 `""` 그대로라 옛 기록은 아무것도 바뀌지 않는다.
4. **생존** — 각 이벤트는 자기 작업의 **마지막 init 이후(그 init 포함)** 일 때만 남는다. 재시작된 작업의 옛 이벤트와, 자기 init 보다 먼저 온 이름표 이벤트(고아)가 빠진다.
   - 이 규칙으로 결과의 `events[0]` 은 항상 init 이다(가장 이른 생존 이벤트의 작업 init 은 그보다 앞서거나 같고 그 init 도 생존한다) — 기존 계약
     (`build_published_values` 의 `events[0].kind == "init"` 검사, `snapshot_from_events` 의 `events[0]` 가정)을 그대로 지킨다.
   - 로그 목록·회차·진행률이 모두 이 같은 열에서 나오므로 셋이 서로 어긋나지 않는다.
- 한 번 훑기(O(n))로 끝난다. 단계 축약기의 이차 비용(RA3, 이벤트 수 × 단계 수)은 작업마다 자기 이벤트만 돌아 전체로는 지금 이하다.

### MT4 — 작업별 진행: `TaskProgress` — 기존 축약기를 작업마다 그대로 쓴다

- `split_events_by_task(events)` 가 살아 있는 열을 **init 순서**로 작업별 묶음(`init, …그 작업 이벤트`)으로 나눈다.
- 묶음마다 지금의 함수를 **그대로** 돌린다: `derive_phase_states`(위치 전이 규칙 불변) · `latest_log_summary`(진행중 단계 상세 — 이제 **그 작업의** 마지막 요약) ·
  `is_commit_logged_after_last_pass` · `is_approval_step_active`. 새 전이 규칙을 만들지 않는다.
- 회차 `R{n}` 은 **작업별** 누적 pass·fail 수다(DN5 의 작업 범위 개정) — 「결함 ① 1회차 FAIL」이 `R1` 로 찍힌다.

### MT5 — 대표 작업과 접힘

- **끝남** = 진행률 100%(`pass` — README 데이터 모델의 종료 신호, FT1 과 같은 정의). **닫힘** = 끝남 ∧ 마지막 pass 뒤 commit 있음(`is_committed`).
- **대표 작업**(세션 수준 값을 대신하는 작업 하나) = 후보 중 **가장 최근에 기록된 작업**(그 작업의 마지막 생존 이벤트가 파일에서 가장 뒤 — 시각이 아니라 순서라 같은 밀리초 동률이 없다).
  후보는 앞에서부터 처음 비지 않는 것: ① 승인 단계가 진행중인 미완 작업 ② 미완 작업 ③ 모든 작업.
  ①을 앞세우는 이유: 승인 대기 알림의 부제가 대표 작업 제목이다(`hub_notify` 무변경) — 다른 작업이 더 최근에 기록됐어도 「승인 대기 — <승인을 기다리는 작업>」이 나와야 한다.
- **접힘** = 닫힘 ∧ 대표 아님. 그래서 (a) 작업이 하나뿐이면 절대 접히지 않는다(옛 기록·오늘의 커밋 완료 화면 그대로) (b) 모두 닫히면 가장 최근 작업 하나는 펼쳐 둔다
  (c) commit 뒤에 다시 `fail`·`impl` 이 오면 100% 가 아니게 돼 저절로 펼쳐진다.
- **표시 순서** = 펼친 작업(init 순) → 접힌 작업(init 순). 진행 중 카드가 위에 오고, 기록이 들어와도 카드 자리가 뛰지 않는다(시작 순서는 바뀌지 않는다).
- 접힌 작업은 **사라지지 않는다** — 다음 무표 init(세션 새 시작) 전까지, 또는 기록 파일 7일 리텐션까지 남는다. 개수 상한은 두지 않는다(§8.1 R5).

### MT6 — 세션 수준 값(`Tier1Snapshot` 상단 필드)과 소비자별 의미 — 소비자 코드는 바꾸지 않는다

`Tier1Snapshot` 에 `tasks: tuple[TaskProgress, ...] = ()`(표시 순서, 맨 뒤 필드)를 더하고, 상단 필드는 **소비자가 이미 기대하는 의미가 다중 작업에서도 성립하도록** 정의한다:

| 상단 필드 | 다중 작업에서의 값 | 소비자와 그 의미가 성립하는 이유 |
|---|---|---|
| `title`·`completed`·`total`·`percent`·`steps`·`is_committed` | 대표 작업의 값 | `percent` = 100 ⇔ **모든 작업이 끝남**(대표는 미완 작업이 있으면 그중에서 고른다) → 끝난 작업 판정(FT1)·실행 목록 경계 (a)/(b) 분기가 「세션의 작업이 다 끝났나」를 그대로 묻는다. `title` → 알림 부제(MT5 ①) |
| `is_approval_step_active` | **어느 작업이든** 승인 단계 진행중 | 승인 대기 표지·알림(`is_awaiting_approval`)은 「사용자 차례인 작업이 하나라도 있나」다. MT5 ① 덕분에 대표 작업의 값과 같다 — 정의는 any 로 적어 둔다 |
| `task_started_at_ms` | 미완 작업이 있으면 그 시작들 중 **가장 이른 것**, 없으면 대표 작업의 시작 | 실행 목록 경계 (a)는 「진행 중 작업에 속한 실행은 숨기지 않는다」다 — 대표 작업 시작으로 두면 먼저 시작한 다른 진행 중 작업의 끝난 실행이 「이전 작업」으로 숨는다. 소요 시간 표시(LM11)도 「지금 진행 중인 일들이 시작된 지」가 된다 |
| `updated_text` | 마지막 생존 이벤트 시각 | 그대로 |
| `tasks` | 작업 목록(표시 순서, `is_folded` 포함) | 세션 줄 진행률(MT9)·상세 패널(MT7) |

- 작업이 하나면(옛 기록 전부) 상단 필드는 **오늘 값과 같다** — 대표 = 유일 작업, 가장 이른 미완 시작 = 그 작업 시작 = init 시각.
- 프로젝트 단위 `tier1`(`select_tier1_source`·세대 판정)은 `file_mtime_ms`·`session_id` 와 세션 판정만 읽어 그대로다. `snapshot_content_key` 는 `tasks` 가 이벤트 열의 함수라 안전하다.
- `Tier1Snapshot` 상단 필드를 「대표 작업」으로 좁히고 소비자마다 고치는 대안은 §8.2 기각 A.

### MT7 — 상세 패널: 작업 카드 묶음 `#dz-tasks` 하나로 그리고 통째 교체한다

- 템플릿의 첫 `.card`(h1·막대·%·단계 목록) 자리를 앵커 **`  <div id="dz-tasks"></div>`** 하나로 바꾼다. 렌더러가 그 안에 작업 카드를 표시 순서대로 그린다.
  작업이 하나뿐이고 이름표가 없으면 카드 1장 — 클래스·글자·모양이 지금과 같다(목업 「현재」와 대조).
- 펼친 카드(마크업이 계약이다 — 클래스는 기존 CSS 를 그대로 받는다):
  ```html
      <div class="card task-card">
        <h1><span class="badge task">결함①</span>결함 ① 수정 — 같은 문서로 가는 연결끼리 서로 취소</h1>
        <div class="bar-outer"><div class="bar-inner" style="width:50%"></div></div>
        <div class="pct">1/2 · 50%</div>
        <ol class="steps">
          <li class="done"><span class="num">1</span>구현<span class="chip">완료</span><span class="step-detail"></span></li>
          <li class="active"><span class="num">2</span>검수<span class="chip">진행중</span><span class="step-detail">결함 ① 지적 2건 수정 — …</span></li>
        </ol>
      </div>
  ```
  이름표 배지는 이름표가 있을 때만 붙는다. 이스케이프는 지금 규칙 그대로(`_escape_single_line` — 텍스트 노드).
- 접힌 카드 — 네이티브 `<details>`(키보드·낭독기 지원이 공짜다), 펼치면 단계 목록:
  ```html
      <details class="card task-card task-folded">
        <summary><span class="badge task">결함①</span><span class="task-folded-title">결함 ① 수정 — …</span><span class="badge commit">커밋</span><span class="task-folded-pct">2/2 · 100%</span></summary>
        <ol class="steps">…</ol>
      </details>
  ```
- 작업 추적(로그) 목록은 **하나로 둔다**(시간순·필터 3종 그대로). 항목마다 이름표 배지(시각 뒤, 회차 앞)를 붙이고 회차는 작업별이다(MT4). 이름표 없는 항목은 지금 모양 그대로.
- 문서 안 **id 를 없앤다**: `dz-title`·`dz-progress-bar`·`dz-progress-pct`·`dz-steps`·`dz-step-{n}`. 카드가 여러 장이면 id 가 겹치고, `dz-step-{n}` 은 읽는 코드가 없다
  (폴링은 `#dz-steps` outerHTML 만 썼다). 앵커는 9종 → **6종**(프로젝트 이름·작업 묶음·구현 세부 2종·로그·갱신).
- 폴링: `syncText('dz-title')`·`syncText('dz-progress-pct')`·`syncProgressBar`·`syncVisualization` 을 **`syncTasks`(`#dz-tasks` outerHTML 대입) 하나**로 바꾼다 — 카드 수·순서·접힘이
  바뀌는 순간을 따로 처리하지 않는다(`#dz-impl-card` 통째 교체와 같은 근거). 나머지(`dz-updated`·구현 세부·로그·라디오·`<style>`·헤더)는 그대로. 대가 두 가지는 §8.1 R3·R4.
- 내 변경으로 고아가 되는 것만 지운다: `ANCHOR_TITLE`·`ANCHOR_PROGRESS_BAR`·`ANCHOR_PROGRESS_PCT`·`ANCHOR_STEPS_BLOCK`, `PublishedValues` 의 해당 4필드,
  `_latest_log_summary_html`, 템플릿의 `syncProgressBar`·`syncVisualization`. 매트릭스 CSS(`table.matrix`, T22-23)는 원래부터 생산자가 없는 죽은 코드라 **언급만 하고 두다**.

### MT8 — 상세 패널 CSS: 기존 토큰·관용구만 쓴다(새 색 토큰 0)

```css
  .badge.task{background:var(--soft);color:var(--head);border:1px solid var(--line)}      /* .badge.commit 과 같은 짝 — 결과 배지와 섞이지 않는 중립 */
  .task-card h1 .badge.task{vertical-align:3px}
  details.task-folded{padding:12px 30px}
  details.task-folded>summary{display:flex;align-items:center;gap:8px;cursor:pointer;list-style:none;font-size:14px;font-weight:700;color:var(--muted)}
  details.task-folded>summary::-webkit-details-marker{display:none}
  details.task-folded>summary::marker{content:""}
  details.task-folded>summary::before{content:"▸";flex:none;width:12px;color:var(--muted)}
  details.task-folded[open]>summary::before{content:"▾"}
  details.task-folded>summary:hover .task-folded-title{color:var(--head)}
  details.task-folded>summary .badge{margin-right:0}
  details.task-folded>summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:6px}
  .task-folded-title{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .task-folded-pct{flex:none;font-size:12px}
  body.dz-pip details.task-folded{display:none}                                              /* 플로팅 압축 보기는 진행 중 작업만 */
```
목업에서 550px 패널(라이트·다크)·420px 압축 보기·펼친 접힌 카드를 확인했다. `.entry summary` 의 마커 숨김(`::-webkit-details-marker`·`::marker`)과 같은 관용구다.

### MT9 — 왼쪽 카드 세션 줄: 안 A(권장) — 접히지 않은 작업마다 진행률 줄 1개

- 안 A: `tasks` 중 접히지 않은 것마다 「제목 — 완료/전체 · %」 한 줄(init 순). 접힌 작업은 카드에 없다(패널에서 본다). 작업이 하나면 오늘과 같은 한 줄.
  - 둘째 줄부터 `.tier1-pct+.tier1-pct{margin-top:2px}`(`.tier1-impl` 과 같은 간격). 트리 갈고리는 첫 줄에 맞으므로 T25-262 의 레일 기하가 그대로다(목업 확인).
  - `tasks` 가 없거나 비면(옛 서버 페이로드·손으로 만든 픽스처) `[tier1]` 로 폴백해 오늘의 한 줄을 그린다.
- 안 B(기각 후보, 목업에 나란히): 대표 작업 1줄 끝에 「· 외 N건」. 카드가 짧지만, 어느 작업이 대표인지는 화면에 안 보이는 규칙(MT5)이라 이번 사고(보이는 진행률이
  다른 작업 것)와 같은 종류의 오해를 다시 남긴다. 사용자 확인 항목 2.
- 함수: `renderTier1(tier1)`(시그니처·`renderSessionProgress` 의 `renderTier1(session.tier1)` 호출 그대로 — T25-255) 가 `visibleProgressTasks(tier1)` 를
  `renderTier1TaskLine(task)` 로 그린다. 줄 앞에 칩·배지를 두지 않는다(LM12·AW5 — 줄은 제목으로 시작한다, T25-263 을 새 줄 함수로 재조준).

### MT10 — 기록 규칙 문구(`hub/rules/dashboard-recording.md`) — +374B, T40-5 만

표 아래에 한 문단을 더하고 중단 문구에 괄호 하나를 붙인다(전문 실측본 `…/scratchpad/proposed-dashboard-recording.md`):

```
  동시에 작업을 둘 이상 하면 나중 작업마다 이름표를 정해 그 작업의 모든 호출에 서브커맨드 바로 뒤
  `--task '<이름표>'` 를 붙인다 — 그 `init` 은 기존 기록을 지우지 않고, 이름표 없는 호출은 첫 작업 몫이다.
  요약 한 줄에는 한 작업만 적는다.

  …(기존) 출력이 `OK` 가 아니면(`NOSESSION`·`DISABLED`·`NOINIT`…) 그 한 줄만 착수 보고에 남기고 이후 호출을 생략한다(`NOTASK` 는 그 이름표로 `init` 부터).
```

- 「요약 한 줄에는 한 작업만」 — 실사례 13:16·16:32 처럼 한 요약에 두 작업을 함께 쓰면 그 줄은 한 작업 카드에만 붙어 다른 작업의 진행이 빠진다. 두 작업이 같은 순간에 바뀌면
  기록도 두 번이다(사용자 승인 하나가 두 작업을 함께 승인하면 `log approve` 를 작업마다).
- 「(`NOTASK` 는 그 이름표로 `init` 부터)」 — 없으면 일반 규칙(「OK 가 아니면 이후 호출 생략」)이 이름표 오타 한 번으로 세션의 남은 기록을 전부 끈다.
- 바이트: **1415B → 1789B(+374B, 편집본 `wc -c` 실측)**. 이 파일은 허브 사용자 세션에 상시 로드되지만 **T26(상시 컨텍스트 예산) 밖**이고 T40-5 래칫만 받는다 —
  `HUB_DASHBOARD_RULE_BUDGET_BYTES` 를 1789 로 올리는 커밋에 이유를 남긴다(T40-5 주석 이력 관례). 예시 줄은 넣지 않는다(「서브커맨드 바로 뒤」가 위치를 정한다, −약 70B).
  T22-158a·T40-6·T33-1·T33-2·T33(G1) 토큰은 그대로 지켜진다(개정본에서 확인).

### MT11 — 하위 호환과 배포 순서

- 이름표 없는 JSONL(오늘까지의 모든 기록): 파서 결과 이벤트 열·상단 필드가 **오늘과 같다**(작업 1개, `tasks` 길이 1, 접힘 없음). 세션 줄 글자도 같다. 상세 패널은 마크업이
  바뀌지만(id 제거·`#dz-tasks` 래퍼) 보이는 모양은 같다 — 목업 「현재」 대조, 렌더 골든 테스트(§6.4)로 잠근다.
- 이름표 없는 기록기 호출이 쓰는 바이트는 오늘과 같다(MT2).
- 기록기·파서·렌더러·템플릿은 같은 허브 설치(`hub/install.sh`)로 함께 바뀐다. 다만 **이미 떠 있는 허브 서버**는 재시작 전까지 옛 파서를 쓴다 — 옛 파서는 `task` 필드를 모르고
  「마지막 init 이후만」 읽으므로 이름표 init 이 생긴 기록은 마지막 작업만 보인다(기록 자체는 온전하다). README 「코드를 고친 뒤 반영하는 절차」의 서버 재시작으로 풀린다 — 「알려진 한계」에 한 줄.

### MT12 — 문서 갱신

- `hub/README.md` — 「진행 기록」: 데이터 모델 표에 선택 필드 `task` 한 줄 · 새 소절 「동시 작업(이름표)」(MT1~MT5 를 사람 말로: 첫 작업 몫·이름표 init 은 덧붙임·같은 이름표는 재시작·
  무표 init 은 새로 시작·닫힘과 접힘·회차는 작업별) · 「헬퍼 스크립트」 표 인자 열에 `[--task '<이름표>']`, 출력 열에 `BADTASK`·`NOTASK`(폐쇄 어휘의 단일 출처 — G2).
  「프로젝트 상세 패널」: 작업마다 카드·접힌 카드·로그 항목 이름표. 상단 「진행률 줄」 항목(46행)과 「화면 배치」: 작업마다 한 줄. 「알려진 한계」: 이름표 잊으면 섞임 ·
  버려진 작업은 열린 카드로 남음(승인 단계였다면 승인 대기 표지도) · 접힌 카드를 펼쳐 둬도 내용이 바뀌는 갱신에서 다시 접힘 · 서버 재시작 전 옛 파서(MT11).
- `docs/prps/dashboard-rationale.md` 「폴링 동기화 계약」 표 — `#dz-title`·`#dz-progress-pct`·`#dz-progress-bar`·`#dz-steps,#dz-matrix` 세 행을 `#dz-tasks`(outerHTML) 한 행으로, 개정 표기.
- `docs/prps/dashboard-native-data-source.md` DN5 — 「회차 = 작업별 누적」 개정 표기 한 줄.
- 템플릿 머리 「DZ:DASHBOARD 갱신 맵」 주석 — 지운 id 4줄을 `#dz-tasks` 한 줄로(매트릭스 줄은 손대지 않는다).
- `README.md` 「설계·조사 문서 N개」 92 → 93(병합 직전 다시 센다). `commands/hub.md` 는 `switch` 만 다뤄 변경 없음.

### MT13 — 하지 않는 것(YAGNI)

- **「에이전트가 돌면 100% 막기」** — 사용자가 이번에 하지 않기로 했다.
- 첫 작업에 거슬러 이름표 붙이기 · 작업별 로그 필터·작업별 패널 주소 · 서브에이전트 실행 줄과 작업의 연결(호스트 기록에 이름표가 없다) · 작업 수 상한 ·
  접힌 카드 펼침 상태의 갱신 간 보존 · 진행 막대 슬라이드 애니메이션 보존(R3·R4) · 무표 init 이 열린 이름표 작업을 지우는 것을 막는 보호(§8.2 기각 D).

---

## 4. 영향 범위

### 4.1 코드

| 파일 | 변경 | 결정 |
|---|---|---|
| `hub/bin/hub_parse.py` ★순수 | `TASK_LABEL_MAX_LENGTH`·`is_valid_task_label` · `DashboardEvent.task` · `_parse_*` 의 `task` 검증 · `parse_event_lines` 개정(시작점·정규화·생존 — 함수 3개로 분할) · `live_task_labels` · `split_events_by_task` · `TaskProgress` · `task_progresses` · `snapshot_from_events` 집계 개정 · `Tier1Snapshot.tasks`. **주석에도 `open(`·`Path(`·`os.`·`time.` 를 쓰지 않는다(T25-10)**. 예상 358 → 약 490행 | MT1·MT3~MT6 |
| `hub/bin/hub_dashboard_log.py` | `_split_task_option` · `cmd_init(args)` 로 시그니처 변경(이름표 init 은 덧붙임) · `cmd_log`·`cmd_step` 에 BADTASK·NOTASK · 쓰는 줄에 `task` 키(이름표 있을 때만). 서브커맨드 4종·디스패치 분기 4개 그대로(T34-5). 예상 314 → 약 370행 | MT2 |
| `hub/bin/hub_dashboard_render.py` ★순수 | `ANCHOR_TASKS` · 앵커 4종·`PublishedValues` 4필드·`_latest_log_summary_html` 삭제 · `render_task_block_lines`·`_render_open_task_card`·`_render_folded_task_card`·`_render_steps_block(steps)` · `_LogEntryFields.task_label_html` · 회차 작업별 · `build_published_values` 가 `snapshot_from_events(events).tasks` 를 쓴다. 예상 419 → 약 450행 | MT4·MT7 |
| `hub/bin/hub_dashboard_template.html` | 첫 `.card` → `<div id="dz-tasks"></div>` · CSS 14줄(MT8) · `syncTasks` 로 교체·고아 함수 2개 삭제 · 머리 갱신 맵 주석 | MT7·MT8 |
| `hub/bin/hub_template.html` | `visibleProgressTasks`·`renderTier1TaskLine` · `renderTier1` 본문 · CSS 1규칙 · 머리 데이터 계약 주석에 `tier1.tasks` 한 구절 | MT9 |
| `hub/rules/dashboard-recording.md` | MT10 문단 + 괄호 | MT10 |

### 4.2 정적 가드와 원장 — 번호는 병합 직전 develop 을 다시 세어 겹치면 다시 매긴다

| ID | 종류 | 내용 |
|---|---|---|
| T22-2 개정 | 정 | 필수 셀렉터 `dz-title dz-progress-bar dz-progress-pct dz-step- dz-log dz-updated` → `dz-tasks task-card task-folded dz-log dz-updated` |
| T22-24 개정 | 정 | `<ol class="steps" id="dz-steps">`·`dz-step-{n}` → 렌더러에 `'<ol class="steps">'`·`class="card task-card"`·`<details class="card task-card task-folded">` |
| T22-53 개정 | 정 | `querySelector('#dz-steps,#dz-matrix')` → `syncTasks` 본문에 `getElementById('dz-tasks')` 와 `outerHTML` |
| T22-137 개정 | 정 | init 폐쇄 어휘 `OK`·`MKDIR-FAILED` + `BADTASK` |
| T22-139 개정 | 정 | 앵커 목록에서 제목·%·단계 3종을 빼고 `<div id="dz-tasks"></div>` 추가(정확히 1회) |
| T25-6 개정 | 정 | `id="dz-step-%d"` → `class="card task-card"`(열린 카드 생산자) |
| T25-263 개정 | 정 | 범위를 `function renderTier1TaskLine(task){` 로 옮기고 `tier1-pct">' + escapeHtml(task.title)` 로 시작함을 문다 |
| T25-281 ② 개정 | 역 | `renderTier1` 과 `renderTier1TaskLine` 두 본문 모두 `approval-wait`·`renderApprovalWaitBadge` 없음 |
| T34-6 개정 | 정 | 폐쇄 어휘 10 → 12종(`BADTASK`·`NOTASK`) |
| T34-7 신설 | 정(정합) | `--task` 가 「헬퍼 스크립트」 표·기록기(`"--task"` 리터럴)·규칙 파일 세 곳에 있다 — 규칙이 가르치는 옵션을 기록기가 받는다 |
| T22-177 신설 | 정 | 템플릿 CSS 에 `.badge.task{`·`details.task-folded>summary{`·`body.dz-pip details.task-folded{display:none}` 가 있고 `.badge.task{` 본문에 `#`(새 색 리터럴)이 없다 |
| T25-294 신설 | 정 | `visibleProgressTasks` 본문이 `is_folded` 를 읽고(서버 필드 개명에 눈멀지 않게 — 메모리 「개명하면 정적 가드가 눈이 먼다」) `.tier1-pct+.tier1-pct{` 규칙이 있다 |
| T40-5 상수 | 래칫 | `HUB_DASHBOARD_RULE_BUDGET_BYTES` 1415 → 1789(편집 후 재실측), 주석 이력 한 문단 |

- 원장(`tests/mutations.tsv`): 신설 3건 행 추가, T25-263 행의 sed 대상(`escapeHtml(tier1.title)` → `escapeHtml(task.title)`) 갱신, 「개정 시 변조행 승급」 표시가 있는
  T22-139·T25-6 은 그 관례대로 변조행으로 승급. `tests/run.sh` 머리 가드 수 이력 주석 갱신. 메시지는 반복문 밖 고정 문구(T25-263 관례).
- **무변경으로 통과해야 하는 것**: T22-158a·T40-6·T33·T25-255(`renderTier1(session.tier1)`·`function renderTier1(tier1){`)·T25-262(레일)·T25-10(★순수)·T34-3~5.

### 4.3 단위·계약·DOM 테스트

| 파일 | 변경 |
|---|---|
| `tests/hub/test_hub_parse_tasks.py` **신규** | §6.1 — `test_hub_parse.py`(665행)에 더하면 800행을 넘는다 |
| `tests/hub/test_hub_parse.py` | 무변경 통과(옛 기록 회귀선) — 「두 init 이면 마지막 이후만」 테스트도 무표 init 이라 그대로 맞다 |
| `tests/hub/test_hub_dashboard_log_tasks.py` **신규** | §6.2 — 기존 모듈은 이미 908행 |
| `tests/hub/test_hub_dashboard_render.py` | 개정분 갱신 — `dz-step-{n}` 정규식(286~296행)·`title_html`(305행)·`progress_text_html`/`progress_width`(340·341·355행)·렌더 결과의 `<h1 id="dz-title">`·`<li id="dz-step-…">`(390~427행)를 카드 블록 기준으로, 누적 회차 테스트(183행)를 「작업 하나일 때 누적」으로 이름·주석 정정 + §6.4 신규 클래스 |
| `tests/hub/test_hub_dashboard_log.py` | 미니 템플릿 상수(37~50행 — 앵커 원문을 문자 단위로 복제)를 6종 앵커로, `build_published_values` 테스트(356~365행 `progress_*`)를 카드 블록 기준으로. 새 테스트는 넣지 않는다(이미 908행) |
| `tests/hub/test_hub_dashboard_contract.py` | §6.3 `MultiTaskRoundTripTest` 1건 |
| `tests/hub/test_hub_server.py` | 282·301행 단언 `<h1 id="dz-title">…</h1>` → `<h1>…</h1>`(서빙 경로·서로게이트 치환 검사의 대상 문자열만 바뀐다) |
| `tests/hub/test_hub_template_dom_session_row.py` | D53·D54(§6.5) |

### 4.4 문서 — MT12 그대로.

---

## 5. 데이터 모델 · 인터페이스

### 5.1 `hub/bin/hub_parse.py`(★순수)

```python
TASK_LABEL_MAX_LENGTH = 20  # 이름표 글자 수 상한(결정 MT1) — 기록기가 재사용한다(HD14)


def is_valid_task_label(label: str) -> bool:
    """이름표 형식 — 1~TASK_LABEL_MAX_LENGTH 자, 앞뒤 공백 없음, 인쇄 가능한 문자만(MT1)."""


@dataclass(frozen=True)
class DashboardEvent:
    ...                      # 기존 필드 그대로
    task: str = ""           # 이름표. parse_event_lines 가 무표를 첫 작업 이름표로 채운다(MT3) — 첫 작업이 무표면 "" 그대로


@dataclass(frozen=True)
class TaskProgress:
    """진행 기록 안 작업 하나의 진행 상태(결정 MT4·MT5)."""

    label: str                       # "" = 이름표 없는 첫 작업
    title: str
    completed: int
    total: int
    percent: int
    steps: tuple[StepView, ...]      # 진행중 단계 detail = 그 작업의 마지막 로그 요약
    started_at_ms: int               # 그 작업의 (마지막) init 시각
    is_committed: bool               # 마지막 pass 뒤 commit
    is_approval_step_active: bool
    is_folded: bool                  # 닫힘(100% ∧ 커밋) ∧ 대표 아님


@dataclass(frozen=True)
class Tier1Snapshot:
    ...                                    # 기존 필드 그대로 — 의미는 MT6 표
    tasks: tuple[TaskProgress, ...] = ()   # 표시 순서(펼침 init 순 → 접힘 init 순). 파서는 항상 1개 이상 채운다


def parse_event_lines(text: str) -> tuple[DashboardEvent, ...]:
    """JSONL → 살아 있는 이벤트 열(MT3: 마지막 무표 init 부터, 무표는 첫 작업 몫, 재시작·고아 제거). init 없으면 ()."""


def live_task_labels(events: tuple[DashboardEvent, ...]) -> frozenset[str]:
    """살아 있는 작업들의 이름표 집합 — 기록기의 NOTASK 판정(MT2)."""


def split_events_by_task(events: tuple[DashboardEvent, ...]) -> tuple[tuple[DashboardEvent, ...], ...]:
    """살아 있는 열 → 작업별 묶음(init 순, 묶음[0] 은 그 작업의 init)."""


def task_progresses(events: tuple[DashboardEvent, ...]) -> tuple[TaskProgress, ...]:
    """작업별 진행(표시 순서, is_folded 채움 — MT5)."""


def snapshot_from_events(events: tuple[DashboardEvent, ...]) -> Tier1Snapshot:
    """이벤트 열 → Tier1Snapshot(상단 필드는 MT6 집계, tasks 는 task_progresses)."""
```

내부 도우미(이름은 구현 재량, 50줄 규칙): 시작점 자르기 · 무표 정규화 · 생존 거르기 · 작업 하나의 진행 계산 · 대표 고르기(후보 풀 3단 + 마지막 생존 이벤트 위치) ·
상단 `task_started_at_ms` 집계. 대표 작업은 공개 모델에 싣지 않는다(읽는 곳이 `snapshot_from_events` 뿐이다).

### 5.2 `hub/bin/hub_dashboard_log.py`(I/O 층)

```python
_TASK_OPTION = "--task"


def _split_task_option(args: list[str]) -> tuple[str | None, list[str]] | None:
    """맨 앞 `--task <이름표>` 를 떼어 (앞뒤 공백 걷은 이름표, 나머지). 옵션이 없으면 (None, args). 형식 위반·값 없음·`--task=…` 이면 None(BADTASK)."""


def cmd_init(args: list[str]) -> None: ...   # 이름표 없으면 지금처럼 새로 쓰기, 있으면 덧붙이기(파일 없으면 생성)
def cmd_log(args: list[str]) -> None: ...    # MT2 순서표
def cmd_step(args: list[str]) -> None: ...
```

### 5.3 `hub/bin/hub_dashboard_render.py`(★순수)

```python
ANCHOR_TASKS = '  <div id="dz-tasks"></div>'


@dataclass(frozen=True)
class PublishedValues:
    project_name_html: str | None
    task_block_lines: list[str]      # <div id="dz-tasks"> … </div> 전체(이미 이스케이프)
    impl_count_html: str | None
    impl_block_lines: list[str] | None
    log_owner_token: str
    log_server_port: str
    log_entry_lines: list[str]
    updated_html: str


def render_task_block_lines(tasks: tuple[TaskProgress, ...]) -> list[str]:
    """작업 카드 묶음 — 펼친 카드는 .card.task-card, 접힌 카드는 details.card.task-card.task-folded(MT7)."""


def render_log_entry_lines(events: tuple[DashboardEvent, ...]) -> list[str]:
    """최신이 위. data-seq 1부터, 최신 3건만 <details open>. 이름표 배지, pass/fail 에 작업별 회차 R{n}."""
```

### 5.4 `hub/bin/hub_template.html`(렌더 IIFE)

```js
  // 세션 줄에 보일 작업(결정 MT9) — 접히지 않은 작업, 서버가 준 표시 순서 그대로. tasks 가 없거나 비면 tier1 자신 하나(옛 페이로드).
  function visibleProgressTasks(tier1){ … }
  // 작업 하나의 진행률 줄 — 제목으로 시작한다(LM12·AW5).
  function renderTier1TaskLine(task){
    return '<div class="tier1-pct">' + escapeHtml(task.title) + ' — '
      + task.completed + '/' + task.total + ' · ' + task.percent + '%</div>';
  }
  function renderTier1(tier1){
    return visibleProgressTasks(tier1).map(renderTier1TaskLine).join('') + renderTier1ImplProgress(tier1);
  }
```
CSS: `.tier1-pct+.tier1-pct{margin-top:2px}`.

---

## 6. 테스트 계획

### 6.1 순수 로직 — `tests/hub/test_hub_parse_tasks.py`

- `is_valid_task_label`: 「결함①」·「9회차」·가운데 공백 참 / `""`·21자·앞뒤 공백·`\n`·`\t`·U+2028 거짓 / 정확히 20자 참.
- 줄 파싱: `task` 가 숫자·리스트·형식 위반이면 그 줄만 버린다, `""` 는 무표, 키 없음은 무표.
- `parse_event_lines`: (a) 무표 init 만 있는 옛 기록 → 오늘과 같은 열(모든 `task == ""`) (b) 무표 init 뒤 이름표 init → 둘 다 남는다 (c) 이름표 작업 뒤 무표 init → 앞의 이름표 작업이 사라진다 (d) 첫 줄이 이름표 init 이면 무표 log 가 그 이름표로 정규화된다 (e) 같은 이름표 재 init → 그 작업 옛 이벤트만 빠지고 다른 작업은 그대로 (f) init 전 이름표 log(고아) 제거 (g) 결과 `events[0].kind == "init"`.
- `split_events_by_task`·`task_progresses`: 작업별 단계 상태 — 한 작업의 `pass` 가 다른 작업의 단계를 바꾸지 않는다(이번 사고의 회귀 테스트, 실사례 순서를 이름표로 재구성한 픽스처 = 목업 생성기의 `LABELED`) · 진행중 단계 detail 은 그 작업의 마지막 요약.
- 대표·접힘(MT5): 미완 둘이면 더 최근 기록된 것 · 승인 진행중 작업이 더 오래됐어도 대표 · 모두 끝나면 가장 최근 · 닫힌 비대표만 접힘 · 작업 하나면 커밋 뒤에도 안 접힘 · commit 뒤 `fail` 이면 펼침 · 표시 순서(펼침 init 순 → 접힘 init 순).
- `snapshot_from_events` 집계(MT6): `percent` = 100 ⇔ 모든 작업 끝남 · `is_approval_step_active` = any · `title` = 대표 · `task_started_at_ms` = 가장 이른 미완 시작(다 끝나면 대표 시작) · 옛 기록은 `tasks` 길이 1이고 상단 필드가 개정 전 구현의 값과 같다(골든 — 개정 전 커밋에서 뽑은 값을 리터럴로 고정).
- 소비자 연결(코드 무변경 확인): 두 작업 스냅샷으로 `hub_session.previous_task_boundary_ms` 가 먼저 시작한 미완 작업 시각을 돌려준다 · `is_session_tier1_from_finished_task` 가 한 작업만 끝났을 때 거짓.

### 6.2 기록기 — `tests/hub/test_hub_dashboard_log_tasks.py`(샌드박스 cwd·HOME — 기존 모듈과 같은 준비)

- `init --task X` 가 기존 기록을 보존하고 한 줄 덧붙인다 · 파일이 없으면 만든다 · 무표 `init` 은 여전히 새로 쓴다(이름표 작업까지 지운다).
- `log --task X` 는 `"task": "X"` 를 쓴다 · 무표 `log` 는 `task` 키 없이 오늘과 같은 바이트를 쓴다.
- BADTASK: `--task` 뒤 값 없음 · `''` · 21자 · 개행 · `--task=결함①`(init 에서 **파일이 그대로인지**도 확인 — 지우는 사고의 회귀 테스트) — 어느 경우든 파일 불변.
- NOTASK: 없는 이름표의 `log`·`step` · 재 init 으로 사라진 이름표 아님(재시작 뒤에도 살아 있다) · 무표 init 으로 지워진 이름표는 NOTASK.
- 순서: 파일 없음 + 형식 위반 이름표 → BADTASK(NOINIT 보다 앞) · 파일 없음 + 정상 이름표 → NOINIT · 잘못된 kind + 없는 이름표 → BADKIND.
- 무표 `log` 는 이름표 작업만 있는 파일에서도 OK(NOTASK 를 내지 않는다).

### 6.3 계약 왕복 — `tests/hub/test_hub_dashboard_contract.py`

`MultiTaskRoundTripTest`: 기록기 실제 호출 `init '첫' '설계|승인|구현|검수'` → `init --task B 'B' '구현|검수'` → `log --task B impl` → `log pass`(무표) → `log commit` →
`hub_collect.read_session_dashboard_snapshots` 결과: `tasks` 2개, 표시 순서 [B, 첫], 첫 작업 접힘, 상단 `percent` = B 의 50, `title` = 'B'.

### 6.4 렌더 — `tests/hub/test_hub_dashboard_render.py`

- 옛 기록 골든: 무표 작업 1개 → `#dz-tasks` 안 카드 1장, `details` 0개, `badge task` 0개, 단계 줄의 클래스·글자가 개정 전과 같다.
- 다중: 카드 순서 · 접힌 카드 마크업(§MT7 그대로) · 이름표 이스케이프(`<`·`&`) · 로그 항목 이름표 배지 위치(시각 뒤·회차 앞) · 회차 작업별(R1·R1·R2) · 무표 항목 배지 없음.
- `render_reissue`: 앵커 6종 각 1회, 하나라도 2회·0회면 `AnchorMismatch`(기존 테스트 개정).

### 6.5 화면 — `tests/hub/test_hub_template_dom_session_row.py`(헤드리스 Chrome, 없으면 SKIP)

- D53: `tier1.tasks` 에 펼친 2개 + 접힌 1개 → 세션 줄 `.tier1-pct` 2개, 글자가 표시 순서대로 「제목 — c/t · p%」, 접힌 작업 제목은 줄에 없다.
- D54: `tasks` 가 빈 옛 픽스처 → `.tier1-pct` 1개, 글자가 오늘과 같다(D27 의 기존 단언과 같은 문자열).

### 6.6 일부러 깨뜨려 실패를 확인한다(구현 단계 — 결과를 구현 보고에 적는다)

대표 후보 풀에서 ①(승인 진행중)을 빼기 · 생존 규칙의 `≤` 를 `<` 로 · 접힘에서 「대표 아님」 빼기 · `task_started_at_ms` 를 대표 시작으로 · 기록기에서 `--task=` 거절 빼기 ·
무표 log 에 NOTASK 내기 · `visibleProgressTasks` 의 접힘 필터 빼기 — 각각 위 테스트 중 하나 이상이 실패해야 한다.

---

## 7. 마일스톤

| M | 내용 | 결정 | 검사 |
|---|---|---|---|
| M1 | 파서 — 이름표·살아 있는 열·작업별 진행·대표·접힘·집계 | MT1·MT3~MT6 | §6.1 · 기존 `test_hub_parse` 무변경 통과 |
| M2 | 기록기 — `--task`·init 덧붙이기·BADTASK·NOTASK | MT2 | §6.2 · §6.3 · T34-6·7 · T22-137 |
| M3 | 상세 패널 — 렌더러·템플릿·CSS·폴링 | MT7·MT8 | §6.4 · T22-2·24·53·139·177 · T25-6 |
| M4 | 왼쪽 카드 — JS·CSS | MT9 | §6.5 · T25-263·281·294 · T25-255·262 무변경 |
| M5 | 규칙 문구·문서 | MT10·MT12 | T40-5·T40-6·T22-158a·T33 |

M1 만으로는 화면이 바뀌지 않는다(옛 기록은 같은 값, 이름표를 쓸 기록기도 아직 없다). M2~M4 는 M1 에 의존한다. M5 는 M2 와 같은 커밋 묶음이어야 한다 — 규칙이 먼저 배포되면 기록기가
`--task` 를 BADKIND 로 거절한다.

---

## 8. 위험과 대안

### 8.1 위험

- **R1 이름표를 잊으면 섞인다** — 사용자가 수용한 대가다. 이름표 없는 기록은 첫 작업에 붙으므로 결과는 오늘과 같은 섞임이고, 더 나빠지지 않는다.
- **R2 버려진 작업이 열린 채 남는다** — 커밋 없이 그만둔 작업은 접히지 않고 그 단계에 머문다. 그 작업이 「승인」 진행중이었다면 세션이 대기일 때마다 `◆ 승인 대기` 표지·알림이
  계속 뜬다(오늘의 「`log approve` 누락」 한계가 작업 범위로 옮겨 온 것 — 지금은 아무 작업의 `log impl` 이 승인을 끝내 줬지만, 이제는 그 작업의 기록만 끝낸다). 실사례의 「우산 작업」
  모양(착수 init 하나 아래 하위 작업들)에서 특히 생길 수 있다. 대응: 규칙의 「요약 한 줄에는 한 작업만」이 승인을 작업마다 기록하게 하고, 끝나지 않을 작업은 다음 무표 init(새 시작)으로
  정리된다. 「알려진 한계」에 적는다. 막는 장치(오래 기록 없는 작업 제외 등)는 임계값을 지어내야 해 넣지 않는다 — 실제로 잦으면 그때 본다.
- **R3 진행 막대가 미끄러지지 않고 바뀐다** — `#dz-tasks` 통째 교체라 `.bar-inner` 의 `transition:width .4s` 가 갱신 때 동작하지 않는다(새 요소). 갱신은 길어야 1분에 한 번이다.
- **R4 펼쳐 둔 접힌 카드가 갱신에서 다시 접힌다** — 문서 문자열이 바뀐 폴링에서만(같으면 아무것도 안 한다). 로그 항목 `<details>` 가 이미 같은 거동이다.
- **R5 접힌 작업 수 상한 없음** — 이름표 작업을 순차로 수십 개 쓰는 긴 세션이면 접힌 줄이 쌓인다(줄당 약 46px). 무표 init·7일 리텐션이 끊는다. 실제로 길어지면 「끝난 작업 N건」 묶음으로 접는다.
- **R6 떠 있는 서버의 옛 파서**(MT11) — 재시작 전까지 이름표 기록은 마지막 작업만 보인다. 허브 갱신 절차가 재시작을 포함한다.
- **R7 무표 init 이 진행 중인 이름표 작업을 지운다** — 첫 작업을 끝낸 세션이 다른 작업이 아직 도는데 새 작업을 무표 `init` 으로 시작하면 그 작업 기록이 사라진다(오늘 동작과 같다).
  규칙 문구 「동시에 … 나중 작업마다 이름표」가 이 경우를 덮는다. 기록기 보호는 §8.2 D.
- **범위 밖 관찰(언급만)**: 한 작업 안에서 구현 단계마다 `log impl` 을 남기면(실사례 9회차의 단계 1·2a·2b) 「구현 완료 → 검수 진행중」으로 읽혀, 단계 3 을 구현하는 중에도
  3/4 · 75%·검수 진행중으로 보인다. 위치 전이 규칙(DN4)의 성질이라 이번 변경과 무관하다 — 다룰지는 별도 결정이다.

### 8.2 검토했으나 채택하지 않은 대안

- **A — `Tier1Snapshot` 을 작업 목록으로 바꾸고 소비자를 하나씩 고친다**(`tier1: tuple[TaskProgress, …]`): 의미가 가장 명시적이다. 기각 — `hub_session`(경계·끝난 작업·승인)·
  `hub_notify`·`hub_project`·`hub_model`·템플릿 다섯 곳과 그 테스트가 모두 흔들린다. MT6 처럼 상단 필드의 뜻을 「세션의 작업들에 대한 질문」으로 정의하면 소비자의 질문이 그대로
  성립해 코드가 0줄 바뀐다. 그 정의는 `snapshot_from_events` 한 곳에 있고 표로 문서화된다.
- **B — 상세 패널 첫 카드는 지금 id 앵커 그대로, 나머지 작업만 새 컨테이너에**: 가드·테스트 개정이 적다. 기각 — 같은 카드를 두 경로가 그려 어긋나기 쉽고(DRY), 첫 카드 제목은
  textContent 동기화라 이름표 배지를 넣을 수 없으며, 대표가 바뀌면 첫 카드 내용이 다른 작업으로 통째로 바뀌어 자리가 뛴다.
- **C — 없는 이름표의 log 가 작업을 암묵 생성**(제목 = 이름표, 단계 = 직전 init 것): init 을 잊어도 기록된다. 기각 — 오타 이름표가 유령 카드를 영구히 만든다. 대신 NOTASK +
  규칙 괄호 하나로 회복 경로를 준다.
- **D — 무표 init 이 열린 이름표 작업이 있으면 거절(새 어휘)**: R7 을 막는다. 기각(지금은) — 순차 작업의 오늘 동작(무표 init = 새로 시작)을 바꾸고 어휘·규칙 바이트가 는다.
  R7 이 실제로 보고되면 다시 본다.
- **E — 작업마다 기록 파일을 따로**(`<세션ID>.<이름표>.jsonl`): 파일 단위 재시작이 쉽다. 기각 — 세션 ↔ 파일 1:1 이 대시보드 키·세션 판정·리텐션·파일명 정규식(ST9) 전부의 전제다.
- **F — 이름표 인자를 `log impl@결함① …` 처럼 종류에 붙이기**: 짧다. 기각 — `init`·`step` 에는 붙일 자리가 없고, 종류 검사(BADKIND)와 이름표 검사가 한 토큰에 엉킨다.

---

## 9. 사용자 확인 항목 (쉬운 말)

1. **기록 방법** — 한 세션이 작업을 둘 이상 동시에 하면, 나중에 시작한 작업의 기록마다 `--task '결함①'` 같은 짧은 이름표를 붙입니다. 처음 작업은 이름표 없이 그대로 둬도 됩니다.
   이름표를 붙인 시작 기록은 앞 작업 기록을 지우지 않습니다. 한 기록 줄에는 한 작업 이야기만 씁니다.
   **승인하면**: 기록 규칙 파일에 세 줄이 더해져 모든 세션이 이 방법을 따르고(파일 크기 1415 → 1789바이트), 이름표를 잊은 기록은 지금처럼 처음 작업에 섞입니다.
2. **왼쪽 카드 표시(안 A)** — 세션 줄의 진행률을 작업마다 한 줄씩 보입니다(접힌 작업은 빼고). 다른 안은 대표 작업 한 줄 끝에 「· 외 1건」만 붙이는 것입니다(안 B, 더 짧지만 어느
   작업이 대표인지는 화면에 안 보입니다). 목업 「왼쪽 카드 세션 줄」 절에 셋이 나란히 있습니다.
   **승인하면**: 두 작업이 동시에 돌면 카드에 「9회차 … — 3/4 · 75%」와 「결함 ① … — 1/2 · 50%」가 위아래로 보입니다.
3. **상세 패널** — 작업마다 진행 카드를 따로 그리고, 작업 추적 목록은 하나로 두되 항목마다 이름표와 그 작업 안의 회차(R1, R2)를 붙입니다. 커밋까지 끝난 작업은 맨 아래 한 줄로 접히고,
   눌러서 펼칠 수 있습니다. 작업이 모두 끝나면 가장 최근 작업 카드는 펼쳐 둡니다.
   **승인하면**: 이번 사례에서 결함 ①이 커밋된 순간 결함 ① 카드만 접히고 9회차 카드는 75% 그대로 남습니다(지금은 기록 전체가 100% 가 됐습니다).
4. **이름표 없는 시작 기록은 지금처럼 「새로 시작」** — 이름표 없이 시작 기록을 다시 부르면 이름표 작업까지 포함해 그 세션 기록이 새로 시작됩니다(오늘과 같은 동작). 그래서 다른 작업이
   아직 진행 중이면 새 작업은 꼭 이름표로 시작해야 합니다.
   **승인하면**: 한 작업씩 차례로 하는 세션의 기록 방식은 하나도 바뀌지 않습니다.
5. **끝내지 않고 그만둔 작업은 열린 채 남습니다** — 커밋 기록이 없으면 접히지 않고, 그 작업이 승인 단계에서 멈췄다면 승인 대기 표지와 알림도 계속 뜰 수 있습니다. 세션 기록을 새로
   시작하면 사라집니다. 자동으로 치우는 장치는 넣지 않았습니다(얼마나 오래면 버린 것인지 기준을 지어내야 해서).
   **승인하면**: 이 한계가 허브 안내 문서 「알려진 한계」에 적힙니다.
