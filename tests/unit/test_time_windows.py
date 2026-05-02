"""Unit tests for weekly and monthly time window filters."""

import datetime
from datetime import timezone, timedelta

from linen_draper.emailer import _weekly_filter, _monthly_filter
from linen_draper.models import InterventionAlert


class TestWeeklyFilter:
    def test_alert_within_7_days_included(self):
        recent = datetime.datetime.now(timezone.utc) - timedelta(days=3)
        alert = InterventionAlert(
            title="Recent alert",
            link="https://archlinux.org/news/recent/",
            description="",
            pub_date=recent,
        )
        assert _weekly_filter(alert) is True

    def test_alert_exactly_7_days_ago_included(self):
        # Use a value just inside the window to avoid sub-millisecond timing issues
        exactly_7 = datetime.datetime.now(timezone.utc) - timedelta(days=7) + timedelta(seconds=1)
        alert = InterventionAlert(
            title="Borderline",
            link="https://archlinux.org/news/border/",
            description="",
            pub_date=exactly_7,
        )
        assert _weekly_filter(alert) is True

    def test_alert_older_than_7_days_excluded(self):
        older = datetime.datetime.now(timezone.utc) - timedelta(days=10)
        alert = InterventionAlert(
            title="Old alert",
            link="https://archlinux.org/news/old/",
            description="",
            pub_date=older,
        )
        assert _weekly_filter(alert) is False

    def test_naive_datetime_treated_as_utc(self):
        naive_recent = datetime.datetime.now() - timedelta(days=2)
        alert = InterventionAlert(
            title="Naive recent",
            link="https://archlinux.org/news/naive/",
            description="",
            pub_date=naive_recent,
        )
        assert _weekly_filter(alert) is True


class TestMonthlyFilter:
    def test_alert_within_30_days_included(self):
        recent = datetime.datetime.now(timezone.utc) - timedelta(days=15)
        alert = InterventionAlert(
            title="Mid-month",
            link="https://archlinux.org/news/mid/",
            description="",
            pub_date=recent,
        )
        assert _monthly_filter(alert) is True

    def test_alert_exactly_30_days_ago_included(self):
        # Use a value just inside the window to avoid sub-millisecond timing issues
        exactly_30 = datetime.datetime.now(timezone.utc) - timedelta(days=30) + timedelta(seconds=1)
        alert = InterventionAlert(
            title="Borderline",
            link="https://archlinux.org/news/border30/",
            description="",
            pub_date=exactly_30,
        )
        assert _monthly_filter(alert) is True

    def test_alert_older_than_30_days_excluded(self):
        older = datetime.datetime.now(timezone.utc) - timedelta(days=45)
        alert = InterventionAlert(
            title="Very old",
            link="https://archlinux.org/news/ancient/",
            description="",
            pub_date=older,
        )
        assert _monthly_filter(alert) is False

    def test_naive_datetime_treated_as_utc(self):
        naive_recent = datetime.datetime.now() - timedelta(days=5)
        alert = InterventionAlert(
            title="Naive recent",
            link="https://archlinux.org/news/naive2/",
            description="",
            pub_date=naive_recent,
        )
        assert _monthly_filter(alert) is True
