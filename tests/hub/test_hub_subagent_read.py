"""hub_subagent_read 단위 테스트 — read_subagent_meta·read_subagent_metas(I/O 접합).

docs/prps/hub-agent-runs-and-prompt-source.md 결정 AR2·AR3, §10.1 test_hub_subagent_read.py
표: 경로 조립 · observed_cwds 다중 후보 · session_id/agent_id 방어 · 파일 없음 · 권한 오류
(경고 반환) · 크기 상한 초과 · record_prompt_excerpt:false → 빈 결과 + 파일 접근 0회.
mock.patch 없이 임시 디렉토리로 검증한다(정본 스타일: test_hub_workflow_read.py).

docs/prps/hub-agent-title-and-excerpt-freshness.md §9.2 R1~R7(결정 TF9·TF10·TF13) — 재개된 실행이 있는 세션만 부모 transcript
끝 RESUME_TITLE_SCAN_MAX_BYTES 를 한 번 읽어 meta 에 resume_title 을 얹는 보강(ReadSubagentMetasResumeTitleTest).
"""

import dataclasses
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_project  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_subagent  # noqa: E402
import hub_subagent_read  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다(test_hub_template_dom.py 의 관례).
try:
    from .resume_transcript_fixtures import (
        AGENT_ID,
        OTHER_AGENT_ID,
        resume_pair_lines as _resume_pair_lines,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from resume_transcript_fixtures import (  # noqa: E402
        AGENT_ID,
        OTHER_AGENT_ID,
        resume_pair_lines as _resume_pair_lines,
    )


class ReadSubagentMetaTest(unittest.TestCase):
    """read_subagent_meta — 실행 1건의 meta.json 을 조립된 경로에서 읽는다(결정 AR3)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_meta_file(self, cwd: str, session_id: str, agent_id: str, content: str) -> Path:
        encoded_name = hub_project.encode_project_dir_name(cwd)
        subagents_dir = self.temp_dir / encoded_name / session_id / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True, exist_ok=True)
        meta_path = subagents_dir / f"agent-{agent_id}.meta.json"
        meta_path.write_text(content, encoding="utf-8")
        return meta_path

    def _read(self, session_id: str, observed_cwds: tuple, agent_id: str):
        return hub_subagent_read.read_subagent_meta(session_id, observed_cwds, agent_id, self.temp_dir)

    def test_missing_file_returns_none_without_warning(self) -> None:
        meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        self.assertIsNone(meta)
        self.assertIsNone(warning)

    def test_meta_in_host_folder_is_found_for_underscore_path(self) -> None:
        """N1(docs/prps/hub-agent-title-and-excerpt-freshness.md §16) — 밑줄 든 경로의 meta.json 은 호스트가
        `_` 를 `-` 로 바꾼 폴더에 있다. 폴더 이름을 리터럴로 적는다 — _write_meta_file 은 같은 함수로
        폴더를 만들어 순환한다."""
        subagents_dir = (
            self.temp_dir / "-Users-dev-works-notebook-wiki-NotebookWiki" / "sess-1" / hub_subagent.SUBAGENT_DIR_NAME
        )
        subagents_dir.mkdir(parents=True)
        (subagents_dir / "agent-agt-1.meta.json").write_text(
            json.dumps({"agentType": "Explore"}), encoding="utf-8"
        )
        meta, warning = self._read("sess-1", ("/Users/dev/works/notebook_wiki/NotebookWiki",), "agt-1")
        self.assertIsNone(warning)
        self.assertEqual(meta.agent_type, "Explore")

    def test_existing_file_is_parsed(self) -> None:
        self._write_meta_file(
            "/repo/a", "sess-1", "agt-1",
            json.dumps({"agentType": "Explore", "description": "설명", "model": "haiku"}),
        )
        meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        self.assertIsNone(warning)
        self.assertEqual(meta.agent_type, "Explore")
        self.assertEqual(meta.title, "설명")
        self.assertEqual(meta.model, "haiku")

    def test_started_at_ms_comes_from_file_mtime(self) -> None:
        """§1.3 — meta.json 의 mtime 을 시작 시각으로 신뢰한다."""
        meta_path = self._write_meta_file(
            "/repo/a", "sess-1", "agt-1", json.dumps({"agentType": "Explore"})
        )
        mtime = 1_700_000_000
        os.utime(meta_path, (mtime, mtime))
        meta, _ = self._read("sess-1", ("/repo/a",), "agt-1")
        self.assertEqual(meta.started_at_ms, mtime * 1000)

    def test_second_observed_cwd_is_found_for_worktree(self) -> None:
        """결정 MD2·E13 과 동형 — 첫 cwd 에는 파일이 없고 두 번째(워크트리)에 있으면 찾는다."""
        self._write_meta_file(
            "/repo/worktree", "sess-1", "agt-1", json.dumps({"agentType": "Explore"})
        )
        meta, _ = self._read("sess-1", ("/repo/root", "/repo/worktree"), "agt-1")
        self.assertIsNotNone(meta)

    def test_first_existing_candidate_wins_deterministically(self) -> None:
        """먼저 존재하는 cwd 를 쓴다(결정적, MD2·E14 와 동형) — 둘 다 있어도 목록의 앞이 이긴다."""
        self._write_meta_file(
            "/repo/first", "sess-1", "agt-1", json.dumps({"agentType": "first-wins"})
        )
        self._write_meta_file(
            "/repo/second", "sess-1", "agt-1", json.dumps({"agentType": "second-loses"})
        )
        meta, _ = self._read("sess-1", ("/repo/first", "/repo/second"), "agt-1")
        self.assertEqual(meta.agent_type, "first-wins")

    def test_broken_json_returns_none_without_warning(self) -> None:
        """파싱 실패는 경고 없이 조용히 None — 호스트 파일 형식이 불안정할 수 있다는 계약의 일부다."""
        self._write_meta_file("/repo/a", "sess-1", "agt-1", "{")
        meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        self.assertIsNone(meta)
        self.assertIsNone(warning)

    def test_oversized_file_is_not_read(self) -> None:
        oversized = json.dumps({"agentType": "x"}) + (" " * hub_subagent.SUBAGENT_META_MAX_BYTES)
        self._write_meta_file("/repo/a", "sess-1", "agt-1", oversized)
        meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        self.assertIsNone(meta)
        self.assertIsNotNone(warning)
        self.assertIn("상한", warning)

    def test_permission_denied_returns_none_with_warning(self) -> None:
        meta_path = self._write_meta_file(
            "/repo/a", "sess-1", "agt-1", json.dumps({"agentType": "x"})
        )
        meta_path.chmod(0o000)
        try:
            meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        finally:
            meta_path.chmod(0o644)
        self.assertIsNone(meta)
        self.assertIsNotNone(warning)

    def test_session_directory_permission_denied_returns_none_without_raising(self) -> None:
        """M3(재검수 1회차) — hub_workflow_read.py 의
        test_workflows_directory_permission_denied_returns_none_without_raising 과 같은 모양.
        pathlib 의 is_file() 은 ENOENT/ENOTDIR/EBADF/ELOOP 만 삼키고 EACCES 는 재발생시킨다
        (실측: meta.json 자체를 chmod(0o000) 해도 stat 은 대상이 아니라 **부모 디렉터리의
        실행 권한**만 요구해 is_file() 이 여전히 True 다 — EACCES 를 재현하려면 session_id
        디렉터리를 잠가야 한다). read_subagent_meta 의 `except OSError: continue` 가 이를
        삼켜 (None, None) 을 돌려주는지 본다(경고 없음 — _read_meta_text 까지 못 가서 그
        분기의 경고를 만들 기회가 없다). root 는 권한 검사를 우회해 재현이 불가능하므로 skip."""
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root 는 디렉터리 권한 검사를 우회해 EACCES 를 재현할 수 없다")
        self._write_meta_file("/repo/a", "sess-1", "agt-1", json.dumps({"agentType": "x"}))
        session_dir = self.temp_dir / hub_project.encode_project_dir_name("/repo/a") / "sess-1"
        session_dir.chmod(0o000)
        try:
            meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        finally:
            session_dir.chmod(0o755)
        self.assertIsNone(meta)
        self.assertIsNone(warning)

    def test_torn_multibyte_content_does_not_raise(self) -> None:
        """GOTCHA 7 — errors="replace" 가 없으면 UnicodeDecodeError(ValueError 서브클래스)가
        except OSError 를 뚫는다."""
        encoded_name = hub_project.encode_project_dir_name("/repo/a")
        subagents_dir = self.temp_dir / encoded_name / "sess-1" / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True)
        torn_bytes = json.dumps({"agentType": "x"}).encode("utf-8") + "가".encode("utf-8")[:2]
        (subagents_dir / "agent-agt-1.meta.json").write_bytes(torn_bytes)
        meta, warning = self._read("sess-1", ("/repo/a",), "agt-1")
        self.assertIsNone(meta)
        self.assertIsNone(warning)

    def test_session_id_with_path_separator_is_rejected(self) -> None:
        """경로 조각 방어(hub_workflow_read._existing_workflow_directories 와 같은 가드) —
        session_id 가 `/` 를 포함하면 Path 의 `/` 연산자가 앞부분을 버릴 수 있다."""
        meta, warning = self._read("/tmp/x", ("/repo/a",), "agt-1")
        self.assertIsNone(meta)
        self.assertIsNone(warning)

    def test_session_id_dot_segments_are_rejected(self) -> None:
        for session_id in ("", ".", ".."):
            with self.subTest(session_id=session_id):
                meta, warning = self._read(session_id, ("/repo/a",), "agt-1")
                self.assertIsNone(meta)
                self.assertIsNone(warning)

    def test_agent_id_with_path_separator_is_rejected(self) -> None:
        self._write_meta_file("/repo/a", "sess-1", "agt-1", json.dumps({"agentType": "x"}))
        meta, warning = self._read("sess-1", ("/repo/a",), "../agt-1")
        self.assertIsNone(meta)
        self.assertIsNone(warning)

    def test_agent_id_dot_segments_are_rejected(self) -> None:
        for agent_id in ("", ".", ".."):
            with self.subTest(agent_id=agent_id):
                meta, warning = self._read("sess-1", ("/repo/a",), agent_id)
                self.assertIsNone(meta)
                self.assertIsNone(warning)


class ReadSubagentMetasTest(unittest.TestCase):
    """read_subagent_metas — 수집 대상 세션 전부의 추적된 실행 meta 를 모은다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_meta_file(self, cwd: str, session_id: str, agent_id: str, agent_type: str = "Explore") -> None:
        encoded_name = hub_project.encode_project_dir_name(cwd)
        subagents_dir = self.temp_dir / encoded_name / session_id / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True, exist_ok=True)
        (subagents_dir / f"agent-{agent_id}.meta.json").write_text(
            json.dumps({"agentType": agent_type}), encoding="utf-8"
        )

    def _facts(self, session_id: str, cwd: str, subagents: tuple) -> hub_session_facts.SessionFacts:
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=0,
            last_event_at_ms=0, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=subagents,
        )

    def _subagent(self, agent_id: str, started_at_ms: int = 0) -> hub_session_facts.SubagentFact:
        return hub_session_facts.SubagentFact(
            agent_id=agent_id, agent_type="Explore", started_at_ms=started_at_ms, ended_at_ms=None,
        )

    def test_collects_metas_across_sessions_by_agent_id(self) -> None:
        self._write_meta_file("/repo/a", "sess-1", "agt-1")
        self._write_meta_file("/repo/b", "sess-2", "agt-2")
        sessions_by_path = {
            "/repo/a": (self._facts("sess-1", "/repo/a", (self._subagent("agt-1"),)),),
            "/repo/b": (self._facts("sess-2", "/repo/b", (self._subagent("agt-2"),)),),
        }
        metas, warnings = hub_subagent_read.read_subagent_metas(sessions_by_path, True, self.temp_dir)
        self.assertEqual(set(metas), {"agt-1", "agt-2"})
        self.assertEqual(warnings, ())

    def test_execution_without_meta_file_is_simply_absent(self) -> None:
        sessions_by_path = {
            "/repo/a": (self._facts("sess-1", "/repo/a", (self._subagent("agt-1"),)),),
        }
        metas, warnings = hub_subagent_read.read_subagent_metas(sessions_by_path, True, self.temp_dir)
        self.assertEqual(metas, {})
        self.assertEqual(warnings, ())

    def test_record_prompt_excerpt_false_returns_empty_without_reading_files(self) -> None:
        """결정 PS7 — false 면 meta.json 자체를 읽지 않는다(read_session_workflows 와 같은 형태)."""
        self._write_meta_file("/repo/a", "sess-1", "agt-1")
        sessions_by_path = {
            "/repo/a": (self._facts("sess-1", "/repo/a", (self._subagent("agt-1"),)),),
        }
        with mock.patch.object(hub_subagent_read, "read_subagent_meta") as mock_read:
            metas, warnings = hub_subagent_read.read_subagent_metas(sessions_by_path, False, self.temp_dir)
        self.assertEqual(metas, {})
        self.assertEqual(warnings, ())
        mock_read.assert_not_called()

    def test_run_count_is_capped_at_subagent_run_max_per_session(self) -> None:
        """AR11 서버측 방어선 — 세션당 읽기 예산이 SUBAGENT_RUN_MAX_PER_SESSION 으로 선형 고정."""
        over_cap = hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION + 5
        subagents = tuple(
            self._subagent(f"agt-{index}", started_at_ms=index) for index in range(over_cap)
        )
        for index in range(over_cap):
            self._write_meta_file("/repo/a", "sess-1", f"agt-{index}")
        sessions_by_path = {"/repo/a": (self._facts("sess-1", "/repo/a", subagents),)}
        metas, _ = hub_subagent_read.read_subagent_metas(sessions_by_path, True, self.temp_dir)
        self.assertLessEqual(len(metas), hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION)

    def test_most_recently_started_are_kept_under_the_cap(self) -> None:
        """상한을 넘으면 가장 최근 시작한 것부터 읽는다 — 화면 정렬(K2)이 최근 우선이라
        오래된 것을 읽어 봐야 대부분 화면 상한 밖으로 밀려난다."""
        over_cap = hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION + 1
        subagents = tuple(
            self._subagent(f"agt-{index}", started_at_ms=index) for index in range(over_cap)
        )
        for index in range(over_cap):
            self._write_meta_file("/repo/a", "sess-1", f"agt-{index}")
        sessions_by_path = {"/repo/a": (self._facts("sess-1", "/repo/a", subagents),)}
        metas, _ = hub_subagent_read.read_subagent_metas(sessions_by_path, True, self.temp_dir)
        self.assertNotIn("agt-0", metas)   # 가장 오래된 것(0)은 상한 밖으로 밀려난다
        self.assertIn(f"agt-{over_cap - 1}", metas)   # 가장 최근 것은 반드시 남는다


class ReadSubagentMetasResumeTitleTest(unittest.TestCase):
    """R1~R7(결정 TF9·TF10·TF13) — 재개된 실행(resume_count ≥ 1)이 meta 를 읽힌 세션만 부모 transcript 끝 창을 한 번 읽어
    meta.resume_title 을 얹는다. 창 읽기는 record_prompt_excerpt 게이트 뒤에 있다(TF10)."""

    SESSION_ID = "sess-1"
    CWD = "/repo/a"

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_meta_file(self, cwd: str, agent_id: str, description: str = "첫 작업 이름", session_id: str = SESSION_ID) -> None:
        subagents_dir = self.temp_dir / hub_project.encode_project_dir_name(cwd) / session_id / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True, exist_ok=True)
        (subagents_dir / f"agent-{agent_id}.meta.json").write_text(
            json.dumps({"agentType": "code-reviewer", "description": description, "model": "sonnet"}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _transcript_path(self, cwd: str, session_id: str = SESSION_ID) -> Path:
        return self.temp_dir / hub_project.encode_project_dir_name(cwd) / f"{session_id}.jsonl"

    def _write_parent_transcript(self, cwd: str, lines: list[str], session_id: str = SESSION_ID) -> Path:
        transcript_path = self._transcript_path(cwd, session_id)
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return transcript_path

    def _facts(self, subagents: tuple, session_id: str = SESSION_ID, observed_cwds: tuple = (CWD,)):
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=observed_cwds[0], observed_cwds=observed_cwds, started_at_ms=0,
            last_event_at_ms=0, last_event_name="Stop", turn_state="ended", ended_at_ms=None, subagents=subagents,
        )

    def _subagent(self, agent_id: str, resume_count: int = 0) -> hub_session_facts.SubagentFact:
        return hub_session_facts.SubagentFact(
            agent_id=agent_id, agent_type="code-reviewer", started_at_ms=0, ended_at_ms=None, resume_count=resume_count,
        )

    def _read(self, *facts_list, record_prompt_excerpt: bool = True):
        sessions_by_path = {facts.cwd: (facts,) for facts in facts_list}
        return hub_subagent_read.read_subagent_metas(sessions_by_path, record_prompt_excerpt, self.temp_dir)

    # ---- R1·R2 — 언제 창을 읽는가 ----

    def test_r1_session_without_a_resumed_run_never_opens_the_parent_transcript(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID)
        self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))

        with mock.patch.object(hub_subagent_read, "_read_parent_transcript_window") as window_reader:
            metas, _ = self._read(self._facts((self._subagent(AGENT_ID, resume_count=0),)))

        window_reader.assert_not_called()
        self.assertIsNone(metas[AGENT_ID].resume_title)

    def test_a_resumed_run_without_a_readable_meta_does_not_trigger_the_scan(self) -> None:
        """meta 를 읽은 실행이 없으면(재개 요약을 얹을 대상이 없다) 파일을 열지 않는다."""
        self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))

        with mock.patch.object(hub_subagent_read, "_read_parent_transcript_window") as window_reader:
            metas, _ = self._read(self._facts((self._subagent(AGENT_ID, resume_count=1),)))

        window_reader.assert_not_called()
        self.assertEqual(metas, {})

    def test_r2_record_prompt_excerpt_false_reads_nothing_even_for_a_resumed_run(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID)
        self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))

        with mock.patch.object(hub_subagent_read, "_read_parent_transcript_window") as window_reader, \
                mock.patch.object(hub_subagent_read, "read_subagent_meta") as meta_reader:
            metas, warnings = self._read(
                self._facts((self._subagent(AGENT_ID, resume_count=2),)), record_prompt_excerpt=False,
            )

        self.assertEqual((metas, warnings), ({}, ()))
        window_reader.assert_not_called()
        meta_reader.assert_not_called()

    def test_one_window_read_serves_every_resumed_run_of_the_session(self) -> None:
        for agent_id in (AGENT_ID, OTHER_AGENT_ID):
            self._write_meta_file(self.CWD, agent_id)
        self._write_parent_transcript(
            self.CWD, _resume_pair_lines("toolu_1", "A 의 작업", AGENT_ID) + _resume_pair_lines("toolu_2", "B 의 작업", OTHER_AGENT_ID),
        )
        facts = self._facts((self._subagent(AGENT_ID, 1), self._subagent(OTHER_AGENT_ID, 3)))

        with mock.patch.object(
            hub_subagent_read, "_read_parent_transcript_window", wraps=hub_subagent_read._read_parent_transcript_window,
        ) as window_reader:
            metas, _ = self._read(facts)

        self.assertEqual(window_reader.call_count, 1)
        self.assertEqual((metas[AGENT_ID].resume_title, metas[OTHER_AGENT_ID].resume_title), ("A 의 작업", "B 의 작업"))

    def test_each_resumed_session_reads_its_own_parent_transcript(self) -> None:
        for cwd, session_id, agent_id, summary in (
            ("/repo/a", "sess-1", AGENT_ID, "첫 세션의 작업"), ("/repo/b", "sess-2", OTHER_AGENT_ID, "둘째 세션의 작업"),
        ):
            self._write_meta_file(cwd, agent_id, session_id=session_id)
            self._write_parent_transcript(cwd, _resume_pair_lines("toolu_1", summary, agent_id), session_id=session_id)
        first = self._facts((self._subagent(AGENT_ID, 1),), session_id="sess-1", observed_cwds=("/repo/a",))
        second = self._facts((self._subagent(OTHER_AGENT_ID, 1),), session_id="sess-2", observed_cwds=("/repo/b",))

        metas, _ = self._read(first, second)

        self.assertEqual((metas[AGENT_ID].resume_title, metas[OTHER_AGENT_ID].resume_title), ("첫 세션의 작업", "둘째 세션의 작업"))

    def test_only_resumed_runs_whose_meta_was_read_are_asked_for(self) -> None:
        """wanted = resume_count ≥ 1 ∧ meta 를 읽은 실행. 재개 안 된 실행·meta 없는 실행은 찾지 않는다."""
        for agent_id in (AGENT_ID, OTHER_AGENT_ID):
            self._write_meta_file(self.CWD, agent_id)
        self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))
        facts = self._facts((
            self._subagent(AGENT_ID, 1), self._subagent(OTHER_AGENT_ID, 0), self._subagent("agent-without-meta", 4),
        ))

        with mock.patch.object(hub_subagent, "parse_resume_titles", wraps=hub_subagent.parse_resume_titles) as parser:
            self._read(facts)

        self.assertEqual(parser.call_args.args[1], frozenset({AGENT_ID}))

    # ---- R3 — 얹는 값 ----

    def test_r3_resumed_run_gets_the_last_resume_summary_and_no_other_field_changes(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID, description="첫 작업 이름")
        self._write_meta_file(self.CWD, OTHER_AGENT_ID, description="재개 안 된 작업")
        self._write_parent_transcript(
            self.CWD, _resume_pair_lines("toolu_1", "옛 재개의 작업") + _resume_pair_lines("toolu_2", "마지막 재개의 작업"),
        )
        facts = self._facts((self._subagent(AGENT_ID, resume_count=2), self._subagent(OTHER_AGENT_ID)))

        metas, warnings = self._read(facts)
        plain_meta, _ = hub_subagent_read.read_subagent_meta(self.SESSION_ID, (self.CWD,), AGENT_ID, self.temp_dir)

        self.assertEqual(warnings, ())
        self.assertEqual(metas[AGENT_ID].resume_title, "마지막 재개의 작업")
        self.assertEqual(dataclasses.replace(metas[AGENT_ID], resume_title=None), plain_meta)   # 나머지 필드는 meta.json 그대로
        self.assertEqual(metas[AGENT_ID].title, "첫 작업 이름")                                    # title 의 뜻은 그대로(AR9)
        self.assertIsNone(metas[OTHER_AGENT_ID].resume_title)
        self.assertEqual(metas[OTHER_AGENT_ID].title, "재개 안 된 작업")

    def test_n1_meta_and_parent_transcript_in_host_folder_are_found_for_underscore_path(self) -> None:
        """N1 — 밑줄 든 경로의 meta 와 부모 transcript 는 호스트가 `_` 를 `-` 로 바꾼 폴더에 있다. 폴더 이름을
        리터럴로 적는다 — _write_meta_file·_write_parent_transcript 는 같은 함수로 폴더를 만들어 순환한다."""
        cwd = "/Users/dev/works/notebook_wiki/NotebookWiki"
        host_folder = self.temp_dir / "-Users-dev-works-notebook-wiki-NotebookWiki"
        subagents_dir = host_folder / self.SESSION_ID / hub_subagent.SUBAGENT_DIR_NAME
        subagents_dir.mkdir(parents=True)
        (subagents_dir / f"agent-{AGENT_ID}.meta.json").write_text(
            json.dumps({"agentType": "code-reviewer", "description": "첫 작업 이름"}, ensure_ascii=False),
            encoding="utf-8",
        )
        (host_folder / f"{self.SESSION_ID}.jsonl").write_text(
            "\n".join(_resume_pair_lines("toolu_1", "재개한 작업")) + "\n", encoding="utf-8"
        )
        facts = self._facts((self._subagent(AGENT_ID, resume_count=1),), observed_cwds=(cwd,))

        metas, warnings = self._read(facts)

        self.assertEqual(warnings, ())
        self.assertEqual(metas[AGENT_ID].title, "첫 작업 이름")
        self.assertEqual(metas[AGENT_ID].resume_title, "재개한 작업")

    def test_a_resumed_run_with_no_request_in_the_window_keeps_its_plain_meta(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID)
        self._write_parent_transcript(self.CWD, ['{"type":"assistant"}'])
        plain_meta, _ = hub_subagent_read.read_subagent_meta(self.SESSION_ID, (self.CWD,), AGENT_ID, self.temp_dir)

        metas, _ = self._read(self._facts((self._subagent(AGENT_ID, 1),)))

        self.assertEqual(metas[AGENT_ID], plain_meta)

    def test_missing_parent_transcript_keeps_the_plain_meta_without_a_warning(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID)

        metas, warnings = self._read(self._facts((self._subagent(AGENT_ID, 1),)))

        self.assertIsNone(metas[AGENT_ID].resume_title)
        self.assertEqual(warnings, ())

    def test_with_resume_titles_does_not_mutate_the_metas_it_is_given(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID)
        self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))
        facts = self._facts((self._subagent(AGENT_ID, 1),))
        meta, _ = hub_subagent_read.read_subagent_meta(self.SESSION_ID, (self.CWD,), AGENT_ID, self.temp_dir)
        given_metas = {AGENT_ID: meta}

        enriched = hub_subagent_read._with_resume_titles(facts, given_metas, self.temp_dir)

        self.assertIsNone(given_metas[AGENT_ID].resume_title)
        self.assertEqual(enriched[AGENT_ID].resume_title, "합성 작업 이름")

    # ---- R4 — 읽는 범위 ----

    def test_r4_window_is_the_tail_of_the_file_bounded_by_the_scan_budget(self) -> None:
        self._write_meta_file(self.CWD, AGENT_ID)
        filler_lines = [json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "합성 채움" * 40}]}})] * 30
        transcript_path = self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "창 밖의 작업") + filler_lines)
        budget = 2048
        self.assertGreater(transcript_path.stat().st_size, budget * 4)   # 전제 — 쌍은 창보다 훨씬 앞이다
        facts = self._facts((self._subagent(AGENT_ID, 1),))

        with mock.patch.object(hub_subagent_read, "RESUME_TITLE_SCAN_MAX_BYTES", budget):
            metas, _ = self._read(facts)
            window = hub_subagent_read._read_parent_transcript_window(self.SESSION_ID, (self.CWD,), self.temp_dir)

        self.assertIsNone(metas[AGENT_ID].resume_title)   # 파일 전체를 읽었다면 찾았을 것이다 — 창 밖이라 못 찾는다
        self.assertEqual(window, transcript_path.read_bytes()[-budget:])   # 끝 budget 바이트뿐
        with mock.patch.object(hub_subagent_read, "RESUME_TITLE_SCAN_MAX_BYTES", budget * 1000):   # 대조 — 창을 넓히면 찾는다
            wide_metas, _ = self._read(facts)
        self.assertEqual(wide_metas[AGENT_ID].resume_title, "창 밖의 작업")

    def test_scan_budget_is_eight_mebibytes(self) -> None:
        """승인된 값(Q2) — 바꾸면 README 고지(T25-261)와 같이 바꿔야 한다."""
        self.assertEqual(hub_subagent_read.RESUME_TITLE_SCAN_MAX_BYTES, 8 * 1024 * 1024)

    def test_a_file_smaller_than_the_budget_is_read_whole(self) -> None:
        transcript_path = self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))

        window = hub_subagent_read._read_parent_transcript_window(self.SESSION_ID, (self.CWD,), self.temp_dir)

        self.assertEqual(window, transcript_path.read_bytes())
        self.assertIsInstance(window, bytes)   # 디코딩하지 않는다 — 파서가 표지를 품은 줄만 디코딩한다

    def test_window_starting_inside_a_multibyte_character_does_not_raise(self) -> None:
        """GOTCHA 7 — seek 가 멀티바이트 글자 한가운데 떨어져도 예외가 나지 않고, 찢긴 첫 줄은 탈락한다. 찢긴 줄이 (다른 에이전트의 옛 재개
        결과라) 재개 표지를 품고 그 에이전트가 아직 안 풀려서 파서가 그 줄까지 내려가 디코딩하는 경로를 일부러 탄다."""
        for agent_id in (AGENT_ID, OTHER_AGENT_ID):
            self._write_meta_file(self.CWD, agent_id)
        torn_line = '{"t":"' + "가" * 20 + '","toolUseResult":{"resumedAgentId":"' + OTHER_AGENT_ID + '"}}'
        transcript_bytes = (torn_line + "\n" + "\n".join(_resume_pair_lines("toolu_1", "합성 작업 이름")) + "\n").encode("utf-8")
        inside_first_character = transcript_bytes.index("가".encode("utf-8")) + 1
        budget = len(transcript_bytes) - inside_first_character
        self._transcript_path(self.CWD).parent.mkdir(parents=True, exist_ok=True)
        self._transcript_path(self.CWD).write_bytes(transcript_bytes)
        facts = self._facts((self._subagent(AGENT_ID, 1), self._subagent(OTHER_AGENT_ID, 1)))

        with mock.patch.object(hub_subagent_read, "RESUME_TITLE_SCAN_MAX_BYTES", budget):
            metas, _ = self._read(facts)
            window = hub_subagent_read._read_parent_transcript_window(self.SESSION_ID, (self.CWD,), self.temp_dir)

        with self.assertRaises(UnicodeDecodeError):
            window.split(b"\n")[0].decode("utf-8")   # 전제 — 찢긴 머리는 엄격한 디코딩이면 터진다
        self.assertEqual(metas[AGENT_ID].resume_title, "합성 작업 이름")
        self.assertIsNone(metas[OTHER_AGENT_ID].resume_title)

    # ---- R5 — 어느 파일을 읽는가 ----

    def test_r5_parent_transcript_is_found_under_a_later_observed_cwd(self) -> None:
        """호스트는 워크트리 진입 때 기록을 새 cwd 폴더로 옮긴다 — 첫 cwd 에는 파일이 없고 둘째에 있으면 찾는다(E13)."""
        self._write_meta_file("/repo/worktree", AGENT_ID)
        self._write_parent_transcript("/repo/worktree", _resume_pair_lines("toolu_1", "워크트리의 작업"))
        facts = self._facts((self._subagent(AGENT_ID, 1),), observed_cwds=("/repo/root", "/repo/worktree"))

        metas, _ = self._read(facts)

        self.assertEqual(metas[AGENT_ID].resume_title, "워크트리의 작업")

    def test_transcript_and_meta_are_located_independently(self) -> None:
        self._write_meta_file("/repo/root", AGENT_ID)
        self._write_parent_transcript("/repo/worktree", _resume_pair_lines("toolu_1", "워크트리의 작업"))
        facts = self._facts((self._subagent(AGENT_ID, 1),), observed_cwds=("/repo/root", "/repo/worktree"))

        metas, _ = self._read(facts)

        self.assertEqual(metas[AGENT_ID].resume_title, "워크트리의 작업")

    def test_first_existing_candidate_wins_deterministically(self) -> None:
        self._write_meta_file("/repo/first", AGENT_ID)
        self._write_parent_transcript("/repo/first", _resume_pair_lines("toolu_1", "먼저 있는 쪽"))
        self._write_parent_transcript("/repo/second", _resume_pair_lines("toolu_1", "나중 쪽"))
        facts = self._facts((self._subagent(AGENT_ID, 1),), observed_cwds=("/repo/first", "/repo/second"))

        metas, _ = self._read(facts)

        self.assertEqual(metas[AGENT_ID].resume_title, "먼저 있는 쪽")

    # ---- R6 — 경로 조각 방어 ----

    def test_r6_unsafe_session_ids_are_never_assembled_into_a_path(self) -> None:
        """session_id 가 `/`·`..` 를 품으면 Path 의 `/` 연산자가 인코딩 폴더 밖으로 나간다(C-7) — 조립 전에 거른다."""
        (self.temp_dir / hub_project.encode_project_dir_name(self.CWD)).mkdir(parents=True)
        decoy_dir = self.temp_dir / "decoy"
        decoy_dir.mkdir()
        (decoy_dir / "x.jsonl").write_text("\n".join(_resume_pair_lines("toolu_1", "밖의 파일")) + "\n", encoding="utf-8")
        self.assertTrue(self._transcript_path(self.CWD, "../decoy/x").is_file())   # 전제 — 가드가 없으면 조립 경로가 바깥 파일을 읽는다
        unsafe_session_ids = ("", ".", "..", "a/b", "../decoy/x", "/abs/path")
        for session_id in unsafe_session_ids:
            with self.subTest(session_id=session_id):
                window = hub_subagent_read._read_parent_transcript_window(session_id, (self.CWD,), self.temp_dir)

                self.assertIsNone(window)

    # ---- R7 — 읽기 실패 ----

    def test_r7_unreadable_parent_transcript_keeps_the_meta_and_does_not_raise(self) -> None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root 는 파일 권한 검사를 우회해 읽기 실패를 재현할 수 없다")
        self._write_meta_file(self.CWD, AGENT_ID)
        transcript_path = self._write_parent_transcript(self.CWD, _resume_pair_lines("toolu_1", "합성 작업 이름"))
        transcript_path.chmod(0o000)
        try:
            metas, warnings = self._read(self._facts((self._subagent(AGENT_ID, 1),)))
        finally:
            transcript_path.chmod(0o644)

        self.assertIsNone(metas[AGENT_ID].resume_title)
        self.assertEqual(metas[AGENT_ID].title, "첫 작업 이름")
        self.assertEqual(warnings, ())   # 실패와 정상 부재의 결과가 같다(폴백 = 오늘의 제목) — 경고를 돌려주지 않는다(SL8 과 같은 이유)

    def test_an_unreadable_candidate_falls_through_to_the_next_one(self) -> None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root 는 파일 권한 검사를 우회해 읽기 실패를 재현할 수 없다")
        first_path = self._write_parent_transcript("/repo/first", ["{}"])
        self._write_parent_transcript("/repo/second", _resume_pair_lines("toolu_1", "둘째 후보의 작업"))
        first_path.chmod(0o000)
        try:
            window = hub_subagent_read._read_parent_transcript_window(self.SESSION_ID, ("/repo/first", "/repo/second"), self.temp_dir)
        finally:
            first_path.chmod(0o644)

        self.assertIn("둘째 후보의 작업".encode("utf-8"), window)

    def test_a_directory_in_place_of_the_transcript_is_not_a_candidate(self) -> None:
        self._transcript_path(self.CWD).mkdir(parents=True)

        self.assertIsNone(hub_subagent_read._read_parent_transcript_window(self.SESSION_ID, (self.CWD,), self.temp_dir))


if __name__ == "__main__":
    unittest.main()
