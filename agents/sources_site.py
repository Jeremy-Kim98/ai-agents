"""Daily Diff 출처 페이지: docs/insta/*/4_post.json → site/index.html (영어, 이름·비용·모델 정보 없음).

실행: python -m agents.sources_site            (결과: site/index.html)
인스타 프로필 링크가 가리킬 페이지. 본인 이름이 드러나지 않는 주소에 배포한다(배포는 워크플로).
"""
import datetime as dt
import json
from pathlib import Path

from agents.common import E
from agents.insta import BRAND, CATEGORY_EN

ROOT = Path(__file__).resolve().parent.parent
MAX_DAYS = 60

CSS = """
:root{--bg:#F6F4EF;--fg:#16161A;--muted:#6B6A66;--line:#DDD8CC;--accent:#D9480F}
@media (prefers-color-scheme:dark){:root{--bg:#121214;--fg:#EDEBE6;--muted:#9A9890;--line:#2A2A2E;--accent:#FF7A3D}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
main{max-width:680px;margin:0 auto;padding:40px 16px 80px}
h1{font-size:34px;margin:0}p.sub{color:var(--muted);margin:6px 0 36px}
h2{font-size:15px;color:var(--muted);font-weight:600;margin:36px 0 8px;letter-spacing:.02em}
ol{margin:0;padding:0;list-style:none}li{padding:14px 0;border-top:1px solid var(--line)}
li a{color:var(--fg);font-weight:650;text-decoration:none}li a:hover{color:var(--accent)}
.meta{color:var(--muted);font-size:14px;margin-top:2px}
"""


def build(posts):
    days = []
    for p in posts:
        lis = "".join(
            f'<li><a href="{E(i["url"])}" target="_blank" rel="noopener">{E(i["card_line"])}</a>'
            f'<div class="meta">{E(i["source"])} · {E(CATEGORY_EN.get(i["category"], i["category"]))}</div></li>'
            for i in p["items"] if i.get("url", "").startswith(("http://", "https://")))
        if lis:
            d = dt.date.fromisoformat(p["date"])
            days.append(f'<h2 id="{p["date"]}">{d:%a, %b} {d.day}</h2><ol>{lis}</ol>')
    body = "".join(days) or "<p>No posts yet.</p>"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{BRAND} · Sources</title>'
            f'<style>{CSS}</style></head><body><main><h1>{BRAND}</h1>'
            f'<p class="sub">Original sources for every story we post. Newest first.</p>{body}</main></body></html>')


def load_posts(root=ROOT / "docs" / "insta"):
    files = sorted(root.glob("*/4_post.json"), reverse=True)[:MAX_DAYS]
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


if __name__ == "__main__":
    out = ROOT / "site"
    out.mkdir(exist_ok=True)
    posts = load_posts()
    (out / "index.html").write_text(build(posts), encoding="utf-8")
    print(f"{len(posts)}일치 → {out / 'index.html'}")
