"""인스타 카드 검사: 공개 거름망, 하루 3개 상한, 편집본 코드 검사. 실행: python -m tests.test_insta"""
import datetime as dt

from agents import insta

ITEMS = [
    {"title": "확인된 뉴스 A", "quote_status": "ok", "importance": 2},
    {"title": "미확인 뉴스 B", "quote_status": "unknown", "importance": 3},
    {"title": "확인된 뉴스 C", "quote_status": "ok", "importance": 3},
]
DAY, DATA = dt.date(2026, 11, 18), {"headline": "헤드라인"}


def run():
    pub = insta.public_items(ITEMS)
    assert [i["title"] for i in pub] == ["확인된 뉴스 C", "확인된 뉴스 A"], f"거름망·중요도 정렬 틀림: {pub}"
    cards = insta.build_cards(DAY, DATA, pub)
    cap = insta.caption(DAY, DATA, pub)
    assert len(cards) == 3, f"표지 1 + 확인된 2 = 3장이어야 함, 실제 {len(cards)}"
    assert not any("미확인 뉴스 B" in c for c in cards + [cap]), "미확인 항목이 카드·캡션에 들어감"
    five = [{"title": f"뉴스{k}", "quote_status": "ok", "importance": 2} for k in range(5)]
    assert len(insta.build_cards(DAY, DATA, five)) == 4, "하루 3개 상한(표지 포함 4장)을 넘김"

    src = {"title": "Astra 출시", "summary": "API 가격은 입력 $8, 출력 $40이다.", "why": ""}
    good = {"card_line": "Astra 출시, 입력 $8·출력 $40", "card_take": "가격부터 보고 고르면 될 것 같아요."}
    assert insta.code_check(src, good) == [], f"정상 편집본이 걸림: {insta.code_check(src, good)}"
    bad_num = {**good, "card_line": "Astra 출시, 입력 $8·출력 $45"}
    assert any("45" in p for p in insta.code_check(src, bad_num)), "원문에 없는 수치 45를 못 잡음"
    too_long = {**good, "card_take": "가" * 51}
    assert any("card_take" in p for p in insta.code_check(src, too_long)), "글자 수 초과를 못 잡음"
    fake = {**good, "card_take": "직접 써봤는데 꽤 빨라요."}
    assert any("경험" in p for p in insta.code_check(src, fake)), "지어낸 사용 경험을 못 잡음"

    # 금지 표현: 각 분류가 잡히고, 비슷하지만 정상인 문장은 통과해야 한다
    for name, take in [("과장어", "판도를 바꿀 소식이에요."), ("이모지", "가격이 내려갔어요 🔥"),
                       ("투자 권유", "상장 전에 사도 될 것 같아요."), ("투자 권유", "주가가 더 오를 거예요."),
                       ("농업 주제", "스마트팜에도 쓸 수 있어요."), ("과장어", "업계 판도를 바꿀 혁신이에요.")]:
        assert any(name in p for p in insta.code_check(src, {**good, "card_take": take})), f"{name} 못 잡음: {take}"
    for take in ["기능을 한 모델에 담아냈어요.", "회사 측 주장이라 검증을 기다려요.", "수출통제가 연구실 조달에 영향을 줘요."]:
        assert insta.code_check(src, {**good, "card_take": take}) == [], f"정상 문장이 걸림: {take}"
    print("✓ test_insta 통과")


if __name__ == "__main__":
    run()
