"""hub_model.py — 허브 스냅샷 계약(HubSnapshot·HubConfig)과 그 직렬화·렌더(순수).

이 모듈은 파일시스템·시각·환경변수에 닿지 않는다(★순수, tests/hub/test_hub_model.py 대상).
여기 있는 것은 **대외 계약**뿐이다 — HubSnapshot 은 hub_template.html 의 #dzh-data 와,
HubConfig 는 ~/.claude/hub/config.json 과 맺은 계약이며, render_hub_html 이 전자를 HTML 에
새기는 유일한 지점이다. 계산은 hub_session·hub_project·hub_server_state·hub_usage 에 있다
(분리 근거: docs/prps/hub-model-module-split.md 결정 MS1).
"""

import json
from dataclasses import asdict, dataclass

from hub_account import AccountInfo
from hub_parse import UNSET_SOURCE_PATH, Tier1Snapshot
from hub_project import ProjectView, project_dashboard_key, tier1_file_path
from hub_release import HarnessVersionView
from hub_usage import RateLimitResets, UsageSample

_DATA_MARKER_OPEN = '<script type="application/json" id="dzh-data">'
_DATA_MARKER_CLOSE = "</script>"


# ---- 입력 ----
@dataclass(frozen=True)
class HubConfig:
    """~/.claude/hub/config.json 이 없으면 전부 이 기본값을 쓴다."""

    roots: tuple[str, ...] = ()
    ignore_globs: tuple[str, ...] = (
        "**/.claude/worktrees/**",
        "/tmp/**",
        "/private/tmp/**",
    )
    scan_depth: int = 3
    stale_after_minutes: int = 30
    event_retention_days: int = 7
    record_prompt_excerpt: bool = True
    server_port: int = 8794                        # 상주 서버 고정 포트(북마크 가능해야 한다)
    # 유지보수 티커가 하트비트를 찍는 주기. 수집 주기가 아니다(개정 2 — 수집은 요청이 이끈다).
    # server_heartbeat_ttl_ms 의 입력이기도 하다: TTL = max(이 값 × 3, 15초).
    server_heartbeat_interval_seconds: int = 5
    show_usage_panel: bool = True                  # false 면 사용량 파일을 아예 읽지 않는다(결정 U4)
    show_account_info: bool = True                 # false 면 ~/.claude.json 을 아예 읽지 않는다(결정 AC7)
    usage_api_enabled: bool = False                # 사용량 API 폴링 스위치, 기본 off(결정 A6 — 옵트인)
    usage_api_poll_interval_seconds: int = 300     # 폴링 기본 주기(5분, 결정 A3)
    update_check_enabled: bool = True              # 새 릴리스 태그 확인(git ls-remote) 스위치, 기본 on(결정 D5·UN4). false 면 스레드를 안 띄우고 캐시도 안 읽는다
    notify_enabled: bool = False                   # macOS 알림 스위치, 기본 off(결정 MN10 — 옵트인). 서버 기동 때 읽는다(바꾸면 /hub server restart)


# ---- 표시(view) ----
@dataclass(frozen=True)
class HubSnapshot:
    """허브 페이지 하나에 인라인되는 전체 데이터."""

    collected_at_ms: int
    projects: tuple[ProjectView, ...]
    unresolved_dir_names: tuple[str, ...]
    warnings: tuple[str, ...]
    usage: UsageSample | None = None    # statusLine 캡처(rate_limits.json)의 투영. 없으면 패널을 그리지 않는다(만료는 is_stale 로 표시된다)
    rate_limit_resets: RateLimitResets | None = None    # 없으면 초기화 예정 시각 줄을 그리지 않는다
    account: AccountInfo | None = None  # usage 가 있을 때만 채워진다(결정 AC2). 출처는 rate_limits.json 이 아니라 ~/.claude.json
    template_stamp: str = ""    # 이 페이지를 렌더한 hub_template.html 의 세대(결정 SH3)
    harness_version: HarnessVersionView | None = None    # 설치된 하네스 버전·새 릴리스 알림. user scope 설치 기록이 없으면 None(템플릿이 숨긴다, harness-versioning UN7)


def _register_dashboard(registry: dict[str, str], key: str | None, tier1: Tier1Snapshot | None) -> None:
    """레지스트리에 (키, 파일 경로) 한 쌍을 등록한다. 값 조립은 `tier1_file_path` 한 곳에
    위임한다(결정 ST14) — 프로젝트 항목과 세션 항목이 같은 조립 지점을 공유해 "카드에 보이는
    진행률과 클릭해서 열리는 파일이 다른 파일"이 되는 결함(T25-113)이 재발하지 않는다.

    불변식: 등록 자격이 있는 `tier1` 은 항상 hub_collect 가 `dataclasses.replace` 로
    `source_path` 를 채운 결과다(`hub_parse.UNSET_SOURCE_PATH` 로 남지 않는다, 결정 WT7·WT8).
    그 계약이 깨지면 `tier1_file_path` 가 엉뚱한 경로를 조립하므로, 키가 없거나 tier1 이
    없거나 `source_path` 가 미설정이면 등록하지 않는다(방어적 제외).
    """
    if key is None or tier1 is None or tier1.source_path == UNSET_SOURCE_PATH:
        return
    registry[key] = tier1_file_path(tier1)


def build_dashboard_registry(snapshot: HubSnapshot) -> dict[str, str]:
    """스냅샷에서 {대시보드 키: 기록(.jsonl) 절대경로} 를 만든다. 프로젝트 요약(티어 1)과 각
    세션 자신의 대시보드를 모두 담는다(결정 ST14).

    서버(hub_server.py)가 요청 경로의 키를 이 딕셔너리에서만 조회하므로, 값은 전부 이 함수가
    실제로 발견한 경로에서 나온다 — 요청 문자열이 경로 조립에 쓰이는 지점이 없다(결정 N3).
    """
    registry: dict[str, str] = {}
    for project in snapshot.projects:
        if project.tier == 1:
            _register_dashboard(registry, project_dashboard_key(project.path), project.tier1)
        for session in project.sessions:
            _register_dashboard(registry, session.dashboard_key, session.tier1)
    return registry


def snapshot_content_key(snapshot: HubSnapshot) -> str:
    """collected_at_ms 를 제외한 스냅샷 내용의 안정적 키. 같으면 hub.html 을 다시 쓰지 않는다."""
    content = asdict(snapshot)
    content.pop("collected_at_ms", None)
    return json.dumps(content, sort_keys=True, ensure_ascii=False)


# ---- 렌더링 ----
def render_hub_html(template: str, snapshot: HubSnapshot) -> str:
    """템플릿의 데이터 마커를 스냅샷 JSON 으로 치환한다. 순수 — 파일을 쓰지 않는다."""
    payload = json.dumps(asdict(snapshot), ensure_ascii=False)
    # <script type="application/json"> 내부는 raw text 다 — HTML 실체 참조(엔티티)는 브라우저가
    # 복원해 주지 않아 JSON.parse 가 그 리터럴 문자열을 그대로 반환하는 버그가 된다(검수 M1).
    # </script> 주입을 막으면서 JSON.parse 에서 원문 그대로 복원되게 하려면 JSON 자체가 정의하는
    # 유니코드 이스케이프(\uXXXX)를 써야 한다.
    escaped_payload = (
        payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )
    start = template.index(_DATA_MARKER_OPEN) + len(_DATA_MARKER_OPEN)
    end = template.index(_DATA_MARKER_CLOSE, start)
    return template[:start] + escaped_payload + template[end:]
