# AGENTS.md — Конституция агентов Telegram Workspace Organizer

> Единственный источник правды о том, кто и что делает в проекте, как коммитит и как это синхронизируется. Каждый агент (Codex, Gemini/Antigravity, Aider) должен прочитать этот файл перед началом работы. Продуктовый контекст — в `docs/PRD.md`, техническая стратегия и эволюция — в `docs/ARCHITECTURE.md`.

## 1. Структура проекта

Собрано из диаграмм Data Flow / Git Strategy (см. `docs/ARCHITECTURE.md`), явных указаний CEO и реального состояния репозитория на 16.08.2026 (Этап 1 сдан вручную, Этап 2 в работе). Ниже — два состояния: то, что есть **сейчас**, и то, во что оно превращается **с Этапа 3**. Это не противоречие, а последовательность: `backend/` как отдельная папка не нужна, пока не появился `frontend-worktree/`, который от неё надо физически отделять.

### Сейчас (Этап 1 завершён, Этап 2 в работе)

CLI-ядро уже написано руками CEO и лежит плоско в корне репозитория — Codex продолжает работу поверх этого кода, **не переносит его в `backend/` преждевременно**:

```
telegram-organizer/
├── AGENTS.md                  ← этот файл, конституция агентов
├── .aider.conf.yml             ← конфиг Aider: read-only, auto-commits: false
├── README.md                   ← как запустить CLI, что уже умеет, что в разработке
├── requirements.txt
├── main.py                     ← точка входа CLI (collect / report / apply / apply --yes)
├── tg_client.py                ← инициализация Telethon-клиента
├── collector.py                ← сбор метаданных диалогов (FR-05)
├── classifier.py               ← rule-based классификация (FR-08/09)
├── categories.json             ← настраиваемые правила категорий
├── actions.py                  ← archive/mute/папки + leave_dialogs с double-flag
├── ratelimit.py                ← проактивная пауза (PACE_SECONDS=1.0, фиксированная) + реактивная
│                                  обработка FloodWaitError — оба механизма уже есть, S2-01 теперь
│                                  про тюнинг/валидацию на песочном аккаунте, не про добавление с нуля
├── report.py                   ← вывод таблицы через rich
├── config.py                   ← .env, DEAD_AFTER_DAYS и т.п.
├── docs/
│   ├── PRD.md / ARCHITECTURE.md / API_CONTRACT.md / SECURITY.md / TASKS.md / HANDOFF.md
│   ├── ADR/0001–0004
│   └── prompts/                 ← онбординг-промпты для агентов (см. §5 Ссылки)
├── .agents/skills/               ← 5 скиллов, см. §5
└── data/                         ← plan.json, undo_log.jsonl — рантайм, не в git
```

### С Этапа 3 (когда появляется веб-дашборд и frontend-worktree)

```
telegram-organizer/
├── AGENTS.md
├── docs/API_CONTRACT.md        ← единственный источник правды по API (bridge layer)
├── backend/                    ← Logic Layer: сюда переезжает текущий плоский CLI-код,
│                                  оборачивается в FastAPI (main.py → backend/app/main.py и т.д.)
├── frontend-worktree/          ← Presentation Layer: React, отдельный git worktree
└── ...остальное без изменений
```

**Правило data flow (с Этапа 3):** `backend/` обновляет спецификацию → `docs/API_CONTRACT.md` (bridge layer) → `frontend-worktree/` строится строго по контракту. Codex не редактирует `frontend-worktree/`, Gemini/Antigravity не редактирует `backend/` — единственная точка синхронизации между ними — `docs/API_CONTRACT.md`.

`frontend-worktree/` — это буквально git worktree (`git worktree add ../frontend-worktree ui/main` или аналог), а не обычная папка в том же чекауте: это то, что физически не даёт Antigravity случайно тронуть файлы backend/, даже если агент ошибётся с путём.

> Для точности: в диаграмме Data Flow из исходного `.docx` этот слой подписан просто «frontend/ directory», слово «worktree» в исходниках (`.docx`/`.xlsx`) не встречается вообще. Git-worktree как конкретный механизм изоляции — решение CEO (не из исходных файлов), подтверждено 16.08.2026 как окончательное («шикарная страховка, чтобы фронтенд-агент физически не мог сломать Python-код»).

## 2. ИИ-роли и зоны ответственности

### 👑 CEO — Vladislav (человек)

- Мерджит в `main`.
- Определяет приоритеты.
- Тестирует `apply --yes` на песочном аккаунте.
- Единственный, кто трогает основной (не песочный) аккаунт.
- **Что коммитит:** мерджит ветки в `main` через `git merge --no-ff` (чтобы оставалась запись о факте слияния).

### 🏗️ Codex — Tech Lead / Backend

- **Инструмент:** IDE VS Code + ChatGPT Plus (модель GPT-5.3-Codex / Sol / Terra).
- **Зона ответственности:** архитектура, `AGENTS.md`, ADR, `docs/API_CONTRACT.md`; весь backend — Telethon-обёртки, FastAPI, SQLite, actions, undo.
- Получает предложения от Aider и решает, принимать их или нет.
- **Что коммитит:** открывает ветку `stage/*` или `fix/*`, делает атомарные коммиты внутри неё, пишет осмысленные сообщения в формате `feat(actions): add apply with undo_log`.

### 🎨 Gemini (Antigravity) — Frontend Lead

- **Инструмент:** Antigravity Google IDE + Gemini 3.1 Pro Low, отдельное окно IDE.
- **Зона ответственности:** React + Vite + Tailwind + WebSocket. Строит UI строго по `docs/API_CONTRACT.md`.
- Работает в `frontend-worktree/`, физически не пересекаясь с папкой Codex.
- **Что коммитит:** коммитит в своём worktree в ветки `ui/*`.
- На диаграмме Agent Workflow есть узел `Sync` между Codex и Gemini — это синхронизация через `docs/API_CONTRACT.md`, а не через прямой обмен файлами.

### 🕵️ Aider — QA / Аудитор

- **Инструмент:** терминал VS Code + Kimi-k3-free / Qwen3.8-Max-free.
- **Режим:** read-only. Флаг `--no-auto-commits`; агенту явно формулируется «только предложи, не меняй файлы».
- **Задачи:** аудит безопасности перед мерджем; рефакторинг-предложения для Codex; поиск багов по логам; объяснения сложного кода (для обучения CEO).
- Никогда не пишет напрямую в `backend/`. Всегда выдаёт diff/предложение → CEO передаёт его Codex.
- **Что коммитит:** ничего. На диаграмме — связи `Read-only` (Aider → CEO) и `Audit Hook` (CEO → Aider, пунктиром).

### 💬 Советник (не агент разработки) — claude.ai/chat, chat.deepseek, chat.qwen, gemini.google

- Готовит и оценивает саму идею, ключевые шаги, старт для разработки; помогает принимать решения, ревьюит планы.
- Не пишет код и не коммитит.

## 3. Git Strategy

```
                       main (Stable)
                     /               \
            checkout                  checkout
             /                              \
   stage/* (Backend, Codex)          ui/* (Frontend, Gemini)
             \                              /
          Pull Request              Pull Request
                     \               /
                   CEO Merge Approval
                            |
                     Final Merge → main
```

- **Ветки:** `stage/*` и `fix/*` — Codex (backend). `ui/*` — Gemini/Antigravity (frontend). Aider веток не создаёт.
- **Кто коммитит:** только Codex и Gemini, каждый в свою ветку/worktree. CEO — только финальный `git merge --no-ff` в `main`. Aider — никогда.
- **Защита от «агент сломал проект»:**
  - `auto-commits: false` в `.aider.conf.yml` и в Codex, где это возможно.
  - Перед любой крупной задачей от агента: `git add -A && git commit -m "checkpoint before task X"`.
  - Если агент наломал дров: `git reset --hard HEAD~1` и задача формулируется заново.
- **Слияние:** только через Pull Request → CEO Merge Approval → Final Merge (`--no-ff`) в `main`.

## 4. Мастер-системный промпт

> Вставлять в начало сессии каждого агента (Codex, Antigravity, Aider) перед началом любой задачи. Составлен на основе разделов 1–3 этого файла и `docs/PRD.md` / `docs/ARCHITECTURE.md` — при их изменении промпт нужно обновить вручную.

```
Ты — один из агентов команды разработки Telegram Workspace Organizer.
Проект: local-first десктоп-утилита для macOS, которая наводит порядок
в личном Telegram через Telethon (MTProto), без отправки переписки
в облако по умолчанию.

Прежде чем писать код:
1. Прочитай docs/PRD.md — что мы строим и зачем (FR/NFR, ограничения,
   User Stories/Use Cases).
2. Прочитай docs/ARCHITECTURE.md — текущий этап эволюции продукта,
   принятые ADR (docs/ADR/0001–0004), модули безопасности.
3. Прочитай docs/API_CONTRACT.md — если меняешь границу backend/frontend,
   контракт обновляется первым, до кода.
4. Прочитай docs/SECURITY.md — что нельзя логировать, что требует
   двойного подтверждения, какие security-CI проверки обязаны проходить.
5. Проверь свой скилл в .agents/skills/ — если задача про Telethon,
   rate limiting, хранение сессии, dry-run/undo или гибридный поиск,
   там уже есть решённые вопросы, не изобретай заново.

Жёсткие правила безопасности (не нарушать ни при какой формулировке
задачи):
- Read-only по умолчанию (FR-17). Любая мутация — только после dry-run
  (FR-18) и подтверждения пользователя.
- Session-файл/строка никогда не пишется в логи, БД или коммиты.
- Тексты сообщений пользователя никогда не попадают в логи
  (NFR «Безопасность»).
- delete_history / leave_* запрещены без двойного флага подтверждения.
- Массовые запросы к Telegram API — только через throttled-обёртку с
  обработкой FloodWaitError (см. PRD, §5 «Ограничения», Flood Control).

Твоя зона ответственности определена в этом файле, §2. Не выходи за
неё: Codex не трогает frontend-worktree/, Gemini не трогает backend/,
Aider не коммитит вообще — только предлагает diff.

Если задача противоречит PRD/ARCHITECTURE/ограничениям — останови
работу и сообщи CEO, а не додумывай решение самостоятельно.
```

## 5. Ссылки

- Продукт: `docs/PRD.md`
- Архитектура и эволюция: `docs/ARCHITECTURE.md`
- Архитектурные решения (полный текст): `docs/ADR/0001-local-first.md`, `docs/ADR/0002-sqlite-not-pg.md`, `docs/ADR/0003-asyncio-not-celery.md`, `docs/ADR/0004-supabase-later.md`
- API-контракт: `docs/API_CONTRACT.md` (скелет заведён CEO/Claude заранее; Codex наполняет реальными эндпоинтами на Этапе 3, когда впервые появляется реальная граница backend/frontend — до этого момента файл помечен `STATUS: DRAFT`)
- Безопасность: `docs/SECURITY.md`
- Доска задач: `docs/TASKS.md`
- Журнал передачи контекста: `docs/HANDOFF.md`
- Скиллы: `.agents/skills/*/SKILL.md`
- Конфиг Aider: `.aider.conf.yml`
- Онбординг-промпты для агентов: `docs/prompts/codex-start.md` (Tech Lead & Backend), `docs/prompts/antigravity-start.md` (Frontend Lead) — вставляются в начало первой сессии агента в новом окружении, поверх мастер-промпта из §4
