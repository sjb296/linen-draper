import reflex as rx
import reflex_local_auth

from linen_draper.state.settings import SettingsState
from linen_draper.components.navbar import navbar


@rx.page(route="/settings", title="Settings — Linen Draper", on_load=SettingsState.on_load)  # type: ignore[arg-type]
@reflex_local_auth.require_login
def settings_page() -> rx.Component:
    return rx.fragment(
        navbar(),
        rx.container(
            rx.vstack(
                rx.heading("Settings", size="5"),
                rx.form(
                    rx.vstack(
                        rx.text("Email"),
                        rx.input(
                            name="email",
                            placeholder="you@example.com",
                            default_value=SettingsState.email,
                            type="email",
                            width="100%",
                        ),
                        rx.checkbox(
                            "Enable daily email reports",
                            name="email_enabled",
                            default_checked=SettingsState.email_enabled,
                        ),
                        rx.button("Save", type="submit", width="100%"),
                        rx.cond(
                            SettingsState.saved,
                            rx.callout("Settings saved.", icon="check", color_scheme="green"),
                        ),
                        spacing="4",
                        min_width="300px",
                    ),
                    on_submit=SettingsState.handle_submit,
                ),
                spacing="4",
                align="start",
            ),
            padding_top="2em",
        ),
    )
