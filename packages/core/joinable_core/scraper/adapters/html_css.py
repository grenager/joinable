from __future__ import annotations

from typing import TYPE_CHECKING, Any

from joinable_core.schemas import HtmlCssConfig
from joinable_core.scraper.engine import ScrapeEngine

if TYPE_CHECKING:
    from joinable_core.models import Source
    from joinable_core.schemas import RawScrapedEvent


class HtmlCssAdapter:
    """Fetch HTML calendar pages and extract events using declarative CSS config."""

    source_type = "html_css"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return HtmlCssConfig.from_raw(config).model_dump()

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        html_config = HtmlCssConfig.from_raw(source.config)
        return ScrapeEngine().scrape_config(source.url, html_config, render_js=source.render_js)
