import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "football_analytics.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS competitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_date TEXT NOT NULL,
    competition_id INTEGER,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_goals INTEGER NOT NULL CHECK(home_goals >= 0),
    away_goals INTEGER NOT NULL CHECK(away_goals >= 0),
    ht_home_goals INTEGER CHECK(ht_home_goals IS NULL OR ht_home_goals >= 0),
    ht_away_goals INTEGER CHECK(ht_away_goals IS NULL OR ht_away_goals >= 0),
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(competition_id) REFERENCES competitions(id),
    FOREIGN KEY(home_team_id) REFERENCES teams(id),
    FOREIGN KEY(away_team_id) REFERENCES teams(id),
    CHECK(home_team_id != away_team_id),
    CHECK(ht_home_goals IS NULL OR ht_home_goals <= home_goals),
    CHECK(ht_away_goals IS NULL OR ht_away_goals <= away_goals)
);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_team_id);
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    model_name TEXT NOT NULL,
    payload TEXT NOT NULL,
    actual_home_goals INTEGER,
    actual_away_goals INTEGER
);
"""

@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize():
    with connection() as conn:
        conn.executescript(SCHEMA)
