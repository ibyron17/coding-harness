"""hub_session_cost 단위 테스트 — 세션 비용 캡처 파일의 I/O 층(⑨, docs/prps/harness-benchmark-adoption.md §10-1).

실제 ~/.claude 는 건드리지 않는다. 모듈 상수 SESSION_COSTS_DIR 을 임시 디렉터리로 바꿔치기한 뒤
원상복구한다(rules/python/testing.md 의 Test Isolation 관례).
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_session_cost  # noqa: E402  (sys.path 조정 후 임포트)
import hub_usage  # noqa: E402

SESSION_ID = "0a1b2c3d-4e5f-6789-abcd-ef0123456789"
OTHER_SESSION_ID = "11111111-2222-3333-4444-555555555555"
NOW_MS = 1_786_433_123_000
ONE_DAY_SECONDS = 24 * 60 * 60
RETENTION_DAYS = 7


def _cost(total_cost_cents: int = 1284) -> hub_usage.SessionCost:
    return hub_usage.SessionCost(
        captured_at_ms=NOW_MS, total_cost_cents=total_cost_cents, api_duration_minutes=31, context_used_percent=62
    )


class SessionCostFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_dir = hub_session_cost.SESSION_COSTS_DIR
        hub_session_cost.SESSION_COSTS_DIR = self.temp_dir / "session_costs"

    def tearDown(self) -> None:
        hub_session_cost.SESSION_COSTS_DIR = self.original_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _file_for(self, session_id: str) -> Path:
        return hub_session_cost.SESSION_COSTS_DIR / f"{session_id}.json"

    def _age_file(self, session_id: str, days: float) -> None:
        aged_seconds = NOW_MS / 1000 - days * ONE_DAY_SECONDS
        os.utime(self._file_for(session_id), (aged_seconds, aged_seconds))

    def test_write_then_read_round_trips_and_creates_the_directory(self) -> None:
        self.assertFalse(hub_session_cost.SESSION_COSTS_DIR.exists())
        hub_session_cost.write_session_cost(SESSION_ID, _cost())
        self.assertEqual(hub_session_cost.read_session_cost(SESSION_ID), _cost())

    def test_write_replaces_the_previous_capture_without_leaving_temp_files(self) -> None:
        hub_session_cost.write_session_cost(SESSION_ID, _cost(100))
        hub_session_cost.write_session_cost(SESSION_ID, _cost(200))
        self.assertEqual(hub_session_cost.read_session_cost(SESSION_ID).total_cost_cents, 200)
        self.assertEqual([path.name for path in hub_session_cost.SESSION_COSTS_DIR.iterdir()], [f"{SESSION_ID}.json"])

    def test_write_with_malformed_session_id_does_nothing(self) -> None:
        for bad_session_id in ("../escape", "", SESSION_ID.upper(), "a/b"):
            hub_session_cost.write_session_cost(bad_session_id, _cost())
        self.assertFalse(hub_session_cost.SESSION_COSTS_DIR.exists())
        self.assertEqual([path.name for path in self.temp_dir.iterdir()], [])

    def test_read_never_leaves_the_capture_directory(self) -> None:
        hub_session_cost.write_session_cost(SESSION_ID, _cost())
        (self.temp_dir / "x.json").write_text(self._file_for(SESSION_ID).read_text(encoding="utf-8"), encoding="utf-8")
        self.assertIsNone(hub_session_cost.read_session_cost("../x"))

    def test_read_absent_or_broken_file_is_none(self) -> None:
        self.assertIsNone(hub_session_cost.read_session_cost(SESSION_ID))  # 디렉터리 자체가 없다
        hub_session_cost.SESSION_COSTS_DIR.mkdir(parents=True)
        self.assertIsNone(hub_session_cost.read_session_cost(SESSION_ID))  # 파일이 없다
        self._file_for(SESSION_ID).write_text("{not json", encoding="utf-8")
        self.assertIsNone(hub_session_cost.read_session_cost(SESSION_ID))  # 깨졌다
        self._file_for(SESSION_ID).write_text('{"captured_at_ms": 1, "context_used_percent": 500}', encoding="utf-8")
        self.assertIsNone(hub_session_cost.read_session_cost(SESSION_ID))  # 계약 위반

    def test_read_session_costs_returns_only_sessions_that_have_a_capture(self) -> None:
        hub_session_cost.write_session_cost(SESSION_ID, _cost())
        found = hub_session_cost.read_session_costs([SESSION_ID, OTHER_SESSION_ID, SESSION_ID])
        self.assertEqual(found, {SESSION_ID: _cost()})
        self.assertEqual(hub_session_cost.read_session_costs([]), {})

    def test_prune_removes_only_json_files_older_than_the_retention(self) -> None:
        hub_session_cost.write_session_cost(SESSION_ID, _cost())
        hub_session_cost.write_session_cost(OTHER_SESSION_ID, _cost())
        self._age_file(SESSION_ID, RETENTION_DAYS + 1)
        self._age_file(OTHER_SESSION_ID, RETENTION_DAYS - 1)
        unrelated_old_file = hub_session_cost.SESSION_COSTS_DIR / "notes.txt"
        unrelated_old_file.write_text("남의 파일", encoding="utf-8")
        os.utime(unrelated_old_file, (0, 0))

        hub_session_cost.prune_old_session_cost_files(NOW_MS, RETENTION_DAYS)

        self.assertFalse(self._file_for(SESSION_ID).exists())
        self.assertTrue(self._file_for(OTHER_SESSION_ID).exists())
        self.assertTrue(unrelated_old_file.exists())

    def test_prune_without_the_directory_is_a_no_op(self) -> None:
        hub_session_cost.prune_old_session_cost_files(NOW_MS, RETENTION_DAYS)
        self.assertFalse(hub_session_cost.SESSION_COSTS_DIR.exists())


if __name__ == "__main__":
    unittest.main()
