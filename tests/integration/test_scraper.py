"""Integration tests for the scraper with mocked HTTP responses."""

import pytest
import respx
import httpx
import sqlmodel

from linen_draper.scraper import (
    scrape_and_store,
    _scrape_rss,
    _scrape_html_pages,
    RSS_URL,
    NEWS_BASE,
)
from linen_draper.models import InterventionAlert


class TestScrapeRSS:
    @pytest.mark.asyncio
    async def test_matching_item_inserted(self, db_session, sample_rss_xml):
        with respx.mock as mock:
            mock.get(RSS_URL).mock(
                return_value=httpx.Response(200, text=sample_rss_xml)
            )

            async with httpx.AsyncClient() as client:
                await _scrape_rss(client)

        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()

        assert len(alerts) == 1
        assert "kea" in alerts[0].title
        assert "manual intervention" in alerts[0].title

    @pytest.mark.asyncio
    async def test_non_matching_items_filtered_out(self, db_session, sample_rss_xml):
        with respx.mock as mock:
            mock.get(RSS_URL).mock(
                return_value=httpx.Response(200, text=sample_rss_xml)
            )

            async with httpx.AsyncClient() as client:
                await _scrape_rss(client)

        # Only the "kea" item should be stored, not election results or iptables
        titles = [a.title for a in db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()]

        assert "election" not in " ".join(titles).lower()
        assert "iptables" not in " ".join(titles).lower()

    @pytest.mark.asyncio
    async def test_duplicate_guid_skipped(self, db_session, sample_rss_xml, make_alert):
        # Pre-insert an alert with the same GUID as the matching RSS item
        make_alert(
            title="kea >= 1:3.0.3-6 update requires manual intervention",
            link="https://archlinux.org/news/kea-requires-manual-intervention/",
            guid="tag:archlinux.org,2026-04-07:/news/kea-requires-manual-intervention/",
        )

        with respx.mock as mock:
            mock.get(RSS_URL).mock(
                return_value=httpx.Response(200, text=sample_rss_xml)
            )

            async with httpx.AsyncClient() as client:
                await _scrape_rss(client)

        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()

        assert len(alerts) == 1  # No duplicate added

    @pytest.mark.asyncio
    async def test_rss_fetch_error_handled(self, db_session):
        with respx.mock as mock:
            mock.get(RSS_URL).mock(
                return_value=httpx.Response(500)
            )

            async with httpx.AsyncClient() as client:
                await _scrape_rss(client)

        # No alerts, no crash
        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()
        assert len(alerts) == 0


class TestScrapeHTML:
    @pytest.mark.asyncio
    async def test_matching_html_item_inserted(self, db_session, sample_html_page):
        with respx.mock as mock:
            mock.get(NEWS_BASE).mock(
                return_value=httpx.Response(200, text=sample_html_page)
            )
            # Page 2 returns empty to stop pagination
            mock.get(f"{NEWS_BASE}?page=2").mock(
                return_value=httpx.Response(200, text="<html></html>")
            )

            async with httpx.AsyncClient() as client:
                await _scrape_html_pages(client)

        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()

        assert len(alerts) == 2  # kea + plasma (not election results)

        titles = [a.title for a in alerts]
        assert any("kea" in t for t in titles)
        assert any("Plasma" in t for t in titles)

    @pytest.mark.asyncio
    async def test_html_link_dedup(self, db_session, sample_html_page, make_alert):
        # Pre-insert alert with same link as one in the HTML
        make_alert(
            link="https://archlinux.org/news/kea-requires-manual-intervention/",
        )

        with respx.mock as mock:
            mock.get(NEWS_BASE).mock(
                return_value=httpx.Response(200, text=sample_html_page)
            )
            mock.get(f"{NEWS_BASE}?page=2").mock(
                return_value=httpx.Response(200, text="<html></html>")
            )

            async with httpx.AsyncClient() as client:
                await _scrape_html_pages(client)

        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()

        assert len(alerts) == 2  # 1 pre-existing + 1 new (plasma)

    @pytest.mark.asyncio
    async def test_cross_source_dedup(self, db_session, sample_rss_xml, sample_html_page, make_alert):
        # The RSS feed and HTML page both contain the kea item
        # The RSS scrape inserts by GUID, HTML scrape by link
        # If we run RSS first, then HTML, the HTML should skip the kea item
        # because its link already exists

        with respx.mock as mock:
            mock.get(RSS_URL).mock(
                return_value=httpx.Response(200, text=sample_rss_xml)
            )
            mock.get(NEWS_BASE).mock(
                return_value=httpx.Response(200, text=sample_html_page)
            )
            mock.get(f"{NEWS_BASE}?page=2").mock(
                return_value=httpx.Response(200, text="<html></html>")
            )

            await scrape_and_store()

        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()

        # kea from RSS + plasma from HTML = 2 (not 3)
        assert len(alerts) == 2

    @pytest.mark.asyncio
    async def test_html_network_error_handled(self, db_session):
        with respx.mock as mock:
            mock.get(NEWS_BASE).mock(
                return_value=httpx.Response(500)
            )

            async with httpx.AsyncClient() as client:
                await _scrape_html_pages(client)

        alerts = db_session.exec(
            sqlmodel.select(InterventionAlert)
        ).all()
        assert len(alerts) == 0
