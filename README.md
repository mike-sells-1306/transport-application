Transport Application
=====================

Scaffold for the Transport for North West integrated journey-planning project.

Quick start (development):

1. Start services with Docker Compose:

```bash
docker-compose up --build
```

2. Backend health: http://localhost:5000/health
3. Frontend: http://localhost:3000/

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

See [docs/account-management.md](docs/account-management.md) for endpoint contracts and implementation notes.

See `docs/software-design-doc-source/main.tex` for the software design document.
# transport-application
todo