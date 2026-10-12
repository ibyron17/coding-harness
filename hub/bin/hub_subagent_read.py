"""hub_subagent_read.py — subagents/agent-<id>.meta.json 을 조립된 경로에서 찾아 읽는 I/O.

hub_workflow.py(★순수 파서) / hub_workflow_read.py(I/O) 쌍과 파일명·역할·임포트 방향이
동형이다(결정 AR2, docs/prps/hub-agent-runs-and-prompt-source.md) — hub_collect.py 가 이미
728/800줄이라 이 기능의 I/O(경로 조립·stat·읽기·세션 순회)를 더 얹을 여유가 없다.

파일 경로는 **조립**한다(결정 AR3) — `subagents/` 디렉터리를 열거(glob)하지 않는다. 허브가
아는 실행은 훅 이벤트가 준 `agent_id` 뿐이므로, 그 값으로 경로를 직접 만든다 — 읽는 파일
수가 화면에 실을 실행 수와 정확히 같아진다. 순환 임포트를 피하려고 `PROJECTS_DIR` 은 이
모듈에 다시 선언하지 않고 호출자(hub_collect.py)가 자신의 `PROJECTS_DIR` 을 인자로 넘긴다.

파일 접근(stat·읽기)은 전부 여기서 하고, 파싱은 hub_subagent.parse_subagent_meta(★순수)에
위임한다.

**결정 TF9·TF13(docs/prps/hub-agent-title-and-excerpt-freshness.md)** — 다시 불러낸(재개한) 실행이
있는 세션은 meta 에 더해 **부모 transcript**(`PROJECTS_DIR/<인코딩>/<session_id>.jsonl`) 끝을
RESUME_TITLE_SCAN_MAX_BYTES 까지 한 번 읽어, 재개 요청의 요약(`summary`)을 meta 의 `resume_title` 로
얹는다(파싱은 hub_subagent.parse_resume_titles). 재개된 실행이 없는 세션은 그 파일을 열지 않는다.
창 읽기는 hub_collect._read_transcript_tail 과 모양이 같은 작은 사본이다 — 그것을 쓰면 hub_subagent_read →
hub_collect 순환이 생긴다(위 `PROJECTS_DIR` 을 인자로 받는 이유와 같다). 다만 디코딩하지 않고 **bytes 창**을
그대로 넘긴다: 파서가 재개 표지를 품은 줄만 골라 디코딩하므로 수 MiB 창을 통째로 디코딩·줄 나누기 할 필요가
없다. 게이트(`record_prompt_excerpt`)는 meta 읽기의 조기 반환이 그대로 물려준다 — 꺼져 있으면 meta 도 창도
읽지 않는다.

**결정 LA1~LA15(docs/prps/hub-live-activity.md)** — 도는 서브에이전트 실행의 활동(안 A)과 백그라운드 작업 출력
파일(안 B)을 수집 시점에 읽는다(`read_live_activity`). 이 읽기는 `record_prompt_excerpt` 로 게이팅하지 않는다(결정
LA13, SL7 과 같은 이유 — 프롬프트 발췌가 아니다). 호스트 기록 내용을 해석하는 코드는 전부 hub_activity.py(★순수)에
있고 여기는 경로 조립·꼬리 읽기·파일 상태 보기만 한다 — 기록은 메모리 안에서 해석되고 어떤 값도 문자열로 남지 않는다.
"""

import dataclasses
import stat
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import hub_activity
import hub_project
import hub_session
import hub_subagent
from hub_session_facts import BackgroundReport, SessionFacts, SubagentFact

# 8MiB — 재개된 실행의 마지막 재개 요청을 찾으려고 부모 transcript 끝에서 읽는 최대 바이트(결정 TF9, 사용자 승인 Q2). 근거(설계 단계 실측,
# 가장 바쁜 날의 14MB 기록 · 약 1.4MB/시간): 화면에 보이는 재개 실행 4건의 요청 줄이 끝에서 0.5~2.4MB, 같은 날 재개된 6개 에이전트의 **마지막**
# 재개 요청 전부가 3.1MB 안이었다 — 8MiB 는 그 2.6배(약 5~6시간치)다. 범위보다 오래된 재개는 원래 제목(description)으로 돌아간다.
# 비용(구현 뒤 실측, 이 세션 기록 15.8MB 의 끝 8MiB, 창을 bytes 로 들고 재개 표지 줄만 디코딩): 재개된 실행이 있는 세션 하나당 읽기 0.7 + 해석
# 1.8 = 2.7ms 안팎이고, 못 찾는 id 가 있어 창 끝까지 훑는 최악도 3.4ms 안팎이다. 창 전체를 str 로 디코딩·줄 나누기 하던 첫 구현은 14ms·
# 15ms 였다. 재개된 실행이 있는 세션 3개인 실기에서 collect_snapshot 은 14ms(보강 없이) → 20ms 다(첫 구현은 50ms). 그런 세션이 여럿이라
# collect_snapshot 이 50ms 를 넘기면 (경로, 크기, mtime) 키 캐시를 재검토한다(에스컬레이션, 결정 TF9). 이 값을 바꾸면 hub/README.md 의 고지도
# 같이 바꾼다(T25-261 이 대조).
RESUME_TITLE_SCAN_MAX_BYTES = 8 * 1024 * 1024


def _is_safe_path_segment(value: str) -> bool:
    """경로 조립에 직접 쓰이는 조각이 안전한가 — `/`·빈 문자열·`.`·`..` 는 걷어낸다.

    hub_workflow_read._existing_workflow_directories 와 같은 가드다(구현 2회차 검수 C-7) —
    `Path` 의 `/` 연산자는 절대경로 피연산자를 만나면 앞부분을 버리므로, 걷어내지 않으면
    session_id·agent_id 가 임의 디렉터리를 가리키게 만들 수 있다.
    """
    return "/" not in value and value not in ("", ".", "..")


def _subagent_meta_path(session_id: str, cwd: str, agent_id: str, projects_dir: Path) -> Path:
    return (
        projects_dir
        / hub_project.encode_project_dir_name(cwd)
        / session_id
        / hub_subagent.SUBAGENT_DIR_NAME
        / f"{hub_subagent.SUBAGENT_META_FILE_PREFIX}{agent_id}{hub_subagent.SUBAGENT_META_FILE_SUFFIX}"
    )


def _read_meta_text(meta_path: Path) -> tuple[str | None, str | None]:
    """상한(SUBAGENT_META_MAX_BYTES) 안이면 본문을, 넘거나 읽기 실패면 (None, 경고 사유)를 돌려준다.

    hub_workflow_read._read_run_text 와 같은 형태 — `errors="replace"` 로 GOTCHA 7
    (UnicodeDecodeError 는 ValueError 서브클래스라 `except OSError` 를 뚫는다)을 방어한다.
    """
    try:
        size = meta_path.stat().st_size
        if size > hub_subagent.SUBAGENT_META_MAX_BYTES:
            return None, (
                f"{meta_path}: 서브에이전트 메타 기록이 상한"
                f"({hub_subagent.SUBAGENT_META_MAX_BYTES}B)을 넘어({size}B) 읽지 않습니다"
            )
        return meta_path.read_text(encoding="utf-8", errors="replace"), None
    except OSError as error:
        return None, f"{meta_path}: 서브에이전트 메타 기록 읽기 실패 ({error})"


def read_subagent_meta(
    session_id: str, observed_cwds: Sequence[str], agent_id: str, projects_dir: Path
) -> tuple[hub_subagent.SubagentMeta | None, str | None]:
    """실행 1건의 meta.json 을 읽어 (뷰, 경고) 를 돌려준다. 절대 예외를 던지지 않는다.

    경로는 조립한다(결정 AR3) — glob 하지 않는다. session_id·agent_id 는 조립 전에
    `/`·""·"."·".." 를 걷어낸다. observed_cwds 를 순서대로 시도하고 **먼저 존재하는
    것**을 쓴다(결정적, MD2·E14 와 동형). started_at_ms 는 이 층이 `stat().st_mtime` 으로
    채워 파서에 넘긴다 — 파서는 ★순수라 파일시스템에 닿을 수 없다(결정 AR1·AR2).
    """
    if not _is_safe_path_segment(session_id) or not _is_safe_path_segment(agent_id):
        return None, None
    for cwd in observed_cwds:
        meta_path = _subagent_meta_path(session_id, cwd, agent_id, projects_dir)
        try:
            if not meta_path.is_file():
                continue
            started_at_ms = int(meta_path.stat().st_mtime * 1000)
        except OSError:
            continue
        text, warning = _read_meta_text(meta_path)
        if text is None:
            return None, warning
        return hub_subagent.parse_subagent_meta(text, started_at_ms), None
    return None, None


def _subagent_transcript_path(session_id: str, cwd: str, agent_id: str, projects_dir: Path) -> Path:
    """agent-<id>.jsonl 의 조립 경로. _subagent_meta_path 와 접미사만 다르다(결정 SL1)."""
    return (
        projects_dir
        / hub_project.encode_project_dir_name(cwd)
        / session_id
        / hub_subagent.SUBAGENT_DIR_NAME
        / f"{hub_subagent.SUBAGENT_META_FILE_PREFIX}{agent_id}{hub_subagent.SUBAGENT_TRANSCRIPT_FILE_SUFFIX}"
    )


def read_subagent_activity_at_ms(
    session_id: str, observed_cwds: Sequence[str], agent_id: str, projects_dir: Path
) -> int | None:
    """실행 1건의 transcript 마지막 기록 시각(ms). 없거나 stat 실패면 None — 절대 예외를
    던지지 않는다.

    경로 조립·안전성 검사·observed_cwds 순회는 read_subagent_meta 와 같은 규칙이다(결정
    AR3 — glob 하지 않는다, `/`·""·"."·".." 를 걷어낸다, 먼저 존재하는 것을 쓴다). 파일
    내용을 읽지 않는다 — read_subagent_meta 와 달리 is_file() 없이 stat() 1회만 부른다
    (결정 SL1, §2.6 — 실행 1건당 syscall 1회로 끝난다).
    """
    if not _is_safe_path_segment(session_id) or not _is_safe_path_segment(agent_id):
        return None
    for cwd in observed_cwds:
        transcript_path = _subagent_transcript_path(session_id, cwd, agent_id, projects_dir)
        try:
            return int(transcript_path.stat().st_mtime * 1000)
        except OSError:
            continue
    return None


def read_unfinished_subagent_activity(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]], projects_dir: Path
) -> dict[str, int]:
    """미종료 실행(ended_at_ms is None)의 {agent_id: 마지막 기록 시각(ms)}.

    프롬프트 발췌 기록 여부 설정으로 게이팅되지 않는다(결정 SL7) — mtime 은 프롬프트
    발췌가 아니므로, 그 설정을 끈 사용자에게도 항상 읽는다(그 설정을 게이트로 쓰면
    설정을 끈 사용자에게만 결함이 남는다). 경고를 돌려주지 않는다(결정 SL8) — 이 경로는
    stat() 하나뿐이라 실패와 정상 부재가 구분되지 않고 결과도 같다(폴백 = 오늘의 판정).
    세션당 읽는 수는 _agent_ids_to_read 와 같은 예산(SUBAGENT_RUN_MAX_PER_SESSION)으로
    묶는다 — 종료된 실행은 그 대상에서 미리 걸러(SL3) 파일이 있어도 stat 조차 부르지
    않는다.
    """
    activity_by_agent_id: dict[str, int] = {}
    for sessions in sessions_by_path.values():
        for facts in sessions:
            unfinished = tuple(sub for sub in facts.subagents if sub.ended_at_ms is None)
            for agent_id in _agent_ids_to_read(unfinished):
                activity_ms = read_subagent_activity_at_ms(
                    facts.session_id, facts.observed_cwds, agent_id, projects_dir
                )
                if activity_ms is not None:
                    activity_by_agent_id[agent_id] = activity_ms
    return activity_by_agent_id


def _agent_ids_to_read(subagents: Sequence[SubagentFact]) -> tuple[str, ...]:
    """읽기 예산(SUBAGENT_RUN_MAX_PER_SESSION) 안에서 읽을 agent_id 를 고른다.

    화면의 최종 정렬(K2 — 실행 중 우선·최근 시작 순, hub_session.summarize_agent_runs)은
    `now_ms` 가 있어야 판정되는데 이 함수는 그 인자를 받지 않는다(§6.2 시그니처가 I/O 층을
    시각 계산에서 분리한다). `started_at_ms` 내림차순만으로도 실제로 도는 실행은 정의상
    시작한 지 얼마 안 됐으므로(좀비 기준 90분 초과) 상한 안에서는 거의 항상 함께 뽑힌다 —
    정상 부하(세션당 ≤100건, §2)에서는 이 함수가 전혀 자르지 않으므로 근사 자체가 발동하지
    않는다.
    """
    ordered = sorted(subagents, key=lambda sub: (-sub.started_at_ms, sub.agent_id))
    return tuple(sub.agent_id for sub in ordered[:hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION])


def _parent_transcript_path(session_id: str, cwd: str, projects_dir: Path) -> Path:
    """부모 transcript 의 조립 경로 — hub_collect.read_session_tail 과 같은 규칙(PROJECTS_DIR/<인코딩>/<session_id>.jsonl)."""
    return projects_dir / hub_project.encode_project_dir_name(cwd) / f"{session_id}.jsonl"


def _read_transcript_window_bytes(transcript_path: Path) -> bytes | None:
    """파일 끝 RESUME_TITLE_SCAN_MAX_BYTES 를 한 번의 seek + read 로 읽는다. 열 수 없으면 None — 예외를 던지지 않는다.

    디코딩하지 않는다 — 파서가 재개 표지를 품은 줄만 골라 그 줄만 디코딩한다(창 전체를 디코딩·줄 나누기 하면 세션당 15ms, 바이트로 들고
    표지 줄만 풀면 2.5ms: PRP §2.1 구현 측정). seek 가 멀티바이트 글자 한가운데 떨어지고 활성 세션이 동시에 append 중인 파일이라 찢긴 줄이
    있을 수 있다 — 파서가 그 줄을 디코딩 오류 없이(errors="replace", GOTCHA 7) 풀어 보고 JSON 실패로 건너뛴다.
    """
    return _read_tail_bytes(transcript_path, RESUME_TITLE_SCAN_MAX_BYTES)


def _read_tail_bytes(path: Path, max_bytes: int) -> bytes | None:
    """파일 끝 max_bytes 를 한 번의 seek + read 로 읽는다. 열 수 없으면 None — 예외를 던지지 않는다.

    창 읽기의 공통 몸통이다 — 재개 제목 창(`_read_transcript_window_bytes`)과 활동 창이 같이 쓴다. 호출자가 상수를
    인자로 넘기므로 기본값이 정의 시점에 묶이지 않는다(GOTCHA 1 — 재개 제목 테스트가 모듈 전역을 패치한다).
    """
    try:
        file_size = path.stat().st_size
        with path.open("rb") as tail_file:
            tail_file.seek(max(0, file_size - max_bytes))
            return tail_file.read()
    except OSError:
        return None


def _read_parent_transcript_window(
    session_id: str, observed_cwds: Sequence[str], projects_dir: Path
) -> bytes | None:
    """부모 transcript 끝 창의 바이트. session_id 가 안전한 경로 조각이 아니거나 읽을 후보가 없으면 None — 예외를 던지지 않는다.

    observed_cwds 를 순서대로 시도하고 **먼저 읽히는 것**을 쓴다(결정적, E14). 호스트는 워크트리 진입 때 기록을 새 cwd 폴더로 옮기는데
    (2026-09-30 실측) 후보 전부를 보는 이 규칙이 그 이전에도 맞다. 경고를 돌려주지 않는다 — 실패와 정상 부재의 결과가 같다(폴백 = 오늘의
    제목, SL8 과 같은 이유).
    """
    if not _is_safe_path_segment(session_id):
        return None
    for cwd in observed_cwds:
        window_bytes = _read_transcript_window_bytes(_parent_transcript_path(session_id, cwd, projects_dir))
        if window_bytes is not None:
            return window_bytes
    return None


def _with_resume_titles(
    facts: SessionFacts, session_metas: dict[str, hub_subagent.SubagentMeta], projects_dir: Path
) -> dict[str, hub_subagent.SubagentMeta]:
    """재개된 실행(resume_count ≥ 1)의 meta 에 부모 transcript 의 마지막 재개 요청 요약을 resume_title 로 얹은 새 dict 를 돌려준다.

    meta 를 읽은 재개 실행이 없으면 파일을 열지 않고 입력을 그대로 돌려준다(대부분의 세션 — 결정 TF9). 못 찾은 실행은 meta 가
    그대로라 화면이 description 으로 폴백한다. 입력 dict 와 meta 는 바꾸지 않는다.
    """
    wanted_agent_ids = frozenset(
        sub.agent_id for sub in facts.subagents if sub.resume_count >= 1 and sub.agent_id in session_metas
    )
    if not wanted_agent_ids:
        return session_metas
    window_bytes = _read_parent_transcript_window(facts.session_id, facts.observed_cwds, projects_dir)
    if window_bytes is None:
        return session_metas
    resume_titles = hub_subagent.parse_resume_titles(window_bytes, wanted_agent_ids)
    return {
        agent_id: dataclasses.replace(meta, resume_title=resume_titles[agent_id]) if agent_id in resume_titles else meta
        for agent_id, meta in session_metas.items()
    }


def _read_session_metas(
    facts: SessionFacts, projects_dir: Path
) -> tuple[dict[str, hub_subagent.SubagentMeta], list[str]]:
    """세션 하나의 (읽을 실행들의 meta, 경고들). 읽을 실행은 _agent_ids_to_read 의 예산 안에서 고른다."""
    metas: dict[str, hub_subagent.SubagentMeta] = {}
    warnings: list[str] = []
    for agent_id in _agent_ids_to_read(facts.subagents):
        meta, warning = read_subagent_meta(facts.session_id, facts.observed_cwds, agent_id, projects_dir)
        if meta is not None:
            metas[agent_id] = meta
        if warning is not None:
            warnings.append(warning)
    return metas, warnings


def read_subagent_metas(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    record_prompt_excerpt: bool,
    projects_dir: Path,
) -> tuple[dict[str, hub_subagent.SubagentMeta], tuple[str, ...]]:
    """수집 대상 세션의 **추적된 실행 전부**의 meta 를 {agent_id: SubagentMeta} 로 모은다.

    `record_prompt_excerpt` 가 거짓이면 파일을 아예 읽지 않고 빈 결과를 돌려준다(결정 PS7,
    read_session_workflows 와 같은 형태) — 재개 요약을 읽는 부모 transcript 창도 이 조기 반환
    뒤에 있어 같은 스위치로 꺼진다(결정 TF10). 캐시를 두지 않는다(MD4·WF10 과 같은 판단 — §2
    계측 근거). 세션당 읽는 실행 수는 hub_subagent.SUBAGENT_RUN_MAX_PER_SESSION 으로
    제한한다(정렬 후 앞에서부터) — 45건 세션이 여럿인 병리적 날에도 읽기 예산이 선형으로
    묶인다. 세션마다 읽은 meta 에 재개 요약을 얹는다(_with_resume_titles, 결정 TF13) — 재개된
    실행이 없는 세션은 부모 transcript 를 열지 않는다.
    """
    if not record_prompt_excerpt:
        return {}, ()
    metas: dict[str, hub_subagent.SubagentMeta] = {}
    warnings: list[str] = []
    for sessions in sessions_by_path.values():
        for facts in sessions:
            session_metas, session_warnings = _read_session_metas(facts, projects_dir)
            metas.update(_with_resume_titles(facts, session_metas, projects_dir))
            warnings.extend(session_warnings)
    return metas, tuple(warnings)


# ---- 실행 중 활동 읽기 (결정 LA1~LA15, docs/prps/hub-live-activity.md) ----
def _first_readable_tail(candidate_paths: Iterable[Path], max_bytes: int) -> bytes | None:
    """후보 경로들을 차례로 시도해 **먼저 읽히는 것**의 끝 max_bytes 를 돌려준다(결정적, E14). 하나도 못 읽으면 None."""
    for candidate_path in candidate_paths:
        tail = _read_tail_bytes(candidate_path, max_bytes)
        if tail is not None:
            return tail
    return None


def _read_subagent_window(
    session_id: str, observed_cwds: Sequence[str], agent_id: str, projects_dir: Path
) -> bytes | None:
    """실행 1건의 agent-<id>.jsonl 끝 ACTIVITY_WINDOW_BYTES. 경로 조각이 안전하지 않거나 읽을 후보가 없으면 None.

    session_id·agent_id 는 조립 전에 `_is_safe_path_segment` 를 통과해야 한다(결정 LA12).
    """
    if not (_is_safe_path_segment(session_id) and _is_safe_path_segment(agent_id)):
        return None
    candidate_paths = (
        _subagent_transcript_path(session_id, cwd, agent_id, projects_dir) for cwd in observed_cwds
    )
    return _first_readable_tail(candidate_paths, hub_activity.ACTIVITY_WINDOW_BYTES)


def _read_main_window(session_id: str, observed_cwds: Sequence[str], projects_dir: Path) -> bytes | None:
    """메인 기록 `<session_id>.jsonl` 끝 ACTIVITY_WINDOW_BYTES(재개 제목 창과 달리 8MiB 가 아니라 1MiB)."""
    if not _is_safe_path_segment(session_id):
        return None
    candidate_paths = (_parent_transcript_path(session_id, cwd, projects_dir) for cwd in observed_cwds)
    return _first_readable_tail(candidate_paths, hub_activity.ACTIVITY_WINDOW_BYTES)


def _running_agent_ids(
    facts: SessionFacts, now_ms: int, unfinished_activity_by_agent_id: Mapping[str, int]
) -> tuple[str, ...]:
    """지금 도는 실행의 agent_id 를 시작 시각 내림차순으로 ACTIVITY_RUNS_MAX_PER_SESSION 건까지(결정 LA2).

    화면이 `is_running` 에 쓰는 것과 같은 술어(`hub_session.is_running_subagent`)라 읽기 대상과 표시 대상이 어긋나지
    않는다. 끝난 실행·좀비는 읽지도 않는다 — 일시정지는 `ended_at_ms` 가 채워진 상태라 자동 제외되고 재개되면
    SubagentStart 가 그 값을 지워 다시 대상이 된다(P8).
    """
    running = [
        sub for sub in facts.subagents
        if hub_session.is_running_subagent(
            sub, now_ms, hub_session.SUBAGENT_ZOMBIE_AFTER_MS, unfinished_activity_by_agent_id.get(sub.agent_id)
        )
    ]
    running.sort(key=lambda sub: (-sub.started_at_ms, sub.agent_id))
    return tuple(sub.agent_id for sub in running[:hub_activity.ACTIVITY_RUNS_MAX_PER_SESSION])


def _stat_output_files(paths: Sequence[str]) -> tuple[tuple[int, int], ...]:
    """출력 파일 경로들의 (수정 시각 ms, 크기). 정규 파일만, 파일은 열지 않는다(결정 LA6).

    심볼릭 링크·디렉터리·없는 파일·상태를 못 보는 파일은 그 경로만 버린다(경고 없음, 결정 LA12). OSError 에 더해 ValueError
    도 그 경로만 버린다 — 호스트 기록 본문의 경로는 우리가 소유하지 않는 입력이라, NUL 이나 JSON 이스케이프된 외톨이
    서로게이트(UnicodeEncodeError)가 파일 시스템 호출에서 예외를 낸다. 순수 층의 NUL 거절은 첫 방어선이고 여기는 마지막이다.
    """
    file_stats = []
    for path_text in paths:
        try:
            output_status = Path(path_text).lstat()
        except (OSError, ValueError):
            continue
        if stat.S_ISREG(output_status.st_mode):
            file_stats.append((int(output_status.st_mtime * 1000), output_status.st_size))
    return tuple(file_stats)


def _activity_for_run(
    facts: SessionFacts, agent_id: str, projects_dir: Path
) -> hub_activity.SubagentActivity | None:
    """도는 실행 1건의 활동 — 꼬리 창의 도구 활동에 그 창에서 찾은 백그라운드 출력 파일 요약을 얹는다(결정 LA2·LA7)."""
    window = _read_subagent_window(facts.session_id, facts.observed_cwds, agent_id, projects_dir)
    if window is None:
        return None
    activity = hub_activity.parse_tool_activity(window)
    if activity is None:
        return None
    output_paths = hub_activity.background_output_paths(window, facts.session_id)
    output = hub_activity.summarize_background_outputs(_stat_output_files(output_paths))
    return dataclasses.replace(activity, background_output=output)


def _activities_of_session(
    facts: SessionFacts, projects_dir: Path, now_ms: int, unfinished_activity_by_agent_id: Mapping[str, int]
) -> dict[str, hub_activity.SubagentActivity]:
    """세션에서 도는 실행들의 {agent_id: 활동}. 읽지 못했거나 해석할 활동이 없는 실행은 키가 없다."""
    activity_by_agent_id = {}
    for agent_id in _running_agent_ids(facts, now_ms, unfinished_activity_by_agent_id):
        activity = _activity_for_run(facts, agent_id, projects_dir)
        if activity is not None:
            activity_by_agent_id[agent_id] = activity
    return activity_by_agent_id


def _recently_stopped_agent_ids(facts: SessionFacts, report: BackgroundReport) -> tuple[str, ...]:
    """보고 지평 안에서 멈춘 실행의 agent_id — 종료 시각 내림차순 BACKGROUND_SCAN_SUBAGENTS_MAX 건까지(결정 LA7).

    지평 = 보고 시각 − BACKGROUND_WAIT_MAX_MS. 서브에이전트가 검사를 띄우고 멈추는 전형(BW)의 띄운 줄이 여기 있다.
    """
    horizon_ms = report.reported_at_ms - hub_session.BACKGROUND_WAIT_MAX_MS
    stopped = [sub for sub in facts.subagents if sub.ended_at_ms is not None and sub.ended_at_ms >= horizon_ms]
    stopped.sort(key=lambda sub: (-sub.ended_at_ms, sub.agent_id))
    return tuple(sub.agent_id for sub in stopped[:hub_activity.BACKGROUND_SCAN_SUBAGENTS_MAX])


def _output_paths_of_windows(windows: Iterable[bytes | None], session_id: str) -> tuple[str, ...]:
    """여러 창에서 찾은 출력 경로를 이어 붙이고 중복을 없앤다(처음 나온 순서 유지)."""
    found_paths = (
        path for window in windows if window is not None
        for path in hub_activity.background_output_paths(window, session_id)
    )
    return tuple(dict.fromkeys(found_paths))


def _background_output_for_session(facts: SessionFacts, projects_dir: Path) -> hub_activity.BackgroundOutputView | None:
    """백그라운드 대기 후보 세션의 출력 요약 — 메인 기록 + 보고 지평 안에서 멈춘 실행들의 끝 창(결정 LA7).

    게이트(`is_background_output_scan_target`)는 호출자가 이미 통과시켰다. 찾은 모든 경로(메인 먼저, 그다음 최근에
    멈춘 실행 순, 중복 제거)를 lstat 해 **지금 존재하는 정규 파일** 중 앞의 BACKGROUND_OUTPUT_MAX_FILES 개를 합친다.
    """
    report = facts.background_report
    if report is None:
        return None
    windows = [_read_main_window(facts.session_id, facts.observed_cwds, projects_dir)]
    windows.extend(
        _read_subagent_window(facts.session_id, facts.observed_cwds, agent_id, projects_dir)
        for agent_id in _recently_stopped_agent_ids(facts, report)
    )
    output_paths = _output_paths_of_windows(windows, facts.session_id)
    existing_files = _stat_output_files(output_paths)[:hub_activity.BACKGROUND_OUTPUT_MAX_FILES]
    return hub_activity.summarize_background_outputs(existing_files)


def _output_of_scan_target(
    facts: SessionFacts, projects_dir: Path, now_ms: int
) -> hub_activity.BackgroundOutputView | None:
    """게이트를 통과한 세션만 출력 요약을 읽는다 — 아니면 메인 기록을 열지 않고 None."""
    if not hub_session.is_background_output_scan_target(facts, now_ms):
        return None
    return _background_output_for_session(facts, projects_dir)


def read_live_activity(
    sessions_by_path: dict[str, tuple[SessionFacts, ...]],
    projects_dir: Path,
    now_ms: int,
    unfinished_activity_by_agent_id: Mapping[str, int],
) -> hub_activity.LiveActivity:
    """도는 실행의 활동(안 A + 실행 줄 출력)과 백그라운드 대기 후보 세션의 출력 요약(안 B)을 읽는다. 예외를 던지지 않는다.

    `record_prompt_excerpt` 로 게이팅하지 않는다(결정 LA13 — 함정 SL7). 읽기 실패는 전부 "그 값 없음"이다(fail-open,
    결정 LA12) — 호스트 기록 형식이 바뀌거나 파일이 없으면 화면은 오늘과 같다.
    """
    activity_by_agent_id: dict[str, hub_activity.SubagentActivity] = {}
    output_by_session_id: dict[str, hub_activity.BackgroundOutputView] = {}
    for sessions in sessions_by_path.values():
        for facts in sessions:
            activity_by_agent_id.update(_activities_of_session(facts, projects_dir, now_ms, unfinished_activity_by_agent_id))
            output = _output_of_scan_target(facts, projects_dir, now_ms)
            if output is not None:
                output_by_session_id[facts.session_id] = output
    return hub_activity.LiveActivity(
        by_agent_id=activity_by_agent_id, background_output_by_session_id=output_by_session_id
    )
