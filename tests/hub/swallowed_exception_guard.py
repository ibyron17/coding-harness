"""진입점이 삼킨 예외로 인한 「공허한 부재 단언」을 닫는 공용 테스트 가드.

docs/prps/tests-hardening.md §4.5(B8)가 정한 것을 구현한다. hub_hook.main() ·
hub_statusline.main() 은 **어떤 예외도 밖으로 내지 않는 것 자체가 계약**이라
(`try: _run() / except Exception: pass`) 내부에서 죽어도 호출자는 exit 0 을 본다. 그래서
「무엇이 일어나지 않았다」를 단언하는 케이스(test_fresh_hub_html_does_not_spawn 류)는
대상 코드가 결정 지점까지 실제로 도달했는지와 **무관하게** 통과할 수 있다.

이 믹스인은 시나리오 베이스 클래스가 진입점을 부를 때 그 모듈의 내부 `_run` 을 감싸 삼킨
예외를 기록하고, 케이스가 명시적으로 옵트인하지 않았으면 테스트를 실패시킨다. 경계가
2개뿐이므로(§0-7) 개별 케이스를 고치는 대신 하네스 한 곳을 고친다 — 그 모듈의 모든
케이스가 한 번에 면역된다. **프로덕션 코드(hub/bin/)는 건드리지 않는다**(§11-4).

원장(tests/mutations.tsv)에는 이 층의 변조행을 만들지 않는다 — 8번째 열 anchor_function 은
맨 함수명 문법이라 파일 성분이 없고, 해소기는 tests/run.sh 안에서만 정의를 찾는다. 이 파일의
정의는 그 안에 없어 파이썬 층 가드는 **변조행으로는** 등록할 수 없다(앵커 해소 실패). 면제행
등록은 파서가 허용하지만 이번 회차에는 하지 않았다 — 이 가드의 회귀 고객이 같은 층의 음성
대조 테스트(test_hub_swallowed_exception_guard.py)이고, 면제행 상한의 헤드룸이 0 이어서다.
그 판단과 근거는 원장 헤더의 한계 절에 적었다(ledger-anchor-column PRP §9-1).

남는 한계(§4.5 가 정직하게 적어 둔 그대로, 비망라) — 이 래퍼는 **예외로 인한 공허성**만
닫는다. 예외 없이 분기 판정이 틀려 부재가 관측되는 경우는 잡지 못한다. 아래는 비망라
예시다: 상태 준비가 잘못돼 애초에 그 분기에 들어가지 않는 경우, 모킹 대상이 실제 호출
경로가 아닌 경우. 반대 방향(위양성)도 있다 — 이 래퍼는 `_run` 을 **탈출한** 예외를 기록할
뿐 `main` 이 그것을 삼켰는지는 보지 않으므로, 베이스를 상속한 케이스가 `_run` 을 직접 불러
`assertRaises` 로 받으면 삼킴이 아닌데도 「진입점이 예외를 삼켰다」로 실패한다(현재 그런
호출은 0건이다). 전수 증명이 아니다.
"""

from collections.abc import Callable, Sequence
from types import ModuleType
from unittest import mock


def describe_exceptions(exceptions: Sequence[BaseException]) -> str:
    """기록된 예외 목록을 진단용 한 줄 문자열로 만든다."""
    return ", ".join(f"{type(item).__name__}({item})" for item in exceptions) or "<없음>"


class SwallowedExceptionGuardMixin:
    """진입점 모듈의 `_run` 을 감싸 삼킨 예외를 기록하고 옵트인 여부로 판정하는 믹스인.

    사용법: 시나리오 베이스 클래스가 이 믹스인을 unittest.TestCase 앞에 두고
    `guarded_entrypoint_module` 에 대상 모듈을, setUp 첫 줄에서 super().setUp() 을 부른다.
    삼킴이 그 케이스의 계약인 경우에만 expect_swallowed_exception() 으로 옵트인한다.
    """

    guarded_entrypoint_module: ModuleType | None = None

    def setUp(self) -> None:
        super().setUp()
        module = self.guarded_entrypoint_module
        if module is None or not hasattr(module, "_run"):
            raise AssertionError(
                "SwallowedExceptionGuardMixin: guarded_entrypoint_module 에 `_run` 을 가진"
                f" 진입점 모듈을 지정해야 한다(현재: {module!r})"
            )
        self._swallowed_exceptions: list[Exception] = []
        self._expected_swallowed_type = None   # expect_swallowed_exception 이 채우는 옵트인
        self._expected_swallowed_reason = ""
        patcher = mock.patch.object(module, "_run", self._wrap_run(module._run))
        patcher.start()
        # addCleanup 은 LIFO 다 — 먼저 등록한 판정이 패치 해제 **뒤에** 돈다.
        self.addCleanup(self._assert_swallowed_matches_opt_in)
        self.addCleanup(patcher.stop)

    def expect_swallowed_exception(self, exception_type: type, reason: str) -> None:
        """이 케이스가 삼킨 예외를 기대한다고 선언한다(reason: 왜 그것이 계약인지).

        타입까지 받는 이유: 옵트인을 「무엇이든 삼켜도 된다」가 아니라 「이 예외를 삼키는
        것이 계약이다」로 좁힌다 — 다른 예외가 섞여 들어오면 그것은 여전히 실패다.
        """
        self._expected_swallowed_type = exception_type
        self._expected_swallowed_reason = reason

    def _wrap_run(self, original_run: Callable[..., None]) -> Callable[..., None]:
        """`_run` 을 감싸 삼킬 예외를 먼저 기록하고 그대로 다시 던지는 함수를 만든다.

        `Exception` 만 잡는 이유: 진입점이 실제로 삼키는 범위가 그것이고, 그 밖의
        BaseException 은 애초에 호출자까지 전파돼 테스트가 스스로 실패한다.
        """

        def recording_run(*args: object, **kwargs: object) -> None:
            try:
                return original_run(*args, **kwargs)
            except Exception as exception:
                self._swallowed_exceptions.append(exception)
                raise

        return recording_run

    def _assert_swallowed_matches_opt_in(self) -> None:
        """삼킨 예외 기록과 옵트인 선언이 맞는지 판정한다(양방향)."""
        swallowed = self._swallowed_exceptions
        expected_type = self._expected_swallowed_type
        if expected_type is None:
            if swallowed:
                raise AssertionError(
                    "진입점이 예외를 삼켰다 — 이 케이스의 단언은 대상 코드가 결정 지점까지"
                    " 도달했음을 전제로만 유효하다(PRP tests-hardening §4.5). 삼킴이 이"
                    " 케이스의 계약이라면 expect_swallowed_exception() 으로 사유와 함께"
                    f" 옵트인하라. 삼킨 예외: {describe_exceptions(swallowed)}"
                )
            return
        if not swallowed:
            raise AssertionError(
                f"expect_swallowed_exception({expected_type.__name__}) 로 옵트인했는데 삼킨"
                " 예외가 없다 — 옵트인이 낡아 이 케이스가 가드 밖에 남아 있다(공허 통과"
                f" 방지). 선언한 사유: {self._expected_swallowed_reason}"
            )
        unexpected = [item for item in swallowed if not isinstance(item, expected_type)]
        if unexpected:
            raise AssertionError(
                f"옵트인한 예외 타입은 {expected_type.__name__} 인데 다른 예외가 삼켜졌다"
                f" — {describe_exceptions(unexpected)}"
            )
