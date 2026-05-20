from pathlib import Path

import pytest

from aow_client.config import ClientConfigBuilder


def test_from_env_minimal():
    """Builds config from minimal required env vars"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"
    config = ClientConfigBuilder().from_env()
    assert config.username == "test_user"
    assert config.password == "test_pass"
    assert config.base_url == "https://example.com"


def test_from_env_missing_username():
    """Raises ValueError when AOW_USERNAME is absent"""
    import os

    os.environ["AOW_USERNAME"] = ""
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"

    with pytest.raises(ValueError):
        ClientConfigBuilder().from_env()


def test_from_env_missing_password():
    """Raises ValueError when AOW_PASSWORD is absent"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = ""
    os.environ["AOW_BASE_URL"] = "https://example.com"

    with pytest.raises(ValueError):
        ClientConfigBuilder().from_env()


def test_from_env_remote_enabled_no_host():
    """Raises ValueError when remote is on but no host"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"
    os.environ["AOW_REMOTE_ENABLED"] = "true"
    os.environ["AOW_REMOTE_HOST"] = ""

    with pytest.raises(ValueError):
        ClientConfigBuilder().from_env()


def test_from_env_remote_defaults_download_dir():
    """Remote mode defaults remote_download_dir to /home/seluser/downloads"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"
    os.environ["AOW_REMOTE_ENABLED"] = "true"
    os.environ["AOW_REMOTE_HOST"] = "127.0.0.1"
    config = ClientConfigBuilder().from_env()
    assert config.remote_download_dir == Path("/home/seluser/downloads")
    assert config.remote_enabled is True
    assert config.remote_host == "127.0.0.1"


def test_from_env_local_defaults_download_dir():
    """Local mode defaults download_dir to ./invoices"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"
    os.environ["AOW_REMOTE_ENABLED"] = "false"
    config = ClientConfigBuilder().from_env()
    assert config.download_dir == Path("./invoices/downloaded")
    assert config.remote_enabled is False


def test_from_env_custom_download_dir():
    """Custom AOW_DOWNLOAD_DIR is respected"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"
    os.environ["AOW_DOWNLOAD_DIR"] = "/custom/downloads"
    config = ClientConfigBuilder().from_env()
    assert config.download_dir == Path("/custom/downloads")


def test_from_env_invalid_session_timeout():
    """Malformed AOW_SESSION_TIMEOUT raises a descriptive error"""
    import os

    os.environ["AOW_USERNAME"] = "test_user"
    os.environ["AOW_PASSWORD"] = "test_pass"
    os.environ["AOW_BASE_URL"] = "https://example.com"
    os.environ["AOW_SESSION_TIMEOUT"] = "not_an_int"

    with pytest.raises(ValueError):
        ClientConfigBuilder().from_env()
