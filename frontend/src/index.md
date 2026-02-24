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
  - Markers are placed at 23 key towns across the North West and Lake District regions, centered at the town center coordinates from OpenStreetMap.
  - Each marker is styled with red circles matching the branding color scheme.
  - Clicking a marker opens a Leaflet popup containing the town name, optional image, and description.
  - **Popup Toggle:** The popup system intelligently manages marker interactions:
    - Click a marker → Opens its popup
    - Click a different marker → Automatically closes the previous popup and opens the new one
    - Click the same marker again → Closes the popup
    - Only one popup is visible at a time, ensuring a clean interface.
  - **Map Bounds & Constraints:** Map bounds are strictly constrained with hard limits at the edges of specific towns and coast:
    - **East:** Far right edge of Manchester (longitude -2.211°W)
    - **South:** Bottom edge of Liverpool (latitude 53.3665°N)
    - **West:** Most western extent of the North West coast with included sea (longitude -3.5°W)
    - **North:** Top edge of Keswick (latitude 54.6200°N)
  - Users **cannot pan or zoom beyond these bounds** at any zoom level. The map will refuse to show areas outside this rectangle.
  - **Responsive Zoom:** The map automatically adjusts its zoom level when the window is resized or switched to fullscreen, maintaining the same geographic view bounds without stretching. This ensures the same geographic area is visible whether viewing in a windowed or fullscreen state.

### 2. Sidebar Navigation
- **Purpose:** Provides persistent navigation and search controls.
- **Implementation:**
  - Fixed to the left, always visible.
  - Top section uses deep red for branding and service title.
  - Below, a lighter red panel contains a travel prompt and two input fields ("Search…" and "to") for journey planning.
  - A circular icon button for swapping or submitting destinations.
  - Navigation links (Account, FAQ, Customer Support) at the bottom with hover highlighting that displays a semi-transparent white background when the mouse hovers over them, making the interactive state obvious.

### 3. Interactive Panels
- **Route Modal:**
  - Appears when a route search is performed.
  - Large red panel with header, sort dropdown, and stacked route results.
  - Each route row shows a transport icon, times, and duration.

- **Weather Panel:**
  - Opens from the top-right icon button (cloud icon).
  - Weather button has hover effect with darker background and enhanced shadow.
  - Lists towns and weather icons in a light grey rounded panel.
  - Automatically closes other panels (notifications, FAQ, account modals) when opened.

- **Notifications Panel:**
  - Opens from the top-right icon button (bell icon).
  - Notification button has hover effect with darker background and enhanced shadow.
  - Lists announcements with timestamps.
  - Automatically closes other panels (weather, FAQ, account modals) when opened.

- **FAQ Panel:**
  - Opens from the FAQ link in the sidebar.
  - Displays common questions about the UI and map usage as a centered modal dialog.
  - Fixed width (700px) with responsive height (max 80vh) to maintain consistent sizing whether in windowed or fullscreen mode.
  - Close button (×) uses `user-select: none` to prevent accidental text selection when hovering/clicking.
  - Each question expands to reveal its answer.
  - When the FAQ panel is closed, all expanded answers are automatically collapsed, ensuring a clean state when reopened.
  - Automatically closes other panels (weather, notifications, account modals) when opened.
  - Includes a visible close button to return to the map.

- **Account Modal:**
  - Displays account settings.
  - Red header, avatar, username, saved routes, and action buttons.
  - Automatically closes other panels (weather, notifications, FAQ) when opened.

### 4. Interactive Map Features
- **Markers & Popups:** Click any red marker to open its popup showing the location name, optional image, and description. The popup behavior is intelligent:
  - **First click on a marker:** Opens the popup for that location.
  - **Click on a different marker:** Automatically closes the previous popup and opens the new one.
  - **Click the same marker again:** Closes that marker's popup. Only one popup is visible at a time.
  - **Hover Effect:** When you hover your mouse over a red marker, it transforms to a brighter red color (#ff5252 fill, #e53935 border) and displays a glowing shadow effect for enhanced visibility and clear interactivity indication.
- **Zoom Controls:** Use the + and - buttons in the top-left of the map or scroll wheel to zoom in/out. Zoom is constrained between levels 9–19.
- **Pan:** Click and drag to move around the map. Panning is restricted and cannot exceed the defined bounds.
- **Responsive Zoom:** The zoom level automatically adjusts when you resize the browser window or switch between windowed and fullscreen modes. This maintains consistent geographic visibility—the same geographic area stays in view regardless of window size, without stretching the map.
- **Bounds Enforcement:** Hard geographic bounds prevent users from seeing beyond:
  - **South:** Bottom edge of Liverpool (53.3665°N)
  - **North:** Top edge of Keswick (54.6200°N)
  - **West:** Most western coast of the North West with included sea (-3.5°W)
  - **East:** Far right edge of Manchester (-2.211°W)
  - The map will automatically stop and prevent panning or zooming to reveal areas outside these limits.
- **Responsive Design:** Map resizes with window to fill the available space.

### 5. JavaScript Application Flow
The `main.js` file handles:
- **Map Initialization:** `initializeMap()` creates and configures the Leaflet map instance.
- **Location Data:** Array of 23 towns across North West England and the Lake District with accurate town center coordinates, descriptions, and optional images.
- **Marker Management:** Adds interactive markers with a single popup per marker, including toggle functionality.
- **Event Listeners:** Sets up click handlers for weather, notification, and marker interactions.
- **FAQ Interaction:** Opens the FAQ panel, toggles answers, and closes the panel. When closing, automatically collapses all expanded answers for a clean state on next open.
- **Panel Toggling:** Functions to show/hide weather and notification panels. All panel-opening functions automatically close other open panels to prevent overlapping UI elements.
- **Panel Coordination:** When any panel (weather, notifications, FAQ, account) is opened, all other panels are automatically closed to maintain a clean, focused interface.
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
All coordinates are in decimal degrees (latitude, longitude). All markers are positioned at town centers based on OpenStreetMap Nominatim data for maximum accuracy.

**Locations (23 towns across North West England and Lake District):**

**South West Region (Liverpool & Manchester area):**
- **Liverpool:** 53.4072° N, 2.9917° W
- **Manchester:** 53.4795° N, 2.2451° W

**Central Lancashire Region:**
- **Blackburn:** 53.7493° N, 2.4841° W
- **Lytham-St-Annes:** 53.7485° N, 2.9991° W
- **Preston:** 53.7593° N, 2.6993° W
- **Kirkham:** 53.7827° N, 2.8715° W
- **Poulton-le-Fylde:** 53.8461° N, 2.9905° W

**Coastal Region:**
- **Fleetwood:** 53.9220° N, 3.0327° W
- **Blackpool:** 53.8179° N, 3.0510° W

**Northern Lancashire & Morecambe Bay Region:**
- **Garstang:** 53.9016° N, 2.7735° W
- **Lancaster:** 54.0488° N, 2.8013° W
- **Morecambe:** 54.0721° N, 2.8651° W
- **Heysham:** 54.0495° N, 2.8903° W

**Southern Lake District Region:**
- **Carnforth:** 54.1282° N, 2.7701° W
- **Kirkby-Lonsdale:** 54.2018° N, 2.5967° W
- **Grange-Over-Sands:** 54.1931° N, 2.9095° W
- **Cartmel:** 54.2009° N, 2.9529° W
- **Kendal:** 54.3290° N, 2.7472° W

**Northern Lake District Region:**
- **Windermere:** 54.3792° N, 2.9063° W
- **Ambleside:** 54.4316° N, 2.9622° W
- **Barrow-in-Furness:** 54.1289° N, 3.2269° W
- **Keswick:** 54.6010° N, 3.1376° W

**Map Bounds:**
- **Southwest Corner:** 53.3665° N, -3.5° W (Bottom of Liverpool, Most western coast with sea)
- **Northeast Corner:** 54.6200° N, -2.211° W (Top of Keswick, Far right of Manchester)
- **Viewing Restrictions:** 
  - Cannot see further south than the bottom of Liverpool
  - Cannot see further north than the top of Keswick
  - Cannot see further west than the most western extent of the North West coast
  - Cannot see further east than the far right edge of Manchester
- **Zoom Behavior:** Map zoom is dynamically adjusted based on window size. When the application window is resized or fullscreened, the zoom level automatically changes to maintain the same geographic boundaries in view, ensuring consistent visibility without stretching or distorting the map.

## OpenStreetMap Attribution
The map data is provided by OpenStreetMap contributors under the Open Data Commons Open Database License. Attribution is automatically displayed in the map corner.

## How to Use
1. Open `index.html` in a web browser or start the frontend server.
2. The interactive map will load, centered on the North West region.
3. Click any red marker to view location details (and image if available) in the popup.
4. Use zoom controls (+ and - buttons) or scroll to zoom in/out.
5. Click the weather (cloud) or notification (bell) icons to toggle side panels.
6. Open the FAQ from the sidebar to view common questions and answers.
7. Navigate using the sidebar links or search bar.

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
Modify bounds in `initializeMap()`. The bounds are defined with a southwest corner (lowest latitude, lowest longitude) and a northeast corner (highest latitude, highest longitude). The map uses `fitBounds()` to dynamically calculate the optimal zoom level for the current window size:
```javascript
const bounds = L.latLngBounds(
  L.latLng(53.3665, -3.5),       // Southwest: bottom of Liverpool, most western coast
  L.latLng(54.6200, -2.211)      // Northeast: top of Keswick, far right of Manchester
);
map.setMaxBounds(bounds);

// Fit map to bounds with padding and automatic zoom calculation
map.fitBounds(bounds, { padding: [50, 50] });

// Adjust zoom on window resize (includes fullscreen toggling)
window.addEventListener('resize', function() {
  map.fitBounds(bounds, { padding: [50, 50] });
});

map.setMinZoom(9);   // Prevent zooming out beyond minimum
map.setMaxZoom(19);  // Maximum zoom level
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
