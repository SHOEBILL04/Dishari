#!/usr/bin/env bash
# Script to apply Dishari SQL migrations and seed data
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/dishari}"

echo "Applying migrations to database..."
if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    "$ROOT_DIR/.venv/bin/python" "$SCRIPT_DIR/migrate.py" --db-url "$DATABASE_URL" "$@"
else
    python3 "$SCRIPT_DIR/migrate.py" --db-url "$DATABASE_URL" "$@"
fi
