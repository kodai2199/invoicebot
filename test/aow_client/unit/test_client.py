from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from aow_client.client import AziendaOnWebClient
from aow_client.config import ClientConfig
from aow_client.types import InvoiceResponse


@pytest.fixture
def client(monkeypatch, base_config):
    monkeypatch.setattr(
        AziendaOnWebClient, "_create_new_session", lambda self: None
    )
    c = AziendaOnWebClient(base_config)
    c.login_page = Mock()
    c.dashboard_page = Mock()
    c.download_page = Mock()
    return c


def _invoice(invoice_id=1):
    return InvoiceResponse(
        id=invoice_id,
        sender_name="Sender",
        seac_code="SEAC",
        creation_date=datetime(2024, 1, 1).date(),
        reception_date=datetime(2024, 1, 2).date(),
        amount=Decimal("10.00"),
    )


def test_init_creates_download_dir(tmp_path, monkeypatch):
    """On local mode, download_dir is created"""
    download_dir = tmp_path / "local_downloads"
    config = ClientConfig(
        username="user",
        password="pass",
        base_url="https://example.com",
        download_dir=download_dir,
        remote_enabled=False,
    )

    monkeypatch.setattr(
        AziendaOnWebClient, "_create_new_session", lambda self: None
    )

    AziendaOnWebClient(config)

    assert download_dir.exists()


def test_init_remote_does_not_create_dir(tmp_path, monkeypatch):
    """On remote mode, directory is not created"""
    download_dir = tmp_path / "remote_downloads"
    config = ClientConfig(
        username="user",
        password="pass",
        base_url="https://example.com",
        download_dir=download_dir,
        remote_enabled=True,
        remote_host="127.0.0.1",
    )

    monkeypatch.setattr(
        AziendaOnWebClient, "_create_new_session", lambda self: None
    )

    AziendaOnWebClient(config)

    assert not download_dir.exists()


def test_login_success(client):
    """login_page.login() → True means client.login() → True"""
    client.login_page.login.return_value = True

    assert client.login() is True
    client.dashboard_page.accept_cookies.assert_called_once()


def test_login_failure(client):
    """login_page.login() → False means client.login() → False"""
    client.login_page.login.return_value = False

    assert client.login() is False
    client.dashboard_page.accept_cookies.assert_not_called()


def test_fetch_invoices_calls_login_first(client):
    """fetch_invoices() calls login() before download_page.fetch_invoices()"""
    call_order = []
    expected = [_invoice(1)]

    client.login = Mock(side_effect=lambda: call_order.append("login") or True)
    client.download_page.fetch_invoices = Mock(
        side_effect=lambda **_: call_order.append("fetch") or expected
    )

    result = client.fetch_invoices()

    assert result == expected
    assert call_order == ["login", "fetch"]


def test_fetch_invoices_returns_empty_on_login_failure(client):
    """Login fails → fetch_invoices() returns []"""
    client.login = Mock(return_value=False)

    result = client.fetch_invoices()

    assert result == []
    client.download_page.fetch_invoices.assert_not_called()


def test_download_invoices_single_invoice(client):
    """Passing a single Invoice is coerced to a list"""
    invoice = _invoice(10)
    client.login = Mock(return_value=True)
    client.download_page.download_invoices.return_value = [False]

    result = client.download_invoices(invoice)

    client.download_page.download_invoices.assert_called_once_with([invoice])
    assert result == {invoice: False}


def test_download_invoices_empty_list(client):
    """Empty input → returns {}"""
    client.login = Mock(return_value=True)

    result = client.download_invoices([])

    assert result == {}
    client.login.assert_not_called()


def test_download_invoices_file_exists(client, tmp_path):
    """Downloaded file present → {invoice: True}"""
    invoice = _invoice(20)
    client.login = Mock(return_value=True)
    client.download_page.download_invoices.return_value = [True]

    expected_file = (
        tmp_path
        / "downloads"
        / f"{client.DOC_PREFIX}{invoice.id}{client.DOC_SUFFIX}"
    )
    expected_file.parent.mkdir(parents=True, exist_ok=True)
    expected_file.write_bytes(b"pdf")

    result = client.download_invoices([invoice])

    assert result == {invoice: True}


def test_download_invoices_file_missing(client):
    """Downloaded file absent → {invoice: False}"""
    invoice = _invoice(21)
    client.login = Mock(return_value=True)
    client.download_page.download_invoices.return_value = [True]

    result = client.download_invoices([invoice])

    assert result == {invoice: False}


def test_session_timeout_triggers_new_session(client):
    """After timeout, _create_new_session() is called"""
    client.config.session_timeout = 1
    client.last_action = datetime.now() - timedelta(seconds=2)
    client._create_new_session = Mock()

    client._check_session_timeout()

    client._create_new_session.assert_called_once()


def test_close_quits_driver(client):
    """close() calls driver.quit()"""
    client.driver = Mock()
    quit_mock = Mock()
    client.driver.quit = quit_mock

    client.close()

    quit_mock.assert_called_once()


def test_context_manager(client):
    """With AziendaOnWebClient(...) as c: calls close() on exit"""
    client.close = Mock()

    with client as c:
        assert c is client

    client.close.assert_called_once()
