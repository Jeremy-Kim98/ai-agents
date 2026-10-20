"""로봇+AI 기술 레이더 (수요일, 토요일 아침).

실행: python -m agents.robot_radar            (실제 실행, GitHub Actions용)
      python -m agents.robot_radar --sample   (API 없이 화면만 확인)
      python -m agents.robot_radar --local    (실제 API 1회, preview/에만 저장)
      python -m agents.robot_radar --local --slack --linear  (위 + Slack 전송 + Linear 자동 등록 시험)
연구 내용은 agents/config.py의 RESEARCH_CONTEXT에서 수정.
"""
from agents import config, linear
from agents.common import log, run_agent

SYSTEM = f"""너는 로봇과 AI 기술 동향을 분석해 주는 연구 보조원이다. 한국어로 쓴다.
독자는 로봇·AI 분야 박사과정생이며, 연구 내용은 다음과 같다:
{config.RESEARCH_CONTEXT}

다루는 범위:
- 로봇 파운데이션 모델, VLA(시각-언어-행동) 모델, 휴머노이드·매니퓰레이션 주요 발표
- 객체 검출·분할 모델 신규 버전 (YOLO 계열, 오픈 어휘 검출 등)
- 로봇 시뮬레이터·가상환경(Isaac Sim/Lab, MuJoCo, Genesis 등)과 벤치마크(BEHAVIOR, RLBench 등)
- 모방학습·강화학습 데이터셋, 원격조작·VR 기반 시연 수집 도구
- 엣지 AI 하드웨어·추론 최적화 (Jetson, TensorRT, 양자화)
- ROS 2, LeRobot 등 오픈소스 도구의 의미 있는 릴리스

규칙:
- 반드시 웹 검색으로 확인한 것만 쓴다.
- apply에는 위 연구의 어느 부분(가상환경 구축, 과제 학습, 시연 데이터 수집,
  사람/로봇 역할 분담, 배포·추론)에
  어떻게 쓸 수 있는지 구체적으로 1~2문장. 연관이 약하면 솔직하게 '직접 연관 낮음'으로 시작한다.
- quote에는 url 페이지 본문에 실제로 있는 문장 일부를 한 글자도 바꾸지 말고 15단어 이내로 옮긴다.
  원문 언어 그대로 둔다(번역 금지). 시스템이 자동 대조하며, 정확히 옮길 수 없으면 빈 문자열.
- 가능한 한 1차 출처(공식 발표, 논문, GitHub 릴리스)를 url로 쓴다."""


def feedback_text():
    """Linear에서 진행·완료한 레이더 이슈와 취소한 이슈를 관심사 힌트로 쓴다."""
    try:
        done, dropped = linear.radar_feedback()
    except Exception as e:
        log(f"[warn] Linear 피드백 조회 실패: {type(e).__name__}")
        return ""
    if not done and not dropped:
        return ""
    lines = ["\n사용자 반응 (Linear 기록, 비슷한 주제의 비중을 조절하라):"]
    if done:
        lines.append("관심 있어 진행한 주제:\n" + "\n".join(f"- {t}" for t in done))
    if dropped:
        lines.append("관심 없다고 취소한 주제:\n" + "\n".join(f"- {t}" for t in dropped))
    return "\n".join(lines) + "\n"


def build_prompt(today, recent):
    avoid = "\n".join(f"- {t}" for t in recent) or "(없음)"
    return f"""오늘은 {today:%Y년 %m월 %d일} (한국시간)이다. 지난 리포트 이후 약 4일간의 로봇+AI 기술 소식을 찾아라.

이전 리포트에서 이미 다룬 항목 (새 진전이 없으면 제외):
{avoid}
{feedback_text()}
5~{config.RADAR_MAX_ITEMS}개를 골라, 마지막에 아래 형식의 JSON 하나만 ```json 블록으로 출력하라.
{{
  "headline": "이번 기간 흐름을 한 문장으로",
  "items": [
    {{
      "title": "한국어 제목",
      "summary": "무엇이 나왔는지 2문장 이내",
      "why": "기술적으로 왜 의미 있는지 한 줄",
      "apply": "내 연구 파이프라인 적용 포인트",
      "category": "로봇모델 | 검출 | 엣지AI | 시뮬레이션 | 오픈소스 중 하나",
      "importance": 1~3 정수 (3 = 내 연구와 직결),
      "source": "매체 또는 사이트 이름",
      "date": "YYYY-MM-DD",
      "url": "https://...",
      "quote": "원문 그대로의 짧은 문구"
    }}
  ]
}}"""


if __name__ == "__main__":
    run_agent(key="robot-radar", label="로봇+AI 레이더", emoji="🤖", system=SYSTEM,
              build_prompt=build_prompt, max_searches=config.RADAR_MAX_SEARCHES,
              max_items=config.RADAR_MAX_ITEMS, show_apply=True,
              webhook_env="SLACK_WEBHOOK_URL_RADAR", on_items=linear.radar_to_linear)
