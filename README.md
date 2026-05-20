# InvoiceBot

A Discord Bot to automate and ease the downloading and printing of invoices from [Azienda On Web](https://www.aziendaonweb.it/).

## Installation

### Requirements

- Python **3.13+**
- Google Chrome (for local Selenium runs)
- A matching ChromeDriver available in your PATH (for local runs)
- Optional: CUPS if you want native printer integration

### Install with `uv` (recommended)

```bash
git clone <your-repo-url>
cd InvoiceBot
uv sync
```

### Install with `pip`

```bash
git clone <your-repo-url>
cd InvoiceBot
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run with Docker Compose

```bash
docker compose up --build -d
```

This starts:
- `app` (the bot)
- `selenium` (Chrome WebDriver service)

## Usage

1. Create a `.env` file (you can start from `.env.example`).
2. Set at least the required variables:
   - `AOW_USERNAME`
   - `AOW_PASSWORD`
   - `INVOICEMANAGER_DATABASE_STRING`
   - `DISCORD_BOT_TOKEN`
   - `DISCORD_BOT_MAIN_CHANNEL_ID`

3. Start the bot locally:

```bash
PYTHONPATH=src uv run python -m discord_bot.app
```

Or, if installed with `pip` in a virtual environment:

```bash
PYTHONPATH=src python -m discord_bot.app
```

### Notes

- By default, downloaded invoices are stored in `./invoices/downloaded`.
- Confirmed/processed invoices are stored in `./invoices/confirmed`.
- For Docker usage, keep `AOW_REMOTE_ENABLED=true` and point `AOW_REMOTE_HOST` to the Selenium service (already configured in `compose.yaml`).
- If you don't configure a valid printing backend, the bot falls back to storage-only mode.

