"""Linear 연결 점검과 준비.

실행: python -m agents.linear_setup               (키 확인, 팀 목록, 라벨 생성, 상태 확인)
      python -m agents.linear_setup --test-issue  (야간 작업 시험용 이슈 1개 생성)
"""
import argparse
import os
import sys

from agents import config, linear

TEST_DESC = """야간 작업 연결 시험입니다.

아래 문단을 학회 발표용으로 다듬고, 영문 초록(80단어 이내)도 함께 작성해줘.

> 본 연구에서는 시뮬레이션 환경에서 로봇 매니퓰레이터의 물체 조작 과제를 학습시키고, 사람이 원격으로 조작한 시연 데이터를 함께 사용하여 학습 효율을 비교하였다. 학습된 정책은 동일한 과제 집합에서 성공률과 소요 시간으로 평가하였다.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-issue", action="store_true", help="시험용 이슈를 만들고 야간작업 라벨을 붙인다")
    args = ap.parse_args()

    key = os.getenv("LINEAR_API_KEY", "")
    print("1) API 키")
    if not key.startswith("lin_api_"):
        sys.exit("   ✗ LINEAR_API_KEY가 없거나 형식이 다릅니다 (lin_api_ 로 시작). .env를 확인하세요")
    try:
        v = linear.viewer()
    except Exception as e:
        sys.exit(f"   ✗ 연결 실패: {e}")
    print(f"   ✓ {v['viewer']['name']} 님, 워크스페이스 '{v['organization']['name']}'")

    print("2) 팀")
    ts = linear.teams()
    for t in ts:
        print(f"   - {t['key']:<8} {t['name']}")
    if not config.LINEAR_TEAM_KEY:
        sys.exit("\n   위 목록에서 쓸 팀의 키를 골라 .env의 LINEAR_TEAM_KEY= 에 넣고 다시 실행하세요")
    team = linear.team()
    print(f"   ✓ 사용할 팀: {team['key']} ({team['name']})")

    print("3) 라벨")
    for name in (config.NIGHT_LABEL, config.NIGHT_DONE_LABEL, config.RADAR_LABEL):
        lid, created = linear.ensure_label(name, team["id"])
        print(f"   ✓ '{name}' " + ("새로 만듦" if created else "이미 있음"))

    print("4) 처리 후 옮길 상태")
    states = ", ".join(f"{s['name']}" for s in team["states"]["nodes"])
    print(f"   팀 상태 목록: {states}")
    if linear.state_id(team, config.LINEAR_REVIEW_STATE):
        print(f"   ✓ 처리가 끝나면 '{config.LINEAR_REVIEW_STATE}'로 옮깁니다")
    else:
        print(f"   - '{config.LINEAR_REVIEW_STATE}' 상태가 없어 상태는 그대로 두고 라벨만 바꿉니다."
              f" 원하면 .env에 LINEAR_REVIEW_STATE=위 목록 중 하나 를 넣으세요")

    if args.test_issue:
        print("5) 시험용 이슈 만들기")
        night_id, _ = linear.ensure_label(config.NIGHT_LABEL, team["id"])
        issue = linear.create_issue(team["id"], "[시험] 야간 작업 연결 확인", TEST_DESC, [night_id])
        print(f"   ✓ {issue['identifier']} 생성: {issue['url']}")
        print(f"   다음: python -m agents.night_queue --issue {issue['identifier']}")

    print("\n결과: Linear 준비 완료")


if __name__ == "__main__":
    main()
