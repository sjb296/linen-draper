
import reflex as rx
import sqlmodel

from linen_draper.models import UserInfo
from linen_draper.state.auth import AuthState


class SettingsState(AuthState):
    email: str = ""
    email_enabled: bool = True
    weekly_enabled: bool = False
    monthly_enabled: bool = False
    saved: bool = False

    def on_load(self):  # type: ignore[override]
        if not self.is_authenticated:
            return
        info = self.authenticated_user_info
        if info:
            self.email = info.email or ""
            self.email_enabled = info.email_enabled
            self.weekly_enabled = info.weekly_enabled
            self.monthly_enabled = info.monthly_enabled

    @rx.event
    def handle_submit(self, form_data: dict):
        if not self.is_authenticated:
            return
        self.email = form_data.get("email", "")
        self.email_enabled = form_data.get("email_enabled", "off") == "on"
        self.weekly_enabled = form_data.get("weekly_enabled", "off") == "on"
        self.monthly_enabled = form_data.get("monthly_enabled", "off") == "on"

        user_pk = self.authenticated_user.id
        assert user_pk is not None  # guaranteed by is_authenticated above

        with rx.session() as session:
            info = session.exec(
                sqlmodel.select(UserInfo).where(
                    UserInfo.user_id == user_pk
                )
            ).one_or_none()

            if info is None:
                info = UserInfo(
                    email=self.email,
                    email_enabled=self.email_enabled,
                    weekly_enabled=self.weekly_enabled,
                    monthly_enabled=self.monthly_enabled,
                    user_id=user_pk,
                )
            else:
                info.email = self.email
                info.email_enabled = self.email_enabled
                info.weekly_enabled = self.weekly_enabled
                info.monthly_enabled = self.monthly_enabled

            session.add(info)
            session.commit()

        self.saved = True
