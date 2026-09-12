"""
GaneshStream AI — v2.2

A single Streamlit app: Settings, Run Collector, Latest Run, and Historic
Feed (all runs, ever — see README for why storage moved to Postgres to
make that tab meaningful).
"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

from src.config import load_config, save_config, get_val
from src.connectors import LIVE_SOURCES
from src.database.manager import DatabaseManager, TABLE_NAME
from src.orchestrator import ProjectOrchestrator
from src.analysis.engine import list_models, DEFAULT_MODEL
from src.language_names import language_display_name

load_dotenv()

st.set_page_config(page_title="GaneshStream AI", page_icon="🚀", layout="wide")
st.title("🚀 GaneshStream AI")

if "config" not in st.session_state:
    st.session_state.config = load_config()

config = st.session_state.config

# Consistent color encoding for sentiment across every chart in the app —
# a dashboard where "green" means something different on each chart is a
# classic usability mistake.
SENTIMENT_COLORS = {
    "Positive": "#2E7D32",
    "Negative": "#C62828",
    "Neutral": "#757575",
    "Unknown": "#BDBDBD",
}


@st.cache_resource(show_spinner="Connecting to database...")
def get_db():
    return DatabaseManager()


def load_dataframe(db: DatabaseManager, query: str, params: dict = None) -> pd.DataFrame:
    with db.engine.begin() as conn:
        df = pd.read_sql(text(query), conn, params=params or {})
    if not df.empty:
        df["post_timestamp"] = pd.to_datetime(df["post_timestamp"], utc=True)
        df["collected_at"] = pd.to_datetime(df["collected_at"], utc=True)
    return df


tab_settings, tab_run, tab_latest, tab_historic = st.tabs(
    ["⚙️ Settings", "▶️ Run Collector", "📍 Latest Run", "📚 Historic Feed"]
)

# ---------------------------------------------------------------------------
# Settings tab
# ---------------------------------------------------------------------------
with tab_settings:
    st.subheader("Analysis profile")

    all_sources = ["mastodon", "bluesky", "reddit", "twitter", "facebook"]
    SOURCE_LABELS = {
        "reddit": "Reddit (blocked — Reddit's Responsible Builder Policy)",
    }
    source = st.selectbox(
        "Source",
        all_sources,
        index=all_sources.index(get_val(config, "search_settings", "source", "mastodon")),
        format_func=lambda s: s.capitalize() if s in LIVE_SOURCES else SOURCE_LABELS.get(s, f"{s.capitalize()} (coming soon)"),
    )
    if source == "reddit":
        st.warning(
            "Reddit closed self-service API app creation in Nov 2025. The connector code "
            "is ready (`src/connectors/reddit_connector.py`) but needs approved credentials, "
            "which Reddit rarely grants for personal use. Pick Mastodon or Bluesky for now."
        )
    elif source not in LIVE_SOURCES:
        st.info(f"{source.capitalize()} isn't built yet — see the roadmap in README.md. Pick Mastodon or Bluesky for now.")

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

    st.divider()
    st.subheader("Database")
    if st.button("🔌 Test database connection"):
        try:
            test_db = get_db()
            test_db.has_data()
            st.success("Connected to Postgres successfully.")
        except Exception as e:
            st.error(f"Couldn't connect: {e}")

# ---------------------------------------------------------------------------
# Run tab
# ---------------------------------------------------------------------------
with tab_run:
    st.subheader("Run the collector")
    st.caption("Uses the settings saved in the Settings tab. Profanity in fetched content is automatically masked before analysis or storage.")

    active_source = get_val(config, "search_settings", "source", "mastodon")
    if active_source not in LIVE_SOURCES:
        st.warning(f"Source '{active_source}' isn't implemented yet. Change it in Settings.")
    elif not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY is not set. Add it to your .env file (see .env.example).")
    elif not os.getenv("DATABASE_URL"):
        st.error("DATABASE_URL is not set. Add your Supabase connection string to your .env file (see README).")
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
                    model_id=get_val(config, "ai_settings", "model", DEFAULT_MODEL),
                )
                saved, run_id = orchestrator.run(
                    topic=get_val(config, "search_settings", "topic", "AI"),
                    limit=get_val(config, "search_settings", "limit", 10),
                    sleep_time=get_val(config, "search_settings", "sleep_time", 12),
                    on_log=on_log,
                )
                st.success(f"Finished — {saved} new post(s) saved. Check the Latest Run tab.")
            except Exception as e:
                st.error(f"Run failed: {e}")

# ---------------------------------------------------------------------------
# Latest Run tab — only the most recently collected run
# ---------------------------------------------------------------------------
with tab_latest:
    st.subheader("Latest run")

    try:
        db = get_db()
    except Exception as e:
        st.error(f"Database not configured: {e}")
        db = None

    if db is not None:
        latest_run_id = db.latest_run_id()
        if not latest_run_id:
            st.info("No data yet — run the collector first.")
        else:
            df = load_dataframe(
                db,
                f"SELECT * FROM {TABLE_NAME} WHERE run_id = :run_id ORDER BY collected_at DESC",
                {"run_id": latest_run_id},
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Posts in this run", len(df))
            c2.metric("Avg sentiment score", f"{df['sentiment_score'].mean():.2f}" if len(df) else "—")
            c3.metric("Topic(s)", ", ".join(df["topic"].dropna().unique().tolist()) if len(df) else "—")
            st.caption(f"Run ID: `{latest_run_id}`")
            st.divider()
            if len(df):
                df["language"] = df["language"].apply(language_display_name)
            st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------------------------
# Historic Feed tab — everything, ever, with filters + charts
# ---------------------------------------------------------------------------
with tab_historic:
    st.subheader("Historic feed — all runs")

    try:
        db = get_db()
    except Exception as e:
        st.error(f"Database not configured: {e}")
        db = None

    if db is not None:
        full_df = load_dataframe(db, f"SELECT * FROM {TABLE_NAME} ORDER BY collected_at DESC")

        if full_df.empty:
            st.info("No data yet — run the collector at least once.")
        else:
            # --- Slice-and-dice filters ---
            with st.expander("🔎 Filters", expanded=True):
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    topics_sel = st.multiselect(
                        "Topic", sorted(full_df["topic"].dropna().unique().tolist())
                    )
                with fc2:
                    sources_sel = st.multiselect(
                        "Source", sorted(full_df["source"].dropna().unique().tolist())
                    )
                with fc3:
                    sentiments_sel = st.multiselect(
                        "Sentiment", sorted(full_df["sentiment"].dropna().unique().tolist())
                    )

                min_date = full_df["collected_at"].min().date()
                max_date = full_df["collected_at"].max().date()
                date_range = st.date_input(
                    "Collected between",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                )
                search_text = st.text_input("Search content or author contains")

            filtered = full_df.copy()
            if topics_sel:
                filtered = filtered[filtered["topic"].isin(topics_sel)]
            if sources_sel:
                filtered = filtered[filtered["source"].isin(sources_sel)]
            if sentiments_sel:
                filtered = filtered[filtered["sentiment"].isin(sentiments_sel)]
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_d, end_d = date_range
                filtered = filtered[
                    (filtered["collected_at"].dt.date >= start_d) & (filtered["collected_at"].dt.date <= end_d)
                ]
            if search_text:
                mask = (
                    filtered["content"].str.contains(search_text, case=False, na=False)
                    | filtered["author"].str.contains(search_text, case=False, na=False)
                )
                filtered = filtered[mask]

            if filtered.empty:
                st.warning("No rows match the current filters.")
            else:
                # --- Summary metrics ---
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Posts", len(filtered))
                m2.metric("Runs represented", filtered["run_id"].nunique())
                m3.metric("Topics", filtered["topic"].nunique())
                m4.metric("Avg sentiment score", f"{filtered['sentiment_score'].mean():.2f}")

                st.divider()

                # --- Charts ---
                row1c1, row1c2 = st.columns(2)
                with row1c1:
                    sentiment_counts = filtered["sentiment"].value_counts().reset_index()
                    sentiment_counts.columns = ["sentiment", "count"]
                    fig_pie = px.pie(
                        sentiment_counts,
                        names="sentiment",
                        values="count",
                        color="sentiment",
                        color_discrete_map=SENTIMENT_COLORS,
                        hole=0.45,
                        title="Sentiment distribution",
                    )
                    fig_pie.update_traces(textinfo="label+percent")
                    st.plotly_chart(fig_pie, use_container_width=True)

                with row1c2:
                    by_source = filtered.groupby(["source", "sentiment"]).size().reset_index(name="count")
                    fig_source = px.bar(
                        by_source,
                        x="source",
                        y="count",
                        color="sentiment",
                        color_discrete_map=SENTIMENT_COLORS,
                        barmode="stack",
                        title="Volume by source (stacked by sentiment)",
                    )
                    st.plotly_chart(fig_source, use_container_width=True)

                trend = filtered.copy()
                trend["date"] = trend["collected_at"].dt.date
                trend_grouped = trend.groupby(["date", "topic"])["sentiment_score"].mean().reset_index()
                fig_trend = px.line(
                    trend_grouped,
                    x="date",
                    y="sentiment_score",
                    color="topic",
                    markers=True,
                    title="Average sentiment score over time, by topic",
                )
                fig_trend.update_yaxes(range=[-1, 1], title="Avg. sentiment score")
                st.plotly_chart(fig_trend, use_container_width=True)

                row2c1, row2c2 = st.columns(2)
                with row2c1:
                    by_topic = (
                        filtered.groupby("topic")["sentiment_score"]
                        .mean()
                        .reset_index()
                        .sort_values("sentiment_score", ascending=True)
                    )
                    fig_topic = px.bar(
                        by_topic,
                        x="sentiment_score",
                        y="topic",
                        orientation="h",
                        title="Average sentiment score by topic",
                    )
                    fig_topic.update_xaxes(range=[-1, 1])
                    st.plotly_chart(fig_topic, use_container_width=True)

                with row2c2:
                    fig_hist = px.histogram(
                        filtered,
                        x="sentiment_score",
                        nbins=20,
                        title="Sentiment score distribution",
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)

                st.divider()
                display_df = filtered.copy()
                display_df["language"] = display_df["language"].apply(language_display_name)
                st.dataframe(display_df, use_container_width=True)
                st.download_button(
                    "⬇️ Download filtered data as CSV",
                    filtered.to_csv(index=False).encode("utf-8"),
                    file_name="ganeshstream_historic_feed.csv",
                    mime="text/csv",
                )
