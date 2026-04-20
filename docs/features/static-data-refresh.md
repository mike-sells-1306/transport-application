# Static Transport Data Refresh (Terminal Workflow)

This project uses **local static data** for:

- stop search (`StopCache`)
- scheduled bus timetable/trip data
- route-planning connection index

Live APIs are still used for weather and live journey updates.

---

## Where to run commands

Run all commands from the repository root:

```bash
cd transport-application
```

---

## Daily usage (offline/static mode)

```bash
make refresh-static
```

This refreshes:

1. stop cache table
2. timetable connection index

---

## When API is back up (pull latest data)

Use `STATIC_DATA_ONLY=false` to allow API-backed refresh during the command:

```bash
# Full refresh (recommended)
STATIC_DATA_ONLY=false make refresh-static-force

# Incremental refresh (optional)
STATIC_DATA_ONLY=false make refresh-static
```

`refresh-static-force` clears/rebuilds the connection index before repopulating.

---

## What success looks like

The terminal output includes JSON with keys similar to:

- `stops.inserted`
- `index.indexed_datasets`
- `index.connections`

If those values are greater than zero, the refresh has loaded static data.

---

## Related files

- `Makefile` (refresh targets)
- `backend/scripts/refresh_static_data.py` (CLI entrypoint)
- `backend/app.py` (`refresh_static_data()` implementation)
