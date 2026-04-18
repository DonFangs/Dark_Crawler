CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    is_onion INTEGER NOT NULL DEFAULT 0,
    onion_version INTEGER,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    last_status TEXT,
    times_seen INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS crawl_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    transport_type TEXT NOT NULL,
    seed_urls TEXT,
    max_depth INTEGER,
    max_pages INTEGER,
    pages_crawled INTEGER NOT NULL DEFAULT 0,
    pages_failed INTEGER NOT NULL DEFAULT 0,
    links_discovered INTEGER NOT NULL DEFAULT 0,
    new_domains_found INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    url TEXT NOT NULL UNIQUE,
    path TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    http_status_code INTEGER,
    content_hash TEXT,
    page_size_bytes INTEGER,
    server_header TEXT,
    crawl_depth INTEGER NOT NULL DEFAULT 0,
    first_seen TIMESTAMP NOT NULL,
    last_crawled TIMESTAMP,
    crawl_count INTEGER NOT NULL DEFAULT 0,
    session_id INTEGER REFERENCES crawl_sessions(id)
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    to_page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    anchor_text TEXT,
    discovered_at TIMESTAMP NOT NULL,
    session_id INTEGER REFERENCES crawl_sessions(id),
    UNIQUE(from_page_id, to_page_id)
);

CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_page_id);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_page_id);
CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain_id);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
CREATE INDEX IF NOT EXISTS idx_domains_domain ON domains(domain);
CREATE INDEX IF NOT EXISTS idx_domains_onion ON domains(is_onion);
CREATE INDEX IF NOT EXISTS idx_domains_status ON domains(last_status);

CREATE VIEW IF NOT EXISTS domain_in_degree AS
SELECT
    d_target.domain AS target_domain,
    COUNT(DISTINCT d_source.domain) AS in_degree
FROM links l
JOIN pages p_target ON l.to_page_id = p_target.id
JOIN domains d_target ON p_target.domain_id = d_target.id
JOIN pages p_source ON l.from_page_id = p_source.id
JOIN domains d_source ON p_source.domain_id = d_source.id
GROUP BY d_target.domain;

CREATE VIEW IF NOT EXISTS domain_out_degree AS
SELECT
    d_source.domain AS source_domain,
    COUNT(DISTINCT d_target.domain) AS out_degree
FROM links l
JOIN pages p_source ON l.from_page_id = p_source.id
JOIN domains d_source ON p_source.domain_id = d_source.id
JOIN pages p_target ON l.to_page_id = p_target.id
JOIN domains d_target ON p_target.domain_id = d_target.id
GROUP BY d_source.domain;

CREATE VIEW IF NOT EXISTS hub_domains AS
SELECT
    in_deg.target_domain AS domain,
    in_deg.in_degree,
    out_deg.out_degree
FROM domain_in_degree in_deg
JOIN domain_out_degree out_deg
    ON in_deg.target_domain = out_deg.source_domain;

CREATE VIEW IF NOT EXISTS isolated_domains AS
SELECT d.domain
FROM domains d
LEFT JOIN domain_in_degree indeg ON indeg.target_domain = d.domain
LEFT JOIN domain_out_degree outdeg ON outdeg.source_domain = d.domain
WHERE indeg.in_degree IS NULL AND outdeg.out_degree IS NULL;

CREATE VIEW IF NOT EXISTS domain_graph_edges AS
SELECT
    d_source.domain AS from_domain,
    d_target.domain AS to_domain,
    COUNT(*) AS link_count
FROM links l
JOIN pages p_source ON l.from_page_id = p_source.id
JOIN domains d_source ON p_source.domain_id = d_source.id
JOIN pages p_target ON l.to_page_id = p_target.id
JOIN domains d_target ON p_target.domain_id = d_target.id
GROUP BY d_source.domain, d_target.domain;
