# Claude Code 진행 지침

이 폴더는 GitHub Actions로 **매일 AI 뉴스**(06:30 KST), **수·토 로봇+AI 레이더**(07:00 KST)를
만들어 Slack으로 보내는 프로젝트다. 사용자가 이 문서를 읽고 설치를 진행해 달라고 하면 아래 단계를 순서대로 따른다.

## 지켜야 할 규칙

- 사용자와 **한국어**로 대화한다. 각 단계 시작 전에 할 일을 한 줄로 말하고, 끝나면 결과를 짧게 보고한다.
- **`.env` 내용은 절대 출력하지 않는다.** `cat .env`, `echo $ANTHROPIC_API_KEY` 금지. 값 확인은 `python -m agents.check` 결과로만 한다.
  사용자가 채팅에 키를 붙여넣으면 화면에 다시 표시하지 말고 `.env`에만 기록한다.
- `.env`는 절대 커밋하지 않는다 (`.gitignore`에 있음, `scripts/setup.sh`도 이중 확인함).
- 🙋 표시 단계는 사용자가 직접 해야 한다. 멈추고 `SETUP.md`의 해당 절을 안내한 뒤 "완료"라고 할 때까지 기다린다.
- 💰 표시 단계는 API 크레딧을 쓴다. 실행 전에 예상 비용을 말하고 사용자 확인을 받는다.
- 코드 수정은 에러 해결에 필요한 최소한으로 하고, 무엇을 왜 고쳤는지 설명한다.
  모델 ID, 가격, 실행 시각, 프롬프트 내용 변경은 사용자 동의를 먼저 받는다.
- OS에 맞게 명령을 바꿔 쓴다 (Windows면 `python`/`py`, `.venv\Scripts\activate`, Git Bash로 `bash` 실행 등).

## 단계

### 1. 내용 검토와 환경 확인 (무료)
1. 폴더 구성과 `agents/*.py`, `.github/workflows/*.yml`, `scripts/setup.sh`를 훑어보고 이상한 점이 있으면 먼저 보고한다.
2. `python --version`(3.10 이상), `git --version`, `gh --version`을 확인한다. 없으면 OS에 맞는 설치 방법을 안내하거나 사용자 동의 후 설치한다 (macOS: `brew install gh`, Windows: `winget install GitHub.cli`).
3. 가상환경을 만들고 의존성을 설치한다: `python -m venv .venv` → 활성화 → `pip install -r requirements.txt`.

### 2. 샘플 미리보기 (무료, API 호출 없음)
```
python -m agents.ai_news --sample
python -m agents.robot_radar --sample
```
`preview/robot-radar/<날짜>.html`을 브라우저로 열어 사용자에게 보여주고 (`open` / `start`),
`preview/*-slack.json`이 Slack에 어떻게 보일지 간단히 설명한다.

### 3. 🙋 키와 웹훅 준비
`.env`가 없으면 `cp .env.example .env`로 만든다.
사용자에게 `SETUP.md` 1~4절(크레딧 연결, API 키, Slack 웹훅, .env 입력)을 안내하고 완료를 기다린다.

### 4. 연결 점검 (비용 1원 미만)
```
python -m agents.check
```
✗가 있으면 아래 문제 해결 표를 보고 원인을 설명한다. 모두 ✓면 사용자에게 Slack 채널에 테스트 메시지가 왔는지 확인받는다.

### 5. 💰 실제 1회 시험 실행 (약 $0.3~0.6)
```
python -m agents.ai_news --local --slack
```
실제 검색·정리 후 Slack으로 보내고, 리포트는 `preview/`에만 저장한다 (기록·누적 비용에는 남지 않음).
로그의 항목 수, 인용 확인 건수, 비용을 보고하고, 사용자에게 Slack 메시지 품질을 확인받는다.
사용자가 원하면 `python -m agents.robot_radar --local --slack`도 실행한다 (약 $0.5~0.8).

### 6. 🙋 GitHub 로그인
`gh auth status`로 확인하고, 로그인이 안 돼 있으면 사용자에게 터미널에서 `gh auth login`을 직접 실행하도록 안내한다
(GitHub.com → HTTPS → 브라우저 로그인). 대화형 입력이 필요하므로 Claude Code가 대신 실행하지 않는다.

### 7. GitHub 저장소·시크릿·Pages 설정 (무료)
```
bash scripts/setup.sh            # 저장소 이름을 바꾸려면: bash scripts/setup.sh 원하는이름
```
공개 저장소를 만들고, `.env` 값을 시크릿으로 등록하고, `PAGES_BASE_URL` 변수와 GitHub Pages를 설정한다.
여러 번 실행해도 안전하다. 출력 결과(저장소 주소, 보관함 주소)를 사용자에게 전달한다.

### 8. 💰 GitHub Actions 첫 실행 (각 $0.3~0.8)
```
gh workflow run ai-news.yml
gh run watch
```
실패하면 `gh run view --log-failed`로 원인을 찾아 고치고, 커밋·푸시 후 다시 실행한다.
성공하면 `robot-radar.yml`도 같은 방식으로 실행한다.

### 9. 결과 확인
1~2분 뒤 보관함 주소가 열리는지 확인한다 (`curl -sI <PAGES_BASE_URL>/`가 200).
Slack 메시지 하단의 "전체 리포트" 링크가 열리는지 사용자에게 확인받는다.

### 10. 완료 보고
- 다음 자동 실행 시각을 한국시간으로 계산해 알려준다 (AI 뉴스 매일 06:30, 레이더 수·토 07:00, 대기열 때문에 늦을 수 있음).
- 자주 바꿀 곳은 `agents/config.py`(연구 내용, 검색 횟수, 월 예산 경고선)라는 것을 안내한다.
- 로컬 `preview/` 폴더는 지워도 된다는 것을 알려준다.

## 문제 해결

| 증상 | 원인과 조치 |
|---|---|
| `authentication_error`, 401 | 키 오타 또는 삭제된 키. Console에서 새로 발급해 `.env`와 시크릿을 갱신 (`bash scripts/setup.sh` 재실행) |
| `credit balance is too low` | API 크레딧이 이 조직에 연결 안 됨, 또는 소진. `SETUP.md` 1절 확인. 키가 크레딧 연결된 조직에서 발급됐는지 확인 |
| 검색 도구 관련 400 오류 | 코드가 최신 버전 → 기본 버전으로 자동 재시도함. 둘 다 실패하면 `config.SEARCH_TOOL_VERSIONS`와 모델 지원 여부를 공식 문서에서 확인 |
| Slack `invalid_token`, `no_service`, 404 | 웹훅이 삭제됨. 새로 발급해 `.env`·시크릿 갱신 |
| Slack `action_prohibited`, 403 | 워크스페이스 관리자가 앱 설치를 막음. 관리자 승인 필요 |
| Actions에서 `git push` 거부 | 저장소 Settings → Actions → General → Workflow permissions를 "Read and write"로 |
| 보관함 주소 404 | 첫 배포 대기(1~2분). 계속되면 Settings → Pages에서 main / docs 확인 |
| 예약 시간에 안 옴 | GitHub 대기열로 지연될 수 있음. Actions 탭에서 실행 기록 확인 |
| JSON 파싱 실패 로그 | 자동으로 Haiku가 형식을 복구함. 반복되면 해당 실행 로그를 사용자에게 보여주고 프롬프트 조정 제안 |
