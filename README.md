# Morning Brief

A single page, rebuilt every weekday morning: the watchlist with overnight moves,
what actually moved and why, markets and macro, and a few headlines worth opening.
Add it to your home screen and it behaves like an app.

**Live at:** https://fredh2005.github.io/morning-brief/

## How it works

| Piece | What it does |
|---|---|
| `watchlist.json` | The list of holdings. Edit this to change what the brief covers. |
| `prices.py` | Last two daily closes per holding, from Yahoo Finance. No API key. |
| `feeds.py` | Headlines per holding from Yahoo's public RSS, plus upcoming earnings dates. |
| `narrate.py` | The written summary, composed from the numbers rather than by a model. |
| `build.py` | Puts the page together into `site/`. |
| `template.html` | The page itself — light and dark, safe-area aware, PWA metadata. |
| `make_icons.py` | Regenerates the home-screen icons. Run by hand; the PNGs are committed. |

No API keys, no accounts, nothing to keep topped up. Everything comes from Yahoo
Finance: prices, earnings dates, and the news feeds behind the headline links.

The summary is assembled, not written. It says what moved and by how much, and
quotes the morning's headline on the biggest mover — preferring one that describes
a move over the evergreen "Is X a buy?" pieces. It never claims to know *why*
something moved, because nothing in this repo does; the link is the honest way to
offer a reason. Everything that reaches the page is HTML-escaped, and only https
links are emitted.

## The schedule

`.github/workflows/brief.yml` runs at **05:00 UK on weekdays**, not 07:00. GitHub's
scheduler is unreliable about start times — on this account it has run crons over an
hour late — so the build aims two hours early and the brief is there by seven.

Two crons cover the UK clock change, and the guard job decides which one is real by
looking at **which cron fired**, never at the wall clock when the run started. That
distinction matters: a wall-clock check silently skips the genuine firing whenever
GitHub is late, and reports success while doing it.

`keepalive.yml` makes one commit a month so GitHub doesn't disable the schedule for
inactivity.

## Setup

No secrets. The only setting is Pages: Settings → Pages → Source → **GitHub
Actions**.

## Running it locally

```bash
pip install -r requirements.txt
python3 build.py
open site/index.html
```

## What it will not do

It reports; it does not advise. No buy/sell/hold, no valuation calls, no forecasts,
and no explanation of cause it cannot actually support. Prices are delayed daily
closes, not live quotes.
