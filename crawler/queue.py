from database.db import Database

class UrlQueue:
    """
    Very simple queue backed by the database's 'sites' table.
    v0.1: pick the next site with NULL status.
    """

    def __init__(self, db: Database):
        self.db = db

    def add_url(self, url: str):
        self.db.ensure_site_exists(url)

    def get_next_url(self) -> str | None:
        return self.db.get_next_unseen_url()
