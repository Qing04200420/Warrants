import json
import sqlite3
from pathlib import Path
from statistics import pstdev

DB_PATH = Path(__file__).resolve().parent.parent / "warrants.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warrant_code TEXT NOT NULL,
            score REAL NOT NULL,
            analyzed_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_analyses_code_time ON analyses(warrant_code, analyzed_at DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS warrant_iv_samples (
            warrant_code TEXT NOT NULL,
            observed_on TEXT NOT NULL,
            implied_vol REAL NOT NULL,
            PRIMARY KEY (warrant_code, observed_on)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_warrant_iv_code_date ON warrant_iv_samples(warrant_code, observed_on DESC)")


def record_iv_sample(warrant_code: str, observed_on: str, implied_vol: float, window: int = 14) -> tuple[float | None, int]:
    """Store one TWSE close IV per day and return its rolling population stddev."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """INSERT INTO warrant_iv_samples(warrant_code, observed_on, implied_vol)
               VALUES (?, ?, ?)
               ON CONFLICT(warrant_code, observed_on)
               DO UPDATE SET implied_vol = excluded.implied_vol""",
            (warrant_code, observed_on, implied_vol),
        )
        rows = db.execute(
            """SELECT implied_vol FROM warrant_iv_samples
               WHERE warrant_code = ?
               ORDER BY observed_on DESC LIMIT ?""",
            (warrant_code, window),
        ).fetchall()
    values = [float(row[0]) for row in rows]
    return (pstdev(values) if len(values) >= 2 else None), len(values)


def save(payload: dict) -> int:
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("INSERT INTO analyses(warrant_code, score, analyzed_at, payload) VALUES (?, ?, ?, ?)", (payload["warrant_code"], payload["score"], payload["analyzed_at"], json.dumps(payload, ensure_ascii=False)))
        return int(cursor.lastrowid)


def history(code: str | None, limit: int) -> list[dict]:
    sql, params = "SELECT id, payload FROM analyses", []
    if code:
        sql += " WHERE warrant_code = ?"
        params.append(code)
    sql += " ORDER BY analyzed_at DESC LIMIT ?"
    params.append(limit)
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(sql, params).fetchall()
    result = []
    for row_id, payload in rows:
        item = json.loads(payload)
        item["id"] = row_id
        result.append(item)
    return result


def clear() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM analyses")

