from logging import getLogger

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from aow_client.pages.base import BasePage, Locator

logger = getLogger(__name__)


class DashboardPage(BasePage):
    """Page representing the Dashboard (or Home Page) of AziendaOnWeb.

    The Dashboard is the page a client is automatically redirected to after
    login.

    The Dashboard is a useful shortcut to discover whether new invoices are
    available or not, since a warning card will be displayed when new invoices
    are available. Moreover, it is a good place to deal with cookie banners,
    since the client is redirected to the Dashboard after login, and thus it is
    the first page the client encounters that could show cookie banners.
    """

    NEW_INVOICES_SECTION = Locator(By.ID, "documento-vendita-ricevuto")
    COOKIE_BANNER = Locator(By.ID, "iubenda-cs-banner")
    COOKIE_ACCEPT_BUTTON = Locator(By.CLASS_NAME, "iubenda-cs-accept-btn")
    DASHBOARD_TITLE = "Impresa - AziendaOnWeb"

    def __init__(self, driver, url: str):
        super().__init__(driver, url)

    def new_invoices_available(self) -> bool:
        """Briefly check whether new invoices are available or not.

        It works by searching for a specific warning card on the Dashboard.

        This method also takes care of accepting cookies, should the cookie
        banner be visible.

        Returns:
            bool: `True` if new invoices are available, `False` if no invoices
                are available, or if there were issues accepting cookies.
        """
        self.load()

        if self._is_cookie_banner_visible():
            accepted = self.accept_cookies()
            if not accepted:
                logger.warning("Could not accept cookies")
                return False

        # Ensure that the invoice cards are loaded, by waiting for one to
        # appear
        try:
            new_invoices_card = self.wait_element(self.NEW_INVOICES_SECTION)
        except TimeoutException:
            logger.warning(
                "Could not obtain the invoice cards, so there must be no "
                "invoices available!"
            )
            return False

        new_invoices_link_cards = new_invoices_card.find_elements(
            By.CSS_SELECTOR, "div.card"
        )
        if len(new_invoices_link_cards) > 0:
            logger.info("There are some invoices that require downloading.")
            new_invoices_available = True
        else:
            logger.info("No new invoices available.")
            new_invoices_available = False
        return new_invoices_available

    @property
    def on_home_page(self) -> bool:
        """Checks if the title matches the expected Dashboard title.

        Although a better check could be implemented, this is extremely fast
        and, so far, effective enough to fullfill its purpose.

        Returns:
            bool: True if the driver is currently on the Dashboard, False
                otherwise.
        """
        return self.DASHBOARD_TITLE in self.driver.title

    def accept_cookies(self) -> bool:
        """Tries to find the cookie banner and click on the "Accept" button.

        This allows it to disappear and ensures it does not re-appear for the
        current session. Note that this method will try to load the Dashboard
        if the client is not on it already.

        Returns:
            bool: True if the cookies appear to have been accepted (i.e. no
                banner is now visible), False otherwise.
        """
        if not self.on_home_page:
            self.load()

        if not self._is_cookie_banner_visible():
            return True

        try:
            cookies_accept_button = self.wait_element(
                self.COOKIE_ACCEPT_BUTTON,
                timeout=2,
            )
            cookies_accept_button.click()
            if not self._is_cookie_banner_visible(0.5):
                logger.info("Cookies accepted successfully.")
                cookies_accepted = True
            else:
                logger.warning("Cookies accepted, but banner still visible.")
                cookies_accepted = False
        except TimeoutException:
            logger.info("Cookies accept button not found.")
            if not self._is_cookie_banner_visible(0.5):
                logger.info(
                    "But since no banner is visible, "
                    "we can assume cookies are accepted."
                )
                cookies_accepted = True
            else:
                logger.warning("However, the cookie banner is still visible.")
                cookies_accepted = False
        return cookies_accepted

    def _is_cookie_banner_visible(
        self, timeout: int | float | None = None
    ) -> bool:
        try:
            self.wait_element_visible(self.COOKIE_BANNER, timeout)
            return True
        except TimeoutException:
            return False
