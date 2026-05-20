import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_bot.enums import LoggingCategory
from discord_bot.logs import BotLogger, _LogItem


@pytest.mark.asyncio
async def test_start_creates_worker_task(state_store):
    logger = BotLogger(SimpleNamespace(rest=SimpleNamespace()), 1, state_store)
    logger._worker = AsyncMock()

    await logger.start()

    assert logger._task is not None
    logger._task.cancel()


@pytest.mark.asyncio
async def test_stop_without_task_is_noop(state_store):
    logger = BotLogger(SimpleNamespace(rest=SimpleNamespace()), 1, state_store)

    await logger.stop()

    assert logger._task is None


@pytest.mark.asyncio
async def test_log_always_calls_std_logger(state_store):
    bot = SimpleNamespace(rest=SimpleNamespace(create_message=AsyncMock()))
    logger = BotLogger(bot, None, state_store)
    logger._std_logger = MagicMock()

    await logger.log("hello", LoggingCategory.INFO)

    logger._std_logger.log.assert_called_once()


@pytest.mark.asyncio
async def test_log_enqueues_only_above_level(state_store):
    bot = SimpleNamespace(rest=SimpleNamespace(create_message=AsyncMock()))
    logger = BotLogger(bot, 10, state_store)
    logger._std_logger = MagicMock()
    state_store.state.discord_log_level = LoggingCategory.WARNING

    await logger.log("debug", LoggingCategory.DEBUG)
    await logger.log("warning", LoggingCategory.WARNING)

    assert logger._queue.qsize() == 1


@pytest.mark.asyncio
async def test_helper_methods_delegate(state_store):
    bot = SimpleNamespace(rest=SimpleNamespace(create_message=AsyncMock()))
    logger = BotLogger(bot, None, state_store)
    logger.log = AsyncMock()

    await logger.debug("d")
    await logger.info("i")
    await logger.warning("w")
    await logger.error("e")
    await logger.critical("c")

    assert logger.log.await_count == 5


@pytest.mark.asyncio
async def test_worker_sends_message_and_marks_done(state_store):
    create_message = AsyncMock()
    bot = SimpleNamespace(rest=SimpleNamespace(create_message=create_message))
    logger = BotLogger(bot, 999, state_store)
    logger._std_logger = MagicMock()

    await logger._queue.put(_LogItem("hello", LoggingCategory.INFO))
    task = asyncio.create_task(logger._worker())
    await asyncio.sleep(0)
    await logger._queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    create_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_handles_discord_exception(state_store):
    create_message = AsyncMock(side_effect=RuntimeError("boom"))
    bot = SimpleNamespace(rest=SimpleNamespace(create_message=create_message))
    logger = BotLogger(bot, 999, state_store)
    logger._std_logger = MagicMock()

    await logger._queue.put(_LogItem("hello", LoggingCategory.INFO))
    task = asyncio.create_task(logger._worker())
    await asyncio.sleep(0)
    await logger._queue.join()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    logger._std_logger.exception.assert_called_once()
