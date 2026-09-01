# GaneshStream AI (v2)

A single-page Streamlit app that tracks a hashtag on Mastodon, runs each
post through Gemini for sentiment analysis, and shows the results in a
live dashboard — all in one place, all local, no paid services required.

## What changed from v1

The original build (three separate scripts) had a working pipeline but a
few pieces that were never actually wired together correctly:

| Problem | Fix in v2 |
|---|---|
| Dashboard read `data/stream_results.db` / table `sentiment_results`; the collector wrote `data/analysis_results.db` / table `posts` | One `DatabaseManager`, one path, one schema — imported everywhere |
| Mastodon connector read `MASTODON_ACCESS_TOKEN`; `.env` defined `MASTODON_TOKEN` | Standardised on `MASTODON_ACCESS_TOKEN` (old name still works as a fallback) |
| `topic` was passed to `SocialPost` but the model didn't declare that field, so Pydantic silently dropped it | `topic` is now a required field, stored and used for dashboard filtering |
| Reddit was referenced in the design docs and `requirements.txt` but never implemented | Implemented (read-only PRAW search across `r/all`) — but Reddit closed self-service API app creation in Nov 2025, so this connector is code-complete and untested against real traffic; see "About Reddit" below |
| Only one source (Mastodon) was ever usable | Bluesky added as a second live source — open public search API, no approval gate |
| Config manager, collector, and dashboard were 3 separate Streamlit/CLI processes talking over subprocess stdout (fragile, encoding issues) | Merged into one `app.py` with three tabs; collector runs in-process |
| Errors were swallowed by broad `try/except` blocks | Failures now surface in the UI log instead of a generic "Execution Error" |
| Gemini model was a hardcoded string (`gemini-2.0-flash`), which Google later retired, breaking every analysis with a 404 | Model is now a dropdown fetched live from `client.models.list()`, so it always matches what Google currently offers |

## Running it locally (step by step)

**1. Get the code**
```bash
git clone <your-new-repo-url>.git
cd GaneshStreamApp
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Set up your API keys**
```bash
cp .env.example .env
```
Open `.env` and fill in:
- `GEMINI_API_KEY` — free tier key from https://aistudio.google.com/apikey
- `MASTODON_ACCESS_TOKEN` — on your Mastodon instance: Settings → Development → New Application → copy the access token
- `MASTODON_API_BASE_URL` — defaults to `https://mastodon.social`; change if you use a different instance
- `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` — create an App Password in the Bluesky app under Settings → App Passwords (never your main password)
- `REDDIT_ID` / `REDDIT_SECRET` — optional, only if you already have approved Reddit API credentials (see "About Reddit" below)

Never commit `.env` — it's already in `.gitignore`.

**5. Run the app**
```bash
streamlit run app.py
```
This opens `http://localhost:8501` in your browser. Streamlit keeps running in that terminal — leave it open while you use the app, `Ctrl+C` to stop it.

**6. Use it**
- **Settings tab** — pick a topic/hashtag, post limit, throttle seconds, and a Gemini model from the dropdown (this list is fetched live from Google every time you open the tab or click Refresh — see "Why a dropdown, not a hardcoded model" below). Click **Save settings**.
- **Run Collector tab** — click **Run now**. A live log shows each post being fetched, analyzed, and saved.
- **Dashboard tab** — filter by topic, see average sentiment score and the full results table.

### Why a dropdown, not a hardcoded model name

The exact failure you hit (`gemini-2.0-flash` returning 404) is why the model
field is no longer a hardcoded string. `src/analysis/engine.py` calls
`client.models.list()` live against the Gemini API and only shows models
that currently support `generateContent`. When Google retires a model in
the future, the dropdown simply stops offering it — nothing in the code
needs to change. If you're offline or haven't set `GEMINI_API_KEY` yet, it
falls back to a short hardcoded list so the UI never breaks, with a warning
shown above the dropdown in that case.

## Deploying it

### Should you use Vercel?

Short answer: **no, not for this app.** Vercel is built around serverless
functions and frameworks like Next.js — each request spins up a short-lived
function and returns. Streamlit is the opposite: it's a single long-running
Python process that holds a persistent WebSocket connection to your
browser to push UI updates. That doesn't fit Vercel's execution model, and
you'd be fighting the platform rather than using it.

### What to use instead: Streamlit Community Cloud (free)

This is what Streamlit itself is built for, it's free, and it fits your
"no paid services" constraint from the FamilyCircle app too:

1. Push this repo to GitHub (public or private).
2. Go to https://streamlit.io/cloud and sign in with GitHub.
3. Click **Create app**, point it at your repo, branch, and `app.py`.
4. Under **Advanced settings → Secrets**, paste your `.env` contents in
   TOML format:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   MASTODON_ACCESS_TOKEN = "your-token-here"
   MASTODON_API_BASE_URL = "https://mastodon.social"
   BLUESKY_HANDLE = "your-handle.bsky.social"
   BLUESKY_APP_PASSWORD = "your-app-password"
   ```
   Streamlit Community Cloud exposes these as environment variables, so no
   code changes are needed — `os.getenv(...)` picks them up the same way.
5. Click **Deploy**. You get a public `*.streamlit.app` URL in a couple of
   minutes, and it redeploys automatically on every push to that branch.

**Free-tier limits worth knowing:** ~1 GB RAM, the app sleeps after about
12 hours with no traffic (auto-wakes on the next visit, just takes a few
seconds), and you get one private app for free — unlimited public ones.
For a personal sentiment-tracking tool run occasionally, this is more than
enough.

If you outgrow that later (need it always-on, more memory, background
jobs), Render and Railway both have free/low-cost tiers that run a
persistent Python process the same way Community Cloud does — same
deployment shape, just a different host. Vercel still wouldn't be the
right fit even then, since the constraint is architectural, not just
about free-tier limits.

## Roadmap

- [x] Mastodon connector + Gemini sentiment analysis + SQLite + dashboard
- [x] Bluesky connector (public search API, App Password auth — no approval gate)
- [x] Reddit connector — built (PRAW, `r/all` search), but **blocked by Reddit's
      own policy**, not by this code. See "About Reddit" below.
- [ ] Twitter/X connector (stub already in `src/connectors/twitter_connector.py`)
- [ ] Facebook connector — note: Graph API's public search is much more
      restricted than Mastodon/Twitter; check current Meta Graph API terms
      before building this one

### About Reddit

Reddit introduced a "Responsible Builder Policy" in November 2025 that
closed self-service OAuth app creation. `reddit.com/prefs/apps` no longer
reliably issues new credentials for new developers, and new API access now
requires manual approval that's rarely granted for personal or script use.

`src/connectors/reddit_connector.py` is fully implemented and will work
immediately if you already hold approved credentials, or if Reddit reopens
self-service access in the future — but it's deliberately left out of
`LIVE_SOURCES` in `src/connectors/__init__.py` so the Settings tab doesn't
offer a source that will just fail for almost everyone. Check
https://support.reddithelp.com for the current policy before re-enabling it.

### Adding a new source later

1. Create `src/connectors/<name>_connector.py` implementing `BaseConnector`
   (see `mastodon_connector.py` for the pattern).
2. Add it to `REGISTRY` in `src/connectors/__init__.py` and to
   `LIVE_SOURCES` once it's working.
3. It will automatically show up as a selectable source in the Settings tab.

## Project structure

```
GaneshStreamApp/
├── app.py                        # single Streamlit app (Settings / Run / Dashboard)
├── requirements.txt
├── .env.example
├── config/
│   └── search_config.yaml        # written by the app, not committed
├── data/
│   └── stream_results.db         # SQLite, not committed
└── src/
    ├── config.py                 # load/save settings
    ├── models.py                 # SocialPost, SentimentResult
    ├── orchestrator.py           # fetch -> dedupe -> analyze -> save
    ├── connectors/
    │   ├── base.py
    │   ├── mastodon_connector.py
    │   ├── bluesky_connector.py
    │   ├── reddit_connector.py    # built, gated by Reddit policy — see README
    │   ├── twitter_connector.py  # stub
    │   └── facebook_connector.py # stub
    ├── analysis/
    │   └── engine.py             # Gemini sentiment analysis
    └── database/
        └── manager.py            # SQLite persistence
```
