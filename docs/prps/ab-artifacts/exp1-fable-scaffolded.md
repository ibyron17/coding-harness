> ⚠️ **실험 원본 — 승인된 설계가 아니다.**
> 이 문서는 모델·프롬프트 A/B 실험의 **실험 1 · A안(fable + 스캐폴딩, design-architect+prp-plan) · 38/50 패** 산출물이다.
> 여기 설계된 기능은 구현되지 않았고, 앞으로 구현할 계획도 없다.
> **저장소 선례로 인용하지 않는다.** 실험 설계·채점·결론은
> [`../model-scaffolding-ab-experiments.md`](../model-scaffolding-ab-experiments.md) 를 본다.
> 본문은 이 배너 블록 아래부터 서브에이전트 원본 그대로다(내용 무수정).

---

# PRP — 허브 플랜 사용률 추이 (수집·보존·표시)

> 설계 문서. **구현 코드는 이 문서에 없다.** 승인 후 `implementer` 가 이 문서를 입력으로 구현한다.
> 커밋 시 정본 경로: `docs/prps/hub-usage-trend.md` · 저장소 소스(`hub/bin/`·`hub/README.md`·`tests/`)만 다룬다.
> 선행 정본: [`hub-dashboard.md`](./hub-dashboard.md) · [`hub-theme-and-usage-panel.md`](./hub-theme-and-usage-panel.md) ·
> [`hub-usage-reset-time-and-refresh.md`](./hub-usage-reset-time-and-refresh.md) ·
> [`hub-card-cleanup-and-usage-source.md`](./hub-card-cleanup-and-usage-source.md)(결정 P1~P8) ·
> [`hub-card-interactions-and-usage.md`](./hub-card-interactions-and-usage.md)(R1·A2~A7) ·
> [`hub-onboarding-statusline-and-stale-usage.md`](./hub-onboarding-statusline-and-stale-usage.md)(EX 계열)
>
> 이 PRP 는 선행 결정을 **개정하지 않는다** — 캡처 파일(`rate_limits.json`)의 계약·생산자·게이트는 전부
> 그대로 두고, 그 위에 「관측 이력」 한 층을 얹는다.
>
> 결정 번호 namespace: **UH**(usage history). 신규 단위 테스트 케이스는 **UH-T1~**,
> `tests/run.sh` 정합성 검사는 **T25-156~** 로 매긴다(기존 T25-1~T25-155 와 충돌 없음).

---

## 1. 요구사항 요약

허브는 현재 플랜 사용률(`rate_limits` 의 5시간/7일 창 `used_percentage`)을 **현재 시점 값 하나**로만
수집·표시한다 — 캡처 파일 `~/.claude/hub/rate_limits.json` 은 값이 바뀔 때마다 덮어써져 직전 값이
소멸한다. 이 사용률의 **시간 추이를 수집·보존**하고, 허브 UI 의 기존 사용량 패널 안에서
**최근 24시간 추이 차트**로 볼 수 있게 한다. 목적은 "지금 25%" 가 아니라 "얼마나 빠르게 소모 중이고
언제 리셋으로 떨어졌는가"를 한눈에 읽는 것이다. 수집(생산자 append)·보존(날짜별 JSONL + 보존 기한)·
표시(스냅샷 투영 + SVG 스텝 차트) 세 층을 이 문서 하나로 확정한다.

---

## 2. 실측으로 확인된 사실 (재조사 대상 아님)

### 2.1 코드 사실 (2026-08-27 직접 읽고 확인)

| # | 사실 | 위치 |
|---|------|------|
| C1 | 퍼센트·리셋 시각의 저장은 `RATE_LIMITS_PATH = HUB_HOME / "rate_limits.json"` **단일 파일 덮어쓰기**다 — 이력이 구조적으로 남지 않는다 | `hub/bin/hub_collect.py:57`, 쓰기 `hub_collect.py:432-436` |
| C2 | 캡처 파일의 **쓰기 지점은 정확히 2곳**: statusLine 진입점과 사용량 API 폴링. 그 외 쓰기 없음(전수 grep) | `hub/bin/hub_statusline.py:35`, `hub/bin/hub_server.py:289` |
| C3 | 두 생산자 모두 쓰기 직전 `same_capture_values` 게이트를 거친다 — **값이 실제로 바뀐 순간에만 쓰기가 발생**한다(`captured_at_ms` 는 비교에서 제외, GOTCHA 4) | `hub/bin/hub_usage.py:282-296`, 호출 `hub_statusline.py:33-35`·`hub_server.py:286-291` |
| C4 | statusLine 진입점은 최대 0.3초마다 실행되며 "정상 상태 파일 I/O 0회 · 예외 절대 금지 · 항상 exit 0" 이 절대 규칙이다. **config 를 읽지 않는다** | `hub/bin/hub_statusline.py:2-15,24-44` |
| C5 | 사용량 API 폴링은 `show_usage_panel && usage_api_enabled` 둘 다 참일 때만 돈다(GOTCHA 2) — 이 게이트를 통과한 캡처만 `_write_usage_api_capture` 에 도달한다 | `hub/bin/hub_server.py:294-319` |
| C6 | `_write_usage_api_capture` 는 로컬 쓰기 실패(OSError)를 흡수해 `record_collect_failure` 로 남긴다 | `hub/bin/hub_server.py:278-291` |
| C7 | 화면 데이터는 `collect_snapshot` 이 캡처를 사이클당 1회 읽어 `HubSnapshot.usage`·`rate_limit_resets` 로 투영하고, `show_usage_panel:false` 면 **파일을 열지도 않는다**(프라이버시 원칙 명문화) | `hub/bin/hub_collect.py:439-467,487-528` |
| C8 | `HubSnapshot` 은 `render_hub_html` 이 `#dzh-data` JSON 으로 인라인하는 대외 계약이고, `snapshot_content_key`(`collected_at_ms` 제외 asdict 직렬화)가 같으면 hub.html 을 다시 쓰지 않는다 | `hub/bin/hub_model.py:46-56,80-100`, 마커 `hub_template.html:606` |
| C9 | 날짜별 JSONL append 의 선례가 이미 있다: 이벤트 로그는 `events/<YYYY-MM-DD>.jsonl` 에 **1회 write() append**(짧은 줄 = 동시 append 안전), 읽기는 오늘+어제 파일, 깨진 줄은 줄 단위 탈락, 보존은 날짜 파일 삭제 | `hub/bin/hub_hook.py:114-121`, `hub/bin/hub_collect.py:176-205,289-301` |
| C10 | 사용량 패널은 정적 컨테이너(`#dzh-usage`) + 파생 본문(`#dzh-usage-body` innerHTML) 구조이고, 폴링이 갱신하는 노드는 `#dzh-app`·`#dzh-usage-body`·`#dzh-usage-summary`·`#dzh-refresh` 속성뿐이다(불변식 H1′) | `hub/bin/hub_template.html:28-30,579-586` |
| C11 | 패널 렌더 함수는 `renderUsagePanel(usage, resets)` 하나이고 호출부는 2곳(렌더 루프·토글 즉시 갱신). 신선/만료(stale) 두 분기 모두 `showUsagePanel` 로 수렴한다 | `hub/bin/hub_template.html:1466-1490,1548,1563,1452-1462` |
| C12 | 패널 폭은 `min(420px, 100vw-32px)`, 본문 좌우 패딩 18px. 하단 여백은 `applyUsageClearance()` 가 실측 높이로 매 렌더 재계산하되 CSS 폴백 상수 `218px` 가 있고 "패널 내용이 바뀌면 재실측하라"는 주석이 달려 있다 | `hub/bin/hub_template.html:385-389,1427-1430` |
| C13 | 클라이언트는 30초 틱마다 `render()` 를 다시 부르고(패널 재계산), 60초마다 서버 폴링한다 | `hub/bin/hub_template.html:831-832,1628-1629` |
| C14 | 차트에 쓸 CSS 변수 팔레트가 이미 있다: `--accent`(#0072B2/#56B4E9)·`--muted`·`--soft`·`--line` (라이트/다크 각각 정의) | `hub/bin/hub_template.html:132-156` |
| C15 | `/hub status` 는 사용량 진단 필드 6종(`usage_sample_age_ms`·`rate_limit_capture_age_ms` 등)을 이미 보고하며, 전부 `show_usage_panel:false` 면 None 인 게이트 관례를 따른다 | `hub/bin/hub.py:127-214,217-251` |
| C16 | 배포는 `hub/install.sh` 가 `hub/bin` 최상위 파일을 복사하고 `HUB_FILE_COUNT=16` 으로 개수를 검증한다(실제 16개 확인). 단위 테스트는 `python3 -m unittest discover -s tests/hub`, 문서·상수 정합성은 `tests/run.sh` T25(현재 T25-155 까지) | `hub/install.sh:12,95-103`, `tests/run.sh:2577,2589-2593` |
| C17 | 캡처 파일 되읽기는 필드 단위 탈락(퍼센트가 이상하면 그 필드만 None) + 전부 없으면 레코드 탈락 규칙을 쓴다 — 새 이력 파서가 따를 검증 관례의 정본 | `hub/bin/hub_usage.py:175-217`, 검증 프리미티브 `hub_usage.py:75-91` |

### 2.2 런타임 사실 (이 머신 2026-08-27 실측)

| # | 사실 | 확인 방법 |
|---|------|----------|
| E1 | `~/.claude/hub/rate_limits.json` 실재 — 퍼센트 2종 모두 캡처됨(`session_used_percent:25`·`weekly_used_percent:30`) | `cat` |
| E2 | 이 머신의 `config.json` 은 `usage_api_enabled:true` — **두 생산자 모두 실가동 중**이라 추이 데이터가 즉시 쌓이기 시작한다 | `cat ~/.claude/hub/config.json` |
| E3 | `~/.claude/hub/` 에는 `usage_history` 류 디렉토리·파일이 없다 — 신규 도입이며 마이그레이션 대상 데이터가 없다 | `ls -la` |
| E4 | 이벤트 파일의 실제 줄은 60~130바이트대의 짧은 한 줄 JSON — C9 의 "1회 write append 안전" 논거가 성립하는 크기다 | `head events/<오늘>.jsonl` |

---

## 3. 확정된 전제 (재론하지 않는다)

1. **단일 정적 HTML, 빌드 단계 없음.** 차트 라이브러리·CDN·JS 러너를 도입하지 않는다 — 차트는 손으로 쓴 인라인 SVG 다.
2. **`#dzh-data` 계약에서 기존 최상위 필드는 불가침.** 새 최상위 필드 **추가**는 허용된다 — 구 템플릿은 모르는 필드를 무시하고, 신 템플릿은 필드 부재를 `|| []` 로 흡수한다(템플릿 세대 자가 치유 SH3~SH9 가 신구 불일치 창을 1 폴링 주기로 줄인다).
3. **불변식 H1′ 불변.** 추이 차트는 `#dzh-usage-body` **안**에 산다 — 폴링 갱신 대상 노드를 새로 만들지 않는다(C10).
4. **캡처 파일 계약 불변.** `rate_limits.json` 의 포맷·생산자·`same_capture_values` 게이트·`show_usage_panel:false` 시 읽기 중단(C7)은 그대로다.
5. **statusLine 절대 규칙 불변**(C4): 예외 금지 · 정상 상태(값 무변화) 파일 I/O 0회 · stdout 은 상태줄 한 줄뿐.
6. **hub/bin 에 새 모듈 파일을 만들지 않는다** — 순수 로직은 `hub_usage.py`, I/O 는 `hub_collect.py` 의 기존 경계에 얹는다. 따라서 `HUB_FILE_COUNT=16` 은 바뀌지 않는다(C16).

---

## 4. 설계 결정과 근거

### UH1. 수집 방식 — 「관측 변화 append」, 별도 샘플러 없음

추이 점은 **캡처 값이 실제로 바뀌어 캡처 파일이 다시 쓰이는 순간**(C3 게이트 통과 직후)에만 1점
append 한다. 유지보수 티커가 N분마다 현재 값을 재기록하는 「주기 샘플링」은 기각한다 —
① 서버가 꺼져 있으면(statusLine 만 가동) 공백이 생기고, ② 값이 안 변해도 중복 점이 쌓이며,
③ statusLine 출처의 값은 세션이 안 돌면 갱신되지 않으므로 주기 재기록은 "신선한 관측"이라는
거짓 주장을 만든다. 변화 단위 append 는 두 생산자 어느 쪽이 가동 중이든 동일하게 동작하고,
데이터량이 곧 정보량이다.

### UH2. 저장 포맷 — `usage_history/<YYYY-MM-DD>.jsonl`, 전체 이름 키

이벤트 로그의 검증된 선례(C9)를 그대로 따른다: 날짜별 JSONL, 1회 write() append(짧은 줄 =
동시 append 안전), 깨진 줄은 읽기에서 줄 단위 탈락, 보존은 파일 삭제. 키는 이벤트 파일의 축약
키(`t`·`e`…)가 아니라 캡처 파일(`rate_limits.json`)처럼 **전체 이름**을 쓴다 —
`{"observed_at_ms":…,"session_percent":…,"weekly_percent":…}`. 축약의 근거였던 고빈도·발췌
동봉(이벤트)이 여기엔 없고(§10 산정: 최악 하루 수백 줄), 같은 도메인(사용량)의 기존 파일과 어휘를
맞추는 쪽이 자기 설명적이다.

### UH3. append 지점 — 생산자 2곳의 기존 게이트 직후, 공용 I/O 함수 1개

`hub_collect.append_usage_history_from_capture(capture)` 하나가 투영+append 를 전담하고,
쓰기 지점 2곳(C2)이 각자의 게이트 통과 직후 이것을 부른다:

- `hub_statusline._run`: 캡처 쓰기 성공 후, **`load_config()` 를 변화 분기에서만 읽어**
  `show_usage_panel` 이 참일 때 append(UH4). 정상 상태(무변화) I/O 0회 규칙(전제 5)은 유지된다 —
  config 읽기·append 모두 변화 분기 안에만 있다.
- `hub_server._write_usage_api_capture`: 캡처 쓰기 직후 append. 이 경로는 호출자
  `_run_usage_api_poll_cycle` 이 이미 `show_usage_panel` 을 확인했다(C5) — 이중 확인하지 않는다.

`write_rate_limit_capture` **안**에 append 를 숨기는 안은 기각 — 그 함수는 "캡처 파일을 원자적으로
쓴다" 하나의 책임이고, statusLine 쪽 프라이버시 게이트(UH4)가 함수 안으로 들어가면 config 읽기가
서버 경로에서 중복된다. 쓰기 지점이 2곳뿐임은 C2 로 확정했고, 회귀는 UH-T12·T14 가 지킨다.

### UH4. 프라이버시 게이트 — `show_usage_panel:false` 면 이력을 **수집하지 않는다**

현행 원칙은 "스위치를 끄면 읽기 자체를 중단"(C7)이지만, 이력은 단일 현재값과 달리 **축적되는
기록**이라 쓰기 쪽도 막아야 진짜 제어다(사용량 API 생산자가 이미 같은 판단을 내렸다 — C5 의
GOTCHA 2). 스위치를 끄면: 수집(append) 중단 · 읽기(스냅샷 투영·진단) 중단 · 기존 파일은
보존 기한(UH7)에 따라 자연 소멸. 캡처 파일 자체의 statusLine 무조건 쓰기는 기존 동작이므로
건드리지 않는다(수술적 변경).

### UH5. 점의 성립 조건 — 퍼센트가 하나라도 있어야 1점

리셋 시각만 바뀐 캡처(퍼센트 둘 다 None — 캡처 계약상 네 값이 창별·필드별 독립 탈락한다,
`hub_usage.py:139-172`)는 추이 점을 만들지 않는다. 한쪽 퍼센트만 있으면 그 필드만 채운 점을
만든다 — 시리즈별로 그리므로(UH9) 반쪽 점도 정보다. 점의 시각은 `capture.captured_at_ms`
("이 값을 처음 관측한 시각", 결정 S3)를 그대로 쓴다 — 값 변화 시점의 의미와 정확히 일치한다.

### UH6. 스냅샷 투영 — 서버는 「정렬→연속 중복 접기→상한」만, 24시간 창은 클라이언트가

읽기는 오늘+어제 파일(이벤트와 같은 창, C9), 순수 선택은 ① `observed_at_ms` 정렬 ② 연속 동일값
(session·weekly 쌍이 같음) 접기 — **앞의 점을 남긴다**(첫 관측 시각 의미 보존, S3 와 동일 정신;
두 생산자의 근접 중복 append 도 여기서 흡수된다) ③ 최신 `USAGE_TREND_MAX_POINTS=720` 점 상한.
**24시간 창 필터는 서버에서 하지 않는다** — 하면 점이 창 경계를 빠져나갈 때마다
`snapshot_content_key`(C8)가 바뀌어 데이터 변화 없이도 hub.html 재작성이 발생한다. 창은 표시
관심사이므로 클라이언트가 `Date.now()` 기준으로 자른다. 결과: hub.html 재작성 트리거는 지금과
동일하게 **실제 데이터 변화뿐**이다.

### UH7. 보존 — 상수 7일, config 필드 추가 없음(YAGNI)

`USAGE_HISTORY_RETENTION_DAYS = 7` 모듈 상수. 표시 창(24h)+읽기 창(48h)보다 넉넉히 남겨 사후
진단 여지를 두되, `event_retention_days`(이벤트 보관) 설정과는 **결합하지 않는다** — 의미가 다른
두 보관을 한 필드에 묶으면 한쪽 요구가 다른 쪽을 끌고 다닌다. 조정 요구가 실제로 생기면 그때
HubConfig 로 승격한다. prune 은 `collect_snapshot` 의 기존 prune 지점(`hub_collect.py:490`) 옆에서
매 수집 사이클 무조건 실행한다(오래된 데이터 삭제는 스위치와 무관하게 프라이버시 긍정적).

### UH8. 표시 위치 — 기존 패널 펼침 본문 안, 별도 UI 없음

새 패널·새 페이지·새 폴링 대상을 만들지 않는다(전제 3). 차트는 `renderUsagePanel` 이 조립하는
본문 HTML 의 한 블록으로 들어가고, 신선/만료(stale) **두 분기 모두**에 그린다(UH10). 패널 자체의
표시 조건(usage 없으면 패널 전체 숨김, `hub_template.html:1466-1467`)은 바꾸지 않는다 — 추이는
패널의 장식이지 독립 표시 조건이 아니다(리셋 줄과 같은 지위, 결정 R3 승계).

### UH9. 차트 형태 — 0~100 고정 y축, [now−24h, now] x축, step-after, 시리즈 2개

- 값은 창 사용률의 **계단 함수**다(다음 관측까지 직전 값이 유효) — 선형 보간은 리셋 낙하(87%→3%)를
  존재하지 않는 사선으로 그리는 거짓말이므로 **step-after**(다음 점의 x 에서 이전 y 를 한 번 더 찍음)로
  그린다.
- **마지막 점 이후로 선을 늘이지 않는다**(외삽 금지) — 세션이 안 돌면 값이 어떻게 됐는지 모른다.
  관측이 없는 구간은 빈 채로 두는 것이 정직하다.
- 창 시작(now−24h)보다 오래된 점은 **마지막 1점만** x=0 에 고정해 앵커로 쓰고 나머지는 버린다 —
  창 진입 시점의 유효값으로 선이 시작되게 하는 최소 장치다.
- 시리즈: 세션 = `--accent` 실선, 주간 = `--muted` **파선** — 색+형태 2채널(이 템플릿의 색각 안전
  관례, 상태 배지의 색+글리프+텍스트 3채널과 같은 정신). 유효 점(해당 필드 non-null) 2개 미만인
  시리즈는 그리지 않고, 두 시리즈 다 못 그리면 블록 자체를 생략한다.
- y축 0~100 고정 — 자동 스케일은 5% 변동을 절벽처럼 그린다. 사용률의 절대 수준이 곧 의미다.

### UH10. stale 패널에서도 추이는 그린다

`is_stale` 은 "현재값의 유효기간 만료"(EX 계열)지 과거 기록의 무효가 아니다. 만료 분기에서도
추이 블록을 싣는다 — 오히려 "언제까지 쓰다 멈췄는지"가 이 상태에서 가장 유용한 정보다.

### UH11. 진단 — `/hub status` 에 `usage_history_points` 1개 필드

패널은 보이는데 추이만 없는 상태의 원인(①이력 파일 없음/점 부족 ②스위치 off)을 가를 창구.
스냅샷에 실릴 선택 결과의 점 개수를 보고하고, `show_usage_panel:false` 면 기존 관례대로
None(C15). 필드 1개로 충분하다 — "마지막 점 시각"은 `usage_sample_age_ms` 가 사실상 대신한다
(마지막 점 = 마지막 값 변화 = 캡처 갱신).

### UH12. 실패 처리 — 기존 어휘만 재사용, 새 실패 채널 없음

- append 실패: statusLine 경로는 `main()` 의 포괄 흡수(C4)가 덮고, 서버 경로는
  `_write_usage_api_capture` 의 기존 OSError→`record_collect_failure` 채널(C6)에 얹힌다.
  **append 는 캡처 쓰기 성공 후에만 시도한다** — 캡처 파일이 1차 계약, 이력은 파생이다.
- 읽기 실패·깨진 줄: `read_recent_events` 와 동일 계약(C9) — 파일 단위 실패는 경고 1건 +
  그 파일 건너뜀, 줄 단위 계약 불일치는 조용히 탈락, 디렉토리 부재는 정상(경고 0건).

### UH13. 스냅샷 필드명 — `usage_trend`

저장소(전체 이력)는 `usage_history/`, 화면 계약(선택된 점들)은 `HubSnapshot.usage_trend` 로
구분한다. 스냅샷은 표시용 투영이라는 기존 구분(캡처 → `usage`·`rate_limit_resets` 투영, 결정 P3)과
같은 작명 논리다.

### UH14. 기각한 대안 (요약)

| 대안 | 기각 사유 |
|------|----------|
| 유지보수 티커 주기 샘플링 | UH1 — 서버 오프 공백·중복 점·거짓 신선도 |
| 단일 JSON 배열 파일 재작성(append 대신) | 매 점마다 전체 파일 재작성 + 두 프로세스 동시 재작성 경합. JSONL append 는 선례로 검증됨(C9) |
| SQLite | 표준 라이브러리로 가능하나 개념 추가 대비 이득 없음 — 데이터가 하루 수 KB(§10) |
| 클라이언트 localStorage 축적 | 브라우저/탭별 파편화, file:// 모드와 서버 모드 불일치, 서버 재기동·다기기와 무관해야 함 |
| 차트 라이브러리 | 전제 1 위반 |
| 훅(hub_hook.py) 경유 수집 | 훅은 사용량을 모른다(전수 grep, C2) — 생산자가 아닌 곳에 세 번째 수집 경로를 만들 이유가 없다 |

---

## 5. 영향 범위

| 파일 | 변경 | 이유 |
|------|------|------|
| `hub/bin/hub_usage.py` | 추가 | 순수 계층: `UsageHistoryPoint` 타입, 투영·직렬화·파싱·선택 함수, 상수 2개 (§8.1) |
| `hub/bin/hub_collect.py` | 추가 + 소규모 리팩토링 | I/O 계층: append/read/prune, 스냅샷 투영 헬퍼, `_recent_event_file_paths` 의 날짜 경로 조립 일반화 (§8.2) |
| `hub/bin/hub_model.py` | 추가 | `HubSnapshot.usage_trend` 필드 (§7) |
| `hub/bin/hub_statusline.py` | 수정 | 변화 분기에 config 게이트 + append 호출 (UH3·UH4) |
| `hub/bin/hub_server.py` | 수정 | `_write_usage_api_capture` 에 append 호출 (UH3) |
| `hub/bin/hub.py` | 추가 | `/hub status` 의 `usage_history_points` (UH11) |
| `hub/bin/hub_template.html` | 추가 | 상수·순수 좌표 함수·`renderUsageTrend`·CSS, `renderUsagePanel` 시그니처 확장, 폴백 여백 재실측 (§9) |
| `hub/README.md` | 추가 | 사용량 패널 절에 추이 문단, 프라이버시 고지에 `usage_history/` (§12) |
| `tests/hub/test_hub_usage.py` 외 5개 테스트 파일 | 추가 | §11 |
| `tests/run.sh` | 추가 | T25-156·T25-157 (§11.3) |

**바뀌지 않는 것**: `rate_limits.json` 계약(전제 4) · `HubConfig`(새 설정 필드 없음, UH7) ·
`hub/install.sh`(새 파일 없음 → `HUB_FILE_COUNT=16` 유지, 전제 6) · `commands/hub.md`(status 필드를
나열하지 않음을 확인함 — 변경 불필요) · `hub_usage_fetch.py`(A-SEC 경계 무접촉) ·
`hub_hook.py`·`hub_settings.py`·`hub_daemon.py`.

---

## 6. 파일 구조와 모듈 경계

```
~/.claude/hub/                     (런타임, 저장소 아님)
├── rate_limits.json               현재값 캡처 — 기존 그대로
└── usage_history/                 ★신규 — 관측 변화 이력
    └── YYYY-MM-DD.jsonl           1줄 = 1점, append 전용, 7일 보존(UH7)

hub/bin/  (모듈 경계 — 기존 원칙 그대로)
├── hub_usage.py        ★순수. 점 타입·투영·(역)직렬화·선택. 파일시스템·시각에 닿지 않는다
├── hub_collect.py      I/O. append/read/prune + 스냅샷 조립. hub/bin 에서 파일시스템에 닿는 유일한 곳이라는 기존 선언 유지
├── hub_model.py        대외 계약. HubSnapshot 필드 추가만 — 계산 없음(결정 MS1 유지)
├── hub_statusline.py   생산자 ① — 게이트+append 호출 2~4줄
├── hub_server.py       생산자 ② — append 호출 1줄
├── hub.py              CLI — 진단 필드 1개
└── hub_template.html   표시 — 전부 #dzh-usage-body 내부(불변식 H1′ 준수)
```

데이터 흐름 (레이어 간 통신은 전부 명시적 타입):

```
RateLimitCapture ──(hub_usage.usage_history_point_from_capture, 순수)──▶ UsageHistoryPoint
      │                                                                       │ append (I/O, 생산자 2곳)
      ▼                                                                       ▼
rate_limits.json (현재값, 기존)                                usage_history/*.jsonl (이력, 신규)
                                                                              │ read_recent_usage_history (I/O)
                                                                              ▼
                                    hub_usage.select_usage_trend_points (순수) ──▶ HubSnapshot.usage_trend
                                                                              │ render_hub_html → #dzh-data
                                                                              ▼
                                                 renderUsageTrend (클라이언트, 24h 창은 여기서)
```

---

## 7. 데이터 모델

### 7.1 `hub_usage.UsageHistoryPoint` (신규, frozen dataclass)

```python
@dataclass(frozen=True)
class UsageHistoryPoint:
    """사용률 변화의 관측 1점 — RateLimitCapture 의 퍼센트 투영(UH5).

    observed_at_ms 는 capture.captured_at_ms(그 값을 '처음 관측한' 시각, 결정 S3)를 그대로 쓴다.
    두 퍼센트는 각각 없을 수 있으나 둘 다 없으면 점 자체가 만들어지지 않는다(UH5).
    """
    observed_at_ms: int
    session_percent: int | None    # rate_limits.five_hour.used_percentage 내림 정수(0~100)
    weekly_percent: int | None     # rate_limits.seven_day.used_percentage 내림 정수(0~100)
```

### 7.2 이력 파일 한 줄 (외부 계약 — 우리가 쓰고 우리가 읽는다)

```json
{"observed_at_ms": 1787792201052, "session_percent": 25, "weekly_percent": 30}
```

검증 규칙(파싱 시, C17 의 캡처 파일 관례 그대로):
`observed_at_ms` 는 엄격 int(`_is_valid_epoch_ms`, bool 배제) 아니면 **줄 전체 탈락**.
퍼센트 2종은 각각 `_is_valid_percent`(엄격 int 0~100) 불통과 시 **그 필드만 None**,
둘 다 None 이 되면 줄 탈락. JSON 불성립·dict 아님 → 줄 탈락. 예외는 절대 밖으로 내지 않는다.

### 7.3 `HubSnapshot` 확장 (hub_model.py:46-56)

```python
usage_trend: tuple[UsageHistoryPoint, ...] = ()   # 이력 선택 결과(UH6). 비면 차트를 그리지 않는다
```

`asdict` 재귀 직렬화로 `#dzh-data` 에 `usage_trend: [{observed_at_ms, session_percent,
weekly_percent}, …]` 로 실린다(projects 튜플과 같은 메커니즘, C8). 기본값 `()` 이므로 필드 추가에
따른 `snapshot_content_key` 변화는 배포 직후 1회 재작성으로 끝난다.

### 7.4 상수

| 상수 | 값 | 위치 | 근거 |
|------|----|------|------|
| `USAGE_TREND_MAX_POINTS` | `720` | hub_usage.py | 24시간을 2분 간격으로 채우는 수. 정당한 최대치(세션 창 상승 ~480 + 주간 상승 ~100 + 리셋 낙하 수 건 ≈ 600/일)를 여유 있게 덮으면서 hub.html 인라인 상한(§10)을 보장 |
| `USAGE_HISTORY_RETENTION_DAYS` | `7` | hub_collect.py | UH7 |
| `USAGE_TREND_WINDOW_MS` | `24 * MS_PER_HOUR` | 템플릿 | UH9. **반드시 `MS_PER_HOUR` 선언(현 906행) 뒤에 선언** — var 호이스팅으로 앞에 두면 NaN(기존 GOTCHA 2, `STALE_SESSION_HIDE_AFTER_MS` 선례) |

---

## 8. 인터페이스 (공개 함수 시그니처)

### 8.1 `hub_usage.py` (★순수 — 파일시스템·시각 무접촉 유지)

```python
def usage_history_point_from_capture(capture: RateLimitCapture) -> UsageHistoryPoint | None:
    """캡처를 추이 점으로 투영한다(UH5). 퍼센트가 둘 다 None 이면 None."""

def usage_history_line(point: UsageHistoryPoint) -> str:
    """점 하나를 이력 파일 한 줄(개행 없는 JSON)로 직렬화한다."""

def parse_usage_history_line(line: str) -> UsageHistoryPoint | None:
    """이력 파일 한 줄을 파싱한다. 계약 불일치는 None(§7.2 규칙) — 예외를 던지지 않는다."""

def select_usage_trend_points(
    points: Sequence[UsageHistoryPoint],
) -> tuple[UsageHistoryPoint, ...]:
    """정렬 → 연속 동일값 접기(앞 점 유지) → 최신 USAGE_TREND_MAX_POINTS 상한(UH6)."""
```

### 8.2 `hub_collect.py` (I/O)

```python
USAGE_HISTORY_DIR = HUB_HOME / "usage_history"
USAGE_HISTORY_RETENTION_DAYS = 7

def append_usage_history_from_capture(capture: hub_usage.RateLimitCapture) -> None:
    """캡처의 퍼센트 변화를 이력에 1줄 append 한다(UH3). 점이 안 만들어지면(UH5) 아무것도 안 한다.

    mkdir(parents) 후 오늘 날짜 파일에 1회 write() append(C9 선례). OSError 는 그대로 올린다 —
    두 호출자가 각자의 기존 방식(statusLine 포괄 흡수 · 서버 record_collect_failure)으로 처리한다(UH12).
    """

def read_recent_usage_history(
    now_ms: int,
) -> tuple[tuple[hub_usage.UsageHistoryPoint, ...], tuple[str, ...]]:
    """오늘+어제 이력 파일을 읽어 (시간순 점들, 경고들)을 돌려준다. 이 함수는 절대 예외를 던지지 않는다.

    read_recent_events(hub_collect.py:182-205)와 같은 계약: 디렉토리·파일 부재는 정상(경고 0),
    파일 읽기 실패는 그 파일만 건너뛰고 경고 1건, errors="replace" 디코딩, 깨진 줄은 줄 단위 탈락.
    """

def prune_old_usage_history_files(now_ms: int) -> None:
    """USAGE_HISTORY_RETENTION_DAYS 보다 오래된 날짜 파일을 삭제한다(prune_old_event_files 와 동형)."""

def _usage_trend_for_snapshot(
    now_ms: int, config: hub_model.HubConfig
) -> tuple[tuple[hub_usage.UsageHistoryPoint, ...], tuple[str, ...]]:
    """사설. show_usage_panel 이 꺼져 있으면 파일을 열지도 않고 ((), ()) (UH4, C7 과 같은 게이트)."""
```

호출 지점 배선:

```python
# hub_collect.collect_snapshot (487-528) — prune(490 옆) + 투영 + 스냅샷 필드
prune_old_usage_history_files(now_ms)
…
usage_trend, trend_warnings = _usage_trend_for_snapshot(now_ms, config)
warnings.extend(trend_warnings)
return hub_model.HubSnapshot(…, usage_trend=usage_trend, …)

# 소규모 리팩토링: _recent_event_file_paths(176-179)의 "오늘+어제 날짜 파일 경로" 조립을
# _recent_dated_jsonl_paths(directory, now_ms) 로 일반화해 이벤트·이력 양쪽이 공유한다(DRY).
```

```python
# hub_statusline._run — 변화 분기(33-35)만 확장 (UH3·UH4)
if not hub_usage.same_capture_values(previous, capture):
    hub_collect.write_rate_limit_capture(capture)
    config, _config_warnings = hub_collect.load_config()
    if config.show_usage_panel:
        hub_collect.append_usage_history_from_capture(capture)
```

```python
# hub_server._write_usage_api_capture (278-291) — 기존 try 안, 쓰기 성공 직후 (UH3·UH12)
if not hub_usage.same_capture_values(previous, capture):
    hub_collect.write_rate_limit_capture(capture)
    hub_collect.append_usage_history_from_capture(capture)
```

```python
# hub.py — 진단 (UH11), cmd_status(217-251)에 1키 추가
def _usage_history_points(now_ms: int, config: hub_model.HubConfig) -> int | None:
    """진단용 — 스냅샷에 실릴 추이 점 개수. 스위치 off 면 None(기존 게이트 관례, C15)."""
# cmd_status payload: "usage_history_points": _usage_history_points(now_ms, config),
```

### 8.3 클라이언트 (hub_template.html — 전부 렌더 IIFE 스코프)

```js
// 상수 (UH9·§7.4 — USAGE_TREND_WINDOW_MS 는 MS_PER_HOUR 선언 뒤!)
var USAGE_TREND_WINDOW_MS = 24 * MS_PER_HOUR;
var USAGE_TREND_LABEL = '최근 24시간';
var USAGE_TREND_CHART_WIDTH = 384;   // viewBox 좌표계 — 패널 본문 실폭과 일치시킬 필요 없음
var USAGE_TREND_CHART_HEIGHT = 56;
var USAGE_TREND_MIN_POINTS = 2;

/** 한 시리즈의 SVG polyline points 문자열. 유효 점 2개 미만이면 null. 순수 — DOM 무접촉.
    유효 점 = 해당 필드가 null 이 아니고 Number()/isFinite 통과(clampPercent 관례, C11 인접).
    창 밖(t < now-24h) 점은 마지막 1점만 x=0 앵커로 남긴다. step-after: 각 점 앞에
    (그 점의 x, 직전 y) 를 끼운다. y = H - clamp(v,0,100)/100*H. */
function usageTrendPolylinePoints(trendPoints, valueKey, nowMs) { … }

/** 추이 블록 HTML. 두 시리즈 다 null 이면 ''(블록 생략). 순수. */
function renderUsageTrend(trendPoints) { … }

// renderUsagePanel(usage, resets) → renderUsagePanel(usage, resets, trendPoints) 로 확장.
// 호출부 2곳(1548·1563) 모두 snapshot.usage_trend || [] 를 세 번째 인자로 넘긴다(전제 2).
```

---

## 9. 화면 사양

### 9.1 마크업 (renderUsagePanel 본문 조립에 삽입)

```html
<div class="usage-trend">
  <svg class="usage-trend-chart" viewBox="0 0 384 56" preserveAspectRatio="none"
       role="img" aria-label="최근 24시간 사용률 추이 (0~100%)">
    <polyline class="usage-trend-line-session" points="…"/>   <!-- 시리즈별로 있을 때만 -->
    <polyline class="usage-trend-line-weekly" points="…"/>
  </svg>
  <div class="usage-trend-legend">
    <span class="usage-trend-swatch usage-trend-swatch-session" aria-hidden="true"></span>세션
    <span class="usage-trend-swatch usage-trend-swatch-weekly" aria-hidden="true"></span>주간
    · 최근 24시간
  </div>
</div>
```

삽입 위치 — 신선 분기: `sessionBar + sessionResetRow + weeklyBar + weeklyResetRow` **뒤**,
`.usage-meta` 앞. 만료 분기: 두 stale 행+리셋 줄 뒤, `.usage-stale-note` 앞(UH10). 값은 전부
숫자(Number/isFinite 검증 후 문자열화)이고 라벨은 상수라 `escapeHtml` 대상이 없다 —
`renderUsageBar`(1352-1357)와 같은 방어 수준. 패널 안에 새 툴팁 트리거를 만들지 않는다
(결정 UT1·EX7 의 "유일한 예외는 stale note" 유지).

### 9.2 CSS (기존 `.usage-*` 블록 옆)

```css
.usage-trend{margin-top:10px}
.usage-trend-chart{display:block;width:100%;height:56px;background:var(--soft);border-radius:6px}
.usage-trend-line-session{fill:none;stroke:var(--accent);stroke-width:1.5;vector-effect:non-scaling-stroke}
.usage-trend-line-weekly{fill:none;stroke:var(--muted);stroke-width:1.5;stroke-dasharray:4 3;vector-effect:non-scaling-stroke}
.usage-trend-legend{font-size:11px;color:var(--muted);margin-top:4px;text-align:right}
.usage-trend-swatch{display:inline-block;width:14px;border-top:2px solid var(--accent);vertical-align:middle;margin:0 4px 0 8px}
.usage-trend-swatch-weekly{border-top-style:dashed;border-top-color:var(--muted)}
```

`vector-effect:non-scaling-stroke` 는 필수다 — `preserveAspectRatio="none"` 스트레치에서 선 굵기가
축별로 왜곡되는 것을 막는다. 팔레트는 기존 변수만 쓴다(C14) — 라이트/다크 모두 자동 대응.

### 9.3 레이아웃 후속 의무

패널 높이가 약 +80px(차트 56 + 여백 14 + 범례 ~15) 커진다. `applyUsageClearance()` 가 실측으로
매 렌더 보정하므로(C12) 동작은 자동이지만, **CSS 폴백 상수 `218px`(hub_template.html:388)와 그
재실측 주석(385-387)을 헤드리스 브라우저 실측값으로 갱신**해야 한다 — 주석 자체가 "내용이 바뀌면
같이 보라"고 요구한다. 30초 틱(C13)마다 `render()` → 차트가 새 `Date.now()` 창으로 다시 그려져
x축이 자연히 흐른다 — 추가 타이머 불필요.

---

## 10. 성능

이 저장소의 병목 원칙(측정 없는 최적화 금지)에 따라 산정 근거만 남긴다.

- **statusLine 핫패스(0.3초 주기)**: 무변화 경로 I/O 0회 **불변**(전제 5). 변화 경로에만
  `load_config`(수 KB JSON 1회 read) + append(1회 write) 추가 — 변화 빈도는 정의상 정수 퍼센트
  변화·리셋뿐이라 시간당 수십 회 상한.
- **데이터량**: 한 줄 ~75B. 정당한 최대 ~600점/일 ≈ 45KB/일, 7일 보존 ≈ 315KB 상한. 통상은
  일 수십 점(수 KB).
- **hub.html 인라인 증가**: `USAGE_TREND_MAX_POINTS=720` × ~75B ≈ **최악 +54KB**(현 154KB 대비),
  통상 +2~5KB. 상한이 상수로 보장된다.
- **재작성 빈도**: UH6 에 의해 hub.html 재작성 트리거는 기존과 동일(실제 값 변화 시에만) —
  창 경계 이동은 content_key 를 바꾸지 않는다.
- **수집 사이클 추가 비용**: 파일 2개(오늘+어제, 수십 KB) 읽기 + 순수 선택 — `collect_snapshot`
  이 이미 하는 이벤트 파일 읽기와 동급. 기존 에스컬레이션 조건(50ms, MD4)을 그대로 계승한다.

---

## 11. 테스트 계획

### 11.1 순수 로직 (stdlib unittest — `python3 -m unittest discover -s tests/hub`, C16)

`tests/hub/test_hub_usage.py`:

| # | 케이스 |
|---|--------|
| UH-T1 | `usage_history_point_from_capture`: 퍼센트 2종 → 점 / 한쪽만 → 반쪽 점 / 둘 다 None(리셋만) → None |
| UH-T2 | `usage_history_line` ↔ `parse_usage_history_line` 왕복 보존(반쪽 점 포함) |
| UH-T3 | `parse_usage_history_line` 탈락: 비 JSON·dict 아님·`observed_at_ms` 부재/문자열/bool → None |
| UH-T4 | 퍼센트 필드 단위 탈락: 범위 밖(101)·float·bool → 그 필드만 None, 둘 다 탈락하면 줄 탈락(§7.2) |
| UH-T5 | `select_usage_trend_points`: 시각 역순 입력이 정렬되어 나온다 |
| UH-T6 | 연속 동일값 접기 — **앞 점 유지**, 값이 바뀌었다 돌아온 (A,B,A) 는 3점 유지 |
| UH-T7 | 상한: 721점 입력 → 최신 720점 |
| UH-T8 | 빈 입력 → 빈 튜플 |

### 11.2 I/O·배선 (기존 temp-dir/patch 관례)

| # | 파일 | 케이스 |
|---|------|--------|
| UH-T9 | test_hub_collect.py | append: 디렉토리 자동 생성 · 오늘 날짜 파일에 줄 누적 · 리셋만 캡처는 무기록 |
| UH-T10 | test_hub_collect.py | read: 오늘+어제 병합 시간순 · 깨진 줄 탈락 · 파일 부재 경고 0 · 읽기 실패 경고 1 + 계속 진행 |
| UH-T11 | test_hub_collect.py | prune: 8일 전 파일 삭제 · 오늘/어제 보존 (기존 prune 테스트와 동형) · `_usage_trend_for_snapshot` 이 `show_usage_panel:false` 면 파일을 열지 않는다(UH4) |
| UH-T12 | test_hub_statusline.py | 값 변화 → 캡처 쓰기 + 이력 1줄 / 동일 재생 → 둘 다 0회 / `show_usage_panel:false` → 캡처는 쓰되 이력 무기록 / 이력 디렉토리 쓰기 불가 → 예외 없이 exit 0 + 캡처는 보존(기존 r29 계열 확장) |
| UH-T13 | test_hub_model.py | `usage_trend` 실린 스냅샷의 asdict 직렬화 · 점 추가 시 `snapshot_content_key` 변화, 창 무관 불변(UH6) |
| UH-T14 | test_hub_server.py | `_write_usage_api_capture`: 값 변화 시 이력 append · 게이트 불통과 시 무기록 · append OSError 가 `record_collect_failure` 로 흡수 |
| UH-T15 | test_hub.py | `usage_history_points`: 스위치 off → None / 이력 없음 → 0 / 점 존재 → 개수 |

### 11.3 문서·상수 정합성 (`tests/run.sh`)

- **T25-156**: `hub_model.py` 에 `usage_trend` 필드, `hub_template.html` 에 `usage_trend` 소비 코드와
  `.usage-trend-line-session`·`.usage-trend-line-weekly` 클래스가 존재한다.
- **T25-157**: `hub/README.md` 가 `usage_history/` 디렉토리와 「최근 24시간」 추이·보존 7일을 문서화한다.

완료 기준: 상기 전부 + 기존 스위트 무회귀(`tests/run.sh` 전체 통과).

---

## 12. 문서·진단·배포 변경

- **`hub/README.md`** — 「사용량 패널」 절(337행~)에 추이 문단 추가: 무엇이 보이나(24시간 스텝 차트,
  세션 실선·주간 파선) · 언제 나타나나(**관측 변화 2점 이상** — 도입 직후에는 값이 두 번 바뀔 때까지
  차트가 없다) · 관측 없는 구간은 선을 긋지 않는다(UH9) · 저장 위치(`usage_history/`)와 보존 7일 ·
  끄는 수단은 기존 `show_usage_panel:false` 하나(수집·표시 동시 중단, UH4) · 진단은
  `usage_history_points`. 프라이버시 고지 절(166-170행 인접)에 `usage_history/` 한 줄 추가.
- **배포**: 새 파일 없음 → `hub/install.sh` 무변경(T25-1 이 자동 검증). 기존 사용자 업그레이드 시
  마이그레이션 없음(E3) — 템플릿 세대 자가 치유(SH3~SH9)가 열린 탭을 갱신한다.

---

## 13. 리스크와 대안

1. **훅 미설치 + statusLine 만 활성인 구성에서 prune 이 안 돈다** — prune 은 수집 사이클에서만
   실행되는데(UH7), 수집은 훅·서버·`/hub` 가 이끈다. 이 구성에서는 이력이 계속 쌓인다.
   완화: 최악 증가율이 ~45KB/일(§10)로 무해하고, `/hub` 를 한 번 열면 정리된다. 검토한 대안
   (statusLine append 시 prune)은 핫패스에 디렉토리 스캔을 넣으므로 기각.
2. **두 생산자 동시 append 로 인한 근접 중복·순서 뒤섞임** — 읽기 쪽 정렬+접기(UH6)가 흡수하고,
   찢긴 줄은 줄 단위 탈락(UH12). 이벤트 로그가 같은 구조로 이미 수년치 실적이 있다(C9).
3. **statusLine 변화 분기의 config 읽기 추가** — 절대 규칙(예외 금지)은 `load_config` 가 예외를
   흡수하는 함수(`hub_collect.py:120-133`)라 침해되지 않지만, 변화 시 I/O 가 1회 늘어난다.
   검토한 대안(게이트 없이 무조건 append)은 UH4 의 프라이버시 판단과 충돌해 기각.
4. **차트의 오독 여지** — 관측 없는 구간의 공백을 "사용량 0"으로 읽을 수 있다. 범례에 창 라벨만
   두고 외삽하지 않는 현 설계(UH9)가 정직한 쪽이고, README 문단(§12)이 해석을 안내한다.
   축 눈금·호버 값 표시는 이번 범위에서 제외(패널 무툴팁 원칙 UT1 유지) — 요구가 생기면 별도 PRP.

---

## 14. 구현 순서 제안

1. `hub_usage.py` 순수 계층 + UH-T1~T8 (여기까지 I/O 무접촉으로 완결 검증)
2. `hub_collect.py` I/O + 스냅샷 배선 + UH-T9~T11
3. 생산자 2곳 배선(`hub_statusline.py`·`hub_server.py`) + UH-T12·T14
4. `hub_model.py` 필드 + UH-T13, `hub.py` 진단 + UH-T15
5. 템플릿(상수→순수 함수→renderUsagePanel 배선→CSS→폴백 여백 실측) + T25-156
6. `hub/README.md` + T25-157, 전체 스위트 실행

---

**승인 확인이 필요한 핵심 결정 (3줄)**

1. **UH4**: `show_usage_panel:false` 를 이력 **수집 중단**까지 확장한다(표시만 끄는 게 아니라).
2. **UH1·UH9**: 주기 샘플링이 아닌 「변화 관측 append」 + 관측 없는 구간은 선을 긋지 않는 정직한 스텝 차트.
3. **UH7**: 보존 7일·상한 720점은 config 없이 상수로 고정한다(필요가 실증되면 승격).
