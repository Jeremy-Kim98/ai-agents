# 직접 준비할 것 (약 15분)

Claude Code가 대신 할 수 없는, 계정 로그인이 필요한 작업들입니다. 순서대로 하면 됩니다.

**준비물**: Max 5x 이상 구독 (가입 7일 경과), GitHub 계정, 앱을 설치할 수 있는 Slack 워크스페이스

---

## 1. API 크레딧 연결 (claude.ai)

1. 웹 브라우저로 claude.ai 접속 (모바일 앱에서는 안 됨)
2. **Settings → Billing** 으로 이동
3. **API credits** 항목에서 **Link organization** 선택
   - Console 조직이 없으면 이 과정에서 새로 만들 수 있습니다
   - 조직은 한 번 연결하면 직접 바꿀 수 없으니, 앞으로 개발용으로 쓸 조직을 고르세요
4. 연결이 끝나면 Console(platform.claude.com)의 Billing 페이지 **Promotional credits** 항목에 $100가 보입니다

## 2. API 키 발급 (Console)

1. platform.claude.com 접속, 1에서 연결한 조직인지 확인
2. **Workspaces** 메뉴에서 새 Workspace 생성 (이름 예: `digest`)
3. 그 Workspace의 **월 지출 한도(spend limit)** 를 $40 정도로 설정
   - 이 에이전트가 크레딧을 다 써버리는 것을 막는 안전장치입니다
4. **API keys** 메뉴에서 키 생성, Workspace는 방금 만든 `digest` 선택
5. 키(`sk-ant-...`)는 **한 번만 표시**되니 바로 4번의 `.env`에 붙여넣으세요

## 3. Slack 웹훅 발급

1. Slack에서 받을 채널을 먼저 만듭니다 (예: `#ai-브리핑`)
2. https://api.slack.com/apps 접속 → **Create New App** → **From scratch**
3. 앱 이름(예: `AI 브리핑`)을 정하고 워크스페이스 선택 → Create
4. 왼쪽 메뉴 **Incoming Webhooks** → 스위치 **On**
5. 아래쪽 **Add New Webhook** → 1에서 만든 채널 선택 → **허용**
6. 생성된 **Webhook URL** (`https://hooks.slack.com/services/...`) 복사 → `.env`에 붙여넣기
7. (선택) 레이더를 다른 채널로 받고 싶으면 5번을 한 번 더 해서 두 번째 URL을 `SLACK_WEBHOOK_URL_RADAR`에 넣습니다
8. (선택) **Basic Information → Display Information**에서 앱 아이콘과 색을 바꾸면 Slack에서 더 보기 좋습니다

> 회사·학교 워크스페이스라 앱 설치가 막혀 있으면 관리자 승인이 필요합니다. 개인 워크스페이스를 하나 만들어 쓰는 게 가장 간단합니다.

## 4. `.env` 파일 작성

폴더 안의 `.env.example`을 복사해 `.env`를 만들고 (Claude Code에 "`.env` 만들어줘"라고 해도 됩니다),
텍스트 편집기로 열어 값을 채웁니다. 따옴표는 필요 없습니다.

```
ANTHROPIC_API_KEY=sk-ant-...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_WEBHOOK_URL_RADAR=
```

키는 Claude Code 채팅창보다 **파일에 직접** 넣는 것을 권장합니다. `.env`는 GitHub에 올라가지 않습니다.

## 5. GitHub CLI 로그인 (Claude Code가 안내할 때)

터미널에서 직접 실행합니다.

```
gh auth login
```

GitHub.com → HTTPS → Login with a web browser 순서로 고르고, 화면에 나온 코드를 브라우저에 입력하면 됩니다.

---

준비가 끝나면 Claude Code에 "준비 완료"라고 알려주세요.
