> ⚠️ **실험 원본 — 승인된 설계가 아니다.**
> 이 문서는 모델·프롬프트 A/B 실험의 **실험 1 · B안(fable + 무스캐폴딩, general-purpose) · 44/50 승** 산출물이다.
> 여기 설계된 기능은 구현되지 않았고, 앞으로 구현할 계획도 없다.
> **저장소 선례로 인용하지 않는다.** 실험 설계·채점·결론은
> [`../model-scaffolding-ab-experiments.md`](../model-scaffolding-ab-experiments.md) 를 본다.
> 본문은 이 배너 블록 아래부터 서브에이전트 원본 그대로다(내용 무수정).

---

# PRP — 허브 플랜 사용률 추이 (최근 24시간)

> 설계 문서. **구현 코드는 이 문서에 없다.** 승인 후 `implementer` 가 이 문서를 입력으로 구현한다.
> 제안 파일명: `docs/prps/hub-usage-trend.md` (이번 산출물은 텍스트 반환 — 저장은 승인 후 구현 단계에서).
> 대상: `hub/bin/` + 관련 문서·테스트. 선행 정본:
> [`hub-dashboard.md`](./hub-dashboard.md) · [`hub-theme-and-usage-panel.md`](./hub-theme-and-usage-panel.md) ·
> [`hub-usage-reset-time-and-refresh.md`](./hub-usage-reset-time-and-refresh.md) ·
> [`hub-card-cleanup-and-usage-source.md`](./hub-card-cleanup-and-usage-source.md)(결정 P1~P8) ·
> [`hub-card-interactions-and-usage.md`](./hub-card-interactions-and-usage.md)(결정 A1~A7, 불변식 A-SEC) ·
> [`hub-onboarding-statusline-and-stale-usage.md`](./hub-onboarding-statusline-and-stale-usage.md)(결정 EX1~EX7).
>
> 이 PRP 는 기존 결정을 **개정하지 않는다** — P1(캡처 단일 출처)·P3(투영)·P4(변화 시에만 쓰기)·
> A2(두 생산자 공존)·EX 계열(stale 표시) 위에 "이력"이라는 새 층을 **추가**한다.
> 결정 번호 namespace: **TR**(trend). 테스트 케이스는 **TH1~**(기존 N·R·A·case 번호와 충돌 없음).
> 신규 T25 검사는 **T25-156~** (현재 최종 번호 T25-155, `tests/run.sh:2593`).

---

## 1. 요구사항 요약

허브는 현재 플랜 사용량(5시간/7일 창의 `used_percentage` 와 초기화 예정 시각)을 **현재 시점
값 하나**로만 수집·표시한다 — 캡처 파일 `~/.claude/hub/rate_limits.json` 은 항상 최신 관측
1건으로 **덮어써진다**(`hub_collect.write_rate_limit_capture`, `hub_collect.py:432-436`).
이 사용률의 시간 추이를 수집·보존해, 허브 사용량 패널에서 **최근 24시간의 추이 차트**를
볼 수 있게 한다.

- **R-1 (수집·보존)**: 사용률 퍼센트가 변할 때마다 `(관측 시각, 세션 %, 주간 %)` 1점을
  append-only 이력에 남긴다. 기존 두 생산자(statusLine·사용량 API 폴링) 어느 쪽의 관측이든
  같은 이력에 쌓인다.
- **R-2 (표시)**: 사용량 패널 펼침 본문에 최근 24시간 스텝 차트(세션·주간 2계열)를 그린다.
  값이 없으면 조용히 생략한다(패널의 기존 관례 — 초기화 시각 줄과 동일, 결정 R3 계열).
- **R-3 (기존 계약 불변)**: `rate_limits.json` 포맷, `RateLimitCapture`/`UsageSample`/
  `RateLimitResets` 타입, `#dzh-data` 마커 치환 방식, 불변식 H1⁗(`hub_template.html:27-31`),
  불변식 A-SEC(토큰 격리)은 그대로다. `HubSnapshot` 에는 **기본값 있는 필드 1개만 추가**한다.
- **R-4 (성능·쓰기 억제 불변)**: statusLine 정상 상태(값 불변)의 파일 I/O 0회
  (`hub_statusline.py:12-14`)와 hub.html 쓰기 억제(`snapshot_content_key`,
  `hub_model.py:80-84`)를 **깨뜨리지 않는다**. 이것이 이 설계의 최대 제약이다(§5.4).
- **R-5 (프라이버시·관측성)**: `show_usage_panel:false` 면 이력을 기록도 읽기도 하지 않는다.
  보존 기한을 두고, `/hub status` 로 이력 상태를 진단할 수 있게 한다.

**비목표**: 별도 HTTP 엔드포인트(화이트리스트 `ALLOWED_REQUEST_PATHS` 불변,
`hub_server.py:28-30`) · 리셋 시각의 이력화 · 7일/30일 등 다른 창 · 서버 사이드 차트 렌더 ·
새 config 필드 · 외부 라이브러리(차트 포함 — file:// 동작 요구, 결정 PV9 계열).

---

## 2. 실측으로 확인된 사실 (재조사 대상 아님)

### 2.1 생산자와 캡처 흐름

| # | 사실 | 위치 |
|---|------|------|
| F1 | 캡처 파일의 생산자는 둘: ① statusLine 진입점이 stdin 파싱 → 이전 캡처 읽기 → `same_capture_values` 비교 → 변화 시에만 쓰기 | `hub_statusline.py:26-35` |
| F2 | ② 상주 서버 유지보수 티커의 사용량 API 폴링 — 같은 읽기→비교→쓰기 시퀀스가 `_write_usage_api_capture` 에 **중복 구현**돼 있다 | `hub_server.py:278-292` |
| F3 | 두 생산자 모두 최종 쓰기는 `hub_collect.write_rate_limit_capture` 하나를 쓴다(원자적 교체) | `hub_collect.py:432-436`, `531-545` |
| F4 | `same_capture_values` 는 리셋 2 + 퍼센트 2 만 비교하고 `captured_at_ms` 는 절대 넣지 않는다(0.3초 주기 쓰기 폭주 방지, GOTCHA 4) | `hub_usage.py:282-296` |
| F5 | `captured_at_ms` 는 "이 값들을 **처음 관측한** 시각"(결정 S3) — 변화 시에만 쓰므로, 쓰인 캡처의 시각이 곧 새 값의 관측 시각이다 | `hub_usage.py:55`, `68` |
| F6 | statusLine 은 최대 0.3초마다 실행되고, 정상 상태(값 불변)에서 파일 쓰기 0회가 설계 목표로 명시돼 있다 | `hub_statusline.py:4-5`, `12-14` |
| F7 | 사용량 API 폴링은 `show_usage_panel`·`usage_api_enabled` **둘 다** 참일 때만, 기본 5분 주기(백오프 최대 60분) | `hub_server.py:305-307`, `hub_model.py:41-42`, `hub_usage.py:420-471` |
| F8 | API 캡처의 관측 시각도 폴링 시점의 벽시계다 | `hub_server.py:310`, `353-355` |

### 2.2 소비자(수집·렌더) 흐름

| # | 사실 | 위치 |
|---|------|------|
| F9 | `_capture_for_snapshot` 이 캡처 파일을 사이클당 1회 읽어 `UsageSample`·`RateLimitResets` 로 투영한다. `show_usage_panel:false` 면 **파일을 열지도 않는다**(전제 8) | `hub_collect.py:439-467`(게이트 453-454) |
| F10 | `HubSnapshot` 은 `usage`·`rate_limit_resets`·`template_stamp` 를 기본값 있는 필드로 갖고, `render_hub_html` 이 `asdict` 전체를 `#dzh-data` 에 인라인한다 | `hub_model.py:46-56`, `88-100` |
| F11 | `snapshot_content_key` 는 `collected_at_ms` **만** 제외한 전체 직렬화 — 같으면 hub.html 을 다시 쓰지 않는다. "지금" 파생값을 스냅샷에 실으면 이 억제가 무력화된다는 경고가 `UsageSample` 주석에 정본으로 남아 있다(결정 D3, 예외는 이산값 `is_stale` 뿐 — EX3·EX4) | `hub_model.py:80-84`, `hub_usage.py:37-48`, `hub_server.py:181` |
| F12 | 템플릿은 `renderUsagePanel(usage, resets)` 이 `#dzh-usage-body` innerHTML 을 통째로 갈아끼우는 구조이고, 폴링·30초 틱이 갱신해도 되는 노드 목록(불변식 H1⁗)에 `#dzh-usage-body` 가 이미 포함돼 있다 | `hub_template.html:27-31`, `1451-1459`, `1466-1488`, 호출부 `1548`·`1563`, 틱 `1629`(30초, `832`) |
| F13 | 템플릿의 "지금" 의존 계산(경과·남은 시간)은 전부 클라이언트가 `Date.now()` 로 한다 — 서버는 정적 값만 싣는다(결정 P6·R5 의 2차 필터 관례) | `hub_template.html:1030`, `1046`, `1359-1394` |
| F14 | 패널 폭 420px, 접힘 시 `.usage-body{display:none}` — 차트는 펼침에서만 보이면 된다 | `hub_template.html:389`, `403` |
| F15 | 색 토큰 `--accent`(#0072B2)·`--attention`(#B45309/#E69F00)은 라이트·다크 양쪽에 정의돼 있다(Okabe-Ito 파랑/주황 계열 — 색약 안전 쌍) | `hub_template.html:137-138`, `149`, `158` |

### 2.3 재사용할 기존 패턴

| # | 사실 | 위치 |
|---|------|------|
| F16 | 날짜별 append-only JSONL + 오늘·어제 읽기 + 관용 파싱(깨진 줄 탈락) + 파일명 날짜 기준 prune 패턴이 이벤트 로그에 이미 있다 | append `hub_hook.py:114-121`, 읽기 `hub_collect.py:172-205`, prune `hub_collect.py:289-301` |
| F17 | "짧은 줄 1회 write() = 사실상 원자적 append" 논거와 그 전제(줄 < 8192B 버퍼)가 기록돼 있다 — 동시 append 안전성의 정본 | `hub_hook.py:38-44`, `115` |
| F18 | 대용량 방어용 꼬리 읽기(seek from end + `errors="replace"` 디코딩, `UnicodeDecodeError`≠`OSError` 함정 명시)가 transcript 읽기에 있다 | `hub_collect.py:229-245` |
| F19 | prune 는 이벤트 append 시(훅)와 `collect_snapshot` 양쪽에서 불린다 — "최대 N일 보관" 고지의 성립 조건 | `hub_hook.py:171-173`, `hub_collect.py:490` |
| F20 | 테스트는 stdlib `unittest`, `hub_collect` 모듈 상수를 임시 디렉토리로 스왑하는 setUp/tearDown 패턴 | `tests/run.sh:2572-2581`, `tests/hub/test_hub_collect.py:868-886` |
| F21 | **`hub/bin/*.py` 전부에 800줄 상한 검사가 있다**(T25-100). `hub_collect.py` 는 현재 716줄 — 이력 I/O 를 여기 더하면 상한을 위협한다 | `tests/run.sh:4162-4167`, `wc -l` 실측 716 |
| F22 | 배포 파일 수 검증 `HUB_FILE_COUNT=16`(hub/bin 최상위, `__pycache__` 제외), README 「파일 배치」의 "16개 파일" 고지를 T25-104 가 강제한다 | `hub/install.sh:12`, `98-99`, `hub/README.md:460-465`, `tests/run.sh:4219-4232` |
| F23 | 제거 시 보존되는 사용자 데이터 목록이 hub/install.sh 완료 메시지에 열거된다 | `hub/install.sh:193-200` |
| F24 | `/hub status` 진단 필드는 `show_usage_panel` 게이트를 따르는 헬퍼들로 구성되고, 중첩 dict 필드 선례가 있다(`rate_limit_resets_remaining_ms`) | `hub.py:127-214`, `144-162`, `217-251` |
| F25 | `usage_sample_from_capture` 는 퍼센트가 **둘 다** 있어야 `UsageSample` 을 만든다 — 패널 자체의 표시 조건 | `hub_usage.py:220-228` |
| F26 | 퍼센트·epoch 의 엄격 검증 함수(`_is_valid_percent`·`_is_valid_epoch_ms`, bool 배제)가 이미 있다 — 이력 파서가 재사용한다 | `hub_usage.py:75-91` |

---

## 3. 확정된 전제 (재론하지 않는다)

1. **관측이 없으면 데이터도 없다.** 두 생산자 모두 꺼져 있거나 세션이 안 돌면 이력에 빈
   구간이 생긴다 — 이것은 결함이 아니라 사실의 정직한 표현이다(P1·P6 과 같은 정신).
   빈 구간을 보간하지 않는다.
2. **단일 정적 HTML, 빌드 단계 없음.** 차트는 인라인 SVG 문자열 생성이다(PV9 관례).
3. **`#dzh-data` 단일 페이로드.** 이력도 스냅샷 필드로 임베드한다 — 별도 fetch 없음(비목표).
4. **`rate_limits.json` 은 계속 "현재 값 1건"이다.** 이력은 별도 파일이 맡는다 —
   기존 캡처 파일의 포맷·소비자를 바꾸지 않는다(A2 와 같은 이유).
5. 이 작업은 전체 경로(설계→구현→검수) 대상이다 — 새 모듈 추가 + 3개 이상 파일 + 공개
   인터페이스(`HubSnapshot`) 변경.

---

## 4. 영향 범위

| 파일 | 변경 | 요지 |
|------|------|------|
| `hub/bin/hub_usage.py` (471줄) | 수정(+약 85줄) | ★순수: `UsageHistoryPoint`, 캡처→점 투영, 퍼센트 변화 판정, 이력 줄 파서, 버킷 다운샘플 |
| `hub/bin/hub_usage_history.py` | **신규**(약 140줄) | I/O 전용: 날짜별 JSONL append/읽기(꼬리 상한)/prune. 경로는 인자로 받는 잎 I/O 모듈(§6) |
| `hub/bin/hub_collect.py` (716줄) | 수정(+약 50줄) | 캡처 영속 초크 포인트 `persist_rate_limit_capture_if_changed`(이력 append 포함), `_capture_for_snapshot` 에 이력 읽기·다운샘플, `collect_snapshot` 에 prune |
| `hub/bin/hub_statusline.py` (48줄) | 수정(-2/+1) | 읽기→비교→쓰기 3줄을 초크 포인트 호출 1줄로 교체 |
| `hub/bin/hub_server.py` (406줄) | 수정(±5) | `_write_usage_api_capture` 내부를 초크 포인트 호출로 교체(실패 채널 유지) |
| `hub/bin/hub_model.py` (100줄) | 수정(+2) | `HubSnapshot.usage_history: tuple[UsageHistoryPoint, ...] = ()` |
| `hub/bin/hub_template.html` (1969줄) | 수정(+약 100줄) | 상수·CSS·`renderUsageTrend`(순수 문자열 생성)·`renderUsagePanel` 3번째 인자·머리 주석 |
| `hub/bin/hub.py` (354줄) | 수정(+약 25줄) | `/hub status` 에 `usage_history` 진단 필드 1개(중첩 dict) |
| `hub/install.sh` | 수정 | `HUB_FILE_COUNT` 16→17(`:12`), 제거 시 보존 목록에 `usage_history/` 추가(`:193-200`) |
| `hub/README.md` | 수정 | 사용량 패널 절(추이 문단), 파일 배치("16개→17개 파일", `usage_history/` 항목), 프라이버시 고지(보존 3일), 제거 절 |
| `commands/hub.md` | 수정 | `/hub status` 설명에 `usage_history` 필드 한 줄(`:226-227` 부근) |
| `docs/prps/hub-dashboard.md` | 수정 | 모듈 구성표(`:40-55`)·구조 트리(`:98`)에 `hub_usage_history.py` 행 추가(원문 삭제 없이 추기 — 이 레포의 이력 보존 방식) |
| `tests/hub/test_hub_usage.py` | 수정 | TH1~TH14 |
| `tests/hub/test_hub_usage_history.py` | **신규** | TH15~TH24 (소스 1:1 테스트 관례, 결정 MS9 계열) |
| `tests/hub/test_hub_collect.py` | 수정 | TH25~TH33 + 기존 `CaptureForSnapshotTest` 시그니처 반영 |
| `tests/hub/test_hub_statusline.py` | 수정 | TH34~TH36 + **CONFIG_PATH 스왑 추가**(GOTCHA 6) |
| `tests/hub/test_hub_server.py` | 수정 | TH37~TH38 |
| `tests/hub/test_hub_model.py` | 수정 | TH39~TH40 |
| `tests/hub/test_hub.py` | 수정 | TH41~TH42 |
| `tests/run.sh` | 수정 | T25-104 파일 수 갱신, 신규 T25-156~T25-159 |

건드리지 않는 것: `hub_usage_fetch.py`(A-SEC 경계 불변) · `hub_hook.py` · `hub_session.py` ·
`hub_project.py` · `hub_parse.py` · `hub_server_state.py` · `hub_settings.py` · `hub_transcript.py` ·
서버 라우팅(`ALLOWED_REQUEST_PATHS`) · `config.json` 스키마.

---

## 5. 설계

### 5.1 데이터 흐름 (전체 그림)

```
statusLine stdin ─┐                       ┌─ rate_limits.json  (현재 값 1건, 기존 그대로)
                  ├─ persist_rate_limit_ ─┤
usage API 폴링 ───┘  capture_if_changed   └─ usage_history/YYYY-MM-DD.jsonl  (신규, append-only)
                     (hub_collect, 신규            │
                      초크 포인트, §5.2)           │ 오늘+어제 읽기(꼬리 상한) + 5분 버킷 다운샘플
                                                   ▼
collect_snapshot ──── _capture_for_snapshot ──▶ HubSnapshot.usage_history (≤600점)
                                                   │  #dzh-data 인라인 (기존 렌더 경로)
                                                   ▼
hub_template.html ── renderUsageTrend ──▶ 24h 창 필터·스텝 SVG (클라이언트, Date.now())
```

### 5.2 생산 — 캡처 영속 초크 포인트 (TR1·TR2)

두 생산자에 중복된 "이전 읽기 → `same_capture_values` → 쓰기" 시퀀스(F1·F2)를
`hub_collect.persist_rate_limit_capture_if_changed(capture)` 하나로 접고, 이력 append 를
그 안에 둔다. **한 곳이어야 하는 이유**: append 를 생산자별로 두면 한쪽을 빼먹는 순간
그 생산자의 관측만 이력에서 조용히 사라진다 — 두 생산자가 "같은 파일, 같은 규칙"이라는
기존 공존 결정(A2)과 같은 형태로 유지한다.

동작 순서(실패 격리 포함):

1. `read_rate_limit_capture()` 로 이전 캡처를 읽는다(기존과 동일, `hub_collect.py:411-429`).
2. `same_capture_values(previous, capture)` 면 아무것도 하지 않고 `False` 반환 —
   **정상 상태의 I/O 횟수는 오늘과 완전히 같다**(읽기 1회, 쓰기 0회, config 읽기 0회. R-4).
3. 값이 변했으면 `write_rate_limit_capture(capture)` — 캡처 파일이 **먼저**다.
   이력이 어떻게 되든 현재 값 표시는 성립해야 한다.
4. 이력 append 판정(§5.3): 실패는 흡수한다(TR12) — append 의 `OSError` 가 statusLine
   출력이나 서버 폴링 스케줄을 죽이면 안 된다. stderr 한 줄만 남긴다
   (`record_collect_failure` 자기 실패 처리와 같은 형태, `hub_collect.py:588-589`).
5. `True` 반환.

호출부 교체:
- `hub_statusline._run` 의 3줄(`hub_statusline.py:33-35`) → `hub_collect.persist_rate_limit_capture_if_changed(capture)` 1줄.
  출력 먼저·파일 나중 순서(`hub_statusline.py:28-29`)는 불변.
- `hub_server._write_usage_api_capture`(`hub_server.py:278-292`) 본문 → 같은 호출.
  기존 `except OSError → record_collect_failure` 래핑과 "로컬 실패를 폴링 백오프에 섞지
  않는다"는 주석 취지는 그대로 유지한다.
- `write_rate_limit_capture` 의 docstring "(hub_statusline.py 전용 쓰기 경로)"
  (`hub_collect.py:433`)는 이미 사실과 다르므로(서버도 호출) "persist_rate_limit_capture_if_changed
  전용 하위 프리미티브"로 고쳐 적는다.

### 5.3 이력 append 판정 (TR3)

append 조건 세 가지가 **모두** 참일 때 1점을 쓴다:

1. **퍼센트 쌍이 변했다**: `not same_percent_values(previous, capture)`
   (신규 순수 함수, §8). 리셋 시각만 변한 캡처 쓰기(세션 창 롤오버 직후 등)는 추이에
   실을 정보가 없다 — `previous` 는 초크 포인트가 이미 손에 쥐고 있으므로 추가 I/O 없이
   판정된다. `previous is None`(최초 캡처)은 "변했다"로 본다(`same_capture_values` 와
   같은 계약, `hub_usage.py:289-290`).
2. **실을 퍼센트가 있다**: `history_point_from_capture(capture) is not None` —
   두 퍼센트가 모두 `None` 인 캡처(리셋 전용)는 점이 되지 않는다.
   한쪽만 있으면 그쪽만 실은 점을 만든다(창별 독립 부재 허용 — 캡처 파서와 같은 정신,
   `hub_usage.py:142`).
3. **`load_config().show_usage_panel` 이 참이다**(TR7): 패널을 끈 사용자에게 사용 궤적을
   축적하지 않는다. 현재 값 1건(`rate_limits.json`)은 오늘도 스위치와 무관하게 쓰이지만
   (statusLine 은 config 를 읽지 않는다 — `hub_statusline.py` 전체에 `load_config` 부재),
   **이력은 시계열이라 질적으로 더 민감하다** — "읽기 중단이 진짜 프라이버시 제어"라는
   기존 문장(`hub_collect.py:445-447`)의 정신을 기록 쪽으로 확장한다.
   config 읽기는 이 조건 판정 시점(= 값이 변한 사이클)에만 일어나므로 정상 상태 I/O 0회는
   유지된다(R-4).

점의 시각은 `capture.captured_at_ms` 를 그대로 쓴다 — 변화 시에만 쓰므로 이 값이 곧
"새 값을 처음 관측한 시각"이다(F5).

append 직후 같은 자리에서 `prune_old_history_files` 를 부른다(F19 의 훅 선례와 같은 이유 —
"최대 N일 보관"은 append 하는 쪽이 보장해야 성립한다). `collect_snapshot` 에서도 매 사이클
부른다(`hub_collect.py:490` 의 `prune_old_event_files` 와 나란히) — append 가 영영 없어도
남은 파일이 기한을 넘겨 잔존하지 않게 한다.

### 5.4 저장 형식과 읽기 — content_key 안정성이 형식을 결정한다 (TR4·TR5·TR6)

**함정(이 설계의 핵심 제약)**: "최근 24시간" 점 집합을 서버가 `now - 24h` 연속 컷오프로
계산해 스냅샷에 실으면, 새 데이터가 없어도 오래된 점이 창 밖으로 밀려나며 매 수집마다
집합이 변한다 → `snapshot_content_key` 가 매번 달라진다 → hub.html 쓰기 억제(F11)가
무력화된다. `UsageSample` 이 "파생값(나이)을 담지 않는다"고 못 박은 것과 정확히 같은
계열의 함정이다(결정 D3, `hub_usage.py:44-45`).

해소책 — **"지금"에 의존하는 판정을 전부 시간 격자가 굵은 쪽·클라이언트 쪽으로 밀어낸다**:

- **저장(TR4)**: `~/.claude/hub/usage_history/YYYY-MM-DD.jsonl` — 이벤트 로그와 같은
  날짜별 append-only JSONL(F16). 한 줄 = 한 점:
  `{"observed_at_ms": 1786433123899, "session_percent": 41, "weekly_percent": 63}`
  (없는 창은 `null`). 짧은 한 줄 1회 `write()` append — 동시 생산자(여러 statusLine
  프로세스 + 서버 폴링) 간 찢김은 이벤트 로그와 같은 논거로 사실상 원자적이고(F17),
  찢겨도 관용 파서가 그 줄만 버린다(F16).
- **읽기 범위**: 오늘 + 어제 파일(= `_recent_event_file_paths` 와 같은 격자,
  `hub_collect.py:176-179`). 이 격자에서 임베드 집합이 변하는 계기는 ① 새 점 append
  (어차피 캡처 변화로 hub.html 이 다시 쓰이는 사이클), ② 자정의 날짜 회전(하루 1회) —
  **둘뿐이다.** 시간 경과만으로는 변하지 않는다. 어떤 클라이언트 시각에서든 24시간 창은
  이 48시간 범위의 부분집합이다.
- **24h 필터는 클라이언트**: 템플릿이 `Date.now()` 기준으로 창을 자른다 — 남은/경과 시간
  계산을 전부 클라이언트가 하는 기존 분업(F13) 그대로.
- **다운샘플(TR5)**: 임베드 전에 **절대 시각 버킷**(`observed_at_ms // USAGE_HISTORY_BUCKET_MS`,
  5분) 당 마지막 점만 남기고, 최신 `USAGE_HISTORY_MAX_POINTS`(600)개로 자른다. 버킷 경계가
  epoch 기준 절대값이라 "지금"과 무관하게 결정적이다 — 상한 근거: 48시간 = 5분 버킷 576개
  ≤ 600. 임베드 크기 상한 ≈ 600점 × ~76B ≈ 45KB(실사용 예상은 훨씬 작다 — 정수 퍼센트
  변화가 곧 점이라 하루 수백 점 규모).
- **읽기 상한(TR6)**: 파일당 꼬리 `USAGE_HISTORY_TAIL_MAX_BYTES`(256KiB ≈ 3천여 줄)만 읽는다
  (`_read_transcript_tail` 과 같은 seek + `errors="replace"` 기법, F18). 경계값 진동
  (49↔50%) 같은 병적 생산이 있어도 수집 비용과 임베드가 유계로 남는다. 꼬리 절단으로
  찢긴 첫 줄은 관용 파서가 버린다.
- **보존(TR7)**: 파일명 날짜 기준 `USAGE_HISTORY_RETENTION_DAYS = 3` 일 —
  읽기 범위(오늘+어제)보다 하루 여유. 이벤트 prune 와 같은 정규식·컷오프 방식
  (`hub_collect.py:289-301`).

정렬: 읽기 결과를 `observed_at_ms` 오름차순으로 정렬해 돌려준다 — 두 생산자의 벽시계가
미세하게 어긋나 파일 내 순서가 뒤섞일 수 있다.

### 5.5 신규 I/O 모듈 `hub_usage_history.py` (TR8)

이력 I/O 를 `hub_collect.py` 에 넣지 않는 이유는 **측정 가능한 제약**이다: T25-100 이
`hub/bin/*.py` 전부에 800줄 상한을 강제하고(F21), 716줄인 `hub_collect.py` 에 이 문서
분량의 docstring 관례로 I/O 4개를 더하면 상한을 넘는다. 관심사 하나(추이 이력)를 I/O 모듈
하나로 격리한 선례는 `hub_usage_fetch.py`(토큰 격리)가 이미 세웠다.

모듈 경계 규칙:
- **임포트는 `hub_usage`(순수)와 stdlib 만.** `hub_collect` 를 임포트하지 않는다 —
  `hub_collect` 가 이 모듈을 임포트하므로 순환이 구조적으로 불가능해야 한다
  (`hub_server_state.py` 잎 모듈 계약과 같은 형태, `hub_collect.py:688-689`).
- **경로를 소유하지 않는다**: 모든 함수가 `history_dir: Path` 를 첫 인자로 받는다.
  실경로 상수 `USAGE_HISTORY_DIR = HUB_HOME / "usage_history"` 는 `hub_collect` 가 정의해
  넘긴다 — `HUB_HOME` 파생 경로의 단일 출처를 `hub_collect` 에 유지하고(`hub_collect.py:27-57`
  의 관례), 테스트는 임시 디렉토리를 직접 인자로 넘길 수 있다.
- `DATE_FORMAT`·`MILLISECONDS_PER_DAY` 는 모듈 안에 자기 사본을 둔다 — `hub_collect` 의
  같은 상수(`hub_collect.py:69-70`)를 임포트하면 순환이 생긴다. 값 사본 선례:
  `MILLISECONDS_PER_DAY` 는 이미 `hub_usage.py:27` 과 `hub_collect.py:69` 에 공존한다.
  두 값이 파일명 계약임을 상수 주석으로 남긴다.

### 5.6 스냅샷 임베드 (TR9)

`_capture_for_snapshot`(`hub_collect.py:439-467`)이 이력 읽기까지 맡아 4-튜플
`(usage, resets, usage_history, warnings)` 를 돌려준다. 게이트는 두 겹:

1. `show_usage_panel:false` → 캡처도 이력도 **열지 않는다**(기존 게이트 확장, F9).
2. `usage is None`(캡처 부재·퍼센트 없는 캡처) → 이력을 읽지 않고 `()`.
   근거: 패널 자체가 `usage` 없이는 그려지지 않으므로(F12 의 `renderUsagePanel` 첫 분기,
   `hub_template.html:1467`) 임베드해도 쓰일 곳이 없다 — statusLine 미설치 사용자의 수집
   사이클에 파일 2개 읽기를 공짜로 얹지 않는다. `usage.is_stale` 은 여기 해당하지 않는다 —
   stale 이어도 패널은 그려지고(EX1), 이력은 과거 사실이라 계속 참이다(TR11).

읽기 실패 경고는 기존 `capture_warnings` 합류 지점(`hub_collect.py:518-519`)에 그대로 싣는다.
`HubSnapshot` 에는 `usage_history: tuple[UsageHistoryPoint, ...] = ()` 를 추가한다 —
기본값이 있어 기존 생성부·테스트가 깨지지 않고, `asdict` 재귀 직렬화(F10)와
`snapshot_content_key`(F11) 포함이 자동으로 성립한다.

---

## 6. 파일 구조

```
hub/bin/
├── hub_usage.py            # ★순수 (수정) — UsageHistoryPoint · 투영 · 변화 판정 · 줄 파서 · 다운샘플
├── hub_usage_history.py    # I/O (신규) — 날짜별 JSONL append / 오늘+어제 꼬리 읽기 / prune.
│                           #   임포트: hub_usage + stdlib 만. 경로는 인자(history_dir)로 받는다.
├── hub_usage_fetch.py      # (불변) usage API I/O — A-SEC 경계 그대로
├── hub_collect.py          # I/O (수정) — USAGE_HISTORY_DIR 상수, persist 초크 포인트,
│                           #   _capture_for_snapshot 4-튜플, collect_snapshot prune
├── hub_statusline.py       # (수정) 캡처 영속을 초크 포인트 호출로 교체
├── hub_server.py           # (수정) _write_usage_api_capture 를 초크 포인트 호출로 교체
├── hub_model.py            # (수정) HubSnapshot.usage_history 필드
├── hub_template.html       # (수정) 추이 차트 렌더
└── hub.py                  # (수정) /hub status 진단 필드

~/.claude/hub/
└── usage_history/          # (신규) YYYY-MM-DD.jsonl — append-only, 3일 보존
    └── 2026-08-27.jsonl

tests/hub/
└── test_hub_usage_history.py   # (신규) 소스 1:1 관례
```

모듈 의존 방향(순환 없음): `hub_usage_history → hub_usage`,
`hub_collect → hub_usage_history·hub_usage`, `hub_statusline/hub_server → hub_collect`.

배포: `hub/install.sh` 의 `HUB_FILE_COUNT` 16→17(F22). 반영 절차는 기존과 동일 —
`hub/install.sh --force` 후 `/hub server restart`(`hub/README.md:83-99`).

---

## 7. 데이터 모델

### 7.1 순수 타입 (hub_usage.py 에 추가)

```python
@dataclass(frozen=True)
class UsageHistoryPoint:
    """플랜 사용률 추이의 점 1개 — 캡처 퍼센트 쌍이 변한 순간의 관측(결정 TR3).

    "지금" 파생값(나이 등)은 담지 않는다(결정 D3 과 같은 이유) — 이 튜플의 시퀀스가
    HubSnapshot 에 실리므로, 파생값을 담으면 content_key 재작성이 폭주한다.
    """
    observed_at_ms: int           # 이 퍼센트 쌍을 처음 관측한 시각(= 캡처의 captured_at_ms)
    session_percent: int | None   # rate_limits.five_hour 내림 정수(0~100). 창별 독립 부재 허용
    weekly_percent: int | None    # rate_limits.seven_day 내림 정수(0~100)
```

### 7.2 이력 파일 계약 (`usage_history/YYYY-MM-DD.jsonl`)

- 한 줄 = `UsageHistoryPoint` 하나의 `json.dumps(asdict(point), ensure_ascii=False)`.
  전체 필드명 사용(축약 금지 — 전역 가독성 규칙; `rate_limits.json` 도 전체 필드명이다).
- 검증 규칙은 캡처 파서 재사용: `observed_at_ms` 는 `_is_valid_epoch_ms`(엄격 int, bool 배제,
  `hub_usage.py:89-91`), 퍼센트는 `_is_valid_percent`(엄격 int 0~100, `hub_usage.py:75-86`).
  퍼센트 필드가 규칙 위반이면 **그 필드만** `None` 으로 강등(캡처 파서의 필드 단위 탈락과
  동일, `hub_usage.py:198-203`), 두 퍼센트가 모두 `None` 이 되면 **그 줄 전체를 버린다**
  (그릴 것이 없는 점은 점이 아니다). `observed_at_ms` 위반·JSON 불량·비 dict 는 줄 폐기.
- 파일명 날짜는 `time.localtime` 기준(`_date_string` 과 동일, `hub_collect.py:172-173`) —
  이벤트 로그와 같은 시간대 규칙.

### 7.3 스냅샷 계약 (hub_model.py)

```python
@dataclass(frozen=True)
class HubSnapshot:
    ...기존 필드 불변...
    usage_history: tuple[UsageHistoryPoint, ...] = ()
    # 오늘+어제 이력 파일의 5분 버킷 다운샘플(observed_at_ms 오름차순, 최대 600점).
    # 24시간 창 필터는 클라이언트 몫이다(결정 TR4) — 서버가 now 기준으로 자르면
    # content_key 가 시간 경과만으로 변해 쓰기 억제가 무력화된다.
```

`#dzh-data` JSON 에는 `"usage_history": [{"observed_at_ms":…, "session_percent":…,
"weekly_percent":…}, …]` 로 실린다(snake_case 그대로 — 기존 계약,
`hub_template.html:14`). 구세대 hub.html(필드 부재)을 읽는 신세대 스크립트는
`snapshot.usage_history || []` 로 흡수한다(`template_stamp` 의 `|| ''` 관례,
`hub_template.html:953-955`).

### 7.4 상수 (신규)

| 상수 | 값 | 위치 | 근거 |
|------|-----|------|------|
| `USAGE_HISTORY_BUCKET_MS` | `5 * 60 * 1000` | hub_usage.py | 임베드 다운샘플 격자. 차트 유효 해상도(패널 폭 ~384px / 24h ≈ 3.75분/px)와 같은 자리수 |
| `USAGE_HISTORY_MAX_POINTS` | `600` | hub_usage.py | 48h ÷ 5min = 576 버킷 + 여유. 임베드 크기 상한 ≈ 45KB |
| `USAGE_HISTORY_RETENTION_DAYS` | `3` | hub_usage_history.py | 읽기 범위(오늘+어제) + 1일 여유 |
| `USAGE_HISTORY_TAIL_MAX_BYTES` | `256 * 1024` | hub_usage_history.py | 병적 생산 시 수집 비용 상한(F18 선례) |
| `DATE_FORMAT`, `MILLISECONDS_PER_DAY` | 사본 | hub_usage_history.py | 순환 임포트 금지(§5.5). 값 동일성은 T25-158 이 지킨다 |
| `USAGE_TREND_WINDOW_MS` | `24 * MS_PER_HOUR` | hub_template.html | 표시 창. **`MS_PER_HOUR`(:907) 선언 뒤에 둘 것** — var 호이스팅 함정(`hub_template.html:909-913` 에 기록된 GOTCHA 2) |
| `USAGE_TREND_GAP_BREAK_MS` | `30 * MS_PER_MINUTE` | hub_template.html | 이보다 긴 간격은 선을 잇지 않는다(§9). `MS_PER_MINUTE`(:833) 재사용 |

---

## 8. 인터페이스 (공개 함수 시그니처)

### 8.1 hub_usage.py (★순수, 추가)

```python
def history_point_from_capture(capture: RateLimitCapture) -> UsageHistoryPoint | None:
    """캡처를 추이 점으로 투영한다(결정 TR3). 퍼센트가 둘 다 없으면 None.
    usage_sample_from_capture(둘 다 필요)와 달리 한쪽만 있어도 점이 된다 — 추이는 창별로 독립이다."""

def same_percent_values(previous: RateLimitCapture | None, current: RateLimitCapture) -> bool:
    """퍼센트 2개가 모두 같은가 — 같으면 이력에 점을 추가하지 않는다(결정 TR3).
    previous 가 None 이면 False(same_capture_values 와 같은 계약). 리셋 시각은 보지 않는다."""

def parse_usage_history_line(line: str) -> UsageHistoryPoint | None:
    """이력 파일 한 줄을 파싱한다. 계약이 안 맞으면 None(호출자가 건너뛴다) — §7.2 규칙."""

def downsample_usage_history(
    points: Sequence[UsageHistoryPoint], bucket_ms: int, max_points: int
) -> tuple[UsageHistoryPoint, ...]:
    """절대 시각 버킷(observed_at_ms // bucket_ms)당 마지막 점만 남기고 최신 max_points 개로
    자른다(결정 TR5). 반환은 observed_at_ms 오름차순. 버킷이 절대값이라 now 와 무관하게 결정적이다."""
```

### 8.2 hub_usage_history.py (I/O, 신규 모듈)

```python
def append_history_point(history_dir: Path, point: hub_usage.UsageHistoryPoint) -> None:
    """오늘 날짜 파일에 한 줄을 1회 write() 로 append 한다(hub_hook._append_event_line 과 같은
    원자성 논거). 디렉토리가 없으면 만든다. OSError 는 호출자가 처리한다."""

def read_recent_history(
    history_dir: Path, now_ms: int
) -> tuple[tuple[hub_usage.UsageHistoryPoint, ...], tuple[str, ...]]:
    """오늘+어제 파일의 꼬리(파일당 USAGE_HISTORY_TAIL_MAX_BYTES)를 읽어 (점 오름차순, 경고)
    를 돌려준다. 이 함수는 절대 예외를 던지지 않는다 — 파일 부재는 정상(경고 없음),
    파일 단위 읽기 실패만 경고 1건(read_recent_events 와 같은 격리 원칙),
    깨진 줄은 parse_usage_history_line 에서 탈락한다. errors="replace" 디코딩(GOTCHA 7 계열)."""

def prune_old_history_files(history_dir: Path, now_ms: int) -> None:
    """USAGE_HISTORY_RETENTION_DAYS 보다 오래된 날짜 파일을 삭제한다. 살아 있는 파일은 절대
    다시 쓰지 않는다(prune_old_event_files 와 같은 정규식·컷오프 방식)."""
```

### 8.3 hub_collect.py (수정·추가)

```python
USAGE_HISTORY_DIR = HUB_HOME / "usage_history"   # 추이 이력(결정 TR2). 경로 단일 출처는 이 모듈

def persist_rate_limit_capture_if_changed(capture: hub_usage.RateLimitCapture) -> bool:
    """두 생산자 공용 캡처 영속 초크 포인트(결정 TR1). 이전과 값이 같으면 아무것도 안 하고
    False. 변했으면 캡처를 쓰고(먼저), 퍼센트 쌍이 변했으며 show_usage_panel 이 켜져 있으면
    추이 이력에 1점을 append + prune 한다(결정 TR3·TR7). 이력 쪽 OSError 는 흡수하고
    stderr 로만 남긴다(결정 TR12) — 캡처 쓰기의 성패만이 반환·예외에 반영된다."""

def _capture_for_snapshot(now_ms: int, config: hub_model.HubConfig) -> tuple[
    hub_usage.UsageSample | None, hub_usage.RateLimitResets | None,
    tuple[hub_usage.UsageHistoryPoint, ...], tuple[str, ...],
]:
    """(기존 docstring 유지에 더해) usage 가 있을 때만 이력을 읽어 다운샘플해 싣는다(결정 TR9)."""
```

`collect_snapshot`(`hub_collect.py:487-528`): `prune_old_event_files` 옆(490)에
`hub_usage_history.prune_old_history_files(USAGE_HISTORY_DIR, now_ms)` 1줄,
518 의 언패킹을 4-튜플로, `HubSnapshot(...)` 에 `usage_history=usage_history`.

### 8.4 hub_statusline.py / hub_server.py (호출부 교체)

```python
# hub_statusline._run (33-35 대체)
hub_collect.persist_rate_limit_capture_if_changed(capture)

# hub_server._write_usage_api_capture (본문 대체 — 함수·docstring 취지 유지)
try:
    hub_collect.persist_rate_limit_capture_if_changed(capture)
except OSError as error:
    hub_collect.record_collect_failure(str(error))
```

### 8.5 hub.py (진단, 추가)

```python
def _usage_history_diagnostics(now_ms: int, config: hub_model.HubConfig) -> dict | None:
    """진단용 — 추이 이력의 마지막 점 나이(ms)와 최근(오늘+어제) 점 개수.
    스위치 off 면 None(자매 헬퍼들과 같은 게이트). 이력이 비어 있으면
    {"last_point_age_ms": None, "recent_point_count": 0}."""
```

`cmd_status`(`hub.py:217-251`) 페이로드에 `"usage_history": _usage_history_diagnostics(now_ms, config)`
1개 추가(중첩 dict 선례: `rate_limit_resets_remaining_ms`, `hub.py:144-162`).

---

## 9. 화면 명세 — 추이 차트

### 9.1 배치와 갱신 규칙

- 위치: `#dzh-usage-body` **안**, 주간 리셋 줄 뒤 · 메타 줄(`usage-meta`/`usage-stale-note`) 앞.
  신선 분기: `sessionBar + sessionResetRow + weeklyBar + weeklyResetRow + trend + meta`,
  만료 분기: `staleRow×2(+reset) + trend + staleNote`(`hub_template.html:1470-1487` 의 두 분기).
- **불변식 H1⁗ 무변경**: 차트는 폴링이 이미 갱신해도 되는 `#dzh-usage-body` innerHTML 의
  일부다(F12). 새 폴링 대상 노드를 만들지 않는다. 머리 주석(:64-73 문단)에
  `usage_history` 출처 한 줄을 추가한다.
- `renderUsagePanel(usage, resets)` → `renderUsagePanel(usage, resets, history)` 로 3번째
  인자를 받고, 호출부 2곳(`hub_template.html:1548`, `1563`)이 `snapshot.usage_history` 를 넘긴다.
- 30초 틱(`:1629`)마다 재렌더되므로 24h 창이 클라이언트 시각을 따라 흐른다(F13).
  접힘 상태에서는 CSS 로 본문째 숨는다(F14) — 추가 처리 없음.
- **stale 이어도 그린다**(TR11): `is_stale` 은 "현재 값의 유효기간 만료"지 과거 관측의
  무효화가 아니다. 시각적 일관성은 기존 `.usage-stale` 클래스가 요약·제목에만 닿으므로 충돌 없음.

### 9.2 렌더 함수 (순수 문자열 생성 — renderUsageBar 관례)

```
function renderUsageTrend(history, nowMs) -> string   // 그릴 것이 없으면 ''
```

1. 입력 방어: 배열이 아니면 `''`. 각 점은 `Number()` 강제 후 `isFinite` 검사, 퍼센트는
   `clampPercent`(`hub_template.html:1346-1350`) 재사용 — 비유한 값은 그 점만 버린다.
   사본을 `observed_at_ms` 오름차순 정렬(서버가 보장하지만 1줄 방어).
2. 창 필터: `observed_at_ms >= nowMs - USAGE_TREND_WINDOW_MS`.
3. 계열 분리: `session_percent != null` 인 점 → 세션 계열, `weekly_percent` → 주간 계열.
4. 계열별 분절: 인접 점 간격 > `USAGE_TREND_GAP_BREAK_MS` 면 선을 끊는다(확정 전제 1 —
   관측 없는 구간을 이어 그리지 않는다). 마지막 점은 `nowMs - t ≤ GAP` 일 때만 현재
   시각까지 수평 연장한다(라이브 엣지).
5. 스텝 보간: `(t1,v1)→(t2,v2)` 는 `H x(t2)` 후 `V y(v2)` — 캡처 의미(다음 관측까지
   그 값이 마지막 관측값)와 일치한다.
6. 1점짜리 분절은 반지름 2 의 원으로 그린다 — 드문 주간 변화가 통째로 사라지지 않게 한다.
7. 두 계열 모두 그릴 점이 0개면 `''`(패널 레이아웃 불변 — 리셋 줄과 같은 "장식" 지위,
   결정 R3 계열).

출력 마크업(신규 CSS 클래스 4개, 색 토큰 신설 0개 — MC1 관례):

```html
<div class="usage-trend" role="img" aria-label="최근 24시간 사용률 추이">
  <div class="usage-trend-head"><span>최근 24시간</span>
    <span class="usage-trend-legend">
      <span class="usage-trend-dot usage-trend-dot-session"></span>세션
      <span class="usage-trend-dot usage-trend-dot-weekly"></span>주간
    </span></div>
  <svg viewBox="0 0 320 72" aria-hidden="true">…폴리라인·원…</svg>
</div>
```

- 좌표계: `viewBox 0 0 320 72`, 상하 패딩 4px. `x = 4 + (t - (now-24h)) / 24h × 312`,
  `y = 4 + (100 - v) / 100 × 64`. y 도메인은 0~100 고정(두 막대와 같은 스케일 인식).
- 색: 세션 `stroke: var(--accent)`, 주간 `stroke: var(--attention)` — 양 테마 정의 확인됨
  (F15), 파랑/주황 색약 안전 쌍. 주간을 먼저(아래에) 그린다. `stroke-width: 1.5`, `fill: none`.
- CSS: `.usage-trend{margin-top:10px}` `.usage-trend svg{display:block;width:100%;height:auto;
  background:var(--soft);border-radius:8px}`(`.usage-bar` 의 면 처리 관례, :408-409)
  `.usage-trend-head{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-bottom:4px}`
  `.usage-trend-dot{…8px 원, 계열색 배경…}`.
- 주입 방어: 동적 값은 전부 숫자(검증 후 문자열화)이고 텍스트는 리터럴 상수뿐 —
  `escapeHtml` 대상 없음. 신규 툴팁 트리거 없음(패널 안 툴팁 금지 원칙 R5·UT1 유지,
  `hub_template.html:66-68`).

---

## 10. 설계 결정 요약

| # | 결정 | 근거 |
|---|------|------|
| TR1 | 이력 append 는 캡처 영속 초크 포인트(`persist_rate_limit_capture_if_changed`) 한 곳에서만 일어난다. 두 생산자의 중복 시퀀스(F1·F2)를 이 함수로 접는다 | 생산자별 append 는 한쪽 누락 = 조용한 데이터 구멍. 기존 중복 제거를 겸한다 |
| TR2 | 저장은 `usage_history/YYYY-MM-DD.jsonl` append-only 날짜 파일 | 이벤트 로그 패턴 재사용(F16·F17) — 동시 append·관용 파싱·prune 논거를 새로 만들지 않는다 |
| TR3 | 점은 "퍼센트 쌍이 변한 캡처 쓰기" 시점에만, `captured_at_ms` 를 시각으로 추가된다. 리셋 전용 변화는 제외 | 변화 없는 관측은 정보 0(F4·F5). previous 가 손에 있어 추가 I/O 0회 |
| TR4 | 임베드 범위는 "오늘+어제 파일"(굵은 격자), 24h 컷오프는 클라이언트 | **content_key 안정성**(F11) — now 연속 컷오프는 쓰기 억제를 무력화한다(결정 D3 계열) |
| TR5 | 임베드 전 절대 시각 5분 버킷 last-wins 다운샘플 + 600점 상한 | 결정적(now 무관), 크기 유계, 차트 해상도 초과분은 정보가 아니다 |
| TR6 | 파일당 256KiB 꼬리 읽기 상한 | 병적 생산(경계 진동)에도 수집 비용 유계(F18 선례) |
| TR7 | append 는 `show_usage_panel` 게이트, 보존 3일, prune 는 append 경로+collect 양쪽 | 시계열은 현재값보다 민감(§5.3) · "최대 N일 보관" 성립 조건(F19) |
| TR8 | I/O 는 신규 잎 모듈 `hub_usage_history.py`(경로 인자화, hub_collect 미임포트) | T25-100 800줄 상한(F21) + hub_usage_fetch 격리 선례 + 순환 불가 구조 |
| TR9 | 이력 읽기·임베드는 `usage` 샘플이 있을 때만 | 패널 없는 화면에 쓰일 데이터를 읽지 않는다(F12 표시 조건) |
| TR10 | 신규 config 필드 0개 | YAGNI — 기존 `show_usage_panel` 이 의미상 정확히 이 기능의 스위치다 |
| TR11 | stale 상태에서도 추이는 그린다 | 과거 관측은 만료되지 않는다(EX1 의 "숨기지 않는다" 정신) |
| TR12 | 이력 I/O 실패는 캡처 쓰기·statusLine 출력·폴링 스케줄에 절대 전파되지 않는다 | statusLine 절대 규칙(`hub_statusline.py:5-6`) · 폴링 상태는 원격 결과만 반영(`hub_server.py:283-285`) |

---

## 11. GOTCHA (구현 시 걸려 넘어질 지점)

1. **now 기준 필터를 서버에 두면 안 된다**(TR4). `_capture_for_snapshot` 안에서
   `now_ms - 24h` 로 점을 거르고 싶어질 것이다 — 그 순간 매 수집마다 content_key 가 변해
   hub.html 쓰기 억제(F11)가 죽는다. 필터는 격자(날짜 파일)와 클라이언트에만 있다.
   TH31 이 이 회귀를 직접 잡는다.
2. **`UnicodeDecodeError` 는 `except OSError` 를 뚫는다**(GOTCHA 7 선례,
   `hub_collect.py:233-235`·`415-418`). 이력 읽기는 동시 append 중인 파일의 꼬리 절단
   지점을 읽으므로 반드시 `errors="replace"` 디코딩.
3. **버킷 다운샘플에 `now` 를 쓰지 말 것**. `(now - t) // bucket` 식 상대 버킷은 결정성이
   깨진다 — 반드시 `t // bucket` 절대 버킷(TH12 검증).
4. **`USAGE_TREND_WINDOW_MS` 선언 위치**: `MS_PER_HOUR`(:907) 뒤. var 호이스팅으로 앞에
   두면 `24 * undefined = NaN` 이 되어 필터가 조용히 전부 통과·전부 탈락한다 —
   같은 파일의 기록된 함정(`hub_template.html:909-913`).
5. **append 순서는 "캡처 먼저, 이력 나중"**(§5.2). 뒤집으면 이력 append 성공 + 캡처 쓰기
   실패 시 "이력에는 있는데 현재 값은 옛것"인 불일치가 생긴다.
6. **테스트 격리 — `CONFIG_PATH` 스왑 누락 주의.** `persist_rate_limit_capture_if_changed`
   는 변화 경로에서 `load_config()` 를 부르는데, 기존 statusline 테스트는 `HUB_HOME`·
   `RATE_LIMITS_PATH` 만 스왑한다(`test_hub_statusline.py` setUp). 그대로 두면 테스트가
   **실제 사용자 `~/.claude/hub/config.json` 을 읽는다** — 사용자가 `show_usage_panel:false`
   면 테스트가 환경 따라 다르게 죽는다. `hub_collect.CONFIG_PATH` 도 임시 디렉토리로
   스왑한다(같은 setUp/tearDown 패턴, F20).
7. **두 생산자 동시 관측 레이스**: statusLine 과 서버 폴링이 같은 변화를 거의 동시에 보면
   둘 다 gate 를 통과해 근접한 점 2개가 append 될 수 있다. 막지 않는다 — 5분 버킷
   last-wins 가 임베드에서 자연 병합하고, 파일의 중복 수십 바이트는 무해하다(문서화만).
8. **`asdict` 는 이미 재귀다** — `usage_history` 튜플을 수동 직렬화하려 들지 말 것.
   `projects`(ProjectView 튜플)가 같은 경로로 이미 직렬화된다(F10).
9. **템플릿 신규 노드 금지 목록 확인**: 차트는 `#dzh-usage-body` 안이므로 H1⁗ 개정이
   필요 없다. 패널 컨테이너(`#dzh-usage`)나 토글에 무언가를 덧붙이면 그 순간 개정 대상이다.

---

## 12. 테스트 계획

실행: `python3 -m unittest discover -s tests/hub -t .`(T24 가 이것을 돌린다,
`tests/run.sh:2572-2581`) + `tests/run.sh` 전체.

### tests/hub/test_hub_usage.py (순수)

| # | 케이스 |
|---|--------|
| TH1 | `history_point_from_capture`: 두 퍼센트 있음 → 점(시각=captured_at_ms, 값 복사) |
| TH2 | 〃: 한쪽만 있음 → 그쪽만 실린 점 |
| TH3 | 〃: 둘 다 None(리셋 전용 캡처) → None |
| TH4 | `same_percent_values`: previous None → False |
| TH5 | 〃: 퍼센트 동일·리셋만 다름 → True (리셋을 보지 않는다) |
| TH6 | 〃: 세션만 다름 / 주간만 다름 / None↔값 전이 → False |
| TH7 | `parse_usage_history_line`: 정상 왕복(append 가 쓰는 형식 그대로) |
| TH8 | 〃: JSON 불량·비 dict·observed_at_ms 부재/실수/bool → None |
| TH9 | 〃: 퍼센트 필드 위반(101, -1, 실수, bool)은 필드 단위 None 강등, 둘 다 잃으면 줄 폐기 |
| TH10 | `downsample_usage_history`: 같은 버킷 여러 점 → 마지막만 생존 |
| TH11 | 〃: max_points 초과 → 최신 쪽 유지, 오름차순 반환 |
| TH12 | 〃: 결정성 — 같은 입력이면 호출 시각과 무관하게 같은 출력(절대 버킷, GOTCHA 3) |
| TH13 | 〃: 빈 입력 → () |
| TH14 | 〃: 비정렬 입력도 오름차순으로 정렬돼 나온다 |

### tests/hub/test_hub_usage_history.py (신규, I/O — 임시 디렉토리 직접 인자)

| # | 케이스 |
|---|--------|
| TH15 | `append_history_point`: 디렉토리 생성 + 오늘 날짜 파일에 1줄, `parse_usage_history_line` 왕복 성공 |
| TH16 | 〃: 연속 append 는 줄 수만 늘린다(덮어쓰기 아님) |
| TH17 | `read_recent_history`: 오늘+어제 파일 병합, observed_at_ms 오름차순 |
| TH18 | 〃: 파일 부재 → ((), ()) 경고 없음 / 그제 파일은 읽지 않는다 |
| TH19 | 〃: 깨진 줄(잘린 JSON·빈 줄) 섞임 → 그 줄만 탈락 |
| TH20 | 〃: 파일 읽기 실패(chmod 000) → 그 파일만 건너뛰고 경고 1건 |
| TH21 | 〃: 꼬리 상한 — 상한보다 큰 파일에서 최신 줄들이 살아남고 예외가 없다(찢긴 첫 줄 탈락 포함) |
| TH22 | `prune_old_history_files`: 보존 기한 밖 날짜 파일만 삭제, 경계일은 생존 |
| TH23 | 〃: 디렉토리 부재 → 무동작 무예외 |
| TH24 | 〃: 날짜 형식이 아닌 파일명은 건드리지 않는다 |

### tests/hub/test_hub_collect.py

| # | 케이스 |
|---|--------|
| TH25 | `persist_rate_limit_capture_if_changed`: 최초 캡처 → 캡처 쓰기 + 이력 1점 + True |
| TH26 | 〃: 값 동일 → 파일 무변경·이력 무변경·**load_config 미호출**(mock)·False (R-4 회귀) |
| TH27 | 〃: 리셋만 변화 → 캡처는 다시 쓰고 이력은 그대로 |
| TH28 | 〃: `show_usage_panel:false`(임시 CONFIG_PATH 에 기록) → 캡처는 쓰고 이력은 안 쓴다 |
| TH29 | 〃: 이력 append 가 OSError(history_dir 를 파일로 막기 등) → 캡처는 쓰였고 예외가 새지 않고 True |
| TH30 | `_capture_for_snapshot`: usage 있음 → 다운샘플된 이력 포함 4-튜플 / usage None → 이력 파일을 **열지 않는다**(Path.read_text 미호출 — N31 방식) / 스위치 off → 둘 다 안 연다 |
| TH31 | **content_key 안정성 회귀(핵심)**: 이력 파일 고정 + 신선한 캡처에서, `now_ms` 를 달리한 두 번의 `collect_snapshot` 이 같은 `snapshot_content_key` 를 낸다(`SnapshotContentKeyStaleTransitionTest` 의 자매, `test_hub_collect.py:1001` 참조) |
| TH32 | `collect_snapshot`: 스냅샷에 `usage_history` 가 실리고, prune 가 이력 디렉토리에도 적용된다 |
| TH33 | 이력 읽기 경고가 스냅샷 `warnings` 로 합류한다 |

### tests/hub/test_hub_statusline.py (기존 N39~N42 유지 + CONFIG_PATH 스왑)

| # | 케이스 |
|---|--------|
| TH34 | 퍼센트 변화 stdin 2회 → 캡처 갱신 + 이력 2점 |
| TH35 | 동일 값 stdin 재실행 → 쓰기 0회(기존 N42 유지) + 이력 0점 |
| TH36 | 이력 디렉토리 쓰기 불가여도 stdout 상태줄 정상 출력 + exit 0 (절대 규칙) |

### tests/hub/test_hub_server.py

| # | 케이스 |
|---|--------|
| TH37 | `_run_usage_api_poll_cycle` 성공 경로가 초크 포인트를 경유해 이력까지 남긴다(`RunUsageApiPollCycleTest`(:508) 확장) |
| TH38 | 초크 포인트가 OSError 를 던지면 `record_collect_failure` 로 흡수되고 폴링 상태는 성공으로 남는다(기존 계약 유지) |

### tests/hub/test_hub_model.py · test_hub.py

| # | 케이스 |
|---|--------|
| TH39 | `HubSnapshot` 기본값 `usage_history=()` — 기존 생성부 무변경 통과 |
| TH40 | `render_hub_html` 산출물에 `usage_history` 배열이 이스케이프 규칙대로 인라인된다 |
| TH41 | `cmd_status`: 이력 있음 → `usage_history.last_point_age_ms`·`recent_point_count` 채움 |
| TH42 | 〃: 스위치 off → `usage_history: null` |

### tests/run.sh (문서·상수 정합 — T25 확장)

| # | 검사 |
|---|------|
| T25-156 | `hub/bin/hub_usage_history.py` 존재 + `hub_collect` 임포트 부재(잎 계약, T25-102 방식) + `hub_template.html` 에 `renderUsageTrend`·`USAGE_TREND_WINDOW_MS`·`usage-trend` 토큰 존재 |
| T25-157 | 파일 수 정합: `hub/install.sh` 의 `HUB_FILE_COUNT=17`, `hub/README.md` 의 "17개 파일" 고지(+옛 "16개 파일" 잔존 시 실패) — T25-104 의 기존 grep 갱신 |
| T25-158 | `hub_usage_history.py` 의 `DATE_FORMAT` 사본이 `hub_collect.py` 의 값과 문자열 동일(§5.5 사본 계약) |
| T25-159 | 프라이버시 고지: `hub/README.md` 에 `usage_history` 보존 기한 문구 존재 + `hub/install.sh` 제거 보존 목록에 `usage_history/` 존재 |

(T25-100 의 800줄 상한은 `hub/bin/*.py` 글롭이라 신규 모듈에 자동 적용된다 — 추가 작업 없음.)

---

## 13. 수동 확인 절차

1. `hub/install.sh --force && /hub server restart`(반영 절차, `hub/README.md:83-99`).
2. statusLine 등록 상태에서 Claude Code 세션을 몇 차례 돌린다 →
   `ls ~/.claude/hub/usage_history/` 에 오늘 파일 생성, `tail` 로 줄 형식 확인.
3. `/hub` 열기 → 사용량 패널 펼침 → 막대 아래 「최근 24시간」 차트. 30초 틱마다 창이
   흐르는지, 라이트/다크 토글에서 두 계열 색이 유지되는지 확인.
4. 세션을 세워 두고 5시간 경과(또는 캡처 시각 조작) → `조회되지 않음` 상태에서도 차트가
   남는지(TR11).
5. `config.json` 에 `"show_usage_panel": false` → 패널·차트 소멸 + 새 점이 쌓이지 않는지,
   되돌리면 그동안의 공백이 끊긴 선으로 보이는지.
6. `/hub status` → `usage_history` 필드 확인. `hub.html` 을 file:// 로 직접 열어도 차트가
   그려지는지(폴링 없이 30초 틱만으로).
7. 자정 전후(또는 파일 날짜 조작)로 어제 파일 회전이 차트에서 자연스러운지, 3일 지난
   파일이 prune 되는지.

---

## 14. 구현 순서 (마일스톤 — 각각 커밋 가능)

1. **M1 — 순수 계층**: hub_usage.py 추가분 + TH1~TH14.
2. **M2 — 이력 I/O 모듈**: hub_usage_history.py + TH15~TH24.
3. **M3 — 초크 포인트와 생산자 교체**: hub_collect.persist… + statusline/server 호출부 +
   TH25~TH29·TH34~TH38 (+기존 statusline 테스트 CONFIG_PATH 스왑).
4. **M4 — 스냅샷 임베드**: `_capture_for_snapshot` 4-튜플 + `HubSnapshot` 필드 +
   collect prune + TH30~TH33·TH39~TH40. **TH31(content_key 안정성)이 이 단계의 게이트다.**
5. **M5 — 템플릿**: 상수·CSS·renderUsageTrend·호출부·머리 주석 + T25-156.
6. **M6 — 진단·문서·배포 정합**: hub.py status + hub/README.md + commands/hub.md +
   hub/install.sh(17개) + docs/prps/hub-dashboard.md 표 + run.sh T25-157~159 + TH41~TH42.

---

## 15. 리스크와 완화

| # | 리스크 | 완화 |
|---|--------|------|
| 1 | 경계값 진동(예: 49↔50%)으로 이력이 비정상 증식 | 꼬리 읽기 상한(TR6) + 버킷 다운샘플(TR5) + 3일 prune(TR7)로 수집·임베드·디스크 모두 유계. 최악 파일 크기도 일 수 MB 수준 |
| 2 | hub.html 크기 증가(최대 +45KB) | 상한이 결정적(600점). 실사용 예상은 수 KB~20KB. 폴링은 문자열 전체 비교라 크기 증가가 비교 비용에 선형으로만 반영 |
| 3 | 클라이언트 시계와 관측 벽시계의 편차로 창 경계가 어긋남 | 기존 경과 표시(`elapsedLabel`)와 동일한 성질 — 수용. 차트는 진단 도구가 아니라 개형 표시다 |
| 4 | 두 생산자 레이스로 근접 중복 점 | 무해(§11-7). 버킷 last-wins 가 임베드에서 병합 |
| 5 | `show_usage_panel` 을 껐다 켠 사용자의 이력 공백을 결함으로 오인 | README 사용량 패널 절에 "관측이 없던 구간은 선이 끊긴다" 명시 + 갭 분절 렌더(§9.2-4)가 시각적으로 일치 |
| 6 | 신규 모듈로 인한 배포 수 불일치(HUB_FILE_COUNT) | install.sh 자체 검증(F22)이 즉시 실패시키고, T25-157 이 문서 쪽을 지킨다 |

---

## 16. 검토했으나 채택하지 않은 대안

1. **유지보수 티커의 고정 주기 샘플링**(5초 티커가 5분마다 현재 캡처를 이력에 복사):
   서버가 꺼진 statusLine 전용 구성(기본 구성이다 — `usage_api_enabled` 기본 false,
   `hub_model.py:41`)에서 이력이 전혀 안 쌓인다. 관측 주도 append(TR1·TR3)는 서버 유무와
   무관하게 동작한다. 또한 값이 안 변한 점의 반복 기록은 정보 0 이다.
2. **`rate_limits.json` 안에 이력 배열 내장**: 매 변화마다 파일 전체 재작성(append 불가),
   구형 파서와의 호환 부담, "현재 값 1건" 계약(확정 전제 4) 파괴. 기각.
3. **서버 신규 엔드포인트(`/usage-history.json`)**: 화이트리스트 고정 원칙(`hub_server.py:28-30`)
   훼손 + file:// 모드 미동작 + 폴링 경로 이원화. `#dzh-data` 단일 페이로드가 정본. 기각.
4. **hub_collect.py 에 이력 I/O 내장(신규 모듈 없이)**: 800줄 상한(F21)을 위협하고,
   파일 수 정합(F22) 회피라는 이득은 문서 3곳 갱신을 아끼는 정도 — 상한 위반 리스크가 더 크다. 기각.
5. **append 시점 솎아내기(최소 간격 미만이면 기록 생략)**: 생산자에 상태(마지막 기록 시각
   읽기)가 생기고 원본 데이터를 영구 손실한다. 읽기 시점 다운샘플(TR5)이 순수 함수라
   테스트 가능하고 원본을 보존한다. 기각.
6. **일반 차트 라이브러리 도입**: CDN·번들 금지(확정 전제 2, PV9). 기각.
7. **연속 24h 서버 컷오프 + content_key 에서 usage_history 제외**: 제외하면 이력이 변해도
   hub.html 이 안 다시 써져 차트가 화면에서 영구히 낡는다 — 억제 게이트의 목적 전도. 기각.

---

## 17. 사용자 승인이 필요한 결정 (구현 전 확인)

1. **표시 창 24시간 고정**(TR4·클라이언트 상수) — 7일 창 등 확장은 비목표로 미룬다. 동의하는가?
2. **이력 기록을 `show_usage_panel` 에 종속**(TR7) — 별도 스위치를 만들지 않는다. 동의하는가?
3. **보존 3일·5분 버킷·600점 상한**(§7.4) — 값 조정 여지 있음(상수 1줄).
4. **주간 계열 색 = `--attention`(주황)** — "경고색" 의미 중첩이 싫다면 회색(`--muted`) 대안이
   있으나 대비·구분성이 떨어진다.
5. **신규 모듈 1개 추가**(TR8, 배포 파일 16→17) — hub_collect 내장 대안(§16-4)을 기각한 것에
   동의하는가?
