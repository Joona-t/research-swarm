"""Research Swarm — G-Memory with decay scoring, temporal validity, and insight promotion.

Applies findings from our own first research run:
- Memory decay scoring: recency * access_frequency * relevance (exponential decay)
- Temporal validity: techniques have valid_from/valid_until, invalidated not deleted
- Three-tier hierarchy: raw runs → structured techniques → distilled insights
- Insight promotion: after threshold, compress related insights into meta-insights
"""

import json
import math
import sqlite3
import time
import uuid
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "memory.db"

# Defaults — can be overridden per-instance from config.toml
DEFAULT_DECAY_LAMBDA = 0.01
DEFAULT_PROMOTION_THRESHOLD = 5
DEFAULT_MAX_TECHNIQUE_AGE = 60 * 60 * 24 * 90  # 90 days

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
    valid_from REAL NOT NULL,
    valid_until REAL DEFAULT 0,
    last_accessed REAL DEFAULT 0,
    access_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    supporting_runs TEXT DEFAULT '[]',
    access_count INTEGER DEFAULT 0,
    last_accessed REAL DEFAULT 0,
    is_meta INTEGER DEFAULT 0,
    parent_insights TEXT DEFAULT '[]',
    created_at REAL NOT NULL
);
"""

# Migration: add new columns to existing databases
MIGRATIONS = [
    # Techniques: temporal validity + access tracking
    "ALTER TABLE techniques ADD COLUMN valid_from REAL DEFAULT 0",
    "ALTER TABLE techniques ADD COLUMN valid_until REAL DEFAULT 0",
    "ALTER TABLE techniques ADD COLUMN last_accessed REAL DEFAULT 0",
    "ALTER TABLE techniques ADD COLUMN access_count INTEGER DEFAULT 0",
    # Insights: access tracking + promotion
    "ALTER TABLE insights ADD COLUMN last_accessed REAL DEFAULT 0",
    "ALTER TABLE insights ADD COLUMN is_meta INTEGER DEFAULT 0",
    "ALTER TABLE insights ADD COLUMN parent_insights TEXT DEFAULT '[]'",
]


class ResearchMemory:
    """G-Memory with decay scoring, temporal validity, and insight promotion."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._db = None
        # Configurable via orchestrator from config.toml
        self.decay_lambda = DEFAULT_DECAY_LAMBDA
        self.promotion_threshold = DEFAULT_PROMOTION_THRESHOLD
        self.max_technique_age = DEFAULT_MAX_TECHNIQUE_AGE

    def initialize(self):
        """Create database and apply schema + migrations."""
        self._db = sqlite3.connect(str(self.db_path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(SCHEMA)
        self._apply_migrations()

    def _apply_migrations(self):
        """Apply column additions to existing tables (idempotent)."""
        for sql in MIGRATIONS:
            try:
                self._db.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists
        self._db.commit()

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
    # Techniques (with temporal validity)
    # ------------------------------------------------------------------

    def store_technique(self, name: str, description: str = "",
                        source: str = "", domain: str = "",
                        applicable_to: str = "") -> str:
        """Store a discovered technique with temporal validity."""
        now = time.time()

        with self._db:
            existing = self._db.execute(
                "SELECT id, description FROM techniques WHERE name = ?", (name,)
            ).fetchone()

            if existing:
                # Update with richer data if we have it now
                if description and not existing[1]:
                    self._db.execute(
                        "UPDATE techniques SET description = ?, source = ?, "
                        "domain = ?, applicable_to = ? WHERE id = ?",
                        (description, source, domain, applicable_to, existing[0]),
                    )
                return existing[0]

            tech_id = str(uuid.uuid4())
            self._db.execute(
                "INSERT INTO techniques VALUES (?,?,?,?,?,?,0,0,?,0,0,0,?)",
                (tech_id, name, description, source, domain, applicable_to,
                 now, now),
            )
        return tech_id

    def invalidate_technique(self, name: str):
        """Mark a technique as no longer valid (temporal invalidation).

        Doesn't delete — preserves history. Sets valid_until to now.
        Uses prefix matching since names may include descriptions.
        """
        now = time.time()
        with self._db:
            self._db.execute(
                "UPDATE techniques SET valid_until = ?, tried = 1, worked = 0 "
                "WHERE (name = ? OR name LIKE ? || ' —%' OR name LIKE ? || ' -%') "
                "AND valid_until = 0",
                (now, name, name, name),
            )

    def mark_technique_tried(self, name: str, worked: bool):
        """Mark a technique as tried, recording whether it worked.

        Uses prefix matching since names may include descriptions.
        """
        now = time.time()
        name_match = (
            "name = ? OR name LIKE ? || ' —%' OR name LIKE ? || ' -%'"
        )
        with self._db:
            if not worked:
                self._db.execute(
                    f"UPDATE techniques SET tried = 1, worked = 0, valid_until = ? "
                    f"WHERE ({name_match})",
                    (now, name, name, name),
                )
            else:
                self._db.execute(
                    f"UPDATE techniques SET tried = 1, worked = 1 "
                    f"WHERE ({name_match})",
                    (name, name, name),
                )

    # ------------------------------------------------------------------
    # Insights (with promotion)
    # ------------------------------------------------------------------

    def store_insight(self, content: str, run_id: str = "") -> str:
        """Store a research insight."""
        insight_id = str(uuid.uuid4())
        supporting = json.dumps([run_id] if run_id else [])
        now = time.time()

        with self._db:
            self._db.execute(
                "INSERT INTO insights VALUES (?,?,?,0,?,0,'[]',?)",
                (insight_id, content, supporting, now, now),
            )

        # Check if promotion is needed
        self._maybe_promote_insights(content)
        return insight_id

    def _maybe_promote_insights(self, new_content: str):
        """If enough related insights exist, promote to a meta-insight.

        Uses keyword overlap to find related insights. When threshold is
        reached, creates a meta-insight that summarizes the cluster.
        """
        if not self._db:
            return

        rows = self._db.execute(
            "SELECT id, content FROM insights WHERE is_meta = 0"
        ).fetchall()

        if len(rows) < self.promotion_threshold:
            return

        new_words = set(new_content.lower().split())
        related = []

        for row_id, content in rows:
            content_words = set(content.lower().split())
            overlap = len(new_words & content_words)
            if overlap >= 3:  # At least 3 shared words
                related.append((row_id, content))

        if len(related) < self.promotion_threshold:
            return

        # Create a meta-insight by combining the related insights
        parent_ids = [r[0] for r in related[:self.promotion_threshold]]
        combined = "; ".join(r[1][:100] for r in related[:self.promotion_threshold])
        meta_content = f"[META] Recurring pattern across {len(parent_ids)} runs: {combined}"

        meta_id = str(uuid.uuid4())
        now = time.time()

        with self._db:
            self._db.execute(
                "INSERT INTO insights VALUES (?,?,?,0,?,1,?,?)",
                (meta_id, meta_content[:500], "[]", now,
                 json.dumps(parent_ids), now),
            )

    # ------------------------------------------------------------------
    # Retrieval (with decay scoring)
    # ------------------------------------------------------------------

    def get_relevant_insights(self, topic: str, limit: int = 5) -> list[dict]:
        """Get insights relevant to a topic, ranked by decay-weighted scoring.

        Score = keyword_relevance * recency_weight * access_boost
        recency_weight = exp(-self.decay_lambda * hours_since_last_access)
        access_boost = 1 + log(1 + access_count) * 0.1
        """
        if not self._db:
            return []

        rows = self._db.execute(
            "SELECT id, content, access_count, last_accessed, is_meta, created_at "
            "FROM insights"
        ).fetchall()

        now = time.time()
        topic_words = set(topic.lower().split())
        scored = []

        for row_id, content, access_count, last_accessed, is_meta, created_at in rows:
            content_words = set(content.lower().split())
            overlap = len(topic_words & content_words)
            if overlap == 0:
                continue

            # Keyword relevance (0-1)
            relevance = overlap / max(len(topic_words), 1)

            # Recency decay
            ref_time = last_accessed if last_accessed > 0 else created_at
            hours_since = max((now - ref_time) / 3600, 0.01)
            recency = math.exp(-self.decay_lambda * hours_since)

            # Access frequency boost (logarithmic, prevents runaway)
            access_boost = 1.0 + math.log1p(access_count) * 0.1

            # Meta-insights get a 1.5x boost — they represent compound knowledge
            meta_boost = 1.5 if is_meta else 1.0

            score = relevance * recency * access_boost * meta_boost

            scored.append({
                "id": row_id,
                "content": content,
                "relevance": relevance,
                "recency": round(recency, 3),
                "score": round(score, 4),
                "is_meta": bool(is_meta),
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # Update access counts and timestamps
        with self._db:
            for item in scored[:limit]:
                self._db.execute(
                    "UPDATE insights SET access_count = access_count + 1, "
                    "last_accessed = ? WHERE id = ?",
                    (now, item["id"]),
                )

        return scored[:limit]

    def get_relevant_techniques(self, topic: str, limit: int = 10) -> list[dict]:
        """Get techniques relevant to a topic, respecting temporal validity.

        Excludes invalidated techniques (valid_until > 0 and in the past).
        Ranks by decay-weighted relevance.
        """
        if not self._db:
            return []

        rows = self._db.execute(
            "SELECT id, name, description, domain, tried, worked, "
            "valid_from, valid_until, last_accessed, access_count, created_at "
            "FROM techniques"
        ).fetchall()

        now = time.time()
        topic_lower = topic.lower()
        results = []

        for (tech_id, name, desc, domain, tried, worked, valid_from,
             valid_until, last_accessed, access_count, created_at) in rows:

            # Temporal validity check: skip invalidated techniques
            if valid_until > 0 and valid_until < now:
                continue

            # Age check: deprioritize very old untouched techniques
            ref_time = last_accessed if last_accessed > 0 else created_at
            age = now - ref_time
            if age > self.max_technique_age and access_count == 0:
                continue

            searchable = f"{name} {desc} {domain}".lower()
            if not any(w in searchable for w in topic_lower.split()):
                continue

            # Decay-weighted scoring
            hours_since = max(age / 3600, 0.01)
            recency = math.exp(-self.decay_lambda * hours_since)
            access_boost = 1.0 + math.log1p(access_count) * 0.1

            # Tried-and-worked techniques get a boost
            tried_boost = 1.3 if (tried and worked) else 1.0

            score = recency * access_boost * tried_boost

            results.append({
                "id": tech_id,
                "name": name,
                "description": desc,
                "domain": domain,
                "tried": bool(tried),
                "worked": bool(worked),
                "score": round(score, 4),
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        # Update access tracking
        with self._db:
            for item in results[:limit]:
                self._db.execute(
                    "UPDATE techniques SET access_count = access_count + 1, "
                    "last_accessed = ? WHERE id = ?",
                    (now, item["id"]),
                )

        return results[:limit]

    def build_memory_context(self, topic: str) -> str:
        """Build a context string from memory for injection into agent prompts.

        Returns decay-ranked insights and temporally-valid techniques.
        """
        insights = self.get_relevant_insights(topic)
        techniques = self.get_relevant_techniques(topic)

        if not insights and not techniques:
            return ""

        sections = []

        if insights:
            sections.append("### Historical Insights (decay-ranked)")
            for i in insights:
                meta_tag = " [META]" if i.get("is_meta") else ""
                sections.append(
                    f"- {i['content']} "
                    f"(score={i['score']}, recency={i['recency']}){meta_tag}"
                )

        if techniques:
            sections.append("\n### Known Techniques (temporally valid)")
            for t in techniques:
                status = ""
                if t["tried"]:
                    status = " **[PROVEN]**" if t["worked"] else " **[FAILED]**"
                desc = f": {t['description']}" if t["description"] else ""
                sections.append(
                    f"- **{t['name']}**{desc}{status} (score={t['score']})"
                )

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        if not self._db:
            return {"runs": 0, "techniques": 0, "insights": 0,
                    "meta_insights": 0, "invalidated": 0}

        counts = {}
        for table in ("research_runs", "techniques", "insights"):
            row = self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0] if row else 0

        # Count meta-insights
        row = self._db.execute(
            "SELECT COUNT(*) FROM insights WHERE is_meta = 1"
        ).fetchone()
        counts["meta_insights"] = row[0] if row else 0

        # Count invalidated techniques
        now = time.time()
        row = self._db.execute(
            "SELECT COUNT(*) FROM techniques WHERE valid_until > 0 AND valid_until < ?",
            (now,),
        ).fetchone()
        counts["invalidated_techniques"] = row[0] if row else 0

        return counts
