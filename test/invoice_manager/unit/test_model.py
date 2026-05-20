from datetime import date
from decimal import Decimal

from invoice_manager.model import Invoice


def test_invoices_eq_same_id():
    """Test that invoice_id is the only field which matters for
    equality, since it should be a unique_id.
    """
    invoice1 = Invoice(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date=date(2023, 1, 1),
        reception_date=date(2023, 1, 2),
        amount=Decimal("100"),
    )
    invoice2 = Invoice(
        id=1,
        sender_name="Invoice Sender B",
        seac_code="SEAC1234",
        creation_date=date(2023, 1, 1),
        reception_date=date(2023, 1, 2),
        amount=Decimal("200"),
    )
    assert invoice1 == invoice2


def test_invoices_ne_different_id():
    invoice1 = Invoice(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date=date(2023, 1, 1),
        reception_date=date(2023, 1, 2),
        amount=Decimal("100"),
    )
    invoice2 = Invoice(
        id=2,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date=date(2023, 1, 1),
        reception_date=date(2023, 1, 2),
        amount=Decimal("100"),
    )
    assert invoice1 != invoice2


def test_invoice_hash_consistent_with_eq():
    """Invoices that are == have the same hash"""
    invoice1 = Invoice(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date=date(2023, 1, 1),
        reception_date=date(2023, 1, 2),
        amount=Decimal("100"),
    )
    invoice2 = Invoice(
        id=1,
        sender_name="Invoice Sender B",
        seac_code="SEAC1234",
        creation_date=date(2023, 1, 1),
        reception_date=date(2023, 1, 2),
        amount=Decimal("200"),
    )
    assert hash(invoice1) == hash(invoice2)
