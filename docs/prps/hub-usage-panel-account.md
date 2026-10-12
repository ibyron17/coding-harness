# PRP — 허브 사용량 패널에 계정 정보(요금제 · 조직 이름 · 이메일) 표시

> **상태: 승인됨.** §15 의 승인 항목 3건이 확정됐다(배치 안 B · `show_account_info` 기본 true · CLI 표시명).
>
> 설계 문서. **구현 코드는 이 문서에 없다.** 승인 후 `implementer` 가 이 문서를 입력으로 구현한다.
> 대상: 워크트리 `worktree-usage-panel-account` (HEAD `1290c71`) · 저장소 소스(`hub/bin/`)만 다룬다.
> 선행 정본: [`hub-theme-and-usage-panel.md`](./hub-theme-and-usage-panel.md) ·
> [`hub-usage-collapse-and-grid.md`](./hub-usage-collapse-and-grid.md) ·
> [`hub-usage-reset-time-and-refresh.md`](./hub-usage-reset-time-and-refresh.md) ·
> [`hub-card-cleanup-and-usage-source.md`](./hub-card-cleanup-and-usage-source.md)
>
> 이 PRP 는 기존 결정을 **폐기하지 않는다.** R3(초기화 시각은 패널의 장식 — 패널 게이팅 불변) ·
> UT1(패널 안 툴팁 트리거 없음) · U4(`show_usage_panel:false` 는 읽지 않는다) · D3(content_key
> 재작성 폭주 방지)를 그대로 물려받아 그 위에 얹는다. 개정 표기는 §9.
>
> 결정 번호 namespace: **AC**(Account). 단위 테스트 케이스는 **AT1~**, DOM 시나리오는 **D33~**
> (기존 최대 D32), 정적 가드는 **T25-264~** (기존 최대 T25-263 — 병합 직전 main 을 다시 세서
> 겹치면 다시 매긴다).
>
> 프리뷰 목업: 세션 스크래치패드의 `hub-usage-panel-account-mock.html`(+ `.png`) — 「현재 | 안 A |
> 안 B」 × 6개 상태(펼침 · 최소 폭 288px + 긴 값 · 만료 · 접힘 hover · 다크 · 값 일부 없음).

---

## 1. 요구사항 요약

허브 우하단 사용량 패널(`#dzh-usage`)은 지금 세션·주간 사용률과 초기화 시각만 보여 준다.
"이 한도가 **어느 계정**의 것인가"는 어디에도 없다 — 회사(Team)와 개인 계정을 오가는 사용자는
패널 숫자가 지금 로그인한 계정의 것인지 확인할 방법이 없다. 이 PRP 는 패널을 **펼쳤을 때**
로그인 계정의 **요금제 · 조직 이름 · 이메일**(사용자가 고른 세 항목, 이름은 제외)을 함께 보여
준다. 출처는 Claude Code 가 관리하는 `~/.claude.json` 의 `oauthAccount` 객체이며, 허브는 그
안의 **세 키만** 추출한다. 이메일·조직 이름은 새로 `~/.claude/hub/hub.html`(평문, 로컬 서버가
제공)에 남으므로 끄는 스위치와 프라이버시 고지를 함께 고친다.

### 성공 기준

| # | 기준 | 검증 |
|---|------|------|
| S1 | 사용량 패널을 펼치면 갱신 문구 아래에 `요금제 / 조직 / 이메일` 세 줄이 보인다 | DOM D33 + 수동 M1 |
| S2 | 접힘 요약(`세션 43% · 주간 71%`)은 바뀌지 않는다 — 접힌 상태에선 이메일이 안 보인다 | DOM D36 |
| S3 | 사용량 값이 없으면(패널 없음) 계정만으로 패널이 뜨지 않고, `~/.claude.json` 도 읽지 않는다 | 단위 C6 + DOM D34 |
| S4 | `show_account_info:false` 또는 `show_usage_panel:false` 면 `~/.claude.json` 을 열지 않는다 | 단위 C4·C5 |
| S5 | `oauthAccount` 의 다른 17개 키 값은 스냅샷·`hub.html`·경고·`/hub status` 어디에도 나오지 않는다 | 단위 AT13·C8 |
| S6 | 값에 `<img onerror=…>` 가 들어 있어도 HTML 로 해석되지 않는다 | DOM D33(XSS 픽스처) |
| S7 | 320px 화면에서 긴 이메일이 말줄임 없이 줄바꿈되고 패널이 가로로 넘치지 않는다 | DOM D36 |
| S8 | 파일 없음·깨짐·키 없음·타입 어긋남에서 수집과 패널은 종전대로 동작한다 | 단위 AT8~AT12·C1~C3 |

---

## 2. 확인된 사실 (재조사 대상 아님)

### 2.1 출처 (과제 지시로 확정)

- `~/.claude.json` 의 `oauthAccount` 키 20개(실측 목록, 값은 옮기지 않는다): accountUuid,
  emailAddress, organizationUuid, hasExtraUsageEnabled, billingType, accountCreatedAt,
  subscriptionCreatedAt, displayName, organizationRole, workspaceRole, organizationName,
  ccOnboardingFlags, claudeCodeTrialEndsAt, claudeCodeTrialDurationDays, seatTier, fullName,
  profileFetchedAt, organizationType, organizationRateLimitTier, userRateLimitTier.
- 토큰·비밀번호는 이 파일에 없다(자격 증명은 키체인).
- 지금 패널 데이터는 `rate_limits.json` 한 곳에서 온다. 계정 정보는 그 캡처에 없다.

### 2.2 요금제 판정 키 — 설계 단계에서 직접 확인함

이 머신의 요금제 키 실제 값: `billingType="stripe_subscription"`, `seatTier="team_tier_1"`,
`organizationType="claude_team"`, `organizationRateLimitTier="default_raven"`,
`userRateLimitTier="default_claude_max_5x"`.

설치된 CLI 바이너리(`~/.local/share/claude/versions/2.1.108`)에서 직접 찾은 코드:

```js
// 프로필 → subscriptionType 도출
switch(q /* organization.organization_type */){
  case"claude_max":K="max";break; case"claude_pro":K="pro";break;
  case"claude_enterprise":K="enterprise";break; case"claude_team":K="team";break;
  default:K=null;break}
// 표시명
function Dk_(){switch(f7()){case"enterprise":return"Claude Enterprise";case"team":return"Claude Team";
  case"max":return"Claude Max";case"pro":return"Claude Pro";default:return"Claude API"}}
// Max 20x 구분은 rateLimitTier 로 따로 한다
w = T==="max" && A==="default_claude_max_20x"
```

| 사실 | 설계에 미치는 영향 |
|------|-------------------|
| CLI 자신이 요금제를 **`organizationType` 하나**로 정한다 | 요금제 키는 `organizationType` 하나면 충분. `billingType`(결제 채널)·`seatTier`(좌석 등급, 요금제명이 아님)는 **읽지 않는다**(결정 AC1) |
| CLI 의 표시명은 `Claude Pro/Max/Team/Enterprise` | 같은 낱말을 쓴다 — 터미널 `/status` 와 허브가 다른 이름을 보이지 않게(결정 AC3) |
| 모르는 값에 CLI 는 `"Claude API"` 로 떨어진다 | 우리는 따라 하지 않는다 — 새 요금제 종류를 "API" 로 부르면 거짓이다(결정 AC3) |
| Max 5x/20x 는 `*RateLimitTier` 로만 갈린다 | 이번 범위에서 구분하지 않는다(키 1개 추가 비용, 승인 항목 3 의 선택지) |

### 2.3 코드 사실 (직접 읽고 확인)

| 위치 | 사실 | 영향 |
|------|------|------|
| `hub_template.html` `renderUsagePanel(usage, resets)` | `usage` 가 없으면 `hideUsagePanel()`. resets 는 장식(R3) | 계정도 같은 장식 지위로 둔다(결정 AC2) |
| 같은 함수 호출부 2곳(폴링 렌더 · 30초 틱) | 두 곳 다 `snapshot.usage, snapshot.rate_limit_resets` 를 넘긴다 | 두 곳 모두 3번째 인자 추가. 정적 가드 T25-266 |
| `hub_template.html` `escapeHtml` | `& < > " '` 전부 이스케이프 | 계정 값 3개 모두 이것을 거친다 |
| 같은 파일 머리 주석 106~109행 | "usage·rate_limit_resets 의 값은 모두 같은 statusLine 캡처 하나에서 온다" | 계정은 **다른 출처**임을 이 주석에 적는다(오독 방지) |
| `hub_collect.collect_snapshot` | 정확히 50줄(def~return). `_capture_for_snapshot` 이 패널 데이터를 1회 읽는다 | collect_snapshot 은 **늘리지 않는다** — §5.3 |
| `hub_collect.py` | 720줄 | +35줄 내외 → 약 755줄(800 상한 안). 넘으면 MS1 절차로 `hub_account_read.py` 분리 |
| `hub_model.snapshot_content_key` | `asdict(snapshot)` 전체를 키로 쓴다 | 계정 필드는 정적 문자열 3개라 재작성을 늘리지 않는다(D3 정합) |
| `hub_config._CONFIG_FIELD_TYPES` | bool 스위치 등록 선례(`show_usage_panel`·`record_prompt_excerpt`) | 같은 방식으로 1줄 |
| `tests/hub/*` | 실제 `$HOME` 그대로 돌고, 클래스마다 `hub_collect` 경로 상수를 바꿔 끼운다. `HUB_HOME` 만 바꾸는 클래스는 `RATE_LIMITS_PATH`(임포트 시 계산)를 못 바꾼다 | 바꿔 끼우기를 잊은 테스트가 **실제 `~/.claude.json`** 을 읽게 된다 → 결정 AC12 |
| `hub/install.sh` `HUB_FILE_COUNT=30` + T25-104·T25-149 | 배포 파일 수 고정 가드 | 새 모듈 1개 → 31 |

---

## 3. 확정된 전제 (재론하지 않는다)

1. python3 표준 라이브러리 전용, 단일 정적 HTML, 새 색 리터럴 0개(`var(--muted)`·`--ink`·`--line` 만).
2. ★순수 모듈은 파일·시각·환경변수에 닿지 않는다(`open(`/`Path(`/`time.`/`os.` 는 주석에도 금지).
3. 훅(`hub_hook.py`)은 건드리지 않는다 — 계정 정보는 수집 시점에 읽고, 훅은 자유 텍스트를 기록하지 않는다.
4. 터미널 세션 표시는 범위 밖.
5. `~/.claude.json` 은 **읽기만** 한다. 쓰기·잠금·백업 어느 것도 하지 않는다.
6. 실제 이메일·조직 이름 값은 이 문서·테스트·목업·보고 어디에도 쓰지 않는다 — 합성 값만.

---

## 4. 영향 범위

### 4.1 신규 파일

| 파일 | 이유 |
|------|------|
| `hub/bin/hub_account.py` | ★순수 · 잎 모듈. `oauthAccount` 계약 파서 + 요금제 표시명 대응표(§7.1) |
| `tests/hub/test_hub_account.py` | AT1~AT15 |
| `tests/hub/test_hub_template_dom_usage.py` | D33~D37 (기존 DOM 파일들은 시나리오 주제가 달라 섞지 않는다 — 800줄 상한 여유도 확보) |

### 4.2 수정 파일

| 파일 | 변경 |
|------|------|
| `hub/bin/hub_model.py` | `HubSnapshot.account: AccountInfo \| None = None` 1필드 · `HubConfig.show_account_info: bool = True` 1필드 · import 1줄 |
| `hub/bin/hub_config.py` | `_CONFIG_FIELD_TYPES` 에 `"show_account_info": bool` |
| `hub/bin/hub_collect.py` | `CLAUDE_GLOBAL_CONFIG_PATH` 상수 · `read_account_info()` · `_usage_panel_for_snapshot()`(§5.3) · `collect_snapshot` 배선(줄 수 불변) |
| `hub/bin/hub.py` | `/hub status` 에 `account_info_enabled`·`account_info_fields` 두 필드(값 미출력, 결정 AC11) |
| `hub/bin/hub_template.html` | CSS 3줄(`.usage-account`) · JS 상수 3개 + 순수 함수 2개 · `renderUsagePanel` 3번째 인자 · 호출부 2곳 · 머리 주석 갱신 |
| `hub/install.sh` | `HUB_FILE_COUNT` 30 → 31 |
| `hub/README.md` | 프라이버시 고지 1 bullet 신설 + 서버 노출 bullet 보강 · 「사용량 패널」에 「계정 정보」 소절 · 「알려진 한계」 2건 · 설정 표 1행 · 파일 배치 31개 + `hub_account.py` |
| `commands/hub.md` | `/hub install` 고지 ② 끝 1문장 · `/hub statusline on` 고지 1문장 · `/hub status` 필드 설명 1문단 |
| `docs/prps/hub-dashboard.md` | 모듈 구성표 「순수」 행에 `hub_account.py`(T25-104 계열이 이 표를 본다) |
| `tests/hub/__init__.py` | 빈 파일 → 경로 중화 몇 줄(결정 AC12) |
| `tests/hub/test_hub_collect.py` | C1~C9 |
| `tests/hub/test_hub.py` | status 두 필드(값 미출력 포함) |
| `tests/hub/test_hub_config.py` · `test_hub_model.py` | 새 스위치 타입 검증 · 새 필드 직렬화 |
| `tests/run.sh` | T25-104·T25-149 수 갱신 · 신규 T25-264~268(§11.4) |
| `tests/mutations.tsv` | 신규 가드마다 원장 1행 이상 |

### 4.3 미영향 — 건드리지 않는 이유

- `hub_usage.py` · `hub_statusline.py` · `hub_usage_fetch.py` · `hub_server.py`: 한도 캡처 계약은 그대로다. 계정은 다른 파일·다른 계약이다.
- `hub_hook.py`: 전제 3.
- `tests/run.sh` T26: 상시 컨텍스트(`CLAUDE.md`·`rules/README.md`·`rules/common`·`rules/workflow`)를 건드리지 않는다 → 래칫 상수 불변.
- `docs/images/*`: 스크린샷 갱신은 범위 밖(새로 찍을 때도 합성 픽스처만 — 기존 메모 정책).

---

## 5. 항목별 설계

### 5.1 출처와 허용 목록 (결정 AC1)

추출하는 키는 **정확히 셋**: `organizationType`(요금제 판정) · `organizationName` · `emailAddress`.

- `json.loads` 는 문서 전체(약 88KB)를 디코드할 수밖에 없다. 보장하는 경계는 **"추출 경계"**다 —
  `parse_account_info` 는 위 세 키 외의 값을 꺼내지 않고, 파싱한 dict 를 돌려주거나 보관하지
  않으며, 사유 문자열에도 입력 값을 넣지 않는다. 이것을 AT13(센티넬 전수)으로 기계적으로 고정한다.
- `billingType`·`seatTier` 를 쓰지 않는 근거는 §2.2 — CLI 자신이 쓰지 않는다.

### 5.2 표시 조건 (결정 AC2)

**계정 정보는 사용량 패널의 장식이다(R3 선례).** 패널을 띄우는 조건은 그대로 `usage` 하나다.

| 상태 | 패널 | 계정 줄 | `~/.claude.json` 읽기 |
|------|------|--------|---------------------|
| usage 있음(신선) | 표시 | 표시 | 읽음 |
| usage 있음(만료 `is_stale`) | 표시(조회되지 않음) | 표시 | 읽음 |
| usage 없음(캡처 없음·계약 불일치) | 숨김 | — | **읽지 않음** |
| `show_usage_panel:false` | 숨김 | — | 읽지 않음 |
| `show_account_info:false` | 종전대로 | 없음 | 읽지 않음 |

근거: ① 패널 제목이 「Claude 사용 한도」인데 한도 없이 계정만 있는 패널은 접힘 요약이 빈칸이
된다. ② **`hub.html` 에 남는 것 = 화면에 보일 수 있는 것** — usage 가 없을 때 계정을 스냅샷에
실으면 보이지도 않는 이메일이 평문 파일에만 남는다. 그래서 usage 가 없으면 아예 읽지 않는다.

계정 정보만 있고 한도 캡처가 없는 사용자(데스크톱 앱 전용 등)는 계정도 못 본다 — 그 경우
`/hub install`(상태줄 등록) 또는 `usage_api_enabled` 가 패널을 여는 기존 경로다. README 에 한 줄로 적는다.

### 5.3 읽기 계층 (결정 AC8·AC9)

`collect_snapshot` 은 이미 50줄이라 늘리지 않는다. 기존 `_capture_for_snapshot` 호출 줄을
새 사설 함수 `_usage_panel_for_snapshot` 호출로 **바꾸고**, 생성자에 `account=account` 1줄을
더하는 대신 `warnings.extend(...)` 줄을 생성자 인자 쪽으로 합쳐 줄 수를 상쇄한다(구현 재량,
결과가 50줄 이하이면 된다).

```
_usage_panel_for_snapshot(now_ms, config)
  usage, resets, warnings = _capture_for_snapshot(now_ms, config)     # 기존 그대로
  if usage is None or not config.show_account_info: return usage, resets, None, warnings
  account, account_warnings = read_account_info()
  return usage, resets, account, warnings + account_warnings
```

(`show_usage_panel:false` 면 `_capture_for_snapshot` 이 usage=None 을 돌려주므로 계정도 자동으로 안 읽힌다.)

**실패 처리 표(결정 AC9)** — 정본은 이 표다.

| 경우 | 결과 | 경고 | 근거 |
|------|------|------|------|
| 파일 없음 | None | 없음 | API 키 사용자·미로그인의 정상 상태 |
| 읽기 실패(`OSError`) | None | 1건(경로 + 사유) | 실제 I/O 실패 |
| JSON 파싱 실패 · 최상위 비객체 | None | 1건 | 계약 불일치 |
| `oauthAccount` 없음 또는 `null` | None | 없음 | 로그아웃·API 키 로그인의 정상 상태 |
| `oauthAccount` 가 객체 아님 | None | 1건 | 계약 불일치 |
| 객체인데 세 값이 **전부** 무효 | None | 1건("표시할 값이 없음 — 키 이름이 바뀌었을 수 있음") | 키 개명 같은 스키마 변경을 조용히 숨기지 않는다 |
| 일부 필드만 무효(타입 어긋남·빈 문자열·256자 초과·모르는 요금제) | 그 필드만 None | 없음 | 필드 단위 탈락(P2 의 퍼센트 선례) |

- 경고 문자열은 **경로와 사유 코드만** 담는다 — 입력 값은 절대 넣지 않는다(AT14). 사유 문자열은
  순수 모듈이 만들고 경로는 `hub_collect` 가 붙인다(`hub_config.config_from_raw` 선례).
- 읽기는 `read_text(encoding="utf-8", errors="replace")`(read_rate_limit_capture 의 검수 M1 선례 —
  `UnicodeDecodeError` 가 `except OSError` 를 뚫지 않게).
- `except` 는 로컬 파일 선례대로 `(json.JSONDecodeError, TypeError)`. `RecursionError` 는 원격 응답
  경로에만 잡는 것이 이 저장소의 기존 결정이다(AR4/B-1) — 이 파일은 CC 가 쓰는 로컬 파일이라 따른다.

### 5.4 요금제 표기 (결정 AC3)

| `organizationType` | 표시 |
|--------------------|------|
| `claude_pro` | `Claude Pro` |
| `claude_max` | `Claude Max` |
| `claude_team` | `Claude Team` |
| `claude_enterprise` | `Claude Enterprise` |
| 그 밖의 문자열 · 없음 · 비문자열 | **그 줄 생략**(경고 없음) |

- 줄 이름(dt)은 한국어 `요금제`, 값은 제품 고유명사라 번역하지 않는다 — CLI 표시명(§2.2)과 같은 낱말.
- 모르는 값을 원문(`claude_xyz`) 그대로 보이지 않는 이유: 내부 식별자는 사용자에게 의미가 없고,
  CLI 처럼 "Claude API" 로 떨어뜨리면 거짓이다. 새 종류가 생기면 대응표 1행으로 고친다 —
  그 사이에도 `/hub status` 의 `account_info_fields.plan:false` 로 "값이 있는데 못 알아봄"이 아니라
  "요금제 줄이 없음"이 드러난다(원문은 진단에 필요하면 사용자가 `~/.claude.json` 을 직접 본다).

### 5.5 이메일·조직 이름 (결정 AC4)

- **전체 표시**(사용자 요구). 마스킹·말줄임 없음. 좁은 폭에서는 `overflow-wrap:anywhere` 로 줄바꿈.
- 앞뒤 공백 제거 후 빈 문자열이면 None. **256자 초과는 버린다**(자르지 않는다 — 잘린 이메일은
  틀린 이메일이다). 256 = 이메일 경로 상한(254)을 덮는 최소 2의 거듭제곱 — 조직 이름에도 같은
  상한을 쓴다(규칙이 하나면 설명도 테스트도 하나다, `_is_valid_epoch_ms` 의 선례 문구).
- 툴팁을 달지 않는다(UT1 유지) — 전문이 줄바꿈으로 이미 보이므로 툴팁이 줄 정보가 없다.

### 5.6 화면 배치 (결정 AC5·AC6) — 목업 참조

**안 B(권장): 펼침 본문 맨 아래, 갱신 문구(`.usage-meta`/`.usage-stale-note`) 아래, 구분선 1px.**

```html
<dl class="usage-account">
  <dt>요금제</dt><dd>Claude Team</dd>
  <dt>조직</dt><dd>Example Labs</dd>
  <dt>이메일</dt><dd>dev.user@example.com</dd>
</dl>
```

```css
.usage-account{display:grid;grid-template-columns:auto minmax(0,1fr);column-gap:12px;row-gap:2px;margin:10px 0 0;padding-top:8px;border-top:1px solid var(--line);font-size:11.5px}
.usage-account dt{color:var(--muted)}
.usage-account dd{margin:0;color:var(--ink);text-align:right;overflow-wrap:anywhere}
```

| 안 | 배치 | 장점 | 대가 |
|----|------|------|------|
| **B (권장)** | 맨 아래 | 막대 위치가 지금과 같다 — 가장 자주 보는 숫자의 자리가 안 바뀐다. 「메타 정보」 영역에 묶여 계정 불일치(§5.8) 때 "이 숫자 = 이 계정"이라는 강한 주장을 덜 한다 | 계정을 먼저 확인하려면 시선이 아래로 내려가야 한다 |
| A | 맨 위(제목 바로 아래) | "누구의 한도인가"를 먼저 답한다 | 막대가 약 55px 아래로 밀린다. 불일치 때 오해가 더 크다 |

공통:
- **접힘 요약은 바꾸지 않는다.** 요약에 요금제를 붙이는 안(`Team · 세션 43% · 주간 71%`)은 기각 —
  접힘 알약 폭이 늘고, 접힘은 "숫자만 빨리 보기" 상태다.
- 마크업은 `dl/dt/dd` — 스크린리더가 `요금제, Claude Team` 처럼 이름-값 쌍으로 읽는다. 별도 aria
  문구는 두지 않는다(`dl` 의 `aria-label` 은 낭독 지원이 고르지 않다).
- 값 3개 모두 `escapeHtml` 을 거친다. 요금제 표시명은 고정 대응표에서 오지만 같은 경로를 탄다
  (분기 없는 한 경로가 검사하기 쉽다).
- 일부 값만 있으면 그 쌍만 생략, 셋 다 없으면 `dl` 자체를 만들지 않는다(빈 목록을 접근성 트리에
  남기지 않는다 — V3 선례).
- 패널 높이가 약 55px 늘지만 `applyUsageClearance()` 가 실측하므로 상수 변경 없음. 상세보기 창
  위치는 패널과 무관(SC16 개정) — D29 회귀 없음.

### 5.7 끄는 스위치 (결정 AC7)

`config.json` 의 **`show_account_info`(bool, 기본 `true`)**.

- 필요한 이유: 이메일·조직 이름은 프롬프트 발췌와 다른 **신원 정보**이고, 화면 공유·로컬 포트
  노출이라는 새 노출이다. 사용량은 보되 신원은 숨기고 싶은 사용자에게 `show_usage_panel:false`
  (패널 전체 끄기)만 주는 것은 과하다.
- 기본값 `true` 의 근거: 사용자가 요청한 기능이고, 같은 등급의 로컬 전용 노출인
  `record_prompt_excerpt`·`show_usage_panel` 이 모두 옵트아웃(기본 켬)이다. 옵트인(기본 끔)은
  자격 증명을 만지거나 외부로 나가는 `usage_api_enabled` 에만 쓴 기준이며, 이 기능은 둘 다 아니다.
- 끄면 **파일을 열지 않는다**(U4 와 같은 원칙 — CSS 숨김이 아니라 읽기 중단이 진짜 제어).
- 필드별 스위치는 두지 않는다(YAGNI).

### 5.8 계정 불일치 (결정 AC10)

캡처(`rate_limits.json`)에는 계정 식별자가 없다. 로그인 계정을 바꾸면 다음 세션 응답이 캡처를
덮어쓸 때까지 **새 계정 이름 아래 옛 계정 숫자**가 보일 수 있다(사용량 API 폴링 경로는 키체인의
현재 자격 증명을 쓰므로 다음 폴링에서 맞춰진다).

**한계 명시로 충분하다고 판단한다.** 해소하려면 캡처에 계정 UUID 를 넣어야 하는데 statusLine
입력에는 계정 정보가 없고, 생산자 2개(statusLine·API)의 캡처 포맷을 함께 바꿔야 한다 — 이 기능의
가치 대비 비용이 크다. README 「알려진 한계」에 적는다:
"계정을 바꾼 직후에는 세션을 한 번 돌리기 전까지 패널의 숫자가 이전 계정 것일 수 있다."

함께 적을 한계: `CLAUDE_CONFIG_DIR` 로 설정 위치를 옮긴 사용자는 허브의 다른 경로들처럼
`~/.claude.json` 고정 경로를 따르지 않는다(허브 전체가 `~/.claude` 를 고정으로 쓴다 — 새 한계가 아니라 기존 한계의 적용).

### 5.9 프라이버시 고지 (문서)

`hub/README.md` 「프라이버시 고지」에 bullet 1개 신설(사용량 패널 bullet 바로 아래):

> 사용량 패널이 떠 있으면 **로그인 계정의 요금제·조직 이름·이메일**도 `hub.html` 에 인라인된다.
> 출처는 Claude Code 의 `~/.claude.json`(`oauthAccount`)이며 허브는 그 안에서 `organizationType`·
> `organizationName`·`emailAddress` **세 값만** 꺼낸다 — 계정 ID·이름·역할 등 나머지 값은 꺼내지
> 않고, 파일에 쓰지도 않는다. 이메일은 패널을 **펼쳤을 때만** 화면에 보인다(화면 공유 시 접어
> 두면 가려진다). 끄는 수단은 `config.json` 의 `show_account_info: false`(이 파일을 아예 읽지
> 않는다) 또는 `show_usage_panel: false`. `/hub status` 는 이 값들을 출력하지 않는다.

서버 노출 bullet(212~218행)의 "`hub.html` 에 인라인된 프롬프트 발췌를 읽거나" 를
"…프롬프트 발췌·계정 이메일과 조직 이름을 읽거나" 로, 끄는 수단 목록에 `show_account_info:false` 를 더한다.

`commands/hub.md`:
- `/hub install` 고지 ② 끝: "사용량 패널을 펼치면 로그인 계정의 요금제·조직 이름·이메일도 보이며
  (`~/.claude.json` 에서 세 값만 읽음) `hub.html` 평문에 인라인됩니다 — `show_account_info:false` 로 끌 수 있습니다."
- `/hub statusline on` 고지: 같은 1문장.
- `/hub status` 필드 설명: §7.3.

`/hub status` 에 값을 싣지 않는 이유(결정 AC11): 그 출력은 Claude 세션에 들어가 **transcript 에
영구 기록**된다 — 상태 점검 한 번이 이메일을 모든 세션 기록에 복사하게 된다.

---

## 6. 데이터 모델

### 6.1 신규 — `hub_account.AccountInfo`

```python
@dataclass(frozen=True)
class AccountInfo:
    """로그인 계정의 표시용 3값 — ~/.claude.json oauthAccount 의 투영(결정 AC1). 각각 없을 수 있다."""

    plan_label: str | None          # organizationType 대응표 결과("Claude Team" 등). 모르는 값이면 None
    organization_name: str | None   # oauthAccount.organizationName (공백 제거, 1~256자)
    email: str | None               # oauthAccount.emailAddress (공백 제거, 1~256자)
```

불변식: 세 필드가 **모두 None 인 AccountInfo 는 만들지 않는다**(그 경우 None).

### 6.2 변경 — `hub_model`

```python
class HubConfig:  ...
    show_account_info: bool = True   # false 면 ~/.claude.json 을 아예 읽지 않는다(결정 AC7)

class HubSnapshot: ...
    rate_limit_resets: RateLimitResets | None = None
    account: AccountInfo | None = None   # usage 가 있을 때만 채워진다(결정 AC2). 출처는 rate_limits.json 이 아니라 ~/.claude.json
    template_stamp: str = ""
```

`#dzh-data` JSON 키: `"account": {"plan_label": …, "organization_name": …, "email": …} | null`.

### 6.3 유지

`UsageSample`·`RateLimitResets`·`RateLimitCapture`·`rate_limits.json` 포맷 — 전부 불변.

---

## 7. 인터페이스 (공개 함수 시그니처)

### 7.1 `hub/bin/hub_account.py` (★순수 · 잎 — `json`·`dataclasses` 만 임포트)

```python
ACCOUNT_FIELD_MAX_CHARS = 256
ACCOUNT_PLAN_LABELS: dict[str, str] = {
    "claude_pro": "Claude Pro", "claude_max": "Claude Max",
    "claude_team": "Claude Team", "claude_enterprise": "Claude Enterprise",
}

def parse_account_info(text: str) -> tuple[AccountInfo | None, str | None]:
    """~/.claude.json 본문에서 계정 3값을 꺼낸다. (결과, 계약 불일치 사유) — 예외를 던지지 않는다.

    사유는 경로·입력 값을 담지 않는 고정 문구다(경로는 호출자가 붙인다). 정상적인 부재
    (oauthAccount 없음·null)는 (None, None).
    """
```

사설 헬퍼(이름은 구현 재량): `_valid_account_text(value: object) -> str | None`(str·strip·1~256자) ·
`_plan_label(value: object) -> str | None`(대응표 조회).

### 7.2 `hub/bin/hub_collect.py` (I/O)

```python
# Claude Code 가 쓰는 전역 설정 — 우리가 소유하지 않는 읽기 전용 입력이다. oauthAccount 의
# 세 값만 꺼낸다(결정 AC1, docs/prps/hub-usage-panel-account.md).
CLAUDE_GLOBAL_CONFIG_PATH = Path.home() / ".claude.json"

def read_account_info() -> tuple[hub_account.AccountInfo | None, tuple[str, ...]]:
    """~/.claude.json 에서 계정 표시 3값을 읽는다. 절대 예외를 던지지 않는다(§5.3 표가 정본)."""

def _usage_panel_for_snapshot(
    now_ms: int, config: hub_model.HubConfig
) -> tuple[hub_usage.UsageSample | None, hub_usage.RateLimitResets | None,
           hub_account.AccountInfo | None, tuple[str, ...]]:
    """사용량 패널에 실을 세 덩어리를 고른다(사설). usage 가 없거나 스위치가 꺼지면 계정을 읽지 않는다(결정 AC2·AC7)."""
```

### 7.3 `hub/bin/hub.py` (CLI)

```python
def _account_info_fields(config: hub_model.HubConfig) -> dict | None:
    """진단용 — 계정 3값의 **유무만**(값은 절대 싣지 않는다, 결정 AC11). 스위치 off·읽기 실패·부재면 None."""
```

`cmd_status` 출력에 추가:
- `"account_info_enabled": config.show_usage_panel and config.show_account_info`
- `"account_info_fields": {"plan": bool, "organization": bool, "email": bool} | null`

(status 는 usage 유무와 무관하게 스위치만 보고 읽는다 — "계정은 읽히는데 패널이 없다"를 구분하려는 진단 창구다.)

### 7.4 `hub/bin/hub_template.html` (JS)

```js
var ACCOUNT_PLAN_TERM = '요금제';
var ACCOUNT_ORGANIZATION_TERM = '조직';
var ACCOUNT_EMAIL_TERM = '이메일';

// 이름-값 한 쌍. 값이 비문자열·빈 문자열이면 ''. 순수 — DOM 에 닿지 않는다.
function renderUsageAccountPair(term, value){ … '<dt>' + term + '</dt><dd>' + escapeHtml(value) + '</dd>' }
// 계정 블록. account 가 없거나 쌍이 0개면 ''.
function renderUsageAccount(account){ … '<dl class="usage-account">' + pairs + '</dl>' }

function renderUsagePanel(usage, resets, account){ … }   // 두 분기(만료·신선) 모두 본문 끝에 renderUsageAccount(account)
```

호출부 2곳: `renderUsagePanel(snapshot.usage, snapshot.rate_limit_resets, snapshot.account);`

머리 주석(106~109행) 뒤에 1문장: "account(있으면)는 펼침 본문 끝에 계정 줄로 더해진다 — 이 값만은
statusLine 캡처가 아니라 `~/.claude.json` 에서 온다(docs/prps/hub-usage-panel-account.md 결정 AC1·AC2)."

---

## 8. 설계 결정과 근거 (요약표)

| # | 결정 | 한 줄 근거 |
|---|------|-----------|
| AC1 | 추출 키 = `organizationType`·`organizationName`·`emailAddress` 셋 | CLI 자신이 요금제를 `organizationType` 으로만 정한다(§2.2). 읽는 키가 적을수록 노출면이 작다 |
| AC2 | 계정은 패널의 장식 — usage 가 없으면 패널도 계정 읽기도 없다 | R3 선례. `hub.html` 에 남는 것 = 화면에 보일 수 있는 것 |
| AC3 | 요금제 = CLI 표시명 그대로, 모르는 값은 그 줄 생략 | 터미널과 같은 낱말. 내부 식별자 노출·"API" 오표기 둘 다 피한다 |
| AC4 | 이메일·조직 전체 표시, 줄바꿈, 256자 초과는 버림 | 사용자 요구(전체 표시). 잘린 이메일은 틀린 값이다 |
| AC5 | 펼침 본문 맨 아래(안 B), 접힘 요약 불변 | 막대 자리를 지키고, 불일치 때 오해를 줄인다. 이메일은 펼쳤을 때만 보인다 |
| AC6 | `dl/dt/dd` · `escapeHtml` · 툴팁 없음 | 스크린리더 이름-값 낭독. UT1 유지 |
| AC7 | `show_account_info`(기본 true), off 면 파일 미열람 | 신원 정보의 새 노출 → 패널 전체를 끄지 않고 신원만 끌 수단. 옵트아웃 선례 |
| AC8 | 새 잎 순수 모듈 `hub_account.py` + `HubSnapshot.account` | 다른 외부 계약(다른 파일·다른 소유자). `hub_usage.py` 는 "다루는 외부 포맷은 하나다"를 스스로 선언한다. `UsageSample` 확장은 캡처 투영 의미를 깨서 기각 |
| AC9 | 실패 처리 표(§5.3) — 정상 부재는 무경고, 계약 불일치는 경고 1건, 필드는 단위 탈락 | `read_rate_limit_capture`·P2 선례. 키 개명은 조용히 숨기지 않는다 |
| AC10 | 계정 불일치는 한계 명시 | 해소 비용(두 생산자 캡처 포맷 변경)이 가치보다 크다 |
| AC11 | `/hub status` 는 유무 불리언만 | status 출력은 transcript 에 영구 기록된다 |
| AC12 | `tests/hub/__init__.py` 가 `hub_collect.CLAUDE_GLOBAL_CONFIG_PATH` 를 존재하지 않는 경로로 중화 | 바꿔 끼우기를 잊은 테스트가 실제 이메일을 읽는 대신 **아무것도 읽지 않게**(fail-closed). 한 곳에서 전 테스트를 덮는다 |
| — | **디자인 패턴 도입 없음** | dataclass 1개 + 순수 함수 1개(+헬퍼 2) + I/O 함수 2개 + JS 순수 함수 2개 + CSS 3줄 |

---

## 9. 구 PRP 개정 표기 (구현 범위 — 원문 삭제 금지)

| 문서 | 위치 | 덧붙일 표기 |
|------|------|------------|
| `hub-usage-reset-time-and-refresh.md` | 결정 R3(초기화 시각 = 장식) | "→ 같은 지위를 계정 줄에도 적용(hub-usage-panel-account.md 결정 AC2)" |
| `hub-card-cleanup-and-usage-source.md` | 결정 P1(퍼센트 단일 출처) | "→ 패널의 **계정 줄**만은 `~/.claude.json` 에서 온다 — 퍼센트·초기화 시각의 단일 출처 원칙은 불변(결정 AC1)" |
| `hub-dashboard.md` | 모듈 구성표 「순수」 행 | `hub_account.py` 추가 |

---

## 10. GOTCHA

1. **테스트가 실제 `~/.claude.json` 을 읽는다.** 단위 테스트는 실제 `$HOME` 으로 돈다. 사용량
   캡처를 만드는 테스트가 `collect_snapshot` 을 부르면 이제 계정 읽기까지 간다. 결정 AC12 의
   패키지 수준 중화가 1차 방어, 계정 테스트는 각자 임시 파일로 덮고 tearDown 에서 **중화값으로**
   되돌린다(원래 실제 경로로 되돌리면 안 된다). 직접 실행(`python3 tests/hub/x.py`)은 패키지를
   안 거쳐 중화가 빠진다 — 정본 명령(`-m unittest discover -s tests/hub -t .`)만 보장한다고 주석에 적는다.
2. **경고·사유 문자열에 값을 넣지 않는다.** `f"... ({payload!r})"` 같은 디버그 편의가 이메일을
   `hub.html` 의 경고 줄(화면에 보인다)로 흘린다. AT14·C8 이 고정한다.
3. **`renderUsagePanel` 호출부는 2곳이다.** 30초 틱 쪽을 빠뜨리면 첫 렌더에만 계정이 보이고 30초
   뒤 사라진다. T25-266 이 두 곳을 센다.
4. **`collect_snapshot` 50줄.** 지금 정확히 50줄 — 배선은 사설 함수 안에서 한다(§5.3).
5. **`hub_collect.py` 800줄.** 약 755줄 예상. 넘으면 MS1 절차로 `hub_account_read.py` 분리(그때는
   배포 파일 수 31 → 32 와 T25-104·149 를 다시 고친다).
6. **`~/.claude.json` 은 CC 가 자주 다시 쓴다.** 쓰는 도중 읽으면 JSON 파싱 실패 경고가 한 수집
   주기(5초) 동안 보였다 사라질 수 있다(리스크 R2).
7. `dd` 의 `overflow-wrap:anywhere` 는 grid 칸에 `minmax(0,1fr)` 가 있어야 듣는다(`1fr` 만 쓰면
   min-content 가 긴 이메일 폭이 되어 패널이 넘친다 — 목업 2행에서 확인한 형태).

---

## 11. 테스트 계획

### 11.1 신규 — `tests/hub/test_hub_account.py` (★순수)

| # | 입력 | 기대 |
|---|------|------|
| AT1 | 세 키 정상(합성 값) | `AccountInfo("Claude Team", "Example Labs", "dev.user@example.com")`, 사유 None |
| AT2 | `organizationType` 4종 각각 | 대응표 표시명과 정확히 일치(4케이스, subTest) |
| AT3 | 모르는 `organizationType`(`"claude_future"`) | plan_label None, 나머지 유지, 사유 None |
| AT4 | `organizationType` 없음·`null`·숫자·bool | plan_label None |
| AT5 | `emailAddress`·`organizationName` 이 숫자·리스트·bool·객체 | 그 필드만 None |
| AT6 | 빈 문자열·공백만·앞뒤 공백 | None / None / 공백 제거된 값 |
| AT7 | 256자 / 257자 | 유지 / None (경계) |
| AT8 | `oauthAccount` 키 없음 | (None, None) |
| AT9 | `oauthAccount: null` | (None, None) |
| AT10 | `oauthAccount` 가 문자열·리스트 | (None, 사유) |
| AT11 | 깨진 JSON · 최상위 리스트 · 빈 문자열 | (None, 사유) |
| AT12 | 객체인데 세 값 전부 무효 | (None, 사유) — 키 개명 감지 |
| AT13 | **허용 목록 전수**: 20개 키 전부 `"SENTINEL-<키>"` 로 채운 픽스처 | `json.dumps(asdict(결과))` 에 emailAddress·organizationName 센티넬만 있고 나머지 18개 센티넬은 0건 |
| AT14 | AT10·AT11·AT12 입력에 센티넬을 심음 | 사유 문자열에 센티넬 0건 |
| AT15 | 결과 객체 | frozen(대입 시 `FrozenInstanceError`) |

### 11.2 추가 — `tests/hub/test_hub_collect.py`

| # | 시나리오 | 기대 |
|---|---------|------|
| C1 | 파일 없음 | (None, ()) |
| C2 | 경로가 디렉터리(읽기 실패) | None + 경고 1건, 경고에 경로 포함·값 미포함 |
| C3 | 깨진 JSON | None + 경고 1건 |
| C4 | `show_account_info:false` + 캡처 있음 | 계정 None, **파일 미열람**(`read_account_info` 를 `mock.patch.object` 로 감시해 호출 0회) |
| C5 | `show_usage_panel:false` | 미열람 |
| C6 | 캡처 없음(usage None) + 계정 파일 있음 | 계정 None, 미열람 |
| C7 | 만료 캡처(`is_stale`) + 계정 파일 | 계정 채워짐 |
| C8 | 정상 수집 → `render_hub_html` | 결과 HTML 에 이메일 센티넬 있음, `fullName`·`displayName`·`accountUuid`·`organizationUuid` 센티넬 0건 |
| C9 | 같은 입력으로 두 번 수집(시각만 다름) | `snapshot_content_key` 동일(D3 정합) |

`tests/hub/test_hub.py`: `account_info_enabled`·`account_info_fields` 값 확인 + 출력 JSON 전체에
이메일 센티넬 0건(AC11). `test_hub_config.py`: `show_account_info` 에 문자열 → 타입 경고 + 기본값.
`test_hub_model.py`: `account` 필드가 `#dzh-data` 에 직렬화되고 `</script>` 이스케이프를 거친다.

### 11.3 신규 — `tests/hub/test_hub_template_dom_usage.py` (헤드리스 Chrome, 기존 하네스)

| # | 시나리오 | 기대 |
|---|---------|------|
| D33 | 신선 usage + 계정 3값, 조직 이름에 `<img src=x onerror=…>` | `.usage-account` 가 `.usage-meta` **뒤**에 있다 · dt 순서 `요금제/조직/이메일` · `#dzh-usage-body img` 0개 · dd textContent 가 원문과 같다 |
| D34 | usage null + 계정 있음 | `#dzh-usage.hidden === true` |
| D35 | plan_label null / account null | dt 2개 / `.usage-account` 없음 |
| D36 | 320px 뷰포트, 257자 미만의 긴 이메일 | 패널 `scrollWidth <= clientWidth` · 토글로 접으면 `#dzh-usage-summary` 텍스트가 `세션 43% · 주간 71%` 그대로 · 접힘 상태에서 `.usage-account` 가 보이지 않는다 |
| D37 | 만료 usage + 계정 | `.usage-account` 가 `.usage-stale-note` 뒤에 있다 |

DOM 테스트는 동시 부하에 약하다(기존 메모) — 단독 실행으로 판정한다.

### 11.4 `tests/run.sh` — 개정 2건 + 신규 5건

| # | 종류 | 내용 |
|---|------|------|
| T25-104 | 개정 | `30개 파일` → `31개 파일`(역방향: 옛 `30개 파일` 고지 잔존 금지) · 개정 이력 주석에 이 PRP |
| T25-149 | 개정 | `HUB_FILE_COUNT` 고정값 30 → 31 · 이력 주석 |
| T25-264 | 신규(★순수) | `hub_account.py` 존재 + `open\(|Path\(|time\.|os\.` 0건(T25-213 동형) |
| T25-265 | 신규(잎) | `hub_account.py` 에 `^[[:space:]]*(import|from) hub_` 0건(T25-214 동형) |
| T25-266 | 신규(템플릿) | `renderUsagePanel(snapshot.usage, snapshot.rate_limit_resets, snapshot.account)` 정확히 2회 · `renderUsageAccountPair` 본문에 `escapeHtml(value)` 존재 |
| T25-267 | 신규(문서) | `hub/README.md`·`commands/hub.md` 에 `show_account_info` 와 `~/.claude.json` 토큰 · README 설정 표에 `show_account_info` 행 |
| T25-268 | 신규(경로 리터럴) | `hub_collect.py` 에 `Path.home() / ".claude.json"` (T25-217 동형 — 단위 테스트는 상수를 바꿔 끼우므로 오탈자를 못 잡는다) |

### 11.5 `tests/mutations.tsv`

신규 가드마다 1행 이상(기존 열 형식 그대로):
T25-264(`hub_account.py` 에 `# time.sleep 흉내` 주입) · T25-265(`import hub_parse` 주입) ·
T25-266a(30초 틱 호출부에서 `, snapshot.account` 삭제) · T25-266b(`escapeHtml(value)` → `value`) ·
T25-267(README 의 `show_account_info` 토큰 개명) · T25-268(`".claude.json"` → `".claude.jsn"`).
T25-104·149 의 기존 원장 행은 기대 문자열의 수(30→31)만 고친다. 단위 테스트가 물어야 할 변이
(AT13 허용 목록 — `parse_account_info` 가 `fullName` 을 organization_name 에 넣도록 바꿈)는
원장 형식이 T25 그룹 전용이면 단위 테스트 쪽 근거로만 남긴다 — 구현 단계에서 원장의 기존 관례를
확인해 정한다.

### 11.6 수동 확인

M1 실제 계정으로 허브를 열어 펼침 본문 아래 세 줄 확인(화면 캡처는 남기지 않는다) ·
M2 `show_account_info:false` → 다음 수집에서 줄이 사라짐 · M3 다크 테마 · M4 창을 320px 로 줄여 줄바꿈 확인.

---

## 12. 구현 순서 (마일스톤 — 각각 커밋 가능)

1. `hub_account.py` + AT1~AT15 → 검증: `python3 -m unittest tests.hub.test_hub_account`
2. `tests/hub/__init__.py` 중화(AC12) → 검증: 기존 `tests/hub` 전체 통과(행동 불변)
3. `hub_model`·`hub_config`·`hub_collect` 배선 + C1~C9 → 검증: 해당 모듈 테스트
4. `hub.py` status + 테스트
5. 템플릿 + D33~D37 → 검증: DOM 파일 단독 실행
6. 문서(README·commands/hub.md·구 PRP 표기·hub-dashboard.md) + `install.sh` 수 + T25·원장 → 검증: `bash tests/run.sh`(메인 세션이 커밋 직전 1회)

---

## 13. 리스크와 완화

| # | 리스크 | 완화 |
|---|--------|------|
| R1 | 이메일이 화면 공유·로컬 포트로 노출 | 펼침 때만 표시 · `show_account_info:false` · 고지 3곳 |
| R2 | CC 가 `~/.claude.json` 을 쓰는 도중 읽어 파싱 실패 경고가 5초간 깜빡임 | 기본은 경고 유지(정직). 실제로 관측되면 "파싱 실패만 무경고 + `/hub status` 로 진단"으로 낮추는 1줄 변경 — 그때 이 PRP 를 개정한다 |
| R3 | 개인 요금제의 `organizationName` 이 자동 생성 이름(예: "<이메일>'s Organization" 꼴)이라 이메일과 중복돼 보일 수 있다 | 사용자가 조직 이름 표시를 명시적으로 골랐다 — 그대로 둔다. 거슬리면 Pro/Max 에서 조직 줄을 숨기는 1조건 추가가 후속 선택지 |
| R4 | 수집마다 약 88KB 파일 읽기 + 디코드 | ms 단위로 추정(50ms 에스컬레이션 조건 대비 작다). 구현 단계에서 `collect_snapshot` 소요를 전후 1회 재서 PR 에 남긴다. mtime 캐시는 측정 근거가 생기면(YAGNI) |
| R5 | CC 가 `oauthAccount` 키 이름을 바꾸면 줄이 사라진다 | 세 값 전부 무효면 경고(AC9) · 일부면 `/hub status` 유무 필드 |
| R6 | 계정 전환 직후 숫자·계정 불일치 | 한계 명시(AC10) |

---

## 14. 검토했으나 채택하지 않은 대안

1. **`UsageSample`(또는 `RateLimitCapture`)에 계정 필드 추가** — 캡처는 statusLine·API 두 생산자가
   같은 포맷으로 쓰는 파일이고 계정은 어느 생산자도 모른다. 투영 타입에 출처가 다른 값을 섞으면
   "패널 값은 전부 캡처 하나에서 온다"(P1·P3)는 계약이 조용히 깨진다.
2. **계정만 있어도 패널을 띄운다** — 접힘 요약이 비고, 보이지 않는 패널 제목("사용 한도")과 내용이
   어긋난다. 무엇보다 한도 캡처가 없을 때도 이메일이 `hub.html` 에 남는다(AC2 의 원칙 위반).
3. **요약 줄에 요금제 붙이기**(`Team · 세션 43% · 주간 71%`) — 접힘 알약 폭 증가, 접힘의 목적(숫자만) 희석.
4. **`hub_usage.py` 에 파서를 넣어 배포 파일 수 증가를 피하기** — 수 갱신(가드 2개 · 문서 3곳)은
   기계적이지만, 한 모듈이 두 외부 계약을 갖게 되고 허용 목록 불변식을 파일 단위 가드로 지킬 수 없다.

---

## 15. 사용자 승인 결정 (확정)

> **확정 결과.** 승인 항목 1 = **안 B**(맨 아래) · 항목 2 = **기본 켜짐(`show_account_info: true`)** ·
> 항목 3 = **CLI 표시명, 모르는 값은 그 줄만 숨김, Max 5x/20x 구분 없음**. 아래는 승인 당시의 선택지 기록이다.

### 승인 항목 1 — 배치 (결정 AC5) · 목업 참조

| 안 | 내용 |
|----|------|
| **B (권장)** | 펼친 패널 **맨 아래**(갱신 문구 밑, 얇은 구분선). 막대 자리는 지금 그대로 |
| A | 펼친 패널 **맨 위**(제목 바로 밑). 막대가 아래로 한 칸쯤 밀린다 |

두 안 모두 접힌 상태 한 줄 요약은 그대로이고, 이메일은 펼쳤을 때만 보인다.

### 승인 항목 2 — 기본값 켜짐 + 끄는 스위치 (결정 AC7)

이메일·조직 이름이 허브 파일(`hub.html`, 평문)과 화면에 새로 남는다. 기본은 **켜짐**, 끄려면
`config.json` 에 `show_account_info: false`(그러면 계정 파일을 아예 읽지 않는다). 기본값을 꺼짐으로
바꾸면 이 기능은 사용자가 설정을 고쳐야만 보인다.

### 승인 항목 3 — 요금제 표기 (결정 AC3)

`Claude Team`·`Claude Max` 처럼 **터미널과 같은 이름**으로 보이고, 허브가 모르는 새 종류면 그 줄만
숨긴다. Max 의 5x/20x 는 구분하지 않는다(원하면 키 1개를 더 읽어 `Claude Max 20x` 로 보이게 할 수 있다).

### 참고 (승인 불필요, 확인만)

- 사용량 숫자가 아직 없으면(패널이 안 뜨는 상태) 계정 정보도 보이지 않는다(결정 AC2).
- 계정을 바꾼 직후엔 세션을 한 번 돌리기 전까지 숫자가 이전 계정 것일 수 있다 — 고치지 않고 문서에 적는다(결정 AC10).
