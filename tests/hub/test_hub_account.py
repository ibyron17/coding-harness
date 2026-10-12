"""hub_account 단위 테스트. docs/prps/hub-usage-panel-account.md 「테스트 계획」 AT1~AT15.

실제 이메일·조직 이름은 어디에도 쓰지 않는다 — 합성 값(example.com 계열)과 센티넬만 쓴다.
"""

import dataclasses
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_account  # noqa: E402  (sys.path 조정 후 임포트)

SYNTHETIC_EMAIL = "dev.user@example.com"
SYNTHETIC_ORGANIZATION = "Example Labs"

# docs/prps/hub-usage-panel-account.md §2.1 이 적은 oauthAccount 키 20개(값은 옮기지 않는다).
OAUTH_ACCOUNT_KEYS = (
    "accountUuid", "emailAddress", "organizationUuid", "hasExtraUsageEnabled", "billingType",
    "accountCreatedAt", "subscriptionCreatedAt", "displayName", "organizationRole",
    "workspaceRole", "organizationName", "ccOnboardingFlags", "claudeCodeTrialEndsAt",
    "claudeCodeTrialDurationDays", "seatTier", "fullName", "profileFetchedAt",
    "organizationType", "organizationRateLimitTier", "userRateLimitTier",
)
EXTRACTED_KEYS = ("emailAddress", "organizationName", "organizationType")


def _document(oauth_account: object) -> str:
    return json.dumps({"numStartups": 3, "oauthAccount": oauth_account})


def _normal_account(**overrides: object) -> dict:
    account = {
        "organizationType": "claude_team",
        "organizationName": SYNTHETIC_ORGANIZATION,
        "emailAddress": SYNTHETIC_EMAIL,
    }
    account.update(overrides)
    return account


class ParseAccountInfoHappyPathTest(unittest.TestCase):
    """AT1~AT2 — 정상 추출과 요금제 대응표."""

    def test_at1_three_keys_become_account_info(self) -> None:
        info, reason = hub_account.parse_account_info(_document(_normal_account()))
        self.assertEqual(info, hub_account.AccountInfo("Claude Team", SYNTHETIC_ORGANIZATION, SYNTHETIC_EMAIL))
        self.assertIsNone(reason)

    def test_at2_each_known_organization_type_maps_to_cli_display_name(self) -> None:
        expected_by_type = {
            "claude_pro": "Claude Pro",
            "claude_max": "Claude Max",
            "claude_team": "Claude Team",
            "claude_enterprise": "Claude Enterprise",
        }
        for organization_type, expected_label in expected_by_type.items():
            with self.subTest(organization_type=organization_type):
                info, _ = hub_account.parse_account_info(
                    _document(_normal_account(organizationType=organization_type))
                )
                self.assertEqual(info.plan_label, expected_label)


class ParseAccountInfoFieldDropTest(unittest.TestCase):
    """AT3~AT7 — 일부 필드만 무효이면 그 필드만 None(필드 단위 탈락)."""

    def test_at3_unknown_organization_type_drops_only_plan_label(self) -> None:
        info, reason = hub_account.parse_account_info(
            _document(_normal_account(organizationType="claude_future"))
        )
        self.assertIsNone(info.plan_label)
        self.assertEqual(info.organization_name, SYNTHETIC_ORGANIZATION)
        self.assertEqual(info.email, SYNTHETIC_EMAIL)
        self.assertIsNone(reason)

    def test_at4_missing_null_number_or_bool_organization_type_drops_plan_label(self) -> None:
        missing = _normal_account()
        del missing["organizationType"]
        for label, account in (
            ("missing", missing),
            ("null", _normal_account(organizationType=None)),
            ("number", _normal_account(organizationType=7)),
            ("bool", _normal_account(organizationType=True)),
        ):
            with self.subTest(case=label):
                info, _ = hub_account.parse_account_info(_document(account))
                self.assertIsNone(info.plan_label)

    def test_at5_non_string_email_or_organization_drops_only_that_field(self) -> None:
        for bad_value in (123, ["a@example.com"], True, {"k": "v"}):
            with self.subTest(bad_value=bad_value):
                info, _ = hub_account.parse_account_info(
                    _document(_normal_account(emailAddress=bad_value))
                )
                self.assertIsNone(info.email)
                self.assertEqual(info.organization_name, SYNTHETIC_ORGANIZATION)
                info, _ = hub_account.parse_account_info(
                    _document(_normal_account(organizationName=bad_value))
                )
                self.assertIsNone(info.organization_name)
                self.assertEqual(info.email, SYNTHETIC_EMAIL)

    def test_at6_blank_values_drop_and_surrounding_whitespace_is_stripped(self) -> None:
        info, _ = hub_account.parse_account_info(
            _document(_normal_account(emailAddress="", organizationName="   "))
        )
        self.assertIsNone(info.email)
        self.assertIsNone(info.organization_name)
        info, _ = hub_account.parse_account_info(
            _document(_normal_account(emailAddress="  dev.user@example.com \n"))
        )
        self.assertEqual(info.email, "dev.user@example.com")

    def test_at7_length_boundary_256_kept_257_dropped(self) -> None:
        kept = "a" * hub_account.ACCOUNT_FIELD_MAX_CHARS
        dropped = "a" * (hub_account.ACCOUNT_FIELD_MAX_CHARS + 1)
        info, _ = hub_account.parse_account_info(_document(_normal_account(emailAddress=kept)))
        self.assertEqual(info.email, kept)
        info, _ = hub_account.parse_account_info(_document(_normal_account(emailAddress=dropped)))
        self.assertIsNone(info.email)
        info, _ = hub_account.parse_account_info(_document(_normal_account(organizationName=dropped)))
        self.assertIsNone(info.organization_name)


class ParseAccountInfoAbsenceAndContractTest(unittest.TestCase):
    """AT8~AT12 — 정상 부재는 사유 없음, 계약 불일치는 고정 사유 문구."""

    def test_at8_missing_oauth_account_key_is_normal_absence(self) -> None:
        self.assertEqual(hub_account.parse_account_info(json.dumps({"numStartups": 1})), (None, None))

    def test_at9_null_oauth_account_is_normal_absence(self) -> None:
        self.assertEqual(hub_account.parse_account_info(_document(None)), (None, None))

    def test_at10_non_object_oauth_account_is_contract_mismatch(self) -> None:
        for bad_account in ("a-string", ["list"], 5):
            with self.subTest(bad_account=bad_account):
                info, reason = hub_account.parse_account_info(_document(bad_account))
                self.assertIsNone(info)
                self.assertIsInstance(reason, str)
                self.assertTrue(reason)

    def test_at11_broken_json_top_level_list_or_empty_text_is_contract_mismatch(self) -> None:
        for text in ("{not json", "[1, 2]", ""):
            with self.subTest(text=text):
                info, reason = hub_account.parse_account_info(text)
                self.assertIsNone(info)
                self.assertTrue(reason)

    def test_at11b_integer_literal_over_digit_limit_is_contract_mismatch_not_exception(self) -> None:
        text = '{"oauthAccount": {"emailAddress": 1' + "0" * 5000 + "}}"
        info, reason = hub_account.parse_account_info(text)
        self.assertIsNone(info)
        self.assertTrue(reason)

    def test_at12_object_with_all_three_values_invalid_is_contract_mismatch(self) -> None:
        renamed_keys = {"emailAddr": SYNTHETIC_EMAIL, "orgName": SYNTHETIC_ORGANIZATION}
        info, reason = hub_account.parse_account_info(_document(renamed_keys))
        self.assertIsNone(info)
        self.assertTrue(reason)


class ParseAccountInfoAllowListTest(unittest.TestCase):
    """AT13~AT14 — 허용 목록 전수와 사유 문자열의 값 비유출."""

    def test_at13_only_the_two_displayed_sentinels_reach_the_result(self) -> None:
        full_account = {key: f"SENTINEL-{key}" for key in OAUTH_ACCOUNT_KEYS}
        # organizationType 은 대응표를 거치는 키라 센티넬이 그대로 나올 수 없다 — 알려진 값으로 바꿔 둔다.
        full_account["organizationType"] = "claude_team"
        info, _ = hub_account.parse_account_info(_document(full_account))
        serialized = json.dumps(dataclasses.asdict(info))
        self.assertIn("SENTINEL-emailAddress", serialized)
        self.assertIn("SENTINEL-organizationName", serialized)
        for key in OAUTH_ACCOUNT_KEYS:
            if key in EXTRACTED_KEYS:
                continue
            with self.subTest(key=key):
                self.assertNotIn(f"SENTINEL-{key}", serialized)

    def test_at13b_unknown_organization_type_value_is_never_echoed(self) -> None:
        info, _ = hub_account.parse_account_info(
            _document(_normal_account(organizationType="SENTINEL-organizationType"))
        )
        self.assertNotIn("SENTINEL-organizationType", json.dumps(dataclasses.asdict(info)))

    def test_at14_reason_strings_never_contain_input_values(self) -> None:
        sentinel_account = {key: f"SENTINEL-{key}" for key in OAUTH_ACCOUNT_KEYS}
        inputs = (
            _document("SENTINEL-not-an-object"),                                   # AT10
            "{SENTINEL-broken-json",                                               # AT11
            json.dumps(["SENTINEL-top-level-list"]),                               # AT11
            _document({"SENTINEL-renamed": SYNTHETIC_EMAIL, **{k: v for k, v in sentinel_account.items() if k not in EXTRACTED_KEYS}}),  # AT12
        )
        for text in inputs:
            with self.subTest(text=text[:30]):
                info, reason = hub_account.parse_account_info(text)
                self.assertIsNone(info)
                self.assertTrue(reason)
                self.assertNotIn("SENTINEL", reason)
                self.assertNotIn(SYNTHETIC_EMAIL, reason)


class AccountInfoImmutabilityTest(unittest.TestCase):
    """AT15 — 결과 객체는 frozen."""

    def test_at15_account_info_is_frozen(self) -> None:
        info, _ = hub_account.parse_account_info(_document(_normal_account()))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            info.email = "other@example.com"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
