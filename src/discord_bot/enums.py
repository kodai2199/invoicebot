import logging
from enum import IntEnum, StrEnum, auto


class LoggingCategory(IntEnum):
    """Enumerates supported log severity levels.

    Values mirror Python's ``logging`` module constants so the enum can be
    passed directly to standard logger APIs.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class JobType(StrEnum):
    """Identifies supported background job kinds.

    String values are used across queue messages and handler maps.
    """

    FETCH_NEW_INVOICES = "fetch_new_invoices"
    DOWNLOAD_INVOICES = "download_invoices"
    PRINT_INVOICES = "print_invoices"
    CONFIRM_INVOICES = "confirm_invoices"
    SCHEDULE_FOR_REPRINT_INVOICES = "schedule_for_reprint_invoices"
    FETCH_PRINTERS = "fetch_printers"


class InvoiceStrDetail(IntEnum):
    """Defines verbosity levels for invoice text rendering.

    Higher values represent more detailed string representations.
    """

    MINIMAL = auto()
    SHORT = auto()
    NORMAL = auto()
    DETAILED = auto()
    FULL = auto()
