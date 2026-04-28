import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "fiesta.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                draws_used     INTEGER NOT NULL DEFAULT 0,
                last_draw_date TEXT
            );
            CREATE TABLE IF NOT EXISTS inventory (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL,
                medal_id INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id);
            """
        )


def ensure_user(user_id: int) -> None:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))


def get_user(user_id: int) -> dict:
    with _conn() as c:
        row = c.execute(
            "SELECT draws_used, last_draw_date FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else {"draws_used": 0, "last_draw_date": None}


def record_draw(user_id: int, medal_id: int, today: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))
        c.execute(
            "UPDATE users SET draws_used = draws_used + 1, last_draw_date = ? WHERE user_id = ?",
            (today, user_id),
        )
        c.execute(
            "INSERT INTO inventory(user_id, medal_id) VALUES (?, ?)",
            (user_id, medal_id),
        )


def get_inventory(user_id: int) -> list[int]:
    with _conn() as c:
        rows = c.execute(
            "SELECT medal_id FROM inventory WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [r["medal_id"] for r in rows]


def has_medal(user_id: int, medal_id: int) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM inventory WHERE user_id = ? AND medal_id = ? LIMIT 1",
            (user_id, medal_id),
        ).fetchone()
    return row is not None


def swap_medals(user_a: int, medal_a: int, user_b: int, medal_b: int) -> None:
    """Atomically remove one medal_a from user_a and one medal_b from user_b,
    then give user_a a medal_b and user_b a medal_a."""
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM inventory WHERE user_id = ? AND medal_id = ? LIMIT 1",
            (user_a, medal_a),
        ).fetchone()
        if not row:
            raise ValueError("initiator no longer has the offered medal")
        c.execute("DELETE FROM inventory WHERE id = ?", (row["id"],))

        row = c.execute(
            "SELECT id FROM inventory WHERE user_id = ? AND medal_id = ? LIMIT 1",
            (user_b, medal_b),
        ).fetchone()
        if not row:
            raise ValueError("target no longer has the offered medal")
        c.execute("DELETE FROM inventory WHERE id = ?", (row["id"],))

        c.execute(
            "INSERT INTO inventory(user_id, medal_id) VALUES (?, ?)", (user_a, medal_b)
        )
        c.execute(
            "INSERT INTO inventory(user_id, medal_id) VALUES (?, ?)", (user_b, medal_a)
        )
