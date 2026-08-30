import os
import re
from typing import List

from mastodon import Mastodon

from .base import BaseConnector
from ..models import SocialPost

_TAG_RE = re.compile(r"<.*?>")


class MastodonConnector(BaseConnector):
    name = "mastodon"

    def __init__(self):
        # v2 fix: the old code read MASTODON_ACCESS_TOKEN here but the
        # .env file defined MASTODON_TOKEN, so auth silently used None.
        # We now read both names so an old .env still works, but the
        # README and .env.example standardise on MASTODON_ACCESS_TOKEN.
        self.token = os.getenv("MASTODON_ACCESS_TOKEN") or os.getenv("MASTODON_TOKEN")
        self.api_base_url = os.getenv("MASTODON_API_BASE_URL", "https://mastodon.social")
        self.api = None
        if self.token:
            self.api = Mastodon(access_token=self.token, api_base_url=self.api_base_url)

    def is_configured(self) -> bool:
        return self.api is not None

    def _clean_html(self, raw_html: str) -> str:
        return _TAG_RE.sub("", raw_html or "")

    def fetch_posts(self, topic: str, limit: int = 10) -> List[SocialPost]:
        if not self.is_configured():
            raise RuntimeError(
                "Mastodon isn't configured. Set MASTODON_ACCESS_TOKEN in your .env file."
            )

        clean_topic = topic.lstrip("#").strip()
        results = self.api.timeline_hashtag(clean_topic, limit=limit)

        posts = []
        for status in results:
            posts.append(
                SocialPost(
                    id=str(status.id),
                    topic=topic,
                    content=self._clean_html(status.content),
                    author=status.account.username,
                    source=self.name,
                    timestamp=status.created_at,
                )
            )
        return posts
