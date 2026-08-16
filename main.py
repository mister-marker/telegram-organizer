"""
CLI-точка входа.

  python main.py collect                     — собрать метаданные всех диалогов
  python main.py report                      — построить и показать план категоризации
  python main.py apply                       — предпросмотр плана (dry-run, ничего не меняет)
  python main.py apply --yes                  — реально выполнить архивацию/мьют/папки
  python main.py apply --yes --confirm-leave  — дополнительно разрешить выход из
                                                 отмеченных мёртвых групп/каналов
                                                 (необратимо, см. README)
  python main.py undo                         — предпросмотр отката последнего действия
  python main.py undo --yes                   — реально откатить последнее действие
"""
import argparse
import asyncio
import os

from config import load_settings
from tg_client import build_client, ensure_started
from collector import collect_dialogs, save_json, load_json
from classifier import classify
from report import build_plan, print_report
import actions
import undo

DIALOGS_PATH = os.path.join("data", "dialogs.json")
PLAN_PATH = os.path.join("data", "plan.json")


async def cmd_collect(args):
    settings = load_settings()
    client = build_client(settings)
    async with client:
        await ensure_started(client)
        print("Собираем список диалогов...")
        dialogs = await collect_dialogs(client, limit=args.limit)
        save_json(dialogs, DIALOGS_PATH)
        print(f"[ok] Сохранено {len(dialogs)} диалогов -> {DIALOGS_PATH}")


async def cmd_report(args):
    settings = load_settings()
    dialogs = load_json(DIALOGS_PATH)
    categories = {str(d["id"]): classify(d, settings.dead_after_days) for d in dialogs}

    plan = build_plan(dialogs, categories)
    print_report(plan)
    save_json(plan, PLAN_PATH)
    print(f"\n[ok] План сохранён -> {PLAN_PATH}. Можно отредактировать вручную перед 'apply'.")


async def cmd_apply(args):
    settings = load_settings()
    plan = load_json(PLAN_PATH)
    client = build_client(settings)

    dry_run = not args.yes
    if dry_run:
        print("=== РЕЖИМ DRY-RUN: ничего не будет изменено, только предпросмотр ===\n")

    async with client:
        await ensure_started(client)
        for category, dialogs in plan.items():
            print(f"\n--- {category} ({len(dialogs)}) ---")
            if "неактивные" in category.lower():
                await actions.archive_dialogs(client, dialogs, dry_run=dry_run)
                await actions.mute_dialogs(client, dialogs, dry_run=dry_run)
                if args.confirm_leave:
                    await actions.leave_dialogs(client, dialogs, dry_run=dry_run, confirmed=True)
            else:
                await actions.ensure_folder(client, category, dialogs, dry_run=dry_run)

    if dry_run:
        print("\nЭто был предпросмотр. Добавьте --yes, чтобы применить по-настоящему.")


async def cmd_undo(args):
    records = undo.find_undo_candidates(last=args.last)

    dry_run = not args.yes
    if dry_run:
        undo.print_undo_preview(records)
        print("\nЭто был предпросмотр. Добавьте --yes, чтобы откатить по-настоящему.")
        return

    if not records:
        print("[undo] Нет действий archive/mute для отката.")
        return

    settings = load_settings()
    client = build_client(settings)
    async with client:
        await ensure_started(client)
        await undo.undo_records(client, records, dry_run=False)


def main():
    parser = argparse.ArgumentParser(description="Организатор чатов Telegram (на своём аккаунте)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="Собрать метаданные диалогов")
    p_collect.add_argument("--limit", type=int, default=None, help="Ограничить число диалогов (для теста)")

    sub.add_parser("report", help="Построить и показать план категоризации")

    p_apply = sub.add_parser("apply", help="Применить план")
    p_apply.add_argument("--yes", action="store_true", help="Реально выполнить действия (без флага — только просмотр)")
    p_apply.add_argument("--confirm-leave", action="store_true",
                          help="Разрешить выход из мёртвых групп/каналов (необратимо)")

    p_undo = sub.add_parser("undo", help="Откатить последние действия archive/mute из undo_log")
    p_undo.add_argument("--yes", action="store_true", help="Реально выполнить откат (без флага — только просмотр)")
    p_undo.add_argument("--last", type=int, default=1, help="Сколько последних действий откатить")

    args = parser.parse_args()
    handlers = {"collect": cmd_collect, "report": cmd_report, "apply": cmd_apply, "undo": cmd_undo}
    asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    main()
