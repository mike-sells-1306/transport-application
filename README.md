Transport Application
=====================

Scaffold for the Transport for North West integrated journey-planning project.

## Quick Start (Local Development)

### Linux/macOS

```bash
# 1. Install dependencies (first time only)
make install

# 2. Run the application
make run

# 3. Open http://localhost:5000
```

### Windows (PowerShell)

```powershell
# 1. Install dependencies (first time only)
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 2. Run the application
$env:DATABASE_URL="sqlite:///transport.db"
python app.py

# 3. Open http://localhost:5000
```

### Podman (containerised)

```bash
# Preferred: built-in compose in Podman v4+
podman compose version

# Optional fallback (if your Podman install has no compose subcommand)
pip install --user podman-compose

# Build and start all services
make up-build
# or directly:
podman compose up -d --build

# Start existing containers (daily usage)
make up

# Follow logs (optional)
make logs

# Frontend: http://localhost:3000
# Backend:  http://localhost:5000

# Stop and remove containers
make down
```

> **Note:** Podman runs rootless by default. No daemon or `sudo` is required.

## Running Tests

```bash
make test          # Linux/macOS
make test-win      # Windows
```

## Static transport data refresh (manual)

Stops and scheduled timetable/index data are now intended to be refreshed on demand from the terminal.

Run these commands from the repository root (`transport-application/`).

```bash
# Refresh static stops + timetable connection index
make refresh-static

# Force a full rebuild of the timetable connection index
make refresh-static-force
```

### Updating static data when the API comes back up

Use `STATIC_DATA_ONLY=false` so the refresh job can pull the latest stop/timetable metadata from the API before rebuilding local static storage.

```bash
# Recommended: full refresh + forced index rebuild
STATIC_DATA_ONLY=false make refresh-static-force

# Optional: incremental refresh
STATIC_DATA_ONLY=false make refresh-static
```

The command output prints inserted stop count and indexed connection totals so you can verify the refresh succeeded.

Environment flags:

- `STATIC_DATA_ONLY=true` (default): static endpoints read from local DB/cache, not live API.
- `AUTO_REFRESH_STATIC_ON_STARTUP=false` (default): do not auto-refresh static data on backend startup.
- `LIVE_POLL_MIN_SECONDS=5` (default minimum): caps live API polling cadence (bus/rail/weather).
- `ROUTE_CONNECTION_INDEX_DB=/tmp/transport_connection_index.sqlite3` (default): SQLite path for the route connection index.

## Viewing Backend Stop/Station Metrics

The backend now tracks route-planning processing counts for:

- total **bus stops processed**
- total **train stations processed**

### How to trigger metric calculation

Run a route search through the backend route planner (for example `POST /api/routes/search` from the frontend journey planner UI).

### Where to view the metrics

1. **Backend logs** during route planning:
   - `Bus stops processed: X`
   - `Train stations processed: Y`
2. **Debug API endpoint**:
   - `GET /api/routes/metrics`

### Example output

```json
{
  "bus_stops_processed": 284,
  "train_stations_processed": 30,
  "planner_stage": "csa"
}
```

## Automated Accessibility Testing

The frontend now includes Playwright + axe-core accessibility smoke tests.

### Quick run (Linux/macOS)

```bash
make test-a11y
```

### Manual frontend run

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:a11y
```

### What is covered

- axe automated scan for serious/critical issues
- accessible names on key interactive controls
- keyboard tab navigation smoke flow
- live-region announcement check for notifications

## Localisation

The frontend now includes a locale-based internationalisation layer.

- Supported locale codes: `en-GB`, `en-US`, `cy-GB`, `fr-FR`, `de-DE`, `es-ES`, `zh-CN`, `hi-IN`, `ar`, `bn-BD`, `pt-BR`, `ru-RU`, `ur-PK`
- Language can be changed in **Accessibility → Language**
- Selected locale is persisted in browser storage
- `<html lang>` is updated dynamically for assistive technologies

Translation resources are stored in:

- [frontend/src/locales/en-GB.json](frontend/src/locales/en-GB.json)
- [frontend/src/locales/fr-FR.json](frontend/src/locales/fr-FR.json)

New locales can be added by creating another JSON file with the same key structure and adding the locale code to the frontend locale list.

## Account management integration

The scaffold now includes a full account management API and UI hooks for:

- account registration and login
- profile updates (username / colour-blind mode preference)
- password update and account deletion
- saving and listing journey routes
- user notifications and tracked weather locations

### Runtime dependencies

- `frontend` proxies all `/api/*` requests to `backend`
- `backend` uses MySQL (`mysql` service in Docker Compose)
- default DB connection is configured in [docker-compose.yml](docker-compose.yml)

### Environment settings

The backend reads the following environment variables:

- `DATABASE_URL`
- `SECRET_KEY`
- `AUTH_TOKEN_MAX_AGE_SECONDS`

See [docs/features/account-management.md](docs/features/account-management.md) for endpoint contracts and implementation notes.

See [docs/design/software-design-doc-source/main.tex](docs/design/software-design-doc-source/main.tex) for the software design document.

See [docs/README.md](docs/README.md) for a full documentation index.
