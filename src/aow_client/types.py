from abc import abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class InvoiceLike(Protocol):
    """Minimal data that can represent an Invoice."""

    id: int
    """The unique id of the Invoice as it appears on the AdE portal."""

    sender_name: str
    """The name of the entitity that created the Invoice."""

    creation_date: date
    """The date of creation of the Invoice."""

    reception_date: date
    """The date when the Invoice was received by AziendaOnWeb."""

    amount: Decimal
    """Total amount of the Invoice, in Euros."""

    @abstractmethod
    def __eq__(self, other) -> bool:
        raise NotImplementedError


@dataclass(slots=True, frozen=True)
class InvoiceResponse(InvoiceLike):
    """A simple concrete Invoice dataclass.

    This dataclass represents an Invoice with all of the data available from
    the AziendaOnWeb portal.
    """

    id: int
    seac_code: str
    """A unique code used only internally by AziendaOnWeb."""

    sender_name: str
    creation_date: date
    reception_date: date
    amount: Decimal

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, InvoiceLike):
            return NotImplemented
        return self.id == other.id
