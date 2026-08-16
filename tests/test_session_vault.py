from dataclasses import replace

import pytest
from telethon.sessions import StringSession

from config import Settings
import session_vault
from session_vault import SessionVaultError
from tg_client import build_client, legacy_session_path


class FakeMacOSKeyring(session_vault.MacOSKeyring):
    def __init__(self):
        self.storage = {}

    def get_password(self, service, username):
        return self.storage.get((service, username))

    def set_password(self, service, username, password):
        self.storage[(service, username)] = password

    def delete_password(self, service, username):
        self.storage.pop((service, username), None)


class UnsafeKeyring:
    pass


class FakeClient:
    def __init__(self, session_string):
        self.session = FakeSession(session_string)


class FakeSession:
    def __init__(self, value=None):
        self.value = value or ""

    def save(self):
        return self.value


@pytest.fixture
def settings():
    return Settings(
        api_id=123,
        api_hash="hash",
        session_name="test_session",
        dead_after_days=180,
    )


def test_save_and_load_session_uses_keychain_backend(settings, monkeypatch):
    fake_keyring = FakeMacOSKeyring()
    monkeypatch.setattr(session_vault.keyring, "get_keyring", lambda: fake_keyring)
    monkeypatch.setattr(session_vault, "StringSession", FakeSession)

    client = FakeClient("fake-test-session-string")

    session_vault.save_client_session(settings, client)
    loaded = session_vault.load_string_session(settings)

    assert loaded.save() == "fake-test-session-string"
    assert fake_keyring.storage == {
        (session_vault.KEYCHAIN_SERVICE, settings.session_name): "fake-test-session-string"
    }


def test_delete_session_removes_keychain_entry(settings, monkeypatch):
    fake_keyring = FakeMacOSKeyring()
    monkeypatch.setattr(session_vault.keyring, "get_keyring", lambda: fake_keyring)
    fake_keyring.set_password(session_vault.KEYCHAIN_SERVICE, settings.session_name, "secret")

    session_vault.delete_session(settings)

    assert fake_keyring.get_password(session_vault.KEYCHAIN_SERVICE, settings.session_name) is None


def test_unsafe_keyring_backend_fails_closed(settings, monkeypatch):
    monkeypatch.setattr(session_vault.keyring, "get_keyring", lambda: UnsafeKeyring())

    with pytest.raises(SessionVaultError, match="Небезопасный backend keyring"):
        session_vault.load_string_session(settings)


def test_build_client_uses_string_session_not_legacy_file_name(settings, monkeypatch, tmp_path):
    fake_keyring = FakeMacOSKeyring()
    monkeypatch.setattr(session_vault.keyring, "get_keyring", lambda: fake_keyring)
    monkeypatch.chdir(tmp_path)

    client = build_client(settings)

    assert isinstance(client.session, StringSession)
    assert legacy_session_path(settings) == "test_session.session"
    assert not (tmp_path / "test_session.session").exists()


def test_session_name_selects_keychain_account(settings, monkeypatch):
    fake_keyring = FakeMacOSKeyring()
    monkeypatch.setattr(session_vault.keyring, "get_keyring", lambda: fake_keyring)
    monkeypatch.setattr(session_vault, "StringSession", FakeSession)
    other_settings = replace(settings, session_name="other_session")

    session_vault.save_client_session(settings, FakeClient("first-account-session"))

    assert session_vault.load_string_session(settings).save() == "first-account-session"
    assert session_vault.load_string_session(other_settings).save() == ""
