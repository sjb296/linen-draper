import reflex as rx

from linen_draper.state.auth import AuthState


def navbar() -> rx.Component:
    return rx.hstack(
        rx.heading("Linen Draper", size="5"),
        rx.spacer(),
        rx.link("Dashboard", href="/"),
        rx.link("Settings", href="/settings"),
        rx.text(AuthState.authenticated_user.username),
        rx.button("Logout", on_click=AuthState.do_logout, color_scheme="ruby"),  # type: ignore[arg-type]
        spacing="4",
        padding="1em",
        border_bottom="1px solid var(--gray-5)",
    )
