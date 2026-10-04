"""Tests for database migrations and seed script against an empty PostgreSQL database."""

from pathlib import Path
import psycopg
from scripts.migrate import apply_migrations, apply_seed

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
SEED_FILE = Path(__file__).resolve().parent.parent / "scripts" / "seed.sql"

EXPECTED_TABLES = {
    "exams",
    "syllabus_versions",
    "syllabus_subject_marks",
    "subjects",
    "topics",
    "questions",
    "tag_log",
    "sources",
    "users",
    "attempts",
    "topic_mastery",
    "review_cards",
    "mocks",
}


def get_public_tables(conn: psycopg.Connection) -> set[str]:
    """Retrieve all table names in public schema."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        return {row[0] for row in cur.fetchall()}


def test_migrations_apply_to_empty_db(empty_db: str) -> None:
    """Verify that migrations apply cleanly to a completely empty database."""
    with psycopg.connect(empty_db) as conn:
        tables_before = get_public_tables(conn)
        assert len(tables_before) == 0, f"Expected empty DB, but found: {tables_before}"

    # Apply migrations
    apply_migrations(empty_db, MIGRATIONS_DIR)

    with psycopg.connect(empty_db) as conn:
        tables_after = get_public_tables(conn)
        # All domain tables plus schema_migrations tracking table
        for expected_table in EXPECTED_TABLES:
            assert expected_table in tables_after, f"Missing table: {expected_table}"
        assert "schema_migrations" in tables_after

        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version;")
            applied_versions = [row[0] for row in cur.fetchall()]
            assert len(applied_versions) == 3
            assert applied_versions[0] == "001_initial_schema.sql"
            assert applied_versions[1] == "002_indexes.sql"
            assert applied_versions[2] == "003_row_level_security.sql"


def test_schema_columns_and_vector_types(empty_db: str) -> None:
    """Validate table columns, constraints, and pgvector extension types."""
    apply_migrations(empty_db, MIGRATIONS_DIR)

    with psycopg.connect(empty_db) as conn:
        with conn.cursor() as cur:
            # 1. Verify extensions
            cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp');")
            installed_exts = {row[0] for row in cur.fetchall()}
            assert "vector" in installed_exts, "pgvector extension is not installed"
            assert "uuid-ossp" in installed_exts, "uuid-ossp extension is not installed"

            # 2. Verify questions table columns and types
            cur.execute("""
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'questions';
            """)
            col_map = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            assert "options" in col_map
            assert col_map["options"][0] == "jsonb"

            assert "embedding" in col_map
            assert col_map["embedding"][1] == "vector"

            assert "status" in col_map
            assert "correct_index" in col_map
            assert "difficulty" in col_map
            assert "grounding_source_id" in col_map
            assert "expires_at" in col_map

            # 3. Verify exams table structure
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'exams';
            """)
            exam_cols = {row[0] for row in cur.fetchall()}
            expected_exam_cols = {
                "id", "bcs_number", "year", "syllabus_version_id", 
                "total_marks", "negative_mark", "duration_min", "created_at"
            }
            assert expected_exam_cols.issubset(exam_cols)


def test_indexes_and_pgvector_hnsw(empty_db: str) -> None:
    """Verify indexes are created, especially HNSW vector index and unique indexes."""
    apply_migrations(empty_db, MIGRATIONS_DIR)

    with psycopg.connect(empty_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE schemaname = 'public';
            """)
            indexes = {row[0]: row[1] for row in cur.fetchall()}

            # Vector HNSW index
            assert "idx_questions_embedding_hnsw" in indexes
            assert "hnsw" in indexes["idx_questions_embedding_hnsw"].lower()
            assert "vector_cosine_ops" in indexes["idx_questions_embedding_hnsw"].lower()

            # Unique index on (exam_id, q_no)
            assert "idx_questions_exam_qno" in indexes
            assert "UNIQUE" in indexes["idx_questions_exam_qno"].upper()

            # Review cards index
            assert "idx_review_cards_user_due" in indexes


def test_row_level_security_enabled(empty_db: str) -> None:
    """Verify that Row-Level Security is enabled on every domain table."""
    apply_migrations(empty_db, MIGRATIONS_DIR)

    with psycopg.connect(empty_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, rowsecurity 
                FROM pg_tables 
                WHERE schemaname = 'public';
            """)
            rls_status = {row[0]: row[1] for row in cur.fetchall()}

            for expected_table in EXPECTED_TABLES:
                assert expected_table in rls_status, f"Table {expected_table} missing"
                assert rls_status[expected_table] is True, f"RLS not enabled on {expected_table}"


def test_seed_script_and_vector_query(empty_db: str) -> None:
    """Apply migrations and seed script, then test constraints and vector search."""
    apply_migrations(empty_db, MIGRATIONS_DIR)
    apply_seed(empty_db, SEED_FILE)

    with psycopg.connect(empty_db) as conn:
        with conn.cursor() as cur:
            # 1. Check 10 subjects seeded
            cur.execute("SELECT COUNT(*) FROM subjects;")
            subject_count = cur.fetchone()[0]
            assert subject_count == 10, f"Expected 10 subjects, found {subject_count}"

            # 2. Check 35th BCS subject marks sum up to 200 marks exactly
            cur.execute("""
                SELECT SUM(marks) 
                FROM syllabus_subject_marks 
                WHERE syllabus_version_id = '00000000-0000-0000-0000-000000000001';
            """)
            total_marks = cur.fetchone()[0]
            assert float(total_marks) == 200.0, f"Expected 200 marks, found {total_marks}"

            # 3. Check seeded questions exist
            cur.execute("SELECT COUNT(*) FROM questions WHERE status = 'verified';")
            question_count = cur.fetchone()[0]
            assert question_count >= 2

            # 4. Perform vector similarity query using cosine distance (<=>)
            cur.execute("""
                SELECT id, stem, embedding <=> array_fill(0.051::real, ARRAY[384])::vector(384) AS distance
                FROM questions
                WHERE embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT 5;
            """)
            results = cur.fetchall()
            assert len(results) >= 2
            # Cosine distance between identical zero vectors is 0 or well-defined real number
            assert results[0][2] is not None


def test_migrations_and_seed_idempotency(empty_db: str) -> None:
    """Verify that applying migrations and seed scripts multiple times is safe and idempotent."""
    apply_migrations(empty_db, MIGRATIONS_DIR)
    apply_seed(empty_db, SEED_FILE)

    # Re-apply migrations (should skip) and seed (should upsert without error)
    apply_migrations(empty_db, MIGRATIONS_DIR)
    apply_seed(empty_db, SEED_FILE)

    with psycopg.connect(empty_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM subjects;")
            assert cur.fetchone()[0] == 10
            cur.execute("SELECT COUNT(*) FROM questions;")
            assert cur.fetchone()[0] >= 2
