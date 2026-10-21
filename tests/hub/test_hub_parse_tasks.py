"""hub_parse.py 의 작업 이름표(동시 작업) 단위 테스트 — docs/prps/hub-dashboard-multi-task.md MT1·MT3~MT6.

test_hub_parse.py(665행)에 더하면 800행을 넘어 따로 뒀다. 이름표 없는 옛 기록이 오늘과 같은 값을
내는 회귀선은 그쪽 기존 테스트가 무변경으로 지킨다 — 여기는 이름표가 있을 때와, 옛 기록 골든만 둔다.
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_parse  # noqa: E402  (sys.path 조정 후 임포트)
import hub_session  # noqa: E402

_BASE_TIME_MS = 1789963200000  # 2026-09-21 04:00:00 UTC
_MINUTE_MS = 60_000
_FULL_PHASES = ["설계", "승인", "구현", "검수"]
_SHORT_PHASES = ["구현", "검수"]
_STALE_AFTER_MS = 10 * _MINUTE_MS


def _time_at(minute_offset: int) -> int:
    return _BASE_TIME_MS + minute_offset * _MINUTE_MS


def _init(minute: int, title: str, phases: list, task: str = "") -> dict:
    row = {"time_ms": _time_at(minute), "kind": "init", "title": title, "phases": phases, "project": "p"}
    return {**row, "task": task} if task else row


def _log(minute: int, kind: str, summary: str, task: str = "", detail: str = "") -> dict:
    row = {"time_ms": _time_at(minute), "kind": kind, "summary": summary, "detail": detail}
    return {**row, "task": task} if task else row


def _text(*rows: dict) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _parse(*rows: dict) -> tuple[hub_parse.DashboardEvent, ...]:
    return hub_parse.parse_event_lines(_text(*rows))


# 이번 사고(klago-ui-oneffice-micro 세션)의 순서를 이름표로 재구성한 픽스처 — 목업 생성기의 LABELED 와 같다.
_INCIDENT_ROWS = (
    _init(0, "8회차", _FULL_PHASES),
    _log(1, "design", "8회차 설계 완료"),
    _init(2, "9회차", _FULL_PHASES, task="9회차"),
    _log(3, "impl", "8회차 구현 완료"),
    _log(4, "pass", "8회차 검수 PASS"),
    _log(5, "commit", "8회차 커밋"),
    _log(6, "design", "9회차 설계 완료", task="9회차"),
    _log(7, "approve", "9회차 승인", task="9회차"),
    _init(8, "결함 ①", _SHORT_PHASES, task="결함①"),
    _log(9, "impl", "결함 ① 구현", task="결함①"),
    _log(10, "fail", "결함 ① 1회차 FAIL", task="결함①"),
    _log(11, "impl", "결함 ① 수정", task="결함①"),
    _log(12, "impl", "9회차 단계 1 구현", task="9회차"),
    _log(13, "pass", "결함 ① 2회차 PASS", task="결함①"),
    _log(14, "commit", "결함 ① 커밋", task="결함①"),
)


class IsValidTaskLabelTest(unittest.TestCase):
    """이름표 형식 — 1~20자, 앞뒤 공백 없음, 인쇄 가능한 문자만(MT1)."""

    def test_accepts_korean_circled_digit_and_inner_space(self) -> None:
        for label in ("결함①", "9회차", "결함 ① 수정", "a"):
            with self.subTest(label=label):
                self.assertTrue(hub_parse.is_valid_task_label(label))

    def test_accepts_exactly_the_maximum_length(self) -> None:
        self.assertTrue(hub_parse.is_valid_task_label("가" * hub_parse.TASK_LABEL_MAX_LENGTH))

    def test_rejects_one_over_the_maximum_length(self) -> None:
        self.assertFalse(hub_parse.is_valid_task_label("가" * (hub_parse.TASK_LABEL_MAX_LENGTH + 1)))

    def test_rejects_empty_and_edge_whitespace(self) -> None:
        for label in ("", " 결함", "결함 ", " "):
            with self.subTest(label=label):
                self.assertFalse(hub_parse.is_valid_task_label(label))

    def test_rejects_control_and_line_separator_characters(self) -> None:
        for label in ("결\n함", "결\t함", "결 함", "결\x00함"):
            with self.subTest(label=repr(label)):
                self.assertFalse(hub_parse.is_valid_task_label(label))


class TaskFieldParsingTest(unittest.TestCase):
    """줄 파싱 — task 필드가 이상하면 그 줄만 버린다(계약 B)."""

    def test_missing_key_and_empty_string_are_both_unlabeled(self) -> None:
        events = _parse(_init(0, "제목", _SHORT_PHASES), {**_log(1, "impl", "a"), "task": ""})

        self.assertEqual([event.task for event in events], ["", ""])

    def test_invalid_task_value_drops_only_that_line(self) -> None:
        bad_values = (5, ["결함"], None, "x" * 21, " 앞공백", "줄\n바꿈")
        for bad_value in bad_values:
            with self.subTest(bad_value=bad_value):
                events = _parse(
                    _init(0, "제목", _SHORT_PHASES),
                    {**_log(1, "impl", "버려질 줄"), "task": bad_value},
                    _log(2, "pass", "남는 줄"),
                )

                self.assertEqual([event.kind for event in events], ["init", "pass"])

    def test_invalid_task_on_init_drops_the_init_line(self) -> None:
        events = _parse(
            _init(0, "제목", _SHORT_PHASES),
            {**_init(1, "나쁜 이름표", _SHORT_PHASES), "task": 7},
        )

        self.assertEqual([event.title for event in events], ["제목"])

    def test_task_is_carried_on_step_events_too(self) -> None:
        step_row = {"time_ms": _time_at(2), "kind": "step", "index": 1, "state": "done", "task": "B"}

        events = _parse(_init(0, "첫", _SHORT_PHASES), _init(1, "B", _SHORT_PHASES, task="B"), step_row)

        self.assertEqual(events[-1].kind, "step")
        self.assertEqual(events[-1].task, "B")


class ParseEventLinesTasksTest(unittest.TestCase):
    """살아 있는 이벤트 열(MT3) — 시작점·정규화·생존."""

    def test_unlabeled_only_record_is_unchanged(self) -> None:
        rows = (_init(0, "제목", _FULL_PHASES), _log(1, "design", "a"), _log(2, "impl", "b"))

        events = _parse(*rows)

        self.assertEqual([event.kind for event in events], ["init", "design", "impl"])
        self.assertTrue(all(event.task == "" for event in events))

    def test_labeled_init_after_unlabeled_init_keeps_both(self) -> None:
        events = _parse(_init(0, "첫", _SHORT_PHASES), _init(1, "B", _SHORT_PHASES, task="B"))

        self.assertEqual([(event.title, event.task) for event in events], [("첫", ""), ("B", "B")])

    def test_unlabeled_init_drops_earlier_labeled_tasks(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "impl", "b 구현", task="B"),
            _init(3, "새 시작", _SHORT_PHASES),
        )

        self.assertEqual([event.title for event in events], ["새 시작"])

    def test_first_line_labeled_init_gives_its_label_to_unlabeled_events(self) -> None:
        events = _parse(_init(0, "A", _SHORT_PHASES, task="A"), _log(1, "impl", "무표 구현"))

        self.assertEqual([event.task for event in events], ["A", "A"])

    def test_same_label_init_restarts_only_that_task(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "impl", "B 옛 구현", task="B"),
            _log(3, "impl", "첫 구현"),
            _init(4, "B 다시", _SHORT_PHASES, task="B"),
            _log(5, "impl", "B 새 구현", task="B"),
        )

        self.assertEqual(
            [(event.kind, event.summary or event.title, event.task) for event in events],
            [
                ("init", "첫", ""),
                ("impl", "첫 구현", ""),
                ("init", "B 다시", "B"),
                ("impl", "B 새 구현", "B"),
            ],
        )

    def test_labeled_event_before_its_own_init_is_dropped_as_orphan(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _log(1, "impl", "고아", task="Z"),
            _init(2, "B", _SHORT_PHASES, task="B"),
        )

        self.assertEqual([event.summary or event.title for event in events], ["첫", "B"])

    def test_events_before_a_labeled_start_point_are_cut(self) -> None:
        events = _parse(
            _log(0, "impl", "init 보다 앞"),
            _init(1, "A", _SHORT_PHASES, task="A"),
            _init(2, "B", _SHORT_PHASES, task="B"),
        )

        self.assertEqual([event.title for event in events], ["A", "B"])

    def test_first_event_is_always_an_init(self) -> None:
        events = _parse(*_INCIDENT_ROWS)

        self.assertEqual(events[0].kind, "init")

    def test_no_init_at_all_returns_empty_tuple(self) -> None:
        self.assertEqual(_parse(_log(0, "impl", "a", task="A")), ())

    def test_last_unlabeled_init_wins_over_labeled_inits_before_it(self) -> None:
        events = _parse(
            _init(0, "A", _SHORT_PHASES, task="A"),
            _init(1, "무표", _SHORT_PHASES),
            _log(2, "impl", "무표 구현"),
        )

        self.assertEqual([(event.kind, event.task) for event in events], [("init", ""), ("impl", "")])


class SplitAndProgressTest(unittest.TestCase):
    """작업별 묶음·진행(MT4) — 한 작업의 기록이 다른 작업의 단계를 바꾸지 않는다."""

    def test_groups_are_in_init_order_and_start_with_their_init(self) -> None:
        groups = hub_parse.split_events_by_task(_parse(*_INCIDENT_ROWS))

        self.assertEqual([group[0].title for group in groups], ["8회차", "9회차", "결함 ①"])
        self.assertTrue(all(group[0].kind == "init" for group in groups))
        self.assertEqual([len(group) for group in groups], [5, 4, 6])

    def test_pass_of_one_task_does_not_finish_the_other_task(self) -> None:
        tasks = {task.label: task for task in hub_parse.task_progresses(_parse(*_INCIDENT_ROWS))}

        self.assertEqual(tasks["결함①"].percent, 100)
        self.assertEqual(tasks["9회차"].percent, 75)
        self.assertEqual(tasks["9회차"].completed, 3)

    def test_active_step_detail_is_the_last_summary_of_that_task(self) -> None:
        tasks = {task.label: task for task in hub_parse.task_progresses(_parse(*_INCIDENT_ROWS))}

        nine_active = [step for step in tasks["9회차"].steps if step.state == "active"][0]
        self.assertEqual(nine_active.name, "검수")
        self.assertEqual(nine_active.detail, "9회차 단계 1 구현")
        first_steps = tasks[""].steps
        self.assertTrue(all(step.state == "done" for step in first_steps))

    def test_progress_carries_title_started_at_and_commit_flag(self) -> None:
        tasks = {task.label: task for task in hub_parse.task_progresses(_parse(*_INCIDENT_ROWS))}

        self.assertEqual(tasks["결함①"].title, "결함 ①")
        self.assertEqual(tasks["결함①"].started_at_ms, _time_at(8))
        self.assertTrue(tasks["결함①"].is_committed)
        self.assertFalse(tasks["9회차"].is_committed)

    def test_progress_has_no_approval_step_active_for_finished_tasks(self) -> None:
        tasks = {task.label: task for task in hub_parse.task_progresses(_parse(*_INCIDENT_ROWS))}

        self.assertFalse(tasks["결함①"].is_approval_step_active)
        self.assertFalse(tasks["9회차"].is_approval_step_active)


class RepresentativeAndFoldingTest(unittest.TestCase):
    """대표 작업·접힘·표시 순서(MT5)."""

    def _labels_and_folded(self, *rows: dict) -> list[tuple[str, bool]]:
        return [(task.label, task.is_folded) for task in hub_parse.task_progresses(_parse(*rows))]

    def test_incident_display_order_unfolded_first_then_folded(self) -> None:
        self.assertEqual(
            self._labels_and_folded(*_INCIDENT_ROWS),
            [("9회차", False), ("", True), ("결함①", True)],
        )

    def test_single_task_is_never_folded_even_after_commit(self) -> None:
        folded = self._labels_and_folded(
            _init(0, "하나", _SHORT_PHASES), _log(1, "pass", "p"), _log(2, "commit", "c")
        )

        self.assertEqual(folded, [("", False)])

    def test_all_closed_keeps_the_most_recently_recorded_task_open(self) -> None:
        folded = self._labels_and_folded(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "pass", "B pass", task="B"),
            _log(3, "commit", "B commit", task="B"),
            _log(4, "pass", "첫 pass"),
            _log(5, "commit", "첫 commit"),
        )

        self.assertEqual(folded, [("", False), ("B", True)])

    def test_finished_but_uncommitted_task_is_not_folded(self) -> None:
        folded = self._labels_and_folded(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "pass", "첫 pass"),
            _log(3, "impl", "B 구현", task="B"),
        )

        self.assertEqual(folded, [("", False), ("B", False)])

    def test_commit_then_fail_unfolds_the_task_again(self) -> None:
        folded = self._labels_and_folded(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "pass", "첫 pass"),
            _log(3, "commit", "첫 commit"),
            _log(4, "impl", "B 구현", task="B"),
            _log(5, "fail", "첫 fail"),
        )

        self.assertEqual(folded, [("", False), ("B", False)])

    def test_two_unfinished_tasks_most_recently_recorded_is_the_representative(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "impl", "B 구현", task="B"),
            _log(3, "impl", "첫 구현"),
        )

        self.assertEqual(hub_parse.snapshot_from_events(events).title, "첫")

    def test_approval_active_task_is_representative_even_if_older(self) -> None:
        events = _parse(
            _init(0, "승인 대기 작업", _FULL_PHASES),
            _log(1, "design", "PRP 끝"),
            _init(2, "B", _SHORT_PHASES, task="B"),
            _log(3, "impl", "B 구현", task="B"),
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.title, "승인 대기 작업")
        self.assertTrue(snapshot.is_approval_step_active)

    def test_same_timestamp_ties_are_broken_by_file_order(self) -> None:
        same_minute = 5
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(same_minute, "impl", "B 구현", task="B"),
            _log(same_minute, "impl", "첫 구현"),
        )

        self.assertEqual(hub_parse.snapshot_from_events(events).title, "첫")


class SnapshotAggregationTest(unittest.TestCase):
    """상단 필드 집계(MT6) — 소비자가 기대하는 의미."""

    def test_percent_is_100_only_when_every_task_is_finished(self) -> None:
        one_open = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "pass", "첫 pass"),
        )
        all_done = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "pass", "첫 pass"),
            _log(3, "pass", "B pass", task="B"),
        )

        self.assertEqual(hub_parse.snapshot_from_events(one_open).percent, 0)
        self.assertEqual(hub_parse.snapshot_from_events(all_done).percent, 100)

    def test_is_approval_step_active_is_any_task(self) -> None:
        events = _parse(
            _init(0, "첫", _FULL_PHASES),
            _log(1, "design", "PRP 끝"),
            _init(2, "B", _SHORT_PHASES, task="B"),
        )

        self.assertTrue(hub_parse.snapshot_from_events(events).is_approval_step_active)

    def test_task_started_at_is_the_earliest_unfinished_start(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(5, "B", _SHORT_PHASES, task="B"),
            _log(6, "impl", "B 구현", task="B"),
        )

        self.assertEqual(hub_parse.snapshot_from_events(events).task_started_at_ms, _time_at(0))

    def test_task_started_at_skips_finished_tasks(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _log(1, "pass", "첫 pass"),
            _init(5, "B", _SHORT_PHASES, task="B"),
        )

        self.assertEqual(hub_parse.snapshot_from_events(events).task_started_at_ms, _time_at(5))

    def test_task_started_at_of_all_finished_is_the_representative_start(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(5, "B", _SHORT_PHASES, task="B"),
            _log(6, "pass", "첫 pass"),
            _log(7, "pass", "B pass", task="B"),
        )

        # 대표 = 가장 최근에 기록된 B(시작 5분). 가장 이른 시작(0분)이 아니다.
        self.assertEqual(hub_parse.snapshot_from_events(events).task_started_at_ms, _time_at(5))

    def test_updated_text_is_the_last_live_event_time(self) -> None:
        events = _parse(*_INCIDENT_ROWS)

        self.assertEqual(
            hub_parse.snapshot_from_events(events).updated_text,
            hub_parse.format_event_updated_label(_time_at(14)),
        )

    def test_incident_top_fields_follow_the_unfinished_task(self) -> None:
        snapshot = hub_parse.snapshot_from_events(_parse(*_INCIDENT_ROWS))

        self.assertEqual((snapshot.title, snapshot.percent, snapshot.completed), ("9회차", 75, 3))
        self.assertEqual(snapshot.task_started_at_ms, _time_at(2))
        self.assertEqual(
            [task.label for task in snapshot.tasks], ["9회차", "", "결함①"]
        )

    def test_unlabeled_record_golden_matches_the_pre_change_values(self) -> None:
        # 개정 전 커밋(26798f8)의 snapshot_from_events 로 뽑은 값을 리터럴로 고정한 골든이다(MT11).
        events = _parse(
            _init(0, "옛 기록 제목", _FULL_PHASES),
            _log(1, "design", "설계 끝"),
            _log(2, "approve", "승인"),
            _log(3, "impl", "구현 끝"),
            _log(4, "fail", "검수 실패", detail="[검증] x"),
            _log(5, "impl", "고침"),
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(
            (snapshot.title, snapshot.subtitle, snapshot.completed, snapshot.total, snapshot.percent),
            ("옛 기록 제목", "", 3, 4, 75),
        )
        self.assertEqual(
            [(step.index, step.name, step.state, step.detail) for step in snapshot.steps],
            [(1, "설계", "done", ""), (2, "승인", "done", ""), (3, "구현", "done", ""), (4, "검수", "active", "고침")],
        )
        self.assertEqual(snapshot.task_started_at_ms, _time_at(0))
        self.assertEqual(snapshot.updated_text, hub_parse.format_event_updated_label(_time_at(5)))
        self.assertEqual((snapshot.is_committed, snapshot.is_approval_step_active), (False, False))
        self.assertEqual((snapshot.matrix_done, snapshot.impl_done, snapshot.impl_total), (None, 0, 0))

    def test_unlabeled_record_has_exactly_one_unfolded_task_equal_to_the_top_fields(self) -> None:
        events = _parse(_init(0, "하나", _FULL_PHASES), _log(1, "design", "d"))

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(len(snapshot.tasks), 1)
        task = snapshot.tasks[0]
        self.assertEqual((task.label, task.title, task.percent, task.is_folded), ("", "하나", 25, False))
        self.assertEqual(task.steps, snapshot.steps)
        self.assertEqual(task.started_at_ms, snapshot.task_started_at_ms)

    def test_tasks_default_is_empty_for_a_hand_built_snapshot(self) -> None:
        field = {f.name: f for f in dataclasses.fields(hub_parse.Tier1Snapshot)}["tasks"]

        self.assertEqual(field.default, ())


class LiveTaskLabelsTest(unittest.TestCase):
    """기록기의 NOTASK 판정에 쓰는 살아 있는 이름표 집합."""

    def test_returns_labels_of_live_inits_including_the_empty_first_task(self) -> None:
        labels = hub_parse.live_task_labels(_parse(*_INCIDENT_ROWS))

        self.assertEqual(labels, frozenset({"", "9회차", "결함①"}))

    def test_label_wiped_by_an_unlabeled_init_is_gone(self) -> None:
        events = _parse(_init(0, "첫", _SHORT_PHASES), _init(1, "B", _SHORT_PHASES, task="B"), _init(2, "새", _SHORT_PHASES))

        self.assertNotIn("B", hub_parse.live_task_labels(events))

    def test_label_survives_its_own_restart(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _init(2, "B 다시", _SHORT_PHASES, task="B"),
        )

        self.assertIn("B", hub_parse.live_task_labels(events))


class ConsumerContractTest(unittest.TestCase):
    """코드를 바꾸지 않은 소비자(hub_session)가 다중 작업 스냅샷에서도 맞는 답을 낸다(MT6)."""

    def test_previous_task_boundary_uses_the_earliest_unfinished_start(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(5, "B", _SHORT_PHASES, task="B"),
            _log(6, "pass", "B pass", task="B"),
        )
        snapshot = dataclasses.replace(hub_parse.snapshot_from_events(events), file_mtime_ms=_time_at(7))

        boundary = hub_session.previous_task_boundary_ms(snapshot, _time_at(3), True)

        self.assertEqual(boundary, _time_at(0))

    def test_session_tier1_is_not_a_finished_task_when_only_one_task_finished(self) -> None:
        events = _parse(
            _init(0, "첫", _SHORT_PHASES),
            _init(1, "B", _SHORT_PHASES, task="B"),
            _log(2, "pass", "첫 pass"),
            _log(3, "commit", "첫 commit"),
        )
        snapshot = hub_parse.snapshot_from_events(events)

        self.assertFalse(
            hub_session.is_session_tier1_from_finished_task(
                snapshot.percent, snapshot.file_mtime_ms, _time_at(600), _STALE_AFTER_MS
            )
        )


if __name__ == "__main__":
    unittest.main()
