import datetime
from contextlib import contextmanager

import pytest
import reflex as rx
import reflex_local_auth
from sqlmodel import Session, create_engine

from linen_draper.models import InterventionAlert, UserInfo

TEST_DB_URL = "sqlite://"


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    rx.Model.metadata.create_all(engine)
    yield engine
    rx.Model.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine, monkeypatch):
    """Session connected to test DB. Patches rx.session() for all callers."""

    @contextmanager
    def _test_session():
        with Session(db_engine) as s:
            yield s

    monkeypatch.setattr(rx, "session", _test_session)
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def make_alert(db_engine):
    """Factory: creates and returns an InterventionAlert."""
    counter = 0

    def _make(**kwargs):
        nonlocal counter
        counter += 1
        defaults = {
            "title": f"Test package {counter} requires manual intervention",
            "link": f"https://archlinux.org/news/test-package-{counter}/",
            "description": "<p>Test description</p>",
            "pub_date": datetime.datetime(2026, 4, counter),
            "guid": f"tag:archlinux.org,2026-04-0{counter}:/news/test-package-{counter}/",
        }
        defaults.update(kwargs)
        alert = InterventionAlert(**defaults)
        with Session(db_engine) as session:
            session.add(alert)
            session.commit()
            session.refresh(alert)
            return alert

    return _make


@pytest.fixture
def make_user(db_engine):
    """Factory: creates a LocalUser + UserInfo, returns (user, info)."""
    counter = 0

    def _make(username=None, email=None, email_enabled=True, password="secret",
              weekly_enabled=False, monthly_enabled=False):
        nonlocal counter
        counter += 1
        username = username or f"testuser{counter}"
        email = email or f"test{counter}@example.com"

        with Session(db_engine) as session:
            user = reflex_local_auth.LocalUser(
                username=username,
                password_hash=reflex_local_auth.LocalUser.hash_password(password),
                enabled=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            assert user.id is not None
            info = UserInfo(
                email=email,
                email_enabled=email_enabled,
                weekly_enabled=weekly_enabled,
                monthly_enabled=monthly_enabled,
                user_id=user.id,
            )
            session.add(info)
            session.commit()
            session.refresh(info)
            return user, info

    return _make


@pytest.fixture
def email_tmp_dir(tmp_path, monkeypatch):
    """Redirect .emails/ output to a temp directory."""
    email_dir = tmp_path / ".emails"
    email_dir.mkdir()
    monkeypatch.setattr("linen_draper.emailer.EMAIL_DIR", email_dir)
    monkeypatch.setattr("linen_draper.emailer.LATEST_EMAIL", email_dir / "latest.html")
    return email_dir


@pytest.fixture
def clean_env(monkeypatch):
    """Remove SMTP env vars and reset APP_ENV."""
    for key in ("APP_ENV", "SMTP_HOST", "SMTP_PORT", "SMTP_USER",
                "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "local")


@pytest.fixture
def production_env(monkeypatch):
    """Set production env vars for SMTP."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")


@pytest.fixture
def sample_rss_xml():
    """RSS feed XML with 3 items: 1 matching, 2 non-matching."""
    return """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
<channel>
    <title>Arch Linux: Recent news updates</title>
    <link>https://archlinux.org/news/</link>
    <item>
        <title>kea >= 1:3.0.3-6 update requires manual intervention</title>
        <link>https://archlinux.org/news/kea-requires-manual-intervention/</link>
        <description>&lt;p&gt;The kea package requires manual steps.&lt;/p&gt;</description>
        <pubDate>Tue, 07 Apr 2026 16:50:29 +0000</pubDate>
        <guid>tag:archlinux.org,2026-04-07:/news/kea-requires-manual-intervention/</guid>
    </item>
    <item>
        <title>Arch Linux 2026 Leader Election Results</title>
        <link>https://archlinux.org/news/leader-election-2026/</link>
        <description>&lt;p&gt;Election results are in.&lt;/p&gt;</description>
        <pubDate>Wed, 15 Apr 2026 10:00:00 +0000</pubDate>
        <guid>tag:archlinux.org,2026-04-15:/news/leader-election-2026/</guid>
    </item>
    <item>
        <title>iptables now defaults to the nft backend</title>
        <link>https://archlinux.org/news/iptables-nft-backend/</link>
        <description>&lt;p&gt;The iptables package has changed.&lt;/p&gt;</description>
        <pubDate>Sun, 05 Apr 2026 18:28:33 +0000</pubDate>
        <guid>tag:archlinux.org,2026-04-05:/news/iptables-nft-backend/</guid>
    </item>
</channel>
</rss>"""


@pytest.fixture
def sample_html_page():
    """HTML news page with mixed items (some matching, some not)."""
    return """<!DOCTYPE html>
<html>
<body>
<table>
  <tr>
    <td>2026-04-07</td>
    <td><a href="/news/kea-requires-manual-intervention/">kea &gt;= 1:3.0.3-6 update requires manual intervention</a></td>
    <td>Robin Candau</td>
  </tr>
  <tr>
    <td>2026-04-15</td>
    <td><a href="/news/leader-election-2026/">Arch Linux 2026 Leader Election Results</a></td>
    <td>Christian Heusel</td>
  </tr>
  <tr>
    <td>2026-06-20</td>
    <td><a href="/news/plasma-x11-intervention/">Plasma 6.4.0 will need manual intervention if you are on X11</a></td>
    <td>Tomaz Canabrava</td>
  </tr>
</table>
</body>
</html>"""


@pytest.fixture(autouse=True)
def _disable_logging(caplog):
    """Set caplog to capture at INFO level for assertions."""
    caplog.set_level("INFO", logger="linen_draper")
