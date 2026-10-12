"""hub_settings 의 순수 병합/제거 로직 단위 테스트.
검수 m1(손상 스키마 내구성)·m2(순수 함수 분리)·n1(파일 모드 보존)·n2(원래 빈 키 보존) 대상.
"""

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_settings  # noqa: E402  (sys.path 조정 후 임포트)

CAM_ENTRY = {
    "hooks": [
        {
            "type": "command",
            "command": (
                "curl -s -m 2 -o /dev/null --data-binary @- -H 'content-type: application/json' "
                "-X POST 'http://127.0.0.1:8790/event' 2>/dev/null || true"
            ),
        }
    ]
}
LITMUS_ENTRY = {
    "hooks": [{"type": "command", "command": '"/Applications/Litmus.app/Contents/MacOS/litmus-hook" claude-stop'}],
    "matcher": "",
}


def _settings_with_all_events(overrides: dict | None = None) -> dict:
    hooks = {name: [] for name in hub_settings.HOOK_EVENTS}
    if overrides:
        hooks.update(overrides)
    return {"hooks": hooks}


class MergeHubHooksTest(unittest.TestCase):
    def test_appends_matcherless_entry_for_every_event(self) -> None:
        merged = hub_settings.merge_hub_hooks(_settings_with_all_events())
        for event_name in hub_settings.HOOK_EVENTS:
            self.assertTrue(hub_settings._entry_has_hub_marker(merged["hooks"][event_name][-1]))

    def test_preserves_existing_cam_and_litmus_entries(self) -> None:
        settings = _settings_with_all_events({"Stop": [CAM_ENTRY, LITMUS_ENTRY]})
        merged = hub_settings.merge_hub_hooks(settings)
        self.assertIn(CAM_ENTRY, merged["hooks"]["Stop"])
        self.assertIn(LITMUS_ENTRY, merged["hooks"]["Stop"])
        self.assertEqual(len(merged["hooks"]["Stop"]), 3)

    def test_idempotent_when_already_installed(self) -> None:
        already_installed = {name: [hub_settings._hub_hook_entry()] for name in hub_settings.HOOK_EVENTS}
        merged = hub_settings.merge_hub_hooks({"hooks": already_installed})
        for event_name in hub_settings.HOOK_EVENTS:
            self.assertEqual(len(merged["hooks"][event_name]), 1)

    def test_input_settings_is_not_mutated(self) -> None:
        settings = _settings_with_all_events()
        original = copy.deepcopy(settings)
        hub_settings.merge_hub_hooks(settings)
        self.assertEqual(settings, original)

    def test_hooks_not_a_dict_raises_schema_error(self) -> None:
        with self.assertRaises(hub_settings.HubHooksSchemaError):
            hub_settings.merge_hub_hooks({"hooks": "not-a-dict"})

    def test_event_entries_not_a_list_raises_schema_error(self) -> None:
        with self.assertRaises(hub_settings.HubHooksSchemaError):
            hub_settings.merge_hub_hooks({"hooks": {"Stop": "not-a-list"}})


class StripHubHooksTest(unittest.TestCase):
    def test_removes_only_marker_entries_preserves_others(self) -> None:
        settings = _settings_with_all_events({"Stop": [CAM_ENTRY, LITMUS_ENTRY, hub_settings._hub_hook_entry()]})
        stripped = hub_settings.strip_hub_hooks(settings)
        self.assertEqual(stripped["hooks"]["Stop"], [CAM_ENTRY, LITMUS_ENTRY])

    def test_removes_event_key_when_empty_after_strip(self) -> None:
        settings = {"hooks": {"SessionStart": [hub_settings._hub_hook_entry()]}}
        stripped = hub_settings.strip_hub_hooks(settings)
        self.assertNotIn("SessionStart", stripped.get("hooks", {}))

    def test_removes_hooks_key_when_all_events_empty_after_strip(self) -> None:
        installed = {name: [hub_settings._hub_hook_entry()] for name in hub_settings.HOOK_EVENTS}
        stripped = hub_settings.strip_hub_hooks({"hooks": installed})
        self.assertNotIn("hooks", stripped)

    def test_no_hooks_key_is_a_no_op(self) -> None:
        settings = {"model": "opus"}
        stripped = hub_settings.strip_hub_hooks(settings)
        self.assertEqual(stripped, settings)

    def test_input_settings_is_not_mutated(self) -> None:
        settings = {"hooks": {"Stop": [hub_settings._hub_hook_entry()]}}
        original = copy.deepcopy(settings)
        hub_settings.strip_hub_hooks(settings)
        self.assertEqual(settings, original)

    def test_hooks_not_a_dict_raises_schema_error(self) -> None:
        with self.assertRaises(hub_settings.HubHooksSchemaError):
            hub_settings.strip_hub_hooks({"hooks": "not-a-dict"})

    def test_preexisting_empty_array_key_survives_strip_untouched(self) -> None:
        """검수 n2 — 우리가 만들지 않은(원래 비어 있던) 키는 제거하지 않는다.

        SubagentStart 는 애초에 설치된 적이 없어(빈 배열) 그대로 남아야 하고, Stop 은 우리가
        설치했던 엔트리라 제거로 비면 키 자체가 사라져야 한다 — 두 결과가 달라야 이 회귀를 잡는다.
        """
        settings = {"hooks": {"SubagentStart": [], "Stop": [hub_settings._hub_hook_entry()]}}
        stripped = hub_settings.strip_hub_hooks(settings)
        self.assertEqual(stripped["hooks"]["SubagentStart"], [])
        self.assertNotIn("Stop", stripped["hooks"])


class HookInstallStatusFromSettingsTest(unittest.TestCase):
    def test_detects_installed_and_missing_events(self) -> None:
        settings = {"hooks": {"Stop": [hub_settings._hub_hook_entry()]}}
        status = hub_settings.hook_install_status_from_settings(settings)
        self.assertTrue(status["Stop"])
        self.assertFalse(status["SessionStart"])

    def test_malformed_schema_returns_all_false_without_raising(self) -> None:
        """검수 m1 — 손상 스키마에서도 트레이스백 대신 False 계약을 지킨다."""
        status = hub_settings.hook_install_status_from_settings({"hooks": "broken"})
        self.assertTrue(all(value is False for value in status.values()))


class EntryHasHubMarkerRobustnessTest(unittest.TestCase):
    """검수 m1 — 손상된 엔트리 구조에서도 트레이스백 없이 False 를 돌려준다."""

    def test_non_dict_entry(self) -> None:
        self.assertFalse(hub_settings._entry_has_hub_marker("not-a-dict"))

    def test_hooks_field_not_a_list(self) -> None:
        self.assertFalse(hub_settings._entry_has_hub_marker({"hooks": "not-a-list"}))

    def test_hook_item_not_a_dict(self) -> None:
        self.assertFalse(hub_settings._entry_has_hub_marker({"hooks": ["not-a-dict"]}))


class StatuslineOwnerTest(unittest.TestCase):
    """케이스 R15 — 소유자 판정표(결정 S4 의 전부)."""

    def test_r15_key_missing_is_none(self) -> None:
        self.assertEqual(hub_settings.statusline_owner({}), "none")

    def test_r15_null_value_is_none(self) -> None:
        self.assertEqual(hub_settings.statusline_owner({"statusLine": None}), "none")

    def test_r15_our_marker_is_hub(self) -> None:
        settings = {"statusLine": {"type": "command", "command": hub_settings.STATUSLINE_COMMAND}}
        self.assertEqual(hub_settings.statusline_owner(settings), "hub")

    def test_r15_foreign_command_dict_is_foreign(self) -> None:
        settings = {"statusLine": {"type": "command", "command": "python3 my_own_statusline.py"}}
        self.assertEqual(hub_settings.statusline_owner(settings), "foreign")

    def test_r15_string_value_is_foreign(self) -> None:
        self.assertEqual(hub_settings.statusline_owner({"statusLine": "not-a-dict"}), "foreign")


class MergeHubStatuslineTest(unittest.TestCase):
    """케이스 R16~R17."""

    def test_r16_installs_from_none_and_is_idempotent(self) -> None:
        merged_once = hub_settings.merge_hub_statusline({})
        self.assertEqual(hub_settings.statusline_owner(merged_once), "hub")

        merged_twice = hub_settings.merge_hub_statusline(merged_once)
        self.assertEqual(merged_once, merged_twice)

    def test_r16_input_settings_is_not_mutated(self) -> None:
        settings = {"hooks": {}}
        original = copy.deepcopy(settings)
        hub_settings.merge_hub_statusline(settings)
        self.assertEqual(settings, original)

    def test_r17_foreign_statusline_raises_and_original_value_survives(self) -> None:
        foreign_command = {"type": "command", "command": "python3 my_own_statusline.py"}
        settings = {"statusLine": foreign_command}
        with self.assertRaises(hub_settings.HubStatusLineConflictError):
            hub_settings.merge_hub_statusline(settings)
        self.assertEqual(settings["statusLine"], foreign_command)


class StripHubStatuslineTest(unittest.TestCase):
    """케이스 R18 — hooks 키는 어느 경우에도 손대지 않는다."""

    def test_r18_our_statusline_is_removed(self) -> None:
        settings = {
            "hooks": {"Stop": [hub_settings._hub_hook_entry()]},
            "statusLine": {"type": "command", "command": hub_settings.STATUSLINE_COMMAND},
        }
        stripped = hub_settings.strip_hub_statusline(settings)
        self.assertNotIn("statusLine", stripped)
        self.assertEqual(stripped["hooks"], settings["hooks"])

    def test_r18_foreign_statusline_is_preserved(self) -> None:
        foreign_command = {"type": "command", "command": "python3 my_own_statusline.py"}
        settings = {"hooks": {}, "statusLine": foreign_command}
        stripped = hub_settings.strip_hub_statusline(settings)
        self.assertEqual(stripped["statusLine"], foreign_command)

    def test_r18_no_key_is_a_no_op(self) -> None:
        settings = {"hooks": {}}
        stripped = hub_settings.strip_hub_statusline(settings)
        self.assertEqual(stripped, settings)


class InstallStatuslineMissingEntrypointTest(unittest.TestCase):
    """케이스 R18b — hub_statusline.py 가 없으면 settings.json 을 건드리지 않고 거부한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        self.original_entrypoint_path = hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"
        hub_settings.SETTINGS_PATH.write_text(json.dumps({"model": "opus"}))
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH = self.temp_dir / "missing_hub_statusline.py"

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH = self.original_entrypoint_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_r18b_missing_entrypoint_is_rejected_without_touching_settings(self) -> None:
        before = hub_settings.SETTINGS_PATH.read_text()
        result = hub_settings.install_statusline()
        self.assertFalse(result["ok"])
        self.assertIn(str(hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH), result["reason"])
        self.assertEqual(hub_settings.SETTINGS_PATH.read_text(), before)


class InstallStatuslineForeignConflictIoTest(unittest.TestCase):
    """검수 MEDIUM 3 — install_statusline()/uninstall_statusline() 는 merge_hub_statusline·
    strip_hub_statusline(R17·R18) 를 거치지 않고 자체 statusline_owner 검사로 단락하므로,
    이 기능의 최대 안전 주장("남의 statusLine 을 절대 건드리지 않는다")을 순수 함수 테스트만으로는
    보증하지 못한다. I/O 진입점 자체가 foreign 값을 만나면 파일 바이트가 한 글자도 안 바뀌는지
    직접 확인한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        self.original_entrypoint_path = hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH = self.temp_dir / "hub_statusline.py"
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH.write_text("# stub")

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH = self.original_entrypoint_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_install_rejects_foreign_statusline_without_touching_settings(self) -> None:
        foreign_settings = {"model": "opus", "statusLine": {"type": "command", "command": "my-own-script.sh"}}
        hub_settings.SETTINGS_PATH.write_text(json.dumps(foreign_settings))
        before = hub_settings.SETTINGS_PATH.read_text()

        result = hub_settings.install_statusline()

        self.assertFalse(result["ok"])
        self.assertEqual(result["current_command"], foreign_settings["statusLine"])
        self.assertEqual(hub_settings.SETTINGS_PATH.read_text(), before)

    def test_uninstall_preserves_foreign_statusline_without_touching_settings(self) -> None:
        foreign_settings = {"model": "opus", "statusLine": {"type": "command", "command": "my-own-script.sh"}}
        hub_settings.SETTINGS_PATH.write_text(json.dumps(foreign_settings))
        before = hub_settings.SETTINGS_PATH.read_text()

        result = hub_settings.uninstall_statusline()

        self.assertTrue(result["ok"])
        self.assertFalse(result["removed"])
        self.assertEqual(hub_settings.SETTINGS_PATH.read_text(), before)


class InstallHooksIoTest(unittest.TestCase):
    """검수 E-1(AR10) — install_hooks()/uninstall_hooks() 는 merge_hub_hooks·strip_hub_hooks
    (순수 함수)를 부르기 전에 자체 파싱·백업·원자적 교체를 거치므로, 이 기능의 최대 안전 주장
    ("파싱 실패 시 손대지 않는다", "쓰기 전 반드시 백업한다", "멱등 재호출은 파일을 만지지 않는다")은
    순수 함수 테스트만으로는 보증하지 못한다. `InstallStatuslineForeignConflictIoTest` 와 대칭인
    I/O 진입점 테스트를 붙인다 — hooks 쪽은 이벤트 6개 배열이라 statusLine 단일 값보다 스키마
    표면이 넓어 더 위험한데도 이 클래스가 생기기 전에는 `tests/hub` 어디에도 install_hooks·
    uninstall_hooks 라는 이름 자체가 없었다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"
        # 사용자의 실제 ~/.claude/settings.json 을 절대 건드리지 않기 위한 자기 검증.
        self.assertTrue(str(hub_settings.SETTINGS_PATH).startswith(str(self.temp_dir)))

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _backup_paths(self) -> list[Path]:
        return sorted(self.temp_dir.glob("settings.json.bak-*"))

    def test_parse_failure_leaves_file_untouched_for_install_and_uninstall(self) -> None:
        """(a) 파싱 실패 시 무개입 — install_hooks()·uninstall_hooks() 각각."""
        hub_settings.SETTINGS_PATH.write_text("{not json", encoding="utf-8")
        before = hub_settings.SETTINGS_PATH.read_bytes()

        install_result = hub_settings.install_hooks()
        self.assertFalse(install_result["ok"])
        self.assertEqual(install_result["reason"], hub_settings.SETTINGS_PARSE_ERROR)
        self.assertEqual(hub_settings.SETTINGS_PATH.read_bytes(), before)

        uninstall_result = hub_settings.uninstall_hooks()
        self.assertFalse(uninstall_result["ok"])
        self.assertEqual(uninstall_result["reason"], hub_settings.SETTINGS_PARSE_ERROR)
        self.assertEqual(hub_settings.SETTINGS_PATH.read_bytes(), before)

        self.assertEqual(self._backup_paths(), [])

    def test_install_creates_exactly_one_backup_matching_original_bytes(self) -> None:
        """(b) 백업 생성 — 정상 settings.json 으로 install_hooks() 를 부르면 백업 1개, 바이트 동일."""
        original_bytes = json.dumps({"model": "opus"}, ensure_ascii=False).encode("utf-8")
        hub_settings.SETTINGS_PATH.write_bytes(original_bytes)

        result = hub_settings.install_hooks()

        self.assertTrue(result["ok"])
        backups = self._backup_paths()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original_bytes)

    def test_reinstall_is_idempotent_and_creates_no_new_backup(self) -> None:
        """(c) 멱등 경로는 파일을 만지지 않는다 — 재호출은 installed == [] 이고 백업이 늘지 않는다."""
        hub_settings.SETTINGS_PATH.write_bytes(json.dumps({"model": "opus"}).encode("utf-8"))
        first_result = hub_settings.install_hooks()
        self.assertTrue(first_result["ok"])
        self.assertEqual(len(self._backup_paths()), 1)

        second_result = hub_settings.install_hooks()

        self.assertTrue(second_result["ok"])
        self.assertEqual(second_result["installed"], [])
        self.assertEqual(len(self._backup_paths()), 1)


class LoadSettingsTopLevelTypeTest(unittest.TestCase):
    """U-S1(H9) — 최상위가 dict 가 아닌 **유효** JSON(배열·문자열·숫자·null)도 파싱 실패와
    같은 '중단 신호'(None)로 접힌다. 기존에는 json.loads 결과를 무검사 반환해 이 네 입력이
    각자 다른 AttributeError 로 죽었다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_top_level_array_is_none(self) -> None:
        hub_settings.SETTINGS_PATH.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertIsNone(hub_settings._load_settings())

    def test_top_level_string_is_none(self) -> None:
        hub_settings.SETTINGS_PATH.write_text('"just a string"', encoding="utf-8")
        self.assertIsNone(hub_settings._load_settings())

    def test_top_level_number_is_none(self) -> None:
        hub_settings.SETTINGS_PATH.write_text("42", encoding="utf-8")
        self.assertIsNone(hub_settings._load_settings())

    def test_top_level_null_is_none(self) -> None:
        hub_settings.SETTINGS_PATH.write_text("null", encoding="utf-8")
        self.assertIsNone(hub_settings._load_settings())


class InstallUninstallHooksNonDictTopLevelTest(unittest.TestCase):
    """U-S2(H9) — install_hooks()/uninstall_hooks() 는 최상위 비객체 입력에서도
    트레이스백 대신 ok:false + 사유를 내고 파일을 건드리지 않는다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_install_and_uninstall_reject_top_level_array_without_touching_file(self) -> None:
        hub_settings.SETTINGS_PATH.write_text("[1, 2, 3]", encoding="utf-8")
        before = hub_settings.SETTINGS_PATH.read_bytes()

        install_result = hub_settings.install_hooks()
        self.assertFalse(install_result["ok"])
        self.assertEqual(install_result["reason"], hub_settings.SETTINGS_PARSE_ERROR)
        self.assertEqual(hub_settings.SETTINGS_PATH.read_bytes(), before)

        uninstall_result = hub_settings.uninstall_hooks()
        self.assertFalse(uninstall_result["ok"])
        self.assertEqual(uninstall_result["reason"], hub_settings.SETTINGS_PARSE_ERROR)
        self.assertEqual(hub_settings.SETTINGS_PATH.read_bytes(), before)


class StatuslinePathsSurviveNonDictTopLevelTest(unittest.TestCase):
    """U-S3(H9 파급, §9-7) — statusline_owner 도 settings.get(...) 를 부르므로
    install_statusline·uninstall_statusline·statusline_install_status 셋 다 같은
    비객체 최상위 입력에서 트레이스백 없이 살아남아야 한다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        self.original_entrypoint_path = hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"
        hub_settings.SETTINGS_PATH.write_text("[1, 2, 3]", encoding="utf-8")
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH = self.temp_dir / "hub_statusline.py"
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH.write_text("# stub")

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        hub_settings.HUB_STATUSLINE_ENTRYPOINT_PATH = self.original_entrypoint_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_install_statusline_returns_ok_false_with_parse_error_reason(self) -> None:
        result = hub_settings.install_statusline()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], hub_settings.SETTINGS_PARSE_ERROR)

    def test_uninstall_statusline_returns_ok_false_with_parse_error_reason(self) -> None:
        result = hub_settings.uninstall_statusline()
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], hub_settings.SETTINGS_PARSE_ERROR)

    def test_statusline_install_status_returns_false(self) -> None:
        self.assertFalse(hub_settings.statusline_install_status())


class HubHookEntryTimeoutTest(unittest.TestCase):
    """U-S4(N2) — 훅 엔트리에 행(hang) 방어용 timeout 이 실리고, 그 필드가 늘어도
    merge_hub_hooks 의 마커 기반 멱등 판정은 그대로다."""

    def test_entry_has_timeout_matching_module_constant(self) -> None:
        entry = hub_settings._hub_hook_entry()
        self.assertEqual(entry["hooks"][0]["timeout"], hub_settings.HOOK_TIMEOUT_SECONDS)

    def test_merge_hub_hooks_is_still_idempotent_with_timeout_field(self) -> None:
        settings = _settings_with_all_events()
        merged_once = hub_settings.merge_hub_hooks(settings)
        merged_twice = hub_settings.merge_hub_hooks(merged_once)
        self.assertEqual(merged_once, merged_twice)


class WriteSettingsAtomicallyModePreservationTest(unittest.TestCase):
    """검수 n1 — mkstemp 는 새 파일을 0600 으로 만든다. 기존 파일 모드(보통 0644)를
    조용히 바꾸면 안 된다 — 교체 전에 기존 모드를 그대로 옮긴다."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"
        hub_settings.SETTINGS_PATH.write_text(json.dumps({"hooks": {}}))
        hub_settings.SETTINGS_PATH.chmod(0o644)

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_existing_file_mode_is_preserved_after_write(self) -> None:
        before_mode = hub_settings.SETTINGS_PATH.stat().st_mode & 0o777
        hub_settings._write_settings_atomically({"hooks": {"Stop": [hub_settings._hub_hook_entry()]}})
        after_mode = hub_settings.SETTINGS_PATH.stat().st_mode & 0o777
        self.assertEqual(after_mode, before_mode)


class StopFailureHookEventTest(unittest.TestCase):
    """S1~S3 — 결정 RI12(docs/prps/hub-rate-limit-interruption.md). HOOK_EVENTS 확장과
    기존 설치 이행."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_settings_path = hub_settings.SETTINGS_PATH
        hub_settings.SETTINGS_PATH = self.temp_dir / "settings.json"

    def tearDown(self) -> None:
        hub_settings.SETTINGS_PATH = self.original_settings_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_s1_hook_events_has_seven_including_stop_failure(self) -> None:
        self.assertEqual(len(hub_settings.HOOK_EVENTS), 7)
        self.assertEqual(hub_settings.HOOK_EVENTS[-1], "StopFailure")

    def test_s2_reinstalling_over_six_existing_events_only_installs_stop_failure(self) -> None:
        """기존 설치(6개 이벤트)에 `/hub install` 을 다시 실행하면 StopFailure 만 새로
        설치되고, 기존 6개 엔트리는 문자 하나 바뀌지 않는다(멱등 재설치, 결정 RI12)."""
        six_events = tuple(name for name in hub_settings.HOOK_EVENTS if name != "StopFailure")
        existing_hooks = {name: [hub_settings._hub_hook_entry()] for name in six_events}
        hub_settings.SETTINGS_PATH.write_text(json.dumps({"hooks": existing_hooks}), encoding="utf-8")

        result = hub_settings.install_hooks()

        self.assertTrue(result["ok"])
        self.assertEqual(result["installed"], ["StopFailure"])
        self.assertEqual(sorted(result["already_installed"]), sorted(six_events))
        written = json.loads(hub_settings.SETTINGS_PATH.read_text(encoding="utf-8"))
        for name in six_events:
            self.assertEqual(written["hooks"][name], existing_hooks[name])

    def test_s3_uninstall_removes_stop_failure_too(self) -> None:
        installed = {name: [hub_settings._hub_hook_entry()] for name in hub_settings.HOOK_EVENTS}
        hub_settings.SETTINGS_PATH.write_text(json.dumps({"hooks": installed}), encoding="utf-8")

        result = hub_settings.uninstall_hooks()

        self.assertTrue(result["ok"])
        self.assertIn("StopFailure", result["removed"])
        written = json.loads(hub_settings.SETTINGS_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("hooks", written)   # 전부 우리 엔트리였으니 hooks 자체가 사라진다


if __name__ == "__main__":
    unittest.main()
