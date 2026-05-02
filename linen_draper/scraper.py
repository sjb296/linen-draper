import logging
import re
from datetime import datetime

import httpx
import feedparser
import reflex as rx
import sqlmodel
from sqlalchemy import select

from linen_draper.models import InterventionAlert

logger = logging.getLogger(__name__)

RSS_URL = "https://archlinux.org/feeds/news/"
NEWS_BASE = "https://archlinux.org/news/"

MANUAL_INTERVENTION_RE = re.compile(r"manual intervention", re.IGNORECASE)


async def scrape_and_store():
    logger.info("Starting Arch Linux news scrape")
    async with httpx.AsyncClient(timeout=30) as client:
        await _scrape_rss(client)
        await _scrape_html_pages(client)
    logger.info("Scrape complete")


async def _scrape_rss(client: httpx.AsyncClient):
    logger.info("Scraping RSS feed")
    try:
        resp = await client.get(RSS_URL)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch RSS feed: {e}")
        return

    feed = feedparser.parse(resp.text)
    new_count = 0

    for entry in feed.entries:
        title = entry.get("title", "")
        if not MANUAL_INTERVENTION_RE.search(title):
            continue

        guid = entry.get("id", "")
        link = entry.get("link", "")
        description = entry.get("description", "")
        pub_date_str = entry.get("published", "")

        pub_date = None
        if pub_date_str:
            try:
                from email.utils import parsedate_to_datetime
                pub_date = parsedate_to_datetime(pub_date_str)
            except Exception:
                pass

        with rx.session() as session:
            existing = session.exec(
                select(InterventionAlert).where(
                    InterventionAlert.guid == guid
                )
            ).first()
            if existing:
                continue

            alert = InterventionAlert(
                title=title,
                link=link,
                description=description,
                pub_date=pub_date or datetime.utcnow(),
                guid=guid,
            )
            session.add(alert)
            session.commit()
            new_count += 1
            logger.info(f"RSS: added alert: {title}")

    logger.info(f"RSS scrape: {new_count} new alerts")


async def _scrape_html_pages(client: httpx.AsyncClient):
    logger.info("Scraping HTML news pages")
    new_count = 0

    for page_num in range(1, 15):
        url = f"{NEWS_BASE}?page={page_num}" if page_num > 1 else NEWS_BASE
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            continue

        html = resp.text

        rows = re.findall(
            r'<tr>\s*<td>(.*?)</td>\s*<td>\s*<a\s+href="([^"]+)">([^<]+)</a>\s*</td>\s*<td[^>]*>(.*?)</td>\s*</tr>',
            html,
            re.DOTALL,
        )

        if not rows:
            break

        for date_str, link, title, author in rows:
            if not MANUAL_INTERVENTION_RE.search(title):
                continue

            title = title.strip()
            link = f"https://archlinux.org{link}" if link.startswith("/") else link
            date_str = date_str.strip()

            pub_date = None
            if date_str:
                try:
                    pub_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass

            with rx.session() as session:
                existing = session.exec(
                    select(InterventionAlert).where(
                        InterventionAlert.link == link
                    )
                ).first()
                if existing:
                    continue

                alert = InterventionAlert(
                    title=title,
                    link=link,
                    description="",
                    pub_date=pub_date or datetime.utcnow(),
                    guid=None,
                )
                session.add(alert)
                session.commit()
                new_count += 1
                logger.info(f"HTML: added alert: {title}")

    logger.info(f"HTML scrape: {new_count} new alerts")
