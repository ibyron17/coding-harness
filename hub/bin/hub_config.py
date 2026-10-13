"""hub_config.py — config.json 의 스키마와 검증 규칙(★순수).

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_config.py 대상,
tests/run.sh T25-10 이 기계적으로 강제한다). `config.json` 을 **읽는** 쪽은 여전히
hub_collect.load_config 다 — CONFIG_PATH 는 HUB_HOME 계열 상수와 함께 hub_collect.py 에
남는다. 여기 있는 것은 "이미 읽어 온 dict 를 HubConfig 로 바꾸는 규칙"뿐이다.

hub_collect.py 에서 분리했다 — main(세션 트리)과 워크플로우 가시성을 통합하며 849줄이 되어
800줄 상한(docs/prps/hub-model-module-split.md 결정 MS1)을 넘었고, 그 파일에서 유일하게
파일시스템에 닿지 않는 덩어리가 이것이었다(docs/prps/hub-collect-split-for-merge.md).
hub_usage.py(★순수 파서) / hub_usage_fetch.py(I/O), hub_workflow.py(★순수) /
hub_workflow_read.py(I/O) 가 세운 "순수 규칙 + I/O 호출자" 배치를 그대로 잇는다.

HubConfig 자체(대외 계약)는 hub_model.py 에 그대로 둔다 — 계약과 검증 규칙은 다른 것이고,
hub_model.py 는 hub_template.html 과의 계약 창구라는 자기 역할이 이미 있다.
"""

import dataclasses

import hub_model

# 필드별 기대 타입(검수 m5). bool 은 int 의 서브클래스라 int 기대 필드에 실수로 통과할 수 있지만,
# 그 정도 오탐은 사용자가 config.json 에 숫자를 불(bool)로 잘못 적는 실제 시나리오가 아니라
# 무시할 만하다 — 여기서 막는 것은 "roots" 에 문자열을 넣는 등 명백한 스키마 오류다.
_CONFIG_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "roots": (list, tuple),
    "ignore_globs": (list, tuple),
    "scan_depth": int,
    "stale_after_minutes": int,
    "event_retention_days": int,
    "record_prompt_excerpt": bool,
    "server_port": int,
    "server_heartbeat_interval_seconds": int,
    "show_usage_panel": bool,
    "show_account_info": bool,
    "usage_api_enabled": bool,
    "usage_api_poll_interval_seconds": int,
    "update_check_enabled": bool,
}


# 개정 1(rev2)에서 폐기된 키. 조용히 무시하면 마이그레이션은 필요 없지만, 사용자가 그
# 필드를 여전히 유효하다고 믿고 있을 수 있다 — 대체 필드를 안내한다(검수 m4).
_DEPRECATED_CONFIG_FIELD_GUIDANCE: dict[str, str] = {
    "serve_port_candidates": "'server_port' 로 대체됐습니다(상주 서버는 후보 순회 없이 고정 포트 하나만 씁니다)",
    "server_collect_interval_seconds": "'server_heartbeat_interval_seconds' 로 대체됐습니다(수집은 이제 요청이 이끌고, 이 값은 유지보수 티커가 하트비트를 찍는 주기입니다)",
}


# 폴링·하트비트 주기 하한(결정 AR6) — 이 값 아래로 config.json 이 설정하면 해당 데몬
# 스레드가 사실상 busy loop 가 된다. 사용량 API 폴링이 전용 스레드로 분리되며(결정 AR5)
# `stop_event.wait(주기)` 루프가 하나 더 생겨 busy-loop 표면이 1→2 로 늘었으므로, 같은
# 단계에서 하한을 강제한다.
MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS = 1
MIN_USAGE_API_POLL_INTERVAL_SECONDS = 60
_INTERVAL_FIELD_MINIMUMS: dict[str, int] = {
    "server_heartbeat_interval_seconds": MIN_SERVER_HEARTBEAT_INTERVAL_SECONDS,
    "usage_api_poll_interval_seconds": MIN_USAGE_API_POLL_INTERVAL_SECONDS,
}


def _clamp_interval_overrides(overrides: dict) -> tuple[dict, tuple[str, ...]]:
    """주기 필드가 하한 미만이면 하한으로 올리고 경고를 남긴다(결정 AR6).

    기본값(5초·300초)은 이미 하한 위이므로 override 가 없는 한 여기서 손대지 않는다 —
    clamp 은 config.json 이 하한 아래 값을 명시했을 때만 발동한다.
    """
    clamped = dict(overrides)
    warnings: list[str] = []
    for field_name, minimum in _INTERVAL_FIELD_MINIMUMS.items():
        value = clamped.get(field_name)
        if value is not None and value < minimum:
            clamped[field_name] = minimum
            warnings.append(
                f"config.json: '{field_name}' 값이 하한({minimum}초) 미만이라 {minimum}초로 조정합니다"
            )
    return clamped, tuple(warnings)


def _validate_config_overrides(raw: dict, defaults: hub_model.HubConfig) -> tuple[dict, tuple[str, ...]]:
    """raw 의 각 필드 타입을 검증해 (안전한 override, 경고 목록) 을 돌려준다.

    알 수 없는 키는 무시하되(존재해도 무해하다) 사유를 warnings 에 남긴다(검수 m4) — 조용히
    무시하면 오타나 폐기된 키(`serve_port_candidates` 등)를 사용자가 눈치챌 방법이 없다.
    """
    known_fields = {field.name for field in dataclasses.fields(defaults)}
    overrides: dict = {}
    warnings: list[str] = []
    for key, value in raw.items():
        if key not in known_fields:
            guidance = _DEPRECATED_CONFIG_FIELD_GUIDANCE.get(key, "무시합니다 — 오타인지 확인하십시오")
            warnings.append(f"config.json: 알 수 없는 필드 '{key}' — {guidance}")
            continue
        if not isinstance(value, _CONFIG_FIELD_TYPES[key]):
            warnings.append(f"config.json: '{key}' 타입이 맞지 않아 기본값을 씁니다")
            continue
        overrides[key] = tuple(value) if isinstance(value, list) else value
    return overrides, tuple(warnings)


def config_from_raw(
    raw: dict, defaults: hub_model.HubConfig
) -> tuple[hub_model.HubConfig, tuple[str, ...]]:
    """읽어 온 config.json dict 를 HubConfig 로 바꾸고 경고를 함께 돌려준다(★순수).

    타입 검증(검수 m5) → 주기 하한 clamp(결정 AR6) → dataclasses.replace 순서다.
    경고 문자열은 경로를 담지 않는다 — 경로가 붙는 경고(JSON 파싱 실패 등)는 파일을
    읽는 쪽(hub_collect.load_config)이 만든다.
    """
    overrides, type_warnings = _validate_config_overrides(raw, defaults)
    overrides, clamp_warnings = _clamp_interval_overrides(overrides)
    return dataclasses.replace(defaults, **overrides), type_warnings + clamp_warnings
