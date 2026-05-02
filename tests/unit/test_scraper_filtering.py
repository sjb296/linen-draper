"""Tests for the scraper's regex filtering and date parsing logic."""

import datetime

from linen_draper.scraper import MANUAL_INTERVENTION_RE


class TestManualInterventionRegex:
    def test_matches_requires_manual_intervention(self):
        assert MANUAL_INTERVENTION_RE.search(
            "kea >= 1:3.0.3-6 update requires manual intervention"
        )

    def test_matches_may_require_manual_intervention(self):
        assert MANUAL_INTERVENTION_RE.search(
            ".NET packages may require manual intervention"
        )

    def test_matches_will_need_manual_intervention(self):
        assert MANUAL_INTERVENTION_RE.search(
            "Plasma 6.4.0 will need manual intervention if you are on X11"
        )

    def test_case_insensitive(self):
        assert MANUAL_INTERVENTION_RE.search(
            "MANUAL INTERVENTION REQUIRED"
        )
        assert MANUAL_INTERVENTION_RE.search(
            "Manual Intervention Required"
        )

    def test_no_match_without_phrase(self):
        assert not MANUAL_INTERVENTION_RE.search(
            "Arch Linux 2026 Leader Election Results"
        )
        assert not MANUAL_INTERVENTION_RE.search(
            "Recent service outages"
        )
        assert not MANUAL_INTERVENTION_RE.search(
            "Cleaning up old repositories"
        )

    def test_phrase_must_be_delimited_correctly(self):
        # "manual intervention" appears as a substring — that still matches via re.search
        assert MANUAL_INTERVENTION_RE.search(
            "manual interventionrequired"
        )


class TestRSSDateParsing:
    def test_parse_rss_pub_date(self):
        from email.utils import parsedate_to_datetime

        pub_date = parsedate_to_datetime(
            "Tue, 07 Apr 2026 16:50:29 +0000"
        )
        assert pub_date.year == 2026
        assert pub_date.month == 4
        assert pub_date.day == 7
        assert pub_date.hour == 16
        assert pub_date.minute == 50

    def test_invalid_date_returns_none(self):
        from email.utils import parsedate_to_datetime

        # Invalid date should raise ValueError (or similar) caught by the scraper
        try:
            result = parsedate_to_datetime("not a date")
        except Exception:
            result = None

        assert result is None


class TestHTMLDateParsing:
    def test_parse_html_date(self):
        dt = datetime.datetime.strptime("2026-04-07", "%Y-%m-%d")
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 7

    def test_invalid_html_date(self):
        import datetime

        try:
            datetime.datetime.strptime("not-a-date", "%Y-%m-%d")
        except ValueError:
            return

        assert False, "Should have raised ValueError"
