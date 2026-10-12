# CLAUDE.md 분리 — 설계 결정 브리프 (PRP 작성용 입력, 커밋 대상 아님)

> 4개 앵커로 독립 설계안을 받아 3렌즈(규격 정합성·파급/리스크·지속성) 심판을 붙인 결과다.
> 최종 종합 에이전트가 세션 한도로 실패해 **메인 세션이 판정했다.**

## 채점 결과 (안 번호로 재집계 — 심판들이 이름 문자열을 다르게 적어 원 집계가 쪼개져 있었다)

| 안 | 규격 | 파급 | 지속성 | 합계 | 치명 결함 |
|---|---|---|---|---|---|
| **안 3 — 배포 채널 이관 (deploy-to-rules)** | **8** | **8** | **8** | **24** | **0건** |
| 안 2 — rules 기반 지침 분리 | 6 | 6 | 6 | 18 | 2건 |
| 안 1 — 루트 고정 + claudeMdExcludes | 5 | 9 | 3 | 17 | 2건 |

**승자: 안 3.** 만장일치 8점, 치명 결함 0건. 규격·지속성 심판의 1위.
**설계안 1개(「완전 분리」 앵커)는 구조화 출력 실패로 반환되지 않았다** — 그 축은 탐색되지 않았다.

## 확정된 규격 사실 (심판이 공식 문서를 직접 WebFetch 해 재확인한 것)

- `~/.claude/rules/` 의 frontmatter 없는 규칙은 `~/.claude/CLAUDE.md` 와 **네 성질이 전부 같다**:
  "Personal rules in `~/.claude/rules/` apply to every project on your machine" ·
  "Rules without `paths` frontmatter are loaded at launch with the same priority as `.claude/CLAUDE.md`" ·
  "User-level rules are loaded before project rules, giving project rules higher priority" ·
  컴팩션 표의 같은 행 "| Project-root CLAUDE.md **and unscoped rules** | Re-injected from disk |"
- 서브에이전트도 계층 전체를 상속한다 — "every level of the CLAUDE.md hierarchy the main
  conversation loads, including `~/.claude/CLAUDE.md`, project rules, ..."
- **발견 이름이 고정돼 있다** — "Claude Code reads `CLAUDE.md`, not `AGENTS.md`". 발견 대상은
  `CLAUDE.md`/`CLAUDE.local.md`/`.claude/CLAUDE.md`/`.claude/rules/*.md` 뿐이다.
  따라서 **레포의 `rules/` 트리는 구조적으로 미발견**이다(실측 삼중 확인).
- 배제된 후보와 사유: `./.claude/CLAUDE.md`(같은 project scope 로 이어 붙는다) ·
  조상 디렉토리(launch 로드) · `.claude/rules/` 아래 frontmatter 없이(재귀 발견) ·
  `CLAUDE.local.md`(같이 로드됨 + gitignore 관례로 팀 공유 불가) ·
  `@path` import(이중 로드 재발) · gitignore 로 감추기(근거 없음) · 저장소 밖(배포 계약 붕괴)
- 안 1 이 탈락한 이유: `claudeMdExcludes` 의 문서화된 용도는 **조상·남의 패키지**이고, 루트를
  언급하는 두 문장이 필요한 것의 반대를 말한다("excludes every package's CLAUDE.md **while
  keeping the root**"). 컴팩션의 project-root 재주입 경로와의 상호작용도 미규정이다.
- 안 2 가 탈락한 이유: "**If a rule must persist across compaction, drop the `paths:`
  frontmatter or move it to the project-root CLAUDE.md**" — 안 2 는 카브아웃을 `paths:` 뒤에 뒀다.
- 지속성 심판의 결정적 논거: `/init`("suggests improvements") · `/doctor`("proposes trims for a
  checked-in CLAUDE.md") · `/memory`("entries for files that don't exist yet")가 모두 **루트
  CLAUDE.md 에 내용을 써 넣도록 능동 제안**한다. 루트를 배포물로 유지하는 설계는 하네스 중력과 싸운다.

## 안 3 의 설계 골자

**배포 목적지를 옮긴다.** `~/.claude/CLAUDE.md` 배포를 그만두고, 그 223줄을 `rules/workflow/`
4파일로 내보낸다. 루트 `CLAUDE.md` 는 coding-harness 전용 프로젝트 지침(~70줄)이 된다.

```
rules/workflow/role-separation.md            응답 언어 · 위임 승인 문단(원문 보존) · 작업 분류 · 1~3단계 · 공통 규칙  ≈120줄
rules/workflow/model-routing.md              모델 운용 원칙                                                      ≈45줄
rules/workflow/code-quality-baseline.md      구조·가독성·설계 원칙·성능·강제 수단                                  ≈45줄
rules/workflow/project-instructions-checklist.md   프로젝트 CLAUDE.md 5항목 체크리스트                            ≈15줄
```

- 배포 자산 = `rules/`(41→46) · `agents/`(4) · `commands/`(10) **3종**. `frontmatter 없음` → launch 로드.
- 루트 `CLAUDE.md` 는 자기 체크리스트 5항목을 실제로 채운다 — 개요·금지사항(설치 스크립트 실행
  금지, **이 저장소에 `--scope project` 자기 설치 금지**), 아키텍처, 병목(**세션 컨텍스트 예산**),
  빌드/검증 4명령, 컨벤션(**`tests/run.sh` T 그룹 함수에 50줄 제한 미적용** 등).
- `install.sh` 는 **짧아진다**(약 −40줄) — CLAUDE.md 특수 케이스(충돌 exit 1, `--force` 백업,
  `files_count.CLAUDE_md`)가 통째로 사라진다. `MANIFEST_VERSION` 을 2로 올린다.
- `--scope project` 가 **구조적으로 비파괴**가 된다 — 대상 프로젝트의 `./CLAUDE.md` 를 건드리지 않는다.
- 부수 해소: README vs `harness-update.md` 의 자동 `--force` 온도차 충돌이 소멸한다.

**세 피해 전부 해소.** 피해 2 는 "함수 50줄"이 user scope 로 도착하고 프로젝트 지침이 이기므로
(`"User-level rules are loaded before project rules, giving project rules higher priority"`)
루트 CLAUDE.md 에 `tests/run.sh` 예외를 **정당하게** 쓸 수 있게 된다.

## 안 3 의 자기 신고 약점 (설계에서 반드시 다뤄라)

1. **전역 컨텍스트 비용은 1바이트도 줄지 않는다** — 215줄은 여전히 모든 프로젝트에서 로드된다.
   줄어드는 것은 이 저장소의 중복분뿐이고, 4파일 분할로 주입 헤더가 3개 늘어 총 바이트는 조금 증가한다.
2. **같은 우선순위의 충돌이 기계적으로 해결되지 않는다** — 이관 후 팀의 `./CLAUDE.md` 와
   `./.claude/rules/workflow/*` 가 같은 우선순위로 공존한다. 규격은 "if two rules contradict
   each other, Claude may pick one arbitrarily" 라고 경고한다. 조정 장치는 이관 본문의 문장 하나뿐이다.
3. **모순의 동거가 눈에 보이게 된다** — `rules/common/agents.md`(옛 로스터)·
   `development-workflow.md`(5단계)가 이관된 4에이전트·3단계와 같은 디렉토리·우선순위에 놓인다.
4. **중복을 옮기기만 한다** — 이관되는 「코드 품질 가이드라인」이 `rules/common/coding-style.md` 와
   상당 부분 겹친다. 컨텍스트 예산을 병목으로 규정하면서 중복을 남기는 것은 일관성 흠이다.
5. **테스트 재작성이 가장 큰 위험** — T5·T6·T7 은 경로가 아니라 **기대 결과**(exit code, 백업 주체)가
   바뀐다. (단 지속성 심판이 정정: "5,391줄 테스트에 HOME 오버라이드가 없다"는 **사실과 다르다** —
   이미 4곳에 있다. 안 3 이 자기 최대 위험을 과대평가했다.)
6. **Case D 는 자동 해결 불가** — 예전에 `--scope project` 로 설치하고 손으로 병합한
   `<proj>/CLAUDE.md` 는 팀 소유 커밋 파일이라 건드리지 않는다. 사람이 정리할 때까지 그쪽엔 이중 로드가 남는다.
7. **은퇴 판정이 센티널 문자열에 의존한다** — `서브에이전트 위임은 사용자가 상시 요청한 것이다` 가
   개정되면 판정이 조용히 실패한다.
8. **갓 clone 한 기여자는 워크플로우를 못 본다** — `install.sh --scope user` 를 돌린 사람만 적용받는다.
9. **롤백에 orphan 이 남는다** — 되돌리면 `~/.claude/rules/workflow/` 가 남아 다시 이중 로드가 된다.

## 사용자 승인 사항

**`~/.claude/CLAUDE.md` 는 백업 후 삭제한다** (2026-08-28 승인). 남기면 같은 223줄이 user
CLAUDE.md 로 또 로드돼 이중 로드가 위치만 바뀐 채 유지된다. 백업본은 이름이 `CLAUDE.md` 가
아니므로 재로드되지 않고 `.claude/rules/` 아래도 아니어서 규칙으로도 걸리지 않는다.
