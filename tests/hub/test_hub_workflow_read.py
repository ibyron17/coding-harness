"""hub_workflow_read 단위 테스트 — read_session_workflow·read_session_workflows(I/O 접합).

구현 2회차 검수로 hub_collect.py 에서 분리된 모듈이다(검수 A-1). 원래 test_hub_collect.py
의 ReadSessionWorkflowTest 를 이 파일로 옮기고, B-1(디렉터리 풀링)·C-4(warnings)·
C-7(session_id 방어)·D-1(디렉터리 EACCES)·D-2(파싱 실패 케이스) 테스트를 더했다.
mock.patch 없이 임시 디렉토리로 검증한다(정본 스타일: test_hub_transcript.py).
"""

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
import hub_workflow  # noqa: E402
import hub_workflow_read  # noqa: E402


class ReadSessionWorkflowTest(unittest.TestCase):
    """read_session_workflow·read_session_workflows(결정 WF2~WF11, 구현 2회차 B-1·C-4·C-7,
    docs/prps/hub-workflow-visibility.md)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _agent_item(self, label: str = "설계") -> dict:
        return {
            "type": "workflow_agent", "index": 1, "label": label,
            "phaseTitle": "Ground", "state": "done",
            "promptPreview": "지시", "resultPreview": "결과",
        }

    def _run_json(self, label: str = "설계") -> str:
        """label 로 파일을 구분한다 — WorkflowRunView.run_id 는 루프 밖 보완으로 제거된
        미사용 필드라(hub_template.html 참조 0건, §17) 더 이상 파일 식별자로 쓸 수 없다.
        agents[0].label 이 그 대체 식별자다."""
        payload = {
            "runId": "wf_a", "workflowName": "wf-name", "status": "completed",
            "startTime": 1000, "workflowProgress": [self._agent_item(label=label)],
        }
        return json.dumps(payload)

    def _session_facts(self, session_id: str, cwd: str) -> hub_session_facts.SessionFacts:
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=0,
            last_event_at_ms=0, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def _write_run_file(self, cwd: str, session_id: str, filename: str, content: str, mtime=None) -> Path:
        encoded_name = hub_project.encode_project_dir_name(cwd)
        workflows_dir = self.temp_dir / encoded_name / session_id / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        run_path = workflows_dir / filename
        run_path.write_text(content, encoding="utf-8")
        if mtime is not None:
            os.utime(run_path, (mtime, mtime))
        return run_path

    def _read(self, session_id: str, observed_cwds: tuple) -> tuple:
        return hub_workflow_read.read_session_workflow(session_id, observed_cwds, self.temp_dir)

    def test_missing_workflows_directory_returns_none(self) -> None:
        workflow, warning = self._read("sess-1", ("/repo/a",))
        self.assertIsNone(workflow)
        self.assertIsNone(warning)

    def test_workflows_in_host_folder_are_found_for_underscore_path(self) -> None:
        """N1(docs/prps/hub-agent-title-and-excerpt-freshness.md §16) — 밑줄 든 경로의 workflows/ 는 호스트가
        `_` 를 `-` 로 바꾼 폴더에 있다. 폴더 이름을 리터럴로 적는다 — _write_run_file 은 같은 함수로
        폴더를 만들어 순환한다."""
        workflows_dir = self.temp_dir / "-Users-dev-works-notebook-wiki-NotebookWiki" / "sess-1" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "wf_a.json").write_text(self._run_json("run-underscore"), encoding="utf-8")
        workflow, warning = self._read("sess-1", ("/Users/dev/works/notebook_wiki/NotebookWiki",))
        self.assertIsNone(warning)
        self.assertEqual(workflow.agents[0].label, "run-underscore")

    def test_most_recent_file_by_mtime_is_selected(self) -> None:
        """결정 WF5 — 세션당 최신 1건만 읽는다. 선택 기준은 파일 mtime 최댓값이다."""
        self._write_run_file("/repo/a", "sess-1", "wf_old.json", self._run_json("run-old"), mtime=1000)
        self._write_run_file("/repo/a", "sess-1", "wf_new.json", self._run_json("run-new"), mtime=2000)
        workflow, _ = self._read("sess-1", ("/repo/a",))
        self.assertEqual(workflow.agents[0].label, "run-new")

    def test_mtime_tie_breaks_by_reverse_lexicographic_filename(self) -> None:
        """결정 WF5 — mtime 이 동률이면 파일명 역순 사전식(알파벳상 더 뒤)이 결정적으로 이긴다."""
        same_mtime = 1000
        self._write_run_file("/repo/a", "sess-1", "wf_aaa.json", self._run_json("run-aaa"), mtime=same_mtime)
        self._write_run_file("/repo/a", "sess-1", "wf_bbb.json", self._run_json("run-bbb"), mtime=same_mtime)
        workflow, _ = self._read("sess-1", ("/repo/a",))
        self.assertEqual(workflow.agents[0].label, "run-bbb")

    def test_second_observed_cwd_is_found_for_worktree(self) -> None:
        """결정 WF4 — 첫 cwd(레포 루트)에는 workflows/ 자체가 없고 두 번째(워크트리)에
        있으면 찾아낸다(E13)."""
        self._write_run_file("/repo/worktree", "sess-1", "wf_a.json", self._run_json())
        workflow, _ = self._read("sess-1", ("/repo/root", "/repo/worktree"))
        self.assertIsNotNone(workflow)

    def test_all_existing_directories_are_pooled_and_overall_latest_wins(self) -> None:
        """결정 WF4 개정(구현 2회차 B-1) — 관측 cwd 후보 전부에 workflows/ 가 있으면 그중
        mtime 최신인 실행 1건을 고른다. 1회차에는 첫 존재 디렉터리에서 멈춰, 세션이
        워크트리 이동 전후 두 번 워크플로우를 돌리면 **오래된 쪽이 이겼다** — "세션당 최신
        1건"(결정 WF5)이라는 목적과 어긋났다."""
        self._write_run_file("/repo/root", "sess-1", "wf_old.json", self._run_json("run-old"), mtime=1000)
        self._write_run_file("/repo/worktree", "sess-1", "wf_new.json", self._run_json("run-new"), mtime=2000)
        workflow, warning = self._read("sess-1", ("/repo/root", "/repo/worktree"))
        self.assertEqual(workflow.agents[0].label, "run-new")
        self.assertIsNone(warning)

    def test_empty_first_directory_does_not_block_the_second(self) -> None:
        """구현 2회차 D-2 재작성 — 1회차의 "먼저 존재하는 디렉터리가 이긴다"(파싱 실패해도
        다음으로 안 넘어간다) 규칙은 B-1 로 폐기됐다. 이제는 디렉터리 자체가 후보를 0개
        보태면(빈 디렉터리) 다른 디렉터리의 후보가 정상적으로 선택된다 — "먼저 존재하는
        후보가 이긴다"가 아니라 "전체에서 최신이 이긴다"이기 때문이다."""
        first_encoded = hub_project.encode_project_dir_name("/repo/first")
        (self.temp_dir / first_encoded / "sess-1" / "workflows").mkdir(parents=True)
        self._write_run_file("/repo/second", "sess-1", "wf_a.json", self._run_json())
        workflow, _ = self._read("sess-1", ("/repo/first", "/repo/second"))
        self.assertIsNotNone(workflow)

    def test_broken_json_in_the_latest_file_returns_none_without_falling_back(self) -> None:
        """구현 2회차 D-2 — PRP §11 표 문구("첫 후보 존재하나 파싱 실패") 그대로의 케이스를
        B-1 이후 의미로 재현한다: 풀링된 후보 중 mtime 최신인 파일이 깨져 있으면, 더 오래된
        다른 후보가 유효하더라도 **그쪽으로 넘어가지 않는다**(결정적, 상한이 곧 예산 —
        1회차 "다음 후보로 넘어가지 않는다" 불변식의 현대 형태)."""
        self._write_run_file("/repo/a", "sess-1", "wf_broken.json", "{", mtime=2000)
        self._write_run_file("/repo/a", "sess-1", "wf_valid.json", self._run_json("run-valid"), mtime=1000)
        workflow, warning = self._read("sess-1", ("/repo/a",))
        self.assertIsNone(workflow)
        self.assertIsNone(warning)  # 파싱 실패는 경고 없이 조용히 None(§2 계약의 일부)

    def test_oversized_file_is_not_read(self) -> None:
        """결정 WF11 — 상한을 넘는 파일은 열지 않고 None. 구현 2회차 C-4 — 사유가
        warnings 로 나와야 한다(1회차에는 무음 실패였다)."""
        oversized_content = self._run_json() + (" " * hub_workflow.WORKFLOW_RUN_MAX_BYTES)
        self._write_run_file("/repo/a", "sess-1", "wf_a.json", oversized_content)
        workflow, warning = self._read("sess-1", ("/repo/a",))
        self.assertIsNone(workflow)
        self.assertIsNotNone(warning)
        self.assertIn("상한", warning)

    def test_permission_denied_returns_none_without_raising(self) -> None:
        """구현 2회차 C-4 — 파일 읽기 실패(OSError)도 warnings 에 사유를 남긴다."""
        run_path = self._write_run_file("/repo/a", "sess-1", "wf_a.json", self._run_json())
        run_path.chmod(0o000)
        try:
            workflow, warning = self._read("sess-1", ("/repo/a",))
        finally:
            run_path.chmod(0o644)
        self.assertIsNone(workflow)
        self.assertIsNotNone(warning)

    def test_workflows_directory_permission_denied_returns_none_without_raising(self) -> None:
        """구현 2회차 D-1 — `workflows_dir.is_dir()` 의 EACCES 분기 재현. pathlib 은
        ENOENT/ENOTDIR/EBADF/ELOOP 만 삼키고 EACCES 는 재발생시킨다(실측: 대상 자체를
        chmod(0o000) 해도 stat 은 대상 자체가 아니라 **부모의 실행 권한만** 요구하므로
        is_dir() 은 여전히 True 를 반환한다 — EACCES 를 재현하려면 workflows_dir 의
        부모(session_id 디렉터리)를 잠가야 한다). root 는 권한 검사를 우회해 재현이
        불가능하므로 skip 한다."""
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root 는 디렉터리 권한 검사를 우회해 EACCES 를 재현할 수 없다")
        encoded_name = hub_project.encode_project_dir_name("/repo/a")
        session_dir = self.temp_dir / encoded_name / "sess-1"
        workflows_dir = session_dir / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "wf_a.json").write_text(self._run_json(), encoding="utf-8")
        session_dir.chmod(0o000)
        try:
            workflow, warning = self._read("sess-1", ("/repo/a",))
        finally:
            session_dir.chmod(0o755)
        self.assertIsNone(workflow)
        self.assertIsNone(warning)

    def test_torn_multibyte_content_does_not_raise(self) -> None:
        """GOTCHA 7 — errors="replace" 가 없으면 UnicodeDecodeError(ValueError 서브클래스)가
        except OSError 를 뚫는다. 찢긴 바이트는 U+FFFD 로 대체돼 JSON 파싱 실패로 자연히
        탈락할 뿐, 예외를 일으키지 않는다."""
        encoded_name = hub_project.encode_project_dir_name("/repo/a")
        workflows_dir = self.temp_dir / encoded_name / "sess-1" / "workflows"
        workflows_dir.mkdir(parents=True)
        torn_bytes = self._run_json().encode("utf-8") + "가".encode("utf-8")[:2]
        (workflows_dir / "wf_a.json").write_bytes(torn_bytes)
        workflow, warning = self._read("sess-1", ("/repo/a",))
        self.assertIsNone(workflow)
        self.assertIsNone(warning)

    def test_session_id_with_path_separator_is_rejected(self) -> None:
        """구현 2회차 C-7 — session_id 가 `/` 를 포함하면(예: 절대경로) Path 의 `/` 연산자가
        앞부분을 버려 임의 디렉터리를 가리킬 수 있다. 경로 조립 전에 걷어낸다."""
        workflow, warning = self._read("/tmp/x", ("/repo/a",))
        self.assertIsNone(workflow)
        self.assertIsNone(warning)

    def test_session_id_dot_segments_are_rejected(self) -> None:
        """구현 2회차 C-7 — "."·".." 도 같은 이유로 걷어낸다."""
        for session_id in ("", ".", ".."):
            with self.subTest(session_id=session_id):
                workflow, warning = self._read(session_id, ("/repo/a",))
                self.assertIsNone(workflow)
                self.assertIsNone(warning)

    def test_read_session_workflows_omits_sessions_without_a_value(self) -> None:
        self._write_run_file("/repo/a", "sess-with-workflow", "wf_a.json", self._run_json())
        sessions_by_path = {
            "/repo/a": (
                self._session_facts("sess-with-workflow", "/repo/a"),
                self._session_facts("sess-without-workflow", "/repo/a"),
            )
        }
        workflows, warnings = hub_workflow_read.read_session_workflows(
            sessions_by_path, record_prompt_excerpt=True, projects_dir=self.temp_dir
        )
        self.assertEqual(set(workflows), {"sess-with-workflow"})
        self.assertEqual(warnings, ())

    def test_record_prompt_excerpt_false_returns_empty_result_without_reading_files(self) -> None:
        """결정 WF8 — show_usage_panel:false 가 사용량 파일을 안 읽는 결정 U4 와 같은 형태.
        read_session_workflow 호출 자체가 0회여야 한다(열기 시도가 0회임을 보증)."""
        self._write_run_file("/repo/a", "sess-1", "wf_a.json", self._run_json())
        sessions_by_path = {"/repo/a": (self._session_facts("sess-1", "/repo/a"),)}
        with mock.patch.object(hub_workflow_read, "read_session_workflow") as mock_read:
            workflows, warnings = hub_workflow_read.read_session_workflows(
                sessions_by_path, record_prompt_excerpt=False, projects_dir=self.temp_dir
            )
        self.assertEqual(workflows, {})
        self.assertEqual(warnings, ())
        mock_read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
