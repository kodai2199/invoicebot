import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from discord_bot import dashboard_manager
from discord_bot.dashboard_manager import DashboardManager, DashboardText
from discord_bot.enums import JobType
from discord_bot.jobs import JobTracker


class FakeHistory:
    def __init__(self, messages):
        self.messages = messages

    def limit(self, _n):
        async def _iter():
            for message in self.messages:
                yield message

        return _iter()


def build_manager(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    tracker = JobTracker()
    return DashboardManager(
        bot=fake_bot,
        miru_client=fake_miru_client,
        channel_id=111,
        store=state_store,
        invoice_manager=fake_invoice_manager,
        job_tracker=tracker,
        logger=fake_logger,
        respond_ephemeral=AsyncMock(),
        enqueue_job=AsyncMock(return_value="id"),
    )


def test_dashboard_text_with_header_only():
    tracker = JobTracker()
    data = {
        "to_download": [],
        "to_print": [],
        "to_confirm": [],
        "to_download_count": 0,
        "to_print_count": 0,
        "to_confirm_count": 0,
        "last_automatic_check": None,
    }

    output = DashboardText.format(data, tracker)

    assert "Invoices Dashboard" in output
    assert "Dashboard last updated" in output


def test_dashboard_text_with_job_and_error(make_invoice):
    tracker = JobTracker(
        current_job_type=JobType.DOWNLOAD_INVOICES,
        queue_size=2,
        last_error="boom",
    )
    data = {
        "to_download": [make_invoice(1)],
        "to_print": [make_invoice(2)],
        "to_confirm": [make_invoice(3)],
        "to_download_count": 1,
        "to_print_count": 1,
        "to_confirm_count": 1,
        "last_automatic_check": datetime.datetime.now(),
    }

    output = DashboardText.format(data, tracker)

    assert "Queued jobs" in output
    assert "Last job failed" in output
    assert "Running" in output


@pytest.mark.asyncio
async def test_needs_renewal_property(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )

    assert manager._needs_renewal is True

    state_store.state.dashboard_message_created_at = datetime.datetime.now()
    assert manager._needs_renewal is False


@pytest.mark.asyncio
async def test_dashboard_exists_false_clears_state(
    fake_bot,
    fake_miru_client,
    state_store,
    fake_invoice_manager,
    fake_logger,
    monkeypatch,
):

    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )
    state_store.state.dashboard_message_id = 10
    state_store.state.dashboard_message_created_at = datetime.datetime.now()

    class FakeNotFoundError(Exception):
        pass

    monkeypatch.setattr(
        dashboard_manager.hikari, "NotFoundError", FakeNotFoundError
    )
    fake_bot.rest.fetch_message.side_effect = FakeNotFoundError()

    exists = await manager._dashboard_exists()

    assert exists is False
    assert state_store.state.dashboard_message_id is None


@pytest.mark.asyncio
async def test_activate_view_starts_and_replaces_old(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )
    old = SimpleNamespace(stop=MagicMock())
    new = SimpleNamespace(stop=MagicMock())
    manager._active_view = old

    manager._activate_view(new, 99)

    old.stop.assert_called_once()
    fake_miru_client.start_view.assert_called_once_with(new, bind_to=99)


@pytest.mark.asyncio
async def test_create_dashboard_message_persists_state(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    fake_bot.rest.create_message.return_value = SimpleNamespace(id=222)
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )
    view = SimpleNamespace(stop=MagicMock())

    message_id = await manager._create_dashboard_message("hello", view)

    assert message_id == 222
    assert state_store.state.dashboard_message_id == 222


@pytest.mark.asyncio
async def test_update_dashboard_creates_when_missing(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )
    manager._render_dashboard = MagicMock(
        return_value=("content", SimpleNamespace())
    )
    manager._create_dashboard_message = AsyncMock(return_value=10)

    await manager._update_dashboard()

    manager._create_dashboard_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_dashboard_edits_when_existing(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )
    state_store.state.dashboard_message_id = 15
    view = SimpleNamespace(stop=MagicMock())
    manager._render_dashboard = MagicMock(return_value=("content", view))

    await manager._update_dashboard()

    fake_bot.rest.edit_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_old_dashboards(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )
    state_store.state.dashboard_message_id = 2
    stale = SimpleNamespace(id=1, content=DashboardText.TITLE + " old")
    current = SimpleNamespace(id=2, content=DashboardText.TITLE + " current")
    other = SimpleNamespace(id=3, content="hello")
    fake_bot.rest.fetch_messages.return_value = FakeHistory(
        [stale, current, other]
    )
    with patch.object(
        DashboardManager, "_needs_renewal", new_callable=PropertyMock
    ) as mock_needs_renewal:
        mock_needs_renewal.return_value = False
        await manager._cleanup_old_dashboards()
        mock_needs_renewal.assert_called_once()

    fake_bot.rest.delete_message.assert_awaited_once_with(111, 1)


def test_render_dashboard_computes_counts(
    fake_bot,
    fake_miru_client,
    state_store,
    fake_invoice_manager,
    fake_logger,
    make_invoice,
):
    fake_invoice_manager.invoices_to_download.return_value = [make_invoice(1)]
    fake_invoice_manager.invoices_to_print.return_value = [
        make_invoice(2),
        make_invoice(3),
    ]
    fake_invoice_manager.invoices_to_confirm.return_value = [make_invoice(4)]
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )

    content, view = manager._render_dashboard()

    assert "New:" in content
    assert view is not None


@pytest.mark.asyncio
async def test_stop_cancels_tasks(
    fake_bot, fake_miru_client, state_store, fake_invoice_manager, fake_logger
):
    manager = build_manager(
        fake_bot,
        fake_miru_client,
        state_store,
        fake_invoice_manager,
        fake_logger,
    )

    async def sleeper():
        await asyncio.Future()

    manager._renew_task = asyncio.create_task(sleeper())
    manager._automatic_check_task = asyncio.create_task(sleeper())
    manager._automatic_printing_task = asyncio.create_task(sleeper())
    manager._automatic_update_task = asyncio.create_task(sleeper())

    await manager.stop()

    assert manager._active_view is None
