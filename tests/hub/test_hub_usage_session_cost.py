"""hub_usage 의 세션 비용 캡처(⑨) 단위 테스트 — docs/prps/harness-benchmark-adoption.md §10-1.

statusLine stdin 1건에서 한도 캡처와 세션 비용 캡처를 한 번에 파는 `parse_status_line_captures`,
캡처 파일을 되읽는 `parse_session_cost_capture`, 쓰기 억제 비교 `same_session_cost_values`,
파일 이름 키 검증 `is_valid_session_id` 를 다룬다. 한도 캡처 쪽 기존 테스트는 test_hub_usage.py 에 있다
(그 파일이 800줄을 넘지 않게 이 파일로 나눴다).
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_usage  # noqa: E402  (sys.path 조정 후 임포트)

BASE_TIME_MS = 1_786_433_123_899
RATE_LIMIT_CAPTURED_AT_MS = 1_786_433_120_000
RATE_LIMIT_CAPTURED_AT_S = RATE_LIMIT_CAPTURED_AT_MS // 1000
ONE_HOUR_SECONDS = 60 * 60
SESSION_ID = "0a1b2c3d-4e5f-6789-abcd-ef0123456789"


def _resets_at_s(hours_from_capture: float) -> int:
    return RATE_LIMIT_CAPTURED_AT_S + int(hours_from_capture * ONE_HOUR_SECONDS)


def _rate_limits(five_hour_percent=None, seven_day_percent=None) -> dict:
    """statusLine 의 rate_limits 객체. 퍼센트를 준 창만 담는다(리셋 시각은 캡처 시각 기준 2시간·48시간 뒤)."""
    rate_limits: dict = {}
    if five_hour_percent is not None:
        rate_limits["five_hour"] = {"used_percentage": five_hour_percent, "resets_at": _resets_at_s(2)}
    if seven_day_percent is not None:
        rate_limits["seven_day"] = {"used_percentage": seven_day_percent, "resets_at": _resets_at_s(48)}
    return rate_limits


def _session_cost_stdin(session_id=SESSION_ID, cost=None, context_window=None, rate_limits=None) -> str:
    payload: dict = {}
    for key, value in (
        ("session_id", session_id), ("cost", cost),
        ("context_window", context_window), ("rate_limits", rate_limits),
    ):
        if value is not None:
            payload[key] = value
    return json.dumps(payload)


def _normal_cost_stdin() -> str:
    return _session_cost_stdin(
        cost={"total_cost_usd": 12.849, "total_api_duration_ms": 31 * 60_000 + 30_000},
        context_window={"used_percentage": 62.9},
    )


class ParseStatusLineCapturesTest(unittest.TestCase):
    """statusLine stdin 1건에서 한도 캡처와 세션 비용 캡처를 한 번에 판다."""

    def test_normal_input_floors_cents_minutes_and_percent(self) -> None:
        captures = hub_usage.parse_status_line_captures(_normal_cost_stdin(), BASE_TIME_MS)
        self.assertEqual(
            captures.session_cost,
            hub_usage.SessionCostCapture(
                SESSION_ID,
                hub_usage.SessionCost(
                    captured_at_ms=BASE_TIME_MS, total_cost_cents=1284,
                    api_duration_minutes=31, context_used_percent=62,
                ),
            ),
        )

    def test_float_noise_does_not_lose_a_cent(self) -> None:
        text = _session_cost_stdin(cost={"total_cost_usd": 0.29})  # 0.29 * 100 == 28.999999999999996
        self.assertEqual(hub_usage.parse_status_line_captures(text, BASE_TIME_MS).session_cost.cost.total_cost_cents, 29)

    def test_each_capture_can_be_absent_independently(self) -> None:
        rate_limits = _rate_limits(five_hour_percent=10)
        only_rate = hub_usage.parse_status_line_captures(
            _session_cost_stdin(rate_limits=rate_limits), RATE_LIMIT_CAPTURED_AT_MS)
        only_cost = hub_usage.parse_status_line_captures(_normal_cost_stdin(), RATE_LIMIT_CAPTURED_AT_MS)
        both = hub_usage.parse_status_line_captures(
            _session_cost_stdin(cost={"total_cost_usd": 1}, rate_limits=rate_limits), RATE_LIMIT_CAPTURED_AT_MS)
        self.assertEqual((only_rate.rate_limits is None, only_rate.session_cost is None), (False, True))
        self.assertEqual((only_cost.rate_limits is None, only_cost.session_cost is None), (True, False))
        self.assertEqual((both.rate_limits is None, both.session_cost is None), (False, False))
        self.assertEqual(hub_usage.parse_status_line_captures("{}", BASE_TIME_MS), hub_usage.StatusLineCaptures(None, None))

    def test_non_object_json_gives_two_nones(self) -> None:
        for text in ("{not json", "[]", "", "12"):
            self.assertEqual(
                hub_usage.parse_status_line_captures(text, BASE_TIME_MS), hub_usage.StatusLineCaptures(None, None), text)

    def test_session_id_that_is_not_a_lowercase_uuid_drops_the_session_cost(self) -> None:
        for bad_session_id in ("../x", SESSION_ID.upper(), "", SESSION_ID + "\n", "a/b", None):
            text = _session_cost_stdin(session_id=bad_session_id, cost={"total_cost_usd": 1})
            self.assertIsNone(hub_usage.parse_status_line_captures(text, BASE_TIME_MS).session_cost, bad_session_id)

    def test_invalid_cost_values_drop_that_field_only(self) -> None:
        bad_values = (-1, float("nan"), float("inf"), True, hub_usage.SESSION_COST_MAX_USD + 1, "12")
        for bad_value in bad_values:
            text = _session_cost_stdin(cost={"total_cost_usd": bad_value}, context_window={"used_percentage": 40})
            cost = hub_usage.parse_status_line_captures(text, BASE_TIME_MS).session_cost.cost
            self.assertIsNone(cost.total_cost_cents, bad_value)
            self.assertEqual(cost.context_used_percent, 40)

    def test_invalid_api_duration_drops_that_field_only(self) -> None:
        """터무니없이 큰 값(1e308 등)·음수·NaN·bool·문자열은 그대로 저장·표시되지 않는다 — 그 필드만 탈락한다."""
        bad_values = (1e308, 10**400, -1, float("nan"), float("inf"), True, "5", hub_usage.SESSION_API_DURATION_MAX_MS + 60_000)
        for bad_value in bad_values:
            text = _session_cost_stdin(
                cost={"total_cost_usd": 2, "total_api_duration_ms": bad_value}, context_window={"used_percentage": 40})
            cost = hub_usage.parse_status_line_captures(text, BASE_TIME_MS).session_cost.cost
            self.assertIsNone(cost.api_duration_minutes, bad_value)
            self.assertEqual((cost.total_cost_cents, cost.context_used_percent), (200, 40))

    def test_api_duration_at_the_cap_is_still_accepted(self) -> None:
        text = _session_cost_stdin(cost={"total_api_duration_ms": hub_usage.SESSION_API_DURATION_MAX_MS})
        cost = hub_usage.parse_status_line_captures(text, BASE_TIME_MS).session_cost.cost
        self.assertEqual(cost.api_duration_minutes, hub_usage.SESSION_API_DURATION_MAX_MINUTES)

    def test_all_three_values_invalid_gives_no_session_cost(self) -> None:
        text = _session_cost_stdin(
            cost={"total_cost_usd": -1, "total_api_duration_ms": -5}, context_window={"used_percentage": 101})
        self.assertIsNone(hub_usage.parse_status_line_captures(text, BASE_TIME_MS).session_cost)

    def test_rate_limits_match_the_legacy_single_purpose_parser(self) -> None:
        text = json.dumps({"rate_limits": _rate_limits(five_hour_percent=23.5, seven_day_percent=41)})
        self.assertEqual(
            hub_usage.parse_status_line_captures(text, RATE_LIMIT_CAPTURED_AT_MS).rate_limits,
            hub_usage.parse_status_line_rate_limits(text, RATE_LIMIT_CAPTURED_AT_MS),
        )


class ParseSessionCostCaptureTest(unittest.TestCase):
    """우리가 쓴 캡처 파일을 되읽는다. 계약 위반이면 예외가 아니라 None."""

    def _file_text(self, **overrides) -> str:
        values = {"captured_at_ms": BASE_TIME_MS, "total_cost_cents": 1284, "api_duration_minutes": 31, "context_used_percent": 62}
        values.update(overrides)
        return json.dumps(values)

    def test_round_trip_via_asdict_and_json(self) -> None:
        cost = hub_usage.SessionCost(BASE_TIME_MS, 1284, 31, 62)
        self.assertEqual(hub_usage.parse_session_cost_capture(json.dumps(dataclasses.asdict(cost))), cost)

    def test_contract_violations_give_none(self) -> None:
        violations = (
            {"captured_at_ms": None}, {"captured_at_ms": "1"}, {"total_cost_cents": -1}, {"total_cost_cents": 1.5},
            {"total_cost_cents": True}, {"api_duration_minutes": "3"}, {"context_used_percent": 101},
            {"context_used_percent": 62.5},
            {"total_cost_cents": hub_usage.SESSION_COST_MAX_CENTS + 1},
            {"api_duration_minutes": hub_usage.SESSION_API_DURATION_MAX_MINUTES + 1},
        )
        for overrides in violations:
            self.assertIsNone(hub_usage.parse_session_cost_capture(self._file_text(**overrides)), overrides)

    def test_values_at_the_caps_are_accepted(self) -> None:
        text = self._file_text(
            total_cost_cents=hub_usage.SESSION_COST_MAX_CENTS, api_duration_minutes=hub_usage.SESSION_API_DURATION_MAX_MINUTES)
        self.assertIsNotNone(hub_usage.parse_session_cost_capture(text))

    def test_missing_or_null_values_are_allowed_but_not_all_three(self) -> None:
        one_left = self._file_text(total_cost_cents=None, api_duration_minutes=None)
        self.assertEqual(hub_usage.parse_session_cost_capture(one_left), hub_usage.SessionCost(BASE_TIME_MS, None, None, 62))
        all_gone = self._file_text(total_cost_cents=None, api_duration_minutes=None, context_used_percent=None)
        self.assertIsNone(hub_usage.parse_session_cost_capture(all_gone))

    def test_broken_json_and_non_object_give_none(self) -> None:
        for text in ("{not json", "[]", ""):
            self.assertIsNone(hub_usage.parse_session_cost_capture(text), text)


class SameSessionCostValuesTest(unittest.TestCase):
    """0.3초 주기의 쓰기가 정상 상태에서 0회가 되게 하는 비교(captured_at_ms 는 뺀다)."""

    def test_previous_none_is_not_same(self) -> None:
        self.assertFalse(hub_usage.same_session_cost_values(None, hub_usage.SessionCost(1, 2, 3, 4)))

    def test_only_captured_at_differs_is_same(self) -> None:
        self.assertTrue(hub_usage.same_session_cost_values(hub_usage.SessionCost(1, 2, 3, 4), hub_usage.SessionCost(99, 2, 3, 4)))

    def test_any_value_differing_is_not_same(self) -> None:
        previous = hub_usage.SessionCost(1, 2, 3, 4)
        for current in (hub_usage.SessionCost(1, 9, 3, 4), hub_usage.SessionCost(1, 2, 9, 4), hub_usage.SessionCost(1, 2, 3, 9)):
            self.assertFalse(hub_usage.same_session_cost_values(previous, current), current)


class IsValidSessionIdTest(unittest.TestCase):
    def test_only_lowercase_uuid_is_valid(self) -> None:
        self.assertTrue(hub_usage.is_valid_session_id(SESSION_ID))
        for bad in (SESSION_ID.upper(), "../x", SESSION_ID + "\n", "", None, 12, SESSION_ID[:-1]):
            self.assertFalse(hub_usage.is_valid_session_id(bad), bad)


if __name__ == "__main__":
    unittest.main()
