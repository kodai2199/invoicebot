from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import miru
import pytest

from discord_bot.views.base import InvoiceBotView, ViewActions


class DummyView(InvoiceBotView):
    def __init__(self, actions):
        super().__init__(actions=actions, timeout=None)

    def render_content(self):
        return "dummy"

    async def _refresh(self):
        return None

    @miru.button(label="A", custom_id="a")
    async def button_a(self, ctx: miru.ViewContext, button: miru.Button):
        return None

    @miru.button(label="B", custom_id="b", disabled=True)
    async def button_b(self, ctx: miru.ViewContext, button: miru.Button):
        return None


@pytest.fixture
def actions():
    return ViewActions(
        respond_ephemeral=AsyncMock(return_value=SimpleNamespace(id=7)),
        enqueue_job=AsyncMock(return_value="1"),
        refresh_dashboard=AsyncMock(),
        list_invoices_to_confirm=MagicMock(return_value=[]),
    )


@pytest.mark.asyncio
async def test_refresh_calls_edit_response(actions):
    view = DummyView(actions)
    ctx = SimpleNamespace(edit_response=AsyncMock())

    await view.refresh(ctx)

    ctx.edit_response.assert_awaited_once_with(
        content="dummy", components=view
    )


@pytest.mark.asyncio
async def test_disable_and_restore_children(actions):
    view = DummyView(actions)
    view.refresh = AsyncMock()
    ctx = SimpleNamespace()

    await view.disable_children(ctx)
    assert all(item.disabled for item in view.children)

    await view.restore_children_state(ctx)
    assert view.children[0].disabled is False
    assert view.children[1].disabled is True


@pytest.mark.asyncio
async def test_launch_view_starts_child(actions):
    parent = DummyView(actions)
    child = DummyView(actions)
    fake_client = SimpleNamespace(start_view=MagicMock())
    parent._client = fake_client
    child._client = fake_client
    ctx = SimpleNamespace()

    await parent.launch_view(ctx, child, delete_after=12)

    assert child.parent_message.id == 7
    fake_client.start_view.assert_called_once_with(
        child, bind_to=child.parent_message
    )


@pytest.mark.asyncio
async def test_close_parent_message_noop(actions):
    view = DummyView(actions)

    await view._close_parent_message()


@pytest.mark.asyncio
async def test_close_parent_message_handles_not_found(actions, monkeypatch):
    view = DummyView(actions)

    class FakeNotFoundError(Exception):
        pass

    import discord_bot.views.base as base

    monkeypatch.setattr(base.hikari, "NotFoundError", FakeNotFoundError)
    response = SimpleNamespace(
        delete=AsyncMock(side_effect=FakeNotFoundError())
    )
    view.parent_message = response

    await view._close_parent_message()
