"""resume_transcript_fixtures.py — 재개 요청이 든 부모 transcript 줄의 합성 픽스처(테스트 공용, 테스트 모듈 아님).

docs/prps/hub-agent-title-and-excerpt-freshness.md §9.2 의 S·R 계열과 스냅샷 배선 테스트가 같은 줄 모양을 쓴다 — 세 곳에 복사해 두면
호스트 형식이 바뀔 때 한 곳만 고쳐 어긋난다. 줄 모양은 2.1.284 호스트의 부모 transcript 실측 그대로다(키·중첩만 — 글은 전부 합성):

- 재개 요청 = assistant 줄의 `SendMessage` tool_use (`input` 에 `to`·`summary`·`message`)
- 그 결과 = 같은 tool_use_id 의 tool_result 블록을 담은 user 줄. `toolUseResult` 는 줄 최상위에 있고, 재개였으면
  `resumedAgentId` 가 있다(실행 중인 에이전트에게 「전달」만 한 요청에는 없다)
"""

import json

AGENT_ID = "a1b2c3d4e5f6a7b8c"         # 합성 — 호스트 에이전트 ID 는 영숫자 17자
OTHER_AGENT_ID = "a9f8e7d6c5b4a3f2e"
NO_SUMMARY = object()                    # send_message_line 에서 summary 키 자체를 뺀다
DEFAULT_SUMMARY = "합성 작업 이름"


def send_message_line(request_id: str, summary: object = DEFAULT_SUMMARY, to: str = AGENT_ID) -> str:
    """부모 transcript 의 재개 요청 줄(assistant 의 SendMessage tool_use). summary 가 NO_SUMMARY 면 키를 뺀다."""
    tool_input = {"to": to, "message": "합성 지시 본문 — 제목으로 싣지 않는다", "type": "message"}
    if summary is not NO_SUMMARY:
        tool_input["summary"] = summary
    blocks = [{"type": "tool_use", "id": request_id, "name": "SendMessage", "input": tool_input}]
    payload = {"type": "assistant", "message": {"role": "assistant", "content": blocks}}
    return json.dumps(payload, ensure_ascii=False)


def resume_result_line(request_id: str, resumed_agent_id: str | None = AGENT_ID, *, block_count: int = 1) -> str:
    """같은 tool_use_id 의 결과 줄. resumed_agent_id 가 None 이면 toolUseResult 에 resumedAgentId 가 없다(「Message queued」 전달)."""
    tool_use_result = {"success": True, "message": "합성 결과 안내"}
    if resumed_agent_id is not None:
        tool_use_result["resumedAgentId"] = resumed_agent_id
    blocks = [
        {"type": "tool_result", "tool_use_id": request_id if index == 0 else f"{request_id}-{index}",
         "content": [{"type": "text", "text": "합성 결과 본문"}]}
        for index in range(block_count)
    ]
    payload = {"type": "user", "message": {"role": "user", "content": blocks}, "toolUseResult": tool_use_result}
    return json.dumps(payload, ensure_ascii=False)


def resume_pair_lines(request_id: str, summary: object = DEFAULT_SUMMARY, resumed_agent_id: str = AGENT_ID) -> list[str]:
    """재개 한 번의 요청·결과 두 줄(파일 순서 그대로)."""
    return [send_message_line(request_id, summary, to=resumed_agent_id), resume_result_line(request_id, resumed_agent_id)]
