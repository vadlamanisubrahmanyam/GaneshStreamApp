from .mastodon_connector import MastodonConnector
from .twitter_connector import TwitterConnector
from .facebook_connector import FacebookConnector

# Add a source here once its connector is actually implemented and you want
# it selectable in the app. Twitter/Facebook are left in on purpose so the
# UI can show them as "coming soon" without any other code changes.
REGISTRY = {
    "mastodon": MastodonConnector,
    "twitter": TwitterConnector,
    "facebook": FacebookConnector,
}

# Sources that are actually usable today.
LIVE_SOURCES = ["mastodon"]
