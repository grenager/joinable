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


def test_scrape_engine_attribute_dates() -> None:
    html = """
    <html><body>
      <div class="left blog">
        <div class="title entry-title">
          <a href="/sample-event/">Sample Event</a>
        </div>
        <div class="meta date-time" data-event-date="2026-07-09 19:30"
             data-event-date-end="2026-07-09 20:30">
          <span class="fc-event-start-time">7:30 pm</span>
          <span class="cost">Cost:</span>
          <span>Davies Symphony Hall</span>
        </div>
        <div class="thumbnail-wrapper">
          <noscript><img src="https://sf.funcheap.com/wp-content/uploads/poster.jpg" /></noscript>
        </div>
        <span class="cost">$99</span>
      </div>
    </body></html>
    """
    engine = ScrapeEngine()
    selectors = SourceSelectors(
        container="div.left.blog",
        title=".entry-title a",
        start=".meta.date-time",
        start_attribute="data-event-date",
        end=".meta.date-time",
        end_attribute="data-event-date-end",
        venue=".meta.date-time > span:not([class])",
        url=".entry-title a",
        image=".thumbnail-wrapper noscript img",
        price=".cost",
        date_format="%Y-%m-%d %H:%M",
    )
    events = engine.parse(html, "https://sf.funcheap.com", selectors)
    assert len(events) == 1
    assert events[0].title == "Sample Event"
    assert events[0].start_raw == "2026-07-09 19:30"
    assert events[0].end_raw == "2026-07-09 20:30"
    assert events[0].venue_name == "Davies Symphony Hall"
    assert events[0].external_url == "https://sf.funcheap.com/sample-event/"
    assert events[0].image_url == "https://sf.funcheap.com/wp-content/uploads/poster.jpg"


def test_scrape_engine_combine_preceding_date() -> None:
    html = """
    <html><body>
      <h2>Thursday, July 9, 2026</h2>
      <table>
        <tr id="post-1">
          <td>7:30 pm</td>
          <td><span class="entry-title"><a href="/event-1/">Table Event</a></span></td>
        </tr>
      </table>
    </body></html>
    """
    from joinable_core.schemas import CombineFieldSpec, FieldSpec, SourceProfile

    engine = ScrapeEngine()
    profile = SourceProfile(
        container='tr[id^="post-"]',
        title=".entry-title a",
        start=CombineFieldSpec(
            template="{day} {time}",
            parts={
                "day": FieldSpec(selector="h2", scope="preceding", match="202"),
                "time": FieldSpec(selector="td:first-child", scope="container"),
            },
        ),
        url=".entry-title a",
    )
    events = engine.parse_profile(html, "https://example.com", profile)
    assert len(events) == 1
    assert events[0].title == "Table Event"
    assert events[0].start_raw == "Thursday, July 9, 2026 7:30 pm"
    assert events[0].external_url == "https://example.com/event-1/"


def test_scrape_engine_profiles_dedupe() -> None:
    html = """
    <html><body>
      <div class="left blog">
        <div class="entry-title"><a href="/dup/">Dup Event</a></div>
        <div class="meta date-time" data-event-date="2026-07-09 19:30"></div>
      </div>
      <tr id="post-1">
        <td>7:30 pm</td>
        <td><span class="entry-title"><a href="/dup/">Dup Event</a></span></td>
      </tr>
    </body></html>
    """
    from joinable_core.schemas import HtmlCssConfig, SourceProfile

    config = HtmlCssConfig(
        profiles=[
            SourceProfile(
                container="div.left.blog",
                title=".entry-title a",
                start=".meta.date-time",
                start_attribute="data-event-date",
                url=".entry-title a",
                date_format="%Y-%m-%d %H:%M",
            ),
            SourceProfile(
                container='tr[id^="post-"]',
                title=".entry-title a",
                start="td:first-child",
                url=".entry-title a",
            ),
        ]
    )
    engine = ScrapeEngine()
    events = engine.parse_profile(html, "https://example.com", config.profiles[0])
    events.extend(engine.parse_profile(html, "https://example.com", config.profiles[1]))
    deduped = engine.dedupe_events(events)
    assert len(deduped) == 1
