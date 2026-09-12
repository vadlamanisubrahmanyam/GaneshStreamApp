"""
Expands ISO 639-1 language codes (as returned by Gemini per the rubric in
src/analysis/engine.py) into full, readable names for display — "en"
becomes "English", "zh" becomes "Chinese", etc. The underlying stored
value stays as the short code; this only affects what's shown in the UI.
"""
from functools import lru_cache

import pycountry


@lru_cache(maxsize=256)
def language_display_name(code: str) -> str:
    """
    Returns a human-readable language name for an ISO 639-1 code.
    Falls back to returning the original value unchanged if it isn't a
    recognized code (e.g. Gemini's own "unknown", or anything unexpected) —
    so this never hides or errors on a value it doesn't recognize.
    """
    if not code:
        return "Unknown"
    try:
        lang = pycountry.languages.get(alpha_2=code.lower())
        if lang:
            return lang.name
    except (LookupError, AttributeError):
        pass
    return code.capitalize() if code.islower() else code
