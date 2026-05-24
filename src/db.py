
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
import pandas as pd

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "tax_calculations.sqlite3"


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calculations (
                id TEXT PRIMARY KEY,
                module TEXT NOT NULL,
                title TEXT NOT NULL,
                input_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_calculation(module: str, title: str, input_data: dict[str, Any], result_data: dict[str, Any]) -> str:
    init_db()
    calc_id = input_data.get("calc_id") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO calculations (id, module, title, input_json, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                calc_id,
                module,
                title,
                json.dumps(input_data, ensure_ascii=False, default=str),
                json.dumps(result_data, ensure_ascii=False, default=str),
                created_at,
            ),
        )
        conn.commit()
    return calc_id


def get_recent_calculations(limit: int = 20) -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, module, title, created_at, input_json, result_json
            FROM calculations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=["id", "module", "title", "created_at", "input_json", "result_json"])
    return pd.DataFrame([dict(r) for r in rows])


def get_calculation(calc_id: str) -> Optional[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, module, title, created_at, input_json, result_json FROM calculations WHERE id = ?",
            (calc_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["input_json"] = json.loads(data["input_json"])
    data["result_json"] = json.loads(data["result_json"])
    return data
