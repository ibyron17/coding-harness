# hub/ — 허브 Python 관례 (이 저장소 전용)

`hub/` 아래 파일을 열면 Claude Code 가 이 파일을 자동으로 불러온다(하위 디렉토리 CLAUDE.md). 배포 대상이
아니다 — `hub/install.sh` 는 `hub/bin`·`hub/rules` 만 복사한다. 배포되는 범용 Python 규칙(`rules/python/`)은
「프로젝트가 이미 쓰는 것을 따른다」가 기본이고, 아래가 이 프로젝트가 쓰는 것이다(예전에 `rules/python/` 에
있던 관례를 옮겨 왔다 — docs/prps/backend-stack-support.md). 인용은 이름에 건다, 줄 번호를 쓰지 않는다.

## 의존성·버전·테스트
- 표준 라이브러리 전용 — 서드파티 import 0(루트 CLAUDE.md §2, 새 의존성 추가 금지).
- 최소 python 3.10 — `X | None` 유니온을 쓴다(`hub_server_state_read.read_server_heartbeat_mtime_ms`).
- 테스트는 stdlib `unittest` 전용(`tests/hub/test_*.py`, 실행은 루트 CLAUDE.md §4). pytest 를 들이지 않는다.

## 구조
- 순수 모듈/I·O 모듈 분리 — 순수 모듈은 머리말에 `★순수` 를 적는다. `tests/run.sh` T25-10 이 그 모듈의
  `open`·`Path`·`os` 임포트를 막는다(`hub_model.py` 머리말).
- 모듈 간 계약은 `@dataclass(frozen=True)` 로만 — 임시 dict 금지. 머리말에 어떤 dataclass 가 누구와의 계약인지
  적는다(`hub_model.HubConfig`·`HubSnapshot`, 그 밖에 `hub_parse`·`hub_session`·`hub_usage`).
- 예상된 실패는 전용 예외 — 하위 폴백이 흡수하지 않는 `OSError` 를 그대로 올리지 않는다(`hub_collect.HubCollectError`).
- 순환 임포트는 잎 모듈로 끊는다 — 어떤 허브 모듈도 임포트하지 않는 모듈(`hub_server_state.py`).
- 상수 주석은 그 값을 고른 이유를 적는다(`hub_workflow.WORKFLOW_PREVIEW_MAX_CHARS`).
- 모듈 비공개 helper 는 `_` 접두. `_clip_to_length` 는 `hub_workflow`·`hub_transcript`·`hub_subagent` 에 각자
  3줄 사본으로 둔다 — 이유는 `hub_subagent.py` 머리말.

## 훅·statusline 진입점
- 진입점 `main()` 은 항상 0 을 반환한다 — 최상위에서만 `except Exception` 으로 삼키고 helper 안에서는 삼키지
  않는다(`hub_hook.main`·`hub_statusline.main`). 관찰용 훅이 세션 진행을 막으면 안 되기 때문이다.
- 진입점 자체는 밀리초 단위(append + 가벼운 장부)로 끝내고 무거운 일은 분리된 하위 프로세스로 넘긴다
  (`hub_hook.py` 머리말).

## 보안
- 프롬프트 등 자유 텍스트를 기록하면 설치 고지에 상한·보관 기간·끄는 법을 적고(`commands/hub.md` 훅 설치
  고지), 쓰기 전에 `hub_redact.redact_secret_tokens` 로 토큰 모양 값을 가린다.
- subprocess 는 argv 리스트, 셸 문자열 금지(`hub_usage_fetch.py` 의 키체인 조회 호출).
- 요청 문자열로 파일 경로를 만들지 않는다 — 고정 형식 토큰만 뽑아 화이트리스트의 조회 키로 쓴다
  (`hub_server.ALLOWED_REQUEST_PATHS`·`PROJECT_DASHBOARD_PATH_PATTERN`).
- 자격 증명·토큰은 모듈 전역 변수에 두지 않고 쓰는 함수의 지역 변수로 둔다.

## 테스트 관례
- 모듈 상태를 건드리는 테스트는 `setUp` 에서 모듈 상수를 바꿔 끼우고 `tearDown` 에서 되돌린다 — 모듈을 통째로
  mock 하지 않는다(`test_hub_hook.HubHookScenarioTest`).
- 특정 함수 교체는 `mock.patch.object`, 점 경로(`subprocess.Popen`·`sys.stdin`)는 `mock.patch`
  (`test_hub_hook.SpawnsBackgroundCollectTest`).
- 구조는 AAA.
