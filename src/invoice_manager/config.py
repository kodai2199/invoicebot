import os
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine

from invoice_manager.model import get_engine
from invoice_manager.printing import (
    AVAILABLE_BACKENDS,
    FallbackPrintingBackend,
    PrintingBackend,
)

logger = getLogger(__name__)


@dataclass(slots=True)
class InvoiceManagerConfig:
    """Configuration for the InvoiceManager."""

    db_engine: Engine
    printing_backend: PrintingBackend
    download_dir: Path = Path("./invoices/downloaded")
    confirmed_dir: Path = Path("./invoices/confirmed")
    print_timeout_minutes: int = 30
    print_retries_limit: int = 0


class InvoiceManagerConfigBuilder:
    """Builder for InvoiceManagerConfig using environment variables."""

    @staticmethod
    def from_env(env_path: Path | None = None) -> InvoiceManagerConfig:
        """Build InvoiceManagerConfig from environment variables.

        Environment variables:
            - INVOICEMANAGER_DATABASE_STRING: database string for SQLAlchemy
              (required)
            - INVOICEMANAGER_DOWNLOADED_DIR: Directory where downloaded
              invoices are found (default: ./invoices/downloaded)
            - INVOICEMANAGER_CONFIRMED_DIR: Directory to store invoices after
              confirming (default: ./invoices/confirmed)
            - INVOICEMANAGER_PRINTING_TIMEOUT_MINUTES: Timeout in minutes after
              which a print job will be considered failed even though it
              appears to be still pending. 0 to disable. (default: 30)
            - INVOICEMANAGER_PRINTING_BACKEND: Which backend to use for
              printing. Natively, only CUPS is supported. If None, or a non
              valid backend is specified, a fallback backend will be used,
              which will allow InvoiceManager to work just as a storage
              solution.
            - INVOICEMANAGER_PRINTING_TRIES_LIMIT: Number of failed print tries
              after which redownload will be attempted with the hope of fixing
              a corrupted file. 0 or not set to disable. (default: 0)


        Refer to the selected printing backend for additional required
        environment variables to configure it (for example,
        INVOICEMANAGER_CUPS_HOST and INVOICEMANAGER_CUPS_PORT, when using CUPS)

        Args:
            env_path: Path to the environment file
                (default: .env).

        Returns:
            InvoiceManagerConfig instance.

        Raises:
            ValueError: If required environment variables are missing.
        """
        env_path = env_path or Path(
            os.getenv("INVOICEMANAGER_ENV_PATH", ".env")
        )
        load_dotenv(env_path)

        database_string = os.getenv("INVOICEMANAGER_DATABASE_STRING")

        if not database_string:
            raise ValueError(
                "Missing required environment variables: "
                "INVOICEMANAGER_DATABASE_STRING"
            )

        download_dir = os.getenv("INVOICEMANAGER_DOWNLOADED_DIR", None)
        if not download_dir:
            download_dir = Path("./invoices/downloaded")
        else:
            download_dir = Path(download_dir)

        confirmed_dir = os.getenv("INVOICEMANAGER_CONFIRMED_DIR", None)
        if not confirmed_dir:
            confirmed_dir = Path("./invoices/confirmed")
        else:
            confirmed_dir = Path(confirmed_dir)

        print_timeout_minutes = int(
            os.getenv("INVOICEMANAGER_PRINTING_TIMEOUT_MINUTES", "30")
        )
        print_retries_limit = int(
            os.getenv("INVOICEMANAGER_PRINTING_TRIES_LIMIT", "0")
        )
        printing_backend_str = os.getenv(
            "INVOICEMANAGER_PRINTING_BACKEND", "Fallback"
        )

        # Try to instantiate printing backend
        try:
            printing_backend = AVAILABLE_BACKENDS.get(
                printing_backend_str, FallbackPrintingBackend
            )
            printing_backend = printing_backend(
                env_var_prefix="INVOICEMANAGER_"
            )
        except Exception as e:
            logger.error(
                "Exception while trying to load the selected PrintingBackend "
                f"{printing_backend_str}. Fallback Backend will be used "
                f"instead. Exception was: {e}"
            )
            printing_backend = FallbackPrintingBackend()

        db_engine = get_engine(database_string)

        return InvoiceManagerConfig(
            db_engine=db_engine,
            download_dir=download_dir,
            confirmed_dir=confirmed_dir,
            printing_backend=printing_backend,
            print_timeout_minutes=print_timeout_minutes,
            print_retries_limit=print_retries_limit,
        )
