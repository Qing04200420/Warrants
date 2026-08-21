import json
import sqlite3
from pathlib import Path
from statistics import pstdev

DB_PATH = Path(__file__).resolve().parent.parent / "warrants.db"


def init_db() -> None:
    """建立分析歷史與每日 IV 樣本資料表；重複執行不會清除既有資料。"""
    with sqlite3.connect(DB_PATH) as db:
        # payload 保存完整 API 回應，方便未來新增欄位時維持相容性。
        db.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warrant_code TEXT NOT NULL,
            score REAL NOT NULL,
            analyzed_at TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_analyses_code_time ON analyses(warrant_code, analyzed_at DESC)")
        # 每個權證每個交易日只留一筆 IV，避免同日重複查詢扭曲標準差。
        db.execute("""CREATE TABLE IF NOT EXISTS warrant_iv_samples (
            warrant_code TEXT NOT NULL,
            observed_on TEXT NOT NULL,
            implied_vol REAL NOT NULL,
            PRIMARY KEY (warrant_code, observed_on)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_warrant_iv_code_date ON warrant_iv_samples(warrant_code, observed_on DESC)")


def record_iv_sample(warrant_code: str, observed_on: str, implied_vol: float, window: int = 14) -> tuple[float | None, int]:
    """保存每日 TWSE 盤後 IV，回傳指定視窗的母體標準差與樣本數。"""
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
    # 只有一筆資料無法表示歷史波動，因此回傳 None 交由上層使用暫代值。
    return (pstdev(values) if len(values) >= 2 else None), len(values)


def save(payload: dict) -> int:
    """保存一次完整分析結果並回傳流水號。"""
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("INSERT INTO analyses(warrant_code, score, analyzed_at, payload) VALUES (?, ?, ?, ?)", (payload["warrant_code"], payload["score"], payload["analyzed_at"], json.dumps(payload, ensure_ascii=False)))
        return int(cursor.lastrowid)


def history(code: str | None, limit: int) -> list[dict]:
    """依時間倒序讀取分析紀錄，可選擇只查單一權證。"""
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
    """清除使用者分析歷史；每日 IV 樣本刻意保留供穩定度計算。"""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM analyses")

