import calendar
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_bot.enums import LoggingCategory
from discord_bot.state import TimeInterval
from discord_bot.views import settings as settings_module
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


def test_time_modal_prefills_end_time(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(9, 0),
        end=datetime.time(11, 45),
    )
    view = EditTimeIntervalView(interval=interval, actions=actions)

    modal = TimeModal(view)

    assert modal.end_time.value == "11:45"


@pytest.mark.asyncio
async def test_settings_save_button_uses_existing_values_when_selects_empty(
    state_store, actions
):
    state_store.state.printer_name = "CURRENT"
    state_store.state.discord_log_level = LoggingCategory.ERROR

    view = SettingsView(
        store=state_store,
        actions=actions,
        available_printers=["P1"],
        default_printer="P1",
    )
    original_get = view.get_item_by_id

    def _get_item(custom_id):
        if custom_id in {"printer_name_select", "log_level_select"}:
            return SimpleNamespace(values=[])
        return original_get(custom_id)

    view.get_item_by_id = _get_item
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    save_button = original_get("settings_save_button")
    await save_button.callback(SimpleNamespace())

    assert state_store.state.printer_name == "CURRENT"
    assert state_store.state.discord_log_level == LoggingCategory.ERROR


@pytest.mark.asyncio
async def test_settings_save_button_none_printer_and_default_log_level(
    state_store, actions
):
    state_store.state.printer_name = "OLD"
    state_store.state.discord_log_level = None

    view = SettingsView(
        store=state_store,
        actions=actions,
        available_printers=["P1"],
        default_printer="P1",
    )
    original_get = view.get_item_by_id

    def _get_item(custom_id):
        if custom_id == "printer_name_select":
            return SimpleNamespace(values=["None"])
        if custom_id == "log_level_select":
            return SimpleNamespace(values=[])
        return original_get(custom_id)

    view.get_item_by_id = _get_item
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    save_button = original_get("settings_save_button")
    await save_button.callback(SimpleNamespace())

    assert state_store.state.printer_name is None
    assert state_store.state.discord_log_level == LoggingCategory.INFO


@pytest.mark.asyncio
async def test_settings_automatic_invoice_check_schedule_button(
    state_store, actions
):
    seeded = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(8, 0),
    )
    updated = TimeInterval(
        weekdays=[calendar.Day.TUESDAY],
        start=datetime.time(9, 0),
    )
    state_store.state.automatic_check_times = [seeded]

    class FakeTimeIntervalsView:
        def __init__(self, intervals, actions):
            self.intervals = list(intervals) + [updated]
            self.wait = AsyncMock()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        settings_module, "TimeIntervalsView", FakeTimeIntervalsView
    )

    view = SettingsView(
        store=state_store,
        actions=actions,
        available_printers=["P1"],
        default_printer="P1",
    )
    view.disable_children = AsyncMock()
    view.launch_view = AsyncMock()
    view.enable_children = AsyncMock()

    button = view.get_item_by_id("automatic_invoice_check_button")
    await button.callback(SimpleNamespace())
    monkeypatch.undo()

    assert state_store.state.automatic_check_times == [seeded, updated]
    view.disable_children.assert_awaited_once()
    view.launch_view.assert_awaited_once()
    view.enable_children.assert_awaited_once()


@pytest.mark.asyncio
async def test_settings_automatic_printing_schedule_button(
    state_store, actions
):
    seeded = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(8, 0),
    )
    updated = TimeInterval(
        weekdays=[calendar.Day.WEDNESDAY],
        start=datetime.time(10, 0),
    )
    state_store.state.automatic_printing_intervals = [seeded]

    class FakeTimeIntervalsView:
        def __init__(self, intervals, actions):
            self.intervals = list(intervals) + [updated]
            self.wait = AsyncMock()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        settings_module, "TimeIntervalsView", FakeTimeIntervalsView
    )

    view = SettingsView(
        store=state_store,
        actions=actions,
        available_printers=["P1"],
        default_printer="P1",
    )
    view.disable_children = AsyncMock()
    view.launch_view = AsyncMock()
    view.enable_children = AsyncMock()

    button = view.get_item_by_id("automatic_printing_button")
    await button.callback(SimpleNamespace())
    monkeypatch.undo()

    assert state_store.state.automatic_printing_intervals == [seeded, updated]
    view.disable_children.assert_awaited_once()
    view.launch_view.assert_awaited_once()
    view.enable_children.assert_awaited_once()


@pytest.mark.asyncio
async def test_interval_select_callback_none_value_returns_without_refresh(
    actions,
):
    view = TimeIntervalsView(intervals=[], actions=actions)
    view.refresh = AsyncMock()
    select = view.get_item_by_id("interval_select")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        type(select), "values", property(lambda _self: ["none"])
    )

    await select.callback(SimpleNamespace())
    monkeypatch.undo()

    assert view.selected_interval_index is None
    view.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_time_interval_refresh_rebuilds_weekday_select(actions):
    view = EditTimeIntervalView(actions=actions)
    old_select = view.get_item_by_id("weekday_select")

    await view._refresh()

    new_select = view.get_item_by_id("weekday_select")
    assert new_select is not old_select


def test_edit_time_interval_render_content_full_summary(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY, calendar.Day.WEDNESDAY],
        start=datetime.time(7, 30),
        end=datetime.time(8, 45),
    )
    view = EditTimeIntervalView(interval=interval, actions=actions)

    content = view.render_content()

    assert "Selected weekdays" in content
    assert "07:30" in content
    assert "08:45" in content


@pytest.mark.asyncio
async def test_edit_time_interval_confirm_button_requires_weekdays(actions):
    view = EditTimeIntervalView(actions=actions)
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    button = view.get_item_by_id("confirm_button")
    await button.callback(SimpleNamespace())

    actions.respond_ephemeral.assert_awaited_once()
    view._close_parent_message.assert_not_awaited()
    view.stop.assert_not_called()


@pytest.mark.asyncio
async def test_edit_time_interval_confirm_button_success(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(9, 0),
    )
    view = EditTimeIntervalView(interval=interval, actions=actions)
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    button = view.get_item_by_id("confirm_button")
    await button.callback(SimpleNamespace())

    view._close_parent_message.assert_awaited_once()
    view.stop.assert_called_once()


@pytest.mark.asyncio
async def test_edit_time_interval_adjust_time_requires_weekdays(actions):
    view = EditTimeIntervalView(actions=actions)
    view.refresh = AsyncMock()
    ctx = SimpleNamespace(respond_with_modal=AsyncMock())

    button = view.get_item_by_id("adjust_time_button")
    await button.callback(ctx)

    actions.respond_ephemeral.assert_awaited_once()
    ctx.respond_with_modal.assert_not_awaited()
    view.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_time_interval_adjust_time_opens_modal(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.FRIDAY],
        start=datetime.time(9, 0),
    )
    view = EditTimeIntervalView(interval=interval, actions=actions)
    view.refresh = AsyncMock()
    ctx = SimpleNamespace(respond_with_modal=AsyncMock())

    button = view.get_item_by_id("adjust_time_button")
    await button.callback(ctx)

    ctx.respond_with_modal.assert_awaited_once()
    view.refresh.assert_awaited_once_with(ctx)


@pytest.mark.asyncio
async def test_edit_time_interval_cancel_button(actions):
    view = EditTimeIntervalView(actions=actions)
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    button = view.get_item_by_id("cancel_button")
    await button.callback(SimpleNamespace())

    view._close_parent_message.assert_awaited_once()
    view.stop.assert_called_once()


@pytest.mark.asyncio
async def test_time_intervals_refresh_rebuilds_interval_select(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(8, 0),
    )
    view = TimeIntervalsView(intervals=[interval], actions=actions)
    old_select = view.get_item_by_id("interval_select")

    await view._refresh()

    new_select = view.get_item_by_id("interval_select")
    assert new_select is not old_select


def test_time_intervals_render_content_empty(actions):
    view = TimeIntervalsView(intervals=[], actions=actions)

    content = view.render_content()

    assert "No configured schedule" in content


def test_time_intervals_render_content_with_selection_marker(actions):
    intervals = [
        TimeInterval(
            weekdays=[calendar.Day.MONDAY], start=datetime.time(8, 0)
        ),
        TimeInterval(
            weekdays=[calendar.Day.TUESDAY], start=datetime.time(9, 0)
        ),
    ]
    view = TimeIntervalsView(intervals=intervals, actions=actions)
    view.selected_interval_index = 1

    content = view.render_content()

    assert "1." in content
    assert "👉 2." in content


@pytest.mark.asyncio
async def test_time_intervals_add_new_button_appends_interval(actions):
    added = TimeInterval(
        weekdays=[calendar.Day.THURSDAY],
        start=datetime.time(10, 0),
    )

    class FakeEditView:
        def __init__(self, interval=None, actions=None):
            self.interval = added
            self.wait = AsyncMock()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings_module, "EditTimeIntervalView", FakeEditView)

    view = TimeIntervalsView(intervals=[], actions=actions)
    view.disable_children = AsyncMock()
    view.launch_view = AsyncMock()
    view.restore_children_state = AsyncMock()

    button = view.get_item_by_id("add_new_button")
    await button.callback(SimpleNamespace())
    monkeypatch.undo()

    assert view.intervals == [added]
    view.disable_children.assert_awaited_once()
    view.launch_view.assert_awaited_once()
    view.restore_children_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_time_intervals_delete_selected_button_requires_selection(
    actions,
):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(8, 0),
    )
    view = TimeIntervalsView(intervals=[interval], actions=actions)

    button = view.get_item_by_id("delete_selected_button")
    await button.callback(SimpleNamespace())

    actions.respond_ephemeral.assert_awaited_once()
    assert view.intervals == [interval]


@pytest.mark.asyncio
async def test_time_intervals_delete_selected_button_success(actions):
    intervals = [
        TimeInterval(
            weekdays=[calendar.Day.MONDAY], start=datetime.time(8, 0)
        ),
        TimeInterval(
            weekdays=[calendar.Day.TUESDAY], start=datetime.time(9, 0)
        ),
    ]
    view = TimeIntervalsView(intervals=intervals, actions=actions)
    view.refresh = AsyncMock()

    select = view.get_item_by_id("interval_select")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(type(select), "values", property(lambda _self: ["0"]))
    await select.callback(SimpleNamespace())
    monkeypatch.undo()

    button = view.get_item_by_id("delete_selected_button")
    await button.callback(SimpleNamespace())

    assert len(view.intervals) == 1
    assert view.selected_interval_index is None
    assert view.get_item_by_id("edit_selected_button").disabled is True
    assert view.get_item_by_id("delete_selected_button").disabled is True
    view.refresh.assert_awaited()


@pytest.mark.asyncio
async def test_time_intervals_edit_selected_button_requires_selection(actions):
    interval = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(8, 0),
    )
    view = TimeIntervalsView(intervals=[interval], actions=actions)

    button = view.get_item_by_id("edit_selected_button")
    await button.callback(SimpleNamespace())

    actions.respond_ephemeral.assert_awaited_once()


@pytest.mark.asyncio
async def test_time_intervals_edit_selected_button_success(actions):
    initial = TimeInterval(
        weekdays=[calendar.Day.MONDAY],
        start=datetime.time(8, 0),
    )
    updated = TimeInterval(
        weekdays=[calendar.Day.FRIDAY],
        start=datetime.time(11, 0),
    )

    class FakeEditView:
        def __init__(self, interval=None, actions=None):
            assert interval is initial
            self.interval = updated
            self.wait = AsyncMock()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings_module, "EditTimeIntervalView", FakeEditView)

    view = TimeIntervalsView(intervals=[initial], actions=actions)
    view.disable_children = AsyncMock()
    view.launch_view = AsyncMock()
    view.restore_children_state = AsyncMock()
    view.refresh = AsyncMock()

    select = view.get_item_by_id("interval_select")
    monkeypatch.setattr(type(select), "values", property(lambda _self: ["0"]))
    await select.callback(SimpleNamespace())

    button = view.get_item_by_id("edit_selected_button")
    await button.callback(SimpleNamespace())
    monkeypatch.undo()

    assert view.intervals[0] == updated
    view.disable_children.assert_awaited_once()
    view.launch_view.assert_awaited_once()
    view.restore_children_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_time_intervals_confirm_button_closes_view(actions):
    view = TimeIntervalsView(intervals=[], actions=actions)
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    button = view.get_item_by_id("confirm_button")
    await button.callback(SimpleNamespace())

    view._close_parent_message.assert_awaited_once()
    view.stop.assert_called_once()
