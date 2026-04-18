import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA_FILE = Path(__file__).with_name("schema.sql")

class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def init_schema(self):
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        self.conn.executescript(schema_sql)
        self.conn.commit()

    def ensure_site_exists(self, url: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO sites (url) VALUES (?)",
            (url,),
        )
        self.conn.commit()

    def upsert_site(self, url: str, status: str | None, title: str | None):
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO sites (url, status, title, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                status=excluded.status,
                title=excluded.title,
                last_seen=excluded.last_seen
            """,
            (url, status, title, now),
        )
        self.conn.commit()

    def update_site_status(self, url: str, status: str):
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            UPDATE sites
            SET status = ?, last_seen = ?
            WHERE url = ?
            """,
            (status, now, url),
        )
        self.conn.commit()

    def get_site_id(self, url: str) -> int | None:
        cur = self.conn.execute(
            "SELECT site_id FROM sites WHERE url = ?",
            (url,),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def insert_link(self, from_url: str, to_url: str):
        from_id = self.get_site_id(from_url)
        to_id = self.get_site_id(to_url)
        if from_id is None or to_id is None:
            return
        self.conn.execute(
            "INSERT INTO links (from_site_id, to_site_id) VALUES (?, ?)",
            (from_id, to_id),
        )
        self.conn.commit()

    def get_next_unseen_url(self) -> str | None:
        cur = self.conn.execute(
            """
            SELECT url FROM sites
            WHERE status IS NULL
            ORDER BY site_id ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return row[0] if row else None
