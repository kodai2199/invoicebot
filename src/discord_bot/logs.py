import asyncio
import logging
from dataclasses import dataclass

import hikari

from discord_bot.enums import LoggingCategory
from discord_bot.internationalization import _
from discord_bot.state import StateStore

LOG_STYLE = {
    logging.DEBUG: {"title": _("🐛 Debug"), "color": 0x999999},
    logging.INFO: {"title": _("ℹ️ Info"), "color": 0x0D6EFD},
    logging.WARNING: {"title": _("⚠️ Warning"), "color": 0xFFC107},
    logging.ERROR: {"title": _("❌ Error"), "color": 0xDC3545},
    logging.CRITICAL: {"title": _("💥 Critical Error"), "color": 0xFF00FF},
}


@dataclass(slots=True)
class _LogItem:
    """Container for a pending Discord log message.

    Attributes:
        message: Plain text message content.
        category: Severity level used for styling and filtering.
    """

    message: str
    category: LoggingCategory


class BotLogger:
    """Asynchronous logger with optional Discord forwarding.

    The logger always writes to Python's standard logging pipeline and,
    when configured, forwards selected messages to a Discord channel by
    means of a background worker queue.
    """

    def __init__(
        self,
        bot: hikari.GatewayBot,
        log_channel_id: int | None,
        state_store: StateStore,
    ) -> None:
        self.store = state_store
        self.bot = bot
        self.log_channel_id = log_channel_id
        self._queue: asyncio.Queue[_LogItem] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._std_logger = logging.getLogger("invoice_bot")

    async def start(self) -> None:
        """Start the Discord log worker if it is not already running.

        Returns:
            None
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._worker(), name="discord-log-worker"
            )

    async def stop(self) -> None:
        """Flush queued entries and stop the Discord log worker.

        Returns:
            None
        """
        if self._task is None:
            return
        await self._queue.join()  # flush pending logs
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def log(
        self, message: str, category: LoggingCategory = LoggingCategory.INFO
    ) -> None:
        """Log a message and optionally queue it for Discord delivery.

        Args:
            message: Message text to record.
            category: Severity level used for filtering and formatting.

        Returns:
            None
        """
        self._std_logger.log(category, message)

        # Discord log is optional
        if self.log_channel_id is None:
            return

        if category >= self.store.state.discord_log_level:
            # Publish log item only if it reaches the set
            # minimum log level
            await self._queue.put(_LogItem(message=message, category=category))

    async def debug(self, message: str) -> None:
        """Log a debug message.

        Args:
            message: Message text.

        Returns:
            None
        """
        await self.log(message, LoggingCategory.DEBUG)

    async def info(self, message: str) -> None:
        """Log an informational message.

        Args:
            message: Message text.

        Returns:
            None
        """
        await self.log(message, LoggingCategory.INFO)

    async def warning(self, message: str) -> None:
        """Log a warning message.

        Args:
            message: Message text.

        Returns:
            None
        """
        await self.log(message, LoggingCategory.WARNING)

    async def error(self, message: str) -> None:
        """Log an error message.

        Args:
            message: Message text.

        Returns:
            None
        """
        await self.log(message, LoggingCategory.ERROR)

    async def critical(self, message: str) -> None:
        """Log a critical message.

        Args:
            message: Message text.

        Returns:
            None
        """
        await self.log(message, LoggingCategory.CRITICAL)

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if self.log_channel_id is None:
                    await asyncio.sleep(1)
                    continue

                cfg = LOG_STYLE.get(item.category, {})
                title = str(cfg.get("title", "Log"))
                color = int(cfg.get("color", 0xCCCCCC))

                embed = hikari.Embed(
                    title=title,
                    description=item.message,
                    color=hikari.Color(color),
                )
                await self.bot.rest.create_message(
                    channel=self.log_channel_id,
                    embed=embed,
                )
            except Exception:
                self._std_logger.exception("Failed to send log to Discord.")
            finally:
                self._queue.task_done()
