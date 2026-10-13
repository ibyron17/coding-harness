"""hub_release_read(I/O) 단위 테스트 — 설치 기록 읽기 · 릴리스 확인 기록 왕복 · git ls-remote 실행 ·
서버 1사이클 · 수집용 뷰(docs/prps/harness-versioning.md §5.5.6).

네트워크를 쓰지 않는다 — 실제 git 실행은 로컬 bare 저장소를 `origin` 으로 건 경우(결정적)뿐이고,
나머지 실패 분류는 subprocess.Popen 을 가짜로 바꿔 본다. 모듈 상수(INSTALL_RECORD_PATH 등)는
setUp 에서 임시 디렉터리로 바꿔 끼우고 tearDown 에서 되돌린다.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402
import hub_release  # noqa: E402
import hub_release_read  # noqa: E402

GIT_IDENTITY_ARGS = ["-c", "user.name=tester", "-c", "user.email=tester@example.invalid"]


class _TempHomeTestCase(unittest.TestCase):
    """INSTALL_RECORD_PATH·RELEASE_CHECK_PATH 를 임시 디렉터리로 바꿔 끼운다."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.temp_dir = Path(self._temp.name)
        self.original_install_path = hub_release_read.INSTALL_RECORD_PATH
        self.original_release_path = hub_release_read.RELEASE_CHECK_PATH
        hub_release_read.INSTALL_RECORD_PATH = self.temp_dir / ".coding-harness.json"
        hub_release_read.RELEASE_CHECK_PATH = self.temp_dir / "hub" / "release_check.json"

    def tearDown(self) -> None:
        hub_release_read.INSTALL_RECORD_PATH = self.original_install_path
        hub_release_read.RELEASE_CHECK_PATH = self.original_release_path

    def write_install_record(self, **overrides) -> None:
        record = {
            "version": 3,
            "repo_path": str(self.temp_dir / "repo"),
            "scope": "user",
            "installed_at": "2026-10-13T05:00:00Z",
            "installed_from_commit": "c" * 40,
            "harness_version": "1.0.0",
        }
        record.update(overrides)
        hub_release_read.INSTALL_RECORD_PATH.write_text(json.dumps(record), encoding="utf-8")


class ReadInstalledHarnessTest(_TempHomeTestCase):
    def test_missing_file_is_none_without_warning(self) -> None:
        self.assertEqual(hub_release_read.read_installed_harness(), (None, ()))

    def test_valid_record_is_parsed(self) -> None:
        self.write_install_record()
        installed, warnings = hub_release_read.read_installed_harness()
        self.assertEqual(warnings, ())
        self.assertEqual(
            installed,
            hub_release.InstalledHarness(
                harness_version="1.0.0",
                installed_from_commit="c" * 40,
                installed_at="2026-10-13T05:00:00Z",
                repo_path=str(self.temp_dir / "repo"),
            ),
        )

    def test_broken_json_warns(self) -> None:
        hub_release_read.INSTALL_RECORD_PATH.write_text("{not json", encoding="utf-8")
        installed, warnings = hub_release_read.read_installed_harness()
        self.assertIsNone(installed)
        self.assertEqual(len(warnings), 1)
        self.assertIn(str(hub_release_read.INSTALL_RECORD_PATH), warnings[0])

    def test_pre_versioning_record_has_no_harness_version(self) -> None:
        hub_release_read.INSTALL_RECORD_PATH.write_text(
            json.dumps({"version": 3, "repo_path": "/r", "installed_from_commit": "unknown"}), encoding="utf-8"
        )
        installed, _warnings = hub_release_read.read_installed_harness()
        assert installed is not None
        self.assertIsNone(installed.harness_version)
        self.assertEqual(installed.installed_at, "")

    def test_unknown_and_malformed_versions_become_none(self) -> None:
        for value in ("unknown", "1.0", "v1.0.0", 7, None):
            with self.subTest(value=value):
                self.write_install_record(harness_version=value)
                installed, _warnings = hub_release_read.read_installed_harness()
                assert installed is not None
                self.assertIsNone(installed.harness_version)

    def test_record_without_usable_repo_path_warns(self) -> None:
        for broken in ({"repo_path": ""}, {"repo_path": 5}, {"repo_path": None}):
            with self.subTest(broken=broken):
                self.write_install_record(**broken)
                installed, warnings = hub_release_read.read_installed_harness()
                self.assertIsNone(installed)
                self.assertEqual(len(warnings), 1)

    def test_non_object_json_warns(self) -> None:
        hub_release_read.INSTALL_RECORD_PATH.write_text("[1, 2]", encoding="utf-8")
        installed, warnings = hub_release_read.read_installed_harness()
        self.assertIsNone(installed)
        self.assertEqual(len(warnings), 1)


class ReleaseCheckRecordFileTest(_TempHomeTestCase):
    RECORD = hub_release.ReleaseCheckRecord(
        last_attempt_at_ms=1791000000000, last_success_at_ms=1791000000000,
        latest_version="1.1.0", last_failure_reason=None,
    )

    def test_missing_file_is_none(self) -> None:
        self.assertIsNone(hub_release_read.read_release_check_record())

    def test_write_then_read_round_trips_and_creates_the_directory(self) -> None:
        hub_release_read.write_release_check_record(self.RECORD)
        self.assertEqual(hub_release_read.read_release_check_record(), self.RECORD)

    def test_round_trips_failure_with_no_success_yet(self) -> None:
        failed = hub_release.ReleaseCheckRecord(5, None, None, "timeout")
        hub_release_read.write_release_check_record(failed)
        self.assertEqual(hub_release_read.read_release_check_record(), failed)

    def test_broken_or_mistyped_file_is_none(self) -> None:
        hub_release_read.RELEASE_CHECK_PATH.parent.mkdir(parents=True)
        for text in ("{not json", "[]", json.dumps({"last_attempt_at_ms": "x"}), json.dumps({"latest_version": "1.0.0"}),
                     json.dumps({"last_attempt_at_ms": True, "last_success_at_ms": None, "latest_version": None, "last_failure_reason": None})):
            with self.subTest(text=text):
                hub_release_read.RELEASE_CHECK_PATH.write_text(text, encoding="utf-8")
                self.assertIsNone(hub_release_read.read_release_check_record())

    def test_unwritable_location_raises_oserror_for_the_caller(self) -> None:
        hub_release_read.RELEASE_CHECK_PATH = self.temp_dir / "blocker" / "release_check.json"
        (self.temp_dir / "blocker").write_text("a file where a directory must be", encoding="utf-8")
        with self.assertRaises(OSError):
            hub_release_read.write_release_check_record(self.RECORD)


class FetchWithRealGitTest(unittest.TestCase):
    """로컬 bare 저장소를 origin 으로 건 실제 git 실행 — 네트워크 없음, 결정적."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.temp_dir = Path(self._temp.name)
        self.bare = self.temp_dir / "origin.git"
        self.work = self.temp_dir / "work"
        self.git("init", "--bare", "-q", str(self.bare), cwd=self.temp_dir)
        self.git("init", "-q", str(self.work), cwd=self.temp_dir)
        self.git(*GIT_IDENTITY_ARGS, "commit", "--allow-empty", "-q", "-m", "release", cwd=self.work)
        self.git("remote", "add", "origin", str(self.bare), cwd=self.work)

    def git(self, *args: str, cwd: Path) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    def push_tags(self, *tag_names: str) -> None:
        for tag_name in tag_names:
            self.git("tag", tag_name, cwd=self.work)
        self.git("push", "-q", "origin", "--tags", cwd=self.work)

    def test_returns_the_highest_release_tag_ignoring_other_tags(self) -> None:
        self.push_tags("v1.0.0", "v1.10.0", "v1.9.0", "nightly", "v2.0.0-rc.1")
        self.assertEqual(hub_release_read.fetch_latest_release_version(str(self.work)), ("1.10.0", None))

    def test_remote_without_release_tags_is_a_successful_none(self) -> None:
        self.push_tags("nightly")
        self.assertEqual(hub_release_read.fetch_latest_release_version(str(self.work)), (None, None))

    def test_does_not_change_the_repository(self) -> None:
        self.push_tags("v1.0.0")
        before = sorted(path.relative_to(self.work).as_posix() for path in (self.work / ".git").rglob("*") if path.is_file())
        hub_release_read.fetch_latest_release_version(str(self.work))
        after = sorted(path.relative_to(self.work).as_posix() for path in (self.work / ".git").rglob("*") if path.is_file())
        self.assertEqual(before, after)

    def test_missing_origin_is_remote_error(self) -> None:
        self.git("remote", "remove", "origin", cwd=self.work)
        self.assertEqual(hub_release_read.fetch_latest_release_version(str(self.work)), (None, "remote_error"))

    def test_unreachable_origin_is_remote_error(self) -> None:
        self.git("remote", "set-url", "origin", str(self.temp_dir / "does-not-exist.git"), cwd=self.work)
        self.assertEqual(hub_release_read.fetch_latest_release_version(str(self.work)), (None, "remote_error"))


class _FakeProcess:
    """subprocess.Popen 의 최소 대역. communicate 첫 호출에서 communicate_error 를 던질 수 있다."""

    pid = 424242

    def __init__(self, returncode: int = 0, stdout: bytes = b"", communicate_error: BaseException | None = None) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.communicate_error = communicate_error
        self.communicate_timeouts: list[float | None] = []

    def communicate(self, timeout: float | None = None) -> tuple[bytes, None]:
        self.communicate_timeouts.append(timeout)
        if self.communicate_error is not None and len(self.communicate_timeouts) == 1:
            raise self.communicate_error
        return self.stdout, None


class FetchWithFakeProcessTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.repo_path = self._temp.name

    def fetch_with(self, fake_process: _FakeProcess) -> tuple[tuple[str | None, str | None], mock.MagicMock]:
        with mock.patch.object(hub_release_read.subprocess, "Popen", return_value=fake_process) as popen:
            with mock.patch.object(hub_release_read.os, "killpg") as killpg:
                result = hub_release_read.fetch_latest_release_version(self.repo_path)
        self.popen = popen
        return result, killpg

    def test_command_is_an_argv_list_without_a_shell_and_never_prompts(self) -> None:
        stdout = f"{'a' * 40}\trefs/tags/v1.2.3\n".encode()
        (result, _killpg) = self.fetch_with(_FakeProcess(stdout=stdout))
        self.assertEqual(result, ("1.2.3", None))
        args, kwargs = self.popen.call_args
        self.assertEqual(args[0], ["git", "-C", self.repo_path, "ls-remote", "--tags", "--refs", "origin"])
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertTrue(kwargs["start_new_session"])
        self.assertNotIn("shell", kwargs)

    def test_timeout_is_the_documented_constant_and_kills_the_process_group(self) -> None:
        fake_process = _FakeProcess(communicate_error=subprocess.TimeoutExpired("git", 15))
        (result, killpg) = self.fetch_with(fake_process)
        self.assertEqual(result, (None, "timeout"))
        self.assertEqual(fake_process.communicate_timeouts[0], hub_release_read.GIT_LS_REMOTE_TIMEOUT_SECONDS)
        self.assertEqual(hub_release_read.GIT_LS_REMOTE_TIMEOUT_SECONDS, 15)
        killpg.assert_called_once_with(fake_process.pid, signal.SIGKILL)
        self.assertEqual(len(fake_process.communicate_timeouts), 2)    # 종료 뒤 회수

    def test_group_already_gone_after_timeout_is_not_an_error(self) -> None:
        fake_process = _FakeProcess(communicate_error=subprocess.TimeoutExpired("git", 15))
        with mock.patch.object(hub_release_read.subprocess, "Popen", return_value=fake_process):
            with mock.patch.object(hub_release_read.os, "killpg", side_effect=ProcessLookupError):
                result = hub_release_read.fetch_latest_release_version(self.repo_path)
        self.assertEqual(result, (None, "timeout"))

    def test_missing_git_binary_is_git_unavailable(self) -> None:
        with mock.patch.object(hub_release_read.subprocess, "Popen", side_effect=FileNotFoundError):
            result = hub_release_read.fetch_latest_release_version(self.repo_path)
        self.assertEqual(result, (None, "git_unavailable"))

    def test_nonzero_exit_is_remote_error(self) -> None:
        (result, _killpg) = self.fetch_with(_FakeProcess(returncode=128))
        self.assertEqual(result, (None, "remote_error"))

    def test_oversized_output_is_rejected(self) -> None:
        oversized = b"x" * (hub_release_read.GIT_LS_REMOTE_MAX_OUTPUT_BYTES + 1)
        (result, _killpg) = self.fetch_with(_FakeProcess(stdout=oversized))
        self.assertEqual(result, (None, "output_too_large"))

    def test_output_exactly_at_the_limit_is_accepted(self) -> None:
        at_limit = b"x" * hub_release_read.GIT_LS_REMOTE_MAX_OUTPUT_BYTES
        (result, _killpg) = self.fetch_with(_FakeProcess(stdout=at_limit))
        self.assertEqual(result, (None, None))

    def test_directory_that_does_not_exist_is_repo_missing_without_running_git(self) -> None:
        with mock.patch.object(hub_release_read.subprocess, "Popen") as popen:
            result = hub_release_read.fetch_latest_release_version(str(Path(self.repo_path) / "gone"))
        self.assertEqual(result, (None, "repo_missing"))
        popen.assert_not_called()

    def test_empty_repo_path_is_repo_missing(self) -> None:
        self.assertEqual(hub_release_read.fetch_latest_release_version(""), (None, "repo_missing"))


class FetchWithHungGitTest(unittest.TestCase):
    """멈춘 git(과 그 자식)이 제한 시간 뒤 프로세스 그룹째 사라지는지 — 가짜 git 스크립트를 PATH 앞에 둔다."""

    def test_timeout_kills_the_child_the_hung_git_spawned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp_dir = Path(temp_name)
            fake_git = temp_dir / "git"
            child_pid_file = temp_dir / "child.pid"
            fake_git.write_text(f"#!/bin/bash\nsleep 300 &\necho $! > '{child_pid_file}'\nwait\n", encoding="utf-8")
            fake_git.chmod(0o755)
            patched_environ = {**os.environ, "PATH": f"{temp_dir}{os.pathsep}{os.environ['PATH']}"}
            with mock.patch.dict(os.environ, patched_environ, clear=True):
                with mock.patch.object(hub_release_read, "GIT_LS_REMOTE_TIMEOUT_SECONDS", 1):
                    result = hub_release_read.fetch_latest_release_version(temp_name)
            self.assertEqual(result, (None, "timeout"))
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    return
                time.sleep(0.05)
            os.kill(child_pid, signal.SIGKILL)
            self.fail("제한 시간 뒤에도 git 의 자식 프로세스가 남아 있음")


class RunReleaseCheckCycleTest(_TempHomeTestCase):
    NOW_MS = 1791000000000

    def test_success_writes_the_latest_version(self) -> None:
        self.write_install_record()
        with mock.patch.object(hub_release_read, "fetch_latest_release_version", return_value=("1.1.0", None)) as fetch:
            record = hub_release_read.run_release_check_cycle(self.NOW_MS)
        fetch.assert_called_once_with(str(self.temp_dir / "repo"))
        self.assertEqual(record.latest_version, "1.1.0")
        self.assertEqual(hub_release_read.read_release_check_record(), record)

    def test_failure_keeps_the_previous_latest_version(self) -> None:
        self.write_install_record()
        hub_release_read.write_release_check_record(hub_release.ReleaseCheckRecord(1, 1, "1.1.0", None))
        with mock.patch.object(hub_release_read, "fetch_latest_release_version", return_value=(None, "timeout")):
            record = hub_release_read.run_release_check_cycle(self.NOW_MS)
        self.assertEqual((record.latest_version, record.last_failure_reason, record.last_attempt_at_ms), ("1.1.0", "timeout", self.NOW_MS))

    def test_without_an_install_record_it_records_the_failure_and_skips_git(self) -> None:
        with mock.patch.object(hub_release_read, "fetch_latest_release_version") as fetch:
            record = hub_release_read.run_release_check_cycle(self.NOW_MS)
        fetch.assert_not_called()
        self.assertEqual(record.last_failure_reason, "no_install_record")
        self.assertEqual(hub_release_read.read_release_check_record(), record)

    def _fake_git(self, stdout_text: str) -> mock.MagicMock:
        fake_process = _FakeProcess(stdout=stdout_text.encode("utf-8"))
        return mock.patch.object(hub_release_read.subprocess, "Popen", return_value=fake_process)

    def test_over_limit_digit_tag_in_the_remote_output_is_ignored_and_the_record_is_written(self) -> None:
        """4300자리 초과 태그가 섞여도 사이클이 예외 없이 끝나고 정상 태그가 최신으로 기록된다."""
        self.write_install_record()
        (self.temp_dir / "repo").mkdir()
        commit = "a" * 40
        stdout_text = f"{commit}\trefs/tags/v1.0.0\n{commit}\trefs/tags/v1.0.{'9' * 5000}\n"
        with self._fake_git(stdout_text):
            record = hub_release_read.run_release_check_cycle(self.NOW_MS)
        self.assertEqual((record.latest_version, record.last_failure_reason), ("1.0.0", None))
        self.assertEqual(hub_release_read.read_release_check_record(), record)

    def test_a_parse_error_is_recorded_as_a_failure_not_raised(self) -> None:
        """방어선 — 출력 해석 단계가 ValueError 를 던져도 사이클은 사유 parse_error 를 기록에 남기고 끝난다."""
        self.write_install_record()
        (self.temp_dir / "repo").mkdir()
        hub_release_read.write_release_check_record(hub_release.ReleaseCheckRecord(1, 1, "1.1.0", None))
        with self._fake_git("whatever\n"):
            with mock.patch.object(hub_release, "latest_release_version", side_effect=ValueError("boom")):
                record = hub_release_read.run_release_check_cycle(self.NOW_MS)
        self.assertEqual((record.last_failure_reason, record.latest_version), ("parse_error", "1.1.0"))
        self.assertEqual(hub_release_read.read_release_check_record(), record)

    def test_unwritable_record_does_not_raise_and_still_returns_the_result(self) -> None:
        self.write_install_record()
        with mock.patch.object(hub_release_read, "fetch_latest_release_version", return_value=("1.1.0", None)):
            with mock.patch.object(hub_release_read, "write_release_check_record", side_effect=OSError("disk full")):
                record = hub_release_read.run_release_check_cycle(self.NOW_MS)
        self.assertEqual(record.latest_version, "1.1.0")


class ReadHarnessVersionViewTest(_TempHomeTestCase):
    def test_switch_on_combines_install_record_and_cached_latest(self) -> None:
        self.write_install_record()
        hub_release_read.write_release_check_record(hub_release.ReleaseCheckRecord(1, 1, "1.1.0", None))
        view, warnings = hub_release_read.read_harness_version_view(hub_model.HubConfig(update_check_enabled=True))
        assert view is not None
        self.assertEqual(warnings, ())
        self.assertTrue(view.is_update_available)
        self.assertEqual((view.installed_version, view.latest_version), ("1.0.0", "1.1.0"))

    def test_switch_off_ignores_the_cache_but_still_shows_the_installed_version(self) -> None:
        self.write_install_record()
        hub_release_read.write_release_check_record(hub_release.ReleaseCheckRecord(1, 1, "9.9.9", None))
        view, _warnings = hub_release_read.read_harness_version_view(hub_model.HubConfig(update_check_enabled=False))
        assert view is not None
        self.assertFalse(view.is_update_available)
        self.assertEqual((view.installed_version, view.latest_version), ("1.0.0", ""))

    def test_no_install_record_is_no_view(self) -> None:
        self.assertEqual(hub_release_read.read_harness_version_view(hub_model.HubConfig()), (None, ()))

    def test_broken_install_record_surfaces_a_warning(self) -> None:
        hub_release_read.INSTALL_RECORD_PATH.write_text("{", encoding="utf-8")
        view, warnings = hub_release_read.read_harness_version_view(hub_model.HubConfig())
        self.assertIsNone(view)
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
