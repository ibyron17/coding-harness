---
description: "모든 프로젝트의 세션 진행 상황을 한 페이지에서 읽기 전용으로 보는 통합 허브 — 상주 서버 제어/훅 설치"
argument-hint: "[install|off|status|server start|server stop|server restart|server status|statusline on|statusline off|dashboard on|dashboard off]"
---

# Hub

> 로컬에서 돌고 있는 **모든 Claude Code 프로젝트**의 진행 상황(프로젝트/세션/단계)을 한 페이지에서
> **읽기 전용**으로 본다. 명령·제어 기능은 범위 밖이다. 이 커맨드는 **얇다** — 아래 python3
> 서브커맨드를 부르고 결과를 보고하는 것 말고는 판단하지 않는다. 설명·설정·프라이버시 고지
> 전부는 [`hub/README.md`](../../hub/README.md), 설계 근거는
> [`docs/prps/hub-dashboard.md`](../../docs/prps/hub-dashboard.md)에 있다.

**진행 기록(허브 기록기)과 반대 방향이다.** 진행 기록은 LLM 만 아는 사실(설계 승인, 검수 결과 등)을
오케스트레이터가 직접 쓴다. `/hub` 는 파일에서 기계적으로 읽히는 사실만 집계하므로 코드가 하고,
이 문서는 그 코드를 부르는 절차만 담는다.

---

## 사전 조건 — 허브는 coding-harness 설치와 분리돼 있다

`~/.claude/hub/bin/hub.py` 가 없으면 아래 절차로 안내하고 **아무것도 만들지 않고 중단**한다.

1. `~/.claude/.coding-harness.json` 이 있으면 `repo_path` 필드를 읽는다(`/harness-update` Phase 1 과
   같은 방법). 없으면 경로 없이 일반 문구로 안내한다.
2. 다음을 그대로 보고한다(경로가 있으면 `{repo_path}` 를 채운다):

   > 허브 실행 코드가 설치돼 있지 않습니다. 허브는 coding-harness 설치와 **분리**돼 있어 별도로
   > 설치해야 합니다:
   >
   >     {repo_path}/hub/install.sh
   >
   > 무엇이 설치되고 무엇이 기록되는지: `{repo_path}/hub/README.md`

## 호출 규약

```
/hub                      # 서버가 살아 있으면 그 URL 을 연다. 아니면 1회 수집 후 file:// 를 연다
/hub install              # 전역 훅 7개 설치 (옵트인, 멱등)
/hub off                  # 전역 훅 제거 (우리 마커가 붙은 엔트리만)
/hub status               # 훅 · 이벤트 · 수집 실패 · 서버 요약 보고
/hub server start         # 상주 서버 기동 (분리 프로세스, 세션 무관 수명). 멱등
/hub server stop          # 상주 서버 종료 (신원 확인 → SIGTERM → 필요 시 SIGKILL)
/hub server restart       # 상주 서버 강제 재기동 (종료 → 재기동) 후 대시보드 탭을 포커스한다. 멱등이 아니다
/hub server status        # 프로세스 · 하트비트 · HTTP 응답 · 비정상 종료 흔적 보고
/hub statusline on        # 터미널 상태줄에 사용량 등록 (옵트인, 다른 statusLine 있으면 거부)
/hub statusline off       # 우리 statusLine 만 제거
```

**`/hub` 는 어떤 경로에서도 서버를 기동하지 않는다.** 서버 기동은 언제나 사용자가
`/hub server start`·`/hub server restart` 로 명시적으로 한다 — 자동으로 뜨지 않는다는 것이
이 개정의 핵심이다.

## `/hub` (인자 없음)

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" open --json
```

결과 JSON 의 `server_alive`·`url`·`browser_opened`·`browser_focus_requested`·`note`(있으면)를
한 문단으로 보고한다.

- `server_alive=true` — "상주 서버가 화면을 열 때마다 갱신합니다."
- `server_alive=false` — `note` 를 그대로 보고한다(이번 한 번만 수집했고, `/hub server start`
  로 켜면 항상 최신 상태가 유지된다는 안내가 들어 있다).
- `browser_opened=false` — 위에 더해 "브라우저를 자동으로 열지 못했습니다. URL 을 직접 열어 주세요."
- `browser_focus_requested=false`(이면서 `browser_opened=true`) — 탭은 열렸지만 창이 앞으로
  오지 않았을 수 있다는 뜻이다(비-macOS 폴백 경로). `browser_fallback_reason`(있으면)을 곁들인다.

## `/hub server start` — 상주 서버 기동

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" server-start --json
```

`already_running=true` 면 "이미 실행 중입니다"만 보고한다(멱등, 재기동하지 않는다).
새로 뜬 경우 `pid`·`url` 을 보고하고 다음을 덧붙인다: "Claude 세션이 끝나도 계속 실행되며,
끄려면 `/hub server stop` 을 실행하십시오." `ok=false` 면 `reason`(포트 점유 또는
`log_tail`)을 그대로 보고한다.

## `/hub server stop` — 상주 서버 종료

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" server-stop --json
```

`ok:true` 면 `was_running` 여부와 (있으면) `reason`을 보고한다. `reason` 이 있는 경우는
대부분 PID 재사용(재부팅 후 낡은 상태 파일 등)이며, **그 프로세스는 건드리지 않고 상태
파일만 정리**했다는 뜻이다 — 실패로 취급하지 않는다.

`ok:false` 면 세 가지다. `reason` 만 있으면 `ps` 실행 자체가 실패해 확인할 수 없었다는
뜻이다. `reason` 과 함께 `pid`·`recorded_hub_py_path` 가 오면 응답 형태는 같지만 원인은
둘로 갈리므로 `reason` 문구로 구분해서 보고한다:

- **"확인하지 못했는데 하트비트는 살아 있습니다"** — 그 PID 를 우리 서버로 확인하지
  못했는데 하트비트는 살아 있다는 뜻이다(신원 불일치 + 하트비트 신선). 오판일 수 있어
  상태 파일은 그대로 두고 아무것도 하지 않았다는 뜻이며, `ps -p <pid> -o args=` 로 직접
  확인하거나 새 코드로 재기동한 뒤 다시 시도해야 한다.
- **"완화 기준과 일치했지만 하트비트가 없어"** — 느슨한 기준(구버전 레코드이거나 디렉토리
  성분 없이 기동된 서버)으로는 신원이 맞았지만, 살아 있다는 독립 증거(하트비트)가 없어
  확증이 부족하다는 뜻이다(완화 일치 + 하트비트 없음). 이 경우도 상태 파일은 건드리지
  않았다 — 잠시 뒤 다시 시도하거나(하트비트가 계속 없으면 다음 시도에서 PID 재사용으로
  판정돼 정리된다) `ps -p <pid> -o args=` 로 직접 확인한다.

## `/hub server restart` — 상주 서버 강제 재기동 + 대시보드 포커스

기존 서버를 확실히 내린 뒤 새 코드로 다시 띄운다(멱등이 아니다 — 살아 있어도 항상
재기동한다). 두 호출을 순서대로 실행하고, **첫 호출이 `ok:false` 면 두 번째 호출을
하지 않는다**:

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" server-restart --json
```

`ok:true` 면 이어서 다음을 실행하고 두 JSON 을 함께 보고한다:

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" open --json
```

`ok:false` 면 `open` 을 실행하지 않고 `phase`(`"stop"`|`"start"`)와 `reason` 을 그대로
보고한다. `ok:true` 면 `stopped_previous`(원래 켜져 있었는가)·`pid`·`note`(있으면, 강제
종료·PID 재사용 등의 이례)와, `open` 결과의 `browser_focus_requested`·`browser_opened` 를
함께 보고한다.

`server-restart` 호출이 `invalid choice: 'server-restart'` 로 **exit 2** 를 내면 설치본이
낡았다는 뜻이다 — `hub/install.sh --force` 재실행을 안내한다.

## `/hub server status`

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" server-status --json
```

`alive`(핵심 한 줄) 를 먼저 보고한다. `crashed_evidence=true` 면 **"비정상 종료된 흔적이
있습니다"**, `maintenance_stalled=true` 면 **"프로세스는 살아 있지만 유지보수 티커가
멈췄습니다"** 와 `log_tail`(있으면)을 함께 보고한다. `collect_health` 는 값별로 다르게
보고한다 — `failing` 이면 실패 사유와 `log_tail` 을 함께, `never_collected` 면 "아직 한
번도 수집하지 않았습니다(정상일 수 있습니다)"를 보고하고, `ok` 면 별도 언급 없이 넘어간다.
그 외 필드(`record`·`process_present`·`heartbeat_age_ms`·`http_ok`·`orphaned_evidence`·
`last_collect_success_age_ms`)는 참고용으로 표에 곁들인다.

## `/hub install` — 훅 + 상태줄 설치 (옵트인)

**1단계 — 훅.**

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" install-hooks --json
```

**2단계 — 상태줄.** 1단계의 `ok` 와 무관하게 이어서 실행한다(둘은 독립된 옵트인이다).

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" install-statusline --json
```

**두 명령 실행 전 아래 고지를 한 번에 보여주고 진행 여부를 확인한다**(최초 1회. 두 결과의
`already_installed` 가 모두 참이면 다음부터 생략):

> **① 전역 훅 7개** — `SessionStart`·`UserPromptSubmit`·`Stop`·`SubagentStart`·`SubagentStop`·
> `SessionEnd`·`StopFailure` 에 훅을 추가합니다. 훅 자신은 프롬프트를 기록하지 않습니다 —
> 세션의 마지막 프롬프트와 서브에이전트 실행 제목이 Claude Code 가 이미 남긴 기록(transcript·
> `subagents/*.meta.json`)에서 읽혀 `~/.claude/hub/hub.html` 평문 파일에 인라인되고 허브 화면
> (127.0.0.1 로컬 서버가 그 파일을 제공)에 표시되며, `~/.claude/hub/config.json` 의
> `record_prompt_excerpt:false` 로 끌 수 있습니다. 알려진 시크릿 패턴(API 키·토큰·개인키 등)은
> 인라인 전에 `[REDACTED]` 로 마스킹됩니다. 워크플로우(다중 서브에이전트 오케스트레이션
> 스크립트)를 쓰는 세션은 서브에이전트에게 준 지시·결과의 앞 400자와 각 에이전트의
> **label·소속 단계 이름**도 같은 방식으로 인라인되며, 같은 `record_prompt_excerpt` 플래그로
> 끌 수 있습니다. `StopFailure` 입력(사용량 한도 등으로 턴이 끊겼을 때 오는 훅)의 오류
> 설명·마지막 응답 문구는 기록하지 않고 오류 종류 하나만 남깁니다. `Stop`·`SubagentStop`
> 입력의 진행 중 백그라운드 작업·예약 목록은 종류별 개수만 남기고 작업 설명·명령줄·예약
> 프롬프트는 기록하지 않습니다. 도는 서브에이전트의 대화 기록 끝과 백그라운드 작업 출력 파일의
> 수정 시각·크기를 읽어 진행 상황(도구 종류·시각·개수)만 표시합니다 — 명령·출력 내용은
> 기록하거나 표시하지 않습니다.
> **② 터미널 상태줄** — `~/.claude/settings.json` 의 `statusLine` 에 우리 커맨드를 등록합니다.
> **모든 프로젝트의 터미널 상태줄**에 `세션 23% · 주간 41%` 가 상시 표시되고, 그 값이
> `~/.claude/hub/rate_limits.json` 에 캡처돼 **허브의 사용량 패널을 채웁니다.** 이미 다른
> `statusLine` 이 설정돼 있으면 **덮어쓰지 않고 거부**합니다. 사용량 패널을 펼치면 로그인
> 계정의 요금제·조직 이름·이메일도 보이며(`~/.claude.json` 에서 세 값만 읽음) `hub.html`
> 평문에 인라인됩니다 — `config.json` 의 `show_account_info:false` 로 끌 수 있습니다.
> 같은 입력에서 세션별 추정 비용·API 시간·컨텍스트 사용률 숫자 3개도 `~/.claude/hub/session_costs/`
> 에 캡처돼 세션 줄의 칩이 됩니다(내용은 없고 숫자뿐 — 구독 요금과 무관한 정가 기준 추정입니다).
> 상태줄을 끈 뒤에도 이미 쓴 캡처 파일은 보관 기간(기본 7일)까지 남습니다.
> 기존에 설치된 다른 도구의 훅(CAM·Litmus 등)은 건드리지 않습니다.
> 상태줄만 원하지 않으면 나중에 `/hub statusline off` 로 즉시 되돌릴 수 있습니다.

사용자가 **"훅만"** 이라고 답하면 2단계를 건너뛴다. 임의로 건너뛰거나 강행하지 않는다.

**보고** — 두 결과를 한 덩어리로 보고한다.

| 상황 | 보고 |
|------|------|
| 둘 다 성공 | 훅 `installed`/`already_installed` + 상태줄 `installed`/`already_installed`. 이어서 `/hub server start` 를 안내 |
| 훅 성공 · 상태줄 `ok:false` | **`/hub install` 을 실패로 보고하지 않는다.** 훅 결과를 먼저 보고하고, 상태줄은 `reason` 을 그대로 옮긴다. 남의 `statusLine` 충돌(`current_command` 동봉)이면 "기존 설정을 보존했습니다 — 사용량 패널이 필요하면 `/hub statusline on` 을 직접 실행하거나, 터미널을 건드리지 않는 대안으로 `config.json` 의 `usage_api_enabled:true`(macOS 전용, 옵트인)를 쓸 수 있습니다" 한 줄을 덧붙인다 |
| 훅 `ok:false` | 훅의 `reason` 을 그대로 보고하고 **재시도하지 않는다**(`settings.json` 파싱 실패는 사용자의 권한 설정을 보호하기 위한 의도적 중단이다). 2단계 결과도 함께 보고한다 |

두 명령 모두 **멱등**이다 — 이미 설치돼 있으면 `settings.json` 을 쓰지 않는다.

## `/hub off` — 훅 제거

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" uninstall-hooks --json
```

`removed` 목록을 보고한다. 서버가 켜져 있으면 계속 돈다 — 이 명령은 훅만 건드린다.

## `/hub statusline on` — 한도 초기화 예정 시각 캡처 등록 (단독 재실행, 옵트인)

`/hub install` 2단계와 같은 명령이다 — 그때 "훅만"을 선택했거나 상태줄 등록만 실패했던
경우 이 명령으로 단독으로 다시 시도한다.

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" install-statusline --json
```

**실행 전 반드시 아래 고지를 사용자에게 보여주고 진행 여부를 확인한다** (최초 1회, 이미
설치돼 있으면 건너뜀 — `already_installed` 로 판단):

> 이 명령은 `~/.claude/settings.json` 의 `statusLine` 에 우리 커맨드를 등록합니다 — **모든
> 프로젝트의 터미널 상태줄**에 영향을 줍니다. 등록 후에는 상태줄에 `세션 23% · 주간 41%` 가
> 상시 표시되고, 한도 초기화 예정 시각과 사용률이 `~/.claude/hub/rate_limits.json` 에
> 캡처돼 사용량 패널에 보입니다. 이미 다른 `statusLine` 이 설정돼 있으면 **덮어쓰지 않고
> 거부**합니다. 패널을 펼치면 로그인 계정의 요금제·조직 이름·이메일도 보이며(`~/.claude.json`
> 에서 세 값만 읽음) `hub.html` 평문에 인라인됩니다 — `show_account_info:false` 로 끌 수 있습니다.
> 같은 입력에서 세션별 추정 비용·API 시간·컨텍스트 사용률 숫자 3개도 `~/.claude/hub/session_costs/`
> 에 캡처돼 세션 줄의 칩이 됩니다(내용은 없고 숫자뿐 — 구독 요금과 무관한 정가 기준 추정입니다).
> 상태줄을 끈 뒤에도 이미 쓴 캡처 파일은 보관 기간(기본 7일)까지 남습니다.

결과의 `installed`·`already_installed` 를 보고한다. `ok=false` 면 `reason` 을 그대로 보고하고
**재시도하지 않는다** — 다른 `statusLine` 과의 충돌(`current_command` 동봉)이거나
`hub_statusline.py` 가 배포되지 않은 상태(`hub/install.sh` 재실행 필요)다.

등록한 적이 없거나 세션을 한 번도 안 돌렸으면 사용량 패널 자체가 존재하지 않는다. 한
번이라도 등록·캡처된 뒤에는 세션을 한동안 안 돌려 캡처가 낡아도 패널이 사라지지 않고
**조회되지 않음**으로 표시된다(`hub/README.md` 「사용량 패널」 참조).

## `/hub statusline off` — 캡처 중단

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" uninstall-statusline --json
```

`removed` 여부를 보고한다. 우리 것이 아닌 `statusLine` 은 건드리지 않는다 — 그 경우
`removed:false` 로 보고하고 no-op 임을 알린다.

## `/hub dashboard on|off` — 이 프로젝트의 진행 기록 켜기·끄기

```bash
python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" switch on|off
```

`.claude/settings.local.json` 의 `dashboard_enabled` 필드만 원자적으로 쓴다.

**기존 필드는 어떤 경우에도 건드리지 않는다** — 파일을 통째로 덮어쓰면 사용자의 권한 허용 목록이 사라진다.

파싱에 실패하면 `INVALID-SETTINGS` 를 내고 쓰지 않는다.

이 절차는 기록 파일을 만들지도 지우지도 않는다 — 다음 `init` 부터 기록 여부가 바뀔 뿐이다.

## `/hub status`

```bash
python3 -- "$HOME/.claude/hub/bin/hub.py" status --json
```

`last_collect_failure` 가 `null` 이 아니거나 `event_read_warnings` 가 비어 있지 않으면
**그 내용을 표보다 먼저 한 줄로 보고한다.** 허브가 조용히 멈춰 있는 상태를 사용자가 표의
숫자에서 유추하게 두지 않는다. `hooks_installed` 에 `false` 가 하나라도 있으면(예: 기존
설치에 `StopFailure` 가 아직 없는 경우) 그것도 표 앞에 한 줄로 `/hub install` 재실행을
안내한다(결정 RI12, docs/prps/hub-rate-limit-interruption.md). 이어서
`hooks_installed`(이벤트별 설치 여부) ·
`events_today_and_yesterday`(오늘+어제 이벤트 수) · `server_alive`·`server_crashed_evidence`·
`server_maintenance_stalled`·`server_collect_health`·`last_collect_success_age_ms`(서버 요약) ·
`last_collected_at_ms` 를 표로 보고한다.

`usage_panel_enabled`(사용량 패널 스위치)·`usage_sample_age_ms`(캡처에서 퍼센트를 실을 수
있을 때만 채워지는 나이, ms)도 같은 표에 곁들인다. 퍼센트의 출처는 `/hub statusline on`
이 등록하는 statusLine 캡처, 또는 `usage_api_enabled:true` 로 켜는 사용량 API 폴링 —
둘 중 하나가 채우는 같은 캡처 파일(`rate_limits.json`)이다. 둘 다 등록·활성화하지 않았거나
세션을 한 번도 안 돌렸으면 `usage_panel_enabled:true` 인데도 `usage_sample_age_ms` 는
항상 `null` 이다. `usage_panel_enabled:false` 면 `config.json` 에서 껐다는 뜻이고, `true`
인데 `usage_sample_age_ms` 가 `null` 이면 캡처가 없거나(두 생산자 모두 미등록·세션 미실행)
계약이 안 맞거나 퍼센트가 없는(구형 캡처 등) 것이며, 숫자인데 5시간(18,000,000ms)을 넘거나
세션(5시간) 창이 이미 리셋됐으면 만료돼 패널이 표시되지 않는 것이다 — 패널이 안 보이는
여러 이유를 이 필드와 아래 `rate_limit_capture_age_ms`·`usage_api_last_failure` 로 구분한다.

`account_info_enabled`(`show_usage_panel` 과 `show_account_info` 가 둘 다 켜졌는가) ·
`account_info_fields`(`{"plan": bool, "organization": bool, "email": bool}` — `~/.claude.json`
에서 각 값이 **읽혔는지 유무만**. 스위치가 꺼졌거나 파일이 없거나 읽기에 실패했으면 `null`)도
같은 표에 곁들인다. **값(이메일·조직 이름)은 이 출력에 없고 보고에도 옮기지 않는다** — 이
출력은 세션 기록에 남기 때문이다. 계정 줄이 안 보이는 이유(①사용량 패널 자체가 없음 ②
`show_account_info:false` ③`~/.claude.json` 에 `oauthAccount` 없음)를 이 두 필드와
`usage_panel_enabled` 로 구분한다. `plan:false` 인데 `organization`·`email` 이 `true` 이면
허브가 모르는 새 요금제 종류다(그 줄만 숨는다).

`statusline_installed`(우리 statusLine 설치 여부) · `rate_limit_capture_age_ms`(한도
초기화 시각 캡처를 처음 관측한 뒤 지난 시간, ms) · `rate_limit_resets_remaining_ms`
(`{"session": ms|null, "weekly": ms|null}` — 아직 지나지 않은 리셋까지 남은 시간)도 같은
표에 곁들인다. 초기화 예정 시각 줄이 안 보이는 이유(①statusLine 미설치 ②세션 미실행
③리셋 시각이 이미 지남 ④`show_usage_panel:false`)를 이 세 필드로 구분한다.

`usage_api_enabled`(`config.json` 의 사용량 API 스위치) · `usage_api_last_attempt_age_ms`
(마지막 폴링 시도로부터 지난 시간, ms — 시도한 적이 없으면 `null`) ·
`usage_api_last_failure`(`{at_ms, reason, message, response_keys?}` 또는 성공 시 `null` —
`message` 는 `reason` 고정 어휘를 사람이 읽는 문장으로 바꾼 것이다)도 같은
표에 곁들인다. `usage_api_enabled:false` 면 옵트인 기능이 꺼져 있다는 뜻이고(기본값),
`true` 인데 `usage_api_last_failure` 가 있으면 그 `reason` 으로 원인을 구분한다 —
`credential_unavailable`/`credential_unparsable` 은 macOS Keychain 접근 문제,
`http_unauthorized` 는 재로그인 필요, `http_rate_limited` 는 일시적 과다 요청,
`network_error` 는 연결 실패, `redirect_blocked` 는 사용량 API 가 리다이렉트를 요청했고
우리가 따라가지 않은 경우(응답 자체는 정상이었다), `tls_verify_failed` 는 서버 인증서
검증에 실패한 경우(`network_error` 와 분리한 이유 — 와이파이 문제로 오인되기 쉽다),
`response_too_large` 는 응답 본문이 상한을 넘어 거부한 경우, `schema_mismatch` 는 응답
형식이 바뀐 경우다(이때만 `response_keys` 에 응답의 키 구조가 함께 실린다 — **값은 절대
포함되지 않는다**). 이 경로는 스위치 off·statusLine 미등록·세션 미실행·계약 불일치·만료와
함께 "패널이 안 뜨는 이유"의 사각지대를 마저 없앤다.

`update_check_enabled`(`config.json` 의 새 릴리스 확인 스위치, 기본 `true`) ·
`release_check`(`{last_attempt_at_ms, last_success_at_ms, latest_version, last_failure_reason}`
또는 한 번도 확인하지 않았으면 `null`)도 같은 표에 곁들인다. 서버가 6시간마다 coding-harness 저장소
폴더에서 `git ls-remote --tags` 로 새 릴리스 태그를 확인한 마지막 결과다. 화면에 「새 버전」 알림이
안 뜨는 이유를 이 두 필드로 구분한다 — `update_check_enabled:false`(껐다) · `release_check:null`
(서버가 꺼져 있었거나 아직 첫 확인 전) · `last_failure_reason` 이 있으면 그 사유(`no_install_record`
설치 기록 없음 · `repo_missing` 저장소 폴더 없음 · `git_unavailable` git 없음 · `timeout` 15초 초과 ·
`remote_error` 원격 접속 실패(인증·네트워크·SSH 키 포함) · `output_too_large` 출력이 너무 큼 · `parse_error` 태그 목록 해석 실패) — 실패해도 직전에 알아낸
`latest_version` 은 남는다. 실패는 화면에 경고로 뜨지 않고 여기서만 보인다.

`notify_enabled`(`config.json` 의 macOS 알림 스위치, 기본 `false`) · `notify_active`(지금 도는 서버가 알림기를
켜고 시작했는가) · `notify_status`(`{active_since_ms, last_attempt_at_ms, last_success_at_ms, last_failure_reason,
last_failure_exit_code}` 또는 기록이 없으면 `null`)도 같은 표에 곁들인다. 세션이 작업중에서 승인 대기·한도
초과로 바뀔 때 서버가 `osascript` 로 띄우는 알림의 상태다(알림 문구는 기록에 없다). 질문·허락 요청·작업 완료는 데스크톱 앱 알림이 맡는다. 알림이 안 오는 이유를 이 세 필드로 구분한다 —
`notify_enabled:false`(껐다, 기본) · `notify_enabled:true` 인데 `notify_active:false`(켰지만 서버를 아직 재기동하지 않았거나 macOS 가
아니거나 `osascript` 가 없다 — `/hub server restart` 후에도 같으면 `server.log` 를 본다) · `last_failure_reason` 이 있으면 그 사유(`osascript_missing`
실행 파일 없음 · `timeout` 10초 초과 · `exit_nonzero` 비정상 종료, 종료 코드는 `last_failure_exit_code` · `invalid_text` 문구에 보낼 수 없는 문자가 섞임). **macOS 알림 설정에서 「스크립트 편집기」
알림이 꺼져 있거나 집중 모드이면 알림이 안 뜨는데도 정상(성공)으로 기록된다** — 그때는 터미널에서
`osascript -e 'display notification "test"'` 로 배너가 뜨는지 확인하도록 안내한다.

---

## 구현 노트 (사람이 읽는 참고용 — 이 절은 실행하지 않는다)

- **훅은 반드시 `type: "command"` 다.** `type: "http"` 는 v2.1.108 에서 발동하지 않음이 실측됐다
  (CAM 2026-08-03) — 이 사실을 모르고 되돌리는 회귀를 막기 위해 여기 적어 둔다.
- 훅 커맨드 문자열은 항상 아래와 **글자 하나까지 동일**해야 한다(7개 이벤트 공통):

  ```
  python3 "$HOME/.claude/hub/bin/hub_hook.py" >/dev/null 2>&1 || true   # DZH_HUB_HOOK
  ```

  `|| true` 는 `Stop` 훅의 종료 코드가 세션을 막지 않게 하고, `>/dev/null` 은
  `UserPromptSubmit` 훅의 stdout 이 세션 컨텍스트로 섞여 들어가는 것을 막는다. 둘 다 생략 금지.
  `# DZH_HUB_HOOK` 마커는 설치·제거의 유일한 판정 키다.
- `Notification` 훅은 설치하지 않는다 — Desktop·Cursor 의 GUI 승인 카드는 이 이벤트를 발화하지
  않는다(CAM 실측 2026-08-04).
- `StopFailure` 는 `Stop` 대신 오는 훅이다 — API 오류(사용량 한도 등)로 턴이 끝나면 호스트는
  `Stop` 을 발화하지 않고 이 훅을 대신 보낸다(호스트 실측, 데스크톱 번들 2.1.280). 서브에이전트
  문맥에서도 발화한다(코드 판독 — `agent_id` 동반, docs/prps/hub-rate-limit-interruption.md
  §1.2). 입력 필드는 `error`(오류 종류)·`error_details`·`last_assistant_message` 등이며, 허브는
  `error` 만 `normalize_error_kind` 로 정규화해 남긴다(결정 RI7).
- `Stop`·`SubagentStop` 은 `bt`(종류별 개수)·`sw`(1회성 예약 수)를 함께 남긴다 —
  `hub_session_facts.normalize_background_task_type` 경유(결정 BW2).
- statusLine 커맨드 문자열은 항상 아래와 **글자 하나까지 동일**해야 한다:

  ```
  python3 "$HOME/.claude/hub/bin/hub_statusline.py" 2>/dev/null || true   # DZH_HUB_STATUSLINE
  ```

  훅 커맨드와 달리 **`>/dev/null`(stdout 리다이렉트)을 절대 넣지 않는다** — statusLine 에서는
  stdout 이 실제 출력 채널이라, 이를 막으면 상태줄이 통째로 사라진다. `2>/dev/null || true`
  만 쓴다. `# DZH_HUB_STATUSLINE` 마커는 설치·제거의 유일한 판정 키다.
- 서버 포트는 **8794 고정**이다(북마크 가능해야 하므로 후보 순회를 하지 않는다).
- 티어 1(`.claude/dashboards/*.jsonl`)은 `hub_parse.py` 가 읽는 JSONL 이벤트 계약을 **읽기만**
  한다. 그 계약(첫 이벤트가 `init` 이어야 한다)이 깨지면 허브 파서가 조용히 티어 2로
  강등한다 — `hub_parse.py` 를 고칠 때 이 의존을 기억할 것. 화면은 허브 서버가 요청마다
  그 이벤트를 `hub_dashboard_render.py` 로 렌더한 결과다.
