import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_bot.state import StateStore
from invoice_manager.model import Invoice


@pytest.fixture
def make_invoice():
    def _make_invoice(invoice_id: int, **overrides):
        payload = {
            "id": invoice_id,
            "seac_code": "SEAC123",
            "sender_name": f"Sender {invoice_id}",
            "creation_date": datetime.date(2024, 1, 1),
            "reception_date": datetime.date(2024, 1, 2),
            "amount": Decimal("10.00"),
            "downloaded": False,
            "printed": False,
            "print_tries": 0,
            "confirmed": False,
            "job_id": None,
            "last_print": None,
        }
        payload.update(overrides)
        return Invoice(**payload)

    return _make_invoice


@pytest.fixture
def state_store(tmp_path: Path):
    return StateStore(tmp_path / "state.json")


@pytest.fixture
def fake_response():
    return SimpleNamespace(id=123, delete=AsyncMock())


@pytest.fixture
def fake_ctx(fake_response):
    return SimpleNamespace(
        respond=AsyncMock(return_value=fake_response),
        edit_response=AsyncMock(),
        delete_response=AsyncMock(),
        respond_with_modal=AsyncMock(),
    )


@pytest.fixture
def fake_bot():
    rest = SimpleNamespace(
        create_message=AsyncMock(),
        edit_message=AsyncMock(),
        delete_message=AsyncMock(),
        fetch_message=AsyncMock(),
        fetch_messages=MagicMock(),
    )
    return SimpleNamespace(rest=rest, subscribe=MagicMock())


@pytest.fixture
def fake_miru_client():
    return SimpleNamespace(start_view=MagicMock())


@pytest.fixture
def fake_logger():
    return SimpleNamespace(
        debug=AsyncMock(),
        info=AsyncMock(),
        warning=AsyncMock(),
        error=AsyncMock(),
        critical=AsyncMock(),
        start=AsyncMock(),
        stop=AsyncMock(),
    )


@pytest.fixture
def fake_invoice_manager():
    manager = SimpleNamespace(
        invoices_to_download=MagicMock(return_value=[]),
        invoices_to_print=MagicMock(return_value=[]),
        invoices_to_confirm=MagicMock(return_value=[]),
        fetch_new_invoices=MagicMock(return_value=[]),
        download=MagicMock(return_value=[]),
        print=MagicMock(return_value=None),
        confirm=MagicMock(return_value=[]),
        schedule_for_reprint=MagicMock(return_value=[]),
        printing_backend=SimpleNamespace(get_default_printer=MagicMock()),
        available_printers=[],
    )
    return manager
