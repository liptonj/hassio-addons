"""Tests for Meraki org selection settings."""

from app.config import Settings
from app.schemas.settings import AllSettings, SettingsUpdate


def test_settings_defaults_include_meraki_org_id() -> None:
    """Settings defaults should include meraki_org_id."""
    settings = Settings()
    assert hasattr(settings, "meraki_org_id")
    assert settings.meraki_org_id == ""


def test_all_settings_includes_meraki_org_id() -> None:
    """AllSettings should expose meraki_org_id with a default value."""
    settings = AllSettings()
    assert hasattr(settings, "meraki_org_id")
    assert settings.meraki_org_id == ""


def test_settings_update_accepts_meraki_org_id() -> None:
    """SettingsUpdate should accept meraki_org_id updates."""
    update = SettingsUpdate(meraki_org_id="org_123")
    assert update.meraki_org_id == "org_123"
