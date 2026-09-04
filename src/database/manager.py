"""
v2.2 change: SQLite -> Supabase Postgres.

Streamlit Community Cloud's local disk isn't guaranteed to persist (their
own docs: "the platform may delete data stored using this technique at any
time" — redeploys, restarts, and sleep/wake cycles can all wipe a local
SQLite file). A "historic feed across all runs" feature is only meaningful
against storage that actually survives those events, so this now points at
a real Postgres database instead of a file on the app's own disk.

Every row is tagged with a `run_id` (one UUID per orchestrator.run() call)
so the app can tell "this run" apart from "all history" without needing
any session state — it's a property of the data itself.
"""
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..models import SocialPost

TABLE_NAME = "sentiment_results"

_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    row_id SERIAL PRIMARY KEY,
    post_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    topic TEXT,
    source TEXT,
    author TEXT,
    content TEXT,
    sentiment TEXT,
    sentiment_score REAL,
    reasoning TEXT,
    language TEXT,
    post_timestamp TIMESTAMPTZ,
    collected_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source, post_id)
)
"""


def new_run_id() -> str:
    return str(uuid.uuid4())


class DatabaseManager:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL not set. Add your Supabase Postgres connection string "
                "(Session Pooler, port 5432 — see README) to your .env file or "
                "Streamlit secrets."
            )
        self.engine: Engine = create_engine(self.database_url, pool_pre_ping=True)
        self._create_table()

    def _create_table(self):
        with self.engine.begin() as conn:
            conn.execute(text(_CREATE_TABLE_SQL))

    def is_duplicate(self, post_id: str, source: str) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(
                text(f"SELECT 1 FROM {TABLE_NAME} WHERE post_id = :pid AND source = :src"),
                {"pid": post_id, "src": source},
            ).fetchone()
        return row is not None

    def save_analysis(self, post: SocialPost, analysis: dict, run_id: str):
        query = text(
            f"""
            INSERT INTO {TABLE_NAME}
                (post_id, run_id, topic, source, author, content, sentiment,
                 sentiment_score, reasoning, language, post_timestamp)
            VALUES
                (:post_id, :run_id, :topic, :source, :author, :content, :sentiment,
                 :sentiment_score, :reasoning, :language, :post_timestamp)
            ON CONFLICT (source, post_id) DO NOTHING
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                query,
                {
                    "post_id": post.id,
                    "run_id": run_id,
                    "topic": post.topic,
                    "source": post.source,
                    "author": post.author,
                    "content": post.content,
                    "sentiment": analysis.get("sentiment", "Unknown"),
                    "sentiment_score": analysis.get("score", 0.0),
                    "reasoning": analysis.get("reasoning", "N/A"),
                    "language": analysis.get("language", "Unknown"),
                    "post_timestamp": post.timestamp,
                },
            )

    def latest_run_id(self):
        """The most recently collected run, across all sources/topics."""
        with self.engine.begin() as conn:
            row = conn.execute(
                text(f"SELECT run_id FROM {TABLE_NAME} ORDER BY collected_at DESC LIMIT 1")
            ).fetchone()
        return row[0] if row else None

    def has_data(self) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(text(f"SELECT 1 FROM {TABLE_NAME} LIMIT 1")).fetchone()
        return row is not None
