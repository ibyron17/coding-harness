"""hub_parse.py 단위 테스트 — JSONL 이벤트 파서·축약기·스냅샷 합성.

docs/prps/dashboard-into-hub.md M2(HD5~HD8)가 HTML DOM 파서를 걷어내고 이 파일을
JSONL 기반으로 재작성했다. `ParseEventLinesTest`·`DerivePhaseStatesTest` 는
tests/hub/test_hub_dashboard_render.py 에서 그대로 옮겨졌다(검증 로직 불변, 참조만
hub_parse.* 로 재조준) — 그 두 함수의 생산자·소비자가 모두 이 모듈로 모였기 때문이다.
"""

import contextlib
import dataclasses
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_parse  # noqa: E402  (sys.path 조정 후 임포트)

_BASE_TIME_MS = 1789963200000  # 2026-09-21 04:00:00 UTC
_MINUTE_MS = 60_000


def _time_at(minute_offset: int) -> int:
    return _BASE_TIME_MS + minute_offset * _MINUTE_MS


def _jsonl(*event_dicts: dict) -> str:
    """이벤트 dict 목록 → JSONL 본문(줄마다 하나, ensure_ascii=False)."""
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in event_dicts)


def _init_dict(minute_offset: int, title: str, phases: list, project: str = "coding-harness") -> dict:
    return {"time_ms": _time_at(minute_offset), "kind": "init", "title": title, "phases": phases, "project": project}


def _log_dict(minute_offset: int, kind: str, summary: str, detail: str = "") -> dict:
    return {"time_ms": _time_at(minute_offset), "kind": kind, "summary": summary, "detail": detail}


def _step_dict(minute_offset: int, index: int, state: str) -> dict:
    return {"time_ms": _time_at(minute_offset), "kind": "step", "index": index, "state": state}


@contextlib.contextmanager
def _forced_timezone(tz_name: str):
    """블록 동안만 프로세스 TZ 를 고정한다(H4 회귀 검증 전용, tests/hub/test_hub_dashboard_render.py
    의 동명 헬퍼와 같다) — 호스트 시간대와 무관하게 로컬 시간 포맷 단언을 결정적으로 만든다.
    time.tzset() 은 POSIX 전용(이 저장소는 macOS·Linux 만 지원)."""
    original_tz = os.environ.get("TZ")
    os.environ["TZ"] = tz_name
    time.tzset()
    try:
        yield
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time.tzset()


class ParseEventLinesTest(unittest.TestCase):
    """parse_event_lines — 줄 단위 fail-open, 마지막 init 이후만 유효."""

    def test_skips_malformed_json_line(self) -> None:
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"])) + "\n{not json\n"

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_skips_unknown_kind(self) -> None:
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"])) + "\n" + json.dumps({"time_ms": 1, "kind": "bogus"})

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_skips_line_with_wrong_field_type(self) -> None:
        broken = {"time_ms": _time_at(1), "kind": "impl", "summary": 123, "detail": ""}
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"])) + "\n" + json.dumps(broken)

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_skips_line_with_time_ms_above_range(self) -> None:
        """H2 회귀 — time_ms 가 sanity 상한을 벗어난 줄은 그 줄만 건너뛴다."""
        corrupted = {"time_ms": 99999999999999999, "kind": "impl", "summary": "손상된 시각", "detail": ""}
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"])) + "\n" + json.dumps(corrupted)

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_skips_line_with_time_ms_below_range(self) -> None:
        """H2 회귀 — 하한 미만(음수 등)도 같은 이유로 그 줄만 건너뛴다."""
        corrupted = {"time_ms": -1, "kind": "impl", "summary": "손상된 시각", "detail": ""}
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"])) + "\n" + json.dumps(corrupted)

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)

    def test_no_init_returns_empty_tuple(self) -> None:
        text = _jsonl(_log_dict(0, "impl", "요약"))

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(events, ())

    def test_multiple_inits_keeps_only_after_last(self) -> None:
        text = _jsonl(
            _init_dict(0, "옛 제목", ["구현", "검수"]),
            _log_dict(1, "impl", "옛 작업"),
            _init_dict(2, "새 제목", ["설계", "구현"]),
        )

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "새 제목")

    def test_summary_with_unicode_line_separator_is_preserved(self) -> None:
        """재검수 MEDIUM 회귀 — summary 에 U+2028(LINE SEPARATOR)이 있어도 그 이벤트가
        사라지지 않는다(수정 전 실측: str.splitlines() 가 이 문자로도 줄을 쪼개 양쪽 다
        json.loads 에 실패, impl 이벤트가 통째로 소실됐다 — kind 목록이 ['init'] 뿐이었다)."""
        text = _jsonl(
            _init_dict(0, "제목", ["구현", "검수"]),
            _log_dict(1, "impl", "한글 요약 줄바꿈 문자 포함"),
        )

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 2)
        self.assertEqual([event.kind for event in events], ["init", "impl"])

    def test_summary_with_unicode_paragraph_separator_is_preserved(self) -> None:
        """위와 같은 회귀, U+2029(PARAGRAPH SEPARATOR)."""
        text = _jsonl(
            _init_dict(0, "제목", ["구현", "검수"]),
            _log_dict(1, "impl", "한글 요약 줄바꿈 문자 포함"),
        )

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 2)
        self.assertEqual([event.kind for event in events], ["init", "impl"])


class ParserNeverRaisesOnPathologicalInputTest(unittest.TestCase):
    """재검수 2회차 RA1 — 계약 B(hub_session_facts.parse_event_line·hub_live_session.
    parse_live_session_record 와 동형, "어떤 입력에도 예외를 던지지 않는다")를 병리적 입력
    표로 고정한다(선례: hub_live_session.py 의 동명 클래스). 신설 당시 `except
    json.JSONDecodeError` 뿐이었던 _parse_single_event_line 은 실제로 "5000자리 정수"에서
    ValueError 를, "5000단 중첩"에서 RecursionError 를, "리스트 kind"·"리스트 state"에서
    멤버십 검사(`in`)가 TypeError(unhashable type)를 던졌다 — 넷 다 그 줄만 버려지지 않고
    parse_event_lines 밖으로 새어나가 collect_snapshot 전체를 죽였다(재검수 2회차 직접
    재현, 기준 커밋 7952146). "Infinity"·"1e300"·"bool index"는 예외는 없었지만
    "bool index"는 index=True 가 정수 1 로 통과해 step 이벤트가 조용히 등록되는 오판정이
    있었다 — 이 표는 그 조용한 오판정까지 함께 고정한다."""

    PATHOLOGICAL_LINES = (
        ("Infinity", '{"time_ms": Infinity, "kind": "impl", "summary": "s", "detail": ""}'),
        ("1e300", '{"time_ms": 1e300, "kind": "impl", "summary": "s", "detail": ""}'),
        ("5000자리 정수", '{"time_ms": ' + "9" * 5000 + ', "kind": "impl", "summary": "s", "detail": ""}'),
        ("5000단 중첩", "[" * 5000 + "]" * 5000),
        ("리스트 kind", '{"time_ms": 1700000000000, "kind": [], "summary": "s"}'),
        ("리스트 state", '{"time_ms": 1700000000000, "kind": "step", "index": 1, "state": []}'),
        ("bool index", '{"time_ms": 1700000000000, "kind": "step", "index": true, "state": "done"}'),
    )

    def test_pathological_line_is_skipped_without_raising(self) -> None:
        init_line = json.dumps(_init_dict(0, "제목", ["구현", "검수"]), ensure_ascii=False)
        for description, bad_line in self.PATHOLOGICAL_LINES:
            with self.subTest(description=description):
                text = init_line + "\n" + bad_line
                try:
                    events = hub_parse.parse_event_lines(text)
                except Exception as error:  # 계약 자체가 "무엇이 와도 던지지 않는다"다
                    self.fail(f"{description} 입력에서 예외 발생: {error!r}")
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0].kind, "init")


class InitPhaseCountLimitTest(unittest.TestCase):
    """재검수 2회차 RA3 — _parse_init_event 의 phases 길이 상한(_MAX_PHASE_COUNT).
    derive_phase_states 가 전이마다 단계 수 길이의 튜플을 새로 만들어 이벤트 수 × 단계 수에
    이차로 들기 때문에 둔 방어선이다(실측: 6000단계 × 6000줄 JSONL 파싱 1회 1.1초)."""

    def test_phase_count_at_the_limit_is_accepted(self) -> None:
        phases = ["단계%d" % i for i in range(hub_parse._MAX_PHASE_COUNT)]
        text = _jsonl(_init_dict(0, "제목", phases))

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(len(events), 1)
        self.assertEqual(len(events[0].phases), hub_parse._MAX_PHASE_COUNT)

    def test_phase_count_over_the_limit_is_rejected_as_no_init(self) -> None:
        phases = ["단계%d" % i for i in range(hub_parse._MAX_PHASE_COUNT + 1)]
        text = _jsonl(_init_dict(0, "제목", phases))

        events = hub_parse.parse_event_lines(text)

        self.assertEqual(events, ())


class DerivePhaseStatesTest(unittest.TestCase):
    """derive_phase_states — DN4 축약기(log 종류가 함의하는 전이 + step 명시 갱신)."""

    PHASES_FULL = ("설계", "승인", "구현", "검수")
    PHASES_SHORT = ("구현", "검수")

    def test_zero_events_first_phase_active(self) -> None:
        states = hub_parse.derive_phase_states(self.PHASES_FULL, ())

        self.assertEqual(states, ("active", "wait", "wait", "wait"))

    def test_standard_full_flow_completes_all_phases(self) -> None:
        events = tuple(
            hub_parse.parse_event_lines(
                _jsonl(
                    _init_dict(0, "제목", list(self.PHASES_FULL)),
                    _log_dict(1, "design", "설계 요약"),
                    _log_dict(2, "approve", "승인 요약"),
                    _log_dict(3, "impl", "구현 요약"),
                    _log_dict(4, "pass", "검수 통과"),
                )
            )
        )[1:]

        states = hub_parse.derive_phase_states(self.PHASES_FULL, events)

        self.assertEqual(states, ("done", "done", "done", "done"))

    def test_shortened_flow_impl_then_pass(self) -> None:
        events = (
            hub_parse.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="구현 요약"),
            hub_parse.DashboardEvent(time_ms=_time_at(2), kind="pass", summary="검수 통과"),
        )

        states = hub_parse.derive_phase_states(self.PHASES_SHORT, events)

        self.assertEqual(states, ("done", "done"))

    def test_impl_alone_marks_earlier_named_phases_done(self) -> None:
        """앞 단계 생략 — `impl` 만 기록해도 설계·승인이 완료로 파생된다."""
        events = (hub_parse.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="구현 요약"),)

        states = hub_parse.derive_phase_states(self.PHASES_FULL, events)

        self.assertEqual(states, ("done", "done", "done", "active"))

    def test_fail_reopens_implementation_and_reverts_review(self) -> None:
        """fail 회귀 — impl→fail 로 구현이 다시 active, 검수는 wait 로 돌아간다."""
        events = (
            hub_parse.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="구현 요약"),
            hub_parse.DashboardEvent(time_ms=_time_at(2), kind="fail", summary="검수 실패"),
        )

        states = hub_parse.derive_phase_states(self.PHASES_FULL, events)

        self.assertEqual(states, ("done", "done", "active", "wait"))

    def test_fail_then_impl_then_pass_completes_again(self) -> None:
        events = (
            hub_parse.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="구현 요약 1"),
            hub_parse.DashboardEvent(time_ms=_time_at(2), kind="fail", summary="검수 실패"),
            hub_parse.DashboardEvent(time_ms=_time_at(3), kind="impl", summary="구현 요약 2"),
            hub_parse.DashboardEvent(time_ms=_time_at(4), kind="pass", summary="검수 통과"),
        )

        states = hub_parse.derive_phase_states(self.PHASES_FULL, events)

        self.assertEqual(states, ("done", "done", "done", "done"))

    def test_unnamed_phase_kind_is_ignored(self) -> None:
        """목록에 없는 단계명 종류는 무시 — 축약 목록에는 '설계' 가 없다."""
        events = (hub_parse.DashboardEvent(time_ms=_time_at(1), kind="design", summary="무시됨"),)

        states = hub_parse.derive_phase_states(self.PHASES_SHORT, events)

        self.assertEqual(states, ("active", "wait"))

    def test_repeated_event_is_idempotent(self) -> None:
        single = (hub_parse.DashboardEvent(time_ms=_time_at(1), kind="impl", summary="구현 요약"),)
        repeated = single * 2

        self.assertEqual(
            hub_parse.derive_phase_states(self.PHASES_FULL, single),
            hub_parse.derive_phase_states(self.PHASES_FULL, repeated),
        )

    def test_step_event_updates_only_its_own_index(self) -> None:
        """비표준 단계 목록 전용 명시 갱신 — 다른 인덱스는 그대로 남는다."""
        custom_phases = ("원인 분석", "설계", "구현", "검수")
        events = (hub_parse.DashboardEvent(time_ms=_time_at(1), kind="step", index=1, state="done"),)

        states = hub_parse.derive_phase_states(custom_phases, events)

        self.assertEqual(states, ("done", "wait", "wait", "wait"))

    def test_step_event_with_out_of_range_index_is_ignored(self) -> None:
        events = (hub_parse.DashboardEvent(time_ms=_time_at(1), kind="step", index=99, state="done"),)

        states = hub_parse.derive_phase_states(self.PHASES_FULL, events)

        self.assertEqual(states, ("active", "wait", "wait", "wait"))


class IsCommitLoggedAfterLastPassTest(unittest.TestCase):
    """is_commit_logged_after_last_pass — 마지막 pass 뒤에 commit 이 있는가(결정 LM6)."""

    @staticmethod
    def _events_of(*kinds: str) -> tuple[hub_parse.DashboardEvent, ...]:
        return tuple(
            hub_parse.DashboardEvent(time_ms=_time_at(minute), kind=kind, summary="요약")
            for minute, kind in enumerate(kinds, start=1)
        )

    def test_no_pass_is_not_committed(self) -> None:
        self.assertFalse(hub_parse.is_commit_logged_after_last_pass(self._events_of("design", "impl")))

    def test_pass_alone_is_not_committed(self) -> None:
        self.assertFalse(hub_parse.is_commit_logged_after_last_pass(self._events_of("impl", "pass")))

    def test_pass_then_commit_is_committed(self) -> None:
        self.assertTrue(hub_parse.is_commit_logged_after_last_pass(self._events_of("pass", "commit")))

    def test_pass_note_commit_is_committed(self) -> None:
        self.assertTrue(hub_parse.is_commit_logged_after_last_pass(self._events_of("pass", "note", "commit")))

    def test_pass_commit_note_is_committed(self) -> None:
        self.assertTrue(hub_parse.is_commit_logged_after_last_pass(self._events_of("pass", "commit", "note")))

    def test_commit_before_a_later_pass_is_not_committed(self) -> None:
        """재검수를 다시 통과한 뒤에는 커밋 전이다 — 앞선 commit 은 마지막 pass 보다 앞이다."""
        events = self._events_of("pass", "commit", "fail", "impl", "pass")

        self.assertFalse(hub_parse.is_commit_logged_after_last_pass(events))

    def test_commit_without_any_pass_is_not_committed(self) -> None:
        self.assertFalse(hub_parse.is_commit_logged_after_last_pass(self._events_of("commit")))

    def test_empty_events_is_not_committed(self) -> None:
        self.assertFalse(hub_parse.is_commit_logged_after_last_pass(()))


class IsApprovalStepActiveTest(unittest.TestCase):
    """is_approval_step_active — 「승인」 단계가 진행중인가(결정 AW2, docs/prps/hub-approval-wait-badge.md).
    이벤트 열 → snapshot_from_events(...).steps → 판정. 이름이 곧 사례다."""

    FULL = ["설계", "승인", "구현", "검수"]
    SHORT = ["구현", "검수"]

    def _steps_of(self, phases: list, *event_dicts: dict) -> tuple[hub_parse.StepView, ...]:
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", phases), *event_dicts))
        return hub_parse.snapshot_from_events(events).steps

    def _is_active(self, phases: list, *event_dicts: dict) -> bool:
        return hub_parse.is_approval_step_active(self._steps_of(phases, *event_dicts))

    def test_init_only_has_design_active_not_approval(self) -> None:
        self.assertFalse(self._is_active(self.FULL))

    def test_design_makes_approval_active(self) -> None:
        self.assertTrue(self._is_active(self.FULL, _log_dict(1, "design", "설계 완료")))

    def test_note_after_design_keeps_approval_active(self) -> None:
        self.assertTrue(self._is_active(self.FULL, _log_dict(1, "design", "설계"), _log_dict(2, "note", "메모")))

    def test_approve_ends_approval(self) -> None:
        self.assertFalse(self._is_active(self.FULL, _log_dict(1, "design", "설계"), _log_dict(2, "approve", "승인")))

    def test_impl_without_approve_ends_approval(self) -> None:
        """approve 누락 — impl 이 승인까지 done 으로 만든다."""
        self.assertFalse(self._is_active(self.FULL, _log_dict(1, "design", "설계"), _log_dict(2, "impl", "구현")))

    def test_fail_after_impl_leaves_implementation_active_not_approval(self) -> None:
        events = (
            _log_dict(1, "design", "설계"), _log_dict(2, "approve", "승인"),
            _log_dict(3, "impl", "구현"), _log_dict(4, "fail", "검수 실패"),
        )

        self.assertFalse(self._is_active(self.FULL, *events))

    def test_abbreviated_path_never_has_an_approval_step(self) -> None:
        for label, events in (
            ("init only", ()),
            ("impl", (_log_dict(1, "impl", "구현"),)),
            ("fail", (_log_dict(1, "impl", "구현"), _log_dict(2, "fail", "실패"))),
            ("pass", (_log_dict(1, "impl", "구현"), _log_dict(2, "pass", "통과"))),
        ):
            with self.subTest(label):
                self.assertFalse(self._is_active(self.SHORT, *events))

    def test_non_standard_list_follows_step_events(self) -> None:
        phases = ["조사", "승인", "실행"]
        base = (_step_dict(1, 1, "done"), _step_dict(2, 2, "active"))

        self.assertTrue(self._is_active(phases, *base))
        self.assertFalse(self._is_active(phases, *base, _step_dict(3, 2, "done")))

    def test_step_named_differently_is_not_approval(self) -> None:
        """「확인」 같은 다른 이름은 승인으로 추정하지 않는다."""
        self.assertFalse(self._is_active(["분석", "확인", "실행"], _step_dict(1, 2, "active")))

    def test_second_approval_step_counts(self) -> None:
        phases = ["설계", "승인", "구현", "승인", "배포"]
        events = (_log_dict(1, "design", "설계"), _log_dict(2, "approve", "승인"), _log_dict(3, "impl", "구현"))

        self.assertTrue(self._is_active(phases, *events))

    def test_standard_flow_pass_ends_approval(self) -> None:
        self.assertFalse(self._is_active(self.FULL, _log_dict(1, "design", "설계"), _log_dict(2, "pass", "통과")))

    def test_empty_steps_is_false(self) -> None:
        self.assertFalse(hub_parse.is_approval_step_active(()))


class SnapshotFromEventsTest(unittest.TestCase):
    """snapshot_from_events — 이벤트 열 → Tier1Snapshot(hub/README.md 「데이터 모델」 대응표)."""

    def test_standard_full_flow_reads_four_of_four_done(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "전체 경로 완료", ["설계", "승인", "구현", "검수"]),
                _log_dict(1, "design", "설계 요약"),
                _log_dict(2, "approve", "승인 요약"),
                _log_dict(3, "impl", "구현 요약"),
                _log_dict(4, "pass", "검수 통과"),
            )
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.title, "전체 경로 완료")
        self.assertEqual((snapshot.completed, snapshot.total, snapshot.percent), (4, 4, 100))
        self.assertEqual([step.state for step in snapshot.steps], ["done", "done", "done", "done"])
        self.assertEqual([step.name for step in snapshot.steps], ["설계", "승인", "구현", "검수"])

    def test_fail_regression_leaves_active_and_wait_with_latest_summary_as_detail(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "축약 경로", ["구현", "검수"]),
                _log_dict(1, "impl", "1차 구현"),
                _log_dict(2, "fail", "1차 검수 실패", "상세 이유"),
            )
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual((snapshot.completed, snapshot.total), (0, 2))
        self.assertEqual(snapshot.steps[0].state, "active")
        self.assertEqual(snapshot.steps[0].detail, "1차 검수 실패")
        self.assertEqual(snapshot.steps[1].state, "wait")
        self.assertEqual(snapshot.steps[1].detail, "")

    def test_abbreviated_path_in_progress_reads_partial_completion(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "구현 진행중", ["구현", "검수"]), _log_dict(1, "impl", "구현 완료"))
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual((snapshot.completed, snapshot.total, snapshot.percent), (1, 2, 50))
        self.assertEqual(snapshot.steps[0].state, "done")
        self.assertEqual(snapshot.steps[1].state, "active")

    def test_impl_only_marks_earlier_named_phases_done(self) -> None:
        """앞 단계 생략 — `impl` 만 기록해도 설계·승인이 완료로 파생돼 스냅샷에 반영된다."""
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["설계", "승인", "구현", "검수"]), _log_dict(1, "impl", "구현 요약"))
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual([step.state for step in snapshot.steps], ["done", "done", "done", "active"])

    def test_non_standard_phase_list_is_updated_by_step_events(self) -> None:
        """비표준 단계 목록 — `step` 이벤트로만 진행률이 갱신된다."""
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "제목", ["원인 분석", "설계", "구현", "검수"]),
                _step_dict(1, 1, "done"),
                _step_dict(2, 2, "active"),
            )
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual([step.state for step in snapshot.steps], ["done", "active", "wait", "wait"])

    def test_zero_events_first_phase_is_active(self) -> None:
        """init 뿐이고 로그가 없으면 첫 단계만 active."""
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["구현", "검수"])))

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual((snapshot.completed, snapshot.total), (0, 2))
        self.assertEqual([step.state for step in snapshot.steps], ["active", "wait"])

    def test_percent_rounds_two_of_three_to_67_not_66(self) -> None:
        """H3 회귀 — 비표준 3단계에서 버림(66%)이 아니라 반올림(67%)이어야 한다."""
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["가", "나", "다"]), _step_dict(1, 1, "done"), _step_dict(2, 2, "done"))
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.percent, 67)

    def test_percent_rounds_one_of_six_to_17_not_16(self) -> None:
        """H3 회귀 — 비표준 6단계에서 버림(16%)이 아니라 반올림(17%)이어야 한다."""
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["a", "b", "c", "d", "e", "f"]), _step_dict(1, 1, "done"))
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.percent, 17)

    def test_title_is_kept_raw_without_html_escaping(self) -> None:
        """title 원문 — `&`·`<` 가 이스케이프되지 않는다(렌더 시점에만 이스케이프한다)."""
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "A & B <T>", ["구현", "검수"])))

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.title, "A & B <T>")

    def test_task_started_at_ms_equals_init_event_time(self) -> None:
        """HD8 — 작업 시작 시각은 init 이벤트의 time_ms 다(사이드카 mtime 이 아니다)."""
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["구현", "검수"])))

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.task_started_at_ms, events[0].time_ms)

    def test_updated_text_uses_the_last_event_time_via_format_event_updated_label(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(_init_dict(0, "제목", ["구현", "검수"]), _log_dict(3, "impl", "작업 완료"))
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.updated_text, hub_parse.format_event_updated_label(events[-1].time_ms))

    def test_constant_fields_stay_at_their_fixed_values(self) -> None:
        """소비자 없는 필드는 상수로 유지된다(HD6) — subtitle ""·matrix_done None·impl 0/0."""
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["구현", "검수"])))

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.subtitle, "")
        self.assertIsNone(snapshot.matrix_done)
        self.assertEqual((snapshot.impl_done, snapshot.impl_total), (0, 0))

    def test_is_committed_is_true_when_commit_follows_the_last_pass(self) -> None:
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "제목", ["구현", "검수"]),
                _log_dict(1, "impl", "구현"),
                _log_dict(2, "pass", "통과"),
                _log_dict(3, "commit", "커밋 제목"),
            )
        )

        self.assertTrue(hub_parse.snapshot_from_events(events).is_committed)

    def test_is_committed_is_false_between_pass_and_commit(self) -> None:
        """검수 통과 뒤·커밋 전 구간 — 4/4 · 100% 인데 아직 커밋 기록이 없다(결정 LM6)."""
        events = hub_parse.parse_event_lines(
            _jsonl(
                _init_dict(0, "제목", ["구현", "검수"]),
                _log_dict(1, "impl", "구현"),
                _log_dict(2, "pass", "통과"),
            )
        )

        snapshot = hub_parse.snapshot_from_events(events)

        self.assertEqual(snapshot.percent, 100)
        self.assertFalse(snapshot.is_committed)

    def test_is_committed_key_is_present_in_the_serialized_snapshot(self) -> None:
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["구현", "검수"])))

        serialized = dataclasses.asdict(hub_parse.snapshot_from_events(events))

        self.assertIn("is_committed", serialized)
        self.assertIs(serialized["is_committed"], False)

    def test_is_approval_step_active_is_true_after_design_and_false_after_approve(self) -> None:
        init = _init_dict(0, "제목", ["설계", "승인", "구현", "검수"])
        design = _log_dict(1, "design", "설계")
        approve = _log_dict(2, "approve", "승인")

        after_design = hub_parse.snapshot_from_events(hub_parse.parse_event_lines(_jsonl(init, design)))
        after_approve = hub_parse.snapshot_from_events(hub_parse.parse_event_lines(_jsonl(init, design, approve)))

        self.assertTrue(after_design.is_approval_step_active)
        self.assertFalse(after_approve.is_approval_step_active)

    def test_is_approval_step_active_key_is_present_in_the_serialized_snapshot(self) -> None:
        events = hub_parse.parse_event_lines(_jsonl(_init_dict(0, "제목", ["구현", "검수"])))

        serialized = dataclasses.asdict(hub_parse.snapshot_from_events(events))

        self.assertIn("is_approval_step_active", serialized)
        self.assertIs(serialized["is_approval_step_active"], False)


class ParseDashboardJsonlTest(unittest.TestCase):
    """parse_dashboard_jsonl — snapshot_from_events(parse_event_lines(text)) 의 얇은 합성."""

    def test_no_init_returns_none(self) -> None:
        text = _jsonl(_log_dict(0, "impl", "요약"))

        self.assertIsNone(hub_parse.parse_dashboard_jsonl(text))

    def test_broken_line_among_valid_ones_is_fail_open(self) -> None:
        """깨진 줄 fail-open — 한 줄이 깨져도 나머지로 정상 스냅샷을 만든다."""
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"])) + "\n{not json\n" + _jsonl(_log_dict(1, "impl", "완료"))

        snapshot = hub_parse.parse_dashboard_jsonl(text)

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.steps[0].state, "done")
        self.assertEqual(snapshot.steps[1].state, "active")
        self.assertEqual(snapshot.steps[1].detail, "완료")

    def test_matches_snapshot_from_events_of_the_same_parsed_events(self) -> None:
        text = _jsonl(_init_dict(0, "제목", ["구현", "검수"]), _log_dict(1, "impl", "완료"))

        combined = hub_parse.parse_dashboard_jsonl(text)
        separate = hub_parse.snapshot_from_events(hub_parse.parse_event_lines(text))

        self.assertEqual(combined, separate)


class FormatEventUpdatedLabelTest(unittest.TestCase):
    """재검수 2회차 RB1 — format_event_updated_label 이 로컬 시간대를 쓰는지 하드코딩
    리터럴과 직접 대조한다. SnapshotFromEventsTest·hub_dashboard_render 쪽의 위임 테스트
    3건은 전부 이 함수 자신으로 기대값을 만들어 비교해(예: `hub_parse.format_event_updated_
    label(events[-1].time_ms)`) 이 함수가 어떻게 망가져도 통과하는 순환 검증이었다 — 기준
    커밋 09cf358 의 test_hub_dashboard_render.py::
    test_updated_text_uses_local_timezone_not_hardcoded_utc(M2 재작성 중 유실된 H4 회귀)에서
    하드코딩 리터럴을 그대로 옮겨 이 순환을 끊는다. 이 함수를 UTC 로 고정한 미러로 같은
    단언을 돌리면 "갱신: 2026-09-21 04:00"이 나와 실패한다(재검수 2회차 직접 확인) — 공허한
    테스트가 아니다."""

    def test_updated_label_uses_local_timezone_not_hardcoded_utc(self) -> None:
        """UTC 로 고정돼 있었다면 Asia/Seoul 로 강제해도 04:00 이 나왔을 것이다."""
        with _forced_timezone("Asia/Seoul"):
            label = hub_parse.format_event_updated_label(_BASE_TIME_MS)

        # _BASE_TIME_MS = 2026-09-21 04:00:00 UTC → Asia/Seoul(UTC+9, DST 없음)로는 13:00
        self.assertEqual(label, "갱신: 2026-09-21 13:00")


if __name__ == "__main__":
    unittest.main()
