"""Tests for environment detection in the emailer."""


from linen_draper.emailer import _get_env


class TestGetEnv:
    def test_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        assert _get_env() == "local"

    def test_production(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        assert _get_env() == "production"

    def test_custom_value(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "staging")
        assert _get_env() == "staging"
