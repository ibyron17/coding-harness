"""hub_release_read.py — 하네스 릴리스 확인의 I/O 레이어. 설치 기록 읽기 · 릴리스 확인 기록 읽기/쓰기 ·
`git ls-remote` 실행 · 서버 1사이클(docs/prps/harness-versioning.md 단계 B, 결정 UN1~UN4).

비교·주기·뷰 조립은 hub_release.py(★순수, 잎)에 있다 — 이 모듈은 그 결과를 파일·프로세스와 잇는
얇은 층이다(hub_usage.py ↔ hub_usage_fetch.py 와 같은 배치). 경로 상수는 이 모듈이 갖는다:
hub_collect 를 임포트하지 않는다(hub_collect 가 이 모듈을 부르므로 순환이 된다). 임포트 방향은
hub_release(잎) ← hub_model · hub_release_read ← hub_collect · hub_server · hub.

원격 확인은 설치 기록의 repo_path 에서 `git ls-remote --tags --refs origin` 한 번이다 — 저장소의
ref·FETCH_HEAD 를 바꾸지 않고, /harness-update 가 쓰는 것과 같은 origin·프록시·인증 경로를 탄다(결정
UN1). repo_path 의 .git/config 가 실행될 수 있으나 사용자가 /harness-update 로 이미 fetch 를 돌리는
저장소와 같은 신뢰 수준이라 새 신뢰를 들이지 않는다. 서버는 start_new_session 으로 떠 제어
터미널이 없으므로 비밀번호·호스트키 질문이 뜰 수 없다(GIT_TERMINAL_PROMPT=0 을 함께 건다).

출력 크기 상한(GIT_LS_REMOTE_MAX_OUTPUT_BYTES)은 메모리 상한이 아니다 — communicate 가 stdout 을 전부
메모리에 올린 뒤 검사한다. 원격은 사용자 저장소의 origin(/harness-update 와 같은 신뢰 수준)이라 이를
받아들였고, 실질적인 상한은 15초 시간 제한이다. 청크 읽기로 바꾸지 않았다.
"""

import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import hub_atomic_write
import hub_model
import hub_release

INSTALL_RECORD_PATH = Path.home() / ".claude" / ".coding-harness.json"
RELEASE_CHECK_PATH = Path.home() / ".claude" / "hub" / "release_check.json"

# 원격이 응답하지 않을 때 전용 스레드가 최악으로 막히는 시간. 넘으면 프로세스 그룹째 종료한다 —
# git 이 띄운 ssh 자식이 남지 않게 한다. 하트비트 티커와 스레드가 달라 이 대기가 하트비트에 번지지 않는다.
GIT_LS_REMOTE_TIMEOUT_SECONDS = 15
# 태그 목록 출력 상한 — **메모리 상한이 아니다.** communicate(timeout=15) 는 stdout 을 전부 메모리에 올린
# 뒤에 이 크기를 검사하므로, 읽는 도중 끊지 않는다(파싱 입력 상한일 뿐이다). 청크 읽기로 바꾸지 않은 이유:
# 원격은 사용자 저장소의 origin 이라 /harness-update 와 같은 신뢰 수준이고, 실질적인 상한은 위의 15초
# 시간 제한이다(그 안에 받을 수 있는 양이 곧 메모리 사용의 한계).
GIT_LS_REMOTE_MAX_OUTPUT_BYTES = 256 * 1024
GIT_TERMINAL_PROMPT_ENV_NAME = "GIT_TERMINAL_PROMPT"

_RECORD_INT_FIELDS = ("last_attempt_at_ms",)
_RECORD_OPTIONAL_INT_FIELDS = ("last_success_at_ms",)
_RECORD_OPTIONAL_STR_FIELDS = ("latest_version", "last_failure_reason")


# ---- 설치 기록 (읽기 전용 입력 — 우리가 소유하지 않는다) ----
def _installed_harness_from_raw(raw: object) -> hub_release.InstalledHarness | None:
    """설치 기록 dict 에서 필요한 값만 꺼낸다. repo_path 가 쓸 수 있는 문자열이 아니면 None."""
    if not isinstance(raw, dict):
        return None
    repo_path = raw.get("repo_path")
    if not isinstance(repo_path, str) or not repo_path:
        return None
    version_text = raw.get("harness_version")
    harness_version = version_text if isinstance(version_text, str) and hub_release.parse_semver(version_text) else None
    commit = raw.get("installed_from_commit")
    installed_at = raw.get("installed_at")
    return hub_release.InstalledHarness(
        harness_version=harness_version,
        installed_from_commit=commit if isinstance(commit, str) else "unknown",
        installed_at=installed_at if isinstance(installed_at, str) else "",
        repo_path=repo_path,
    )


def read_installed_harness() -> tuple[hub_release.InstalledHarness | None, tuple[str, ...]]:
    """user scope 설치 기록을 읽는다. 없으면 (None, ()), 읽을 수 없거나 깨졌으면 (None, (경고,))."""
    try:
        text = INSTALL_RECORD_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, ()
    except (OSError, UnicodeDecodeError) as error:
        return None, (f"{INSTALL_RECORD_PATH}: 읽기 실패 — 버전 표기를 건너뜁니다 ({error})",)
    try:
        installed = _installed_harness_from_raw(json.loads(text))
    except ValueError:
        installed = None
    if installed is None:
        return None, (f"{INSTALL_RECORD_PATH}: JSON 이 아니거나 repo_path 가 없어 버전 표기를 건너뜁니다",)
    return installed, ()


# ---- 릴리스 확인 기록 (서버 스레드만 쓴다) ----
def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _record_from_raw(raw: object) -> hub_release.ReleaseCheckRecord | None:
    """dict 가 계약 타입을 지키면 ReleaseCheckRecord, 아니면 None."""
    if not isinstance(raw, dict):
        return None
    if not all(_is_int(raw.get(name)) for name in _RECORD_INT_FIELDS):
        return None
    if not all(raw.get(name) is None or _is_int(raw.get(name)) for name in _RECORD_OPTIONAL_INT_FIELDS):
        return None
    if not all(raw.get(name) is None or isinstance(raw.get(name), str) for name in _RECORD_OPTIONAL_STR_FIELDS):
        return None
    return hub_release.ReleaseCheckRecord(
        last_attempt_at_ms=raw["last_attempt_at_ms"],
        last_success_at_ms=raw.get("last_success_at_ms"),
        latest_version=raw.get("latest_version"),
        last_failure_reason=raw.get("last_failure_reason"),
    )


def read_release_check_record() -> hub_release.ReleaseCheckRecord | None:
    """release_check.json 을 읽는다. 없거나 깨졌거나 타입이 틀리면 None(캐시 없음으로 본다)."""
    try:
        return _record_from_raw(json.loads(RELEASE_CHECK_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def write_release_check_record(record: hub_release.ReleaseCheckRecord) -> None:
    """release_check.json 을 원자적으로 쓴다. OSError 는 호출측이 받는다."""
    RELEASE_CHECK_PATH.parent.mkdir(parents=True, exist_ok=True)
    hub_atomic_write.atomic_write_text(
        RELEASE_CHECK_PATH, RELEASE_CHECK_PATH.parent, "release_check.json.",
        json.dumps(asdict(record), ensure_ascii=False),
    )


# ---- 원격 확인 ----
def _kill_process_group(process: subprocess.Popen) -> None:
    """시간 초과한 git 과 그 자식(ssh 등)을 프로세스 그룹째 종료하고 회수한다."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass    # 그 사이 스스로 끝났다 — 종료시킬 것이 없다
    process.communicate()


def _run_git_ls_remote(repo_path: str) -> tuple[int, bytes]:
    """`git -C <repo_path> ls-remote --tags --refs origin` 을 실행해 (종료 코드, stdout) 을 돌려준다.

    argv 리스트·셸 없음(rules/python/security.md) · stdin 닫음 · 대화형 질문 금지. 시간 초과면
    프로세스 그룹을 종료하고 subprocess.TimeoutExpired 를 그대로 올린다.
    """
    process = subprocess.Popen(
        ["git", "-C", repo_path, "ls-remote", "--tags", "--refs", "origin"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env={**os.environ, GIT_TERMINAL_PROMPT_ENV_NAME: "0"},
        start_new_session=True,
    )
    try:
        stdout, _stderr = process.communicate(timeout=GIT_LS_REMOTE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)
        raise
    return process.returncode, stdout


def fetch_latest_release_version(repo_path: str) -> tuple[str | None, str | None]:
    """(최신 릴리스 버전 | None, 실패 사유 | None). 태그가 하나도 없으면 (None, None) — 성공이다."""
    if not repo_path or not Path(repo_path).is_dir():
        return None, "repo_missing"
    try:
        return_code, stdout = _run_git_ls_remote(repo_path)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError:
        return None, "git_unavailable"
    if return_code != 0:
        return None, "remote_error"
    if len(stdout) > GIT_LS_REMOTE_MAX_OUTPUT_BYTES:
        return None, "output_too_large"
    try:
        return hub_release.latest_release_version(stdout.decode("utf-8", errors="replace")), None
    except ValueError:
        return None, "parse_error"   # 방어선 — 자릿수 상한이 막는 값이 어떻게든 새도 사이클은 사유를 남기고 끝난다


def run_release_check_cycle(now_ms: int) -> hub_release.ReleaseCheckRecord:
    """설치 기록 → ls-remote → 기록 쓰기 1회. 예외를 올리지 않고 결과 기록을 돌려준다.

    기록 쓰기가 실패해도(디스크 문제) 결과는 돌려준다 — 호출측 루프가 메모리의 시도 시각으로
    주기를 지키므로 쓰기 실패가 원격 호출을 폭주시키지 않는다. 쓰기 실패는 stderr 에만 남긴다.
    """
    installed, _warnings = read_installed_harness()
    if installed is None:
        latest_version, failure = None, "no_install_record"
    else:
        latest_version, failure = fetch_latest_release_version(installed.repo_path)
    record = hub_release.next_release_check_record(read_release_check_record(), now_ms, latest_version, failure)
    try:
        write_release_check_record(record)
    except OSError as error:
        print(f"릴리스 확인 기록 쓰기 실패: {error}", file=sys.stderr)
    return record


# ---- 수집용 뷰 ----
def read_harness_version_view(
    config: hub_model.HubConfig,
) -> tuple[hub_release.HarnessVersionView | None, tuple[str, ...]]:
    """수집(collect_snapshot)용. 스위치가 꺼지면 캐시를 읽지 않는다 — 옛 캐시로 알림이 남지 않게(결정 UN4).

    설치 버전 표기는 로컬 정보라 스위치와 무관하게 보인다.
    """
    installed, warnings = read_installed_harness()
    record = read_release_check_record() if config.update_check_enabled else None
    return hub_release.build_harness_version_view(installed, record), warnings
