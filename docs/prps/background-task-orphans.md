# 서브에이전트가 남긴 백그라운드 작업 — 보고 게이트로 예방한다

- **상태: 승인 (2회차, 2026-10-21)** — 사용자 선택: 사전 실험 먼저(§8.3, 통과), 자동 끄기 없음(Q2 = 돌려보내기만),
  범위는 배포 에이전트 3종(Q1). Q3(포그라운드 복귀)는 하지 않는다.
- 설계 모델: opus(2회차 — 사용자 반려 후 방향 전환, 승격 기준 미해당: 반려 사유가 능력이 아니라 문제 정의)
- 작업 경로: 전체 경로(에이전트 3종 frontmatter 계약 변경 + 허브 파일 1개 신설 + 가드·원장)
- 기준: `origin/develop` `26798f8`, 브랜치 `fix/background-task-orphans`

## 0. 2회차 — 1회차 반려 사유

1회차는 메인이 「뭐가 돌고 있냐」는 질문을 받거나 알림 노트를 받았을 때 **제대로 열거해서 끄는 것**을 주 해결책으로
삼았다(상시 규칙 +1,272B). 사용자는 이를 반려했다: 「제대로 검사하는 게 해결책이 아니고, 백그라운드에 연결이 끊긴 작업이
남아 있지 않게 막는 방법을 검토하라」. 2회차는 목표를 **예방**으로 바꾼다 — 주인(서브에이전트)이 끝나는 순간에 제 작업이
남아 있지 않게 한다. 질문 시 열거·알림 턴 열거는 버리고, 상시 규칙 증가는 **0B** 로 한다.

| 1회차 결정 | 2회차 처리 |
|------------|------------|
| BG1 메인 규칙을 상시 규칙에 (+1,272B) | **폐기** — 예방 수단이 아니다. 상시 증가 0B(BG2-1) |
| BG2 에이전트 3종 「백그라운드 정리」 절 | **유지·개정** — 게이트와 짝을 이루는 짧은 문구로(§6.2) |
| BG3 프로세스 트리 열거 명령 | **폐기**(규칙에서 뺀다) — 실측 근거로만 남긴다(§2.4) |
| BG4 메인의 세 시점 열거 | **폐기** |
| BG5 끄는 법(TaskStop·`lsof -t` 대체) | **유지** — 게이트의 거부 사유 문구로 옮긴다 |
| BG6 에이전트 `tools` 에 `TaskStop` | **유지** — V0 충족(메인 도구 목록에 정확히 그 이름) |
| BG7 SubagentStop 차단 | **재평가** → 주 수단이 아니라 폴백(P3, §4) |
| BG8 UserPromptSubmit 주입 | **폐기**(주제 밖) |
| BG9 `</dev/null` 강제 | **기각 유지** |
| BG10 백그라운드 기능 끄기 | **재평가 → 기각 유지**(P1, 근거를 공식 문서로 갱신) |
| BG11 자동 kill | **재평가** → 권고하지 않음, 사용자 선택지로 남김(P5, §9 Q2) |
| BG12 T31-12 정적 가드(면제행) | **개정** — 토큰을 게이트 배선으로 바꾼다(§6.4) |
| BG13 프로젝트 메모리는 저장소 밖 | 유지 |

## 1. 요구사항 요약

데스크톱 앱에서 서브에이전트가 보고를 마친 뒤에도 그 서브에이전트가 띄운 셸이 몇 시간~하루 넘게 돈다(사건 3건, 모두
서브에이전트가 띄운 셸). 「주인이 끝났는데 셸이 남는 일」을 **주인이 끝나는 순간에 기계적으로 막는다.** 정당한
일시정지(서브에이전트가 자기 백그라운드 완료를 기다리며 턴을 끝내는 것)와 긴 검사 운용은 깨지 않는다.

## 2. 원인 — 구조와 세 겹

### 2.1 구조적 원인 (공식 문서, 캐시 `scratchpad/docs-raw/`)

- **포그라운드 서브에이전트가 띄운 명령은 그 실행이 끝나면 멈춘다. 메인과 백그라운드 서브에이전트가 띄운 명령은 최종 응답
  뒤에도 끝날 때까지 돈다**(tools-reference 「When a background command stops」). 타임아웃으로 백그라운드로 옮겨진 명령도
  같다 — 「a foreground subagent's moved command still stops when that subagent's run ends」.
- **데스크톱 앱은 2.1.302 부터 fork mode 가 기본으로 켜져 메인이 서브에이전트를 기다릴 수 없다** — 서브에이전트는 전부
  백그라운드다(sub-agents 「Which subagents run in the background」·「Turn fork mode off」).
- 데스크톱의 백그라운드 명령에는 **시간 제한이 없다**(2.1.288~). 시간 제한은 `-p`·SDK·클라우드 같은 무인 실행에만 있다.
- 서브에이전트 종료 시 그 셸을 정리하는 설정은 없다. 끄는 수단은 `/tasks`·`TaskStop`·세션 종료뿐이다.

즉 2.1.302 이후 데스크톱에서는 **서브에이전트가 남긴 백그라운드 명령을 거둘 주체가 구조적으로 없다.**

### 2.2 명령이 멈춘 이유 (사건 3)

빈 명령 치환 → 파일 인자 없는 `grep` → 120초 타임아웃에서 호스트가 **죽이지 않고 백그라운드로 옮김**. 멈춘 원인(stdin
파이프 추정)은 미확정이다 — 현행 2.1.304 서브에이전트 포그라운드 셸의 stdin 은 `/dev/null` 이다(1회차 실측). 이
설계는 원인과 무관하게 작동해야 한다(P6 기각 근거).

### 2.3 서브에이전트가 안 끈 이유

- 에이전트 3종 지침에 「보고 전에 내 백그라운드를 정리한다」가 없다. 옮겨진 명령은 「내가 띄운 백그라운드」라는 인식도 없다.
- 끌 도구가 없다 — `tools` 허용 목록에 `TaskStop` 이 없다. 백그라운드 서브에이전트가 유지하는 내장 도구에 `TaskStop` 이
  들어 있지만(sub-agents 「Available tools」), `tools` 를 명시하면 그 목록 밖은 주어지지 않는다(tools-reference — 이 설계
  세션의 도구 목록에도 없다).
- 보고(SubagentHandback)를 막는 것이 아무것도 없다. 보고 뒤 호스트는 이 실행을 「제 백그라운드가 남은 채 멈춤」으로 두고,
  셸이 꺼지면 실패 알림으로 서브에이전트를 **다시 깨운다**(사건 3: 20.8시간 뒤 꺼지자 재개해 엉뚱한 진단을 적었다).

### 2.4 이 설계에서 실측한 것 (2.1.304, 이 세션)

| 확인 | 결과 |
|------|------|
| 서브에이전트 transcript 경로 | `<메인 transcript 경로에서 .jsonl 을 뗀 것>/subagents/agent-<agentId>.jsonl` (이 실행: `…/78af0cc6-…/subagents/agent-a6f5c7aca8439993a.jsonl`) |
| 자동 전환 결과가 그 transcript 에 남는가 | 남는다 — `user` 줄의 `tool_result` 본문: `Command did not complete within its 120s timeout and was moved to the background (ID: b2l1gdl7h). Output is being written to: /private/tmp/claude-501/<프로젝트>/<세션>/tasks/b2l1gdl7h.output. …` |
| `run_in_background` 결과 | `Command running in background with ID: bfrtiwey5. Output is being written to: …/tasks/bfrtiwey5.output. …` — 출력 디렉터리는 **메인 세션 ID** 아래다 |
| SubagentHandback 이 transcript 에 남는가 | 남는다 — `tool_use` `name:"SubagentHandback"`, 입력 키 `message` |
| 작업 ↔ 프로세스 | `lsof -t <출력 파일>` = 그 작업의 셸과 자식 전부(`run_in_background`: zsh 60494(부모 = 세션 claude) + `sleep` 60496) |
| 끄기 | `kill $(lsof -t <출력 파일>)` — 분류기 허용, 잔여 0, 주인에게 `failed`(exit 144) 알림이 감. 음수 PGID `kill` 은 분류기 거부 |
| 이 설계 세션도 같은 사고를 겪었다 | 정규식 grep 이 120초를 넘어 `b2l1gdl7h` 로 옮겨졌다. 손으로 껐고, 이번 회차에 띄운 시험 작업 `bfrtiwey5` 도 껐다(남은 것 0) |

## 3. 예방의 열쇠 — 「끝」을 알리는 단일 지점

서브에이전트의 끝은 두 종류다 — **보고**(SubagentHandback 호출)와 **일시정지**(보고 없이 턴을 끝내고 제 백그라운드 완료를
기다림). 고아는 앞의 것에서만 생긴다. 뒤의 것은 정당한 대기다.

auto 모드에서 로컬 서브에이전트(포크 제외)의 보고는 `SubagentHandback` 호출로만 전달된다(tools-reference — 그 도구가 주어지면 맺음 텍스트는 보고가 아니다). 그래서
**`PreToolUse`(matcher `SubagentHandback`) 훅은 「주인이 끝을 선언하는 순간」 딱 한 번, 보고가 전달되기 전에 실행된다.**
일시정지에는 실행되지 않는다. 훅이 `permissionDecision:"deny"` 를 내면 호출이 막히고 사유가 그 서브에이전트에게 간다
(hooks 「PreToolUse decision control」). 이 지점이 SubagentStop 보다 나은 이유:

- SubagentStop 은 보고와 일시정지 둘 다에 온다. 둘을 가르려면 transcript 에서 보고 호출을 찾아야 하는데, transcript 는
  비동기로 써져 **마지막 호출이 아직 안 실렸을 수 있다**(hooks 「Common input fields」 `transcript_path`).
- SubagentStop 의 차단은 보고가 **이미 전달된 뒤**다 — 메인은 고아가 남은 보고를 받고, 차단으로 이어진 턴이 알림을 한 번 더 만든다.

## 4. 예방 수단 비교 (결정 표)

사건 1·2 는 서브에이전트가 백그라운드로 띄운 **대기 루프**(`until grep -q …; do sleep 10; done` 류), 사건 3 은 **자동
전환된 포그라운드 명령**이다. 1·2 의 서브에이전트가 보고했는지 일시정지했는지는 기록이 없다 — 보고 뒤 메인이 다음 단계로
넘어간 정황으로 보아 「보고 뒤 남음」으로 본다(표의 「1·2」 열은 이 가정에 선다).

| # | 안 | 사건 1·2 | 사건 3 | 정당한 일시정지·긴 검사에 대한 부작용 | 배포 위치 | 검증 | 판정 |
|---|----|---------|--------|---------------------------------------|-----------|------|------|
| P1 | 백그라운드 기능 끄기 `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` | 막음 | 막음(타임아웃에 종료) | **모두 사라진다** — `run_in_background`·자동 전환·Ctrl+B·백그라운드 서브에이전트·「완료 알림으로 재개」가 전부 꺼진다. 메인의 27분 전체 검사는 포그라운드로 돌려야 하고 `BASH_MAX_TIMEOUT_MS`(기본 10분)를 올려야 하며, 그동안 메인이 막힌다 | 사용자 settings `env` 1줄 | 설정 후 아무 명령이나 타임아웃 | **기각** — 모든 프로젝트의 작업 방식을 바꾸는 값이 예방 효과보다 크다 |
| P2 | 포그라운드 서브에이전트 `CLAUDE_CODE_FORK_SUBAGENT=0` + 메인이 「기다리며」 부름 | 막음 | 막음 | 서브에이전트가 도는 동안 **메인이 막힌다**(데스크톱 「Run in background」로 떼면 보장이 사라진다). 서브에이전트의 「일시정지 → 완료 알림 재개」가 불가능해진다 — 턴을 끝내면 제 명령이 같이 죽는다. 긴 검사는 포그라운드 + 큰 timeout 으로 바꿔야 한다. 포크가 꺼진다 | settings `env` 1줄 + 상시 규칙 1줄(기다리며 부르기) | 설정 후 서브에이전트에 `run_in_background` 를 띄우고 보고 → 셸 소멸 확인 | **대안**(§9 Q3) — 구조적으로 가장 확실하지만 데스크톱이 2.1.302 에 택한 동작을 되돌린다. 기다릴지는 디스패치마다 메인 판단이다(fork 를 꺼도 기본은 백그라운드) |
| P3 | SubagentStop 차단 + TaskStop 지시 | 막음(보고 뒤) | 막음(보고 뒤) | 일시정지와 보고를 transcript 로 가려야 한다 — 비동기 기록 때문에 보고 직후 판정이 「일시정지」로 빗나갈 수 있다(그때는 허용 = 고아). 보고가 이미 전달된 뒤 막는다 | 에이전트 frontmatter(`Stop`→SubagentStop) 또는 settings | 같음 | **폴백** — P4 의 V 항목이 실패할 때만(§8) |
| P4 | **보고 게이트**: `PreToolUse`(`SubagentHandback`)에서 이 실행이 띄운 작업이 살아 있고 보고에 선언되지 않았으면 **거부** + 끄는 법 안내 | 막음 | 막음 | 없음 — 일시정지에는 발화하지 않는다. 결과를 기다릴 서브에이전트는 보고하지 않고 턴을 끝내면 된다. 남겨야 할 것은 보고에 ID 를 적으면 통과한다(탈출구) | **에이전트 3종 frontmatter `hooks`** + 스크립트 `hub/bin/hub_handback_guard.py`(§5 결정 BG-L) | 단위 테스트 + 설치 후 수락 시험(§8) | **채택(권고)** |
| P5 | 보고 뒤(또는 직전) 자기 셸 **자동 kill** | 막음 | 막음 | 남기려던 것도 죽는다(탈출구로 완화 가능). 바깥에서 죽이면 주인이 실패 알림에 **다시 깨어난다**(사건 3·2.4 실측) — 보고 뒤 kill 은 쓸데없는 턴과 메인 알림을 한 번 더 만든다. 훅이 프로세스를 죽이므로, transcript 문구를 위조한 경로가 남의 프로세스를 가리키면 그것을 죽인다 | P4 와 같음 | 같음 | **권고하지 않음**(§9 Q2) — P4 는 끄는 일을 호스트의 `TaskStop` 에 맡겨 등록소와 알림이 어긋나지 않는다 |
| P6 | 자동 전환 자체를 막기 | 해당 없음 | 막음(종료) | 개별 차단 설정이 없다 — `CLAUDE_AUTO_BACKGROUND_TASKS` 는 켜기 전용, `BASH_*_TIMEOUT_MS` 는 시점만 바꾼다. 남는 수단은 P1(전부 끄기)이나, 훅의 `updatedInput` 으로 명령 앞에 `sleep` 을 붙여 「sleep 으로 시작하는 명령은 옮기지 않는다」 예외를 노리는 우회뿐이다 | — | — | **기각** — 우회는 호스트 예외 규칙의 의도 밖 사용이고 모든 Bash 호출을 다시 쓴다. 옮겨진 명령은 P4 가 보고 시점에 잡는다 |
| P7 | 프롬프트 규칙만(에이전트 3종 정리 절 + `TaskStop`) | 줄임 | 줄임 | 없음 | 에이전트 3종 | 정적 가드 | **P4 와 함께 채택** — 게이트의 거부 왕복을 줄이고, 게이트가 안 도는 환경(auto 모드 아님·허브 미설치)을 받친다 |

**권고안 = P4 + P7.** 상시 규칙 0B, 사용자 화면 변화 없음, 일시정지·긴 검사 운용 그대로.

## 5. 설계 결정

| # | 결정 | 근거 | 기각안 |
|---|------|------|--------|
| BG-G1 | **게이트 판정 = 「이 서브에이전트 transcript 의 호스트 결과 문구에서 찾은 작업」 ∩ 「지금 그 출력 파일을 쥔 프로세스가 있는 작업」 − 「보고 본문에 ID 가 적힌 작업」** 이 비어 있지 않으면 거부 | 소유: 훅 입력의 `background_tasks` 에는 소유자가 없지만(hooks — 그리고 PreToolUse 에는 이 배열 자체가 없다), 서브에이전트 transcript 에는 **제가 띄운 것만** 결과 문구로 남는다(2.4). 생존: `lsof` 가 출력 파일 ↔ 프로세스를 정확히 잇는다(2.4). 선언: 일부러 남기는 것의 탈출구이자, 메인이 그 작업을 넘겨받는다는 기록이다 | SubagentStop 의 `background_tasks[].id` 교집합(P3) — 보고 시점에는 그 배열을 받을 수 없다 |
| BG-G2 | **소유 문구는 두 호스트 문장만 인정한다**: `…was moved to the background (ID: X). Output is being written to: P` · `Command running in background with ID: X. Output is being written to: P`. 그리고 P 는 허브의 기존 형태 검증(`hub_activity._valid_output_path` 의 5조건 — 절대경로·조각 검사·`tasks/` 부모·조부모 = 이 세션 ID·`ID: <줄기>` 짝)을 통과해야 한다. **(검수 1회차 개정) 문장은 tool_result 본문 맨 앞에서 시작할 때만 인정한다** — `Command running in background with ID:` 로 시작하거나 `Command did not complete within its <N>s timeout and was moved to the background (ID:` 로 시작하는 본문 | 서브에이전트가 다른 기록을 `Read`·`cat`·`grep` 해 그 안의 문구가 tool_result 에 실리면 남의 작업을 「내 것」으로 오인한다. 같은 세션의 기록이면 세션 경로까지 원문 그대로라 문장·경로 검증만으로는 못 거른다 — 본문 맨 앞 고정이 그 인용을 거른다(§10). 게이트는 아무것도 죽이지 않지만, 오인하면 사유가 남의 작업을 끄라고 안내하므로 오인 자체를 막아야 한다 | 표지 「Output is being written to」만 보기 — 허브 표시용으로는 충분하지만 게이트에는 느슨하다 |
| BG-G3 | **fail-open**: 입력 이상·`agent_id` 없음·transcript 없음·`lsof` 없음/시간 초과·파싱 오류는 전부 **허용**(출력 없음, 종료 0) | 게이트의 오작동이 보고를 영영 막는 것이 고아보다 나쁘다. `rules/python/hooks.md` 「Hook … Entry Points Always Exit 0」. 명령줄도 `2>/dev/null \|\| true` 로 감싼다 — 스크립트 파일이 없으면 `python3` 가 종료 코드 **2** 를 내는데, PreToolUse 에서 2 는 **차단**이다(hooks) | — |
| BG-G4 | **게이트는 프로세스를 죽이지 않는다.** 거부 사유가 「`TaskStop`(ID) → 다시 보고 / 기다려야 하면 보고하지 말고 턴 종료 / 남길 거면 보고에 ID·이유」를 안내한다. `TaskStop` 이 없을 때의 대체 `kill $(lsof -t <출력 파일>)` 도 사유에 적는다 | P5 기각 근거. `TaskStop` 은 호스트가 등록소를 직접 정리한다 | P5 |
| BG-L | **배포 위치 = 에이전트 3종 frontmatter `hooks`(PreToolUse, matcher `SubagentHandback`) + 스크립트는 `hub/bin/`** | frontmatter 훅은 「그 서브에이전트가 도는 동안만」 등록되고(hooks 「Hooks in skills and agents」), `~/.claude/agents/` 정의는 신뢰 단계가 없다(sub-agents). `install.sh` 가 이미 배포하는 파일 안에 들어가므로 **settings.json·설치 동의·허브 설치기를 건드리지 않는다.** 스크립트는 stdlib 파이썬이 배포되는 유일한 채널(`hub/bin`)에 두고, 허브의 기존 순수 파서(`hub_activity`)를 재사용한다. 허브 설치기는 이 훅을 **등록하지 않는다** — 허브의 「읽기 전용」 성격은 그대로다 | (a) settings.json 전역 등록(허브 설치기에 별도 스위치) — 비배포 에이전트(general-purpose 등)까지 덮지만 `hub_settings` 병합·제거·설치 동의 문구·`/hub` 하위 명령이 늘고, 허브가 세션 동작에 개입하는 훅을 등록하게 된다(§9 Q1). (b) `install.sh` 에 4번째 자산 종류(`hooks/`) 신설 — 배포 채널·대장·파일 수 상수·제거 처리가 함께 바뀌고 `--scope project` 경로가 갈린다. (c) frontmatter 에 인라인 셸 — 시험할 수 없다 |
| BG-L2 | 허브가 설치돼 있지 않으면 게이트는 **조용히 없다**(BG-G3). 그 환경은 P7 규칙만 받친다 | 배포 자산(에이전트)이 허브 파일을 부르는 교차 의존을 fail-open 으로 무해하게 만든다. 루트 README 에 한 줄로 밝힌다 | 허브 미설치 시 경고 — 보고마다 소음 |
| BG-M | **`hub_activity` 에 공개 함수 하나를 더한다**: `host_background_launches(window: bytes, session_id: str) -> tuple[BackgroundLaunch, ...]` — BG-G2 의 두 문장만, 개수 상한 없음, 중복 제거. 기존 `background_output_paths`(표시용, 8개 상한)는 바꾸지 않는다 | 형태 검증 로직을 복제하지 않는다(DRY). `hub_activity` 는 이미 ★순수(T25-10 목록)이고 같은 문구를 다룬다. 사적 헬퍼를 다른 모듈이 import 하지 않는다 | 게이트 전용 순수 모듈 신설 — 파일 2개(순수 + 진입점)가 되고 HUB_FILE_COUNT·고지가 2씩 는다. 남는 순수 로직(선언 제외·거부 JSON)은 10줄 남짓이라 진입점 모듈 안의 함수로 충분하다 |
| BG-T | 에이전트 3종 `tools` 에 `TaskStop`(1회차 BG6) | 2.3. 메인 도구 목록에 정확히 `TaskStop` 이 있음을 메인이 확인했다(V0 충족) | — |
| BG-R | 상시 규칙 **0B**. 메인용 규칙을 두지 않는다 | 예방은 게이트가 한다. 일부러 남긴 작업은 보고 본문에 ID·이유로 오므로 메인은 보고를 읽고 처리한다. 질문 시 열거는 사용자가 해결책이 아니라고 했다 | 1회차 BG1 |

## 6. 변경 내용 (정확한 텍스트·명세)

### 6.1 에이전트 3종 frontmatter

`effort:` 줄 다음에 아래 블록을 넣고, `tools` 끝에 `, TaskStop` 을 붙인다.

```text
hooks:
  PreToolUse:
    - matcher: "SubagentHandback"
      hooks:
        - type: command
          command: 'python3 "$HOME/.claude/hub/bin/hub_handback_guard.py" 2>/dev/null || true'
          timeout: 10
```

- `implementer`: `tools: Read, Grep, Glob, Bash, Edit, Write, Agent, Skill, TaskStop`
- `code-reviewer`: `tools: Read, Grep, Glob, Bash, Agent, Skill, TaskStop`
- `design-architect`: `tools: Read, Grep, Glob, Bash, Write, Agent, Skill, TaskStop`

`timeout: 10` — 정상 실행은 transcript 읽기(수 MB) + `lsof` 1회로 1초 안팎이다. 10초를 넘기면 호스트가 훅을 끊고 허용한다.

### 6.2 에이전트 3종 본문 — 「준수 사항」 앞(code-reviewer 는 「검수 체크리스트」 앞)

```text
## 백그라운드 정리

최종 보고 전에 내가 띄운 백그라운드 명령을 `TaskStop` 으로 끈다 — `run_in_background` 로 띄운 것과,
타임아웃에 "was moved to the background (ID: …)" 로 넘어간 포그라운드 명령 둘 다다. 결과를 기다려야
하면 보고하지 말고 턴을 끝내 완료 알림을 기다린다. 기다리기용 루프(`until …; do sleep …; done`)를
백그라운드로 띄우지 않는다 — 기다릴 명령 자체를 백그라운드로 띄운다. 일부러 남겨 메인에 넘길 것은
보고에 그 ID 와 이유를 적는다. 살아 있는 내 작업이 남아 있으면 보고 게이트 훅이 보고를 거부한다.
```

대기 루프 금지는 사건 1·2 의 모양 자체를 줄인다 — 기다릴 명령을 바로 백그라운드로 띄우면 그 명령이 끝날 때 알림이 오고,
조건이 영영 안 맞는 루프가 생기지 않는다.

### 6.3 `hub/bin/hub_handback_guard.py` (신설, stdlib 전용)

모듈 머리 docstring: 「서브에이전트 보고 게이트(PreToolUse·SubagentHandback). **허브가 등록하지 않는다** — 배포 에이전트의
frontmatter hooks 가 부른다. 이 실행이 띄운 백그라운드 작업이 살아 있고 보고에 선언되지 않았으면 보고를 거부한다.
프로세스를 끄지 않는다. 무엇이든 실패하면 허용한다.」 + 이 PRP 경로.

```python
GUARDED_EVENT_NAME = "PreToolUse"
GUARDED_TOOL_NAME = "SubagentHandback"
LSOF_TIMEOUT_SECONDS = 3            # 훅 timeout(10) 안에서 transcript 읽기와 나눠 쓴다
SUBAGENT_TRANSCRIPT_MAX_BYTES = 16 * 1024 * 1024   # 초과분은 끝에서부터 이만큼만 읽는다

@dataclass(frozen=True)
class GuardInput:                   # 훅 stdin 에서 검증해 뽑은 값
    session_id: str
    agent_id: str
    transcript_path: str
    report_message: str

def main() -> int: ...              # 항상 0. try: _run() / except Exception: pass
def parse_guard_input(raw: str) -> GuardInput | None: ...           # 순수 — 이벤트·도구 이름·필수 키 검사
def subagent_transcript_path(transcript_path: str, agent_id: str) -> Path: ...  # 순수 — 2.4 의 경로 규칙
def parse_lsof_open_names(lsof_output: str) -> frozenset[str]: ...  # 순수 — `lsof -Fn` 의 n 줄
def undeclared_live_launches(launches: Sequence[BackgroundLaunch], open_paths: frozenset[str],
                             report_message: str) -> tuple[BackgroundLaunch, ...]: ...  # 순수
def deny_decision(launches: Sequence[BackgroundLaunch]) -> dict: ...  # 순수 — hookSpecificOutput JSON
def _open_output_paths(paths: Sequence[str]) -> frozenset[str]: ...   # I/O — subprocess.run(["lsof", "-Fn", "--", *paths], timeout=…)
def _run() -> None: ...             # I/O — stdin → 판정 → 거부일 때만 stdout 에 JSON 한 줄
```

- 「선언」 판정: 보고 본문에 `(?<![\w-])<ID>(?![\w-])` 가 있으면 제외.
- 거부 JSON: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <사유>}}`.
- 사유 문안(상수):
  `보고 전에 정리할 것: 이 실행이 띄운 백그라운드 작업 {ID 목록}이 아직 돈다(출력 파일 {경로 목록}). 결과가 필요 없으면 TaskStop 으로 끈 뒤 다시 보고한다(TaskStop 이 없으면 Bash 로 kill $(lsof -t <출력 파일>)). 결과를 기다려야 하면 보고하지 말고 턴을 끝내 완료 알림을 기다린다. 일부러 남겨 메인에 넘길 것이면 보고 본문에 그 ID 와 이유를 적고 다시 보고한다.`
- `lsof` 경로 비교는 `os.path.realpath` 로 맞춘다(`/tmp` ↔ `/private/tmp`).

### 6.4 `hub/bin/hub_activity.py` — 공개 함수 1개 + 데이터 클래스 1개

```python
@dataclass(frozen=True)
class BackgroundLaunch:
    task_id: str
    output_path: str

def host_background_launches(window: bytes, session_id: str) -> tuple[BackgroundLaunch, ...]:
    """tool_result 본문 맨 앞에서 시작하는 호스트의 두 백그라운드 시작 문장(BG-G2, 검수 1회차 개정)만 찾아 형태 검증을 통과한 것을 낸다 — 상한 없음, 중복 제거, 예외 없음."""
```

기존 `_marker_lines_backwards`·`_tool_result_bodies`·`_valid_output_path` 를 재사용한다. 기존 공개 함수는 바꾸지 않는다.

### 6.5 `tests/run.sh` T31-12 (개정) — 보고 게이트 배선

T31-11 다음에 둔다. T31-10·T31-11 의 줄은 건드리지 않는다. 세 에이전트 각각에 대해:

- 본문에 `moved to the background` 가 있다.
- frontmatter(첫 `---` 쌍 사이, T31-10 의 awk 추출 방식)에 `TaskStop` 이 `tools:` 의 한 토큰으로 있고,
  `matcher: "SubagentHandback"` · `hub_handback_guard.py` · `|| true` 가 있다.
- 교차 파일: `hub/bin/hub_handback_guard.py` 가 실재한다(개명하면 가드가 눈이 머는 것을 막는다 — 프로젝트 메모리 「개명하면 정적 가드가 눈이 먼다」).
- 실패 메시지는 모두 `"T31-12: …"` 로 시작한다. 예: `T31-12: agents/<이름>.md frontmatter 에 보고 게이트 배선 토큰 '<토큰>' 이 없음(서브에이전트가 제 백그라운드 작업을 남긴 채 보고할 수 있다)`.
- 그룹 머리 주석에 한계: 문구·배선의 존재만 본다. 훅이 실제로 발화하는지·호스트 계약이 유지되는지는 보지 못한다(§8 수락 시험의 몫).
- `test_desc` 범위 「T31-1~T31-12」.

### 6.6 원장·상수·문서

- `tests/mutations.tsv` T31-11 행 아래 면제행:
  `T31-12	tests/run.sh	-	-	-	보고 게이트 배선이 조용히 사라진다 — 세 작업 에이전트의 frontmatter hooks(PreToolUse·SubagentHandback·hub_handback_guard.py·fail-open 꼬리)·tools 의 TaskStop·본문 정리 문구가 삭제되거나 스크립트 파일이 개명된다	정적 grep 가드 — 변조 검증은 구현 시 수동 1회(docs/prps/background-task-orphans.md §8)로 대신한다. K6 시간 예산 보호(사용자 결정 2026-10-08)	-`
- `SOURCE_GUARD_ID_FLOOR` 571 → 572 + 이력 주석, 원장 헤더 인용 `(572 — …→571→572)`.
- `hub/install.sh` `HUB_FILE_COUNT` 37 → 38. 이 상수의 이력 주석(T25-1 근처)과 `hub/README.md` 의 파일 수 고지(37 → 38)·모듈 목록에 `hub_handback_guard.py` 한 줄. 그 밖의 문서 수 인용은 구현 중 T25 실패 메시지가 가리키는 곳을 따른다.
- `hub/README.md` 프라이버시 고지에 한 항목: 「보고 게이트(`hub_handback_guard.py`)는 허브가 등록하지 않는다 — 배포 에이전트 3종이 보고하는 순간에만 돈다. 그 서브에이전트의 기록에서 호스트의 백그라운드 시작 문장(작업 ID·출력 파일 경로)만 찾고, `lsof` 로 그 출력 파일을 쥔 프로세스가 있는지만 본다. 아무것도 저장하지 않고 아무 프로세스도 끄지 않는다.」 — 기존 고지(도구 결과의 출력 파일 경로를 찾는다)와 같은 범위다.
- 루트 `README.md`: 에이전트 설명 근처에 한 줄 — 「배포 에이전트 3종은 허브가 설치돼 있으면 보고 직전에 제 백그라운드 작업이 남았는지 검사한다(보고 게이트).」 그리고 `docs/prps/` 문서 수 92 → 93.
- `rules/workflow/*`·`CLAUDE.md`: 변경 없음 — **상시 바이트 0**, `ALWAYS_ON_CONTEXT_BUDGET_BYTES` 그대로.

### 6.7 바이트

| 대상 | 증가 | T26 |
|------|------|-----|
| 상시 컨텍스트 | **0B** | — |
| 에이전트 1개당 | **+911B**(§6.8) | 아니오 — 그 서브에이전트 컨텍스트에만 |
| `hub/bin` | 새 파일 1개(약 130줄 예상), `hub_activity.py` +25줄 예상 | 아니오 |

### 6.8 에이전트 블록 실측

이 문서의 §6.1·§6.2 블록을 그대로 떼어 `wc -c` 로 쟀다: §6.1 frontmatter 블록 **209B**(frontmatter 안이라 빈 줄 없음),
§6.2 본문 블록 **691B** + 뒤 빈 줄 1B, `, TaskStop` 10B — 에이전트 1개당 **+911B**. implementer 8,029 → 8,940,
code-reviewer 20,313 → 21,224, design-architect 6,505 → 7,416. 구현자는 편집 뒤 실측으로 확인한다.

## 7. 영향 파일

| 파일 | 변경 |
|------|------|
| `agents/implementer.md`·`agents/code-reviewer.md`·`agents/design-architect.md` | §6.1·§6.2 |
| `hub/bin/hub_handback_guard.py` | 신설 §6.3 |
| `hub/bin/hub_activity.py` | §6.4 |
| `tests/hub/test_hub_handback_guard.py` | 신설 §8 |
| `tests/hub/test_hub_activity.py` | `host_background_launches` 케이스 추가 |
| `tests/run.sh` | T31-12, `SOURCE_GUARD_ID_FLOOR` |
| `tests/mutations.tsv` | 면제행, 헤더 인용 |
| `hub/install.sh` | `HUB_FILE_COUNT` 37 → 38 |
| `hub/README.md` | 파일 수·모듈 목록·프라이버시 고지 |
| `README.md` | 한 줄 + 문서 수 92 → 93 |

바꾸지 않는 것: `rules/**`·`CLAUDE.md`(상시 0B), `install.sh`(rules 46·agents 4·commands 8 그대로), `hub/bin/hub_settings.py`·
`hub_hook.py`(허브는 이 훅을 등록하지 않는다), `agents/explore.md`(Bash 없음), `NOTICE.md`, `VERSION`.

## 8. 검증

### 8.1 구현 단계 (설치 전)

1. **단위 테스트 먼저(RED)** — `tests/hub/test_hub_handback_guard.py`(stdlib unittest, `SwallowedExceptionGuardMixin` 적용 —
   「출력 없음」 단언이 삼킨 예외로 공허하게 통과하지 않게):
   - `parse_guard_input`: PreToolUse·SubagentHandback·필수 키 → 값 / 다른 이벤트·다른 도구·`agent_id` 없음·JSON 아님 → None.
   - `subagent_transcript_path`: 2.4 의 실제 경로 모양.
   - `host_background_launches`(hub_activity): 2.4 의 두 문장 원문으로 만든 transcript 줄 → 둘 다 / 같은 문장이지만 다른 세션
     경로 → 제외 / 표지만 있고 `ID:` 짝 없음 → 제외 / 문서를 읽어 실린 예시 문장(ID 없는 꼴) → 제외 / 중복 → 1개 / 9개 이상 → 전부.
   - `parse_lsof_open_names`: `p…`/`f…`/`n…` 줄 섞인 출력 → n 값 집합.
   - `undeclared_live_launches`: 죽은 것 제외 / 보고에 ID 가 있으면 제외 / ID 가 다른 낱말의 일부면 제외하지 않음.
   - `deny_decision`: 키 구조, 사유에 모든 ID·경로·`TaskStop` 포함.
   - `main()`: stdin 이 위 무효 입력·transcript 없음·`lsof` 가 `FileNotFoundError`/`TimeoutExpired` → stdout 비고 0 반환 /
     살아 있는 미선언 작업(`subprocess.run` 모킹) → 거부 JSON 한 줄, 0 반환.
2. `python3 -m unittest discover -s tests/hub -t .`, `python3 -m py_compile hub/bin/*.py`(뒤에 `__pycache__` 정리 — 프로젝트 메모리).
3. `bash tests/run.sh --only T25,T31,T37`(T25 파일 수·고지, T31-12, T37 K5·ID 하한·헤더 인용). 전체는 메인이 커밋 직전 1회.
4. **T31-12 수동 변조 1회**(면제행 전제, 저장소 밖 사본): implementer 사본 frontmatter 에서 `|| true` 삭제 / code-reviewer 사본
   에서 `, TaskStop` 삭제 / `hub_handback_guard.py` 를 다른 이름으로 바꾼 사본 — 각각 T31-12 가 실패해야 한다.
5. **스크립트 실입력 시험(설치 없이, 이 세션의 실제 기록으로)**: 이 설계 실행의 transcript(`…/subagents/agent-a6f5c7aca8439993a.jsonl`)
   를 가리키는 가짜 PreToolUse 입력을 stdin 으로 주고 — (a) 작업이 다 꺼진 지금은 출력 없음, (b) 구현자가 `run_in_background`
   로 `sleep 600` 을 하나 띄우고 그 결과 문장을 담은 임시 transcript 사본을 만든 뒤 → 거부 JSON, (c) 그 작업을 끈 뒤 → 출력 없음.
   끝나면 띄운 작업 0개.

### 8.2 설치 후 수락 시험 (메인, 사용자 `/harness-update` 와 허브 갱신 뒤) — 호스트 계약 V 항목

이 단계에서는 사용자 설정·`~/.claude/agents` 를 바꿀 수 없어 실측하지 못했다. 배포된 에이전트로 한 번 돌린다:
「implementer 에게: `run_in_background` 로 `sleep 600` 을 띄우고, 끄지 말고 바로 SubagentHandback 으로 보고하라」.

| V | 확인 | 실패하면 |
|---|------|----------|
| V1 | 서브에이전트 안의 PreToolUse 입력에 `agent_id`·`session_id`·`transcript_path`·`tool_input.message` 가 있다(hooks 「Common input fields」는 있다고 적는다) | P3 폴백 — frontmatter `Stop`(→SubagentStop) 훅으로 바꾼다. 입력에 `agent_transcript_path`·`background_tasks[].id` 가 있으므로 소유 = transcript ID ∩ 등록소 ID, 보고 여부 = transcript 의 마지막 `tool_use` 가 SubagentHandback. 차단은 `decision:"block"` |
| V2 | `agent_id` 로 만든 경로(§6.3)가 실제 transcript 파일이다 | V1 과 같은 폴백(SubagentStop 은 경로를 직접 준다) |
| V3 | 보고 시점에 앞선 시작 문장이 transcript 에 이미 실려 있다(비동기 기록) | 시작과 보고 사이에 도구 호출이 최소 1회 있는 경우만 보장으로 문서화 — 바로 다음 호출에서 보고하는 경우는 허용(fail-open)으로 남는다 |
| V4 | 거부가 보고를 실제로 막고 사유가 서브에이전트에게 간다 → 서브에이전트가 `TaskStop` 후 다시 보고 → 통과 | P3 폴백 |
| V5 | `~/.claude/agents/` 정의의 frontmatter 훅이 데스크톱 백그라운드 서브에이전트에서 발화한다 | 등록 위치를 settings.json 으로 옮긴다(§5 BG-L 기각안 a) — 이때는 §9 Q1 을 다시 묻는다 |
| V6 | 보고 뒤 그 서브에이전트가 다시 깨어나지 않고, 메인 알림이 한 번뿐이다 | 사유 문구에서 「TaskStop 뒤 보고」 순서를 더 강하게. 동작 자체는 고아 방지와 무관 |

수락 시험 뒤 열거로 남은 셸 0 을 확인한다(1회차 2.4 의 명령 — 시험 도구로만 쓴다).

### 8.3 사전 실험 결과 (2026-10-21, 2.1.304, 구현 전)

실행 중인 세션은 새 에이전트 파일을 읽지 못해서(같은 세션에서 3회 `not found`) 새 데스크톱 세션에서 돌렸다. 임시
`~/.claude/agents/bg-probe.md`(tools `Bash, TaskStop`, frontmatter PreToolUse matcher `SubagentHandback|Bash` → 입력 기록 +
SubagentHandback 첫 호출만 거부)로 「`run_in_background` 로 `sleep 600` → 끄지 않고 바로 보고」를 시켰다. 실험 뒤 에이전트
파일·워크트리는 지웠다. 기록 원본: 메인 scratchpad `probe/probe_payloads.jsonl`(3줄)·`probe/session_report.md`.

| V | 결과 | 근거 |
|---|------|------|
| V1 | **통과** — 입력 키: `agent_id`·`agent_type`·`cwd`·`effort`·`hook_event_name`·`permission_mode`·`prompt_id`·`scratchpad_dir`·`session_id`·`tool_input`·`tool_name`·`tool_use_id`·`transcript_path`. SubagentHandback 의 `tool_input` 키는 `message` 하나 | 기록 3줄 |
| V2 | **통과** — `transcript_path` 는 **메인** 세션 기록이다. §6.3 규칙(`.jsonl` 뗀 경로 + `/subagents/agent-<agent_id>.jsonl`)으로 만든 경로가 실재했다 | `derived_exists: true` |
| V3 | **통과(가장 빡빡한 경우)** — 시작 직후 바로 다음 호출이 보고였는데도 그 시점 서브에이전트 기록에 시작 문장이 이미 있었다(n=1). 메인 기록에는 없다 | `derived_has_launch: true`, `given_has_launch: false` |
| V4 | **통과** — 거부로 보고가 막혔고, 서브에이전트가 받은 사유는 `PreToolUse:SubagentHandback hook error: <사유>` 꼴(호스트가 「hook error」 머리를 붙인다). 서브에이전트가 `TaskStop` → 다시 보고 → 통과 | 메인이 받은 보고는 2번째 1건뿐 |
| V5 | **통과** — `~/.claude/agents/` 정의의 frontmatter 훅이 데스크톱 백그라운드 서브에이전트 안에서 발화했다(Bash·SubagentHandback 둘 다) | 기록 3줄 |
| V6 | **통과** — 알림 1회, note 는 「no live background children of its own」(깨끗한 종료). 실험 세션의 열거 결과 남은 셸 0 | session_report.md |
| BG-T | **통과** — `tools` 에 `TaskStop` 을 적으면 서브에이전트가 쓸 수 있다. 응답 `Successfully stopped task: bq98j3nxt (sleep 600)` | 프로브 보고 |

구현 메모: 입력에 `scratchpad_dir` 가 있다(이 실험에서 처음 확인 — 출력 파일의 `tasks/` 는 그 형제 디렉터리). 게이트 판정에는
쓰지 않아도 되지만, 형태 검증의 세션 ID 대조에는 `session_id` 를 쓴다. 폴백 P3 는 필요 없어졌다.

## 9. 사용자에게 물을 것

- **Q1 — 게이트를 어디에 걸까** (권고: 배포 에이전트 3종의 frontmatter, BG-L). 다른 안은 settings.json 전역 등록이다. 그러면
  general-purpose 등 모든 서브에이전트에 걸리지만, 허브 설치기가 세션 동작에 개입하는 훅을 하나 더 관리하게 되고 `/hub` 에
  켜고 끄는 스위치·설치 동의 문구가 는다. 권고는 3종부터 시작해, 비배포 에이전트의 고아가 관측되면 전역으로 넓히는 것이다.
- **Q2 — 게이트가 직접 끄게 할까(자동 kill, P5)** (권고: 아니오 — 거부하고 안내만 한다). 직접 끄면 서브에이전트 협조가 필요 없지만,
  남기려던 것도 죽고, 바깥에서 죽인 작업은 주인을 다시 깨워 쓸데없는 턴과 알림을 만든다(실측). 거부 방식에서도 보고하려면
  끄거나 선언하는 수밖에 없어 고아는 남지 않는다.
- **Q3 — 서브에이전트를 포그라운드로 되돌리는 설정(P2)도 함께 할까** (권고: 아니오). `CLAUDE_CODE_FORK_SUBAGENT=0` 한 줄이면
  서브에이전트가 끝날 때 그 명령이 구조적으로 같이 끝나지만, 서브에이전트가 도는 동안 메인이 막히고 「완료 알림으로 재개」
  운용이 사라진다. 모든 프로젝트에 적용되는 사용자 설정이라 이 저장소가 배포하지 않는다.

## 10. 리스크

| 리스크 | 완화 |
|--------|------|
| 게이트가 안 도는 환경 — auto 모드가 아니어서 SubagentHandback 이 없음, 포크, 허브 미설치, 비배포 에이전트 | P7 규칙이 받친다. 범위는 §9 Q1 에서 사용자가 정한다 |
| 호스트가 결과 문장 문구를 바꾸면 소유를 못 찾아 조용히 허용한다 | §8.2 수락 시험이 문구를 실측 고정한다. 단위 테스트 픽스처는 2.4 의 실제 문장이다. 문구가 바뀌면 허브의 기존 표시(`hub_activity`)도 같이 깨지므로 같은 회차에 드러난다 |
| 일시정지 중인 서브에이전트의 무한 대기 루프(보고하지 않음)는 게이트 밖이다 | §6.2 의 대기 루프 금지. 그래도 남으면 그 서브에이전트는 「끝나지 않은」 상태로 보여(보고가 없다) 메인이 알아챌 수 있다 |
| 남의 작업을 「내 것」으로 오인한 거부 | BG-G2 의 문장 단위·세션 경로 검증 + **본문 맨 앞 고정**(검수 1회차 HIGH 로 추가 — 같은 세션의 다른 기록을 Read·grep·diff 하면 남의 시작 문장이 세션 ID 까지 원문 그대로 실려 문장·경로 검증만으로는 못 거른다. 이 경우 사유가 남의 작업을 끄라고 안내하므로 무해하지 않다. 실측: 호스트가 쓴 문장은 tool_result 본문 위치 0 또는 「Command did not complete within its Ns timeout and 」 바로 뒤에서만 나오고, 인용은 86~9938 위치였다). 남는 구멍: `grep -o` 처럼 남의 문장만 뽑아 본문 맨 앞에 오게 한 출력 — 드물고, 보고에 ID 를 적으면 통과한다 |
| 다른 주체(메인·형제의 `tail -f`)가 이미 끝난 내 작업의 출력 파일을 쥐고 있어 거짓 거부 | 사유에 「TaskStop 이 이미 끝났다고 하면 보고에 ID 를 적어 다시 보고」를 넣는다(검수 1회차 LOW) |
| 반복 거부로 서브에이전트가 맴돈다 | 사유가 세 출구(끄기·기다리기·선언)를 모두 준다. 선언은 항상 통과한다 |
| 에이전트 정의가 허브 파일을 부르는 교차 의존 | BG-L2 fail-open. T31-12 가 파일 이름 일치를 잠근다 |

검토했으나 채택하지 않은 대안: P1(기능 끄기), P2(포그라운드 복귀 — Q3), P3(SubagentStop 차단 — 폴백으로만), P5(자동 kill — Q2),
P6(자동 전환 우회), settings 전역 등록(Q1), `install.sh` 자산 종류 신설.

## 11. 구현 순서

1. `hub_activity.host_background_launches` 테스트(RED) → 구현(GREEN).
2. `test_hub_handback_guard.py`(RED) → `hub_handback_guard.py`(GREEN).
3. T31-12(RED) → 에이전트 3종 §6.1·§6.2 (GREEN).
4. 원장 면제행·`SOURCE_GUARD_ID_FLOOR`·헤더 인용 / `HUB_FILE_COUNT`·허브 README / 루트 README.
5. §8.1-2·3·4·5. 띄운 백그라운드 0개 확인.
6. (메인) 커밋 직전 전체 검증 → 사용자 설치 뒤 §8.2 수락 시험.
