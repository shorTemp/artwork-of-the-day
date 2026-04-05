"""Shared artwork history to avoid repeats. Uses SQLite for persistence."""

import sqlite3, os

DB_PATH = os.environ.get("HISTORY_DB", os.path.join(os.path.dirname(__file__), "history.db"))

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS seen (id INTEGER PRIMARY KEY)")
    return conn

def load():
    with _conn() as conn:
        return {row[0] for row in conn.execute("SELECT id FROM seen")}

def check_and_add(art_id):
    """Returns True if new (not seen before), False if already seen."""
    with _conn() as conn:
        try:
            conn.execute("INSERT INTO seen (id) VALUES (?)", (art_id,))
            return True
        except sqlite3.IntegrityError:
            return False
