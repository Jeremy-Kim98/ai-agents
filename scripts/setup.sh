#!/usr/bin/env bash
# GitHub 저장소 생성 → 시크릿·변수 등록 → Pages 활성화까지 한 번에.
# 사용법: bash scripts/setup.sh [저장소이름]   (기본: ai-agents)
# 여러 번 실행해도 안전합니다 (이미 된 단계는 건너뜀).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_NAME="${1:-ai-agents}"

say()  { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
fail() { printf '\n✗ %s\n' "$1" >&2; exit 1; }
envval() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' || true; }

say "0. 사전 점검"
command -v git >/dev/null || fail "git이 없습니다"
command -v gh  >/dev/null || fail "GitHub CLI(gh)가 없습니다: https://cli.github.com"
gh auth status >/dev/null 2>&1 || fail "gh 로그인이 필요합니다: gh auth login"
[ -f .env ] || fail ".env가 없습니다: cp .env.example .env 후 값을 채우세요"
[ -n "$(envval ANTHROPIC_API_KEY)" ] || fail ".env의 ANTHROPIC_API_KEY가 비어 있습니다"
[ -n "$(envval SLACK_WEBHOOK_URL)" ] || fail ".env의 SLACK_WEBHOOK_URL이 비어 있습니다"
OWNER="$(gh api user -q .login)"
OWNER_LC="$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')"
echo "  GitHub 계정: $OWNER, 저장소: $REPO_NAME"

say "1. git 준비 (.env는 절대 올라가지 않게 확인)"
[ -d .git ] || git init -q
git check-ignore -q .env || fail ".env가 .gitignore에 없습니다. 중단합니다"
git add -A
git diff --cached --name-only | grep -qx '.env' && fail ".env가 커밋 대상에 있습니다. 중단합니다"
git -c user.name="${GIT_AUTHOR_NAME:-$OWNER}" -c user.email="${GIT_AUTHOR_EMAIL:-$OWNER@users.noreply.github.com}" \
    commit -qm "초기 설정" 2>/dev/null || echo "  (커밋할 변경 없음)"
git branch -M main

say "2. GitHub 저장소 만들고 올리기"
if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin main
elif gh repo view "$OWNER/$REPO_NAME" >/dev/null 2>&1; then
  git remote add origin "https://github.com/$OWNER/$REPO_NAME.git"
  git push -u origin main
else
  gh repo create "$REPO_NAME" --public --source=. --remote=origin --push \
     --description "매일 AI 뉴스, 수·토 로봇+AI 레이더를 Slack으로"
fi

say "3. 시크릿 등록 (값은 화면에 표시하지 않음)"
for name in ANTHROPIC_API_KEY SLACK_WEBHOOK_URL SLACK_WEBHOOK_URL_RADAR LINEAR_API_KEY SLACK_WEBHOOK_URL_NIGHT; do
  v="$(envval "$name")"
  if [ -n "$v" ]; then
    printf '%s' "$v" | gh secret set "$name" --repo "$OWNER/$REPO_NAME" >/dev/null && echo "  ✓ $name"
  else
    echo "  - $name 비어 있음 (건너뜀)"
  fi
done

say "4. 변수 등록"
PAGES_URL="https://$OWNER_LC.github.io/$REPO_NAME"
gh variable set PAGES_BASE_URL --body "$PAGES_URL" --repo "$OWNER/$REPO_NAME" && echo "  ✓ PAGES_BASE_URL=$PAGES_URL"
TEAM_KEY="$(envval LINEAR_TEAM_KEY)"
if [ -n "$TEAM_KEY" ]; then
  gh variable set LINEAR_TEAM_KEY --body "$TEAM_KEY" --repo "$OWNER/$REPO_NAME" && echo "  ✓ LINEAR_TEAM_KEY=$TEAM_KEY"
else
  echo "  - LINEAR_TEAM_KEY 비어 있음 (Linear 연동을 쓰지 않으면 정상)"
fi

say "5. GitHub Pages 켜기 (main 브랜치 /docs)"
if gh api "repos/$OWNER/$REPO_NAME/pages" >/dev/null 2>&1; then
  gh api -X PUT "repos/$OWNER/$REPO_NAME/pages" -f "source[branch]=main" -f "source[path]=/docs" >/dev/null || true
  echo "  ✓ 이미 켜져 있음 (설정 갱신)"
else
  gh api -X POST "repos/$OWNER/$REPO_NAME/pages" -f "source[branch]=main" -f "source[path]=/docs" >/dev/null \
    && echo "  ✓ 켜짐. 첫 배포까지 1~2분 걸립니다"
fi

say "완료"
cat <<MSG
  저장소:  https://github.com/$OWNER/$REPO_NAME
  보관함:  $PAGES_URL/
  수동 실행:
    gh workflow run ai-news.yml     --repo $OWNER/$REPO_NAME
    gh workflow run robot-radar.yml --repo $OWNER/$REPO_NAME
    gh workflow run night-queue.yml --repo $OWNER/$REPO_NAME
    gh run watch --repo $OWNER/$REPO_NAME
MSG
