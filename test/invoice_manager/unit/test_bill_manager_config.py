from pathlib import Path

import pytest

from invoice_manager.config import InvoiceManagerConfigBuilder
from invoice_manager.printing import FallbackPrintingBackend


def test_from_env_requires_database_string(monkeypatch, tmp_path):
    monkeypatch.delenv("INVOICEMANAGER_DATABASE_STRING", raising=False)

    with pytest.raises(ValueError):
        InvoiceManagerConfigBuilder.from_env(tmp_path / ".env.missing")


def test_from_env_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "INVOICEMANAGER_DATABASE_STRING", f"sqlite:///{tmp_path / 'db.sqlite'}"
    )
    monkeypatch.delenv("INVOICEMANAGER_DOWNLOADED_DIR", raising=False)
    monkeypatch.delenv("INVOICEMANAGER_CONFIRMED_DIR", raising=False)
    monkeypatch.delenv(
        "INVOICEMANAGER_PRINTING_TIMEOUT_MINUTES", raising=False
    )
    monkeypatch.delenv("INVOICEMANAGER_PRINTING_TRIES_LIMIT", raising=False)
    monkeypatch.delenv("INVOICEMANAGER_PRINTING_BACKEND", raising=False)

    config = InvoiceManagerConfigBuilder.from_env(tmp_path / ".env.unused")

    assert config.download_dir == Path("./invoices/downloaded")
    assert config.confirmed_dir == Path("./invoices/confirmed")
    assert config.print_timeout_minutes == 30
    assert config.print_retries_limit == 0
    assert isinstance(config.printing_backend, FallbackPrintingBackend)


def test_from_env_uses_custom_values(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "INVOICEMANAGER_DATABASE_STRING", f"sqlite:///{tmp_path / 'db.sqlite'}"
    )
    monkeypatch.setenv(
        "INVOICEMANAGER_DOWNLOADED_DIR", str(tmp_path / "downloads")
    )
    monkeypatch.setenv(
        "INVOICEMANAGER_CONFIRMED_DIR", str(tmp_path / "confirmed")
    )
    monkeypatch.setenv("INVOICEMANAGER_PRINTING_TIMEOUT_MINUTES", "5")
    monkeypatch.setenv("INVOICEMANAGER_PRINTING_TRIES_LIMIT", "4")

    config = InvoiceManagerConfigBuilder.from_env(tmp_path / ".env.unused")

    assert config.download_dir == tmp_path / "downloads"
    assert config.confirmed_dir == tmp_path / "confirmed"
    assert config.print_timeout_minutes == 5
    assert config.print_retries_limit == 4


def test_from_env_falls_back_to_fallback_backend_on_backend_error(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(
        "INVOICEMANAGER_DATABASE_STRING", f"sqlite:///{tmp_path / 'db.sqlite'}"
    )
    monkeypatch.setenv("INVOICEMANAGER_PRINTING_BACKEND", "CUPS")
    monkeypatch.delenv("INVOICEMANAGER_CUPS_HOST", raising=False)
    monkeypatch.delenv("INVOICEMANAGER_CUPS_PORT", raising=False)

    config = InvoiceManagerConfigBuilder.from_env(tmp_path / ".env.unused")

    assert isinstance(config.printing_backend, FallbackPrintingBackend)
