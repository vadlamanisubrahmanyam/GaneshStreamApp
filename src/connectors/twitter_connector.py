"""
Roadmap placeholder — not wired into the app yet.

When you're ready to add Twitter/X:
1. Implement TwitterConnector(BaseConnector) here, following the same
   pattern as MastodonConnector (fetch_posts returns List[SocialPost]).
2. Register it in src/connectors/__init__.py's REGISTRY dict.
3. It will automatically appear as a source option in app.py — no other
   changes needed.
"""
from typing import List

from .base import BaseConnector
from ..models import SocialPost


class TwitterConnector(BaseConnector):
    name = "twitter"

    def is_configured(self) -> bool:
        return False

    def fetch_posts(self, topic: str, limit: int = 10) -> List[SocialPost]:
        raise NotImplementedError("Twitter/X connector is not built yet.")
