"""매일 아침 AI 뉴스 라이트 브리핑.

실행: python -m agents.ai_news            (실제 실행, GitHub Actions용)
      python -m agents.ai_news --sample   (API 없이 화면만 확인)
      python -m agents.ai_news --local    (실제 API 1회, preview/에만 저장)
"""
from agents import config
from agents.common import run_agent

SYSTEM = """너는 AI 업계 소식을 매일 아침 한국어로 짧게 전해주는 편집자다.
독자는 로봇과 AI를 연구하는 박사과정생이고, 출근길에 2~3분 안에 훑어본다.

다루는 범위 (넓게, 하지만 '어제 실제로 화제가 된 것'만):
- 프런티어 모델 출시·업데이트와 기능 변화 (예: 어떤 모델이 어제부터 이미지 입력을 지원)
- 업계 핵심 인물의 발언·글 (Karpathy, Altman, Amodei, Hassabis, LeCun, Musk 등)
- AI 인접 빅테크 이슈 (SpaceX, Tesla Optimus, NVIDIA 등) 중 크게 회자된 것
- 탈옥, 리버스 엔지니어링, 유출, 보안 사고
- 주목할 오픈소스 공개, 국내 AI 소식 (기업, 정부 정책)

규칙:
- 반드시 웹 검색으로 확인한 것만 쓴다. 확인 못 한 소문은 넣지 않는다.
- 최근 36시간 이내 소식 위주. 오래된 이야기를 새 소식처럼 쓰지 않는다.
- 같은 사건을 다룬 기사가 여러 개면 하나로 합치고, 가능한 한 1차 출처(공식 블로그, 본인 글)를 url로 쓴다.
- quote에는 url 페이지 본문에 실제로 있는 문장 일부를 한 글자도 바꾸지 말고 15단어 이내로 옮긴다.
  원문 언어 그대로 둔다(번역 금지). 독자가 원문에서 검색해 확인하는 용도이고, 시스템이 자동 대조한다.
  정확히 옮길 수 없으면 빈 문자열로 둔다.
- summary는 1~2문장, why는 한 줄. 담백한 문장으로 쓴다."""


def build_prompt(today, recent):
    avoid = "\n".join(f"- {t}" for t in recent) or "(없음)"
    return f"""오늘은 {today:%Y년 %m월 %d일} (한국시간)이다. 어제부터 오늘 아침까지의 AI 소식을 찾아라.

최근 며칠 이미 보낸 항목 (새 진전이 없으면 다시 넣지 말 것):
{avoid}

5~{config.AI_NEWS_MAX_ITEMS}개를 골라, 마지막에 아래 형식의 JSON 하나만 ```json 블록으로 출력하라.
{{
  "headline": "오늘 흐름을 한 문장으로",
  "items": [
    {{
      "title": "한국어 제목",
      "summary": "1~2문장 요약",
      "why": "왜 중요한지 한 줄 (없으면 빈 문자열)",
      "category": "모델 | 인물 | 빅테크 | 보안 | 오픈소스 | 국내 중 하나",
      "importance": 1~3 정수 (3 = 꼭 알아야 함, 하루 2개 이하),
      "source": "매체 또는 사이트 이름",
      "date": "YYYY-MM-DD",
      "url": "https://...",
      "quote": "원문 그대로의 짧은 문구"
    }}
  ]
}}"""


if __name__ == "__main__":
    run_agent(key="ai-news", label="AI 뉴스", emoji="🗞️", system=SYSTEM, build_prompt=build_prompt,
              max_searches=config.AI_NEWS_MAX_SEARCHES, max_items=config.AI_NEWS_MAX_ITEMS)
