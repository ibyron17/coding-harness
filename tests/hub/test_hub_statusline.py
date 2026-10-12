"""hub_statusline.py 단위 테스트. 실제 ~/.claude 는 건드리지 않고 hub_collect 의 모듈 상수를
임시 디렉토리로 바꿔치기한 뒤 원상복구한다(WriteHubHtmlAtomicityTest 의 setUp/tearDown 패턴).
docs/prps/hub-usage-reset-time-and-refresh.md 「테스트 계획」 케이스 R26~R29 +
docs/prps/hub-card-cleanup-and-usage-source.md 「테스트 계획」 케이스 N39~N42(퍼센트도
캡처값 비교에 들어간 뒤의 회귀 — 결정 P4).
"""

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402
import hub_session_cost  # noqa: E402
import hub_statusline  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다 —
# 이 파일 맨 아래 unittest.main() 진입점이 이미 후자를 지원하고 있었다.
try:
    from .swallowed_exception_guard import SwallowedExceptionGuardMixin
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from swallowed_exception_guard import SwallowedExceptionGuardMixin  # noqa: E402

ONE_HOUR_SECONDS = 60 * 60


def _rate_limits_payload(
    now_s: int,
    session_hours_from_now: float = 2.0,
    weekly_hours_from_now: float = 48.0,
    session_used_percentage: float = 23,
    weekly_used_percentage: float = 41,
) -> str:
    payload = {
        "rate_limits": {
            "five_hour": {
                "used_percentage": session_used_percentage,
                "resets_at": now_s + int(session_hours_from_now * ONE_HOUR_SECONDS),
            },
            "seven_day": {
                "used_percentage": weekly_used_percentage,
                "resets_at": now_s + int(weekly_hours_from_now * ONE_HOUR_SECONDS),
            },
        }
    }
    return json.dumps(payload)


class HubStatuslineEntrypointTest(SwallowedExceptionGuardMixin, unittest.TestCase):
    """statusline 진입점 시나리오의 공통 베이스. 삼킨 예외 가드는 믹스인이 담당한다(PRP §4.5)."""

    guarded_entrypoint_module = hub_statusline

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_session_costs_dir = hub_session_cost.SESSION_COSTS_DIR
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_session_cost.SESSION_COSTS_DIR = self.temp_dir / "session_costs"

    def tearDown(self) -> None:
        self.temp_dir.chmod(0o755)
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_session_cost.SESSION_COSTS_DIR = self.original_session_costs_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_with_stdin(self, text: str) -> tuple[int, str]:
        captured = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(text)), redirect_stdout(captured):
            exit_code = hub_statusline.main()
        return exit_code, captured.getvalue()


class NormalPayloadTest(HubStatuslineEntrypointTest):
    """케이스 R26 — 정상 페이로드는 캡처 파일과 상태줄 한 줄을 만든다."""

    def test_r26_writes_capture_and_prints_summary(self) -> None:
        now_s = int(time.time())
        exit_code, output = self._run_with_stdin(_rate_limits_payload(now_s))

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "세션 23% · 주간 41%")
        self.assertTrue(hub_collect.RATE_LIMITS_PATH.is_file())
        capture, warnings = hub_collect.read_rate_limit_capture()
        self.assertIsNotNone(capture)
        self.assertEqual(warnings, ())


class SameReplayDoesNotRewriteTest(HubStatuslineEntrypointTest):
    """케이스 R27·N40 — 완전히 같은 페이로드(퍼센트 포함)로 재실행하면 파일을 다시 쓰지
    않는다(결정 S3·P4 회귀 방지, GOTCHA 4 — captured_at_ms 를 비교에 넣으면 이 테스트가
    깨진다)."""

    def test_r27_identical_payload_leaves_mtime_unchanged(self) -> None:
        text = _rate_limits_payload(int(time.time()))
        self._run_with_stdin(text)
        mtime_before = hub_collect.RATE_LIMITS_PATH.stat().st_mtime_ns

        self._run_with_stdin(text)
        mtime_after = hub_collect.RATE_LIMITS_PATH.stat().st_mtime_ns

        self.assertEqual(mtime_before, mtime_after)


class ChangedResetsRewriteTest(HubStatuslineEntrypointTest):
    """케이스 R28 — 리셋 시각이 달라진 페이로드는 파일을 갱신한다."""

    def test_r28_different_reset_times_rewrite_the_file(self) -> None:
        now_s = int(time.time())
        self._run_with_stdin(_rate_limits_payload(now_s, session_hours_from_now=2.0))
        mtime_before = hub_collect.RATE_LIMITS_PATH.stat().st_mtime_ns

        self._run_with_stdin(_rate_limits_payload(now_s, session_hours_from_now=3.0))
        mtime_after = hub_collect.RATE_LIMITS_PATH.stat().st_mtime_ns

        self.assertNotEqual(mtime_before, mtime_after)


class ChangedPercentRewriteTest(HubStatuslineEntrypointTest):
    """케이스 N39 — 리셋 시각은 그대로인데 퍼센트만 달라진 페이로드도 파일을 갱신한다
    (결정 P4 — 비교를 네 값으로 확장한 회귀 방지. 리셋만 비교했다면 이 케이스는 안 써진다)."""

    def test_n39_percent_only_change_rewrites_the_file(self) -> None:
        now_s = int(time.time())
        self._run_with_stdin(_rate_limits_payload(now_s, session_used_percentage=23))
        mtime_before = hub_collect.RATE_LIMITS_PATH.stat().st_mtime_ns

        self._run_with_stdin(_rate_limits_payload(now_s, session_used_percentage=24))
        mtime_after = hub_collect.RATE_LIMITS_PATH.stat().st_mtime_ns

        self.assertNotEqual(mtime_before, mtime_after)


class FailureIsolationTest(HubStatuslineEntrypointTest):
    """케이스 R29 — 깨진 stdin·rate_limits 없음·쓰기 불가 디렉토리 모두 예외 없이 exit 0."""

    def test_r29_broken_stdin_never_raises(self) -> None:
        exit_code, _output = self._run_with_stdin("{not json")
        self.assertEqual(exit_code, 0)
        self.assertFalse(hub_collect.RATE_LIMITS_PATH.exists())

    def test_r29_missing_rate_limits_never_raises_and_writes_nothing(self) -> None:
        exit_code, output = self._run_with_stdin(json.dumps({"hookEventName": "Status"}))
        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "")
        self.assertFalse(hub_collect.RATE_LIMITS_PATH.exists())

    def test_r29_unwritable_directory_never_raises_and_preserves_existing_capture(self) -> None:
        # 삼킴 옵트인(§4.5) — 이 케이스는 쓰기 불가 디렉토리에서 원자적 쓰기의 mkstemp 이
        # PermissionError 를 던지게 만들고, main 이 그것을 삼켜 exit 0 과 기존 캡처 보존을
        # 지키는 것을 확인한다. 즉 삼킴 자체가 이 케이스의 시험 대상이다. R29 의 다른 두
        # 케이스는 예외를 내지 않으므로(parse_status_line_rate_limits 가 내부에서 처리한다)
        # 옵트인이 필요하지 않다 — 실측으로 확인했다.
        self.expect_swallowed_exception(
            PermissionError,
            "쓰기 불가 디렉토리에서 mkstemp 이 던지는 예외를 main 이 삼켜 상태줄을 지키는 것이 이 케이스의 계약",
        )
        now_s = int(time.time())
        self._run_with_stdin(_rate_limits_payload(now_s, session_hours_from_now=2.0))
        existing_bytes = hub_collect.RATE_LIMITS_PATH.read_bytes()

        self.temp_dir.chmod(0o500)  # mkstemp 가 새 임시 파일을 만들 수 없게 한다
        try:
            exit_code, _output = self._run_with_stdin(
                _rate_limits_payload(now_s, session_hours_from_now=5.0)
            )
        finally:
            self.temp_dir.chmod(0o755)

        self.assertEqual(exit_code, 0)
        self.assertEqual(hub_collect.RATE_LIMITS_PATH.read_bytes(), existing_bytes)


SESSION_ID = "0a1b2c3d-4e5f-6789-abcd-ef0123456789"


def _session_cost_payload(now_s: int, total_cost_usd: float = 12.849, with_rate_limits: bool = True) -> str:
    payload = json.loads(_rate_limits_payload(now_s)) if with_rate_limits else {}
    payload["session_id"] = SESSION_ID
    payload["cost"] = {"total_cost_usd": total_cost_usd, "total_api_duration_ms": 31 * 60_000}
    payload["context_window"] = {"used_percentage": 62}
    return json.dumps(payload)


class SessionCostCaptureTest(HubStatuslineEntrypointTest):
    """⑨ — 같은 stdin 1건에서 세션 비용 캡처도 만든다. 출력 한 줄은 기존과 같다(docs/prps/harness-benchmark-adoption.md §10-1)."""

    def _session_cost_file(self) -> Path:
        return hub_session_cost.SESSION_COSTS_DIR / f"{SESSION_ID}.json"

    def test_cost_payload_writes_the_session_file_and_keeps_the_summary_line(self) -> None:
        exit_code, output = self._run_with_stdin(_session_cost_payload(int(time.time())))

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "세션 23% · 주간 41%")
        cost = hub_session_cost.read_session_cost(SESSION_ID)
        self.assertEqual((cost.total_cost_cents, cost.api_duration_minutes, cost.context_used_percent), (1284, 31, 62))
        self.assertTrue(hub_collect.RATE_LIMITS_PATH.is_file())

    def test_cost_only_payload_writes_no_rate_limit_capture(self) -> None:
        _exit_code, output = self._run_with_stdin(_session_cost_payload(int(time.time()), with_rate_limits=False))

        self.assertEqual(output.strip(), "")
        self.assertTrue(self._session_cost_file().is_file())
        self.assertFalse(hub_collect.RATE_LIMITS_PATH.exists())

    def test_identical_payload_leaves_the_session_file_untouched(self) -> None:
        text = _session_cost_payload(int(time.time()))
        self._run_with_stdin(text)
        mtime_before = self._session_cost_file().stat().st_mtime_ns

        self._run_with_stdin(text)

        self.assertEqual(self._session_cost_file().stat().st_mtime_ns, mtime_before)

    def test_changed_cost_rewrites_the_session_file(self) -> None:
        now_s = int(time.time())
        self._run_with_stdin(_session_cost_payload(now_s, total_cost_usd=1.0))
        mtime_before = self._session_cost_file().stat().st_mtime_ns

        self._run_with_stdin(_session_cost_payload(now_s, total_cost_usd=2.0))

        self.assertNotEqual(self._session_cost_file().stat().st_mtime_ns, mtime_before)
        self.assertEqual(hub_session_cost.read_session_cost(SESSION_ID).total_cost_cents, 200)

    def test_payload_without_either_capture_does_no_file_io(self) -> None:
        _exit_code, output = self._run_with_stdin(json.dumps({"hookEventName": "Status"}))

        self.assertEqual(output.strip(), "")
        self.assertFalse(hub_session_cost.SESSION_COSTS_DIR.exists())
        self.assertFalse(hub_collect.RATE_LIMITS_PATH.exists())

    def test_unwritable_directory_still_prints_the_line_and_exits_zero(self) -> None:
        self.expect_swallowed_exception(
            PermissionError,
            "쓰기 불가 디렉토리에서 mkdir 이 던지는 예외를 main 이 삼켜 상태줄을 지키는 것이 이 케이스의 계약",
        )
        self.temp_dir.chmod(0o500)  # session_costs 디렉터리를 만들 수 없게 한다
        try:
            exit_code, output = self._run_with_stdin(_session_cost_payload(int(time.time()), with_rate_limits=False))
        finally:
            self.temp_dir.chmod(0o755)

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.strip(), "")
        self.assertFalse(hub_session_cost.SESSION_COSTS_DIR.exists())


if __name__ == "__main__":
    unittest.main()
