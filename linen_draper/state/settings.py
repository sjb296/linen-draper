from typing import Optional

import reflex as rx
import sqlmodel

from linen_draper.models import UserInfo
from linen_draper.state.auth import AuthState


class SettingsState(AuthState):
    email: str = ""
    email_enabled: bool = True
    saved: bool = False

    def on_load(self):
        if not self.is_authenticated:
            return
        info = self.authenticated_user_info
        if info:
            self.email = info.email or ""
            self.email_enabled = info.email_enabled

    @rx.event
    def handle_submit(self, form_data: dict):
        if not self.is_authenticated:
            return
        self.email = form_data.get("email", "")
        self.email_enabled = form_data.get("email_enabled", "on") == "on"

        with rx.session() as session:
            info = session.exec(
                sqlmodel.select(UserInfo).where(
                    UserInfo.user_id == self.authenticated_user.id
                )
            ).one_or_none()

            if info is None:
                info = UserInfo(
                    email=self.email,
                    email_enabled=self.email_enabled,
                    user_id=self.authenticated_user.id,
                )
            else:
                info.email = self.email
                info.email_enabled = self.email_enabled

            session.add(info)
            session.commit()

        self.saved = True
