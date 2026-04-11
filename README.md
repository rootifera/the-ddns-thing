# The DDNS Thing

`the-ddns-thing` is a small web UI for managing Cloudflare-based dynamic DNS.

It is designed to be simple to self-host: one admin account, one Cloudflare account, multiple domains, and a clean browser-based workflow instead of hand-editing config files.

## What It Does

- Runs a small web app for managing DDNS records
- Stores app state in SQLite
- Supports multiple Cloudflare root domains under one account
- Supports root records and subdomains for IPv4 `A` record DDNS
- Automatically syncs managed records to the current public IPv4 address
- Lets you enable domains directly from your Cloudflare zone list
- Lets you add and remove managed records from the UI
- Shows sync status, recent IP information, and basic runtime statistics
- Supports import/export of managed domains and records
- Supports TOTP 2FA for the admin account

## First-Run Flow

On first launch, the app opens a setup screen in the browser and asks for:

- Admin username
- Admin password
- Cloudflare email
- Cloudflare global API key

After setup, you can:

1. Enable domains from the Cloudflare zone list
2. Add DDNS records for those domains
3. Let the background sync worker keep them updated

## Main Features

- Dashboard with:
  - Sync status
  - Runtime statistics
  - Available Cloudflare domains
  - Enabled domains
  - Import/export tools
- Dedicated subdomain management page with:
  - Add/remove records
  - Filtering by name, domain, or full record
  - Current IP and previous IP display
  - Recent IP hover history
- Account page with:
  - TOTP 2FA setup
  - QR code-based authenticator enrollment

## Local Run

Install dependencies and start the app:

```bash
pip install -r requirements.txt
python -m the_ddns_thing.main
```

The web UI listens on `http://127.0.0.1:10710` by default.

You can override host, port, sync interval, and data directory:

```bash
python -m the_ddns_thing.main \
  --host 0.0.0.0 \
  --port 10710 \
  --sync-interval 300 \
  --data-dir ./data
```

## Data Storage

Outside Docker, the app stores its local data in the current working directory by default:

- `./the-ddns-thing.db`
- `./secret.key`

You can change that location with either:

- `THE_DDNS_THING_DATA_DIR`
- `--data-dir`

## Docker

Pull the published image:

```bash
docker pull rootifera/the-ddns-thing:latest
```

Run it directly:

```bash
docker run --rm -p 10710:10710 -v ddns_data:/data rootifera/the-ddns-thing:latest
```

Or use Compose:

```bash
docker compose up -d
```

The included [docker-compose.yml](/home/omur/repos/the-ddns-thing/docker-compose.yml) uses:

- `rootifera/the-ddns-thing:latest`
- port `10710`
- a named Docker volume mounted at `/data`

Inside the container:

- app code lives in `/app`
- SQLite database and `secret.key` live in `/data`

If you want to build locally instead:

```bash
docker build -t the-ddns-thing .
docker run --rm -p 10710:10710 -v ddns_data:/data the-ddns-thing
```

## Configuration

The app currently assumes:

- one admin account per installation
- one Cloudflare account per installation
- multiple Cloudflare zones per installation
- dynamic DNS for IPv4 `A` records only

There is intentionally no direct “edit record” flow right now. Managed records are added or removed from the UI.

## Import / Export

The import/export tools back up and restore:

- enabled domains
- managed DDNS records

They do not include:

- admin credentials
- Cloudflare API credentials
- session secrets

## Security

- Admin passwords are stored as hashes
- Cloudflare API credentials are encrypted at rest in the SQLite database
- The Cloudflare API key is not hashed, because the app must decrypt and use the real key for Cloudflare API requests
- Stored TOTP secrets are encrypted at rest
- Optional TOTP 2FA is available from the Account page
- TOTP setup includes a QR code for authenticator apps
- The Docker image runs with Gunicorn instead of Flask’s development server

## Notes

- Root/apex records are supported
- Cloudflare record IDs are managed internally and not exposed as a primary UI concept
- The sync interval can be changed from the dashboard

## Development

If you change dependencies or templates, rebuild the Docker image before redeploying:

```bash
docker build -t rootifera/the-ddns-thing:latest .
```

For a quick Python sanity check:

```bash
python3 -m compileall the_ddns_thing
```
