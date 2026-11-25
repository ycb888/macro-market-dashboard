#!/usr/bin/env python3
"""Build the rolling market-news snapshot from public feeds."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from market_news_rules import classify


@dataclass(frozen=True)
class Feed:
    id: str
    group: str
    url: str
    domains: tuple
    default_category: str | None = None


FEEDS = (
    Feed("bloomberg-markets", "bloomberg", "https://www.bloomberg.com/feeds/markets/news.rss", ("bloomberg.com",)),
    Feed("bloomberg-economics", "bloomberg", "https://www.bloomberg.com/feeds/economics/news.rss", ("bloomberg.com",)),
    Feed("bloomberg-politics", "bloomberg", "https://www.bloomberg.com/feeds/politics/news.rss", ("bloomberg.com",)),
    Feed("bbc-business", "bbc", "https://feeds.bbci.co.uk/news/business/rss.xml", ("bbc.co.uk", "bbc.com")),
    Feed("bbc-world", "bbc", "https://feeds.bbci.co.uk/news/world/rss.xml", ("bbc.co.uk", "bbc.com")),
    Feed("fed-monetary", "fed", "https://www.federalreserve.gov/feeds/press_monetary.xml", ("federalreserve.gov",), "macro"),
    Feed("bls-cpi", "bls", "https://www.bls.gov/feed/cpi.rss", ("bls.gov",), "macro"),
    Feed("bls-jobs", "bls", "https://www.bls.gov/feed/empsit.rss", ("bls.gov",), "macro"),
    Feed("bea-releases", "bea", "https://apps.bea.gov/rss/rss.xml", ("bea.gov",)),
    Feed("eia-energy", "eia", "https://www.eia.gov/rss/todayinenergy.xml", ("eia.gov",)),
)

PUBLISHERS = {
    "bloomberg": "Bloomberg", "bbc": "BBC News", "fed": "Federal Reserve",
    "bls": "U.S. Bureau of Labor Statistics", "bea": "U.S. Bureau of Economic Analysis",
    "eia": "U.S. Energy Information Administration",
}
WINDOW = timedelta(days=7)
MAX_BYTES = 2_000_000
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "market_news.json"


def iso(date):
    return date.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if date.tzinfo is None:
        return None
    return date.astimezone(UTC)


def plain(text):
    return " ".join(re.sub(r"<[^>]*>", " ", html.unescape(text)).split())


def event_summary(title, description):
    description = re.sub(r"\s*(Continue reading|Read more)\s*[.…]*$", "", description, flags=re.I)
    if not description or description.rstrip(". …").casefold() == title.rstrip(". …").casefold():
        return title, "headline"
    # Use the source's lead sentences, keeping abbreviations such as U.S. intact.
    sentences = re.split(r"(?<!\b[A-Z]\.)(?<=[.!?])\s+(?=[A-Z0-9])", description, maxsplit=2)
    summary = " ".join(sentences[:2])
    if len(summary) > 300:
        summary = summary[:299].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return summary, "publisher"


def article_url(url, feed):
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or parts.username or parts.password:
        return None
    if not any(host == domain or host.endswith("." + domain) for domain in feed.domains):
        return None
    if feed.group == "bloomberg" and parts.path.startswith(("/news/videos/", "/news/audio/")):
        return None
    query = [
        (key, value) for key, value in parse_qsl(parts.query)
        if not key.lower().startswith(("utm_", "at_", "syn-"))
        and key.lower() not in {"cmpid", "mod", "sref", "srnd", "leadsource", "traffic_source"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sorted(query)), ""))


def parse_feed(payload, feed, now):
    root = ElementTree.fromstring(payload)
    if root.tag in {"rss", "{http://purl.org/rss/1.0/}RDF"}:
        entries = root.findall("./channel/item") or root.findall("./{*}item")
    elif root.tag in {"feed", "{http://www.w3.org/2005/Atom}feed"}:
        entries = root.findall("./{*}entry")
    else:
        raise ValueError("unexpected feed format")

    latest = None
    items = []
    parsed_entries = 0
    for entry in entries:
        title = plain(entry.findtext("{*}title") or "")
        date = parse_date(
            entry.findtext("{*}pubDate") or entry.findtext("{*}published")
            or entry.findtext("{*}date") or entry.findtext("{*}updated")
        )
        if not date or date > now:
            continue
        parsed_entries += 1
        latest = max(latest, date) if latest else date
        if not title or date < now - WINDOW:
            continue

        links = entry.findall("{*}link")
        link = next(
            (item.get("href") or item.text for item in links
             if item.get("rel", "alternate") == "alternate" and (item.get("href") or item.text)),
            "",
        )
        try:
            url = article_url(link.strip(), feed)
        except ValueError:
            continue
        if not url:
            continue

        description = plain(entry.findtext("{*}description") or entry.findtext("{*}summary")
                            or entry.findtext("{*}content") or "")
        result = classify(title, description, feed.default_category)
        if result is None:
            continue
        category, impact = result
        facts, basis = event_summary(title, description)
        items.append({
            "title": title, "url": url, "published_at": iso(date), "feed": feed.id,
            "source": PUBLISHERS[feed.group], "group": feed.group,
            "category": category, "facts": facts, "facts_basis": basis, "impact": impact,
        })

    if entries and not parsed_entries:
        raise ValueError("feed entries have no valid publication dates")
    return items, iso(latest) if latest else None


def fetch(feed, now):
    request = Request(feed.url, headers={
        "User-Agent": "MacroDashboardNews/1.0 (public RSS reader)",
        "Accept": "application/rss+xml,application/atom+xml,text/xml,application/xml,*/*;q=0.1",
    })
    try:
        with urlopen(request, timeout=12) as response:
            payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ValueError("feed exceeds size limit")
        return parse_feed(payload, feed, now)
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        print(f"{feed.id}: {exc}", file=sys.stderr)
        return None


def deduplicate(items):
    urls, titles = set(), set()
    for item in sorted(items, key=lambda item: item["published_at"], reverse=True):
        headline = " ".join(re.findall(r"\w+", item["title"].casefold()))
        if item["url"] in urls or headline in titles:
            continue
        urls.add(item["url"])
        titles.add(headline)
        yield item


def build_snapshot(previous, now):
    old_feeds = previous.get("feeds", {})
    cutoff = iso(now - WINDOW)
    recent = [item for item in previous.get("items", []) if item["published_at"] >= cutoff]
    prior_by_url = {item["url"]: item for item in recent}
    statuses = {}
    current = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(lambda feed: fetch(feed, now), FEEDS)
        for feed, result in zip(FEEDS, results):
            if result is None:
                statuses[feed.id] = {
                    "group": feed.group, "status": "unavailable",
                    "last_success_at": old_feeds.get(feed.id, {}).get("last_success_at"),
                    "latest_published_at": old_feeds.get(feed.id, {}).get("latest_published_at"),
                }
                continue
            items, latest = result
            for item in items:
                old = prior_by_url.get(item["url"], {})
                if item["facts"] == old.get("facts") and old.get("facts_zh"):
                    item["facts_zh"] = old["facts_zh"]
                    if old.get("facts_basis") == "official":
                        item["facts_basis"] = "official"
            current.extend(items)
            statuses[feed.id] = {
                "group": feed.group, "status": "ok",
                "last_success_at": iso(now), "latest_published_at": latest,
            }
            print(f"{feed.id}: {len(items)} relevant items, latest publication {latest or 'none'}")

    return {
        "collected_at": iso(now),
        "feeds": statuses,
        "items": list(deduplicate(current + recent))[:240],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    output = parser.parse_args().output
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    snapshot = build_snapshot(previous, datetime.now(UTC))
    if not any(feed["status"] == "ok" for feed in snapshot["feeds"].values()):
        print("All feeds failed. Keeping previous snapshot.", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Wrote {len(snapshot['items'])} items to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
