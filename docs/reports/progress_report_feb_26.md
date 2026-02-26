# Progress Report — 26 February 2026

**Project:** Transport for North West  
**Group:** Group 5-2  
**Report Date:** 26 February 2026  
**Submission Date (Design Doc):** 12 February 2026

---

## Overview

This report compares the current implementation status of the Transport for North West application against the milestones, task list, and functional/non-functional requirements defined in the Software Design Document (`main.tex`).

---

## Milestone & Task Progress

### Milestone 1 — Base Website Structure

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T1** | Develop static page structure | ✅ Complete | Single-page application with sidebar, interactive map area, route results modal, weather panel, notification panel, FAQ panel, auth modal, and account settings modal. |
| **T2** | Implement interactive elements of pages | ✅ Complete | Map markers (22 locations with image popups), panel toggles (weather, notifications), FAQ accordion, autocomplete search with keyboard navigation, swap button, account login/register/logout/settings flows. |
| **T3** | Add accessibility information | 🔶 Partial | ARIA attributes on FAQ panel (`aria-hidden`, `aria-expanded`, `aria-label`). Semantic HTML (`<aside>`, `<main>`, `<nav>`, `<section>`, `<label>`). Keyboard navigation on autocomplete. Basic responsive design (media query at 900px). **However: colour-blind mode exists only as a backend database field — no frontend toggle or CSS theme changes are implemented.** WCAG 2.2 AA compliance has not been validated. |

**Milestone 1 Verdict: ~85% complete.** Core structure and interactivity are solid. Accessibility is the gap.

---

### Milestone 2 — API Integration

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T4** | Weather API integration and fallback mechanism | 🔶 Partial | **Backend:** Weather adapter fetches live data from `transport.scc.lancs.ac.uk/weather`, translates it into structured format (temperature, wind, conditions, icon URL). Endpoints for point weather, route weather, and icon proxy all work. **Frontend:** Weather panel displays **hardcoded static data** (12 towns with fixed icons) — not wired to the live backend endpoints. No fallback mechanism is visible. |
| **T5** | Transport API integration with fallback mechanism | 🔶 Partial | **Backend:** Adapters exist for NPTG gazetteer (locality data), NaPTAN stops (full XML parsing with namespace support), bus timetable, bus live data, and rail corpus. NaPTAN has a 10-stop mock fallback. **However:** Live feed adapter (`LiveFeedAdapter`) is a **placeholder with empty methods** — STOMP/AMQP real-time data is not implemented. Data translator has only 3–4 entries per lookup dictionary. |
| **T6** | Implement timetable viewing, download logic, and dataset switching | ❌ Not started | Backend endpoint `/api/bus/timetable/<bus_code>` exists and proxies data, but **no frontend UI** for timetable viewing or download has been built. No dataset switching logic exists. |

**Milestone 2 Verdict: ~40% complete.** Backend adapters are functional but frontend integration is largely missing. Timetable UI is absent entirely.

---

### Milestone 3 — Account System

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T7** | Account database implementation | ✅ Complete | SQLAlchemy models for User, Route, Saves, Notification, and UserWeather. Schema SQL also provided for MySQL. In-memory SQLite used for development/testing. Passwords hashed with Werkzeug. Token-based auth via `itsdangerous`. |
| **T8** | User account management system | ✅ Complete | Full lifecycle: register (`POST /api/auth/register`), login (`POST /api/auth/login`), logout (`POST /api/auth/logout`), view profile (`GET /api/account/profile`), update username (`PATCH /api/account/profile`), update password (`PATCH /api/account/password`), delete account with password confirmation (`DELETE /api/account`). Frontend modals for login, register, and account settings all wired up. ~110 backend tests cover account flows including edge cases, SQL injection, XSS, and boundary values. |

**Milestone 3 Verdict: ✅ ~95% complete.** The account system is the most mature subsystem. Minor gaps: no rate limiting on auth endpoints, no CSRF protection, no email verification.

---

### Milestone 4 — Route Planning

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T9** | Implement route search, selection, and sorting functionality | ❌ Not started | The Route Results Modal exists as **static HTML mockup** (hardcoded "Lancaster to Blackpool" with 3 example routes and a sort dropdown). **No JavaScript** connects the autocomplete-selected stops to any route-search API. No backend route calculation endpoint exists. |
| **T10** | Develop multi-modal journey planning logic | ❌ Not started | No algorithm, API call, or service calculates routes between two stops. The transport adapters fetch raw timetable/live data per bus code but there is **no journey planner** that combines modes (bus + rail). |
| **T11** | Implement the ability to save routes to user accounts | 🔶 Partial | **Backend:** Fully implemented — `POST /api/account/routes` creates a Route + Save association, `GET /api/account/routes` lists saved routes, `DELETE /api/account/routes/<id>` removes saves. Notifications are generated on save. **Frontend:** Account settings modal renders saved routes list, but the **"remove" button is not wired** and there is no UI flow to save a route from search results (since route search doesn't exist yet). |

**Milestone 4 Verdict: ~15% complete.** This is the largest gap. Route planning is the core feature (FR1, FR2, FR6) and is essentially unimplemented. The save-routes backend is ready but has no frontend flow to feed it.

---

### Milestone 5 — Notification and Alert System

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T12** | Develop weather alert and notification section | 🔶 Partial | **Backend:** `UserWeather` tracking (add/remove/list locations). Weather data endpoints exist. Notification model stores alerts. **Frontend:** Notification panel toggles open and renders dynamically when logged in (fetches from `GET /api/account/notifications`). Static example notifications shown when logged out. **Missing:** No automated weather alert generation — notifications are only created as side effects of saving routes. No proactive weather-to-notification pipeline. |
| **T13** | Develop transport alert and notification system | ❌ Not started | No transport disruption detection. Live feed adapter is an empty placeholder. No mechanism to detect delays/cancellations and push notifications. |

**Milestone 5 Verdict: ~25% complete.** Notification infrastructure exists but automated alert generation for both weather and transport is missing.

---

### Milestone 6 — Integration of Map Logic

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T14** | Implement map interactivity | ✅ Complete | Leaflet map with 22 location markers, click-to-open image popups, pan/zoom, geographic bounds constraint (SW: 53.37°N 3.5°W to NE: 54.62°N 2.21°W), responsive resize handling, min/max zoom levels. |
| **T15** | Implement visualisation of routes onto maps | ❌ Not started | No polylines, route layers, or any route visualisation on the map. This depends on route planning (T9/T10) which is also not implemented. |

**Milestone 6 Verdict: ~50% complete.** Map interactivity is strong, but route visualisation — the key deliverable — is absent.

---

### Milestone 7 — Testing

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T16** | Test functional correctness | 🔶 Partial | ~150 backend tests across 4 files covering health, account management (comprehensive), and weather endpoints. Tests use in-memory SQLite. **No frontend/JavaScript tests exist.** Route planning cannot be tested as it doesn't exist. |
| **T17** | Conduct usability tests | ❌ Not started | No evidence of usability testing having been conducted. |
| **T18** | Validate UX against accessibility/inclusivity guidelines | ❌ Not started | No WCAG audit, no automated accessibility testing, no colour-blind mode in the frontend. |

**Milestone 7 Verdict: ~20% complete.** Backend test coverage is good for what exists, but frontend testing and user-facing validation are entirely absent.

---

## Functional Requirements Coverage

| ID | Requirement | Status | Evidence |
|----|-------------|--------|----------|
| **FR1** | Multi-modal journey planning | ❌ Not implemented | No journey planner exists |
| **FR2** | Multi-operator integration | 🔶 Partial | Transport adapters fetch bus + rail data, but no unified query |
| **FR3** | Timetable information access | 🔶 Partial | Backend endpoint exists; no frontend UI |
| **FR4** | Live service information | ❌ Not implemented | Live feed adapter is empty placeholder |
| **FR5** | Disruption detection and handling | ❌ Not implemented | No disruption logic |
| **FR6** | Route search and selection | ❌ Not implemented | Static mockup only |
| **FR7** | Geographic visualisation | 🔶 Partial | Map with stops/locations; no route visualisation |
| **FR8** | Interactive map interaction | ✅ Complete | 22 markers with popups, pan/zoom, bounds |
| **FR9** | Weather information integration | 🔶 Partial | Backend complete; frontend hardcoded |
| **FR10** | Accessibility information | ❌ Not implemented | No stop/station accessibility data displayed |
| **FR11** | Administrative data updates | ❌ Not implemented | No admin interface or data update mechanism |
| **FR12** | Account management | ✅ Complete | Full CRUD lifecycle with auth |

**Functional Requirements Met: 2/12 fully, 4/12 partially, 6/12 not implemented.**

---

## Non-Functional Requirements Coverage

| ID | Category | Status | Notes |
|----|----------|--------|-------|
| **NFR1** | Performance (<4s response) | ⚠️ Untested | No performance benchmarking done |
| **NFR2** | Scalability | ⚠️ Untested | No load testing |
| **NFR3** | Reliability (fallback data) | 🔶 Partial | NaPTAN has mock fallback; no other fallbacks |
| **NFR4** | Availability (99%) | ⚠️ Untested | No monitoring or uptime tracking |
| **NFR5** | Data freshness (<8s) | ❌ N/A | Live feeds not implemented |
| **NFR6** | Usability (first-time users) | ⚠️ Untested | No usability testing conducted |
| **NFR7** | Accessibility (WCAG 2.2 AA) | ❌ Not met | No audit, no colour-blind mode on frontend |
| **NFR8** | Security | 🔶 Partial | Passwords hashed, token auth; no rate limiting, CSRF, or CORS |
| **NFR9** | Privacy | 🔶 Partial | Minimal data collection; no privacy policy or consent flow |
| **NFR10** | Maintainability | ✅ Met | Modular architecture, adapter pattern, clear separation |
| **NFR11** | Interoperability | ✅ Met | Standard REST APIs, XML/JSON parsing |
| **NFR12** | Auditability | 🔶 Partial | Console logging exists; no structured audit log |
| **NFR13** | Ethical compliance | ❌ Not implemented | No consent mechanism for user studies |

---

## Infrastructure & DevOps Status

| Component | Status |
|-----------|--------|
| Docker Compose (3-service stack) | ✅ Configured (MySQL, backend, frontend) |
| Podman support | ✅ Via Makefile |
| Backend Dockerfile | ✅ Python 3.11, gunicorn |
| Frontend Dockerfile | ✅ Node 18, Express proxy |
| Local dev workflow (`make run`) | ✅ Working with SQLite |
| Test workflow (`make test`) | ✅ Working with in-memory SQLite |
| CI/CD pipeline | ❌ Not configured |
| Seed data script | ❌ Empty stub |

---

## Summary Scorecard

| Milestone | Planned Tasks | Progress | Critical? |
|-----------|--------------|----------|-----------|
| 1. Base Website Structure | T1, T2, T3 | **~85%** | On critical path — ✅ mostly done |
| 2. API Integration | T4, T5, T6 | **~40%** | On critical path — ⚠️ behind |
| 3. Account System | T7, T8 | **~95%** | Not on critical path — ✅ done |
| 4. Route Planning | T9, T10, T11 | **~15%** | On critical path — 🔴 significantly behind |
| 5. Notifications & Alerts | T12, T13 | **~25%** | On critical path — ⚠️ behind |
| 6. Map Logic | T14, T15 | **~50%** | On critical path — ⚠️ behind |
| 7. Testing | T16, T17, T18 | **~20%** | End of critical path — ⚠️ blocked by above |

**Overall estimated completion: ~40%**

---

## Critical Path Analysis

Per the design document, the critical path is:

> T1 → T2 → T9 → T10 → T12 → T13 → T14 → T15 → T16 → T17 → T18

| Critical Path Task | Status |
|--------------------|--------|
| T1 (Static page structure) | ✅ Done |
| T2 (Interactive elements) | ✅ Done |
| T9 (Route search/selection/sorting) | ❌ Not started |
| T10 (Multi-modal planning logic) | ❌ Not started |
| T12 (Weather alerts/notifications) | 🔶 Partial |
| T13 (Transport alerts/notifications) | ❌ Not started |
| T14 (Map interactivity) | ✅ Done |
| T15 (Route visualisation on map) | ❌ Not started |
| T16 (Functional testing) | 🔶 Partial |
| T17 (Usability testing) | ❌ Not started |
| T18 (Accessibility validation) | ❌ Not started |

**The critical path is blocked at T9 (route planning).** This is the single largest risk to project delivery.

---

## Recommended Priorities

1. **🔴 URGENT — Route Planning (T9, T10):** Implement a journey planning service that queries the existing transport adapters and returns routes between two selected stops. Wire the frontend autocomplete selections to this new endpoint and dynamically populate the Route Results Modal.
2. **🔴 HIGH — Frontend Weather Integration (T4):** Connect the existing weather panel to the live backend weather endpoints instead of displaying hardcoded data.
3. **🟠 HIGH — Route Visualisation (T15):** Once routes are calculable, draw them as polylines on the Leaflet map.
4. **🟠 HIGH — Timetable UI (T6):** Build a frontend component that calls the existing timetable endpoint and allows viewing/downloading.
5. **🟡 MEDIUM — Notification Automation (T12, T13):** Build pipelines that proactively generate weather and transport disruption alerts.
6. **🟡 MEDIUM — Accessibility (T3, T18):** Implement the colour-blind mode toggle on the frontend and conduct a WCAG 2.2 AA audit.
7. **🟢 LOWER — Testing & Validation (T16–T18):** Expand to frontend tests, usability studies, and accessibility validation once core features are in place.
