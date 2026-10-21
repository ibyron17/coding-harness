#!/usr/bin/env python3
"""hub_handback_guard.py — 서브에이전트 보고 게이트(PreToolUse · SubagentHandback). 항상 exit 0.

**허브가 등록하지 않는다** — 배포 에이전트(implementer·code-reviewer·design-architect)의 frontmatter hooks 가 부른다.
이 실행이 띄운 백그라운드 작업이 살아 있고 보고에 선언되지 않았으면 보고를 거부한다. 프로세스를 끄지 않는다 — 끄는 일은
거부 사유를 받은 서브에이전트가 TaskStop 으로 한다. 무엇이든 실패하면 허용한다(fail-open).

판정(결정 BG-G1): 「이 서브에이전트 기록의 호스트 시작 문장에서 찾은 작업」 ∩ 「지금 그 출력 파일을 쥔 프로세스가 있는 작업」
− 「보고 본문에 ID 가 적힌 작업」 이 비어 있지 않으면 거부한다. 소유 문장 해석은 hub_activity.host_background_launches 가 한다.
보고 시점에 PreToolUse 입력에는 소유자를 가리는 배열이 없어 기록 문장이 유일한 소유 근거다.

정본: docs/prps/background-task-orphans.md. 이 모듈은 문서화된 대로 파일시스템·subprocess 에 닿는 I/O 층이라 ★순수 모듈이 아니다 —
순수 판정은 위 함수들로 분리돼 단위 테스트(tests/hub/test_hub_handback_guard.py)가 본다.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Sequence

import hub_activity

GUARDED_EVENT_NAME = "PreToolUse"
GUARDED_TOOL_NAME = "SubagentHandback"
LSOF_TIMEOUT_SECONDS = 3                          # 훅 timeout(10) 안에서 기록 읽기와 나눠 쓴다
SUBAGENT_TRANSCRIPT_MAX_BYTES = 16 * 1024 * 1024  # 초과분은 끝에서부터 이만큼만 읽는다

_AGENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")   # 경로 조각이 되므로 디렉터리를 벗어나지 못하게 가둔다
_MAIN_TRANSCRIPT_SUFFIX = ".jsonl"
_DENY_REASON_TEMPLATE = (
    "보고 전에 정리할 것: 이 실행이 띄운 백그라운드 작업 {task_ids}이 아직 돈다(출력 파일 {output_paths}). "
    "결과가 필요 없으면 TaskStop 으로 끈 뒤 다시 보고한다(TaskStop 이 없으면 Bash 로 kill $(lsof -t <출력 파일>)). "
    "TaskStop 이 이미 끝난 작업이라고 하면 보고 본문에 그 ID 를 적어 다시 보고한다. "
    "결과를 기다려야 하면 보고하지 말고 턴을 끝내 완료 알림을 기다린다. "
    "일부러 남겨 메인에 넘길 것이면 보고 본문에 그 ID 와 이유를 적고 다시 보고한다."
)


@dataclass(frozen=True)
class GuardInput:
    """훅 stdin 에서 검증해 뽑은 값."""

    session_id: str
    agent_id: str
    transcript_path: str
    report_message: str


def _non_empty_string(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def parse_guard_input(raw: str) -> GuardInput | None:
    """훅 stdin 원문에서 게이트에 필요한 값을 뽑는다. 다른 이벤트·도구, 필수 키 없음, JSON 이 아님이면 None."""
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("hook_event_name") != GUARDED_EVENT_NAME or payload.get("tool_name") != GUARDED_TOOL_NAME:
        return None
    session_id = _non_empty_string(payload, "session_id")
    agent_id = _non_empty_string(payload, "agent_id")
    transcript_path = _non_empty_string(payload, "transcript_path")
    tool_input = payload.get("tool_input")
    report_message = tool_input.get("message") if isinstance(tool_input, dict) else None
    if None in (session_id, agent_id, transcript_path) or not isinstance(report_message, str):
        return None
    if not _AGENT_ID_PATTERN.fullmatch(agent_id):
        return None
    return GuardInput(session_id, agent_id, transcript_path, report_message)


def subagent_transcript_path(transcript_path: str, agent_id: str) -> Path:
    """메인 세션 기록 경로에서 서브에이전트 기록 경로를 만든다 — `<.jsonl 을 뗀 경로>/subagents/agent-<id>.jsonl`(실측 2.1.304)."""
    session_directory = transcript_path.removesuffix(_MAIN_TRANSCRIPT_SUFFIX)
    return Path(session_directory) / "subagents" / f"agent-{agent_id}.jsonl"


def parse_lsof_open_names(lsof_output: str) -> frozenset[str]:
    """`lsof -Fn` 출력에서 파일 이름 줄(n 로 시작)의 값을 모은다. p(프로세스)·f(기술자) 줄은 버린다."""
    return frozenset(line[1:] for line in lsof_output.splitlines() if line.startswith("n") and len(line) > 1)


def _report_declares(report_message: str, task_id: str) -> bool:
    """보고 본문에 task_id 가 독립된 낱말로 적혀 있는지 — 다른 낱말의 일부는 선언이 아니다."""
    return re.search(r"(?<![\w-])" + re.escape(task_id) + r"(?![\w-])", report_message) is not None


def undeclared_live_launches(
    launches: Sequence[hub_activity.BackgroundLaunch],
    open_paths: Collection[str],
    report_message: str,
) -> tuple[hub_activity.BackgroundLaunch, ...]:
    """시작 문장이 있는 작업 중 출력 파일이 지금 열려 있고(open_paths) 보고에 ID 가 적히지 않은 것만 돌려준다."""
    return tuple(
        launch for launch in launches
        if launch.output_path in open_paths and not _report_declares(report_message, launch.task_id)
    )


def deny_decision(launches: Sequence[hub_activity.BackgroundLaunch]) -> dict:
    """보고를 막는 PreToolUse 결정(hookSpecificOutput JSON 로 직렬화될 dict). 사유에 작업 ID·출력 파일·세 출구를 싣는다."""
    reason = _DENY_REASON_TEMPLATE.format(
        task_ids=", ".join(launch.task_id for launch in launches),
        output_paths=", ".join(launch.output_path for launch in launches),
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": GUARDED_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _read_transcript_tail(transcript_file: Path) -> bytes | None:
    """서브에이전트 기록의 끝 SUBAGENT_TRANSCRIPT_MAX_BYTES 까지를 읽는다. 파일이 없거나 못 읽으면 None."""
    try:
        with open(transcript_file, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - SUBAGENT_TRANSCRIPT_MAX_BYTES))
            return handle.read()
    except OSError:
        return None


def _open_output_paths(paths: Sequence[str]) -> frozenset[str]:
    """paths 중 지금 어떤 프로세스가 열어 둔 파일을 돌려준다(요청한 경로 문자열 그대로).

    lsof 가 없거나 시간 초과·실행 실패면 아무것도 열려 있지 않은 것으로 본다(fail-open, BG-G3). lsof 는 /tmp 를 /private/tmp
    로 풀어 적으므로 realpath 로 맞춰 비교한다.
    """
    if not paths:
        return frozenset()
    try:
        completed = subprocess.run(
            ["lsof", "-Fn", "--", *paths],
            capture_output=True, text=True, timeout=LSOF_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    open_names = {os.path.realpath(name) for name in parse_lsof_open_names(completed.stdout)}
    return frozenset(path for path in paths if os.path.realpath(path) in open_names)


def _run() -> None:
    guard_input = parse_guard_input(sys.stdin.read())
    if guard_input is None:
        return
    window = _read_transcript_tail(subagent_transcript_path(guard_input.transcript_path, guard_input.agent_id))
    if window is None:
        return
    launches = hub_activity.host_background_launches(window, guard_input.session_id)
    open_paths = _open_output_paths([launch.output_path for launch in launches])
    stray_launches = undeclared_live_launches(launches, open_paths, guard_input.report_message)
    if stray_launches:
        print(json.dumps(deny_decision(stray_launches)))


def main() -> int:
    """항상 0 을 반환한다 — 이 게이트가 보고를 영영 막는 것은 고아가 남는 것보다 나쁘다(결정 BG-G3)."""
    try:
        _run()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
