"""
Data models shared across the app.

v2 fix: the old SocialPost model had no `topic` field, so it was silently
dropped by Pydantic every time a connector set it — which is part of why
the dashboard could never filter by topic. `topic` is now a first-class,
required field.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SocialPost(BaseModel):
    id: str
    topic: str
    content: str
    author: str
    source: str  # "mastodon", "twitter", "facebook", ...
    timestamp: datetime


class SentimentResult(BaseModel):
    sentiment: str
    score: float
    reasoning: str
    language: str
