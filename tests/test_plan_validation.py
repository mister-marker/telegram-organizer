import asyncio

import main
import plan_validation
from config import Settings
from plan_validation import PlanValidationError


def _dialogs(count):
    return [{"id": i, "name": f"Chat {i}"} for i in range(count)]


def _plan(folder_count, chats_per_folder):
    return {
        f"Folder {index}": _dialogs(chats_per_folder)
        for index in range(folder_count)
    }


def test_free_plan_at_limits_passes():
    plan_validation.validate_plan_limits(_plan(10, 100), has_premium=False)


def test_free_plan_with_too_many_folders_fails():
    try:
        plan_validation.validate_plan_limits(_plan(11, 1), has_premium=False)
    except PlanValidationError as e:
        assert e.limits.folder_count == 10
        assert e.issues[0].code == "TOO_MANY_FOLDERS"
        assert "папок: 11 из 10" in str(e)
    else:
        raise AssertionError("Expected PlanValidationError")


def test_free_plan_with_too_many_chats_in_folder_fails():
    try:
        plan_validation.validate_plan_limits({"Work": _dialogs(101)}, has_premium=False)
    except PlanValidationError as e:
        assert e.limits.chats_per_folder == 100
        assert e.issues[0].code == "TOO_MANY_CHATS_IN_FOLDER"
        assert "«Work»: 101 чатов из 100" in str(e)
    else:
        raise AssertionError("Expected PlanValidationError")


def test_premium_plan_uses_larger_limits():
    plan_validation.validate_plan_limits(_plan(20, 200), has_premium=True)


def test_archive_category_does_not_count_as_folder():
    plan = _plan(10, 100)
    plan["Неактивные чаты"] = _dialogs(500)

    plan_validation.validate_plan_limits(plan, has_premium=False)


def test_cmd_apply_fails_before_building_telegram_client(monkeypatch, capsys):
    settings = Settings(
        api_id=123,
        api_hash="hash",
        session_name="test_session",
        dead_after_days=180,
        has_premium=False,
    )
    build_client_called = False

    def fail_if_build_client_called(_settings):
        nonlocal build_client_called
        build_client_called = True
        raise AssertionError("build_client must not be called for invalid plan")

    monkeypatch.setattr(main, "load_settings", lambda: settings)
    monkeypatch.setattr(main, "load_json", lambda _path: _plan(11, 1))
    monkeypatch.setattr(main, "build_client", fail_if_build_client_called)

    asyncio.run(main.cmd_apply(type("Args", (), {"yes": False, "confirm_leave": False})()))

    assert not build_client_called
    assert "[plan-error]" in capsys.readouterr().out
