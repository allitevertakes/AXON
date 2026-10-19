
"""SQLite persistence for AXON resume profiles."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "axon.db"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection and ensure the profile table exists."""
    path = Path(
        db_path or os.getenv("AXON_DB_PATH", str(DEFAULT_DB_PATH))
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            skills_json TEXT NOT NULL,
            education_json TEXT NOT NULL,
            projects_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    return connection


def save_resume_profile(
    filename: str,
    skills: list[dict[str, Any]],
    education: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    db_path: str | Path | None = None,
) -> int:
    """Persist an extracted resume profile and return its record ID."""
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO resume_profiles
                (filename, skills_json, education_json, projects_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                filename,
                json.dumps(skills),
                json.dumps(education),
                json.dumps(projects),
            ),
        )
        return int(cursor.lastrowid)


def get_resume_profile(
    profile_id: int,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Retrieve one saved profile, or None when it does not exist."""
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM resume_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "filename": row["filename"],
        "skills": json.loads(row["skills_json"]),
        "education": json.loads(row["education_json"]),
        "projects": json.loads(row["projects_json"]),
        "created_at": row["created_at"],
    }


def list_resume_profiles(
    limit: int = 20,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List saved profiles, newest first, without returning extracted content."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, filename, created_at
            FROM resume_profiles
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
