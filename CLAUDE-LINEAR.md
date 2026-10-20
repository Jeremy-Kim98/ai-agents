# Claude Code 진행 지침: Linear 연동 추가

**전제**: 기본 설치(`CLAUDE.md` 1~10단계)가 끝나 AI 뉴스가 GitHub Actions에서 정상 동작하는 상태.
`CLAUDE.md`의 "지켜야 할 규칙"을 그대로 따른다 (한국어, `.env` 값 출력 금지, 🙋에서 멈춤, 💰 전에 확인).

추가로 지킬 것:
- 저장소는 공개다. **야간 작업 내용, 이슈 제목, 첨부 내용을 저장소나 로그에 남기지 않는다.**
  `night_queue.py`는 이슈 번호만 출력하도록 되어 있으니, 디버깅하며 print를 추가했다면 커밋 전에 반드시 지운다.
- Linear GraphQL 오류가 나면 스키마 문제일 수 있다. 오류 메시지를 보고 `agents/linear.py`의 쿼리를 최소한으로 고친다
  (필요하면 Linear API 문서나 introspection으로 필드 이름 확인).

## 1. 추가 파일 반영 (무료)
추가 패키지(`ai-agents-linear-addon/`)는 기존 `ai-agents/`와 같은 폴더 구조로, **바뀐 파일과 새 파일만** 들어 있다.
1. 기본 설치 중에 수정된 파일이 있는지 확인한다: `ai-agents`에서 `git log --oneline`과
   `git diff <첫 커밋> HEAD --stat` (첫 커밋 = 원본 zip 상태).
2. 추가 패키지의 각 파일을 `ai-agents`의 같은 경로로 복사한다.
   - 새 파일, 그리고 기본 설치 이후 수정되지 않은 기존 파일 → 그대로 덮어쓴다.
   - 기본 설치 중에 **수정된 기존 파일**(예: 에러를 고친 `common.py`) → 덮어쓰지 말고, 그 수정 사항을 보존하면서
     추가 패키지의 변경을 병합한다. 병합 내용을 사용자에게 설명한다.
3. `git status`, `git diff --stat`으로 결과를 보여주고 주요 변경을 3~5줄로 요약한다.
4. 가상환경에서 `pip install -r requirements.txt` (python-docx, openpyxl 추가됨).
5. 오프라인 테스트: `python -m tests.test_offline` → 21개 모두 통과해야 한다.
6. 기존 기능이 그대로인지: `python -m agents.ai_news --sample`, `python -m agents.robot_radar --sample`.

## 2. 🙋 Linear API 키 발급
사용자에게 안내하고 완료를 기다린다:
- Linear → Settings → **Security & access** (또는 API) → **Personal API keys** → 새 키 만들기
  (주소 `linear.app/settings/api`로도 갈 수 있다. 메뉴 이름은 Linear 버전에 따라 조금 다를 수 있다)
- 권한을 고르는 화면이 있으면 **읽기와 쓰기**(이슈·댓글·라벨 생성), 팀 접근은 쓸 팀을 포함
- 키(`lin_api_...`)를 `.env`의 `LINEAR_API_KEY=`에 사용자가 직접 넣는다

## 3. Linear 준비 (무료)
```
python -m agents.linear_setup
```
- 팀 목록이 나오면 🙋 사용자에게 어느 팀을 쓸지 묻고, 그 팀 키를 `.env`의 `LINEAR_TEAM_KEY=`에 넣는다 (키 값이 아니라 팀 약어라 기록해도 된다).
- 다시 실행해 라벨 3개(`야간작업`, `야간완료`, `레이더`) 생성과 상태 목록을 확인한다.
- `In Review` 상태가 없으면 사용자에게 처리 후 옮길 상태를 고르게 하고 `.env`에 `LINEAR_REVIEW_STATE=`로 넣는다
  (나중에 저장소 변수로도 등록: `gh variable set LINEAR_REVIEW_STATE --body "<상태>"`).

## 4. 대기열 확인 (무료)
```
python -m agents.night_queue --dry-run
```

## 5. 💰 야간 작업 시험 (약 $0.05~0.2)
```
python -m agents.linear_setup --test-issue
python -m agents.night_queue --issue <생성된 이슈 번호>
```
사용자에게 확인받을 것: Linear 이슈에 결과 댓글, 라벨이 `야간완료`로, 상태 변경, Slack에 "🌙 야간 작업" 요약.
시험 이슈는 확인 후 사용자가 지우거나 Cancel 해도 된다.

## 6. 💰 (선택) 레이더 자동 등록 시험 (약 $0.5~0.8)
```
python -m agents.robot_radar --local --slack --linear
```
🔥 항목이 있으면 `[레이더]` 이슈가 생기고 Slack에 📌 이슈 번호가 붙는다. 🔥 항목이 없으면 등록 없이 끝나는 게 정상이다.

## 7. GitHub 반영 (무료)
1. `bash scripts/setup.sh` 재실행 → `LINEAR_API_KEY` 시크릿, `LINEAR_TEAM_KEY` 변수가 추가로 등록된다.
2. 커밋 전 점검: `git diff`에 키 값이나 작업 내용이 없는지 확인. `.env`가 커밋 대상이 아닌지 확인.
3. `git add -A && git commit -m "Linear 연동: 야간 작업 큐, 레이더 자동 등록" && git push`

## 8. 💰 Actions 확인
1. Linear에 실제로 맡길 작은 일 하나를 사용자와 함께 이슈로 만들고 `야간작업` 라벨을 붙인다 (또는 5단계 시험 이슈에 라벨을 다시 붙인다).
2. `gh workflow run night-queue.yml` → `gh run watch`
3. 성공하면 `gh run view --log`로 **로그에 이슈 번호 외의 내용이 없는지** 확인한다.

## 9. 완료 보고
- 야간 작업 자동 실행 시각: 매일 00:30, 04:00 (KST)
- 사용법은 `LINEAR.md`를 안내한다 (맡기는 법, 수정 요청, 레이더 이슈 다루는 법, 비용)
- 바로 처리: `gh workflow run night-queue.yml -f issue=RES-12`

## 문제 해결

| 증상 | 원인과 조치 |
|---|---|
| `Authentication required`, 401 | Linear 키 오타·삭제. 새로 발급해 `.env`와 시크릿 갱신 |
| `팀 키 '...'를 찾을 수 없습니다` | `LINEAR_TEAM_KEY`가 틀림. `linear_setup`의 팀 목록에서 다시 고르기 |
| GraphQL `Cannot query field` / `Unknown argument` | Linear 스키마 변경. 오류에 나온 필드만 최소 수정 |
| 첨부 `내려받기 실패 (401/403)` | 키 권한 부족. 읽기 권한과 팀 접근 확인 |
| 대기열이 비어 있음 | 라벨 이름이 정확히 `야간작업`인지, 이슈가 `LINEAR_TEAM_KEY` 팀에 있는지, 완료·취소 상태가 아닌지 확인 |
| 결과는 왔는데 Linear 알림이 없음 | 정상. 내 키로 단 댓글이라 Linear가 알리지 않음. Slack 요약으로 확인 |
