"""hub_transcript 단위 테스트. docs/prps/hub-tier1-clamp-fix-and-session-model.md 「테스트
계획」 §8.3 — normalize_model_name(MD5)·parse_session_model_from_tail(MD6~MD7) 표 전체."""

import json
import os
import sys
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_transcript  # noqa: E402  (sys.path 조정 후 임포트)


class NormalizeModelNameTest(unittest.TestCase):
    """MD5 — 표 전체가 실측(760개 transcript 꼬리 전수 조사)에서 나온 실제 ID 다."""

    def test_basic_single_version_ids(self) -> None:
        self.assertEqual(hub_transcript.normalize_model_name("claude-opus-5"), "Opus 5")
        self.assertEqual(hub_transcript.normalize_model_name("claude-fable-5"), "Fable 5")
        self.assertEqual(hub_transcript.normalize_model_name("claude-sonnet-5"), "Sonnet 5")

    def test_two_part_version_ids(self) -> None:
        self.assertEqual(hub_transcript.normalize_model_name("claude-opus-4-6"), "Opus 4.6")
        self.assertEqual(hub_transcript.normalize_model_name("claude-opus-4-8"), "Opus 4.8")

    def test_date_suffix_is_dropped(self) -> None:
        """구세대 모델 ID 의 YYYYMMDD 접미(8자리 전부 숫자)는 정규화에서 버려진다."""
        self.assertEqual(
            hub_transcript.normalize_model_name("claude-haiku-4-5-20251001"), "Haiku 4.5"
        )

    def test_synthetic_is_not_a_model(self) -> None:
        self.assertIsNone(hub_transcript.normalize_model_name("<synthetic>"))

    def test_empty_string_is_not_a_model(self) -> None:
        self.assertIsNone(hub_transcript.normalize_model_name(""))

    def test_unknown_future_model_following_convention_normalizes_automatically(self) -> None:
        """미지의 미래 모델도 claude-{family}-{version...} 관례를 따르면 자동으로 잘 나온다."""
        self.assertEqual(hub_transcript.normalize_model_name("claude-opus-6"), "Opus 6")

    def test_unknown_future_family_with_date_suffix(self) -> None:
        self.assertEqual(
            hub_transcript.normalize_model_name("claude-newfamily-7-2-20990101"), "Newfamily 7.2"
        )

    def test_legacy_non_alpha_first_token_falls_back_to_raw_id(self) -> None:
        """구세대 claude-3-5-sonnet-... 형태는 첫 토큰이 숫자라 정규화를 포기하고 원문을 낸다."""
        raw_id = "claude-3-5-sonnet-20241022"
        self.assertEqual(hub_transcript.normalize_model_name(raw_id), raw_id)

    def test_non_claude_prefix_is_not_a_model(self) -> None:
        self.assertIsNone(hub_transcript.normalize_model_name("gpt-4o"))

    def test_prefix_only_is_not_a_model(self) -> None:
        self.assertIsNone(hub_transcript.normalize_model_name("claude-"))

    def test_no_version_token_uses_family_alone(self) -> None:
        self.assertEqual(hub_transcript.normalize_model_name("claude-opus"), "Opus")


def _assistant_line(model: str, effort: str | None = "xhigh", **overrides) -> str:
    payload = {"type": "assistant", "message": {"model": model, "role": "assistant"}}
    if effort is not None:
        payload["effort"] = effort
    payload.update(overrides)
    return json.dumps(payload)


def _last_prompt_line(last_prompt, **overrides) -> str:
    """§1.4 실측 전문대로의 last-prompt 줄. leafUuid·sessionId 는 이 설계가 읽지 않는다."""
    payload = {
        "type": "last-prompt", "lastPrompt": last_prompt,
        "leafUuid": "90c389e5-0000-0000-0000-000000000000", "sessionId": "768e8a38-0000",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _human_line(content, **overrides) -> str:
    """사람이 입력한 user 줄 — 호스트가 붙이는 origin.kind=human 표지(결정 TF2)와 실측 필드 모양.
    content 는 문자열(실측 대다수) 또는 블록 목록(이미지·첨부가 딸린 입력). 픽스처 글은 전부 합성 문장이다."""
    payload = {
        "type": "user", "origin": {"kind": "human"}, "isSidechain": False,
        "message": {"role": "user", "content": content},
    }
    payload.update(overrides)
    return json.dumps(payload)


def _key_block(total_chars: int) -> str:
    """개인키 모양의 블록(여는 표지 + 본문) — 스크럽이 한 덩어리 「[REDACTED]」 로 접어 창을 크게 줄인다. 합성 값이라 실제 키가 아니다."""
    opening_marker = "-----BEGIN PRIVATE KEY-----"
    return opening_marker + "A" * (total_chars - len(opening_marker))


class ParseSessionModelFromTailTest(unittest.TestCase):
    """MD6(마지막 값)·MD7(부재 처리)·GOTCHA 4·5·6 — 표 전체."""

    def test_single_assistant_line(self) -> None:
        tail = _assistant_line("claude-opus-5", effort="xhigh")
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertEqual(
            model,
            hub_transcript.SessionModel(
                model_label="Opus 5", raw_model_id="claude-opus-5", effort="xhigh"
            ),
        )

    def test_last_value_wins_on_model_switch(self) -> None:
        """MD6 — opus-5 다음에 fable-5 로 전환되면 화면은 마지막 값(Fable 5)을 보여준다."""
        tail = "\n".join([
            _assistant_line("claude-opus-5", effort="xhigh"),
            _assistant_line("claude-fable-5", effort="high"),
        ])
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertEqual(model.model_label, "Fable 5")

    def test_model_and_effort_are_taken_from_the_same_line(self) -> None:
        """GOTCHA 5 — 서로 다른 줄에서 뽑으면 (Fable 5, xhigh) 같은 잘못된 조합이 나온다."""
        tail = "\n".join([
            _assistant_line("claude-opus-5", effort="xhigh"),
            _assistant_line("claude-fable-5", effort="high"),
        ])
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertEqual((model.model_label, model.effort), ("Fable 5", "high"))

    def test_missing_effort_key_is_none(self) -> None:
        tail = _assistant_line("claude-opus-5", effort=None)
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertIsNone(model.effort)

    def test_effort_inside_message_is_ignored(self) -> None:
        """GOTCHA 4 — effort 는 줄 최상위에만 있다. message.effort 는 보지 않는다."""
        payload = {
            "type": "assistant",
            "message": {"model": "claude-opus-5", "effort": "xhigh"},
        }
        model = hub_transcript.parse_session_model_from_tail(json.dumps(payload))
        self.assertIsNotNone(model)
        self.assertIsNone(model.effort)

    def test_synthetic_line_is_skipped_and_search_continues(self) -> None:
        """E11 — 마지막이 <synthetic> 이면 건너뛰고 그 앞의 실제 모델을 찾는다."""
        tail = "\n".join([
            _assistant_line("claude-opus-5", effort="xhigh"),
            _assistant_line("<synthetic>", effort=None),
        ])
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertEqual(model.model_label, "Opus 5")

    def test_truncated_first_line_is_ignored(self) -> None:
        """꼬리의 첫 줄(파일 중간에서 잘렸을 수 있다)이 깨져도 뒤 줄에서 성공한다."""
        good_line = _assistant_line("claude-opus-5", effort="xhigh")
        truncated_first_line = good_line[10:]   # 앞부분이 잘려 JSON 파싱이 실패한다
        tail = truncated_first_line + "\n" + good_line
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertEqual(model.model_label, "Opus 5")

    def test_no_assistant_line_returns_none(self) -> None:
        tail = json.dumps({"type": "user", "message": {"role": "user"}})
        self.assertIsNone(hub_transcript.parse_session_model_from_tail(tail))

    def test_empty_tail_returns_none(self) -> None:
        self.assertIsNone(hub_transcript.parse_session_model_from_tail(""))

    def test_broken_json_line_mixed_with_valid_line(self) -> None:
        good_line = _assistant_line("claude-opus-5", effort="xhigh")
        tail = "not-json-at-all\n" + good_line
        model = hub_transcript.parse_session_model_from_tail(tail)
        self.assertEqual(model.model_label, "Opus 5")

    def test_message_not_a_dict_returns_none_without_raising(self) -> None:
        payload = {"type": "assistant", "message": "x"}
        self.assertIsNone(hub_transcript.parse_session_model_from_tail(json.dumps(payload)))

    def test_non_assistant_type_with_model_is_ignored(self) -> None:
        """assistant 줄만 본다 — user 줄에 model 이 있어도 무시한다."""
        payload = {"type": "user", "message": {"model": "claude-opus-5"}}
        self.assertIsNone(hub_transcript.parse_session_model_from_tail(json.dumps(payload)))


class ParseSessionTailTest(unittest.TestCase):
    """PS1·PS2 — (모델, last_prompt) 를 한 번의 역방향 스캔으로 함께 판다."""

    def test_model_line_and_last_prompt_line_are_both_filled(self) -> None:
        tail = "\n".join([
            _assistant_line("claude-opus-5", effort="xhigh"),
            _last_prompt_line("프롬프트 본문"),
        ])
        result = hub_transcript.parse_session_tail(tail)
        self.assertEqual(result.model.model_label, "Opus 5")
        self.assertEqual(result.last_prompt, "프롬프트 본문")

    def test_last_prompt_only_leaves_model_none(self) -> None:
        result = hub_transcript.parse_session_tail(_last_prompt_line("프롬프트만"))
        self.assertIsNone(result.model)
        self.assertEqual(result.last_prompt, "프롬프트만")

    def test_model_only_leaves_last_prompt_none(self) -> None:
        result = hub_transcript.parse_session_tail(_assistant_line("claude-opus-5"))
        self.assertEqual(result.model.model_label, "Opus 5")
        self.assertIsNone(result.last_prompt)

    def test_multiple_last_prompt_lines_the_last_one_wins(self) -> None:
        tail = "\n".join([_last_prompt_line("첫 번째"), _last_prompt_line("마지막")])
        result = hub_transcript.parse_session_tail(tail)
        self.assertEqual(result.last_prompt, "마지막")

    def test_non_string_last_prompt_is_none(self) -> None:
        result = hub_transcript.parse_session_tail(_last_prompt_line(12345))
        self.assertIsNone(result.last_prompt)

    def test_oversized_last_prompt_is_clipped_to_400_chars(self) -> None:
        result = hub_transcript.parse_session_tail(_last_prompt_line("가" * 500))
        self.assertEqual(len(result.last_prompt), hub_transcript.LAST_PROMPT_MAX_CHARS)
        self.assertTrue(result.last_prompt.endswith("…"))

    def test_secret_in_last_prompt_is_redacted(self) -> None:
        """PS9 — 오늘 훅이 하던 스크럽을 파서가 물려받는다."""
        result = hub_transcript.parse_session_tail(
            _last_prompt_line("키 sk-ant-abcdefghijklmnopqrstuvwxyz 공유")
        )
        self.assertIn("[REDACTED]", result.last_prompt)
        self.assertNotIn("sk-ant-abcdefghijklmnopqrstuvwxyz", result.last_prompt)

    def test_scrubbing_happens_before_clipping_not_after(self) -> None:
        """PS9 — redact → clip 순서. 자르기가 먼저면 400자 경계의 시크릿이 패턴 불일치로 산다.

        재검수 1회차 H2 — 원래 산문 380자는 절단 경계(399자)를 지나도 시크릿의 x 부분이
        12자 남아 SECRET_TOKEN_PATTERN 의 최소 길이({10,})를 여전히 만족해, 순서를 뒤집어도
        (자르기 → 스크럽) 이 단언이 우연히 통과했다(판별력 없음, 검수자 실측). 산문을 390자로
        올리면 절단 후 남는 x 부분이 2자(399-390-7)로 줄어 최소 길이 미달이 되고, 순서가
        뒤집혔을 때 이 단언이 실제로 실패한다.

        재검수 2회차 수정 2 — 390 이 하드코딩이라 LAST_PROMPT_MAX_CHARS 를 올리면(재검수자
        실측: 500 으로) 경계에서 멀어져 판별력이 사라졌다. LAST_PROMPT_MAX_CHARS-10 으로
        유도해 상한이 바뀌어도 "경계 뒤 잔존 2자 < 10자" 관계가 자동으로 유지되게 한다.
        """
        secret = "sk-ant-" + "x" * 40
        prompt = ("가" * (hub_transcript.LAST_PROMPT_MAX_CHARS - 10)) + secret + ("가" * 50)
        result = hub_transcript.parse_session_tail(_last_prompt_line(prompt))
        self.assertNotIn("sk-ant-", result.last_prompt)

    def test_empty_tail_returns_both_none(self) -> None:
        result = hub_transcript.parse_session_tail("")
        self.assertIsNone(result.model)
        self.assertIsNone(result.last_prompt)

    def test_full_model_table_still_passes_through_parse_session_model_from_tail(self) -> None:
        """PS2 — parse_session_model_from_tail 은 parse_session_tail(...).model 과 같다는
        위임 계약을 다시 한 번 직접 확인한다(기존 ParseSessionModelFromTailTest 표 전체가
        이름 변경 없이 통과하는 것이 1차 확인이다)."""
        tail = _assistant_line("claude-fable-5", effort="high")
        self.assertEqual(
            hub_transcript.parse_session_model_from_tail(tail), hub_transcript.parse_session_tail(tail).model
        )


# §1.3 실측 그대로의 시각 하나로 전 테스트를 고정한다 — epoch ms 는 datetime.fromisoformat 을
# 쓰지 않고 독립적으로 계산한 리터럴이라(순환 검증 방지) 실측 도출: python3 -B -c
# "from datetime import datetime, timezone; print(int(datetime(2026,9,22,6,38,33,931000,
# tzinfo=timezone.utc).timestamp()*1000))".
_ERROR_LINE_TIMESTAMP = "2026-09-22T06:38:33.931Z"
_ERROR_LINE_FAILED_AT_MS = 1790059113931


def _error_line(error="rate_limit", timestamp=_ERROR_LINE_TIMESTAMP, quota_limits=None, **overrides) -> str:
    """§1.3 실측 그대로의 API 오류 assistant 줄. message.content 는 담지 않는다(RI7 — T12 가
    담더라도 읽히지 않음을 확인한다)."""
    payload = {
        "type": "assistant",
        "isApiErrorMessage": True,
        "error": error,
        "timestamp": timestamp,
        "message": {"model": hub_transcript.SYNTHETIC_MODEL_ID},
    }
    if quota_limits is not None:
        payload["quotaLimits"] = quota_limits
    payload.update(overrides)
    return json.dumps(payload)


class ParseSessionTailTurnFailureTest(unittest.TestCase):
    """RI1·RI5·RI7 — 꼬리의 마지막 메인 대화 줄이 API 오류 줄인지 판정하는 표 T1~T12."""

    def test_t1_error_line_with_quota_limits_fills_all_fields(self) -> None:
        result = hub_transcript.parse_session_tail(
            _error_line(quota_limits={"resetsAt": 1790148600, "rateLimitType": "five_hour", "status": "rejected"})
        ).turn_failure
        self.assertEqual(result.error_kind, "rate_limit")
        self.assertEqual(result.failed_at_ms, _ERROR_LINE_FAILED_AT_MS)
        self.assertEqual(result.resets_at_ms, 1790148600 * 1000)

    def test_t1b_detection_survives_python310_fromisoformat_semantics(self) -> None:
        """검수 1회차 HIGH — `datetime.fromisoformat` 은 3.11 부터만 트레일링 "Z" 를
        받아들인다. 이 저장소의 최소 지원 버전은 3.10(hub/install.sh·hub/README.md
        「요구사항」)이라, 3.10 의미론(Z 거부)에서도 검출이 성공해야 한다. 현재 인터프리터가
        몇 버전이든(3.11 이상이라도) 재현되도록, `hub_transcript.datetime` 을 "Z" 로 끝나는
        문자열만 거부하는 가짜로 바꿔 끼운다 — 그 외 입력은 실제 datetime.fromisoformat 에
        위임해 반환값이 진짜 datetime 인스턴스이게 한다(.replace·.timestamp 가 정상 동작해야
        하므로). `epoch_ms_from_iso8601` 이 파싱 전에 "Z" 를 "+00:00" 으로 바꾸지 않으면
        (수정 전 코드) 이 가짜가 ValueError 를 던져 turn_failure 가 조용히 None 이 된다 —
        직접 재현 확인(수정 전 로직으로 스크래치패드에서 검증, None 반환)."""
        class _Python310SemanticsFromIsoformat:
            @staticmethod
            def fromisoformat(value):
                if isinstance(value, str) and value.endswith("Z"):
                    raise ValueError(f"Invalid isoformat string: {value!r}")
                return datetime.fromisoformat(value)

        tail = _error_line(quota_limits={"resetsAt": 1790148600})
        with mock.patch.object(hub_transcript, "datetime", _Python310SemanticsFromIsoformat):
            result = hub_transcript.parse_session_tail(tail).turn_failure
        self.assertIsNotNone(result)
        self.assertEqual(result.error_kind, "rate_limit")
        self.assertEqual(result.failed_at_ms, _ERROR_LINE_FAILED_AT_MS)
        self.assertEqual(result.resets_at_ms, 1790148600 * 1000)

    def test_t2_error_line_followed_by_nine_non_conversation_line_types_still_detected(self) -> None:
        """§1.3 실측 목록 그대로(비대화 줄 9종) — 역방향 스캔이 이 줄들을 건너뛰고 그 앞의
        오류 줄에 도달해야 한다."""
        non_conversation_types = (
            "queue-operation", "last-prompt", "custom-title", "agent-name",
            "mode", "atis-latch", "bridge-session", "relocated", "worktree-state",
        )
        lines = [_error_line()] + [json.dumps({"type": line_type}) for line_type in non_conversation_types]
        result = hub_transcript.parse_session_tail("\n".join(lines)).turn_failure
        self.assertIsNotNone(result)
        self.assertEqual(result.error_kind, "rate_limit")

    def test_t3_error_line_followed_by_user_line_returns_none(self) -> None:
        tail = "\n".join([_error_line(), json.dumps({"type": "user", "message": {"role": "user"}})])
        self.assertIsNone(hub_transcript.parse_session_tail(tail).turn_failure)

    def test_t4_error_line_followed_by_normal_assistant_line_returns_none(self) -> None:
        tail = "\n".join([_error_line(), _assistant_line("claude-opus-5")])
        self.assertIsNone(hub_transcript.parse_session_tail(tail).turn_failure)

    def test_t5_trailing_sidechain_error_line_is_ignored_earlier_main_line_decides(self) -> None:
        tail = "\n".join([
            _error_line(error="authentication_failed"),
            _error_line(error="rate_limit", isSidechain=True),
        ])
        result = hub_transcript.parse_session_tail(tail).turn_failure
        self.assertIsNotNone(result)
        self.assertEqual(result.error_kind, "authentication_failed")

    def test_t6_trailing_meta_user_line_is_ignored_earlier_error_line_still_detected(self) -> None:
        tail = "\n".join([_error_line(), json.dumps({"type": "user", "isMeta": True, "message": {"role": "user"}})])
        result = hub_transcript.parse_session_tail(tail).turn_failure
        self.assertIsNotNone(result)
        self.assertEqual(result.error_kind, "rate_limit")

    def test_t7_missing_quota_limits_still_detects_with_resets_none(self) -> None:
        """구버전 호스트(§1.3 — 2.1.219~2.1.229 는 quotaLimits 0/26) 재현."""
        result = hub_transcript.parse_session_tail(_error_line()).turn_failure
        self.assertIsNotNone(result)
        self.assertIsNone(result.resets_at_ms)

    def test_t8_malformed_resets_at_yields_resets_none(self) -> None:
        malformed_resets_at_by_label = {
            "bool": True,
            "float": 1790148600.5,
            "string": "1790148600",
            "ms_unit": 1790148600123,                          # 초가 아니라 ms 로 온 값(단위 혼동)
            "past": 1000,                                       # failed_at_ms 이전
            "beyond_8_days": 1790059113 + 9 * 24 * 60 * 60,      # failed_at 초 + 9일
        }
        for label, resets_at in malformed_resets_at_by_label.items():
            with self.subTest(label=label):
                result = hub_transcript.parse_session_tail(
                    _error_line(quota_limits={"resetsAt": resets_at})
                ).turn_failure
                self.assertIsNotNone(result)
                self.assertIsNone(result.resets_at_ms)

    def test_t9_missing_or_broken_timestamp_returns_none(self) -> None:
        payload_without_timestamp = json.loads(_error_line())
        del payload_without_timestamp["timestamp"]
        self.assertIsNone(
            hub_transcript.parse_session_tail(json.dumps(payload_without_timestamp)).turn_failure
        )
        self.assertIsNone(
            hub_transcript.parse_session_tail(_error_line(timestamp="not-a-timestamp")).turn_failure
        )

    def test_t10_non_string_error_returns_none_but_shape_violation_becomes_unknown(self) -> None:
        """구조적 이상(error 가 비문자열) → 줄 전체를 버린다(None). 어휘적 이상(형태 위반,
        문자열이지만 ERROR_KIND_PATTERN 불일치) → normalize_error_kind 가 "unknown" 으로
        접을 뿐 줄은 여전히 유효한 오류 줄로 남는다."""
        self.assertIsNone(hub_transcript.parse_session_tail(_error_line(error=12345)).turn_failure)

        result = hub_transcript.parse_session_tail(_error_line(error="Rate Limit!")).turn_failure
        self.assertIsNotNone(result)
        self.assertEqual(result.error_kind, "unknown")

    def test_t11_model_and_last_prompt_detection_unaffected_by_turn_failure(self) -> None:
        """E11 — 기존 기대가 turn_failure 판독 추가로 흔들리지 않는지 다시 확인한다."""
        tail = "\n".join([
            _assistant_line("claude-opus-5", effort="xhigh"),
            _last_prompt_line("마지막 프롬프트"),
            _error_line(),
        ])
        result = hub_transcript.parse_session_tail(tail)
        self.assertEqual(result.model.model_label, "Opus 5")
        self.assertEqual(result.last_prompt, "마지막 프롬프트")
        self.assertIsNotNone(result.turn_failure)

    def test_t12_error_line_message_content_is_never_read(self) -> None:
        secret = "sk-ant-abcdefghijklmnopqrstuvwxyz"
        tail = _error_line(message={
            "model": hub_transcript.SYNTHETIC_MODEL_ID,
            "content": [{"type": "text", "text": f"오류 세부 {secret}"}],
        })
        result = hub_transcript.parse_session_tail(tail)
        self.assertNotIn(secret, str(result.turn_failure))
        self.assertNotIn(secret, str(result.model))
        self.assertNotIn(secret, str(result.last_prompt))


_TOOL_RESULT_BLOCK = {"type": "tool_result", "tool_use_id": "toolu_01", "content": "도구 결과 본문"}
_IMAGE_BLOCK = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAAA"}}


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


class EpochMsFromIso8601Test(unittest.TestCase):
    """LA-T1(docs/prps/hub-live-activity.md 결정 LA14) — hub_activity 가 사적 심볼 없이 같은 "Z" 처리를 쓰도록 공개된 이름."""

    def test_utc_z_suffix_is_parsed(self) -> None:
        self.assertEqual(hub_transcript.epoch_ms_from_iso8601("2026-10-07T00:00:01.500Z"), 1791331201500)

    def test_utc_z_suffix_is_parsed_under_python310_semantics(self) -> None:
        class _Python310SemanticsFromIsoformat:
            @staticmethod
            def fromisoformat(value):
                if isinstance(value, str) and value.endswith("Z"):
                    raise ValueError(f"Invalid isoformat string: {value!r}")
                return datetime.fromisoformat(value)

        with mock.patch.object(hub_transcript, "datetime", _Python310SemanticsFromIsoformat):
            result = hub_transcript.epoch_ms_from_iso8601("2026-10-07T00:00:01.500Z")

        self.assertEqual(result, 1791331201500)

    def test_non_string_and_garbage_return_none(self) -> None:
        self.assertIsNone(hub_transcript.epoch_ms_from_iso8601(1791331201500))
        self.assertIsNone(hub_transcript.epoch_ms_from_iso8601("not a time"))
        self.assertIsNone(hub_transcript.epoch_ms_from_iso8601(None))


class ParseSessionTailHumanPromptTest(unittest.TestCase):
    """결정 TF1~TF4(docs/prps/hub-agent-title-and-excerpt-freshness.md §9.1). 호스트는 last-prompt 줄을 대화 기록이
    32KiB 쌓일 때마다만 다시 적으므로(§2.2), 꼬리에서 사람 프롬프트 줄이 마지막 last-prompt 줄보다 파일상 뒤에 있으면
    그 줄에서 호스트 규칙으로 유도한 값이 발췌다. 표 H1~H19 와 경계·방어 검사."""

    def _last_prompt_of(self, *lines: str) -> str | None:
        return hub_transcript.parse_session_tail("\n".join(lines)).last_prompt

    # ---- TF1: 파일에서 더 뒤의 것이 이긴다 ----

    def test_h1_human_line_after_last_prompt_line_is_the_excerpt(self) -> None:
        """요구 ② 회귀 검사 — 방금 입력한 프롬프트가 아직 last-prompt 에 실리기 전에도 보인다."""
        result = self._last_prompt_of(_last_prompt_line("옛 프롬프트"), _human_line("새 프롬프트"))
        self.assertEqual(result, "새 프롬프트")

    def test_h2_last_prompt_line_after_human_line_confirms_the_same_value(self) -> None:
        result = self._last_prompt_of(_human_line("새 프롬프트"), _last_prompt_line("새 프롬프트"))
        self.assertEqual(result, "새 프롬프트")

    def test_h2b_later_last_prompt_line_wins_over_earlier_human_line_even_if_values_differ(self) -> None:
        """'파일에서 더 뒤의 것' 규칙(TF1)의 뒷면 — 호스트 값이 뒤에 실렸으면 유도값이 아니라 그것이 발췌다."""
        result = self._last_prompt_of(_human_line("유도될 프롬프트 본문"), _last_prompt_line("호스트가 적은 값"))
        self.assertEqual(result, "호스트가 적은 값")

    def test_non_string_last_prompt_line_after_human_line_still_confirms_none(self) -> None:
        """오늘의 규칙 유지 — 가장 뒤의 last-prompt 줄이 권위 있는 값이라 비문자열이면 더 앞 줄로 넘어가지 않는다."""
        result = self._last_prompt_of(_human_line("앞선 프롬프트"), _last_prompt_line(12345))
        self.assertIsNone(result)

    def test_h3_human_line_alone_is_the_excerpt(self) -> None:
        self.assertEqual(self._last_prompt_of(_human_line("새 프롬프트")), "새 프롬프트")

    # ---- TF2: 사람 프롬프트 줄 판정 — 호스트가 붙인 표지만 믿는다 ----

    def test_h4_user_line_without_origin_is_not_derived(self) -> None:
        """구버전 호스트·SDK 세션 — origin 이 없으면 오늘과 같은 last-prompt 경로."""
        plain_user_line = json.dumps({"type": "user", "message": {"role": "user", "content": "새 프롬프트"}})
        self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), plain_user_line), "옛 프롬프트")

    def test_h5_user_lines_from_other_origins_are_not_derived(self) -> None:
        for origin_kind in ("task-notification", "coordinator", "peer"):
            with self.subTest(origin_kind=origin_kind):
                line = _human_line("서브에이전트 보고 본문", origin={"kind": origin_kind})
                self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    def test_h6_human_line_flagged_meta_sidechain_or_compact_summary_is_not_derived(self) -> None:
        for flag in ("isMeta", "isSidechain", "isCompactSummary"):
            with self.subTest(flag=flag):
                line = _human_line("새 프롬프트", **{flag: True})
                self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    def test_h7_tool_result_user_line_is_not_derived(self) -> None:
        """origin 이 human 이어도 tool_result 블록이 있는 줄은 프롬프트가 아니다 — 섞인 줄도 통째로 제외한다."""
        for label, content in (
            ("only_tool_result", [_TOOL_RESULT_BLOCK]),
            ("text_and_tool_result", [_text_block("본문처럼 보이는 글"), _TOOL_RESULT_BLOCK]),
        ):
            with self.subTest(label=label):
                line = _human_line(content)
                self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    def test_user_line_shapes_that_are_not_prompts_fall_back_without_raising(self) -> None:
        malformed_lines = {
            "origin_is_a_string": _human_line("본문", origin="human"),
            "message_is_a_string": json.dumps({"type": "user", "origin": {"kind": "human"}, "message": "본문"}),
            "message_without_content": json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {}}),
            "content_is_a_number": _human_line(12345),
            "content_is_null": _human_line(None),
            "text_is_a_number": _human_line([{"type": "text", "text": 12345}]),
            "blocks_are_not_dicts": _human_line(["본문", 7, None]),
            "no_blocks": _human_line([]),
        }
        for label, line in malformed_lines.items():
            with self.subTest(label=label):
                self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    # ---- TF3: 호스트 규칙의 부분 사본 ----

    def test_h8_leading_auto_injected_block_is_skipped_and_next_text_block_is_used(self) -> None:
        line = _human_line([_text_block("<ide_opened_file>편집기에서 열린 파일 안내</ide_opened_file>"), _text_block("본문")])
        self.assertEqual(self._last_prompt_of(line), "본문")

    def test_h9_interrupt_marker_block_is_skipped_and_next_text_block_is_used(self) -> None:
        for marker in ("[Request interrupted by user]", "[Request interrupted by user for tool use]"):
            with self.subTest(marker=marker):
                line = _human_line([_text_block(marker), _text_block("다시")])
                self.assertEqual(self._last_prompt_of(line), "다시")

    def test_line_with_only_auto_injected_or_blank_text_is_not_derived(self) -> None:
        for label, content in (
            ("system_reminder_only", [_text_block("<system-reminder>자동주입 안내</system-reminder>")]),
            ("blank_string", "  \n \t "),
            ("blank_block", [_text_block("   ")]),
        ):
            with self.subTest(label=label):
                line = _human_line(content)
                self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    def test_text_that_only_looks_like_a_tag_is_still_a_prompt(self) -> None:
        """호스트 l7t 는 소문자로 시작하는 태그 이름 뒤에 공백·'>' 가 올 때만 건너뛴다."""
        for prompt in ("<3 고마워요", "<Foo> 는 대문자라 태그가 아니다", "a <b> c 처럼 앞에 글이 있다"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self._last_prompt_of(_human_line(prompt)), prompt)

    def test_h10_command_line_is_given_up_and_earlier_human_line_is_used(self) -> None:
        """포기한 줄은 확정하지 않는다 — 그 앞의 유도 가능한 사람 줄(또는 last-prompt)이 정한다."""
        command_line = _human_line("<command-name>/x</command-name>\n<command-args>인자</command-args>")
        result = self._last_prompt_of(_last_prompt_line("옛 프롬프트"), _human_line("A 프롬프트"), command_line)
        self.assertEqual(result, "A 프롬프트")

    def test_h10b_command_marker_gives_up_the_whole_line_even_when_a_plain_block_follows(self) -> None:
        """태그로 시작하는 블록은 어차피 건너뛰므로, 포기 규칙이 따로 필요한 경우는 뒤에 평문 블록이 더 있는 줄이다."""
        line = _human_line([_text_block("<command-name>/x</command-name>"), _text_block("인자처럼 보이는 평문")])
        self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    def test_h11_bash_input_line_is_given_up(self) -> None:
        for label, content in (
            ("bash_block_alone", "<bash-input>ls</bash-input>"),
            ("bash_marker_after_plain_text", "설명 뒤에 <bash-input>ls</bash-input> 가 붙은 줄"),
        ):
            with self.subTest(label=label):
                line = _human_line(content)
                self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), line), "옛 프롬프트")

    def test_h12_pasted_content_wrapper_is_unwrapped(self) -> None:
        wrapped = '<pasted_content id="1a2b">\n붙인 글\n</pasted_content id="1a2b">'
        self.assertEqual(self._last_prompt_of(_human_line(wrapped)), "붙인 글")

    def test_h12b_pasted_content_wrapper_also_absorbs_the_newlines_outside_its_markers(self) -> None:
        """호스트 xue 는 표지 안쪽 줄바꿈뿐 아니라 바깥쪽(여는 표지 앞·닫는 표지 뒤 각 최대 2개)도 함께 벗기고 조각을 구분자
        없이 잇는다. 바깥쪽을 남기면 글 한가운데 붙여 넣은 줄이 호스트 값보다 공백이 1~2칸 많아진다(설계 때 14일 재생의
        불일치 1/453 이 이 차이였다). 기대값은 호스트 알고리즘을 손으로 따라간 독립 리터럴이다."""
        open_marker = '<pasted_content id="1a2b">\n'
        close_marker = '\n</pasted_content id="1a2b">'
        cases = (
            ("two_newlines_each_side", "앞 글\n\n" + open_marker + "붙인 글" + close_marker + "\n\n뒷 글", "앞 글붙인 글뒷 글"),
            ("one_newline_each_side", "앞 글\n" + open_marker + "붙인 글" + close_marker + "\n뒷 글", "앞 글붙인 글뒷 글"),
            # 최대 2개까지만 벗긴다 — 셋째 줄바꿈은 남아 공백이 된다
            ("third_newline_stays_as_a_space",
             "앞 글\n\n\n" + open_marker + "붙인 글" + close_marker + "\n\n\n뒷 글", "앞 글 붙인 글 뒷 글"),
            ("marker_at_the_start_of_the_text", open_marker + "붙인 글" + close_marker + "\n\n뒷 글", "붙인 글뒷 글"),
            # 표지 안쪽 본문의 줄바꿈은 벗기지 않는다 — 공백으로 남는다
            ("inner_newlines_of_the_body_stay_as_spaces", open_marker + "첫 줄\n둘째 줄" + close_marker, "첫 줄 둘째 줄"),
        )
        for label, prompt, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(self._last_prompt_of(_human_line(prompt)), expected)

    def test_text_that_starts_with_an_auto_injected_tag_after_unwrapping_is_skipped(self) -> None:
        """벗기기(xue)가 태그 건너뛰기(l7t)보다 먼저다 — H12 가 그 순서를 묶는다(감싸기 태그 자체도 소문자 태그 모양이라
        l7t 가 먼저면 붙여 넣은 글이 전부 사라진다). 벗긴 뒤의 글이 자동주입 태그로 시작하면 호스트처럼 건너뛴다."""
        wrapped_tag = '<pasted_content id="1a2b">\n<ide_selection>선택 영역</ide_selection>\n</pasted_content id="1a2b">'
        self.assertIsNone(self._last_prompt_of(_human_line(wrapped_tag)))

    def test_h15_string_content_is_used_as_is(self) -> None:
        self.assertEqual(self._last_prompt_of(_human_line("공백  두 칸과 한글 English 12")), "공백  두 칸과 한글 English 12")

    def test_h16_image_block_is_ignored_and_text_block_is_used(self) -> None:
        self.assertEqual(self._last_prompt_of(_human_line([_IMAGE_BLOCK, _text_block("그림 설명")])), "그림 설명")

    def test_h17_image_only_line_is_given_up_and_last_prompt_line_is_used(self) -> None:
        result = self._last_prompt_of(_last_prompt_line("옛 프롬프트"), _human_line([_IMAGE_BLOCK]))
        self.assertEqual(result, "옛 프롬프트")

    # ---- TF4: 줄바꿈 → 공백 · 호스트식 200자 절단 · 스크럽이 절단보다 먼저 · 400자 최종 관문 ----

    def test_h13_newlines_become_spaces_and_text_is_cut_at_200_chars_with_ellipsis(self) -> None:
        result = self._last_prompt_of(_human_line("줄1\n줄2 " + "가" * 300))
        # 독립 계산 리터럴 — 앞 200자는 「줄1 줄2 」 6자 + 「가」 194자, 뒤에 말줄임표 1자
        self.assertEqual(result, "줄1 줄2 " + "가" * 194 + "…")

    def test_cut_boundary_is_exactly_200_chars(self) -> None:
        self.assertEqual(self._last_prompt_of(_human_line("가" * 200)), "가" * 200)
        self.assertEqual(self._last_prompt_of(_human_line("가" * 201)), "가" * 200 + "…")

    def test_whitespace_at_the_cut_and_at_the_edges_is_stripped(self) -> None:
        """호스트식 — 앞뒤 공백을 걷어 낸 뒤 자르고, 자른 끝의 공백도 걷어 낸 다음 말줄임표를 붙인다."""
        self.assertEqual(self._last_prompt_of(_human_line("  \n앞뒤 공백  \n")), "앞뒤 공백")
        self.assertEqual(self._last_prompt_of(_human_line("가" * 199 + " " + "나" * 50)), "가" * 199 + "…")

    def test_h14_secret_straddling_the_cut_is_scrubbed_before_cutting(self) -> None:
        """PS9 와 같은 판별력 설계 — 스크럽이 절단보다 먼저다. 절단이 먼저면 시크릿이 10자 접두(sk-ant-xxx)만 남아 패턴의
        최소 길이({10,})를 못 채우고 살아남아 assertNotIn 이 실패한다."""
        secret = "sk-ant-" + "x" * 40
        prompt = "가" * (hub_transcript.HOST_LAST_PROMPT_MAX_CHARS - 10) + secret + "가" * 50
        result = self._last_prompt_of(_human_line(prompt))
        self.assertNotIn("sk-ant-", result)
        self.assertIn("[REDACTED]", result)

    def test_final_gate_still_clips_derived_value_to_last_prompt_max_chars(self) -> None:
        """유도 경로도 last-prompt 경로와 같은 단일 최종 관문(400자)을 지난다. 호스트 절단값(200)이 정상이라 평소에는
        발동하지 않으므로, 절단값 상수를 키워 관문만 남기고 확인한다."""
        with mock.patch.object(hub_transcript, "HOST_LAST_PROMPT_MAX_CHARS", 1000):
            result = self._last_prompt_of(_human_line("가" * 900))
        self.assertEqual(len(result), hub_transcript.LAST_PROMPT_MAX_CHARS)
        self.assertTrue(result.endswith("…"))

    def test_last_prompt_line_path_is_unchanged_by_the_host_cut(self) -> None:
        """last-prompt 경로는 오늘과 한 글자도 같다 — 200자 절단을 다시 걸지 않고 400자 관문만 지난다."""
        self.assertEqual(self._last_prompt_of(_last_prompt_line("가" * 300)), "가" * 300)

    # ---- 스크럽 입력 길이 제한(M1 검수 MEDIUM — 가용성) ----

    def _scrub_inputs_of(self, *lines: str) -> tuple[str | None, list[str]]:
        """parse_session_tail 을 돌리며 스크럽(redact_secret_tokens)에 넘어간 글들을 모은다. 스크럽은 그대로 실행한다(wraps)."""
        original_redact = hub_transcript.redact_secret_tokens
        with mock.patch.object(hub_transcript, "redact_secret_tokens", wraps=original_redact) as redact_spy:
            last_prompt = self._last_prompt_of(*lines)
        return last_prompt, [call.args[0] for call in redact_spy.call_args_list]

    def test_scrub_input_of_a_huge_pasted_line_is_capped_so_collection_cannot_stall(self) -> None:
        """회귀 가드 — 스크럽의 JWT 대안은 점 없이 eyJ 가 반복되는 긴 글에서 길이의 제곱에 비례해 느려져(128KiB 에 8초, 검수
        실측) 유도 경로가 원문 전체를 스크럽하면 그 줄이 꼬리 창에 있는 동안 요청 시 동기 수집이 매번 수 초 걸린다. 시간을
        재면 비결정적이라 스크럽에 넘어간 글의 길이를 단언한다. 붙여 넣기로 생길 수 있는 10만 자 한 줄을 쓴다."""
        huge_line = _human_line("eyJ" * 33334)   # 100,002자

        last_prompt, scrub_inputs = self._scrub_inputs_of(huge_line)

        self.assertEqual(len(scrub_inputs), 1)
        self.assertLessEqual(len(scrub_inputs[0]), hub_transcript.DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS)
        # 화면에 나가는 값은 여전히 호스트식 앞 200자 + 말줄임표다 — 독립 계산 리터럴(66번 반복 + 「ey」 = 200자)
        self.assertEqual(last_prompt, "eyJ" * 66 + "ey" + "…")

    def test_scrub_input_is_the_first_cap_chars_of_the_flattened_prompt(self) -> None:
        """상한 경계 — 딱 상한이면 통째로, 하나 넘으면 앞 상한만큼, 짧으면 그대로. 자르기는 줄바꿈→공백·strip 뒤에 하므로 글머리의
        빈 줄이 창을 먹지 않는다."""
        cap = hub_transcript.DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS
        cases = (
            ("exactly_the_cap_passes_through_whole", "가" * cap, cap),
            ("one_over_the_cap_is_cut_to_the_cap", "가" * (cap + 1), cap),
            ("shorter_than_the_cap_passes_through_whole", "가" * 50, 50),
            ("leading_blank_lines_do_not_eat_the_window", "\n" * (cap + 10) + "가" * 50, 50),
        )
        for label, prompt, expected_length in cases:
            with self.subTest(label=label):
                _, scrub_inputs = self._scrub_inputs_of(_human_line(prompt))
                self.assertEqual([len(scrub_input) for scrub_input in scrub_inputs], [expected_length])

    def test_secret_in_the_head_of_a_huge_line_is_still_scrubbed(self) -> None:
        """제한은 화면에 나가는 앞부분(200자)보다 훨씬 넓다 — 긴 줄의 머리에 있는 시크릿은 여전히 절단 전에 마스킹된다."""
        secret = "sk-ant-" + "x" * 40
        visible_head = "키 [REDACTED] 공유 "   # 16자

        result = self._last_prompt_of(_human_line("키 " + secret + " 공유 " + "가" * 100000))

        self.assertEqual(result, visible_head + "가" * (200 - len(visible_head)) + "…")

    # ---- 스크럽 창 끝 조각(M1 재검수 LOW-A — 보안) ----
    # 창(cap 자)의 끝이 시크릿을 한가운데서 가르면 그 조각은 패턴 최소 길이에 못 미쳐 마스킹되지 않는다. 앞부분이 개인키 블록처럼
    # 크게 접히면 창 끝이 화면(앞 200자)에 나온다. 합성 값만 쓴다.

    def _prompt_cut_inside(self, secret: str, filler: str = "", separator: str = ": ") -> str:
        """스크럽 창의 끝이 secret 의 마지막 글자 바로 앞에 오는 프롬프트: 개인키 블록(창을 접는다) + filler + separator +
        secret[:-1] | secret[-1] + 「 뒷 글」. 창은 앞 cap 자라 secret[:-1] 까지만 담고, 자른 자리 양쪽이 낱말 글자다."""
        tail = filler + separator + secret[:-1]
        cap = hub_transcript.DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS
        return _key_block(cap - len(tail)) + tail + secret[-1] + " 뒷 글"

    def test_cut_secret_fragment_at_the_scrub_window_end_is_dropped_when_the_masked_window_collapses(self) -> None:
        """검수자 재현 형태 — 개인키 블록 + 「: 」 + ghp_ 토큰(본문 36자)이 창 끝에 한 글자 모자라게 걸리면, 고정 길이 패턴이라
        조각이 마스킹되지 않고 접힌 결과(51자) 안에서 통째로 화면에 나왔다. 끝 낱말을 버려 닫는다."""
        token = "ghp_" + "b" * 36
        prompt = self._prompt_cut_inside(token)
        # 전제 — 조각이 스크럽을 그대로 통과한다(이 검사가 공허하지 않다)
        window = prompt[: hub_transcript.DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS]
        self.assertIn(token[:-1], hub_transcript.redact_secret_tokens(window))

        result = self._last_prompt_of(_human_line(prompt))

        self.assertEqual(result, "[REDACTED]:")

    def test_every_fixed_length_secret_shape_cut_one_short_is_dropped(self) -> None:
        """hub_redact 의 최소·고정 길이 패턴마다 한 글자 모자라게 잘린 조각(마스킹 안 됨)이 창 끝에서 버려진다. Bearer 는 낱말
        사이에 공백이 있어 앞의 「Bearer」 만 남는다."""
        shapes = (
            ("aws", "AKIA" + "B" * 16, "[REDACTED]:"),
            ("github", "ghp_" + "b" * 36, "[REDACTED]:"),
            ("google", "AIza" + "c" * 35, "[REDACTED]:"),
            ("openai", "sk-" + "d" * 20, "[REDACTED]:"),
            ("github_pat", "github_pat_" + "e" * 22, "[REDACTED]:"),
            ("anthropic", "sk-ant-" + "f" * 10, "[REDACTED]:"),
            ("slack", "xoxb-" + "g" * 10, "[REDACTED]:"),
            ("bearer", "Bearer " + "h" * 16, "[REDACTED]: Bearer"),
        )
        for label, token, expected in shapes:
            with self.subTest(label=label):
                self.assertEqual(self._last_prompt_of(_human_line(self._prompt_cut_inside(token))), expected)

    def test_window_end_fragment_with_no_word_boundary_gives_up_derivation_and_falls_back(self) -> None:
        """결과 전체가 한 낱말이면(「[REDACTED]:ghp_…」) 경계 조각을 가려낼 수 없다 — 안전한 쪽으로 유도를 포기하고 더 앞 줄(옛
        last-prompt 값·더 앞 사람 줄)로 물러난다. 없으면 None. 포기한 줄은 확정하지 않는다(명령·bash 줄과 같은 처리)."""
        prompt = self._prompt_cut_inside("ghp_" + "b" * 36, separator=":")

        self.assertEqual(self._last_prompt_of(_last_prompt_line("옛 프롬프트"), _human_line(prompt)), "옛 프롬프트")
        self.assertEqual(self._last_prompt_of(_human_line("A 프롬프트"), _human_line(prompt)), "A 프롬프트")
        self.assertIsNone(self._last_prompt_of(_human_line(prompt)))

    def test_fragment_reaching_into_the_screen_band_is_dropped_and_beyond_it_is_left_alone(self) -> None:
        """결과 길이가 화면(200자)을 조금 넘어도 끝 조각(최대 39자)이 앞 200자에 걸린다 — 「결과 < 200」 만으로는 못 닫는 띠.
        filler 100·150·160·188 은 결과 150·200·210·238자(조각 시작 111·161·171·199 < 200)라 버려지고, 190·300 은 조각이
        화면 밖이라 평소의 200자 절단 그대로다."""
        token = "ghp_" + "b" * 36
        for filler_length in (100, 150, 160, 188):
            with self.subTest(dropped_filler_length=filler_length):
                prompt = self._prompt_cut_inside(token, filler="가" * filler_length, separator=" ")
                self.assertEqual(self._last_prompt_of(_human_line(prompt)), "[REDACTED]" + "가" * filler_length)
        for filler_length in (190, 300):
            with self.subTest(untouched_filler_length=filler_length):
                prompt = self._prompt_cut_inside(token, filler="가" * filler_length, separator=" ")
                self.assertEqual(self._last_prompt_of(_human_line(prompt)), "[REDACTED]" + "가" * 190 + "…")

    def test_boundary_fragment_limit_covers_the_longest_fixed_length_secret_fragment(self) -> None:
        """조각 상한은 고정 길이 패턴 중 가장 긴 것(ghp_ + 본문 36자)이 한 글자 모자라 잘린 조각 이상이어야 한다."""
        self.assertGreaterEqual(hub_transcript.BOUNDARY_FRAGMENT_MAX_CHARS, len("ghp_" + "b" * 35))

    def test_boundary_handling_leaves_the_normal_paths_untouched(self) -> None:
        """창이 안 잘렸거나 결과가 충분히 길면 오늘과 같다 — 끝 낱말을 버리지 않는다."""
        cap = hub_transcript.DERIVED_PROMPT_SCRUB_INPUT_MAX_CHARS
        cases = (
            # 창이 안 잘렸다(길이 < cap) — 접힌 결과가 짧아도 끝 낱말은 원문의 진짜 끝이다
            ("window_not_cut_keeps_the_last_word", _key_block(cap - 20) + ": 끝낱말", "[REDACTED]: 끝낱말"),
            # 길이가 딱 cap 자다 — 길이 == cap 은 잘린 것이 아니다(경계 검사)
            ("window_exactly_cap_long_is_not_cut", _key_block(cap - 4) + ": 끝낱", "[REDACTED]: 끝낱"),
            # 창은 잘렸지만 결과가 길어 끝 낱말이 화면 밖이다
            ("long_prose_keeps_the_normal_200_char_cut", "가나다 " * 1000, "가나다 " * 49 + "가나다" + "…"),
            # 공백 없는 거대한 한 줄 — 결과가 길어 조각이 화면 밖이다(머리는 스크럽을 거친 안전한 부분이다)
            ("giant_unbroken_run_keeps_the_head", "가" * 5000, "가" * 200 + "…"),
        )
        for label, prompt, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(self._last_prompt_of(_human_line(prompt)), expected)

    # ---- 대화 줄 판정·모델 탐지는 그대로 ----

    def test_h18_conversation_line_judgement_and_model_detection_are_unchanged(self) -> None:
        failed_turn_lines = [_assistant_line("claude-opus-5", effort="xhigh"), _error_line()]
        without_human_line = hub_transcript.parse_session_tail("\n".join(failed_turn_lines))
        self.assertIsNotNone(without_human_line.turn_failure)   # 대조 — 사람 줄이 없으면 오류 턴이 잡힌다

        result = hub_transcript.parse_session_tail("\n".join(failed_turn_lines + [_human_line("새 프롬프트")]))

        self.assertIsNone(result.turn_failure)   # 사람 줄이 마지막 대화 줄이 되면 오류 턴은 끝난 것이다
        self.assertEqual(result.model.model_label, "Opus 5")
        self.assertEqual(result.last_prompt, "새 프롬프트")

    def test_h19_torn_first_line_is_dropped_like_any_broken_json(self) -> None:
        """꼬리 경계에서 잘린 사람 줄은 JSON 이 깨져 탈락한다 — 그런 큰 줄은 호스트가 같은 드레인에서 last-prompt 를 바로
        붙이므로 폴백이 이미 새 값이다."""
        torn_line = _human_line("잘린 줄의 프롬프트")[10:]
        self.assertIsNone(self._last_prompt_of(torn_line))


if __name__ == "__main__":
    unittest.main()
