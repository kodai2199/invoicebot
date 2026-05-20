import asyncio
import os
from pathlib import Path
from typing import Any

import hikari
import miru
from dotenv import load_dotenv

from aow_client import AziendaOnWebClient, ClientConfigBuilder
from discord_bot.internationalization import _, set_user_locale
from invoice_manager import InvoiceManager, InvoiceManagerConfigBuilder

_BOOTSTRAPPED = False


def bootstrap_from_env() -> str:
    """Load env vars and set locale before importing localized modules."""
    global _BOOTSTRAPPED
    load_dotenv()
    bot_language = os.environ.get("DISCORD_BOT_LANGUAGE", "en")
    set_user_locale(bot_language)
    _BOOTSTRAPPED = True
    return bot_language


def ensure_bootstrapped() -> None:
    """Performs localization bootstrap if not already done."""
    if not _BOOTSTRAPPED:
        bootstrap_from_env()


def _create_runtime_components() -> tuple[Any, Any, Any, Any, Any]:
    """Import localized runtime dependencies only after bootstrap."""
    from discord_bot.dashboard_manager import DashboardManager
    from discord_bot.jobs import JobRunner, JobTracker
    from discord_bot.logs import BotLogger
    from discord_bot.state import StateStore

    return DashboardManager, JobRunner, JobTracker, StateStore, BotLogger


class InvoiceBot:
    """Wires and controls the Discord bot runtime.

    The class initializes networking, state persistence, dashboard
    management, logging, and background job execution, exposing a compact
    interface for startup and shutdown.
    """

    def __init__(
        self,
        invoice_manager: InvoiceManager,
        token: str | None = None,
        main_channel_id: int | None = None,
        log_channel_id: int | None = None,
        savefile_path: Path = Path("invoice_bot_save.txt"),
    ):
        ensure_bootstrapped()
        DashboardManager, JobRunner, JobTracker, StateStore, BotLogger = (
            _create_runtime_components()
        )

        if not token:
            token = os.getenv("DISCORD_BOT_TOKEN")
        if not main_channel_id:
            main_channel_id = os.getenv("DISCORD_BOT_MAIN_CHANNEL_ID")
        if not log_channel_id:
            log_channel_id = os.getenv("DISCORD_BOT_LOG_CHANNEL_ID")

        if not token or not main_channel_id:
            raise ValueError(
                _(
                    "Missing required arguments or environment variables for "
                    "the Discord Bot: DISCORD_BOT_TOKEN and "
                    "DISCORD_BOT_MAIN_CHANNEL_ID"
                )
            )

        self.invoice_manager = invoice_manager
        self.token = token
        self.main_channel_id = int(main_channel_id)
        self.log_channel_id = int(log_channel_id) if log_channel_id else None
        self.state_store = StateStore(savefile_path)

        self.bot = hikari.GatewayBot(intents=hikari.Intents.ALL, token=token)
        self.miru_client = miru.Client(
            self.bot, ignore_unknown_interactions=True
        )

        self.logger = BotLogger(
            self.bot, self.log_channel_id, self.state_store
        )
        self.job_tracker = JobTracker()
        self.job_runner = JobRunner(
            invoice_manager=self.invoice_manager,
            logger=self.logger,
            tracker=self.job_tracker,
            on_state_changed=self._on_job_state_changed,
        )

        self._background_tasks: set[asyncio.Task[Any]] = set()
        self.dashboard_manager = DashboardManager(
            bot=self.bot,
            miru_client=self.miru_client,
            channel_id=self.main_channel_id,
            store=self.state_store,
            invoice_manager=self.invoice_manager,
            job_tracker=self.job_tracker,
            logger=self.logger,
            respond_ephemeral=self.respond_ephemeral,
            enqueue_job=self.job_runner.enqueue,
        )
        self.bot.subscribe(hikari.StartedEvent, self.on_start)
        self.bot.subscribe(hikari.StoppedEvent, self.on_stop)

    def create_background_task(
        self,
        coroutine: Any,
        name: str,
    ) -> asyncio.Task[Any]:
        """Create a named task and track it for graceful shutdown.

        Args:
            coroutine: Awaitable object to run in the background.
            name: Task name used for debugging and introspection.

        Returns:
            asyncio.Task[Any]: The created task.
        """
        task = asyncio.create_task(coroutine, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def respond_ephemeral(
        self,
        ctx: miru.ViewContext,
        message: str,
        delete_after: int = 20,
        components: Any = None,
    ) -> Any:
        """Send an ephemeral reply and schedule delayed deletion.

        The deletion delay is clamped below Discord's ephemeral timeout to
        avoid leaving responses that cannot be removed by the bot.

        Args:
            ctx: Miru interaction context used to respond.
            message: Text content to send.
            delete_after: Delay in seconds before auto-deletion.
            components: Optional components to attach.

        Returns:
            Any: Response object returned by ``ctx.respond``.
        """
        response = await ctx.respond(
            message,
            flags=hikari.MessageFlag.EPHEMERAL,
            components=components,
        )
        # In any case, must delete within 15 minutes
        # or the ephemeral message becomes un-removable by the bot.
        safe_delete_after = min(delete_after, 14 * 60 + 30)
        self.create_background_task(
            self._delete_response_later(ctx, response, safe_delete_after),
            name="ephemeral-autodelete",
        )
        return response

    async def _delete_response_later(
        self,
        ctx: miru.ViewContext,
        response: Any,
        delay_seconds: int,
    ) -> None:
        await asyncio.sleep(delay_seconds)
        delete_method = getattr(response, "delete", None)
        if callable(delete_method):
            try:
                await delete_method()
                return
            except (
                hikari.NotFoundError,
                hikari.ForbiddenError,
                hikari.BadRequestError,
            ):
                return

        fallback_delete = getattr(ctx, "delete_response", None)
        if callable(fallback_delete):
            try:
                await fallback_delete()
            except (
                hikari.NotFoundError,
                hikari.ForbiddenError,
                hikari.BadRequestError,
            ):
                pass

    async def _on_job_state_changed(self) -> None:
        try:
            await self.dashboard_manager.update_dashboard()
        except Exception as exc:
            await self.logger.warning(
                _(
                    "[DASHBOARD] Failed to refresh dashboard after "
                    "job state change: {exception!r}"
                ).format(exception=exc),
            )

    async def on_start(self, event: hikari.StartedEvent) -> None:
        """Handle startup lifecycle event.

        Args:
            event: Hikari started event.

        Returns:
            None
        """
        await self.logger.start()
        await self.dashboard_manager.start()
        await self.job_runner.start()
        await self.logger.info(_("InvoiceBot initialized and started"))

    async def on_stop(self, event: hikari.StoppedEvent) -> None:
        """Handle shutdown lifecycle event.

        This method stops services in order, persists state, and waits for
        tracked background tasks to complete.

        Args:
            event: Hikari stopped event.

        Returns:
            None
        """
        await self.job_runner.stop()
        await self.dashboard_manager.stop()
        await self.logger.stop()
        self.state_store.save()

        running_tasks = [
            task for task in self._background_tasks if not task.done()
        ]
        if running_tasks:
            await self.logger.warning(
                _(
                    "Waiting for background tasks to end in order to "
                    "leave a clean state."
                )
            )
            await asyncio.gather(*running_tasks, return_exceptions=True)

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Start the underlying Hikari gateway bot.

        Args:
            *args: Positional arguments forwarded to Hikari.
            **kwargs: Keyword arguments forwarded to Hikari.

        Returns:
            None
        """
        await self.bot.start(*args, **kwargs)

    async def join(self, *args: Any, **kwargs: Any) -> None:
        """Wait for the underlying Hikari gateway bot to finish.

        Args:
            *args: Positional arguments forwarded to Hikari.
            **kwargs: Keyword arguments forwarded to Hikari.

        Returns:
            None
        """
        await self.bot.join(*args, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> None:
        """Run the underlying Hikari bot lifecycle.

        Args:
            *args: Positional arguments forwarded to Hikari.
            **kwargs: Keyword arguments forwarded to Hikari.

        Returns:
            None
        """
        await self.bot.run(*args, **kwargs)


async def main() -> None:  # noqa: D103
    bootstrap_from_env()
    aow = AziendaOnWebClient(ClientConfigBuilder.from_env())
    bm = InvoiceManager(aow, InvoiceManagerConfigBuilder.from_env())

    bot = InvoiceBot(bm)
    await bot.start()
    await bot.join()


if __name__ == "__main__":
    if os.name != "nt":
        import uvloop

        uvloop.run(main())
    else:
        asyncio.run(main())
