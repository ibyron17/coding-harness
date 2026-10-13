"""tests/hub/test_hub_template_dom_update.py — 헤드리스 Chrome DOM 행동 검사 중 하네스 새 버전 알림 5건
(D38~D42, docs/prps/harness-versioning.md 결정 UN7~UN9).

- D38 알림이 있는 뷰: h1 옆 설치 버전 표기(v1.0.0)와 헤더 알림 버튼(새 버전 1.1.0)이 보이고, 복사·툴팁 문구가 맞다.
      복사 피드백 라벨 둘은 마크업에 있으나 보이지 않는다(CSS 가 하나만 보인다).
- D39 알림이 없는 뷰(최신이거나 설치가 더 새것): 표기만 보이고 버튼은 박스가 없다. 뷰 자체가 없으면(설치 기록 없음) 둘 다 없다.
- D40 도입 이전 설치(설치 버전 모름) + 최신 있음: 표기는 숨고 버튼은 뜬다.
- D41 폴링이 뷰를 바꾸면(알림 생김 → 사라짐) 정적 노드가 그대로 갱신된다. 복사 피드백 상태는 폴링 재렌더가 지우지 않는다(UN8).
- D42 복사: 성공이면 /harness-update 가 클립보드로 가고 「복사됨」 라벨이 2초 뒤 되돌아온다, 거부·미지원이면 「입력하세요」 라벨이
      뜬다. file:// 모드에서도 동작한다(UN9 — 복사 IIFE 는 isServed 가드 바깥).

Chrome 이 없으면 SKIP. 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 — 변경 전 템플릿으로 돌려 RED 를 확인하는 용도다.
"""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)
import hub_release  # noqa: E402

try:
    from .template_dom_harness import (
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        inject_scripts,
        make_snapshot as _snapshot,
        minimal_data_document,
        pre_script,
        run_scenario,
        run_scenario_via_file,
        safe_js_string_literal,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        inject_scripts,
        make_snapshot as _snapshot,
        minimal_data_document,
        pre_script,
        run_scenario,
        run_scenario_via_file,
        safe_js_string_literal,
    )

UPDATE_COMMAND = "/harness-update"
COPY_FEEDBACK_WAIT_MS = 2100     # 템플릿의 UPDATE_COPY_FEEDBACK_MS(2000) 보다 조금 길게


def _view(installed: str = "1.0.0", latest: str = "1.1.0", available: bool = True) -> hub_release.HarnessVersionView:
    return hub_release.HarnessVersionView(
        installed_version=installed, installed_commit_short="abcdef1" if installed else "",
        installed_at="2026-10-13T05:00:00Z", latest_version=latest, is_update_available=available,
    )


def _snapshot_with(view: hub_release.HarnessVersionView | None, warnings: tuple[str, ...] = ()) -> hub_model.HubSnapshot:
    return dataclasses.replace(_snapshot((), warnings), harness_version=view)


def _page(snapshot: hub_model.HubSnapshot, probe_body: str, poll_snapshot: hub_model.HubSnapshot | None = None) -> str:
    rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, snapshot)
    return inject_scripts(rendered, pre_script(poll_snapshot), probe_body)


# 두 정적 노드의 상태를 읽는다. 「보인다」는 hidden 속성이 아니라 실제 박스(폭 > 0)로 판정한다 —
# [hidden] 이 CSS display 에 져서 안 숨는 결함(.update-btn 이 inline-flex)을 잡으려는 것이다.
_READ_PROBE = """
function readNodes(){
  var version = document.getElementById('dzh-harness-version');
  var update = document.getElementById('dzh-update');
  var label = update.querySelector('.update-label');
  var visibleLabelClasses = Array.prototype.filter.call(update.children, function(el){
    return getComputedStyle(el).display !== 'none';
  }).map(function(el){ return el.className; });
  return {
    versionHidden: version.hidden, versionBoxWidth: version.getBoundingClientRect().width,
    versionText: version.textContent, versionTooltip: version.getAttribute('data-tooltip'),
    updateHidden: update.hidden, updateBoxWidth: update.getBoundingClientRect().width,
    updateLabel: label.textContent, updateAria: update.getAttribute('aria-label'),
    updateTooltip: update.getAttribute('data-tooltip'), updateClass: update.className,
    visibleLabelClasses: visibleLabelClasses,
    visibleLabelText: Array.prototype.filter.call(update.children, function(el){
      return getComputedStyle(el).display !== 'none';
    }).map(function(el){ return el.textContent; }).join('|'),
    inTopActions: !!update.closest('.top-actions') && update.parentElement.firstElementChild === update,
    nextToTitle: version.previousElementSibling && version.previousElementSibling.tagName === 'H1'
  };
}
__probeResult({nodes: readNodes()});
"""


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HarnessUpdateDomTest(unittest.TestCase):
    """하네스 버전 표기·새 버전 알림의 행동 계약 — 근거는 PRP 결정 UN7·UN8·UN9."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def _nodes(self, view: hub_release.HarnessVersionView | None) -> dict:
        return run_scenario(_page(_snapshot_with(view), _READ_PROBE), window_width=1440, window_height=900)["nodes"]

    def test_d38_new_release_shows_the_version_label_and_the_update_button(self) -> None:
        nodes = self._nodes(_view())
        self.assertFalse(nodes["versionHidden"], "설치 버전 표기가 hidden(D38, UN7)")
        self.assertEqual(nodes["versionText"], "v1.0.0")
        self.assertTrue(nodes["nextToTitle"], "설치 버전 표기가 h1 바로 옆이 아님(D38, UN7)")
        self.assertIn("abcdef1", nodes["versionTooltip"], "표기 툴팁에 짧은 해시가 없음(D38, HV4 — 릴리스 사이 설치본 구별)")
        self.assertIn("1.0.0", nodes["versionTooltip"])
        self.assertFalse(nodes["updateHidden"], "새 버전이 있는데 알림 버튼이 hidden(D38, UN7)")
        self.assertGreater(nodes["updateBoxWidth"], 0, "알림 버튼 박스가 없음(D38 — [hidden] 이 CSS display 에 짐)")
        self.assertEqual(nodes["updateLabel"], "새 버전 1.1.0")
        self.assertTrue(nodes["inTopActions"], "알림 버튼이 .top-actions 맨 앞이 아님(D38, UN7)")
        self.assertEqual(nodes["visibleLabelClasses"], ["update-label"], "기본 상태에서 복사 피드백 라벨이 같이 보임(D38, UN8)")
        self.assertIn("1.0.0", nodes["updateTooltip"])
        self.assertIn("1.1.0", nodes["updateTooltip"])
        self.assertIn(UPDATE_COMMAND, nodes["updateTooltip"], "툴팁에 복사될 명령이 없음(D38, R10)")
        self.assertIn("1.1.0", nodes["updateAria"])

    def test_d39_no_alert_shows_only_the_label_and_no_view_shows_nothing(self) -> None:
        up_to_date = self._nodes(_view(latest="1.0.0", available=False))
        self.assertFalse(up_to_date["versionHidden"])
        self.assertEqual(up_to_date["versionText"], "v1.0.0")
        self.assertTrue(up_to_date["updateHidden"], "알림이 없는데 버튼이 hidden 이 아님(D39)")
        self.assertEqual(up_to_date["updateBoxWidth"], 0, "알림이 없는데 버튼 박스가 남음(D39 — [hidden] 이 CSS display 에 짐)")
        no_view = self._nodes(None)
        self.assertTrue(no_view["versionHidden"], "설치 기록이 없는데 버전 표기가 보임(D39, UN7)")
        self.assertEqual(no_view["versionBoxWidth"], 0)
        self.assertTrue(no_view["updateHidden"])
        self.assertEqual(no_view["updateBoxWidth"], 0)

    def test_d40_pre_versioning_install_hides_the_label_but_still_alerts(self) -> None:
        nodes = self._nodes(_view(installed=""))
        self.assertTrue(nodes["versionHidden"], "버전을 모르는 설치에 v 만 남은 표기가 보임(D40)")
        self.assertFalse(nodes["updateHidden"], "도입 이전 설치인데 알림이 안 뜸(D40, UN3)")
        self.assertEqual(nodes["updateLabel"], "새 버전 1.1.0")
        self.assertIn("1.1.0", nodes["updateTooltip"])

    def test_d41_polling_updates_the_static_nodes_and_keeps_the_copy_feedback(self) -> None:
        # 처음엔 알림 없음 → 폴링이 알림을 가져옴 → 버튼이 뜬다(정적 노드 속성 갱신). 클릭해 피드백 클래스가 붙은 뒤
        # 폴링이 한 번 더 렌더해도(내용이 바뀐 스냅샷) 피드백 클래스를 지우지 않는다. 마지막 폴링이 알림을 걷으면 버튼이 사라진다.
        # 페이지 로드가 poll() 을 먼저 한 번 조용히 돌릴 수 있다(하네스 PROBE_PRELUDE 주석) — 그래서 응답은 처음부터
        # 「알림 없음」으로 두고, 프로브가 응답 문자열을 바꾼 뒤에만 알림이 나오게 한다.
        probe = _READ_PROBE.replace("__probeResult({nodes: readNodes()});", "") + """
var initial = readNodes();
Object.defineProperty(navigator, 'clipboard', {value: {writeText: function(){ return Promise.resolve(); }}, configurable: true});
window.__mockFetchResponseText = window.__alertText;
__invokeIntervalByDelay(60000);
await __sleep(TRIGGER_SETTLE_MS);
var afterAlert = readNodes();
__dispatchClick(document.getElementById('dzh-update'));
await __sleep(60);
var clicked = readNodes();
window.__mockFetchResponseText = window.__stillAlertText;
__invokeIntervalByDelay(60000);
await __sleep(TRIGGER_SETTLE_MS);
var afterSecondPoll = readNodes();
window.__mockFetchResponseText = window.__retractedText;
__invokeIntervalByDelay(60000);
await __sleep(TRIGGER_SETTLE_MS);
var afterRetract = readNodes();
__probeResult({initial: initial, afterAlert: afterAlert, clicked: clicked, afterSecondPoll: afterSecondPoll, afterRetract: afterRetract});
"""
        initial = _snapshot_with(_view(latest="1.0.0", available=False))
        poll_snapshots = {
            "__alertText": _snapshot_with(_view(), warnings=("두 번째 렌더를 강제하는 경고 1",)),
            "__stillAlertText": _snapshot_with(_view(), warnings=("두 번째 렌더를 강제하는 경고 2",)),
            "__retractedText": _snapshot_with(_view(installed="1.1.0", latest="1.1.0", available=False), warnings=("경고 3",)),
        }
        assignments = "".join(
            f"\nwindow.{name} = {safe_js_string_literal(minimal_data_document(snapshot))};"
            for name, snapshot in poll_snapshots.items()
        )
        page = inject_scripts(hub_model.render_hub_html(_TEMPLATE_TEXT, initial), pre_script(initial) + assignments, probe)
        result = run_scenario(page, window_width=1440, window_height=900)
        self.assertTrue(result["initial"]["updateHidden"])
        self.assertFalse(result["afterAlert"]["updateHidden"], "폴링이 가져온 알림이 버튼에 반영되지 않음(D41, UN8)")
        self.assertEqual(result["afterAlert"]["updateLabel"], "새 버전 1.1.0")
        self.assertIn("update-btn-copied", result["clicked"]["updateClass"], "클릭 뒤 복사됨 클래스가 안 붙음(D41 사전조건)")
        self.assertIn("update-btn-copied", result["afterSecondPoll"]["updateClass"], "폴링 재렌더가 복사 피드백 클래스를 지움(D41, UN8)")
        self.assertTrue(result["afterRetract"]["updateHidden"], "알림이 걷힌 뒤에도 버튼이 남음(D41, UN8)")
        self.assertEqual(result["afterRetract"]["versionText"], "v1.1.0", "/harness-update 직후 표기가 갱신되지 않음(D41)")

    def _click_probe(self, clipboard_setup_js: str) -> str:
        return _READ_PROBE.replace("__probeResult({nodes: readNodes()});", "") + clipboard_setup_js + """
window.__copied = null;
var before = readNodes();
__dispatchClick(document.getElementById('dzh-update'));
await __sleep(60);
var clicked = readNodes();
await __sleep(%d);
var settled = readNodes();
__probeResult({before: before, clicked: clicked, settled: settled, copied: window.__copied});
""" % COPY_FEEDBACK_WAIT_MS

    def test_d42_click_copies_the_command_and_shows_then_reverts_the_feedback(self) -> None:
        probe = self._click_probe(
            "Object.defineProperty(navigator, 'clipboard', {value: {writeText: function(text){ window.__copied = text; return Promise.resolve(); }}, configurable: true});"
        )
        result = run_scenario(_page(_snapshot_with(_view()), probe), window_width=1440, window_height=900)
        self.assertEqual(result["copied"], UPDATE_COMMAND, "복사된 문자열이 /harness-update 가 아님(D42)")
        self.assertIn("update-btn-copied", result["clicked"]["updateClass"])
        self.assertEqual(result["clicked"]["visibleLabelClasses"], ["update-label-copied"], "복사 뒤 보이는 라벨이 하나가 아님(D42, UN8)")
        self.assertEqual(result["clicked"]["visibleLabelText"], "복사됨 · /harness-update")
        self.assertNotIn("update-btn-copied", result["settled"]["updateClass"], "복사됨 표시가 2초 뒤에도 남음(D42)")
        self.assertEqual(result["settled"]["visibleLabelClasses"], ["update-label"])

    def test_d42_denied_or_missing_clipboard_asks_the_user_to_type_the_command(self) -> None:
        for case, setup in (
            ("거부", "Object.defineProperty(navigator, 'clipboard', {value: {writeText: function(){ return Promise.reject(new Error('denied')); }}, configurable: true});"),
            ("미지원", "Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true});"),
        ):
            with self.subTest(case=case):
                result = run_scenario(_page(_snapshot_with(_view()), self._click_probe(setup)), window_width=1440, window_height=900)
                self.assertIn("update-btn-copy-failed", result["clicked"]["updateClass"], f"클립보드 {case} 인데 실패 표시가 없음(D42, R10)")
                self.assertEqual(result["clicked"]["visibleLabelText"], "/harness-update 를 입력하세요")
                self.assertNotIn("update-btn-copy-failed", result["settled"]["updateClass"])

    def test_d42_copy_works_in_file_mode_where_the_render_iife_returns_early(self) -> None:
        # UN9 — 복사 IIFE 를 렌더 IIFE 의 `if(!isServed){ … return; }` 뒤에 두면 file:// 에서 조용히 죽는다.
        probe = self._click_probe(
            "Object.defineProperty(navigator, 'clipboard', {value: {writeText: function(text){ window.__copied = text; return Promise.resolve(); }}, configurable: true});"
        )
        result = run_scenario_via_file(_page(_snapshot_with(_view()), probe), window_width=1440, window_height=900)
        self.assertEqual(result["copied"], UPDATE_COMMAND, "file:// 모드에서 복사가 동작하지 않음(D42, UN9)")
        self.assertFalse(result["before"]["updateHidden"], "file:// 모드에서 알림 버튼이 안 그려짐(D42)")


if __name__ == "__main__":
    unittest.main()
