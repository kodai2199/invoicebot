import asyncio
import datetime
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from discord_bot.enums import JobType
from discord_bot.internationalization import _, ngettext
from discord_bot.invoice_presenter import pretty_print
from discord_bot.logs import BotLogger
from invoice_manager.manager import InvoiceManager
from invoice_manager.model import Invoice

JOB_DESCRIPTIONS = {
    JobType.FETCH_NEW_INVOICES: _("check for new invoices"),
    JobType.DOWNLOAD_INVOICES: _("download of missing invoices"),
    JobType.PRINT_INVOICES: _("print invoices"),
    JobType.CONFIRM_INVOICES: _("invoice confirmation"),
    JobType.SCHEDULE_FOR_REPRINT_INVOICES: _("schedule invoices for reprint"),
    JobType.FETCH_PRINTERS: _("finding available printers"),
}


@dataclass(slots=True, frozen=True)
class Job:
    """Represents a single queued background task.

    Instances are immutable so they can be passed safely through the async
    queue without accidental mutation by producers or consumers.

    Attributes:
        type: Job category used to select the execution handler.
        data: Optional payload consumed by the selected handler.
        id: Unique identifier assigned at creation time.
        future: Optional future completed with job result or exception.
    """

    type: JobType
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    future: asyncio.Future[Any] | None = field(
        default=None,
        compare=False,
        repr=False,
    )


@dataclass(slots=True)
class JobTracker:
    """Stores runtime metadata about queue and worker execution state.

    The dashboard uses this object to render current activity, queue size,
    and information about the most recent error or completed job.

    Attributes:
        current_job_type: Type of the job currently being executed.
        current_job_started_at: Start timestamp for the active job.
        last_completed_job_type: Type of the most recently completed job.
        last_completed_at: Completion timestamp of the latest job.
        last_error: String representation of the last worker exception.
        queue_size: Number of pending jobs.
    """

    current_job_type: JobType | None = None
    current_job_started_at: datetime.datetime | None = None
    last_completed_job_type: str | None = None
    last_completed_at: datetime.datetime | None = None
    last_error: str | None = None
    queue_size: int = 0

    @property
    def is_busy(self) -> bool:
        """Report whether the worker is currently executing a job.

        Returns:
            bool: ``True`` when a job is active, otherwise ``False``.
        """
        return self.current_job_type is not None

    def current_status_line(self) -> str | None:
        """Build a localized line describing the active job.

        Returns:
            str | None: Localized status text, or ``None`` when idle.
        """
        if not self.current_job_type:
            return None
        return _("⚙️ Running: {job_description}").format(
            job_description=JOB_DESCRIPTIONS[self.current_job_type]
        )


class JobRunner:
    """A basic, single-process, queue-based job runner."""

    def __init__(
        self,
        invoice_manager: InvoiceManager,
        logger: BotLogger,
        tracker: JobTracker,
        on_state_changed: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.invoice_manager = invoice_manager
        self.logger = logger
        self.tracker = tracker
        self._on_state_changed = on_state_changed
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._handlers = {
            JobType.FETCH_NEW_INVOICES: self.fetch_new_invoices_job,
            JobType.DOWNLOAD_INVOICES: self.download_invoices_job,
            JobType.PRINT_INVOICES: self.print_invoices_job,
            JobType.CONFIRM_INVOICES: self.confirm_invoices_job,
            JobType.SCHEDULE_FOR_REPRINT_INVOICES: (
                self.schedule_for_reprint_job
            ),
            JobType.FETCH_PRINTERS: self.fetch_printers_job,
        }

    @property
    def queue_size(self) -> int:
        """Return the number of jobs currently waiting in the queue.

        Returns:
            int: Pending job count.
        """
        return self._queue.qsize()

    async def start(self) -> None:
        """Start the queue worker task if it is not already running.

        Returns:
            None
        """
        if self._worker_task and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(
            self._run(), name="invoice-bot-job-runner"
        )

    async def stop(self) -> None:
        """Cancel the queue worker task and await termination.

        Returns:
            None
        """
        if self._worker_task is None:
            return

        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None

    async def enqueue(self, job: Job) -> str:
        """Push a job into the queue and notify state listeners.

        Args:
            job: Job instance to enqueue.

        Returns:
            str: Identifier of the enqueued job.
        """
        await self._queue.put(job)
        self.tracker.queue_size = self._queue.qsize()
        await self._notify_state_changed()
        return job.id

    async def _notify_state_changed(self) -> None:
        if self._on_state_changed is not None:
            await self._on_state_changed()

    async def _execute(self, job: Job):
        handler = self._handlers.get(job.type, None)
        if handler is not None:
            return await handler(job)
        else:
            await self.logger.warning(
                _(
                    "[JOB] No handler registered for worker of type {job_type}"
                ).format(job_type=job.type)
            )
        return None

    async def _run(self) -> None:
        while True:
            job = await self._queue.get()
            self.tracker.queue_size = self._queue.qsize()
            self.tracker.current_job_type = job.type
            self.tracker.current_job_started_at = datetime.datetime.now()
            await self._notify_state_changed()

            try:
                result = await self._execute(job)
                self.tracker.last_completed_job_type = job.type
                self.tracker.last_completed_at = datetime.datetime.now()
                if job.future and not job.future.done():
                    self.tracker.last_error = None
                    job.future.set_result(result)
            except Exception as exc:
                self.tracker.last_error = f"{job.type}: {exc!r}"
                await self.logger.error(
                    _(
                        "[JOB] Error while running {job_type}: {exception!r}"
                    ).format(job_type=job.type, exception=exc),
                )
                if job.future and not job.future.done():
                    job.future.set_exception(exc)
            finally:
                self.tracker.current_job_type = None
                self.tracker.current_job_started_at = None
                self.tracker.queue_size = self._queue.qsize()
                self._queue.task_done()
                await self._notify_state_changed()

    def _get_fetch_new_job_log_message(self, found: list[Invoice]) -> str:
        if len(found) <= 0:
            return _("[JOB] Check complete. No new invoices found.")

        lines = []
        lines.append(
            ngettext(
                "[JOB] Check complete. Found {found_count} new invoice:",
                "[JOB] Check complete. Found {found_count} new invoices:",
                len(found),
            ).format(found_count=len(found))
        )
        lines.append(pretty_print(found))
        return "\n".join(lines)

    async def fetch_new_invoices_job(self, job: Job):
        """Handle the job that fetches new invoices from the provider.

        If new invoices are found, a download job is enqueued automatically.

        Args:
            job: Job payload for the fetch operation.

        Returns:
            list[Invoice]: Newly discovered invoices.
        """
        found = self.invoice_manager.fetch_new_invoices()
        if len(found) > 0:
            # Automatically queue newly found invoices for downloading
            await self.enqueue(
                Job(JobType.DOWNLOAD_INVOICES, data={"invoices": found})
            )
        await self.logger.info(self._get_fetch_new_job_log_message(found))
        return found

    def _get_download_job_log_message(self, downloaded: list[Invoice]) -> str:
        if len(downloaded) <= 0:
            return _("[JOB] No invoices to download.")

        lines = []
        lines.append(
            ngettext(
                "[JOB] Downloaded {downloaded_count} invoice:",
                "[JOB] Downloaded {downloaded_count} invoices:",
                len(downloaded),
            ).format(downloaded_count=len(downloaded))
        )
        lines.append(pretty_print(downloaded))
        return "\n".join(lines)

    async def download_invoices_job(self, job: Job):
        """Handle the job that downloads invoices.

        The job may include an explicit invoice list. If omitted, the
        invoice manager decides which invoices still require download.

        Args:
            job: Job payload containing optional invoices.

        Returns:
            dict[Invoice, bool]: Download result per invoice.
        """
        to_get = None
        if job.data is not None:
            to_get = job.data.get("invoices")
        downloaded = self.invoice_manager.download(to_get)
        await self.logger.info(self._get_download_job_log_message(downloaded))
        return downloaded

    def _get_to_print_job_log_message(
        self, to_print: list[Invoice] | None
    ) -> str:
        if to_print is None:
            return _("[JOB] Scheduled all downloaded invoices for printing.")

        lines = []
        lines.append(
            ngettext(
                "[JOB] Scheduled {to_print_count} invoice for printing:",
                "[JOB] Scheduled {to_print_count} invoices for printing:",
                len(to_print),
            ).format(to_print_count=len(to_print))
        )
        lines.append(pretty_print(to_print))
        return "\n".join(lines)

    async def print_invoices_job(self, job: Job):
        """Handle the job that submits invoices to the print backend.

        Args:
            job: Job payload with optional invoices and printer name.

        Returns:
            None
        """
        to_print = None
        if job.data is not None:
            to_print = job.data.get("invoices")
            printer_name = job.data.get("printer_name")
        self.invoice_manager.print(to_print, printer_name)
        log_message = self._get_to_print_job_log_message(to_print)
        await self.logger.info(log_message)

    def _get_confirm_job_log_message(self, confirmed: list[Invoice]) -> str:
        if len(confirmed) <= 0:
            return _("[JOB] No invoices confirmed.")

        lines = []
        lines.append(
            ngettext(
                "[JOB] Confirmed {confirmed_count} invoice:",
                "[JOB] Confirmed {confirmed_count} invoices:",
                len(confirmed),
            ).format(confirmed_count=len(confirmed))
        )
        lines.append(pretty_print(confirmed))
        return "\n".join(lines)

    async def confirm_invoices_job(self, job: Job):
        """Handle the job that confirms invoices.

        Args:
            job: Job payload containing invoices to confirm.

        Returns:
            list[Invoice]: Confirmed invoices.
        """
        to_confirm = []
        if job.data is not None:
            to_confirm = job.data.get("invoices", [])
        confirmed = self.invoice_manager.confirm(to_confirm)
        await self.logger.info(self._get_confirm_job_log_message(confirmed))
        return confirmed

    def _get_reprint_job_log_message(self, rescheduled: list[Invoice]) -> str:
        if len(rescheduled) <= 0:
            return _("[JOB] No invoices rescheduled for printing.")

        lines = []
        lines.append(
            ngettext(
                "[JOB] Scheduled for reprinting {rescheduled_count} invoice:",
                "[JOB] Scheduled for reprinting {rescheduled_count} invoices:",
                len(rescheduled),
            ).format(rescheduled_count=len(rescheduled))
        )
        lines.append(pretty_print(rescheduled))
        return "\n".join(lines)

    async def schedule_for_reprint_job(self, job: Job):
        """Handle the job that schedules invoices for reprinting.

        Args:
            job: Job payload containing invoices to reschedule.

        Returns:
            list[Invoice]: Rescheduled invoices.
        """
        to_reschedule = []
        if job.data is not None:
            to_reschedule = job.data.get("invoices", [])
        rescheduled = self.invoice_manager.schedule_for_reprint(to_reschedule)
        await self.logger.info(self._get_reprint_job_log_message(rescheduled))
        return rescheduled

    async def fetch_printers_job(self, job: Job):
        """Handle the job that retrieves printer information.

        Args:
            job: Job payload, currently unused.

        Returns:
            dict[str, str | list[str] | None]: Default printer and available
            printer names.
        """
        default_printer = (
            self.invoice_manager.printing_backend.get_default_printer()
        )
        available_printers = self.invoice_manager.available_printers
        return {"default": default_printer, "available": available_printers}
