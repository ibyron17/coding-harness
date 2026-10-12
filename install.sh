#!/bin/bash
# coding-harness 배포 스크립트.
# rules/ + agents/ + commands/ 를 프로젝트 디렉토리 또는 사용자 홈에 설치한다.
# ~/.claude/CLAUDE.md(이전 버전이 배포하던 범용 지침)는 더 이상 배포하지 않고, user scope
# 설치 시 안전하게 은퇴시킨다(§retire_user_claude_md — 판정 불가는 보호, 삭제하지 않음).
#
# 소유권 원칙: 이 스크립트는 레포가 배포하는 파일만 관리한다.
# 대상 디렉토리에만 존재하는 파일(사용자의 다른 에이전트·커맨드·규칙 등)은
# 충돌로 보지 않고 삭제하지도 않는다.
# 예외 — __pycache__(3회차 검수 Major 1): 파이썬이 기계적으로 재생성하는 바이트코드
# 캐시는 위 소유권 판단 대상이 아니다. 관리 디렉토리(rules/agents/commands) 안에서
# 발견되면 이번 설치가 만들었는지와 무관하게, 그리고 .py 원본이 이미 사라진 고아
# 캐시여도 매 실행마다 무조건 지운다 — 상세는 §remove_pycache_from_target_directory.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
readonly REPO_ROOT
readonly RULES_FILE_COUNT=46
readonly AGENTS_FILE_COUNT=4
readonly COMMANDS_FILE_COUNT=8
readonly MAX_DIFF_LINES=20
readonly MANIFEST_FILE_NAME=".coding-harness.json"
readonly MANIFEST_VERSION=3
# ~/.claude/CLAUDE.md 은퇴 판정 상수 — 매직 문자열 금지. user scope 전용(project scope 는
# CLAUDE.md 를 아예 모른다). 개명 접미사는 덮어쓰기 전 백업(.bak-)과 의미가 달라 구분한다 —
# 은퇴는 덮어쓸 본체가 없는 1회성 마이그레이션이다.
readonly RETIRED_BACKUP_SUFFIX_FORMAT="retired-%Y%m%d-%H%M%S"
# H5(PRP shell-hardening §9-5): --force 로 modified 파일을 덮어쓰기 전 형제 위치에 남기는
# 백업 접미사. 위 주석이 이미 "덮어쓰기 전 백업(.bak-)"을 이 저장소의 관례로 지목했다 —
# 이 저장소의 다른 런타임에도 같은 형태의 타임스탬프 백업 관례가 있다(설치 분리 원칙상
# 이 파일은 그 모듈명을 알지 못한다, 요구 R-5).
readonly FORCE_OVERWRITE_BACKUP_SUFFIX_FORMAT="bak-%Y%m%d-%H%M%S"
readonly LEGACY_CLAUDE_MD_TITLE_SENTINEL='# 전역 개발 지침 (~/.claude/CLAUDE.md)'
readonly LEGACY_CLAUDE_MD_BODY_SENTINEL='서브에이전트 위임은 사용자가 상시 요청한 것이다'
# 툼스톤 목록. 테스트 시임 — 대부분의 삭제 시나리오 테스트는 레포의 실제 removals.txt
# 내용과 무관하게 CODING_HARNESS_REMOVALS_FILE 로 임시 목록을 주입한다(HOME 치환과 같은 성격).
readonly REMOVALS_FILE="${CODING_HARNESS_REMOVALS_FILE:-$REPO_ROOT/removals.txt}"

scope=""
force_overwrite="false"
dry_run="false"
target_base_dir=""
retired_claude_md_path=""
target_rules_dir=""
target_agents_dir=""
target_commands_dir=""
target_manifest_path=""

log_info() { echo "[INFO] $*"; }
log_warn() { echo "[WARN] $*" >&2; }
log_ok() { echo "[OK]   $*"; }
log_error() { echo "[ERROR] $*" >&2; }
log_done() { echo "[DONE] $*"; }
log_plan() { echo "  [계획] $*"; }
log_protected() { echo "  [보호] $*"; }

usage() {
  cat << 'EOF'
Usage: install.sh --scope project|user [--force] [--dry-run] [--help]

Options:
  --scope project      현재 디렉토리($PWD)에 설치
  --scope user         $HOME/.claude/ 에 설치
  --force              수정된 rules/agents/commands 강제 덮어쓰기
  --dry-run            계획만 출력 (파일시스템 변경 없음)
  --help               이 메시지 표시
EOF
}

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --scope)
        if [[ $# -lt 2 ]]; then
          log_error "--scope 에 값이 없습니다"
          usage
          exit 1
        fi
        scope="$2"
        shift 2
        ;;
      --force) force_overwrite="true"; shift ;;
      --dry-run) dry_run="true"; shift ;;
      --help) usage; exit 0 ;;
      *) log_error "알 수 없는 옵션: $1"; usage; exit 1 ;;
    esac
  done

  if [[ "$scope" != "project" && "$scope" != "user" ]]; then
    log_error "--scope project 또는 --scope user 를 지정하십시오"
    usage
    exit 1
  fi
}

# 심볼릭 링크 판정. macOS 의 /var → /private/var 시스템 링크는 정상으로 취급한다.
is_symlinked_path() {
  local candidate_path="$1"
  local resolved_path
  resolved_path=$(cd "$candidate_path" > /dev/null 2>&1 && /bin/pwd -P) || return 1
  if [[ "$candidate_path" == "$resolved_path" || "$candidate_path" == "${resolved_path#/private}" ]]; then
    return 1
  fi
  return 0
}

# H4(PRP shell-hardening §9-4): --scope project 인데 $PWD 가 $HOME 과 실경로로 같으면
# 거부한다. $HOME 하위(예: ~/projects/foo)는 정상 프로젝트이므로 거부 대상이 아니다 —
# 정확히 같을 때만. 비교는 실경로로 한다(/bin/pwd -P) — 문자열 비교만 하면 macOS 의
# /var → /private/var 나 심링크된 $HOME 에서 빗나간다(is_symlinked_path 와 같은 관용구).
# ${HOME:-} 로 읽는 이유(GOTCHA 7): project 경로는 지금까지 $HOME 을 참조하지 않았고,
# set -u 아래에서 미설정 $HOME 을 그대로 참조하면 스크립트가 죽는다 — $HOME 이 없으면
# $PWD 가 그것과 같을 수 없으므로 그 경우는 검사를 건너뛴다.
reject_project_scope_at_home() {
  [[ -n "${HOME:-}" ]] || return 0

  local resolved_home
  resolved_home=$(cd "$HOME" > /dev/null 2>&1 && /bin/pwd -P) || resolved_home=""
  [[ -n "$resolved_home" ]] || return 0

  if [[ "$(/bin/pwd -P)" == "$resolved_home" ]]; then
    log_error "현재 디렉토리가 \$HOME 과 같습니다 — --scope user 를 쓰십시오"
    return 1
  fi
  return 0
}

resolve_target_paths() {
  if [[ "$scope" == "project" ]]; then
    target_base_dir="$PWD"
    if ! reject_project_scope_at_home; then
      return 1
    fi
  else
    target_base_dir="$HOME"
    retired_claude_md_path="$HOME/.claude/CLAUDE.md"
  fi
  target_rules_dir="$target_base_dir/.claude/rules"
  target_agents_dir="$target_base_dir/.claude/agents"
  target_commands_dir="$target_base_dir/.claude/commands"
  target_manifest_path="$target_base_dir/.claude/$MANIFEST_FILE_NAME"

  if is_symlinked_path "$target_base_dir"; then
    log_error "심볼릭 링크입니다: $target_base_dir"
    return 1
  fi
}

compute_sha256() {
  if command -v sha256sum &> /dev/null; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

count_lines() {
  grep -c . || true
}

# 대상에 없는, 우리가 배포하는 파일 목록 (복원 대상)
# -x __pycache__: __pycache__ 는 실행 시점마다 바뀔 수 있는 바이트코드 파생물이라 비교·설치
# 대상이 아니다 — cp -R 가 옮겨도 remove_pycache_from_target_directory 가 곧바로 지워
# 최종적으로는 배포되지 않는 것과 판정 기준을 맞춘다(3회차 검수 Minor 3 — "배포하지 않는다"가
# 아니라 "복사 후 곧바로 지운다"가 정확한 기제다). 맞추지 않으면 소스에만 존재하는 __pycache__
# 가 항상 "missing"으로 잡혀 verify_managed_files_installed 를 상시 실패시킨다.
#
# H1(PRP shell-hardening §9-1): diff 는 같음(0)·차이 있음(1)·오류(2 이상)를 다른 코드로
# 구분한다. 출력과 상태를 함께 잡아(2>&1) 상태 2 이상만 실패로 본다 — 상태 1(차이 있음)을
# 실패로 오분류하면 차이가 있는 모든 정상 설치가 막힌다(GOTCHA 1). `diff_output=$(...) ||
# diff_status=$?` 형태를 쓰는 이유(GOTCHA 2, karpathy-guidelines 「실패 사례」와 같은 계열):
# 이 조합이 아니면 set -e 가 diff 실패에서 함수를 통째로 끊어 아래 필터링에 도달하지 못한다.
list_missing_managed_files() {
  local source_directory="$1"
  local target_directory="$2"
  local diff_output diff_status=0
  diff_output=$(diff -rq -x __pycache__ "$source_directory" "$target_directory" 2>&1) \
    || diff_status=$?
  if ((diff_status >= 2)); then
    log_error "diff 검사 실패($source_directory ↔ $target_directory) — 설치 상태를 신뢰할 수 없어 중단합니다"
    log_error "$diff_output"
    return 1
  fi

  local diff_line
  while IFS= read -r diff_line; do
    case "$diff_line" in
      "Only in $source_directory"*) printf '%s\n' "$diff_line" ;;
    esac
  done <<< "$diff_output"
}

# 대상에 있으나 내용이 다른, 우리가 배포하는 파일 목록 (사용자 수정 의심 → --force 필요)
# __pycache__ 배제 이유는 list_missing_managed_files 주석과 동일. diff 실패 처리(H1)도 동일.
list_differing_managed_files() {
  local source_directory="$1"
  local target_directory="$2"
  local diff_output diff_status=0
  diff_output=$(diff -rq -x __pycache__ "$source_directory" "$target_directory" 2>&1) \
    || diff_status=$?
  if ((diff_status >= 2)); then
    log_error "diff 검사 실패($source_directory ↔ $target_directory) — 설치 상태를 신뢰할 수 없어 중단합니다"
    log_error "$diff_output"
    return 1
  fi

  grep -E "^Files .* differ$" <<< "$diff_output" || true
}

# 경로 생성에 실제로 쓰기가 필요한, 존재하는 최상위 조상 디렉토리를 반환한다.
find_existing_ancestor() {
  local probe_path="$1"
  while [[ ! -d "$probe_path" && "$probe_path" != "/" ]]; do
    probe_path=$(dirname "$probe_path")
  done
  echo "$probe_path"
}

check_write_permission() {
  local writable_ancestor
  writable_ancestor=$(find_existing_ancestor "$target_rules_dir")
  if [[ ! -w "$writable_ancestor" ]]; then
    log_error "쓰기 권한 없음: $writable_ancestor"
    return 1
  fi
  return 0
}

# check_no_symlink_targets 전용 헬퍼(50줄 제한 분리, S1 검수 1회차) — 관리 파일(잎)과 그
# 조상 디렉토리 전부의 상대경로 후보를 열거해 stdout 에 낸다. 열거는 build_files_ledger_json
# 과 같은 관리 파일(잎) 목록을 재사용한다. 각 잎의 조상은 문자열 접미사 제거(${var%/*})를
# 반복해 얻고, bash 3.2 에 연관 배열이 없어 중복 제거는 sort -u 로 한다(GOTCHA 16).
#
# m2(S1 검수 1회차): find | while | sort -u 파이프라인은 마지막 단(sort)의 종료 상태만
# candidate_paths 로 남으므로 find 자신의 오류(예: rules·agents·commands 세 인자 중 하나가
# 사라짐)가 조용히 사라졌다 — 나머지 인자가 파일을 냈다면 그 부분 결과만으로 통과했다.
# find 를 명령 치환으로 따로 잡아(GOTCHA 2 와 같은 관용구, x=$(cmd) || status=$?) 상태를
# 직접 확인한다. 후보 0건은 그 검사를 통과하고도 남는 별도 결함 형태다(예: rules·agents·
# commands 셋 다 빈 디렉토리) — 정상 레포에서는 일어나지 않지만(T31 등이 관리 파일 수를
# 별도로 강제한다) 조용한 무동작보다 fail-closed 가 낫다. 이 분기를 재현하는 픽스처는
# 마련하지 않았다(§10-3 기록 — H2-원자성과 같은 성격의 좁힘).
list_symlink_check_candidates() {
  local absolute_path relative_path ancestor_relative_path candidate_paths
  local find_output find_status=0
  find_output=$(find "$REPO_ROOT/rules" "$REPO_ROOT/agents" "$REPO_ROOT/commands" -type f \
    -not -path '*/__pycache__/*' 2>&1) || find_status=$?
  if ((find_status != 0)); then
    log_error "관리 파일 열거 실패(find) — 심링크 검사를 신뢰할 수 없어 중단합니다: $find_output"
    return 1
  fi

  candidate_paths=$(
    printf '%s\n' "$find_output" \
      | while IFS= read -r absolute_path; do
        [[ -z "$absolute_path" ]] && continue
        relative_path="${absolute_path#"$REPO_ROOT"/}"
        echo "$relative_path"
        ancestor_relative_path="$relative_path"
        while [[ "$ancestor_relative_path" == */* ]]; do
          ancestor_relative_path="${ancestor_relative_path%/*}"
          echo "$ancestor_relative_path"
        done
      done | sort -u
  )
  if [[ -z "$candidate_paths" ]]; then
    log_error "관리 파일 열거 결과가 0건입니다 — 심링크 검사를 신뢰할 수 없어 중단합니다"
    return 1
  fi
  printf '%s\n' "$candidate_paths"
}

# H3(PRP shell-hardening §9-3): 관리 경로(잎 파일)와 그 조상 디렉토리 전부의 대상 대응
# 경로가 심볼릭 링크인지 확인한다. cp -R 는 대상에 이미 있는 심링크를 관통한다 — 잎이면
# 링크가 가리키는 파일의 내용을 덮어쓰고, 조상 디렉토리(예: rules/common)면 그 안에 새
# 파일을 만든다. 세 최상위 디렉토리 자체만 보던 이전 버전을 이 안에서 확장한다(호출부
# 유지) — "관리 디렉토리 전체 심링크 거부"가 아니라 "우리가 배포하는 경로와 그 조상"만
# 검사한다: 사용자가 자기 에이전트를 관리 디렉토리에 심링크로 심어 두는 것은 소유권 원칙상
# 우리 소관이 아니고, 그것까지 거부하면 정상 설치가 막히는 오탐이 된다.
#
# --force 는 이 가드를 우회하지 못한다 — check_directory_conflict 의 --force 조기 반환과
# 대비되는 지점이다. --force 의 의미는 "내 수정본을 덮어써도 좋다"이지 "대상 트리 밖에
# 써도 좋다"가 아니다(호출부인 check_preconditions 가 --force 여부와 무관하게 이 함수를
# 항상 부른다).
#
# M3(S1 검수 1회차): 아래 후보 열거(list_symlink_check_candidates)는 $target_base_dir/
# .claude/ **하위** 상대경로만 만들어, 모든 관리 경로의 최상위 공통 조상인 .claude 자신은
# 그 열거에 들지 않는다 — "그 조상 디렉토리 전부"가 참이 되려면 .claude 자신도 별도로
# 봐야 한다. 이 파일에서 .claude 를 보는 다른 검사는 없다 — is_symlinked_path 의 유일한
# 호출부가 보는 것은 $target_base_dir, 즉 .claude 의 **부모**다. 그래서 여기서 놓치면
# mkdir -p·cp -R 가 그 링크를 관통한다.
#
# 검수 2회차 정정: 이 문단의 앞 판은 「신규 설치에서는 resolve_target_paths 의
# is_symlinked_path 검사도 cd 실패로 무력화된다」고 적었는데 반증됐다 — 그 검사는 애초에
# .claude 를 보지 않으므로 무력화될 대상이 없고, .claude 자신을 넣어 보면 cd 가 성공해
# 오히려 검출된다. 허브 쪽의 같은 형태 서술은 참이다(TARGET_HUB_DIR 이 링크보다 한 단계
# 깊어 cd 가 실제로 실패한다) — 두 파일에서 같은 문장이 참·거짓으로 갈리는 자리다.
check_no_symlink_targets() {
  if [[ -L "$target_base_dir/.claude" ]]; then
    log_error "심볼릭 링크입니다: $target_base_dir/.claude"
    return 1
  fi

  local candidate_paths
  candidate_paths=$(list_symlink_check_candidates) || return 1

  local candidate_relative_path target_path
  while IFS= read -r candidate_relative_path; do
    [[ -z "$candidate_relative_path" ]] && continue
    target_path="$target_base_dir/.claude/$candidate_relative_path"
    if [[ -L "$target_path" ]]; then
      log_error "심볼릭 링크입니다: $target_path"
      return 1
    fi
  done <<< "$candidate_paths"
  return 0
}

# S2 검수 1회차 반영(MEDIUM-문면 — DRY): report_directory_differences 와
# backup_modified_managed_files 가 각자 갖고 있던 "건수 산출 → 헤더 → 상한 절단 →
# 초과분 안내" 4줄을 한 곳으로 모은다. 두 호출부는 헤더 문구 뒤에 붙는 접미사만 다르므로
# 그 접미사를 인자로 받는다. 기존 호출부(report_directory_differences)는 빈 접미사를
# 넘겨, 이 추출 전과 문자 단위로 같은 출력을 낸다.
log_differing_file_list() {
  local target_directory="$1"
  local file_list="$2"
  local header_suffix="$3"
  local file_count
  file_count=$(printf '%s\n' "$file_list" | count_lines)

  log_warn "$target_directory 에서 수정된 파일이 ${file_count}건 발견됐습니다${header_suffix}"
  printf '%s\n' "$file_list" | head -n "$MAX_DIFF_LINES" >&2
  if [[ "$file_count" -gt "$MAX_DIFF_LINES" ]]; then
    log_warn "…외 $((file_count - MAX_DIFF_LINES))건"
  fi
}

report_directory_differences() {
  local target_directory="$1"
  local differing_list="$2"
  log_differing_file_list "$target_directory" "$differing_list" ""
  log_warn "덮어쓰려면 --force 를 쓰십시오"
}

# H2(PRP shell-hardening §9-2·§7-4): 문자열을 JSON 문자열 리터럴 안에 넣을 수 있게
# 이스케이프한다. 순서가 규약이다 — \ 를 먼저, " 를 그다음에(GOTCHA 3). 뒤집으면 두 번째
# 치환이 첫 번째가 넣은 백슬래시를 다시 바꾼다. 제어문자(개행 등)가 있으면 fail-closed 로
# 거부한다(1 반환, stdout 없음) — 대장의 읽기 쪽(read_installed_ledger_hash)은 grep/sed 로
# 줄 단위로 동작하므로, 개행이 든 키는 쓸 수는 있어도 읽을 수 없는 대장을 만든다
# (validate_removals_file 과 같은 방향의 fail-closed).
escape_json_string() {
  local raw_string="$1"
  # M1(S1 검수 1회차): 아래 case 문의 브래킷 범위 [$'\x01'-$'\x1f'] 는 바이트가 아니라
  # 콜레이션 순서로 해석된다 — C 로케일 밖(예: en_US.UTF-8)에서는 이 범위가 개행(0x0a)을
  # 비롯한 일부 제어문자를 걸러내지 못해 §7-4 의 fail-closed 가 무력화된다(실측). 이
  # 함수 안에서만 LC_ALL=C 로 고정해 호출측 로케일과 무관하게 항상 바이트 범위로 동작시킨다
  # — local 이라 이 함수를 벗어나면 호출측 로케일로 되돌아간다.
  local LC_ALL=C
  case "$raw_string" in
    *[$'\x01'-$'\x1f']*) return 1 ;;
  esac
  local escaped_string="${raw_string//\\/\\\\}"
  escaped_string="${escaped_string//\"/\\\"}"
  printf '%s' "$escaped_string"
}

# manifest 에서 상대경로의 대장 해시를 꺼낸다. 파일이 없거나 키가 없으면 빈 문자열.
# bash 3.2 호환 — 외부 JSON 파서 없이 grep/sed 로 고정 포맷을 직접 조회한다. 이 포맷은
# build_files_ledger_json 의 출력과 반드시 일치해야 한다("<relative_path>": "<sha256>").
#
# H2(GOTCHA 4 — 이 항목의 대표적 실패): 조회 키도 쓰기 쪽과 같은 규칙으로 이스케이프한다.
# 쓰기만 고치고 읽기를 빠뜨리면, 이스케이프가 필요한 경로에서 조회가 항상 빈 문자열을 내
# classify_differing_file 이 "대장 없음 → modified"로 오분류해 정상 설치가 --force 를
# 요구하게 된다.
read_installed_ledger_hash() {
  local manifest_path="$1"
  local relative_path="$2"

  [[ -f "$manifest_path" ]] || return 0
  local escaped_relative_path
  escaped_relative_path=$(escape_json_string "$relative_path") || return 0
  # 키(경로 문자열)는 64자리 hex 가 될 수 없으므로, 줄에서 유일한 64자리 hex 인용 문자열이
  # 곧 값이다 — 앞의 .* 가 탐욕적으로 키 쪽을 삼키고 값만 남긴다.
  # grep 이 키를 못 찾으면 exit 1 — set -euo pipefail 문맥의 명령 치환(`ledger_hash=$(...)`)
  # 에서 그대로 스크립트를 죽인다. "조회 실패 = 빈 문자열"이 이 함수의 계약이므로
  # `|| return 0` 으로 그 계약을 코드로 드러낸다.
  local matched_line
  matched_line=$(grep -F "\"$escaped_relative_path\":" "$manifest_path" | head -1) || return 0
  printf '%s' "$matched_line" | sed -E 's/.*"([0-9a-f]{64})".*/\1/'
}

# 내용이 다른 관리 파일 1개를 "stale"(대장과 일치 — 우리가 설치한 그대로인데 레포가
# 전진한 낡은 사본, 자동 통과) | "modified"(대장과 불일치 또는 대장 없음 — 사용자 수정
# 의심, --force 요구) 로 분류한다. v1 설치본(대장 자체가 없음)은 보수적으로 modified 로
# 본다 — 하위호환 원칙(설계 §8 결정3).
classify_differing_file() {
  local relative_path="$1"
  local target_file_path="$2"
  local previous_manifest_path="$3"

  local ledger_hash
  ledger_hash=$(read_installed_ledger_hash "$previous_manifest_path" "$relative_path")
  if [[ -z "$ledger_hash" ]]; then
    echo "modified"
    return 0
  fi

  if [[ "$(compute_sha256 "$target_file_path")" == "$ledger_hash" ]]; then
    echo "stale"
  else
    echo "modified"
  fi
}

# diff -rq 의 "Files A and B differ" 한 줄에서 대상측 경로(B)를 뽑는다.
extract_target_path_from_diff_line() {
  echo "$1" | sed -E 's/^Files (.*) and (.*) differ$/\2/'
}

# differing_list 에서 modified 로 분류된 줄만 남긴다. stale 로 분류된 것은 여기서 걸러져
# 충돌 보고에서 빠지고(자동으로 갱신 대상이 된다), 걸러졌다는 사실을 정보 로그로 남긴다.
filter_modified_files() {
  local differing_list="$1"
  local diff_line target_file_path relative_path classification

  while IFS= read -r diff_line; do
    [[ -z "$diff_line" ]] && continue
    target_file_path=$(extract_target_path_from_diff_line "$diff_line")
    relative_path="${target_file_path#"$target_base_dir"/.claude/}"
    classification=$(classify_differing_file "$relative_path" "$target_file_path" "$target_manifest_path")
    if [[ "$classification" == "stale" ]]; then
      # 호출부(check_directory_conflict)가 이 함수의 stdout 전체를 blocking_list 로
      # 캡처하므로, 여기서 stdout 에 쓰면 diff 줄이 아닌 안내문이 섞여 들어간다 — stderr 로만.
      echo "[INFO] 갱신 (낡은 사본, --force 불필요): $relative_path" >&2
    else
      echo "$diff_line"
    fi
  done <<< "$differing_list"
}

# D1: 우리가 배포하는 파일이 대상에서 수정됐으면 --force 를 요구한다.
# 대상에만 있는 파일은 우리 소유가 아니므로 충돌로 보지 않는다.
# 결함 5: 내용이 다른 파일도 곧바로 충돌은 아니다 — 대장과 대조해 "낡은 사본"(stale)은
# 자동 통과시키고, "사용자 수정 의심"(modified)만 --force 를 요구한다.
#
# H5(PRP shell-hardening §9-5): --force 는 더 이상 조기 반환하지 않는다 — modified 파일을
# 덮어쓰기 전에 backup_modified_managed_files 가 형제 위치에 백업을 남긴다. ! -d 만 조기
# 반환한다(대상이 아예 없으면 백업할 것도 없다). list_differing_managed_files 의
# || return 1 은 두 경로 모두에 적용된다 — H1 수정으로 이 함수는 diff 상태 2 이상에서
# 실패를 반환하므로, 그 상태를 모르는 채로 --force 가 덮어쓰지 않는다.
check_directory_conflict() {
  local source_directory="$1"
  local target_directory="$2"

  [[ -d "$target_directory" ]] || return 0

  if [[ "$force_overwrite" == "true" ]]; then
    backup_modified_managed_files "$source_directory" "$target_directory" || return 1
    return 0
  fi

  local differing_list
  differing_list=$(list_differing_managed_files "$source_directory" "$target_directory") || return 1
  if [[ -z "$differing_list" ]]; then
    return 0
  fi

  local blocking_list
  blocking_list=$(filter_modified_files "$differing_list")
  if [[ -z "$blocking_list" ]]; then
    return 0
  fi

  report_directory_differences "$target_directory" "$blocking_list"
  return 1
}

# H5(PRP shell-hardening §9-5): --force 로 덮어쓸 modified 파일을 형제 위치에
# .bak-<타임스탬프> 로 백업한다. 분류는 기존 list_differing_managed_files →
# filter_modified_files 를 그대로 쓴다 — stale(대장과 일치, 우리가 설치한 그대로인 낡은
# 사본)은 백업하지 않는다(잃을 것이 없다). S1 의 H2 가 고친 대장 조회
# (read_installed_ledger_hash)에 이 분류가 의존한다 — S1 이 이 항목의 필수 선행인 이유다.
#
# fail-closed(구현 결정, §9-5 보강 — 설계가 비워 둔 자리를 구현이 채웠다): 백업 자체가
# 실패하면(디스크 부족 등) 그 파일을 덮어쓰지 않고 설치를 중단한다. 백업의 존재 이유가
# 사용자 수정본을 잃지 않는 것인데, 실패한 채로 계속 진행하면 정확히 그 약속이 깨진다 —
# S1 이 세운 fail-loud 원칙(H1)과 같은 방향이다.
#
# 누적된 .bak-* 파일의 자동 정리는 만들지 않는다(YAGNI, §11-13).
#
# S2 검수 1회차 반영(CRITICAL-1) — 백업 이름 심링크 관통: 백업 이름
# ($target_file_path.$backup_suffix) 이 이미 심볼릭 링크로 선점돼 있으면 cp -p 가 그
# 링크를 관통해 대상 트리 밖에 쓴다(check_no_symlink_targets 가 관리 경로에서 막는 것과
# 같은 형태의 결함). cp -p 직전에 -L 로 거부한다. -e 가 아니라 -L 인 이유 — 댕글링
# 링크는 -e 가 false 이지만 cp -p 는 그래도 링크가 가리키는 경로에 파일을 새로 만들어
# (관통) exit 0 을 낸다. 동시에 -e 는 아래 §17(항목 9)이 남겨 둔 "백업 실패 → 같은 초
# 재시도"라는 도달 가능한 정상 경로까지 하드 실패로 막아 과잉이다 — -L 은 심링크만
# 거부해 그 경로를 건드리지 않는다.
#
# S2 검수 1회차 반영(MAJOR-1) — dry-run 부작용: dry-run 계약(파일시스템 변경 없음)을
# 지킨다. 목록·건수 표시(log_differing_file_list)는 dry-run 여부와 무관하게 그대로
# 낸다(그 표시 자체가 dry-run 의 목적이다) — 실제 백업(cp -p)만 process_removals ·
# retire_user_claude_md 두 형제 쓰기 경로와 같은 형태로 log_plan 을 남기고 건너뛴다.
backup_modified_managed_files() {
  local source_directory="$1"
  local target_directory="$2"

  local differing_list
  differing_list=$(list_differing_managed_files "$source_directory" "$target_directory") || return 1
  # S2 검수 1회차 반영(LOW-1): 형제 줄(위 differing_list 대입)과 형태를 맞춘다 —
  # filter_modified_files 의 마지막 실행 명령은 입력이 있으면 항상 echo, 없으면
  # `continue`(어느 쪽이든 사실상 항상 성공)라 이 || return 1 은 지금은 도달하지 않는다.
  # 그래도 형제 줄과 같은 fail-closed 규약을 이 함수의 계약으로 못박아 둔다 —
  # filter_modified_files 가 나중에 실패를 반환하도록 바뀌어도 이 줄이 이미 대비한다.
  local blocking_list
  blocking_list=$(filter_modified_files "$differing_list") || return 1
  [[ -z "$blocking_list" ]] && return 0

  log_differing_file_list "$target_directory" "$blocking_list" " — 백업 후 덮어씁니다(--force)"

  local backup_suffix
  backup_suffix=$(date +"$FORCE_OVERWRITE_BACKUP_SUFFIX_FORMAT")

  local diff_line target_file_path backup_path
  while IFS= read -r diff_line; do
    [[ -z "$diff_line" ]] && continue
    target_file_path=$(extract_target_path_from_diff_line "$diff_line")
    backup_path="${target_file_path}.${backup_suffix}"

    if [[ "$dry_run" == "true" ]]; then
      log_plan "cp -p $target_file_path $backup_path (--force 백업)"
      continue
    fi

    if [[ -L "$backup_path" ]]; then
      log_error "백업 이름이 심볼릭 링크입니다 — 대상 트리 밖에 쓰지 않고 중단합니다: $backup_path"
      return 1
    fi
    if ! cp -p "$target_file_path" "$backup_path"; then
      log_error "백업 실패 — 원본을 보존할 수 없어 중단합니다: $target_file_path"
      return 1
    fi
    log_info "백업: $target_file_path → $backup_path"
  done <<< "$blocking_list"
  return 0
}

# removals.txt 형식·안전 제약을 검증한다. 위반 시 1 — check_preconditions 가 이 함수로
# 쓰기보다 먼저 중단시킨다(D-5: 형식 위반·살아있는 파일의 툼스톤은 fail-closed).
validate_removals_file() {
  local removals_path="$1"
  [[ -f "$removals_path" ]] || return 0   # 파일 자체가 없으면 빈 것과 동일 취급

  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue

    case "$line" in
      rules/*|agents/*|commands/*) ;;
      *)
        log_error "removals.txt 형식 위반 — 세 네임스페이스(rules/agents/commands) 밖 경로: $line"
        return 1
        ;;
    esac
    case "$line" in
      *..*|/*|*'*'*|*'?'*|*'['*)
        log_error "removals.txt 형식 위반 — 상대경로·비글롭 규칙 위반: $line"
        return 1
        ;;
    esac
    if [[ -e "$REPO_ROOT/$line" ]]; then
      log_error "removals.txt 가 레포에 아직 존재하는 파일을 가리킵니다(레포 버그): $line"
      return 1
    fi
  done < "$removals_path"
  return 0
}

# m1(S1 검수 1회차 — check_preconditions 자신의 계약 "모든 쓰기보다 먼저 실행된다"를
# 지킨다): escape_json_string 의 제어문자 거부가 이전에는 build_manifest_json(관리 파일
# 전량 복사 뒤의 마지막 단계)에서만 발화해, 개행 든 경로가 있으면 파일을 전량 설치하고도
# manifest 만 없는 상태로 실패했다. $REPO_ROOT·$target_base_dir 는 이 시점에 이미
# 확정돼 있으므로 여기서 미리 검사한다 — 관리 파일 열거는 check_no_symlink_targets 와
# 같은 find 를 재사용한다. 이 함수는 그 find 의 실패를 스스로 재확인하지 않는다 —
# check_preconditions 안에서 반드시 check_no_symlink_targets **뒤**에 불려, find 가
# 이미 fail-closed 로 검증됐다고 가정한다(m2). 순서를 바꾸면 이 가정은 깨지지만
# fail-closed 는 유지된다 — 뒤로 밀린 check_no_symlink_targets 가 같은 실패를 잡는다
# (검수 2회차 실측). 잃는 것은 안전성이 아니라 같은 find 를 두 번 돌리지 않는 절약뿐이다.
check_manifest_paths_escapable() {
  escape_json_string "$REPO_ROOT" > /dev/null || {
    log_error "레포 경로에 제어문자가 있어 대장을 만들 수 없습니다: $REPO_ROOT"
    return 1
  }
  escape_json_string "$target_base_dir" > /dev/null || {
    log_error "설치 대상 경로에 제어문자가 있어 대장을 만들 수 없습니다: $target_base_dir"
    return 1
  }

  local absolute_path relative_path
  while IFS= read -r absolute_path; do
    relative_path="${absolute_path#"$REPO_ROOT"/}"
    escape_json_string "$relative_path" > /dev/null || {
      log_error "관리 파일 경로에 제어문자가 있어 대장을 만들 수 없습니다: $relative_path"
      return 1
    }
  done < <(find "$REPO_ROOT/rules" "$REPO_ROOT/agents" "$REPO_ROOT/commands" -type f \
    -not -path '*/__pycache__/*')
  return 0
}

# 모든 쓰기보다 먼저 실행된다 — 단 --force 백업(check_directory_conflict 의 --force 분기가
# 부르는 backup_modified_managed_files)은 이 계약의 예외다(S2 검수 2회차 MEDIUM N1). 그
# 백업이 실제 쓰기(cp -p)를 하므로, 이 함수가 실패를 반환해도 이미 파일이 생겼을 수 있다.
# 그런데도 여기서 하는 이유 — 백업 대상 판별(list_differing_managed_files →
# filter_modified_files)이 대장 조회(read_installed_ledger_hash)에 의존하고, 그 판별을
# 거치는 자리가 이 사전조건 단계뿐이다(설치 본체는 판별 없이 디렉토리 전체를 복사한다 —
# install_directory 가 부르는 copy_directory_contents 의 cp -R 이고, install_directory 자신이
# 두 목록 함수를 부르는 것은 갱신 건수 로그용이지 stale·modified 판별이 아니다). 그래서 실패 시 "파일을 하나도 건드리지 않은 상태"는 --force 가
# 아닐 때만 참이다 — 호출부(perform_installation)가 이 차이를 반영해 중단 메시지를 가른다.
check_preconditions() {
  check_write_permission || return 1
  check_no_symlink_targets || return 1
  check_manifest_paths_escapable || return 1
  check_directory_conflict "$REPO_ROOT/rules" "$target_rules_dir" || return 1
  check_directory_conflict "$REPO_ROOT/agents" "$target_agents_dir" || return 1
  check_directory_conflict "$REPO_ROOT/commands" "$target_commands_dir" || return 1
  validate_removals_file "$REMOVALS_FILE" || return 1
  return 0
}

# 툼스톤 처리 본체. D-1~D-4 판정, dry-run 지원. 보호는 실패가 아니므로 항상 0 을 반환한다.
#   D-1 대상에 파일 없음           → 조용히 skip (멱등)
#   D-2 대장 해시와 일치           → 삭제
#   D-3 대장에 항목 없음(v1 설치본) → 보호(설치 이력 불명)
#   D-4 대장 해시와 불일치(사용자 수정) → 보호(--force 로도 삭제하지 않는다 — 소유권 원칙)
process_removals() {
  local removals_path="$1"
  local previous_manifest_path="$2"
  [[ -f "$removals_path" ]] || return 0

  local line protected_count=0 removed_count=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue

    local target_file_path="$target_base_dir/.claude/$line"
    if [[ ! -f "$target_file_path" ]]; then
      continue   # D-1
    fi

    local ledger_hash
    ledger_hash=$(read_installed_ledger_hash "$previous_manifest_path" "$line")
    if [[ -z "$ledger_hash" ]]; then
      log_protected "$line — 설치 이력을 확인할 수 없어 남겨둡니다. 확인 후 수동 삭제하십시오"  # D-3
      protected_count=$((protected_count + 1))
      continue
    fi

    if [[ "$(compute_sha256 "$target_file_path")" != "$ledger_hash" ]]; then
      log_protected "$line — 수정된 파일이라 삭제하지 않습니다(--force 로도 삭제하지 않습니다). 확인 후 수동 삭제하십시오"  # D-4
      protected_count=$((protected_count + 1))
      continue
    fi

    if [[ "$dry_run" == "true" ]]; then
      log_plan "rm $target_file_path (툼스톤)"
    else
      rm -f "$target_file_path"
      rmdir "$(dirname "$target_file_path")" 2> /dev/null || true
      log_ok "제거: $line"
    fi
    removed_count=$((removed_count + 1))
  done < "$removals_path"

  if [[ "$protected_count" -gt 0 || "$removed_count" -gt 0 ]]; then
    log_info "툼스톤 처리: 제거 ${removed_count}건, 보호 ${protected_count}건"
  fi
  return 0
}

# 커맨드 하나를 전역(~/.claude/commands)과 비교해 same | differ | absent 를 출력한다.
classify_against_global_command() {
  local command_file="$1"
  local global_file="$HOME/.claude/commands/$(basename "$command_file")"

  if [[ ! -f "$global_file" ]]; then
    echo absent
  elif cmp -s "$command_file" "$global_file"; then
    echo same
  else
    echo differ
  fi
}

# 전역 커맨드와의 중복 상황을 보고한다.
# --scope user 는 설치 대상이 곧 전역이므로 비교가 의미 없어 생략한다.
report_global_command_overlap() {
  if [[ "$scope" != "project" || ! -d "$HOME/.claude/commands" ]]; then
    return 0
  fi

  local identical_count=0
  local differing_names=""
  local command_file
  for command_file in "$REPO_ROOT/commands"/*; do
    [[ -f "$command_file" ]] || continue   # __pycache__ 등 디렉토리 항목은 비교 대상이 아니다
    case "$(classify_against_global_command "$command_file")" in
      same) identical_count=$((identical_count + 1)) ;;
      differ) differing_names="$differing_names $(basename "$command_file")" ;;
    esac
  done

  if [[ -n "$differing_names" ]]; then
    log_warn "전역 커맨드와 내용이 다릅니다:${differing_names}"
    log_warn "커맨드는 전역이 프로젝트보다 우선하므로 이 머신에서는 전역 버전이 실행됩니다"
    log_warn "프로젝트 사본을 쓰려면 전역을 갱신하십시오: install.sh --scope user"
  fi
  if [[ "$identical_count" -gt 0 ]]; then
    log_info "전역에 동일한 커맨드 ${identical_count}개 존재 — 내용이 같아 동작 차이 없음"
  fi
}

# mkdir + cp 의 실패를 명시적으로 검사한다.
# set -e 는 조건문에서 호출된 함수 내부에 적용되지 않으므로 직접 검사해야 한다.
#
# 2회차 검수 반영 — find 로 파일을 하나씩 복사하던 1회차 구현을 cp -R 로 되돌렸다. 그
# 구현은 프로세스 치환 `< <(find …)` 안의 find 실패를 while 도 함수의 return 0 도 검사하지
# 않아 "0개 복사 = 성공"이 되는 무성 실패가 있었고(Critical 1), `${source_file#$source_
# directory/}` 의 패턴 쪽이 인용되지 않아 글롭 메타문자가 든 경로에서 접두사 제거가
# 실패했으며(Critical 2), find -type f 가 심볼릭 링크·빈 디렉토리를 내지 않아 원래 cp -R
# 의 계약보다 좁아졌다(Major 1). cp -R 는 세 문제 모두 없다 — 아래에서 실패를 직접
# 검사하고, 심볼릭 링크·빈 디렉토리는 원래처럼 그대로 옮긴다.
copy_directory_contents() {
  local source_directory="$1"
  local target_directory="$2"

  if ! mkdir -p "$target_directory"; then
    log_error "디렉토리 생성 실패: $target_directory"
    return 1
  fi
  if ! cp -R "$source_directory/." "$target_directory/"; then
    log_error "복사 실패: $source_directory → $target_directory"
    return 1
  fi

  remove_pycache_from_target_directory "$target_directory"
  return 0
}

# cp -R 가 소스의 __pycache__(로컬에서 python3 -m py_compile 등을 실행해 남은 바이트코드
# 파생물)를 그대로 옮겼다면 대상에서 걷어낸다. 실측한 범위(이 머신의 BSD cp)에서는 이식
# 가능한 제외 플래그가 없다 — GNU coreutils 는 이 머신에 없어 확인하지 못했다. 그래서
# 배제는 복사 자체가 아니라 복사 후 즉시 제거로 한다 — 순간적으로는 대상에 존재하지만
# 이 함수가 반환할 때는 배포되지 않는다.
#
# 소유권 원칙(이 파일 상단 "예외 — __pycache__" 참고)과의 관계: __pycache__ 는 사용자가
# 직접 배치한 에이전트·커맨드·규칙류가 아니라 파이썬이 기계적으로 만드는 바이트코드
# 캐시다(.gitignore 도 배포 자산에서 제외). .py 원본이 남아있는 통상의 경우는 다음
# 임포트 때 그대로 재생성돼 삭제로 잃는 콘텐츠가 없다 — 아래 "무조건 실행" 문단이 함께
# 지우는 고아 캐시(.py 원본이 이미 사라진 경우)는 이 재생성 근거가 적용되지 않는다.
# 그 경우가 무해한 이유는 재생성이 아니라, 사라진 이름으로는 다시 import 될 파이썬
# 모듈이 애초에 없다는 것이다(4회차, A16 — 논거 범위를 실제 뒷받침되는 만큼으로 좁힘).
#
# 무조건 실행(3회차 검수 Major 1 — 시점 명시): target_directory 아래 임의 깊이의
# __pycache__ 를, 이번 cp -R 가 옮긴 것인지와 무관하게 매 설치마다 전부 지운다 — 이전
# 실행이 남긴 것, .py 원본이 이미 사라진 고아 캐시도 함께 지운다(1회차 미판단 항목이던
# 고아 캐시 자가 치유를 이 경로가 겸한다). 실패해도(권한 등) install_directory 의
# 성패에는 영향 없이 경고만 남긴다(관리 파일 자체의 설치 여부는
# verify_managed_files_installed 가 별도로 검증한다).
#
# 범위 방어(3회차 검수 Minor 1): find 의 검색 시작점 인자나 -name 패턴이 이후 실수로
# 넓어지는 변경이 있어도, 실제로 지우기 직전에 각 후보를 (a) 이 함수가 받은
# target_directory 의 정규화 경로(pwd -P — 문자열 접두사 비교만으로는 find 시작점에
# ".." 가 섞여도 그대로 매치돼 버려 방어가 안 된다) 아래인지, (b) 이름이 정확히
# __pycache__ 인지 다시 확인한다. 각각은 find 호출 인자와 독립적으로 재확인하므로, 그
# 인자 쪽 한 곳만 틀어져도 여기서 막힌다. 벗어나면 지우지 않고 경고만 남긴다.
#
# 비망라 예시(위 기제에서 따라오는 한계): 사용자가 같은 디렉토리에 자신의 .py 를 두어
# 같은 __pycache__ 를 공유하면 그 바이트코드도 함께 지워지지만, 위 이유로 데이터 손실은
# 아니다.
#
# 4회차 갱신(S4, tests-hardening PRP §9 A10~A16) — 개명(A14): "복사된" 이라는 이름은 이 함수가
# 실제로 하는 일(대상 디렉토리 안, 범위 가드를 통과한 __pycache__ 를 모두 지운다 — cp -R 가
# 옮긴 것인지와는 무관하다는 점은 위 "무조건 실행" 문단이 이미 명시한다)보다 좁아
# remove_pycache_from_target_directory 로 바꿨다. 인자 공백(A15) — 빈 문자열을 넘기면 `cd ""`
# 가 이 셸에서 성공을 반환해(실측) 범위 가드의 기준(resolved_target_directory)이 호출부의 현재
# 작업 디렉토리로 잡힌다. 다만 그 앵커가 읽히는 지점에는 도달하지 않는다 — `find ""` 가 후보를
# 0개 내므로 루프 본문이 한 번도 돌지 않는다(실측). 그래서 이 가드의 값은 앵커 보호가 아니라
# 조용한 무작동 대신 경고를 남기는 것이다(4회차 검수 Minor 정정 — 이 자리에 앵커 오설정을
# 거부의 근거로 적었었다). 실패 원인·건수(A11·A12·A13) — 이전 판은 rm -rf 의 표준 에러를 버려
# 실패해도 원인이 안 남았고(A11), 대상(commands 등) 자체가 쓰기 금지(555)라 그 자신은 못 지워도
# 그 rm -rf 재귀가 안의 중첩 자식(같은 이름의 __pycache__)은 먼저 지우는 혼합 상황에서, 이미
# 사라진 그 자식 후보에 다시 rm -rf 를 걸어도 그 호출은 성공을 반환해 건수가 실제 rm 연산
# 수보다 부풀었다(A12) — 평범한 중첩(권한 제약 없음)은 부모(바깥 __pycache__)가 통째로
# 사라지므로 자식 후보 처리 시 위 resolved_pycache_parent 의 cd 가 먼저 실패해 continue 하고,
# 그 cd 가드가 A12 의 1차 방어선이다 — 아래 `[[ -d ]]` 는 후보의 조상 중 하나가 쓰기 금지라 rm
# -rf 가 부분 성공한 혼합 상황에서 발화하는 2차 방어선이다(대상 자체가 쓰기 금지인 경우는 그중
# 대표 사례이고 T35-12 가 겨냥하는 것이 그 사례다 — 더 깊은 중간 디렉토리만 쓰기 금지인 변형도
# 같은 가드가 받는다. 4회차 검수 Minor 정정 — 이 자리에 「대상 자체가 …인 경우에만」으로 좁혀
# 적었었고, 그 문안은 이 가드를 실환경 도달 불가로 오판하게 만든다). 그래서 후보가 이미
# 사라졌으면(같은 실행에서 먼저 지워짐) 성공·실패 어느 쪽으로도 세지 않고 건너뛰고, 성공/실패를
# 따로 집계하며, 실패 시 rm 의 표준 에러를 담아 원인을 남기고, 성공한 개별 경로를 그때그때
# 로그로 남긴다(A13) — "N개 정리" 집계 로그의 N 은 이 실행에서 성공한 rm 연산 수를
# 주장하고(실패한 rm 도 연산은 수행되지만 N 에 들어가지 않는다), 개별 로그는 그 성공 건마다 한
# 레코드씩 남긴다(경로에 개행이 있으면 한 레코드가 물리적으로 여러 줄로 보일 수 있다). find 의
# -name 필터가 실수로 넓어지는 변조(A10)는 원장(tests/mutations.tsv T35-11)에, 이 `[[ -d ]]`
# 가드 자체를 되돌리는 변조(A12)는 원장(T35-12)에 등록해 tests/run.sh 의 T35 스위트가 고정한다
# — 이 함수 자체는 바뀌지 않는다.
remove_pycache_from_target_directory() {
  local target_directory="$1"
  if [[ -z "$target_directory" ]]; then
    log_warn "정리 대상 경로가 비어 있어 건너뜀(무해 — 관리 파일에는 영향 없음)"
    return 0
  fi

  local resolved_target_directory
  resolved_target_directory=$(cd "$target_directory" 2> /dev/null && pwd -P) || return 0

  local pycache_path pycache_parent resolved_pycache_parent
  local removed_count=0 failed_count=0 rm_error
  while IFS= read -r -d '' pycache_path; do
    pycache_parent=$(dirname "$pycache_path")
    resolved_pycache_parent=$(cd "$pycache_parent" 2> /dev/null && pwd -P) || continue

    case "$resolved_pycache_parent" in
      "$resolved_target_directory" | "$resolved_target_directory"/*)
        [[ "$(basename "$pycache_path")" == "__pycache__" ]] || continue
        [[ -d "$pycache_path" ]] || continue   # 조상 쓰기 금지로 후보만 사라진 경우(A12)

        if rm_error=$(rm -rf "$pycache_path" 2>&1); then
          removed_count=$((removed_count + 1))
          log_info "__pycache__ 제거: $pycache_path"
        else
          failed_count=$((failed_count + 1))
          rm_error="${rm_error//$'\n'/ }"
          log_warn "$pycache_path 정리 실패(원인: ${rm_error:-알 수 없음} · 무해 — 관리 파일에는 영향 없음)"
        fi
        ;;
      *)
        log_warn "범위 밖이라 건너뜀(무해 — 관리 파일에는 영향 없음): $pycache_path"
        ;;
    esac
  done < <(find "$target_directory" -type d -name '__pycache__' -print0 2> /dev/null)

  if [[ "$removed_count" -gt 0 ]]; then
    log_info "$target_directory 에서 __pycache__ ${removed_count}개 정리"
  fi
  if [[ "$failed_count" -gt 0 ]]; then
    log_warn "$target_directory 에서 __pycache__ 정리 실패 ${failed_count}건"
  fi
  return 0
}

# 배포한 파일이 전부 대상에 있고 내용이 같은지 확인한다.
# 대상에만 있는 파일은 검사하지 않는다 (우리 소유가 아니므로).
verify_managed_files_installed() {
  local name="$1"
  local source_directory="$2"
  local target_directory="$3"

  local missing_list
  local differing_list
  missing_list=$(list_missing_managed_files "$source_directory" "$target_directory") || return 1
  differing_list=$(list_differing_managed_files "$source_directory" "$target_directory") || return 1

  if [[ -n "$missing_list" || -n "$differing_list" ]]; then
    log_error "$name/ 설치 검증 실패 — 아래 파일이 반영되지 않았습니다"
    printf '%s\n%s\n' "$missing_list" "$differing_list" | grep -E . | head -n "$MAX_DIFF_LINES" >&2
    return 1
  fi
  return 0
}

install_directory() {
  local name="$1"
  local source_directory="$2"
  local target_directory="$3"
  local managed_count="$4"

  # 대상이 없으면 diff 가 빈 출력을 내므로 0건으로 오계산된다. 신규 설치는 전량이 대상이다.
  local outdated_count
  if [[ ! -d "$target_directory" ]]; then
    outdated_count="$managed_count"
  else
    # H1(PRP shell-hardening §9-1): 두 목록 함수를 파이프 안 그룹으로 묶지 않고 각각
    # 명령 치환으로 받아 || return 1 을 붙인다 — 그룹을 파이프 비-마지막 단으로 두면 diff
    # 실패가 set -e 아래에서 어떻게 전파되는지 불확실해진다.
    local missing_list differing_list
    missing_list=$(list_missing_managed_files "$source_directory" "$target_directory") || return 1
    differing_list=$(list_differing_managed_files "$source_directory" "$target_directory") || return 1
    outdated_count=$(printf '%s\n%s\n' "$missing_list" "$differing_list" | count_lines)
  fi

  copy_directory_contents "$source_directory" "$target_directory" || return 1
  verify_managed_files_installed "$name" "$source_directory" "$target_directory" || return 1

  if [[ "$outdated_count" -eq 0 ]]; then
    log_ok "$name/  ${managed_count}개 파일 → 변경 없음"
  elif [[ "$outdated_count" -eq "$managed_count" ]]; then
    log_ok "$name/  ${managed_count}개 파일 → $target_directory/"
  else
    log_ok "$name/  ${outdated_count}개 갱신 (관리 대상 ${managed_count}개) → $target_directory/"
  fi
  return 0
}

# manifest 의 "version" 필드를 읽는다. 파일 없음·필드 없음·파싱 실패(비정규 표기,
# 예: 콜론 뒤 공백 없는 "version":3) → 0.
# read_installed_ledger_hash 와 같은 grep 기반 조회 — bash 3.2 호환, 외부 JSON 파서 없음.
read_manifest_version() {
  local manifest_path="$1"
  [[ -f "$manifest_path" ]] || { echo 0; return 0; }
  local matched_line
  matched_line=$(grep -oE '"version": *[0-9]+' "$manifest_path" | head -1) || { echo 0; return 0; }
  local parsed_version="${matched_line##*: }"
  # 콜론 뒤 공백이 없으면(예: "version":3) 위 치환 패턴(*: )이 매치되지 않아 원문을 그대로
  # 반환한다 — 주석의 계약("파싱 실패 → 0")을 코드로 강제해, 호출측의 [[ … -ge 3 ]] 가
  # 비숫자 문자열을 만나 raw bash 오류를 내는 것을 막는다.
  [[ "$parsed_version" =~ ^[0-9]+$ ]] || parsed_version=0
  echo "$parsed_version"
}

# ~/.claude/CLAUDE.md 은퇴 판정 1건을 출력한다: retire|protect_modified|protect_unknown|skip
# 규칙은 위에서 아래로, 첫 일치가 승리한다(설계 §5.4).
#
# 접근 범위: 쓰는 경로는 $retired_claude_md_path(= $HOME/.claude/CLAUDE.md) 와, mv 직전
# 충돌 검사가 그 순간 계산하는 백업 후보 경로(같은 파일 + 지금 타임스탬프) 둘뿐이다.
# 읽는 경로는 그 둘에 인자로 받은 이전 manifest($previous_manifest_path, .coding-harness.json)
# 가 더해져 셋이다 — read_manifest_version(규칙 4)·read_installed_ledger_hash(규칙 5·6)
# 의 입력이다. 이 셋이 코드에서 닫힌 집합이다. 레포 원본과도 비교하지 않는다(대장·센티널
# 판정이므로 레포 루트의 CLAUDE.md 를 참조하지 않는다).
#
# 그 기제에서 따라오는 한계: 위 두 경로 밖은 존재 확인도, 내용 열람도 하지 않는다 —
# "판정에 영향을 주지 않는다"이지 "안전을 검증했다"는 뜻이 아니다. 비망라 예시:
# CLAUDE.local.md · ~/.claude/rules/** · 프로젝트 ./CLAUDE.md · 이번 실행의 백업과
# 타임스탬프가 다른 기존 .bak-*·.retired-* 파일들. 전수 나열이 아니다 — 위 범위 밖에
# 인접 자산이 더 있을 수 있다.
classify_user_claude_md_retirement() {
  local previous_manifest_path="$1"

  [[ -f "$retired_claude_md_path" ]] || { echo "skip"; return 0; }          # 규칙 2
  if [[ -L "$retired_claude_md_path" ]]; then
    echo "protect_unknown"; return 0                                       # 규칙 3
  fi

  local manifest_version
  manifest_version=$(read_manifest_version "$previous_manifest_path")
  if [[ "$manifest_version" -ge 3 ]]; then
    echo "skip"; return 0                                                  # 규칙 4 — 로그는 호출측에서 내지 않는다
  fi

  local ledger_hash
  ledger_hash=$(read_installed_ledger_hash "$previous_manifest_path" "CLAUDE.md")
  if [[ -n "$ledger_hash" ]]; then
    if [[ "$(compute_sha256 "$retired_claude_md_path")" == "$ledger_hash" ]]; then
      echo "retire"; return 0                                              # 규칙 5
    fi
    echo "protect_modified"; return 0                                      # 규칙 6 — --force 로도 삭제하지 않는다
  fi

  if grep -qxF "$LEGACY_CLAUDE_MD_TITLE_SENTINEL" "$retired_claude_md_path" \
    && grep -qF "$LEGACY_CLAUDE_MD_BODY_SENTINEL" "$retired_claude_md_path"; then
    echo "retire"; return 0                                                # 규칙 7 — 레거시 설치본 자동 이관
  fi

  echo "protect_unknown"                                                   # 규칙 8
}

# 판정에 따라 mv 원자 개명(= 백업이자 삭제)을 실행한다. dry-run 은 계획만 출력한다.
# 보호는 실패가 아니므로 항상 0 을 반환 — mv 자체가 실패했을 때만 1(설치 중단).
# project scope 는 호출측(log_installation_plan · perform_installation)의
# [[ "$scope" == "user" ]] 게이트가 이 함수를 아예 부르지 않는다 — retired_claude_md_path 가
# project scope 에서 비어 있는 것은 그 게이트가 없어도 안전하도록 만드는 2차 방어일 뿐,
# 부르지 않는 이유 그 자체는 아니다.
retire_user_claude_md() {
  local previous_manifest_path="$1"
  local classification
  classification=$(classify_user_claude_md_retirement "$previous_manifest_path")

  case "$classification" in
    skip)
      return 0
      ;;
    protect_modified | protect_unknown)
      local reason="설치 이력을 확인할 수 없어"
      if [[ "$classification" == "protect_modified" ]]; then
        reason="수정된 파일이라 --force 로도"
      elif [[ -L "$retired_claude_md_path" ]]; then
        reason="심볼릭 링크라 의도를 판정할 수 없어"
      fi
      log_protected "$retired_claude_md_path — ${reason} 은퇴시키지 않습니다. 확인 후 수동 이관: mv $retired_claude_md_path $retired_claude_md_path.retired-manual"
      return 0
      ;;
    retire)
      local backup_path
      backup_path="${retired_claude_md_path}.$(date +"$RETIRED_BACKUP_SUFFIX_FORMAT")"
      if [[ "$dry_run" == "true" ]]; then
        log_plan "mv $retired_claude_md_path $backup_path (CLAUDE.md 배포 채널 은퇴)"
        return 0
      fi
      # 초 단위 해상도 충돌 방어: 같은 초에 두 번째 은퇴가 시도되면(예: 재실행) mv 가 기존
      # 은퇴 백업을 조용히 덮어써 파괴할 수 있다 — "성공 로그 + 파일 소멸"이 되어 지운
      # 사실조차 알 수 없는 무성 데이터 손실이다. mv -n 은 쓰지 않는다: 대상이 있으면 옮기지
      # 않고 exit 0 을 반환해 "성공 로그 + 파일 잔존 + 다음 실행부터 규칙 4 로 영구 침묵"이라는
      # 더 나쁜 무성 실패가 된다. 대신 mv 직전에 직접 검사해 fail-closed 로 만든다.
      if [[ -e "$backup_path" ]]; then
        log_error "은퇴 대상 백업 이름이 이미 존재합니다: $backup_path"
        return 1
      fi
      if ! mv "$retired_claude_md_path" "$backup_path"; then
        log_error "은퇴 실패: $retired_claude_md_path → $backup_path"
        return 1
      fi
      log_ok "CLAUDE.md 은퇴 → $backup_path"
      return 0
      ;;
  esac
}

# 관리 파일 전수의 "상대경로": "sha256" JSON 오브젝트 본문을 stdout 으로 낸다 (정렬 고정 —
# 멱등성 비교 `grep -v installed_at` 로직이 그대로 성립해야 한다). 대장은 레포 원본 해시다
# — verify_managed_files_installed 가 대상·원본 동일함을 이미 검증했으므로 원본만 훑으면 된다.
# __pycache__ 는 복사 후 remove_pycache_from_target_directory 가 곧바로 지워 최종적으로는
# 배포되지 않으므로(3회차 검수 Minor 3) 대장에도 올리지 않는다.
build_files_ledger_json() {
  local relative_path file_hash escaped_relative_path is_first=true
  local absolute_path relative_paths

  relative_paths=$(
    find "$REPO_ROOT/rules" "$REPO_ROOT/agents" "$REPO_ROOT/commands" -type f \
      -not -path '*/__pycache__/*' \
      | while IFS= read -r absolute_path; do echo "${absolute_path#"$REPO_ROOT"/}"; done \
      | sort
  )

  while IFS= read -r relative_path; do
    [[ -z "$relative_path" ]] && continue
    # H2(§9-2): 대장 키에 넣기 전에 이스케이프한다. 제어문자가 든 경로는
    # escape_json_string 이 fail-closed 로 거부한다 — 이 저장소의 실제 파일명에는
    # 일어나지 않지만, 쓸 수 없는 것을 읽을 수도 없는 대장으로 만들지 않기 위해서다.
    escaped_relative_path=$(escape_json_string "$relative_path") || {
      log_error "관리 파일 경로에 제어문자가 있어 대장에 기록할 수 없습니다: $relative_path"
      return 1
    }
    file_hash=$(compute_sha256 "$REPO_ROOT/$relative_path")
    if [[ "$is_first" == "true" ]]; then
      is_first=false
    else
      printf ',\n'
    fi
    printf '    "%s": "%s"' "$escaped_relative_path" "$file_hash"
  done <<< "$relative_paths"
  printf '\n'
}

build_manifest_json() {
  local installed_at="$1"
  local installed_from_commit="$2"
  local files_ledger
  files_ledger=$(build_files_ledger_json) || return 1

  # H2(§9-2·§7-4): repo_path·target_base_dir 도 JSON 문자열 자리에 넣기 전에 이스케이프한다.
  # scope·installed_at·installed_from_commit 은 이스케이프하지 않는다 — 각각 parse_arguments
  # 가 검증한 고정값, date 출력, git 커밋 해시라 이스케이프가 필요한 문자가 나올 수 없다.
  local escaped_repo_path escaped_target_base_dir
  escaped_repo_path=$(escape_json_string "$REPO_ROOT") || {
    log_error "레포 경로에 제어문자가 있어 manifest 를 생성할 수 없습니다: $REPO_ROOT"
    return 1
  }
  escaped_target_base_dir=$(escape_json_string "$target_base_dir") || {
    log_error "설치 대상 경로에 제어문자가 있어 manifest 를 생성할 수 없습니다: $target_base_dir"
    return 1
  }

  cat <<EOF
{
  "version": $MANIFEST_VERSION,
  "repo_path": "$escaped_repo_path",
  "scope": "$scope",
  "installed_at": "$installed_at",
  "installed_from_commit": "$installed_from_commit",
  "target_base_dir": "$escaped_target_base_dir",
  "files_count": {
    "rules": $RULES_FILE_COUNT,
    "agents": $AGENTS_FILE_COUNT,
    "commands": $COMMANDS_FILE_COUNT
  },
  "files": {
$files_ledger
  }
}
EOF
}

# H2(PRP shell-hardening §9-2): 원자적 교체 — 같은 디렉토리에 고유 임시 파일을 만들어
# 쓰고 mv 로 교체한다(이 저장소 다른 런타임의 파일 원자적 교체 관용구와 같은 형태 —
# 프로젝트 CLAUDE.md §2 가 선언한 대로 이 스크립트는 그 런타임을 모른다). 고정 임시
# 파일명을 공유하면 동시 쓰기가 뒤섞인 파일을 발행할 수 있어 mktemp 로 매 호출마다
# 고유한 이름을 받는다. mktemp 산출물은 항상 0600 이므로, 그대로 mv 하면 신규 설치의
# manifest 가 0600 으로 좁아진다(M2, S1 검수 1회차 — 기존 파일 모드 보존이 "기존 파일이
# 있을 때"만 있어 최초 설치엔 적용되지 않았다). umask 를 반영한 기본 모드를 먼저 세워
# 신규 설치를 일반 파일 권한과 맞추고, 기존 파일이 있으면 그 모드로 다시 덮어써 재설치의
# 권한 보존을 유지한다.
write_manifest_atomically() {
  local manifest_path="$1"
  local parent_directory="$2"
  local manifest_content="$3"

  local tmp_manifest
  tmp_manifest=$(mktemp "$parent_directory/${MANIFEST_FILE_NAME}.XXXXXX") || {
    log_error "manifest 임시 파일 생성 실패: $parent_directory"
    return 1
  }
  # M2: 0666 에서 현재 umask 만큼 뺀 값 — printf '%s' > file 같은 일반 리다이렉션이 새
  # 파일을 만들 때의 모드와 같다(이 파일이 mktemp 로 바뀌기 전 save_manifest_file 이 쓰던
  # 방식). 실패해도(chmod 자체가 막힌 파일시스템 등) 무해 — 아래 mv 전 존재 파일 모드
  # 보존이 여전히 동작하고, 그마저 없으면 mktemp 의 0600 이 남는다.
  local default_mode
  default_mode=$(printf '%o' $(( 0666 & ~$(umask) )) )
  chmod "$default_mode" "$tmp_manifest" 2> /dev/null || true
  if ! printf '%s\n' "$manifest_content" > "$tmp_manifest"; then
    log_error "manifest 임시 파일 쓰기 실패: $tmp_manifest"
    rm -f "$tmp_manifest"
    return 1
  fi
  if [[ -f "$manifest_path" ]]; then
    local existing_mode
    existing_mode=$(stat -f '%OLp' "$manifest_path" 2>/dev/null || stat -c '%a' "$manifest_path" 2>/dev/null || true)
    if [[ -n "$existing_mode" ]]; then
      chmod "$existing_mode" "$tmp_manifest" 2> /dev/null || true
    fi
  fi
  if ! mv -f "$tmp_manifest" "$manifest_path"; then
    log_error "manifest 파일 저장 실패: $manifest_path"
    rm -f "$tmp_manifest"
    return 1
  fi
  return 0
}

save_manifest_file() {
  local manifest_path="$target_base_dir/.claude/$MANIFEST_FILE_NAME"
  local parent_directory
  parent_directory=$(dirname "$manifest_path")

  # parent 디렉토리 생성
  if ! mkdir -p "$parent_directory"; then
    log_error "manifest 부모 디렉토리 생성 실패: $parent_directory"
    return 1
  fi

  # 설치 시점의 커밋 해시 가져오기 (실패 시 "unknown")
  local installed_from_commit="unknown"
  if command -v git &> /dev/null && [[ -d "$REPO_ROOT/.git" ]]; then
    installed_from_commit=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
  fi

  # ISO 8601 타임스탬프 생성
  local installed_at
  installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # 새 manifest 생성
  local manifest
  manifest=$(build_manifest_json "$installed_at" "$installed_from_commit") || return 1

  # 기존 파일이 있으면 installed_at 제외하고 비교 (멱등성 확보)
  if [[ -f "$manifest_path" ]]; then
    local new_stripped
    local old_stripped
    new_stripped=$(printf '%s\n' "$manifest" | grep -v '"installed_at"')
    old_stripped=$(grep -v '"installed_at"' "$manifest_path" 2>/dev/null || true)

    if [[ "$new_stripped" == "$old_stripped" ]]; then
      log_ok "manifest → 변경 없음"
      return 0
    fi
  fi

  write_manifest_atomically "$manifest_path" "$parent_directory" "$manifest" || return 1

  log_ok "manifest → $manifest_path"
  return 0
}

log_installation_plan() {
  log_info "coding-harness 설치 계획 (scope: $scope, DRY-RUN)"
  log_info "대상: $target_base_dir"

  if ! check_preconditions; then
    log_error "사전 조건 실패 — 실제 실행 시 설치되지 않습니다"
    return 1
  fi

  log_plan "mkdir -p $target_rules_dir $target_agents_dir $target_commands_dir"
  log_plan "cp -R rules/. $target_rules_dir/         (${RULES_FILE_COUNT}개)"
  log_plan "cp -R agents/. $target_agents_dir/       (${AGENTS_FILE_COUNT}개)"
  log_plan "cp -R commands/. $target_commands_dir/   (${COMMANDS_FILE_COUNT}개)"
  # 3회차 검수 Major 1 — 이 삭제 경로(remove_pycache_from_target_directory)도 다른 두 삭제
  # 경로(툼스톤·CLAUDE.md 은퇴)처럼 dry-run 계획에 나와야 한다. 존재 여부와 무관하게 매
  # 실행마다 수행되므로(위 §remove_pycache_from_target_directory "무조건 실행") 조건 없이
  # 항상 출력한다.
  log_plan "rules/·agents/·commands/ 각각에서 __pycache__ 정리 (있으면 삭제, 매 실행마다 무조건 수행)"

  local planned_total=$((RULES_FILE_COUNT + AGENTS_FILE_COUNT + COMMANDS_FILE_COUNT))

  log_plan "mkdir -p $target_base_dir/.claude"
  # 아래 세 줄의 순서는 perform_installation 의 실제 실행 순서(removals → retire →
  # save_manifest_file)와 맞춘다 — dry-run 계획은 실제 순서를 미리 보여주는 것이 목적이다.
  process_removals "$REMOVALS_FILE" "$target_manifest_path"
  if [[ "$scope" == "user" ]]; then
    retire_user_claude_md "$target_manifest_path"
  fi
  log_plan "save manifest → $target_base_dir/.claude/$MANIFEST_FILE_NAME"

  report_global_command_overlap
  log_done "${planned_total}개 파일이 대상에 반영될 예정. 실제 변경 없음"
  return 0
}

perform_installation() {
  log_info "coding-harness 설치 (scope: $scope)"
  log_info "대상: $target_base_dir"

  if ! check_preconditions; then
    # S2 검수 2회차(MEDIUM N1): check_preconditions 는 --force 에서 이미 백업 쓰기를 했을 수
    # 있으므로(위 check_preconditions 주석 참고), "변경된 파일 없음"은 --force 가 아닐 때만
    # 참이다. force_overwrite 는 스크립트 전역이라 여기서 바로 읽는다.
    if [[ "$force_overwrite" == "true" ]]; then
      log_error "설치 중단 — 관리 파일은 변경되지 않았습니다(--force 백업 파일이 남아 있을 수 있습니다)"
    else
      log_error "설치 중단 — 변경된 파일 없음"
    fi
    return 1
  fi

  # target_manifest_path 는 전역 변수 그대로다 — 이 지역 변수는 사본이 아니라 이름표일
  # 뿐이고, 실제 보장은 순서다: process_removals·check_directory_conflict·
  # retire_user_claude_md 는 반드시 save_manifest_file(:아래) 이전에 호출돼야 "갱신 전"
  # 대장을 읽는다. dry-run 쪽(log_installation_plan)은 이 alias 없이 $target_manifest_path
  # 를 직접 읽는데, 거기도 save_manifest_file 을 호출하지 않으므로 같은 순서 보장이
  # 대칭적으로 성립한다.
  local previous_manifest_path="$target_manifest_path"

  install_directory "rules" "$REPO_ROOT/rules" "$target_rules_dir" "$RULES_FILE_COUNT" || return 1
  install_directory "agents" "$REPO_ROOT/agents" "$target_agents_dir" "$AGENTS_FILE_COUNT" || return 1
  install_directory "commands" "$REPO_ROOT/commands" "$target_commands_dir" "$COMMANDS_FILE_COUNT" || return 1
  process_removals "$REMOVALS_FILE" "$previous_manifest_path"
  if [[ "$scope" == "user" ]]; then
    retire_user_claude_md "$previous_manifest_path" || return 1
  fi
  save_manifest_file || return 1
  report_global_command_overlap

  log_done "$((RULES_FILE_COUNT + AGENTS_FILE_COUNT + COMMANDS_FILE_COUNT))개 파일 반영 완료"
  return 0
}

main() {
  parse_arguments "$@"
  resolve_target_paths || { log_error "설치 중단 — 변경된 파일 없음"; return 1; }

  if [[ "$dry_run" == "true" ]]; then
    log_installation_plan
    return $?
  fi

  perform_installation
}

main "$@"
