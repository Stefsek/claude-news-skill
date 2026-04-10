---
name: ai-news
description: Fetch and deliver AI news. Use this skill whenever the user says /ai-news, asks for AI news, wants a news digest, or asks what's new in AI/LLMs/coding tools. Also use when they ask about recent news, want to check for updates, or say things like "what's happening in AI", "any new releases", "check for news". This skill searches the web, checks YouTube channels, scores and filters results against user preferences, saves to a local SQLite DB, and posts to Discord.
---

# AI News Skill

You are an AI news aggregator. You search the web and YouTube for AI/developer news, score it against the user's preferences, and deliver a curated digest — asking for confirmation before posting to Discord.

**Project root:** The directory containing `.claude/`, `.venv/`, and `.env`.

**Skill directory:** `.claude/skills/ai-news/` — scripts, db, and preferences all live here.

---

## Step 1: Initialize DB

```bash
mkdir -p .claude/skills/ai-news/db
sqlite3 .claude/skills/ai-news/db/news.db "
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    summary TEXT,
    score REAL,
    source TEXT,
    posted_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at TEXT NOT NULL,
    items_fetched INTEGER NOT NULL,
    items_posted INTEGER NOT NULL,
    description TEXT NOT NULL
);"
```

---

## Step 2: Read preferences

Read `.claude/skills/ai-news/PREFERENCES.md` fresh every run. This defines what to love, like, and skip — and is your scoring rubric.

---

## Step 3: Check recent history

```bash
# Last 3 runs
sqlite3 -json .claude/skills/ai-news/db/news.db "SELECT ran_at, items_fetched, items_posted, description FROM runs ORDER BY ran_at DESC LIMIT 3"

# Items from last 7 days
sqlite3 -json .claude/skills/ai-news/db/news.db "SELECT url, title, score, source, posted_at FROM items WHERE posted_at > datetime('now', '-7 days') ORDER BY posted_at DESC"
```

If a topic was covered recently, skip it or find a different angle.

---

## Step 4: Fetch YouTube videos

Pass **all** channels from PREFERENCES.md in a single call:

```bash
uv run .claude/skills/ai-news/scripts/youtube_fetch.py '[{"id": "CHANNEL_ID", "name": "Channel Name"}, ...]'
```

The script returns the **5 most recent non-Shorts videos** per channel as `{title, url, source, published}` objects. Check each video URL against the DB to skip duplicates. Also apply the same 7-day date filter as web articles — drop any video whose `published` date is older than 7 days from today. If `published` is missing or unparseable, keep the video.

---

## Step 5: Search the web

The goal is **20–30 promising candidates** before date verification, because many will be dropped. Before building queries, determine today's date and compute:

- **Month name + year** (e.g. `April 2026`) — include in every query to bias toward recent results

Never hardcode a month — compute it fresh each run.

### 5a. News-site queries

Read the **"Preferred news sites"** section from PREFERENCES.md. For each site listed, run a search:

```
site:<domain> AI [Month Year]
```

Take the top 2–3 results from each site.

### 5b. Broad topic queries — cover ALL preferences

Read **every bullet** in both the **"I love this"** and **"I like this"** sections of PREFERENCES.md. For each bullet, build a search query using its key terms plus `[Month Year]`:

```
<key terms from bullet> [Month Year]
```

Run one search per bullet. Take the top 2–3 results from each.

### 5c. Collect and pre-filter

Merge results from 5a and 5b. You should have **25–40 raw candidates**. Pre-filter by title relevance against PREFERENCES.md — drop anything that clearly falls into the "skip" list. Keep at most **30 candidates** going into date verification.

Set `source` to the domain for each result (e.g. `github.com`, `venturebeat.com`).

### 5d. Date verification — MANDATORY for every web article

For each candidate, use WebFetch to open the page. Look for a publish date in the HTML (`<time>`, `datePublished`, `pubdate`, byline, or any visible date near the top of the article).

- Date is within the last 7 days of today's date → **keep**
- Date is older than 7 days → **drop**, do not include under any circumstances
- Can't fetch (paywall, timeout, error) → **skip and move on**
- No date found anywhere on the page → **drop**

This step does NOT apply to YouTube videos (handled in Step 4). It applies only to web articles.

**DO NOT skip this step.** The URL date, search snippet date, and article title are all unreliable — they have caused stale articles to be posted before. The only date that counts is the one you read from the fetched page content.

Fetch articles in parallel where possible (batch WebFetch calls) to keep the run fast.

---

## Step 6: Deduplicate

For each candidate, compute its MD5 hash and check the DB:

```bash
echo -n 'https://example.com/article' | md5

sqlite3 .claude/skills/ai-news/db/news.db "SELECT url_hash FROM items WHERE url_hash IN ('hash1','hash2',...)"
```

Drop any URL already in the DB. Also skip near-identical titles to recent items.

---

## Step 7: Score and summarize

For each remaining candidate, using PREFERENCES.md:

1. **Score** (0.0–1.0) — how well it matches the user's interests. "Love" topics score 0.8–1.0, "like" topics 0.5–0.8, "skip" topics below 0.4. Apply boosts and penalties from PREFERENCES.md.
2. **Summary** — 2–3 sentences. What's new, what changed, why it matters to an AI developer.

Filter out anything below 0.5. Rank by score descending.

---

## Step 8: Display digest and confirm

Show the digest in the terminal:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AI NEWS DIGEST — <date>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[████░ 0.90] LangGraph CLI 0.4.21: Validate + Async Subagents
  LangGraph CLI 0.4.21 adds a validate command. Deep Agents now support async
  subagents for non-blocking background tasks.
  github.com → https://github.com/langchain-ai/langgraph/releases

[█████ 1.00] Andrej Karpathy Just 10x'd Everyone's Claude Code
  Andrej Karpathy shares workflow techniques for maximizing Claude Code
  effectiveness, covering approaches that dramatically improve output quality.
  YouTube: Nate Herk → https://www.youtube.com/watch?v=sboNwYmH3AY

...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  N items ready · M filtered below threshold
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then ask: **"Post these N items to Discord? [y/N]"**

- Yes → proceed to Step 9
- No → skip to Step 10, save locally only

---

## Step 9: Post to Discord

```bash
uv run .claude/skills/ai-news/scripts/post_discord.py '<json-array>'
```

Each item needs: `title`, `url`, `score`, `source`, `published` (ISO date string — include for both web articles and YouTube videos). The script reads `DISCORD_TOKEN` and `NEWS_CHANNEL_ID` from `.env`.

---

## Step 10: Save to DB

```bash
sqlite3 .claude/skills/ai-news/db/news.db "INSERT OR IGNORE INTO items (url_hash, url, title, summary, score, source, posted_at) VALUES ('HASH','URL','TITLE','SUMMARY',SCORE,'SOURCE',datetime('now'))"
```

Escape single quotes by doubling them (`'` → `''`).

---

## Step 11: Save run record

```bash
sqlite3 .claude/skills/ai-news/db/news.db "INSERT INTO runs (ran_at, items_fetched, items_posted, description) VALUES (datetime('now'), FETCHED, POSTED, 'DESCRIPTION')"
```

Example description: `"Fetched 12 items (8 web, 4 YouTube). Posted 7: LangGraph CLI 0.4.21, Cursor 3 launch, Claude 300k output, 3 Nate Herk videos. Filtered 5 below threshold."`

---

## Notes

- Re-read PREFERENCES.md fresh every run — the user edits it freely
- Be strict: only post things that genuinely matter to an AI developer
- If nothing clears 0.5, say: "No new items above your score threshold"
- Escape all content before inserting into SQLite
