from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from aow_client.types import InvoiceResponse
from invoice_manager.model import Invoice
from invoice_manager.printing import PrintJobStatus

# Test init


def test_init_creates_working_directories(manager, manager_config):
    assert manager_config.download_dir.exists()
    assert manager_config.confirmed_dir.exists()


def test_init_reads_client_doc_metadata(manager):
    assert manager.doc_prefix == "IT"
    assert manager.doc_suffix == ".pdf"


# Test queries


def test_invoices_to_download_returns_only_not_downloaded(
    manager, make_invoice
):
    b1 = make_invoice(31, downloaded=False)
    b2 = make_invoice(32, downloaded=True)

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add_all([b1, b2])
        session.commit()

    output = manager.invoices_to_download()

    assert [b.id for b in output] == [31]


def test_invoices_to_print_returns_downloaded_not_printed_with_no_job(
    manager, make_invoice
):
    b1 = make_invoice(33, downloaded=True, printed=False, job_id=None)
    b2 = make_invoice(34, downloaded=True, printed=True, job_id=None)
    b3 = make_invoice(35, downloaded=True, printed=False, job_id="900")

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add_all([b1, b2, b3])
        session.commit()

    output = manager.invoices_to_print()

    assert [b.id for b in output] == [33]


def test_invoices_to_confirm_returns_printed_not_confirmed(
    manager, make_invoice
):
    b1 = make_invoice(36, downloaded=True, printed=True, confirmed=False)
    b2 = make_invoice(37, downloaded=True, printed=True, confirmed=True)
    b3 = make_invoice(38, downloaded=True, printed=False, confirmed=False)

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add_all([b1, b2, b3])
        session.commit()

    output = manager.invoices_to_confirm()

    assert [b.id for b in output] == [36]


# Test Fetch


def test_fetch_new_invoices_inserts_only_new_records(
    manager, fake_client, make_invoice
):
    existing_invoice = make_invoice(1)
    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(existing_invoice)
        session.commit()

    fake_client.fetch_invoices_result = [
        InvoiceResponse(
            id=1,
            seac_code="SEAC1",
            sender_name="Sender A",
            creation_date=date(2024, 1, 1),
            reception_date=date(2024, 1, 2),
            amount=Decimal("100.00"),
        ),
        InvoiceResponse(
            id=2,
            seac_code="SEAC2",
            sender_name="Sender B",
            creation_date=date(2024, 1, 3),
            reception_date=date(2024, 1, 4),
            amount=Decimal("200.00"),
        ),
    ]

    inserted = manager.fetch_new_invoices()

    assert [b.id for b in inserted] == [2]

    with Session() as session:
        all_invoices = session.query(Invoice).order_by(Invoice.id.asc()).all()
        assert [b.id for b in all_invoices] == [1, 2]


def test_download_with_none_downloads_pending_invoices(
    manager, fake_client, make_invoice
):
    b1 = make_invoice(1)
    b2 = make_invoice(2)

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add_all([b1, b2])
        session.commit()

    fake_client.download_result = {b1: True, b2: False}

    result = manager.download()

    assert result[b1] is True
    assert result[b2] is False

    with Session() as session:
        db_b1 = session.get(type(b1), b1.id)
        db_b2 = session.get(type(b2), b2.id)
        assert db_b1.downloaded is True
        assert db_b2.downloaded is False


def test_download_single_invoice_coerces_to_list(
    manager, fake_client, make_invoice
):
    b1 = make_invoice(10)
    fake_client.download_result = {b1: True}

    output = manager.download(b1)

    assert output[b1] is True


def test_download_empty_list_returns_empty_dict(manager):
    output = manager.download([])
    assert output == {}


# Printing


def test_print_sets_job_id_when_file_exists(
    manager, fake_printing_backend, make_invoice
):
    invoice = make_invoice(11, downloaded=True)
    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(invoice)
        session.commit()

    file_path = (
        manager.download_dir
        / f"{manager.doc_prefix}{invoice.id}{manager.doc_suffix}"
    )
    file_path.write_text("fake-pdf")

    manager.print([invoice], printer="Office Printer")

    with Session() as session:
        refreshed = session.get(type(invoice), invoice.id)
        assert refreshed.job_id is not None
        assert refreshed.last_print is not None

    assert len(fake_printing_backend.printed_files) == 1


def test_print_marks_invoice_not_downloaded_if_file_missing(
    manager, fake_printing_backend, make_invoice
):
    invoice = make_invoice(12, downloaded=True)
    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(invoice)
        session.commit()

    manager.print([invoice])

    with Session() as session:
        refreshed = session.get(type(invoice), invoice.id)
        assert refreshed.downloaded is False
        assert refreshed.job_id is None

    assert fake_printing_backend.printed_files == []


def test_update_ongoing_prints_marks_successful_jobs_as_printed(
    manager, fake_printing_backend, make_invoice
):
    invoice = make_invoice(13, downloaded=True, printed=False, job_id="101")

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(invoice)
        session.commit()

    fake_printing_backend.jobs[101] = PrintJobStatus.SUCCESSFUL

    successful, failed = manager.update_ongoing_prints()

    assert [b.id for b in successful] == [13]
    assert failed == []

    with Session() as session:
        refreshed = session.get(type(invoice), invoice.id)
        assert refreshed.printed is True
        assert refreshed.job_id is None
        assert refreshed.print_tries == 1


def test_update_ongoing_prints_cancels_timed_out_jobs(
    manager, fake_printing_backend, make_invoice
):
    old = datetime.now() - timedelta(minutes=40)
    invoice = make_invoice(
        14, downloaded=True, printed=False, job_id="102", last_print=old
    )

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(invoice)
        session.commit()

    fake_printing_backend.jobs[102] = PrintJobStatus.PENDING

    successful, failed = manager.update_ongoing_prints()

    assert successful == []
    assert [b.id for b in failed] == [14]
    assert fake_printing_backend.cancelled_jobs == [102]

    with Session() as session:
        refreshed = session.get(type(invoice), invoice.id)
        assert refreshed.printed is False
        assert refreshed.job_id is None
        assert refreshed.print_tries == 1


# Confirmation


def test_schedule_for_reprint_resets_flags_and_increments_tries(
    manager, make_invoice
):
    invoice = make_invoice(
        21, downloaded=True, printed=True, confirmed=True, print_tries=0
    )

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(invoice)
        session.commit()

    updated = manager.schedule_for_reprint([invoice])

    assert [b.id for b in updated] == [21]

    with Session() as session:
        refreshed = session.get(type(invoice), invoice.id)
        assert refreshed.confirmed is False
        assert refreshed.printed is False
        assert refreshed.print_tries == 1


def test_confirm_marks_invoice_confirmed_and_moves_file(manager, make_invoice):
    invoice = make_invoice(22, downloaded=True, printed=True, confirmed=False)

    Session = sessionmaker(bind=manager.db_engine, expire_on_commit=False)
    with Session() as session:
        session.add(invoice)
        session.commit()

    source = (
        manager.download_dir
        / f"{manager.doc_prefix}{invoice.id}{manager.doc_suffix}"
    )
    source.write_text("fake-pdf")

    updated = manager.confirm([invoice])

    assert [b.id for b in updated] == [22]

    with Session() as session:
        refreshed = session.get(type(invoice), invoice.id)
        assert refreshed.confirmed is True

    destination = manager.confirmed_dir / source.name
    assert destination.exists()
    assert not source.exists()
