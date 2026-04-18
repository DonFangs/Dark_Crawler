CREATE TABLE IF NOT EXISTS sites (
    site_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT UNIQUE NOT NULL,
    status     TEXT,          -- 'working', 'dead', 'captcha', 'timeout', NULL = unseen
    title      TEXT,
    last_seen  DATETIME
);

CREATE TABLE IF NOT EXISTS links (
    from_site_id INTEGER,
    to_site_id   INTEGER,
    FOREIGN KEY(from_site_id) REFERENCES sites(site_id),
    FOREIGN KEY(to_site_id)   REFERENCES sites(site_id)
);
