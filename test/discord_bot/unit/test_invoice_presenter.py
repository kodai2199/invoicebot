from discord_bot.enums import InvoiceStrDetail
from discord_bot.invoice_presenter import _pretty_print, pretty_print


def test_pretty_print_minimal(make_invoice):
    text = _pretty_print(make_invoice(1), InvoiceStrDetail.MINIMAL)
    assert "Sender 1" in text
    assert "01/01/2024" in text


def test_pretty_print_short(make_invoice):
    text = _pretty_print(make_invoice(2), InvoiceStrDetail.SHORT)
    assert "€`10.00`" in text


def test_pretty_print_normal(make_invoice):
    text = _pretty_print(make_invoice(3), InvoiceStrDetail.NORMAL)
    assert "Invoice from" in text


def test_pretty_print_detailed(make_invoice):
    text = _pretty_print(make_invoice(4), InvoiceStrDetail.DETAILED)
    assert "#4" in text
    assert "received on" in text


def test_pretty_print_full(make_invoice):
    text = _pretty_print(make_invoice(5), InvoiceStrDetail.FULL)
    assert "seac code" in text
    assert "SEAC123" in text


def test_pretty_print_coerces_single_invoice(make_invoice):
    text = pretty_print(make_invoice(7))
    assert text.startswith("0. ")
    assert "Sender 7" in text


def test_pretty_print_multiple_invoices(make_invoice):
    text = pretty_print([make_invoice(8), make_invoice(9)])
    lines = text.splitlines()
    assert lines[0].startswith("0. ")
    assert lines[1].startswith("1. ")
