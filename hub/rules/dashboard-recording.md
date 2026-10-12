# 허브 진행 기록 (hub/rules/dashboard-recording.md — hub/install.sh 가 배포·제거한다)

- **전체 경로·축약 경로 작업은 진행 상황을 허브에 기록한다** — 아래 기록기를 Bash 로 직접 부른다
  (인자는 홑따옴표. 본문의 `'` 는 `’` 로 바꾼다):
  `python3 -- "$HOME/.claude/hub/bin/hub_dashboard_log.py" <서브커맨드> …`

  | 시점 | 호출 |
  |------|------|
  | 착수 보고 | `init '<제목>' '설계|승인|구현|검수'` (축약 경로: `'구현|검수'`) |
  | PRP 작성 완료 | `log design '<요약>'` |
  | 사용자 승인 수령 | `log approve '<요약>'` |
  | 구현 완료(회차마다) | `log impl '<요약>' ['<상세>']` |
  | 검수 결과 | `log pass '<요약>' ['<상세>']` 또는 `log fail '<요약>' '[<사유 범주>] <상세>'`(범주는 검수 Verdict 의 것) — 회차는 자동 |
  | 커밋·푸시 | `log commit '<커밋 제목>'` |

  단계 상태·진행률·활성 단계 상세는 위 기록에서 파생된다 — 서브에이전트 디스패치·결과 시점에는
  아무것도 기록하지 않는다(허브가 호스트 기록으로 그린다). 출력이 `OK` 가 아니면(`NOSESSION`·
  `DISABLED`·`NOINIT`…) 그 한 줄만 착수 보고에 남기고 이후 호출을 생략한다.
  끄기: `/hub dashboard off` — `.claude/settings.local.json` 의 `dashboard_enabled`(나만·커밋 안 됨).
