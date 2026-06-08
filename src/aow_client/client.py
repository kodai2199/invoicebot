"""AziendaOnWeb Selenium Client.

A robust client for automating invoice downloads from AziendaOnWeb using
Selenium. Supports both local and remote (Selenium Grid) WebDriver instances.
"""

import logging
import time
from datetime import date, datetime
from typing import TypeVar

from selenium.webdriver.remote.webdriver import WebDriver

from aow_client.config import ClientConfig, ClientConfigBuilder
from aow_client.driver_factory import WebDriverFactory
from aow_client.pages.dashboard import DashboardPage
from aow_client.pages.download import DownloadPage
from aow_client.pages.login import LoginPage
from aow_client.types import InvoiceLike, InvoiceResponse

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=InvoiceLike, default=InvoiceResponse, covariant=True)


class AziendaOnWebClient:
    """Client for interacting with AziendaOnWeb using Selenium.

    Handles login, invoice fetching, and invoice downloading with automatic
    session management and error recovery.

    Args:
        config: ClientConfig instance with client configuration.
    """

    DOC_PREFIX = "Documento_di_vendita_ricevuto_"
    DOC_SUFFIX = ".pdf"

    def __init__(self, config: ClientConfig):
        self.config = config
        if not config.remote_enabled:
            config.download_dir.mkdir(exist_ok=True, parents=True)

        self.download_dir = config.download_dir

        self.driver: WebDriver | None = None
        self.last_action = None

        # Page objects
        self.login_page: LoginPage | None = None
        self.dashboard_page: DashboardPage | None = None
        self.download_page: DownloadPage | None = None

    def _create_new_session(self) -> None:
        """Create a new WebDriver session and initialize page objects."""
        self._close_driver()

        try:
            self.driver = WebDriverFactory.create_driver(self.config)
            logger.info("WebDriver session created successfully.")

            # Initialize page objects
            self.login_page = LoginPage(
                self.driver,
                self.config.base_url,
                self.config.username,
                self.config.password,
            )
            self.dashboard_page = DashboardPage(
                self.driver, f"{self.config.base_url}/impresa/dashboard"
            )
            self.download_page = DownloadPage(
                self.driver,
                f"{self.config.base_url}/fatturazione/documento-vendita-ricevuto",
            )

            time.sleep(self.config.page_load_wait)
            self._update_last_action()
        except Exception as e:
            logger.error(f"Failed to create new session: {e}")
            raise

    def _close_driver(self) -> None:
        """Close the WebDriver session gracefully."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver session closed")
            except Exception as e:
                logger.warning(
                    f"Error quitting driver: {e}. Continuing with cleanup."
                )
            self.driver = None
            self.last_action = None

    def _check_session_timeout(self) -> None:
        """Check if session has timed out and create a new one if needed."""
        if self.last_action is None:
            logger.info("Creating a session for the first time.")
            self._create_new_session()
            return

        elapsed = (datetime.now() - self.last_action).total_seconds()
        if elapsed > self.config.session_timeout:
            timeout = self.config.session_timeout
            logger.info(
                f"Session timeout reached ({elapsed}s > {timeout}s). "
                "Creating new session."
            )
            self._create_new_session()

    def _update_last_action(self) -> None:
        """Update the timestamp of the last action."""
        self.last_action = datetime.now()

    def is_logged_in(self) -> bool:
        """Check if the current session is logged in.

        This method navigates to the login page to verify the login status.
        Use with caution as it changes the current page context.

        Returns:
            True if logged in, False otherwise.
        """
        self._check_session_timeout()

        try:
            current_url = self.driver.current_url
            self.login_page.load()
            logged_in = self.login_page.logged_in
            # Try to restore the original URL
            self.driver.get(current_url)
            self._update_last_action()
            return logged_in
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def login(self) -> bool:
        """Perform login to AziendaOnWeb.

        Returns:
            True if login was successful, False otherwise.
        """
        self._check_session_timeout()

        try:
            if self.login_page.login():
                logger.info("Login successful.")
                self.dashboard_page.accept_cookies()
                self._update_last_action()
                return True
            else:
                logger.error("Login failed.")
                return False
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False

    def fetch_invoices(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        new_only: bool = True,
    ) -> list[InvoiceResponse]:
        """Fetch the list of new invoices available for download.

        Returns:
            List of Invoice objects, or empty list if no invoices are available
            or an error occurs.
        """
        self._check_session_timeout()

        try:
            if not self.login():
                return []
            self._update_last_action()
            return self.download_page.fetch_invoices(
                start_date=start_date, end_date=end_date, new_only=new_only
            )
        except Exception as e:
            logger.error(f"Error fetching new invoices: {e}")
            return []

    def download_invoices(self, invoices: T | list[T]) -> dict[T, bool]:
        """Download invoices from AziendaOnWeb.

        Args:
            invoices: A single Invoice or list of Invoice objects to download.

        Returns:
            Dictionary mapping each invoice to its download status (True =
            success).
        """
        self._check_session_timeout()

        if isinstance(invoices, InvoiceLike):
            invoices = [invoices]

        if not invoices:
            return {}

        try:
            if not self.login():
                logger.error("Cannot download: not logged in")
                return {invoice: False for invoice in invoices}

            # Download invoices using the download page
            download_results = self.download_page.download_invoices(invoices)

            # Verify downloaded files exist
            results = {}
            for i, invoice in enumerate(invoices):
                if not download_results[i]:
                    results[invoice] = False
                    logger.error(f"Failed to download invoice {invoice.id}")
                    continue

                invoice_path = (
                    self.download_dir
                    / f"{self.DOC_PREFIX}{invoice.id}{self.DOC_SUFFIX}"
                )
                results[invoice] = invoice_path.exists()
                if not results[invoice]:
                    logger.warning(
                        f"Downloaded file not found for invoice {invoice.id}"
                    )
            self._update_last_action()
            return results
        except Exception as e:
            logger.error(f"Error downloading invoices: {e}")
            return {invoice: False for invoice in invoices}

    def close(self) -> None:
        """Close the client and clean up resources."""
        self._close_driver()

    def __enter__(self) -> "AziendaOnWebClient":
        """Enable context manager usage."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close resources when leaving context manager scope."""
        self.close()
        return None


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging for the application.

    Args:
        log_level: Logging level (default: INFO).
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


if __name__ == "__main__":
    # Example usage
    setup_logging("INFO")

    try:
        config = ClientConfigBuilder.from_env()
        client = AziendaOnWebClient(config)

        # Fetch and download new invoices
        logger.info("Fetching new invoices...")
        new_invoices = client.fetch_invoices(new_only=False)

        if new_invoices:
            logger.info(f"Found {len(new_invoices)} new invoices")
            results = client.download_invoices(new_invoices)

            for invoice, success in results.items():
                status = "✓ Downloaded" if success else "✗ Failed"
                logger.info(f"{status}: {invoice}")
        else:
            logger.info("No new invoices to download")

        client.close()
        logger.info("Client closed successfully")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
