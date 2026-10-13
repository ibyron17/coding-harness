# coding-harness — 프로젝트 지침

이 문서는 **coding-harness 저장소 자신**의 프로젝트 지침이다(배포 대상이 아니다). 범용
개발 워크플로우 규칙은 `rules/workflow/*.md` 로 이관됐다 — `install.sh --scope user`
로 설치해야 이 저장소를 clone 한 세션에도 자동 적용된다(레포의 `rules/` 트리 자체는
구조적으로 미발견이다).

## 1. 개요와 목적

- Claude Code 배포 자산(rules/agents/commands) + 세션 허브(hub/)를 관리·배포하는 저장소.
- **하지 말 것**:
  - (a) 이 저장소 **안에서 `install.sh --scope project` 실행 금지** — 자기 설치는
    `.claude/rules` 이중 로드 재발이며, `tests/run.sh` T31-4 가 이런 커밋을 차단한다.
  - (b) 세션이 **실제 `$HOME` 을 대상으로 설치를 실행하는 것 금지** — 검증은
    `bash -n install.sh`·`bash tests/run.sh`(샌드박스 `HOME` 치환)로 한다.
    `--scope user` 실설치는 사용자가 명시적으로 요청했을 때만 한다.

## 2. 아키텍처 (레이어와 책임)

- **배포 채널**: `install.sh` — 순수 bash, 외부 의존성 0. 소유권 원칙(레포가 배포하는
  파일만 관리하고, 대상 디렉토리의 다른 파일은 건드리지 않는다).
- **배포 자산**: `rules/` 46개 · `agents/` 4개 · `commands/` 8개 — 3종. 레이어 간
  통신은 manifest(`.coding-harness.json`, v3)의 해시 대장뿐이다.
- **허브 런타임**: `hub/` — python3 표준 라이브러리 전용(문서화된 결정, 새 의존성 추가
  금지).
- **검증**: `tests/run.sh`(install.sh·문서 정합성 T 그룹) · `tests/hub`(stdlib unittest).

## 3. 성능 (병목)

이 저장소의 병목은 실행 성능이 아니라 **세션 컨텍스트 예산**이다 — 상시 로드되는
바이트 수를 `tests/run.sh` T26 이 래칫으로 강제한다. 상시 컨텍스트(`CLAUDE.md` ·
`rules/README.md` · `rules/common/*.md` · `rules/workflow/*.md`)를 늘리는 변경은
그 근거를 커밋에 남긴다. 내리는 것은 자유, 올리려면 T26 상수를 고치는 커밋에 이유가
있어야 한다.

## 4. 빌드/검증 명령 (정본)

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

## 5. 컨벤션

- **커밋 메시지**: `type: 한국어 서술형` (git log 관행 — feat/fix/docs/test/refactor 등).
- **브랜치**: `main` 은 릴리스 브랜치다 — 직접 커밋·푸시하지 않고 릴리스 때만 `develop` 에서
  반영한다. 작업은 `develop` 위의 `<type>/<짧은-이름>` 브랜치(예: `fix/hub-host-header-guard`)에서
  하고 원격에 푸시한다. 워크트리가 `main` 에서 갈라졌으면 `develop` 위로 옮긴다. `develop`
  반영은 사용자가 요청할 때 한다.
- **함수 50줄 제한의 프로젝트 예외**: `tests/run.sh` 의 T 그룹 함수는 시나리오 나열이
  본질이라 분할이 오히려 가독성을 해친다 — user rules 의 50줄 규칙에 대한 정당한
  프로젝트 우선 적용이다(project CLAUDE.md 가 user-level rules 보다 우선순위가 높다).
- 레포에서 관리 파일(rules/agents/commands)을 지우거나 개명하는 커밋은 `removals.txt`
  에 옛 경로를 추가한다(툼스톤 — 대상 머신의 낡은 사본을 청소하는 영구 메커니즘).
- 설계 문서(PRP)는 `docs/prps/{기능명}.md` 에 쓴다.
