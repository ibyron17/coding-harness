"""hub_activity 단위 테스트(★순수) — docs/prps/hub-live-activity.md §10.1 표 전체(LA-K1·LA-P*·LA-B*·LA-O1·LA-S*·LA-C1).

전부 합성 픽스처다 — 테스트 안에서 json.dumps 로 줄을 만든다. 실제 경로·프롬프트·기록을 넣지 않는다.
"""

import dataclasses
import json
import os
import sys
import typing
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_activity  # noqa: E402  (sys.path 조정 후 임포트)
import hub_transcript  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다(test_hub_subagent_read.py 의 관례).
try:
    from .live_activity_fixtures import (
        BASE_MS,
        MINUTE_MS,
        SECOND_MS,
        SESSION_ID,
        iso as _iso,
        jsonl_bytes as _window,
        line as _line,
        moved_phrase as _moved_phrase,
        output_phrase as _output_phrase,
        result_line as _result_line,
        use_line as _use_line,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from live_activity_fixtures import (  # noqa: E402
        BASE_MS,
        MINUTE_MS,
        SECOND_MS,
        SESSION_ID,
        iso as _iso,
        jsonl_bytes as _window,
        line as _line,
        moved_phrase as _moved_phrase,
        output_phrase as _output_phrase,
        result_line as _result_line,
        use_line as _use_line,
    )


class ClassifyToolKindTest(unittest.TestCase):
    def test_la_k1_every_listed_name_maps_to_its_kind(self) -> None:
        for name, expected_kind in hub_activity.TOOL_KIND_BY_NAME.items():
            with self.subTest(name=name):
                self.assertEqual(hub_activity.classify_tool_kind(name), expected_kind)

    def test_la_k1_table_values_stay_inside_the_closed_set(self) -> None:
        self.assertEqual(set(hub_activity.TOOL_KIND_BY_NAME.values()) - set(hub_activity.TOOL_KINDS), set())

    def test_la_k1_unknown_prefixed_and_non_string_names_are_other(self) -> None:
        for value in ("Unknown", "mcp__a__b", None, 3):
            with self.subTest(value=value):
                self.assertEqual(hub_activity.classify_tool_kind(value), "other")


class ParseToolActivityTest(unittest.TestCase):
    def test_la_p1_empty_window_and_lines_without_a_usable_timestamp_are_none(self) -> None:
        no_timestamp = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "a", "name": "Read"}]}}
        integer_timestamp = {**_use_line(BASE_MS, "a"), "timestamp": 123}
        garbage_timestamp = {**_use_line(BASE_MS, "a"), "timestamp": "not a time"}
        for window in (b"", _window(no_timestamp), _window(integer_timestamp), _window(garbage_timestamp)):
            with self.subTest(window=window[:20]):
                self.assertIsNone(hub_activity.parse_tool_activity(window))

    def test_la_p2_lines_without_any_tool_block_are_none(self) -> None:
        thinking_line = _line("assistant", BASE_MS, [{"type": "thinking", "thinking": "SENTINEL-THOUGHT"}])
        text_line = _line("assistant", BASE_MS + SECOND_MS, [{"type": "text", "text": "SENTINEL-TEXT"}])

        self.assertIsNone(hub_activity.parse_tool_activity(_window(thinking_line, text_line)))

    def test_la_p3_a_call_with_its_result_is_not_pending(self) -> None:
        window = _window(_use_line(BASE_MS, "a", "Read"), _result_line(BASE_MS + SECOND_MS, "a"))

        activity = hub_activity.parse_tool_activity(window)

        self.assertEqual(activity.pending_count, 0)
        self.assertIsNone(activity.pending_tool_kind)
        self.assertIsNone(activity.pending_since_ms)
        self.assertEqual(activity.last_tool_kind, "read")
        self.assertEqual(activity.recent_tool_counts.read, 1)
        self.assertEqual(activity.last_record_at_ms, BASE_MS + SECOND_MS)
        self.assertIsNone(activity.stall_suspect_at_ms)
        self.assertIsNone(activity.background_output)

    def test_la_p4_a_call_without_a_result_is_pending(self) -> None:
        activity = hub_activity.parse_tool_activity(_window(_use_line(BASE_MS, "a", "Bash")))

        self.assertEqual(activity.pending_count, 1)
        self.assertEqual(activity.pending_tool_kind, "run")
        self.assertEqual(activity.pending_since_ms, BASE_MS)
        self.assertEqual(activity.last_tool_kind, "run")

    def test_la_p5_with_parallel_calls_the_oldest_pending_one_is_reported(self) -> None:
        window = _window(
            _use_line(BASE_MS, "a", "Edit"),
            _use_line(BASE_MS + SECOND_MS, "b", "Bash"),
            _use_line(BASE_MS + 2 * SECOND_MS, "c", "Read"),
            _result_line(BASE_MS + 3 * SECOND_MS, "c"),
        )

        activity = hub_activity.parse_tool_activity(window)

        self.assertEqual(activity.pending_count, 2)
        self.assertEqual(activity.pending_tool_kind, "edit")
        self.assertEqual(activity.pending_since_ms, BASE_MS)

    def test_la_p6_a_result_whose_call_is_outside_the_window_is_ignored(self) -> None:
        activity = hub_activity.parse_tool_activity(_window(_result_line(BASE_MS, "outside")))

        self.assertEqual(activity.pending_count, 0)
        self.assertIsNone(activity.last_tool_kind)
        self.assertEqual(activity.last_record_at_ms, BASE_MS)

    def test_la_p7_torn_first_line_and_torn_result_line_leave_that_call_pending(self) -> None:
        complete_pair = _window(_use_line(BASE_MS, "a", "Read"), _result_line(BASE_MS + SECOND_MS, "a"))
        torn_head = b'ncated-tail-of-a-line"}]}}\n'
        pending_use = _window(_use_line(BASE_MS + 2 * SECOND_MS, "b", "Bash"))
        torn_result = json.dumps(_result_line(BASE_MS + 3 * SECOND_MS, "b")).encode("utf-8")[:-10]

        activity = hub_activity.parse_tool_activity(torn_head + complete_pair + pending_use + torn_result)

        self.assertEqual(activity.pending_count, 1)
        self.assertEqual(activity.pending_tool_kind, "run")

    def test_la_p7_window_starting_inside_a_multibyte_character_does_not_raise(self) -> None:
        pair = _window(_use_line(BASE_MS, "a", "Read"), _result_line(BASE_MS + SECOND_MS, "a"))
        torn_multibyte = "가나다".encode("utf-8")[1:] + b'"}\n'

        activity = hub_activity.parse_tool_activity(torn_multibyte + pair)

        self.assertEqual(activity.pending_count, 0)

    def test_la_p8_shape_violations_never_raise_and_only_the_violating_part_is_ignored(self) -> None:
        valid_pair = [_use_line(BASE_MS, "a", "Read"), _result_line(BASE_MS + SECOND_MS, "a")]
        later = BASE_MS + 2 * SECOND_MS
        violations = {
            "message is a list": {"type": "assistant", "timestamp": _iso(later), "message": [1, 2]},
            "content is a string": _line("assistant", later, "plain text"),
            "blocks are not objects": _line("assistant", later, [1, "x", None, ["y"]]),
            "use without id": _line("assistant", later, [{"type": "tool_use", "name": "Bash"}]),
            "use with integer id": _line("assistant", later, [{"type": "tool_use", "id": 7, "name": "Bash"}]),
            "result with integer id": _line("user", later, [{"type": "tool_result", "tool_use_id": 7}]),
            "integer timestamp": {**_use_line(later, "z", "Bash"), "timestamp": 99},
            "line is not an object": ["tool_use"],
        }
        for label, violation in violations.items():
            with self.subTest(label):
                activity = hub_activity.parse_tool_activity(_window(*valid_pair, violation))

                self.assertEqual(activity.pending_count, 0)
                self.assertEqual(activity.last_tool_kind, "read")

    def test_la_p8_integer_tool_name_is_other_kind(self) -> None:
        activity = hub_activity.parse_tool_activity(_window(_use_line(BASE_MS, "a", name=3)))

        self.assertEqual(activity.last_tool_kind, "other")
        self.assertEqual(activity.pending_tool_kind, "other")

    def test_la_p8_deeply_nested_line_does_not_raise(self) -> None:
        deep_line = b'{"type":"assistant","message":' + b"[" * 200_000 + b"]" * 200_000 + b"}\n"
        pair = _window(_use_line(BASE_MS, "a", "Read"), _result_line(BASE_MS + SECOND_MS, "a"))

        activity = hub_activity.parse_tool_activity(deep_line + pair)

        self.assertEqual(activity.pending_count, 0)

    def test_la_p9_a_reattached_duplicate_call_line_is_counted_once(self) -> None:
        window = _window(
            _use_line(BASE_MS, "a", "Read"),
            _result_line(BASE_MS + SECOND_MS, "a"),
            _use_line(BASE_MS + 2 * SECOND_MS, "a", "Read"),
        )

        activity = hub_activity.parse_tool_activity(window)

        self.assertEqual(activity.recent_tool_counts.read, 1)
        self.assertEqual(activity.pending_count, 0)

    def test_la_p9_a_later_reattached_copy_does_not_move_the_first_lines_time(self) -> None:
        """재부착 사본이 더 늦은 시각을 달고 와도 호출의 시각·종류는 첫 줄 기준이다 — 마지막 줄이 이기면(덮어쓰기) 진행 중
        시작 시각이 사본 시각으로 밀리고, 개수 범위 밖이던 호출이 범위 안으로 들어온다."""
        last_ms = BASE_MS + 30 * MINUTE_MS
        first_ms = last_ms - 11 * MINUTE_MS
        window = _window(_use_line(first_ms, "a", "Bash"), _use_line(last_ms, "a", "Bash"))

        activity = hub_activity.parse_tool_activity(window)

        self.assertEqual(activity.pending_count, 1)
        self.assertEqual(activity.pending_since_ms, first_ms)
        self.assertEqual(activity.last_record_at_ms, last_ms)
        self.assertEqual(activity.recent_counts_since_ms, last_ms - hub_activity.RECENT_TOOL_WINDOW_MS)
        self.assertEqual(activity.recent_tool_counts, hub_activity.ToolKindCounts())   # 첫 줄은 범위(마지막 10분) 밖이다

    def test_la_p10_counts_cover_the_last_ten_minutes_of_records_not_the_clock(self) -> None:
        last_ms = BASE_MS + 30 * MINUTE_MS
        window = _window(
            _line("attachment", last_ms - 20 * MINUTE_MS),
            _use_line(last_ms - 11 * MINUTE_MS, "a", "Read"),
            _result_line(last_ms - 11 * MINUTE_MS + SECOND_MS, "a"),
            _use_line(last_ms - 9 * MINUTE_MS, "b", "Edit"),
            _result_line(last_ms - 9 * MINUTE_MS + SECOND_MS, "b"),
            _use_line(last_ms, "c", "Bash"),
        )

        activity = hub_activity.parse_tool_activity(window)

        self.assertEqual(activity.recent_counts_since_ms, last_ms - hub_activity.RECENT_TOOL_WINDOW_MS)
        self.assertEqual(
            activity.recent_tool_counts, hub_activity.ToolKindCounts(read=0, edit=1, run=1, delegate=0, other=0)
        )

    def test_la_p10_when_the_window_is_shorter_than_ten_minutes_the_lower_bound_is_its_first_record(self) -> None:
        last_ms = BASE_MS + 30 * MINUTE_MS
        window = _window(
            _line("attachment", last_ms - 3 * MINUTE_MS),
            _use_line(last_ms - 2 * MINUTE_MS, "a", "Read"),
            _result_line(last_ms, "a"),
        )

        activity = hub_activity.parse_tool_activity(window)

        self.assertEqual(activity.recent_counts_since_ms, last_ms - 3 * MINUTE_MS)
        self.assertEqual(activity.recent_tool_counts.read, 1)

    def test_la_p11_the_last_record_time_comes_from_any_line_even_a_non_tool_one(self) -> None:
        window = _window(
            _use_line(BASE_MS, "a", "Read"),
            _result_line(BASE_MS + SECOND_MS, "a"),
            _line("attachment", BASE_MS + 5 * MINUTE_MS),
        )

        self.assertEqual(hub_activity.parse_tool_activity(window).last_record_at_ms, BASE_MS + 5 * MINUTE_MS)

    def test_la_p12_utc_z_timestamps_parse_under_python310_semantics(self) -> None:
        self.assertIs(hub_activity.epoch_ms_from_iso8601, hub_transcript.epoch_ms_from_iso8601)

        class _Python310SemanticsFromIsoformat:
            @staticmethod
            def fromisoformat(value):
                if isinstance(value, str) and value.endswith("Z"):
                    raise ValueError(f"Invalid isoformat string: {value!r}")
                return datetime.fromisoformat(value)

        with mock.patch.object(hub_transcript, "datetime", _Python310SemanticsFromIsoformat):
            activity = hub_activity.parse_tool_activity(_window(_use_line(BASE_MS, "a", "Bash")))

        self.assertEqual(activity.pending_since_ms, BASE_MS)

    def test_only_the_tail_of_an_oversized_window_is_interpreted(self) -> None:
        old_pending_use = _window(_use_line(BASE_MS, "old", "Bash"))
        filler = _window(*[_line("attachment", BASE_MS + SECOND_MS) for _ in range(5)])
        padding = filler * (hub_activity.ACTIVITY_PARSE_BYTES // len(filler) + 2)
        recent_pair = _window(_use_line(BASE_MS + MINUTE_MS, "a", "Read"), _result_line(BASE_MS + MINUTE_MS, "a"))

        activity = hub_activity.parse_tool_activity(old_pending_use + padding + recent_pair)

        self.assertEqual(activity.pending_count, 0)
        self.assertEqual(activity.last_tool_kind, "read")


class BackgroundOutputPathsTest(unittest.TestCase):
    def _paths_for(self, line: dict, session_id: str = SESSION_ID) -> tuple[str, ...]:
        return hub_activity.background_output_paths(_window(line), session_id)

    def _tool_result_line(self, content: object) -> dict:
        return _result_line(BASE_MS, "toolu_1", content)

    def test_la_b1_a_string_body_yields_its_output_path(self) -> None:
        line = self._tool_result_line(_output_phrase(SESSION_ID, "abc"))

        self.assertEqual(self._paths_for(line), (f"/t/x/{SESSION_ID}/tasks/abc.output",))

    def test_la_b2_a_text_block_list_body_yields_the_same_path(self) -> None:
        line = self._tool_result_line([{"type": "text", "text": _output_phrase(SESSION_ID, "abc")}])

        self.assertEqual(self._paths_for(line), (f"/t/x/{SESSION_ID}/tasks/abc.output",))

    def test_la_b3_the_phrase_outside_a_tool_result_block_is_ignored(self) -> None:
        phrase = _output_phrase(SESSION_ID, "abc")
        outside = {
            "human prompt text": _line("user", BASE_MS, [{"type": "text", "text": phrase}]),
            "human prompt string": _line("user", BASE_MS, phrase),
            "assistant text": _line("assistant", BASE_MS, [{"type": "text", "text": phrase}]),
            "assistant tool input": _line(
                "assistant", BASE_MS, [{"type": "tool_use", "id": "a", "name": "Bash", "input": {"command": phrase}}]
            ),
            "assistant line carrying a tool_result block": _line(
                "assistant", BASE_MS, [{"type": "tool_result", "tool_use_id": "a", "content": phrase}]
            ),
        }
        for label, line in outside.items():
            with self.subTest(label):
                self.assertEqual(self._paths_for(line), ())

    def test_la_b4_shape_violations_are_rejected(self) -> None:
        good_path = f"/t/x/{SESSION_ID}/tasks/abc.output"
        bodies = {
            "grandparent is another session": _output_phrase("other-session", "abc"),
            "parent is not tasks": _output_phrase(SESSION_ID, "abc", directory="jobs"),
            "no matching ID line": f"Output is being written to: {good_path}",
            "ID names another task": f"ID: zzz. Output is being written to: {good_path}",
            "relative path": f"ID: abc. Output is being written to: t/x/{SESSION_ID}/tasks/abc.output",
            "dot-dot piece": f"ID: abc. Output is being written to: /t/../x/{SESSION_ID}/tasks/abc.output",
            "empty piece": f"ID: abc. Output is being written to: /t//x/{SESSION_ID}/tasks/abc.output",
            "stem with a dollar sign": f"ID: a$b. Output is being written to: /t/x/{SESSION_ID}/tasks/a$b.output",
            "stem with a space": f"ID: a b. Output is being written to: /t/x/{SESSION_ID}/tasks/a b.output",
            "stem too long": _output_phrase(SESSION_ID, "a" * 65),
            "embedded NUL": f"ID: abc. Output is being written to: /t/x\x00y/{SESSION_ID}/tasks/abc.output",
        }
        for label, body in bodies.items():
            with self.subTest(label):
                self.assertEqual(self._paths_for(self._tool_result_line(body)), ())

    def test_la_b4_a_sixty_four_character_stem_is_accepted(self) -> None:
        long_task_id = "a" * 64

        paths = self._paths_for(self._tool_result_line(_output_phrase(SESSION_ID, long_task_id)))

        self.assertEqual(paths, (f"/t/x/{SESSION_ID}/tasks/{long_task_id}.output",))

    def test_la_b5_duplicates_collapse_and_only_the_newest_eight_distinct_paths_remain(self) -> None:
        task_ids = [f"t{index}" for index in range(10)]
        lines = [_result_line(BASE_MS + index, f"u{index}", _output_phrase(SESSION_ID, task_id)) for index, task_id in enumerate(task_ids)]
        lines.append(_result_line(BASE_MS + 99, "u99", _output_phrase(SESSION_ID, "t5")))

        paths = hub_activity.background_output_paths(_window(*lines), SESSION_ID)

        expected_order = ("t5", "t9", "t8", "t7", "t6", "t4", "t3", "t2")
        self.assertEqual(paths, tuple(f"/t/x/{SESSION_ID}/tasks/{task_id}.output" for task_id in expected_order))
        self.assertEqual(hub_activity.BACKGROUND_OUTPUT_MAX_FILES, 8)

    def test_la_b6_lines_without_the_marker_are_never_decoded(self) -> None:
        plain_lines = [_use_line(BASE_MS + index, f"u{index}") for index in range(20)]
        marker_line = _result_line(BASE_MS + 99, "u99", _output_phrase(SESSION_ID, "abc"))
        window = _window(*plain_lines, marker_line, *plain_lines)

        with mock.patch.object(
            hub_activity, "_json_object_or_none", wraps=hub_activity._json_object_or_none
        ) as decode:
            paths = hub_activity.background_output_paths(window, SESSION_ID)

        self.assertEqual(decode.call_count, 1)
        self.assertEqual(len(paths), 1)

    def test_a_torn_marker_line_is_skipped_without_raising(self) -> None:
        torn = json.dumps(self._tool_result_line(_output_phrase(SESSION_ID, "abc"))).encode("utf-8")[:-15]

        self.assertEqual(hub_activity.background_output_paths(torn, SESSION_ID), ())


class HostBackgroundLaunchesTest(unittest.TestCase):
    """host_background_launches — 호스트의 두 시작 문장(PRP background-task-orphans BG-G2)만 인정한다. 상한이 없다."""

    def _launches_for(self, *bodies: object, session_id: str = SESSION_ID) -> tuple[hub_activity.BackgroundLaunch, ...]:
        lines = [_result_line(BASE_MS + index, f"u{index}", body) for index, body in enumerate(bodies)]
        return hub_activity.host_background_launches(_window(*lines), session_id)

    def _expected(self, task_id: str) -> hub_activity.BackgroundLaunch:
        return hub_activity.BackgroundLaunch(task_id=task_id, output_path=f"/t/x/{SESSION_ID}/tasks/{task_id}.output")

    def test_the_run_in_background_sentence_yields_a_launch(self) -> None:
        launches = self._launches_for(_output_phrase(SESSION_ID, "bfrtiwey5"))

        self.assertEqual(launches, (self._expected("bfrtiwey5"),))

    def test_the_timeout_moved_sentence_yields_a_launch(self) -> None:
        launches = self._launches_for(_moved_phrase(SESSION_ID, "b2l1gdl7h"))

        self.assertEqual(launches, (self._expected("b2l1gdl7h"),))

    def test_a_text_block_list_body_is_read_like_a_string_body(self) -> None:
        body = [{"type": "text", "text": _moved_phrase(SESSION_ID, "b2l1gdl7h")}]

        self.assertEqual(self._launches_for(body), (self._expected("b2l1gdl7h"),))

    def test_both_sentences_in_one_window_come_newest_first(self) -> None:
        launches = self._launches_for(_moved_phrase(SESSION_ID, "older"), _output_phrase(SESSION_ID, "newer"))

        self.assertEqual(launches, (self._expected("newer"), self._expected("older")))

    def test_the_same_task_reported_twice_collapses_to_one(self) -> None:
        launches = self._launches_for(_output_phrase(SESSION_ID, "abc"), _output_phrase(SESSION_ID, "abc"))

        self.assertEqual(launches, (self._expected("abc"),))

    def test_there_is_no_upper_bound_on_the_number_of_launches(self) -> None:
        task_ids = [f"t{index}" for index in range(hub_activity.BACKGROUND_OUTPUT_MAX_FILES + 3)]

        launches = self._launches_for(*[_output_phrase(SESSION_ID, task_id) for task_id in task_ids])

        self.assertEqual({launch.task_id for launch in launches}, set(task_ids))
        self.assertEqual(len(launches), len(task_ids))

    def test_a_path_under_another_session_is_excluded(self) -> None:
        launches = self._launches_for(_output_phrase("other-session", "abc"), _moved_phrase("other-session", "def"))

        self.assertEqual(launches, ())

    def test_the_marker_without_a_paired_id_is_excluded(self) -> None:
        good_path = f"/t/x/{SESSION_ID}/tasks/abc.output"
        bodies = {
            "marker only": f"Output is being written to: {good_path}",
            "ID names another task": f"Command running in background with ID: zzz. Output is being written to: {good_path}",
            "moved sentence names another task": (
                f"Command did not complete within its 120s timeout and was moved to the background (ID: zzz). "
                f"Output is being written to: {good_path}."
            ),
        }
        for label, body in bodies.items():
            with self.subTest(label):
                self.assertEqual(self._launches_for(body), ())

    def test_a_host_sentence_quoted_in_the_middle_of_a_body_is_excluded(self) -> None:
        """검수 1회차 지적 1 — 다른 기록을 Read·grep·cat 해 남의 시작 문장이 본문 중간에 실려도 내 작업이 아니다."""
        for label, sentence in {
            "running": _output_phrase(SESSION_ID, "sibling1"),
            "moved": _moved_phrase(SESSION_ID, "sibling2"),
        }.items():
            quoted_line = json.dumps(_result_line(BASE_MS, "toolu_s", sentence))
            quoted_bodies = {
                "after a Read line number": f"     42\t{sentence}",
                "after a grep file prefix": f"agent-sibling.jsonl:42:{sentence}",
                "inside a JSON dump of the sibling line": f"agent-sibling.jsonl:42:{quoted_line}",
                "after a leading sentence": f"결과 확인\n{sentence}",
                "after a leading space": f" {sentence}",
            }
            for quote_label, body in quoted_bodies.items():
                with self.subTest(sentence=label, quoted=quote_label):
                    self.assertEqual(self._launches_for(body), ())

    def test_a_second_text_block_starting_with_the_host_sentence_is_not_the_body_start(self) -> None:
        body = [{"type": "text", "text": "머리말"}, {"type": "text", "text": _output_phrase(SESSION_ID, "abc")}]

        self.assertEqual(self._launches_for(body), ())

    def test_the_moved_sentence_needs_its_timeout_lead_in(self) -> None:
        bare = f"was moved to the background (ID: abc). Output is being written to: /t/x/{SESSION_ID}/tasks/abc.output."

        self.assertEqual(self._launches_for(bare), ())

    def test_a_bare_id_plus_marker_that_is_not_one_of_the_two_host_sentences_is_excluded(self) -> None:
        good_path = f"/t/x/{SESSION_ID}/tasks/abc.output"

        launches = self._launches_for(f"ID: abc. Output is being written to: {good_path}")

        self.assertEqual(launches, ())

    def test_example_sentences_quoted_from_documentation_are_excluded(self) -> None:
        examples = {
            "placeholder id": "Command running in background with ID: <id>. Output is being written to: <path>",
            "placeholder path": "Command running in background with ID: abc. Output is being written to: /path/to/<id>.output",
            "relative path": f"Command running in background with ID: abc. Output is being written to: t/{SESSION_ID}/tasks/abc.output",
            "no output suffix": f"Command running in background with ID: abc. Output is being written to: /t/{SESSION_ID}/tasks/abc",
        }
        for label, body in examples.items():
            with self.subTest(label):
                self.assertEqual(self._launches_for(body), ())

    def test_a_sentence_outside_a_tool_result_block_is_ignored(self) -> None:
        phrase = _moved_phrase(SESSION_ID, "abc")
        outside = _line("assistant", BASE_MS, [{"type": "text", "text": phrase}])

        self.assertEqual(hub_activity.host_background_launches(_window(outside), SESSION_ID), ())

    def test_a_torn_line_is_skipped_without_raising(self) -> None:
        torn = json.dumps(_result_line(BASE_MS, "u0", _moved_phrase(SESSION_ID, "abc"))).encode("utf-8")[:-15]

        self.assertEqual(hub_activity.host_background_launches(torn, SESSION_ID), ())

    def test_the_display_function_keeps_its_eight_file_cap(self) -> None:
        bodies = [_output_phrase(SESSION_ID, f"t{index}") for index in range(10)]
        lines = [_result_line(BASE_MS + index, f"u{index}", body) for index, body in enumerate(bodies)]

        paths = hub_activity.background_output_paths(_window(*lines), SESSION_ID)

        self.assertEqual(len(paths), hub_activity.BACKGROUND_OUTPUT_MAX_FILES)


class SummarizeBackgroundOutputsTest(unittest.TestCase):
    def test_la_o1_no_files_is_none(self) -> None:
        self.assertIsNone(hub_activity.summarize_background_outputs(()))

    def test_la_o1_several_files_are_counted_with_the_newest_time_and_total_size(self) -> None:
        view = hub_activity.summarize_background_outputs(((1_000, 10), (3_000, 20), (2_000, 30)))

        self.assertEqual(view, hub_activity.BackgroundOutputView(file_count=3, updated_at_ms=3_000, total_bytes=60))


def _activity_with(**overrides: object) -> hub_activity.SubagentActivity:
    base: dict = dict(
        last_record_at_ms=BASE_MS,
        last_tool_kind="read",
        pending_count=0,
        pending_tool_kind=None,
        pending_since_ms=None,
        recent_tool_counts=hub_activity.ToolKindCounts(read=1),
        recent_counts_since_ms=BASE_MS,
    )
    base.update(overrides)
    return hub_activity.SubagentActivity(**base)


class WithStallSuspectAtTest(unittest.TestCase):
    def test_la_s1_a_pending_call_means_no_suspect_time(self) -> None:
        activity = _activity_with(pending_count=1, pending_tool_kind="run", pending_since_ms=BASE_MS, stall_suspect_at_ms=123)

        result = hub_activity.with_stall_suspect_at(activity, BASE_MS - MINUTE_MS)

        self.assertIsNone(result.stall_suspect_at_ms)

    def test_la_s2_without_pending_calls_the_suspect_time_is_last_record_plus_threshold(self) -> None:
        activity = _activity_with(last_record_at_ms=BASE_MS)

        result = hub_activity.with_stall_suspect_at(activity, BASE_MS - 5 * MINUTE_MS)

        self.assertEqual(result.stall_suspect_at_ms, BASE_MS + hub_activity.SUBAGENT_STALL_SUSPECT_AFTER_MS)

    def test_la_s3_a_resume_after_the_last_record_restarts_the_clock(self) -> None:
        activity = _activity_with(last_record_at_ms=BASE_MS)
        resumed_at_ms = BASE_MS + 40 * MINUTE_MS

        result = hub_activity.with_stall_suspect_at(activity, resumed_at_ms)

        self.assertEqual(result.stall_suspect_at_ms, resumed_at_ms + hub_activity.SUBAGENT_STALL_SUSPECT_AFTER_MS)

    def test_the_given_activity_is_not_changed(self) -> None:
        activity = _activity_with()

        hub_activity.with_stall_suspect_at(activity, BASE_MS)

        self.assertIsNone(activity.stall_suspect_at_ms)

    def test_the_threshold_is_ten_minutes(self) -> None:
        self.assertEqual(hub_activity.SUBAGENT_STALL_SUSPECT_AFTER_MS, 10 * MINUTE_MS)


class ActivityContractTest(unittest.TestCase):
    """LA-C1 — 내보내는 타입의 잎은 정수·None·ToolKind 리터럴·이 모듈의 세 데이터 클래스뿐이다(자유 문자열 0)."""

    EXPORTED_CLASSES = (hub_activity.ToolKindCounts, hub_activity.BackgroundOutputView, hub_activity.SubagentActivity)

    def _leaf_types(self, annotation: object) -> list[object]:
        origin = typing.get_origin(annotation)
        if origin is typing.Literal:
            return [annotation]
        if origin is not None:
            return [leaf for argument in typing.get_args(annotation) for leaf in self._leaf_types(argument)]
        if annotation in self.EXPORTED_CLASSES:
            return [leaf for hint in typing.get_type_hints(annotation).values() for leaf in self._leaf_types(hint)]
        return [annotation]

    def test_la_c1_leaf_types_hold_no_free_text(self) -> None:
        allowed_literal = typing.Literal[hub_activity.TOOL_KINDS]
        for exported_class in self.EXPORTED_CLASSES:
            for field_name, hint in typing.get_type_hints(exported_class).items():
                for leaf in self._leaf_types(hint):
                    with self.subTest(exported_class=exported_class.__name__, field=field_name):
                        self.assertTrue(leaf in (int, type(None), allowed_literal) or leaf in self.EXPORTED_CLASSES, leaf)

    def test_la_c1_tool_kind_literal_equals_the_kind_tuple(self) -> None:
        self.assertEqual(typing.get_args(hub_activity.ToolKind), hub_activity.TOOL_KINDS)

    def test_la_c1_every_contract_class_is_frozen(self) -> None:
        for contract_class in (*self.EXPORTED_CLASSES, hub_activity.LiveActivity):
            with self.subTest(contract_class=contract_class.__name__):
                self.assertTrue(dataclasses.is_dataclass(contract_class))
                self.assertTrue(contract_class.__dataclass_params__.frozen)

    def test_la_c1_counts_cover_exactly_the_kind_tuple(self) -> None:
        field_names = tuple(field.name for field in dataclasses.fields(hub_activity.ToolKindCounts))

        self.assertEqual(field_names, hub_activity.TOOL_KINDS)

    def test_new_trailing_fields_have_defaults_so_existing_constructions_stay_valid(self) -> None:
        field_defaults = {field.name: field.default for field in dataclasses.fields(hub_activity.SubagentActivity)}

        self.assertIsNone(field_defaults["stall_suspect_at_ms"])
        self.assertIsNone(field_defaults["background_output"])
        self.assertEqual(
            tuple(field_defaults)[-2:], ("stall_suspect_at_ms", "background_output")
        )


if __name__ == "__main__":
    unittest.main()
