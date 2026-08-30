"""
GaneshStream AI — v2

A single Streamlit app (config manager + collector + dashboard used to be
three separate, mismatched pieces — see README for what changed and why).
"""
import os

import pandas as pd
import sqlite3
import streamlit as st
from dotenv import load_dotenv

from src.config import load_config, save_config, get_val
from src.connectors import LIVE_SOURCES
from src.database.manager import DB_PATH, TABLE_NAME
from src.orchestrator import ProjectOrchestrator
from src.analysis.engine import list_models, DEFAULT_MODEL

load_dotenv()

st.set_page_config(page_title="GaneshStream AI", page_icon="🚀", layout="wide")
st.title("🚀 GaneshStream AI")

if "config" not in st.session_state:
    st.session_state.config = load_config()

config = st.session_state.config

tab_settings, tab_run, tab_dashboard = st.tabs(["⚙️ Settings", "▶️ Run Collector", "📊 Dashboard"])

# ---------------------------------------------------------------------------
# Settings tab
# ---------------------------------------------------------------------------
with tab_settings:
    st.subheader("Analysis profile")

    all_sources = ["mastodon", "twitter", "facebook"]
    source = st.selectbox(
        "Source",
        all_sources,
        index=all_sources.index(get_val(config, "search_settings", "source", "mastodon")),
        format_func=lambda s: s.capitalize() if s in LIVE_SOURCES else f"{s.capitalize()} (coming soon)",
    )
    if source not in LIVE_SOURCES:
        st.info(f"{source.capitalize()} isn't built yet — see the roadmap in README.md. Pick Mastodon for now.")

    topic = st.text_input("Search topic / hashtag", value=get_val(config, "search_settings", "topic", "AI"))
    limit = st.slider("Posts limit", 1, 50, value=get_val(config, "search_settings", "limit", 10))
    sleep_time = st.number_input(
        "Throttle between AI calls (seconds)", min_value=1, value=get_val(config, "search_settings", "sleep_time", 12)
    )

    st.subheader("AI settings")

    col_model, col_refresh = st.columns([4, 1])
    with col_refresh:
        st.write("")  # vertical spacer to align button with selectbox
        refresh_clicked = st.button("🔄 Refresh", help="Re-fetch the current model list from Google")

    if "model_list" not in st.session_state or refresh_clicked:
        with st.spinner("Fetching available Gemini models..."):
            st.session_state.model_list = list_models(os.getenv("GEMINI_API_KEY", ""))

    model_list = st.session_state.model_list
    saved_model = get_val(config, "ai_settings", "model", DEFAULT_MODEL)
    if saved_model not in model_list:
        model_list = [saved_model] + model_list  # keep the saved choice selectable even if it's since disappeared

    with col_model:
        model = st.selectbox(
            "Gemini model",
            model_list,
            index=model_list.index(saved_model),
            help="Fetched live from the Gemini API, so this list always matches what's actually available right now.",
        )

    if not os.getenv("GEMINI_API_KEY"):
        st.caption("⚠️ Showing a fallback list — set GEMINI_API_KEY to fetch the live list.")

    if st.button("💾 Save settings", type="primary"):
        new_config = {
            "search_settings": {"source": source, "topic": topic, "limit": limit, "sleep_time": sleep_time},
            "ai_settings": {"model": model},
        }
        save_config(new_config)
        st.session_state.config = new_config
        st.success("Saved.")
        st.rerun()

# ---------------------------------------------------------------------------
# Run tab
# ---------------------------------------------------------------------------
with tab_run:
    st.subheader("Run the collector")
    st.caption("Uses the settings saved in the Settings tab.")

    active_source = get_val(config, "search_settings", "source", "mastodon")
    if active_source not in LIVE_SOURCES:
        st.warning(f"Source '{active_source}' isn't implemented yet. Change it in Settings.")
    elif not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY is not set. Add it to your .env file (see .env.example).")
    else:
        log_area = st.empty()
        log_lines = []

        def on_log(msg: str):
            log_lines.append(msg)
            log_area.code("\n".join(log_lines[-20:]), language="text")

        if st.button("▶️ Run now", type="primary"):
            try:
                orchestrator = ProjectOrchestrator(
                    source=active_source,
                    model_id=get_val(config, "ai_settings", "model", "gemini-2.0-flash"),
                )
                saved = orchestrator.run(
                    topic=get_val(config, "search_settings", "topic", "AI"),
                    limit=get_val(config, "search_settings", "limit", 10),
                    sleep_time=get_val(config, "search_settings", "sleep_time", 12),
                    on_log=on_log,
                )
                st.success(f"Finished — {saved} new post(s) saved.")
            except Exception as e:
                st.error(f"Run failed: {e}")

# ---------------------------------------------------------------------------
# Dashboard tab
# ---------------------------------------------------------------------------
with tab_dashboard:
    st.subheader("Sentiment dashboard")

    if not os.path.exists(DB_PATH):
        st.info("No data yet — run the collector first.")
    else:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME} ORDER BY timestamp DESC", conn)
        conn.close()

        if df.empty:
            st.info("No data yet — run the collector first.")
        else:
            topics = ["All topics"] + sorted(df["topic"].dropna().unique().tolist())
            selected = st.selectbox("Filter by topic", topics)
            display_df = df if selected == "All topics" else df[df["topic"] == selected]

            c1, c2, c3 = st.columns(3)
            c1.metric("Posts shown", len(display_df))
            c2.metric("Avg sentiment score", f"{display_df['sentiment_score'].mean():.2f}" if len(display_df) else "—")
            c3.metric("Topic", selected if selected != "All topics" else "Multiple")

            st.divider()
            st.dataframe(display_df, use_container_width=True)
