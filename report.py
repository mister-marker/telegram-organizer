"""
Отчёт по результатам классификации: таблица в консоли + сохранение плана
(data/plan.json), который затем можно вручную отредактировать и применить
командой `apply`.
"""
from collections import defaultdict
from rich.console import Console
from rich.table import Table

console = Console()


def build_plan(dialogs: list[dict], categories: dict[str, str]) -> dict:
    """categories: {str(dialog_id): category_name}"""
    plan = defaultdict(list)
    for d in dialogs:
        cat = categories.get(str(d["id"]), "Разное")
        plan[cat].append(d)
    return dict(plan)


def print_report(plan: dict) -> None:
    table = Table(title="Предлагаемая структура")
    table.add_column("Категория", style="bold cyan")
    table.add_column("Чатов", justify="right")
    table.add_column("Непрочитано", justify="right")

    total = 0
    for category, dialogs in sorted(plan.items(), key=lambda kv: -len(kv[1])):
        unread = sum(d["unread_count"] for d in dialogs)
        table.add_row(category, str(len(dialogs)), str(unread))
        total += len(dialogs)

    console.print(table)
    console.print(f"\nВсего диалогов: [bold]{total}[/bold]")
