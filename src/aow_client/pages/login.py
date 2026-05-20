from logging import getLogger

from selenium.common import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from aow_client.pages.base import BasePage, Locator

logger = getLogger(__name__)


class LoginPage(BasePage):
    """Page representing the login form of AziendaOnWeb.

    This class allows the client to perform login with the given credentials.

    Args:
        username (str): The username to login with.
        password (str): The password to login with.
    """

    USERNAME_FIELD = Locator(By.ID, "userName")
    PASSWORD_FIELD = Locator(By.ID, "password")
    SUBMIT_BUTTON = Locator(By.CLASS_NAME, "mat-button-base")
    DASHBOARD_READY_MARKER = Locator(By.ID, "documento-vendita-ricevuto")
    LOGIN_PAGE_KEYWORD = "AziendaOnWeb"

    def __init__(
        self,
        driver,
        url: str,
        username: str,
        password: str,
        default_timeout: int | float = 10,
    ):
        super().__init__(driver, url, default_timeout=default_timeout)
        self.username = username
        self.password = password

    def _perform_actions(self, username_field, password_field, submit_button):
        username_field.clear()
        password_field.clear()
        (
            ActionChains(self.driver)
            .pause(0.1)
            .move_to_element(username_field)
            .send_keys_to_element(username_field, self.username)
            .pause(0.1)
            .move_to_element(password_field)
            .send_keys_to_element(password_field, self.password)
            .pause(0.1)
            .click(submit_button)
            .perform()
        )

    def _wait_stale(
        self, web_element, timeout: int | float | None = None
    ) -> None:
        wait_timeout = timeout or self.default_timeout
        return WebDriverWait(self.driver, wait_timeout).until(
            expected_conditions.staleness_of(web_element),
        )

    def login(self) -> bool:
        """Performs login.

        If we are not logged in yet, then the function waits for
        the login fields to appear, and populates them. It then clicks
        on the submit button.

        Note that the login process is highly unreliable. Multiple times,
        during testing, clicking on the submit button after populating the
        login form would randomly not work. This is why the function re-tries
        clearing, filling the form and clicking the button for three times
        before giving up.

        Returns:
            bool: Whether the login was successful or not
        """
        self.load()

        if self.logged_in:
            logger.info("Already logged in.")
            return True

        try:
            username_field = self.wait_element_clickable(self.USERNAME_FIELD)
            password_field = self.wait_element_clickable(
                self.PASSWORD_FIELD, timeout=2
            )
            submit_button = self.wait_element_clickable(
                self.SUBMIT_BUTTON, timeout=2
            )
            for i in range(3):
                try:
                    self._perform_actions(
                        username_field, password_field, submit_button
                    )
                    self._wait_stale(submit_button, 5)
                    self.wait_page_ready()
                    return True
                except TimeoutException:
                    logger.error(
                        "All login elements have been identified and "
                        "interacted with, but apparently the login did "
                        "not succeed."
                    )
                    continue
            return False
        except TimeoutException:
            logger.error("Could not login.")
            return False

    @property
    def logged_in(self):
        """Checks if the title contains a specific keyword.

        Although a better check could be implemented, this is extremely fast
        and, so far, effective enough to fullfill its purpose.

        Returns:
            bool: True if the driver is currently on the Login page, False
                otherwise.
        """
        return self.LOGIN_PAGE_KEYWORD in self.driver.title
