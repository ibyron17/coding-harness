"""hub_live_session 단위 테스트. docs/prps/hub-live-session-native-source.md §7.1(L1~L13) —
~/.claude/sessions/<pid>.json(호스트 소유 「살아있는 세션 명부」) 레코드의 순수 파서와
5값(RosterState) 판정값 변환을 검증한다."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_live_session  # noqa: E402  (sys.path 조정 후 임포트)


def _record_json(**overrides) -> str:
    payload = {"sessionId": "session-1", "pid": 1234, "status": "busy"}
    payload.update(overrides)
    return json.dumps(payload)


class ParseLiveSessionRecordTest(unittest.TestCase):
    """L1~L7 — 레코드 1건 파싱(parse_live_session_record)."""

    def test_l1_normal_record_round_trips_three_fields(self) -> None:
        """L1 — 실측 원문과 같은 모양의 레코드가 3필드 그대로 나온다.
        변조 검출: status→is_busy 매핑을 뒤집으면 마지막 단언이 깨진다."""
        record = hub_live_session.parse_live_session_record(_record_json())
        self.assertEqual(record.session_id, "session-1")
        self.assertEqual(record.pid, 1234)
        self.assertIs(record.is_busy, True)

    def test_l2_status_key_absent_is_busy_none(self) -> None:
        """L2 — status 키 자체가 없으면 is_busy 는 None(실측 10%).
        변조 검출: payload.get("status") 에 기본값 "idle" 을 주면 is_busy 가 False 로 나와 실패한다."""
        text = json.dumps({"sessionId": "session-1", "pid": 1234})
        record = hub_live_session.parse_live_session_record(text)
        self.assertIsNone(record.is_busy)

    def test_l3_status_busy_is_true(self) -> None:
        """L3 — 변조 검출: LIVE_SESSION_STATUS_BUSY 상수를 "Busy" 로 바꾸면 "busy" 입력이
        더 이상 매치되지 않아 is_busy 가 None 이 되어 실패한다."""
        record = hub_live_session.parse_live_session_record(_record_json(status="busy"))
        self.assertIs(record.is_busy, True)

    def test_l3_status_idle_is_false(self) -> None:
        record = hub_live_session.parse_live_session_record(_record_json(status="idle"))
        self.assertIs(record.is_busy, False)

    def test_l4_status_unknown_value_is_busy_none(self) -> None:
        """L4 — status 가 실측에 없는 값("starting")이면 is_busy 는 None(→ roster_state 는
        "listed"). 변조 검출: 미지값을 False 로 접으면 실패한다."""
        record = hub_live_session.parse_live_session_record(_record_json(status="starting"))
        self.assertIsNone(record.is_busy)

    def test_l5_session_id_missing_is_none(self) -> None:
        text = json.dumps({"pid": 1234, "status": "busy"})
        self.assertIsNone(hub_live_session.parse_live_session_record(text))

    def test_l5_pid_missing_is_none(self) -> None:
        text = json.dumps({"sessionId": "session-1", "status": "busy"})
        self.assertIsNone(hub_live_session.parse_live_session_record(text))

    def test_l5_pid_as_string_is_none(self) -> None:
        """변조 검출: isinstance(pid, int) 검사를 지우면 문자열 pid 도 그대로 통과해 실패한다."""
        record = hub_live_session.parse_live_session_record(_record_json(pid="1234"))
        self.assertIsNone(record)

    def test_l6_pid_zero_is_none(self) -> None:
        """L6 — pid 가 0 또는 음수면 None. 변조 검출: pid > 0 검사를 지우면(os.kill(0,0)
        footgun 재개통) 이 단언이 깨진다."""
        self.assertIsNone(hub_live_session.parse_live_session_record(_record_json(pid=0)))

    def test_l6_pid_negative_is_none(self) -> None:
        self.assertIsNone(hub_live_session.parse_live_session_record(_record_json(pid=-5)))

    def test_bool_pid_is_none(self) -> None:
        """검수 1회차 L1 — JSON 의 true/false 는 파이썬에서 int 의 서브클래스라
        isinstance(pid, int) 만으로는 통과해 버린다(재현: parse_live_session_record 가
        LiveSessionRecord(pid=True, ...) 를 냈었다). pid=True 는 os.kill(1, 0) 과 같아
        launchd(PID 1)를 가리켜 항상 생존이라는 거짓 참을 만든다. 변조 검출:
        `not isinstance(pid, bool)` 조건을 지우면 이 단언이 깨진다."""
        self.assertIsNone(hub_live_session.parse_live_session_record(_record_json(pid=True)))

    def test_pid_over_pid_t_max_is_none(self) -> None:
        """검수 1회차 H1-3 — pid_t 32비트 상한을 넘으면 os.kill 이 OverflowError 를 던져
        ProcessLookupError/PermissionError 두 분기를 모두 뚫는다(재현:
        {"pid": 99999999999999999999}). 변조 검출: `pid <= LIVE_SESSION_PID_MAX` 상한을
        지우면 이 단언이 깨진다."""
        self.assertIsNone(
            hub_live_session.parse_live_session_record(_record_json(pid=99999999999999999999))
        )

    def test_pid_at_pid_t_max_boundary_is_kept(self) -> None:
        """경계값 확인 — LIVE_SESSION_PID_MAX 와 정확히 같은 값은 정상 범위다(비용 0 확인)."""
        record = hub_live_session.parse_live_session_record(
            _record_json(pid=hub_live_session.LIVE_SESSION_PID_MAX)
        )
        self.assertEqual(record.pid, hub_live_session.LIVE_SESSION_PID_MAX)

    def test_live_session_pid_max_pinned_to_darwin_pid_t_signed_max(self) -> None:
        """검수 2회차 H3 — 위 두 테스트는 "상한이 존재하는가"만 보고 "그 값이 맞는가"는
        보지 않는다: test_pid_over_pid_t_max_is_none 은 1e20 리터럴을 써서 2**63 보다도
        큰 상한 어디에도 걸리고, test_pid_at_pid_t_max_boundary_is_kept 는 상수 자신을
        참조해 항진명제다. 그 결과 LIVE_SESSION_PID_MAX 를 `2**63` 이나 `2**31`(off-by-one)
        로 바꿔도 798건 전부 통과했다(검수 실측). 이 값 자체가 Darwin 에서 실제로 고장나는
        경계라(2**31-1 은 os.kill 이 정상 처리, 2**31 은 OverflowError) 리터럴로 고정한다.
        픽스처 하드코딩 금지 규칙의 예외 — 고정하려는 대상이 상수 자신의 값이기 때문이다.
        변조 검출: 상수를 `2**63`·`2**31` 등으로 바꾸면 이 단언이 깨진다."""
        self.assertEqual(hub_live_session.LIVE_SESSION_PID_MAX, 2147483647)

    def test_pid_one_over_darwin_pid_t_max_is_none(self) -> None:
        """검수 2회차 H3 — off-by-one 상한(2**31)에서 실제로 고장나는 값(2147483648)을
        상수 참조가 아니라 리터럴로 박아 검사한다(위 테스트와 같은 이유 — 상수를 참조하면
        상한 자체가 틀린 값으로 바뀌어도 이 테스트가 그 틀린 값을 그대로 따라가 버린다)."""
        self.assertIsNone(
            hub_live_session.parse_live_session_record(_record_json(pid=2147483648))
        )

    def test_l7_broken_json_is_none_without_raising(self) -> None:
        """L7 — 변조 검출: except json.JSONDecodeError 를 지우면 예외가 그대로 올라와 이
        테스트 자체가 에러로 실패한다."""
        self.assertIsNone(hub_live_session.parse_live_session_record("not-json-at-all"))

    def test_l7_top_level_list_is_none(self) -> None:
        self.assertIsNone(hub_live_session.parse_live_session_record(json.dumps([1, 2, 3])))


class ParserNeverRaisesOnPathologicalInputTest(unittest.TestCase):
    """검수 1회차 H1 — 계약 B(hub_workflow.parse_workflow_run·hub_subagent.parse_subagent_meta
    와 동형, "어떤 입력에도 예외를 던지지 않는다")를 병리적 입력 표로 고정한다(선례:
    hub_workflow.py 의 ParserNeverRaisesOnPathologicalInputTest). 신설 당시
    except (json.JSONDecodeError, TypeError) 였던 이 함수는 아래 두 입력에서 실제로
    ValueError·RecursionError 를 던졌다(검수 1회차 직접 재현)."""

    PATHOLOGICAL_INPUTS = (
        ("4,400자리를 넘는 정수 리터럴", '{"sessionId": "s", "pid": ' + "9" * 4400 + "}"),
        ("깊게 중첩된 배열", "[" * 30000 + "]" * 30000),
    )

    def test_pathological_input_never_raises(self) -> None:
        for description, text in self.PATHOLOGICAL_INPUTS:
            with self.subTest(description=description):
                try:
                    result = hub_live_session.parse_live_session_record(text)
                except Exception as error:  # 계약 자체가 "무엇이 와도 던지지 않는다"다
                    self.fail(f"{description} 입력에서 예외 발생: {error!r}")
                self.assertIsNone(result)


class BuildLiveSessionIndexTest(unittest.TestCase):
    """L8~L9 — 같은 session_id 의 레코드가 여럿일 때의 결정적 접기(build_live_session_index)."""

    def test_l8_busy_wins_over_idle_regardless_of_order(self) -> None:
        """L8 — 변조 검출: 접기 우선순위를 pid 순으로만 바꾸면(busy>idle 우선순위 삭제) idle 쪽
        (pid 더 작음)이 이겨 이 단언이 깨진다."""
        busy = hub_live_session.LiveSessionRecord(session_id="s1", pid=200, is_busy=True)
        idle = hub_live_session.LiveSessionRecord(session_id="s1", pid=100, is_busy=False)
        index_busy_first = hub_live_session.build_live_session_index([busy, idle], is_complete=True)
        index_idle_first = hub_live_session.build_live_session_index([idle, busy], is_complete=True)
        self.assertIs(index_busy_first.by_session_id["s1"].is_busy, True)
        self.assertIs(index_idle_first.by_session_id["s1"].is_busy, True)

    def test_l8b_unknown_wins_over_idle_regardless_of_order(self) -> None:
        """검수 1회차 H3 — L8 은 busy>idle, L9 는 동률 타이브레이커만 본다. 우선순위 3단
        (busy 0 > 미상 1 > idle 2) 중 중간 단(미상 vs idle)을 가르는 테스트가 없었다.
        idle 쪽 pid 를 더 작게 둬(idle=100, 미상=200) 타이브레이커가 대신 맞히는 거짓
        양성을 막는다(L8 과 같은 기법). 변조 검출: _fold_priority 의
        `is_busy is None: return 1` 을 `return 2` 로 바꾸면(미상과 idle 의 우선순위가
        같아져) pid 가 더 작은 idle 쪽이 이겨 이 단언이 깨진다."""
        idle = hub_live_session.LiveSessionRecord(session_id="s1", pid=100, is_busy=False)
        unknown = hub_live_session.LiveSessionRecord(session_id="s1", pid=200, is_busy=None)
        index_idle_first = hub_live_session.build_live_session_index([idle, unknown], is_complete=True)
        index_unknown_first = hub_live_session.build_live_session_index([unknown, idle], is_complete=True)
        self.assertIsNone(index_idle_first.by_session_id["s1"].is_busy)
        self.assertIsNone(index_unknown_first.by_session_id["s1"].is_busy)

    def test_l8c_busy_wins_over_unknown_regardless_of_order(self) -> None:
        """검수 2회차 H2 — 우선순위 3단(busy 0 > 미상 1 > idle 2) 중 인접 쌍은 정확히
        3개(busy-idle, idle-미상, busy-미상)인데 L8(busy-idle)·L8b(idle-미상) 는 두 쌍만
        덮고 마지막 쌍(busy-미상)이 무방비였다(1회차 H3 가 빠뜨린 것과 같은 결함 계열).
        미상 쪽 pid 를 더 작게 둬(미상=100, busy=200) 타이브레이커가 대신 맞히는 거짓
        양성을 막는다(L8·L8b 와 같은 기법). 변조 검출: `_fold_priority` 의
        `is_busy is True: return 0` 을 `return 1` 로 바꾸면(busy 와 미상의 우선순위가
        같아져) pid 가 더 작은 미상 쪽이 이겨 이 단언이 깨진다."""
        unknown = hub_live_session.LiveSessionRecord(session_id="s1", pid=100, is_busy=None)
        busy = hub_live_session.LiveSessionRecord(session_id="s1", pid=200, is_busy=True)
        index_unknown_first = hub_live_session.build_live_session_index([unknown, busy], is_complete=True)
        index_busy_first = hub_live_session.build_live_session_index([busy, unknown], is_complete=True)
        self.assertIs(index_unknown_first.by_session_id["s1"].is_busy, True)
        self.assertIs(index_busy_first.by_session_id["s1"].is_busy, True)

    def test_l9_same_status_smaller_pid_wins_deterministically(self) -> None:
        """L9 — 변조 검출: 타이브레이커(pid 비교)를 지우면 입력 순서에 따라 승자가 바뀌어
        두 호출의 결과가 달라진다(snapshot_content_key 결정성 위협)."""
        first = hub_live_session.LiveSessionRecord(session_id="s1", pid=200, is_busy=None)
        second = hub_live_session.LiveSessionRecord(session_id="s1", pid=100, is_busy=None)
        index_one = hub_live_session.build_live_session_index([first, second], is_complete=True)
        index_two = hub_live_session.build_live_session_index([second, first], is_complete=True)
        self.assertEqual(index_one.by_session_id["s1"].pid, 100)
        self.assertEqual(index_two.by_session_id["s1"].pid, 100)

    def test_distinct_session_ids_are_kept_independently(self) -> None:
        one = hub_live_session.LiveSessionRecord(session_id="s1", pid=100, is_busy=True)
        two = hub_live_session.LiveSessionRecord(session_id="s2", pid=200, is_busy=False)
        index = hub_live_session.build_live_session_index([one, two], is_complete=True)
        self.assertEqual(set(index.by_session_id), {"s1", "s2"})


class RosterStateForSessionTest(unittest.TestCase):
    """L10~L13 — 5값 판정(roster_state_for_session)."""

    def test_l10_none_index_is_unknown(self) -> None:
        """L10 — 변조 검출: index is None 분기를 지우면 None.by_session_id 접근에서
        AttributeError 로 죽는다."""
        self.assertEqual(hub_live_session.roster_state_for_session(None, "s1"), "unknown")

    def test_l11_incomplete_index_and_unregistered_is_unknown(self) -> None:
        """L11 — 변조 검출: is_complete 를 무시하면 "not_listed" 가 나와 실패한다.

        검수 2회차 M3 — `by_session_id` 를 **비어 있지 않게** 둔다(다른 세션 "other" 만
        등재하고 "s1" 은 조회만 한다). `return "not_listed" if index.by_session_id or
        index.is_complete else "unknown"` 처럼 게이트를 truthiness 로 넓히는 변조는 빈
        딕셔너리만 쓰는 픽스처로는 못 잡는다 — 레코드를 하나라도 실제로 읽은 상태에서
        불완전(is_complete=False)해야 그 변조가 "unknown" 대신 "not_listed" 를 내도록
        만들어 이 단언이 깨진다."""
        other_record = hub_live_session.LiveSessionRecord(session_id="other", pid=1, is_busy=True)
        index = hub_live_session.LiveSessionIndex(by_session_id={"other": other_record}, is_complete=False)
        self.assertEqual(hub_live_session.roster_state_for_session(index, "s1"), "unknown")

    def test_l12_complete_index_and_unregistered_is_not_listed(self) -> None:
        """L12 — 변조 검출: 미등재를 항상 "unknown" 으로 반환하게 하면 실패한다."""
        index = hub_live_session.LiveSessionIndex(by_session_id={}, is_complete=True)
        self.assertEqual(hub_live_session.roster_state_for_session(index, "s1"), "not_listed")

    def test_l12b_complete_index_with_other_sessions_and_unregistered_is_not_listed(self) -> None:
        """L12b — L12 와 같은 판정을 **비어 있지 않은** 명부에서 확인한다(검수 3회차 H2).

        `(by_session_id 비었나) × (is_complete)` 네 칸 중 「있다+True+미등재」가 비어 있었다.
        L12 는 빈 명부만 보므로 게이트를 `index.is_complete and not index.by_session_id` 로
        **좁히는** 변조를 못 잡는다 — 검수 2회차 M3 이 막은 것은 truthiness 로 넓히는 반대
        방향뿐이었다. 실사용에서 명부는 다른 살아있는 세션들 때문에 거의 항상 비어 있지
        않으므로, 그 변조가 들어가면 `not_listed` 행이 **영원히 실행되지 않아** 죽은 세션이
        계속 「작업중」으로 남는다 — 이 기능이 고치려던 증상 그 자체이고, 그래도 803건이
        전부 통과했다."""
        other_record = hub_live_session.LiveSessionRecord(session_id="other", pid=1, is_busy=True)
        index = hub_live_session.LiveSessionIndex(by_session_id={"other": other_record}, is_complete=True)
        self.assertEqual(hub_live_session.roster_state_for_session(index, "s1"), "not_listed")

    def test_l13_registered_busy(self) -> None:
        """L13 — 변조 검출: is_busy is None 분기를 "not is_busy" 로 바꾸면 미상(None)이
        idle 로 오분류돼 이 세 테스트 중 하나가 깨진다."""
        record = hub_live_session.LiveSessionRecord(session_id="s1", pid=1, is_busy=True)
        index = hub_live_session.LiveSessionIndex(by_session_id={"s1": record}, is_complete=True)
        self.assertEqual(hub_live_session.roster_state_for_session(index, "s1"), "busy")

    def test_l13_registered_idle(self) -> None:
        record = hub_live_session.LiveSessionRecord(session_id="s1", pid=1, is_busy=False)
        index = hub_live_session.LiveSessionIndex(by_session_id={"s1": record}, is_complete=True)
        self.assertEqual(hub_live_session.roster_state_for_session(index, "s1"), "idle")

    def test_l13_registered_unknown_status_is_listed(self) -> None:
        record = hub_live_session.LiveSessionRecord(session_id="s1", pid=1, is_busy=None)
        index = hub_live_session.LiveSessionIndex(by_session_id={"s1": record}, is_complete=True)
        self.assertEqual(hub_live_session.roster_state_for_session(index, "s1"), "listed")

    def test_l12_and_l11_use_is_complete_field_not_dict_truthiness(self) -> None:
        """LS7 회귀 방어 — 빈 딕셔너리라도 is_complete=True 면 not_listed, False 면 unknown 이다
        (by_session_id 의 truthiness 로 대신하면 둘 다 같은 결과가 나와 이 대조가 무너진다)."""
        complete_empty = hub_live_session.LiveSessionIndex(by_session_id={}, is_complete=True)
        incomplete_empty = hub_live_session.LiveSessionIndex(by_session_id={}, is_complete=False)
        self.assertEqual(hub_live_session.roster_state_for_session(complete_empty, "s1"), "not_listed")
        self.assertEqual(hub_live_session.roster_state_for_session(incomplete_empty, "s1"), "unknown")


if __name__ == "__main__":
    unittest.main()
