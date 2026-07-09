from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from joinable_core.schemas import RawScrapedEvent, SourceSelectors
from joinable_core.scraper.normalize import extract_attr, extract_text, resolve_url
from joinable_core.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "JoinableBot/0.1 (+https://joinable.dev)",
    "Accept": "text/html,application/xhtml+xml",
}

SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"


class ScrapeEngine:
    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout
        settings = get_settings()
        self._scrapingbee_api_key = settings.scrapingbee_api_key
        self._scrapingbee_premium_proxy = settings.scrapingbee_premium_proxy
        self._scrapingbee_country_code = settings.scrapingbee_country_code

    def _fetch_via_scrapingbee(self, url: str, render_js: bool) -> str:
        params = {
            "api_key": self._scrapingbee_api_key,
            "url": url,
            "render_js": "true" if render_js else "false",
            "premium_proxy": "true" if self._scrapingbee_premium_proxy else "false",
        }
        if self._scrapingbee_country_code:
            params["country_code"] = self._scrapingbee_country_code
        with httpx.Client(timeout=self._timeout) as client:
            response = client.get(SCRAPINGBEE_URL, params=params)
            response.raise_for_status()
            return response.text

    def _fetch_direct(self, url: str) -> str:
        with httpx.Client(
            timeout=self._timeout, headers=DEFAULT_HEADERS, follow_redirects=True
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def fetch_html(self, url: str, render_js: bool = False) -> str:
        if self._scrapingbee_api_key:
            return self._fetch_via_scrapingbee(url, render_js)
        return self._fetch_direct(url)

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

    def scrape(
        self, url: str, selectors: SourceSelectors, render_js: bool = False
    ) -> list[RawScrapedEvent]:
        html = self.fetch_html(url, render_js=render_js)
        return self.parse(html, url, selectors)
