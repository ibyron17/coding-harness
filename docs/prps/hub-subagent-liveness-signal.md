# 허브 — 서브에이전트 실행 중 생존 신호 (PRP)

> **결함 1건**: 서브에이전트 실행이 30분을 넘기면 그 실행을 디스패치한 **메인 세션 카드와
> 프로젝트 카드가 「소식 없음」으로 뒤집힌다.** 실제로는 그 세션이 가장 활발히 일하는 중이다.
> 90분을 더 넘기면 「소식 없음 · 직전 **대기**」까지 내려간다.

| 항목 | 값 |
|------|-----|
| 대상 | `hub_session.py`(판정) · `hub_subagent.py`(상수 1개) · `hub_subagent_read.py`(신규 I/O) · `hub_project.py`·`hub_collect.py`(배선) + 테스트·문서 |
| 브랜치 | `worktree-subagent-liveness` (기준 `251f727`) |
| 상위 설계 정본 | [`hub-dashboard.md`](./hub-dashboard.md)(「상태 판정 규칙 2」) → [`hub-session-revival-and-stale-tier1.md`](./hub-session-revival-and-stale-tier1.md)(RV1~RV3) → [`hub-zombie-subagent-guard.md`](./hub-zombie-subagent-guard.md)(ZG1~ZG7) → [`hub-agent-runs-and-prompt-source.md`](./hub-agent-runs-and-prompt-source.md)(AR1~AR11) → [`hub-live-session-native-source.md`](./hub-live-session-native-source.md)(LS1~LS13) → **이 문서** |
| 워크플로우 경로 | **전체 경로** — 상태 판정 규칙(정본 문서)과 공개 함수 시그니처 5개가 바뀐다 |
| 규모 | **Small~Medium** — 신규 1개(이 문서) / 수정 5개 소스 + 4개 테스트 + 2개 문서. Python 순증 약 **+70줄** |
| 새 데이터 계약 필드 | **0개** — `SessionView`·`ProjectView`·`SubagentRunView`·`#dzh-data` 스키마 **무변경** |
| 템플릿(`hub_template.html`) | **0줄** — 새 마크업·클래스·색·레이아웃이 없다(§10) |
| 새 외부 의존성 | **없음**(stdlib). 새 config 키 **0개**, 새 상수 **1개**(파일 접미사 리터럴) |
| 결정 코드 | **SL**(Subagent Liveness). `grep -rhoE "결정 [A-Z]{1,3}[0-9]+" docs/prps/*.md` 로 확인 — 사용 중 접두사 51종에 `SL` 은 없다 |
| 승인 상태 | **승인됨**(2026-09-18). 항목 1·2(SL4·SL2)는 원안 승인. 항목 3(메인 턴 절반)은 「함께 고친다」로 채택됐다가 **측정 게이트 불통과로 보류** — 결정 **SL10**(§2.7·§4) |
| 개정 이력 | 초안 SL1~SL9 → 승인 항목 3 채택으로 §9 기각 I 철회 → §2.7 측정 결과 **SL10 으로 보류**. 코드 변경 계획(§5·§7·§11·§12)은 **초안 그대로** |

---

## 1. 요구사항 요약

허브가 구독하는 훅은 6개뿐이고(`hub_settings.HOOK_EVENTS`), **서브에이전트가 도는 도중에
발화하는 훅이 하나도 없다.** 그래서 `SessionFacts.last_event_at_ms` 가 `SubagentStart` 시각에
얼어붙고, 그 값만 보는 `stale` 오버레이가 30분 뒤 `working` 을 덮는다. 90분을 더 넘기면
`is_running_subagent` 의 좀비 상한이 `base_state` 까지 `idle` 로 떨어뜨린다.

**살아 있다는 증거는 이미 파일로 존재한다** —
`~/.claude/projects/<인코딩된 cwd>/<session_id>/subagents/agent-<agentId>.jsonl` 은
서브에이전트 자신의 transcript 이며 실행 내내 append 된다. 허브는 **이미 같은 디렉터리의
`agent-<agentId>.meta.json` 을 경로 조립해 읽는다**(`hub_subagent_read` 의
`_subagent_meta_path`·`read_subagent_meta`) — 경로 조립·안전성 검사·`observed_cwds` 순회가
전부 있다. 형제 `.jsonl` 에 `stat()` 1회를 더하는 것이 이 설계의 전부다.

### 1.1 성공 기준 (검증 가능한 형태)

| # | 기준 | 증명 수단 |
|---|------|-----------|
| **G1** | 42분째 도는 `implementer` 를 가진 세션의 `state == "working"`(≠`"stale"`) | 단위 `SL-U1` — 훅 마지막 이벤트가 42분 전, transcript mtime 이 1분 전 |
| **G2** | 98분째 도는 실행의 `base_state == "working"` 이고 그 칩 `is_running is True` | 단위 `SL-U2` — 현행 코드에서는 `idle`/`False`(버그 재현) |
| **G3** | transcript 가 **없는** 세션의 판정이 오늘과 **한 글자도** 다르지 않다 | 단위 `SL-U3` — 보강 인자 없이 호출한 결과 == 오늘의 기대값(회귀 고정) |
| **G4** | 진짜 죽은 실행은 여전히 상한 안에서 잡힌다 — 시작 5분 뒤 append 가 멈춘 미종료 실행은 `now = 마지막 append + 90분` 에서 `is_running is False` | 단위 `SL-U4` |
| **G5** | `stale` 판정식이 `live_roster` 에서 파생된 어떤 값도 읽지 않는다(**결정 LS9 보존**) | 단위 `SL-U8` + 기계 검사 `T25-224` |
| **G6** | 상태와 칩이 어긋나지 않는다 — 같은 뷰에서 `base_state == "working"` 이면 `any(run.is_running)` | 단위 `SL-U7`(ZG11 의 이번 판) |
| **G7** | 프로젝트 카드도 함께 교정된다 — 그 세션 하나만 있는 프로젝트의 `state == "working"` | 단위 `SL-U9`(`compose_project_views` 경유) |
| **G8** | `record_prompt_excerpt: false` 인 사용자에게도 교정이 적용된다(**함정 PS7 회피**) | 단위 `SL-R5` + 기계 검사 `T25-222` |
| **G9** | `snapshot_content_key` 가 매 수집마다 바뀌지 않는다 — transcript mtime 은 어떤 뷰 필드에도 실리지 않는다 | 단위 `SL-U10` + 기계 검사 `T25-223` |

---

## 2. 실측 (이 문서를 쓰면서 직접 측정한 것만 적는다)

측정 대상: `~/.claude/hub/events/*.jsonl` 8일치(2026-09-11 ~ 09-18) ·
`~/.claude/projects/*/*/subagents/` 전량. 측정 스크립트는 세션 스크래치패드에 있고 저장소에
남기지 않는다.

### 2.1 실행 시간 — 30분 상한을 정기적으로 넘는다

| 관측 | 값 |
|------|-----|
| 짝이 맞는(`SubagentStart`+`SubagentStop`) 실행 | **119건** |
| 실행 시간 | 중앙값 **16.0분** · p90 **42.1분** · 최장 **85.0분** |
| **30분 초과** | **27건 = 22.7%** |
| 미종료(고아) 실행 | 8건 |

> **E1 — `SUBAGENT_ZOMBIE_AFTER_MS`=90분의 근거는 이미 깨졌다.** 그 상수를 정한 결정 ZG2 는
> "완료된 정상 실행 90건의 최장 47.3분, 90분은 그 1.9배"를 근거로 삼았다. 지금 실측 최장은
> **85.0분**(리텐션 8일 창)이고, 과제 제시 측정(8일치, 136건)에서는 **98.4분** — 상한을 이미
> 넘긴 정상 종료 실행이 관측됐다. 상한을 **올리는 것은 이 설계의 해법이 아니다**(§9 기각 G).

### 2.2 실행 중 transcript append 간격 — 이 설계의 안전 마진

훅 이벤트의 `SubagentStart`~`SubagentStop` 창 **안쪽**에서만 측정했다(창 밖 append 는
§2.3 참조). 체인은 `시작 → 첫 줄 → … → 마지막 줄 → 종료` 로 잡아 양 끝의 침묵도 포함한다.

| 관측 | 값 |
|------|-----|
| 측정 대상 | 119건 **전부** transcript 가 존재했고, 창 안에 줄이 0개인 실행은 **0건** |
| 창 안 최장 침묵 | 중앙값 **2.4분** · p90 **10.0분** · p99 **10.5분** · **최댓값 11.1분** |
| 침묵 ≥ 20분인 실행 | **0건 (0%)** |
| 침묵 ≥ 30분인 실행 | **0건 (0%)** |
| 30분 넘는 실행 27건만 따로 | 최장 침묵 p50 9.4분 · p90 10.0분 · **최댓값 10.5분** |

> **E2 — 10분 부근의 천장.** 긴 실행 다수의 최장 침묵이 정확히 `10.0분` 에 몰린다. `Bash`
> 도구의 timeout 상한(600,000ms = 10분)과 값이 일치한다 — 즉 관측된 천장은 우연이 아니라
> **도구 하나가 최대로 잡아먹을 수 있는 시간**으로 설명된다. 이 설계가 쓰는 상한(90분)은 그
> 천장의 **8.1배**다.

### 2.3 죽은 실행은 스스로 조용해진다 — 이 설계의 상한이 성립하는 근거

리텐션 창 안의 미종료(고아) 실행 8건 전수:

| agent_type | 시작 이후 경과 | 마지막 append (시작 기준) | 마지막 append 이후 경과 |
|---|---|---|---|
| implementer | 162.6h | +54.3분 | 161.7h |
| code-reviewer | 161.9h | +12.8분 | 161.7h |
| implementer | 91.2h | +13.7분 | 90.9h |
| code-reviewer | 41.7h | +7.8분 | 41.5h |
| code-reviewer | 41.7h | +8.0분 | 41.5h |
| code-reviewer | 41.6h | +6.6분 | 41.5h |
| design-architect | 0.3h | +18.5분 | **0.0h(지금 도는 중)** |
| design-architect | 0.1h | +4.3분 | **0.0h(지금 도는 중)** |

> **E3 — 6건의 진짜 좀비는 전부 append 가 멈춰 있고, 2건의 진짜 실행은 전부 append 가
> 살아 있다.** 이것이 결정 SL1 의 실증 근거다: **transcript mtime 은 자기소멸하는 신호다.**
> 죽은 프로세스는 파일에 쓸 수 없으므로 `now - 마지막 append` 는 단조 증가한다.

### 2.4 창 밖 append — 미종료 실행만 보는 이유

같은 `agent-<id>.jsonl` 이 `SubagentStop` **한참 뒤에** 다시 append 되는 경우가 있다
(119건 중 **3건**, 지연 ~10,083~10,155분 ≈ 7일). 파일 단위로만 보면 span 1,000분 · 최장
공백 935분짜리 파일도 존재한다 — 즉 **파일은 실행 1건과 1:1 이 아니다**(재개·이어하기·
`agent_id` 재등장). → 결정 SL3: **`ended_at_ms is None` 인 실행의 파일만 본다.**

### 2.5 meta.json 필드 커버리지 (760건 전수)

| 필드 | 커버리지 |
|---|---|
| `agentType`·`description`·`toolUseId`·`spawnDepth` | 760 / 760 (100%) |
| `model` | 677 / 760 (89.1%) |
| `parentAgentId` | 21 / 760 (2.8%) |
| **`requestShape`** | **55 / 760 (7.2%)** — background 34 · foreground 21 |
| `spawnDepth == 2`(중첩) | 21 / 760 (2.8%) |

> **E4 — `requestShape` 는 쓰지 않는다**(§9 기각 H). 7.2% 커버리지로는 판정을 세울 수 없고,
> 이 설계가 그 구분을 **필요로 하지 않는다**(foreground·background 어느 쪽이든 transcript 는
> 똑같이 append 된다).

### 2.6 수집 1회당 비용 (성능, 요구 7)

`hub_collect.read_recent_events` 는 **오늘 + 어제** 이벤트 파일만 읽는다
(`_recent_event_file_paths`). 8일치를 그 2일 창으로 재생한 결과:

| 창 종료일 | 세션 수 | 실행 수 | **미종료 실행 수** | 한 세션 최대 미종료 |
|---|---|---|---|---|
| 09-11 | 19 | 66 | 2 | 1 |
| 09-12 | 20 | 66 | 2 | 1 |
| 09-14 | 41 | 16 | 1 | 1 |
| 09-15 | 54 | 23 | 1 | 1 |
| 09-16 | 32 | 57 | **4** | 4 |
| 09-17 | 25 | 141 | 3 | 3 |
| 09-18 | 14 | 120 | 1 | 1 |

- **실측 상한: 수집 1회당 추가 `stat()` 4회**(8일 창 전체의 최악값). 워크트리 세션은
  `observed_cwds` 를 2개까지 시도할 수 있으므로 **실질 상한 ≈ 8회**.
- **구조적 상한**: `세션 수 × SUBAGENT_RUN_MAX_PER_SESSION(100) × |observed_cwds|` — 기존
  `read_subagent_metas` 의 읽기 예산과 **같은 식**이다(§4.2 가 같은 상한을 재사용한다).
  기존 경로는 실행 1건당 `is_file()` + `stat()` + `read_text()` 3회를 쓰는 데 비해 이 경로는
  `stat()` 1회뿐이므로, 최악의 경우에도 서브에이전트 관련 syscall 예산의 **1/3 증가**가
  상한이다.
- 파일 **내용을 읽지 않는다** — 크기 상한도 파싱도 시크릿 스크럽도 필요 없다(§8 보안).

---

### 2.7 메인 세션 transcript — 승인 항목 3 의 측정 게이트 (2026-09-18 추가)

사용자가 승인 항목 3 을 「함께 고친다」로 결정해, 기각 I(긴 메인 턴의 「소식 없음」)를 같은
방법으로 고칠 수 있는지 **측정했다.** 그 채택은 "측정이 받쳐주면"이라는 전제 위에 있었고,
**측정은 받쳐주지 않는다.** 아래 다섯 측정이 근거이며 판정의 정본은 결정 SL10 이다.

**(a) 원인별 분해 — 오케스트레이터 측정의 재현.** 훅 이벤트 7.5일치(83세션)를 분당 재생해
stale 로 표시된 세션-분을 원인별로 갈랐다. 절대값은 오케스트레이터 측정(총 11,311분)과
다르다 — 내 재생은 클라이언트의 12시간 숨김을 적용하지 않고 죽은 세션까지 전부 세기
때문이다. **비중의 순서는 같다(C ≫ A > B).**

| 원인 | 분 | 비중 | 상태 |
|---|---|---|---|
| **A.** 미종료 서브에이전트가 있는 동안 | 13,619 | 21.7% | **SL2+SL4 가 고친다** |
| **B.** 서브에이전트 없이 메인 턴만 `turn_state == "running"` | **519** | **0.8%** | 승인 항목 3 의 대상 |
| **C.** 턴도 끝난 진짜 대기 | 48,745 | 77.5% | 정상 동작 — 깨뜨리면 안 된다 |

**(b) 회복률 — 이 개정의 결론을 혼자 결정하는 숫자.** B 의 519분 각각에 대해 "그 시점 직전
30분 안에 메인 transcript 에 기록이 있었는가"를 물었다. **회복: 8분 / 519분 = 1.5%.**

B 의 분은 3개 세션에 몰려 있고(377 · 141 · 1분), 상위 2건은 **턴이 6.8시간·2.4시간 열려
있는 동안 transcript 가 통째로 조용한** 창이다 — 사람이 자리를 비웠거나 승인 프롬프트 앞에
멈춰 있던 구간이고, `turn_state == "running"` 은 그것을 구분하지 못하는 낡은 훅 사실일
뿐이다. **그 구간에 「소식 없음」은 참이다.** 파일 신호로 되살릴 것이 없다.

**(c) 턴 진행 중 append 간격 — 안전 마진이 없다.** 227개 턴 창(`UserPromptSubmit`→`Stop`)
안쪽의 최장 침묵(체인은 `시작 → 줄들 → 종료`):

| 모집단 | n | p50 | p90 | p99 | 최댓값 | ≥30분 |
|---|---|---|---|---|---|---|
| 전체 턴 창 | 227 | 0.47분 | 7.08분 | 48.18분 | **415.3분** | 7 |
| 서브에이전트 없는 창(= B 모집단) | 170 | 0.35분 | 1.57분 | 10.08분 | **400.2분** | 1 |
| **30분 넘는 긴 창**(= stale 이 실제로 발동하는 모집단) | **15** | **29.16분** | 400.2분 | 415.3분 | 415.3분 | **7 (47%)** |

**결정적 대비**: SL2 의 서브에이전트 신호는 최장 침묵 **11.1분** — 30분 문턱 대비 2.7배,
90분 상한 대비 8.1배 여유였다. 메인 세션 쪽은 stale 이 실제로 발동하는 긴 창의 **중앙값이
29.16분**으로 문턱과 같은 자리이고 **47%가 문턱을 넘는다.** 여유는 **약 1.0배**다.

**(d) 턴이 끝난 뒤에도 파일은 계속 쓰인다 — C 를 정면으로 깬다.**

- `Stop` 이후 다음 `UserPromptSubmit` 이전에 기록된 줄 **2,036건, 33세션 중 13세션(39%)**.
  종류: `attachment` 637 · `queue-operation` 508 · `user` 475 · `system` 404 · `pr-link` 12 —
  **전부 타임스탬프를 갖는다**(4종 22,142건 전수 확인). 사람이 대기 중에 메시지를 미리
  입력하거나 파일을 붙일 때 쓰인다.
- 더 나쁜 것: **타임스탬프가 아예 없는 호스트 관리용 줄** 9종이 있다 —
  `last-prompt`·`atis-latch`·`bridge-session`·`custom-title`·`mode`·`worktree-state`·
  `relocated`·`file-history-snapshot`·`ai-title`. 이들이 `st_mtime` 을 움직인다.
- 결과: 2시간 넘게 조용한 세션 31건의 **`mtime` − 마지막 타임스탬프 줄** 은 중앙값
  **3,073분(51시간)** · p90 26,052분 · 최댓값 50,453분(35일)이고 **20/31 이 30분을 넘는다.**
  실례 — 99.2시간째 조용한 세션의 mtime 이 마지막 기록보다 **4,071분(68시간)** 뒤이며 꼬리
  줄은 `bridge-session`·`last-prompt` 같은 관리 줄이다.

> **(d) 의 뜻**: 메인 transcript 의 `st_mtime` 은 **작업 신호가 아니다.** 세션 열기·제목
> 생성·모드 전환·워크트리 상태·재개 기록이 며칠 지난 세션의 파일을 건드린다. SL1 이
> 서브에이전트 신호에 대해 논증한 성질(「죽은 프로세스는 파일에 쓸 수 없다」)이 **여기서는
> 성립하지 않는다** — 살아 있는 호스트가 죽은 세션의 파일에 쓴다.

**(e) 비용은 장애물이 아니었다(요구 4).** `hub_collect._read_transcript_tail` 은 이미 매
수집마다 모든 세션의 메인 transcript 에 `stat()`(`st_size`) + `open` + `seek` + `read` 를
한다. `st_mtime` 은 **이미 부르고 있는 그 `stat()` 이 함께 돌려주는 값**이라 추가 `stat()`
은 **0회**다. 이 확장은 공짜였다 — 채택하지 않는 이유는 비용이 아니라 **신호 품질**이다.
§2.6 의 비용 표(수집 1회당 +4~8회)는 서브에이전트 쪽 값이며 **변하지 않는다.**

**표본의 한계(정직하게 적는다)**: 훅에 등장한 83세션 중 메인 transcript 를 조립 경로에서
찾은 것은 **33건**이다(나머지는 그 경로에 파일이 없다 — `read_session_tail` 도 같은 경로
규칙을 쓰므로 허브 역시 그 50건에는 이 신호를 쓸 수 없다). (b) 의 회복률은 그 33건 위의
값이고, 찾지 못한 50건은 **어차피 신호를 쓸 수 없는 세션**이라 회복률을 올리는 방향으로
작용하지 않는다.

---

## 3. 확정된 전제 (재론하지 않는다)

1. **실행 중 발화하는 훅은 없다.** `hub_settings.HOOK_EVENTS` 6종 전부 실행의 시작·끝
   또는 세션/턴 경계다. 훅을 추가하는 것은 §9 기각 C.
2. **허브는 `~/.claude/projects/<인코딩>/<session_id>/subagents/` 경로를 이미 조립한다.**
   `_subagent_meta_path`·`_is_safe_path_segment`·`observed_cwds` 순회가 전부 존재한다.
3. **`hub_session.py`·`hub_subagent.py`·`hub_live_session.py` 는 ★순수다.** 새 I/O 는
   `hub_*_read.py` 계열에 둔다. `now_ms` 는 항상 인자로 받는다. `tests/run.sh` T25-10·
   T25-205 가 기계적으로 강제한다.
4. **클라이언트는 상태를 재계산하지 않는다.** `hub_template.html` 은 `session.state` 를 그대로
   그리고, `last_event_at_ms` 는 경과 라벨·12시간 숨김·정렬·툴팁에만 쓴다(직접 확인).
   → 서버측 수정만으로 화면이 교정된다.

---

## 4. 설계 결정

### SL1 — 생존 신호는 **미종료 실행의 transcript mtime** 하나다

`agent-<agentId>.jsonl` 의 `stat().st_mtime` 을 ms 로 바꾼 값. 내용은 읽지 않는다.

**왜 이것인가** — 세 가지 성질을 동시에 만족하는 유일한 관측값이다.

| 성질 | 근거 |
|------|------|
| 실행 중 계속 갱신된다 | E2 — 창 안 최장 침묵 11.1분, ≥20분 0건 |
| 죽으면 스스로 멈춘다 | E3 — 고아 6건 전부 append 정지, 41~162시간째 동결 |
| 읽는 비용이 O(1) 이다 | §2.6 — `stat()` 1회, 내용 파싱 없음 |

**`meta.json` mtime 을 쓰지 않는 이유**: 그 파일은 spawn 시점에 한 번 쓰이고 끝난다 —
이미 `SubagentRunView.started_at_ms` 의 출처다(결정 AR7). 생존 신호가 될 수 없다.

### SL2 — 판정은 **덧셈**이다: 기존 규칙을 대체하지 않고 **True 로 가는 길을 하나 더** 연다

```python
def is_running_subagent(
    subagent: SubagentFact,
    now_ms: int,
    zombie_after_ms: int,
    last_activity_at_ms: int | None = None,
) -> bool:
    if subagent.ended_at_ms is not None:
        return False
    if (now_ms - subagent.started_at_ms) < zombie_after_ms:
        return True      # 오늘의 규칙 — 한 글자도 바뀌지 않는다
    return last_activity_at_ms is not None and (now_ms - last_activity_at_ms) < zombie_after_ms
```

**단조성(monotone)이 핵심이다.** 새 인자는 판정을 `False→True` 로만 뒤집을 수 있고 절대
`True→False` 로 뒤집지 못한다. 그래서:

- **결정 ZG2 가 「더 나쁘다」고 못 박은 방향의 회귀 위험이 0 이다** — "정말 오래 걸리는 정상
  에이전트의 glow 가 꺼진다"는 실패는 이 변경으로 **새로 생길 수 없다**.
- **`last_activity_at_ms=None`(transcript 부재·`stat` 실패·구버전 호스트)이면 오늘의
  판정식 그대로다**(성공 기준 G3). 폴백을 따로 설계할 필요가 없다 — 기본값이 곧 폴백이다.
- **`SUBAGENT_ZOMBIE_AFTER_MS = 90 * 60 * 1000` 리터럴을 건드리지 않는다** →
  `T25-91`(상수 리터럴 고정)과 원장 행이 그대로 유효하다.

**상수의 뜻이 바뀐다 — 그리고 그 새 뜻이 더 튼튼하다.** 90분은 이제 "실행이 최대로 오래
걸릴 수 있는 시간"(실측 최장 85~98분 — **이미 깨진 가정**)이 아니라 **"실행 중 침묵이 최대로
길 수 있는 시간"**(실측 최장 11.1분 — **8.1배 여유**)이다. 같은 숫자를 올리지 않고 근거만
교체한다.

**대가(정직하게 적는다)**: 진짜 좀비의 검출이 최대 `마지막 append − 시작` 만큼 늦어진다.
E3 의 6건 기준 6.6~54.3분, 즉 최악의 sticky-working 구간이 90분 → **144.3분**. 결정 ZG2 가
"작은 쪽 실패가 더 나쁘다"고 명시한 비대칭에 따르면 이쪽이 **덜 나쁜 방향**이고, 그래도
상한은 유지된다(무한이 아니다). 더 빠른 검출은 §9 기각 J 에 revisit 트리거와 함께 적는다.

### SL3 — 읽는 대상은 **미종료 실행뿐**이다

`ended_at_ms is not None` 인 실행의 파일은 **읽지 않는다.** 두 가지 이유:

1. **필요 없다** — 이미 끝난 실행의 `is_running` 은 첫 분기에서 `False` 로 확정된다.
2. **거짓 생존을 만든다** — E4(§2.4): 종료 후 7일 뒤에 다시 append 되는 파일이 실재하고,
   파일 단위 최장 공백은 935분이다. 파일은 실행 1건과 1:1 이 아니다.

부수 효과로 읽기 대상이 §2.6 의 "미종료 실행 수"(실측 최악 4)로 줄어든다.

### SL4 — `stale` 오버레이는 **같은 신호로 함께 넓힌다** (결정 LS9 재확인 — 이 설계의 핵심 쟁점)

```python
def last_known_activity_at_ms(
    facts: SessionFacts, subagent_activity_by_agent_id: dict[str, int] | None = None
) -> int:
    """stale 판정이 보는 '허브가 이 세션에 대해 아는 가장 새로운 것'의 시각."""
```

= `max(facts.last_event_at_ms, 미종료 실행들의 마지막 append 시각들)`

```python
is_stale = base_state != "done" and (now_ms - last_known_activity_at_ms(...)) >= stale_after_ms
```

**SL2 만으로는 결함이 고쳐지지 않는다.** SL2 는 `base_state` 를 `working` 으로 유지시키지만,
`stale` 오버레이가 그 위를 덮어 카드는 여전히 「소식 없음 · 직전 작업중」이다. **SL4 가
「소식 없음」을 지우고, SL2 가 「직전 대기」를 막는다** — 둘은 한 쌍이며 따로 넣으면 각각
절반만 고친다(SL4 만 넣으면 90분 뒤 「대기」로 표시되는 새 오답이 생긴다).

#### 결정 LS9 의 「독립 상한」 성질이 보존됨을 논증한다

LS9 는 `stale` 을 두 가지 이유로 훅 유래 그대로 뒀다. 둘을 분해해 각각 확인한다.

**(P1) 「명부 오판의 유일한 독립 상한이다」 — 완전히 보존된다.**

LS9 가 말하는 독립은 **`live_roster` 로부터의 독립**이다. 명부는 *선언*이고, 선언은 그것을
쓴 프로세스가 죽은 뒤에도 남을 수 있다(잔존 레코드 + PID 재사용, 결정 LS8 이 "검증할 수
없다"고 수용한 바로 그 구멍). 그래서 명부를 `stale` 에 섞으면 오판이 영구화된다.

transcript mtime 은 **선언이 아니라 쓰기의 흔적**이다. 죽은 프로세스는 파일에 쓸 수 없다 —
PID 재사용에 해당하는 실패 모드가 **원리적으로 없다**. 그래서:

- `last_known_activity_at_ms` 의 입력은 `SessionFacts` 와 파일시스템 유래 dict 둘뿐이다.
  `roster_state_for_session` 의 출력은 이 경로에 **도달하지 않는다**(기계 검사 `T25-224`).
- 명부가 거짓 생존을 말해도, 훅이 멈추고 transcript 도 멈춰 있으면 30분 뒤 `stale` 이 덮는다.
  **상한은 그대로 30분이다.**
- 실증: E3 의 고아 6건은 새 규칙에서도 마지막 append 30분 뒤 `stale` 이 된다(현재 41~162
  시간 동결). 명부 기반 확장이었다면 그렇지 않다.

**(P2) 「다른 질문에 답한다 — 허브가 아는 것이 얼마나 낡았는가」 — 오히려 더 정확해진다.**

`stale` 의 질문은 "이 세션이 살아 있는가"가 아니라 "**허브가 이 세션에 대해 아는 것이 얼마나
낡았는가**"다. 지금 허브는 그 답을 훅 이벤트만으로 계산하는데, 훅은 실행 구간에 **구조적으로
0건**이다(§3 전제 1). 즉 오늘의 `stale` 은 "허브가 모른다"가 아니라 "**허브가 볼 수 있는데도
안 보고 있다**"를 말하고 있다. transcript mtime 은 허브가 **실제로 아는 새 사실**이므로,
그것을 세는 것은 LS9 의 질문을 바꾸는 것이 아니라 **더 충실하게 답하는 것**이다.

**(P3) LS9 자신이 이 항목을 명시적으로 유보했다 — 이 문서가 그 유보의 청구다.**

> LS9 원문: "부작용으로 '한 턴이 30분 넘게 도는 세션은 `busy` 인데도 소식 없음' 이 남지만,
> 그것은 **오늘도 같은 동작**이고 이번 요구와 무관하다(고치려면 **별도 결정이 필요하다** —
> YAGNI 보류)."

이 PRP 가 그 「별도 결정」이다. **서브에이전트 절반만** 청구한다 — 메인 턴이 길게 도는
쪽(같은 증상, 다른 원인)은 §9 기각 I 로 명시적으로 범위 밖에 둔다.

**(P4) 화면 문구는 거짓이 되지 않는다.** `hub_template.html` 의
`STALE_TOOLTIP_SESSION_CRITERION`("마지막 이벤트로부터 30분 이상 새 소식이 없으면")은
`renderStateBadge` 가 **`state === 'stale'` 일 때만** 붙인다. 새 규칙에서 `stale` 이라는 것은
곧 "미종료 실행의 append 도 30분 이상 없었다"는 뜻이므로, 그 문구가 화면에 뜨는 모든 상황에서
문구는 참이다. → **템플릿 0줄**(§10).

### SL5 — 값은 **판정에만** 쓰고 **뷰에 싣지 않는다** (결정 LS10 과 같은 이유, D2 방어)

`hub_model.snapshot_content_key` 는 `collected_at_ms` 만 빼고 전부 비교한다. transcript mtime 은
실행 중 **초 단위로 갱신되는 값**이라, 이것을 `SessionView`·`SubagentRunView` 에 실으면 매
수집마다 키가 바뀌어 `hub.html` 쓰기 억제가 통째로 무력해진다 — 결정 LS10 이 `updatedAt`·
`statusUpdatedAt` 을 거부한 것과 **같은 실패**다.

그래서 이 값은 `live_roster` 와 같은 계열이다: **보강 인자로 들어와 판정에만 쓰이고 뷰에는
실리지 않는다.** 결과:

- **새 데이터 계약 필드 0개** — `SessionView` 무변경 → `T25-150`
  (`dataclasses.fields(SessionView)[-1].name == "tier1_is_finished_task"` 고정)이 **무영향**.
- `SubagentFact`·`SessionFacts` 무변경 — "사실"은 훅 이벤트에서만 접는다는 계약(결정 ZG5 의
  기각 사유)이 유지된다. 파일시스템 유래 값은 사실이 아니라 **조회 시점의 해석**이다.
- `#dzh-data` JSON 스키마 변경 0건. 키가 바뀌는 시점은 `state`/`base_state`/`is_running` 이
  실제로 바뀔 때뿐 — **오늘과 같은 빈도**다.

> **개정됨(2026-10-07, [`hub-live-activity.md`](./hub-live-activity.md) 결정 LA11) — SL5 옆.** SL5 는 유지된다 — 생존
> 판정용 mtime dict(`subagent_activity_by_agent_id`)는 여전히 판정에만 쓰이고 뷰에 실리지 않으며 `SessionView` 는 무변경이다
> (SL-U10·T25-225 역방향이 수정 없이 통과한다). 개정되는 것은 「새 데이터 계약 필드 0개」·「스키마 변경 0건」이다: 도는 실행의
> 활동(마지막 기록 시각·결과를 기다리는 도구·종류별 개수 등)은 **별도 통로**(`live_activity`)로 `SubagentRunView.activity` 와
> `BackgroundWait.output` 에만 실린다. 이 값은 mtime 이 아니라 기록 끝 창의 내용과 출력 파일 stat 의 함수라 도는 동안 수집마다
> 바뀐다 — SL5 가 막으려던 「쓰기 억제 무력화」를 이 기능은 표시 목적상 받아들이고(hub-live-activity.md 쟁점 4 승인), 아무것도
> 돌지 않을 때는 키가 오늘과 같다.

### SL6 — 배선은 `subagent_meta_by_agent_id` 와 **글자 그대로 같은 모양**이다

이미 있는 관례를 하나도 새로 만들지 않는다:

| 이미 있는 것 | 이 설계가 더하는 것 |
|---|---|
| `read_subagent_metas(...) -> dict[str, SubagentMeta]` | `read_unfinished_subagent_activity(...) -> dict[str, int]` |
| `compute_session_view(..., subagent_meta_by_agent_id=None)` | `..., subagent_activity_by_agent_id=None` |
| `compose_project_views(..., subagent_meta_by_agent_id=None)` | `..., subagent_activity_by_agent_id=None` |
| `_read_session_annotations` 가 모아 반환 | 같은 함수에서 6번째 값으로 반환 |

전부 **기본값 `None`** 이라 기존 호출부(테스트 포함)는 무해하다.

### SL7 — **`record_prompt_excerpt` 로 게이팅하지 않는다** (함정 회피, 결정 PS7 의 경계)

`read_subagent_metas` 는 `record_prompt_excerpt` 가 거짓이면 파일을 아예 읽지 않는다(결정
PS7) — `description` 이 사용자 프롬프트 유래 자유 텍스트이기 때문이다. **mtime 은 프롬프트
발췌가 아니다.** 그 게이트 안에 넣으면 프라이버시 설정을 끈 사용자에게만 결함이 남는다.

선례가 이미 있다: `read_live_session_roster` 도 같은 이유로 게이팅되지 않는다(결정 LS2 —
"명부는 `record_prompt_excerpt` 로 게이팅하지 않는다 — 프롬프트 콘텐츠가 아니다").
→ 성공 기준 G8, 단위 `SL-R5`, 기계 검사 `T25-222`.

### SL8 — 읽기 실패는 **경고를 내지 않는다**

`read_unfinished_subagent_activity` 는 `(dict, warnings)` 가 아니라 **`dict` 하나만** 돌려준다.
근거: 이 경로가 하는 것은 `stat()` 하나뿐이고, 실패("파일 없음"·"권한 없음")와 정상 부재
("이 호스트 버전은 transcript 를 안 쓴다")가 **구분되지 않으며 결과도 같다**(폴백 = 오늘의
판정). 경고로 올리면 transcript 없는 실행이 하나라도 있을 때마다 수집 사이클마다 같은 줄이
화면에 쌓인다 — 조용한 실패가 아니라 **의미 없는 소음**이다.

`read_subagent_meta` 가 경고를 내는 것은 그쪽이 **내용을 읽기** 때문이다(크기 상한 초과·
권한 거부는 "읽을 수 있어야 하는데 못 읽었다"는 진짜 이상 신호다). 두 함수의 차이는
"실패가 진단 가치를 갖는가"이지 일관성이 아니다.

### SL9 — 되돌리기 수단은 **만들지 않는다** (결정 LS12 와 같은 판단)

`HubConfig` 에 스위치를 두지 않는다.

- 기존 불린 3개(`show_usage_panel`·`record_prompt_excerpt`·`usage_api_enabled`)는 전부
  **사용자 선택의 문제**지 "고장 나면 끄는 스위치"가 아니다(결정 LS12 원문).
- **고장 대비는 구조가 맡는다** — SL2 의 단조성 때문에 신호가 사라지면(`None`) 동작이 오늘로
  정확히 되돌아간다. 즉 **폴백이 곧 롤백**이고, 그것이 기본 경로다.
- 그래도 되돌려야 한다면 이 변경은 5개 파일의 가산적 diff 라 `git revert` 1회로 끝난다.

**revisit 트리거**: 호스트가 `subagents/*.jsonl` 을 쓰지 않는 빌드에서 "여전히 소식 없음으로
뒤집힌다"는 보고가 나오면 — 그때 필요한 것은 스위치가 아니라 **다른 신호**다(§9 기각 I 재검토).

---

### SL10 — 메인 세션 transcript 는 **신호로 쓰지 않는다** (측정 게이트 불통과)

**개정 이력**: 초안은 이 항목을 §9 기각 I(범위 밖)로 뒀다. 사용자가 **승인 항목 3 을
「함께 고친다」로 채택**해 그 기각을 철회했고, 이 결정으로 승격했다. 채택의 전제는 "측정이
받쳐주면"이었으며 §2.7 의 측정이 **받쳐주지 못했다** — 그래서 이 결정의 내용은 「채택」이
아니라 **「측정에 근거한 보류」**다. 전제가 바뀌면 결정을 공개적으로 뒤집는 이 저장소의
관례(RV1 이 「`done` 은 터미널」을, LS4 가 AR1/AR7 을 부분 번복한 선례)를 그대로 따른다.
초안의 기각 사유 ③("측정 근거가 없다")은 **해소됐다** — 측정했고, 결과가 반대였다.

**보류 사유 — §2.7 의 측정이 각각 독립적으로 치명적이다.**

| # | 측정 | 판정 |
|---|------|------|
| 1 | B 의 stale **519분 중 8분(1.5%)**만 회복된다(§2.7b) | **얻는 것이 사실상 없다.** B 의 분은 사람이 자리를 비운 긴 열린 턴에 몰려 있고 그 구간엔 파일 기록 자체가 없다 |
| 2 | stale 이 실제로 발동하는 긴 턴 창의 최장 침묵 **중앙값 29.16분 · 47%가 30분 초과**(§2.7c) | **안전 마진이 없다.** SL2 가 승인받은 근거(11.1분, 2.7~8.1배)에 대응하는 값이 여기엔 없다 — 여유 약 1.0배 |
| 3 | 턴 종료 후에도 `attachment`·`queue-operation` 이 기록되고(13/33 세션), **타임스탬프 없는 관리 줄 9종**이 `st_mtime` 을 움직인다(§2.7d) | **C(77.5%)를 깬다.** 4일 조용한 세션의 mtime 이 마지막 기록보다 중앙값 51시간 뒤다 |
| 4 | 추가 `stat()` **0회** — 이미 하고 있다(§2.7e) | 비용은 장애물이 **아니었다**. 보류 사유가 비용이 아님을 분명히 한다 |

**「`turn_state == "running"` 일 때만 본다」로 좁히면 되는가 — 안 된다(요구 3 의 답).**

좁히기는 측정 3(C 파괴)만 막고 측정 1·2 를 **전혀 건드리지 못한다.**

- **C 는 실제로 보호된다**: 조용한 세션은 `turn_state == "ended"` 다 — 재생에서 **마지막 턴이
  `Stop` 을 보지 못한 세션은 0 / 83 (0.0%)** 였다. 측정 3 의 51시간 드리프트 모집단은 게이트
  밖으로 빠진다.
- **그런데도 B 는 1.5% 밖에 살아나지 않는다.** 회복률은 게이트와 무관하게 "그 시점에 기록이
  있었는가"만으로 정해지고 답이 「없었다」이기 때문이다. 결국 **이득이 0 에 가까운 장치를 위해
  `stale` 의 정의를 전 세션 대상으로 바꾸는 것**이 되어 비용/편익이 성립하지 않는다.
- 요구 3 이 물은 반대 실패(턴 중 크래시로 `Stop` 이 안 뜬 세션이 영구 `working` 이 되어
  `stale` 상한을 잃는 것)는 **이 데이터에서 관측되지 않았다(0/83)** — 위험은 작다. 그러나
  위험이 작다는 것은 이득 없는 장치를 넣을 이유가 되지 못한다.

**대신 남기는 것(재방문 조건)**: 이 문제를 다시 다루려면 필요한 것은 `st_mtime` 이 아니라
**「마지막 *작업* 줄의 타임스탬프」**다 — 허브가 이미 읽는 128KiB 꼬리
(`hub_transcript.TRANSCRIPT_TAIL_BYTES`) 안에서 `assistant` 계열 줄만 골라 시각을 뽑으면
측정 3 은 피할 수 있다. 그러나 측정 1·2 는 그대로 남고(회복률은 파일 내용과 무관하다),
우리가 소유하지 않는 외부 형식의 **줄 종류 13종 이상을 분류하는 새 계약**이 생겨
`hub_transcript.py` 의 계약 표면이 크게 늘어난다. **재방문 트리거**: B 의 비중이 A 를
넘어서거나(지금 0.8% vs 21.7%), 긴 턴 창의 최장 침묵 중앙값이 문턱의 절반(15분) 아래로
내려가면 그때 그 방식으로 다시 측정한다.

**이 결정이 §5·§7·§11·§12 에 주는 영향: 없다.** 영향 범위·데이터 모델·테스트 계획·원장
행 계획·구현 순서, 그리고 `SOURCE_GUARD_ID_FLOOR`(491→495)·신규 서브체크 번호
(T25-222~T25-225)는 **초안 그대로**다 — 이 결정은 코드를 한 줄도 더하지 않는다.

---

## 5. 영향 범위

### 수정 파일 (5개 소스 + 4개 테스트 + 2개 문서)

| 파일 | 순수/IO | 변경 | 이유 |
|------|---------|------|------|
| `hub/bin/hub_subagent.py` | ★순수 | 상수 1개 추가 | `SUBAGENT_TRANSCRIPT_FILE_SUFFIX = ".jsonl"` — 파일 형식 상수는 파서 모듈에 둔다는 이 모듈의 관례(`SUBAGENT_META_FILE_SUFFIX`·`SUBAGENT_META_MAX_BYTES` 선례). **파서 함수는 추가하지 않는다** — 내용을 읽지 않으므로 팔 것이 없다 |
| `hub/bin/hub_subagent_read.py` | I/O | 함수 2개 + 경로 헬퍼 1개 (+약 40줄, 128 → ~170) | 새 파일 접근. `_is_safe_path_segment`·`observed_cwds` 순회를 그대로 재사용 |
| `hub/bin/hub_session.py` | ★순수 | 시그니처 4개 + 새 순수 함수 1개 (+약 25줄, 551 → ~576) | 판정 본체. 800줄 상한까지 224줄 여유 |
| `hub/bin/hub_project.py` | ★순수 | 배선만 — 인자 3곳 통과 (+약 5줄) | `subagent_meta_by_agent_id` 와 같은 경로 |
| `hub/bin/hub_collect.py` | I/O | `_read_session_annotations` 6번째 반환값 + `collect_snapshot` 전달 (+약 4줄, **775 → ~779**) | **800줄 상한까지 21줄뿐** — 그래서 새 I/O 함수는 `hub_subagent_read.py` 에 둔다(모듈 docstring 의 선례와 같은 이유) |
| `tests/hub/test_hub_session.py` | 테스트 | 클래스 1개 추가 | §7.1 |
| `tests/hub/test_hub_subagent_read.py` | 테스트 | 클래스 1개 추가 | §7.2 |
| `tests/hub/test_hub_project.py`·`test_hub_collect.py` | 테스트 | 각 1~2건 | §7.3 |
| `tests/run.sh` | 테스트 | T25-222~225 + `SOURCE_GUARD_ID_FLOOR` 491→495 | §7.4 |
| `tests/mutations.tsv` | 원장 | 변조행 4개 + 헤더 인용 1곳 갱신 | §7.5 |
| `hub/README.md` | 문서 | 좀비 가드 항목 개정 + 소식 없음 항목 보강 | §7.6 |
| `docs/prps/hub-dashboard.md` | 문서 | 「상태 판정 규칙 2」에 개정 화살표 1블록 추가 | §7.6 |

### 미영향 — 건드리지 않는 이유 (직접 확인함)

| 파일 | 왜 안 건드리나 |
|------|----------------|
| `hub/bin/hub_template.html` | 새 필드도 새 상태도 없다. `session.state` 값만 정확해진다. 툴팁 문구도 참으로 남는다(SL4 P4). `T25-93` 의 `run.is_running` 참조 수 4 고정이 그대로 유효 |
| `hub/bin/hub_model.py` | `HubSnapshot`·`HubConfig` 무변경. 새 config 키 없음(SL9) |
| `hub/bin/hub_live_session.py`·`_read.py` | 이 설계는 명부를 읽지도 쓰지도 않는다 — 그것이 SL4 P1 의 요점이다 |
| `hub/bin/hub_settings.py` | 훅을 추가하지 않는다(§9 기각 C) |
| `hub/bin/hub_hook.py` | 같은 이유 |
| `hub/bin/hub_transcript.py` · 메인 세션 transcript | 승인 항목 3 으로 한 번 채택됐다가 **측정 게이트 불통과로 보류**(결정 SL10, §2.7) — `SessionTail`·`parse_session_tail`·`_read_transcript_tail` 을 손대지 않는다. `st_mtime` 은 이미 부르는 `stat()` 에 들어 있으나 쓰지 않는다 |
| `rules/`·`agents/`·`commands/`·`CLAUDE.md` | 상시 컨텍스트 예산(T26) 대상 파일이다. 이 작업에 건드릴 이유가 **없다** |

---

## 6. 데이터 모델과 인터페이스

### 6.1 데이터 모델 — 변경 요약

```python
# 변경 없음: HookEvent · SubagentFact · SessionFacts · SubagentRunView · SessionView
#           ProjectView · HubSnapshot · HubConfig · Tier1Snapshot · LiveSessionIndex
#           PROJECT_STATE_PRIORITY · LIVE_SESSION_STATES · SUBAGENT_ZOMBIE_AFTER_MS
#
# 의미만 변경(타입·이름·JSON 키 전부 그대로):
#   SubagentRunView.is_running  "시작 후 90분 이내" → "시작 후 90분 이내 **또는** 마지막
#                                기록 후 90분 이내"
#   SessionView.state           stale 판정의 기준 시각이 '마지막 훅 이벤트' → '마지막으로
#                                알려진 활동'(훅 ∪ 미종료 실행 기록)
#
# 신설 상수 1개 (hub_subagent.py, ★순수)
SUBAGENT_TRANSCRIPT_FILE_SUFFIX = ".jsonl"

# 모듈 간 새 통신 타입: 없음. dict[str, int] (agent_id → epoch ms) 하나뿐이며
# subagent_meta_by_agent_id: dict[str, SubagentMeta] 와 같은 형태·같은 수명이다.
```

> **`dict[str, int]` 로 충분한가** — 예. 값이 "시각 하나"뿐이라 frozen dataclass 로 감쌀
> 이유가 없다(YAGNI). `agent_id` 가 세션 간에 충돌하면 나중 것이 이긴다는 성질은
> `read_subagent_metas` 가 이미 갖고 있는 **기존 속성**이며 이 설계가 새로 만드는 것이
> 아니다(§11 리스크 R3).

### 6.2 `hub/bin/hub_subagent_read.py` (I/O, 수정)

```python
def _subagent_transcript_path(
    session_id: str, cwd: str, agent_id: str, projects_dir: Path
) -> Path:
    """agent-<id>.jsonl 의 조립 경로. _subagent_meta_path 와 접미사만 다르다."""


def read_subagent_activity_at_ms(
    session_id: str, observed_cwds: Sequence[str], agent_id: str, projects_dir: Path
) -> int | None:
    """실행 1건의 transcript 마지막 기록 시각(ms). 없거나 stat 실패면 None — 절대 예외를
    던지지 않는다.

    경로 조립·안전성 검사·observed_cwds 순회는 read_subagent_meta 와 **같은 규칙**이다
    (결정 AR3 — glob 하지 않는다, `/`·""·"."·".." 를 걷어낸다, 먼저 존재하는 것을 쓴다).
    파일 **내용을 읽지 않는다** — stat 1회로 끝난다(결정 SL1).
    """


def read_unfinished_subagent_activity(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]], projects_dir: Path
) -> dict[str, int]:
    """미종료 실행(ended_at_ms is None)의 {agent_id: 마지막 기록 시각(ms)}.

    `record_prompt_excerpt` 인자를 **받지 않는다**(결정 SL7) — mtime 은 프롬프트 발췌가
    아니므로 그 게이트 안에 넣으면 설정을 끈 사용자에게만 결함이 남는다.
    경고를 돌려주지 않는다(결정 SL8). 세션당 읽는 수는 `_agent_ids_to_read` 와 같은
    예산(SUBAGENT_RUN_MAX_PER_SESSION)으로 묶는다.
    """
```

### 6.3 `hub/bin/hub_session.py` (★순수, 수정)

```python
def is_running_subagent(
    subagent: SubagentFact,
    now_ms: int,
    zombie_after_ms: int,
    last_activity_at_ms: int | None = None,   # 신규, 기본값 None = 오늘의 판정
) -> bool


def last_known_activity_at_ms(                 # 신규 (★순수)
    facts: SessionFacts,
    subagent_activity_by_agent_id: dict[str, int] | None = None,
) -> int


def _compute_base_state(
    facts: SessionFacts, now_ms: int, zombie_after_ms: int, roster: RosterState,
    subagent_activity_by_agent_id: dict[str, int] | None = None,   # 신규
) -> Literal["working", "idle", "done"]


def compute_session_view(
    ..., subagent_meta_by_agent_id=None,
    subagent_activity_by_agent_id: dict[str, int] | None = None,   # 신규
    live_roster=None,
) -> SessionView


def summarize_agent_runs(
    facts, now_ms, zombie_after_ms=SUBAGENT_ZOMBIE_AFTER_MS,
    subagent_meta_by_agent_id=None, previous_task_boundary_ms=None,
    subagent_activity_by_agent_id: dict[str, int] | None = None,   # 신규
) -> tuple[SubagentRunView, ...]
```

**기본값 정책**: 신규 인자는 전부 `None` 기본값이고 **마지막 위치**에 붙인다
(`live_roster` 는 `compute_session_view` 의 마지막을 유지 — 신규 인자를 그 앞에 둔다).
기존 호출부(비테스트 3곳 + 테스트 다수)는 **한 줄도 바뀌지 않는다**.

> **GOTCHA — `T25-93` 은 `zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS` 문자열이 정확히
> **2건**일 것을 요구한다.** 신규 인자는 `zombie_after_ms` 기본값을 **새로 만들지 않으므로**
> 그 수는 2 그대로다. `is_running_subagent` 의 `zombie_after_ms` 는 오늘도 기본값 없는 필수
> 인자이며 그대로 둔다.

### 6.4 `hub/bin/hub_project.py` (★순수, 배선만)

`_session_views_for_path` · `_project_view_for_path` · `compose_project_views` 세 함수가
`subagent_activity_by_agent_id: dict[str, int] | None = None` 를 받아 그대로 통과시킨다 —
`subagent_meta_by_agent_id` 와 **완전히 같은 경로**(세션에 스코프되지 않는 전역 맵, 판단 없이
전달). 새 판정은 하나도 넣지 않는다.

### 6.5 `hub/bin/hub_collect.py` (I/O, 배선만)

`_read_session_annotations` 가 6번째 값으로 `dict[str, int]` 를 반환하고,
`collect_snapshot` 이 `compose_project_views` 에 넘긴다.

```python
subagent_activity_by_agent_id = hub_subagent_read.read_unfinished_subagent_activity(
    sessions_by_path, PROJECTS_DIR
)
```

> `record_prompt_excerpt` 를 넘기지 않는 유일한 서브에이전트 읽기다 — 그 자리에 함께
> 적어 둔다(결정 SL7). `read_live_session_roster` 가 같은 줄 아래에서 같은 성질을 갖는다.

> **YAGNI 경계**: 반환 튜플이 5 → 6 으로 늘어난다. 7번째가 생기면 그때
> `SessionAnnotations` frozen dataclass 로 묶는다 — 지금 묶으면 호출부 1곳을 위한 타입을
> 미리 만드는 것이라 추측성 추상화다.

---

## 7. 테스트 계획

### 7.1 `tests/hub/test_hub_session.py` — 신규 클래스 `SubagentLivenessSignalTest`

`SubagentZombieGuardTest`(결정 ZG)와 같은 형태의 표 기반. 전부 ★순수 — 파일을 만들지 않고
`dict[str, int]` 를 직접 넘긴다.

| ID | 입력 | 기대 | 성공기준 |
|----|------|------|----------|
| `SL-U1` | 미종료 실행, 마지막 훅 42분 전, 활동 1분 전, `stale=30분` | `state == "working"` — **현행 코드에서는 `"stale"`(버그 재현)** | G1 |
| `SL-U2` | 미종료 실행, 시작 98분 전, 활동 1분 전 | `base_state == "working"` · 칩 `is_running is True` — **현행 `"idle"`/`False`** | G2 |
| `SL-U3` | 위 둘과 같은 사실, **활동 dict 없이** 호출 | 오늘의 기대값 그대로(`"stale"` / `"idle"`) — 무동작 회귀 고정 | G3 |
| `SL-U4` | 미종료 실행, 시작 후 5분에 활동 정지, `now = 활동 + 90분` | `is_running is False` — 상한이 살아 있다 | G4 |
| `SL-U5` | 같은 열, `now = 활동 + 90분 − 1ms` | `is_running is True` — 경계는 `<`(ZG3 와 같은 관례) | G4 |
| `SL-U6` | **종료된** 실행 + 그 agent_id 에 방금 시각의 활동 | `is_running is False` · `base_state` 에 기여하지 않음 — 종료 검사가 먼저다(결정 SL3) | — |
| `SL-U7` | 뷰 하나에서 동시 단정 | `base_state == "working"` **이면** `any(run.is_running for run in view.agent_runs)` — 상태·칩 모순 금지 | G6 |
| `SL-U8` | `live_roster=None` 과 `roster="not_listed"` 두 경우에 활동 dict 동일 | **`is_stale` 값이 두 경우에 같다** — stale 이 roster 와 독립임을 단정(LS9 P1) | G5 |
| `SL-U9` | 미종료 실행 2건(하나는 조용, 하나는 활발) | 세션 `state == "working"` — `max` 가 맞다 | — |
| `SL-U10` | 같은 사실에 활동 시각만 1ms 씩 다른 뷰 2개 | `dataclasses.asdict` 결과가 **동일** — mtime 이 뷰에 새지 않는다 | G9 |
| `SL-U11` | 활동 dict 에 그 세션과 무관한 agent_id 만 있음 | 오늘의 판정 그대로 — 조회 실패가 무해하다 | — |
| `SL-U12` | `now_ms < 활동 시각`(시계 역행) | `is_running is True` — 안전한 방향(ZG5 선례) | — |

### 7.2 `tests/hub/test_hub_subagent_read.py` — 신규 클래스 `ReadUnfinishedSubagentActivityTest`

> **개정됨(2026-10-07, [`hub-live-activity.md`](./hub-live-activity.md) §10.2)** — 이 클래스는 파일 분리로 `tests/hub/test_hub_subagent_read_activity.py` 로 옮겨졌다. 아래는 작성 시점의 기록이다.

`ReadSubagentMetaTest` 와 같은 tempdir 관례.

| ID | 시나리오 | 기대 |
|----|----------|------|
| `SL-R1` | `.jsonl` 존재 | `stat().st_mtime * 1000` 값을 돌려준다 |
| `SL-R2` | `.jsonl` 부재(`.meta.json` 만 있음) | `None` — 예외 없음 |
| `SL-R3` | 두 번째 `observed_cwd` 에만 존재(워크트리) | 찾아낸다 |
| `SL-R4` | `session_id`·`agent_id` 에 `/`·`.`·`..` | 조립 전에 거부(`None`) |
| **`SL-R5`** | **`record_prompt_excerpt` 를 흉내 낸 어떤 조건에서도 읽는다** — 시그니처에 그 인자가 **없음**을 단정 | **함정 PS7 회귀 방지**(G8) |
| `SL-R6` | 종료된 실행만 있는 세션 | 빈 dict — 파일이 있어도 읽지 않는다(SL3). `unittest.mock` 으로 stat 호출 0회 확인 |
| `SL-R7` | 세션당 실행 100건 초과 | `SUBAGENT_RUN_MAX_PER_SESSION` 으로 잘린다 |
| `SL-R8` | 디렉터리 권한 거부 | `None`, 예외 없음, **경고도 없음**(SL8) |

### 7.3 `test_hub_project.py` · `test_hub_collect.py`

- `SL-P1`: `compose_project_views` 에 활동 dict 를 넘기면 프로젝트 `state == "working"`
  (G7). 넘기지 않으면 오늘의 값.
- `SL-C1`: `_read_session_annotations` 가 6개 값을 돌려주고 6번째가 dict 다.
- `SL-C2`: `collect_snapshot` 이 그 값을 `compose_project_views` 에 전달한다
  (`mock.patch.object` 로 인자 확인).

### 7.4 `tests/run.sh` — T25 그룹 신규 서브체크 4종 (T25-222 ~ T25-225)

현재 최대 서브체크 ID 는 `T25-221`. 전부 **함수명·상수명 앵커**만 쓰고 줄 번호를 인용하지
않는다.

| ID | 검사 | 왜 기계가 봐야 하나 |
|----|------|---------------------|
| `T25-222` | ① `hub_subagent_read.py` 에 `def read_unfinished_subagent_activity(` 가 있다 ② **역방향** — 그 함수 시그니처와 `_read_session_annotations` 의 호출 양쪽에 `record_prompt_excerpt` 가 **없다** | 함정 PS7. 게이트 안으로 들어가는 실수는 리뷰로만 잡히고 테스트로는 안 잡힌다(설정을 끈 환경에서만 발현) |
| `T25-223` | ① `_compute_base_state`·`summarize_agent_runs` 두 본문 모두 `is_running_subagent(` 를 호출한다(T25-92·T25-207 승계) ② 두 본문 모두 `subagent_activity_by_agent_id` 를 그 호출에 넘긴다 ③ **역방향** — `SessionView` 본문에 `activity` 를 포함하는 새 필드가 없다 | 상태·칩 단일 판정자(G6)와 D2 방어(G9)를 동시에 문다 |
| `T25-224` | `compute_session_view` 본문에서 `is_stale` 대입식이 `last_known_activity_at_ms(` 를 경유하고, `last_known_activity_at_ms` **함수 본문**에 `roster` 가 등장하지 않는다 | **결정 LS9 의 독립 상한을 기계가 문다**(G5). 이 설계에서 가장 값진 가드 |
| `T25-225` | ① `SUBAGENT_ZOMBIE_AFTER_MS = 90 * 60 * 1000` 리터럴이 그대로다(T25-91 재확인 — 상수를 올리는 우회를 막는다) ② `hub/README.md` 와 `docs/prps/hub-dashboard.md` 에 개정 토큰이 있다 | §9 기각 G(상수 인상)로 되돌아가는 것을 막는다 |

**`SOURCE_GUARD_ID_FLOOR` 491 → 495**(+4, 신규 ID 접두 4종). 인상 사유를 그 상수 주석에
한 줄로 남긴다 — 그 저장소 관례가 요구한다.

### 7.5 `tests/mutations.tsv` — 변조행 4개 (계획만, 작성은 구현 단계)

전부 `hub/bin/*.py` 를 겨눈 8열 TSV 변조행이며 `mutation_sed` 는 `[addr]s/…/…/[flags]`
형태(`/` 구분자, `w`·`W`·`r`·`R`·`e` 금지)를 지킨다.

| guard_id | target_path | 변조 취지 | 흉내내는 실제 결함 |
|----------|-------------|-----------|--------------------|
| `T25-222` | `hub/bin/hub_subagent_read.py` | 시그니처에 `record_prompt_excerpt` 인자를 되살린다 | 프라이버시 설정을 끈 사용자에게만 결함이 남는 것 |
| `T25-223` | `hub/bin/hub_session.py` | `summarize_agent_runs` 의 `is_running_subagent` 호출에서 활동 인자를 뗀다 | 카드 상태와 칩이 어긋나는 GOTCHA 4 의 이번 판 |
| `T25-224` | `hub/bin/hub_session.py` | `is_stale` 대입식을 `facts.last_event_at_ms` 직접 참조로 되돌린다 | 결함이 조용히 재발하는 것(이 PRP 의 출발점) |
| `T25-225` | `hub/bin/hub_session.py` | 상수를 `180 * 60 * 1000` 으로 바꾼다 | 신호를 안 쓰고 상한만 올리는 우회(§9 기각 G) |

**원장 상수 영향**:
- `LEDGER_MUTATION_ROW_FLOOR`(100)은 **하한**이라 행을 더해도 만족된다 → 인상 불필요.
- `LEDGER_EXEMPT_ROW_RATCHET`(382)은 면제행 **상한** — 신규 4행은 전부 변조행이므로 무영향.
- **`SOURCE_GUARD_ID_FLOOR` 를 올리면 원장 헤더의 그 인용도 함께 고쳐야 한다** —
  `verify_ledger_header_citations`(T99-6)가 헤더의 `SOURCE_GUARD_ID_FLOOR(491 — …)` 값을
  상수와 대조한다. 같은 함정에 아홉 번 걸린 이력이 그 행의 `defect_description` 에 적혀
  있다. **구현 단계 체크리스트의 마지막 항목으로 박는다.**

### 7.6 문서 정합 (기계가 무는 토큰)

- **`docs/prps/hub-dashboard.md` 「상태 판정 규칙 2」** — 기존 ZG 개정 블록 **아래에**
  개정 화살표를 한 블록 더 붙인다(원문 코드블록·기존 개정 블록 **삭제 금지**, GOTCHA 10 관례).

  > **개정 →(결정 SL1~SL9, `hub-subagent-liveness-signal.md`)**: 규칙 2 의 `stale` 오버레이
  > 기준 시각이 `last_event_at_ms` 에서 **「마지막으로 알려진 활동」**(= 마지막 훅 이벤트와
  > 미종료 서브에이전트 실행들의 transcript 마지막 기록 중 최댓값)으로 넓어진다. 또
  > `working` 의 서브에이전트 항은 "시작 후 90분 이내" **또는** "마지막 기록 후 90분 이내"로
  > 넓어진다 — 실행 중에 발화하는 훅이 하나도 없어 42분짜리 정상 실행이 카드를
  > 「소식 없음 · 직전 대기」로 뒤집던 결함의 수정이다. `SUBAGENT_ZOMBIE_AFTER_MS`(90분)는
  > 값도 이름도 그대로이며, **`live_roster` 는 여전히 `stale` 판정에 섞이지 않는다**(LS9).

- **`hub/README.md`** — 「좀비 서브에이전트 가드」 항목에 "마지막 기록 이후"를 더하고,
  「소식 없음」 관련 서술에 "도는 중인 서브에이전트가 기록을 남기는 동안에는 소식 없음으로
  뒤집히지 않는다"를 더한다. `T25-94` 가 무는 기존 토큰(`— CSS 가 숨긴다` 부재 등)은 건드리지
  않는다.

### 7.7 검증 명령 (정본, `CLAUDE.md` §4)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

> **금지**: `python3 hub/bin/hub.py collect` 실행(사용자의 실제 `~/.claude/hub/hub.html` 을
> 덮어쓴다) · 이 저장소 안에서 `install.sh --scope project` · 실제 `$HOME` 대상 설치.

---

## 8. 보안

| 항목 | 판정 |
|------|------|
| 계약 A(redact → clip) 적용 | **불필요** — 뷰로 나가는 값이 없다. 읽는 것은 `st_mtime`(정수) 하나이고 그 값은 판정에만 쓰인다(SL5). 결정 LS13 과 같은 「면제가 아니라 경로 부재」 |
| 파일 **내용** 노출 | **0** — `read_text` 를 부르지 않는다. 서브에이전트 transcript 는 프롬프트 전문·도구 출력이 든 가장 민감한 파일인데, 이 설계는 **그 파일을 열지 않는다** |
| 경로 조립 | `read_subagent_meta` 와 **같은 가드**(`_is_safe_path_segment` — `/`·""·"."·".." 거부). 새 입력원이 없다 — `session_id`·`agent_id` 는 이미 조립에 쓰이는 값이다 |
| 경고 문자열 | 없다(SL8) — 경로가 로그로 샐 지점이 0 |
| 크기 상한 | 불필요 — `stat()` 은 파일 크기와 무관하게 O(1) |

---

## 9. 기각한 대안

| # | 대안 | 기각 사유 |
|---|------|-----------|
| **C** | **`PostToolUse` 등 실행 중 훅 추가** | **기각.** ① 이벤트가 하루 100건 → 수천 건이 되고 `read_recent_events` 가 2일치를 매 수집마다 전부 파싱한다 ② `hub_hook.py` 의 절대 규칙("세션을 막지 않는다")과 정면 충돌 — 도구 호출마다 append + spawn 이 붙는다 ③ **우리가 이미 갖고 있는 신호를 위해 사용자 세션에 비용을 매긴다**. 파일은 이미 거기 있다 |
| **D** | **실행 중이면 `stale` 판정 자체를 유예**(`has_running_subagent` 면 stale 스킵) | **기각.** 1줄이지만 결정 LS9 를 그냥 깎는다 — 좀비 1건이 `stale` **상한 자체를 무한으로** 만든다(오늘 90분 상한이 있는 것과 대조). SL4 는 상한을 유지한 채 기준 시각만 옮기므로 이 대안이 주는 것을 전부 주면서 안전망을 남긴다 |
| **E** | **`SessionFacts.last_event_at_ms` 자체를 넓힌다** | **기각.** ① `SessionFacts` 는 "훅 이벤트를 접은 **사실**"이고 파일 mtime 은 조회 시점의 해석이다 — 결정 ZG5 가 같은 이유로 "좀비 제거한 `SessionFacts` 사본"을 기각했다 ② 그 값은 `is_session_tier1_from_finished_task` 의 Δ 판정과 `_last_activity_at_ms`(프로젝트 정렬), 클라이언트의 경과 라벨·12시간 숨김이 함께 쓴다 — 넓히면 네 판정이 동시에, 각각 다른 방향으로 흔들린다 |
| **F** | **활동 시각을 `SessionView`·`SubagentRunView` 에 싣는다** | **기각.** `snapshot_content_key` 가 매 수집마다 바뀌어 `hub.html` 쓰기 억제가 무력해진다 — 결정 LS10 이 `updatedAt` 을 거부한 것과 **같은 실패**. 얻는 것(툴팁에 "마지막 기록 N분 전")은 요구에 없다 |
| **G** | **`SUBAGENT_ZOMBIE_AFTER_MS` 를 180분 등으로 올린다** | **기각.** ① 결함의 절반(`stale` 오버레이)을 **전혀** 고치지 못한다 — 30분에 「소식 없음」이 그대로 뜬다 ② 좀비의 sticky-working 상한을 2배로 늘리는 순수 손실 ③ 실측 최장이 47.3 → 98.4분으로 2년 사이 2배가 된 것이 보여주듯, **상수를 고르는 방식 자체가 실패**했다. 신호를 보는 쪽이 옳다. → `T25-225` 가 이 우회를 기계로 막는다 |
| **H** | **`meta.json` 의 `requestShape` 로 foreground 실행만 특별 취급** | **기각.** 커버리지 7.2%(E4)로 판정을 세울 수 없고, **이 설계가 그 구분을 필요로 하지 않는다** — 두 종류 모두 transcript 를 append 한다. YAGNI |
| **I** | **같은 신호를 메인 세션 transcript(`<session_id>.jsonl`)에도 적용** — 긴 메인 턴의 「소식 없음」도 함께 고친다 | **기각 → 사용자가 승인 항목 3 으로 채택(기각 철회) → 측정 후 결정 SL10 으로 보류.** 초안의 기각 사유 ③ "측정 근거가 없다"는 §2.7 이 해소했다 — 그러나 결과가 **반대 방향**이었다: B 의 stale 519분 중 회복 **8분(1.5%)** · stale 이 발동하는 긴 턴 창의 최장 침묵 중앙값 **29.16분**(문턱과 같은 자리, 47%가 초과) · 턴 종료 후와 세션 사망 후에도 `st_mtime` 이 움직인다(중앙값 **51시간** 드리프트). 추가 비용은 **0**이었으나(이미 `stat` 한다) 신호 품질이 미달이다. 전문은 **결정 SL10** |
| **J** | **침묵 임계값을 `stale_after_ms`(30분)로 따로 두어 좀비를 더 빨리 잡는다**(대체 semantics) | **기각(지금은).** 측정상 성립한다 — 창 안 최장 침묵 11.1분 대비 30분은 2.7배 여유이고, 이는 결정 ZG2 가 승인받은 여유(1.9배)보다 **더 보수적**이다. 얻는 것: E3 의 고아 6건이 90분이 아니라 36.6~84.3분에 잡힌다. **그럼에도 기각하는 이유**: ① 요구에 없는 개선이고(오늘의 좀비 검출은 이미 상한이 있다) ② `True→False` 로 뒤집을 수 있는 유일한 형태라 SL2 의 단조성(=회귀 위험 0)을 잃는다 ③ 임계값이 둘이 되면 "어느 쪽이 발동했는가"가 진단에서 안 보인다. **revisit 트리거**: sticky-working 재보고, 또는 2일 창 미종료 실행 수가 4를 크게 넘기 시작하면 |

> **과제가 제시한 방향 B 에 대한 정정**: "`max(started_at, last_append)` 로 바꾸면 5분 만에
> 죽은 실행이 90분이 아니라 35분에 잡힌다"는 **같은 상수를 쓰는 한 성립하지 않는다** —
> `last_append >= started_at` 이므로 상한이 **늦어진다**(5+90=95분). 그 이득을 얻으려면
> **두 번째·더 짧은 임계값**이 필요하고, 그것이 위 대안 J 다. 이 문서는 단조성을 택해
> J 를 보류했다.

---

## 10. 프리뷰 목업 — **불필요**(판단 근거)

이 설계는 `hub_template.html` 을 **0줄** 바꾼다. 새 마크업·클래스명·색 토큰·레이아웃·모션이
하나도 없고, 바뀌는 것은 기존 렌더러가 이미 그리는 **배지의 값**뿐이다:

```
현재:  [소식 없음 · 직전 작업중]   →  (90분 후) [소식 없음 · 직전 대기]
제안:  [작업중]                    (실행이 기록을 남기는 동안 계속)
```

`STATE_LABEL`·`STATE_GLYPH`·`state-working` CSS 클래스·카드 glow 는 전부 **이미 존재하고
이미 이 값들을 그린다** — 목업이 보여줄 새 시각 요소가 없다. 「현재 vs 제안」의 대조도 위 두
줄이 전부다.

---

## 11. 리스크와 완화

| # | 리스크 | 완화 |
|---|--------|------|
| **R1** | 호스트가 `subagents/*.jsonl` 경로·형식을 바꾸면 신호가 사라진다 | **폴백이 곧 오늘의 동작**이다(SL2 단조성) — 결함이 되돌아올 뿐 새 고장은 없다. 경로 계약은 `hub_subagent_read.py` 한 파일에 갇혀 있다(결정 AR2 의 목적) |
| **R2** | 측정한 침묵 천장 11.1분이 다른 워크로드에서 깨진다(예: 중첩 서브에이전트가 오래 도는 동안 부모 transcript 가 조용) | **상한 대비 8.1배 여유**가 있다. 그리고 중첩(spawnDepth 2, 실측 2.8%)의 경우 자식도 미종료 실행이면 그 자식의 활동이 `max` 에 들어가 세션은 계속 `working` 이다 — 부모 **칩 하나**가 중립색이 되는 것이 최악이다(카드 상태는 안 흔들린다) |
| **R3** | `agent_id` 가 세션 간에 충돌하면 남의 활동 시각을 읽는다 | **기존 속성**이다 — `read_subagent_metas` 가 이미 `dict[str, SubagentMeta]` 를 agent_id 로만 키잉한다(§2.4 의 3/119 이상치가 그 흔적). 이 설계가 새로 만들지 않고, 결과의 방향도 "working 이 조금 더 오래 유지된다"로 안전한 쪽이다. 고치려면 키를 `(session_id, agent_id)` 로 바꾸는 별도 변경이 필요하고 그것은 이 결함과 무관하다 |
| **R4** | `hub_collect.py` 가 779/800 줄이 되어 다음 기능이 못 들어간다 | 이 설계가 새 I/O 를 전부 `hub_subagent_read.py` 에 둔 이유다. 다음 회차가 이 파일을 또 늘려야 하면 그때 분리한다(결정 MS1 의 기존 절차) |
| **R5** | 수집 비용 증가 | 실측 상한 `stat()` 4~8회/수집(§2.6). 기존 서브에이전트 syscall 예산의 1/3 증가가 구조적 상한. `collect_snapshot` 이 50ms 를 넘기면 재검토(결정 MD4·WF10·LS11 과 같은 에스컬레이션 조건) |

---

## 12. 구현 순서 (검증 가능한 단계)

| # | 단계 | 검증 |
|---|------|------|
| 1 | `hub_subagent.py` 에 `SUBAGENT_TRANSCRIPT_FILE_SUFFIX` 추가 | `python3 -m py_compile hub/bin/*.py` |
| 2 | `hub_subagent_read.py` 에 함수 2개 + 경로 헬퍼 (RED: `SL-R1`~`SL-R8` 먼저) | `python3 -m unittest discover -s tests/hub -t .` |
| 3 | `hub_session.py` — `is_running_subagent` 4번째 인자 + `last_known_activity_at_ms` + 시그니처 3개 (RED: `SL-U1`~`SL-U12` 먼저) | 같은 명령. **`SL-U3` 가 무동작을 고정한다** |
| 4 | `hub_project.py`·`hub_collect.py` 배선 (RED: `SL-P1`·`SL-C1`·`SL-C2` 먼저) | 같은 명령 |
| 5 | `tests/run.sh` T25-222~225 + `SOURCE_GUARD_ID_FLOOR` 495 | `bash tests/run.sh` |
| 6 | `tests/mutations.tsv` 변조행 4개 **+ 헤더의 `SOURCE_GUARD_ID_FLOOR` 인용 495 로 갱신** | `bash tests/run.sh`(T37·T99 계열) |
| 7 | `hub/README.md`·`docs/prps/hub-dashboard.md` 개정 | `bash tests/run.sh`(T25-225·T25-94) |
| 8 | 전체 검증 4종(§7.7) | 전부 통과 |

> 5·6 단계의 뮤테이션 확인은 **변조 → 실패 확인 → 되돌리기** 순서로 1회씩 돌린다. 특히
> `T25-224`(stale 이 roster 와 독립) 변조가 **실제로 발화하는지**를 눈으로 본다 — 이 설계에서
> 유일하게 「기존 결정을 건드리는」 항목이기 때문이다.

---

## 13. 승인 요청 항목

### 승인 항목 1 — `stale` 오버레이를 넓히는 것 자체 (결정 SL4)

결정 LS9 는 `stale` 을 "훅 유래 그대로" 두기로 했다. 이 설계는 그 기준 시각에 **미종료
서브에이전트 실행의 transcript 기록 시각**을 더한다. §4 SL4 의 P1~P4 가 LS9 의 두 근거(독립
상한 · 다른 질문)가 **보존됨**을 논증하고, LS9 자신이 이 항목을 「별도 결정 필요」로 유보해
둔 것을 근거로 든다. **승인하면**: 42분짜리 실행 중에도 카드가 「작업중」을 유지한다. 대신
`stale` 의 정의가 "마지막 훅 이벤트로부터"에서 "마지막으로 알려진 활동으로부터"로 바뀐다.

### 승인 항목 2 — 좀비 판정을 **덧셈**으로 넓히고 90분 상수는 그대로 둔다 (결정 SL2, 대안 J 보류)

`is_running_subagent` 가 `True` 로 갈 길을 하나 더 열되(단조), 대체하지 않는다. 결과:
정상 실행의 glow 가 꺼지는 회귀 위험 0 · 상수·기존 테스트 무변경. **대가**: 진짜 좀비의
sticky-working 최악 구간이 90분 → 144분으로 늘어난다. 더 빠른 검출(대안 J, 30분 침묵
임계값)은 측정상 가능하지만 요구 범위를 넘어 보류했다. **이 대가를 받아들일지**가 질문이다.

### 승인 항목 3 — 메인 세션 transcript 절반: **채택 → 측정 게이트 불통과 → 보류** (결정 SL10)

**경과**: 초안은 이것을 §9 기각 I(범위 밖)로 뒀고, 사용자가 **「함께 고친다」로 결정**해
기각을 철회했다. 채택의 전제는 "측정이 받쳐주면"이었다. §2.7 에서 다섯 가지를 쟀고 **전제가
충족되지 않았다** — 판정의 정본은 결정 SL10 이다.

| 물음 | 답 |
|---|---|
| 얼마나 고치는가 | B 의 stale **519분 중 8분(1.5%)**. B 의 분은 사람이 자리를 비운 긴 열린 턴에 몰려 있어 파일에도 기록이 없다 |
| 안전 마진은 | **없다.** stale 이 발동하는 긴 턴 창의 최장 침묵 중앙값 **29.16분**(문턱 30분)이고 47%가 초과. SL2 의 11.1분(2.7~8.1배 여유)에 대응하는 값이 여기엔 없다 |
| C(77.5%)를 깨는가 | **깬다.** 턴 종료 후 기록(13/33 세션) + 타임스탬프 없는 관리 줄 9종이 `st_mtime` 을 움직여, 4일 조용한 세션의 mtime 이 마지막 기록보다 중앙값 **51시간** 뒤다 |
| 비용은 | **0** — `_read_transcript_tail` 이 이미 매 수집마다 그 파일을 `stat` 한다. 비용은 장애물이 아니었다 |
| 좁히면(턴 진행 중에만) 되는가 | C 는 보호되지만(`Stop` 못 본 세션 0/83) **B 의 1.5% 는 그대로다** — 이득 없는 장치를 위해 `stale` 의 정의를 전 세션 대상으로 바꾸게 된다 |

**필요한 회신**: 이 보류를 받아들이는지. **받아들이면** 이 PRP 는 **원안(SL1~SL9) 그대로**
구현 단계로 넘어간다 — §5 영향 범위, §7 테스트·원장 계획, §12 구현 순서의 숫자는 전부 변경
없다. **받아들이지 않고 그래도 넣기를 원하면**, 필요한 것은 `st_mtime` 이 아니라 transcript
꼬리에서 **작업 줄만 골라내는 새 파싱 계약**이며(SL10 재방문 조건) 그것은 별도 측정과 별도
설계가 필요하다 — 이 PRP 의 범위에서는 만들 수 없다.
