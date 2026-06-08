from unittest.mock import Mock

import pytest
from selenium.common import TimeoutException

from aow_client.pages.dashboard import DashboardPage


@pytest.fixture
def dashboard_page(mock_driver):
    """Fixture for a DashboardPage instance with a mock driver"""
    dashboard_page = DashboardPage(
        driver=mock_driver,
        url="http://test.com/dashboard",
    )
    dashboard_page.load = Mock()
    return dashboard_page


def test_accept_cookies_no_banner(dashboard_page):
    """If no banner is visible, returns True immediately"""
    dashboard_page._is_cookie_banner_visible = Mock(return_value=False)
    result = dashboard_page.accept_cookies()
    assert result is True
    dashboard_page._is_cookie_banner_visible.assert_called_once()
    dashboard_page.load.assert_called_once()


def test_accept_cookies_success(dashboard_page):
    """Banner found, button clicked, banner disappears → True"""
    dashboard_page._is_cookie_banner_visible = Mock(side_effect=[True, False])
    accept_button = Mock()
    accept_button.click = Mock()
    dashboard_page._wait_element = Mock(return_value=accept_button)
    result = dashboard_page.accept_cookies()
    accept_button.click.assert_called_once()
    assert result is True
    dashboard_page._is_cookie_banner_visible.assert_called()
    dashboard_page.load.assert_called_once()


def test_accept_cookies_button_not_found_but_banner_gone(dashboard_page):
    """No button but no banner → True"""
    dashboard_page._is_cookie_banner_visible = Mock(side_effect=[True, False])
    dashboard_page._wait_element = Mock(side_effect=TimeoutException())
    result = dashboard_page.accept_cookies()
    assert result is True
    dashboard_page._is_cookie_banner_visible.assert_called()
    dashboard_page.load.assert_called_once()


def test_accept_cookies_button_not_found_banner_still_visible(dashboard_page):
    """No button and banner persists → False"""
    dashboard_page._is_cookie_banner_visible = Mock(side_effect=[True, True])
    dashboard_page._wait_element = Mock(side_effect=TimeoutException())
    result = dashboard_page.accept_cookies()
    assert result is False
    dashboard_page._is_cookie_banner_visible.assert_called()
    dashboard_page.load.assert_called_once()


def test_new_invoices_available_with_cards(dashboard_page):
    """div.card elements found → returns True"""
    dashboard_page._is_cookie_banner_visible = Mock(return_value=False)
    invoices_card = Mock()
    invoices_card.find_elements = Mock(return_value=[1, 2, 3])
    dashboard_page._wait_element = Mock(return_value=invoices_card)
    result = dashboard_page.new_invoices_available()
    assert result is True
    invoices_card.find_elements.assert_called_once()
    dashboard_page._is_cookie_banner_visible.assert_called()
    dashboard_page.load.assert_called_once()


def test_new_invoices_available_no_cards(dashboard_page):
    """No div.card elements → returns False"""
    dashboard_page._is_cookie_banner_visible = Mock(return_value=False)
    invoices_card = Mock()
    invoices_card.find_elements = Mock(return_value=[])
    dashboard_page._wait_element = Mock(return_value=invoices_card)
    result = dashboard_page.new_invoices_available()
    assert result is False
    invoices_card.find_elements.assert_called_once()
    dashboard_page._is_cookie_banner_visible.assert_called()
    dashboard_page.load.assert_called_once()


def test_new_invoices_available_section_timeout(dashboard_page):
    """INVOICES_SECTION times out → returns False"""
    dashboard_page._is_cookie_banner_visible = Mock(return_value=False)
    dashboard_page._wait_element = Mock(side_effect=TimeoutException())
    result = dashboard_page.new_invoices_available()
    assert result is False
    dashboard_page._is_cookie_banner_visible.assert_called()
    dashboard_page.load.assert_called_once()
