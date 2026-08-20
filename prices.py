"""Watchlist prices from Yahoo Finance.

Yahoo is the same source the VWRP screener already uses, so there is no extra
API key to keep alive. Everything here is defensive: a brief that renders with
one price missing is far better than one that fails to build at all.
"""

import json
import math
import time
from pathlib import Path

import yfinance as yf

CURRENCY_SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€", "GBp": "p"}


def load_watchlist(path="watchlist.json"):
    data = json.loads(Path(path).read_text())
    return [h for h in data["holdings"]]


def _bulk_closes(symbols, attempts=3):
    """Closing prices for every symbol at once, or None if Yahoo won't play.

    Returns None rather than raising: a single missing frame should fall through
    to the per-symbol path below, not end the build.
    """
    for attempt in range(1, attempts + 1):
        try:
            frame = yf.download(
                symbols, period="7d", interval="1d",
                progress=False, auto_adjust=False, threads=False,
            )
        except Exception as exc:
            print(f"  bulk download attempt {attempt} failed: {type(exc).__name__}: {exc}")
            frame = None
        if frame is not None and not frame.empty and "Close" in frame:
            return frame["Close"]
        if attempt < attempts:
            time.sleep(2 * attempt)
    print("  bulk download gave nothing usable - falling back per symbol")
    return None


def _closes_for(frame, symbol):
    """The close series for one symbol, from the bulk frame or fetched alone."""
    if frame is not None:
        try:
            series = frame[symbol].dropna()
            if len(series) >= 2:
                return series
        except (KeyError, IndexError):
            pass
    try:
        history = yf.Ticker(symbol).history(period="7d", auto_adjust=False)
        if history is not None and "Close" in history:
            return history["Close"].dropna()
    except Exception as exc:
        print(f"  no prices for {symbol}: {type(exc).__name__}")
    return None


def fetch(holdings):
    """Return one row per holding: price, previous close, percent change.

    Rows whose data did not arrive keep `price=None` rather than being dropped,
    so a gap shows up on the page as a visible dash instead of a silently
    shorter table.
    """
    symbols = [h["symbol"] for h in holdings]
    frame = _bulk_closes(symbols)

    rows = []
    for h in holdings:
        row = dict(h, price=None, prev=None, change=None, currency=None)
        series = _closes_for(frame, h["symbol"])

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
