"""연결 점검: API 키, 크레딧, Slack 웹훅이 제대로 되는지 확인 (비용 1원 미만).

실행: python -m agents.check
"""
import os
import sys

import requests

from agents import config


def mask(v):
    return f"{v[:10]}...{v[-4:]}" if len(v) > 16 else "(짧음)"


def main():
    ok = True
    key = os.getenv("ANTHROPIC_API_KEY", "")
    hooks = {k: os.getenv(k, "") for k in ("SLACK_WEBHOOK_URL", "SLACK_WEBHOOK_URL_RADAR")}

    print("1) 값 형식 확인")
    if not key.startswith("sk-ant-"):
        print("   ✗ ANTHROPIC_API_KEY가 없거나 형식이 다릅니다 (sk-ant- 로 시작해야 함)")
        ok = False
    else:
        print(f"   ✓ ANTHROPIC_API_KEY {mask(key)}")
    for name, v in hooks.items():
        if not v:
            print(f"   - {name} 비어 있음" + (" (선택 항목, 비우면 기본 채널 사용)" if name.endswith("RADAR") else ""))
            ok = ok and name.endswith("RADAR")
        elif not v.startswith("https://hooks.slack.com/"):
            print(f"   ✗ {name} 형식이 다릅니다 (https://hooks.slack.com/ 로 시작해야 함)")
            ok = False
        else:
            print(f"   ✓ {name} {mask(v)}")

    print("2) Claude API 호출")
    if key.startswith("sk-ant-"):
        import anthropic
        try:
            r = anthropic.Anthropic().messages.create(
                model=config.HELPER_MODEL, max_tokens=10,
                messages=[{"role": "user", "content": "ping이라고만 답해"}])
            print(f"   ✓ 응답 받음 ({config.HELPER_MODEL}): {r.content[0].text.strip()[:20]}")
        except anthropic.AuthenticationError:
            print("   ✗ 키가 유효하지 않습니다. Console에서 새로 발급해 .env에 넣으세요")
            ok = False
        except anthropic.APIStatusError as e:
            msg = str(e)
            if "credit" in msg.lower():
                print("   ✗ 크레딧이 없습니다. claude.ai 설정 > 결제 > API credits에서 이 조직이 연결됐는지 확인하세요")
            else:
                print(f"   ✗ API 오류: {msg[:200]}")
            ok = False
        except Exception as e:
            print(f"   ✗ 연결 실패 (네트워크 확인): {str(e)[:200]}")
            ok = False

    print("3) Slack 테스트 메시지")
    sent = set()
    for name, v in hooks.items():
        if not v.startswith("https://hooks.slack.com/") or v in sent:
            continue
        what = "로봇+AI 레이더" if name.endswith("RADAR") else ("AI 뉴스와 로봇+AI 레이더"
                                                               if not hooks["SLACK_WEBHOOK_URL_RADAR"] else "AI 뉴스")
        try:
            r = requests.post(v, json={"text": f"✅ 연결 테스트: 이 채널로 {what}가 옵니다."}, timeout=20)
        except requests.RequestException as e:
            print(f"   ✗ {name} 연결 실패 (네트워크 또는 URL 확인): {str(e)[:150]}")
            ok = False
            continue
        if r.status_code == 200:
            print(f"   ✓ {name} 전송 성공. Slack 채널을 확인하세요")
            sent.add(v)
        else:
            print(f"   ✗ {name} 전송 실패 ({r.status_code} {r.text})")
            ok = False

    print("\n결과:", "모두 정상입니다" if ok else "위 ✗ 항목을 고친 뒤 다시 실행하세요")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
