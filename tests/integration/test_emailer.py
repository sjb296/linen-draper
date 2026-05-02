"""Integration tests for the email system. CRITICAL: covers local + production paths."""

import datetime
from datetime import timezone

import pytest
import reflex_local_auth

from linen_draper.emailer import send_daily_digest


class TestSendDailyDigestLocalMode:
    @pytest.mark.asyncio
    async def test_no_alerts_returns_early(self, db_session, email_tmp_dir, clean_env, caplog):
        await send_daily_digest()

        assert "No alerts to send" in caplog.text

    @pytest.mark.asyncio
    async def test_no_enabled_users_returns_early(self, db_session, make_alert, email_tmp_dir, clean_env, caplog):
        make_alert()

        await send_daily_digest()

        assert "No users with email enabled" in caplog.text

    @pytest.mark.asyncio
    async def test_disabled_user_skipped(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        make_alert()
        make_user(email_enabled=False)

        await send_daily_digest()

        assert "No users with email enabled" in caplog.text

    @pytest.mark.asyncio
    async def test_one_alert_one_user_writes_file(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        make_alert(
            title="Test intervention alert",
            link="https://archlinux.org/news/test/",
            pub_date=datetime.datetime(2026, 4, 7),
        )
        user, info = make_user(email="recipient@example.com")

        await send_daily_digest()

        latest = email_tmp_dir / "latest.html"
        assert latest.exists()
        content = latest.read_text()
        assert "Test intervention alert" in content
        assert "Hello testuser1" in content
        assert "archlinux.org/news/test/" in content

    @pytest.mark.asyncio
    async def test_multiple_users_each_get_email(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        make_alert(title="Alert for everyone",
                   link="https://archlinux.org/news/everyone/")
        make_user(username="alice", email="alice@example.com")
        make_user(username="bob", email="bob@example.com")

        await send_daily_digest()

        # Both users should be logged
        assert "Would send" in caplog.text
        assert "alice@example.com" in caplog.text
        assert "bob@example.com" in caplog.text

    @pytest.mark.asyncio
    async def test_last_email_sent_at_updated(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        import sqlmodel
        from linen_draper.models import UserInfo

        make_alert()
        make_user(username="email_test_user", email="email_test@example.com")

        # Get the persistent user_id from this session
        fresh_user = db_session.exec(
            sqlmodel.select(reflex_local_auth.LocalUser).where(
                reflex_local_auth.LocalUser.username == "email_test_user"
            )
        ).one()

        await send_daily_digest()

        # Re-query UserInfo to verify timestamp was set
        fresh_info = db_session.exec(
            sqlmodel.select(UserInfo).where(UserInfo.user_id == fresh_user.id)
        ).one()
        assert fresh_info.last_email_sent_at is not None

    @pytest.mark.asyncio
    async def test_no_new_alerts_since_last_send_skipped(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        import asyncio
        make_alert()
        user, info = make_user()

        await asyncio.sleep(0.1)

        # First run: email sent, timestamp set
        await send_daily_digest()
        assert "Would send" in caplog.text

        caplog.clear()

        # Second run: no new alerts since last send
        await send_daily_digest()

        # Should skip this user
        assert "No new alerts for" in caplog.text

    @pytest.mark.asyncio
    async def test_new_alerts_since_last_send_sent(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        make_alert(title="Old alert",
                            created_at=datetime.datetime(2026, 1, 1, tzinfo=timezone.utc))
        user, info = make_user()

        # Set last_email_sent_at to after alert1 but before alert2
        info.last_email_sent_at = datetime.datetime(2026, 3, 1, tzinfo=timezone.utc)
        db_session.add(info)
        db_session.commit()

        # Create a new alert after the last send time
        make_alert(
            title="New intervention alert",
            link="https://archlinux.org/news/new-alert/",
            created_at=datetime.datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        await send_daily_digest()

        latest = email_tmp_dir / "latest.html"
        content = latest.read_text()
        # Should contain the new alert but not the old one
        assert "New intervention alert" in content
        assert "Old alert" not in content

    @pytest.mark.asyncio
    async def test_email_contains_user_specific_greeting(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        make_alert()
        user, info = make_user(username="archfan42", email="archfan@example.com")

        await send_daily_digest()

        content = (email_tmp_dir / "latest.html").read_text()
        assert "Hello archfan42" in content

    @pytest.mark.asyncio
    async def test_email_contains_link_to_archlinux(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        make_alert(
            title="Product link test",
            link="https://archlinux.org/news/specific-item/",
        )
        make_user()

        await send_daily_digest()

        content = (email_tmp_dir / "latest.html").read_text()
        assert 'href="https://archlinux.org/news/specific-item/"' in content


class TestSendDailyDigestProductionMode:
    @pytest.mark.asyncio
    async def test_smtp_send_called_with_correct_params(self, db_session, make_alert, make_user, production_env, mocker):
        make_alert()
        make_user(email="prod@example.com")

        mock_send = mocker.patch("aiosmtplib.send", new_callable=mocker.AsyncMock)

        await send_daily_digest()

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["hostname"] == "smtp.example.com"
        assert call_kwargs["port"] == 587
        assert call_kwargs["username"] == "user@example.com"
        assert call_kwargs["password"] == "password"
        assert call_kwargs["start_tls"] is True

    @pytest.mark.asyncio
    async def test_mime_message_has_correct_headers(self, db_session, make_alert, make_user, production_env, mocker):
        make_alert()
        make_user(email="headers@example.com")

        mock_send = mocker.patch("aiosmtplib.send", new_callable=mocker.AsyncMock)

        await send_daily_digest()

        msg = mock_send.call_args.args[0]
        assert msg["Subject"] == "Arch Linux Manual Intervention Report"
        assert msg["From"] == "noreply@example.com"
        assert msg["To"] == "headers@example.com"

    @pytest.mark.asyncio
    async def test_missing_smtp_host_raises(self, db_session, make_alert, make_user, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SMTP_HOST", "")  # empty

        make_alert()
        make_user()

        with pytest.raises(KeyError):
            await send_daily_digest()
