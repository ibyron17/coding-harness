"""tests/hub/template_dom_harness.py — 헤드리스 Chrome DOM 행동 검사의 공용 하네스
(docs/prps/hub-session-modal-and-partial-update.md §10.3, 구현 단계 개정(2026-09-24)).

M1(부분 갱신, D1~D7)의 test_hub_template_dom.py 하나였던 파일이 M2(카드 상세보기, D8~D17)로
800줄 상한을 넘게 돼, Chrome 탐색·서버·사전 스크립트·프로브·run_scenario·픽스처 빌더 등
**시나리오와 무관한 부분**을 이 모듈로 옮겼다 — 이름이 `test` 로 시작하지 않아
`python3 -m unittest discover` 가 테스트 모듈로 줍지 않는다. 시나리오 전용 픽스처(특정 세션·
스냅샷 인스턴스)와 그것을 굽는 `_make_page` 류 헬퍼는 각 시나리오 파일(test_hub_template_dom.py·
test_hub_template_dom_modal.py)에 그대로 남는다 — 이 모듈이 아는 것은 "페이지를 어떻게 굽고
Chrome 으로 어떻게 실행하는가"뿐이고, "무엇을 굽는가"는 모른다.

노드 동일성 판정은 attribute 태그가 아니라 **JS 변수 참조 + isConnected**로 한다 — 마킹용
속성을 추가하면 syncAttributes(결정 PU3, "렌더 결과에 없는 속성은 지운다")가 그 자체를
지워버려 판정 수단이 검사 대상 메커니즘과 충돌한다. 참조를 액션 전에 잡아 두고 액션 후
그 참조가 여전히 문서에 연결돼 있는지(isConnected)만 보면, 노드가 파괴·재생성됐을 때만
false 가 된다 — 충돌 없는 판정이다.
"""

import html
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "hub", "bin"))

import hub_model  # noqa: E402  (sys.path 조정 후 임포트)
import hub_project  # noqa: E402
import hub_session  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CHROME_ENV_VAR = "DZH_TEST_CHROME"
TEMPLATE_ENV_VAR = "DZH_DOM_TEST_TEMPLATE"
TEMPLATE_PATH = Path(os.environ.get(TEMPLATE_ENV_VAR, REPO_ROOT / "hub" / "bin" / "hub_template.html"))

VIRTUAL_TIME_BUDGET_MS = 5000        # §2.2 함정 4 — 무한 CSS 애니메이션과 겹치지 않는 예산.
# 구현 중 실측: 이 값을 15000 으로 3배 늘려도 실패율이 그대로였다 — 원인은 예산 부족이
# 아니라 렌더 완료 대기를 setTimeout 폴링으로 구현했던 옛 방식(지금은 삭제, _PROBE_PRELUDE
# 의 TRIGGER_SETTLE_MS 설명 참고)이 예산을 스스로 먹어치우던 것이었다. 그래서 원 실측값
# (5000) 그대로 둔다.
# 실측(2026-09-23, 메인 세션, /private/tmp/.../scratchpad/chrome-probe/probe_chrome_flags.py,
# 조합당 2회, 다른 세션이 tests/run.sh 를 동시에 돌리는 상태): --use-mock-keychain 을 주면
# 정상 실행 1.1~2.0초(가짜 HOME·실제 HOME 무관), 설계 단계 실측(§2.2)은 2~9초 — 30초면
# 재시도 없이도 넉넉하다.
CHROME_TIMEOUT_SECONDS = 30
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
BASE_TIME_MS = 1_790_000_000_000     # 임의의 고정 기준 시각(달력상 의미 없음 — 결정적 픽스처용)
TICK_MS = 30000
TICK_ADVANCE_MS = 61000              # §2.2 — "61초 뒤" 시계로 틱 콜백을 직접 부른다
POLL_INTERVAL_MS = 60000             # 앱의 POLL_INTERVAL_MS(hub_template.html)와 같은 값 —
# __triggerPoll 이 이 delay 로 가로챈 setInterval(poll, …) 콜백을 직접 부른다.


def _find_chrome() -> str | None:
    """DZH_TEST_CHROME → macOS 기본 경로 → PATH 상의 이름들 순으로 찾는다(§10.3)."""
    env_chrome = os.environ.get(CHROME_ENV_VAR)
    if env_chrome and Path(env_chrome).exists():
        return env_chrome
    mac_default = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac_default.exists():
        return str(mac_default)
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME_PATH = _find_chrome()
SKIP_REASON = f"Chrome 을 찾지 못해 DOM 행동 검사를 건너뜁니다({CHROME_ENV_VAR} 로 직접 지정 가능)"


def read_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def minimal_data_document(snapshot: hub_model.HubSnapshot) -> str:
    """poll() 이 DOMParser 로 파싱할 최소 문서 — #dzh-data 마커만 있으면 충분하다(전체
    템플릿을 다시 구울 필요가 없다)."""
    template = '<html><body><script type="application/json" id="dzh-data">{}</script></body></html>'
    return hub_model.render_hub_html(template, snapshot)


def safe_js_string_literal(text: str) -> str:
    """text 를 <script> 안에 안전하게 심을 수 있는 JS 문자열 리터럴로 만든다 — </script> 가
    문자열 안에 그대로 있으면 HTML 파서가 스크립트를 조기 종료시킨다(hub_model.render_hub_html
    이 #dzh-data 페이로드에 쓰는 것과 같은 유니코드 이스케이프 관례, GOTCHA)."""
    raw = json.dumps(text)
    return raw.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


# ---- 사전 스크립트(<body> 직후) — fetch·setInterval·Date.now 가로채기(§2.2 함정 2·3·4) ----
_PRE_SCRIPT_HEAD = """
window.__probeIntervals = [];
window.__mockNowBaseMs = %d;
window.__mockNowOffsetMs = 0;
Date.now = function(){ return window.__mockNowBaseMs + window.__mockNowOffsetMs; };
window.setInterval = function(fn, delay){
  window.__probeIntervals.push({fn: fn, delay: delay});
  return window.__probeIntervals.length;
};
window.fetch = function(){
  return Promise.resolve({
    ok: true,
    status: 200,
    text: function(){ return Promise.resolve(window.__mockFetchResponseText); }
  });
};
// 렌더 횟수를 여기서부터 센다 — 앱 스크립트가 아직 실행되기 전이라, 이후 앱이 등록하는
// visibilitychange·focus 리스너가 페이지 로드 자체의 부수효과로(사람 조작 없이도) 아주
// 이르게 발화해 poll() 이 조용히 먼저 돌아도(실측 — 헤드리스 dump-dom 에서 재현) 그 렌더를
// 놓치지 않는다. 프로브가 나중에 'dzh:rendered' 를 한 번만 기다리는 방식은 이미 지나간
// 이벤트를 볼 수 없어 Promise 가 영원히 안 풀렸다(구현 중 실측 — D1 이 간헐적으로 이 경로로
// 죽었다). 카운터 비교는 "몇 번째 렌더부터 세는가"만 알면 되므로 이 문제가 없다.
window.__renderCount = 0;
document.addEventListener('dzh:rendered', function(){ window.__renderCount++; });
""" % BASE_TIME_MS


def pre_script(poll_response_snapshot: hub_model.HubSnapshot | None) -> str:
    if poll_response_snapshot is not None:
        response_literal = safe_js_string_literal(minimal_data_document(poll_response_snapshot))
    else:
        response_literal = "''"
    return _PRE_SCRIPT_HEAD + "\nwindow.__mockFetchResponseText = " + response_literal + ";\n"


# ---- 프로브 서문(</body> 앞) — 모든 시나리오가 공유하는 헬퍼 ----
PROBE_PRELUDE = """
function __probeResult(obj){
  var pre = document.createElement('pre');
  pre.id = 'probe-result';
  pre.textContent = JSON.stringify(obj);
  document.body.appendChild(pre);
}
function __probeFail(err){
  __probeResult({error: String((err && err.message) || err), stack: (err && err.stack) || ''});
}
function __sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
// 렌더 완료를 "dzh:rendered 를 기다린다"가 아니라 트리거 뒤 짧게 실제로 쉬는 것으로
// 갈음한다 — 이벤트 기반 대기(리스너 1회성이든 window.__renderCount 비교든)를 둘 다
// 실측으로 시도했으나 간헐적으로 풀리지 않았다: 이 프로브의 mock fetch 는 트리거마다
// **같은** window.__mockFetchResponseText 를 돌려주므로, 헤드리스 dump-dom 이 페이지
// 로드 자체의 부수효과로 poll() 을 먼저 한 번 조용히 돌리면(실측 — 사람 조작 없이도
// 발생) 그 호출이 이미 lastHtml 을 그 문자열로 채워 둔다. 뒤이은 내 명시적 트리거는
// poll() 안의 `if(html === lastHtml){ …; return; }` 최적화에 걸려 render() 를 다시
// 부르지 않는다 — "이벤트를 놓쳤다"가 아니라 "그 트리거로는 애초에 두 번째 렌더가
// 일어나지 않는다"였다(구현 중 실측, __waitForRenderSince 두 버전 모두 비결정적으로
// 실패해 이 결론에 도달했다). 렌더 자체는(사고든 의도든) 이미 일어나 있거나 트리거
// 직후 마이크로태스크로 끝나므로, 언제 어떤 경로로 왔는지 구분하지 않고 짧게 실제로
// 쉬었다가 DOM 상태를 그대로 읽는 쪽이 결정적이다.
var TRIGGER_SETTLE_MS = 200;
// 가로챈 setInterval(fn, delayMs) 콜백을 delay 로 찾아 직접 부른다. 못 찾으면 false.
// window.dispatchEvent(new Event('focus')) 로 대신하지 않는 이유 — 헤드리스 dump-dom 에서는
// .focus() 류 조작이 그 자체로 진짜 window 'focus' 이벤트를 유발할 때가 있어(실측,
// 비결정적) 명시적 dispatch 와 경합한다. 직접 호출은 네이티브 이벤트 의미론에 기대지
// 않아 결정적이다.
function __invokeIntervalByDelay(delayMs){
  for(var i = 0; i < window.__probeIntervals.length; i++){
    if(window.__probeIntervals[i].delay === delayMs){ window.__probeIntervals[i].fn(); return true; }
  }
  return false;
}
function __triggerPoll(){
  if(!__invokeIntervalByDelay(%d)){
    throw new Error('60초 폴링 interval 이 가로채기에 잡히지 않음 — setInterval(poll, POLL_INTERVAL_MS) 앵커가 깨졌다');
  }
  return __sleep(TRIGGER_SETTLE_MS);
}
function __fireTick(){
  window.__mockNowOffsetMs += %d;
  if(!__invokeIntervalByDelay(%d)){
    throw new Error('30초 틱 interval 이 가로채기에 잡히지 않음 — setInterval(render, TICK_MS) 앵커가 깨졌다');
  }
  return __sleep(TRIGGER_SETTLE_MS);
}
function __dispatchClick(el){ el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); }
""" % (POLL_INTERVAL_MS, TICK_ADVANCE_MS, TICK_MS)


def _handler_factory(directory: str):
    return partial(SimpleHTTPRequestHandler, directory=directory)


_PROBE_RESULT_OPEN = '<pre id="probe-result">'


def _extract_probe_result(dumped_html: str) -> dict:
    start = dumped_html.find(_PROBE_RESULT_OPEN)
    if start == -1:
        raise AssertionError(
            "probe-result 를 dump-dom 출력에서 찾지 못함 — 프로브가 실행되지 않았거나 "
            "JS 오류로 죽었다(비동기 IIFE 의 try/catch 바깥에서 던졌을 가능성)"
        )
    start += len(_PROBE_RESULT_OPEN)
    end = dumped_html.index("</pre>", start)
    payload = json.loads(html.unescape(dumped_html[start:end]))
    if "error" in payload:
        raise AssertionError(f"프로브 내부 오류: {payload['error']}\n{payload.get('stack', '')}")
    return payload


def run_scenario(page_html: str, window_width: int = WINDOW_WIDTH, window_height: int = WINDOW_HEIGHT) -> dict:
    """page_html 을 임시 디렉터리에 서빙하고 헤드리스 Chrome 으로 --dump-dom 한 뒤,
    프로브가 남긴 <pre id="probe-result"> 의 JSON 을 파싱해 돌려준다. Chrome 인자·타임아웃
    근거는 _dump_dom 의 문서 주석을 볼 것 — --user-data-dir 를 주지 않으므로 프로필은
    Chrome 의 기본 위치를 쓰지만, HOME 을 실제 값 그대로 두면(이 함수가 그렇게 한다) 그
    기본 위치도 실제 $HOME 밖(Chrome 자신의 기존 프로필 디렉터리)이라 이 스위트가 그
    아래에 새 파일을 남기지 않는다(가짜 HOME 재현 시나리오는 이 함수의 호출자가 HOME 을
    직접 바꿔 별도로 확인한다). window_width·window_height 는 M2 의 뷰포트별 시나리오
    (SC2 밀어내기 1024px·SC14 오버레이 820px)를 위한 선택 인자 — 기본값은 D1~D7 의
    기존 창 크기와 같다(회귀 없음)."""
    with tempfile.TemporaryDirectory() as site_dir:
        (Path(site_dir) / "index.html").write_text(page_html, encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_factory(site_dir))
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            port = server.server_address[1]
            url = f"http://127.0.0.1:{port}/index.html"
            dumped_html = _dump_dom(url, window_width, window_height)
        finally:
            server.shutdown()
            server_thread.join(timeout=5)
            server.server_close()   # shutdown() 은 serve_forever 루프만 멈춘다 — 리스닝 소켓
            # 자체를 닫지 않으면 매 호출마다 ResourceWarning: unclosed socket 이 남는다(검수
            # 2회차, LOW).
    return _extract_probe_result(dumped_html)


def run_scenario_via_file(page_html: str, window_width: int = WINDOW_WIDTH, window_height: int = WINDOW_HEIGHT) -> dict:
    """run_scenario 와 같지만 HTTP 서버를 띄우지 않고 file:// 로 직접 연다 — D16(카드
    상세보기의 file:// 모드, isServed=false 분기)처럼 `location.protocol` 이 실제로
    "file:" 이어야 하는 시나리오 전용이다. 서버 기동이 없으므로 run_scenario 의 스레드·
    소켓 정리 절차가 필요 없다."""
    with tempfile.TemporaryDirectory() as site_dir:
        file_path = Path(site_dir) / "index.html"
        file_path.write_text(page_html, encoding="utf-8")
        dumped_html = _dump_dom(f"file://{file_path}", window_width, window_height)
    return _extract_probe_result(dumped_html)


def _dump_dom(url: str, window_width: int = WINDOW_WIDTH, window_height: int = WINDOW_HEIGHT) -> str:
    """--dump-dom 을 1회 시도한다(재시도 없음 — 원인(아래)이 사라진 뒤에는 재시도가 남은
    결정적 결함을 가리는 쪽 위험이 재시도 자체의 이득보다 크다).

    실측(2026-09-23, 메인 세션, /private/tmp/.../scratchpad/chrome-probe/
    probe_chrome_flags.py, 조합당 2회, 다른 세션이 tests/run.sh 를 동시에 돌리는 상태에서):
    --user-data-dir(새 빈 폴더)는 실제/가짜 HOME·--use-mock-keychain·조용한 플래그 6종
    추가 여부와 무관하게 5개 조합 10/10 멈췄다(PRP §2.2 함정 1 의 원래 관찰이 맞았다) —
    그래서 주지 않는다. 대신 --use-mock-keychain 를 준다: 가짜 HOME(이 스위트의 T24 가
    돌아가는 샌드박스 조건과 같다)에서는 이 플래그가 없으면 macOS 키체인 접근에서 멈춘다
    (플래그 없이 2/2 멈춤 vs 플래그 있으면 4/4 성공 1.1~1.6초). 실제 HOME 은 플래그 없이도
    2/2 성공(1.3~2.0초)했지만 --use-mock-keychain 을 얹어도 4/4 성공(1.2~1.4초)이라 손해가
    없어, 실제/가짜 HOME 분기 없이 항상 붙인다.

    subprocess.run 의 timeout 처리는 직계 자식만 죽여 Chrome 의 헬퍼 프로세스(GPU·렌더러 등)
    가 고아로 남을 수 있다(실측 확인) — Popen 을 새 세션(start_new_session=True)으로 띄워
    타임아웃 시 os.killpg 로 프로세스 그룹 전체를 죽인다.
    """
    args = [
        CHROME_PATH, "--headless=new", "--disable-gpu", "--use-mock-keychain",
        f"--window-size={window_width},{window_height}",
        f"--virtual-time-budget={VIRTUAL_TIME_BUDGET_MS}",
        "--dump-dom", url,
    ]
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=dict(os.environ), start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=CHROME_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()   # 그룹을 죽인 뒤 남은 파이프를 비우고 좀비를 거둔다
        raise AssertionError(f"Chrome 이 {CHROME_TIMEOUT_SECONDS}초 안에 끝나지 않아 프로세스 그룹을 강제 종료함: {url}")
    if process.returncode != 0:
        raise AssertionError(f"Chrome 종료 코드 {process.returncode}\nstderr:\n{stderr[-4000:]}")
    return stdout


# ---- 픽스처 빌더(범용 — 특정 시나리오 값은 각 테스트 파일이 쥔다) ----
def make_session(session_id, state, base_state, last_event_at_ms, dashboard_key=None, task_excerpt=None, background_wait=None):
    return hub_session.SessionView(
        session_id=session_id, short_id=session_id, started_at_ms=BASE_TIME_MS,
        state=state, base_state=base_state, last_event_at_ms=last_event_at_ms,
        task_excerpt=task_excerpt, agent_runs=(), dashboard_key=dashboard_key,
        background_wait=background_wait,
    )


def make_project(path, display_name, state, sessions):
    return hub_project.ProjectView(
        display_name=display_name, path=path, tier=2, state=state,
        last_activity_at_ms=BASE_TIME_MS, sessions=sessions, tier1=None, note=None,
    )


def make_snapshot(projects, warnings=()):
    return hub_model.HubSnapshot(
        collected_at_ms=BASE_TIME_MS, projects=projects,
        unresolved_dir_names=(), warnings=warnings,
    )


TEMPLATE_TEXT = read_template() if TEMPLATE_PATH.exists() else ""


def inject_scripts(rendered_page: str, pre_script_text: str, probe_body: str) -> str:
    """이미 구워진 페이지(rendered_page)에 사전 스크립트·프로브를 끼운다 — 각 시나리오
    파일의 make_page 류 헬퍼가 이 함수로 위임한다(예: 데이터 블록을 일부러 깬 사본처럼
    이미 특수하게 만든 페이지에는 이 함수를 직접 쓴다)."""
    body_open_tag = "<body>"
    body_close_tag = "</body>"
    open_index = rendered_page.index(body_open_tag) + len(body_open_tag)
    close_index = rendered_page.rindex(body_close_tag)
    probe_script = PROBE_PRELUDE + "\n(async function(){\ntry{\n" + probe_body + "\n}catch(e){ __probeFail(e); }\n})();\n"
    return (
        rendered_page[:open_index]
        + "\n<script>" + pre_script_text + "</script>\n"
        + rendered_page[open_index:close_index]
        + "\n<script>" + probe_script + "</script>\n"
        + rendered_page[close_index:]
    )


def fresh_page_for_snapshot(snapshot: hub_model.HubSnapshot, probe_body: str) -> str:
    """snapshot 을 처음부터 그린 페이지 — D2 오라클과 D7 의 "새로 그리기" 비교 대상, D15
    류 "사라진 프로젝트" 시나리오의 재사용 대상."""
    rendered = hub_model.render_hub_html(TEMPLATE_TEXT, snapshot)
    return inject_scripts(rendered, pre_script(None), probe_body)
