import json
import sqlite3
from pathlib import Path

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

