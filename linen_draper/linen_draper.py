import asyncio
import logging

import reflex as rx
import reflex_local_auth
from dotenv import load_dotenv

from linen_draper.emailer import send_daily_digest
from linen_draper.pages.dashboard import dashboard_page  # noqa: F401
from linen_draper.pages.settings import settings_page  # noqa: F401
from linen_draper.scraper import scrape_and_store

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def background_scrape_loop():
    scrape_interval = 6 * 3600
    try:
        while True:
            try:
                await scrape_and_store()
            except Exception as e:
                logger.error(f"Scrape failed: {e}")
            try:
                await send_daily_digest()
            except Exception as e:
                logger.error(f"Daily digest failed: {e}")
            # Sleep in 30-second chunks so hot-reload cancellation is responsive
            for _ in range(scrape_interval // 30):
                await asyncio.sleep(30)
    except asyncio.CancelledError:
        logger.info("Background scrape loop cancelled, shutting down gracefully")


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
