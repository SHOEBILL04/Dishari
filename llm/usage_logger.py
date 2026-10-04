"""Usage and cost logging table for LLM calls."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Optional
from llm.types import UsageRecord


class UsageLogger:
    """SQLite-backed audit log for token usage, latency, and costs."""

    def __init__(self, db_path: str | Path = "data/llm_usage.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize usage log table and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    prompt_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    estimated_cost REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    cache_hit INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_log_prompt 
                ON llm_usage_log (prompt_name, prompt_version);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_log_provider 
                ON llm_usage_log (provider, model);
            """)

    def log(self, record: UsageRecord) -> None:
        """Record an LLM call event."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_usage_log (
                    call_id, timestamp, prompt_name, prompt_version, provider, model,
                    input_tokens, output_tokens, estimated_cost, latency_ms, cache_hit,
                    status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.call_id,
                    record.timestamp.isoformat(),
                    record.prompt_name,
                    record.prompt_version,
                    record.provider,
                    record.model,
                    record.input_tokens,
                    record.output_tokens,
                    record.estimated_cost,
                    record.latency_ms,
                    1 if record.cache_hit else 0,
                    record.status,
                    record.error_message,
                )
            )
            conn.commit()

    def get_summary(self) -> dict[str, Any]:
        """Return aggregated stats for all calls."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(estimated_cost) as total_cost,
                    AVG(latency_ms) as avg_latency_ms
                FROM llm_usage_log;
            """)
            row = cur.fetchone()
            total_calls = row["total_calls"] or 0
            cache_hits = row["cache_hits"] or 0
            return {
                "total_calls": total_calls,
                "cache_hits": cache_hits,
                "cache_hit_rate": (cache_hits / total_calls) if total_calls > 0 else 0.0,
                "total_input_tokens": row["total_input_tokens"] or 0,
                "total_output_tokens": row["total_output_tokens"] or 0,
                "total_cost_usd": round(row["total_cost"] or 0.0, 6),
                "avg_latency_ms": round(row["avg_latency_ms"] or 0.0, 2),
            }
