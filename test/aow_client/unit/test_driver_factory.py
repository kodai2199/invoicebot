from pathlib import Path
from unittest.mock import Mock

import pytest
from selenium.common.exceptions import WebDriverException

from aow_client.config import ClientConfig
from aow_client.driver_factory import WebDriverFactory


def _make_config(**overrides) -> ClientConfig:
    payload = {
        "username": "test_user",
        "password": "test_pass",
        "base_url": "https://example.com",
        "download_dir": Path("./downloads"),
        "remote_download_dir": Path("/home/seluser/downloads"),
        "remote_enabled": False,
        "remote_host": None,
        "chrome_binary_path": None,
    }
    payload.update(overrides)
    return ClientConfig(**payload)


def test_build_chrome_options_uses_local_download_dir(tmp_path):
    config = _make_config(
        download_dir=tmp_path / "local", remote_enabled=False
    )

    options = WebDriverFactory._build_chrome_options(config)

    assert "--window-size=1920,1080" in options.arguments
    prefs = options.experimental_options["prefs"]
    assert prefs["download.default_directory"] == str(
        config.download_dir.absolute()
    )
    assert prefs["download.prompt_for_download"] is False
    assert (
        prefs["profile.default_content_setting_values.automatic_downloads"]
        == 1
    )
    assert prefs["profile.default_content_settings.popups"] == 0


def test_build_chrome_options_uses_remote_download_dir(tmp_path):
    config = _make_config(
        remote_enabled=True,
        remote_host="http://selenium:4444/wd/hub",
        remote_download_dir=tmp_path / "remote",
    )

    options = WebDriverFactory._build_chrome_options(config)

    prefs = options.experimental_options["prefs"]
    assert prefs["download.default_directory"] == str(
        config.remote_download_dir.absolute()
    )


def test_create_driver_remote_uses_webdriver_remote(monkeypatch):
    config = _make_config(
        remote_enabled=True,
        remote_host="http://selenium:4444/wd/hub",
    )
    fake_options = Mock(name="chrome_options")
    fake_driver = Mock(name="remote_driver")
    remote_ctor = Mock(return_value=fake_driver)

    monkeypatch.setattr(
        "aow_client.driver_factory.WebDriverFactory._build_chrome_options",
        Mock(return_value=fake_options),
    )
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Remote", remote_ctor
    )

    result = WebDriverFactory.create_driver(config)

    assert result is fake_driver
    remote_ctor.assert_called_once_with(
        command_executor=config.remote_host,
        options=fake_options,
    )


def test_create_driver_remote_missing_host_raises(monkeypatch):
    config = _make_config(remote_enabled=True, remote_host=None)
    remote_ctor = Mock()

    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Remote", remote_ctor
    )

    with pytest.raises(ValueError, match="remote_host not configured"):
        WebDriverFactory.create_driver(config)

    remote_ctor.assert_not_called()


def test_create_driver_local_uses_chrome_and_service(monkeypatch):
    config = _make_config(remote_enabled=False)
    fake_options = Mock(name="chrome_options")
    fake_service = Mock(name="chrome_service")
    fake_driver = Mock(name="local_driver")
    service_ctor = Mock(return_value=fake_service)
    chrome_ctor = Mock(return_value=fake_driver)

    monkeypatch.setattr(
        "aow_client.driver_factory.WebDriverFactory._build_chrome_options",
        Mock(return_value=fake_options),
    )
    monkeypatch.setattr("aow_client.driver_factory.Service", service_ctor)
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Chrome", chrome_ctor
    )

    result = WebDriverFactory.create_driver(config)

    assert result is fake_driver
    service_ctor.assert_called_once_with()
    chrome_ctor.assert_called_once_with(
        service=fake_service,
        options=fake_options,
    )


def test_create_driver_local_sets_chrome_binary_path(monkeypatch):
    config = _make_config(
        remote_enabled=False,
        chrome_binary_path="/usr/bin/google-chrome",
    )
    fake_options = Mock(name="chrome_options")
    fake_options.binary_location = None
    service_ctor = Mock(return_value=Mock(name="chrome_service"))
    chrome_ctor = Mock(return_value=Mock(name="local_driver"))

    monkeypatch.setattr(
        "aow_client.driver_factory.WebDriverFactory._build_chrome_options",
        Mock(return_value=fake_options),
    )
    monkeypatch.setattr("aow_client.driver_factory.Service", service_ctor)
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Chrome", chrome_ctor
    )

    WebDriverFactory.create_driver(config)

    assert fake_options.binary_location == "/usr/bin/google-chrome"


def test_create_driver_remote_reraises_webdriver_exception(monkeypatch):
    config = _make_config(
        remote_enabled=True,
        remote_host="http://selenium:4444/wd/hub",
    )
    fake_options = Mock(name="chrome_options")

    monkeypatch.setattr(
        "aow_client.driver_factory.WebDriverFactory._build_chrome_options",
        Mock(return_value=fake_options),
    )
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Remote",
        Mock(side_effect=WebDriverException("boom")),
    )

    with pytest.raises(WebDriverException, match="boom"):
        WebDriverFactory.create_driver(config)


def test_create_driver_local_reraises_webdriver_exception(monkeypatch):
    config = _make_config(remote_enabled=False)
    fake_options = Mock(name="chrome_options")

    monkeypatch.setattr(
        "aow_client.driver_factory.WebDriverFactory._build_chrome_options",
        Mock(return_value=fake_options),
    )
    monkeypatch.setattr("aow_client.driver_factory.Service", Mock())
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Chrome",
        Mock(side_effect=WebDriverException("boom")),
    )

    with pytest.raises(WebDriverException, match="boom"):
        WebDriverFactory.create_driver(config)


def test_create_driver_remote_does_not_call_local_chrome(monkeypatch):
    config = _make_config(
        remote_enabled=True,
        remote_host="http://selenium:4444/wd/hub",
    )
    remote_ctor = Mock(return_value=Mock(name="remote_driver"))
    chrome_ctor = Mock()

    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Remote", remote_ctor
    )
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Chrome", chrome_ctor
    )

    WebDriverFactory.create_driver(config)

    remote_ctor.assert_called_once()
    chrome_ctor.assert_not_called()


def test_create_driver_local_does_not_call_remote(monkeypatch):
    config = _make_config(remote_enabled=False)
    remote_ctor = Mock()
    chrome_ctor = Mock(return_value=Mock(name="local_driver"))

    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Remote", remote_ctor
    )
    monkeypatch.setattr(
        "aow_client.driver_factory.webdriver.Chrome", chrome_ctor
    )
    monkeypatch.setattr(
        "aow_client.driver_factory.Service", Mock(return_value=Mock())
    )

    WebDriverFactory.create_driver(config)

    chrome_ctor.assert_called_once()
    remote_ctor.assert_not_called()
