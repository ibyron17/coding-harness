"""hub_collect 의 I/O 로직 단위 테스트. 실제 ~/.claude 는 건드리지 않고 모듈 상수를
임시 디렉토리로 바꿔치기(monkeypatch)한 뒤 원상복구한다. 검수 M2·M7·m3·m4·m5 회귀 대상.
"""

import inspect
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402
import hub_atomic_write  # noqa: E402
import hub_collect  # noqa: E402
import hub_model  # noqa: E402
import hub_parse  # noqa: E402
import hub_project  # noqa: E402
import hub_server_state  # noqa: E402
import hub_server_state_read  # noqa: E402
import hub_session  # noqa: E402
import hub_session_cost  # noqa: E402
import hub_session_facts  # noqa: E402
import hub_subagent_read  # noqa: E402
import hub_transcript  # noqa: E402
import hub_usage  # noqa: E402
import hub_workflow  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다(test_hub_template_dom.py 의 관례).
try:
    from .resume_transcript_fixtures import AGENT_ID as RESUMED_AGENT_ID, resume_pair_lines as _resume_pair_lines
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from resume_transcript_fixtures import (  # noqa: E402
        AGENT_ID as RESUMED_AGENT_ID,
        resume_pair_lines as _resume_pair_lines,
    )

try:
    from .live_activity_fixtures import jsonl_bytes as _jsonl_bytes, use_line as _use_line
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from live_activity_fixtures import jsonl_bytes as _jsonl_bytes, use_line as _use_line  # noqa: E402


def _minimal_snapshot(collected_at_ms: int) -> hub_model.HubSnapshot:
    return hub_model.HubSnapshot(
        collected_at_ms=collected_at_ms, projects=(), unresolved_dir_names=(), warnings=()
    )


class ServerRecordRoundTripTest(unittest.TestCase):
    """검수 m3 — read_server_record 가 실제로 hub_server_state.parse_server_record(공유 파서)를
    거치는지 실사용 경로(파일 I/O)로 확인한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_server_state_read.HUB_HOME
        self.original_record_path = hub_server_state_read.SERVER_RECORD_PATH
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_server_state_read.SERVER_RECORD_PATH = self.temp_dir / "server.json"

    def tearDown(self) -> None:
        hub_server_state_read.HUB_HOME = self.original_hub_home
        hub_server_state_read.SERVER_RECORD_PATH = self.original_record_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_then_read_round_trip(self) -> None:
        record = hub_server_state.ServerRecord(pid=123, port=8794, started_at_ms=1786000000000)
        hub_server_state_read.write_server_record(record)
        self.assertEqual(hub_server_state_read.read_server_record(), record)

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(hub_server_state_read.read_server_record())

    def test_broken_json_returns_none_without_raising(self) -> None:
        hub_server_state_read.SERVER_RECORD_PATH.write_text("{not valid json")
        self.assertIsNone(hub_server_state_read.read_server_record())


class ClearServerStateCompareAndDeleteTest(unittest.TestCase):
    """검수 m1 — expected_pid 가 주어지면 현재 server.json 의 pid 가 그것과 같을 때만 지운다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_server_state_read.HUB_HOME
        self.original_record_path = hub_server_state_read.SERVER_RECORD_PATH
        self.original_heartbeat_path = hub_server_state_read.SERVER_HEARTBEAT_PATH
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_server_state_read.SERVER_RECORD_PATH = self.temp_dir / "server.json"
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.temp_dir / "server_heartbeat"

    def tearDown(self) -> None:
        hub_server_state_read.HUB_HOME = self.original_hub_home
        hub_server_state_read.SERVER_RECORD_PATH = self.original_record_path
        hub_server_state_read.SERVER_HEARTBEAT_PATH = self.original_heartbeat_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_does_not_delete_when_pid_was_replaced_by_a_newer_server(self) -> None:
        """다른 셸이 이미 새 서버를 띄워 server.json 을 갈아 끼운 뒤에는 지우면 안 된다."""
        old_record = hub_server_state.ServerRecord(pid=111, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(old_record)
        hub_server_state_read.touch_server_heartbeat()

        # 다른 프로세스가 새 서버를 등록했다고 가정한다.
        new_record = hub_server_state.ServerRecord(pid=222, port=8794, started_at_ms=2)
        hub_server_state_read.write_server_record(new_record)

        hub_server_state_read.clear_server_state(expected_pid=old_record.pid)

        self.assertEqual(hub_server_state_read.read_server_record(), new_record)
        self.assertTrue(hub_server_state_read.SERVER_HEARTBEAT_PATH.exists())

    def test_deletes_when_pid_still_matches(self) -> None:
        record = hub_server_state.ServerRecord(pid=111, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.touch_server_heartbeat()

        hub_server_state_read.clear_server_state(expected_pid=record.pid)

        self.assertIsNone(hub_server_state_read.read_server_record())
        self.assertFalse(hub_server_state_read.SERVER_HEARTBEAT_PATH.exists())

    def test_deletes_when_record_already_absent(self) -> None:
        hub_server_state_read.clear_server_state(expected_pid=111)  # 예외 없이 조용히 통과해야 한다
        self.assertIsNone(hub_server_state_read.read_server_record())

    def test_no_expected_pid_always_deletes(self) -> None:
        record = hub_server_state.ServerRecord(pid=111, port=8794, started_at_ms=1)
        hub_server_state_read.write_server_record(record)
        hub_server_state_read.clear_server_state()
        self.assertIsNone(hub_server_state_read.read_server_record())


class WriteHubHtmlAtomicityTest(unittest.TestCase):
    """검수 M2 — 고정 임시 파일명을 공유하면 동시 쓰기가 뒤섞인다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_hub_html_path = hub_collect.HUB_HTML_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.HUB_HTML_PATH = self.original_hub_html_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_writes_never_produce_corrupted_output(self) -> None:
        barrier = threading.Barrier(2)

        def write(collected_at_ms: int) -> None:
            barrier.wait()
            hub_collect.write_hub_html(_minimal_snapshot(collected_at_ms))

        threads = [threading.Thread(target=write, args=(value,)) for value in (111, 222)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        final_text = hub_collect.HUB_HTML_PATH.read_text(encoding="utf-8")
        payload = final_text.split('id="dzh-data">', 1)[1].split("</script>", 1)[0]
        data = json.loads(payload)  # 뒤섞였다면 여기서 JSONDecodeError 가 난다
        self.assertIn(data["collected_at_ms"], (111, 222))

    def test_no_leftover_temp_files_after_write(self) -> None:
        hub_collect.write_hub_html(_minimal_snapshot(1))
        leftover = list(self.temp_dir.glob("hub.html.*.tmp"))
        self.assertEqual(leftover, [])


class WriteHubHtmlSurrogateHandlingTest(unittest.TestCase):
    """루프 밖 보완 HIGH-A — 고립 서로게이트(호스트가 UTF-16 코드유닛 400개 경계에서
    이모지 서로게이트 쌍을 쪼개면 발생, 재현: {"promptPreview": "a\\ud83db"})가 워크플로우
    뷰에 실리면, json.loads·render_hub_html(ensure_ascii=False)까지는 예외 없이 통과하고
    hub_atomic_write.atomic_write_text 의 os.fdopen(..., encoding="utf-8") 에서 UnicodeEncodeError 로
    죽는다 — 그 wf 파일이 세션 mtime 최신인 동안 매 수집 사이클마다 hub.html 쓰기 자체가
    막히는 결함이었다. 이 계열은 "파서가 예외를 안 던진다"만으로는 닫히지 않는다 —
    렌더→실제 파일 쓰기까지 통과해야 닫힌다(검수 지적)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_hub_html_path = hub_collect.HUB_HTML_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.HUB_HTML_PATH = self.original_hub_html_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _snapshot_with_unpaired_surrogate(self) -> hub_model.HubSnapshot:
        agent = hub_workflow.WorkflowAgentView(index=1, label="a\ud83db", state="done")
        session = hub_session.SessionView(
            session_id="s1", short_id="s1", started_at_ms=0,
            state="working", base_state="working", last_event_at_ms=0,
            task_excerpt=None, agent_runs=(), workflow=hub_workflow.WorkflowRunView(agents=(agent,)),
        )
        project = hub_project.ProjectView(
            display_name="p", path="/repo", tier=2, state="working",
            last_activity_at_ms=0, sessions=(session,), tier1=None, note=None,
        )
        return hub_model.HubSnapshot(
            collected_at_ms=0, projects=(project,), unresolved_dir_names=(), warnings=()
        )

    def test_write_hub_html_does_not_raise_and_produces_a_file(self) -> None:
        hub_collect.write_hub_html(self._snapshot_with_unpaired_surrogate())  # 던지면 이 테스트가 실패한다
        self.assertTrue(hub_collect.HUB_HTML_PATH.is_file())

    def test_written_file_is_valid_utf8_and_carries_the_rest_of_the_string(self) -> None:
        """정규화가 서로게이트를 U+FFFD 로 치환하고 나머지 문자는 보존하는지 확인한다.

        `assertNotIn("\\ud83d", text)` 만으로는 치환 문자가 '?' 든 U+FFFD 든 제거든 구별하지
        못한다 — 픽스처 문자열("a\\ud83db")은 원래 '?' 를 포함하지 않으므로, 치환 결과에 '?'
        가 있다면 그건 옛 구현(encode "replace")의 산물이다. '?' 부재 검사를 JSON payload
        의 해당 필드로 좁히는 이유는 hub_template.html 자체가 인라인 JS 에서 '?' 를 32곳
        (삼항 연산자 등)에서 쓰기 때문에, 전체 text 에 대해 assertNotIn("?", text) 하면
        무관한 매치로 항상 실패한다."""
        hub_collect.write_hub_html(self._snapshot_with_unpaired_surrogate())
        text = hub_collect.HUB_HTML_PATH.read_text(encoding="utf-8")  # UTF-8 로 다시 읽혀야 한다
        self.assertIn("a", text)
        self.assertIn("b", text)
        self.assertNotIn("\ud83d", text)

        payload = text.split('id="dzh-data">', 1)[1].split("</script>", 1)[0]
        agent = json.loads(payload)["projects"][0]["sessions"][0]["workflow"]["agents"][0]
        self.assertEqual(agent["label"], "a\ufffdb")


class Tier3IgnoreFilterTest(unittest.TestCase):
    """검수 m4 — ignore_globs 를 인코딩한 패턴으로 티어 3 소음(worktree·scratchpad)을 원천 제거한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        hub_collect.PROJECTS_DIR = self.temp_dir

    def tearDown(self) -> None:
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_encoded_project_dir(self, encoded_name: str) -> None:
        project_dir = self.temp_dir / encoded_name
        project_dir.mkdir()
        (project_dir / "session.jsonl").write_text("{}")

    def test_worktree_and_tmp_encoded_names_are_excluded(self) -> None:
        self._make_encoded_project_dir("-Users-b-repo--claude-worktrees-f1")
        self._make_encoded_project_dir("-private-tmp-claude-501-x")
        self._make_encoded_project_dir("-Users-b-private-project-coding-harness")

        ignore_globs = hub_model.HubConfig().ignore_globs
        activity, warnings = hub_collect._tier3_activity_by_encoded_name(ignore_globs)

        self.assertEqual(list(activity), ["-Users-b-private-project-coding-harness"])
        self.assertEqual(warnings, ())

    def test_user_glob_with_underscore_and_space_matches_host_folder_names(self) -> None:
        """N1 — 호스트 규칙은 `_`·공백도 `-` 로 바꾼다. 사용자가 config 에 적은 패턴의 그런 글자도 같은 규칙으로
        인코딩돼야 폴더 이름(리터럴)에 맞는다. 이웃 이름(my_apple)은 걸러지지 않는다."""
        self._make_encoded_project_dir("-Users-b-my-app-v1-sub")
        self._make_encoded_project_dir("-Users-b-my-apple")

        activity, warnings = hub_collect._tier3_activity_by_encoded_name(("/Users/b/my_app v1/**",))

        self.assertEqual(list(activity), ["-Users-b-my-apple"])
        self.assertEqual(warnings, ())

    def test_r3_m1_iterdir_permission_error_gives_up_tier3_only(self) -> None:
        """검수 R3-m1 — PROJECTS_DIR.iterdir() 실패는 티어 3 전체를 포기하되 예외를 던지지 않는다."""
        self._make_encoded_project_dir("-Users-b-private-project-coding-harness")
        self.temp_dir.chmod(0o000)
        try:
            activity, warnings = hub_collect._tier3_activity_by_encoded_name(())
        finally:
            self.temp_dir.chmod(0o755)

        self.assertEqual(activity, {})
        self.assertEqual(len(warnings), 1)
        self.assertIn("목록 조회 실패", warnings[0])

    def test_r3_m1_entry_stat_failure_skips_only_that_project(self) -> None:
        """검수 R3-m1 — glob 열거와 stat 사이의 TOCTOU(파일이 그 사이 사라짐)는 그 프로젝트만
        건너뛴다. 디렉토리 권한만으로는 이 race 를 재현할 수 없다(glob 이 권한 오류를 삼키고
        빈 목록을 반환함을 실측 확인) — Path.stat 을 패치해 결정적으로 재현한다."""
        self._make_encoded_project_dir("-Users-b-private-project-coding-harness")
        self._make_encoded_project_dir("-Users-b-flaky")
        flaky_jsonl = self.temp_dir / "-Users-b-flaky" / "session.jsonl"
        original_stat = Path.stat

        def _flaky_stat(path_self, *args, **kwargs):
            if path_self == flaky_jsonl:
                raise OSError("simulated TOCTOU: file vanished between glob and stat")
            return original_stat(path_self, *args, **kwargs)

        with mock.patch.object(Path, "stat", _flaky_stat):
            activity, warnings = hub_collect._tier3_activity_by_encoded_name(())

        self.assertIn("-Users-b-private-project-coding-harness", activity)
        self.assertNotIn("-Users-b-flaky", activity)
        self.assertEqual(len(warnings), 1)
        self.assertIn("mtime 조회 실패", warnings[0])


class WorktreeFoldGroupingTest(unittest.TestCase):
    """U-11~U-13 — _group_sessions_by_project 는 fold 를 ignore 보다 먼저 적용한다
    (결정 WT4·WT5, docs/prps/hub-worktree-fold.md)."""

    BASE_TIME_MS = 1_786_000_000_000

    def _event(self, cwd: str, received_at_ms: int | None = None) -> hub_session_facts.HookEvent:
        return hub_session_facts.HookEvent(
            received_at_ms=received_at_ms if received_at_ms is not None else self.BASE_TIME_MS,
            hook_event_name="UserPromptSubmit",
            session_id="s1", cwd=cwd, source=None, reason=None, agent_id=None, agent_type=None,
        )

    def test_u11_worktree_cwd_groups_under_repo_root(self) -> None:
        """S1 — 워크트리 cwd 이벤트가 레포 루트 그룹으로 묶인다. **기본** ignore_globs 를
        쓴다(빈 튜플이면 워크트리 glob 이 아예 발동하지 않아 fold-먼저 순서를 검증하지 못한다) —
        기본값에는 `**/.claude/worktrees/**` 가 있어, ignore 가 먼저였다면 이 세션은 통째로
        사라졌을 것이다."""
        ignore_globs = hub_model.HubConfig().ignore_globs
        events = [self._event("/repo/.claude/worktrees/w")]
        grouped = hub_collect._group_sessions_by_project(events, ignore_globs)
        self.assertIn("/repo", grouped)
        self.assertNotIn("/repo/.claude/worktrees/w", grouped)

    def test_u12_flip_scenario_session_survives_when_first_event_is_worktree(self) -> None:
        """S2(E5 재현) — 창이 굴러 첫 이벤트가 만료되면 남는 이벤트는 전부 워크트리 cwd 다.
        그 궤적을 **같은 세션의 이벤트 2건**(시각차만 다름)으로 재현한다(검수 1회차 m3 —
        이벤트 1건짜리는 U-11 과 입력이 사실상 같아 flip 을 실제로 재현하지 못했다).

        「접기 전」 비교는 손수 그룹핑을 재구현하지 않고 실제 술어 `should_ignore_cwd` 를
        원본(미접힘) cwd 에 직접 호출한다(검수 1회차 m3 — 예전 버전은 `pre_fold_grouped` 에
        애초에 원본 cwd 로만 키를 넣어 두고 "/repo 가 없다"를 확인했는데, 그 키 자체가
        `should_ignore_cwd` 를 전혀 거치지 않아 무슨 뮤테이션을 넣어도 항상 참인 항진명제였다).
        이 단언이 참이라는 것은 곧 「ignore 를 fold 전에 적용하면(결정 WT5 위반) 이 세션이
        `_group_sessions_by_project` 안에서 통째로 걸러진다」는 실제 위험 경로를 보여준다."""
        ignore_globs = hub_model.HubConfig().ignore_globs
        events = [
            self._event("/repo/.claude/worktrees/w"),
            self._event("/repo/.claude/worktrees/w", received_at_ms=self.BASE_TIME_MS + 60_000),
        ]

        grouped = hub_collect._group_sessions_by_project(events, ignore_globs)
        self.assertEqual(len(grouped.get("/repo", ())), 1)
        self.assertEqual(grouped["/repo"][0].session_id, "s1")

        raw_cwd = hub_session_facts.build_session_facts(events)["s1"].cwd
        self.assertTrue(hub_project.should_ignore_cwd(raw_cwd, ignore_globs))

    def test_u13_folded_scratchpad_worktree_is_still_ignored(self) -> None:
        """E9 회귀 방어 — /private/tmp 아래 워크트리는 접어도 여전히 제외된다."""
        ignore_globs = hub_model.HubConfig().ignore_globs
        events = [self._event("/private/tmp/claude-501/scratch-repo/.claude/worktrees/w")]
        grouped = hub_collect._group_sessions_by_project(events, ignore_globs)
        self.assertEqual(grouped, {})


_VALID_INIT_TIME_MS = 1_700_000_000_000  # hub_parse 의 sanity 범위(2000~2100년) 안의 임의 값


def _dashboard_jsonl(title: str, time_ms: int = _VALID_INIT_TIME_MS) -> str:
    """세션별 진행 기록 픽스처 한 줄(init 이벤트만) — HD5~HD8 이후 읽기 대상은 이 형식뿐이다."""
    event = {"time_ms": time_ms, "kind": "init", "title": title, "phases": ["구현", "검수"], "project": "repo"}
    return json.dumps(event, ensure_ascii=False) + "\n"


class ReadSessionDashboardSnapshotsTest(unittest.TestCase):
    """P9(hub-session-tree-and-per-session-dashboards.md) —
    read_session_dashboard_snapshots: 디렉토리 열거 + 파일명 정규식 필터(결정 ST9).
    M2(dashboard-into-hub.md HD6·HD8)로 읽는 파일이 `.jsonl` 로 바뀌고, task_started_at_ms
    의 출처가 사이드카 mtime 에서 JSONL 첫 줄(init)의 time_ms 로 바뀌었다."""

    SESSION_ID_A = "f733cfcd-32eb-4339-9d99-e7375887e376"
    SESSION_ID_B = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_path = str(self.temp_dir / "repo")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _dashboards_dir(self) -> Path:
        dashboards_dir = Path(self.project_path) / ".claude" / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        return dashboards_dir

    def test_missing_directory_returns_empty_without_warnings(self) -> None:
        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)
        self.assertEqual((snapshots, warnings), ((), ()))

    def test_only_uuid_jsonl_files_are_parsed(self) -> None:
        dashboards_dir = self._dashboards_dir()
        (dashboards_dir / f"{self.SESSION_ID_A}.jsonl").write_text(
            _dashboard_jsonl("세션 A"), encoding="utf-8"
        )
        (dashboards_dir / f"{self.SESSION_ID_B}.jsonl").write_text(
            _dashboard_jsonl("세션 B"), encoding="utf-8"
        )
        (dashboards_dir / "README.md").write_text("무시 대상", encoding="utf-8")
        (dashboards_dir / "garbage.jsonl").write_text("무시 대상", encoding="utf-8")

        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(warnings, ())
        self.assertEqual({s.session_id for s in snapshots}, {self.SESSION_ID_A, self.SESSION_ID_B})
        for snapshot in snapshots:
            self.assertEqual(snapshot.source_path, self.project_path)
            self.assertGreater(snapshot.file_mtime_ms, 0)

    def test_missing_init_event_yields_one_warning_and_is_excluded(self) -> None:
        dashboards_dir = self._dashboards_dir()
        (dashboards_dir / f"{self.SESSION_ID_A}.jsonl").write_text(
            json.dumps({"time_ms": 1, "kind": "impl", "summary": "init 없음", "detail": ""}) + "\n",
            encoding="utf-8",
        )

        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)

        self.assertEqual(snapshots, ())
        self.assertEqual(len(warnings), 1)

    def test_directory_listing_failure_is_isolated_and_returns_a_warning(self) -> None:
        """B-9(검수 2회차) — docstring 이 약속한 실패 경로(디렉토리 목록 조회 실패)의 실측:
        dashboards_dir 자체를 읽을 수 없어도 collect 파이프라인은 이 프로젝트만 건너뛴다."""
        dashboards_dir = self._dashboards_dir()
        dashboards_dir.chmod(0o000)
        try:
            snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)
        finally:
            dashboards_dir.chmod(0o755)

        self.assertEqual(snapshots, ())
        self.assertEqual(len(warnings), 1)
        self.assertIn("목록 조회 실패", warnings[0])

    def test_one_file_read_failure_does_not_abort_the_sibling_file(self) -> None:
        """B-9(검수 2회차) — 격리 계약: 파일 하나의 읽기 실패(권한 없음)가 같은 디렉토리의
        정상 항목까지 끌고 내려가지 않는다. docstring 이 약속한 실패 경로(파일 읽기 실패)의 실측."""
        dashboards_dir = self._dashboards_dir()
        good_path = dashboards_dir / f"{self.SESSION_ID_A}.jsonl"
        bad_path = dashboards_dir / f"{self.SESSION_ID_B}.jsonl"
        good_path.write_text(_dashboard_jsonl("정상"), encoding="utf-8")
        bad_path.write_text(_dashboard_jsonl("읽기 실패 예정"), encoding="utf-8")
        bad_path.chmod(0o000)
        try:
            snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)
        finally:
            bad_path.chmod(0o644)

        self.assertEqual({snapshot.session_id for snapshot in snapshots}, {self.SESSION_ID_A})
        self.assertEqual(len(warnings), 1)
        self.assertIn("읽기 실패", warnings[0])

    def test_task_started_at_ms_comes_from_the_init_event_time(self) -> None:
        """HD8(docs/prps/dashboard-into-hub.md) — 작업 시작 시각은 JSONL 첫 줄(init)의
        time_ms 다(M1 까지는 사이드카 mtime 이었다)."""
        dashboards_dir = self._dashboards_dir()
        init_time_ms = 1_700_000_000_000
        (dashboards_dir / f"{self.SESSION_ID_A}.jsonl").write_text(
            _dashboard_jsonl("세션 A", time_ms=init_time_ms), encoding="utf-8"
        )

        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)

        self.assertEqual(warnings, ())
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].task_started_at_ms, init_time_ms)

    def test_collection_does_not_overwrite_task_started_at_ms_with_file_mtime(self) -> None:
        """수집이 task_started_at_ms 를 덮어쓰지 않는다(HD8) — 파일 mtime 을 init 시각과
        다르게 강제로 바꿔도 task_started_at_ms 는 여전히 init 시각을 가리킨다."""
        dashboards_dir = self._dashboards_dir()
        init_time_ms = 1_700_000_000_000
        dashboard_path = dashboards_dir / f"{self.SESSION_ID_A}.jsonl"
        dashboard_path.write_text(_dashboard_jsonl("세션 A", time_ms=init_time_ms), encoding="utf-8")
        touched_mtime_seconds = init_time_ms / 1000 + 3600  # init 시각과 다르게 1시간 뒤로
        os.utime(dashboard_path, (touched_mtime_seconds, touched_mtime_seconds))

        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)

        self.assertEqual(warnings, ())
        self.assertEqual(snapshots[0].task_started_at_ms, init_time_ms)
        self.assertEqual(snapshots[0].file_mtime_ms, int(touched_mtime_seconds * 1000))
        self.assertNotEqual(snapshots[0].task_started_at_ms, snapshots[0].file_mtime_ms)

    def test_two_sessions_each_keep_their_own_task_started_at_ms(self) -> None:
        """세션마다 독립된 task_started_at_ms — 값이 한 세션에서 다른 세션으로 새지 않는다."""
        dashboards_dir = self._dashboards_dir()
        session_a_time_ms = _VALID_INIT_TIME_MS
        session_b_time_ms = _VALID_INIT_TIME_MS + 1000
        (dashboards_dir / f"{self.SESSION_ID_A}.jsonl").write_text(
            _dashboard_jsonl("세션 A", time_ms=session_a_time_ms), encoding="utf-8"
        )
        (dashboards_dir / f"{self.SESSION_ID_B}.jsonl").write_text(
            _dashboard_jsonl("세션 B", time_ms=session_b_time_ms), encoding="utf-8"
        )

        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)

        self.assertEqual(warnings, ())
        started_at_by_session = {s.session_id: s.task_started_at_ms for s in snapshots}
        self.assertEqual(
            started_at_by_session, {self.SESSION_ID_A: session_a_time_ms, self.SESSION_ID_B: session_b_time_ms}
        )

    def test_parse_failure_in_one_project_does_not_affect_another_project(self) -> None:
        """RA1(재검수 2회차, 수집 단위) — hub_parse.parse_dashboard_jsonl 이 계약을 어기고
        예외를 던지는 파일이 있어도(그 계약이 미래에 깨지는 경우의 2차 방어선, RA1-e), 그
        파일 하나만 경고로 건너뛰고 다른 프로젝트의 수집은 영향을 받지 않는다."""
        project_a = self.project_path
        project_b = str(self.temp_dir / "repo_b")
        dashboards_dir_a = self._dashboards_dir()
        dashboards_dir_b = Path(project_b) / ".claude" / "dashboards"
        dashboards_dir_b.mkdir(parents=True)
        (dashboards_dir_a / f"{self.SESSION_ID_A}.jsonl").write_text(
            _dashboard_jsonl("깨진 프로젝트"), encoding="utf-8"
        )
        (dashboards_dir_b / f"{self.SESSION_ID_B}.jsonl").write_text(
            _dashboard_jsonl("정상 프로젝트"), encoding="utf-8"
        )
        real_parse = hub_parse.parse_dashboard_jsonl

        def _raise_only_for_broken_project(text: str):
            if "깨진 프로젝트" in text:
                raise TypeError("unhashable type: 'list'")
            return real_parse(text)

        with mock.patch.object(hub_parse, "parse_dashboard_jsonl", side_effect=_raise_only_for_broken_project):
            snapshots_a, warnings_a = hub_collect.read_session_dashboard_snapshots(project_a)
            snapshots_b, warnings_b = hub_collect.read_session_dashboard_snapshots(project_b)

        self.assertEqual(snapshots_a, ())
        self.assertEqual(len(warnings_a), 1)
        self.assertIn("파싱 실패", warnings_a[0])
        self.assertEqual({snapshot.session_id for snapshot in snapshots_b}, {self.SESSION_ID_B})
        self.assertEqual(warnings_b, ())

    def test_coexisting_legacy_html_and_sidecar_files_are_ignored(self) -> None:
        """RB3(재검수 2회차) — M1 잔존 산출물(.html·초기값 사이드카)이 같은 세션 ID 로 같은
        디렉터리에 남아 있어도 .jsonl 스냅샷 1건만 읽는다(리텐션 대상일 뿐 읽기 대상이
        아니다, PRP §14.2 M2 TDD 순서 2번 "셋을 다 둔 디렉터리로 검증")."""
        dashboards_dir = self._dashboards_dir()
        (dashboards_dir / f"{self.SESSION_ID_A}.jsonl").write_text(
            _dashboard_jsonl("세션 A"), encoding="utf-8"
        )
        (dashboards_dir / f"{self.SESSION_ID_A}.html").write_text("<html>구세대</html>", encoding="utf-8")
        session_token = self.SESSION_ID_A.split("-", 1)[0]
        (dashboards_dir / f"{session_token}.init-values.json").write_text("{}", encoding="utf-8")

        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(self.project_path)

        self.assertEqual(warnings, ())
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].session_id, self.SESSION_ID_A)


class ReadDashboardEnabledTest(unittest.TestCase):
    """RL10(docs/prps/hub-card-gate-and-run-list-reset.md §5.2) — read_dashboard_enabled 는
    파일·필드 없음, 읽기·파싱 실패, 값이 bool 이 아닌 모든 경로에서 켜짐(True)으로 넘어진다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_path = str(self.temp_dir / "repo")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_settings(self, text: str) -> Path:
        settings_dir = Path(self.project_path) / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.local.json"
        settings_path.write_text(text, encoding="utf-8")
        return settings_path

    def test_missing_file_is_enabled(self) -> None:
        self.assertTrue(hub_collect.read_dashboard_enabled(self.project_path))

    def test_empty_object_is_enabled(self) -> None:
        self._write_settings("{}")
        self.assertTrue(hub_collect.read_dashboard_enabled(self.project_path))

    def test_explicit_false_is_disabled(self) -> None:
        self._write_settings('{"dashboard_enabled": false}')
        self.assertFalse(hub_collect.read_dashboard_enabled(self.project_path))

    def test_string_value_is_enabled(self) -> None:
        """값이 bool 이 아니면(문자열 "false") 켜짐으로 넘어진다."""
        self._write_settings('{"dashboard_enabled": "false"}')
        self.assertTrue(hub_collect.read_dashboard_enabled(self.project_path))

    def test_broken_json_is_enabled(self) -> None:
        self._write_settings("{ not json")
        self.assertTrue(hub_collect.read_dashboard_enabled(self.project_path))

    def test_permission_error_is_enabled(self) -> None:
        settings_path = self._write_settings('{"dashboard_enabled": false}')
        settings_path.chmod(0o000)
        try:
            self.assertTrue(hub_collect.read_dashboard_enabled(self.project_path))
        finally:
            settings_path.chmod(0o644)


class Tier1SourceSelectionTest(unittest.TestCase):
    """U-14~U-16 — _read_tier1_for_root 가 루트·워크트리 후보 중 mtime 최신 승자를 고른다
    (S4·S7, 결정 WT6). P10(hub-session-tree-and-per-session-dashboards.md) — 세션별 파일들
    사이의 경쟁(결정 ST11). M2(dashboard-into-hub.md HD7)로 레거시 단일 파일 읽기가 폐기돼
    후보는 세션별 `.jsonl` 뿐이다."""

    ROOT_SESSION_ID = "f733cfcd-32eb-4339-9d99-e7375887e376"
    WORKTREE_SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.root = str(self.temp_dir / "repo")
        self.worktree = str(self.temp_dir / "repo" / ".claude" / "worktrees" / "w")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_session_dashboard(
        self, project_path: str, session_id: str, title: str, mtime_seconds: float
    ) -> None:
        dashboards_dir = Path(project_path) / ".claude" / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = dashboards_dir / f"{session_id}.jsonl"
        dashboard_path.write_text(_dashboard_jsonl(title), encoding="utf-8")
        os.utime(dashboard_path, (mtime_seconds, mtime_seconds))

    def test_u14_newer_worktree_dashboard_wins_and_carries_its_own_source_path(self) -> None:
        """S4 — 승자는 mtime 이 더 새로운 쪽이고, snapshot.source_path 가 그 디렉토리다."""
        self._write_session_dashboard(self.root, self.ROOT_SESSION_ID, "루트", mtime_seconds=1_000_000)
        self._write_session_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리", mtime_seconds=2_000_000)

        snapshot, session_snapshots, warnings = hub_collect._read_tier1_for_root((self.root, self.worktree))

        self.assertEqual(warnings, ())
        self.assertEqual(snapshot.title, "워크트리")
        self.assertEqual(snapshot.source_path, self.worktree)
        self.assertEqual(len(session_snapshots), 2)

    def test_u15_worktree_only_promotes_root_card_to_tier1(self) -> None:
        self._write_session_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리", mtime_seconds=1_000_000)

        snapshot, session_snapshots, warnings = hub_collect._read_tier1_for_root((self.root, self.worktree))

        self.assertEqual(warnings, ())
        self.assertEqual(snapshot.source_path, self.worktree)
        self.assertEqual(len(session_snapshots), 1)

    def test_u16_root_only_is_unchanged_from_before(self) -> None:
        """S7 — 워크트리가 없는 프로젝트는 오늘과 완전히 동일하게 source_path 가 루트다."""
        self._write_session_dashboard(self.root, self.ROOT_SESSION_ID, "루트", mtime_seconds=1_000_000)

        snapshot, session_snapshots, warnings = hub_collect._read_tier1_for_root((self.root,))

        self.assertEqual(warnings, ())
        self.assertEqual(snapshot.source_path, self.root)
        self.assertEqual(len(session_snapshots), 1)

    def test_p10_newer_session_file_wins_and_both_members_are_listed(self) -> None:
        """P10(S4·WT6 확장) — 서로 다른 두 세션 파일(루트·워크트리) 중 mtime 최신이 이기고,
        세션별 스냅샷 목록에는 두 멤버의 세션 파일이 모두 들어간다."""
        self._write_session_dashboard(self.root, self.ROOT_SESSION_ID, "루트 세션", mtime_seconds=1_000_000)
        self._write_session_dashboard(
            self.worktree, self.WORKTREE_SESSION_ID, "워크트리 세션", mtime_seconds=2_000_000
        )

        snapshot, session_snapshots, warnings = hub_collect._read_tier1_for_root((self.root, self.worktree))

        self.assertEqual(warnings, ())
        self.assertIsNotNone(snapshot.session_id)
        self.assertEqual(snapshot.session_id, self.WORKTREE_SESSION_ID)
        session_ids = {s.session_id for s in session_snapshots}
        self.assertEqual(session_ids, {self.ROOT_SESSION_ID, self.WORKTREE_SESSION_ID})


class CollectTier1SnapshotsTest(unittest.TestCase):
    """검수 1회차 M1 — `_collect_tier1_snapshots`(collect_snapshot 조립 루프)가 각 루트의
    멤버 경로 전체를 `_read_tier1_for_root` 에 그대로 넘기는지 직접 확인한다.

    이전에는 이 배선이 `collect_snapshot` 안에 있었는데, 이를 참조하는 테스트가 전부
    `_read_tier1_for_root` 자체를 `mock.patch` 로 우회해 이 조립 지점을 한 번도 실행하지
    않았다 — `_read_tier1_for_root(root, members_by_root[root])` → `_read_tier1_for_root(root,
    (root,))`(멤버 대신 루트만 넘김, 결함 A 완전 복원) 뮤테이션이 397 tests OK 로 통과했다.
    여기서는 `_read_tier1_for_root` 를 mock 으로 바꿔치기해 실제로 어떤 인자로 불렸는지
    직접 단언한다."""

    def test_full_member_tuple_is_forwarded_not_just_the_root(self) -> None:
        candidates_by_root = {"/repo": ("/repo", "/repo/.claude/worktrees/w")}
        with mock.patch.object(
            hub_collect, "_read_tier1_for_root", return_value=(None, (), ())
        ) as mocked_read:
            hub_collect._collect_tier1_snapshots(candidates_by_root)
        mocked_read.assert_called_once_with(("/repo", "/repo/.claude/worktrees/w"))

    def test_snapshot_and_warnings_are_collected_per_root(self) -> None:
        tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=1, source_path="/repo",
        )
        candidates_by_root = {"/repo": ("/repo",), "/other": ("/other",)}

        def _fake_read(member_paths):
            if member_paths == ("/repo",):
                return tier1, (), ()
            return None, (), (f"{member_paths[0]}: 경고",)

        with mock.patch.object(hub_collect, "_read_tier1_for_root", side_effect=_fake_read):
            tier1_by_path, session_dashboards_by_path, warnings = hub_collect._collect_tier1_snapshots(
                candidates_by_root
            )

        self.assertEqual(tier1_by_path, {"/repo": tier1})
        self.assertEqual(session_dashboards_by_path, {"/repo": (), "/other": ()})
        self.assertEqual(warnings, ("/other: 경고",))

    def test_p9_session_snapshots_are_forwarded_per_root(self) -> None:
        """P9/ST9 확장 — 세션별 스냅샷 튜플이 루트별로 그대로 전달된다(compose_project_views 의
        session_dashboards_by_path 입력이 된다)."""
        session_tier1 = hub_parse.Tier1Snapshot(
            title="t", subtitle="s", completed=1, total=2, percent=50, steps=(),
            matrix_done=None, impl_done=0, impl_total=0, updated_text="-",
            file_mtime_ms=1, source_path="/repo", session_id="s1",
        )
        candidates_by_root = {"/repo": ("/repo",)}
        with mock.patch.object(
            hub_collect, "_read_tier1_for_root", return_value=(session_tier1, (session_tier1,), ())
        ):
            _, session_dashboards_by_path, _ = hub_collect._collect_tier1_snapshots(candidates_by_root)
        self.assertEqual(session_dashboards_by_path, {"/repo": (session_tier1,)})


class RenderHubHtmlWorktreeFoldTest(unittest.TestCase):
    """U-21(S3) — 워크트리 세션이 있는 스냅샷을 렌더해도 #dzh-data 의 projects[].path 에
    워크트리 경로가 남지 않는다(워크트리는 별도 카드가 되지 않는다)."""

    BASE_TIME_MS = 1_786_000_000_000
    WORKTREE_PATH_MARKER = "/.claude/worktrees/"

    def test_u21_no_project_path_contains_the_worktree_marker(self) -> None:
        event = hub_session_facts.HookEvent(
            received_at_ms=self.BASE_TIME_MS, hook_event_name="UserPromptSubmit",
            session_id="s1", cwd="/repo/.claude/worktrees/w", source=None, reason=None,
            agent_id=None, agent_type=None,
        )
        sessions_by_path = hub_collect._group_sessions_by_project([event], ())
        views = hub_project.compose_project_views(
            tier1_by_path={}, sessions_by_path=sessions_by_path, tier3_last_activity_by_path={},
            now_ms=self.BASE_TIME_MS, stale_after_ms=30 * 60 * 1000,
        )
        snapshot = hub_model.HubSnapshot(
            collected_at_ms=self.BASE_TIME_MS, projects=views, unresolved_dir_names=(), warnings=(),
        )
        template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
        rendered = hub_model.render_hub_html(template, snapshot)
        payload = rendered.split('id="dzh-data">', 1)[1].rsplit("</script>", 1)[0]
        parsed = json.loads(payload)
        worktree_paths = [
            project["path"] for project in parsed["projects"]
            if self.WORKTREE_PATH_MARKER in (project["path"] or "")
        ]
        self.assertEqual(worktree_paths, [])


class CollectSnapshotWorktreeTier1Test(unittest.TestCase):
    """U-22~U-26 — `collect_snapshot()` 을 이벤트 파일 입력부터 실행하는 유일한 티어 1
    테스트다(결정 WT20, docs/prps/hub-worktree-fold.md). 선례는
    `CollectSnapshotRateLimitIsolationTest`(:804-833) — 같은 방식으로 모듈 상수를 임시
    디렉토리로 바꾼다.

    이 클래스가 재현하는 것은 2판이 고친 바로 그 결함이다(E11) — 세션의 `SessionFacts.cwd` 는
    창 안 최초 이벤트인 레포 루트에 고정되고, 워크트리 cwd 는 **이벤트에만** 남는다. 중간
    함수(`plan_tier1_candidates`·`_read_tier1_for_root` 등)에 손으로 입력을 넣는 테스트는
    이 이음매를 검증하지 못한다 — 1회차 구현이 정확히 그 방식으로 검수를 통과하고도 실환경
    확인(S8)에서 결함 A 를 남겼다.

    M2(dashboard-into-hub.md HD7)로 레거시 단일 파일(.claude/dashboard.html) 읽기가 폐기돼,
    `_write_dashboard` 는 세션별 `.jsonl` 을 쓴다 — 각 시나리오가 요구하는 위치(루트·워크트리·
    하위 디렉토리)마다 고유한 세션 ID 상수를 쓴다."""

    ROOT_SESSION_ID = "f733cfcd-32eb-4339-9d99-e7375887e376"
    WORKTREE_SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    SUBDIRECTORY_SESSION_ID = "12121212-3434-5656-7878-909090909090"
    ONE_HOUR_MS = 60 * 60 * 1000
    ONE_MINUTE_MS = 60 * 1000

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"      # 티어 3 격리 — 만들지 않으면 무동작
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        # 만들지 않는 경로로 격리한다 — 실제 ~/.claude/sessions 를 읽으면 이 클래스가 이 세션
        # 자신의 살아있는 레코드까지 주워 roster 가 "unknown" 이 아니게 돼(결정 LS7의 `unknown`
        # 폴백이 깨진다) 이 클래스가 전제하는 "오늘의 판정"이 흔들린다.
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"
        self.now_ms = int(time.time() * 1000)
        self.root = str(self.temp_dir / "repo")
        self.worktree = str(Path(self.root) / ".claude" / "worktrees" / "w")
        # /tmp·/private/tmp 를 ignore_globs 에서 뺀다 — tempfile.mkdtemp() 가 TMPDIR 을
        # 따르므로 환경에 따라 픽스처 전체가 무시 대상이 될 수 있다(U-11 과 같은 이유).
        # **/.claude/worktrees/** 는 반드시 남긴다 — fold-first 순서를 검증하는 대상이다.
        # show_usage_panel: false 는 _capture_for_snapshot 이 캡처 파일을 열지도 않게 한다
        # (hub_collect.py:383, 결정 U4) — 테스트가 사용자 홈의 캡처 파일에 의존하지 않는다.
        hub_collect.CONFIG_PATH.write_text(
            json.dumps({"ignore_globs": ["**/.claude/worktrees/**"], "show_usage_panel": False})
        )

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_dashboard(self, project_path: str, session_id: str, title: str, mtime_offset_ms: int) -> None:
        dashboards_dir = Path(project_path) / ".claude" / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = dashboards_dir / f"{session_id}.jsonl"
        dashboard_path.write_text(_dashboard_jsonl(title), encoding="utf-8")
        mtime_seconds = (self.now_ms + mtime_offset_ms) / 1000
        os.utime(dashboard_path, (mtime_seconds, mtime_seconds))

    def _write_events(self, lines: list[dict]) -> None:
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        today_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        with today_file.open("w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(json.dumps(line) + "\n")

    def _root_then_worktree_event_lines(self, first_offset_ms: int, second_offset_ms: int) -> list[dict]:
        """실패 시나리오(E11)를 그대로 재현하는 이벤트 두 줄 — 첫 이벤트는 레포 루트,
        둘째는 워크트리다. 이 두 줄이면 `SessionFacts.cwd == self.root` 이고 워크트리는
        `observed_cwds` 에만 남는다. 개정 전 코드에서는 이 입력으로 워크트리가 절대 티어 1
        후보가 되지 않는다."""
        return [
            {"t": self.now_ms + first_offset_ms, "e": "UserPromptSubmit", "s": "s1", "c": self.root},
            {"t": self.now_ms + second_offset_ms, "e": "UserPromptSubmit", "s": "s1", "c": self.worktree},
        ]

    def test_worktree_dashboard_wins_when_only_events_know_the_worktree(self) -> None:
        """U-22(S9) — 이번 결함의 정확한 재현. 뮤테이션 9(`facts.observed_cwds` →
        `(facts.cwd,)`) · 뮤테이션 13(`select_tier1_source` 의 `max` → `min`)을 넣으면 이
        테스트가 실패해야 한다."""
        self._write_dashboard(self.root, self.ROOT_SESSION_ID, "루트 작업", mtime_offset_ms=-24 * self.ONE_HOUR_MS)
        self._write_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리 작업", mtime_offset_ms=-10 * self.ONE_MINUTE_MS)
        self._write_events(
            self._root_then_worktree_event_lines(-2 * self.ONE_HOUR_MS, -30 * self.ONE_MINUTE_MS)
        )

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        self.assertEqual(snapshot.projects[0].path, self.root)
        self.assertEqual(snapshot.projects[0].tier, 1)
        self.assertEqual(snapshot.projects[0].tier1.title, "워크트리 작업")
        self.assertEqual(snapshot.projects[0].tier1.source_path, self.worktree)

    def test_root_dashboard_wins_when_it_is_newer(self) -> None:
        """U-23 — S9 의 대조군. mtime 관계만 뒤집어 결과가 양방향으로 실제로 움직이는
        테스트임을 보장한다(검수 2회차가 「결과를 줄이는 뮤테이션에만 반응 못 하는 단언」을
        잡았던 것과 같은 함정을 여기서 미리 방어한다)."""
        self._write_dashboard(self.root, self.ROOT_SESSION_ID, "루트 작업", mtime_offset_ms=-10 * self.ONE_MINUTE_MS)
        self._write_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리 작업", mtime_offset_ms=-24 * self.ONE_HOUR_MS)
        self._write_events(
            self._root_then_worktree_event_lines(-2 * self.ONE_HOUR_MS, -30 * self.ONE_MINUTE_MS)
        )

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(snapshot.projects[0].tier1.title, "루트 작업")
        self.assertEqual(snapshot.projects[0].tier1.source_path, self.root)

    def test_previous_task_label_turns_on_when_session_started_after_the_worktree_file(self) -> None:
        """U-24(S11 ON) — (a)안과 (c)안을 가르는 테스트다. `facts.cwd == source_path` 로
        되돌리면(뮤테이션 11) live 집합이 비어 `False` 가 된다. 세션의 마지막 이벤트를 최근
        (T-5m)으로 둬 상태가 `working` 으로 살아 있게 한다 — 그래야 세대 판정 집합에 들어간다."""
        self._write_dashboard(self.root, self.ROOT_SESSION_ID, "루트 작업", mtime_offset_ms=-24 * self.ONE_HOUR_MS)
        self._write_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리 작업", mtime_offset_ms=-2 * self.ONE_HOUR_MS)
        self._write_events(
            self._root_then_worktree_event_lines(-1 * self.ONE_HOUR_MS, -5 * self.ONE_MINUTE_MS)
        )

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertIs(snapshot.projects[0].tier1_is_previous_task, True)

    def test_previous_task_label_stays_off_when_the_live_session_predates_the_file(self) -> None:
        """U-25(S11 OFF) — 「우연히 꺼짐」을 통과로 인정하지 않는다.

        라벨이 꺼지는 근거가 「live 집합이 비어서」가 아니라 **실제 대소 비교**임을 보장한다:
        이 세션의 워크트리 경로가 `observed_cwds` 에 있고 상태가 `working` 이므로 판정 집합은
        비지 않으며, `False` 는 세션 시작(-2h)이 파일 mtime(-10m)보다 이르다는 비교에서 나온다.
        뮤테이션 9(`observed_cwds` → `(cwd,)`)를 넣으면 이 단언이 `True` 로 뒤집히는 것이 그
        증거다(검수 3회차 실측)."""
        self._write_dashboard(self.root, self.ROOT_SESSION_ID, "루트 작업", mtime_offset_ms=-24 * self.ONE_HOUR_MS)
        self._write_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리 작업", mtime_offset_ms=-10 * self.ONE_MINUTE_MS)
        self._write_events(
            self._root_then_worktree_event_lines(-2 * self.ONE_HOUR_MS, -5 * self.ONE_MINUTE_MS)
        )

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertIs(snapshot.projects[0].tier1_is_previous_task, False)

    def test_subdirectory_cwd_never_creates_a_second_card(self) -> None:
        """U-26(S12) — 앵커 규칙(결정 WT17). 이벤트에 프로젝트 **하위 디렉토리** cwd 가 있고
        그곳에 세션별 진행 기록이 있어도 카드는 하나다(E14 가 실데이터로 이 입력의 존재를
        확인했다). 뮤테이션 12(`root in anchors` 조건 삭제)를 넣으면 이 테스트가 실패해야 한다."""
        subdirectory = str(Path(self.root) / "sub")
        self._write_dashboard(self.root, self.ROOT_SESSION_ID, "루트 작업", mtime_offset_ms=-24 * self.ONE_HOUR_MS)
        self._write_dashboard(self.worktree, self.WORKTREE_SESSION_ID, "워크트리 작업", mtime_offset_ms=-10 * self.ONE_MINUTE_MS)
        self._write_dashboard(subdirectory, self.SUBDIRECTORY_SESSION_ID, "하위 디렉토리 작업", mtime_offset_ms=-1 * self.ONE_MINUTE_MS)
        lines = self._root_then_worktree_event_lines(-2 * self.ONE_HOUR_MS, -30 * self.ONE_MINUTE_MS)
        lines.append(
            {"t": self.now_ms - 20 * self.ONE_MINUTE_MS, "e": "UserPromptSubmit", "s": "s1", "c": subdirectory}
        )
        self._write_events(lines)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        self.assertEqual(snapshot.projects[0].path, self.root)
        self.assertTrue(all(not project.path.endswith("/sub") for project in snapshot.projects))

    def test_compose_project_views_session_dashboard_wiring_is_exercised_end_to_end(self) -> None:
        """A-M2(검수 2회차) — collect_snapshot() 종단에서 session_dashboards_by_path 가 실제로
        SessionView 까지 배선된다. compose_project_views 호출에서 그 인자를 삭제하거나 앞
        인자(model_by_session_id)와 순서를 바꾸면 이 테스트가 실패해야 한다 — 기존 548건의
        유닛 중 어느 것도 이 마지막 배선 홉을 실행하지 않았다(검수자 실측)."""
        session_id = "12345678-90ab-cdef-1234-567890abcdef"
        self._write_events(
            [{"t": self.now_ms - self.ONE_MINUTE_MS, "e": "UserPromptSubmit", "s": session_id, "c": self.root}]
        )
        dashboards_dir = Path(self.root) / ".claude" / "dashboards"
        dashboards_dir.mkdir(parents=True, exist_ok=True)
        (dashboards_dir / f"{session_id}.jsonl").write_text(
            _dashboard_jsonl("세션 자체 대시보드"), encoding="utf-8"
        )

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        session_view = snapshot.projects[0].sessions[0]
        self.assertIsNotNone(session_view.tier1)
        expected_file_path = hub_project.tier1_file_path(session_view.tier1)
        self.assertEqual(session_view.dashboard_key, hub_project.dashboard_file_key(expected_file_path))


class CollectSnapshotLiveSessionRosterTest(unittest.TestCase):
    """W1~W2 — docs/prps/hub-live-session-native-source.md §7.4. `collect_snapshot()` 을
    이벤트 파일 + 살아있는 세션 명부 입력부터 실행하는 배선(결정 LS2·LS4) 테스트다 —
    순수 층 테스트(test_hub_session.RosterReconciliationTest)로는 hub_collect→hub_project→
    hub_session 배선 누락을 잡지 못한다(CollectSnapshotWorktreeTier1Test 의 선례와 같은 이유)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"
        self.now_ms = int(time.time() * 1000)
        self.root = str(self.temp_dir / "repo")
        hub_collect.CONFIG_PATH.write_text(json.dumps({"show_usage_panel": False}))

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sessions_dir_points_to_the_real_host_directory(self) -> None:
        """검수 2회차 M2 — `SESSIONS_DIR` 의 유일한 구조 가드는 `tests/run.sh` 의 T25-217 인데
        `grep -qF` 라 주석에 옛 값을 남기고 실제 리터럴만 바꾸는 수법(검수 1회차 M3 가
        T25-216 에 썼던 것과 같음)이 통과한다(실측: `SESSIONS_DIR = Path.home() / ".claude" /
        "sessionz"` 로 바꿔도 T25 는 통과하고 798건 전부 OK). 다른 모듈 상수는 실사용 값을
        단언하는 단위 테스트가 최소 하나씩 있어 2중 방어인데 `SESSIONS_DIR` 만 1중이었다 —
        `setUp` 이 이미 보관해 둔 `original_sessions_dir`(교체 전 원본 값)로 이 테스트가
        그 분모가 된다. 변조 검출: `SESSIONS_DIR` 리터럴이 `.claude/sessions` 이외의 경로를
        가리키도록 바뀌면 이 단언이 깨진다."""
        self.assertEqual(self.original_sessions_dir, Path.home() / ".claude" / "sessions")

    def _write_events(self, session_id: str, lines: list[dict]) -> None:
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        today_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        with today_file.open("w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(json.dumps(line) + "\n")

    def test_w1_busy_roster_record_overrides_ended_turn_end_to_end(self) -> None:
        """W1 — 변조 검출: hub_collect→hub_project→hub_session 배선 중 어느 한 군데라도
        live_roster 전달이 빠지면(인자 누락) 이 세션이 idle 로 나와 실패한다."""
        session_id = "12345678-90ab-cdef-1234-567890abcdef"
        self._write_events(session_id, [
            {"t": self.now_ms - 60_000, "e": "UserPromptSubmit", "s": session_id, "c": self.root},
            {"t": self.now_ms - 1_000, "e": "Stop", "s": session_id, "c": self.root},
        ])
        # 실제로 살아 있는 pid(테스트 프로세스 자신)를 써야 한다 — 가짜 pid 는 _is_process_alive
        # 가 os.kill(pid, 0) 에서 ProcessLookupError 를 받아 죽었다고 정확히 판정해 버려,
        # 이 배선 테스트가 "레코드가 죽어서 제외됨"과 "배선이 빠져서 안 먹힘"을 구별하지 못한다.
        hub_collect.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        (hub_collect.SESSIONS_DIR / f"{os.getpid()}.json").write_text(
            json.dumps({"sessionId": session_id, "pid": os.getpid(), "status": "busy"}), encoding="utf-8"
        )

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        session_view = snapshot.projects[0].sessions[0]
        self.assertEqual(session_view.base_state, "working")

    def test_w2_missing_sessions_dir_matches_todays_snapshot_without_warnings(self) -> None:
        """W2 — 변조 검출: is_complete 기본값이 잘못되면(True 로 새면) 훅만으로 판단하던
        프로젝트가 갑자기 not_listed 취급을 받아 상태가 달라진다."""
        session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self._write_events(session_id, [
            {"t": self.now_ms - 60_000, "e": "UserPromptSubmit", "s": session_id, "c": self.root},
        ])
        # hub_collect.SESSIONS_DIR 를 가리키는 디렉터리 자체를 만들지 않는다 — 부재 경로.

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        session_view = snapshot.projects[0].sessions[0]
        self.assertEqual(session_view.base_state, "working")  # turn_state=="running" 그대로(오늘과 동일)
        self.assertEqual(snapshot.warnings, ())

    def test_w3_broken_roster_record_warning_is_merged_into_snapshot(self) -> None:
        """W3(검수 1회차 H5) — 변조 검출: _read_session_annotations 의 warnings 합치기에서
        *roster_warnings 를 빼면(병합 누락) 여기서 경고가 안 잡혀 실패한다. W2 는 "경고가
        없다"는 부정 단언만 해 분모가 없었다 — 이 테스트가 그 분모다(R6·R7·R9 가 만드는
        경고가 실제로 snapshot.warnings 까지 올라오는지 확인, 선례: R23 의 긍정 단언과
        같은 형태)."""
        hub_collect.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        (hub_collect.SESSIONS_DIR / "broken.json").write_text("not-json-at-all", encoding="utf-8")

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertTrue(any("살아있는 세션 명부" in warning for warning in snapshot.warnings))


class ReadSessionAnnotationsSubagentActivityTest(unittest.TestCase):
    """SL-C1 — docs/prps/hub-subagent-liveness-signal.md 결정 SL6. _read_session_annotations
    가 6번째 값으로 subagent_activity_by_agent_id(dict) 를 반환한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"

    def tearDown(self) -> None:
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_slc1_returns_seven_values_with_the_activity_dict_sixth_and_live_activity_last(self) -> None:
        """개정(docs/prps/hub-live-activity.md 결정 LA14) — 반환 끝에 `LiveActivity` 한 칸이 더해졌다. SL6 의
        생존 신호 dict 는 여전히 여섯 번째다."""
        result = hub_collect._read_session_annotations({}, True, 0)
        self.assertEqual(len(result), 7)
        self.assertIsInstance(result[5], dict)
        self.assertIsInstance(result[-1], hub_activity.LiveActivity)

    def test_la_cl1_read_live_activity_is_called_without_the_prompt_excerpt_gate(self) -> None:
        """LA-CL1(결정 LA13 — 함정 SL7) — 읽기 함수에 `record_prompt_excerpt` 를 넘기지 않는다. 끈 사용자에게도 같은 규칙이 돈다."""
        sentinel_activity = {"agt-sentinel": 123}
        sentinel_live_activity = hub_activity.LiveActivity({}, {})
        with mock.patch.object(
            hub_subagent_read, "read_unfinished_subagent_activity", return_value=sentinel_activity,
        ), mock.patch.object(
            hub_subagent_read, "read_live_activity", return_value=sentinel_live_activity,
        ) as read_live_activity:
            for record_prompt_excerpt in (True, False):
                with self.subTest(record_prompt_excerpt=record_prompt_excerpt):
                    result = hub_collect._read_session_annotations({}, record_prompt_excerpt, 777)

                    self.assertIs(result[-1], sentinel_live_activity)
                    call = read_live_activity.call_args
                    self.assertEqual(call.args, ({}, hub_collect.PROJECTS_DIR, 777, sentinel_activity))
                    self.assertEqual(call.kwargs, {})


class CollectSnapshotSubagentActivityWiringTest(unittest.TestCase):
    """SL-C2 — collect_snapshot 이 read_unfinished_subagent_activity 의 결과를
    compose_project_views 에 그대로 전달한다(mock.patch.object 로 인자 확인)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"
        self.now_ms = int(time.time() * 1000)
        hub_collect.CONFIG_PATH.write_text(json.dumps({"show_usage_panel": False}))

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_slc2_subagent_activity_flows_into_compose_project_views(self) -> None:
        """compose_project_views 는 subagent_meta_by_agent_id 바로 다음 위치 인자로
        subagent_activity_by_agent_id 를 받는다(hub_project.py 참고) — 값만 모아 assertIn
        하면 이 둘이 서로 뒤바뀌어 전달돼도 통과한다(재검수 2회차 MEDIUM-1). 실제 호출의
        시그니처에 인자를 이름으로 묶어(inspect.signature().bind) 두 값이 각자의 자리에
        있는지 확인한다."""
        sentinel_meta = {"agt-meta-sentinel": "meta"}
        sentinel_activity = {"agt-activity-sentinel": 123}
        real_signature = inspect.signature(hub_project.compose_project_views)
        with mock.patch.object(
            hub_subagent_read, "read_unfinished_subagent_activity", return_value=sentinel_activity,
        ), mock.patch.object(
            hub_subagent_read, "read_subagent_metas", return_value=(sentinel_meta, ()),
        ), mock.patch.object(
            hub_project, "compose_project_views", return_value=(),
        ) as mock_compose:
            hub_collect.collect_snapshot(self.now_ms)
        bound_args = real_signature.bind(*mock_compose.call_args.args, **mock_compose.call_args.kwargs)
        self.assertEqual(bound_args.arguments["subagent_meta_by_agent_id"], sentinel_meta)
        self.assertEqual(bound_args.arguments["subagent_activity_by_agent_id"], sentinel_activity)


class CollectSnapshotLiveActivityWiringTest(unittest.TestCase):
    """LA-CL2(docs/prps/hub-live-activity.md 결정 LA14) — collect_snapshot 이 `now_ms` 를 보강 읽기에 넘기고, 그 결과(`LiveActivity`)를
    compose_project_views 의 `live_activity` 자리에 그대로 전달한다. 임시 경로 설정은 위 클래스의 setUp·tearDown 을 그대로 쓴다
    (상속하면 그 클래스의 시험이 두 번 돈다)."""

    setUp = CollectSnapshotSubagentActivityWiringTest.setUp
    tearDown = CollectSnapshotSubagentActivityWiringTest.tearDown

    def test_la_cl2_now_ms_and_the_result_flow_through(self) -> None:
        sentinel_live_activity = hub_activity.LiveActivity({}, {})
        real_signature = inspect.signature(hub_project.compose_project_views)
        with mock.patch.object(
            hub_subagent_read, "read_live_activity", return_value=sentinel_live_activity,
        ) as read_live_activity, mock.patch.object(
            hub_project, "compose_project_views", return_value=(),
        ) as mock_compose:
            hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(read_live_activity.call_args.args[2], self.now_ms)
        bound_args = real_signature.bind(*mock_compose.call_args.args, **mock_compose.call_args.kwargs)
        self.assertIs(bound_args.arguments["live_activity"], sentinel_live_activity)

    def _write_run_events_and_transcript(self, agent_ended: bool) -> str:
        """훅 이벤트(세션·서브에이전트 시작[·종료])와 그 실행의 기록(결과 없는 Bash 호출 하나)을 임시 경로에 쓴다."""
        root = str(self.temp_dir / "repo")
        session_id, agent_id = "e2e00000-0000-0000-0000-000000000001", "agt-e2e"
        events = [
            {"t": self.now_ms - 300_000, "e": "UserPromptSubmit", "s": session_id, "c": root},
            {"t": self.now_ms - 180_000, "e": "SubagentStart", "s": session_id, "c": root, "ai": agent_id, "at": "implementer"},
        ]
        if agent_ended:
            events.append({"t": self.now_ms - 60_000, "e": "SubagentStop", "s": session_id, "c": root, "ai": agent_id, "at": "implementer"})
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        events_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        events_file.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        transcript_dir = hub_collect.PROJECTS_DIR / hub_project.encode_project_dir_name(root) / session_id / "subagents"
        transcript_dir.mkdir(parents=True)
        pending_use = _use_line(self.now_ms - 30_000, "u-pending", "Bash")
        (transcript_dir / f"agent-{agent_id}.jsonl").write_bytes(_jsonl_bytes(pending_use))
        return session_id

    def test_the_real_pipeline_carries_a_running_runs_activity_into_the_snapshot(self) -> None:
        """이벤트 파일 + 실행 기록에서 시작하는 배선 시험 — 읽기 호출만 가짜로 바꾼 위 시험으로는 읽은 값이 실제로 뷰까지 가는지 모른다."""
        self._write_run_events_and_transcript(agent_ended=False)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        run = snapshot.projects[0].sessions[0].agent_runs[0]
        self.assertTrue(run.is_running)
        self.assertEqual((run.activity.pending_count, run.activity.pending_tool_kind), (1, "run"))

    def test_the_real_pipeline_gives_an_ended_run_no_activity(self) -> None:
        self._write_run_events_and_transcript(agent_ended=True)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        run = snapshot.projects[0].sessions[0].agent_runs[0]
        self.assertFalse(run.is_running)
        self.assertIsNone(run.activity)


class CollectSnapshotSessionCostWiringTest(unittest.TestCase):
    """⑨(docs/prps/harness-benchmark-adoption.md §10-1) — collect_snapshot 이 세션 비용 캡처를 읽어 세션 뷰까지 싣고,
    보관 기간이 지난 캡처 파일은 지운다. 임시 경로 설정은 위 클래스의 setUp·tearDown 에 세션 비용 디렉터리 격리만 더해 쓴다."""

    SESSION_ID = "0a1b2c3d-4e5f-6789-abcd-ef0123456789"
    OLD_SESSION_ID = "11111111-2222-3333-4444-555555555555"
    COST = hub_usage.SessionCost(captured_at_ms=1_786_433_123_000, total_cost_cents=1284, api_duration_minutes=31, context_used_percent=62)
    BEYOND_RETENTION_DAYS = 8

    def setUp(self) -> None:
        CollectSnapshotSubagentActivityWiringTest.setUp(self)
        self.original_session_costs_dir = hub_session_cost.SESSION_COSTS_DIR
        hub_session_cost.SESSION_COSTS_DIR = self.temp_dir / "session_costs"

    def tearDown(self) -> None:
        hub_session_cost.SESSION_COSTS_DIR = self.original_session_costs_dir
        CollectSnapshotSubagentActivityWiringTest.tearDown(self)

    def _write_session_event(self) -> None:
        root = str(self.temp_dir / "repo")
        events = [{"t": self.now_ms - 60_000, "e": "UserPromptSubmit", "s": self.SESSION_ID, "c": root}]
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        events_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        events_file.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

    def test_the_captured_cost_flows_into_the_session_view(self) -> None:
        self._write_session_event()
        hub_session_cost.write_session_cost(self.SESSION_ID, self.COST)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(snapshot.projects[0].sessions[0].session_cost, self.COST)

    def test_a_session_without_a_capture_has_no_cost(self) -> None:
        self._write_session_event()

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertIsNone(snapshot.projects[0].sessions[0].session_cost)

    def test_captures_older_than_the_event_retention_are_pruned(self) -> None:
        self._write_session_event()
        hub_session_cost.write_session_cost(self.SESSION_ID, self.COST)
        hub_session_cost.write_session_cost(self.OLD_SESSION_ID, self.COST)
        old_file = hub_session_cost.SESSION_COSTS_DIR / f"{self.OLD_SESSION_ID}.json"
        old_seconds = self.now_ms / 1000 - self.BEYOND_RETENTION_DAYS * 24 * 60 * 60
        os.utime(old_file, (old_seconds, old_seconds))

        hub_collect.collect_snapshot(self.now_ms)

        self.assertFalse(old_file.exists())
        self.assertTrue((hub_session_cost.SESSION_COSTS_DIR / f"{self.SESSION_ID}.json").exists())


class ReadRecentEventsFailureIsolationTest(unittest.TestCase):
    """검수 M7 — collect 파이프라인은 이벤트 파일 하나의 실패로 전체가 죽지 않는다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir
        self.now_ms = int(time.time() * 1000)

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        for path in self.temp_dir.glob("*"):
            path.chmod(0o644)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _today_file(self) -> Path:
        today = hub_collect._date_string(self.now_ms)
        return self.temp_dir / f"{today}.jsonl"

    def _yesterday_file(self) -> Path:
        yesterday = hub_collect._date_string(self.now_ms - hub_collect.MILLISECONDS_PER_DAY)
        return self.temp_dir / f"{yesterday}.jsonl"

    def test_permission_denied_file_is_skipped_with_warning(self) -> None:
        """실측 (1) — 이벤트 파일 권한 없음 → PermissionError 로 collect 전체가 죽지 않는다."""
        good_file = self._yesterday_file()
        good_file.write_text('{"t":1,"e":"Stop","s":"s1","c":"/repo"}\n')
        bad_file = self._today_file()
        bad_file.write_text('{"t":2,"e":"Stop","s":"s2","c":"/repo"}\n')
        bad_file.chmod(0o000)

        events, warnings = hub_collect.read_recent_events(self.now_ms)

        self.assertEqual([event.session_id for event in events], ["s1"])
        self.assertTrue(any("읽기 실패" in warning for warning in warnings))

    def test_invalid_utf8_tail_byte_does_not_abort_the_whole_file(self) -> None:
        """실측 (2) — 이벤트 파일 꼬리의 비UTF-8 1바이트(동시 append 찢김) → 그 줄만 탈락."""
        today_file = self._today_file()
        with open(today_file, "wb") as raw_file:
            raw_file.write(b'{"t":1,"e":"Stop","s":"s1","c":"/repo"}\n')
            raw_file.write(b'{"t":2,"e":"Stop","s":"s2","c":"/repo"\xff}\n')

        events, warnings = hub_collect.read_recent_events(self.now_ms)

        self.assertEqual([event.session_id for event in events], ["s1"])
        self.assertEqual(warnings, ())  # 디코딩 자체는 죽지 않는다 — errors="replace" 가 흡수한다

    def test_malformed_lines_are_skipped_without_raising(self) -> None:
        """실측 결함(hub_session_facts.parse_event_line, RI13 후속) — Infinity·5000자리 정수·깊은
        중첩·1e300 인 t 를 가진 줄은 버려지고, ai 가 리스트인 SubagentStart 줄은 agent_id 만
        None 으로 살아남는다. 어느 쪽도 read_recent_events·build_session_facts 를 예외로
        중단시키지 않는다."""
        good_line_1 = '{"t":1,"e":"UserPromptSubmit","s":"s1","c":"/repo"}'
        good_line_2 = '{"t":2,"e":"Stop","s":"s1","c":"/repo"}'
        degraded_subagent_line = (
            '{"t":3,"e":"SubagentStart","s":"s1","c":"/repo","ai":[1],"at":"implementer"}'
        )
        unparseable_lines = [
            '{"t":Infinity,"e":"Stop","s":"s2","c":"/repo"}',
            '{"t":' + ("9" * 5000) + ',"e":"Stop","s":"s2","c":"/repo"}',
            '{"t":1,"e":' + "[" * 5000 + "]" * 5000 + ',"s":"s2","c":"/repo"}',
            '{"t":1e300,"e":"Stop","s":"s2","c":"/repo"}',
        ]
        all_lines = [good_line_1, good_line_2, degraded_subagent_line, *unparseable_lines]
        self._today_file().write_text("\n".join(all_lines) + "\n")

        events, warnings = hub_collect.read_recent_events(self.now_ms)

        self.assertEqual(warnings, ())
        self.assertEqual([event.session_id for event in events], ["s1", "s1", "s1"])
        degraded_event = events[2]
        self.assertEqual(degraded_event.hook_event_name, "SubagentStart")
        self.assertIsNone(degraded_event.agent_id)
        facts_by_session = hub_session_facts.build_session_facts(events)
        self.assertEqual(facts_by_session["s1"].subagents[0].agent_id, "")


class ScanDirectoryFailureIsolationTest(unittest.TestCase):
    """검수 M7 — (3) config.roots 스캔 중 EACCES 로 스캔 전체가 죽지 않는다.

    `Path.exists()` 는 ENOENT 만 흡수하고 EACCES 는 그대로 올린다(macOS 실측) — 마커 탐침을
    try/except 로 감싸지 않으면 권한 없는 디렉토리 하나가 collect 전체를 중단시킨다.
    """

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.restricted_dir = self.temp_dir / "restricted"
        self.restricted_dir.mkdir()
        self.readable_project_dir = self.temp_dir / "readable_project"
        self.readable_project_dir.mkdir()
        (self.readable_project_dir / ".git").mkdir()
        self.restricted_dir.chmod(0o000)

    def tearDown(self) -> None:
        self.restricted_dir.chmod(0o755)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_eacces_on_marker_probe_is_skipped_not_raised(self) -> None:
        matches = hub_collect._scan_directory(self.temp_dir, remaining_depth=2)
        self.assertIn(str(self.readable_project_dir), matches)
        self.assertNotIn(str(self.restricted_dir), matches)


class WriteHubHtmlMissingTemplateTest(unittest.TestCase):
    """검수 M7 — (4) hub_template.html 부재 시 원시 FileNotFoundError 대신 HubCollectError."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_template_path = hub_collect.TEMPLATE_PATH
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_hub_html_path = hub_collect.HUB_HTML_PATH
        hub_collect.TEMPLATE_PATH = self.temp_dir / "missing_template.html"
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.HUB_HTML_PATH = self.temp_dir / "hub.html"

    def tearDown(self) -> None:
        hub_collect.TEMPLATE_PATH = self.original_template_path
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.HUB_HTML_PATH = self.original_hub_html_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_template_raises_hub_collect_error(self) -> None:
        with self.assertRaises(hub_collect.HubCollectError):
            hub_collect.write_hub_html(_minimal_snapshot(1))


class ReadTemplateStampTest(unittest.TestCase):
    """docs/prps/hub-ungated-poll-and-stale-tab-self-heal.md 결정 SH3·SH5 — 세대 스탬프는
    파일 바이트의 SHA-256 이라 내용이 같으면 항상 같고 한 바이트라도 바뀌면 달라진다(결정성).
    mtime 방식이었다면 이 결정성 자체가 성립하지 않는다(성공 기준 S5 이 막으려는 회귀)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_template_path = hub_collect.TEMPLATE_PATH
        hub_collect.TEMPLATE_PATH = self.temp_dir / "hub_template.html"

    def tearDown(self) -> None:
        hub_collect.TEMPLATE_PATH = self.original_template_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_same_content_yields_same_stamp(self) -> None:
        hub_collect.TEMPLATE_PATH.write_bytes(b"<html>hub</html>")
        first_read = hub_collect.read_template_stamp()
        second_read = hub_collect.read_template_stamp()
        self.assertEqual(first_read, second_read)
        self.assertEqual(len(first_read), hub_collect.TEMPLATE_STAMP_LENGTH)

    def test_same_content_rewritten_yields_same_stamp(self) -> None:
        """결정 SH3 이 mtime 방식을 기각한 바로 그 실패 모드 — `install.sh` 의 `cp` 는 내용이
        한 글자도 안 바뀐 재설치에도 mtime 을 현재 시각으로 갱신한다. 내용을 그대로 다시 쓴
        뒤에도 스탬프가 같아야 한다(성공 기준 S5). mtime 기반이었다면 이 단언이 깨진다."""
        content = b"<html>hub</html>"
        hub_collect.TEMPLATE_PATH.write_bytes(content)
        stamp_before_rewrite = hub_collect.read_template_stamp()
        time.sleep(0.01)
        hub_collect.TEMPLATE_PATH.write_bytes(content)   # 재설치 흉내 — 내용 동일, mtime 만 갱신
        stamp_after_rewrite = hub_collect.read_template_stamp()
        self.assertEqual(stamp_before_rewrite, stamp_after_rewrite)

    def test_one_byte_difference_yields_different_stamp(self) -> None:
        hub_collect.TEMPLATE_PATH.write_bytes(b"<html>hub</html>")
        stamp_before_edit = hub_collect.read_template_stamp()
        hub_collect.TEMPLATE_PATH.write_bytes(b"<html>hux</html>")
        stamp_after_edit = hub_collect.read_template_stamp()
        self.assertNotEqual(stamp_before_edit, stamp_after_edit)

    def test_missing_template_returns_empty_string_without_raising(self) -> None:
        """결정 SH5 — 예외를 올리면 "쓸 필요가 없는 사이클"까지 실패로 뒤집힌다. 보고 지점은
        write_hub_html 하나로 충분하다(WriteHubHtmlMissingTemplateTest 가 그쪽을 검증한다)."""
        self.assertEqual(hub_collect.read_template_stamp(), "")


class CollectFailureObservabilityTest(unittest.TestCase):
    """검수 M7 — 배경 spawn 은 stdout/stderr 가 무성음이라 실패를 파일로 남겨 관측 가능하게 한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_error_path = hub_collect.LAST_COLLECT_ERROR_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.LAST_COLLECT_ERROR_PATH = self.temp_dir / "last_collect_error.json"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.LAST_COLLECT_ERROR_PATH = self.original_error_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_then_clear_round_trip(self) -> None:
        hub_collect.record_collect_failure("템플릿 없음")
        recorded = hub_collect.read_last_collect_failure()
        self.assertEqual(recorded["reason"], "템플릿 없음")

        hub_collect.clear_collect_failure()
        self.assertIsNone(hub_collect.read_last_collect_failure())

    def test_no_failure_recorded_returns_none(self) -> None:
        self.assertIsNone(hub_collect.read_last_collect_failure())

    def test_record_collect_failure_never_raises_when_write_itself_fails(self) -> None:
        """검수 M2-2 — 1차 실패의 가장 흔한 원인(HUB_HOME 쓰기 불가)이 기록 자신에게도
        똑같이 영향을 준다. 이 함수가 그대로 예외를 던지면 상관 실패가 호출자(상주 서버의
        유지보수 티커, `_maintenance_loop`)의 예외 처리 범위를 뚫고 나가 스레드 전체를
        죽인다 — 그래서 기록 실패는 stderr 로만 남기고 절대 예외를 올리지 않는다."""
        with mock.patch.object(hub_atomic_write, "atomic_write_text", side_effect=OSError("디스크 가득 참")):
            try:
                hub_collect.record_collect_failure("원인 실패 사유")
            except OSError:
                self.fail("record_collect_failure 가 예외를 던졌다 — 절대 던지지 않아야 한다")


class RecordUsageApiFailureMessageTest(unittest.TestCase):
    """U-R8(N1, docs/prps/shell-hardening.md §8-3·§14 승인 3) — record_usage_api_failure 의
    payload 에 원어휘 키(reason)와 사람이 읽는 문장(message)이 함께 실리고, message 를
    생략하면(기존 호출부와의 하위 호환) 그 키 자체가 없다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_error_path = hub_collect.LAST_USAGE_API_ERROR_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.temp_dir / "last_usage_api_error.json"

    def tearDown(self) -> None:
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.LAST_USAGE_API_ERROR_PATH = self.original_error_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reason_and_message_both_present_when_message_given(self) -> None:
        hub_collect.record_usage_api_failure("tls_verify_failed", message="사용량 API 서버의 인증서를 확인할 수 없습니다")
        recorded = hub_collect.read_last_usage_api_failure()
        self.assertEqual(recorded["reason"], "tls_verify_failed")
        self.assertEqual(recorded["message"], "사용량 API 서버의 인증서를 확인할 수 없습니다")

    def test_message_key_absent_when_not_provided(self) -> None:
        """기존 호출부(테스트 포함)가 message 없이 부르던 형태와 하위 호환된다."""
        hub_collect.record_usage_api_failure("network_error")
        recorded = hub_collect.read_last_usage_api_failure()
        self.assertNotIn("message", recorded)


class CollectSuccessStampRoundTripTest(unittest.TestCase):
    """개정 2 — evaluate_collect_health 의 유일한 성공 시각 출처인 스탬프 파일의 왕복."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_server_state_read.HUB_HOME
        self.original_success_stamp_path = hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH
        hub_server_state_read.HUB_HOME = self.temp_dir
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.temp_dir / "last_collect_success"

    def tearDown(self) -> None:
        hub_server_state_read.HUB_HOME = self.original_hub_home
        hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH = self.original_success_stamp_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_touch_then_read_round_trip(self) -> None:
        hub_server_state_read.touch_collect_success_stamp()
        mtime_ms = hub_server_state_read.read_collect_success_stamp_mtime_ms()
        self.assertIsInstance(mtime_ms, int)

    def test_no_stamp_returns_none(self) -> None:
        self.assertIsNone(hub_server_state_read.read_collect_success_stamp_mtime_ms())

    def test_touch_advances_mtime_on_each_success(self) -> None:
        """§0.3 Minor 8 — `evaluate_collect_health` 는 "성공할 때마다 스탬프가 전진한다"에
        의존한다. 전진하지 않으면 한 번 실패한 뒤 그 실패의 `at_ms` 가 스탬프보다 영구히
        커서, 복구 후에도 `collect_health` 가 `failing` 에 갇힌다. `assertIsInstance` 만으로는
        `touch_collect_success_stamp` 를 "파일이 없을 때만 만든다"로 바꿔도 통과해 이 성질을
        지키지 못한다 — 여기서는 스탬프를 인위적으로 과거로 되돌린 뒤 다시 touch 해 mtime 이
        실제로 앞으로 나아가는지 확인한다."""
        backdate_seconds = 10
        hub_server_state_read.touch_collect_success_stamp()
        first_mtime_ms = hub_server_state_read.read_collect_success_stamp_mtime_ms()

        backdated_seconds = (first_mtime_ms / 1000) - backdate_seconds
        os.utime(hub_server_state_read.COLLECT_SUCCESS_STAMP_PATH, (backdated_seconds, backdated_seconds))
        backdated_mtime_ms = hub_server_state_read.read_collect_success_stamp_mtime_ms()

        hub_server_state_read.touch_collect_success_stamp()
        second_mtime_ms = hub_server_state_read.read_collect_success_stamp_mtime_ms()

        self.assertGreater(second_mtime_ms, backdated_mtime_ms)


class LoadConfigValidationTest(unittest.TestCase):
    """검수 m5 — 필드 타입이 안 맞으면 그 필드만 기본값으로 되돌리고 사유를 warnings 로 남긴다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_config_path = hub_collect.CONFIG_PATH
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"

    def tearDown(self) -> None:
        hub_collect.CONFIG_PATH = self.original_config_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_wrong_type_field_falls_back_to_default_with_warning(self) -> None:
        hub_collect.CONFIG_PATH.write_text(
            json.dumps({"scan_depth": "three", "stale_after_minutes": 45})
        )
        config, warnings = hub_collect.load_config()
        self.assertEqual(config.scan_depth, hub_model.HubConfig().scan_depth)
        self.assertEqual(config.stale_after_minutes, 45)
        self.assertTrue(any("scan_depth" in warning for warning in warnings))

    def test_no_config_file_returns_defaults_without_warnings(self) -> None:
        config, warnings = hub_collect.load_config()
        self.assertEqual(config, hub_model.HubConfig())
        self.assertEqual(warnings, ())

    def test_broken_json_returns_defaults_with_warning(self) -> None:
        hub_collect.CONFIG_PATH.write_text("{not valid json")
        config, warnings = hub_collect.load_config()
        self.assertEqual(config, hub_model.HubConfig())
        self.assertEqual(len(warnings), 1)


class CaptureForSnapshotTest(unittest.TestCase):
    """케이스 N30~N36 — _capture_for_snapshot 이 캡처 파일을 사이클당 1회만 읽어 사용률·
    리셋 시각을 고르는 반환 계약(docs/prps/hub-card-cleanup-and-usage-source.md §5.5 표)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        self.now_ms = 1786433123899

    def tearDown(self) -> None:
        for path in self.temp_dir.glob("*"):
            path.chmod(0o644)
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_capture(self, **overrides) -> None:
        payload = {
            "captured_at_ms": self.now_ms,
            "session_resets_at_ms": None,
            "weekly_resets_at_ms": None,
            "session_used_percent": None,
            "weekly_used_percent": None,
        }
        payload.update(overrides)
        hub_collect.RATE_LIMITS_PATH.write_text(json.dumps(payload))

    def test_n30_missing_capture_file_returns_none_pair_without_warnings(self) -> None:
        usage, resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertIsNone(usage)
        self.assertIsNone(resets)
        self.assertEqual(warnings, ())

    def test_n31_switch_off_never_reads_the_file(self) -> None:
        """검수 m6 과 같은 이유 — 래퍼가 아니라 I/O 경계(Path.read_text)에서 직접 확인한다."""
        self._write_capture(session_used_percent=23, weekly_used_percent=41)
        config = hub_model.HubConfig(show_usage_panel=False)
        with mock.patch.object(hub_collect.Path, "read_text") as mocked_read_text:
            usage, resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, config)
        self.assertIsNone(usage)
        self.assertIsNone(resets)
        self.assertEqual(warnings, ())
        mocked_read_text.assert_not_called()

    def test_n32_normal_new_style_capture_fills_both_usage_and_resets(self) -> None:
        self._write_capture(
            session_resets_at_ms=self.now_ms + 10_000, weekly_resets_at_ms=self.now_ms + 20_000,
            session_used_percent=10, weekly_used_percent=19,
        )
        usage, resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertEqual(
            usage, hub_usage.UsageSample(sampled_at_ms=self.now_ms, session_percent=10, weekly_percent=19)
        )
        self.assertEqual(
            resets,
            hub_usage.RateLimitResets(
                captured_at_ms=self.now_ms,
                session_resets_at_ms=self.now_ms + 10_000,
                weekly_resets_at_ms=self.now_ms + 20_000,
            ),
        )
        self.assertEqual(warnings, ())

    def test_n33_legacy_capture_without_percent_fills_resets_only(self) -> None:
        self._write_capture(session_resets_at_ms=self.now_ms + 10_000)
        usage, resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertIsNone(usage)
        self.assertIsNotNone(resets)
        self.assertEqual(warnings, ())

    def test_n34_six_hours_old_capture_marks_usage_stale_without_warnings(self) -> None:
        """R-B 개정 — 만료돼도 usage 는 숨겨지지 않고 살아남아 is_stale 로 표시된다."""
        six_hours_ms = 6 * 60 * 60 * 1000
        self._write_capture(
            captured_at_ms=self.now_ms - six_hours_ms, session_used_percent=10, weekly_used_percent=19
        )
        usage, _resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertIsNotNone(usage)
        self.assertTrue(usage.is_stale)
        self.assertEqual(warnings, ())

    def test_n35_session_window_rolled_over_marks_usage_stale_even_when_fresh(self) -> None:
        """결정 P5·EX2 개정 — 나이가 3시간뿐이어도 세션 리셋 시각이 지났으면 확실히 틀린
        값이라 is_stale 로 표시된다(숨기지는 않는다)."""
        self._write_capture(
            captured_at_ms=self.now_ms - 3 * 60 * 60 * 1000,
            session_resets_at_ms=self.now_ms - 60 * 60 * 1000,
            session_used_percent=10, weekly_used_percent=19,
        )
        usage, _resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertIsNotNone(usage)
        self.assertTrue(usage.is_stale)
        self.assertEqual(warnings, ())

    def test_u8_stale_usage_keeps_future_weekly_reset_row(self) -> None:
        """결정 EX8 — 만료 상태에서도 아직 지나지 않은 초기화 예정 시각은 그대로 실린다."""
        six_hours_ms = 6 * 60 * 60 * 1000
        weekly_reset_future_ms = self.now_ms + 3 * 24 * 60 * 60 * 1000
        self._write_capture(
            captured_at_ms=self.now_ms - six_hours_ms,
            weekly_resets_at_ms=weekly_reset_future_ms,
            session_used_percent=10, weekly_used_percent=19,
        )
        usage, resets, _warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertIsNotNone(usage)
        self.assertTrue(usage.is_stale)
        self.assertIsNotNone(resets)
        self.assertEqual(resets.weekly_resets_at_ms, weekly_reset_future_ms)

    def test_n36_broken_capture_file_returns_none_pair_with_exactly_one_warning(self) -> None:
        """GOTCHA 5 회귀 — 캡처 파일을 사이클당 1회만 읽으므로 경고가 2건으로 중복되지 않는다."""
        hub_collect.RATE_LIMITS_PATH.write_text("{not valid json")
        usage, resets, warnings = hub_collect._capture_for_snapshot(self.now_ms, hub_model.HubConfig())
        self.assertIsNone(usage)
        self.assertIsNone(resets)
        self.assertEqual(len(warnings), 1)

    def test_n43_truncated_multibyte_capture_does_not_raise(self) -> None:
        """§17 발견 1 회귀 — 찢긴 멀티바이트 읽기가 UnicodeDecodeError 로 except OSError 를
        뚫지 않는다(read_latest_usage_sample 의 검수 M1 선례와 같은 문제, errors="replace" 로 흡수)."""
        truncated_bytes = b'{"captured_at_ms":1,"session_used_percent":' + b"\xed\xa0"
        hub_collect.RATE_LIMITS_PATH.write_bytes(truncated_bytes)
        try:
            capture, warnings = hub_collect.read_rate_limit_capture()
        except UnicodeDecodeError:
            self.fail("read_rate_limit_capture 가 UnicodeDecodeError 를 던졌다 — 절대 던지지 않아야 한다")
        self.assertIsNone(capture)
        self.assertEqual(len(warnings), 1)


class SnapshotContentKeyStaleTransitionTest(unittest.TestCase):
    """U9 — is_stale 만 다른 두 HubSnapshot 의 snapshot_content_key 가 서로 다르다(결정 EX4 의
    기계적 고정). 이 성질이 없으면 신선→만료 전이가 일어나도 hub.html 이 다시 쓰이지 않아
    화면이 스스로 "조회되지 않음"으로 바뀌지 않는 회귀를 아무도 못 잡는다."""

    def _snapshot(self, is_stale: bool) -> hub_model.HubSnapshot:
        usage = hub_usage.UsageSample(
            sampled_at_ms=1786433123899, session_percent=10, weekly_percent=19, is_stale=is_stale
        )
        return hub_model.HubSnapshot(
            collected_at_ms=1786433123899, projects=(), unresolved_dir_names=(), warnings=(), usage=usage
        )

    def test_u9_stale_transition_changes_content_key(self) -> None:
        fresh_key = hub_model.snapshot_content_key(self._snapshot(is_stale=False))
        stale_key = hub_model.snapshot_content_key(self._snapshot(is_stale=True))
        self.assertNotEqual(fresh_key, stale_key)


class RateLimitCaptureTest(unittest.TestCase):
    """케이스 R19~R20·R23b — read/write_rate_limit_capture 의 I/O 반환 계약(신형 5필드).
    스위치·만료·롤오버 시나리오는 CaptureForSnapshotTest(N30~N36)로 옮겼다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_hub_home = hub_collect.HUB_HOME
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        hub_collect.HUB_HOME = self.temp_dir
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        self.now_ms = 1786433123899

    def tearDown(self) -> None:
        for path in self.temp_dir.glob("*"):
            path.chmod(0o644)
        hub_collect.HUB_HOME = self.original_hub_home
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _capture(
        self, session_resets_at_ms=None, weekly_resets_at_ms=None,
        session_used_percent=None, weekly_used_percent=None,
    ) -> hub_usage.RateLimitCapture:
        return hub_usage.RateLimitCapture(
            captured_at_ms=self.now_ms,
            session_resets_at_ms=session_resets_at_ms,
            weekly_resets_at_ms=weekly_resets_at_ms,
            session_used_percent=session_used_percent,
            weekly_used_percent=weekly_used_percent,
        )

    def test_r19_missing_capture_file_returns_none_without_warnings(self) -> None:
        capture, warnings = hub_collect.read_rate_limit_capture()
        self.assertIsNone(capture)
        self.assertEqual(warnings, ())

    def test_r20_broken_json_returns_none_with_one_warning(self) -> None:
        hub_collect.RATE_LIMITS_PATH.write_text("{not valid json")
        capture, warnings = hub_collect.read_rate_limit_capture()
        self.assertIsNone(capture)
        self.assertEqual(len(warnings), 1)

    def test_r20_unreadable_file_returns_none_with_one_warning(self) -> None:
        hub_collect.write_rate_limit_capture(self._capture(session_resets_at_ms=self.now_ms + 10_000))
        hub_collect.RATE_LIMITS_PATH.chmod(0o000)
        capture, warnings = hub_collect.read_rate_limit_capture()
        self.assertIsNone(capture)
        self.assertEqual(len(warnings), 1)

    def test_r23b_write_then_read_round_trip_is_atomic(self) -> None:
        original = self._capture(
            session_resets_at_ms=self.now_ms + 10_000, weekly_resets_at_ms=self.now_ms + 20_000,
            session_used_percent=23, weekly_used_percent=41,
        )
        hub_collect.write_rate_limit_capture(original)
        capture, warnings = hub_collect.read_rate_limit_capture()
        self.assertEqual(capture, original)
        self.assertEqual(warnings, ())
        leftover = list(self.temp_dir.glob("rate_limits.json.*.tmp"))
        self.assertEqual(leftover, [])


class CollectSnapshotRateLimitIsolationTest(unittest.TestCase):
    """케이스 R23·N37 — 캡처 파일 계약 불일치가 collect_snapshot() 전체를 죽이지 않는다
    (실패 격리 회귀 방지)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"  # 만들지 않는다 — 실제 ~/.claude/sessions 격리
        hub_collect.RATE_LIMITS_PATH.write_text("{not valid json")

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_r23_broken_capture_does_not_abort_project_collection(self) -> None:
        snapshot = hub_collect.collect_snapshot(1786433123899)
        self.assertEqual(snapshot.projects, ())
        self.assertIsNone(snapshot.usage)
        self.assertIsNone(snapshot.rate_limit_resets)
        self.assertTrue(any("캡처 파일 계약 불일치" in warning for warning in snapshot.warnings))


class ReadSessionTailTest(unittest.TestCase):
    """§8.4 — read_session_tail·read_session_tails(요구 2,
    docs/prps/hub-tier1-clamp-fix-and-session-model.md 결정 MD1~MD10). 결정 PS1(개명)·PS7
    (record_prompt_excerpt:false 배선)은 docs/prps/hub-agent-runs-and-prompt-source.md."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        hub_collect.PROJECTS_DIR = self.temp_dir

    def tearDown(self) -> None:
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_transcript(self, cwd: str, session_id: str, content) -> Path:
        encoded_name = hub_project.encode_project_dir_name(cwd)
        project_dir = self.temp_dir / encoded_name
        project_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = project_dir / f"{session_id}.jsonl"
        payload = content.encode("utf-8") if isinstance(content, str) else content
        transcript_path.write_bytes(payload)
        return transcript_path

    def _assistant_line(self, model: str, effort: str = "xhigh") -> str:
        return json.dumps({"type": "assistant", "message": {"model": model}, "effort": effort})

    def _last_prompt_line(self, last_prompt: str) -> str:
        return json.dumps({"type": "last-prompt", "lastPrompt": last_prompt})

    def _session_facts(self, session_id: str, cwd: str) -> hub_session_facts.SessionFacts:
        return hub_session_facts.SessionFacts(
            session_id=session_id, cwd=cwd, observed_cwds=(cwd,), started_at_ms=0,
            last_event_at_ms=0, last_event_name="Stop", turn_state="ended",
            ended_at_ms=None, subagents=(),
        )

    def test_transcript_found_returns_value(self) -> None:
        self._write_transcript("/repo/a", "sess-1", self._assistant_line("claude-opus-5"))
        tail = hub_collect.read_session_tail("sess-1", ("/repo/a",))
        self.assertIsNotNone(tail)
        self.assertEqual(tail.model.model_label, "Opus 5")

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(hub_collect.read_session_tail("sess-missing", ("/repo/a",)))

    def test_transcript_in_host_folder_is_found_for_underscore_path(self) -> None:
        """N1(docs/prps/hub-agent-title-and-excerpt-freshness.md §16) — 밑줄 든 경로의 transcript 는
        호스트가 `_` 를 `-` 로 바꾼 폴더에 있다. 폴더 이름을 리터럴로 적는다 — _write_transcript 는
        같은 함수로 폴더를 만들어 순환한다."""
        host_folder = self.temp_dir / "-Users-dev-works-notebook-wiki-NotebookWiki"
        host_folder.mkdir()
        (host_folder / "sess-1.jsonl").write_text(self._assistant_line("claude-opus-5"), encoding="utf-8")
        tail = hub_collect.read_session_tail("sess-1", ("/Users/dev/works/notebook_wiki/NotebookWiki",))
        self.assertIsNotNone(tail)
        self.assertEqual(tail.model.model_label, "Opus 5")

    def test_second_observed_cwd_is_found_for_worktree(self) -> None:
        """결정 MD2 — 첫 cwd(레포 루트)에는 파일이 없고 두 번째(워크트리)에 있으면 찾아낸다."""
        self._write_transcript("/repo/worktree", "sess-1", self._assistant_line("claude-fable-5"))
        tail = hub_collect.read_session_tail("sess-1", ("/repo/root", "/repo/worktree"))
        self.assertIsNotNone(tail)
        self.assertEqual(tail.model.model_label, "Fable 5")

    def test_first_existing_file_wins_even_without_a_valid_model(self) -> None:
        """E14 — "먼저 존재하는 것을 쓴다"는 결정적이다. 그 파일의 꼬리에 유효한 값이
        없어도(§3.4 절차 5, 상한이 곧 예산이다) 다음 후보로 넘어가지 않는다."""
        self._write_transcript("/repo/first", "sess-1", json.dumps({"type": "user"}))
        self._write_transcript("/repo/second", "sess-1", self._assistant_line("claude-opus-5"))
        tail = hub_collect.read_session_tail("sess-1", ("/repo/first", "/repo/second"))
        self.assertIsNone(tail.model)

    def test_oversized_file_seeks_and_reads_exactly_tail_bytes(self) -> None:
        """파일 크기 > 128KiB — seek 로 꼬리만 읽는다. 읽은 바이트 수를 직접 검증한다."""
        content = "a" * (hub_transcript.TRANSCRIPT_TAIL_BYTES + 5000)
        transcript_path = self._write_transcript("/repo/a", "sess-1", content)
        tail_text = hub_collect._read_transcript_tail(transcript_path)
        self.assertEqual(len(tail_text.encode("utf-8")), hub_transcript.TRANSCRIPT_TAIL_BYTES)

    def test_undersized_file_reads_from_start_without_seek_error(self) -> None:
        content = "a" * 100
        transcript_path = self._write_transcript("/repo/a", "sess-1", content)
        tail_text = hub_collect._read_transcript_tail(transcript_path)
        self.assertEqual(tail_text, content)

    def test_permission_denied_returns_none_without_raising(self) -> None:
        transcript_path = self._write_transcript("/repo/a", "sess-1", self._assistant_line("claude-opus-5"))
        transcript_path.chmod(0o000)
        try:
            tail = hub_collect.read_session_tail("sess-1", ("/repo/a",))
        finally:
            transcript_path.chmod(0o644)
        self.assertIsNone(tail)

    def test_torn_multibyte_first_line_is_absorbed_by_errors_replace(self) -> None:
        """GOTCHA 7 — errors="replace" 가 없으면 UnicodeDecodeError(ValueError 서브클래스)가
        except OSError 를 뚫는다(read_rate_limit_capture 의 검수 M1 과 같은 함정). 찢긴 첫
        줄은(꼬리 경계에서 흔하다) U+FFFD 로 대체돼 JSON 파싱에 실패하고 자연히 탈락한다."""
        torn_multibyte_prefix = "가".encode("utf-8")[:2]   # 3바이트 문자의 앞 2바이트만
        content_bytes = torn_multibyte_prefix + b"\n" + self._assistant_line("claude-opus-5").encode("utf-8")
        self._write_transcript("/repo/a", "sess-1", content_bytes)
        tail = hub_collect.read_session_tail("sess-1", ("/repo/a",))
        self.assertIsNotNone(tail)
        self.assertEqual(tail.model.model_label, "Opus 5")

    def test_read_session_tails_omits_sessions_without_a_value(self) -> None:
        self._write_transcript("/repo/a", "sess-with-model", self._assistant_line("claude-opus-5"))
        sessions_by_path = {
            "/repo/a": (
                self._session_facts("sess-with-model", "/repo/a"),
                self._session_facts("sess-without-model", "/repo/a"),
            )
        }
        tails = hub_collect.read_session_tails(sessions_by_path, record_prompt_excerpt=True)
        self.assertEqual(set(tails), {"sess-with-model"})
        self.assertEqual(tails["sess-with-model"].model.model_label, "Opus 5")

    def test_last_prompt_is_carried_when_record_prompt_excerpt_is_true(self) -> None:
        self._write_transcript("/repo/a", "sess-1", self._last_prompt_line("마지막 프롬프트"))
        sessions_by_path = {"/repo/a": (self._session_facts("sess-1", "/repo/a"),)}
        tails = hub_collect.read_session_tails(sessions_by_path, record_prompt_excerpt=True)
        self.assertEqual(tails["sess-1"].last_prompt, "마지막 프롬프트")

    def test_record_prompt_excerpt_false_drops_last_prompt_but_keeps_model(self) -> None:
        """결정 PS7 — false 일 때도 모델 표시를 위한 꼬리 읽기 자체는 계속된다. 버려지는
        것은 last_prompt 뿐이다(파일은 읽되 값을 안 싣는다)."""
        tail_text = "\n".join([
            self._assistant_line("claude-opus-5"), self._last_prompt_line("숨겨져야 하는 프롬프트"),
        ])
        self._write_transcript("/repo/a", "sess-1", tail_text)
        sessions_by_path = {"/repo/a": (self._session_facts("sess-1", "/repo/a"),)}
        tails = hub_collect.read_session_tails(sessions_by_path, record_prompt_excerpt=False)
        self.assertIsNone(tails["sess-1"].last_prompt)
        self.assertEqual(tails["sess-1"].model.model_label, "Opus 5")

    def test_record_prompt_excerpt_false_also_drops_a_value_derived_from_a_human_line(self) -> None:
        """결정 TF5(C1) — 사람 프롬프트 줄에서 유도한 값도 last_prompt 이므로 같은 스위치로 버려진다. 꼬리에 사람 줄만 있는
        기록으로, 스위치를 켜면 값이 나오는 것을 함께 확인해 부정 단언이 공허하지 않게 한다."""
        human_line = json.dumps({
            "type": "user", "origin": {"kind": "human"},
            "message": {"role": "user", "content": "방금 입력한 합성 프롬프트"},
        })
        self._write_transcript("/repo/a", "sess-1", human_line)
        sessions_by_path = {"/repo/a": (self._session_facts("sess-1", "/repo/a"),)}

        tails_with_excerpt = hub_collect.read_session_tails(sessions_by_path, record_prompt_excerpt=True)
        tails_without_excerpt = hub_collect.read_session_tails(sessions_by_path, record_prompt_excerpt=False)

        self.assertEqual(tails_with_excerpt["sess-1"].last_prompt, "방금 입력한 합성 프롬프트")
        self.assertIsNone(tails_without_excerpt["sess-1"].last_prompt)


class CollectSnapshotWorkflowIntegrationTest(unittest.TestCase):
    """§11 「collect_snapshot 통합」 — 이벤트 파일 입력부터 실행해, 워크플로우가 있는 세션의
    뷰에 실제로 값이 실리는지 확인한다(선례: CollectSnapshotWorktreeTier1Test)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"  # 만들지 않는다 — 실제 ~/.claude/sessions 격리
        self.now_ms = int(time.time() * 1000)
        self.repo = str(self.temp_dir / "repo")
        # /tmp·/private/tmp 를 ignore_globs 에서 뺀다 — tempfile.mkdtemp() 가 TMPDIR 을
        # 따르므로 격리 TMPDIR 환경(예: /private/tmp 아래)에서는 self.repo 자신이 기본
        # ignore_globs 의 `/private/tmp/**` 에 걸려 세션이 통째로 사라진다(U-11 과 같은 이유,
        # 그 무시 패턴 자체는 의도된 프로덕션 동작이다 — docs/prps/hub-dashboard.md 의 노이즈
        # 필터 논거).
        # `**/.claude/worktrees/**` 는 이 클래스가 워크트리 폴딩을 검증하지 않아 없어도 되지만
        # 자매 클래스와의 스타일 일관성을 위해 남긴다. 두 클래스에 같은 override 블록이 생겼는데
        # 공용 헬퍼로 뽑지 않았다 — 자매 쪽은 그 glob 을 남기는 이유가 달라(폴딩 순서 검증)
        # 파라미터화가 필요하고, 지금은 override 가 한 줄이라 추출 이득이 작다. 다만 이 중복이
        # 실제 비용을 냈다: 4회차 검수에서 문자열 치환 기반 되돌리기가 엉뚱한 클래스를 건드렸다.
        # §18 이관 12 — CollectSnapshotWorktreeTier1Test:644-651 의 선례를 그대로 따른다).
        # show_usage_panel: false — _capture_for_snapshot 이 캡처 파일을 열지 않게 한다(결정 U4).
        hub_collect.CONFIG_PATH.write_text(
            json.dumps({"ignore_globs": ["**/.claude/worktrees/**"], "show_usage_panel": False})
        )

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_events(self, session_id: str, cwd: str | None = None) -> None:
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        today_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        line = {"t": self.now_ms, "e": "UserPromptSubmit", "s": session_id,
                "c": cwd or self.repo}
        today_file.write_text(json.dumps(line) + "\n", encoding="utf-8")

    def _write_workflow_run(self, session_id: str) -> None:
        encoded_name = hub_project.encode_project_dir_name(self.repo)
        workflows_dir = hub_collect.PROJECTS_DIR / encoded_name / session_id / "workflows"
        workflows_dir.mkdir(parents=True)
        payload = {
            "runId": "wf_integration", "workflowName": "wf-integration", "status": "completed",
            "startTime": 1000,
            "workflowProgress": [{
                "type": "workflow_agent", "index": 1, "label": "구현",
                "phaseTitle": "Build", "state": "done",
                "promptPreview": "구현해줘", "resultPreview": "완료했습니다",
            }],
        }
        (workflows_dir / "wf_integration.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_session_view_carries_the_workflow_run(self) -> None:
        self._write_events("sess-1")
        self._write_workflow_run("sess-1")

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        session_view = snapshot.projects[0].sessions[0]
        self.assertIsNotNone(session_view.workflow)
        self.assertEqual(len(session_view.workflow.agents), 1)
        self.assertEqual(session_view.workflow.agents[0].label, "구현")

    def test_session_without_a_workflow_run_has_none(self) -> None:
        self._write_events("sess-1")

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertIsNone(snapshot.projects[0].sessions[0].workflow)

    def test_repo_path_under_private_tmp_is_not_silently_dropped(self) -> None:
        """§18 이관 12 회귀 — 격리 TMPDIR(예: /private/tmp 아래)에서 tempfile.mkdtemp() 가
        돌려주는 경로를 그대로 repo 로 쓰면 기본 ignore_globs 의 `/private/tmp/**` 에 걸려
        프로젝트가 조용히 사라진다(원래 재현된 결함, `bash tests/run.sh` 는 통과해도
        `TMPDIR=<격리 경로> python3 -m unittest ...` 만 깨졌었다). setUp 의 ignore_globs
        override 가 없으면 이 단언이 실패한다 — 실제 TMPDIR 환경과 무관하게 결정적으로
        재현하려고 경로 자체를 /private/tmp 아래로 하드코딩했다. 그 경로는 이벤트 JSON 의
        문자열 값으로만 쓰이고 실제 디렉토리는 만들지 않는다 — 정리할 것이 없고 실환경·다른
        테스트와 충돌하지도 않는다."""
        repo_under_private_tmp = "/private/tmp/coding-harness-regression-fixture/repo"
        self._write_events("sess-2", cwd=repo_under_private_tmp)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)


class CollectSnapshotExcerptWiringTest(unittest.TestCase):
    """요구 ②(docs/prps/hub-agent-title-and-excerpt-freshness.md 결정 TF1) — `collect_snapshot()` 을 이벤트 파일 +
    transcript 입력부터 실행해, 꼬리에서 읽은 발췌가 세션 뷰의 task_excerpt 까지 배선되는지 확인한다(선례:
    CollectSnapshotInterruptionWiringTest — 배선 한 군데 누락은 순수 층 테스트(H1)로 못 잡는다). setUp 은 그 선례와
    같은 격리 블록이다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"  # 만들지 않는다 — roster unknown 격리
        self.now_ms = int(time.time() * 1000)
        self.repo = str(self.temp_dir / "repo")
        hub_collect.CONFIG_PATH.write_text(
            json.dumps({"ignore_globs": ["**/.claude/worktrees/**"], "show_usage_panel": False})
        )

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_prompt_submit_event(self, session_id: str) -> None:
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        today_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        line = {"t": self.now_ms, "e": "UserPromptSubmit", "s": session_id, "c": self.repo}
        today_file.write_text(json.dumps(line) + "\n", encoding="utf-8")

    def _write_transcript(self, session_id: str, transcript_lines: list[str]) -> None:
        project_dir = hub_collect.PROJECTS_DIR / hub_project.encode_project_dir_name(self.repo)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / f"{session_id}.jsonl").write_text("\n".join(transcript_lines) + "\n", encoding="utf-8")

    def test_session_view_excerpt_is_the_human_prompt_typed_after_the_last_prompt_line(self) -> None:
        """호스트가 last-prompt 를 아직 다시 적지 않은 사이에도, 이벤트 파일 입력부터 실행한 스냅샷의 세션 뷰 발췌가 방금
        입력한 프롬프트 줄의 값이다 — 꼬리 읽기 → 세션 뷰 task_excerpt 배선 한 군데 누락을 잡는다."""
        self._write_prompt_submit_event("sess-1")
        self._write_transcript("sess-1", [
            json.dumps({"type": "last-prompt", "lastPrompt": "옛 합성 프롬프트"}),
            json.dumps({
                "type": "user", "origin": {"kind": "human"},
                "message": {"role": "user", "content": "방금 입력한 합성 프롬프트"},
            }),
        ])

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(snapshot.projects[0].sessions[0].task_excerpt, "방금 입력한 합성 프롬프트")


class CollectSnapshotResumeTitleWiringTest(unittest.TestCase):
    """요구 ①(docs/prps/hub-agent-title-and-excerpt-freshness.md 결정 TF7·TF9·TF13) — `collect_snapshot()` 을 훅 이벤트 파일 +
    meta.json + 부모 transcript 입력부터 실행해, 재개된 서브에이전트의 제목·횟수가 세션 뷰의 agent_runs 까지 배선되는지 확인한다.
    수집 배선(hub_collect·hub_project)은 이번 변경에서 한 줄도 바뀌지 않는다(결정 TF13) — 그 주장을 이 테스트가 문다. setUp 은
    CollectSnapshotExcerptWiringTest 와 같은 격리 블록이다."""

    SESSION_ID = "sess-1"
    FIRST_TITLE = "첫 작업 이름"

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"  # 만들지 않는다 — roster unknown 격리
        self.now_ms = int(time.time() * 1000)
        self.repo = str(self.temp_dir / "repo")
        self._write_config({})
        self._write_resumed_run_events()
        self._write_meta_and_parent_transcript()

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_config(self, overrides: dict) -> None:
        config = {"ignore_globs": ["**/.claude/worktrees/**"], "show_usage_panel": False, **overrides}
        hub_collect.CONFIG_PATH.write_text(json.dumps(config))

    def _write_resumed_run_events(self) -> None:
        """Start → Stop → Start(같은 agent_id) — 호스트가 SendMessage 로 재개한 실행의 훅 이벤트 모양."""
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        event_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        subagent_fields = {"s": self.SESSION_ID, "c": self.repo, "ai": RESUMED_AGENT_ID, "at": "code-reviewer"}
        events = [
            {"t": self.now_ms - 4000, "e": "UserPromptSubmit", "s": self.SESSION_ID, "c": self.repo},
            {"t": self.now_ms - 3000, "e": "SubagentStart", **subagent_fields},
            {"t": self.now_ms - 2000, "e": "SubagentStop", **subagent_fields},
            {"t": self.now_ms - 1000, "e": "SubagentStart", **subagent_fields},
        ]
        event_file.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")

    def _write_meta_and_parent_transcript(self) -> None:
        project_dir = hub_collect.PROJECTS_DIR / hub_project.encode_project_dir_name(self.repo)
        subagents_dir = project_dir / self.SESSION_ID / "subagents"
        subagents_dir.mkdir(parents=True, exist_ok=True)
        (subagents_dir / f"agent-{RESUMED_AGENT_ID}.meta.json").write_text(
            json.dumps({"agentType": "code-reviewer", "description": self.FIRST_TITLE, "model": "sonnet"}, ensure_ascii=False),
            encoding="utf-8",
        )
        transcript_lines = _resume_pair_lines("toolu_1", "지금 작업 이름")
        (project_dir / f"{self.SESSION_ID}.jsonl").write_text("\n".join(transcript_lines) + "\n", encoding="utf-8")

    def _the_run(self, snapshot):
        return snapshot.projects[0].sessions[0].agent_runs[0]

    def test_resumed_run_carries_the_latest_request_summary_and_the_hook_resume_count(self) -> None:
        run = self._the_run(hub_collect.collect_snapshot(self.now_ms))

        self.assertEqual(run.resume_title, "지금 작업 이름")
        self.assertEqual(run.resume_count, 1)
        self.assertEqual(run.title, self.FIRST_TITLE)   # title 의 뜻(meta.description)은 그대로 — 화면이 resume_title 을 먼저 고른다(M3)

    def test_record_prompt_excerpt_false_drops_the_resume_title_but_not_the_hook_count(self) -> None:
        """재개 요약은 사용자 프롬프트에서 파생된 자유 텍스트라 발췌와 같은 스위치로 꺼진다 — meta.json 도 함께 안 읽는다. 재개 횟수는
        훅 사실(숫자)이라 남는다."""
        self._write_config({"record_prompt_excerpt": False})

        run = self._the_run(hub_collect.collect_snapshot(self.now_ms))

        self.assertIsNone(run.resume_title)
        self.assertIsNone(run.title)
        self.assertEqual(run.resume_count, 1)


class CollectSnapshotInterruptionWiringTest(unittest.TestCase):
    """W1 — docs/prps/hub-rate-limit-interruption.md 결정 RI1. `collect_snapshot()` 을 이벤트
    파일 + transcript 오류 줄 입력부터 실행해, 세션 뷰까지 「한도 초과」가 배선되는지 확인한다
    (선례: CollectSnapshotWorkflowIntegrationTest — 배선 한 군데 누락은 순수 층 테스트로
    못 잡는다). 이 시나리오는 훅 StopFailure 없이(UserPromptSubmit 뿐) transcript 오류 줄
    만으로 판정이 서는 폴백 경로를 겨냥한다(RI1 의 (b)만 있는 경우)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"  # 만들지 않는다 — roster unknown 격리
        self.now_ms = int(time.time() * 1000)
        self.repo = str(self.temp_dir / "repo")
        hub_collect.CONFIG_PATH.write_text(
            json.dumps({"ignore_globs": ["**/.claude/worktrees/**"], "show_usage_panel": False})
        )

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_prompt_submit_event(self, session_id: str) -> None:
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        today_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        line = {"t": self.now_ms, "e": "UserPromptSubmit", "s": session_id, "c": self.repo}
        today_file.write_text(json.dumps(line) + "\n", encoding="utf-8")

    def _write_transcript_ending_in_rate_limit_error(self, session_id: str, resets_at_seconds: int) -> None:
        # 오류 시각은 now_ms 보다 반드시 뒤여야 한다 — effective_interruption 의 tail 유효
        # 조건(failed_at_ms >= last_prompt_at_ms)을 실제 실행 시각과 무관하게 결정적으로
        # 만족시키기 위해서다.
        error_timestamp = datetime.fromtimestamp(
            (self.now_ms + 1000) / 1000, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")
        encoded_name = hub_project.encode_project_dir_name(self.repo)
        project_dir = hub_collect.PROJECTS_DIR / encoded_name
        project_dir.mkdir(parents=True, exist_ok=True)
        error_line = {
            "type": "assistant", "isApiErrorMessage": True, "error": "rate_limit",
            "timestamp": error_timestamp,
            "quotaLimits": {"resetsAt": resets_at_seconds, "rateLimitType": "five_hour", "status": "rejected"},
            "message": {"model": "<synthetic>"},
        }
        (project_dir / f"{session_id}.jsonl").write_text(json.dumps(error_line) + "\n", encoding="utf-8")

    def test_w1_transcript_error_line_drives_session_state_to_interrupted(self) -> None:
        session_id = "9dbd335d-0000-0000-0000-000000000000"
        resets_at_seconds = int(self.now_ms / 1000) + 3600
        self._write_prompt_submit_event(session_id)
        self._write_transcript_ending_in_rate_limit_error(session_id, resets_at_seconds)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        session_view = snapshot.projects[0].sessions[0]
        self.assertEqual(session_view.state, "interrupted")
        self.assertIsNotNone(session_view.interruption)
        self.assertEqual(session_view.interruption.resets_at_ms, resets_at_seconds * 1000)


class CollectSnapshotBackgroundWiringTest(unittest.TestCase):
    """W1 — docs/prps/hub-subagent-background-pause.md 결정 BW2·BW9. `collect_snapshot()`
    을 이벤트 파일 입력부터 실행해, `bt`·`sw` 를 실은 Stop 줄이 세션 뷰의
    `state=="background"`·`background_wait`(정수 4개)까지 배선되는지 확인한다(배선 한
    군데 누락은 순수 층 테스트로 못 잡는다 — CollectSnapshotInterruptionWiringTest 와
    같은 선례)."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"  # 만들지 않는다 — roster unknown 격리
        self.now_ms = int(time.time() * 1000)
        self.repo = str(self.temp_dir / "repo")
        hub_collect.CONFIG_PATH.write_text(
            json.dumps({"ignore_globs": ["**/.claude/worktrees/**"], "show_usage_panel": False})
        )

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_stop_event_with_background_report(self, session_id: str, reported_at_ms: int) -> None:
        hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
        today_file = hub_collect.EVENTS_DIR / f"{hub_collect._date_string(self.now_ms)}.jsonl"
        line = {"t": reported_at_ms, "e": "Stop", "s": session_id, "c": self.repo, "bt": {"shell": 2}, "sw": 0}
        today_file.write_text(json.dumps(line) + "\n", encoding="utf-8")

    def test_w1_background_report_line_drives_session_state_to_background(self) -> None:
        session_id = "5a1e4b0c-0000-0000-0000-000000000000"
        reported_at_ms = self.now_ms - 10 * 60 * 1000   # 10분 전 — 상한(90분) 안
        self._write_stop_event_with_background_report(session_id, reported_at_ms)

        snapshot = hub_collect.collect_snapshot(self.now_ms)

        self.assertEqual(len(snapshot.projects), 1)
        session_view = snapshot.projects[0].sessions[0]
        self.assertEqual(session_view.state, "background")
        self.assertIsNotNone(session_view.background_wait)
        self.assertEqual(session_view.background_wait.since_ms, reported_at_ms)
        self.assertEqual(session_view.background_wait.until_ms, reported_at_ms + hub_session.BACKGROUND_WAIT_MAX_MS)
        self.assertEqual(session_view.background_wait.task_count, 2)
        self.assertEqual(session_view.background_wait.wakeup_count, 0)


class AccountInfoCollectTest(unittest.TestCase):
    """C1~C9 — docs/prps/hub-usage-panel-account.md §11.2. 계정 읽기(read_account_info)와
    패널 배선(_usage_panel_for_snapshot)·종단(collect_snapshot → render_hub_html).

    실제 이메일·조직 이름은 쓰지 않는다 — 합성 값과 센티넬만 쓴다. tearDown 은 경로를
    **패키지가 중화해 둔 값**으로 되돌린다(tests/hub/__init__.py, 결정 AC12) — 원래 실제
    경로로 되돌리면 뒤따르는 테스트가 실제 ~/.claude.json 을 읽는다."""

    SENTINEL_KEYS = (
        "accountUuid", "organizationUuid", "displayName", "fullName", "billingType", "seatTier",
        "organizationRole", "workspaceRole", "userRateLimitTier", "organizationRateLimitTier",
    )

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_events_dir = hub_collect.EVENTS_DIR
        self.original_projects_dir = hub_collect.PROJECTS_DIR
        self.original_config_path = hub_collect.CONFIG_PATH
        self.original_rate_limits_path = hub_collect.RATE_LIMITS_PATH
        self.original_sessions_dir = hub_collect.SESSIONS_DIR
        self.neutralized_account_path = hub_collect.CLAUDE_GLOBAL_CONFIG_PATH
        hub_collect.EVENTS_DIR = self.temp_dir / "events"
        hub_collect.PROJECTS_DIR = self.temp_dir / "projects"
        hub_collect.CONFIG_PATH = self.temp_dir / "config.json"
        hub_collect.RATE_LIMITS_PATH = self.temp_dir / "rate_limits.json"
        hub_collect.SESSIONS_DIR = self.temp_dir / "sessions"
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH = self.temp_dir / "claude.json"
        self.now_ms = 1786433123899

    def tearDown(self) -> None:
        hub_collect.EVENTS_DIR = self.original_events_dir
        hub_collect.PROJECTS_DIR = self.original_projects_dir
        hub_collect.CONFIG_PATH = self.original_config_path
        hub_collect.RATE_LIMITS_PATH = self.original_rate_limits_path
        hub_collect.SESSIONS_DIR = self.original_sessions_dir
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH = self.neutralized_account_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_capture(self, captured_at_ms: int | None = None) -> None:
        hub_collect.RATE_LIMITS_PATH.write_text(
            json.dumps(
                {
                    "captured_at_ms": self.now_ms if captured_at_ms is None else captured_at_ms,
                    "session_resets_at_ms": None,
                    "weekly_resets_at_ms": None,
                    "session_used_percent": 43,
                    "weekly_used_percent": 71,
                }
            )
        )

    def _write_account(self, **overrides: object) -> None:
        account = {
            "organizationType": "claude_team",
            "organizationName": "Example Labs",
            "emailAddress": "dev.user@example.com",
        }
        account.update(overrides)
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH.write_text(json.dumps({"oauthAccount": account}))

    def test_c1_missing_file_is_normal_absence_without_warning(self) -> None:
        self.assertEqual(hub_collect.read_account_info(), (None, ()))

    def test_c2_unreadable_path_warns_once_with_path_and_no_values(self) -> None:
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH = self.temp_dir   # 디렉터리 — 읽기 실패(OSError)
        info, warnings = hub_collect.read_account_info()
        self.assertIsNone(info)
        self.assertEqual(len(warnings), 1)
        self.assertIn(str(self.temp_dir), warnings[0])

    def test_c3_broken_json_warns_once_without_echoing_content(self) -> None:
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH.write_text("{SENTINEL-broken", encoding="utf-8")
        info, warnings = hub_collect.read_account_info()
        self.assertIsNone(info)
        self.assertEqual(len(warnings), 1)
        self.assertIn(str(hub_collect.CLAUDE_GLOBAL_CONFIG_PATH), warnings[0])
        self.assertNotIn("SENTINEL", warnings[0])

    def test_c3b_normal_file_returns_info_without_warning(self) -> None:
        self._write_account()
        info, warnings = hub_collect.read_account_info()
        self.assertEqual(info.email, "dev.user@example.com")
        self.assertEqual(info.plan_label, "Claude Team")
        self.assertEqual(warnings, ())

    def test_c4_account_switch_off_never_opens_the_file(self) -> None:
        self._write_capture()
        self._write_account()
        config = hub_model.HubConfig(show_account_info=False)
        with mock.patch.object(hub_collect, "read_account_info") as mocked_read:
            usage, _resets, account, _warnings = hub_collect._usage_panel_for_snapshot(self.now_ms, config)
        self.assertIsNotNone(usage)
        self.assertIsNone(account)
        mocked_read.assert_not_called()

    def test_c5_usage_panel_off_never_opens_the_account_file(self) -> None:
        self._write_capture()
        self._write_account()
        config = hub_model.HubConfig(show_usage_panel=False)
        with mock.patch.object(hub_collect, "read_account_info") as mocked_read:
            usage, _resets, account, _warnings = hub_collect._usage_panel_for_snapshot(self.now_ms, config)
        self.assertIsNone(usage)
        self.assertIsNone(account)
        mocked_read.assert_not_called()

    def test_c6_no_capture_never_opens_the_account_file(self) -> None:
        self._write_account()
        with mock.patch.object(hub_collect, "read_account_info") as mocked_read:
            usage, _resets, account, _warnings = hub_collect._usage_panel_for_snapshot(
                self.now_ms, hub_model.HubConfig()
            )
        self.assertIsNone(usage)
        self.assertIsNone(account)
        mocked_read.assert_not_called()

    def test_c7_stale_capture_still_carries_the_account(self) -> None:
        stale_ms = self.now_ms - hub_usage.USAGE_MAX_SAMPLE_AGE_MS - 1
        self._write_capture(captured_at_ms=stale_ms)
        self._write_account()
        usage, _resets, account, warnings = hub_collect._usage_panel_for_snapshot(
            self.now_ms, hub_model.HubConfig()
        )
        self.assertTrue(usage.is_stale)
        self.assertEqual(account.organization_name, "Example Labs")
        self.assertEqual(warnings, ())

    def test_c7b_account_warnings_are_appended_after_capture_warnings(self) -> None:
        self._write_capture()
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH.write_text("{broken", encoding="utf-8")
        usage, _resets, account, warnings = hub_collect._usage_panel_for_snapshot(
            self.now_ms, hub_model.HubConfig()
        )
        self.assertIsNotNone(usage)
        self.assertIsNone(account)
        self.assertEqual(len(warnings), 1)

    def test_c8_rendered_html_carries_only_the_three_allowed_values(self) -> None:
        self._write_capture()
        account = {key: f"SENTINEL-{key}" for key in self.SENTINEL_KEYS}
        account.update(
            organizationType="claude_team",
            organizationName="SENTINEL-organizationName",
            emailAddress="SENTINEL-emailAddress",
        )
        hub_collect.CLAUDE_GLOBAL_CONFIG_PATH.write_text(json.dumps({"oauthAccount": account}))

        snapshot = hub_collect.collect_snapshot(self.now_ms)
        template = '<script type="application/json" id="dzh-data"></script>'
        rendered = hub_model.render_hub_html(template, snapshot)

        self.assertIn("SENTINEL-emailAddress", rendered)
        self.assertIn("SENTINEL-organizationName", rendered)
        for key in self.SENTINEL_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(f"SENTINEL-{key}", rendered)

    def test_c9_content_key_is_stable_across_collection_times(self) -> None:
        self._write_capture()
        self._write_account()
        first = hub_collect.collect_snapshot(self.now_ms)
        second = hub_collect.collect_snapshot(self.now_ms + 5_000)
        self.assertEqual(hub_model.snapshot_content_key(first), hub_model.snapshot_content_key(second))
        self.assertIsNotNone(first.account)


if __name__ == "__main__":
    unittest.main()
