"""tests/hub/test_hub_template_dom_release_check.py — 헤드리스 Chrome DOM 행동 검사 중 새 릴리스 즉시 확인 신호 4건
(D46~D52, docs/prps/hub-release-check-on-refresh.md 결정 RR1·RR2·RR6).

- D46 서버 모드 페이지 로드가 `/release-check` 를 헤더·no-store 와 함께 1건 보낸다. 204(ok)를 받으면 그 직후 폴링이 뒤따르고,
      거절(403)이면 뒤따르지 않는다.
- D47 새로고침 버튼 클릭은 확인을 한 번 더 요청한다(총 2건). 1분 폴링·포커스·탭 복귀는 요청하지 않는다(U3).
- D48 응답이 끝나지 않는 동안 버튼을 연타해도 요청은 총 1건이다(탭당 진행 중 1건 가드). 새로고침 회전 클래스는 그대로 붙는다.
- D49 `file://` 로 연 허브는 확인을 요청하지 않는다(서버가 없다).
- D50~D52 진행 중 가드는 실패 뒤에도 풀린다 — 403 응답(D50)·네트워크 오류(D51)·성공 핸들러의 동기 예외(D52) 뒤에 새로고침 버튼을 다시
      누르면 신호가 다시 나간다(가드가 풀리지 않으면 그 탭은 새로고침을 닫을 때까지 확인을 못 한다).

공용 하네스(template_dom_harness.py)는 고치지 않는다 — 이 모듈이 사전 스크립트를 확장해 `window.fetch` 를 감싸 호출을 기록하고
`/release-check` 응답만 시나리오별로 바꾼다. Chrome 이 없으면 SKIP. 대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 —
변경 전 템플릿으로 돌려 RED 를 확인하는 용도다. 동시 부하에서 「Teardown watchdog expired」 거짓 실패가 나면 이 모듈만 단독 재실행한다.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)

try:
    from .template_dom_harness import (
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        inject_scripts,
        make_snapshot as _snapshot,
        pre_script,
        run_scenario,
        run_scenario_via_file,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        inject_scripts,
        make_snapshot as _snapshot,
        pre_script,
        run_scenario,
        run_scenario_via_file,
    )

RELEASE_CHECK_PATH = "/release-check"
RELEASE_CHECK_HEADER_NAME = "X-Dzh-Release-Check"

# 사전 스크립트 확장 — window.fetch 를 감싸 모든 호출을 기록하고 `/release-check` 응답만 모드(ok·forbidden·pending·network_error·
# broken_response — 마지막은 성공 핸들러가 `res.ok` 를 읽다 동기로 던지는 경우)로 바꾼다.
# `__callsAfterCheck` 는 `/release-check` 응답이 풀린 직후 마이크로태스크 몇 칸 안에 새로 생긴 fetch 호출이다 — 화면의 후속 폴링은
# 응답 처리 마이크로태스크 안에서 동기로 나간다(1칸). 헤드리스가 자발적으로 내는 focus 폴링은 매크로태스크라 마이크로태스크
# 구간 안에는 끼어들 수 없어, 「확인이 폴링을 뒤따르게 하는가」를 부하와 무관하게 판정할 수 있다(setTimeout 으로 재면 부하 때
# 그 사이에 자발적 폴링이 끼어 거절 시나리오가 거짓 실패했다 — 구현 중 실측).
_FETCH_RECORDER = """
window.__fetchCalls = [];
window.__callsAfterCheck = null;
window.__releaseCheckMode = '%s';
var __harnessFetch = window.fetch;
function __afterMicrotaskHops(hops, callback){
  if(hops === 0){ callback(); return; }
  Promise.resolve().then(function(){ __afterMicrotaskHops(hops - 1, callback); });
}
window.fetch = function(url, init){
  var headers = (init && init.headers) || {};
  window.__fetchCalls.push({url: String(url), header: headers['X-Dzh-Release-Check'] || null, cache: (init && init.cache) || null});
  if(String(url) !== '/release-check') return __harnessFetch.apply(this, arguments);
  if(window.__releaseCheckMode === 'pending') return new Promise(function(){});
  if(window.__releaseCheckMode === 'network_error') return Promise.reject(new TypeError('Failed to fetch'));
  var response = window.__releaseCheckMode === 'forbidden' ? {ok: false, status: 403} : {ok: true, status: 204};
  if(window.__releaseCheckMode === 'broken_response') response = {get ok(){ throw new Error('boom'); }, status: 204};
  return Promise.resolve(response).then(function(res){
    var callCountAtResolve = window.__fetchCalls.length;
    __afterMicrotaskHops(4, function(){
      window.__callsAfterCheck = window.__fetchCalls.slice(callCountAtResolve).map(function(call){ return call.url; });
    });
    return res;
  });
};
"""

_COUNT_RELEASE_CHECKS = """
function countReleaseChecks(){
  return window.__fetchCalls.filter(function(call){ return call.url === '%s'; }).length;
}
""" % RELEASE_CHECK_PATH


def _page(mode: str, probe_body: str) -> str:
    snapshot = _snapshot(())
    rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, snapshot)
    return inject_scripts(rendered, pre_script(snapshot) + _FETCH_RECORDER % mode, _COUNT_RELEASE_CHECKS + probe_body)


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
@unittest.skipUnless(TEMPLATE_PATH.exists(), "템플릿을 찾지 못해 DOM 행동 검사를 건너뜁니다")
class HubReleaseCheckSignalDomTest(unittest.TestCase):
    def test_d46_page_load_sends_one_signal_and_polls_after_an_ok_answer_only(self) -> None:
        probe = """
await __sleep(TRIGGER_SETTLE_MS);
__probeResult({
  calls: window.__fetchCalls, afterCheck: window.__callsAfterCheck, pathname: location.pathname,
  checks: countReleaseChecks()
});
"""
        accepted = run_scenario(_page("ok", probe))
        self.assertEqual(accepted["checks"], 1, "페이지 로드가 확인 신호를 정확히 1건 보내지 않음(D46)")
        signal = next(call for call in accepted["calls"] if call["url"] == RELEASE_CHECK_PATH)
        self.assertEqual(signal["header"], "1", "신호에 헤더가 없음 — 서버가 403 으로 거절한다(D46, RR3)")
        self.assertEqual(signal["cache"], "no-store")
        self.assertEqual(accepted["afterCheck"], [accepted["pathname"]], "204 뒤에 폴링이 뒤따르지 않음(D46, RR6)")

        rejected = run_scenario(_page("forbidden", probe))
        self.assertEqual(rejected["checks"], 1)
        self.assertEqual(rejected["afterCheck"], [], "거절 응답 뒤에도 폴링이 뒤따름(D46, RR6)")

    def test_d47_refresh_button_signals_again_but_polling_focus_and_tab_return_do_not(self) -> None:
        probe = """
await __sleep(TRIGGER_SETTLE_MS);
var afterLoad = countReleaseChecks();
__dispatchClick(document.getElementById('dzh-refresh'));
await __sleep(TRIGGER_SETTLE_MS);
var afterClick = countReleaseChecks();
await __triggerPoll();
window.dispatchEvent(new Event('focus'));
document.dispatchEvent(new Event('visibilitychange'));
await __sleep(TRIGGER_SETTLE_MS);
__probeResult({afterLoad: afterLoad, afterClick: afterClick, afterOthers: countReleaseChecks()});
"""
        result = run_scenario(_page("ok", probe))
        self.assertEqual(result["afterLoad"], 1)
        self.assertEqual(result["afterClick"], 2, "새로고침 버튼이 확인 신호를 보내지 않음(D47, RR1)")
        self.assertEqual(
            result["afterOthers"], 2, "1분 폴링·포커스·탭 복귀가 확인 신호를 보냄 — 창을 오갈 때마다 원격에 묻게 된다(D47, U3)"
        )

    def test_d48_a_pending_signal_blocks_more_signals_and_keeps_the_spin_class(self) -> None:
        probe = """
var refreshButton = document.getElementById('dzh-refresh');
await __sleep(TRIGGER_SETTLE_MS);
__dispatchClick(refreshButton);
__dispatchClick(refreshButton);
__dispatchClick(refreshButton);
await __sleep(TRIGGER_SETTLE_MS);
__probeResult({checks: countReleaseChecks(), isSpinning: refreshButton.classList.contains('refresh-spinning')});
"""
        result = run_scenario(_page("pending", probe))
        self.assertEqual(result["checks"], 1, "응답을 기다리는 중 연타가 요청을 더 보냄(D48, RR6 진행 중 가드)")
        self.assertTrue(result["isSpinning"], "확인 신호가 새로고침 회전 애니메이션을 깼음(D48 회귀)")

    def test_d49_file_mode_never_signals(self) -> None:
        probe = """
await __sleep(TRIGGER_SETTLE_MS);
__probeResult({checks: countReleaseChecks(), protocol: location.protocol});
"""
        result = run_scenario_via_file(_page("ok", probe))
        self.assertEqual(result["protocol"], "file:")
        self.assertEqual(result["checks"], 0, "file:// 모드가 서버 없는 확인 신호를 보냄(D49)")

    def _assert_guard_is_released_after(self, mode: str, label: str) -> None:
        probe = """
await __sleep(TRIGGER_SETTLE_MS);
var afterLoad = countReleaseChecks();
__dispatchClick(document.getElementById('dzh-refresh'));
await __sleep(TRIGGER_SETTLE_MS);
__probeResult({afterLoad: afterLoad, afterClick: countReleaseChecks()});
"""
        result = run_scenario(_page(mode, probe))
        self.assertEqual(result["afterLoad"], 1)
        self.assertEqual(result["afterClick"], 2, f"{label} 뒤 진행 중 가드가 풀리지 않아 새로고침이 신호를 못 보냄(RR6)")

    def test_d50_the_guard_is_released_after_a_rejected_answer(self) -> None:
        self._assert_guard_is_released_after("forbidden", "403 응답")

    def test_d51_the_guard_is_released_after_a_network_error(self) -> None:
        self._assert_guard_is_released_after("network_error", "네트워크 오류")

    def test_d52_the_guard_is_released_even_when_the_success_handler_throws(self) -> None:
        self._assert_guard_is_released_after("broken_response", "성공 핸들러의 동기 예외")


if __name__ == "__main__":
    unittest.main()
