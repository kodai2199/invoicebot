from unittest.mock import MagicMock

import pytest

from aow_client.config import ClientConfig


@pytest.fixture
def base_config(tmp_path):
    return ClientConfig(
        username="test_user",
        password="test_pass",
        base_url="https://example.com",
        download_dir=tmp_path / "downloads",
        session_timeout=180,
    )


@pytest.fixture
def mock_driver():
    """Fixture for a mock Selenium WebDriver"""
    driver = MagicMock()
    driver.title = "AziendaOnWeb"
    driver.current_url = "https://example.com"
    return driver
