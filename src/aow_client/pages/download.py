import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from logging import getLogger

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from aow_client.pages.base import BasePage, Locator
from aow_client.types import InvoiceLike, InvoiceResponse

logger = getLogger(__name__)


class DownloadPage(BasePage):
    """Page representing the Download Page for received invoices.

    In this page, there is a form that allows to search and filter received
    invoices. In the results table, every row is an invoice that satisfies the
    given filters. In that row, the basic information of the invoice (such as
    the sender, the amount, the creation and reception dates) are available
    along a download button. Other buttons and actions are available too, but
    not supported so far, as they are unneeded. Some information, like the
    unique invoice ID, is available in the HTML document, but not displayed on
    screen.

    This class acts as an API to interact with the webpage, supporting simple
    methods to search for and download invoices.
    """

    DOWNLOAD_BUTTON = Locator(
        By.XPATH, "//a[contains(@class, 'download-pdf')]"
    )
    ATTACHMENTS_CLOSE_BUTTON = Locator(
        By.XPATH,
        "//div[@class='modal-content'][div[@id='modalAllegatiContentId']]"
        "//button[@class='close']",
    )
    SHOW_STATUS_SELECT = Locator(
        By.CSS_SELECTOR, "div#statoLetturaSelectBoxId"
    )
    DROPDOWN_CHOICE = Locator(By.CSS_SELECTOR, "div.dx-list-item-content")
    INVOICE_ID_FIELD = Locator(By.CSS_SELECTOR, "input#idSDIInputFieldName")
    UPDATE_BUTTON = Locator(By.CSS_SELECTOR, "button#aggiornaButtonId")
    PAGE_SIZE_SELECT = Locator(
        By.CSS_SELECTOR, "select.seac-dx-page-selector-select"
    )
    LOADING_SPINNER = Locator(
        By.XPATH,
        (
            "//div[@id='gridId']"
            "//div[@role='grid' and"
            " contains(@class, 'dx-datagrid')]"
            "//div[contains(@class, 'dx-overlay') and"
            " contains(@class, 'dx-widget') and"
            " contains(@class, 'dx-visibility-change-handler') and"
            " contains(@class, 'dx-loadpanel')]"
        ),
    )
    LOADING_SPINNER_INVISIBLE = Locator(
        By.XPATH,
        "//div[@id='gridId']"
        "//div[@role='grid' and"
        " contains(@class, 'dx-datagrid')]"
        "//div[contains(@class, 'dx-overlay') and"
        " contains(@class, 'dx-widget') and"
        " contains(@class, 'dx-visibility-change-handler') and"
        " contains(@class, 'dx-loadpanel') and"
        " contains(@class, 'dx-state-invisible')]",
    )

    def __init__(self, driver, url: str):
        super().__init__(driver, url)

    @staticmethod
    def parse_amount(value: str) -> Decimal:
        """Parse the amount string of an invoice into a Decimal.

        These strings are obtained in the table of the invoice search results.

        Due to localization, it is first necessary to remove Italian-style
        thousand separators (dots '.') and substitute the comma decimal
        separators with dots.


        Args:
            value: The amount string as displayed on the invoice search results
                table.

        Raises:
            ValueError: Raised when the string could not be converted to
                Decimal.

        Returns:
            Decimal: The amount represented by the string, encoded as Decimal
                to ensure no loss of precision.
        """
        normalized = value.strip().replace(".", "").replace(",", ".")
        if normalized.endswith("€"):
            normalized = normalized[:-1]
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid amount value: {value!r}") from exc

    @staticmethod
    def parse_date(value: str) -> date:
        """Parses the date string of an invoice into a date object.

        These strings are obtained in the table of the invoice search results.

        Args:
            value (str): The date string as displayed on the invoice search
                results table.

        Returns:
            date: The date represented by the string, encoded as date object.
        """
        return date(*(int(part) for part in value.split("/")[::-1]))

    def _create_invoice_from_button(self, button) -> InvoiceResponse:
        invoice_id = int(button.get_attribute("href").split("#")[-1])
        invoice_row = button.find_element(By.XPATH, ".//ancestor::tr")
        invoice_columns = invoice_row.find_elements(By.XPATH, ".//child::td")
        invoice_data = [e.text for e in invoice_columns]
        data = {
            "id": int(invoice_data[2]),
            "seac_code": invoice_data[3],
            "sender_name": invoice_data[1].split("\n")[0],
            "creation_date": self.parse_date(invoice_data[5]),
            "reception_date": self.parse_date(invoice_data[7]),
            "amount": self.parse_amount(invoice_data[6]),
        }
        if invoice_id != data["id"]:
            logger.error(
                f"Mismatch in document ID ({invoice_id}->{data['id']}) "
                "while downloading. Something must have gone wrong."
            )
        b = InvoiceResponse(**data)
        return b

    def fetch_invoices(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        new_only: bool = False,
    ) -> list[InvoiceResponse]:
        """Find invoices in a certain time period.

        The method can filter for invoices to be either new, or both new and
        already downloaded/read. Once an invoice is downloaded, AziendaOnWeb
        marks it as read automatically.

        Args:
            start_date: Invoices older than this date will not be listed. If
                `None`, it will automatically get invoices starting from the
                1st of the previous month. Defaults to `None`.
            end_date: Invoices newer than this date will not be listed. If
                `None`, it will automatically default to the current day.
                Defaults to None.
            new_only: If True, only new (yet to download) Invoices will be
                listed. Defaults to False.

        Returns:
            list[InvoiceResponse]: A list of the retrieved Invoices
        """
        self._load_invoice_list(
            start_date=start_date, end_date=end_date, new_only=new_only
        )
        try:
            self._wait_element(self.DOWNLOAD_BUTTON, 10)
        except TimeoutException:
            logger.error("Could not obtain the invoice list in time.")
            return []

        download_buttons = self.find_elements(self.DOWNLOAD_BUTTON)
        invoices = []
        for button in download_buttons:
            self.wait_element_clickable(button)
            invoices.append(self._create_invoice_from_button(button))
            logger.info(f"Found a invoice: {invoices[-1]}")
        return invoices

    @property
    def _is_attachments_popup_visible(
        self,
    ) -> tuple[bool, tuple[str, str] | None]:
        try:
            attachments_close_button = self.wait_element_visible(
                self.ATTACHMENTS_CLOSE_BUTTON, 1
            )
            return True, attachments_close_button
        except TimeoutException:
            return False, None

    @property
    def on_invoice_list(self) -> bool:
        """Checks if the title contains words specific to this page.

        Although a better check could be implemented, this is extremely fast
        and, so far, effective enough to fullfill its purpose.

        Returns:
            bool: `True` if the driver is currently on the Search and
                Download Page for received invoices, `False` otherwise.
        """
        return (
            "documenti" in self.driver.title
            and "ricevuti" in self.driver.title
        )

    def _download_from_button(self, button) -> bool:
        button.click()
        download_pdf_dropdowns = self.find_elements(
            Locator(
                By.XPATH,
                (
                    "//a[@class='dropdown-item']"
                    "[contains(text(), 'PDF elettronico')]"
                ),
            )
        )
        found = False
        for pdf_dropdown in download_pdf_dropdowns:
            if pdf_dropdown.text != "PDF elettronico":
                continue
            pdf_dropdown.click()
            time.sleep(3)  # Give time for the download
            found = True
            # Wait for a popup for additional documents to appear
            # If it does, close it. Otherwise, proceed to the next.
            popup_visible, close_button = self._is_attachments_popup_visible
            if popup_visible:
                logger.info("Attachments popup detected, clicking on 'Close'.")
                ActionChains(self.driver).move_to_element(close_button).click(
                    close_button
                ).perform()
        return found

    def _load_invoice_list(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        new_only: bool = False,
        invoice_id: int | None = None,
    ) -> bool:
        if (
            end_date is not None
            and start_date is not None
            and end_date < start_date
        ):
            raise ValueError("End date cannot be before start date.")

        if end_date is None:
            end_date = date.today()

        if start_date is None:
            # Load the list of invoices up to the 1st day of the previous
            # month.
            today = date.today()
            start_date = today - timedelta(days=today.day) - timedelta(days=30)
            logger.info(
                f"Loading invoices starting from {start_date.isoformat()}"
            )
            self.driver.get(
                f"{self.url}?dataDa={start_date.isoformat()}&dataA={end_date.isoformat()}"
            )
        else:
            self.driver.get(
                f"{self.url}?dataDa={start_date.isoformat()}&dataA={end_date.isoformat()}"
            )
        # Get the current "show" state of the invoice list.
        # The possible states are "All", "New" and "Old".
        current_show_state = "All"
        show_status_div = self.find_element(self.SHOW_STATUS_SELECT)
        show_all_div = show_status_div.find_element(
            By.XPATH, ".//child::div[@data-dx_placeholder='Tutti']"
        )
        show_all_div_classes = show_all_div.get_attribute("class").split()
        if "dx-state-invisible" in show_all_div_classes:
            show_status_input = show_status_div.find_element(
                By.XPATH,
                ".//child::input[contains(@class, 'dx-texteditor-input')]",
            )
            show_status_input_value = show_status_input.get_attribute("value")
            if show_status_input_value == "Letto":
                current_show_state = "Old"
            elif show_status_input_value == "Non letto":
                current_show_state = "New"

        dropdown_button = show_status_div.find_element(
            By.XPATH,
            ".//child::div[contains(@class, 'dx-dropdowneditor-button')]",
        )

        if new_only and current_show_state != "New":
            dropdown_button.click()
            self._wait_element(self.DROPDOWN_CHOICE, timeout=2)

            dropdown_choices = self.find_elements(self.DROPDOWN_CHOICE)
            # Index 1 is the "Non letto" element of the dropdown selector
            # index 0 for "Letto" instead
            dropdown_choices[1].click()
        elif not new_only and current_show_state != "All":
            clear_button = show_status_div.find_element(
                By.XPATH,
                ".//child::span[contains(@class, 'dx-clear-button-area')]",
            )
            clear_button.click()

        if invoice_id is not None:
            invoice_id_field = self._wait_element(self.INVOICE_ID_FIELD)
            invoice_id_field.send_keys(Keys.CONTROL + "a")
            invoice_id_field.send_keys(Keys.DELETE)
            invoice_id_field.send_keys(str(invoice_id))

        # Update the invoice list by clicking on the "Aggiorna" button
        update_button = self.find_element(self.UPDATE_BUTTON)
        (
            ActionChains(self.driver)
            .move_to_element(update_button)
            .click(update_button)
            .perform()
        )
        self.find_elements(self.LOADING_SPINNER)
        self._wait_element(self.LOADING_SPINNER_INVISIBLE)
        try:
            elements_per_page_select = self._wait_element(
                self.PAGE_SIZE_SELECT
            )
            Select(elements_per_page_select).select_by_value("1000")
            return True
        except NoSuchElementException:
            logger.error(
                "Could not set the invoice list to display 1000 "
                "elements per page. The system should still work, "
                "but older documents might not be getting downloaded."
            )
            return False

    def download_invoices(
        self, invoices: InvoiceLike | list[InvoiceLike]
    ) -> list[bool]:
        """Automatically interacts to download one or more invoices.

        Args:
            invoices: An invoice or list of invoices to download.
                InvoiceResponses returned by `fetch_invoices` are a valid
                input.

        Returns:
            list[bool]: A list exactly as long as the input list (one, if one
                `InvoiceLike` was passed instead of a list), where every item
                is `True` if the invoice has been downloaded successfully or
                `False` otherwise. The items are in the same order as in the
                input list.
        """
        if isinstance(invoices, InvoiceLike):
            invoices = [invoices]

        downloaded = []
        for b in invoices:
            downloaded.append(False)
            try:
                loaded = self._load_invoice_list(
                    start_date=b.reception_date, invoice_id=b.id
                )
                if not loaded:
                    logger.error(
                        f"Could not load the invoice list for invoice {b.id}"
                    )
                    continue
            except TimeoutException as e:
                logger.error(
                    "An timeout occurred while loading the invoice list "
                    f"for invoice {b.id}: {e}"
                )
                continue

            try:
                self._wait_element(self.DOWNLOAD_BUTTON, timeout=5)
            except TimeoutException:
                logger.error(
                    "Could not find the invoice download button "
                    f"for invoice {b.id}"
                )
                continue

            self.wait_element_clickable(self.DOWNLOAD_BUTTON, 5)
            download_buttons = self.find_elements(self.DOWNLOAD_BUTTON)
            for button in download_buttons:
                # self.wait_element_clickable(button)
                # There was a procedure creating invoices from buttons
                # but i do not see why that was necessary. This
                # should just download the files. I think it was a way
                # to further
                #
                # There was a retry. Hopefully it is not necessary anymore
                # due to better handling of loading procedures.
                #
                #
                # Retry a few times to create the invoice from the button, as
                # sometimes the page might hang and some elements might not be
                #    interactable yet. try:
                # self._create_invoice_from_button(button) except Exception as
                #    e: logger.error( f"An error occurred while creating
                #        invoice from button for invoice {b.invoice_id}: {e}" )
                downloaded[-1] = self._download_from_button(button)
        return downloaded
