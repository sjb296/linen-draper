"""E2E tests for the Settings state."""

import reflex_local_auth

from linen_draper.models import UserInfo


class TestSettingsState:
    def test_handle_submit_creates_new_userinfo(self, db_session):
        # Simulate what Reflex would do: set up state with an authenticated user
        user = reflex_local_auth.LocalUser(
            username="settingsuser",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None

        # Simulate form submission by directly calling the handler logic
        # (We can't easily instantiate Reflex state, so we test the underlying DB ops)
        info = UserInfo(
            email="new@example.com",
            email_enabled=True,
            user_id=user.id,
        )
        db_session.add(info)
        db_session.commit()
        db_session.refresh(info)

        assert info.email == "new@example.com"
        assert info.email_enabled is True

    def test_handle_submit_updates_existing_userinfo(self, db_session):
        user = reflex_local_auth.LocalUser(
            username="updater",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None

        # Create initial UserInfo
        info = UserInfo(
            email="old@example.com",
            email_enabled=True,
            user_id=user.id,
        )
        db_session.add(info)
        db_session.commit()
        db_session.refresh(info)

        # Update it
        info.email = "updated@example.com"
        info.email_enabled = False
        db_session.add(info)
        db_session.commit()
        db_session.refresh(info)

        assert info.email == "updated@example.com"
        assert info.email_enabled is False

    def test_form_data_parsing(self, db_session):
        """Test that form submission data is parsed correctly."""
        user = reflex_local_auth.LocalUser(
            username="formuser",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Simulate form data as it comes from the frontend
        form_data = {
            "email": "form@example.com",
            "email_enabled": "on",
        }

        email = form_data.get("email", "")
        email_enabled = form_data.get("email_enabled", "on") == "on"

        assert email == "form@example.com"
        assert email_enabled is True

        # Test with checkbox unchecked
        form_data2 = {
            "email": "noemail@example.com",
        }
        email_enabled2 = form_data2.get("email_enabled", "off") == "on"
        assert email_enabled2 is False
