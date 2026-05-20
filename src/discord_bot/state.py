import calendar
import datetime
import logging
from pathlib import Path

from pydantic import BaseModel, ValidationError

from discord_bot.enums import LoggingCategory
from discord_bot.internationalization import _


class TimeInterval(BaseModel):
    """Represents a scheduled time window.

    The interval defines one or more weekdays and a starting time, with an
    optional ending time for bounded ranges.
    """

    weekdays: list[calendar.Day]
    start: datetime.time
    end: datetime.time | None = None


class AppState(BaseModel):
    """Serializable runtime configuration and dashboard metadata.

    This model stores user-facing settings and runtime values that must
    survive process restarts.
    """

    dashboard_message_id: int | None = None
    dashboard_message_created_at: datetime.datetime | None = None
    dashboard_refresh_interval: int = 60
    last_automatic_check: datetime.datetime | None = None
    automatic_check_times: list[TimeInterval] = []
    automatic_printing_intervals: list[TimeInterval] = []
    discord_log_level: LoggingCategory = LoggingCategory.INFO
    printer_name: str | None = None


class StateStore:
    """A simple JSON-Backed runtime state and settings store."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._state: AppState = AppState()
        self.logger = logging.getLogger("invoice_bot_state_store")
        self.load()

    @property
    def state(self) -> AppState:
        """Expose the mutable in-memory application state.

        Returns:
            AppState: Current state object.
        """
        return self._state

    def load(self) -> None:
        """Load persisted state from disk.

        If the file is missing, state remains at defaults. If validation
        fails, defaults are restored and the error is logged.

        Returns:
            None
        """
        if not self.file_path.exists():
            return

        with open(self.file_path, encoding="utf-8") as f:
            try:
                self._state = AppState.model_validate_json(f.read())
            except ValidationError:
                self.logger.exception(
                    _("Error while trying to read App State from file.")
                )
                self._state = AppState()

    def save(self) -> None:
        """Persist state atomically using a temporary file.

        Returns:
            None
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(self._state.model_dump_json(indent=4))
        tmp_path.replace(self.file_path)
