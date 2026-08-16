"""
Классификация диалогов.

По умолчанию — только rule-based логика на основе метаданных и заголовка,
БЕЗ содержимого сообщений. Инструмент полезен уже без единого обращения
к какой-либо AI-модели, что напрямую отвечает вашему требованию к
конфиденциальности.

ai_classify() ниже — точка расширения для будущего этапа (локальная LLM
через Ollama или облачный API). Она ничего никуда не отправляет, пока вы
её явно не подключите и не решите, что именно ей передавать: заголовок
метаданных (низкий риск) или содержимое сообщений (высокий риск,
требует отдельного явного согласия).
"""
import json
import os
from datetime import datetime, timezone

DEFAULT_RULES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")


def _load_rules(path: str = DEFAULT_RULES_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _days_since(iso_date: str | None) -> float | None:
    if not iso_date:
        return None
    dt = datetime.fromisoformat(iso_date)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def classify(dialog: dict, dead_after_days: int, rules: dict | None = None) -> str:
    rules = rules or _load_rules()
    title = dialog["name"].lower()

    # 1. Пользовательские правила по ключевым словам в названии (categories.json)
    for category, keywords in rules.get("keyword_map", {}).items():
        if any(kw.lower() in title for kw in keywords):
            return category

    # 2. Боты — отдельная категория, к ним не применяется логика "активности"
    if dialog["kind"] == "bot":
        return "Боты"

    age_days = _days_since(dialog["last_message_date"])
    is_dead = age_days is not None and age_days > dead_after_days

    # 3. Остальное — по типу диалога и давности последнего сообщения
    if dialog["kind"] == "channel":
        return "Каналы (неактивные)" if is_dead else "Каналы (активные)"
    if dialog["kind"] == "group":
        return "Группы (неактивные)" if is_dead else "Группы (активные)"
    if dialog["kind"] == "private":
        return "Личные (неактивные)" if is_dead else "Личные (активные)"

    return "Разное"


def ai_classify(dialog: dict) -> str:
    """
    Заглушка для Этапа 4 (см. README). Здесь можно подключить локальную
    LLM (Ollama) или облачный API. По умолчанию мы бы рекомендовали
    передавать модели не сырые сообщения, а только заголовок + сводку
    метаданных — этого достаточно для большинства решений о категории,
    и не требует прогонять личную переписку через сторонние сервисы.
    """
    raise NotImplementedError(
        "AI-классификация ещё не подключена — см. README.md, раздел 'Этап 4'."
    )
