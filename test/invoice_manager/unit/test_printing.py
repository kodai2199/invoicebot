import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from invoice_manager.printing import (
    AVAILABLE_BACKENDS,
    CupsPrintingBackend,
    FallbackPrintingBackend,
    PrintingBackend,
    PrintJobStatus,
)


@pytest.fixture(autouse=True)
def mock_cups_module(monkeypatch):
    class FakeIPPError(Exception):
        pass

    fake_cups = SimpleNamespace(
        IPPError=FakeIPPError,
        Connection=Mock(return_value=Mock()),
    )
    monkeypatch.setitem(sys.modules, "cups", fake_cups)
    return fake_cups


# PrintJobStatus check
def test_print_job_status_names():
    assert PrintJobStatus.PENDING.name == "PENDING"
    assert PrintJobStatus.SUCCESSFUL.name == "SUCCESSFUL"
    assert PrintJobStatus.FAILED.name == "FAILED"


def test_print_job_status_invalid_lookup():
    with pytest.raises(ValueError):
        PrintJobStatus("Fake status")


# Available backends
def test_cups_available():
    assert "CUPS" in AVAILABLE_BACKENDS.keys()
    assert AVAILABLE_BACKENDS["CUPS"] == CupsPrintingBackend


def test_fallback_available():
    assert "Fallback" in AVAILABLE_BACKENDS.keys()
    assert AVAILABLE_BACKENDS["Fallback"] == FallbackPrintingBackend


# FALLBACK: Init
def test_fallback_instance():
    fallback_pb = FallbackPrintingBackend()
    assert isinstance(fallback_pb, FallbackPrintingBackend)


# FALLBACK: Compliance
def test_fallback_satisfies_backend_protocol():
    fallback_pb = FallbackPrintingBackend()
    assert isinstance(fallback_pb, PrintingBackend)
    assert hasattr(fallback_pb, "get_default_printer")
    assert hasattr(fallback_pb, "list_printers")
    assert hasattr(fallback_pb, "print_file")
    assert hasattr(fallback_pb, "get_job_status")
    assert hasattr(fallback_pb, "cancel_job")


# Fallback: Work


def test_fallback_default_printer():
    fallback_pb = FallbackPrintingBackend()
    printer = fallback_pb.get_default_printer()
    assert printer == "Fallback Printer"


def test_fallback_list_printers():
    fallback_pb = FallbackPrintingBackend()
    printer_list = fallback_pb.list_printers()
    assert isinstance(printer_list, list)
    assert len(printer_list) == 1
    assert printer_list[0] == "Fallback Printer"


def test_fallback_print_file(tmp_path):
    fallback_pb = FallbackPrintingBackend()
    job_id = fallback_pb.print_file(tmp_path)
    assert job_id == 0

    job_id = fallback_pb.print_file(tmp_path, "description")
    assert job_id == 0

    job_id = fallback_pb.print_file(tmp_path, "description", "fake printer")
    assert job_id == 0

    with pytest.raises(TypeError):
        # Missing argument
        fallback_pb.print_file()


def test_fallback_get_job_status():
    fallback_pb = FallbackPrintingBackend()
    for i in range(-10, 10):
        assert fallback_pb.get_job_status(i) == PrintJobStatus.SUCCESSFUL


def test_fallback_cancel_job():
    fallback_pb = FallbackPrintingBackend()
    for i in range(-10, 10):
        assert fallback_pb.cancel_job(i) is True


# CUPS: Init


def test_cups_fails_without_env_variables(monkeypatch):
    monkeypatch.delenv("CUPS_HOST", raising=False)
    monkeypatch.delenv("CUPS_PORT", raising=False)
    with pytest.raises(ValueError):
        CupsPrintingBackend()


def test_cups_fails_with_wrong_env_variables(monkeypatch):
    monkeypatch.setenv("INVOICEMANAGER_CUPS_HOST", "127.0.0.1")
    monkeypatch.setenv("INVOICEMANAGER_CUPS_PORT", "631")
    with pytest.raises(ValueError):
        CupsPrintingBackend()


def test_cups_init_base_env_variables(monkeypatch, mock_cups_module):
    monkeypatch.setenv("CUPS_HOST", "127.0.0.1")
    monkeypatch.setenv("CUPS_PORT", "631")
    cups_pb = CupsPrintingBackend()
    assert isinstance(cups_pb, CupsPrintingBackend)
    assert cups_pb.cups_host == "127.0.0.1"
    assert cups_pb.cups_port == 631
    mock_cups_module.Connection.assert_called_once_with("127.0.0.1", 631)


def test_cups_init_prefix_env_variables(monkeypatch, mock_cups_module):
    monkeypatch.setenv("INVOICEMANAGER_CUPS_HOST", "127.0.0.1")
    monkeypatch.setenv("INVOICEMANAGER_CUPS_PORT", "631")
    cups_pb = CupsPrintingBackend("INVOICEMANAGER_")
    assert isinstance(cups_pb, CupsPrintingBackend)
    assert cups_pb.cups_host == "127.0.0.1"
    assert cups_pb.cups_port == 631
    mock_cups_module.Connection.assert_called_once_with("127.0.0.1", 631)


# CUPS: Compliance


def test_cups_satisfies_backend_protocol(monkeypatch):
    monkeypatch.setenv("CUPS_HOST", "127.0.0.1")
    monkeypatch.setenv("CUPS_PORT", "631")
    cups_pb = CupsPrintingBackend()
    assert isinstance(cups_pb, PrintingBackend)
    assert hasattr(cups_pb, "get_default_printer")
    assert hasattr(cups_pb, "list_printers")
    assert hasattr(cups_pb, "print_file")
    assert hasattr(cups_pb, "get_job_status")
    assert hasattr(cups_pb, "cancel_job")


# CUPS: Work


def test_cups_uses_mocked_module(cups_pb):
    assert hasattr(cups_pb.cups, "Connection")


@pytest.fixture
def cups_pb(monkeypatch, mock_cups_module):
    monkeypatch.setenv("CUPS_HOST", "127.0.0.1")
    monkeypatch.setenv("CUPS_PORT", "631")
    pb = CupsPrintingBackend()
    mock_cups_module.Connection.assert_called_once_with("127.0.0.1", 631)
    return pb


def test_cups_default_printer(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.getDefault = Mock(return_value="Printer")
    assert cups_pb.get_default_printer() == "Printer"
    cups_pb.connection.getDefault.assert_called_once()


def test_cups_list_printers(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.getPrinters = Mock(
        return_value={"Printer 1": [], "Printer 2": []}
    )
    printers = cups_pb.list_printers()
    assert len(printers) == 2
    assert "Printer 1" in printers
    assert "Printer 2" in printers
    cups_pb.connection.getPrinters.assert_called_once()


def test_cups_print_file_default_printer(cups_pb, tmp_path):
    cups_pb.connection = Mock()
    cups_pb.connection.getDefault = Mock(return_value="Printer")
    cups_pb.connection.printFile = Mock(return_value=0)
    job_id = cups_pb.print_file(tmp_path)
    assert job_id == 0
    cups_pb.connection.printFile.assert_called_once()
    cups_pb.connection.getDefault.assert_called_once()


def test_cups_print_file_specified_printer(cups_pb, tmp_path):
    cups_pb.connection = Mock()
    cups_pb.connection.getDefault = Mock(return_value="Printer")
    cups_pb.list_printers = Mock(return_value=["My Printer"])
    cups_pb.connection.printFile = Mock(return_value=0)
    job_id = cups_pb.print_file(tmp_path, "", "My Printer")
    assert job_id == 0
    cups_pb.connection.printFile.assert_called_once()
    cups_pb.connection.getDefault.assert_not_called()


def test_cups_print_file_non_existing_printer(cups_pb, tmp_path):
    cups_pb.connection = Mock()
    cups_pb.connection.getDefault = Mock(return_value="Printer")
    cups_pb.list_printers = Mock(return_value=["Printer"])
    cups_pb.connection.printFile = Mock(return_value=0)
    job_id = cups_pb.print_file(tmp_path, "", "Not-existing Printer")
    assert job_id == 0
    cups_pb.connection.printFile.assert_called_once()
    cups_pb.connection.getDefault.assert_called_once()


def test_cups_get_job_status_successful(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.getJobAttributes = Mock(return_value={"job-state": 9})
    status = cups_pb.get_job_status(0)
    assert status == PrintJobStatus.SUCCESSFUL
    cups_pb.connection.getJobAttributes.assert_called_once()


def test_cups_get_job_status_pending(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.getJobAttributes = Mock(return_value={"job-state": 0})
    status = cups_pb.get_job_status(0)
    assert status == PrintJobStatus.PENDING
    cups_pb.connection.getJobAttributes.assert_called_once()


def test_cups_get_job_status_failed(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.getJobAttributes = Mock(
        side_effect=cups_pb.cups.IPPError()
    )
    status = cups_pb.get_job_status(0)
    assert status == PrintJobStatus.FAILED
    cups_pb.connection.getJobAttributes.assert_called_once()


def test_cups_cancel_job_success(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.cancelJob = Mock()
    status = cups_pb.cancel_job(0)
    assert status is True
    cups_pb.connection.cancelJob.assert_called_once()


def test_cups_cancel_job_fail(cups_pb):
    cups_pb.connection = Mock()
    cups_pb.connection.cancelJob = Mock(side_effect=cups_pb.cups.IPPError())
    status = cups_pb.cancel_job(0)
    assert status is False
    cups_pb.connection.cancelJob.assert_called_once()
