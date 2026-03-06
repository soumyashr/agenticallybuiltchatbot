import sqlite3
import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)
DB_PATH = "documents.db"


def init_db() -> None:
    """Create documents table if it does not exist."""
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL,
            display_name  TEXT NOT NULL,
            allowed_roles TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'UPLOADED',
            chunk_count   INTEGER NOT NULL DEFAULT 0,
            file_size     INTEGER NOT NULL DEFAULT 0,
            uploaded_at   TEXT NOT NULL DEFAULT (datetime('now')),
            ingested_at   TEXT,
            error_msg     TEXT
        )
    """)
    con.commit()
    con.close()
    log.info("Documents DB initialised.")


def _row_to_dict(row: tuple) -> dict:
    cols = [
        "id", "filename", "display_name", "allowed_roles",
        "status", "chunk_count", "file_size",
        "uploaded_at", "ingested_at", "error_msg",
    ]
    d = dict(zip(cols, row))
    d["allowed_roles"] = json.loads(d["allowed_roles"])
    return d


def register_document(
    filename: str,
    display_name: str,
    allowed_roles: list[str],
    file_size: int,
) -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        """INSERT INTO documents (filename, display_name, allowed_roles, file_size)
           VALUES (?, ?, ?, ?)""",
        (filename, display_name, json.dumps(allowed_roles), file_size),
    )
    doc_id = cur.lastrowid
    con.commit()
    con.close()
    return doc_id


def get_all_documents() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT * FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    con.close()
    return [_row_to_dict(r) for r in rows]


def get_pending_documents() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT * FROM documents WHERE status = 'UPLOADED'"
    ).fetchall()
    con.close()
    return [_row_to_dict(r) for r in rows]


def get_ingested_documents() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT * FROM documents WHERE status = 'INGESTED'"
    ).fetchall()
    con.close()
    return [_row_to_dict(r) for r in rows]


def get_allowed_roles_map() -> dict[str, list[str]]:
    """Returns { filename: [roles] } for all INGESTED documents."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT filename, allowed_roles FROM documents WHERE status = 'INGESTED'"
    ).fetchall()
    con.close()
    return {row[0]: json.loads(row[1]) for row in rows}


def set_status_ingesting(doc_id: int) -> None:
    _update_status(doc_id, "INGESTING")


def set_status_ingested(doc_id: int, chunk_count: int) -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE documents SET status='INGESTED', chunk_count=?, ingested_at=? WHERE id=?",
        (chunk_count, datetime.utcnow().isoformat(), doc_id),
    )
    con.commit()
    con.close()


def set_status_failed(doc_id: int, error: str) -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE documents SET status='FAILED', error_msg=? WHERE id=?",
        (error, doc_id),
    )
    con.commit()
    con.close()


def delete_document(doc_id: int) -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    con.commit()
    con.close()


def _update_status(doc_id: int, status: str) -> None:
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE documents SET status=? WHERE id=?", (status, doc_id))
    con.commit()
    con.close()
