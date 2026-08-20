"""Watchlist prices from Yahoo Finance.

Yahoo is the same source the VWRP screener already uses, so there is no extra
API key to keep alive. Everything here is defensive: a brief that renders with
one price missing is far better than one that fails to build at all.
"""

import json
import math
from pathlib import Path

import yfinance as yf

CURRENCY_SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€", "GBp": "p"}


def load_watchlist(path="watchlist.json"):
    data = json.loads(Path(path).read_text())
    return [h for h in data["holdings"]]


def fetch(holdings):
    """Return one row per holding: price, previous close, percent change.

    Rows whose data did not arrive keep `price=None` rather than being dropped,
    so a gap shows up on the page as a visible dash instead of a silently
    shorter table.
    """
    symbols = [h["symbol"] for h in holdings]
    frame = yf.download(
        symbols, period="7d", interval="1d", progress=False, auto_adjust=False
    )["Close"]

    rows = []
    for h in holdings:
        row = dict(h, price=None, prev=None, change=None, currency=None)
        try:
            series = frame[h["symbol"]].dropna()
        except KeyError:
            series = None

        if series is not None and len(series) >= 2:
            last, prev = float(series.iloc[-1]), float(series.iloc[-2])
            if not (math.isnan(last) or math.isnan(prev)) and prev:
                row["price"] = last
                row["prev"] = prev
                row["change"] = 100.0 * (last / prev - 1.0)

        try:
            row["currency"] = yf.Ticker(h["symbol"]).fast_info.currency
        except Exception:
            row["currency"] = None

        rows.append(row)
    return rows


def format_price(row):
    if row["price"] is None:
        return "—"
    sym = CURRENCY_SYMBOL.get(row["currency"] or "", "")
    return f"{sym}{row['price']:,.2f}"


def format_change(row):
    if row["change"] is None:
        return "—"
    return f"{row['change']:+.2f}%"


def change_class(row):
    if row["change"] is None:
        return "na"
    if row["change"] > 0.05:
        return "up"
    if row["change"] < -0.05:
        return "down"
    return "flat"


def movers(rows, threshold=2.0):
    """The rows worth mentioning in prose, biggest absolute move first."""
    moved = [r for r in rows if r["change"] is not None and abs(r["change"]) >= threshold]
    return sorted(moved, key=lambda r: abs(r["change"]), reverse=True)
