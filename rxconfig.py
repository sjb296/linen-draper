import os

import reflex as rx

config = rx.Config(
    app_name="linen_draper",
    db_url=os.environ.get("DATABASE_URL", "sqlite:///reflex.db"),
    api_url=os.environ.get("API_URL", ""),
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)
