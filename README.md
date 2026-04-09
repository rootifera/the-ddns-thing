# The DDNS Thing

`the-ddns-thing` is a small web UI for managing dynamic DNS subdomains on Cloudflare.

Instead of editing flat config files, the app now stores its managed state in SQLite and walks you through first-run setup in the browser.

## What It Does

- Creates a local SQLite database in the app working directory
- Shows a first-run setup form for:
  - admin username
  - admin password
  - Cloudflare email
  - Cloudflare global API key
- Lets you add and remove multiple managed root domains from the web dashboard
- Looks up each Cloudflare zone automatically when you add a domain
- Lets you add and remove managed subdomains under any configured domain
- Runs a background sync loop that keeps those `A` records pointed at the machine's current public IPv4 address

## Run It

Install dependencies and start the app:

```bash
pip install -r requirements.txt
python -m the_ddns_thing.main
```

Or after installing the package:

```bash
the-ddns-thing
```

By default the web UI starts on `http://127.0.0.1:5000`.

You can override the bind address, port, and sync interval:

```bash
the-ddns-thing --host 0.0.0.0 --port 8080 --sync-interval 300
```

## Storage

By default outside Docker, the application stores local data in the current working directory:

- `./the-ddns-thing.db`
- `./secret.key`

You can override that location with `THE_DDNS_THING_DATA_DIR` or `--data-dir`.

## Docker

Pull and run from Docker Hub:

```bash
docker pull rootifera/the-ddns-thing:latest
docker run --rm -p 5000:5000 rootifera/the-ddns-thing:latest
```

For persistent data with Docker, mount a dedicated data path instead of the repo:

```bash
docker run --rm -p 5000:5000 -v ddns_data:/data rootifera/the-ddns-thing:latest
```

Or with Compose:

```bash
docker compose up -d
```

The checked-in [docker-compose.yml](/home/omur/repos/the-ddns-thing/docker-compose.yml) uses the published `rootifera/the-ddns-thing:latest` image and stores the SQLite database plus secret key in a named Docker volume mounted at `/data`.

If you want to build locally instead of pulling from Docker Hub:

```bash
docker build -t the-ddns-thing .
docker run --rm -p 5000:5000 the-ddns-thing
```

The container uses `/app` for code and `/data` for persisted state. That keeps runtime data separate from the image contents and avoids leaking files from your repo into the container.

The database contains:

- Cloudflare connection settings
- the local admin account
- managed root domains and zone IDs
- managed subdomains
- sync status details such as last IP and last sync result

## Current Scope

This version is intentionally simple:

- one Cloudflare account per installation
- multiple Cloudflare zones per installation
- domains and subdomains can be added and removed
- no edit flow yet
- IPv4 `A` records only

## Next Good Improvements

- stronger authentication flows
- HTTPS/reverse-proxy deployment guidance
- audit history in the UI
- better test coverage around setup, login, and sync
- per-domain sync history and filtering
