# TODO

## Account Management – Next Steps

- [ ] Stabilize runtime dependencies
  - Add/confirm frontend dependencies in [frontend/package.json](frontend/package.json).
  - Remove masked install failures (`|| true`) in [frontend/Dockerfile](frontend/Dockerfile).

- [ ] Finalize database migration workflow
  - Replace ad-hoc `db.create_all()` usage in [backend/app.py](backend/app.py) with versioned migrations.
  - Keep schema source aligned in [backend/migrations/account_management_schema.sql](backend/migrations/account_management_schema.sql).

- [ ] Harden authentication and security
  - Move from local-storage bearer token to `HttpOnly` cookie session (or access/refresh tokens).
  - Add auth rate limiting and stricter password policy in [backend/app.py](backend/app.py).

- [ ] Complete account UI actions
  - Add profile edit and color-blind preference controls in [frontend/src/index.html](frontend/src/index.html).
  - Wire UI logic in [frontend/src/main.js](frontend/src/main.js).
  - Add saved-route removal and notification read actions.

- [ ] Expand automated testing
  - Add negative/security tests to [backend/tests/test_account.py](backend/tests/test_account.py) (invalid token, duplicate email, wrong password, etc.).
  - Add frontend flow tests for register/login/logout/delete.

- [ ] Finalize documentation and handover
  - Keep endpoint/auth contract current in [docs/account-management.md](docs/account-management.md).
  - Add operator runbook steps in [README.md](README.md) for env vars, DB reset, and smoke tests.
