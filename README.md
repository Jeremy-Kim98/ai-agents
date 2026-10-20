# AI 뉴스 & 로봇+AI 레이더 → Slack

자는 동안 Claude가 웹을 검색해 정리하고, 아침에 Slack으로 보내주는 에이전트 2개입니다.

| 에이전트 | 도착 (KST) | 내용 |
|---|---|---|
| 🗞️ AI 뉴스 | 매일 06:30 | 어제~오늘 AI 소식 5~8개. 모델 기능 변화, 업계 인물 발언, 빅테크, 보안·탈옥, 오픈소스, 국내 |
| 🤖 로봇+AI 레이더 | 수·토 07:00 | 로봇 모델, 검출 모델, 엣지 AI, 시뮬레이션·시연 데이터 소식 + 항목마다 "내 연구 적용" 분석 |
| 🌙 야간 작업 큐 (Linear) | 매일 00:30, 04:00 | Linear에서 `야간작업` 라벨 붙인 이슈를 처리해 결과를 댓글로, 요약은 Slack으로 |

GitHub 대기열 사정으로 도착이 늦어질 수 있습니다.

## 처음 설치

1. `SETUP.md`대로 API 키와 Slack 웹훅을 준비합니다 (약 15분)
2. 이 폴더에서 Claude Code를 실행하고 `CLAUDE.md`대로 진행해 달라고 합니다
3. Linear 연동은 `CLAUDE-LINEAR.md`로 이어서 설치합니다. 사용법은 `LINEAR.md`

## 동작 방식

```
GitHub Actions (예약 실행)
  → Claude Sonnet + 웹 검색으로 조사·정리
  → JSON 형식 검증 (깨지면 Haiku가 복구)
  → 이전에 보낸 항목 제외
  → 인용 문구를 원문 페이지와 자동 대조
  → Slack 전송 + HTML 리포트를 GitHub Pages 보관함에 저장
```

**인용 문구 검증**: 각 항목에는 원문에서 그대로 옮긴 짧은 문구가 붙습니다. 실행할 때마다 원문 페이지를 직접 열어 그 문구가 실제로 있는지 확인합니다.
- ✅ 원문에서 같은 문구를 확인함
- ⚠️ 미확인: 사이트가 자동 접속을 막아 확인 못 함 (링크에서 직접 확인)
- 원문에 없는 문구는 자동으로 빼고 보냅니다

## 명령어

| 명령 | 용도 | 비용 |
|---|---|---|
| `python -m agents.check` | 키, 크레딧, Slack 연결 점검 | 1원 미만 |
| `python -m agents.ai_news --sample` | API 없이 화면만 미리보기 (`preview/`) | 무료 |
| `python -m agents.ai_news --local` | 실제 1회 실행, `preview/`에만 저장 | $0.3~0.6 |
| `python -m agents.ai_news --local --slack` | 위와 같고 Slack으로도 전송 | $0.3~0.6 |
| `bash scripts/setup.sh` | GitHub 저장소·시크릿·Pages 설정 | 무료 |
| `gh workflow run ai-news.yml` | Actions에서 즉시 실행 | $0.3~0.6 |
| `python -m agents.linear_setup` | Linear 키·팀·라벨 점검과 준비 | 무료 |
| `python -m agents.night_queue --dry-run` | 야간 작업 대기열 확인 | 무료 |
| `python -m agents.night_queue --issue RES-12` | 이슈 하나 바로 처리 | 건당 $0.05~1.5 |
| `python -m tests.test_offline` | 네트워크 없이 Linear 흐름 검증 | 무료 |

`ai_news` 자리에 `robot_radar`를 넣으면 레이더도 같은 방식으로 실행됩니다.

## 바꾸고 싶을 때

| 바꿀 것 | 위치 |
|---|---|
| 연구 내용 ("내 연구 적용" 기준) | `agents/config.py`의 `RESEARCH_CONTEXT` |
| 검색 횟수, 항목 수, 월 예산 경고선 | `agents/config.py` |
| 다루는 주제, 말투 | `agents/ai_news.py`, `agents/robot_radar.py`의 `SYSTEM` |
| 실행 시각 | `.github/workflows/*.yml`의 `cron` (UTC 기준, KST = UTC+9) |

## 예상 비용 (Sonnet 5.5 기준)

AI 뉴스 월 $10~15, 레이더 월 $5~7, 합계 월 $15~22 수준입니다. 야간 작업은 맡긴 만큼 건당 $0.05~1.5가 더해집니다.
Slack 하단과 리포트 하단에 매회 비용과 이번 달 누적이 표시되고, `MONTHLY_BUDGET`(기본 $40)의 80%를 넘으면 경고가 붙습니다.
실제 비용은 `data/costs.json`에 쌓입니다.

## 폴더 구성

```
agents/
  config.py        자주 바꾸는 설정
  common.py        공통 흐름 (검색, 검증, HTML, Slack, 비용 기록)
  ai_news.py       AI 뉴스 프롬프트
  robot_radar.py   로봇+AI 레이더 프롬프트
  check.py         연결 점검
  linear.py        Linear API (이슈, 라벨, 댓글, 첨부 다운로드)
  linear_setup.py  Linear 준비·시험 이슈
  night_queue.py   야간 작업 큐
scripts/setup.sh   GitHub 설정 자동화
.github/workflows/ 예약 실행 정의
docs/              GitHub Pages 보관함 (자동 생성)
data/              보낸 항목 기록, 비용 기록 (자동 생성)
tests/sample.json  미리보기용 샘플
tests/test_offline.py  Linear 연동 오프라인 테스트
```

## 알아둘 점

- X(트위터) 글은 검색에 잘 잡히지 않아, 인물 발언은 기사·블로그로 보도된 것 위주로 들어옵니다.
- 저장소는 GitHub Pages 무료 사용을 위해 공개로 만듭니다. 키는 시크릿에만 저장되어 공개되지 않고, 리포트는 공개 뉴스 요약뿐입니다.
- 실행이 실패하면 Slack에 ⚠️ 메시지가 옵니다. 크레딧이 떨어진 경우도 같습니다.
