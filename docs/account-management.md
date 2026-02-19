# Account Management Integration

This document describes the account subsystem integrated into the scaffold.

## Overview

The account subsystem is implemented in the backend API and consumed from the frontend account modal.

### Backend

- Framework: Flask + SQLAlchemy
- Auth model: signed bearer token (`Authorization: Bearer <token>`)
- Data storage: MySQL (Docker Compose `mysql` service)

### Frontend

- Static UI + JavaScript integration in `frontend/src`
- API requests go to `/api/*` and are proxied by `frontend/server.js`

## Data model

Core tables are defined in [backend/migrations/account_management_schema.sql](../backend/migrations/account_management_schema.sql):

- `User`
- `Route`
- `Saves`
- `Notification`
- `UserWeather`

## API endpoints

### Authentication

- `POST /api/auth/register`
  - body: `{ "email", "userName", "password" }`
  - response: `{ "token", "user" }`
- `POST /api/auth/login`
  - body: `{ "email", "password" }`
  - response: `{ "token", "user" }`
- `POST /api/auth/logout`

### Account

- `GET /api/account/me`
- `PATCH /api/account/profile`
  - body: `{ "userName"?, "colorblindmode"? }`
- `PATCH /api/account/password`
  - body: `{ "currentPassword", "newPassword" }`
- `DELETE /api/account`
  - body: `{ "password" }`

### Saved routes

- `GET /api/account/saved-routes`
- `POST /api/account/saved-routes`
  - body: `{ "routeName", "routeStart", "routeEnd", "startTime"?, "endTime"?, "disruption"? }`
- `DELETE /api/account/saved-routes/:route_id`

### Notifications

- `GET /api/account/notifications`
- `PATCH /api/account/notifications/:notification_id/read`

### Weather tracking

- `GET /api/account/weather-locations`
- `POST /api/account/weather-locations`
  - body: `{ "location" }`
- `DELETE /api/account/weather-locations/:location`

## Security notes

- Passwords are stored as hashes (`werkzeug.security.generate_password_hash`).
- Protected routes require bearer token auth.
- Token expiry is controlled by `AUTH_TOKEN_MAX_AGE_SECONDS`.

## Frontend behavior summary

- Selecting Account opens login/register if no token is present.
- On successful login/register, token is stored in `localStorage`.
- Account modal loads current user profile and saved routes.
- Notifications panel is populated from account notifications when available.

## Next recommended improvements

1. Move to short-lived access token + refresh token rotation.
2. Add API rate limiting on auth endpoints.
3. Add automated migration tooling (Alembic / Flask-Migrate).
4. Add backend integration tests for auth and account lifecycle.
