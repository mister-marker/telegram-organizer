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


def load_settings() -> Settings:
    return Settings(
        api_id=int(_require("TG_API_ID")),
        api_hash=_require("TG_API_HASH"),
        session_name=os.getenv("TG_SESSION_NAME", "tg_organizer"),
        dead_after_days=int(os.getenv("DEAD_AFTER_DAYS", "180")),
    )
