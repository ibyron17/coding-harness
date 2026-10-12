"""tests/hub/test_hub_template_dom_usage.py — 헤드리스 Chrome DOM 행동 검사 중 사용량 패널의 계정 줄 5건
(D33~D37, docs/prps/hub-usage-panel-account.md §11.3, 결정 AC2·AC5·AC6).

- D33 신선 usage + 계정 3값: 계정 줄이 갱신 문구(.usage-meta) 뒤에 있고, 이름 순서는 요금제/조직/이메일이며,
      값은 글자 그대로(조직 이름의 `<img onerror>` 가 요소로 해석되지 않는다). 30초 틱 뒤에도 남는다(두 번째 호출부).
- D34 usage 없음 + 계정 있음: 패널이 hidden 이다(계정만으로 패널이 뜨지 않는다).
- D35 값 일부 없음 / 계정 없음: 그 쌍만 빠지고, 셋 다 없거나 계정이 없으면 목록 자체가 없다.
- D36 320px 화면(패널 폭 288px): 긴 이메일이 줄바꿈되고 패널이 가로로 넘치지 않으며, 접힘 요약은 그대로고 접히면 계정 줄이 안 보인다.
- D37 만료 usage + 계정: 계정 줄이 만료 안내(.usage-stale-note) 뒤에 있다.

실제 이메일·조직 이름은 쓰지 않는다 — 합성 값만. Chrome 이 없으면 SKIP. 대상 템플릿은 DZH_DOM_TEST_TEMPLATE
환경변수로 바꿀 수 있다 — 변경 전 템플릿으로 돌려 이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다.
"""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_account  # noqa: E402  (sys.path 조정 후 임포트 — AccountInfo 픽스처용)
import hub_usage  # noqa: E402  (UsageSample 픽스처용)

try:
    from .template_dom_harness import (
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        make_snapshot as _snapshot,
        run_scenario,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _make_page,
        make_snapshot as _snapshot,
        run_scenario,
    )

_MS_PER_MINUTE = 60000
# 헤드리스 Chrome 은 창 폭을 500px 밑으로 줄이지 못한다(실측 innerWidth=500). 패널 폭은 min(420px, 100vw - 32px) 라
# 320px 화면에서는 288px 이다 — 그 폭을 패널에 직접 지정해 최소 폭 상황을 재현한다(줄바꿈 규칙은 패널 폭에만 달렸다).
_NARROW_PANEL_WIDTH_PX = 288
_NARROW_PANEL_SETUP = "document.getElementById('dzh-usage').style.width = '%dpx';" % _NARROW_PANEL_WIDTH_PX
_LONG_EMAIL_LOCAL_PART_CHARS = 200     # 256자 상한 안의 긴 이메일 — 공백이 없어 줄바꿈 규칙이 없으면 패널을 밀어낸다
_EXPECTED_TERMS = ["요금제", "조직", "이메일"]
_SYNTHETIC_EMAIL = "dev.user@example.com"
_SYNTHETIC_ORGANIZATION = "Example Labs"
_HOSTILE_ORGANIZATION = "Example <img src=x onerror=window.__xssFired=1> Labs"
_FRESH_USAGE = hub_usage.UsageSample(sampled_at_ms=BASE_TIME_MS - 4 * _MS_PER_MINUTE, session_percent=43, weekly_percent=71)
_STALE_USAGE = dataclasses.replace(_FRESH_USAGE, is_stale=True)
_SUMMARY_TEXT = "세션 43% · 주간 71%"


def _account(organization: str | None = _SYNTHETIC_ORGANIZATION, email: str | None = _SYNTHETIC_EMAIL,
             plan: str | None = "Claude Team") -> hub_account.AccountInfo:
    return hub_account.AccountInfo(plan_label=plan, organization_name=organization, email=email)


def _usage_snapshot(usage, account):
    return dataclasses.replace(_snapshot(()), usage=usage, account=account)


# 패널 본문의 계정 줄 상태를 읽는다. 채우는 자리는 없다 — 시나리오가 다른 것은 스냅샷뿐이다.
_PANEL_PROBE = """
__SETUP__
function readPanel(){
  var usage = document.getElementById('dzh-usage');
  var body = document.getElementById('dzh-usage-body');
  var account = body.querySelector('.usage-account');
  var childClasses = Array.prototype.map.call(body.children, function(el){ return el.className; });
  return {
    hidden: usage.hidden,
    hasAccount: !!account,
    childClasses: childClasses,
    accountIsLast: !!account && body.lastElementChild === account,
    terms: Array.prototype.map.call(body.querySelectorAll('.usage-account dt'), function(el){ return el.textContent; }),
    values: Array.prototype.map.call(body.querySelectorAll('.usage-account dd'), function(el){ return el.textContent; }),
    imgCount: body.querySelectorAll('img').length,
    xssFired: window.__xssFired === 1,
    summary: document.getElementById('dzh-usage-summary').textContent,
    scrollWidth: usage.scrollWidth, clientWidth: usage.clientWidth,
    rightEdge: usage.getBoundingClientRect().right, innerWidth: window.innerWidth,
    accountBoxHeight: account ? account.getBoundingClientRect().height : null
  };
}
var before = readPanel();
await __fireTick();
var afterTick = readPanel();
if(!before.hidden){
  __dispatchClick(document.getElementById('dzh-usage-toggle'));
  await __sleep(30);
}
var collapsed = readPanel();
__probeResult({before: before, afterTick: afterTick, collapsed: collapsed});
"""


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class UsageAccountDomTest(unittest.TestCase):
    """사용량 패널 계정 줄의 행동 계약 — 근거는 PRP 결정 AC2·AC5·AC6."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def _run(self, snapshot, setup_js: str = "") -> dict:
        probe_body = _PANEL_PROBE.replace("__SETUP__", setup_js)
        return run_scenario(_make_page(snapshot, probe_body), window_width=1440, window_height=900)

    def test_d33_account_lines_follow_the_meta_line_and_render_values_as_plain_text(self) -> None:
        # 결정 AC5·AC6 — 계정 줄은 본문 맨 아래(갱신 문구 뒤)이고 dl/dt/dd 이름-값 쌍이다. 값은 escapeHtml 을 거쳐 글자 그대로 보인다.
        result = self._run(_usage_snapshot(_FRESH_USAGE, _account(organization=_HOSTILE_ORGANIZATION)))
        before = result["before"]
        self.assertFalse(before["hidden"], "usage 가 있는데 패널이 hidden(D33 사전조건)")
        self.assertTrue(before["hasAccount"], "계정 줄이 없음(D33, AC5)")
        self.assertEqual(before["terms"], _EXPECTED_TERMS, "이름 순서가 요금제/조직/이메일이 아님(D33, AC5)")
        self.assertEqual(before["values"], ["Claude Team", _HOSTILE_ORGANIZATION, _SYNTHETIC_EMAIL], "값이 원문과 다름(D33, AC6)")
        self.assertEqual(before["imgCount"], 0, "조직 이름의 <img> 가 요소로 해석됨(D33, AC6 — XSS)")
        self.assertFalse(before["xssFired"], "조직 이름의 onerror 가 실행됨(D33, AC6 — XSS)")
        self.assertTrue(before["accountIsLast"], "계정 줄이 본문 맨 아래가 아님(D33, AC5)")
        self.assertEqual(before["childClasses"], ["usage-row", "usage-bar", "usage-row", "usage-bar", "usage-meta", "usage-account"],
                         "본문 순서가 막대 → 갱신 문구 → 계정 줄이 아님(D33, AC5)")

    def test_d33_account_lines_survive_the_thirty_second_tick(self) -> None:
        # GOTCHA 3 — renderUsagePanel 호출부는 둘이다(폴링 렌더·30초 틱). 틱 쪽이 세 번째 인자를 빠뜨리면 30초 뒤 계정 줄이 사라진다.
        result = self._run(_usage_snapshot(_FRESH_USAGE, _account()))
        self.assertTrue(result["afterTick"]["hasAccount"], "30초 틱 뒤 계정 줄이 사라짐(D33, 두 번째 호출부)")
        self.assertEqual(result["afterTick"]["values"], ["Claude Team", _SYNTHETIC_ORGANIZATION, _SYNTHETIC_EMAIL])

    def test_d34_account_alone_never_opens_the_panel(self) -> None:
        # 결정 AC2 — 패널을 띄우는 조건은 usage 하나다(계정은 장식). usage 없이 계정만 있어도 패널은 숨겨진다.
        result = self._run(_usage_snapshot(None, _account()))
        self.assertTrue(result["before"]["hidden"], "usage 없는데 계정만으로 패널이 뜸(D34, AC2)")
        self.assertFalse(result["before"]["hasAccount"], "숨겨진 패널 본문에 계정 줄이 그려짐(D34, AC2)")

    def test_d35_missing_values_drop_only_their_own_pair(self) -> None:
        # 결정 AC6 — 일부 값만 있으면 그 쌍만 생략, 셋 다 없거나 계정이 없으면 dl 자체가 없다(빈 목록을 접근성 트리에 남기지 않는다).
        without_plan = self._run(_usage_snapshot(_FRESH_USAGE, _account(plan=None)))["before"]
        self.assertEqual(without_plan["terms"], ["조직", "이메일"], "요금제가 없는데 쌍이 남거나 다른 쌍이 빠짐(D35)")
        self.assertEqual(without_plan["values"], [_SYNTHETIC_ORGANIZATION, _SYNTHETIC_EMAIL])
        email_only = self._run(_usage_snapshot(_FRESH_USAGE, _account(plan=None, organization=None)))["before"]
        self.assertEqual(email_only["terms"], ["이메일"], "이메일만 있는 계정이 한 쌍이 아님(D35)")
        for label, account in (("계정 없음", None), ("세 값 모두 없음", _account(plan=None, organization=None, email=None))):
            with self.subTest(case=label):
                report = self._run(_usage_snapshot(_FRESH_USAGE, account))["before"]
                self.assertFalse(report["hasAccount"], f".usage-account 가 남음(D35 — {label})")
                self.assertFalse(report["hidden"], f"계정이 없다고 패널이 숨겨짐(D35 — {label}, AC2)")

    def test_d36_long_email_wraps_inside_a_320px_panel_and_collapsed_state_hides_the_account(self) -> None:
        # 결정 AC4·AC5 — 긴 이메일은 말줄임 없이 줄바꿈되고 패널이 가로로 넘치지 않는다(grid 칸의 minmax(0,1fr) + overflow-wrap:anywhere).
        # 접힘 요약은 계정과 무관하게 그대로고, 접히면 계정 줄은 박스가 없다 — 이메일은 펼쳤을 때만 보인다.
        long_email = "a" * _LONG_EMAIL_LOCAL_PART_CHARS + "@example.com"
        result = self._run(_usage_snapshot(_FRESH_USAGE, _account(email=long_email)), setup_js=_NARROW_PANEL_SETUP)
        expanded = result["before"]
        self.assertLessEqual(expanded["clientWidth"], _NARROW_PANEL_WIDTH_PX, "패널이 288px 로 줄지 않음(D36 사전조건)")
        self.assertEqual(expanded["values"][2], long_email, "긴 이메일이 말줄임·절단됨(D36, AC4)")
        self.assertLessEqual(expanded["scrollWidth"], expanded["clientWidth"], "긴 이메일이 패널을 가로로 넘치게 함(D36, AC4)")
        collapsed = result["collapsed"]
        self.assertEqual(collapsed["summary"], _SUMMARY_TEXT, "접힘 요약이 바뀜(D36, AC5 — 접힘 요약은 불변)")
        self.assertEqual(collapsed["accountBoxHeight"], 0, "접힌 상태에서 계정 줄이 보임(D36, AC5 — 이메일은 펼쳤을 때만)")

    def test_d37_account_lines_follow_the_stale_note_when_the_usage_is_expired(self) -> None:
        # 결정 AC2 — 만료(조회되지 않음)여도 패널은 있으므로 계정 줄도 있다. 위치는 만료 안내 뒤(본문 맨 아래).
        result = self._run(_usage_snapshot(_STALE_USAGE, _account()))
        before = result["before"]
        self.assertFalse(before["hidden"], "만료 usage 에서 패널이 hidden(D37 사전조건)")
        self.assertTrue(before["hasAccount"], "만료 패널에 계정 줄이 없음(D37, AC2)")
        self.assertEqual(before["childClasses"][-2:], ["usage-meta usage-stale-note", "usage-account"],
                         "계정 줄이 만료 안내 뒤 맨 아래가 아님(D37, AC5)")


if __name__ == "__main__":
    unittest.main()
