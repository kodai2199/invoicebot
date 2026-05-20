import logging

from discord_bot.enums import InvoiceStrDetail, JobType, LoggingCategory


def test_logging_category_matches_logging_constants():
    assert LoggingCategory.DEBUG == logging.DEBUG
    assert LoggingCategory.INFO == logging.INFO
    assert LoggingCategory.WARNING == logging.WARNING
    assert LoggingCategory.ERROR == logging.ERROR
    assert LoggingCategory.CRITICAL == logging.CRITICAL


def test_job_type_values():
    assert JobType.FETCH_NEW_INVOICES == "fetch_new_invoices"
    assert JobType.DOWNLOAD_INVOICES == "download_invoices"
    assert JobType.PRINT_INVOICES == "print_invoices"
    assert JobType.CONFIRM_INVOICES == "confirm_invoices"
    assert (
        JobType.SCHEDULE_FOR_REPRINT_INVOICES
        == "schedule_for_reprint_invoices"
    )
    assert JobType.FETCH_PRINTERS == "fetch_printers"


def test_invoice_str_detail_members_are_ordered():
    assert InvoiceStrDetail.MINIMAL < InvoiceStrDetail.SHORT
    assert InvoiceStrDetail.SHORT < InvoiceStrDetail.NORMAL
    assert InvoiceStrDetail.NORMAL < InvoiceStrDetail.DETAILED
    assert InvoiceStrDetail.DETAILED < InvoiceStrDetail.FULL
