"""hub_atomic_write.atomic_write_text 단위 테스트. 실제 ~/.claude 는 건드리지 않고
임시 디렉토리에서만 동작한다. 검수 M2·루프 밖 보완 HIGH-A 회귀 대상
(docs/prps/hub-collect-split-for-merge.md §6.2·§10.1). 이 함수를 hub_collect.write_hub_html
경유로 확인하는 이음매 테스트는 tests/hub/test_hub_collect.py 의
WriteHubHtmlAtomicityTest·WriteHubHtmlSurrogateHandlingTest 가 그대로 맡는다.
"""

import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_atomic_write  # noqa: E402


class AtomicWriteTextConcurrencyTest(unittest.TestCase):
    """검수 M2 — 고정 임시 파일명을 공유하면 동시 쓰기가 뒤섞인 파일을 낼 수 있다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.final_path = self.temp_dir / "target.txt"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_concurrent_writes_never_produce_corrupted_output(self) -> None:
        barrier = threading.Barrier(2)
        payloads = ("A" * 500, "B" * 500)

        def write(payload: str) -> None:
            barrier.wait()
            hub_atomic_write.atomic_write_text(self.final_path, self.temp_dir, "target.txt.", payload)

        threads = [threading.Thread(target=write, args=(payload,)) for payload in payloads]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        final_text = self.final_path.read_text(encoding="utf-8")
        self.assertIn(final_text, payloads)  # 뒤섞이면 둘 중 어느 것도 아니게 된다

    def test_no_leftover_temp_files_after_write(self) -> None:
        hub_atomic_write.atomic_write_text(self.final_path, self.temp_dir, "target.txt.", "content")
        leftover = list(self.temp_dir.glob("target.txt.*.tmp"))
        self.assertEqual(leftover, [])


class AtomicWriteTextSurrogateHandlingTest(unittest.TestCase):
    """루프 밖 보완 HIGH-A — 고립 서로게이트를 U+FFFD 로 치환하고 나머지 문자는 보존한다.
    tests/hub/test_hub_collect.py::WriteHubHtmlSurrogateHandlingTest 가 write_hub_html 경유로
    확인하는 것과 같은 정규화 규칙을 여기서는 atomic_write_text 를 직접 두들겨 고정한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.final_path = self.temp_dir / "target.txt"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_lone_surrogate_is_replaced_and_rest_of_text_is_preserved(self) -> None:
        hub_atomic_write.atomic_write_text(self.final_path, self.temp_dir, "target.txt.", "a\ud83db")  # 던지면 실패
        text = self.final_path.read_text(encoding="utf-8")
        self.assertEqual(text, "a\ufffdb")
        self.assertNotIn("\ud83d", text)
        self.assertNotIn("?", text)


class AtomicWriteTextFailureCleanupTest(unittest.TestCase):
    """쓰기 도중 실패해도 임시파일이 남지 않고 예외가 그대로 전파되며 final_path 는 이전
    내용을 유지한다 — 반쯤 쓰다 만 상태를 밖으로 노출하지 않는다는 원자성 계약의 실패 경로."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.final_path = self.temp_dir / "target.txt"
        self.final_path.write_text("previous content", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_failure_leaves_no_temp_file_and_propagates_and_keeps_previous_content(self) -> None:
        # mkstemp 이후(os.fdopen 시점)에 예외를 주입한다 — 그 이전에 실패하면 애초에 임시파일이
        # 생기지 않아 이 테스트가 검증하려는 "쓰다 만 임시파일 정리" 경로를 타지 않는다.
        with mock.patch("os.fdopen", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                hub_atomic_write.atomic_write_text(
                    self.final_path, self.temp_dir, "target.txt.", "new content"
                )

        leftover = list(self.temp_dir.glob("target.txt.*.tmp"))
        self.assertEqual(leftover, [])
        self.assertEqual(self.final_path.read_text(encoding="utf-8"), "previous content")


if __name__ == "__main__":
    unittest.main()
