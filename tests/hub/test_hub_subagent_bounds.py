"""hub_subagent 의 상한·비용 경계 테스트 — docs/prps/hub-agent-title-and-excerpt-freshness.md M2 검수 반영.

1. 제목 스크럽 입력 상한(SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS, 검수 MEDIUM) — 상한을 넘는 글은 제목이 아니다: 자르지도 스크럽하지도 않고 빈 제목으로
   버린다. 앞부분만 잘라 스크럽하면 창 끝에 걸린 시크릿(서명이 창 밖인 JWT · 닫는 따옴표가 창 밖인 password="…" 값 등)의 머리가 마스킹되지 않은 채
   제목 앞 120자로 나가 기준 커밋(전체 스크럽 뒤 120자)보다 마스킹이 약해졌다. description 과 재개 요약이 같은 헬퍼를 쓴다.
2. 요청 색인(검수 LOW-1) — 결과 줄마다 요청을 못 찾으면 앞의 요청 줄 전부를 매번 해석해 결과 수 × 요청 수로 느려지던 강등 경로를, 첫 미스 때 만든
   색인으로 묶는다. 시간은 재면 비결정적이라 json.loads 호출 횟수로 단언한다(스크럽·파서는 wraps 로 그대로 실행).

모든 값은 합성이다(실제 키·토큰·대화가 아니다).
"""

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
        OTHER_AGENT_ID,
        resume_result_line as _resume_result_line,
        send_message_line as _send_message_line,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from resume_transcript_fixtures import (  # noqa: E402
        AGENT_ID,
        OTHER_AGENT_ID,
        resume_result_line as _resume_result_line,
        send_message_line as _send_message_line,
    )

STARTED_AT_MS = 1_786_000_000_000
SCRUB_CAP = hub_subagent.SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS
TITLE_MAX = hub_subagent.SUBAGENT_TITLE_MAX_CHARS


def _window(*lines: str) -> bytes:
    return "\n".join(lines).encode("utf-8")


def _resume_title_of(summary: str) -> str | None:
    """재개 요약 경로 — 요청·결과 한 쌍을 창에 넣어 풀린 제목(없으면 None)."""
    window = _window(_send_message_line("toolu_1", summary), _resume_result_line("toolu_1"))
    return hub_subagent.parse_resume_titles(window, frozenset({AGENT_ID})).get(AGENT_ID)


def _description_title_of(description: str) -> str:
    """description 경로 — meta.json 을 풀어 얻은 제목(비어 있으면 "")."""
    meta_text = json.dumps({"agentType": "Explore", "description": description, "model": "haiku"})
    return hub_subagent.parse_subagent_meta(meta_text, STARTED_AT_MS).title


def _scrub_calls_while(action) -> tuple[object, list[str]]:
    """action 을 돌리며 스크럽(redact_secret_tokens)에 넘어간 글들을 모은다. 스크럽은 그대로 실행한다(wraps)."""
    with mock.patch.object(hub_subagent, "redact_secret_tokens", wraps=hub_subagent.redact_secret_tokens) as redact_spy:
        result = action()
    return result, [call.args[0] for call in redact_spy.call_args_list]


def _key_block(total_chars: int) -> str:
    """개인키 모양의 블록 — 스크럽이 한 덩어리 「[REDACTED]」 로 접어 결과를 크게 줄인다. 합성 값이라 실제 키가 아니다."""
    opening_marker = "-----BEGIN PRIVATE KEY-----"
    return opening_marker + "A" * (total_chars - len(opening_marker))


class OverCapTitleIsDroppedTest(unittest.TestCase):
    """상한(SUBAGENT_TITLE_SCRUB_INPUT_MAX_CHARS)을 넘는 제목은 스크럽 없이 빈 제목이다 — 스크럽 호출 자체가 없다(wraps 로 확인)."""

    def test_a_resume_summary_over_the_cap_is_dropped_without_any_scrub_call(self) -> None:
        huge_summary = "eyJ" * 33334   # 100,002자 — 점이 없어 스크럽의 JWT 대안이 가장 느려지는 모양

        title, scrub_inputs = _scrub_calls_while(lambda: _resume_title_of(huge_summary))

        self.assertIsNone(title)
        self.assertEqual(scrub_inputs, [])

    def test_a_description_over_the_cap_gives_an_empty_title_without_any_scrub_call(self) -> None:
        """같은 헬퍼를 쓰는 meta.json 의 description 도 같다(SUBAGENT_META_MAX_BYTES 64KiB 까지 길 수 있다)."""
        title, scrub_inputs = _scrub_calls_while(lambda: _description_title_of("eyJ" * 20000))

        self.assertEqual(title, "")
        self.assertEqual(scrub_inputs, [])

    def test_the_cap_itself_is_the_boundary_for_both_paths(self) -> None:
        """상한 이하(딱 상한 포함)는 통째로 스크럽하고 제목 상한으로 자른다 — 기준 커밋과 같다. 하나만 넘어도 버린다."""
        clipped_title = "가" * (TITLE_MAX - 1) + "…"
        paths = (("description", _description_title_of, ""), ("resume_summary", _resume_title_of, None))
        for path_label, title_of, dropped in paths:
            for length, is_dropped in ((50, False), (SCRUB_CAP - 1, False), (SCRUB_CAP, False), (SCRUB_CAP + 1, True)):
                with self.subTest(path=path_label, length=length):
                    title, scrub_inputs = _scrub_calls_while(lambda: title_of("가" * length))

                    if is_dropped:
                        self.assertEqual((title, scrub_inputs), (dropped, []))
                    else:
                        self.assertEqual([len(scrub_input) for scrub_input in scrub_inputs], [length])
                        self.assertEqual(title, "가" * length if length <= TITLE_MAX else clipped_title)

    def test_reviewer_repro_jwt_whose_signature_lies_beyond_the_cap_leaks_no_head(self) -> None:
        """검수 재현 — 서명이 상한 밖이라 앞 상한만 스크럽하면 JWT 패턴(점 둘)을 못 채워 머리가 제목 앞 120자로 나갔다."""
        jwt_header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"   # 합성 — 표준 예시 모양
        value = "메모 " + jwt_header + "." + "eyJ" + "p" * 2000 + "." + "s" * 43
        self.assertGreater(len(value), SCRUB_CAP)
        self.assertIn(jwt_header, hub_subagent.redact_secret_tokens(value[:SCRUB_CAP]))      # 전제 1 — 잘라 스크럽하면 머리가 남는다(이전 구현이 샌 경로)
        self.assertNotIn(jwt_header, hub_subagent.redact_secret_tokens(value))               # 전제 2 — 전체를 스크럽하면 마스킹된다(기준 커밋)

        self.assertEqual(_description_title_of(value), "")
        self.assertIsNone(_resume_title_of(value))

    def test_reviewer_repro_quoted_value_whose_closing_quote_lies_beyond_the_cap_leaks_no_head(self) -> None:
        """검수 재현 — 닫는 따옴표가 상한 밖이면 따옴표 값 패턴이 안 맞아 password="… 머리가 그대로 나갔다."""
        value = 'password="' + "x y " * 400 + '"'
        self.assertGreater(len(value), SCRUB_CAP)
        self.assertIn('password="x y', hub_subagent.redact_secret_tokens(value[:SCRUB_CAP]))   # 전제 1
        self.assertIn("password=[REDACTED]", hub_subagent.redact_secret_tokens(value))         # 전제 2

        self.assertEqual(_description_title_of(value), "")
        self.assertIsNone(_resume_title_of(value))

    def test_fixed_length_secret_fragment_cut_at_the_cap_leaks_nothing(self) -> None:
        """이전 구현이 「결과 < 160 이면 빈 제목」 으로만 덮던 형태(개인키 블록이 접혀 창 끝 조각이 화면에 닿는다)도 같은 규칙에 든다."""
        token = "ghp_" + "b" * 36
        tail = ": " + token[:-1]
        value = _key_block(SCRUB_CAP - len(tail)) + tail + token[-1] + " 뒷 글"
        self.assertIn(token[:-1], hub_subagent.redact_secret_tokens(value[:SCRUB_CAP]))   # 전제 — 조각이 스크럽을 그대로 통과한다

        self.assertEqual(_description_title_of(value), "")
        self.assertIsNone(_resume_title_of(value))

    def test_secret_in_the_head_of_an_over_cap_title_leaks_nothing(self) -> None:
        value = "키 sk-ant-" + "x" * 40 + " 공유 " + "가" * 100000

        self.assertEqual(_description_title_of(value), "")
        self.assertIsNone(_resume_title_of(value))

    def test_titles_within_the_cap_are_scrubbed_in_full_like_before(self) -> None:
        """상한 이하는 기준 커밋과 같다: 전체를 스크럽한 뒤 제목 상한으로 자른다 — 닫는 따옴표가 상한 안이면 값 전체가 마스킹된다."""
        secret_head = "키 sk-ant-" + "x" * 40 + " "
        cases = (
            # 딱 상한 길이 — 머리의 시크릿이 마스킹되고 120자로 잘린다(독립 계산 리터럴: 「키 [REDACTED] 」 13자 + 가 106자 + 말줄임표 = 120자)
            ("secret_at_head_exactly_cap", secret_head + "가" * (SCRUB_CAP - len(secret_head)), "키 [REDACTED] " + "가" * 106 + "…"),
            ("private_key_block_exactly_cap", _key_block(SCRUB_CAP), "[REDACTED]"),
            ("quoted_value_closed_inside_the_cap", 'password="' + "x y " * 100 + '"', "password=[REDACTED]"),
        )
        for label, value, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(_description_title_of(value), expected)
                self.assertEqual(_resume_title_of(value), expected)


def _window_with_unmatched_results(agent_count: int, other_request_count: int) -> tuple[bytes, frozenset[str]]:
    """다른 id 의 재개 요청 줄 other_request_count 개 뒤에, 짝 요청이 어디에도 없는 재개 결과 줄 agent_count 개(서로 다른 에이전트)."""
    agent_ids = [f"a{index:016d}" for index in range(agent_count)]
    lines = [_send_message_line(f"toolu_other_{index}", f"다른 요청 {index}", to=OTHER_AGENT_ID) for index in range(other_request_count)]
    lines += [_resume_result_line(f"toolu_orphan_{index}", agent_id) for index, agent_id in enumerate(agent_ids)]
    return _window(*lines), frozenset(agent_ids)


def _repeated_id_lines(arrangement: tuple[str, ...]) -> list[str]:
    """배열 표기를 transcript 줄로 — 「dup:요약」 은 tool_use id 가 toolu_dup 인 재개 요청 사본, 「result」 는 그 id 의 재개 결과."""
    return [_resume_result_line("toolu_dup") if item == "result" else _send_message_line("toolu_dup", item.removeprefix("dup:")) for item in arrangement]


class RequestIndexAfterMissTest(unittest.TestCase):
    """짝 요청을 못 찾는 결과 줄(호스트 형식이 바뀐 강등 경로)의 비용 상한 — 첫 미스 때 앞 요청 줄을 한 번만 풀어 색인을 만든다."""

    def test_unmatched_results_do_not_rescan_every_request_line_per_result(self) -> None:
        """결과 W 개 × 요청 S 줄. 색인이 없으면 결과마다 S 줄을 다시 풀어 W×S+W 번이다 — 색인이 있으면 W + 2S(첫 미스의 훑기 + 색인 구축)를 넘지 않는다."""
        result_count, request_count = 20, 50
        window, wanted = _window_with_unmatched_results(result_count, request_count)

        with mock.patch.object(hub_subagent.json, "loads", wraps=json.loads) as loads_spy:
            titles = hub_subagent.parse_resume_titles(window, wanted)

        self.assertEqual(titles, {})
        self.assertLessEqual(loads_spy.call_count, result_count + 2 * request_count)

    def test_a_request_is_found_through_the_index_after_an_earlier_miss(self) -> None:
        """파일 뒤쪽의 결과(A)가 요청을 못 찾아 색인이 만들어진 뒤, 앞쪽의 결과(B)는 색인으로 자기 요청을 찾는다."""
        window = _window(
            _send_message_line("toolu_b", "B 의 작업", to=OTHER_AGENT_ID),
            *[_send_message_line(f"toolu_other_{index}", "다른 요청", to=AGENT_ID) for index in range(5)],
            _resume_result_line("toolu_b", OTHER_AGENT_ID),
            _resume_result_line("toolu_a_without_request", AGENT_ID),
        )

        titles = hub_subagent.parse_resume_titles(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {OTHER_AGENT_ID: "B 의 작업"})

    def test_index_lookup_still_requires_the_request_to_precede_its_result(self) -> None:
        """색인은 결과 줄 뒤의 요청도 담고 있다(첫 미스의 앞 구간 전체) — 그래도 자기 결과 줄보다 뒤의 요청은 짝이 아니다(인과)."""
        window = _window(
            _resume_result_line("toolu_b", OTHER_AGENT_ID),
            _send_message_line("toolu_b", "결과 뒤의 요청", to=OTHER_AGENT_ID),
            _resume_result_line("toolu_a_without_request", AGENT_ID),
        )

        titles = hub_subagent.parse_resume_titles(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {})

    def test_the_index_answers_like_the_fast_path_even_when_a_tool_use_id_repeats(self) -> None:
        """같은 id 의 요청 사본이 여럿이면 결과 줄 앞에서 가장 가까운 사본이 짝이다 — 색인도 같은 답을 내야 한다. 실데이터에도 있다: 대화 기록 재부착이 같은 줄을
        다시 붙여 같은 tool_use id 가 2~7번 나온다(최근 90일 재개 요청 263건 중 44개 id). 색인이 파일에서 가장 뒤의 사본만 남기면, 그 사본이 자기 결과 줄보다 뒤이고
        더 앞에 짝 사본이 있을 때 색인 경로만 제목을 잃는다(M2 검수 LOW)."""
        # (배열 이름, 줄 순서 — 「dup:요약」 은 tool_use id 가 같은 요청 사본, 「result」 는 그 id 의 재개 결과, 기대 요약)
        arrangements = (
            ("copy_after_the_result", ("dup:옛 요약", "result", "dup:새 요약"), "옛 요약"),
            ("two_copies_after_the_result", ("dup:가 요약", "result", "dup:나 요약", "dup:다 요약"), "가 요약"),
            ("copies_on_both_sides_of_the_result", ("dup:가 요약", "dup:나 요약", "result", "dup:다 요약"), "나 요약"),
            ("all_copies_before_the_result", ("dup:옛 요약", "dup:새 요약", "result"), "새 요약"),
        )
        for label, arrangement, expected_summary in arrangements:
            with self.subTest(arrangement=label):
                lines = _repeated_id_lines(arrangement)

                through_fast_path = hub_subagent.parse_resume_titles(_window(*lines), frozenset({AGENT_ID}))
                through_index = hub_subagent.parse_resume_titles(   # 끝에 짝 없는 결과를 붙여 첫 미스로 색인을 만들게 한다
                    _window(*lines, _resume_result_line("toolu_orphan", OTHER_AGENT_ID)), frozenset({AGENT_ID, OTHER_AGENT_ID}),
                )

                self.assertEqual(through_fast_path, {AGENT_ID: expected_summary})
                self.assertEqual(through_index, through_fast_path)

    def test_a_request_with_an_unusable_summary_found_through_the_index_gives_no_title(self) -> None:
        """색인에서 찾은 요청의 summary 가 비어 있어도 제목 없음이다 — 더 옛 요청으로 대체하지 않는다(정상 경로와 같은 규칙)."""
        window = _window(
            _send_message_line("toolu_b_old", "B 의 옛 작업", to=OTHER_AGENT_ID),
            _resume_result_line("toolu_b_old", OTHER_AGENT_ID),
            _send_message_line("toolu_b", "", to=OTHER_AGENT_ID),
            _resume_result_line("toolu_b", OTHER_AGENT_ID),
            _resume_result_line("toolu_a_without_request", AGENT_ID),
        )

        titles = hub_subagent.parse_resume_titles(window, frozenset({AGENT_ID, OTHER_AGENT_ID}))

        self.assertEqual(titles, {})


if __name__ == "__main__":
    unittest.main()
