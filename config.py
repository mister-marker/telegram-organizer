"""
Загрузка конфигурации из .env.

Никаких значений по умолчанию для api_id/api_hash — они обязаны прийти
из окружения, иначе явная ошибка со ссылкой на my.telegram.org, а не
непонятный сбой где-то в середине работы.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Переменная {name} не задана.\n"
            f"1) Скопируйте .env.example в .env\n"
            f"2) Получите api_id и api_hash на https://my.telegram.org "
            f"(раздел 'API development tools')\n"
            f"3) Впишите их в .env"
        )
    return value


@dataclass
class Settings:
    api_id: int
    api_hash: str
    session_name: str
    dead_after_days: int
    device_model: str | None = None
    system_version: str | None = None
    app_version: str = "5.16.4"
    lang_code: str = "en"
    system_lang_code: str = "en"
    has_premium: bool = False


def load_settings() -> Settings:
    return Settings(
        api_id=int(_require("TG_API_ID")),
        api_hash=_require("TG_API_HASH"),
        session_name=os.getenv("TG_SESSION_NAME", "tg_organizer"),
        dead_after_days=int(os.getenv("DEAD_AFTER_DAYS", "180")),
        device_model=_optional("TG_DEVICE_MODEL"),
        system_version=_optional("TG_SYSTEM_VERSION"),
        app_version=os.getenv("TG_APP_VERSION", "5.16.4"),
        lang_code=os.getenv("TG_LANG_CODE", "en"),
        system_lang_code=os.getenv("TG_SYSTEM_LANG_CODE", "en"),
        has_premium=_bool_env("TG_HAS_PREMIUM", default=False),
    )


def _optional(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _bool_env(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
