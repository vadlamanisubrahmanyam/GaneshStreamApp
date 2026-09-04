"""
Masks profanity in fetched post content before it's analyzed or stored.
Uses a local wordlist (better-profanity) — no external API call, no extra
cost or latency, works offline.
"""
from better_profanity import profanity

_loaded = False


def _ensure_loaded():
    global _loaded
    if not _loaded:
        profanity.load_censor_words()
        _loaded = True


def clean_text(text: str) -> str:
    """Replace profane words with asterisks, preserving everything else."""
    if not text:
        return text
    _ensure_loaded()
    return profanity.censor(text)
