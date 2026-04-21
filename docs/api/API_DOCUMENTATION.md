# Backend API Documentation

This document reflects the endpoints currently implemented in `backend/app.py`.

## Base URL

- Local backend: `http://localhost:5000`

## Authentication

Authenticated endpoints require:

```http
Authorization: Bearer <token>
```

Tokens are issued by login/register endpoints.

## Response conventions

- Success responses are JSON unless explicitly returning binary (weather icon PNG).
- Error responses follow a JSON shape with an `error` message and appropriate HTTP status.

---

## Health and diagnostics

### `GET /health`
Simple service liveness check.

### `GET /api/health`
Extended diagnostics including static-data and route-index readiness.

### `GET /api/hello`
Basic backend identity message.

---

## Authentication and account

### `POST /api/auth/register`
Create account.

Request body:

```json
{
  "email": "user@example.com",
  "userName": "exampleUser",
  "password": "minimum-8-chars"
}
```

Returns `201` with `{ token, user }` on success.

### `POST /api/auth/login`
Authenticate user.

Request body:

```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

Returns `{ token, user }`.

### `POST /api/auth/logout`
Stateless logout acknowledgement.

### `GET /api/account/me` *(auth required)*
Get current account profile.

### `PATCH /api/account/profile` *(auth required)*
Update profile fields.

Supported body fields:

- `userName`
- `colorblindmode` (boolean)
- `accessibilitymode` (`none`, `deuteranopia`, `protanopia`, `tritanopia`, `achromatopsia`)
- `accessibilityfontsize` (`small`, `normal`, `large`)
- `accessibilityzoom` (float between `0.85` and `1.4`)

### `PATCH /api/account/password` *(auth required)*
Update password.

Body:

```json
{
  "currentPassword": "old-password",
  "newPassword": "new-password"
}
```

### `DELETE /api/account` *(auth required)*
Delete account.

Body:

```json
{
  "password": "current-password"
}
```

### `GET /api/account/saved-routes` *(auth required)*
List user saved routes.

### `POST /api/account/saved-routes` *(auth required)*
Save a route.

Body fields:

- `routeName` *(required)*
- `routeStart` *(required)*
- `routeEnd` *(required)*
- `startTime` *(optional ISO datetime)*
- `endTime` *(optional ISO datetime)*
- `disruption` *(optional text)*

Returns `201` with `{ message, routeID }`.

### `DELETE /api/account/saved-routes/<route_id>` *(auth required)*
Remove saved route.

### `GET /api/account/notifications` *(auth required)*
Get latest notifications (up to 30).

### `PATCH /api/account/notifications/<notification_id>/read` *(auth required)*
Mark a notification as read.

### `POST /api/admin/notifications` *(auth required, admin only)*
Create a notification message.

Request body:

```json
{
  "message": "Service update: expect delays this evening.",
  "targetUserId": 123
}
```

- Omit `targetUserId` to broadcast to all users.
- Returns `201` with `{ message, count }`.

### `GET /api/account/weather-locations` *(auth required)*
List tracked weather locations.

### `POST /api/account/weather-locations` *(auth required)*
Track a location.

Body:

```json
{
  "location": "Lancaster"
}
```

### `DELETE /api/account/weather-locations/<location>` *(auth required)*
Remove tracked location.

---

## Stops and route planning

### `GET /api/gazetteer`
Return NPTG gazetteer data.

### `GET /api/naptan`
Return NaPTAN stop data.

Query parameters:

- `full=true|false` (default `false`)
- `dataset=<name>` (default `lancashire`; supports north west aliases)

### `GET /api/stops/search`
Autocomplete stop search from local stop cache.

Query parameters:

- `q` *(required, min length 2)*
- `limit` *(optional, max 50)*

### `POST /api/routes/search`
Search journey options between origin and destination.

Request body:

```json
{
  "from": { "name": "Lancaster", "atcoCode": "2400LAC30001", "lat": 54.0488, "lon": -2.8013 },
  "to": { "name": "Preston", "atcoCode": "2400LAA10001", "lat": 53.7593, "lon": -2.6993 },
  "sort_by": "soonest_arrival",
  "depart_time": "09:00"
}
```

Notes:

- `sort_by` accepts `soonest_arrival` or `fewest_changes`.
- `atcoCode` / `ATCOCode` is preferred when available.
- Returns 422 if stop resolution fails.
- Returns fallback mock routes when live route planning yields none.

### `GET /api/routes/metrics`
Return latest route-processing metrics.

---

## Bus and rail

### `GET /api/bus/timetable/<bus_code>`
Bus timetable data.

### `GET /api/bus/live/<bus_code>`
Live bus data.

### `GET /api/rail/corpus`
Rail corpus data.

### `GET /api/rail/departures/<crs_code>`
Rail departure board for station CRS code.

### `POST /api/translate/train_event`
Translate train event payload into human-readable values.

---

## Weather

### `GET /api/weather/search`
Location search with weather previews.

Query parameters:

- `q` *(required, min length 2)*
- `limit` *(optional, max 20)*

### `GET /api/weather`
Weather by coordinates.

Query parameters:

- `lat` *(required float)*
- `lon` *(required float)*

### `POST /api/weather/route` *(auth required)*
Weather along route points.

Request body:

```json
{
  "route_points": [
    { "latitude": 54.05, "longitude": -2.80, "name": "Lancaster" },
    { "latitude": 53.48, "longitude": -2.24, "name": "Manchester" }
  ]
}
```

### `GET /api/weather/icon/<icon_code>`
Returns weather icon PNG.

---

## Frontend fallback routes (non-API)

- `GET /` serves frontend `index.html`
- `GET /<path>` serves frontend static assets and SPA fallback (excluding `/api/*`)

---

## Source of truth

If this document and runtime behavior diverge, treat `backend/app.py` and backend tests in `backend/tests/` as source of truth and update this file.
