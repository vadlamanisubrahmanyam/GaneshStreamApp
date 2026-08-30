"""
Roadmap placeholder — not wired into the app yet.

Note: Facebook's Graph API has much tighter restrictions on public content
search than Mastodon/Twitter — you'll likely need an approved app + a
specific Page's own content rather than open keyword search. Worth
checking Meta's current Graph API terms before building this one.

Same pattern as twitter_connector.py: implement, register in
src/connectors/__init__.py's REGISTRY, done.
"""
from typing import List

from .base import BaseConnector
from ..models import SocialPost


class FacebookConnector(BaseConnector):
    name = "facebook"

    def is_configured(self) -> bool:
        return False

    def fetch_posts(self, topic: str, limit: int = 10) -> List[SocialPost]:
        raise NotImplementedError("Facebook connector is not built yet.")
