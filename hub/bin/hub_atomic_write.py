"""hub_atomic_write.py — 텍스트 파일 원자적 교체 + UTF-8 인코딩 안전 정규화.

허브의 모든 파일 쓰기가 지나는 단 하나의 관문이다 — hub.html · rate_limits.json ·
last_collect_error.json · last_usage_api_error.json · server.json 이 전부 여기를 지난다.
도메인을 모른다: 무엇을 쓰는지가 아니라 "어떻게 안전하게 바꿔치는지"만 안다.

★순수가 아니다 — tempfile·os.fdopen 을 쓴다. tests/run.sh T25-10 의 순수 파일 목록에
넣지 말 것.

hub_collect.py 에서 분리했다(docs/prps/hub-collect-split-for-merge.md). 849줄이 된 그
파일에서, 선언된 책임("프로젝트 발견 · 3티어 읽기 · 스냅샷 조립 · hub.html 원자적 쓰기")
중 마지막 항목의 **기반 기계**만 떼어낸 것이다. 어떤 허브 모듈도 임포트하지 않는 잎이라
(hub_server_state.py 와 같은 계약) 순환이 구조적으로 불가능하다 — 반대로 이 모듈이
hub_collect.HUB_HOME 같은 상수를 참조하기 시작하면 임포트 순서에 따라 터지는 순환이 된다.
"""

import os
import re
import tempfile
from pathlib import Path

_LONE_SURROGATE_PATTERN = re.compile(r"[\ud800-\udfff]")
# U+FFFD REPLACEMENT CHARACTER. 리터럴 문자로 박지 않고 이스케이프 표기로 두는 이유: 인코딩
# 안전을 다루는 코드에서 그 안전장치의 핵심 문자가 소스 파일 인코딩 손상에 취약한 표기로
# 들어가면 안 되고, 리터럴 U+FFFD 는 화면에서 모지바케와 구별되지 않아 오인된다(검수 M1).
# 이름 있는 상수로 두는 것은 hub_workflow.WORKFLOW_PREVIEW_TRUNCATION_MARK 와 같은 관례다.
_LONE_SURROGATE_REPLACEMENT = "\ufffd"


def encode_safe_utf8(text: str) -> str:
    """text 에서 UTF-8 로 인코딩 불가능한 고립 서로게이트를 U+FFFD(REPLACEMENT CHARACTER)로
    치환한다.

    공개 함수다(재검수 2회차 RA2 — 이 파일 안의 원자적 쓰기 경계뿐 아니라 hub_server.py 의
    세션별 진행 기록 렌더 응답(HTTP 인코딩 경계, 파일 쓰기가 아니라 직접 `str.encode`)도
    같은 정규화를 그대로 재사용한다. 그 응답 경로는 이 파일을 거치지 않아 아래 정규화 없이는
    같은 실패를 반복한다).

    루프 밖 보완(HIGH-A) — text 는 호스트 소유 페이로드(예: wf_*.json 의 promptPreview)에서
    파생된 문자열을 담을 수 있다. 호스트가 UTF-16 코드유닛 400개 경계에서 이모지 서로게이트
    쌍을 쪼개면(재현: {"promptPreview": "a\\ud83db"}), 그 결과 문자열은 유효한 Python str
    이지만 UTF-8 로 인코딩할 수 없다("surrogates not allowed") — json.loads·문자열 슬라이싱·
    정규식 스크럽은 전부 서로게이트를 그대로 통과시키므로 이 함수를 거치기 전까지는 아무
    단계도 실패하지 않는다. 이 정규화가 없으면 그 wf 파일이 세션 mtime 최신인 동안 매 수집
    사이클마다 hub.html 쓰기 자체가 실패한다.

    ASCII '?' 대신 U+FFFD 를 쓰는 이유: '?' 는 사용자가 실제로 입력한 물음표와 화면에서
    구별되지 않는다. U+FFFD 는 hub_template.html 이 서로게이트 절단(다른 경로에서 오는 같은
    계열 결함)을 표시할 때 이미 쓰는 문자이기도 하다. 왕복 인코딩 대신 정규식 치환으로 바꾼
    근거(실측): Python str 에서 UTF-8 인코딩이 실패하는 코드포인트는 서로게이트 범위
    (U+D800~U+DFFF, 2048개) 뿐이다 — 0 부터 0x10FFFF 까지 전체 코드포인트를 encode("utf-8")
    해 확인했고, 논캐릭터(U+FFFE·U+FFFF 등)는 실패 집합에 없었다. 이 범위만 U+FFFD 로
    치환하면 이전의 왕복(encode("utf-8", "replace").decode("utf-8"))과 동등한 결과를 내면서
    바이트 왕복이 없는 순수한 문자열→문자열 변환이 되고, 치환 후 문자열은 항상
    encode("utf-8") 에 성공한다(치환 대상이 전부 사라지므로).

    이 기능이 만든 결함이 아니다 — 이 쓰기 경계는 처음부터 호스트·사용자 소유 문자열을
    그대로 인코딩해 왔다(훅의 프롬프트 발췌 채널도 같은 노출면을 가진다). 워크플로우 인라인이
    그 표면을 넓혔을 뿐이므로, 파서(hub_workflow.py) 대신 이 공용 쓰기 경계에서 막는다 —
    이 함수 하나가 hub.html 뿐 아니라 이 모듈이 쓰는 모든 파일(rate_limits.json 등)의 호스트
    소유 문자열을 함께 방어하고, 앞으로 새 채널이 추가돼도 자동으로 적용된다.
    """
    return _LONE_SURROGATE_PATTERN.sub(_LONE_SURROGATE_REPLACEMENT, text)


def atomic_write_text(final_path: Path, directory: Path, prefix: str, text: str) -> None:
    """directory 안에 고유한 임시 파일을 만들어 text 를 쓰고 final_path 로 원자적으로 교체한다.

    고정된 임시 파일명을 여러 프로세스가 공유하면 동시 쓰기가 뒤섞인 파일을 발행할 수 있다
    (검수 M2) — `tempfile.mkstemp` 로 매 호출마다 고유한 이름을 받는다. 쓰기 전에
    `encode_safe_utf8` 로 정규화한다(루프 밖 보완 HIGH-A) — 그러지 않으면 고립 서로게이트를
    담은 text 가 `UnicodeEncodeError` 로 이 함수 자체를 실패시킨다.
    """
    temp_fd, temp_name = tempfile.mkstemp(dir=directory, prefix=prefix, suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(encode_safe_utf8(text))
        temp_path.replace(final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
