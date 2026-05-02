from typing import Optional

import reflex as rx
import reflex_local_auth
import sqlmodel

from linen_draper.models import UserInfo


class AuthState(reflex_local_auth.LocalAuthState):
    @rx.var(cache=True)
    def authenticated_user_info(self) -> Optional[UserInfo]:
        if self.authenticated_user.id < 0:
            return None
        with rx.session() as session:
            return session.exec(
                sqlmodel.select(UserInfo).where(
                    UserInfo.user_id == self.authenticated_user.id
                )
            ).one_or_none()

    def on_load(self):
        if not self.is_authenticated:
            return reflex_local_auth.LoginState.redir

    def do_logout(self):
        return reflex_local_auth.LocalAuthState.do_logout
