#!/bin/bash
# 허브 전용 설치기 — coding-harness 의 루트 install.sh 와 완전히 독립적이다.
#
# 허브는 머신 전역 자산이다(개정 쟁점 R5) — 설치 위치는 ~/.claude/hub/bin 하나뿐이고
# --scope 인자가 없다. coding-harness 를 설치했다고 허브가 함께 설치되지 않는다(요구 R-5).
#
# 소유권 원칙(루트 install.sh 와 동일): 이 스크립트는 hub/bin 과 hub/rules(HD2·HD11 —
# 진행 기록 지침 채널) 두 채널이 배포하는 파일만 관리한다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly REPO_ROOT
readonly HUB_FILE_COUNT=35
readonly HUB_RULE_FILE_COUNT=1
readonly MAX_DIFF_LINES=20
readonly TARGET_HUB_DIR="$HOME/.claude/hub"
readonly TARGET_BIN_DIR="$TARGET_HUB_DIR/bin"
readonly SOURCE_BIN_DIR="$REPO_ROOT/hub/bin"
# 진행 기록 지침 채널(HD2·HD11, docs/prps/dashboard-into-hub.md) — bin/ 과는 배포 대상
# 디렉터리가 다른 두 번째 채널이다. coding-harness 의 install.sh 는 이 디렉터리를 모른다
# (파일 집합이 서로소라 소유권이 겹치지 않는다).
readonly SOURCE_RULES_DIR="$REPO_ROOT/hub/rules"
readonly TARGET_RULES_DIR="$HOME/.claude/rules/hub"
readonly REQUIRED_PYTHON_MAJOR=3
readonly REQUIRED_PYTHON_MINOR=10

# hub/bin 은 PEP 604 `X | None` 어노테이션을 쓰고 `from __future__ import annotations` 를
# 쓰지 않는다 — 클래스·함수 어노테이션이 정의 시점에 즉시 평가되므로 3.10 미만에서는 임포트
# 자체가 TypeError 로 죽는다(hub/README.md 「요구사항」 근거와 동일). uninstall 경로에는
# 걸지 않는다 — 구버전 파이썬 머신에서 제거까지 막을 이유가 없다.
require_python() {
  if ! command -v python3 > /dev/null 2>&1; then
    log_error "python3 이 필요합니다 (${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR} 이상)"
    return 1
  fi
  if ! python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (${REQUIRED_PYTHON_MAJOR}, ${REQUIRED_PYTHON_MINOR}) else 1)"; then
    log_error "python3 ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ 필요 — 현재: $(python3 -V 2>&1)"
    return 1
  fi
}

force_overwrite="false"
dry_run="false"
do_uninstall="false"

log_info() { echo "[INFO] $*"; }
log_warn() { echo "[WARN] $*" >&2; }
log_ok() { echo "[OK]   $*"; }
log_error() { echo "[ERROR] $*" >&2; }
log_done() { echo "[DONE] $*"; }
log_plan() { echo "  [계획] $*"; }

usage() {
  cat << 'EOF'
Usage: hub/install.sh [--force] [--dry-run] [--uninstall] [--help]

Options:
  --force        수정된 hub/bin·hub/rules 파일 강제 덮어쓰기
  --dry-run      계획만 출력 (파일시스템 변경 없음)
  --uninstall    서버 정지 → 훅 제거 → statusLine 제거 → 규칙 파일 제거 → hub/bin 삭제 (순서 고정. events/·hub.html·config.json 은 보존)
  --help         이 메시지 표시
EOF
}

parse_arguments() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --force) force_overwrite="true"; shift ;;
      --dry-run) dry_run="true"; shift ;;
      --uninstall) do_uninstall="true"; shift ;;
      --help) usage; exit 0 ;;
      *) log_error "알 수 없는 옵션: $1"; usage; exit 1 ;;
    esac
  done
}

is_symlinked_path() {
  local candidate_path="$1"
  local resolved_path
  resolved_path=$(cd "$candidate_path" > /dev/null 2>&1 && /bin/pwd -P) || return 1
  if [[ "$candidate_path" == "$resolved_path" || "$candidate_path" == "${resolved_path#/private}" ]]; then
    return 1
  fi
  return 0
}

count_lines() {
  grep -c . || true
}

# 수정 감지 — 대상에 있으나 내용이 다른 관리 파일 목록 (사용자 수정 의심 → --force 필요).
# 대상에만 있는 파일(우리 소유가 아님)은 충돌로 보지 않는다 — 루트 install.sh 의 D1 원칙과 동일.
# __pycache__ 는 실행 시점마다 바뀌는 바이트코드 파생물이라 비교 대상이 아니므로 제외한다.
list_differing_managed_files() {
  diff -rq -x __pycache__ "$SOURCE_BIN_DIR" "$TARGET_BIN_DIR" 2> /dev/null | grep -E "^Files .* differ$" || true
}

# 규칙 채널의 수정 감지(HD11) — bin/ 과 같은 원칙, __pycache__ 제외가 필요 없을 뿐이다(마크다운).
list_differing_managed_rule_files() {
  diff -rq "$SOURCE_RULES_DIR" "$TARGET_RULES_DIR" 2> /dev/null | grep -E "^Files .* differ$" || true
}

# N3(PRP shell-hardening §9-3, H3 의 허브 트윈 — 독립 구현, 루트 install.sh 의 헬퍼를
# 공유하지 않는다·파일 상단 선언): TARGET_BIN_DIR 자신과 그 안의 배포 대상 파일 각각이
# 심볼릭 링크면 거부한다. copy_managed_bin_files 는 최상위 파일만 옮기므로(maxdepth 1)
# 검사도 그 얕은 깊이만큼이면 충분하다 — 관리 대상이 아닌 파일(대상에만 있는 사용자 자산)의
# 심링크는 검사하지 않는다(오탐 방지, H3 와 같은 판단 근거).
check_no_symlink_bin_targets() {
  if [[ -L "$TARGET_BIN_DIR" ]]; then
    log_error "심볼릭 링크입니다: $TARGET_BIN_DIR"
    return 1
  fi
  local source_file target_file
  while IFS= read -r -d '' source_file; do
    target_file="$TARGET_BIN_DIR/$(basename "$source_file")"
    if [[ -L "$target_file" ]]; then
      log_error "심볼릭 링크입니다: $target_file"
      return 1
    fi
  done < <(find "$SOURCE_BIN_DIR" -maxdepth 1 -type f -print0)
  return 0
}

# N3 의 규칙 채널 트윈(검수 1회차 F7 — 실측: 배포 파일이 dotfile 을 가리키는 심링크일 때
# --force 가 exit 0 으로 링크 대상의 사용자 내용을 덮었다). TARGET_RULES_DIR 자신과 그
# 안의 배포 대상 파일 각각이 심볼릭 링크면 거부한다 — bin 쪽과 같은 얕은 깊이(maxdepth 1)
# 판단 근거다.
check_no_symlink_rule_targets() {
  if [[ -L "$TARGET_RULES_DIR" ]]; then
    log_error "심볼릭 링크입니다: $TARGET_RULES_DIR"
    return 1
  fi
  local source_file target_file
  while IFS= read -r -d '' source_file; do
    target_file="$TARGET_RULES_DIR/$(basename "$source_file")"
    if [[ -L "$target_file" ]]; then
      log_error "심볼릭 링크입니다: $target_file"
      return 1
    fi
  done < <(find "$SOURCE_RULES_DIR" -maxdepth 1 -type f -name '*.md' -print0)
  return 0
}

# bin/ 채널의 수정 감지 — 대상이 아직 없으면(신규 설치) 통과.
check_no_modified_managed_bin_files() {
  if [[ ! -d "$TARGET_BIN_DIR" ]]; then
    return 0
  fi
  local differing_list
  differing_list=$(list_differing_managed_files)
  if [[ -z "$differing_list" ]]; then
    return 0
  fi
  local differing_count
  differing_count=$(printf '%s\n' "$differing_list" | count_lines)
  log_warn "$TARGET_BIN_DIR 에서 수정된 파일이 ${differing_count}건 발견됐습니다"
  printf '%s\n' "$differing_list" | head -n "$MAX_DIFF_LINES" >&2
  log_warn "덮어쓰려면 --force 를 쓰십시오"
  return 1
}

# 규칙 채널의 수정 감지(HD11) — 위와 같은 형태, 대상 디렉터리만 다르다. bin/ 채널과 독립
# 판정이다 — 한쪽만 바뀌어도(예: 규칙 문구만 수정) 그 채널만 --force 를 요구한다.
check_no_modified_managed_rule_files() {
  if [[ ! -d "$TARGET_RULES_DIR" ]]; then
    return 0
  fi
  local differing_list
  differing_list=$(list_differing_managed_rule_files)
  if [[ -z "$differing_list" ]]; then
    return 0
  fi
  local differing_count
  differing_count=$(printf '%s\n' "$differing_list" | count_lines)
  log_warn "$TARGET_RULES_DIR 에서 수정된 파일이 ${differing_count}건 발견됐습니다"
  printf '%s\n' "$differing_list" | head -n "$MAX_DIFF_LINES" >&2
  log_warn "덮어쓰려면 --force 를 쓰십시오"
  return 1
}

# 제거 사전조건·규칙 제거·dry-run 계획 셋이 공유하는 심링크 자리 탐지(UL1, 검수 3회차
# N7 — docs/prps/hub-uninstall-symlink-precondition.md). TARGET_RULES_DIR 자신이 심링크면
# 그 경로를, 아니고 부모($HOME/.claude/rules)가 심링크면 그 경로를, 둘 다 아니면 빈
# 문자열을 stdout 으로 낸다. 조상 전체를 cd+pwd -P 로 보는 is_symlinked_path 는 쓰지
# 않는다 — /private 밖의 조상($HOME 등)이 심링크인 머신에서 오탐하고, 없는 경로를
# "링크 아님"으로 읽는다(M3 가 닫은 구멍과 같은 함정). 부작용 없이 항상 0 을 반환한다.
find_rules_dir_symlink() {
  if [[ -L "$TARGET_RULES_DIR" ]]; then
    echo "$TARGET_RULES_DIR"
    return 0
  fi
  local target_rules_parent_dir
  target_rules_parent_dir="$(dirname "$TARGET_RULES_DIR")"
  if [[ -L "$target_rules_parent_dir" ]]; then
    echo "$target_rules_parent_dir"
    return 0
  fi
  return 0
}

# 제거 전용 사전조건(UL1·UL2, 검수 3회차 N7 — 검수 2회차 N4 의 판정을 좁힌다) —
# perform_uninstall·log_uninstall_plan(--dry-run) 양쪽의 **첫 줄**에서, 서버 정지·훅
# 제거보다도 먼저 부른다. N4 의 판정은 부모 디렉터리·TARGET_RULES_DIR 자신·배포 파일 중
# 하나라도 심링크면 무조건 거부했다 — 그래서 지울 규칙이 애초에 없어도 거부했고
# (dotfiles 로 규칙 디렉터리를 연결한 머신에서 규칙 채널 이전의 옛 허브가 영구 제거되지
# 않는다), 안내를 따라도 링크 자체는 남아 재실행이 다시 거부됐다(N7). 이 함수는 배포
# 규칙 이름마다 순서대로 ① 그 자리가 심링크면 거부(원본은 그대로 두고 링크만 지우라는
# 안내) ② 아니고 규칙 디렉터리 자신이나 그 부모가 심링크이며 그 자리에 파일이 실제로 있으면 거부(링크 너머의 그
# 파일만 지우라는 안내) ③ 그 밖은 통과로 좁힌다 — 안내를 한 번 따르면 입력이 ③ 으로
# 바뀌므로 재실행은 반드시 통과한다(UL2 계약). --force 우회는 두지 않는다(UL6) — 설치
# 쪽 check_no_modified_managed_rule_files 의 --force 는 "사용자 수정을 알고 덮어쓴다"는
# 의사결정이지만, 여기서는 그 우회가 곧 심링크 관통이나 최악 잔존 상태가 되어 의미가
# 다르다.
check_uninstall_preconditions() {
  local rules_dir_link
  rules_dir_link=$(find_rules_dir_symlink)
  local source_file target_file
  while IFS= read -r -d '' source_file; do
    target_file="$TARGET_RULES_DIR/$(basename "$source_file")"
    if [[ -L "$target_file" ]]; then
      log_error "심볼릭 링크입니다: $target_file"
      log_error "링크만 지운 뒤 다시 실행하십시오 — 링크가 가리키는 원본 파일은 건드리지 마십시오"
      return 1
    fi
    if [[ -n "$rules_dir_link" && -e "$target_file" ]]; then
      log_error "심볼릭 링크입니다: $rules_dir_link"
      log_error "링크 너머에 허브 규칙 파일이 남아 있습니다: $target_file"
      log_error "그 파일만 지운 뒤 다시 실행하십시오 — 링크는 지우지 마십시오"
      return 1
    fi
  done < <(find "$SOURCE_RULES_DIR" -maxdepth 1 -type f -name '*.md' -print0)
  return 0
}

check_preconditions() {
  # M3(S1 검수 1회차 — H3 의 허브 트윈 N3 을 다시 여는 자리): 아래 is_symlinked_path
  # "$TARGET_HUB_DIR" 는 신규 설치에서 TARGET_HUB_DIR(=$HOME/.claude/hub) 자신이 아직
  # 없으면 cd 가 실패해 "심링크 아님"으로 오판된다 — $HOME/.claude 자신이 심링크이고
  # 그 안에 아직 hub/ 가 없는 경우가 정확히 이 형태다. TARGET_HUB_DIR 의 부모를 직접
  # 검사해 그 구멍을 닫는다(부모가 이미 존재하면 -L 은 심링크 여부를 그대로 본다).
  local target_hub_parent_dir
  target_hub_parent_dir="$(dirname "$TARGET_HUB_DIR")"
  if [[ -L "$target_hub_parent_dir" ]]; then
    log_error "심볼릭 링크입니다: $target_hub_parent_dir"
    return 1
  fi
  if is_symlinked_path "$TARGET_HUB_DIR"; then
    log_error "심볼릭 링크입니다: $TARGET_HUB_DIR"
    return 1
  fi
  check_no_symlink_bin_targets || return 1
  # 규칙 채널의 M3 트윈(검수 1회차 F7) — $HOME/.claude/rules 자신이 심링크이면
  # TARGET_RULES_DIR(그 아래)이 아직 없을 때 is_symlinked_path 의 cd 가 실패해
  # "심링크 아님"으로 오판된다. 부모를 직접 검사해 그 구멍을 닫는다.
  local target_rules_parent_dir
  target_rules_parent_dir="$(dirname "$TARGET_RULES_DIR")"
  if [[ -L "$target_rules_parent_dir" ]]; then
    log_error "심볼릭 링크입니다: $target_rules_parent_dir"
    return 1
  fi
  check_no_symlink_rule_targets || return 1
  if [[ "$force_overwrite" == "true" ]]; then
    return 0
  fi
  check_no_modified_managed_bin_files || return 1
  check_no_modified_managed_rule_files || return 1
  return 0
}

# 대상 디렉토리 총량이 아니라 "이 스크립트가 배포하는 파일이 전부 도착했는가"만 본다 —
# 소유권 원칙(hub/bin 이 배포하는 파일만 관리)과 정합해진다. 대상에 남의 파일이
# 공존해도(예: 사용자가 직접 넣은 스크립트) 실패 사유로 삼지 않는다.
verify_installed_file_count() {
  local missing_files=()
  local source_file
  while IFS= read -r -d '' source_file; do
    local target_file="$TARGET_BIN_DIR/$(basename "$source_file")"
    if [[ ! -f "$target_file" ]]; then
      missing_files+=("$(basename "$source_file")")
    fi
  done < <(find "$SOURCE_BIN_DIR" -maxdepth 1 -type f -print0)

  if ((${#missing_files[@]} > 0)); then
    log_error "설치 검증 실패 — 누락 파일: ${missing_files[*]}"
    return 1
  fi
  return 0
}

# 규칙 채널의 설치 검증(HD11) — bin/ 과 같은 형태.
verify_installed_rule_file_count() {
  local missing_files=()
  local source_file
  while IFS= read -r -d '' source_file; do
    local target_file="$TARGET_RULES_DIR/$(basename "$source_file")"
    if [[ ! -f "$target_file" ]]; then
      missing_files+=("$(basename "$source_file")")
    fi
  done < <(find "$SOURCE_RULES_DIR" -maxdepth 1 -type f -name '*.md' -print0)

  if ((${#missing_files[@]} > 0)); then
    log_error "규칙 설치 검증 실패 — 누락 파일: ${missing_files[*]}"
    return 1
  fi
  return 0
}

# hub/bin 최상위의 일반 파일만 배포 대상이다 — __pycache__ 는 테스트 실행이 만든 로컬
# 바이트코드 파생물(.gitignore 대상)이라 배포하지 않는다(소유권 원칙: hub/bin 이 배포하는 파일만 관리).
copy_managed_bin_files() {
  local source_file
  while IFS= read -r -d '' source_file; do
    cp "$source_file" "$TARGET_BIN_DIR/" || return 1
  done < <(find "$SOURCE_BIN_DIR" -maxdepth 1 -type f -print0)
}

# hub/rules 최상위의 .md 파일만 배포 대상이다(HD11 — bin/ 과 같은 소유권 원칙).
copy_managed_rule_files() {
  local source_file
  while IFS= read -r -d '' source_file; do
    cp "$source_file" "$TARGET_RULES_DIR/" || return 1
  done < <(find "$SOURCE_RULES_DIR" -maxdepth 1 -type f -name '*.md' -print0)
}

perform_install() {
  log_info "허브 설치 (coding-harness 설치와 무관 — 별도 자산)"
  check_preconditions || { log_error "설치 중단 — 변경된 파일 없음"; return 1; }

  if ! mkdir -p "$TARGET_BIN_DIR"; then
    log_error "디렉토리 생성 실패: $TARGET_BIN_DIR"
    return 1
  fi
  if ! copy_managed_bin_files; then
    log_error "복사 실패: $SOURCE_BIN_DIR → $TARGET_BIN_DIR"
    return 1
  fi
  verify_installed_file_count || return 1

  if ! mkdir -p "$TARGET_RULES_DIR"; then
    log_error "디렉토리 생성 실패: $TARGET_RULES_DIR"
    return 1
  fi
  if ! copy_managed_rule_files; then
    log_error "복사 실패: $SOURCE_RULES_DIR → $TARGET_RULES_DIR"
    return 1
  fi
  verify_installed_rule_file_count || return 1

  log_ok "hub/bin  ${HUB_FILE_COUNT}개 파일 → $TARGET_BIN_DIR/"
  log_ok "규칙 ${HUB_RULE_FILE_COUNT}개 → $TARGET_RULES_DIR/ (허브 사용자만 진행 기록 지침을 받는다)"
  log_done "허브 설치 완료"
  log_info "다음 단계: /hub install (훅 + 상태줄 옵트인) → /hub server start → /hub"
  log_info "자세한 설명: $REPO_ROOT/hub/README.md"
  return 0
}

log_install_plan() {
  log_info "허브 설치 계획 (DRY-RUN)"
  check_preconditions || { log_error "사전 조건 실패 — 실제 실행 시 설치되지 않습니다"; return 1; }
  log_plan "mkdir -p $TARGET_BIN_DIR"
  log_plan "hub/bin 최상위 파일 → $TARGET_BIN_DIR/   (${HUB_FILE_COUNT}개, __pycache__ 제외)"
  log_plan "mkdir -p $TARGET_RULES_DIR"
  log_plan "hub/rules 최상위 파일 → $TARGET_RULES_DIR/   (${HUB_RULE_FILE_COUNT}개)"
  log_done "${HUB_FILE_COUNT}개 파일 + 규칙 ${HUB_RULE_FILE_COUNT}개가 대상에 반영될 예정. 실제 변경 없음"
  return 0
}

# --uninstall 의 순서가 이 스크립트의 존재 이유다. bin/ 을 먼저 지우면 server-stop 도
# uninstall-hooks 도 uninstall-statusline 도 실행할 수 없어, 서버는 계속 돌고 훅은
# 존재하지 않는 스크립트를 매 이벤트마다 호출하는, 사용자가 손으로 되돌리기 가장 어려운
# 상태가 된다.
#
# 세 하위 명령(server-stop·uninstall-hooks·uninstall-statusline) 중 어느 것의 실패도
# `|| true` 로 삼키지 않는다(선례: 검수 m2 가 server-stop 에 먼저 적용시킨 결정 — PRP
# shell-hardening §4 가 나머지 둘로 넓혔다). 삼키면 그 하위 명령이 되돌리려던 상태가 남은
# 채 bin/ 이 삭제돼 "그 상태 + 그것을 되돌릴 유일한 수단(hub.py)의 소멸"이 된다는 점은
# 셋 다 같다. 훅·statusLine 쪽은 서버처럼 계속 "돌지"는 않는다 — 잔존 훅 엔트리는
# `|| true` 와 stderr 봉쇄로 조용히 exit 0 일 뿐이다. 그래도 같은 결로 수렴하는 이유는
# 복구 수단(uninstall-hooks/uninstall-statusline 자신)이 지금 지우려는 bin/ 안에 있고,
# 그 대체 수단(사용자가 설정 파일을 직접 편집하는 것)이 이 저장소가 선언한 소유권 원칙과
# 어긋나기 때문이다(PRP shell-hardening §4-2). 결과를 파싱해 ok=false 면 --force 없이는
# 중단한다.
#
# ok 판정은 `grep -q '"ok": true'` 같은 문자열 매칭이 아니라 실제 JSON 파싱으로 한다(검수 n1)
# — 문자열 매칭은 `json.dumps` 의 키-값 사이 공백 규칙(기본은 `": "` 지만 보장된 계약이 아니다)
# 에 결합돼, 그 규칙이 바뀌면 `ok:true` 인데도 조용히 미가동으로 오판할 수 있다.
#
# uninstall_statusline 이 돌려주는 `{"ok": true, "removed": false}` 는 실패가 아니다 —
# 남의 statusLine 이거나 애초에 없을 때의 정상 무동작이고, ok 값만 보는 이 게이트가 그
# 경우를 그대로 통과시킨다(별도 분기 불필요, PRP shell-hardening §4-3 결정 2).
#
# 인자: hub.py 경로 · 하위 명령(--json 은 이 함수가 붙인다) · 실패 시 중단 사유 문장
#       (그 하위 명령에 고유하고, 그 시점까지 이미 끝난 단계를 함께 적는다 — 중단이
#       남기는 부분 적용 상태를 사용자에게 명시적으로 알리기 위해서다, §4-3 결정 3)
# 반환: 0 = ok:true 또는 --force 우회 / 1 = 중단
run_hub_subcommand_or_abort() {
  local hub_py="$1"
  local subcommand="$2"
  local abort_reason_sentence="$3"
  # 사용자에게 보이는 문장에는 하위 명령 이름 대신 사람이 읽는 이름을 쓴다 — 이 파일의
  # 다른 안내(호출부의 "상주 서버 정지 중...", usage, 제거 계획)가 모두 그 관례다(S3 검수
  # 2렌즈 지적). 하위 명령 이름 자체는 호출 인자로 남으므로 등장 순서를 보는 검사(T25-23·
  # T25-39)는 그대로 성립한다.
  local subcommand_label recovery_hint
  case "$subcommand" in
    server-stop)
      subcommand_label="서버 정지"
      recovery_hint="서버 프로세스가 남아 있는지 직접 확인해 종료하십시오" ;;
    uninstall-hooks)
      subcommand_label="훅 제거"
      recovery_hint="남은 훅 항목이 있는지 직접 확인해 제거하십시오" ;;
    uninstall-statusline)
      subcommand_label="statusLine 제거"
      recovery_hint="남은 상태줄 항목이 있는지 직접 확인해 제거하십시오" ;;
    # 네 번째 하위 명령이 추가돼도 틀린 문장을 내지 않도록 중립 문장을 둔다 — 옛 판은
    # 여기서 훅·상태줄 전용 문장을 내보내 그 경우 거짓이 됐다(S3 검수 지적).
    *)
      subcommand_label="$subcommand"
      recovery_hint="그 단계가 되돌리려던 항목이 남았는지 직접 확인하십시오" ;;
  esac

  local subcommand_result
  subcommand_result=$(python3 "$hub_py" "$subcommand" --json)
  echo "$subcommand_result"
  if echo "$subcommand_result" | python3 -c 'import json, sys; sys.exit(0 if json.load(sys.stdin).get("ok") else 1)' 2>/dev/null; then
    return 0
  fi
  if [[ "$force_overwrite" == "true" ]]; then
    log_warn "$subcommand_label 실패를 --force 로 무시하고 계속합니다"
    # 강행을 고른 사용자에게만 필요한 정보다 — 중단 경로는 --force 안내로 충분하다(§4-3
    # 결정 4). 서버는 프로세스, 훅·statusLine 은 설정 파일 안의 항목이라 복구 대상이 다르다.
    log_warn "수동 복구 절차: $recovery_hint"
    return 0
  fi
  log_error "$subcommand_label 실패 — bin/ 삭제를 중단합니다"
  log_error "$abort_reason_sentence"
  log_error "원인을 해결하거나, 그래도 강행하려면 --force 를 쓰십시오"
  return 1
}

# 규칙 채널 제거(HD11) — 배포한 이름만 rm -f 로 지운다. rm -rf 를 쓰지 않는 이유: 이
# 디렉터리에는 남의 파일이 함께 있을 수 있다(coding-harness 의 소유권 원칙과 같은 이유,
# rm -rf "$TARGET_BIN_DIR" 리터럴이 bin/ 삭제에만 쓰이는 것과 대칭). 디렉터리가 그 결과
# 비면 rmdir 로 정리하되, 남의 파일이 남아 있으면(rmdir 실패) 조용히 둔다.
#
# 규칙 디렉터리가 심링크 너머면(UL3·UL4, 검수 3회차 N7·N8) rm·rmdir 을 하나도 돌리지
# 않고 맨 앞에서 이 재판정 방어선으로 먼저 판단한다 — check_uninstall_preconditions 를
# 그대로 다시 불러, 정상 흐름에서는 이미 통과한 판정이라 그대로 통과([INFO] 후 0)하지만
# 사전조건을 거치지 않은 호출이나 그 사이 링크 너머에 규칙이 생긴 경우는 거부(1)로
# bin/ 삭제 전에 멈춘다. 통과해도 링크 너머는 건드리지 않는다 — rmdir 은 빈 디렉터리만
# 지우지만, "링크를 지나 바꾸지 않는다"를 예외 없이 두어야 한 문장으로 검증된다.
#
# rm -f 실패는 명시적으로 return 1 한다(검수 1회차 F11) — 이 함수를 조건문
# (`if ! remove_managed_rule_files; then …`)에서 부르면 set -e 가 호출된 함수 내부에는
# 적용되지 않으므로(프로젝트 CLAUDE.md 관례와 같은 함정), 실패를 암묵적 전파에 맡기지
# 않고 이 함수 자신이 판정해 반환값으로 알린다. 방어선의 check_uninstall_preconditions
# 호출에도 같은 이유로 || return 1 을 명시한다.
remove_managed_rule_files() {
  local rules_dir_link
  rules_dir_link=$(find_rules_dir_symlink)
  if [[ -n "$rules_dir_link" ]]; then
    check_uninstall_preconditions || return 1
    log_info "규칙 파일 제거를 건너뜁니다 — $rules_dir_link 가 심볼릭 링크이고 그 너머에 지울 허브 규칙 파일이 없습니다(링크는 건드리지 않습니다)"
    return 0
  fi
  if [[ ! -d "$TARGET_RULES_DIR" ]]; then
    return 0
  fi
  local source_file
  while IFS= read -r -d '' source_file; do
    rm -f "$TARGET_RULES_DIR/$(basename "$source_file")" || return 1
  done < <(find "$SOURCE_RULES_DIR" -maxdepth 1 -type f -name '*.md' -print0)
  if rmdir "$TARGET_RULES_DIR" 2> /dev/null; then
    log_ok "$TARGET_RULES_DIR 제거 완료(디렉터리 포함)"
  else
    log_ok "$TARGET_RULES_DIR 의 배포 파일 제거 완료(디렉터리는 유지 — 다른 파일이 있음)"
  fi
  return 0
}

perform_uninstall() {
  check_uninstall_preconditions || return 1

  local hub_py="$TARGET_BIN_DIR/hub.py"
  if [[ -f "$hub_py" ]]; then
    log_info "상주 서버 정지 중..."
    run_hub_subcommand_or_abort "$hub_py" "server-stop" \
      "그대로 진행하면 서버는 계속 도는데 끌 수단(hub.py)만 사라집니다" || return 1
    log_info "훅 제거 중..."
    run_hub_subcommand_or_abort "$hub_py" "uninstall-hooks" \
      "서버 정지는 이미 완료됐습니다. 그대로 진행하면 훅 항목은 남고 그것을 지울 수단(hub.py)만 사라집니다" || return 1
    log_info "statusLine 제거 중..."
    run_hub_subcommand_or_abort "$hub_py" "uninstall-statusline" \
      "서버 정지·훅 제거는 이미 완료됐습니다. 그대로 진행하면 statusLine 항목은 남고 그것을 지울 수단(hub.py)만 사라집니다" || return 1
  else
    log_warn "$hub_py 가 없어 서버 정지·훅 제거·statusLine 제거를 건너뜁니다"
  fi

  # 규칙 파일을 bin/ 보다 먼저 지운다 — 순서를 반대로 하면 모든 세션이 존재하지 않는
  # 기록기를 가리키는 지침을 계속 받는, 되돌리기 가장 어려운 상태가 된다(HD2 R2).
  log_info "규칙 파일 제거 중..."
  if ! remove_managed_rule_files; then
    log_error "규칙 파일 제거 실패: $TARGET_RULES_DIR"
    return 1
  fi

  if ! rm -rf "$TARGET_BIN_DIR"; then
    log_error "삭제 실패: $TARGET_BIN_DIR"
    return 1
  fi
  log_ok "$TARGET_BIN_DIR 삭제 완료"
  log_done "허브 제거 완료"
  log_info "사용자 데이터·잔존 상태 파일은 지우지 않았습니다 — 직접 결정하십시오:"
  log_info "  $TARGET_HUB_DIR/events/  (이벤트 로그)"
  log_info "  $TARGET_HUB_DIR/hub.html  (마지막 화면)"
  log_info "  $TARGET_HUB_DIR/config.json  (설정, 있는 경우)"
  log_info "  $TARGET_HUB_DIR/server.json, server_heartbeat  (정지 실패로 남아 있을 수 있음)"
  log_info "  $TARGET_HUB_DIR/server.log  (서버 로그)"
  log_info "  $TARGET_HUB_DIR/.collect_spawn_stamp  (훅 디바운스 스탬프)"
  log_info "  $TARGET_HUB_DIR/rate_limits.json  (한도 초기화 예정 시각 캡처, 있는 경우)"
  log_info "  $TARGET_HUB_DIR/session_costs/  (세션별 비용·컨텍스트 캡처, 있는 경우)"
  log_info "  각 프로젝트의 .claude/dashboards/*.jsonl 은 지우지 않았습니다(열거 불가)"
  return 0
}

# --uninstall --dry-run 조합 전용 계획 출력 — perform_uninstall 을 호출하지 않으므로
# server-stop·훅 제거·bin/ 삭제 어느 것도 실제로 실행되지 않는다.
log_uninstall_plan() {
  check_uninstall_preconditions || return 1

  log_info "허브 제거 계획 (DRY-RUN)"
  local hub_py="$TARGET_BIN_DIR/hub.py"
  if [[ -f "$hub_py" ]]; then
    log_plan "상주 서버 정지 → 훅 제거 → statusLine 제거 (hub.py 경유)"
  else
    log_plan "$hub_py 가 없어 서버 정지·훅 제거·statusLine 제거 단계는 건너뛸 예정"
  fi
  local rules_dir_link
  rules_dir_link=$(find_rules_dir_symlink)
  if [[ -z "$rules_dir_link" ]]; then
    log_plan "규칙 파일 제거 → $TARGET_RULES_DIR (배포한 이름만 rm -f, 비면 rmdir)"
  else
    log_plan "규칙 파일 제거 건너뜀 — $rules_dir_link 가 심볼릭 링크이고 그 너머에 지울 허브 규칙 파일이 없음(링크는 건드리지 않음)"
  fi
  log_plan "rm -rf $TARGET_BIN_DIR"
  log_done "위 절차가 실제 실행될 예정. 실제 변경 없음"
  return 0
}

main() {
  parse_arguments "$@"

  if [[ "$do_uninstall" == "true" ]]; then
    if [[ "$dry_run" == "true" ]]; then
      log_uninstall_plan
      return $?
    fi
    perform_uninstall
    return $?
  fi

  require_python || return 1

  if [[ "$dry_run" == "true" ]]; then
    log_install_plan
    return $?
  fi
  perform_install
}

main "$@"
