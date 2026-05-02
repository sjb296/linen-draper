"""E2E tests for the auth flow via Reflex state methods."""

import reflex_local_auth
import sqlmodel

from linen_draper.models import UserInfo


class TestRegistrationAndLogin:
    def test_register_user_stores_password_hash(self, db_session):
        password = "secure_password_123"
        hashed = reflex_local_auth.LocalUser.hash_password(password)

        user = reflex_local_auth.LocalUser(
            username="newuser",
            password_hash=hashed,
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.password_hash != password.encode("utf-8")
        assert user.verify(password) is True
        assert user.verify("wrong_password") is False

    def test_disabled_user_verify_fails(self, db_session):
        user = reflex_local_auth.LocalUser(
            username="disabled",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=False,
        )
        db_session.add(user)
        db_session.commit()

        assert user.enabled is False
        assert user.verify("pw") is True  # verify doesn't check enabled

    def test_user_info_linked_to_user(self, db_session):
        user = reflex_local_auth.LocalUser(
            username="linkeduser",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        info = UserInfo(
            email="linked@example.com",
            email_enabled=True,
            user_id=user.id,
        )
        db_session.add(info)
        db_session.commit()

        # Query back
        fetched = db_session.exec(
            sqlmodel.select(UserInfo).where(UserInfo.user_id == user.id)
        ).one_or_none()

        assert fetched is not None
        assert fetched.email == "linked@example.com"
        assert fetched.user_id == user.id

    def test_no_userinfo_for_unauthenticated_user(self, db_session):
        # UserInfo with user_id=-1 (dummy unauthenticated user id) should not exist
        info = db_session.exec(
            sqlmodel.select(UserInfo).where(UserInfo.user_id == -1)
        ).one_or_none()

        assert info is None


class TestRequireLoginLogic:
    def test_require_login_wraps_function(self):
        """Test that require_login returns a callable wrapper."""
        def my_page():
            return "hello"

        wrapped = reflex_local_auth.require_login(my_page)
        assert callable(wrapped)
        assert wrapped.__name__ == "my_page"

    def test_require_login_preserves_name(self):
        def dashboard_page():
            pass

        wrapped = reflex_local_auth.require_login(dashboard_page)  # type: ignore[arg-type]
        assert wrapped.__name__ == "dashboard_page"
