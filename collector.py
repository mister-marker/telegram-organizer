"""
Сбор метаданных по диалогам.

Принципиально: здесь НЕ читается содержимое сообщений — только метаданные
диалога (тип, активность, статус, заголовок). Это осознанное решение по
конфиденциальности: базовая классификация не требует отправки текста
переписки куда-либо, включая любые AI-модели. Опциональный анализ
содержимого — отдельный, явно включаемый шаг на будущем этапе (см.
classifier.ai_classify и README, раздел "Этап 4").
"""
import json
import os
from telethon import TelegramClient


async def collect_dialogs(client: TelegramClient, limit: int | None = None) -> list[dict]:
    result = []
    async for dialog in client.iter_dialogs(limit=limit):
        entity = dialog.entity

        mute_until = None
        try:
            mute_until = dialog.dialog.notify_settings.mute_until
        except AttributeError:
            pass

        result.append({
            "id": dialog.id,
            "name": dialog.name or "Без названия",
            "kind": _kind(dialog),
            "unread_count": dialog.unread_count,
            "unread_mentions_count": dialog.unread_mentions_count,
            "archived": bool(dialog.archived),
            "pinned": bool(dialog.pinned),
            "muted": mute_until is not None,
            "last_message_date": dialog.date.isoformat() if dialog.date else None,
            "has_username": bool(getattr(entity, "username", None)),
        })
    return result


def _kind(dialog) -> str:
    if dialog.is_channel and not dialog.is_group:
        return "channel"
    if dialog.is_group:
        return "group"
    if dialog.is_user:
        return "bot" if getattr(dialog.entity, "bot", False) else "private"
    return "unknown"


def save_json(data, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
