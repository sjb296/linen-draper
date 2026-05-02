"""E2E tests for the Dashboard state."""

import datetime

import sqlmodel

from linen_draper.models import InterventionAlert


class TestDashboardState:
    def test_alerts_ordered_by_pub_date_desc(self, db_session):
        alerts_data = [
            ("Oldest", "https://archlinux.org/news/1/", datetime.datetime(2024, 1, 1)),
            ("Middle", "https://archlinux.org/news/2/", datetime.datetime(2025, 6, 15)),
            ("Newest", "https://archlinux.org/news/3/", datetime.datetime(2026, 4, 7)),
        ]
        for title, link, pub_date in alerts_data:
            db_session.add(InterventionAlert(
                title=title, link=link, description="",
                pub_date=pub_date,
            ))
        db_session.commit()

        results = list(db_session.exec(
            sqlmodel.text("""
                SELECT id, title, link, description, pub_date, created_at
                FROM interventionalert
                ORDER BY pub_date DESC
            """)
        ).all())

        assert len(results) == 3
        assert results[0][1] == "Newest"
        assert results[1][1] == "Middle"
        assert results[2][1] == "Oldest"

    def test_empty_dashboard_has_no_alerts(self, db_session):
        results = list(db_session.exec(
            sqlmodel.text("""
                SELECT id, title, link, description, pub_date, created_at
                FROM interventionalert
                ORDER BY pub_date DESC
            """)
        ).all())

        assert len(results) == 0

    def test_alert_dict_keys(self, db_session):
        alert = InterventionAlert(
            title="Dict test",
            link="https://archlinux.org/news/dict-test/",
            description="Test desc",
            pub_date=datetime.datetime(2026, 4, 1),
            guid="test-guid",
        )
        db_session.add(alert)
        db_session.commit()

        d = alert.dict()

        assert "id" in d
        assert "title" in d
        assert "link" in d
        assert "description" in d
        assert "pub_date" in d
        assert "created_at" in d

        assert d["title"] == "Dict test"
        assert d["link"] == "https://archlinux.org/news/dict-test/"

    def test_multiple_alerts_with_descriptions(self, db_session):
        import datetime

        alert1 = InterventionAlert(
            title="Alert with desc",
            link="https://archlinux.org/news/desc/",
            description="<p>Detailed instructions for manual intervention</p>",
            pub_date=datetime.datetime(2026, 4, 1),
        )
        alert2 = InterventionAlert(
            title="Alert without desc",
            link="https://archlinux.org/news/no-desc/",
            description="",
            pub_date=datetime.datetime(2026, 4, 2),
        )
        db_session.add_all([alert1, alert2])
        db_session.commit()

        results = list(db_session.exec(
            sqlmodel.text("""
                SELECT id, title, link, description, pub_date, created_at
                FROM interventionalert
                ORDER BY pub_date DESC
            """)
        ).all())

        assert len(results) == 2
        assert results[0][1] == "Alert without desc"  # newer first
        assert results[1][1] == "Alert with desc"

        # Check descriptions
        assert results[0][3] == ""
        assert "manual intervention" in results[1][3]
