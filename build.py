"""Assemble the morning brief into site/index.html.

    python3 build.py

No API keys and no accounts: prices and earnings dates come from Yahoo Finance,
headlines from Yahoo's public RSS, and the prose is composed from those numbers
rather than written by a model. A build that cannot get prices fails loudly
rather than publishing a half-empty page — a silently wrong brief is worse than
a visible red X.
"""

import html
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feeds
import narrate
import prices

LONDON = ZoneInfo("Europe/London")
OUT = Path("site")
ASSETS = ["manifest.webmanifest", "sw.js", "icon-192.png", "icon-512.png", "apple-touch-icon.png"]
MAX_LINKS = 8

NOTE = (
    "Prices and earnings dates from Yahoo Finance, shown as the last two daily "
    "closes and delayed. Headlines from Yahoo's news feeds. The summary is "
    "assembled from those numbers, not written by anyone &mdash; it says what moved "
    "and links the story, and does not claim to know why. Nothing here is "
    "investment advice."
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


def upcoming_panel(lines):
    if not lines:
        return ""
    body = "\n".join(
        f"<div>{esc(line)}</div>" for line in lines
    )
    return f'<div class="earnings">\n{body}\n</div>'


def headlines_block(rows, movers, headlines):
    """Grouped by holding, whatever moved most first."""
    if not headlines:
        return ""

    order = [m["symbol"] for m in movers]
    order += [r["symbol"] for r in rows if r["symbol"] not in order]

    out = ['<h2>Headlines</h2><div class="news">']
    used = 0
    for symbol in order:
        items = headlines.get(symbol)
        if not items or used >= MAX_LINKS:
            continue
        name = next((r["name"] for r in rows if r["symbol"] == symbol), symbol)
        rendered = []
        for item in items:
            if used >= MAX_LINKS:
                break
            url = safe_url(item["url"])
            if not url:
                continue
            rendered.append(
                f'<li><a href="{url}" rel="noopener noreferrer" target="_blank">'
                f'{esc(item["title"])}</a>'
                f'<span class="src">{esc(item["source"])}</span></li>'
            )
            used += 1
        if rendered:
            out.append(f'<div class="topic">{esc(name)}</div><ul>')
            out.extend(rendered)
            out.append("</ul>")
    out.append("</div>")
    return "\n".join(out) if used else ""


def main():
    now = datetime.now(LONDON)
    date_label = f"{now:%A} {now.day} {now:%B}"
    print(f"building brief for {date_label}")

    holdings = prices.load_watchlist()
    rows = prices.fetch(holdings)

    priced = [r for r in rows if r["price"] is not None]
    if len(priced) < max(2, len(rows) // 2):
        sys.exit(f"only {len(priced)} of {len(rows)} holdings priced - not publishing")
    print(f"  priced {len(priced)}/{len(rows)} holdings")

    movers = prices.movers(rows)
    print(f"  movers: {[m['label'] for m in movers] or 'none'}")

    headlines = feeds.for_holdings(holdings)
    print(f"  headlines for {len(headlines)} holding(s)")

    earnings = feeds.earnings_dates(holdings)
    print(f"  upcoming: {[e['name'] for e in earnings] or 'none'}")

    body = "\n".join(part for part in [
        "<h2>Watchlist</h2>",
        f'<div class="prose">{paragraphs(narrate.watchlist_prose(rows, movers, headlines))}</div>',
        watchlist_table(rows),
        upcoming_panel(narrate.upcoming(earnings)),
        "<h2>Markets</h2>" if narrate.market_prose(rows) else "",
        f'<div class="prose">{paragraphs(narrate.market_prose(rows))}</div>'
        if narrate.market_prose(rows) else "",
        headlines_block(rows, movers, headlines),
    ] if part)

    page = (Path("template.html").read_text()
            .replace("{{DATE}}", esc(date_label))
            .replace("{{STAMP}}", f"Built {now:%H:%M %Z}")
            .replace("{{BODY}}", body)
            .replace("{{NOTE}}", NOTE))

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    for asset in ASSETS:
        shutil.copy(asset, OUT / asset)
    print(f"  wrote {OUT/'index.html'} ({len(page):,} bytes) and {len(ASSETS)} assets")


if __name__ == "__main__":
    main()
