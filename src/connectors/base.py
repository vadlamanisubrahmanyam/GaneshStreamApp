"""
Every source (Mastodon today; Twitter/X and Facebook later) implements this
interface. Adding a new source is: write a class, register it in REGISTRY
at the bottom of this package's __init__.py — nothing else in the app needs
to change.
"""
from abc import ABC, abstractmethod
from typing import List
from ..models import SocialPost


class BaseConnector(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_posts(self, topic: str, limit: int) -> List[SocialPost]:
        """Fetch up to `limit` recent posts matching `topic`."""
        raise NotImplementedError

    def is_configured(self) -> bool:
        """Return True if required credentials/env vars are present."""
        return True
