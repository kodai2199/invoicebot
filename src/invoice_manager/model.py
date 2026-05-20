from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Engine,
    Integer,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
)

from aow_client.types import InvoiceLike, InvoiceResponse


class _Base(DeclarativeBase, MappedAsDataclass):
    pass


class Invoice(_Base):
    """SQLAlchemy Model of a complete invoice.

    This model includes all data of an InvoiceResponse, plus additional data
    that is used by the Invoice Manager to understand the status of each
    invoice, such as flags for download, print, and confirmation.

    job_id refers to the printing job identifier.
    """

    __tablename__ = "Invoices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    """The unique id of the Invoice as it appears on the AdE portal."""

    seac_code: Mapped[str] = mapped_column()
    """A unique code used only internally by AziendaOnWeb."""

    sender_name: Mapped[str] = mapped_column()
    """The name of the entitity that created the Invoice."""

    creation_date: Mapped[date] = mapped_column()
    """The date of creation of the Invoice."""

    reception_date: Mapped[date] = mapped_column()
    """The date when the Invoice was received by AziendaOnWeb."""

    amount: Mapped[Decimal] = mapped_column()
    """Total amount of the Invoice, in Euros."""

    downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    """True if the Invoice has been downloaded, False otherwise."""

    printed: Mapped[bool] = mapped_column(Boolean, default=False)
    """True if the Invoice has been scheduled for printing, False otherwise."""

    print_tries: Mapped[int] = mapped_column(Integer, default=0)
    """Number of times this Invoice has been scheduled for printing."""

    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    """True if the Invoice has been marked as printed, False otherwise."""

    job_id: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    """Job identifier, of the latest print job of the Invoice.
    
    The job identifier is returned by the printing backend after the Invoice
    has been scheduled for printing.
    """

    last_print: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    """Last time the Invoice has been scheduled for printing.
    
    Internally, this is used to automatically reschedule the print if, after
    a certain amount of time, the printing job does not appear complete.
    """

    @classmethod
    def from_invoice_response(cls, invoice_response: InvoiceResponse) -> Self:
        """Converts an `InvoiceResponse` into a SQLAlchemy `Invoice`.

        Used to convert the `InvoiceResponse` from `aow_client.types` to the
        SQLAlchemy model instance used by the `InvoiceManager`.

        Args:
            invoice_response: the object to convert

        Returns:
            Invoice: the SQLAlchemy model instance
        """
        return cls(**asdict(invoice_response))

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InvoiceLike):
            return NotImplemented
        return self.id == other.id

    def __str__(self):
        return (
            f"From `{self.sender_name}`, "
            f"created on  `{self.creation_date}` "
            f"and received on `{self.reception_date}`, "
            f"for a total of `{self.amount:.2f}€`"
        )

    def __repr__(self):
        return (
            f"<Invoice(id='{self.id}', "
            f"seac_code='{self.seac_code}', "
            f"sender_name='{self.sender_name}', "
            f"amount='{self.amount}', "
            f"reception_date='{self.reception_date}')>"
        )


def get_engine(connection_string: str) -> Engine:
    """Return a SQLAlchemy engine, and create required tables.

    Args:
        connection_string: The SQLAlchemy connection string.

    Returns:
        Engine: Object to interact with the database.
    """
    engine = create_engine(connection_string)
    _Base.metadata.create_all(engine)
    return engine
