from datetime import date
from decimal import Decimal

import pytest

from aow_client.pages.download import DownloadPage


def test_parse_amount_integer():
    """ "1.234" → Decimal("1234")"""
    assert DownloadPage.parse_amount("1.234") == Decimal("1234")


def test_parse_amount_decimal_comma():
    """ "1.234,56 €" → Decimal("1234.56")"""
    assert DownloadPage.parse_amount("1.234,56 €") == Decimal("1234.56")


def test_parse_amount_with_euro_sign():
    """Trailing € is stripped before parsing"""
    assert DownloadPage.parse_amount("1.234,56 €") == Decimal("1234.56")


def test_parse_amount_zero():
    """ "0,00" → Decimal("0.00")"""
    assert DownloadPage.parse_amount("0,00") == Decimal("0.00")


def test_parse_amount_invalid():
    """ "abc" raises ValueError"""
    with pytest.raises(ValueError):
        DownloadPage.parse_amount("abc")


def test_parse_amount_returns_decimal_not_float():
    """Return type is Decimal, not float"""
    assert isinstance(DownloadPage.parse_amount("1.234,56"), Decimal)


def test_parse_date_standard():
    """ "31/12/2024" → date(2024, 12, 31)"""
    assert DownloadPage.parse_date("31/12/2024") == date(2024, 12, 31)


def test_parse_date_single_digit():
    """ "01/01/2024" → date(2024, 1, 1)"""
    assert DownloadPage.parse_date("01/01/2024") == date(2024, 1, 1)


def test_parse_date_invalid_format():
    """Non-date string raises an exception"""
    with pytest.raises(ValueError):
        DownloadPage.parse_date("not_a_date")
