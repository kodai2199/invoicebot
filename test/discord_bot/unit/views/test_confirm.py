from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_bot.enums import JobType
from discord_bot.views.base import ViewActions
from discord_bot.views.confirm import (
    ConfirmInvoicesSelect,
    ConfirmInvoicesView,
)


@pytest.fixture
def actions():
    return ViewActions(
        respond_ephemeral=AsyncMock(),
        enqueue_job=AsyncMock(return_value="id"),
        refresh_dashboard=AsyncMock(),
        list_invoices_to_confirm=MagicMock(return_value=[]),
    )


def test_confirm_select_caps_options_to_25(make_invoice):
    invoices = [make_invoice(i) for i in range(40)]

    select = ConfirmInvoicesSelect(invoices)

    assert len(select.options) == 25


def test_confirm_view_render_content(actions, make_invoice):
    view = ConfirmInvoicesView([make_invoice(1)], actions=actions)

    assert "Select the invoices to confirm" in view.render_content()


def test_get_job_confirm_message_variants(actions, make_invoice):
    view = ConfirmInvoicesView([make_invoice(1)], actions=actions)
    selected = [make_invoice(2)]
    unselected = [make_invoice(3)]

    both = view._get_job_confirm_message(selected, unselected)
    only_confirm = view._get_job_confirm_message(selected, [])
    only_reprint = view._get_job_confirm_message([], unselected)

    assert "confirm" in both
    assert "reprint" in both
    assert "confirm" in only_confirm
    assert "reprint" in only_reprint


@pytest.mark.asyncio
async def test_confirm_button_enqueues_jobs(actions, make_invoice):
    invoices = [make_invoice(1), make_invoice(2)]
    view = ConfirmInvoicesView(invoices, actions=actions)
    select = SimpleNamespace(values=["1"])
    original_get = view.get_item_by_id
    view.get_item_by_id = lambda custom_id: (
        select
        if custom_id == "confirm_invoices_select"
        else original_get(custom_id)
    )
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()
    ctx = SimpleNamespace()

    confirm_button = view.get_item_by_id("confirm_invoices_confirm_button")
    await confirm_button.callback(ctx)

    assert actions.enqueue_job.await_count == 2
    first = actions.enqueue_job.await_args_list[0].args[0]
    second = actions.enqueue_job.await_args_list[1].args[0]
    assert first.type == JobType.CONFIRM_INVOICES
    assert second.type == JobType.SCHEDULE_FOR_REPRINT_INVOICES
    view._close_parent_message.assert_awaited_once()
    view.stop.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_button_closes_and_stops(actions, make_invoice):
    view = ConfirmInvoicesView([make_invoice(1)], actions=actions)
    view._close_parent_message = AsyncMock()
    view.stop = MagicMock()

    cancel_button = view.get_item_by_id("confirm_invoices_cancel_button")
    await cancel_button.callback(SimpleNamespace())

    view._close_parent_message.assert_awaited_once()
    view.stop.assert_called_once()
