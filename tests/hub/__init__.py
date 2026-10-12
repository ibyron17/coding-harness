"""tests/hub 패키지 초기화 — 실제 `~/.claude.json` 을 읽는 테스트를 구조적으로 막는다.

단위 테스트는 실제 `$HOME` 으로 돈다. 사용량 캡처를 만드는 테스트가 `collect_snapshot` 을
부르면 계정 읽기(`hub_collect.read_account_info`)까지 가므로, 경로 상수를 바꿔 끼우기를
잊은 테스트가 실제 로그인 계정의 이메일을 읽게 된다. 패키지가 로드될 때 그 경로를 존재하지
않는 곳으로 한 번 중화해 두면 그런 테스트는 아무것도 읽지 않는다(fail-closed,
docs/prps/hub-usage-panel-account.md 결정 AC12).

계정 테스트는 각자 임시 파일로 덮고 tearDown 에서 **이 중화값으로** 되돌린다 — 원래(실제)
경로로 되돌리면 뒤따르는 테스트가 실제 파일을 읽는다. 정본 실행 명령
(`python3 -m unittest discover -s tests/hub -t .`)만 이 중화를 보장한다 — 테스트 파일을
`python3 tests/hub/x.py` 로 직접 실행하면 패키지를 거치지 않아 중화가 빠진다.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_collect  # noqa: E402  (sys.path 조정 후 임포트)
import hub_session_cost  # noqa: E402

NEUTRALIZED_CLAUDE_GLOBAL_CONFIG_PATH = Path("/nonexistent-coding-harness-tests/.claude.json")
hub_collect.CLAUDE_GLOBAL_CONFIG_PATH = NEUTRALIZED_CLAUDE_GLOBAL_CONFIG_PATH

# 세션 비용 캡처 디렉터리(⑨, docs/prps/harness-benchmark-adoption.md)도 같은 방식으로 중화한다 —
# collect_snapshot 은 보관 기간이 지난 캡처 파일을 지우고 보이는 세션의 캡처를 읽으므로, 경로 상수를
# 바꿔 끼우기를 잊은 테스트가 실제 홈의 파일을 지우거나 읽지 못하게 한다. 캡처를 쓰는 테스트는 각자
# 임시 디렉터리로 덮고 tearDown 에서 **이 중화값으로** 되돌린다.
NEUTRALIZED_SESSION_COSTS_DIR = Path("/nonexistent-coding-harness-tests/session_costs")
hub_session_cost.SESSION_COSTS_DIR = NEUTRALIZED_SESSION_COSTS_DIR
