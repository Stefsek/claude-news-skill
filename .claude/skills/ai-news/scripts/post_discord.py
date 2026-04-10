#!/usr/bin/env python3
"""Post news items to a Discord channel.

Usage:
    uv run .claude/skills/ai-news/scripts/post_discord.py '[{"title": "...", "url": "...", "score": 0.9, "source": "..."}]'
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
NEWS_CHANNEL_ID = os.getenv("NEWS_CHANNEL_ID")
DISCORD_API = f"https://discord.com/api/v10/channels/{NEWS_CHANNEL_ID}/messages"


def post_message(text: str) -> bool:
    payload = json.dumps({"content": text}).encode()
    req = urllib.request.Request(
        DISCORD_API,
        data=payload,
        headers={
            "Authorization": f"Bot {DISCORD_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/aiNewsBot, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        print(f"  Discord error {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return False


def format_message(item: dict) -> str:
    score = item.get("score", 0)
    bar = "█" * round(score * 5) + "░" * (5 - round(score * 5))
    published = item.get("published", "")
    if published:
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            published = published[:10]
    date_part = f" · {published}" if published else ""
    return (
        f"**{item['title']}**\n"
        f"{item['url']}\n"
        f"_{item.get('source', '')}{date_part} · {bar} {score:.2f}_"
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: post_discord.py '<json-array>'", file=sys.stderr)
        return 1

    items = json.loads(sys.argv[1])
    posted = 0

    for item in items:
        ok = post_message(format_message(item))
        print(f"  {'✓' if ok else '✗'} {item['title'][:70]}")
        if ok:
            posted += 1
        time.sleep(1)

    print(f"\nPosted {posted}/{len(items)}")
    return 0 if posted == len(items) else 1


if __name__ == "__main__":
    sys.exit(main())
