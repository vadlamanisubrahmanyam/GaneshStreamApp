"""
One-time migration: copies every row from `sentiment_results` in the OLD
(shared) Supabase project into the same table in a NEW (dedicated)
Supabase project. Safe to run more than once — it uses the same
ON CONFLICT (source, post_id) DO NOTHING dedup logic as the app itself,
so re-running it just skips rows already copied.

This script is completely independent of app.py / Streamlit, on purpose
— same reasoning as test_db_connection.py: fewer moving parts to debug
if something goes wrong.

Usage:
    python migrate_data.py

Reads two connection strings from environment variables (set them inline
or export them first — see step-by-step instructions):
    OLD_DATABASE_URL   — the shared project GaneshStream has been using
    NEW_DATABASE_URL   — the new, dedicated project for GaneshStream

It does NOT modify or delete anything in the old database — this is a
copy, not a move. Dropping the old table is a separate, manual step you
take only after confirming the new database looks correct.
"""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

OLD_DATABASE_URL = os.getenv("OLD_DATABASE_URL")
NEW_DATABASE_URL = os.getenv("NEW_DATABASE_URL")

TABLE_NAME = "sentiment_results"

CREATE_TABLE_SQL = f"""
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

INSERT_SQL = text(
    f"""
    INSERT INTO {TABLE_NAME}
        (post_id, run_id, topic, source, author, content, sentiment,
         sentiment_score, reasoning, language, post_timestamp, collected_at)
    VALUES
        (:post_id, :run_id, :topic, :source, :author, :content, :sentiment,
         :sentiment_score, :reasoning, :language, :post_timestamp, :collected_at)
    ON CONFLICT (source, post_id) DO NOTHING
    """
)


def main():
    if not OLD_DATABASE_URL or not NEW_DATABASE_URL:
        print("❌ Set both OLD_DATABASE_URL and NEW_DATABASE_URL (in .env or your shell) before running this.")
        sys.exit(1)

    print("Connecting to OLD (shared) database...")
    old_engine = create_engine(OLD_DATABASE_URL)
    print("Connecting to NEW (dedicated) database...")
    new_engine = create_engine(NEW_DATABASE_URL)

    # Make sure the destination table exists before copying into it.
    with new_engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))

    with old_engine.begin() as conn:
        try:
            rows = conn.execute(text(f"SELECT * FROM {TABLE_NAME}")).mappings().all()
        except Exception as e:
            print(f"❌ Couldn't read from the old database's {TABLE_NAME} table: {e}")
            print("   If the table genuinely doesn't exist there, there's nothing to migrate — you can skip this script.")
            sys.exit(1)

    print(f"Found {len(rows)} row(s) in the old database.")
    if not rows:
        print("Nothing to migrate.")
        return

    copied = 0
    skipped = 0
    with new_engine.begin() as conn:
        for row in rows:
            result = conn.execute(INSERT_SQL, dict(row))
            if result.rowcount > 0:
                copied += 1
            else:
                skipped += 1

    print(f"✅ Done. {copied} row(s) copied, {skipped} row(s) already present (skipped).")
    print("Nothing in the old database was changed or deleted.")


if __name__ == "__main__":
    main()
