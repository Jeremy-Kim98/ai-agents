"""인스타 카드 검사(영어 계정): 공개 거름망, 하루 3개 상한, 편집본 코드 검사. 실행: python -m tests.test_insta"""
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
    assert "Nov 18" in cards[0], "표지 날짜가 영어 형식이 아님"

    src = {"title": "Astra 출시", "summary": "API 가격은 입력 $8, 출력 $40이다.", "why": ""}
    good = {"card_line": "OpenAI ships Astra at $8 in / $40 out",
            "card_take": "Pricing will decide this one for most labs on a budget.", "cover_q": "Worth switching?"}
    assert insta.code_check(src, good) == [], f"정상 편집본이 걸림: {insta.code_check(src, good)}"
    bad_num = {**good, "card_line": "OpenAI ships Astra at $8 in / $45 out"}
    assert any("45" in p for p in insta.code_check(src, bad_num)), "원문에 없는 수치 45를 못 잡음"
    unit_src = {"title": "", "summary": "100만 토큰당 입력 $8, 직원 1.5억 명, 투자 2조 원", "why": ""}
    unit_ok = {**good, "card_line": "$8 per 1M tokens", "card_take": "150M staff, 2T won raised."}
    assert insta.code_check(unit_src, unit_ok) == [], f"단위 환산(1M·150M·2T)이 걸림: {insta.code_check(unit_src, unit_ok)}"
    ipo_src = {"title": "", "summary": "8억 2,500만 주를 주당 70~78달러에 공모, 1,500만 명 사용", "why": ""}
    ipo_ok = {**good, "card_line": "825M shares at $70-78 each", "card_take": "15M users already."}
    assert insta.code_check(ipo_src, ipo_ok) == [], f"복합 단위(825M·15M)가 걸림: {insta.code_check(ipo_src, ipo_ok)}"
    unit_bad = {**good, "card_line": "$8 per 3M tokens"}
    assert any("3" in p for p in insta.code_check(unit_src, unit_bad)), "원문에 없는 수치 3M을 못 잡음"
    too_long = {**good, "card_take": "a" * 111}
    assert any("card_take" in p for p in insta.code_check(src, too_long)), "글자 수 초과를 못 잡음"
    long_q = {**good, "cover_q": "q" * 51}
    assert any("cover_q" in p for p in insta.code_check(src, long_q)), "표지 질문 길이 초과를 못 잡음"
    for fake in ["I tried it and it felt fast.", "I've been using it all week.", "In my testing it was solid.",
                 "직접 써봤는데 꽤 빨라요."]:
        assert any("경험" in p for p in insta.code_check(src, {**good, "card_take": fake})), f"지어낸 경험 못 잡음: {fake}"

    # 금지 표현: 각 분류가 잡히고, 비슷하지만 정상인 문장은 통과해야 한다
    for name, take in [("과장어", "A total game-changer for labs."), ("과장어", "This is insane."),
                       ("이모지", "Prices just dropped 🔥"), ("투자 권유", "Time to buy before the IPO."),
                       ("투자 권유", "The stock will pop on day one."), ("농업 주제", "Great news for smart farming."),
                       ("과장어", "판도를 바꿀 소식이에요."), ("AI 티", "Cheaper tokens — finally."),
                       ("AI 티", "Here's why this matters for labs."), ("AI 티", "It's not a model, it's a platform."),
                       ("AI 티", "Not just a chip deal, but a bet on world models."),
                       ("AI 티", "Time to delve into the docs."), ("AI 티", "The AI landscape keeps shifting.")]:
        assert any(name in p for p in insta.code_check(src, {**good, "card_take": take})), f"{name} 못 잡음: {take}"
    for take in ["Server farms just got pricier to rent.", "Chips now need a license to sell abroad.",
                 "Company claims it, not independently verified yet.", "Cropping images got easier in the API.",
                 "Here's the catch: the price only applies to Astra.", "It's not cheap, but it's fast enough for evals.",
                 "World models just got a GPU-sized backer."]:
        assert insta.code_check(src, {**good, "card_take": take}) == [], f"정상 문장이 걸림: {take}"
    long_rq = {**good, "reader_q": "q" * 91}
    assert any("reader_q" in p for p in insta.code_check(src, long_rq)), "독자 질문 길이 초과를 못 잡음"
    assert any("AI 티" in p for p in insta.code_check(src, {**good, "reader_q": "Here's why it matters — thoughts?"})), \
        "독자 질문의 AI 티를 못 잡음"

    # 출처 페이지: 운영 정보·본인 이름이 새지 않고, 링크는 http(s)만
    from agents import sources_site
    rec = insta.post_record(DAY, {"cover_q": "Q?"}, [
        {"card_line": "Line A", "source": "TechCrunch", "category": "빅테크", "url": "https://x.test/a",
         "importance": 3, "quote_status": "ok", "summary": "요약", "card_take": "t"},
        {"card_line": "Bad link", "source": "S", "category": "모델", "url": "javascript:alert(1)"}])
    assert set(rec["items"][0]) == {"card_line", "card_take", "category", "source", "date", "url"}, "기록에 운영 정보가 섞임"
    page = sources_site.build([rec])
    assert "Line A" in page and "Big Tech" in page, "출처 페이지에 항목이 없음"
    assert "javascript:" not in page, "http(s)가 아닌 링크가 출처 페이지에 들어감"
    for leak in ("jeremy", "Jeremy", "Claude", "$", "비용", "요약"):
        assert leak not in page, f"출처 페이지에 '{leak}'가 드러남"
    print("✓ test_insta 통과")


if __name__ == "__main__":
    run()
