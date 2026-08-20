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
| `brief.py` | Claude researches the moves with web search, then reshapes the findings into a fixed schema. |
| `build.py` | Puts the page together into `site/`. |
| `template.html` | The page itself — light and dark, safe-area aware, PWA metadata. |
| `make_icons.py` | Regenerates the home-screen icons. Run by hand; the PNGs are committed. |

Every link on the page is one that web search actually returned — `brief.py` checks
each URL against the search results and drops anything the model invented, rather
than trusting it. Everything that reaches the page is HTML-escaped.

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

One secret is required: **`ANTHROPIC_API_KEY`**, under Settings → Secrets and
variables → Actions. Pages must be set to deploy from **GitHub Actions**
(Settings → Pages → Source).

## Running it locally

```bash
pip install -r requirements.txt
python3 build.py --no-llm     # prices only, no API key needed
python3 build.py              # the real thing
open site/index.html
```

## What it will not do

It reports; it does not advise. No buy/sell/hold, no valuation calls, no forecasts.
An analyst's view appears only as a fact about what that analyst said. Prices are
delayed daily closes, not live quotes.
