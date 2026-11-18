"""AI 뉴스 결과 → 인스타그램 캐러셀 카드(PNG, 1080x1350) + 캡션.

형식: 표지(질문형 훅 + 오늘 3줄) + 뉴스 카드(한 줄 사실 + 대학원생 한마디) 최대 3장.
단계: (1 수집 = ai_news) → 2 편집(Claude, 도구 없음) → 3 검증(코드 검사 + 별도 Claude가 원문과 대조)
      → 4 렌더(PNG) → 5 배포(아직 없음). 단계끼리는 대화하지 않고 JSON 파일만 넘긴다.

미리보기(무료, 편집 없이):  python -m agents.insta --from-report docs/ai-news/2026-11-18.html
편집·검증까지(유료):        python -m agents.insta --from-report ... --edit
결과는 preview/insta/ 에 생긴다.
"""
import argparse
import datetime as dt
import html as _html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from agents import config
from agents.common import E, WEEKDAYS, Meter, _client, extract_json

W, H = 1080, 1350
DAILY_MAX = 3      # 하루에 싣는 뉴스 수
EDIT_POOL = 9      # 편집에 넘기는 후보 수 (검증에서 빠질 것을 감안)
LIMITS = {"card_line": 36, "card_take": 50}
NUM = re.compile(r"\d+(?:\.\d+)?")

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden}
body{background:#F6F4EF;color:#16161A;font-family:'Apple SD Gothic Neo','Noto Sans CJK KR','Noto Sans KR',sans-serif;
  padding:88px 84px;display:flex;flex-direction:column;letter-spacing:-0.01em}
.top{display:flex;justify-content:space-between;font-size:30px;color:#6B6A66;font-weight:600}
.brand b{color:#16161A}
.mid{margin:auto 0;display:flex;flex-direction:column}
.chip{display:inline-block;padding:10px 22px;border-radius:999px;background:#16161A;color:#F6F4EF;
  font-size:28px;font-weight:700;align-self:flex-start}
.hot{background:#D9480F}
.line{font-size:76px;line-height:1.25;font-weight:800;margin-top:40px;word-break:keep-all}
.take{margin-top:72px;padding-top:40px;border-top:3px solid #16161A;font-size:40px;line-height:1.5;
  color:#2B2B30;word-break:keep-all}
.take b{display:block;font-size:28px;color:#D9480F;margin-bottom:14px}
.foot{display:flex;justify-content:space-between;font-size:27px;color:#6B6A66}
.ok{color:#2F7D4F;font-weight:700}
.q{font-size:92px;line-height:1.2;font-weight:800;word-break:keep-all}
.cover ol{margin-top:80px;list-style:none;counter-reset:n}
.cover li{counter-increment:n;font-size:36px;line-height:1.4;padding:22px 0;border-top:2px solid #DDD8CC;
  word-break:keep-all;display:flex;gap:22px}
.cover li::before{content:counter(n);font-weight:800;color:#D9480F;min-width:36px}
"""


def _page(body, cls=""):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head>'
            f'<body class="{cls}">{body}</body></html>')


def public_items(items):
    """공개 계정에는 원문 문구를 자동 확인한 항목만, 중요도 순으로."""
    ok = [i for i in items if i.get("quote_status") == "ok"]
    return sorted(ok, key=lambda i: -i.get("importance", 0))[:EDIT_POOL]


# ============================================================ 2. 편집
EDIT_SYSTEM = """너는 인스타그램 AI 뉴스 계정의 편집자다. 계정의 화자는 'AI와 기술 트렌드에 관심이 아주 많은 대학원생'이다.
입력은 이미 검증된 뉴스 항목이고, 너는 카드 문구만 쓴다. 카드 한 장 = 굵은 한 줄 + 대학원생 한마디.

card_line (36자 이하): 무슨 일인지 사실만 한 줄. 핵심 수치가 있으면 넣는다. 평서·명사형 종결("~출시", "~확대").
card_take (50자 이하): 대학원생 화자의 한마디. 해요체. "그래서 나/우리 같은 사람에게 뭐가 달라지나"를 말한다.
cover_q (22자 이하): 항목마다 하나씩, 그 소식을 표지에 걸 때 쓸 질문형 훅. 예: "GPT-6.2, 갈아탈 만할까?"

규칙:
- 입력에 있는 사실만 쓴다. 새 사실, 새 수치를 더하지 않는다. 수치는 입력 그대로.
- 회사 측 주장·미검증이라는 단서가 입력에 있으면 card_line이나 card_take에 남긴다("회사 측 주장").
- card_take는 의견·의미만 말한다. "직접 써봤는데", "제가 해보니" 같은 경험담은 절대 쓰지 않는다(실제로 써보지 않았다).
- 과장·감탄사·이모지 금지. "혁신", "충격", "미쳤다" 금지.
- 해시태그: 공통 3개 + 항목마다 그 항목에만 해당하는 1~2개. # 포함, 띄어쓰기 없이.
```json 블록 하나만 출력한다:
{"common_tags": ["#..."],
 "items": [{"idx": 0, "card_line": "...", "card_take": "...", "cover_q": "...", "tags": ["#..."]}]}"""


def edit_items(data, items, meter):
    src = [{"idx": k, "title": i["title"], "summary": i.get("summary", ""), "why": i.get("why", ""),
            "source": i.get("source", "")} for k, i in enumerate(items)]
    resp = _client().messages.create(
        model=config.MODEL, max_tokens=16000, system=EDIT_SYSTEM,  # thinking이 출력 한도를 같이 쓴다
        messages=[{"role": "user", "content": json.dumps(
            {"headline": data.get("headline", ""), "items": src}, ensure_ascii=False)}])
    meter.add(config.MODEL, resp.usage)
    return extract_json("".join(b.text for b in resp.content if b.type == "text"))


# ============================================================ 3. 검증
EXPERIENCE = re.compile(r"써\s?봤|써\s?보니|해\s?봤|해\s?보니|사용해\s?보|돌려\s?봤|돌려\s?보니")


def code_check(item, ed):
    """편집본의 기계 검사. 문제 목록을 돌려준다(빈 목록 = 통과)."""
    probs = [f"{k} {len(ed.get(k, ''))}자 > {n}자" for k, n in LIMITS.items() if len(ed.get(k, "")) > n]
    probs += [f"{k} 비어 있음" for k in LIMITS if not ed.get(k, "").strip()]
    source = " ".join(item.get(k, "") for k in ("title", "summary", "why"))
    edited = " ".join(ed.get(k, "") for k in LIMITS)
    probs += [f"원문 요약에 없는 수치 {n}" for n in sorted(set(NUM.findall(edited)) - set(NUM.findall(source)))]
    if EXPERIENCE.search(ed.get("card_take", "")):
        probs.append("지어낸 사용 경험 표현")
    return probs


def page_text(url):
    """shortcut: common._verify_one과 같은 방식의 본문 추출을 복제. 공용 코드 정리 때 합친다."""
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (compatible; digest-bot/1.0)"})
        if r.status_code >= 400:
            return ""
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", r.text)
        return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", body)))
    except Exception:
        return ""


VERIFY_SYSTEM = """너는 사실 검증자다. 원문 기사 본문과 카드 문구를 받는다. 카드 문구를 쓴 사람의 의도는 모른다.
- card_line: 모든 사실·수치가 원문 본문에 근거가 있어야 한다. 원문보다 강한 단정(주장→사실, 계획→완료)은 문제다.
  한 줄 카드라서 생략·축약(직함 일부 생략, 고유명사 한글 표기 등)은 뜻이 바뀌지 않으면 문제가 아니다.
- card_take: 의견이라 원문에 그대로 없어도 되지만, 원문 사실과 모순되거나 원문에 없는 사실을 전제하면 문제다.
  직접 사용해 본 것처럼 쓴 경험담도 문제다.
```json 블록 하나만: {"ok": true|false, "problems": ["..."]}"""


def llm_check(item, ed, meter):
    page = page_text(item.get("url", ""))
    if len(page) < 500:
        return False, ["원문 본문을 가져오지 못함"]
    card = {k: ed.get(k, "") for k in LIMITS}
    resp = _client().messages.create(
        model=config.MODEL, max_tokens=8000, system=VERIFY_SYSTEM,
        messages=[{"role": "user", "content": f"원문 본문:\n{page[:24000]}\n\n카드 문구:\n"
                                              + json.dumps(card, ensure_ascii=False)}])
    meter.add(config.MODEL, resp.usage)
    v = extract_json("".join(b.text for b in resp.content if b.type == "text"))
    return bool(v.get("ok")), list(v.get("problems", []))


def edit_and_verify(data, items, meter, out_dir):
    """2·3단계. 중요도 순으로 검증해 DAILY_MAX개가 통과하면 멈춘다. 단계별 결과를 파일로 남긴다."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    items = public_items(items)
    edited = edit_items(data, items, meter)
    (out / "2_edit.json").write_text(json.dumps(edited, ensure_ascii=False, indent=2), encoding="utf-8")
    by_idx = {e.get("idx"): e for e in edited.get("items", []) if isinstance(e, dict)}
    passed, report, tags = [], [], list(edited.get("common_tags", []))
    for k, it in enumerate(items):
        if len(passed) >= DAILY_MAX:
            break
        ed = by_idx.get(k, {})
        probs = code_check(it, ed)
        ok = not probs
        if ok:  # 코드 검사를 통과한 것만 Claude 검증에 보낸다
            ok, probs = llm_check(it, ed, meter)
        report.append({"idx": k, "title": it["title"], "ok": ok, "problems": probs})
        if ok:  # 걸러진 항목의 해시태그는 싣지 않는다
            passed.append({**it, **{f: ed[f] for f in LIMITS}, "cover_q": str(ed.get("cover_q", ""))[:30]})
            tags += ed.get("tags", [])
    (out / "3_verify.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tags = [h for h in dict.fromkeys(tags) if isinstance(h, str) and re.fullmatch(r"#\S{1,30}", h)]
    # 표지 질문은 통과한 1순위 항목의 것을 쓴다(빠진 항목의 질문이 표지에 남지 않게)
    cover_q = passed[0]["cover_q"] if passed else ""
    return {**data, "cover_q": cover_q, "hashtags": tags[:10]}, passed, report


# ============================================================ 4. 렌더
def build_cards(today, data, items):
    items = items[:DAILY_MAX]
    day = f"{today.month}.{today.day} ({WEEKDAYS[today.weekday()]})"
    n = len(items)
    line = lambda i: i.get("card_line") or i["title"]
    lis = "".join(f"<li>{E(line(i))}</li>" for i in items)
    q = data.get("cover_q") or f"오늘의 AI 뉴스 {n}"
    cards = [_page(f'<div class="top"><span class="brand"><b>AI 뉴스</b> 대학원생 노트</span><span>{day}</span></div>'
                   f'<div class="mid"><p class="q">{E(q)}</p><ol>{lis}</ol></div>'
                   f'<div class="foot"><span>넘겨서 보기 →</span><span>매일 아침</span></div>', "cover")]
    for k, it in enumerate(items, 1):
        chip = "hot" if it.get("importance", 0) >= 3 else ""
        take = (f'<p class="take"><b>대학원생 한마디</b>{E(it["card_take"])}</p>' if it.get("card_take") else "")
        cards.append(_page(
            f'<div class="top"><span class="brand"><b>AI 뉴스</b> {day}</span><span>{k} / {n}</span></div>'
            f'<div class="mid"><span class="chip {chip}">{E(it.get("category", ""))}</span>'
            f'<p class="line">{E(line(it))}</p>{take}</div>'
            f'<div class="foot"><span>출처 {E(it.get("source", ""))} · {E(it.get("date", ""))}</span>'
            f'<span class="ok">✓ 원문 대조</span></div>'))
    return cards


def caption(today, data, items):
    items = items[:DAILY_MAX]
    lines = [f"🗞️ {today.month}월 {today.day}일 ({WEEKDAYS[today.weekday()]}) AI 뉴스", "",
             data.get("cover_q") or data.get("headline", ""), ""]
    lines += [f"{k}. {i.get('card_line') or i['title']} ({i.get('source', '')})" for k, i in enumerate(items, 1)]
    tags = data.get("hashtags") or ["#AI뉴스", "#인공지능", "#AI트렌드"]
    lines += ["", "AI 요약은 매일 원문과 다시 대조합니다. 원문 링크는 프로필의 전체 리포트에서.", "",
              " ".join(tags)]
    return "\n".join(lines)


def _chrome():
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              shutil.which("google-chrome"), shutil.which("chromium")):
        if p and Path(p).exists():
            return p
    sys.exit("크롬을 찾지 못했습니다")


def render_png(cards, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    chrome, paths = _chrome(), []
    for k, page in enumerate(cards):
        src, png = out / f"card_{k:02d}.html", out / f"card_{k:02d}.png"
        src.write_text(page, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--hide-scrollbars", f"--window-size={W},{H}",
                        f"--screenshot={png.resolve()}", src.resolve().as_uri()],
                       check=True, capture_output=True, timeout=60)
        paths.append(png)
    return paths


def items_from_report(path):
    """보관된 HTML 리포트에서 항목을 되살린다.
    shortcut: render_report 마크업에 묶인 정규식 파싱, 미리보기 전용. 실제 운영은 run_agent의 items를 직접 넘긴다."""
    text = Path(path).read_text(encoding="utf-8")
    un = lambda s: _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
    head = re.search(r'<p class="verdict">(.*?)</p>', text, re.S)
    items = []
    for art in re.findall(r"<article( class=\"hot\")?>(.*?)</article>", text, re.S):
        hot, body = art
        g = lambda pat: (m.group(1) if (m := re.search(pat, body, re.S)) else "")
        cat, src, date = (un(g(r'<p class="src">(.*?)</p>')).split(" / ") + ["", "", ""])[:3]
        items.append({"title": un(g(r"<h2>(.*?)</h2>")), "url": _html.unescape(g(r'<h2><a href="([^"]+)"')),
                      "category": cat, "source": src, "date": date,
                      "summary": un(g(r"<p>(.*?)</p>")), "why": un(g(r'<p class="why">(.*?)</p>')),
                      "importance": 3 if hot else 2,
                      "quote_status": "ok" if '<small class="ok">' in body else "unknown"})
    m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    return dt.date.fromisoformat(m.group(1)), {"headline": un(head.group(1)) if head else ""}, items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-report", required=True)
    ap.add_argument("--out", default="preview/insta")
    ap.add_argument("--edit", action="store_true", help="2 편집·3 검증 실행 (API 사용)")
    a = ap.parse_args()
    today, data, items = items_from_report(a.from_report)
    n_all = len(items)
    if a.edit:
        meter = Meter()
        data, items, report = edit_and_verify(data, items, meter, a.out)
        for r in report:
            print(("✓ " if r["ok"] else "✗ ") + r["title"] + ("" if r["ok"] else f"  ← {r['problems']}"))
        print(f"편집·검증 비용 약 ${meter.cost:.3f}")
    else:
        items = public_items(items)
    for old in Path(a.out).glob("card_*"):
        old.unlink()
    if not items:
        sys.exit("공개할 항목이 없어 오늘은 게시하지 않습니다")
    pngs = render_png(build_cards(today, data, items), a.out)
    (Path(a.out) / "caption.txt").write_text(caption(today, data, items), encoding="utf-8")
    print(f"항목 {n_all}개 → 게시 {min(len(items), DAILY_MAX)}개, 카드 {len(pngs)}장: {a.out}")
