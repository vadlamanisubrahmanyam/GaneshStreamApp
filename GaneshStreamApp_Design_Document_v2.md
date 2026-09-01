# GaneshStream AI — Design Document (v2)

*Supersedes the original "Phase 2" design docs. This version is written
against the actual rebuilt codebase, not a forward-looking plan — every
section below describes what's really in the repo today.*

---

## 1. Overview

GaneshStream AI is a personal, local-first tool for tracking sentiment
around a topic on social media. A user picks a hashtag, the app pulls
recent public posts matching it, runs each post through Gemini for
sentiment classification, and shows the results in a live dashboard.

**Core jobs to be done**
1. Let the user configure a topic, a source, and an AI model without touching code.
2. Fetch recent public posts for that topic from the selected source.
3. Classify each post's sentiment (and score, reasoning, language) via Gemini.
4. Store results without duplicates, and show them filterable by topic in a dashboard.

**Explicitly out of scope for v1:** authentication/multi-user support,
posting or replying to anything, any source other than Mastodon, and any
hosted/always-on deployment (this is a laptop-local tool for now).

---

## 2. What changed from the original build

The original three-script build (`configure_manager.py`, `main.py`,
`dashboard.py`) had a sound overall shape but several pieces that were
never actually wired together:

| Area | v1 problem | v2 fix |
|---|---|---|
| Storage | Dashboard read `data/stream_results.db` / table `sentiment_results`; the collector wrote `data/analysis_results.db` / table `posts` — two databases that never met | One `DatabaseManager`, one path (`data/stream_results.db`), one schema, imported by both the collector and the dashboard |
| Mastodon auth | Connector read env var `MASTODON_ACCESS_TOKEN`; `.env` defined `MASTODON_TOKEN` — token was always `None` | Standardised on `MASTODON_ACCESS_TOKEN` (old name still accepted as a fallback) |
| Data model | `topic` was passed into `SocialPost` but not declared on the model, so Pydantic silently dropped it | `topic` is now a required field on `SocialPost`, persisted and used for dashboard filtering |
| Sources | Reddit referenced in design docs and `requirements.txt`, never implemented; `base_collector.py` and `reddit_collector.py` were empty files | `RedditConnector` implemented (PRAW, `r/all` search), but Reddit's own Nov-2025 policy change now blocks new credentials — see §11. Bluesky added instead as the second live source (open public search, no approval gate) |
| App structure | Three separate processes (Streamlit config UI → subprocess → separate Streamlit dashboard), coordinating over subprocess stdout | Merged into a single `app.py` with three tabs; the collector runs in-process, no subprocess/stdout parsing |
| Error handling | Broad `try/except` blocks in `main.py` printed generic "Execution Error", hiding the real cause | Errors propagate to the UI log with the actual exception message |
| AI model selection | Hardcoded string `gemini-2.0-flash`; broke with a 404 once Google retired that model | Model dropdown populated live from `client.models.list()`, filtered to models that support `generateContent`; falls back to a short static list if offline or unauthenticated |

---

## 3. User flow

1. **Settings tab** — choose source (Mastodon and Bluesky live; Reddit built but policy-gated, Twitter/Facebook shown as "coming soon"), topic/hashtag, post limit, throttle seconds between AI calls, and Gemini model (live dropdown). Save writes `config/search_config.yaml`.
2. **Run Collector tab** — click Run now. For each fetched post: skip if already in the database (by post ID), otherwise send to Gemini, store the result, log one line to a live-updating log panel.
3. **Dashboard tab** — reads the same database directly, lets the user filter by topic, shows post count and average sentiment score, and the full results table.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      app.py (Streamlit)                  │
│   ┌───────────┐   ┌────────────────┐   ┌──────────────┐  │
│   │ Settings  │   │  Run Collector  │   │  Dashboard   │  │
│   │   tab     │   │      tab        │   │     tab      │  │
│   └─────┬─────┘   └────────┬────────┘   └──────┬───────┘  │
│         │                  │                    │          │
│   config/search_config.yaml│              reads directly   │
│         │          ┌───────▼────────┐            │          │
│         │          │ ProjectOrchestrator          │          │
│         │          │  (src/orchestrator.py)       │          │
│         │          └───┬───────┬────┘            │          │
│         │              │       │                  │          │
│         │    ┌─────────▼──┐ ┌──▼───────────┐      │          │
│         │    │ Connector  │ │ AnalysisEngine│      │          │
│         │    │ (Mastodon) │ │   (Gemini)    │      │          │
│         │    └────────────┘ └──────────────┘      │          │
│         │              │       │                  │          │
│         │              └───┬───┘                  │          │
│         │           ┌──────▼──────┐                │          │
│         └──────────►│DatabaseManager│◄──────────────┘          │
│                      │ (SQLite)     │                          │
│                      └──────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

**Process model:** one process, one Streamlit run. The collector executes
synchronously inside the "Run now" button handler; there is no background
worker or queue. This is intentional for a single-user, occasional-use
local tool — it keeps the whole system in one file you can read top to
bottom, at the cost of the UI being busy while a run is in progress.

---

## 5. Data model

**`sentiment_results` table** (SQLite, `data/stream_results.db`)

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT (PK) | Source-native post ID; used for dedup |
| `topic` | TEXT | The hashtag/topic searched for |
| `source` | TEXT | `"mastodon"` / `"bluesky"` today (live); `"reddit"` implemented but not offered (policy-gated); `"twitter"` / `"facebook"` reserved |
| `author` | TEXT | Username |
| `content` | TEXT | Post text, HTML-stripped |
| `sentiment` | TEXT | e.g. "Positive" / "Negative" / "Neutral" |
| `sentiment_score` | REAL | Model's confidence/intensity score |
| `reasoning` | TEXT | Model's short justification |
| `language` | TEXT | Detected language |
| `timestamp` | DATETIME | Post's original creation time (ISO 8601) |

**In-memory models (`src/models.py`, Pydantic)**
- `SocialPost` — `id, topic, content, author, source, timestamp`
- `SentimentResult` — `sentiment, score, reasoning, language` (this is also passed as Gemini's structured-output schema, so the model's JSON response is validated on the way in)

---

## 6. Connector interface

```python
class BaseConnector(ABC):
    name: str
    def fetch_posts(self, topic: str, limit: int) -> List[SocialPost]: ...
    def is_configured(self) -> bool: ...
```

`src/connectors/__init__.py` holds a `REGISTRY` dict mapping source name →
connector class, and a `LIVE_SOURCES` list of which ones are actually
usable today (`["mastodon", "bluesky"]`). Reddit's connector is registered
in `REGISTRY` but deliberately left out of `LIVE_SOURCES` (see §11) so the
Settings tab doesn't offer a source that fails for almost everyone. Adding
a new source is: implement the class, add one line to `REGISTRY`, add one
line to `LIVE_SOURCES` once it's tested — `app.py` needs no changes, since
the Settings tab reads the source list from these two structures.

---

## 7. AI model selection

`src/analysis/engine.list_models(api_key)` calls the Gemini API's
`models.list()` and filters to entries whose `supported_actions` includes
`generateContent`, excluding embedding/image/video-only models. This list
is what populates the Settings tab dropdown. Rationale: the v1 outage
(`gemini-2.0-flash` returning 404 after being retired) was a direct result
of a hardcoded model string. A live dropdown means the app self-adjusts as
Google ships and retires models, rather than needing a code change every
time.

A small hardcoded `FALLBACK_MODELS` list exists only for the case where
`GEMINI_API_KEY` isn't set yet or the network call fails, so the dropdown
is never empty.

---

## 8. Configuration & secrets

| File | Committed? | Purpose |
|---|---|---|
| `.env` | No (gitignored) | `GEMINI_API_KEY`, `MASTODON_ACCESS_TOKEN`, `MASTODON_API_BASE_URL` |
| `.env.example` | Yes | Template showing required variable names |
| `config/search_config.yaml` | No (gitignored) | User's saved topic/limit/model/etc. — written by the Settings tab, per-machine |

---

## 9. Deployment

Runs as a single local Streamlit process (`streamlit run app.py`) on the
user's laptop today. For future hosting, Streamlit Community Cloud (free
tier) is the natural next step — it's built specifically for this
single-process, persistent-WebSocket execution model, unlike serverless
platforms (Vercel, etc.) which aren't a fit for Streamlit's architecture.
See `README.md` for step-by-step deployment instructions.

---

## 10. Non-functional notes

| Area | Current behavior |
|---|---|
| Duplicate handling | `DatabaseManager.is_duplicate()` checks post ID before analysis; duplicates are skipped, not re-analyzed (saves API quota) |
| Rate limiting | User-configurable sleep between Gemini calls (`sleep_time`, default 12s) to stay within free-tier rate limits |
| Failure isolation | If one post fails analysis (e.g. model deprecated, malformed response), the run logs it and continues with the next post rather than aborting |
| Concurrency | None — single-user, single-process, synchronous. Not a concern at current scale |

---

## 11. Open items for future phases

1. **Twitter/X connector** — stub exists (`src/connectors/twitter_connector.py`); needs actual API integration (note: X's API pricing/access tiers should be checked before committing, unlike Mastodon's free public API).
2. **Facebook connector** — stub exists; Graph API's public content search is materially more restricted than Mastodon/Twitter, likely requiring an approved app and access to specific Pages rather than open keyword search.
3. **Reddit connector** — code-complete (`RedditConnector`, PRAW, `r/all` search), but Reddit closed self-service OAuth app creation in November 2025 ("Responsible Builder Policy"). New credentials are rarely approved for personal/script use, so this source is kept out of `LIVE_SOURCES` until that changes. Re-enabling it later is a one-line change if you obtain credentials or the policy shifts.
4. **Bluesky connector** — done (v2.1): open public search API (`app.bsky.feed.search_posts`), App Password auth, no approval process. Second live source alongside Mastodon.
4. **Background/async runs** — if post limits grow large enough that a run takes minutes, consider moving the collector off the main Streamlit thread so the UI stays responsive.
5. **Hosted deployment** — Streamlit Community Cloud, if/when the user wants this accessible outside their own laptop.

---

*This document reflects the codebase as of the v2 rebuild. Update it alongside the code — a design doc that drifts from the implementation is exactly the failure mode that caused v1's dashboard/database mismatch in the first place.*
