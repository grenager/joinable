from __future__ import annotations

from typing import TYPE_CHECKING, Any

from joinable_core.schemas import SourceSelectors
from joinable_core.scraper.engine import ScrapeEngine

if TYPE_CHECKING:
    from joinable_core.models import Source
    from joinable_core.schemas import RawScrapedEvent


class HtmlCssAdapter:
    """Fetch an HTML page and extract events using CSS selectors."""

    source_type = "html_css"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return SourceSelectors.model_validate(config).model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        selectors = SourceSelectors.model_validate(source.config)
        return ScrapeEngine().scrape(source.url, selectors, render_js=source.render_js)
