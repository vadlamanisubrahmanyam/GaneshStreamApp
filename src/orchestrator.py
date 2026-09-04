import time
from typing import Callable, Optional

from .analysis.engine import AnalysisEngine
from .connectors import REGISTRY
from .database.manager import DatabaseManager, new_run_id
from .moderation import clean_text


class ProjectOrchestrator:
    """
    v2 change: runs in-process instead of being launched as a subprocess
    from Streamlit. The old subprocess approach existed mainly to work
    around console encoding errors on Windows; running in-process removes
    that whole class of bug and lets the UI show live progress via a
    plain callback instead of parsing subprocess stdout.
    """

    def __init__(self, source: str, model_id: str):
        if source not in REGISTRY:
            raise ValueError(f"Unknown source: {source}")
        self.connector = REGISTRY[source]()
        self.db = DatabaseManager()
        self.ai_brain = AnalysisEngine(model_id=model_id)

    def run(
        self,
        topic: str,
        limit: int,
        sleep_time: float,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str]:
        """Returns (number of newly-saved posts, run_id for this run)."""
        log = on_log or (lambda msg: None)
        run_id = new_run_id()

        if not self.connector.is_configured():
            raise RuntimeError(
                f"'{self.connector.name}' isn't configured — check its credentials in .env."
            )

        log(f"Searching {self.connector.name} for #{topic} (limit {limit})...")
        posts = self.connector.fetch_posts(topic, limit)
        log(f"Fetched {len(posts)} post(s).")

        saved = 0
        for i, post in enumerate(posts, start=1):
            if self.db.is_duplicate(post.id, post.source):
                log(f"[{i}/{len(posts)}] Skipping @{post.author} — already analyzed.")
                continue

            # Mask profanity in the content before it's analyzed or stored,
            # so nothing offensive ever lands in the database or dashboard.
            post.content = clean_text(post.content)

            try:
                analysis = self.ai_brain.analyze_content(post.content)
            except Exception as e:
                log(f"[{i}/{len(posts)}] ⚠️ Analysis failed for @{post.author}: {e}")
                continue

            self.db.save_analysis(post, analysis, run_id=run_id)
            saved += 1
            log(
                f"[{i}/{len(posts)}] ✅ @{post.author} — {analysis.get('sentiment')} "
                f"({analysis.get('score')})"
            )

            if i < len(posts):
                time.sleep(sleep_time)

        log(f"Done. {saved} new post(s) saved. (run_id: {run_id})")
        return saved, run_id
