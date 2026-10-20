"""자주 바꿀 설정은 모두 여기에. 환경변수로도 덮어쓸 수 있다 (빈 값이면 기본값 사용)."""
import os

# 모델: 정리·판단은 Sonnet, JSON 복구 같은 잡일은 Haiku
MODEL = os.getenv("CLAUDE_MODEL") or "claude-sonnet-5-5"
HELPER_MODEL = os.getenv("CLAUDE_HELPER_MODEL") or "claude-haiku-5-5"

# 1회 실행당 웹 검색 상한 (검색 1회 = $0.01 + 결과 토큰)
AI_NEWS_MAX_SEARCHES = int(os.getenv("AI_NEWS_MAX_SEARCHES") or 8)
RADAR_MAX_SEARCHES = int(os.getenv("RADAR_MAX_SEARCHES") or 12)

# 한 번에 보낼 항목 수 상한
AI_NEWS_MAX_ITEMS = 8
RADAR_MAX_ITEMS = 8

# 월 예산 경고선 (USD). 이번 달 누적이 80%를 넘으면 Slack 하단에 경고 표시
MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET") or 40)

# 로봇+AI 레이더의 '내 연구 적용' 분석 기준. 연구가 바뀌면 여기만 수정
RESEARCH_CONTEXT = """로봇 조작 학습을 위한 가상환경과 시연 데이터 수집.
시뮬레이션에서 조작 과제를 학습시키고, VR·원격조작 등 사람이 참여하는 인터페이스로 시연 데이터를 모은다.
로봇이 스스로 학습할 과제와 사람의 시연이 필요한 과제를 가르는 것이 핵심 문제."""

# 비용 추정용 단가 (USD / 100만 토큰: 입력, 출력). 가격이 바뀌면 여기만 수정
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
SEARCH_PRICE = 0.01

# 웹 검색 도구: 최신(동적 필터링, 토큰 절약) → 기본 순서로 시도
SEARCH_TOOL_VERSIONS = ["web_search_20260209", "web_search_20250305"]

# ---------------------------------------------------------------- Linear 연동
LINEAR_TEAM_KEY = os.getenv("LINEAR_TEAM_KEY") or ""          # 예: RES (이슈 번호 앞의 영문)
NIGHT_LABEL = os.getenv("NIGHT_LABEL") or "야간작업"            # 이 라벨이 붙은 이슈를 밤에 처리
NIGHT_DONE_LABEL = os.getenv("NIGHT_DONE_LABEL") or "야간완료"  # 처리 후 붙는 라벨
RADAR_LABEL = os.getenv("RADAR_LABEL") or "레이더"              # 레이더 자동 등록 이슈 라벨
LINEAR_REVIEW_STATE = os.getenv("LINEAR_REVIEW_STATE") or "In Review"  # 처리 후 옮길 상태 (없으면 그대로 둠)

NIGHT_MAX_ISSUES = int(os.getenv("NIGHT_MAX_ISSUES") or 5)      # 한 번에 처리할 최대 이슈 수
NIGHT_MAX_SEARCHES = int(os.getenv("NIGHT_MAX_SEARCHES") or 5)  # 이슈당 웹 검색 상한
NIGHT_MAX_FILE_MB = 25                                          # 첨부 파일 1개 최대 크기
RADAR_TO_LINEAR_MIN_IMPORTANCE = 3                              # 이 중요도 이상인 레이더 항목만 Linear 등록
