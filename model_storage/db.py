from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from model_storage.errors import DatabaseError

MAX_MODELS_PER_USER = 5


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_users_drop_legacy_model_id(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "users", "model_id"):
        return
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.executescript(
        """
        CREATE TABLE users_new (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            model_count INTEGER NOT NULL DEFAULT 0,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            password_hash TEXT,
            password_salt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO users_new (
            user_id, user_name, model_count, first_name, last_name, email,
            password_hash, password_salt, created_at
        )
        SELECT
            user_id,
            user_name,
            COALESCE(model_count, 0),
            first_name,
            last_name,
            email,
            password_hash,
            password_salt,
            created_at
        FROM users;

        DROP TABLE users;
        ALTER TABLE users_new RENAME TO users;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON;")


def init_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS models (
                model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                image_url TEXT,
                size REAL,
                user_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                model_count INTEGER NOT NULL DEFAULT 0,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                password_hash TEXT,
                password_salt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Backward-compatible migration for existing databases.
        _ensure_column(conn, "models", "user_id", "INT")
        _ensure_column(conn, "models", "image_url", "TEXT")
        _ensure_column(conn, "users", "first_name", "TEXT")
        _ensure_column(conn, "users", "last_name", "TEXT")
        _ensure_column(conn, "users", "email", "TEXT")
        _ensure_column(conn, "users", "password_hash", "TEXT")
        _ensure_column(conn, "users", "password_salt", "TEXT")
        _ensure_column(conn, "users", "created_at", "TIMESTAMP")
        _ensure_column(conn, "users", "model_count", "INTEGER")
        if _column_exists(conn, "users", "model_id"):
            conn.execute(
                """
                UPDATE models
                SET user_id = (
                    SELECT u.user_id
                    FROM users u
                    WHERE u.model_id = models.model_id
                    LIMIT 1
                )
                WHERE user_id IS NULL
                """
            )
        _migrate_users_drop_legacy_model_id(conn)
        conn.execute("UPDATE users SET model_count = 0 WHERE model_count IS NULL")
        conn.execute(
            """
            UPDATE users
            SET model_count = (
                SELECT COUNT(*)
                FROM models m
                WHERE m.user_id = users.user_id
            )
            """
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_models_user_id ON models(user_id)")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return digest.hex(), salt


def verify_password(password: str, expected_hash: str, salt: str) -> bool:
    computed_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(computed_hash, expected_hash)


def insert_model(
    db_path: Path,
    url: str,
    size_mb: float,
    user_id: int | None = None,
    image_url: str | None = None,
) -> int:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO models (url, image_url, size, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (url, image_url, size_mb, user_id, datetime.utcnow().isoformat()),
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

            cur = conn.execute(
                "INSERT INTO users (user_name, created_at, model_count) VALUES (?, ?, ?)",
                (user_name, datetime.utcnow().isoformat(), 0),
            )
            return int(cur.lastrowid)
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to ensure user record: {exc}") from exc


def create_auth_user(
    db_path: Path,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> dict[str, Any]:
    email = email.strip().lower()
    user_name = f"{first_name.strip()} {last_name.strip()}".strip()
    password_hash, password_salt = hash_password(password)

    try:
        with connect(db_path) as conn:
            existing = conn.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()
            if existing is not None:
                raise DatabaseError("Email already registered")

            cur = conn.execute(
                """
                INSERT INTO users (
                    user_name, first_name, last_name, email,
                    password_hash, password_salt, created_at, model_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_name,
                    first_name.strip(),
                    last_name.strip(),
                    email,
                    password_hash,
                    password_salt,
                    datetime.utcnow().isoformat(),
                    0,
                ),
            )
            user_id = int(cur.lastrowid)

        return {
            "user_id": user_id,
            "user_name": user_name,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "email": email,
        }
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, DatabaseError):
            raise
        raise DatabaseError(f"Failed to create auth user: {exc}") from exc


def get_auth_user_by_email(db_path: Path, email: str) -> dict[str, Any] | None:
    email = email.strip().lower()
    try:
        with connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT user_id, user_name, first_name, last_name, email, password_hash, password_salt
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
        if row is None:
            return None
        return {
            "user_id": int(row[0]),
            "user_name": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "email": row[4],
            "password_hash": row[5],
            "password_salt": row[6],
        }
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to get auth user by email: {exc}") from exc


def link_model_to_user(db_path: Path, user_id: int, model_id: int) -> None:
    try:
        with connect(db_path) as conn:
            row = conn.execute("SELECT model_count FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                raise DatabaseError(f"User {user_id} not found")
            current_count = int(row[0] or 0)
            if current_count >= MAX_MODELS_PER_USER:
                raise DatabaseError(f"User {user_id} reached max {MAX_MODELS_PER_USER} models")

            conn.execute(
                """
                UPDATE models
                SET user_id = ?
                WHERE model_id = ?
                """,
                (user_id, model_id),
            )
            conn.execute(
                """
                UPDATE users
                SET model_count = COALESCE(model_count, 0) + 1
                WHERE user_id = ?
                """,
                (user_id,),
            )
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, DatabaseError):
            raise
        raise DatabaseError(f"Failed to link model to user: {exc}") from exc


def assert_user_can_store_model(db_path: Path, user_id: int) -> None:
    try:
        with connect(db_path) as conn:
            row = conn.execute("SELECT model_count FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise DatabaseError(f"User {user_id} not found")
        current_count = int(row[0] or 0)
        if current_count >= MAX_MODELS_PER_USER:
            raise DatabaseError(f"User {user_id} reached max {MAX_MODELS_PER_USER} models")
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, DatabaseError):
            raise
        raise DatabaseError(f"Failed to validate user model limit: {exc}") from exc


def list_models(db_path: Path, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT model_id, url, image_url, size, user_id, created_at
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
                "image_url": row[2],
                "size_mb": float(row[3]) if row[3] is not None else None,
                "user_id": int(row[4]) if row[4] is not None else None,
                "created_at": row[5],
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
                SELECT model_id, url, image_url, size, user_id, created_at
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
            "image_url": row[2],
            "size_mb": float(row[3]) if row[3] is not None else None,
            "user_id": int(row[4]) if row[4] is not None else None,
            "created_at": row[5],
        }
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to get model {model_id}: {exc}") from exc


def list_users(db_path: Path, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT
                    u.user_id, u.user_name, u.first_name, u.last_name, u.email,
                    COALESCE(u.model_count, 0)
                FROM users u
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
                "first_name": row[2],
                "last_name": row[3],
                "email": row[4],
                "model_count": int(row[5]),
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
                SELECT
                    u.user_id, u.user_name, u.first_name, u.last_name, u.email,
                    COALESCE(u.model_count, 0)
                FROM users u
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
            "first_name": row[2],
            "last_name": row[3],
            "email": row[4],
            "model_count": int(row[5]),
        }
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to get user {user_id}: {exc}") from exc


def delete_model_for_user(db_path: Path, user_id: int, model_id: int) -> None:
    """Delete one model row only if it belongs to `user_id`. Updates `users.model_count`."""
    try:
        with connect(db_path) as conn:
            user_row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if user_row is None:
                raise DatabaseError(f"User {user_id} not found")

            row = conn.execute(
                "SELECT user_id FROM models WHERE model_id = ?",
                (model_id,),
            ).fetchone()
            if row is None:
                raise DatabaseError(f"Model {model_id} not found")

            owner_id = row[0]
            if owner_id is None:
                raise DatabaseError(f"Model {model_id} is not linked to any user")
            if int(owner_id) != user_id:
                raise DatabaseError(f"Model {model_id} does not belong to user {user_id}")

            conn.execute("DELETE FROM models WHERE model_id = ?", (model_id,))
            conn.execute(
                """
                UPDATE users
                SET model_count = (
                    SELECT COUNT(*) FROM models m WHERE m.user_id = users.user_id
                )
                WHERE user_id = ?
                """,
                (user_id,),
            )
    except sqlite3.DatabaseError as exc:
        if isinstance(exc, DatabaseError):
            raise
        raise DatabaseError(f"Failed to delete model {model_id}: {exc}") from exc


def list_models_by_user(db_path: Path, user_id: int, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                """
                SELECT model_id, url, image_url, size, user_id, created_at
                FROM models
                WHERE user_id = ?
                ORDER BY model_id DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )
            rows = cur.fetchall()
        return [
            {
                "model_id": int(row[0]),
                "url": row[1],
                "image_url": row[2],
                "size_mb": float(row[3]) if row[3] is not None else None,
                "user_id": int(row[4]) if row[4] is not None else None,
                "created_at": row[5],
            }
            for row in rows
        ]
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Failed to list models for user {user_id}: {exc}") from exc
