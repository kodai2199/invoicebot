import asyncio

import hikari
import miru

from discord_bot.internationalization import _, ngettext
from discord_bot.invoice_presenter import pretty_print
from discord_bot.jobs import Job, JobType
from discord_bot.state import StateStore
from discord_bot.views.base import InvoiceBotView
from discord_bot.views.confirm import ConfirmInvoicesView
from discord_bot.views.settings import SettingsView
from invoice_manager import Invoice


class DashboardView(InvoiceBotView):
    """Primary action view attached to the dashboard message.

    The view exposes controls for fetching, downloading, printing,
    confirming, and configuring invoice processing behavior.
    """

    def __init__(
        self,
        store: StateStore,
        to_download_count: int,
        to_print_count: int,
        to_confirm_count: int,
        is_busy: bool,
        **kwargs,
    ):
        super().__init__(timeout=None, **kwargs)
        self.store = store
        self.download_missing_invoices_button.disabled = (
            is_busy or to_download_count == 0
        )
        self.print_missing_invoices_button.disabled = (
            is_busy or to_print_count == 0
        )
        self.confirm_missing_invoices_button.disabled = (
            is_busy or to_confirm_count == 0
        )

    def _get_fetch_result_message(self, results: list[Invoice]):
        reply = [_("New invoices check complete.")]
        if len(results) == 0:
            reply.append(_("☑️ No new invoices found."))
        else:
            reply.append(
                ngettext(
                    "💸 {invoice_count} new invoice found:",
                    "💸 {invoice_count} new invoices found:",
                    len(results),
                ).format(invoice_count=len(results))
            )
            for invoice in results:
                reply.append(pretty_print(invoice))
        return "\n".join(reply)

    @miru.button(
        label=_("Check for new invoices"),
        custom_id="fetch_new_invoices_button",
    )
    async def fetch_new_invoices_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Queue invoice discovery and show a completion summary.

        Args:
            ctx: Interaction context used to reply.
            button: Triggering button component.

        Returns:
            None
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.actions.enqueue_job(
            Job(type=JobType.FETCH_NEW_INVOICES, future=future)
        )
        await self.actions.respond_ephemeral(
            ctx,
            _("⏳ Job queued: checking for new invoices."),
            delete_after=20,
        )
        await self.actions.refresh_dashboard()
        results: list[Invoice] = await future
        message = self._get_fetch_result_message(results)

        await self.actions.respond_ephemeral(ctx, message, delete_after=60)

    @miru.button(
        label=_("Download missing invoices"),
        custom_id="download_missing_invoices_button",
    )
    async def download_missing_invoices_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Queue download for invoices missing local files.

        Args:
            ctx: Interaction context used to reply.
            button: Triggering button component.

        Returns:
            None
        """
        await self.actions.enqueue_job(Job(type=JobType.DOWNLOAD_INVOICES))
        await self.actions.respond_ephemeral(
            ctx,
            _("⏳ Job queued: download missing invoices."),
            delete_after=20,
        )
        await self.actions.refresh_dashboard()

    @miru.button(
        label=_("Print invoices"), custom_id="print_missing_invoices_button"
    )
    async def print_missing_invoices_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Queue printing for downloaded invoices awaiting print.

        Args:
            ctx: Interaction context used to reply.
            button: Triggering button component.

        Returns:
            None
        """
        await self.actions.enqueue_job(Job(type=JobType.PRINT_INVOICES))
        await self.actions.respond_ephemeral(
            ctx,
            _("⏳ Job queued: print invoices."),
            delete_after=20,
        )
        await self.actions.refresh_dashboard()

    @miru.button(
        label=_("Confirm invoices"),
        custom_id="confirm_missing_invoices_button",
    )
    async def confirm_missing_invoices_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Open the invoice confirmation selection view.

        Args:
            ctx: Interaction context used to reply.
            button: Triggering button component.

        Returns:
            None
        """
        invoices_to_confirm = self.actions.list_invoices_to_confirm()
        if not invoices_to_confirm:
            await self.actions.respond_ephemeral(
                ctx,
                _("☑️ There are no invoices to confirm."),
                delete_after=20,
            )
            return

        view = ConfirmInvoicesView(
            invoices=invoices_to_confirm,
            actions=self.actions,
        )
        await self.launch_view(ctx, view, 600)

    @miru.button(
        label=_("Search invoices"), custom_id="search_invoices_button"
    )
    async def search_invoices_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Show placeholder text for the not-yet-implemented search.

        Args:
            ctx: Interaction context used to reply.
            button: Triggering button component.

        Returns:
            None
        """
        await self.actions.respond_ephemeral(
            ctx,
            "Search function yet to be implemented.",
            delete_after=20,
        )
        return

        # view = ConfirmInvoicesView(
        #    invoices=invoices_to_confirm,
        #    actions=self.actions,
        # )
        # await self.launch_view(ctx, view, 600)

    @miru.button(
        label=_("Settings"),
        custom_id="main_settings_button",
        style=hikari.ButtonStyle.DANGER,
        row=2,
    )
    async def main_settings_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Fetch printer data and open the settings management view.

        Args:
            ctx: Interaction context used to reply.
            button: Triggering button component.

        Returns:
            None
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self.actions.enqueue_job(
            Job(type=JobType.FETCH_PRINTERS, future=future)
        )
        await self.actions.respond_ephemeral(
            ctx,
            _("⏳ Getting available printers..."),
            delete_after=2,
        )
        results: dict[str, str | list | None] = await future
        default_printer = results.get("default")
        available_printers = results.get("available")
        view = SettingsView(
            self.store,
            actions=self.actions,
            available_printers=available_printers,
            default_printer=default_printer,
        )
        await self.launch_view(ctx, view, 600)
