"""
Single source of truth for user-editable settings.

Kept as a small YAML file (not committed to git — see .gitignore) so the
Streamlit app and the orchestrator always agree on the same values without
threading arguments through five layers of function calls.
"""
import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "search_config.yaml")

DEFAULTS = {
    "search_settings": {
        "source": "mastodon",
        "topic": "AI",
        "limit": 10,
        "sleep_time": 12,
    },
    "ai_settings": {
        "model": "gemini-2.5-flash",
    },
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return DEFAULTS.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        # Merge over defaults so a partial/old config file never crashes the app
        merged = {**DEFAULTS, **loaded}
        merged["search_settings"] = {**DEFAULTS["search_settings"], **loaded.get("search_settings", {})}
        merged["ai_settings"] = {**DEFAULTS["ai_settings"], **loaded.get("ai_settings", {})}
        return merged
    except Exception:
        return DEFAULTS.copy()


def save_config(config: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_val(config: dict, section: str, key: str, default=None):
    try:
        return config[section][key]
    except (KeyError, TypeError):
        return default
