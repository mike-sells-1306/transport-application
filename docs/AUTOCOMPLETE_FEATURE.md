# Transport Stop Autocomplete Feature

## Overview

The Transport for North West application includes an intelligent autocomplete system that helps users search for valid bus and train stops within the defined geographic region. This feature ensures users can only select legitimate transport stops, improving data quality and user experience.

**Last Updated:** 25 February 2026  
**Author:** Transport for North West Development Team

---

## Table of Contents

1. [Feature Description](#feature-description)
2. [Technical Architecture](#technical-architecture)
3. [Implementation Details](#implementation-details)
4. [API Endpoint](#api-endpoint)
5. [Frontend Components](#frontend-components)
6. [User Experience](#user-experience)
7. [Geographic Bounds](#geographic-bounds)
8. [Data Sources](#data-sources)
9. [Code Examples](#code-examples)
10. [Troubleshooting](#troubleshooting)

---

## Feature Description

The autocomplete feature provides real-time search suggestions for both the "from" and "to" search inputs in the sidebar. As users type, the system:

- **Filters** bus and train stops from the NaPTAN (National Public Transport Access Nodes) database
- **Restricts** results to stops within the defined map boundaries
- **Displays** up to 10 matching suggestions in a dropdown menu
- **Enforces** selection from the dropdown (users must choose a valid stop)
- **Supports** keyboard navigation (arrow keys, Enter, Escape)
- **Debounces** search requests to reduce server load

### Key Benefits

- **Data Validation:** Only valid stops can be selected
- **User Guidance:** Suggestions help users discover available stops
- **Performance:** Debouncing and result limiting keep the system responsive
- **Accessibility:** Full keyboard navigation support
- **Regional Accuracy:** Only shows stops within the North West region

---

## Technical Architecture

### System Components

```
┌─────────────────┐
│   User Input    │
│  (from/to box)  │
└────────┬────────┘
         │ (types query)
         ▼
┌─────────────────┐
│   Debounce      │
│   (300ms)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Frontend JS    │
│  (main.js)      │
└────────┬────────┘
         │ GET /api/stops/search?q=query
         ▼
┌─────────────────┐
│  Backend API    │
│  (Flask/app.py) │
└────────┬────────┘
         │ get_naptan()
         ▼
┌─────────────────┐
│ Transport       │
│ Service         │
│ (NaPTAN Data)   │
└────────┬────────┘
         │ Filter by bounds
         │ Filter by query
         ▼
┌─────────────────┐
│  JSON Response  │
│  (stop list)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Dropdown UI    │
│  (suggestions)  │
└─────────────────┘
```

---

## Implementation Details

### Backend Implementation

**File:** `/backend/app.py`

The backend provides a new endpoint `/api/stops/search` that:

1. Accepts a query parameter `q` (minimum 2 characters)
2. Accepts an optional `limit` parameter (default 10, max 50)
3. Retrieves NaPTAN data from the transport service
4. Filters stops by geographic bounds
5. Filters stops by query match (case-insensitive)
6. Returns formatted stop data as JSON

**Geographic Bounds:**
- **Southwest Corner:** 53.3665°N, -3.5°W (Liverpool bottom, western coast)
- **Northeast Corner:** 54.6200°N, -2.211°W (Keswick top, Manchester right edge)

**Response Format:**
```json
{
  "stops": [
    {
      "name": "Blackpool Tower (Stop A), Blackpool",
      "atcoCode": "2400LAA00123",
      "lat": 53.8179,
      "lon": -3.0510,
      "stopType": "bus"
    }
  ]
}
```

### Frontend Implementation

**Files Modified:**
- `/frontend/src/index.html` - Added autocomplete wrapper divs
- `/frontend/src/style.css` - Added autocomplete styling
- `/frontend/src/main.js` - Added autocomplete logic

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `initializeAutocomplete()` | Sets up autocomplete for both inputs |
| `setupAutocomplete()` | Attaches event listeners to an input |
| `searchStops()` | Calls the backend API with the query |
| `displaySuggestions()` | Renders suggestions in the dropdown |
| `selectStop()` | Handles stop selection |
| `updateSelectedSuggestion()` | Manages keyboard navigation |
| `getSelectedStops()` | Returns currently selected stops |

---

## API Endpoint

### `GET /api/stops/search`

**Description:** Search for transport stops within the map bounds

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query (min 2 chars) |
| `limit` | integer | No | 10 | Max results (max 50) |

**Example Request:**
```bash
curl "http://localhost:5000/api/stops/search?q=blackpool&limit=5"
```

**Example Response:**
```json
{
  "stops": [
    {
      "name": "Blackpool Tower (Stop A), Blackpool",
      "atcoCode": "2400LAA00123",
      "lat": 53.8179,
      "lon": -3.0510,
      "stopType": "bus"
    },
    {
      "name": "Blackpool North Railway Station, Blackpool",
      "atcoCode": "9100BKPN",
      "lat": 53.8212,
      "lon": -3.0507,
      "stopType": "rail"
    }
  ]
}
```

**Error Response:**
```json
{
  "error": "Error message",
  "stops": []
}
```

**Status Codes:**
- `200 OK` - Success (even if no results)
- `500 Internal Server Error` - Server error

---

## Frontend Components

### HTML Structure

```html
<div class="autocomplete-wrapper">
  <input id="from-input" type="text" placeholder="Search…" autocomplete="off" />
  <div class="autocomplete-suggestions" id="from-suggestions"></div>
</div>
```

### CSS Classes

| Class | Purpose |
|-------|---------|
| `.autocomplete-wrapper` | Container for input and suggestions |
| `.autocomplete-suggestions` | Dropdown container |
| `.autocomplete-suggestions.visible` | Shows the dropdown |
| `.autocomplete-suggestion-item` | Individual suggestion |
| `.autocomplete-suggestion-item.selected` | Keyboard-selected item |
| `.autocomplete-no-results` | "No results" message |

### Styling Details

**Colors:**
- Background: `#1a1a1a` (dark grey matching input boxes)
- Border: `#444` (subtle grey)
- Hover: `#2a2a2a` (lighter grey)
- Text: `#fff` (white)

**Dimensions:**
- Max height: `240px` (scrollable)
- Border radius: `10px` (matching UI)
- Padding: `10px 14px` per item

---

## User Experience

### Interaction Flow

1. **User Types:** User begins typing a location name (e.g., "black")
2. **Debounce Wait:** System waits 300ms for user to finish typing
3. **Search Request:** Frontend sends request to `/api/stops/search`
4. **Results Display:** Suggestions appear in dropdown below input
5. **User Selection:** User clicks or presses Enter on a suggestion
6. **Value Set:** Input box fills with the selected stop name
7. **Dropdown Closes:** Suggestions hide automatically

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `↓` (Down Arrow) | Move to next suggestion |
| `↑` (Up Arrow) | Move to previous suggestion |
| `Enter` | Select highlighted suggestion |
| `Escape` | Close suggestions dropdown |
| `Tab` | Move to next input field |

### Mouse Interaction

- **Hover:** Highlights suggestion with background color
- **Click:** Selects suggestion and closes dropdown
- **Click Outside:** Closes all open dropdowns

### Visual Feedback

- **Typing:** Cursor visible, input accepts text
- **Loading:** Brief delay (300ms) before suggestions appear
- **Hover State:** Background changes to `#2a2a2a`
- **Selected State:** Same styling as hover
- **No Results:** Italic grey text: "No stops found within the region"
- **Error State:** "Error loading stops" message

---

## Geographic Bounds

The system enforces strict geographic boundaries matching the visible map area:

### Boundary Coordinates

```javascript
const MIN_LAT = 53.3665; // Bottom of Liverpool
const MAX_LAT = 54.6200; // Top of Keswick
const MIN_LON = -3.5;    // Western coast
const MAX_LON = -2.211;  // Far right of Manchester
```

### Included Areas

- **South:** Liverpool metropolitan area
- **Central:** Preston, Blackpool, Fylde, Wyre coast
- **North:** Lancaster, Morecambe Bay region
- **Lake District:** Windermere, Ambleside, Keswick, Kendal
- **East:** Manchester outskirts, Blackburn

### Excluded Areas

Stops outside these bounds are filtered out automatically:
- Areas south of Liverpool (e.g., Chester, Warrington)
- Areas north of Keswick (Scottish borders)
- Areas east of Manchester (Yorkshire)
- Areas west of the Irish Sea coast

---

## Data Sources

### NaPTAN Database

The system uses the **National Public Transport Access Nodes (NaPTAN)** database, which provides:

- **Bus Stops:** All registered bus stops in the UK
- **Train Stations:** All railway stations
- **Tram Stops:** Light rail and metro stops
- **Ferry Terminals:** Maritime transport nodes

**Data Fields Used:**
- `CommonName` - Stop name (e.g., "Blackpool Tower")
- `Indicator` - Stop identifier (e.g., "Stop A")
- `LocalityName` - Town/area name (e.g., "Blackpool")
- `ATCOCode` - Unique stop identifier
- `Latitude` - Decimal degrees
- `Longitude` - Decimal degrees
- `StopType` - bus, rail, tram, ferry, etc.

### Data Freshness

The NaPTAN data is accessed through the SCC Transport API, which provides up-to-date stop information. The backend caches this data internally to improve performance.

---

## Code Examples

### Accessing Selected Stops

```javascript
// Get both selected stops
const stops = getSelectedStops();

console.log('From stop:', stops.from);
console.log('To stop:', stops.to);

// Example output:
// From stop: {
//   name: "Preston Bus Station, Preston",
//   atcoCode: "2400LAA10987",
//   lat: 53.7593,
//   lon: -2.6993,
//   stopType: "bus"
// }
```

### Validating User Input

```javascript
// Check if user has selected valid stops before submission
function validateSearchInputs() {
  const stops = getSelectedStops();
  
  if (!stops.from) {
    alert('Please select a valid starting location');
    return false;
  }
  
  if (!stops.to) {
    alert('Please select a valid destination');
    return false;
  }
  
  return true;
}
```

### Custom Search Limit

```javascript
// Modify the API call to request more results
async function searchStops(query, suggestionsContainer, input, inputType) {
  const response = await fetch(
    `/api/stops/search?q=${encodeURIComponent(query)}&limit=20`
  );
  // ... rest of function
}
```

### Programmatic Stop Selection

```javascript
// Programmatically set a stop (useful for "Use My Location" features)
function setStop(inputType, stopData) {
  const input = document.getElementById(`${inputType}-input`);
  input.value = stopData.name;
  selectedStops[inputType] = stopData;
}

// Usage:
setStop('from', {
  name: "Lancaster Bus Station, Lancaster",
  atcoCode: "2400LAA11234",
  lat: 54.0488,
  lon: -2.8013,
  stopType: "bus"
});
```

---

## Troubleshooting

### Issue: Suggestions Not Appearing

**Possible Causes:**
1. Query is less than 2 characters
2. Backend is not running
3. No stops match the query within bounds
4. Network error

**Solutions:**
- Type at least 2 characters
- Ensure backend is running on port 5000
- Check browser console for errors
- Verify backend logs for API errors

### Issue: Wrong Stops Appearing

**Possible Causes:**
1. Stops are outside the intended region
2. NaPTAN data includes unexpected stops
3. Geographic bounds are incorrect

**Solutions:**
- Verify the MIN/MAX LAT/LON values in `/backend/app.py`
- Check that `get_naptan()` returns correct data
- Review NaPTAN data source for accuracy

### Issue: Slow Performance

**Possible Causes:**
1. Debounce delay too short
2. Too many results returned
3. NaPTAN data not cached

**Solutions:**
- Increase debounce delay from 300ms to 500ms
- Reduce limit parameter (default 10)
- Implement backend caching for NaPTAN data

### Issue: Dropdown Styling Issues

**Possible Causes:**
1. CSS not loaded
2. Z-index conflicts
3. Wrapper positioning incorrect

**Solutions:**
- Verify `style.css` is loaded
- Increase `.autocomplete-suggestions` z-index
- Check that `.autocomplete-wrapper` has `position: relative`

### Issue: Keyboard Navigation Not Working

**Possible Causes:**
1. Input focus lost
2. Event listeners not attached
3. Suggestions not visible

**Solutions:**
- Ensure input has focus
- Check that `setupAutocomplete()` is called
- Verify suggestions have `.visible` class

---

## Browser Compatibility

The autocomplete feature is compatible with:

- **Chrome/Chromium:** 60+
- **Firefox:** 55+
- **Safari:** 12+
- **Edge:** 79+

**Required Browser Features:**
- ES6 JavaScript (arrow functions, async/await, template literals)
- Fetch API
- CSS Grid/Flexbox
- classList API

---

## Future Enhancements

Potential improvements for future versions:

1. **Fuzzy Matching:** Use Levenshtein distance for typo tolerance
2. **Recent Searches:** Store and suggest previously searched stops
3. **Favorites:** Allow users to save frequently used stops
4. **Stop Icons:** Display bus/train icons in suggestions
5. **Distance Sorting:** Sort results by proximity to user location
6. **Multi-Language:** Support Welsh and other regional languages
7. **Offline Mode:** Cache stops for offline use
8. **Voice Input:** Speech-to-text for accessibility
9. **Route Previews:** Show route previews on hover
10. **Stop Details:** Display stop facilities (shelter, real-time displays, etc.)

---

## Related Documentation

- [API Documentation](../backend/API_DOCUMENTATION.md)
- [Account Management](./account-management.md)
- [Frontend UI Guide](../frontend/src/index.md)
- [Backend Status](../backend/BACKEND_STATUS.md)

---

## Support

For technical support or questions about this feature:

- **Email:** support@transportfornorthwest.uk
- **GitHub Issues:** [Create an issue](https://github.com/transport-nw/issues)
- **Developer Forum:** [Discussion Board](https://forum.transportfornorthwest.uk)

---

**Document Version:** 1.0  
**Last Reviewed:** 25 February 2026  
**Next Review:** March 2026
