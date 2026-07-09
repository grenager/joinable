from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from joinable_core.models import Source
    from joinable_core.schemas import RawScrapedEvent


@runtime_checkable
class Adapter(Protocol):
    """A pluggable scraping strategy that produces normalized events.

    Every adapter turns a Source into a list of RawScrapedEvent, regardless of
    the underlying transport (HTML+CSS, JSON API, iCal, etc.). Adding support for
    a new calendar platform means adding one adapter and registering it below.
    """

    source_type: str

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate/normalize adapter-specific config; raise on invalid input."""

    def scrape(self, source: Source) -> list[RawScrapedEvent]:
        """Fetch and parse events for the given source."""


def get_adapter(source_type: str) -> Adapter:
    # Imported lazily to avoid import cycles (adapters import models/schemas).
    from joinable_core.scraper.adapters.evvnt import EvvntAdapter
    from joinable_core.scraper.adapters.html_css import HtmlCssAdapter

    registry: dict[str, Adapter] = {
        HtmlCssAdapter.source_type: HtmlCssAdapter(),
        EvvntAdapter.source_type: EvvntAdapter(),
    }
    adapter = registry.get(source_type)
    if adapter is None:
        raise ValueError(f"Unknown source_type: {source_type!r}")
    return adapter


def list_source_types() -> list[str]:
    return ["html_css", "evvnt"]
