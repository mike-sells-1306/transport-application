# Live Weather Panel Feature

## Overview
The weather panel displays **real-time weather data** for 22 towns and cities across the North West England region. When the user clicks the weather button (cloud icon in the top-right corner of the map), the panel opens and fetches live weather conditions from the backend API, displaying the correct weather icon and current temperature for each location.

## How It Works

### Data Flow
```
User clicks weather button
        │
        ▼
toggleWeatherPanel() opens panel
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
Render each location row:
  [Town Name]  [Weather Icon Image]  [Temp °C]
```

### Frontend (main.js)

#### Key Functions

- **`fetchWeatherForAllLocations()`**
  - Calls `/api/weather?lat=...&lon=...` for all 22 locations using `Promise.allSettled()` (parallel requests).
  - Results are cached in the `weatherCache` variable with a 5-minute TTL to avoid hammering the API.
  - Returns an array of `{ name, weather }` objects.

- **`renderWeatherPanel()`**
  - Clears the weather list and shows a "Loading weather data…" message.
  - Awaits `fetchWeatherForAllLocations()`.
  - For each location, creates a `<li>` element containing:
    - **Location name** (`<span class="weather-location-name">`)
    - **Weather icon** (`<img>` element sourced from `/api/weather/icon/{code}`)
    - **Temperature** (`<span class="weather-temp">`) in integer °C format (e.g., `12°C`)

- **`toggleWeatherPanel()`**
  - Toggles the weather panel visibility.
  - When opening, calls `renderWeatherPanel()` to fetch/display live data.
  - Closes all other panels (notifications, FAQ, auth, account).

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
  <ul class="weather-list" id="weather-list">
    <!-- Dynamically populated by renderWeatherPanel() -->
    <!-- Each <li> contains: -->
    <!--   <span class="weather-location-name">Lancaster</span> -->
    <!--   <span class="weather-info"> -->
    <!--     <img class="weather-icon-img" src="/api/weather/icon/04d" alt="broken clouds" /> -->
    <!--     <span class="weather-temp">12°C</span> -->
    <!--   </span> -->
  </ul>
</section>
```

### CSS Classes
| Class | Purpose |
|-------|---------|
| `.weather-location-name` | Left-aligned location name with ellipsis overflow |
| `.weather-info` | Flex container for icon + temperature on the right |
| `.weather-icon-img` | 28×28px weather icon from API |
| `.weather-temp` | Bold temperature text (right-aligned, min-width 42px) |
| `.weather-loading` | Italic centered loading/error message |

## Caching Strategy
- **Client-side cache:** Weather data is stored in a `weatherCache` variable after the first fetch, with a `weatherCacheTimestamp`. If the panel is re-opened within 5 minutes, cached data is reused without making new API calls.
- **Server-side:** The external weather API bins locations into areas due to rate limits, so nearby locations may return identical data. This is noted in the API response.

## Error Handling
- If the backend is unreachable, the panel shows "Unable to load weather data".
- If an individual location fails, it displays `--°C` with no icon as a graceful fallback.
- All fetch calls use `Promise.allSettled()` so a single location failure does not block others.

## Adding New Weather Locations
To add a new location to the weather panel, add an entry to the `weatherLocations` array in `main.js`:
```javascript
{ name: 'New Town', lat: 54.0000, lon: -2.5000 },
```
The location will automatically appear in the weather panel (alphabetically) on the next panel open.

---

**Author:** [Your Name]  
**Date:** 26 February 2026
