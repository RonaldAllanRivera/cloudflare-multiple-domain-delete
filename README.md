# Cloudflare Multiple Domain Delete (GUI)

A small Python app with a Tkinter UI that lets you bulk delete Cloudflare domains ("zones") safely, with progress feedback and logs.

## Overview

This tool helps you remove multiple domains from your Cloudflare account in a controlled way. You can paste up to 10 domains at a time, press DELETE, and watch a progress bar and log update as each zone is removed.

- Built with Python + Tkinter
- Uses Cloudflare API v4
- API Token (least-privilege) recommended
- Progress bar + ETA + log window
- Confirmation prompt before deletion

## Features

- Delete up to 10 domains per run (prevents accidental mass deletion)
- Progress bar with ETA and detailed logs
- Threaded deletion to keep the UI responsive
- Rate-limit aware (backs off on HTTP 429)
- Safe-by-default confirmation dialog
- .env-based configuration to keep secrets out of source control

## Requirements

- Python 3.9+ (Tkinter usually included on Windows/macOS)
- pip

## Setup

1. Clone or download this repository.
2. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Windows CMD
.\.venv\Scripts\activate.bat
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create your `.env` from the example and fill in your credentials:

```bash
copy .env.example .env  # on Windows
# or
cp .env.example .env    # on macOS/Linux
```

Edit `.env` and set either:

- CLOUDFLARE_API_TOKEN (recommended)

or (not recommended):

- CLOUDFLARE_EMAIL
- CLOUDFLARE_API_KEY

## Where to get the secrets

- API Token (recommended):
  - Cloudflare Dashboard → My Profile → API Tokens → Create Token → Create Custom Token
  - Permissions: Zone → Read, Zone → Edit
  - Resources: Include → All zones (or specific zones you plan to delete)
  - Copy the token into `CLOUDFLARE_API_TOKEN` in your `.env` file.

- Global API Key (legacy, not recommended):
  - Cloudflare Dashboard → My Profile → API Keys → Global API Key → View
  - Copy `Global API Key` and your account email into `CLOUDFLARE_API_KEY` and `CLOUDFLARE_EMAIL`.

Note: The app will prefer the API Token if present.

## Usage

Run the app:

```bash
python app.py
```

1. Paste up to 10 domain names (one per line) in the input box.
2. Click DELETE.
3. Confirm the operation when prompted.
4. Watch progress and logs. When done, inputs are re-enabled.

## Safety Notes

- Deleting a zone is irreversible. Be absolutely sure before proceeding.
- Start with a single test domain to validate access and behavior.
- The app spaces out requests slightly and backs off on rate limits, but you should still avoid unnecessary repeated attempts.

## Troubleshooting

- "Missing credentials": Ensure your `.env` is created and filled, then restart the app.
- "Zone not found": Verify the exact domain spelling (e.g., `example.com`, not `https://example.com`).
- API errors (HTTP 4xx/5xx): Check your token permissions and network connectivity.

## Development

- Linting/formatting are not configured. Feel free to add tools like `black`, `ruff`, or `flake8` if you wish.

## License

This project is provided as-is for internal workflow automation. Add a license if you plan to distribute.
