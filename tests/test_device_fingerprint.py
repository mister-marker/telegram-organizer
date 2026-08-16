from telethon.sessions import StringSession

from config import Settings, load_settings
import device_fingerprint
import session_vault
from tg_client import build_client


class FakeMacOSKeyring(session_vault.MacOSKeyring):
    def get_password(self, service, username):
        return None


class FakeTelegramClient:
    def __init__(self, session, api_id, api_hash, **kwargs):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash
        self.kwargs = kwargs


def _settings(**overrides):
    values = {
        "api_id": 123,
        "api_hash": "hash",
        "session_name": "test_session",
        "dead_after_days": 180,
    }
    values.update(overrides)
    return Settings(**values)


def test_detects_human_readable_mac_fingerprint(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return type("Result", (), {"returncode": 0, "stdout": "MacBookPro18,3\n"})()

    monkeypatch.setattr(device_fingerprint.subprocess, "run", fake_run)
    monkeypatch.setattr(device_fingerprint.platform, "mac_ver", lambda: ("15.6.1", ("", "", ""), "arm64"))

    fingerprint = device_fingerprint.build_device_fingerprint(_settings())

    assert fingerprint.device_model == "MacBook Pro"
    assert fingerprint.system_version == "macOS 15.6.1"
    assert fingerprint.app_version == "5.16.4"
    assert fingerprint.lang_code == "en"
    assert fingerprint.system_lang_code == "en"


def test_settings_can_override_device_fingerprint(monkeypatch):
    monkeypatch.setenv("TG_API_ID", "123")
    monkeypatch.setenv("TG_API_HASH", "hash")
    monkeypatch.setenv("TG_DEVICE_MODEL", "MacBook Air")
    monkeypatch.setenv("TG_SYSTEM_VERSION", "macOS 15.5")
    monkeypatch.setenv("TG_APP_VERSION", "5.17.0")
    monkeypatch.setenv("TG_LANG_CODE", "ru")
    monkeypatch.setenv("TG_SYSTEM_LANG_CODE", "ru")

    settings = load_settings()

    assert settings.device_model == "MacBook Air"
    assert settings.system_version == "macOS 15.5"
    assert settings.app_version == "5.17.0"
    assert settings.lang_code == "ru"
    assert settings.system_lang_code == "ru"


def test_build_client_passes_fingerprint_to_telethon(monkeypatch):
    fake_keyring = FakeMacOSKeyring()
    monkeypatch.setattr(session_vault.keyring, "get_keyring", lambda: fake_keyring)
    monkeypatch.setattr("tg_client.TelegramClient", FakeTelegramClient)

    def fake_run(*_args, **_kwargs):
        return type("Result", (), {"returncode": 0, "stdout": "MacBookAir10,1\n"})()

    monkeypatch.setattr(device_fingerprint.subprocess, "run", fake_run)
    monkeypatch.setattr(device_fingerprint.platform, "mac_ver", lambda: ("14.7", ("", "", ""), "arm64"))

    client = build_client(_settings(lang_code="ru", system_lang_code="ru"))

    assert isinstance(client.session, StringSession)
    assert client.kwargs == {
        "device_model": "MacBook Air",
        "system_version": "macOS 14.7",
        "app_version": "5.16.4",
        "lang_code": "ru",
        "system_lang_code": "ru",
    }


def test_fingerprint_falls_back_when_sysctl_is_unavailable(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise OSError("sysctl unavailable")

    monkeypatch.setattr(device_fingerprint.subprocess, "run", fake_run)
    monkeypatch.setattr(device_fingerprint.platform, "mac_ver", lambda: ("", ("", "", ""), ""))

    fingerprint = device_fingerprint.build_device_fingerprint(_settings())

    assert fingerprint.device_model == "MacBook Pro"
    assert fingerprint.system_version == "macOS"
