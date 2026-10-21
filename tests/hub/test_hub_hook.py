"""hub_hook.py 단위 테스트. 실제 ~/.claude 는 건드리지 않고 hub_collect·hub_server_state_read 의
모듈 상수를 임시 디렉토리로 바꿔치기한 뒤 원상복구한다. 검수 M4(서브프로세스 분리)·M5(리텐션
도달성) 대상.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402
import hub_hook  # noqa: E402
import hub_server_state_read  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다 —
# 이 파일 맨 아래 unittest.main() 진입점이 이미 후자를 지원하고 있었다.
try:
    from .swallowed_exception_guard import SwallowedExceptionGuardMixin
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from swallowed_exception_guard import SwallowedExceptionGuardMixin  # noqa: E402

EIGHT_DAYS_SECONDS = 8 * 24 * 60 * 60
ONE_HOUR_SECONDS = 60 * 60
MACOS_PATH_MAX_BYTES = 1024      # 이벤트 줄에 함께 실리는 cwd 의 현실적 최댓값
SESSION_ID_LENGTH = 36           # UUID 문자열 길이


class HubHookScenarioTest(SwallowedExceptionGuardMixin, unittest.TestCase):
    """훅 진입점 시나리오의 공통 베이스. 삼킨 예외 가드는 믹스인이 담당한다(PRP §4.5)."""

    guarded_entrypoint_module = hub_hook

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_html_path = hub_collect.HUB_HTML_PATH
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_spawn_stamp_path = hub_collect.SPAWN_STAMP_PATH
        self.original_heartbeat_path = hub_server_state_read.SERVER_HEARTBEAT_PATH

        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.EVENTS_DIR.mkdir()
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.SPAWN_STAMP_PATH = self.temp_dir / ".collect_spawn_stamp"
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.temp_dir / "server_heartbeat"

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.HUB_HTML_PATH = self.original_html_path
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.SPAWN_STAMP_PATH = self.original_spawn_stamp_path
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.original_heartbeat_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_hook_with_stdin(self, payload: dict) -> None:
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            hub_hook.main()


class RetentionReachabilityTest(HubHookScenarioTest):
    """검수 M5 — hub.html 이 없어도(허브 off 상태) 리텐션이 여전히 동작해야 한다."""

    def test_old_event_file_pruned_even_without_hub_html(self) -> None:
        old_date = time.strftime("%Y-%m-%d", time.localtime(time.time() - EIGHT_DAYS_SECONDS))
        old_file = hub_collect.EVENTS_DIR / f"{old_date}.jsonl"
        old_file.write_text('{"t":1,"e":"Stop","s":"s","c":"/repo"}\n')

        self.assertFalse(hub_collect.HUB_HTML_PATH.exists())  # 허브 off 상태 전제

        # 검수 M2-5 이후로는 이 조합(hub.html 없음 + 서버 죽음)이 실제로 spawn 을 한다 — 이
        # 테스트의 관심사는 리텐션 정리이므로 subprocess.Popen 을 모킹해 실제 프로세스를
        # 띄우지 않는다(실제 ~/.claude 를 건드리지 않는다는 이 파일의 전제를 지킨다).
        with mock.patch("subprocess.Popen"):
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s2", "cwd": "/repo"})

        self.assertFalse(old_file.exists())


class SpawnsBackgroundCollectTest(HubHookScenarioTest):
    """검수 M4 — 훅은 재수집을 서브프로세스로 떼어내고 자신은 무거운 작업을 하지 않는다."""

    def test_stale_hub_html_triggers_subprocess_spawn_not_inline_collect(self) -> None:
        hub_collect.HUB_HTML_PATH.write_text("stale-marker")
        old_time = time.time() - ONE_HOUR_SECONDS
        os.utime(hub_collect.HUB_HTML_PATH, (old_time, old_time))

        with mock.patch("subprocess.Popen") as mock_popen, \
             mock.patch.object(hub_collect, "collect_snapshot") as mock_collect_snapshot, \
             mock.patch.object(hub_collect, "write_hub_html") as mock_write_hub_html:
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})

        mock_popen.assert_called_once()
        spawned_command = mock_popen.call_args[0][0]
        self.assertIn("collect", spawned_command)
        mock_collect_snapshot.assert_not_called()
        mock_write_hub_html.assert_not_called()

    def test_fresh_hub_html_does_not_spawn(self) -> None:
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")  # mtime = 지금

        with mock.patch("subprocess.Popen") as mock_popen:
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})

        mock_popen.assert_not_called()

    def test_missing_hub_html_spawns_when_server_is_not_alive(self) -> None:
        """검수 M2-5 — 서버가 죽어 있고(하트비트 없음) hub.html 도 없으면 훅 폴백이 뚫려야
        한다. 예전에는 이 조합이 항상 False 라, 상주 서버가 HUB_HOME 쓰기 실패 등으로
        hub.html 을 한 번도 못 만든 채 수집 스레드까지 죽으면 훅 폴백조차 영원히 막혀
        사용자가 영구히 빈 페이지만 보는 이중 실패였다(hub_server_state.should_spawn_collect 참조)."""
        with mock.patch("subprocess.Popen") as mock_popen:
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})

        mock_popen.assert_called_once()


class ServerDelegationTest(HubHookScenarioTest):
    """검수 개정 쟁점 R3 — 상주 서버가 살아 있으면(하트비트 신선) 훅은 spawn 하지 않는다."""

    def test_fresh_heartbeat_suppresses_spawn_even_with_stale_hub_html(self) -> None:
        hub_collect.HUB_HTML_PATH.write_text("stale-marker")
        old_time = time.time() - ONE_HOUR_SECONDS
        os.utime(hub_collect.HUB_HTML_PATH, (old_time, old_time))
        hub_server_state_read.SERVER_HEARTBEAT_PATH.write_text("")  # mtime = 지금 = 신선한 하트비트

        with mock.patch("subprocess.Popen") as mock_popen:
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})

        mock_popen.assert_not_called()

    def test_stale_heartbeat_falls_back_to_hook_spawn(self) -> None:
        hub_collect.HUB_HTML_PATH.write_text("stale-marker")
        old_time = time.time() - ONE_HOUR_SECONDS
        os.utime(hub_collect.HUB_HTML_PATH, (old_time, old_time))
        hub_server_state_read.SERVER_HEARTBEAT_PATH.write_text("")
        os.utime(hub_server_state_read.SERVER_HEARTBEAT_PATH, (old_time, old_time))  # 서버 크래시 흉내

        with mock.patch("subprocess.Popen") as mock_popen:
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})

        mock_popen.assert_called_once()


class ThrottleDebounceStampTest(HubHookScenarioTest):
    """검수 n3 — 훅 버스트(여러 세션이 거의 동시에 훅을 쏘는 경우) 에서 spawn 이 한 번만 일어난다.

    hub.html 의 mtime 은 spawn 된 자식 프로세스가 다 끝나야 바뀌므로, 그것만 보면 뒤따르는
    훅들이 전부 spawn 을 결정해 버린다(실측: 훅 6개 버스트 → 동시 collect 6개). spawn 직전에
    스탬프를 찍어 디바운스 판정 시점을 옮긴다.
    """

    def test_burst_of_hooks_spawns_collect_only_once(self) -> None:
        hub_collect.HUB_HTML_PATH.write_text("stale-marker")
        old_time = time.time() - ONE_HOUR_SECONDS
        os.utime(hub_collect.HUB_HTML_PATH, (old_time, old_time))

        with mock.patch("subprocess.Popen") as mock_popen:
            for _ in range(3):
                self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})

        mock_popen.assert_called_once()

    def test_stamp_is_touched_before_first_spawn(self) -> None:
        hub_collect.HUB_HTML_PATH.write_text("stale-marker")
        old_time = time.time() - ONE_HOUR_SECONDS
        os.utime(hub_collect.HUB_HTML_PATH, (old_time, old_time))

        self.assertFalse(hub_collect.SPAWN_STAMP_PATH.exists())
        with mock.patch("subprocess.Popen"):
            self._run_hook_with_stdin({"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo"})
        self.assertTrue(hub_collect.SPAWN_STAMP_PATH.exists())


class PromptExcerptRemovedTest(HubHookScenarioTest):
    """결정 PS4(docs/prps/hub-agent-runs-and-prompt-source.md) — 훅은 더 이상 프롬프트를
    기록하지 않는다. 발췌 출처는 transcript 의 `last-prompt`(hub_transcript.parse_session_tail)
    로 옮겨갔다 — 옛 PromptRecordingTest·AutoInjectedPromptTest 가 검증하던 clip·자동주입
    벗기기 로직 자체가 이 파일에서 사라졌으므로 그 표는 폐기하고, "안 남는다"만 확인한다.
    """

    def _record_and_read_last_line(self, prompt: str) -> dict:
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")   # spawn 억제(이 테스트의 관심사 밖)
        self._run_hook_with_stdin({
            "hook_event_name": "UserPromptSubmit", "session_id": "s", "cwd": "/repo",
            "prompt": prompt,
        })
        today = time.strftime("%Y-%m-%d", time.localtime())
        lines = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_long_prompt_leaves_no_p_key_in_the_recorded_line(self) -> None:
        prompt = ("긴 프롬프트 " * 60).strip()
        recorded = self._record_and_read_last_line(prompt)
        self.assertNotIn("p", recorded)
        self.assertEqual(recorded["e"], "UserPromptSubmit")   # 턴 상태 판정 근거는 여전히 남는다

    def test_secret_bearing_prompt_never_appears_anywhere_in_the_event_file(self) -> None:
        secret_prompt = "이 키 좀 봐줘 sk-ant-abcdefghijklmnopqrstuvwxyz 고마워"
        self._record_and_read_last_line(secret_prompt)
        today = time.strftime("%Y-%m-%d", time.localtime())
        raw_file_text = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(secret_prompt, raw_file_text)
        self.assertNotIn("sk-ant-abcdefghijklmnopqrstuvwxyz", raw_file_text)

    def test_no_prompt_related_symbols_remain_on_the_hook_module(self) -> None:
        """역방향 — PROMPT_EXCERPT_MAX_CHARS·strip_auto_injected_blocks 등 삭제 대상 심볼이
        전부 없어졌는지 이름으로도 확인한다(T25-211 이 소스 텍스트로 같은 것을 문다)."""
        removed_symbols = (
            "PROMPT_EXCERPT_MAX_CHARS", "PROMPT_TRUNCATION_MARK",
            "AUTO_INJECTED_PROMPT_BLOCK", "strip_auto_injected_blocks", "_clip_prompt",
        )
        for symbol in removed_symbols:
            with self.subTest(symbol=symbol):
                self.assertFalse(hasattr(hub_hook, symbol))


class OtherHookEventsAreUnaffectedTest(HubHookScenarioTest):
    """§10.1 — 나머지 5종 훅(UserPromptSubmit 이외)은 오늘과 문자 단위로 같은 줄을 남긴다."""

    def _recorded_line(self, payload: dict) -> dict:
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")
        self._run_hook_with_stdin(payload)
        today = time.strftime("%Y-%m-%d", time.localtime())
        lines = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_subagent_start_keeps_agent_id_and_type(self) -> None:
        recorded = self._recorded_line({
            "hook_event_name": "SubagentStart", "session_id": "s", "cwd": "/repo",
            "agent_id": "agt-1", "agent_type": "implementer",
        })
        self.assertEqual(recorded["ai"], "agt-1")
        self.assertEqual(recorded["at"], "implementer")

    def test_stop_session_end_source_and_reason_are_recorded(self) -> None:
        for hook_event_name in ("SubagentStop", "Stop", "SessionEnd", "SessionStart"):
            with self.subTest(hook_event_name=hook_event_name):
                recorded = self._recorded_line({
                    "hook_event_name": hook_event_name, "session_id": "s", "cwd": "/repo",
                    "source": "startup", "reason": "clear",
                })
                self.assertEqual(recorded["e"], hook_event_name)
                self.assertEqual(recorded["so"], "startup")
                self.assertEqual(recorded["r"], "clear")


class StopFailureProjectionTest(HubHookScenarioTest):
    """H1~H4 — 결정 RI7(docs/prps/hub-rate-limit-interruption.md). StopFailure 투영은
    오류 종류 하나만 남기고, 두 자유 텍스트 필드(error_details·last_assistant_message)는
    절대 기록하지 않는다."""

    def _recorded_line(self, payload: dict) -> dict:
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")   # spawn 억제(이 테스트의 관심사 밖)
        self._run_hook_with_stdin(payload)
        today = time.strftime("%Y-%m-%d", time.localtime())
        lines = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_h1_only_error_kind_is_recorded_free_text_fields_never_appear(self) -> None:
        """V1 실측 입력 형태(§8.2) 그대로 재현 — 실측 키 9개(cwd·effort·error·
        hook_event_name·last_assistant_message·prompt_id·scratchpad_dir·session_id·
        transcript_path) 를 전부 채운다(검수 1회차 MEDIUM ① — effort·prompt_id·
        scratchpad_dir·transcript_path 가 빠져 있으면, 이 넷을 추가로 기록하게 만드는
        변조가 걸릴 게 없어 키 집합 단언을 우연히 통과한다). error_details·
        last_assistant_message 는 키도 값도 기록 줄 어디에도 없어야 한다."""
        error_details = "429 rate limit exceeded, retry after 300s"
        last_assistant_message = "There's an issue with the selected model — please pick another one."
        payload = {
            "hook_event_name": "StopFailure", "session_id": "s", "cwd": "/repo",
            "effort": "high", "error": "rate_limit", "error_details": error_details,
            "last_assistant_message": last_assistant_message,
            "prompt_id": "prompt-e5f6a1", "scratchpad_dir": "/repo/.claude/scratchpad",
            "transcript_path": "/Users/x/.claude/projects/-repo/9dbd335d.jsonl",
        }
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")
        self._run_hook_with_stdin(payload)
        today = time.strftime("%Y-%m-%d", time.localtime())
        raw_line = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()[-1]
        recorded = json.loads(raw_line)
        self.assertEqual(set(recorded), {"t", "e", "s", "c", "er"})
        self.assertEqual(recorded["er"], "rate_limit")
        self.assertNotIn(error_details, raw_line)
        self.assertNotIn(last_assistant_message, raw_line)

    def test_h2_shape_violation_error_becomes_unknown(self) -> None:
        recorded = self._recorded_line({
            "hook_event_name": "StopFailure", "session_id": "s", "cwd": "/repo",
            "error": "Rate Limit!",
        })
        self.assertEqual(recorded["er"], "unknown")

    def test_h3_subagent_payload_records_agent_id_and_type(self) -> None:
        recorded = self._recorded_line({
            "hook_event_name": "StopFailure", "session_id": "s", "cwd": "/repo",
            "error": "rate_limit", "agent_id": "agt-1", "agent_type": "code-reviewer",
        })
        self.assertEqual(recorded["ai"], "agt-1")
        self.assertEqual(recorded["at"], "code-reviewer")
        self.assertEqual(recorded["er"], "rate_limit")

    def test_h4_other_event_with_error_key_does_not_record_er(self) -> None:
        """GOTCHA 8 — er 는 StopFailure 전용이다. 다른 훅에 같은 이름의 필드가 있어도 새지
        않는다."""
        recorded = self._recorded_line({
            "hook_event_name": "Stop", "session_id": "s", "cwd": "/repo", "error": "rate_limit",
        })
        self.assertNotIn("er", recorded)


class BackgroundProjectionTest(HubHookScenarioTest):
    """H1~H7 — 결정 BW2(docs/prps/hub-subagent-background-pause.md). Stop·SubagentStop 의
    background_tasks·session_crons 투영은 종류별 개수(bt)·1회성 예약 수(sw)만 남기고,
    자유 텍스트·id·status 는 어디에도 남지 않는다."""

    def _recorded_line(self, payload: dict) -> dict:
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")   # spawn 억제(이 테스트의 관심사 밖)
        self._run_hook_with_stdin(payload)
        today = time.strftime("%Y-%m-%d", time.localtime())
        lines = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_h1_stop_projects_counts_only_free_text_and_ids_never_appear(self) -> None:
        secret_description = "실행 중인 명령: rm -rf /some/secret/path"
        secret_command = "curl https://internal.example.com/secret-token"
        secret_prompt = "이 프롬프트에는 비밀이 있다 sk-ant-abcdefghijklmnop"
        payload = {
            "hook_event_name": "Stop", "session_id": "s", "cwd": "/repo",
            "background_tasks": [{
                "id": "task-1", "type": "shell", "status": "running",
                "description": secret_description, "command": secret_command,
            }],
            "session_crons": [{"id": "cron-1", "schedule": "*/5 * * * *", "recurring": False, "prompt": secret_prompt}],
        }
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")
        self._run_hook_with_stdin(payload)
        today = time.strftime("%Y-%m-%d", time.localtime())
        raw_line = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()[-1]
        recorded = json.loads(raw_line)
        self.assertEqual(set(recorded), {"t", "e", "s", "c", "bt", "sw"})
        self.assertEqual(recorded["bt"], {"shell": 1})
        self.assertEqual(recorded["sw"], 1)
        for secret in ("task-1", "cron-1", secret_description, secret_command, secret_prompt):
            self.assertNotIn(secret, raw_line)

    def test_h2_subagent_stop_keeps_agent_fields_alongside_bt_sw(self) -> None:
        recorded = self._recorded_line({
            "hook_event_name": "SubagentStop", "session_id": "s", "cwd": "/repo",
            "agent_id": "agt-1", "agent_type": "implementer",
            "background_tasks": [{"type": "shell"}], "session_crons": [],
        })
        self.assertEqual(recorded["ai"], "agt-1")
        self.assertEqual(recorded["at"], "implementer")
        self.assertEqual(recorded["bt"], {"shell": 1})
        self.assertEqual(recorded["sw"], 0)

    def test_h3_other_events_never_record_bt_or_sw(self) -> None:
        for hook_event_name in ("UserPromptSubmit", "SubagentStart"):
            with self.subTest(hook_event_name=hook_event_name):
                recorded = self._recorded_line({
                    "hook_event_name": hook_event_name, "session_id": "s", "cwd": "/repo",
                    "background_tasks": [{"type": "shell"}], "session_crons": [{"recurring": False}],
                })
                self.assertNotIn("bt", recorded)
                self.assertNotIn("sw", recorded)

    def test_h4_missing_or_wrong_typed_arrays_never_record_bt_or_sw(self) -> None:
        malformed_payloads = {
            "missing": {},
            "dict": {"background_tasks": {}, "session_crons": {}},
            "str": {"background_tasks": "shell", "session_crons": "x"},
        }
        for label, extra in malformed_payloads.items():
            with self.subTest(label=label):
                payload = {"hook_event_name": "Stop", "session_id": "s", "cwd": "/repo", **extra}
                recorded = self._recorded_line(payload)
                self.assertNotIn("bt", recorded)
                self.assertNotIn("sw", recorded)

    def test_h4b_session_crons_counts_one_shot_only(self) -> None:
        recorded = self._recorded_line({
            "hook_event_name": "Stop", "session_id": "s", "cwd": "/repo",
            "background_tasks": [],
            "session_crons": [{"recurring": True}, {}, "not-a-dict", {"recurring": False}],
        })
        self.assertEqual(recorded["sw"], 1)

    def test_h5_scan_max_truncation_keeps_the_total_and_caps_kinds(self) -> None:
        """300개(shell 250 + 이상한 것 50) — 앞 256개만 분류하고 나머지는 unknown 으로
        센다. 합계는 300 이 유지되고 종류 수는 상한(8) 이하다."""
        weird_tasks = [{"type": None} for _ in range(50)]
        shell_tasks = [{"type": "shell"} for _ in range(250)]
        recorded = self._recorded_line({
            "hook_event_name": "Stop", "session_id": "s", "cwd": "/repo",
            "background_tasks": weird_tasks + shell_tasks, "session_crons": [],
        })
        self.assertLessEqual(len(recorded["bt"]), 8)
        self.assertEqual(sum(recorded["bt"].values()), 300)

    def test_h6_twelve_distinct_kinds_collapse_overflow_into_unknown(self) -> None:
        # 정규화 패턴([a-z_]만, 숫자 없음)을 통과해야 "서로 다른 유효한 종류"가 된다 —
        # "kind0" 처럼 숫자가 섞이면 전부 unknown 하나로 접혀 이 테스트의 전제가 깨진다.
        twelve_distinct_tasks = [{"type": f"kind_{letter}"} for letter in "abcdefghijkl"]
        recorded = self._recorded_line({
            "hook_event_name": "Stop", "session_id": "s", "cwd": "/repo",
            "background_tasks": twelve_distinct_tasks, "session_crons": [],
        })
        self.assertEqual(len(recorded["bt"]), 8)
        self.assertIn("unknown", recorded["bt"])
        self.assertEqual(sum(recorded["bt"].values()), 12)

    def test_h7_non_dict_or_typeless_tasks_count_as_unknown(self) -> None:
        recorded = self._recorded_line({
            "hook_event_name": "Stop", "session_id": "s", "cwd": "/repo",
            "background_tasks": ["not-a-dict", {"status": "running"}], "session_crons": [],
        })
        self.assertEqual(recorded["bt"], {"unknown": 2})

    def test_h_pw1_artifact_watch_payload_is_still_counted_as_monitor_without_its_text(self) -> None:
        """결정 PW2(docs/prps/hub-bg-wait-passive-watch.md) — 아티팩트 실시간 감시는 기록에 그대로 monitor 로 남는다.
        「백그라운드 대기」에서 빼는 일은 판정층이 하고, 훅이 monitor 를 걸러 내면 이 테스트가 깨진다."""
        artifact_url = "https://claude.ai/artifact/FAKE-ARTIFACT-KEY"
        watch_description = f"live updates for artifact {artifact_url} (re-armed on session resume)"
        payload = {
            "hook_event_name": "SubagentStop", "session_id": "s", "cwd": "/repo",
            "agent_id": "agt-1", "agent_type": "bt-probe",
            "background_tasks": [
                {"id": "s3fakewatch", "type": "monitor", "status": "running", "description": watch_description},
                {"id": "a9fakeagent", "type": "subagent", "status": "running",
                 "agent_type": "bt-probe", "description": "probe agent"},
            ],
            "session_crons": [],
        }
        hub_collect.HUB_HTML_PATH.write_text("fresh-marker")
        self._run_hook_with_stdin(payload)
        today = time.strftime("%Y-%m-%d", time.localtime())
        raw_line = (hub_collect.EVENTS_DIR / f"{today}.jsonl").read_text(encoding="utf-8").splitlines()[-1]
        self.assertEqual(json.loads(raw_line)["bt"], {"monitor": 1, "subagent": 1})
        for leaked in (watch_description, "claude.ai/artifact", "s3fakewatch", "a9fakeagent"):
            self.assertNotIn(leaked, raw_line)


if __name__ == "__main__":
    unittest.main()
