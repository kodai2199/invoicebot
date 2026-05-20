import calendar
import datetime

from discord_bot.enums import LoggingCategory
from discord_bot.state import AppState, StateStore, TimeInterval


def test_app_state_defaults():
    state = AppState()
    assert state.dashboard_message_id is None
    assert state.dashboard_refresh_interval == 60
    assert state.last_automatic_check is None
    assert state.automatic_check_times == []
    assert state.automatic_printing_intervals == []
    assert state.discord_log_level == LoggingCategory.INFO
    assert state.printer_name is None


def test_time_interval_validation():
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(hour=8, minute=0),
        end=datetime.time(hour=18, minute=0),
    )
    assert interval.weekdays == [calendar.Day.MONDAY]


def test_load_missing_file_is_noop(tmp_path):
    store = StateStore(tmp_path / "missing.json")
    assert isinstance(store.state, AppState)


def test_save_and_load_roundtrip(tmp_path):
    file_path = tmp_path / "state.json"
    store = StateStore(file_path)
    store.state.dashboard_message_id = 77
    store.state.printer_name = "Office Printer"
    store.save()

    store2 = StateStore(file_path)

    assert store2.state.dashboard_message_id == 77
    assert store2.state.printer_name == "Office Printer"


def test_load_invalid_json_resets_state_and_logs(tmp_path, monkeypatch):
    file_path = tmp_path / "bad.json"
    file_path.write_text("{broken", encoding="utf-8")

    store = StateStore(file_path)
    logger_exc = []
    monkeypatch.setattr(
        store.logger, "exception", lambda msg: logger_exc.append(msg)
    )

    store.load()

    assert isinstance(store.state, AppState)
    assert logger_exc


def test_save_creates_parent_directory(tmp_path):
    file_path = tmp_path / "nested" / "state.json"
    store = StateStore(file_path)

    store.save()

    assert file_path.exists()
