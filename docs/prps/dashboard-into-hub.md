# 대시보드를 허브로 이관하고, 허브가 기록 파일(JSONL)을 직접 읽는다 (PRP)

> 결정 접두: **HD**(Hub Dashboard). `grep -rhoE "결정 HD[0-9]+" docs/prps/` 0건 확인(2026-09-23).
> 상태: **승인됨(2026-09-23) — §17 승인 항목 1~8 전부 권고안대로 확정**(항목 2 는 포인터 1줄 없는 안 A). 구현은
> **M1 부터**, M1 검수 통과 뒤 커밋 여부를 사용자에게 묻고 M2 로 간다. 기준 커밋 `9f23534`(`main`). 구현 코드는 이 문서에 없다.
> **M1 착지: `33e1ce9`.** **M2 계획 재확인(2026-09-24, 기준 `3d76b81`)** — M1 뒤 `main` 에 들어온 `be20be4`(한도 초과 표시)·`8f520de`·
> `ff02bc8`·`3d76b81`(허브 부분 갱신)에 맞춰 §0·§5.1·§5.2·§5.4·HD6·HD7·HD12·§7.2(+§7.2.1)·§8.1·§10.2·§10.3·§10.5·§13(13.1 표기·13.2·13.3)·
> §14.2·§15·§16·§17 을 고쳤다. 고친 곳마다 `(2026-09-24 재확인, 기준 3d76b81)` 를 달았다. **설계 결정 HD1~HD15 와 §17 승인 항목 1~8 은
> 바뀌지 않았다 — 재승인 필요 없음(§17 끝).** 재확인 모델: opus(기본값 — 기존 PRP 의 사실 재확인, 승격 기준 해당 없음).
> **설계 모델: fable(기준 2 — install.sh 배포 채널 · commands 헬퍼 · hub 런타임 · rules 상시 컨텍스트, 4개 서브시스템을 가로지르는 구조 변경).**
> 수치: 「메인 세션 실측」으로 표시한 값은 디스패치 프롬프트가 넘긴 측정을 그대로 인용했고(다시 재지 않았다),
> 「이 세션 실측」은 이 회차에서 직접 잰 값, 「추정」은 실측이 아닌 값이다.
> **프리뷰 목업 없음** — 이 설계는 사람이 보는 화면을 바꾸지 않는다(§5.4 에 근거를 적었다). 화면을 바꾸는
> 후속(카드 판정 배지)은 범위 밖으로 명시하고 그 회차에 목업을 붙인다(HD13).

---

## 0. 한눈에

| 항목 | 값 |
|------|-----|
| 사용자 요청 | ① 허브가 대시보드 기록 파일을 **직접 읽는다**(DN14-(b)). ② 대시보드 관련 내용을 **전부 허브 프로젝트로 이동**하고, 허브 없이 coding-harness 만 설치한 경우 대시보드 HTML 을 **발행하지 않는다**. ③ "비용 감소 효과도 있는가" |
| 비용 답(§2) | **직접 읽기(DN14)만으로는 모델 토큰 절감 0** — 허브는 모델 토큰을 쓰지 않는다(메인 세션 주장 3건 전부 확인, §2.4). 절감은 **이전·게이팅**에서만 나오고 **허브 없는 머신에 한정**된다: 상시 규칙 문단 1,439B(≈400 토큰, 추정) + 기록 호출 4.3회/작업 + 스킬 목록 1줄 → 이 세션 창(7세션·448호출·cache_read 1.16억)의 **≈0.3%(추정 상한)**. 허브 있는 머신은 **≈0**. 1단계(`fd79fa7`)가 큰 절감(스킬 재주입 0·문서 −94%)을 이미 가져갔다 — **효과는 작다.** 이 설계의 값은 토큰이 아니라 구조다(허브 없는 사용자의 대시보드 발자국 0, 허브의 HTML 왕복 소멸) |
| 핵심 결정 | HD1 허브 없음 = 기록 자체 없음(지침·기록기·명령 전부 부재) · HD2 기록 지침은 **허브 설치기가 `~/.claude/rules/hub/dashboard-recording.md` 로 배포**(안 A) · HD3 기록기 = `hub/bin/hub_dashboard_log.py`(얇은 진입점) · HD5 허브 서버가 **요청 시 JSONL → 같은 템플릿으로 렌더**(화면 변화 0) · HD6 `Tier1Snapshot` 계약 유지, 생산자만 교체 · HD7 레거시 단일 파일 읽기 폐기 · HD8 사이드카 폐기(작업 시작 = init 줄 시각) · HD9 `/dashboard on\|off` → `/hub dashboard on\|off` · HD12 신규 가드 ID 는 T25-2xx 를 쓰지 않는다(신설 그룹 T40) |
| 마일스톤 | **M1 이전·게이팅**(HTML 은 그대로 발행 — 허브 파이썬 0변경, 단독 배포 가능) → **M2 직접 읽기**(HTML·사이드카 발행 중단, 서버 렌더, 레거시 폐기 — 단독 배포 가능). M1 은 `33e1ce9` 로 착지했다. M2 는 동시 작업 3건과의 병합 순서 권고를 따른다(§13.2 끝 — 2026-09-24 재확인, 기준 3d76b81). M3(카드 배지)은 범위 밖·병합 후·별도 목업 |
| 폭발 반경 | M1: 파일 삭제 4·신설 5·수정 ≈14, `tests/run.sh` T22(99 ID 경로 재조준, 본문 수정 ≈9)·T23 11·T25 8·T33 3·T34 3·T35 1·T26·T27 주석 + 신설 T40 8, 유닛 125건 이동 · **M2 (2026-09-24 재확인, 기준 3d76b81)**: 허브 파이썬 6모듈 + 주석만 3곳(`hub_model`·`hub_usage` docstring, 대시보드 템플릿 8행) · 테스트 픽스처 5 삭제 · 유닛 기존 ≈138건 손댐(삭제 ≈46·이동 19·재작성/수정 ≈62·참조 재조준 11) + 신규 ≈27 · `tests/run.sh` T25-222·T34 개정 + T22-137·T25-146 개정(면제→변조 승급) + 주석 5곳 + 신설 T40-13~15 |
| 승인 필요 | **8개**(§17). M2 계획 재확인 뒤 **재승인 필요 0**(§17 끝 — 2026-09-24 재확인, 기준 3d76b81) |

---

## 1. 요구사항 요약

1단계(`0576c87`·`fd79fa7`·`33d5cea`·`42f0dc1`)에서 메인 세션은 `dashboard_helper.py` 를 Bash 로 불러
`.claude/dashboards/<세션ID>.jsonl` 에 한 줄씩 기록하고, 헬퍼가 그 기록으로 `.html` 을 그리고, 허브는
`hub_parse.parse_dashboard_html` 로 그 HTML 을 다시 읽는다. 사용자는 (a) 허브가 그 JSONL 을 직접 읽는
2단계(DN14)를 진행하고, (b) 대시보드 자산을 전부 허브로 옮겨 **허브 없이 coding-harness 만 설치한 머신에서는
대시보드 HTML 을 만들지 않게** 하자고 했다. 앞 PRP §9-(e)가 직접 렌더를 기각한 두 사유 중 "허브 없는
사용자가 HTML 을 연다"는 사용자가 뒤집었고, "토큰 절감은 같고 위험만 크다"는 이 문서 §2 가 정량화한다.
사용자는 09-21 에 "토큰 비용이 우려돼 개인 PC 에서는 허브를 쓰지 않는다"고 했다 — 그 머신이 (i)형이다.

이 문서는 디스패치가 요구한 8개 질문에 순서대로 답한다 — Q1 비용(§2) · Q2 지침 위치(§3) · Q3 「발행하지
않는다」의 뜻(§4) · Q4 허브 화면(§5) · Q5 이행(§11) · Q6 스위치·명령(§12) · Q7 동시 작업(§13) ·
Q8 마일스톤(§14).

---

## 2. 비용 — Q1

### 2.1 인용하는 실측 (메인 세션 실측, 2026-09-21T10:00Z ~, `tool_use` id 중복 제거)

| 항목 | 값 |
|------|-----|
| 상시 규칙 문단(`rules/workflow/role-separation.md`, 「전체 경로·축약 경로 작업은 …」~「끄기: …」) | **924자 / 1,439B** (이 세션 재측정 923자/1,438B — 경계 1자 차이, 같은 값으로 본다) |
| 헬퍼를 부른 메인 세션 | **3개**, 호출 **26회**, 명령+결과 **9,099자** |
| 이 세션 | 작업 3건에 기록 호출 13회 → **작업당 ≈4.3회, 호출당 ≈385자**. 별도로 측정용 `render` 6회(1회성, 아래 계산에서 제외) |
| 같은 기간 메인 세션 전체 cache_read | **7세션 · API 호출 448회 · ≈1.16억 토큰** → 호출당 평균 컨텍스트 ≈259K 토큰 |
| 측정 스크립트 | 스크래치패드 `dash_calls.py <since>` |

이 세션 실측(보조): 상시 컨텍스트 합계(CLAUDE.md + rules/README.md + rules/common + rules/workflow) =
**55,559B** — `tests/run.sh` T26 상수와 일치. 문단 1,438B 안의 한글 244자 · 그 외 679자.

### 2.2 토큰 환산 (추정 — 토크나이저 없이 문자 구성으로 환산)

- 문단 1,438B ≈ **400 토큰**(한글 244자 ≈ 200 토큰 + ASCII 679자 ≈ 195 토큰. 추정 폭 350~450).
- 기록 호출 1회 385자 ≈ **140 토큰**(명령 + 결과, 추정).
- `commands/dashboard.md` 의 `description` 1줄(스킬 목록에 상시 노출, ≈130자) ≈ **60 토큰**.

### 2.3 설치 형태별 정량화

| 형태 | 오늘의 대시보드 귀속 토큰(이 창 7세션·448호출 기준) | 이 설계 이후 | 절감 | 그중 DN14(직접 읽기) 기여 |
|------|------|------|------|------|
| **(i) coding-harness 만 설치** | 문단 400 × 448 ≈ **179K** + 호출 26회 × 140 ≈ 3.6K + 그 호출이 세션 끝까지 다시 읽히는 꼬리 26 × 140 × ≈32(평균 잔여 호출) ≈ **116K** + 스킬 목록 60 × 448 ≈ **27K** → **≈326K 토큰 ≈ cache_read 의 0.28%(추정 상한)** | **0** — 규칙 문단·기록기·`/dashboard` 명령·`.claude/dashboards/` 생성 전부 없음 | ≈326K 토큰(≈0.3%) | **0.** 전부 이전·게이팅(HD1·HD2)의 몫 |
| **(ii) 허브까지 설치** | 같음(≈326K) | 문단 → 허브 배포 규칙 **1,345B(이 세션 실측 초안, §10.1)** ≈ 같은 크기 · 기록 호출 횟수 같음(4.3회/작업) · `init` 출력이 `OK <경로>` → `OK` 로 ≈40자 짧아짐 · 스킬 목록 1줄 −60 토큰/호출 | ≈27K + 미미(≈0.03%) | **0.** 허브는 모델 토큰을 쓰지 않는다(§2.4) |

**결론.** "비용 감소 효과도 있는가" — **있지만 작다.** (i)형에서 ≈0.3%, (ii)형에서 ≈0. 금액으로 옮기면
(model-routing.md 의 단가 기준, cache_read = 입력 단가의 10%) opus 에서 326K 토큰 ≈ **$0.16** / 2일 창.
1단계가 이미 재주입 63K 토큰/세션(스킬 `init` 재호출)과 편집 출력을 없앴고, 남은 것은 문단 1개와 Bash
한 줄 몇 회다. **직접 읽기(DN14)는 토큰과 무관한 구조 정리**(허브의 60KB HTML 쓰기·파싱 왕복 소멸 —
작업당 5~8회 × 60KB 쓰기, 수집 사이클마다 프로젝트 × 세션 수만큼의 정규식 파싱)이고, **게이팅은 허브 없는
머신의 발자국을 0 으로** 만드는 것이다. 이 둘이 사용자 요청의 본체이므로 절감이 작아도 진행할 가치가
있다 — 단, "토큰 때문에" 하는 일은 아니라고 적어 둔다.

### 2.4 「허브는 모델 토큰을 쓰지 않는다」 — 메인 세션 주장 3건 검증

| 주장 | 판정 | 근거 |
|------|------|------|
| 훅 명령 `python3 "$HOME/.claude/hub/bin/hub_hook.py" >/dev/null 2>&1 \|\| true` 는 stdout 을 내지 않는다 | **맞다 — 단, 그 `>/dev/null` 이 유일한 방벽이다** | `hub_settings.HOOK_COMMAND` 원문 확인. Claude Code 문서(hooks-guide 「Re-inject context after compaction」): **`SessionStart`·`UserPromptSubmit`** 훅의 stdout 은 모델 컨텍스트에 더해진다. 허브는 같은 명령을 6이벤트에 쓰므로 리다이렉트를 빼는 순간 두 이벤트에서 토큰을 쓰기 시작한다 — §3 안 B 를 기각하는 근거이자, 훅 명령 문자열이 설치 판정 키라는 제약과 함께 「바꾸지 않는다」로 굳힌다 |
| statusLine 출력은 모델에 가지 않는다 | **맞다** | `hub_statusline.py` 의 stdout 은 상태줄 표시 채널이다(문서: statusLine 은 표시 전용) |
| `hub_usage_fetch.py` 의 `/api/oauth/usage` 는 사용량 조회라 메시지 호출이 아니다 | **맞다** | Messages API 가 아니고 토큰 청구 대상이 아니다 |

정정할 것은 없다. 덧붙일 것 하나: coding-harness 가 배포하는 **`commands/hub.md` 의 `description`** 은 스킬
목록으로 상시 노출된다(≈100자) — 허브가 아니라 coding-harness 의 상시 비용이고 이 설계로 바뀌지 않는다.

---

## 3. 허브 설치 시 기록 지침을 어디에 두나 — Q2

### 3.1 전제 (문서 확인, 2026-09-23)

- `~/.claude/rules/` 아래 **하위 디렉터리의 `.md` 도 재귀적으로 로드**되고, 사용자 범위 규칙은 **모든 프로젝트**에
  적용된다(memory 문서 「Set up rules」·「User-level rules」). 이 저장소가 배포하는 `rules/common/`·`rules/workflow/`
  가 그 경로로 로드되고 있는 것이 실증이다.
- **startup 콘텐츠(CLAUDE.md·규칙)는 메시지 히스토리 밖에 살고 compact 뒤 다시 로드된다**(context-window 문서:
  "startup content, which lives outside the message history and reloads after compaction"). 반대로 **스킬 설명
  목록은 compact 뒤 재주입되지 않는다**(`noSurviveCompact`).
- `SessionStart` 훅은 `source: compact` 로 compact 뒤 **다시 발화**하고 그 stdout 이 컨텍스트에 들어간다.

### 3.2 후보 비교

| 안 | 배포·소유 | compact 뒤 생존 | 비용(토큰) | 문제 |
|----|-----------|----------------|-----------|------|
| **A. `hub/install.sh` 가 `hub/rules/dashboard-recording.md` → `~/.claude/rules/hub/` 로 배포 (권고)** | 허브 설치기가 소유. coding-harness `install.sh` 는 이 파일을 **모르며 건드리지 않는다** — `check_directory_conflict` 는 "대상에만 있는 파일은 충돌로 보지 않는다"(D1), 복사는 `cp -R rules/. target/`(추가만), 삭제는 `removals.txt` 툼스톤 + 대장 해시 일치 때만(D-2). manifest v3 대장은 coding-harness 가 배포한 파일만 적으므로 허브 규칙은 대장 밖이다 — **두 채널이 같은 디렉터리를 공유하되 파일 집합이 서로소**다 | **생존**(startup 콘텐츠) | (ii)형만 ≈400 토큰/호출 — 오늘과 같음 | `~/.claude/rules/` 에 coding-harness 가 모르는 파일이 산다 — 그러나 이 디렉터리는 원래 사용자 소유이고 coding-harness 는 소유권 원칙상 남의 파일을 지우지 않는다. `hub/install.sh --uninstall` 이 제거해야 한다(§11.6) |
| B. 허브 `SessionStart` 훅이 지침을 stdout 으로 주입 | 허브 소유. **훅 명령 문자열을 바꿔야 한다**(`>/dev/null` 제거 또는 별도 7번째 엔트리) — 문자열은 `_entry_has_hub_marker` 의 설치 판정 키라 **기존 설치본은 자동 갱신되지 않는다**(`hub_settings.py` 주석: `/hub off` → `/hub install` 재실행 필요) | **생존**(compact 재발화 — 문서화된 유일한 보장) | 같음(≈400 토큰) — 다만 허브가 처음으로 모델 토큰을 쓰는 구성이 된다(§2.4 주장 1 파기) | 설치 키 변경·기존 머신 무갱신·`UserPromptSubmit` 도 같은 명령이라 출력을 이벤트별로 갈라야 함·지침이 `/memory` 에 보이지 않아 발견 불가 |
| C. `role-separation.md` 에 조건문("허브가 설치돼 있으면 …")으로 남긴다 | coding-harness 소유(오늘과 같음) | 생존 | **(i)형도 계속 ≈400 토큰/호출** — 게이팅 목표 불달성 | 사용자 요청 ②의 정면 반대. 기각 |
| D. A + `role-separation.md` 에 1줄 포인터("진행 기록은 허브 규칙이 담당") | A 와 같음 + coding-harness 1줄 | 생존 | (i)형 ≈40 토큰/호출 | 포인터의 유일한 효용은 "허브 없는 세션이 기록을 시도하지 않게" 하는 것인데, 규칙이 없으면 시도할 이유도 없다. YAGNI — **기각.** 다만 승인 항목에서 사용자가 원하면 1줄을 넣는다(§17-2 대안) |

**결정: A(HD2).** B 는 허브의 "모델 토큰 0" 성질을 깨고 설치 키를 흔든다. C 는 요청과 반대다.

---

## 4. 「허브가 없으면 HTML 을 발행하지 않는다」의 정확한 의미 — Q3

| 해석 | 남는 것 | 판정 |
|------|--------|------|
| (a) **기록 자체를 하지 않는다** — 지침·기록기·명령 전부 허브 자산. 허브 없는 머신에는 대시보드라는 개념이 없다 | 없음. `.claude/dashboards/` 도 새로 생기지 않는다 | **권고(HD1)** |
| (b) 기록(JSONL)만 하고 HTML 만 안 만든다 | coding-harness 에 지침 문단(≈400 토큰/호출)과 기록기가 남는다 | 소비자 없는 기록이다 — 허브가 없으면 JSONL 을 읽을 것이 아무것도 없다. 사용자의 비용 우려(09-21)와 반대. **기각** |
| (c) HTML 은 만들되 허브 없이도 `file://` 로 본다(오늘) | 오늘 그대로 | 사용자가 뒤집은 전제. **기각** |

(a) 의 귀결: `commands/dashboard.md`·`dashboard_helper.py`·`dashboard_render.py`·`dashboard_template.html`
4파일이 coding-harness 배포 대상에서 빠지고(툼스톤), `role-separation.md` 의 문단이 사라지고, coding-harness README 의
설치 절차에서 「대시보드 옵션 질문」 단계가 사라진다(§11).

---

## 5. 허브 설치 시 화면 — Q4

### 5.1 세션별 HTML 파일을 계속 만들 것인가

| 안 | 내용 | 판정 |
|----|------|------|
| (가) 계속 만든다(헬퍼·렌더러·템플릿을 허브로 옮기기만) | 허브는 오늘처럼 HTML 을 파싱 | **M1 의 중간 상태로만 쓴다.** 최종 상태로는 기각 — DN14-(b)가 없어지는 것(HTML 생성·`Tier1Snapshot` HTML 파싱)이 그대로 남는다 |
| **(나) 허브가 JSONL 로 즉석에서 그린다 — 서버가 `/project/<key>/dashboard.html` 요청을 받으면 JSONL 을 읽어 같은 템플릿·같은 렌더러로 그 자리에서 렌더(권고, HD5)** | 디스크에 `.jsonl` 만 남는다. iframe 의 출처 URL 은 **오늘과 같다**(레지스트리의 값만 `.html` 경로에서 `.jsonl` 경로로 바뀐다) | 화면 바이트가 오늘의 파일과 **동일**하다(같은 이벤트 → 같은 `render_from_events` 출력, 결정적 렌더 DN2). 템플릿 변경 0 — 단 머리 HTML 주석 8행 한 줄(옛 `commands/dashboard.md` 참조)은 M2 가 고친다. `<head>` 안 주석이라 화면에 닿지 않는다 (2026-09-24 재확인, 기준 3d76b81) |
| (다) 허브 페이지(`hub_template.html`) 안에 세션 뷰를 인라인 렌더(iframe 제거) | 폴링·PiP·필터가 허브 쪽으로 통합 | 화면이 크게 바뀌고(목업 필요), `hub_template.html` 을 한창 고치는 워크트리(§13)와 정면 충돌. **이번 회차 기각**, M3 이후 후보로만 기록 |

### 5.2 PiP · `file://` · 단독 탭 · `window.dzRequestRefresh`

| 계약 | 오늘 | M2 이후 | 변화 |
|------|------|--------|------|
| 상세 패널 iframe 출처 | `http://localhost:8794/project/<key>/dashboard.html` → 서버가 **파일 바이트**를 서빙 | 같은 URL → 서버가 **JSONL 을 렌더한 바이트**를 서빙(`X-Content-Type-Options: nosniff`·`Cache-Control: no-store` 유지) | URL·헤더·문서 내용 동일 |
| 템플릿 자체 폴링(`fetch(location.pathname)` 60초 + 가시성·포커스) | 서버가 최신 파일을 돌려준다 | 서버가 요청마다 JSONL 을 다시 렌더한다(신선도 게이트 2초는 **레지스트리 갱신**에만 걸리고, 렌더는 요청 시점 파일을 읽는다) | 동일. 디스패치가 말한 "템플릿 폴링이 없어진다"는 (다)안에서만 성립한다 — (나)에서는 남는다(localhost 60초 1회, 비용 무시) |
| `window.dzRequestRefresh` | 허브 폴링·즉시 갱신 3종이 iframe 의 이 훅을 호출 → 대시보드가 `poll()` | **불변**(템플릿 로직 0변경 — M2 가 고치는 것은 머리 주석 8행 한 줄뿐 (2026-09-24 재확인, 기준 3d76b81)) | 없음 |
| PiP 플로팅 | 서빙 URL 을 최상위 탭으로 열면 `isServed && !isEmbedded` | 같음 | 없음 |
| 단독 탭 | 같은 URL | 같음. `init` 출력에서 URL 이 사라지므로(HD15) hub/README 가 "카드에서 열린 패널의 URL" 을 안내 | 안내 문구만 |
| `file://` 폴백(`.claude/dashboards/<id>.html` 을 Finder 에서 열기) | 가능(포커스 시 갱신) | **불가 — 파일이 없다.** 허브 `file://` 모드(서버 꺼짐)의 패널은 오늘도 대시보드를 띄우지 못하므로(`FILE_MODE_DASHBOARD_HINT`) 허브 쪽 동작은 동일 | **능력 손실 1건** — 서버가 꺼진 머신에서 대시보드를 보는 길이 없어진다(승인 §17-5) |
| 템플릿의 `file://` 분기(갱신 경로 A) | 살아 있음 | 도달 불가한 죽은 분기로 남는다 — **0바이트 유지**(T22 가드가 "회귀 금지 대상"으로 물고 있고, 수술적 변경) | 없음 |

### 5.3 「구세대 파일」 문제의 소멸

오늘 hub/README 「알려진 한계」 첫 항목(플로팅 숨김 CSS 가 없는 구세대 HTML, 잠금 CSS 부재)은 **파일 세대**
문제다. 서버 렌더에서는 템플릿 세대가 언제나 현재 배포본이므로 이 한계 항목이 사라진다(hub/README 갱신).

### 5.4 화면 변화 0 의 근거 (목업을 만들지 않는 이유)

- 허브 카드: `Tier1Snapshot` 의 필드·값이 같다(§9.2) — 템플릿이 읽는 8필드(`title`·`completed`·`total`·`percent`·
  `steps`·`impl_done`·`impl_total`·`session_id`)를 JSONL 파서가 같은 규칙으로 채운다. **한 가지 차이는 결함
  수정이다**: HTML 파서는 이스케이프된 텍스트(`&amp;`)를 돌려줘 템플릿의 `escapeHtml` 이 한 번 더 이스케이프
  했다(`&`·`<` 를 가진 제목이 `&amp;` 로 보이던 잠재 결함). JSONL 파서는 원문을 돌려주므로 제목이 바르게 보인다.
- 상세 패널·단독 탭: 같은 템플릿 + 같은 `render_from_events` → 같은 바이트(템플릿 머리 주석 8행 한 줄만 다르다 — 보이는 화면은 같다 (2026-09-24 재확인, 기준 3d76b81)).
- `hub_template.html` 은 이 설계에서 **0바이트 변경**이다(주석 정정까지 M3 이후로 미룬다, §13).

---

## 6. 설계 결정과 근거 (HD1~HD15)

### HD1 — 허브 없는 설치에는 대시보드가 **존재하지 않는다**
§4-(a). 지침·기록기·`/dashboard` 명령·템플릿·HTML 전부 허브 자산이 된다. 기각: (b) 기록만 남기기(소비자
없는 기록 + 비용 잔존).

### HD2 — 기록 지침은 허브 설치기가 `~/.claude/rules/hub/dashboard-recording.md` 로 배포한다
§3.2 안 A. 두 배포 채널이 `~/.claude/rules/` 를 공유하지만 파일 집합이 서로소이고, coding-harness 는 소유권 원칙상
남의 파일을 지우지 않는다(D1·D-2). compact 뒤 생존은 startup 콘텐츠 재로드로 문서화돼 있다. 기각: B(훅 주입 —
모델 토큰 0 파기·설치 키 변경), C(조건문 — 게이팅 불달성).

### HD3 — 기록기는 `hub/bin/hub_dashboard_log.py`, 얇은 진입점이다
`hub_hook.py`·`hub_statusline.py` 와 같은 관례(자주 불리는 진입점은 `hub.py` 의 argparse·전체 임포트를 거치지
않는다). 런처는 `python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" <서브커맨드> …` 한 형태 —
**프로젝트 폴백(`.claude/commands/…`) 없음**. 허브는 머신 전역 자산이라 프로젝트 사본이 없다(hub/install.sh
서두 R5). 기각: `hub.py dashboard-log …` 서브커맨드 — 호출마다 `hub_daemon`·`hub_server`·`hub_usage_fetch` 까지
임포트하고 `--json` 관례가 폐쇄 어휘 출력과 어긋난다.

### HD4 — 마일스톤 순서: **M1 이전·게이팅(HTML 유지) → M2 직접 읽기**
M1 은 허브 파이썬 0변경으로 배포 채널만 바꾼다(기록기가 옮겨진 자리에서 오늘처럼 JSONL+HTML+사이드카를 쓰고
허브는 HTML 을 읽는다). M2 는 허브 안에서만 일어난다. 기각: 역순(허브가 먼저 JSONL 을 읽고 헬퍼는
commands 에 남기기) — 한 마일스톤 동안 렌더러가 두 채널(`commands/`·`hub/bin/`)에 중복 존재하고, 생산자↔소비자
계약 테스트가 채널을 가로질러 임포트해야 한다. M1 우선이면 중복이 한 번도 생기지 않는다.

### HD5 — 허브 서버가 요청 시 JSONL 을 **같은 템플릿·같은 렌더러로** 렌더한다
§5.1-(나). 화면 변화 0, `hub_template.html` 0변경, 워크트리 충돌 0. 렌더는 요청마다 한다(60KB 문자열 치환
9회 — 밀리초 단위, localhost). 템플릿 파일은 요청마다 읽는다(캐시 없음, YAGNI) — `collect_snapshot` 이
50ms 를 넘기 시작하면 재검토한다는 `read_session_tails` 의 에스컬레이션 조건을 그대로 적용한다.

### HD6 — `Tier1Snapshot` 은 그대로 두고 **생산자만 교체**한다
`Tier1Snapshot`·`StepView` 를 소비하는 hub_project(85건 중 24건 픽스처 — 2026-09-24 재확인, 기준 3d76b81: 총 89건, `be20be4` 가 더한 4건은 대시보드 무관)·hub_session·hub_model·hub_server·
hub_template 은 그대로다. `hub_parse.parse_dashboard_html` 자리에 `parse_dashboard_jsonl` 이 들어가고 필드는
같은 의미로 채운다(§9.2). 소비자 없는 필드(`subtitle`·`matrix_done`·`impl_done`·`impl_total`·`started_at`)는
**상수값으로 유지**한다 — 삭제하면 픽스처 ≈40건과 T25-12 를 흔든다(수술적 변경). 부채로 기록한다(§16).

### HD7 — 레거시 단일 파일 `.claude/dashboard.html` 읽기를 폐기한다
DN9 는 "허브의 레거시 읽기는 그대로다"였다 — **공개 번복**. 이유: (1) 사용자 요청이 "HTML 파싱이 없어진다"이고
레거시 읽기가 그 파싱의 마지막 소비자다. (2) 서버가 렌더 서빙으로 바뀌면 레거시는 "파일 바이트 서빙" 분기를
따로 요구한다 — 두 서빙 모드를 유지할 이유가 09-14 이후 0건 쓰기(DN 실측)인 파일에는 없다. 폐기 대상:
`hub_collect.read_tier1_snapshot`, `hub_project.PROJECT_DASHBOARD_RELATIVE_PATH`·`tier1_file_path` 의 레거시 갈래,
hub/README 서술 3곳(2026-09-24 재확인, 기준 3d76b81: 「프라이버시 고지」·「프로젝트 상세 패널」 첫 문단·「티어 한계」 표 — 「알려진 한계」의 구세대 항목은
통째로 지우고, 「주인 세션 없음」 bullet 의 레거시 칩 문장은 공허하게 참이라 둔다, §7.2.1). `hub_template.html` 의 레거시 면제 분기(`if(!project.tier1.session_id) return true;`,
T25-223 이 물고 있다)는 **그대로 둔다**(도달 불가, 템플릿 0변경 원칙).

### HD8 — 사이드카(`{토큰}.init-values.json`)를 폐기하고 작업 시작 시각 = JSONL `init` 줄의 `time_ms`
RL8 이 사이드카 mtime 을 쓴 이유는 "허브가 JSONL 을 읽지 않기 때문"이었다(DN11 이 같은 이유로 1단계에서
보류). 이제 파서가 읽는 첫 이벤트가 곧 그 값이다 — 같은 시각(헬퍼가 사이드카를 쓴 순간 = `init` 이벤트
`time_ms`)이고, `previous_task_boundary_ms` 의 (c) 갈래(사이드카 부재)는 JSONL 스냅샷에서 도달 불가가 되지만
코드는 그대로 둔다(hub_session 0변경). `hub_project.INIT_VALUES_FILE_NAME_PATTERN`·`session_token*`·
`read_session_dashboard_snapshots` 의 첫 루프가 사라진다 — T25-222 의 `iterdir()` 1회 계약은 그대로 만족한다.

### HD9 — 스위치는 `/hub dashboard on|off`, 판정·쓰기는 기록기 `switch` 가 한다
`commands/hub.md`(coding-harness 배포, 허브 부재 시 안내 절 보유)에 절 하나를 더한다. 실행은
`python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" switch on|off`(프로젝트 cwd 의 `.claude/settings.local.json`,
DN16 의 보증 그대로). 기각: 별도 `/dashboard` 명령 파일을 허브가 `~/.claude/commands/` 에 배포 — 허브
설치기에 세 번째 배포 대상이 생기고 coding-harness 의 `report_global_command_overlap` 과 얽힌다. `hub.py
dashboard-switch --json` — 스위치는 프로젝트 로컬 조작이라 머신 전역 명령인 `hub.py` 의 성격과 다르다.

### HD10 — `commands/dashboard*` 4파일은 툼스톤으로 제거하고 문서는 `hub/README.md` 로 옮긴다
`removals.txt` 에 4줄, `COMMANDS_FILE_COUNT=8`. `dashboard.md` 가 담던 정본(경로 규칙·JSONL 스키마·서브커맨드
표·폐쇄 어휘)은 hub/README 「진행 기록」 절이 이어받아 T22/T25/T34 의 참조 대상이 된다. `on/off` 보증 문장은
hub.md 로(T23).

### HD11 — `hub/install.sh` 에 규칙 배포 채널을 더한다
`hub/rules/*.md` → `~/.claude/rules/hub/`. `HUB_RULE_FILE_COUNT=1`. 수정 감지(`diff -rq`)·설치 검증·dry-run 계획·
완료 메시지에 규칙 경로를 더한다. `--uninstall` 순서: 서버 정지 → 훅 제거 → statusLine 제거 → **규칙 파일 제거
(배포한 이름만 `rm -f`, 디렉터리는 비었을 때만 `rmdir`)** → `bin/` 삭제. 규칙 제거는 `rm -rf` 를 쓰지 않는다 —
남의 파일이 같은 디렉터리에 있을 수 있다(소유권 원칙). (사실 정정, 검수 1회차 F16: T25-23·T25-39 는
`rm -rf "$TARGET_BIN_DIR"` 리터럴을 앵커로 순서를 재므로 — `rm -rf` 의 첫 등장 위치가 아니다 — 이 채널의
`rm -f` 선택은 애초에 그 두 검사와 무관하다.)
`/harness-update` Phase 4b 의 "이미 최신" 비교에 `hub/rules` 비교를 **둘째 줄로** 더한다(T25-228 이 첫 비교 줄의
리터럴과 `server-stop` 순서를 물고 있어 첫 줄은 그대로 둔다).

### HD12 — 신규 가드 ID 는 **T25-2xx 를 쓰지 않는다**
워크트리가 T25-228~T25-239 를 예약했고 main 이 이미 T25-228 을 다른 뜻으로 쓴다(§13). 이 설계의 신규 검사는
**신설 그룹 T40**(`test_hub_dashboard_channel`)과 대시보드 소유 그룹의 뒷번호(T22-176+·T23-12+·T33-3+·T34-3+)에만
둔다. 원장 행도 그 그룹 블록 뒤에만 붙인다. (2026-09-24 재확인, 기준 3d76b81) M1 이 T40-1~11·T40-7a/7b·T22-176·T34-3~6 을 썼고,
T40-12 는 별도 PRP(N7·N8 — 하위 ID T40-12a~d)가 먼저 가져가 **M2 신규는 T40-13~T40-15** 다(§13.3). `main` 은 이제 T25-228~232·T25-241~244 를 쓰고
세션 모달 작업이 T25-233~240 을 쓴다 — 이 규칙의 근거는 더 강해졌다.

### HD13 — 범위 밖: 카드 판정 배지(DN14-(a) 후반)·실행 뷰 병합·reflog 커밋 파생(DN14-(c))
- **배지**: `hub_template.html` 변경이고 화면 변화다 → 워크트리 M2(SC)가 `renderSessionContent` 를 분리한 뒤의
  템플릿을 대상으로 별도 회차 + 목업. 지금 목업을 만들면 병합 시점에 낡는다. 데이터 준비(`Tier1Snapshot` 에
  최근 판정 필드)도 그때 함께 한다(YAGNI — 소비자 없는 필드를 먼저 넣지 않는다).
- **실행 뷰 병합**(세션 페이지에 서브에이전트 실행 칩): 화면 변화 + DN13 의 분업("대시보드 = 선언, 허브 =
  관측") 재검토가 필요하다. 별도 회차.
- **reflog 커밋**: `log commit` 1줄(작업당 1회, ≈140 토큰)을 없애기 위해 허브가 각 프로젝트의 `.git/logs/HEAD`
  라는 새 외부 형식을 읽어야 하고, 세션 밖 커밋·워크트리 HEAD 귀속을 구분할 수 없다. `log commit` 은 "이
  작업의 커밋"이라는 오케스트레이터의 **선언**이라 reflog 관측이 대체하지 못한다(DN13 와 같은 이유). **기각.**

### HD14 — 기록기는 허브 모듈을 **재사용**한다(복제 금지)
`_atomic_write_text` 복제(헬퍼 docstring: "서로 다른 배포 채널이라 임포트하지 않는다")의 전제가 사라졌다 →
`hub_atomic_write.atomic_write_text`. `_dashboard_enabled` → `hub_collect.read_dashboard_enabled(cwd)`(RL10 의 두
도구 합의를 한 함수로). 경로 상수 → `hub_project.SESSION_DASHBOARDS_RELATIVE_DIRECTORY`·`session_dashboard_relative_path`.
이벤트 종류 어휘 → `hub_parse.LOG_EVENT_KINDS`·`STEP_STATES`(생산자와 소비자가 같은 상수를 본다). `hub_collect`
임포트 비용은 `hub_hook.py` 가 매 훅마다 이미 지는 비용과 같다.

### HD15 — M2 에서 `render` 서브커맨드와 `NOTEMPLATE`·`ANCHOR-FAIL` 어휘를 폐기한다
HTML 이 없으니 재발행도 없다. 렌더 실패(템플릿 부재·앵커 불일치)는 서버 쪽 사건이 되어 404 + `server.log` 한
줄로 드러난다(`_serve_project_dashboard` 의 기존 404 접기 관례). `init` 출력은 `OK`(경로 없음).

### HD16 — 개정(2026-10-08): 기록기는 cwd 가 아니라 소유 레포 루트에 쓴다
워크트리 안에서 불러도 기록 파일·오프 스위치·`init` 의 `project` 이름이 `hub_project.fold_worktree_path(cwd)`
기준이다. 워크트리 폴더의 `.claude/dashboards/` 가 `git worktree remove` 때 함께 사라져 허브가 소유 루트의
낡은 기록으로 되돌아가던 결함(끝난 작업이 0%·진행중으로 보임)의 수정이다. 읽는 쪽은 그대로라 옛 버전이
워크트리에 남긴 기록도 계속 읽는다. 위 본문(HD1~HD15)은 고치지 않는다.

---

## 7. 영향 범위

### 7.1 M1 — 이전·게이팅 (HTML 발행 유지, 허브 파이썬 0변경)

| 파일 | 조작 | 이유 |
|------|------|------|
| `commands/dashboard.md` · `dashboard_helper.py` · `dashboard_render.py` · `dashboard_template.html` | **삭제** | HD1·HD10 |
| `removals.txt` | +4줄 | 툼스톤(위 4경로) |
| `install.sh` | `COMMANDS_FILE_COUNT=8` · 35행 주석("실제 removals.txt 는 항상 비어 있으므로") 정정 | 파일 수 · 사실 정정 |
| `hub/bin/hub_dashboard_log.py` | **신설**(≈230줄, `dashboard_helper.py` 이동 + HD14 재사용) | 기록기 |
| `hub/bin/hub_dashboard_render.py` | **신설**(`dashboard_render.py` 그대로 이동, docstring 경로만) | M1 에서는 이벤트 파싱+렌더 그대로 |
| `hub/bin/hub_dashboard_template.html` | **신설**(`dashboard_template.html` 0바이트 변경 이동) | 템플릿 |
| `hub/rules/dashboard-recording.md` | **신설**(§10.1, 1,345B 실측 초안) | HD2 |
| `hub/install.sh` | `HUB_FILE_COUNT=29` · 규칙 채널(복사·검증·수정 감지·dry-run·uninstall 순서·완료 메시지) | HD11 |
| `rules/workflow/role-separation.md` | 문단 삭제(−1,438B) | HD1. 상시 컨텍스트 감소 |
| `CLAUDE.md` | `commands/ 12개` → `8개` · 검증 명령에서 `tests/commands` 줄 삭제 | T39-2 파리티 · 디렉터리 소멸 |
| `README.md` | 커맨드 표 `dashboard` 행 삭제 · `/dashboard` 문단 → 허브 안내 1문단 · 설치 절차 4~6단계(대시보드 옵션 질문) 삭제 · 트리 주석 · 파일 수 62→58 · T26 수치 2곳 | HD1·HD10 |
| `commands/hub.md` | `argument-hint` + `## /hub dashboard on\|off` 절 · 구현 노트의 "dashboard_render.py" → `hub_dashboard_render.py` | HD9 |
| `commands/harness-update.md` | Phase 4b 비교 둘째 줄 + Phase 4 에 "툼스톤이 옛 dashboard 명령을 제거한다" 1문장 | HD11 |
| `hub/README.md` | 「진행 기록」 절 신설(정본 이관) · 설치/제거/파일 배치(29개·규칙 경로) · 상세 패널 절 `/dashboard init` 언급 3곳 | HD10 |
| `tests/run.sh` | §14.1 표 | — |
| `tests/mutations.tsv` | §14.1 표 | — |
| `tests/commands/test_dashboard_helper.py` → `tests/hub/test_hub_dashboard_log.py` · `test_dashboard_render.py` → `tests/hub/test_hub_dashboard_render.py` · `tests/commands/__init__.py` 삭제 | 이동(임포트 경로) | 채널 통합 |
| `tests/hub/test_hub_dashboard_contract.py` | 임포트 경로 1줄 | — |
| `.gitignore` | 무변경(`.claude/dashboards/` 유지) | — |

**무변경(의도적)**: `hub/bin/*.py` 기존 26개 전부 · `hub/bin/hub_template.html` · `tests/hub/test_hub_*.py`
기존 파일(계약 테스트 임포트 1줄 제외) · `rules/` 나머지 45개 · `agents/`.

### 7.2 M2 — 직접 읽기 (허브 안에서만)

**(2026-09-24 재확인, 기준 3d76b81)** `33e1ce9..3d76b81` 네 커밋(`be20be4`·`8f520de`·`ff02bc8`·`3d76b81`) 뒤의 코드·테스트로 이 표를 다시 맞췄다. M2 가 지우거나
바꾸는 대상 — `.html` 대시보드 읽기·사이드카·`read_tier1_snapshot`·`session_token*`·`PROJECT_DASHBOARD_RELATIVE_PATH`·
`INIT_VALUES_FILE_NAME_PATTERN`·`parse_dashboard_html`·`_MAX_VALID_TIME_MS`·`resolve_dashboard_paths`·`render`·`NOTEMPLATE`·`ANCHOR-FAIL` — 의
사용처는 두 커밋 사이 **파일별 건수가 하나도 달라지지 않았다**(`git grep -c` 대조). 네 커밋은 이 대상을 새로 쓰기 시작하지 않았고, 새 유닛
테스트(`test_hub_template_dom.py` 10건·collect W1·project P1/P2·한도 초과 session 22건)와 새 T 가드(T25-229~232·T25-241~244)도 이 대상을
고정하지 않는다. ★ 표시는 **원 계획이 놓친 결합**이다 — 새 커밋 때문이 아니라 이번 재확인에서 드러났다.

| 파일(3d76b81 줄 수) | 조작 | 이유 |
|------|------|------|
| `hub/bin/hub_parse.py`(145) | 재작성(→ ≈290): HTML 정규식 파서 삭제, `DashboardEvent`·`LOG_EVENT_KINDS`·`STEP_STATES`·`parse_event_lines`·`derive_phase_states`·`latest_log_summary`·★`format_event_updated_label`·`snapshot_from_events`·`parse_dashboard_jsonl` 추가(§10.2). 시각 범위 상수 `_MIN_VALID_TIME_MS`·`_MAX_VALID_TIME_MS` 는 **이름·값 그대로** 옮긴다(§13.2-(a)). 모듈 docstring 4행의 `commands/dashboard.md` 인용은 재작성으로 사라진다 | HD6·HD8 |
| `hub/bin/hub_dashboard_render.py`(641) | 이벤트 파싱·축약기(174~354행, 181줄)를 `hub_parse` 로 옮기고 임포트 · ★M1 이 운영 경로에서 뺀 사본(`SESSION_DASHBOARD_DIR`·`_SESSION_ID_PATTERN`·`DashboardPaths`·`resolve_dashboard_paths` — 28~29·602~641행) 삭제 · `_format_event_updated_label` → `hub_parse.format_event_updated_label` 임포트 · ★`hub_parse` 가 HTML 을 읽는다고 전제한 주석 3곳(`_escape_single_line` 근거 425~433행, 로그 렌더 머리 446행, `_render_steps_block` docstring 551행)을 "허브는 HTML 을 파싱하지 않는다 — 출력 바이트를 유지하려고(HD5) 정규화·줄 형태는 그대로 둔다"로 → ≈420 | 단일 출처 |
| `hub/bin/hub_dashboard_log.py`(372) | `cmd_render`·`_render_dashboard_html`·`_find_template`·`TEMPLATE_PATH` 삭제 · `_DashboardPaths` 의 `html_path`·`sidecar_path` 삭제(`hub_project.session_token` 호출 소멸) · 어휘 `NOTEMPLATE`·`ANCHOR-FAIL` 제거 · `init` 출력 `OK` · `_LOG_KINDS`·`_STEP_STATES` → `hub_parse.LOG_EVENT_KINDS`·`STEP_STATES`(HD14) · 리텐션 3패턴 유지(§10.5) · docstring 의 "서브커맨드 5종"·`render` 서술 갱신 → ≈290 | HD8·HD14·HD15 |
| `hub/bin/hub_collect.py`(736) | `read_session_dashboard_snapshots` 가 `*.jsonl` 을 `parse_dashboard_jsonl` 로 읽고 사이드카 루프 삭제 · `read_tier1_snapshot` 삭제 · `_read_tier1_for_root` 레거시 갈래 삭제 · `DASHBOARD_TEMPLATE_PATH` 추가 · 주석 부패: 80·356행 "/dashboard 오프 스위치" → "진행 기록 오프 스위치(`/hub dashboard off`)", 289행 절 머리는 재작성 → ≈690 | HD6~HD8 |
| `hub/bin/hub_project.py`(569) | `SESSION_DASHBOARD_FILE_NAME_PATTERN`·`session_dashboard_relative_path` → `.jsonl` · `PROJECT_DASHBOARD_RELATIVE_PATH`·`INIT_VALUES_FILE_NAME_PATTERN`·`session_token*` 삭제 · `tier1_file_path` 단일 갈래 · 주석 부패: 37행(`SESSION_DASHBOARDS_RELATIVE_DIRECTORY` docstring — "`PROJECT_DASHBOARD_RELATIVE_PATH` 와 같은 이유로"가 삭제로 끊기므로 어차피 다시 쓴다: pathlib 함정 근거를 이리 옮기고 정본을 hub/README 「진행 기록」>「대시보드 경로 규칙」으로) · 51·274행(대상 자체가 삭제된다) · 46행(파일명 패턴 docstring 의 레거시 비교 — `.jsonl` 로 다시 쓸 때 뺀다) · 371·422·543행 `/dashboard` → "기록기"·"진행 기록 오프 스위치(`/hub dashboard off`)" → ≈540 | HD7·HD8 |
| `hub/bin/hub_server.py`(463) | `_serve_project_dashboard` 가 JSONL → `parse_event_lines` → `render_from_events` → 응답(§10.4). **함수 이름 유지** — T25-122 가 AST 로 이 이름의 본문을 뽑아 사용량 API 호출 0 을 본다(성립 확인). 139~140행 주석("이 프로세스가 만든 파일이 아니라 디스크 위의 파일")을 렌더 결과 기준으로 → ≈480 | HD5 |
| `hub/bin/hub_model.py` | docstring 1곳 — `build_dashboard_registry` 의 "{대시보드 키: 파일 절대경로}" → 기록(`.jsonl`) 절대경로 | — |
| ★`hub/bin/hub_usage.py` | 모듈 docstring 8행 "`hub_parse.py`(/dashboard DOM 파서)와 같은 성격" → "`hub_parse.py`(진행 기록 JSONL 파서)와 같은 fail-open 태도". M2 가 hub_parse 의 성격을 바꿔 이 비유가 틀어진다(주석만) | M2 가 틀리게 만드는 주석 |
| ★`hub/bin/hub_dashboard_template.html` | 8행 머리 주석 한 줄 "…, commands/dashboard.md 참조" → "…, hub/bin/hub_dashboard_render.py 앵커 상수·hub/README.md 「진행 기록」 참조". 나머지(로직·앵커 9종·`file://` 분기)는 0바이트. 템플릿 바이트를 고정하는 가드는 없다(확인). §5.1·§5.4 단서 | 주석 부패(M1) |
| `hub/bin/hub_session.py` | **무변경 유지**(HD6·HD8). 조건부 예외 하나: 세션 B(§13.2)가 먼저 병합됐다면 그 주석 한 줄의 모듈명(`hub_dashboard_render.py` → `hub_parse.py`)만 고친다(줄 수 불변 — T25-100). 558·569·579·611행 주석 부패와 M2 가 낡게 하는 (c) 갈래 서술은 **미룬다** — 근거 §13.2-(e) | HD6 |
| `hub_template.html` · `hub_daemon.py` · `hub.py` · `hub_hook.py` | **무변경** | HD6 |
| `hub/README.md` | §7.2.1 표(문장 단위) | — |
| `commands/hub.md` | 구현 노트 티어 1 문단(328~333행 — DOM 계약·매트릭스 구파일 호환 → JSONL 계약). 이 문단을 고정하는 가드는 없다. `be20be4` 의 hub.md 변경(훅 7개)은 다른 절이다 | — |
| ★`tests/hub/fixtures/*.html` 5개 | **삭제** — `test_hub_parse.py` 만 쓴다(확인). 배포 관리 파일이 아니라 툼스톤이 필요 없다 | 고아 |
| `tests/hub/*` | §14.2 표 | — |
| `tests/run.sh` · `tests/mutations.tsv` | §14.2 9·10번 | — |

#### 7.2.1 `hub/README.md` — M2 가 고치는 문장과 두는 문장 (2026-09-24 재확인, 기준 3d76b81)

**원칙: M2 는 (1) M2 의 동작 변화로 사실이 틀어지는 문장과 (2) 테스트가 고정하는 문장만 고친다.** 그 밖의 낡은 표현은 사용자가 나중에
일괄 정리한다 — 대표가 37행 「진행률 줄」의 "`/dashboard` 기록에서 온 작업 제목"이고, **M2 는 37행을 건드리지 않는다.** 행 번호는
`3d76b81` 기준이다 — 세션 A 가 「카드 상세보기」 절(+60 안팎)을 넣으면 뒤쪽이 밀리므로 절 이름으로 찾는다.

| 절(3d76b81 행) | 지금 | M2 뒤 | 근거 |
|---|---|---|---|
| 「프라이버시 고지」(205~206) | 패널 iframe 이 "대시보드 파일(레거시 `.claude/dashboard.html` 또는 세션별 `.claude/dashboards/*.html` 중 가장 최근 것)을 원본 그대로" 보여준다 | "세션별 기록(`.claude/dashboards/*.jsonl`) 중 가장 최근 것을 서버가 그 자리에서 그린 화면" — 노출 범위는 같다 | HD5·HD7 |
| 「화면 배치」 실행 목록 경계(286~292) | 경계 = "기록기 `init` 이 남기는 사이드카 파일의 시각" · "사이드카 파일이 없으면" | "기록기 `init` 이 남기는 첫 기록 줄의 시각" · "기록 파일이 없으면". 굵은 「작업이 시작된 뒤에 시작된 실행만 남는다」·「대시보드를 끈 프로젝트」·「기록기 `init`」 토큰은 그대로 | HD8 · T25-222 ⑬ · T25-90 |
| 「프로젝트 상세 패널」 첫 문단(383~384) | 괄호 "(레거시 `.claude/dashboard.html` 또는 세션별 `.claude/dashboards/*.html` 중 가장 최근 것)" | "(세션별 기록 `.claude/dashboards/*.jsonl` 중 가장 최근 것을 서버가 그린 화면)" — 구 단위 교체 | HD5·HD7 |
| 같은 절, 서빙 키(389) | "그 세션이 발행한 대시보드 파일 자체의 절대경로" | "그 세션의 기록 파일(`.jsonl`) 절대경로" | §9.3 |
| 같은 절, 잠금(398~402) | "이 잠금은 그 프로젝트의 대시보드 파일 세대에 달렸다(구세대 파일에는 잠금 CSS/JS 자체가 없다, 아래 「알려진 한계」 참조)" | 세대 단서 삭제 — 서버가 언제나 지금 템플릿으로 그린다. ★**「텍스트 선택」 토큰을 이 문장에 담는다**(지금은 지울 항목의 555행에만 있다) | §5.3 · T25-146 |
| 같은 절, PiP·단독 탭(406~411) | 구세대 파일 단서 · 단독 탭을 `http://localhost:{포트}/dashboard.html` 로 적음 · "이 단독 탭 URL 은 기록기 `init` 보고에 항상 함께 적힌다" | 구세대 단서 삭제 · "단독 탭은 패널에 열린 `/project/<16자리 hex>/dashboard.html` 그대로다(`init` 은 `OK` 만 낸다)" | HD15 · §5.2 |
| 「진행 기록」 머리 인용(456) | "HTML 은 그 파일의 파생 산출물이며 매 이벤트마다 통째로 다시 그린다" | "화면은 허브 서버가 요청 때마다 그 파일로 그린다 — 디스크에는 `.jsonl` 만 남는다" | HD5 |
| 「대시보드 경로 규칙」(475~485) | "세 파일을 쓴다" + 코드 블록 3줄 · 리텐션 3패턴 | "한 파일을 쓴다" + 코드 블록 1줄. 리텐션 문장은 "`*.jsonl` 과 M1 까지의 **구세대 산출물**(`*.html`·`*.init-values.json` — 허브는 읽지 않는다)". `CLAUDE_CODE_SESSION_ID`·`.claude/dashboards/`·`hub_dashboard_log.py` 유지, 코드 블록의 `.claude/dashboard.html` 0 | HD8 · T22-159 · T22-161 · T25-158 · T25-90 |
| 「데이터 모델」(498~500) | "(`hub_parse._STEP_LINE_PATTERN` 계약 — …)" | "(`hub_dashboard_render._render_steps_block` 이 만든다 — 템플릿 자체 폴링의 부분 치환이 이 id 로 찾는다)" | M2 가 그 심볼을 지운다 |
| 「헬퍼 스크립트」 표(515~525) | 5행(`render` 포함) · `NOTEMPLATE`·`ANCHOR-FAIL` · `init` 출력 `OK <html 절대경로>` · `render` 설명 문장 | 4행(§9.4 그대로) · `render` 문장 삭제 · README 어디에도 `NOTEMPLATE`·`ANCHOR-FAIL` 0. 523행 예시 문장은 둔다(T22 합본 검사가 `설계\|승인\|구현\|검수` 를 README 에서만 찾는다) | HD15 · T34 · T22-137 · T22 합본 |
| 「템플릿 파일」(537) | "하나만 본다(없으면 `NOTEMPLATE`)" | "허브 서버가 요청마다 하나만 읽는다 — 없거나 앵커가 어긋나면 그 요청은 404, `server.log` 에 한 줄" · 파일명 `hub_dashboard_template.html` 유지 | HD15 · T22-136 |
| 「알려진 한계」 첫 항목(545~555) | 구세대 대시보드의 플로팅 노출(잠금 CSS/JS 부재 포함) | **삭제** | §5.3 · T25-146 |
| 「티어 한계」 표 1행(662) | 출처 = `.claude/dashboard.html` 및 `.claude/dashboards/*.html` | `<프로젝트 또는 그 워크트리>/.claude/dashboards/*.jsonl`(여럿이면 mtime 최신) | HD7 |

**M2 가 두는 문장**(공허하게 참이 되거나 M2 와 무관 — 나중 일괄 정리): 37행 「진행률 줄」의 "`/dashboard` 기록" · 457행 "`Skill(dashboard)` 을
기록 경로에서 부르지 않는다" · 445~446행 "레거시 단일 파일에는 … 이 칩이 붙지 않는다"(레거시를 안 읽으니 공허하게 참 — 그 bullet 은 세션 A
가 고치는 중이라 건드리면 충돌만 는다, §13.2-(d)) · 470~471행 사진 설명(화면이 같으므로 참) · 531행 "대시보드 HTML 을 만들지도 지우지도
않는다"(공허하게 참). 테스트가 문장을 고정하는지 전수로 봤다 — README 를 단일 토큰으로 무는 T25 검사 37건 가운데 M2 가 건드리는 것은
T25-146·T25-90 둘뿐이고, T22 합본 검사 토큰 가운데 README 에만 있는 것은 523행 예시 하나다.

---

## 8. 파일 구조와 모듈 경계

### 8.1 저장소 배치 (M2 완료 시)

```
hub/
  install.sh                      # bin/ + rules/ 두 채널을 배포·제거한다(HD11)
  rules/
    dashboard-recording.md        # → ~/.claude/rules/hub/dashboard-recording.md (상시 로드, 허브 사용자만)
  bin/                            # → ~/.claude/hub/bin/ (29개)
    hub_dashboard_log.py          # I/O 진입점 — 기록기 CLI(init·log·step·switch). 얇다
    hub_dashboard_render.py       # ★순수 — 이벤트 → PublishedValues → HTML(앵커 9종 치환)
    hub_dashboard_template.html   # 세션 페이지 템플릿(옛 commands/dashboard_template.html — M1 은 0바이트 이동, M2 는 머리 주석 8행 한 줄만, 2026-09-24 재확인)
    hub_parse.py                  # ★순수, 잎 — JSONL 이벤트 스키마·파서·축약기·Tier1Snapshot 생산
    hub_collect.py                # I/O — .claude/dashboards/*.jsonl 발견·읽기 → Tier1Snapshot(mtime·경로 보강)
    hub_server.py                 # I/O — /project/<key>/dashboard.html 요청 시 JSONL 렌더 서빙
    … (나머지 23개 — hub_project 는 수정, hub_model·hub_usage 는 docstring 만, §7.2 (2026-09-24 재확인, 기준 3d76b81))
```

프로젝트 로컬(런타임):
```
<project>/.claude/dashboards/<세션 ID>.jsonl        # 상태의 단일 출처 — 유일한 산출물
<project>/.claude/settings.local.json                # dashboard_enabled (RL10·DN16, 그대로)
```

### 8.2 임포트 그래프 (화살표 = 임포트한다)

```
hub_dashboard_log (I/O)  → hub_parse(어휘) · hub_project(경로) · hub_collect(read_dashboard_enabled) · hub_atomic_write
hub_dashboard_render (★) → hub_parse(DashboardEvent·derive_phase_states)
hub_server (I/O)         → hub_collect · hub_dashboard_render · hub_parse · hub_project (+기존)
hub_collect (I/O)        → hub_parse(parse_dashboard_jsonl) (+기존)
hub_parse (★, 잎)        → (허브 모듈 임포트 0 — 오늘과 같다)
```

순환 없음: `hub_parse` 는 잎이고 `hub_project → hub_parse` 방향은 오늘과 같다. `hub_dashboard_render` 는
`hub_parse` 만 본다. 기록기가 `hub_collect` 를 임포트하는 것은 hub_hook.py 의 선례다.

### 8.3 계층 원칙 (프로젝트 CLAUDE.md §2)

- 외부 세계에 닿는 것: `hub_dashboard_log`(cwd 파일·환경변수·시각)·`hub_collect`(파일)·`hub_server`(소켓·파일).
- 순수: `hub_parse`(★, T25-10 대상)·`hub_dashboard_render`(★, T25-10 대상에 추가). 둘 다 `open(`·`Path(`·`os.` 0.
- 통신은 frozen dataclass 로만: `DashboardEvent`(JSONL 한 줄) · `Tier1Snapshot`(허브 계약, 무변경) ·
  `PublishedValues`(렌더 값, 무변경).

---

## 9. 데이터 모델

### 9.1 `DashboardEvent` — JSONL 이벤트 (변경 없음, 위치만 `hub_parse.py`)

DN §6.2 그대로다. 1단계 헬퍼가 09-21 이후 써 둔 `.jsonl` 은 **그대로 읽힌다**(같은 스키마 — 이행 비용 0).

```
DashboardEvent(frozen)
  time_ms : int                 # 2000-01-01 ~ 2100-01-01 범위 밖은 줄 단위로 버린다(1단계 검수 H2 그대로)
  kind    : "init" | "design" | "approve" | "impl" | "pass" | "fail" | "commit" | "note" | "step"
  title, phases(tuple[str,...]), project        # init
  summary, detail                               # log 7종
  index(1-based), state("done"|"active"|"wait") # step
```
공개 상수: `LOG_EVENT_KINDS = ("design","approve","impl","pass","fail","commit","note")`, `STEP_STATES`.
생산자(기록기)와 소비자(파서·렌더러)가 이 상수를 함께 본다(HD14).

### 9.2 `Tier1Snapshot` ← 이벤트 대응표 (HD6 — 필드·타입 무변경)

| 필드 | 오늘(HTML 파서) | M2(JSONL 파서 `snapshot_from_events`) |
|------|----------------|------|
| `title` | `<h1 id="dz-title">` 텍스트(이스케이프된 채) | `init.title` **원문** |
| `subtitle` | `#dz-subtitle` 또는 "" | `""`(상수) |
| `completed`·`total`·`percent` | `#dz-progress-pct` 파싱 | `derive_phase_states` → done 수 / 단계 수 / `round(M/N×100)` — 렌더러와 같은 산식 |
| `steps[i]` | `<li id="dz-step-n">` 정규식 | `StepView(index=i+1, name=phases[i], state, detail=활성이면 최근 로그 요약 원문 else "", started_at=None)` |
| `matrix_done`·`impl_done`·`impl_total` | 정규식 계수 | `None`·`0`·`0`(상수 — 템플릿의 impl 표시는 0/0 이면 오늘처럼 숨는다) |
| `updated_text` | `#dz-updated` 텍스트 | `"갱신: YYYY-MM-DD HH:MM"`(마지막 이벤트 `time_ms`, 로컬 시간대 — 렌더러 `_format_event_updated_label` 과 같은 함수) |
| `file_mtime_ms`·`source_path`·`session_id` | hub_collect 가 `dataclasses.replace` | 같음(값은 `.jsonl` 의 stat·부모·파일명) |
| `task_started_at_ms` | hub_collect 가 사이드카 mtime | **파서가 채운다** — `init.time_ms`(HD8) |

`parse_dashboard_jsonl(text) -> Tier1Snapshot | None`: `parse_event_lines` 가 빈 튜플(init 없음)이면 `None` →
hub_collect 가 오늘의 "DOM 계약 불일치" 자리에서 경고 1건을 남기고 건너뛴다(같은 fail-open 태도).

### 9.3 레지스트리·서빙 (HD5·HD7)

- `build_dashboard_registry(snapshot) -> dict[str, str]` 는 서명·의미 그대로 — 값이 **`.jsonl` 절대경로**가 된다
  (`tier1_file_path` 가 `.claude/dashboards/<id>.jsonl` 을 조립). 키 규칙(`project_dashboard_key`·`dashboard_file_key`)
  무변경 — 단, 값이 바뀌므로 세션 키의 해시 입력이 달라져 **M2 배포 직후 열려 있던 패널은 첫 폴링에서 404 →
  다음 수집 뒤 새 키로 회복**한다(오늘도 파일이 바뀌면 같은 일이 생긴다, U20 의 직전 레지스트리 유지 관례).
- 세션 ID 는 서버가 레지스트리 값의 파일명에서 `hub_project.session_id_from_dashboard_file_name`(`.jsonl` 패턴)으로
  판다 — 값 타입을 튜플로 바꾸지 않는다(hub_server 테스트 10건의 `dashboard_paths_by_key` 계약 유지).

### 9.4 기록기 출력 폐쇄 어휘 (M2 기준, G2 표의 정본은 hub/README 「진행 기록」)

| 서브커맨드 | 인자 | 출력 |
|---|---|---|
| `init` | `'<제목>' '<단계1\|…>'` | `OK` \| `NOSESSION` \| `DISABLED` \| `MKDIR-FAILED` |
| `log` | `<design\|approve\|impl\|pass\|fail\|commit\|note> '<요약>' ['<상세>']` | `OK` \| `NOSESSION` \| `DISABLED` \| `NOINIT` \| `BADKIND` |
| `step` | `<n> <done\|active\|wait>` | `OK` \| `NOSESSION` \| `DISABLED` \| `NOINIT` \| `BADINDEX` |
| `switch` | `on\|off` | `ON` \| `OFF` \| `INVALID-SETTINGS` |

M1 에서는 오늘의 표(`render` 포함, `NOTEMPLATE`·`ANCHOR-FAIL`·`OK <html 절대경로>`)가 그대로다.

---

## 10. 인터페이스

### 10.1 허브 규칙 파일 `hub/rules/dashboard-recording.md` (이 세션 실측 1,345B — 편집 후 재측정해 T40-5 상수로 고정)

```markdown
# 허브 진행 기록 (hub/rules/dashboard-recording.md — hub/install.sh 가 배포·제거한다)

- **전체 경로·축약 경로 작업은 진행 상황을 허브에 기록한다** — 아래 기록기를 Bash 로 직접 부른다
  (인자는 홑따옴표. 본문의 `'` 는 `’` 로 바꾼다):
  `python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" <서브커맨드> …`

  | 시점 | 호출 |
  |------|------|
  | 착수 보고 | `init '<제목>' '설계|승인|구현|검수'` (축약 경로: `'구현|검수'`) |
  | PRP 작성 완료 | `log design '<요약>'` |
  | 사용자 승인 수령 | `log approve '<요약>'` |
  | 구현 완료(회차마다) | `log impl '<요약>' ['<상세>']` |
  | 검수 결과 | `log pass '<요약>' ['<상세>']` 또는 `log fail …` — 회차는 자동 |
  | 커밋·푸시 | `log commit '<커밋 제목>'` |

  단계 상태·진행률·활성 단계 상세는 위 기록에서 파생된다 — 서브에이전트 디스패치·결과 시점에는
  아무것도 기록하지 않는다(허브가 호스트 기록으로 그린다). 출력이 `OK` 가 아니면(`NOSESSION`·
  `DISABLED`·`NOINIT`…) 그 한 줄만 착수 보고에 남기고 이후 호출을 생략한다.
  끄기: `/hub dashboard off` — `.claude/settings.local.json` 의 `dashboard_enabled`(나만·커밋 안 됨).
```

- `paths:` frontmatter 없음(상시 로드). `dashboard_enabled`·`.claude/settings.local.json` 리터럴 유지(T25-222 ⑬
  재조준 대상). 런처 정규형은 이 파일과 hub/README 에 각 1회(T33-2 재조준). `Skill(dashboard)` 금지 문장은
  스킬이 사라지므로 뺐다.
- `role-separation.md` 에서 빠지는 문단: 1,438B → T26 상수 55,559 → **≈54,068B(추정 — 문단 1,438 + 뒤따르는
  빈 줄 1 + CLAUDE.md 검증 명령 1줄 52; 편집 후 실측으로 고정)**. README 의 두 선언도 같은 값으로.

### 10.2 `hub/bin/hub_parse.py` (★순수, 잎) — 공개 함수

```python
LOG_EVENT_KINDS: tuple[str, ...]; STEP_STATES: frozenset[str]

@dataclass(frozen=True)
class DashboardEvent: ...                                   # §9.1

def parse_event_lines(text: str) -> tuple[DashboardEvent, ...]:
    """JSONL 본문 → 이벤트 열. 줄 단위 fail-open('\n' 분할, U+2028 보존). 마지막 init 이후만."""

def derive_phase_states(phases: tuple[str, ...], events: tuple[DashboardEvent, ...]) -> tuple[str, ...]:
    """DN4 축약기(무변경). 각 단계의 'done'|'active'|'wait'."""

def latest_log_summary(events: tuple[DashboardEvent, ...]) -> str:
    """가장 최근 로그 요약 원문(DN6). 없으면 ''. 렌더러와 스냅샷이 공유한다."""

def snapshot_from_events(events: tuple[DashboardEvent, ...]) -> Tier1Snapshot:
    """§9.2 대응표. events[0] 은 init 이어야 한다(parse_event_lines 계약)."""

def parse_dashboard_jsonl(text: str) -> Tier1Snapshot | None:
    """= snapshot_from_events(parse_event_lines(text)); init 이 없으면 None(호출자가 경고 후 건너뛴다)."""
```
삭제: `parse_dashboard_html`, `_TITLE/_SUBTITLE/_PROGRESS/_UPDATED/_STEP_LINE/_IMPL_LINE/_CELL_LINE_PATTERN`,
`_parse_steps`, `_count_matrix_done`, `_count_impl_progress`. 유지: `StepView`, `Tier1Snapshot`(필드·기본값 전부),
`UNSET_FILE_MTIME_MS`, `UNSET_SOURCE_PATH`.

**보강 (2026-09-24 재확인, 기준 3d76b81)**: `def format_event_updated_label(time_ms: int) -> str` 을 **공개**로 둔다 — 렌더러의
`_format_event_updated_label`("갱신: YYYY-MM-DD HH:MM", 로컬 시간대)을 옮긴 것이다. §9.2 의 `updated_text` 와 렌더러의 `#dz-updated` 가
"같은 함수"를 쓰려면 잎인 `hub_parse` 가 가져야 하고, 렌더러는 그것을 임포트한다(비공개 이름을 모듈 밖에서 임포트하지 않는다). 시각 범위
상수 `_MIN_VALID_TIME_MS`·`_MAX_VALID_TIME_MS` 는 이름·값 그대로 옮긴다 — 다른 세션의 주석이 이 이름을 인용한다(§13.2-(a)).

**검수 반영 (2026-09-25, M2 검수 1회차 RA1~RA3).** M2 부터 이 파서는 허브의 공용 수집 루프와 요청 처리 경로에서 매번 돈다 —
M1 까지는 기록기 CLI 안에서만 돌아 예외가 그 호출에 갇혔지만, 이제 한 줄의 예외가 모든 프로젝트의 수집을 멈추고 요청을 끊는다(실측).
그래서 계약을 셋 더한다. ① **줄 단위 fail-open 을 `hub_session.parse_event_line`(`63f5c23`)과 같은 수준으로** — `json.loads` 의
`ValueError`(자릿수 폭탄 포함)·`RecursionError`(깊은 중첩)를 그 줄만 버리는 것으로 흡수하고, `kind`·`state` 는 문자열인지 먼저 본 뒤
멤버십을 검사하며(리스트·dict 의 `TypeError: unhashable` 차단), `index`·`time_ms` 에서 `bool` 을 거부한다. `hub_collect.
read_session_dashboard_snapshots` 는 파일 단위 최종 방어선(좁은 예외 3종 → 그 파일만 건너뛰고 경로가 든 경고 1건)을 둔다. ② **단계 수
상한 `_MAX_PHASE_COUNT = 32`** — 넘는 `init` 은 무효(→ 기존 「init 없음」 경로: 수집은 경고 1건, 서버는 404). 정상 사용은 2~4단계라 8배
여유이고, 상한이 없으면 파싱 비용이 단계 수 × 이벤트 수로 이차가 된다(6000×6000 에서 1.1초 실측). 기록기는 이 파서를 부르지 않으므로
(`LOG_EVENT_KINDS`·`STEP_STATES` 상수만 재사용) 기록기 출력 어휘는 그대로다. ③ **응답 인코딩 정규화** — 고립 서로게이트가 응답을 깨지
않게 서버가 `hub_atomic_write.encode_safe_utf8`(hub.html 쓰기와 같은 U+FFFD 규칙, 이번에 공개 이름으로 올렸다)을 거쳐 인코딩한다(§10.4).
①·③ 의 입력은 정식 기록기가 만들지 않는다 — 스캔 루트 아래 저장소가 `.claude/dashboards/<uuid>.jsonl` 을 커밋해 둔 경우가 유입 경로다.
② 는 다르다(검수 2회차 RC2) — 기록기는 단계 수를 제한하지 않아 33단계 이상의 `init` 도 `OK` 로 받아 쓰고, 허브는 그 기록을 읽지 않는다
(수집 경고 「init 없음 또는 무효」, 서버 404). 기록기 쪽 거부는 닫힌 출력 어휘(T34)를 바꿔야 해 이번 범위 밖이고, 대신 README 데이터
모델 표의 `init` 행에 상한을 적는다. 기록 규칙이 쓰는 단계는 2~4개라 실제로 닿을 일은 없다.

### 10.3 `hub/bin/hub_dashboard_render.py` (★순수)

`commands/dashboard_render.py` 에서 이벤트 파싱·축약기·`resolve_dashboard_paths` 를 뺀 나머지 그대로:
`PublishedValues`, `AnchorMismatch`, `ANCHOR_*` 9종, `escape_for_dom`, `render_reissue`, `render_detail_html`,
`render_log_entry_lines`, `build_published_values(events, session_id)`, `render_from_events(template_text, events, session_id)`.
**사실 갱신 (2026-09-24 재확인, 기준 3d76b81)** — 기록기 쪽 경로 계산은 M1 이 이미 `hub_dashboard_log._resolve_paths`(hub_project 상수 재사용)로
만들었다. 렌더러의 `resolve_dashboard_paths` 는 M1 부터 호출되지 않는 사본이다. M2 는 그 사본(`SESSION_DASHBOARD_DIR`·`_SESSION_ID_PATTERN`·
`DashboardPaths`·`resolve_dashboard_paths`)을 지우고, `_resolve_paths` 는 `.jsonl` 경로 하나만 돌려준다. `_OWNER_TOKEN_LENGTH`(로그의
`data-owner-token`)는 렌더러에 남는다.

### 10.4 `hub/bin/hub_server.py` — 세션 페이지 렌더 서빙

```python
def _serve_project_dashboard(self, dashboard_key: str) -> None:
    """레지스트리 값(.jsonl 절대경로) → 읽기 → parse_event_lines → render_from_events → text/html 응답.
    모르는 키·파일 부재·init 없음·AnchorMismatch·템플릿 읽기 실패는 전부 404 로 접고, 뒤의 둘은
    server.log 에 한 줄 남긴다(배포 결함이라 사용자가 알아야 한다)."""
```
`hub_collect.DASHBOARD_TEMPLATE_PATH = SCRIPT_DIR / "hub_dashboard_template.html"` 을 요청마다 읽는다(HD5).
`nosniff`·`no-store` 헤더는 `_respond_with_html` 관례 그대로.

### 10.5 `hub/bin/hub_dashboard_log.py` — 기록기 CLI

```python
def main(argv: list[str]) -> int          # init|log|step|switch 디스패치. 알 수 없는 서브커맨드는 stderr + exit 2
def cmd_init(title: str, phases_arg: str) -> None
def cmd_log(args: list[str]) -> None
def cmd_step(args: list[str]) -> None
def cmd_switch(state_arg: str) -> None    # DN16 그대로. 다른 필드 보존, 파싱 실패 시 무기록
```
- 세션 ID = `CLAUDE_CODE_SESSION_ID`(UUID 아니면 `NOSESSION`). 경로 = `hub_project.session_dashboard_relative_path(id)`
  (cwd 기준). 켜짐 판정 = `hub_collect.read_dashboard_enabled(os.getcwd())`. 쓰기 = `hub_atomic_write.atomic_write_text`.
- 리텐션(`init`): 7일 초과 `*.jsonl` + 구세대 산출물(`*.html`·`*.init-values.json`) 정리 — 세 패턴 유지(한 릴리스
  뒤 두 패턴을 걷는 것은 후속 청소).
- `sys.dont_write_bytecode` 는 뺀다 — 그 이유(commands/ 파일 수 오염)가 사라졌다. (2026-09-24 재확인, 기준 3d76b81) M1 이 이미 뺐다.

### 10.6 `hub/install.sh` 추가 인터페이스

```
readonly HUB_FILE_COUNT=29
readonly HUB_RULE_FILE_COUNT=1
readonly SOURCE_RULES_DIR="$REPO_ROOT/hub/rules"
readonly TARGET_RULES_DIR="$HOME/.claude/rules/hub"
copy_managed_rule_files()      # find "$SOURCE_RULES_DIR" -maxdepth 1 -type f -name '*.md' → cp
remove_managed_rule_files()    # 배포한 이름만 rm -f, 비었으면 rmdir (--uninstall 4번째 단계)
```
`--dry-run` 계획에 규칙 줄 추가, `list_differing_managed_files` 에 규칙 디렉터리 `diff -rq` 추가, 완료 메시지에
"규칙 1개 → ~/.claude/rules/hub/ (허브 사용자만 진행 기록 지침을 받는다)".

### 10.7 `commands/hub.md` 신설 절 (T23 보증 문장 3개를 그대로 담는다)

```
## `/hub dashboard on|off` — 이 프로젝트의 진행 기록 켜기·끄기
python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" switch on|off
```
"`.claude/settings.local.json` 의 `dashboard_enabled` 필드만 원자적으로 쓴다. **기존 필드는 어떤 경우에도
건드리지 않는다** — 파일을 통째로 덮어쓰면 사용자의 권한 허용 목록이 사라진다. 파싱에 실패하면 `INVALID-SETTINGS`
를 내고 쓰지 않는다. 이 절차는 기록 파일을 만들지도 지우지도 않는다 — 다음 `init` 부터 기록 여부가 바뀔 뿐이다."

---

## 11. 기존 머신의 이행 — Q5

### 11.1 `~/.claude/commands/dashboard*` 청소
`removals.txt` 에 `commands/dashboard.md`·`commands/dashboard_helper.py`·`commands/dashboard_render.py`·
`commands/dashboard_template.html`. `process_removals` 의 판정 그대로: 대장 해시 일치(D-2) → 삭제, 사용자 수정
(D-4)·v1 대장(D-3) → 보호 + 안내. `validate_removals_file` 은 레포에 파일이 없음을 요구하므로 삭제 커밋과 같은
커밋에 넣는다. `install.sh` 35행 주석과 `tests/run.sh` 8883행 주석("실제 removals.txt 는 항상 비어 있음")은
사실 정정 — T27-9 는 원본 removals.txt 로 빈 샌드박스에 설치하는 검사라 D-1(대상 없음 → skip)로 계속 통과한다.

### 11.2 project scope 설치
`install.sh --scope project` 를 다시 돌리면 같은 툼스톤이 `.claude/commands/dashboard*` 를 지운다. 규칙 런처의
프로젝트 폴백(`.claude/commands/dashboard_helper.py`)은 문단과 함께 사라진다(HD3 — 새 런처에 폴백 없음).

### 11.3 `/harness-update` 순서
Phase 4(coding-harness: 문단 삭제 + 툼스톤) → Phase 4b(허브: `bin/` + `rules/`). Phase 4b 의 "이미 최신" 비교에
`diff -rq "$repo_path/hub/rules" "$HOME/.claude/rules/hub"` 를 둘째 줄로 더해, `bin/` 이 같아도 규칙만 바뀌면
재설치가 돈다.

**구현 개정(M1 검수 1회차 M2, 2026-09-24) — 3분기.** 두 비교의 조합으로 갈린다: (1) 둘 다 건너뛰기 조건을
만족 → 전부 건너뛴다(서버 그대로) · (2) `bin/` 비교가 건너뛰기 조건을 못 넘음 → 기존 1~5단계(서버 정지·재설치·
재시작) · (3) `bin/` 은 같고 규칙 비교만 다름(대상 디렉터리 부재로 인한 `diff` 오류 포함) → **서버 상태 확인·정지·
재시작 없이 `hub/install.sh` 만** 실행한다. 근거: 서버 프로세스는 `hub/rules/*.md` 를 읽지 않으므로 규칙만 바뀐
재설치에 서버를 멈출 이유가 없다 — `9f23534`(허브가 이미 최신이면 서버를 끄지 않는다)의 연장이고, 그 커밋이
막으려던 「불필요한 server-stop 요구 → 자동 모드 분류기 거부」가 규칙 배포 때문에 재발하지 않게 한다.
T40-7a(비교 줄이 `server-stop --json` 보다 앞)·T40-7b(3번 분기 서술 존재)가 고정한다.

틈 분석:

| 상황 | 결과 | 대응 |
|------|------|------|
| 업데이트 전에 시작해 살아 있는 세션(옛 문단이 컨텍스트에 있음) | 다음 기록 호출이 `python3: can't open file …dashboard_helper.py` | 규칙의 "OK 아니면 한 줄 남기고 이후 생략"으로 흡수. 배포 시점에 살아 있는 세션 수만큼의 1회성 단절(DN §8 과 같은 종류) |
| 허브 설치 머신에서 `install.sh --scope user` 만 손으로 돌림(Phase 4b 없음) | 문단은 사라졌고 허브 규칙은 아직 없음 → 기록이 **조용히 멈춘다** | `/harness-update` 를 쓰면 생기지 않는다. README·hub/README 에 "허브 사용자는 `hub/install.sh` 도 함께" 1줄. `hub/install.sh` 재실행으로 즉시 회복 |
| 역순(허브만 먼저 갱신, coding-harness 는 옛 것) | 두 지침이 공존(옛 헬퍼도 아직 있음) — 오케스트레이터가 둘 중 하나를 따르거나 둘 다 부른다. 같은 JSONL 에 `init` 이 두 번 쓰이면 뒤가 이긴다(손상 아님) | `/harness-update` 순서(4 → 4b)가 이를 막는다. 과도기 1회성 |
| 허브 미설치 머신 | Phase 4 만 — 문단·명령 소멸, 아무것도 새로 생기지 않음 | 요청 ② 그대로 |

### 11.4 각 프로젝트에 이미 쌓인 `.claude/dashboards/*`
M1: 그대로(기록기가 같은 3종을 계속 쓴다). M2: `.jsonl` 은 **그대로 읽힌다**(같은 스키마), `.html`·`.init-values.json`
은 더 쓰지도 읽지도 않으며 `init` 의 7일 리텐션이 걷는다. 이 저장소 실측: html 3·jsonl 2·사이드카 3.

### 11.5 `/dashboard` 스킬을 기억하는 compact 요약
스킬 설명 목록은 compact 뒤 재주입되지 않으므로(§3.1) 요약에 남은 "/dashboard" 언급이 새 세션을 오도할 가능성은
낮다. 오도되어 `Skill(dashboard)` 을 부르면 "no such skill" 로 즉시 드러난다.

### 11.6 `hub/install.sh --uninstall`
순서: 서버 정지 → 훅 제거 → statusLine 제거 → **규칙 파일 제거** → `bin/` 삭제. 규칙을 지우지 않으면 모든 세션이
존재하지 않는 기록기를 가리키는 문단을 계속 받는다(가장 나쁜 잔존 상태 — `bin/` 을 먼저 지우면 안 되는 이유와
같은 부류). 완료 메시지에 "각 프로젝트의 `.claude/dashboards/*.jsonl` 은 지우지 않았다(열거 불가)" 1줄.

---

## 12. `/dashboard on|off` 와 `commands/dashboard.md` 의 행방 — Q6

- **`/hub dashboard on|off` 로 합친다(HD9).** `commands/dashboard.md` 는 삭제(툼스톤). 이유: 명령 파일을 허브가
  따로 배포하려면 세 번째 배포 대상과 coding-harness `report_global_command_overlap` 과의 상호작용이 생긴다. hub.md 는
  이미 "허브가 없으면 안내하고 중단" 절을 갖고 있어 hub-less 머신에서 `/hub dashboard off` 도 그 절로 흡수된다.
- README 「AI 에이전트로 설치」의 4~6단계(대시보드 옵션 질문·선택 반영·최종 보고의 전환 방법)는 **삭제**하고
  "진행 기록(대시보드)은 허브 기능이다 — `hub/README.md`" 1줄로 바꾼다(T23-4 재조준).
- 스위치 저장 위치(`.claude/settings.local.json` `dashboard_enabled`)와 페일 방향(파일·필드 없음 = 켜짐)은 그대로 —
  허브 `read_dashboard_enabled` 와 기록기가 **같은 함수**를 쓰게 되어(HD14) RL10 의 합의가 코드로 강제된다.

---

## 13. 동시 작업과의 순서 · 가드 ID 할당 — Q7

> **(2026-09-24 재확인, 기준 3d76b81)** 아래 13.1 은 M1 설계 시점(2026-09-23)의 기록이다 — 거기 적힌 두 워크트리는 그 뒤 `main` 에
> 들어왔다(세션 모달 M1 = `3d76b81`, 한도 초과 = `be20be4`, README 예시 = `ff02bc8`). **M2 의 동시 작업 판단은 13.2, M2 가드 ID·래칫은
> 13.3 이 정본이다.**

### 13.1 M1 시점 기록 (2026-09-23)

워크트리 `hub-session-modal`(기준 `19bca3a`, PRP `hub-session-modal-and-partial-update.md`, M1(PU) 진행 중):
미커밋 `hub/bin/hub_template.html`(+231/−54) · `tests/run.sh`(+105, T25-107 개정 + **T25-228~231 신설**) ·
`tests/mutations.tsv`(T25-107 승급 + T25-228~231 행, 머리 주석 291→290) · `hub/README.md`(+5, 327·343행 부근) ·
신규 `tests/hub/test_hub_template_dom.py`. 그 PRP 는 "허브 파이썬과 스냅샷 계약은 한 줄도 바꾸지 않는다".
main 은 `9f23534` 에서 **T25-228 을 harness-update 검사로 이미 사용** — 워크트리의 T25-228 과 번호가 겹친다(그쪽이
리베이스 때 재번호해야 한다).

| 이 설계가 만지는 것 | 워크트리가 만지는 것 | 충돌 |
|------|------|------|
| `hub/bin/hub_template.html` **0변경**(주석 정정까지 M3 이후) | +231/−54 | **없음** |
| `hub/bin/*.py`(M2) | 0 | 없음 |
| `tests/run.sh` T22·T23·T24 주석·T26·T27 주석·T33·T34·T35-0·**신설 T40**·레지스트리 1줄 | T25 만 | 없음 |
| `tests/run.sh` T25: 변수 선언(≈3926행) · T25-6·10·104·124·136·145·149·158(M1) · T25-222 의 `init-values` 5줄(M2, ≈8563행 — 2026-09-24 재확인, 기준 3d76b81: 지금 8659~8663행, 13.2) | T25-107(M1) · T25-81·105·108·127·163·218·**223**(M2) · 함수 끝에 228~239 추가 | **낮음** — 겹치는 hunk 없음. T25-222(≈8563)와 T25-223(≈8590) 은 25줄 떨어져 3줄 문맥 병합이 된다(2026-09-24 재확인, 기준 3d76b81: 지금 51줄, 13.2-(c-1)). 함수 끝 추가분은 T25-227 이후이고 내 M1 은 T25-227 을 안 만진다 |
| `tests/mutations.tsv`: T22/T23/T25-145/T33/T34 행 재조준·삭제, T40 행 추가(파일 끝), 머리 주석 계수(면제행 수가 변하면) | T25 블록 뒤 행 추가, 머리 주석 291→290 | **머리 주석 1줄 — 높음.** 면제행 수 변화가 있으면(T23-4 삭제 등) 리베이스 뒤 실측으로 다시 센다. 그 외 행은 다른 블록 |
| `hub/README.md`: 설치·제거·파일 배치·상세 패널·프라이버시·티어 표·알려진 한계 + 신설 절 | 327·343행 부근(+5) | **낮음~중간** — 근접 hunk 가능(카드 순서·화면 배치 절). 리베이스 1회 |
| 상시 컨텍스트(`rules/`·`CLAUDE.md`) | 0 | 없음 |

**두 번째 동시 작업(승인 시점 추가 확인, 2026-09-23).** 워크트리 `hub-rate-limit-interruption`(브랜치
`worktree-hub-rate-limit-interruption`, 기준 `9f23534`, 커밋 0): 미커밋 `hub/README.md` +13(맨 위 샘플 이미지 아래
「카드 한 장에 보이는 멀티 에이전트 작업」 절 — 문구에 "`/dashboard` 기록에서 온 작업 제목"이 있다) · 신규
`docs/images/hub-card-multi-agent-dark.png`. 설계 진행 중(그쪽 `docs/prps/hub-rate-limit-interruption.md`) —
한도 초과로 끊긴 세션을 `StopFailure` 훅 또는 transcript 꼬리의 `error: "rate_limit"` 로 알아채 표시하는 작업이라
`hub_settings`·`hub_hook`·`hub_transcript`·`hub_session`·`hub_model`·`hub_template.html` 쪽이 후보다.

| 이 설계 | 그쪽(예상 포함) | 충돌 |
|------|------|------|
| M1 `hub/README.md` 의 설치·제거·파일 배치·상세 패널 절 + 신설 「진행 기록」 절 | 맨 위 절 +13 | **낮음** — 다른 hunk. 단 그쪽 문구의 `/dashboard` 는 M1 뒤 낡은 이름이 된다 — **나중에 병합하는 쪽이 "진행 기록"으로 고친다** |
| M1 `commands/hub.md` `argument-hint`·신설 절 | `StopFailure` 훅을 더하면 훅 설명 절 | 낮음 — `argument-hint` 1줄이 겹칠 수 있다 |
| `tests/run.sh`·`tests/mutations.tsv` 머리 주석 계수 | 그쪽도 가드를 더할 것(아마 T25) | 머리 주석 1줄 **높음**(§13 표와 같은 종류). 신설 그룹 번호 T40 을 그쪽도 쓰면 레지스트리 줄에서 드러난다 — 나중에 병합하는 쪽이 재번호 |
| M2 `hub_collect`·`hub_project`·`hub_server`·`hub_parse`·`hub_model`(docstring 1곳) | `hub_session`·`hub_transcript`·`hub_model`(필드 추가 가능)·수집 경로 | 미정이었다 → **확인됨 (2026-09-24 재확인, 기준 3d76b81)** — 그 작업은 `be20be4` 로 들어왔고 M2 대상 심볼을 새로 쓰지 않는다(§7.2 머리). 그 뒤의 후속(세션 B)은 13.2 |

**순서.**(M1 시점 판단 — M2 의 순서 권고는 13.2 끝) M1·M2 모두 워크트리 병합 **전**에 진행할 수 있다. 병합 **후**로 미루는 것: (a) `hub_template.html`
주석 2곳(`.claude/dashboard.html` 서술) 정정, (b) M3 카드 배지(별도 PRP·목업). 워크트리의 M2(SC)가 먼저
들어오면 내 M2 의 T25-222 hunk 는 리베이스 1회로 붙는다.

**가드 ID(HD12).** 신규는 **T40-1~T40-15**(신설 그룹 `test_hub_dashboard_channel`, 레지스트리 `"T40:test_hub_dashboard_channel"` — 2026-09-24 재확인, 기준 3d76b81: 그중 T40-12 는 별도 PRP 몫, 13.3)
과 T22-176+·T23-12+·T33-3+·T34-3+. **구현 개정(M1 검수 1·2회차, 2026-09-24)**: M1 이 T40-1~T40-11 과 T40-7a·7b 를
쓴다(검수로 T40-9 수정된 규칙 파일 보호 · T40-10 규칙 채널 심링크 거부(설치) · T40-11 제거 전 심링크 사전 조건 ·
T40-7a/7b harness-update 비교 순서·3분기가 늘었다) — 그래서 M2 의 신규 가드는 (옛 번호 T40-12~T40-14 →) **T40-13~T40-15** 다(2026-09-24 재확인, 기준 3d76b81 — T40-12 는 별도 PRP
`hub-uninstall-symlink-precondition.md` 의 N7·N8 이 먼저 쓴다, 13.3·§14.2 8번). T22 는 T22-176(기록기의 `hub_atomic_write`
임포트)을 M1 이 썼으므로 다음 신규는 T22-177 부터다. **T25 에는 신규 ID 를 만들지 않는다.** 기존 T25 ID 의 본문 수정만 한다.
래칫 상수: `SOURCE_GUARD_ID_FLOOR=462` 는 손대지 않는다(삭제 ≤4, 신규 ≥14 → 순증 — M1 시점 서술. 지금 바닥은 466, M2 재계산은 13.3). `LEDGER_MUTATION_ROW_FLOOR`·
`LEDGER_EXEMPT_ROW_RATCHET` 무변경. `NOTE_FAILURE_ID_LESS_RATCHET=110` — T34 의 "G2:" 접두 8건을 `T34-n:` 으로
바꾸면 실측이 내려가므로 그만큼 **내린다**(내리는 것은 자유). `LINE_CITATION_RATCHET_SUITE=5` 포화 — 이 설계가
`tests/run.sh` 에 새로 적는 주석은 `파일명:줄번호` 형태를 쓰지 않는다.

### 13.2 M2 와 동시 작업의 겹침 (2026-09-24 재확인, 기준 3d76b81)

확인된 동시 작업은 셋이다. 두 워크트리의 내용은 메인 세션이 전달한 사실이고, 이 회차는 그 워크트리를 읽지 않았다.

- **세션 A**(바쁨) — 워크트리 `hub-session-modal`, 브랜치 `worktree-hub-session-modal`, 기준 `3d76b81`, 전부 미커밋.
  `docs/prps/` 5개(hub-detail-side-panel·hub-panel-empty-state-and-open-card·hub-session-modal-and-partial-update·
  hub-session-tree-and-per-session-dashboards·hub-unified-card-tree-ui, 각 +3~8) · `hub/README.md`(+60 안팎) ·
  `hub/bin/hub_template.html`(559줄 변경) · `tests/hub/test_hub_template_dom.py` · `tests/mutations.tsv`(23줄) · `tests/run.sh`(397줄) ·
  새 `tests/hub/template_dom_harness.py`·`tests/hub/test_hub_template_dom_modal.py`. 건드리는 ID: T25-66·76·81·88·105·108·127·160·163·201·
  218·223 개정, T25-233~240 신설, T37-13. `main` 에 있는 그쪽 PRP(`hub-session-modal-and-partial-update.md` §9.2)가 README 「카드 상세보기」
  절 신설(「카드 순서」와 「프로젝트 상세 패널」 사이)과 「프로젝트 상세 패널」 5곳 개정, 원장 머리 계수 286 → 282 를 예고한다.
- **세션 B**(쉬는 중) — 워크트리 `hub-rate-limit-interruption`, 브랜치 `worktree-hub-event-time-bounds`, 기준 `3d76b81`, 미커밋.
  `hub/bin/hub_session.py` +18/−10(`parse_event_line` 에 `EVENT_TIME_MAX_MS = 4_102_444_800_000` — 주석 "hub_dashboard_render.py.
  _MAX_VALID_TIME_MS 와 같은 값(결합을 피하려 import 하지 않는다)", 모듈 docstring 에 "800줄 상한(T25-100)에 닿았다") ·
  `tests/hub/test_hub_collect.py` +29 · `tests/hub/test_hub_session.py` +63. `main` 의 `hub_session.py` 는 792줄이라 B 가 들어오면 800/800 이다.
- **N7·N8** — 별도 PRP `docs/prps/hub-uninstall-symlink-precondition.md`, M2 보다 먼저 구현(메인 세션 전달). 그 PRP 는 `3d76b81` 에는
  없고, 이 회차 도중 `main` 체크아웃에 **미추적 파일**로 생겼다(상태 「승인 대기」 — 내용이 바뀔 수 있다). 거기 적힌 대로라면 배정분
  T40-12 를 **하위 ID T40-12a~d** 로 쓰고(맨 `T40-12:` 접두는 쓰지 않는다), 원장 T40-11 행 바로 뒤에 변조행 4개를 더하며, T40 블록은
  행동 검사 묶음 끝(T40-11 뒤, 정적 T40-7·8 앞)에 둔다. T40 머리 주석을 "T40-1~T40-12(M2 에서 T40-13~15 …)"로, `test_desc` 를
  "(T40-1~T40-12)"로 먼저 고친다. 원장 머리 주석이 인용하는 수는 바꾸지 않는다(면제행 불변). `hub/install.sh`·T40 그룹·원장 T40 블록에서
  M2 와 만나지만 순차라 텍스트 충돌은 없다.

| # | 겹치는 곳 | M2 | 상대 | 위험 | 대응 |
|---|---|---|---|---|---|
| (a) | `_MAX_VALID_TIME_MS` 의 위치 | 렌더러 → `hub_parse.py` 로 **이름·값 그대로** 옮긴다 | B 의 `hub_session.py` 주석이 "`hub_dashboard_render.py._MAX_VALID_TIME_MS` 와 같은 값"을 인용한다 | **낮음** — 텍스트는 안 겹치고 뜻만 낡는다 | 나중에 병합하는 쪽이 그 주석의 모듈명 한 단어를 `hub_parse.py` 로 고친다(줄 수 불변 — 800/800). B 가 먼저면 M2 구현이 고친다(M2 의 유일한 `hub_session.py` 편집). M2 가 먼저면 B 가 리베이스 때 고친다. 상수를 공개로 올려 B 가 임포트하게 하는 안은 B 의 결정(결합 회피)을 뒤집으므로 쓰지 않는다. ※ B 의 테스트(+63·+29)가 렌더러 상수를 직접 임포트하는지는 확인하지 못했다 — 임포트한다면 M2 뒤 `AttributeError` 다. M2 착수 때 B 가 이미 들어와 있으면 `grep -rn _MAX_VALID_TIME_MS tests/` 로 먼저 본다 |
| (b) | `tests/hub/test_hub_collect.py` | 4클래스 21건 수정·삭제(342·521·607·696행 부근) + 신규 ≈3 | B +29 | **낮음** | M2 신규 케이스는 **기존 클래스 안**에 넣는다 — 파일 끝에 새 클래스를 붙이면 B 가 끝에 붙인 경우와 인접 hunk 가 된다. 두 번째 병합 쪽이 `python3 -B -m unittest tests.hub.test_hub_collect` 로 확인한다 |
| (c-1) | `tests/run.sh` T25-222 ↔ T25-223 | T25-222 ⑨·⑩·머리 주석(8603~8670행) | A 가 T25-223(8710~8782, 특히 8741~8756) 을 고친다 | **낮음** — 40줄 넘게 떨어진 별개 hunk. 원 계획이 적은 "25줄"(`9f23534` 기준)은 지금 51줄 | M2 는 ⑬(8703~8708)을 건드리지 않는다 — 건드리면 T25-223 머리와 2줄 거리로 붙는다 |
| (c-2) | `tests/run.sh` 그 밖의 T25 | 주석 T25-6(4093~4096)·T25-75(5401~5407)·T25-90(5714~5718), 개정 T25-146(6976~6984) | A 의 T25-76(5419~)·T25-88(5673~5686) 등 | **낮음** — 가장 가까운 것이 T25-75 ↔ T25-76(12줄) | — |
| (c-3) | `tests/mutations.tsv` 머리 주석 "아래 286개는"(91행)·연혁 문장(110~111행) | 286 → 284 | A 286 → 282 | **높음** — 같은 줄 | 나중에 병합하는 쪽이 다시 센다(둘 다면 280). 틀리면 사전 점검 T99-6 이 스위트를 멈추고 실측을 알려 준다. 연혁 문장은 두 회차 것을 모두 남긴다 |
| (c-4) | `tests/mutations.tsv` 행 | T34-1/2 행 삭제(702~703) · T22-137(265)·T25-146(398) 승급 · T40-13~15 추가(T40 블록 끝 — N7·N8 의 T40-12a~d 행 뒤, T25-241 앞) | A 의 T25-233~240 추가(T25-232 = 701행 뒤로 예상) · T25-127(378)·T25-160(414) 등 | **중간** — A 가 T34-1 바로 앞에 붙이면 인접 hunk | 둘 다 살린다(A 행 유지 + T34-1/2 삭제). M2 의 새 행은 T40 블록 안에만 둔다 |
| (c-5) | T37-13(원장 변조행 검사) | 0 — 단 M2 의 새·승급 변조행 5개가 그 규칙을 따라야 한다 | A 가 T37-13 을 고친다 | **낮음**(텍스트) · 뜻 결합 | A 가 먼저면 M2 행은 A 의 T37-13 규칙대로 쓴다 |
| (d) | `hub/README.md` 「프로젝트 상세 패널」 | 383~384(괄호) · 389(서빙 키) · 398~402(잠금 — 「텍스트 선택」) · 406~411(PiP·단독 탭) | A 가 같은 절 383·392~394·422·426~435·436~446 을 고치고, 그 바로 앞에 「카드 상세보기」 절(+60)을 넣는다 | **높음** — 383행은 같은 문장, 388~411 은 A 의 hunk 사이 | M2 는 **구(句) 단위**로만 고친다. 445~446행(레거시 칩)은 건드리지 않는다(§7.2.1). 나중에 병합하는 쪽이 손으로 합친다 — A 가 먼저면(권고) M2 가 A 의 새 문장 위에 같은 구 교체를 다시 적용하고, A PRP §9.2 의 "보존해야 할 README 토큰"을 확인한다 |
| (d-2) | `hub/README.md` 그 밖 | 「프라이버시」(205~206)·실행 목록 경계(286~292)·「진행 기록」(456~537)·「알려진 한계」(545~555)·「티어 한계」(662) | A 는 이 절들을 고치지 않는다 · 37행은 사용자가 나중에 일괄 정리 | **없음~낮음** | 37행은 건드리지 않는다(§7.2.1) |
| (e) | `hub/bin/hub_session.py` 주석 부패 | **미룬다**(아래) — (a) 의 조건부 한 줄만 | B 가 편집 중, B 뒤 800/800 | **없음**(M2 가 손대지 않으므로) | — |
| (f) | `hub/bin/hub_template.html`·`tests/hub/test_hub_template_dom*.py`·`template_dom_harness.py`·`tests/hub/test_hub_session.py`·A 의 PRP 5개 | 0 | A·B | **없음** | — |
| (g) | T40 그룹(머리 주석·`test_desc`·본문)·원장 T40 블록·`hub/install.sh` | T40-13~15 · 머리 주석 · `test_desc` | N7·N8 이 T40-12a~d(변조행 4)와 머리 주석·`test_desc` 를 먼저 고친다 | **없음**(순차) — 병렬로 가면 **높음** | N7·N8 이 병합된 뒤 착수한다 |

**(e) `hub_session.py` 주석을 미루는 근거.** 대상은 558·569·579행(`commands/dashboard.md` 인용 — 579행이 드는 "30분 이내 갱신이면
RECENT" 규칙은 1단계 `fd79fa7` 에서 이미 사라져 지금 어느 문서에도 없다)·611행(`/dashboard init`), 그리고 M2 가 낡게 하는
`previous_task_boundary_ms` 의 (c) 갈래 서술("사이드카가 없어") 한 곳이다. ① HD6·HD8 이 `hub_session.py` 무변경을 약속했고, 그 약속이
세션 B 와의 충돌을 병합 순서와 무관하게 0 으로 만든다. ② B 가 들어오면 800/800 이다 — 출처 인용을 `hub/README.md` 「진행 기록」 표로 바꾸는
한국어 문장 교체는 줄이 늘기 쉽고, 한 줄만 늘어도 T25-100 이 스위트를 깨뜨린다. 주석 정리에 줄 수 제약을 거는 값이 낮다. ③ 코드는 맞다
— 낡은 것은 출처 인용뿐이고, 네 곳은 M1 부터 낡아 있었다(M2 가 만든 것이 아니다). ④ RI13(`docs/prps/hub-rate-limit-interruption.md`)이
이 파일의 다음 확장 때 분리를 먼저 검토하라고 걸어 두었다 — 그 회차가 이 docstring 들을 어차피 다시 쓴다. 그래서 **다음 `hub_session.py`
편집 회차의 할 일**로 §16 R12 에 적는다. 그때 쓸 문구: 558·569행 → "hub/README.md 「진행 기록」 데이터 모델 표의 `pass` = 전부 완료(100%)" ·
579행 → 세 번째 공유처(옛 RECENT 규칙) 삭제 · 611행 → "기록기 `init`" · (c) 갈래 → "작업 시작 시각을 모르면(`tier1` 이 없거나 그 값이
없으면)".

**병합 순서 권고**(결정은 사용자 몫이다). **N7·N8 → 세션 A(세션 모달 M2) → 이 문서의 M2**, 세션 B 는 M2 앞뒤 어디든 된다. N7·N8 은 이
M2 보다 먼저 가기로 정해져 있고, T40 번호가 그 순서를 전제한다. 세션 A 는 README 「프로젝트 상세 패널」을 문단 단위로 다시 쓰고 원장 T25
블록을 크게 바꾸는 쪽이라, A 를 먼저 들이고 M2 가 구 단위 교체와 계수 재계산을 그 위에 다시 얹는 편이 반대(A 가 M2 의 구 교체 위에 문단
재작성을 다시 얹는 것)보다 손이 덜 간다. 세션 B 는 M2 와 텍스트가 겹치는 곳이 없다 — B 가 먼저면 M2 가 B 주석 한 줄을 고치고((a)),
나중이면 B 가 리베이스 때 고친다. 어느 순서든 두 번째로 들어가는 쪽은 `bash tests/run.sh` 전체를 다시 돌린다.

### 13.3 가드 ID 할당 · 래칫 — M2 (2026-09-24 재확인, 기준 3d76b81)

| 항목 | M2 의 값 | 실측 근거 |
|---|---|---|
| T40 | M1 = T40-1~11·T40-7a·7b(13 ID) · **T40-12 = 별도 PRP(N7·N8) — 하위 ID T40-12a~d 4개** · **M2 = T40-13·T40-14·T40-15**(§14.2 8번). T40 머리 주석의 "M2 에서 T40-12~14 가 이어받는다"(12850행)와 `test_desc` 의 "T40-1~T40-11"(12861행)은 구현 때 고칠 대상이다(§14.2 9번) | `main` 소스의 T40 ID 13종. `T40-12` 는 그 머리 주석에 1회뿐 |
| T22 | 최대 T22-176. **T22-177 이상은 비어 있다**(소스·원장 0 — 이 문서의 인용 1회뿐). M2 는 새 T22 ID 를 쓰지 않는다(T22-137 은 같은 ID 로 개정) | `grep -oE 'T22-[0-9]+[a-z]?'` |
| T34 | T34-1·T34-2 삭제(번호 재사용 금지) · T34-3~6 개정 | — |
| T25 | 신규 0(HD12). `main` 은 T25-228~232·T25-241~244 를 쓰고, 세션 A 가 T25-233~240 을 쓴다 | `3d76b81` 소스·원장 |
| `SOURCE_GUARD_ID_FLOOR` | **466 그대로.** 소스 서브체크 ID 실측 489 → N7·N8 뒤 493(+T40-12a~d) → M2 뒤 494(−T34-1·T34-2, +3). M2 몫은 +1 이다 | `collect_guard_ids` 원본 함수를 떼어 실행: 481(`33e1ce9`)·485(`be20be4`)·489(`3d76b81`). 참고 — `be20be4` 는 462 → 466 을 "실측치"라 적었지만 그 시점 실측은 485 다(바닥이 실측 이하이면 되므로 래칫 위반은 아니다. M2 가 고칠 일도 아니다) |
| `NOTE_FAILURE_ID_LESS_RATCHET` | **103 그대로 — 실측 103 으로 포화.** M2 는 ID 없는 실패 호출을 한 줄도 더할 수 없다. T34-1/2 삭제는 ID 있는 호출이라 분모와 분자가 같이 준다 | 실패 호출 1215 · ID 보유 1112 |
| `LEDGER_EXEMPT_ROW_RATCHET`(382)·`LEDGER_MUTATION_ROW_FLOOR`(100) | 무변경. M2 몫은 행 −2 +3 · 변조 −2 +3 +2 · 면제 −2. `3d76b81` 기준 496 → 497행·변조 174 → 177·면제 322 → 320, N7·N8(변조 +4)이 먼저면 500 → 501행·178 → 181·322 → 320 | `3d76b81` 원장 |
| 원장 머리 주석 "아래 N개는" | **286 → 284**(T22-137·T25-146 승급). 세션 A 가 같은 줄을 286 → 282 로 고치므로 둘 다 들어가면 **280** — 사전 점검 T99-6 이 실측과 대조한다 | 공통 사유 면제행 실측 286 |
| `LINE_CITATION_RATCHET_SUITE` | 5 로 포화 — 이 문서의 `tests/run.sh` 주석 개정안은 `파일명:줄번호` 형태를 쓰지 않는다 | — |

---

## 14. 마일스톤 — Q8 (각각 단독 배포 가능)

### 14.1 M1 — 이전·게이팅 (허브 파이썬 0변경)

**TDD 순서** (각 단계: RED 확인 → 구현 → GREEN → `bash tests/run.sh --only <그룹>`):
1. `tests/hub/test_hub_dashboard_log.py`·`test_hub_dashboard_render.py` 를 `tests/commands/` 에서 옮기고 임포트
   경로를 `hub/bin` 으로 → **RED**(모듈 없음). `hub_dashboard_log.py`·`hub_dashboard_render.py`·템플릿 이동 →
   GREEN. 기록기의 HD14 재사용(원자적 쓰기·켜짐 판정·경로 상수) 케이스 3건 추가 → GREEN.
2. T40 신설(RED): T40-1 규칙 배포(샌드박스 `HOME` 으로 `hub/install.sh` 실행 → `$HOME/.claude/rules/hub/dashboard-recording.md`
   존재 + `bin/` 파일 수 = `HUB_FILE_COUNT`) · T40-2 `--uninstall` 이 배포한 규칙만 지우고 같은 디렉터리의 미끼
   파일은 남긴다 · T40-3 uninstall 본문에서 `uninstall-statusline` < 규칙 제거 < `rm -rf "$TARGET_BIN_DIR"` ·
   T40-4 `HUB_RULE_FILE_COUNT` = `hub/rules` 실제 수 + hub/README 「파일 배치」 규칙 경로 고지 · T40-5 규칙 파일
   바이트 = `HUB_DASHBOARD_RULE_BUDGET_BYTES`(정확 일치 래칫, 옛 T22-163 승계) · T40-6 규칙 파일에 `paths:` 없음 +
   `dashboard_enabled`·`.claude/settings.local.json` 리터럴 · T40-7 harness-update Phase 4b 에 `hub/rules` 비교 줄이
   있고 `server-stop --json` 보다 앞 · T40-8 `rules/**/*.md` 에 `hub_dashboard_log.py` 0건 + 레포에
   `commands/dashboard*` 부재 → `hub/install.sh`·규칙 파일·harness-update.md·`role-separation.md` 편집 → GREEN.
3. 삭제·툼스톤: `commands/dashboard*` 삭제, `removals.txt` 4줄, `COMMANDS_FILE_COUNT=8` → T17·T22-138·T35-3·T27·
   T39-2(CLAUDE.md 8개) GREEN. **T35-0 개정**: `commands/*.py` 가 없어 `py_compile commands/*.py` 가 실패하므로
   `py_compile.compile(<임시 .py>, cfile="commands/__pycache__/<이름>.cpython-XY.pyc")` 로 실물 바이트코드를 그
   자리에 만든다(빈 파일 흉내 금지 원칙 유지) — 가드가 지키는 `remove_pycache_from_target_directory` 경로는 그대로다.
4. T22 재조준: 4개 경로 변수 → `$REPO_ROOT/hub/bin/…`, `dashboard_command_file` → `$REPO_ROOT/hub/README.md`
   (「진행 기록」 절이 표·경로 규칙·어휘를 담는다). T22-1 → "샌드박스 설치 결과에 `commands/dashboard*` 가 없다"
   (역방향). T22-136(문서가 템플릿 파일명 언급)·T22-137(init 어휘)·T22-159(「대시보드 경로 규칙」 절이 「헬퍼
   스크립트」 절보다 앞)·T22-161(코드 블록의 레거시 리터럴 0)·T22-135 는 hub/README 절 구조로 만족시킨다.
   T22-163 삭제(→ T40-5). 그룹 설명 문구 갱신.
5. T23 재조준: `dashboard_command_file` → `commands/hub.md`. T23-4 → README 의 허브 안내 1줄. T23-5 →
   `## \`/hub dashboard on|off\``. T23-6 → `head -4` 에 `dashboard on|dashboard off`. T23-7 문서 목록 →
   규칙 파일·hub.md·hub/README(README 는 제외 — `dashboard_enabled` 언급이 사라진다). T23-8~10 → hub.md.
6. T33: G1 대상 `commands/dashboard.md` → `hub/rules/dashboard-recording.md`. T33-1 대상 목록에서 dashboard.md →
   규칙 파일(+hub/README). T33-2 상수 `DASHBOARD_LAUNCHER_CANONICAL_FORM` → `python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" <서브커맨드> …`,
   대상 = 규칙 파일·hub/README 각 1회. 원장 T33-1(대상 규칙 파일)·T33-2(대상 hub/README) 재조준.
7. T34: 대상 `hub/README.md`·`hub/bin/hub_dashboard_log.py`·`hub_dashboard_render.py`. 표 절 앵커 `## 헬퍼 스크립트` →
   hub/README 의 절 제목. "G2:" 8건을 `T34-3~T34-10` 로 ID 승격. T34-1/2 유지(M1 은 render 가 있다).
8. T25(M1 분): 변수 줄 재조준(`dashboard_command_file`→hub/README, `dashboard_template_file`→hub/bin 템플릿),
   T25-6·T25-10(순수 목록에 `hub_dashboard_render.py` 추가)·T25-124(dashboard.md 줄 → hub/README)·T25-136·T25-145
   (원장 대상 경로)·T25-104/T25-149(26→29)·T25-158(hub/README 에 `.claude/dashboards` 리터럴).
9. T26: 상수 → 편집 후 실측(≈54,068B), README 선언 2곳. T27 주석 2곳 정정. T24 주석 정정.
10. 문서: README·CLAUDE.md·hub.md·harness-update.md·hub/README. 검증 5종 전부(프로젝트 CLAUDE.md §4, `tests/commands`
    줄은 빠진 새 목록으로).

**폭발 반경(M1)**: 삭제 4 · 신설 5(`hub_dashboard_log.py`·`hub_dashboard_render.py`·`hub_dashboard_template.html`·
`hub/rules/dashboard-recording.md`·`tests/hub/*` 2 이동) · 수정 14(`install.sh`·`removals.txt`·`hub/install.sh`·
`role-separation.md`·`CLAUDE.md`·`README.md`·`hub.md`·`harness-update.md`·`hub/README.md`·`tests/run.sh`·`mutations.tsv`·
계약 테스트·`.gitignore` 0). 영향받는 기존 검사: T22 99 ID(경로 재조준으로 전부 재실행, 본문 수정 ≈9: 1·134·135·
136·137·159·161·163 삭제·138) · T23 11 · T25 8 · T33 3 · T34 3(+8 승격) · T35 1 · T26 3 · T27 주석 · T39-2 · 유닛
125건 이동 + 3건 신규. 새 가드: **T40-1~8(8건)** + 원장 변조행 ≈8(T40 각 1) + 재조준 ≈16.
**구현 실측(M1 검수 1·2회차 반영 뒤)**: 신규 가드 T40-1~11 · T40-7a/7b · T22-176 · T34-3~6(`G2:` 접두 보고를 ID 로
승격 — 설계 추정 「8건 → T34-3~10」과 달리 서로 다른 보고 4종이라 4개 ID), 면제행 승급 T22-1 · T25-75 ·
T22-158a/b · T23-4a/b, `NOTE_FAILURE_ID_LESS_RATCHET` 110 → 103(실측).

**승인 항목(M1)**: §17-1~4.

### 14.2 M2 — 직접 읽기 (허브 안)

**(2026-09-24 재확인, 기준 3d76b81)** 이 절은 `3d76b81` 의 실제 테스트·가드로 다시 셌다. 원 계획과 달라진 점은 셋이다. ① T40 신규 번호 T40-12~14 →
**T40-13~15**(§13.3). ② 원 계획이 놓친 결합 ★5건 — T22-137(폐기 어휘가 README 에 **있어야** 통과한다) · T25-146(「알려진 한계」 구세대
조항과, 그 항목에만 있는 「텍스트 선택」 토큰) · T25-90(README 「구세대」 토큰) · `HelperReusesHubModulesTest`(`init` 한 번에 원자적 쓰기 3회
이상) · 렌더러·기록기 테스트 21건의 `resolve_dashboard_paths`·`hub_parse.parse_dashboard_html` 의존. ③ 유닛 건수 "≈70" → 손대는 기존 ≈138 +
신규 ≈27(아래 표). 새 커밋이 만든 결합은 없다(§7.2 머리).

**TDD 순서** (각 단계: RED 확인 → 구현 → GREEN → 해당 모듈만 `python3 -B -m unittest tests.hub.<모듈>` 또는 `bash tests/run.sh --only <그룹>`):
1. `tests/hub/test_hub_parse.py`(22건 — **전부** HTML 파서 대상이다. 원 계획의 "14건"은 오기): 22건과 픽스처 `tests/hub/fixtures/*.html`
   5개를 지운다 → JSONL 스냅샷 케이스 ≈16건(RED): 표준 전체 4/4 · FAIL 회귀(구현 active·검수 wait·detail = 최근 요약) · 축약 1/2 · 앞 단계
   생략(`impl` 만) · 비표준 목록 `step` · 이벤트 0건 = 첫 단계 active · `percent` 반올림(2/3→67) · `title` 원문(`&`·`<` 이스케이프 안 됨) ·
   `task_started_at_ms == init.time_ms` · init 없음 → None · 깨진 줄 fail-open · `updated_text` = 마지막 이벤트(`format_event_updated_label`) · 상수
   필드(`subtitle ""`·`matrix_done None`·`impl 0/0`) → `hub_parse` 재작성 → GREEN. `test_hub_dashboard_render.py` 의 `ParseEventLinesTest`(9)·
   `DerivePhaseStatesTest`(10) 19건을 이 파일로 **옮긴다**(검증 로직 불변, 참조만 `hub_parse.*`).
2. `test_hub_collect.py`(100건 — `be20be4` 의 W1 1건 추가, 대시보드 무관): 영향 4클래스 21건 — `ReadSessionDashboardSnapshotsTest`(8)·
   `Tier1SourceSelectionTest`(4)·`CollectTier1SnapshotsTest`(3)·`CollectSnapshotWorktreeTier1Test`(6). `.jsonl` 만 열고 `.html`·사이드카를
   무시(셋을 다 둔 디렉터리로 검증) · `session_id`·`source_path`·`file_mtime_ms` 보강 · init 없는 jsonl → 경고 1건 · 수집이
   `task_started_at_ms` 를 덮어쓰지 않는다 · 레거시 경쟁 케이스 ≈6 삭제 · `_read_tier1_for_root` 가 멤버 전부를 읽는 계약(M1 검수 M1 케이스)
   유지. **신규 케이스는 기존 클래스 안에** 넣는다(§13.2-(b)).
3. `test_hub_project.py`(89건 — `be20be4` 의 P1·P2 4건 추가, 무관): `SessionTokenFromInitValuesFileNameTest`(4)·`SessionTokenTest`(1) 삭제 ·
   `SessionIdFromDashboardFileNameTest`(6)·`SessionDashboardRelativePathTest`(1)·`TierOneFilePathAndDashboardFileKeyTest`(4) 를 `.jsonl` 로(레거시
   갈래 1건 삭제). `test_hub_model.py`: `BuildDashboardRegistryTest` 7건 픽스처(값이 `.jsonl` 경로). `test_hub_session.py`(150건): **무변경** —
   Tier1Snapshot 픽스처 5건 통과 확인만(`be20be4` 가 더한 22건은 대시보드 무관). `test_hub_template_dom.py`(`3d76b81` 신규 10건): 무관 —
   대시보드 HTML 을 만들지 않는다.
4. `test_hub_server.py`(37건): 경로 패턴·라우팅·리프레셔·신선도 게이트의 대시보드 케이스 ≈12건 수정 + `_serve_project_dashboard` 신규 ≈5건 —
   등록된 키 + 실제 jsonl + 템플릿 픽스처 → 200·본문에 `dz-title` 원문·`nosniff` · 파일 부재 404 · init 없음 404 · 템플릿 부재 404 +
   server.log 한 줄 · 모르는 키 404.
5. `test_hub_dashboard_contract.py`(6건) 재작성(≈4): 기록기(`cmd_init`/`cmd_log`, 임시 cwd)가 쓴 파일을
   `hub_collect.read_session_dashboard_snapshots` 로 읽어 `Tier1Snapshot` 필드를 대조한다(생산자↔소비자, 같은 채널). HTML 정규식 계약
   (`_STEP_LINE_PATTERN` 3건·`parse_dashboard_html` 3건)은 지운다.
6. `test_hub_dashboard_render.py`(61건): 19건 이동(1번) · ★`ResolveDashboardPathsTest` 5건 삭제 · ★`RenderFromEventsHubParseContractTest` 9건
   재작성(→≈5) — `hub_parse.parse_dashboard_html` 이 사라지므로, 같은 이벤트로 만든 `render_from_events` 출력의 제목·진행률·단계 줄이
   `snapshot_from_events` 값과 일치하는지로 바꾼다(두 소비자의 일관성) · `BuildPublishedValuesTest` 5건의 `parse_event_lines` 참조를
   `hub_parse` 로 → 잔여 ≈33.
7. `test_hub_dashboard_log.py`(74건 — 앞 54건은 렌더러 순수 함수 검사다): ★`ResolveDashboardPathsTest` 7건 삭제 · `ParseEventLinesTest` 5건과
   `BuildPublishedValuesTest` 의 `_format_event_updated_label` 1건을 `hub_parse` 로 재조준 · `ResolvePathsRuntimeContractTest` 첫 케이스(사이드카
   경로 단언) 수정 · ★`HelperReusesHubModulesTest` 의 원자적 쓰기 위임 케이스 — `init` 한 번에 `call_count >= 3`(jsonl·사이드카·html) →
   `>= 1`(jsonl 만) · `HelperEndToEndSmokeTest` 재작성(`render` 없음, `.html`·사이드카 미생성, JSONL 3줄) · `_HelperIOTestCase` docstring 의
   `TEMPLATE_PATH` 서술과 경로 탈출 케이스 docstring 의 옛 `resolve_dashboard_paths` 언급 정리 · 신규 ≈3(`init` 출력이 정확히 `OK` · `.html`·
   사이드카 미생성 · `render` 는 알 수 없는 서브커맨드 → stderr + exit 2). 리텐션 3패턴 케이스는 그대로. 두 파일에 겹쳐 있는 렌더러 순수
   테스트의 중복 정리는 범위 밖이다(기존 중복 — 손대지 않는다).
8. T40-13~15(RED → GREEN, T40-12 는 별도 PRP 몫 — §13.3). T40 머리의 순서 규칙(정적 검사 → 행동 검사, 검수 1회차 F6)에 따라 **첫 정적 검사
   구역**(지금 순서 T40-3·4·6·5 → 행동 T40-1·2·9·10·11 → 정적 T40-7·7a·7b·8 의 T40-5 뒤, T40-1 앞)에 둔다. 끝(T40-8 뒤)에 두어도 물림 간섭은
   없다 — M2 의 변조는 `hub/bin` 파이썬 내용만 바꿔 설치·제거 행동을 바꾸지 않는다. 앵커는 `3d76b81` 코드로 정밀화했다.
   - **T40-13** 기록기·수집이 HTML 을 만들거나 읽지 않는다 — `hub_dashboard_log.py` 에 `hub_dashboard_render` 임포트 0 · `html_path` 0 ·
     `read_session_dashboard_snapshots` 본문이 `parse_dashboard_jsonl(` 을 부르고 `parse_dashboard_html` 0 · `hub_project.py` 의
     `SESSION_DASHBOARD_FILE_NAME_PATTERN` 선언이 `\.jsonl\Z` 로 끝난다(원 계획의 "본문에 `.jsonl`"은 그 리터럴이 수집 함수 본문에 없어
     성립하지 않는다).
   - **T40-14** 서버가 요청 때 렌더한다 — `_serve_project_dashboard` 본문에 `render_from_events(`·`nosniff` · `hub_parse.py` 에
     `_STEP_LINE_PATTERN`·`parse_dashboard_html` 0.
   - **T40-15** 작업 시작 시각의 출처는 init 줄이다 — `snapshot_from_events` 본문에 `task_started_at_ms=`(원 계획의 `parse_dashboard_jsonl` 은
     한 줄 합성이라 그 대입이 없다) · `read_session_dashboard_snapshots` 본문에 `task_started_at_ms=` 0(수집이 덮어쓰지 않는다). 원 계획의
     "`hub_project.py` 에 `init-values` 0"은 T25-222 ⑨ 역방향과 겹쳐 T25-222 로 모은다(9번).

   각 1 변조행(원장 T40 블록 끝 — N7·N8 의 T40-12a~d 행 뒤, T25-241 앞). 렌더러 `resolve_dashboard_paths` 사본 삭제는 6번과 같은 커밋.
9. 기존 가드 개정(`tests/run.sh` — 새 주석에 `파일명:줄번호` 형태 인용을 만들지 않는다, T39-5 포화):
   - **T25-222**(변조행, 8601~8708행): ⑨(8659~8663) 정 → 역 — "`hub_project.py`·`hub_collect.py`·`hub_parse.py`·`hub_dashboard_render.py` 에 `init-values` 0
     (HD8)" — 넷 다 M2 재작성으로 그 리터럴을 잃는다(`hub_parse.py` 는 `task_started_at_ms` 필드 주석 55~59행). 기록기는 리텐션
     패턴으로 `*.init-values.json` 을 계속 가지므로 대상에서 빼고, README 쪽 짝 검사는 지운다(README 는 그 파일을 구세대 산출물로 계속
     언급한다) · ⑩ 실패 문구의 "사이드카 mtime" → "기록 파일 밖의 디렉터리 조회" · 머리 주석 ①~⑬ 목록의 ⑨ 서술과 "(사이드카 mtime)으로
     바뀐다" · 8642행 문구 "사이드카 부재 갈래" → "작업 시작 미상 갈래". **⑬(8703~8708)은 건드리지 않는다**(§13.2-(c-1)). 원장 행은 그대로
     (대상이 `hub_session.py` 의 RL10 갈래다).
   - **T34**(변조행 T34-1~6): T34-3·T34-4 루프 목록에서 `render` 제거(5 → 4) · T34-5 기대 분기 수 5 → 4(문구 포함) · T34-6 어휘 12 → 10
     (`NOTEMPLATE`·`ANCHOR-FAIL` 제거) · T34-1/2 블록과 원장 T34-1/2 행 삭제 · 그룹 머리 주석(10278~10290행 — "5종"·`render`·`ANCHOR-FAIL`
     행 대응 한계 문단) 갱신 · 원장 T34-3("5종")·T34-6("12종") 설명 열 갱신.
   - ★**T22-137**(면제행 → **변조행 승급**): 정 `OK`·`MKDIR-FAILED`(init 이 여전히 낼 수 있는 어휘) + 역 `NOTEMPLATE`·`ANCHOR-FAIL` 이 README
     에 0건(HD15). 원 계획은 이 검사를 빠뜨렸다 — 그대로 두면 M2 의 README 표 개정이 T22-137 을 깨뜨린다. 정·역을 T22-137a/b 로 나누는 것
     (T22-158a/b 선례)은 구현·검수 판단에 맡긴다 — 나누면 변조행이 1개, 소스 ID 가 1개 더 는다.
   - ★**T25-146**(면제행 → **변조행 승급**): 둘째 서브체크("알려진 한계"에 `잠금 CSS/JS 도 없어`)를 지운다 — 그 항목이 §5.3 으로 사라진다.
     첫 서브체크(`우클릭`·`텍스트 선택`)는 둔다 — 「텍스트 선택」은 지금 지울 항목(555행)에만 있으므로 README 상세 패널 잠금 문장에 옮겨
     담는다(§7.2.1).
   - ★**T25-90**(면제행, **주석만** — 승급 없음. T25-92 선례: 실행 줄이 그대로면 래칫 미발동): 토큰 `구세대` 는 「대시보드 경로 규칙」의
     리텐션 문장("구세대 산출물")이 계속 담는다. 주석의 "구세대 대시보드 자연 치유" → "구세대 산출물 처리(읽지 않음·리텐션)". 대안은
     §16 R13.
   - 주석만(실행 줄 불변 → 승급 없음): T22-139("ANCHOR-FAIL 상시화 방지" → "서버 렌더 404 상시화 방지") · T22-171("JSONL·사이드카·HTML·
     settings.local.json" → "JSONL·settings.local.json" — 호출이 5회라 `>= 2` 는 그대로 성립, 원장 설명 열도 갱신) · T25-6("파서 계약은
     test_hub_dashboard_contract.py 가 고정한다" → 템플릿 자체 폴링의 id 계약) · T25-75(예외 근거 "M1, HD4 — 허브 파이썬 0변경" → M2 부터 서버가
     렌더러를 부른다. 검사 자체는 `hub_parse`·`hub_server` 가 `data-owner-token` 을 갖지 않으므로 성립).
   - 그대로 성립(확인): T25-222 ③(`task_started_at_ms: int | None = None` — 필드·기본값 유지, HD6) · T25-6 본문(`id="dz-step-%d"` 는
     렌더러에 남는다) · T22-161 · T22-136 · T22-159 · T22-160 · T25-10(`hub_parse` 는
     `json`·`datetime` 만 더한다) · T25-122 · T25-113·T25-157(역검사 — 상수가 사라져도 참) · T25-137 · T25-142 · T25-223 · T33-2 · T23-7·
     T23-10 · T24(건수 바닥 없음).
   - T40 머리 주석(12847~12852행)과 `test_desc` 를 최종 상태 "T40-1~T40-15 — T40-12a~d 는 hub-uninstall-symlink-precondition(N7·N8),
     T40-13~15 는 dashboard-into-hub M2"로 고친다. N7·N8 이 먼저 이 두 줄을 "T40-1~T40-12(M2 에서 T40-13~15 …)"·"(T40-1~T40-12)"로 고쳐
     둘 것이므로(그 PRP §8) 그 위에서 고친다.
10. 원장(`tests/mutations.tsv`): T34-1/2 행 삭제 · T40-13~15 변조행 3 추가 · T22-137·T25-146 면제 → 변조 승급 2 · 머리 주석 "아래 286개는" →
    **284**, 연혁 문장에 "docs/prps/dashboard-into-hub.md M2 가 폐기 어휘(HD15)·구세대 조항(§5.3) 때문에 개정한 T22-137·T25-146 을 같은
    규칙으로 변조행 승급시켜 286 → 284" 한 문장. 이 숫자는 사전 점검 T99-6 이 실측과 대조한다(틀리면 스위트 전체 exit 1).
11. 문서: `hub/README.md`(§7.2.1 표) · `commands/hub.md` 구현 노트 · 주석(§7.2).
12. 검증 5종(프로젝트 CLAUDE.md §4, 파이썬은 `python3 -B`). 배포 후 `/hub server restart` 1회(서버는 옛 코드로 돈다 — harness-update 한계 문단
    그대로).

**폭발 반경(M2)** (2026-09-24 재확인, 기준 3d76b81):
- 코드: `hub/bin` 6모듈 — `hub_parse` 145 → ≈290 · `hub_dashboard_render` 641 → ≈420 · `hub_dashboard_log` 372 → ≈290 · `hub_collect` 736 →
  ≈690 · `hub_project` 569 → ≈540 · `hub_server` 463 → ≈480(전부 800줄 상한 T25-100 아래). 주석만 3곳(`hub_model`·`hub_usage` docstring,
  대시보드 템플릿 8행) + 조건부 `hub_session` 주석 한 줄(§13.2-(a)).
- 테스트: 아래 표 + 픽스처 5 삭제.
- `tests/run.sh`: T25-222·T34·T22-137·T25-146 개정, 주석 T22-139·T22-171·T25-6·T25-75·T25-90, T40 머리 주석·`test_desc`, T40-13~15 신설.
- 원장(M2 몫): 행 −2 +3, 변조 −2 +3 +2, 면제 −2(공통 사유 286 → 284). `3d76b81` 기준 496 → 497행·변조 174 → 177, N7·N8 이 먼저면
  500 → 501행·178 → 181. 소스 서브체크 ID 는 M2 몫 +1(489 → 490, N7·N8 뒤면 493 → 494).
- 새 가드: **T40-13~15(3건)**.

| 테스트 모듈(3d76b81 건수) | 삭제 | 이동 | 재작성·수정 | 참조 재조준 | 신규 |
|---|---|---|---|---|---|
| `test_hub_parse.py`(22) | 22 | 19 들어옴 | — | — | ≈16 |
| `test_hub_dashboard_render.py`(61) | 5 | 19 나감 | 9(→≈5) | 5 | — |
| `test_hub_dashboard_log.py`(74) | 7 | — | 3 | 6 | ≈3 |
| `test_hub_dashboard_contract.py`(6) | — | — | 6(→≈4) | — | — |
| `test_hub_collect.py`(100) | ≈6 | — | ≈15 | — | ≈3 |
| `test_hub_project.py`(89) | 6 | — | ≈10 | — | — |
| `test_hub_model.py`(27) | — | — | 7 | — | — |
| `test_hub_server.py`(37) | — | — | ≈12 | — | ≈5 |
| `test_hub_session.py`(150)·`test_hub_template_dom.py`(10) | — | — | — | — | — |
| **합계** | **≈46** | **19** | **≈62** | **11** | **≈27** |

손대는 기존 테스트 ≈138건(원 계획 "≈70"), 신규 ≈27건, 순감 ≈25건.

**승인 항목(M2)**: §17-5~7(재승인 필요 없음 — §17 끝).

### 14.3 M3 (범위 밖, 병합 후) — 카드 판정 배지 · 템플릿 주석 정정 · 구세대 리텐션 패턴 제거
별도 PRP + 목업. 이 문서는 데이터 준비도 하지 않는다(HD13).

---

## 15. 테스트 계획 요약 — 순수 로직 케이스

| 대상 | 케이스 |
|------|--------|
| `hub_parse.parse_event_lines`(이동) | 기존 케이스 전부 유지(깨진 줄·모르는 kind·타입 불일치·time_ms 범위·U+2028 보존·마지막 init 이후) |
| `hub_parse.snapshot_from_events`(신규) | 표준 4/4·FAIL 회귀·축약·앞 단계 생략(`impl` 만 기록)·비표준 목록 `step`·이벤트 0건 = 첫 단계 active·`percent` 반올림(2/3→67)·`title` 원문·`task_started_at_ms`·`updated_text` |
| `hub_dashboard_render.*` | 로그 렌더·상세 마크업·`PublishedValues` 케이스 그대로(61 → ≈33 — 파싱·축약기 19건은 `test_hub_parse.py` 로, 경로 사본 5건 삭제) · 옛 HTML 파서 계약 9건 자리에 렌더↔스냅샷 일관성 ≈5건(같은 이벤트의 `render_from_events` 제목·진행률·단계 줄 = `snapshot_from_events` 값) (2026-09-24 재확인, 기준 3d76b81) |
| `hub_project.session_id_from_dashboard_file_name`·`tier1_file_path` | `.jsonl` 만 통과·`.html` 거부·경로 조립 |
| `hub_dashboard_log`(I/O, 샌드박스 cwd·`HOME`) | `NOSESSION`·`DISABLED`(`read_dashboard_enabled` 경유)·`NOINIT`·`BADKIND`·`BADINDEX`·`MKDIR-FAILED`·리텐션 3패턴·원자적 쓰기 잔재 없음·`switch` 필드 보존/파싱 실패 무기록·M2: `.html`·사이드카 미생성·`init` 한 번의 원자적 쓰기 1회 이상(옛 3회 이상)·`render` 는 알 수 없는 서브커맨드(exit 2) (2026-09-24 재확인, 기준 3d76b81) |
| `hub_server._serve_project_dashboard`(I/O) | §14.2-4 |
| `hub/install.sh`(T40, 샌드박스 HOME) | 규칙 배포·제거·순서·계수·미끼 보존 |

---

## 16. 리스크와 대안

| # | 리스크 | 대비 |
|---|--------|------|
| R1 | 허브 사용자가 coding-harness 만 갱신해 기록이 조용히 멈춘다(§11.3 둘째 줄) | `/harness-update` 는 두 채널을 순서대로 갱신. README·hub/README 1줄 안내. 회복은 `hub/install.sh` 1회 |
| R2 | `~/.claude/rules/hub/` 가 coding-harness 의 관리 밖 파일이라 사용자가 "누가 만들었나" 혼동 | 파일 첫 줄에 출처("hub/install.sh 가 배포·제거")를 적는다. `hub/install.sh --uninstall` 이 지운다(T40-2) |
| R3 | 서버가 꺼진 머신에서 대시보드를 볼 길이 없어진다(`file://` 폴백 소멸) | 승인 §17-5. 허브 패널의 `file://` 안내 문구(FILE_MODE_DASHBOARD_HINT)가 이미 "서버를 켜면" 이라고 안내한다 |
| R4 | M2 배포 직후 열려 있던 패널의 세션 키가 바뀌어 첫 폴링 404 | 다음 수집(≤2초 게이트)에서 새 레지스트리로 회복. 재기동 1회 필요(코드 갱신) |
| R5 | 요청마다 템플릿 읽기 + 렌더 — 폴링 60초 × 열린 패널 수 | 60KB 문자열 치환 9회, 밀리초. `collect_snapshot` 50ms 에스컬레이션 조건에 편입 |
| R6 | T35 개정(commands 에 .py 부재)으로 가드가 약해질 여지 | 실물 바이트코드를 `commands/__pycache__/` 에 만드는 방식으로 설치기 경로는 그대로 검증한다. 검사 대상 코드(`remove_pycache_from_target_directory`)는 무변경 |
| R7 | 원장 머리 주석 계수·hub/README 근접 hunk 의 리베이스 충돌 | §13 표 — 리베이스 뒤 실측으로 다시 센다. 상수는 만지지 않는다 |
| R8 | `Tier1Snapshot` 의 소비자 없는 필드가 상수로 남는다(HD6) | 부채로 기록. M3 이후 별도 청소(픽스처 ≈40건 + T25-12) |
| R9 | 옛 문단이 든 compact 요약을 안고 있는 세션이 옛 런처를 부른다 | 파일 부재 오류 1줄 → 규칙의 생략 조항. 1회성 |
| R10 | 규칙 파일 바이트가 조용히 늘어난다(허브 사용자의 상시 비용) | T40-5 정확 일치 래칫(T22-163 승계) |
| R11 | 동시 작업과의 병합 충돌 — README 「프로젝트 상세 패널」 383행(같은 문장)·원장 머리 계수(같은 줄)·원장 T34-1/2 ↔ T25-233~240(인접 행) (2026-09-24 재확인, 기준 3d76b81) | §13.2 대응 열 — 두 번째 병합 쪽이 구 단위 재적용·계수 재계산(T99-6)·전체 스위트 |
| R12 | `hub_session.py` 주석 부패 5곳을 미룬다(§13.2-(e)) — 그동안 독자가 사라진 문서(`commands/dashboard.md`)를 찾는다 (2026-09-24 재확인, 기준 3d76b81) | 다음 `hub_session.py` 편집 회차(RI13 분리 검토 포함)의 할 일. 바꿀 문구는 §13.2-(e) 에 적어 뒀다. 코드 동작과는 무관 → **해소(2026-09-28)**: 5곳을 §13.2-(e) 문구대로 교체했다((c) 갈래의 "그 값"은 `task_started_at_ms` 로 풀어 썼다). 파일이 800 → 799줄로 줄어 RI13 분리 검토(확장 시)는 걸리지 않았다 |
| R13 | T25-90 의 「구세대」 토큰을 리텐션 문장이 계속 담는 방식(주석만 개정, 승급 없음)은 가드의 뜻이 "자연 치유 서술"에서 "구세대 산출물 처리 서술"로 바뀐 채 이어진다 (2026-09-24 재확인, 기준 3d76b81) | 주석에 새 뜻을 적는다. 대안 — 토큰을 빼고 T25-90 을 개정·변조행 승급(면제 −1 더, T37 미러 +1회) — 은 뜻을 더 분명히 하는 대신 무겁다. 구현·검수가 대안을 택해도 결정 변경이 아니다 |
| R14 | 원 계획이 놓친 결합 5건(★)이 재확인에서 드러났다 — 같은 종류가 더 있을 수 있다 (2026-09-24 재확인, 기준 3d76b81) | M2 1단계 전에 README·헬퍼 표 개정본만 먼저 적용한 상태로 `bash tests/run.sh --only T22,T25,T34` 를 돌려 RED 목록을 받고 §14.2 9번과 대조한다 |

**검토했으나 채택하지 않은 대안**
1. **SessionStart 훅 주입(§3.2 B)** — compact 재발화라는 문서화된 보장은 매력적이지만, 허브의 "모델 토큰 0"을
   깨고 설치 키를 흔들며 기존 머신이 자동 갱신되지 않는다.
2. **허브 페이지 안 인라인 세션 뷰(§5.1 다)** — 폴링·PiP 통합의 최종형이지만 화면 변화 + 워크트리 충돌. M3 이후.
3. **M2 를 먼저(HD4 역순)** — 채널 간 렌더러 중복 1회차. 기각.
4. **`/dashboard` 명령 파일을 허브가 `~/.claude/commands/` 에 배포** — 세 번째 배포 대상. 기각(HD9).

---

## 17. 사용자 승인이 필요한 결정

**M1**
1. **허브 없는 머신에서 대시보드 기능 전체 소멸(HD1).** 승인하면: 허브를 설치하지 않은 머신(개인 PC 등)에서는
   진행 기록 지침(상시 1.4KB)·기록기·`/dashboard` 명령이 모두 사라지고 `.claude/dashboards/` 가 새로 생기지 않는다.
2. **기록 지침의 배포 경로 = 허브 설치기 → `~/.claude/rules/hub/dashboard-recording.md`(HD2, 안 A).** 승인하면:
   허브를 설치·제거할 때 그 규칙 파일이 함께 생기고 사라지며, coding-harness 설치기는 그 파일을 건드리지 않는다.
   (대안: `role-separation.md` 에 "진행 기록은 허브 규칙이 담당" 1줄 포인터를 남긴다 — 상시 ≈40 토큰/호출.)
3. **`/dashboard on|off` → `/hub dashboard on|off`(HD9), `commands/dashboard.md` 툼스톤 제거(HD10).** 승인하면:
   끄기·켜기 명령 이름이 바뀌고, 다음 설치에서 옛 `dashboard*` 4파일이 대상 머신에서 지워진다(수정된 사본은 보호).
4. **coding-harness 설치 절차(README)에서 「대시보드 옵션 질문」 삭제.** 승인하면: coding-harness 만 설치할 때 대시보드
   질문을 하지 않고, 허브 안내 1줄만 남는다.

**M2**
5. **세션별 HTML·사이드카 발행 중단, 허브 서버가 JSONL 로 요청 시 렌더(HD5·HD8).** 승인하면: `.claude/dashboards/`
   에는 `.jsonl` 만 남고, 대시보드 화면은 허브 서버가 켜져 있을 때만 볼 수 있다(디스크의 HTML 을 브라우저로 직접
   여는 길이 없어진다). **화면 모양은 같다.**
6. **레거시 단일 파일 `.claude/dashboard.html` 읽기 폐기(HD7 — DN9 번복).** 승인하면: 09-14 이전 방식으로 만들어진
   옛 파일은 허브 카드에서 더 이상 보이지 않는다(지금 그 파일을 갱신하는 곳은 없다).
7. **작업 시작 시각 = JSONL 첫 줄(`init`) 시각(HD8).** 승인하면: 허브의 실행 목록 경계(RL8)가 사이드카 파일 없이
   같은 값으로 판정된다.

**범위**
8. **카드 판정 배지·실행 뷰 병합·reflog 커밋 파생은 이 회차 범위 밖(HD13).** 승인하면: 이번 회차는 화면 변화
   0 으로 끝나고, 배지는 워크트리 병합 뒤 별도 설계·목업으로 간다.

**재승인 필요 (2026-09-24 재확인, 기준 3d76b81): 없음.**
이번 갱신은 M2 계획을 지금 코드에 맞춰 사실·건수·테스트 계획을 고친 것이다. 위 1~8 의 결정은 하나도 바뀌지 않았다 — M2 는 이미 받은
승인 5·6·7 대로 시작하면 된다. 바뀐 것은 네 가지다. ① M2 가 새로 쓰는 검사 번호(T40-12~14 → T40-13~15 — 12번은 다른 작업이 먼저 쓴다).
② 원래 계획이 빠뜨린, M2 가 함께 고쳐야 하는 기존 검사 5곳과 늘어난 테스트 수정 건수(약 70건 → 약 140건). ③ 동시에 진행 중인 두 작업과
겹치는 곳과 병합 순서 권고. ④ 오래된 주석 정리 범위. 알려 둘 것(승인 불필요): 대시보드 화면 파일의 머리 주석 한 줄을 고치므로 "템플릿
0바이트 변경"이 "보이는 화면 변경 0"으로 바뀐다(§5.1) · `hub_session.py` 의 오래된 주석 다섯 곳은 다른 작업이 그 파일을 고치는 중이라
이번에는 두고 다음에 고친다(§13.2-(e)).

**사용자 결정 (2026-09-24, M2 착수 전).** ① 병합 순서 **N7·N8 → 세션 A(세션 모달) → M2** 승인 — M2 구현은 바로 시작하되
`main` 반영은 세션 A 가 들어온 뒤로 한다(늦어지면 그때 다시 묻는다). ② `hub_session.py` 주석 부패 정리를 다음 그 파일 편집
회차로 미루는 것(§13.2-(e)) 승인. ③ `hub_dashboard_template.html` 머리 주석 한 줄 정정을 M2 에 넣는 것(§7.2 · §5.1) 승인.

---

## 18. 참고

- 번복한 결정: DN9 의 "허브 레거시 읽기 유지"(→ HD7) · DN11 의 사이드카 유지(1단계 한정 결정 — 2단계에서
  폐기하기로 예견돼 있었다, → HD8) · DN14-(b) 의 "템플릿 폴링 제거"는 (다)안의 성질이라 이 회차에는 해당 없음.
- 유지한 결정: DN2·DN3·DN4·DN5·DN6·DN12·DN13·DN15·DN16 · ST1(세션 ID 파일명)·ST9~ST14(발견·라우트·키) ·
  RL10(오프 스위치) · N3(요청 문자열로 경로를 조립하지 않는다 — 레지스트리 값이 `.jsonl` 로 바뀌어도 그대로).
- 사실 확인 출처(2026-09-23): Claude Code 문서 hooks-guide 「Re-inject context after compaction」(stdout 주입 이벤트·
  `source: compact`), memory 「Set up rules」·「User-level rules」(하위 디렉터리 재귀 로드·사용자 범위), context-window
  (startup 콘텐츠 compact 재로드·스킬 설명 `noSurviveCompact`).
- 메인 세션 실측 스크립트: 스크래치패드 `dash_calls.py`(세션 종료 시 사라진다 — 방법은 §2.1 서술로 충분하다).
