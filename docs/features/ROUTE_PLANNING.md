# Route Planning Feature

## Overview

The route planning feature allows users to search for transport routes between any two stops in the North West England region. Routes are fetched from the external Journey Planner API, with a comprehensive mock fallback that provides realistic multi-modal routes with detailed leg information.

## How It Works

### User Flow

1. User types an origin stop in the **"From"** input and a destination in the **"To"** input.
2. The autocomplete system (backed by the StopCache database) suggests matching stops.
3. Once both stops are selected, a route search is triggered automatically.
4. The **Route Modal** appears in the centre of the map, showing available routes sorted by the selected criterion.
5. Clicking a route row **expands** it to reveal detailed leg-by-leg information.

### Triggering a Search

A search is triggered in two scenarios:

- **Selecting the second stop** — as soon as both `selectedStops.from` and `selectedStops.to` are populated, `searchRoutes()` fires.
- **Pressing the swap button** — the from/to inputs are swapped and, if both are populated, `searchRoutes()` fires again.

## Backend API

### `POST /api/routes/search`

**Request body:**

```json
{
  "from": { "name": "Lancaster Bus Station (Bay 1)", "atcoCode": "2400LAC30001", "lat": 54.0488, "lon": -2.8013 },
  "to":   { "name": "Blackpool North Bus Station",   "atcoCode": "2400LAB20001", "lat": 53.8212, "lon": -3.0507 }
}
```

Notes:
- `atcoCode`/`ATCOCode` (or `CRS:<code>` for rail stations) is preferred and used as an exact stop pin when available.
- For compatibility, requests that include stop names and coordinates can still be routed without explicit stop codes.

**Response:**

```json
{
  "from": "Lancaster Bus Station (Bay 1)",
  "to": "Blackpool North Bus Station",
  "timestamp": "2025-07-14T12:00:00",
  "routes": [
    {
      "start_time": "09:10",
      "end_time": "10:05",
      "duration_mins": 55,
      "transport": ["bus"],
      "changes": 0,
      "legs": [ ... ]
    }
  ]
}
```

### Route Object

| Field          | Type       | Description                                        |
|----------------|------------|----------------------------------------------------|
| `start_time`   | `string`   | Departure time of the first leg (HH:MM)            |
| `end_time`     | `string`   | Arrival time of the last leg (HH:MM)               |
| `duration_mins`| `integer`  | Total journey duration in minutes                  |
| `transport`    | `string[]` | Unique transport modes used (`"bus"`, `"train"`)    |
| `changes`      | `integer`  | Number of vehicle changes (excluding walks)         |
| `legs`         | `object[]` | Ordered list of journey legs (see below)            |

### Leg Object — Walking

```json
{
  "mode": "walk",
  "from_stop": "Selected stop",
  "to_stop": "Lancaster Bus Station (Bay 1)",
  "depart": "09:10",
  "arrive": "09:15",
  "duration_mins": 5,
  "distance_m": 300
}
```

### Leg Object — Transport (Bus / Train)

```json
{
  "mode": "bus",
  "service": "Service 42",
  "from_stop": "Lancaster Bus Station (Bay 1)",
  "to_stop": "Blackpool North Bus Station",
  "depart": "09:15",
  "arrive": "10:02",
  "duration_mins": 47,
  "intermediate_stops": [
    { "name": "Garstang Bus Stop", "time": "09:32" },
    { "name": "Preston Bus Station (Stand 1)", "time": "09:48" }
  ]
}
```

## Sorting

Two sort options are available via the dropdown in the route modal:

| Option            | Primary Sort           | Secondary Sort |
|-------------------|------------------------|----------------|
| **Fastest**       | `duration_mins` ASC    | `start_time`   |
| **Fewest Changes**| `changes` ASC          | `duration_mins` |

> The "Cheapest" option has been removed as fare data is not available from the transport APIs.

## Expandable Route Details

Each route row in the modal is clickable. Clicking a row toggles an **expansion panel** that shows every leg of the journey:

- **Walking legs** — displayed with a walking icon, distance in metres, and a start → end stop label.
- **Transport legs** — displayed with a bus or train icon, the service name (e.g. "Service 42", "Northern Rail"), origin and destination stops, and an optional list of intermediate stops with arrival times.
- Only one route can be expanded at a time; opening a new one collapses the previous.

## Route Algorithm

### API-First Strategy

The backend first attempts to call the external **Journey Planner API** at `http://transport.scc.lancs.ac.uk/journey/plan`. If this returns valid routes, they are used directly.

### Mock Fallback

If the external API is unavailable or returns no results, the system falls back to `_generate_valid_mock_routes()`, which provides:

1. **Predefined routes** for common pairs (Lancaster ↔ Blackpool, Blackpool ↔ Preston, Manchester ↔ Liverpool, Preston ↔ Manchester, Manchester ↔ Leeds, Lancaster ↔ Kendal, Kendal ↔ Windermere, and their reverse directions). These include realistic intermediate stops, service names, and walking segments.

2. **Procedural generation** for any other pair. Uses a seeded random number generator (`hash(from + to)`) so results are deterministic. Generated routes include:
   - An opening walking leg from the selected stop to the nearest transport stop.
   - One or two transport legs (single-mode or multi-modal with a walking transfer).
   - Random intermediate stops drawn from the region's known stops.
   - A closing walking leg to the destination.

### Multi-Modal Support

Routes may combine bus and train segments. When a route requires changing between modes, a walking leg is inserted between the two transport legs to represent the transfer between stops (e.g. walking from a bus station to a nearby railway station).

## Test Coverage

Tests are located in `backend/tests/test_routes.py` and cover:

- **Endpoint validation** — missing body, missing from/to, empty names → 400 errors
- **Response schema** — routes contain all required fields including `legs`
- **Leg structure** — walking legs have `distance_m`, transport legs have `service` and `intermediate_stops`
- **Mock generation** — known pairs produce predefined routes, unknown pairs produce procedural routes, output is deterministic and sorted by start time
- **Duration consistency** — `duration_mins` matches the difference between `start_time` and `end_time`
- **Sorting** — Fastest and Fewest Changes sort algorithms produce correctly ordered output
- **Reverse routes** — both directions of a pair produce distinct route sets

Run tests:

```bash
cd backend
python3 -m pytest tests/test_routes.py -v
```

## Files Modified

| File | Changes |
|------|---------|
| `backend/app.py` | Rewrote `_generate_valid_mock_routes()` with detailed leg data for 10 predefined route pairs + procedural generation |
| `frontend/src/index.html` | Removed "Cheapest" sort option, cleared static route rows (now populated dynamically) |
| `frontend/src/main.js` | Removed Cheapest from `sortRoutes()`, added `formatDuration()`, `buildWalkLeg()`, `buildTransportLeg()`, `toggleRouteDetail()`, rewrote `renderRoutesTable()` with clickable rows and expand icons |
| `frontend/src/style.css` | Added styles for transport icon chains, changes badge, expand icon, route detail panel, walking/transport legs, intermediate stops list, expand animation |
| `backend/tests/test_routes.py` | **New file** — 17 tests covering the route search endpoint and mock generator |
| `docs/features/ROUTE_PLANNING.md` | **New file** — this document |
