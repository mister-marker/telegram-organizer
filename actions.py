"""
Действия, изменяющие состояние аккаунта: архивация, мьют, папки, выход.

Все функции по умолчанию работают в режиме dry_run=True — то есть только
ПЕЧАТАЮТ, что было бы сделано, и ничего не меняют. Реальное применение
требует явного dry_run=False (флаг --yes в main.py).

Каждое РЕАЛЬНО выполненное действие пишется в data/undo_log.jsonl с
состоянием ДО изменения — чтобы при необходимости откатить вручную.

Про поле title в DialogFilter: в установленной версии Telethon (проверено
на 1.44.0) это TypeTextWithEntities, а не обычная строка — схема поменялась
ради поддержки кастомных эмодзи в названиях папок. Мы оборачиваем его
явно; если у вас более старая версия Telethon без TextWithEntities,
делаем откат на обычную строку.
"""
import inspect
import json
import os
import time
from telethon import TelegramClient, functions, types
from ratelimit import with_flood_control

UNDO_LOG_PATH = os.path.join("data", "undo_log.jsonl")


def _log_action(action: str, dialog: dict, before: dict) -> None:
    os.makedirs(os.path.dirname(UNDO_LOG_PATH), exist_ok=True)
    with open(UNDO_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": time.time(),
            "action": action,
            "dialog_id": dialog["id"],
            "name": dialog["name"],
            "before": before,
        }, ensure_ascii=False) + "\n")


async def archive_dialogs(client: TelegramClient, dialogs: list[dict], dry_run: bool = True) -> None:
    for d in dialogs:
        if d["archived"]:
            continue
        if dry_run:
            print(f"[dry-run] Архивировать: {d['name']}")
            continue
        entity = await client.get_entity(d["id"])
        await with_flood_control(lambda e=entity: client.edit_folder(e, 1))
        _log_action("archive", d, before={"archived": False})
        print(f"[done] Заархивирован: {d['name']}")


async def unarchive_dialogs(client: TelegramClient, dialogs: list[dict], dry_run: bool = True) -> None:
    for d in dialogs:
        if not d["archived"]:
            continue
        if dry_run:
            print(f"[dry-run] Разархивировать: {d['name']}")
            continue
        entity = await client.get_entity(d["id"])
        await with_flood_control(lambda e=entity: client.edit_folder(e, 0))
        _log_action("unarchive", d, before={"archived": True})
        print(f"[done] Разархивирован: {d['name']}")


async def mute_dialogs(client: TelegramClient, dialogs: list[dict], dry_run: bool = True,
                        forever: bool = True) -> None:
    for d in dialogs:
        if d["muted"]:
            continue
        if dry_run:
            print(f"[dry-run] Заглушить уведомления: {d['name']}")
            continue
        input_entity = await client.get_input_entity(d["id"])
        # 2**31 - 1 — общепринятое в клиентах Telegram значение "мьют навсегда"
        # (максимум для 32-битной unix-метки времени).
        mute_until = 2 ** 31 - 1 if forever else 0
        peer = types.InputNotifyPeer(peer=input_entity)
        settings = types.InputPeerNotifySettings(mute_until=mute_until)
        await with_flood_control(lambda p=peer, s=settings: client(
            functions.account.UpdateNotifySettingsRequest(peer=p, settings=s)
        ))
        _log_action("mute", d, before={"muted": False})
        print(f"[done] Заглушен: {d['name']}")


def _build_dialog_filter(filter_id: int, title: str, include_peers: list):
    """
    Собираем DialogFilter, подставляя только те поля, которые поддерживает
    установленная версия Telethon (интроспекция сигнатуры вместо жёстко
    зашитого списка полей — схема папок несколько раз менялась между
    слоями Telegram API).
    """
    supported = inspect.signature(types.DialogFilter.__init__).parameters
    kwargs = {"id": filter_id, "include_peers": include_peers,
              "pinned_peers": [], "exclude_peers": []}
    for flag in ("contacts", "non_contacts", "groups", "broadcasts", "bots",
                 "exclude_muted", "exclude_read", "exclude_archived"):
        if flag in supported:
            kwargs[flag] = False
    kwargs = {k: v for k, v in kwargs.items() if k in supported}

    if hasattr(types, "TextWithEntities"):
        try:
            return types.DialogFilter(title=types.TextWithEntities(text=title, entities=[]), **kwargs)
        except TypeError:
            pass
    return types.DialogFilter(title=title, **kwargs)


async def ensure_folder(client: TelegramClient, title: str, dialogs: list[dict],
                         dry_run: bool = True) -> None:
    if dry_run:
        names = ", ".join(d["name"] for d in dialogs[:5])
        more = f" и ещё {len(dialogs) - 5}" if len(dialogs) > 5 else ""
        print(f"[dry-run] Папка «{title}»: {names}{more}")
        return

    existing = await client(functions.messages.GetDialogFiltersRequest())
    filters = getattr(existing, "filters", existing)  # разные слои API возвращают по-разному

    def _title_of(f):
        t = getattr(f, "title", None)
        return getattr(t, "text", t)  # TextWithEntities.text либо обычная строка

    match = next((f for f in filters if _title_of(f) == title), None)
    used_ids = {getattr(f, "id", 0) for f in filters}
    filter_id = match.id if match else next(i for i in range(2, 256) if i not in used_ids)

    include_peers = [await client.get_input_entity(d["id"]) for d in dialogs]
    dialog_filter = _build_dialog_filter(filter_id, title, include_peers)

    try:
        await with_flood_control(lambda: client(
            functions.messages.UpdateDialogFilterRequest(id=filter_id, filter=dialog_filter)
        ))
        print(f"[done] Папка «{title}» обновлена ({len(dialogs)} чатов)")
    except Exception as e:
        print(f"[error] Не удалось создать/обновить папку «{title}»: {e}")
        print("        Проверьте версию Telethon (pip show telethon). Это самая "
              "чувствительная к версии API часть инструмента — см. README.")


async def leave_dialogs(client: TelegramClient, dialogs: list[dict],
                         dry_run: bool = True, confirmed: bool = False) -> None:
    """
    Самое необратимое действие в наборе: выход из группы/канала обычно
    удаляет локальную историю переписки в этом чате. Поэтому:
      - работает ТОЛЬКО для групп и каналов (никогда для личных чатов);
      - требует dry_run=False И confirmed=True одновременно;
      - действие логируется в undo_log.jsonl только после успешного выполнения.
    """
    targets = [d for d in dialogs if d["kind"] in ("group", "channel")]
    for d in targets:
        if dry_run or not confirmed:
            print(f"[dry-run] Выйти из: {d['name']} (нужен флаг --confirm-leave)")
            continue
        entity = await client.get_entity(d["id"])
        await with_flood_control(lambda e=entity: client.delete_dialog(e))
        _log_action("leave", d, before={"member": True})
        print(f"[done] Покинут: {d['name']}")
