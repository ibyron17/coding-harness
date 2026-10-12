"""hub_workflow 단위 테스트. docs/prps/hub-workflow-visibility.md 「테스트 계획」(§11)의
test_hub_workflow.py 표 전체 — parse_workflow_run(WF2)·시크릿 스크럽(WF7)·타입 방어."""

import dataclasses
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_redact  # noqa: E402  (sys.path 조정 후 임포트)
import hub_workflow  # noqa: E402  (sys.path 조정 후 임포트)

SCRUB_CAP = hub_workflow.WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS


def _agent_item(**overrides) -> dict:
    """§2 계약대로의 최소 workflow_agent 항목. 개별 테스트가 필요한 필드만 덮어쓴다."""
    item = {
        "type": "workflow_agent", "index": 1, "label": "설계 에이전트",
        "phaseTitle": "Ground", "state": "done",
        "promptPreview": "지시 내용", "resultPreview": "결과 내용",
    }
    item.update(overrides)
    return item


def _run_json(agents: list, **overrides) -> str:
    """§2 계약대로의 최소 wf_<runId>.json 본문."""
    payload = {
        "runId": "wf_abc123", "workflowName": "sample-workflow",
        "status": "completed", "startTime": 1700000000000,
        "workflowProgress": agents,
    }
    payload.update(overrides)
    return json.dumps(payload)


def _parse_with_scrub_spy(labels: list[str]) -> tuple[hub_workflow.WorkflowRunView, list[str]]:
    """label 마다 에이전트 하나씩 실행 기록을 풀고 (뷰, 스크럽에 넘어간 글들)을 돌려준다. 스크럽은 그대로 실행한다(wraps).

    hub_workflow 는 `from hub_redact import redact_secret_tokens` 로 가져오므로 가로챌 대상은 hub_workflow 쪽 이름이다.
    """
    agents = [_agent_item(index=position, label=label) for position, label in enumerate(labels, start=1)]
    with mock.patch.object(hub_workflow, "redact_secret_tokens", wraps=hub_redact.redact_secret_tokens) as redact_spy:
        view = hub_workflow.parse_workflow_run(_run_json(agents))
    return view, [call.args[0] for call in redact_spy.call_args_list]


class ParseWorkflowRunTest(unittest.TestCase):
    """WF2 — 정상 실행 파싱, workflow_phase 항목 무시, index 정렬, state 원문 보존."""

    def test_minimal_valid_run_parses_all_fields(self) -> None:
        """run_id·workflow_name·status·started_at_ms 는 루프 밖 보완으로 제거됐다(미사용
        필드 — hub_template.html 참조 0건, docs/prps/hub-workflow-visibility.md §19).
        phase_title·prompt_preview·result_preview 3개는 워크플로우 칩 툴팁이 유일한
        소비처였는데 그 툴팁이 제거되며 함께 빠졌다(이슈 3, 결정 WT3,
        docs/prps/hub-ui-4-issues.md §4). state 는 선택 항목 E(실패 칩 시각 상태)가 남아
        유지된다."""
        view = hub_workflow.parse_workflow_run(_run_json([_agent_item()]))
        self.assertIsNotNone(view)
        self.assertEqual(len(view.agents), 1)
        agent = view.agents[0]
        self.assertEqual(agent.index, 1)
        self.assertEqual(agent.label, "설계 에이전트")
        self.assertEqual(agent.state, "done")

    def test_workflow_phase_items_are_ignored(self) -> None:
        text = _run_json([
            {"type": "workflow_phase", "index": 0, "title": "Ground"},
            _agent_item(index=1),
        ])
        view = hub_workflow.parse_workflow_run(text)
        self.assertEqual(len(view.agents), 1)
        self.assertEqual(view.agents[0].index, 1)

    def test_agents_are_sorted_by_index_ascending(self) -> None:
        text = _run_json([_agent_item(index=3), _agent_item(index=1), _agent_item(index=2)])
        view = hub_workflow.parse_workflow_run(text)
        self.assertEqual([agent.index for agent in view.agents], [1, 2, 3])

    def test_unknown_state_value_is_preserved_verbatim(self) -> None:
        """계약이 바뀔 수 있어 state 를 표로 좁히지 않는다 — 미지의 값도 그대로 통과한다."""
        view = hub_workflow.parse_workflow_run(_run_json([_agent_item(state="cancelled")]))
        self.assertEqual(view.agents[0].state, "cancelled")


class ParseWorkflowRunMalformedInputTest(unittest.TestCase):
    """방어 — 깨진 JSON·비-dict 최상위·workflowProgress 부재·agent 0개."""

    def test_broken_json_returns_none(self) -> None:
        self.assertIsNone(hub_workflow.parse_workflow_run("{"))

    def test_top_level_list_is_not_a_run(self) -> None:
        self.assertIsNone(hub_workflow.parse_workflow_run("[]"))

    def test_top_level_number_is_not_a_run(self) -> None:
        self.assertIsNone(hub_workflow.parse_workflow_run("3"))

    def test_missing_workflow_progress_still_returns_a_view_with_no_agents(self) -> None:
        payload = {"runId": "wf_x", "workflowName": "w", "status": "completed", "startTime": 1}
        view = hub_workflow.parse_workflow_run(json.dumps(payload))
        self.assertIsNotNone(view)
        self.assertEqual(view.agents, ())

    def test_phase_only_progress_yields_no_agents(self) -> None:
        view = hub_workflow.parse_workflow_run(
            _run_json([{"type": "workflow_phase", "index": 0, "title": "Ground"}])
        )
        self.assertEqual(view.agents, ())


class ViewFieldContractTest(unittest.TestCase):
    """WT3·WT4(이슈 3, docs/prps/hub-ui-4-issues.md §4) — 워크플로우 칩 툴팁 제거로
    phase_title·prompt_preview·result_preview 3개 뷰 필드가 함께 빠졌다. 선택 항목 E
    채택으로 state 는 남는다(실패 칩 시각 상태 판정)."""

    def test_agent_view_fields_are_exactly_index_label_state(self) -> None:
        self.assertEqual(
            [f.name for f in dataclasses.fields(hub_workflow.WorkflowAgentView)],
            ["index", "label", "state"],
        )

    def test_host_preview_fields_are_not_inlined(self) -> None:
        """phase_title·prompt_preview·result_preview 값이 뷰 직렬화 어디에도 등장하지
        않는지 값으로 검사한다(이름이 아니라 값을 봐야 "이름만 바꿔 다시 인라인"을 잡는다).
        state 는 선택 항목 E로 남아 인라인되므로 이 검사 대상이 아니다."""
        item = _agent_item(
            phaseTitle="제거된-단계-제목-마커",
            promptPreview="제거된-프롬프트-마커",
            resultPreview="제거된-결과-마커",
        )
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        serialized = json.dumps(dataclasses.asdict(view))
        self.assertNotIn("제거된-단계-제목-마커", serialized)
        self.assertNotIn("제거된-프롬프트-마커", serialized)
        self.assertNotIn("제거된-결과-마커", serialized)


class SecretScrubbingTest(unittest.TestCase):
    """WF7 — label 이 스크럽을 거친다(§2 — label 도 콘텐츠). phase_title·prompt_preview·
    result_preview 대상 테스트는 그 필드들이 WT3 으로 제거되며 함께 빠졌다 — label 대상
    테스트가 같은 스크럽 경로(_scrubbed_and_clipped)를 이미 검사한다."""

    def test_label_secret_is_redacted(self) -> None:
        """§2 — label 이 프롬프트 파생일 수 있어 콘텐츠다. 스크럽·표시 절단 대상이다(결정 WF7·WF9)."""
        github_token = "ghp_" + "a" * 36
        item = _agent_item(label=f"토큰 {github_token} 포함 라벨")
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertNotIn(github_token, view.agents[0].label)
        self.assertIn("[REDACTED]", view.agents[0].label)

    def test_key_value_secret_keeps_key_name(self) -> None:
        item = _agent_item(label="api_key=abcdef123456 로 설정했어")
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].label, "api_key=[REDACTED] 로 설정했어")

    def test_truncation_mark_is_preserved(self) -> None:
        """호스트가 이미 400자에서 자른 뒤 붙인 말줄임표는 그대로 보존한다 — 잘렸다는 사실이
        화면에 남아야 한다."""
        truncated = "가" * 400 + "…"
        item = _agent_item(label=truncated)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertTrue(view.agents[0].label.endswith("…"))
        self.assertEqual(len(view.agents[0].label), 401)


class ContentLengthLimitTest(unittest.TestCase):
    """구현 2회차 검수 C-1 — label·prompt_preview·result_preview 는 스크럽 뒤 401자로도
    잘린다. 검수가 promptPreview/resultPreview 각 104,000자·label 5,000자 파일로 절단 0건을
    재현했다. 지금은 label 만 남았고, 스크럽 입력 상한(WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS)을
    넘는 label 은 401자로 자르기 전에 스크럽 없이 버려진다(LabelScrubInputCapTest) — 이 클래스의
    401자 상한은 입력 상한 이하의 label 에 작동한다."""

    def test_oversized_label_is_dropped_not_clipped(self) -> None:
        """label 은 호스트가 길이를 보장하지 않아(스크립트가 준 값은 자르지 않는다, §2) 이론상 무제한일 수 있다 — 검수 재현(5,000자).
        이전에는 401자로 잘렸지만, 스크럽 입력 상한을 넘는 글은 label 이 아니라 빈 문자열로 버린다."""
        item = _agent_item(label="다" * 5000)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].label, "")

    def test_label_between_the_clip_limit_and_the_scrub_cap_is_still_clipped_to_401_chars(self) -> None:
        """입력 상한 이하는 이전과 같다 — 전체를 스크럽한 뒤 401자(400자 + 말줄임표)로 자른다."""
        label_value = "다" * (SCRUB_CAP - 200)
        self.assertGreater(len(label_value), hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS)
        view = hub_workflow.parse_workflow_run(_run_json([_agent_item(label=label_value)]))
        self.assertEqual(view.agents[0].label, "다" * 400 + "…")

    def test_scrubbing_happens_before_clipping_not_after(self) -> None:
        """순서가 바뀌면(자르기 먼저) 401자 경계 근처의 시크릿이 패턴 불일치로 살아남는다.

        재검수 2회차 수정 1 — 원래 산문 350자는 350+43(시크릿 전체 길이)=393<400 이라 애초
        경계에 걸치지조차 않았다("경계에 걸치게 하고"는 사실과 달랐다). 단언도 43자 시크릿
        전체를 찾아 접두사만 남는 유출을 못 잡았다 — 재검수자가 구현의 스크럽→자르기 순서를
        뒤집어(자르기→스크럽) 전체 스위트(739건)를 돌려도 무반응임을 실측했다. 산문 길이를
        WORKFLOW_PREVIEW_MAX_CHARS-10 으로 유도(오늘 값 391)하면 절단 후 남는 영숫자부가
        2자(400-391-7)로 줄어 SECRET_TOKEN_PATTERN 의 최소 길이({10,}) 미달이 되고, 순서가
        뒤집혔을 때 "sk-ant-" 접두사 유출이 실제로 잡힌다. 상수가 바뀌어도 경계 관계가
        자동으로 유지된다.
        """
        secret = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
        label_value = ("가" * (hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS - 10)) + secret + ("가" * 200)
        # 스크럽 입력 상한을 낮추면 이 label 이 통째로 버려져 빈 문자열이 되고 아래 단언이 공허하게 통과한다 — 그러지 않게 고정한다
        self.assertLessEqual(len(label_value), SCRUB_CAP)
        item = _agent_item(label=label_value)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertNotIn("sk-ant-", view.agents[0].label)
        self.assertEqual(len(view.agents[0].label), hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS)

    def test_exactly_401_chars_is_not_clipped(self) -> None:
        """상한과 정확히 같은 길이(호스트의 정상 출력 형태)는 손대지 않는다 — 비용 0 확인."""
        exact = ("가" * 400) + "…"
        item = _agent_item(label=exact)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].label, exact)


class LabelScrubInputCapTest(unittest.TestCase):
    """label 은 호스트가 길이를 보장하지 않고(스크립트가 준 값은 자르지 않는다, §2), 스크럽의 JWT 대안은 점 없이 `eyJ` 가 반복되는
    긴 글에서 길이의 제곱에 비례해 느려진다(hub_redact 참고 — 4MiB 파일의 label 하나가 수집을 몇 시간 멈출
    수 있었다). 그래서 WORKFLOW_LABEL_SCRUB_INPUT_MAX_CHARS 를 넘는 label 은 스크럽을 부르지 않고 빈 문자열로
    버린다 — 잘라서 스크럽하면 자른 자리에 걸린 시크릿의 머리가 마스킹되지 않기 때문이다(hub_subagent 의 제목
    경로와 같은 설계). 시간은 재면 비결정적이라 스크럽이 불린 횟수와 받은 글의 길이로 단언한다(스크럽은 wraps 로
    그대로 실행한다). 모든 값은 합성이다(실제 키·토큰이 아니다)."""

    def test_label_one_char_over_the_cap_is_dropped_without_any_scrub_call(self) -> None:
        """점이 없어 JWT 대안이 가장 느려지는 모양(eyJ 반복)으로 딱 상한 + 1자. 에이전트 칩 자체는 남는다(빈 label)."""
        over_cap_label = ("eyJ" * (SCRUB_CAP // 3 + 1))[: SCRUB_CAP + 1]
        self.assertEqual(len(over_cap_label), SCRUB_CAP + 1)

        view, scrub_inputs = _parse_with_scrub_spy([over_cap_label])

        self.assertEqual(scrub_inputs, [])
        self.assertEqual(len(view.agents), 1)
        self.assertEqual(
            (view.agents[0].index, view.agents[0].label, view.agents[0].state), (1, "", "done"),
        )

    def test_label_exactly_at_the_cap_is_scrubbed_once_in_full_then_clipped(self) -> None:
        """상한과 같은 길이는 버리지 않는다 — 통째로(상한 길이 그대로) 스크럽하고 401자로 자른다."""
        view, scrub_inputs = _parse_with_scrub_spy(["가" * SCRUB_CAP])

        self.assertEqual([len(scrub_input) for scrub_input in scrub_inputs], [SCRUB_CAP])
        self.assertEqual(view.agents[0].label, "가" * 400 + "…")
        self.assertEqual(len(view.agents[0].label), hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS)

    def test_secret_inside_an_over_cap_label_leaves_neither_the_secret_nor_the_mask(self) -> None:
        """통째로 버리므로 시크릿도 [REDACTED] 도 결과에 없다(빈 문자열)."""
        github_token = "ghp_" + "a" * 36
        view, _ = _parse_with_scrub_spy([github_token + "가" * SCRUB_CAP])

        serialized_view = json.dumps(dataclasses.asdict(view))
        self.assertEqual(view.agents[0].label, "")
        self.assertNotIn(github_token, serialized_view)
        self.assertNotIn(hub_redact.SECRET_REDACTION_MARK, serialized_view)

    def test_reviewer_repro_jwt_whose_signature_lies_beyond_the_cap_leaks_no_head(self) -> None:
        """서명이 상한 밖이라 앞 상한만 잘라 스크럽하면 JWT 패턴(점 둘)을 못 채워 머리가 label 앞쪽으로 나간다(hub_subagent 의 같은 재현)."""
        jwt_header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"   # 합성 — 표준 예시 모양
        label_value = "메모 " + jwt_header + "." + "eyJ" + "p" * 2000 + "." + "s" * 43
        self.assertGreater(len(label_value), SCRUB_CAP)
        self.assertIn(jwt_header, hub_redact.redact_secret_tokens(label_value[:SCRUB_CAP]))   # 전제 1 — 잘라 스크럽하면 머리가 남는다
        self.assertNotIn(jwt_header, hub_redact.redact_secret_tokens(label_value))            # 전제 2 — 전체를 스크럽하면 마스킹된다

        view, _ = _parse_with_scrub_spy([label_value])

        self.assertEqual(view.agents[0].label, "")

    def test_reviewer_repro_quoted_value_whose_closing_quote_lies_beyond_the_cap_leaks_no_head(self) -> None:
        """닫는 따옴표가 상한 밖이면 따옴표 값 패턴이 안 맞아 password="… 머리가 그대로 나간다(잘라 스크럽했을 때)."""
        label_value = 'password="' + "x y " * 400 + '"'
        self.assertGreater(len(label_value), SCRUB_CAP)
        self.assertIn('password="x y', hub_redact.redact_secret_tokens(label_value[:SCRUB_CAP]))   # 전제 1
        self.assertIn("password=[REDACTED]", hub_redact.redact_secret_tokens(label_value))         # 전제 2

        view, _ = _parse_with_scrub_spy([label_value])

        self.assertEqual(view.agents[0].label, "")

    def test_run_with_every_label_over_the_cap_never_calls_the_scrub(self) -> None:
        """실행당 에이전트가 최대 WORKFLOW_RUN_MAX_AGENTS 개 — 전부 상한 초과면 스크럽 호출은 0회다."""
        over_cap_labels = ["다" * (SCRUB_CAP + 1)] * hub_workflow.WORKFLOW_RUN_MAX_AGENTS

        view, scrub_inputs = _parse_with_scrub_spy(over_cap_labels)

        self.assertEqual(scrub_inputs, [])
        self.assertEqual(len(view.agents), hub_workflow.WORKFLOW_RUN_MAX_AGENTS)
        self.assertEqual({agent.label for agent in view.agents}, {""})

    def test_scrub_input_of_a_whole_run_is_bounded_by_agent_limit_times_the_cap(self) -> None:
        """에이전트가 상한(WORKFLOW_RUN_MAX_AGENTS)보다 20개 많고 전부 상한 길이여도 스크럽 호출은 상한만큼뿐이고 호출마다 받은 글은
        입력 상한 이하다 — 이 둘이 실행 하나의 총 스크럽 입력량을 에이전트 상한 × 입력 상한으로 묶는다."""
        at_cap_labels = ["가" * SCRUB_CAP] * (hub_workflow.WORKFLOW_RUN_MAX_AGENTS + 20)

        _, scrub_inputs = _parse_with_scrub_spy(at_cap_labels)

        scrub_input_lengths = [len(scrub_input) for scrub_input in scrub_inputs]
        self.assertEqual(len(scrub_input_lengths), hub_workflow.WORKFLOW_RUN_MAX_AGENTS)
        self.assertLessEqual(max(scrub_input_lengths), SCRUB_CAP)


class RecursionErrorDefenseTest(unittest.TestCase):
    """구현 2회차 검수 C-3 — 깊게 중첩된 JSON 은 RecursionError 를 던지는데
    json.JSONDecodeError 로는 안 잡힌다. 검수 재현(400KB, 중첩 200000단)과 같은 형태."""

    def test_deeply_nested_json_returns_none_without_raising(self) -> None:
        deeply_nested = "[" * 200000 + "]" * 200000
        self.assertIsNone(hub_workflow.parse_workflow_run(deeply_nested))


class MetadataFieldLimitTest(unittest.TestCase):
    """구현 3회차 계약 A — state 는 스크럽하지 않지만 WORKFLOW_METADATA_MAX_CHARS(128자)로는
    자른다. 2회차까지는 상한이 전혀 없어 100,000자가 그대로 hub.html 에 인라인됐다(검수
    3회차 재현). **루프 밖 보완**: run_id·workflow_name·status 는 미사용 필드로 제거돼
    (hub_template.html 참조 0건, §19) 이 클래스 대상은 state 하나만 남았다."""

    def test_oversized_agent_state_is_clipped_to_128_chars(self) -> None:
        item = _agent_item(state="상" * 1000)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(len(view.agents[0].state), hub_workflow.WORKFLOW_METADATA_MAX_CHARS)

    def test_metadata_field_is_not_scrubbed(self) -> None:
        """state 는 '스크럽 없이 상한만'이 설계다(모듈 docstring — 닫힌 값 집합 성격) —
        그 구분 자체를 회귀 없이 고정한다. 시크릿 형태의 값이 와도 [REDACTED] 로 바뀌지
        않는다는 것이 지금의 의도된 동작임을 명시한다."""
        secret_shaped_state = "sk-ant-abcdefghijklmnopqrstuvwxyz"
        item = _agent_item(state=secret_shaped_state)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].state, secret_shaped_state)


class BoundedIndexTest(unittest.TestCase):
    """루프 밖 보완 HIGH-A/MEDIUM-A — index 는 정수형 필드라 계약 A(문자열 상한)가 못
    덮는 채널이었다. 4,300자리 미만 정수 리터럴은 json.loads 를 통과하므로(계약 B 의
    자릿수 방어는 그 이상만 잡는다), 자릿수 폭탄이 그대로 뷰에 실려 hub.html 에 인라인될
    수 있었다 — [0, WORKFLOW_RUN_MAX_AGENTS] 범위 밖은 0 으로 접는다."""

    def test_index_far_beyond_agent_limit_is_clamped_to_zero(self) -> None:
        item = _agent_item(index=10**4000)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].index, 0)

    def test_negative_index_is_clamped_to_zero(self) -> None:
        item = _agent_item(index=-1)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].index, 0)

    def test_index_equal_to_agent_limit_is_kept(self) -> None:
        """상한과 정확히 같은 값(WORKFLOW_RUN_MAX_AGENTS)은 정상 범위로 취급한다 — 비용 0 확인."""
        item = _agent_item(index=hub_workflow.WORKFLOW_RUN_MAX_AGENTS)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].index, hub_workflow.WORKFLOW_RUN_MAX_AGENTS)

    def test_realistic_index_within_measured_range_is_unaffected(self) -> None:
        """실측 정상 범위(1~25, §3 계측 8)는 상한과 무관하게 그대로 통과한다."""
        item = _agent_item(index=25)
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertEqual(view.agents[0].index, 25)


class AgentCountLimitTest(unittest.TestCase):
    """구현 3회차 계약 A — 에이전트 수도 서버가 WORKFLOW_RUN_MAX_AGENTS 로 상한을 건다.
    클라이언트 표시 상한(MAX_VISIBLE_WORKFLOW_CHIPS, hub_template.html)은 "화면에 몇 개
    보여줄까"일 뿐 직렬화 자체를 막지 못한다(검수 3회차 재현: 에이전트 30,000개가 그대로
    파싱됐다)."""

    def test_agent_count_over_limit_is_clamped_keeping_smallest_indexes(self) -> None:
        agent_count = 30000
        agents = [_agent_item(index=index) for index in range(agent_count, 0, -1)]  # 역순
        view = hub_workflow.parse_workflow_run(_run_json(agents))
        self.assertEqual(len(view.agents), hub_workflow.WORKFLOW_RUN_MAX_AGENTS)
        self.assertEqual(
            [agent.index for agent in view.agents],
            list(range(1, hub_workflow.WORKFLOW_RUN_MAX_AGENTS + 1)),
        )


class StringFieldLengthRatchetTest(unittest.TestCase):
    """구현 3회차 계약 A 래칫 — "hub.html 에 인라인되는 모든 문자열 필드는 상한을
    경유한다"는 계약을 dataclasses.fields() 순회로 강제한다.

    **[루프 밖 보완 — 과잉 보장 서술 정정]** 이전 판은 "필드 이름을 하드코딩하지 않으므로,
    다음에 누군가 새 문자열 필드를 추가하면 상한을 걸지 않는 한 이 테스트가 자동으로
    실패한다 — 재발할 수 없는 구조다"라고 적었으나 **사실이 아니다.** 이 테스트는
    dataclasses.fields() 를 순회하지만, 병리적 값을 채우는 픽스처(_agent_item·_run_json)가
    소스 JSON 키를 하드코딩한다 — 새 필드를 추가해도 그 필드의 소스 키가 픽스처 오버라이드
    목록에 없으면 파서가 빈 문자열을 만들어 이 테스트가 **조용히 통과**한다(열거의 구멍이
    어서션에서 픽스처로 옮겨졌을 뿐이다 — 검수가 사본에 상한 없는 notes: str 필드를 추가해
    실증했다). 이 구멍은 이 테스트가 아니라 tests/run.sh 의 정적 가드(T25-166)가 막는다 —
    그 가드는 픽스처에 의존하지 않고 hub_workflow.py 의 생성자 호출부 자체를 검사해 모든
    키워드 인자가 승인된 상한 헬퍼를 거치는지 확인한다. 이 테스트는 "**기존** 필드가 실제로
    상한 안에 있는가"의 회귀 가드로는 여전히 유효하다(예: label 을 상한 없이 그대로
    돌려주게 되돌리면 정확히 실패한다) — 다만 "새 필드 누락을 자동으로 잡는다"는 보장은
    정적 가드(T25-166) 쪽의 몫이다. **이슈 3(결정 WT3, docs/prps/hub-ui-4-issues.md §4)**:
    phase_title·prompt_preview·result_preview 3개는 뷰 필드 자체가 삭제돼 오버라이드
    대상에서도 함께 빠졌다 — 남은 문자열 필드는 label 뿐이다(state 는 별도로
    MetadataFieldLimitTest 가 128자 상한을 검사한다)."""

    _MAX_ALLOWED_STRING_LENGTH = max(
        hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS, hub_workflow.WORKFLOW_METADATA_MAX_CHARS
    )

    def _assert_every_string_field_is_bounded(self, instance: object) -> None:
        for field in dataclasses.fields(instance):
            value = getattr(instance, field.name)
            if isinstance(value, str):
                self.assertLessEqual(
                    len(value),
                    self._MAX_ALLOWED_STRING_LENGTH,
                    f"{type(instance).__name__}.{field.name} 이 상한을 넘었다(길이={len(value)})",
                )

    def test_every_string_field_is_bounded_against_pathological_payload(self) -> None:
        huge_value = "가" * 100000
        item = _agent_item(label=huge_value)
        text = _run_json([item])
        view = hub_workflow.parse_workflow_run(text)
        self.assertIsNotNone(view)
        self._assert_every_string_field_is_bounded(view)
        self.assertEqual(len(view.agents), 1)
        self._assert_every_string_field_is_bounded(view.agents[0])


class ParserNeverRaisesOnPathologicalInputTest(unittest.TestCase):
    """구현 3회차 계약 B 래칫 — "파서는 어떤 입력에도 예외를 던지지 않는다"는 계약을
    병리적 입력 표로 고정한다. 2회차는 RecursionError 만 추가로 잡아, 형제 예외인
    ValueError(4,300자리를 넘는 정수 리터럴의 int 문자열 변환 자릿수 한도)가 여전히
    collect_snapshot 전체를 죽였다(검수 3회차 재현) — 예외 유형을 하나씩 추가하는
    패턴을 끊기 위해 표로 모아 한 번에 고정한다."""

    PATHOLOGICAL_INPUTS = (
        ("깨진 JSON", "{"),
        ("빈 문자열", ""),
        ("최상위 배열", "[]"),
        ("최상위 정수 스칼라", "3"),
        ("최상위 null", "null"),
        ("4,300자리를 넘는 정수 리터럴", '{"startTime": ' + "9" * 5000 + "}"),
        ("최상위 거대 문자열 스칼라(딕셔너리가 아니라 None)", '"' + "가" * 100000 + '"'),
        ("문자열 값 안의 미이스케이프 제어문자(널바이트)", '{"workflowName": "abc\x00def"}'),
        ("깊게 중첩된 배열", "[" * 200000 + "]" * 200000),
    )
    # 루프 밖 보완 HIGH-A — 고립 서로게이트(짝을 이루지 못한 \uD800~\uDFFF, 호스트가 UTF-16
    # 코드유닛 400개 경계에서 이모지 서로게이트 쌍을 쪼개면 발생)는 이 표에 넣지 않는다.
    # json.loads 는 이를 허용해 parse_workflow_run 이 **유효한 뷰**(None 이 아님)를 돌려주므로
    # 이 표의 단언(assertIsNone)과 성격이 다르다 — 파서 레벨 회귀는
    # UnpairedSurrogateHandlingTest 가, "예외 없이 값이 보존됨"을 넘어 UTF-8 로 실제 인코딩
    # 하는 쓰기 경계까지 통과하는지는 test_hub_collect.py 의 엔드투엔드 테스트가 각각 잡는다.

    def test_pathological_input_never_raises(self) -> None:
        for description, text in self.PATHOLOGICAL_INPUTS:
            with self.subTest(description=description):
                try:
                    result = hub_workflow.parse_workflow_run(text)
                except Exception as error:  # 계약 자체가 "무엇이 와도 던지지 않는다"다
                    self.fail(f"{description} 입력에서 예외 발생: {error!r}")
                self.assertIsNone(result)


class TypeDefenseTest(unittest.TestCase):
    """호스트 소유 형식이라 타입 보장이 없다 — isinstance 방어로 예외 없이 안전한 기본값을 낸다."""

    def test_non_string_label_falls_back_to_empty_string(self) -> None:
        view = hub_workflow.parse_workflow_run(_run_json([_agent_item(label=123)]))
        self.assertEqual(view.agents[0].label, "")

    def test_non_int_index_falls_back_to_zero(self) -> None:
        view = hub_workflow.parse_workflow_run(_run_json([_agent_item(index="1")]))
        self.assertEqual(view.agents[0].index, 0)


class UnpairedSurrogateHandlingTest(unittest.TestCase):
    """루프 밖 보완 HIGH-A — 고립 서로게이트가 실제로 읽히는 필드(label 등)에
    실려도 파서는 예외를 던지지 않고 그 문자를 그대로 뷰에 싣는다. json.loads·문자열
    슬라이싱·정규식 스크럽 전부 서로게이트를 다룰 수 있어(Python str 연산 자체는 문제
    없다) 이 계열의 실패는 파서가 아니라 UTF-8 로 실제 인코딩하는 쓰기 경계에서만
    일어난다 — 그래서 이 테스트는 "예외 없음 + 값이 보존됨"만 확인하고, 쓰기 실패
    회귀는 test_hub_collect.py 가 별도로 잡는다. 대상 필드는 이슈 3(결정 WT3)으로
    prompt_preview 에서 label 로 바뀌었다 — label 이 남은 유일한 자유 텍스트 필드다."""

    def test_unpaired_surrogate_in_label_is_preserved_without_raising(self) -> None:
        item = _agent_item(label="a\ud83db")
        view = hub_workflow.parse_workflow_run(_run_json([item]))
        self.assertIsNotNone(view)
        self.assertIn("\ud83d", view.agents[0].label)


if __name__ == "__main__":
    unittest.main()
