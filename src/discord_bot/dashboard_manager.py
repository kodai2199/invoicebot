import asyncio
import calendar
import datetime
from collections.abc import Awaitable, Callable
from typing import Any

import hikari
import miru

from discord_bot.enums import JobType
from discord_bot.internationalization import _
from discord_bot.invoice_presenter import pretty_print
from discord_bot.jobs import Job, JobTracker
from discord_bot.logs import BotLogger
from discord_bot.state import StateStore
from discord_bot.views.base import ViewActions
from discord_bot.views.dashboard import DashboardView
from invoice_manager import InvoiceManager


class DashboardText:
    """Stores localized dashboard text templates.

    The manager uses these templates to render status lines and section
    headers with runtime values.
    """

    TITLE = _("# 📊 **Invoices Dashboard**\n")
    NEW_INVOICES_LINE = _("🆕 New: `{to_download_count}`")
    TO_PRINT_LINE = _("🖨️ To Print: `{to_print_count}`")
    TO_CONFIRM_LINE = _("✅ To Confirm: `{to_confirm_count}`\n")

    HEADER_LINES = [
        TITLE,
        NEW_INVOICES_LINE,
        TO_PRINT_LINE,
        TO_CONFIRM_LINE,
    ]

    NEW_INVOICES_SECTION_HEADER = _("## New invoices to download: ")

    TO_PRINT_INVOICES_SECTION_HEADER = _("## Downloaded invoices to print: ")

    TO_CONFIRM_INVOICES_SECTION_HEADER = _("## Printed invoices to confirm: ")

    JOBS_LINE = _("🧵 Queued jobs: `{queue_size}`")
    JOBS_ERROR_LINE = _("⚠️ Last job failed. Check log channel for details.")

    LAST_CHECK_LINE = _(
        "\nLast automatic check for new invoices on {date}, at {time}."
    )
    UPDATE_LINE = _("⏱️ Dashboard last updated: {date} at {time}\n_ _")

    @staticmethod
    def format(data: dict[str, Any], job_tracker: JobTracker):
        """Build dashboard message content from runtime data.

        Args:
            data: Invoice counts, invoice lists, and check timestamps.
            job_tracker: Current queue and worker state.

        Returns:
            str: Fully rendered dashboard message.
        """
        now = datetime.datetime.now()
        lines = [] + DashboardText.HEADER_LINES

        if data["to_download_count"] > 0:
            lines.append(DashboardText.NEW_INVOICES_SECTION_HEADER)
            for i, invoice in enumerate(data["to_download"], start=1):
                lines.append(f"{i}. {pretty_print(invoice)}")
            lines.append("\n")

        if data["to_print_count"] > 0:
            lines.append(DashboardText.TO_PRINT_INVOICES_SECTION_HEADER)
            for i, invoice in enumerate(data["to_print"], start=1):
                lines.append(f"{i}. {pretty_print(invoice)}")
            lines.append("\n")

        if data["to_confirm_count"] > 0:
            lines.append(DashboardText.TO_CONFIRM_INVOICES_SECTION_HEADER)
            for i, invoice in enumerate(data["to_confirm"], start=1):
                lines.append(f"{i}. {pretty_print(invoice)}")
            lines.append("\n")

        current_job_line = job_tracker.current_status_line()
        if current_job_line is not None:
            lines.append(current_job_line)

        queue_size = job_tracker.queue_size
        if queue_size > 0:
            lines.append(DashboardText.JOBS_LINE.format(queue_size=queue_size))

        if job_tracker.last_error is not None:
            lines.append(DashboardText.JOBS_ERROR_LINE)

        last_checked = data.get("last_automatic_check")
        if last_checked is not None:
            date = last_checked.strftime("%d/%m/%Y")
            time = last_checked.strftime("%H:%M:%S")
            lines.append(
                DashboardText.LAST_CHECK_LINE.format(date=date, time=time)
            )

        date = now.strftime("%d/%m/%Y")
        time = now.strftime("%H:%M:%S")
        lines.append(DashboardText.UPDATE_LINE.format(date=date, time=time))
        return "\n".join(lines).format_map(data)


class DashboardManager:
    """Owns dashboard lifecycle and periodic maintenance tasks.

    The manager renders dashboard content, updates the active message,
    rotates old messages, and coordinates automatic background behaviors.
    """

    # After 1 hour, Discord puts a message into
    # a mode that limits the amount of changes that
    # you can attempt on it, and other things.
    # The DashboardManager works around it by
    # deleting and recreating the message if it is
    # approaching the 1-hour mark.
    DISCORD_RENEW_THRESHOLD = datetime.timedelta(minutes=50)
    DASHBOARD_AUTOUPDATE_TIME = datetime.timedelta(minutes=5)

    def __init__(
        self,
        bot: hikari.GatewayBot,
        miru_client: miru.Client,
        channel_id: int,
        store: StateStore,
        invoice_manager: InvoiceManager,
        job_tracker: JobTracker,
        logger: BotLogger,
        respond_ephemeral: Callable[..., Awaitable[Any]],
        enqueue_job: Callable[[Job], Awaitable[str]],
    ):
        self.bot = bot
        self.miru_client = miru_client
        self.main_channel_id = channel_id
        self.store = store
        self.invoice_manager = invoice_manager
        self.job_tracker = job_tracker
        self.logger = logger
        self.respond_ephemeral = respond_ephemeral
        self.enqueue_job = enqueue_job
        self._edit_lock = asyncio.Lock()
        self._renew_task: asyncio.Task[None] | None = None
        self._automatic_check_task: asyncio.Task[None] | None = None
        self._automatic_printing_task: asyncio.Task[None] | None = None
        self._automatic_update_task: asyncio.Task[None] | None = None
        self._active_view: DashboardView | None = None
        self._last_update = None

    async def start(self) -> None:
        """Start dashboard management, and renew task."""
        await self._cleanup_old_dashboards()
        await self.update_dashboard()
        if self._renew_task is None or self._renew_task.done():
            self._renew_task = asyncio.create_task(self._renew_loop())

        if (
            self._automatic_check_task is None
            or self._automatic_check_task.done()
        ):
            self._automatic_check_task = asyncio.create_task(
                self._automatic_check_loop()
            )

        if (
            self._automatic_printing_task is None
            or self._automatic_printing_task.done()
        ):
            self._automatic_printing_task = asyncio.create_task(
                self._automatic_print_loop()
            )

        if (
            self._automatic_update_task is None
            or self._automatic_update_task.done()
        ):
            self._automatic_update_task = asyncio.create_task(
                self._automatic_update_loop()
            )

    async def stop(self) -> None:
        """Stop renew task."""
        for task in [
            self._renew_task,
            self._automatic_check_task,
            self._automatic_printing_task,
            self._automatic_update_task,
        ]:
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                task = None

        if self._active_view is not None:
            self._active_view.stop()
            self._active_view = None

    async def update_dashboard(self) -> None:
        """Refresh dashboard content and components under a lock.

        Returns:
            None
        """
        async with self._edit_lock:
            self._last_update = datetime.datetime.now()
            await self._update_dashboard()

    async def _renew_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            if not self._needs_renewal:
                now = datetime.datetime.now()
                if now - self._last_update >= self.DASHBOARD_AUTOUPDATE_TIME:
                    await self.update_dashboard()
                continue

            async with self._edit_lock:
                message_id = self.store.state.dashboard_message_id
                if message_id is not None:
                    try:
                        await self.bot.rest.delete_message(
                            self.main_channel_id, message_id
                        )
                    except hikari.NotFoundError:
                        # Message was already deleted,
                        pass
                    self.store.state.dashboard_message_id = None
                    self.store.state.dashboard_message_created_at = None
                    self.store.save()
            await self.update_dashboard()

    async def _automatic_check_loop(self) -> None:
        while True:
            await asyncio.sleep(30)
            today = datetime.datetime.today()
            now = datetime.datetime.now()
            minute = datetime.timedelta(minutes=1)
            for interval in self.store.state.automatic_check_times:
                day = calendar.Day(now.weekday())
                if day not in interval.weekdays:
                    continue

                if (
                    abs(now - datetime.datetime.combine(today, interval.start))
                    <= minute
                ):
                    await self.logger.info(
                        _("Running automatic invoice check.")
                    )
                    loop = asyncio.get_running_loop()
                    future = loop.create_future()
                    await self.enqueue_job(
                        Job(JobType.FETCH_NEW_INVOICES, future=future)
                    )
                    await future  # could get result here if needed
                    await asyncio.sleep(120)

    async def _automatic_print_loop(self) -> None:
        while True:
            await asyncio.sleep(300)
            today = datetime.datetime.today()
            now = datetime.datetime.now()
            for interval in self.store.state.automatic_check_times:
                day = calendar.Day(now.weekday())
                if day not in interval.weekdays:
                    continue

                end = interval.end or datetime.time(hour=23, minute=59)
                if now >= datetime.datetime.combine(
                    today, interval.start
                ) and now <= datetime.datetime.combine(today, end):
                    # Run print job
                    await self.logger.debug(
                        _("Running automatic printing service.")
                    )
                    await asyncio.sleep(600)
                    await self.update_dashboard()

    async def _automatic_update_loop(self) -> None:
        while True:
            await asyncio.sleep(120)
            await self.update_dashboard()

    async def _cleanup_old_dashboards(self) -> None:
        """Remove old messages that appear to be dashboards.

        In theory, this should never be needed, as the DashboardManager
        should clean up after itself. However, this method ensures
        that in case something went wrong (i.e. state store got
        corrupted or deleted), and the object lost track of some
        previous message, it will be removed, avoiding clutter.
        """
        current_dashboard_id = self.store.state.dashboard_message_id

        if self._needs_renewal:
            # Current dashboard needs to be deleted anyway so we can ignore it.
            current_dashboard_id = None

        try:
            history = self.bot.rest.fetch_messages(self.main_channel_id)
            async for message in history.limit(500):
                if (
                    current_dashboard_id is not None
                    and message.id == current_dashboard_id
                ):
                    # Keep current dashboard if it exist
                    continue

                if message.content and message.content.startswith(
                    DashboardText.TITLE
                ):
                    await self.bot.rest.delete_message(
                        self.main_channel_id, message.id
                    )
        except Exception as e:
            await self.logger.warning(
                _(
                    "Could not cleanup all stale dashboard messages: "
                    "{exception!r}"
                ).format(exception=e)
            )
        await self.logger.debug("Cleanup of old dashboards complete.")

    @property
    def _needs_renewal(self) -> bool:
        created_at = self.store.state.dashboard_message_created_at
        if not created_at:
            return True

        now = datetime.datetime.now()
        return now - created_at >= self.DISCORD_RENEW_THRESHOLD

    async def _dashboard_exists(self) -> bool:
        message_id = self.store.state.dashboard_message_id
        if message_id is None:
            return False

        try:
            await self.bot.rest.fetch_message(self.main_channel_id, message_id)
            return True
        except hikari.NotFoundError:
            self.store.state.dashboard_message_id = None
            self.store.state.dashboard_message_created_at = None
            self.store.save()
            return False

    def _activate_view(self, view: DashboardView, message: int) -> None:
        """Sets the new view as active, and starts it with the miru client.

        Args:
            view (DashboardView): The DashboardView to activate
            message (int): The message id to bind the view to, required
                for bounded persistent views.
        """
        if self._active_view is view:
            return

        if self._active_view is not None:
            self._active_view.stop()

        self._active_view = view
        self.miru_client.start_view(view, bind_to=message)

    async def _create_dashboard_message(
        self, content: str, view: DashboardView
    ) -> int:
        """Creates a new dashboard messages and updates state.

        Args:
            content (str): Message content
            view (DashboardView): The latest DashboardView to use.

        Returns:
            int: the new message.id
        """
        message = await self.bot.rest.create_message(
            channel=self.main_channel_id, content=content, components=view
        )
        self._activate_view(view, message.id)
        self.store.state.dashboard_message_id = message.id
        self.store.state.dashboard_message_created_at = datetime.datetime.now()
        self.store.save()
        return message.id

    async def _update_dashboard(self) -> None:
        content, view = self._render_dashboard()

        current_message_id = self.store.state.dashboard_message_id
        if current_message_id is None:
            await self._create_dashboard_message(content, view)
            return

        try:
            await self.bot.rest.edit_message(
                self.main_channel_id,
                current_message_id,
                content=content,
                components=view,
            )
            self._activate_view(view, current_message_id)
        except hikari.NotFoundError:
            await self._create_dashboard_message(content, view)
            return

    def _render_dashboard(self) -> tuple[str, DashboardView]:
        data = {
            "to_download": self.invoice_manager.invoices_to_download(),
            "to_print": self.invoice_manager.invoices_to_print(),
            "to_confirm": self.invoice_manager.invoices_to_confirm(),
            "to_download_count": len(
                self.invoice_manager.invoices_to_download()
            ),
            "to_print_count": len(self.invoice_manager.invoices_to_print()),
            "to_confirm_count": len(
                self.invoice_manager.invoices_to_confirm()
            ),
            "last_automatic_check": self.store.state.last_automatic_check,
        }

        content = DashboardText.format(data, self.job_tracker)
        actions = ViewActions(
            enqueue_job=self.enqueue_job,
            respond_ephemeral=self.respond_ephemeral,
            refresh_dashboard=self.update_dashboard,
            list_invoices_to_confirm=self.invoice_manager.invoices_to_confirm,
        )
        view = DashboardView(
            store=self.store,
            actions=actions,
            is_busy=self.job_tracker.is_busy,
            **data,
        )
        return content, view
