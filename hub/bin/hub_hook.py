#!/usr/bin/env python3
"""hub_hook.py — 훅 엔트리. stdin 이벤트 1줄 append + 리텐션 정리 + 쓰로틀 재수집 spawn. 항상 exit 0.

세션을 막지 않는 것이 이 스크립트의 유일한 절대 규칙이다 — 모든 예외를 여기서 삼킨다.
훅 설치 커맨드 문자열의 `|| true`·`>/dev/null` 은 2차 방어일 뿐, 1차 방어는 이 스크립트 자신이다.

재수집(`hub.py collect`)은 이 프로세스가 직접 하지 않고 분리된 프로세스로 spawn 한다(검수 M4) —
프로젝트 수에 비례해 늘어나는 파일 읽기 비용을 훅 자신이 지면, "훅은 항상 빠르게 끝난다"는
보장이 성립하지 않는다. 훅 자신의 작업은 append + 리텐션 정리(수 ms)뿐이다.

**상주 서버가 켜져 있으면 훅은 spawn 하지 않는다**(개정 쟁점 R3) — 서버가 요청이 올 때마다
수집을 전담하므로(개정 2) 훅까지 같은 일을 하면 중복이다. 판정은 순수 함수 `should_spawn_collect` 하나로
빠져 단위 테스트가 가능하다. 서버 생존 판정은 하트비트 파일 mtime 만 본다(`stat()` 1회) —
포트 프로브·PID 조회는 훅을 지연시킬 수 있어 넣지 않는다(불변 원칙 1).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import hub_collect
import hub_model
import hub_server_state
import hub_server_state_read
import hub_session_facts
import hub_transcript

HUB_PY_PATH = Path(__file__).resolve().parent / "hub.py"
REFRESH_THROTTLE_SECONDS = 5
THROTTLE_MS = REFRESH_THROTTLE_SECONDS * 1000


def _project_fields(payload: dict) -> dict:
    """훅 페이로드에서 화면에 쓰이는 필드만 골라 짧은 키로 투영한다.

    프롬프트 발췌(`p`)는 더 이상 여기서 만들지 않는다(결정 PS4,
    docs/prps/hub-agent-runs-and-prompt-source.md) — 허브가 모델을 알아내려고 이미 읽는
    transcript 꼬리에 호스트가 같은 것(`last-prompt`)을 남기므로, 이 훅이 평문 사본을 또
    만들 이유가 없다. 카드의 발췌는 hub_transcript.parse_session_tail 이 그 꼬리에서 판다.

    `StopFailure` 는 오류 종류 하나만 `er` 로 남긴다(결정 RI7, docs/prps/
    hub-rate-limit-interruption.md) — `error_details`·`last_assistant_message` 같은 자유
    텍스트 필드는 읽지 않는다. 범용 `optional_keys` 루프에 넣지 않는 이유(GOTCHA 8)도
    같다 — 다른 훅에 같은 이름의 자유 텍스트 필드가 생겨도 이 함수가 조용히 새 필드를
    옮겨 적지 않도록, 투영 대상을 이벤트 이름으로 명시적으로 가둔다.

    `Stop`·`SubagentStop` 은 진행 중 백그라운드 작업·예약 목록을 `bt`(종류별 개수)·
    `sw`(1회성 예약 수)로만 남긴다(결정 BW2, docs/prps/hub-subagent-background-pause.md) —
    같은 이유로 범용 `optional_keys` 루프에 넣지 않는다.
    """
    fields = {
        "t": int(time.time() * 1000),
        "e": payload.get("hook_event_name", ""),
        "s": payload.get("session_id", ""),
        "c": payload.get("cwd", ""),
    }
    optional_keys = {"source": "so", "reason": "r", "agent_id": "ai", "agent_type": "at"}
    for payload_key, short_key in optional_keys.items():
        if payload.get(payload_key) is not None:
            fields[short_key] = payload[payload_key]
    if payload.get("hook_event_name") == hub_session_facts.STOP_FAILURE_EVENT_NAME:
        fields["er"] = hub_transcript.normalize_error_kind(payload.get("error"))
    if payload.get("hook_event_name") in hub_session_facts.BACKGROUND_REPORTING_EVENT_NAMES:
        fields.update(_background_fields(payload))
    return fields


def _background_fields(payload: dict) -> dict:
    """Stop·SubagentStop 의 두 배열을 bt(종류별 개수)·sw(1회성 예약 수)로만 줄인다(BW2).
    목록이 아니면 그 키를 싣지 않는다(구버전 호스트 — 페일오픈)."""
    fields: dict = {}
    background_tasks = payload.get("background_tasks")
    if isinstance(background_tasks, list):
        fields["bt"] = _task_type_counts(background_tasks)
    session_crons = payload.get("session_crons")
    if isinstance(session_crons, list):
        fields["sw"] = _one_shot_wakeup_count(session_crons)
    return fields


def _task_type_counts(tasks: list) -> dict[str, int]:
    """작업 목록 → {정규화된 종류: 개수}. 앞 SCAN_MAX 개만 분류하고 나머지·종류 상한 초과는
    unknown 으로 센다. 각 작업에서 읽는 것은 `type` 한 필드뿐이다(BW2) — `id`·`status`·
    `description`·`command` 등은 읽지 않는다."""
    counts: dict[str, int] = {}
    scanned = tasks[: hub_session_facts.BACKGROUND_TASK_SCAN_MAX]
    # 7 = BACKGROUND_TASK_KIND_MAX(8) − 1 — unknown 자리 하나를 항상 남겨 둔다. 그러지
    # 않으면 8번째 서로 다른 종류가 새 키로 더해져 총 9개가 되고(BW2 의 "unknown 포함 8개"
    # 상한을 넘는다), 병리적 입력에서 이벤트 줄이 무한히 길어질 수 있다.
    max_named_kinds = hub_session_facts.BACKGROUND_TASK_KIND_MAX - 1
    for task in scanned:
        raw_type = task.get("type") if isinstance(task, dict) else None
        normalized_type = hub_session_facts.normalize_background_task_type(raw_type)
        if normalized_type not in counts and len(counts) >= max_named_kinds:
            normalized_type = hub_session_facts.UNKNOWN_BACKGROUND_TASK_TYPE
        counts[normalized_type] = min(
            counts.get(normalized_type, 0) + 1, hub_session_facts.BACKGROUND_COUNT_MAX
        )
    overflow_count = len(tasks) - len(scanned)
    if overflow_count > 0:
        unknown = hub_session_facts.UNKNOWN_BACKGROUND_TASK_TYPE
        counts[unknown] = min(counts.get(unknown, 0) + overflow_count, hub_session_facts.BACKGROUND_COUNT_MAX)
    return counts


def _one_shot_wakeup_count(crons: list) -> int:
    """예약 목록 → recurring 이 정확히 False 인 항목 수(앞 SCAN_MAX 개만, COUNT_MAX 로
    자른다). 다른 키는 읽지 않는다(BW2) — `id`·`schedule`·`prompt` 는 읽지 않는다."""
    scanned = crons[: hub_session_facts.BACKGROUND_TASK_SCAN_MAX]
    count = sum(1 for cron in scanned if isinstance(cron, dict) and cron.get("recurring") is False)
    return min(count, hub_session_facts.BACKGROUND_COUNT_MAX)


def _append_event_line(fields: dict) -> None:
    """events/<오늘>.jsonl 에 1회 write() 로 한 줄을 append 한다(짧은 줄 = 동시 append 안전)."""
    hub_collect.EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    today = time.strftime(hub_collect.DATE_FORMAT, time.localtime())
    file_path = hub_collect.EVENTS_DIR / f"{today}.jsonl"
    line = json.dumps(fields, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(file_path, "a", encoding="utf-8") as event_file:
        event_file.write(line)


def _mtime_ms_or_none(path) -> int | None:
    try:
        return int(path.stat().st_mtime * 1000)
    except OSError:
        return None


def _should_spawn_collect_now(config: hub_model.HubConfig) -> bool:
    """`should_spawn_collect`(순수)에 지금 시각의 파일 상태를 채워 판정한다.

    서버 생존은 하트비트 mtime 만으로 판정한다(포트 프로브·PID 조회는 훅을 지연시킬 수 있어
    넣지 않는다 — 불변 원칙 1). 서버가 죽으면 TTL 이 지나며 이 훅 폴백이 자동으로 부활한다.
    """
    ttl_ms = hub_server_state.server_heartbeat_ttl_ms(config.server_heartbeat_interval_seconds)
    heartbeat_mtime_ms = _mtime_ms_or_none(hub_server_state_read.SERVER_HEARTBEAT_PATH)
    server_alive = hub_server_state.is_server_alive(int(time.time() * 1000), heartbeat_mtime_ms, ttl_ms)
    return hub_server_state.should_spawn_collect(
        now_ms=int(time.time() * 1000),
        server_alive=server_alive,
        hub_html_mtime_ms=_mtime_ms_or_none(hub_collect.HUB_HTML_PATH),
        spawn_stamp_mtime_ms=_mtime_ms_or_none(hub_collect.SPAWN_STAMP_PATH),
        throttle_ms=THROTTLE_MS,
    )


def _spawn_background_collect() -> None:
    """`hub.py collect` 를 분리된 프로세스로 띄운다 — 훅 자신은 그 결과를 기다리지 않는다.

    spawn 직전에 디바운스 스탬프를 찍어(검수 n3) 뒤따르는 훅들의 쓰로틀 판정이 곧바로
    갱신되게 한다. 이 순서(스탬프 먼저)가 중요하다 — Popen 이 실패해도 스탬프는 남아
    다음 훅이 재시도할 기회를 5초 뒤로 미루는 것이, 매 훅마다 재시도를 시도하는 것보다 낫다.
    """
    hub_collect.touch_spawn_stamp()
    try:
        subprocess.Popen(
            [sys.executable, str(HUB_PY_PATH), "collect"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


def _run() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    config, _config_warnings = hub_collect.load_config()
    _append_event_line(_project_fields(payload))
    # hub.html 이 없어도(허브 off 상태) 항상 실행돼야 "최대 N일 보관" 고지가 성립한다(검수 M5).
    hub_collect.prune_old_event_files(int(time.time() * 1000), config.event_retention_days)

    if _should_spawn_collect_now(config):
        _spawn_background_collect()


def main() -> int:
    """항상 0 을 반환한다 — 이 훅이 세션 진행을 막는 일은 원리적으로 없어야 한다."""
    try:
        _run()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
