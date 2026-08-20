"""Assemble the morning brief into site/index.html.

    python3 build.py              # full build, needs ANTHROPIC_API_KEY
    python3 build.py --no-llm     # prices only, for checking layout offline

Everything the model or the market hands us is escaped before it reaches the
page, and a build that cannot get prices fails loudly rather than publishing a
half-empty brief — a silently wrong page is worse than a visible red X.
"""

import argparse
import html
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import prices

LONDON = ZoneInfo("Europe/London")
OUT = Path("site")
ASSETS = ["manifest.webmanifest", "sw.js", "icon-192.png", "icon-512.png", "apple-touch-icon.png"]

NOTE = (
    "Prices from Yahoo Finance, delayed and shown as the last two daily closes. "
    "Headlines found by Claude with web search; every link is one search actually "
    "returned. Prose written by Claude from the data above &mdash; check anything that "
    "matters before you act on it. Nothing here is investment advice."
)


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(url):
    """Only ever emit https links, and never anything with markup in it."""
    url = str(url).strip()
    if not url.lower().startswith("https://"):
        return None
    return html.escape(url, quote=True)


def paragraphs(items):
    return "\n".join(f"<p>{esc(p)}</p>" for p in items if str(p).strip())


def watchlist_table(rows):
    out = ["<table><tbody>"]
    for r in rows:
        out.append(
            "<tr>"
            f'<td class="name">{esc(r["name"])}<small>{esc(r["label"])}</small></td>'
            f'<td class="px">{esc(prices.format_price(r))}</td>'
            f'<td class="pct {prices.change_class(r)}">{esc(prices.format_change(r))}</td>'
            "</tr>"
        )
    out.append("</tbody></table>")
    return "\n".join(out)


def upcoming_panel(items):
    if not items:
        return ""
    lines = "\n".join(f"<div>{esc(i)}</div>" for i in items)
    return f'<div class="earnings">\n{lines}\n</div>'


def headlines_block(topics):
    if not topics:
        return ""
    out = ['<h2>Headlines</h2><div class="news">']
    for topic in topics:
        items = []
        for item in topic["items"]:
            url = safe_url(item["url"])
            if not url:
                continue
            items.append(
                f'<li><a href="{url}" rel="noopener noreferrer" target="_blank">'
                f'{esc(item["title"])}</a>'
                f'<span class="src">{esc(item["source"])}</span></li>'
            )
        if not items:
            continue
        out.append(f'<div class="topic">{esc(topic["topic"])}</div><ul>')
        out.extend(items)
        out.append("</ul>")
    out.append("</div>")
    return "\n".join(out)


def build_body(rows, written):
    parts = ["<h2>Watchlist</h2>"]
    if written and written.get("watchlist_prose"):
        parts.append(f'<div class="prose">{paragraphs(written["watchlist_prose"])}</div>')
    parts.append(watchlist_table(rows))
    if written:
        parts.append(upcoming_panel(written.get("upcoming", [])))
        if written.get("macro_prose"):
            parts.append("<h2>Markets &amp; macro</h2>")
            parts.append(f'<div class="prose">{paragraphs(written["macro_prose"])}</div>')
        parts.append(headlines_block(written.get("headlines", [])))
    return "\n".join(p for p in parts if p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true",
                    help="skip the Claude calls; render prices only")
    args = ap.parse_args()

    now = datetime.now(LONDON)
    date_label = f"{now:%A} {now.day} {now:%B}"

    print(f"building brief for {date_label}")
    rows = prices.fetch(prices.load_watchlist())

    priced = [r for r in rows if r["price"] is not None]
    if len(priced) < max(2, len(rows) // 2):
        sys.exit(f"only {len(priced)} of {len(rows)} holdings priced - not publishing")
    print(f"  priced {len(priced)}/{len(rows)} holdings")

    moved = prices.movers(rows)
    print(f"  movers: {[m['label'] for m in moved] or 'none'}")

    written = None
    if not args.no_llm:
        import brief
        written = brief.generate(
            date_label, rows, moved, prices.format_price, prices.format_change
        )
        n = sum(len(t["items"]) for t in written.get("headlines", []))
        print(f"  wrote {len(written.get('watchlist_prose', []))} watchlist paragraph(s), "
              f"{n} headline link(s)")

    stamp = f"Built {now:%H:%M %Z}"
    if args.no_llm:
        stamp += " &middot; prices only"

    page = (Path("template.html").read_text()
            .replace("{{DATE}}", esc(date_label))
            .replace("{{STAMP}}", stamp)
            .replace("{{BODY}}", build_body(rows, written))
            .replace("{{NOTE}}", NOTE))

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    for asset in ASSETS:
        shutil.copy(asset, OUT / asset)
    print(f"  wrote {OUT/'index.html'} ({len(page):,} bytes) and {len(ASSETS)} assets")


if __name__ == "__main__":
    main()
