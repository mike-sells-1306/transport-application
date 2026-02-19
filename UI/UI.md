# Transport for North West Web UI

## Overview
This project is a desktop-style web application interface for a regional travel service called **Transport for North West**. It is built using HTML and CSS, with a focus on bold branding, clear layout, and modern UI practices. The design is inspired by real-world travel and transport apps, with a fixed sidebar, interactive map, and layered modal panels.

## File Structure
- `index.html`: Main HTML file containing the structure and content of the UI.
- `style.css`: Main stylesheet for all visual styling and layout.

## How the Code Works

### 1. Sidebar Navigation
- **Purpose:** Provides persistent navigation and search controls.
- **Implementation:**
  - Fixed to the left, always visible.
  - Top section uses a deep red for branding and the service title.
  - Below, a lighter red panel contains a travel prompt and two input fields ("Search…" and "to") for journey planning.
  - A circular icon button is included for actions like swapping or submitting destinations.
  - Navigation links (Account, FAQ, Customer Support) are at the bottom.

### 2. Main Map Area
- **Purpose:** Displays a stylized map of North West England and acts as the main interactive canvas.
- **Implementation:**
  - Uses an SVG illustration for the map, with blue sea, green land, yellow/grey roads, and red town markers.
  - The map is always visible as a background layer.
  - Overlay panels (info cards, modals) are absolutely positioned above the map.

### 3. Overlay Panels
- **Info Card:**
  - Appears when a location is selected.
  - Shows an image, destination name, and description.
  - White background, rounded corners, drop shadow.
- **Route Modal:**
  - Appears when a route search is performed.
  - Large red panel with header, sort dropdown, and stacked route results.
  - Each route row shows a transport icon, times, and duration.
- **Weather Panel:**
  - Opens from the top-right icon button.
  - Lists towns and weather icons in a light grey rounded panel.
- **Notifications Panel:**
  - Opens from the top-right icon button.
  - Lists announcements with timestamps in a similar panel.
- **Account Modal:**
  - Replaces route modal when viewing account settings.
  - Red header, avatar, username, saved routes, and action buttons.

### 4. Top-Right Icon Buttons
- **Purpose:** Quick access to weather and notifications.
- **Implementation:**
  - Two circular icon buttons (cloud and bell) in the top-right corner.
  - Clicking toggles the corresponding panel.

### 5. Responsiveness
- The layout is optimized for desktop but adapts to smaller screens by reducing sidebar width and modal sizes.

## Why the Code Works
- **Separation of Concerns:** HTML handles structure and content, CSS handles all visual styling.
- **Accessibility:** Uses semantic elements and labels for inputs.
- **Maintainability:** CSS variables and modular classes make it easy to update branding or layout.
- **Performance:** No external dependencies; all icons are inline SVGs or data URIs for fast loading.

## How to Use
1. Open `index.html` in a web browser.
2. The sidebar and map will be visible. Try clicking the weather or notification icons in the top-right to toggle panels.
3. The UI is static for demonstration, but can be extended with JavaScript for interactivity.

## Customization
- To change branding colors, edit the CSS variables in `style.css`.
- To add more towns or routes, update the SVG or info card sections in `index.html`.
- For real map integration, replace the SVG with a map library (e.g., Leaflet, Mapbox).

## Comments in Code
- Both HTML and CSS files are commented to explain the purpose of each section and key styles.

---

**Author:** [Your Name]  
**Date:** 19 February 2026
