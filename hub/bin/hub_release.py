"""hub_release.py — 하네스 릴리스 버전 비교와 원격 확인 주기 판정(★순수, 잎 모듈).

이 모듈은 파일시스템·시각·환경변수·네트워크에 닿지 않고 다른 허브 모듈도 임포트하지 않는다
(tests/hub/test_hub_release.py 대상, tests/run.sh T25-10 이 파일시스템 접근 흔적을 기계적으로
강제한다). 여기 있는 것은 "이미 읽어 온 값을 비교하는 규칙"과 대외 계약(설치 기록에서 꺼낸 값 ·
릴리스 확인 기록 · hub.html 의 harness_version)뿐이다. 읽고 쓰고 git 을 부르는 일은 I/O 위성
모듈 hub_release_read.py 가 한다(hub_usage.py ↔ hub_usage_fetch.py 와 같은 배치).

배경: docs/prps/harness-versioning.md 단계 B. 루트 VERSION(SemVer)이 정본이고 원격에 올라온
태그 vX.Y.Z 가 릴리스 공표다 — 이 모듈은 "설치된 버전이 원격 최신 릴리스보다 뒤처졌는가"만 답한다.
"""

import re
from dataclasses import dataclass
from typing import Literal

SemVer = tuple[int, int, int]

# 원격 확인 주기 — 상수다(설정 키로 만들지 않는다, 결정 UN4).
RELEASE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000

ReleaseCheckFailure = Literal[
    "no_install_record",   # 설치 기록이 없거나 repo_path 를 쓸 수 없다
    "repo_missing",        # repo_path 가 디렉터리가 아니다
    "git_unavailable",     # git 실행 파일이 없다
    "timeout",             # 제한 시간 초과(프로세스 그룹째 종료)
    "remote_error",        # 종료 코드가 0 이 아니다(원격 없음·인증·네트워크·SSH 키 없음 포함)
    "output_too_large",    # 출력이 상한을 넘었다
    "parse_error",         # 출력 해석 중 예기치 못한 ValueError(자릿수 상한이 막는 값이라 방어선 — 사이클을 죽이지 않는다)
]

# 숫자 부분 하나의 최대 자릿수. install.sh 의 HARNESS_VERSION_PATTERN(`{0,8}`)·tests/run.sh T41 과 같은
# 경계다 — 저장소가 받는 형식과 이 모듈이 읽는 형식이 달라지면 안 된다(PRP HV1). 상한이 없으면 원격
# 태그 한 줄(`v1.0.<5000자리>`)이 파이썬 int() 변환 한도(4300자리)를 넘어 ValueError 로 사이클을 죽인다.
MAX_VERSION_NUMBER_DIGITS = 9
_VERSION_NUMBER = rf"(0|[1-9][0-9]{{0,{MAX_VERSION_NUMBER_DIGITS - 1}}})"
# VERSION 파일 규칙(install.sh 의 HARNESS_VERSION_PATTERN 과 같다): 앞자리 0·접두 v·프리릴리스 거부.
_SEMVER_PATTERN = re.compile(rf"{_VERSION_NUMBER}\.{_VERSION_NUMBER}\.{_VERSION_NUMBER}")
# `git ls-remote --tags --refs` 한 줄: <40 또는 64자리 hex>\trefs/tags/v<버전 후보>. 64자리는 sha256 저장소 대비.
_LS_REMOTE_TAG_LINE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\trefs/tags/v(\S+)")
_COMMIT_HASH_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
COMMIT_SHORT_LENGTH = 7


@dataclass(frozen=True)
class InstalledHarness:
    """user scope 설치 기록(~/.claude/.coding-harness.json)에서 꺼낸 값. 설치 기록과 맺은 계약."""

    harness_version: str | None     # 필드 없음·"unknown"·형식 오류 → None
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
    """hub.html #dzh-data 의 harness_version. hub_template.html 과 맺은 계약."""

    installed_version: str          # "1.0.0" · 모르면 ""
    installed_commit_short: str     # 7자 · 모르면 ""
    installed_at: str
    latest_version: str             # 모르면 ""(미확인·실패·스위치 꺼짐)
    is_update_available: bool


def parse_semver(text: str) -> SemVer | None:
    """'X.Y.Z' 만 받는다(앞자리 0·접두 v·프리릴리스·앞뒤 공백·숫자 10자리 이상 거부). 아니면 None."""
    matched = _SEMVER_PATTERN.fullmatch(text)
    if matched is None:
        return None
    major, minor, patch = matched.groups()
    return (int(major), int(minor), int(patch))


def latest_release_version(ls_remote_stdout: str) -> str | None:
    """`ls-remote --tags --refs` 출력에서 vX.Y.Z 태그의 최댓값을 'X.Y.Z' 로 돌려준다.

    숫자 튜플로 비교한다(v1.10.0 > v1.9.0). 형식 밖 태그(자릿수 상한 초과 포함)·해시가 hex 가 아닌 줄은 무시한다.
    """
    versions: list[SemVer] = []
    for line in ls_remote_stdout.splitlines():
        matched = _LS_REMOTE_TAG_LINE.fullmatch(line)
        if matched is None:
            continue
        version = parse_semver(matched.group(1))
        if version is not None:
            versions.append(version)
    if not versions:
        return None
    return ".".join(str(part) for part in max(versions))


def should_attempt_release_check(now_ms: int, last_attempt_at_ms: int | None, interval_ms: int) -> bool:
    """지금 원격을 확인해도 되는가. 기록 없음·주기 경과(경계 포함)·벽시계 역행(now < last)이면 참."""
    if last_attempt_at_ms is None or now_ms < last_attempt_at_ms:
        return True
    return (now_ms - last_attempt_at_ms) >= interval_ms


def next_release_check_record(
    previous: ReleaseCheckRecord | None, now_ms: int, latest_version: str | None, failure: str | None
) -> ReleaseCheckRecord:
    """시도 결과를 반영한 **새** 기록을 돌려준다(원본은 불변).

    실패면 직전 성공의 latest_version·last_success_at_ms 를 보존한다 — 일시적 네트워크 실패가 이미 알려진
    새 버전을 화면에서 지우지 않는다(결정 UN2, A7 선례). 성공이면 갱신하고 실패 사유를 지운다.
    """
    if failure is not None:
        return ReleaseCheckRecord(
            last_attempt_at_ms=now_ms,
            last_success_at_ms=previous.last_success_at_ms if previous else None,
            latest_version=previous.latest_version if previous else None,
            last_failure_reason=failure,
        )
    return ReleaseCheckRecord(
        last_attempt_at_ms=now_ms,
        last_success_at_ms=now_ms,
        latest_version=latest_version,
        last_failure_reason=None,
    )


def short_commit(commit: str) -> str:
    """40/64 자리 hex 해시의 앞 7자. 해시가 아니면(unknown 등) 빈 문자열."""
    if _COMMIT_HASH_PATTERN.fullmatch(commit) is None:
        return ""
    return commit[:COMMIT_SHORT_LENGTH]


def _is_newer(latest: SemVer, installed: SemVer | None) -> bool:
    """설치 버전을 모르면(도입 이전 설치) 어떤 릴리스보다 오래된 것으로 본다(결정 UN3)."""
    return installed is None or latest > installed


def build_harness_version_view(
    installed: InstalledHarness | None, record: ReleaseCheckRecord | None
) -> HarnessVersionView | None:
    """화면용 뷰. 설치 기록이 없으면 None(템플릿이 표기·알림을 모두 숨긴다).

    record 가 None 이면(원격 확인 스위치 꺼짐·아직 확인 전) 알림 없이 설치 버전 표기만 남는다.
    설치 버전이 최신보다 크면(관리자가 태그 푸시 전에 설치) 알림이 없다.
    """
    if installed is None:
        return None
    installed_version = parse_semver(installed.harness_version) if installed.harness_version else None
    latest_version = parse_semver(record.latest_version) if record and record.latest_version else None
    return HarnessVersionView(
        installed_version=installed.harness_version if installed_version else "",
        installed_commit_short=short_commit(installed.installed_from_commit),
        installed_at=installed.installed_at,
        latest_version=record.latest_version if record and latest_version else "",
        is_update_available=latest_version is not None and _is_newer(latest_version, installed_version),
    )
