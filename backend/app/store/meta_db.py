import sqlite3
import threading
from app.config import get_settings
_settings = get_settings()
_lock = threading.Lock()
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_settings.meta_db_path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c
def init_db() -> None:
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            doc_name TEXT NOT NULL,
            dept TEXT NOT NULL DEFAULT 'public',
            status TEXT NOT NULL DEFAULT 'pending',
            uploader TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
def add_document(doc_id: str, doc_name: str, dept: str = "public", uploader: str = "") -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO documents(doc_id, doc_name, dept, uploader) VALUES(?,?,?,?)",
            (doc_id, doc_name, dept, uploader),
        )
def list_documents() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
def set_status(doc_id: str, status: str) -> None:
    with _lock, _conn() as c:
        c.execute("UPDATE documents SET status=? WHERE doc_id=?", (status, doc_id))
def delete_document(doc_id: str) -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
