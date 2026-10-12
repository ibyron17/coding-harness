# shell-hardening — 쉘·설치 경계 견고성 (설계)

2026-08 전수 감사(`docs/prps/full-audit-2026-08.md`)가 낸 지적 중 「쉘 견고성」 계열을
`docs/prps/audit-remediation.md` §9 「의도적 미룸」 표가 이 PRP 로 이관했다. 이 문서가 그
첫 설계다.

**행 번호를 쓰지 않는다** — 감사 문서의 행 번호는 감사 기준 커밋 시점이라 현재 파일과
어긋난다. 이 문서의 코드 인용은 전부 심볼명이다(`tests/run.sh` 의 `T39` 가 이것을 강제한다).
**저장소 자신의 현재 상태를 숫자로 단정하지 않는다** — 세는 값이 필요한 자리에는 세는 명령을
적는다(`docs/prps/rules-docs-sync.md` §17-1 규범).

---

## 0. 이 문서를 쓰면서 직접 재실측한 것

메인 세션의 재검증 결과(14건 중 1건 해소·2건 부분 유효·11건 유효)를 입력으로 받았고, 설계
판단의 근거가 되는 자리를 직접 열어 확인했다. 아래는 **표를 그대로 옮긴 것이 아니라 내가
파일을 열어 확인한 것**이고, 표와 어긋나거나 표에 없는 것은 굵게 표시했다.

| 확인 | 방법 | 결과 |
|---|---|---|
| 항목 1 해소 | `list_missing_managed_files` 본문 | `case "$diff_line" in "Only in $source_directory"*)` — `grep -E` 가 사라졌다. 표와 일치. **이미 원장 행 `T27-13` 이 이 자리를 물고 있다** |
| 항목 2 | `check_directory_conflict` 첫 분기 | `[[ ! -d "$target_directory" \|\| "$force_overwrite" == "true" ]]` → `return 0`. 목록·백업 어느 쪽도 없다. 표와 일치 |
| 항목 3 | `check_no_symlink_targets` · `copy_directory_contents` | 가드는 세 최상위 디렉토리에 `[[ -L ]]` 만 본다. 복사는 `cp -R "$source_directory/." "$target_directory/"`. 표와 일치 |
| 항목 3 트윈 | `hub/install.sh` 의 `check_preconditions` · `copy_managed_bin_files` | **표에 없다** — 같은 결함이 허브 설치기에도 있다. §2-B 신규 3 |
| 항목 4 | `save_manifest_file` · `build_files_ledger_json` · `read_installed_ledger_hash` | 절단 쓰기 + 미이스케이프 삽입. **추가로 대장 *읽기* 도 미이스케이프다** — `read_installed_ledger_hash` 가 `grep -F "\"$relative_path\":"` 로 조회한다. 쓰기만 고치면 조회가 어긋난다(§9-4) |
| 항목 5 | `resolve_target_paths` 와 `grep -n HOME install.sh` | project 스코프는 `target_base_dir="$PWD"` 뒤에 `is_symlinked_path` 검사만 있다. **project 경로에는 `$HOME` 참조가 하나도 등장하지 않는다** — 그래서 `set -u` 관련 신규 고려가 생긴다(§9-5) |
| 항목 6 | `perform_uninstall` | `uninstall-hooks --json \|\| true` · `uninstall-statusline --json \|\| true` 그대로. `stop_server_or_abort` 만 고쳐졌다. 표와 일치 |
| 항목 6 테스트 지점 | `tests/run.sh` 의 `T25-26` | **표에 없는 유리한 사실** — 이미 샌드박스 `HOME` + 스텁 `hub.py` 로 `hub/install.sh --uninstall` 을 실행하고 `server-stop` 실패 시 `bin/` 보존을 단언한다. 항목 6 의 테스트는 그 스텁에 분기 하나를 더하는 것으로 끝난다 |
| 항목 7 | `_load_settings` · `_validated_hooks_container` · `statusline_owner` | 반환 타입 `dict \| None` 인데 `json.loads` 결과를 무검사 반환. **파급이 표보다 넓다** — `statusline_owner` 도 `settings.get(...)` 를 부르므로 statusline 3경로도 같이 죽는다(§9-7) |
| 항목 8 | `commands/harness-update.md` 「Phase 4 — REINSTALL」 | 「(for small diffs) the diff content install.sh already printed」 존재. `report_directory_differences` 는 `diff -rq` 요약행만 찍는다. 표와 일치. **같은 문단에 `manifest v2's files field` 라는 낡은 표기가 하나 더 있다** — 현재 `MANIFEST_VERSION` 은 그 값이 아니다(§9-8 편승) |
| 항목 9 | 세 파일 frontmatter | 없다. 표와 일치. **`grep -rln 'disable-model-invocation' commands/` 가 빈 결과다** — 이 키를 쓰는 커맨드가 저장소에 처음 들어온다(선례 신설, §9-9) |
| 항목 10~13 | `fetch_rate_limit_capture` · `_classify_http_error` | 표와 일치. **항목 12 는 3개 모듈을 가로지르는 데이터 모델 변경이다** — `UsageApiPollState`·`next_usage_api_poll_state`·`_run_usage_api_poll_cycle` (§9-12) |
| 항목 10 의 숨은 비용 | `tests/hub/test_hub_usage_fetch.py` | **표에 없다** — 기존 테스트가 `mock.patch.object(hub_usage_fetch.urllib.request, "urlopen", ...)` 로 모킹한다. opener 로 바꾸면 그 모킹 지점이 사라진다. 영향 규모는 `grep -n 'urlopen' tests/hub/test_hub_usage_fetch.py` 로 센다(§9-10) |
| 항목 14 | `list_missing_managed_files` · `list_differing_managed_files` | 둘 다 `2> /dev/null` + `\|\| true`. 표와 일치. **`diff` 는 차이 있음(1)과 오류(2 이상)를 다른 코드로 구분한다** — 고칠 때 1 을 오류로 오분류하면 정상 설치가 전부 막힌다(§9-14) |
| 이관 누락 2건 | `full-audit-2026-08.md` 의 감사 행 vs `audit-remediation.md` §9 세 표 | **표에 없다** — 감사 행 2건이 편승·후속 PRP·범위 밖 기록 **어느 표에도** 들어가지 않았다. §2-B 신규 1·2 |
| 상시 컨텍스트 예산 | 이 PRP 의 대상 파일 목록 | `CLAUDE.md`·`rules/README.md`·`rules/common/`·`rules/workflow/` 를 건드리는 항목이 없다 → `T26` 4중 등식 연쇄는 이 PRP 의 범위 밖 |

---

## 1. 요구사항 요약

감사가 낸 쉘·설치 경계 결함을 고쳐, **설치기와 허브의 「대상 밖 쓰기·조용한 통과·정지 수단
소멸」 세 실패 형태를 닫는다.** 세 형태가 이 PRP 의 실제 축이다 — 심링크 관통과 미이스케이프
JSON 은 대상 밖에 쓰는 형태고, 삼킨 `diff` 오류와 비객체 `settings.json` 은 조용히 통과하거나
트레이스백으로 죽는 형태고, `--uninstall` 의 `|| true` 는 복구 수단이 함께 사라지는 형태다.
셋 다 「사용자가 손으로 되돌리기 어려운 상태」로 수렴하기 때문에 한 PRP 로 묶인다.

### 성공 기준 (검증 가능한 형태)

1. 관리 경로에 심볼릭 링크가 있으면 루트·허브 설치기가 **쓰기 전에** 중단한다 — 샌드박스
   `HOME` 픽스처로 재현하고 exit 코드와 링크 대상 파일의 불변을 단언한다.
2. `diff` 자체가 실패하면 「결측 없음」이 아니라 실패로 보고된다 — 그 분기에 도달하는 픽스처를
   만들고, 도달했음을 뮤테이션 원장 행으로 못박는다.
3. `--force` 가 사용자 수정본을 지울 때 백업 파일이 남고 목록이 표시된다.
4. `hub/install.sh --uninstall` 은 훅·statusLine 제거가 실패하면 `bin/` 을 지우지 않는다.
5. `settings.json` 최상위가 객체가 아니면 트레이스백 대신 `ok:false` + 사유를 낸다.
6. 사용량 API 호출이 리다이렉트를 따라가지 않고, 응답 읽기에 상한이 있고, TLS 검증 실패가
   연결 실패와 다른 어휘로 보고된다.
7. 4종 정본 검증 명령이 전부 완주한다(§10-0).

---

## 2. 이관 항목 인벤토리

### 2-A. 이관된 14건의 재계수

메인 세션의 재검증을 그대로 받는다. 항목 1(grep 미이스케이프)은 커밋 `81bbec5` 이 해소했고
원장 행 `T27-13` 이 그 자리를 이미 물고 있으므로 **범위에서 뺀다.** 남는 13건에 아래 ID 를
붙인다 — 이 PRP 안에서만 쓰는 식별자다.

| ID | 대상 심볼 | 결함 | 성격 | 단계 |
|---|---|---|---|---|
| **H1** | `install.sh` `list_missing_managed_files`·`list_differing_managed_files` | `diff` 자체의 오류를 삼켜 「결측 없음」으로 만든다 | 국소 + fail-loud 전환 | S1 |
| **H2** | `install.sh` `save_manifest_file`·`build_files_ledger_json`·`read_installed_ledger_hash` | 비원자적 절단 쓰기 + JSON 미이스케이프(쓰기·읽기 양쪽) | 국소 | S1 |
| **H3** | `install.sh` `check_no_symlink_targets` | 관리 경로 **안**의 심링크를 `cp -R` 가 관통한다 | 국소 + 가드 확장 | S1 |
| **H4** | `install.sh` `resolve_target_paths` | `--scope project` 가 `$PWD == $HOME` 를 수용 | 국소 | S1 |
| **H5** | `install.sh` `check_directory_conflict` | `--force` 가 목록도 백업도 없이 덮어쓴다 | 동작 추가 | S2 |
| **H6** | `commands/harness-update.md` 「Phase 4 — REINSTALL」 | install.sh 가 diff 내용을 보여준다는 허위 기술 | 문면 | S2 |
| **H7** | `commands/harness-update.md`·`prp-commit.md`·`prp-pr.md` frontmatter | `disable-model-invocation` 부재 | 문면 + 신규 가드 | S2 |
| **H8** | `hub/install.sh` `perform_uninstall` | 훅·statusLine 제거 실패를 `\|\| true` 로 삼킨 채 `bin/` 삭제 | **정책 결정** | S3 |
| **H9** | `hub/bin/hub_settings.py` `_load_settings` | 최상위 비객체 유효 JSON → `AttributeError` | 국소 | S4 |
| **H10** | `hub/bin/hub_usage_fetch.py` `fetch_rate_limit_capture` | 리다이렉트로 Bearer 토큰 재전송 | **정책 결정** | S4 |
| **H11** | 〃 | 응답 무제한 읽기 + 키 구조 무제한 기록 | 국소 + 어휘 추가 | S4 |
| **H12** | 〃 `_classify_http_error` | 429 의 `Retry-After` 를 버린다 | **데이터 모델 변경** | S4(보류 후보) |
| **H13** | 〃 `fetch_rate_limit_capture` 의 `except (URLError, OSError)` | TLS 검증 실패가 `network_error` 로 접힌다 | 어휘 추가 | S4 |

### 2-B. 신규 발견 — 감사 행인데 어느 이관 표에도 없다

`full-audit-2026-08.md` 의 감사 행과 `audit-remediation.md` §9 의 세 표(편승 / 후속 PRP 3건 /
범위 밖 기록)를 대조하다 나왔다. 아래 2건은 감사가 지적했는데 **세 표 어디에도 실리지 않아**
조용히 떨어졌다. 이관 대장이 「조용히 빠뜨리지 않는다」를 표제로 달고 있으므로, 이 PRP 가
줍는 것이 그 표제와 정합한다.

| ID | 대상 심볼 | 감사 지적 | 내가 확인한 것 | 판정 |
|---|---|---|---|---|
| **N1** | `hub/bin/hub_usage_fetch.py` `FAILURE_REASON_MESSAGES` | 「A-SEC 불변식 문장과 PRP 가 반환값이라고 지목한 `FAILURE_REASON_MESSAGES` 를 코드 어디서도 읽지 않는다」(미검증) | `grep -rn FAILURE_REASON_MESSAGES hub tests commands docs` 의 hit 는 ① 정의 자리 ② 모듈 docstring ③ `tests/run.sh` 의 `T25-60`(이름 존재만 `grep -qF`) ④ 설계 문서 언급. **소비하는 코드가 없다.** 실제로 화면·`/hub status` 에 나가는 것은 `record_usage_api_failure(reason)` 가 기록한 **원어휘 키**다 | **유효** |
| **N2** | `hub/bin/hub_settings.py` `_hub_hook_entry` | 「설치되는 훅 엔트리에 `timeout` 이 없어 행(hang) 방어가 규격 기본값에 맡겨진다」(CONFIRMED) | `grep -n timeout hub/bin/hub_settings.py` 가 빈 결과다. `audit-remediation.md` 의 `hub_settings` 언급은 전부 `E-1`(테스트 추가) 계열이고 이 항목이 아니다 | **유효** |
| **N3** | `hub/install.sh` `check_preconditions`·`copy_managed_bin_files` | (감사에 없다 — H3 를 설계하다 발견) | `check_preconditions` 는 `is_symlinked_path "$TARGET_HUB_DIR"` 만 본다. `copy_managed_bin_files` 는 `cp "$source_file" "$TARGET_BIN_DIR/"` — `$TARGET_BIN_DIR/hub.py` 가 심링크면 관통한다. H3 와 **같은 결함의 트윈** | **유효** |

**N1·N2 는 이 PRP 의 범위에 넣는 것을 권고하고 승인 항목으로 올린다**(§14 승인 3). 근거:
둘 다 H10~H13 이 여는 것과 같은 파일이고(N1 은 같은 모듈, N2 는 H9 와 같은 모듈), 「이번에
어차피 여는 파일」이 `audit-remediation.md` 가 편승을 판정한 기준이다. **N3 는 H3 와 같은
결함이므로 별도 승인 없이 H3 와 함께 처리한다** — 루트 설치기만 고치고 허브 설치기를 남기면
같은 벡터가 열린 채로 「고쳤다」가 된다.

**N1 은 H13 의 선행이다.** H13 은 새 실패 어휘를 하나 더한다. 아무도 읽지 않는 dict 에 항목을
더하는 것은 죽은 코드를 늘리는 것이므로, N1 을 먼저(또는 함께) 해소하지 않으면 H13 의 산출물
절반이 태어날 때부터 죽어 있다.

---

## 3. 분할 권고 — 4단계

**13건(+신규 3건)을 한 회차에 하지 않는다.** 근거 셋:

1. **검수 왕복 상한이 3회다**(`rules/workflow/role-separation.md` §3). 16건을 한 커밋에
   넣으면 1회차 지적이 수십 건이 되고 상한 안에 수렴할 가능성이 낮다. 3회 FAIL 은 재설계
   신호이므로 분할이 비용이 아니라 보험이다.
2. **검증 표면이 갈린다.** S1~S3 은 `bash tests/run.sh`(샌드박스 `HOME` 실행), S4 는
   `python3 -m unittest discover -s tests/hub` 가 판정한다. 한 커밋에 섞으면 실패가 났을 때
   원인 범위가 두 하네스에 걸쳐 넓어진다. 반대로 나누면 각 단계가 **한 명령으로 판정된다.**
3. **정책 결정 2건에 승인 게이트가 붙는다**(H8·H10). 승인 대기가 정책 판단이 필요 없는
   국소 수정 4건(S1)을 볼모로 잡지 않게 분리한다.

분할 축은 **파일별이 아니라 「검증 표면 + 정책 의존성」**이다. 결과적으로 파일별과 거의
같아지지만, 축이 파일이면 H6(문면)이 H5(코드)와 갈라져 §9-6 의 인과(H6 의 문면이 H5 의
동작을 서술한다)가 끊긴다.

| 단계 | 내용 | 항목 | 선행 | 단독 착지 가능성 | 판정 명령 |
|---|---|---|---|---|---|
| **S1** | `install.sh` 무결성 계열 — `diff` fail-loud · 매니페스트 원자성·이스케이프 · 관리 경로 심링크 가드(루트+허브) · `$PWD == $HOME` | H1, H2, H3, H4, N3 | 없음 | **완전** — 검출력만 늘고 기존 시나리오는 그대로여야 한다 | `bash tests/run.sh` |
| **S2** | `--force` 백업 + 그 동작을 서술하는 커맨드 문면 + frontmatter | H5, H6, H7 | **S1 필수**(H2 가 대장 조회를 고친다 — §9-5 인과) | **중간** — H5 의 분류가 S1 의 대장 조회에 의존한다 | `bash tests/run.sh` |
| **S3** | `hub/install.sh --uninstall` 제거 순서 정책 | H8 | 없음 | **완전** — S1·S2 와 파일이 겹치지 않는다 | `bash tests/run.sh` |
| **S4** | `hub/bin` 파이썬 — 최상위 스키마 · 리다이렉트 · 읽기 상한 · TLS 어휘 · 죽은 어휘 dict · 훅 timeout | H9, H10, H11, H13, N1, N2 | 없음(N1 은 H13 의 **내부** 선행) | **높음** | `python3 -m unittest discover -s tests/hub` |
| **(보류)** | 429 `Retry-After` 반영 | H12 | S4 | — | — |

**S3·S4 는 S1·S2 와 파일이 겹치지 않으므로 순서를 교환할 수 있다.** 권고 순서는
S1 → S2 → S3 → S4 이고, 승인이 S3·S4 의 정책 항목에서 막히면 S1·S2 를 먼저 착지시킨다.

### H12 를 보류 후보로 두는 근거

감사 자신이 「방향은 보수적이지만 패널이 최대 60분 얼어붙는다」로 적었다 — 즉 **안전 방향의
과보수**이고 데이터 유실이나 대상 밖 쓰기가 아니다. 그런데 고치려면
`fetch_rate_limit_capture` 의 반환 튜플 · `UsageApiPollState` 필드 ·
`next_usage_api_poll_state` 시그니처 · `hub_server._run_usage_api_poll_cycle` 호출부까지
**4개 자리의 계약이 함께 움직인다**(§9-12). 「낮은 심각도 × 넓은 파급」 조합이라 다른 15건과
같은 회차에 넣으면 검수 지적의 대부분을 이것이 차지할 위험이 있다. **승인 항목 4 로 올려
사용자가 「이번에 한다 / 다음 PRP 로 넘긴다」를 고르게 한다.**

---

## 4. 정책 결정 1 — H8: `--uninstall` 이 제거 실패를 만났을 때

### 4-1. 선례가 무엇을 정했는가

`stop_server_or_abort` 는 이미 「실패 시 `--force` 없이는 중단」을 선택했고, 그 근거를 함수
위 주석에 남겼다 — 삼키면 「돌고 있는 서버 + 그 서버를 끌 유일한 수단의 소멸」이 된다.

### 4-2. 훅 쪽에 그 논거가 그대로 성립하는가

**성립한다. 단 심각도의 결이 다르다.** 두 갈래를 나눠 본다.

- **동작 피해**: 잔존 훅의 커맨드는 `python3 "$HOME/.claude/hub/bin/hub_hook.py"
  >/dev/null 2>&1 || true` 다 — 파일이 사라져도 `|| true` 와 stderr 봉쇄 때문에 조용히 exit 0
  이다. 즉 **서버처럼 계속 「돌지」는 않는다.** 이 결에서는 서버보다 가볍다.
- **복구 수단**: 그 엔트리를 마커로 찾아 지우는 수단은 `hub.py uninstall-hooks`
  (→ `hub_settings.strip_hub_hooks`)이고, 그 파일은 지금 지우려는 `bin/` 안에 있다. 지운 뒤에
  남는 복구 경로는 사용자가 `~/.claude/settings.json` 을 손으로 열어 마커 문자열이 든 엔트리를
  골라 지우는 것이다. **이 결에서는 서버와 같은 형태다** — 복구 수단이 함께 사라진다.

`settings.json` 은 이 저장소가 「사용자가 명시적으로 부를 때만 손댄다」로 소유권을 선언한
파일이고(`hub_settings.py` 모듈 docstring), 그런 파일을 손으로 고치라고 안내하는 것은 그
선언과 어긋난다. **복구 수단 쪽 논거가 결정적이므로 선례를 따른다.**

### 4-3. 결정

**`ok:false` 면 `--force` 없이 `rm -rf` 를 중단한다.** 세 하위 명령(`server-stop` ·
`uninstall-hooks` · `uninstall-statusline`)에 같은 게이트를 적용한다.

세부 결정 넷:

1. **판정은 JSON 파싱으로 한다** — `stop_server_or_abort` 가 이미 문자열 매칭을 기각한
   근거(`json.dumps` 의 키-값 공백 규칙은 보장된 계약이 아니다)가 그대로 적용된다.
2. **`uninstall_statusline` 의 `{"ok": true, "removed": false}` 는 실패가 아니다** — 남의
   statusLine 이거나 애초에 없을 때의 정상 무동작이다. `ok` 만 보는 게이트가 이 경우를 옳게
   통과시킨다(별도 분기 불필요).
3. **중단은 부분 적용 상태를 남긴다** — `server-stop` 이 이미 성공한 뒤 `uninstall-hooks` 가
   실패하면 「서버는 멈췄고 `bin/` 은 남았다」가 된다. 그 상태를 사용자에게 **명시적으로
   보고한다**(어느 단계까지 갔는지). 조용히 중단하면 사용자가 서버 상태를 오해한다.
4. **`--force` 경로에는 수동 복구 절차를 인쇄한다** — 「그래도 강행」을 고른 사용자에게만
   필요한 정보이고, 중단 경로에서는 `--force` 를 안내하는 것으로 충분하다.

### 4-4. 구현 형태 — 헬퍼 추출

세 자리가 같은 구조(실행 → stdout 반향 → `ok` 파싱 → `--force` 우회 → 중단)를 갖는다.
**공용 헬퍼 하나로 모은다.**

```bash
# hub/install.sh
# 인자: hub.py 경로 · 하위 명령 · 실패 시 중단 사유 문장
# 반환: 0(ok 또는 --force 우회) / 1(중단)
run_hub_subcommand_or_abort() { ... }
```

`stop_server_or_abort` 는 이 헬퍼의 호출 한 줄로 대체한다. 근거는 DRY 가 아니라 **이 저장소가
이미 겪은 드리프트**다 — `tests/run.sh` 의 `FAILURE_REPORT_LINE_PATTERN` 상수 주석이
「두 함수가 이 리터럴을 각자 들고 있어, 다섯 번째 보고 함수를 더하는 수정이 한쪽만 고치면 두
검사가 서로 다른 분모를 보게 됐다」를 기록했다. 게이트를 3벌 복제하면 같은 형태가 된다.

**대안(기각)**: 계속 진행하되 수동 복구 절차만 안내한다. 기각 근거 — (i) 형제 선례와
불일치하고, (ii) 안내하는 절차가 소유권 선언과 어긋나는 `settings.json` 수동 편집이며,
(iii) 「알고도 강행」은 `--force` 라는 자리가 이미 있다.

---

## 5. 정책 결정 2 — H10: 리다이렉트 정책

### 5-1. 불변식 A-SEC 이 요구하는 것에서 출발한다

`hub_usage_fetch.py` 모듈 docstring 이 선언한 것은 두 문장이다 — 「accessToken 이 존재하는
유일한 파일이다」와 「누가 토큰을 볼 수 있는가를 이 파일 하나의 질문으로 만들기 위해
격리했다」. 두 번째 문장이 이 결정의 기준이다: **토큰의 수신자가 이 파일을 읽어서 결정될 수
있어야 한다.**

리다이렉트를 따라가면 수신자는 응답 헤더가 지정하는 임의의 호스트가 된다 — 이 파일을 읽어서
결정되지 않는다. 로컬 노출(로그·파일·HTML)만 막고 네트워크 egress 를 열어 둔 상태다.

### 5-2. 세 선택지

| 선택지 | 기제 | A-SEC 기준 판정 |
|---|---|---|
| (a) 리다이렉트를 따라가지 않는다 | `HTTPRedirectHandler` 하위 클래스의 `redirect_request` 가 `None` 을 돌려주는 opener 를 쓴다 | **수신자 = 이 파일의 `USAGE_API_URL` 상수. 파일 하나로 결정된다** |
| (b) 같은 호스트만 허용 | 새 URL 의 scheme·host 를 비교해 통과시킨다 | 결정 가능하지만, scheme 강등·authority 의 userinfo·대소문자·IDN 정규화를 각각 옳게 처리해야 한다. 비교 로직 자체가 새 공격면이다 |
| (c) 리다이렉트 시 헤더를 벗긴다 | `Authorization` 을 지운 채 따라간다 | 토큰은 안 새지만 요청이 401 로 돌아와 `http_unauthorized`(「재로그인이 필요합니다」)로 보고된다 — **H13 이 없애려는 「접힘」을 새로 만든다** |

### 5-3. 결정: (a) — 리다이렉트를 따라가지 않는다

근거 셋:
1. A-SEC 이 요구하는 「파일 하나로 결정된다」를 (a)만 **추가 로직 없이** 만족한다.
2. (b)가 사는 대가(같은 호스트 리다이렉트를 따라갈 수 있음)를 지금 필요로 하는 소비자가 없다.
   현재 엔드포인트는 상수 하나다 — YAGNI(`rules/common/karpathy-guidelines.md` #2).
3. (c)는 보안 이벤트를 인증 만료로 오표시한다. H13 과 정면으로 어긋난다.

**차단된 리다이렉트를 `http_error` 로 접지 않는다.** 그것은 H13 과 같은 접힘이다. 새 어휘
`redirect_blocked` 를 더한다 — 그리고 이 어휘는 실제로 발화한다: 캡티브 포털(호텔·공항
WiFi)이 302 를 돌려주는 것이 흔한 형태다. 「일어날 수 없는 상황」에 대한 처리가 아니다.

### 5-4. 기존 테스트 모킹 지점이 사라진다 (표에 없던 비용)

`urlopen` 은 핸들러를 받지 않으므로, 리다이렉트를 막으려면 opener 를 써야 하고 그러면
`urllib.request.urlopen` 을 더 이상 부르지 않는다. 기존 `FetchRateLimitCaptureTest` 는 그
이름을 모킹한다(§0 표). 규모는 `grep -n 'urlopen' tests/hub/test_hub_usage_fetch.py` 로 센다.

**대응**: 모듈 프라이빗 이음선 하나를 만들어 테스트가 그 한 점을 모킹하게 한다.

```python
def _open_usage_api_request(request: urllib.request.Request):
    """리다이렉트를 따라가지 않는 opener 로 1회 보낸다(불변식 A-SEC — §5-3)."""
```

`urllib.request.install_opener()`(전역 설치)는 **쓰지 않는다** — 전역 가변 상태 금지
(`rules/workflow/code-quality-baseline.md` 「설계 원칙」). opener 는 호출마다 지역으로 만든다.

---

## 6. 영향 범위 (수정·추가 파일)

| 파일 | 단계 | 조치 | 이유 |
|---|---|---|---|
| `install.sh` | S1 | UPDATE | H1·H2·H3·H4 |
| `install.sh` | S2 | UPDATE | H5 (`--force` 백업) |
| `hub/install.sh` | S1 | UPDATE | N3 (심링크 트윈) |
| `hub/install.sh` | S3 | UPDATE | H8 (제거 게이트 + 헬퍼 추출) |
| `commands/harness-update.md` | S2 | UPDATE | H6 문면 + H7 frontmatter |
| `commands/prp-commit.md` | S2 | UPDATE | H7 frontmatter |
| `commands/prp-pr.md` | S2 | UPDATE | H7 frontmatter |
| `hub/bin/hub_settings.py` | S4 | UPDATE | H9 · N2 |
| `hub/bin/hub_usage_fetch.py` | S4 | UPDATE | H10·H11·H13·N1 |
| `hub/bin/hub_collect.py` | S4 | UPDATE | **구현 시 정정(§6 원표 누락)** — N1 의 소비자 배치(§8-3·승인 3)가 `record_usage_api_failure` 의 payload 스키마를 늘린다. 이 함수의 소유 모듈이 여기라 S4 대상에서 빠져 있었다 |
| `hub/bin/hub_server.py` | S4 | UPDATE | **구현 시 정정(§6 원표 누락, H12 승인과 별개)** — `_run_usage_api_poll_cycle` 의 두 `record_usage_api_failure` 호출부가 `hub_usage_fetch.failure_reason_message(reason)` 를 구해 넘긴다. 원표는 이 호출부 변경을 "H12 승인 시"로만 적었는데, N1 배치(H12 와 무관하게 이번 회차에 승인됨)에도 같은 자리가 필요하다는 것을 놓쳤다 — 안 고치면 `failure_reason_message` 를 만들기만 하고 실제로는 아무도 부르지 않는 죽은 코드가 된다(§8-3 이 경고한 바로 그 실패 형태) |
| `hub/bin/hub_usage.py` | (H12 승인 시) | UPDATE | `UsageApiPollState`·`next_usage_api_poll_state` |
| `hub/bin/hub_server.py` | (H12 승인 시) | UPDATE | `_run_usage_api_poll_cycle` 의 4-튜플 반환·`Retry-After` 배선(N1 배선과는 다른 변경 — H12 가 승인되면 같은 파일을 두 번째 이유로 또 고친다) |
| `tests/run.sh` | S1·S2·S3 | UPDATE | 신규 서브체크 + 래칫 상수 |
| `tests/mutations.tsv` | S1·S2·S3 | UPDATE | 신규 변조행 + 헤더 인용 갱신(S3 는 §10-3 판정에 따라 변조행 없이 면제행만 추가) |
| `tests/hub/test_hub_settings.py` | S4 | UPDATE | H9 · N2 |
| `tests/hub/test_hub_usage_fetch.py` | S4 | UPDATE | H10·H11·H13·N1 + 모킹 이음선 이전 |
| `tests/hub/test_hub_collect.py` | S4 | UPDATE | **구현 시 정정(§6 원표 누락)** — `record_usage_api_failure` 의 `message` 인자(U-R8) |
| `tests/hub/test_hub_server.py` | S4 | UPDATE | **구현 시 정정(§6 원표 누락, §5-4 비용의 실제 발현)** — N1 두 호출부 배선 테스트 2건. **그리고 별개로 더 심각한 것 하나** — `RunUsageApiPollCycleDeepNestingRegressionTest._patch_credential_and_transport` 가 `hub_usage_fetch.urllib.request.urlopen` 을 직접 모킹하고 있었다(§5-4 가 "표에 없던 비용"으로 경고한 것과 같은 종류의 누락인데, 그 경고 자체도 `test_hub_usage_fetch.py` 만 지목했다). H10 이후 `_open_usage_api_request` 가 `opener.open()` 을 직접 부르므로 `urlopen` 은 더 이상 호출되지 않는다 — 옮기지 않았으면 이 mock 이 조용히 무력해져 그 테스트가 (가짜 토큰이긴 하나) 실제로 `api.anthropic.com` 에 네트워크 연결을 시도했을 것이다. `_FakeUrlopenResponse.read()` 도 H11 의 `response.read(상한+1)` 호출과 맞물리도록 size 인자를 받게 고쳤다 |

**새 파일은 만들지 않는다.** **`removals.txt` 는 건드리지 않는다** — 관리 파일
(`rules/`·`agents/`·`commands/`)의 삭제·개명이 없다. `hub/install.sh` 의 셸 함수 개명은 관리
파일이 아니므로 툼스톤 대상이 아니다(`tests-hardening` 의 `A14` 판정과 같은 근거).

### 모듈 경계 — 이 PRP 가 지켜야 하는 것

프로젝트 `CLAUDE.md` §2 의 레이어 구성을 따른다.

- **배포 채널(`install.sh`)**: 순수 bash, 외부 의존성 0. H1~H5 는 이 제약 안에서 해결한다 —
  JSON 이스케이프에 `python3`·`jq` 를 끌어오지 않는다(§9-2).
- **허브 런타임(`hub/`)**: python3 표준 라이브러리 전용. H10 의 opener 는 `urllib.request`
  안에서 끝난다 — 새 의존성이 없다.
- **레이어 간 통신은 manifest 의 해시 대장뿐이다.** H2 가 그 채널의 쓰기·읽기 양쪽을
  고치므로 **이 PRP 에서 파급이 가장 넓은 항목이다**(`tests-hardening` 이 `A6` 에
  「매니페스트는 유일한 레이어 간 통신 채널」을 근거로 우선순위 최상을 준 것과 같은 이유).
- **`hub/install.sh` 는 루트 `install.sh` 와 완전히 독립이다**(그 파일 상단 선언). N3 를
  고칠 때 루트의 헬퍼를 공유하려 들지 않는다 — 각자 자기 파일 안에서 해결한다.

---

## 7. 데이터 모델

### 7-1. `FailureReason` 어휘 확장 (S4)

`hub_usage_fetch.py` 의 `FailureReason` Literal 과 `FAILURE_REASON_MESSAGES` dict 에 셋을
더한다. 둘은 **같은 커밋에서 함께** 움직여야 한다(§10-4 의 완비 테스트가 강제한다).

| 새 어휘 | 언제 | 왜 기존 어휘로 접지 않는가 |
|---|---|---|
| `redirect_blocked` | 3xx 를 받았고 따라가지 않았다 | `http_error`(그 외 4xx/5xx)로 접으면 「서버 오류」로 읽힌다. 실제로는 응답이 정상이고 **우리가 거부한** 것이다 |
| `tls_verify_failed` | 인증서 검증 실패 | `network_error`(「연결할 수 없습니다」)로 접으면 사용자가 「WiFi 문제」로 읽는다. H13 이 지적한 그 접힘이다 |
| `response_too_large` | 응답 본문이 상한을 넘었다 | `schema_mismatch` 는 계약상 `response_keys` 자기 진단 창구를 함께 준다. 잘린 본문으로는 그 창구를 채울 수 없어 계약이 조건부로 거짓이 된다 |

**대안(기각)**: `response_too_large` 를 `schema_mismatch` 로 접는다. 「300KB 본문은 우리가 아는
모양이 아니다」로 읽을 수 있어 어휘 팽창을 3에서 2로 줄인다. 기각 근거는 위 표 세 번째 칸 —
그 어휘가 약속한 진단 창구를 채울 수 없다. 어휘 3개 추가에 대한 승인은 §14 승인 5.

### 7-2. 응답 상한 상수 (S4, H11)

저장소 안 선례를 따른다 — `hub_server.py` 의 `SERVER_LOG_MAX_BYTES` ·
`hub_workflow.py` 의 `WORKFLOW_RUN_MAX_BYTES` 가 「로컬 신뢰 파일에는 상한을 걸어 둔」 자리다.

```python
USAGE_API_MAX_RESPONSE_BYTES: int      # 응답 본문 상한
USAGE_API_MAX_RESPONSE_KEY_ENTRIES: int  # response_keys 목록 길이 상한
```

두 번째가 필요한 이유: 감사 지적은 「무제한으로 읽고 **그 키 구조를 무제한으로 디스크에
쓴다**」 두 갈래다. 본문 상한만 걸면 상한 안의 본문이 만드는 대량 키 목록이
`last_usage_api_error.json` 에 그대로 들어간다. 목록이 상한을 넘으면 **잘렸음을 알리는
표지 항목**을 마지막에 넣는다 — 조용히 자르면 자기 진단 창구가 거짓말을 한다.

값은 구현 시 정한다. 판단 기준만 고정한다: 정상 응답 크기의 여유 배수이면서,
`SERVER_LOG_MAX_BYTES` 처럼 「명백히 병리적」을 가르는 자리. 값을 지금 못박지 않는 이유는
실제 응답 크기를 이 설계가 재보지 않았기 때문이다.

**구현이 정한 것(결정 A, §15 남은 질문 3의 답)**: **실측하지 않았다** — 정상 응답 크기를
재려면 사용자의 OAuth 토큰으로 실제 사용량 API 를 호출해야 하는데, 크기 하나를 재기 위해
자격증명을 네트워크로 보내는 것은 정당화되지 않는다. 위 문단의 「정상 응답 크기의 여유
배수」라는 표현은 그대로 쓰지 않는다 — 재지 않은 값을 배수라고 쓰면 거짓이기 때문이다.
대신 파서가 실제로 읽는 필드 구조에서 유도했다: `parse_usage_api_response` 가 쓰는 것은
최상위 `five_hour`·`seven_day` 두 객체뿐이고 각각 `utilization`(숫자)·`resets_at`(ISO 8601
문자열) 두 필드라 알려진 스키마는 수백 바이트 안쪽이다.

- `USAGE_API_MAX_RESPONSE_BYTES = 64 * 1024`(64KiB) — `SERVER_LOG_MAX_BYTES`(256*1024)보다
  작게 잡았다. 그 상수는 신뢰하는 로컬 파일의 상한이고 이 상수는 신뢰하지 않는 원격 응답의
  상한이라, 같은 값이 아니라 더 좁은 값이어야 한다고 판단했다. 64KiB 는 알려진 스키마의
  수백 배 여유를 주면서 캡티브 포털의 HTML 로그인 페이지 같은 「명백히 병리적」 응답을 가른다.
- `USAGE_API_MAX_RESPONSE_KEY_ENTRIES = 100` — 알려진 스키마의 리프는 4개
  (`five_hour.utilization`·`five_hour.resets_at`·`seven_day.utilization`·`seven_day.resets_at`)
  뿐이라 100 은 스키마가 크게 늘어도 남는 여유로 판단했다.

두 값 모두 `hub_usage_fetch.py` 의 상수 주석에 이 유도 근거와 "실측이 아니다"라는 사실을
명시했다(`USAGE_API_MAX_RESPONSE_BYTES`·`USAGE_API_MAX_RESPONSE_KEY_ENTRIES`).

**구현 2회차가 추가한 것(검수 접지 MEDIUM 반영)**: `USAGE_API_MAX_RESPONSE_KEY_ENTRIES` 는
항목 **수**만 가둔다 — `describe_json_key_structure` 의 각 항목이 조상 키 경로 전체를
문자열로 담으므로, 항목 수가 상한 이내여도 총 **바이트**는 항목 수 × 경로 길이로 증폭될 수
있다(검수자 실측: 깊이 60·키 길이 1000·리프 100 의 61,440바이트 본문 → 항목 수는 정확히
상한인데 `last_usage_api_error.json` 은 6,007,530바이트). 그래서
`USAGE_API_MAX_RESPONSE_KEY_BYTES = 8 * 1024`(8KiB)를 더해 `_capped_response_key_structure`
가 개수·바이트 양쪽을 본다 — 유도 근거는 같은 방식이다: 알려진 스키마의 response_keys 총
바이트는 리프 4개 × 경로 30자 안팎으로 200바이트를 넘지 않고, 8KiB 는 그 수십 배 여유를
주면서 위 재현 같은 증폭을 자른다. 개수·바이트 중 하나만
넘어도, 둘 다 넘어도 표지 항목은 하나다 — 표지가 둘이 되면 자기 진단 창구 자체가 이상하게
읽힌다.

### 7-3. `UsageApiPollState` (H12 — 승인 시에만)

현재 상태는 `last_attempt_at_ms` · `consecutive_failures` · `forced_multiplier` 셋이고,
429 는 `forced_multiplier = USAGE_API_RATE_LIMITED_MULTIPLIER` 로 즉시 상한으로 점프한다.

**권고안: `forced_multiplier` 를 `forced_delay_ms: int | None` 로 교체한다.** 필드를 더하지
않고 바꾼다.

- 429 + `Retry-After` 유효 → 그 값(ms 환산, 아래 clamp)
- 429 + 헤더 없음/무효 → 현재와 같은 값(`base × USAGE_API_RATE_LIMITED_MULTIPLIER × 1000`)
- **clamp**: `[0, base × USAGE_API_BACKOFF_MAX_MULTIPLIER × 1000]`. 상한을 기존 천장으로
  두면 **최악값은 지금과 같고 통상값만 짧아진다** — 감사가 지적한 「최대 60분 얼어붙는다」의
  개선이 정확히 이 방향이다. 하한 0 은 적대적/오작동 헤더가 음수·거대값을 넣는 경우를 막는다.

`next_usage_api_poll_state` 가 delay 를 계산하려면 `base_interval_seconds` 를 받아야 한다 →
시그니처가 늘어난다(§8-3).

**대안(기각)**: `forced_multiplier` 를 남기고 `forced_delay_ms` 를 **추가**한다. 시그니처
변경이 작다. 기각 근거 — 「기다릴 시간」을 정하는 기제가 둘이 되고, `usage_api_poll_delay_ms`
안에서 우선순위 규칙을 새로 만들어야 한다. 같은 판정을 두 출처가 나눠 갖는 형태를 이 모듈은
이미 기각했다(`_valid_usage_api_percentage` 가 `_valid_used_percentage` 를 재사용하는 이유:
「판정 규칙이 출처마다 갈리면 상태줄과 패널이 다른 숫자를 보이게 된다」).

**`Retry-After` 의 HTTP-date 형식은 받지 않는다.** 숫자(delta-seconds)만 해석하고, 그 밖의
표기는 헤더가 없는 것과 같이 취급한다. 근거: 날짜 파싱은 시계 오차·타임존 처리를 끌어오고,
지금 필요를 만든 엔드포인트가 요구하지 않는다(YAGNI). **한계**: 서버가 date 형식으로만
응답하면 이 수정의 이득이 그 경우에는 발생하지 않는다.

### 7-4. `install.sh` 의 데이터 모델 — manifest JSON (S1, H2)

매니페스트는 이 저장소의 유일한 레이어 간 통신 채널이다. 이 PRP 가 바꾸는 것은 **표현
규약**이고 스키마(키 집합·`version`)는 그대로다.

- **쓰기**: `build_files_ledger_json` 이 상대경로를, `build_manifest_json` 이 `repo_path` ·
  `target_base_dir` 를 JSON 문자열 자리에 넣는다 → 넣기 전에 `\` 와 `"` 를 이스케이프한다.
- **읽기**: `read_installed_ledger_hash` 가 `grep -F "\"$relative_path\":"` 로 조회한다 →
  **같은 이스케이프를 적용한 뒤** 조회한다. 한쪽만 고치면 이스케이프가 필요한 경로에서 조회가
  빈 문자열을 내고, `classify_differing_file` 이 그것을 「대장 없음 → modified」로 읽어
  정상 설치가 `--force` 를 요구하게 된다.
- **제어문자가 든 경로는 fail-closed 로 거부한다.** 이스케이프하지 않는다. 근거: 대장의
  **읽기 쪽이 줄 단위**(`grep`·`sed`)이므로 개행이 든 키는 읽기가 표현할 수 없다. 쓰기만
  가능하게 만들면 쓸 수 있지만 읽을 수 없는 대장이 생긴다. `validate_removals_file` 이 이미
  같은 방향의 fail-closed 선례다.

`MANIFEST_VERSION` 은 **올리지 않는다.** 키 집합이 그대로이고, 이스케이프는 지금까지도
「이스케이프가 필요 없는 경로」에서 같은 바이트를 내므로 기존 설치본과 호환된다.

---

## 8. 인터페이스 (공개 함수 시그니처)

### 8-1. `install.sh` (셸 함수 — 인자·반환 계약)

```bash
# H1 — 두 목록 함수는 이제 실패를 반환한다(이전: 항상 0)
# 반환: 0 = 목록을 stdout 에 냈다(빈 목록 포함) / 1 = diff 자체가 실패했다(사유는 stderr)
list_missing_managed_files   <source_directory> <target_directory>
list_differing_managed_files <source_directory> <target_directory>

# H3 — 신규. 관리 경로와 그 조상 디렉토리에 심볼릭 링크가 있으면 1
# check_no_symlink_targets 를 대체하지 않고 그 안에서 확장한다(호출부 유지)
check_no_symlink_targets                    # 반환: 0 안전 / 1 링크 발견(사유는 stderr)

# H2 — 신규 헬퍼. JSON 문자열 자리에 넣을 수 있게 이스케이프한다
# 제어문자가 들어 있으면 1 을 반환하고 stdout 에 아무것도 내지 않는다(fail-closed)
escape_json_string <raw_string>             # stdout: 이스케이프된 문자열

# H5 — 신규. --force 로 덮어쓸 modified 파일을 백업한다
# 반환: 0 = 백업 완료(0건 포함) / 1 = 백업 실패(설치를 중단시킨다)
backup_modified_managed_files <source_directory> <target_directory>
```

**호출부 변경**: `verify_managed_files_installed` · `install_directory` ·
`check_directory_conflict` 는 두 목록 함수의 명령 치환에 `|| return 1` 을 붙인다.

### 8-2. `hub/install.sh`

```bash
# H8 — 신규. stop_server_or_abort 를 이 호출로 대체한다
# 반환: 0 = ok:true 또는 --force 우회 / 1 = 중단
run_hub_subcommand_or_abort <hub_py_path> <subcommand> <abort_reason_sentence>

# N3 — 신규. TARGET_BIN_DIR 자신과 그 안의 배포 대상 경로에 심링크가 있으면 1
check_no_symlink_bin_targets                # 반환: 0 안전 / 1 링크 발견
```

### 8-3. `hub/bin` (파이썬 — 타입 명시)

```python
# H9 — 시그니처 불변. 반환 계약을 좁힌다: 최상위가 dict 가 아니면 None
def _load_settings() -> dict | None: ...

# N2 — 반환 dict 에 timeout 키가 추가된다(값은 모듈 상수)
def _hub_hook_entry() -> dict: ...
HOOK_TIMEOUT_SECONDS: int

# H10 — 신규(모듈 프라이빗). 테스트의 모킹 이음선이 여기로 이전한다
def _open_usage_api_request(request: urllib.request.Request): ...
class _NoRedirectHandler(urllib.request.HTTPRedirectHandler): ...

# N1 — 신규(공개). 고정 어휘를 사람이 읽는 문장으로 바꾼다 — dict 의 유일한 소비자
def failure_reason_message(reason: str) -> str: ...

# H11 — 신규 상수 2종 (§7-2)
USAGE_API_MAX_RESPONSE_BYTES: int
USAGE_API_MAX_RESPONSE_KEY_ENTRIES: int

# H12 (승인 시) — 시그니처가 늘어난다
def next_usage_api_poll_state(
    now_ms: int,
    state: UsageApiPollState,
    failure_reason: str | None,
    base_interval_seconds: int,
    retry_after_seconds: int | None = None,
) -> UsageApiPollState: ...

# H12 (승인 시) — 4-튜플로 늘어난다. 4번째는 http_rate_limited 일 때만 채워진다
def fetch_rate_limit_capture(
    now_ms: int,
) -> tuple[hub_usage.RateLimitCapture | None, FailureReason | None, list[str] | None, int | None]: ...
```

**N1 의 소비자를 어디에 붙이는가**: `failure_reason_message` 를 만들기만 하고 아무도 부르지
않으면 죽은 코드가 하나 늘 뿐이다. `record_usage_api_failure(reason)` 가 기록하는 payload 에
사람이 읽는 문장을 함께 넣어 `/hub status` 의 `usage_api_last_failure` 소비자가 원어휘 키와
문장을 같이 보게 한다. **이 배치는 승인 항목이다**(§14 승인 3) — payload 스키마가 늘어난다.

---

## 9. 항목별 처리 방향

### 9-1. H1 — `diff` 오류를 삼키는 두 함수 (S1)

`diff` 는 **같음(0) · 차이 있음(1) · 오류(2 이상)** 를 다른 코드로 구분한다. 지금 코드는
`2> /dev/null` 로 사유를 지우고 `|| true` 로 코드를 지운다.

수정 형태 — 출력과 상태를 한 번에 잡고 상태만으로 갈린다:

```bash
diff_output=$(diff -rq -x __pycache__ "$src" "$tgt" 2>&1) || diff_status=$?
if (( diff_status >= 2 )); then <사유와 diff_output 을 stderr 로> ; return 1 ; fi
# diff_status 0·1 은 정상 — diff_output 을 기존 case / grep 으로 필터한다
```

`2>&1` 로 바꿔도 목록이 오염되지 않는 이유: 두 함수의 필터가 이미 **알려진 두 모양만**
고른다(`Only in <src>*` / `^Files .* differ$`). `diff` 의 에러 문장은 어느 쪽에도 맞지 않아
목록에서 자연히 빠지고, 대신 실패 상태에서 사용자에게 보여줄 원문으로 쓰인다.

**`set -e` 함정**: `x=$(cmd) || status=$?` 형태를 쓴다. `if` 조건절 안에서 함수를 부르면
그 함수 내부에는 `set -e` 가 적용되지 않는다 —
`rules/common/karpathy-guidelines.md` 「실패 사례」가 이 저장소에서 실제로 겪은 것으로
기록한 함정이다.

**`note_failure` vs `record_failure` 판정**: 이 계열의 새 서브체크는 **뒤 검사의 전제가
되므로 `record_failure` + `return 1`** 을 쓴다(`tests/run.sh` 가 `note_failure` 위 주석에
명문화한 기준: 종속 서브체크는 `record_failure`).

### 9-2. H2 — 매니페스트 원자성과 이스케이프 (S1)

**원자성**: 같은 디렉토리의 임시 파일에 쓴 뒤 `mv -f` 로 교체한다(같은 파일시스템 안의
rename). 실패 경로에서 임시 파일을 지운다. 선례는 `hub_atomic_write.py` 와
`hub_settings._write_settings_atomically` 이고, 감사가 「저장소 자체 표준에 미달」이라고 쓴
그 표준이 이 둘이다.

**임시 파일명**: 고정 이름을 쓰지 않는다 — `_write_settings_atomically` 의 주석이
「고정된 임시 파일명을 공유하면 동시 쓰기가 뒤섞인 파일을 발행할 수 있다」를 검수 지적으로
기록했다. bash 에서는 `mktemp` 를 대상 디렉토리에 두고 쓴다.

**모드 보존**: `mktemp` 산출물의 모드가 기존 파일과 다를 수 있다. `_write_settings_atomically`
가 `shutil.copymode` 로 이 문제를 이미 만났다(검수 n1 — 「사용자의 권한이 0644 에서 조용히
0600 으로 바뀐다」). 같은 대응을 셸에서 한다.

**이스케이프**: 순수 bash 파라미터 확장으로 한다 — `\` 를 먼저, `"` 를 다음에. 순서가 규약이다
(먼저 `"` 를 바꾸면 그때 넣은 백슬래시를 두 번째 치환이 다시 바꾼다).
**`python3`·`jq` 를 부르지 않는다** — 「순수 bash, 외부 의존성 0」이 이 파일의 레이어 계약이다
(프로젝트 `CLAUDE.md` §2).

**읽기 쪽을 함께 고친다**(§7-4). 이것이 이 항목에서 가장 놓치기 쉬운 자리다.

### 9-3. H3 · N3 — 심링크 관통 (S1)

**무엇을 검사 대상으로 삼는가**가 이 항목의 설계 판단이다.

- 「세 디렉토리 아래의 모든 심링크를 거부」는 **오탐을 만든다** — 사용자가 자기 에이전트를
  `~/.claude/agents/` 에 심링크로 넣어 두는 것은 소유권 원칙상 우리 소관이 아닌데, 그 사용자의
  설치를 전부 막게 된다.
- 그래서 **우리가 배포하는 경로와 그 조상 디렉토리만** 검사한다. 관통이 일어나는 자리가 정확히
  거기다(`cp -R` 가 쓰는 대상). 열거는 `build_files_ledger_json` 이 이미 쓰는 것과 같은
  관리 파일 열거를 재사용한다.

조상까지 보는 이유: 잎(`rules/common/coding-style.md`)이 링크가 아니어도 중간
디렉토리(`rules/common`)가 링크면 `cp -R` 는 그 링크를 통해 대상 밖에 쓴다.
bash 3.2 에 연관 배열이 없으므로(GOTCHA) 조상 중복 제거는 `sort -u` 로 한다.

**`--force` 는 이 가드를 우회하지 못한다.** `--force` 의 의미는 「내 수정본을 덮어써도 좋다」이고
「대상 트리 밖에 써도 좋다」가 아니다. `check_directory_conflict` 가 `--force` 로 조기
반환하는 것과 대비되는 지점이므로 코드에 주석으로 남긴다.

**N3(허브 트윈)**: `copy_managed_bin_files` 가 `cp "$source_file" "$TARGET_BIN_DIR/"` 로
최상위 파일만 옮기므로 검사 대상도 얕다 — `$TARGET_BIN_DIR` 자신과 배포 대상 파일명 각각의
`-L` 이면 충분하다. **루트의 헬퍼를 공유하지 않는다**(두 설치기의 독립 선언).

**실측 사실의 취급**: 메인 세션이 확인한 「`cp` 는 대상 심링크를 관통한다」와 「절대 경로 링크의
`Permission denied` 는 샌드박스 산물로 보인다」를 그대로 받는다. **테스트 픽스처는 상대 경로
링크로 만든다** — 절대 경로 링크로 만들면 관통이 아니라 권한 오류로 끝나 검사가 무엇을
증명했는지 불분명해진다.

### 9-4. H4 — `--scope project` 가 `$HOME` 을 받는다 (S1)

`resolve_target_paths` 의 project 분기에서 `$PWD` 가 `$HOME` 과 **같은 실경로**면 거부하고
`--scope user` 를 안내한다.

- **비교는 실경로로 한다** — `/bin/pwd -P` 와 `cd "$HOME" && /bin/pwd -P` 를 비교한다. 문자열
  비교만 하면 macOS 의 `/var → /private/var` 나 심링크된 `$HOME` 에서 빗나간다.
  `is_symlinked_path` 가 이미 같은 문제를 다루고 있어 관용구가 파일 안에 있다.
- **`$PWD` 가 `$HOME` **하위**인 경우는 거부하지 않는다** — `~/projects/foo` 는 정당한 프로젝트다.
  정확히 같을 때만이다.
- **`$HOME` 미설정 대응**: project 경로에는 지금 `$HOME` 참조가 없다(§0 실측). `set -u` 아래
  에서 새로 참조하면 미설정 환경에서 스크립트가 죽는다 → `${HOME:-}` 로 읽고 빈 값이면 검사를
  건너뛴다. 「$HOME 이 없으면 $PWD 가 그것과 같을 수 없다」가 그 건너뜀의 근거다.

### 9-5. H5 — `--force` 백업 (S2)

`check_directory_conflict` 가 `--force` 에서 조기 반환하기 **전에** 세 일을 한다: 목록 산출 →
표시 → 백업. 산출·분류는 기존 `list_differing_managed_files` → `filter_modified_files` 를
그대로 쓴다(stale 은 백업하지 않는다 — 우리가 설치한 그대로인 낡은 사본이므로 잃을 것이 없다).

**S1 선행이 필수인 이유**: `filter_modified_files` 의 판정은 `read_installed_ledger_hash` 의
대장 조회에 달려 있고, H2 가 그 조회를 고친다. H2 없이 H5 를 넣으면 이스케이프가 필요한 경로에서
「대장 없음 → modified」로 오분류돼 **잃을 것이 없는 파일까지 백업이 쌓인다.**

**백업 파일명**: 형제 위치에 `.bak-<타임스탬프>`. 근거 — `install.sh` 자신이
`RETIRED_BACKUP_SUFFIX_FORMAT` 주석에서 「덮어쓰기 전 백업(`.bak-`)」을 이 저장소의 백업 관례로
이미 지목했고, `_write_settings_atomically` 의 `settings.json.bak-<ts>` 가 같은 형태다.

**관리 디렉토리 안에 남는 것이 안전한가** — 세 갈래로 확인했다:
1. `diff -rq` 판정: 백업은 대상에만 있으므로 `Only in <target>` 줄이 되고, 두 목록 함수는 그
   모양을 고르지 않는다 → 설치 검증을 깨지 않는다.
2. 로더 글롭: 규칙·에이전트·커맨드는 `*.md` 로 읽힌다. `<name>.md.bak-<ts>` 는 그 글롭에
   맞지 않는다.
3. 소유권 원칙: 백업은 우리가 만든 것이므로 다음 설치에서 우리가 판단할 대상이다 — 다만 **이
   PRP 는 자동 정리를 만들지 않는다**(YAGNI). 누적은 사용자에게 보고로 알린다.

**대안(기각)**: `~/.claude/.coding-harness-backups/<ts>/` 같은 별도 트리. 관리 디렉토리를 전혀
오염시키지 않고 한 회차를 한 묶음으로 남길 수 있다. 기각 근거 — 새 디렉토리 하나가 소유권
원칙·매니페스트·툼스톤 어디에도 등록되지 않은 채 생긴다. 그 등록까지 하면 이 항목이 국소
수정에서 구조 변경으로 넘어간다.

**구현이 정한 것 — 백업 자체가 실패했을 때(fail-closed, S2 구현 보강)**: 위 설계는 「목록
산출 → 표시 → 백업」순서만 정하고 백업 실패 시의 동작을 비워 뒀다. 구현은 **백업이
실패하면(디스크 부족 등) 그 파일을 덮어쓰지 않고 설치를 중단한다**로 정한다. 근거 — 백업의
존재 이유가 사용자 수정본을 잃지 않는 것인데, 백업 실패를 삼키고 계속 진행하면 정확히 그
약속이 깨진다. S1 이 H1 에서 세운 fail-loud 원칙(diff 오류를 「결측 없음」으로 접지 않는다)과
같은 방향이다. 진단 메시지에는 실패한 파일의 경로를 넣는다(`backup_modified_managed_files`).

**구현이 정한 것 — S2 검수 1회차 반영**: 검수 1회차가 위 구현에서 결함 3건을 더 찾았다
(모두 구현이 채운 자리를 손보는 것이지 이 설계 문단을 다시 여는 것은 아니다) — (1) 백업
이름이 대상 트리 밖을 가리키는 심링크로 선점되면 `cp -p` 가 그 링크를 관통한다(CRITICAL)
→ `cp -p` 직전에 `-L` 로 거부, (2) `check_directory_conflict` 의 `--force` 분기에
`dry_run` 검사가 없어 `--force --dry-run` 이 실제로 백업을 만들었다(MAJOR) → 목록·건수
표시는 그대로 두고 실제 `cp -p` 만 형제 두 쓰기 경로(`process_removals`·
`retire_user_claude_md`)와 같은 형태로 `log_plan` 대체, (3) `blocking_list=$(filter_
modified_files …)` 에 형제 줄과 같은 `|| return 1` 이 빠져 있었다(LOW — 지금은
`filter_modified_files` 의 항상-성공 성질 때문에 도달하지 않지만 계약을 맞춘다). 상세
근거는 `backup_modified_managed_files` 의 코드 주석 참고. 부수로 `report_directory_
differences` 와 공유하던 보고 4줄을 `log_differing_file_list` 헬퍼로 뽑았다(MEDIUM-문면,
DRY — 기존 두 호출부 출력은 문자 단위로 동일).

**구현이 정한 것 — S2 검수 2회차 반영(`check_preconditions` 계약의 예외를 명시한다)**: 위
(1)·(2)를 넣고 나서 검수 2회차가 **이 백업이 `check_preconditions` 의 계약을 깬다**는 것을
지적했다 — 그 함수의 계약 주석은 「모든 쓰기보다 먼저 실행된다. 실패하면 파일을 하나도
건드리지 않은 상태로 중단한다」였는데, 백업이 실제 쓰기(`cp -p`)이므로 그 함수가 실패를
반환한 뒤에도 백업이 남을 수 있다. 검수 실측 두 경로 — `validate_removals_file` 실패(그 검사는
세 `check_directory_conflict` **뒤에** 있다)와 뒤쪽 디렉토리의 백업 실패 — 모두에서 관리
파일은 불변인데 `.bak-*` 가 잔존했고, 그런데도 `설치 중단 — 변경된 파일 없음` 이 출력됐다.

구현은 **계약을 되돌리지 않고 예외를 명시하는 쪽**으로 정한다. 근거 — 백업 대상 판별
(`list_differing_managed_files` → `filter_modified_files`)이 대장 조회에 의존하고, 그 판별을
거치는 자리가 사전조건 단계뿐이다(설치 본체는 판별 없이 디렉토리 전체를 복사한다).
따라서 (a) `check_preconditions` 의 계약 주석에 그 예외와 왜 그 자리인지를 적고, (b) 사전조건
실패 뒤의 중단 메시지를 `force_overwrite` 로 갈라 **두 분기 모두에서 참이 되게** 한다 —
`--force` 면 「관리 파일은 변경되지 않았습니다(`--force` 백업 파일이 남아 있을 수 있습니다)」,
아니면 종전 문구. `main` 의 `resolve_target_paths` 실패 자리는 사전조건 **전**이라 백업이
있을 수 없어 손대지 않는다. 메인 세션이 두 분기를 실측했다(`--force` → 새 문구 · 백업 잔존,
`--force` 없음 → 종전 문구 · 백업 0건).

### 9-6. H6 — `harness-update.md` 의 허위 기술 (S2)

「Phase 4 — REINSTALL」의 `exit 1` 처리 문단에서 「(for small diffs) the diff content
install.sh already printed」를 지운다. 대신 `report_directory_differences` 가 실제로 내는 것을
쓴다 — `diff -rq` 의 요약행(`Files X and Y differ`)이고 상한은 `MAX_DIFF_LINES` 다.

**H5 와 같은 단계여야 하는 이유**: H5 가 착지하면 이 문단의 「`--force`(백업 없음)」 서술도
거짓이 된다. 두 항목을 다른 단계에 두면 **어느 순서로 해도 중간 상태에서 문서가 거짓**이다.

**편승 1건(승인 항목)**: 같은 문단이 `manifest v2's files field` 라고 적는데 현재
`MANIFEST_VERSION` 은 그 값이 아니다(값은 `grep -n 'MANIFEST_VERSION=' install.sh` 로 센다).
같은 문단을 어차피 다시 쓰므로 함께 고치는 것을 권고한다 — 감사 이관 항목은 아니다(§14 승인 2).

### 9-7. H9 · N2 — `hub_settings.py` (S4)

**H9**: `_load_settings` 가 `json.loads` 결과를 `isinstance(..., dict)` 로 확인하고, 아니면
기존 「중단 신호」인 `None` 을 돌려준다. 6개 호출부는 손대지 않는다 — 이미 `None` 을
`ok:false` 로 바꾸는 분기를 갖고 있다.

**사유 문장**: `SETTINGS_PARSE_ERROR` 의 문면이 「파싱 실패」인데 유효 JSON 배열은 파싱이
성공한 경우다. **상수의 문면을 두 경우를 함께 덮는 표현으로 넓힌다**(예: 「객체로 읽을 수
없습니다」). 테스트는 리터럴이 아니라 `hub_settings.SETTINGS_PARSE_ERROR` 동일성으로
단언하므로(§0 확인) 문면 변경이 테스트를 깨지 않는다.

**두 경우를 한 어휘로 접는 것이 H13 과 모순되지 않는가** — 아니다. H13 이 접힘을 문제로 본
근거는 「사용자가 서로 다른 **대응**을 해야 하는데 구분되지 않는다」였다. 여기 두 경우는
대응이 같다(사용자가 `settings.json` 을 직접 고친다)고 우리 동작도 같다(손대지 않고 중단).
대응이 같은 두 경우를 한 어휘로 묶는 것은 접힘이 아니다.

**파급이 표보다 넓다**: `statusline_owner` 도 `settings.get(...)` 를 부르므로
`install_statusline` · `uninstall_statusline` · `statusline_install_status` 도 같은 입력에서
죽는다. `_load_settings` 한 곳을 고치면 셋이 함께 낫는다 — **테스트는 그 셋도 덮는다**(§10-4).

**N2**: `_hub_hook_entry` 가 돌려주는 dict 에 `timeout` 을 넣는다. 값은 모듈 상수
`HOOK_TIMEOUT_SECONDS`. `merge_hub_hooks` 는 마커 존재만 보고 멱등을 판정하므로
(`_entry_has_hub_marker`) **기존 설치본의 timeout 없는 엔트리는 자동으로 갱신되지 않는다** —
그 한계를 상수 주석에 적고, 갱신 경로는 `/hub off` → `/hub install` 임을 문서에 남긴다.
자동 마이그레이션은 만들지 않는다(YAGNI, 그리고 남의 엔트리를 읽지 않는다는 이 모듈의 선언과
가까이 붙는 작업이다).

### 9-8. H10 · H11 · H13 · N1 — `hub_usage_fetch.py` (S4)

**H10**: §5-3 결정. `_open_usage_api_request` 이음선 + `_NoRedirectHandler`.
차단된 3xx 는 `HTTPError` 로 올라오므로 `_classify_http_error` 가 3xx 대역을
`redirect_blocked` 로 분류한다.

> **구현 시 실측할 것**: 「`redirect_request` 가 `None` 을 돌려주면 3xx 가 `HTTPError` 로
> 올라온다」는 CPython 의 핸들러 연쇄에서 따라오는 동작이다. 이 설계는 그것을 재보지 않았다 —
> 구현 단계가 로컬 스텁 서버로 확인하고, 확인 결과를 테스트로 고정한다(§10-4 U-R1).

**H11**: `response.read(USAGE_API_MAX_RESPONSE_BYTES + 1)` 로 상한+1 을 읽어 초과를 판정한다
(상한만 읽으면 「정확히 상한」과 「초과」를 구분할 수 없다). 초과면 `response_too_large`.
`describe_json_key_structure` 결과는 `USAGE_API_MAX_RESPONSE_KEY_ENTRIES` 로 자르고 잘렸음을
알리는 표지 항목을 넣는다(§7-2).

**H13**: `ssl.SSLCertVerificationError` 를 `URLError`·`OSError` 보다 **앞선** except 절에서
잡아 `tls_verify_failed` 로 분류한다. 순서가 규약이다 — `SSLCertVerificationError` 는
`OSError` 하위이므로 뒤에 두면 도달하지 않는다. `import ssl` 이 늘어난다(표준 라이브러리).

> **구현 시 확인할 것**: `urllib` 이 TLS 검증 실패를 `URLError` 로 **감싸서** 올리는 경로가
> 있다. 그 경우 `except URLError` 안에서 `error.reason` 이
> `ssl.SSLCertVerificationError` 인지 보는 층이 함께 필요하다. 두 경로 모두 테스트로 고정한다.

**A-SEC 을 깨지 않는지** — 세 신규 어휘는 고정 문자열이고 예외 객체를 문자열로 바꾸지 않는다.
`except Exception` 마지막 방어선은 **그대로 둔다**(그 자리의 주석이 남긴 근거가 이 PRP 로
무효화되지 않는다).

**N1**: `failure_reason_message` 를 만들고 `record_usage_api_failure` payload 에 문장을 함께
싣는다(§8-3). 배치는 승인 항목.

### 9-9. H7 — `disable-model-invocation` (S2)

세 파일 frontmatter 에 `disable-model-invocation: true` 를 넣는다.

**선례 신설임을 명시한다** — 이 키를 쓰는 커맨드가 저장소에 아직 없다(§0 실측). 그래서
「부작용 커맨드는 전부 이 키를 갖는가」라는 질문이 곧 따라온다. **이 PRP 는 감사가 지목한
세 개만 한다**(수술적 변경 — `karpathy-guidelines.md` #3). 나머지 커맨드의 판정은 §15 남은
질문 2 로 올린다.

### 9-10. H8 — `hub/install.sh --uninstall` (S3)

§4 결정. 구현 형태는 §4-4.

**기존 검사와의 상호작용**(GOTCHA): `T25-23` 은 `hub/install.sh` 안에서
`server-stop`·`uninstall-hooks`·`rm -rf` 리터럴의 **등장 순서**를 grep 한다. `T25-39` 는
`uninstall-statusline`·`rm -rf` 로 같은 일을 한다. 헬퍼로 추출해도 하위 명령 문자열은 호출
인자로 남으므로 순서 grep 은 계속 성립한다 — **그러나 헬퍼 정의를 호출부보다 아래에 두면
순서가 뒤집힌다.** 헬퍼는 `perform_uninstall` **위**에 정의한다.

**구현이 정한 것(S3)**: §4-4 는 헬퍼의 인자 형태만 정했고 문구는 비워 뒀다 — 구현이
아래를 정한다.
- **중단 사유 문장은 하위 명령마다 다르고, 그 시점까지 끝난 단계를 포함한다**(§4-3 결정 3
  충족): `server-stop` 은 원문 그대로("그대로 진행하면 서버는 계속 도는데 끌
  수단(hub.py)만 사라집니다"), `uninstall-hooks`·`uninstall-statusline` 은 각각
  "서버 정지는 이미 완료됐습니다"·"서버 정지·훅 제거는 이미 완료됐습니다"를 앞에 붙인다.
- **`--force` 경로의 수동 복구 절차는 두 갈래로 가른다**(`server-stop` vs 나머지) —
  서버는 프로세스 확인·종료, 훅·statusLine 은 설정 파일 안의 항목 확인·제거로 복구 대상이
  다르기 때문이다(§4-2). `hub/install.sh` 는 `settings.json` 문자열을 알지 못한다는 선례
  (`T25-73`, "전제 1")가 있어 파일명은 적지 않고 "설정 파일"로만 가리킨다.
- **테스트는 새 ID 하나(`T25-176`)로 훅·statusLine 실패 두 갈래와 `--force` 우회까지
  함께 검증한다** — `T25-26` 이 이미 같은 방식(한 ID 아래 성공·실패 두 시나리오)으로
  서 있어(§0), 그 관용구를 따랐다. 원장은 면제행으로 등록한다(§10-3 판정 그대로 — exit
  코드·`bin/` 존재의 직접 관측).

### 9-11. H12 — 429 `Retry-After` (보류 후보)

§7-3 데이터 모델. 승인되면 S4 의 마지막 항목으로, 별도 커밋으로 한다 — 유일하게 순수 함수
계약이 바뀌는 항목이라 검수 렌즈가 다르다.

---

## 10. 테스트 계획

### 10-0. 정본 검증 명령 (프로젝트 `CLAUDE.md` §4)

각 단계 끝에서 아래를 완주한다. **부분 실행으로 대체하지 않는다.**

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/hub -t .
python3 -m unittest discover -s tests/commands -t .
python3 -m py_compile hub/bin/*.py
bash -n install.sh && bash -n hub/install.sh
```

**`commands/*.py` 를 `py_compile` 대상에 넣지 않는다** — 배포 소스 디렉토리에 `__pycache__` 를
만들어 `T22-138` 이 실패한다(`tests/run.sh` 에 문서화된 함정).

### 10-1. 실행 검증의 제약 (`install.sh`·`hub/install.sh`)

- **이 저장소 안에서 `install.sh --scope project` 를 실행하지 않는다** — 자기 설치이고
  `tests/run.sh` 의 `T31-4` 가 그런 커밋을 차단한다(프로젝트 `CLAUDE.md` §1(a)).
- **실제 `$HOME` 을 대상으로 설치하지 않는다** — 모든 실행 검증은 `tests/run.sh` 의
  샌드박스 `HOME` 치환으로만 한다(§1(b)). 픽스처 관용구는 이미 파일 안에 있다:
  `sandbox=$(mktemp -d)` → `register_cleanup_path` → `HOME="$sandbox" "$INSTALL_SCRIPT" ...`.
- **Bash 도구의 `find` 는 `bfs` 다.** 스크립트 동작을 손으로 재현할 때는 `/usr/bin/find` 를
  절대경로로 부른다.

### 10-2. 셸 항목의 서브체크 (S1~S3)

| 항목 | 무엇을 확인하면 고쳐졌다고 하는가 | 픽스처 | 보고 함수 |
|---|---|---|---|
| H1 | `diff` 가 상태 2 이상을 낸 지점에서 **`diff 검사 실패` 진단과 함께** 중단한다. **exit 코드는 판별 근거가 아니다** — 같은 픽스처에서 변조판도 `cp` 자신의 실패로 exit 1 을 낸다(검수 2회차 실측). 복사 **뒤** 호출부(`verify_managed_files_installed`)는 이 픽스처가 밟지 않고, 변조가 공유 함수를 겨냥하는 것으로 대신한다 | 대상측 **파일 하나**를 `chmod 000`(실측 갱신, S1 검수 1회차 m4 — 애초 계획한 "대상 하위 디렉토리 전체를 chmod" 는 이 환경의 diff 가 상태 0/1 만 내 재현되지 않았다. **파일 단위** chmod 는 안정적으로 상태 2 를 낸다. 1회차 구현이 실제로 쓴 "소스 디렉토리 자체를 지운다" 방식은 그 뒤 m2 수정으로 `check_no_symlink_targets` 의 find 실패 검사가 같은 픽스처에서 더 먼저 발화하게 돼, 이 항목의 재현 수단으로는 폐기하고 대상측 파일 chmod 로 교체했다 — 그 소스-제거 픽스처는 대신 T15-2(m2) 자신의 회귀 검사로 재사용한다) | `record_failure` + `return 1`(뒤 검사의 전제) |
| H2-원자성 | 매니페스트 쓰기 도중 실패해도 기존 파일이 온전하다 · 임시 파일이 남지 않는다 | 쓰기 불가 상황을 만든 샌드박스 | `note_failure`(독립) |
| H2-이스케이프 | `"` 가 든 경로의 레포 사본에서 대장 키·해시가 채워지고, 재설치가 `--force` 를 요구하지 않는다 | `T27-11`·`T27-12` 가 쓰는 메타문자 경로 사본 관용구를 그대로 확장 | `note_failure` |
| H3 | 관리 경로 잎이 심링크 → exit≠0 · 링크 **대상 파일의 내용이 변하지 않았다** · 조상 디렉토리가 심링크인 경우도 같다 · `--force` 로도 통과하지 않는다 | 상대 경로 링크(§9-3) | `record_failure` + `return 1` |
| N3 | `$TARGET_BIN_DIR/hub.py` 가 심링크 → 허브 설치가 exit≠0 · 링크 대상 불변 | 〃 | `record_failure` + `return 1` |
| H4 | `$PWD == $HOME` 에서 `--scope project` → exit≠0 · `.claude/` 미생성 · 기존 user 매니페스트 불변 | `cd "$sandbox" && HOME="$sandbox"` | `note_failure` |
| H5 | `--force` 가 modified 파일을 덮어쓸 때 `.bak-*` 가 생기고 **원본 내용을 담고 있다** · 목록이 출력된다 · stale 은 백업되지 않는다 | 기존 `T15`/`--force` 픽스처 확장 | `note_failure` |
| H6 | 문서에 `diff -rq` 요약행 서술이 있다(양성 grep) · `--force` 백업 서술이 H5 동작과 일치한다 | 문면 grep | `note_failure` |
| H7 | 세 파일 frontmatter 에 키가 있다(루프) | 문면 grep | `note_failure` |
| H8 | `uninstall-hooks` 가 `ok:false` → exit≠0 · `bin/` 보존 · 어느 단계까지 갔는지 보고에 나타난다 · `--force` 면 진행하고 수동 복구 절차를 인쇄한다 | **`T25-26` 의 스텁 `hub.py` 에 분기 추가**(§0) | `note_failure` |

**신규 서브체크 ID 는 대상 그룹의 접두를 따른다** — H1~H5 는 그 시나리오를 실행하는 그룹
(`T15`·`T20`·`T27`·`T14` 계열), H6~H8 은 문면·허브 그룹(`T22`·`T25`). **모든 신규 실패 보고에
`T<그룹>-<id>` 접두를 붙인다** → `NOTE_FAILURE_ID_LESS_RATCHET` 는 움직이지 않는다.

### 10-3. 뮤테이션 원장(그물)이 필요한가 — 항목별 판정

이 저장소의 규칙은 「새 검사·가드는 고의로 깨뜨렸을 때 실패함을 확인한다」다. 13건(+3)에 전부
원장 행을 붙이면 원장이 크게 늘고 `LEDGER_MUTATION_ROW_FLOOR`·`SOURCE_GUARD_ID_FLOOR`·헤더
인용의 래칫 연쇄가 따라온다. **판정 기준을 먼저 세운다.**

> **기준**: 가드의 발화가 **픽스처가 특정 분기에 도달하는지**에 달려 있고 그 도달이
> 자명하지 않으면 원장 행을 붙인다. 실패가 주 경로의 직접 관측(exit 코드·파일 존재)이면
> 가드를 없애는 것만으로 검사가 큰 소리로 깨지므로 행을 붙이지 않는다.
>
> 이 기준은 이 저장소가 실제로 겪은 실패에서 나왔다 — `tests-hardening` §9 가 「`T35-9` 의
> 픽스처로는 `A12` 분기에 도달하지 못해 그 확장은 이빨 없는 검사가 된다」를 기록했다.

| 항목 | 그물 | 근거 |
|---|---|---|
| **H1** | **필요** | 발화 조건이 「복사 성공 + `diff` 상태 2 이상」이라는 인공 분기다. 픽스처가 거기 닿았는지가 자명하지 않다 |
| **H2-이스케이프** | **필요** | 메타문자 경로에서만 발화한다. `T27-11`·`T27-12` 가 정확히 이 형태로 이미 등록돼 있어 관용구도 있다 |
| **H3 · N3** | **필요** | 조상 열거가 조용히 좁아지는 변조(잎만 보게 만들기)가 검사를 통과하는지가 핵심이다. 이 계열은 `T35-11`(`-name` 광역화)이 선례다 |
| **H7** | **필요** | 문면 grep 가드다 — 표현이 바뀌면 조용히 0건이 되는 형태가 이 원장의 본래 대상이다. **행 하나만 등록하고 루프의 마지막 파일을 변조한다**(조기 이탈한 루프가 가장 흔한 고장 형태다) |
| **H6** | **필요** | 〃(양성 grep 하나) |
| **H4** | 불필요 | 가드를 지우면 설치가 진행돼 「`.claude/` 미생성」 단언이 즉시 깨진다. 비교를 잘못 쓰면 **수용** 방향으로 틀어져 같은 단언이 잡는다 |
| **H5** | 불필요 | `.bak-*` 파일의 존재와 내용을 직접 관측한다. 백업이 빠지면 그 관측이 깨진다 |
| **H8** | 불필요 | exit 코드와 `bin/` 존재의 직접 관측이다. `T25-26` 이 같은 형태로 이미 원장 없이 서고 있다 |
| **H2-원자성** | 불필요(기록) | 「쓰기 도중 실패」를 셸에서 결정적으로 만드는 픽스처가 마땅하지 않다. 검사는 **임시 파일 잔존 없음**과 **실패 시 기존 파일 불변**의 관측으로 좁힌다. **이 좁힘이 남기는 것**: 교체가 실제로 rename 인지를 기계가 확인하지 못한다 — `mv` 를 `cp` 로 바꾸는 변조는 이 검사를 통과할 수 있다. 그 한계를 서브체크 주석에 적는다 |
| **H9~H13 · N1 · N2** | 불필요 | 파이썬 **행위 테스트**다. 프로덕션을 깨면 `unittest` 가 실패한다 — grep 가드처럼 조용히 0건이 되는 실패 모드가 없다. 원장의 대상은 `tests/run.sh` 의 문면·grep 가드다 |

**신규 변조행: H1 · H2-이스케이프 · H3 · N3 · H6 · H7 — 6행 규모.** 붙일 때 함께 움직이는 것:

1. `tests/mutations.tsv` 의 **8열 규약**을 지킨다 — `anchor_function` 은 `tests/run.sh` 안의
   맨 함수명이고, `T37-13` 이 5열 토큰을 그 함수 몸통 안에서 교차검증한다.
2. `mutation_sed` 는 `[주소]s/…/…/[플래그]` 한 형태만 쓰고 `w`·`W`·`r`·`R`·`e` 플래그를 쓰지
   않는다(미러 밖 쓰기 차단 — `mutation_sed_is_write_safe`).
3. `expect_group` 은 **실행 매개체**다(그 가드를 담은 그룹이 아니다). `T37` 을 가리키면
   파서가 거부한다(미러 안 무한 재귀).
4. `expect_token` 은 `tests/run.sh` 의 실패 보고 호출 줄에서 **1건만** 등장해야 한다.
5. **`SOURCE_GUARD_ID_FLOOR` 와 `LEDGER_MUTATION_ROW_FLOOR` 를 올리고, 원장 헤더의 인용
   숫자와 이력 화살표를 같은 커밋에서 갱신한다.** 안 하면
   `verify_ledger_header_citations` 가 **어느 그룹도 돌기 전에** `exit 1` 로 막는다. 현재 값은
   `grep -n 'SOURCE_GUARD_ID_FLOOR=\|LEDGER_MUTATION_ROW_FLOOR=' tests/run.sh` 로 읽는다.
6. 면제 바구니 계수 2종도 헤더 인용 대조 대상이다 — 면제행을 더하면 그 숫자도 함께 움직인다.

### 10-4. 파이썬 항목의 단위 테스트 (S4)

`tests/hub/` 의 기존 관용구를 따른다 — `unittest` + `mock.patch.object`, 클래스당 한 관심사.

| ID | 대상 | 케이스 |
|---|---|---|
| U-S1 | `_load_settings` (H9) | 최상위가 배열 · 문자열 · 숫자 · `null` → 각각 `None` |
| U-S2 | `install_hooks`·`uninstall_hooks` (H9) | 위 입력에서 `ok:false` + 사유 · **트레이스백이 나지 않는다** · `settings.json` 이 변경되지 않았다 |
| U-S3 | statusline 3경로 (H9, §9-7 파급) | `install_statusline`·`uninstall_statusline`·`statusline_install_status` 가 같은 입력에서 죽지 않는다 |
| U-S4 | `_hub_hook_entry` (N2) | `timeout` 키가 있고 값이 상수와 같다 · `merge_hub_hooks` 가 여전히 멱등이다 |
| U-R1 | `_open_usage_api_request` (H10) | 302 를 **따라가지 않는다**. 확인 방식 두 층: ① 로컬 스텁 서버(`tests/hub/test_hub_server.py` 에 선례)가 302 를 내면 두 번째 요청이 도착하지 않는다 ② `fetch_rate_limit_capture` 가 `redirect_blocked` 를 돌려준다 |
| U-R2 | 〃 (H10, A-SEC) | 리다이렉트가 차단됐을 때 반환값·기록 어디에도 토큰 문자열이 없다 |
| U-R3 | `fetch_rate_limit_capture` (H11) | 상한+1 바이트 본문 → `response_too_large` · 상한 정확히 → 정상 처리 |
| U-R4 | 〃 (H11) | 키 목록이 상한을 넘으면 잘리고 **잘렸음을 알리는 표지가 있다** |
| U-R5 | 〃 (H13) | `SSLCertVerificationError` → `tls_verify_failed`. **직접 발생 · `URLError` 로 감싸진 경우 두 갈래 모두**(§9-8) |
| U-R6 | 〃 (H13 회귀) | 타임아웃·DNS 실패는 여전히 `network_error` — 새 어휘가 기존 어휘를 잠식하지 않았다 |
| U-R7 | `failure_reason_message` (N1) | **`FailureReason` Literal 의 모든 값에 메시지가 있다**(어휘 완비 — `typing.get_args` 로 순회). 이것이 §7-1 의 「둘이 함께 움직인다」를 기계로 강제하는 자리다 |
| U-R8 | `record_usage_api_failure` (N1) | payload 에 원어휘 키와 문장이 함께 있고 **토큰이 없다** |
| U-P1 | `next_usage_api_poll_state` (H12, 승인 시) | `Retry-After` 없음 → 기존 값과 동일 · 유효 숫자 → 그 값 · 상한 초과 → clamp · 음수 → 0 · 날짜 표기 → 헤더 없음과 동일 |

**기존 테스트 이전(H10)**: `urlopen` 을 모킹하는 케이스를 `_open_usage_api_request` 모킹으로
옮긴다. 규모는 `grep -n 'urlopen' tests/hub/test_hub_usage_fetch.py` 로 센다. **옮긴 뒤 각
케이스가 이전과 같은 어휘를 단언하는지 하나씩 대조한다** — 모킹 지점 이전은 조용히 단언을
무력화하기 쉬운 변경이다.

### 10-5. 단계별 착지 판정

각 단계 끝에서 §10-0 의 명령을 완주하고, **그 단계의 신규 가드를 고의로 깨뜨려 실패함을
직접 재현해 보고한다**(원장 행이 붙은 것은 `bash tests/run.sh --only T37` 이 대신 한다).
다음 단계는 검수 PASS 후에 시작한다.

---

## 11. 기각 목록 — 검토했으나 하지 않기로 한 것

1. **같은 호스트 리다이렉트 허용**(H10 대안 b) — §5-2. 비교 로직 자체가 새 공격면이고, 지금
   그것을 필요로 하는 소비자가 없다.
2. **리다이렉트 시 헤더 벗기기**(H10 대안 c) — §5-2. 보안 이벤트를 인증 만료로 오표시한다.
3. **`response_too_large` 를 `schema_mismatch` 로 접기** — §7-1. 그 어휘가 약속한 진단 창구를
   채울 수 없다.
4. **`forced_multiplier` 를 남기고 `forced_delay_ms` 추가** — §7-3. 같은 판정의 출처가 둘이 된다.
5. **`Retry-After` 의 HTTP-date 해석** — §7-3. 시계 오차·타임존을 끌어온다(YAGNI).
6. **백업을 별도 트리에 모으기**(H5 대안) — §9-5. 소유권 원칙에 등록되지 않은 디렉토리가 생긴다.
7. **`--uninstall` 계속 진행 + 수동 복구 안내**(H8 대안) — §4-4. 형제 선례와 불일치하고 안내가
   소유권 선언과 어긋난다.
8. **`timeout` 없는 기존 훅 엔트리의 자동 마이그레이션**(N2) — §9-7. 남의 엔트리를 읽지 않는다는
   모듈 선언에 가까이 붙고, 지금 요구가 없다.
9. **관리 디렉토리 아래 **모든** 심링크 거부**(H3) — §9-3. 사용자의 심링크된 자기 자산 때문에
   설치가 막히는 오탐을 만든다.
10. **`MANIFEST_VERSION` 상향**(H2) — §7-4. 키 집합이 그대로고 기존 설치본과 호환된다.
11. **JSON 이스케이프에 `python3`·`jq` 사용**(H2) — §9-2. `install.sh` 의 「외부 의존성 0」 계약.
12. **`disable-model-invocation` 을 부작용 커맨드 전체에 일괄 적용**(H7) — §9-9. 감사가 지목한
    범위를 넘는다. §15 질문 2 로 올린다.
13. **`.bak-*` 자동 정리**(H5) — §9-5. 지금 요구가 없다.
14. **네 정본 명령에 `commands/*.py` 의 `py_compile` 추가** — `T22-138` 이 실패한다.

---

## 12. 리스크와 완화

| 리스크 | 완화 |
|---|---|
| **H2 가 레이어 간 유일 통신 채널을 건드린다** — 조회가 어긋나면 stale/modified 분류·은퇴 판정·멱등 비교가 전부 근거를 잃는다 | 쓰기·읽기를 **한 커밋에서** 고치고, 메타문자 경로 사본 시나리오(`T27-11`·`T27-12` 관용구)로 왕복을 단언한다. S1 을 가장 먼저 착지시키는 이유다 |
| **H10 이 기존 테스트의 모킹 지점을 없앤다** | 이음선 하나를 만들고 케이스를 하나씩 대조 이전한다(§10-4). 이전 규모를 착수 보고에 세어 남긴다 |
| **H3 의 조상 열거가 정상 설치를 막는다**(오탐) | 검사 대상을 배포 경로와 그 조상으로 한정한다(§9-3). 기존 `T1`·`T2`·`T3` 신규·재설치 시나리오가 회귀 그물이다 |
| **원장 6행 추가가 래칫 연쇄를 건드려 스위트 전체를 막는다** | `verify_ledger_header_citations` 는 **fail-loud** 다(조용한 통과가 아니다). §10-3 의 6개 동반 수정을 체크리스트로 쓰고, 각 단계에서 `bash tests/run.sh` 완주로 확인한다 |
| **H5 의 백업이 대상 디렉토리를 오염시킨다** | 세 갈래로 안전성을 확인했다(§9-5). 누적은 사용자에게 보고로 알리고 자동 정리는 만들지 않는다 |
| **`--force` 로 조기 반환하던 경로에 일이 추가돼 느려진다** | 추가되는 일은 이미 비-`--force` 경로가 하던 `diff`+분류와 같은 작업이다. 이 저장소의 병목은 실행 성능이 아니라 세션 컨텍스트 예산이다(프로젝트 `CLAUDE.md` §3) |
| **어휘 3개 추가가 `/hub status` 소비자를 놀래킨다** | `record_usage_api_failure` 는 임의 reason 문자열을 이미 받는다. 표시 경로는 문자열 그대로 노출한다 — 새 enum 을 요구하는 소비자가 이 설계의 조사 범위에서 나오지 않았다 |
| **S4 의 파이썬 항목 6건이 한 커밋에 몰린다** | 두 파일로 갈라져 있고(`hub_settings.py` 2건 · `hub_usage_fetch.py` 4건) 검수 렌즈를 파일별로 나눌 수 있다. 필요하면 S4a/S4b 로 쪼갠다 |

---

## 13. GOTCHA (구현자가 틀리기 쉬운 함정)

1. **`diff` 의 상태 1 은 오류가 아니다**(H1). `>= 2` 만 실패로 본다. 1 을 실패로 오분류하면
   차이가 있는 모든 정상 설치가 막힌다.
2. **`set -e` 는 조건문에서 호출된 함수 내부에 적용되지 않는다.**
   `rules/common/karpathy-guidelines.md` 가 이 저장소의 실제 실패로 기록한 함정이다.
   `x=$(cmd) || status=$?` 형태를 쓴다.
3. **이스케이프 순서는 `\` 먼저, `"` 다음**(H2). 뒤집으면 두 번째 치환이 첫 번째가 넣은
   백슬래시를 다시 바꾼다.
4. **대장 읽기도 이스케이프한다**(H2). `read_installed_ledger_hash` 를 빠뜨리는 것이 이
   항목의 대표적 실패다.
5. **심링크 픽스처는 상대 경로로 만든다**(H3). 절대 경로 링크는 이 환경에서 `cp` 가
   `Permission denied` 로 끝나 검사가 무엇을 증명했는지 불분명해진다(메인 세션 실측).
6. **`--force` 가 심링크 가드를 우회하지 않는다**(H3). `check_directory_conflict` 의 조기
   반환과 대비되는 지점이라 주석으로 남긴다.
7. **`${HOME:-}` 로 읽는다**(H4). project 경로에 `$HOME` 참조가 새로 들어가므로 `set -u`
   아래에서 미설정 환경이 죽는다.
8. **`run_hub_subcommand_or_abort` 정의를 `perform_uninstall` 위에 둔다**(H8). `T25-23`·
   `T25-39` 가 리터럴 **등장 순서**를 grep 한다.
9. **`SSLCertVerificationError` 의 except 절은 `URLError`·`OSError` 보다 앞이다**(H13).
   `OSError` 하위이므로 뒤에 두면 도달하지 않는다. 그리고 감싸진 경로(`URLError.reason`)도
   함께 다룬다.
10. **`response.read(상한 + 1)`**(H11). 상한만 읽으면 「정확히 상한」과 「초과」가 구분되지 않는다.
11. **`urllib.request.install_opener()` 를 쓰지 않는다**(H10). 전역 가변 상태 금지.
12. **원장 8열 `anchor_function` 은 맨 함수명이다.** `함수명() {` 리터럴도 `파일:심볼` 형태도
    아니다. 해소기가 `tests/run.sh` 안에서 `^<name>() {` 정의를 찾고 hit 이 1 이 아니면 실패한다.
13. **`expect_group` 에 `T37` 을 쓰지 않는다.** 미러 안 무한 재귀.
14. **모든 신규 실패 보고에 `T<그룹>-<id>` 접두를 붙인다.** 안 붙이면
    `NOTE_FAILURE_ID_LESS_RATCHET` 의 분모가 늘어 그 래칫이 발화한다.
15. **`bash tests/run.sh` 완주로 확인한다** — `bash -n` 만으로는 부족하다.
    `hub/install.sh` 도 `T` 군이 샌드박스 `HOME` 으로 실제 실행한다
    (`audit-remediation.md` GOTCHA 8).
16. **환경**: bash 3.2(연관 배열 없음), BSD `sed`/`grep`/`find`. 조상 중복 제거는 `sort -u`.

---

## 14. 승인 요청 항목

| # | 항목 | 권고 | 승인이 필요한 이유 |
|---|---|---|---|
| **1** | **분할: 4단계(S1→S2→S3→S4)** | 승인 | 회차 수와 커밋 경계를 정한다. 반대라면 「한 회차」가 대안이고, 그때 검수 3회 상한 안에 수렴하지 않을 위험을 받는다 |
| **2** | **신규 발견 N1(죽은 어휘 dict)·N2(훅 timeout)를 범위에 넣는다** | 승인 | 감사 행인데 어느 이관 표에도 없다(§2-B). 범위를 넓히는 결정이다. **N1 은 H13 의 선행**이므로 빼면 H13 산출물의 절반이 죽은 코드가 된다 |
| **3** | **N1 의 소비자 배치** — `record_usage_api_failure` payload 에 사람이 읽는 문장을 함께 싣는다 | 승인 | `last_usage_api_error.json` 스키마가 늘어난다(`/hub status` 소비자가 보는 모양) |
| **4** | **H12(429 `Retry-After`)를 이번에 하는가** | **다음 PRP 로 보류** | 낮은 심각도 × 4개 자리 계약 변경. 하기로 하면 §7-3 의 `forced_multiplier` → `forced_delay_ms` 교체안도 함께 승인 대상 |
| **5** | **`FailureReason` 어휘 3개 추가**(`redirect_blocked`·`tls_verify_failed`·`response_too_large`) | 승인 | 이 모듈의 공개 어휘가 늘어난다. 대안(기존 어휘로 접기)은 §7-1·§11 에 기각 근거와 함께 적었다 |
| **6** | **H6 편승 1건** — 같은 문단의 `manifest v2` 낡은 표기 정정 | 승인 | 감사 이관 항목이 아니다(수술적 변경 원칙상 별도 승인) |
| **7** | **H8 의 세부 결정 3** — 중단 시 「어느 단계까지 갔는지」를 보고한다(부분 적용 상태 노출) | 승인 | `--uninstall` 의 사용자 노출 문면이 늘어난다 |

---

## 15. 남은 질문 (추측하지 않고 묻는다)

1. **`.bak-*` 누적을 언젠가 정리할 계획이 있는가?** 이 PRP 는 만들지 않기로 했다(§11-13).
   「다음 설치가 이전 백업을 지운다」 같은 정책을 원하면 별건으로 설계해야 한다 — 사용자가
   일부러 남긴 백업을 지우는 방향이라 소유권 원칙과 부딪친다.
2. **`disable-model-invocation` 을 부작용 커맨드 전체에 적용할 것인가?** 이 PRP 는 감사가
   지목한 세 개만 한다(§9-9). 대상 후보는 `grep -rln 'description:' commands/` 로 열거한 뒤
   「부작용이 있는가」를 사람이 판정해야 한다 — 기계로 가를 기준이 없다.
3. **`USAGE_API_MAX_RESPONSE_BYTES` 의 값을 무엇으로 하는가?** 이 설계는 정상 응답 크기를
   재보지 않았다(§7-2). 구현 단계가 실측하고 그 근거를 상수 주석에 남기는 것으로 충분한가,
   아니면 값을 지금 정해야 하는가?

   **S4 구현 시 답변(결정 A)**: **실측하지 않는다** — 정상 응답 크기를 재려면 사용자의
   OAuth 토큰으로 실제 API 를 호출해야 하고, 크기 하나를 재려고 자격증명을 네트워크로
   보내는 것은 정당화되지 않는다(이 구현도 실제 호출을 하지 않았다). 대신 파서가 실제로
   읽는 필드 구조에서 유도했다 — `USAGE_API_MAX_RESPONSE_BYTES = 64 * 1024`,
   `USAGE_API_MAX_RESPONSE_KEY_ENTRIES = 100`. 유도 근거와 "실측이 아니다"라는 사실은
   §7-2 와 `hub_usage_fetch.py` 상수 주석 양쪽에 남겼다.
4. **`hub/install.sh --uninstall --dry-run` 의 별건**(`audit-remediation.md` 편승 13)이 이미
   착지했는지 이 설계는 확인하지 않았다. H8 이 같은 함수를 열므로, 그 항목이 아직 남아 있다면
   S3 에 편승시킬 것인가?

   **S3 구현 시 답변**: 이미 착지해 있어 편승시킬 것이 없다 — `log_uninstall_plan` 이
   `--uninstall --dry-run` 조합 전용으로 이미 존재하고(`grep -n '^log_uninstall_plan'
   hub/install.sh` 로 확인), `perform_uninstall` 을 호출하지 않는다. 그래서 H8 이
   `perform_uninstall` 안에 추가한 중단 게이트(`run_hub_subcommand_or_abort`)는 이 조합
   경로에는 전혀 관여하지 않는다. 그 함수의 계획 문면("상주 서버 정지 → 훅 제거 →
   statusLine 제거 (hub.py 경유)")은 H8 이 세 하위 명령 모두에 중단 게이트를 추가한 뒤에도
   여전히 참이다 — 순서 자체는 바뀌지 않았고(구현 중 재확인), 이 문면은 게이트의 통과·중단
   여부를 서술하지 않으므로 게이트 추가로 거짓이 되지 않는다.

---

## 16. 한계 — 이 설계가 보증하지 않는 것

**기제**: 이 문서는 메인 세션의 재검증 결과를 입력으로 받고, 설계 판단의 근거가 되는 심볼을
직접 열어 확인했다(§0). 확인의 단위는 **함수 본문과 그 호출부**다.

**그 기제에서 따라오는 한계**: 확인 범위가 「내가 근거로 삼은 자리」로 한정된다. 같은 파일의
다른 함수, 같은 결함의 다른 발현 자리는 그 범위 밖이다.

**비망라 예시** — 아래는 이 설계가 보지 않은 것의 일부다:

- `install.sh` 의 다른 함수에 같은 계열의 결함(미이스케이프 삽입·삼킨 상태 코드)이 더 있는지
  전수로 훑지 않았다. `H2`·`H1` 이 지목한 자리만 봤다.
- `hub/bin` 의 다른 모듈이 `_load_settings` 와 같은 「반환 타입은 좁은데 검사가 없다」 형태를
  갖는지 보지 않았다.
- 세 신규 어휘를 소비할 수 있는 자리를 `record_usage_api_failure` → `/hub status` 경로까지만
  따라갔다. `hub_template.html` 의 렌더 경로가 어휘를 어떻게 표시하는지는 보지 않았다.
- `T25-23`·`T25-39` 외에 `hub/install.sh` 의 텍스트 순서에 결합된 검사가 더 있는지 전수로
  세지 않았다(`grep -n 'hub/install.sh' tests/run.sh` 의 hit 중 일부만 읽었다).
- H10 의 「3xx 가 `HTTPError` 로 올라온다」와 H13 의 「TLS 실패가 감싸져 올라오는 경로」는 이
  설계가 재보지 않았다 — 구현 단계의 실측 항목으로 남겼다(§9-8).

**전수 증명이 아니다.**

---

## 17. 앞선 단계가 남긴 후속 항목

**기제**: S1(H1·H2·H3·N3·H4) 구현이 검수 1회차를 거치며 Major 3건(M1·M2·M3)과 Minor 4건
(m1~m4)을 반영했다. 그 검수가 함께 지적했지만 이번 회차의 승인 범위 밖이거나 선재
결함으로 판정된 것은 코드를 고치지 않고 이 절에 기록만 남긴다 — 근거는 그 검수의
실측이다. 이후 단계(S2 이후)가 추가하는 항목은 출처가 검수 지적일 수도, 구현 중 검수
이전에 스스로 발견한 것일 수도 있다 — 항목(또는 항목 묶음)마다 자신의 출처를 표시하고,
이 절 전체가 몇 번째 항목까지 어느 출처인지는 번호로 적지 않는다(바로 아래 한계 문단과
같은 이유 — 항목이 늘 때마다 낡는 자기 이동값이다).

**한계**: 아래 항목들은 "이번에 고치지 않기로 했다"의 기록이지 "안전하다"는 보증이
아니다. **건수를 여기 적지 않는다** — 회차가 늘 때마다 항목이 추가되는 목록이라 위
문단이 그 수를 말하면 곧 낡는다(검수 3회차: 항목 6·7 을 더했는데 이 두 문단이 "5건"
으로 남아 있었다. 바로 아래 항목 2 가 같은 계열을 스스로 교정한 절인데 같은 일이
다시 났다). 목록을 세면 된다.
판정을 뒤집을 새 근거가 나오면 별도 항목(또는 별도 PRP)으로 다시 연다.

**비망라 예시**:

1. **허브 `list_differing_managed_files` 의 `diff` 삼킴** — 선재 결함이지만 **비대칭은
   이번에 새로 생겼다**: H1 이 루트 `install.sh` 의 같은 계열 함수만 fail-loud 로 고쳐,
   루트는 `diff` 오류에서 중단하는데 허브는 여전히 침묵한다. N3(심링크 트윈)는 이번에
   등록했으면서 H1 트윈은 §2-A·§2-B·§11·§15·§16 어디에도 없다(산문 렌즈 전수 대조,
   hit 0) — §2-B 표제("조용히 빠뜨리지 않는다")와 어긋나는 자리다.
2. **`install.sh` 가 800줄 상한을 넘는다** — HEAD 시점에 이미 초과였고 이번 회차가 더
   늘렸다. 모듈 분리는 S1 범위 밖이다. 함수 단위 50줄 제한은 이번 회차가 추가한 함수를
   포함해 전부 통과한다. **줄 수를 숫자로 적지 않는다**(`rules-docs-sync.md` §17-1,
   `T39` 가 강제한다) — 이 파일을 고치는 커밋마다 움직이는 값이고, **이 항목의 초안이
   실제로 그렇게 낡았다**: 검수 2회차가 적어 둔 증분이 실측의 절반 남짓이었고, 「최대」라
   지목한 함수도 최대가 아니었다(손대지 않은 함수 둘이 더 길다). 세는 방법 —
   `wc -l install.sh` · `git show HEAD:install.sh | wc -l` · 함수별 줄 수는
   `awk '/^[a-z_]+\(\) \{/{n=$1;s=NR} /^\}$/{if(n){print NR-s+1, n; n=""}}' install.sh | sort -rn`.
3. **`HOME` 미설정 시 `--scope project` 가 전량 설치 후 `classify_against_global_command`
   에서 죽는다** — HEAD 도 같은 지점에서 죽으므로 회귀가 아니다. H4 의 `${HOME:-}` 방어는
   자기 범위(`reject_project_scope_at_home`) 안에서는 참이다.
4. **`mktemp`~`mv` 사이 시그널 사망 시 임시 manifest 파일 잔존** — 트랩이 없다. 그 잔존
   파일을 심은 채 재설치해도 무해함을 실측했다(rc=0, 유효 JSON 재발행).
5. **신규 `group_failures=()` 리셋 2건이 기본 실행 순서에서 죽은 코드** — `--only` 로
   그룹 순서를 뒤집을 때만 의미가 있다(앞 그룹이 조기 `return` 한 잔여물을 다음 그룹
   시작에서 지운다).
6. **허브의 `find` 상태 삼김** — m2 가 루트의 `find` fail-open 을 막았지만
   `hub/install.sh` 는 그대로다(`check_no_symlink_bin_targets`·`verify_installed_file_count`·
   `copy_managed_bin_files` 세 곳이 `< <(find …)` 로 상태를 보지 않는다). 그래서 **이번에
   새로 넣은 N3 심링크 가드가 `find` 실패 시 조용히 무동작이 된다**(검수 2회차 실측: 소스
   `hub/bin` 을 `chmod 000` 하면 exit 0 · 「21개 파일」 로그 · 실제 설치 0건 · 가드 진단
   없음). **회귀는 아니다** — HEAD 사본도 같은 픽스처에서 조용히 성공하고, 그 조건에서는
   복사가 0건이라 관통이 실제로 일어나지 않는다(sentinel 온전 확인). 고치지 않은 이유:
   설계가 허브 트윈으로 범위에 넣은 것은 N3 뿐이고, 제대로 고치려면 서브체크와 래칫이
   함께 움직인다. 1번과 같은 계열(같은 결함을 한쪽만 고쳐 생긴 비대칭)이라 함께 읽는다.
7. **`find` 실패 진단이 열거 결과 전체를 한 로그에 싣는다** — `list_symlink_check_candidates`
   의 진단이 `2>&1` 로 합친 출력을 그대로 담아, 실패 형태에 따라 수십 줄이 된다(`diff` 쪽
   진단은 통상 1~2줄). 원인 줄이 첫 줄에 오므로 진단 자체는 유효하다 — 부피만의 문제다.

**아래는 S2(H5) 구현 중 발견한 것이다(검수 이전 — 위 항목들과 출처가 다르다)**:

8. **H5 의 `--force` 백업 안전망이 `hub/install.sh` 에는 없다** — S2 가 넣은
   `backup_modified_managed_files` 는 루트 `install.sh` 에만 있다. `hub/install.sh` 의
   `--force` 는 여전히 무백업 직접 덮어쓰기다(`commands/harness-update.md` Phase 4b 문서가 그
   차이를 그대로 서술한다 — "hub/install.sh has no such ledger"). 1번 항목과 같은 계열
   (같은 결함을 한쪽만 고쳐 생긴 비대칭)이지만, 이번 설계 §6 이 대상 파일로 넣은 것은
   루트 `install.sh` 뿐이고(H5), `hub/install.sh` 는 매니페스트 자체가 없어 stale·modified
   분류(`filter_modified_files` 가 의존하는 대장 조회)를 재사용할 수 없다 — 백업 대상을
   가르려면 분류 기제부터 새로 설계해야 해 국소 수정을 넘어선다.
9. **`.bak-<타임스탬프>` 는 초 단위 해상도이고 `cp -p` 앞에 존재 검사가 없어, 그 이름을 가진
   기존 파일이면 무엇이든(우리 자신의 이전 백업이든 아니든) 같은 초 안에서 조용히 덮어써질
   수 있다** — 도달 경로는 실재한다(S2 검수 1회차 정정 — 1회차 초안의 반론은 설치가 완주하는
   경우에만 성립했다): `check_preconditions` 는 `check_directory_conflict` 를 rules·
   agents·commands 순서로 부르고 `validate_removals_file` 은 그 뒤에 있다. 첫 `--force`
   호출이 rules 백업까지 마친 뒤 이후 호출(agents·commands 의 `check_directory_conflict`
   또는 `validate_removals_file`)이 실패해 설치 전체가 중단되면, 백업은 남고 대상 파일은
   여전히 modified 상태로 남는다 — "첫 --force 실행이 반드시 성공해야 두 번째 실행에
   modified 가 없다"는 전제 없이도 같은 초 재시도가 성립한다. 그 상태에서 같은 초 안에
   같은 파일이 다시 수정되고 다시 `--force` 로 실행되면, 두 번째 `cp -p` 가 그 이름을 가진
   기존 파일(통상은 우리 자신의 첫 번째 백업)을 조용히 덮어쓴다.
   **선점자가 우리 백업이 아닐 수도 있다(S2 검수 2회차 LOW N4)**: 백업 경로는 대상 파일명과
   초 단위 접미사만으로 결정되므로, 그 정확한 이름을 우연히 가진 사용자 파일이 이미 있어도
   같은 방식으로 조용히 덮어써진다 — 검수자 실측: 향후 10초 창을 사용자 메모 파일 10개로
   먼저 선점한 뒤 `--force` 를 실행하면 exit 0 이고, install.sh 가 실제로 고른 초에 해당하는
   1건만 파괴되며 나머지 9건은 그대로 보존된다. 기준 커밋(`b567669`)에서는 같은 이름의 대상
   전용 파일이 `--force` 후에도 해시가 불변이었다 — **이번 회차(H5)가 새로 연 자리**이고,
   이 파일 머리말의 소유권 원칙(대상 디렉토리에만 존재하는 파일은 건드리지 않는다)에서
   벗어난다.
   **그래도 고치지 않는 이유가 「가능성이 낮다」에서 「그 가드가 해를 끼친다」로 바뀐다**:
   `retire_user_claude_md` 의 `[[ -e "$backup_path" ]]` fail-closed 를 그대로 옮겨 오면,
   내용이 다시 같아지는(같은 install.sh 재실행만 반복되고 파일이 다시 수정되지 않는) 무해한
   "중단 → 같은 초 재시도" 경로까지 하드 실패로 바꾼다 — 그 경로는 `retire_user_claude_md`
   에는 없는, H5 고유의 정상 재시도 형태다. 손실 규모도 다르다 — `retire_user_claude_md`
   는 `mv` 라 이름 충돌 시 유일한 은퇴 사본이 파괴되지만, H5 는 `cp` 라 원본(대상 파일)이
   그대로 살아있어 잃는 것은 "같은 초 안에 존재했던 백업 중간 상태"뿐이다. 사람 손으로
   재현하려면 여전히 같은 초 안에 같은 파일을 다시 수정하고 다시 `--force` 로 실행해야 해
   사실상 불가능하지만(자동화 스크립트는 가능), 그 희소성은 이제 판정의 보조 근거일 뿐
   주된 근거가 아니다 — 주된 근거는 위 가드 이식이 만드는 새 실패다. **같은 근거가 선점자가
   우리 백업이 아닌 경우에도 그대로 적용된다** — `-e`(또는 `-L`) 검사는 선점자의 출처(우리
   이전 백업인지, 우연히 같은 이름을 가진 사용자 파일인지)를 구분하지 못하므로, 막으려는
   가드 자체가 같은 코드고 같은 부작용(정상 재시도 경로의 신규 실패)을 낳는다. 이 PRP 는
   그 경로를 다루기로 하지 않았다(YAGNI, `karpathy-guidelines.md` #2 — 요청 범위를 넘는 방어).
10. **`T22` 그룹 안에서 신규 문면 검사(T22-168·T22-169)보다 앞서 `record_failure`+
    `return 1` 로 조기 이탈하는 관문(T22-162 등)이 있어, 그룹 끝에 붙은 신규 검사는 앞
    검사의 실패에 취약하다** — **같은 형태가 `T22` 뿐 아니라 `T14`·`T15` 에도 있다**
    (`T14-8`·`T15-3` 이 각각 자신보다 앞선 관문들 뒤에 있다, S2 검수 2회차 LOW N6). 지금은
    세 그룹 모두 그 앞 검사들이 전부 통과하므로 실제 피해는 없다(S2 검수 1회차 접지 렌즈
    실측 + 변조 재현이 그 증거다). 세 그룹을 `note_failure`/`finish_group` 형태로 바꿔 이
    취약성 자체를 없애는 것은 각 그룹의 실패 집계 방식을 바꾸는 별도 작업이라 이번 라운드의
    국소 수정 범위를 넘는다 — 코드는 고치지 않고 기록만 남긴다.
11. **`commands/harness-update.md` Phase 1 "Manifest Validation" 의 `version` ∈ `{ 1, 2, 3 }`
    열거가 자기 이동값이다** — `install.sh` 의 `MANIFEST_VERSION` 이 오르면 이 열거도
    함께 낡는다. S1 라운드에서 이미 지시됐던 기록 항목인데 이번 회차 전까지 이 절 어디에도
    없었다(S2 검수 1회차 접지·문면 렌즈 양쪽 확인). 고치지 않는 이유 — 이 값은 배포 감사가
    지목한 항목(H1~H13·N1~N3)이 아니고, 이번 라운드가 손댄 대상 파일 범위(§6)에 이 열거를
    포함하지 않는다. 세는 방법을 적어 자기 이동값 문제를 완화할 수는 있지만(예: `grep -n
    'MANIFEST_VERSION=' install.sh`), 그 개조까지 하면 이 PRP 의 국소 수정 범위를 넘는다 —
    수술적 변경 원칙(`karpathy-guidelines.md` #3)에 따라 기록만 남긴다.

**아래는 S2 검수 2회차가 남기고 이번 3회차가 범위 밖으로 판정한 새 항목이다(위 항목들과
출처가 다르다 — **항목 번호로 경계를 적지 않는다**: 항목이 늘거나 해소돼 빠지면 번호가
밀려 인용이 조용히 엉뚱한 항목을 가리킨다. 이 계열이 이 절에서 되풀이됐다 — S2 검수 1회차가
「아래는 S2(H5) 구현 중 발견한 것이다」 단락 도입부에서 같은 패턴을 지적해 고쳤고, 3회차가
이 문장에서 재생산했고, 그것을 메인 세션이 고치면서 **번호 인용을 하나 더 남겨** 3회차 델타
검수가 다시 지적했다. 그래서 지금은 번호가 아니라 **단락의 표제 문구**로 가리킨다)**:

12. **`-L` 가드는 심링크 전용이라 하드링크는 관통한다(S2 검수 2회차 MEDIUM N3)** —
    `backup_modified_managed_files` 가 백업 경로 자신에 붙인 `-L` 가드(S2 검수 1회차
    CRITICAL-1 로 추가)의 진단은 "대상 트리 밖에 쓰지 않고 중단합니다"라고 말하지만, 백업
    이름이 하드링크로 먼저 선점되면 `cp -p` 가 그 inode 를 그대로 따라가 대상 트리 밖 파일의
    내용을 파괴한다(검수자 실측: exit 0, 밖 파일 해시 `2f669775…`→`646efaf4…`).
    고치지 않는 근거 둘, 둘 다 실측이다 — (i) **기준 커밋(`b567669`)에서도 동일하다**:
    관리 잎 자신을 밖 inode 로 하드링크하면 `cp -R` + `--force` 가 같은 해시 변화
    (`594576c7…`→`1417a024…`)를 낸다 — 관리 경로를 겨냥한 `check_no_symlink_targets` 도
    설계상 심링크 전용이라 같은 사각을 갖고 있다. 즉 파일 전체에 걸친 선재 성질이지 이번
    회차가 만든 것이 아니다. (ii) **새 능력을 주지 않는다**: 백업 이름에 하드링크를 심으려면
    install.sh 가 고를 초 단위 타임스탬프를 맞춰야 하지만, 그럴 수 있는 주체는 관리 잎
    자신(타임스탬프 불필요)에도 심을 수 있다 — 노출은 오히려 백업 경로 쪽이 더 작다.
13. **`backup_modified_managed_files` 가 관리 디렉토리(rules·agents·commands)마다 `date` 를
    새로 부른다(S2 검수 2회차 LOW N7)** — 3회 호출되며 접미사를 각각 계산하므로, 초 경계를
    걸치는 실행은 한 번의 `--force` 가 서로 다른 접미사의 백업을 남긴다. 사용자가 "이 실행의
    백업"을 접미사로 한데 묶을 수 없다는 것 외에 피해는 없다. 고치려면 접미사를 호출부에서
    1회 계산해 인자로 넘겨야 해 함수 계약이 바뀐다 — 이 회차의 범위를 넘는다.

**아래는 S3 검수가 남긴 항목이다(위 항목들과 출처가 다르다 — 앞선 단계가 아니라 허브 제거
회차에서 나왔다)**:

14. **깨진 `~/.claude/settings.json` 이 이제 허브 제거를 막는다(S3 검수 접지, 의도된
    트레이드오프)** — 실제 `uninstall_hooks` 는 파싱 실패 시 `ok:false` 와 사유를 돌려주고,
    S3 의 게이트가 그것을 받아 `--force` 없이는 `bin/` 삭제를 중단한다(검수 실측: exit 1 ·
    `bin/` 보존). 기준 커밋에서는 `|| true` 가 그 실패를 삼켜 `bin/` 이 삭제됐다.
    **결함이 아니라 §4-3 이 고른 방향이다** — 사유가 하위 명령의 stdout 으로 사용자에게
    그대로 인쇄되고 `--force` 우회도 실측으로 동작한다. 다만 깨진 설정 파일은 현실에서
    생기는 상태이므로, **제거가 막히는 새 조건이 생겼다**는 사실을 기록한다.
15. **게이트가 하위 명령의 종료 코드를 보지 않는다 — stdout JSON 파싱 한 축뿐이다(S3 검수
    접지, 선재 성질)** — `ok:true` 를 인쇄한 뒤 비정상 종료하는 하위 명령은 통과한다(검수
    실측: 스텁이 `ok:true` 인쇄 후 종료 코드 7 → `--uninstall` exit 0 · `bin/` 삭제).
    **현재 도달 불가**다 — `hub/bin/hub.py` 의 세 하위 명령이 모두 `_report` 직후
    `ok` 값으로 종료 코드를 결정해 둘이 커플링돼 있다. 기준 커밋의 `stop_server_or_abort`
    도 같은 성질이었으므로 이번 회차의 회귀가 아니다. 기록하는 이유는 이 게이트를
    "fail-closed" 라 부르는 근거가 **한 축**이라는 것을 남겨 두기 위해서다.
16. **`require_python` 주석의 의도가 이미 성립하지 않는다(S3 검수 접지, 선재)** — 그 주석은
    「제거 경로에는 파이썬 버전 요구를 걸지 않는다 — 구버전 파이썬 머신에서 제거까지 막을
    이유가 없다」고 적었지만, `python3` 자체가 `PATH` 에 없으면 `--uninstall` 은 첫 하위
    명령 자리에서 중단한다(검수 실측: 기준 커밋과 현재 판 둘 다 exit 1 · `bin/` 보존,
    `--force` 를 주면 세 단계를 우회하고 완주). 이번 회차의 회귀가 아니고, 주석의 의도를
    실제로 성립시키려면 파이썬 없이도 되는 제거 경로를 새로 설계해야 해 범위를 넘는다.

**아래는 S4 검수가 남긴 항목이다(위 항목들과 출처가 다르다 — 앞선 단계가 아니라 사용량 API
실패 진단 회차에서 나왔다)**:

17. **`response_keys` 가 서버 응답 문자열을 값 검사 없이 디스크에 쓴다(S4 검수 접지, 선재)**
    — 요청의 `Authorization` 헤더 값을 그대로 JSON **키 이름**으로 되돌려주는 로컬 스텁
    서버를 붙이면 그 카나리아가 `response_keys` 를 거쳐 `last_usage_api_error.json` 에
    나타난다(검수자 실측). A-SEC 은 「`last_usage_api_error.json` 그 어디에도 나타나지
    않는다」고 쓰여 있어 이 시나리오에서 어긋난다.
    고치지 않는 근거 셋(검수자 판정) — (i) `describe_json_key_structure` 와 `response_keys`
    는 **선재 코드**이고 이번 회차는 그 위에 상한만 씌웠다, (ii) 이 시나리오는 상대가
    **이미 토큰을 받은 뒤**라 원격 노출의 확대가 아니라 로컬 잔존·화면 표시로의 노출이다,
    (iii) **이번 회차가 이 위험을 오히려 줄였다** — H10 이 임의 호스트를, H13 이 검증 실패
    호스트를 상대에서 뺀다.
    이번 회차가 추가한 `_capped_response_key_structure` 의 바이트 상한(위 §7-2 개정)이 이
    위험을 **부분적으로 완화한다** — 긴 키 이름은 잘린다. 다만 짧은 키로 되돌려주면 그대로
    남으므로 완화이지 해소가 아니다. 닫으려면 `_capped_response_key_structure` 가 경로
    성분의 길이·문자류까지 제한하는 것이 같은 자리다 — 이 PRP 는 그 확장을 하지 않는다.

**전수 증명이 아니다.**
