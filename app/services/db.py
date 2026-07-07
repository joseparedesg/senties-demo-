"""DB helper — SQLite para el demo."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "senties_demo.db"


def get_db():
    """Retorna conexión SQLite con row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
