# Transport for North West Web UI

## Overview
This project is a desktop-style web application interface for a regional travel service called **Transport for North West**. It is built using HTML, CSS, and JavaScript with an integrated **OpenStreetMap** interactive map powered by **Leaflet.js**. The design focuses on bold branding, clear layout, and modern UI practices with a fixed sidebar, dynamic interactive map, and layered modal panels.

## Technology Stack
- **Frontend Framework:** HTML5, CSS3, Vanilla JavaScript
- **Mapping Library:** Leaflet.js 1.9.4 (open-source JavaScript library)
- **Map Provider:** OpenStreetMap (free, open-source map data)
- **Region Focus:** Coastal North West England (Preston–Lancaster corridor, including Blackpool, the Fylde, and the Wyre coast)

## File Structure
- `index.html`: Main HTML file containing the structure and content of the UI.
- `style.css`: Main stylesheet for visual styling and layout.
- `main.js`: JavaScript application logic for map initialization, interactivity, and panel management.
- `index.md`: Documentation file (this file).

## How the Code Works

### 1. Map Integration
- **Purpose:** Provides an interactive, zoomable map of the North West England region.
- **Implementation:**
  - Uses **Leaflet.js** library, a lightweight and flexible mapping solution.
  - Connects to **OpenStreetMap** tiles for real-time, crowd-sourced map data.
  - Map is centered at coordinates `[53.88, -3.02]` (Fylde/Wyre coastline) with initial zoom level 11.
  - Markers are placed at key towns: Preston, Blackpool, Lancaster, Morecambe, Fleetwood, Wyre Coast, and Poulton-le-Fylde.
  - Each marker is styled with red circles matching the branding color scheme.
  - Clicking a marker opens a single Leaflet popup containing an optional image and a description.
  - Map is constrained to the coastal region with bounds to prevent excessive panning.

### 2. Sidebar Navigation
- **Purpose:** Provides persistent navigation and search controls.
- **Implementation:**
  - Fixed to the left, always visible.
  - Top section uses deep red for branding and service title.
  - Below, a lighter red panel contains a travel prompt and two input fields ("Search…" and "to") for journey planning.
  - A circular icon button for swapping or submitting destinations.
  - Navigation links (Account, FAQ, Customer Support) at the bottom.

### 3. Interactive Panels
- **Route Modal:**
  - Appears when a route search is performed.
  - Large red panel with header, sort dropdown, and stacked route results.
  - Each route row shows a transport icon, times, and duration.

- **Weather Panel:**
  - Opens from the top-right icon button.
  - Lists towns and weather icons in a light grey rounded panel.

- **Notifications Panel:**
  - Opens from the top-right icon button.
  - Lists announcements with timestamps.

- **Account Modal:**
  - Displays account settings.
  - Red header, avatar, username, saved routes, and action buttons.

### 4. Interactive Map Features
- **Markers & Popups:** Click any red marker to view location details and an image (if available) in a single popup.
- **Zoom Controls:** Use the + and - buttons in the top-left of the map or scroll wheel.
- **Pan:** Click and drag to move around the map.
- **Bounds Limiting:** Map restricts panning to the coastal Preston–Lancaster corridor.
- **Responsive Design:** Map resizes with window to fill the available space.

### 5. JavaScript Application Flow
The `main.js` file handles:
- **Map Initialization:** `initializeMap()` creates and configures the Leaflet map instance.
- **Location Data:** Array of 7 key towns with coordinates, descriptions, and optional images.
- **Marker Management:** Adds interactive markers with a single popup per marker.
- **Event Listeners:** Sets up click handlers for weather, notification, and marker interactions.
- **Panel Toggling:** Functions to show/hide weather and notification panels.
- **Backend Health Check:** Attempts to connect to backend API (if running).

## Why the Code Works

### Separation of Concerns
- **HTML:** Provides semantic structure and page layout.
- **CSS:** Handles all visual styling, colors, and responsive design.
- **JavaScript:** Manages interactivity, map initialization, and dynamic content.

### Performance
- **Leaflet.js:** Lightweight (~40KB), optimized for mapping applications.
- **CDN Delivery:** CSS and JavaScript libraries are loaded from CDNs for fast delivery.
- **Minimal Dependencies:** No heavy frameworks; vanilla JavaScript for control and simplicity.

### Maintainability
- **CSS Variables:** Easy color and spacing updates at the top of `style.css`.
- **Modular JavaScript:** Functions are clearly named and separated by responsibility.
- **Inline SVG Icons:** No external icon files; small data URIs reduce HTTP requests.

### Accessibility
- **Semantic HTML:** Uses proper elements like `<aside>`, `<main>`, `<nav>`, `<section>`.
- **Form Labels:** Input fields have associated labels for screen readers.
- **Alt Text:** Images include descriptive alt attributes.

## Map Coordinate Reference
- **Preston:** 53.7578° N, 2.7059° W
- **Blackpool:** 53.8160° N, 3.0500° W
- **Lancaster:** 54.0466° N, 2.8015° W
- **Morecambe:** 54.0740° N, 2.8650° W
- **Fleetwood:** 53.9176° N, 3.0102° W
- **Wyre Coast:** 53.8820° N, 3.0380° W
- **Poulton-le-Fylde:** 53.8468° N, 2.9920° W

## OpenStreetMap Attribution
The map data is provided by OpenStreetMap contributors under the Open Data Commons Open Database License. Attribution is automatically displayed in the map corner.

## How to Use
1. Open `index.html` in a web browser or start the frontend server.
2. The interactive map will load, centered on the North West region.
3. Click any red marker to view location details (and image if available) in the popup.
4. Use zoom controls (+ and - buttons) or scroll to zoom in/out.
5. Click the weather (cloud) or notification (bell) icons to toggle side panels.
6. Navigate using the sidebar links or search bar.

## Customization

### Add New Locations
Edit the `locations` array in `main.js` to add new markers:
```javascript
const locations = [
  {
    name: 'Town Name',
    lat: 53.0,
    lng: -2.5,
    description: 'Town description',
    image: '../../docs/software-design-doc-source/Assets/town_name.png',
  },
  // ... more locations
];
```

### Change Map Styling
Update CSS variables in `style.css`:
```css
:root {
  --red-main: #b71c1c;
  --red-light: #d32f2f;
  /* ... etc */
}
```

### Zoom/Pan Constraints
Modify bounds in `initializeMap()`:
```javascript
const bounds = L.latLngBounds(
  L.latLng(53.68, -3.28),  // Southwest corner
  L.latLng(54.12, -2.62)   // Northeast corner
);
```

### Alternative Map Providers
Replace the tile layer URL to use different providers (e.g., Mapbox, USGS):
```javascript
L.tileLayer('https://api.mapbox.com/styles/v1/{id}/static/{lon},{lat},{z}/{width}x{height}...', { ... })
```

## Browser Compatibility
- Chrome/Chromium 60+
- Firefox 55+
- Safari 12+
- Edge 79+

---

**Author:** [Your Name]  
**Date:** 19 February 2026  
**Last Updated:** 19 February 2026 (Leaflet/OpenStreetMap Integration)
