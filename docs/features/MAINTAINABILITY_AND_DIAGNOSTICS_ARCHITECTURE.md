# Maintainability + Backend Diagnostics (Staged Refactor Note)

## Scope and constraints

- This work is a **staged refactor**, not a full rewrite.
- **Behavior parity** for existing API/UI flows is a hard requirement.
- Existing contracts (health, account, weather, route-search, route-metrics) remain stable while internals are improved incrementally.

## Acceptance criteria

### Maintainability outcomes

- Introduce clearer ownership boundaries using incremental extraction (service/helper modules and frontend feature modules).
- Reduce repeated UI panel-toggle logic through a shared orchestration helper.
- Keep endpoint paths and payload compatibility for existing consumers/tests.

### Backend diagnostics outcomes

- Provide a dedicated diagnostics endpoint contract for UI consumption.
- Include:
  - backend status
  - static-data mode
  - stop-cache readiness and count
  - route-index readiness + redacted DB reference
  - route-processing metrics
  - snapshot timestamp
- Keep `/api/health` backward-compatible for probe usage.

## Target architecture direction

### Backend

- `app.py` remains the entry point while responsibilities are gradually extracted into service modules.
- Diagnostics snapshot generation is centralized in `services/diagnostics_service.py`.
- Dedicated diagnostics contract endpoint: `GET /api/diagnostics/summary`.

### Frontend

- Add feature module `frontend/src/diagnostics-client.js` for diagnostics API access.
- Add diagnostics panel and navigation entry integrated with existing sidebar/panel UX.
- Centralize panel open/close behavior through shared orchestration in `main.js`.

## Security and data exposure rules

- Diagnostics endpoint redacts filesystem-style route index paths to a safe basename.
- Existing `/api/health` behavior remains compatible for operational probes.

## Freshness semantics

- Diagnostics responses are snapshot-based and include `snapshot_utc`.
- UI shows last-updated time and supports manual refresh.

## Troubleshooting quick guide

- **Backend unreachable**: diagnostics panel shows unavailable state; verify backend process/container.
- **Stop cache not ready**: run static refresh workflow (`make refresh-static` / `make refresh-static-force`).
- **Route index not ready**: rebuild index (`make build-index` or refresh-static-force).
