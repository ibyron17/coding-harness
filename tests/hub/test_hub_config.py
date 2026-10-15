"""hub_config.config_from_raw(★순수) 단위 테스트. 파일시스템 무접촉 —
config.json 을 실제로 읽는 이음매는 tests/hub/test_hub_collect.py::LoadConfigValidationTest
가 test_wrong_type_field_falls_back_to_default_with_warning 한 건으로 고정한다
(docs/prps/hub-collect-split-for-merge.md §6.3).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_config  # noqa: E402
import hub_model  # noqa: E402


class ConfigFromRawTest(unittest.TestCase):
    """검수 m4·m5, 결정 AR6 — config_from_raw(raw, defaults) 직접 호출.

    tests/hub/test_hub_collect.py::LoadConfigValidationTest 의 스키마 케이스를 이관했다
    (docs/prps/hub-collect-split-for-merge.md §6.3) — 파일 계약(부재·깨진 JSON)과
    load_config 위임 자체를 지키는 이음매 테스트만 그 파일에 남는다.
    """

    def setUp(self) -> None:
        self.defaults = hub_model.HubConfig()

    def test_deprecated_field_warns_with_replacement_guidance(self) -> None:
        """검수 m4 — 폐기된 serve_port_candidates 는 무시하되 대체 필드를 안내한다."""
        config, warnings = hub_config.config_from_raw(
            {"serve_port_candidates": [8794, 8795]}, self.defaults
        )
        self.assertEqual(config, self.defaults)
        self.assertTrue(
            any("serve_port_candidates" in warning and "server_port" in warning for warning in warnings)
        )

    def test_deprecated_collect_interval_field_warns_with_replacement_guidance(self) -> None:
        """개정 2 — 폐기된 server_collect_interval_seconds 는 무시하되
        server_heartbeat_interval_seconds 로 대체됐음을 안내하고, 나머지 필드는 정상 적용된다."""
        config, warnings = hub_config.config_from_raw(
            {"server_collect_interval_seconds": 5, "stale_after_minutes": 45}, self.defaults
        )
        self.assertEqual(config.stale_after_minutes, 45)
        self.assertEqual(
            config.server_heartbeat_interval_seconds, self.defaults.server_heartbeat_interval_seconds
        )
        self.assertTrue(
            any(
                "server_collect_interval_seconds" in warning and "server_heartbeat_interval_seconds" in warning
                for warning in warnings
            )
        )

    def test_heartbeat_interval_wrong_type_falls_back_to_default_with_warning(self) -> None:
        """개정 2 — server_heartbeat_interval_seconds 타입 오류 시 기본값으로 폴백한다.

        결정 AR6 케이스(e) — 타입이 안 맞아 제외된 필드는 _clamp_interval_overrides 가 보지
        못한다(그 필드가 overrides 에 아예 없다). 경고가 타입 경고 1건뿐이어야 이를 증명한다 —
        clamp 이 잘못 개입하면 2건이 된다."""
        config, warnings = hub_config.config_from_raw(
            {"server_heartbeat_interval_seconds": "five"}, self.defaults
        )
        self.assertEqual(
            config.server_heartbeat_interval_seconds, self.defaults.server_heartbeat_interval_seconds
        )
        self.assertTrue(any("server_heartbeat_interval_seconds" in warning for warning in warnings))
        self.assertEqual(len(warnings), 1)

    def test_unknown_field_warns_generically(self) -> None:
        """검수 m4 — 오타 등 진짜 알 수 없는 키도 조용히 무시되지 않는다."""
        _config, warnings = hub_config.config_from_raw({"scan_dpeth": 5}, self.defaults)
        self.assertTrue(any("scan_dpeth" in warning for warning in warnings))

    def test_case25_show_usage_panel_wrong_type_falls_back_to_default_with_warning(self) -> None:
        """케이스 25 — config.json 의 show_usage_panel:"yes" 는 기본값 True + 경고 1건."""
        config, warnings = hub_config.config_from_raw({"show_usage_panel": "yes"}, self.defaults)
        self.assertTrue(config.show_usage_panel)
        self.assertTrue(any("show_usage_panel" in warning for warning in warnings))

    def test_ac7_show_account_info_defaults_to_true(self) -> None:
        """결정 AC7(docs/prps/hub-usage-panel-account.md) — 기본값은 켜짐, 경고 없음."""
        config, warnings = hub_config.config_from_raw({}, self.defaults)
        self.assertTrue(config.show_account_info)
        self.assertEqual(warnings, ())

    def test_ac7_show_account_info_false_is_accepted(self) -> None:
        config, warnings = hub_config.config_from_raw({"show_account_info": False}, self.defaults)
        self.assertFalse(config.show_account_info)
        self.assertEqual(warnings, ())

    def test_ac7_show_account_info_wrong_type_falls_back_to_default_with_warning(self) -> None:
        config, warnings = hub_config.config_from_raw({"show_account_info": "no"}, self.defaults)
        self.assertTrue(config.show_account_info)
        self.assertEqual(len(warnings), 1)
        self.assertIn("show_account_info", warnings[0])

    def test_ar6_heartbeat_interval_below_minimum_is_clamped_with_warning(self) -> None:
        """결정 AR6 케이스(a) — 0 은 유지보수 티커(`_maintenance_loop`)의 `stop_event.wait(0)`
        을 busy loop 로 만든다. 하한(1초)으로 clamp 되고 경고에 필드명이 남아야 한다."""
        config, warnings = hub_config.config_from_raw(
            {"server_heartbeat_interval_seconds": 0}, self.defaults
        )
        self.assertEqual(
            config.server_heartbeat_interval_seconds, hub_config.MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS
        )
        self.assertTrue(any("server_heartbeat_interval_seconds" in warning for warning in warnings))

    def test_ar6_usage_api_poll_interval_below_minimum_is_clamped_with_warning(self) -> None:
        """결정 AR6 케이스(b) — 사용량 API 폴링 주기가 하한(60초) 미만이면 60초로 clamp 되고
        경고가 정확히 1건이어야 한다."""
        config, warnings = hub_config.config_from_raw(
            {"usage_api_poll_interval_seconds": 1}, self.defaults
        )
        self.assertEqual(
            config.usage_api_poll_interval_seconds, hub_config.MIN_USAGE_API_POLL_INTERVAL_SECONDS
        )
        self.assertEqual(len(warnings), 1)
        self.assertTrue(any("usage_api_poll_interval_seconds" in warning for warning in warnings))

    def test_ar6_no_override_leaves_defaults_untouched_without_clamp_warning(self) -> None:
        """결정 AR6 케이스(c) — override 가 없으면 clamp 은 손대지 않는다. `_clamp_interval_
        overrides` docstring 의 "override 가 없는 한 손대지 않는다" 주장을 고정한다."""
        config, warnings = hub_config.config_from_raw({}, self.defaults)
        self.assertEqual(
            config.server_heartbeat_interval_seconds, self.defaults.server_heartbeat_interval_seconds
        )
        self.assertEqual(
            config.usage_api_poll_interval_seconds, self.defaults.usage_api_poll_interval_seconds
        )
        self.assertEqual(warnings, ())

    def test_ar6_boundary_values_at_minimum_are_not_clamped(self) -> None:
        """결정 AR6 케이스(d) — 하한값 자체(1초·60초)는 그대로 통과해야 한다(`<` vs `<=`
        off-by-one 가드)."""
        config, warnings = hub_config.config_from_raw(
            {"server_heartbeat_interval_seconds": 1, "usage_api_poll_interval_seconds": 60}, self.defaults
        )
        self.assertEqual(config.server_heartbeat_interval_seconds, 1)
        self.assertEqual(config.usage_api_poll_interval_seconds, 60)
        self.assertEqual(warnings, ())


class NotifyEnabledSwitchTest(unittest.TestCase):
    """결정 MN10(docs/prps/hub-macos-notification.md) — macOS 알림 스위치는 기본 꺼짐(옵트인)이다."""

    def test_defaults_to_off(self) -> None:
        self.assertFalse(hub_model.HubConfig().notify_enabled)

    def test_config_json_can_turn_it_on(self) -> None:
        config, warnings = hub_config.config_from_raw({"notify_enabled": True}, hub_model.HubConfig())
        self.assertTrue(config.notify_enabled)
        self.assertEqual(warnings, ())

    def test_wrong_type_falls_back_to_default_with_warning(self) -> None:
        config, warnings = hub_config.config_from_raw({"notify_enabled": "yes"}, hub_model.HubConfig())
        self.assertFalse(config.notify_enabled)
        self.assertEqual(len(warnings), 1)
        self.assertIn("notify_enabled", warnings[0])


if __name__ == "__main__":
    unittest.main()
