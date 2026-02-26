# Transport Application Backend API Documentation

## Overview
This backend provides unified API endpoints for regional transport datasets and feeds, including account management and route saving. All endpoints return JSON.

---

## Endpoints

### Health
- `GET /health`
  - Returns API status.

### Hello
- `GET /api/hello`
  - Returns a welcome message.

### Gazetteer (NPTG)
- `GET /api/gazetteer`
  - Returns gazetteer data (National Public Transport Gazetteer).

### NaPTAN
- `GET /api/naptan?full=true|false`
  - Returns NaPTAN stop data. `full=true` for UK-wide, `false` for Lancashire only.

### Bus Timetable
- `GET /api/bus/timetable/<bus_code>`
  - Returns timetable for specified bus service.

### Bus Live
- `GET /api/bus/live/<bus_code>`
  - Returns live bus data for specified service.

### Rail Corpus
- `GET /api/rail/corpus`
  - Returns rail movement/event corpus.

### Translate Train Event
- `POST /api/translate/train_event`
  - Input: JSON train event object
  - Output: Translated event with human-readable fields (uses appendix mappings).

### Weather
- `GET /api/weather?lat=<latitude>&lon=<longitude>`
  - Returns current weather data for the specified coordinates
  - Parameters: latitude (float), longitude (float)
  - Output: Weather object with temperature, humidity, pressure, wind, visibility, cloud coverage, conditions, and icon code
  - Example: `/api/weather?lat=54.05&lon=-2.80`
  - Note: Data updated every few minutes, locations binned into areas due to API rate limits

- `POST /api/weather/route` (Requires Auth Token)
  - Get weather for all waypoints along a multi-modal route
  - Input: 
    ```json
    {
      "route_points": [
        {"latitude": 54.05, "longitude": -2.80, "name": "Lancaster Station"},
        {"latitude": 53.48, "longitude": -2.24, "name": "Manchester Piccadilly"}
      ]
    }
    ```
  - Output: Array of weather objects for each route point with location names

- `GET /api/weather/icon/<icon_code>`
  - Returns weather icon image in PNG format
  - Parameters: icon_code (e.g., '04n', '01d')
  - Output: PNG image file

### Account Management
- `POST /api/account/create`
  - Input: `{email, password, name}`
  - Output: Account creation result
- `POST /api/account/delete`
  - Input: `{email, password}`
  - Output: Account deletion result
- `POST /api/account/update`
  - Input: `{email, password, new_password}`
  - Output: Password update result
- `POST /api/account/save_route`
  - Input: `{email, route}`
  - Output: Route saved for user
- `GET /api/account/routes?email=<email>`
  - Output: List of saved routes for user

---

## Data Translation
- All codes and fields are mapped to human-readable values using the appendix from the HTML design report.

---

## Error Handling
- All endpoints return error messages and HTTP status codes for invalid input, missing data, or server errors.

---

## Example Usage
- See README.md for example API calls and expected responses.

---

## References
- [Transport Application Overview.html](../design/software-design-doc-source/Transport%20Application%20Overview.html)
- [main.tex](../design/software-design-doc-source/main.tex)

---

For further details, see the design report and appendix.
