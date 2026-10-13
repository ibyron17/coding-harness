# coding-harness 버전 체계와 허브 새 버전 알림 (harness-versioning)

> **확정 문서 — 2026-10-13 사용자 승인(D1~D5 전부 아래 표의 권고안 채택).** 단계 A(버전 체계 적용)와
> 단계 B(허브 새 버전 알림, 안 1)를 둘 다 구현한다. B 는 A 에 의존한다(설치 기록의 버전 필드와 원격 태그가
> 있어야 비교할 수 있다). 허브에서 직접 업데이트를 실행하는 안 2 는 채택하지 않았다 — 서버에 상태를 바꾸는
> 경로(POST)를 추가하지 않는다.

---

## 사용자가 정할 것

| # | 결정 | 선택지 | 권고 | 승인하면 일어나는 일 | 결정 결과(승인 2026-10-13) |
|---|------|--------|------|------------------|------------------|
| D1 | 버전의 기준과 올리는 시점 | (가) 저장소 맨 위 `VERSION` 파일이 기준, **릴리스할 때만** 올리고 같은 커밋에 태그 `vX.Y.Z` 를 단다 · (나) 배포되는 파일이 바뀌는 커밋마다 올린다 · (다) 파일 없이 git 태그만 쓴다 | **(가)** | 평소 커밋은 버전을 건드리지 않는다. "이제 내보내자"고 정한 때만 번호를 하나 올리고 이름표(태그)를 붙인다. 문서만 바꾼 커밋은 번호가 바뀌지 않는다 | **채택(가)** — 루트 `VERSION` 정본, 릴리스할 때만 올림, 같은 커밋에 태그 `vX.Y.Z` |
| D2 | 첫 번호와 첫 태그 | `1.0.0` · `0.1.0` | **`1.0.0`** — 팀이 이미 쓰고 있고 공개 저장소이며 업데이트 경로가 문서화돼 있다. `0.x` 는 "아직 아무 때나 바뀔 수 있다"는 뜻이라 지금 상태와 맞지 않다 | 단계 A 가 main 에 들어간 커밋에 `v1.0.0` 이름표를 붙인다. **원격(공개 저장소)에 이름표를 올리는 일(태그 푸시)은 그 시점에 한 번 더 묻는다** | **채택 `1.0.0`** — 첫 태그 `v1.0.0`(태그 푸시는 그 시점에 한 번 더 묻는다) |
| D3 | GitHub 릴리스 페이지 | 만든다 · 만들지 않는다(태그만) | **만들지 않는다** | GitHub 의 Tags 목록에만 보인다. 변경 내역 페이지는 없다. 필요해지면 태그에 나중에 붙일 수 있다 | **채택 — 만들지 않는다**(태그만) |
| D4 | 허브에 새 버전 알림을 넣을지, 넣으면 버튼이 무엇을 할지 | (0) 넣지 않는다 · **(1) 「새 버전 1.1.0」 버튼 — 누르면 `/harness-update` 가 복사되고 Claude Code 에 붙여 넣어 실행** · (2) 허브에서 바로 업데이트 실행 | **(1)** | 허브 제목 옆에 설치된 버전(`v1.0.0`)이 작게 보이고, 새 릴리스가 올라오면 오른쪽 위에 파란 알림 버튼이 뜬다. 버튼은 업데이트를 직접 하지 않고 명령을 복사만 한다 — 업데이트는 지금처럼 Claude Code 안에서 `/harness-update` 로 한다 | **채택 (1)** — 「새 버전 X.Y.Z」 알림 버튼 + 누르면 `/harness-update` 복사. 허브에서 직접 업데이트 실행(안 2)은 하지 않는다 |
| D5 | (D4 가 1 이면) 원격 확인의 기본값 | **켜짐**(끄는 설정 제공) · 옵트인(기본 꺼짐) | **켜짐** | 허브 서버가 켜져 있는 동안 6시간에 한 번, coding-harness 저장소 폴더에서 원격의 이름표 목록을 읽는다(`git fetch` 와 같은 상대에게 같은 종류의 요청, 저장소 내용은 바꾸지 않는다). 꺼짐으로 정하면 사용자가 설정을 켜기 전에는 알림이 뜨지 않는다 | **채택 — 기본 켜짐**(`update_check_enabled: false` 로 끈다) |

목업(D4 의 「현재 | 안 1 | 안 2」 대조): 최종 보고에 적은 스크래치패드 경로의
`harness-versioning-mock.html`·`.png`.

### 해석 메모 — 다르게 읽힐 여지

- **「버전을 적용해줘」** — 번호 체계를 정하고, 그 번호가 설치 기록·설치 출력·업데이트 보고에 실제로
  찍히며, 첫 번호(D2)를 다는 것까지로 읽었다. 허브 화면에 버전을 띄우는 것은 단계 B 에 넣었다.
- **「원격 저장소에 버전이 업데이트된 경우」** — 원격에 **새 릴리스 태그가 올라온 경우**로 읽었다.
  "원격에 새 커밋이 생긴 경우"로 읽으면 문서만 바꾼 커밋에도 알림이 뜬다. 그 해석이 맞다면 D1 은
  (나)가 되고 B 의 확인 대상이 태그가 아니라 `refs/heads/main` 이 된다(§5.3 표의 마지막 행).
- **「업데이트 버튼」** — 실행 버튼(안 2)이 아니라 알림 + 명령 복사 버튼(안 1)을 권고한다. 근거는 §5.4.

---

## 1. 요구사항 요약

coding-harness 에는 지금 버전 개념이 없다. `install.sh` 의 `MANIFEST_VERSION=3` 은 설치 기록 파일의
**스키마** 번호이고, 설치된 것이 어느 시점의 하네스인지는 커밋 해시(`installed_from_commit`)로만 알 수
있다. 팀원은 "지금 내 것이 최신인가", "무엇이 바뀌었나"를 커밋 해시로 판단해야 하고, 허브는 새 버전이
나왔다는 사실을 알릴 방법이 없다. 이 설계는 (A) SemVer 버전 번호를 정본 한 곳에 두고 설치 기록·설치
출력·`/harness-update` 보고에 흐르게 하며, (B) 그 번호를 원격 릴리스 태그와 비교해 허브에 새 버전
알림을 띄울 수 있는지 검토하고 권고안을 별도 단계로 설계한다.

## 2. 단계 구성

| 단계 | 범위 | 의존 | 외부 작업 |
|------|------|------|-----------|
| A | `VERSION` 도입 · `install.sh` 가 설치 기록에 버전 기록 · `/harness-update` 보고 · README · `CLAUDE.md` 1줄 · T41 | 없음 | 첫 태그 푸시(D2, 사용자 확인) |
| B | 허브가 설치 버전을 표시하고 원격 태그와 비교해 알림 버튼(안 1)을 띄운다 | A(설치 기록의 `harness_version` · 원격의 `v*` 태그) | 없음 |

A 는 허브를 전혀 건드리지 않는다. D4 가 (0)이면 A 만 구현하고 끝난다.

---

## 3. 단계 A — 버전 체계

### 3.1 결정

**HV1 — 정본은 루트 `VERSION` 파일(SemVer `X.Y.Z` 한 줄)이다.** 태그는 파생이다.
- 근거: `install.sh` 가 git 없이 읽을 수 있다(zip 다운로드·얕은 clone·`.git` 없는 사본에서도
  `installed_from_commit` 은 `"unknown"` 이 되지만 버전은 남는다). `tests/run.sh` 가 형식을 검사할 수
  있다. 태그만 정본으로 두면(D1-다) 설치 시마다 `git describe` 가 필요하고, 태그를 받지 않은 clone
  에서는 버전이 사라진다.
- 형식: `^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$` 한 줄 + 끝 개행 1개. 프리릴리스·빌드
  메타(`-rc.1`, `+sha`)는 받지 않는다(YAGNI, §6).
- **숫자 부분은 1~9자리다**(2회차 검수 Major 반영). 상한이 없으면 원격 태그 한 줄(`v1.0.<5000자리>`)이
  파이썬 `int()` 변환 한도(4300자리)를 넘어 허브의 릴리스 확인 사이클을 예외로 끝낸다(30자리는 그대로
  최신으로 채택돼 화면에 뜬다). 같은 경계를 세 곳이 쓴다 — `install.sh` `HARNESS_VERSION_PATTERN`(`{0,8}`) ·
  `tests/run.sh` T41 · 허브 `hub_release.py` `MAX_VERSION_NUMBER_DIGITS`(9). **저장소가 받는 형식과 허브가 읽는
  형식이 달라지면 안 된다** — 한쪽만 고치지 않는다. 상한 초과 태그는 형식 밖 태그와 같이 무시된다.
  방어선으로, 출력 해석 중 `ValueError` 가 새도 사이클은 사유 `parse_error` 를 기록에 남기고 끝난다.

**HV2 — 태그는 `vX.Y.Z` 주석 태그(annotated)이고, 그 커밋의 `VERSION` 과 같아야 한다.** 원격에
태그를 올리는 것(태그 푸시)이 곧 **릴리스 공표**다 — 단계 B 의 알림은 이것만 본다.

**HV3 — GitHub 릴리스 페이지는 만들지 않는다**(D3). Tags 목록으로 충분하고, 무엇이 바뀌었는지는
`/harness-update` 가 이미 `git log --oneline HEAD..@{u}` 로 보여 준다.

**HV4 — `VERSION` 은 릴리스할 때만 올린다.** 평소 커밋(기능·수정 포함)은 건드리지 않는다.
- 근거 1: 사용자 표현이 "버전이 업데이트된 경우"다 — 알림은 공표된 릴리스에만 반응해야 하고, 문서만
  바꾼 커밋마다 팀 전원에게 알림을 띄우면 알림의 의미가 사라진다.
- 근거 2: 같은 저장소에서 여러 세션·워크트리가 동시에 돈다(사용자 메모리 「동시 세션 주의」). 커밋마다
  `VERSION` 한 줄을 올리면 병합 때마다 같은 줄이 충돌한다.
- 대가: 릴리스 사이의 main 을 설치하면 버전 표기는 직전 릴리스 번호인데 내용은 그보다 앞서 있다.
  그래서 버전을 보이는 곳에는 항상 커밋 짧은 해시를 함께 적는다(`1.0.0 (ce458d6)`).

**HV5 — 올림 규칙은 "배포 표면"을 기준으로 한다.**

배포 표면 = 팀원 머신에 실제로 닿는 것: `rules/` · `agents/` · `commands/` · `hub/` · `install.sh` ·
`removals.txt`. 그 밖(`docs/` · `tests/` · `README.md` · `CLAUDE.md` · `NOTICE.md` · `LICENSE` ·
`VERSION` 자신)만 바뀌었으면 **릴리스 사유가 아니다**.

| 수준 | 언제 | 예 |
|------|------|-----|
| MAJOR | 팀원이 손으로 무언가 해야 하거나, 옛 사용법이 더는 통하지 않는 변경 | 커맨드 삭제·개명(`/env-update` → `/harness-update` 같은), 에이전트 삭제, `install.sh` 옵션 삭제·의미 변경, 옛 `/harness-update` 가 못 읽는 설치 기록 스키마 변경, 허브 `config.json` 키 삭제·의미 변경, 허브 포트 변경, 요구 python 최소 버전 상향 |
| MINOR | 하위 호환 기능 추가 | 새 커맨드·에이전트·규칙, 허브 새 기능, 새 설정 키, 새 `install.sh` 옵션 |
| PATCH | 하위 호환 수정 | 결함 수정, 규칙·커맨드 문구 수정, 성능 개선, 리팩토링 |

릴리스 내용에 여러 수준이 섞이면 가장 높은 것을 쓴다. 판정 입력은
`git log --oneline v<직전>..HEAD -- rules agents commands hub install.sh removals.txt` 이고, 비어
있으면 릴리스하지 않는다. 커밋 접두(`feat:`→MINOR, `fix:`·`refactor:`·`perf:`→PATCH)는 참고일 뿐이다
— MAJOR 는 접두로 드러나지 않으므로 위 표의 목록으로 판정한다.

**HV6 — 설치 기록(manifest)에 `"harness_version"` 필드를 더한다. 스키마 번호는 3 그대로다(v4 아님).**

하위 호환 추가로 충분한 근거(코드를 직접 확인했다):
- `read_manifest_version`(install.sh)은 `grep -oE '"version": *[0-9]+' | head -1` 이다. `"harness_version"`
  에는 `"version"` 부분문자열이 없다(`v` 앞이 `"` 가 아니라 `_`). 값도 따옴표로 시작해 `[0-9]+` 와
  맞지 않는다 — 은퇴 판정 규칙 4(`-ge 3`)가 영향받지 않는다.
- `read_installed_ledger_hash` 는 64자리 hex 값 줄만 찾으므로 무관하다.
- `/harness-update` Phase 1 검증 `version ∈ {1,2,3}` 은 그대로 통과한다. 설치 기록을 읽는 쪽은 모르는
  필드를 무시한다(grep 기반, 허브는 `json.loads` 후 필요한 키만 읽는다).
- 멱등 비교(`save_manifest_file` 의 `grep -v installed_at`)는 버전이 바뀌면 다른 내용으로 보고 다시
  쓴다 — 원하는 동작이다.
- 스키마 번호는 **읽는 쪽이 반드시 알아야 하는 의미 변경**(v2 대장 도입, v3 대장에서 CLAUDE.md 제외)
  에만 올려 왔다. 정보성 필드 추가는 그 기준에 들지 않는다.
- 필드 이름은 `"version"` 으로 시작하거나 `"version"` 을 따옴표째 포함하지 않아야 한다 — T41-3 이 이
  간섭을 고정한다.

**HV7 — `VERSION` 이 없거나 형식이 틀리면 `"unknown"` 을 기록하고 WARN 1줄을 내고, 설치는 계속한다.**
`installed_from_commit` 의 `"unknown"` 폴백이 같은 판단의 선례다. 버전은 메타데이터라 이것 때문에
팀원 설치를 막지 않는다. 형식 오류가 커밋되는 것은 T41-1 이 막는다.

**HV8 — 버전이 보이는 곳(단계 A).**

| 위치 | 표기 |
|------|------|
| `install.sh` 첫 로그 줄 | `[INFO] coding-harness 1.0.0 설치 (scope: user)` / dry-run: `… 1.0.0 설치 계획 (scope: user, DRY-RUN)` |
| 설치 기록 | `"harness_version": "1.0.0"` |
| `/harness-update` Phase 2 | 새 커밋이 있으면 `[INFO] Version: 1.0.0 → 1.1.0` (원격 쪽은 `git show '@{u}:VERSION'`, 없으면 `unknown`) · 최신이면 `[INFO] Already up to date (1.0.0). No changes.` |
| `/harness-update` Phase 5 | `[OK] Update complete — coding-harness 1.1.0 (<short hash>)` |
| `README.md` | 새 절 「버전」 — 의미·확인 방법·릴리스 절차 |

허브 화면 표시는 단계 B 다. `install.sh --version` 은 만들지 않는다(§6).

**HV9 — 강제 수단은 테스트(T41)뿐이다.** 형식·설치 기록 반영·스키마 무간섭·폴백·로컬 태그 일치·문서
토큰을 검사한다. "평소 커밋에서 `VERSION` 을 바꾸지 마라"는 기계로 강제하지 않는다 — 릴리스 커밋과
평소 커밋을 기계가 가를 수 없고, 커밋 훅은 이 저장소가 배포하는 자산이 아니다. 대신 `CLAUDE.md` 에
1줄(HV10)을 둔다.

**HV10 — `CLAUDE.md` §5 컨벤션에 1줄을 더한다**(상시 컨텍스트 증가 — T26 래칫 상수를 같은 커밋에서
올리고 사유를 적는다).
- 문안(안): `- **버전**: 루트 VERSION(SemVer)이 정본이다. 릴리스 때만 올리고 그 커밋에 태그 vX.Y.Z 를
  단다(평소 커밋은 건드리지 않는다). 태그 푸시는 사용자 확인 뒤. 규칙: README 「버전」.`
- 근거: `VERSION` 파일을 본 세션이 `feat:` 커밋마다 번호를 올리는 것이 가장 그럴듯한 실패다. 그 실패는
  HV4(동시 세션 충돌·알림 남발)를 직접 깬다. 규칙 전문은 README 에 두고 상시 컨텍스트에는 포인터만
  둔다(증가분 약 250바이트 — 정확한 값은 구현 단계에서 T26 이 잰다).

**HV11 — 첫 릴리스.** `VERSION` 을 `1.0.0` 으로 만드는 커밋(단계 A)이 로컬 main 에 들어간 뒤 그
커밋에 `git tag -a v1.0.0 -m "coding-harness 1.0.0"` 을 단다. 현재 HEAD(`ce458d6`)에는 달지 않는다
— 그 커밋에는 `VERSION` 이 없어 HV2 를 어긴다. B 를 A 와 함께 구현하기로 하면 B 까지 들어간 뒤에
단다. `git push origin v1.0.0` 은 공개 저장소에 대한 외부 작업이므로 **사용자 확인 대상**이다.

### 3.2 릴리스 절차 (README 「버전」 절에 실을 내용)

1. `git log --oneline v<직전>..HEAD -- rules agents commands hub install.sh removals.txt` — 비면 중단.
2. HV5 표로 수준을 정해 `VERSION` 을 고친다.
3. `bash tests/run.sh --only T41` 통과 확인 → 커밋 `chore: 버전을 X.Y.Z 로 올린다`.
4. `git tag -a vX.Y.Z -m "coding-harness X.Y.Z"` (로컬).
5. **사용자 확인 뒤** `git push origin main` · `git push origin vX.Y.Z`. 모델은 1~4 를 준비하고 5 는
   묻는다(사용자 메모리 — 모델은 병합·푸시까지만, `/harness-update` 는 사용자가 입력).

### 3.3 영향 범위 (A)

| 파일 | 변경 | 이유 |
|------|------|------|
| `VERSION` (신규) | `1.0.0` 한 줄 | HV1 정본. 배포 대상 아님(`rules/agents/commands` 밖) — 파일 수 상수 불변 |
| `install.sh` | 상수 3개 · `read_harness_version` · `build_manifest_json` 인자 1개 · 첫 로그 줄 2곳 | HV6·HV7·HV8 |
| `commands/harness-update.md` | Phase 1 검증 메모(필드 선택적) · Phase 2 버전 줄 · "Already up to date" 줄 · Phase 5 보고 | HV8. 배포 자산이라 설치 대장 해시가 바뀐다(정상) |
| `README.md` | 「버전」 절 신설 · 구조 목록에 `VERSION` 1줄 · `docs/prps/` 문서 수 85 → 86(이 PRP) | HV8·§3.2 |
| `CLAUDE.md` | §5 에 1줄 | HV10 |
| `tests/run.sh` | T41 그룹 신설 · `TEST_GROUPS` 등록 · T26 예산 상수 · 원장 관련 상수(서브체크 ID 하한 등) | HV9 |
| `tests/mutations.tsv` | T41 서브체크마다 변조행 또는 면제행 | 저장소 규약(K5 완비 검사) |

바뀌지 않는 것: `removals.txt`(지우거나 개명하는 관리 파일 없음) · `hub/*` · `MANIFEST_VERSION` ·
`RULES/AGENTS/COMMANDS_FILE_COUNT`.

### 3.4 데이터 모델 (A)

```
VERSION                     # 저장소 루트, 한 줄
1.0.0
```

설치 기록(`~/.claude/.coding-harness.json`) — 새 필드 1개, 위치는 출처 필드 묶음 끝:

```json
{
  "version": 3,
  "repo_path": "/Users/me/works/coding-harness",
  "scope": "user",
  "installed_at": "2026-10-13T05:00:00Z",
  "installed_from_commit": "<40 hex | unknown>",
  "harness_version": "1.0.0",
  "target_base_dir": "/Users/me",
  "files_count": { "rules": 46, "agents": 4, "commands": 8 },
  "files": { "...": "<sha256>" }
}
```

`harness_version` 값 영역: `X.Y.Z` 또는 `"unknown"`. 필드가 없으면 버전 도입 이전 설치다(읽는 쪽은
`"unknown"` 과 같게 다룬다).

### 3.5 인터페이스 (A)

`install.sh` (bash 3.2 호환, 외부 의존 0):

```bash
readonly VERSION_FILE="$REPO_ROOT/VERSION"
readonly HARNESS_VERSION_PATTERN='^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})$'
readonly UNKNOWN_HARNESS_VERSION="unknown"

# 루트 VERSION 을 읽어 SemVer 문자열을 stdout 으로 낸다. 파일 없음·여러 줄·형식 오류 → "unknown"
# 을 내고 WARN 1줄(stderr). 실패로 반환하지 않는다(HV7).
read_harness_version()

# 인자 3개로 바뀐다: installed_at, installed_from_commit, harness_version
build_manifest_json()
```

- `harness_version` 은 전역(`scope`·`force_overwrite` 와 같은 관례)으로 `main` 에서
  `parse_arguments`·`resolve_target_paths` 다음에 한 번 읽는다 — WARN 이 실행당 1번만 나온다.
- 값은 정규식을 통과했거나 고정 문자열이라 JSON 이스케이프가 필요 없다(`installed_from_commit` 과
  같은 근거를 주석에 남긴다).

`commands/harness-update.md` (영문 서술 유지):

- Phase 1 Manifest Validation 에 한 줄: `harness_version` is optional — absent or `"unknown"` means a
  pre-versioning install; report it as `unknown`. **`version ∈ {1,2,3}` 문장은 바꾸지 않는다.**
- Phase 2 Detect changes: 새 커밋이 있으면 `git show '@{u}:VERSION'`(실패 → `unknown`)과 설치 기록의
  `harness_version` 으로 `[INFO] Version: <installed> → <remote>` 를 커밋 목록 앞에 낸다.
- Phase 5 Report 의 첫 줄에 버전과 짧은 해시를 넣는다.
- 기존 T22-168·T22-169 가 검사하는 문구(`MAX_DIFF_LINES` · `.bak-<timestamp>` · `no automatic cleanup`
  · `disable-model-invocation: true` 등)는 건드리지 않는다.

### 3.6 테스트 계획 (A) — `tests/run.sh` T41 「버전 체계」

모두 샌드박스(`mktemp -d`, 기존 그룹과 같은 `register_cleanup_path`)에서 돈다. 실제 `$HOME` 을 쓰지
않는다.

| ID | 검사 | 실패 조건 | 원장 변조행 예 |
|----|------|-----------|----------------|
| T41-1 | `VERSION` 형식 | 파일 없음 · 줄 수 ≠ 1 · 정규식 불일치 · 앞뒤 공백 · 끝 개행 없음 | `VERSION` 을 `1.0` 으로 |
| T41-2 | 설치 기록 반영 | `--scope project` 샌드박스 설치 후 `"harness_version": "<VERSION 값>"` 줄이 정확히 1개가 아님 | `install.sh` 의 `"harness_version"` 줄 삭제 |
| T41-3 | 스키마 무간섭(행동) | 샌드박스 HOME 에 `--scope user` 로 설치해 **새 install.sh 가 만든** 설치 기록을 남기고, 대장에 없는 `~/.claude/CLAUDE.md` 를 둔 뒤 재설치했을 때 `[보호]` 줄이 나오거나 파일이 바뀜 — 은퇴 규칙 4(`read_manifest_version ≥ 3` → skip)가 새 필드가 든 기록에서도 그대로 발동하는지 본다. 지금 T7 의 v3 기록은 손으로 쓴 고정 문자열이라 새 install.sh 산출물로 이 경로를 도는 검사가 없다 | `MANIFEST_VERSION=3` → `2` |
| T41-4 | 폴백 | `VERSION` 을 지운 사본·`1.0` 으로 깨뜨린 사본(`rules agents commands install.sh removals.txt` 복사)에서 설치가 exit 0 이 아님 · `"harness_version": "unknown"` 아님 · stderr 에 WARN 없음 | `read_harness_version` 의 폴백을 `return 1` 로 |
| T41-5 | 멱등·갱신 | 같은 `VERSION` 재설치에서 `manifest → 변경 없음` 이 안 나옴 · `VERSION` 만 바꾼 사본 재설치에서 설치 기록이 안 바뀜 | 멱등 비교에서 `harness_version` 줄도 빼는 변조 |
| T41-6 | 로컬 태그 일치 | 레포의 `v*` 태그마다 `vX.Y.Z` 형식이 아니거나 `git show <tag>:VERSION` 이 태그 숫자와 다름. git·`.git` 이 없으면 건너뛰고 로그 1줄(실패 아님) | 면제행 후보 — 레포의 git 상태에 의존해 사본 변조로 재현하기 어렵다. 면제 사유를 적는다 |
| T41-7 | 문서 토큰 | `harness-update.md` 에 `harness_version` 없음 · README 에 `## 버전`·`VERSION` 없음 · `CLAUDE.md` 에 `VERSION` 없음 | 각 문서에서 토큰 제거 |

부수 갱신: T26 예산 상수(HV10), 원장 하한·서브체크 ID 하한 상수(기존 커밋들이 남긴 주석 관례대로
"순증가 N"과 사유), T20 의 `"version": 3` 검사는 그대로 통과해야 한다.

검증 명령(정본, `CLAUDE.md` §4): `bash -n install.sh` · `bash tests/run.sh` (메인 세션이 커밋 직전 1회).
구현자는 `bash tests/run.sh --only T41` 과 영향받는 그룹(T20·T21·T22·T26·T27·T37)만 돌린다.

---

## 4. 단계 B 결론 (요약)

- **가능하다.** 허브는 이미 "서버 전용 스레드가 원격을 확인하고 → 결과를 파일에 남기고 → 수집이 그
  파일을 읽어 `hub.html` 에 싣는" 구조를 사용량 API 폴링으로 갖고 있다. 같은 모양으로 붙는다.
- **권고: 안 1(알림 + `/harness-update` 복사).** 서버에 쓰기 경로를 만들지 않아 지금의 GET 전용·
  "읽기 전용 허브"(hub/README.md, commands/hub.md) 성질을 그대로 지킨다.
- **원격 확인은 `repo_path` 에서 `git ls-remote --tags --refs origin`** — 저장소를 바꾸지 않고,
  `/harness-update` 가 쓰는 것과 같은 원격·같은 프록시 설정·같은 인증을 쓴다. 확인이 실패하는
  네트워크에서는 `/harness-update` 도 실패하므로 알림과 실제 업데이트 가능 여부가 어긋나지 않는다.
- **안 2(허브에서 바로 업데이트)는 권고하지 않는다** — localhost 상태 변경 엔드포인트(CSRF·DNS
  리바인딩), 실행 중인 서버의 자기 재설치·재시작, `--force` 판단 UI, `/harness-update` 절차의 파이썬
  이중 구현이 필요하고, 허브의 문서화된 범위("명령·제어 기능은 범위 밖")를 뒤집는다.
- 주요 위험: 원격 확인이 허브의 첫 **기본 켜짐 네트워크 호출**이 된다(D5) · 설치 기록이 없는 허브
  단독 설치·project scope 설치에는 알림이 없다 · 360px 폭에서 헤더가 두 줄이 된다.

## 5. 단계 B — 타당성 검토

### 5.1 설치된 버전은 어디서 읽나

| 대상 | 출처 | 비고 |
|------|------|------|
| coding-harness | `~/.claude/.coding-harness.json` 의 `harness_version`·`installed_from_commit`·`installed_at`·`repo_path` | 허브는 머신 전역 자산이라 **user scope 설치 기록만** 읽는다. project scope 설치는 대상 밖(문서화) |
| 허브 자신 | 따로 없다 | 아래 UN6 |

`commands/hub.md` 의 사전 조건 안내가 이미 같은 파일의 `repo_path` 를 읽는다 — 허브가 설치 기록을
읽는 것은 새 결합이 아니다(다만 파이썬 코드가 읽는 것은 처음이다).

### 5.2 둘의 버전이 어긋날 때

허브는 `hub/install.sh` 로 따로 설치되고 설치 기록이 없다. 어긋나는 경로는 둘이다.

| 경로 | 결과 | 판단 |
|------|------|------|
| 팀원이 `install.sh` 만 손으로 돌림(허브는 옛 코드) | 옛 허브에는 이 기능 자체가 없거나, 있으면 하네스 기준 "최신"으로 표시 | README 가 이미 "`install.sh` 를 손으로 돌렸다면 `hub/install.sh` 도" 라고 경고한다. `/harness-update` Phase 4b 가 허브를 저장소와 맞춘다 |
| `hub/install.sh` 만 손으로 돌림(하네스는 옛 설치) | 설치 기록 버전 < 원격 → 알림이 뜬다 | 맞는 알림이다 — rules/agents/commands 가 뒤처져 있다 |

**UN6 — 허브 자신의 버전은 따로 추적하지 않는다.** 알림의 의미는 "coding-harness 설치가 최신
릴리스보다 뒤처졌다"이고, 해결책(`/harness-update`)이 허브까지 함께 맞춘다. 허브가 자기 버전 파일을
갖게 하는 안(`hub/install.sh` 가 `~/.claude/hub/VERSION` 기록)은 관리 파일 수·소유권 범위를 늘리는데
지금 그것이 필요한 사용자 경로가 없다. 다시 꺼낼 조건: 하네스 없이 허브만 설치해 쓰는 사용자가 생기고
그들에게도 알림이 필요할 때.

### 5.3 원격 최신 버전을 아는 방법

| 방법 | 저장소·작업 트리 변경 | 네트워크 상대·프록시 | 실패 처리 | 호출 한도 | 신호 | 의존 |
|------|------|------|------|------|------|------|
| **`git -C <repo_path> ls-remote --tags --refs origin`** | **없음**(ref·`FETCH_HEAD` 를 쓰지 않는다) | 사용자의 `origin` 그대로 — 포크·사내 미러·SSH 모두 따라간다. git 자체 프록시·인증 설정 사용 = `/harness-update` 의 `git fetch` 와 같은 경로 | 타임아웃·종료 코드로 분류. 서버는 `start_new_session` 으로 떠 제어 터미널이 없어 비밀번호·호스트키 질문이 뜰 수 없다 | 공개 저장소 익명 git 요청, 6시간 1회 | 공표된 태그(HV2) | git 바이너리(clone 했으니 있다), `subprocess` |
| `git fetch` 후 비교 | **있다** — `refs/remotes/origin/*`·`FETCH_HEAD` 를 바꾼다. 사용자가 같은 저장소에서 git 을 쓰는 순간과 겹치면 ref 잠금 충돌 | 위와 같음 | 위와 같음 | 위와 같음 | 무엇이든 | 위와 같음 |
| HTTPS 로 raw `VERSION` (`urllib`) | 없음 | `raw.githubusercontent.com` — `origin` URL 을 GitHub 형식으로 해석해야 하고 다른 호스트·사내 미러는 지원 불가. 사내망에서 이 호스트가 막혀 있을 수 있다(미측정) | `hub_usage_fetch` 의 리다이렉트 차단·크기 상한·TLS 분류를 다시 써야 한다 | CDN 캐시(수 분 지연) | main 의 `VERSION` — HV4 에서는 태그와 사실상 같다 | 표준 라이브러리만 |
| GitHub API (`/repos/{o}/{r}/tags`) | 없음 | `api.github.com` — GitHub 전용 | 위와 같음 + JSON 스키마 | **익명 60회/시간/IP** — 회사 NAT 뒤 공유 IP 에서 다른 도구와 한도를 나눈다 | 태그 | 표준 라이브러리만 |
| (참고) `ls-remote origin refs/heads/main` 해시 비교 | 없음 | 첫 행과 같음 | 같음 | 같음 | **새 커밋**(문서 커밋 포함) — 해석 메모의 다른 해석 | 같음 |

**UN1 — `git ls-remote --tags --refs origin` 을 채택한다.** 결정 근거는 "같은 경로" 성질이다 —
알림이 뜨는 머신에서는 `/harness-update` 의 fetch 도 된다. `git fetch` 는 사용자 저장소의 ref 를
바꾸므로 기각, raw HTTPS·API 는 `origin` 을 따라가지 못하고(포크·미러) 새 네트워크 상대를 늘리므로 기각.

실행 세부:
- argv 리스트, 셸 없음(rules/python/security.md) · `stdin=DEVNULL` · 환경에 `GIT_TERMINAL_PROMPT=0`
  추가 · `start_new_session=True` · 타임아웃 15초, 넘으면 프로세스 그룹째 종료(git 이 띄운 ssh 자식이
  남지 않게) · stdout 상한 256KiB(읽은 뒤에 거르는 입력 상한이지 메모리 상한이 아니다 — 원격은 사용자 저장소의 origin 이라
  `/harness-update` 와 같은 신뢰 수준이고 실질 상한은 15초 시간 제한이다, 2회차 검수 Minor).
- 출력 파싱: `^[0-9a-f]{40,64}\trefs/tags/v(X.Y.Z)$` 줄만 채택(sha256 저장소 대비 64자), 나머지는
  무시. 숫자 튜플로 최댓값.
- 신뢰 경계: `repo_path` 의 `.git/config`(예: `core.sshCommand`, `ext::` 원격)가 실행된다 — 사용자가
  `/harness-update` 로 이미 fetch 를 돌리는 저장소와 같은 신뢰 수준이다. 새 신뢰를 들이지 않는다.

**UN2 — 확인 주기와 캐시.** 서버의 전용 데몬 스레드(사용량 API 폴링과 같은 이유 — 최악 15초 블로킹을
하트비트 티커에 태우지 않는다, 결정 AR5 선례)가 6시간마다 1회 확인하고 결과를
`~/.claude/hub/release_check.json` 에 원자적으로 쓴다. 마지막 시도 시각을 이 파일에 남겨 서버를 자주
재시작해도 6시간에 한 번을 넘지 않는다. 실패해도 직전 성공의 `latest_version` 을 지우지 않는다(결정 A7
선례 — 실패가 정상 값을 덮지 않는다). 실패는 화면 경고를 띄우지 않고 `/hub status` 에서만 보인다
(사용량 API 폴링과 같은 처리).
- 서버가 꺼져 있으면 확인하지 않는다(`/hub` 의 1회 수집 경로는 네트워크를 쓰지 않는다).
- `/harness-update` 직후에는 새 확인이 필요 없다 — 비교는 **수집 시점**에 "설치 기록(매번 새로 읽음)
  vs 캐시된 최신 버전"으로 하므로 업데이트가 끝나면 다음 수집에서 알림이 사라진다.

**UN3 — 비교 규칙.** `is_update_available = latest 가 있고 (installed 가 없거나 latest > installed)`.
설치 기록에 버전이 없는(도입 이전) 설치는 어떤 릴리스보다 오래된 것으로 본다. `installed > latest`
(관리자가 태그 푸시 전에 설치)는 알림 없음.

**UN4 — 스위치.** `config.json` 의 `update_check_enabled`(기본값은 D5). 꺼지면 스레드를 띄우지 않고,
수집도 캐시 파일을 무시한다(옛 캐시로 알림이 남지 않게). 설치 버전 표기(`v1.0.0`)는 로컬 정보라
스위치와 무관하게 보인다. 주기는 상수다(설정 키로 만들지 않는다 — YAGNI).

### 5.4 버튼이 하는 일 — 안 1 vs 안 2

| 항목 | 안 1 — 알림 + 명령 복사 (권고) | 안 2 — 허브에서 직접 업데이트 |
|------|------|------|
| 서버 변경 | 없음(GET 전용 유지) | POST 엔드포인트 + 작업 실행기 + 상태 조회 |
| `file://` 로 연 허브 | 그대로 동작(복사는 브라우저 기능) | 서버가 없어 동작 불가 — 버튼을 숨기는 두 번째 화면 분기 |
| 충돌(`exit 1` → `--force`) | `/harness-update` 가 대화로 묻는다(지금과 같음) | 버튼 UI 가 파일 목록·덮어쓰기 확인을 다시 만들어야 한다. `hub/install.sh` 충돌은 지금 **LLM 이 파일 내용을 보고** 판단한다 — 버튼은 그 판단을 대신할 수 없다 |
| 업데이트 절차의 정본 | `commands/harness-update.md` 하나 | 마크다운 명세 + 파이썬 재구현 두 벌 — 갈라진다(분기 상황: 갈라진 브랜치·추적 브랜치 없음·더러운 작업 트리·project scope…) |
| 허브 문서화 범위 | "읽기 전용, 명령·제어 범위 밖" 유지 | 그 선언을 뒤집는 결정 필요 |
| 보안 검수 | 일반 | 민감 변경(opus 검수 승격 대상) |
| 대략 비용(코드+테스트) | 600~800줄 | 안 1 + 1,300줄 이상 |

안 2 의 필수 검토 4항목:

1. **CSRF·DNS 리바인딩.** 사용자가 아무 웹사이트를 열어 둔 상태에서 그 페이지의 스크립트가
   `fetch('http://127.0.0.1:8794/…', {method:'POST', mode:'no-cors'})` 로 "단순 요청"을 보내면 사전
   확인(preflight) 없이 도착한다 — 지금은 GET 전용이라 최악이 정보 노출이지만, 안 2 에서는 **원격 웹
   페이지가 업데이트·서버 재시작을 일으킬 수 있다**. 막으려면 (a) 단순 요청이 될 수 없는 사용자 정의
   헤더 요구 (b) `Host` 가 `127.0.0.1:8794`·`localhost:8794` 인지 검사(DNS 리바인딩) (c) `Origin` 검사
   (d) 서버 기동마다 만든 토큰 — 단 토큰은 `hub.html` 에 실리고 `hub.html` 은 로컬 프로세스가 읽을 수
   있다. 브라우저의 사설망 접근 제한(Private Network Access)은 브라우저마다 달라 기댈 수 없다.
   지금의 GET 전용 성질은 **깨진다** — 위 방어를 전부 해도 "상태를 바꾸는 표면이 없다"에서 "방어로
   막는 표면이 있다"로 바뀐다.
2. **자기 재설치·재시작.** 서버가 `hub/install.sh` 를 돌리면 자기가 실행 중인 `bin/*.py` 를 갈아
   끼운다(이미 올라간 모듈과 새 파일이 섞일 수 있다). 끝나면 자신을 멈추고 새 코드로 다시 떠야 하므로
   분리된 도우미 프로세스(setsid)가 "옛 서버 종료 대기 → 재설치 → `server-start`"를 맡아야 하고,
   버튼을 누른 요청은 중간에 끊긴다. 화면은 연결 끊김 상태를 견디다 `template_stamp` 자가 리로드
   (결정 SH6~SH9)로 돌아와야 한다 — 일부는 재사용되지만 서버 신원 기록(`hub-server-identity.md` D2)과
   경로 판정까지 함께 맞춰야 한다.
3. **`install.sh` 충돌 처리.** 루트 `install.sh` 의 `exit 1` 은 "대장과 다른, 사용자가 고친 것으로
   의심되는 파일"이다. 버튼은 (i) 항상 거기서 멈추고 "`/harness-update` 를 쓰세요"로 보내거나
   (ii) 목록을 보여 주고 `--force` 2차 요청을 받거나 해야 한다. (i)이면 결국 안 1 로 수렴하고,
   (ii)이면 `hub/install.sh` 쪽의 "의도적 수정인가" 판단(지금은 LLM 이 내용을 보고 한다)을 대체할
   수 없다.
4. **「`/harness-update` 는 사용자만 호출」과의 관계.** 버튼 클릭은 사용자 행위이므로 문자 그대로는
   어기지 않는다. 그러나 그 원칙이 지키는 것은 "업데이트가 사람이 보는 대화 안에서 일어나고, 유일한
   질문(`--force`)에 사람이 답한다"는 성질이다. 안 2 는 같은 일을 그 대화 밖에서 하는 두 번째 경로를
   만든다. 안 1 은 그 원칙을 그대로 따른다 — 버튼은 사용자가 명령을 입력하도록 돕기만 한다.

**UN5 — 안 1 을 권고한다.** 안 2 를 다시 꺼낼 조건: `/harness-update` 에 대화 없이 끝나는 모드가
생기고(충돌 시 항상 멈춤), 허브 범위를 "제어 포함"으로 바꾸는 결정이 따로 내려질 때.

### 5.5 권고안(안 1) 설계

#### 5.5.1 결정

- **UN7 — 화면.** `h1` 오른쪽에 설치 버전 `v1.0.0`(작은 고정폭, `--muted`, 툴팁: 버전·짧은 해시·설치
  날짜), `.top-actions` 맨 앞에 알림 버튼 `새 버전 1.1.0`(32px 알약, `--accent-soft` 면·`--accent-ink`
  글자, 새 색 토큰 0, 대비 라이트 5.9:1·다크 7.5:1). 누르면 `/harness-update` 를 클립보드에 넣고
  2초간 「복사됨 · /harness-update」, 클립보드가 거부되면 「/harness-update 를 입력하세요」. 툴팁:
  `설치된 버전 1.0.0 → 최신 1.1.0` + 사용법 한 줄. 설치 기록이 없으면 둘 다 숨는다(= 지금 화면).
- **UN8 — 갱신 불변식(H1⁗) 개정.** 폴링이 갱신하는 노드 목록에 `#dzh-harness-version`(hidden·
  textContent·data-tooltip)과 `#dzh-update`(hidden·data-tooltip·aria-label·`.update-label`
  textContent)를 **속성·textContent 단위로** 더한다. 노드는 정적 마크업이고 교체하지 않는다
  (`#dzh-refresh` 의 data-tooltip 갱신이 선례). 복사 피드백 상태는 사용자 상태라 렌더 대상 밖이다 —
  별도 IIFE 가 `.update-btn-copied`·`.update-btn-copy-failed` 클래스만 만지고, 렌더 IIFE 는 그 두
  클래스를 건드리지 않는다. 라벨 3종은 마크업에 함께 두고 CSS 가 하나만 보인다(같은 노드의 글자를 두
  IIFE 가 나눠 쓰지 않는다).
- **UN9 — 복사 IIFE 의 등록 위치.** 스냅샷을 몰라도 되는 상수 문자열 복사라 새로고침 회전 IIFE 처럼
  렌더 IIFE 바깥의 독립 IIFE 로 둔다 — 렌더 IIFE 안의 `if(!isServed){ … return; }` 뒤에 두면 `file://`
  모드에서 조용히 죽는다(GOTCHA 4 선례).
- **UN10 — 공개 문서.** hub/README.md 보안·프라이버시 절에 "서버가 켜져 있으면 6시간마다
  coding-harness 저장소 폴더에서 `git ls-remote --tags origin` 을 실행한다 — 보내는 것은 git 이
  원격에 하는 일반 요청뿐, 끄는 수단 `update_check_enabled:false`"를 더한다. 설정 표·파일 트리
  (`release_check.json`)·`/hub status` 필드 설명도 갱신한다.

#### 5.5.2 파일 구조와 모듈 경계

허브 레이어 관례(★순수 모듈 + I/O 위성 모듈, 데이터클래스 계약)를 따른다. `hub_collect.py` 는
790/800줄이라 읽기 로직을 넣지 않고 호출 1줄만 더한다.

| 파일 | 종류 | 변경 |
|------|------|------|
| `hub/bin/hub_release.py` (신규) | ★순수 · 잎 모듈(허브 모듈 임포트 없음) | SemVer 파싱·`ls-remote` 출력 파싱·비교·게이트·뷰 조립·기록 갱신 |
| `hub/bin/hub_release_read.py` (신규) | I/O | 설치 기록 읽기 · `release_check.json` 읽기/쓰기(`hub_atomic_write`) · `git ls-remote` 실행 · 서버 1사이클. 경로 상수는 이 모듈이 갖는다(`hub_collect` 를 임포트하지 않는다 — 순환 방지) |
| `hub/bin/hub_model.py` | 순수 | `HubConfig.update_check_enabled` · `HubSnapshot.harness_version` |
| `hub/bin/hub_config.py` | 순수 | 스키마에 `update_check_enabled: bool` |
| `hub/bin/hub_collect.py` | I/O | `collect_snapshot` 에서 뷰 읽기 1회·경고 합치기. 함수가 이미 50줄이라 넘치면 기존 관례(보조 함수로 묶기, 재검수 M4)를 따른다 |
| `hub/bin/hub_server.py` | I/O | `_release_check_loop` 스레드(스위치가 켜졌을 때만 기동) |
| `hub/bin/hub.py` | I/O | `cmd_status` 에 `release_check` 필드 1개 |
| `hub/bin/hub_template.html` | UI | 마크업 2곳 · CSS 약 15줄 · 렌더 함수 1개 · 복사 IIFE 1개 · 데이터 계약 주석(H1⁗) |
| `hub/install.sh` | 배포 | `HUB_FILE_COUNT` 33 → 35 |
| `hub/README.md` · `commands/hub.md` | 문서 | UN10 · `/hub status` 표 |
| `tests/hub/test_hub_release.py` · `test_hub_release_read.py` (신규) | 테스트 | §5.5.6 |
| `tests/run.sh` · `tests/mutations.tsv` | 테스트 | T25 새 서브체크(문서·상수·순수 목록 T25-10 편입·argv 검사) + 원장 행 |

순환 의존 없음: `hub_release`(잎) ← `hub_model`·`hub_release_read` ← `hub_collect`·`hub_server`·`hub`.

#### 5.5.3 데이터 모델 (B)

```python
# hub_release.py (★순수)
SemVer = tuple[int, int, int]

ReleaseCheckFailure = Literal[
    "no_install_record",   # ~/.claude/.coding-harness.json 없음·repo_path 없음
    "repo_missing",        # repo_path 가 디렉터리가 아님
    "git_unavailable",     # git 실행 파일 없음
    "timeout",             # 15초 초과(프로세스 그룹 종료)
    "remote_error",        # 종료 코드 ≠ 0 (원격 없음·인증·네트워크·SSH 키 없음 포함)
    "output_too_large",    # stdout 상한 초과
    "parse_error",         # 출력 해석 중 ValueError(자릿수 상한이 막는 값 — 방어선, 2회차 검수 Major)
]

@dataclass(frozen=True)
class InstalledHarness:
    """user scope 설치 기록에서 꺼낸 값. 설치 기록과 맺은 계약."""
    harness_version: str | None     # 필드 없음·"unknown" → None
    installed_from_commit: str      # 40/64 hex 또는 "unknown"
    installed_at: str               # ISO 8601 그대로
    repo_path: str

@dataclass(frozen=True)
class ReleaseCheckRecord:
    """~/.claude/hub/release_check.json 과 맺은 계약. 서버 스레드만 쓴다."""
    last_attempt_at_ms: int
    last_success_at_ms: int | None
    latest_version: str | None              # 마지막 성공에서 본 최신 릴리스. 실패가 지우지 않는다
    last_failure_reason: str | None         # ReleaseCheckFailure. 성공하면 None

@dataclass(frozen=True)
class HarnessVersionView:
    """hub.html #dzh-data 의 harness_version. 템플릿과 맺은 계약."""
    installed_version: str          # "1.0.0" · 모르면 ""
    installed_commit_short: str     # 7자 · 모르면 ""
    installed_at: str
    latest_version: str             # 모르면 ""(미확인·실패·스위치 꺼짐)
    is_update_available: bool
```

`HubSnapshot.harness_version: HarnessVersionView | None = None` — 설치 기록이 없으면 `None`(템플릿은
두 노드를 숨긴다). `HubConfig.update_check_enabled: bool`(기본값 D5).

`release_check.json` 예:

```json
{"last_attempt_at_ms": 1791000000000, "last_success_at_ms": 1791000000000,
 "latest_version": "1.1.0", "last_failure_reason": null}
```

#### 5.5.4 인터페이스 (B)

```python
# hub_release.py — ★순수
RELEASE_CHECK_INTERVAL_MS: int        # 6시간
def parse_semver(text: str) -> SemVer | None:
    """'X.Y.Z' 만 받는다(앞자리 0·접두 v·프리릴리스 거부)."""
def latest_release_version(ls_remote_stdout: str) -> str | None:
    """`ls-remote --tags --refs` 출력에서 vX.Y.Z 태그의 최댓값을 'X.Y.Z' 로 돌려준다."""
def should_attempt_release_check(now_ms: int, last_attempt_at_ms: int | None, interval_ms: int) -> bool:
    """기록 없음·주기 경과·벽시계 역행(now < last)이면 참."""
def next_release_check_record(previous: ReleaseCheckRecord | None, now_ms: int,
                              latest_version: str | None, failure: str | None) -> ReleaseCheckRecord:
    """실패면 직전 latest_version 을 보존하고, 성공이면 갱신·실패 사유를 지운다."""
def build_harness_version_view(installed: InstalledHarness | None,
                               record: ReleaseCheckRecord | None) -> HarnessVersionView | None:
    """설치 기록이 없으면 None. record 가 None 이면(스위치 꺼짐 포함) 알림 없음."""

# hub_release_read.py — I/O
INSTALL_RECORD_PATH: Path             # ~/.claude/.coding-harness.json
RELEASE_CHECK_PATH: Path              # ~/.claude/hub/release_check.json
GIT_LS_REMOTE_TIMEOUT_SECONDS = 15
GIT_LS_REMOTE_MAX_OUTPUT_BYTES = 256 * 1024
def read_installed_harness() -> tuple[InstalledHarness | None, tuple[str, ...]]:
    """없으면 (None, ()), 깨졌으면 (None, (경고,))."""
def read_release_check_record() -> ReleaseCheckRecord | None:
    """없거나 깨졌으면 None."""
def write_release_check_record(record: ReleaseCheckRecord) -> None:
    """원자적 쓰기. OSError 는 호출측이 받는다."""
def fetch_latest_release_version(repo_path: str) -> tuple[str | None, str | None]:
    """(최신 버전 | None, 실패 사유 | None). 태그가 하나도 없으면 (None, None)."""
def run_release_check_cycle(now_ms: int) -> ReleaseCheckRecord:
    """설치 기록 → ls-remote → 기록 쓰기 1회. 예외를 올리지 않고 결과 기록을 돌려준다."""
def read_harness_version_view(config: HubConfig) -> tuple[HarnessVersionView | None, tuple[str, ...]]:
    """수집용. 스위치가 꺼지면 캐시를 읽지 않는다."""

# hub_server.py
def _release_check_loop(config: hub_model.HubConfig, stop_event: threading.Event) -> None:
    """전용 데몬 스레드. 하트비트 주기로 깨어 게이트를 보고, 최종 방어선은 stderr 만(AR4·AR5 선례)."""
```

템플릿(JS):

```text
renderHarnessVersion(view)       // render() 안, renderConnectionStatus() 옆에서 호출
UPDATE_COMMAND_TEXT = '/harness-update'
UPDATE_COPY_FEEDBACK_MS = 2000   // 복사 피드백 표시 시간(독립 IIFE)
```

#### 5.5.5 화면 — 목업

`harness-versioning-mock.html`(최종 보고의 절대 경로). 행: 최신 설치됨 / 새 버전 있음 / hover+툴팁 /
누른 뒤 / 실패(안 1: 클립보드 거부, 안 2: 충돌). 열: 현재 | 안 1 | 안 2. 라이트·다크, 폭 640px·최소
360px. 마크업·클래스는 구현 이름 그대로이고 기존 CSS 는 `hub_template.html` 에서 문자 그대로 옮겼다.

목업에서 드러난 점: 최소 폭 360px 에서는 버전 표기(`v1.0.0`)만으로도 헤더가 두 줄로 접힌다(지금은
한 줄). `.head-row` 는 이미 `flex-wrap` 으로 그 접힘을 허용하도록 설계돼 있어 깨지지는 않는다 —
권고는 수용. 대안(좁은 폭에서 표기 숨김)은 템플릿의 브레이크포인트 단일 출처 규칙(GOTCHA 2)을 건드려
채택하지 않는다.

#### 5.5.6 테스트 계획 (B)

`tests/hub` (stdlib unittest):

| 대상 | 케이스 |
|------|--------|
| `parse_semver` | `1.2.3` 통과 · `1.2` · `01.2.3` · `v1.2.3` · `1.2.3-rc.1` · ` 1.2.3` · 빈 문자열 거부 |
| `latest_release_version` | `v1.10.0` > `v1.9.0`(숫자 비교) · 형식 밖 태그(`v1.0`·`release-1`·`v1.0.0^{}`) 무시 · 해시가 40/64 hex 가 아닌 줄 무시 · 빈 출력 → None |
| `should_attempt_release_check` | 기록 없음 → 참 · 주기 안 → 거짓 · 경계값 · 벽시계 역행 → 참 |
| `next_release_check_record` | 실패가 직전 `latest_version` 보존 · 성공이 실패 사유 지움 · 첫 실패(직전 없음) |
| `build_harness_version_view` | 1.0.0 vs 1.1.0 → 알림 · 같음 → 없음 · 설치 > 최신 → 없음 · 설치 버전 없음(옛 설치) + 최신 있음 → 알림 · 최신 없음 → 없음 · record None(스위치 꺼짐) → 표기만 · 설치 기록 None → None |
| `read_installed_harness` | 임시 HOME: 파일 없음 → (None, ()) · JSON 깨짐 → 경고 · `harness_version` 없음/`unknown` → None · 정상 |
| `fetch_latest_release_version` | **로컬 bare 저장소에 태그 3개를 푸시하고 `origin` 으로 건 실제 git 실행**(네트워크 없음, 결정적) → `1.1.0` · `subprocess` 모킹으로 argv 리스트·`GIT_TERMINAL_PROMPT=0`·`stdin=DEVNULL`·타임아웃 인자 확인 · `TimeoutExpired` → `timeout` · `FileNotFoundError` → `git_unavailable` · 종료 코드 128 → `remote_error` · 디렉터리 아님 → `repo_missing` |
| 기록 왕복 | 쓰기→읽기 동일 · 깨진 파일 → None |
| 서버 | 스위치 꺼짐이면 스레드 미기동 · 사이클 예외가 루프를 죽이지 않음(기존 `_usage_api_poll_loop` 테스트 관례) |
| 템플릿 DOM(`template_dom_harness`) | 뷰 있음+알림 → `#dzh-update` 보임·라벨 · 알림 없음 → 숨김 · `None` → 둘 다 숨김 · 폴링 재렌더가 `.update-btn-copied` 를 지우지 않음 |

`tests/run.sh` T25 새 서브체크: `HUB_FILE_COUNT` 일치(기존 T25-1 이 자동으로 잡음) · `hub_release.py`
를 순수 목록(T25-10)에 편입 · `subprocess` 호출이 리스트 인자·`shell=True` 없음(T25-61 과 같은 형태) ·
README 의 `update_check_enabled`·`release_check.json`·네트워크 고지 토큰 · 데이터 계약 주석에
`#dzh-update` 등재 · 복사 IIFE 가 `if(!isServed)` 뒤에 있지 않음. 각 서브체크는 원장 행을 갖는다.

DOM 테스트는 동시 부하에 약하다(사용자 메모리) — 구현자는 단독 실행으로 확인한다.

---

## 6. 하지 않는 것 (YAGNI)

| 하지 않는 것 | 이유 | 다시 꺼낼 조건 |
|------|------|------|
| GitHub 릴리스 페이지 · `CHANGELOG.md` | 변경 목록은 `/harness-update` 가 git log 로 이미 보여 준다 | 팀원이 릴리스 노트를 요청할 때 |
| 프리릴리스·빌드 메타(`-rc.1`, `+sha`) | 채널이 하나다 | 시험 채널이 필요할 때 |
| 태그로 체크아웃하는 안정 채널(`/harness-update` 가 main 대신 최신 태그를 받기) | 업데이트 의미가 바뀌는 큰 변경. 지금은 main 이 곧 배포다 | 릴리스 사이 main 이 자주 깨질 때 |
| `install.sh --version` | `cat VERSION` 으로 충분, `--scope` 필수 규칙에 예외를 만든다 | — |
| `/harness-release` 커맨드 | 관리자 한 명만 쓰는데 배포 커맨드는 팀 전원에게 깔린다 | 릴리스하는 사람이 여럿일 때 |
| 커밋 훅으로 버전 올림 강제 | 릴리스 커밋을 기계가 판별 못 함, 훅은 배포 자산이 아님 | — |
| 설치 기록 스키마 v4 | 하위 호환 추가로 충분(HV6) | 읽는 쪽이 반드시 알아야 할 의미 변경이 생길 때 |
| 허브 자체 버전 파일 | UN6 | UN6 의 조건 |
| 새 커밋마다 알림 · 자동 업데이트 | 해석 메모 · UN5 | 사용자가 다른 해석을 택할 때 |

## 7. 리스크와 대안

### 7.1 리스크

| # | 리스크 | 대응 |
|---|------|------|
| R1 | 릴리스 때 태그 푸시를 잊으면 알림이 영영 안 뜬다 | §3.2 절차 5단계 · T41-6 은 로컬 태그와 `VERSION` 불일치만 잡는다(푸시 누락은 못 잡는다 — 수용) |
| R2 | 릴리스 사이 main 설치본의 버전 표기가 내용보다 오래돼 보인다 | 모든 표기에 짧은 해시를 함께(HV4) |
| R3 | 원격 확인이 허브의 첫 기본 켜짐 네트워크 호출이다(IP·사용 사실이 원격에 보인다) | D5 로 사용자가 정한다 · README 고지 · 스위치 · `git fetch` 와 같은 상대·같은 종류의 요청 |
| R4 | `repo_path` 의 git 설정이 실행된다 | `/harness-update` 와 같은 신뢰 수준 — 새 신뢰 없음(UN1) |
| R5 | SSH 원격 + 에이전트 없음 → 항상 `remote_error`, 알림이 조용히 없다 | `/hub status` 에 사유가 보인다 · 수용 |
| R6 | 사내 프록시·방화벽에서 6시간마다 15초 타임아웃 | 전용 스레드라 하트비트·수집에 영향 없음 · 그 머신에서는 `/harness-update` 도 같은 이유로 실패한다 |
| R7 | 360px 에서 헤더 두 줄 | 수용(§5.5.5) |
| R8 | `hub_collect.py` 790/800줄 · `collect_snapshot` 50줄 | 읽기 로직은 새 I/O 모듈, 호출만 1줄 · 넘치면 보조 함수(선례 M4) |
| R9 | `/harness-update` 문서 수정이 T22 의 기존 문구 검사를 깰 수 있다 | §3.5 의 "건드리지 않는다" 목록 · 구현자가 T22 를 단독 실행 |
| R10 | 클립보드 API 가 `http://127.0.0.1`·`file://` 에서 브라우저마다 다르게 동작할 수 있다 | 실패 라벨(「/harness-update 를 입력하세요」)과 툴팁에 명령이 항상 적혀 있다 · 구현 단계 측정 과제 |

**발견(범위 밖, 언급만)**: 지금 서버는 `Host` 헤더를 검사하지 않는다(`hub_server.py` `do_GET` 은
경로만 본다). 그래서 DNS 리바인딩으로 브라우저 안의 원격 페이지가 `hub.html`(프롬프트 발췌·계정
이메일)을 읽을 수 있는 여지가 있다. hub/README.md 는 "로컬의 다른 프로세스"만 노출 주체로 적는다.
안 1 은 이 상태를 바꾸지 않는다. 별도 과제로 다룰지 사용자가 정할 일이다.

### 7.2 검토했으나 채택하지 않은 대안

- **태그만 정본(D1-다)** — `.git` 없는 사본·태그 없는 clone 에서 설치 버전이 사라지고, 형식 검사를
  기계가 할 자리가 없다.
- **커밋마다 올림(D1-나)** — 동시 세션 병합 충돌, 문서 커밋 알림 남발.
- **raw `VERSION` HTTPS · GitHub API · `git fetch`** — §5.3.
- **안 2(허브에서 직접 업데이트)** — §5.4.

## 8. 구현 단계 측정 과제 (설계에서 재지 않았다)

1. 클립보드 쓰기의 실제 동작: `http://127.0.0.1:8794` 와 `file://` 에서 Chrome·Safari 각각.
2. 팀 네트워크(사내망·프록시)에서 `git ls-remote --tags --refs origin` 1회의 소요·성공 여부.
3. 실제 템플릿에 얹은 뒤 360px·640px·1440px 스크린샷(목업이 아니라 실데이터 `hub.html`).
4. `CLAUDE.md` 1줄 추가 후 T26 실측 바이트(상수 갱신값).

## 9. 구현 순서와 검증

```
A1. VERSION + install.sh(read_harness_version · build_manifest_json · 로그 줄)
    → 검증: bash -n install.sh · T41-1~5 · T20·T21·T27
A2. harness-update.md · README · CLAUDE.md
    → 검증: T41-7 · T22 · T26(상수 갱신)
A3. 원장 행 · 상수 → 검증: T37 · 메인 세션의 전체 bash tests/run.sh
A4. (사용자 확인) 태그 v1.0.0 생성·푸시 — B 를 함께 하면 B 뒤로
B1. hub_release.py(순수) + 단위 테스트 → python3 -m unittest tests.hub.test_hub_release
B2. hub_release_read.py + 로컬 bare 저장소 테스트
B3. hub_model·hub_config·hub_collect·hub_server·hub.py 배선 → tests/hub 전체 · py_compile
B4. 템플릿(마크업·CSS·렌더·복사 IIFE·H1⁗ 주석) + DOM 테스트(단독 실행)
B5. hub/install.sh 파일 수 · README·commands/hub.md · T25 서브체크·원장 → T24·T25·T37
```
