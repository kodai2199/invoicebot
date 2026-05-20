from unittest.mock import Mock, PropertyMock, patch

import pytest
from selenium.common import TimeoutException

from aow_client.pages.login import LoginPage


@pytest.fixture
def login_page(mock_driver):
    """Fixture for a LoginPage instance with a mock driver"""
    return LoginPage(
        driver=mock_driver,
        url="http://test.com/login",
        username="testuser",
        password="testpass",
    )


def test_login_already_logged_in(login_page, mock_driver):
    """If logged_in is True on load, returns True without filling the form"""
    login_page.load = Mock()
    with patch.object(
        LoginPage, "logged_in", new_callable=PropertyMock
    ) as mock_logged_in:
        mock_logged_in.return_value = True
        result = login_page.login()
        assert result is True
        login_page.load.assert_called_once()


def test_login_success(login_page, mock_driver):
    """ActionChain enters credentials, clicks submit, returns True"""
    mock_username_field = Mock()
    mock_password_field = Mock()
    mock_submit_button = Mock()

    mock_action_chain = Mock()
    mock_action_chain.pause.return_value = mock_action_chain
    mock_action_chain.move_to_element.return_value = mock_action_chain
    mock_action_chain.send_keys_to_element.return_value = mock_action_chain
    mock_action_chain.click.return_value = mock_action_chain

    login_page.load = Mock()
    login_page._wait_stale = Mock()
    with (
        patch.object(
            LoginPage, "logged_in", new_callable=PropertyMock
        ) as mock_logged_in,
        patch("aow_client.pages.login.ActionChains") as mock_action_chains,
    ):
        mock_logged_in.return_value = False
        mock_action_chains.return_value = mock_action_chain

        login_page.wait_element_clickable = Mock(
            side_effect=[
                mock_username_field,
                mock_password_field,
                mock_submit_button,
            ]
        )
        login_page.wait_stale = Mock()
        login_page.wait_page_ready = Mock()

        result = login_page.login()

        assert result is True
        mock_action_chains.assert_called_once_with(mock_driver)
        mock_username_field.clear.assert_called_once()
        mock_password_field.clear.assert_called_once()
        mock_action_chain.send_keys_to_element.assert_any_call(
            mock_username_field, "testuser"
        )
        mock_action_chain.send_keys_to_element.assert_any_call(
            mock_password_field, "testpass"
        )
        mock_action_chain.click.assert_called_once_with(mock_submit_button)
        mock_action_chain.perform.assert_called_once()
        login_page._wait_stale.assert_called_once_with(mock_submit_button, 5)
        login_page.wait_page_ready.assert_called_once()


def test_login_timeout_on_fields(login_page, mock_driver):
    """TimeoutException on waiting for fields → returns False"""
    login_page.load = Mock()
    with patch.object(
        LoginPage, "logged_in", new_callable=PropertyMock
    ) as mock_logged_in:
        mock_logged_in.return_value = False
        login_page.wait_element_clickable = Mock(
            side_effect=TimeoutException()
        )
        result = login_page.login()
        assert result is False
