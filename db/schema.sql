
-- AXON database schema
-- Stores extracted resume profiles in SQLite.

CREATE TABLE IF NOT EXISTS resume_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    skills_json TEXT NOT NULL,
    education_json TEXT NOT NULL,
    projects_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
