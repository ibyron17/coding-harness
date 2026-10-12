# 허브 세션 트리 UI + 세션별 대시보드 파일 분리

> 결정 접두: **ST**(Session Tree). `grep -rhoE "결정 [A-Z]{1,3}[0-9]+" docs/prps/*.md` 로 미사용임을 확인했다(2026-09-02).
> 상태: **승인됨(2026-09-02)** — §20 승인 항목 1~6 전부 권고안대로 확정, §22 미결 질문 1~4 도 권고안대로(카드 기본값 · 리텐션 7일 · 폴백 보고 1줄 · 사람 아이콘 없음). 구현 코드는 이 문서에 없다.
> 기준 커밋 `d193b6c`(`main`). 인용한 행 번호는 전부 그 시점의 실측이다.
>
> 이 문서는 [`dashboard-ownership-guard.md`](dashboard-ownership-guard.md) §R4 가 보류한 「안 1(세션별
> 대시보드 파일 분리)」의 **재방문**이자, 허브 쪽 정본 사슬(`hub-dashboard.md` → … →
> `hub-tier1-clamp-fix-and-session-model.md`)의 다음 개정이다. 두 사슬을 한 문서로 잇는 이유는 §7·§8 에 있다
> — 파일 체계(쓰기 쪽)와 허브 발견(읽기 쪽)은 같은 키(세션 ID)로 맞물려야 하며, 따로 설계하면 어긋난다.

---

## 0. 한눈에

| 항목 | 값 |
|------|-----|
| 요구 | **R1** 허브에서 한 프로젝트의 여러 메인 세션을 **조직도형 트리**로 본다. **R2** 트리의 세션 노드를 클릭하면 상세 패널이 **그 세션의** 대시보드를 띄운다 |
| 왜 지금인가 | R4 보류 근거 4개 중 1(동시 작업이 드물다)·2(세션 ID 를 알 수 없다)가 실측으로 무효화됐고(§2), 재방문 트리거 T-1·T-4 가 발동했다 |
| 핵심 결정 | 대시보드 파일을 **`.claude/dashboards/<CLAUDE_CODE_SESSION_ID>.html`** 로 쪼갠다(ST1). 허브는 레거시 단일 파일과 세션별 파일을 **둘 다 읽고**, 프로젝트 요약은 종전대로 mtime 최신(WT6 확장), 세션 노드는 자기 파일(ST9~ST12). 트리는 **헤더 보기 토글(카드/트리)** 로 켜는 별도 모드이며 기본값은 카드(ST17). 패널 신원은 `(projectPath, sessionId)` 로 확장한다(ST23) |
| 변경 규모 | XL 급이지만 **새 모듈 0개, 새 의존성 0개, 새 서버 라우트 0개**(ST13·ST15). 마일스톤 3개로 독립 배포·검증(§13). 배포 순서는 **M2(허브 Python) → M1(`/dashboard`) → M3(허브 템플릿)** |
| 승인 필요 | §20 의 6개 항목 |

---

## 1. 요구사항 요약

프로젝트에서 메인 세션이 여럿 동시에 돌 때(실측 최대 coding-harness 4·atlas 5·daily-brief 3, §2 F4), 지금
허브는 카드 하나에 세션 줄 N개를 나열하고, 상세 패널은 **프로젝트당 1파일**(`.claude/dashboard.html`)
— 마지막에 `init` 한 세션의 것 — 만 보여준다. 다른 세션의 진행률은 어디에서도 볼 수 없고, `init`
충돌은 확인 프롬프트(결정 O5)로만 막고 있다. 이 세션 자체가 그 충돌 사례다: `init` 0단계가 `RECENT`
+ 타 세션 토큰 `4dba59f0`(제목 「릴리스 트랙 R1~R3 + CLAUDE.md 분리」, mtime 10:17)을 냈고, 메인 세션은
대시보드 없이 진행 중이다.

사용자가 원하는 것은 둘이다 — 첨부 이미지(조직도: 루트 1 → 2단 2 → 3단 4 → 잎 12, 사람 아이콘 +
라벨 박스, 직각 꺾임 연결선, 위→아래)**처럼** 세션들을 트리로 보는 것(R1)과, 세션 노드를 눌러 **그
세션의** 대시보드를 패널에서 보는 것(R2). "처럼"이므로 시각적 유사성이 목표이고 픽셀 복제가 아니다.
이 프로젝트에 대응시키면 **루트 = 프로젝트, 2단 = 메인 세션, 3단 = 그 세션이 띄운 서브에이전트**가
자연스럽다.

### 사용자 스토리

- 동시에 여러 작업을 돌리는 사용자로서, 허브를 열면 프로젝트 아래 어느 세션이 무엇을 어디까지 했는지
  트리 한 장에서 읽고 싶다 — 카드 안 세션 줄을 스크롤하며 발췌를 대조하는 대신.
- 그 사용자로서, 세션 노드를 누르면 **그 세션의** 대시보드(단계·구현 세부·작업 추적 로그)를 패널에서
  보고 싶다 — 마지막에 `init` 한 세션의 것이 아니라.
- 오케스트레이터(메인 세션)로서, 다른 세션이 쓰고 있는 대시보드를 덮어쓸지 묻는 프롬프트를 더 보고
  싶지 않다 — 내 파일은 애초에 내 것이어야 한다.

### 성공 기준 (검증 가능한 형태)

| # | 기준 | 검증 |
|---|------|------|
| S1 | `CLAUDE_CODE_SESSION_ID` 가 있는 세션의 `init` 은 `.claude/dashboards/<그 ID>.html` 을 만들고 **다른 파일을 지우지도 묻지도 않는다** | 수동(§13 M1) + T22-159~ |
| S2 | 그 변수가 없으면 오늘과 **바이트 단위로 같은** 절차(`.claude/dashboard.html` + 8자리 랜덤 토큰 + 0단계 확인)로 내려앉고, 보고에 사유 한 줄이 붙는다 | T22-160 + 수동 |
| S3 | 허브 `#dzh-data` 의 `projects[].sessions[]` 에 `tier1`(그 세션의 진행 스냅샷)·`dashboard_key` 가 실리고, 파일이 없는 세션은 둘 다 `null` 이다 | 유닛 P4·P7 |
| S4 | 프로젝트 카드의 진행률(티어 1 요약)은 레거시 파일·세션별 파일 전체 중 **mtime 최신**이다 — 워크트리 포함(WT6 확장) | 유닛 P5·P9 |
| S5 | 상세 패널의 `/project/<16hex>/dashboard.html` 라우트·정규식·핸들러는 **한 줄도 바뀌지 않고**, 세션 대시보드도 그 라우트로 서빙된다 | 유닛 P11 + T25-57 무변경 |
| S6 | 허브 헤더의 보기 토글로 트리 모드를 켜면 프로젝트마다 전폭 조직도 섹션이 그려지고, 새로고침·폴링 후에도 모드·선택 표시가 유지된다 | 수동(§13 M3) + T25-156~ |
| S7 | 트리의 세션 노드 클릭 → 패널 제목 `{프로젝트} · 세션 {short_id}` + 그 세션의 대시보드. 대시보드 없는 세션은 사유 문구 | 수동 |
| S8 | 카드 모드 화면·동작은 **회귀 0** — 카드 DOM 의 속성 집합·클릭·드래그·툴팁이 종전과 같다 | T25 기존 검사 전부 통과 |
| S9 | `tests/run.sh` 27/27, 유닛 514+신규 전부 통과, `py_compile`·`bash -n` OK | §13 검증 명령 |

---

## 2. 확정된 전제와 실측 (재론하지 않는다)

메인 세션이 검증한 사실(F1~F7)을 이 문서가 인용하는 파일을 **직접 열어** 재확인한 결과다.

| # | 전제 | 근거(실측) |
|---|------|-----------|
| F1 | 메인 세션은 자기 세션 ID 를 안다 — 이 세션의 Bash 환경에 `CLAUDE_CODE_SESSION_ID=f733cfcd-32eb-4339-9d99-e7375887e376` 가 있고, 허브 이벤트 `s` 필드(`~/.claude/hub/events/2026-09-02.jsonl` 의 `{"t":1788311173210,"e":"SessionStart","s":"f733cfcd-…","c":"/Users/dev/private/project/coding-harness","so":"startup"}`)·transcript 파일명·스크래치패드 경로와 일치한다. **공식 문서에는 등재되지 않았다** — 메인 세션이 2026-09-02 에 `code.claude.com/docs/en/env-vars`·`hooks`·`settings` 를 확인했고 어디에도 이 변수가 없다(`CLAUDECODE`·`CLAUDE_CODE_CHILD_SESSION` 만 있다). 그러므로 「관측된 사실, 비공식 계약」으로 취급하고, 없으면 명확히 폴백한다(ST2). 이 저장소 안에는 이 변수를 참조하는 곳이 아직 없다(`grep -rn CLAUDE_CODE_SESSION_ID docs commands hub tests` 0건) |
| F2 | `CLAUDE_ENV_FILE` 은 훅 시점 변수다 — 이 세션의 Bash 환경에서는 비어 있다(`echo $CLAUDE_ENV_FILE` → 빈 문자열). 훅 `hub/bin/hub_hook.py` 는 `SessionStart` 에서 `session_id` 를 받으므로(L129-136 `_project_fields`) 이론상 주입 폴백이 가능하지만 **채택하지 않는다**(§17-1) |
| F3 | R4 의 보류 근거 4개 중 3(영향 범위)·4(파일 수명)는 여전히 유효하다 — 이 문서 §8(영향 범위 전수)·ST5(수명)가 정면으로 답한다. R4 「연결점」(`dashboard-ownership-guard.md` L739-749)은 **토큰을 파일명으로** 쓰는 경로를 예고했는데, 전제 2 가 깨졌으므로 파일명은 토큰이 아니라 **세션 ID** 다(ST1·ST3 이 그 차이를 다룬다) |
| F4 | 동시 세션은 드물지 않다. 7일 훅 이벤트에서 **프롬프트를 실제로 입력한** 세션(= 대시보드를 만들 수 있는 세션) 수: daily-brief 10 · coding-harness 7 · atlas 4. 잡음 세션(`SessionStart(startup)` 직후 `SessionEnd`)은 `hub_template.html` L1224-1231 `shouldRenderSession` 이 이미 거른다 — 트리는 이 필터를 **재사용**한다(ST20) |
| F5 | 허브가 읽는 이벤트 창은 **오늘 + 어제**뿐이다(`hub_collect.py` L208-211 `_recent_event_file_paths`). 보존 7일(`hub_model.py` L33 `event_retention_days`)은 파일 삭제 기준이지 표시 창이 아니다 — 세션별 파일의 「무귀속(세션이 창 밖)」 상태가 정상적으로 존재한다(ST11 이 그 처리를 정한다) |
| F6 | 허브 `#dzh-data` 의 `Tier1Snapshot` JSON 은 실측 292B(steps 0개)~654B(steps 2개)이고 현재 `hub.html` 은 114,058B 다. 세션마다 스냅샷을 실어도 프로젝트당 +3~6KB 다(ST15) |
| F7 | 이 저장소의 워크트리 3개(`git worktree list`)는 `coding-harness-worktrees/` 형제 디렉토리라 `WORKTREE_PATH_MARKER`(`hub_project.py` L18 `/.claude/worktrees/`)에 걸리지 않는다 — 허브에서 별도 프로젝트로 보이며 이 설계와 무관하다. `hub-workflow-visibility/.claude/dashboard.html`(10:12) 이 그 예다 |

### 재방문 트리거 판정 (R4 (c), `dashboard-ownership-guard.md` L730-737)

| 트리거 | 발동 | 근거 |
|--------|------|------|
| T-1 동시 전체 경로가 일상 + 두 번째 세션의 진행률을 허브에서 봐야 한다 | **발동** | F4 + 사용자 요구 R2 |
| T-2 덮어쓰기 확인이 반복적으로 걸리적거린다 | 발동 | 이 세션이 그 사례다(§1) |
| T-3 `FOREIGN` 주 단위 반복 | 미관측 | — |
| T-4 허브가 세션 단위 표시로 확장된다 | **발동** | 요구 R1 이 곧 그 확장이다 |

---

## 3. 영향 범위

### 수정 파일

| 파일 | 마일스톤 | 변경 | 이유 |
|------|---------|------|------|
| `commands/dashboard.md`(1,344줄 · 89,893B) | M1 | 「대시보드 경로 규칙」 절 신설 + `init` 0·1·4단계 + `step`/`impl`/`log` 0단계 grep 경로 + 「자동 발행」 2·2-a·3 + 「포트 각인」 1 + `serve` 1·3·4 + 「보고 최소화」 1행 + 「데이터 모델」 토큰 문단 1문장 + 「소유권 검증」 1문단 | ST1~ST8. 리터럴 `.claude/dashboard.html` 28곳 중 **명령 안의 20곳**이 `"$dz_path"` 로 바뀐다(§11 표) |
| `docs/prps/dashboard-rationale.md` | M1 | 앵커 `#session-path` 절 신설(경로 규칙·리텐션·토큰 의미의 「왜」) | `dashboard.md` 는 호출마다 전량 로드되므로 근거 문단은 여기로 뺀다(기존 관례: L11-241 의 앵커 절들) |
| `.gitignore`(16줄) | M1 | L9 `.claude/dashboard.html` 아래에 `.claude/dashboards/` 1줄 | ST5 |
| `README.md` | M1 | L47·L161 의 산출물 경로 문구, L141 표의 `dashboard` 줄 수(현재 표기 1315 는 실측 1344 와 이미 어긋나 있다 — 이번에 새 값으로 맞춘다) | 사실 정합 |
| `hub/bin/hub_parse.py`(135줄) | M2 | `Tier1Snapshot.session_id: str \| None = None` 1필드 | ST10 |
| `hub/bin/hub_project.py`(313줄) | M2 | 상수 2·순수 함수 4·`compose_project_views` 인자 1 | ST9·ST11·ST13·ST14 |
| `hub/bin/hub_session.py`(410줄) | M2 | `SessionView.tier1`·`dashboard_key`(`model` **앞**에 삽입) + `compute_session_view` 인자 2 | ST12 (T25-150 이 마지막 필드 = `model` 을 고정한다) |
| `hub/bin/hub_collect.py`(748줄) | M2 | `read_session_dashboard_snapshots` 신설, `_read_tier1_for_root`·`_collect_tier1_snapshots` 반환 확장, `collect_snapshot` 배선 1줄 | ST9 — 파일을 만지는 곳은 여기뿐 |
| `hub/bin/hub_model.py`(100줄) | M2 | `build_dashboard_registry` 가 세션 항목도 담고, 값 조립을 `hub_project.tier1_file_path` 에 위임 | ST14 |
| `tests/hub/test_hub_parse.py`·`test_hub_project.py`·`test_hub_session.py`·`test_hub_model.py`·`test_hub_collect.py`·`test_hub_server.py` | M2 | §14 P1~P14 | — |
| `hub/bin/hub_template.html`(1,969줄) | M3 | 머리 주석(H1⁗ ③·OC1 개정) + CSS(토글·트리) + 헤더 마크업(토글 2버튼) + 렌더 IIFE(보기 모드·트리 렌더 5함수) + 패널 IIFE(`PanelTarget` 확장 4지점) | ST17~ST26 |
| `hub/README.md` | M2·M3 | L162·L167·L273-L277·L298·L318·L424 의 경로·문구, 「프로젝트 상세 패널」 절에 세션 노드·트리 모드 문단, 「알려진 한계」 2항목 | 사실 정합 |
| `commands/hub.md` | M2 | L283 티어 1 경로 문구 | 사실 정합 |
| `tests/run.sh`(5,914줄) | M1·M2·M3 | T22 헤더 범위 갱신 + T22-93 문자열 갱신 + T22-159~T22-163 신설, T25 헤더 범위 갱신 + T25-156~T25-163 신설 | §14 |
| 기존 PRP 5건 | M1~M3 | §18 의 개정 blockquote | 정본 정합 |

### 미영향 — 건드리지 않는 이유 (전수 확인)

| 파일 | 이유 |
|------|------|
| `commands/dashboard_template.html`(766줄) | **0 바이트.** 폴링은 `fetch(location.pathname)`(L410)라 파일명과 무관하고, `#dz-log data-owner-token=""`(L290)의 계약도 그대로다. `dashboard.md` L1342-1344 의 불변식(「이 문서를 고치는 작업은 템플릿을 한 바이트도 건드리지 않는다」)을 지킨다 |
| `hub/bin/hub_server.py` | **0 바이트.** 라우트 정규식(L36)·핸들러(L125-140)·레지스트리 교체(L200-209)는 키 개수와 무관하다(ST13). T25-57 무변경 |
| `hub/bin/hub_hook.py`·`hub_settings.py`·`hub_daemon.py`·`hub.py`·`hub_transcript.py`·`hub_usage*.py`·`hub_statusline.py`·`hub_server_state.py` | 세션 ID 는 이미 이벤트에 있고(F1), 훅은 주입하지 않는다(§17-1). 새 모듈이 없으므로 `hub/install.sh` L12 `HUB_FILE_COUNT=16`·`hub/README.md` L44 「16개 파일」·T25-1 도 무변경 |
| `CLAUDE.md`·`rules/` | 워크플로우 트리거 표(`dashboard.md` L49-64)는 그대로다 — `init`·`step`·`log` 호출 규약이 바뀌지 않는다. T26 예산(51,195B) 무관 |
| `hub_project.ProjectView` 필드 | 순서·이름 무변경(T25-87 이 `dashboard_key` → `tier1_is_previous_task` 순서를 고정한다) |

---

## 4. 파일 구조와 모듈 경계

레이어는 프로젝트 CLAUDE.md 의 원칙(I/O 와 순수 로직 분리 · 레이어 간 명시적 타입)을 그대로 따른다.
**새 모듈은 만들지 않는다**(결정 WT13 의 선례 — 세션별 파일 발견은 기존 티어 1 읽기의 확장이다).

```
쓰기 쪽 (LLM 절차)                      읽기 쪽 (허브)
commands/dashboard.md ──init──▶ <프로젝트>/.claude/dashboards/<sid>.html   ◀── hub_collect.py (I/O, 유일)
                       ──폴백──▶ <프로젝트>/.claude/dashboard.html          ◀──   │ 열거·stat·읽기·mtime
                                                                              ▼
                                            hub_parse.parse_dashboard_html → Tier1Snapshot(+session_id, source_path)
                                                                              ▼
                                            hub_project (★순수) ── 후보 합성·키·경로 조립·세션 색인
                                            hub_session (★순수) ── SessionView(+tier1, +dashboard_key)
                                                                              ▼
                                            hub_model (★순수) ── HubSnapshot → #dzh-data · build_dashboard_registry
                                                                              ▼
                                            hub_server (I/O, 무변경) ── /project/<16hex>/dashboard.html 조회 서빙
                                            hub_template.html ── 렌더 IIFE(카드|트리) ─dzh:rendered─▶ 패널 IIFE
```

경계 규칙(전부 기존 규칙의 재확인):

- **파일시스템에 닿는 코드는 `hub_collect.py` 만**이다. 파일명 → 세션 ID 추출, 상대경로·키 조립,
  후보 선택은 전부 `hub_project.py`(★순수)에 두어 `tests/hub/test_hub_project.py` 가 파일 없이 검증한다.
- `Tier1Snapshot.session_id` 는 `source_path`(결정 WT7, `hub_parse.py` L19-21·L50)와 **같은 계열**이다 —
  파서는 채우지 않고 I/O 가 `dataclasses.replace` 로 덮어쓴다.
- 렌더 IIFE 와 패널 IIFE 는 여전히 서로의 변수를 모른다(결정 SP1·OC8). 트리 노드 → 패널 인계는
  **카드와 같은 DOM 속성 경로**로만 한다(ST26). 패널 IIFE 범위(`var PANEL_OPEN_BODY_CLASS` 이후)에
  `snapshot` 문자열을 쓰지 않는다(T25-89 가 0건을 강제한다).

---

## 5. 데이터 모델

### 5.1 대시보드 파일 체계 (쓰기 쪽 · ST1~ST3)

| 항목 | SESSION 모드 | LEGACY 모드(폴백) |
|------|-------------|------------------|
| 조건 | `CLAUDE_CODE_SESSION_ID` 가 UUID 형식(`^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$`)이다 | 변수가 없거나 형식이 다르다 |
| 경로(`$dz_path`) | `.claude/dashboards/<CLAUDE_CODE_SESSION_ID>.html` | `.claude/dashboard.html`(오늘과 같다) |
| `init` 0단계 충돌 판정 | **없다** — 경로가 내 것이다 | 오늘의 `ABSENT`/`RECENT`/`STALE` + 확인 절차 그대로 |
| `data-owner-token` | 세션 ID 앞 8자리(= 허브 `short_id`, `hub_session.py` L19·L359) | `od /dev/urandom` 8자리(오늘과 같다) |
| 소유권 검증(`step`·`log`·`impl`) | 경로가 1차 소유권. 토큰 비교는 **그대로 수행**(경로 규칙 오적용 감지, ST4) | 오늘과 같다 |
| 수명 | `init` 1단계가 같은 디렉토리의 **7일 초과** 파일을 삭제(ST5) | 사용자가 `rm`(오늘과 같다) |
| 허브에서 | 세션 노드에 귀속 + 프로젝트 요약 후보 | 프로젝트 요약 후보만(귀속 불가) |

### 5.2 허브 순수 타입 (읽기 쪽 · ST10·ST12)

```python
# hub/bin/hub_parse.py — 기존 Tier1Snapshot(L36-50)에 1필드 추가
@dataclass(frozen=True)
class Tier1Snapshot:
    ...                                    # 기존 필드 무변경
    source_path: str = UNSET_SOURCE_PATH   # 이 스냅샷을 읽어 온 파일의 **소유 디렉토리**(WT7)
    # 세션별 파일(.claude/dashboards/<id>.html)이면 그 id, 레거시 단일 파일이면 None.
    # source_path 와 같은 계열 — 파서는 채우지 않고 hub_collect 가 dataclasses.replace 로 덮어쓴다(ST10).
    session_id: str | None = None

# hub/bin/hub_session.py — 기존 SessionView(L89-113). 두 필드를 **model 앞**에 넣는다(T25-150).
@dataclass(frozen=True)
class SessionView:
    ...                                    # session_id … agent_runs 무변경
    # 이 세션이 발행한 자기 대시보드의 진행 스냅샷과 서빙 키(ST12). ProjectView 의 tier1·dashboard_key
    # 쌍(hub_project.py L51·L53)과 같은 모양이라 템플릿이 같은 렌더 함수를 쓴다. 정체성 필드가 아니라
    # 정당하게 부재할 수 있는 부가 정보이므로 model 과 같은 계열(기본값 None)이다.
    tier1: Tier1Snapshot | None = None
    dashboard_key: str | None = None
    model: SessionModel | None = None      # 마지막 필드 유지(T25-150 GOTCHA 8)
```

`ProjectView`(L41-57)는 **무변경**이다. `tier1` 의 뜻만 「프로젝트의 대시보드」에서 「이 프로젝트에서
가장 최근에 갱신된 대시보드(레거시·세션별 불문)」로 넓어진다(ST11).

### 5.3 `#dzh-data` 계약 증분 (`hub_template.html` L13-15 「DZH:HUB 데이터 계약」)

```
projects[].tier1                 : Tier1Snapshot | null  — 뜻 확장(ST11). session_id 필드가 추가된다
projects[].sessions[].tier1      : Tier1Snapshot | null  — 신설(ST12). 그 세션 자신의 파일
projects[].sessions[].dashboard_key : string | null      — 신설(ST12). 서빙 키(16자리 hex)
```

`template_stamp` 가 바뀌므로 배포 후 열려 있던 탭은 1회 자가 리로드한다(결정 SH6~SH9).
`snapshot_content_key`(`hub_model.py` L80-84)는 안정적이다 — 새 값은 전부 파일에서 온 정적 값
(`file_mtime_ms`·`updated_text` 포함)이고 「지금」 파생값이 없다(`hub_session.py` L100-101 의 주의).

### 5.4 패널 타깃 (`hub_template.html` 패널 IIFE · ST23)

```ts
// readCardTarget(el) 이 만드는 레코드. 신원은 (projectPath, sessionId) 쌍이다(OC1 개정).
interface PanelTarget {
  projectPath: string;            // data-project-path — 항상 있다
  sessionId: string | null;       // data-session-id — 세션 노드만. 프로젝트(카드·트리 루트)는 null
  sessionShortId: string | null;  // data-session-short-id — 제목용
  dashboardKey: string | null;    // data-dashboard-key — 있으면 iframe, 없으면 빈 상태
  displayName: string;            // .project-name 텍스트, 없으면 data-project-name
  emptyReason: string;            // data-panel-empty-reason(OC4)
  isPreviousTask: boolean;        // data-tier1-previous — 프로젝트 타깃만 참일 수 있다
  openerElement: Element;
}
```

### 5.5 서빙 키와 레지스트리 (ST13·ST14)

| 대상 | 키 | 레지스트리 값(파일 절대경로) |
|------|-----|--------------------------|
| 프로젝트 요약 | `project_dashboard_key(project.path)` = sha256(프로젝트 경로)[:16] — **오늘과 같다**(N1) | `tier1_file_path(project.tier1)` — 승자가 세션별 파일이면 그 파일 |
| 세션 | `dashboard_file_key(tier1_file_path(session.tier1))` = sha256(파일 절대경로)[:16] | `tier1_file_path(session.tier1)` |

두 키는 같은 16자리 hex 공간에 살고 라우트는 하나다(`hub_server.py` L36). 프로젝트 승자가 세션별
파일이면 두 키가 같은 경로를 가리킨다 — 무해하다.

---

## 6. 인터페이스

### 6.1 셸 — 「대시보드 경로 규칙」 (dashboard.md 신설 절, ST2)

이 한 줄이 이 문서의 **모든 Bash 블록 첫 줄**이 되고, 명령 안의 `.claude/dashboard.html` 은
`"$dz_path"` 로 바뀐다. Bash 도구 호출 사이에 셸 상태가 남지 않으므로 블록마다 다시 계산한다.

```bash
dz_path=.claude/dashboard.html; echo "${CLAUDE_CODE_SESSION_ID:-}" | grep -qE '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' && dz_path=.claude/dashboards/$CLAUDE_CODE_SESSION_ID.html
```

- POSIX 유틸리티만 쓴다(`echo`·`grep -E`). 형식 검사는 **정규식 하나**뿐이며 이 값이 경로에 들어가므로
  생략하지 않는다(값의 출처는 하네스이지 사용자 입력이 아니지만, 미래 버전이 형식을 바꾸면 조용히
  LEGACY 로 내려앉는 것이 안전한 방향이다).
- 파이썬 블록(`init` 4단계·포트 스캔)에는 `DZ_PATH="$dz_path" python3 …` 로 **환경변수로 넘긴다** —
  인용 heredoc(`<<'PY'`)은 셸 확장을 하지 않으므로(L619-620 의 설계 근거) 파이썬에서 규칙을 다시
  쓰면 같은 규칙이 두 언어에 살게 된다.

### 6.2 Python (★순수 · `hub/bin/hub_project.py`)

```python
SESSION_DASHBOARDS_RELATIVE_DIRECTORY = ".claude/dashboards"
"""세션별 대시보드 디렉토리(프로젝트 루트 기준). PROJECT_DASHBOARD_RELATIVE_PATH(L29)와 같은 이유로
앞에 "/" 를 붙이지 않는다. commands/dashboard.md 「대시보드 경로 규칙」과 문자 단위로 같아야 한다(T25-158)."""

SESSION_DASHBOARD_FILE_NAME_PATTERN = re.compile(
    r"\A(?P<session_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.html\Z"
)
"""파일명 → 세션 ID. 이 정규식을 통과하지 않는 파일은 존재하지 않는 것으로 본다(ST9) — 레지스트리 값이
여기서 발견된 경로로만 만들어지므로(결정 N3) 발견 단계가 곧 서빙 표면의 경계다."""

def session_id_from_dashboard_file_name(file_name: str) -> str | None:
    """`<uuid>.html` 이면 uuid, 아니면 None."""

def session_dashboard_relative_path(session_id: str) -> str:
    """세션별 대시보드의 프로젝트 루트 기준 상대경로. 예: ".claude/dashboards/<id>.html"."""

def tier1_file_path(tier1: Tier1Snapshot) -> str:
    """스냅샷이 읽힌 파일의 절대경로 — 레지스트리 값의 **유일한 조립 지점**(결정 WT8 확장, ST14).
    session_id 가 있으면 source_path + "/" + session_dashboard_relative_path(session_id),
    없으면 source_path + "/" + PROJECT_DASHBOARD_RELATIVE_PATH."""

def dashboard_file_key(absolute_file_path: str) -> str:
    """파일 절대경로 → 서빙용 불투명 키(sha256 앞 16자리). project_dashboard_key(L207-214)와 같은
    해시 규칙을 쓴다 — 둘은 `_opaque_key(text)` 하나를 공유한다(ST13)."""

def index_session_dashboards(snapshots: Sequence[Tier1Snapshot]) -> dict[str, Tier1Snapshot]:
    """세션 ID 별 mtime 최신 스냅샷. session_id 가 None 인 것(레거시)은 넣지 않는다. 같은 세션의 파일이
    루트·워크트리 양쪽에 있으면 mtime 최신(WT6 과 같은 규칙, 동률은 입력 순서 앞)."""

def compose_project_views(
    tier1_by_path: dict[str, Tier1Snapshot],
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    tier3_last_activity_by_path: dict[str, int],
    now_ms: int,
    stale_after_ms: int,
    model_by_session_id: dict[str, SessionModel] | None = None,
    session_dashboards_by_path: dict[str, tuple[Tier1Snapshot, ...]] | None = None,   # 신설(ST12)
) -> tuple[ProjectView, ...]:
    """… 세션별 스냅샷을 index_session_dashboards 로 색인해 각 SessionView 에 tier1·dashboard_key 로 싣는다.
    tier1_by_path 는 이미 승자(레거시+세션별 전체의 mtime 최신)다 — 승자 선택은 I/O 쪽 _read_tier1_for_root
    가 select_tier1_source(★순수)로 끝낸다(ST11)."""
```

```python
# hub/bin/hub_session.py
def compute_session_view(
    facts: SessionFacts, now_ms: int, stale_after_ms: int,
    zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS,          # 선언 수 2 유지(T25-93)
    model: SessionModel | None = None,
    tier1: Tier1Snapshot | None = None,                        # 신설 — 실어 나르기만 한다
    dashboard_key: str | None = None,                          # 신설 — hub_project 가 계산해 넘긴다
) -> SessionView: ...
```

### 6.3 Python (I/O · `hub/bin/hub_collect.py`)

```python
def read_session_dashboard_snapshots(project_path: str) -> tuple[tuple[Tier1Snapshot, ...], tuple[str, ...]]:
    """<project_path>/.claude/dashboards/ 를 1회 열거해 파일명 정규식을 통과한 파일을 전부 파싱한다.
    (스냅샷들, 경고들). 디렉토리 부재는 정상(빈 튜플, 경고 없음). iterdir 실패·파일 읽기 실패·DOM 계약
    불일치는 그 항목만 건너뛰고 경고 1건(read_tier1_snapshot L337-350 과 같은 문구 형식)."""

def _read_tier1_for_root(
    member_paths: Sequence[str],
) -> tuple[Tier1Snapshot | None, tuple[Tier1Snapshot, ...], tuple[str, ...]]:
    """(프로젝트 요약 승자, 세션별 스냅샷 전부, 경고). 승자 = select_tier1_source(레거시 후보 + 세션별 후보)."""

def _collect_tier1_snapshots(
    tier1_candidates_by_root: dict[str, tuple[str, ...]],
) -> tuple[dict[str, Tier1Snapshot], dict[str, tuple[Tier1Snapshot, ...]], tuple[str, ...]]:
    """루트별 (승자, 세션별 스냅샷들) 을 모은다. collect_snapshot(L531-549)이 두 번째 값을
    compose_project_views 의 session_dashboards_by_path 로 넘긴다."""
```

`hub_model.build_dashboard_registry(snapshot) -> dict[str, str]` 는 시그니처 불변 — 프로젝트 항목의 값을
`tier1_file_path` 로 바꾸고, `session.tier1 is not None` 인 세션마다 `session.dashboard_key → tier1_file_path(session.tier1)`
를 더한다. `UNSET_SOURCE_PATH` 방어(L73-75)는 두 경로 모두에 적용한다.

### 6.4 JavaScript (`hub/bin/hub_template.html`)

렌더 IIFE(스냅샷을 아는 쪽):

```js
var VIEW_MODE_STORAGE_KEY = 'dzh-view-mode';          // 'cards' | 'tree'. 그 밖의 값·부재 → 'cards'
function readStoredViewMode(): 'cards'|'tree'          // readStoredUsageCollapsed(L1402) 관례 — try/catch, 실패 시 기본값
function persistViewMode(mode): void                   // persistUsageCollapsed 관례 — 실패 흡수
function applyViewModeButtons(mode): void              // 두 토글 <button> 의 aria-pressed 만 갱신(정적 노드, H1⁗)
function visibleSessionsOf(project): SessionView[]     // L1289-1292 의 slice().sort().filter(shouldRenderSession) 를 추출 — 카드·트리 공용(ST20)
function renderProjectTree(project): string            // 전폭 섹션 1개(.tree-section[data-project-path])
function renderTreeRoot(project, isClickable, emptyReason): string   // 루트 노드 = 카드의 .project-head 와 같은 정보 + renderTier1
function renderSessionNode(project, session): string   // <button class="tree-node"> — ST26 속성 집합
function renderAgentLeaf(run): string                  // renderAgentChip(L1120) 재사용을 <li> 로 감싼 잎
function sessionPanelEmptyReason(session, isClickable): string   // panelEmptyReason(L1271-1275) 의 세션판
```

패널 IIFE(스냅샷을 모르는 쪽):

```js
var SESSION_ID_ATTRIBUTE = 'data-session-id';
var SESSION_SHORT_ID_ATTRIBUTE = 'data-session-short-id';
var PROJECT_NAME_ATTRIBUTE = 'data-project-name';
var PANEL_SESSION_TITLE_SEPARATOR = ' · 세션 ';
function readCardTarget(el): PanelTarget               // L1785-1796 확장 — sessionId·sessionShortId 추가, displayName 폴백
function findOpenTargetElement(projectPath, sessionId): Element|null   // findCardByProjectPath(L1836-1843) 대체 — 두 속성 비교, 셀렉터 조립 금지
function panelTitleText(target): string                // displayName (+ ' · 세션 ' + sessionShortId)
```

`openDetailPanel`(L1866-1893)·`applyOpenCardMarking`(L1847-1860)·`refreshOpenPanelDocument`(L1944-1962)는
시그니처 불변이고 본문 3지점만 바뀐다(§12).

---

## 7. 설계 결정 — D1 `/dashboard` 쪽 (ST1~ST8)

### 결정 ST1 — 파일명은 **세션 ID**다. 토큰이 아니다

| 안 | 얻는 것 | 잃는 것 |
|----|---------|---------|
| **A. `.claude/dashboards/<CLAUDE_CODE_SESSION_ID>.html`(권고)** | 허브가 **추가 데이터 없이** 파일을 세션에 붙인다 — `SessionFacts.session_id`(`hub_session.py` L59)가 이미 키다. `read_session_model`(`hub_collect.py` L280-299)이 transcript 를 찾는 방식과 정확히 같다. `ls .claude/dashboards` 로 어느 세션의 것인지 즉시 안다 | 변수 부재 시 폴백이 필요하다(ST2) |
| B. `.claude/dashboards/<8자리 토큰>.html`(R4 연결점의 예고) | 폴백이 필요 없다 | 허브가 파일 → 세션을 **연결할 수 없다.** 토큰은 파일 안에만 있고 세션 어디에도 없다. R2 가 원리적으로 불가능하다 |
| C. 파일 안에 `data-session-id` 를 추가 각인 + 토큰 파일명 | R2 가능 | 허브가 세션을 알기 위해 **파일마다 열어야** 한다(A 는 stat 로 끝난다). 각인 하나가 더 늘고 얻는 것이 없다 |

> **결정 ST1 — 안 A.** R4 연결점(L739-749)이 예고한 「토큰이 곧 파일명」은 전제 2(세션 ID 를 알 수 없다)
> 위에 서 있었다. 전제가 깨졌으므로 파일명은 세션 ID 이고, 토큰은 파일명이 아니라 **파일 내용의
> 자기 검증 값**으로 남는다(ST3). 디렉토리 이름 `dashboards` 는 R4 (a) 의 스케치를 그대로 쓴다.

### 결정 ST2 — 폴백은 **오늘의 단일 파일 절차 그대로**다

변수가 없을 때 `.claude/dashboards/<랜덤 8자리>.html` 을 만드는 안(과제 제안 후보)을 기각한다.

- 그 파일은 허브가 어느 세션에도 붙일 수 없는 **「무귀속 세션 파일」** 이라는 새 개념을 만든다. 레거시
  단일 파일은 어차피 호환을 위해 읽어야 하므로(ST9), 무귀속 파일의 자리는 **그 하나**로 충분하다.
- 폴백 경로에서는 오늘의 0단계 충돌 판정·확인 절차·8자리 랜덤 토큰이 **바이트 단위로** 살아 있어야
  한다 — T22-106 이 `ABSENT`·`RECENT`·`STALE`·`/dev/urandom`·`data-owner-token` 을 `init` 절에서 계속
  요구한다(`tests/run.sh` L1928-1932).
- 폴백이 발동했음은 **보고에 한 줄**로 드러낸다(§11 (12)) — 조용히 내려앉으면 「세션별 대시보드가
  왜 허브 트리에 안 붙는가」를 사용자가 추적할 수 없다.

### 결정 ST3 — `data-owner-token` 은 SESSION 모드에서 **세션 ID 앞 8자리**다

| 안 | 평가 |
|----|------|
| 세션 ID 36자 전체 | `dashboard.md` L178-180 의 규격(`[0-9a-f]{8}`)이 깨진다. 「소유권 검증」 표의 비교 대상이 두 형식이 된다 |
| 랜덤 8자리 유지 | 파일명(세션 ID)과 내용(토큰)이 서로를 검증하지 못한다. 생성 명령이 하나 더 필요하다 |
| **앞 8자리(권고)** | 형식 불변. 값이 곧 허브의 `short_id`(`hub_session.py` L359 `facts.session_id[:SHORT_ID_LENGTH]`)라 카드·트리의 세션 칩과 **눈으로 대조**된다. 생성은 `${CLAUDE_CODE_SESSION_ID%%-*}` 한 조각 |

> **결정 ST3 — 앞 8자리.** 불변식 9(L308-311, `init` 만 쓴다·스크립트는 읽지 않는다)는 그대로다.
> 보고 형식 `대시보드: {URL} · 토큰 {소유 토큰}`(L93)도 그대로다 — SESSION 모드에서 토큰 망실은
> 치명적이지 않지만(경로 규칙이 환경에서 다시 계산한다) 형식을 두 개로 만들 이유가 없다.

### 결정 ST4 — 「소유권 검증」은 **경로 규칙이 1차, 토큰 비교는 유지**한다

R4 연결점은 검증이 「경로 결정 규칙으로 대체(승격)」된다고 예고했다. 승격은 맞지만 **대체는 아니다**:

- SESSION 모드에서 `step`·`log`·`impl` 이 여는 파일은 규칙상 항상 내 것이므로 판정은 `MINE` 이어야
  한다. 그런데 `FOREIGN` 이 나오면 그것은 **경로 규칙을 적용하지 않고 옛 리터럴 경로를 연 실행 오류**의
  신호다 — 바로 이 설계가 없애려는 「남의 파일 조용한 오염」의 마지막 방어선이다. 비용은 0 이다(같은
  grep 줄에 이미 있다).
- 새 어휘는 만들지 않는다. 파일 부재(`grep` 이 `No such file`)는 오늘의 「대상 줄이 안 나온다 → 보고 후
  중단」에 이미 포섭되며, 문구만 `serve` 1단계(L1227)와 같게 「`/dashboard init` 을 먼저 부르라」로 맞춘다.
- `MINE`·`FOREIGN`·`SKIP` 세 어휘와 `Bash 호출을 새로 만들지 않는다` 문구는 그대로다(T22-110).

### 결정 ST5 — 수명: **`init` 이 같은 디렉토리의 7일 초과 파일을 지운다**

| 안 | 평가 |
|----|------|
| 허브가 정리 | **기각.** 허브는 프로젝트 파일을 읽기 전용으로만 소비한다(`hub/README.md` 「알려진 한계」 첫 항목의 원칙). 허브는 옵트인 자산이라 없는 환경에서는 아무도 안 지운다 |
| `log commit` 이 자기 파일 삭제 | **기각.** 끝난 작업의 대시보드는 허브가 `done` 세션과 함께 보여주는 것이 가치다(발췌·칩과 같은 이유). 커밋 없이 끝나는 작업도 많다 |
| 수동만 | 상한이 없다. 실측 주당 프로젝트당 4~10파일 × ~60KB = 0.25~0.6MB/주 — 크지 않지만 무한이다 |
| **`init` 1단계의 `find … -mtime +7 -delete`(권고)** | 이미 있는 Bash 호출에 한 조각(Bash 호출 0 증가, 결정 O8 의 원칙). 활성 세션의 파일은 `step`·`log` 마다 mtime 이 갱신돼 걸리지 않는다. 7일은 `HubConfig.event_retention_days` 기본값(L33)과 같은 수 — 이벤트가 사라진 세션의 대시보드는 허브 어디에도 붙을 수 없다. **두 값은 서로 참조하지 않는다**(대시보드는 허브 없이도 동작해야 한다) |

> **결정 ST5.** `mkdir -p .claude/dashboards && find .claude/dashboards -maxdepth 1 -name '*.html' -mtime +7 -delete 2>/dev/null`
> 을 `init` 1단계 첫 명령으로 둔다.
>
> **→ 개정(2026-09-02, M1 구현 · 검수 3회차).** 실제 구현은 `mkdir -p .claude/dashboards || echo MKDIR-FAILED;`
> `find … -delete 2>/dev/null` 이다 — **`&&` 게이트를 버렸다.** 사유: 리텐션 실패를 `find` 의 종료 코드로
> 감지할 수 없다(실측 — BSD `/usr/bin/find` 는 `-delete` 가 권한으로 거부돼도 **0** 을 낸다. 이 하네스의
> `find` 는 셸 함수로 대체돼 1 을 내므로 한 환경에서만 동작하는 감지였다). 감지를 POSIX 가 종료 코드를
> 보장하는 `mkdir` 로 옮기고 새 폐쇄 어휘 `MKDIR-FAILED` 를 두었으며, 리텐션 자체는 **최선 노력**으로
> 격하해 실패를 보고하지 않는다(`commands/dashboard.md` 「출력 계약」과 그 뒤 문단이 정본).
> 위험 3(무한 성장) 완화는 유효하다 — 디렉터리가 쓰기 가능하면 unlink 가 되므로 **파일이 늘어나는
> 모든 `init` 은 리텐션이 동작한 `init` 이다**(검수 3회차 실증). 레거시 `.claude/dashboard.html` 은 **건드리지 않는다**(다른 세션의
> 것일 수 있다 — 오늘처럼 사용자가 지운다). `.gitignore` 에 `.claude/dashboards/` 1줄. 7일 넘게 대시보드를
> 갱신하지 않은 세션이 살아 있다면 다음 `step` 이 파일 부재로 중단되고 `init` 을 안내받는다 — 드물고
> 눈에 보이는 실패다.

### 결정 ST6 — 「자동 발행」·`serve` 는 **심볼릭 링크 원본만** 바뀐다 (1 세션 = 1 서버 유지)

| 안 | 평가 |
|----|------|
| **A. 세션마다 서버 1개, `$DZ_DIR/dashboard.html → $PWD/$dz_path`(권고)** | URL `http://localhost:{포트}/dashboard.html`·포트 스캔(L983-1028)·`REUSE` 바이트 비교(L991-1001)·`log commit` 종료(L917-956)·`data-server-port` 각인이 **전부 무변경**. 바뀌는 것은 `ln -s` 원본 경로 1토큰(L1021·L1236 — 두 줄은 T25-143 이 동일성을 강제하므로 함께 고친다) |
| B. 프로젝트당 서버 1개가 `.claude/dashboards/` 디렉토리를 서빙 | 세션 A 의 `log commit` 이 세션 B 가 쓰는 서버를 끈다 — 새 조정 문제. `REUSE` 판정을 「디렉토리 서빙 중」으로 다시 설계해야 한다 |

> **결정 ST6 — 안 A.** 같은 프로젝트의 세션 3개까지 8791~8793 을 하나씩 쓰고, 4개째는 오늘과 같은 `NONE` →
> 티어 2(`file://`) 폴백이다. 후보 포트를 늘리지 않는다(YAGNI — 허브 서버가 살아 있으면 3-a 가 허브를
> 열고, 허브 패널이 세션별 대시보드를 서빙하므로 로컬 서버의 역할은 플로팅 전용으로 좁아졌다).
> `REUSE` 는 여전히 옳다: 내 파일은 방금 만든 고유 토큰·제목을 담아 남의 서버 응답과 바이트가 다르다.

### 결정 ST7 — `commands/dashboard_template.html` 은 **0 바이트** 변경

폴링(`fetch(location.pathname)`, L410)·임베드 판정(L331)·갱신 훅(L429)·`#dz-log` 속성(L290) 모두 파일명과
무관하다. 머리 주석 L17-21 의 토큰 설명도 「발행한 세션의 소유 토큰」이라 그대로 참이다.

### 결정 ST8 — `dashboard.md` 증분 상한 **+6,000B(96,000B 이하)**, 근거는 `dashboard-rationale.md` 로

이 문서는 호출마다 전량 로드된다(L44-47 의 세션 1회 제한이 그 비용 때문이다). §11 의 편집을 조각별로
추산하면 약 +5.4KB 다(경로 규칙 한 줄 × 12블록 ≈ +2.1KB 가 가장 크다). 구현자는 `wc -c commands/dashboard.md`
를 **편집 전후로 실측해 보고**하고, T22-163 래칫(§14)에 실측치를 적는다. 상한을 넘기면 구현을 멈추고
이 문서를 먼저 고친다(에스컬레이션).

---

## 8. 설계 결정 — D2 허브 데이터 계약 (ST9~ST16)

### 결정 ST9 — 발견은 **디렉토리 열거**다. 세션 ID 로 조립하지 않는다

| 안 | 평가 |
|----|------|
| A. 알려진 세션 ID 로 경로 조립(`read_session_model` 방식, MD2) | 열거가 없고 작업량이 세션 수에 묶인다. 그러나 이벤트 창이 **오늘+어제**(F5)라 3일 전 세션의 파일은 존재해도 보이지 않는다 → 프로젝트 요약이 이틀 뒤 티어 2 로 떨어진다. 오늘의 레거시 파일은 7일이든 30일이든 티어 1 로 남는다(GN 「이전 작업」 라벨이 그 전제 위에 있다) — **제품 의미의 회귀**다 |
| **B. `.claude/dashboards/` 열거 + 파일명 정규식(권고)** | 프로젝트 요약 의미가 오늘과 같다(가장 최근 파일, 발행자 불문). 무귀속 파일은 요약 후보로만 쓰이고 세션 노드에는 붙지 않는다. 비용: 멤버 경로마다 `iterdir` 1회 + 파일 ≤ ~10개 파싱(리텐션 7일, F4) ≈ 0.6MB/사이클 — transcript 꼬리 읽기(~1.8MB/사이클, MD4)보다 작다 |

> **결정 ST9 — 안 B.** 정규식을 통과하지 않는 파일명은 **존재하지 않는 것**으로 본다 — 발견된 경로만
> 레지스트리 값이 되므로(N3) 이 필터가 서빙 표면의 경계다. 캐시는 두지 않는다(MD4 와 같은 판단).
> **에스컬레이션 조건**: `collect_snapshot` 이 50ms 를 넘기면 파일별 mtime 캐시를 재검토한다.

### 결정 ST10 — `Tier1Snapshot.session_id` 는 `source_path` 와 **같은 계열**이다

파서(`hub_parse.py` L112-135)는 텍스트만 받으므로 파일명을 모른다. I/O 가 `dataclasses.replace(snapshot,
file_mtime_ms=…, source_path=…, session_id=…)` 로 채운다(L350 의 현행과 같은 자리). 기본값 `None` = 레거시.
T25-10(순수 모듈에 파일 접근 흔적 없음)에 어긋나지 않는다.

### 결정 ST11 — 프로젝트 요약은 **후보 전체의 mtime 최신**이다 (WT6 확장). GN 은 손대지 않는다

`select_tier1_source`(L217-225)에 넘기는 후보를 「멤버별 레거시 파일」에서 「멤버별 레거시 파일 + 멤버별
세션 파일 전부」로 넓힌다. 규칙·동률 처리(목록 앞 = 레포 루트 = 레거시 먼저) 모두 그대로다.

「살아 있는 세션의 대시보드를 우선한다」는 안을 기각한다 — 새 상수·새 판정이 필요하고, 그 필요는
**트리가 이미 채운다**(세션별 진실은 노드에 있다). 카드 한 줄의 요약이 「이 프로젝트에서 가장 최근에
갱신된 대시보드」라는 한 문장으로 설명되는 것이 WT6 의 가치였고, 여기서도 같다.

GN(`is_tier1_from_previous_task`, L228-238)은 무변경이다. 승자가 세션별 파일이면 그 세션은 필연적으로
그 mtime 보다 먼저 시작했으므로 그 세션이 살아 있는 한 라벨은 꺼진다 — 「지금 세션의 대시보드」에
「이전 작업」이 붙는 오탐이 구조적으로 없다. 승자가 다른(idle·done) 세션의 파일이고 그 뒤에 시작한
세션만 살아 있으면 라벨이 켜진다 — 옳다. `_live_session_start_times_ms`(L241-260)의
`tier1_source_path in facts.observed_cwds` 비교도 그대로다(T25-117).

### 결정 ST12 — `SessionView.tier1`·`dashboard_key` — ProjectView 의 쌍과 같은 모양

`index_session_dashboards` 가 세션당 1개(mtime 최신)를 고르고, `compose_project_views` 가
`compute_session_view(..., tier1=…, dashboard_key=dashboard_file_key(tier1_file_path(tier1)))` 로 넘긴다.
`compute_session_view` 는 실어 나르기만 한다(`model` 과 같은 관례, L349-352 주석). 필드 위치는 **`model`
앞**이다 — T25-150(`tests/run.sh` L5324-5343)이 「마지막 필드 = `model`」을 고정한다. 기본값 `None` 이라
`test_hub_model.py` 등 기존 픽스처(예: L27-30)는 무수정이다.

### 결정 ST13 — 라우트는 **기존 것 하나**다. 세션 키 = sha256(파일 절대경로)[:16]

| 안 | 평가 |
|----|------|
| A. `/project/<key16>/session/<uuid36>/dashboard.html` | 사람이 읽는 URL. 그러나 정규식·핸들러·레지스트리 키 타입·`hub_server.py` 테스트(u14~u18)·`hub/README.md` L162·L277 이 전부 움직인다. 그 URL 을 사람이 볼 일이 없다(iframe src) |
| **B. `/project/<key16>/dashboard.html` 재사용, 키 = `dashboard_file_key(파일 절대경로)`(권고)** | `hub_server.py` **0 바이트.** N1 의 「sha256(경로) 앞 16자리」에서 「경로」가 프로젝트 경로에서 파일 경로로 일반화될 뿐이고, 결정 N3(요청 문자열로 경로를 조립하지 않는다)은 레지스트리 조회 그대로다. 충돌은 64비트 접두 — 실질 0 |

> **결정 ST13 — 안 B.** `PanelTarget.dashboardKey` 와 `projectDashboardUrl`(L1798-1800)도 무변경이다.

### 결정 ST14 — 레지스트리 값 조립은 `hub_project.tier1_file_path` **한 곳**이다 (WT8 확장)

오늘 `hub_model.py` L76 은 `source_path + "/" + PROJECT_DASHBOARD_RELATIVE_PATH` 를 직접 잇는다. 승자가
세션별 파일일 수 있으므로 상대경로가 둘이 됐고, 그 분기를 `hub_model` 에 두면 「카드에 보이는 진행률과
클릭해서 열리는 파일이 다른 파일」(T25-113 이 막는 결함)이 다른 자리에서 재발한다. `tier1_file_path` 가
`session_id` 유무로 상대경로를 고르고, `dashboard_file_key` 도 같은 문자열을 해시한다 — **키와 값이 한
함수의 출력**이라 어긋날 수 없다.

### 결정 ST15 — 새 모듈 0 · 의존성 0 · `snapshot_content_key` 안정

- 새 파일을 만들지 않는다(WT13). `HUB_FILE_COUNT=16`·T25-1·`hub/README.md` L44 무변경.
- `SessionView` 에 실리는 값은 파일에서 온 정적 값뿐이다 — `Tier1Snapshot.updated_text` 가 바뀌면 키가
  바뀌어 `hub.html` 이 다시 쓰이는데, 그것은 내용이 실제로 바뀐 경우다(옳다).
- `hub.html` 증분은 프로젝트당 +3~6KB(F6). 세션 스냅샷의 `steps` 는 카드가 `renderTier1ActiveStep`(L1233)으로
  활성 단계 1개만 쓰지만, 트리 노드도 같은 함수를 쓰므로 필드를 줄이지 않는다(새 축약 타입 = YAGNI).

### 결정 ST16 — WT·ZG·RV 와의 상호작용 (전수)

| 결정 | 상호작용 | 결론 |
|------|---------|------|
| WT6 승자 규칙 | 후보 집합만 커진다 | 유지(ST11) |
| WT7·WT8 source_path | 세션 파일도 소유 디렉토리를 싣는다. 워크트리에서 `init` 한 세션의 파일은 그 워크트리 멤버 열거에서 나온다 | 유지 |
| WT16~WT18 observed_cwds | 후보 멤버는 종전대로 `plan_tier1_candidates`(L121-161)가 정한다 — 세션 파일 열거는 그 멤버 안에서만 일어난다. GN 비교식 무변경 | 유지 |
| ZG1·ZG4 좀비 | 트리 3단 잎은 `agent_runs`(타입 병합, `is_running` 포함)라 배지와 같은 술어를 쓴다 | 어긋남 없음 |
| RV1~RV3 부활 | 부활한 세션은 자기 파일을 그대로 갖는다(`done` 이든 아니든 `tier1` 은 붙는다) | 무영향 |
| GN1~GN3 | ST11 참조 | 무변경 |
| N3 | 발견 경로만 레지스트리에 든다(ST9 정규식) | 유지 |

---

## 9. 설계 결정 — D3 트리 UI (ST17~ST22)

### 결정 ST17 — 배치는 **안 B: 헤더 보기 토글(카드 | 트리), 기본값 카드**

**안 A — 카드 본문의 세션 목록을 소형 조직도로 교체**

```
┌ coding-harness  [대시보드 추적] [● 작업중]                     3분 전 ┐
│ /Users/dev/private/project/coding-harness                           │
│ 릴리스 트랙 R1~R3 + CLAUDE.md 분리 — 1/9 · 11%                     │
│                    ┌──────┴──────┐                                │ ← 340px 카드 안(콘텍츠 폭 ≥278px)
│               ┌────┴───┐   ┌────┴───┐   …▸ (가로 스크롤)           │    노드 ≤ 130px → 발췌·메타·모델 탈락
│               │1fc9c845│   │4dba59f0│                             │    기존 세션 줄(배지·경과·칩·메타·발췌) 소멸
│               └──┬───┬─┘   └───┬────┘                             │
│                 ▪   ▪         ▪                                    │
└───────────────────────────────────────────────────────────────────┘
```

**안 B — 헤더 토글로 켜는 별도 모드. 프로젝트마다 전폭 조직도 섹션(`grid-column:1/-1`)**

```
Claude 세션 허브                                              [▦ 카드 | ⑂ 트리]  [⟳]  [☾]
┌─ coding-harness  [대시보드 추적] [● 작업중]   릴리스 트랙 R1~R3 + CLAUDE.md 분리 — 1/9 · 11%      3분 전 ─┐
│                                            │                                                       │
│                     ┌──────────────────────┴──────────────────────┐                                │
│           ┌─────────┴──────────┐                       ┌─────────┴──────────┐                      │
│           │ ● 작업중   3분 전   │                       │ ○ 대기     16분 전  │                      │
│           │ 시작 09:52 1fc9c845 │                       │ 시작 10:01 4dba59f0 │                      │
│           │ Opus 5 · high       │                       │ Opus 5              │                      │
│           │ 허브 세션 트리 — 2/4 · 50% │                 │ 릴리스 트랙 R1~R3 — 1/9 · 11% │             │
│           │ 「권고안대로 진행해. 그리고…」│              │ 「R1 F-3·F-4 로스터 표…」    │             │
│           └────┬──────────┬────┘                       └──────────┬──────────┘                     │
│          ┌─────┴────┐ ┌───┴──────┐                          ┌─────┴─────┐                          │
│          │ ● 검수    │ │ 구현      │                          │ ● 설계     │                          │
│          └──────────┘ └──────────┘                          └───────────┘                          │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌─ daily-brief  [세션 활동] [대기]                                                          1시간 전 ─┐
│   …                                                                                               │
```

**안 C — 상세 패널 상단의 세션 전환기**

```
┌ 상세 패널 (550px) ───────────────────────── ✕ ┐
│ coding-harness                                     │
│  [프로젝트] [1fc9c845 ●] [4dba59f0 ○] [de319e3b] │ ← 세션 띠. 패널을 열어야 보인다
│ ┌────────────────────────────────────────────┐ │
│ │ <iframe> 선택한 대시보드                    │ │
```

| 기준 | A 카드 내 트리 | **B 보기 토글** | C 패널 전환기 |
|------|--------------|----------------|-------------|
| R1 「허브 화면에서 조직도형 트리」 | 폭 278px 에서 노드 정보가 거의 다 탈락 — 조직도의 인상만 남는다 | **충족.** 전폭(최대 1,440px)이라 첨부 이미지와 같은 위→아래 3단 트리가 그려진다 | 미충족 — 패널을 열어야 보이고, 트리가 아니라 띠다 |
| R2 세션 노드 클릭 → 세션 패널 | 가능 | **가능** — 노드가 카드와 같은 속성 인계 경로를 탄다 | 가능 |
| 카드 모드 회귀 | **전 카드 변경.** 발췌·메타·칩 줄이 사라지거나 축소된다 — 가장 자주 쓰는 스캔 UX 를 바꾼다 | **0** — 기본값이 카드이고 카드 렌더 함수는 무수정 | 0 |
| 5세션 이상·서브에이전트 다수 | 카드 안에서 파열 | 섹션 내부 `overflow-x:auto` — 노드 200px × 5 = 1,000px 는 스크롤 없이 들어간다 | 띠가 550px 를 넘으면 접힌다 |
| 드래그 재정렬·툴팁·열린 카드 표시 | 카드 구조 변경으로 전부 재검토 | 카드 모드에 그대로. 트리 모드는 저장 순서만 따르고 드래그 핸들 없음 | 무영향 |
| `file://` 모드 | 노드 클릭 불가 안내 필요 | 노드가 `data-panel-empty-reason=FILE_MODE_DASHBOARD_HINT` 를 갖는다(OC6 확장) | 패널 자체가 빈 상태 |
| 구현 표면 | CSS·렌더·패널 전부 | CSS(트리) + 렌더 5함수 + 패널 4지점 | 패널 IIFE 가 세션 데이터를 알아야 한다 → **G8(패널은 스냅샷을 모른다) 위반** |

> **결정 ST17 — 안 B.** C 는 SP1·G8 을 깨고 R1 을 채우지 못한다. A 는 R1 의 인상만 주면서 카드 UX 를
> 무너뜨린다. B 는 「무회귀 + 요구 충족」의 유일한 교집합이다. 사용자가 트리를 기본으로 원하면 §20
> 승인 항목 5 의 대안(기본값 `tree`)으로 뒤집을 수 있다 — 상수 1개다.

### 결정 ST18 — 보기 모드는 **사용자 상태**다 (불변식 H1⁗ ③ 개정)

- 저장: `localStorage['dzh-view-mode']` ∈ {`cards`, `tree`}, 그 외·부재·저장소 차단 → `cards`. 읽기·쓰기는
  `readStoredUsageCollapsed`/`persistUsageCollapsed`(L1402-1416)와 같은 try/catch 관례. 오리진별로
  따로 저장되는 한계(`file://` ↔ `http://localhost:8794`)는 테마·순서와 같다(`hub/README.md` 「카드 순서」).
- 토글 2버튼은 `.top-actions`(L350·L551-575) 안 **정적 마크업**이다 — `#dzh-refresh` 앞에 둔다. 폴링이
  절대 교체하지 않는 노드 목록(L31)에 추가하고, 갱신은 `aria-pressed` 속성만이다.
- `render()`(L1525-1551)는 모드에 따라 `renderProject` 또는 `renderProjectTree` 를 고른다. 순서는 두 모드
  모두 `syncProjectOrder`(L1517)가 정한다 — 트리 모드에서도 카드 순서 기억이 그대로 쓰인다.
- 모드 전환은 즉시 `render()` 1회다(폴링을 기다리지 않는다). `isReordering` 중 전환은 불가능하다
  (드래그 핸들이 카드 모드에만 있다).

머리 주석 H1⁗ ③ 에 한 문장을 더한다: 「보기 모드(카드/트리)도 사용자 상태다 — `localStorage['dzh-view-mode']`
+ 토글 버튼의 `aria-pressed` 에 살고, `#dzh-app` 은 그 값을 읽어 그릴 뿐 저장하지 않는다.」

### 결정 ST19 — 3단 트리: 프로젝트 → 세션 → **서브에이전트 타입**(실행 단위 아님)

| 안 | 평가 |
|----|------|
| 2단(프로젝트 → 세션) | 첨부 이미지의 깊이감이 사라진다. 세션이 지금 무엇을 돌리는지(검수 중인가)가 노드 밖으로 나간다 |
| **3단, 잎 = `agent_runs`(타입 병합, 권고)** | 데이터 계약 **증분 0** — `SubagentRunView`(L77-86)가 이미 `#dzh-data` 에 있다. `is_running` 이 배지와 같은 술어(ZG4)라 어긋남이 없다. 실측상 타입은 ≤ 4종 |
| 3단, 잎 = 실행 단위(`agent_id`) | `SubagentFact`(L45-52)를 `#dzh-data` 에 새로 실어야 한다(계약 확장·`snapshot_content_key`·T25 검사). 한 세션이 검수 3회를 돌리면 잎 3개 — 타임라인의 초입이다. **보류**(§19) |

카드의 칩 상한 `MAX_VISIBLE_AGENT_CHIPS = 2`(L858)는 340px 카드의 제약이라 트리에 적용하지 않는다 —
잎은 `agent_runs` 전부다. 상수는 손대지 않는다.

### 결정 ST20 — 노드 정보와 **렌더 함수 재사용**. 잡음 필터는 카드와 공유

세션 노드에 싣는 것(위→아래): 상태 배지(`renderStateBadge`, L1103) + 경과(`elapsedLabel`) / 시작 시각·
short_id·모델 칩(`renderSessionMeta`, L1200) / **세션별 진행률**(`session.tier1` 이 있으면 `renderTier1(session.tier1, false)`,
없으면 `--muted` 한 줄 「대시보드 없음」) / 발췌(`renderSessionExcerpt`, L1158 — CSS 가 2줄로 클램프).
루트 노드 = 카드 `.project-head`(L1311-1316) 와 같은 구성 + `renderTier1(project.tier1, project.tier1_is_previous_task)`.

- **필터 공유(F4)**: L1289-1292 의 `slice().sort().filter(shouldRenderSession)` 를 `visibleSessionsOf(project)` 로
  추출해 `renderProject`·`renderProjectTree` 가 함께 부른다. `shouldRenderSession`(L1224-1231)의 시그니처·
  본문은 건드리지 않는다(T25-120 이 그 함수 범위를 앵커로 추출한다). 새 필터를 만들면 카드에서 안 보이는
  잡음 세션이 트리에만 나타나는 어긋남이 생긴다.
- `renderSession`(L1208-1215)은 **무수정**이다 — T25-127 이 그 본문의 첫 줄 구성을 검사한다. 노드는 같은
  부품을 다른 순서로 조립하는 별도 함수다.
- 새 문자열 상수는 2개다: `SESSION_NO_DASHBOARD_LABEL`(노드 안 한 줄)과 `SESSION_NO_DASHBOARD_REASON`
  (패널 빈 상태 사유, ST25). 새 색 토큰 0개.

### 결정 ST21 — 연결선은 **CSS 의사요소**, 폭은 **섹션 내부 가로 스크롤**

PV9(라이브러리·CDN 금지, `file://` 에서도 열려야 한다)를 그대로 지킨다. 널리 쓰이는 순수 CSS 조직도
기법이다 — 노드 위 16px 구간에 `::before/::after` 로 수평선 절반씩과 수직 짧은 선을 그린다.

```css
/* 트리 모드(ST21). 색은 --line·--surface·--accent·--accent-soft·--muted 만 쓴다 — 새 토큰 0개. */
#dzh-app>.tree-section{grid-column:1/-1;background:var(--surface);border:1px solid var(--line);
  border-radius:14px;padding:16px 20px;box-shadow:var(--shadow);overflow-x:auto}
.tree,.tree ul{list-style:none;margin:0;padding:16px 0 0;display:flex;justify-content:center;position:relative}
.tree>li{padding-top:0}
.tree li{position:relative;padding:16px 6px 0;display:flex;flex-direction:column;align-items:center}
.tree li::before,.tree li::after{content:"";position:absolute;top:0;right:50%;width:50%;height:16px;border-top:1px solid var(--line)}
.tree li::after{right:auto;left:50%;border-left:1px solid var(--line)}
.tree li:only-child::before,.tree li:only-child::after{display:none}
.tree li:first-child::before,.tree li:last-child::after{border:0 none}
.tree li:last-child::before{border-right:1px solid var(--line);border-radius:0 6px 0 0}
.tree li:first-child::after{border-radius:6px 0 0 0}
.tree ul::before{content:"";position:absolute;top:0;left:50%;width:0;height:16px;border-left:1px solid var(--line)}
.tree-node{width:200px;font:inherit;text-align:left;background:var(--surface);color:var(--ink);
  border:1px solid var(--line);border-radius:10px;padding:8px 10px;cursor:pointer}
.tree-node:hover{border-color:var(--accent)}
.tree-node:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.tree-node.card-open{background:var(--accent-soft);border-color:var(--accent)}   /* OC9 와 같은 채널 */
.tree-node .excerpt{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tree-leaf{padding:0}   /* 잎은 .agent-chip 그대로 — 클릭 대상이 아니다 */
```

- 노드 폭 200px 고정: 5세션 = 1,000px + 간격 → 1,440px 안에 들어간다. 그 이상은 섹션이 가로 스크롤된다.
  줄바꿈(wrap)은 기각 — 연결선이 끊어지고 조직도가 아니게 된다.
- `.tree-node .excerpt` 의 클램프는 TC1~TC5 의 함정(flex 축소)과 무관하다 — 노드는 고정 높이 컨테이너의
  flex 아이템이 아니다. 그래도 구현 시 헤드리스 Chrome 으로 1·2·3줄 발췌를 실측한다(§14 수동 M3-4).
- 아이콘: 토글 2버튼은 lucide `layout-grid`·`network` 의 path 를 정적 인라인 SVG 로 옮긴다(PV9, 새로고침
  버튼 L554-561 의 viewBox·stroke 관용구 그대로). 첨부 이미지의 「사람 아이콘」은 넣지 않는다 — 상태 배지의
  글리프(●/○ 등)가 이미 노드의 시각 앵커이고, 아이콘 하나가 더 늘면 200px 안에서 정보가 밀린다.

**구현 후 개정(M3 검수, 위 CSS 스니펫·§12 대비) — 원문은 지우지 않고 화살표만 덧붙인다:**

- `justify-content:center` → **개정** — `safe center`. 구현 중 헤드리스 Chrome(152) 실측: 상세
  패널이 열려 폭이 줄어든 5세션 트리에서 `center` 는 첫·끝 노드가 음수 스크롤 영역으로 밀려
  스크롤로도 닿지 않게 잘렸다. `safe` 는 그 경우에만 `flex-start` 로 낙착해 전 노드가 스크롤로
  닿는다(안 넘칠 때는 기존과 동일). 코드 주석에만 근거가 있었을 뿐 이 PRP 에는 등록되지 않은
  채로 반영돼 있었다 — 이번에 여기 등록한다.
- `.tree-node{...}` → **개정** — `min-height:160px` 추가(검수 1회차 B-8). 세션마다 노드 높이가
  달라(발췌 0~2줄 클램프 + tier1 유무·active 0~2줄 클램프로 실측 101~175px) 3단(잎)의 시작
  줄이 최대 72px 어긋났다. 커넥터(`.tree li::before/::after`)가 `top:0` 기준이라 노드를
  아래로 미는 방식은 못 쓴다 — 노드 높이를 맞추는 것이 유일한 손잡이였다. 160px 는 실측
  분포(대부분 101~157px)를 덮는 값이고, `height` 아닌 `min-height` 라 드문 극단은 내용을
  자르는 대신 살짝 더 크게 남긴다(전 케이스 `clipped:false`). → **정정(검수 2회차 B-3)** —
  바로 위 "드문 극단 175px·형제보다 15px" 추정치는 실측과 달랐다. 실측값은 콘텐츠 212px·
  노드 214px 로, 160px 바닥에 고정된 형제 노드보다 54px 더 크다.
- 위 스니펫에 없던 신설 규칙 3건(원판에도 없었고, ST21 채택 당시 등록되지 않은 채 구현에만
  반영돼 있었다 — 이번에 여기 등록한다):
  - `.tree-root{...}` — 트리 루트(프로젝트 자신) 박스. 최초 `width:300px` 뿐이었으나 실측에서
    잘림을 냈다(14자 프로젝트명이 52%만 보임) → **개정(검수 1회차 A-1)** — `width:460px`(실측
    420px 부터 해소, 여유를 둠) + `.tree-node` 와 같은 계열의 상자(배경·테두리·radius·padding).
    후자는 A-4 가 칠할 표면이기도 하다.
  - `.tree-section.card-open .tree-root{background:var(--accent-soft);border-color:var(--accent)}`
    — **신설(검수 1회차 A-4)**. 루트를 열어도 시각적 「열림」 표시가 전혀 없었다(`.tree-node.card-open`
    은 있는데 `.tree-section` 용 규칙이 없었다 — OC9 의 트리 회귀). `findOpenTargetElement` 가
    프로젝트 타깃에 `.tree-section` 을 고르므로 그 스코프에서 `.tree-root` 를 지정한다(섹션
    전체를 칠하면 과하다).
  - `.tree-node-no-dashboard{font-size:12px;color:var(--muted);margin-top:8px}` — 세션 자신의
    대시보드가 없을 때(ST20)의 무채색 한 줄. 스니펫에는 없었다.
  - `.tree-section[data-dashboard-key],.tree-section[data-panel-empty-reason]{cursor:pointer}` —
    카드와 같은 클릭 가능 판정(OC5)의 시각적 안내(ST26). 스니펫에는 없었다.
- `.tree-section[data-tier1-previous] .tier1-pct,.tier1-active{color:var(--muted)}` (GN5 톤 다운,
  ST21 채택 당시 별도 스니펫으로 등록되지 않았다) → **개정(검수 1회차 A-3)** — 셀렉터를
  `.tree-section[data-tier1-previous] .tree-root .tier1-pct` 로 좁힌다. 카드에서는 `.tier1-pct` 가
  카드 안에 하나뿐이라 후손 선택자가 안전했지만, `.tree-section` 안에는 루트 1 + 세션 N 이 있어
  세션 노드까지 물들었다(세션은 `renderTier1(session.tier1, false)` 로 항상 "이전 작업 아님"으로
  그려지는데도).
- 렌더 IIFE 에 `initializeTreeRootScrollPositions`/`centerTreeRootIfOverflowing` 함수와
  `treeRootScrollInitializedProjectPaths` 상태 **신설(검수 1회차 A-2)** — `safe center` 로도
  풀리지 않는 문제가 남아 있었다: 세션이 많아 콘텐츠가 뷰포트보다 넓어지면 기본 스크롤 위치
  (`scrollLeft:0`)에서 루트(콘텐츠 가운데 있다)가 보이지 않는다. `.tree-root{position:sticky;left:0}`
  로 먼저 풀려 했으나 실측으로 기각했다 — sticky 는 스크롤 "도중"의 이탈만 막을 뿐, 정지 상태
  (`scrollLeft:0`)에서 애초에 뷰포트 밖에 있던 요소를 끌어오지 못한다(실측: 12세션·패널 열림·
  뷰포트 858px 에서 sticky 를 줘도 루트가 여전히 보이지 않았다 — scrollLeft 가 이미 0 이라 sticky
  가 개입할 지점 자체가 없었다). 대신 `render()` 끝에서 JS 로 초기 `scrollLeft` 를 한 번 계산해
  넣되, `#dzh-app` 이 render() 마다 자식을 통째로 교체하므로(불변식 H1⁗) 프로젝트 경로마다
  "이미 한 번 맞췄다"를 모듈 스코프에 기억해 최초 1회만 맞춘다(순서·접힘과 같은 사용자 상태 취급).
  → **개정(검수 2회차 A-1)** — "최초 1회만 맞춘다"가 실패였다. `render()` 는 poll 의
  `html === lastHtml` 가드를 타는 경로 말고도 `setInterval(render, TICK_MS)`(`TICK_MS=30000`,
  L946 부근)로 데이터 변화와 무관하게 30초마다 무조건 다시 불린다 — "render() 자체는 데이터가
  실제로 바뀔 때만 불린다"는 위 전제는 거짓이었다. `render()` 가 매번 `#dzh-app.innerHTML` 을
  통째로 교체해 `.tree-section` 이 새 DOM 노드(`scrollLeft:0`)가 되는데, 프로젝트 경로별 메모는
  이미 `true` 라 재보정이 건너뛰어져 30초 뒤 이 A-2 수정 이전과 같은 상태(루트 부재)로 되돌아갔다
  (실측: 12세션·패널 열림 `t=31s` 가시율 0, 8세션·패널 열림 46, 12세션·패널 닫힘 74).
  `treeRootScrollInitializedProjectPaths` 메모를 없애고 매 렌더 무조건
  `centerTreeRootIfOverflowing` 을 다시 호출하도록 고쳤다 — 사용자가 스크롤을 옮겨도 다음
  `render()` 의 `innerHTML` 교체가 이미 그 값을 파괴하므로, 매 렌더 재보정으로 새로 잃는 사용자
  상태는 없다.

### 결정 ST22 — `file://` 모드·드래그·툴팁

- `file://`: 노드는 카드와 같은 규칙(OC6)으로 `data-panel-empty-reason="{FILE_MODE_DASHBOARD_HINT}"` 를
  갖고, 클릭하면 빈 상태 패널이 같은 문구를 보인다. 문구 상수는 L928 의 것을 **재사용**한다.
- 드래그 재정렬은 카드 모드 전용이다. 트리 섹션에는 `.card-drag-handle` 이 없어 `dragstart` 가 발화하지
  않는다(L1589 `handle.closest('[data-project-path]')` 경로 미진입). `currentCardOrder`(L1015-1019)는
  `.card[data-project-path]` 로 스코프돼 있어 트리 요소를 세지 않는다.
- 툴팁(`data-tooltip`)은 문서 위임 리스너라 트리 노드 안의 배지·칩·발췌에서 그대로 동작한다.

---

## 10. 설계 결정 — D4 세션별 상세 패널 (ST23~ST26)

### 결정 ST23 — 패널 신원은 **`(projectPath, sessionId)`** 다 (OC1 개정)

OC1 이 신원을 `data-project-path` 로 정한 이유는 「경로는 항상 유일하다」였다. 세션 노드는 같은 경로를
공유하므로 세션 ID 를 두 번째 성분으로 더한다. `openPanelTarget` 은 여전히 **변수 1개**(`PanelTarget | null`)이고
「닫힘 ⇔ null」(SP15·OC3)도 그대로다. `findCardByProjectPath`(L1836-1843)는 `findOpenTargetElement(projectPath, sessionId)`
로 바뀐다 — `[data-project-path]` 전체를 순회하며 두 속성을 `getAttribute` 로 비교한다. 속성 셀렉터를
조립하지 않는 이유(L1832-1834: 경로에 큰따옴표·역슬래시가 올 수 있다)는 세션 ID 에는 해당하지 않지만
같은 함수 안에서 규칙을 둘로 나누지 않는다.

`applyOpenCardMarking`(L1847-1860)은 찍는 대상만 일반화한다: 매치된 요소에 `card-open` 클래스(상수
`OPEN_CARD_CLASS` 재사용 — T25-108 이 그 이름을 검사한다), `aria-current="true"` 는 그 안의 `.project-name`
이 있으면 거기에, 없으면(세션 노드 = 그 자체가 `<button>`) 요소 자신에게. CSS 가 카드·노드의 겉모습을
각각 정한다.

### 결정 ST24 — 제목 형식 `{프로젝트} · 세션 {short_id}`, 전체 ID 는 툴팁

`panelTitleEl.textContent = target.displayName`(L1876) → `panelTitleText(target)`. 세션이면
`data-tooltip` 에 전체 세션 ID 를 싣고(카드 세션 칩 L1203 과 같은 관례 — 절단이라 정보 손실이 실재한다,
결정 R4), 프로젝트면 속성을 제거한다. 정적 노드의 속성·textContent 단위 갱신이라 H1⁗ 에 맞는다.

### 결정 ST25 — 빈 상태 사유·같은 문서 판정·즉시 갱신

- 대시보드 없는 세션의 사유 상수: `SESSION_NO_DASHBOARD_REASON = '이 세션은 세션별 대시보드를 기록하지 않았습니다 — /dashboard init 을 부른 세션만 자기 대시보드를 갖습니다(구세대 단일 파일은 프로젝트 요약으로만 보입니다)'`.
  카드처럼 `data-panel-empty-reason` 속성 1개로 인계한다(OC4). 문구의 단일 출처는 렌더 IIFE 의 이 상수다.
- `isSameDocument`(L1872-1875) = 세 성분(`projectPath`·`sessionId`·`dashboardKey`) 모두 같음. 프로젝트 요약과
  그 승자 세션의 노드가 같은 파일을 가리켜도(ST13) 신원이 다르므로 iframe 을 다시 싣는다 — 제목이
  바뀌어야 하고, 재로딩 비용은 1회다. 스크롤 유지 최적화(OC2)의 범위를 넓히지 않는다(YAGNI).
- IR1~IR8 **무변경**: `refreshOpenPanelDocument`(L1944-1962)는 `openPanelTarget.dashboardKey` 만 쓰고, 세션별
  파일도 같은 템플릿이라 `dzRequestRefresh` 를 노출한다(ST7).
- `data-tier1-previous` 는 세션 노드에 붙지 않는다 → 안내 줄(GN6)은 세션 타깃에서 항상 숨는다.

### 결정 ST26 — DOM 속성 인계(카드 → 노드로 확장)와 이스케이프

세션 노드 `<button class="tree-node" type="button">` 의 속성 집합:

| 속성 | 값 | 비고 |
|------|-----|------|
| `data-project-path` | `escapeHtml(project.path)` | 카드 L1298 과 같다 |
| `data-project-name` | `escapeHtml(project.display_name)` | 노드 안에 `.project-name` 이 없으므로 제목용 |
| `data-session-id` | `escapeHtml(session.session_id)` | 신원 성분. T25-11·T25-125 의 `escapeHtml(session.session_id)` 관례 |
| `data-session-short-id` | `escapeHtml(session.short_id)` | 제목용 |
| `data-dashboard-key` **또는** `data-panel-empty-reason` | 카드 L1299-1301 의 `if/else` 와 같은 강제 지점(불변식 OC-A) | `CLICKABLE_CARD_SELECTOR`(L1745)가 그대로 노드를 잡는다 |

트리 루트 요소(`.tree-section`)는 카드와 **같은 속성 집합**(`data-project-path`·`data-dashboard-key`|`data-panel-empty-reason`·
`data-tier1-previous`·`data-tooltip`)을 가지며 `.project-name` `<button>` 을 품는다. 클릭은
`event.target.closest(CLICKABLE_CARD_SELECTOR)`(L1933)가 **가장 안쪽** 요소를 고르므로 노드 클릭은 노드,
섹션 여백 클릭은 프로젝트 요약이다 — 카드 모드의 「카드 어디를 눌러도 열린다」와 같은 규칙이다.

> → **개정** — 카드 여백 = 카드 상세보기, 프로젝트 요약은 모달 루트(결정 SC4,
> hub-session-modal-and-partial-update.md)
>
> → **개정(2026-09-30)** — 프로젝트 요약을 여는 요소는 없어졌다: 모달 루트도 패널 속성을 달지 않는다(hub-session-modal-cleanup.md
> 결정 MX1). 카드 여백은 보일 세션이 있는 카드에서만 카드 상세보기를 연다(MX2).

---

## 11. `commands/dashboard.md` 절차 개정안 (M1)

행 번호는 현행(1,344줄) 기준. 각 항목의 편집이 T22 의 어느 앵커에 걸리는지 함께 적는다. **새 절은 반드시
`## \`init\`` 앞에 둔다** — T22-93·T22-106 이 `init` 절을 `/^## \`init\`/,/^## \`step\`/` 로 잘라낸다(`tests/run.sh` L1799).

| # | 위치 | 편집 | T22 영향 |
|---|------|------|---------|
| (1) | L10 도입 blockquote | 「`.claude/dashboard.html` 의 DOM 자체가 상태다」 → 「대시보드 파일(「대시보드 경로 규칙」)의 DOM 자체가 상태다」 | 없음 |
| (2) | L93 「보고 최소화」 표 | 행 추가: `init` LEGACY 폴백 → 위 한 줄 + 「세션 ID(`CLAUDE_CODE_SESSION_ID`)를 알 수 없어 단일 파일 `.claude/dashboard.html` 로 발행했습니다 — 허브 트리의 세션 노드에는 연결되지 않습니다」 | 없음 |
| (3) | L178-180 토큰 문단 | 1문장: 「SESSION 모드(경로 규칙 참조)에서는 세션 ID 앞 8자리다 — 허브의 `short_id` 와 같은 값」 | 없음 |
| (4) | L363 `## 진행 시각화 규격` 앞(또는 그 절 끝, L460 다음) | **신설 `## 대시보드 경로 규칙`**: §6.1 의 한 줄 + 모드 표(5.1 의 앞 3행) + 「이 문서의 모든 Bash 블록 첫 줄이며, 명령 안의 `.claude/dashboard.html` 은 `"$dz_path"` 다」 + 「파이썬 블록에는 `DZ_PATH="$dz_path"` 로 넘긴다」 + `> 근거: [근거](../docs/prps/dashboard-rationale.md#session-path)` | 신설 T22-159 |
| (5) | L470-505 `init` 0단계 | Bash 첫 줄에 경로 규칙. `if [ "$dz_path" != .claude/dashboard.html ]; then echo SESSION; elif [ ! -f "$dz_path" ]; then echo ABSENT; else …(현행 RECENT/STALE + grep, 경로만 `"$dz_path"`) fi`. 표에 행 추가 `SESSION \| — \| 1번으로. 묻지 않는다 — 경로가 이 세션의 것이다`. 확인 절차 문구의 파일명은 LEGACY 전용이므로 그대로 | T22-106 토큰 5개 유지 |
| (6) | L508-521 `init` 1단계 | 첫 줄 경로 규칙 → **(ST5 개정 참조 — 실제 구현은 `\|\| echo MKDIR-FAILED;`)** `mkdir -p .claude/dashboards && find .claude/dashboards -maxdepth 1 -name '*.html' -mtime +7 -delete 2>/dev/null; rm -f "$dz_path"` → 템플릿 탐색(현행) → `if [ "$dz_path" = .claude/dashboard.html ]; then dz_token=$(od -An -N4 -tx1 /dev/urandom \| tr -d ' \n'); else dz_token=${CLAUDE_CODE_SESSION_ID%%-*}; fi` → `cp "$dz_template" "$dz_path" && basename "$PWD" && echo "$dz_token"`. 출력 계약(2줄: 첫 줄 이름, 마지막 줄 8글자 토큰) 불변. 설명에 리텐션 1문장(ST5) | **T22-93 문자열 갱신**(`rm -f .claude/dashboard.html` → `rm -f "$dz_path"`, L1806-1807). T22-106 `/dev/urandom` 유지. T22-125 `basename "$PWD"` 유지 |
| (7) | L564-616 `init` 4단계 | `python3 - <<'PY'` → 경로 규칙 1줄 + `DZ_PATH="$dz_path" python3 - <<'PY'`; `import html, pathlib` → `import html, os, pathlib`; L606 `path = pathlib.Path(os.environ["DZ_PATH"])`. 앵커·치환 목록 무변경 | 없음 |
| (8) | L645-663 「소유권 검증」 | 표 아래 1문단(ST4): 「SESSION 모드에서는 경로가 곧 소유권이라 판정은 항상 `MINE` 이어야 한다. 그런데도 `FOREIGN` 이면 경로 규칙을 적용하지 않고 옛 경로를 연 것이다 — 같은 행동(중단)이고, 보고에 그 가능성을 한 줄 덧붙인다」 | T22-110 어휘 3개·문구 유지 |
| (9) | L672 `step` 0단계 | Bash 첫 줄 경로 규칙, 경로 `"$dz_path"`. 「대상 줄이 안 나온다」 항목에 「파일 자체가 없으면(`No such file`) 이 세션이 `init` 을 부르지 않은 것이다 — `/dashboard init` 을 안내하고 중단한다」 | T22-110 `FOREIGN` 참조 유지 |
| (10) | L722-723·L840 감사용 재계수 | 위에 경로 규칙 1줄, 경로 `"$dz_path"` | 없음 |
| (11) | L767·L811 `impl set`·`impl <k>` 0단계, L773·L777 문구 | 같은 처리 | T22-108·T22-110 유지 |
| (12) | L849 `log` 0-a | 같은 처리(`grep -n 'id="dz-log"' "$dz_path"`) | T22-110 유지 |
| (13) | L972 티어 표·L1033 티어 2 URL | `file://{절대경로}/.claude/dashboard.html` → `file://{절대경로}/{dz_path}` | 없음 |
| (14) | L983-1001 포트 스캔 | 첫 줄 경로 규칙 + `DZ_PATH="$dz_path" python3 -c "…"`; `import socket, urllib.request, pathlib` → `+ os`; L991 `mine = pathlib.Path(os.environ['DZ_PATH']).read_bytes()`. 출력 어휘 3개 불변 | 없음 |
| (15) | L1021 자동 발행 2-a · L1236 `serve` 3 | 기동 명령 **바로 앞 줄**에 경로 규칙; `ln -s "$PWD/.claude/dashboard.html"` → `ln -s "$PWD/$dz_path"` — **두 곳 글자 하나까지 같게** | T25-143(두 기동 명령 동일성 · `trap 'exit 0' TERM; DZ_DIR=$(mktemp -d)` 앵커 2건 · pkill 패턴)은 앵커 줄이 그대로라 통과한다 — 경로 규칙은 별도 앞 줄이다 |
| (16) | L1197 「포트 각인」 1 | 경로 규칙 + `"$dz_path"` | 없음 |
| (17) | L1227 `serve` 1 · L1251-1262 `serve` 4 | 존재 확인·stop 후 grep 의 경로 | 없음 |
| (18) | L1333 「템플릿 파일」 | 「`.claude/dashboard.html` 로」 → 「대시보드 경로(「대시보드 경로 규칙」)로」 | T22-136(템플릿 파일명 언급) 유지 |

바뀌지 않는 것: `log commit` 3단계(L917-956) 전부, `on`/`off`(L1270-1315), CLAUDE.md 트리거 표(L49-64),
데이터 모델 6 셀렉터 표(L132-143), 불변식 1~10, 그룹×단계 규격.

`docs/prps/dashboard-rationale.md` 신설 절 `#session-path`(기존 앵커 관례 L11-12 의 `<a id>` + `##`): 왜 세션
ID 인가(ST1), 왜 폴백이 단일 파일인가(ST2), 왜 앞 8자리인가(ST3), 왜 `init` 이 7일 초과를 지우는가(ST5),
왜 파이썬 블록에 환경변수로 넘기는가(§6.1). `dashboard.md` 본문에는 각 결론 1문장만 남긴다(ST8).

---

## 12. `hub/bin/hub_template.html` 변경 지도 (M3)

| 위치 | 변경 |
|------|------|
| L13-15 데이터 계약 | §5.3 의 3줄 |
| L36-46 H1⁗ ③ | ST18 의 한 문장 |
| L78-84 패널 신원 문단 | 「신원은 `data-project-path` 다」 → 「신원은 `data-project-path` + `data-session-id`(세션 노드만) 쌍이다(OC1 개정, 결정 ST23)」 |
| L31 정적 노드 목록 | `#dzh-view-cards`·`#dzh-view-tree` 추가 |
| `<style>` L299 뒤 | ST21 의 CSS 블록 + `.view-toggle`(`.icon-btn` 관용구 재사용) → **개정(M3 구현)** — 한 지점이 아니라 관심사별로 세 곳에 나눠 삽입됐다: 트리 전용 규칙은 `.tree-section` 근방, 토글 버튼 규칙(`.view-toggle-group` 등)은 기존 헤더 버튼 클러스터 CSS 근방, `data-tier1-previous` 톤 다운은 카드용 규칙 바로 옆. 근접 배치가 목적이라 타당한 이탈로 판단해 그대로 둔다(검수 1회차 B-4) |
| L551-575 `.head-row .top-actions` | `#dzh-refresh` 앞에 토글 2버튼(`role="group"`, `aria-pressed`, `data-tooltip`, lucide SVG) |
| 렌더 IIFE L928 부근 상수 | `VIEW_MODE_STORAGE_KEY`·`VIEW_MODE_CARDS`·`VIEW_MODE_TREE`·`SESSION_NO_DASHBOARD_LABEL`·`SESSION_NO_DASHBOARD_REASON`·토글 아이콘 SVG 2개 → **개정(M3 구현)** — 토글 아이콘 SVG 2개는 렌더 IIFE 상수가 아니라 헤더의 **정적 인라인 마크업**으로 구현됐다. 이 표의 지시(L803)와 바로 위 행(L802, "lucide SVG")·이 절 §9 ST21 의 아이콘 문단("정적 인라인 SVG 로 옮긴다")·이 파일 머리 주석("정적 인라인 SVG 다 — CDN·런타임 라이브러리를 쓰지 않는다")이 서로 모순이었다 — 다수(3곳)가 가리키는 정적 인라인 쪽이 맞다고 보고 그쪽을 유지했다(검수 1회차 B-4, PRP 내부 모순 해소) |
| L1285-1320 `renderProject` | `visibleSessions` 계산을 `visibleSessionsOf(project)` 호출로 치환(본문 그 외 무수정) |
| L1320 뒤 | `renderProjectTree`·`renderTreeRoot`·`renderSessionNode`·`renderAgentLeaf`·`sessionPanelEmptyReason` |
| L1540 `render()` | `renderProject` → `viewMode === VIEW_MODE_TREE ? renderProjectTree : renderProject` |
| L1558 `usageToggleButton` 리스너 옆 | 토글 클릭 리스너 2개(모드 저장 → `applyViewModeButtons` → `render()`). **`if(!isServed){ … return; }` 앞**에 등록한다(L1555-1556 의 GOTCHA 4 와 같은 함정) |
| 패널 IIFE L1742-1744 상수 | `SESSION_ID_ATTRIBUTE`·`SESSION_SHORT_ID_ATTRIBUTE`·`PROJECT_NAME_ATTRIBUTE`·`PANEL_SESSION_TITLE_SEPARATOR` |
| L1785-1796 `readCardTarget` | `sessionId`·`sessionShortId` 필드 + `displayName` 폴백 |
| L1836-1843 `findCardByProjectPath` | → `findOpenTargetElement(projectPath, sessionId)` |
| L1847-1860 `applyOpenCardMarking` | 매치 요소 일반화(ST23) |
| L1872-1876 `openDetailPanel` | `isSameDocument` 3성분 · `panelTitleEl` 제목/툴팁 |

문자열 리터럴 `dzh:rendered`·`dzh:refresh-requested` 를 **새 코드·주석 어디에도 쓰지 않는다**(T25-107·T25-131 이
정확히 2건을 센다). 패널 IIFE 범위에 `snapshot` 을 쓰지 않는다(T25-89).

---

## 13. 마일스톤 — 각각 독립 배포·검증. **배포 순서 M2 → M1 → M3**

과제의 번호(M1 `/dashboard`, M2 허브 Python, M3 템플릿)를 그대로 쓰되, **배포는 M2 를 먼저** 한다. M1 만
먼저 나가면 새 세션의 파일을 허브가 모르기 때문이다(아래 「부분 배포 상태」).

### M2 — 허브 Python (읽기 쪽 먼저)

| 항목 | 값 |
|------|-----|
| 산출 | `hub_parse.py`·`hub_project.py`·`hub_session.py`·`hub_collect.py`·`hub_model.py` + 유닛 P1~P14 + `hub/README.md`·`commands/hub.md` 문구 + T25 헤더 범위·T25-156~T25-158(T25-158 은 M2 단독 배포 시점엔 **휴면** — `dashboard.md` 에 `CLAUDE_CODE_SESSION_ID` 리터럴이 없어 스스로 건너뛰고, M1 착수 후 활성화된다. 상세는 §23-1) |
| 검증 | `python3 -m py_compile hub/bin/*.py` · `python3 -m unittest discover -s tests/hub -t .`(T24 가 쓰는 명령, `tests/run.sh` L2627) · `bash tests/run.sh`(27/27) |
| 수동 | (a) 임시 프로젝트에 `.claude/dashboard.html` + `.claude/dashboards/<uuid>.html` 2개를 손으로 두고 `python3 ~/.claude/hub/bin/hub.py collect` → `~/.claude/hub/hub.html` 의 `#dzh-data` 에서 `sessions[].tier1`·`dashboard_key` 와 프로젝트 `tier1.session_id` 확인 (b) `/hub server restart` 후 `curl -sI http://127.0.0.1:8794/project/<세션 키>/dashboard.html` → 200 + `X-Content-Type-Options: nosniff` (c) 존재하지 않는 키·`../` 포함 경로 → 404(기존 u16·u18 과 같다) |
| 사용자가 보는 것(M2 만) | **오늘과 같다.** 세션별 파일이 아직 없으므로 카드·패널 무변화. `template_stamp` 무변경(템플릿 안 건드림) |

### M1 — `/dashboard` (쓰기 쪽)

| 항목 | 값 |
|------|-----|
| 산출 | `commands/dashboard.md` §11 + `dashboard-rationale.md#session-path` + `.gitignore` + `README.md` + T22 헤더 범위·T22-93 갱신·T22-159~T22-163 |
| 검증 | `bash tests/run.sh`(T22 그룹 포함 27/27) · `bash -n tests/run.sh` · `wc -c commands/dashboard.md` ≤ 96,000(ST8, 전후 실측 보고) · `bash -n` 으로 §6.1 한 줄과 §11 (5)(6) Bash 블록을 각각 파싱 |
| 수동 | (a) 데스크톱 세션에서 `echo $CLAUDE_CODE_SESSION_ID` 가 UUID 임을 확인한 뒤 `/dashboard init "t" "구현\|검수"` → `.claude/dashboards/<그 ID>.html` 생성, `data-owner-token` = 앞 8자리, 기존 `.claude/dashboard.html` **무접촉**(mtime 불변), 질문 없음 (b) `step 1 done` → 같은 파일 갱신, `MINE` (c) `env -u CLAUDE_CODE_SESSION_ID` 를 흉내내기 어려우면 §6.1 한 줄을 변수 미설정 셸에서 실행해 `dz_path` 가 레거시로 떨어지는지 확인 (d) 자동 발행 URL `http://localhost:879x/dashboard.html` 이 새 파일을 서빙(바이트 동일) (e) 8일 전 mtime 의 더미 파일을 `.claude/dashboards/` 에 두고 `init` → 삭제됨, 레거시 파일은 남음 |
| 사용자가 보는 것(M2 + M1) | 카드는 종전 UI 그대로이되 진행률 요약이 **레거시·세션별 중 최신**을 보인다. 패널 클릭은 그 승자 파일을 띄운다. 세션별 노드·트리는 아직 없다 |
| **M1 만 배포된 상태(비권고)** | 새 세션의 대시보드가 `.claude/dashboards/` 에만 생겨 **옛 허브는 그것을 모른다** — 그 프로젝트 카드는 레거시 파일이 없으면 티어 2(「세션 활동」)로, 있으면 낡은 진행률 + 「이전 작업」 라벨로 보인다. 대시보드 자체(로컬 서버·`file://`)는 정상이다. 이 손실이 배포 순서를 M2 먼저로 정하는 이유다 |

### M3 — 허브 템플릿

| 항목 | 값 |
|------|-----|
| 산출 | `hub_template.html` §12 + `hub/README.md` 「프로젝트 상세 패널」·「알려진 한계」 + T25-159~T25-163 |
| 검증 | `bash tests/run.sh`(T25 그룹 27/27) · 헤드리스 Chrome 실측(§14 수동 M3) |
| 수동 | (a) 토글 → 트리 모드, 새로고침(F5) 후 유지, `file://` 로 열어도 토글·트리 동작 (b) 세션 5개 프로젝트에서 섹션 가로 스크롤, 연결선 끊김 없음 (c) 세션 노드 클릭 → 제목 `coding-harness · 세션 1fc9c845`, iframe 에 그 세션의 대시보드; 다른 노드 → 교체; 루트 → 프로젝트 요약; 대시보드 없는 세션 → 사유 문구 (d) 열린 노드에 `card-open` 틴트 + `aria-current`, 폴링(1분) 뒤에도 유지 (e) Tab 으로 노드 포커스 → Enter 로 열림 (f) 새로고침 버튼·포커스 복귀 시 열린 세션 패널의 `dzRequestRefresh` 호출(스크롤 유지) (g) 카드 모드로 돌아가면 카드 DOM·드래그·툴팁이 종전과 같다 (h) 1·2·3줄 발췌 노드 높이 실측 |
| 사용자가 보는 것(전부) | §9 안 B 의 그림 |

---

## 14. 테스트 계획

### 14.1 파이썬 유닛 (`tests/hub/`, `python3 -m unittest discover -s tests/hub -t .`)

| # | 파일 | 케이스 | 기대 |
|---|------|-------|------|
| P1 | `test_hub_project.py` | `session_id_from_dashboard_file_name`: 정상 uuid·대문자·길이 35·`.html` 아님·`../x.html`·빈 문자열 | 정상만 uuid, 나머지 None |
| P2 | 〃 | `session_dashboard_relative_path("<id>")` == `".claude/dashboards/<id>.html"`; 앞에 `/` 없음 | — |
| P3 | 〃 | `tier1_file_path`: `session_id=None` → `source_path/.claude/dashboard.html`, 있으면 세션 경로. `dashboard_file_key` 가 그 문자열의 sha256[:16] 이고 `project_dashboard_key(source_path)` 와 다르다 | 결정 ST13·ST14 |
| P4 | 〃 | `compose_project_views(..., session_dashboards_by_path=…)`: 세션 A 에 파일 있음·B 없음 → A.tier1·A.dashboard_key 채워짐, B 둘 다 None; 세션 뷰 순서·기존 필드 무변경 | S3 |
| P5 | 〃 | `index_session_dashboards`: 같은 세션의 루트·워크트리 파일 2개 → mtime 최신; 동률 → 앞; `session_id=None` 제외 | ST12 |
| P6 | 〃 | GN 무변경: 승자가 살아 있는 세션 자신의 파일(start < mtime) → `tier1_is_previous_task=False`; 승자가 done 세션 파일이고 그 뒤 시작한 working 세션만 있음 → True | ST11 |
| P7 | `test_hub_session.py` | `compute_session_view(..., tier1=…, dashboard_key=…)` 실어 나름; 기본값 None; 필드 순서 — `dataclasses.fields(SessionView)[-1].name == "model"` | T25-150 |
| P8 | `test_hub_parse.py` | `Tier1Snapshot.session_id` 기본값 None; `parse_dashboard_html` 은 채우지 않는다 | ST10 |
| P9 | `test_hub_collect.py` | `read_session_dashboard_snapshots`(임시 디렉토리): 디렉토리 없음 → `((), ())`; uuid 파일 2 + `README.md` + `garbage.html` → 2건만, `source_path`·`session_id`·`file_mtime_ms` 채워짐; 깨진 DOM 1건 → 경고 1 | ST9 |
| P10 | 〃 | `_read_tier1_for_root([root, worktree])`: 레거시(오래됨) + 세션 파일(최신) → 승자 = 세션 파일(`session_id` 있음), 세션 목록에 두 멤버의 파일 모두 | S4·WT6 확장 |
| P11 | `test_hub_model.py` | `build_dashboard_registry`: 프로젝트 키 → 승자 파일(세션 파일이면 그 경로), 세션 키 → 세션 파일, `UNSET_SOURCE_PATH` 세션 스냅샷 제외; 값에 `PROJECT_DASHBOARD_RELATIVE_PATH` 직접 조립 없음 | ST14·T25-113 |
| P12 | 〃 | `snapshot_content_key`: 세션 tier1 이 있는 스냅샷에서 `collected_at_ms` 만 다르면 같은 키; `updated_text` 다르면 다른 키 | ST15 |
| P13 | 〃 | `render_hub_html` → `#dzh-data` JSON 에 `sessions[0].tier1.session_id`·`dashboard_key` 가 실린다 | S3 |
| P14 | `test_hub_server.py` | `ProjectDashboardRoutingTest` 에 케이스 1개: 레지스트리에 세션 키 → 그 파일이 200 + nosniff. 정규식·핸들러 무수정임을 전제로 하는 회귀 테스트 | S5 |

### 14.2 `tests/run.sh` — 신규 검사

T22 헤더(L1099·L1103)를 `T22-1~T22-163`, T25 헤더(L2639·L2643)를 `T25-1~T25-163` 으로 갱신한다.

| # | 대상 | 검사 |
|---|------|------|
| T22-93(갱신) | `init` 절 | `rm -f "$dz_path"` 존재(옛 리터럴 검사 대체) |
| T22-159 | `dashboard.md` | `## 대시보드 경로 규칙` 절 존재 + 그 절에 `CLAUDE_CODE_SESSION_ID`·`.claude/dashboards/`·`grep -qE` 존재 + 절이 `## \`init\`` **앞**에 온다(줄 번호 비교) |
| T22-160 | `init` 절 | `SESSION` 어휘 + `-mtime +7` + `${CLAUDE_CODE_SESSION_ID%%-*}` + `DZ_PATH=` 존재. 역방향: `init` 절 fenced bash 블록 안에 `rm -f .claude/dashboard.html` 리터럴이 **없다** |
| T22-161 | 문서 전체 | fenced 코드 블록 안의 `.claude/dashboard.html` 리터럴 등장 줄 수 == 경로 규칙 한 줄이 나오는 블록 수(정확한 기대값은 구현 후 실측해 고정, 뮤테이션: 한 블록을 옛 리터럴로 되돌리면 실패해야 한다) |
| T22-162 | `.gitignore` | `.claude/dashboards/` 1줄 존재(T22 는 지금까지 `.gitignore` 를 보지 않았다 — 경계를 넓히는 유일한 검사) |
| T22-163 | `dashboard.md` | `wc -c` ≤ `DASHBOARD_MD_BUDGET_BYTES`(래칫, T26 L25 관례 — 구현 실측치로 고정, 상한 96,000) |
| T25-156 | `hub_project.py` | `SESSION_DASHBOARDS_RELATIVE_DIRECTORY = ".claude/dashboards"` + `def tier1_file_path(` + `def dashboard_file_key(` 존재 |
| T25-157 | `hub_model.py` | `tier1_file_path(` 호출 존재. 역방향: `"/" + PROJECT_DASHBOARD_RELATIVE_PATH` 조립이 `hub_model.py` 에 없다(T25-113 확장) |
| T25-158 | 정합 | `dashboard.md` 경로 규칙의 `.claude/dashboards/` 와 `hub_project.py` 상수 값이 같다(양쪽에서 값을 추출해 비교 — T25-136 의 `dzRequestRefresh` 비교 선례) |
| T25-159 | `hub_template.html` | `dzh-view-mode` 리터럴 정확히 1건(상수 선언), `id="dzh-view-cards"`·`id="dzh-view-tree"` 가 `id="dzh-app"` **앞**(정적 노드) |
| T25-160 | 〃 | `function renderProjectTree(`·`function visibleSessionsOf(` 존재; `renderProject(`·`renderProjectTree(` 본문 모두 `visibleSessionsOf(` 를 호출; `renderProject` 본문에 `.filter(shouldRenderSession)` 직접 호출이 **없다**(공유 강제) |
| T25-161 | 〃 | `data-session-id` 리터럴 정확히 2건(렌더 문자열 1 + 패널 상수 1 — T25-107 관용구); `escapeHtml(session.session_id)` ≥ 2건 |
| T25-162 | 〃 | `.tree li::before`·`.tree li::after` CSS 존재; 트리 관련 `<script src=`·`@import`·`https://` 0건(PV9) |
| T25-163 | 〃 | 패널 IIFE 에 `SESSION_ID_ATTRIBUTE`·`function findOpenTargetElement(` 존재, `function findCardByProjectPath(` **부재**; `isSameDocument` 판정식에 `sessionId` 포함 |

기존 검사 중 이 변경이 **의존하는** 것(회귀 확인): T25-89(패널 `snapshot` 0건) · T25-107·T25-131(이벤트 리터럴 2건) ·
T25-108(`card-open`·`aria-current`) · T25-120(`shouldRenderSession` 범위) · T25-127(`renderSession` 첫 줄) ·
T25-143(기동 명령 2곳 동일) · T25-150(`SessionView` 마지막 필드 `model`) · T25-57(라우트 정규식 무변경) ·
T22-105/106/109/110 · T22-125.

### 14.3 뮤테이션 검증 (구현 중 1회)

- `hub_model.build_dashboard_registry` 에서 세션 항목 추가 줄을 지우면 P11·P14 가 실패해야 한다.
- `compose_project_views` 에서 `tier1=` 전달을 빼면 P4 가 실패해야 한다.
- `renderProjectTree` 가 `project.sessions` 를 직접 순회하도록 바꾸면 T25-160 이 실패해야 한다.
- `init` 1단계의 `rm -f "$dz_path"` 를 옛 리터럴로 되돌리면 T22-160 역방향이 실패해야 한다.

### 14.4 수동 확인 — 자동화 불가

- **`CLAUDE_CODE_SESSION_ID` 의 존재 자체는 `tests/run.sh` 로 검증할 수 없다.** 테스트 프로세스의 환경은
  Claude Code 대화형 세션이 아니다. 확인은 대화형 세션의 Bash 도구에서 `echo $CLAUDE_CODE_SESSION_ID` 를
  실행해 이벤트 파일의 `s` 필드와 대조하는 것(F1 의 방법)뿐이다. 공식 문서 등재 여부(F1 미확인)는 이
  설계의 전제가 아니다 — 없으면 LEGACY 로 내려앉는 것이 설계다.
- §13 의 M1·M3 수동 항목.

---

## 15. GOTCHA (구현 중 반드시 확인)

1. **`SessionView` 새 필드는 `model` 앞에.** T25-150 이 「마지막 필드 = `model`」을 고정한다(`tests/run.sh` L5343).
2. **`compute_session_view` 에 `zombie_after_ms: int = SUBAGENT_ZOMBIE_AFTER_MS` 선언을 늘리지 않는다.** T25-93 이
   선언 수 2 를 센다. 새 인자는 `model` 뒤에 기본값 `None` 으로만 붙인다.
3. **`dzh:rendered`·`dzh:refresh-requested` 리터럴을 새 코드·주석에 쓰지 않는다**(T25-107·T25-131). 이벤트 발행은
   기존 `RENDERED_EVENT_NAME` 변수를 통해 이미 `render()` 끝(L1551)에서 일어난다 — 트리 렌더도 그 경로를 탄다.
4. **패널 IIFE(`var PANEL_OPEN_BODY_CLASS` 이후)에 `snapshot` 문자열 금지**(T25-89). 「세션 데이터」라고 쓴다.
5. **새 절 `## 대시보드 경로 규칙` 은 `## \`init\`` 앞**에. `init`·`step`·`impl`·`log` 절 추출 앵커(L1591·L1722·L1799·L1943·L1961)를
   깨지 않는다. 절 제목에 백틱 없는 `## ` 헤딩을 쓴다(기존 추출 sed 가 `^## \`init\`` 형태를 앵커로 쓴다).
6. **기동 명령 두 곳(L1021·L1236)은 글자 하나까지 같게, 경로 규칙은 그 앞 별도 줄로.** T25-143 이 `trap … DZ_DIR=$(mktemp -d)`
   줄 + 다음 줄을 두 곳에서 비교한다.
7. **`hub_model.py` 에서 `"/" + PROJECT_DASHBOARD_RELATIVE_PATH` 조립을 남기지 않는다**(T25-113·T25-157). `tier1_file_path` 만 쓴다.
8. **파일명 정규식을 통과하지 않는 파일은 읽지 않는다**(ST9). 레지스트리 값이 곧 서빙 표면이다.
9. **`renderSession`·`shouldRenderSession` 본문을 고치지 않는다**(T25-120·T25-127 앵커). 공유는 `visibleSessionsOf` 추출로만.
10. **토글 리스너는 `if(!isServed){ … return; }` 앞**에 등록(L1555-1556 GOTCHA 4 와 동일) — 뒤에 두면 `file://` 에서 토글이 죽는다.
11. **`find … -delete` 는 `.claude/dashboards/` 로 스코프**한다. `-maxdepth 1 -name '*.html'` 을 지우면 하위·다른 파일이 위험하다.
12. **`init` 4단계·포트 스캔의 파이썬은 `os.environ["DZ_PATH"]`** — 경로 규칙을 파이썬으로 다시 쓰지 않는다(§6.1).
13. **`dashboard.md` 바이트 실측**을 편집 전후로 보고한다(ST8). 근거 문단은 `dashboard-rationale.md` 로.
14. **T22-93 문자열 갱신을 잊지 않는다** — 잊으면 M1 이 T22 그룹을 통째로 실패시킨다(L1806-1807).

---

## 16. 리스크와 완화

| # | 리스크 | 가능성 | 영향 | 완화 |
|---|--------|-------|------|------|
| 1 | `CLAUDE_CODE_SESSION_ID` 가 공식 계약이 아니어서 이름·형식이 바뀐다 | 중 | 세션별 파일이 생기지 않는다 | 정규식 불일치 → LEGACY 로 **자동 폴백** + 보고 1줄(ST2). 허브·템플릿은 레거시를 계속 읽는다. 변수 이름은 `dashboard.md` 경로 규칙 한 줄에만 있다(수정 지점 1) |
| 2 | 프롬프트 없는 sdk-cli 2.1.108 세션에는 변수가 없다 | 확실 | 없음 | 그 세션은 `/dashboard` 를 부르지 않는다(F1) |
| 3 | `.claude/dashboards/` 가 무한히 자란다 | 저 | 디스크·열거 비용 | ST5 7일 리텐션. 상한 = 주당 ≤ ~10파일 × 60KB |
| 4 | 7일 넘게 갱신 없는 살아 있는 세션의 파일이 지워진다 | 저 | 다음 `step` 이 중단 | 파일 부재 → `init` 안내(ST4). 조용한 손실이 아니다 |
| 5 | `dashboard.md` 가 +6KB 넘게 자란다 | 중 | 호출당 컨텍스트 비용 | ST8 상한·T22-163 래칫·근거 외부화. 초과 시 에스컬레이션 |
| 6 | 같은 프로젝트에 4개 이상 세션이 서버를 띄운다 | 저 | 4번째부터 `file://` 폴백 | 오늘과 같은 강등 경로. 허브 패널이 세션 대시보드를 대신 보인다(ST6) |
| 7 | `hub.html` 이 커진다 | 확실 | 프로젝트당 +3~6KB | F6 실측. `snapshot_content_key` 억제는 그대로(ST15) |
| 8 | 트리 모드에서 프로젝트가 많아 페이지가 길어진다 | 중 | 스크롤 | 기본값이 카드다(ST17). 트리 모드는 「지금 여러 세션을 굴리는 프로젝트」를 볼 때 켠다 |
| 9 | 패널 신원 확장이 OC3(대기 타이머 불변식)·SP15 를 흔든다 | 저 | 닫는 중 클릭 시 오동작 | `openPanelTarget` 은 여전히 1변수·`null` 이 닫힘. `isSameDocument` 만 성분이 는다(ST25). T25-163 |
| 10 | 템플릿 세대 자가 리로드가 열린 패널·모드를 초기화한다 | 확실(1회) | 사용자 1회 불편 | 모드는 localStorage 에 있어 복원된다. 패널은 알려진 한계(`hub/README.md`) |
| 11 | 워크트리 fold 와 세션 파일 위치가 어긋난다 | 저 | 세션 노드에 파일이 안 붙는다 | 열거는 멤버 전체(WT16·WT17)에서 한다(ST16). P10 |
| 12 | `data-owner-token` 이 세션 ID 앞 8자리라 8자리 랜덤 토큰과 충돌한다 | 무시 | — | 2^-32. 충돌해도 결과는 「같은 세션으로 판정 → 묻지 않고 덮어쓰기」인데 SESSION 모드에서는 그 파일을 열 일이 없다 |

---

## 17. 검토했으나 채택하지 않은 대안

1. **`CLAUDE_ENV_FILE` 로 훅이 세션 ID 를 주입하는 폴백(F2).** 기각 — (a) 허브는 옵트인 자산이고 `/dashboard`
   는 허브 없이 동작해야 한다(설치 안 한 사용자에게 폴백이 없다). (b) `hub_hook.py` 의 절대 규칙(L2-4)은
   「세션을 막지 않는다」다 — 파일 쓰기 하나가 늘면 실패 표면이 하나 는다. (c) 실측상 대화형 클라이언트
   (desktop ≥2.1.234·vscode 2.1.251)는 전부 변수를 갖고, 없는 쪽(sdk-cli 2.1.108)은 `/dashboard` 를 부르지 않는다.
   (d) 이 세션의 Bash 환경에서 `CLAUDE_ENV_FILE` 이 비어 있다 — 훅 시점 변수라 Bash 도구가 아닌 곳에서
   써야 하고, 그러면 `dashboard.md` 가 두 출처를 알게 된다. **재방문 트리거**: `CLAUDE_CODE_SESSION_ID` 가
   대화형 클라이언트에서 사라지는 것이 관측될 때.
2. **파일명 = 8자리 토큰**(R4 연결점의 예고). 기각 — 허브가 세션에 붙일 수 없어 R2 불가(ST1).
3. **폴백 = `.claude/dashboards/<랜덤>.html`.** 기각 — 무귀속 세션 파일이라는 새 개념(ST2).
4. **세션 ID 로 경로를 조립해 발견**(열거 없음). 기각 — 이벤트 창(오늘+어제) 밖의 파일이 프로젝트 요약에서
   사라지는 제품 의미 회귀(ST9).
5. **명시적 세션 라우트 `/project/<key>/session/<uuid>/dashboard.html`.** 기각 — 서버·테스트·README 가 움직이고
   사람이 볼 URL 이 아니다(ST13).
6. **프로젝트 요약이 살아 있는 세션의 대시보드를 우선.** 기각 — 새 판정·상수, 트리가 그 필요를 채운다(ST11).
7. **잎 = 실행 단위(`agent_id`).** 보류 — 데이터 계약 확장, 타임라인의 초입(ST19·§19).
8. **안 A(카드 내 소형 트리)·안 C(패널 세션 전환기).** 기각 — §9 표. C 는 G8 위반.
9. **카드 모드에서 세션 줄 클릭 → 세션 패널.** 보류 — R2 는 트리 노드에 한정된 요구이고, 클릭 가능한 카드
   안에 클릭 가능한 줄을 겹치면 N6 계열의 충돌 정리가 다시 필요하다(§19).
10. **대시보드 로컬 서버가 `.claude/dashboards/` 디렉토리를 서빙.** 기각 — `log commit` 종료의 소유권 문제(ST6).
11. **허브가 오래된 세션 파일을 정리.** 기각 — 읽기 전용 원칙(ST5).
12. **첨부 이미지의 사람 아이콘을 노드에 추가.** 기각 — 200px 노드에서 정보를 밀어내고, 상태 글리프가
    이미 시각 앵커다(ST21).

---

## 18. 이 PRP 가 개정하는 기존 문서·불변식

| 문서 · 위치 | 개정 형식 | 내용 |
|------------|----------|------|
| `dashboard-ownership-guard.md` §R4(L685) | 절 머리에 blockquote(WT 부분 해소 L688-692 와 같은 형식) | 「**해소(이 PRP)** — 안 1 을 채택했다. 파일명은 토큰이 아니라 세션 ID 다(**보류 근거 2 무효**, ST1). 토큰은 SESSION 모드에서 세션 ID 앞 8자리로 남는다(ST3). 보류 근거 3·4 는 §8·ST5 가 답했다. 재방문 트리거는 **T-4** 가 발화했다」 |
| 같은 문서 결정 O1 표 L159(「PID·세션 ID 거부」) | 각주 1줄 | 「2026-09-02 실측으로 세션 ID 가 `CLAUDE_CODE_SESSION_ID` 로 관측됨 — hub-session-tree-and-per-session-dashboards.md ST1」 |
| `session-dashboard.md` 결정 3(L416-419) | blockquote | 산출물 경로가 SESSION 모드에서 `.claude/dashboards/<세션 ID>.html` 로 바뀜 |
| `hub-dashboard.md` 티어 표 L118-122 | 1행 수정 | 티어 1 출처 = `<프로젝트 또는 워크트리>/.claude/dashboard.html` **및** `.claude/dashboards/*.html`(여럿이면 mtime 최신) |
| `hub-worktree-fold.md` 결정 WT6(L289)·WT8(L339) | blockquote | 후보 집합 확장(ST11) · 값 조립 `tier1_file_path` 로 이동(ST14) |
| `hub-card-interactions-and-usage.md` 결정 N1(L541) | blockquote | 「경로」가 파일 절대경로로 일반화, 라우트 불변(ST13) |
| `hub-panel-empty-state-and-open-card.md` 결정 OC1(L197) | blockquote | 신원 = `(projectPath, sessionId)`(ST23) |
| `hub-detail-side-panel.md` 결정 SP6 H1⁗(L274) | blockquote | 조항 ③ 에 보기 모드 추가(ST18) |
| `hub_template.html` 머리 주석 | §12 | H1⁗ ③·OC1·데이터 계약 |
| `commands/dashboard.md` 불변식 | 무변경 | 불변식 9 는 그대로 참이다(ST3) |
| `hub/README.md` 「알려진 한계」 | 2항목 추가 | (a) 세션별 파일은 이벤트 창(오늘+어제) 밖 세션에는 붙지 않고 프로젝트 요약 후보로만 쓰인다 (b) 트리 모드는 `file://` 에서 그려지되 노드 클릭은 안내 문구다(카드와 같다) |

---

## 19. 보류 (이번에 만들지 않는다)

- **패널 개폐 시 트리 루트 재보정** — 트리 모드에서 세션 노드를 눌러 패널이 열리면 섹션 폭이 줄지만
  재렌더가 없어 루트 가시율이 100 → 66 으로 떨어지고 다음 틱(≤30초)에 복구된다(검수 3회차 실측 N-3).
  선재 결함이고 M3 의 매 렌더 재보정이 이미 완화했다(옛 메모 시절 같은 경로는 0% 로 갔다). 정본 해법은
  `pushModeQuery` 변화나 패널 개폐에 재보정을 거는 것인데 새 설계 결정이라 미룬다. 트리거: 그 30초가
  실사용에서 거슬린다는 관측.

- 서브에이전트 **실행 단위**(`agent_id`) 잎·타임라인 — 트리거: 한 세션이 같은 타입을 3회 이상 돌리는 것이
  일상이 되어 「몇 번째 검수인가」가 필요할 때.
- 카드 모드 세션 줄의 클릭(세션 패널) — 트리거: 트리 모드 사용률이 낮은데 세션 패널 요구가 계속될 때.
- 트리를 **프로젝트 간**으로 확장(허브 전체가 하나의 조직도) — 요구에 없다.
- 후보 포트 확장(8791~8793 → 5개) — 트리거: `NONE` 강등 보고가 반복 관측될 때.
- 세션 파일 발견의 mtime 캐시 — 트리거: `collect_snapshot` 50ms 초과(ST9).
- 레거시 `.claude/dashboard.html` 의 자동 정리 — 다른 세션의 것일 수 있어 사용자가 지운다.

---

## 20. 사용자 승인이 필요한 결정 (6개)

| # | 결정 | 권고 | 대안 1개 |
|---|------|------|---------|
| 1 | 파일 체계·폴백(ST1·ST2) | `.claude/dashboards/<CLAUDE_CODE_SESSION_ID>.html`; 변수 부재 시 오늘의 `.claude/dashboard.html` 절차 그대로 + 보고 1줄 | 폴백도 `.claude/dashboards/<랜덤 8자리>.html` — 허브에 「무귀속 세션 파일」 개념이 생긴다 |
| 2 | `data-owner-token` 값(ST3) | SESSION 모드 = 세션 ID 앞 8자리(허브 `short_id` 와 동일) | 세션 ID 36자 전체 — `[0-9a-f]{8}` 규격 파기, 검증 표가 두 형식 |
| 3 | 파일 수명(ST5) | `init` 1단계가 `.claude/dashboards/` 의 7일 초과 파일을 삭제. 레거시 파일 무접촉 | 자동 삭제 없음(수동 `rm`) — 무한 성장 |
| 4 | 서버 라우트·키(ST13) | 기존 `/project/<16hex>/dashboard.html` 재사용, 세션 키 = sha256(파일 절대경로)[:16], `hub_server.py` 0바이트 | `/project/<key>/session/<uuid>/dashboard.html` 신설 — 서버·테스트·README 변경, URL 가독성만 얻음 |
| 5 | 트리 배치·기본값(ST17·ST18) | 헤더 보기 토글(카드 \| 트리), **기본값 카드**, `localStorage` 유지 | 기본값 트리(상수 1개) — 카드 스캔 UX 를 쓰는 사용자에게 첫 화면이 바뀐다 |
| 6 | 배포 순서(§13) | **M2(허브 Python) → M1(`/dashboard`) → M3(템플릿)** | M1 먼저 — M2 까지 새 세션의 진행률이 허브에서 티어 2 로 보이는 구간을 감수 |

---

## 21. 필수 읽기와 미러할 패턴 (구현자용)

### 필수 읽기

| 우선 | 파일 | 행 | 왜 |
|------|------|-----|-----|
| P0 | `hub/bin/hub_project.py` | 23-29, 41-57, 121-161, 207-260, 263-313 | 상수·`ProjectView`·후보 계획·키·GN·합성 — 새 순수 함수가 들어갈 자리와 관례 |
| P0 | `hub/bin/hub_collect.py` | 280-318, 337-393, 519-560 | `read_session_model` 관례(절대 예외를 던지지 않는다·경고 문구 형식)·티어 1 읽기·배선 |
| P0 | `hub/bin/hub_session.py` | 89-113, 341-367 | `SessionView` 필드 규칙(정체성 vs 부가 정보)·`compute_session_view` 인자 관례 |
| P0 | `hub/bin/hub_model.py` | 59-84 | 레지스트리·`snapshot_content_key` |
| P0 | `hub/bin/hub_template.html` | 12-128, 928-935, 1224-1231, 1285-1319, 1525-1551, 1733-1800, 1836-1893 | 계약 주석·상수·필터·카드 렌더·render()·패널 IIFE 전반 |
| P0 | `commands/dashboard.md` | 83-115, 461-663, 958-1045, 1191-1268 | 보고 최소화·init·소유권 검증·자동 발행·포트 각인·serve |
| P1 | `tests/run.sh` | 1098-1104, 1799-1807, 1905-2036, 2622-2631, 2639-2670, 3954-3976, 4343-4363, 4992-5001, 5205-5240, 5324-5343 | T22·T25 헤더, 절 추출 앵커, 소유권 검사, T24 명령, T25-1, T25-89, T25-107, T25-131, T25-143, T25-150 |
| P1 | `hub/bin/hub_parse.py` | 15-50 | `UNSET_*` 계열과 `Tier1Snapshot` |
| P1 | `hub/bin/hub_server.py` | 30-36, 125-140, 156-209 | 무변경임을 확인할 대상 |
| P2 | `docs/prps/dashboard-ownership-guard.md` | 139-160, 645-663(원문 절차 대응), 685-749 | O1~O8·R4 |
| P2 | `docs/prps/hub-panel-empty-state-and-open-card.md` | 197-266, 433-470 | OC1·OC2·OC8·OC9 |
| P2 | `docs/prps/hub-worktree-fold.md` | 289-355 | WT6·WT7·WT8 |

### 미러할 패턴 (실제 코드, SOURCE 표기)

**I/O 함수 계약 — 절대 예외를 던지지 않고 (값, 경고) 를 돌려준다**
```python
# SOURCE: hub/bin/hub_collect.py:337-350
def read_tier1_snapshot(project_path: str) -> tuple[hub_parse.Tier1Snapshot | None, str | None]:
    """프로젝트의 .claude/dashboard.html 을 읽어 판다. (스냅샷, 경고 메시지) 튜플을 돌려준다."""
    dashboard_path = Path(project_path) / hub_project.PROJECT_DASHBOARD_RELATIVE_PATH
    if not dashboard_path.is_file():
        return None, None
    ...
    return dataclasses.replace(snapshot, file_mtime_ms=mtime_ms, source_path=project_path), None
```
→ `read_session_dashboard_snapshots` 는 같은 형태에 `session_id=` 를 더해 `replace` 한다.

**순수 함수가 I/O 결과를 받는 관례 — 딕셔너리 인자, 키 부재 = None**
```python
# SOURCE: hub/bin/hub_project.py:263-289
def compose_project_views(..., model_by_session_id: dict[str, SessionModel] | None = None):
    model_by_session_id = model_by_session_id or {}
    ...
            compute_session_view(facts, now_ms, stale_after_ms, model=model_by_session_id.get(facts.session_id))
```
→ `session_dashboards_by_path` 도 같은 관례(`or {}` · `.get(path, ())`).

**레지스트리 — 발견된 경로만 값이 된다(N3)**
```python
# SOURCE: hub/bin/hub_model.py:66-76
    for project in snapshot.projects:
        if project.tier != 1 or project.tier1 is None:
            continue
        source_path = project.tier1.source_path
        if source_path == UNSET_SOURCE_PATH:
            continue
        registry[project_dashboard_key(project.path)] = source_path + "/" + PROJECT_DASHBOARD_RELATIVE_PATH
```
→ 마지막 줄만 `hub_project.tier1_file_path(project.tier1)` 로, 세션 루프를 같은 방어와 함께 추가.

**카드 속성 인계 — `if/else` 가 불변식 OC-A 의 강제 지점**
```js
// SOURCE: hub/bin/hub_template.html:1298-1301
    var cardAttrs = ' data-project-path="' + escapeHtml(project.path || '') + '"';
    if(isClickable) cardAttrs += ' data-dashboard-key="' + escapeHtml(project.dashboard_key) + '"';
    // else 로 붙이는 것이 불변식 OC-A 의 강제 지점이다 — 키가 없으면 사유가 반드시 붙는다.
    else cardAttrs += ' data-panel-empty-reason="' + escapeHtml(emptyReason) + '"';
```
→ `renderSessionNode` 도 정확히 이 형태.

**저장소 읽기 — try/catch, 실패 시 기본값**
```js
// SOURCE: hub/bin/hub_template.html:1402-1408
  function readStoredUsageCollapsed(){
    try{
      return localStorage.getItem(USAGE_COLLAPSE_STORAGE_KEY) === USAGE_COLLAPSED_FLAG;
    }catch(e){
      return false;
    }
  }
```
→ `readStoredViewMode`.

**run.sh 「정확히 N건」 검사**
```bash
# SOURCE: tests/run.sh:4996-5001
  immediate_refresh_event_count=$(grep -c "dzh:refresh-requested" "$hub_template_file")
  if [[ "$immediate_refresh_event_count" -ne 2 ]]; then
    record_failure "$test_name" "T25-131: 'dzh:refresh-requested' 리터럴이 ${immediate_refresh_event_count}건(기대 2)"
    return 1
  fi
```
→ T25-159·T25-161.

---

## 22. 미결 질문 (메인 세션이 사용자에게 확인할 것)

> **해소(2026-09-02)** — 1~4 전부 권고안대로 확정됐다(사용자 회신 「권고안대로 진행해」). 5 는 아래 표기대로 문서 확인으로 해소.

1. **트리 기본값** — 카드(권고)로 두어도 되는가, 아니면 요구의 취지가 「허브를 열면 곧 트리」인가(승인 5).
2. **리텐션 7일** — 대시보드를 더 오래 보고 싶은 작업 방식인가(예: 주 단위 회고). 그렇다면 14일로 올리되
   허브 이벤트 보존(7일)과 어긋난다는 점을 감수하는가(승인 3).
3. **LEGACY 폴백 보고 문구** — 폴백이 발동했을 때 한 줄 알림을 원하는가, 아니면 침묵(보고 최소화의 기본값)이
   나은가. 권고는 알림 1줄이다(ST2 — 추적 가능성).
4. **첨부 이미지의 사람 아이콘** — 노드에 아이콘을 원하는가. 권고는 넣지 않는다(ST21).
5. ~~`CLAUDE_CODE_SESSION_ID` 문서화 확인~~ — **해소(2026-09-02)**: 공식 문서 미등재로 확인했다(§2 F1 갱신). 설계는 그대로 유효하다(폴백 내장, 리스크 1).

---

## 23. M2 인수 — M1·M3 구현자가 알아야 할 것

M2 검수 2회차(2026-09-02)에서 고치지 않고 넘기기로 한 항목들이다. 코드는 그대로이고, 다음
마일스톤 착수 전에 읽어야 할 사실만 남긴다 — 이 diff 가 남긴 비용은 코드보다 이쪽에 더 크다.

1. **해소(M1).** T25-158 은 M2 검수 시점에는 휴면이었다 — 활성 스위치는 `commands/dashboard.md`
   안의 `CLAUDE_CODE_SESSION_ID` 리터럴이었는데, 검수자가 그 파일에 마커를 손으로 넣어
   확인한 대로(실측 26/27, 상수 값 불일치를 주입하면 잡힘) 당시엔 그 리터럴이 `dashboard.md`
   에 아예 없어(§11 이 아직 M1 미착수였다) 검사 자체가 조건부로 건너뛰었다. 이 사실은 그때
   `tests/run.sh` 의 T25-158 주석에만 있었고 여기(§13 M2 「산출」행)에는 없었다 — 위 표에
   1행으로 옮겨 적었다. **M1 이 「대시보드 경로 규칙」 절을 신설하며 이 리터럴이 들어갔다 —
   T25-158 이 활성화되어 값 비교를 수행하고 통과한다(29/29).**
2. **해소(M1).** T25-158 은 `dashboard.md` 파일 전체를 grep 한다 — §14.2 는 원래 「경로 규칙
   **절**」을 지정했는데, T25-158 자체는 문서 전체에서 값 등장 여부만 본다. 산문 어딘가에 그
   문자열이 있고 정작 「대시보드 경로 규칙」 절의 한 줄이 표류해도(예: 다른 절로 잘못
   옮겨져도) 그 검사만으로는 통과해 버린다. 절 스코프로 좁히는 것은 M2 검수 시점에는 아직
   그 절 자체가 없어 M1 이 신설하는 T22-159 의 몫으로 남겨 뒀다. **M1 이 T22-159 를 신설해
   「대시보드 경로 규칙」 절 스코프로 세 토큰(`CLAUDE_CODE_SESSION_ID`·`.claude/dashboards/`·
   `grep -qE`)의 존재와 절 위치(`## \`init\`` 앞)를 검사한다 — T25-158(문서 전체 스코프)의
   빈틈을 T22-159(절 스코프)가 메운다.**
3. **해소(M3).** T25 헤더 범위(`tests/run.sh:2741`·`:2745`)를 158 → 163 으로 올렸다 — §14.2 가
   정한 최종 값이다. T25-159~T25-163(보기 토글·`visibleSessionsOf` 공유·`data-session-id`
   리터럴 계수·트리 CSS·패널 신원 확장)을 신설하며 함께 갱신했다 — 실측 `bash tests/run.sh`
   29/29.
4. **해소(M3).** `hub/README.md` 「프로젝트 상세 패널」 절에 세션 노드·트리 모드 문단을,
   「알려진 한계」에 신규 2항목(이벤트 창 밖 세션은 트리에 안 붙는다·`file://` 트리 노드는
   안내 문구만 낸다)을 추가했다.
5. **해소(M1).** M2 검수 시점에는 `.claude/dashboards/` 가 아직 `.gitignore` 에 없었다(M1 범위,
   §13 M1 「산출」 `.gitignore` 항목). M2 만 배포됐던 그 시점에 수동 확인 중 손으로 만든
   세션별 대시보드 파일은 그대로 두면 추적 대상이 될 수 있었다. **M1 이 `.gitignore` 에
   `.claude/dashboards/` 1줄을 추가했다 — T22-162 가 이를 검사한다.**
6. **`hub/bin/hub_collect.py` 가 799/800줄이다.** M2 검수 2회차 시점 기준 800줄 하드 게이트
   (`tests/run.sh` T25-100, 전역 CLAUDE.md 코드 품질 기준)에 1줄 여유뿐이다. 다음에 이 파일을
   건드리기 전에 티어 1 읽기 섹션(`read_tier1_snapshot`·`read_session_dashboard_snapshots`·
   `_read_tier1_for_root`·`_collect_tier1_snapshots`, 현재 대략 L336-442)을 별도 모듈로
   분리할 것을 검수자가 권고했다 — 선례는 `docs/prps/hub-model-module-split.md` MS1(분리 후
   ~692줄). **새 모듈을 만들면 `hub/install.sh` 의 `HUB_FILE_COUNT`(현재 16)·`hub/README.md`
   「파일 배치」·T25-1 이 함께 움직여야 하므로, 그 분리는 이 PRP 의 개정 없이 임의로 하지
   않는다.**
7. **세션 대시보드 읽기에 크기 상한·경고 개수 상한이 없다.** 레거시 경로(`.claude/dashboard.html`
   1파일)는 구조적으로 프로젝트당 경고 1건이 한도였지만, `.claude/dashboards/` 는 디렉토리
   열거라 그 한도가 사라졌다 — 지속되는 스킵 사유(권한·깨진 DOM 등)가 있으면 수집 사이클마다
   같은 경고가 재생성돼 hub 페이지에 영구 노출될 수 있다. 상한 도입은 새 정책 결정이라
   설계 범위이며, 이번 회차에서는 만들지 않았다.
8. **해소(M3, 재검토 없음).** `SessionView.tier1` 전체가 `hub.html` 의 `#dzh-data` JSON 에
   그대로 실린다 — 스냅샷 1개 ≈ 1KB, 세션이 많은 프로젝트(예: 25개)면 +26KB 안팎(당시 관측
   154KB 대비 +17% 수준). **M3 가 트리 UI 를 실제로 렌더했다** — 페이로드 조립 방식은 그대로
   두었고, 이번 회차에서 이 값의 실측 재검토는 하지 않았다(트리 렌더 자체의 결함 수정이
   우선이었다). 재검토가 필요해지는 트리거는 여전히 그대로다 — 체감 페이로드가 문제가 될
   만큼 커지면(예: 세션 수가 훨씬 많은 프로젝트가 실측되면) 그때 다룬다.
9. **미해소(R2 검수).** T22-159 는 `.claude/dashboards/` 를 `tests/run.sh` 안에 **세 번째로**
   하드코딩한다(다른 둘은 `hub_project.py:32` 의 `SESSION_DASHBOARDS_RELATIVE_DIRECTORY` 상수와
   `dashboard.md` 본문). T25-158 처럼 `hub_project.py` 에서 값을 추출해 비교하는 방식이
   **가능하나**(T22 함수 `test_dashboard_template_integrity` 에 `local
   hub_project_file="$REPO_ROOT/hub/bin/hub_project.py"` 를 다시 선언하면 된다 —
   `$REPO_ROOT` 는 전역이고 `tests/run.sh:2606` 이 이미 쓴다) 이번 회차(R2)의 수정
   범위에서 제외했다. M3 가 디렉토리명을 바꾸면 이 리터럴도 손으로 맞춰야 한다.
