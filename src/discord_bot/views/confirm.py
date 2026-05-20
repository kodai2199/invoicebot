import hikari
import miru

from discord_bot.internationalization import _, ngettext
from discord_bot.jobs import Job, JobType
from discord_bot.views.base import InvoiceBotView
from invoice_manager import Invoice


class ConfirmInvoicesSelect(miru.TextSelect):
    """Select widget used to choose invoices to confirm.

    The component mirrors selected values across refreshes so user choices
    remain visible while interacting with the view.
    """

    def __init__(self, invoices: list[Invoice]) -> None:
        super().__init__(
            options=[
                miru.SelectOption(
                    label=invoice.sender_name[:100],
                    value=str(invoice.id),
                )
                for invoice in invoices[:25]
            ],
            custom_id="confirm_invoices_select",
            placeholder=_("Select invoices to confirm"),
            min_values=0,
            max_values=min(len(invoices), 25),
            row=1,
            autodefer=True,
        )

    async def callback(self, ctx: miru.ViewContext) -> None:
        """Persist selected options and enable the confirm button.

        Args:
            ctx: Interaction context used to edit the response.

        Returns:
            None
        """
        # self.view is the parent view
        confirm_button = self.view.get_item_by_id(
            "confirm_invoices_confirm_button"
        )

        # Enable the button once the select menu has been interacted
        # with
        confirm_button.disabled = False

        # Set options as default to keep them selected
        # after view refreshes.
        selected = set(self.values)
        for option in self.options:
            option.is_default = option.value in selected

        # Update the message
        await ctx.edit_response(components=self.view)


class ConfirmInvoicesView(InvoiceBotView):
    """View that confirms selected invoices and reschedules others.

    Users can mark a subset of invoices as confirmed. Any unselected
    invoices are automatically scheduled for reprint.
    """

    def __init__(self, invoices: list[Invoice], **kwargs) -> None:
        super().__init__(timeout=None, **kwargs)
        self.invoices = invoices
        self.add_item(ConfirmInvoicesSelect(invoices))
        confirm_button = self.get_item_by_id("confirm_invoices_confirm_button")
        confirm_button.disabled = True

    def render_content(self) -> str:
        """Return prompt text for the confirmation selection view.

        Returns:
            str: Localized message shown above the selector.
        """
        return _("Select the invoices to confirm:")

    def _get_job_confirm_message(
        self, selected: list[Invoice], unselected: list[Invoice]
    ):
        confirm_part = ngettext(
            "confirm {selected_invoices_count} invoice",
            "confirm {selected_invoices_count} invoices",
            len(selected),
        ).format(selected_invoices_count=len(selected))

        reprint_part = ngettext(
            "schedule for reprint {unselected_invoices_count} invoice",
            "schedule for reprint {unselected_invoices_count} invoices",
            len(unselected),
        ).format(unselected_invoices_count=len(unselected))

        master_template = _(
            "⏳ Job queued: {confirm_part}, and {reprint_part}."
        )
        if len(selected) > 0 and len(unselected) == 0:
            master_template = _("⏳ Job queued: {confirm_part}.")
        elif len(selected) == 0 and len(unselected) > 0:
            master_template = _("⏳ Job queued: {reprint_part}.")
        message = master_template.format(
            confirm_part=confirm_part, reprint_part=reprint_part
        )
        return message

    @miru.button(
        label=_("Confirm"),
        style=hikari.ButtonStyle.SUCCESS,
        custom_id="confirm_invoices_confirm_button",
        row=2,
    )
    async def confirm_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Queue confirmation and reprint jobs from the current selection.

        Args:
            ctx: Interaction context for responses.
            button: Triggering button component.

        Returns:
            None
        """
        select = self.get_item_by_id("confirm_invoices_select")
        selected = select.values if select and select.values else []
        selected = set([int(s) for s in selected])
        selected_invoices = [b for b in self.invoices if b.id in selected]
        unselected_invoices = [
            b for b in self.invoices if b.id not in selected
        ]
        await self.actions.enqueue_job(
            Job(
                type=JobType.CONFIRM_INVOICES,
                data={"invoices": selected_invoices},
            )
        )
        await self.actions.enqueue_job(
            Job(
                type=JobType.SCHEDULE_FOR_REPRINT_INVOICES,
                data={"invoices": unselected_invoices},
            )
        )
        message = self._get_job_confirm_message(
            selected_invoices, unselected_invoices
        )
        await self.actions.respond_ephemeral(
            ctx,
            message,
            delete_after=20,
        )
        await self.actions.refresh_dashboard()
        await self._close_parent_message()
        self.stop()

    @miru.button(
        label=_("Cancel"),
        style=hikari.ButtonStyle.DANGER,
        custom_id="confirm_invoices_cancel_button",
        row=2,
    )
    async def cancel_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Close the view without queueing any background work.

        Args:
            ctx: Interaction context for the action.
            button: Triggering button component.

        Returns:
            None
        """
        await self._close_parent_message()
        self.stop()
