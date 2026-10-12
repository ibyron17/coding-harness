# 허브 세션 목록·카드 대시보드·실행 목록·글로우 결함 4건

- **상태**: **완료(2026-09-17) — 검수 2회차 PASS(지적 0건).** 1회차는 PASS(CRITICAL·HIGH 0 ·
  MEDIUM 2 — 둘 다 테스트 가드 부재)였고, 2회차에서 그 2건을 `tests/run.sh` T25-220 의
  서브체크 ⑥⑦ 로 해소했다. 검수자가 워크트리 사본에 변조를 넣어 두 가드가 실제로 발화함을
  재현했다. 판정은 §10 각 항목 머리에 기록했다.
  네 항목은 권고대로, **승인 항목 2 의 표시 정책만 권고(B 라벨)가 아닌 (A) 숨김으로 결정됐다**
  — 그 선택이 파생시키는 변경(README 개정 · T25-220 앵커 이동 · `shouldRenderSession` 2차 효과의
  명시적 수용)은 §5.4 아래 「(A) 채택 확정」 절이 정본이다. 구현 범위는 §2 표 그대로이고, §13
  완료 기준 1~4는 실행 확인됨(`bash tests/run.sh` 전체·`--only T37` 112쌍 전부 통과 포함).
  **§8.5 「눈으로 확인할 것」 5개 항목은 2026-09-17 16:40 메인 세션이 전부 확인했다** — 살아
  있는 허브(8794)의 `hub.html` 에서 스냅샷 JSON 만 떼어내 이 워크트리의 `hub_template.html` 로
  다시 렌더하는 방식이다(포트 8799, 사용자의 `~/.claude/hub/` 무변경 — `collect_snapshot` 은
  `prune_old_event_files` 부수효과가 있어 쓰지 않았다). 실측: 카드의 `data-dashboard-key` 소멸 +
  카드 전용 사유 문구 · 42분 뒤처진 `working` 이 1분 전 `done` 을 제치고 맨 위(작업중→대기→
  소식없음→완료) · 이전 작업 11건 숨김 후 `+6건 더`(숨긴 건수 미혼입) · `inset 0 0 14px -1px`
  / `2s` 와 열린 카드 `20px -1px` · 카드 폭 296px 에서 실행 행 전부 18px 한 줄·가로 스크롤 없음.
- **기준 커밋**: `735547c` (브랜치 `worktree-hub-session-list-fixes`)
- **목업**(필수 검토): `/private/tmp/claude-501/-Users-dev-private-project-coding-harness/02185cdc-285f-4361-b489-280930a710a9/scratchpad/hub-session-list-and-glow-fixes-mockup.html`
  · 렌더 PNG: 같은 디렉토리의 `mockup-full.png`
  목업의 CSS 는 `hub/bin/hub_template.html` 의 `<style>` 블록을 **한 글자도 고치지 않고** 실었고
  마크업도 `renderProject`·`renderSession` 이 실제로 만드는 구조·클래스와 같다. 목업 전용 장치는
  `.mock-` 접두 하나로 격리했다.
- **기존 결정과의 관계**: FT1~FT7(`hub-ui-4-issues.md` §5)·TR1~TR8(같은 문서 §2)·GN1~GN6·RV1~RV3
  (`hub-session-revival-and-stale-tier1.md`)·AR4~AR11(`hub-agent-runs-and-prompt-source.md`)과
  충돌하지 않는다. **한 건만 재해석**한다 — FT5(§3.6, 인용과 근거 포함).

---

## 0. 요구사항 요약

허브 화면에서 사용자가 신고한 4건을 고친다. (1) 세션 행은 「완료된 이전 작업」이라며 열기를 막는데
**같은 파일**이 프로젝트 카드 클릭으로는 그대로 열린다. (2) 세션 목록이 시간 내림차순뿐이라 **방금
끝난 세션이 진행 중인 세션 위**를 차지하고, 카드 높이가 340px 고정이라 진행 중 세션이 접힌 자리로
밀려 보이지 않는다. (3) 끝난 작업의 서브에이전트 실행 목록이 **새 작업을 시작한 뒤에도 그대로 남아**
새 작업의 것처럼 읽힌다. (4) 작업중 카드 글로우의 `box-shadow` spread 를 `-1px`, 주기를 `2s` 로
바꾼다. 1~3 은 「보이는 것과 사실이 어긋난다」는 같은 계열의 결함이고, 4 는 값 2개다.

---

## 1. 조사와 접지 (설계 판단의 근거)

읽은 것은 전부 워크트리 `/Users/dev/private/project/coding-harness/.claude/worktrees/hub-session-list-fixes`
안의 파일이다. 아래 행 번호는 기준 커밋 `735547c` 기준.

### 1.1 이슈 1 — 왜 같은 파일이 카드로는 열리는가 (원인 확정)

세 지점을 이어 붙이면 원인이 나온다.

| # | 위치 | 사실 |
|---|---|---|
| 1 | `hub_collect.py:_read_tier1_for_root` (337행 정의, 승자 선정은 363행) | `winner = hub_project.select_tier1_source((*legacy_candidates, *session_snapshots))` — **세션별 대시보드(`.claude/dashboards/<id>.html`)가 프로젝트 티어 1 승자가 될 수 있다**(결정 ST11). mtime 최신이 이긴다 |
| 2 | `hub_model.py:build_dashboard_registry` (74~87행) | 프로젝트 항목과 세션 항목이 **같은 조립 지점**(`tier1_file_path`)을 공유한다(결정 ST14). 키는 다르지만(프로젝트=경로 해시, 세션=파일경로 해시) **값(절대경로)은 같은 파일일 수 있다** |
| 3 | `hub_template.html:1673` `renderProject` | 카드 클릭 판정은 `Boolean(project.dashboard_key) && isServed` 뿐 — 세션 행이 쓰는 `tier1_is_finished_task` 에 해당하는 판정이 **프로젝트 쪽에 없다** |

즉 세션 행이 FT4 로 막은 그 파일이, 카드에서는 아무 판정 없이 열린다. 프로젝트 쪽에 있는 세대 판정은
`tier1_is_previous_task`(`hub_project.py:74`, 결정 GN1~GN3) 하나인데 그것은 **다른 세션이 남긴
대시보드**를 겨냥하고 살아 있는 세션들의 *시작 시각*을 `all()` 로 보므로, 같은 세션이 발행한 경우에는
정의상 항상 거짓이다(FT6 의 표가 이미 그 실측을 기록해 뒀다 — 6개 프로젝트 전부 False).

### 1.2 이슈 2 — 정렬이 시간뿐이다

`hub_template.html:1666` `visibleSessionsOf`:

```js
return project.sessions.slice()
  .sort(function(a, b){ return b.last_event_at_ms - a.last_event_at_ms; })
  .filter(shouldRenderSession);
```

`done` 세션의 `last_event_at_ms` 는 `SessionEnd` 시각이라 **방금 끝난 세션일수록 크다**. 반대로
진행 중인 세션은 긴 서브에이전트가 도는 동안 훅 이벤트를 내지 않아 `last_event_at_ms` 가 20~40분
뒤처질 수 있다(`SubagentStart` 이후 `SubagentStop` 까지 무이벤트). 그래서 「완료가 위, 작업중이
아래」가 정상 동작으로 발생한다. 카드 높이는 340px 고정이고 넘치는 세션은 `.sessions`(406행)
내부 스크롤이라(결정 TR4) 밀린 세션은 화면에서 사라진다.

참고 선례: `hub_project.py:49` `PROJECT_STATE_PRIORITY = ("working", "idle", "stale", "done")` —
서버가 프로젝트 배지를 고를 때 쓰는 **같은 4값 순서**가 이미 있다.

### 1.3 이슈 3 — 실행 목록에 작업 경계가 없다

`hub_session.py:459` `summarize_agent_runs` 는 `facts.subagents` **전부**를 뷰로 만들고 정렬 후
`SUBAGENT_RUN_MAX_PER_SESSION`(100)으로만 자른다. 세션이 대시보드를 100% 로 끝낸 뒤 새 프롬프트로
다시 일하면 이전 작업의 실행이 그대로 남는다. 클라이언트도 상한(`MAX_VISIBLE_AGENT_RUNS = 5`)만
적용한다(1383행 `visibleAgentRunRows`).

작업 경계로 쓸 수 있는 관측치를 전수 확인했다:

| 후보 | 관측 가능? | 판정 |
|---|---|---|
| 대시보드 파일 mtime (`Tier1Snapshot.file_mtime_ms`) | ✅ 이미 스냅샷에 있다 | **채택**(§5) |
| 「100% 도달 시각」 | ❌ 대시보드 DOM 계약에 그런 필드가 없다 — 진행률이 유일한 종료 신호다(결정 FT1 의 근거와 같다) | 기각 |
| 대시보드 단계의 `data-started-at`(→ `StepView.started_at`) | ❌ **현행 생성물이 그 속성을 쓰지 않는다** — `commands/dashboard_template.html`·`commands/dashboard.md` 전수 0건이고, `hub_parse.py:66` 의 정규식에서도 선택 그룹이며 필드에 「현재 렌더 소비자 없음」이 명시돼 있다 | 기각(§5.2) |
| 마지막 프롬프트 시각 | ❌ `SessionTail.last_prompt` 는 문자열뿐이고 시각이 없다 | 기각(§5.2) |
| 실행 사이의 유휴 간격(30분) | ✅ 계산 가능 | **기각** — 이 저장소 워크플로우는 *설계 승인 대기*로 30분 넘게 멈추는 것이 정상이라, 사용자가 PRP 를 읽는 동안 그 설계 실행이 목록에서 사라진다(§5.2) |

### 1.4 이슈 4 — 지금 값과 그것을 무는 검사

`hub_template.html:313~318`:

```css
.card.card-working::after{ … box-shadow:inset 0 0 14px -6px var(--accent);
  animation:card-working-glow 4s ease-in-out infinite}
@keyframes card-working-glow{0%,100%{opacity:.6}50%{opacity:1}}
.card.card-open.card-working::after{box-shadow:inset 0 0 20px -4px var(--accent)}
```

- `tests/run.sh` **T25-171** 이 `animation:card-working-glow 4s` 리터럴을 고정한다 → 기대값 갱신 필요.
- **T25-65** 는 진폭 `.6` 만 고정한다 → 무관(건드리지 않는다).
- **T25-189** 는 `.card.card-working{…,0 0 8px -2px var(--accent)}` 의 **바깥** bloom 만 읽어
  `1.5×blur + spread ≤ gap(12px)` 을 검사한다. 이 변경은 `::after` 의 **inset** 그림자만 건드리고
  inset 은 상자 밖으로 번지지 않으므로 **T25-189 는 손대지 않는다**(정규식도 `\.card\.card-working\{`
  로 시작해 `::after` 규칙에 매치되지 않는다 — 실측 확인).
- 279~312행 주석이 「진폭 .6·주기 4s 는 대시보드 단계 칩 halo(`ol.steps li.active .chip::after`)와
  **같은 두 숫자**를 공유하는 단일 모션 언어(결정 D5)」라고 적는다. 대시보드 쪽은
  `commands/dashboard_template.html:172` 의 `dz-step-active-pulse 4s` 이고 `tests/run.sh:4388` 이
  그 값을 따로 고정한다 → **주기는 더 이상 공유되지 않으므로 주석을 정정해야 한다**(§6).

---

## 2. 영향 범위 (파일별)

| 파일 | 변경 | 이슈 |
|---|---|---|
| `hub/bin/hub_session.py` | ① `SubagentRunView` 에 `is_previous_task: bool = False` 필드 ② `summarize_agent_runs` 에 `previous_task_boundary_ms: int \| None = None` 인자 + 그 bool 을 채우는 1줄 ③ `compute_session_view` 가 FT 판정을 **먼저** 하고 경계를 넘기도록 6줄 재배치 | 3 |
| `hub/bin/hub_project.py` | `ProjectView` 에 `tier1_is_finished_task: bool = False` 필드(맨 뒤) + `_project_view_for_path` 에서 채우는 순수 헬퍼 1개 **(승인 항목 3 에서 「서버」안을 고를 때만)** | 1 |
| `hub/bin/hub_template.html` | ① `renderProject` 의 `isClickable` 산식 + `panelEmptyReason` 분기 + 툴팁 가드 ② `PROJECT_FINISHED_TASK_REASON` 상수 ③ `SESSION_STATE_ORDER` 상수 + `sessionStateRank()` + `visibleSessionsOf` 비교 함수 ④ 이전 작업 실행 표시(승인된 안에 따라 `visibleAgentRunRows` 또는 `renderAgentRunRow`) + CSS 규칙 1~2줄 ⑤ 글로우 값 2개 + 279~312행 주석 정정 | 1·2·3·4 |
| `hub/README.md` | 「화면 배치」에 3줄(세션 정렬 규칙 / 이전 작업 실행 표시 / 카드도 끝난 대시보드를 사유로 대체) | 1·2·3 |
| `tests/run.sh` | 신설 T25-218~T25-221, 개정 T25-171 | 전부 |
| `tests/mutations.tsv` | 신설 4행, 개정 1행(T25-171) | 전부 |
| `tests/hub/test_hub_session.py` | 신설 클래스 1개(+ 기존 클래스에 통합 검사 2건) | 3 |
| `tests/hub/test_hub_project.py` | 신설 클래스 1개 **(승인 항목 3 에서 「서버」안을 고를 때만)** | 1 |

**건드리지 않는 것**: `hub_collect.py`(발견 규칙 불변) · `hub_model.build_dashboard_registry`
(등록 유지 — §3.6) · `hub_parse.py`(대시보드 DOM 계약 불변) · `hub_server.py` · `commands/dashboard*`
· `.card.card-working{…}` 바깥 bloom · `@keyframes` 이름과 진폭.

---

## 3. 이슈 1 — 카드가 끝난 대시보드를 연다 (결정 CD1~CD7)

> → **템플릿 부분 폐기(2026-09-30)** — 카드와 카드 상세보기 머리는 더는 대시보드를 열지 않고(hub-session-modal-cleanup.md 결정
> MX1) 프로젝트 진행률도 그리지 않으므로(MX4), CD1~CD7 의 카드 쪽 배선(끝난 작업 사유 분기·`PROJECT_FINISHED_TASK_REASON`·
> 「이전 작업」 라벨 논의)은 템플릿에서 대상이 사라졌다. 서버의 프로젝트 단위 판정 필드(`ProjectView.tier1_is_finished_task`)는
> 그대로 남고 후속 가지치기 대상이다(MX12). 세션 행의 끝난 작업 게이트(FT4)는 무관하게 유지된다.

### 3.1 판정

> **결정 CD1 — 판정은 「이 카드가 열 파일이, 어떤 세션의 *끝난 작업* 대시보드인가」다.**
> `project.tier1.session_id` 가 있고(= 승자가 세션별 파일이고), 그 세션의
> `tier1_is_finished_task` 가 참이면 참.

`session_id` 대조가 **정확한** 이유: `index_session_dashboards`(`hub_project.py:273`)는 세션 S 의
스냅샷 중 mtime 최대를 고르고, `select_tier1_source` 는 전체 후보 중 mtime 최대를 고른다. 전체 최대가
`session_id == S` 라면 그것은 곧 S 의 최대이기도 하다 — 두 승자는 **같은 스냅샷**이다. 그래서 새로운
파일 동일성 판정을 발명할 필요가 없다.

새 임계값·새 술어는 만들지 않는다. `is_session_tier1_from_finished_task`(FT1·FT6)의 결과를
**그대로 들어 올리는 것**이 이 절의 전부다.

### 3.2 판정을 어디서 하는가 — **승인 항목 3**

| | **(P) 서버 필드 신설 (권고)** | (C) 클라이언트 유도 |
|---|---|---|
| 형태 | `ProjectView.tier1_is_finished_task: bool = False` | `renderProject` 가 `project.tier1.session_id` 로 `project.sessions` 를 훑어 bool 을 읽는다 |
| 코드량 | 파이썬 순수 헬퍼 1개(4줄) + 필드 1개 | JS 순수 함수 1개(4줄) |
| 단위 테스트 | **붙는다**(`tests/hub` stdlib unittest) | 붙지 않는다 — 템플릿 JS 는 `tests/run.sh` 의 grep 가드뿐이다 |
| 기존 관례 | `renderProject` 가 이미 옆줄에서 `project.tier1_is_previous_task`(서버 bool)를 읽는다 — 같은 계열의 판정이 한 곳에 모인다 | 「서버는 사실만, 클릭 가능 여부는 클라이언트가 조립」(FT4·GN4)에도 맞다 |
| 데이터 | 프로젝트당 bool 1개 증가(무시할 수준) | 0 |

> **결정 CD2 — (P) 를 권고한다.**
> 근거: (a) **같은 판정 계열이 흩어지지 않는다** — 카드는 이미 `tier1_is_previous_task` 를 서버에서
> 받아 읽는다. 쌍둥이 판정 하나만 클라이언트 유도로 두면, `renderProject` 를 여는 사람이 두 개의
> 세대 판정을 서로 다른 층에서 찾아야 한다. (b) **단위 테스트가 붙는다** — §1.1 의 세 지점을 잇는
> 판정이라 회귀가 조용하다(오늘 이 결함이 조용했던 이유이기도 하다). grep 가드는 「함수를 경유했다」만
> 말할 수 있고 「판정이 맞다」는 말할 수 없다. (c) 필드 이름은 `SessionView` 와 **같은 이름**을
> 쓴다 — 담체만 다를 뿐 **같은 판정**이기 때문이다(GN 이 서로 *다른* 판정에 다른 이름을 준 것과
> 모순되지 않는다). 그 점을 필드 주석에 명시한다.
> (C) 를 고를 만한 유일한 근거는 「스냅샷에 이미 있는 두 사실의 AND 를 서버가 미리 계산해 담을
> 필요가 있나」(YAGNI)다. 그 반문은 정당하지만 (a)·(b) 가 더 무겁다고 본다.

### 3.3 판정이 참일 때의 동작

> **결정 CD3 — 세션 행과 같은 형태다(FT4 (A)): 대시보드 대신 사유를 띄운다.**
> 카드는 여전히 클릭 대상이고(`data-panel-empty-reason` 이 붙는다 → `.card[data-panel-empty-reason]`
> 이 커서·hover 를 담당), 패널이 비는 것이 아니라 사유 문구가 뜬다(불변식 OC-A). 정보 손실 0.

### 3.4 문구

> **결정 CD4 — 새 상수 `PROJECT_FINISHED_TASK_REASON` 을 만든다.**
> 문안: **「이 카드가 가리키는 대시보드는 완료된 이전 작업입니다 — 그 세션은 그 뒤로도 작업을
> 계속했습니다.」**
> `SESSION_FINISHED_TASK_REASON`(1167행) 재사용을 기각하는 이유는 FT4 (c) 가 GN6 문구 재사용을
> 기각한 것과 **같은 형태**다 — 그 문장의 주어가 「이 세션이 발행한 대시보드는」이라, 프로젝트 카드를
> 눌렀을 때 뜨면 어느 세션을 말하는지 화면에 없다. 「이전 작업」 어휘는 GN5·FT4 와 공유한다.

### 3.5 분기 순서

> **결정 CD5 — `panelEmptyReason(project, isClickable)` 에서 새 분기는 `project.dashboard_key`
> 분기보다 **앞**에 온다.** 뒤로 가면 키가 있는 끝난 대시보드가 `FILE_MODE_DASHBOARD_HINT`(서버를
> 켜라)로 잘못 설명된다 — `sessionPanelEmptyReason` 이 이미 같은 함정을 겪었고 T25-203 이 그 순서를
> 기계적으로 문다. 카드 쪽도 같은 형태의 가드를 신설한다(T25-218).
> 같은 이유로 `file://` 안내 툴팁도 함께 가린다(`sessionRowAttributes` 1560~1563행의 가드와 같은 형태).

### 3.6 FT5 재해석 (기존 결정과의 유일한 충돌 지점)

FT5 원문:

> **결정 FT5 — 「그래도 열기」 우회 수단을 만들지 않는다.** 요청 범위 밖이고(YAGNI), 파일은 여전히
> 서버에 등록돼 있으므로 **필요하면 프로젝트 카드 경로로 도달할 수 있다.**

> **결정 CD6 — FT5 의 *규범*(우회 수단을 새로 만들지 않는다)은 그대로 유지하고, 그 문장 뒤쪽의
> *부수적 관찰*(프로젝트 카드로 도달 가능)만 무효가 된다.**
> 근거: 그 도달 경로가 지금 사용자에게 **결함으로 신고됐다.** 설계된 탈출구가 아니라 판정이 빠져
> 생긴 구멍이었다는 것이 §1.1 의 결론이다. 파일 자체는 `build_dashboard_registry` 에 **그대로
> 등록해 둔다** — 직접 URL(`/project/<16자리 hex>/dashboard.html`, hub/README.md 177행에 이미
> 문서화)로는 여전히 도달할 수 있으므로 「파일이 사라진다」는 오해가 없도록 README 에 한 줄로 남긴다.
> 새 UI 우회 버튼은 만들지 않는다(FT5 규범 유지).

### 3.7 카드의 「이전 작업」 라벨은 붙이지 않는다

> **결정 CD7 — GN5 의 카드 라벨(`이전 작업` + 톤다운)은 이 판정에 적용하지 않는다.**
> 이유: (a) 사용자 요청은 **클릭 동작**이다. (b) 카드가 보여주는 티어 1 요약(제목 — 5/5 · 100%)은
> 그 대시보드가 실제로 말하는 것 그대로라 거짓이 아니다. (c) `data-tier1-previous` 속성 하나가
> CSS 스코프와 패널 인계를 겸하고 있어(GN4), 다른 판정을 같은 속성에 얹으면 패널 안내 줄(GN6 문구)
> 까지 잘못 딸려 온다 — 그 문구는 *다른* 세션 케이스 전용이다. 필요해지면 별도 속성으로 나중에
> 더한다(YAGNI). **승인 항목 4** 로 올린다(반대 의견이 있으면 뒤집기 쉬운 항목이다).

---

## 4. 이슈 2 — 세션 목록 정렬 (결정 SO1~SO5)

### 4.1 정렬 규칙 — **승인 항목 1**

네 안을 목업 이슈 2 절에 **같은 데이터로 네 열** 나란히 두었다(완료 1분 전 / 대기 5분 전 /
**작업중 20분 전**(설계 서브에이전트 실행 중) / 완료 12분 전 / 소식없음 2시간 전).

| | 현재 | **(A) 상태 우선 후 시간 (권고)** | (B) 작업중만 위로 | (C) 완료만 아래로 |
|---|---|---|---|---|
| 정렬 키 | 시간 ↓ | `(상태 순위, 시간 ↓)` | `(working 여부, 시간 ↓)` | `(done 여부, 시간 ↓)` |
| 위 데이터의 결과 | 완료·대기·완료·**작업중**·소식없음 | **작업중**·대기·소식없음·완료·완료 | **작업중**·완료·대기·완료·소식없음 | 대기·**작업중**·소식없음·완료·완료 |
| 작업중이 항상 맨 위 | ✕ | **✓** | ✓ | ✕ |
| 방금 끝난 완료가 대기 위로 | ✕(문제) | ✓ 해결 | ✕ 남음 | ✓ 해결 |
| 목록 순서 = 배지 순서 | — | **✓**(설명이 필요 없다) | 부분 | 부분 |
| 새 어휘 | — | 0 — `PROJECT_STATE_PRIORITY` 와 같은 4값 순서 | 새 이분법 | 새 이분법 |

> **결정 SO1 — (A) 를 권고한다. 정렬 키는 `(상태 우선순위, last_event_at_ms 내림차순)`,
> 우선순위는 `working > idle > stale > done`.**
> 근거: (a) **(B)·(C) 는 각각 사용자 신고의 절반만 답한다** — (C) 는 「완료가 위에 있다」만, (B) 는
> 「진행 중이 아래에 있다」만 고친다. (b) 실데이터에서 (A) 와 (C) 는 대개 같은 결과를 낸다(상태와
> 최신성이 상관한다 — `stale` 은 정의상 30분 이상 조용하고 `idle` 은 30분 미만이다). **갈리는 지점이
> 바로 사용자 케이스다**: 긴 서브에이전트가 도는 동안 이벤트가 뜸한 `working` 세션(마지막 이벤트
> 20분 전)과 방금 턴이 끝난 `idle` 세션(5분 전). (A) 만 그 작업중을 위로 올린다. (c) 목록 순서가
> 배지 순서와 같아 사용자에게 설명할 규칙이 하나 줄어든다.

### 4.2 어떤 상태로 정렬하는가

> **결정 SO2 — 표시 상태(`session.state`)로 정렬한다. `base_state` 를 쓰지 않는다.**
> `base_state` 로 정렬하면 「소식 없음」 배지를 단 행이 「대기」 배지 위에 올라와 순서와 배지가
> 어긋난다. 결정 D2 가 카드 글로우에서 같은 이유로 `state === 'working'` 만 강조한 선례를 따른다.

### 4.3 상수와 경유 함수

> **결정 SO3 — 클라이언트에 `SESSION_STATE_ORDER = ['working','idle','stale','done']` 상수와 순수
> 함수 `sessionStateRank(state)` 를 둔다. `visibleSessionsOf` 는 반드시 그 함수를 경유한다.**
> 서버 상수를 import 할 수 없으므로 같은 값의 두 번째 리터럴이 된다 — `STALE_AFTER_MINUTES = 30`
> (1030행)이 `hub_model.HubConfig.stale_after_minutes` 기본값과 이미 그런 이중 리터럴이다.
> 다만 **T25-130 은 그 클라이언트 리터럴의 존재만 확인하고 두 값을 대조하지는 않는다**(그 가드
> 주석의 「셸은 서버 설정을 읽을 수 없으므로」 — 실측 확인). 이 PRP 의 **T25-219** 는 한 걸음 더
> 간다: 두 값 모두 이 저장소 안의 소스 리터럴이라 실제로 **뽑아서 대조할 수 있다**(§8.1).
> 목록에 없는 상태가 오면 순위는 배열 끝(= 가장 아래)으로 폴백한다 — 새 상태가 생겼을 때 정렬이
> 예외로 죽지 않게 하는 1줄이고, 그 폴백 자체가 검사 대상이다.

### 4.4 타이브레이크와 필터 순서

> **결정 SO4 — 정렬은 `visibleSessionsOf` 안, `filter(shouldRenderSession)` **앞**에 그대로 둔다.**
> 현재 구조(`slice().sort().filter()`)와 T25-160 계약(`renderProject` 는 `visibleSessionsOf` 를
> 경유하고 직접 `.filter(shouldRenderSession)` 를 부르지 않는다)이 불변이다.

> **결정 SO5 — 같은 상태·같은 시각이면 `short_id` 오름차순으로 결정적으로 깬다.**
> 서버 `summarize_agent_runs` 가 `agent_id` 로 타이를 깨는 것과 같은 관례(AR5). 30초마다
> `innerHTML` 을 통째로 교체하므로(`TICK_MS = 30000`, 2027행) 비결정 정렬은 카드 깜빡임이 된다.

**흔들림(churn)에 대한 기록**: `working ↔ idle` 은 턴마다 바뀌므로 (A)·(B) 에서는 자리 이동이
생긴다. 다만 렌더는 30초 주기이고 `html === lastHtml` 이면 아예 다시 그리지 않는다(2082행) —
자리 이동은 **이미 카드 전체가 다시 그려지는 시점**에만 일어나므로 새로운 종류의 흔들림이 아니다.

---

## 5. 이슈 3 — 끝난 작업의 실행이 남는다 (결정 PT1~PT7)

### 5.1 경계 — **승인 항목 2 의 전반부**

> **결정 PT1 — 경계는 `session.tier1.file_mtime_ms` 이고, 게이트는 `session.tier1_is_finished_task`
> (FT1 판정)다.** 판정이 거짓이면 아무것도 바뀌지 않는다.
> 「끝났다고 볼 수 있는 대시보드」의 **마지막 쓰기 시각** = 그 작업이 화면에 기록을 남긴 마지막
> 순간이다. 100% 이후의 `log commit` 쓰기까지 포함되므로 경계는 뒤로(= 더 보수적으로) 밀리고,
> 그렇게 밀린 구간의 실행은 실제로도 그 작업의 것이다.

> **결정 PT2 — 이전 작업 판정은 `run.started_at_ms < boundary` (엄격한 `<`).**
> 경계와 같은 밀리초는 **현재 작업**으로 본다 — 여기서의 오탐은 「살아 있는 실행을 이전 작업으로
> 감춘다」쪽이 더 나쁘므로 그 반대 방향으로 경계를 연다. FT1 의 `>` 관례(오탐 회피 방향 선택)와
> 같은 사고다.

### 5.2 기각한 경계 (근거를 남긴다)

- **대시보드의 작업 시작 시각**: 계약에 없다. `StepView.started_at`(`data-started-at`)이 유일한
  후보였으나 **현행 `/dashboard` 생성물은 그 속성을 쓰지 않는다**(§1.3 전수 확인). 파서에 선택
  그룹으로만 남은 사문이라 이것을 되살리려면 `commands/dashboard.md` + `dashboard_template.html`
  + `hub_parse.py` 를 함께 고쳐야 한다 — 이 PRP 범위 밖(§11).
- **마지막 프롬프트 시각**: 값 자체가 없고(문자열뿐), 있어도 **한 작업 안에 프롬프트가 여러 번**
  있다(설계 승인 → 구현, 검수 지적 → 수정). 그 경계로 자르면 구현 단계에서 설계 실행이 사라진다.
- **유휴 간격 30분 휴리스틱**: 대시보드 없이도 되고 `/dashboard init` 에도 견디지만, 이 저장소
  워크플로우의 **설계 승인 대기**가 30분을 넘는 것이 정상이라 사용자가 PRP 를 읽는 동안 그 설계
  실행이 사라진다. 오탐 방향이 정확히 반대다.

### 5.3 판정을 어디서 하는가 — **승인 항목 2 의 후반부**

> **결정 PT3 — 서버가 *사실*을, 클라이언트가 *표시*를 맡는다. 서버에서 목록을 잘라내지 않는다.**
> `SubagentRunView` 에 `is_previous_task: bool` 을 더하고(순수 계산, 단위 테스트 대상),
> 클라이언트가 그 bool 로 표시 정책을 집행한다.
> 서버 절단을 기각하는 이유: (a) 표시 정책이 바뀔 때마다 **데이터 계약이 바뀐다**. (b) 목록이 비면
> `shouldRenderSession`(1598행)의 숨김 조건과 맞물려 **세션 줄 자체가 사라지는** 2차 효과가 서버
> 변경에서 발생한다 — 그 상호작용은 클라이언트 한 층에 가두는 편이 추적 가능하다. (c) 사실을
> bool 로 실어 두면 아래 두 안 사이를 **3줄로 갈아탈 수 있다**(되돌리기 비용이 거의 0).
> 「서버는 사실(bool)만 주고 표시는 클라이언트가 정한다」는 FT4·GN4 관례 그대로다.

### 5.4 표시 정책 — **승인 항목 2 의 핵심**

목업 이슈 3 절에 **두 경우**(새 실행 0건 = 프롬프트를 막 넣은 직후 / 새 실행 1건) × 3열로 실었다.

| | 현재 | (A) 숨김 | **(B) 「이전 작업」 라벨 + 톤다운 (권고)** |
|---|---|---|---|
| 구현 | — | `visibleAgentRunRows` 안에서 `filter` 1줄 | `renderAgentRunRow` 에 라벨·클래스 2줄 + CSS 1줄 |
| 오해 제거 | ✕ | ✓ | ✓ |
| 340px 절약 | — | **✓** (이슈 2 의 가시성 문제에도 도움) | ✕ — 다만 정렬이 「실행 중 우선 · 최근 시작 순」(AR5)이라 이전 작업은 **자연히 아래로 가고 상한 5줄에서 먼저 잘린다** — 새 실행이 밀려나지 않는다 |
| 정보 손실 | — | 있다 — 실행이 전부 이전 작업이면 목록이 통째로 사라지고, `shouldRenderSession` 과 맞물려 **세션 줄 자체가 사라질 수 있다** | 없다 |
| 문서와의 충돌 | — | **`hub/README.md` 256~258행**(「세션이 이미 완료됐어도 무엇을 몇 번 시켰는지 남는다」)과 어긋나 README 를 함께 고쳐야 한다 | 없다 |
| 허브의 다른 「이전 작업」 처리와의 일관성 | — | 어긋난다 | **맞는다** — GN5(카드 라벨+톤다운)·FT4(패널 사유) 모두 **감추지 않고 설명하는** 방향이다 |

> **결정 PT4 — (B) 를 권고한다.** 라벨 마크업은 기존 클래스를 그대로 재사용한다
> (`<span class="tier1-prev-label">이전 작업</span>` — `::after{content:" · "}` 까지 이미 있다).
> 새 CSS 는 톤다운 1~2줄(`.agent-run-prev` 스코프)뿐이고 **새 색 토큰은 만들지 않는다**(GN5 관례).
> (A) 를 고르면 README 256~258행을 함께 고치고 T25-220 의 앵커를 `visibleAgentRunRows` 로 바꾼다 —
> 그 외 설계는 전부 같다.

#### (A) 채택 확정 (2026-09-17 사용자 판정 — 권고 번복)

사용자가 **(A) 숨김**을 선택했다. PT3(서버는 사실 bool, 클라이언트가 표시)은 그대로다 —
바뀌는 것은 클라이언트의 표시 정책 한 갈래뿐이고, `SubagentRunView.is_previous_task` 도
`is_session_tier1_from_finished_task` 게이트도 설계 그대로다. (A) 가 파생시키는 변경은 넷이다.

1. **필터 위치는 `visibleAgentRunRows` 안이다**(`renderAgentRunRow` 가 아니다). GOTCHA 3 이
   요구하는 단일 경유점이 그대로 유지돼야 `shouldRenderSession` 과 `+N건 더` 계산이 같은
   목록을 본다.
2. **`hub/README.md` 256~258행을 함께 고친다.** 현재 문장은 「세션이 이미 완료됐어도 무엇을 몇 번
   시켰는지 남는다」인데 (A) 는 그 약속을 좁힌다 — **끝난 작업의 실행은 목록에서 빠지고, 지금
   작업의 실행만 남는다**는 취지로 개정한다. 문서와 화면이 어긋난 채 커밋되지 않게 한다.
3. **T25-220 의 앵커를 `visibleAgentRunRows` 로 옮긴다**(라벨 마크업 가드가 아니라 필터 가드가
   된다). `.agent-run-prev` CSS 와 `tier1-prev-label` 재사용은 **구현하지 않는다** — §7.3 의
   CSS 1~2줄은 (A) 에서 범위 밖이다.
4. **`shouldRenderSession` 의 2차 효과를 의도된 동작으로 수용한다.** 실행이 **전부** 이전 작업인
   `done` 세션은 보이는 칩이 0개가 되어 세션 줄 자체가 목록에서 사라진다(발췌·워크플로우 칩도
   없을 때). 이것은 결함이 아니라 결정 V2(「완료 + 표시할 발췌 없음 + 보이는 실행·칩 0개 = 숨김」)
   의 정확한 귀결이며, (A) 가 「보여줄 것이 아닌 것」의 정의를 넓힌 결과다. 이슈 3 이 신고한
   시나리오(완료 뒤 새 프롬프트로 계속 진행)의 세션은 `state`가 `working` 이라 이 조건에 걸리지
   않는다 — 사라지는 것은 **끝난 뒤 아무 흔적도 남기지 않은 done 세션**뿐이다. 이 동작을
   **`tests/run.sh` 의 T25-220 서브체크(§8.1)로 고정**한다(회귀로 오인되지 않게) — 정정(재검수
   1회차 MEDIUM-2): 최초 계획은 「§8.3 의 단위 테스트 1건」이었으나, `hub_template.html` 의
   JS 를 실행하는 테스트 메커니즘이 이 저장소에 없어(node/jsdom 부재) 실현 불가능했다. §8.3 은
   순수 파이썬 계산(`summarize_agent_runs`)만 실행할 수 있고, "행이 사라진다"는 클라이언트
   렌더 동작이라 이 저장소의 기존 관례(§8.1 의 grep 기반 구조 고정)로 대체했다.

### 5.5 나머지

> **결정 PT5 — 필드 이름은 `SubagentRunView.is_previous_task`.** 카드의 `tier1_is_previous_task`
> (프로젝트 세대 판정)와 어휘를 공유하되 담체가 실행 1건이라 접두 `tier1_` 을 붙이지 않는다.
> `SubagentRunView` 에는 맨 뒤에 기본값과 함께 둔다 — 이 클래스의 필드 순서를 무는 검사는 없다
> (T25-150 이 무는 것은 `SessionView` 다, 실측 확인).

> **결정 PT6 — 게이트가 꺼져 있으면(판정 거짓·`tier1` 없음) 모든 실행이 `is_previous_task=False`
> 이고 화면은 오늘과 한 픽셀도 다르지 않다.** 회귀 표면을 이 한 문장으로 좁힌다.

> **결정 PT7 — 알려진 미검출(의도적)**: 새 작업이 `/dashboard init` 으로 **같은 세션 대시보드를
> 덮어쓰면** `percent < 100` 이 되어 FT 게이트가 꺼지고 이전 작업 실행이 라벨 없이 돌아온다.
> 근본 해결은 §5.2 의 「작업 시작 시각」을 대시보드 계약에 넣는 것이고 이 PRP 범위 밖이다.
> FT3 이 「측정 불가 구간에서는 미검출과 오탐 중 미검출을 택한다」고 못박은 것과 같은 방향이며,
> 그 구간에서도 **화면은 오늘과 같다**(더 나빠지지 않는다).

---

## 6. 이슈 4 — 작업중 카드 글로우 (결정 GW1~GW3)

> **결정 GW1 — `.card.card-working::after` 를 `inset 0 0 14px -1px`, `animation:… 2s` 로 바꾼다.**
> (blur 14px 과 `@keyframes` 이름·진폭 `.6` 은 불변.)

> **결정 GW2 — `.card.card-open.card-working::after` 의 spread 도 `-4px → -1px` 로 함께 올린다
> (blur 20px 유지).** — **승인 항목 5**
> 근거: 이 규칙의 목적은 「열린 채 작업중」이 평상시 작업중보다 **더 깊고 넓게** 보이는 것이고,
> `hub/README.md` 293~295행이 그 관계를 사용자에게 약속한다. 기본 규칙만 -1px 로 올리면 같은 blur
> 대비 기본 쪽 띠가 더 두꺼워져 **관계가 뒤집힌다.** 두 spread 를 같게 두면 판별자는 blur 차
> (14 vs 20)로 남는다. 대안은 「지시 문면 그대로 기본 규칙만 바꾼다」이고, 그 경우 열린 카드의
> 글로우가 평상시보다 약해 보인다 — 목업 이슈 4 절이 두 조합을 나란히 보여준다.

> **결정 GW3 — 주석·검사·원장을 같은 커밋에서 정정한다.**
> ① 279~312행 주석의 「진폭 .6·주기 4s 를 대시보드 단계 칩 halo 와 공유하는 단일 모션 언어(D5)」
> 서술 → **진폭은 계속 공유, 주기는 허브만 2s(2026-09-17 사용자 요청)** 로 정정하고, 확산 inset
> bloom 수치를 인용한 D11 관련 문장도 새 값으로 갱신한다. 대시보드(`dz-step-active-pulse 4s`)는
> **건드리지 않는다.**
> ② `tests/run.sh` T25-171 의 기대 리터럴 `animation:card-working-glow 4s` → `2s`, 실패 문구의
> 회귀 방향도 「옛 4s 로 되돌아감」으로 갱신.
> ③ `tests/mutations.tsv` 491행(T25-171)의 `mutation_sed` 를 `s/card-working-glow 2s/card-working-glow 4s/`
> 로, `expect_token` 을 새 실패 문구에 맞춰 갱신한다 — 갱신하지 않으면 sed 가 아무것도 바꾸지 못해
> **변조가 살아남고 T37-15 가 실패한다.**
> T25-65(진폭)·T25-189(바깥 bloom 확산)는 손대지 않는다(§1.4).

---

## 7. 데이터 모델과 인터페이스

### 7.1 서버 (파이썬 — ★순수 계약 유지: 파일시스템·시각·환경 접근 0)

```python
# hub_session.py
@dataclass(frozen=True)
class SubagentRunView:
    ...                                  # 기존 필드 불변
    is_previous_task: bool = False       # 신설(PT5) — 끝난 작업 경계 이전에 시작된 실행인가

def summarize_agent_runs(
    facts: SessionFacts,
    now_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,
    subagent_meta_by_agent_id: dict[str, SubagentMeta] | None = None,
    previous_task_boundary_ms: int | None = None,   # 신설(PT1) — None 이면 전부 False
) -> tuple[SubagentRunView, ...]:
    """세션의 서브에이전트 실행 1건당 뷰 1개. 경계가 주어지면 그 이전 시작분에 표시를 남긴다."""

def compute_session_view(...) -> SessionView:
    """변경점: FT 판정(tier1_is_finished_task)을 summarize_agent_runs 호출 **앞**으로 옮기고,
    참일 때만 tier1.file_mtime_ms 를 previous_task_boundary_ms 로 넘긴다."""
```

```python
# hub_project.py  (승인 항목 3 에서 (P) 를 고를 때만)
@dataclass(frozen=True)
class ProjectView:
    ...
    tier1_is_previous_task: bool = False
    tier1_is_finished_task: bool = False   # 신설(CD1·CD2) — 맨 뒤, 기본값 있음

def is_project_tier1_from_finished_session_task(
    tier1: Tier1Snapshot | None, session_views: Sequence[SessionView]
) -> bool:
    """카드가 열 티어 1 파일이 어떤 세션의 *끝난 작업* 대시보드인가(결정 CD1).

    세션 판정(SessionView.tier1_is_finished_task)을 프로젝트 담체로 들어 올리기만 한다 —
    새 임계값도 새 술어도 만들지 않는다.
    """
```

### 7.2 클라이언트 (hub_template.html — 전부 순수 함수, DOM 에 닿지 않는다)

| 심볼 | 신설/개정 | 시그니처·값 |
|---|---|---|
| `PROJECT_FINISHED_TASK_REASON` | 신설 (CD4) | 문자열 상수 |
| `SESSION_STATE_ORDER` | 신설 (SO3) | `['working','idle','stale','done']` |
| `sessionStateRank(state)` | 신설 (SO3) | `string -> number` (목록 밖이면 배열 길이) |
| `compareSessionsForDisplay(a, b)` | 신설 (SO1·SO5) | `(session, session) -> number` |
| `visibleSessionsOf(project)` | 개정 (SO4) | 비교 함수만 교체, 구조 불변 |
| `panelEmptyReason(project, isClickable)` | 개정 (CD4·CD5) | 분기 1개를 **맨 앞**에 추가 |
| `renderProject(project)` | 개정 (CD2·CD3) | `isClickable` 산식 + 툴팁 가드 |
| `renderAgentRunRow(run, nowMs)` | 개정 (PT4-B 채택 시) | 라벨 + `agent-run-prev` 클래스 |
| `visibleAgentRunRows(runs)` | 개정 (PT4-A 채택 시에만) | `filter` 1줄 — 시그니처 불변이라 `shouldRenderSession` 경유 계약(GOTCHA 3·T25-209)이 자동으로 유지된다 |

### 7.3 CSS (PT4-B 채택 시)

```css
/* 이전 작업 실행(결정 PT4) — 새 색 토큰을 만들지 않는다(.tier1-prev-label 과 같은 관례). */
.agent-run-prev .agent-run-title,.agent-run-prev .agent-run-meta{color:var(--muted)}
```

---

## 8. 테스트 계획

### 8.1 `tests/run.sh` 소스 가드 (신설 4 · 개정 1)

머리 주석은 `# T25-218(...)` 형태로 붙이고, 전부 `test_hub_docs_and_constants` 함수 안(T25-2xx 관례)에 둔다.

| ID | 무엇을 무는가 | 방향 |
|---|---|---|
| **T25-218** (이슈 1) | ① `PROJECT_FINISHED_TASK_REASON` 상수 존재 ② `renderProject()` 본문에 `tier1_is_finished_task` 가 `isClickable` 산식에 있다 ③ `panelEmptyReason()` 본문에서 그 분기가 `project.dashboard_key` 분기보다 **앞줄**(T25-203 과 같은 줄 번호 비교) ④ (P) 채택 시 `hub_project.py` 에 필드·헬퍼 존재 ⑤ `hub/README.md` 에 카드도 사유로 대체된다는 문장 | 정 |
| **T25-219** (이슈 2) | ① `hub_project.py` 의 `PROJECT_STATE_PRIORITY` 와 `hub_template.html` 의 `SESSION_STATE_ORDER` 에서 4값 순서를 각각 추출해 **문자열로 대조**(어느 한쪽만 바뀌면 실패, 추출 실패도 실패로 보고 — 공허 통과 방지) ② `visibleSessionsOf()` 본문이 `sessionStateRank(` 를 경유한다 ③ **역**: 본문에 시간 단독 비교(`b.last_event_at_ms - a.last_event_at_ms` 만 있는 return)가 남아 있지 않다 | 정+역 |
| **T25-220** (이슈 3) | ① `hub_session.py` 에 `is_previous_task` 필드와 `previous_task_boundary_ms` 인자 존재 ② `compute_session_view` 본문에서 FT 판정이 `summarize_agent_runs` 호출보다 **앞줄**(순서가 뒤집히면 경계를 못 넘긴다 — 줄 번호 비교) ③ 클라이언트가 `run.is_previous_task` 를 경유한다(B 안: `renderAgentRunRow` 본문 / A 안: `visibleAgentRunRows` 본문) ④ **역**: `summarize_agent_runs` 본문에 새 `30 * 60` 리터럴 0건(T25-204 와 같은 형태 — 경계는 `stale_after_ms` 파생이지 새 임계값이 아니다) ⑤ README 문장 ⑥ (재검수 1회차 MEDIUM-1 신설) `renderAgentRunList()` 의 `currentTaskRunCount` 오버플로 카운트 필터가 `visibleAgentRunRows()` 필터 조건과 리터럴로 일치(두 리터럴의 드리프트 방지) ⑦ (재검수 1회차 MEDIUM-2 신설) `shouldRenderSession()` 의 `done` 숨김 조건식 전체를 리터럴로 고정(§5.4 4항의 2차 효과 고정) | 정+역 |
| **T25-221** (이슈 4) | `.card.card-working::after` 의 spread 가 `-1px`, blur 가 `14px` / `.card.card-open.card-working::after` 가 `20px -1px`(GW2 채택 시) — 두 규칙을 각각 정규식으로 뽑아 값 비교. 「열린 쪽이 더 넓다」는 부등식(`blur_open > blur_base`)도 함께 단언한다 | 정 |
| **T25-171** (개정) | 기대 리터럴 `animation:card-working-glow 2s` | 정 |

### 8.2 `tests/mutations.tsv` 원장

- 신설 4행(T25-218~221) — 전부 **변조행**(면제행으로 등록하지 않는다. `LEDGER_EXEMPT_ROW_RATCHET`
  상한을 건드리지 않기 위해서이기도 하다). 8열 규약(§원장 머리)대로 `target_path`·`mutation_sed`
  (`[주소]s/…/…/` 형태만)·`expect_group=T25`·`expect_token`(실패 보고 줄에서 **정확히 1건**)·
  `defect_description`·빈 `exempt_reason`·`anchor_function=test_hub_docs_and_constants` 를 채운다.
- 개정 1행(T25-171, 현재 491행): `mutation_sed` → `s/card-working-glow 2s/card-working-glow 4s/`,
  `expect_token` → 새 실패 문구. **갱신하지 않으면 sed 가 no-op 이 되어 변조가 살아남고 T37-15 가
  실패한다.**
- `LEDGER_MUTATION_ROW_FLOOR`(100)·`LEDGER_EXEMPT_ROW_RATCHET` 상수는 **건드리지 않는다** —
  변조행이 순증가라 하한 미달이 없고 면제행은 늘지 않는다.

### 8.3 `tests/hub` 단위 테스트 (stdlib unittest — 순수 로직만)

**`test_hub_session.py` — 신설 `SummarizeAgentRunsPreviousTaskTest`**

| 케이스 | 입력 | 기대 |
|---|---|---|
| PT-1 | 경계 `None` | 모든 실행 `is_previous_task=False` (오늘과 동일) |
| PT-2 | 경계보다 **1ms 앞**에 시작한 실행 | `True` |
| PT-3 | 경계와 **같은 밀리초**에 시작 | `False` (결정 PT2 — 경계는 현재 작업 쪽으로 연다) |
| PT-4 | 경계보다 뒤 | `False` |
| PT-5 | 실행 전부가 경계 이전 | 전부 `True`, **개수는 줄지 않는다**(서버는 자르지 않는다 — PT3) |
| PT-6 | 이전·현재가 섞인 6건 | 정렬은 AR5 그대로(실행 중 우선 → 최근 시작 → agent_id), 플래그만 다르다 |
| PT-7 | `meta.json` 시작 시각이 있는 실행(AR7) | 경계 비교는 **뷰의 `started_at_ms`**(= meta 우선) 기준임을 고정 |

**`test_hub_session.py` — 기존 클래스에 통합 검사 2건**

| 케이스 | 입력 | 기대 |
|---|---|---|
| PT-8 | `tier1.percent=100`, Δ > `stale_after_ms`, 실행이 mtime 앞뒤로 하나씩 | `tier1_is_finished_task=True` **그리고** 앞 실행만 `is_previous_task=True` |
| PT-9 | `tier1.percent=60`(진행 중), 같은 실행 배치 | 판정 거짓 → **전부 `False`**(PT6 회귀 표면) |

기존 `SessionTierOneFinishedTaskTest`(13건)와 `SummarizeAgentRunsTest` 는 **손대지 않는다** —
판정 자체도 기존 시그니처의 기본 인자 동작도 바뀌지 않는다.

**`test_hub_project.py` — 신설 `ProjectTierOneFinishedTaskTest`** (승인 항목 3 에서 (P) 채택 시)

| 케이스 | 입력 | 기대 |
|---|---|---|
| CD-1 | 승자 = 끝난 세션 대시보드, 그 세션이 `sessions` 에 있다 | `True` |
| CD-2 | 승자 = 레거시 단일 파일(`session_id is None`) | `False` (세션 귀속 불가 — 알려진 공백, §11) |
| CD-3 | 승자 = 세션 파일이지만 그 세션이 `sessions` 에 없다(이벤트 창 밖) | `False` (**열린 채로 실패** — 오늘 동작 유지) |
| CD-4 | 승자 = 진행 중 대시보드(percent 60) | `False` |
| CD-5 | `tier1_is_previous_task` 와 동시에 참인 배치 | 두 필드가 **독립적으로** 참이 된다(FT6 표의 「독립적으로 참/거짓」 재확인) |
| CD-6 | `tier1 is None` | `False` |

### 8.4 검증 명령 (정본)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

### 8.5 눈으로 확인할 것 (구현 후)

1. 끝난 작업 대시보드를 가진 프로젝트 카드를 클릭 → 패널에 `PROJECT_FINISHED_TASK_REASON` 이
   뜨고 대시보드가 **뜨지 않는다**. 같은 세션 행을 클릭하면 세션용 문구가 뜬다(문구가 서로 다르다).
2. 진행 중 세션이 있는 카드에서 세션 목록 맨 위가 항상 `작업중` 배지다(완료가 방금 끝났어도).
3. 끝난 작업 뒤 새 프롬프트를 넣은 세션의 실행 목록에서 이전 작업 실행에 라벨이 붙는다(또는 사라진다).
4. 작업중 카드의 글로우가 눈에 띄게 굵어지고 호흡이 2배 빨라진다. **열린 채 작업중**인 카드가
   평상시 작업중보다 여전히 더 넓게 보인다.
5. 320px 최소 폭에서 실행 목록 칩이 두 줄로 찢어지지 않는다(T25-212 가 무는 `flex:0 0 auto` 유지).

---

## 9. 구현 순서 (각 단계 끝에 검증)

1. **이슈 4** (CSS 2값 + 주석 + T25-171 + 원장 1행) → `bash tests/run.sh` — 가장 작고 독립적이라
   검사 파이프라인(가드 ↔ 원장 동기화)이 도는지 먼저 확인한다.
2. **이슈 2** (클라이언트 정렬 + T25-219 + 원장) → `bash tests/run.sh`.
3. **이슈 3 서버** (`SubagentRunView`·`summarize_agent_runs`·`compute_session_view`) + 단위 테스트
   → `python3 -m unittest discover -s tests/hub -t .`.
4. **이슈 3 클라이언트** (표시 정책) + T25-220 + 원장 → 전체 검증.
5. **이슈 1** (서버 필드 + 단위 테스트 → 클라이언트 3곳 + T25-218 + 원장) → 전체 검증.
6. `hub/README.md` 3줄 + 이 문서의 「상태」 줄 갱신.

의존: 3 → 4(뷰 필드가 있어야 표시가 붙는다), 5 의 서버 → 5 의 클라이언트. 1·2 는 독립.

---

## 10. 승인이 필요한 결정

> **판정 요약 (2026-09-17)** — 1: (A) · 2: 경계 승인 + 표시 **(A) 숨김(권고 번복)** · 3: (P) 서버 필드 ·
> 4: 붙이지 않음 · 5: 함께 `-1px`. 항목 2 의 파생 변경은 §5.4 「(A) 채택 확정」 절이 정본이다.

### 승인 항목 1 — 세션 정렬 규칙 (§4.1, 결정 SO1)
**→ 판정: (A) 채택 (권고대로).**
**(A) 상태 우선(작업중>대기>소식없음>완료) 후 시간 — 권고** / (B) 작업중만 위로 / (C) 완료만 아래로.
목업 이슈 2 절에 네 열로 나란히 있다. (A) 만이 「긴 서브에이전트로 이벤트가 뜸한 작업중 세션」까지
위로 올린다.

### 승인 항목 2 — 이전 작업 실행의 경계와 표시 (§5.1·§5.4, 결정 PT1·PT4)
**→ 판정: 경계 승인 · 표시는 (A) 숨김 채택 — 권고(B)를 번복한 결정이다. 파생 변경 4건은
§5.4 「(A) 채택 확정」 절을 따른다(README 개정 · T25-220 앵커 이동 · CSS 범위 밖 · 2차 효과 수용).**
경계는 **대시보드 파일 mtime + FT 판정 게이트**(다른 후보는 §5.2 에서 전부 기각, 근거 있음).
표시는 **(B) 「이전 작업」 라벨 + 톤다운 — 권고** / (A) 숨김. (A) 는 340px 를 아끼지만 완료 세션의
실행 기록이 사라지고 `hub/README.md` 256~258행을 함께 고쳐야 한다. 두 안의 구현 비용은 같고
나중에 갈아타는 비용도 3줄이다.

### 승인 항목 3 — 이슈 1 판정 위치 (§3.2, 결정 CD2)
**→ 판정: (P) 채택 (권고대로).** `tests/hub/test_hub_project.py` 의 신설 클래스와
`_project_view_for_path` 헬퍼가 구현 범위에 들어온다.
**(P) `ProjectView.tier1_is_finished_task` 서버 필드 신설 — 권고** / (C) 클라이언트 유도.
(P) 는 단위 테스트가 붙고 카드의 두 세대 판정이 한 층에 모인다. (C) 는 새 필드 0개.

### 승인 항목 4 — 카드에 「이전 작업」 라벨을 붙일까 (§3.7, 결정 CD7)
**→ 판정: 붙이지 않음 (권고대로).**
**붙이지 않음 — 권고.** 붙이면 `data-tier1-previous` 속성을 공유하게 되어 패널 안내 줄(GN6, *다른*
세션 전용 문구)까지 잘못 딸려 온다. 별도 속성이 필요하면 그때 더한다.

### 승인 항목 5 — `card-open` 조합 spread (§6, 결정 GW2)
**→ 판정: 함께 `-1px` 채택 (권고대로).**
**함께 `-1px` 로 — 권고** / 지시 문면 그대로 기본 규칙만 변경. 후자는 「열면 더 깊고 넓다」는
hub/README.md 293~295행의 약속과 어긋난다. 목업 이슈 4 절에서 두 조합을 직접 비교할 수 있다.

---

## 11. 리스크와 대안

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| **살아 있는 대시보드가 카드에서 사라진다**(이슈 1 오탐) | 낮음 | 큼 | 판정은 FT1 을 **그대로** 재사용한다 — FT 의 4겹 오탐 방어(percent 100 연접 · Δ 여유 · `log commit` 이 mtime 을 되살림 · 엄격한 `>`)를 그대로 물려받는다. 새 임계값 0개 |
| 이슈 3 의 `/dashboard init` 미검출(PT7) | **확실** | 중 | 그 구간에서도 화면은 **오늘과 같다**(더 나빠지지 않는다). 근본 해결은 대시보드 계약에 작업 시작 시각을 넣는 별도 작업 |
| 레거시 단일 파일(`session_id is None`)이 승자인 프로젝트는 이슈 1 판정이 서지 않는다 | 중 | 소 | 세션 귀속이 원리적으로 불가능하다. `tier1_is_previous_task`(GN)가 *다른 세션* 케이스를 이미 덮으므로 남는 공백은 「같은 세션이 레거시 파일로 끝낸 작업」 하나다. CD-2 테스트로 **의도된 거짓**임을 고정 |
| 정렬 변경으로 카드 안 세션 위치가 바뀌어 읽던 자리를 놓친다 | 중 | 소 | 렌더는 30초 주기 + `html === lastHtml` 억제라 이미 카드 전체가 다시 그려지는 시점에만 일어난다(§4.4) |
| 글로우 -1px 이 2026-09-08 사용자 지적(「테두리가 너무 두껍다」)을 되살린다 | 중 | 소 | 사용자가 현재 화면을 보고 직접 지시한 값이다. 목업 이슈 4 절(라이트·다크·열린 카드)에서 **승인 전에** 눈으로 확인한다 |
| `SESSION_STATE_ORDER` 가 서버 상수와 드리프트 | 낮음 | 중 | T25-219 가 두 파일에서 순서를 뽑아 대조(추출 실패도 실패로 보고) |

**검토했으나 채택하지 않은 큰 대안 2개**

1. **이슈 3 을 서버에서 잘라낸다**(`summarize_agent_runs` 가 이전 작업 실행을 목록에서 제거).
   가장 짧지만 표시 정책이 데이터 계약에 박히고, 목록이 비면 `shouldRenderSession` 과 맞물려 세션
   줄이 사라지는 2차 효과가 서버 변경에서 발생한다. 사실(bool)과 표시를 분리하는 쪽이 되돌리기 쉽다(PT3).
2. **이슈 1 을 `build_dashboard_registry` 에서 등록을 빼는 방식으로 막는다.** 클릭하면 404 가 되어
   「없는 척」이 된다 — 불변식 OC-A(키가 없으면 사유가 반드시 붙는다)와 결정 N7(조용한 실패 금지)에
   정면으로 어긋난다. 파일은 등록해 두고 **화면에서 사유로 설명**한다(CD3·CD6).

---

## 12. 범위 밖 (명시)

- 대시보드 DOM 계약에 「작업 시작 시각」을 넣는 것(`commands/dashboard.md` + `dashboard_template.html`
  + `hub_parse.py`) — PT7 의 근본 해결이지만 이 4건과 층이 다르다.
- 끝난 대시보드에 대한 「그래도 열기」 UI(FT5 규범 유지, CD6).
- `commands/dashboard_template.html` 의 `dz-step-active-pulse 4s` — 허브만 2s 로 간다(GW3).
- 세션 목록의 표시 개수 상한·페이지네이션, 카드 높이(340px, TR4) 변경.
- `select_tier1_source`(WT6)·`index_session_dashboards`(ST12)의 승자 규칙 변경.
- 프로젝트 배지 집계(서버 `state`)에 대한 영향 — 이슈 2·3 은 전부 클라이언트 표시층이다(결정 V1 유지).

---

## 13. 완료 기준 (Acceptance Criteria)

1. `bash tests/run.sh` · `python3 -m unittest discover -s tests/hub -t .` ·
   `python3 -m unittest discover -s tests/commands -t .` · `python3 -m py_compile hub/bin/*.py` 전부 통과.
2. 신설 가드 4개가 **일부러 되돌렸을 때 실제로 실패한다**(원장 변조행으로 T37-15 가 기계적으로 확인).
3. `hub_session.py`·`hub_project.py` 의 ★순수 계약 유지(파일시스템·시각·환경 접근 0 — 기존 가드가 문다).
4. 새 의존성 0개(python3 표준 라이브러리 전용), `hub_template.html` 외부 리소스 참조 0건(T25-162).
5. §8.5 의 눈 확인 5개가 실제 허브에서 재현된다.
6. 승인된 안과 문서(이 PRP·`hub/README.md`)의 서술이 일치한다.

---

## 14. 구현 전 필독

- `docs/prps/hub-ui-4-issues.md` §5(FT1~FT7) — 이슈 1·3 판정의 뿌리.
- `docs/prps/hub-session-revival-and-stale-tier1.md` GN1~GN6 — 카드 세대 판정과 어휘.
- `docs/prps/hub-agent-runs-and-prompt-source.md` AR4~AR11 — 실행 목록 뷰의 계약(정렬 K2·상한 AR11).
- `tests/mutations.tsv` 머리 주석(8열 규약) — 새 가드를 원장에 올리는 방법. 특히 `expect_token` 이
  `tests/run.sh` 의 실패 보고 줄에서 **정확히 1건**이어야 한다는 제약(T37-13).
- `hub/bin/hub_template.html` 279~312행 주석 — 글로우 수치의 역사(하드 링 → 확산 bloom, D9~D11).
