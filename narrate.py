"""The written half, composed from the numbers rather than by a model.

This is deliberately mechanical. It says what moved, by how much, and what the
morning's headline on it is — all facts already on the page. It never explains
why something moved and never characterises a price, because nothing here knows
either of those things. Where a cause is wanted, the headline link is the honest
way to offer one.
"""

import prices


# Headlines that describe a move are far more use next to a mover than the
# evergreen "Is X a buy?" pieces that dominate syndicated feeds. This is a
# preference, not a filter — if nothing matches, the first story still runs.
MOVE_WORDS = (
    "surge", "surges", "surged", "jump", "jumps", "jumped", "climb", "climbs",
    "climbed", "rally", "rallies", "rallied", "soar", "soars", "soared",
    "rise", "rises", "rose", "gain", "gains", "gained",
    "fall", "falls", "fell", "drop", "drops", "dropped", "sink", "sinks",
    "sank", "slide", "slides", "slid", "slump", "slumps", "slumped",
    "tumble", "tumbles", "tumbled", "plunge", "plunges", "plunged",
    "sell-off", "selloff", "buyback", "upsizes", "offering", "guidance",
    "results", "earnings", "downgrade", "upgrade", "%",
)


def _explaining_story(stories):
    """The story most likely to say why something moved."""
    if not stories:
        return None
    for story in stories:
        title = story["title"].lower()
        if any(word in title for word in MOVE_WORDS):
            return story
    return stories[0]


def _join(names):
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def _direction(row):
    return "down" if row["change"] < 0 else "up"


def _pct(row):
    return f"{abs(row['change']):.1f}%"


def watchlist_prose(rows, movers, headlines):
    """Two or three plain sentences about what the table shows."""
    paragraphs = []
    priced = [r for r in rows if r["change"] is not None]

    if not priced:
        return ["No prices came through this morning."]

    if not movers:
        biggest = max(priced, key=lambda r: abs(r["change"]))
        paragraphs.append(
            f"A quiet session on the watchlist — nothing moved more than 2%, and "
            f"the widest was {biggest['name']} at {_pct(biggest)} {_direction(biggest)}."
        )
    else:
        lead = movers[0]
        sentence = (
            f"{lead['name']} is the one that moved, {_direction(lead)} {_pct(lead)}"
        )
        rest = movers[1:]
        if rest:
            same = [m for m in rest if (m["change"] < 0) == (lead["change"] < 0)]
            opposite = [m for m in rest if (m["change"] < 0) != (lead["change"] < 0)]
            tail = []
            if same:
                tail.append(
                    f"{_join([m['name'] for m in same])} went the same way "
                    f"({_join([_pct(m) for m in same])})"
                )
            if opposite:
                tail.append(
                    f"{_join([m['name'] for m in opposite])} ran the other way "
                    f"({_join([_pct(m) for m in opposite])})"
                )
            sentence += ", while " + " and ".join(tail)
        paragraphs.append(sentence + ".")

        # Point at the story rather than claiming to know the cause.
        top_story = _explaining_story(headlines.get(lead["symbol"]))
        if top_story:
            paragraphs.append(
                f"The morning's headline on {lead['name']} is “{top_story['title']}” "
                f"({top_story['source']}) — it's linked below, along with the rest."
            )

    quiet = [r for r in priced if abs(r["change"]) < 1.0]
    if len(quiet) >= 2:
        widest = max(quiet, key=lambda r: abs(r["change"]))
        paragraphs.append(
            f"{_join([r['name'] for r in quiet])} were all inside "
            f"{_pct(widest)} of flat."
        )

    return paragraphs


def market_prose(rows):
    """What the whole list did, taken together."""
    priced = [r for r in rows if r["change"] is not None]
    if len(priced) < 3:
        return []

    up = [r for r in priced if r["change"] > 0.05]
    down = [r for r in priced if r["change"] < -0.05]
    tracker = next((r for r in rows if r["label"] == "VWRP"), None)

    if len(down) >= len(priced) - 1:
        shape = "Almost everything on the list finished lower"
    elif len(up) >= len(priced) - 1:
        shape = "Almost everything on the list finished higher"
    elif len(down) > len(up):
        shape = f"More down than up — {len(down)} of {len(priced)} finished lower"
    elif len(up) > len(down):
        shape = f"More up than down — {len(up)} of {len(priced)} finished higher"
    else:
        shape = "The list split evenly"

    if tracker and tracker["change"] is not None:
        shape += (
            f", and the All-World tracker itself was {_direction(tracker)} "
            f"{_pct(tracker)}"
        )

    return [shape + "."]


def upcoming(earnings):
    return [
        f"{e['name']} reports {e['date']:%-d %B}" for e in earnings
    ]
