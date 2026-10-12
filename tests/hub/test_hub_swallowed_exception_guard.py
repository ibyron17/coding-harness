"""SwallowedExceptionGuardMixin 자신의 음성 대조(회귀 고객).

이 파일이 존재하는 이유: 삼킨 예외 래퍼(swallowed_exception_guard.py)가 고장나면
test_hub_hook.py·test_hub_statusline.py 의 케이스들이 **조용히** 예전 상태(예외로 인한
공허한 부재 단언)로 돌아간다 — 래퍼가 아무것도 하지 않아도 그 파일들은 전부 초록이다.
그래서 「래퍼가 실제로 발화하는가」를 직접 시험한다(PRP tests-hardening §4.5 + S3a 의 교훈
「가드가 있다」와 「가드가 불린다」는 다르다).

원장(tests/mutations.tsv)에 이 층의 변조행은 만들지 않는다 — 8번째 열 anchor_function 은
맨 함수명 문법이라 파일 성분이 없고, 해소기는 tests/run.sh 안에서만 정의를 찾는다. 이 파일의
정의는 그 안에 없어 파이썬 층 가드는 변조행으로는 등록할 수 없다(앵커 해소 실패, 이전에는
5열 규약을 사유로 들었으나 8열 도입 후에도 등록 불가는 그대로다 — ledger-anchor-column
PRP §9-1). 면제행 등록은 파서가 허용하지만 이번 회차에는 하지 않았다(그 판단과 근거는 원장
헤더의 한계 절). 이 파일이 그 자리를 대신한다.

이 파일은 두 층을 시험한다 — 믹스인 자신의 **판정**(아래 다섯 시나리오)과, 실제 진입점
베이스 클래스에 그 믹스인이 실제로 **얹혀 돌고 있는가**(RealEntrypointBasesAreGuardedTest).
두 번째 층이 필요한 이유는 실측이다: statusline 쪽은 옵트인한 케이스 하나가 증인이 되어
믹스인을 떼면 그 케이스가 에러로 죽지만, **hook 쪽에는 증인이 하나도 없어** 믹스인을 떼고도
tests/hub 전체가 통과했다(두 실측 모두 이 두 번째 층을 넣기 전, 622건 기준).
「가드가 있다」와 「가드가 불린다」는 다르다(S3a 의 교훈).

한계(비망라) — 두 번째 층은 베이스 클래스를 상속한 프로브 케이스를 실제로 돌려 `_run` 이
교체됐는지만 본다. 그 아래 개별 시나리오 클래스가 베이스를 우회해 진입점을 직접 부르는
형태(예: 새 테스트가 unittest.TestCase 를 직접 상속해 hub_hook.main() 을 호출)는 보지 않고,
믹스인이 감싸지 않는 다른 진입점이 새로 생기는 것도 보지 않는다. 전수 증명이 아니다.
"""

import io
import types
import unittest

try:
    from . import test_hub_hook, test_hub_statusline
    from .swallowed_exception_guard import SwallowedExceptionGuardMixin
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    import test_hub_hook  # noqa: E402
    import test_hub_statusline  # noqa: E402
    from swallowed_exception_guard import SwallowedExceptionGuardMixin  # noqa: E402

GUARD_MESSAGE_WITHOUT_OPT_IN = "진입점이 예외를 삼켰다"
GUARD_MESSAGE_STALE_OPT_IN = "옵트인했는데 삼킨"
GUARD_MESSAGE_WRONG_TYPE = "다른 예외가 삼켜졌다"
GUARD_MESSAGE_NO_MODULE = "진입점 모듈을 지정해야 한다"


def build_fake_entrypoint_module(run_body) -> types.ModuleType:
    """hub_hook·hub_statusline 과 같은 형태(`_run` + 전부 삼키는 `main`)의 가짜 모듈을 만든다."""
    module = types.ModuleType("fake_entrypoint")

    def main() -> int:
        try:
            module._run()
        except Exception:
            pass
        return 0

    module._run = run_body
    module.main = main
    return module


def run_guarded_probe_case(module, test_body) -> unittest.TestResult:
    """믹스인을 얹은 1케이스 TestCase 를 즉석에서 만들어 돌리고 그 결과를 낸다."""
    case_class = type(
        "GuardProbeCase",
        (SwallowedExceptionGuardMixin, unittest.TestCase),
        {"guarded_entrypoint_module": module, "runTest": test_body},
    )
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    return runner.run(unittest.TestSuite([case_class()]))


def collect_problem_text(result: unittest.TestResult) -> str:
    """실패·에러의 트레이스백을 한 문자열로 이어 낸다(판정 메시지 대조용)."""
    return "\n".join(text for _case, text in list(result.failures) + list(result.errors))


class GuardFiresOnSwallowedExceptionTest(unittest.TestCase):
    """옵트인 없이 예외가 삼켜지면 래퍼가 케이스를 실패시킨다(이 가드의 본래 목적)."""

    def test_swallowed_exception_without_opt_in_fails_the_case(self) -> None:
        def raising_run() -> None:
            raise RuntimeError("삼켜질 예외")

        module = build_fake_entrypoint_module(raising_run)

        def probe(case) -> None:
            case.assertEqual(module.main(), 0)  # 진입점 계약대로 exit 0 은 유지된다

        result = run_guarded_probe_case(module, probe)

        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.wasSuccessful())
        problem_text = collect_problem_text(result)
        self.assertIn(GUARD_MESSAGE_WITHOUT_OPT_IN, problem_text)
        self.assertIn("RuntimeError", problem_text)


class GuardStaysSilentOnCleanRunTest(unittest.TestCase):
    """예외가 없으면 래퍼는 아무것도 하지 않는다(위양성 부재)."""

    def test_clean_run_leaves_the_case_green(self) -> None:
        module = build_fake_entrypoint_module(lambda: None)

        def probe(case) -> None:
            case.assertEqual(module.main(), 0)

        result = run_guarded_probe_case(module, probe)

        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful(), collect_problem_text(result))


class GuardRejectsStaleOptInTest(unittest.TestCase):
    """옵트인했는데 삼킨 예외가 없으면 실패시킨다 — 낡은 옵트인이 케이스를 가드 밖에 남기는
    것을 막는다(공허 통과 방지)."""

    def test_stale_opt_in_fails_the_case(self) -> None:
        module = build_fake_entrypoint_module(lambda: None)

        def probe(case) -> None:
            case.expect_swallowed_exception(RuntimeError, "옛 회차에는 여기서 삼켰다")
            case.assertEqual(module.main(), 0)

        result = run_guarded_probe_case(module, probe)

        self.assertFalse(result.wasSuccessful())
        self.assertIn(GUARD_MESSAGE_STALE_OPT_IN, collect_problem_text(result))


class GuardRejectsWrongExceptionTypeTest(unittest.TestCase):
    """옵트인은 「무엇이든 삼켜도 된다」가 아니다 — 선언한 타입이 아니면 여전히 실패다."""

    def test_wrong_exception_type_fails_the_case(self) -> None:
        def raising_run() -> None:
            raise ValueError("선언하지 않은 예외")

        module = build_fake_entrypoint_module(raising_run)

        def probe(case) -> None:
            case.expect_swallowed_exception(PermissionError, "쓰기 불가만 기대했다")
            case.assertEqual(module.main(), 0)

        result = run_guarded_probe_case(module, probe)

        self.assertFalse(result.wasSuccessful())
        problem_text = collect_problem_text(result)
        self.assertIn(GUARD_MESSAGE_WRONG_TYPE, problem_text)
        self.assertIn("ValueError", problem_text)


class GuardRequiresEntrypointModuleTest(unittest.TestCase):
    """대상 모듈을 지정하지 않은 채 믹스인을 얹으면 setUp 이 시끄럽게 멈춘다 — 래퍼가 붙지
    않은 채 초록으로 도는 자리를 막는다."""

    def test_missing_module_declaration_fails_the_case(self) -> None:
        result = run_guarded_probe_case(None, lambda case: None)

        self.assertFalse(result.wasSuccessful())
        self.assertIn(GUARD_MESSAGE_NO_MODULE, collect_problem_text(result))


class RealEntrypointBasesAreGuardedTest(unittest.TestCase):
    """실제 진입점 베이스 클래스가 이 믹스인을 얹고 있고, setUp 이 래퍼를 실제로 설치하는지
    확인한다 — hook 쪽에는 믹스인을 떼도 알려 주는 케이스가 하나도 없다(실측)."""

    def guarded_base_classes(self) -> tuple:
        """두 진입점 시나리오 베이스 클래스를 낸다(임포트가 sys.path 준비까지 겸한다)."""
        return (
            test_hub_hook.HubHookScenarioTest,
            test_hub_statusline.HubStatuslineEntrypointTest,
        )

    def test_bases_declare_the_guard_and_its_entrypoint_module(self) -> None:
        for base_class in self.guarded_base_classes():
            with self.subTest(base=base_class.__name__):
                self.assertTrue(
                    issubclass(base_class, SwallowedExceptionGuardMixin),
                    f"{base_class.__name__} 가 삼킨 예외 가드 믹스인을 얹지 않았다",
                )
                module = base_class.guarded_entrypoint_module
                self.assertIsNotNone(
                    module, f"{base_class.__name__} 가 guarded_entrypoint_module 을 비워 뒀다"
                )
                self.assertTrue(
                    hasattr(module, "_run"),
                    f"{base_class.__name__} 가 지정한 모듈에 `_run` 이 없다",
                )

    def test_bases_actually_install_the_wrapper_in_set_up(self) -> None:
        """베이스의 setUp 이 super().setUp() 을 실제로 부르는지 — 부르지 않으면 래퍼가 아예
        설치되지 않는다. 베이스를 상속한 프로브 케이스를 unittest 러너로 돌려(공개 API 만
        쓴다 — setUp/tearDown/cleanup 순서를 손으로 흉내내지 않는다) `_run` 교체를 본다."""
        for base_class in self.guarded_base_classes():
            with self.subTest(base=base_class.__name__):
                module = base_class.guarded_entrypoint_module
                original_run = module._run

                def probe(case, module=module, original_run=original_run) -> None:
                    case.assertIsNot(
                        module._run,
                        original_run,
                        "setUp 이 끝났는데도 진입점의 `_run` 이 감싸이지 않았다"
                        " (베이스 setUp 이 super().setUp() 을 부르지 않았을 가능성)",
                    )

                probe_class = type("WrapperInstallProbe", (base_class,), {"runTest": probe})
                runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
                result = runner.run(unittest.TestSuite([probe_class()]))
                self.assertTrue(result.wasSuccessful(), collect_problem_text(result))
                self.assertIs(
                    module._run, original_run, "프로브가 끝난 뒤 `_run` 이 복원되지 않았다"
                )


if __name__ == "__main__":
    unittest.main()
