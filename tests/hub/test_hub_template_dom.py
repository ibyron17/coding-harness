"""tests/hub/test_hub_template_dom.py — 헤드리스 Chrome DOM 행동 검사 중 M1(부분 갱신,
D1~D7, 승인 2, 결정 PU9, docs/prps/hub-session-modal-and-partial-update.md §10.3).

grep 가드(tests/run.sh 의 T25 구역)는 "맞대기를 부른다"까지만 증명한다 — "노드가 살아남는다"는
브라우저에서만 보인다. 설계 단계 실측(§2.2)의 방법을 그대로 자동 검사로 옮긴다: fetch·
setInterval·Date.now 를 가로챈 사전 스크립트를 <body> 직후에, 시나리오를 실행하고 결과를
<pre id="probe-result"> 에 JSON 으로 남기는 프로브를 </body> 앞에 끼운 사본을 헤드리스
Chrome(--dump-dom)으로 연다. Chrome 탐색·서버·사전 스크립트·프로브·픽스처 빌더 등 시나리오와
무관한 공용 하네스는 template_dom_harness.py 로 옮겨졌다(구현 단계 개정(2026-09-24) — M1 하나였던
이 파일에 M2(카드 상세보기, D8~D17)를 더하면 800줄 상한을 넘는다). M2 시나리오는
test_hub_template_dom_modal.py 를 볼 것.

Chrome 이 없으면 SKIP(사유 출력) — 이 저장소의 개발 머신(macOS + Chrome)에서는 항상 돈다.
대상 템플릿은 DZH_DOM_TEST_TEMPLATE 환경변수로 바꿀 수 있다 — 구현자가 변경 전 템플릿으로
돌려 이 모듈의 시나리오가 실패함(RED)을 확인하는 용도다(§2.2 가 그 예고편).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)
import hub_session  # noqa: E402

# 패키지 문맥(python3 -m unittest discover)과 파일 직접 실행 둘 다에서 임포트되게 한다 —
# 이 파일 맨 아래 unittest.main() 진입점이 이미 후자를 지원하고 있었다(tests/hub/test_hub_hook.py
# 의 관례).
try:
    from .template_dom_harness import (
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _fresh_page_for_snapshot,
        inject_scripts as _inject_scripts,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document as _minimal_data_document,
        pre_script as _pre_script,
        run_scenario,
        safe_js_string_literal as _safe_js_string_literal,
    )
except ImportError:  # 파일을 직접 실행한 경로(패키지 문맥이 없다)
    from template_dom_harness import (  # noqa: E402
        BASE_TIME_MS,
        CHROME_PATH,
        SKIP_REASON as _SKIP_REASON,
        TEMPLATE_PATH,
        TEMPLATE_TEXT as _TEMPLATE_TEXT,
        fresh_page_for_snapshot as _fresh_page_for_snapshot,
        inject_scripts as _inject_scripts,
        make_project as _project,
        make_session as _session,
        make_snapshot as _snapshot,
        minimal_data_document as _minimal_data_document,
        pre_script as _pre_script,
        run_scenario,
        safe_js_string_literal as _safe_js_string_literal,
    )


def _make_page(pre_script_text: str, probe_body: str) -> str:
    """실제 템플릿을 스냅샷 A 로 굽고 사전 스크립트·프로브를 끼운다(_inject_scripts 로 위임 —
    D7c 처럼 이미 특수하게 만든 사본에 끼울 때는 _inject_scripts 를 직접 쓴다)."""
    rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, _SCENARIO_SNAPSHOT_A)
    return _inject_scripts(rendered, pre_script_text, probe_body)


# 시나리오 공통 스냅샷 A — coding-harness(3세션, 상태 뒤집힐 예정) + atlas(1세션, 참조용). 발췌를
# 채워 세션 줄을 카드 높이(약 150~228px)보다 키운다 — D1 의 "보던 줄의 화면 위치 유지"
# 단언(§10.3 표)은 세션 칸이 실제로 스크롤돼야만(브라우저 스크롤 앵커링, PU2 보너스) 뜻이
# 있는데, 발췌 없는 최소 세션 3개는 칸을 넘치지 않아 그 전제 자체가 성립하지 않았다
# (구현 중 실측 — 그 상태에서는 재정렬로 줄이 실제로 한 칸 밀려나는 것 자체가 정상이라
# screenTopDelta 단언이 가짜로 실패했다).
_SESSION_EXCERPT = "발췌 텍스트를 충분히 길게 채워 세션 줄 높이를 늘린다 — 카드 안 세션 칸이 실제로 넘쳐야 스크롤 앵커링을 관찰할 수 있다."
_SESSION_S1 = _session("s1", "idle", "idle", BASE_TIME_MS - 5 * 60000, task_excerpt=_SESSION_EXCERPT)
_SESSION_S2 = _session("s2", "working", "working", BASE_TIME_MS - 1 * 60000, task_excerpt=_SESSION_EXCERPT)
_SESSION_S3 = _session(
    "s3", "idle", "idle", BASE_TIME_MS - 9 * 60000,
    dashboard_key="cafe0000cafe0000", task_excerpt=_SESSION_EXCERPT,
)
_SESSION_ATLAS = _session("k1", "idle", "idle", BASE_TIME_MS - 20 * 60000)
_SCENARIO_SNAPSHOT_A = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "working", (_SESSION_S1, _SESSION_S2, _SESSION_S3)),
    _project("/repo/atlas", "atlas", "idle", (_SESSION_ATLAS,)),
))
# 스냅샷 B — 정렬이 뒤집힌다: s2(working→idle) · s1(idle→working). §2.2 가 재현한 실측 조건.
_SCENARIO_SNAPSHOT_B_REORDERED = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "working", (
        _session("s1", "working", "working", BASE_TIME_MS + 60000, task_excerpt=_SESSION_EXCERPT),
        _session("s2", "idle", "idle", BASE_TIME_MS - 1 * 60000, task_excerpt=_SESSION_EXCERPT),
        _SESSION_S3,
    )),
    _project("/repo/atlas", "atlas", "idle", (_SESSION_ATLAS,)),
))

# D-BW1 전용 스냅샷(결정 BW5·BW9·BW10, docs/prps/hub-subagent-background-pause.md §8.2) —
# background 세션 1개 + working·idle 세션이 섞인 카드(coding-harness, 순서 검증용 ④)와
# background+idle 만 있는 카드(atlas, working 없음 — 프로젝트 배지·card-working 부재
# 검증용 ②·③). 각 카드 안 세션은 일부러 상태 우선순위와 반대로 늘어놓는다 — 렌더 순서가
# compareSessionsForDisplay 의 실제 정렬 결과임을 증명한다(입력 순서를 그대로 베끼면
# 아무것도 증명하지 못한다).
_BACKGROUND_WAIT = hub_session.BackgroundWait(
    since_ms=BASE_TIME_MS - 20 * 60000, until_ms=BASE_TIME_MS - 20 * 60000 + 90 * 60000,
    task_count=2, wakeup_count=0,
)
_SCENARIO_SNAPSHOT_BACKGROUND = _snapshot((
    _project("/repo/coding-harness", "coding-harness", "working", (
        _session("bg-idle-sibling", "idle", "idle", BASE_TIME_MS - 25 * 60000),
        _session("bg1", "background", "idle", BASE_TIME_MS - 20 * 60000, background_wait=_BACKGROUND_WAIT),
        _session("w1", "working", "working", BASE_TIME_MS - 1 * 60000),
    )),
    _project("/repo/atlas", "atlas", "background", (
        _session("k-idle", "idle", "idle", BASE_TIME_MS - 30 * 60000),
        _session("bg2", "background", "idle", BASE_TIME_MS - 5 * 60000, background_wait=_BACKGROUND_WAIT),
    )),
))


@unittest.skipUnless(CHROME_PATH, _SKIP_REASON)
class HubTemplateDomTest(unittest.TestCase):
    """D1~D7(§10.3) — 부분 갱신(PU1~PU6)이 노드 동일성·스크롤·포커스·툴팁을 지키는지."""

    def setUp(self) -> None:
        if not _TEMPLATE_TEXT:
            self.skipTest(f"템플릿을 찾지 못함: {TEMPLATE_PATH}")

    def test_d1_poll_with_reorder_preserves_card_session_and_focus(self) -> None:
        # 폴링 대상 스냅샷은 _pre_script(스냅샷) 으로 페이지 로드 시점부터 미리 장전해 두지
        # 않는다 — 헤드리스 dump-dom 은 사람 조작 없이도 poll() 을 한 번 조용히 먼저 돌릴
        # 때가 있고(실측), 그 우연한 첫 호출이 이미 목표 스냅샷을 lastHtml 에 채워 버리면
        # 내가 트리거하는 두 번째 호출은 poll() 의 "내용 같으면 다시 안 그린다" 최적화에
        # 걸려 아무 일도 안 한다 — 그 사이 카드가 우연히 이미 한 번 바뀐 뒤였을 뿐인데
        # "바뀌지 않았다"는 식으로 RED 에서도 조용히 통과해 버렸다(구현 중 실측). 응답
        # 문자열을 트리거 직전에 심어 두면 우연한 조기 폴링은 빈 문자열(초기값과 동일 —
        # 무해한 no-op)을 받고, 내가 여는 그 순간에만 실제로 바뀐 스냅샷을 받는다.
        probe_body = """
var card = document.querySelector('[data-project-path="/repo/coding-harness"]');
var nameButton = card.querySelector('.project-name');
var sessionsEl = card.querySelector('ul.sessions');
if(sessionsEl.scrollHeight <= sessionsEl.clientHeight){
  throw new Error('세션 칸이 넘치지 않음(사전조건 실패 — scrollHeight ' + sessionsEl.scrollHeight
    + ' <= clientHeight ' + sessionsEl.clientHeight + ')');
}
sessionsEl.scrollTop = 20;   // §2.2 실측과 같은 조건 — 스크롤 앵커링은 이미 스크롤된 칸에서만 뜻이 있다
// s3 의 <li> 를 잡아 둔다 — liSame(같은 노드인지)은 s3 로 확인한다. 화면 위치(픽셀) 자체는
// 더 이상 단언하지 않는다: 실측(구현 중, __probeResult 로 scrollHeight·각 행 offsetHeight·
// sessionsEl 동일성을 모두 찍어 확인) 결과 세 행의 높이(116px)와 전체 scrollHeight(348px)는
// 폴링 전후로 전혀 바뀌지 않는데도 scrollTop 이 20→94 로 이동했다 — 이는 브라우저 네이티브
// 스크롤 앵커링이 "재정렬 당사자(s1·s2)" 중 하나를 스스로 앵커로 골라 그 노드의 화면 위치를
// 지키기 때문이며, 그 앵커는 내가 관찰하는 s3 이 아니다. 즉 "재정렬에 관여하지 않는 임의의
// 행이 픽셀 단위로 고정된다"는 것은 앵커링 알고리즘이 실제로 약속하는 바가 아니다(PU2 는
// 이 보정 자체를 "보너스"로 표시했다) — 대신 M1 이 실제로 깨뜨리면 안 되는 것은 "poll 이
// scrollTop 을 0 으로 되돌리지 않는다"(구 전체교체 버그의 증상)이므로 아래 단언은 그것만
// 검사한다.
var liS3 = document.querySelector('li [data-session-id="s3"]').closest('li');
// s1·s2(재정렬 당사자)의 <li> 도 잡아 둔다 — liSame(s3, 위)만으로는 "노드가 하나도 안
// 지워졌다"만 보고 "그 노드가 여전히 같은 세션을 대표하는가"는 못 본다(검수 2회차, MEDIUM
// — 재현: 세션 <li> 에서 RENDER_KEY_ATTRIBUTE 를 뺀 사본도 9/9 통과했다). 원인: 모든 세션
// <li> 가 class 없는 맨 <li> 라 키가 없으면 findUnkeyedMatch 가 커서 위치로만 짝짓는다 —
// s1·s2 는 자리가 그대로라(재정렬은 내용만 뒤집혔다) 커서 순서 짝짓기가 우연히 "그 자리의
// 옛 노드"를 집어 새 세션의 내용으로 덮어쓴다: 노드 자체는 안 지워지므로 isConnected 는
// 계속 참이지만, 그 노드가 대표하는 세션이 바뀐다. 아래에서 각 참조의 data-session-id 를
// 다시 읽어 잡을 때 값과 비교하면 이 "내용 뒤바뀜"을 잡는다 — 키가 있으면 노드가 실제로
// 이동해 자기 세션을 들고 다니므로 항상 같고, 키가 없으면 s1·s2 자리에서 어긋난다.
var liS1 = document.querySelector('li [data-session-id="s1"]').closest('li');
var liS2 = document.querySelector('li [data-session-id="s2"]').closest('li');
var scrollTopBefore = sessionsEl.scrollTop;
var glowAnims = card.getAnimations({subtree: true});
if(glowAnims.length < 1) throw new Error('작업중 카드에 글로우 애니메이션이 없음(사전조건 실패)');
var glowAnim = glowAnims[0];
nameButton.focus();
window.__mockFetchResponseText = %s;
await __triggerPoll();""" % _safe_js_string_literal(_minimal_data_document(_SCENARIO_SNAPSHOT_B_REORDERED))
        probe_body += """
var cardSame = card.isConnected;
var liSame = liS3.isConnected;
var focusSame = document.activeElement === nameButton;
var scrollTopAfter = sessionsEl.scrollTop;
var glowAnimsAfter = card.getAnimations({subtree: true});
var glowSame = glowAnimsAfter.indexOf(glowAnim) !== -1;
function sessionIdOf(li){ return li.querySelector('[data-session-id]').getAttribute('data-session-id'); }
var order = Array.prototype.map.call(
  card.querySelectorAll('ul.sessions li'),
  sessionIdOf
);
__probeResult({
  cardSame: cardSame, liSame: liSame, focusSame: focusSame, glowSame: glowSame,
  scrollTopBefore: scrollTopBefore, scrollTopAfter: scrollTopAfter, sessionOrderAfter: order,
  liS1StillS1: liS1.isConnected && sessionIdOf(liS1) === 's1',
  liS2StillS2: liS2.isConnected && sessionIdOf(liS2) === 's2',
  liS3StillS3: liS3.isConnected && sessionIdOf(liS3) === 's3',
});
"""
        page = _make_page(_pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertTrue(result["cardSame"], "폴링(정렬 뒤집힘) 뒤 카드가 같은 노드가 아님(D1)")
        self.assertTrue(result["liSame"], "폴링 뒤 세션 <li> 가 같은 노드가 아님(D1)")
        self.assertTrue(result["focusSame"], "폴링 뒤 키보드 포커스가 유지되지 않음(D1)")
        self.assertTrue(result["glowSame"], "폴링 뒤 작업중 글로우 애니메이션이 재시작됨(D1)")
        # 픽셀 단위 위치가 아니라 "poll 이 scrollTop 을 0 으로 되돌리지 않는다"만 검사한다 —
        # 위 준비 블록의 실측 설명대로, 재정렬에 관여하지 않는 행의 화면 위치를 픽셀 단위로
        # 고정하는 것은 브라우저 네이티브 스크롤 앵커링이 실제로 약속하는 바가 아니다.
        self.assertEqual(result["scrollTopBefore"], 20, "스크롤 사전조건이 적용되지 않음(사전조건 실패)")
        self.assertGreater(result["scrollTopAfter"], 0, "폴링 뒤 스크롤이 0 으로 리셋됨(전체교체 버그 재발, D1)")
        self.assertEqual(result["sessionOrderAfter"], ["s1", "s2", "s3"], "정렬이 뒤집히지 않음(사전조건)")
        # liSame(위)은 "노드가 안 지워졌다"만 본다 — 아래는 "그 노드가 여전히 같은 세션을
        # 대표하는가"를 본다(검수 2회차, MEDIUM). 키가 없으면 재정렬 당사자(s1·s2) 자리에서
        # 어긋난다 — 준비 블록의 실측 설명 참고.
        self.assertTrue(result["liS1StillS1"], "폴링 뒤 s1 이 있던 자리의 <li> 가 더 이상 s1 을 대표하지 않음(D1, 키 없는 재정렬 회귀)")
        self.assertTrue(result["liS2StillS2"], "폴링 뒤 s2 가 있던 자리의 <li> 가 더 이상 s2 를 대표하지 않음(D1, 키 없는 재정렬 회귀)")
        self.assertTrue(result["liS3StillS3"], "폴링 뒤 s3 이 있던 자리의 <li> 가 더 이상 s3 을 대표하지 않음(D1, 키 없는 재정렬 회귀)")

    def test_d2_poll_result_matches_fresh_render_oracle(self) -> None:
        """오라클 — A→B 폴링 결과의 #dzh-app 정규화 직렬화가 B 를 처음부터 그린 결과와 같다."""
        probe_body = """
function normalizedTree(root){
  function serialize(node){
    if(node.nodeType === Node.TEXT_NODE) return JSON.stringify(node.nodeValue);
    if(node.nodeType !== Node.ELEMENT_NODE) return '';
    var attrs = Array.prototype.slice.call(node.attributes)
      .map(function(a){
        if(a.name === 'aria-describedby') return null;
        if(a.name === 'aria-current') return null;
        if(a.name === 'class'){
          var tokens = a.value.split(' ').filter(function(t){ return t !== 'card-open'; });
          return tokens.length ? ('class="' + tokens.join(' ') + '"') : null;
        }
        return a.name + '="' + a.value + '"';
      })
      .filter(function(v){ return v !== null; })
      .sort()
      .join(' ');
    var children = Array.prototype.map.call(node.childNodes, serialize).join('');
    return '<' + node.tagName + (attrs ? (' ' + attrs) : '') + '>' + children + '</' + node.tagName + '>';
  }
  return serialize(root);
}
window.__mockFetchResponseText = %s;
await __triggerPoll();
var afterPoll = normalizedTree(document.getElementById('dzh-app'));
__probeResult({afterPoll: afterPoll});
""" % _safe_js_string_literal(_minimal_data_document(_SCENARIO_SNAPSHOT_B_REORDERED))
        # D1 과 같은 이유(그 테스트의 문서 주석 참고) — 응답을 페이지 로드 시점부터 미리
        # 장전해 두지 않고 트리거 직전에 심는다.
        page = _make_page(_pre_script(None), probe_body)
        polled = run_scenario(page)["afterPoll"]

        fresh_probe_body = """
var afterFresh = (function(){
  function normalizedTree(root){
    function serialize(node){
      if(node.nodeType === Node.TEXT_NODE) return JSON.stringify(node.nodeValue);
      if(node.nodeType !== Node.ELEMENT_NODE) return '';
      var attrs = Array.prototype.slice.call(node.attributes)
        .map(function(a){
          if(a.name === 'aria-describedby') return null;
          if(a.name === 'aria-current') return null;
          if(a.name === 'class'){
            var tokens = a.value.split(' ').filter(function(t){ return t !== 'card-open'; });
            return tokens.length ? ('class="' + tokens.join(' ') + '"') : null;
          }
          return a.name + '="' + a.value + '"';
        })
        .filter(function(v){ return v !== null; })
        .sort()
        .join(' ');
      var children = Array.prototype.map.call(node.childNodes, serialize).join('');
      return '<' + node.tagName + (attrs ? (' ' + attrs) : '') + '>' + children + '</' + node.tagName + '>';
    }
    return serialize(document.getElementById('dzh-app'));
  }
  return normalizedTree();
})();
__probeResult({afterFresh: afterFresh});
"""
        fresh_page = _fresh_page_for_snapshot(_SCENARIO_SNAPSHOT_B_REORDERED, fresh_probe_body)
        fresh = run_scenario(fresh_page)["afterFresh"]
        self.assertEqual(polled, fresh, "맞대기(폴링) 결과가 B 를 새로 그린 결과와 다름(D2 오라클)")

    def test_d3_tick_changes_text_only_same_node_scroll_preserved(self) -> None:
        probe_body = """
var sessionsEl = document.querySelector('[data-project-path="/repo/coding-harness"] ul.sessions');
sessionsEl.scrollTop = 6;
var scrollBefore = sessionsEl.scrollTop;
var li = document.querySelector('li [data-session-id="s2"]').closest('li');
var lastActivityBefore = document.querySelector('[data-project-path="/repo/coding-harness"] .last-activity').textContent;
await __fireTick();
await __sleep(30);
var scrollAfter = sessionsEl.scrollTop;
var lastActivityAfter = document.querySelector('[data-project-path="/repo/coding-harness"] .last-activity').textContent;
__probeResult({
  liSame: li.isConnected, scrollUnchanged: scrollAfter === scrollBefore,
  textChanged: lastActivityAfter !== lastActivityBefore,
});
"""
        page = _make_page(_pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertTrue(result["liSame"], "30초 틱 뒤 세션 <li> 가 같은 노드가 아님(D3)")
        self.assertTrue(result["scrollUnchanged"], "글자만 바뀌는 틱인데 세션 칸 scrollTop 이 바뀜(D3)")
        self.assertTrue(result["textChanged"], "61초가 지났는데 경과 라벨(.last-activity)이 안 바뀜(D3 사전조건)")

    def test_d4_live_move_simulation_is_restored_by_tick(self) -> None:
        """라이브 이동 흉내(마지막 카드를 맨 앞으로) → 틱 → 저장 순서 복원 · 같은 노드(PU7)."""
        probe_body = """
var app = document.getElementById('dzh-app');
var atlasCard = document.querySelector('[data-project-path="/repo/atlas"]');
app.insertBefore(atlasCard, app.firstChild);
var orderDuringMove = Array.prototype.map.call(
  app.querySelectorAll('.card'), function(c){ return c.getAttribute('data-project-path'); }
);
await __fireTick();
var orderAfter = Array.prototype.map.call(
  app.querySelectorAll('.card'), function(c){ return c.getAttribute('data-project-path'); }
);
__probeResult({
  atlasSame: atlasCard.isConnected,
  orderDuringMove: orderDuringMove, orderAfter: orderAfter,
});
"""
        page = _make_page(_pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertEqual(result["orderDuringMove"], ["/repo/atlas", "/repo/coding-harness"], "라이브 이동 흉내 자체가 실패함(사전조건)")
        self.assertEqual(result["orderAfter"], ["/repo/coding-harness", "/repo/atlas"], "틱이 저장 순서를 복원하지 않음(D4, PU7)")
        self.assertTrue(result["atlasSame"], "순서 복원 뒤 카드가 같은 노드가 아님(D4)")

    def test_d5_session_row_click_marking_survives_tick(self) -> None:
        """세션 줄 클릭(패널 열림 표시) → 틱 → 같은 노드에 .card-open·aria-current 유지(PU3)."""
        probe_body = """
var button = document.querySelector('[data-session-id="s3"]');
__dispatchClick(button);
var openBefore = button.classList.contains('card-open') && button.getAttribute('aria-current') === 'true';
await __fireTick();
await __sleep(30);
var openAfter = button.classList.contains('card-open') && button.getAttribute('aria-current') === 'true';
__probeResult({buttonSame: button.isConnected, openBefore: openBefore, openAfter: openAfter});
"""
        page = _make_page(_pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertTrue(result["openBefore"], "세션 줄 클릭이 .card-open·aria-current 를 못 켬(사전조건)")
        self.assertTrue(result["buttonSame"], "틱 뒤 세션 줄 버튼이 같은 노드가 아님(D5)")
        self.assertTrue(result["openAfter"], "틱 뒤 .card-open·aria-current 표시가 사라짐(D5, PU3)")

    def test_d6_tooltip_survives_tick_and_closes_on_removal(self) -> None:
        """hover(트리거) → 틱(글자만, 툴팁 유지) → 폴링(그 세션 줄 제거, 툴팁 닫힘)."""
        probe_body = """
var trigger = document.querySelector('[data-session-id="s1"]').querySelector('.session-id');
__dispatchClick(document.body);  // 툴팁 IIFE 의 'click' 전역 리스너가 이전 상태를 닫아 둔다(위생)
trigger.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
await __sleep(220);
var tooltipEl = document.getElementById('dzh-tooltip');
var visibleAfterHover = tooltipEl.classList.contains('tooltip-visible');
var describedByAfterHover = trigger.getAttribute('aria-describedby');
await __fireTick();
await __sleep(30);
var visibleAfterTick = tooltipEl.classList.contains('tooltip-visible');
var describedByAfterTick = trigger.getAttribute('aria-describedby');
var triggerSameAfterTick = trigger.isConnected;
"""
        probe_body += """
window.__mockFetchResponseText = %s;
await __triggerPoll();
var visibleAfterRemoval = tooltipEl.classList.contains('tooltip-visible');
__probeResult({
  visibleAfterHover: visibleAfterHover, describedByAfterHover: describedByAfterHover,
  visibleAfterTick: visibleAfterTick, describedByAfterTick: describedByAfterTick,
  triggerSameAfterTick: triggerSameAfterTick, visibleAfterRemoval: visibleAfterRemoval,
});
""" % _safe_js_string_literal(_minimal_data_document(_snapshot((
            _project("/repo/coding-harness", "coding-harness", "working", (_SESSION_S2, _SESSION_S3)),
            _project("/repo/atlas", "atlas", "idle", (_SESSION_ATLAS,)),
        ))))
        page = _make_page(_pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertTrue(result["visibleAfterHover"], "hover 뒤 툴팁이 안 뜸(사전조건)")
        self.assertEqual(result["describedByAfterHover"], "dzh-tooltip", "hover 뒤 aria-describedby 가 안 붙음(사전조건)")
        self.assertTrue(result["triggerSameAfterTick"], "틱 뒤 트리거가 같은 노드가 아님(D6)")
        self.assertTrue(result["visibleAfterTick"], "글자만 바뀌는 틱인데 떠 있던 툴팁이 닫힘(D6, PU5)")
        self.assertEqual(result["describedByAfterTick"], "dzh-tooltip", "틱 뒤 aria-describedby 가 지워짐(D6, PU3 보존 예외)")
        self.assertFalse(result["visibleAfterRemoval"], "트리거가 제거됐는데 툴팁이 안 닫힘(D6, PU5 구조 변화 감지)")

    def test_d7a_warnings_render_last_and_empty_state_matches_fresh_render(self) -> None:
        warned_snapshot = _snapshot(
            (_project("/repo/coding-harness", "coding-harness", "idle", (_SESSION_S1,)),),
            warnings=("경고 문구 1", "경고 문구 2"),
        )
        probe_body = """
var app = document.getElementById('dzh-app');
var lastChild = app.lastElementChild;
__probeResult({lastChildIsWarnings: lastChild.classList.contains('warnings'), warningsText: lastChild.textContent});
"""
        page = _fresh_page_for_snapshot(warned_snapshot, probe_body)
        result = run_scenario(page)
        self.assertTrue(result["lastChildIsWarnings"], "경고 블록이 #dzh-app 의 마지막 자식이 아님(D7)")
        self.assertIn("경고 문구 1", result["warningsText"])
        self.assertIn("경고 문구 2", result["warningsText"])

    def test_d7b_empty_project_list_shows_empty_state(self) -> None:
        empty_snapshot = _snapshot(())
        probe_body = """
var emptyEl = document.querySelector('#dzh-app .empty');
__probeResult({text: emptyEl ? emptyEl.textContent : null});
"""
        page = _fresh_page_for_snapshot(empty_snapshot, probe_body)
        result = run_scenario(page)
        self.assertEqual(result["text"], "아직 프로젝트가 없습니다. 훅을 설치했나요? — /hub install")

    def test_d7c_broken_data_block_shows_parse_error(self) -> None:
        rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, _SCENARIO_SNAPSHOT_A)
        marker_open = '<script type="application/json" id="dzh-data">'
        marker_close = "</script>"
        start = rendered.index(marker_open) + len(marker_open)
        end = rendered.index(marker_close, start)
        broken = rendered[:start] + "{이것은 유효한 JSON 이 아니다" + rendered[end:]
        probe_body = """
var emptyEl = document.querySelector('#dzh-app .empty');
__probeResult({text: emptyEl ? emptyEl.textContent : null});
"""
        page = _inject_scripts(broken, _pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertIsNotNone(result["text"], "파싱 오류 안내 블록을 찾지 못함(D7)")
        self.assertIn("데이터를 읽지 못했습니다", result["text"])

    def test_d7d_empty_project_list_with_warnings_shows_both(self) -> None:
        # D7 변형(검수 2회차, HIGH) — appContentHtml() 의 조기 반환이 "프로젝트 0개" 일 때
        # 경고 블록 계산 자체를 건너뛰었다. D7a 는 "카드 + 경고", D7b 는 "빈 상태(경고 없음)"
        # 만 보고, 둘을 조합한 "빈 상태 + 경고"는 이 테스트가 생기기 전까지 아무도 안 봤다.
        # D2 오라클도 폴링·새로 그리기가 같은 함수(appContentHtml)를 쓰므로 이 결손을 못
        # 잡는다 — 함수 자체가 틀렸으면 오라클 비교의 양쪽이 똑같이 틀리기 때문이다.
        empty_with_warnings_snapshot = _snapshot((), warnings=("경고 문구 1", "경고 문구 2"))
        probe_body = """
var emptyEl = document.querySelector('#dzh-app .empty');
var warningsEl = document.querySelector('#dzh-app .warnings');
__probeResult({
  emptyText: emptyEl ? emptyEl.textContent : null,
  warningsText: warningsEl ? warningsEl.textContent : null,
});
"""
        page = _fresh_page_for_snapshot(empty_with_warnings_snapshot, probe_body)
        result = run_scenario(page)
        self.assertEqual(result["emptyText"], "아직 프로젝트가 없습니다. 훅을 설치했나요? — /hub install")
        self.assertIsNotNone(result["warningsText"], "프로젝트 0개일 때 경고 블록이 사라짐(D7 변형, 검수 2회차 HIGH)")
        self.assertIn("경고 문구 1", result["warningsText"])
        self.assertIn("경고 문구 2", result["warningsText"])


    def test_d_bw1_background_badge_project_badge_order_and_glow(self) -> None:
        """D-BW1(§8.2) — ① 세션 배지 텍스트·툴팁 ② 프로젝트 배지 텍스트·정적 툴팁
        ③ working 세션이 없는 카드에 card-working 없음 ④ 세션 순서 working→background→idle
        ⑤ 틱(61초) 뒤에도 배지 노드가 같다(부분 갱신 PU1)."""
        probe_body = """
var appEl = document.getElementById('dzh-app');
var codingCard = appEl.querySelector('[data-project-path="/repo/coding-harness"]');
var atlasCard = appEl.querySelector('[data-project-path="/repo/atlas"]');
var bgLi = codingCard.querySelector('[data-session-id="bg1"]').closest('li');
var bgBadge = bgLi.querySelector('.badge.state-background');
var bgBadgeText = bgBadge.textContent;
var bgBadgeTooltip = bgBadge.getAttribute('data-tooltip');
var sessionOrder = Array.prototype.map.call(
  codingCard.querySelectorAll('ul.sessions li [data-session-id]'),
  function(el){ return el.getAttribute('data-session-id'); }
);
var projectBadge = atlasCard.querySelector('.project-head .badge.state-background');
var projectBadgeText = projectBadge.textContent;
var projectBadgeTooltip = projectBadge.getAttribute('data-tooltip');
var atlasHasCardWorking = atlasCard.classList.contains('card-working');
await __fireTick();
await __sleep(30);
__probeResult({
  bgBadgeText: bgBadgeText, bgBadgeTooltip: bgBadgeTooltip, sessionOrder: sessionOrder,
  projectBadgeText: projectBadgeText, projectBadgeTooltip: projectBadgeTooltip,
  atlasHasCardWorking: atlasHasCardWorking, bgBadgeSameNodeAfterTick: bgBadge.isConnected,
});
"""
        rendered = hub_model.render_hub_html(_TEMPLATE_TEXT, _SCENARIO_SNAPSHOT_BACKGROUND)
        page = _inject_scripts(rendered, _pre_script(None), probe_body)
        result = run_scenario(page)
        self.assertEqual(result["bgBadgeText"], "◐백그라운드 대기", "① 세션 배지 텍스트가 다름")
        self.assertIn("백그라운드 작업 2개", result["bgBadgeTooltip"], "① 세션 배지 툴팁에 작업 수가 없음")
        self.assertRegex(result["bgBadgeTooltip"], r"\d{1,2}:\d{2}.*\d{1,2}:\d{2}", "① 세션 배지 툴팁에 절대 시각(since·until) 두 개가 없음")
        self.assertEqual(result["sessionOrder"], ["w1", "bg1", "bg-idle-sibling"], "④ 세션 순서가 working→background→idle 이 아님")
        self.assertEqual(result["projectBadgeText"], "◐백그라운드", "② 프로젝트 배지 텍스트가 다름(짧은 라벨이어야 한다)")
        self.assertEqual(result["projectBadgeTooltip"], "백그라운드 작업이 끝나기를 기다리는 세션이 있습니다.", "② 프로젝트 배지 툴팁이 정적 문구와 다름")
        self.assertFalse(result["atlasHasCardWorking"], "③ working 세션이 없는데 card-working 이 있음(glow 오발동)")
        self.assertTrue(result["bgBadgeSameNodeAfterTick"], "⑤ 61초 틱 뒤 배지가 같은 노드가 아님(부분 갱신 PU1 위반)")


if __name__ == "__main__":
    unittest.main()
