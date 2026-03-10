# Progress Report — 10 March 2026

**Project:** Transport for North West  
**Group:** Group 5-2  
**Report Date:** 10 March 2026  
**Previous Report:** 26 February 2026

---

## Overview

This report assesses the current implementation state of the Transport for North West application as of 10 March 2026, compared against the requirements and milestones defined in the Software Design Document (`main.tex`) and the findings documented in the 26 February 2026 progress report. The analysis is based solely on the contents of the repository.

---

## Changes Since Last Report (26 Feb → 10 Mar)

The following significant changes have been identified since the previous progress report:

### New and Substantially Reworked Features

| Feature | Description |
|---------|-------------|
| **Route Planning (T9, T10)** | The `RoutePlannerAdapter` (1,100+ lines) now plans multi-modal routes using **live rail departure boards** from the SCC API and a curated **bus-service knowledge base** (15 real Stagecoach/Arriva/Blackpool Transport services with stop sequences and frequencies). This replaces the previous empty placeholder / static mockup. |
| **Route Search Frontend (T9)** | Selecting both "from" and "to" stops via autocomplete now triggers `searchRoutes()`, which calls `POST /api/routes/search`. The Route Results Modal is dynamically populated with sortable (Fastest / Fewest Changes), expandable route rows showing per-leg detail (walk, bus, train, wait). |
| **Live Rail Departures** | New `RailDeparturesAdapter` parses real-time XML departure boards (`/rail/departures/<CRS>`) with full namespace support. Connecting routes via hub stations (Preston, Lancaster, Manchester, Oxenholme, Wigan) are computed from live data. |
| **Live Bus Integration** | `RoutePlannerAdapter` fetches and parses the SIRI live bus feed (`/bus/live`) to obtain real departure times and operational durations. Cached for 60 seconds. Falls back to headway-based estimation when the feed is unavailable. |
| **StopCache Database** | NaPTAN stops are loaded into a local `StopCache` SQLite table on startup via a background thread. Autocomplete searches now hit the local DB (word-order-independent matching) instead of re-fetching the external XML on every keystroke. A supplemental stop list (80+ entries) ensures all 22 map locations have stop coverage even if the upstream API is partial. |
| **Live Weather Panel** | Previously hardcoded; now calls `/api/weather?lat=…&lon=…` for all 22 locations via `Promise.allSettled()`, with 1-minute client-side cache, auto-refresh while the panel is open, expandable detail rows (feels-like, humidity, wind, clouds, visibility), and a search bar backed by the NPTG gazetteer (`/api/weather/search`). |
| **Colourblind Mode (T3)** | Full implementation: CSS `colorblind-mode` class applies a WCAG-safe blue/orange palette across the entire UI (sidebar, markers, focus rings, buttons, journey dots, route badges). Toggleable via sidebar "Accessibility" link (no login required) or account settings checkbox. Persists to `localStorage` for guests and to the server for authenticated users. |
| **Route Tests** | 17 new tests in `test_routes.py` covering endpoint validation, response schema, leg structure, mock generation, duration consistency, and sorting. |
| **Weather Tests** | 37 tests in `test_weather.py` covering point weather, route weather, icon proxy, and weather-location tracking (with mocking of the adapter). |

### Incremental Improvements

- "Cheapest" sort option removed (fare data unavailable — aligns with out-of-scope declaration).
- Weather icon proxy (`/api/weather/icon/<code>`) serves upstream PNG images through the backend.
- Route weather endpoint (`POST /api/weather/route`) returns weather for every waypoint along a journey.
- Swap button triggers route re-search when both stops are populated.
- Comprehensive supplemental stop data for all 22 map locations (Liverpool, Manchester, Keswick, Kendal, etc.).

---

## Milestone & Task Progress

### Milestone 1 — Base Website Structure

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T1** | Develop static page structure | ✅ Complete | Unchanged from previous report. SPA with sidebar, map, panels, modals. |
| **T2** | Implement interactive elements of pages | ✅ Complete | Route modal now fully dynamic. Weather panel fully dynamic. |
| **T3** | Add accessibility information | 🔶 Partial → Improved | **Colourblind mode fully implemented** on frontend (CSS theme + toggles + persistence). ARIA attributes on FAQ, weather items, autocomplete. Semantic HTML. Keyboard navigation. **Remaining:** WCAG 2.2 AA compliance audit not yet conducted. Screen-reader testing not evidenced. |

**Milestone 1 Progress: ~90% (was ~85%)**

---

### Milestone 2 — API Integration

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T4** | Weather API integration and fallback mechanism | ✅ Complete | **Backend:** WeatherAdapter fetches live data, parses into structured format. **Frontend:** Live weather panel with all 22 locations, expandable detail, search via gazetteer, 1-minute auto-refresh. Icon proxy. **Fallback:** Graceful degradation per-location (shows "—°C" if one fetch fails; others unaffected). |
| **T5** | Transport API integration with fallback mechanism | 🔶 Partial → Substantially Improved | **Adapters now operational:** NPTG gazetteer (XML namespace parsing), NaPTAN stops (full XML parsing + supplemental fallback), bus timetable, bus live (SIRI XML), rail corpus, **rail departures (real-time XML)**, route planner (live rail + bus knowledge base). **StopCache** provides local fallback when the external API is slow. **Remaining:** The STOMP/AMQP real-time data feed adapter (`LiveFeedAdapter`) was removed or never existed. Data translator dictionaries remain minimal (3–4 entries per lookup). |
| **T6** | Implement timetable viewing, download logic, and dataset switching | ❌ Not started | Backend endpoint `/api/bus/timetable/<bus_code>` exists. No frontend UI for viewing or downloading timetables. No dataset switching. |

**Milestone 2 Progress: ~65% (was ~40%)**

---

### Milestone 3 — Account System

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T7** | Account database implementation | ✅ Complete | Unchanged. SQLAlchemy models for User, Route, Save, Notification, UserWeather. |
| **T8** | User account management system | ✅ Complete | Full lifecycle. ~110 backend tests. Colourblind mode preference now synced between server and frontend. |

**Milestone 3 Progress: ✅ ~95% (unchanged)**

---

### Milestone 4 — Route Planning

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T9** | Implement route search, selection, and sorting functionality | ✅ Complete | **NEW.** Users select stops via autocomplete → `POST /api/routes/search` → Route modal dynamically populated. Sort by Fastest or Fewest Changes. Expandable route rows with per-leg detail (walk distance, intermediate stops, service names). |
| **T10** | Develop multi-modal journey planning logic | ✅ Complete | **NEW.** `RoutePlannerAdapter` builds routes from: (1) walk-only for < 2 km, (2) direct rail via live departure boards, (3) connecting rail via hub stations, (4) bus routes from 15-service knowledge base with live SIRI departure times. Multi-modal (bus + train) routes are fully supported. |
| **T11** | Implement the ability to save routes to user accounts | 🔶 Partial | Backend fully implemented. Frontend account modal renders saved routes. **Remaining:** No "Save" button on route results; the "Remove" button in account settings is not wired to the DELETE endpoint. |

**Milestone 4 Progress: ~80% (was ~15%)** — This is the single largest improvement since the last report.

---

### Milestone 5 — Notification and Alert System

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T12** | Develop weather alert and notification section | 🔶 Partial | Backend: UserWeather tracking + weather endpoints. Frontend: notification panel renders from API when logged in. **Missing:** No automated weather alert generation. Notifications are only created when saving routes (welcome notification on registration). |
| **T13** | Develop transport alert and notification system | ❌ Not started | No transport disruption detection logic. No mechanism to detect delays/cancellations from the rail departure boards and push notifications. The data is available (etd vs std comparisons in departure data) but no pipeline consumes it. |

**Milestone 5 Progress: ~25% (unchanged)**

---

### Milestone 6 — Integration of Map Logic

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T14** | Implement map interactivity | ✅ Complete | Leaflet map with 22 markers (now with colourblind-safe palette), popups, pan/zoom, bounds. |
| **T15** | Implement visualisation of routes onto maps | ❌ Not started | No polylines or route layers drawn on the map. The route data now contains lat/lon coordinates for all stops and could be visualised, but no frontend code draws them. |

**Milestone 6 Progress: ~50% (unchanged)**

---

### Milestone 7 — Testing

| Task | Description | Status | Notes |
|------|-------------|--------|-------|
| **T16** | Test functional correctness | 🔶 Partial → Improved | **~175+ backend tests** across 6 files: health (1), account (30), account comprehensive (72), weather (37), routes (17), plus conftest. Tests cover endpoint validation, response schemas, security edge cases (SQL injection, XSS), boundary values, and multi-user isolation. **No frontend/JavaScript tests.** |
| **T17** | Conduct usability tests | ❌ Not started | No evidence of usability testing. |
| **T18** | Validate UX against accessibility/inclusivity guidelines | ❌ Not started | Colourblind mode is now implemented, but no formal WCAG 2.2 AA audit or automated accessibility testing has been conducted. |

**Milestone 7 Progress: ~25% (was ~20%)**

---

## Functional Requirements Coverage

| ID | Requirement | Previous Status | Current Status | Evidence |
|----|-------------|-----------------|----------------|----------|
| **FR1** | Multi-modal journey planning | ❌ | ✅ Implemented | `RoutePlannerAdapter.plan_routes()` combines walk + bus + train legs. Frontend displays multi-modal routes. |
| **FR2** | Multi-operator integration | 🔶 | ✅ Implemented | Real-time rail (Northern, Avanti, TransPennine via live departure boards) + bus (Stagecoach, Arriva, Blackpool Transport, Kirkby Lonsdale Coaches). No preferential treatment. |
| **FR3** | Timetable information access | 🔶 | 🔶 Partial | Backend bus timetable proxy exists. Route planner shows scheduled times. **No dedicated timetable viewing UI.** |
| **FR4** | Live service information | ❌ | 🔶 Partial | Rail departure boards show real-time ETDs. Bus SIRI feed parsed for live departure times. **However:** No standalone "departure board" or "live tracking" UI. Live data is consumed only within route planning. |
| **FR5** | Disruption detection and handling | ❌ | 🔶 Partial | Rail departure parser skips cancelled services (`isCancelled`). ETD vs STD differences are available. **No proactive disruption alerts or alternative route suggestions triggered by disruptions.** |
| **FR6** | Route search and selection | ❌ | ✅ Implemented | Full search → sort → select → expand detail flow. |
| **FR7** | Geographic visualisation | 🔶 | 🔶 Partial | Map with stops/locations. **No route polylines.** |
| **FR8** | Interactive map interaction | ✅ | ✅ Complete | 22 markers with popups, pan/zoom, bounds, colourblind-safe markers. |
| **FR9** | Weather information integration | 🔶 | ✅ Implemented | Live weather for 22 locations + gazetteer search. Expandable detail. Auto-refresh. Route weather endpoint. |
| **FR10** | Accessibility information | ❌ | ❌ Not implemented | No stop/station accessibility data (step-free access, facilities) displayed anywhere. |
| **FR11** | Administrative data updates | ❌ | ❌ Not implemented | No admin interface or data update mechanism. |
| **FR12** | Account management | ✅ | ✅ Complete | Full CRUD lifecycle with auth, colourblind preference sync. |

**Functional Requirements Met: 6/12 fully (was 2/12), 4/12 partially (was 4/12), 2/12 not implemented (was 6/12).**

---

## Non-Functional Requirements Coverage

| ID | Category | Previous Status | Current Status | Notes |
|----|----------|-----------------|----------------|-------|
| **NFR1** | Performance (<4s) | ⚠️ Untested | ⚠️ Untested | Route planner makes multiple live API calls which may exceed 4s. No benchmarking. |
| **NFR2** | Scalability | ⚠️ Untested | ⚠️ Untested | No load testing. |
| **NFR3** | Reliability (fallback) | 🔶 Partial | 🔶 Improved | StopCache fallback (supplemental stops), weather graceful degradation, NaPTAN empty-XML fallback. Still no offline/cached route data. |
| **NFR4** | Availability (99%) | ⚠️ Untested | ⚠️ Untested | No monitoring. |
| **NFR5** | Data freshness (<8s) | ❌ N/A | 🔶 Partial | Rail departures are real-time. Bus SIRI feed cached 60s. Weather cached 60s client-side. |
| **NFR6** | Usability (first-time) | ⚠️ Untested | ⚠️ Untested | No usability testing. UI is significantly more complete. |
| **NFR7** | Accessibility (WCAG 2.2 AA) | ❌ | 🔶 Partial | Colourblind mode implemented. ARIA attributes present. No formal audit. |
| **NFR8** | Security | 🔶 Partial | 🔶 Partial | Unchanged: hashed passwords, token auth. Still no rate limiting, CSRF, or CORS configuration. |
| **NFR9** | Privacy | 🔶 Partial | 🔶 Partial | Unchanged. Minimal data collection. No privacy policy or consent flow. |
| **NFR10** | Maintainability | ✅ | ✅ Met | Adapter pattern, modular services, clear separation. Extensive documentation. |
| **NFR11** | Interoperability | ✅ | ✅ Met | REST APIs, XML/JSON parsing, standard protocols. |
| **NFR12** | Auditability | 🔶 Partial | 🔶 Partial | `app.logger` used throughout. No structured audit log. |
| **NFR13** | Ethical compliance | ❌ | ❌ Not implemented | No consent mechanism for user studies. |

---

## Discrepancies Between Previous Report and Current Codebase

The following items were reported as "not started" or "not implemented" on 26 February but are now present in the codebase — indicating **new progress not documented** in any intermediate report:

| Item | Previous Report (26 Feb) | Actual State (10 Mar) |
|------|-------------------------|-----------------------|
| Route search/selection/sorting (T9) | ❌ "Not started — static HTML mockup" | ✅ Fully dynamic with live API data |
| Multi-modal journey planning (T10) | ❌ "Not started — no algorithm" | ✅ `RoutePlannerAdapter` with rail+bus+walk |
| FR1 Multi-modal journey planning | ❌ "Not implemented" | ✅ Implemented |
| FR2 Multi-operator integration | 🔶 "No unified query" | ✅ Unified route planner querying multiple operators |
| FR6 Route search and selection | ❌ "Static mockup only" | ✅ Fully implemented |
| FR9 Weather information integration | 🔶 "Frontend hardcoded" | ✅ Fully live |
| Weather panel (T4 frontend) | "Frontend displays hardcoded static data" | ✅ Live API data with expandable detail and search |
| Colourblind mode (T3) | "Backend database field only — no frontend toggle" | ✅ Full CSS theme + sidebar + checkbox toggles |
| `test_routes.py` | Did not exist | 17 tests |
| `test_weather.py` | Did not exist | 37 tests |
| `StopCache` database | Did not exist | Background-loaded NaPTAN cache with supplemental stops |
| `RailDeparturesAdapter` | Did not exist | Full XML parser for live rail departure boards |
| `RoutePlannerAdapter` | Did not exist | 1,100+ line multi-modal route planner |

No discrepancies were found where the previous report **overstated** progress relative to the current codebase.

---

## Infrastructure & DevOps Status

| Component | Status |
|-----------|--------|
| Docker Compose (3-service stack: MySQL, backend, frontend) | ✅ Configured |
| Podman support via Makefile | ✅ Working |
| Backend Dockerfile (Python 3.11, gunicorn) | ✅ Working |
| Frontend Dockerfile (Node 18, Express proxy) | ✅ Working |
| Local dev workflow (`make run`) | ✅ Working with SQLite |
| Test workflow (`make test`) | ✅ Working with in-memory SQLite |
| CI/CD pipeline | ❌ Not configured |
| Seed data script | ❌ Empty placeholder |

---

## Summary Scorecard

| Milestone | Planned Tasks | Previous (26 Feb) | Current (10 Mar) | Δ |
|-----------|--------------|--------------------|--------------------|---|
| 1. Base Website Structure | T1, T2, T3 | ~85% | **~90%** | +5% |
| 2. API Integration | T4, T5, T6 | ~40% | **~65%** | +25% |
| 3. Account System | T7, T8 | ~95% | **~95%** | — |
| 4. Route Planning | T9, T10, T11 | ~15% | **~80%** | +65% |
| 5. Notifications & Alerts | T12, T13 | ~25% | **~25%** | — |
| 6. Map Logic | T14, T15 | ~50% | **~50%** | — |
| 7. Testing | T16, T17, T18 | ~20% | **~25%** | +5% |

**Overall estimated completion: ~62% (was ~40%)**

---

## Critical Path Analysis

Per the design document, the critical path is:

> T1 → T2 → T9 → T10 → T12 → T13 → T14 → T15 → T16 → T17 → T18

| Critical Path Task | Previous (26 Feb) | Current (10 Mar) |
|--------------------|--------------------|-------------------|
| T1 (Static page structure) | ✅ Done | ✅ Done |
| T2 (Interactive elements) | ✅ Done | ✅ Done |
| T9 (Route search/selection/sorting) | ❌ Not started | ✅ **Done** |
| T10 (Multi-modal planning logic) | ❌ Not started | ✅ **Done** |
| T12 (Weather alerts/notifications) | 🔶 Partial | 🔶 Partial |
| T13 (Transport alerts/notifications) | ❌ Not started | ❌ Not started |
| T14 (Map interactivity) | ✅ Done | ✅ Done |
| T15 (Route visualisation on map) | ❌ Not started | ❌ Not started |
| T16 (Functional testing) | 🔶 Partial | 🔶 Partial (improved) |
| T17 (Usability testing) | ❌ Not started | ❌ Not started |
| T18 (Accessibility validation) | ❌ Not started | ❌ Not started |

**The critical path is no longer blocked at T9/T10.** The bottleneck has moved to T12/T13 (notification automation) and T15 (route visualisation).

---

## Completed Features (Summary)

1. ✅ Single-page application with sidebar, interactive map, panels, and modals
2. ✅ Interactive Leaflet map with 22 location markers and image popups
3. ✅ Colourblind-accessible theme with toggle (sidebar + account settings)
4. ✅ Live weather panel with expandable detail and gazetteer search
5. ✅ Transport stop autocomplete (NaPTAN, StopCache, keyboard nav)
6. ✅ Multi-modal route planning (walk + bus + train, live data)
7. ✅ Route results modal with sort and expandable leg detail
8. ✅ Full account system (register, login, profile, password, delete)
9. ✅ Saved routes backend (save, list, unsave)
10. ✅ Notification infrastructure (create, list, mark read)
11. ✅ Weather location tracking (add, list, remove)
12. ✅ Docker Compose deployment (MySQL + backend + frontend)
13. ✅ 175+ automated backend tests

---

## Work In Progress

1. 🔶 Accessibility audit (colourblind mode done; WCAG 2.2 AA audit needed)
2. 🔶 Transport API fallback data (NaPTAN has fallback; bus/rail adapters have basic error handling but no cached fallback data)
3. 🔶 Disruption handling (cancelled services skipped; no proactive alerts)
4. 🔶 Saved route UI wiring (backend done; frontend "Save" and "Remove" buttons not wired)
5. 🔶 Data translator expansion (only 3–4 entries per lookup dictionary)

---

## Missing Requirements

| Priority | Item | Requirement(s) | Effort Estimate |
|----------|------|-----------------|-----------------|
| 🔴 High | Route visualisation on map (polylines) | FR7, T15 | Medium — route data has coords, needs Leaflet polyline layer |
| 🔴 High | Notification automation (weather alerts, transport disruption alerts) | FR5, T12, T13 | Medium — data sources available, pipeline needed |
| 🟠 Medium | Timetable viewing/download UI | FR3, T6 | Low–Medium — backend endpoint exists |
| 🟠 Medium | "Save Route" button in route results | FR6, T11 | Low — backend ready |
| 🟠 Medium | Stop/station accessibility information | FR10 | Medium — needs data source |
| 🟡 Lower | Administrative data update mechanism | FR11 | Medium |
| 🟡 Lower | Usability testing | NFR6, T17 | Effort depends on participant recruitment |
| 🟡 Lower | WCAG 2.2 AA audit | NFR7, T18 | Low–Medium — tooling available |
| 🟡 Lower | Security hardening (rate limiting, CSRF, CORS) | NFR8 | Low |
| 🟡 Lower | Privacy policy / consent flow | NFR9, NFR13 | Low |
| 🟡 Lower | CI/CD pipeline | — | Low |

---

## Potential Risks and Blockers

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Route planner performance** — multiple live API calls (rail departures + bus SIRI) per search may exceed the 4-second NFR1 target | Medium | High | Add caching of rail departure boards (TTL 30–60s). Parallelise API calls. Set timeouts aggressively. |
| **External API instability** — the SCC transport API (`transport.scc.lancs.ac.uk`) is a single point of failure for live data | Medium | High | StopCache already mitigates NaPTAN dependency. Extend to cache recent departure boards and weather data on the backend. |
| **No frontend tests** — all 175+ tests are backend-only; frontend regressions are undetectable | High | Medium | Introduce minimal Playwright or Cypress smoke tests covering the critical user flows (search → route display, weather panel, login). |
| **Timetable UI not started (T6)** — this is a distinct functional requirement (FR3) with no frontend work | Medium | Medium | Prioritise a basic timetable display component that calls the existing backend endpoint. |
| **Map route visualisation not started (T15)** — core deliverable for FR7 and Milestone 6 | Medium | High | Route data already contains lat/lon for every stop. Drawing Leaflet polylines is straightforward once prioritised. |
| **Notification pipeline absent (T12/T13)** — current critical-path bottleneck | Medium | High | Implement a periodic check (e.g. on weather fetch or route save) that generates notifications when disruptions or severe weather are detected. |
| **Scope of testing milestones (T17, T18)** — usability and accessibility testing require participant availability and planning | Medium | Medium | Begin WCAG automated tooling (axe-core, Lighthouse) immediately; schedule usability sessions early. |

---

## Recommended Priorities (Updated)

1. **🔴 URGENT — Route Map Visualisation (T15):** Draw route legs as Leaflet polylines. The route response already contains coordinates for every stop. This completes Milestone 6 and addresses FR7.
2. **🔴 URGENT — Notification Pipeline (T12, T13):** Implement automated alert generation. Compare rail ETD vs STD for delay detection. Check weather conditions for severe-weather alerts. Push notifications to users tracking affected routes or locations.
3. **🔴 HIGH — Save Route UI (T11):** Add a "Save" button to each route in the results modal. Wire the "Remove" button in account settings to the DELETE endpoint. This completes Milestone 4.
4. **🟠 HIGH — Timetable Viewing UI (T6):** Build a frontend component to display and optionally download timetable data from the existing backend endpoint.
5. **🟠 HIGH — Frontend Testing:** Add Playwright or Cypress smoke tests for the critical user flows to prevent regression.
6. **🟡 MEDIUM — Accessibility Audit (T18):** Run axe-core/Lighthouse. Address any WCAG 2.2 AA failures. Document results.
7. **🟡 MEDIUM — Usability Testing (T17):** Plan and schedule user testing sessions.
8. **🟢 LOWER — Security Hardening:** Add rate limiting on auth endpoints, CORS headers, CSRF tokens.
9. **🟢 LOWER — Data Translator Expansion:** Populate TOC, STANOX, reason code dictionaries from the full appendix.

---

*Report generated from repository analysis on 10 March 2026. All conclusions are based solely on the contents of the project repository.*
