"""hub_workflow_read.py — 워크플로우 실행 기록(wf_<runId>.json)을 세션별로 찾아 읽는 I/O.

hub_collect.py 에서 분리했다(구현 2회차 검수 A-1) — hub_collect.py 가 800/800줄 상한에
닿아 여유가 없었다(docs/prps/hub-model-module-split.md 의 800줄 분리 선례와 같은 이유).
hub_usage.py(★순수 파서) / hub_usage_fetch.py(I/O) 가 이미 세운 "도메인 파서 + I/O 위성
모듈" 패턴을 잇는다 — 이 모듈이 hub_workflow.py(★순수 파서)의 I/O 위성이다. I/O 동사는
`fetch`(hub_usage_fetch.py, 네트워크 호출) 대신 이 저장소가 로컬 파일 읽기에 일관되게 쓰는
`read`(read_session_tail 등, hub_collect.py)를 따른다 — 이 모듈이 하는 일은 로컬
파일시스템 읽기이지 네트워크 호출이 아니기 때문이다.

hub_collect.py 는 collect_snapshot 파이프라인 **안**에서 이 모듈을 임포트해 호출한다 —
hub_usage_fetch.py 가 별도 프로세스(hub_server.py)에서만 호출돼 그 파이프라인 밖에 있던
것과 다르다. 순환 임포트를 피하기 위해 `PROJECTS_DIR` 은 이 모듈에 다시 선언하지 않고
호출자(hub_collect.py)가 자신의 `PROJECTS_DIR` 을 인자로 넘긴다 — hub_collect.py 가 이
모듈을 임포트하므로 이 모듈이 다시 hub_collect 를 임포트하면 순환이 생긴다.

파일 접근(is_dir·glob·stat·읽기)은 전부 여기서 하고, 파싱은 hub_workflow.parse_workflow_run
(★순수)에 위임한다.
"""

from pathlib import Path
from typing import Sequence

import hub_project
import hub_workflow
from hub_session_facts import SessionFacts


def _existing_workflow_directories(
    session_id: str, observed_cwds: Sequence[str], projects_dir: Path
) -> list[Path]:
    """관측된 cwd 후보 중 workflows/ 가 실제로 존재하는 것만 전부 골라 돌려준다.

    (결정 WF4 개정, 구현 2회차 검수 B-1) 1회차에는 첫 존재 후보에서 멈췄으나, 세션이
    워크트리 이동 전후로 워크플로우를 두 번 돌리면 두 디렉터리가 다 존재해 **오래된 쪽이
    이기는** 결함이 있었다("최신 1건"이라는 결정 WF5 의 목적과 정면으로 어긋난다). 존재
    여부만 여기서 걸러내고, mtime 비교는 `_latest_run_path` 가 전체 후보를 모은 뒤에 한다.
    `session_id` 는 경로 조립에 직접 쓰이므로(구현 2회차 검수 C-7) `/`·빈 문자열·`.`·`..`
    는 조립 전에 걷어낸다 — `Path` 의 `/` 연산자는 절대경로 피연산자를 만나면 앞부분을
    버리므로, 걷어내지 않으면 세션 사실의 session_id 가 임의 디렉터리를 가리키게 만들 수
    있다. `is_dir()` 은 ENOENT 는 삼키지만 EACCES 는 올린다(pathlib 실측) — 권한 없는
    디렉터리는 없는 것으로 보고 다음 cwd 로 넘어간다(검수 M7 과 같은 방어).
    """
    if "/" in session_id or session_id in ("", ".", ".."):
        return []
    directories = []
    for cwd in observed_cwds:
        workflows_dir = (
            projects_dir / hub_project.encode_project_dir_name(cwd) / session_id / hub_workflow.WORKFLOWS_DIR_NAME
        )
        try:
            if workflows_dir.is_dir():
                directories.append(workflows_dir)
        except OSError:
            continue
    return directories


def _latest_run_path(workflows_dirs: Sequence[Path]) -> Path | None:
    """여러 workflows/ 디렉터리에 흩어진 wf_*.json 후보를 합쳐 mtime 최댓값 1건을 고른다.

    (결정 WF5 확장, 구현 2회차 검수 B-1) 동률이면 파일명 역순 사전식으로 결정적으로 깬다
    (snapshot_content_key 안정성, 결정 D2). 디렉터리별 glob 실패(권한·경합 중 삭제 등)는 그
    디렉터리만 건너뛰고 나머지 후보로 계속 진행한다 — 후보 디렉터리 수는 실측상 1~2개라
    이 순회 비용은 무시할 만하다(§10).
    """
    candidates: list[tuple[float, Path]] = []
    for workflows_dir in workflows_dirs:
        try:
            candidates.extend(
                (path.stat().st_mtime, path) for path in workflows_dir.glob(hub_workflow.WORKFLOW_RUN_FILE_GLOB)
            )
        except OSError:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda entry: (entry[0], entry[1].name))[1]


def _read_run_text(run_path: Path) -> tuple[str | None, str | None]:
    """상한(WORKFLOW_RUN_MAX_BYTES) 안이면 본문을, 넘거나 읽기 실패면 (None, 경고 사유)를 돌려준다.

    (결정 WF11, 구현 2회차 검수 C-4) 1회차에는 상한 초과·OSError 모두 조용히 None 만
    돌려줘 그 세션의 칩 행이 설명 없이 사라졌다 — "워크플로우를 안 쓴 세션"과 "읽다가
    실패한 세션"을 화면에서 구별할 방법이 없었다. `read_recent_events`(검수 M7)와 같은
    형태로 사유를 warnings 에 남긴다. `errors="replace"` — GOTCHA 7 방어
    (UnicodeDecodeError 는 ValueError 서브클래스라 `except OSError` 를 뚫는다).
    """
    try:
        size = run_path.stat().st_size
        if size > hub_workflow.WORKFLOW_RUN_MAX_BYTES:
            return None, (
                f"{run_path}: 워크플로우 실행 기록이 상한"
                f"({hub_workflow.WORKFLOW_RUN_MAX_BYTES}B)을 넘어({size}B) 읽지 않습니다"
            )
        return run_path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as error:
        return None, f"{run_path}: 워크플로우 실행 기록 읽기 실패 ({error})"


def read_session_workflow(
    session_id: str, observed_cwds: Sequence[str], projects_dir: Path
) -> tuple[hub_workflow.WorkflowRunView | None, str | None]:
    """세션의 최신 워크플로우 실행 기록을 읽어 (뷰, 경고) 를 돌려준다. 절대 예외를 던지지 않는다.

    `read_session_tail`(hub_collect.py)과 같은 관용구를 잇되(결정 WF4), 이번 회차부터는
    **모든** 관측 cwd 의 workflows/ 를 훑어 전체에서 mtime 최신인 실행 1건을 고른다(위
    B-1) — "먼저 존재하는 후보에서 멈춘다"는 1회차 규칙은 디렉터리가 여럿일 때 "세션당
    최신 1건"(결정 WF5)이라는 목적과 어긋났다. 파일을 못 찾으면 (None, None), 상한 초과나
    읽기 실패면 (None, 경고)다. 파싱 실패(JSON 깨짐 등)는 경고 없이 조용히 None 이다 —
    호스트 파일 형식 자체가 불안정할 수 있다는 계약(§2)의 일부이지 이례적 실패가 아니다.
    """
    run_path = _latest_run_path(_existing_workflow_directories(session_id, observed_cwds, projects_dir))
    if run_path is None:
        return None, None
    run_text, warning = _read_run_text(run_path)
    if run_text is None:
        return None, warning
    return hub_workflow.parse_workflow_run(run_text), warning


def read_session_workflows(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    record_prompt_excerpt: bool,
    projects_dir: Path,
) -> tuple[dict[str, hub_workflow.WorkflowRunView], tuple[str, ...]]:
    """수집 대상 세션 전부의 최신 워크플로우와 경고를 모은다. 값을 못 얻은 세션은 키를 안 넣는다.

    캐시를 두지 않는다(결정 WF10, YAGNI) — `read_session_tails` 와 같은 이유로,
    `collect_snapshot` 이 50ms 를 넘기 시작하면 그때 재검토한다. `record_prompt_excerpt` 가
    거짓이면(결정 WF8) 파일을 아예 읽지 않고 빈 결과를 돌려준다 — `show_usage_panel:false`
    가 사용량 파일을 안 읽는 결정 U4 와 같은 형태.
    """
    if not record_prompt_excerpt:
        return {}, ()
    workflows: dict[str, hub_workflow.WorkflowRunView] = {}
    warnings: list[str] = []
    for sessions in sessions_by_path.values():
        for facts in sessions:
            workflow, warning = read_session_workflow(facts.session_id, facts.observed_cwds, projects_dir)
            if workflow is not None:
                workflows[facts.session_id] = workflow
            if warning is not None:
                warnings.append(warning)
    return workflows, tuple(warnings)
