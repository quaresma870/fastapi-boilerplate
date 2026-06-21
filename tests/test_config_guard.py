"""
Tests for the startup guard that refuses insecure defaults in production —
see app.core.config.Settings._refuse_insecure_production_defaults.
"""

import pytest

from app.core.config import Settings


class TestProductionConfigGuard:
    def test_development_allows_default_secret_key(self):
        Settings(
            ENVIRONMENT="development",
            SECRET_KEY="change-me-in-production-use-openssl-rand-hex-32",
        )

    def test_production_rejects_default_secret_key(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="change-me-in-production-use-openssl-rand-hex-32",
                ALLOWED_HOSTS=["api.example.com"],
            )

    def test_production_rejects_wildcard_allowed_hosts(self):
        with pytest.raises(ValueError, match="ALLOWED_HOSTS"):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a-real-randomly-generated-secret-key-not-the-default",
                ALLOWED_HOSTS=["*"],
            )

    def test_production_accepts_proper_configuration(self):
        s = Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a-real-randomly-generated-secret-key-not-the-default",
            ALLOWED_HOSTS=["api.example.com"],
        )
        assert s.ENVIRONMENT == "production"

    def test_staging_is_not_subject_to_the_guard(self):
        """The guard is deliberately scoped to ENVIRONMENT == 'production'
        only — staging environments commonly need to test against
        not-yet-finalised configuration."""
        Settings(
            ENVIRONMENT="staging",
            SECRET_KEY="change-me-in-production-use-openssl-rand-hex-32",
        )


class TestVersionMatchesChangelog:
    def test_settings_version_matches_latest_changelog_entry(self):
        """Regression guard: settings.VERSION is served in /health and the
        OpenAPI docs — it drifted out of sync with the actual shipped
        release once already (stuck at '1.0.0' through four real
        releases) before this test existed."""
        import re
        from pathlib import Path

        from app.core.config import settings

        changelog = Path(__file__).parent.parent / "CHANGELOG.md"
        text = changelog.read_text()
        match = re.search(r"###\s+v(\d+\.\d+\.\d+)", text)
        assert match, "Could not find a version heading in CHANGELOG.md"
        latest_version = match.group(1)

        assert settings.VERSION == latest_version, (
            f"settings.VERSION ({settings.VERSION}) does not match the latest "
            f"CHANGELOG.md entry (v{latest_version}) — bump app/core/config.py's "
            f"VERSION when cutting a release."
        )
