"""hub_usage_fetch 단위 테스트. 네트워크·subprocess 는 전부 mock 한다 — 이 테스트는 실제
Keychain·API 를 절대 건드리지 않는다(불변식 A-SEC). U26~U33
(docs/prps/hub-card-interactions-and-usage.md 「테스트 계획」), U-S1~U-R8
(docs/prps/shell-hardening.md §10-4, S4 — H10·H11·H13·N1).

H10 의 리다이렉트 차단만 로컬 루프백 스텁 서버(127.0.0.1, OS 가 고른 포트)를 실제로 띄운다
(RedirectBlockedStubServerTest) — 나머지는 전부 `_open_usage_api_request` 모킹이다."""

import http.client
import http.server
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import typing
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_usage_fetch  # noqa: E402  (sys.path 조정 후 임포트)

FETCH_NOW_MS = 1_786_433_120_000
_CANARY_TOKEN = "canary-token-must-never-leak-into-a-failure-path"  # 테스트 전용 가짜 값


def _keychain_result(returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _valid_keychain_stdout(token: str = "test-only-fake-token") -> str:
    return json.dumps({"claudeAiOauth": {"accessToken": token}})


def _http_error(status_code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(hub_usage_fetch.USAGE_API_URL, status_code, "error", {}, None)


def _mock_response(body_text: str) -> mock.MagicMock:
    """`response.read(size)` 를 실제 소켓처럼 흉내낸다(H11) — 인자 없이 부르면 전체를,
    상한이 있으면 그 상한까지만 자른 bytes 를 돌려준다. 기존 호출부(인자 없음)와
    새 상한 읽기(`response.read(cap + 1)`) 양쪽에서 그대로 쓸 수 있다."""
    body_bytes = body_text.encode("utf-8")
    response = mock.MagicMock()
    response.read.side_effect = lambda size=None: body_bytes if size is None else body_bytes[:size]
    response.__enter__.return_value = response
    return response


class ReadOauthAccessTokenTest(unittest.TestCase):
    """U26~U28 — Keychain 읽기 실패 3경로는 모두 None(사유 구분은 fetch_rate_limit_capture 몫)."""

    def test_u26_security_command_missing_returns_none(self) -> None:
        with mock.patch.object(hub_usage_fetch.subprocess, "run", side_effect=FileNotFoundError()):
            self.assertIsNone(hub_usage_fetch.read_oauth_access_token())

    def test_u27_non_zero_exit_returns_none(self) -> None:
        with mock.patch.object(hub_usage_fetch.subprocess, "run", return_value=_keychain_result(returncode=1)):
            self.assertIsNone(hub_usage_fetch.read_oauth_access_token())

    def test_u28_output_not_json_returns_none(self) -> None:
        with mock.patch.object(hub_usage_fetch.subprocess, "run", return_value=_keychain_result(stdout="not json")):
            self.assertIsNone(hub_usage_fetch.read_oauth_access_token())

    def test_u28_missing_token_field_returns_none(self) -> None:
        stdout = json.dumps({"claudeAiOauth": {"refreshToken": "x"}})
        with mock.patch.object(hub_usage_fetch.subprocess, "run", return_value=_keychain_result(stdout=stdout)):
            self.assertIsNone(hub_usage_fetch.read_oauth_access_token())

    def test_valid_token_is_returned(self) -> None:
        stdout = _valid_keychain_stdout("test-only-fake-token")
        with mock.patch.object(hub_usage_fetch.subprocess, "run", return_value=_keychain_result(stdout=stdout)):
            self.assertEqual(hub_usage_fetch.read_oauth_access_token(), "test-only-fake-token")

    def test_u33_keychain_subprocess_uses_list_args_without_shell(self) -> None:
        """U33 — subprocess.run 이 리스트 인자 + shell 미지정으로 호출된다."""
        stdout = _valid_keychain_stdout()
        with mock.patch.object(hub_usage_fetch.subprocess, "run", return_value=_keychain_result(stdout=stdout)) as mocked_run:
            hub_usage_fetch.read_oauth_access_token()
        call_args, call_kwargs = mocked_run.call_args
        self.assertIsInstance(call_args[0], list)
        self.assertNotIn("shell", call_kwargs)


class FetchRateLimitCaptureTest(unittest.TestCase):
    """U26~U32 — fetch_rate_limit_capture 의 전체 실패/성공 경로(3-튜플 반환, 개정 반영)."""

    def _patch_keychain(self, **kwargs):
        return mock.patch.object(hub_usage_fetch.subprocess, "run", return_value=_keychain_result(**kwargs))

    def _fetch_with_http_outcome(self, open_request_mock: mock.Mock, token: str = "test-only-fake-token"):
        """모킹 이음선은 `_open_usage_api_request` 다(H10, §5-4) — 리다이렉트를 막으려면
        opener 를 써야 해서 `urllib.request.urlopen` 을 더 이상 호출하지 않기 때문이다.
        이 헬퍼 하나를 옮기면 아래 모든 케이스가 함께 새 이음선을 쓴다(§0 표의 「항목 10 의
        숨은 비용」 행)."""
        with self._patch_keychain(stdout=_valid_keychain_stdout(token)), \
             mock.patch.object(hub_usage_fetch, "_open_usage_api_request", open_request_mock):
            return hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS)

    def test_u26_credential_unavailable_when_security_missing(self) -> None:
        with mock.patch.object(hub_usage_fetch.subprocess, "run", side_effect=FileNotFoundError()):
            capture, reason, detail = hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS)
        self.assertIsNone(capture)
        self.assertEqual(reason, "credential_unavailable")
        self.assertIsNone(detail)

    def test_u27_credential_unavailable_when_non_zero_exit(self) -> None:
        with self._patch_keychain(returncode=1):
            capture, reason, detail = hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS)
        self.assertIsNone(capture)
        self.assertEqual(reason, "credential_unavailable")

    def test_u28_credential_unparsable_when_output_not_json(self) -> None:
        with self._patch_keychain(stdout="not json"):
            capture, reason, detail = hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS)
        self.assertIsNone(capture)
        self.assertEqual(reason, "credential_unparsable")

    def test_u28_credential_unparsable_when_token_field_missing(self) -> None:
        with self._patch_keychain(stdout=json.dumps({"claudeAiOauth": {"refreshToken": "x"}})):
            capture, reason, detail = hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS)
        self.assertEqual(reason, "credential_unparsable")

    def test_u29_http_401_is_unauthorized(self) -> None:
        _capture, reason, _detail = self._fetch_with_http_outcome(mock.Mock(side_effect=_http_error(401)))
        self.assertEqual(reason, "http_unauthorized")

    def test_u29_http_403_is_unauthorized(self) -> None:
        _capture, reason, _detail = self._fetch_with_http_outcome(mock.Mock(side_effect=_http_error(403)))
        self.assertEqual(reason, "http_unauthorized")

    def test_u29_http_429_is_rate_limited(self) -> None:
        _capture, reason, _detail = self._fetch_with_http_outcome(mock.Mock(side_effect=_http_error(429)))
        self.assertEqual(reason, "http_rate_limited")

    def test_u29_http_500_is_http_error(self) -> None:
        _capture, reason, _detail = self._fetch_with_http_outcome(mock.Mock(side_effect=_http_error(500)))
        self.assertEqual(reason, "http_error")

    def test_u30_url_error_is_network_error(self) -> None:
        _capture, reason, _detail = self._fetch_with_http_outcome(
            mock.Mock(side_effect=urllib.error.URLError("timed out"))
        )
        self.assertEqual(reason, "network_error")

    def test_u30_timeout_is_network_error(self) -> None:
        _capture, reason, _detail = self._fetch_with_http_outcome(mock.Mock(side_effect=TimeoutError()))
        self.assertEqual(reason, "network_error")

    def test_unclassified_http_client_exceptions_are_sealed_to_network_error(self) -> None:
        """검수 Major — http.client.HTTPException 계열(OSError 가 아니다)이 urlopen·응답 읽기
        도중 나도 경계를 넘지 않고 network_error 로 접혀야 한다(불변식 A-SEC 경계 봉합)."""
        unclassified_exceptions = (
            http.client.IncompleteRead(partial=b""),
            http.client.BadStatusLine("garbage"),
        )
        for exception in unclassified_exceptions:
            with self.subTest(exception=type(exception).__name__):
                capture, reason, detail = self._fetch_with_http_outcome(mock.Mock(side_effect=exception))
                self.assertIsNone(capture)
                self.assertEqual(reason, "network_error")
                self.assertIsNone(detail)

    def test_u31_200_with_unparseable_body_is_schema_mismatch(self) -> None:
        capture, reason, detail = self._fetch_with_http_outcome(
            mock.Mock(return_value=_mock_response(json.dumps({"unexpected": "shape"})))
        )
        self.assertIsNone(capture)
        self.assertEqual(reason, "schema_mismatch")
        self.assertIsNotNone(detail)
        self.assertIn("/unexpected <str>", detail)

    def test_major3_recursion_error_from_parse_usage_api_response_does_not_propagate(self) -> None:
        """검수 MAJOR 3(결정 AR4/B-1) — hub_usage_fetch.py:119-133 에서 파싱 2줄을 try
        경계 안으로 옮긴 것 자체를 무는 유일한 테스트. 병리적으로 깊은 중첩 응답에서
        `parse_usage_api_response` 가 던지는 `RecursionError`(json.loads 의 실측 경로,
        hub_usage.py:364)가 이 함수 밖으로 새지 않고 깨끗한 3-튜플로 접혀야 한다."""
        with mock.patch.object(hub_usage_fetch.hub_usage, "parse_usage_api_response", side_effect=RecursionError):
            capture, reason, detail = self._fetch_with_http_outcome(mock.Mock(return_value=_mock_response("{}")))
        self.assertIsNone(capture)
        self.assertEqual(reason, "network_error")
        self.assertIsNone(detail)

    def test_major3_recursion_error_from_describe_json_key_structure_does_not_propagate(self) -> None:
        """같은 경계 안에 있는 `describe_json_key_structure`(schema_mismatch 진단 경로,
        hub_usage.py:414)가 던지는 미분류 예외도 전파되지 않아야 한다."""
        with mock.patch.object(hub_usage_fetch.hub_usage, "parse_usage_api_response", return_value=None), \
             mock.patch.object(hub_usage_fetch.hub_usage, "describe_json_key_structure", side_effect=RecursionError):
            capture, reason, detail = self._fetch_with_http_outcome(
                mock.Mock(return_value=_mock_response(json.dumps({"unexpected": "shape"})))
            )
        self.assertIsNone(capture)
        self.assertEqual(reason, "network_error")
        self.assertIsNone(detail)

    def test_success_returns_capture_and_no_failure(self) -> None:
        body = json.dumps(
            {
                "five_hour": {"utilization": 23, "resets_at": "2026-08-13T18:00:00+00:00"},
                "seven_day": {"utilization": 41, "resets_at": "2026-08-20T00:00:00+00:00"},
            }
        )
        capture, reason, detail = self._fetch_with_http_outcome(mock.Mock(return_value=_mock_response(body)))
        self.assertIsNotNone(capture)
        self.assertIsNone(reason)
        self.assertIsNone(detail)

    def test_h10_3xx_http_error_is_classified_as_redirect_blocked(self) -> None:
        """H10(§5-3) — 차단된 리다이렉트를 http_error 로 접지 않는다. 3xx 전 대역이 대상이다
        (자동 추적 대상인 301/302/303/307/308 뿐 아니라, 그 외 3xx 도 우리가 따라가지 않은
        정상 응답이라는 점은 같다)."""
        for status_code in (300, 301, 302, 303, 307, 308, 399):
            with self.subTest(status_code=status_code):
                _capture, reason, detail = self._fetch_with_http_outcome(
                    mock.Mock(side_effect=_http_error(status_code))
                )
                self.assertEqual(reason, "redirect_blocked")
                self.assertIsNone(detail)

    def test_h13_direct_ssl_verification_error_is_tls_verify_failed(self) -> None:
        """H13(§9-8) — ssl.SSLCertVerificationError 가 감싸지지 않고 직접 올라오는 경로도
        대비한다(방어적 — 자체 서명 인증서로 만든 로컬 HTTPS 서버로 실측하면 표준 urllib 은
        항상 URLError 로 감싼다)."""
        _capture, reason, _detail = self._fetch_with_http_outcome(
            mock.Mock(side_effect=ssl.SSLCertVerificationError("certificate verify failed"))
        )
        self.assertEqual(reason, "tls_verify_failed")

    def test_h13_ssl_verification_error_wrapped_in_url_error_is_tls_verify_failed(self) -> None:
        """H13 — 실측으로 확인된 실제 경로(자체 서명 인증서로 만든 로컬 HTTPS 서버에 붙여
        관측했다): urllib 은 TLS 검증 실패를 URLError(reason=SSLCertVerificationError) 로
        감싸 올린다."""
        wrapped = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        _capture, reason, _detail = self._fetch_with_http_outcome(mock.Mock(side_effect=wrapped))
        self.assertEqual(reason, "tls_verify_failed")

    def test_h13_regression_dns_failure_is_still_network_error(self) -> None:
        """H13 회귀(U-R6) — 새 TLS 어휘가 기존 network_error 어휘를 잠식하지 않는다."""
        _capture, reason, _detail = self._fetch_with_http_outcome(
            mock.Mock(side_effect=socket.gaierror("Name or service not known"))
        )
        self.assertEqual(reason, "network_error")

    def test_h11_response_exactly_at_cap_is_processed_normally(self) -> None:
        """H11(§9-8) — `response.read(상한+1)` 로 초과만 판정한다. 본문이 상한과 정확히
        같으면(cap+1 을 읽어도 cap 바이트만 나온다) 정상 처리로 이어진다."""
        body_text = json.dumps({"five_hour": {"utilization": 10}})
        cap = len(body_text.encode("utf-8"))
        with mock.patch.object(hub_usage_fetch, "USAGE_API_MAX_RESPONSE_BYTES", cap):
            capture, reason, _detail = self._fetch_with_http_outcome(
                mock.Mock(return_value=_mock_response(body_text))
            )
        self.assertIsNotNone(capture)
        self.assertIsNone(reason)

    def test_h11_response_one_byte_over_cap_is_too_large(self) -> None:
        body_text = json.dumps({"five_hour": {"utilization": 10}})
        cap = len(body_text.encode("utf-8")) - 1   # 본문이 상한보다 정확히 1바이트 크다
        with mock.patch.object(hub_usage_fetch, "USAGE_API_MAX_RESPONSE_BYTES", cap):
            capture, reason, detail = self._fetch_with_http_outcome(
                mock.Mock(return_value=_mock_response(body_text))
            )
        self.assertIsNone(capture)
        self.assertEqual(reason, "response_too_large")
        self.assertIsNone(detail)

    def test_h11_response_key_list_is_capped_with_truncation_marker(self) -> None:
        """H11(§7-2) — response_keys 자기 진단 목록도 상한이 있고, 잘리면 표지 항목을
        마지막에 남긴다(조용히 자르면 자기 진단 창구가 거짓말을 한다)."""
        body_text = json.dumps({f"field_{i}": i for i in range(10)})  # 스키마 불일치 유도
        with mock.patch.object(hub_usage_fetch, "USAGE_API_MAX_RESPONSE_KEY_ENTRIES", 2):
            _capture, reason, detail = self._fetch_with_http_outcome(
                mock.Mock(return_value=_mock_response(body_text))
            )
        self.assertEqual(reason, "schema_mismatch")
        self.assertEqual(len(detail), 3)   # 상한 2 + 표지 항목 1
        self.assertIn("생략", detail[-1])

    def test_u32_no_failure_path_leaks_the_token_string(self) -> None:
        """불변식 A-SEC — 어떤 실패 경로의 반환값에도 토큰 문자열이 없다."""
        outcomes = []
        with mock.patch.object(hub_usage_fetch.subprocess, "run", side_effect=FileNotFoundError()):
            outcomes.append(hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS))
        with self._patch_keychain(returncode=1):
            outcomes.append(hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS))
        with self._patch_keychain(stdout="not json"):
            outcomes.append(hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS))
        for status_code in (401, 429, 500):
            outcomes.append(
                self._fetch_with_http_outcome(mock.Mock(side_effect=_http_error(status_code)), token=_CANARY_TOKEN)
            )
        outcomes.append(
            self._fetch_with_http_outcome(mock.Mock(side_effect=urllib.error.URLError("x")), token=_CANARY_TOKEN)
        )
        outcomes.append(
            # U-R2(H10, A-SEC) — 리다이렉트가 차단됐을 때도 토큰이 반환값에 없다.
            self._fetch_with_http_outcome(mock.Mock(side_effect=_http_error(302)), token=_CANARY_TOKEN)
        )
        outcomes.append(
            self._fetch_with_http_outcome(
                mock.Mock(return_value=_mock_response(json.dumps({"unexpected": "shape"}))), token=_CANARY_TOKEN
            )
        )
        for outcome in outcomes:
            self.assertNotIn(_CANARY_TOKEN, repr(outcome))


class CappedResponseKeyStructureTest(unittest.TestCase):
    """구현 2회차(검수 접지 MEDIUM) — 항목 수 상한만으로는 총 바이트를 막지 못한다는 지적을
    반영한 `_capped_response_key_structure` 경계 테스트. `describe_json_key_structure` 의
    각 항목은 조상 키 경로 전체를 문자열로 담으므로, 항목 수가 상한 이내여도 총 바이트는
    항목 수 × 경로 길이로 증폭될 수 있다 — 개수 상한 테스트(`test_h11_response_key_list_is_
    capped_with_truncation_marker`, `FetchRateLimitCaptureTest`)는 이 클래스가 건드리지
    않는다."""

    def test_within_both_caps_returns_original_list_unchanged(self) -> None:
        key_structure = ["/five_hour/utilization <int>", "/five_hour/resets_at <str>"]
        result = hub_usage_fetch._capped_response_key_structure(key_structure)
        self.assertEqual(result, key_structure)

    def test_exactly_at_byte_cap_has_no_truncation_marker(self) -> None:
        """바이트 경계 — 누적 바이트가 상한과 정확히 같으면 표지를 붙이지 않는다(기존 개수
        상한의 경계 테스트와 대칭인 성질)."""
        entry = "x" * hub_usage_fetch.USAGE_API_MAX_RESPONSE_KEY_BYTES   # 상한과 정확히 같은 바이트
        result = hub_usage_fetch._capped_response_key_structure([entry])
        self.assertEqual(result, [entry])

    def test_one_byte_over_cap_is_truncated_with_single_marker(self) -> None:
        entry = "x" * (hub_usage_fetch.USAGE_API_MAX_RESPONSE_KEY_BYTES + 1)   # 상한보다 1바이트 크다
        result = hub_usage_fetch._capped_response_key_structure([entry])
        self.assertEqual(len(result), 1)   # 바이트 예산을 넘는 첫 항목 자체가 잘려 표지만 남는다
        self.assertIn("생략", result[0])

    def test_count_within_cap_but_bytes_over_cap_still_truncates(self) -> None:
        """검수자 지적의 핵심 — 항목 수(2)는 상한(100)에 한참 못 미쳐도 누적 바이트가 상한을
        넘으면(조상 키 경로 반복으로 인한 증폭 시나리오) 잘려야 한다."""
        half_cap_plus_one = hub_usage_fetch.USAGE_API_MAX_RESPONSE_KEY_BYTES // 2 + 1
        key_structure = ["x" * half_cap_plus_one, "y" * half_cap_plus_one]
        result = hub_usage_fetch._capped_response_key_structure(key_structure)
        truncation_marker = "…(상한 초과로 나머지 생략됨 — 개수는 세지 않는다)"
        self.assertEqual(result, [key_structure[0], truncation_marker])

    def test_count_and_byte_caps_both_exceeded_yields_single_marker(self) -> None:
        """개수·바이트가 동시에 초과해도(바이트 상한이 개수 상한보다 먼저 걸린다) 표지는
        하나다."""
        entry = "k" * 100   # 100바이트 항목
        entry_count = hub_usage_fetch.USAGE_API_MAX_RESPONSE_KEY_ENTRIES + 50   # 개수 상한도 넘는다
        key_structure = [entry] * entry_count
        result = hub_usage_fetch._capped_response_key_structure(key_structure)
        marker_count = sum(1 for item in result if "생략" in item)
        self.assertEqual(marker_count, 1)
        # 바이트 상한(엔트리당 100바이트 기준 약 82개분)이 개수 상한(100개)보다 먼저 걸린다.
        self.assertLess(len(result), hub_usage_fetch.USAGE_API_MAX_RESPONSE_KEY_ENTRIES)

    def test_reviewer_reproduction_deep_nesting_amplification_is_bounded(self) -> None:
        """검수자 실측 재현(깊이 60·키 길이 1000·리프 100) — 조상 키 경로 반복 증폭이 바이트
        상한 근처로 줄어드는지 `describe_json_key_structure` 의 실제 산출물로 확인한다."""
        nesting_depth = 60
        repeated_key_length = 1000
        leaf_count = 100
        repeated_key = "k" * repeated_key_length
        nested_payload: dict = {f"leaf_{i}": i for i in range(leaf_count)}
        for _ in range(nesting_depth):
            nested_payload = {repeated_key: nested_payload}
        body_text = json.dumps(nested_payload)

        key_structure = hub_usage_fetch.hub_usage.describe_json_key_structure(body_text)
        self.assertIsNotNone(key_structure)
        uncapped_bytes = sum(len(entry.encode("utf-8")) for entry in key_structure)

        result = hub_usage_fetch._capped_response_key_structure(key_structure)
        capped_bytes = sum(len(entry.encode("utf-8")) for entry in result)

        self.assertLess(capped_bytes, uncapped_bytes)
        self.assertLessEqual(capped_bytes, hub_usage_fetch.USAGE_API_MAX_RESPONSE_KEY_BYTES + 256)


class FailureReasonMessageTest(unittest.TestCase):
    """U-R7·N1 — `FAILURE_REASON_MESSAGES` 는 죽은 dict 였다(소비자 0개, §2-B 의 N1 행).
    이 테스트가 §7-1 의 "어휘와 메시지는 같은 커밋에서 함께 움직인다" 계약을 기계로
    강제하는 자리다 — 어휘를 하나 더하고 메시지를 안 더하면 이 테스트가 실패해야 한다."""

    def test_every_failure_reason_literal_value_has_its_specific_message(self) -> None:
        for reason in typing.get_args(hub_usage_fetch.FailureReason):
            with self.subTest(reason=reason):
                message = hub_usage_fetch.failure_reason_message(reason)
                self.assertEqual(message, hub_usage_fetch.FAILURE_REASON_MESSAGES[reason])

    def test_unknown_reason_falls_back_to_generic_message_instead_of_raising(self) -> None:
        """`record_usage_api_failure` 호출부 중 하나(hub_server.py)는 FailureReason 밖의
        값("internal_error")도 넘긴다 — 총함수여야 한다(KeyError 로 죽으면 안 된다)."""
        self.assertEqual(
            hub_usage_fetch.failure_reason_message("internal_error"),
            hub_usage_fetch._UNKNOWN_FAILURE_REASON_MESSAGE,
        )


class _RedirectStubRequestHandler(http.server.BaseHTTPRequestHandler):
    """H10 실측(§9-8) — 302 를 내고 Location 을 아무 데나 가리킨다. `hit_count` 로 두 번째
    요청(리다이렉트를 따라갔을 경우 도착할 요청)이 실제로 오지 않았음을 센다."""

    hit_count = 0

    def do_GET(self) -> None:
        _RedirectStubRequestHandler.hit_count += 1
        self.send_response(302)
        self.send_header("Location", "http://127.0.0.1:1/should-never-be-reached")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass   # 테스트 stdout 을 조용히 유지한다(BaseHTTPRequestHandler 기본 로깅 억제)


class RedirectBlockedStubServerTest(unittest.TestCase):
    """U-R1 — 로컬 루프백 스텁 서버로 302 를 실제로 왕복시켜 설계가 "구현 시 실측할 것"으로
    남긴 두 층을 함께 확인한다(§9-8): ① 두 번째 요청이 도착하지 않는다 ② fetch_rate_limit_capture
    가 redirect_blocked 를 돌려준다. 실제 사용량 API 는 절대 호출하지 않는다 — 127.0.0.1
    루프백 전용이고 Keychain 은 여전히 mock 한다. `tests/hub/test_hub_server.py` 의
    `_RunningHubServerTestCase` 실소켓 bind 관용구를 따른다."""

    def setUp(self) -> None:
        _RedirectStubRequestHandler.hit_count = 0
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RedirectStubRequestHandler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.original_usage_api_url = hub_usage_fetch.USAGE_API_URL
        hub_usage_fetch.USAGE_API_URL = f"http://127.0.0.1:{self.httpd.server_address[1]}/"

    def tearDown(self) -> None:
        hub_usage_fetch.USAGE_API_URL = self.original_usage_api_url
        self.httpd.shutdown()
        self.httpd.server_close()
        self.server_thread.join(timeout=2)

    def test_redirect_is_blocked_end_to_end_against_a_real_local_server(self) -> None:
        with mock.patch.object(
            hub_usage_fetch.subprocess, "run", return_value=_keychain_result(stdout=_valid_keychain_stdout())
        ):
            _capture, reason, _detail = hub_usage_fetch.fetch_rate_limit_capture(FETCH_NOW_MS)
        self.assertEqual(reason, "redirect_blocked")
        self.assertEqual(_RedirectStubRequestHandler.hit_count, 1)


if __name__ == "__main__":
    unittest.main()
