from logging import getLogger

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

from aow_client.config import ClientConfig

logger = getLogger(__name__)


class WebDriverFactory:
    """Factory for creating WebDriver instances (local or remote)."""

    @staticmethod
    def create_driver(config: ClientConfig) -> WebDriver:
        """Create a WebDriver instance based on configuration.

        Args:
            config: ClientConfig instance with driver configuration.

        Returns:
            WebDriver instance (local or remote).

        Raises:
            ValueError: If remote driver is enabled but host is not configured.
            WebDriverException: If driver initialization fails.
        """
        chrome_options = WebDriverFactory._build_chrome_options(config)

        try:
            if config.remote_enabled:
                if not config.remote_host:
                    raise ValueError(
                        "Remote driver enabled but remote_host not configured"
                    )
                logger.info(
                    f"Creating remote WebDriver at {config.remote_host}"
                )
                return webdriver.Remote(
                    command_executor=config.remote_host, options=chrome_options
                )
            else:
                logger.info("Creating local WebDriver")
                chrome_service = Service()
                if config.chrome_binary_path:
                    chrome_options.binary_location = config.chrome_binary_path
                return webdriver.Chrome(
                    service=chrome_service, options=chrome_options
                )
        except WebDriverException as e:
            logger.error(f"Failed to create WebDriver: {e}")
            raise

    @staticmethod
    def _build_chrome_options(config: ClientConfig) -> Options:
        """Build Chrome options for WebDriver."""
        options = Options()
        options.add_argument("--window-size=1920,1080")

        chrome_download_dir = (
            config.remote_download_dir
            if config.remote_enabled
            else config.download_dir
        )

        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": str(
                    chrome_download_dir.absolute()
                ),
                "download.prompt_for_download": False,
                (
                    "profile.default_content_setting_values."
                    "automatic_downloads"
                ): 1,
                "profile.default_content_settings.popups": 0,
            },
        )

        return options
