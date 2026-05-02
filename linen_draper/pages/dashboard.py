import reflex as rx
import reflex_local_auth

from linen_draper.state.dashboard import DashboardState
from linen_draper.components.navbar import navbar


@rx.page(route="/", title="Linen Draper — Arch Linux Intervention Alerts", on_load=DashboardState.on_load)  # type: ignore[arg-type]
@reflex_local_auth.require_login
def dashboard_page() -> rx.Component:
    return rx.fragment(
        navbar(),
        rx.container(
            rx.vstack(
                rx.cond(
                    DashboardState.alerts.length() == 0,  # type: ignore[attr-defined]
                    rx.callout(
                        "No alerts yet. The scraper will check for Arch Linux news requiring manual intervention.",
                        icon="info",
                    ),
                ),
                rx.foreach(
                    DashboardState.alerts,
                    lambda alert: rx.card(
                        rx.vstack(
                            rx.link(
                                rx.heading(alert["title"], size="3"),
                                href=alert["link"],
                                is_external=True,
                            ),
                            rx.text(alert["pub_date"], color_scheme="gray"),
                            rx.cond(
                                alert["description"] != "",
                                rx.markdown(alert["description"]),
                            ),
                            spacing="2",
                            align="start",
                        ),
                    ),
                ),
                spacing="4",
                width="100%",
            ),
            padding_top="2em",
        ),
    )
