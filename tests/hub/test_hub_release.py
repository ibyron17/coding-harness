"""hub_release(★순수) 단위 테스트 — 하네스 릴리스 버전 비교·확인 주기·뷰 조립.

파일시스템·git·시각 무접촉이다. 설치 기록 읽기·ls-remote 실행은
tests/hub/test_hub_release_read.py 가 맡는다(docs/prps/harness-versioning.md §5.5.6).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_release  # noqa: E402

COMMIT_40 = "a" * 40
COMMIT_64 = "b" * 64


def _tag_line(version_text: str, commit: str = COMMIT_40) -> str:
    return f"{commit}\trefs/tags/v{version_text}"


class ParseSemverTest(unittest.TestCase):
    def test_accepts_plain_x_y_z(self) -> None:
        self.assertEqual(hub_release.parse_semver("1.2.3"), (1, 2, 3))
        self.assertEqual(hub_release.parse_semver("0.0.0"), (0, 0, 0))
        self.assertEqual(hub_release.parse_semver("10.20.30"), (10, 20, 30))

    def test_digit_limit_is_nine_per_part(self) -> None:
        """자릿수 상한(MAX_VERSION_NUMBER_DIGITS=9) — 경계 값은 받고 한 자리 넘으면 None 이다."""
        self.assertEqual(hub_release.MAX_VERSION_NUMBER_DIGITS, 9)
        at_limit = "9" * 9
        self.assertEqual(hub_release.parse_semver(f"{at_limit}.{at_limit}.{at_limit}"), (999999999,) * 3)
        over_limit = "1" + "0" * 9
        for rejected in (f"{over_limit}.0.0", f"0.{over_limit}.0", f"0.0.{over_limit}"):
            with self.subTest(rejected=rejected):
                self.assertIsNone(hub_release.parse_semver(rejected))

    def test_thousands_of_digits_are_rejected_without_raising(self) -> None:
        """int() 변환 한도(4300자리)에 닿기 전에 형식 검사에서 걸러 ValueError 가 나지 않는다."""
        for digit_count in (30, 4301, 5000):
            with self.subTest(digit_count=digit_count):
                self.assertIsNone(hub_release.parse_semver("1.0." + "9" * digit_count))

    def test_rejects_everything_else(self) -> None:
        for rejected in ("1.2", "01.2.3", "1.02.3", "v1.2.3", "1.2.3-rc.1", "1.2.3+sha", " 1.2.3", "1.2.3\n", "", "1.2.x"):
            with self.subTest(rejected=rejected):
                self.assertIsNone(hub_release.parse_semver(rejected))


class LatestReleaseVersionTest(unittest.TestCase):
    def test_compares_numerically_not_lexically(self) -> None:
        stdout = "\n".join([_tag_line("1.9.0"), _tag_line("1.10.0"), _tag_line("1.2.0")])
        self.assertEqual(hub_release.latest_release_version(stdout), "1.10.0")

    def test_ignores_tags_outside_the_release_format(self) -> None:
        stdout = "\n".join(
            [_tag_line("1.0"), f"{COMMIT_40}\trefs/tags/release-1", _tag_line("1.0.0^{}"), _tag_line("2.0.0-rc.1"), _tag_line("1.0.0")]
        )
        self.assertEqual(hub_release.latest_release_version(stdout), "1.0.0")

    def test_ignores_tags_whose_numbers_exceed_the_digit_limit(self) -> None:
        """상한 초과 태그는 형식 밖 태그와 같이 무시된다 — 정상 태그가 최신이 된다."""
        stdout = "\n".join([_tag_line("1.0.0"), _tag_line("1.0." + "9" * 30), _tag_line("1.0." + "9" * 5000), _tag_line("1.1.0")])
        self.assertEqual(hub_release.latest_release_version(stdout), "1.1.0")

    def test_only_over_limit_tags_means_no_release(self) -> None:
        self.assertIsNone(hub_release.latest_release_version(_tag_line("1.0." + "9" * 5000)))

    def test_ignores_lines_whose_hash_is_not_40_or_64_hex(self) -> None:
        stdout = "\n".join(
            [_tag_line("9.0.0", "z" * 40), _tag_line("9.0.0", "a" * 39), _tag_line("9.0.0", "a" * 41), _tag_line("1.0.0", COMMIT_64)]
        )
        self.assertEqual(hub_release.latest_release_version(stdout), "1.0.0")

    def test_empty_or_no_matching_output_is_none(self) -> None:
        self.assertIsNone(hub_release.latest_release_version(""))
        self.assertIsNone(hub_release.latest_release_version("garbage\n\n"))


class ShouldAttemptReleaseCheckTest(unittest.TestCase):
    INTERVAL_MS = 1000

    def test_no_previous_attempt_means_attempt(self) -> None:
        self.assertTrue(hub_release.should_attempt_release_check(5000, None, self.INTERVAL_MS))

    def test_inside_the_interval_means_wait(self) -> None:
        self.assertFalse(hub_release.should_attempt_release_check(5999, 5000, self.INTERVAL_MS))

    def test_exact_boundary_means_attempt(self) -> None:
        self.assertTrue(hub_release.should_attempt_release_check(6000, 5000, self.INTERVAL_MS))

    def test_wall_clock_going_backwards_means_attempt(self) -> None:
        self.assertTrue(hub_release.should_attempt_release_check(4000, 5000, self.INTERVAL_MS))

    def test_default_interval_is_six_hours(self) -> None:
        self.assertEqual(hub_release.RELEASE_CHECK_INTERVAL_MS, 6 * 60 * 60 * 1000)

    def test_manual_min_interval_is_one_minute(self) -> None:
        self.assertEqual(hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS, 60 * 1000)

    def test_manual_interval_is_shorter_than_the_automatic_interval(self) -> None:
        """수동 간격이 자동 주기보다 길면 수동 확인이 자동 확인에 가려 의미가 없다(RR8)."""
        self.assertLess(hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS, hub_release.RELEASE_CHECK_INTERVAL_MS)

    def test_manual_interval_boundary(self) -> None:
        manual_interval_ms = hub_release.MANUAL_RELEASE_CHECK_MIN_INTERVAL_MS
        self.assertFalse(hub_release.should_attempt_release_check(5000 + 59_999, 5000, manual_interval_ms))
        self.assertTrue(hub_release.should_attempt_release_check(5000 + 60_000, 5000, manual_interval_ms))


class NextReleaseCheckRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = hub_release.ReleaseCheckRecord(
            last_attempt_at_ms=100, last_success_at_ms=90, latest_version="1.1.0", last_failure_reason=None
        )

    def test_failure_keeps_previous_latest_version_and_success_time(self) -> None:
        record = hub_release.next_release_check_record(self.previous, 200, None, "timeout")
        self.assertEqual(record.latest_version, "1.1.0")
        self.assertEqual(record.last_success_at_ms, 90)
        self.assertEqual(record.last_attempt_at_ms, 200)
        self.assertEqual(record.last_failure_reason, "timeout")

    def test_success_updates_latest_and_clears_failure(self) -> None:
        failed = hub_release.next_release_check_record(self.previous, 200, None, "remote_error")
        record = hub_release.next_release_check_record(failed, 300, "1.2.0", None)
        self.assertEqual(record.latest_version, "1.2.0")
        self.assertEqual(record.last_success_at_ms, 300)
        self.assertIsNone(record.last_failure_reason)

    def test_first_failure_without_previous_has_no_latest(self) -> None:
        record = hub_release.next_release_check_record(None, 200, None, "git_unavailable")
        self.assertIsNone(record.latest_version)
        self.assertIsNone(record.last_success_at_ms)
        self.assertEqual(record.last_failure_reason, "git_unavailable")

    def test_does_not_mutate_the_previous_record(self) -> None:
        hub_release.next_release_check_record(self.previous, 200, "9.9.9", None)
        self.assertEqual(self.previous.latest_version, "1.1.0")


class BuildHarnessVersionViewTest(unittest.TestCase):
    def _installed(self, version: str | None, commit: str = COMMIT_40) -> hub_release.InstalledHarness:
        return hub_release.InstalledHarness(
            harness_version=version, installed_from_commit=commit, installed_at="2026-10-13T05:00:00Z", repo_path="/repo"
        )

    def _record(self, latest: str | None) -> hub_release.ReleaseCheckRecord:
        return hub_release.ReleaseCheckRecord(
            last_attempt_at_ms=1, last_success_at_ms=1, latest_version=latest, last_failure_reason=None
        )

    def test_newer_release_raises_the_alert(self) -> None:
        view = hub_release.build_harness_version_view(self._installed("1.0.0"), self._record("1.1.0"))
        assert view is not None
        self.assertTrue(view.is_update_available)
        self.assertEqual((view.installed_version, view.latest_version), ("1.0.0", "1.1.0"))
        self.assertEqual(view.installed_commit_short, "aaaaaaa")
        self.assertEqual(view.installed_at, "2026-10-13T05:00:00Z")

    def test_same_version_has_no_alert(self) -> None:
        view = hub_release.build_harness_version_view(self._installed("1.1.0"), self._record("1.1.0"))
        assert view is not None
        self.assertFalse(view.is_update_available)

    def test_installed_newer_than_latest_has_no_alert(self) -> None:
        view = hub_release.build_harness_version_view(self._installed("1.2.0"), self._record("1.1.0"))
        assert view is not None
        self.assertFalse(view.is_update_available)

    def test_pre_versioning_install_counts_as_older_than_any_release(self) -> None:
        view = hub_release.build_harness_version_view(self._installed(None, "unknown"), self._record("1.0.0"))
        assert view is not None
        self.assertTrue(view.is_update_available)
        self.assertEqual((view.installed_version, view.installed_commit_short), ("", ""))

    def test_no_known_latest_means_no_alert(self) -> None:
        view = hub_release.build_harness_version_view(self._installed("1.0.0"), self._record(None))
        assert view is not None
        self.assertFalse(view.is_update_available)
        self.assertEqual(view.latest_version, "")

    def test_missing_record_shows_the_installed_version_only(self) -> None:
        """원격 확인 스위치가 꺼진 경우 — 표기는 남고 알림만 없다."""
        view = hub_release.build_harness_version_view(self._installed("1.0.0"), None)
        assert view is not None
        self.assertEqual(view.installed_version, "1.0.0")
        self.assertFalse(view.is_update_available)
        self.assertEqual(view.latest_version, "")

    def test_no_install_record_means_no_view(self) -> None:
        self.assertIsNone(hub_release.build_harness_version_view(None, self._record("1.0.0")))

    def test_corrupt_cached_latest_is_ignored(self) -> None:
        view = hub_release.build_harness_version_view(self._installed("1.0.0"), self._record("not-a-version"))
        assert view is not None
        self.assertFalse(view.is_update_available)
        self.assertEqual(view.latest_version, "")

    def test_cached_latest_over_the_digit_limit_neither_raises_nor_alerts(self) -> None:
        """release_check.json 이 상한 초과 값을 담고 있어도(옛 버전이 쓴 파일·손으로 고친 파일) 알림 없이 숨긴다."""
        for oversized in ("1.0." + "9" * 30, "1.0." + "9" * 5000):
            with self.subTest(digits=len(oversized)):
                view = hub_release.build_harness_version_view(self._installed("1.0.0"), self._record(oversized))
                assert view is not None
                self.assertFalse(view.is_update_available)
                self.assertEqual(view.latest_version, "")

    def test_installed_version_over_the_digit_limit_is_shown_as_unknown(self) -> None:
        view = hub_release.build_harness_version_view(self._installed("1.0." + "9" * 5000), self._record("1.0.0"))
        assert view is not None
        self.assertEqual(view.installed_version, "")

    def test_short_commit_requires_a_real_hash(self) -> None:
        self.assertEqual(hub_release.short_commit(COMMIT_64), "bbbbbbb")
        self.assertEqual(hub_release.short_commit("unknown"), "")
        self.assertEqual(hub_release.short_commit("abc"), "")


if __name__ == "__main__":
    unittest.main()
