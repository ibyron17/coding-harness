# 허브: 살아있는 세션의 권위 출처를 호스트 명부로 옮긴다

> 산출: `docs/prps/hub-live-session-native-source.md` · 설계 모델: opus(승격 기준 미해당 —
> 데이터 모델 전면 개편도, 3개 이상 서브시스템 횡단도 아니다. 상태 판정 1개 지점의 입력을
> 바꾼다)

## 0. 요구사항 요약

사용자 요구는 **"클로드가 세션 진행 시 기본으로 생성하는 파일·데이터가 있으면, 허브가 굳이
새 데이터를 만들지 말고 그것을 쓰게 하라"** 이고, 승인된 범위는 그중 **살아있는 세션만**이다:
`~/.claude/sessions/<pid>.json`(호스트 소유 「살아있는 세션 명부」)을 **살아있는 세션의 권위
출처**로 삼고, 훅은 **갱신 트리거 + 끝난 세션 이력용으로 그대로 남긴다.**

허브는 오늘 "이 세션이 지금 일하고 있는가"를 훅 이벤트(`UserPromptSubmit`↔`Stop`)로 접은
`SessionFacts.turn_state` 로 판정한다. 호스트는 같은 사실을 자기 명부의 `status`
(`busy`↔`idle`)로 이미 적고 있고, 게다가 훅에 없는 사실 하나를 더 준다 — **레코드의 존재
자체가 "이 세션의 프로세스가 살아 있다"** 는 증거다. 이 설계는 그 중복 한 쌍(`turn_state` ↔
`status`)을 호스트 쪽으로 넘기고, 훅만으로는 알 수 없던 "프로세스가 죽었다"를 새로 쓴다.

**이 설계가 고치는 실제 증상 3가지**

| 증상 | 오늘 | 이 설계 이후 |
|---|---|---|
| 세션이 죽었는데 카드가 `작업중` 으로 남는다(훅 `Stop` 유실·허브 off 구간·크래시) | 최대 30분 뒤 `소식 없음` 으로 덮임 | 다음 수집에서 곧바로 `대기` |
| 세션이 살아 있는데 카드가 `완료` 다(`SessionEnd` 뒤 재부착 이벤트를 놓쳤다) | `done` 고착(터미널 표시라 `stale` 로도 안 덮임) | 명부에 있으면 `done` 취소 |
| 허브가 꺼진 동안 턴이 끝났다 | `turn_state` 가 `running` 인 채 남음 | 호스트 `status` 가 이김 |

---

## 1. 실측 (설계 근거, 2026-09-17 재확인)

### 1.1 명부의 모양

`~/.claude/sessions/` 에는 `<pid>.json` 과 `<pid>.<sha256>.key` 가 공존한다. **`*.json` 만
대상이고 `.key` 는 읽지도 건드리지도 않는다**(8월자 잔존 다수 — 두 파일의 생명주기가 다르다).

레코드 1건(이 설계를 만든 세션 자신):

```json
{"pid":64395,"sessionId":"768e8a38-ef92-4a4b-a356-e96efbcc80f2",
 "cwd":"/Users/dev/private/project/coding-harness","startedAt":1789535361067,
 "procStart":"Wed Sep 16 05:09:20 2026","version":"2.1.271","kind":"interactive",
 "entrypoint":"claude-desktop","messagingSocketPath":"/tmp/cc-socks/64395.sock",
 "name":"coding-harness-1a","status":"busy","updatedAt":1789603498032,
 "statusUpdatedAt":1789603498032,"bridgeSessionId":"session_01CMBEAUPkzHuvGDCYMbbR3q"}
```

키 출현율(10건 전수, 메인 세션 감사): `pid`·`sessionId`·`cwd`·`startedAt`·`kind`·`entrypoint`
**10/10**, `status`·`updatedAt`·`statusUpdatedAt` 등 **9/10**, `nameSource` 7/10,
`bridgeSessionId` 4/10. → **`status` 는 100% 가 아니다(실측 90%).**

### 1.2 이 설계를 바꾼 3개의 실측

**(가) `updatedAt` 은 하트비트가 아니다.** 측정 시점에 `status:"busy"` 인 세션 2개의
`updatedAt` 나이가 각각 **208초·248초**였다(둘 다 그 순간 실제로 턴이 돌고 있었다). 즉
호스트는 **상태가 바뀔 때만** 레코드를 다시 쓴다.

- 귀결 1: `updatedAt`·`statusUpdatedAt` 을 **신선도(liveness) 판정에 쓸 수 없다** — 살아 있는
  idle 세션의 `updatedAt` 이 42시간 전인 경우가 실측 4건이다.
- 귀결 2: 결정 D2(`snapshot_content_key`) 노출이 애초에 없다 — 이 값들을 뷰에 싣지 않기로
  했으므로(결정 LS10) 그 위험은 구조적으로 성립하지 않는다.

**(나) 레코드 부재 ⇔ 세션 종료 (12/12).** 훅 이벤트 창(오늘+어제)에 있는 세션 17개 중
레코드가 없는 12개는 **전부 `SessionEnd` 를 관측한 세션**이었다. 반례 0건. 반대로 레코드가
있는 9개는 `os.kill(pid, 0)` 로 **9/9 전부 프로세스 생존**이었다.

**(다) 명부에만 있고 훅 창에는 없는 세션이 4개(9개 중 44%).** 전부 `claude-vscode`
entrypoint, `status:"idle"`, 40시간 이상 아무 일도 하지 않은 세션이다. → 결정 LS1(새 카드를
만들지 않는다)의 직접 근거.

### 1.3 PID 재사용

`procStart` 는 UTC 로 렌더된 ctime 문자열이고 `ps -o lstart=` 는 로컬 시각이다(실측 9시간
차). 표준 라이브러리만으로 프로세스 시작 시각을 얻을 수 없어 **PID 재사용을 검증할 수단이
없다**(psutil 금지 — `hub/` 는 stdlib 전용). `hub_daemon.py` 는 `ps -o args=` 로 신원을
확인하지만 그것은 `/hub stop` 의 1회성 경로이고, 여기는 수집 사이클마다 도는 경로다(예산
50ms). → 결정 LS8(검증하지 않고 수용, 상한을 명시).

---

## 2. 비목표 (명시적으로 하지 않는 것)

| # | 하지 않는 것 | 이유 |
|---|---|---|
| N1 | 훅 이벤트 로그 폐지 | 사용자가 기각. 훅은 갱신 트리거이자 **끝난 세션의 유일한 이력**이다(명부는 종료 즉시 사라진다) |
| N2 | 서브에이전트 읽기를 glob 으로 전환(결정 AR3 뒤집기) | 사용자가 기각. 이번 범위 밖 |
| N3 | 사용량·한도(`rate_limits.json`) 손대기 | 호스트가 파일로 남기지 않는다. statusLine stdin 이 유일한 경로(결정 P1) |
| N4 | 프로젝트 대시보드(진행 단계·작업 추적) 손대기 | 메인 세션의 판단이라 호스트가 만들 수 없다 |
| N5 | 명부만 있는 세션을 새 카드로 띄우기 | 결정 LS1 |
| N6 | `name`·`entrypoint`·`version`·`cwd` 등 새 정보를 화면에 싣기 | 결정 LS10(YAGNI — 요구는 "중복 생성 중단"이지 "정보 추가"가 아니다) |
| N7 | `stale` 오버레이를 호스트 신호로 바꾸기 | 결정 LS9 — 그것이 명부 오판의 **유일한 독립 상한**이다 |

---

## 3. 영향 범위

| 파일 | 조치 | 이유 |
|---|---|---|
| `hub/bin/hub_live_session.py` | **신설(★순수)** | 호스트 레코드 계약(파싱·접기·판정값 변환). 외부 계약은 모듈 하나에 가둔다(AR2 선례) |
| `hub/bin/hub_live_session_read.py` | **신설(I/O)** | 디렉터리 열거·읽기·PID 생존. `hub_subagent_read.py` 와 동형 |
| `hub/bin/hub_session.py` | 수정 | `_compute_base_state` 에 화해 표(결정 LS5) · `compute_session_view` 에 `live_roster` 인자 |
| `hub/bin/hub_project.py` | 수정 | `compose_project_views`→`_project_view_for_path`→`_session_views_for_path` 로 `live_roster` 전달(판단 0, 배선만) |
| `hub/bin/hub_collect.py` | 수정 | `SESSIONS_DIR` 상수 1개 · `_read_session_annotations` 가 명부 읽기를 4번째 항목으로 포함 |
| `hub/bin/hub_template.html` | **변경 없음** | 결정 LS10 |
| `hub/install.sh` | 수정 | `HUB_FILE_COUNT` 23 → **25** |
| `hub/README.md` | 수정 | 「파일 배치」 "23개 파일" → "25개 파일" + 모듈 표에 2개 추가 |
| `docs/prps/hub-dashboard.md` | 수정 | 모듈 구성표에 2개 추가(T25-104 가 이 표의 존재를 문다) |
| `tests/hub/test_hub_live_session.py` | 신설 | ★순수 단위(진리표) |
| `tests/hub/test_hub_live_session_read.py` | 신설 | I/O 단위(임시 디렉터리) |
| `tests/hub/test_hub_session.py` | 수정 | 화해 진리표 15케이스 + 회귀 방어 |
| `tests/hub/test_hub_collect.py` | 수정 | 배선 1케이스(end-to-end) |
| `tests/run.sh` | 수정 | T25-10 목록 편입 · T25-149 파일 수 · T25-213~217 신설 |
| `tests/mutations.tsv` | 수정 | 신설 정적 가드마다 변조행 1개 |

**건드리지 않는 것**: `hub_model.py`(스냅샷 계약 불변) · `hub_server.py` · `hub_daemon.py` ·
`hub_hook.py`(훅은 그대로) · `hub_config.py`(새 설정 없음, 결정 LS12).

---

## 4. 필독 파일 (구현 전)

| 우선 | 파일 | 무엇을 |
|---|---|---|
| P0 | `hub/bin/hub_session.py` | `SessionFacts`·`SessionView`·`_compute_base_state`·`compute_session_view` 전부. 특히 `SessionView` 의 D2 주석 |
| P0 | `hub/bin/hub_subagent_read.py` | **이번 I/O 모듈의 본보기** — 2단 가드·`errors="replace"`·경고 반환 계약 |
| P0 | `hub/bin/hub_subagent.py` 머리 | ★순수 선언 + 계약 A 서술 형식 |
| P1 | `hub/bin/hub_collect.py` 의 `_tier3_activity_by_encoded_name` | 2단 OSError 가드(검수 R3-m1)의 정본 |
| P1 | `docs/prps/hub-session-revival-and-stale-tier1.md` 결정 RV1~RV3 | `done` 의 의미와 부활 규칙 |
| P1 | `docs/prps/hub-agent-runs-and-prompt-source.md` 결정 AR1·AR2·AR7 | 이번에 부분 번복하는 대상 |
| P2 | `tests/run.sh` T25-10·T25-149·T25-205 | 새 모듈이 통과해야 할 정적 검사 형식 |
| P2 | `tests/mutations.tsv` 헤더(8열 규약) | 신설 가드의 변조행 형식 |

---

## 5. 설계 결정

### LS1. 명부는 **기존 세션을 교정**할 뿐, 새 세션 카드를 만들지 않는다

명부에만 있고 훅 창에 없는 세션이 실측 4/9(44%)다 — 전부 40시간 이상 조용한 VS Code 세션.
이들을 카드로 띄우면:

- `last_event_at_ms` 가 없다 → 배지·경과·정렬·프로젝트 `last_activity_at_ms` 에 쓸 값이 없어
  **합성값을 지어내야 한다**(`updatedAt` 은 실측 42시간 전이라 쓰면 곧장 `소식 없음` 이 된다).
- `task_excerpt`·`agent_runs`·`workflow`·대시보드가 전부 비어 "거의 아무것도 말하지 않는 카드"가
  프로젝트마다 늘어난다.
- 게다가 이들은 훅 창(오늘+어제)에 이벤트가 **0건**이라는 뜻이고, 그것은 정의상 "이틀간 아무
  일도 하지 않았다" 이다 — 보여 줄 값이 낮다.

→ **명부는 허브가 이미 아는 `session_id` 에만 작용한다.** 재방문 트리거: 사용자가 "지금 열려
있는 세션 전부를 보고 싶다"고 요구하면, 이 설계가 만든 파서·리더가 그대로 그 기능의 입력이
된다(추가 비용은 카드 조립뿐).

### LS2. 모듈 배치 — ★순수 파서 + I/O 위성 **한 쌍 신설**, 화해 판정은 `hub_session.py` 에 둔다

| 무엇 | 어디 | 근거 |
|---|---|---|
| 호스트 레코드 **형식** 해석 | `hub_live_session.py`(★순수, 신설) | "외부 계약은 모듈 하나에 가둔다"(AR2·hub_transcript·hub_workflow·hub_subagent 3연속 선례). 호스트가 형식을 바꾸면 이 파일만 고친다 |
| 디렉터리 열거·파일 읽기·**PID 생존** | `hub_live_session_read.py`(I/O, 신설) | ★순수 모듈은 `os.` 를 임포트할 수 없다(T25-10) — `os.kill` 이 여기 있어야 할 물리적 이유다 |
| **화해 판정**(무엇이 이기는가) | `hub_session.py`(기존 ★순수) | 상태 판정 사다리가 한 파일에 있어야 한다 |

세 번째 줄이 이 결정의 핵심이다. 화해를 별도 모듈로 빼면 `_compute_base_state` 를 읽는 사람이
**자기가 읽는 함수의 결론이 하류에서 뒤집힌다는 것을 모른다** — 이 저장소가 ZG4(카드 상태와
칩이 같은 술어를 쓰게 만든 결정)로 이미 한 번 값을 치른 실패 계열이다. 화해는 상태 판정이지
외부 계약이 아니므로 상태 판정이 사는 곳에 둔다.

`hub_collect.py` 에 I/O 를 얹지 않는 이유는 선례와 같다 — **764/800줄**이고
`collect_snapshot` 은 이미 51줄(비어있지 않은 줄 45)이다. 신설 I/O 는 약 70줄이다.

> 배포 파일 수 **23 → 25**. `hub/install.sh` 의 `HUB_FILE_COUNT` 와 `hub/README.md`
> 「파일 배치」를 함께 고친다(T25-149 가 둘의 일치를 강제한다).

**임포트 방향**(순환 없음, T25-102 계약 유지):
`hub_live_session`(잎) ← `hub_session` ← `hub_project` ← `hub_model`,
그리고 `hub_live_session_read` ← `hub_collect`. `hub_live_session_read` 는 `hub_live_session`
만 임포트한다. `SESSIONS_DIR` 은 읽기 모듈에 선언하지 않고 **호출자(`hub_collect.py`)가 인자로
넘긴다** — `PROJECTS_DIR`→`read_subagent_metas(..., projects_dir)` 와 같은 관례다.

### LS3. 호스트 형식은 **5값 리터럴 하나로만** 상태 레이어를 건넌다

```python
RosterState = Literal["unknown", "not_listed", "listed", "busy", "idle"]
```

`hub_session.py` 는 `LiveSessionRecord` 의 필드 이름도, `status` 라는 문자열도 모른다 —
`RosterState` 라는 **우리가 소유한 5값**만 본다. 호스트가 `status` 를 `state` 로 개명하든
값을 늘리든 `hub_live_session.py` 안에서 흡수된다.

| 값 | 뜻 |
|---|---|
| `unknown` | 명부가 이 세션에 대해 말해 주는 것이 없다(디렉터리 없음·열거 실패·명부 불완전 + 미등재) |
| `not_listed` | **명부를 빠짐없이 읽었는데 없다** = 프로세스가 없다 |
| `listed` | 명부에 있고 프로세스가 살아 있다. busy/idle 은 모른다(`status` 키 부재, 실측 10%) |
| `busy` | 명부에 있고 `status == "busy"` |
| `idle` | 명부에 있고 `status == "idle"` |

### LS4. 결정 AR1/AR7 을 **부분 번복**한다 — 번복 범위를 한 문장으로 못 박는다

AR1 의 본문은 두 가지를 말하고 있었다:

1. `SessionFacts` 는 "훅 이벤트 → 세션 사실" 단일 입력원 계약이다.
2. (구조적 귀결) **카드 상태는 100% 훅 유래로 남는다.**

이번 변경은 **1은 유지하고 2를 폐기한다.**

> **개정된 정본:** `SessionFacts` 는 여전히 100% 훅 유래다(`SubagentFact` 도 그대로 — AR7
> 유지). 그러나 **표시 상태(`SessionState`) 판정은 훅 사실 + 호스트 명부 2입력이다.**

번복의 근거: AR1 이 지키려던 것은 "호스트 파일이 사라지거나 형식이 깨져도 판정이 흔들리지
않는다" 였다. 그 방어는 이번에도 살아 있지만 **다른 장치**로 산다 — `RosterState ==
"unknown"` 이면 화해가 완전한 무동작이고, 그때의 판정은 **오늘의 코드와 문자 그대로 같다**
(결정 LS7). 즉 AR1 이 사려던 "호스트 장애에 대한 면역"은 유지되고, 포기하는 것은 "호스트가
정상일 때도 그 정보를 안 쓴다"는 부분이다. 그것이 바로 사용자가 멈추라고 한 중복이다.

AR7(시작 시각 보정을 뷰에서만 한다)은 **그대로 유지**한다 — 이번 변경은 `SubagentFact` 에
아무것도 되먹이지 않는다.

결정 RV1~RV3(부활 규칙)은 **번복이 아니라 확장**이다. RV3 은 이미 "`done` 이 터미널인 것은
표시일 뿐 사실이 아니다 — 세션은 되살아날 수 있다"고 적었다. 이번에 트리거가 하나 늘 뿐이다:
`SessionStart` 이벤트에 더해 **"명부에 살아 있다"도 부활 근거다.** RV1 이 `SubagentStop` 을
부활 근거에서 뺀 이유("종료된 세션의 지연 꼬리 이벤트")는 명부에 해당하지 않는다 — 명부의
존재는 지연 이벤트가 아니라 **지금 이 순간의 관측**이다.

### LS5. 화해 표 (정본)

훅 사실 3개를 기호로 둔다: **E** = `facts.ended_at_ms is not None`(SessionEnd 관측),
**T** = `facts.turn_state == "running"`, **S** = 좀비가 아닌 미종료 서브에이전트가 있다
(`is_running_subagent`, 결정 ZG7).

| `RosterState` | `base_state` 판정 | 오늘 대비 |
|---|---|---|
| `unknown` | `E→done` / `(T∨S)→working` / `else idle` | **완전 동일**(무동작) |
| `not_listed` | `E→done` / `else idle` | **T·S 를 무시한다**(죽은 프로세스는 턴도 서브에이전트도 돌릴 수 없다) |
| `listed` | `(T∨S)→working` / `else idle`, **E 무시** | 부활만 추가 |
| `busy` | `working`, **E 무시** | `status` 가 T 를 대체 + 부활 |
| `idle` | `S→working` / `else idle`, **E 무시** | `status` 가 T 를 대체 + 부활 |

**과제가 요구한 개별 케이스의 답**

| 어긋남 | 승자 | 근거 |
|---|---|---|
| 레코드 `busy` vs 훅 `turn_state:"ended"` | **레코드(working)** | 호스트가 자기 상태를 적은 것이 권위 출처다. 훅 `Stop` 유실 구간이 실제 원인 |
| 레코드 `idle` vs 훅 `turn_state:"running"` | **레코드(턴 항 끔)** | 같은 이유. 이것이 "카드가 작업중에 고착"의 직접 치료다 |
| 레코드 있음 vs 훅 `ended_at_ms` 존재 | **레코드(`done` 취소)** | RV1 확장. 살아 있는 프로세스가 그 `session_id` 를 자기 것이라고 적고 있다 |
| 레코드 없음 vs 훅 `turn_state:"running"`(좀비) | **부재(→`idle`)** | 실측 12/12 로 부재 ⇔ 종료. 단 `done` 으로 **승격하지 않는다**(LS6) |
| `status` 키 부재(실측 10%) | **훅(T)** | 생존만 명부가, busy/idle 은 훅이 답한다(`listed` 행) |
| PID 재사용 | 검증하지 않는다 | LS8 |

**서브에이전트 항(S)을 `idle` 행에서 살려 두는 이유**(중요): 메인 턴이 끝난 뒤에도 백그라운드
서브에이전트가 도는 경우가 실재한다(`run_in_background`). 그때 호스트가 `busy` 를 유지하는지는
**측정하지 못했다.** S 를 끄면 결정 ZG7(미종료 서브에이전트가 있으면 `working`)을 조용히
뒤집게 되고, 그 실패는 "실제로 도는데 glow 가 꺼진다" — RV1 을 만든 바로 그 불만이다. 반면
S 를 살려 두면 최악이 "고아 서브에이전트가 90분간 glow 를 잡는다" 인데 그것은 이미 결정
ZG2 가 상한을 걸어 둔 **기존 동작**이다. **이번 변경은 감사표가 「완전 중복」으로 지목한 한
쌍(`turn_state`↔`status`)만 교체한다.**

### LS6. `not_listed` 는 `done` 으로 승격하지 않는다

`done` 은 "**`SessionEnd` 를 관측했다**"는 뜻이다(RV3). 부재는 관측이 아니다 — 크래시는
레코드도 `SessionEnd` 도 남기지 않는다. 또 `done` 은 `stale` 오버레이를 면제받는 유일한
상태라, 부재를 `done` 으로 올리면 **오판이 영구화**된다. `idle` 로 두면 30분 뒤 `소식 없음`,
12시간 뒤 클라이언트가 숨긴다(`STALE_SESSION_HIDE_AFTER_MS`) — 오판에 자연 상한이 생긴다.

### LS7. 부재의 증거력은 `is_complete` 플래그 **하나**로 통제한다

명부 읽기는 세 가지로 실패할 수 있고, 셋 다 같은 위험을 만든다 — **"부재"를 잘못 읽어 살아
있는 세션을 죽었다고 판정하는 것.**

| 실패 | `is_complete` | 결과 |
|---|---|---|
| 디렉터리 없음 / `iterdir()` 실패 | `False` | 모든 세션이 `unknown` → **오늘의 동작과 동일** |
| 레코드 1건이 깨짐·크기 초과·읽기 실패 | `False` | 읽힌 레코드는 그대로 쓰되, **미등재를 `not_listed` 로 읽지 않는다** |
| 전부 정상(빈 디렉터리 포함) | `True` | 미등재 = `not_listed` |

찢긴 읽기(호스트가 레코드를 다시 쓰는 중에 읽는 경합)가 **자기 세션의 레코드**에 걸리면
그 세션이 순간적으로 "죽었다"로 보일 수 있다 — `is_complete` 가 그 창을 닫는다. 빈
디렉터리가 `True` 인 것은 의도적이다: 살아 있는 세션이 0개인 것은 정상 상태이고, 그때야말로
"전부 끝났다"를 화면에 반영해야 한다.

`is_complete` 를 **`by_session_id` 의 truthiness 로 대신하지 않는다** — `{}` 와 `None` 의
차이에 이 설계의 가장 위험한 판정이 걸리면 훗날 누군가의 `if not index:` 한 줄에 무너진다.
필드 이름으로 박아 둔다.

### LS8. PID 생존은 `os.kill(pid, 0)` 로 확인하고, PID 재사용은 **수용하고 상한을 명시**한다

```
pid <= 0·bool 값·pid_t 32비트 상한(LIVE_SESSION_PID_MAX = 2**31 - 1) 초과는 파서가 이미
배제한다(불변식) — os.kill(0, 0) 은 프로세스 그룹 전체를 가리켜 "항상 생존"이라는 거짓
참을 만들고(JSON true/false 는 int 의 서브클래스라 pid=True 도 같은 함정, 검수 1회차 L1),
상한을 넘는 pid 는 os.kill 자체가 OverflowError 를 던져 ProcessLookupError·PermissionError
두 분기를 모두 뚫는다(검수 1회차 H1-3). 이 세 footgun 은 파서의
`isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid <= LIVE_SESSION_PID_MAX`
검사가 유일한 방어선이다. ProcessLookupError → 죽음 / PermissionError → 생존(남의
프로세스지만 존재한다).
```

PID 재사용은 §1.3 대로 stdlib 로 검증할 수 없다. **수용하는 근거는 상한이 있다는 것**이다:

- 재사용은 **레코드가 잔존할 때만**(=호스트 크래시) 의미가 생기고, 잔존 자체가 미관측이다
  (실측 9/9 정상, 반면 `.key` 파일은 잔존 — 두 파일의 생명주기가 다르다는 방증).
- 걸리더라도 크래시한 세션은 훅 이벤트도 끊기므로 **30분 뒤 `stale` 오버레이가 덮고**
  12시간 뒤 카드가 숨는다. `working` 오판의 최대 지속은 **30분**, `done` 취소 오판의 최대
  지속은 **12시간**이다.
- 이 상한을 만드는 것이 결정 LS9 다.

### LS9. `stale` 오버레이는 **훅 유래 그대로** 둔다

`is_stale = base_state != "done" and (now_ms - facts.last_event_at_ms) >= stale_after_ms`
를 손대지 않는다. 두 가지 이유:

1. **다른 질문에 답한다.** `stale` 은 "이 세션이 살아 있는가"가 아니라 "허브가 이 세션에
   대해 아는 것이 얼마나 낡았는가"다. 실측의 42시간 idle 세션은 살아 있고, 그 카드가
   `소식 없음` 인 것은 **옳다**.
2. **명부 오판의 유일한 독립 상한이다.** 명부가 거짓 생존(PID 재사용)을 말해도 훅 이벤트는
   멈춰 있으므로 30분 뒤 덮인다. 두 신호를 같은 출처로 묶으면 이 안전망이 사라진다.

부작용으로 "한 턴이 30분 넘게 도는 세션은 `busy` 인데도 `소식 없음`" 이 남지만, 그것은
**오늘도 같은 동작**이고 이번 요구와 무관하다(고치려면 별도 결정이 필요하다 — YAGNI 보류).

### LS10. `SessionView` 에 새 필드 0개 · 템플릿 변경 0 (D2 대응)

`snapshot_content_key` 는 `collected_at_ms` 만 빼고 전부 비교하므로, `updatedAt`·
`statusUpdatedAt` 처럼 **호스트가 계속 갱신하는 값**을 뷰에 실으면 매 수집마다 키가 바뀌어
`hub.html` 쓰기 억제가 무력해진다. 이 설계는 그 값을 **읽지도 않는다**(파서가 3필드만
투영한다 — LS11).

새로 뷰에 실리는 필드가 하나도 없으므로:

- **D2 노출 증가 0.** 키가 바뀌는 시점은 `state`/`base_state` 가 바뀔 때뿐이고, 그 빈도는
  오늘(`turn_state` 전이)과 같다.
- **T25-150 무영향** — `dataclasses.fields(SessionView)[-1].name` 고정 검사(GOTCHA 8)를
  건드리지 않는다.
- **`hub_template.html` 변경 0** — 상태 4종(`작업중`/`대기`/`소식 없음`/`완료`)의 렌더는 그대로다.

`name`·`entrypoint`·`version`·`messagingSocketPath` 를 화면에 싣지 않는다(비목표 N6).

### LS11. 읽기 비용·시점·캐시

- **언제**: 수집 사이클마다 1회(`collect_snapshot` 안). 캐시를 두지 않는다 — 결정 MD4·WF10
  과 같은 판단이고, 대상은 열거 1회 + **9개 안팎 × 660B** 파일이다. 에스컬레이션 조건도
  같다: `collect_snapshot` 이 50ms 를 넘기면 그때 재검토한다.
- **무엇을 읽나**: `*.json` 만(`.key` 제외). 파싱은 **3필드만** 투영한다 — `sessionId`·
  `pid`·`status`. 나머지 키는 뷰로도 로그로도 나가지 않는다.
- **크기 상한**: `LIVE_SESSION_RECORD_MAX_BYTES = 64 * 1024`(실측 ~660B 의 약 100배 방어선,
  `SUBAGENT_META_MAX_BYTES` 와 같은 형태·같은 값).
- **실패 흡수**(2단 가드, `_tier3_activity_by_encoded_name` 의 선례 그대로):

| 실패 | 처리 | 경고 |
|---|---|---|
| 디렉터리 부재 | 빈 인덱스 + `is_complete=False` | 없음(허브를 안 쓰는 호스트도 정상) |
| `iterdir()` 실패 | 같음 | **1건** |
| 개별 `stat`/읽기 실패, 크기 초과, JSON 깨짐, 필수 키 부재 | 그 레코드만 제외 + `is_complete=False` | **사이클당 1건으로 집계**(`N건을 읽지 못했습니다`) |
| `os.kill` → `ProcessLookupError` | 그 레코드 제외(정상 경로) | 없음 |

개별 실패를 파일마다 경고하지 않고 **집계 1건**으로 묶는 이유: 호스트가 레코드를 다시 쓰는
중에 읽는 경합은 예상된 일시 현상이라 매 사이클 N건씩 경고가 쏟아지면 경고 목록이 못 쓰게
된다. 그렇다고 조용히 삼키지도 않는다(집계 1건은 남긴다).

**열거에 `iterdir()` 를 쓰고 `glob("*.json")` 을 쓰지 않는 이유**(실측, Python 3.11.5,
구현 중 발견): `Path.glob()` 은 디렉터리에 읽기 권한이 없어도(EACCES) 예외를 던지지 않고
조용히 빈 이터레이터를 반환한다. `is_dir()` 은 그 상황에서도 `True` 를 돌려주므로(부모
디렉터리만 순회 가능하면 통과) 열거를 `glob` 으로 하면 위 표의 `except OSError` 가드
자체가 호출되지 않고 `is_complete=True`·경고 0건인 채로 명부가 통째로 비어 버린다 — 이것이
바로 LS7 이 「가장 위험한 판정」이라 부른 실패(살아 있는데 죽었다고 오판)를 무성음으로 만드는
경로다. `iterdir()` 은 같은 조건에서 `PermissionError`(`OSError` 서브클래스)를 던져
가드에 정상적으로 걸린다. `*.json` 필터는 glob 패턴이 아니라 `path.suffix == ".json"`
비교로 재현한다.

### LS12. 설정 스위치를 만들지 않는다 (YAGNI)

`HubConfig` 에 `live_session_source_enabled` 같은 필드를 두지 않는다. 기존 불린 3개는
`show_usage_panel`(프라이버시)·`record_prompt_excerpt`(프라이버시)·`usage_api_enabled`
(네트워크 옵트인)로 전부 **사용자 선택의 문제**지 "고장 나면 끄는 스위치"가 아니다. 고장
대비는 코드 쪽 구조(`unknown` → 무동작)가 맡는다.

**재방문 트리거**: 호스트가 명부를 쓰지 않는 빌드(구버전 CLI 등)에서 "glow 가 안 켜진다"는
보고가 나오면 그때 스위치를 만든다. → §9 의 사용자 확인 항목 3.

### LS13. 보안 — 명부 문자열은 `hub.html` 에 인라인되지 않는다

계약 A(redact → clip)는 **적용하지 않는다.** 근거는 면제가 아니라 **경로 부재**다:

- 뷰로 나가는 값은 `state`/`base_state`(닫힌 4값 리터럴)뿐이다.
- `session_id` 는 화면에 나가지만 그 값의 **출처는 훅 이벤트**이고(오늘과 동일), 명부의
  `sessionId` 는 **딕셔너리 조회 키로만** 쓰인다 — 뷰에 실리지 않는다.
- `cwd`·`name`·`messagingSocketPath`·`bridgeSessionId` 는 **파싱조차 하지 않는다**.
- `pid` 는 정수이고 `os.kill` 인자로만 쓰인다.
- 경고 문자열에는 **파일 경로를 담지 않는다** — 디렉터리 경로(고정 문자열)와 실패 건수만
  담는다. `<pid>.json` 파일명은 그 자체로 민감하진 않지만, 담을 이유가 없다.

**경로 조립 없음**: 파일 경로는 `sessions_dir.glob("*.json")` 의 결과를 그대로 쓴다 —
`session_id`·`agent_id` 로 경로를 조립하는 `hub_subagent_read` 와 달리 요청 문자열이
경로에 닿는 지점이 없으므로 `_is_safe_path_segment` 류의 가드가 필요 없다.

---

## 6. 데이터 모델과 인터페이스

### 6.1 `hub/bin/hub_live_session.py` (★순수, 신설)

```python
"""hub_live_session.py — ~/.claude/sessions/<pid>.json(호스트 소유 「살아있는 세션 명부」)의
순수 파서 + 명부 판정값 변환.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_live_session.py 대상).
...(계약을 한 파일에 가두는 이유 = 결정 LS2, 5값만 건너보내는 이유 = 결정 LS3)
"""

RosterState = Literal["unknown", "not_listed", "listed", "busy", "idle"]

LIVE_SESSION_STATUS_BUSY = "busy"
LIVE_SESSION_STATUS_IDLE = "idle"
LIVE_SESSION_RECORD_MAX_BYTES = 64 * 1024   # 실측 ~660B 의 약 100배 방어선
LIVE_SESSION_PID_MAX = 2**31 - 1   # pid_t 32비트 부호 있는 정수 상한(실측, Darwin) — 이 값을
                                   # 넘기면 os.kill 이 OverflowError 를 던져 ProcessLookupError·
                                   # PermissionError 두 분기를 모두 뚫는다(검수 1회차 H1-3)

@dataclass(frozen=True)
class LiveSessionRecord:
    """레코드 1건에서 허브가 쓰는 3필드만 남긴 것(결정 LS11·LS13)."""
    session_id: str
    pid: int              # 불변식: bool 이 아닌 0 < pid <= LIVE_SESSION_PID_MAX
                           # (파서가 강제 — os.kill(0, 0) footgun 과 pid_t 32비트 OverflowError
                           # 둘 다 방어, 결정 LS8, 검수 1회차 L1·H1-3)
    is_busy: bool | None  # "busy"→True, "idle"→False, 키 부재·미지값→None(실측 10%)

@dataclass(frozen=True)
class LiveSessionIndex:
    """수집 1회분의 명부. `is_complete` 가 거짓이면 **부재를 근거로 쓰지 않는다**(결정 LS7)."""
    by_session_id: dict[str, LiveSessionRecord]
    is_complete: bool

def parse_live_session_record(text: str) -> LiveSessionRecord | None:
    """레코드 1건의 본문을 판다. 깨졌거나 필수 키(sessionId·pid)가 없으면 None. 예외를 던지지 않는다."""

def build_live_session_index(
    records: Sequence[LiveSessionRecord], is_complete: bool
) -> LiveSessionIndex:
    """같은 session_id 의 레코드가 여럿이면 결정적으로 하나로 접는다 — busy > 미상 > idle,
    동률은 pid 가 작은 쪽(결정론 = snapshot_content_key 안정성)."""

def roster_state_for_session(index: LiveSessionIndex | None, session_id: str) -> RosterState:
    """이 세션에 대해 명부가 말하는 것(결정 LS3 의 5값). index 가 None 이면 항상 "unknown"."""
```

### 6.2 `hub/bin/hub_live_session_read.py` (I/O, 신설)

```python
def read_live_session_roster(sessions_dir: Path) -> tuple[LiveSessionIndex, tuple[str, ...]]:
    """명부 디렉터리를 훑어 (인덱스, 경고) 를 돌려준다. 절대 예외를 던지지 않는다.

    2단 가드(결정 LS11): 열거 실패는 명부 전체를 포기하고(is_complete=False), 레코드 단위
    실패는 그 레코드만 건너뛰되 is_complete 를 내린다. 죽은 PID 의 레코드는 인덱스에
    넣지 않는다 — 인덱스에 있다 == 프로세스가 살아 있다(결정 LS8).
    """

def _is_process_alive(pid: int) -> bool:
    """전제: pid > 0 (LiveSessionRecord 불변식). ProcessLookupError→False,
    PermissionError→True(남의 프로세스지만 존재한다)."""
```

### 6.3 `hub/bin/hub_session.py` (수정)

```python
def _compute_base_state(
    facts: SessionFacts,
    now_ms: int,
    zombie_after_ms: int,
    roster: RosterState,     # ← 신규. 기본값 없음(재검수 1회차 M2 — 아래 참조)
) -> Literal["working", "idle", "done"]:
    """결정 LS5 의 화해 표. 표의 5행을 그대로 옮긴 것 외의 판단은 없다."""

def compute_session_view(
    facts, now_ms, stale_after_ms, zombie_after_ms=SUBAGENT_ZOMBIE_AFTER_MS,
    model=None, tier1=None, dashboard_key=None, workflow=None, task_excerpt=None,
    subagent_meta_by_agent_id=None,
    live_roster: LiveSessionIndex | None = None,     # ← 신규(맨 뒤, 기본값 None)
) -> SessionView:
    """... `live_roster` 는 이 함수가 읽지 않는다(I/O) — hub_collect 가 모아 넘긴다.
    다른 보강 인자들과 달리 **뷰에 실어 나르지 않고 상태 판정에 쓴다**(결정 LS4)."""
```

**재검수 1회차 M2(구현 정정)**: `_compute_base_state` 의 `roster` 는 기본값을 두지 않는다.
유일 호출자 `compute_session_view`(위)가 `roster_state_for_session` 의 결과를 항상 명시적으로
계산해 넘기므로, 기본값을 두면 호출부가 저장소 전체에 하나뿐이라 그 기본값 자체는 도달
불가능한 죽은 코드가 된다(YAGNI 위반). `roster == "unknown"`(명부가 이 세션에 대해 말해
주는 것이 없을 때)이 "오늘의 판정과 완전히 같은" 것은 이 함수 **본문의 마지막 분기**가
원래 코드 그대로이기 때문이지, 매개변수 기본값 때문이 아니다 — 이 구분이 아래 §7.3 C1 행의
변조 검출 문구에도 그대로 반영된다.

`SessionView`·`SessionFacts`·`SubagentFact`·`HookEvent` 는 **필드 변경 없음**.

### 6.4 `hub/bin/hub_project.py` (수정 — 배선만)

`compose_project_views` / `_project_view_for_path` / `_session_views_for_path` 세 시그니처에
`live_roster: LiveSessionIndex | None = None` 을 더하고 그대로 `compute_session_view` 에
넘긴다. **판단 0줄** — `subagent_meta_by_agent_id` 가 이미 세운 관례와 같은 모양이다.

### 6.5 `hub/bin/hub_collect.py` (수정)

```python
# 호스트(Claude Code)가 살아있는 세션마다 쓰는 명부 — 우리가 소유하지 않는 읽기 전용 입력이다.
# *.json 만 대상이고 같은 디렉터리의 <pid>.<sha256>.key 는 건드리지 않는다(결정 LS11).
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
```

`_read_session_annotations` 가 **4종**(모델·마지막 프롬프트 / 워크플로우 / 서브에이전트 메타 /
**명부**)을 모으도록 확장하고 5-튜플을 돌려준다. 명부는 `record_prompt_excerpt` 로 게이팅하지
**않는다**(프롬프트 콘텐츠가 아니다).

> **왜 `collect_snapshot` 에 직접 넣지 않나**: 그 함수는 이미 51줄(비어있지 않은 줄 45)로
> 50줄 규칙의 경계에 있고, `_read_session_annotations` 는 정확히 그 압력 때문에 뽑힌 함수다
> (재검수 1회차 M4). 명부는 "세션에 얹을 보강 정보"라는 그 함수의 정의에 그대로 들어맞는다.

---

## 7. 테스트 계획 (뮤테이션 검출력 포함)

규약: `tests/hub/` 는 stdlib `unittest`, 모듈 상수는 `setUp`/`tearDown` 에서 swap.
**모든 신규 테스트에 "무엇을 변조하면 이 테스트가 실패하는가"를 함께 적는다** — 직전 회차에
"코드는 맞는데 가드가 무력한" 결함이 14건 나왔다.

### 7.1 `tests/hub/test_hub_live_session.py` (★순수)

| # | 케이스 | 단언 | **이것을 변조하면 실패해야 한다** |
|---|---|---|---|
| L1 | 정상 레코드(실측 원문 그대로) | 3필드가 정확히 나온다 | `status` → `is_busy` 매핑을 뒤집는다 |
| L2 | `status` 키 부재 | `is_busy is None` | `payload.get("status")` → `payload.get("status", "idle")` |
| L3 | `status:"busy"` / `"idle"` 각각 | `True` / `False` | 상수 `LIVE_SESSION_STATUS_BUSY` 를 `"Busy"` 로 |
| L4 | `status` 가 미지값(`"starting"`) | `is_busy is None`(→ `listed`) | 미지값을 `False` 로 접는다 |
| L5 | `sessionId` 부재 / `pid` 부재 / `pid` 가 문자열 | `None` | `isinstance(pid, int)` 검사 삭제 |
| L5b | `pid` 가 `True`(bool, 검수 1회차 L1) | `None` | `not isinstance(pid, bool)` 검사 삭제(→ `os.kill(1,0)`=launchd 로 항상 생존) |
| L6 | **`pid` 가 0 또는 음수** | `None` | `pid > 0` 검사 삭제(= `os.kill(0,0)` footgun 재개통) |
| L6b | `pid` 가 `LIVE_SESSION_PID_MAX` 초과(검수 1회차 H1-3) | `None` | 상한 검사 삭제(→ `os.kill` 이 `OverflowError`) |
| L6c | `pid == LIVE_SESSION_PID_MAX`(경계) | 그대로 유지 | — (경계값 확인, 비용 0) |
| L6d | `LIVE_SESSION_PID_MAX` 상수 자체(리터럴 `2147483647`, 검수 2회차 H3) | 그 리터럴과 정확히 같다 | 상수를 `2**63`·`2**31`(off-by-one) 등으로 바꾼다 — L6b·L6c 는 "상한 존재 여부"만 봐서 못 잡는다 |
| L6e | `pid == 2147483648`(off-by-one 상한에서 실제로 고장나는 값, 리터럴, 검수 2회차 H3) | `None` | 상한을 `2**31`로 한 칸 늘린다(→ `os.kill` 이 `OverflowError`) |
| L7 | JSON 깨짐 / 최상위가 리스트 | `None`, 예외 없음 | `except json.JSONDecodeError` 삭제 |
| L7b | 병리적 입력(4,400자리 정수 리터럴 · 30,000단 중첩 배열, 검수 1회차 H1) | `None`, 예외 없음(계약 B) | `except (ValueError, RecursionError)` 를 좁힌다 |
| L8 | 같은 `session_id` 2건(busy+idle) | busy 쪽이 이긴다 | 접기 우선순위를 pid 순으로만 |
| L8b | 같은 `session_id` 2건(idle+미상, 검수 1회차 H3) | 미상 쪽이 이긴다 | `is_busy is None: return 1` 을 `return 2` 로 |
| L8c | 같은 `session_id` 2건(busy+미상, 검수 2회차 H2) | busy 쪽이 이긴다(3단 우선순위의 마지막 인접 쌍) | `is_busy is True: return 0` 을 `return 1` 로 |
| L9 | 같은 `session_id` 2건(같은 상태, pid 다름) | pid 작은 쪽 결정론 | 타이브레이커 삭제(비결정 → D2 위협) |
| L10 | `roster_state_for_session(None, sid)` | `"unknown"` | `None` 분기 삭제 |
| L11 | `is_complete=False` + 미등재 | `"unknown"` | `is_complete` 무시(→ `"not_listed"` 가 나와 실패) |
| L12 | `is_complete=True` + 미등재 | `"not_listed"` | 항상 `"unknown"` 반환 |
| L13 | 등재 + busy/idle/미상 3케이스 | `"busy"`/`"idle"`/`"listed"` | `is_busy is None` 을 `not is_busy` 로 |

### 7.2 `tests/hub/test_hub_live_session_read.py` (I/O, 임시 디렉터리)

`_is_process_alive` 의 두 분기는 `mock.patch("os.kill", side_effect=...)` 로 태운다 —
`tests/hub/test_hub_daemon.py: StopServerKillCallSiteTest` 가 세운 선례다(그 클래스의
「부정 단언에는 분모를 함께 공급한다」 규약도 따른다). 생존 쪽 분모는 `os.getpid()` 를
그대로 쓴 케이스로 확보한다(모킹 없이도 반드시 True).

| # | 케이스 | 단언 | **변조 검출** |
|---|---|---|---|
| R1 | 디렉터리 자체가 없음 | 빈 인덱스, `is_complete False`, 경고 0 | `is_complete=True` 로 반환 |
| R2 | 정상 3건 전부 생존 | 3건, `is_complete True` | — (분모) |
| R3 | 3건 중 1건 PID 죽음(`ProcessLookupError`) | 2건만, `is_complete **True**` | 죽은 PID 를 인덱스에 남긴다 |
| R4 | `PermissionError` | 인덱스에 남는다 | `PermissionError` 분기를 `return False` 로 |
| R5 | `.key` 파일 공존 | 무시, `is_complete True` | suffix 필터(`path.suffix == ".json"`) 삭제(→ `.key` 도 파싱 시도해 `is_complete False` 가 되어 실패) |
| R6 | JSON 깨진 레코드 1건 + 정상 2건 | 정상 2건은 살고 `is_complete False`, 경고 **1건** | 깨진 레코드에서 `is_complete` 를 안 내린다 / 경고를 파일마다 낸다(건수 단언이 잡는다) |
| R7 | 크기 상한 초과 1건 | 제외 + `is_complete False` | 크기 검사 삭제 |
| R8 | 빈 디렉터리(`.json` 0건) | 빈 인덱스, **`is_complete True`**, 경고 0 | 빈 명부를 `False` 로(=LS7 의 의도적 구분이 사라짐) |
| R9 | 열거 실패 — 실제 `chmod 000` 디렉터리(`PermissionError`, `OSError` 서브클래스). 모킹이 아니라 실제 권한 오류로 검증한다 — `glob("*.json")` 은 이 조건을 예외 없이 조용히 통과시켜(Python 3.11.5 실측, LS11 참고) 모킹으로 `OSError` 를 주입하는 테스트로는 이 가드가 실전에서 무력해도 통과했다 | `is_complete False`, 경고 1건(경고 문구에 "목록 조회 실패" 포함을 `assertIn` 으로 고정) | 열거를 `iterdir` 대신 `glob("*.json")` 으로 되돌리면 EACCES 를 묵살해 실패(경고 0건·`is_complete True`) / 경고 문구를 R11(접근 실패)과 같게 만들면 `assertIn` 이 실패 |
| R10 | 읽기 중 `UnicodeDecodeError` 유발 바이트 | 예외 없이 흡수 | `errors="replace"` 삭제(GOTCHA 7 — `ValueError` 는 `except OSError` 를 뚫는다) |
| R6a | `iterdir()` 이 본 경로가 `stat()` 시점에 사라짐(TOCTOU, 검수 1회차 H4) | 그 레코드만 실패로 집계, `is_complete False`, 경고 1건 | `_read_record_text` 의 `except OSError` 를 다른 예외형으로 바꾼다 |
| R11 | `is_dir()` 자신이 `PermissionError`(EACCES, 검수 2회차 H1) | `is_complete False`, 경고 1건(경고 문구에 "접근 실패" 포함을 `assertIn` 으로 고정 — R9 의 "목록 조회 실패"와 구별됨, 검수 3회차 LOW) | `is_dir()` 호출을 try/except 로 감싸지 않는다(`hub_workflow_read._existing_workflow_directories` 선례와 동형) / 경고 문구를 R9(목록 조회 실패)와 같게 만들면 `assertIn` 이 실패 |

### 7.3 `tests/hub/test_hub_session.py` (확장)

**진리표 테스트(표 기반, 15케이스)** — LS5 표의 5행 × 훅 상태 3조합(E / T / S). 표를
데이터로 두고 반복한다. 핵심 케이스와 변조 검출:

| # | 입력 | 기대 | **변조 검출** |
|---|---|---|---|
| C1 | `unknown` × 전 조합 | **오늘의 판정과 동일** | `_compute_base_state` 의 `unknown` 분기(본문 마지막 else 사슬) 자체를 지우면 여기서 무너진다 — 매개변수 기본값이 아니라 이 분기가 유일한 방어선이다(재검수 1회차 M2, §6.3 참조) |
| C2 | `not_listed` + T(running) | `idle` | `not_listed` 행 삭제(→ `working` 이 나와 실패) |
| C3 | `not_listed` + S(서브에이전트 running) | `idle` | S 항을 `not_listed` 행에서 살려 둔다 |
| C4 | `not_listed` + E | `done` | 부재를 무조건 `idle` 로(→ `done` 이 사라져 실패) |
| C5 | `busy` + E | `working` | 부활(E 무시) 삭제 → `done` |
| C6 | `busy` + `turn_state="ended"` | `working` | `busy` 행이 훅의 turn ended 를 무시하는가를 본다(자기 고유 역할). OR 합성 변조(status 가 T 를 대체하지 않고 OR 로만 합쳐지는 결함)는 이 케이스 **단독으로는** 못 잡는다 — busy 자체가 이미 working 이라 OR 이든 대체든 결과가 같다(재검수 1회차 M5 실측) |
| C7 | `idle` + T(running) | `idle` | 이 표에서 OR 합성 변조를 잡는 **유일한** 테스트다 — 지우면 `working` 이 나와 실패한다(재검수 1회차 M5) |
| C7b | `idle` + E(`SessionEnd`, `Stop` 선행으로 T=0 고정) | `idle`(부활) | 검수 3회차 H1 — 부활(E 무시)이 `busy`(C5)·`listed`(C10) 행에만 있고 `idle` 행엔 없었다. `idle` 은 실측상 가장 흔한 행이라, 이 테스트 없이는 803건이 전부 통과했다. `idle` 행 앞에 E 를 검사해 `done` 으로 보내는 분기를 넣으면 실패 |
| C8 | `idle` + S | `working` | ZG7 보존. S 항 삭제 시 실패 |
| C9 | `listed` + T | `working` | `listed` 를 `busy` 로 접으면(항상 working) 실패 |
| C9b | `listed` + `turn_state="ended"` + S 없음 | `idle` | `listed` 를 `busy` 로 접으면 실패(C9 와 짝) |
| C9c | `listed` + S(서브에이전트 running, T=0) | `working` | 검수 1회차 M1 — `listed` 행은 `(T∨S)→working` 인데 S 항을 지키는 케이스가 C8(`idle` 행)뿐이었다. `listed` 행의 (T∨S) 에서 S 를 지우면(T 만 남으면) turn 이 이미 끝난 상태라 `idle` 이 나와 실패 |
| C10 | `listed` + E | `idle`(부활) | 부활을 `busy` 행에만 달면 실패 |
| C11 | `busy` + `last_event` 가 31분 전 | `state == "stale"`, `base_state == "working"` | `is_stale` 계산에 roster 를 섞으면 실패(LS9 회귀 가드) |
| C12 | `compute_session_view(live_roster=None)` | 기존 테스트 전부 무변화 | 기본값을 없애면 호출부 전체가 깨진다 |

> **재검수 1회차 M5(구현 정정)**: 이 표는 원래 "C6·C7 을 짝으로 봐야 값진다"고 적었으나
> 실측과 다르다 — **C7 혼자** "호스트가 훅을 대체한다"와 "둘을 OR 한다"를 가른다(OR 합성
> 변조에서도 C6 은 통과한다). 상호 의존이 아니라 C7 쪽 단방향 의존이다 — "짝이니까
> 괜찮다"는 인식은 정작 위험한 C7 단독 삭제를 가려 준다. C6 은 그 대신 자기 고유 역할
> ("busy 가 turn ended 를 무시한다")을 지킨다. 반대 방향(busy 행을 `working` 고정값으로
> 바꾸는 변조)은 C6 과 W1 둘 다 잡는다.

### 7.4 `tests/hub/test_hub_collect.py` (확장)

| # | 케이스 | 단언 | **변조 검출** |
|---|---|---|---|
| W1 | 임시 `SESSIONS_DIR` 에 busy 레코드 + 훅 이벤트(turn ended) → `collect_snapshot` | 해당 세션 뷰가 `working` | 배선(인자 전달) 한 군데만 빠져도 실패 — 순수 층 테스트로는 못 잡는 유일한 결함 계열 |
| W2 | `SESSIONS_DIR` 없음 | 스냅샷이 오늘과 동일, 경고 0 | `is_complete` 기본값 오류 |
| W3 | 깨진 명부 레코드 1건(검수 1회차 H5) | 경고가 `snapshot.warnings` 에 합쳐진다 | `_read_session_annotations` 의 warnings 합치기에서 `*roster_warnings` 를 뺀다(병합 누락) |

### 7.5 `tests/run.sh` T 그룹 (정적 검사)

| ID | 검사 | 근거 |
|---|---|---|
| **T25-10 갱신** | ★순수 파일 목록에 `hub_live_session.py` 편입(`open(`/`Path(`/`os.` 금지) | 순수 레이어 경계의 기계적 강제 |
| **T25-149 갱신** | `HUB_FILE_COUNT == 25`, `hub/README.md` 에 "25개 파일" | 배포 파일 수 고정 |
| **T25-104 갱신** | `hub/README.md`·`docs/prps/hub-dashboard.md` 모듈표에 신규 2개 | 문서 정합 |
| **T25-213 신설** | 두 파일 존재 + `hub_live_session.py` 에 `open(`/`Path(`/`time.`/`os.` 흔적 없음 | T25-205 와 동형 |
| **T25-214 신설** | `hub_live_session.py` 가 다른 허브 모듈을 임포트하지 않는다(잎 계약) | T25-102 와 동형 — 순환 방지 |
| **T25-215 신설** | `hub_session.py` 에 `"not_listed"`·`"busy"`·`"idle"`·`"listed"` 네 분기가 모두 있다(독립 서브체크 `T25-215`·`215b`·`215c`·`215d`, 검수 1회차 H2 로 강화) | 화해 표의 행 하나가 조용히 사라지는 것을 막는다 |
| **T25-216 신설** | `hub_live_session.py` 에 pid 유효성 검사 **전체식**(`isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid <= LIVE_SESSION_PID_MAX`)이 있다 | LS8 의 footgun 방어선이 유일하므로 기계적으로 고정한다. bare `pid > 0` 부분 문자열은 가짜 주석("# invariant: pid > 0")으로도 통과해 무력화된다(검수 1회차 M3) |
| **T25-217 신설** | `hub_collect.py` 의 `SESSIONS_DIR` 이 `~/.claude/sessions` 를 가리킨다(리터럴 고정, 검수 1회차 M4) | 오탈자(`sessions`→`session`)가 디렉터리 부재로 이어져 전 세션이 `unknown` 으로 조용히 폴백하는 완전 무성음 고장을 막는다 |

각 신설 가드는 `tests/mutations.tsv` 에 변조행 1개를 등록한다(T25-215 는 서브체크 4개라
4행, 나머지는 1행씩 — 5종 합계 8행. 8열 규약, `expect_token` 은 실패 보고 줄에서 1건만
등장해야 한다). 예: T25-216 의 변조는 파서에서 `and not isinstance(pid, bool) and
0 < pid <= LIVE_SESSION_PID_MAX` 전체식을 지우는 `sed` 이고, 기대 실패 토큰은 그 가드의
`note_failure` 문구다. **주의**: 위 다섯 가드(`T25-215`~`215d`·`216`)는 전부 `grep -qF`
문자열 매칭이라 소스에 실제 검사 대신 그 문자열을 담은 **주석**만 남겨도 통과한다 —
「검출기」가 아니라 「래칫」이다. 동작 여부의 실제 검증은 각 단위 테스트(§7.1·§7.3)가 맡는다.

### 7.6 검증 명령 (정본, `CLAUDE.md` §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

**금지**(CLAUDE.md §1): 이 저장소 안에서 `install.sh --scope project` 실행, 실제 `$HOME`
대상 설치. 명부 디렉터리(`~/.claude/sessions/`)는 **읽기만** 한다 — 테스트는 반드시 임시
디렉터리를 `SESSIONS_DIR` 에 swap 해서 돈다.

---

## 8. 리스크와 대안

| # | 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|---|
| K1 | 호스트가 명부 형식·경로를 바꾼다 | 중 | 화해가 무동작 → **오늘의 동작으로 복귀** | `unknown` 경로가 곧 폴백(LS7). 계약이 `hub_live_session.py` 한 파일에 갇혀 있다 |
| K2 | 명부를 쓰지 않는 호스트 빌드 | 낮 | 모든 세션이 `unknown` → 오늘과 동일 | 디렉터리 부재 = `is_complete False`. **부재를 근거로 쓰지 않는다** |
| K3 | 레코드를 쓰지 **않는 세션 종류**가 있다(미관측) | 낮 | 그 세션이 `작업중` 대신 `대기` (glow 손실) | 실측 반례 0건(12/12). 발생 시 증상이 명확해 진단 가능 → LS12 의 스위치 재방문 트리거 |
| K4 | PID 재사용 + 레코드 잔존 | 매우 낮 | `working` 오판 ≤30분, `done` 취소 오판 ≤12시간 | `stale` 오버레이(LS9)가 독립 상한 |
| K5 | 찢긴 읽기로 자기 세션이 순간 "죽음"으로 보인다 | 중 | 없음 | `is_complete=False` 가 그 사이클의 부재 판정을 통째로 끈다(LS7) |
| K6 | `done` 취소로 숨어 있던 카드가 다시 보인다 | 중 | 화면에 카드 1~N개 증가 | 상한이 있다 — 그 카드는 `소식 없음` 이 되고 12시간 뒤 클라이언트가 숨긴다 |
| K7 | 파라미터 줄줄이 전달(hub_project 3개 시그니처) | — | 가독성 | 새 패턴이 아니다(`subagent_meta_by_agent_id` 와 동형). 판단은 0줄 |

### 검토했으나 채택하지 않은 대안

1. **명부만 있는 세션도 카드로 띄운다.** 기각(LS1) — 실측 44%가 40시간 이상 조용한 세션이고,
   `last_event_at_ms` 를 합성해야 한다. 값보다 소음이 크고, 되돌리기 어렵다(사용자가 한 번
   본 카드가 사라지면 그것 자체가 회귀로 읽힌다).
2. **`status` 와 훅 `turn_state` 를 OR 로 합친다**(둘 중 하나라도 working 이면 working).
   기각 — 그러면 "카드가 `작업중` 에 고착"이라는 **원래 증상이 하나도 고쳐지지 않는다.**
   호스트를 권위 출처로 삼는다는 승인 범위와도 어긋난다. 대신 서브에이전트 항(S)만 OR 로
   남겨 ZG7 을 보존했다(LS5).
3. **`ps` 로 PID 신원까지 확인한다**(hub_daemon 선례). 기각(LS8) — 수집 사이클마다 도는
   경로라 subprocess 예산이 없고(50ms), 비교 가능한 신원 신호가 없다(`procStart` 는 UTC,
   `ps lstart` 는 로컬, argv 는 entrypoint 마다 다르다).
4. **화해를 새 모듈에 둔다.** 기각(LS2) — 상태 판정이 두 파일로 쪼개져 `_compute_base_state`
   를 읽는 사람이 결론이 뒤집히는 것을 모르게 된다(ZG4 가 값을 치른 실패 계열).
5. **`is_complete` 대신 `LiveSessionIndex | None` 의 truthiness.** 기각(LS7) — `{}` 와
   `None` 의 차이에 가장 위험한 판정이 걸린다.

---

## 9. 사용자 확인이 필요한 항목 (승인 요청)

1. **`done` 이 취소된다.** 지금 `완료` 로 보이는 카드 중 프로세스가 실제로 살아 있는 것은
   `대기`/`소식 없음` 으로 바뀐다(숨어 있던 카드가 다시 보일 수 있고, 12시간 뒤 다시
   숨는다). 승인하면 화면에서 눈에 띄는 변화는 이것 하나다.
2. **명부에만 있는 세션 4개는 계속 안 보인다**(결정 LS1). "지금 열려 있는 세션은 전부 보고
   싶다"면 지금 말해야 한다 — 설계가 달라진다.
3. **끄는 스위치를 만들지 않는다**(결정 LS12). 호스트가 명부를 안 쓰는 환경에서 문제가
   생기면 코드 수정으로 대응한다.

---

## 10. 구현 순서 (검증 가능한 단계)

| # | 단계 | 검증 |
|---|---|---|
| 1 | `hub_live_session.py` + `tests/hub/test_hub_live_session.py`(L1~L13) | `python3 -m unittest discover -s tests/hub -t .` 통과 |
| 2 | `hub_live_session_read.py` + 테스트(R1~R11) | 같음 |
| 3 | `hub_session.py` 화해 표 + 진리표 테스트(C1~C12) | 기존 `test_hub_session.py` 전부 무변화 통과(= C1·C12 가 보장) |
| 4 | `hub_project.py`·`hub_collect.py` 배선 + W1~W3 | `collect_snapshot` 이 여전히 50줄 규칙 안(비어있지 않은 줄 ≤50) |
| 5 | `hub/install.sh` 25 · `hub/README.md` · `docs/prps/hub-dashboard.md` | `bash tests/run.sh` (T25-104·T25-149) |
| 6 | `tests/run.sh` T25-10 갱신 + T25-213~217(215 는 215b~215d 서브체크 포함, 총 5종) + `tests/mutations.tsv` 8행 | `bash tests/run.sh` 전체 통과 |
