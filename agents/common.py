"""공통 실행 흐름.

검색·정리(Claude) → JSON 검증/복구 → 중복 제거 → 인용 문구 원문 대조
→ HTML 리포트 저장 → Slack 전송 → 기록·비용 저장
"""
import argparse
import concurrent.futures
import datetime
import html
import json
import os
import pathlib
import re
import sys
import traceback
from string import Template

import requests

from agents import config

KST = datetime.timezone(datetime.timedelta(hours=9))
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEEKDAYS = "월화수목금토일"
FIELDS = ("title", "summary", "why", "apply", "category", "source", "date", "url", "quote")
CATEGORY_EMOJI = {
    "모델": "🧠", "인물": "🗣️", "빅테크": "🚀", "보안": "🔓", "오픈소스": "📦", "국내": "🇰🇷",
    "로봇모델": "🤖", "검출": "🎯", "엣지AI": "🔌", "시뮬레이션": "🕹️",
}


def now_kst():
    return datetime.datetime.now(KST)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


# ============================================================ Claude 호출
class Meter:
    """실행 중 쓴 토큰·검색을 달러로 누적."""

    def __init__(self):
        self.cost = 0.0
        self.searches = 0

    def add(self, model, usage):
        pin, pout = config.PRICES.get(model, (2.0, 10.0))
        inp = (usage.input_tokens or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        stu = getattr(usage, "server_tool_use", None)
        s = (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
        self.searches += s
        self.cost += inp / 1e6 * pin + (usage.output_tokens or 0) / 1e6 * pout + s * config.SEARCH_PRICE


def _client():
    import anthropic
    return anthropic.Anthropic()


def research(system, prompt, max_searches, meter):
    """웹 검색을 켜고 Claude에게 조사시킨 뒤 최종 텍스트를 돌려준다."""
    import anthropic
    client = _client()
    last_err = None
    for ver in config.SEARCH_TOOL_VERSIONS:
        try:
            return _research_once(client, system, prompt, ver, max_searches, meter)
        except anthropic.BadRequestError as e:
            last_err = e
            log(f"[warn] 검색 도구 {ver} 사용 불가 → 다음 버전으로 재시도 ({e})")
    raise last_err


def _research_once(client, system, prompt, ver, max_searches, meter):
    tools = [{"type": ver, "name": "web_search", "max_uses": max_searches}]
    messages = [{"role": "user", "content": prompt}]
    texts = []
    for _ in range(6):  # 검색이 길어져 pause_turn이 오면 이어서 진행
        resp = client.messages.create(model=config.MODEL, max_tokens=16000,
                                      system=system, tools=tools, messages=messages)
        meter.add(config.MODEL, resp.usage)
        texts.append("".join(b.text for b in resp.content if b.type == "text"))
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant",
                         "content": [b.model_dump(exclude_none=True) for b in resp.content]})
    return "\n".join(texts)


def extract_json(text):
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    cand = blocks[-1] if blocks else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(cand)


def parse_or_repair(text, meter):
    """JSON이 깨졌으면 Haiku로 형식만 고친다 (몇 원 수준)."""
    try:
        return extract_json(text)
    except Exception:
        log("[warn] JSON 파싱 실패 → Haiku로 형식 복구")
    resp = _client().messages.create(
        model=config.HELPER_MODEL, max_tokens=8000,
        system="입력 텍스트에 담긴 뉴스 정리 내용을 지정된 JSON 형식으로만 출력한다. "
               "내용을 새로 지어내지 말고, 설명 없이 ```json 블록 하나만 출력한다.",
        messages=[{"role": "user", "content":
                   '형식: {"headline": str, "items": [{"title","summary","why","apply","category",'
                   '"importance"(1-3),"source","date","url","quote"}]}\n\n텍스트:\n' + text[-40000:]}],
    )
    meter.add(config.HELPER_MODEL, resp.usage)
    return extract_json("".join(b.text for b in resp.content if b.type == "text"))


# ============================================================ 정리·검증
def clean_items(raw, seen_urls, limit):
    out = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        item = {k: str(it.get(k, "") or "").strip() for k in FIELDS}
        if not item["title"] or not item["url"].startswith(("http://", "https://")):
            continue
        if item["url"] in seen_urls:
            continue
        try:
            item["importance"] = max(1, min(3, int(it.get("importance", 1))))
        except (TypeError, ValueError):
            item["importance"] = 1
        seen_urls.add(item["url"])
        out.append(item)
    out.sort(key=lambda i: -i["importance"])
    return out[:limit]


_QUOTE_MAP = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "\u00a0": " "})


def _norm(s):
    return re.sub(r"\s+", " ", s.translate(_QUOTE_MAP)).strip().lower()


def _verify_one(item):
    """quote가 원문 페이지에 실제로 있는지 확인. ok / unknown / removed."""
    q = item.get("quote", "")
    if not q:
        return "none"
    try:
        r = requests.get(item["url"], timeout=12,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; digest-bot/1.0)"})
        if r.status_code >= 400:
            return "unknown"
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", r.text)
        page = html.unescape(re.sub(r"<[^>]+>", " ", body))
    except Exception:
        return "unknown"
    if len(page) < 500:  # 자바스크립트로만 그리는 페이지 등
        return "unknown"
    return "ok" if _norm(q) in _norm(page) else "removed"


def verify_quotes(items):
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for item, status in zip(items, ex.map(_verify_one, items)):
            item["quote_status"] = status
            if status == "removed":  # 원문에 없는 문구는 보여주지 않는다
                item["quote"] = ""


# ============================================================ 기록·비용
def _load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def recent_titles(hist, key, n_runs=3):
    return [t for run in hist.get(key, [])[-n_runs:] for t in run["titles"]]


def record_run(hist, key, date_str, items, keep=20):
    runs = hist.setdefault(key, [])
    runs.append({"date": date_str, "titles": [i["title"] for i in items],
                 "urls": [i["url"] for i in items]})
    hist[key] = runs[-keep:]
    _save("history.json", hist)


def month_total(costs, month):
    return round(sum(costs.get(month, {}).values()), 2)


def record_cost(key, month, cost):
    costs = _load("costs.json", {})
    m = costs.setdefault(month, {})
    m[key] = round(m.get(key, 0) + cost, 4)
    _save("costs.json", costs)
    return month_total(costs, month)


# ============================================================ HTML
PAGE = Template("""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>$title</title>
<meta property="og:title" content="$title">
<meta property="og:description" content="$desc">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@700&family=IBM+Plex+Sans+KR:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {
  --paper:#F8FAFB; --ink:#1D2B3A; --pencil:#2F5D8C; --graphite:#5E6873;
  --rule:#DCE3E9; --marker:#FFE36E; --ok:#2E7D4F; --grid:rgba(47,93,140,.07); color-scheme:light;
}
@media (prefers-color-scheme: dark) {
  :root { --paper:#121A22; --ink:#E4EAF0; --pencil:#8DB6E2; --graphite:#9AA6B2;
          --rule:#2A3644; --marker:#6B5A12; --ok:#7CC79A; --grid:rgba(141,182,226,.06); color-scheme:dark; }
}
* { box-sizing:border-box; }
html {
  background-color:var(--paper);
  background-image:linear-gradient(var(--grid) 1px,transparent 1px),
                   linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:24px 24px; min-height:100%;
}
body {
  margin:0; color:var(--ink); background:transparent;
  font-family:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  font-size:16px; line-height:1.7; word-break:keep-all; overflow-wrap:anywhere;
  padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
}
main { max-width:42rem; margin:0 auto; padding:2.75rem 1.25rem 4rem; }
.kind { color:var(--pencil); font-weight:600; margin:0; }
h1 { font-family:"Gowun Batang",serif; font-size:2.4rem; line-height:1.2; margin:.15rem 0 0; }
.verdict { border-left:3px solid var(--pencil); padding:.1rem 0 .1rem 1rem; margin:1.6rem 0 2.4rem; font-size:1.05rem; }
h3.group { font-size:.95rem; color:var(--graphite); font-weight:600; margin:2.2rem 0 .2rem; }
article { padding:1.3rem 0; border-top:1px solid var(--rule); }
article h2 { font-size:1.12rem; line-height:1.5; margin:0 0 .35rem; }
article h2 a { color:inherit; text-decoration-color:var(--pencil); text-underline-offset:4px; }
article.hot h2 a { background:linear-gradient(transparent 58%,var(--marker) 58%); }
.src { font-size:.85rem; color:var(--graphite); margin:0 0 .5rem; }
p { margin:.35rem 0; }
.why { color:var(--graphite); }
.apply { margin-top:.75rem; padding:.6rem .85rem; border:1px dashed var(--pencil); border-radius:4px; }
.apply strong { color:var(--pencil); }
blockquote { margin:.7rem 0 0; padding:0 0 0 .9rem; border-left:2px solid var(--rule); font-size:.92rem; }
blockquote small { display:block; color:var(--graphite); font-size:.8rem; }
blockquote small.ok { color:var(--ok); }
.empty { color:var(--graphite); }
footer { margin-top:2.75rem; font-size:.85rem; color:var(--graphite); }
footer p { margin:.15rem 0; }
a { color:var(--pencil); }
a:focus-visible { outline:2px solid var(--pencil); outline-offset:2px; }
h2.series { font-family:"Gowun Batang",serif; font-size:1.5rem; margin:2.6rem 0 0; }
h3.month { font-size:.9rem; color:var(--graphite); font-weight:600; margin:1.2rem 0 .2rem; }
ul.archive { list-style:none; padding:0; margin:0; }
ul.archive li { padding:.5rem 0; border-top:1px solid var(--rule); }
</style>
</head>
<body><main>
$body
</main></body></html>
""")

E = html.escape
QUOTE_NOTE = {
    "ok": ('ok', "원문에서 같은 문구를 자동으로 확인했습니다"),
    "unknown": ('', "사이트 접근 제한으로 자동 확인을 못 했습니다. 링크에서 직접 확인하세요"),
}


def _article(it):
    cls = ' class="hot"' if it["importance"] >= 3 else ""
    meta = " / ".join(x for x in (it["category"], it["source"], it["date"]) if x)
    parts = [f"<article{cls}>",
             f'<h2><a href="{E(it["url"])}" target="_blank" rel="noopener">{E(it["title"])}</a></h2>',
             f'<p class="src">{E(meta)}</p>' if meta else "",
             f'<p>{E(it["summary"])}</p>' if it["summary"] else "",
             f'<p class="why">{E(it["why"])}</p>' if it["why"] else ""]
    if it.get("apply"):
        parts.append(f'<div class="apply"><strong>내 연구에 적용하면</strong><br>{E(it["apply"])}</div>')
    if it.get("quote"):
        cls_note, note = QUOTE_NOTE.get(it.get("quote_status"), ("", "자동 확인 전입니다"))
        parts.append(f'<blockquote>“{E(it["quote"])}”'
                     f'<small class="{cls_note}">{E(note)}</small></blockquote>')
    parts.append("</article>")
    return "\n".join(p for p in parts if p)


def render_report(label, today, data, items, cost, month_cost):
    hot = [i for i in items if i["importance"] >= 3]
    rest = [i for i in items if i["importance"] < 3]
    sections = []
    if hot and rest:
        sections += ['<h3 class="group">꼭 볼 것</h3>', *map(_article, hot),
                     '<h3 class="group">그 밖에</h3>', *map(_article, rest)]
    else:
        sections += list(map(_article, items))
    if not items:
        sections.append('<p class="empty">이번에는 새로 전할 만한 소식이 없었습니다.</p>')
    body = (f'<p class="kind">{E(label)}</p>'
            f'<h1>{today.month}월 {today.day}일 {WEEKDAYS[today.weekday()]}요일</h1>'
            f'<p class="verdict">{E(data.get("headline", ""))}</p>'
            + "\n".join(sections) +
            f'<footer><p>이번 실행 비용 약 ${cost:.2f}, 이번 달 누적 약 ${month_cost:.2f}</p>'
            f'<p><a href="../index.html">지난 리포트 모아보기</a></p></footer>')
    return PAGE.substitute(title=E(f"{label} {today:%Y-%m-%d}"),
                           desc=E(data.get("headline", "")), body=body)


def _day_label(stem):
    d = datetime.date.fromisoformat(stem)
    return f"{d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]})"


def write_index(out_dir):
    blocks = []
    for key, label in (("ai-news", "AI 뉴스"), ("robot-radar", "로봇+AI 레이더")):
        files = sorted((out_dir / key).glob("*.html"), reverse=True) if (out_dir / key).exists() else []
        by_month = {}
        for f in files[:120]:
            by_month.setdefault(f.stem[:7], []).append(f)
        inner = "".join(
            f'<h3 class="month">{m[:4]}년 {int(m[5:])}월</h3><ul class="archive">'
            + "".join(f'<li><a href="{key}/{f.name}">{_day_label(f.stem)}</a></li>' for f in fs)
            + "</ul>" for m, fs in by_month.items())
        blocks.append(f'<h2 class="series">{label}</h2>' + (inner or '<p class="empty">아직 리포트가 없습니다.</p>'))
    body = '<p class="kind">리포트 보관함</p><h1>지난 브리핑</h1>' + "".join(blocks)
    (out_dir / "index.html").write_text(
        PAGE.substitute(title="리포트 보관함", desc="AI 뉴스와 로봇+AI 레이더 보관함", body=body),
        encoding="utf-8")


# ============================================================ Slack
def _mrk(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slack_blocks(label, emoji, today, data, items, page_url, cost, month_cost, show_apply):
    title = f"{emoji} {label}  {today.month}월 {today.day}일 ({WEEKDAYS[today.weekday()]})"
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": title[:150]}}]
    if data.get("headline"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{_mrk(data['headline'])}*"}})
    blocks.append({"type": "divider"})
    if not items:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                                                   "text": "이번에는 새로 전할 만한 소식이 없었습니다."}})
    for n, it in enumerate(items, 1):
        fire = "  🔥" if it["importance"] >= 3 else ""
        lines = [f"*{n}. <{it['url']}|{_mrk(it['title'])}>*{fire}"]
        if it["summary"]:
            lines.append(_mrk(it["summary"]))
        if it["why"]:
            lines.append(f"_{_mrk(it['why'])}_")
        if show_apply and it.get("apply"):
            lines.append(f"🌱 *내 연구:* {_mrk(it['apply'])}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)[:2900]}})
        ctx = [x for x in (it["category"], it["source"], it["date"]) if x]
        elems = [{"type": "mrkdwn",
                  "text": f"{CATEGORY_EMOJI.get(it['category'], '•')} {_mrk('  |  '.join(ctx))}"}]
        if it.get("quote"):
            mark = "✅" if it.get("quote_status") == "ok" else "⚠️ 미확인"
            elems.append({"type": "mrkdwn", "text": f"{mark} “{_mrk(it['quote'])}”"[:2900]})
        if it.get("linear_url"):
            elems.append({"type": "mrkdwn", "text": f"📌 <{it['linear_url']}|Linear {it['linear_id']}>"})
        blocks.append({"type": "context", "elements": elems})
    foot = [f"이번 실행 ${cost:.2f}", f"이번 달 누적 ${month_cost:.2f}"]
    if month_cost >= config.MONTHLY_BUDGET * 0.8:
        foot.append(f"⚠️ 월 예산 ${config.MONTHLY_BUDGET:.0f}의 80% 초과")
    if page_url:
        foot.insert(0, f"<{page_url}|📄 전체 리포트>")
    blocks += [{"type": "divider"},
               {"type": "context", "elements": [{"type": "mrkdwn", "text": "   |   ".join(foot)}]}]
    return blocks[:50]


def post_slack(webhook, blocks, fallback):
    payload = {"text": fallback, "blocks": blocks, "unfurl_links": False, "unfurl_media": False}
    r = requests.post(webhook, json=payload, timeout=30)
    if r.status_code != 200:  # 블록 형식 문제면 일반 텍스트로라도 전달
        log(f"[warn] Slack 블록 전송 실패({r.status_code} {r.text}) → 텍스트로 재전송")
        r = requests.post(webhook, json={"text": fallback}, timeout=30)
        r.raise_for_status()


def plain_fallback(label, data, items, page_url):
    lines = [f"{label}: {data.get('headline', '')}"]
    lines += [f"{n}. {it['title']} {it['url']}" for n, it in enumerate(items, 1)]
    if page_url:
        lines.append(page_url)
    return "\n".join(lines)[:3500]


def notify_error(webhook, label, err):
    msg = f"⚠️ {label} 실행 실패: {err}\n```{traceback.format_exc()[-1500:]}```"
    log(msg)
    if webhook:
        try:
            requests.post(webhook, json={"text": msg}, timeout=30)
        except Exception:
            pass


# ============================================================ 실행 흐름
def run_agent(*, key, label, emoji, system, build_prompt, max_searches, max_items,
              show_apply=False, webhook_env="SLACK_WEBHOOK_URL", on_items=None):
    ap = argparse.ArgumentParser(description=f"{label} 실행")
    ap.add_argument("--sample", action="store_true", help="API 호출 없이 tests/sample.json으로 화면만 확인")
    ap.add_argument("--local", action="store_true", help="실제 API로 1회 실행하되 preview/에만 저장, 기록은 남기지 않음")
    ap.add_argument("--slack", action="store_true", help="--sample/--local에서도 Slack으로 실제 전송")
    ap.add_argument("--linear", action="store_true", help="--local에서도 Linear 자동 등록 실행")
    args = ap.parse_args()

    trial = args.sample or args.local
    out_dir = ROOT / ("preview" if trial else "docs")
    send = (not trial) or args.slack
    webhook = os.getenv(webhook_env) or os.getenv("SLACK_WEBHOOK_URL", "")
    today = now_kst()
    hist = _load("history.json", {})
    meter = Meter()

    try:
        if not args.sample and not os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-"):
            raise RuntimeError("ANTHROPIC_API_KEY가 없거나 형식이 다릅니다. .env(로컬) 또는 저장소 시크릿(Actions)을 확인하세요")
        if args.sample:
            data = json.loads((ROOT / "tests" / "sample.json").read_text(encoding="utf-8"))
        else:
            text = research(system, build_prompt(today, recent_titles(hist, key)), max_searches, meter)
            data = parse_or_repair(text, meter)

        seen = set() if trial else {u for run in hist.get(key, []) for u in run["urls"]}
        items = clean_items(data.get("items"), seen, max_items)
        if not args.sample:
            verify_quotes(items)
        if on_items and not args.sample and (not trial or args.linear):
            try:  # Linear 등록이 실패해도 브리핑은 그대로 보낸다
                on_items(items)
            except Exception as e:
                log(f"[warn] 후처리(Linear 등록) 실패: {type(e).__name__}: {e}")

        month = today.strftime("%Y-%m")
        month_cost = record_cost(key, month, meter.cost) if not trial \
            else month_total(_load("costs.json", {}), month) + meter.cost

        (out_dir / key).mkdir(parents=True, exist_ok=True)
        report = out_dir / key / f"{today:%Y-%m-%d}.html"
        report.write_text(render_report(label, today, data, items, meter.cost, month_cost), encoding="utf-8")
        write_index(out_dir)
        base = os.getenv("PAGES_BASE_URL", "").rstrip("/")
        page_url = f"{base}/{key}/{report.name}" if base and not trial else ""

        blocks = slack_blocks(label, emoji, today, data, items, page_url, meter.cost, month_cost, show_apply)
        if send:
            if not webhook:
                raise RuntimeError(f"{webhook_env} 또는 SLACK_WEBHOOK_URL이 비어 있습니다")
            post_slack(webhook, blocks, plain_fallback(label, data, items, page_url))
        else:
            (out_dir / f"{key}-slack.json").write_text(
                json.dumps({"blocks": blocks}, ensure_ascii=False, indent=1), encoding="utf-8")

        if not trial:
            record_run(hist, key, today.strftime("%Y-%m-%d"), items)

        verified = sum(1 for i in items if i.get("quote_status") == "ok")
        log(f"[ok] {label}: {len(items)}건 (인용 확인 {verified}건), 검색 {meter.searches}회, "
            f"비용 약 ${meter.cost:.3f}, 리포트 {report.relative_to(ROOT)}"
            + ("" if send else f", Slack 미리보기 {out_dir.name}/{key}-slack.json"))
    except Exception as e:
        notify_error(webhook if send else "", label, e)
        raise
