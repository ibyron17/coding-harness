"""hub_live_session_read 단위 테스트. docs/prps/hub-live-session-native-source.md §7.2(R1~R11) —
~/.claude/sessions/ 디렉터리 열거·읽기·PID 생존 확인(I/O). 임시 디렉터리를 sessions_dir 인자로
직접 넘긴다(모듈 상수가 없다 — 호출자가 넘긴다, 결정 LS2)."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_live_session  # noqa: E402  (sys.path 조정 후 임포트)
import hub_live_session_read  # noqa: E402


def _write_record(directory: Path, pid: int, session_id: str, status: str | None = "busy") -> None:
    payload = {"sessionId": session_id, "pid": pid}
    if status is not None:
        payload["status"] = status
    (directory / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


class ReadLiveSessionRosterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.restricted_dirs: list[Path] = []

    def tearDown(self) -> None:
        for restricted_dir in self.restricted_dirs:
            restricted_dir.chmod(0o755)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_r1_missing_directory_is_empty_and_incomplete_without_warnings(self) -> None:
        """R1 — 변조 검출: is_complete=True 로 반환하면 이 단언이 깨진다."""
        missing_dir = self.temp_dir / "does-not-exist"
        index, warnings = hub_live_session_read.read_live_session_roster(missing_dir)
        self.assertEqual(index.by_session_id, {})
        self.assertFalse(index.is_complete)
        self.assertEqual(warnings, ())

    def test_r2_three_alive_records_survive_without_mocking(self) -> None:
        """R2 — 분모. 실제 프로세스(os.getpid(), 모킹 없음)로 생존 경로 자체가 동작함을 확인한다.
        같은 실제 pid 를 세 세션에 재사용한다 — 이 테스트의 관심사는 "생존 판정이 실제로
        동작하는가"이지 pid 유일성이 아니다(파일명이 인덱스 키이므로 겹치지 않는다)."""
        my_pid = os.getpid()
        for session_id in ("s1", "s2", "s3"):
            payload = {"sessionId": session_id, "pid": my_pid, "status": "idle"}
            (self.temp_dir / f"{session_id}.json").write_text(json.dumps(payload), encoding="utf-8")

        result_index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)

        self.assertEqual(len(result_index.by_session_id), 3)
        self.assertTrue(result_index.is_complete)
        self.assertEqual(warnings, ())

    def test_r3_dead_pid_is_excluded_but_is_complete_stays_true(self) -> None:
        """R3 — 변조 검출: 죽은 PID 를 인덱스에 남기면 len 단언이 깨지고, is_complete 를
        내리면(정상 경로를 실패로 취급) 이 단언이 깨진다."""
        alive_pid = os.getpid()
        dead_pid = 999999

        def _fake_kill(pid: int, sig: int) -> None:
            if pid == dead_pid:
                raise ProcessLookupError()

        (self.temp_dir / "alive-1.json").write_text(
            json.dumps({"sessionId": "alive-1", "pid": alive_pid, "status": "idle"}), encoding="utf-8"
        )
        (self.temp_dir / "alive-2.json").write_text(
            json.dumps({"sessionId": "alive-2", "pid": alive_pid, "status": "idle"}), encoding="utf-8"
        )
        (self.temp_dir / "dead.json").write_text(
            json.dumps({"sessionId": "dead", "pid": dead_pid, "status": "busy"}), encoding="utf-8"
        )

        with mock.patch("os.kill", side_effect=_fake_kill):
            index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)

        self.assertEqual(set(index.by_session_id), {"alive-1", "alive-2"})
        self.assertTrue(index.is_complete)
        self.assertEqual(warnings, ())

    def test_r4_permission_error_counts_as_alive(self) -> None:
        """R4 — 변조 검출: PermissionError 분기를 `return False` 로 바꾸면 레코드가 인덱스에서
        빠져 이 단언이 깨진다."""
        _write_record(self.temp_dir, 555, "s1")
        with mock.patch("os.kill", side_effect=PermissionError()):
            index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)
        self.assertIn("s1", index.by_session_id)
        self.assertTrue(index.is_complete)
        self.assertEqual(warnings, ())

    def test_r5_key_file_is_ignored(self) -> None:
        """R5 — 변조 검출: suffix 필터(`path.suffix == ".json"`)를 지우면 .key 파일도 훑어
        파싱을 시도하다 실패해 is_complete 가 False 로 떨어져 이 단언이 깨진다."""
        my_pid = os.getpid()
        _write_record(self.temp_dir, my_pid, "s1")
        (self.temp_dir / f"{my_pid}.deadbeef.key").write_text("opaque-key-bytes", encoding="utf-8")

        index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)

        self.assertEqual(set(index.by_session_id), {"s1"})
        self.assertTrue(index.is_complete)
        self.assertEqual(warnings, ())

    def test_r6_two_broken_json_records_are_isolated_with_one_aggregated_warning(self) -> None:
        """R6 — 변조 검출: 깨진 레코드에서 is_complete 를 안 내리면 실패하고, 파일마다 개별
        경고를 내면(집계 대신) 경고 개수 단언이 깨진다. 깨진 레코드를 **2건** 두는 이유 —
        1건뿐이면 "집계 1건"과 "파일마다 개별 경고"가 우연히 같은 개수(1건)가 돼 이 변조를
        구별하지 못한다(실측: 최초 버전은 이 함정에 걸렸다)."""
        my_pid = os.getpid()
        (self.temp_dir / "good-1.json").write_text(
            json.dumps({"sessionId": "good-1", "pid": my_pid, "status": "idle"}), encoding="utf-8"
        )
        (self.temp_dir / "good-2.json").write_text(
            json.dumps({"sessionId": "good-2", "pid": my_pid, "status": "busy"}), encoding="utf-8"
        )
        (self.temp_dir / "broken-1.json").write_text("not-json-at-all", encoding="utf-8")
        (self.temp_dir / "broken-2.json").write_text("{also not json", encoding="utf-8")

        index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)

        self.assertEqual(set(index.by_session_id), {"good-1", "good-2"})
        self.assertFalse(index.is_complete)
        self.assertEqual(len(warnings), 1)

    def test_r7_oversized_record_is_excluded_and_marks_incomplete(self) -> None:
        """R7 — 변조 검출: 크기 검사를 지우면 이 레코드가 파싱을 시도해 성공적으로 살아남고
        is_complete 도 True 로 남아 두 단언이 모두 깨진다."""
        oversized_payload = json.dumps(
            {"sessionId": "s1", "pid": 555, "status": "busy", "padding": "x" * hub_live_session.LIVE_SESSION_RECORD_MAX_BYTES}
        )
        (self.temp_dir / "555.json").write_text(oversized_payload, encoding="utf-8")

        index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)

        self.assertEqual(index.by_session_id, {})
        self.assertFalse(index.is_complete)
        self.assertEqual(len(warnings), 1)

    def test_r8_empty_directory_is_complete_with_no_warnings(self) -> None:
        """R8 — LS7 의 의도적 구분(빈 명부 vs 디렉터리 부재). 변조 검출: 빈 명부를 False 로
        반환하면(R1 과 결과가 같아져) 이 구분이 사라진다."""
        index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)
        self.assertEqual(index.by_session_id, {})
        self.assertTrue(index.is_complete)
        self.assertEqual(warnings, ())

    def test_r9_enumeration_failure_gives_up_the_whole_roster(self) -> None:
        """R9 — 변조 검출: 열거 가드(try/except)를 지우면 이 테스트가 예외로 실패한다(수집
        전체가 죽는다). 모킹이 아니라 실제 `chmod 000` 디렉터리로 EACCES 를 낸다 —
        `Path.glob()` 은 이 조건에서 예외를 던지지 않고 조용히 빈 목록을 반환해(Python
        3.11.5 실측) 모킹으로 `OSError` 를 주입하는 테스트로는 이 가드가 실전에서 뚫려
        있어도 통과했다. 권한 검사가 무력한 root 실행(CI 등)에서는 건너뛴다."""
        if os.geteuid() == 0:
            self.skipTest("root 로 실행 중이라 디렉터리 권한 검사가 무력해 EACCES 를 재현할 수 없다")
        restricted_dir = self.temp_dir / "restricted"
        restricted_dir.mkdir()
        restricted_dir.chmod(0o000)
        self.restricted_dirs.append(restricted_dir)

        index, warnings = hub_live_session_read.read_live_session_roster(restricted_dir)

        self.assertEqual(index.by_session_id, {})
        self.assertFalse(index.is_complete)
        self.assertEqual(len(warnings), 1)
        self.assertIn("목록 조회 실패", warnings[0])

    def test_r10_invalid_utf8_byte_is_absorbed_without_raising(self) -> None:
        """R10 — 변조 검출: errors="replace" 를 지우면 UnicodeDecodeError(ValueError 서브클래스)
        가 `except OSError` 를 뚫고 올라와 이 테스트 자체가 에러로 실패한다.

        검수 1회차 L3 — pid 555 를 모킹 없이 썼던 이전 판은 비결정적이었다(머신에 pid 555 가
        떠 있으면 PermissionError 로 생존, 없으면 ProcessLookupError 로 죽음 — 실행마다 다른
        경로를 탄다). os.kill 을 모킹해 항상 생존 경로를 타게 고정하고, is_complete·인덱스
        내용까지 단언한다(R4 선례와 같은 형태)."""
        record_path = self.temp_dir / "555.json"
        with open(record_path, "wb") as raw_file:
            raw_file.write(b'{"sessionId":"s\xff1","pid":555,"status":"busy"}')

        with mock.patch("os.kill", return_value=None):
            index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)  # 던지면 실패

        self.assertIsInstance(index, hub_live_session.LiveSessionIndex)
        self.assertTrue(index.is_complete)
        self.assertIn("s�1", index.by_session_id)
        self.assertEqual(warnings, ())

    def test_r6a_stat_toctou_race_is_absorbed_with_one_warning(self) -> None:
        """R6a(검수 1회차 H4) — iterdir() 이 본 파일이 stat() 시점에 사라지는 TOCTOU 는 방어적
        가정이 아니라 상시 발생한다(~/.claude/sessions/ 는 호스트가 세션마다 만들고 지우는
        디렉터리). iterdir 의 반환 목록에 실제로는 없는 경로를 섞어 그 경합을 재현한다.

        mock.patch.object(Path, "stat", side_effect=FileNotFoundError) 로 직접 예외를
        주입하지 않는 이유(실측 확인, 검수가 제안한 형태에서 이탈) — sessions_dir.is_dir()
        자신도 내부적으로 Path.stat 을 쓴다(파이썬 3.11 pathlib.is_dir). Path.stat 을
        통째로 모킹하면 is_dir() 판정까지 함께 깨져 "디렉터리 없음"(경고 0건) 경로로 새
        버려 의도한 단언이 성립하지 않는다(검수 2회차 L1 — errno 유무에 따라 단언 실패
        또는 예외 전파, 어느 쪽도 "통과"는 아니다). Path.iterdir 을 모킹하되 stat 자체는
        건드리지 않아 이 충돌을 피한다 — R9 는 열거 자체의 EACCES 를 실제 `chmod 000`
        디렉터리로 재현하지만, 여기서 노리는 것은 열거 이후의 stat 경합이라 모킹이 맞다.

        변조 검출: _read_record_text 의 except OSError 를 다른 예외형(예:
        ZeroDivisionError)으로 바꾸면 FileNotFoundError 가 여기를 뚫고 올라와 이 테스트가
        에러로 실패한다."""
        my_pid = os.getpid()
        _write_record(self.temp_dir, my_pid, "s1")
        real_record_path = self.temp_dir / f"{my_pid}.json"
        vanished_path = self.temp_dir / "vanished.json"  # iterdir 이후 stat 이전에 사라진 것을 흉내

        with mock.patch.object(Path, "iterdir", return_value=[vanished_path, real_record_path]):
            index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)

        self.assertEqual(set(index.by_session_id), {"s1"})
        self.assertFalse(index.is_complete)
        self.assertEqual(len(warnings), 1)

    def test_r11_is_dir_permission_error_gives_up_the_whole_roster_with_a_warning(self) -> None:
        """R11(검수 2회차 H1) — `is_dir()` 자신이 `PermissionError`(EACCES, 권한 없는 부모
        디렉터리 등)를 올리는 경우를 R9(열거 실패)와 같은 급으로 흡수해야 한다.
        `hub_workflow_read._existing_workflow_directories` 가 `is_dir()` 를 이미
        try/except OSError 로 감싸 둔 것과 같은 형태(그 모듈 docstring 의 pathlib 실측
        주석 참조 — `is_dir()` 은 ENOENT 는 삼키지만 EACCES 는 올린다).

        변조 검출: `is_dir()` 호출을 try/except 로 감싸지 않으면 `PermissionError` 가
        그대로 올라와 이 테스트가 에러로 실패한다. 경고 문구가 "접근 실패" 로 시작해 R9
        의 "목록 조회 실패" 와 구별됨을 assertIn 으로 고정한다(검수 3회차 LOW — 두 문구를
        같게 만드는 변조가 이 assertIn 없이는 잡히지 않았다)."""
        with mock.patch.object(Path, "is_dir", side_effect=PermissionError("simulated EACCES")):
            index, warnings = hub_live_session_read.read_live_session_roster(self.temp_dir)
        self.assertEqual(index.by_session_id, {})
        self.assertFalse(index.is_complete)
        self.assertEqual(len(warnings), 1)
        self.assertIn("접근 실패", warnings[0])


class IsProcessAliveTest(unittest.TestCase):
    """_is_process_alive 의 두 예외 분기 — StopServerKillCallSiteTest 의 모킹 선례를 따른다."""

    def test_current_process_is_alive_without_mocking(self) -> None:
        """분모 — 모킹 없이도 반드시 True."""
        self.assertTrue(hub_live_session_read._is_process_alive(os.getpid()))

    def test_process_lookup_error_means_dead(self) -> None:
        with mock.patch("os.kill", side_effect=ProcessLookupError()):
            self.assertFalse(hub_live_session_read._is_process_alive(12345))

    def test_permission_error_means_alive(self) -> None:
        with mock.patch("os.kill", side_effect=PermissionError()):
            self.assertTrue(hub_live_session_read._is_process_alive(12345))


if __name__ == "__main__":
    unittest.main()
