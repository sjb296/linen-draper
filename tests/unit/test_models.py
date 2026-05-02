import datetime

import pytest

from linen_draper.models import InterventionAlert, UserInfo


class TestInterventionAlert:
    def test_create_valid_alert(self, db_session):
        alert = InterventionAlert(
            title="Test package requires manual intervention",
            link="https://archlinux.org/news/test/",
            description="<p>Details</p>",
            pub_date=datetime.datetime(2026, 4, 1),
            guid="tag:archlinux.org,2026-04-01:/news/test/",
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)

        assert alert.id is not None
        assert alert.title == "Test package requires manual intervention"
        assert alert.link == "https://archlinux.org/news/test/"
        assert alert.pub_date == datetime.datetime(2026, 4, 1)
        assert alert.created_at is not None

    def test_guid_nullable(self, db_session):
        alert = InterventionAlert(
            title="Item without GUID",
            link="https://archlinux.org/news/no-guid/",
            description="",
            pub_date=datetime.datetime(2026, 5, 1),
            guid=None,
        )
        db_session.add(alert)
        db_session.commit()

        assert alert.guid is None

    def test_dict_serialization(self, db_session):
        alert = InterventionAlert(
            title="Serialization test",
            link="https://archlinux.org/news/serial/",
            description="<p>Test</p>",
            pub_date=datetime.datetime(2026, 3, 15, 12, 0, 0),
            guid="tag:archlinux.org,2026-03-15:/news/serial/",
        )
        db_session.add(alert)
        db_session.commit()

        d = alert.dict()
        assert d["title"] == "Serialization test"
        assert d["link"] == "https://archlinux.org/news/serial/"
        assert "T" in d["pub_date"]
        assert "T" in d["created_at"]

    def test_link_uniqueness(self, db_session):
        alert1 = InterventionAlert(
            title="First",
            link="https://archlinux.org/news/dupe/",
            description="",
            pub_date=datetime.datetime(2026, 1, 1),
        )
        db_session.add(alert1)
        db_session.commit()

        alert2 = InterventionAlert(
            title="Second",
            link="https://archlinux.org/news/dupe/",
            description="",
            pub_date=datetime.datetime(2026, 1, 2),
        )
        db_session.add(alert2)
        with pytest.raises(Exception):
            db_session.commit()


class TestUserInfo:
    def test_defaults(self, db_session):
        info = UserInfo(user_id=1)
        assert info.email == ""
        assert info.email_enabled is True
        assert info.last_email_sent_at is None

    def test_create_and_retrieve(self, db_session):
        import reflex_local_auth

        user = reflex_local_auth.LocalUser(
            username="testuser",
            password_hash=reflex_local_auth.LocalUser.hash_password("secret"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        info = UserInfo(
            email="user@example.com",
            email_enabled=True,
            user_id=user.id,
        )
        db_session.add(info)
        db_session.commit()
        db_session.refresh(info)

        assert info.email == "user@example.com"
        assert info.user_id == user.id

    def test_email_disabled(self, db_session):
        info = UserInfo(
            email="off@example.com",
            email_enabled=False,
            user_id=1,
        )
        db_session.add(info)
        db_session.commit()

        assert info.email_enabled is False

    def test_last_email_sent_at_timestamp(self, db_session):
        now = datetime.datetime(2026, 4, 1, 9, 0, 0)
        info = UserInfo(
            email="timed@example.com",
            last_email_sent_at=now,
            user_id=1,
        )
        db_session.add(info)
        db_session.commit()

        assert info.last_email_sent_at == now
