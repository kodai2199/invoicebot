import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import hikari
import pytest

from discord_bot import app


class FakeStateStore:
    def __init__(self, _path):
        self.save = MagicMock()


class FakeLogger:
    def __init__(self, *_args):
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.info = AsyncMock()
        self.warning = AsyncMock()


class FakeRunner:
    def __init__(self, **_kwargs):
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.enqueue = AsyncMock(return_value="job")


class FakeDashboardManager:
    def __init__(self, **_kwargs):
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.update_dashboard = AsyncMock()


class FakeGatewayBot:
    def __init__(self, **_kwargs):
        self.start = AsyncMock()
        self.join = AsyncMock()
        self.run = AsyncMock()
        self.subscribe = MagicMock()


@pytest.fixture
def setup_invoice_bot(monkeypatch):
    monkeypatch.setattr(app, "ensure_bootstrapped", lambda: None)
    monkeypatch.setattr(
        app,
        "_create_runtime_components",
        lambda: (
            FakeDashboardManager,
            FakeRunner,
            lambda: SimpleNamespace(),
            FakeStateStore,
            FakeLogger,
        ),
    )
    monkeypatch.setattr(
        app.hikari, "GatewayBot", lambda **kwargs: FakeGatewayBot()
    )
    monkeypatch.setattr(
        app.miru, "Client", lambda *_args, **_kwargs: SimpleNamespace()
    )


@pytest.mark.asyncio
async def test_bootstrap_from_env(monkeypatch):
    calls = []
    monkeypatch.setattr(app, "load_dotenv", lambda: calls.append("dotenv"))
    monkeypatch.setattr(
        app, "set_user_locale", lambda locale: calls.append(locale)
    )
    monkeypatch.setenv("DISCORD_BOT_LANGUAGE", "it")

    language = app.bootstrap_from_env()

    assert language == "it"
    assert calls == ["dotenv", "it"]


@pytest.mark.asyncio
async def test_bootstrap_defaults_to_en(monkeypatch):
    calls = []
    monkeypatch.setattr(app, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        app, "set_user_locale", lambda locale: calls.append(locale)
    )
    monkeypatch.delenv("DISCORD_BOT_LANGUAGE", raising=False)

    language = app.bootstrap_from_env()

    assert language == "en"
    assert calls == ["en"]


def test_invoice_bot_requires_token_and_channel(
    setup_invoice_bot, monkeypatch
):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_BOT_MAIN_CHANNEL_ID", raising=False)

    with pytest.raises(ValueError):
        app.InvoiceBot(SimpleNamespace(), token=None, main_channel_id=None)


def test_invoice_bot_uses_env_values(setup_invoice_bot, monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "abc")
    monkeypatch.setenv("DISCORD_BOT_MAIN_CHANNEL_ID", "10")
    monkeypatch.setenv("DISCORD_BOT_LOG_CHANNEL_ID", "20")

    bot = app.InvoiceBot(SimpleNamespace(), savefile_path=Path("dummy.txt"))

    assert bot.token == "abc"
    assert bot.main_channel_id == 10
    assert bot.log_channel_id == 20


@pytest.mark.asyncio
async def test_respond_ephemeral_sets_flag_and_schedules_delete(
    setup_invoice_bot,
):
    bot = app.InvoiceBot(SimpleNamespace(), token="t", main_channel_id=1)
    ctx = SimpleNamespace(respond=AsyncMock(return_value=SimpleNamespace()))

    def fake_create_background_task(coroutine, name):
        coroutine.close()

    bot.create_background_task = MagicMock(
        side_effect=fake_create_background_task
    )

    await bot.respond_ephemeral(ctx, "hello", delete_after=99999)

    kwargs = ctx.respond.await_args.kwargs
    assert kwargs["flags"] == hikari.MessageFlag.EPHEMERAL
    bot.create_background_task.assert_called_once()


@pytest.mark.asyncio
async def test_delete_response_later_uses_response_delete(
    setup_invoice_bot, monkeypatch
):
    bot = app.InvoiceBot(SimpleNamespace(), token="t", main_channel_id=1)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    response = SimpleNamespace(delete=AsyncMock())
    ctx = SimpleNamespace(delete_response=AsyncMock())

    await bot._delete_response_later(ctx, response, 1)

    response.delete.assert_awaited_once()
    ctx.delete_response.assert_not_called()


@pytest.mark.asyncio
async def test_delete_response_later_fallback_to_ctx(
    setup_invoice_bot, monkeypatch
):
    bot = app.InvoiceBot(SimpleNamespace(), token="t", main_channel_id=1)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    ctx = SimpleNamespace(delete_response=AsyncMock())

    await bot._delete_response_later(ctx, SimpleNamespace(), 1)

    ctx.delete_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_job_state_changed_logs_warning_on_failure(setup_invoice_bot):
    bot = app.InvoiceBot(SimpleNamespace(), token="t", main_channel_id=1)
    bot.dashboard_manager.update_dashboard = AsyncMock(
        side_effect=RuntimeError("x")
    )

    await bot._on_job_state_changed()

    bot.logger.warning.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_start_and_stop(setup_invoice_bot):
    bot = app.InvoiceBot(SimpleNamespace(), token="t", main_channel_id=1)
    done_task = asyncio.create_task(asyncio.sleep(0))
    await done_task
    bot._background_tasks.add(done_task)

    await bot.on_start(SimpleNamespace())
    await bot.on_stop(SimpleNamespace())

    bot.logger.start.assert_awaited_once()
    bot.dashboard_manager.start.assert_awaited_once()
    bot.job_runner.start.assert_awaited_once()
    bot.job_runner.stop.assert_awaited_once()
    bot.dashboard_manager.stop.assert_awaited_once()
    bot.logger.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_join_run_delegate(setup_invoice_bot):
    bot = app.InvoiceBot(SimpleNamespace(), token="t", main_channel_id=1)

    await bot.start(1)
    await bot.join(2)
    await bot.run(3)

    bot.bot.start.assert_awaited_once()
    bot.bot.join.assert_awaited_once()
    bot.bot.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_bootstraps_before_bot_start(monkeypatch):
    order = []

    monkeypatch.setattr(
        app, "bootstrap_from_env", lambda: order.append("bootstrap")
    )
    monkeypatch.setattr(
        app,
        "AziendaOnWebClient",
        lambda *_args, **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        app.ClientConfigBuilder,
        "from_env",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        app.InvoiceManagerConfigBuilder,
        "from_env",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        app,
        "InvoiceManager",
        lambda *_args, **_kwargs: SimpleNamespace(),
    )

    fake_bot = SimpleNamespace(start=AsyncMock(), join=AsyncMock())
    monkeypatch.setattr(app, "InvoiceBot", lambda *_args, **_kwargs: fake_bot)

    await app.main()

    assert order == ["bootstrap"]
    fake_bot.start.assert_awaited_once()
    fake_bot.join.assert_awaited_once()
