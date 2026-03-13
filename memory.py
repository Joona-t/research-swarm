"""Research Swarm — Simplified G-Memory (SQLite only, no Redis/LanceDB)."""

import json
import sqlite3
import time
import uuid
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    date TEXT NOT NULL,
    actionability REAL DEFAULT 0,
    status TEXT DEFAULT 'pending',
    insight TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS techniques (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    source TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    applicable_to TEXT DEFAULT '',
    tried INTEGER DEFAULT 0,
    worked INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    supporting_runs TEXT DEFAULT '[]',
    access_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);
"""


class ResearchMemory:
    """Simplified G-Memory for research swarm. SQLite only."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._db = None

    def initialize(self):
        """Create database and apply schema."""
        self._db = sqlite3.connect(str(self.db_path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(SCHEMA)

    def close(self):
        if self._db:
            self._db.close()

    # ------------------------------------------------------------------
    # Research runs
    # ------------------------------------------------------------------

    def log_run(self, topic: str, actionability: float, status: str,
                insight: str = "") -> str:
        """Log a completed research run."""
        run_id = str(uuid.uuid4())
        now = time.time()
        date = time.strftime("%Y-%m-%d")

        with self._db:
            self._db.execute(
                "INSERT INTO research_runs VALUES (?,?,?,?,?,?,?)",
                (run_id, topic, date, actionability, status, insight, now),
            )
        return run_id

    # ------------------------------------------------------------------
    # Techniques
    # ------------------------------------------------------------------

    def store_technique(self, name: str, description: str = "",
                        source: str = "", domain: str = "",
                        applicable_to: str = ""):
        """Store a discovered technique."""
        tech_id = str(uuid.uuid4())
        now = time.time()

        with self._db:
            # Check for duplicate by name
            existing = self._db.execute(
                "SELECT id FROM techniques WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                return existing[0]

            self._db.execute(
                "INSERT INTO techniques VALUES (?,?,?,?,?,?,0,0,?)",
                (tech_id, name, description, source, domain, applicable_to, now),
            )
        return tech_id

    # ------------------------------------------------------------------
    # Insights
    # ------------------------------------------------------------------

    def store_insight(self, content: str, run_id: str = ""):
        """Store a research insight."""
        insight_id = str(uuid.uuid4())
        supporting = json.dumps([run_id] if run_id else [])
        now = time.time()

        with self._db:
            self._db.execute(
                "INSERT INTO insights VALUES (?,?,?,0,?)",
                (insight_id, content, supporting, now),
            )
        return insight_id

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_relevant_insights(self, topic: str, limit: int = 5) -> list[dict]:
        """Get insights that might be relevant to a topic.

        Simple keyword matching — no embeddings. Good enough for <100 insights.
        """
        if not self._db:
            return []

        rows = self._db.execute(
            "SELECT id, content, access_count FROM insights ORDER BY access_count DESC"
        ).fetchall()

        # Simple relevance: check if any topic words appear in insight
        topic_words = set(topic.lower().split())
        scored = []
        for row_id, content, access_count in rows:
            content_words = set(content.lower().split())
            overlap = len(topic_words & content_words)
            if overlap > 0:
                scored.append({
                    "id": row_id,
                    "content": content,
                    "relevance": overlap / max(len(topic_words), 1),
                })

        scored.sort(key=lambda x: x["relevance"], reverse=True)

        # Update access counts
        for item in scored[:limit]:
            self._db.execute(
                "UPDATE insights SET access_count = access_count + 1 WHERE id = ?",
                (item["id"],),
            )
        self._db.commit()

        return scored[:limit]

    def get_relevant_techniques(self, topic: str, limit: int = 10) -> list[dict]:
        """Get techniques that might be relevant."""
        if not self._db:
            return []

        rows = self._db.execute(
            "SELECT name, description, domain, tried, worked FROM techniques"
        ).fetchall()

        topic_lower = topic.lower()
        results = []
        for name, desc, domain, tried, worked in rows:
            searchable = f"{name} {desc} {domain}".lower()
            if any(w in searchable for w in topic_lower.split()):
                results.append({
                    "name": name,
                    "description": desc,
                    "domain": domain,
                    "tried": bool(tried),
                    "worked": bool(worked),
                })

        return results[:limit]

    def build_memory_context(self, topic: str) -> str:
        """Build a context string from memory for injection into agent prompts."""
        insights = self.get_relevant_insights(topic)
        techniques = self.get_relevant_techniques(topic)

        if not insights and not techniques:
            return ""

        sections = []

        if insights:
            sections.append("### Historical Insights")
            for i in insights:
                sections.append(f"- {i['content']}")

        if techniques:
            sections.append("\n### Known Techniques")
            for t in techniques:
                status = ""
                if t["tried"]:
                    status = " (tried, worked)" if t["worked"] else " (tried, didn't work)"
                sections.append(f"- **{t['name']}**: {t['description']}{status}")

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        if not self._db:
            return {"runs": 0, "techniques": 0, "insights": 0}

        counts = {}
        for table in ("research_runs", "techniques", "insights"):
            row = self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0] if row else 0
        return counts
