# TASKS.md — Доска задач

> Обновляется после каждой завершённой задачи — тем агентом, который её закрыл, либо CEO. Это не Jira: плоский список, читаемый всеми агентами без доступа к внешним таск-трекерам. Если задача блокирует другого агента — это фиксируется явно в колонке «Блокирует» и дублируется в `docs/HANDOFF.md`.

## Как пользоваться этим файлом

1. Перед началом задачи агент проверяет, не занята ли она уже (`In Progress` у другого агента).
2. Берёт задачу → переводит в `In Progress`, проставляет свою роль и ветку.
3. Закончил → переводит в `Review` (если нужен CEO Merge Approval) или сразу в `Done` (если задача не требует мерджа, например аудит Aider).
4. Если задача открыла новую работу для другого агента — новая строка + запись в `docs/HANDOFF.md`.

Статусы: `Backlog` → `In Progress` → `Review` → `Done`. Отдельно — `Blocked`, если задача упёрлась в решение CEO или в незакрытую зависимость.

## Легенда колонки «Кто»

👑 CEO · 🏗️ Codex (Backend) · 🎨 Gemini/Antigravity (Frontend) · 🕵️ Aider (QA, только предложения)

---

## Этап 1 — CLI Baseline ✅ (завершён)

| ID | Задача | Кто | Статус |
|---|---|---|---|
| S1-01 | Read-only аудит диалогов, rule-based классификация | 🏗️ Codex | Done |
| S1-02 | Manual edit plan.json, Rich CLI вывод статистики | 🏗️ Codex | Done |

## Этап 2 — Undo + Safety (текущий)

| ID | Задача | Кто | Ветка | Блокирует | Статус |
|---|---|---|---|---|---|
| S2-01 | ~~Rate limiter: проактивная пауза + обработка `FloodWaitError`~~ — оба механизма уже в `ratelimit.py` (фиксированный `PACE_SECONDS=1.0` + реактивный `FloodWaitError`). Осталось: валидация реального темпа на песочном аккаунте, при необходимости — сделать паузу адаптивной вместо фиксированной (скилл `rate-limiter`) | 🏗️ Codex | `stage/rate-limiter` | — | Review |
| S2-02 | Session vault: Telethon переведён с файлового `.session` на `StringSession` + macOS Keychain через `keyring`; fallback backend запрещён fail-closed; добавлен `logout` для удаления Keychain-записи. Legacy `.session` не мигрируется автоматически, только предупреждение пользователю. | 🏗️ Codex | `stage/session-vault` | — | Review |
| S2-03 | Команда `undo`: реализован write-ahead append-only `undo_log.jsonl` для archive/unarchive/mute (`snapshot` до Telegram API, затем `applied`/`failed`), добавлена CLI-команда `undo` с dry-run по умолчанию и реальным откатом archive/mute по `--yes`. Папки пока не включены в automatic undo: нужен полный snapshot `DialogFilter` до `ensure_folder`. | 🏗️ Codex | `stage/undo-and-tests` | — | Review |
| S2-04 | Валидация лимитов папок (10/100 без Premium, 20/200 с Premium) до apply | 🏗️ Codex | `stage/plan-validation` | — | Backlog |
| S2-05 | Device fingerprint при авторизации: добавлен `device_fingerprint.py`, Telethon получает `device_model`, `system_version`, `app_version`, `lang_code`, `system_lang_code` при создании клиента; модель Mac и версия macOS определяются локально, `.env` может переопределить значения. | 🏗️ Codex | `stage/device-fingerprint` | — | Review |
| S2-06 | pytest + fake Telethon client — минимальный harness создан для S2-03 (`tests/test_undo_journal.py`: write-ahead archive/mute и undo archive без реального Telegram API). Расширить на S2-01/S2-02/S2-04/S2-05 отдельными тестами. | 🏗️ Codex | `stage/undo-and-tests` | — | In Progress |
| S2-07 | Security-CI grep-проверки из `docs/SECURITY.md` §7 как pre-commit/CI шаг | 🏗️ Codex | `stage/security-ci` | — | Backlog |
| S2-08 | Аудит S2-01–S2-05 перед PR: risk review, поиск багов | 🕵️ Aider | — (не коммитит) | — | Backlog |

## Этап 3 — Web Dashboard (не начат)

| ID | Задача | Кто | Ветка | Блокирует | Статус |
|---|---|---|---|---|---|
| S3-01 | Наполнить `docs/API_CONTRACT.md` реальными эндпоинтами, сменить STATUS: DRAFT → STABLE | 🏗️ Codex | `stage/api-contract` | S3-02 | Backlog |
| S3-02 | FastAPI-скелет под контракт (`backend/app/main.py`, `backend/app/api/`) | 🏗️ Codex | `stage/fastapi-skeleton` | — | Backlog |
| S3-03 | Инициализация `frontend-worktree/` (git worktree), Vite + React + Tailwind скелет | 🎨 Gemini | `ui/init` | — | Backlog |
| S3-04 | Dashboard: статистика, список диалогов по `GET /dialogs` | 🎨 Gemini | `ui/dashboard` | S3-01 | Backlog |
| S3-05 | Plan Editor: drag-and-drop редактор плана (FR-10) | 🎨 Gemini | `ui/plan-editor` | S3-01 | Backlog |
| S3-06 | WS-прогресс в дашборде (FR-21) | 🎨 Gemini | `ui/ws-progress` | S3-01 | Backlog |
| S3-07 | История действий / audit log UI (FR-14) | 🎨 Gemini | `ui/history` | S3-01 | Backlog |

## Backlog без привязки к этапу

| ID | Задача | Кто | Статус |
|---|---|---|---|
| BL-01 | Заполнить `docs/ADR/0004-supabase-later.md` оригинальным текстом, если найдётся исходник | 👑 CEO | Backlog |
| BL-02 | Проверить точный model-string kimi-k3-free/qwen3.8-max-free в `.aider.conf.yml` | 👑 CEO | Backlog |
| BL-03 | Собрать реальный сеанс на песочном аккаунте под первый прогон Этапа 2 | 👑 CEO | Backlog |
| BL-04 | ⏰ Решено (16.08.2026): после 31.08 Aider переходит на платную модель (Kimi K2.5 или актуальный аналог на OpenRouter), не на ручной аудит. Осталось: завести API-ключ/биллинг у провайдера и переключить `model:` в `.aider.conf.yml` к 31.08 | 👑 CEO | Backlog |
| BL-05 | При старте Этапа 4: реализация LLMProviderInterface (ADR-0005) для поддержки сторонних API-ключей. | 🏗️ Codex | Backlog |
| BL-06 | Dockerfile для CLI-ядра (Этапы 1–2) — второй канал дистрибуции для обратной связи от друзей-разработчиков, параллельно с Tauri (Этап 5), не вместо него. Сессия внутри контейнера — зашифрованный файл (`cryptography.fernet`, ключ из переменной окружения, не в образе), см. `docs/SECURITY.md` §2a | 🏗️ Codex | Backlog |

---

## Журнал закрытых задач (архив)

_Пусто — первая задача, закрытая после введения этой доски, переносится сюда с датой._
