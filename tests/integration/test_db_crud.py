"""Integration tests for DB CRUD operations."""

import datetime

import pytest
import reflex_local_auth
import sqlmodel

from linen_draper.models import InterventionAlert, UserInfo


class TestInterventionAlertCRUD:
    def test_insert_and_select(self, db_session):
        alert = InterventionAlert(
            title="kea update requires manual intervention",
            link="https://archlinux.org/news/kea/",
            description="details",
            pub_date=datetime.datetime(2026, 4, 7),
            guid="tag:archlinux.org,2026-04-07:/news/kea/",
        )
        db_session.add(alert)
        db_session.commit()

        fetched = db_session.exec(
            sqlmodel.select(InterventionAlert).where(
                InterventionAlert.link == "https://archlinux.org/news/kea/"
            )
        ).first()

        assert fetched is not None
        assert fetched.title == "kea update requires manual intervention"

    def test_duplicate_link_raises(self, db_session):
        alert1 = InterventionAlert(
            title="First", link="https://archlinux.org/news/dup/",
            description="", pub_date=datetime.datetime(2026, 1, 1),
        )
        db_session.add(alert1)
        db_session.commit()

        alert2 = InterventionAlert(
            title="Second", link="https://archlinux.org/news/dup/",
            description="", pub_date=datetime.datetime(2026, 1, 2),
        )
        db_session.add(alert2)

        with pytest.raises(Exception):
            db_session.commit()

    def test_duplicate_guid_raises(self, db_session):
        alert1 = InterventionAlert(
            title="First", link="https://archlinux.org/news/a/",
            description="", pub_date=datetime.datetime(2026, 1, 1),
            guid="duplicate-guid",
        )
        db_session.add(alert1)
        db_session.commit()

        alert2 = InterventionAlert(
            title="Second", link="https://archlinux.org/news/b/",
            description="", pub_date=datetime.datetime(2026, 1, 2),
            guid="duplicate-guid",
        )
        db_session.add(alert2)

        with pytest.raises(Exception):
            db_session.commit()

    def test_order_by_pub_date_desc(self, db_session):
        alerts_data = [
            ("Oldest", "https://archlinux.org/news/old/",
             datetime.datetime(2024, 1, 1)),
            ("Middle", "https://archlinux.org/news/mid/",
             datetime.datetime(2025, 6, 15)),
            ("Newest", "https://archlinux.org/news/new/",
             datetime.datetime(2026, 4, 7)),
        ]
        for title, link, pub_date in alerts_data:
            db_session.add(InterventionAlert(
                title=title, link=link, description="",
                pub_date=pub_date,
            ))
        db_session.commit()

        results = db_session.exec(
            sqlmodel.select(InterventionAlert).order_by(
                sqlmodel.desc(InterventionAlert.pub_date)
            )
        ).all()

        assert len(results) == 3
        assert results[0].title == "Newest"
        assert results[1].title == "Middle"
        assert results[2].title == "Oldest"


class TestUserInfoCRUD:
    def test_create_and_link_to_user(self, db_session):
        user = reflex_local_auth.LocalUser(
            username="cruduser",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        info = UserInfo(email="crud@example.com", user_id=user.id)
        db_session.add(info)
        db_session.commit()
        db_session.refresh(info)

        assert info.id is not None
        assert info.email == "crud@example.com"
        assert info.user_id == user.id

    def test_query_by_user_id(self, db_session):
        import reflex_local_auth

        user = reflex_local_auth.LocalUser(
            username="queryuser",
            password_hash=reflex_local_auth.LocalUser.hash_password("pw"),
            enabled=True,
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        info = UserInfo(email="query@example.com", user_id=user.id)
        db_session.add(info)
        db_session.commit()

        fetched = db_session.exec(
            sqlmodel.select(UserInfo).where(UserInfo.user_id == user.id)
        ).one_or_none()

        assert fetched is not None
        assert fetched.email == "query@example.com"

    def test_update_email_preference(self, db_session):
        info = UserInfo(email="old@example.com", email_enabled=True, user_id=1)
        db_session.add(info)
        db_session.commit()

        info.email_enabled = False
        info.email = "new@example.com"
        db_session.add(info)
        db_session.commit()

        db_session.refresh(info)
        assert info.email_enabled is False
        assert info.email == "new@example.com"

    def test_last_email_sent_at_updated(self, db_session):
        info = UserInfo(email="timed@example.com", user_id=1)
        db_session.add(info)
        db_session.commit()

        assert info.last_email_sent_at is None

        from datetime import datetime, timezone
        info.last_email_sent_at = datetime.now(timezone.utc)
        db_session.add(info)
        db_session.commit()

        db_session.refresh(info)
        assert info.last_email_sent_at is not None
