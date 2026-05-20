from discord_bot.enums import InvoiceStrDetail
from discord_bot.internationalization import _
from invoice_manager.model import Invoice

INVOICE_STRING_TEMPLATES = {
    InvoiceStrDetail.MINIMAL: _(
        "`{sender_name}` • `{creation_date:%d/%m/%Y}`"
    ),
    InvoiceStrDetail.SHORT: _(
        "`{sender_name}` • `{creation_date:%d/%m/%Y}` • €`{amount:.2f}`"
    ),
    InvoiceStrDetail.NORMAL: _(
        "Invoice from `{sender_name}` dated `{creation_date:%d/%m/%Y}` "
        "for €`{amount:.2f}`"
    ),
    InvoiceStrDetail.DETAILED: _(
        "Invoice `#{id}` from `{sender_name}` dated `{creation_date:%d/%m/%Y}`"
        " for €`{amount:.2f}`, received on `{reception_date:%d/%m/%Y}`"
    ),
    InvoiceStrDetail.FULL: _(
        "Invoice `#{id}`, with seac code `{seac_code}` from `{sender_name}` "
        "dated `{creation_date:%d/%m/%Y}` for €`{amount:.2f}`, received on "
        "`{reception_date:%d/%m/%Y}`"
    ),
}


def _pretty_print(
    invoice: Invoice, detail: InvoiceStrDetail = InvoiceStrDetail.NORMAL
) -> str:
    return INVOICE_STRING_TEMPLATES[detail].format(
        id=invoice.id,
        sender_name=invoice.sender_name,
        creation_date=invoice.creation_date,
        amount=invoice.amount,
        reception_date=invoice.reception_date,
        seac_code=invoice.seac_code,
    )


def pretty_print(
    invoices: Invoice | list[Invoice],
    detail: InvoiceStrDetail = InvoiceStrDetail.NORMAL,
) -> str:
    """Formats an Invoice or a list of Invoices.

    Each invoice is printed with the level of detail passed in the last
    argument. If a list of invoices is passed, then every element is printed on
    a separate line and enumerated.

    Args:
        invoices: Invoice or list of Invoice(s).
        detail: the level of detail with which each element
            should be formatted. Defaults to InvoiceStrDetail.NORMAL.

    Returns:
        str: the formatted str containing the Invoice or
            list of invoices.
    """
    if not isinstance(invoices, list):
        invoices = [invoices]
    lines = []
    if len(invoices) == 1:
        return _pretty_print(invoices[0], detail)

    for i, invoice in enumerate(invoices):
        lines.append(f"{i}. {_pretty_print(invoice, detail)}")
    return "\n".join(lines)
