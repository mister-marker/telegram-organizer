"""
Device fingerprint для Telethon-клиента.

Когда MTProto-клиент подключается к Telegram, он отправляет не только api_id
и авторизационные данные, но и metadata подключения: модель устройства,
версию ОС, версию приложения и язык. В Telegram API эти поля входят в
обёртку initConnection; Telethon прокидывает их через параметры
TelegramClient(device_model=..., system_version=..., app_version=...).

Это НЕ делает приложение "невидимым" и не является способом обхода правил
Telegram. Смысл здесь проще и честнее: не светить дефолтным библиотечным
отпечатком, когда пользователь запускает локальный desktop-инструмент на
macOS. Все остальные меры безопасности — read-only по умолчанию, dry-run,
rate limiter и Keychain — остаются обязательными.
"""
from __future__ import annotations

from dataclasses import dataclass
import platform
import subprocess

from config import Settings


@dataclass(frozen=True)
class DeviceFingerprint:
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    system_lang_code: str

    def as_telethon_kwargs(self) -> dict:
        return {
            "device_model": self.device_model,
            "system_version": self.system_version,
            "app_version": self.app_version,
            "lang_code": self.lang_code,
            "system_lang_code": self.system_lang_code,
        }


def build_device_fingerprint(settings: Settings) -> DeviceFingerprint:
    """
    Собрать fingerprint из явных настроек и безопасных локальных источников.

    Приоритет такой:
      1. Значение из .env, если пользователь явно задал override.
      2. Реальная информация macOS, которую можно прочитать локально.
      3. Консервативный fallback, если окружение не похоже на macOS или
         системная команда недоступна.

    Мы не читаем ничего чувствительного: модель Mac и версия macOS не являются
    Telegram-сессией, текстом сообщений или пользовательскими секретами.
    """
    return DeviceFingerprint(
        device_model=settings.device_model or detect_mac_device_model(),
        system_version=settings.system_version or detect_macos_version(),
        app_version=settings.app_version,
        lang_code=settings.lang_code,
        system_lang_code=settings.system_lang_code,
    )


def detect_mac_device_model() -> str:
    raw_model = _sysctl_hw_model()
    if not raw_model:
        return "MacBook Pro"
    return _humanize_mac_model(raw_model)


def detect_macos_version() -> str:
    version = platform.mac_ver()[0]
    return f"macOS {version}" if version else "macOS"


def _sysctl_hw_model() -> str | None:
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _humanize_mac_model(raw_model: str) -> str:
    """
    Превратить аппаратный код macOS в человекочитаемое имя.

    sysctl обычно возвращает что-то вроде MacBookAir10,1 или MacBookPro18,3.
    Для Telegram device list человек ожидает видеть семейство устройства, а не
    внутренний hardware identifier, поэтому нормализуем известные префиксы.
    """
    prefixes = (
        ("MacBookAir", "MacBook Air"),
        ("MacBookPro", "MacBook Pro"),
        ("MacBook", "MacBook"),
        ("Macmini", "Mac mini"),
        ("MacStudio", "Mac Studio"),
        ("MacPro", "Mac Pro"),
        ("iMacPro", "iMac Pro"),
        ("iMac", "iMac"),
    )
    for prefix, label in prefixes:
        if raw_model.startswith(prefix):
            return label
    return "Mac"
