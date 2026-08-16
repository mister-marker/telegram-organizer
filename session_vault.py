"""
Хранилище Telegram-сессии в macOS Keychain.

Telethon умеет два основных режима хранения сессии:
  1. Файловый режим: TelegramClient("tg_organizer", ...) создаёт рядом
     SQLite-файл tg_organizer.session. Это удобно, но такой файл равен
     активному входу в аккаунт Telegram.
  2. StringSession: Telethon держит сессию в памяти, а мы сами решаем,
     где хранить сериализованную строку между запусками.

В этом проекте StringSession используется только как транспортный формат
между Telethon и Keychain. Мы не пишем эту строку в .env, JSON, SQLite,
логи или временный файл: на macOS единственное разрешённое постоянное
хранилище секрета — системная связка ключей.
"""
from __future__ import annotations

import keyring
from keyring.backends.macOS import Keyring as MacOSKeyring
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import Settings


KEYCHAIN_SERVICE = "telegram-organizer.telethon-session"


class SessionVaultError(RuntimeError):
    """Ошибка конфигурации или доступа к безопасному хранилищу сессии."""


def _account_name(settings: Settings) -> str:
    return settings.session_name


def _keychain_backend() -> MacOSKeyring:
    """
    Убедиться, что keyring реально пишет в macOS Keychain.

    Библиотека keyring кросс-платформенная: на разных ОС и в разных окружениях
    она может выбрать backend не из системной связки ключей, а из fallback-
    хранилища. Для обычных паролей это иногда приемлемая деградация, но для
    Telegram session-string нет: fallback в файл фактически вернул бы нас к
    исходному риску `.session` на диске. Поэтому приложение жёстко падает,
    если выбран не keyring.backends.macOS.Keyring.
    """
    backend = keyring.get_keyring()
    if not isinstance(backend, MacOSKeyring):
        raise SessionVaultError(
            "Небезопасный backend keyring: "
            f"{type(backend).__module__}.{type(backend).__name__}. "
            "Для Telegram-сессии разрешён только macOS Keychain. "
            "Проверьте окружение Python и доступность Keychain Services."
        )
    return backend


def assert_keychain_backend() -> None:
    _keychain_backend()


def load_string_session(settings: Settings) -> StringSession:
    """
    Загрузить StringSession из Keychain.

    Если записи ещё нет, возвращаем пустую StringSession: Telethon выполнит
    обычный интерактивный login, а после успешного старта мы сохраним новую
    session-string обратно в Keychain.
    """
    backend = _keychain_backend()
    value = backend.get_password(KEYCHAIN_SERVICE, _account_name(settings))
    return StringSession(value) if value else StringSession()


def save_client_session(settings: Settings, client: TelegramClient) -> None:
    """
    Сохранить текущую Telethon-сессию в Keychain.

    client.session.save() возвращает секретную строку, эквивалентную активной
    Telegram-сессии. Мы держим её только в локальной переменной ровно на время
    записи в Keychain и никогда не печатаем её в консоль.
    """
    backend = _keychain_backend()
    session_string = client.session.save()
    if not session_string:
        raise SessionVaultError("Telethon вернул пустую session-string после авторизации.")
    backend.set_password(KEYCHAIN_SERVICE, _account_name(settings), session_string)


def delete_session(settings: Settings) -> None:
    """
    Удалить сохранённую session-string из Keychain.

    Операция идемпотентна для CLI logout: если записи уже нет, считаем, что
    локальный секрет удалён. Это удобно после частично выполненного logout или
    ручной чистки Keychain пользователем.
    """
    backend = _keychain_backend()
    try:
        backend.delete_password(KEYCHAIN_SERVICE, _account_name(settings))
    except keyring.errors.PasswordDeleteError:
        pass
