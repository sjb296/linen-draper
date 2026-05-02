"""Integration tests for the email system. CRITICAL: covers local + production paths."""

import datetime
from datetime import timezone

import pytest
import reflex_local_auth

from linen_draper.emailer import send_daily_digest, send_weekly_report, send_monthly_report


class TestSendDailyDigestLocalMode:
    @pytest.mark.asyncio
    async def test_no_alerts_returns_early(self, db_session, email_tmp_dir, clean_env, caplog):
        await send_daily_digest()

        assert "No alerts to send" in caplog.text

    @pytest.mark.asyncio
    async def test_no_enabled_users_returns_early(self, db_session, make_alert, email_tmp_dir, clean_env, caplog):
        make_alert()

        await send_daily_digest()

        assert "No users with daily enabled" in caplog.text

    @pytest.mark.asyncio
    async def test_disabled_user_skipped(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        make_alert()
        make_user(email_enabled=False)

        await send_daily_digest()

        assert "No users with daily enabled" in caplog.text

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
        assert "Arch Linux Manual Intervention Report (Daily)" in msg["Subject"]
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


class TestSendWeeklyReportLocalMode:
    @pytest.mark.asyncio
    async def test_no_alerts_returns_early(self, db_session, email_tmp_dir, clean_env, caplog):
        await send_weekly_report()
        assert "No alerts to send" in caplog.text

    @pytest.mark.asyncio
    async def test_no_users_with_weekly_enabled(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        make_alert()
        make_user()  # defaults: weekly_enabled=False
        await send_weekly_report()
        assert "No users with weekly enabled" in caplog.text

    @pytest.mark.asyncio
    async def test_recent_alert_included(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        from datetime import timezone, timedelta
        recent = datetime.datetime.now(timezone.utc) - timedelta(days=3)
        make_alert(
            title="Recent weekly alert",
            link="https://archlinux.org/news/weekly-recent/",
            pub_date=recent,
        )
        make_user(weekly_enabled=True)

        await send_weekly_report()

        content = (email_tmp_dir / "latest.html").read_text()
        assert "Recent weekly alert" in content

    @pytest.mark.asyncio
    async def test_old_alert_excluded(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        from datetime import timezone, timedelta
        old = datetime.datetime.now(timezone.utc) - timedelta(days=14)
        make_alert(
            title="Old weekly alert",
            link="https://archlinux.org/news/weekly-old/",
            pub_date=old,
        )
        make_user(weekly_enabled=True)

        await send_weekly_report()

        assert "No weekly alerts within window" in caplog.text

    @pytest.mark.asyncio
    async def test_mixed_alerts_only_recent_sent(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone.utc)
        make_alert(title="Old one", link="https://x.com/old/", pub_date=now - timedelta(days=10))
        make_alert(title="New one", link="https://x.com/new/", pub_date=now - timedelta(days=2))
        make_user(weekly_enabled=True)

        await send_weekly_report()

        content = (email_tmp_dir / "latest.html").read_text()
        assert "New one" in content
        assert "Old one" not in content

    @pytest.mark.asyncio
    async def test_last_weekly_sent_at_updated(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        import sqlmodel
        from linen_draper.models import UserInfo
        from datetime import timezone, timedelta

        recent = datetime.datetime.now(timezone.utc) - timedelta(days=1)
        make_alert(pub_date=recent)
        make_user(username="weekly_user", weekly_enabled=True)

        fresh_user = db_session.exec(
            sqlmodel.select(reflex_local_auth.LocalUser).where(
                reflex_local_auth.LocalUser.username == "weekly_user"
            )
        ).one()

        await send_weekly_report()

        fresh_info = db_session.exec(
            sqlmodel.select(UserInfo).where(UserInfo.user_id == fresh_user.id)
        ).one()
        assert fresh_info.last_weekly_sent_at is not None


class TestSendMonthlyReportLocalMode:
    @pytest.mark.asyncio
    async def test_no_alerts_returns_early(self, db_session, email_tmp_dir, clean_env, caplog):
        await send_monthly_report()
        assert "No alerts to send" in caplog.text

    @pytest.mark.asyncio
    async def test_no_users_with_monthly_enabled(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        make_alert()
        make_user()  # defaults: monthly_enabled=False
        await send_monthly_report()
        assert "No users with monthly enabled" in caplog.text

    @pytest.mark.asyncio
    async def test_recent_alert_included(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        from datetime import timezone, timedelta
        recent = datetime.datetime.now(timezone.utc) - timedelta(days=10)
        make_alert(
            title="Recent monthly alert",
            link="https://archlinux.org/news/monthly-recent/",
            pub_date=recent,
        )
        make_user(monthly_enabled=True)

        await send_monthly_report()

        content = (email_tmp_dir / "latest.html").read_text()
        assert "Recent monthly alert" in content

    @pytest.mark.asyncio
    async def test_old_alert_excluded(self, db_session, make_alert, make_user, email_tmp_dir, clean_env, caplog):
        from datetime import timezone, timedelta
        old = datetime.datetime.now(timezone.utc) - timedelta(days=40)
        make_alert(
            title="Ancient monthly alert",
            link="https://archlinux.org/news/monthly-old/",
            pub_date=old,
        )
        make_user(monthly_enabled=True)

        await send_monthly_report()

        assert "No monthly alerts within window" in caplog.text

    @pytest.mark.asyncio
    async def test_mixed_alerts_only_recent_sent(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        from datetime import timezone, timedelta
        now = datetime.datetime.now(timezone.utc)
        make_alert(title="Ancient", link="https://x.com/anc/", pub_date=now - timedelta(days=45))
        make_alert(title="Midmonth", link="https://x.com/mid/", pub_date=now - timedelta(days=15))
        make_user(monthly_enabled=True)

        await send_monthly_report()

        content = (email_tmp_dir / "latest.html").read_text()
        assert "Midmonth" in content
        assert "Ancient" not in content

    @pytest.mark.asyncio
    async def test_last_monthly_sent_at_updated(self, db_session, make_alert, make_user, email_tmp_dir, clean_env):
        import sqlmodel
        from linen_draper.models import UserInfo
        from datetime import timezone, timedelta

        recent = datetime.datetime.now(timezone.utc) - timedelta(days=5)
        make_alert(pub_date=recent)
        make_user(username="monthly_user", monthly_enabled=True)

        fresh_user = db_session.exec(
            sqlmodel.select(reflex_local_auth.LocalUser).where(
                reflex_local_auth.LocalUser.username == "monthly_user"
            )
        ).one()

        await send_monthly_report()

        fresh_info = db_session.exec(
            sqlmodel.select(UserInfo).where(UserInfo.user_id == fresh_user.id)
        ).one()
        assert fresh_info.last_monthly_sent_at is not None


class TestSendWeeklyReportProductionMode:
    @pytest.mark.asyncio
    async def test_smtp_subject_includes_weekly(self, db_session, make_alert, make_user, production_env, mocker):
        from datetime import timezone, timedelta
        make_alert(pub_date=datetime.datetime.now(timezone.utc) - timedelta(days=1))
        make_user(weekly_enabled=True, email="weekly@example.com")

        mock_send = mocker.patch("aiosmtplib.send", new_callable=mocker.AsyncMock)

        await send_weekly_report()

        msg = mock_send.call_args.args[0]
        assert "Weekly" in msg["Subject"]


class TestSendMonthlyReportProductionMode:
    @pytest.mark.asyncio
    async def test_smtp_subject_includes_monthly(self, db_session, make_alert, make_user, production_env, mocker):
        from datetime import timezone, timedelta
        make_alert(pub_date=datetime.datetime.now(timezone.utc) - timedelta(days=5))
        make_user(monthly_enabled=True, email="monthly@example.com")

        mock_send = mocker.patch("aiosmtplib.send", new_callable=mocker.AsyncMock)

        await send_monthly_report()

        msg = mock_send.call_args.args[0]
        assert "Monthly" in msg["Subject"]
