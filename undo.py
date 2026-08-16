"""
Автоматический откат действий из data/undo_log.jsonl.

Файл undo_log хранится в формате JSONL: одна JSON-запись на одну строку.
Это удобнее обычного большого JSON-массива для audit/undo-журнала, потому
что новые события можно дописывать append-only, не переписывая весь файл.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Iterable

from telethon import TelegramClient, functions, types

import actions
from ratelimit import with_flood_control


SUPPORTED_UNDO_ACTIONS = {"archive", "unarchive", "mute"}


@dataclass
class UndoRecord:
    undo_id: str
    action: str
    dialog_id: int
    name: str
    before: dict
    status: str
    ts: float
    reversible: bool = True


def read_undo_log(path: str | None = None) -> list[dict]:
    """
    Прочитать JSONL-журнал построчно.

    Здесь обычный синхронный for, а не async for: чтение маленького локального
    файла не требует сетевого ожидания. Async начинается позже, когда undo
    делает реальные Telegram-запросы и каждое await отдаёт управление event
    loop, пока Telethon ждёт ответ сети.
    """
    path = path or actions.UNDO_LOG_PATH
    if not os.path.exists(path):
        return []

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entry["_line_no"] = line_no
            entries.append(entry)
    return entries


def build_undo_records(entries: Iterable[dict]) -> list[UndoRecord]:
    """
    Собрать события append-only журнала в текущее состояние каждого undo_id.

    У одного действия может быть несколько строк:
      snapshot -> applied -> undone
    или:
      snapshot -> failed

    Snapshot-only запись тоже считается кандидатом на аккуратное восстановление:
    процесс мог упасть во время Telegram-запроса, и для archive/mute обратное
    действие идемпотентно достаточно безопасно.
    """
    grouped: dict[str, dict] = {}

    for entry in entries:
        event = entry.get("event", "snapshot")
        undo_id = entry.get("undo_id")
        if not undo_id:
            undo_id = f"legacy:{entry.get('dialog_id')}:{entry.get('ts')}:{entry.get('_line_no')}"
            event = "snapshot"

        state = grouped.setdefault(undo_id, {
            "events": set(),
            "snapshot": None,
            "reversible": True,
        })
        state["events"].add(event)

        if event == "snapshot":
            state["snapshot"] = entry
        if entry.get("reversible") is False:
            state["reversible"] = False

    records = []
    for undo_id, state in grouped.items():
        snapshot = state["snapshot"]
        if not snapshot:
            continue

        events = state["events"]
        if "undone" in events:
            status = "undone"
        elif "failed" in events:
            status = "failed"
        elif "applied" in events:
            status = "applied"
        else:
            status = "snapshot_only"

        records.append(UndoRecord(
            undo_id=undo_id,
            action=snapshot["action"],
            dialog_id=snapshot["dialog_id"],
            name=snapshot["name"],
            before=snapshot.get("before", {}),
            status=status,
            ts=snapshot.get("ts", 0),
            reversible=state["reversible"],
        ))

    return sorted(records, key=lambda r: r.ts)


def find_undo_candidates(*, last: int = 1, path: str | None = None) -> list[UndoRecord]:
    if last <= 0:
        return []
    records = build_undo_records(read_undo_log(path))
    candidates = [
        r for r in reversed(records)
        if r.reversible
        and r.status in ("applied", "snapshot_only")
        and r.action in SUPPORTED_UNDO_ACTIONS
    ]
    return candidates[:last]


def print_undo_preview(records: list[UndoRecord]) -> None:
    if not records:
        print("[undo] Нет действий archive/mute для отката.")
        return

    print("=== РЕЖИМ DRY-RUN: undo ничего не изменит, только покажет план ===\n")
    for r in records:
        note = "write-ahead snapshot без applied-маркера" if r.status == "snapshot_only" else "applied"
        print(f"[dry-run] Откатить {r.action}: {r.name} ({note})")


async def undo_records(client: TelegramClient, records: list[UndoRecord], *, dry_run: bool = True) -> None:
    """
    Асинхронно выполнить обратные Telegram-действия.

    Цикл намеренно последовательный. На каждой итерации await делает паузу
    в нашей coroutine и возвращает управление event loop: Python не блокирует
    весь процесс, пока Telethon ждёт сеть, но мы не запускаем параллельные
    Telegram-запросы и не обходим rate limiter.
    """
    for record in records:
        if dry_run:
            print(f"[dry-run] Откатить {record.action}: {record.name}")
            continue

        if record.action in ("archive", "unarchive"):
            await _undo_archive_state(client, record)
        elif record.action == "mute":
            await _undo_mute_state(client, record)
        else:
            print(f"[skip] Undo для действия {record.action!r} пока не поддержан.")
            continue

        actions._mark_undo_event(record.undo_id, "undone")
        print(f"[undone] Откат выполнен: {record.name}")


async def _undo_archive_state(client: TelegramClient, record: UndoRecord) -> None:
    entity = await client.get_entity(record.dialog_id)
    folder_id = 1 if record.before.get("archived") else 0
    await with_flood_control(lambda e=entity, f=folder_id: client.edit_folder(e, f))


async def _undo_mute_state(client: TelegramClient, record: UndoRecord) -> None:
    input_entity = await client.get_input_entity(record.dialog_id)
    mute_until = 2 ** 31 - 1 if record.before.get("muted") else 0
    peer = types.InputNotifyPeer(peer=input_entity)
    settings = types.InputPeerNotifySettings(mute_until=mute_until)
    await with_flood_control(lambda p=peer, s=settings: client(
        functions.account.UpdateNotifySettingsRequest(peer=p, settings=s)
    ))
