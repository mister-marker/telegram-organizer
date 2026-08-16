import asyncio
import json

import actions
import undo


async def _fast_flood_control(coro_factory, **_kwargs):
    return await coro_factory()


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class FakeTelegramClient:
    def __init__(self, log_path=None):
        self.log_path = log_path
        self.folder_calls = []
        self.requests = []

    async def get_entity(self, dialog_id):
        return f"entity:{dialog_id}"

    async def get_input_entity(self, dialog_id):
        return f"input:{dialog_id}"

    async def edit_folder(self, entity, folder_id):
        if self.log_path is not None:
            events = _read_jsonl(self.log_path)
            assert events[0]["event"] == "snapshot"
        self.folder_calls.append((entity, folder_id))

    async def __call__(self, request):
        if self.log_path is not None:
            events = _read_jsonl(self.log_path)
            assert events[0]["event"] == "snapshot"
        self.requests.append(request)


def test_archive_writes_snapshot_before_telegram_api(tmp_path, monkeypatch):
    log_path = tmp_path / "undo_log.jsonl"
    monkeypatch.setattr(actions, "UNDO_LOG_PATH", str(log_path))
    monkeypatch.setattr(actions, "with_flood_control", _fast_flood_control)

    dialogs = [{
        "id": 101,
        "name": "Archive me",
        "archived": False,
    }]
    client = FakeTelegramClient(log_path=log_path)

    asyncio.run(actions.archive_dialogs(client, dialogs, dry_run=False))

    events = _read_jsonl(log_path)
    assert [e["event"] for e in events] == ["snapshot", "applied"]
    assert events[0]["action"] == "archive"
    assert events[0]["before"] == {"archived": False}
    assert client.folder_calls == [("entity:101", 1)]


def test_mute_writes_snapshot_before_telegram_api(tmp_path, monkeypatch):
    log_path = tmp_path / "undo_log.jsonl"
    monkeypatch.setattr(actions, "UNDO_LOG_PATH", str(log_path))
    monkeypatch.setattr(actions, "with_flood_control", _fast_flood_control)
    monkeypatch.setattr(actions.types, "InputNotifyPeer", lambda peer: {"peer": peer})
    monkeypatch.setattr(actions.types, "InputPeerNotifySettings", lambda mute_until: {"mute_until": mute_until})
    monkeypatch.setattr(
        actions.functions.account,
        "UpdateNotifySettingsRequest",
        lambda peer, settings: {"peer": peer, "settings": settings},
    )

    dialogs = [{
        "id": 202,
        "name": "Mute me",
        "muted": False,
    }]
    client = FakeTelegramClient(log_path=log_path)

    asyncio.run(actions.mute_dialogs(client, dialogs, dry_run=False))

    events = _read_jsonl(log_path)
    assert [e["event"] for e in events] == ["snapshot", "applied"]
    assert events[0]["action"] == "mute"
    assert events[0]["before"] == {"muted": False}
    assert client.requests


def test_undo_archive_restores_previous_folder_and_marks_undone(tmp_path, monkeypatch):
    log_path = tmp_path / "undo_log.jsonl"
    monkeypatch.setattr(actions, "UNDO_LOG_PATH", str(log_path))
    monkeypatch.setattr(undo, "with_flood_control", _fast_flood_control)

    log_path.write_text(
        "\n".join([
            json.dumps({
                "undo_id": "u1",
                "event": "snapshot",
                "ts": 1,
                "action": "archive",
                "dialog_id": 303,
                "name": "Undo archive",
                "before": {"archived": False},
            }),
            json.dumps({
                "undo_id": "u1",
                "event": "applied",
                "ts": 2,
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    records = undo.find_undo_candidates(path=str(log_path))
    client = FakeTelegramClient()

    asyncio.run(undo.undo_records(client, records, dry_run=False))

    events = _read_jsonl(log_path)
    assert client.folder_calls == [("entity:303", 0)]
    assert events[-1]["event"] == "undone"
    assert events[-1]["undo_id"] == "u1"


def test_snapshot_only_record_is_still_candidate_for_safe_archive_undo(tmp_path):
    log_path = tmp_path / "undo_log.jsonl"
    log_path.write_text(
        json.dumps({
            "undo_id": "u2",
            "event": "snapshot",
            "ts": 1,
            "action": "archive",
            "dialog_id": 404,
            "name": "Maybe archived",
            "before": {"archived": False},
        }) + "\n",
        encoding="utf-8",
    )

    records = undo.find_undo_candidates(path=str(log_path))

    assert len(records) == 1
    assert records[0].status == "snapshot_only"
