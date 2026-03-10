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
# transport-application
todo