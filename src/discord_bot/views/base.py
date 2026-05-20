from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Self

import hikari
import miru

from discord_bot.jobs import Job
from invoice_manager import Invoice


@dataclass(slots=True)
class ViewActions:
    """Bundle of callbacks exposed to UI views.

    Attributes:
        respond_ephemeral: Sends ephemeral responses for interactions.
        enqueue_job: Enqueues a background job and returns its id.
        refresh_dashboard: Refreshes the main dashboard message.
        list_invoices_to_confirm: Returns invoices pending confirmation.
    """

    respond_ephemeral: Callable[..., Awaitable[Any]]
    enqueue_job: Callable[[Job], Awaitable[str]]
    refresh_dashboard: Callable[[], Awaitable[None]]
    list_invoices_to_confirm: Callable[[], list[Invoice]]


class InvoiceBotView(miru.View):
    """Base class with shared helpers for bot views.

    The class centralizes common interaction patterns such as refreshing
    component state, temporarily disabling controls, and launching nested
    ephemeral views.
    """

    def __init__(self, actions: ViewActions, **kwargs):
        super().__init__(
            timeout=kwargs.get("timeout"),
            autodefer=kwargs.get("autodefer", True),
        )
        self.actions = actions
        self.parent_message = None
        self._item_state = {}

    def render_content(self) -> str | None:
        """Return message content to render for the view.

        Returns:
            str | None: Content string, or ``None`` when unchanged.
        """
        return None

    async def _refresh(self):
        pass

    async def refresh(self, ctx: miru.ViewContext):
        """Refresh dynamic state and edit the bound interaction response.

        Args:
            ctx: Interaction context used to edit the response.

        Returns:
            None
        """
        await self._refresh()
        await ctx.edit_response(content=self.render_content(), components=self)

    async def enable_or_disable_children(
        self, ctx: miru.ViewContext, disable: bool
    ) -> None:
        """Set disabled state for all child components.

        Args:
            ctx: Interaction context used to refresh the message.
            disable: Target disabled state for child components.

        Returns:
            None
        """
        for item in self.children:
            self._item_state[item.custom_id] = item.disabled
            item.disabled = disable
        await self.refresh(ctx)

    async def disable_children(self, ctx: miru.ViewContext):
        """Disable all child components in the view.

        Args:
            ctx: Interaction context used to refresh the message.

        Returns:
            None
        """
        await self.enable_or_disable_children(ctx, True)

    async def restore_children_state(self, ctx: miru.ViewContext) -> None:
        """Restore disabled state captured before bulk modifications.

        Args:
            ctx: Interaction context used to refresh the message.

        Returns:
            None
        """
        for item in self.children:
            item.disabled = self._item_state[item.custom_id]
        await self.refresh(ctx)

    async def enable_children(self, ctx: miru.ViewContext):
        """Enable all child components in the view.

        Args:
            ctx: Interaction context used to refresh the message.

        Returns:
            None
        """
        await self.enable_or_disable_children(ctx, False)

    async def launch_view(
        self, ctx: miru.ViewContext, view: Self, delete_after: int = 60
    ):
        """Launch another view in an ephemeral response.

        Args:
            ctx: Interaction context used to send the ephemeral response.
            view: View instance to launch.
            delete_after: Auto-delete delay in seconds.

        Returns:
            None
        """
        message = await self.actions.respond_ephemeral(
            ctx,
            view.render_content(),
            components=view,
            delete_after=delete_after,
        )
        view.parent_message = message
        self.client.start_view(view, bind_to=message)

    async def _close_parent_message(self) -> None:
        if self.parent_message is None:
            return
        delete_method = getattr(self.parent_message, "delete", None)
        if callable(delete_method):
            try:
                await delete_method()
            except hikari.NotFoundError:
                pass
