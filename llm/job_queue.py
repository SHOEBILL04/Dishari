"""Resumable SQLite-backed job queue for offline batch LLM scripts.

Ensures long-running batch jobs (tagging thousands of questions, OCR verification)
survive process crashes, power failures, or Ctrl+C interruptions without re-running finished tasks.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any, Callable, Optional


class JobQueue:
    """Persistent SQLite job queue supporting resumption and failure recovery."""

    def __init__(self, db_path: str | Path = "data/llm_jobs.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize jobs table and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_jobs (
                    job_id TEXT PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    prompt_name TEXT NOT NULL,
                    variables_json TEXT NOT NULL,
                    temperature REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_json TEXT,
                    error_message TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_jobs_queue_status 
                ON llm_jobs (queue_name, status);
            """)

    def enqueue(
        self,
        queue_name: str,
        prompt_name: str,
        variables: dict[str, Any],
        temperature: float = 0.0,
        job_id: Optional[str] = None,
    ) -> str:
        """Add a job to the queue if not already present."""
        jid = job_id or str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        vars_json = json.dumps(variables, ensure_ascii=False)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO llm_jobs (
                    job_id, queue_name, prompt_name, variables_json, temperature,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                ON CONFLICT(job_id) DO NOTHING;
                """,
                (jid, queue_name, prompt_name, vars_json, temperature, now_iso, now_iso)
            )
            conn.commit()
        return jid

    def enqueue_batch(
        self,
        queue_name: str,
        items: list[dict[str, Any]],
    ) -> list[str]:
        """Add multiple jobs in a single transaction."""
        job_ids = []
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            for item in items:
                jid = item.get("job_id") or str(uuid.uuid4())
                prompt_name = item["prompt_name"]
                variables = item.get("variables", {})
                temperature = item.get("temperature", 0.0)
                vars_json = json.dumps(variables, ensure_ascii=False)

                conn.execute(
                    """
                    INSERT INTO llm_jobs (
                        job_id, queue_name, prompt_name, variables_json, temperature,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                    ON CONFLICT(job_id) DO NOTHING;
                    """,
                    (jid, queue_name, prompt_name, vars_json, temperature, now_iso, now_iso)
                )
                job_ids.append(jid)
            conn.commit()
        return job_ids

    def reset_stuck_jobs(self, queue_name: Optional[str] = None) -> int:
        """Reset any 'in_progress' jobs back to 'pending' after an unexpected script restart."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            if queue_name:
                cur.execute(
                    """
                    UPDATE llm_jobs 
                    SET status = 'pending', updated_at = ? 
                    WHERE queue_name = ? AND status = 'in_progress';
                    """,
                    (now_iso, queue_name)
                )
            else:
                cur.execute(
                    """
                    UPDATE llm_jobs 
                    SET status = 'pending', updated_at = ? 
                    WHERE status = 'in_progress';
                    """,
                    (now_iso,)
                )
            conn.commit()
            return cur.rowcount

    def claim_next(self, queue_name: str) -> Optional[dict[str, Any]]:
        """Atomically fetch and lock the next pending job."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT job_id, prompt_name, variables_json, temperature, attempts
                FROM llm_jobs
                WHERE queue_name = ? AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (queue_name,)
            )
            row = cur.fetchone()
            if not row:
                return None

            job_id = row["job_id"]
            cur.execute(
                """
                UPDATE llm_jobs
                SET status = 'in_progress', attempts = attempts + 1, updated_at = ?
                WHERE job_id = ?;
                """,
                (now_iso, job_id)
            )
            conn.commit()

            return {
                "job_id": job_id,
                "prompt_name": row["prompt_name"],
                "variables": json.loads(row["variables_json"]),
                "temperature": row["temperature"],
                "attempts": row["attempts"] + 1,
            }

    def complete(self, job_id: str, result: Any) -> None:
        """Mark job completed and record result."""
        now_iso = datetime.now(timezone.utc).isoformat()
        result_json = (
            result if isinstance(result, str) 
            else json.dumps(
                result.model_dump() if hasattr(result, "model_dump") else result,
                ensure_ascii=False
            )
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE llm_jobs
                SET status = 'completed', result_json = ?, error_message = NULL, updated_at = ?
                WHERE job_id = ?;
                """,
                (result_json, now_iso, job_id)
            )
            conn.commit()

    def fail(self, job_id: str, error_message: str) -> None:
        """Mark job as failed with error details."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE llm_jobs
                SET status = 'failed', error_message = ?, updated_at = ?
                WHERE job_id = ?;
                """,
                (error_message, now_iso, job_id)
            )
            conn.commit()

    def get_stats(self, queue_name: str) -> dict[str, int]:
        """Return counts of jobs by status for a given queue."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT status, COUNT(*) as cnt
                FROM llm_jobs
                WHERE queue_name = ?
                GROUP BY status;
                """,
                (queue_name,)
            )
            rows = cur.fetchall()
            stats = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "total": 0}
            for row in rows:
                stats[row["status"]] = row["cnt"]
                stats["total"] += row["cnt"]
            return stats

    def run_queue(
        self,
        queue_name: str,
        complete_fn: Callable[..., Any],
        schema: Any,
        on_success: Optional[Callable[[str, Any], None]] = None,
        on_failure: Optional[Callable[[str, Exception], None]] = None,
    ) -> dict[str, int]:
        """Execute all pending jobs in the queue using complete_fn.
        
        Resets stuck in_progress jobs first, then processes one-by-one.
        Safe to interrupt; re-running picks up exactly where it left off.
        """
        self.reset_stuck_jobs(queue_name)
        while True:
            job = self.claim_next(queue_name)
            if not job:
                break

            jid = job["job_id"]
            try:
                result = complete_fn(
                    prompt_name=job["prompt_name"],
                    variables=job["variables"],
                    schema=schema,
                    temperature=job["temperature"],
                )
                self.complete(jid, result)
                if on_success:
                    on_success(jid, result)
            except Exception as exc:
                self.fail(jid, str(exc))
                if on_failure:
                    on_failure(jid, exc)

        return self.get_stats(queue_name)
