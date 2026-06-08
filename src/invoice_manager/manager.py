import datetime
from logging import getLogger

from sqlalchemy.orm import sessionmaker

from aow_client import AziendaOnWebClient
from invoice_manager.config import InvoiceManagerConfig
from invoice_manager.model import Invoice
from invoice_manager.printing import PrintJobStatus

logger = getLogger(__name__)

# TODO Improve logging


class InvoiceManager:
    """Coordinates invoice synchronization and local processing.

    This class acts as the application-facing service layer for invoice
    operations. It persists invoices, tracks print state transitions, and
    delegates remote I/O to the web client and printing backend.
    """

    def __init__(
        self, client: AziendaOnWebClient, config: InvoiceManagerConfig
    ):
        self.client = client
        self.db_engine = config.db_engine
        self.db = sessionmaker(bind=self.db_engine, expire_on_commit=False)
        self.printing_backend = config.printing_backend
        self.doc_prefix = client.DOC_PREFIX
        self.doc_suffix = client.DOC_SUFFIX
        self.download_dir = config.download_dir
        self.confirmed_dir = config.confirmed_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.confirmed_dir.mkdir(parents=True, exist_ok=True)
        self.print_timeout_minutes = config.print_timeout_minutes
        self.print_retries_limit = config.print_retries_limit
        self.config = config

    def fetch_new_invoices(self) -> list[Invoice]:
        """Fetch unseen invoices from the provider and persist them.

        The method requests invoices marked as new by the remote service,
        stores only those not already present in the local database, and
        returns the inserted records.

        Returns:
            list[Invoice]: Newly inserted invoices.
        """
        # Optionally, one could instead get all the
        # invoices in the last month to be doubly sure
        web_new_invoices = []
        with self.client as client:
            web_new_invoices = client.fetch_invoices(new_only=True)
        new_invoices = []
        with self.db() as session:
            for invoice in web_new_invoices:
                if session.get(Invoice, invoice.id) is None:
                    new_invoice = Invoice.from_invoice_response(invoice)
                    session.add(new_invoice)
                    new_invoices.append(new_invoice)
            session.commit()
        return new_invoices

    def download(
        self, invoices: None | Invoice | list[Invoice] = None
    ) -> dict[Invoice, bool]:
        """Downloads one or more Invoice(s).

        Args:
            invoices: A single Invoice or list of Invoice objects to download.
                If None, automatically downloads all (new) missing invoices.

        Returns:
            List of invoices successfully downloaded.
        """
        if invoices is None:
            to_download = self.invoices_to_download()
        elif isinstance(invoices, Invoice):
            to_download = [invoices]
        else:
            to_download = invoices

        if len(to_download) == 0:
            return {}

        with self.client as client:
            downloaded_list = client.download_invoices(to_download)
        for invoice, downloaded in downloaded_list.items():
            invoice.downloaded = downloaded

        output_dict = {}
        with self.db() as session:
            for invoice in downloaded_list.keys():
                invoice = session.merge(invoice)
                output_dict[invoice] = invoice.downloaded
            session.commit()

        return output_dict

    def query_invoices(self, filter_dict: dict) -> list[Invoice]:
        """Query invoices using ``Session.query(...).filter_by``.

        Args:
            filter_dict: Keyword arguments passed to SQLAlchemy ``filter_by``.

        Returns:
            list[Invoice]: Matching invoice rows.
        """
        invoices = []
        with self.db() as session:
            invoices = session.query(Invoice).filter_by(**filter_dict).all()
            session.commit()
        return invoices

    @property
    def available_printers(self) -> list[str]:
        """List printers exposed by the configured backend.

        Returns:
            list[str]: Printer identifiers available for print jobs.
        """
        return self.printing_backend.list_printers()

    def print(
        self, invoices: None | Invoice | list[Invoice] = None, printer=None
    ) -> None:
        """Submit invoices for printing and persist print job metadata.

        Missing files are marked as not downloaded so they can be fetched
        again later. Successfully submitted jobs store their job id and
        last print timestamp.

        Args:
            invoices: A single invoice, a list of invoices, or ``None`` to
                print all pending invoices.
            printer: Optional printer identifier for the backend.

        Returns:
            None
        """
        if invoices is None:
            invoices = self.invoices_to_print()

        if isinstance(invoices, Invoice):
            invoices = [invoices]

        with self.db() as session:
            for b in invoices:
                b = session.merge(b)
                file_path = (
                    self.download_dir
                    / f"{self.doc_prefix}{b.id}{self.doc_suffix}"
                )
                if not file_path.exists():
                    # Mark the file as not downloaded to attempt redownload
                    b.downloaded = False
                    logger.warning(
                        f"File {file_path} does not exist, even though the "
                        "invoice was marked as downloaded. Scheduling for "
                        "download again."
                    )
                    continue
                job_id = self.printing_backend.print_file(
                    file_path, f"Invoice {b.id}", printer
                )
                b.job_id = job_id
                b.last_print = datetime.datetime.now()
            session.commit()

    def update_ongoing_prints(self) -> tuple[list[Invoice], list[Invoice]]:
        """Reconcile ongoing print jobs with backend job state.

        Pending jobs are checked against the printing backend. Completed
        jobs are marked printed, while timed-out jobs are marked failed and
        optionally reset for redownload after retry limits are exceeded.

        Returns:
            tuple[list[Invoice], list[Invoice]]: A pair containing
            successful invoices first and failed invoices second.
        """
        if self.print_timeout_minutes == 0:
            print_timeout_timestamp = None
        else:
            print_timeout_timestamp = (
                datetime.datetime.now()
                - datetime.timedelta(minutes=self.print_timeout_minutes)
            )

        ongoing_prints = []
        with self.db() as session:
            ongoing_prints = (
                session.query(Invoice)
                .filter(
                    Invoice.downloaded,
                    ~Invoice.printed,
                    Invoice.job_id.is_not(None),
                )
                .all()
            )

        successful_invoices = []
        failed_invoices = []
        for b in ongoing_prints:
            job_status = self.printing_backend.get_job_status(int(b.job_id))

            if job_status == PrintJobStatus.SUCCESSFUL:
                successful_invoices.append(b)
            elif (
                b.last_print is not None
                and print_timeout_timestamp is not None
                and b.last_print < print_timeout_timestamp
            ):
                failed_invoices.append(b)
                self.printing_backend.cancel_job(int(b.job_id))

        with self.db() as session:
            for i in range(len(successful_invoices)):
                invoice = successful_invoices[i]
                invoice.job_id = None
                invoice.print_tries += 1
                invoice.printed = True
                invoice = session.merge(invoice)
                successful_invoices[i] = invoice

            for i in range(len(failed_invoices)):
                invoice = failed_invoices[i]
                invoice.job_id = None
                invoice.print_tries += 1
                invoice.printed = False

                if (
                    self.print_retries_limit > 0
                    and invoice.print_tries > self.print_retries_limit
                ):
                    # Maybe the file is corrupt?
                    # Try to re-download the file.
                    invoice.print_tries = 0
                    invoice.downloaded = False
                    file_path = (
                        self.download_dir
                        / f"{self.doc_prefix}{invoice.id}{self.doc_suffix}"
                    )
                    if file_path.exists():
                        file_path.unlink()

                invoice = session.merge(invoice)
                failed_invoices[i] = invoice
            session.commit()

        return successful_invoices, failed_invoices

    def schedule_for_reprint(
        self, invoices: Invoice | list[Invoice]
    ) -> list[Invoice]:
        """Mark invoices so they will be included in future print runs.

        The method clears confirmation and printed flags and increments
        print attempts before persisting the updated invoice rows.

        Args:
            invoices: A single invoice or list of invoices to reschedule.

        Returns:
            list[Invoice]: Updated invoices after merge into the session.
        """
        if isinstance(invoices, Invoice):
            invoices = [invoices]
        unconfirmed_invoices = []
        for b in invoices:
            b.confirmed = False
            b.printed = False
            b.print_tries += 1
            unconfirmed_invoices.append(b)

        with self.db() as session:
            for i in range(len(unconfirmed_invoices)):
                unconfirmed_invoices[i] = session.merge(
                    unconfirmed_invoices[i]
                )
            session.commit()

        return unconfirmed_invoices

    def confirm(self, invoices: Invoice | list[Invoice]) -> list[Invoice]:
        """Confirm invoices and move their files to the confirmed directory.

        Each confirmed invoice is marked in the database. When the
        downloaded file is found, it is moved from the download directory
        to the confirmed directory.

        Args:
            invoices: A single invoice or list of invoices to confirm.

        Returns:
            list[Invoice]: Updated confirmed invoices.
        """
        if isinstance(invoices, Invoice):
            invoices = [invoices]

        confirmed_invoices = []
        for b in invoices:
            b.confirmed = True
            confirmed_invoices.append(b)
            downloaded_file = (
                self.download_dir / f"{self.doc_prefix}{b.id}{self.doc_suffix}"
            )
            confirmed_file = self.confirmed_dir / downloaded_file.name
            if downloaded_file.exists():
                downloaded_file.rename(confirmed_file)
                logger.info(
                    f"Invoice {b.id} confirmed. File "
                    f"{downloaded_file.absolute()} has been moved to "
                    f"{self.confirmed_dir.absolute()}"
                )
            else:
                logger.warning(
                    f"Invoice {b.id} confirmed, however the downloaded "
                    f"file {downloaded_file.absolute()} was not found."
                )

        with self.db() as session:
            for i in range(len(confirmed_invoices)):
                confirmed_invoices[i] = session.merge(confirmed_invoices[i])
            session.commit()

        return confirmed_invoices

    def invoices_to_download(self) -> list[Invoice]:
        """Return invoices that are not downloaded yet.

        Returns:
            list[Invoice]: Invoices with ``downloaded == False``.
        """
        return self.query_invoices({"downloaded": False})

    def invoices_to_print(self):
        """Return downloaded invoices still waiting to be printed.

        Before querying, ongoing print jobs are reconciled so stale states
        do not appear as printable.

        Returns:
            list[Invoice]: Downloaded invoices with no active print job.
        """
        self.update_ongoing_prints()
        return self.query_invoices(
            {"downloaded": True, "printed": False, "job_id": None}
        )

    def invoices_to_confirm(self) -> list[Invoice]:
        """Return printed invoices that are not confirmed yet.

        Returns:
            list[Invoice]: Printed invoices with ``confirmed == False``.
        """
        return self.query_invoices(
            {"downloaded": True, "printed": True, "confirmed": False}
        )
