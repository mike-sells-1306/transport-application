# Live Weather Panel Feature

## Overview
The weather panel displays **real-time weather data** for 22 towns and cities across the North West England region. When the user clicks the weather button (cloud icon in the top-right corner of the map), the panel opens and fetches live weather conditions from the backend API. Each location is displayed as a **clickable, expandable row** showing the weather icon (on a dark circular background for contrast), current temperature, and a chevron indicator. Clicking a row expands it to reveal detailed weather information (description, feels-like temperature, humidity, wind speed, cloud cover, and visibility).

A **search bar** at the top of the panel allows users to search for the weather at any named locality within the map bounds, powered by the NPTG gazetteer.

## How It Works

### Data Flow — Default Locations
```
User clicks weather button
        │
        ▼
toggleWeatherPanel() opens panel, clears search input
        │
        ▼
renderWeatherPanel() called
        │
        ▼
fetchWeatherForAllLocations()
  ├─► Checks local cache (5 min TTL)
  │     └─► If valid cache → return cached data
  └─► For each of 22 locations:
        GET /api/weather?lat={lat}&lon={lon}
              │
              ▼
        Backend (app.py) → TransportService.get_weather()
              │
              ▼
        WeatherAdapter.fetch_weather() → external weather API
              │
              ▼
        WeatherAdapter.parse_weather() → structured response
              │
              ▼
        Response: { temperature, icon, conditions, ... }
        │
        ▼
buildWeatherListItem(name, weather) for each location
  └─► Renders expandable row:
        [Town Name] [Icon on dark bg] [Temp °C] [▸ chevron]
          └─ Hidden detail section (click to expand):
              Description | Feels like | Humidity | Wind | Clouds | Visibility
```

### Data Flow — Weather Search
```
User types in search bar (e.g., "black")
        │
        ▼
initWeatherSearch() debounced handler (400ms)
        │
        ├─► Client-side: filter cached default locations by query
        │
        └─► Server-side: GET /api/weather/search?q=black&limit=5
              │
              ▼
        Backend (app.py) → weather_search()
              │
              ├─► Calls transport_service.get_gazetteer() → NPTGAdapter
              │     └─► Fetches & parses NPTG XML (namespace-aware)
              │     └─► Filters by bounds (53.37–54.62°N, -3.5–-2.21°W)
              │
              ├─► Filters localities whose name contains the query (case-insensitive)
              ├─► Deduplicates by name, sorts (starts-with matches first)
              │
              └─► For each match (up to limit):
                    GET /api/weather?lat=...&lon=...
                          │
                          ▼
                    Returns { name, lat, lon, weather }
        │
        ▼
renderWeatherSearchResults(results) + merge with cached defaults
  └─► Deduplicate by lowercase name, render with buildWeatherListItem()
```

### Frontend (main.js)

#### Key Functions

- **`buildWeatherListItem(name, weather)`**
  - Creates an expandable `<li class="weather-item">` for a single location.
  - The **summary row** (`<div class="weather-row">`) contains:
    - Location name
    - Weather icon on a **dark circular background** (`<span class="weather-icon-bg">`) for contrast against white/light icons
    - Temperature in integer °C
    - A chevron arrow (`▸`) that rotates 90° when expanded
  - The **detail section** (`<div class="weather-detail">`) is hidden by default and contains:
    - Description (red text, e.g., "overcast clouds")
    - Feels-like temperature
    - Humidity percentage
    - Wind speed and direction
    - Cloud cover percentage
    - Visibility distance in km
  - Clicking the row toggles the detail section open/closed via `max-height` CSS animation.

- **`fetchWeatherForAllLocations()`**
  - Calls `/api/weather?lat=...&lon=...` for all 22 locations using `Promise.allSettled()` (parallel requests).
  - Results are cached in the `weatherCache` variable with a 5-minute TTL to avoid hammering the API.
  - Returns an array of `{ name, weather }` objects.

- **`renderWeatherPanel()`**
  - Clears the weather list and shows a "Loading weather data…" message.
  - Awaits `fetchWeatherForAllLocations()`.
  - For each location, calls `buildWeatherListItem()` and appends it to the list.

- **`toggleWeatherPanel()`**
  - Toggles the weather panel visibility.
  - Clears the search input when opening.
  - When opening, calls `renderWeatherPanel()` to fetch/display live data.
  - Closes all other panels (notifications, FAQ, auth, account).

- **`initWeatherSearch()`**
  - Sets up a debounced `input` event listener on the search bar (400ms delay).
  - When the user types a query:
    1. Filters the cached default weather results by name (client-side).
    2. Calls `searchWeatherLocations(query)` to fetch additional results from the NPTG gazetteer.
    3. Merges and deduplicates both result sets by lowercase name.
    4. Renders the combined results.
  - When the search input is cleared, re-renders the full default panel.

- **`searchWeatherLocations(query)`**
  - Calls `GET /api/weather/search?q={query}&limit=5`.
  - Returns an array of `{ name, weather }` objects from the gazetteer search.

- **`renderWeatherSearchResults(results)`**
  - Clears the list and renders the given results using `buildWeatherListItem()`.
  - Shows "No matching locations found" if results are empty.

#### Weather Locations Array
The `weatherLocations` array in `main.js` contains all 22 locations (alphabetically sorted) with their coordinates:

| Location | Latitude | Longitude |
|----------|----------|-----------|
| Ambleside | 54.4316 | -2.9622 |
| Barrow-in-Furness | 54.1289 | -3.2269 |
| Blackburn | 53.7493 | -2.4841 |
| Blackpool | 53.8179 | -3.0510 |
| Carnforth | 54.1282 | -2.7701 |
| Cartmel | 54.2009 | -2.9529 |
| Fleetwood | 53.9220 | -3.0327 |
| Garstang | 53.9016 | -2.7735 |
| Grange-Over-Sands | 54.1931 | -2.9095 |
| Heysham | 54.0495 | -2.8903 |
| Kendal | 54.3290 | -2.7472 |
| Keswick | 54.6010 | -3.1376 |
| Kirkby-Lonsdale | 54.2018 | -2.5967 |
| Kirkham | 53.7827 | -2.8715 |
| Lancaster | 54.0488 | -2.8013 |
| Liverpool | 53.4072 | -2.9917 |
| Lytham-St-Annes | 53.7485 | -2.9991 |
| Manchester | 53.4795 | -2.2451 |
| Morecambe | 54.0721 | -2.8651 |
| Poulton-le-Fylde | 53.8461 | -2.9905 |
| Preston | 53.7593 | -2.6993 |
| Windermere | 54.3792 | -2.9063 |

### Backend API Endpoints

#### `GET /api/weather?lat={lat}&lon={lon}`
Fetches parsed weather data for a single coordinate pair.

**Response structure (from WeatherAdapter.parse_weather):**
```json
{
  "location": { "latitude": 54.0488, "longitude": -2.8013 },
  "temperature": { "current": 11.5, "feels_like": 9.2, "unit": "Celsius" },
  "atmospheric_conditions": { "humidity": 78, "pressure": 1013 },
  "wind": { "speed": 4.2, "direction_degrees": 220 },
  "visibility": { "distance": 10000 },
  "cloud_coverage": { "percentage": 75 },
  "conditions": { "code": "Clouds", "description": "broken clouds" },
  "icon": { "code": "04d", "icon_url": "/api/weather/icon/04d" },
  "timestamp": 1740600000
}
```

#### `GET /api/weather/icon/{icon_code}`
Returns the PNG image for the given weather icon code (e.g., `01d` for clear sky day, `10n` for rain at night).

#### `GET /api/weather/search?q={query}&limit={limit}`
Searches the NPTG gazetteer for named localities matching the query string, filtered to within the map bounds, and returns weather data for each match.

**Query Parameters:**
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `q` | Yes | — | Search query (minimum 2 characters) |
| `limit` | No | 5 | Maximum number of results (1–10) |

**Bounds Filter:** Only localities within the map region are returned:
- Latitude: 53.37°N to 54.62°N
- Longitude: -3.5°W to -2.21°W

**Response structure:**
```json
{
  "results": [
    {
      "name": "Blackburn",
      "lat": 53.74991,
      "lon": -2.484317,
      "weather": {
        "temperature": { "current": 10.49, "feels_like": 9.89, "unit": "Celsius" },
        "conditions": { "code": "Clouds", "description": "overcast clouds" },
        "icon": { "code": "04d", "icon_url": "/api/weather/icon/04d" },
        ...
      }
    }
  ]
}
```

**Sorting:** Results that start with the query string appear first, followed by results that contain it elsewhere.

**Common icon codes:**
| Code | Meaning |
|------|---------|
| 01d/01n | Clear sky |
| 02d/02n | Few clouds |
| 03d/03n | Scattered clouds |
| 04d/04n | Broken/overcast clouds |
| 09d/09n | Shower rain |
| 10d/10n | Rain |
| 11d/11n | Thunderstorm |
| 13d/13n | Snow |
| 50d/50n | Mist/fog |

### HTML Structure
```html
<section class="weather-panel hidden">
  <div class="panel-header">Weather</div>
  <div class="weather-search-wrapper">
    <input type="text" id="weather-search-input" class="weather-search-input"
           placeholder="Search location weather…" autocomplete="off" />
  </div>
  <ul class="weather-list" id="weather-list">
    <!-- Dynamically populated by renderWeatherPanel() / renderWeatherSearchResults() -->
    <!-- Each <li class="weather-item"> contains: -->
    <!--   <div class="weather-row"> (clickable, toggles detail) -->
    <!--     <span class="weather-location-name">Lancaster</span> -->
    <!--     <span class="weather-info"> -->
    <!--       <span class="weather-icon-bg"> (dark circular background) -->
    <!--         <img class="weather-icon-img" src="/api/weather/icon/04d" /> -->
    <!--       </span> -->
    <!--       <span class="weather-temp">12°C</span> -->
    <!--       <span class="weather-chevron">▸</span> -->
    <!--     </span> -->
    <!--   </div> -->
    <!--   <div class="weather-detail"> (hidden by default, expands on click) -->
    <!--     <div class="weather-detail-desc">overcast clouds</div> -->
    <!--     <div class="weather-detail-extras"> -->
    <!--       Feels like 10°C · Humidity 85% · Wind 4.2 m/s (220°) -->
    <!--       Clouds 75% · Visibility 10.0 km -->
    <!--     </div> -->
    <!--   </div> -->
  </ul>
</section>
```

### CSS Classes
| Class | Purpose |
|-------|---------|
| `.weather-search-wrapper` | Container for the search input with padding |
| `.weather-search-input` | Text input with red focus border for location search |
| `.weather-item` | Individual location list item with bottom border |
| `.weather-row` | Clickable flex row (name + info); hover shows light grey background |
| `.weather-location-name` | Left-aligned location name with ellipsis overflow |
| `.weather-info` | Flex container for icon + temperature + chevron on the right |
| `.weather-icon-bg` | **Dark circular background (#3a3a3a)** behind the icon for contrast against white/light icons |
| `.weather-icon-img` | 22×22px weather icon image from API |
| `.weather-temp` | Bold temperature text (right-aligned, min-width 38px) |
| `.weather-chevron` | Right-pointing arrow (▸) that rotates 90° when expanded, turns red |
| `.weather-detail` | Hidden expandable section (max-height animation 0→120px) |
| `.weather-detail-desc` | Description text in red (e.g., "overcast clouds") |
| `.weather-detail-extras` | Grey secondary info (feels-like, humidity, wind, clouds, visibility) |
| `.weather-loading` | Italic centered loading/error message |

## Caching Strategy
- **Client-side cache:** Weather data is stored in a `weatherCache` variable after the first fetch, with a `weatherCacheTimestamp`. If the panel is re-opened within 5 minutes, cached data is reused without making new API calls. The cached data is also used for instant client-side filtering when searching.
- **Server-side:** The external weather API bins locations into areas due to rate limits, so nearby locations may return identical data. This is noted in the API response.

## Error Handling
- If the backend is unreachable, the panel shows "Unable to load weather data".
- If an individual location fails, it displays `--°C` with no icon as a graceful fallback.
- All fetch calls use `Promise.allSettled()` so a single location failure does not block others.
- If the search endpoint fails or returns no results, a "No matching locations found" message is displayed.
- The search input requires a minimum of 2 characters before querying the backend.

## NPTG Gazetteer Integration
The weather search feature uses the **National Public Transport Gazetteer (NPTG)** to resolve location names to coordinates:
- The `NPTGAdapter` fetches and parses the NPTG XML file with proper namespace handling (`xmlns="http://www.naptan.org.uk/"`).
- Locality data is extracted from `NptgLocalities/NptgLocality` elements, including `NptgLocalityCode`, `LocalityName` (under `Descriptor`), and lat/lon (under `Location/Translation`).
- The `/api/weather/search` endpoint filters these localities to within the map bounds before searching by name.

## Adding New Weather Locations
To add a new location to the **default weather panel**, add an entry to the `weatherLocations` array in `main.js`:
```javascript
{ name: 'New Town', lat: 54.0000, lon: -2.5000 },
```
The location will automatically appear in the weather panel (alphabetically) on the next panel open.

Any locality within the map bounds that exists in the NPTG gazetteer can be searched for via the **search bar** without any code changes.

---

**Date:** 26 February 2026
