from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from aow_client.pages import download as download_module
from aow_client.pages.download import DownloadPage
from aow_client.types import InvoiceResponse


@pytest.fixture
def page(mock_driver):
    return DownloadPage(mock_driver, "https://example.com/download")


def test_parse_amount_integer():
    """ "1.234" → Decimal("1234")"""
    assert DownloadPage.parse_amount("1.234") == Decimal("1234")


def test_parse_amount_decimal_comma():
    """ "1.234,56 €" → Decimal("1234.56")"""
    assert DownloadPage.parse_amount("1.234,56 €") == Decimal("1234.56")


def test_parse_amount_with_euro_sign():
    """Trailing € is stripped before parsing"""
    assert DownloadPage.parse_amount("1.234,56 €") == Decimal("1234.56")


def test_parse_amount_zero():
    """ "0,00" → Decimal("0.00")"""
    assert DownloadPage.parse_amount("0,00") == Decimal("0.00")


def test_parse_amount_invalid():
    """ "abc" raises ValueError"""
    with pytest.raises(ValueError):
        DownloadPage.parse_amount("abc")


def test_parse_amount_returns_decimal_not_float():
    """Return type is Decimal, not float"""
    assert isinstance(DownloadPage.parse_amount("1.234,56"), Decimal)


def test_parse_date_standard():
    """ "31/12/2024" → date(2024, 12, 31)"""
    assert DownloadPage.parse_date("31/12/2024") == date(2024, 12, 31)


def test_parse_date_single_digit():
    """ "01/01/2024" → date(2024, 1, 1)"""
    assert DownloadPage.parse_date("01/01/2024") == date(2024, 1, 1)


def test_parse_date_invalid_format():
    """Non-date string raises an exception"""
    with pytest.raises(ValueError):
        DownloadPage.parse_date("not_a_date")


def test_create_invoice_from_button_parses_invoice_data(page, monkeypatch):
    button = Mock()
    button.get_attribute.return_value = "https://x/#123"

    row = Mock()
    cells = [Mock() for _ in range(8)]
    values = [
        "unused0",
        "Sender Name\nExtra",
        "123",
        "SEAC1",
        "unused4",
        "31/12/2024",
        "1.234,56 €",
        "01/01/2025",
    ]
    for cell, value in zip(cells, values):
        cell.text = value

    row.find_elements.return_value = cells
    button.find_element.return_value = row

    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    invoice = page._create_invoice_from_button(button)

    assert isinstance(invoice, InvoiceResponse)
    assert invoice.id == 123
    assert invoice.seac_code == "SEAC1"
    assert invoice.sender_name == "Sender Name"
    assert invoice.creation_date == date(2024, 12, 31)
    assert invoice.reception_date == date(2025, 1, 1)
    assert invoice.amount == Decimal("1234.56")
    logger_error.assert_not_called()


def test_create_invoice_from_button_logs_id_mismatch(page, monkeypatch):
    button = Mock()
    button.get_attribute.return_value = "https://x/#999"

    row = Mock()
    cells = [Mock() for _ in range(8)]
    values = [
        "unused0",
        "Sender Name",
        "123",
        "SEAC1",
        "unused4",
        "31/12/2024",
        "1,00 €",
        "01/01/2025",
    ]
    for cell, value in zip(cells, values):
        cell.text = value

    row.find_elements.return_value = cells
    button.find_element.return_value = row

    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    page._create_invoice_from_button(button)

    logger_error.assert_called_once()


def test_fetch_invoices_returns_empty_when_list_load_times_out(
    page, monkeypatch
):
    page._load_invoice_list = Mock()
    page._wait_element = Mock(side_effect=TimeoutException())
    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    result = page.fetch_invoices()

    assert result == []
    logger_error.assert_called_once()


def test_fetch_invoices_builds_invoice_list(page):
    button1 = Mock()
    button2 = Mock()
    invoice1 = Mock()
    invoice2 = Mock()

    page._load_invoice_list = Mock()
    page._wait_element = Mock()
    page.find_elements = Mock(return_value=[button1, button2])
    page.wait_element_clickable = Mock()
    page._create_invoice_from_button = Mock(side_effect=[invoice1, invoice2])

    result = page.fetch_invoices(new_only=True)

    assert result == [invoice1, invoice2]
    assert page.wait_element_clickable.call_count == 2


def test_is_attachments_popup_visible_true(page):
    close_button = Mock()
    page.wait_element_visible = Mock(return_value=close_button)

    visible, button = page._is_attachments_popup_visible

    assert visible is True
    assert button is close_button


def test_is_attachments_popup_visible_false(page):
    page.wait_element_visible = Mock(side_effect=TimeoutException())

    visible, button = page._is_attachments_popup_visible

    assert visible is False
    assert button is None


def test_on_invoice_list_true_and_false(page, mock_driver):
    mock_driver.title = "documenti ricevuti"
    assert page.on_invoice_list is True

    mock_driver.title = "other page"
    assert page.on_invoice_list is False


def test_download_from_button_downloads_pdf_and_closes_popup(
    page, monkeypatch
):
    button = Mock()
    wrong_item = Mock(text="Something else")
    pdf_item = Mock(text="PDF elettronico")
    page.find_elements = Mock(return_value=[wrong_item, pdf_item])

    chain = Mock()
    chain.move_to_element.return_value = chain
    chain.click.return_value = chain
    action_chains_cls = Mock(return_value=chain)

    monkeypatch.setattr(download_module, "ActionChains", action_chains_cls)
    monkeypatch.setattr(download_module.time, "sleep", Mock())
    monkeypatch.setattr(
        DownloadPage,
        "_is_attachments_popup_visible",
        property(lambda self: (True, Mock())),
    )

    result = page._download_from_button(button)

    assert result is True
    button.click.assert_called_once()
    pdf_item.click.assert_called_once()
    action_chains_cls.assert_called_once()
    chain.perform.assert_called_once()


def test_download_from_button_returns_false_if_no_pdf_entry(page, monkeypatch):
    button = Mock()
    page.find_elements = Mock(return_value=[Mock(text="Attachment")])
    monkeypatch.setattr(download_module.time, "sleep", Mock())

    result = page._download_from_button(button)

    assert result is False


def test_load_invoice_list_rejects_invalid_date_range(page):
    with pytest.raises(ValueError, match="End date cannot be before start"):
        page._load_invoice_list(
            start_date=date(2025, 1, 2), end_date=date(2025, 1, 1)
        )


def test_load_invoice_list_new_only_selects_non_letto_and_filters_by_invoice_id(
    page, monkeypatch
):
    page.driver.get = Mock()

    show_status_div = Mock()
    show_all_div = Mock()
    show_all_div.get_attribute.return_value = "dx-placeholder"
    dropdown_button = Mock()

    def show_find_element(by, value):
        if "@data-dx_placeholder='Tutti'" in value:
            return show_all_div
        if "dx-dropdowneditor-button" in value:
            return dropdown_button
        raise AssertionError(value)

    show_status_div.find_element.side_effect = show_find_element

    update_button = Mock()
    invoice_id_field = Mock()
    page_size_select = Mock()

    def find_element_side_effect(locator):
        if locator == page.SHOW_STATUS_SELECT:
            return show_status_div
        if locator == page.UPDATE_BUTTON:
            return update_button
        raise AssertionError(locator)

    page.find_element = Mock(side_effect=find_element_side_effect)

    def wait_element_side_effect(locator, timeout=None):
        if locator == page.INVOICE_ID_FIELD:
            return invoice_id_field
        if locator == page.LOADING_SPINNER_INVISIBLE:
            return Mock()
        if locator == page.PAGE_SIZE_SELECT:
            return page_size_select
        if locator == page.DROPDOWN_CHOICE:
            return Mock()
        raise AssertionError(locator)

    page._wait_element = Mock(side_effect=wait_element_side_effect)

    non_letto_choice = Mock()
    all_choices = [Mock(), non_letto_choice]

    def find_elements_side_effect(locator):
        if locator == page.DROPDOWN_CHOICE:
            return all_choices
        if locator == page.LOADING_SPINNER:
            return [Mock()]
        raise AssertionError(locator)

    page.find_elements = Mock(side_effect=find_elements_side_effect)

    chain = Mock()
    chain.move_to_element.return_value = chain
    chain.click.return_value = chain
    monkeypatch.setattr(
        download_module, "ActionChains", Mock(return_value=chain)
    )

    selector = Mock()
    monkeypatch.setattr(download_module, "Select", Mock(return_value=selector))

    result = page._load_invoice_list(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        new_only=True,
        invoice_id=777,
    )

    assert result is True
    dropdown_button.click.assert_called_once()
    non_letto_choice.click.assert_called_once()
    invoice_id_field.send_keys.assert_any_call("777")
    selector.select_by_value.assert_called_once_with("1000")
    chain.perform.assert_called_once()


def test_load_invoice_list_clears_filter_when_all_requested(page, monkeypatch):
    page.driver.get = Mock()

    show_status_div = Mock()
    show_all_div = Mock()
    show_all_div.get_attribute.return_value = "dx-state-invisible"
    show_status_input = Mock()
    show_status_input.get_attribute.return_value = "Non letto"
    dropdown_button = Mock()
    clear_button = Mock()

    def show_find_element(by, value):
        if "@data-dx_placeholder='Tutti'" in value:
            return show_all_div
        if "dx-texteditor-input" in value:
            return show_status_input
        if "dx-dropdowneditor-button" in value:
            return dropdown_button
        if "dx-clear-button-area" in value:
            return clear_button
        raise AssertionError(value)

    show_status_div.find_element.side_effect = show_find_element

    update_button = Mock()
    page_size_select = Mock()

    page.find_element = Mock(
        side_effect=lambda locator: (
            show_status_div
            if locator == page.SHOW_STATUS_SELECT
            else update_button
        )
    )
    page.find_elements = Mock(return_value=[Mock()])

    def wait_element_side_effect(locator, timeout=None):
        if locator == page.LOADING_SPINNER_INVISIBLE:
            return Mock()
        if locator == page.PAGE_SIZE_SELECT:
            return page_size_select
        raise AssertionError(locator)

    page._wait_element = Mock(side_effect=wait_element_side_effect)

    chain = Mock()
    chain.move_to_element.return_value = chain
    chain.click.return_value = chain
    monkeypatch.setattr(
        download_module, "ActionChains", Mock(return_value=chain)
    )
    monkeypatch.setattr(download_module, "Select", Mock(return_value=Mock()))

    result = page._load_invoice_list(new_only=False)

    assert result is True
    clear_button.click.assert_called_once()
    dropdown_button.click.assert_not_called()


def test_load_invoice_list_returns_false_when_page_size_select_missing(
    page, monkeypatch
):
    page.driver.get = Mock()

    show_status_div = Mock()
    show_all_div = Mock()
    show_all_div.get_attribute.return_value = "dx-placeholder"
    dropdown_button = Mock()

    def show_find_element(by, value):
        if "@data-dx_placeholder='Tutti'" in value:
            return show_all_div
        if "dx-dropdowneditor-button" in value:
            return dropdown_button
        raise AssertionError(value)

    show_status_div.find_element.side_effect = show_find_element

    update_button = Mock()
    page.find_element = Mock(
        side_effect=lambda locator: (
            show_status_div
            if locator == page.SHOW_STATUS_SELECT
            else update_button
        )
    )
    page.find_elements = Mock(return_value=[Mock()])

    def wait_element_side_effect(locator, timeout=None):
        if locator == page.LOADING_SPINNER_INVISIBLE:
            return Mock()
        if locator == page.PAGE_SIZE_SELECT:
            raise NoSuchElementException()
        raise AssertionError(locator)

    page._wait_element = Mock(side_effect=wait_element_side_effect)

    chain = Mock()
    chain.move_to_element.return_value = chain
    chain.click.return_value = chain
    monkeypatch.setattr(
        download_module, "ActionChains", Mock(return_value=chain)
    )

    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    result = page._load_invoice_list(new_only=False)

    assert result is False
    logger_error.assert_called_once()


def test_download_invoices_single_invoice_success(page):
    invoice = InvoiceResponse(
        id=1,
        seac_code="SEAC1",
        sender_name="Sender",
        creation_date=date(2024, 1, 1),
        reception_date=date(2024, 1, 2),
        amount=Decimal("1.00"),
    )
    page._load_invoice_list = Mock(return_value=True)
    page._wait_element = Mock()
    page.wait_element_clickable = Mock()
    page.find_elements = Mock(return_value=[Mock()])
    page._download_from_button = Mock(return_value=True)

    result = page.download_invoices(invoice)

    assert result == [True]
    page._load_invoice_list.assert_called_once_with(
        start_date=invoice.reception_date, invoice_id=invoice.id
    )


def test_download_invoices_keeps_false_when_list_cannot_be_loaded(
    page, monkeypatch
):
    invoice = InvoiceResponse(
        id=2,
        seac_code="SEAC2",
        sender_name="Sender",
        creation_date=date(2024, 1, 1),
        reception_date=date(2024, 1, 2),
        amount=Decimal("2.00"),
    )
    page._load_invoice_list = Mock(return_value=False)
    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    result = page.download_invoices([invoice])

    assert result == [False]
    logger_error.assert_called_once()


def test_download_invoices_keeps_false_on_load_timeout(page, monkeypatch):
    invoice = InvoiceResponse(
        id=3,
        seac_code="SEAC3",
        sender_name="Sender",
        creation_date=date(2024, 1, 1),
        reception_date=date(2024, 1, 2),
        amount=Decimal("3.00"),
    )
    page._load_invoice_list = Mock(side_effect=TimeoutException())
    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    result = page.download_invoices([invoice])

    assert result == [False]
    logger_error.assert_called_once()


def test_download_invoices_keeps_false_when_download_button_not_found(
    page, monkeypatch
):
    invoice = InvoiceResponse(
        id=4,
        seac_code="SEAC4",
        sender_name="Sender",
        creation_date=date(2024, 1, 1),
        reception_date=date(2024, 1, 2),
        amount=Decimal("4.00"),
    )
    page._load_invoice_list = Mock(return_value=True)
    page._wait_element = Mock(side_effect=TimeoutException())
    logger_error = Mock()
    monkeypatch.setattr(download_module.logger, "error", logger_error)

    result = page.download_invoices([invoice])

    assert result == [False]
    logger_error.assert_called_once()


def test_download_invoices_last_button_result_wins(page):
    invoice = InvoiceResponse(
        id=5,
        seac_code="SEAC5",
        sender_name="Sender",
        creation_date=date(2024, 1, 1),
        reception_date=date(2024, 1, 2),
        amount=Decimal("5.00"),
    )
    buttons = [Mock(name="button1"), Mock(name="button2")]
    page._load_invoice_list = Mock(return_value=True)
    page._wait_element = Mock()
    page.wait_element_clickable = Mock()
    page.find_elements = Mock(return_value=buttons)
    page._download_from_button = Mock(side_effect=[False, True])

    result = page.download_invoices([invoice])

    assert result == [True]
    assert page._download_from_button.call_count == 2
