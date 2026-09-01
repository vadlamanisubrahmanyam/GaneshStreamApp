import os
from datetime import datetime, timezone
from typing import List

import praw
import prawcore

from .base import BaseConnector
from ..models import SocialPost


class RedditConnector(BaseConnector):
    """
    Read-only Reddit search across r/all. Uses PRAW in "script, read-only"
    mode — only needs a client ID + secret (from
    https://www.reddit.com/prefs/apps, app type "script"), no Reddit
    username/password.

    NOTE: since November 2025, Reddit's "Responsible Builder Policy" closed
    self-service OAuth app creation — /prefs/apps no longer reliably issues
    new credentials, and new API access now requires manual approval that's
    rarely granted for personal/script use. This connector is fully
    implemented and will work immediately for anyone who already has valid
    credentials (or if Reddit reopens self-service access), but it's kept
    out of LIVE_SOURCES in __init__.py for that reason. Check
    https://support.reddithelp.com for the current policy before assuming
    this has changed.
    """

    name = "reddit"

    def __init__(self):
        self.client_id = os.getenv("REDDIT_ID")
        self.client_secret = os.getenv("REDDIT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "GaneshStreamAI/1.0")
        self.api = None
        if self.client_id and self.client_secret:
            self.api = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
            self.api.read_only = True

    def is_configured(self) -> bool:
        return self.api is not None

    def fetch_posts(self, topic: str, limit: int = 10) -> List[SocialPost]:
        if not self.is_configured():
            raise RuntimeError(
                "Reddit isn't configured. Set REDDIT_ID and REDDIT_SECRET in your .env file "
                "(create a 'script' app at https://www.reddit.com/prefs/apps)."
            )

        clean_topic = topic.lstrip("#").strip()

        try:
            results = self.api.subreddit("all").search(clean_topic, sort="new", limit=limit)
            submissions = list(results)
        except prawcore.exceptions.ResponseException as e:
            raise RuntimeError(f"Reddit API rejected the request ({e}). Check your credentials.") from e
        except prawcore.exceptions.RequestException as e:
            raise RuntimeError(f"Couldn't reach Reddit: {e}") from e

        posts = []
        for submission in submissions:
            author = str(submission.author) if submission.author else "[deleted]"
            body = submission.selftext.strip() if submission.selftext else ""
            content = f"{submission.title}\n\n{body}".strip() if body else submission.title

            posts.append(
                SocialPost(
                    id=submission.id,
                    topic=topic,
                    content=content,
                    author=author,
                    source=self.name,
                    timestamp=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                )
            )
        return posts
