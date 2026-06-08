import calendar
import datetime

import hikari
import miru

from discord_bot.internationalization import _
from discord_bot.logs import LoggingCategory
from discord_bot.state import StateStore, TimeInterval
from discord_bot.views.base import InvoiceBotView

DAY_LABELS = {
    calendar.MONDAY: _("Mon"),
    calendar.TUESDAY: _("Tue"),
    calendar.WEDNESDAY: _("Wed"),
    calendar.THURSDAY: _("Thu"),
    calendar.FRIDAY: _("Fri"),
    calendar.SATURDAY: _("Sat"),
    calendar.SUNDAY: _("Sun"),
}


def format_time_interval(interval: TimeInterval) -> str:
    """Create a string representing a TimeInterval.

    Args:
        interval: the object to convert to a string.

    Returns:
        str: string representation of a TimeInterval
    """
    days = " ".join(DAY_LABELS[d] for d in sorted(interval.weekdays))

    if interval.end:
        return (
            f"{days} • "
            f"{interval.start.strftime('%H:%M')}"
            f"-{interval.end.strftime('%H:%M')}"
        )

    return f"{days} • {interval.start.strftime('%H:%M')}"


class SettingsView(InvoiceBotView):
    """View for configuring printer, logging, and schedules.

    This view acts as the entry point for runtime settings management and
    launches nested views for editing time-based automation intervals.
    """

    def __init__(
        self,
        store: StateStore,
        available_printers: list[str],
        default_printer: str,
        **kwargs,
    ):
        super().__init__(timeout=None, **kwargs)
        self.store = store

        default_printer_option = miru.SelectOption(
            label=_(
                "Use the server's default printer ({default_printer_name})"
            ).format(default_printer_name=default_printer),
            value="None",
            is_default=self.store.state.printer_name is None,
        )
        self.add_item(
            miru.TextSelect(
                options=[default_printer_option]
                + [
                    miru.SelectOption(
                        label=_("Printer {printer_name}").format(
                            printer_name=name
                        ),
                        value=name,
                        is_default=name == self.store.state.printer_name,
                    )
                    for name in available_printers
                ],
                custom_id="printer_name_select",
                placeholder=_("Choose default printer to use"),
                min_values=1,
                max_values=1,
                row=1,
                autodefer=True,
            )
        )
        self.add_item(
            miru.TextSelect(
                options=[
                    miru.SelectOption(
                        label=_("Log level {level}").format(level=log.name),
                        value=log.value,
                        is_default=log == self.store.state.discord_log_level,
                    )
                    for log in LoggingCategory
                ],
                custom_id="log_level_select",
                placeholder=_("Choose minimum log level to display"),
                min_values=1,
                max_values=1,
                row=2,
                autodefer=True,
            )
        )

    def render_content(self) -> str:
        """Return heading text for the settings panel.

        Returns:
            str: Localized heading content.
        """
        return _("## ⚙️ Bot settings")

    @miru.button(
        label=_("Automatic invoice check schedule"),
        style=hikari.ButtonStyle.PRIMARY,
        custom_id="automatic_invoice_check_button",
        row=3,
    )
    async def automatic_invoice_check_schedule_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ):
        """Open schedule editor for automatic invoice checks.

        Args:
            ctx: Interaction context used for nested view handling.
            button: Triggering button component.

        Returns:
            None
        """
        intervals = self.store.state.automatic_check_times
        view = TimeIntervalsView(intervals=intervals, actions=self.actions)
        await self.disable_children(ctx)
        await self.launch_view(ctx, view, 300)
        await view.wait()
        self.store.state.automatic_check_times = view.intervals
        await self.enable_children(ctx)

    @miru.button(
        label=_("Automatic printing schedule"),
        style=hikari.ButtonStyle.PRIMARY,
        custom_id="automatic_printing_button",
        row=3,
    )
    async def automatic_printing_schedule_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ):
        """Open schedule editor for automatic printing windows.

        Args:
            ctx: Interaction context used for nested view handling.
            button: Triggering button component.

        Returns:
            None
        """
        intervals = self.store.state.automatic_printing_intervals
        view = TimeIntervalsView(intervals=intervals, actions=self.actions)
        await self.disable_children(ctx)
        await self.launch_view(ctx, view, 300)
        await view.wait()
        self.store.state.automatic_printing_intervals = view.intervals
        await self.enable_children(ctx)

    @miru.button(
        label=_("Save"),
        style=hikari.ButtonStyle.SUCCESS,
        custom_id="settings_save_button",
        row=4,
    )
    async def save_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ) -> None:
        """Persist selected settings and close the settings view.

        Args:
            ctx: Interaction context used to send confirmation.
            button: Triggering button component.

        Returns:
            None
        """
        printer_name_select = self.get_item_by_id("printer_name_select")
        selected_printer_name = (
            printer_name_select.values if printer_name_select else []
        )
        if len(selected_printer_name) == 0:
            selected_printer_name = [self.store.state.printer_name]
        if selected_printer_name[0] == "None":
            selected_printer_name[0] = None
        self.store.state.printer_name = selected_printer_name[0]

        log_level_select = self.get_item_by_id("log_level_select")
        selected_log_level = (
            log_level_select.values if log_level_select else []
        )
        if len(selected_log_level) == 0:
            selected_log_level = [
                self.store.state.discord_log_level or LoggingCategory.INFO
            ]
        self.store.state.discord_log_level = LoggingCategory(
            int(selected_log_level[0])
        )
        self.store.save()
        await self.actions.respond_ephemeral(
            ctx, _("Settings saved."), delete_after=15
        )
        await self.actions.refresh_dashboard()
        await self._close_parent_message()
        self.stop()


class WeekdaySelect(miru.TextSelect):
    """Select widget used to choose weekdays for an interval.

    The component maps localized labels to ``calendar.Day`` values.
    """

    def __init__(self, selected: list[calendar.Day]) -> None:
        super().__init__(
            placeholder=_("Select weekdays"),
            min_values=1,
            max_values=7,
            custom_id="weekday_select",
            row=1,
            options=[
                miru.SelectOption(
                    label=DAY_LABELS[d],
                    value=str(d.value),
                    is_default=d in selected,
                )
                for d in calendar.Day
            ],
        )

    async def callback(self, ctx: miru.ViewContext) -> None:
        """Store selected weekdays in the parent editor view.

        Args:
            ctx: Interaction context used to refresh the parent view.

        Returns:
            None
        """
        view = self.view

        view.interval.weekdays = [calendar.Day(int(v)) for v in self.values]
        await view.refresh(ctx)


class IntervalSelect(miru.TextSelect):
    """Select widget for choosing an existing interval entry.

    It enables edit and delete actions once a concrete interval is chosen.
    """

    def __init__(self, intervals: list[TimeInterval]) -> None:
        super().__init__(
            placeholder=_("Select a time interval to edit or delete"),
            min_values=1,
            max_values=1,
            custom_id="interval_select",
            options=[
                miru.SelectOption(
                    label=format_time_interval(event)[:20],
                    value=str(i),
                )
                for i, event in enumerate(intervals)
            ]
            or [
                miru.SelectOption(
                    label=_("No configured time intervals."),
                    value="none",
                )
            ],
            row=2,
        )

    async def callback(self, ctx: miru.ViewContext) -> None:
        """Record selected interval index and enable management buttons.

        Args:
            ctx: Interaction context used to refresh the parent view.

        Returns:
            None
        """
        view: TimeIntervalsView = self.view

        if self.values[0] == "none":
            return

        view.selected_interval_index = int(self.values[0])
        edit_button = view.get_item_by_id("edit_selected_button")
        edit_button.disabled = False

        delete_button = view.get_item_by_id("delete_selected_button")
        delete_button.disabled = False
        await view.refresh(ctx)


class EditTimeIntervalView(InvoiceBotView):
    """View for creating or editing a single time interval.

    Users select weekdays and configure time bounds before confirming the
    interval back to the parent schedule view.
    """

    def __init__(self, interval: TimeInterval | None = None, **kwargs):
        super().__init__(timeout=None, **kwargs)
        self.interval = interval
        if self.interval is None:
            self.interval = TimeInterval(
                weekdays=[], start=datetime.time(hour=8)
            )
        self.add_item(WeekdaySelect(self.interval.weekdays))

    async def _refresh(self):
        weekday_select_old = self.get_item_by_id("weekday_select")
        self.remove_item(weekday_select_old)
        self.add_item(WeekdaySelect(self.interval.weekdays))

    def render_content(self):
        """Render a text preview for the interval under editing.

        Returns:
            str: Multiline summary of selected weekdays and times.
        """
        lines = [_("### Configure a new element")]
        if self.interval.weekdays:
            labels = [DAY_LABELS[d] for d in self.interval.weekdays]
            days_list = ", ".join(labels)
            lines.append(
                _("Selected weekdays: {days_list}").format(days_list=days_list)
            )
        if self.interval.start:
            lines.append(
                _("Selected starting time: {start_time}").format(
                    start_time=self.interval.start.strftime("%H:%M")
                )
            )
        if self.interval.end:
            lines.append(
                _("Selected end time: {end_time}").format(
                    end_time=self.interval.end.strftime("%H:%M")
                )
            )
        return "\n".join(lines)

    @miru.button(
        label=_("Confirm"),
        custom_id="confirm_button",
        style=hikari.ButtonStyle.SUCCESS,
        row=4,
    )
    async def confirm_button(self, ctx: miru.ViewContext, button: miru.Button):
        """Validate input and accept the edited interval.

        Args:
            ctx: Interaction context used for validation feedback.
            button: Triggering button component.

        Returns:
            None
        """
        if not self.interval.weekdays:
            await self.actions.respond_ephemeral(
                ctx, _("Select the weekdays first"), delete_after=5
            )
            return
        await self._close_parent_message()
        self.stop()

    @miru.button(
        label=_("Adjust time"),
        custom_id="adjust_time_button",
        style=hikari.ButtonStyle.PRIMARY,
        row=4,
    )
    async def adjust_time_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ):
        """Open modal controls for start and end time editing.

        Args:
            ctx: Interaction context used to present the modal.
            button: Triggering button component.

        Returns:
            None
        """
        if not self.interval.weekdays:
            await self.actions.respond_ephemeral(
                ctx, _("Select the weekdays first"), delete_after=5
            )
            return
        modal = TimeModal(self)
        await ctx.respond_with_modal(modal)
        await self.refresh(ctx)

    @miru.button(
        label=_("Cancel"),
        custom_id="cancel_button",
        style=hikari.ButtonStyle.DANGER,
        row=4,
    )
    async def cancel_button(self, ctx: miru.ViewContext, button: miru.Button):
        """Cancel editing and close the interval editor view.

        Args:
            ctx: Interaction context for the action.
            button: Triggering button component.

        Returns:
            None
        """
        await self._close_parent_message()
        self.stop()


class TimeModal(miru.Modal):
    """Modal used to capture interval start and end times.

    Values are parsed as ``HH:MM`` and propagated back to the parent
    ``EditTimeIntervalView`` instance.
    """

    start_time = miru.TextInput(
        label=_("Start Time"),
        placeholder="09:00",
        required=True,
    )

    end_time = miru.TextInput(
        label=_("End Time"),
        placeholder="None",
        required=False,
    )

    def __init__(
        self,
        view: EditTimeIntervalView,
    ) -> None:
        super().__init__(title=_("Time Interval"))
        self.view = view
        self.start_time.value = view.interval.start.strftime("%H:%M")

        if view.interval.end:
            self.end_time.value = view.interval.end.strftime("%H:%M")

    async def callback(self, ctx: miru.ViewContext) -> None:
        """Parse modal input and update the parent interval values.

        Args:
            ctx: Interaction context used for validation feedback.

        Returns:
            None
        """
        try:
            start = datetime.datetime.strptime(
                self.start_time.value,
                "%H:%M",
            ).time()

            end = None

            if self.end_time.value:
                end = datetime.datetime.strptime(
                    self.end_time.value,
                    "%H:%M",
                ).time()

        except ValueError:
            await self.view.actions.respond_ephemeral(
                ctx, _("Invalid time format. Use HH:MM"), delete_after=5
            )
            return

        self.view.interval.start = start
        self.view.interval.end = end
        await self.view.refresh(ctx)


class TimeIntervalsView(InvoiceBotView):
    """View for listing and managing multiple time intervals.

    This view lets users add, edit, remove, and confirm interval sets used
    by automatic check and printing schedules.
    """

    def __init__(self, intervals: list[TimeInterval] | None = None, **kwargs):
        super().__init__(timeout=None, **kwargs)
        self.intervals = intervals or []
        self.selected_interval_index: int | None = None
        self.selected_weekdays: list[calendar.Day] = []
        self.add_item(IntervalSelect(self.intervals))

    async def _refresh(self):
        interval_select_old = self.get_item_by_id("interval_select")
        self.remove_item(interval_select_old)
        self.add_item(IntervalSelect(self.intervals))

    def render_content(self):
        """Render the interval list with current selection highlight.

        Returns:
            str: Localized multiline list of configured intervals.
        """
        lines = [_("## Automatic check schedule\n")]

        if not self.intervals:
            lines.append(_("No configured schedule."))
        else:
            for i, interval in enumerate(self.intervals, start=1):
                prefix = (
                    "👉 " if (self.selected_interval_index == i - 1) else ""
                )
                lines.append(f"{prefix}{i}.{format_time_interval(interval)}")

        return "\n".join(lines)

    @miru.button(
        label=_("Add new"),
        custom_id="add_new_button",
        style=hikari.ButtonStyle.PRIMARY,
        row=3,
    )
    async def add_new_button(self, ctx: miru.ViewContext, button: miru.Button):
        """Launch editor flow to append a new interval.

        Args:
            ctx: Interaction context used for nested view handling.
            button: Triggering button component.

        Returns:
            None
        """
        view = EditTimeIntervalView(actions=self.actions)
        await self.disable_children(ctx)
        await self.launch_view(ctx, view, 300)
        await view.wait()
        self.intervals.append(view.interval)
        await self.restore_children_state(ctx)

    @miru.button(
        label=_("Delete selected"),
        custom_id="delete_selected_button",
        style=hikari.ButtonStyle.DANGER,
        disabled=True,
        row=3,
    )
    async def delete_selected_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ):
        """Delete the currently selected interval from the list.

        Args:
            ctx: Interaction context used for feedback and refresh.
            button: Triggering button component.

        Returns:
            None
        """
        if self.selected_interval_index is None:
            await self.actions.respond_ephemeral(
                ctx, _("Select a schedule to delete first."), delete_after=5
            )
            return
        self.intervals.pop(self.selected_interval_index)
        self.selected_interval_index = None
        edit_button = self.get_item_by_id("edit_selected_button")
        edit_button.disabled = True

        delete_button = self.get_item_by_id("delete_selected_button")
        delete_button.disabled = True
        await self.refresh(ctx)

    @miru.button(
        label=_("Edit selected"),
        custom_id="edit_selected_button",
        style=hikari.ButtonStyle.SECONDARY,
        disabled=True,
        row=3,
    )
    async def edit_selected_button(
        self, ctx: miru.ViewContext, button: miru.Button
    ):
        """Launch editor flow for the selected interval.

        Args:
            ctx: Interaction context used for nested view handling.
            button: Triggering button component.

        Returns:
            None
        """
        if self.selected_interval_index is None:
            await self.actions.respond_ephemeral(
                ctx, _("Select a schedule to edit first."), delete_after=5
            )
            return
        interval = self.intervals[self.selected_interval_index]
        view = EditTimeIntervalView(interval=interval, actions=self.actions)
        await self.disable_children(ctx)
        await self.launch_view(ctx, view, 300)
        await view.wait()
        self.intervals[self.selected_interval_index] = view.interval
        await self.restore_children_state(ctx)

    @miru.button(
        label=_("Confirm schedule"),
        custom_id="confirm_button",
        style=hikari.ButtonStyle.SUCCESS,
        row=4,
    )
    async def confirm_button(self, ctx: miru.ViewContext, button: miru.Button):
        """Close the manager and keep current interval selections.

        Args:
            ctx: Interaction context for the action.
            button: Triggering button component.

        Returns:
            None
        """
        await self._close_parent_message()
        self.stop()
