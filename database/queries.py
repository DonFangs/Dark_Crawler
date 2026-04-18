from collections import deque
from typing import Dict, List, Optional, Tuple

from database.db_manager import Database


def top_linked_domains(db: Database, limit: int = 20) -> List[Tuple[str, int]]:
    """Return domains with the highest incoming link count."""
    cur = db.conn.execute(
        "SELECT target_domain, in_degree FROM domain_in_degree ORDER BY in_degree DESC LIMIT ?",
        (limit,),
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def top_linking_domains(db: Database, limit: int = 20) -> List[Tuple[str, int]]:
    """Return domains with the highest outgoing link count."""
    cur = db.conn.execute(
        "SELECT source_domain, out_degree FROM domain_out_degree ORDER BY out_degree DESC LIMIT ?",
        (limit,),
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def find_path(db: Database, from_domain: str, to_domain: str) -> Optional[List[str]]:
    """Return the shortest domain-level path between two domains."""
    from_domain = from_domain.lower().strip()
    to_domain = to_domain.lower().strip()
    if from_domain == to_domain:
        return [from_domain]

    cur = db.conn.execute(
        "SELECT from_domain, to_domain FROM domain_graph_edges",
    )
    graph: Dict[str, List[str]] = {}
    for row in cur.fetchall():
        graph.setdefault(row[0], []).append(row[1])

    queue = deque([[from_domain]])
    visited = {from_domain}
    while queue:
        path = queue.popleft()
        current = path[-1]
        for neighbor in graph.get(current, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            candidate = path + [neighbor]
            if neighbor == to_domain:
                return candidate
            queue.append(candidate)
    return None


def get_domain_neighbors(db: Database, domain: str, direction: str = "both") -> List[str]:
    """Return the neighboring domains for a given domain."""
    domain = domain.lower().strip()
    neighbors: List[str] = []
    if direction in ("out", "both"):
        cur = db.conn.execute(
            "SELECT to_domain FROM domain_graph_edges WHERE from_domain = ?",
            (domain,),
        )
        neighbors.extend(row[0] for row in cur.fetchall())
    if direction in ("in", "both"):
        cur = db.conn.execute(
            "SELECT from_domain FROM domain_graph_edges WHERE to_domain = ?",
            (domain,),
        )
        neighbors.extend(row[0] for row in cur.fetchall())
    return list(dict.fromkeys(neighbors))


def get_crawl_session_summary(db: Database, session_id: int) -> Optional[Dict[str, object]]:
    """Return the statistics stored for a crawl session."""
    cur = db.conn.execute(
        "SELECT * FROM crawl_sessions WHERE id = ?",
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "transport_type": row["transport_type"],
        "seed_urls": row["seed_urls"],
        "max_depth": row["max_depth"],
        "max_pages": row["max_pages"],
        "pages_crawled": row["pages_crawled"],
        "pages_failed": row["pages_failed"],
        "links_discovered": row["links_discovered"],
        "new_domains_found": row["new_domains_found"],
        "status": row["status"],
    }


def domain_timeline(db: Database, domain: str) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Return crawl history for pages within a domain."""
    domain = domain.lower().strip()
    cur = db.conn.execute(
        "SELECT p.url, p.status, p.last_crawled FROM pages p JOIN domains d ON p.domain_id = d.id WHERE d.domain = ? ORDER BY p.last_crawled ASC",
        (domain,),
    )
    return [(row[0], row[1], row[2]) for row in cur.fetchall()]


def orphan_pages(db: Database) -> List[Tuple[int, str]]:
    """Return pages with no incoming or outgoing links."""
    cur = db.conn.execute(
        """
        SELECT p.id, p.url
        FROM pages p
        LEFT JOIN links l_from ON p.id = l_from.from_page_id
        LEFT JOIN links l_to ON p.id = l_to.to_page_id
        WHERE l_from.id IS NULL AND l_to.id IS NULL
        """,
    )
    return [(row[0], row[1]) for row in cur.fetchall()]
