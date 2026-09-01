from .mastodon_connector import MastodonConnector
from .bluesky_connector import BlueskyConnector
from .reddit_connector import RedditConnector
from .twitter_connector import TwitterConnector
from .facebook_connector import FacebookConnector

# Add a source here once its connector is actually implemented and you want
# it selectable in the app. Twitter/Facebook are left in on purpose so the
# UI can show them as "coming soon" without any other code changes.
REGISTRY = {
    "mastodon": MastodonConnector,
    "bluesky": BlueskyConnector,
    "reddit": RedditConnector,
    "twitter": TwitterConnector,
    "facebook": FacebookConnector,
}

# Sources that are actually usable today.
# Reddit's connector is fully implemented but NOT listed here: since Nov
# 2025 Reddit's "Responsible Builder Policy" closed self-service OAuth app
# creation, so new credentials are effectively unobtainable for a personal
# script. If that ever changes, moving "reddit" into this list is the only
# change needed.
LIVE_SOURCES = ["mastodon", "bluesky"]
