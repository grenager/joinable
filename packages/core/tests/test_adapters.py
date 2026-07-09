from __future__ import annotations

from joinable_core.scraper.adapters.cityspark import detect_cityspark
from joinable_core.scraper.adapters.eventscom import detect_eventscom
from joinable_core.scraper.adapters.evvnt import detect_evvnt
from joinable_core.scraper.adapters.localist import detect_localist
from joinable_core.scraper.adapters.tribe import detect_tribe
from joinable_core.scraper.adapters.base import get_adapter, list_source_types


def test_list_source_types_includes_new_adapters() -> None:
    types = list_source_types()
    assert "cityspark" in types
    assert "eventscom" in types
    assert "tribe" in types
    assert "localist" in types


def test_get_adapter_cityspark() -> None:
    adapter = get_adapter("cityspark")
    assert adapter.source_type == "cityspark"
    config = adapter.validate_config(
        {
            "portal_slug": "MarinIndependent",
            "latitude": 37.9735,
            "longitude": -122.5311,
        }
    )
    assert config["portal_slug"] == "MarinIndependent"


def test_detect_evvnt_from_html() -> None:
    html = '<script>var evvnt_discovery_plugin = { publisher_id: 4298 };</script>'
    cfg = detect_evvnt(html)
    assert cfg is not None
    assert cfg.publisher_id == 4298


def test_detect_cityspark_from_html() -> None:
    html = '<script src="https://portal.cityspark.com/PortalScripts/MarinIndependent"></script>'
    cfg = detect_cityspark(html)
    assert cfg is not None
    assert cfg.portal_slug == "MarinIndependent"


def test_detect_eventscom_from_html() -> None:
    html = (
        '<script src="https://cw.events.com/edc-calendar.min.js"></script>'
        '<edc-calendar token="68b81b25-b6de-11eb-abbe-42010a0a0a0b"></edc-calendar>'
    )
    cfg = detect_eventscom(html)
    assert cfg is not None
    assert cfg.calendar_token == "68b81b25-b6de-11eb-abbe-42010a0a0a0b"


def test_detect_tribe_from_html() -> None:
    html = '<link href="/wp-json/tribe/events/v1/doc" rel="https://api.w.org/" />'
    cfg = detect_tribe(html, "https://demo.theeventscalendar.com/events/")
    assert cfg is not None
    assert cfg.base_url == "https://demo.theeventscalendar.com"


def test_detect_localist_from_html() -> None:
    html = '<script src="https://events.wfu.edu/api/2/events?pp=5"></script>'
    cfg = detect_localist(html, "https://events.wfu.edu/calendar/")
    assert cfg is not None
    assert cfg.calendar_url == "https://events.wfu.edu"
