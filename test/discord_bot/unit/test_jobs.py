import asyncio
from unittest.mock import AsyncMock

import pytest

from discord_bot.enums import JobType
from discord_bot.jobs import Job, JobRunner, JobTracker


@pytest.mark.asyncio
async def test_job_tracker_is_busy_and_status_line():
    tracker = JobTracker()
    assert tracker.is_busy is False
    assert tracker.current_status_line() is None

    tracker.current_job_type = JobType.DOWNLOAD_INVOICES
    assert tracker.is_busy is True
    assert "Running" in tracker.current_status_line()


@pytest.mark.asyncio
async def test_enqueue_updates_queue_and_notifies(
    fake_invoice_manager, fake_logger
):
    tracker = JobTracker()
    callback = AsyncMock()
    runner = JobRunner(fake_invoice_manager, fake_logger, tracker, callback)

    job_id = await runner.enqueue(Job(JobType.DOWNLOAD_INVOICES))

    assert runner.queue_size == 1
    assert tracker.queue_size == 1
    assert isinstance(job_id, str)
    callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_is_idempotent(fake_invoice_manager, fake_logger):
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())
    runner._run = AsyncMock()

    await runner.start()
    task = runner._worker_task
    await runner.start()

    assert runner._worker_task is task
    runner._worker_task.cancel()


@pytest.mark.asyncio
async def test_stop_cancels_worker(fake_invoice_manager, fake_logger):
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())

    async def never_end():
        await asyncio.Future()

    runner._worker_task = asyncio.create_task(never_end())
    await runner.stop()

    assert runner._worker_task is None


@pytest.mark.asyncio
async def test_execute_unknown_handler_logs_warning(
    fake_invoice_manager, fake_logger
):
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())
    fake_logger.warning = AsyncMock()
    del runner._handlers[JobType.FETCH_PRINTERS]

    result = await runner._execute(Job(JobType.FETCH_PRINTERS))

    assert result is None
    fake_logger.warning.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_success_sets_future_result(
    fake_invoice_manager, fake_logger
):
    tracker = JobTracker()
    runner = JobRunner(fake_invoice_manager, fake_logger, tracker)
    future = asyncio.get_running_loop().create_future()
    runner.download_invoices_job = AsyncMock(return_value=["ok"])
    runner._handlers[JobType.DOWNLOAD_INVOICES] = runner.download_invoices_job

    await runner.enqueue(Job(JobType.DOWNLOAD_INVOICES, future=future))
    task = asyncio.create_task(runner._run())
    await asyncio.wait_for(future, timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert future.result() == ["ok"]
    assert tracker.current_job_type is None
    assert tracker.last_error is None


@pytest.mark.asyncio
async def test_run_failure_sets_future_exception(
    fake_invoice_manager, fake_logger
):
    tracker = JobTracker()
    runner = JobRunner(fake_invoice_manager, fake_logger, tracker)
    future = asyncio.get_running_loop().create_future()

    async def fail(_job):
        raise RuntimeError("boom")

    runner._handlers[JobType.DOWNLOAD_INVOICES] = fail

    await runner.enqueue(Job(JobType.DOWNLOAD_INVOICES, future=future))
    task = asyncio.create_task(runner._run())

    with pytest.raises(RuntimeError):
        await asyncio.wait_for(future, timeout=1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert "boom" in (tracker.last_error or "")
    fake_logger.error.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_new_invoices_job_enqueues_download(
    fake_invoice_manager, fake_logger, make_invoice
):
    found = [make_invoice(1)]
    fake_invoice_manager.fetch_new_invoices.return_value = found
    tracker = JobTracker()
    runner = JobRunner(fake_invoice_manager, fake_logger, tracker)
    runner.enqueue = AsyncMock()

    result = await runner.fetch_new_invoices_job(
        Job(JobType.FETCH_NEW_INVOICES)
    )

    assert result == found
    runner.enqueue.assert_awaited_once()
    fake_logger.info.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_invoices_job_reads_data(
    fake_invoice_manager, fake_logger, make_invoice
):
    downloaded = {make_invoice(2): True}
    fake_invoice_manager.download.return_value = downloaded
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())

    result = await runner.download_invoices_job(
        Job(JobType.DOWNLOAD_INVOICES, data={"invoices": downloaded})
    )

    assert result == downloaded
    fake_invoice_manager.download.assert_called_once_with(downloaded)


@pytest.mark.asyncio
async def test_print_invoices_job_passes_printer(
    fake_invoice_manager, fake_logger, make_invoice
):
    invoices = [make_invoice(3)]
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())

    await runner.print_invoices_job(
        Job(
            JobType.PRINT_INVOICES,
            data={"invoices": invoices, "printer_name": "Office"},
        )
    )

    fake_invoice_manager.print.assert_called_once_with(invoices, "Office")


@pytest.mark.asyncio
async def test_confirm_invoices_job(
    fake_invoice_manager, fake_logger, make_invoice
):
    invoices = [make_invoice(4)]
    fake_invoice_manager.confirm.return_value = invoices
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())

    result = await runner.confirm_invoices_job(
        Job(JobType.CONFIRM_INVOICES, data={"invoices": invoices})
    )

    assert result == invoices


@pytest.mark.asyncio
async def test_schedule_for_reprint_job(
    fake_invoice_manager, fake_logger, make_invoice
):
    invoices = [make_invoice(5)]
    fake_invoice_manager.schedule_for_reprint.return_value = invoices
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())

    result = await runner.schedule_for_reprint_job(
        Job(JobType.SCHEDULE_FOR_REPRINT_INVOICES, data={"invoices": invoices})
    )

    assert result == invoices


@pytest.mark.asyncio
async def test_fetch_printers_job(fake_invoice_manager, fake_logger):
    fake_invoice_manager.printing_backend.get_default_printer.return_value = (
        "P1"
    )
    fake_invoice_manager.available_printers = ["P1", "P2"]
    runner = JobRunner(fake_invoice_manager, fake_logger, JobTracker())

    result = await runner.fetch_printers_job(Job(JobType.FETCH_PRINTERS))

    assert result == {"default": "P1", "available": ["P1", "P2"]}
