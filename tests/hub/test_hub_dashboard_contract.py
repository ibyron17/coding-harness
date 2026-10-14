"""hub_dashboard_log.py(생산자) ↔ hub_collect.read_session_dashboard_snapshots(소비자) 계약 테스트.

이전 판(1단계 이전 PRP audit-remediation AR8, 이후 dashboard-native-data-source DN3)은
렌더러 출력과 hub_parse 의 HTML 정규식 사이의 왕복을 고정했다 — 두 형식(렌더된 HTML ↔
DOM 정규식)이 서로 다른 코드가 만드는 계약이었기 때문이다. docs/prps/dashboard-into-hub.md
M2(HD5~HD8)에서 상태의 단일 출처가 JSONL 하나로 좁혀지며 그 계약 자체가 사라졌다 — 이제
생산자(기록기 hub_dashboard_log.py)가 실제로 쓴 파일을, 소비자(hub_collect.
read_session_dashboard_snapshots)가 그대로 읽어 Tier1Snapshot 필드가 기대와 같은지
대조한다. 같은 채널(.claude/dashboards/*.jsonl)의 양 끝을 잇는 계약이라는 점은 그대로다.
"""

import contextlib
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402
import hub_dashboard_log  # noqa: E402  (sys.path 조정 후 임포트)


class _ContractTestCase(unittest.TestCase):
    """생산자(기록기) 호출 → 소비자(hub_collect) 읽기 왕복의 공통 준비 — 샌드박스 cwd·HOME.
    실제 $HOME 은 건드리지 않는다(각 테스트가 tempfile 로 격리된 사본에서만 동작한다)."""

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

        env_patch = mock.patch.dict(
            os.environ, {"HOME": str(home_dir), "CLAUDE_CODE_SESSION_ID": self.SESSION_ID}
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)

    @staticmethod
    def _run(func, *args: object) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            func(*args)
        return buffer.getvalue().strip()

    def _collect_one(self):
        """수집이 정확히 스냅샷 1건을 읽었다고 단언하고 그 스냅샷을 돌려준다."""
        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(str(self._project_dir))
        self.assertEqual(warnings, ())
        self.assertEqual(len(snapshots), 1)
        return snapshots[0]


class StandardFlowRoundTripTest(_ContractTestCase):
    """init → design → approve → impl → pass 로 기록한 뒤 수집하면 4/4 완료로 읽힌다."""

    def test_full_flow_is_collected_as_complete(self) -> None:
        self._run(hub_dashboard_log.cmd_init, "전체 경로 완료", "설계|승인|구현|검수")
        for kind, summary in (
            ("design", "설계 완료"), ("approve", "승인 완료"), ("impl", "구현 완료"), ("pass", "검수 통과"),
        ):
            self.assertEqual(self._run(hub_dashboard_log.cmd_log, [kind, summary]), "OK")

        snapshot = self._collect_one()

        self.assertEqual(snapshot.title, "전체 경로 완료")
        self.assertEqual((snapshot.completed, snapshot.total, snapshot.percent), (4, 4, 100))
        self.assertTrue(all(step.state == "done" for step in snapshot.steps))
        self.assertEqual(snapshot.session_id, self.SESSION_ID)


class FailRegressionRoundTripTest(_ContractTestCase):
    """impl → fail 로 기록하면 구현이 active 로, 검수가 wait 로 읽히고 최근 요약이 상세로 남는다."""

    def test_fail_leaves_active_step_with_latest_summary_as_detail(self) -> None:
        self._run(hub_dashboard_log.cmd_init, "축약 경로", "구현|검수")
        self._run(hub_dashboard_log.cmd_log, ["impl", "1차 구현"])
        self._run(hub_dashboard_log.cmd_log, ["fail", "1차 검수 실패", "상세 이유"])

        snapshot = self._collect_one()

        self.assertEqual((snapshot.completed, snapshot.total), (0, 2))
        self.assertEqual(snapshot.steps[0].state, "active")
        self.assertEqual(snapshot.steps[0].detail, "1차 검수 실패")
        self.assertEqual(snapshot.steps[1].state, "wait")


class NonStandardPhaseStepRoundTripTest(_ContractTestCase):
    """비표준 단계 목록은 `step` 호출로만 갱신되고, 수집이 그 상태를 그대로 읽는다."""

    def test_step_events_update_the_collected_snapshot(self) -> None:
        self._run(hub_dashboard_log.cmd_init, "원인 분석 진행", "원인 분석|설계|구현|검수")
        self.assertEqual(self._run(hub_dashboard_log.cmd_step, ["1", "done"]), "OK")
        self.assertEqual(self._run(hub_dashboard_log.cmd_step, ["2", "active"]), "OK")

        snapshot = self._collect_one()

        self.assertEqual([step.state for step in snapshot.steps], ["done", "active", "wait", "wait"])


class ApprovalWaitRoundTripTest(_ContractTestCase):
    """기록기가 쓴 「설계|승인|구현|검수」 기록이 수집되면 승인 단계 진행 사실이 설계 뒤에만 켜진다.
    기록 규칙의 단계 이름과 파서가 보는 이름이 어긋나면 여기서 깨진다(결정 AW2)."""

    def test_approval_step_is_active_between_design_and_approve(self) -> None:
        self._run(hub_dashboard_log.cmd_init, "승인 대기 왕복", "설계|승인|구현|검수")
        self.assertFalse(self._collect_one().is_approval_step_active)

        self.assertEqual(self._run(hub_dashboard_log.cmd_log, ["design", "설계 완료"]), "OK")
        self.assertTrue(self._collect_one().is_approval_step_active)

        self.assertEqual(self._run(hub_dashboard_log.cmd_log, ["approve", "승인 완료"]), "OK")
        self.assertFalse(self._collect_one().is_approval_step_active)


class DisabledSwitchRoundTripTest(_ContractTestCase):
    """진행 기록을 끈 프로젝트는 init 이 아무것도 쓰지 않아 수집 대상이 없다(RL10)."""

    def test_disabled_project_has_no_collectible_snapshot(self) -> None:
        self.assertEqual(self._run(hub_dashboard_log.cmd_switch, "off"), "OFF")

        init_output = self._run(hub_dashboard_log.cmd_init, "꺼진 프로젝트", "구현|검수")

        self.assertEqual(init_output, "DISABLED")
        snapshots, warnings = hub_collect.read_session_dashboard_snapshots(str(self._project_dir))
        self.assertEqual((snapshots, warnings), ((), ()))


if __name__ == "__main__":
    unittest.main()
