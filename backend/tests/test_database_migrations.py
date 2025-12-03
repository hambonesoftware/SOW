"""Tests covering automatic database migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend import database
from backend.config import reset_settings_cache


def _create_legacy_document_table(path: Path) -> None:
    """Create a ``document`` table missing the ``mime_type`` column."""

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE document (
                id INTEGER PRIMARY KEY,
                filename VARCHAR NOT NULL,
                checksum VARCHAR NOT NULL,
                uploaded_at DATETIME NOT NULL,
                status VARCHAR NOT NULL
            )
            """
        )


def _create_legacy_sow_tables(path: Path) -> None:
    """Create legacy SOW tables missing the ``label`` column."""

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE sow_runs (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                model VARCHAR NOT NULL,
                source_hash VARCHAR NOT NULL,
                prompt_hash VARCHAR NOT NULL,
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                latency_ms INTEGER,
                status VARCHAR NOT NULL DEFAULT 'pending',
                error_message VARCHAR,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE sow_steps (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                order_index INTEGER NOT NULL,
                step_id VARCHAR,
                phase VARCHAR,
                title VARCHAR NOT NULL,
                description TEXT NOT NULL,
                actor VARCHAR,
                location VARCHAR,
                inputs TEXT,
                outputs TEXT,
                dependencies TEXT,
                header_section_key VARCHAR,
                source_section_title VARCHAR,
                start_page INTEGER,
                end_page INTEGER,
                created_at DATETIME NOT NULL
            )
            """
        )


def test_init_db_backfills_mime_type_column(tmp_path, monkeypatch):
    """``init_db`` should add the ``mime_type`` column when it is missing."""

    db_path = tmp_path / "legacy.db"
    _create_legacy_document_table(db_path)

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    database.reset_database_state()
    reset_settings_cache()

    database.init_db()

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(document)")
        }

    assert "mime_type" in columns


def test_init_db_creates_sow_tables(tmp_path, monkeypatch):
    """The database initialiser should create the SOW tables."""

    db_path = tmp_path / "sow.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    database.reset_database_state()
    reset_settings_cache()

    database.init_db()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert "sow_runs" in tables
    assert "sow_steps" in tables


def test_init_db_backfills_sow_step_label(tmp_path, monkeypatch):
    """``init_db`` should add the ``label`` column to ``sow_steps`` when missing."""

    db_path = tmp_path / "legacy_sow.db"
    _create_legacy_sow_tables(db_path)

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    database.reset_database_state()
    reset_settings_cache()

    database.init_db()

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(sow_steps)")
        }

    assert "label" in columns
