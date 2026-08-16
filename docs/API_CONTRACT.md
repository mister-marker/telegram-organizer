---
STATUS: DRAFT — не является источником правды до Этапа 3
OWNER: Codex (Tech Lead & Backend)
---

# API_CONTRACT.md — Контракт backend ⇄ frontend

> ⭐ Самый важный файл для Antigravity/Gemini. Как только этот файл помечен `STATUS: STABLE`, Gemini строит React строго по нему, не читая `backend/`. До тех пор — это только каркас, обозначающий форму, а не финальные эндпоинты.

**Кто редактирует:** только Codex. Gemini/Antigravity читает, но не правит — если контракту чего-то не хватает для UI, это заявка Gemini через `docs/HANDOFF.md`, а не прямая правка файла (см. `AGENTS.md` §1, «Правило data flow»).

**Когда становится реальным:** Этап 3 «Web Dashboard» (`docs/ARCHITECTURE.md` §1) — до этого backend — CLI без HTTP-поверхности, контракту нечего описывать. Секции ниже — предварительный каркас на основе FR/пайплайна apply из PRD/ARCHITECTURE, чтобы Gemini мог начать проектировать компоненты заранее; названия полей и путей на Этапе 3 могут измениться.

## 1. Принципы

- Версионирование: префикс `/api/v1/...` с первого реального эндпоинта — ломающие изменения без bump версии запрещены после `STATUS: STABLE`.
- Формат ошибок единый на всё API (см. §5).
- Ничего из `docs/SECURITY.md` §3 («что никогда не попадает в логи») не должно утекать в тела ответов API без явного opt-in пользователя — в частности, полные тексты сообщений возвращаются только там, где FR-06/FR-24 (opt-in чтение содержимого) это разрешают.
- WebSocket-канал — один общий канал прогресса на сессию дашборда (FR-21), не отдельный сокет на каждую операцию.

## 2. Сущности (черновые схемы)

Выведены из FR-05 (метаданные диалогов), FR-08 (категории), FR-14/15 (audit log, undo). Codex уточняет типы на Этапе 3.

```jsonc
// Dialog — единица диалога/чата
{
  "id": "string",              // Telegram peer id
  "title": "string",
  "type": "user | group | channel | bot",
  "participants_count": "number | null",
  "last_message_at": "string (ISO 8601) | null",
  "unread_count": "number",
  "category": "string | null", // одна из FR-08 категорий, либо null до классификации
  "is_premium_limited": "boolean" // упирается ли план в лимиты без Premium, см. FR-19
}

// PlanItem — строка plan-манифеста (пайплайн apply, ARCHITECTURE §4)
{
  "dialog_id": "string",
  "current_category": "string | null",
  "proposed_category": "string",
  "action": "move | archive | keep | virtual_tag", // FR-22 — виртуальные категории
  "user_edited": "boolean" // отличает правку пользователя от AI-предложения, влияет на KPI override-rate
}
// AuditLogEntry — FR-14
{
  "id": "string",
  "timestamp": "string (ISO 8601)",
  "action": "string",
  "dialog_ids": ["string"],
  "reversible": "boolean",
  "undo_log_ref": "string | null"
}

// LLMProviderStatus — статус настройки BYOK
{
  "provider_id": "openai | anthropic | ollama | custom",
  "name": "string",
  "is_configured": "boolean",
  "key_preview": "string | null" // маскированный ключ (например, "sk-...1234"), сами ключи передавать ЗАПРЕЩЕНО
}

```

## 3. Эндпоинты (заявка на структуру, не финал)

| Метод | Путь | Назначение | Источник требования |
|---|---|---|---|
| `GET` | `/api/v1/dialogs` | Список диалогов с метаданными | FR-05 |
| `POST` | `/api/v1/sync` | Запустить/продолжить инкрементальный collect | FR-07, FR-20 |
| `GET` | `/api/v1/plan` | Текущий plan-манифест | ARCHITECTURE §4 |
| `GET` | `/api/v1/settings/llm` | Получить список доступных провайдеров и статус ключей (без самих ключей) | ARCHITECTURE §4 |
| `POST` | `/api/v1/settings/llm` | Сохранить API-ключ выбранного провайдера (отправляется в Keychain) | ARCHITECTURE §4 |
| `DELETE` | `/api/v1/settings/llm/{provider_id}` | Отозвать/удалить сохранённый ключ провайдера из Keychain | `docs/ADR/0005-byok-llm-providers.md`, `docs/SECURITY.md` §2 |
| `PATCH` | `/api/v1/plan/{dialog_id}` | Ручная правка пункта плана (drag-and-drop UI) | FR-09, FR-10 |
| `POST` | `/api/v1/plan/apply?dry_run=true` | Dry-run предпросмотр батча | FR-18 |
| `POST` | `/api/v1/plan/apply` | Реальное применение (после подтверждения, double-flag для опасных действий) | FR-17, `docs/SECURITY.md` §5 |
| `POST` | `/api/v1/undo/{audit_log_id}` | Откат действия | FR-15 |
| `GET` | `/api/v1/audit-log` | История действий | FR-14 |
| `GET` | `/api/v1/network-status` | Экран сетевой прозрачности | FR-23 |
| `GET` | `/api/v1/search?q=...` | Гибридный поиск (Этап 4+) | FR-25 |
| `WS` | `/api/v1/ws/progress` | Прогресс collect/apply в реальном времени | FR-21 |


## 4. WebSocket-сообщения (черновой формат)

```jsonc
{
  "type": "progress | done | error | flood_wait",
  "operation": "collect | apply | index",
  "current": "number",
  "total": "number",
  "message": "string | null",       // никогда не содержит текст сообщений Telegram
  "retry_after_seconds": "number | null" // заполняется при type: flood_wait
}
```

## 5. Формат ошибок (единый)

```jsonc
{
  "error": {
    "code": "string",        // машиночитаемый, например PLAN_LIMIT_EXCEEDED
    "message": "string",     // человекочитаемый, для UI
    "details": "object | null"
  }
}
```

## 6. Открытые вопросы для Codex на Этапе 3

- Аутентификация локального дашборда: нужен ли токен между frontend и localhost-backend, или доверяем localhost-only биндингу?
- Пагинация `/dialogs` при 5000+ диалогах (NFR производительности: дашборд/поиск < 2с) — курсор или offset?
- Формат `retry_after_seconds` при каскаде FloodWait на несколько операций одновременно.

Когда эти вопросы закрыты и первый реальный эндпоинт реализован — сменить `STATUS: DRAFT` на `STATUS: STABLE` в шапке файла и зафиксировать в `docs/HANDOFF.md`.
