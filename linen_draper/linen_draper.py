import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

import reflex as rx
import reflex_local_auth

from linen_draper.pages.dashboard import dashboard_page
from linen_draper.pages.settings import settings_page
from linen_draper.scraper import scrape_and_store
from linen_draper.emailer import send_daily_digest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def background_scrape_loop():
    while True:
        try:
            await scrape_and_store()
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
        try:
            await send_daily_digest()
        except Exception as e:
            logger.error(f"Daily digest failed: {e}")
        await asyncio.sleep(6 * 3600)


app = rx.App()

app.add_page(
    reflex_local_auth.pages.login_page,
    route=reflex_local_auth.routes.LOGIN_ROUTE,
    title="Login — Linen Draper",
)

app.add_page(
    reflex_local_auth.pages.register_page,
    route=reflex_local_auth.routes.REGISTER_ROUTE,
    title="Register — Linen Draper",
)

app.register_lifespan_task(background_scrape_loop)
