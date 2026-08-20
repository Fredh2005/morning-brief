"""Headlines per holding, from Yahoo Finance's public RSS. No API key.

One feed per symbol. Items are filtered for freshness and de-duplicated across
symbols, so a story naming three of your holdings appears once rather than three
times. Anything that fails is skipped quietly — a missing feed should cost you a
few links, not the morning's brief.
"""

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
UA = "Mozilla/5.0 (compatible; morning-brief/1.0)"

# Yahoo carries syndicated content of wildly varying quality. These are the
# domains whose headlines are worth putting in front of someone at seven a.m.
PREFERRED = (
    "reuters.com", "ft.com", "bloomberg.com", "cnbc.com", "wsj.com",
    "barrons.com", "finance.yahoo.com", "marketwatch.com", "investors.com",
    "theguardian.com", "bbc.co.uk", "apnews.com",
)


def _source_name(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _fetch(symbol, timeout):
    request = urllib.request.Request(FEED.format(symbol=urllib.parse.quote(symbol)),
                                     headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return ET.fromstring(response.read())


def _published(item):
    raw = item.findtext("pubDate")
    if not raw:
        return None
    try:
        stamp = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def for_holdings(holdings, per_holding=2, max_age_hours=48, timeout=15):
    """Fresh headlines keyed by symbol, best sources first, no repeats."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    seen_titles = set()
    out = {}

    for holding in holdings:
        symbol = holding["symbol"]
        try:
            root = _fetch(symbol, timeout)
        except (urllib.error.URLError, ET.ParseError, OSError) as exc:
            print(f"  no feed for {symbol}: {type(exc).__name__}")
            continue

        candidates = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link.startswith("https://"):
                continue
            published = _published(item)
            if published and published < cutoff:
                continue
            key = title.lower()
            if key in seen_titles:
                continue
            source = _source_name(link)
            candidates.append({
                "title": title,
                "url": link,
                "source": source,
                "published": published,
                "rank": PREFERRED.index(source) if source in PREFERRED else len(PREFERRED),
            })

        candidates.sort(key=lambda c: (c["rank"], -(c["published"] or cutoff).timestamp()))
        chosen = candidates[:per_holding]
        for c in chosen:
            seen_titles.add(c["title"].lower())
        if chosen:
            out[symbol] = chosen

    return out


def earnings_dates(holdings, within_days=21, timeout=15):
    """Upcoming earnings for holdings that have them, soonest first."""
    import yfinance as yf

    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=within_days)
    found = []

    for holding in holdings:
        try:
            calendar = yf.Ticker(holding["symbol"]).calendar or {}
        except Exception:
            continue  # ETFs and anything without fundamentals simply have none
        dates = calendar.get("Earnings Date") or []
        for date in dates:
            if today <= date <= horizon:
                found.append((date, holding["name"]))
                break

    found.sort()
    return [{"date": d, "name": n} for d, n in found]
