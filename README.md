# TG Organizer

A **local-first CLI that brings order to a personal Telegram account**: it collects dialog metadata, proposes a category structure, and applies archiving, muting and folder changes — with a mandatory dry-run before anything is touched.

> The official Bot API cannot do this. It has no access to your dialog list or folders — that boundary is built into Telegram itself, not a limitation of this project. The only technical path is an MTProto client authorised as a regular app, which is what Telethon provides.

---

## Status

| Stage | Scope | State |
|---|---|---|
| **1 — CLI core** | `collect` → `report` → `apply` → `undo` | ✅ Complete and working |
| **2 — Hardening** | rate limiting, Keychain session vault, undo journal, folder-limit pre-validation, device fingerprint | 🚧 In progress |
| **3 — Web dashboard** | FastAPI + React, drag-and-drop plan editing, WebSocket progress, database instead of flat JSON | 📋 Planned |
| **4 — Semantic classification** | local LLM / embeddings (Ollama, LanceDB), opt-in cloud tagging | 📋 Planned |
| **5 — Packaging** | Tauri DMG for macOS | 📋 Planned |

Stage 1 is a complete, working tool on its own — it needs nothing but Python.
Every stage is specified before it is built: requirements in [`docs/PRD.md`](docs/PRD.md), design in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), decisions in [`docs/ADR/`](docs/ADR/).

---

## What it does today

- Collects metadata for every dialog — type, unread count, last activity date, archived / pinned / muted flags — **without reading message contents**.
- Classifies rule-based: keywords in the dialog title, plus dialog type and age (`DEAD_AFTER_DAYS`, default 180 days).
- Builds a plan, prints it as a table, and writes `data/plan.json` so you can edit it by hand before applying anything.
- Applies the plan: archive, mute, create and update folders.
- Validates the plan against Telegram folder limits **before** connecting — 10 folders / 100 chats, or 20 / 200 with `TG_HAS_PREMIUM=true`. If the plan does not fit, the CLI stops before touching the network.
- `undo` rolls back the last archive/mute from an append-only journal.

---

## Safety model

This tool operates a personal account, so safety is a first-class feature rather than a checkbox:

- **Dry-run is the default.** `apply` and `undo` only preview changes unless `--yes` is passed.
- **Write-ahead undo journal.** `data/undo_log.jsonl` records a snapshot of the state *before* the API call, then the `applied` / `failed` event.
- **Double-flag confirmation for irreversible actions.** Leaving groups and channels requires both `--yes` and `--confirm-leave`.
- **Session stored in the macOS Keychain**, not in a `*.session` file. A Telethon `StringSession` is not encrypted by itself — the security comes from where that string lives.
- **Two-layer rate limiting.** A fixed proactive pause between requests lowers the chance of hitting a limit; reactive `FloodWaitError` handling waits exactly as long as Telegram asks, never a guessed value.
- **No message content is read.** Semantic classification would be a separate, explicit opt-in at Stage 4.

---

## Deliberately out of scope in v1

- Reading message bodies — metadata only.
- Irreversibly deleting anything by default.
- Auto-leaving personal chats — archiving and muting only.

---

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Create an application at https://my.telegram.org → *API development tools*, then put `api_id` and `api_hash` into `.env`.

---

## Usage

```bash
python main.py collect      # first run asks for phone, code and 2FA password
python main.py report       # prints the table, writes data/plan.json
python main.py apply        # dry run — changes nothing
python main.py apply --yes  # actually archives / mutes / creates folders
python main.py undo         # dry run of the rollback
python main.py undo --yes   # actually rolls back
python main.py logout       # ends the session and removes it from the Keychain
```

Open `data/plan.json` before `--yes` and adjust it by hand if needed. Categories are configured in `categories.json` — the starter set is meant to be edited for your own chat titles.

---

## Project structure

| File | Role |
|---|---|
| `main.py` | CLI entry point (`collect` / `report` / `apply` / `undo` / `logout`) |
| `tg_client.py` | Telethon client initialised from a `StringSession` |
| `session_vault.py` | stores the session string in the macOS Keychain |
| `device_fingerprint.py` | Telegram Desktop / macOS client metadata for MTProto `initConnection` |
| `plan_validation.py` | validates folder limits before a plan is applied |
| `collector.py` | collects dialog metadata, never message contents |
| `classifier.py` + `categories.json` | rule-based classification |
| `actions.py` | archive / mute / folders; `leave_dialogs` behind a double flag |
| `ratelimit.py` | proactive pause + `FloodWaitError` handling |
| `report.py` | terminal table rendered with `rich` |

---

## Documentation

The project is written down before it is built:

| Document | Content |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | product requirements, KPIs, constraints |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | architecture and how it evolves per stage |
| [`docs/SECURITY.md`](docs/SECURITY.md) | what is forbidden, and why |
| [`docs/TASKS.md`](docs/TASKS.md) | live task board |
| [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) | API contract (draft until Stage 3) |
| [`docs/ADR/`](docs/ADR/) | five accepted architecture decisions with rationale |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | full context handoff between working sessions |
| [`.agents/skills/`](.agents/skills/) | five reusable agent skills: Telethon safety, session vault, rate limiter, human-in-the-loop, hybrid search |

---

## Built with AI agents, under human control

Development runs with coding agents (Codex, Antigravity, Aider) against a strict context file.
[`AGENTS.md`](AGENTS.md) is the project constitution and a mandatory entry point before any task,
with onboarding prompts in [`docs/prompts/`](docs/prompts/). Architecture decisions, security rules
and scope are owned by me — the agents write and refactor code inside those constraints.

That is how the project keeps a full PRD / ADR / security trail while still moving fast.

---

## Stack

Python 3 · Telethon (MTProto) · `keyring` (macOS Keychain) · `rich` · `python-dotenv` · pytest

## Tests

```bash
pytest -q
```

## License

MIT — see [LICENSE](LICENSE).
