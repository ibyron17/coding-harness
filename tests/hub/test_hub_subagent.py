"""hub_subagent 단위 테스트. docs/prps/hub-agent-runs-and-prompt-source.md 「테스트 계획」
(§10.1)의 test_hub_subagent.py 표 전체 — parse_subagent_meta(계약 B)·시크릿 스크럽(AR10)·
타입 방어.

docs/prps/hub-agent-title-and-excerpt-freshness.md §9.2 의 S1~S11(결정 TF8·TF10) — 부모 transcript 창에서 재개 요청의
요약을 파는 parse_resume_titles. 제목 스크럽 입력 상한(SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS)과 요청 색인의 경계 테스트는
test_hub_subagent_bounds.py 에 있다(이 파일이 800줄 상한에 가까워 나눴다)."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_subagent  # noqa: E402  (sys.path 조정 후 임포트)

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다(test_hub_template_dom.py 의 관례).
try:
    from .resume_transcript_fixtures import (
        AGENT_ID,
        NO_SUMMARY,
        OTHER_AGENT_ID,
        resume_result_line as _resume_result_line,
        send_message_line as _send_message_line,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from resume_transcript_fixtures import (  # noqa: E402
        AGENT_ID,
        NO_SUMMARY,
        OTHER_AGENT_ID,
        resume_result_line as _resume_result_line,
        send_message_line as _send_message_line,
    )

STARTED_AT_MS = 1_786_000_000_000


def _meta_payload(**overrides) -> dict:
    """실측 전문(§1.1)대로의 최소 subagents/agent-<id>.meta.json 본문. 개별 테스트가
    필요한 필드만 덮어쓴다."""
    payload = {
        "agentType": "Explore",
        "description": "대시보드 발행·종료 상태 판정 경로",
        "toolUseId": "toolu_01Tuf535i8L3HQXUG3SrWs7M",
        "spawnDepth": 1,
        "model": "haiku",
    }
    payload.update(overrides)
    return payload


def _meta_json(**overrides) -> str:
    return json.dumps(_meta_payload(**overrides))


class ParseSubagentMetaTest(unittest.TestCase):
    """정상 실행 파싱 — 실측 전문 그대로."""

    def test_realistic_payload_parses_all_fields(self) -> None:
        meta = hub_subagent.parse_subagent_meta(_meta_json(), STARTED_AT_MS)
        self.assertEqual(
            meta,
            hub_subagent.SubagentMeta(
                title="대시보드 발행·종료 상태 판정 경로",
                agent_type="Explore",
                model="haiku",
                started_at_ms=STARTED_AT_MS,
            ),
        )

    def test_started_at_ms_is_passed_through_verbatim(self) -> None:
        """started_at_ms 는 이 함수의 계산 대상이 아니라 I/O 층이 채워 넘기는 값이다(★순수)."""
        meta = hub_subagent.parse_subagent_meta(_meta_json(), 42)
        self.assertEqual(meta.started_at_ms, 42)


class MissingModelTest(unittest.TestCase):
    """`model` 키 없음 — 실측 818건 중 153건(18.7%)이 이 형태다. 부재가 정상 상태다."""

    def test_missing_model_key_yields_none_with_rest_intact(self) -> None:
        payload = _meta_payload()
        del payload["model"]
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertIsNone(meta.model)
        self.assertEqual(meta.agent_type, "Explore")
        self.assertEqual(meta.title, "대시보드 발행·종료 상태 판정 경로")


class MissingDescriptionTest(unittest.TestCase):
    def test_missing_description_yields_empty_title(self) -> None:
        payload = _meta_payload()
        del payload["description"]
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertEqual(meta.title, "")


class MalformedInputTest(unittest.TestCase):
    """계약 B(hub_workflow.parse_workflow_run 과 동형) — 어떤 입력에도 예외를 던지지 않는다."""

    def test_top_level_list_is_not_meta(self) -> None:
        self.assertIsNone(hub_subagent.parse_subagent_meta("[]", STARTED_AT_MS))

    def test_top_level_number_is_not_meta(self) -> None:
        self.assertIsNone(hub_subagent.parse_subagent_meta("3", STARTED_AT_MS))

    def test_top_level_string_is_not_meta(self) -> None:
        self.assertIsNone(hub_subagent.parse_subagent_meta('"x"', STARTED_AT_MS))

    def test_broken_json_returns_none(self) -> None:
        self.assertIsNone(hub_subagent.parse_subagent_meta("{", STARTED_AT_MS))

    def test_oversized_integer_literal_returns_none(self) -> None:
        """4,300자리 초과 정수 리터럴은 ValueError(자릿수 한도)를 던진다 — WF 3회차 재현과 같은 형태."""
        text = '{"spawnDepth": ' + "9" * 5000 + "}"
        self.assertIsNone(hub_subagent.parse_subagent_meta(text, STARTED_AT_MS))

    def test_deeply_nested_json_returns_none(self) -> None:
        """RecursionError 흡수 — 구현 2회차 검수 C-3 과 같은 형태."""
        text = "[" * 20000
        self.assertIsNone(hub_subagent.parse_subagent_meta(text, STARTED_AT_MS))


class TitleScrubbingAndClippingTest(unittest.TestCase):
    """AR10 계약 A — title(=description)은 스크럽 + SUBAGENT_TITLE_MAX_CHARS(120) 상한을 거친다."""

    def test_oversized_description_is_clipped_to_120_chars(self) -> None:
        """제목 상한(120자)을 넘는 description 은 120자로 잘린다 — 스크럽 입력 상한(SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS)까지는. 그 상한을
        넘는 글은 제목이 아니라 잘라 쓰지 않고 빈 제목으로 버린다(M2 검수 MEDIUM — test_hub_subagent_bounds.py 가 문다)."""
        payload = _meta_payload(description="다" * hub_subagent.SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS)
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertEqual(len(meta.title), hub_subagent.SUBAGENT_TITLE_MAX_CHARS)
        self.assertTrue(meta.title.endswith(hub_subagent.SUBAGENT_TRUNCATION_MARK))

    def test_secret_in_description_is_redacted(self) -> None:
        payload = _meta_payload(description="key sk-ant-AAAAAAAAAA0 포함")
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertIn("[REDACTED]", meta.title)
        self.assertNotIn("sk-ant-AAAAAAAAAA0", meta.title)

    def test_scrubbing_happens_before_clipping_not_after(self) -> None:
        """순서가 바뀌면(자르기 먼저) 120자 경계 근처의 시크릿이 패턴 불일치로 살아남는다.

        재검수 1회차 H2 — 원래 산문 100자는 절단 경계(119자)를 지나도 시크릿의 영숫자부가
        12자 남아 SECRET_TOKEN_PATTERN 의 최소 길이({10,})를 여전히 만족해, 순서를 뒤집어도
        (자르기 → 스크럽) 이 단언이 우연히 통과했다(판별력 없음, 검수자 실측). 산문을 110자로
        올리면 절단 후 남는 영숫자부가 2자(119-110-7)로 줄어 최소 길이 미달이 되고, 순서가
        뒤집혔을 때 이 단언이 실제로 실패한다 — 자르기 전에 반드시 스크럽해야 하는 이유가
        이 테스트에서 실제로 검증된다.

        재검수 2회차 수정 2 — 110 이 하드코딩이라 SUBAGENT_TITLE_MAX_CHARS 를 올리면(재검수자
        실측: 200 으로) 경계에서 멀어져 판별력이 사라졌다. SUBAGENT_TITLE_MAX_CHARS-10 으로
        유도해 상한이 바뀌어도 "경계 뒤 잔존 2자 < 10자" 관계가 자동으로 유지되게 한다.
        """
        secret = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
        description = ("가" * (hub_subagent.SUBAGENT_TITLE_MAX_CHARS - 10)) + secret + ("가" * 200)
        payload = _meta_payload(description=description)
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertNotIn("sk-ant-", meta.title)


class MetadataFieldLimitTest(unittest.TestCase):
    """AR10 계약 A — model·agent_type 은 상한만(스크럽 없음), SUBAGENT_METADATA_MAX_CHARS(32)."""

    def test_oversized_model_is_clipped_to_32_chars(self) -> None:
        payload = _meta_payload(model="상" * 200)
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertEqual(len(meta.model), hub_subagent.SUBAGENT_METADATA_MAX_CHARS)

    def test_non_string_agent_type_falls_back_to_empty_string(self) -> None:
        for bad_value in (123, None, ["Explore"]):
            with self.subTest(bad_value=bad_value):
                payload = _meta_payload(agentType=bad_value)
                meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
                self.assertEqual(meta.agent_type, "")

    def test_non_string_model_is_none_not_empty_string(self) -> None:
        """model 은 agent_type 과 달리 '' 이 아니라 None 이어야 한다 — 부재(18.7%)와
        빈 문자열을 구분해야 화면(모델 미기록 라벨)이 옳게 갈린다."""
        payload = _meta_payload(model=123)
        meta = hub_subagent.parse_subagent_meta(json.dumps(payload), STARTED_AT_MS)
        self.assertIsNone(meta.model)


class ClipMetadataPublicHelperTest(unittest.TestCase):
    """clip_metadata 는 훅 유래 agent_type·agent_id 에도 쓰도록 공개된다(§6.1)."""

    def test_short_value_is_unchanged(self) -> None:
        self.assertEqual(hub_subagent.clip_metadata("implementer"), "implementer")

    def test_oversized_value_is_clipped_with_truncation_mark(self) -> None:
        clipped = hub_subagent.clip_metadata("가" * 100)
        self.assertEqual(len(clipped), hub_subagent.SUBAGENT_METADATA_MAX_CHARS)
        self.assertTrue(clipped.endswith(hub_subagent.SUBAGENT_TRUNCATION_MARK))


class ResumeTitleFieldDefaultTest(unittest.TestCase):
    """결정 TF13 — SubagentMeta.resume_title 은 맨 뒤 기본값 None 이다: meta.json 만으로는 만들 수 없고, 기존 생성 지점은 무해하다."""

    def test_four_argument_construction_defaults_resume_title_to_none(self) -> None:
        meta = hub_subagent.SubagentMeta(title="t", agent_type="a", model=None, started_at_ms=0)

        self.assertIsNone(meta.resume_title)

    def test_parse_subagent_meta_never_fills_resume_title(self) -> None:
        meta = hub_subagent.parse_subagent_meta(_meta_json(), STARTED_AT_MS)

        self.assertIsNone(meta.resume_title)


# ---- 재개 요청 파서 (결정 TF8·TF10, docs/prps/hub-agent-title-and-excerpt-freshness.md §9.2 S1~S11) ----
# 줄 모양은 2.1.284 호스트의 부모 transcript 실측 그대로다(키·중첩만 — 글은 합성). 요청 = assistant 줄의 SendMessage tool_use,
# 결과 = 같은 tool_use_id 의 tool_result 를 담은 user 줄(toolUseResult 는 줄 최상위).

WANTED = frozenset({AGENT_ID})


def _window(*lines: str) -> bytes:
    """부모 transcript 창 — 호스트 파일처럼 UTF-8 bytes, 줄은 개행으로 잇는다(파서는 bytes 창을 받는다)."""
    return "\n".join(lines).encode("utf-8")


def _titles_of(window: bytes, wanted: frozenset[str] = WANTED) -> dict[str, str]:
    return hub_subagent.parse_resume_titles(window, wanted)


class ParseResumeTitlesTest(unittest.TestCase):
    """S1~S6·S9~S11 — 요청 ⋈ 결과 짝짓기와 「에이전트마다 가장 늦은 재개 1건」 규칙."""

    def test_s1_request_and_result_pair_yields_the_summary_for_the_resumed_agent(self) -> None:
        window = _window(_send_message_line("toolu_1", "합성 작업 이름"), _resume_result_line("toolu_1"))

        self.assertEqual(_titles_of(window), {AGENT_ID: "합성 작업 이름"})

    def test_s2_the_latest_of_two_resumes_of_the_same_agent_wins(self) -> None:
        window = _window(
            _send_message_line("toolu_old", "옛 작업 이름"), _resume_result_line("toolu_old"),
            _send_message_line("toolu_new", "새 작업 이름"), _resume_result_line("toolu_new"),
        )

        self.assertEqual(_titles_of(window), {AGENT_ID: "새 작업 이름"})

    def test_s3_a_delivery_without_resumed_agent_id_is_not_a_resume(self) -> None:
        """실행 중인 에이전트에게 메시지를 「전달」만 한 요청(Message queued)은 재개가 아니다 — 결과에 resumedAgentId 가 없다."""
        window = _window(_send_message_line("toolu_1", "전달만 한 요청"), _resume_result_line("toolu_1", None))

        self.assertEqual(_titles_of(window), {})

    def test_a_later_delivery_does_not_shadow_the_latest_real_resume(self) -> None:
        """재개 뒤에 같은 에이전트에게 전달만 한 요청이 있어도(재개가 아니므로) 가장 늦은 재개의 요약이 그대로 제목이다."""
        window = _window(
            _send_message_line("toolu_resume", "재개한 작업 이름"), _resume_result_line("toolu_resume"),
            _send_message_line("toolu_queued", "전달만 한 요청"), _resume_result_line("toolu_queued", None),
        )

        self.assertEqual(_titles_of(window), {AGENT_ID: "재개한 작업 이름"})

    def test_s4_latest_resume_without_a_usable_summary_gives_no_title_not_an_older_one(self) -> None:
        """옛 재개의 요약으로 대체하지 않는다 — 옛 작업 이름이 새 작업을 가리키는 오늘의 결함을 다른 모양으로 되살리지 않는다."""
        unusable_summaries = {
            "key_missing": NO_SUMMARY, "empty_string": "", "blank_string": "   ", "number": 123, "null": None,
            "list": ["작업"],
        }
        for label, unusable in unusable_summaries.items():
            with self.subTest(label=label):
                window = _window(
                    _send_message_line("toolu_old", "옛 작업 이름"), _resume_result_line("toolu_old"),
                    _send_message_line("toolu_new", unusable), _resume_result_line("toolu_new"),
                )

                self.assertEqual(_titles_of(window), {})

    def test_s5_a_request_without_its_result_or_a_result_without_its_request_gives_nothing(self) -> None:
        only_request = _window(_send_message_line("toolu_1", "결과가 아직 없는 요청"))
        only_result = _window(_resume_result_line("toolu_1"))   # 요청 줄이 창 앞에서 잘렸다

        self.assertEqual(_titles_of(only_request), {})
        self.assertEqual(_titles_of(only_result), {})

    def test_s5_a_latest_result_whose_request_is_outside_the_window_does_not_fall_back_to_an_older_pair(self) -> None:
        """가장 늦은 재개의 결과만 창 안에 있고 그 요청 줄은 창 경계 앞에 있으면(병렬 호출로 요청 줄이 옛 쌍보다 앞에 놓인 드문 모양)
        창 안의 더 옛 쌍이 있어도 그 요약을 쓰지 않는다 — 옛 작업 이름이 새 작업을 가리키는 결함을 되살리지 않는다."""
        window = _window(
            _send_message_line("toolu_old", "옛 작업 이름"), _resume_result_line("toolu_old"),
            _resume_result_line("toolu_new"),   # 새 요청(toolu_new)의 줄은 창 안에 없다
        )

        self.assertEqual(_titles_of(window), {})

    def test_s6_an_agent_that_was_not_asked_for_is_ignored(self) -> None:
        window = _window(
            _send_message_line("toolu_1", "다른 에이전트의 작업", to=OTHER_AGENT_ID),
            _resume_result_line("toolu_1", OTHER_AGENT_ID),
        )

        self.assertEqual(_titles_of(window), {})

    def test_an_empty_wanted_set_gives_nothing_without_parsing(self) -> None:
        window = _window(_send_message_line("toolu_1"), _resume_result_line("toolu_1"))

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window, frozenset())

        self.assertEqual(titles, {})
        loads_spy.assert_not_called()

    def test_each_wanted_agent_gets_its_own_latest_summary(self) -> None:
        window = _window(
            _send_message_line("toolu_a1", "A 의 옛 작업"), _resume_result_line("toolu_a1", AGENT_ID),
            _send_message_line("toolu_b1", "B 의 작업", to=OTHER_AGENT_ID), _resume_result_line("toolu_b1", OTHER_AGENT_ID),
            _send_message_line("toolu_a2", "A 의 새 작업"), _resume_result_line("toolu_a2", AGENT_ID),
        )

        titles = _titles_of(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {AGENT_ID: "A 의 새 작업", OTHER_AGENT_ID: "B 의 작업"})

    def test_s9_a_result_line_with_several_tool_result_blocks_is_not_mapped(self) -> None:
        """toolUseResult 는 줄 단위라 블록이 여럿이면 누구 결과인지 알 수 없다 — 매핑하지 않는다."""
        window = _window(_send_message_line("toolu_1"), _resume_result_line("toolu_1", block_count=2))

        self.assertEqual(_titles_of(window), {})

    def test_s10_the_pair_is_made_by_the_result_not_by_the_to_field(self) -> None:
        """to 는 이름으로 보낼 수도 있다 — 짝은 결과의 resumedAgentId 로 맺는다."""
        window = _window(_send_message_line("toolu_1", "이름으로 보낸 요청", to="reviewer"), _resume_result_line("toolu_1"))

        self.assertEqual(_titles_of(window), {AGENT_ID: "이름으로 보낸 요청"})

    def test_s11_a_tool_use_result_that_is_not_an_object_gives_nothing(self) -> None:
        """도구가 꺼져 있는 오류는 toolUseResult 가 문자열이다. 줄 최상위의 같은 이름 키(decoy)로 표지 거름을 통과시켜, 줄이 실제로
        풀려도 toolUseResult 가 객체가 아니면 매핑하지 않음을 본다."""
        error_result = json.loads(_resume_result_line("toolu_1"))
        error_result["toolUseResult"] = "Error: 합성 오류"
        error_result["resumedAgentId"] = AGENT_ID
        window = _window(_send_message_line("toolu_1"), json.dumps(error_result, ensure_ascii=False))

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {})
        self.assertEqual(loads_spy.call_count, 1)   # 오류 줄(표지를 품은 유일한 줄)은 풀렸다 — 거름이 아니라 타입 검사가 막았다

    def test_the_request_message_body_is_never_part_of_the_result(self) -> None:
        """본문(message)은 줄을 풀 때 메모리에 올라오지만 어디에도 싣지 않는다 — 결과 값은 요약 하나뿐이다."""
        window = _window(_send_message_line("toolu_1", "합성 작업 이름"), _resume_result_line("toolu_1"))

        self.assertNotIn("지시 본문", repr(_titles_of(window)))


class ParseResumeTitlesPairingTest(unittest.TestCase):
    """요청 ⋈ 결과 짝짓기의 인과·병렬 모양 — 결과 줄을 먼저 보고 그 줄 앞에서만 요청을 찾는다(PRP §2.1 구현 측정의 V5)."""

    def test_a_request_line_after_the_result_line_is_never_its_request(self) -> None:
        """요청은 자기 결과보다 앞에 있다(인과). 같은 id 의 요청이 결과 뒤에 있어도 짝으로 보지 않는다."""
        window = _window(_resume_result_line("toolu_1"), _send_message_line("toolu_1", "결과 뒤의 요청"))

        self.assertEqual(_titles_of(window), {})

    def test_parallel_requests_with_interleaved_results_each_resolve_to_their_own_summary(self) -> None:
        """A 요청 · B 요청 · A 결과 · B 결과 — 결과 사이에 끼어든 다른 요청을 건너뛰고 각자의 요청을 찾는다."""
        window = _window(
            _send_message_line("toolu_a", "A 의 작업"), _send_message_line("toolu_b", "B 의 작업", to=OTHER_AGENT_ID),
            _resume_result_line("toolu_a", AGENT_ID), _resume_result_line("toolu_b", OTHER_AGENT_ID),
        )

        titles = _titles_of(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {AGENT_ID: "A 의 작업", OTHER_AGENT_ID: "B 의 작업"})

    def test_two_requests_in_one_assistant_line_resolve_by_tool_use_id(self) -> None:
        """병렬 호출이 한 줄에 든 모양 — 같은 줄의 tool_use 둘 중 결과의 tool_use_id 와 같은 쪽의 요약을 쓴다."""
        first = json.loads(_send_message_line("toolu_a", "A 의 작업"))
        second = json.loads(_send_message_line("toolu_b", "B 의 작업", to=OTHER_AGENT_ID))
        first["message"]["content"].extend(second["message"]["content"])
        window = _window(
            json.dumps(first, ensure_ascii=False),
            _resume_result_line("toolu_a", AGENT_ID), _resume_result_line("toolu_b", OTHER_AGENT_ID),
        )

        titles = _titles_of(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {AGENT_ID: "A 의 작업", OTHER_AGENT_ID: "B 의 작업"})

    def test_a_request_for_another_id_before_the_result_is_skipped_over(self) -> None:
        window = _window(
            _send_message_line("toolu_mine", "내 작업"), _send_message_line("toolu_other", "다른 요청", to=OTHER_AGENT_ID),
            _resume_result_line("toolu_mine"),
        )

        self.assertEqual(_titles_of(window), {AGENT_ID: "내 작업"})

    def test_a_result_line_with_the_marker_twice_is_read_once(self) -> None:
        """한 줄에 표지가 여럿이어도(중첩 객체의 같은 키) 그 줄은 한 번만 푼다 — 값은 줄 최상위 toolUseResult 의 것이다."""
        result = json.loads(_resume_result_line("toolu_1"))
        result["toolUseResult"]["pin"] = {"resumedAgentId": OTHER_AGENT_ID}
        window = _window(_send_message_line("toolu_1", "합성 작업 이름"), json.dumps(result, ensure_ascii=False))

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {AGENT_ID: "합성 작업 이름"})
        self.assertEqual(loads_spy.call_count, 2)   # 결과 줄 1번 + 요청 줄 1번


class MarkerLineGeneratorTest(unittest.TestCase):
    """_lines_with_marker_backwards — 표지를 품은 줄의 (시작, 끝) 을 뒤에서 앞으로 한 줄씩 낸다(순수, bytes 입출력)."""

    MARKER = b'"K"'

    def _lines(self, window: bytes, bound: int | None = None) -> list[bytes]:
        limit = len(window) if bound is None else bound
        return [window[start:end] for start, end in hub_subagent._lines_with_marker_backwards(window, self.MARKER, limit)]

    def test_yields_marker_lines_from_the_end_and_skips_lines_without_the_marker(self) -> None:
        window = b'a"K"1\nplain\nb"K"2\nplain2\nc"K"3\n'

        self.assertEqual(self._lines(window), [b'c"K"3', b'b"K"2', b'a"K"1'])

    def test_a_line_with_the_marker_several_times_is_yielded_once(self) -> None:
        window = b'first\n"K" x "K" y "K"\nlast\n'

        self.assertEqual(self._lines(window), [b'"K" x "K" y "K"'])

    def test_first_and_last_lines_without_surrounding_newlines_are_found(self) -> None:
        self.assertEqual(self._lines(b'"K"first\nmid\nlast"K"'), [b'last"K"', b'"K"first'])
        self.assertEqual(self._lines(b'only "K" line'), [b'only "K" line'])

    def test_bound_hides_lines_at_or_after_it(self) -> None:
        window = b'a"K"1\nb"K"2\nc"K"3\n'
        second_line_start = window.index(b"b")

        self.assertEqual(self._lines(window, second_line_start), [b'a"K"1'])
        self.assertEqual(self._lines(window, 0), [])

    def test_empty_and_marker_free_windows_yield_nothing(self) -> None:
        for window in (b"", b"\n", b"no marker here\nat all\n"):
            with self.subTest(window=window):
                self.assertEqual(self._lines(window), [])

    def test_lines_split_only_on_newline_bytes_not_on_unicode_line_separators(self) -> None:
        """U+2028·U+2029·U+0085 는 JSON 문자열 안에 그대로 들어올 수 있다(호스트 JSON.stringify 는 이스케이프하지 않는다) — 줄 경계가 아니다."""
        line = '앞 "K" 뒤\u0085끝'.encode("utf-8")

        self.assertEqual(self._lines(b"x\n" + line + b"\ny"), [line])

    def test_multibyte_characters_never_contain_the_newline_byte(self) -> None:
        """줄 경계(0x0A)가 다중 바이트 글자 한가운데 나올 수 없다는 UTF-8 성질에 기댄 설계의 전제를 확인한다."""
        every_character = "".join(chr(code) for code in range(0x80, 0x3000)) + "😀𠮷"

        self.assertNotIn(b"\n", every_character.encode("utf-8"))

    def test_scanning_is_lazy_so_an_early_break_leaves_the_rest_unread(self) -> None:
        window = b'a"K"\n' * 3
        scanned_lines = hub_subagent._lines_with_marker_backwards(window, self.MARKER, len(window))

        first = next(scanned_lines)

        self.assertEqual(window[first[0]:first[1]], b'a"K"')


class ParseResumeTitlesBytesWindowTest(unittest.TestCase):
    """bytes 창이기 때문에 생기는 입력 — 깨진 UTF-8 · 글자 한가운데서 잘린 창 머리 · 유니코드 줄 구분자 · 끝 개행."""

    def test_invalid_utf8_inside_a_candidate_line_does_not_drop_the_pair(self) -> None:
        """호스트가 append 하다 글자를 반쯤 쓴 줄 등 — 깨진 바이트는 U+FFFD 가 될 뿐 줄 구조가 온전하면 그대로 풀린다(errors="replace")."""
        request_line = _send_message_line("toolu_1", "합성 작업 이름").encode("utf-8").replace("지시 본문".encode("utf-8"), b"\xff\xfe\xc3")
        window = request_line + b"\n" + _resume_result_line("toolu_1").encode("utf-8")

        self.assertIn(b"\xff\xfe\xc3", window)   # 전제 — 깨진 바이트가 실제로 창에 들어 있다
        self.assertEqual(_titles_of(window), {AGENT_ID: "합성 작업 이름"})

    def test_invalid_utf8_inside_the_summary_survives_as_a_replacement_character(self) -> None:
        request_line = _send_message_line("toolu_1", "작업ZZ이름").encode("utf-8").replace(b"ZZ", b"\xff")
        window = request_line + b"\n" + _resume_result_line("toolu_1").encode("utf-8")

        self.assertEqual(_titles_of(window), {AGENT_ID: "작업�이름"})

    def test_window_head_cut_inside_a_multibyte_character_is_dropped_without_hiding_later_pairs(self) -> None:
        """seek 가 글자 한가운데 떨어진 첫 줄이 재개 표지를 품고 있어도(다른 에이전트의 옛 결과) 예외 없이 탈락하고, 뒤의 온전한 쌍은 풀린다."""
        old_result_line = ('{"t":"' + "가" * 6 + '","toolUseResult":{"resumedAgentId":"' + OTHER_AGENT_ID + '"}}').encode("utf-8")
        inside_first_character = len(b'{"t":"') + 1
        torn_head = old_result_line[inside_first_character:]
        window = torn_head + b"\n" + _window(_send_message_line("toolu_1"), _resume_result_line("toolu_1"))

        self.assertEqual(window[:1], "가".encode("utf-8")[1:2])   # 전제 — 창이 글자 한가운데(이어지는 바이트)에서 시작한다
        with self.assertRaises(UnicodeDecodeError):
            torn_head.decode("utf-8")                              # 전제 — 엄격한 디코딩이면 이 줄에서 터진다
        titles = _titles_of(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {AGENT_ID: "합성 작업 이름"})

    def test_window_that_ends_with_a_newline_or_not_resolves_the_same(self) -> None:
        pair = _window(_send_message_line("toolu_1"), _resume_result_line("toolu_1"))

        self.assertEqual(_titles_of(pair), _titles_of(pair + b"\n"))
        self.assertEqual(_titles_of(pair + b"\n\n\n"), {AGENT_ID: "합성 작업 이름"})

    def test_unicode_line_separators_inside_the_summary_do_not_tear_the_request_line(self) -> None:
        """U+2028 이 들어간 요약 — splitlines 로 가르면 줄이 찢겨 요청을 잃는다. 개행 바이트로만 가르므로 그대로 풀린다."""
        summary = "작업 이름 끝"
        window = _window(_send_message_line("toolu_1", summary), _resume_result_line("toolu_1"))

        self.assertEqual(_titles_of(window), {AGENT_ID: summary})

    def test_carriage_return_line_endings_still_parse(self) -> None:
        window = _window(_send_message_line("toolu_1") + "\r", _resume_result_line("toolu_1") + "\r")

        self.assertEqual(_titles_of(window), {AGENT_ID: "합성 작업 이름"})

    def test_result_passes_through_a_huge_non_marker_line_without_decoding_it(self) -> None:
        """표지 없는 큰 줄(이미지 프롬프트 등)은 디코딩하지 않는다 — 깨진 바이트로 가득해도 지나간다."""
        giant_line = b"\xff" * 200_000
        window = (
            _send_message_line("toolu_1").encode("utf-8") + b"\n" + giant_line + b"\n" + _resume_result_line("toolu_1").encode("utf-8")
        )

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {AGENT_ID: "합성 작업 이름"})
        self.assertEqual(loads_spy.call_count, 2)


class ParseResumeTitlesScanCostTest(unittest.TestCase):
    """창이 수 MiB 라 비용이 관건이다(결정 TF9) — 표지 없는 줄은 풀지 않고, 다 정해지면 더 옛 줄을 보지 않는다."""

    def test_lines_without_a_marker_are_never_decoded(self) -> None:
        unrelated_lines = [json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "합성"}]}})] * 5
        window = _window(_send_message_line("toolu_1"), _resume_result_line("toolu_1"), *unrelated_lines)

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {AGENT_ID: "합성 작업 이름"})
        self.assertEqual(loads_spy.call_count, 2)   # 결과 줄 + 요청 줄뿐 — 끝의 표지 없는 5줄은 풀지 않았다

    def test_the_scan_stops_as_soon_as_every_wanted_agent_is_settled(self) -> None:
        """더 옛 결과 줄(표지를 품은 줄)이 앞에 있어도, 찾는 에이전트가 다 정해지면 거기서 멈춰 그 줄들을 풀지 않는다."""
        older_result_line = _resume_result_line("toolu_unrelated", OTHER_AGENT_ID)
        window = _window(
            older_result_line, older_result_line,
            _send_message_line("toolu_1"), _resume_result_line("toolu_1"),
        )

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {AGENT_ID: "합성 작업 이름"})
        self.assertEqual(loads_spy.call_count, 2)   # 결과 → 요청 에서 정해져 앞의 결과 표지 줄 2개는 풀지 않았다

    def test_request_lines_older_than_the_matching_request_are_not_decoded_either(self) -> None:
        """요청 탐색도 짝을 찾으면 멈춘다 — 짝 요청보다 앞(더 옛)의 요청 표지 줄은 풀지 않는다."""
        older_request_line = _send_message_line("toolu_unrelated", "더 옛 요청", to=OTHER_AGENT_ID)
        window = _window(older_request_line, older_request_line, _send_message_line("toolu_1"), _resume_result_line("toolu_1"))

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {AGENT_ID: "합성 작업 이름"})
        self.assertEqual(loads_spy.call_count, 2)

    def test_unwanted_result_lines_are_decoded_but_their_requests_are_never_searched(self) -> None:
        """찾지 않는 에이전트의 결과 줄은 풀어 보지만(누구 것인지 알아야 한다) 그 요청 줄은 찾지도 풀지도 않는다."""
        window = _window(
            _send_message_line("toolu_other", "다른 에이전트의 작업", to=OTHER_AGENT_ID), _resume_result_line("toolu_other", OTHER_AGENT_ID),
        )

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = _titles_of(window)

        self.assertEqual(titles, {})
        self.assertEqual(loads_spy.call_count, 1)   # 결과 줄뿐 — 요청 줄은 풀지 않았다

    def test_a_quoted_mention_inside_text_does_not_pass_the_marker_filter(self) -> None:
        """본문 속 「"SendMessage"」 언급은 JSON 이스케이프(\\"SendMessage\\")라 표지(따옴표째)에 걸리지 않는다."""
        mention_line = json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": 'the "SendMessage" tool'}]}}
        )
        window = _window(_send_message_line("toolu_1"), _resume_result_line("toolu_1"), mention_line)

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            _titles_of(window)

        self.assertEqual(loads_spy.call_count, 2)


class ParseResumeTitlesContractBTest(unittest.TestCase):
    """S8 — 계약 B: 어떤 입력에도 예외를 던지지 않고, 깨진 줄은 건너뛰며 그 옆의 정상 쌍은 그대로 풀린다."""

    def test_s8_malformed_lines_are_skipped_without_hiding_a_valid_pair(self) -> None:
        marker = '"resumedAgentId" "SendMessage"'
        malformed_lines = {
            "broken_json": '{"toolUseResult": ' + marker,
            "torn_first_line": 'sage": "SendMessage"}]}}',
            "top_level_list": '["resumedAgentId"]',
            "top_level_number": "3 " + marker,
            "oversized_integer_literal": '{"n": ' + "9" * 5000 + ', "k": "SendMessage"}',
            "deeply_nested": '["SendMessage"' + "[" * 20000,
            "content_is_not_a_list": json.dumps({"message": {"content": "SendMessage"}, "toolUseResult": {"resumedAgentId": AGENT_ID}}),
            "message_is_not_an_object": json.dumps({"message": "SendMessage", "toolUseResult": {"resumedAgentId": AGENT_ID}}),
            "blocks_are_not_objects": json.dumps({"message": {"content": ["SendMessage", 3, None]}, "toolUseResult": {"resumedAgentId": AGENT_ID}}),
            "request_input_is_not_an_object": json.dumps(
                {"message": {"content": [{"type": "tool_use", "id": "toolu_x", "name": "SendMessage", "input": "x"}]}}
            ),
            "request_id_is_not_a_string": json.dumps(
                {"message": {"content": [{"type": "tool_use", "id": 7, "name": "SendMessage", "input": {"summary": "s"}}]}}
            ),
            "result_id_is_not_a_string": json.dumps(
                {"message": {"content": [{"type": "tool_result", "tool_use_id": 7}]}, "toolUseResult": {"resumedAgentId": AGENT_ID}}
            ),
            "resumed_agent_id_is_not_a_string": json.dumps(
                {"message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_y"}]}, "toolUseResult": {"resumedAgentId": 5}}
            ),
        }
        valid_pair = [_send_message_line("toolu_1"), _resume_result_line("toolu_1")]
        for label, malformed_line in malformed_lines.items():
            with self.subTest(label=label, position="newer_than_the_pair"):
                self.assertEqual(_titles_of(_window(*valid_pair, malformed_line)), {AGENT_ID: "합성 작업 이름"})
            with self.subTest(label=label, position="between_request_and_result"):
                self.assertEqual(
                    _titles_of(_window(valid_pair[0], malformed_line, valid_pair[1])), {AGENT_ID: "합성 작업 이름"}
                )
            with self.subTest(label=label, position="alone"):
                self.assertEqual(_titles_of(_window(malformed_line)), {})

    def test_empty_and_blank_windows_give_nothing(self) -> None:
        for window in (b"", b"\n\n", b"   ", b"\n"):
            with self.subTest(window=repr(window)):
                self.assertEqual(_titles_of(window), {})


class ResumeTitleContractATest(unittest.TestCase):
    """S7 — 계약 A: 재개 요약은 description 과 완전히 같은 취급(결정 TF10) — 스크럽 + SUBAGENT_TITLE_MAX_CHARS 상한."""

    def test_s7_secret_in_the_summary_is_redacted(self) -> None:
        window = _window(_send_message_line("toolu_1", "key sk-ant-AAAAAAAAAA0 포함"), _resume_result_line("toolu_1"))

        title = _titles_of(window)[AGENT_ID]

        self.assertIn("[REDACTED]", title)
        self.assertNotIn("sk-ant-AAAAAAAAAA0", title)

    def test_s7_summary_over_the_title_limit_is_clipped_with_the_truncation_mark(self) -> None:
        window = _window(_send_message_line("toolu_1", "다" * 130), _resume_result_line("toolu_1"))

        title = _titles_of(window)[AGENT_ID]

        self.assertEqual(title, "다" * (hub_subagent.SUBAGENT_TITLE_MAX_CHARS - 1) + hub_subagent.SUBAGENT_TRUNCATION_MARK)

    def test_s7_scrubbing_happens_before_clipping_not_after(self) -> None:
        """description 경로(test_scrubbing_happens_before_clipping_not_after)와 같은 판별력 설계 — 자르기를 먼저 하면 경계에 걸린
        시크릿이 패턴 최소 길이 미달로 살아남아 접두가 샌다. 산문을 상한-10 자로 유도해 상한이 바뀌어도 관계가 유지된다."""
        secret = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
        summary = ("가" * (hub_subagent.SUBAGENT_TITLE_MAX_CHARS - 10)) + secret + ("가" * 200)
        window = _window(_send_message_line("toolu_1", summary), _resume_result_line("toolu_1"))

        self.assertNotIn("sk-ant-", _titles_of(window)[AGENT_ID])

    def test_summary_is_stripped_of_surrounding_whitespace(self) -> None:
        window = _window(_send_message_line("toolu_1", "  합성 작업 이름 \n"), _resume_result_line("toolu_1"))

        self.assertEqual(_titles_of(window), {AGENT_ID: "합성 작업 이름"})

    def test_request_message_body_with_a_secret_never_reaches_the_result(self) -> None:
        """본문(message)에 시크릿이 있어도 결과에는 요약만 있다 — 본문은 아예 읽어 싣지 않는다."""
        request = json.loads(_send_message_line("toolu_1", "합성 작업 이름"))
        request["message"]["content"][0]["input"]["message"] = "token sk-ant-SECRETSECRETSECRET 본문"
        window = _window(json.dumps(request, ensure_ascii=False), _resume_result_line("toolu_1"))

        self.assertEqual(_titles_of(window), {AGENT_ID: "합성 작업 이름"})


if __name__ == "__main__":
    unittest.main()
