"""Disk cache for LLM completions backed by SQLite.

Keys are computed deterministically using hash(prompt_version + variables + model).
Cache hits avoid external API calls and have zero token cost.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Optional


class DiskCache:
    """SQLite-backed persistent disk cache for LLM responses."""

    def __init__(self, db_path: str | Path = "data/llm_cache.sqlite"):
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
        """Create cache table and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    prompt_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    model TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_cache_model 
                ON llm_cache (model);
            """)

    @staticmethod
    def compute_key(
        prompt_name: str,
        prompt_version: str,
        variables: dict[str, Any],
        model: str,
        temperature: float = 0.0,
    ) -> str:
        """Compute a deterministic SHA-256 hash for cache lookup."""
        payload = {
            "prompt_name": prompt_name,
            "prompt_version": prompt_version,
            "variables": variables,
            "model": model,
            "temperature": round(temperature, 4),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, cache_key: str) -> Optional[dict[str, Any] | list[Any]]:
        """Retrieve cached response if present and increment hit counter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT response_json FROM llm_cache WHERE cache_key = ?;",
                (cache_key,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE cache_key = ?;",
                    (cache_key,)
                )
                conn.commit()
                return json.loads(row["response_json"])
        return None

    def set(
        self,
        cache_key: str,
        prompt_name: str,
        prompt_version: str,
        model: str,
        response_data: dict[str, Any] | list[Any] | str,
    ) -> None:
        """Store response in SQLite cache."""
        if isinstance(response_data, str):
            json_text = response_data
        else:
            json_text = json.dumps(response_data, ensure_ascii=False)

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_cache (
                    cache_key, prompt_name, prompt_version, model, response_json, created_at, hit_count
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = EXCLUDED.response_json,
                    created_at = EXCLUDED.created_at;
                """,
                (cache_key, prompt_name, prompt_version, model, json_text, now_iso)
            )
            conn.commit()

    def clear(self) -> int:
        """Clear all entries from cache and return count of deleted items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM llm_cache;")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM llm_cache;")
            conn.commit()
            return count
