#!/usr/bin/env python3
"""Database migration runner for Dishari.

Applies SQL migrations in sequential order and optionally runs seed scripts.
"""

import argparse
import os
import sys
from pathlib import Path
import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
SEED_FILE = Path(__file__).resolve().parent.parent / "scripts" / "seed.sql"

CREATE_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_db_url() -> str:
    """Retrieve database URL from environment or fallback default."""
    return os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/dishari"
    )


def apply_migrations(db_url: str, migrations_path: Path = MIGRATIONS_DIR) -> None:
    """Apply all pending SQL migrations."""
    print(f"Connecting to database to apply migrations...")
    migration_files = sorted(migrations_path.glob("*.sql"))

    if not migration_files:
        print(f"No migration files found in {migrations_path}")
        return

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            # Ensure migrations tracking table exists
            cur.execute(CREATE_MIGRATIONS_TABLE_SQL)
            conn.commit()

            cur.execute("SELECT version FROM schema_migrations;")
            applied_versions = {row[0] for row in cur.fetchall()}

            for m_file in migration_files:
                version = m_file.name
                if version in applied_versions:
                    print(f"[-] Migration already applied: {version}")
                    continue

                print(f"[+] Applying migration: {version}...")
                sql_content = m_file.read_text(encoding="utf-8")
                cur.execute(sql_content)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s);", 
                    (version,)
                )
                conn.commit()
                print(f"[✓] Successfully applied: {version}")


def apply_seed(db_url: str, seed_path: Path = SEED_FILE) -> None:
    """Apply the database seed script."""
    if not seed_path.exists():
        print(f"Seed file not found at {seed_path}")
        return

    print(f"[+] Applying seed script: {seed_path.name}...")
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            seed_sql = seed_path.read_text(encoding="utf-8")
            cur.execute(seed_sql)
    print(f"[✓] Successfully seeded database from {seed_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Dishari SQL migrations.")
    parser.add_argument(
        "--db-url", 
        default=None, 
        help="Postgres connection string (defaults to DATABASE_URL env var)"
    )
    parser.add_argument(
        "--seed", 
        action="store_true", 
        help="Run seed script after applying migrations"
    )
    args = parser.parse_args()

    db_url = args.db_url or get_db_url()

    try:
        apply_migrations(db_url)
        if args.seed:
            apply_seed(db_url)
        print("All database operations completed successfully.")
    except Exception as exc:
        print(f"Database operation failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
