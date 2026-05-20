from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from invoice_manager.config import InvoiceManagerConfig
from invoice_manager.manager import InvoiceManager
from invoice_manager.model import Invoice, get_engine


class FakeAowClient:
    DOC_PREFIX = "IT"
    DOC_SUFFIX = ".pdf"

    def __init__(self):
        self.fetch_invoices_result = []
        self.download_result = {}

    def fetch_invoices(self, new_only: bool = True):
        return self.fetch_invoices_result

    def download_invoices(self, invoices):
        return self.download_result

    def __enter__(self):
        """Enable context manager usage."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close resources when leaving context manager scope."""
        return None


class FakePrintingBackend:
    def __init__(self):
        self.jobs: dict[int, Any] = {}
        self.printed_files = []
        self.cancelled_jobs = []
        self.next_job_id = 100

    def get_default_printer(self):
        return "Fake Printer"

    def list_printers(self):
        return ["Fake Printer", "Office Printer"]

    def print_file(
        self, path: Path, description: str | None, printer: str | None = None
    ):
        self.printed_files.append((path, description, printer))
        self.next_job_id += 1
        return self.next_job_id

    def get_job_status(self, job_id: int):
        return self.jobs.get(job_id, "Failed")

    def cancel_job(self, job_id: int):
        self.cancelled_jobs.append(job_id)
        return True


@pytest.fixture
def db_engine(tmp_path):
    return get_engine(f"sqlite:///{tmp_path / 'test.sqlite'}")


@pytest.fixture
def fake_client():
    return FakeAowClient()


@pytest.fixture
def fake_printing_backend():
    return FakePrintingBackend()


@pytest.fixture
def manager_config(tmp_path, db_engine, fake_printing_backend):
    return InvoiceManagerConfig(
        db_engine=db_engine,
        printing_backend=fake_printing_backend,
        download_dir=tmp_path / "downloaded",
        confirmed_dir=tmp_path / "confirmed",
        print_timeout_minutes=30,
        print_retries_limit=2,
    )


@pytest.fixture
def manager(fake_client, manager_config):
    return InvoiceManager(fake_client, manager_config)


@pytest.fixture
def make_invoice():
    def _make_invoice(invoice_id: int, **overrides):
        payload = {
            "id": invoice_id,
            "seac_code": "SEAC123",
            "sender_name": "Sender",
            "creation_date": date(2024, 1, 1),
            "reception_date": date(2024, 1, 2),
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
