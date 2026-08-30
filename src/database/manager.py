import os
import sqlite3

from ..models import SocialPost

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "stream_results.db")
TABLE_NAME = "sentiment_results"


class DatabaseManager:
    """
    v2 fix: the old app had the collector write to data/analysis_results.db
    (table `posts`) while the dashboard read from data/stream_results.db
    (table `sentiment_results`) — two different files that never talked to
    each other. There is now exactly one DB path and one schema, defined
    once here, imported everywhere else (including app.py's dashboard tab).
    """

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id TEXT PRIMARY KEY,
                topic TEXT,
                source TEXT,
                author TEXT,
                content TEXT,
                sentiment TEXT,
                sentiment_score REAL,
                reasoning TEXT,
                language TEXT,
                timestamp DATETIME
            )
            """
        )
        self.conn.commit()

    def is_duplicate(self, post_id: str) -> bool:
        cursor = self.conn.execute(f"SELECT 1 FROM {TABLE_NAME} WHERE id = ?", (post_id,))
        return cursor.fetchone() is not None

    def save_analysis(self, post: SocialPost, analysis: dict):
        query = f"""
            INSERT INTO {TABLE_NAME}
                (id, topic, source, author, content, sentiment, sentiment_score, reasoning, language, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        data = (
            post.id,
            post.topic,
            post.source,
            post.author,
            post.content,
            analysis.get("sentiment", "Unknown"),
            analysis.get("score", 0.0),
            analysis.get("reasoning", "N/A"),
            analysis.get("language", "Unknown"),
            post.timestamp.isoformat(),
        )
        try:
            self.conn.execute(query, data)
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.rollback()
