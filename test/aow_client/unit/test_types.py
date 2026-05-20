from aow_client.types import InvoiceResponse


def test_invoices_eq_same_id():
    """Test that id is the only field which matters for
    equality, since it should be a unique_id.
    """
    invoice1 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    invoice2 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender B",
        seac_code="SEAC1234",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=200,
    )
    assert invoice1 == invoice2


def test_invoices_ne_different_id():
    invoice1 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    invoice2 = InvoiceResponse(
        id=2,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    assert invoice1 != invoice2


def test_invoice_hash_consistent_with_eq():
    """Invoices that are == have the same hash"""
    invoice1 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    invoice2 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender B",
        seac_code="SEAC1234",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=200,
    )
    assert hash(invoice1) == hash(invoice2)


def test_invoice_in_dict_key():
    """A invoice can be used as a dict key and looked up by an equal invoice"""
    invoice1 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    invoice2 = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender B",
        seac_code="SEAC1234",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=200,
    )
    invoices_dict = {invoice1: "Test Value"}
    assert invoices_dict[invoice2] == "Test Value"
    assert invoice1 in invoices_dict
    assert invoice2 in invoices_dict
    assert len(invoices_dict) == 1


def test_invoice_str():
    """__str__ contains sender name, dates, and formatted amount"""
    invoice = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    assert invoice.sender_name in str(invoice)
    assert invoice.creation_date in str(invoice)
    assert invoice.reception_date in str(invoice)
    assert f"{invoice.amount}" in str(invoice)


def test_invoice_repr():
    """__repr__ contains all fields."""
    invoice = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    repr_str = repr(invoice)
    assert f"id={invoice.id}" in repr_str
    assert f"seac_code='{invoice.seac_code}'" in repr_str
    assert f"sender_name='{invoice.sender_name}'" in repr_str
    assert f"amount={invoice.amount}" in repr_str
    assert f"reception_date='{invoice.reception_date}'" in repr_str


def test_invoice_eq_wrong_type():
    invoice = InvoiceResponse(
        id=1,
        sender_name="Invoice Sender A",
        seac_code="SEAC123",
        creation_date="2023-01-01",
        reception_date="2023-01-02",
        amount=100,
    )
    assert (invoice == "not a invoice") is False
