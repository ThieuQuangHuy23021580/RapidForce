from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from model_storage.errors import DatabaseError


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS models (
                model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                size REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                model_id INT,
                CONSTRAINT fk_model
                    FOREIGN KEY(model_id)
                    REFERENCES models(model_id)
                    ON DELETE SET NULL
            );
            """
        )


def insert_model(db_path: Path, url: str, size_mb: float) -> int:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO models (url, size, created_at) VALUES (?, ?, ?)",
                (url, size_mb, datetime.utcnow().isoformat()),
            )
            return int(cur.lastrowid)
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to insert model metadata: {exc}") from exc


def ensure_user(db_path: Path, user_name: str) -> int:
    try:
        with connect(db_path) as conn:
            cur = conn.execute("SELECT user_id FROM users WHERE user_name = ?", (user_name,))
            row = cur.fetchone()
            if row:
                return int(row[0])

            cur = conn.execute("INSERT INTO users (user_name) VALUES (?)", (user_name,))
            return int(cur.lastrowid)
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to ensure user record: {exc}") from exc


def link_model_to_user(db_path: Path, user_id: int, model_id: int) -> None:
    try:
        with connect(db_path) as conn:
            cur = conn.execute("UPDATE users SET model_id = ? WHERE user_id = ?", (model_id, user_id))
            if cur.rowcount == 0:
                raise DatabaseError(f"User {user_id} not found")
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, DatabaseError):
            raise
        raise DatabaseError(f"Failed to link model to user: {exc}") from exc


def list_models(db_path: Path, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT model_id, url, size, created_at
                FROM models
                ORDER BY model_id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        return [
            {
                "model_id": int(row[0]),
                "url": row[1],
                "size_mb": float(row[2]) if row[2] is not None else None,
                "created_at": row[3],
            }
            for row in rows
        ]
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to list models: {exc}") from exc


def get_model(db_path: Path, model_id: int) -> dict[str, Any] | None:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT model_id, url, size, created_at
                FROM models
                WHERE model_id = ?
                """,
                (model_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "model_id": int(row[0]),
            "url": row[1],
            "size_mb": float(row[2]) if row[2] is not None else None,
            "created_at": row[3],
        }
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to get model {model_id}: {exc}") from exc


def list_users(db_path: Path, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT u.user_id, u.user_name, u.model_id, m.url, m.size, m.created_at
                FROM users u
                LEFT JOIN models m ON u.model_id = m.model_id
                ORDER BY u.user_id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        return [
            {
                "user_id": int(row[0]),
                "user_name": row[1],
                "model_id": int(row[2]) if row[2] is not None else None,
                "model_url": row[3],
                "model_size_mb": float(row[4]) if row[4] is not None else None,
                "model_created_at": row[5],
            }
            for row in rows
        ]
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to list users: {exc}") from exc


def get_user(db_path: Path, user_id: int) -> dict[str, Any] | None:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT u.user_id, u.user_name, u.model_id, m.url, m.size, m.created_at
                FROM users u
                LEFT JOIN models m ON u.model_id = m.model_id
                WHERE u.user_id = ?
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {
            "user_id": int(row[0]),
            "user_name": row[1],
            "model_id": int(row[2]) if row[2] is not None else None,
            "model_url": row[3],
            "model_size_mb": float(row[4]) if row[4] is not None else None,
            "model_created_at": row[5],
        }
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to get user {user_id}: {exc}") from exc
