"""hub_redact 단위 테스트. 결함 8 — 시크릿 스크럽 로직. 파이프라인 순서(redact 를 자르기
전에 부른다)와 지수 시간 백트래킹 금지가 핵심 요구사항이다(hub_redact.redact_secret_tokens
문서 참조 — 선형 시간은 아니다: JWT 대안은 긴 글에서 이차 시간이라 입력이 긴 호출자가 길이를
먼저 제한한다).

이 테스트는 원래 hub_hook.py 가 프롬프트를 기록하던 시절 test_hub_hook.py 의
SecretRedactionTest 로 있었다 — hub_hook.py 의 UserPromptSubmit 훅을 stdin 으로 돌려 기록된
줄을 되읽는 간접 경로였다. 결정 PS4(docs/prps/hub-agent-runs-and-prompt-source.md)로 훅이
프롬프트를 더 이상 기록하지 않게 되며 그 간접 경로 자체가 사라졌다 — hub_redact 를 직접
호출하는 이 파일로 옮겨, 로직 자체의 회귀 가드는 그대로 남긴다.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_redact  # noqa: E402  (sys.path 조정 후 임포트)

# 재앙적 백트래킹(분 단위)과 정상 소요(ms) 사이에 여유를 둔 상한.
SECRET_TIMEOUT_SECONDS = 2


class SecretRedactionTest(unittest.TestCase):
    def test_anthropic_key_is_masked_and_surrounding_prose_survives(self) -> None:
        prompt = "이 키 좀 봐줘 sk-ant-abcdefghijklmnopqrstuvwxyz 고마워"
        redacted = hub_redact.redact_secret_tokens(prompt)
        self.assertNotIn("sk-ant-abcdefghijklmnopqrstuvwxyz", redacted)
        self.assertIn(hub_redact.SECRET_REDACTION_MARK, redacted)
        self.assertTrue(redacted.startswith("이 키 좀 봐줘 "))
        self.assertTrue(redacted.endswith(" 고마워"))

    def test_aws_github_jwt_tokens_are_each_masked(self) -> None:
        aws_key = "AKIAABCDEFGHIJKLMNOP"
        github_token = "ghp_" + "a" * 36
        jwt_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PYE2haRQ"

        for secret in (aws_key, github_token, jwt_token):
            with self.subTest(secret=secret):
                redacted = hub_redact.redact_secret_tokens(f"토큰: {secret}")
                self.assertNotIn(secret, redacted)
                self.assertIn(hub_redact.SECRET_REDACTION_MARK, redacted)

    def test_key_value_secret_masks_value_but_keeps_key_name(self) -> None:
        redacted = hub_redact.redact_secret_tokens("api_key=abc12345 로 설정했어")
        self.assertEqual(redacted, f"api_key={hub_redact.SECRET_REDACTION_MARK} 로 설정했어")

    def test_secret_straddling_the_clip_boundary_does_not_leak(self) -> None:
        """스크럽-후-자르기 순서의 회귀 가드 — 잘린 뒤에 스크럽하면 경계에 걸린 시크릿의
        접두사가 그대로 새어 나간다는 것을 간접 확인한다(이 테스트 자체는 자르지 않고
        redact_secret_tokens 가 경계와 무관하게 시크릿 전체를 잡는지만 본다 — 실제 자르기
        + 스크럽 순서 계약은 호출자(hub_transcript.py 등)가 지킨다)."""
        prose = "가" * 490
        secret = "sk-ant-" + "x" * 40
        prompt = prose + secret
        redacted = hub_redact.redact_secret_tokens(prompt)

        self.assertNotIn("sk-ant-", redacted)
        self.assertIn(hub_redact.SECRET_REDACTION_MARK, redacted)

    def test_plain_words_token_and_secret_are_not_touched(self) -> None:
        prompt = "이 token 과 secret 이라는 단어는 값이 아니라 그냥 산문이다"
        self.assertEqual(hub_redact.redact_secret_tokens(prompt), prompt)

    def test_redaction_is_linear_time_on_near_match_repetition(self) -> None:
        """선형성 회귀 가드 — 준-일치 문자열 대량 반복이 넉넉한 상한 안에 끝나야 한다.
        중첩 수량자 등 백트래킹 폭발 형태가 들어오면 이 케이스가 분 단위로 걸려 실패한다."""
        near_match_prompt = "sk-" * 50000

        start = time.perf_counter()
        redacted = hub_redact.redact_secret_tokens(near_match_prompt)
        elapsed_seconds = time.perf_counter() - start

        self.assertLess(elapsed_seconds, SECRET_TIMEOUT_SECONDS)
        self.assertIsInstance(redacted, str)


if __name__ == "__main__":
    unittest.main()
