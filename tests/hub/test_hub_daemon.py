"""hub_daemon 단위 테스트. 순수 함수(D1~D5)는 docs/prps/hub-dashboard.md 「개정 테스트 계획」 참조.

D6(parse_server_record)은 hub_server_state.py 로 옮겨 tests/hub/test_hub_server_state.py 에 있다(검수 m3).
I/O 함수(server_status·stop_server)는 검수 m1(고아 신호·compare-and-delete) 회귀 테스트 대상이다.
"""

import os
import shutil
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402
import hub_daemon  # noqa: E402
import hub_model  # noqa: E402
import hub_server_state  # noqa: E402
import hub_server_state_read  # noqa: E402

HUB_PY_PATH = "/Users/x/.claude/hub/bin/hub.py"


class IsOurServerProcessTest(unittest.TestCase):
    """D1~D5 — PID 재사용 방어의 핵심 판정. N1~N7(설계 문서 hub-server-identity.md §9-2) —
    신원 기준을 판정자 자기 경로에서 레코드가 적어 둔 기동 경로로 옮긴 뒤의 확장."""

    def test_d1_matching_server_run_process(self) -> None:
        ps_output = f"python3 {HUB_PY_PATH} server-run"
        self.assertTrue(hub_daemon.is_our_server_process(ps_output, HUB_PY_PATH))

    def test_d2_same_hub_py_but_collect_subcommand(self) -> None:
        """배경 collect 프로세스를 서버로 오인하지 않는다."""
        ps_output = f"python3 {HUB_PY_PATH} collect"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, HUB_PY_PATH))

    def test_d3_entirely_different_process(self) -> None:
        """PID 재사용 방어의 핵심 — 전혀 다른 프로세스는 False."""
        ps_output = "/usr/sbin/cupsd"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, HUB_PY_PATH))

    def test_d4_empty_output_is_unverifiable(self) -> None:
        """확인할 수 없으면(ps 실패 등의 빈 출력) 죽이지 않는다."""
        self.assertFalse(hub_daemon.is_our_server_process("", HUB_PY_PATH))
        self.assertFalse(hub_daemon.is_our_server_process("python3 x server-run", ""))

    def test_d5_home_directory_with_spaces(self) -> None:
        """부분 문자열 판정이 경로의 공백에 깨지지 않는다."""
        spaced_path = "/Users/x y/.claude/hub/bin/hub.py"
        ps_output = f"python3 {spaced_path} server-run"
        self.assertTrue(hub_daemon.is_our_server_process(ps_output, spaced_path))

    def test_n1_two_installs_authoritative_case(self) -> None:
        """N1 — 두 벌 설치 정본: 기준이 레코드에서 온 레포 사본 경로이면, ps 가 그 경로를
        돌려주는 한 True 다 — 오늘의 코드(판정자 자기 경로와 대조)가 False 를 내던
        바로 그 입력이다."""
        repo_checkout_path = "/Users/x/private/project/coding-harness/hub/bin/hub.py"
        ps_output = f"python3 {repo_checkout_path} server-run"
        self.assertTrue(hub_daemon.is_our_server_process(ps_output, repo_checkout_path))

    def test_n2_mismatched_install_path_is_still_false(self) -> None:
        """N2 — 대조군: 같은 ps 출력이라도 기준(레코드 경로)이 다른 사본 경로면 False —
        N1 이 판정 자체를 무력화해서 통과한 게 아님을 고정한다."""
        repo_checkout_path = "/Users/x/private/project/coding-harness/hub/bin/hub.py"
        ps_output = f"python3 {repo_checkout_path} server-run"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, HUB_PY_PATH))

    def test_n3_legacy_record_relaxed_criteria_matches(self) -> None:
        """N3 — 구버전 강등: 기준이 None(필드 없던 구버전 레코드)이고 ps 가 …/hub.py
        server-run 이면 True."""
        ps_output = f"python3 {HUB_PY_PATH} server-run"
        self.assertTrue(hub_daemon.is_our_server_process(ps_output, None))

    def test_n4_legacy_record_relaxed_criteria_requires_server_run_marker(self) -> None:
        """N4 — 구버전 강등의 하한: server-run 마커가 없으면(배경 collect 프로세스 등) False."""
        ps_output = f"python3 {HUB_PY_PATH} collect"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, None))

    def test_n5_legacy_record_relaxed_criteria_rejects_unrelated_process(self) -> None:
        """N5 — 구버전 강등의 하한: 전혀 다른 프로세스는 False."""
        self.assertFalse(hub_daemon.is_our_server_process("/usr/sbin/cupsd", None))

    def test_n6_legacy_record_relaxed_criteria_requires_token_suffix(self) -> None:
        """N6 — 구버전 강등의 접미 판정: hub.py 가 등장해도 경로 토큰의 접미가 아니면
        (예: grep 인자로 언급된 bare 파일명) False."""
        ps_output = "grep -r hub.py server-run /x"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, None))

    def test_n7_legacy_record_relaxed_criteria_with_spaced_home_directory(self) -> None:
        """N7 — 공백 든 홈 + 강등: 토큰 접미 판정이 경로의 공백에 깨지지 않는다."""
        ps_output = "python3 /Users/x y/.claude/hub/bin/hub.py server-run"
        self.assertTrue(hub_daemon.is_our_server_process(ps_output, None))

    def test_m2_bare_filename_recorded_value_is_demoted_and_still_matches_real_path(self) -> None:
        """Minor 2(2회차 검수) — 분모. 기록값이 경로 형태가 아닌 맨 파일명("hub.py", 슬래시도
        접미도 아닌 값)이면 완화 분기로 강등된다 — 이 강등이 무조건 False 를 내는 죽은
        분기가 아님을, ps 에 실제 경로가 있으면 여전히 True 가 남을 통해 보인다. 아래 두
        음성 테스트(pgrep·grep 자기 언급)의 분모다."""
        ps_output = f"python3 {HUB_PY_PATH} server-run"
        self.assertTrue(hub_daemon.is_our_server_process(ps_output, "hub.py"))

    def test_m2_bare_filename_recorded_value_rejects_pgrep_self_mention(self) -> None:
        """Minor 2 — 검수자 실측 회귀 1. 기록값이 "hub.py"(경로 형태가 아님)면 엄격 대조로
        새지 않고 완화 분기로 강등된다. ps 출력의 "hub.py" 토큰은 경로 접미(`/hub.py`)가
        아니므로 완화 기준도 충족하지 못해 False — 강등 전(엄격 `in` 대조)이었다면
        "hub.py" in ps_output 가 참이 되어 이 명령행(우리 서버를 찾는 pgrep 자신)이
        오탐으로 우리 서버로 오인됐을 것이다."""
        ps_output = "pgrep -f hub.py server-run"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, "hub.py"))

    def test_m2_bare_filename_recorded_value_rejects_grep_self_mention(self) -> None:
        """Minor 2 — 검수자 실측 회귀 2. 위와 같은 이유로, hub.py 를 언급하는 grep 명령행도
        경로 접미가 없어 False 다."""
        ps_output = "grep -rn hub.py server-run /x"
        self.assertFalse(hub_daemon.is_our_server_process(ps_output, "hub.py"))


class BrowserOpenCommandTest(unittest.TestCase):
    """D9 — 플랫폼 판정을 순수 함수로 떼어 세 플랫폼 전부를 단위 테스트로 덮는다."""

    def test_b1_darwin_uses_open_command_that_focuses(self) -> None:
        url = "http://localhost:8794/hub.html"
        self.assertEqual(
            hub_daemon.browser_open_command("darwin", url),
            ["/usr/bin/open", url],
        )

    def test_b2_linux_falls_back_to_webbrowser(self) -> None:
        url = "http://localhost:8794/hub.html"
        self.assertIsNone(hub_daemon.browser_open_command("linux", url))

    def test_b3_windows_falls_back_to_webbrowser(self) -> None:
        url = "http://localhost:8794/hub.html"
        self.assertIsNone(hub_daemon.browser_open_command("win32", url))

    def test_b4_url_stays_one_argv_element_even_with_spaces(self) -> None:
        """셸 인젝션 표면 부재의 회귀(GOTCHA 5) — 공백 있는 URL 도 argv 원소 하나로 그대로 간다."""
        url = "file:///Users/x y/.claude/hub/hub.html"
        command = hub_daemon.browser_open_command("darwin", url)
        self.assertEqual(len(command), 2)
        self.assertEqual(command[1], url)


class RestartNoteTest(unittest.TestCase):
    """restart_server 의 stop 단계 이례를 사용자 문구로 바꾸는 순수 함수."""

    def test_n1_clean_stop_has_no_note(self) -> None:
        self.assertIsNone(hub_daemon.restart_note({"ok": True, "was_running": True}))

    def test_n2_forced_kill_is_reported(self) -> None:
        stop_result = {"ok": True, "was_running": True, "forced": True}
        self.assertEqual(hub_daemon.restart_note(stop_result), hub_daemon.FORCED_STOP_NOTE)

    def test_n3_stop_reason_is_passed_through_verbatim(self) -> None:
        """문구를 두 곳에서 관리하지 않는다 — stop_server 가 만든 문구를 그대로 옮긴다."""
        reason = "PID 가 재사용됐습니다 — 그 프로세스는 건드리지 않고 상태 파일만 정리했습니다"
        stop_result = {"ok": True, "was_running": False, "reason": reason}
        self.assertEqual(hub_daemon.restart_note(stop_result), reason)


class HubDaemonIoScenarioTest(unittest.TestCase):
    """server_status/stop_server 의 I/O 시나리오. 실제 ~/.claude 는 건드리지 않는다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        # hub_server_state_read.py 가 서버 상태 3개(HUB_HOME 자신의 mkdir 대상 포함)를 갖고
        # 있으므로 hub_collect.HUB_HOME 과 나란히 격리한다 — 안 그러면 touch_server_heartbeat
        # 등의 mkdir(parents=True) 호출이 실제 ~/.claude/hub 를 대상으로 한다(무해하지만
        # 이 파일의 "실제 ~/.claude 는 건드리지 않는다" 약속을 어긴다).
        self.original_server_state_hub_home = hub_server_state_read.HUB_HOME
        self.original_record_path = hub_server_state_read.SERVER_RECORD_PATH
        self.original_heartbeat_path = hub_server_state_read.SERVER_HEARTBEAT_PATH
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_server_state_read.SERVER_RECORD_PATH = self.temp_dir / "server.json"
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.temp_dir / "server_heartbeat"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        # 개정 2 — server_status() 가 evaluate_collect_health 를 위해 이 둘을 새로 읽는다.
        # 격리하지 않으면 개발자 실제 머신의 ~/.claude/hub/last_collect_error.json ·
        # last_collect_success 를 읽어 테스트 결과가 머신 상태에 따라 달라진다.
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_server_state_read.HUB_HOME = self.original_server_state_hub_home
        hub_server_state_read.SERVER_RECORD_PATH = self.original_record_path
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.original_heartbeat_path
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class ServerStatusOrphanedEvidenceTest(HubDaemonIoScenarioTest):
    """검수 m1 — 하트비트는 살아 있는데 server.json 이 없는 상태를 이상 신호로 관측한다."""

    def test_fresh_heartbeat_without_record_is_orphaned(self) -> None:
        hub_server_state_read.touch_server_heartbeat()
        with mock.patch.object(hub_daemon, "_check_http_ok", return_value=False):
            status = hub_daemon.server_status()
        self.assertTrue(status.orphaned_evidence)
        self.assertFalse(status.crashed_evidence)

    def test_no_heartbeat_no_record_is_not_orphaned(self) -> None:
        with mock.patch.object(hub_daemon, "_check_http_ok", return_value=False):
            status = hub_daemon.server_status()
        self.assertFalse(status.orphaned_evidence)


class ServerStatusMaintenanceStalledTest(HubDaemonIoScenarioTest):
    """검수 M2-3/M2-4(2), 개정 2 — 프로세스(HTTP 서버 스레드)는 살아 있는데 유지보수 티커만
    죽어 하트비트가 만료된 상태를 crashed_evidence 와 구분해 이름 붙인다. (구) collect_stalled
    에서 이름만 바뀌었을 뿐 판정식은 그대로다 — 기대값도 그대로다.

    log_tail 게이트는 `crashed_evidence or maintenance_stalled or collect_health ==
    "failing"` 셋의 or 다(§0.3 정정 3) — 티커만 죽어도 수집은 요청 구동으로 계속 성공해
    collect_health 가 ok 로 남을 수 있으므로, maintenance_stalled 단독으로도 log_tail 이
    채워져야 스레드 사망 트레이스백을 놓치지 않는다."""

    def test_process_present_but_heartbeat_expired_is_maintenance_stalled(self) -> None:
        record = hub_server_state.ServerRecord(pid=999, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        ps_output_with_marker = f"python3 {hub_daemon.HUB_PY_PATH} server-run"
        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output_with_marker), \
             mock.patch.object(hub_daemon, "_check_http_ok", return_value=True):
            status = hub_daemon.server_status()
        self.assertTrue(status.process_present)
        self.assertFalse(status.alive)
        self.assertTrue(status.maintenance_stalled)
        self.assertFalse(status.crashed_evidence)  # 완전 사망이 아니라 유지보수 티커만 사망
        self.assertIsNotNone(status.log_tail)  # maintenance_stalled 단독으로도 log_tail 이 채워진다

    def test_process_present_and_heartbeat_fresh_is_not_maintenance_stalled(self) -> None:
        record = hub_server_state.ServerRecord(pid=999, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.touch_server_heartbeat()
        ps_output_with_marker = f"python3 {hub_daemon.HUB_PY_PATH} server-run"
        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output_with_marker), \
             mock.patch.object(hub_daemon, "_check_http_ok", return_value=True):
            status = hub_daemon.server_status()
        self.assertFalse(status.maintenance_stalled)
        self.assertIsNone(status.log_tail)


class ServerStatusCollectHealthTest(HubDaemonIoScenarioTest):
    """개정 2 — evaluate_collect_health 를 실제 파일 두 곳(성공 스탬프·last_collect_error.json)
    과 엮어 server_status() 가 collect_health·last_collect_success_age_ms·log_tail 을
    올바르게 채우는지 확인한다."""

    def test_failure_record_only_is_failing_with_log_tail(self) -> None:
        hub_collect.record_collect_failure("boom")
        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=""), \
             mock.patch.object(hub_daemon, "_check_http_ok", return_value=False):
            status = hub_daemon.server_status()
        self.assertEqual(status.collect_health, "failing")
        self.assertIsNotNone(status.log_tail)
        self.assertIsNone(status.last_collect_success_age_ms)

    def test_success_stamp_only_is_ok_with_no_log_tail(self) -> None:
        hub_server_state_read.touch_collect_success_stamp()
        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=""), \
             mock.patch.object(hub_daemon, "_check_http_ok", return_value=False):
            status = hub_daemon.server_status()
        self.assertEqual(status.collect_health, "ok")
        self.assertIsNone(status.log_tail)
        self.assertIsNotNone(status.last_collect_success_age_ms)


class StopServerCompareAndDeleteTest(HubDaemonIoScenarioTest):
    """검수 m1 — stop 진행 중 다른 프로세스가 이미 새 서버를 등록했으면 그 기록을 지우지 않는다."""

    def test_stop_does_not_wipe_a_newer_server_registered_mid_race(self) -> None:
        old_record = hub_server_state.ServerRecord(pid=111, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(old_record)

        def fake_ps_args(pid: int) -> str:
            # "그 사이" 다른 셸이 새 서버를 등록했다고 흉내낸 뒤, 예전 프로세스는 이미
            # 종료된 것처럼 보이는 빈 출력을 돌려줘 정리 분기를 태운다.
            hub_server_state_read.write_server_record(hub_server_state.ServerRecord(pid=222, port=8794, started_at_ms=2))
            return ""

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", side_effect=fake_ps_args):
            result = hub_daemon.stop_server()

        self.assertTrue(result["ok"])
        surviving_record = hub_server_state_read.read_server_record()
        self.assertIsNotNone(surviving_record)
        self.assertEqual(surviving_record.pid, 222)


class StopServerHeartbeatGateTest(HubDaemonIoScenarioTest):
    """S1·S2·S4~S6(설계 문서 hub-server-identity.md §9-3) — 신원 기준을 레코드의 기동
    경로로 옮기고, 신원 확인 실패 시 상태 파일 삭제를 하트비트로 게이트한다. S3(불일치 +
    하트비트 없음/만료 → 정리)은 기존 StopServerKillCallSiteTest.test_pid_reuse_does_not_send_a_signal
    이 이미 덮고 있고 이 회차의 수정 없이 그대로 통과해야 한다(그 테스트의 setUp 이 하트비트를
    만들지 않으므로 이미 이 조건이다)."""

    REPO_CHECKOUT_HUB_PY_PATH = "/Users/x/private/project/coding-harness/hub/bin/hub.py"

    def test_s1_two_installs_identity_match_now_sends_sigterm(self) -> None:
        """S1 — 결함 정본. 레코드가 레포 사본 경로를 기록했고 ps 도 그 경로를 돌려주면,
        판정 모듈 자신의 설치 경로(hub_daemon.HUB_PY_PATH)와 달라도 신원이 확인돼 SIGTERM
        이 간다. 수정 전 코드는 HUB_PY_PATH 와 대조해 불일치로 오판하고 kill 없이 상태
        파일만 지웠다(설계 문서 관측 A)."""
        record = hub_server_state.ServerRecord(
            pid=555, port=8794, started_at_ms=1, hub_py_path=self.REPO_CHECKOUT_HUB_PY_PATH
        )
        hub_server_state_read.write_server_record(record)
        ps_output = f"python3 {self.REPO_CHECKOUT_HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output), \
             mock.patch.object(
                 hub_daemon, "_wait_for_process_exit", return_value={"ok": True, "was_running": True}
             ) as mock_wait, \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_called_once_with(555, signal.SIGTERM)
        mock_wait.assert_called_once_with(record)
        self.assertTrue(result["ok"])
        self.assertTrue(result["was_running"])

    def test_s2_mismatch_with_fresh_heartbeat_preserves_state_and_reports_ok_false(self) -> None:
        """S2 — 고아 방지 정본(관측 A 의 재현). 레코드 경로와 ps 가 불일치하는데 하트비트가
        신선하면 오판을 의심해 아무것도 하지 않는다 — server.json·하트비트를 모두 보존하고
        ok:false + pid 를 보고한다(설계 문서 §5 판정표 마지막 행)."""
        record = hub_server_state.ServerRecord(
            pid=555, port=8794, started_at_ms=1, hub_py_path=self.REPO_CHECKOUT_HUB_PY_PATH
        )
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.touch_server_heartbeat()
        mismatched_ps_output = "/usr/sbin/cupsd"  # 그 사이 PID 를 차지한 무관한 프로세스를 흉내낸다

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=mismatched_ps_output), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["pid"], 555)
        self.assertIsNotNone(hub_server_state_read.read_server_record())
        self.assertIsNotNone(hub_server_state_read.read_server_heartbeat_mtime_ms())

    def test_s4_legacy_record_with_fresh_heartbeat_can_still_be_stopped(self) -> None:
        """S4 — 구버전 레코드(경로 없음)도 완화 기준으로 신원이 확인되면 정지할 수 있다
        (§3 의 "영구 정지 불가" 기각을 실제로 보장한다)."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)  # hub_py_path 없음
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.touch_server_heartbeat()
        ps_output = f"python3 {hub_daemon.HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output), \
             mock.patch.object(
                 hub_daemon, "_wait_for_process_exit", return_value={"ok": True, "was_running": True}
             ), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_called_once_with(555, signal.SIGTERM)
        self.assertTrue(result["ok"])

    def test_legacy_relaxed_match_with_expired_heartbeat_preserves_state_and_reports_ok_false(
        self,
    ) -> None:
        """Minor 1(2회차 검수) — 완화 판정(레코드 경로 없음 + ps 가 …/hub.py server-run)이
        참이어도 하트비트가 없으면(만료) kill 하지 않고 상태 파일을 보존한 채 ok:false 를
        낸다(hub-server-identity.md §5 판정표 마지막 행이 완화 분기에도 적용됨을 고정 —
        완화 판정 하나만으로는 "우리 서버라는 확증"이 되지 않는다). 대조군은 위
        test_s4_legacy_record_with_fresh_heartbeat_can_still_be_stopped(같은 완화 판정 +
        하트비트 신선 → 정상 정지)다 — 두 테스트가 하트비트 하나만 다르고 나머지 조건은
        같아, 이 게이트가 실제로 하트비트로 갈리는 것을 보인다."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)  # hub_py_path 없음
        hub_server_state_read.write_server_record(record)
        # 하트비트를 touch 하지 않는다 — 만료(부재) 상태를 그대로 둔다.
        ps_output = f"python3 {hub_daemon.HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["pid"], 555)
        self.assertIsNotNone(hub_server_state_read.read_server_record())

    def test_major1_non_path_recorded_value_with_expired_heartbeat_preserves_state(self) -> None:
        """Major 1(3회차 검수) — 완화 판정(레코드 값이 경로 형태가 아닌 "hub.py" + ps 가
        …/hub.py server-run)이 참이어도 하트비트가 없으면(만료) kill 하지 않고 상태를
        보존한 채 ok:false 를 낸다. 수정 전 코드는 `is_legacy_relaxed_match` 를
        `record.hub_py_path is None` 으로만 좁게 셌다 — "hub.py" 는 None 이 아니므로 그
        판정이 거짓이 되어 이 게이트를 건너뛰고 하트비트 없이 곧장 SIGTERM 이 나갔다(3회차
        검수가 이 입력으로 실제 kill 발사를 실측했다). 분모는 바로 아래
        test_major1_non_path_recorded_value_with_fresh_heartbeat_still_sends_sigterm 이다 —
        같은 입력에 하트비트만 신선하게 주면 kill 이 나가야, 이 부정 단언이 "모킹이 배선되지
        않아 0회"와 구별된다."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1, hub_py_path="hub.py")
        hub_server_state_read.write_server_record(record)
        # 하트비트를 touch 하지 않는다 — 만료(부재) 상태를 그대로 둔다.
        ps_output = f"python3 {hub_daemon.HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["pid"], 555)
        self.assertIsNotNone(hub_server_state_read.read_server_record())
        self.assertIsNone(hub_server_state_read.read_server_heartbeat_mtime_ms())

    def test_major1_non_path_recorded_value_with_fresh_heartbeat_still_sends_sigterm(self) -> None:
        """분모 — 위 테스트와 같은 입력(레코드 값 "hub.py")에 하트비트만 신선하게 주면
        정상 정지(SIGTERM)로 간다. 이 짝이 있어야 위 테스트의 kill 미호출이 "게이트가
        실제로 작동해서"임을 보인다(같은 이유를 든 문서는 StopServerKillCallSiteTest 의
        클래스 docstring 참고)."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1, hub_py_path="hub.py")
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.touch_server_heartbeat()
        ps_output = f"python3 {hub_daemon.HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output), \
             mock.patch.object(
                 hub_daemon, "_wait_for_process_exit", return_value={"ok": True, "was_running": True}
             ), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_called_once_with(555, signal.SIGTERM)
        self.assertTrue(result["ok"])

    def test_s5_legacy_record_relaxed_criteria_still_rejects_unrelated_process(self) -> None:
        """S5 — 구버전 레코드라도 강등이 무조건 kill 은 아니다: 하트비트가 없으면(만료)
        PID 재사용으로 판정해 상태 파일을 정리한다."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        unrelated_process_ps_output = "/usr/sbin/cupsd"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=unrelated_process_ps_output), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertIsNone(hub_server_state_read.read_server_record())

    def test_s6_ps_execution_failure_is_unchanged(self) -> None:
        """S6 — ps 실행 자체가 실패하면(None) 오늘 그대로 — 아무것도 하지 않고 상태
        파일을 보존한다."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=None), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertIsNotNone(hub_server_state_read.read_server_record())


class ServerStatusIdentityAcrossInstallsTest(HubDaemonIoScenarioTest):
    """S9(설계 문서 §9-3) — 관측 C 의 회귀 방지: server_status() 가 판정자 자기 모듈
    경로가 아니라 레코드에 적힌 기동 경로로 신원을 판정해야, 서로 다른 사본에게 같은
    살아 있는 서버의 상태를 물어도 같은 답이 나온다."""

    def test_process_present_true_even_when_module_path_differs_from_record(self) -> None:
        repo_checkout_path = "/Users/x/private/project/coding-harness/hub/bin/hub.py"
        record = hub_server_state.ServerRecord(
            pid=999, port=8794, started_at_ms=1, hub_py_path=repo_checkout_path
        )
        hub_server_state_read.write_server_record(record)
        ps_output_with_marker = f"python3 {repo_checkout_path} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=ps_output_with_marker), \
             mock.patch.object(hub_daemon, "_check_http_ok", return_value=False):
            status = hub_daemon.server_status()

        self.assertTrue(status.process_present)


class RestartServerHeartbeatGateTest(HubDaemonIoScenarioTest):
    """S10(설계 문서 §9-3) — stop 이 하트비트 게이트로 ok:false 를 내면 restart 도 start 를
    시도하지 않는다(기존 D4 유지). 실제 stop_server() 를 통해 통합 확인한다."""

    def test_restart_does_not_start_when_stop_is_gated_by_heartbeat(self) -> None:
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.touch_server_heartbeat()

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value="/usr/sbin/cupsd"), \
             mock.patch.object(hub_daemon, "start_server") as mock_start, \
             mock.patch.object(hub_daemon, "_wait_for_port_release"):
            result = hub_daemon.restart_server()

        mock_start.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["phase"], "stop")


class StopServerKillCallSiteTest(HubDaemonIoScenarioTest):
    """B7(PRP tests-hardening §9) — `os.kill` 호출부의 행위 테스트. 감사 재실측(2026-09-07,
    이 회차) — `tests/hub/` 전체에 `os.kill` 을 모킹하는 테스트가 0건이었다(패치·직접 호출
    모두). D1~D5(위 IsOurServerProcessTest)는 `is_our_server_process` 자체의 순수 판정만
    보고, 그 판정이 실제 kill 호출부까지 이어지는지는 보지 않았다 — 이 클래스가 그 간극을
    닫는다.

    「PID 재사용 → 죽이지 않는다」는 부정 단언이라 분모를 함께 공급한다: 같은 `os.kill`
    모킹으로 신원 확인이 **성공**하는 경로에서는 실제로 불린다는 것을
    test_identity_match_sends_sigterm 이 짝지어 확인한다 — 이 짝이 없으면 부정 단언은
    「모킹이 애초에 배선되지 않아 0회」인 경우와 구별되지 않는다."""

    def test_pid_reuse_does_not_send_a_signal(self) -> None:
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        reused_process_ps_output = "/usr/sbin/cupsd"  # 진짜 다른 프로세스 — PID 재사용 시나리오

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=reused_process_ps_output), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertIn("재사용", result["reason"])

    def test_identity_match_sends_sigterm(self) -> None:
        """분모 — 위 테스트와 같은 `os.kill` 모킹을 신원 확인이 성공하는 경로에 적용해 실제로
        호출됨을 확인한다. `_wait_for_process_exit` 는 결과를 고정 반환하도록 패치해 SIGTERM
        호출부만 격리한다(SIGKILL 승격은 아래 별도 테스트가 전담한다).

        레코드에 hub_py_path 를 채워 "정확한 경로 일치" 분기(hub-server-identity.md §5
        판정표의 「일치」행)를 태운다 — 이 분기는 하트비트 게이트를 거치지 않는다(2회차 검수
        §0). record.hub_py_path 를 비워 두면(구버전 레코드) 완화 판정으로 강등되고,
        하트비트가 없는 이 테스트의 setUp 에서는 완화 판정+하트비트 미신선 조합이 되어
        kill 이 보류된다 — 그 조합은
        StopServerHeartbeatGateTest.test_legacy_relaxed_match_with_expired_heartbeat_preserves_state_and_reports_ok_false
        가 따로 덮는다."""
        record = hub_server_state.ServerRecord(
            pid=555, port=8794, started_at_ms=1, hub_py_path=hub_daemon.HUB_PY_PATH
        )
        hub_server_state_read.write_server_record(record)
        matching_ps_output = f"python3 {hub_daemon.HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid", return_value=matching_ps_output), \
             mock.patch.object(
                 hub_daemon, "_wait_for_process_exit", return_value={"ok": True, "was_running": True}
             ) as mock_wait, \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon.stop_server()

        mock_kill.assert_called_once_with(555, signal.SIGTERM)
        mock_wait.assert_called_once_with(record)
        self.assertTrue(result["ok"])

    def test_sigterm_escalates_to_sigkill_when_process_survives_the_wait_window(self) -> None:
        """SIGKILL 승격 — SIGTERM 뒤에도 신원이 계속 확인되면(안 죽으면) 대기 상한에서
        SIGKILL 로 올린다. `time.monotonic` 을 직접 통제해 실제 SERVER_STOP_WAIT_SECONDS(5초)를
        기다리지 않는다: 1차 호출(deadline 계산)=0.0, 2차(루프 조건, 안 죽음 확인 1회
        발생)=1.0 < 5.0 이라 한 번 더 폴링하고, 3차(루프 조건)=100.0 이 되어서야 대기를
        포기하고 SIGKILL 로 넘어간다.

        `time.monotonic` 고정의 취약면은 **비대칭**이다(4회차 검수 접지 렌즈 실측).
        루프 **본문 안**에서 호출이 늘면 side_effect 가 바닥나 `StopIteration` 으로
        요란하게 죽는다. 그런데 루프 **진입 전**에 늘거나(진입 시각 기록 같은 추가)
        deadline 값을 첫 조건 검사에 재사용하는 리팩터를 하면, 실제 폴링 반복 횟수가
        0회나 2회로 바뀌는데도 최종 결과(kill 호출·반환값·레코드 삭제)만 보는 단언은
        그대로 통과한다 — 그래서 아래에 폴링 횟수(`_ps_args_for_pid` 호출 수)를 함께
        단언한다. 그 단언이 없으면 「SIGKILL 전에 몇 번 폴링하는가」가 드러나지 않은
        채 바뀔 수 있다.

        `_wait_for_process_exit` 는 이제 pid 가 아니라 record 를 받는다(설계 문서
        hub-server-identity.md §4·§7, R5) — 재확인도 record 의 경로로 대조해야 두 벌
        설치에서도 살아 있는 프로세스를 죽었다고 오판하지 않는다."""
        record = hub_server_state.ServerRecord(pid=555, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        matching_ps_output = f"python3 {hub_daemon.HUB_PY_PATH} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid",
                               return_value=matching_ps_output) as mock_ps, \
             mock.patch("time.monotonic", side_effect=[0.0, 1.0, 100.0]), \
             mock.patch("time.sleep"), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon._wait_for_process_exit(record)

        mock_kill.assert_called_once_with(555, signal.SIGKILL)
        # 폴링 1회(위 docstring 의 비대칭 참고) — 이 단언이 중간 상태를 고정한다.
        self.assertEqual(mock_ps.call_count, 1)
        self.assertEqual(result, {"ok": True, "was_running": True, "forced": True})
        self.assertIsNone(hub_server_state_read.read_server_record())  # compare-and-delete 로 정리됐다

    def test_s8_wait_for_process_exit_uses_record_path_not_module_path(self) -> None:
        """S8(설계 문서 §9-3) — 회귀 방지. record 의 경로가 hub_daemon.HUB_PY_PATH 와 달라도
        (두 벌 설치) 그 record 경로로 계속 살아 있음이 확인되면 SIGKILL 로 승격한다.
        `_wait_for_process_exit` 가 record 대신 자기 모듈 경로(HUB_PY_PATH)로 되돌아가면
        ps 출력이 그 경로와 맞지 않아 첫 폴링에서 곧바로 "안 살아있음"으로 오판하고
        clear_server_state 를 즉시 불러 SIGKILL 에 도달하지 못한다 — 이 테스트는 그
        되돌림이 일어나면 mock_kill 단언에서 깨진다(S7 은 record.hub_py_path 가 None 이라
        이 회귀를 잡지 못한다 — ps 가 우연히 HUB_PY_PATH 와도 일치하기 때문이다)."""
        repo_checkout_path = "/Users/x/private/project/coding-harness/hub/bin/hub.py"
        self.assertNotEqual(repo_checkout_path, hub_daemon.HUB_PY_PATH)
        record = hub_server_state.ServerRecord(
            pid=555, port=8794, started_at_ms=1, hub_py_path=repo_checkout_path
        )
        hub_server_state_read.write_server_record(record)
        ps_output = f"python3 {repo_checkout_path} server-run"

        with mock.patch.object(hub_daemon, "_ps_args_for_pid",
                               return_value=ps_output) as mock_ps, \
             mock.patch("time.monotonic", side_effect=[0.0, 1.0, 100.0]), \
             mock.patch("time.sleep"), \
             mock.patch("os.kill") as mock_kill:
            result = hub_daemon._wait_for_process_exit(record)

        mock_kill.assert_called_once_with(555, signal.SIGKILL)
        self.assertEqual(mock_ps.call_count, 1)
        self.assertEqual(result, {"ok": True, "was_running": True, "forced": True})


class RestartServerSequenceTest(HubDaemonIoScenarioTest):
    """restart_server 의 조합 계약(D3~D7) — stop/start 를 그대로 호출하고, stop 실패 시 start 를
    시도하지 않으며, 고아 하트비트는 실패로 보고한다. `_wait_for_port_release` 는 실제 소켓을
    건드리지 않도록 패치한다(테스트가 8794 포트를 폴링할 이유가 없다)."""

    def setUp(self) -> None:
        super().setUp()
        self.wait_patcher = mock.patch.object(hub_daemon, "_wait_for_port_release")
        self.mock_wait = self.wait_patcher.start()

    def tearDown(self) -> None:
        self.wait_patcher.stop()
        super().tearDown()

    def test_s1_stop_failure_never_starts_a_new_server(self) -> None:
        stop_result = {"ok": False, "reason": "ps 실행 실패 — 확인할 수 없어 아무것도 하지 않았습니다"}
        with mock.patch.object(hub_daemon, "stop_server", return_value=stop_result), \
             mock.patch.object(hub_daemon, "start_server") as mock_start:
            result = hub_daemon.restart_server()

        mock_start.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["phase"], "stop")
        self.assertEqual(result["reason"], stop_result["reason"])

    def test_s2_running_server_is_stopped_then_started(self) -> None:
        """PRP 테스트 계획 S2 — 호출 순서가 stop → 포트대기 → start 여야 한다(GOTCHA 2 완화 회귀 보호)."""
        stop_result = {"ok": True, "was_running": True}
        start_result = {"ok": True, "pid": 2, "url": "http://localhost:8794/hub.html"}
        call_order = mock.Mock()
        with mock.patch.object(hub_daemon, "stop_server", return_value=stop_result) as mock_stop, \
             mock.patch.object(hub_daemon, "start_server", return_value=start_result) as mock_start:
            call_order.attach_mock(mock_stop, "stop")
            call_order.attach_mock(self.mock_wait, "wait")
            call_order.attach_mock(mock_start, "start")
            result = hub_daemon.restart_server()

        self.assertTrue(result["ok"])
        self.assertTrue(result["stopped_previous"])
        self.assertEqual(result["pid"], 2)
        self.assertEqual(result["url"], start_result["url"])
        self.assertNotIn("note", result)
        default_server_port = hub_model.HubConfig().server_port
        self.assertEqual(
            call_order.mock_calls,
            [mock.call.stop(), mock.call.wait(default_server_port), mock.call.start()],
        )

    def test_s2b_absent_server_is_just_started(self) -> None:
        stop_result = {"ok": True, "was_running": False}
        start_result = {"ok": True, "pid": 3, "url": "http://localhost:8794/hub.html"}
        with mock.patch.object(hub_daemon, "stop_server", return_value=stop_result), \
             mock.patch.object(hub_daemon, "start_server", return_value=start_result):
            result = hub_daemon.restart_server()

        self.assertTrue(result["ok"])
        self.assertFalse(result["stopped_previous"])

    def test_s3_already_running_after_stop_is_reported_as_failure(self) -> None:
        stop_result = {"ok": True, "was_running": True}
        start_result = {"ok": True, "already_running": True}
        with mock.patch.object(hub_daemon, "stop_server", return_value=stop_result), \
             mock.patch.object(hub_daemon, "start_server", return_value=start_result):
            result = hub_daemon.restart_server()

        self.assertFalse(result["ok"])
        self.assertEqual(result["phase"], "start")
        self.assertIn("orphaned_evidence", result["reason"])

    def test_s4_forced_stop_surfaces_as_note(self) -> None:
        stop_result = {"ok": True, "was_running": True, "forced": True}
        start_result = {"ok": True, "pid": 4, "url": "http://localhost:8794/hub.html"}
        with mock.patch.object(hub_daemon, "stop_server", return_value=stop_result), \
             mock.patch.object(hub_daemon, "start_server", return_value=start_result):
            result = hub_daemon.restart_server()

        self.assertTrue(result["ok"])
        self.assertEqual(result["note"], hub_daemon.FORCED_STOP_NOTE)

    def test_s5_start_failure_carries_reason_and_log_tail(self) -> None:
        stop_result = {"ok": True, "was_running": True}
        start_result = {
            "ok": False,
            "reason": "포트 8794 이 이미 사용 중입니다(다른 프로세스)",
            "log_tail": "tail",
        }
        with mock.patch.object(hub_daemon, "stop_server", return_value=stop_result), \
             mock.patch.object(hub_daemon, "start_server", return_value=start_result):
            result = hub_daemon.restart_server()

        self.assertFalse(result["ok"])
        self.assertEqual(result["phase"], "start")
        self.assertEqual(result["reason"], start_result["reason"])
        self.assertEqual(result["log_tail"], start_result["log_tail"])


class OpenBrowserFallbackTest(unittest.TestCase):
    """D8·GOTCHA 7 — 포커스 경로 성공/실패, 미지원 플랫폼, 이중 실패를 예외 없이 흡수한다."""

    URL = "http://localhost:8794/hub.html"

    def test_o1_darwin_success_does_not_touch_webbrowser(self) -> None:
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)) as mock_run, \
             mock.patch("webbrowser.open") as mock_webbrowser_open:
            result = hub_daemon.open_browser(self.URL, platform_name="darwin")

        mock_run.assert_called_once()
        mock_webbrowser_open.assert_not_called()
        self.assertTrue(result.opened)
        self.assertTrue(result.focus_requested)
        self.assertIsNone(result.fallback_reason)

    def test_o2_darwin_failure_falls_back_with_reason(self) -> None:
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=1)), \
             mock.patch("webbrowser.open", return_value=True) as mock_webbrowser_open:
            result = hub_daemon.open_browser(self.URL, platform_name="darwin")

        mock_webbrowser_open.assert_called_once()
        self.assertTrue(result.opened)
        self.assertFalse(result.focus_requested)
        self.assertIsNotNone(result.fallback_reason)

    def test_o3_non_darwin_uses_webbrowser_only(self) -> None:
        with mock.patch("subprocess.run") as mock_run, \
             mock.patch("webbrowser.open", return_value=True):
            result = hub_daemon.open_browser(self.URL, platform_name="linux")

        mock_run.assert_not_called()
        self.assertTrue(result.opened)
        self.assertFalse(result.focus_requested)

    def test_o4_both_paths_failing_is_not_an_exception(self) -> None:
        with mock.patch("subprocess.run", side_effect=OSError("no such file")), \
             mock.patch("webbrowser.open", side_effect=RuntimeError("boom")):
            result = hub_daemon.open_browser(self.URL, platform_name="darwin")

        self.assertFalse(result.opened)

    def test_o5_non_darwin_webbrowser_exception_still_carries_a_reason(self) -> None:
        """검수 지적 — 포커스 경로 자체가 없는 플랫폼(fallback_reason 이 아직 None)에서
        webbrowser.open() 마저 예외를 던지면 그 사유가 소실되지 않아야 한다."""
        with mock.patch("webbrowser.open", side_effect=RuntimeError("boom")):
            result = hub_daemon.open_browser(self.URL, platform_name="linux")

        self.assertFalse(result.opened)
        self.assertEqual(result.fallback_reason, "boom")


if __name__ == "__main__":
    unittest.main()
