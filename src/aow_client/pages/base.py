from dataclasses import dataclass

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By, ByType
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait


@dataclass(slots=True, frozen=True)
class Locator:
    """A class to locate and identify elements within the Selenium API.

    Attributes:
        by: A `selenium.webdriver.common.by.By` element, like `By.CLASS_NAME`
        value: The value of the locator. For example, the HTML class name.

    """

    by: ByType
    value: str

    def as_tuple(self) -> tuple[ByType, str]:
        """Returns the locator as a tuple.

        Returns:
            `by` as first element, `value` as second.
        """
        return (self.by, self.value)


class BasePage:
    """Base class for all Pages.

    Pages are classes that have a WebDriver and a URL identifying them. In
    general, they will load the URL and provide methods to interact with the
    content. This includes reading data, selecting elements and filling forms.

    Args:
        driver: The WebDriver instance that the class will use to load and
            interact with the page.
        url: The url of the web resource.
        default_timeout: Time, in seconds, to use as default for all operations
            that support a timeout, such as wait_element. It is recommended to
            avoid setting this argument to `None`, to avoid functions blocking
            indefinitely. Defaults to 15.
    """

    def __init__(
        self,
        driver: WebDriver,
        url: str,
        default_timeout: int | float | None = 15,
    ):
        self.driver = driver
        self.url = url
        self.default_timeout = default_timeout

    def load(self) -> None:
        """Loads the page URL using the WebDriver."""
        self.driver.get(self.url)

    def _solve_locator(
        self, locator: Locator | WebElement
    ) -> tuple[ByType, str]:
        if isinstance(locator, Locator):
            return locator.as_tuple()
        return locator

    def _wait_element(
        self, locator: Locator | WebElement, timeout: int | float | None = None
    ) -> WebElement:
        """Block until an object is present on the page or the timeout expires.

        Args:
            locator: The element to wait for.
            timeout: Maximum time, in seconds, to wait before raising a
                `TimeoutException`. Defaults to `None`. If `None`, it will take
                the value of the Page's default timeout instead.

        Raises:
            TimeoutException: if `timeout` is not `None`, this exception will
                be raised if the element could not be located before
                `timeout` has elapsed.

        Returns:
            WebElement: A reference to the element whose presence has been
                assured.
        """
        wait_timeout = timeout or self.default_timeout
        return WebDriverWait(self.driver, wait_timeout).until(
            expected_conditions.presence_of_element_located(
                self._solve_locator(locator)
            )
        )

    def wait_element_visible(
        self, locator: Locator | WebElement, timeout: int | float | None = None
    ) -> WebElement:
        """Block until an object is visible on the page or the timeout expires.

        Args:
            locator: The element to wait for.
            timeout: Maximum time, in seconds, to wait before raising a
                `TimeoutException`. Defaults to `None`. If `None`, it will take
                the value of the Page's default timeout instead.

        Raises:
            TimeoutException: if `timeout` is not `None`, this exception will
                be raised if the element could not be located before
                `timeout` has elapsed.

        Returns:
            WebElement: A reference to the element whose presence has been
                assured.
        """
        wait_timeout = timeout or self.default_timeout
        return WebDriverWait(self.driver, wait_timeout).until(
            expected_conditions.visibility_of_element_located(
                self._solve_locator(locator)
            )
        )

    def wait_element_clickable(
        self, locator: Locator | WebElement, timeout: int | float | None = None
    ) -> WebElement:
        """Block until an object is clickable or the timeout expires.

        Args:
            locator: The element to wait for.
            timeout: Maximum time, in seconds, to wait before raising a
                `TimeoutException`. Defaults to `None`. If `None`, it will take
                the value of the Page's default timeout instead.

        Raises:
            TimeoutException: if `timeout` is not `None`, this exception will
                be raised if the element could not be located before
                `timeout` has elapsed.

        Returns:
            WebElement: A reference to the element whose presence has been
                assured.
        """
        wait_timeout = timeout or self.default_timeout
        return WebDriverWait(self.driver, wait_timeout).until(
            expected_conditions.element_to_be_clickable(
                self._solve_locator(locator)
            )
        )

    def find_element(self, locator: Locator) -> WebElement:
        """Returns a reference to the first WebElement identified by `locator`.

        Args:
            locator: The element to search for.

        Raises:
            NoSuchElementException: if no elements are identified by locator.

        Returns:
            WebElement: A reference to the first element identified by
                `locator`.
        """
        return self.driver.find_element(*locator.as_tuple())

    def find_elements(self, locator: Locator) -> list[WebElement]:
        """Returns a list of reference to WebElement(s) found with `locator`.

        Args:
            locator: The elements to search for.

        Raises:
            NoSuchElementException: if no elements are identified by locator.

        Returns:
            list[WebElement]: A list of references to the elements identified
                by `locator`.
        """
        return self.driver.find_elements(*locator.as_tuple())

    def has_element(
        self, locator: Locator, timeout: int | float | None = None
    ) -> bool:
        """Boolean check for presence of an element on the page.

        Returns true if an element identified by locator is present on the
        page, or false otherwise. It is blocking for a duration up to `timeout`
        seconds. It is a convenience wrapper of `wait_element`.

        Args:
            locator: The element to wait for.
            timeout: Maximum time, in seconds, to wait before raising a
                `TimeoutException`. Defaults to `None`. If `None`, it will take
                the value of the Page's default timeout instead.

        Returns:
            bool: Whether the element identified by `locator` is present on the
                page or not.
        """
        try:
            self._wait_element(locator, timeout)
            return True
        except TimeoutException:
            return False

    def wait_page_ready(self, timeout: int | float | None = None) -> None:
        """Waits for HTML body to be present.

        Block until an object the body element on the page is present,
        or the timeout expires. It is a convenience wrapper around
        `wait_element`, useful when a page spontaneously starts loading another
        url.

        Args:
            timeout: Maximum time, in seconds, to wait before raising a
                `TimeoutException`. Defaults to `None`. If `None`, it will take
                the value of the Page's default timeout instead.

        Raises:
            TimeoutException: if `timeout` is not `None`, this exception will
                be raised if the element could not be located before
                `timeout` has elapsed.
        """
        wait_timeout = timeout or self.default_timeout
        self._wait_element(Locator(By.TAG_NAME, "body"), wait_timeout)
