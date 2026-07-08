from __future__ import annotations

from joinable_core.schemas import SourceSelectors
from joinable_core.scraper.dedupe import compute_dedupe_hash
from joinable_core.scraper.engine import ScrapeEngine


def test_compute_dedupe_hash_stable() -> None:
    h1 = compute_dedupe_hash("Indie Night", "2026-07-08T20:00:00+00:00", "The Independent")
    h2 = compute_dedupe_hash("Indie Night", "2026-07-08T20:00:00+00:00", "The Independent")
    assert h1 == h2
    assert len(h1) == 64


def test_scrape_engine_parse_html() -> None:
    html = """
    <html><body>
      <div class="event">
        <h2>Live Band</h2>
        <span class="date">July 8, 2026 8:00 PM</span>
        <span class="venue">The Independent</span>
        <a href="/tickets/1">Tickets</a>
      </div>
    </body></html>
    """
    engine = ScrapeEngine()
    selectors = SourceSelectors(
        container=".event",
        title="h2",
        start=".date",
        venue=".venue",
        url="a",
    )
    events = engine.parse(html, "https://example.com", selectors)
    assert len(events) == 1
    assert events[0].title == "Live Band"
    assert events[0].venue_name == "The Independent"
    assert events[0].external_url == "https://example.com/tickets/1"
