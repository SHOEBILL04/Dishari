"""Pytest configuration and database fixtures for Dishari tests."""

import os
import socket
import subprocess
import time
import pytest
import psycopg

DOCKER_IMAGE = "pgvector/pgvector:pg16"


def find_free_port() -> int:
    """Find an available port on the host machine."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def postgres_container():
    """Start an ephemeral pgvector container if no external TEST_DATABASE_URL is provided."""
    env_db_url = os.getenv("TEST_DATABASE_URL")
    if env_db_url:
        yield env_db_url
        return

    port = find_free_port()
    container_name = f"dishari-test-db-{port}"
    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_USER=postgres",
        "-e", "POSTGRES_DB=dishari_test",
        "-p", f"127.0.0.1:{port}:5432",
        DOCKER_IMAGE
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    db_url = f"postgresql://postgres:postgres@127.0.0.1:{port}/dishari_test"

    # Wait for database to become ready
    deadline = time.time() + 20
    ready = False
    last_err = None
    while time.time() < deadline:
        try:
            with psycopg.connect(db_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    ready = True
                    break
        except Exception as exc:
            last_err = exc
            time.sleep(0.5)

    if not ready:
        subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL)
        pytest.fail(f"Test postgres container failed to become ready: {last_err}")

    try:
        yield db_url
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL)


@pytest.fixture
def empty_db(postgres_container):
    """Provide a clean, empty database for each test that needs one."""
    db_url = postgres_container
    # Drop all tables, types, and extensions to ensure a completely clean state
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DROP SCHEMA IF EXISTS public CASCADE;
                CREATE SCHEMA public;
                GRANT ALL ON SCHEMA public TO postgres;
                GRANT ALL ON SCHEMA public TO public;
            """)
    return db_url
