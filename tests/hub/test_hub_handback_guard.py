"""hub_handback_guard 단위 테스트 — docs/prps/background-task-orphans.md §6.3·§8.1-1.

순수 함수는 입력→출력만 본다. I/O 는 subprocess.run(lsof)·stdin·임시 기록 파일만 쓰고 실제 ~/.claude 는 건드리지 않는다.
픽스처의 훅 입력 모양은 실측(2.1.304 PreToolUse·SubagentHandback 입력 3줄)에서 가져왔다.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402  (sys.path 조정 후 임포트)
import hub_handback_guard  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다(test_hub_hook.py 의 관례).
try:
    from .live_activity_fixtures import (
        BASE_MS,
        SESSION_ID,
        jsonl_bytes as _window,
        moved_phrase as _moved_phrase,
        output_phrase as _output_phrase,
        result_line as _result_line,
    )
    from .swallowed_exception_guard import SwallowedExceptionGuardMixin
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from live_activity_fixtures import (  # noqa: E402
        BASE_MS,
        SESSION_ID,
        jsonl_bytes as _window,
        moved_phrase as _moved_phrase,
        output_phrase as _output_phrase,
        result_line as _result_line,
    )
    from swallowed_exception_guard import SwallowedExceptionGuardMixin  # noqa: E402

AGENT_ID = "a6f5c7aca8439993a"
OUTPUT_ROOT = "/t/x"


def _hook_input(**overrides: object) -> str:
    """실측 모양의 PreToolUse·SubagentHandback 입력(JSON 문자열). overrides 로 키를 바꾸고, 값이 None 이면 키를 뺀다."""
    payload: dict = {
        "session_id": SESSION_ID,
        "transcript_path": f"/home/u/.claude/projects/p/{SESSION_ID}.jsonl",
        "cwd": "/repo",
        "permission_mode": "auto",
        "agent_id": AGENT_ID,
        "agent_type": "implementer",
        "hook_event_name": "PreToolUse",
        "tool_name": "SubagentHandback",
        "tool_input": {"message": "완료"},
        "tool_use_id": "toolu_1",
    }
    payload.update(overrides)
    return json.dumps({key: value for key, value in payload.items() if value is not None})


def _launch(task_id: str) -> hub_activity.BackgroundLaunch:
    return hub_activity.BackgroundLaunch(task_id=task_id, output_path=f"{OUTPUT_ROOT}/{SESSION_ID}/tasks/{task_id}.output")


class ParseGuardInputTest(unittest.TestCase):
    def test_a_handback_input_yields_the_four_values(self) -> None:
        parsed = hub_handback_guard.parse_guard_input(_hook_input(tool_input={"message": "끝 b2l1gdl7h"}))

        self.assertEqual(
            parsed,
            hub_handback_guard.GuardInput(
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
                transcript_path=f"/home/u/.claude/projects/p/{SESSION_ID}.jsonl",
                report_message="끝 b2l1gdl7h",
            ),
        )

    def test_other_events_tools_and_missing_keys_are_none(self) -> None:
        invalid_inputs = {
            "other event": _hook_input(hook_event_name="PostToolUse"),
            "other tool": _hook_input(tool_name="Bash"),
            "no agent_id (main thread)": _hook_input(agent_id=None),
            "empty agent_id": _hook_input(agent_id=""),
            "no session_id": _hook_input(session_id=None),
            "no transcript_path": _hook_input(transcript_path=None),
            "no tool_input": _hook_input(tool_input=None),
            "tool_input without message": _hook_input(tool_input={"other": "x"}),
            "message is not a string": _hook_input(tool_input={"message": 3}),
            "tool_input is not an object": _hook_input(tool_input="x"),
            "agent_id walks out of the directory": _hook_input(agent_id="../../etc/passwd"),
            "agent_id with a space": _hook_input(agent_id="a b"),
        }
        for label, raw in invalid_inputs.items():
            with self.subTest(label):
                self.assertIsNone(hub_handback_guard.parse_guard_input(raw))

    def test_text_that_is_not_a_json_object_is_none(self) -> None:
        for label, raw in {"empty": "", "garbage": "{not json", "array": "[1]", "null": "null", "number": "7"}.items():
            with self.subTest(label):
                self.assertIsNone(hub_handback_guard.parse_guard_input(raw))


class SubagentTranscriptPathTest(unittest.TestCase):
    def test_the_real_layout_is_the_main_path_minus_jsonl_plus_subagents_directory(self) -> None:
        main_path = f"/Users/u/.claude/projects/-Users-u-repo/{SESSION_ID}.jsonl"

        path = hub_handback_guard.subagent_transcript_path(main_path, AGENT_ID)

        self.assertEqual(
            path, Path(f"/Users/u/.claude/projects/-Users-u-repo/{SESSION_ID}/subagents/agent-{AGENT_ID}.jsonl")
        )


class ParseLsofOpenNamesTest(unittest.TestCase):
    def test_only_the_name_lines_are_collected(self) -> None:
        lsof_output = "p60494\nf1\nn/t/a.output\np60496\nf1\nn/t/a.output\nf2\nn/t/b.output\n"

        names = hub_handback_guard.parse_lsof_open_names(lsof_output)

        self.assertEqual(names, frozenset({"/t/a.output", "/t/b.output"}))

    def test_empty_output_is_the_empty_set(self) -> None:
        self.assertEqual(hub_handback_guard.parse_lsof_open_names(""), frozenset())


class UndeclaredLiveLaunchesTest(unittest.TestCase):
    def _undeclared(self, launches: list, open_paths: set, report_message: str = "완료") -> tuple:
        return hub_handback_guard.undeclared_live_launches(launches, frozenset(open_paths), report_message)

    def test_a_launch_whose_output_file_is_not_held_is_dead_and_excluded(self) -> None:
        alive, dead = _launch("alive1"), _launch("dead1")

        result = self._undeclared([alive, dead], {alive.output_path})

        self.assertEqual(result, (alive,))

    def test_a_live_launch_named_in_the_report_is_declared_and_excluded(self) -> None:
        kept, other = _launch("keep1"), _launch("other1")

        result = self._undeclared([kept, other], {kept.output_path, other.output_path}, "서버 keep1 은 메인이 이어받는다")

        self.assertEqual(result, (other,))

    def test_an_id_that_is_only_part_of_another_word_does_not_declare_it(self) -> None:
        launch = _launch("abc")
        for label, message in {
            "suffix of a longer word": "xabc 를 남긴다",
            "prefix of a longer word": "abcd 를 남긴다",
            "inside a hyphenated word": "a-abc-b 를 남긴다",
            "inside an underscored word": "task_abc 를 남긴다",
        }.items():
            with self.subTest(label):
                self.assertEqual(self._undeclared([launch], {launch.output_path}, message), (launch,))

    def test_an_id_between_punctuation_and_spaces_declares_it(self) -> None:
        launch = _launch("abc")
        for message in ("ID: abc.", "(abc)", "abc", "작업 `abc` 남김", "남김:abc,"):
            with self.subTest(message):
                self.assertEqual(self._undeclared([launch], {launch.output_path}, message), ())

    def test_nothing_launched_or_nothing_open_is_empty(self) -> None:
        self.assertEqual(self._undeclared([], {"/x"}), ())
        self.assertEqual(self._undeclared([_launch("abc")], set()), ())


class DenyDecisionTest(unittest.TestCase):
    def test_the_json_shape_is_the_pretooluse_deny_envelope(self) -> None:
        decision = hub_handback_guard.deny_decision([_launch("abc")])

        self.assertEqual(list(decision), ["hookSpecificOutput"])
        self.assertEqual(
            set(decision["hookSpecificOutput"]), {"hookEventName", "permissionDecision", "permissionDecisionReason"}
        )
        self.assertEqual(decision["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_the_reason_names_every_id_and_path_and_the_three_exits(self) -> None:
        launches = [_launch("abc1"), _launch("def2")]

        reason = hub_handback_guard.deny_decision(launches)["hookSpecificOutput"]["permissionDecisionReason"]

        for launch in launches:
            self.assertIn(launch.task_id, reason)
            self.assertIn(launch.output_path, reason)
        for exit_token in ("TaskStop", "kill $(lsof -t", "이미 끝난 작업이라고 하면 보고 본문에 그 ID", "보고하지 말고 턴을 끝내", "보고 본문에 그 ID"):
            self.assertIn(exit_token, reason)

    def test_the_decision_is_json_serializable(self) -> None:
        json.dumps(hub_handback_guard.deny_decision([_launch("abc")]))


class OpenOutputPathsTest(unittest.TestCase):
    def _completed(self, stdout: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    def test_lsof_is_called_with_an_argv_list_after_double_dash_and_a_timeout(self) -> None:
        with mock.patch.object(subprocess, "run", return_value=self._completed("")) as run:
            hub_handback_guard._open_output_paths(["/t/a.output", "/t/b.output"])

        args, kwargs = run.call_args
        self.assertEqual(args[0], ["lsof", "-Fn", "--", "/t/a.output", "/t/b.output"])
        self.assertEqual(kwargs["timeout"], hub_handback_guard.LSOF_TIMEOUT_SECONDS)
        self.assertFalse(kwargs.get("shell", False))

    def test_only_requested_paths_that_lsof_reports_are_returned(self) -> None:
        with mock.patch.object(subprocess, "run", return_value=self._completed("p1\nf1\nn/t/a.output\n")):
            open_paths = hub_handback_guard._open_output_paths(["/t/a.output", "/t/b.output"])

        self.assertEqual(open_paths, frozenset({"/t/a.output"}))

    def test_a_symlinked_request_matches_the_real_name_lsof_prints(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp_dir, True)
        real_file = temp_dir / "real.output"
        real_file.write_text("")
        link = temp_dir / "link.output"
        link.symlink_to(real_file)
        lsof_stdout = f"p1\nf1\nn{os.path.realpath(real_file)}\n"

        with mock.patch.object(subprocess, "run", return_value=self._completed(lsof_stdout)):
            open_paths = hub_handback_guard._open_output_paths([str(link)])

        self.assertEqual(open_paths, frozenset({str(link)}))

    def test_a_missing_lsof_or_a_timeout_means_nothing_is_open(self) -> None:
        failures = (FileNotFoundError("lsof"), subprocess.TimeoutExpired(cmd="lsof", timeout=3), PermissionError("x"))
        for failure in failures:
            with self.subTest(type(failure).__name__):
                with mock.patch.object(subprocess, "run", side_effect=failure):
                    self.assertEqual(hub_handback_guard._open_output_paths(["/t/a.output"]), frozenset())

    def test_no_paths_means_no_lsof_call(self) -> None:
        with mock.patch.object(subprocess, "run") as run:
            self.assertEqual(hub_handback_guard._open_output_paths([]), frozenset())

        run.assert_not_called()

    @unittest.skipUnless(shutil.which("lsof"), "lsof 가 없는 환경")
    def test_the_real_lsof_sees_a_file_this_process_holds_open(self) -> None:
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp_dir, True)
        held = temp_dir / "held.output"
        released = temp_dir / "released.output"
        released.write_text("")

        with open(held, "w"):
            open_paths = hub_handback_guard._open_output_paths([str(held), str(released)])

        self.assertEqual(open_paths, frozenset({str(held)}))


class MainTest(SwallowedExceptionGuardMixin, unittest.TestCase):
    """main() — 어떤 입력에도 0 을 반환하고, 거부일 때만 stdout 에 JSON 한 줄을 낸다."""

    guarded_entrypoint_module = hub_handback_guard

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        self.main_transcript = self.temp_dir / f"{SESSION_ID}.jsonl"

    def _write_subagent_transcript(self, *bodies: object) -> None:
        subagents_dir = self.temp_dir / SESSION_ID / "subagents"
        subagents_dir.mkdir(parents=True)
        lines = [_result_line(BASE_MS + index, f"u{index}", body) for index, body in enumerate(bodies)]
        (subagents_dir / f"agent-{AGENT_ID}.jsonl").write_bytes(_window(*lines))

    def _run_main(self, raw_input: str, lsof_stdout: str = "", lsof_failure: BaseException | None = None) -> tuple[int, str]:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=lsof_stdout, stderr="")
        stdout = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(raw_input)), contextlib.redirect_stdout(stdout):
            with mock.patch.object(subprocess, "run", return_value=completed, side_effect=lsof_failure):
                exit_code = hub_handback_guard.main()
        return exit_code, stdout.getvalue()

    def _guard_input(self, message: str = "완료") -> str:
        return _hook_input(transcript_path=str(self.main_transcript), tool_input={"message": message})

    def _lsof_reports_open(self, task_id: str) -> str:
        return f"p1\nf1\nn{OUTPUT_ROOT}/{SESSION_ID}/tasks/{task_id}.output\n"

    def test_invalid_inputs_allow_silently(self) -> None:
        for label, raw in {
            "empty": "",
            "not json": "{oops",
            "other tool": _hook_input(tool_name="Bash"),
            "main thread (no agent_id)": _hook_input(agent_id=None),
        }.items():
            with self.subTest(label):
                self.assertEqual(self._run_main(raw), (0, ""))

    def test_a_missing_subagent_transcript_allows_silently(self) -> None:
        self.assertEqual(self._run_main(self._guard_input()), (0, ""))

    def test_a_transcript_without_launch_sentences_allows_without_calling_lsof(self) -> None:
        self._write_subagent_transcript("그냥 결과")
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        stdout = io.StringIO()

        with mock.patch("sys.stdin", io.StringIO(self._guard_input())), contextlib.redirect_stdout(stdout):
            with mock.patch.object(subprocess, "run", return_value=completed) as run:
                exit_code = hub_handback_guard.main()

        self.assertEqual((exit_code, stdout.getvalue()), (0, ""))
        run.assert_not_called()

    def test_lsof_missing_or_timed_out_allows_silently(self) -> None:
        self._write_subagent_transcript(_output_phrase(SESSION_ID, "abc", root=OUTPUT_ROOT))
        for failure in (FileNotFoundError("lsof"), subprocess.TimeoutExpired(cmd="lsof", timeout=3)):
            with self.subTest(type(failure).__name__):
                self.assertEqual(self._run_main(self._guard_input(), lsof_failure=failure), (0, ""))

    def test_a_live_undeclared_task_is_denied_with_one_json_line(self) -> None:
        self._write_subagent_transcript(_moved_phrase(SESSION_ID, "b2l1gdl7h", root=OUTPUT_ROOT))

        exit_code, output = self._run_main(self._guard_input(), self._lsof_reports_open("b2l1gdl7h"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.count("\n"), 1)
        decision = json.loads(output)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("b2l1gdl7h", decision["permissionDecisionReason"])

    def test_a_sibling_task_quoted_from_another_transcript_is_not_mine_and_is_allowed(self) -> None:
        """검수 1회차 지적 1 재현 — 형제 기록을 grep 해 그 시작 문장이 Bash 결과 중간에 실렸고, 형제 작업이 살아 있다."""
        sibling_line = json.dumps(_result_line(BASE_MS, "toolu_s", _output_phrase(SESSION_ID, "bsibling1", root=OUTPUT_ROOT)))
        self._write_subagent_transcript(f"agent-sibling.jsonl:42:{sibling_line}")

        result = self._run_main(self._guard_input(), self._lsof_reports_open("bsibling1"))

        self.assertEqual(result, (0, ""))

    def test_a_task_that_has_finished_is_allowed(self) -> None:
        self._write_subagent_transcript(_output_phrase(SESSION_ID, "abc", root=OUTPUT_ROOT))

        self.assertEqual(self._run_main(self._guard_input(), lsof_stdout=""), (0, ""))

    def test_a_live_task_named_in_the_report_is_allowed(self) -> None:
        self._write_subagent_transcript(_output_phrase(SESSION_ID, "abc", root=OUTPUT_ROOT))

        result = self._run_main(self._guard_input("개발 서버 abc 는 일부러 남긴다"), self._lsof_reports_open("abc"))

        self.assertEqual(result, (0, ""))

    def test_only_the_undeclared_live_tasks_are_listed_in_the_denial(self) -> None:
        self._write_subagent_transcript(
            _output_phrase(SESSION_ID, "keep1", root=OUTPUT_ROOT), _output_phrase(SESSION_ID, "stray1", root=OUTPUT_ROOT)
        )
        lsof_stdout = self._lsof_reports_open("keep1") + self._lsof_reports_open("stray1")

        _, output = self._run_main(self._guard_input("keep1 은 남긴다"), lsof_stdout)

        reason = json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("stray1", reason)
        self.assertNotIn("keep1", reason)

    def test_an_unexpected_error_is_swallowed_and_allows(self) -> None:
        self.expect_swallowed_exception(RuntimeError, "진입점 계약 — 어떤 예외도 보고를 막지 않는다(BG-G3 fail-open)")
        self._write_subagent_transcript(_output_phrase(SESSION_ID, "abc", root=OUTPUT_ROOT))

        with mock.patch.object(hub_handback_guard, "_open_output_paths", side_effect=RuntimeError("boom")):
            stdout = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(self._guard_input())), contextlib.redirect_stdout(stdout):
                exit_code = hub_handback_guard.main()

        self.assertEqual((exit_code, stdout.getvalue()), (0, ""))

    def test_a_transcript_larger_than_the_cap_is_read_from_its_tail_only(self) -> None:
        """상한 밖(앞부분)의 살아 있는 작업은 보지 않는다 — 상한을 무시하고 전체를 읽으면 head1 이 사유에 나타난다."""
        subagents_dir = self.temp_dir / SESSION_ID / "subagents"
        subagents_dir.mkdir(parents=True)
        head = _window(_result_line(BASE_MS, "head", _output_phrase(SESSION_ID, "head1", root=OUTPUT_ROOT)))
        filler = _window(*[_result_line(BASE_MS, "u", "x" * 100) for _ in range(40)])
        tail = _window(_result_line(BASE_MS, "tail", _output_phrase(SESSION_ID, "tail1", root=OUTPUT_ROOT)))
        (subagents_dir / f"agent-{AGENT_ID}.jsonl").write_bytes(head + filler + tail)
        both_open = self._lsof_reports_open("head1") + self._lsof_reports_open("tail1")

        with mock.patch.object(hub_handback_guard, "SUBAGENT_TRANSCRIPT_MAX_BYTES", len(tail) + 20):
            _, output = self._run_main(self._guard_input(), both_open)

        reason = json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("tail1", reason)
        self.assertNotIn("head1", reason)


if __name__ == "__main__":
    unittest.main()
