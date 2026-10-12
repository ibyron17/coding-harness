"""hub_server_state 단위 테스트. docs/prps/hub-dashboard.md 「테스트 계획」 M21~M26,
D6(parse_server_record) — hub_daemon.py 와 hub_collect.py 가 공유하는 파서를 하나로
합쳤다(검수 m3). 실사용 경로(hub_server_state_read.read_server_record)를 이 테스트가 직접 덮는다."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_server_state  # noqa: E402  (sys.path 조정 후 임포트)

BASE_TIME_MS = 1_786_000_000_000


class ShouldSpawnCollectTest(unittest.TestCase):
    """M21~M24 — 훅의 재수집 spawn 판정(개정 쟁점 R3)."""

    THROTTLE_MS = 5000

    def test_m21_server_alive_always_false(self) -> None:
        """서버가 살아 있으면 쓰로틀이 지났어도 spawn 하지 않는다 — 서버가 전담한다."""
        result = hub_server_state.should_spawn_collect(
            now_ms=BASE_TIME_MS, server_alive=True,
            hub_html_mtime_ms=BASE_TIME_MS - 60_000, spawn_stamp_mtime_ms=None,
            throttle_ms=self.THROTTLE_MS,
        )
        self.assertFalse(result)

    def test_m22_server_dead_no_stamp_hub_html_stale(self) -> None:
        result = hub_server_state.should_spawn_collect(
            now_ms=BASE_TIME_MS, server_alive=False,
            hub_html_mtime_ms=BASE_TIME_MS - 6000, spawn_stamp_mtime_ms=None,
            throttle_ms=self.THROTTLE_MS,
        )
        self.assertTrue(result)

    def test_m23_server_dead_recent_stamp_is_throttled(self) -> None:
        result = hub_server_state.should_spawn_collect(
            now_ms=BASE_TIME_MS, server_alive=False,
            hub_html_mtime_ms=BASE_TIME_MS - 60_000, spawn_stamp_mtime_ms=BASE_TIME_MS - 2000,
            throttle_ms=self.THROTTLE_MS,
        )
        self.assertFalse(result)

    def test_m24_hub_html_missing_but_server_alive_is_false(self) -> None:
        """서버가 살아 있으면 hub.html 이 없어도 False — 다음 사이클에 서버가 만든다."""
        result = hub_server_state.should_spawn_collect(
            now_ms=BASE_TIME_MS, server_alive=True,
            hub_html_mtime_ms=None, spawn_stamp_mtime_ms=None,
            throttle_ms=self.THROTTLE_MS,
        )
        self.assertFalse(result)

    def test_m24b_hub_html_missing_and_server_dead_with_no_stamp_spawns_immediately(self) -> None:
        """검수 M2-5 — 서버가 죽고 hub.html 도 없으면(HUB_HOME 쓰기 실패 등으로 한 번도 못
        만든 경우 포함) 훅 폴백이 곧바로 뚫려야 한다. 예전에는 hub_html_mtime_ms 가 None 이면
        서버 상태와 무관하게 항상 False 라, 상주 서버가 hub.html 을 한 번도 못 만든 채 수집
        스레드까지 죽으면 훅 폴백조차 영원히 막히는 이중 실패였다."""
        result = hub_server_state.should_spawn_collect(
            now_ms=BASE_TIME_MS, server_alive=False,
            hub_html_mtime_ms=None, spawn_stamp_mtime_ms=None,
            throttle_ms=self.THROTTLE_MS,
        )
        self.assertTrue(result)

    def test_m24c_hub_html_missing_and_server_dead_but_recent_stamp_is_throttled(self) -> None:
        """즉시 재시도를 허용해도 쓰로틀은 여전히 산다 — 매 훅마다 spawn 하지 않는다."""
        result = hub_server_state.should_spawn_collect(
            now_ms=BASE_TIME_MS, server_alive=False,
            hub_html_mtime_ms=None, spawn_stamp_mtime_ms=BASE_TIME_MS - 2000,
            throttle_ms=self.THROTTLE_MS,
        )
        self.assertFalse(result)


class IsServerAliveTest(unittest.TestCase):
    """M25 — 하트비트 나이로 상주 서버 생존을 판정한다."""

    TTL_MS = 15_000

    def test_m25_no_heartbeat_file(self) -> None:
        self.assertFalse(hub_server_state.is_server_alive(BASE_TIME_MS, None, self.TTL_MS))

    def test_m25_just_before_ttl(self) -> None:
        heartbeat_mtime_ms = BASE_TIME_MS - (self.TTL_MS - 1)
        self.assertTrue(hub_server_state.is_server_alive(BASE_TIME_MS, heartbeat_mtime_ms, self.TTL_MS))

    def test_m25_just_after_ttl(self) -> None:
        heartbeat_mtime_ms = BASE_TIME_MS - self.TTL_MS
        self.assertFalse(hub_server_state.is_server_alive(BASE_TIME_MS, heartbeat_mtime_ms, self.TTL_MS))


class ServerHeartbeatTtlMsTest(unittest.TestCase):
    """M26 — 하트비트 주기 3배, 하한 15초(개정 2 — 공식·값은 그대로, 뜻만 사실에 맞췄다)."""

    def test_m26_short_interval_hits_floor(self) -> None:
        self.assertEqual(hub_server_state.server_heartbeat_ttl_ms(1), 15_000)

    def test_m26_default_interval_hits_floor(self) -> None:
        self.assertEqual(hub_server_state.server_heartbeat_ttl_ms(5), 15_000)

    def test_m26_long_interval_uses_multiplier(self) -> None:
        self.assertEqual(hub_server_state.server_heartbeat_ttl_ms(60), 180_000)


class EvaluateCollectHealthTest(unittest.TestCase):
    """개정 2 — 요청 구동 수집에서 "수집이 실제로 되고 있는가"를 성공·실패 시각의 순서만으로
    판정한다(나이는 보지 않는다)."""

    def test_both_absent_is_never_collected(self) -> None:
        result = hub_server_state.evaluate_collect_health(
            last_success_at_ms=None, last_failure_at_ms=None
        )
        self.assertEqual(result, "never_collected")

    def test_success_only_is_ok(self) -> None:
        result = hub_server_state.evaluate_collect_health(
            last_success_at_ms=1_000, last_failure_at_ms=None
        )
        self.assertEqual(result, "ok")

    def test_failure_only_is_failing(self) -> None:
        result = hub_server_state.evaluate_collect_health(
            last_success_at_ms=None, last_failure_at_ms=1_000
        )
        self.assertEqual(result, "failing")

    def test_more_recent_failure_is_failing(self) -> None:
        result = hub_server_state.evaluate_collect_health(
            last_success_at_ms=1_000, last_failure_at_ms=2_000
        )
        self.assertEqual(result, "failing")

    def test_more_recent_success_is_ok(self) -> None:
        result = hub_server_state.evaluate_collect_health(
            last_success_at_ms=2_000, last_failure_at_ms=1_000
        )
        self.assertEqual(result, "ok")

    def test_same_timestamp_folds_to_ok(self) -> None:
        """동시각 규약 고정 — 한 사이클이 성공하면 실패 기록을 지운 뒤 성공 스탬프를 찍으므로,
        같은 ms 에 둘이 잡히면 성공이 나중이다."""
        result = hub_server_state.evaluate_collect_health(
            last_success_at_ms=1_000, last_failure_at_ms=1_000
        )
        self.assertEqual(result, "ok")


class ParseServerRecordTest(unittest.TestCase):
    """D6 — 정상 1건, 나머지 전부 None(예외 없음). hub_daemon.py 와 hub_collect.py 가 공유하는
    파서를 hub_server_state.py 하나로 합쳤다(검수 m3) — 실사용 경로(hub_server_state_read.read_server_record)를
    이 테스트가 직접 덮는다.

    P1~P6(설계 문서 hub-server-identity.md §9-1) — 선택 필드 hub_py_path 확장. P6 은 아래
    기존 D6 케이스 3개가 그대로 맡는다(필수화 회귀 방지 — 새 필드가 기존 파싱 계약을
    깨지 않는다)."""

    def test_d6_valid_record(self) -> None:
        record = hub_server_state.parse_server_record(
            '{"pid": 123, "port": 8794, "started_at_ms": 1786000000000}'
        )
        self.assertIsNotNone(record)
        self.assertEqual((record.pid, record.port, record.started_at_ms), (123, 8794, 1786000000000))

    def test_d6_missing_field(self) -> None:
        self.assertIsNone(hub_server_state.parse_server_record('{"pid": 123, "port": 8794}'))

    def test_d6_broken_json(self) -> None:
        self.assertIsNone(hub_server_state.parse_server_record("{not valid json"))

    def test_d6_empty_file(self) -> None:
        self.assertIsNone(hub_server_state.parse_server_record(""))

    def test_p1_new_format_fills_hub_py_path(self) -> None:
        """P1 — 새 형식(4필드)이면 hub_py_path 가 그 값으로 채워진다."""
        record = hub_server_state.parse_server_record(
            '{"pid": 123, "port": 8794, "started_at_ms": 1786000000000, '
            '"hub_py_path": "/Users/x/.claude/hub/bin/hub.py"}'
        )
        self.assertIsNotNone(record)
        self.assertEqual(record.hub_py_path, "/Users/x/.claude/hub/bin/hub.py")

    def test_p2_legacy_format_without_field_is_none(self) -> None:
        """P2 — 구버전(3필드, 필드 부재)도 파싱은 성공하고 hub_py_path 는 None(필수화 회귀 방지)."""
        record = hub_server_state.parse_server_record(
            '{"pid": 123, "port": 8794, "started_at_ms": 1786000000000}'
        )
        self.assertIsNotNone(record)
        self.assertIsNone(record.hub_py_path)

    def test_p3_null_value_is_none(self) -> None:
        record = hub_server_state.parse_server_record(
            '{"pid": 123, "port": 8794, "started_at_ms": 1786000000000, "hub_py_path": null}'
        )
        self.assertIsNotNone(record)
        self.assertIsNone(record.hub_py_path)

    def test_p4_empty_or_whitespace_value_is_none(self) -> None:
        """P4 — 빈 문자열/공백만이면 None(빈 문자열이 비교 기준으로 새지 않는다)."""
        for blank_value in ("", "   "):
            with self.subTest(blank_value=repr(blank_value)):
                record = hub_server_state.parse_server_record(
                    '{"pid": 123, "port": 8794, "started_at_ms": 1786000000000, '
                    f'"hub_py_path": "{blank_value}"}}'
                )
                self.assertIsNotNone(record)
                self.assertIsNone(record.hub_py_path)

    def test_p5_wrong_type_value_folds_without_raising(self) -> None:
        """P5 — 타입 위반(정수)이어도 예외 없이 None 으로 접힌다."""
        record = hub_server_state.parse_server_record(
            '{"pid": 123, "port": 8794, "started_at_ms": 1786000000000, "hub_py_path": 123}'
        )
        self.assertIsNotNone(record)
        self.assertIsNone(record.hub_py_path)


if __name__ == "__main__":
    unittest.main()
