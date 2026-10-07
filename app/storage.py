"""SQLite persistence for processed uploads."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/geospatial.sqlite3"))


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with connect() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS uploaded_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                feature_count INTEGER NOT NULL,
                crs TEXT,
                status TEXT NOT NULL,
                features_json TEXT NOT NULL
            )"""
        )


def save_file(
    file_id: str,
    filename: str,
    features: list[dict[str, Any]],
    crs: str | None,
) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO uploaded_files VALUES (?, ?, ?, ?, ?, ?)",
            (
                file_id,
                filename,
                len(features),
                crs,
                "COMPLETED",
                json.dumps(features, allow_nan=False),
            ),
        )


def get_file(file_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute(
            "SELECT id, filename, feature_count, crs, status, features_json "
            "FROM uploaded_files WHERE id = ?",
            (file_id,),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["features"] = json.loads(result.pop("features_json"))
    return result
