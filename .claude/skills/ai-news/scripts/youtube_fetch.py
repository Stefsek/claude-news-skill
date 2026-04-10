#!/usr/bin/env python3
"""Fetch the 2 most recent videos per YouTube channel via RSS.

Usage:
    uv run .claude/skills/ai-news/scripts/youtube_fetch.py '[{"id": "CHANNEL_ID", "name": "Channel Name"}, ...]'

Outputs a JSON array of {title, url, source} to stdout.
Shorts are excluded automatically.
"""

import json
import sys

import feedparser

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
MAX_PER_CHANNEL = 5


def fetch_channel(channel_id: str, name: str) -> list[dict]:
    feed = feedparser.parse(RSS_URL.format(channel_id))
    videos = []
    for entry in feed.entries:
        if "/shorts/" in entry.get("link", ""):
            continue
        videos.append({
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "source": f"YouTube: {name}",
            "published": entry.get("published", ""),
        })
        if len(videos) >= MAX_PER_CHANNEL:
            break
    return videos


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: youtube_fetch.py '<json-array>'", file=sys.stderr)
        return 1

    channels = json.loads(sys.argv[1])
    results = []

    for ch in channels:
        try:
            results.extend(fetch_channel(ch["id"], ch["name"]))
        except Exception as e:
            print(f"Error fetching '{ch.get('name', '?')}': {e}", file=sys.stderr)

    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
