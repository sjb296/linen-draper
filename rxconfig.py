import reflex as rx

config = rx.Config(
    app_name="linen_draper",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)