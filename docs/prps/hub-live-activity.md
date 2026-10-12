# 허브 — 실행 중 활동 표시 (PRP)

| 항목 | 값 |
|------|-----|
| 대상 | `hub/bin/hub_activity.py`(신설, ★순수) · `hub_subagent_read.py` · `hub_session.py` · `hub_project.py` · `hub_collect.py` · `hub_transcript.py` · `hub_template.html` |
| 기준 커밋 | `bcf3705` (main) |
| 워크플로우 경로 | **전체 경로** — 공개 데이터 계약(`SubagentRunView`·`BackgroundWait`) 변경 + 새 모듈 + 프라이버시 고지 변경 |
| 규모 | Medium-Large — 신설 3(소스 1·테스트 2) / 수정 소스 6·테스트 6·문서 5. 파이썬 약 +420, 템플릿 약 +110(M4 실측 +193/−7), 테스트 약 +1,000, `tests/run.sh` 약 +170(M5 실측 +182/−23) |
| 새 외부 의존성 | 없음(python3 표준 라이브러리·바닐라 JS) |
| 설계 모델 | opus |
| 프리뷰 목업 | 세션 스크래치패드 `mock/hub-live-activity-mock.html`(+ `.png`) — §8.4 |
| 승인 상태 | **승인**(2026-10-07) — 쟁점 1~5 권고안대로, 표시 문구는 「새 기록 없음」(P9) |

결정 코드 접두는 **LA**(Live Activity) — 저장소에 `LA<숫자>` 는 아직 없다(설계 시점 grep). 새 검사 번호·상수
값은 전부 **잠정**이다 — 다른 세션이 같은 저장소에서 동시에 일하고 있을 수 있으므로 구현자는 **병합 직전 main
에서 다시 센다**(§10.5).

---

## 0. 요구사항 요약

서브에이전트가 1시간 넘게 돌거나, 세션이 긴 검사를 백그라운드로 걸어 두고 「백그라운드 대기」로 멈춰 있는 동안
허브는 "작업중"·"백그라운드 대기"라는 **상태**만 보여 줄 뿐 그 안에서 무언가가 진행되는지 알려 주지 않는다. 사용자는
멈춘 것인지 조용히 도는 것인지 알 수 없어 답답하다. 이 설계는 허브 수집기가 **호스트가 이미 남기는 기록**(서브에이전트
`agent-<id>.jsonl` 꼬리, 백그라운드 작업 출력 파일의 stat)을 수집 시점에 읽어, ① 도는 서브에이전트의 실행 줄 아래에
**지금 무엇을 하는지(도구 종류)·언제 마지막으로 기록했는지·결과를 기다리는 도구가 몇 분째인지**를 한 줄로, ② 「백그라운드
대기」 세션의 첫 줄에 **백그라운드 작업 출력이 마지막으로 늘어난 시각**을 보인다. 서브에이전트 기록이 10분(잠정) 넘게 비고
기다리는 도구도 없으면 그 실행 줄에만 「▲ N분째 새 기록 없음」을 띄운다 — 허브는 멈춤을 **단정하지 않는다**. 훅·에이전트
파일·토큰 비용은 바뀌지 않고, 출력·명령·설명 텍스트는 화면과 `hub.html` 어디에도 들어가지 않는다(「구조만」). 시간을
줄이는 기능이 아니라 **불확실성을 없애고 멈춤을 일찍 알아채게 하는** 기능이다. 호스트 기록 형식이 바뀌어 읽지 못하면
활동 필드는 비고 화면은 오늘과 같다(fail-open).

### 사용자 스토리

> 서브에이전트에게 긴 작업을 맡겨 두고 다른 일을 하는 사용자로서, 허브 카드만 보고도 "지금 명령을 돌리는 중이고 4분째다",
> "방금도 파일을 읽었다", "12분째 아무 기록이 없다"를 알고 싶다 — 그래야 기다릴지 들여다볼지 정할 수 있다.

---

## 1. 확정 전제 (재논의하지 않는다)

| # | 전제 | 출처 |
|---|------|------|
| P1 | 설계 착수 | 사용자 결정 1 |
| P2 | 개인정보 = **「구조만」** — 출력·명령·설명 텍스트는 어떤 형태로도 스냅샷·화면에 넣지 않는다. 마스킹한 마지막 줄 같은 선택 기능도 만들지 않는다. 도구 활동은 **도구 이름으로만** 종류를 나눈다(Bash 명령 문자열로 세분하지 않는다) | 사용자 결정 2 |
| P3 | 범위 = **서브에이전트 실행 줄의 활동 표시 + 「백그라운드 대기」 배지의 활동 표시** 둘 다 | 사용자 결정 3 |
| P4 | 훅·에이전트 파일·토큰 비용 변경 없음. 수집기가 수집 시점에 호스트 기록을 읽는다(안 A: 서브에이전트 꼬리, 안 B: 출력 파일 stat) | 지시 §3 |
| P5 | 「새 기록 없음」 표지 = (서브에이전트 기록이 임계 이상 비었고) ∧ (진행 중 호출 없음) ∧ (일시정지·백그라운드 대기 아님). 임계는 명명 상수 하나, 잠정 10분, 실측 튜닝은 구현 단계 | 지시 §4 |
| P6 | 수집은 TF9(bounded tail reads, `collect_snapshot` 50 ms 에스컬레이션)를 따른다. 화면은 60초 폴링·30초 틱 | 지시 §4 |
| P7 | 읽기 실패·형식 불일치 → 활동 필드 없음 → 오늘과 같은 화면(fail-open) | 지시 §4 |
| P8 | 일시정지 = `SubagentStop` 먼저, 재개 때 같은 `agent_id` 로 `SubagentStart` 다시(TF7·BW7(b)) — 이 판정과 충돌시키지 않는다 | 지시 §4 |
| P9 | 표시 문구는 **사실만** 적는다 — `▲ N분째 새 기록 없음`. 「멈춘 것 같음」은 허브가 모르는 원인(긴 생각·재시도 대기일 수도 있다)을 추측하는 표현이라 기각. 해석은 툴팁에 둔다 | 사용자 결정(설계 승인 때) |

재사용하는 이미 확인된 수치(다시 재지 않는다): 출력 파일은 작업이 끝나면 지워진다(12일 163개 중 4개 잔존) · 서브에이전트
실행 286건 중 49건이 백그라운드 작업을 걸었다 · 서브에이전트 턴 시간 중앙 3.6초(<100K)/9.1초(>300K), 생각 긴 턴 2% ·
sleep 대기 중앙 13초 · 10분 넘는 기록 공백 48회 전부 정상 공백(다른 에이전트 라운드 대기) · 수집 1회당 미종료 실행 실측
최대 4건(SL §2.6) · 가장 바쁜 날 transcript 증가 약 1.4MB/시간(TF9 상수 주석).

---

## 2. 설계 단계에서 확인한 사실 (구조 필드만 — 내용·명령은 출력하지 않았다)

방법: 세션 스크래치패드의 `python3 -B` 읽기 전용 스크립트(`shape_probe.py`·`shape_probe2.py`·`tail_cost.py`, 저장소에 남기지
않는다)가 **키 이름·타입·불리언·개수만** 출력했다. 요청대로 실제 기록 파일의 필드 이름만 열었다 — 처음에는 2+2개
(서브에이전트·메인), 형태 확인은 최근 7일 파일 중 문구가 든 서브에이전트 49개·메인 12개에서 불리언만 셌다.

| ID | 사실 | 이 설계에 주는 것 |
|----|------|------------------|
| E1 | 서브에이전트 기록 줄 최상위 키: `type`·`timestamp`·`message`·`isSidechain`·`agentId`·`sessionId`… — **`toolUseResult` 키가 없다.** 블록은 `tool_use{caller,id,input,name,type}`·`tool_result{content,tool_use_id,type[,is_error]}`·`thinking`·`text`. `tool_result.content` 는 문자열(대부분) 또는 `text` 블록 리스트 | 안 A 는 `type`·`timestamp`·`message.content[]` 의 `type`·`id`·`name`·`tool_use_id` 만으로 된다. 서브에이전트 쪽 출력 경로는 **`tool_result` 본문 텍스트에만** 있다 |
| E2 | 메인 기록에는 `toolUseResult` 가 있고, 백그라운드 Bash 결과에 구조 필드 `backgroundTaskId` 가 있다(값 = 경로의 파일 이름 줄기). 경로 자체는 여기서도 `tool_result` 본문(과 `toolUseResult.stdout`)에만 있다. 비동기 Agent 결과에는 `toolUseResult.outputFile` 키가 있다 | 메인에서도 **같은 문구로** 경로를 얻을 수 있다 → 서브에이전트·메인에 규칙 하나(LA6) |
| E3 | `type:"user"` 줄의 `tool_result` 블록 안에서만 센 일치: 메인 157건 · 서브에이전트 162건. **전부 Bash 결과**, 부모 디렉터리 이름 `tasks` 100%, 본문에 `ID: <파일 줄기>` 100%, 조부모 디렉터리 이름 == 줄의 `sessionId` 서브에이전트 162/162 · 메인 150/157, 심볼릭 링크 0, 지금 존재 메인 1 · 서브에이전트 4 | 경로 검증 5조건(LA6)이 정상 데이터를 거의 다 통과한다. 메인 7건 손실은 fail-open 방향 |
| E4 | 같은 문구가 `tool_result` **밖**에도 나온다 — 사람 프롬프트·assistant 줄(설계 지시문이 그 문구를 인용하는 경우 등) | 위치 제한(`user` 줄의 `tool_result` 블록 안)이 필수다 |
| E5 | 꼬리 창 전량 JSON 해석 비용(최근 600KB+ 서브에이전트 기록 6개): 128KiB 0.35–0.54 ms(창이 덮는 시간 0.2–2.5분) · **256KiB 0.82–1.12 ms(3.2–4.8분, tool_use 줄 11–32)** · 512KiB 1.49–2.61 ms(3.7–7.6분) | 전량 해석 창 = 256KiB(LA2). 도구 개수 범위는 "최근 10분"을 약속하지 않고 실제 범위를 싣는다(LA5) |
| E6 | 지금 `~/.claude/hub/hub.html` 크기 280,795 B(stat) | D2 비용 산정(LA11) |

---

## 3. 비목표

| # | 하지 않는 것 | 이유 |
|---|---|---|
| N1 | 메인 세션 자체(서브에이전트 없이 긴 메인 턴)의 활동 표시 | 범위 P3 밖. 메인 기록 mtime 은 작업 신호가 아니다(SL10) |
| N2 | 출력·명령·설명 텍스트의 어떤 형태(마스킹·요약·마지막 줄 포함) | P2 |
| N3 | Bash 명령 문자열로 세분(「테스트 실행」 등) | P2 — 도구 이름만 |
| N4 | 출력 파일 줄 수 | 내용을 열어야 한다. 「늘었다」는 mtime 이, 「얼마나」는 크기가 이미 말한다(LA6) |
| N5 | 「멈춤」 단정·새 표시 상태·자동 조치 | 조용한 명령과 멈춘 명령은 출력으로 구분되지 않는다(P5). 상태 사다리 불변(LA8) |
| N6 | 끄는 스위치 | SL9·LS12 선례 — 고장 대비는 fail-open 구조가 맡는다(LA13) |
| N7 | 수집 캐시 | 비용이 50 ms 임계 안이다(LA15). 넘으면 에스컬레이션 |
| N8 | 훅·에이전트·명령 파일 변경, 새 훅 | P4 |

---

## 4. 영향 범위

| 파일 | 순수/IO | 변경 | 현재 → 예상 줄 수 |
|------|---------|------|------------------|
| `hub/bin/hub_activity.py` **(신설)** | ★순수 | 도구 종류 분류, 꼬리 창 활동 해석(A), 출력 경로 찾기(B), 출력 stat 요약, 멈춤 의심 시각, 계약 타입 4개 | 0 → ~240 |
| `hub/bin/hub_subagent_read.py` | I/O | `read_live_activity` + 꼬리 바이트 읽기·출력 lstat 헬퍼. 기존 `_read_transcript_window_bytes` 는 새 헬퍼를 부르도록 본문만 바꾼다(GOTCHA 1) | 284 → ~400 |
| `hub/bin/hub_session.py` | ★순수 | `SubagentRunView.activity`, `BackgroundWait.output`, `waking_background_task_count`, `is_background_output_scan_target`, `summarize_agent_runs`·`effective_background_wait`·`compute_session_view` 배선, docstring 개정 | 604 → ~645 |
| `hub/bin/hub_project.py` | ★순수 | `live_activity` 통과(3함수) | 632 → ~640 |
| `hub/bin/hub_collect.py` | I/O | `_read_session_annotations` 가 `now_ms` 를 받고 `read_live_activity` 결과를 하나 더 돌려준다, `collect_snapshot` 배선 | 766 → ~771 (800 상한 — GOTCHA 4) |
| `hub/bin/hub_transcript.py` | ★순수 | `_epoch_ms_from_iso8601` → 공개 `epoch_ms_from_iso8601`(정의 1·호출 1). 동작 불변 | 468 → 468 |
| `hub/bin/hub_template.html` | 화면 | CSS 6규칙, 상수 19, 새 함수 16(M4 실측 — 추정은 5·6·6. 문구·구분자 상수를 하나씩 이름 붙였고 행 툴팁 줄을 종류별 작은 함수로 나눴다), `renderAgentRunRow`·`agentRunTooltipText`·`backgroundBadgeTooltipText`·`renderSessionContent` 수정 | 3235 → 3421 |
| `hub/install.sh` | — | `HUB_FILE_COUNT` 31 → 32(잠정) | ±0 |
| `hub/README.md` | 문서 | 프라이버시 고지 3곳·화면 배치·툴팁 목록·알려진 한계·파일 배치(32개) | +~30 |
| `commands/hub.md` | 문서(배포) | 설치 고지 ① 한 문장 | +2 |
| `docs/prps/hub-dashboard.md` | 문서 | 모듈 구성표에 `hub_activity.py` | +1 |
| `docs/prps/hub-subagent-background-pause.md` · `hub-subagent-liveness-signal.md` | 문서 | 개정 블록(원문 삭제 금지): BW N4·BW9 / SL5 옆 | +~10 |
| `tests/hub/test_hub_activity.py` **(신설)** | 테스트 | 순수 해석·경로·계약 구조 | ~380 |
| `tests/hub/test_hub_template_dom_activity.py` **(신설)** | 테스트 | DOM 행동(Chrome 없으면 SKIP) | ~200 |
| `tests/hub/test_hub_subagent_read_activity.py`(신설)·`test_hub_session.py`·`test_hub_model.py`·`test_hub_collect.py`·`test_hub_project.py`·`test_hub_transcript.py` | 테스트 | §10 | +~420 |
| `tests/run.sh` | 테스트 | T25-269~T25-274(잠정) 신설, T25-10·T25-93·T25-104·T25-149 개정, `SOURCE_GUARD_ID_FLOOR`·`LEDGER_MUTATION_ROW_FLOOR` | +~170 |
| `tests/mutations.tsv` | 테스트 | 변조행 6 | +6 |

**건드리지 않는 것**: `hub_hook.py`·`hub_settings.py`(훅·이벤트 스키마 불변 — T25-249 무영향) · `hub_session_facts.py`(사실은
훅에서만 접는다) · `hub_subagent.py`(meta·재개 제목 파서) · `hub_model.py`(`asdict` 가 새 중첩 필드를 싣는다) ·
`hub_server*.py` · `rules/`·`CLAUDE.md`(T26 무영향) · `SessionView` 필드(T25-150·T25-225 역방향 그대로 통과).

---

## 5. 파일 구조와 모듈 경계

```
 ~/.claude/projects/<인코딩>/<sid>/subagents/agent-<id>.jsonl ─┐ (끝 1MiB 1회 읽기)
 ~/.claude/projects/<인코딩>/<sid>.jsonl ───────────────────────┤ (백그라운드 대기 후보 세션만)
 <호스트 tmp>/…/<sid>/tasks/<id>.output ── lstat 만 ───────────┤
                                                              ▼
 hub_subagent_read.py (I/O)  read_live_activity ──bytes──▶ hub_activity.py (★순수, 잎에 가깝다)
        │  is_running_subagent·is_background_output_scan_target      parse_tool_activity / background_output_paths
        │  (hub_session 의 순수 술어 재사용)                         summarize_background_outputs / with_stall_suspect_at
        ▼  LiveActivity(계약)
 hub_collect._read_session_annotations ─▶ hub_project.compose_project_views ─▶ hub_session.compute_session_view
                                                                                  │ SubagentRunView.activity
                                                                                  │ BackgroundWait.output
                                                                                  ▼
                                                     hub_model(asdict) ─▶ hub_template.html(#dzh-data → 렌더)
```

- **임포트 방향**: `hub_redact ← hub_transcript ← hub_activity ← hub_session ← hub_project ← hub_model`, I/O 쪽은
  `hub_subagent_read → {hub_activity, hub_session, hub_session_facts, hub_subagent, hub_project}`. `hub_activity` 는
  `hub_transcript.epoch_ms_from_iso8601` 하나만 가져온다(GOTCHA 7 의 "Z" 처리 사본을 만들지 않으려고). 순환 없음 —
  `hub_session` 은 읽기 모듈을 임포트하지 않는다.
- **새 모듈을 둔 이유**(기존 `hub_subagent.py` 에 얹지 않은 이유): ① 이 기능에서 **호스트 기록 내용을 해석하는 코드 전부**가
  한 파일에 모여야 프라이버시 가드(T25-269·T25-270)가 파일 단위로 성립한다 — 함수 범위 awk 로 가드하면 개명 한 번에
  눈이 먼다. ② 이 모듈은 문자열을 **밖으로 내보내지 않는다**(스크럽 계약 A 가 필요 없다) — `hub_redact` 를 쓰는
  `hub_subagent.py` 와 계약이 다르다. I/O 는 경로 조립·안전 조각 검사·부모 transcript 경로가 이미 있는
  `hub_subagent_read.py` 에 얹는다(사본 3벌을 만들지 않는다).
- **`LiveActivity` 묶음**: 보강 dict 두 개를 따로 나르면 `hub_collect`(766/800)와 7-튜플 반환, 매개변수 15개짜리
  `compute_session_view` 가 각각 2칸씩 늘어난다. 한 수집의 같은 읽기에서 나온 두 값이라 PS3 의 「묶어 나른다」 근거와 같다.

---

## 6. 설계 결정

### 결정 ID 목록

| ID | 한 줄 |
|----|------|
| LA1 | 신호원 = 호스트가 이미 남기는 기록을 수집 시점에 읽는다. 훅·에이전트·토큰 무변경 |
| LA2 | 안 A 대상 = **지금 도는**(`is_running_subagent`) 실행만, 세션당 최대 8건. 끝 1MiB 를 한 번 읽어 그 끝 256KiB 만 전량 해석 |
| LA3 | 도구 종류 = 5값 닫힌 집합(읽기·수정·실행·위임·기타), **도구 이름으로만** 분류. 스냅샷에는 종류만, 이름은 안 싣는다 |
| LA4 | 진행 중 호출 = 창 안의 `tool_use` 중 같은 id 의 `tool_result` 가 없는 것. 개수·가장 오래된 것의 종류·시각 |
| LA5 | 도구 개수 = 창 ∩ [마지막 기록 − 10분, 마지막 기록], 실제 하한 시각을 함께 싣는다. **툴팁 전용** |
| LA6 | 출력 경로 = `user` 줄 `tool_result` 블록 안의 호스트 문구 + 형태 검증 5조건. lstat 만(정규 파일), 수정 시각·크기만. 줄 수 기각 |
| LA7 | 귀속 = 경로를 찾은 기록의 주인. 실행 줄은 그 실행 자신의 창, 배지는 메인 기록 + 보고 지평 안에서 멈춘 서브에이전트(최대 8) |
| LA8 | 「새 기록 없음」 표지 = 서버가 정적 시각 `stall_suspect_at_ms` 를 싣고 클라이언트가 비교. 실행 줄 표지일 뿐 **상태가 아니다** |
| LA9 | 화면 ① 실행 줄 아래 활동 한 줄 |
| LA10 | 화면 ② 백그라운드 대기 첫 줄 끝 「출력 N분 전 갱신」 + 배지 툴팁 한 줄 |
| LA11 | D2 — 활동 값은 **파일 내용·stat 의 함수**(지금 시각 무관). 도는 동안은 수집마다 `hub.html` 을 다시 쓴다(비용 명시) |
| LA12 | fail-open·예외 범위 — 계약 B(예외 없음). 순수 해석은 `(ValueError, RecursionError)`, I/O 층은 `OSError`·`ValueError`(NUL·서로게이트)만 잡는다, 경고 없음 |
| LA13 | 스위치·`record_prompt_excerpt` 게이트 없음 |
| LA14 | 모듈 배치(§5)·`epoch_ms_from_iso8601` 공개화·`LiveActivity` 묶음 |
| LA15 | 비용 예산과 에스컬레이션(TF9 와 같은 50 ms) |

### LA1. 신호원 — 대안은 한 문단

이미 정해진 방향(P4)을 따른다. 검토 후 기각한 것: **도구 호출마다 훅 기록**(PostToolUse) — 호출마다 프로세스 기동
오버헤드가 세션 진행을 늦추고, 훅이 도구 입력을 받으므로 BW2(「자유 텍스트는 읽지도 않는다」)와 정면으로 충돌한다.
**에이전트가 직접 진행 기록** — 턴·토큰이 늘고, 「서브에이전트 단계에서는 기록하지 않는다」(dashboard-impl-substeps 확정
2·`session-dashboard.md` 결정 4)를 뒤집는다. **메인 `toolUseResult.backgroundTaskId`(구조 필드)만 쓰기** — 서브에이전트
기록에는 `toolUseResult` 가 없어(E1) 어차피 본문 문구가 필요하고, 규칙이 둘이 된다. **세션의 `tasks/` 디렉터리 열거** —
호스트 tmp 루트·uid·인코딩을 재구성해야 하는 비공개 배치(BW N4 의 기각 사유 그대로)라 채택하지 않되, 호스트가 문구를
바꾸면 검토할 후속 후보로 남긴다(§13 A3).

### LA2. 안 A 의 대상과 창

- 대상: 세션마다 `ended_at_ms is None` 이고 `hub_session.is_running_subagent(sub, now_ms, SUBAGENT_ZOMBIE_AFTER_MS,
  SL mtime)` 이 참인 실행을 시작 시각 내림차순으로 `ACTIVITY_RUNS_MAX_PER_SESSION = 8` 건까지. 화면 상한
  (`MAX_VISIBLE_AGENT_RUNS` 5)의 여유이자 실측 동시 미종료 최대 4건의 2배다. **화면이 `is_running` 에 쓰는 것과 같은 술어**라
  읽기 대상과 표시 대상이 어긋나지 않는다 — 좀비·일시정지 실행은 읽지도 않는다(P8: 일시정지 = `ended_at_ms` 가 채워진
  상태라 자동 제외, 재개되면 `SubagentStart` 가 지워 다시 대상).
- 창: 경로 조립은 SL1 그대로(`observed_cwds` 순서, 먼저 읽히는 것). 끝 `ACTIVITY_WINDOW_BYTES = 1MiB` 를 **한 번** 읽고
  ① 그 끝 `ACTIVITY_PARSE_BYTES = 256KiB` 를 줄 단위 전량 해석(안 A) ② 1MiB 전체에서 출력 문구 줄만 해석(안 B, LA6).
  256KiB 근거 E5 — 해석 1 ms 안팎, 바쁜 실행의 3~5분을 덮는다. 진행 중 호출은 정의상 창 끝 가까이에 있다(호출이 결과를
  기다리는 동안 그 실행은 기록을 쓰지 않는다). 1MiB 근거 — 바쁜 날 1.4MB/시간 기준 40분 남짓으로, 실행이 백그라운드 셸을
  띄운 뒤 sleep·확인 루프(작은 줄)를 도는 전형에서 띄운 줄이 오래 창 안에 남는다. 페이지 캐시에서 1MiB 읽기는 0.1 ms 대.
- 창 머리의 찢긴 줄·끝의 쓰는 중인 줄은 JSON 실패로 건너뛴다(`errors="replace"`, GOTCHA 7 — `_read_transcript_window_bytes`
  와 같은 방식).

### LA3. 도구 종류 — 이름으로만, 5값

```python
ToolKind = Literal["read", "edit", "run", "delegate", "other"]
TOOL_KIND_BY_NAME: dict[str, ToolKind] = {
    "Read": "read", "Grep": "read", "Glob": "read", "LS": "read", "NotebookRead": "read",
    "WebFetch": "read", "WebSearch": "read",
    "Edit": "edit", "MultiEdit": "edit", "Write": "edit", "NotebookEdit": "edit",
    "Bash": "run", "BashOutput": "run", "KillShell": "run", "KillBash": "run", "Monitor": "run",
    "Agent": "delegate", "Task": "delegate", "SendMessage": "delegate", "Workflow": "delegate",
}   # 표에 없는 이름(Skill·TodoWrite·AskUserQuestion·SubagentHandback·ToolSearch·mcp__* 등)과 문자열이 아닌 값은 "other"
```

- 스냅샷에 실리는 것은 **종류(5값 리터럴)뿐**이다. 원래 도구 이름은 메모리에서 분류에만 쓰고 버린다 — `mcp__<서버>__…`
  이름에는 사용자가 붙인 서버 이름이 들어 있어 이름 자체도 싣지 않는다.
- 호스트 목록의 사본을 늘리지 않는다 — 모르는 이름은 `other`(BW2 의 형태 검사 선례와 같은 페일오픈).

### LA4. 진행 중 호출

- `type:"assistant"` 줄의 `tool_use` 블록(문자열 `id`)을 `id → (줄 시각, 종류)` 로 모으고(같은 id 의 사본 줄은 첫 것만 —
  대화 기록 재부착이 같은 줄을 다시 붙인다, `hub_subagent._request_summary` 의 실측), `type:"user"` 줄의 `tool_result`
  블록 `tool_use_id` 를 집합으로 모은다. 차집합이 **진행 중**이다.
- 싣는 것: `pending_count`, 가장 오래된 진행 중 호출의 `pending_tool_kind`·`pending_since_ms`(병렬 호출이면 가장 오래 기다린
  것이 사용자가 궁금한 것이다).
- 창 경계: 창 밖에서 시작해 창 안에서 끝난 호출(결과만 보임)은 무시한다. 창 안에서 시작한 호출의 결과는 정의상 그 뒤(창
  안)에 있다 — 창 때문에 생기는 거짓 진행 중은 없다. 쓰는 중인 결과 줄이 찢겨 있으면 그 순간만 진행 중으로 보인다(다음
  수집에서 풀린다).
- 백그라운드 Bash(`run_in_background`)는 결과가 즉시 오므로 진행 중이 아니다 — 그 작업의 진행은 안 B 가 맡는다.

### LA5. 도구 개수 — 실제 범위를 싣는다, 툴팁 전용

- 범위 하한 `recent_counts_since_ms = max(창의 첫 기록 시각, last_record_at_ms − RECENT_TOOL_WINDOW_MS)`,
  `RECENT_TOOL_WINDOW_MS = 10분`. 그 안의 `tool_use` 를 종류별로 센다(`ToolKindCounts`, 다섯 정수).
- **지금 시각을 쓰지 않는다** — "지금부터 10분"은 아무 일이 없어도 매 수집 값이 바뀌어 D2 를 깬다. 마지막 기록 기준이라
  같은 파일이면 같은 값이다.
- 256KiB 창은 바쁜 실행의 3~5분만 덮으므로(E5) "최근 10분"이라고 쓰면 거짓이 된다 — 툴팁 문구가 하한 시각을 그대로 말한다
  (「14:27 이후 도구 — 읽기 6 · 수정 2 · 실행 3」). 화면 본문에는 싣지 않는다(320px 폭·가독성).

### LA6. 출력 경로(안 B) — 문구 + 형태 검증, stat 만

**찾기**(순수, `background_output_paths(window, session_id)`): 창에서 `b"Output is being written to"` 를 품은 줄만 골라
(`hub_subagent._lines_with_marker_backwards` 와 같은 방식 — 표지 없는 줄은 디코딩하지 않는다) JSON 으로 풀고, 아래를 **모두**
만족하는 경로만 낸다. 파일에서 뒤의 것부터, 중복 제거, 최대 `BACKGROUND_OUTPUT_MAX_FILES = 8`. (구현 반영: 안 A 의 `parse_tool_activity` 는
받은 창의 끝 `ACTIVITY_PARSE_BYTES`(256KiB)만 **함수 안에서** 잘라 해석한다 — I/O 층은 1MiB 창을 그대로 넘기고, 이 찾기는 1MiB 전체를 본다.)

1. 위치: `type == "user"` 줄의 `message.content[]` 중 `type == "tool_result"` 블록의 본문(문자열, 또는 `text` 블록들의
   `text`) 안 — E4 의 거짓 일치(프롬프트·assistant 줄)를 배제한다.
2. 문구: `Output is being written to:? *(/\S+?\.output)` (경로 뒤가 단어 문자가 아님).
3. 모양: 절대경로, 빈·`.`·`..` 조각 없음, NUL 없음(구현이 더한 방어선 — NUL 은 파일 상태를 볼 때 예외를 낸다), 파일 이름 줄기가
   `[A-Za-z0-9_-]{1,64}`.
4. 위치 규칙: 부모 디렉터리 이름 `tasks`, 조부모 디렉터리 이름 == 이 세션의 `session_id`(E3 — 다른 세션 작업의 오귀속을
   구조적으로 막는다).
5. 짝: 같은 본문에 `ID: <줄기>` 가 있다(E3 100%).

**보기**(I/O): `os.lstat` → `stat.S_ISREG` 일 때만 `(mtime_ms, size)`. 파일을 **열지 않는다**. 심볼릭 링크·디렉터리·없음은
버린다. `OSError`·`ValueError`(NUL·서로게이트) 는 그 경로만 버린다(LA12).

**잔여 위험**: 경로의 앞부분은 고정하지 않는다 — 뒤 세 조각(`<세션>/tasks/<id>.output`)만 검증하고 stat 만 하므로 새는 것은 mtime·크기뿐이다.
응답 없는 마운트를 가리키면 lstat 이 막힐 수 있다. 조이려면(호스트 tmp 루트 고정) LA1 의 기각 사유(비공개 배치 재구성)와 충돌한다 → 사용자 판단.

**줄 수 vs 크기**: 크기를 쓴다. 줄 수는 내용을 읽어야 하고(시크릿이 섞일 수 있는 출력이다) 「진행 중인가」는 mtime 이,
「얼마나」는 크기가 이미 답한다. 「크기 증가」를 수집 사이 비교로 판정하려면 서버 상태가 필요하지만 mtime 갱신이 곧 증가의
증거라 상태를 두지 않는다(YAGNI). 크기는 툴팁에만 보인다.

### LA7. 귀속 — 경로를 찾은 기록의 주인

| 경로를 찾은 곳 | 귀속 | 화면 | 가능한 범위 / 불가능한 범위 |
|---|---|---|---|
| 도는 서브에이전트 자신의 창(LA2 의 1MiB) | 그 실행 | 실행 줄 활동 줄 끝 「출력 N분 전」 | 띄운 줄이 창 안이면 가능. 띄운 뒤 1MiB 넘게 일했으면 놓친다(표시 없음) |
| 메인 기록 끝 1MiB | 세션(배지) | 「백그라운드 대기」 첫 줄·툴팁 | 메인이 띄운 셸. E3 의 7/157(조부모 ≠ 세션 id, 재배치 추정)은 놓친다 |
| 보고 지평 안에서 멈춘 서브에이전트들의 끝 1MiB | 세션(배지) | 같음 | `ended_at_ms ≥ reported_at_ms − BACKGROUND_WAIT_MAX_MS` 인 실행을 종료 시각 내림차순 최대 `BACKGROUND_SCAN_SUBAGENTS_MAX = 8`. BW 의 전형(서브에이전트가 검사를 띄우고 멈춤)이 여기다 |

- **배지 쪽 읽기 게이트**(순수, `hub_session.is_background_output_scan_target(facts, now_ms)`): `facts.background_report`
  가 있고, 깨우는 작업 수(`waking_background_task_count` — `effective_background_wait` 의 합산식을 함수로 뽑아 둘이 같은
  식을 공유한다) 또는 1회성 예약 수가 0 보다 크고, 보고 뒤 `BACKGROUND_WAIT_MAX_MS` 가 지나지 않았을 때만. 명부(roster)는
  섞지 않는다 — 판정이 아니라 읽기 범위 결정이고, 결과는 `state == "background"` 일 때만 뷰에 남는다(BW9 불변식 그대로).
- 실행 줄 귀속(BW7 의 「귀속하지 않는다」)은 **훅 배열** 이야기다 — 배열에 소유자가 없어서였다. 여기서는 띄운 줄을 쓴 기록이
  곧 소유자라 귀속이 정확하다. 그래도 BW7 의 칩 표시(멈춘 서브에이전트는 「종료」)는 바꾸지 않는다 — 배지 쪽에서 세션
  단위로 합쳐 보인다.
- 배지 출력 요약은 찾은 모든 경로(메인 + 서브에이전트, 중복 제거)를 합친다: 파일 수·수정 시각 최댓값·크기 합. 파일 수 상한
  (`BACKGROUND_OUTPUT_MAX_FILES`)은 **존재하는 정규 파일 중 앞 8개**다 — 순서는 메인 기록 경로 먼저, 그다음 최근에 멈춘 실행 순(중복 제거 뒤).

### LA8. 「새 기록 없음」 — 정적 시각, 실행 줄 표지, 상태 아님

- 서버(순수, `with_stall_suspect_at(activity, run_started_at_ms)`, `summarize_agent_runs` 가 부른다):
  `pending_count > 0` 이면 `None`, 아니면 `max(last_record_at_ms, run_started_at_ms) + SUBAGENT_STALL_SUSPECT_AFTER_MS`.
  `run_started_at_ms` 를 섞는 이유: 재개(같은 id 의 `SubagentStart`)되면 시작 시각이 재개 시각으로 덮인다(TF7) — 일시정지
  동안 비어 있던 기록 시각으로 재개 직후 바로 「새 기록 없음」이 뜨는 것을 막는다.
- 클라이언트: `now ≥ stall_suspect_at_ms` 면 표시. 서버는 "언제부터 의심할지"라는 **정적 시각**만 싣는다 — BW9 의
  `until_ms` 와 같은 모양이라 임계값의 출처가 파이썬 상수 하나다(자바스크립트 사본 없음).
- 조건 P5 의 세 항이 구조로 성립한다: 기록 공백 = `last_record_at_ms`(재개 보정), 진행 중 호출 없음 = `pending_count == 0`,
  일시정지·백그라운드 대기 아님 = 활동은 `is_running` 실행에만 붙는다(일시정지면 `ended_at_ms` 가 있다. 실행이 도는 세션은
  base_state 가 working 이라 `background` 가 될 수 없다).
- `SUBAGENT_STALL_SUSPECT_AFTER_MS = 10 * 60 * 1000` — **잠정.** 근거: 정상 실행 안 최장 침묵이 Bash 상한 10분에 몰려 있었고
  (SL E2) 그 호출은 진행 중이라 제외된다. 48회의 10분+ 공백은 위임 도구 결과 대기(진행 중) 또는 일시정지(`ended_at_ms`)로
  해석되며, 둘 다 이 규칙이 제외한다 — **이 해석은 구현 M0 에서 같은 48건을 규칙에 재생해 확인한다**(통과 기준: 오탐 0).
  다른 값이 필요하면 상수 한 줄과 README 고지를 같이 고친다(T25-273).
- **M0 재생 결과(2026-10-07)**: 같은 48건(모든 프로젝트 기록, 09-25 이후·현행 모델)을 규칙에 재생 — 오탐 0, 일시정지(`SubagentStop`) 확인 43건, 이벤트 로그가 09-30 부터라 확인 불가 5건(09-29, 같은 모양 29건이 전부 일시정지로 확인됨). 임계 10분 유지. **한계 둘**: ① 재개 `SubagentStart` 는 실사례로 재생하지 않았다 — 재개 직후의 오탐은 LA-S3 단위 테스트가 지킨다. ② 이 재생은 **오탐만** 잰다 — 진짜 멈춘 실행(검출해야 할 것)의 재현율 표본은 없다. 확인 불가 5건은 유사한 29건으로 추정했다.
- **상태 사다리와의 관계**: 바꾸지 않는다. `작업중 > 한도 초과 > 백그라운드 대기 > 대기 > 소식 없음 > 완료` 순서·세션/프로젝트
  배지·카드 glow·정렬·12시간 숨김 모두 그대로다. 「새 기록 없음」은 7번째 상태가 아니라 실행 줄 하나의 주석이다 — 허브가 근거
  없이 상태를 뒤집으면 배지 전체의 신뢰가 깨지고, 실제로 죽은 실행은 이미 좀비 가드(마지막 기록 90분, ZG·SL2)가 칩을 끈다.
  시각 처리는 `소식 없음` 배지와 같은 `--attention` 글자색 + 같은 글리프 ▲(같은 「소식 없음」 계열 언어), 면색·테두리·
  애니메이션 없음.

### LA9. 화면 ① — 실행 줄 활동 줄

`is_running` 이고 `activity` 가 있는 실행 줄에만 붙는다. 실행 줄(`.agent-run`) **안의** 두 번째 줄이라 맞대기(PU1)의 렌더 키
(`agent_id`)와 함께 움직이고 행 툴팁을 공유한다.

| 우선 | 조건 | 본문(예) |
|---|---|---|
| 1 | `stall_suspect_at_ms != null && now ≥ stall_suspect_at_ms` | `▲ 12분째 새 기록 없음` (주황 — 경과 = 지금 − `last_record_at_ms`) |
| 2 | `pending_count > 0` | `명령 실행 중 · 4분째` / 여럿이면 `명령 실행 중 외 1건 · 4분째` / 1분 미만이면 `· 방금 시작` |
| 3 | 그 밖 | `마지막 기록 방금 · 읽기` / `마지막 기록 3분 전 · 실행` (마지막 도구 종류가 없으면 종류 생략) |
| + | `background_output != null`(1·2·3 공통 꼬리) | ` · 출력 1분 전` |

진행 중 문구(종류별): 읽기 `읽는 중` · 수정 `고치는 중` · 실행 `명령 실행 중` · 위임 `다른 에이전트 기다리는 중` · 기타 `도구 실행 중`.
마지막 도구 명사: `읽기`·`수정`·`실행`·`위임`·`기타`. 경과는 기존 `elapsedLabel`·`durationLabel` 을 재사용한다(새 포맷 함수는
「N분째」 꼬리를 붙이는 작은 래퍼 하나).

행 툴팁(`agentRunTooltipText`, `.tooltip` 은 `white-space:pre-wrap` 이라 줄바꿈이 산다) — 기존 첫 줄 뒤에 줄을 더한다:

```
implementer · 구현 단계 · sonnet · 시작 14:02 · 진행 중            ← 오늘과 같다
마지막 기록 14:31(방금) · 14:27 이후 도구 — 읽기 6 · 수정 2 · 실행 3   ← 0 인 종류는 생략
결과를 기다리는 도구 1건 — 명령 실행 중, 14:27 부터                  ← pending 이 있을 때(진행 중 문구 표 재사용 — M4 구현)
백그라운드 출력 파일 1개 — 14:30 갱신 · 48KB                        ← background_output 이 있을 때
14:19 이후 새 기록이 없고 결과를 기다리는 도구도 없습니다(기준 10분).  ← 새 기록 없음일 때
허브는 멈춤을 단정하지 않습니다 — 길게 생각하는 중일 수도 있습니다.
```

**구현 반영(M4)**: ① 마지막 줄 위의 「기준 10분」은 자바스크립트에 임계값 사본을 두지 않고 서버가 준 정적 시각에서 거꾸로 센다 —
`stall_suspect_at_ms − max(last_record_at_ms, started_at_ms)`(표지 시각이 `max(마지막 기록, 실행 시작) + 임계` 라 같은 값이 나온다).
② 기다리는 도구 줄은 진행 중 문구 표(`TOOL_KIND_PENDING_LABEL`)를 재사용해 「명령 실행 중, 14:27 부터」로 적는다 — 위 예시의
「명령 실행」과 한 글자 다르다. 표를 하나 더 두지 않으려는 선택이다.

CSS(새 색 토큰 0, 애니메이션 0):

```css
.agent-run.agent-run-with-activity{display:grid;grid-template-columns:auto minmax(0,1fr) auto;column-gap:6px;row-gap:0;
                                   align-items:baseline}
.agent-run-activity{grid-column:2 / -1;font-size:11px;line-height:1.35;color:var(--muted);
                    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.agent-run-activity-stall{color:var(--attention);font-weight:700}
.agent-run-activity .glyph{margin-right:3px}
```

활동이 있는 행만 칩 | 제목 | 경과 격자로 바꾸고 활동 줄이 2칸부터 끝까지 가로지르게 하는 이유: 활동 줄 왼쪽이 제목 왼쪽에 맞아야
어느 서브에이전트에 딸린 내용인지 읽힌다. 칩 폭은 단계 라벨(「설계」)이냐 `agent_type` 폴백(최대 12자 + 말줄임)이냐에 따라 가변이라
고정 들여쓰기로는 못 맞추고, 칸 경계가 곧 제목 왼쪽이다. 제목 칸을 `minmax(0,1fr)` 로 둬 긴 제목이 칸을 밀어내지 않고 말줄임으로
남는다. 격자는 `.agent-run` 기본 규칙이 아니라 modifier 에만 둬서 활동이 없는 오늘의 줄 모양(flex)을 한 픽셀도 바꾸지 않는다.

개정 2026-10-07 — 사용자 요청: 활동 줄 왼쪽을 칩이 아니라 제목 왼쪽에 맞추도록 flex-wrap → grid 로 변경(위 CSS·이유 문단이 개정본이다).

### LA10. 화면 ② — 백그라운드 대기

`session.state == "background"` 이고 `background_wait.output` 이 있을 때만. 첫 줄(`.session-line`, 이미 `flex-wrap`) 끝에
`<span class="session-activity">출력 1분 전 갱신</span>` — 320px 목업에서 한 줄에 들어간다(§8.4). 배지 라벨 「◐ 백그라운드
대기」·프로젝트 배지 「◐ 백그라운드」는 바꾸지 않는다(BW R8 의 320px 실측 제약).

배지 툴팁(`backgroundBadgeTooltipText`) — 오늘 문장 뒤에 한 줄:
`작업 출력은 14:30(1분 전)에 마지막으로 늘었습니다 — 확인된 출력 파일 1개 · 1.2MB. 조용히 오래 도는 명령은 끝날 때만 출력이 늘 수 있습니다.`
「확인된」을 붙이는 이유: 훅이 센 작업 수(`task_count`)와 찾은 파일 수가 다를 수 있다(LA7 의 불가능 범위). 배지 쪽에는
「새 기록 없음」을 띄우지 않는다(P5 — 백그라운드 대기 상태는 판정 대상이 아니다). 출력이 오래 전이면 「출력 25분 전 갱신」이
그대로 정보다.

### LA11. D2 — 활동 값과 `snapshot_content_key`

- `hub_activity.py` 의 모든 값은 **파일 내용과 stat 의 함수**다 — 이 모듈은 지금 시각을 받지 않는다(T25-271). 같은 파일이면
  같은 값이라, 아무것도 돌지 않을 때 키는 오늘과 똑같이 안정적이고 쓰기 억제가 그대로 산다.
- 무언가 도는 동안에는 기록·출력이 바뀔 때마다 값이 바뀌어 **수집마다 `hub.html` 을 다시 쓴다.** 비용: 280,795 B(E6) 원자적
  쓰기 1회 / 수집. 수집은 열린 페이지의 60초 폴링(+포커스·탭 복귀, 신선도 창 2초)과 5분 유지보수 티커가 이끌므로 탭 하나면
  분당 1회 안팎이다. 클라이언트는 이미 매 폴링마다 페이지 전체를 받고(`html === lastHtml` 비교) 30초마다 `render()` 하므로
  늘어나는 것은 분당 `DOMParser` 1회 정도다. 이 기능의 목적이 "바뀐 것을 보이기"라 피할 수 없는 비용이고, 값을 분 단위로 깎는
  양자화는 폴링 주기와 같아 이득이 없다(측정 없는 최적화 금지).
- SL5 는 **그대로다** — 생존 판정용 mtime dict(`subagent_activity_by_agent_id`)는 여전히 판정에만 쓰이고 뷰에 실리지 않는다
  (SL-U10·T25-225 역방향 무수정 통과). 새 값은 별도 통로(`live_activity`)로 `SubagentRunView`·`BackgroundWait` 에만 실리고
  `SessionView` 에는 새 필드가 없다. BW9 의 「정적 값만」은 `output` 에 한해 개정한다(개정 블록).

### LA12. fail-open·예외 범위

- 순수 해석(계약 B — 어떤 입력에도 예외를 던지지 않는다): `json.loads` 는 `(ValueError, RecursionError)` 만 잡고 그 줄을
  건너뛴다. 나머지는 `isinstance` 방어. 넓은 `except Exception` 은 두지 않는다 — 진짜 버그를 숨긴다.
- `None`(= 오늘 화면)이 되는 경우: 창을 못 읽음 · 시각이 붙은 줄 0개 · 인식한 `tool_use`/`tool_result` 블록 0개(호스트 형식이
  바뀌었거나 아직 도구를 안 썼다 — 이때 「새 기록 없음」을 내면 형식 변경이 오탐으로 번진다).
- I/O: I/O 층은 `OSError`·`ValueError`(NUL·서로게이트)를 잡는다 — 호스트 기록 본문의 경로는 우리가 소유하지 않는 입력이라 JSON 이스케이프된 외톨이 서로게이트(`\ud800`)가 형태 검증을 통과해 파일 상태를 볼 때 `UnicodeEncodeError` 를 낼 수 있다(1회차 검수 HIGH). 경고는 내지 않는다 —
SL8 처럼 부재와 실패가 같은 결과이고, 기록 없는 실행마다 소음이 쌓인다.
  `session_id`·`agent_id` 는 조립 전에 `_is_safe_path_segment` 를 통과해야 한다.

### LA13. 스위치·게이트 없음

`record_prompt_excerpt` 로 게이팅하지 않는다(SL7·LS2 선례 — 프롬프트 발췌가 아니다. 그 스위치를 끈 사용자에게만 기능이
사라진다). 새 설정도 없다(SL9·LS12). 고장 대비는 LA12 의 fail-open 이 맡는다. 읽는 범위가 늘어나는 것은 프라이버시 고지로
알린다(§9.4) — 끄는 수단이 필요하다는 판단이 나오면 승인 쟁점 1 의 대안이다.

### LA14. 모듈 배치 세부

- `hub_transcript._epoch_ms_from_iso8601` → `epoch_ms_from_iso8601`(공개). 정의 1·호출 1·테스트 docstring 언급 1. 3.10 의
  트레일링 "Z" 함정을 다루는 함수라 사본을 만들지 않는다(사적 심볼 임포트 금지 관례).
- `hub_activity.py` 는 `★순수` 표지를 달고 T25-10 목록에 들어간다(GOTCHA 2).

### LA15. 비용 예산

| 경로 | 수집 1회 최악(관측 기반) | 근거 |
|---|---|---|
| 안 A + 실행 줄 출력 | 미종료 4건 × (1MiB 읽기 ≈0.1 ms + 256KiB 해석 ≈1 ms + 표지 스캔 + lstat ≤8) ≈ 5 ms | E5, SL §2.6 |
| 배지 출력 | 후보 세션(보고 90분 안 + 깨우는 작업) × (메인 1MiB + 멈춘 실행 ≤8 × 1MiB 표지 스캔) — 세션당 ≈2–3 ms | TF9 실측(8MiB 창 + 표지 줄만 해석 2.7 ms) |

오늘 `collect_snapshot` 14–20 ms(TF9 실기) + 최악 ~10 ms → 50 ms 임계 안. **에스컬레이션**: 실기에서 `collect_snapshot` 이
50 ms 를 넘으면 (경로, 크기, mtime) 키 캐시를 재검토한다(TF9·MD4 와 같은 조건).

**G7 실측(구현 M3, 2026-10-07)**: 실데이터 읽기 전용 15회 — `collect_snapshot` 중앙값 31.2 ms(활동 읽기 제외) → 33.6 ms(포함), +2.4 ms. 50 ms 임계 안.

---

## 7. 데이터 모델과 인터페이스

### 7.1 `hub/bin/hub_activity.py` (★순수, 신설)

```python
"""hub_activity.py — 실행 중 활동 표시(결정 LA1~LA15, docs/prps/hub-live-activity.md)의 순수 해석 + 계약 타입.

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_activity.py 대상). 호스트 기록 내용을
해석하는 이 기능의 코드는 전부 여기 있다 — 읽는 필드는 화이트리스트(T25-269), 내보내는 타입에는 자유 문자열이
없다(T25-270), 지금 시각을 받지 않는다(T25-271)."""

ToolKind = Literal["read", "edit", "run", "delegate", "other"]
TOOL_KINDS: tuple[ToolKind, ...] = ("read", "edit", "run", "delegate", "other")
TOOL_KIND_BY_NAME: dict[str, ToolKind]                       # §6 LA3
ACTIVITY_WINDOW_BYTES = 1024 * 1024                          # 한 번 읽는 창 = 출력 경로 찾기 범위(LA2·LA6)
ACTIVITY_PARSE_BYTES = 256 * 1024                            # 전량 해석 창(LA2, E5)
RECENT_TOOL_WINDOW_MS = 10 * 60 * 1000                       # 도구 개수 범위 상한(LA5)
SUBAGENT_STALL_SUSPECT_AFTER_MS = 10 * 60 * 1000             # 잠정(LA8, 구현 M0 에서 확정)
ACTIVITY_RUNS_MAX_PER_SESSION = 8                            # LA2
BACKGROUND_SCAN_SUBAGENTS_MAX = 8                            # LA7
BACKGROUND_OUTPUT_MAX_FILES = 8                              # LA6
BACKGROUND_OUTPUT_MARKER = b"Output is being written to"     # 호스트 문구(E3) — 줄 선별 표지

@dataclass(frozen=True)
class ToolKindCounts:
    read: int = 0
    edit: int = 0
    run: int = 0
    delegate: int = 0
    other: int = 0

@dataclass(frozen=True)
class BackgroundOutputView:
    file_count: int          # 지금 존재하는 정규 파일 수 1..BACKGROUND_OUTPUT_MAX_FILES
    updated_at_ms: int       # 그 파일들 st_mtime 최댓값(ms)
    total_bytes: int         # st_size 합

@dataclass(frozen=True)
class SubagentActivity:
    last_record_at_ms: int                          # 창 안 마지막 기록의 timestamp
    last_tool_kind: ToolKind | None                 # 창 안 마지막 tool_use 의 종류
    pending_count: int                              # 결과가 아직 없는 tool_use 수
    pending_tool_kind: ToolKind | None              # 그중 가장 오래된 것의 종류 (pending_count == 0 ⇔ None)
    pending_since_ms: int | None                    # 그 시각 (pending_count == 0 ⇔ None)
    recent_tool_counts: ToolKindCounts              # [recent_counts_since_ms, last_record_at_ms] 의 tool_use 수
    recent_counts_since_ms: int                     # 개수 범위 하한(LA5)
    stall_suspect_at_ms: int | None = None          # hub_session 이 채운다(LA8). pending 이 있으면 None
    background_output: BackgroundOutputView | None = None   # I/O 층이 채운다(LA6·LA7)

@dataclass(frozen=True)
class LiveActivity:
    """수집 1회의 활동 판독 — hub_collect → hub_project → hub_session 의 통로(뷰가 아니다, 직렬화되지 않는다)."""
    by_agent_id: Mapping[str, SubagentActivity]
    background_output_by_session_id: Mapping[str, BackgroundOutputView]

def classify_tool_kind(tool_name: object) -> ToolKind: ...
def parse_tool_activity(window: bytes) -> SubagentActivity | None: ...
def background_output_paths(window: bytes, session_id: str) -> tuple[str, ...]: ...
def summarize_background_outputs(file_stats: Sequence[tuple[int, int]]) -> BackgroundOutputView | None: ...
def with_stall_suspect_at(activity: SubagentActivity, run_started_at_ms: int) -> SubagentActivity: ...
```

- 50줄 한도: `parse_tool_activity` 는 `_json_lines(window)`·`_tool_events(payload)`·`_pending_calls(uses, results)`·
  `_recent_counts(uses, since_ms)` 로 쪼갠다. `background_output_paths` 는 `_tool_result_texts(payload)`·
  `_valid_output_path(text, session_id)` 로.
- `background_output_paths` 의 반환은 **내부 값**이다 — I/O 층이 lstat 에만 쓰고 어떤 dataclass 에도 담지 않는다.

### 7.2 `hub/bin/hub_subagent_read.py` (I/O, 추가)

```python
def read_live_activity(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    projects_dir: Path,
    now_ms: int,
    unfinished_activity_by_agent_id: Mapping[str, int],   # read_unfinished_subagent_activity 의 결과(SL mtime)
) -> hub_activity.LiveActivity:
    """도는 실행의 활동(안 A + 실행 줄 출력)과 백그라운드 대기 후보 세션의 출력 요약(안 B)을 읽는다. 예외를 던지지 않는다."""

# 사적 헬퍼
def _read_tail_bytes(path: Path, max_bytes: int) -> bytes | None: ...                 # seek+read, OSError → None
def _read_subagent_window(session_id, observed_cwds, agent_id, projects_dir) -> bytes | None: ...
def _running_agent_ids(facts, now_ms, unfinished_activity_by_agent_id) -> tuple[str, ...]: ...   # LA2
def _activity_for_run(facts, agent_id, projects_dir) -> SubagentActivity | None: ...
def _stat_output_files(paths: Sequence[str]) -> tuple[tuple[int, int], ...]: ...       # lstat + S_ISREG
def _background_output_for_session(facts, projects_dir) -> BackgroundOutputView | None: ...       # LA7
```

### 7.3 `hub/bin/hub_session.py` (★순수, 수정)

```python
@dataclass(frozen=True)
class BackgroundWait:
    ...                                           # 기존 4필드 그대로
    output: BackgroundOutputView | None = None     # 맨 뒤, LA10. 개정: 「정적 값만」은 이 필드에 한해 "파일 stat 의 함수"

@dataclass(frozen=True)
class SubagentRunView:
    ...                                           # 기존 필드 그대로
    activity: SubagentActivity | None = None       # 맨 뒤, LA9. is_running 일 때만 채워진다

def waking_background_task_count(report: BackgroundReport | None) -> int: ...      # effective_background_wait 가 재사용
def is_background_output_scan_target(facts: SessionFacts, now_ms: int,
                                     max_age_ms: int = BACKGROUND_WAIT_MAX_MS) -> bool: ...   # LA7 게이트
def effective_background_wait(facts, now_ms, roster, max_age_ms=BACKGROUND_WAIT_MAX_MS,
                              output: BackgroundOutputView | None = None) -> BackgroundWait | None: ...
def summarize_agent_runs(facts, now_ms, zombie_after_ms=..., subagent_meta_by_agent_id=None,
                         previous_task_boundary_ms=None, subagent_activity_by_agent_id=None,
                         activity_by_agent_id: Mapping[str, SubagentActivity] | None = None,
                         ) -> tuple[SubagentRunView, ...]: ...
def compute_session_view(..., transcript_turn_failure=None,
                         live_activity: LiveActivity | None = None) -> SessionView: ...
```

`summarize_agent_runs` 의 붙이기(한 줄 술어 — T25-272 가 문다):
`activity = with_stall_suspect_at(found, started_at_ms) if is_running and found is not None else None`
(`found = activity_by_agent_id.get(sub.agent_id)`, `started_at_ms` 는 뷰와 같은 값 — meta 우선, AR7).

### 7.4 배선

- `hub_collect._read_session_annotations(sessions_by_path, record_prompt_excerpt, now_ms)` — SL mtime 을 읽은 **다음 줄**에서
  `hub_subagent_read.read_live_activity(sessions_by_path, PROJECTS_DIR, now_ms, subagent_activity_by_agent_id)` 를 부르고
  반환 튜플 끝에 `live_activity` 를 더한다(`record_prompt_excerpt` 를 넘기지 않는다 — T25-272). `collect_snapshot` 이
  `now_ms` 를 넘기고 결과를 `compose_project_views(..., live_activity)` 에 전달.
- `hub_project.compose_project_views` → `_project_view_for_path` → 세션 뷰 함수 → `compute_session_view(live_activity=...)`
  — 판단 없이 통과(SL6 과 같은 모양). 기본값 `None` 이라 기존 호출부·테스트는 무해하다.

### 7.5 `#dzh-data` JSON (추가분만)

```json
"agent_runs": [{ "...기존 키...": "…",
  "activity": null | {
    "last_record_at_ms": 1791370260000, "last_tool_kind": "read",
    "pending_count": 1, "pending_tool_kind": "run", "pending_since_ms": 1791370020000,
    "recent_tool_counts": {"read": 6, "edit": 2, "run": 3, "delegate": 0, "other": 0},
    "recent_counts_since_ms": 1791370020000, "stall_suspect_at_ms": null,
    "background_output": null | {"file_count": 1, "updated_at_ms": 1791370200000, "total_bytes": 49152}
  }}],
"background_wait": null | { "since_ms": …, "until_ms": …, "task_count": 1, "wakeup_count": 0,
  "output": null | {"file_count": 1, "updated_at_ms": …, "total_bytes": 1258291} }
```

하위호환: 키가 없는 옛 페이로드는 `undefined` → 「없음」과 같은 경로(오늘 화면). 새 템플릿·옛 서버 조합은 템플릿 세대 자가
리로드(SH6~SH9)가 정리한다. 문자열 값은 `ToolKind` 리터럴 5종뿐이다.

---

## 8. 화면

### 8.1 변경 전 / 후 (텍스트 목업, 320px 카드)

```
현재                                              제안
┌ coding-harness   티어1 ●작업중  방금 ┐          ┌ coding-harness   티어1 ●작업중  방금 ┐
│ └●작업중 1시간 11분 소요         │          │ └●작업중 1시간 11분 소요         │
│   시작 13:20 7c2e91d4 Opus 5     │          │   시작 13:20 7c2e91d4 Opus 5     │
│   ├ 구현 허브 실행 중… 2/4 · 50%  │          │   ├ 구현 허브 실행 중… 2/4 · 50%  │
│   └ [구현] 허브 활동 표시…   29분 │          │   └ [구현] 허브 활동 표시…   29분 │
│     [검수] 파서 1회차 검수    6분 │          │     명령 실행 중 · 4분째 · 출력 1분 전
│     [설계] 허브 활동 표시 설계 38분│          │     [검수] 파서 1회차 검수    6분 │
└──────────────────────────────────┘          │     마지막 기록 방금 · 읽기          │
                                              │     [설계] 허브 활동 표시 설계 38분│  ← 끝난 실행: 변화 없음
                                              └──────────────────────────────────┘

새 기록 없음(실행 줄만 주황, 배지·glow·정렬 그대로)     백그라운드 대기
│     [구현] 대시보드 표 정렬 수정  33분 │            │ └◐백그라운드 대기 1시간 26분 소요 출력 1분 전 갱신
│     ▲ 12분째 새 기록 없음           │            │   (실행 줄은 BW7 대로 전부 「종료」)
```

> **개정(2026-10-07)** — 위 「제안」 목업은 활동 줄이 칩 왼쪽에 서는 옛 모양이다. 구현은 활동 줄 왼쪽을 제목 왼쪽에 맞춘다(LA9 개정).

### 8.2 문구 표 (비개발자 기준)

| 자리 | 문구 | 비고 |
|---|---|---|
| 진행 중 | `명령 실행 중 · 4분째` · `읽는 중 · 방금 시작` · `다른 에이전트 기다리는 중 · 12분째` · `명령 실행 중 외 1건 · 4분째` | 종류 5값 |
| 도구 사이 | `마지막 기록 방금 · 읽기` · `마지막 기록 3분 전 · 실행` | |
| 새 기록 없음 | `▲ 12분째 새 기록 없음` | `--attention` 글자색 |
| 실행 줄 출력 | 꼬리 ` · 출력 1분 전` | |
| 세션 출력 | `출력 1분 전 갱신` | 백그라운드 대기 첫 줄 끝 |
| 툴팁 | §6 LA9·LA10 | 개수·크기는 툴팁에만 |

### 8.3 배지 우선순위와의 관계

`작업중 > 한도 초과 > 백그라운드 대기 > 대기 > 소식 없음 > 완료` 는 **불변**. 「새 기록 없음」은 작업중 세션 안 한 실행 줄의
주석이고 세션·프로젝트 배지·정렬·glow 에 반영되지 않는다(LA8). 백그라운드 대기 배지의 출력 표시는 라벨을 바꾸지 않는 꼬리다.
한도 초과(interrupted) 세션에서도 도는 서브에이전트 줄의 활동은 그대로 보인다(칩과 같은 질문 — README 「좀비 가드」 문단의
기존 예외와 같은 성질).

### 8.4 프리뷰 목업

- `<세션 스크래치패드>/mock/hub-live-activity-mock.html`
  (독립 실행, 외부 의존성 0) · 렌더: 같은 폴더 `hub-live-activity-mock.png`(1680×3950 전체), `zoom-320.png`(320px 열 2배 확대).
- **목업 화면의 「멈춘 것 같음」 문구는 구버전이다** — 구현은 §8.2 의 「▲ 12분째 새 기록 없음」을 따른다(승인 때 변경).
- 목업의 활동 줄 배치(flex-wrap, 칩 왼쪽부터)도 구버전이다 — 구현은 LA9 개정(grid, 제목 왼쪽 맞춤)을 따른다. 폭이 큰 폴백 칩(agent_type 12자 + 말줄임)이면
  320px 에서 활동 줄이 말줄임될 수 있다 — 한 줄은 유지되고 전체 문구는 행 툴팁에 있다.
- `<style>` 앞부분은 `hub_template.html` 의 `<style>` 블록을 글자 그대로 복사했고, `[제안 LA9]·[제안 LA10]` 주석 규칙이 구현이
  더할 CSS 와 같은 글자다. 마크업은 `renderAgentRunRow`·`renderSessionContent`·`renderStateBadge` 와 같은 클래스·구조.
  목업 전용 장치는 `.mock-*`(격자·장면 제목·한 페이지 두 테마용 `.mock-dark`·툴팁 고정 펼침 `.mock-static-tooltip`·hover 재현).
- 장면 3개(도는 실행 2 + 끝난 실행 1 / 새 기록 없음 / 백그라운드 대기) × 「현재 | 제안」 × 320px·460px × 라이트·다크, hover(행
  배경 + 툴팁) 상태 포함. 확인된 것: 320px 에서 칩·제목·경과가 한 줄을 유지하고 제목 말줄임이 산다 · 활동 줄은 한 줄에 들어간다 ·
  백그라운드 대기 첫 줄이 320px 한 줄에 들어간다 · 340px 고정 카드에서 도는 실행 1건당 약 15px 늘어 내부 스크롤이 조금 일찍 시작된다.

---

## 9. 개인정보

### 9.1 읽는 필드 화이트리스트

| 출처 | 읽는 필드 | 용도 | 메모리 밖으로 나가는가 |
|---|---|---|---|
| `agent-<id>.jsonl` 끝 256KiB(전량) | 줄 `type`·`timestamp` · `message.content[].type` · `tool_use.id`·`tool_use.name` · `tool_result.tool_use_id` | 시각·종류·짝 맞추기 | 시각·종류(5값)·개수만 |
| `agent-<id>.jsonl` 끝 1MiB · 메인 `<sid>.jsonl` 끝 1MiB(표지 줄만) | `type` · `message.content[].type` · `tool_result.content`(문자열 또는 `text` 블록의 `text`) | 출력 경로 찾기(LA6) | **없음** — 경로는 lstat 에만 쓰고 버린다 |
| `<…>/<sid>/tasks/<id>.output` | `lstat` 의 모드·`st_mtime`·`st_size` | 출력 갱신·크기 | 시각·크기·파일 수만. 파일은 열지 않는다 |

읽지 않는 것(키 리터럴 자체가 모듈에 없다): `input`(명령·파일 내용), `toolUseResult`(stdout 등), `description`, `prompt`,
`thinking`, assistant `text`. `tool_result` 본문은 메모리에서 문구 검색에만 쓰이고 어떤 값으로도 남지 않는다 — 재개 요청
본문(`message`)에 대한 README 의 기존 서술(「줄을 해석하는 동안 메모리에 올라오지만 어디에도 싣거나 저장하지 않는다」)과
같은 성질이다.

### 9.2 스냅샷에 나가는 값(전부)

정수: `last_record_at_ms`·`pending_count`·`pending_since_ms`·`recent_tool_counts.{read,edit,run,delegate,other}`·
`recent_counts_since_ms`·`stall_suspect_at_ms`·`file_count`·`updated_at_ms`·`total_bytes`. 닫힌 리터럴: `last_tool_kind`·
`pending_tool_kind`(5값). 그 밖의 문자열·경로·도구 이름·명령·출력 0.

### 9.3 구조 가드와 깨뜨려 확인하는 방법

| 가드(잠정) | 무엇을 | 의도적으로 깨뜨리는 방법(변조행 / 단위 RED) |
|---|---|---|
| **T25-269 읽기 화이트리스트** | `hub_activity.py` 의 키 접근 리터럴(`.get("…")`·`["…"]`) 전부가 `{type, timestamp, message, content, id, name, tool_use_id, text}` 안 + 역방향: `"input"`·`"toolUseResult"`·`"stdout"`·`"description"`·`"prompt"`·`"command"` 리터럴 0건 | 변조행: `classify_tool_kind(block.get("name"))` 에 `or block.get("input")` 을 끼운다 → 실패 토큰 `화이트리스트 밖 키 리터럴`(5열 토큰은 보고 줄 1건이어야 해 ID 가 아니라 문구다 — 아래 둘도 같다) |
| **T25-270 출력 구조** | `ToolKindCounts`·`BackgroundOutputView`·`SubagentActivity` 클래스 본문에 `str` 주석 0건(`ToolKind` 리터럴만 허용). 단위 `ActivityContractTest`: `typing.get_type_hints` 를 재귀로 걸어 잎 타입이 `int`·`NoneType`·`ToolKind`·위 세 클래스뿐임을 단정 | 변조행: `SubagentActivity.last_tool_kind` 의 주석 `ToolKind \| None` 을 `str \| None` 으로 푼다 → `필드에 자유 문자열(str) 주석이 있음` · 단위도 RED |
| **T25-271 지금 시각 없음** | `hub_activity.py` 에 `now_ms`·`time.`·`.now(` 토큰 0건(활동 값 = 파일 내용의 함수, LA11) | 변조행: `parse_tool_activity(window: bytes, now_ms: int)` → `지금 시각 토큰` |
| 카나리(단위 `test_hub_model.LiveActivityCanaryTest`) | 합성 기록: `tool_use.input` 에 `SENTINEL-CMD`, `tool_result` 에 `SENTINEL-OUT` + 유효 출력 경로, 도구 이름 `mcp__SENTINELSRV__x`, assistant `text` 에 `SENTINEL-TXT` → `read_live_activity` → `compose_project_views` → `render_hub_html` 결과에 `SENTINEL`·`/tasks/`·`.output` 0건 | 구현 중 한 번: 뷰에 경로를 담는 임시 필드를 넣어 RED 를 확인한 뒤 되돌린다(T25-270 이 정적으로도 막는다) |

T25-249(훅 쪽 문자 수준 가드)는 무수정 — 훅은 바뀌지 않는다.

### 9.4 고지 문구(문서 갱신 — §11)

- README 「프라이버시 고지」 서브에이전트 항목의 「그 에이전트의 대화 기록(`agent-<id>.jsonl`)은 **읽지 않는다.**」를 개정:
  「**지금 도는** 실행에 한해 대화 기록 끝 1MiB 를 수집 때마다 읽어 도구 이름(읽기·수정·실행·위임·기타로만 접는다)·기록
  시각·도구 호출과 결과의 짝, 그리고 도구 결과에 적힌 백그라운드 출력 파일 경로만 쓴다. `hub.html` 에는 시각·개수·종류·
  출력 파일 수·크기만 실리고 명령·출력·설명 텍스트와 경로는 싣지 않는다. 출력 파일은 열지 않고 수정 시각·크기만 본다.
  끄는 스위치는 없다.」
- 메인 transcript 항목: 「백그라운드 대기 중인 세션은 같은 파일 끝 1MiB 에서 도구 결과에 적힌 출력 파일 경로만 한 번 더
  찾는다(경로는 싣지 않는다)」.
- 「정수 4개」 서술 → 「정수 4개 + (출력이 확인되면) 정수 3개」.
- `commands/hub.md` 설치 고지 ① 끝: 「도는 서브에이전트의 대화 기록 끝과 백그라운드 작업 출력 파일의 수정 시각·크기를 읽어
  진행 상황(도구 종류·시각·개수)만 표시합니다 — 명령·출력 내용은 기록하거나 표시하지 않습니다.」

---

## 10. 테스트 계획

전부 합성 픽스처(테스트 안에서 `json.dumps` 로 줄을 만든다). 실제 경로·프롬프트·기록을 픽스처·이미지에 넣지 않는다.
AAA 구조, `unittest`.

### 10.1 `tests/hub/test_hub_activity.py` (신설, ★순수)

| ID | 입력 | 기대 |
|---|---|---|
| LA-K1 | 표의 이름 각각 / `"Unknown"` / `"mcp__a__b"` / `None`·`3` | 해당 종류 / `other` ×3 |
| LA-P1 | 빈 창 · 시각 없는 줄만 | `None` |
| LA-P2 | thinking·text 줄만(도구 블록 0) | `None`(LA12) |
| LA-P3 | tool_use(Read) + 짝 결과 | pending 0, `last_tool_kind="read"`, counts.read 1 |
| LA-P4 | tool_use(Bash) 결과 없음 | pending 1, kind `run`, since = 그 줄 시각, `last_tool_kind="run"` |
| LA-P5 | 병렬 tool_use 3개 중 결과 1개 | pending 2, kind·since = 더 오래된 것 |
| LA-P6 | 결과만 있고 use 는 창 밖 | pending 0, 예외 없음 |
| LA-P7 | 창 머리 찢긴 줄 + 끝 찢긴 결과 줄 | 예외 없음, 그 호출은 pending |
| LA-P8 | 형태 위반: `message` 가 리스트, `content` 문자열, 블록 비-dict, `name` 정수, `id` 없음, `timestamp` 정수, 깊은 중첩 줄 | 예외 없음(계약 B), 위반 블록만 무시 |
| LA-P9 | 같은 id 의 tool_use 줄 2번(재부착) | 한 번만 센다 |
| LA-P10 | use 시각 last−11분·last−9분·last, 창 첫 기록 last−20분 | counts 2, `recent_counts_since_ms = last−10분`; 창 첫 기록이 last−3분이면 하한 = 그 시각 |
| LA-P11 | 마지막 줄이 attachment(도구 아님) | `last_record_at_ms` = 그 줄 시각 |
| LA-P12 | `"…Z"` 시각 | 3.10 에서도 파싱(공개 함수 재사용 확인) |
| LA-B1 | user 줄 tool_result 문자열 본문에 `Command running in background with ID: abc. Output is being written to: /t/x/<sid>/tasks/abc.output` | `("/t/x/<sid>/tasks/abc.output",)` |
| LA-B2 | 같은 본문이 `text` 블록 리스트 | 같은 결과 |
| LA-B3 | 문구가 사람 프롬프트 text 블록 · assistant text · tool_use `input` 안 | `()` (E4) |
| LA-B4 | 조부모 ≠ sid / 부모 ≠ `tasks` / `ID: abc` 없음 / 상대경로 / `..` 조각 / 줄기에 공백·`$` | 각각 `()` |
| LA-B5 | 유효 경로 10개 + 중복 | 중복 제거, 파일에서 뒤의 8개 |
| LA-B6 | 표지 없는 줄 다수 + 표지 줄 1 | 표지 없는 줄은 해석하지 않는다(`_json_object_or_none` 호출 수 = 1, `mock.patch.object`) |
| LA-O1 | `summarize_background_outputs(())` / 값 3개 | `None` / (3, max, sum) |
| LA-S1 | pending 있음 | `stall_suspect_at_ms is None` |
| LA-S2 | pending 없음, 시작 < 마지막 기록 | 마지막 기록 + 10분 |
| LA-S3 | pending 없음, 재개 시작 > 마지막 기록 | 재개 시작 + 10분(P8) |
| LA-C1 | `ActivityContractTest` | 타입 힌트 재귀 — 자유 `str` 없음, 리터럴 = `TOOL_KINDS`, 전부 `frozen` |

### 10.2 `tests/hub/test_hub_subagent_read_activity.py` (tempdir, 신설)

옛 `test_hub_subagent_read.py` 가 800줄 상한을 넘어(2026-10-07) 이 PRP 의 시나리오(`ReadLiveActivityTest`)를 이 새 파일로 분리했다 —
지금 옛 파일에는 이 PRP 가 더한 것이 없다. LA-R10 의 「기존 재개 제목 테스트」는 옛 파일에 그대로 있다. 같은 분리로
`hub-subagent-liveness-signal.md` §7.2 의 `ReadUnfinishedSubagentActivityTest`(SL-R1~R8)도 이 파일로 함께 옮겨졌다.

| ID | 시나리오 | 기대 |
|---|---|---|
| LA-R1 | 도는 실행(jsonl 있음) / 끝난 실행 / 좀비(시작·기록 90분 초과) | 첫째만 `by_agent_id` 에. 끝난·좀비는 파일을 열지 않는다(`_read_tail_bytes` 호출 수) |
| LA-R2 | 1.5MiB 파일, 창 밖(앞)에 결과 없는 tool_use | pending 에 잡히지 않는다(창 1MiB·해석 256KiB) |
| LA-R3 | 실행 창에 유효 경로 + tempdir 에 `<sid>/tasks/abc.output` | `background_output = (1, mtime, size)`; 파일 삭제 후 `None` |
| LA-R4 | 출력 경로가 심볼릭 링크·디렉터리 | 버린다 |
| LA-R5 | 배지 후보(보고 30분 전, `bt={"shell":1}`): 메인 + 20분 전 종료 실행에 경로 | `background_output_by_session_id[sid]` 합산 |
| LA-R6 | 보고 91분 전 / `bt={"subagent":1}` 만 / 보고 없음 | 메인 기록을 열지 않는다(읽기 호출 0) |
| LA-R7 | 종료 실행 10개 | 최근 종료 8개만 읽는다 |
| LA-R8 | 권한 거부·없는 파일 | 예외 없음, 해당 키 없음 |
| LA-R9 | `session_id`·`agent_id` 에 `/`·`..` | 조립 전에 건너뛴다 |
| LA-R10 | 기존 재개 제목 테스트(`RESUME_TITLE_SCAN_MAX_BYTES` 패치) | **무수정 통과**(GOTCHA 1 회귀) |

### 10.3 `test_hub_session.py`·`test_hub_project.py`·`test_hub_collect.py`·`test_hub_model.py`·`test_hub_transcript.py`

- LA-V1 `summarize_agent_runs`: 도는 실행에만 `activity`, 끝난·좀비 실행은 dict 에 있어도 `None`.
- LA-V2 `stall_suspect_at_ms` 가 `with_stall_suspect_at` 경유로 채워진다(뷰의 `started_at_ms` 사용).
- LA-V3 `compute_session_view(live_activity=None)` 의 `asdict` 가 **오늘과 동일**(회귀) — 기존 표 기반 테스트 전부 무수정 통과.
- LA-V4 `background_wait.output` 은 `state == "background"` 일 때만, 그 밖엔 `background_wait` 자체가 `None`(BW9 불변식 유지).
- LA-V5 멈춤 의심 활동이 있어도 `state`·`base_state`·`PROJECT_STATE_PRIORITY` 결과 불변(LA8).
- LA-V6 `waking_background_task_count` 리팩터 동등성 — 기존 BW 표(L·E) 무수정 통과. `is_background_output_scan_target` 경계(`>=` 만료).
- LA-V7 SL-U10 무수정 통과(SL mtime 이 뷰에 새지 않음).
- LA-PJ1 `compose_project_views(live_activity=…)` 가 세션 뷰까지 전달.
- LA-CL1 `_read_session_annotations` 가 `live_activity` 를 돌려주고 `read_live_activity` 에 `record_prompt_excerpt` 를 넘기지 않는다;
  LA-CL2 `collect_snapshot` 이 `now_ms`·결과를 전달(`mock.patch.object`).
- LA-M1 카나리(§9.3). LA-M2 `snapshot_content_key` — `live_activity` 없음과 빈 `LiveActivity` 가 같은 키, 활동 시각만 다르면 다른 키.
- LA-T1 `epoch_ms_from_iso8601` 공개 이름으로 기존 "Z" 회귀 테스트 통과.

### 10.4 DOM (`tests/hub/test_hub_template_dom_activity.py`, 기존 하네스, Chrome 없으면 SKIP)

D-LA1 진행 중 → `.agent-run-activity` 문구 · D-LA2 `now` 가 `stall_suspect_at_ms` 전/후 → 일반/`agent-run-activity-stall` ·
D-LA3 키 없는 옛 페이로드 → `.agent-run-activity`·modifier 0개(오늘 마크업) · D-LA4 끝난 실행에 activity 가 있어도 줄 없음 ·
D-LA5 백그라운드 대기 + output → `.session-activity`, 툴팁에 「작업 출력은」 · output 없음 → span 없음 · D-LA6 320px 트랙에서
칩·제목·경과의 `offsetTop` 이 같고 제목 `scrollWidth > clientWidth`(말줄임)(개정 2026-10-07: 활동 줄 `left` 가 같은 행 제목 `left` 와 같다 —
칩 폭이 다른 두 행을 카드 목록(320px)·상세보기에서 `HubActivityAlignmentDomTest` 가 잰다) · D-LA7 행 툴팁에 「이후 도구 —」 줄 · D-LA8 모달 세션
카드에도 같은 줄(공유 조각). 메모리 「DOM 테스트는 동시 부하에 약하다」 — 전체 스위트와 겹쳐 돌리지 않는다.

### 10.5 `tests/run.sh` (T25, 전부 잠정 번호 — 현재 최대 T25-268)

| ID | 검사 |
|---|---|
| T25-269 | 읽기 화이트리스트(§9.3) |
| T25-270 | 출력 구조(§9.3) |
| T25-271 | `hub_activity.py` 에 지금 시각 토큰 없음(§9.3) |
| T25-272 | 배선: `def read_live_activity(` 존재 · 그 시그니처와 `_read_session_annotations` 의 호출에 `record_prompt_excerpt` 없음(SL7 의 함정) · `summarize_agent_runs` 본문에 `if is_running and found is not None` 술어 |
| T25-273 | README ↔ 상수: 고지의 「끝 1MiB」·임계 「10분」이 `ACTIVITY_WINDOW_BYTES`·`SUBAGENT_STALL_SUSPECT_AFTER_MS` 와 같다(T25-261 과 같은 모양) |
| T25-274 | 템플릿: `.agent-run-activity-stall{` 규칙에 `#` 색 리터럴·`animation`·`box-shadow` 0 · `TOOL_KIND_NOUN`·`TOOL_KIND_PENDING_LABEL` 키 집합 == 파이썬 `TOOL_KINDS`(T25-219 처럼 양쪽에서 뽑아 대조) · `renderAgentRunRow` 가 `renderAgentRunActivity(` 를 부른다 |

개정: **T25-10** 목록에 `hub_activity.py`(★순수) · **T25-93** 템플릿의 `run.is_running` 참조 수 3 → 4(M4 — 활동 줄과 행 툴팁 줄이
`runningActivityOf(run)` 한 곳에서 같은 판정을 공유하므로 새 참조는 그 한 곳뿐이다. 각자 읽으면 5가 된다. 기대값과 주석을 고쳤다) ·
**T25-104·T25-149** 31 → 32(역방향 「31개 파일」 잔존 검사 추가) ·
`SOURCE_GUARD_ID_FLOOR` 531 → 537(상수 주석에 사유) · `LEDGER_MUTATION_ROW_FLOOR` 108 → 114 · 원장 머리의
`LEDGER_MUTATION_ROW_FLOOR(…)`·`SOURCE_GUARD_ID_FLOOR(…)` 인용과 T99-6 변조행의 sed 리터럴(「(108」→「(114」, 대체값 「(118」)도 함께(T99-6 이
대조한다 — 반복된 함정). 변조행 6개(T25-269~274, 8열 TSV, `/` 구분자, `w`·`W`·`r`·`R`·`e` 금지, 5열 토큰은 실패 보고 줄에서 1건만).

**구현 반영(M5, 2026-10-07)**: 번호 269~274 는 이 작업 폴더 기준 확정이고 병합 직전 main 에서 다시 센다. 숫자는 `collect_guard_ids` 를
그대로 재현해 측정했다 — 소스 가드 ID 531 → 537(차집합이 정확히 +T25-269~274), 원장 변조행 227 → 233(순증가 6, 면제행 311 은 래칫
372 아래). 하위 검사 구성은 표와 조금 다르다: T25-269 는 정방향(키 리터럴 정규식은 `.get("…"` 첫 인자와 `["…"]` — 닫는 `]` 까지 맞춰 `ToolKind =
Literal["read", …]` 를 피한다) + 역방향(금지 리터럴 6종) + 추출 0건 앵커 실패, T25-270 은 클래스 본문 전체가 아니라 세 클래스의 **필드 줄**(줄 끝
주석을 뗀다)만 본다, T25-273 은 ① 「끝 **N MiB**」(T25-261 의 「끝에서 최대 **N MiB**」와 겹치지 않는 형태) ② 「**N분** 넘게 비」 ③ 옛 「읽지 않는다」
약속 부활 금지 세 가지이고 코드 상수는 새 헬퍼 `read_python_product_constant`(정수 곱 한 줄만 읽어 단위로 나눈다 — `1024 * 1024`·`10 * 60 * 1000`
형태가 깨지면 불일치로 보고)로 읽는다, T25-274 의 ② 는 두 표 키 집합과 `TOOL_KINDS` 를 정렬해 대조한다(순서는 보지 않는다). 변조행은 T37 대신 스크래치
미러 개별 검증으로 6행 모두 ① sed 가 정확히 1줄을 바꾸고 ② `--only T25` 가 실패하고 ③ 토큰이 출력에 나옴을 확인했다(T37 은 메인이 커밋 직전에 돌린다).
행이 직접 물지 않는 하위 검사 12개도 같은 방식으로 각각 깨뜨려 발화함을 확인했다.

### 10.6 성공 기준

| # | 기준 | 검증 |
|---|---|---|
| G1 | 도는 실행 줄에 진행 중 도구·마지막 기록이 보인다 | D-LA1, LA-R1 |
| G2 | 10분+ 공백·진행 중 호출 없음일 때만 「새 기록 없음」, 상태 사다리 불변 | LA-S1~S3, LA-V5, D-LA2 |
| G3 | 백그라운드 대기 세션에 출력 갱신 시각 | LA-R5, D-LA5 |
| G4 | 스냅샷에 텍스트·경로·도구 이름 0 | T25-269·270, LA-M1 |
| G5 | 읽기 실패·형식 변화 → 오늘 화면 | LA-P1·P2·P8, LA-R8, D-LA3, LA-V3 |
| G6 | 아무것도 안 돌 때 `snapshot_content_key` 오늘과 동일 | LA-M2, T25-271 |
| G7 | `collect_snapshot` < 50 ms | 구현 M2 실측 |

---

## 11. 문서 갱신 범위

- `hub/README.md` — 「프라이버시 고지」 3곳(§9.4) · 「화면 배치」에 활동 줄·새 기록 없음 규칙(「허브는 멈춤을 단정하지 않는다」,
  임계 10분, 실행 줄에만)·백그라운드 대기 출력 줄 · 툴팁 목록 문단(실행 줄 툴팁에 활동 줄, 배지 툴팁에 출력 줄) · 「알려진 한계」
  4항(호스트 기록 형식 의존 — 바뀌면 활동 줄이 사라진다 / 도구 개수는 기록 끝 일부만 / 출력 파일은 기록 끝 1MiB 안에서 띄운
  것만 / 조용한 명령은 출력이 끝에만 늘 수 있다) · 「파일 배치」 32개·`hub_activity.py`(70행·862행 두 곳).
- `commands/hub.md` 설치 고지 ① 한 문장(§9.4).
- `docs/prps/hub-dashboard.md` 모듈 구성표에 `hub_activity.py` 한 줄.
- `docs/prps/hub-subagent-background-pause.md` — N4·BW9 옆에 개정 블록(출력 파일 stat 을 **판정이 아닌 표시**에 쓴다, `output`
  필드는 파일 stat 의 함수). `docs/prps/hub-subagent-liveness-signal.md` — SL5 옆 개정 블록(SL5 는 유지, 활동 값은 별도 통로로
  `SubagentRunView` 에만, `SessionView` 무변경). 원문 삭제 금지(GOTCHA 10 관례).

---

## 12. 구현 순서와 규모

| 단계 | 내용 | 검증 |
|---|---|---|
| **M0** | 측정(코드 없음): 같은 48건 10분+ 공백을 LA8 규칙에 재생 → 오탐 0 확인, 임계 확정. 결과를 이 PRP §6 LA8 에 한 줄로 | 오탐 0. 아니면 사용자에게 보고 후 임계·규칙 재제안 |
| **M1** | `epoch_ms_from_iso8601` 공개화 · `hub_activity.py` + `test_hub_activity.py`(TDD) · T25-10 목록 · 파일 수 31→32(install.sh·README 2곳·T25-104·T25-149·hub-dashboard.md) | 4개 검증 명령 |
| **M2** | `hub_subagent_read.read_live_activity` + 헬퍼 + 테스트 · `hub_session` 의 두 순수 헬퍼(I/O 게이트가 쓴다) | LA-R*, 기존 재개 테스트 무수정, 실기 `collect_snapshot` 시간 측정(G7) |
| **M3** | `hub_session` 뷰·배선 · `hub_project`·`hub_collect` 통과 · 카나리 | LA-V*·LA-CL*·LA-M* · 기존 스위트 무수정 통과 |
| **M4** | 템플릿 CSS·JS · DOM 테스트 · 목업과 실화면 대조(메모리 「허브 CSS 시각 확인」 — 실데이터 생성물의 style 만 갈아끼워 로컬 서빙) | D-LA* 단독 실행 |
| **M5** | README·commands/hub.md·PRP 개정 블록 · T25-269~274 · 변조행·바닥값 | `bash tests/run.sh` 전체, 변조행 6개 검출 확인 |

규모: 파이썬 소스 약 +420(신설 ~240 포함) · 템플릿 약 +110 · 테스트 약 +1,000 · run.sh 약 +170 · 문서 약 +45.

GOTCHA:
1. **재개 제목 테스트는 `hub_subagent_read.RESUME_TITLE_SCAN_MAX_BYTES` 를 `mock.patch.object` 로 바꾼다.** 기존 함수에 기본값
   매개변수 `max_bytes=RESUME_TITLE_SCAN_MAX_BYTES` 를 더하면 기본값이 정의 시점에 묶여 패치가 무력해진다 — 기존 함수 시그니처는
   그대로 두고 본문만 `_read_tail_bytes(path, RESUME_TITLE_SCAN_MAX_BYTES)`(호출 시점에 모듈 전역을 읽는다)로 바꾼다.
2. T25-10 은 ★순수 파일에서 `open(`·`Path(`·`os.` 를 **주석까지** 잡는다 — `hub_activity.py` 의 주석·docstring 에 `os.lstat`
   같은 표기를 쓰지 않는다(「lstat」만).
3. T25-225 역방향은 `SessionView` 본문의 `activity` 문자열을 잡는다 — `SessionView` 에 필드·주석을 더하지 않는다.
4. `hub_collect.py` 766/800(T25-100) — 배선만, 5줄 안팎. 넘칠 기미면 멈추고 보고.
5. `SubagentRunView.activity`·`BackgroundWait.output` 은 **맨 뒤·기본값 `None`** — 기존 생성 지점(테스트 포함)이 무해해야 한다.
   T25-150 은 `SessionView` 만 문다(무영향).
6. 개명 전 옛 이름으로 run.sh·원장을 grep 한다(메모리 「개명하면 정적 가드가 눈이 먼다」) — `_epoch_ms_from_iso8601` 은 설계 시점
   테스트 docstring 1곳뿐이었다.
7. `python3 -B` 로 임포트한다(메모리 — `__pycache__` 가 commands 파일 수를 흔든다). `python3 hub/bin/hub.py collect` 금지
   (실제 `hub.html` 을 덮는다).

---

## 13. 리스크와 대안

| # | 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|---|
| R1 | 호스트 기록 형식 변경(블록·문구) | 중 | 활동 줄·출력 줄이 조용히 사라진다 | fail-open(LA12) · README 알려진 한계 · 합성 픽스처로 형식 가정을 테스트에 명문화 |
| R2 | 「새 기록 없음」 오탐(긴 생각·API 재시도 대기) | 낮음~중 | 불필요한 걱정 | M0 재생 · 사실만 적는 문구(원인 단정 없음) · 실행 줄에만 · 상태 불변 |
| R3 | D2 — 도는 동안 매 수집 `hub.html` 다시 쓰기 | 확정 | 분당 280KB 쓰기 1회 안팎 | LA11 수치 · 아무것도 안 돌면 오늘과 같다 |
| R4 | 수집 비용 | 낮음 | 50 ms 초과 | LA15 예산 · 에스컬레이션(캐시) |
| R5 | 메모리에 올라오는 내용이 늘어난다 | 확정 | 고지 변경 필요 | 화이트리스트·구조 가드·카나리 · 고지 개정(쟁점 1) |
| R6 | 출력 귀속 누락(창 밖·재배치 7/157) | 중 | 출력 줄 없음 | fail-open 방향 · 「확인된」 문구 |
| R7 | 340px 카드에서 보이는 세션 수 감소 | 중 | 스크롤이 조금 일찍 | 도는 실행에만(보통 1~3줄) · 목업 확인 |
| R8 | 동시 세션과 번호·파일 수 충돌 | 중 | 병합 충돌 | 전부 잠정 · 병합 직전 재계산 |

검토했으나 채택하지 않은 대안:
- **A1. 세션 배지에도 「새 기록 없음」**(배지 접미·카드 표지) — 근거가 휴리스틱인 표시를 배지에 올리면 배지 전체의 신뢰가
  깨지고, 우선순위 사다리·정렬·glow 와의 관계를 새로 정해야 한다. 실행 줄은 카드에 상시 보이므로 이득이 작다(쟁점 2).
- **A2. 도구 개수 창을 1MiB 로 넓혀 "최근 10분"을 채운다** — 해석 비용 약 4배(실행당 ~4 ms), 그래도 아주 바쁜 실행은 못 채운다.
  실제 범위를 문구로 말하는 쪽이 정직하고 싸다(쟁점 5).
- **A3. 세션 `tasks/` 디렉터리 열거**(LA1) — 문구 의존이 없어지지만 호스트 비공개 디렉터리 배치를 재구성해야 한다. 호스트가 문구를
  바꿔 R1 이 현실화하면 후속 후보.

---

## 14. 사용자 승인이 필요한 쟁점

1. **프라이버시 고지 변경** — 지금 README 는 서브에이전트 대화 기록을 「읽지 않는다」고 약속한다. 승인하면 **도는 실행의 기록 끝
   1MiB** 와 **백그라운드 대기 세션의 메인 기록 끝 1MiB** 를 읽게 되고(메모리 안에서만), 화면·`hub.html` 에는 시각·개수·도구 종류·
   출력 파일 수·크기만 나간다. 끄는 스위치는 두지 않는 것이 권고다(대안: 기존 `record_prompt_excerpt:false` 로 함께 끄기).
2. **「새 기록 없음」의 자리** — 권고는 실행 줄에만 주황 한 줄(세션 배지·카드 테두리·정렬은 그대로). 대안은 세션 배지에도 표시(A1).
3. **임계 10분(잠정)** — 구현 첫 단계에서 지난 10분+ 공백 48건을 규칙에 다시 돌려 오탐 0 이면 확정, 아니면 다시 묻는다.
4. **도는 동안 페이지 파일을 수집마다 다시 쓴다** — 약 280KB, 탭 하나면 분당 1회 안팎. 아무것도 안 돌 때는 지금처럼 쓰지 않는다.
5. **툴팁의 도구 개수는 "최근 10분"이 아니라 "14:27 이후"처럼 실제 범위로** 말한다(읽는 범위 256KiB ≈ 바쁜 실행의 3~5분).

승인 기록: 2026-10-07 사용자가 설계를 승인했다 — 쟁점 1~5 는 권고안대로(1 끄는 스위치 없음 · 2 실행 줄에만 · 3 임계 10분 잠정, M0 에서 확정 · 4 수집마다 페이지 재작성 · 5 실제 읽은 범위 표기), 표시 문구는 「새 기록 없음」(사실만).

---

## 15. 검증 명령 (정본 — 프로젝트 `CLAUDE.md` §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

금지: 이 저장소 안에서 `install.sh --scope project` · 실제 `$HOME` 대상 설치 · `python3 hub/bin/hub.py collect`.
