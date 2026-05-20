import calendar
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_bot.enums import LoggingCategory
from discord_bot.state import TimeInterval
from discord_bot.views.base import ViewActions
from discord_bot.views.settings import (
    DAY_LABELS,
    EditTimeIntervalView,
    IntervalSelect,
    SettingsView,
    TimeIntervalsView,
    TimeModal,
    WeekdaySelect,
    format_time_interval,
)


@pytest.fixture
def actions():
    return ViewActions(
        respond_ephemeral=AsyncMock(),
        enqueue_job=AsyncMock(return_value="id"),
        refresh_dashboard=AsyncMock(),
        list_invoices_to_confirm=MagicMock(return_value=[]),
    )


def test_format_time_interval_with_end():
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY, calendar.Day.FRIDAY],
        start=datetime.time(8, 0),
        end=datetime.time(10, 30),
    )

    result = format_time_interval(interval)

    assert DAY_LABELS[calendar.Day.MONDAY] in result
    assert "08:00-10:30" in result


def test_format_time_interval_without_end():
    interval = TimeInterval(
        weekdays=[calendar.Day.TUESDAY],
        start=datetime.time(9, 15),
    )

    result = format_time_interval(interval)

    assert "09:15" in result


def test_settings_view_render_content(state_store, actions):
    view = SettingsView(
        store=state_store,
        actions=actions,
        available_printers=["P1"],
        default_printer="P1",
    )

    assert "Bot settings" in view.render_content()


@pytest.mark.asyncio
async def test_settings_save_button(state_store, actions):
    view = SettingsView(
        store=state_store,
        actions=actions,
        available_printers=["P1"],
        default_printer="P1",
    )
    printer_select = SimpleNamespace(values=["P1"])
    log_level_select = SimpleNamespace(values=[LoggingCategory.WARNING.value])
    original_get = view.get_item_by_id

    def _get_item(custom_id):
        if custom_id == "printer_name_select":
            return printer_select
        if custom_id == "log_level_select":
            return log_level_select
        return original_get(custom_id)

    view.get_item_by_id = _get_item
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    save_button = view.get_item_by_id("settings_save_button")
    await save_button.callback(SimpleNamespace())

    assert state_store.state.printer_name == "P1"
    assert state_store.state.discord_log_level == LoggingCategory.WARNING
    actions.refresh_dashboard.assert_awaited_once()
    view._close_parent_message.assert_awaited_once()


def test_weekday_select_defaults():
    select = WeekdaySelect([calendar.Day.MONDAY])

    monday = [
        opt
        for opt in select.options
        if opt.value == str(calendar.Day.MONDAY.value)
    ][0]
    assert monday.is_default is True


@pytest.mark.asyncio
async def test_weekday_select_callback_updates_interval(actions):
    view = EditTimeIntervalView(actions=actions)
    view.refresh = AsyncMock()
    select = view.get_item_by_id("weekday_select")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        type(select),
        "values",
        property(
            lambda _self: [
                str(calendar.Day.MONDAY.value),
                str(calendar.Day.TUESDAY.value),
            ]
        ),
    )

    await select.callback(SimpleNamespace())
    monkeypatch.undo()

    assert calendar.Day.MONDAY in view.interval.weekdays
    view.refresh.assert_awaited_once()


def test_interval_select_uses_placeholder_on_empty():
    select = IntervalSelect([])
    assert len(select.options) == 1
    assert "No configured" in select.options[0].label


@pytest.mark.asyncio
async def test_interval_select_callback_enables_buttons(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY], start=datetime.time(9, 0)
    )
    view = TimeIntervalsView(intervals=[interval], actions=actions)
    view.refresh = AsyncMock()
    select = view.get_item_by_id("interval_select")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(type(select), "values", property(lambda _self: ["0"]))

    await select.callback(SimpleNamespace())
    monkeypatch.undo()

    assert view.selected_interval_index == 0
    assert view.get_item_by_id("edit_selected_button").disabled is False


@pytest.mark.asyncio
async def test_time_modal_invalid_input(actions):
    view = EditTimeIntervalView(actions=actions)
    view.refresh = AsyncMock()
    modal = TimeModal(view)
    modal.start_time.value = "bad"
    modal.end_time.value = ""

    await modal.callback(SimpleNamespace())

    actions.respond_ephemeral.assert_awaited_once()


@pytest.mark.asyncio
async def test_time_modal_valid_input(actions):
    view = EditTimeIntervalView(actions=actions)
    view.refresh = AsyncMock()
    modal = TimeModal(view)
    modal.start_time.value = "09:00"
    modal.end_time.value = "10:00"

    await modal.callback(SimpleNamespace())

    assert view.interval.start == datetime.time(9, 0)
    assert view.interval.end == datetime.time(10, 0)
    view.refresh.assert_awaited_once()
