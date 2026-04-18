from database.db import Database
from crawler.queue import UrlQueue
from crawler.fetcher import Fetcher
from crawler.parser import Parser
from crawler.safety import Safety
from network.transport_darkweb import DarkWebTransport

START_URLS = [
    "https://example.com",
]

def main():
    db = Database("crawler.db")
    db.init_schema()

    transport = DarkWebTransport()
    fetcher = Fetcher(transport)
    parser = Parser()
    safety = Safety()
    queue = UrlQueue(db)

    # Seed initial URLs
    for url in START_URLS:
        queue.add_url(url)

    while True:
        url = queue.get_next_url()
        if url is None:
            print("Queue empty, stopping.")
            break

        print(f"[CRAWL] {url}")
        html, status_code, error = fetcher.fetch(url)

        if error is not None:
            print(f"  -> error: {error}")
            db.update_site_status(url, status="dead")
            continue

        if not safety.is_safe_html(html):
            print("  -> unsafe content detected, marking as dead.")
            db.update_site_status(url, status="dead")
            continue

        if safety.is_captcha_page(html):
            print("  -> captcha detected, marking as captcha.")
            db.update_site_status(url, status="captcha")
            continue

        title = parser.extract_title(html)
        db.upsert_site(url, status="working", title=title)

        links = parser.extract_links(html, base_url=url)
        print(f"  -> found {len(links)} links")

        for link in links:
            if not safety.is_potentially_valid_url(link):
                continue
            db.ensure_site_exists(link)
            db.insert_link(from_url=url, to_url=link)
            queue.add_url(link)

if __name__ == "__main__":
    main()
