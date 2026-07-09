from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from joinable_core.schemas import HtmlCssConfig, RawScrapedEvent, SourceProfile, SourceSelectors
from joinable_core.scraper.classifier import tags_from_html_classes
from joinable_core.scraper.fields import extract_field
from joinable_core.scraper.normalize import extract_attr, resolve_url
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

    def parse_profile(
        self, html: str, base_url: str, profile: SourceProfile
    ) -> list[RawScrapedEvent]:
        soup = BeautifulSoup(html, "lxml")
        containers = soup.select(profile.container)
        events: list[RawScrapedEvent] = []

        for container in containers:
            title = extract_field(container, profile.title)
            start_raw = extract_field(
                container,
                profile.start,
                legacy_attribute=profile.start_attribute if isinstance(profile.start, str) else None,
            )
            if not title or not start_raw:
                continue

            end_raw = extract_field(
                container,
                profile.end,
                legacy_attribute=profile.end_attribute if isinstance(profile.end, str) else None,
            )
            venue_name = extract_field(container, profile.venue)
            description = extract_field(container, profile.description)
            price_text = extract_field(container, profile.price)

            external_url: str | None = None
            if profile.url is not None:
                if isinstance(profile.url, str):
                    href = extract_attr(container, profile.url, profile.url_attribute)
                else:
                    href = extract_field(container, profile.url)
                external_url = resolve_url(base_url, href)

            image_url: str | None = None
            if profile.image is not None:
                if isinstance(profile.image, str):
                    image_url = extract_attr(container, profile.image, "src")
                else:
                    image_url = extract_field(container, profile.image)
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
                    date_format=profile.date_format,
                    source_tags=tags_from_html_classes(container),
                )
            )

        return events

    def parse(self, html: str, base_url: str, selectors: SourceSelectors) -> list[RawScrapedEvent]:
        profile = SourceProfile.model_validate(selectors.model_dump())
        return self.parse_profile(html, base_url, profile)

    @staticmethod
    def dedupe_events(events: list[RawScrapedEvent]) -> list[RawScrapedEvent]:
        seen: set[str] = set()
        unique: list[RawScrapedEvent] = []
        for event in events:
            key = event.external_url or f"{event.title}|{event.start_raw}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
        return unique

    def _next_page_url(self, html: str, base_url: str, config: HtmlCssConfig) -> str | None:
        if config.pagination is None:
            return None
        soup = BeautifulSoup(html, "lxml")
        link = soup.select_one(config.pagination.next)
        if link is None:
            return None
        href = link.get(config.pagination.url_attribute)
        if not isinstance(href, str) or not href.strip():
            return None
        return resolve_url(base_url, href.strip())

    def scrape_config(
        self, url: str, config: HtmlCssConfig, render_js: bool = False
    ) -> list[RawScrapedEvent]:
        max_pages = config.pagination.max_pages if config.pagination is not None else 1
        all_events: list[RawScrapedEvent] = []
        page_url: str | None = url
        pages_fetched = 0

        while page_url is not None and pages_fetched < max_pages:
            html = self.fetch_html(page_url, render_js=render_js)
            for profile in config.profiles:
                all_events.extend(self.parse_profile(html, page_url, profile))
            pages_fetched += 1
            if config.pagination is None or pages_fetched >= max_pages:
                break
            page_url = self._next_page_url(html, page_url, config)

        return self.dedupe_events(all_events)

    def scrape(
        self, url: str, selectors: SourceSelectors, render_js: bool = False
    ) -> list[RawScrapedEvent]:
        config = HtmlCssConfig.from_raw(selectors.model_dump())
        return self.scrape_config(url, config, render_js=render_js)
