"""hub_subagent_read 의 「활동」 읽기 단위 테스트 — 생존 신호 mtime(SL-R1~R8)과 도는 실행의 활동·백그라운드 대기 출력 요약(LA-R1~R9).

docs/prps/hub-subagent-liveness-signal.md §7.2(ReadUnfinishedSubagentActivityTest) · docs/prps/hub-live-activity.md §10.2
(ReadLiveActivityTest). test_hub_subagent_read.py 가 800줄 상한을 넘어 두 클래스를 이 파일로 옮겼다(본문은 그대로다).
공용 합성 기록 픽스처는 live_activity_fixtures.py 를 쓴다.
"""

import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402
import hub_project  # noqa: E402
import hub_session  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_subagent  # noqa: E402
import hub_subagent_read  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다(test_hub_template_dom.py 의 관례).
try:
    from .live_activity_fixtures import (
        BASE_MS,
        MINUTE_MS,
        SECOND_MS,
        SENTINEL_OUTPUT,
        jsonl_bytes as _jsonl_bytes,
        line as _line,
        output_phrase as _output_phrase,
        result_line as _result_line,
        use_line as _use_line,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from live_activity_fixtures import (  # noqa: E402
        BASE_MS,
        MINUTE_MS,
        SECOND_MS,
        SENTINEL_OUTPUT,
        jsonl_bytes as _jsonl_bytes,
        line as _line,
        output_phrase as _output_phrase,
        result_line as _result_line,
        use_line as _use_line,
    )


class ReadUnfinishedSubagentActivityTest(unittest.TestCase):
    """SL-R1~R8 — docs/prps/hub-subagent-liveness-signal.md 결정 SL1·SL3·SL7·SL8.

    read_subagent_activity_at_ms(실행 1건) · read_unfinished_subagent_activity(세션 전체
    합성) 을 함께 검증한다. read_subagent_meta 와 같은 tempdir 관례 — mock.patch 없이
    임시 디렉토리로 검증한다(SL-R6 의 stat 호출 0회 확인만 예외).
    """

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_transcript_file(self, cwd: str, session_id: str, agent_id: str) -> Path:
        encoded_name = hub_project.encode_project_dir_name(cwd)
        subagents_dir = self.temp_dir / encoded_name / session_id / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = subagents_dir / f"agent-{agent_id}.jsonl"
        transcript_path.write_text('{"type":"assistant"}\n', encoding="utf-8")
        return transcript_path

    def _write_meta_file_only(self, cwd: str, session_id: str, agent_id: str) -> None:
        """SL-R2 전용 — .jsonl 없이 .meta.json 만 있는 상태를 만든다."""
        encoded_name = hub_project.encode_project_dir_name(cwd)
        subagents_dir = self.temp_dir / encoded_name / session_id / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True, exist_ok=True)
        (subagents_dir / f"agent-{agent_id}.meta.json").write_text("{}", encoding="utf-8")

    def _facts(self, session_id: str, cwd: str, subagents: tuple) -> hub_session_facts.SessionFacts:
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=0,
            last_event_at_ms=0, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=subagents,
        )

    def _subagent(
        self, agent_id: str, started_at_ms: int = 0, ended_at_ms: int | None = None,
    ) -> hub_session_facts.SubagentFact:
        return hub_session_facts.SubagentFact(
            agent_id=agent_id, agent_type="implementer",
            started_at_ms=started_at_ms, ended_at_ms=ended_at_ms,
        )

    def test_slr1_existing_transcript_returns_mtime_in_ms(self) -> None:
        transcript_path = self._write_transcript_file("/repo/a", "sess-1", "agt-1")
        mtime = 1_700_000_000
        os.utime(transcript_path, (mtime, mtime))
        activity_ms = hub_subagent_read.read_subagent_activity_at_ms(
            "sess-1", ("/repo/a",), "agt-1", self.temp_dir
        )
        self.assertEqual(activity_ms, mtime * 1000)

    def test_n1_transcript_in_host_folder_is_found_for_underscore_path(self) -> None:
        """N1 — 밑줄 든 경로의 에이전트 transcript 는 호스트가 `_` 를 `-` 로 바꾼 폴더에 있다. 폴더 이름을
        리터럴로 적는다 — _write_transcript_file 은 같은 함수로 폴더를 만들어 순환한다."""
        subagents_dir = (
            self.temp_dir / "-Users-dev-works-notebook-wiki-NotebookWiki" / "sess-1" / hub_subagent.SUBAGENT_DIR_NAME
        )
        subagents_dir.mkdir(parents=True)
        transcript_path = subagents_dir / "agent-agt-1.jsonl"
        transcript_path.write_text('{"type":"assistant"}\n', encoding="utf-8")
        mtime = 1_700_000_000
        os.utime(transcript_path, (mtime, mtime))
        activity_ms = hub_subagent_read.read_subagent_activity_at_ms(
            "sess-1", ("/Users/dev/works/notebook_wiki/NotebookWiki",), "agt-1", self.temp_dir
        )
        self.assertEqual(activity_ms, mtime * 1000)

    def test_slr2_missing_transcript_with_only_meta_file_returns_none(self) -> None:
        self._write_meta_file_only("/repo/a", "sess-1", "agt-1")
        activity_ms = hub_subagent_read.read_subagent_activity_at_ms(
            "sess-1", ("/repo/a",), "agt-1", self.temp_dir
        )
        self.assertIsNone(activity_ms)

    def test_slr3_second_observed_cwd_is_found_for_worktree(self) -> None:
        """결정 MD2·E13 과 동형 — 첫 cwd 에는 파일이 없고 두 번째(워크트리)에 있으면 찾는다."""
        self._write_transcript_file("/repo/worktree", "sess-1", "agt-1")
        activity_ms = hub_subagent_read.read_subagent_activity_at_ms(
            "sess-1", ("/repo/root", "/repo/worktree"), "agt-1", self.temp_dir
        )
        self.assertIsNotNone(activity_ms)

    def test_slr4_unsafe_path_segments_are_rejected(self) -> None:
        """경로 조각 방어(_is_safe_path_segment) — 조립 전에 거부한다."""
        self._write_transcript_file("/repo/a", "sess-1", "agt-1")
        unsafe_cases = (
            ("/tmp/x", "agt-1"), ("sess-1", "../agt-1"), ("", "agt-1"),
            (".", "agt-1"), ("..", "agt-1"), ("sess-1", ""), ("sess-1", "."), ("sess-1", ".."),
        )
        for session_id, agent_id in unsafe_cases:
            with self.subTest(session_id=session_id, agent_id=agent_id):
                activity_ms = hub_subagent_read.read_subagent_activity_at_ms(
                    session_id, ("/repo/a",), agent_id, self.temp_dir
                )
                self.assertIsNone(activity_ms)

    def test_slr5_signature_has_no_record_prompt_excerpt_gate(self) -> None:
        """함정 PS7 회귀 방지(G8) — mtime 은 프롬프트 발췌가 아니므로 그 게이트가 없어야 한다."""
        params = inspect.signature(hub_subagent_read.read_unfinished_subagent_activity).parameters
        self.assertNotIn("record_prompt_excerpt", params)

    def test_slr6_finished_runs_are_never_stat_ed(self) -> None:
        """SL3 — 종료된 실행만 있는 세션은 빈 dict 이고, 파일이 있어도 읽지 않는다."""
        self._write_transcript_file("/repo/a", "sess-1", "agt-1")
        sessions_by_path = {
            "/repo/a": (self._facts("sess-1", "/repo/a", (self._subagent("agt-1", ended_at_ms=999),)),),
        }
        with mock.patch.object(Path, "stat", autospec=True) as mock_stat:
            activity_by_agent_id = hub_subagent_read.read_unfinished_subagent_activity(
                sessions_by_path, self.temp_dir
            )
        self.assertEqual(activity_by_agent_id, {})
        mock_stat.assert_not_called()

    def test_slr7_run_count_is_capped_at_subagent_run_max_per_session(self) -> None:
        """세션당 실행 100건 초과 시 SUBAGENT_RUN_MAX_PER_SESSION 으로 잘리고, 남는 것은
        가장 최근 시작한 것부터다 — read_subagent_metas 자매 테스트
        test_most_recently_started_are_kept_under_the_cap 과 같은 형태(재검수 2회차 HIGH-1).
        이전 판은 상한만 보고(assertLessEqual) 어느 것이 남는지는 보지 않아, 정렬 방향이
        거꾸로 뒤집혀도(오래된 것부터 남아도) 통과했다."""
        over_cap = hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION + 5
        subagents = tuple(
            self._subagent(f"agt-{index}", started_at_ms=index) for index in range(over_cap)
        )
        for index in range(over_cap):
            self._write_transcript_file("/repo/a", "sess-1", f"agt-{index}")
        sessions_by_path = {"/repo/a": (self._facts("sess-1", "/repo/a", subagents),)}
        activity_by_agent_id = hub_subagent_read.read_unfinished_subagent_activity(
            sessions_by_path, self.temp_dir
        )
        self.assertEqual(len(activity_by_agent_id), hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION)
        self.assertNotIn("agt-0", activity_by_agent_id)   # 가장 오래된 것은 상한 밖으로 밀려난다
        self.assertIn(f"agt-{over_cap - 1}", activity_by_agent_id)   # 가장 최근 것은 반드시 남는다

    def test_slr8_directory_permission_denied_returns_none_without_raising(self) -> None:
        """SL8 — 경고를 돌려주지 않는 함수라(dict 하나만 반환) 이 함수 자체에는 경고가 없다."""
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root 는 디렉터리 권한 검사를 우회해 EACCES 를 재현할 수 없다")
        self._write_transcript_file("/repo/a", "sess-1", "agt-1")
        session_dir = self.temp_dir / hub_project.encode_project_dir_name("/repo/a") / "sess-1"
        session_dir.chmod(0o000)
        try:
            activity_ms = hub_subagent_read.read_subagent_activity_at_ms(
                "sess-1", ("/repo/a",), "agt-1", self.temp_dir
            )
        finally:
            session_dir.chmod(0o755)
        self.assertIsNone(activity_ms)

    def test_collects_activity_across_sessions_by_agent_id(self) -> None:
        """배선 함수의 양성 경로(재검수 2회차 HIGH-1) — read_subagent_metas 자매 테스트
        test_collects_metas_across_sessions_by_agent_id 와 같은 형태. SL-R6·SL-R7 은 이
        함수가 무슨 이유로든 항상 빈 dict 를 반환해도 통과한다({} == {}, 0 <= CAP) — 미종료
        실행이 두 세션에 걸쳐 있을 때 그 agent_id 들의 정확한 mtime 값이 실제로 들어오는지를
        여기서 직접 확인한다."""
        transcript_path_a = self._write_transcript_file("/repo/a", "sess-1", "agt-1")
        transcript_path_b = self._write_transcript_file("/repo/b", "sess-2", "agt-2")
        mtime_a, mtime_b = 1_700_000_000, 1_700_000_100
        os.utime(transcript_path_a, (mtime_a, mtime_a))
        os.utime(transcript_path_b, (mtime_b, mtime_b))
        sessions_by_path = {
            "/repo/a": (self._facts("sess-1", "/repo/a", (self._subagent("agt-1"),)),),
            "/repo/b": (self._facts("sess-2", "/repo/b", (self._subagent("agt-2"),)),),
        }
        activity_by_agent_id = hub_subagent_read.read_unfinished_subagent_activity(
            sessions_by_path, self.temp_dir
        )
        self.assertEqual(
            activity_by_agent_id, {"agt-1": mtime_a * 1000, "agt-2": mtime_b * 1000}
        )


class ReadLiveActivityTest(unittest.TestCase):
    """LA-R1~R9(docs/prps/hub-live-activity.md §10.2, 결정 LA2·LA6·LA7·LA12) — 도는 실행의 활동(안 A + 실행 줄 출력)과
    백그라운드 대기 후보 세션의 출력 요약(안 B). 임시 디렉터리에 합성 기록을 쓰고, 읽기 호출 수는 `_read_tail_bytes` 를
    감싸 센다. LA-R10(기존 재개 제목 테스트 무수정 통과)은 test_hub_subagent_read.py 의 ReadSubagentMetasResumeTitleTest 가 그대로 진다."""

    SESSION_ID = "sess-live"
    CWD = "/repo/live"
    NOW_MS = BASE_MS

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.projects_dir = self.temp_dir / "projects"
        self.host_tmp_dir = self.temp_dir / "host_tmp"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ---- 픽스처 ----
    def _pair_lines(self) -> list[dict]:
        return [_use_line(self.NOW_MS - 2 * SECOND_MS, "u1", "Read"), _result_line(self.NOW_MS - SECOND_MS, "u1")]

    def _agent_transcript_path(self, agent_id: str, session_id: str = SESSION_ID, cwd: str = CWD) -> Path:
        subagents_dir = self.projects_dir / hub_project.encode_project_dir_name(cwd) / session_id / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True, exist_ok=True)
        return subagents_dir / f"agent-{agent_id}.jsonl"

    def _write_agent_transcript(self, agent_id: str, lines: list[dict] | None = None, **path_options) -> Path:
        transcript_path = self._agent_transcript_path(agent_id, **path_options)
        transcript_path.write_bytes(_jsonl_bytes(*(self._pair_lines() if lines is None else lines)))
        return transcript_path

    def _write_main_transcript(self, lines: list[dict], session_id: str = SESSION_ID, cwd: str = CWD) -> Path:
        transcript_path = self.projects_dir / hub_project.encode_project_dir_name(cwd) / f"{session_id}.jsonl"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_bytes(_jsonl_bytes(*lines))
        return transcript_path

    def _write_output_file(self, task_id: str, size: int = 10, mtime_seconds: int | None = None) -> Path:
        output_path = self.host_tmp_dir / self.SESSION_ID / "tasks" / f"{task_id}.output"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"x" * size)
        modified_seconds = BASE_MS // SECOND_MS - 100 if mtime_seconds is None else mtime_seconds
        os.utime(output_path, (modified_seconds, modified_seconds))
        return output_path

    def _output_line(self, task_id: str) -> dict:
        phrase = _output_phrase(self.SESSION_ID, task_id, root=str(self.host_tmp_dir))
        return _result_line(self.NOW_MS - 5 * SECOND_MS, f"toolu_{task_id}", phrase)

    def _subagent(self, agent_id: str, started_ago_ms: int = MINUTE_MS, ended_ago_ms: int | None = None):
        return hub_session_facts.SubagentFact(
            agent_id=agent_id, agent_type="implementer", started_at_ms=self.NOW_MS - started_ago_ms,
            ended_at_ms=None if ended_ago_ms is None else self.NOW_MS - ended_ago_ms,
        )

    def _facts(self, subagents: tuple = (), reported_ago_ms: int | None = None, task_counts: tuple = (("shell", 1),),
               session_id: str = SESSION_ID, observed_cwds: tuple = (CWD,)):
        report = None if reported_ago_ms is None else hub_session_facts.BackgroundReport(
            self.NOW_MS - reported_ago_ms, task_counts, 0
        )
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=observed_cwds[0], observed_cwds=observed_cwds, started_at_ms=0,
            last_event_at_ms=0, last_event_name="Stop", turn_state="ended", ended_at_ms=None,
            subagents=subagents, background_report=report,
        )

    def _read(self, *facts_list, unfinished: dict | None = None) -> hub_activity.LiveActivity:
        sessions_by_path = {facts.cwd: (facts,) for facts in facts_list}
        return hub_subagent_read.read_live_activity(sessions_by_path, self.projects_dir, self.NOW_MS, unfinished or {})

    def _spy_on_reads(self):
        return mock.patch.object(hub_subagent_read, "_read_tail_bytes", wraps=hub_subagent_read._read_tail_bytes)

    # ---- LA-R1 — 어떤 실행을 읽는가 ----
    def test_la_r1_only_the_running_run_is_read(self) -> None:
        for agent_id in ("agt-run", "agt-done", "agt-zombie"):
            self._write_agent_transcript(agent_id)
        facts = self._facts((
            self._subagent("agt-run"),
            self._subagent("agt-done", started_ago_ms=10 * MINUTE_MS, ended_ago_ms=2 * MINUTE_MS),
            self._subagent("agt-zombie", started_ago_ms=91 * MINUTE_MS),
        ))

        with self._spy_on_reads() as reader:
            live_activity = self._read(facts)

        self.assertEqual(set(live_activity.by_agent_id), {"agt-run"})
        self.assertEqual([call.args[0].name for call in reader.call_args_list], ["agent-agt-run.jsonl"])

    def test_la_r1_a_run_past_the_zombie_limit_with_a_fresh_transcript_signal_is_read(self) -> None:
        self._write_agent_transcript("agt-old")
        facts = self._facts((self._subagent("agt-old", started_ago_ms=100 * MINUTE_MS),))

        live_activity = self._read(facts, unfinished={"agt-old": self.NOW_MS - SECOND_MS})

        self.assertEqual(set(live_activity.by_agent_id), {"agt-old"})

    def test_la_r1_at_most_eight_running_runs_per_session_most_recent_first(self) -> None:
        run_count = hub_activity.ACTIVITY_RUNS_MAX_PER_SESSION + 2
        for index in range(run_count):
            self._write_agent_transcript(f"agt-{index}")
        facts = self._facts(tuple(self._subagent(f"agt-{index}", started_ago_ms=(run_count - index) * SECOND_MS) for index in range(run_count)))

        live_activity = self._read(facts)

        expected = {f"agt-{index}" for index in range(2, run_count)}
        self.assertEqual(set(live_activity.by_agent_id), expected)

    def test_a_run_whose_transcript_has_no_tool_blocks_has_no_activity(self) -> None:
        self._write_agent_transcript("agt-run", [_line("assistant", self.NOW_MS, [{"type": "text", "text": "SENTINEL-TXT"}])])

        live_activity = self._read(self._facts((self._subagent("agt-run"),)))

        self.assertEqual(dict(live_activity.by_agent_id), {})

    def test_a_transcript_under_a_later_observed_cwd_is_found(self) -> None:
        self._write_agent_transcript("agt-run", cwd="/repo/worktree")
        facts = self._facts((self._subagent("agt-run"),), observed_cwds=(self.CWD, "/repo/worktree"))

        self.assertEqual(set(self._read(facts).by_agent_id), {"agt-run"})

    # ---- LA-R2 — 창 ----
    def test_la_r2_a_call_outside_the_window_is_not_pending(self) -> None:
        filler = _line("attachment", self.NOW_MS - 10 * SECOND_MS)
        filler["padding"] = "x" * 1000
        filler_count = (3 * hub_activity.ACTIVITY_WINDOW_BYTES // 2) // 1000
        lines = [_use_line(self.NOW_MS - 20 * SECOND_MS, "old", "Bash"), *([filler] * filler_count), *self._pair_lines()]
        transcript_path = self._write_agent_transcript("agt-run", lines)
        self.assertGreater(transcript_path.stat().st_size, hub_activity.ACTIVITY_WINDOW_BYTES)

        activity = self._read(self._facts((self._subagent("agt-run"),))).by_agent_id["agt-run"]

        self.assertEqual(activity.pending_count, 0)
        self.assertEqual(activity.last_tool_kind, "read")

    def test_the_window_read_is_bounded_by_the_activity_window(self) -> None:
        self._write_agent_transcript("agt-run")
        facts = self._facts((self._subagent("agt-run"),))

        with self._spy_on_reads() as reader:
            self._read(facts)

        self.assertEqual(reader.call_args_list[0].args[1], hub_activity.ACTIVITY_WINDOW_BYTES)

    # ---- LA-R3·R4 — 실행 줄 출력 ----
    def test_la_r3_an_output_path_in_the_run_window_becomes_background_output(self) -> None:
        output_path = self._write_output_file("abc", size=48, mtime_seconds=BASE_MS // SECOND_MS - 60)
        self._write_agent_transcript("agt-run", [*self._pair_lines(), self._output_line("abc")])
        facts = self._facts((self._subagent("agt-run"),))

        activity = self._read(facts).by_agent_id["agt-run"]

        expected_ms = int(output_path.stat().st_mtime * 1000)
        self.assertEqual(activity.background_output, hub_activity.BackgroundOutputView(1, expected_ms, 48))

    def test_la_r3_once_the_output_file_is_gone_the_output_is_none(self) -> None:
        output_path = self._write_output_file("abc")
        self._write_agent_transcript("agt-run", [*self._pair_lines(), self._output_line("abc")])
        facts = self._facts((self._subagent("agt-run"),))
        output_path.unlink()

        activity = self._read(facts).by_agent_id["agt-run"]

        self.assertIsNone(activity.background_output)

    def test_la_r4_symlinks_and_directories_are_dropped(self) -> None:
        real_file = self.temp_dir / "elsewhere.txt"
        real_file.write_bytes(b"data")
        link_path = self.host_tmp_dir / self.SESSION_ID / "tasks" / "linked.output"
        link_path.parent.mkdir(parents=True)
        link_path.symlink_to(real_file)
        (self.host_tmp_dir / self.SESSION_ID / "tasks" / "folder.output").mkdir()
        self._write_agent_transcript("agt-run", [*self._pair_lines(), self._output_line("linked"), self._output_line("folder")])

        activity = self._read(self._facts((self._subagent("agt-run"),))).by_agent_id["agt-run"]

        self.assertIsNone(activity.background_output)

    def test_output_files_are_inspected_with_lstat_and_never_opened(self) -> None:
        self._write_output_file("abc")
        self._write_agent_transcript("agt-run", [*self._pair_lines(), self._output_line("abc")])
        real_open = Path.open

        def guarded_open(path_self, *args, **kwargs):
            if path_self.suffix == ".output":
                raise AssertionError("출력 파일을 열었다")
            return real_open(path_self, *args, **kwargs)

        with mock.patch.object(Path, "open", guarded_open):
            activity = self._read(self._facts((self._subagent("agt-run"),))).by_agent_id["agt-run"]

        self.assertEqual(activity.background_output.file_count, 1)

    # ---- LA-R5~R7 — 배지(백그라운드 대기 후보) ----
    def test_la_r5_badge_output_adds_up_the_main_transcript_and_a_recently_stopped_run(self) -> None:
        main_path = self._write_output_file("main1", size=100, mtime_seconds=BASE_MS // SECOND_MS - 300)
        sub_path = self._write_output_file("sub1", size=200, mtime_seconds=BASE_MS // SECOND_MS - 120)
        self._write_main_transcript([self._output_line("main1")])
        self._write_agent_transcript("agt-ended", [self._output_line("sub1")])
        facts = self._facts(
            (self._subagent("agt-ended", started_ago_ms=40 * MINUTE_MS, ended_ago_ms=20 * MINUTE_MS),),
            reported_ago_ms=30 * MINUTE_MS,
        )

        live_activity = self._read(facts)

        expected = hub_activity.BackgroundOutputView(2, int(sub_path.stat().st_mtime * 1000), 300)
        self.assertEqual(live_activity.background_output_by_session_id, {self.SESSION_ID: expected})
        self.assertLess(main_path.stat().st_mtime, sub_path.stat().st_mtime)
        self.assertEqual(dict(live_activity.by_agent_id), {})

    def test_badge_file_count_never_exceeds_the_output_file_limit(self) -> None:
        limit = hub_activity.BACKGROUND_OUTPUT_MAX_FILES
        main_task_ids = [f"main{index}" for index in range(limit)]
        sub_task_ids = ["subA", "subB"]
        for task_id in main_task_ids + sub_task_ids:
            self._write_output_file(task_id, size=1)
        self._write_main_transcript([self._output_line(task_id) for task_id in main_task_ids])
        self._write_agent_transcript("agt-ended", [self._output_line(task_id) for task_id in sub_task_ids])
        facts = self._facts((self._subagent("agt-ended", ended_ago_ms=MINUTE_MS),), reported_ago_ms=MINUTE_MS)

        view = self._read(facts).background_output_by_session_id[self.SESSION_ID]

        self.assertEqual((view.file_count, view.total_bytes), (limit, limit))

    def test_badge_output_is_absent_when_no_listed_file_exists(self) -> None:
        self._write_main_transcript([self._output_line("main1")])
        facts = self._facts((), reported_ago_ms=30 * MINUTE_MS)

        self.assertEqual(dict(self._read(facts).background_output_by_session_id), {})

    def test_la_r6_the_main_transcript_is_not_opened_unless_the_session_is_a_scan_target(self) -> None:
        self._write_output_file("main1")
        self._write_main_transcript([self._output_line("main1")])
        not_targets = {
            "report older than the wait limit": self._facts((), reported_ago_ms=91 * MINUTE_MS),
            "only non-waking kinds": self._facts((), reported_ago_ms=MINUTE_MS, task_counts=(("subagent", 1),)),
            "no report": self._facts(()),
        }
        for label, facts in not_targets.items():
            with self.subTest(label), self._spy_on_reads() as reader:
                live_activity = self._read(facts)

                reader.assert_not_called()
                self.assertEqual(dict(live_activity.background_output_by_session_id), {})

    def test_la_r7_only_the_eight_most_recently_stopped_runs_are_read(self) -> None:
        stopped = tuple(self._subagent(f"agt-{index}", started_ago_ms=100 * MINUTE_MS, ended_ago_ms=(index + 1) * MINUTE_MS) for index in range(10))
        for index in range(10):
            self._write_agent_transcript(f"agt-{index}", [self._output_line("none")])
        self._write_main_transcript([self._output_line("none")])
        facts = self._facts(stopped, reported_ago_ms=0)

        with self._spy_on_reads() as reader:
            self._read(facts)

        read_names = sorted(call.args[0].name for call in reader.call_args_list)
        expected = sorted([f"agent-agt-{index}.jsonl" for index in range(hub_activity.BACKGROUND_SCAN_SUBAGENTS_MAX)] + [f"{self.SESSION_ID}.jsonl"])
        self.assertEqual(read_names, expected)

    def test_a_run_stopped_before_the_report_horizon_is_not_read(self) -> None:
        horizon_ms = hub_session.BACKGROUND_WAIT_MAX_MS
        long_gone = self._subagent("agt-gone", started_ago_ms=horizon_ms + 3 * MINUTE_MS, ended_ago_ms=horizon_ms + 2 * MINUTE_MS)
        self._write_agent_transcript("agt-gone", [self._output_line("none")])
        self._write_main_transcript([self._output_line("none")])
        facts = self._facts((long_gone,), reported_ago_ms=MINUTE_MS)

        with self._spy_on_reads() as reader:
            self._read(facts)

        self.assertEqual([call.args[0].name for call in reader.call_args_list], [f"{self.SESSION_ID}.jsonl"])

    def test_badge_and_run_outputs_are_counted_once_when_the_same_path_appears_in_both(self) -> None:
        self._write_output_file("shared", size=7)
        self._write_main_transcript([self._output_line("shared")])
        self._write_agent_transcript("agt-ended", [self._output_line("shared")])
        facts = self._facts((self._subagent("agt-ended", ended_ago_ms=MINUTE_MS),), reported_ago_ms=MINUTE_MS)

        view = self._read(facts).background_output_by_session_id[self.SESSION_ID]

        self.assertEqual((view.file_count, view.total_bytes), (1, 7))

    # ---- LA-R8·R9 — 실패와 안전 ----
    def test_la_r8_missing_and_unreadable_transcripts_never_raise_and_leave_no_key(self) -> None:
        self._write_agent_transcript("agt-unreadable")
        facts = self._facts((self._subagent("agt-missing"), self._subagent("agt-unreadable")))
        unreadable_path = self._agent_transcript_path("agt-unreadable")
        can_deny = not (hasattr(os, "geteuid") and os.geteuid() == 0)
        if can_deny:
            unreadable_path.chmod(0o000)
        try:
            live_activity = self._read(facts)
        finally:
            unreadable_path.chmod(0o644)

        self.assertNotIn("agt-missing", live_activity.by_agent_id)
        if can_deny:
            self.assertNotIn("agt-unreadable", live_activity.by_agent_id)

    def test_la_r8_an_output_path_that_does_not_exist_is_simply_dropped(self) -> None:
        self._write_agent_transcript("agt-run", [*self._pair_lines(), self._output_line("never-created")])

        activity = self._read(self._facts((self._subagent("agt-run"),))).by_agent_id["agt-run"]

        self.assertIsNone(activity.background_output)

    def _lone_surrogate_output_line(self, task_id: str) -> dict:
        """JSON 이스케이프된 외톨이 서로게이트(`\\ud800`)를 경로에 품은 결과 줄 — 호스트 기록은 우리가 소유하지 않는 입력이다."""
        phrase = _output_phrase(self.SESSION_ID, task_id, root=str(self.host_tmp_dir) + "\ud800x")
        return _result_line(self.NOW_MS - 5 * SECOND_MS, f"toolu_{task_id}", phrase)

    def test_la_r8_a_lone_surrogate_in_an_output_path_drops_only_that_path_and_never_raises(self) -> None:
        """검수 1회차 HIGH — 서로게이트가 든 경로는 형태 검증을 통과하지만 파일 상태를 볼 때 UnicodeEncodeError(ValueError 계열)가
        난다. 그 예외가 수집 전체를 죽이면 안 된다 — 그 경로만 버리고 같은 창의 정상 경로는 그대로 센다."""
        self._write_output_file("good", size=5)
        lines = [*self._pair_lines(), self._lone_surrogate_output_line("bad"), self._output_line("good")]
        self._write_agent_transcript("agt-run", lines)

        activity = self._read(self._facts((self._subagent("agt-run"),))).by_agent_id["agt-run"]

        self.assertEqual(activity.background_output.file_count, 1)
        self.assertEqual(activity.background_output.total_bytes, 5)

    def test_la_r8_a_lone_surrogate_output_path_in_the_badge_window_never_raises(self) -> None:
        self._write_main_transcript([self._lone_surrogate_output_line("bad")])
        facts = self._facts((), reported_ago_ms=MINUTE_MS)

        live_activity = self._read(facts)

        self.assertEqual(dict(live_activity.background_output_by_session_id), {})

    def test_la_r8_stat_output_files_skips_a_path_that_cannot_be_encoded(self) -> None:
        good_path = self._write_output_file("good", size=3)

        file_stats = hub_subagent_read._stat_output_files(
            [f"/x\ud800y/{self.SESSION_ID}/tasks/a1.output", str(good_path)]
        )

        self.assertEqual([size for _, size in file_stats], [3])

    def test_la_r9_unsafe_ids_are_skipped_before_any_path_is_assembled(self) -> None:
        unsafe_runs = self._facts((self._subagent("../escape"), self._subagent("a/b"), self._subagent(".."), self._subagent("")))
        unsafe_session = self._facts((self._subagent("agt-run"),), reported_ago_ms=MINUTE_MS, session_id="../evil")
        for label, facts in {"agent ids": unsafe_runs, "session id": unsafe_session}.items():
            with self.subTest(label), self._spy_on_reads() as reader:
                live_activity = self._read(facts)

                reader.assert_not_called()
                self.assertEqual(dict(live_activity.by_agent_id), {})
                self.assertEqual(dict(live_activity.background_output_by_session_id), {})

    def test_signature_has_no_record_prompt_excerpt_gate(self) -> None:
        """함정 SL7(결정 LA13) — 활동은 프롬프트 발췌가 아니다. 그 스위치를 끈 사용자에게도 같은 규칙이 돈다."""
        parameter_names = tuple(inspect.signature(hub_subagent_read.read_live_activity).parameters)

        self.assertEqual(parameter_names, ("sessions_by_path", "projects_dir", "now_ms", "unfinished_activity_by_agent_id"))

    def test_nothing_running_and_no_report_gives_an_empty_result_without_reading(self) -> None:
        facts = self._facts((self._subagent("agt-done", ended_ago_ms=MINUTE_MS),))

        with self._spy_on_reads() as reader:
            live_activity = self._read(facts)

        reader.assert_not_called()
        self.assertEqual((dict(live_activity.by_agent_id), dict(live_activity.background_output_by_session_id)), ({}, {}))

    def test_output_bodies_never_reach_the_result(self) -> None:
        self._write_output_file("abc")
        self._write_agent_transcript("agt-run", [*self._pair_lines(), self._output_line("abc")])

        live_activity = self._read(self._facts((self._subagent("agt-run"),)))

        self.assertNotIn(SENTINEL_OUTPUT, repr(live_activity))
        self.assertNotIn(".output", repr(live_activity))


if __name__ == "__main__":
    unittest.main()
