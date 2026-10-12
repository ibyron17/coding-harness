# hub_collect.py 800줄 상한 복귀를 위한 모듈 분리 (병합 회귀 대응)

> 상태: 설계(구현 전). 승인 대기.
> 대상 브랜치: `feature/hub-workflow-visibility` (main 위로 리베이스 완료)
> 선행 문서: `docs/prps/hub-model-module-split.md`(결정 MS1 — 800줄 규칙),
> `docs/prps/hub-workflow-visibility.md`(`hub_workflow_read.py` 분리 선례),
> `docs/prps/hub-session-tree-and-per-session-dashboards.md`(T25-156~163 라벨 블록)

---

## 1. 요구사항 요약

`main`(세션 트리)과 이 브랜치(워크플로우 가시성)를 리베이스로 통합한 결과
`hub/bin/hub_collect.py` 가 **849줄**이 되어 `tests/run.sh` 의 **T25-100**(hub/bin/\*.py 전부
800줄 이하)이 1건 실패한다. 두 기능이 각자 상한 바로 아래(양쪽 다 799줄)까지 채운 채
합쳐졌기 때문이다.

**목표는 `hub_collect.py` 를 800줄 이하로 되돌리되 런타임 동작을 1비트도 바꾸지 않는 것**이다.
상한 상수는 올리지 않는다(§8 기각 1). 파이썬 단위 테스트는 이미 613/613 통과하므로, 이
작업의 성공 기준은 **"`bash tests/run.sh` 전체 통과 + 어떤 공개 함수의 시그니처·반환값·경고
문자열도 변하지 않음"** 이다.

부수 과제 1건: 리베이스 충돌 해소 과정에서 `tests/run.sh` 에 **T25-156·157·158 라벨이 각각
두 벌씩** 생겼다. 재번호 방침을 §9 에서 정한다.

---

## 2. 실측 (모두 이 워크트리에서 직접 측정한 값)

### 2.1 파일 크기

```
849 hub/bin/hub_collect.py     ← 상한 초과
476 hub/bin/hub_usage.py
456 hub/bin/hub_server.py
438 hub/bin/hub_project.py
435 hub/bin/hub_session.py
370 hub/bin/hub_daemon.py
354 hub/bin/hub.py
... (나머지 전부 800 이하)
```

`tests/run.sh` 의 800줄 검사는 **`hub/bin/*.py` 글롭에만** 적용된다(L4763). `tests/hub/*.py`
에는 크기 상한이 없다 — 실측: `tests/hub/test_hub_collect.py` 는 이미 1,560줄인데 통과한다.
따라서 **테스트 파일 분리는 이 작업의 강제 요구가 아니다**(다만 §6 에서 모듈 1:1 관례 때문에
새 테스트 파일 2개를 만든다).

### 2.2 `hub_collect.py` 의 성장 이력 (여유 산정의 근거)

`git log --format=%h -- hub/bin/hub_collect.py` 의 각 커밋에서 `git show <sha>:파일` 을 떠서
직접 센 값이다.

| 커밋 | 날짜 | 줄 수 | 증감 |
|---|---|---:|---:|
| e0e9a40 | 08-13 | 521 | — |
| 4c5e351 | 08-13 | 564 | +43 |
| e2c3434 | 08-14 | 563 | −1 |
| 112225c | 08-18 | 567 | +4 |
| 39eaf15 | 08-20 | 613 | +46 |
| e0f6a3d | 08-21 | 634 | +21 |
| aed4b46 | 08-25 | 652 | +18 |
| 91db9b8 | 08-26 | 716 | +64 |
| c69ca32 | 08-28 | 748 | +32 |
| 321e279 | 09-02 | 799 | +51 |
| 45a07cf | 09-02 | 830 | +31 |
| 910a6e8 | 09-03 | 849 | +19 |

**기능당 중앙값 +31줄, 최대 +64줄, 11회 중 8회가 +18 이상.** 게다가 45a07cf(+31)는
`hub_workflow_read.py`(145줄)를 **따로 뽑아낸 뒤의** 증가분이므로 실제 압력은 이보다 크다.

→ 이 표가 §3.2「왜 한 개가 아니라 두 개인가」의 유일한 근거다. 여유 26줄(한 덩어리만 분리)은
11회 중 3회만 견딘다. 여유 82줄은 최대 관측치(+64)를 한 번 견디고, 중앙값 기준 약 2.6회를
견딘다.

### 2.3 분리 후보 덩어리와 그 호출자 (`grep -rn` 전수)

| 후보 | 위치 | 줄 수 | `collect_snapshot` 이 부르는가 | 외부 호출자 | 모듈 상수 참조 수(테스트 포함) |
|---|---|---:|---|---|---:|
| **A. config 스키마·검증** | L78–152 | 75 | ○ (`load_config` 경유) | 없음 — 상수 직접 참조는 `hub_collect.MIN_*` 2건뿐 | `CONFIG_PATH` 42 |
| **B. 원자적 쓰기 유틸** | L623–678 | 56 | ○ (`write_hub_html`) | 없음 — 전부 module-private | `_atomic_write_text` 외부 참조 **2건** |
| C. 한도 캡처 I/O | L494–554 | 61 | ○ (`_capture_for_snapshot`) | `hub.py`×4·`hub_server.py`×2·`hub_statusline.py`×2 | `RATE_LIMITS_PATH` 다수 |
| D. 실패 기록 파일 | L705–777 | 73 | **✕** | `hub.py`×4·`hub_server.py`×5·`hub_daemon.py`×1 | 37 |
| E. 상주 서버 상태 파일 | L778–849 | 72 | **✕** | `hub.py`×2·`hub_server.py`×4·`hub_daemon.py`×다수 | 56 |

- A 영역이 참조하는 외부 이름은 **`dataclasses`·`hub_model` 뿐**이다(실측: 정규식 스캔 결과
  `json` 은 경고 문자열 `"config.json: …"` 의 부분일치였고 실제 호출은 없다).
- A 영역에 `open(`·`Path(`·`os.` 은 **0건**이다(실측) → **★순수 모듈로 승격 가능**하다.
- B 영역은 `tempfile`·`os.fdopen`·`re` 를 쓴다 → ★순수가 **아니다**.
- `_atomic_write_text` 는 `hub_collect.py` 안 **5곳**(L521·693·720·754·813)에서 호출된다.
- `import tempfile` 은 `_atomic_write_text` 에서만 쓰인다 → B 이동 시 제거 가능.
  `os` 는 L278(transcript seek), `re` 는 L336(이벤트 파일명)에서 계속 쓰이므로 남는다.

### 2.4 순환 임포트가 실제로 어떻게 깨지는지 (실측)

`hub_collect` 와 위성 모듈이 서로를 임포트하는 형태를 임시 디렉터리에서 재현했다.

| 형태 | 임포트 순서 | 결과 |
|---|---|---|
| 위성이 `import hub_collect` 후 **호출 시점**에 `hub_collect.HUB_HOME` 참조 | host 먼저 | exit 0 (동작) |
| 〃 | 위성 먼저 | exit 0 (동작) |
| 위성이 최상위에서 `from hub_collect import HUB_HOME` | **host 먼저** | **exit 1 — `ImportError: cannot import name 'HUB_HOME' from partially initialized module`** |
| 〃 | 위성 먼저 | exit 0 |

→ **순환 자체는 조용히 통과하다가 임포트 순서가 바뀌는 날 터진다.** `hub/bin/` 은
`hub.py`·`hub_server.py`·`hub_daemon.py`·`hub_hook.py`·`hub_statusline.py` 다섯 진입점이
각기 다른 순서로 모듈을 임포트하므로 이 잠복 결함은 실재한다. 프로젝트 CLAUDE.md 의
「순환 의존이 생기면 구현을 멈춘다」와 T25-102(잎 모듈 계약)를 그대로 따른다.

### 2.5 테스트의 격리 방식과 그 위험

- 테스트는 `hub_collect.HUB_HOME = temp` 같은 **직접 대입**으로 경로를 격리한다 —
  실측 54건. `mock.patch.object(hub_collect, …)` 는 33건.
- 직접 대입은 **속성이 없어도 조용히 새 속성을 만든다** → 상수를 다른 모듈로 옮기면서
  대입 지점 하나를 놓치면 실제 `~/.claude/hub` 에 쓰는 사고가 난다(조용한 실패).
- 완화 요인(실측): `tests/run.sh` 는 진입부 L24-25 에서 `export HOME="$GLOBAL_HOME_SANDBOX"`
  로 HOME 자체를 샌드박스로 바꾸고, 파이썬 유닛 테스트(T24)도 그 안에서 돈다. 따라서
  `bash tests/run.sh` 경로에서는 실제 홈이 오염되지 않는다. **그러나 개발자가
  `python3 -m unittest` 를 직접 돌리면 보호가 없다.**

→ 이것이 §8 에서 후보 D·E(상수 이동이 큰 후보)를 기각하는 주된 근거다.

### 2.6 `tests/run.sh` 가 `hub_collect.py` 를 이름으로 붙잡는 지점 (전수)

`hub_collect_file` 변수 사용 + 문자열 `hub_collect` 포함 검사 전부를 나열한다. **조치 열이
이 설계의 핵심 산출물이다.**

| 줄 | 검사 | 무엇을 붙잡는가 | 이번 이동의 영향 | 조치 |
|---:|---|---|---|---|
| 3199 | 변수 선언 | `hub_collect_file` | — | **유지.** 아래에 `hub_config_file`·`hub_atomic_write_file` 선언 2줄 추가 |
| 3213 | 변수 선언 | `test_hub_collect_file` | — | 유지 |
| 3428 | T25-18 | `awk '^def _tier3_activity_by_encoded_name\('` 본문에 `except OSError` | 티어 3 은 안 옮긴다 | **유지(무영향)** |
| 3900 | T25-54(역) | `plan-usage-history`·`PLAN_USAGE_HISTORY_PATH`·`parse_usage_history` 가 hub_collect/hub_usage 에 없다 | 이동 영역 A·B 어디에도 이 토큰 없음 | **유지(무영향).** 새 파일이 은신처가 되지 않는지는 T25-14/75 글롭이 겹쳐 덮는다 |
| 4008 | T25-61 | `'"usage_api_enabled": bool'` **in `$hub_collect_file`** | `_CONFIG_FIELD_TYPES` 가 `hub_config.py` 로 이동 | **깨진다 → 앵커 이동 필수.** 대상 파일을 `$hub_config_file` 로 바꾸고 실패 메시지의 파일명도 함께 고친다 |
| 4166 | T25-72 | `mark_stale_usage_sample` in hub_collect | 한도 캡처는 안 옮긴다 | **유지(무영향)** |
| 4171 | T25-72 | `sed -n '/^def _capture_for_snapshot/,/^# ---- 합성 ----/p'` | 두 앵커 모두 hub_collect 에 잔류 | **유지(무영향).** 단 종료 앵커 주석 `# ---- 합성 ----`(L571) 을 **지우지 말 것** — 지우면 sed 범위가 비어 검사가 조용히 공허해진다 |
| 5072–5076 | T25-112 | `fold_worktree_path` 호출 줄번호 < `should_ignore_cwd` 호출 줄번호 | 줄번호는 바뀌나 **상대 순서 불변** | **유지(무영향)** |
| 5666 | T25-138 | `template_stamp=` 대입 in hub_collect | `collect_snapshot` 잔류 | **유지(무영향)** |
| 5677 | T25-139 | `awk '^def read_template_stamp\(\) -> str:'` 본문 | 잔류 | **유지(무영향)** |
| 5131–5135 | T25-118 | `test_hub_collect.py` 에 `class CollectSnapshotWorktreeTier1Test`·`hub_collect.collect_snapshot(` | 해당 클래스는 안 옮긴다 | **유지(무영향)** |

`hub/bin/*.py` **글롭**으로 도는 검사 — 새 파일이 자동으로 검사 대상에 들어간다. 별도 조치
불필요하되, 새 파일이 규칙을 어기면 여기서 잡힌다:

| 줄 | 검사 | 새 모듈에 대한 의미 |
|---:|---|---|
| 3345 | T25-14 | serve 잔재 0건 — 새 파일도 자동 검사 |
| 4228 | T25-75 | 허브 무변경 역방향 검사 — 자동 |
| 4763 | **T25-100** | 800줄 상한 — **새 파일도 자동으로 상한 적용**(hub_config 75줄·hub_atomic_write 56줄로 문제없음) |
| 5247 | T25-121 | `server_collect_interval_seconds` 리터럴이 **정확히 1건**. 그 1건은 `_DEPRECATED_CONFIG_FIELD_GUIDANCE`(L98–102, 이동 영역 A 안) → 이동 후에도 hub/bin 합계 1건 유지 → **통과, 조치 불필요.** (검사 주석은 파일명을 특정하지 않고 상수 이름만 말하므로 이동해도 서술이 여전히 참이다 — 확인함) |
| 5364 | T25-123 | `collect_stalled` 0건 — 자동 |

배포 파일 수 계약 — **`hub/install.sh` 에 있다**(루트 `install.sh` 는 허브를 전혀 모른다,
T25-2 가 그것을 강제한다):

| 지점 | 현재 값 | 조치 |
|---|---|---|
| `hub/install.sh:12` `readonly HUB_FILE_COUNT=19` | 19 | **21 로 변경.** 복사 자체는 `find -maxdepth 1 -type f` 글롭이라(L134-139) 새 파일이 자동 배포된다 — 이 상수는 검증용이다 |
| `tests/run.sh:3218` T25-1 | 선언값 == 실제 파일 수 | 상수만 바꾸면 자동 통과 |
| `tests/run.sh:3238` T25-2 | 설치 결과 파일 수 == 선언값 | 자동 통과 |
| `tests/run.sh:5871` T25-149 | `-ne 19` | **`-ne 21`** 로 변경 + 주석의 이력 문구에 이번 회차 추가 |
| `tests/run.sh:5874` T25-149 | `hub/README.md` 에 `'19개 파일'` | **`'21개 파일'`** |
| `tests/run.sh:4826` T25-104 | 〃 | **`'21개 파일'`** |

문서 — 모듈 목록/파일 수를 적은 곳:

| 파일 | 줄 | 조치 |
|---|---:|---|
| `hub/README.md` | 53 | `19개 파일` → `21개 파일` |
| `hub/README.md` | 530–532 | 트리 주석의 `19개 파일(...)` → `21개 파일(...)`, 괄호 목록에 `hub_config.py`·`hub_atomic_write.py` 추가 + 출처로 이 문서 경로 추가 |
| `docs/prps/hub-dashboard.md` | 49·86·99 | **고치지 않는다.** 실측상 이 표는 이미 낡았다(`hub_collect.py ~180줄`, I/O 레이어 행에 `hub_usage_fetch.py`·`hub_workflow_read.py`·`hub_transcript.py` 누락). 이번 변경이 낡음을 더하지 않으며, 인접 문서 정비는 이 작업의 범위가 아니다(Karpathy #3). T25-104 는 이 파일에서 `hub_session.py` 존재만 보므로 무영향 |
| 루트 `README.md` | — | 허브 모듈 수를 적지 않는다(실측: `개 파일` 언급은 rules/commands 것뿐) → 무영향 |

---

## 3. 채택한 분리 경계

**두 개의 새 모듈을 만든다. 둘 다 `hub_collect.py` 가 임포트하는 단방향 하류 모듈이다.**

```
hub_collect.py ──imports──▶ hub_config.py        (★순수, 신설)
       │
       └────────imports──▶ hub_atomic_write.py   (I/O 유틸, 신설, 허브 모듈 무의존 잎)
```

역방향 간선은 만들지 않는다. `hub_config.py`·`hub_atomic_write.py` 는 **어떤 허브 모듈의
상수도 참조하지 않는다** — 그래서 §2.4 의 잠복 `ImportError` 가 구조적으로 불가능하다.
(`hub_config.py` 는 `hub_model` 만 임포트한다. `hub_model` 은 `hub_config` 를 임포트하지
않으므로 순환이 아니다.)

### 3.1 왜 이 경계인가

1. **`HUB_HOME` 은 절대 옮기지 않는다**(§2.5). 이 제약이 후보 공간을 결정한다. `HUB_HOME`
   아래에 쓰는 함수를 다른 모듈로 옮기면 그 모듈은 `hub_collect.HUB_HOME` 을 참조해야 하고,
   `hub_collect` 가 그 모듈을 임포트하면 순환이 된다. **A·B 는 `HUB_HOME` 을 전혀 쓰지
   않는 유일한 후보다** — `load_config` 는 `CONFIG_PATH` 만, `_atomic_write_text` 는 인자로
   받은 `directory` 만 쓴다.
2. **호출부 변경면이 0 이다.** A·B 모두 `hub_collect.py` **안에서만** 쓰이는 private
   심볼과 상수다. `hub.py`·`hub_server.py`·`hub_daemon.py`·`hub_hook.py`·`hub_statusline.py`
   는 **한 줄도 바뀌지 않는다.** `load_config()` 의 시그니처도 그대로다. "동작을 1비트도
   바꾸지 않는다"를 가장 강하게 담보하는 경계다.
3. **A 는 순수 로직이 I/O 모듈에 갇힌 레이어 위반의 해소다.** 프로젝트 CLAUDE.md 는 "외부
   세계에 닿는 코드와 순수 로직을 분리한다"를 명시한다. `_validate_config_overrides`·
   `_clamp_interval_overrides` 와 세 개의 스키마 테이블은 dict→dict 순수 변환인데
   `hub_collect.py`(I/O 레이어)에 있다. 실측으로 `open(`/`Path(`/`os.` 0건이므로 T25-10 의
   ★순수 계약을 그대로 만족한다.
4. **B 는 도메인 무관 유틸의 무단 점유 해소다.** `_atomic_write_text` 는 `hub.html`·
   `rate_limits.json`·`last_collect_error.json`·`last_usage_api_error.json`·`server.json`
   다섯 종류의 파일에 쓰인다 — "3티어 읽기·스냅샷 조립" 이라는 `hub_collect.py` 의 선언된
   책임 어디에도 속하지 않는 공통 기반이다. 56줄 중 대부분이 **왜 이렇게 하는지**를 적은
   docstring(서로게이트 처리 근거, 고유 임시파일 근거)이라, 함께 옮기면 `hub_collect.py` 의
   서사가 그만큼 짧아진다.

### 3.2 왜 한 개가 아니라 두 개인가 (여유 산정)

| 안 | 결과 줄 수 | 800 대비 여유 | §2.2 분포로 본 판정 |
|---|---:|---:|---|
| A 만 | 774 | 26 | 11회 중 3회만 견딤 — **다음 기능에서 다시 막힐 확률이 높다** |
| B 만 | 793 | 7 | 요구는 만족하나 사실상 무의미 |
| **A + B (채택)** | **718** | **82** | 관측 최대치(+64)를 한 번 견디고, 중앙값 기준 ~2.6회 |

실측 방법: 원본을 고치지 않고 메모리에서 두 구간을 잘라 센 뒤, 부대 증감(`import tempfile`
제거 −1 / `load_config` 본문 1줄 축약 −1 / 새 import 2줄 +2 = ±0)을 더했다.

두 번째 모듈은 "혹시 몰라서"가 아니라 **측정된 성장률에 대한 응답**이다. B 의 추가 비용은
외부 참조 2건 수정과 새 파일 1개뿐이라(§2.3), 여유를 26 → 82 로 세 배 늘리는 값으로는
싸다. 반대로 세 번째 모듈은 만들지 않는다 — 82줄이면 근거 있는 여유고 그 이상은 추측이다
(YAGNI).

---

## 4. 새 모듈의 이름·docstring 초안·책임

### 4.1 `hub/bin/hub_config.py` — ★순수

```python
"""hub_config.py — config.json 의 스키마와 검증 규칙(★순수).

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_config.py 대상,
tests/run.sh T25-10 이 기계적으로 강제한다). `config.json` 을 **읽는** 쪽은 여전히
hub_collect.load_config 다 — CONFIG_PATH 는 HUB_HOME 계열 상수와 함께 hub_collect.py 에
남는다. 여기 있는 것은 "이미 읽어 온 dict 를 HubConfig 로 바꾸는 규칙"뿐이다.

hub_collect.py 에서 분리했다 — main(세션 트리)과 워크플로우 가시성을 통합하며 849줄이 되어
800줄 상한(docs/prps/hub-model-module-split.md 결정 MS1)을 넘었고, 그 파일에서 유일하게
파일시스템에 닿지 않는 덩어리가 이것이었다(docs/prps/hub-collect-split-for-merge.md).
hub_usage.py(★순수 파서) / hub_usage_fetch.py(I/O), hub_workflow.py(★순수) /
hub_workflow_read.py(I/O) 가 세운 "순수 규칙 + I/O 호출자" 배치를 그대로 잇는다.

HubConfig 자체(대외 계약)는 hub_model.py 에 그대로 둔다 — 계약과 검증 규칙은 다른 것이고,
hub_model.py 는 hub_template.html 과의 계약 창구라는 자기 역할이 이미 있다.
"""
```

**책임**: 사용자가 적은 임의 dict → `(HubConfig, 경고 튜플)`. 알 수 없는/폐기된 키 안내,
필드 타입 검증, 주기 필드 하한 clamp.
**비책임**: 파일 읽기, 경로 결정, 경고의 출력.

이동하는 것 (`hub_collect.py` L78–152, 75줄 전부):

| 심볼 | 이동 후 가시성 | 비고 |
|---|---|---|
| `_CONFIG_FIELD_TYPES` | private 유지 | 머리 주석(bool/int 오탐 근거) 함께 이동 |
| `_DEPRECATED_CONFIG_FIELD_GUIDANCE` | private 유지 | T25-121 이 세는 `server_collect_interval_seconds` 리터럴 1건이 여기 있다 |
| `MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS` | **public** | 테스트가 이름으로 참조한다(실측 2건) |
| `MIN_USAGE_API_POLL_INTERVAL_SECONDS` | **public** | 〃 |
| `_INTERVAL_FIELD_MINIMUMS` | private 유지 | |
| `_clamp_interval_overrides` | private 유지 | 모듈 안에서만 쓰인다 |
| `_validate_config_overrides` | private 유지 | 〃 |
| — | **신규 public** | `config_from_raw`(아래 §5.1) |

이동하지 않는 것: `CONFIG_PATH`, `load_config`.

### 4.2 `hub/bin/hub_atomic_write.py` — I/O 유틸(★순수 아님)

```python
"""hub_atomic_write.py — 텍스트 파일 원자적 교체 + UTF-8 인코딩 안전 정규화.

허브의 모든 파일 쓰기가 지나는 단 하나의 관문이다 — hub.html · rate_limits.json ·
last_collect_error.json · last_usage_api_error.json · server.json 이 전부 여기를 지난다.
도메인을 모른다: 무엇을 쓰는지가 아니라 "어떻게 안전하게 바꿔치는지"만 안다.

★순수가 아니다 — tempfile·os.fdopen 을 쓴다. tests/run.sh T25-10 의 순수 파일 목록에
넣지 말 것.

hub_collect.py 에서 분리했다(docs/prps/hub-collect-split-for-merge.md). 849줄이 된 그
파일에서, 선언된 책임("프로젝트 발견 · 3티어 읽기 · 스냅샷 조립 · hub.html 원자적 쓰기")
중 마지막 항목의 **기반 기계**만 떼어낸 것이다. 어떤 허브 모듈도 임포트하지 않는 잎이라
(hub_server_state.py 와 같은 계약) 순환이 구조적으로 불가능하다 — 반대로 이 모듈이
hub_collect.HUB_HOME 같은 상수를 참조하기 시작하면 임포트 순서에 따라 터지는 순환이 된다.
"""
```

**책임**: 고유 임시파일 생성 → 인코딩 안전 정규화 → `Path.replace` 로 원자적 교체.
실패 시 임시파일 정리 후 예외 재전파.
**비책임**: 디렉터리 생성(`mkdir` 은 호출자 몫 — 현행 그대로), 실패 흡수, 경로 결정.

이동하는 것 (`hub_collect.py` L623–678, 56줄 전부):

| 심볼 | 이동 후 이름 | 비고 |
|---|---|---|
| `_LONE_SURROGATE_PATTERN` | 동일(private) | |
| `_LONE_SURROGATE_REPLACEMENT` | 동일(private) | U+FFFD 이스케이프 표기 유지 |
| `_encode_safe_utf8` | 동일(private) | 모듈 경계를 넘지 않는다 |
| `_atomic_write_text` | **`atomic_write_text`**(public) | 경계를 넘으므로 언더스코어를 뗀다 |

---

## 5. 인터페이스 (타입 명시)

### 5.1 `hub_config.py`

```python
MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS: int = 1
MIN_USAGE_API_POLL_INTERVAL_SECONDS: int = 60


def config_from_raw(
    raw: dict, defaults: hub_model.HubConfig
) -> tuple[hub_model.HubConfig, tuple[str, ...]]:
    """읽어 온 config.json dict 를 HubConfig 로 바꾸고 경고를 함께 돌려준다(★순수).

    타입 검증(검수 m5) → 주기 하한 clamp(결정 AR6) → dataclasses.replace 순서다.
    경고 문자열은 경로를 담지 않는다 — 경로가 붙는 경고(JSON 파싱 실패 등)는 파일을
    읽는 쪽(hub_collect.load_config)이 만든다.
    """
```

내부(private, 시그니처는 현행 그대로 이동):

```python
def _validate_config_overrides(raw: dict, defaults: hub_model.HubConfig) -> tuple[dict, tuple[str, ...]]
def _clamp_interval_overrides(overrides: dict) -> tuple[dict, tuple[str, ...]]
```

### 5.2 `hub_atomic_write.py`

```python
def atomic_write_text(final_path: Path, directory: Path, prefix: str, text: str) -> None:
    """directory 안 고유 임시파일에 text 를 쓰고 final_path 로 원자적으로 교체한다."""
```

시그니처·동작·예외 전파는 현행 `_atomic_write_text` 와 **완전히 동일**하다.

### 5.3 `hub_collect.py` 에 남는 `load_config` (시그니처 불변)

```python
def load_config() -> tuple[hub_model.HubConfig, tuple[str, ...]]:
    """~/.claude/hub/config.json 을 읽는다. 없거나 깨졌으면 기본값 전부.
    필드 타입·주기 하한 검증은 hub_config.config_from_raw(★순수)에 위임한다."""
    defaults = hub_model.HubConfig()
    if not CONFIG_PATH.exists():
        return defaults, ()
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults, (f"{CONFIG_PATH}: JSON 파싱 실패 — 기본값을 씁니다",)
    if not isinstance(raw, dict):
        return defaults, (f"{CONFIG_PATH}: 최상위 값이 객체가 아니라 기본값을 씁니다",)
    return hub_config.config_from_raw(raw, defaults)
```

세 개의 조기 반환과 그 경고 문자열은 **한 글자도 바뀌지 않는다**.

### 5.4 데이터 모델

**새 데이터 모델을 만들지 않는다.** 모듈 간 통신은 이미 존재하는 명시적 타입으로만 한다.

| 경계 | 넘나드는 타입 |
|---|---|
| `hub_collect` → `hub_config` | `dict`(json.loads 결과) · `hub_model.HubConfig`(기본값) |
| `hub_config` → `hub_collect` | `tuple[hub_model.HubConfig, tuple[str, ...]]` |
| `hub_collect` → `hub_atomic_write` | `Path` · `str` |

새 dataclass 를 도입하지 않은 이유: 옮기는 것은 **구현**이지 계약이 아니다. `HubConfig` 는
이미 `hub_model.py` 의 대외 계약이고, 경고는 이미 `tuple[str, ...]` 로 흐른다. 여기에
`ConfigLoadResult` 같은 래퍼를 새로 만들면 호출부 8곳이 전부 바뀌어 "동작 불변" 담보가
약해진다(YAGNI).

---

## 6. 영향 범위 — 수정/추가 파일 전수

### 6.1 소스

| 파일 | 변경 | 이유 |
|---|---|---|
| `hub/bin/hub_config.py` | **신규(≈95줄 예상)** | §4.1 |
| `hub/bin/hub_atomic_write.py` | **신규(≈70줄 예상)** | §4.2 |
| `hub/bin/hub_collect.py` | L78–152 삭제 · L623–678 삭제 · `import hub_atomic_write`·`import hub_config` 추가 · `import tempfile` 제거 · `load_config` 본문 위임 · `_atomic_write_text(` 호출 **5곳**(L521·693·720·754·813)을 `hub_atomic_write.atomic_write_text(` 로 · 모듈 docstring 에 분리 사실 1문단 추가 | 849 → **718줄(목표)** |

**import 변경이 필요한 파일은 `hub_collect.py` 하나뿐이다**(실측 근거 §2.3·§3.1-2).
`hub.py`·`hub_server.py`·`hub_daemon.py`·`hub_hook.py`·`hub_statusline.py`·
`hub_settings.py`·`hub_workflow_read.py`·`hub_usage_fetch.py` — **전부 무변경**.

### 6.2 테스트

| 파일 | 변경 |
|---|---|
| `tests/hub/test_hub_collect.py` | ① L1107·L1115 의 `hub_collect.MIN_*` → `hub_config.MIN_*`(+`import hub_config`) ② L967 `mock.patch.object(hub_collect, "_atomic_write_text", …)` → `mock.patch.object(hub_atomic_write, "atomic_write_text", …)` ③ L161 docstring 의 `_atomic_write_text` 언급을 새 이름·모듈로 ④ `LoadConfigValidationTest` 12개 중 **8개 이관**(§6.3) ⑤ `WriteHubHtmlSurrogateHandlingTest` 의 순수 정규화 단언 일부 이관(§6.3) |
| `tests/hub/test_hub_config.py` | **신규** — 이관된 스키마 케이스를 `hub_config.config_from_raw(raw, defaults)` 직접 호출로 재작성(임시 디렉터리 불필요) |
| `tests/hub/test_hub_atomic_write.py` | **신규** — `atomic_write_text` 동시 쓰기 무손상·임시파일 잔여 0·고립 서로게이트 U+FFFD 치환 |

모듈 1:1 테스트 관례(`docs/prps/hub-model-module-split.md` 결정 MS9, T25-103 이 기존 3개에
대해 강제)를 새 모듈 2개에도 적용한다.

### 6.3 테스트 이관 상세 — 무엇을 옮기고 무엇을 남기는가

`LoadConfigValidationTest`(L1018–1144, 12 케이스):

| 케이스 | 성격 | 조치 |
|---|---|---|
| `test_no_config_file_returns_defaults_without_warnings` | 파일 계약 | **잔류** |
| `test_broken_json_returns_defaults_with_warning` | 파일 계약 | **잔류** |
| `test_wrong_type_field_falls_back_to_default_with_warning` | 스키마 | **잔류 — 이음매 테스트** |
| `test_deprecated_field_warns_with_replacement_guidance` | 스키마 | 이관 |
| `test_deprecated_collect_interval_field_warns_with_replacement_guidance` | 스키마 | 이관 |
| `test_heartbeat_interval_wrong_type_falls_back_to_default_with_warning` | 스키마 | 이관 |
| `test_unknown_field_warns_generically` | 스키마 | 이관 |
| `test_case25_show_usage_panel_wrong_type_falls_back_to_default_with_warning` | 스키마 | 이관 |
| `test_ar6_heartbeat_interval_below_minimum_is_clamped_with_warning` | 스키마 | 이관 |
| `test_ar6_usage_api_poll_interval_below_minimum_is_clamped_with_warning` | 스키마 | 이관 |
| `test_ar6_no_override_leaves_defaults_untouched_without_clamp_warning` | 스키마 | 이관(순수 호출이면 `config_from_raw({}, …)` 로 단순해진다 — 원본 docstring 이 설명하는 "빈 객체를 파일에 써야 조기 반환을 피한다"는 우회가 불필요해진다) |
| `test_ar6_boundary_values_at_minimum_are_not_clamped` | 스키마 | 이관 |

> **`test_wrong_type_field_…` 을 남기는 이유(중요).** 스키마 케이스를 **전부** 옮기면
> `load_config` 가 실제로 `config_from_raw` 를 부르는지 증명하는 테스트가 하나도 남지
> 않는다 — 남는 두 케이스는 모두 조기 반환 경로라 위임 지점에 도달하지 않기 때문이다.
> 한 건을 파일 경유 그대로 남겨 이음매를 고정한다(T25-118 이 지키는 "이음매 테스트"와
> 같은 관용구).

`WriteHubHtmlSurrogateHandlingTest`(L157–221): `write_hub_html` 은 `hub_collect` 에 남으므로
클래스 자체는 **잔류**한다. 다만 "고립 서로게이트가 U+FFFD 로 치환된다"는 **정규화 규칙
자체**의 단언은 `test_hub_atomic_write.py` 에 직접 케이스로 새로 두고, 잔류분은
"write_hub_html 이 예외 없이 유효한 UTF-8 파일을 낸다"는 이음매 확인으로 유지한다.
`WriteHubHtmlAtomicityTest`(L118–156)도 같은 이유로 잔류하며, 동시 쓰기 무손상 성질은
새 파일에서 `atomic_write_text` 를 직접 두들겨 다시 고정한다.

### 6.4 배포·검사·문서

| 파일 | 변경 |
|---|---|
| `hub/install.sh` | `HUB_FILE_COUNT=19` → `21` (L12) |
| `hub/README.md` | `19개 파일` → `21개 파일`(L53·L530) + 트리 주석 괄호 목록에 새 모듈 2개와 이 문서 경로 추가 |
| `tests/run.sh` | §2.6 표 + §7(신설 가드) + §9(라벨 재번호) |

---

## 7. `tests/run.sh` 변경 — 검사별 조치표

### 7.1 기존 검사 수정 (4건)

| 검사 | 수정 내용 |
|---|---|
| **T25-10** | ★순수 파일 목록에 `$hub_config_file` 추가. 실측으로 이동 영역에 `open(`/`Path(`/`os.` 0건이므로 통과한다. `hub_atomic_write.py` 는 **넣지 않는다**(tempfile·os.fdopen 사용) |
| **T25-61** | `grep -qF '"usage_api_enabled": bool' "$hub_collect_file"` → `"$hub_config_file"`. 실패 메시지의 `hub_collect.py 의 _CONFIG_FIELD_TYPES` 도 `hub_config.py 의 _CONFIG_FIELD_TYPES` 로 |
| **T25-104** | `'19개 파일'` → `'21개 파일'`(정방향 1곳). 역방향 `'12개 파일'` 검사는 그대로 |
| **T25-149** | `-ne 19` → `-ne 21`, `'19개 파일'` → `'21개 파일'`, 머리 주석 이력에 `19 → 21(docs/prps/hub-collect-split-for-merge.md)` 추가 |

변수 선언부(L3199 부근)에 2줄 추가:

```bash
local hub_config_file="$REPO_ROOT/hub/bin/hub_config.py"
local hub_atomic_write_file="$REPO_ROOT/hub/bin/hub_atomic_write.py"
```

### 7.2 신설 가드 (2건 — 최소로 유지)

**T25-167(정+역, 되돌림 방지 — T25-101 관용구)**
- 정: `hub_config.py`·`hub_atomic_write.py` 가 존재한다.
- 역: `hub_collect.py` 에 `def _validate_config_overrides(`·`def _clamp_interval_overrides(`·
  `_CONFIG_FIELD_TYPES`·`def _encode_safe_utf8(`·`def _atomic_write_text(` 정의가 **없다**.
  (이동한 심볼이 되살아나면 두 벌이 갈라져 실사용 경로와 테스트 대상이 달라진다 —
  `read_server_record` 가 겪었던 검수 m3 와 같은 실패 모드다.)

**T25-168(역, 조용한 무력화 방지 — 이번 설계 고유의 위험)**
- `hub_collect.py` 에 `^from hub_atomic_write import` 가 **없다**.
- `hub_collect.py` 의 `hub_atomic_write.atomic_write_text(` 호출이 **정확히 5건**이다.

> 왜 필요한가: `test_hub_collect.py` 가 `mock.patch.object(hub_atomic_write,
> "atomic_write_text", side_effect=OSError)` 로 "실패 기록 자체가 실패해도 예외를 던지지
> 않는다"를 검증한다. `hub_collect` 가 `from hub_atomic_write import atomic_write_text` 로
> 이름을 자기 네임스페이스에 복사해 두면 이 패치가 **아무 효과 없이 통과**한다 — 테스트는
> 초록인데 검증은 사라진다. 정규화된 호출을 정적으로 못 박는다.

### 7.3 조치 불필요한 것 (근거를 남긴다)

T25-18·T25-54·T25-72·T25-112·T25-118·T25-138·T25-139 는 §2.6 표대로 앵커가 전부
`hub_collect.py` 에 잔류하므로 무영향이다. **특히 T25-72 의 sed 종료 앵커
`# ---- 합성 ----`(L571)과 T25-139 의 awk 앵커 `def read_template_stamp() -> str:` 는
문자 그대로 보존해야 한다** — 삭제하면 추출 결과가 비어 검사가 실패 대신 **공허하게
통과**한다. 구현 시 이 두 줄을 건드리지 않는지 diff 로 확인한다.

---

## 8. 기각한 후보와 근거

**기각 1 — `tests/run.sh` 의 800 상수를 올린다.**
800줄은 `docs/prps/hub-model-module-split.md` 결정 MS1 이 세운 문서화된 설계 규칙이고, 이
저장소는 이미 두 번(MS1 의 3개 분리, `hub_workflow_read.py`) 그 규칙에 따라 쪼갰다.
`hub_collect.py` 의 모듈 docstring 자체가 "800/800줄 상한에 닿아 여유가 없었다"를 분리
사유로 적고 있다. 상수를 올리면 그 두 번의 분리가 소급해서 근거를 잃는다. **분리가 기본값
이라는 과제 지시와도 일치한다.**

**기각 2 — 실패 기록(D) + 상주 서버 상태(E) 파일 I/O 분리.**
*가장 응집도 높은 후보였고, 채택하지 않은 것이 아쉬운 유일한 안이다.* 근거는 셋이다.
(a) **응집도는 최고다**: 이 145줄은 `collect_snapshot` 이 한 번도 부르지 않는다 —
`hub_collect.py` 의 자기 선언 책임("프로젝트 발견·3티어 읽기·스냅샷 조립·hub.html 쓰기")
어디에도 속하지 않는 순수 squatter 이며, 프로세스 간 신호 파일이라는 하나의 이름으로
설명된다. 여유도 최대다(→ 675줄).
(b) **그러나 `HUB_HOME` 을 쓴다.** 세 함수가 `HUB_HOME.mkdir()` + `_atomic_write_text(...,
HUB_HOME, ...)` 를 한다. `HUB_HOME` 은 옮길 수 없으므로(§2.5) 새 모듈이 `hub_collect` 를
역참조해야 하고, 이는 §2.4 에서 실측한 **임포트 순서 의존 `ImportError`** 의 씨앗이 된다.
(c) **변경면이 §3 안의 25배다.** 옮겨야 할 모듈 상수 참조가 실측 99건
(`COLLECT_SUCCESS_STAMP_PATH` 22 · `SERVER_HEARTBEAT_PATH` 21 · `LAST_COLLECT_ERROR_PATH` 21
· `LAST_USAGE_API_ERROR_PATH` 16 · `SERVER_RECORD_PATH` 10 · `SPAWN_STAMP_PATH` 6 ·
`SERVER_LOG_PATH` 3), 함수 호출 지점이 약 50건이다. 그중 54건이 `mock.patch.object` 가 아닌
**직접 대입**이라 하나만 놓쳐도 조용히 실제 홈에 쓴다(§2.5). "동작을 1비트도 바꾸지
않는다"가 요구인 회차에 맞는 위험 프로파일이 아니다.
→ **보류이지 폐기가 아니다.** 다음번 상한 압박 때의 1순위 후보로 이 문단을 남긴다. 그때는
`hub_atomic_write.py` 가 이미 존재하므로 (b)의 절반은 해소돼 있다(남는 것은 `HUB_HOME`
하나뿐이고, 그때는 `hub_home` 을 인자로 받는 방식을 검토할 수 있다).

**기각 3 — 한도 캡처 I/O(C) 분리.**
`_capture_for_snapshot` 을 `collect_snapshot` 이 부르므로 `hub_collect` → 새 모듈 간선이
생기는데, `write_rate_limit_capture` 가 `HUB_HOME.mkdir()` 을 하므로 새 모듈 → `hub_collect`
간선도 필요하다. **양방향 = 순환.** §2.4 실측대로 런타임에 즉시 죽지는 않지만 임포트 순서에
따라 터지는 잠복 결함이 되고, 프로젝트 CLAUDE.md 의 순환 금지 규칙에 정면으로 걸린다.
게다가 61줄뿐이라 여유가 11줄에 그친다.

**기각 4 — config 도메인 전체(`CONFIG_PATH`·`load_config` 포함)를 `hub_config.py` 로.**
개념적으로는 더 깔끔하다("config 는 한 모듈에"). 그러나 (a) `hub_collect.CONFIG_PATH` 참조
42건을 전부 옮겨야 하고(§2.5 의 조용한 실패 위험), (b) `hub_config.py` 가
`Path.home() / ".claude" / "hub" / "config.json"` 을 다시 적어야 해서 허브 홈 경로가 두 곳에
생기며, (c) `load_config()` 호출부 7곳(production)이 바뀐다. §3 의 안은 같은 여유를 얻으면서
이 셋을 전부 피한다. **경로를 아는 것은 I/O 레이어의 일이고, 규칙을 아는 것은 순수
레이어의 일** — 레이어 원칙과도 §3 쪽이 더 맞는다.

**기각 5 — `HUB_HOME` 을 공용 모듈로 뽑는다.**
참조 61건이고, 테스트가 직접 대입으로 격리하는 축이라 하나만 놓치면 실제 사용자 홈에 쓴다.
`bash tests/run.sh` 는 전역 HOME 샌드박스로 막아 주지만 `python3 -m unittest` 직접 실행은
막지 못한다(§2.5 실측). 얻는 것(여유 몇 줄)에 비해 잃을 수 있는 것이 사용자 파일이다.

**기각 6 — 한 모듈만 뽑는다(A 만 또는 B 만).**
§3.2 표대로 여유가 각각 26·7줄이다. 측정된 기능당 중앙값 증가가 +31줄이므로 다음 기능에서
같은 실패가 재발한다. 이 작업을 한 번 더 하게 만드는 선택이다.

---

## 9. T25 라벨 재번호 방침

### 9.1 실측 — 중복은 정확히 3건이다

`tests/run.sh` 의 모든 `note_failure`/`record_failure` 첫 인자에서 `T\d+-\d+` 를 뽑아 전수
조사했다. **멀리 떨어진 두 블록에 같은 라벨이 나타나는 것은 T25-156·157·158 뿐이다**
(T22 를 포함해 다른 중복 없음).

| 라벨 | 세션 트리 블록(main) | 워크플로우 블록(이 브랜치) | 간격 |
|---|---|---|---:|
| T25-156 | L5999·6002·6005 | L6203·6206·6223·6230 | 198줄 |
| T25-157 | L6012·6015·6022 | L6240·6243 | 218줄 |
| T25-158 | L6035·6038 | L6318·6346 | 280줄 |

**실행 영향은 없다(확인함)** — `note_failure`/`record_failure` 는 라벨을 해석하지 않고 문자열
그대로 배열에 append 한다(L138-144·L157-160). 즉 이것은 **진단 가능성** 문제다: 실패
메시지만 보고는 그 `T25-158` 이 워크플로우 상한 래칫인지 대시보드 경로 정합인지 구별할 수
없다. 정적 가드로 회귀를 못 박는 이 저장소의 문화와 어긋나므로 고친다.

### 9.2 방침 — **워크플로우 트리오를 T25-164/165/166 으로 옮긴다**

| 현재 | 변경 | 대상 블록 |
|---|---|---|
| T25-156 (L6197~6230) | **T25-164** | `renderWorkflowChip` escapeHtml 회귀 + 에이전트 필드 헬퍼 외부 참조 |
| T25-157 (L6233~6243) | **T25-165** | `hub_workflow.py`·`hub_redact.py` ★순수 계약 |
| T25-158 (L6246~6346) | **T25-166** | 계약 A 문자열 상한 정적 래칫 |

세션 트리 쪽(T25-156~163)을 그대로 두는 이유:
1. **연속 블록이고 문서가 표로 고정한다.** `docs/prps/hub-session-tree-and-per-session-dashboards.md`
   §14(L945–952)가 T25-156~163 을 8행 표로 적고, 본문 6곳이 개별 라벨을 인용한다. 옮기면
   14곳 이상을 고쳐야 한다.
2. **워크플로우 쪽은 3개뿐이고 인용도 6곳이다**(`docs/prps/hub-workflow-visibility.md`
   L304·387·1110·1162·1176·1180·1204).
3. **파일 순서 = 번호 순서가 유지된다.** 워크플로우 블록이 세션 트리 블록보다 뒤(L6197 >
   L6193)에 있으므로 164~166 을 주면 오름차순이 그대로다.

### 9.3 함께 고칠 곳

| 파일 | 줄 | 조치 |
|---|---:|---|
| `tests/run.sh` | 3189·3193 | 그룹 헤더 `T25-1~T25-163` → `T25-1~T25-168`(재번호 166 + 신설 167·168) |
| `tests/run.sh` | 6197~6346 | 블록 안의 라벨 문자열 9건과 머리 주석을 164/165/166 으로 |
| `docs/prps/hub-workflow-visibility.md` | 304·387·1110·1162·1176·1180·1204 | 인용 라벨 갱신 + "리베이스 통합 시 T25-156~158 → T25-164~166 으로 재번호" 한 줄 각주 |
| `docs/prps/hub-session-tree-and-per-session-dashboards.md` | 935 등 | **고치지 않는다.** 그 문서는 자기 회차에 무엇을 했는지의 **기록**이고, 라벨도 그대로 유지되므로 서술이 여전히 참이다(헤더 범위 문장만 낡는데, 완료된 PRP 의 시점 기술로 남기는 편이 이 저장소 관례에 맞다) |

---

## 10. 테스트·검증 계획

### 10.1 순수 로직 단위 테스트 (새로 쓰는 것)

`tests/hub/test_hub_config.py` — `config_from_raw(raw, defaults)` 직접 호출, 파일시스템 무접촉:

| 케이스 | 입력 | 기대 |
|---|---|---|
| 알 수 없는 키 | `{"typo_field": 1}` | 기본값 전부 + 경고 1건에 "오타인지 확인" |
| 폐기 키 안내 | `{"serve_port_candidates": [1]}` | 경고에 `'server_port' 로 대체` |
| 폐기 키 안내 2 | `{"server_collect_interval_seconds": 5}` | 경고에 `'server_heartbeat_interval_seconds' 로 대체` |
| 타입 불일치 | `{"roots": "not-a-list"}` | 해당 필드만 기본값 + 경고 1건 |
| 타입 불일치(bool) | `{"show_usage_panel": 1}` | 기본값 + 경고 |
| list → tuple 정규화 | `{"roots": ["/a", "/b"]}` | `config.roots == ("/a", "/b")` |
| 하한 clamp | `{"server_heartbeat_interval_seconds": 0}` | `MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS` + 경고 |
| 하한 clamp 2 | `{"usage_api_poll_interval_seconds": 1}` | `MIN_USAGE_API_POLL_INTERVAL_SECONDS` + 경고 |
| 경계값 | 하한과 정확히 같은 값 | clamp 되지 않고 경고 0건 |
| override 없음 | `{}` | 기본값 그대로, 경고 0건 |
| 타입 불일치 필드는 clamp 대상이 아니다 | `{"server_heartbeat_interval_seconds": "x"}` | 기본값 + **타입 경고 1건만**(clamp 경고 없음) |
| 경고 순서 | 타입 경고 + clamp 경고 동시 발생 | 타입 경고가 먼저(현행 `type_warnings + clamp_warnings` 순서 고정) |

`tests/hub/test_hub_atomic_write.py` — `atomic_write_text` 직접 호출:

| 케이스 | 기대 |
|---|---|
| 동시 쓰기(스레드 N개) | 최종 파일이 항상 어느 한 호출의 완전한 내용 — 뒤섞인 산출 없음 |
| 성공 후 임시파일 | `directory` 에 `.tmp` 잔여 0개 |
| 고립 서로게이트 포함 텍스트 | 예외 없이 성공하고, 읽으면 U+FFFD 로 치환돼 있으며 나머지 문자는 보존 |
| 쓰기 도중 실패(mkstemp 이후 예외 주입) | 임시파일이 남지 않고 예외가 그대로 전파되며 `final_path` 는 이전 내용 유지 |

### 10.2 회귀 방지 — 이음매 테스트 (잔류)

- `test_hub_collect.py::LoadConfigValidationTest::test_wrong_type_field_…` —
  `load_config` → `config_from_raw` 위임이 실제로 일어남을 증명(§6.3).
- `test_hub_collect.py::WriteHubHtmlAtomicityTest` / `WriteHubHtmlSurrogateHandlingTest` —
  `write_hub_html` → `atomic_write_text` 위임 증명.
- `test_hub_collect.py::CollectFailureObservabilityTest::test_record_collect_failure_never_raises_when_write_itself_fails` —
  패치 대상만 새 모듈로 옮기고 성질은 그대로.

### 10.3 검증 명령 (프로젝트 실제 명령)

```
# 1) 파이썬 단위 테스트 (현행 613건 + 신규)
python3 -m unittest discover -s tests/hub -t .

# 2) 전체 스위트 — T25-100 을 포함한 정적 가드 전부
bash tests/run.sh

# 3) 크기 계약 직접 확인
wc -l hub/bin/*.py | sort -rn | head -5
```

### 10.4 완료 판정 (검증 가능한 목표)

1. `hub/bin/*.py` 전부 800줄 이하 → 검증: 위 명령 3, `hub_collect.py` 가 **718줄 내외**.
2. `bash tests/run.sh` 실패 0건 → 검증: 종료 코드 0.
3. **동작 불변** → 검증: `git diff` 에서 `hub/bin/` 중 `hub_collect.py` 외 기존 파일의
   변경이 **0줄**임을 확인(신규 2개 파일 제외). 이것이 이 회차의 가장 강한 불변식이다.
4. 새 정적 가드가 실제로 발화함 → 검증: 구현 후 `hub_collect.py` 에서 임시로
   `hub_atomic_write.atomic_write_text` 를 `from hub_atomic_write import atomic_write_text` +
   `atomic_write_text` 로 바꿔 T25-168 이 실패하는지 1회 확인하고 되돌린다(뮤테이션 확인 —
   `docs/prps/hub-workflow-visibility.md` 가 T25-158 에서 쓴 것과 같은 절차).
5. 라벨 중복 0건 → 검증: `note_failure`/`record_failure` 라벨 전수 스캔에서 멀리 떨어진
   중복 블록이 없다.

---

## 11. 리스크

| # | 리스크 | 심각도 | 완화 |
|---|---|---|---|
| R1 | `from hub_atomic_write import atomic_write_text` 형태로 쓰면 `mock.patch.object` 기반 테스트가 **초록인 채로 무력화**된다 | HIGH | T25-168 신설(§7.2) + §10.4-4 뮤테이션 확인 |
| R2 | T25-72 의 sed 종료 앵커(`# ---- 합성 ----`)나 T25-139 의 awk 앵커를 정리하다 지우면 검사가 **공허하게 통과** | MEDIUM | §7.3 에 명시 + 구현 후 두 앵커 존재를 diff 로 확인 |
| R3 | `hub_config.py` 가 나중에 파일시스템에 손대면 ★순수 계약이 깨진다 | MEDIUM | T25-10 목록에 편입(§7.1) — 기계적으로 강제된다 |
| R4 | 스키마 테스트를 순수 호출로 재작성하며 단언이 미묘하게 약해진다(예: 경고 **개수** 확인 누락) | MEDIUM | 이관은 케이스별 1:1로 하고, 각 케이스의 기존 단언(값 + 경고 개수 + 경고 문구 부분일치)을 **그대로** 옮긴다. 이관 전후로 총 테스트 개수를 비교 |
| R5 | 여유 82줄도 결국 부족해진다 | LOW | 측정 기반 선택이며(§3.2), 다음 후보(기각 2)를 근거와 함께 남겨 뒀다 |
| R6 | `hub_config.py` 에 불필요한 import(`json` 등)를 넣어 죽은 의존이 생긴다 | LOW | 실측상 필요한 것은 `dataclasses`·`hub_model` 뿐(§2.3) — 구현 시 확인 |
| R7 | 재번호가 `docs/prps/hub-workflow-visibility.md` 인용과 어긋난다 | LOW | §9.3 표대로 7곳 동시 수정 |

---

## 12. 명시적 비목표

- **800줄 상한 자체를 손대지 않는다.**
- **후보 C·D·E(한도 캡처·실패 기록·상주 서버 상태)를 이번에 옮기지 않는다.** 기각 근거는
  §8 에 남긴다.
- **`HUB_HOME` 을 비롯한 어떤 경로 상수도 옮기지 않는다.**
- **어떤 공개 함수의 시그니처·반환 타입·경고 문자열도 바꾸지 않는다.** `load_config()` 는
  인자 없는 형태 그대로다.
- **새 데이터 모델(dataclass)을 도입하지 않는다.**
- **`hub_collect.py` 에 남는 코드를 "정리"하지 않는다.** 주석 재배열, 인접 함수 리팩토링,
  타입 힌트 보강 전부 범위 밖이다 — 변경된 모든 줄이 이 문서의 이동 목록으로 추적돼야 한다.
- **`docs/prps/hub-dashboard.md` 의 낡은 모듈표를 고치지 않는다**(이미 낡았고, 이번 변경이
  악화시키지 않는다 — §2.6).
- **성능 최적화를 하지 않는다.** 이 작업은 순수 재배치다.

---

## 13. 승인이 필요한 결정

| # | 결정 | 대안 |
|---|---|---|
| **D1** | 새 모듈을 **2개**(`hub_config.py` ★순수 + `hub_atomic_write.py`) 만들어 849 → **718줄**(여유 82)로 내린다 | 1개만(A: 774줄/여유 26 — 측정된 중앙값 +31 에 못 미쳐 다음 기능에서 재발) |
| **D2** | 응집도 최고 후보인 **실패 기록·서버 상태 파일 I/O 분리는 보류**한다 — `HUB_HOME` 역참조로 순환이 생기고 변경면이 150건 이상이라 "동작 불변" 회차에 맞지 않는다(§8 기각 2) | 지금 감행(여유 125줄, 대신 조용한 홈 오염 위험) |
| **D3** | 중복 라벨은 **워크플로우 트리오(T25-156/157/158) → T25-164/165/166** 으로 옮긴다 | 세션 트리 쪽(156~163)을 옮긴다 — 문서 인용 14곳 이상 수정 필요 |
