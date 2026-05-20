import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_bot.enums import JobType
from discord_bot.views.base import ViewActions
from discord_bot.views.dashboard import DashboardView


@pytest.fixture
def actions(make_invoice):
    return ViewActions(
        respond_ephemeral=AsyncMock(),
        enqueue_job=AsyncMock(return_value="id"),
        refresh_dashboard=AsyncMock(),
        list_invoices_to_confirm=MagicMock(return_value=[make_invoice(1)]),
    )


def make_view(
    state_store, actions, to_download=1, to_print=1, to_confirm=1, busy=False
):
    return DashboardView(
        store=state_store,
        actions=actions,
        to_download_count=to_download,
        to_print_count=to_print,
        to_confirm_count=to_confirm,
        is_busy=busy,
    )


def test_buttons_disabled_when_busy(state_store, actions):
    view = make_view(state_store, actions, busy=True)

    assert view.download_missing_invoices_button.disabled is True
    assert view.print_missing_invoices_button.disabled is True
    assert view.confirm_missing_invoices_button.disabled is True


def test_get_fetch_result_message_empty(state_store, actions):
    view = make_view(state_store, actions)
    message = view._get_fetch_result_message([])

    assert "No new invoices" in message


@pytest.mark.asyncio
async def test_fetch_new_invoices_button_flow(
    state_store, actions, make_invoice
):
    view = make_view(state_store, actions)

    async def enqueue_job_side_effect(job):
        job.future.set_result([make_invoice(9)])
        return "x"

    actions.enqueue_job = AsyncMock(side_effect=enqueue_job_side_effect)
    ctx = SimpleNamespace()

    fetch_button = view.get_item_by_id("fetch_new_invoices_button")
    await fetch_button.callback(ctx)

    assert actions.enqueue_job.await_count == 1
    assert actions.respond_ephemeral.await_count == 2
    actions.refresh_dashboard.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_button_flow(state_store, actions):
    view = make_view(state_store, actions)

    button = view.get_item_by_id("download_missing_invoices_button")
    await button.callback(SimpleNamespace())

    job = actions.enqueue_job.await_args.args[0]
    assert job.type == JobType.DOWNLOAD_INVOICES


@pytest.mark.asyncio
async def test_print_button_flow(state_store, actions):
    view = make_view(state_store, actions)

    button = view.get_item_by_id("print_missing_invoices_button")
    await button.callback(SimpleNamespace())

    job = actions.enqueue_job.await_args.args[0]
    assert job.type == JobType.PRINT_INVOICES


@pytest.mark.asyncio
async def test_confirm_button_no_invoices(state_store, actions):
    actions.list_invoices_to_confirm = MagicMock(return_value=[])
    view = make_view(state_store, actions)

    button = view.get_item_by_id("confirm_missing_invoices_button")
    await button.callback(SimpleNamespace())

    actions.respond_ephemeral.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_button(state_store, actions):
    view = make_view(state_store, actions)

    button = view.get_item_by_id("search_invoices_button")
    await button.callback(SimpleNamespace())

    actions.respond_ephemeral.assert_awaited_once()


@pytest.mark.asyncio
async def test_settings_button_fetches_printers(
    state_store, actions, monkeypatch
):
    view = make_view(state_store, actions)
    future = asyncio.get_running_loop().create_future()
    future.set_result({"default": "P1", "available": ["P1"]})
    actions.enqueue_job = AsyncMock(return_value="id")
    view.launch_view = AsyncMock()

    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        lambda: SimpleNamespace(create_future=lambda: future),
    )

    button = view.get_item_by_id("main_settings_button")
    await button.callback(SimpleNamespace())

    actions.enqueue_job.assert_awaited_once()
    view.launch_view.assert_awaited_once()
