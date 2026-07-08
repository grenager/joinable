from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup

from joinable_core.schemas import RawScrapedEvent, SourceSelectors
from joinable_core.scraper.normalize import extract_attr, extract_text, resolve_url

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "JoinableBot/0.1 (+https://joinable.dev)",
    "Accept": "text/html,application/xhtml+xml",
}


class ScrapeEngine:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def fetch_html(self, url: str) -> str:
        with httpx.Client(timeout=self._timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def parse(self, html: str, base_url: str, selectors: SourceSelectors) -> list[RawScrapedEvent]:
        soup = BeautifulSoup(html, "lxml")
        containers = soup.select(selectors.container)
        events: list[RawScrapedEvent] = []

        for container in containers:
            title = extract_text(container, selectors.title)
            start_raw = extract_text(container, selectors.start)
            if not title or not start_raw:
                continue

            end_raw = extract_text(container, selectors.end) if selectors.end else None
            venue_name = extract_text(container, selectors.venue) if selectors.venue else None
            description = extract_text(container, selectors.description) if selectors.description else None
            price_text = extract_text(container, selectors.price) if selectors.price else None

            external_url: str | None = None
            if selectors.url:
                href = extract_attr(container, selectors.url, selectors.url_attribute)
                external_url = resolve_url(base_url, href)

            image_url: str | None = None
            if selectors.image:
                image_url = extract_attr(container, selectors.image, "src")
                if image_url:
                    image_url = resolve_url(base_url, image_url)

            events.append(
                RawScrapedEvent(
                    title=title,
                    start_raw=start_raw,
                    end_raw=end_raw,
                    venue_name=venue_name,
                    external_url=external_url,
                    image_url=image_url,
                    price_text=price_text,
                    description=description,
                )
            )

        return events

    def scrape(self, url: str, selectors: SourceSelectors) -> list[RawScrapedEvent]:
        html = self.fetch_html(url)
        return self.parse(html, url, selectors)
