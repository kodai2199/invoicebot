import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class ClientConfig:
    """Configuration for the AziendaOnWeb client."""

    username: str
    password: str
    base_url: str
    remote_download_dir: Path = Path("/home/seluser/downloads")
    download_dir: Path = Path("./invoices/downloaded")
    session_timeout: int = 180  # seconds
    element_timeout: int = 10  # seconds
    download_timeout: int = 30  # seconds
    page_load_wait: float = 1.0  # seconds
    download_wait: float = 3.0  # seconds
    remote_enabled: bool = False
    remote_host: str | None = None
    chrome_binary_path: str | None = None


class ClientConfigBuilder:
    """Builder for ClientConfig using environment variables and defaults."""

    @staticmethod
    def from_env(env_path: Path | None = None) -> ClientConfig:
        """Build ClientConfig from environment variables.

        Environment variables:
            - AOW_USERNAME: AziendaOnWeb username (required)
            - AOW_PASSWORD: AziendaOnWeb password (required)
            - AOW_BASE_URL: AziendaOnWeb base URL (default:
              https://aziendaweb.seac.it)
            - AOW_DOWNLOAD_DIR: Directory for downloads (default:
              ./invoices/downloaded)
            - AOW_REMOTE_DOWNLOAD_DIR: Directory for downloads of a remote
              Selenium instance (default: /home/seluser/downloads)
            - AOW_ENV_PATH: Path to .env file (default: .env)
            - AOW_SESSION_TIMEOUT: Session timeout in seconds (default: 180)
            - AOW_ELEMENT_TIMEOUT: Element wait timeout in seconds
              (default: 10)
            - AOW_DOWNLOAD_TIMEOUT: Download timeout in seconds (default: 30)
            - AOW_PAGE_LOAD_WAIT: Page load wait in seconds (default: 1.0)
            - AOW_DOWNLOAD_WAIT: Download wait in seconds (default: 3.0)
            - AOW_REMOTE_ENABLED: Enable remote driver (default: false)
            - AOW_REMOTE_HOST: Remote driver host URL (required if remote
              enabled)
            - AOW_CHROME_BINARY_PATH: Path to Chrome binary (optional)

        Args:
            env_path: Path to the environment file (default: .env).

        Returns:
            ClientConfig instance.

        Raises:
            ValueError: If required environment variables are missing.
        """
        env_path = env_path or Path(os.getenv("AOW_ENV_PATH", ".env"))
        load_dotenv(env_path)

        username = os.getenv("AOW_USERNAME")
        password = os.getenv("AOW_PASSWORD")

        if not username or not password:
            raise ValueError(
                "Missing required environment variables: "
                "AOW_USERNAME and AOW_PASSWORD"
            )

        download_dir = os.getenv("AOW_DOWNLOAD_DIR", None)
        if not download_dir:
            download_dir = Path("./invoices/downloaded")
        else:
            download_dir = Path(download_dir)

        remote_download_dir = os.getenv("AOW_REMOTE_DOWNLOAD_DIR", None)
        if not remote_download_dir:
            remote_download_dir = Path("/home/seluser/downloads")
        else:
            remote_download_dir = Path(remote_download_dir)

        base_url = os.getenv("AOW_BASE_URL", "https://aziendaweb.seac.it")
        session_timeout = int(os.getenv("AOW_SESSION_TIMEOUT", "180"))
        element_timeout = int(os.getenv("AOW_ELEMENT_TIMEOUT", "10"))
        download_timeout = int(os.getenv("AOW_DOWNLOAD_TIMEOUT", "30"))
        page_load_wait = float(os.getenv("AOW_PAGE_LOAD_WAIT", "1.0"))
        download_wait = float(os.getenv("AOW_DOWNLOAD_WAIT", "3.0"))
        remote_enabled = (
            os.getenv("AOW_REMOTE_ENABLED", "false").lower() == "true"
        )
        remote_host = os.getenv("AOW_REMOTE_HOST")
        chrome_binary_path = os.getenv("AOW_CHROME_BINARY_PATH")

        if remote_enabled and not remote_host:
            raise ValueError(
                "Remote driver enabled but AOW_REMOTE_HOST "
                "environment variable not set"
            )

        return ClientConfig(
            username=username,
            password=password,
            base_url=base_url,
            download_dir=download_dir,
            remote_download_dir=remote_download_dir,
            session_timeout=session_timeout,
            element_timeout=element_timeout,
            download_timeout=download_timeout,
            page_load_wait=page_load_wait,
            download_wait=download_wait,
            remote_enabled=remote_enabled,
            remote_host=remote_host,
            chrome_binary_path=chrome_binary_path,
        )
