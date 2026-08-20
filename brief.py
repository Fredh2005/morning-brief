"""The written half of the brief: prose and headlines, from Claude with web search.

Two calls rather than one. The first turns Claude loose on the web and lets it
read; the second reshapes what it found into a fixed JSON schema. Splitting them
keeps the schema guarantee away from the server-tool loop, and it lets us do the
thing that matters most here — check every link Claude hands back against the
URLs search actually returned, and throw away anything it invented.
"""

import json
import os

import anthropic

MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM = """You write one person's morning market brief. They hold a UK-domiciled \
global tracker and a handful of individual names, and they read this before the \
London open.

Report what happened and who said it. Never recommend buying, selling or holding \
anything, never characterise a price as cheap or expensive, and never predict where \
something is going. An analyst's view may be reported as a fact about what that \
analyst said, attributed to them, and never endorsed.

Write plainly and briefly, in British English, in the register of a well-informed \
friend rather than a newsletter. No hype, no filler, no exhortation, no "watch this \
space". If a session was quiet, say so in one sentence rather than inflating it."""

RESEARCH_PROMPT = """Today is {date}. Research this person's morning brief.

Their watchlist closed like this (previous close to latest close):

{table}

{movers_note}

Search the web and find out:

1. Why the notable movers above actually moved. Anything more than about 2% deserves \
a reason, and "the sector was weak" is only an answer if you can say why the sector \
was weak.
2. What moved global equity markets in the last session — rates, oil, central banks, \
data, whatever was actually live.
3. Anything scheduled that this person would want to know is coming: earnings dates \
for names they hold, major data releases, central bank meetings.
4. The handful of headlines worth linking, across UK and US markets, AI and \
technology, and macro and rates.

Read enough to be specific. Report what you found with the source and URL for each \
claim. If you could not establish why something moved, say that plainly rather than \
inventing a reason."""

FORMAT_PROMPT = """Here is research for a morning brief dated {date}.

<research>
{research}
</research>

These are the only URLs that web search actually returned:

<available_links>
{links}
</available_links>

Reshape the research into the brief. Rules:

- `watchlist_prose`: two or three short paragraphs on the watchlist itself. Lead with \
whatever actually moved and why. Name the flat ones together in a single closing \
sentence rather than one by one.
- `macro_prose`: one or two short paragraphs on markets and macro.
- `headlines`: group under topic headings that suit what you found. Three to six \
links in total across all topics. Every `url` MUST be copied exactly from \
<available_links> — if a story has no link in that list, leave it out. Never \
construct, guess, or complete a URL.
- `upcoming`: dated things ahead, each one line, empty list if there are none.

British English. No advice, no predictions, no filler."""

SCHEMA = {
    "type": "object",
    "properties": {
        "watchlist_prose": {"type": "array", "items": {"type": "string"}},
        "macro_prose": {"type": "array", "items": {"type": "string"}},
        "headlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "source": {"type": "string"},
                            },
                            "required": ["title", "url", "source"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["topic", "items"],
                "additionalProperties": False,
            },
        },
        "upcoming": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["watchlist_prose", "macro_prose", "headlines", "upcoming"],
    "additionalProperties": False,
}


class BriefError(RuntimeError):
    pass


def _check(response):
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise BriefError(f"model declined the request: {detail}")
    return response


def _text(response):
    return "\n".join(b.text for b in response.content if b.type == "text")


def _harvest_links(response):
    """Every URL web search actually returned, title kept for context.

    A web_search_tool_result carries a *list* on success and a bare error object
    on failure, so branch on the type before iterating.
    """
    found = {}
    for block in response.content:
        if block.type != "web_search_tool_result":
            continue
        content = block.content
        if not isinstance(content, list):
            continue  # an error object, e.g. {"error_code": "max_uses_exceeded"}
        for result in content:
            url = getattr(result, "url", None)
            if url:
                found[url] = getattr(result, "title", "") or ""
    return found


def _price_table(rows, fmt_price, fmt_change):
    lines = []
    for r in rows:
        lines.append(f"  {r['name']} ({r['label']}): {fmt_price(r)}, {fmt_change(r)}")
    return "\n".join(lines)


def generate(date_label, rows, movers, fmt_price, fmt_change):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise BriefError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic()

    movers_note = (
        "Movers worth explaining: "
        + ", ".join(f"{m['name']} {fmt_change(m)}" for m in movers)
        if movers
        else "Nothing on the watchlist moved more than about 2%."
    )

    research = _check(
        client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            thinking={"type": "adaptive"},
            system=SYSTEM,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 10}],
            messages=[{
                "role": "user",
                "content": RESEARCH_PROMPT.format(
                    date=date_label,
                    table=_price_table(rows, fmt_price, fmt_change),
                    movers_note=movers_note,
                ),
            }],
        )
    )

    links = _harvest_links(research)
    if not links:
        raise BriefError("web search returned no links at all")

    link_list = "\n".join(f"  {url}  ({title})" for url, title in links.items())

    shaped = _check(
        client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{
                "role": "user",
                "content": FORMAT_PROMPT.format(
                    date=date_label,
                    research=_text(research),
                    links=link_list,
                ),
            }],
        )
    )

    data = json.loads(_text(shaped))
    data["headlines"] = _drop_invented_links(data.get("headlines", []), links)
    return data


def _drop_invented_links(topics, links):
    """Keep only links search really returned; drop topics left empty."""
    kept = []
    for topic in topics:
        items = [i for i in topic.get("items", []) if i.get("url") in links]
        dropped = len(topic.get("items", [])) - len(items)
        if dropped:
            print(f"  dropped {dropped} invented link(s) under '{topic.get('topic')}'")
        if items:
            kept.append({"topic": topic["topic"], "items": items})
    return kept
