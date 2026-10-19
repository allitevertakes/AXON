
-- AXON starter skill catalogue.
-- These are sample reference skills for demonstrations.

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
);

INSERT OR IGNORE INTO skills (name, category) VALUES
    ('Python', 'Programming'),
    ('Java', 'Programming'),
    ('JavaScript', 'Programming'),
    ('HTML', 'Web Development'),
    ('CSS', 'Web Development'),
    ('SQL', 'Databases'),
    ('Data Analysis', 'Data'),
    ('Machine Learning', 'AI and Data'),
    ('Leadership', 'Professional'),
    ('Communication', 'Professional'),
    ('Docker', 'DevOps'),
    ('AWS', 'Cloud Computing');
