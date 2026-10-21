"""hub_dashboard_log.py 의 작업 이름표(`--task`) 테스트 — docs/prps/hub-dashboard-multi-task.md MT2.

test_hub_dashboard_log.py 는 이미 908행이라 따로 뒀다. 기록기 I/O 층이라 샌드박스 cwd·HOME 을 쓰고
실제 `$HOME` 은 건드리지 않는다(기존 모듈과 같은 준비).
"""

import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_dashboard_log  # noqa: E402  (sys.path 조정 후 임포트)

_PHASES = "구현|검수"


class _TaskLogTestCase(unittest.TestCase):
    SESSION_ID = "d4973ae5-cf0c-4cf2-b560-cb3606bc1cd2"

    def setUp(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        root = pathlib.Path(tmpdir.name)
        self._project_dir = root / "project"
        home_dir = root / "home"
        self._project_dir.mkdir(parents=True)
        home_dir.mkdir(parents=True)
        original_cwd = os.getcwd()
        os.chdir(self._project_dir)
        self.addCleanup(os.chdir, original_cwd)
        env_patch = mock.patch.dict(os.environ, {"HOME": str(home_dir), "CLAUDE_CODE_SESSION_ID": self.SESSION_ID})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def _jsonl_path(self) -> pathlib.Path:
        return self._project_dir / ".claude" / "dashboards" / ("%s.jsonl" % self.SESSION_ID)

    def _read_rows(self) -> list[dict]:
        text = self._jsonl_path().read_text(encoding="utf-8")
        return [json.loads(line) for line in text.split("\n") if line]

    def _read_text(self) -> str:
        return self._jsonl_path().read_text(encoding="utf-8")

    @staticmethod
    def _run(func, args: list[str]) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            func(args)
        return buffer.getvalue().strip()

    def _init(self, *args: str) -> str:
        return self._run(hub_dashboard_log.cmd_init, list(args))

    def _log(self, *args: str) -> str:
        return self._run(hub_dashboard_log.cmd_log, list(args))

    def _step(self, *args: str) -> str:
        return self._run(hub_dashboard_log.cmd_step, list(args))


class InitTaskTest(_TaskLogTestCase):
    """이름표 init 은 덧붙이고, 무표 init 은 지금처럼 새로 쓴다(MT2)."""

    def test_labeled_init_appends_and_keeps_earlier_records(self) -> None:
        self._init("첫 작업", _PHASES)
        self._log("impl", "첫 구현")

        output = self._init("--task", "결함①", "결함 수정", _PHASES)

        self.assertEqual(output, "OK")
        rows = self._read_rows()
        self.assertEqual([row["kind"] for row in rows], ["init", "impl", "init"])
        self.assertEqual(rows[2]["task"], "결함①")
        self.assertEqual(rows[2]["title"], "결함 수정")
        self.assertEqual(rows[2]["phases"], ["구현", "검수"])
        self.assertNotIn("task", rows[0])

    def test_labeled_init_creates_the_file_when_missing(self) -> None:
        output = self._init("--task", "B", "B 작업", _PHASES)

        self.assertEqual(output, "OK")
        self.assertEqual([row["task"] for row in self._read_rows()], ["B"])

    def test_unlabeled_init_still_rewrites_the_file_and_wipes_labeled_tasks(self) -> None:
        self._init("첫 작업", _PHASES)
        self._init("--task", "B", "B 작업", _PHASES)

        self._init("새 시작", _PHASES)

        rows = self._read_rows()
        self.assertEqual([row["title"] for row in rows], ["새 시작"])
        self.assertNotIn("task", rows[0])

    def test_unlabeled_init_writes_the_same_keys_as_before(self) -> None:
        self._init("제목", _PHASES)

        row = self._read_rows()[0]

        self.assertEqual(list(row.keys()), ["time_ms", "kind", "title", "phases", "project"])

    def test_same_label_init_again_appends_another_init_line(self) -> None:
        self._init("첫", _PHASES)
        self._init("--task", "B", "B 1", _PHASES)

        self._init("--task", "B", "B 2", _PHASES)

        self.assertEqual([row.get("task") for row in self._read_rows()], [None, "B", "B"])

    def test_option_value_edge_whitespace_is_trimmed(self) -> None:
        self._init("--task", "  B  ", "B 작업", _PHASES)

        self.assertEqual(self._read_rows()[0]["task"], "B")


class LogAndStepTaskTest(_TaskLogTestCase):
    """log·step 은 이름표를 그대로 기록하고, 이름표 없는 호출은 오늘과 같은 바이트를 쓴다."""

    def test_labeled_log_writes_the_task_key_last(self) -> None:
        self._init("첫", _PHASES)
        self._init("--task", "B", "B", _PHASES)

        output = self._log("--task", "B", "fail", "실패", "[검증] 상세")

        self.assertEqual(output, "OK")
        row = self._read_rows()[-1]
        self.assertEqual(list(row.keys()), ["time_ms", "kind", "summary", "detail", "task"])
        self.assertEqual((row["kind"], row["task"], row["detail"]), ("fail", "B", "[검증] 상세"))

    def test_unlabeled_log_writes_no_task_key(self) -> None:
        self._init("첫", _PHASES)

        self._log("impl", "구현")

        self.assertEqual(list(self._read_rows()[-1].keys()), ["time_ms", "kind", "summary", "detail"])

    def test_labeled_step_writes_the_task_key(self) -> None:
        self._init("첫", _PHASES)
        self._init("--task", "B", "B", _PHASES)

        output = self._step("--task", "B", "1", "done")

        self.assertEqual(output, "OK")
        row = self._read_rows()[-1]
        self.assertEqual(list(row.keys()), ["time_ms", "kind", "index", "state", "task"])

    def test_unlabeled_step_writes_no_task_key(self) -> None:
        self._init("첫", _PHASES)

        self._step("1", "done")

        self.assertEqual(list(self._read_rows()[-1].keys()), ["time_ms", "kind", "index", "state"])

    def test_unlabeled_log_is_ok_even_when_only_labeled_tasks_exist(self) -> None:
        self._init("--task", "A", "A", _PHASES)

        self.assertEqual(self._log("impl", "무표 구현"), "OK")
        self.assertEqual(self._step("1", "done"), "OK")

    def test_summary_starting_with_task_flag_text_is_not_an_option_after_the_kind(self) -> None:
        self._init("첫", _PHASES)

        output = self._log("impl", "--task 라는 글자로 시작하는 요약")

        self.assertEqual(output, "OK")
        row = self._read_rows()[-1]
        self.assertEqual(row["summary"], "--task 라는 글자로 시작하는 요약")
        self.assertNotIn("task", row)


class BadTaskTest(_TaskLogTestCase):
    """BADTASK — 어느 경우든 파일은 그대로다."""

    # `--task` 만 있고 값이 없는 호출(("--task",))은 뒤에 인자가 더 붙으면 그 인자가 값으로 읽히므로 따로 시험한다.
    BAD_OPTION_ARGS = (
        ("--task", ""),
        ("--task", "   "),
        ("--task", "가" * 21),
        ("--task", "줄\n바꿈"),
        ("--task=결함①",),
        ("--task=",),
        ("--taskx", "B"),
    )

    def test_init_rejects_bad_option_and_leaves_the_file_untouched(self) -> None:
        self._init("첫 작업", _PHASES)
        before = self._read_text()
        for option_args in self.BAD_OPTION_ARGS:
            with self.subTest(option_args=option_args):
                output = self._init(*option_args, "결함 수정", _PHASES)

                self.assertEqual(output, "BADTASK")
                self.assertEqual(self._read_text(), before)

    def test_option_without_any_value_is_rejected_by_every_subcommand(self) -> None:
        self._init("첫 작업", _PHASES)
        before = self._read_text()

        self.assertEqual(self._init("--task"), "BADTASK")
        self.assertEqual(self._log("--task"), "BADTASK")
        self.assertEqual(self._step("--task"), "BADTASK")
        self.assertEqual(self._read_text(), before)

    def test_task_equals_form_never_wipes_the_record_as_an_unlabeled_init(self) -> None:
        self._init("첫 작업", _PHASES)
        self._log("impl", "첫 구현")
        before = self._read_text()

        output = self._init("--task=결함①", "결함 수정", _PHASES)

        self.assertEqual(output, "BADTASK")
        self.assertEqual(self._read_text(), before)

    def test_log_and_step_reject_bad_option_and_leave_the_file_untouched(self) -> None:
        self._init("첫 작업", _PHASES)
        before = self._read_text()
        for option_args in self.BAD_OPTION_ARGS:
            with self.subTest(option_args=option_args):
                self.assertEqual(self._log(*option_args, "impl", "요약"), "BADTASK")
                self.assertEqual(self._step(*option_args, "1", "done"), "BADTASK")
                self.assertEqual(self._read_text(), before)

    def test_bad_init_on_a_missing_file_creates_nothing(self) -> None:
        self.assertEqual(self._init("--task", "", "제목", _PHASES), "BADTASK")

        self.assertFalse(self._jsonl_path().exists())


class MisplacedOptionAndArityTest(_TaskLogTestCase):
    """`--task` 가 서브커맨드 바로 뒤가 아닌 자리에 있거나 이름표 init 의 인자 수가 틀리면 BADTASK — 파일은 그대로다.
    버리거나(`log … --task B` 가 첫 작업 몫) 무표 init 으로 읽어(`init … --task C` 가 기록을 지움) 조용히 틀리게 쓰는 것을 막는다."""

    def _prepare(self) -> str:
        self._init("첫 작업", _PHASES)
        self._init("--task", "B", "B 작업", _PHASES)
        self._log("impl", "첫 구현")
        return self._read_text()

    def test_trailing_option_is_rejected_by_every_subcommand_without_touching_the_file(self) -> None:
        before = self._prepare()
        calls = {
            "init 맨 뒤": lambda: self._init("C 작업", _PHASES, "--task", "C"),
            "init 맨 뒤 등호": lambda: self._init("C 작업", _PHASES, "--task=C"),
            "log 상세 뒤": lambda: self._log("impl", "x", "상세", "--task", "B"),
            "log 상세 자리": lambda: self._log("impl", "x", "--task", "B"),
            "log 등호": lambda: self._log("impl", "x", "상세", "--task=B"),
            "step 뒤": lambda: self._step("1", "done", "--task", "B"),
        }
        for label, call in calls.items():
            with self.subTest(case=label):
                self.assertEqual(call(), "BADTASK")
                self.assertEqual(self._read_text(), before)

    def test_option_in_front_and_again_behind_is_rejected(self) -> None:
        before = self._prepare()

        self.assertEqual(self._log("--task", "B", "impl", "x", "--task", "B"), "BADTASK")
        self.assertEqual(self._read_text(), before)

    def test_labeled_init_with_wrong_positional_count_is_rejected(self) -> None:
        before = self._prepare()
        for positional in (("제목만",), ("제목", _PHASES, "초과"), ()):
            with self.subTest(positional=positional):
                self.assertEqual(self._init("--task", "C", *positional), "BADTASK")
                self.assertEqual(self._read_text(), before)

    def test_labeled_init_missing_the_label_value_never_crashes_and_writes_nothing(self) -> None:
        before = self._prepare()

        self.assertEqual(self._init("--task", "제목", _PHASES), "BADTASK")
        self.assertEqual(self._read_text(), before)

    def test_unlabeled_init_with_wrong_positional_count_is_rejected_without_wiping_the_record(self) -> None:
        # 철자 틀린 이름표 옵션이 무표 init 으로 읽혀 기록 전체를 지우던 경로(재검수 재현: 3줄 → 1줄 + OK).
        before = self._prepare()
        misspelled = {
            "대문자": ("C 작업", _PHASES, "--Task", "C"),
            "em dash": ("C 작업", _PHASES, "—task", "C"),
            "대시 하나": ("C 작업", _PHASES, "-task", "C"),
            "공백 든 단일 인자": ("C 작업", _PHASES, "--task C"),
            "복수형": ("C 작업", _PHASES, "--tasks", "C"),
            "앞자리 대문자": ("--Task", "C", _PHASES),
            "초과 인자": ("제목", _PHASES, "초과 인자"),
            "인자 하나": ("제목만",),
            "인자 없음": (),
        }
        for label, args in misspelled.items():
            with self.subTest(case=label):
                self.assertEqual(self._init(*args), "BADTASK")
                self.assertEqual(self._read_text(), before)

    def test_unlabeled_init_with_exactly_two_arguments_still_starts_a_new_record(self) -> None:
        self._prepare()

        self.assertEqual(self._init("새 시작", _PHASES), "OK")
        self.assertEqual([row["title"] for row in self._read_rows()], ["새 시작"])


class LabeledInitReadFailureTest(_TaskLogTestCase):
    """이름표 init 이 기존 기록을 읽지 못하면(파일은 있는데 권한 등) 빈 기록으로 보고 덮어쓰지 않고 MKDIR-FAILED 다."""

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root 는 권한 없는 파일도 읽는다")
    def test_unreadable_existing_file_is_not_overwritten(self) -> None:
        self._init("첫 작업", _PHASES)
        self._log("impl", "첫 구현")
        before = self._read_text()
        os.chmod(self._jsonl_path(), 0)
        self.addCleanup(os.chmod, self._jsonl_path(), 0o644)

        output = self._init("--task", "B", "B 작업", _PHASES)

        os.chmod(self._jsonl_path(), 0o644)
        self.assertEqual(output, "MKDIR-FAILED")
        self.assertEqual(self._read_text(), before)

    def test_missing_file_is_still_created_by_a_labeled_init(self) -> None:
        self.assertEqual(self._init("--task", "B", "B 작업", _PHASES), "OK")


class NoTaskTest(_TaskLogTestCase):
    """NOTASK — 이름표가 가리키는 살아 있는 작업이 없으면 쓰지 않는다."""

    def test_log_and_step_with_unknown_label_are_rejected_without_writing(self) -> None:
        self._init("첫", _PHASES)
        before = self._read_text()

        self.assertEqual(self._log("--task", "없는이름", "impl", "요약"), "NOTASK")
        self.assertEqual(self._step("--task", "없는이름", "1", "done"), "NOTASK")

        self.assertEqual(self._read_text(), before)

    def test_label_survives_its_own_restart(self) -> None:
        self._init("첫", _PHASES)
        self._init("--task", "B", "B 1", _PHASES)
        self._init("--task", "B", "B 2", _PHASES)

        self.assertEqual(self._log("--task", "B", "impl", "요약"), "OK")

    def test_label_wiped_by_an_unlabeled_init_is_a_notask(self) -> None:
        self._init("첫", _PHASES)
        self._init("--task", "B", "B", _PHASES)
        self._init("새 시작", _PHASES)

        self.assertEqual(self._log("--task", "B", "impl", "요약"), "NOTASK")

    def test_label_of_a_labeled_first_task_is_live(self) -> None:
        self._init("--task", "A", "A", _PHASES)

        self.assertEqual(self._log("--task", "A", "impl", "요약"), "OK")


class VocabularyOrderTest(_TaskLogTestCase):
    """검사 순서(MT2 표) — 앞에서 걸리면 거기서 끝난다."""

    def test_bad_label_beats_noinit(self) -> None:
        self.assertEqual(self._log("--task", "", "impl", "요약"), "BADTASK")
        self.assertEqual(self._step("--task", "", "1", "done"), "BADTASK")

    def test_good_label_without_a_file_is_noinit(self) -> None:
        self.assertEqual(self._log("--task", "B", "impl", "요약"), "NOINIT")
        self.assertEqual(self._step("--task", "B", "1", "done"), "NOINIT")

    def test_bad_kind_beats_unknown_label(self) -> None:
        self._init("첫", _PHASES)

        self.assertEqual(self._log("--task", "없는이름", "bogus", "요약"), "BADKIND")

    def test_bad_index_beats_unknown_label(self) -> None:
        self._init("첫", _PHASES)

        self.assertEqual(self._step("--task", "없는이름", "0", "done"), "BADINDEX")

    def test_nosession_and_disabled_come_before_bad_label(self) -> None:
        del os.environ["CLAUDE_CODE_SESSION_ID"]
        self.assertEqual(self._init("--task", "", "제목", _PHASES), "NOSESSION")

        os.environ["CLAUDE_CODE_SESSION_ID"] = self.SESSION_ID
        settings_path = self._project_dir / ".claude" / "settings.local.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"dashboard_enabled": False}), encoding="utf-8")
        self.assertEqual(self._init("--task", "", "제목", _PHASES), "DISABLED")
        self.assertEqual(self._log("--task", "", "impl", "요약"), "DISABLED")


class MainDispatchTest(_TaskLogTestCase):
    """디스패치 — init 은 남은 인자 전부를 cmd_init 에 넘긴다."""

    def test_main_passes_the_task_option_through_to_init(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = hub_dashboard_log.main(["init", "--task", "B", "B 작업", _PHASES])

        self.assertEqual((exit_code, buffer.getvalue().strip()), (0, "OK"))
        self.assertEqual(self._read_rows()[0]["task"], "B")


if __name__ == "__main__":
    unittest.main()
