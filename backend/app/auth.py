import sqlite3
import logging
from datetime import datetime, timedelta

import bcrypt
import jwt

from app.config import settings

log = logging.getLogger(__name__)
DB_PATH = "users.db"


def init_users_db() -> None:
    """Create users table and seed default users on first run."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role     TEXT NOT NULL
        )
    """)
    con.commit()
    _seed_users(con)
    con.close()
    log.info("Users DB initialised.")


def _seed_users(con: sqlite3.Connection) -> None:
    """Seed three default users if they do not already exist."""
    seeds = [
        ("admin",    "HMAdmin@2024",    "admin"),
        ("faculty1", "HMFaculty@2024",  "faculty"),
        ("student1", "HMStudent@2024",  "student"),
    ]
    for username, password, role in seeds:
        existing = con.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not existing:
            hashed = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            con.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed, role),
            )
            log.info(f"Seeded user: {username} ({role})")
    con.commit()


def verify_user(username: str, password: str) -> dict | None:
    """Return { username, role } if credentials are valid, else None."""
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT password, role FROM users WHERE username = ?", (username,)
    ).fetchone()
    con.close()
    if not row:
        return None
    stored_hash, role = row
    if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        return {"username": username, "role": role}
    return None


def create_token(username: str, role: str) -> str:
    """Issue a signed JWT token."""
    payload = {
        "sub":  username,
        "role": role,
        "exp":  datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises jwt exceptions on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
