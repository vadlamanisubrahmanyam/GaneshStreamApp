import os
from datetime import datetime
from typing import List

from atproto import Client
from atproto_client.exceptions import AtProtocolError

from .base import BaseConnector
from ..models import SocialPost


class BlueskyConnector(BaseConnector):
    """
    Bluesky's public search (app.bsky.feed.search_posts) is open — no app
    review or approval queue, unlike Reddit's post-Nov-2025 "Responsible
    Builder Policy" gate. Auth is just a handle + an App Password (create
    one at Settings -> App Passwords in the Bluesky app — never use your
    main account password here).
    """

    name = "bluesky"

    def __init__(self):
        self.handle = os.getenv("BLUESKY_HANDLE")
        self.app_password = os.getenv("BLUESKY_APP_PASSWORD")
        self.client = None
        if self.handle and self.app_password:
            self.client = Client()

    def is_configured(self) -> bool:
        return self.client is not None

    def _ensure_logged_in(self):
        # Session tokens are short-lived; log in fresh for each run rather
        # than trying to manage refresh tokens for a low-frequency script.
        self.client.login(self.handle, self.app_password)

    def fetch_posts(self, topic: str, limit: int = 10) -> List[SocialPost]:
        if not self.is_configured():
            raise RuntimeError(
                "Bluesky isn't configured. Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD "
                "in your .env file (create an App Password in the Bluesky app under "
                "Settings -> App Passwords)."
            )

        clean_topic = topic.lstrip("#").strip()

        try:
            self._ensure_logged_in()
            response = self.client.app.bsky.feed.search_posts(
                params={"q": clean_topic, "limit": limit, "sort": "latest"}
            )
        except AtProtocolError as e:
            raise RuntimeError(f"Bluesky API error: {e}") from e

        posts = []
        for item in response.posts:
            record = item.record
            author_handle = item.author.handle if item.author else "unknown"
            created_at = record.created_at
            try:
                timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now()

            posts.append(
                SocialPost(
                    id=item.uri,
                    topic=topic,
                    content=record.text,
                    author=author_handle,
                    source=self.name,
                    timestamp=timestamp,
                )
            )
        return posts
