# Transport Application

A full-stack journey planning application for North West England transport data.

## What this repository contains

- **Backend**: Flask API for transport feeds, route planning, account management, and weather
- **Frontend**: Static/Express-served UI with map-based journey planning and accessibility features
- **Docs**: Feature notes, API reference, and design artifacts in `docs/`

## Repository structure

- `/backend` — Flask app, adapters, services, tests, migration SQL
- `/frontend` — UI assets, Express dev server, Playwright accessibility tests
- `/docs` — project documentation index and feature/API/design documents
- `/scripts` — helper scripts for local data seeding

## Prerequisites

- Python 3.10+
- Node.js 20+
- `make` (recommended for local workflows)
- Optional: Podman or Docker for containerised development

## Local development (Linux/macOS)

```bash
# Install backend dependencies in backend/.venv
make install

# Run backend (serves frontend static assets)
make run
```

If your filesystem blocks Python venv symlinks, `make install` automatically retries with copied binaries.

Open: `http://localhost:5000`

## Local development (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

$env:DATABASE_URL="sqlite:///transport.db"
python app.py
```

Open: `http://localhost:5000`

## Container development (Podman/Docker compose)

```bash
# Build and run all services
make up-build

# Start existing services
make up

# Follow logs
make logs

# Stop and remove stack
make down
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:5000`

## Testing

### Backend tests

```bash
cd backend
python -m pytest tests/ -q
```

Or from repo root:

```bash
make test
```

### Frontend accessibility tests

```bash
cd frontend
npm ci
npx playwright install --with-deps chromium
npm run test:a11y
```

Or from repo root:

```bash
make test-a11y
```

## Key environment variables

Backend supports:

- `DATABASE_URL` (default: `sqlite:////tmp/transport.db`)
- `SECRET_KEY` (default: `dev-change-me`)
- `AUTH_TOKEN_MAX_AGE_SECONDS` (default: `86400`)
- `STATIC_DATA_ONLY` (default: `true`)
- `AUTO_REFRESH_STATIC_ON_STARTUP` (default: `false`)

## Static data refresh

Run from repository root:

```bash
# Refresh static stop/timetable data and route index
make refresh-static

# Force full route index rebuild
make refresh-static-force
```

When upstream APIs are available and you want fresh remote data:

```bash
STATIC_DATA_ONLY=false make refresh-static-force
```

## Documentation

Start here:

- [Documentation Index](docs/README.md)
- [User Manual](docs/USER_MANUAL.md)
- [Backend API Documentation](docs/api/API_DOCUMENTATION.md)

## License

See [LICENSE](LICENSE).
