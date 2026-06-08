import os
from abc import abstractmethod
from enum import Enum
from logging import getLogger
from pathlib import Path
from typing import Protocol, override, runtime_checkable

logger = getLogger(__name__)


class PrintJobStatus(Enum):
    """Supported printing statuses.

    The purpose of this Enum Class is to allow different printing backends to
    signal in a uniform way the status of a print job.
    """

    SUCCESSFUL = "successful"
    PENDING = "pending"
    FAILED = "failed"


@runtime_checkable
class PrintingBackend(Protocol):
    """Abstract printing backend.

    This Protocol Class contains the minimum methods that every printing
    backend must expose.
    """

    def __init__(self, *args, **kwargs):
        super().__init__()

    @abstractmethod
    def get_default_printer(self) -> str:
        """Returns the default printer for the backend.

        Returns:
            str: A string that represents the default
            printer for the backend.
        """
        raise NotImplementedError

    @abstractmethod
    def list_printers(self) -> list[str]:
        """Returns a list of the printers available with the backend.

        Returns:
            list[str]: a list of strings each of which represents
                a printer available to the backend.
        """
        raise NotImplementedError

    @abstractmethod
    def print_file(
        self, path: Path, description: str | None, printer: str | None = None
    ) -> int:
        """Prints the file at `path` with the given `printer`.

        If `printer` is None, the default printer is used.

        Args:
            path: The path of the file to be printed

            description: A optional title for the job

            printer: A valid identifier for a printer available
                on this backend. If None, the default printer will be used.

        Returns:
            int: The Job Identifier for the particular printing
                job submitted.
        """
        raise NotImplementedError

    @abstractmethod
    def get_job_status(self, job_id: int) -> PrintJobStatus:
        """Returns the current PrintJobStatus of a given job.

        Args:
            job_id (int): the Job Identifier

        Returns:
            JobStatus: Either PrintJobStatus.SUCCESSFUL, PENDING OR
                FAILED. Will return PrintJobStatus.FAILED if there were
                issues while trying to get the status.
        """
        raise NotImplementedError

    @abstractmethod
    def cancel_job(self, job_id: int) -> bool:
        """Cancels a job.

        Args:
            job_id (int): the Job Identifier

        Returns:
            bool: True if the job was deleted without issues.
                False otherwise (i.e job not found).
        """
        raise NotImplementedError


class CupsPrintingBackend(PrintingBackend):
    """Provides printing capabilities by connecting to a CUPS instance.

    Requires setting CUPS_HOST and CUPS_PORT environment variables.

    Args:
        env_var_prefix: optional argument to specify a prefix for environmental
            variables. For example, if this argument is set to "TEST_", the
            class will search for environment variables "TEST_CUPS_HOST" and
            "TEST_CUPS_PORT" instead of just "CUPS_PORT" and "CUPS_HOST".
            Defaults to `None`.
    """

    def __init__(self, env_var_prefix: str | None = None):
        super().__init__()
        import cups

        self.cups = cups

        if not env_var_prefix:
            env_var_prefix = ""

        self.cups_host = os.getenv(f"{env_var_prefix}CUPS_HOST")
        self.cups_port = os.getenv(f"{env_var_prefix}CUPS_PORT")

        if not self.cups_host or not self.cups_port:
            raise ValueError(
                "Missing required environment variables for the CUPS backend: "
                "INVOICEMANAGER_CUPS_HOST and INVOICEMANAGER_CUPS_PORT"
            )

        self.cups_port = int(self.cups_port)
        self.cups.setServer(self.cups_host)
        self.cups.setPort(self.cups_port)
        self.connection = self.cups.Connection(self.cups_host, self.cups_port)

    @override
    def get_default_printer(self) -> str | None:
        return self.connection.getDefault()

    @override
    def list_printers(self) -> list[str]:
        return list(self.connection.getPrinters().keys())

    @override
    def print_file(
        self,
        path: Path,
        description: str | None = "",
        printer: str | None = None,
    ) -> int:
        if printer is None or printer not in self.list_printers():
            printer = self.get_default_printer()

        if not description:
            description = path.name

        file_path = str(path.absolute())
        return self.connection.printFile(printer, file_path, description, {})

    @override
    def get_job_status(self, job_id: int) -> PrintJobStatus:
        try:
            job_attributes = self.connection.getJobAttributes(job_id)
            job_state = job_attributes.get("job-state")
        except self.cups.IPPError as e:
            logger.error(
                f"[CUPS] Error while getting job status for job_id {job_id}; "
                f"assuming job was failed. Detailed error is: {e}"
            )
            return PrintJobStatus.FAILED

        # job_state 9 -> IPP_JOB_COMPLETED
        if job_state == 9:
            return PrintJobStatus.SUCCESSFUL

        return PrintJobStatus.PENDING

    @override
    def cancel_job(self, job_id: int) -> bool:
        try:
            self.connection.cancelJob(job_id)
            return True
        except self.cups.IPPError as e:
            logger.error(
                f"[CUPS] Error while cancelling job {job_id}; "
                f"assuming job was failed. Detailed error is: {e}"
            )
            return False


class FallbackPrintingBackend(PrintingBackend):
    """A mock fallback class.

    The FallbackPrintingBackend allows InvoiceManager to continue working
    without a truly working backend. Useful to store invoices without having to
    actually print them.
    """

    @override
    def get_default_printer(self) -> str | None:
        return "Fallback Printer"

    @override
    def list_printers(self) -> list[str]:
        return ["Fallback Printer"]

    @override
    def print_file(
        self,
        path: Path,
        description: str | None = None,
        printer: str | None = None,
    ) -> int:
        return 0

    @override
    def get_job_status(self, job_id: int) -> PrintJobStatus:
        return PrintJobStatus.SUCCESSFUL

    @override
    def cancel_job(self, job_id: int) -> bool:
        return True


AVAILABLE_BACKENDS = {
    "CUPS": CupsPrintingBackend,
    "Fallback": FallbackPrintingBackend,
    "": FallbackPrintingBackend,
}
