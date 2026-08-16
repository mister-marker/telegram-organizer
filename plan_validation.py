"""
Предвалидация plan.json перед apply.

Fail-fast идея простая: если план заведомо не помещается в лимиты Telegram,
мы должны остановиться до создания Telethon-клиента и до любого сетевого
запроса. Это дешевле, безопаснее и понятнее пользователю, чем начинать batch
apply, дойти до `UpdateDialogFilterRequest`, получить ошибку от Telegram и
оставить часть действий уже выполненными.

Модуль намеренно синхронный и "чистый": на вход приходит обычный dict из
data/plan.json, на выходе либо OK, либо структурированная ошибка. Здесь нет
`await`, потому что нет сети, файлового I/O или Telegram API. Поток данных:

    plan.json -> collector.load_json() -> validate_plan_limits() -> apply

Только после успешной validate_plan_limits() CLI имеет право строить
TelegramClient и переходить к dry-run/apply циклу.
"""
from __future__ import annotations

from dataclasses import dataclass


FREE_LIMITS = "free"
PREMIUM_LIMITS = "premium"


@dataclass(frozen=True)
class FolderLimits:
    account_kind: str
    folder_count: int
    chats_per_folder: int


@dataclass(frozen=True)
class PlanValidationIssue:
    code: str
    message: str


class PlanValidationError(ValueError):
    def __init__(self, limits: FolderLimits, issues: list[PlanValidationIssue]):
        self.limits = limits
        self.issues = issues
        super().__init__(format_plan_validation_error(limits, issues))


def limits_for_account(*, has_premium: bool) -> FolderLimits:
    if has_premium:
        return FolderLimits(account_kind=PREMIUM_LIMITS, folder_count=20, chats_per_folder=200)
    return FolderLimits(account_kind=FREE_LIMITS, folder_count=10, chats_per_folder=100)


def is_archive_category(category: str) -> bool:
    """
    Повторить бизнес-правило cmd_apply: категории с "неактивные" не становятся
    Telegram-папками, а идут в archive/mute pipeline. Поэтому их нельзя
    считать против лимита папок.
    """
    return "неактивные" in category.lower()


def folder_categories(plan: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {category: dialogs for category, dialogs in plan.items() if not is_archive_category(category)}


def validate_plan_limits(plan: dict[str, list[dict]], *, has_premium: bool = False) -> None:
    limits = limits_for_account(has_premium=has_premium)
    folders = folder_categories(plan)
    issues: list[PlanValidationIssue] = []

    if len(folders) > limits.folder_count:
        issues.append(PlanValidationIssue(
            code="TOO_MANY_FOLDERS",
            message=f"папок: {len(folders)} из {limits.folder_count}",
        ))

    for category, dialogs in folders.items():
        if len(dialogs) > limits.chats_per_folder:
            issues.append(PlanValidationIssue(
                code="TOO_MANY_CHATS_IN_FOLDER",
                message=f"«{category}»: {len(dialogs)} чатов из {limits.chats_per_folder}",
            ))

    if issues:
        raise PlanValidationError(limits, issues)


def format_plan_validation_error(limits: FolderLimits, issues: list[PlanValidationIssue]) -> str:
    lines = [
        f"[plan-error] План превышает лимиты Telegram folders для {limits.account_kind}-аккаунта:",
    ]
    lines.extend(f"- {issue.message}" for issue in issues)
    lines.append(
        "Решение: уменьшите категории в data/plan.json, включите "
        "TG_HAS_PREMIUM=true если аккаунт Premium, или оставьте часть чатов "
        "вне Telegram-папок."
    )
    return "\n".join(lines)
