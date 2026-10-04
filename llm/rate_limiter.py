"""Rate limiter tracking per-provider requests per minute and per day."""

from pathlib import Path
import sqlite3
import time
from typing import Tuple
from llm.types import RateLimitError


class RateLimiter:
    """Persistent sliding-window rate limiter backed by SQLite."""

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
        """Initialize events table and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_rate_limit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rate_events_prov_ts 
                ON llm_rate_limit_events (provider, timestamp);
            """)

    def check_limit(
        self,
        provider: str,
        requests_per_minute: int,
        requests_per_day: int,
    ) -> Tuple[bool, float]:
        """Check if request is permitted under RPM and RPD limits.
        
        Returns:
            Tuple of (is_allowed: bool, wait_seconds: float).
        """
        now = time.time()
        one_min_ago = now - 60.0
        one_day_ago = now - 86400.0

        with self._get_connection() as conn:
            cur = conn.cursor()
            # Clean up old records periodically
            cur.execute(
                "DELETE FROM llm_rate_limit_events WHERE timestamp < ?;",
                (one_day_ago,)
            )

            # Check minute limit
            cur.execute(
                """
                SELECT COUNT(*), MIN(timestamp) 
                FROM llm_rate_limit_events 
                WHERE provider = ? AND timestamp >= ?;
                """,
                (provider, one_min_ago)
            )
            count_min, oldest_min = cur.fetchone()

            if count_min >= requests_per_minute and oldest_min is not None:
                wait_sec = max(0.1, (oldest_min + 60.0) - now)
                return False, wait_sec

            # Check daily limit
            cur.execute(
                """
                SELECT COUNT(*), MIN(timestamp) 
                FROM llm_rate_limit_events 
                WHERE provider = ? AND timestamp >= ?;
                """,
                (provider, one_day_ago)
            )
            count_day, oldest_day = cur.fetchone()

            if count_day >= requests_per_day and oldest_day is not None:
                wait_sec = max(1.0, (oldest_day + 86400.0) - now)
                return False, wait_sec

            return True, 0.0

    def record_request(self, provider: str) -> None:
        """Record an executed request timestamp."""
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO llm_rate_limit_events (provider, timestamp) VALUES (?, ?);",
                (provider, now)
            )
            conn.commit()

    def acquire_or_wait(
        self,
        provider: str,
        requests_per_minute: int,
        requests_per_day: int,
        max_wait_sec: float = 3.0,
    ) -> bool:
        """Attempt to acquire a request slot, sleeping if wait time is under max_wait_sec.
        
        Returns True if acquired, or False if rate limited and wait time exceeds max_wait_sec.
        """
        allowed, wait_sec = self.check_limit(provider, requests_per_minute, requests_per_day)
        if allowed:
            self.record_request(provider)
            return True

        if wait_sec <= max_wait_sec:
            time.sleep(wait_sec)
            self.record_request(provider)
            return True

        return False
