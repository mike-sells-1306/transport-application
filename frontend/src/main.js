/*
  main.js - Main application script for Transport for North West
  Handles interactive map initialization, panel toggling, and API interactions
*/

const authState = {
  token: localStorage.getItem('authToken') || null,
  user: null,
};

// Track which marker has an open popup
let currentOpenPopup = null;

// Store map marker references for theme updates
let mapMarkers = [];

// Store current routes data for sorting
let currentRoutesData = null;

// Swap button functionality
function setupSwapButton() {
  const swapBtn = document.querySelector('.journey-swap-btn');
  const fromInput = document.getElementById('from-input');
  const toInput = document.getElementById('to-input');
  const fromSuggestions = document.getElementById('from-suggestions');
  const toSuggestions = document.getElementById('to-suggestions');
  
  if (swapBtn) {
    swapBtn.addEventListener('click', () => {
      // Swap the input values
      const temp = fromInput.value;
      fromInput.value = toInput.value;
      toInput.value = temp;
      
      // Swap the selected stop data
      const tempStop = selectedStops.from;
      selectedStops.from = selectedStops.to;
      selectedStops.to = tempStop;
      
      // Clear autocomplete suggestions
      fromSuggestions.innerHTML = '';
      fromSuggestions.classList.remove('visible');
      toSuggestions.innerHTML = '';
      toSuggestions.classList.remove('visible');
      
      // Search for routes if both stops are selected
      if (selectedStops.from && selectedStops.to) {
        searchRoutes();
      }
    });
  }
}

// Initialize Leaflet map focused on North West England (Preston, Blackpool, Fylde, Wyre)
function initializeMap() {
  // Center coordinates: Between Preston and Blackpool, spanning the Fylde and Wyre coastline
  // Approximate center: 53.8° N, -3.0° W
  const mapCenter = [53.88, -3.02];
  const initialZoom = 11;

  // Create Leaflet map instance
  const map = L.map('map').setView(mapCenter, initialZoom);

  // Add OpenStreetMap tile layer
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19,
    minZoom: 9,
  }).addTo(map);

  // Define key towns and locations in the North West region
  const locations = [
    {
      name: 'Liverpool',
      lat: 53.4072,
      lng: -2.9917,
      description: 'Liverpool - Historic port city and cultural center on the Irish Sea coast.',
      image: 'https://www.hope.ac.uk/media/lifeathope/images/City%20of%20Liverpool%20Main%20Image%20880x425.jpg',
    },
    {
      name: 'Manchester',
      lat: 53.4795,
      lng: -2.2451,
      description: 'Manchester - Major industrial and commercial city in the heart of Greater Manchester.',
      image: 'https://images.ctfassets.net/szez98lehkfm/5Et7n40qkVp1XWiFp8prq0/0d863f37c9779a0332b641616e280975/MyIC_Article_93787?w=730&h=410&fm=jpg&fit=fill',
    },
    {
      name: 'Preston',
      lat: 53.7593,
      lng: -2.6993,
      description: 'Preston - England\'s newest city, cultural hub of Lancashire.',
      image: 'https://visitpreston.co.uk/image/13304/Preston-Flag-Market/related.jpg?m=1677680887777',
    },
    {
      name: 'Blackburn',
      lat: 53.7493,
      lng: -2.4841,
      description: 'Blackburn - Historic textile town, home to the cathedral.',
      image: 'https://upload.wikimedia.org/wikipedia/commons/5/55/Blackburn_Lancashire_Townscape.jpg',
    },
    {
      name: 'Lytham-St-Annes',
      lat: 53.7485,
      lng: -2.9991,
      description: 'Lytham-St-Annes - Seaside town on the Fylde coast.',
      image: 'https://hampshire.redkitedays.co.uk/wp-content/uploads/2024/06/Visit-Lytham-St-Annes-scaled.jpeg',
    },
    {
      name: 'Kirkham',
      lat: 53.7827,
      lng: -2.8715,
      description: 'Kirkham - Market town in the heart of the Fylde.',
      image: 'https://www.english-heritage.org.uk/siteassets/home/visit/places-to-visit/kirkham-priory/kirkham-twitter-card.jpg',
    },
    {
      name: 'Poulton-le-Fylde',
      lat: 53.8461,
      lng: -2.9905,
      description: 'Poulton-le-Fylde - Market town in the heart of the Fylde.',
      image: 'https://upload.wikimedia.org/wikipedia/commons/1/1d/Market_day_in_Poulton_-_geograph.org.uk_-_4103554.jpg',
    },
    {
      name: 'Fleetwood',
      lat: 53.9220,
      lng: -3.0327,
      description: 'Fleetwood - Coastal town at the mouth of the River Wyre and historic fishing port.',
      image: 'https://www.visitfyldecoast.info/wp-content/uploads/2024/05/IMG_8526-scaled-1.jpg',
    },
    {
      name: 'Blackpool',
      lat: 53.8179,
      lng: -3.0510,
      description: 'Blackpool - Iconic seaside resort with the famous Blackpool Tower.',
      image: 'https://i.guim.co.uk/img/media/5d9e2da10d2400d30c68ed77c725bd04e124e0cd/0_179_5404_3242/master/5404.jpg?width=1200&height=900&quality=85&auto=format&fit=crop&s=86096e66ab7a04d4183121b8aa78f8c6',
    },
    {
      name: 'Garstang',
      lat: 53.9016,
      lng: -2.7735,
      description: 'Garstang - Historic market town on the River Wyre.',
      image: 'https://canalrivertrust.org.uk/media/image/ZUEi447LPBxcv0Ri4kX8tw/Jzvw5PsTGFJIY8aaA7cX9ZwNHe-7eZMHn3Ehx1aJ1P4/rs:fill:1900:1187:1:0/g:ce/aHR0cHM6Ly9jcnRwcm9kY21zdWtzMDEuYmxvYi5jb3JlLndpbmRvd3MubmV0L2ltYWdlLzAxODk5MjczLWNiMjQtNzk0YS04YjM1LTExNTU3MGNjMDY5Yg.webp',
    },
    {
      name: 'Lancaster',
      lat: 54.0488,
      lng: -2.8013,
      description: 'Lancaster - Historic city with a medieval castle and university.',
      image: 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/1c/02/20/ac/the-newly-restored-lower.jpg?w=800&h=500&s=1',
    },
    {
      name: 'Morecambe',
      lat: 54.0721,
      lng: -2.8651,
      description: 'Morecambe - Seaside town known for its promenade and bay views.',
      image: 'https://www.hawthornscaravanpark.co.uk/wp-content/uploads/2023/09/lancashires-coastline-morecambe-bay-scaled.jpg',
    },
    {
      name: 'Heysham',
      lat: 54.0495,
      lng: -2.8903,
      description: 'Heysham - Coastal village with nuclear power station and maritime heritage.',
      image: 'https://nt.global.ssl.fastly.net/binaries/content/gallery/website/national/regions/liverpool-lancashire/places/heysham-coast/library/beach-heysham-coast-lancashire-1525498.jpg',
    },
    {
      name: 'Carnforth',
      lat: 54.1282,
      lng: -2.7701,
      description: 'Carnforth - Village known for its railway heritage.',
      image: 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/28/eb/14/0c/leighton-hall-front-view.jpg?w=600&h=-1&s=1',
    },
    {
      name: 'Kirkby-Lonsdale',
      lat: 54.2018,
      lng: -2.5967,
      description: 'Kirkby-Lonsdale - Picturesque village in the Lune Valley.',
      image: 'https://www.thetimes.com/imageserver/image/%2Fmethode%2Fsundaytimes%2Fprod%2Fweb%2Fbin%2F2fb016a4-44d1-11e9-8121-489737db5c2b.jpg?crop=2250%2C1266%2C0%2C117',
    },
    {
      name: 'Grange-Over-Sands',
      lat: 54.1931,
      lng: -2.9095,
      description: 'Grange-Over-Sands - Charming coastal resort on Morecambe Bay.',
      image: 'https://www.visitcumbria.com/wp-content/uploads/2024/11/Grange-over-Sands-Village.jpg',
    },
    {
      name: 'Cartmel',
      lat: 54.2009,
      lng: -2.9529,
      description: 'Cartmel - Picturesque village famous for its Priory and steeplechase racecourse.',
      image: 'https://www.sykescottages.co.uk/inspiration/wp-content/uploads/things-to-do-in-Cartmel.jpg',
    },
    {
      name: 'Kendal',
      lat: 54.3290,
      lng: -2.7472,
      description: 'Kendal - Gateway to the Lake District, historic market town.',
      image: 'https://eu-assets.simpleview-europe.com/golakes/imageresizer/?image=%2Fdmsimgs%2F6D1CFF58CABBCFA6EE82AAFCEE101B4D85DCC848.jpg&action=ProductDetailPro',
    },
    {
      name: 'Windermere',
      lat: 54.3792,
      lng: -2.9063,
      description: 'Windermere - Heart of the Lake District with England\'s largest lake.',
      image: 'https://www.lakelovers.co.uk/blog/wp-content/uploads/sites/15/2025/04/Blog-header-image-1400-x-950-18.png',
    },
    {
      name: 'Ambleside',
      lat: 54.4316,
      lng: -2.9622,
      description: 'Ambleside - Picturesque Lake District town on the shores of Lake Windermere.',
      image: 'https://www.thegables-ambleside.co.uk/images/galleries/thingstodo/ambleside2.jpg',
    },
    {
      name: 'Barrow-in-Furness',
      lat: 54.289,
      lng: -3.2269,
      description: 'Barrow-in-Furness - Industrial town on the Irish Sea coast.',
      image: 'https://www.leahough.co.uk/wp-content/uploads/2025/06/Barrow-in-Furness.jpg',
    },
    {
      name: 'Keswick',
      lat: 54.6010,
      lng: -3.1376,
      description: 'Keswick - Historic market town in the northern Lake District.',
      image: 'https://www.mountain-goat.com/getmedia/75c36f97-015f-4347-95ec-cf08f8133057/Keswick-Page-Image.jpg.aspx',
    },
  ];

  // Add markers for each location with popups and toggle functionality
  locations.forEach(location => {
    const colors = getMarkerColors();
    const marker = L.circleMarker([location.lat, location.lng], {
      radius: 9,
      fillColor: colors.fillColor,
      color: colors.color,
      weight: 1,
      opacity: 1,
      fillOpacity: colors.fillOpacity,
    });
    mapMarkers.push(marker);

    marker.addTo(map);

    const popupImageMarkup = location.image
      ? `<img src="${location.image}" alt="${location.name} photo" style="width: 100%; height: 120px; object-fit: cover; border-radius: 10px; margin-bottom: 10px;" />`
      : '';

    marker.bindPopup(`
      <div class="popup-content">
        ${popupImageMarkup}
        <h3 class="popup-title">${location.name}</h3>
        <p class="popup-description">${location.description}</p>
      </div>
    `);

    // Handle popup toggle: close old popup if different marker clicked,
    // or close current popup if same marker clicked again
    marker.on('click', function() {
      if (currentOpenPopup === this) {
        // Same marker clicked again - close it
        this.closePopup();
        currentOpenPopup = null;
      } else {
        // Different marker or no popup open
        if (currentOpenPopup) {
          // Close the previously open popup
          currentOpenPopup.closePopup();
        }
        // Open the new popup
        this.openPopup();
        currentOpenPopup = this;
      }
    });
  });

  // Maximum panning bounds: generous area around all locations.
  // This must be larger than the location extent so that Leaflet's popup
  // autoPan can scroll the map to reveal popups near the edges (e.g. Keswick).
  const maxBounds = L.latLngBounds(
    L.latLng(53.0, -3.7),         // Southwest: well south of Liverpool, west of Barrow coast
    L.latLng(55.2, -1.9)          // Northeast: well above Keswick popup, east of Manchester
  );
  map.setMaxBounds(maxBounds);
  
  // Initial view: fit to the actual location extent (tighter than maxBounds)
  // so all red-dot markers are visible with comfortable padding.
  const locationBounds = L.latLngBounds(
    L.latLng(53.38, -3.28),       // Southwest of locations (Liverpool / Barrow)
    L.latLng(54.65, -2.20)        // Northeast of locations (Keswick / Manchester)
  );
  map.fitBounds(locationBounds, { padding: [50, 50] });
  
  // Set zoom constraints to prevent seeing beyond bounds at any zoom level
  map.setMinZoom(9);
  map.setMaxZoom(19);
  
  // Add responsive zoom: when window is resized (including fullscreen), 
  // adjust zoom to maintain the same geographic bounds visibility
  window.addEventListener('resize', function() {
    map.fitBounds(locationBounds, { padding: [50, 50] });
  });

  return map;
}

// ============================================================================
// COLOURBLIND MODE / ACCESSIBILITY FUNCTIONS
// ============================================================================

/**
 * Get marker colours based on current theme.
 * Returns blue palette in colourblind mode, red in normal mode.
 */
function getMarkerColors() {
  const isCB = document.body.classList.contains('colorblind-mode');
  return {
    fillColor: isCB ? '#1976D2' : '#d32f2f',
    color: isCB ? '#0057B7' : '#b71c1c',
    fillOpacity: isCB ? 0.6 : 0.35,
  };
}

/**
 * Update all map marker colours to match the current theme.
 */
function updateMapMarkerColors() {
  const colors = getMarkerColors();
  mapMarkers.forEach(marker => {
    marker.setStyle({
      fillColor: colors.fillColor,
      color: colors.color,
      fillOpacity: colors.fillOpacity,
    });
  });
}

/**
 * Apply or remove colourblind mode across the application.
 * Toggles the CSS class, updates map markers, syncs UI controls,
 * and persists the preference to localStorage.
 * @param {boolean} enabled - Whether colourblind mode should be active
 */
function applyColorblindMode(enabled) {
  document.body.classList.toggle('colorblind-mode', enabled);

  // Sync the account settings checkbox
  const checkbox = document.getElementById('colorblind-checkbox');
  if (checkbox) {
    checkbox.checked = enabled;
    checkbox.setAttribute('aria-checked', String(enabled));
  }

  // Sync the sidebar accessibility link
  const sidebarLink = document.getElementById('colorblind-toggle-link');
  if (sidebarLink) {
    sidebarLink.setAttribute('aria-pressed', String(enabled));
    sidebarLink.textContent = enabled ? 'Accessibility \u2713' : 'Accessibility';
  }

  // Persist preference for non-logged-in users
  localStorage.setItem('colorblindMode', JSON.stringify(enabled));

  // Update map markers to match the new theme
  updateMapMarkerColors();
}

// ============================================================================
// LIVE WEATHER FUNCTIONALITY
// ============================================================================

// Weather locations: all 22 map locations with coordinates for API calls
const weatherLocations = [
  { name: 'Ambleside', lat: 54.4316, lon: -2.9622 },
  { name: 'Barrow-in-Furness', lat: 54.1289, lon: -3.2269 },
  { name: 'Blackburn', lat: 53.7493, lon: -2.4841 },
  { name: 'Blackpool', lat: 53.8179, lon: -3.0510 },
  { name: 'Carnforth', lat: 54.1282, lon: -2.7701 },
  { name: 'Cartmel', lat: 54.2009, lon: -2.9529 },
  { name: 'Fleetwood', lat: 53.9220, lon: -3.0327 },
  { name: 'Garstang', lat: 53.9016, lon: -2.7735 },
  { name: 'Grange-Over-Sands', lat: 54.1931, lon: -2.9095 },
  { name: 'Heysham', lat: 54.0495, lon: -2.8903 },
  { name: 'Kendal', lat: 54.3290, lon: -2.7472 },
  { name: 'Keswick', lat: 54.6010, lon: -3.1376 },
  { name: 'Kirkby-Lonsdale', lat: 54.2018, lon: -2.5967 },
  { name: 'Kirkham', lat: 53.7827, lon: -2.8715 },
  { name: 'Lancaster', lat: 54.0488, lon: -2.8013 },
  { name: 'Liverpool', lat: 53.4072, lon: -2.9917 },
  { name: 'Lytham-St-Annes', lat: 53.7485, lon: -2.9991 },
  { name: 'Manchester', lat: 53.4795, lon: -2.2451 },
  { name: 'Morecambe', lat: 54.0721, lon: -2.8651 },
  { name: 'Poulton-le-Fylde', lat: 53.8461, lon: -2.9905 },
  { name: 'Preston', lat: 53.7593, lon: -2.6993 },
  { name: 'Windermere', lat: 54.3792, lon: -2.9063 },
];

// Cache for weather data to avoid repeated API calls
let weatherCache = null;
let weatherCacheTimestamp = 0;
const WEATHER_CACHE_DURATION_MS = 60 * 1000; // 1 minute

// Auto-refresh interval ID (runs while panel is open)
let weatherRefreshInterval = null;

// Debounce timer for weather search
let weatherSearchTimer = null;

/**
 * Fetch weather data for all default locations from the backend API.
 * Uses the /api/weather endpoint for each location.
 * Results are cached for 1 minute to reduce API load.
 * @returns {Promise<Array>} Array of { name, weather } objects
 */
async function fetchWeatherForAllLocations() {
  const now = Date.now();
  if (weatherCache && (now - weatherCacheTimestamp) < WEATHER_CACHE_DURATION_MS) {
    return weatherCache;
  }

  const results = await Promise.allSettled(
    weatherLocations.map(async (loc) => {
      try {
        const res = await fetch(`/api/weather?lat=${loc.lat}&lon=${loc.lon}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return { name: loc.name, weather: data };
      } catch (err) {
        console.warn(`Weather fetch failed for ${loc.name}:`, err);
        return { name: loc.name, weather: null };
      }
    })
  );

  const weatherData = results.map(r => r.status === 'fulfilled' ? r.value : r.reason);
  weatherCache = weatherData;
  weatherCacheTimestamp = now;
  return weatherData;
}

/**
 * Search for locations by name via the backend gazetteer and return weather data.
 * @param {string} query - The search string
 * @returns {Promise<Array>} Array of { name, weather } objects from the API
 */
async function searchWeatherLocations(query) {
  try {
    const res = await fetch(`/api/weather/search?q=${encodeURIComponent(query)}&limit=15`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return (data.results || []).map(r => ({ name: r.name, weather: r.weather }));
  } catch (err) {
    console.error('Weather search failed:', err);
    return [];
  }
}

/**
 * Build a single weather list item element with expandable detail section.
 * @param {string} name - Location name
 * @param {object|null} weather - Parsed weather data from API
 * @returns {HTMLLIElement}
 */
function buildWeatherListItem(name, weather) {
  const li = document.createElement('li');
  li.className = 'weather-item';

  // --- Top row (always visible): name + icon + temp ---
  const row = document.createElement('div');
  row.className = 'weather-row';
  row.setAttribute('role', 'button');
  row.setAttribute('tabindex', '0');
  row.setAttribute('aria-expanded', 'false');

  const nameSpan = document.createElement('span');
  nameSpan.className = 'weather-location-name';
  nameSpan.textContent = name;

  const rightSide = document.createElement('span');
  rightSide.className = 'weather-info';

  let description = '';
  let humidity = null;
  let windSpeed = null;
  let windUnit = '';
  let feelsLike = null;
  let cloudCoverage = null;
  let visibility = null;

  if (weather && !weather.error) {
    const temp = weather.temperature?.current;
    const tempSpan = document.createElement('span');
    tempSpan.className = 'weather-temp';
    tempSpan.textContent = temp != null ? `${Math.round(temp)}\u00b0C` : '--\u00b0C';

    const iconCode = weather.icon?.code;
    if (iconCode) {
      const iconWrap = document.createElement('span');
      iconWrap.className = 'weather-icon-bg';
      const iconImg = document.createElement('img');
      iconImg.src = `/api/weather/icon/${iconCode}`;
      iconImg.alt = weather.conditions?.description || 'weather';
      iconImg.className = 'weather-icon-img';
      iconImg.width = 32;
      iconImg.height = 32;
      iconWrap.appendChild(iconImg);
      rightSide.appendChild(iconWrap);
    }

    rightSide.appendChild(tempSpan);

    // Collect detail data
    description = weather.conditions?.description || '';
    humidity = weather.atmospheric_conditions?.humidity;
    windSpeed = weather.wind?.speed;
    windUnit = weather.wind?.speed_unit || 'm/s';
    feelsLike = weather.temperature?.feels_like;
    cloudCoverage = weather.cloud_coverage?.percentage;
    visibility = weather.visibility?.distance;
  } else {
    const errorSpan = document.createElement('span');
    errorSpan.className = 'weather-temp';
    errorSpan.textContent = '--\u00b0C';
    rightSide.appendChild(errorSpan);
  }

  // Expand chevron
  const chevron = document.createElement('span');
  chevron.className = 'weather-chevron';
  chevron.textContent = '\u25B8'; // right-pointing triangle
  rightSide.appendChild(chevron);

  row.appendChild(nameSpan);
  row.appendChild(rightSide);

  // --- Detail section (hidden by default) ---
  const detail = document.createElement('div');
  detail.className = 'weather-detail';

  if (description) {
    // Capitalise first letter of description
    const desc = description.charAt(0).toUpperCase() + description.slice(1);
    let detailHTML = `<span class="weather-detail-desc">${desc}</span>`;
    const extras = [];
    if (feelsLike != null) extras.push(`Feels like ${Math.round(feelsLike)}\u00b0C`);
    if (humidity != null) extras.push(`Humidity ${humidity}%`);
    if (windSpeed != null) extras.push(`Wind ${windSpeed} ${windUnit}`);
    if (cloudCoverage != null) extras.push(`Cloud cover ${cloudCoverage}%`);
    if (visibility != null) extras.push(`Visibility ${(visibility / 1000).toFixed(1)} km`);
    if (extras.length) {
      detailHTML += `<span class="weather-detail-extras">${extras.join(' \u00b7 ')}</span>`;
    }
    detail.innerHTML = detailHTML;
  } else {
    detail.innerHTML = '<span class="weather-detail-desc">No detail available</span>';
  }

  li.appendChild(row);
  li.appendChild(detail);

  // Toggle expand/collapse on click
  row.addEventListener('click', () => {
    const isOpen = li.classList.toggle('weather-item-open');
    row.setAttribute('aria-expanded', String(isOpen));
  });
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      row.click();
    }
  });

  return li;
}

/**
 * Render the weather list inside the weather panel with real API data.
 * Each item displays: location name, weather icon, temperature,
 * and an expandable detail section with a brief description.
 */
async function renderWeatherPanel() {
  const weatherList = document.getElementById('weather-list');
  if (!weatherList) return;

  // Show loading state
  weatherList.innerHTML = '<li class="weather-loading">Loading weather data\u2026</li>';

  try {
    const weatherData = await fetchWeatherForAllLocations();
    weatherList.innerHTML = '';
    weatherData.forEach(({ name, weather }) => {
      weatherList.appendChild(buildWeatherListItem(name, weather));
    });
  } catch (err) {
    console.error('Failed to load weather data:', err);
    weatherList.innerHTML = '<li class="weather-loading">Unable to load weather data</li>';
  }
}

/**
 * Render weather search results into the weather list.
 * @param {Array} results - Array of { name, weather } objects
 */
function renderWeatherSearchResults(results) {
  const weatherList = document.getElementById('weather-list');
  if (!weatherList) return;

  weatherList.innerHTML = '';
  if (!results.length) {
    weatherList.innerHTML = '<li class="weather-loading">No locations found</li>';
    return;
  }
  results.forEach(({ name, weather }) => {
    weatherList.appendChild(buildWeatherListItem(name, weather));
  });
}

/**
 * Initialise the weather search bar event listeners.
 * Filters default locations client-side for instant feedback,
 * and queries the backend gazetteer for broader location search.
 */
function initWeatherSearch() {
  const input = document.getElementById('weather-search-input');
  if (!input) return;

  input.addEventListener('input', () => {
    const query = input.value.trim().toLowerCase();
    clearTimeout(weatherSearchTimer);

    if (query.length === 0) {
      // Empty search: show all default locations from cache or re-fetch
      renderWeatherPanel();
      return;
    }

    if (query.length < 2) {
      // Too short: filter default locations client-side only
      if (weatherCache) {
        const filtered = weatherCache.filter(w =>
          w.name.toLowerCase().includes(query)
        );
        renderWeatherSearchResults(filtered);
      }
      return;
    }

    // For 2+ chars: immediately filter defaults, then debounce an API search
    // for broader gazetteer results
    if (weatherCache) {
      const filtered = weatherCache.filter(w =>
        w.name.toLowerCase().includes(query)
      );
      renderWeatherSearchResults(filtered);
    }

    weatherSearchTimer = setTimeout(async () => {
      const weatherList = document.getElementById('weather-list');
      // Show a subtle loading indicator at the bottom while searching
      if (weatherList) {
        const loadingLi = document.createElement('li');
        loadingLi.className = 'weather-loading';
        loadingLi.textContent = 'Searching more locations\u2026';
        weatherList.appendChild(loadingLi);
      }

      const apiResults = await searchWeatherLocations(query);

      // Merge: default locations matching query + API results, deduplicated
      const seen = new Set();
      const merged = [];

      // Add matching defaults first (already cached)
      if (weatherCache) {
        weatherCache.filter(w => w.name.toLowerCase().includes(query)).forEach(w => {
          if (!seen.has(w.name.toLowerCase())) {
            seen.add(w.name.toLowerCase());
            merged.push(w);
          }
        });
      }

      // Then add API results that aren't already shown
      apiResults.forEach(r => {
        if (!seen.has(r.name.toLowerCase())) {
          seen.add(r.name.toLowerCase());
          merged.push(r);
        }
      });

      // Only update if the search query hasn't changed while we were fetching
      if (input.value.trim().toLowerCase() === query) {
        renderWeatherSearchResults(merged);
      }
    }, 400);
  });
}

// ============================================================================
// END LIVE WEATHER FUNCTIONALITY
// ============================================================================

// Toggle weather panel visibility
function toggleWeatherPanel() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const faqPanel = document.getElementById('faq-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');
  
  weatherPanel.classList.toggle('hidden');
  notifPanel.classList.add('hidden');

  // Update aria-expanded states for screen readers
  const weatherBtn = document.getElementById('weather-btn');
  const notifBtn = document.getElementById('notif-btn');
  if (weatherBtn) weatherBtn.setAttribute('aria-expanded', String(!weatherPanel.classList.contains('hidden')));
  if (notifBtn) notifBtn.setAttribute('aria-expanded', 'false');

  // Close other panels when weather is opened
  if (!weatherPanel.classList.contains('hidden')) {
    faqPanel?.classList.add('hidden');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
    // Clear search input when opening the panel
    const searchInput = document.getElementById('weather-search-input');
    if (searchInput) searchInput.value = '';
    // Fetch and render live weather data when panel is opened
    renderWeatherPanel();
    // Start auto-refresh every 60 seconds while panel is open
    clearInterval(weatherRefreshInterval);
    weatherRefreshInterval = setInterval(() => {
      // Invalidate cache so next render fetches fresh data
      weatherCache = null;
      weatherCacheTimestamp = 0;
      // Only re-render if search bar is empty (don't overwrite active search)
      const si = document.getElementById('weather-search-input');
      if (!si || si.value.trim() === '') {
        renderWeatherPanel();
      }
    }, WEATHER_CACHE_DURATION_MS);
  } else {
    // Panel is closing — stop auto-refresh
    clearInterval(weatherRefreshInterval);
    weatherRefreshInterval = null;
  }
}

// Toggle notifications panel visibility
function toggleNotificationsPanel() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const faqPanel = document.getElementById('faq-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');
  
  notifPanel.classList.toggle('hidden');
  weatherPanel.classList.add('hidden');

  // Update aria-expanded states for screen readers
  const weatherBtn = document.getElementById('weather-btn');
  const notifBtn = document.getElementById('notif-btn');
  if (notifBtn) notifBtn.setAttribute('aria-expanded', String(!notifPanel.classList.contains('hidden')));
  if (weatherBtn) weatherBtn.setAttribute('aria-expanded', 'false');

  // Close other panels when notifications is opened
  if (!notifPanel.classList.contains('hidden')) {
    faqPanel?.classList.add('hidden');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
  }
}

function openFaqPanel() {
  const faqPanel = document.getElementById('faq-panel');
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');
  
  if (faqPanel) {
    faqPanel.classList.remove('hidden');
    faqPanel.setAttribute('aria-hidden', 'false');
    
    // Close other panels when FAQ is opened
    weatherPanel?.classList.add('hidden');
    notifPanel?.classList.add('hidden');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
  }
}

function closeFaqPanel() {
  const faqPanel = document.getElementById('faq-panel');
  if (faqPanel) {
    faqPanel.classList.add('hidden');
    faqPanel.setAttribute('aria-hidden', 'true');
    
    // Close all FAQ answers when panel is closed
    const openItems = faqPanel.querySelectorAll('.faq-item.open');
    openItems.forEach(item => {
      item.classList.remove('open');
      const question = item.querySelector('.faq-question');
      if (question) {
        question.setAttribute('aria-expanded', 'false');
      }
      const answer = item.querySelector('.faq-answer');
      if (answer) {
        answer.setAttribute('aria-hidden', 'true');
      }
    });
  }
}

function attachFaqEventHandlers() {
  const faqLink = document.querySelector('.sidebar-links a[href="#faq"]');
  faqLink?.addEventListener('click', event => {
    event.preventDefault();
    openFaqPanel();
  });

  document.getElementById('faq-close')?.addEventListener('click', closeFaqPanel);

  document.getElementById('faq-panel')?.addEventListener('click', event => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (!target.classList.contains('faq-question')) {
      return;
    }

    const item = target.closest('.faq-item');
    if (!item) {
      return;
    }

    const isOpen = item.classList.toggle('open');
    target.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    const answer = item.querySelector('.faq-answer');
    if (answer) {
      answer.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
    }
  });
}

function setAuthToken(token) {
  authState.token = token;
  if (token) {
    localStorage.setItem('authToken', token);
  } else {
    localStorage.removeItem('authToken');
  }
}

async function apiRequest(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (authState.token) {
    headers.Authorization = `Bearer ${authState.token}`;
  }

  const response = await fetch(path, {
    method: options.method || 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new Error(data.error || `Request failed (${response.status})`);
  }

  return data;
}

function openAuthModal() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const faqPanel = document.getElementById('faq-panel');
  
  document.getElementById('auth-modal')?.classList.remove('hidden');
  document.getElementById('account-modal')?.classList.add('hidden');
  
  // Close other panels when auth modal is opened
  weatherPanel?.classList.add('hidden');
  notifPanel?.classList.add('hidden');
  faqPanel?.classList.add('hidden');
}

function closeAuthModal() {
  document.getElementById('auth-modal')?.classList.add('hidden');
}

function openAccountModal() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const faqPanel = document.getElementById('faq-panel');
  
  document.getElementById('account-modal')?.classList.remove('hidden');
  document.getElementById('auth-modal')?.classList.add('hidden');
  
  // Close other panels when account modal is opened
  weatherPanel?.classList.add('hidden');
  notifPanel?.classList.add('hidden');
  faqPanel?.classList.add('hidden');
}

function closeAccountModal() {
  document.getElementById('account-modal')?.classList.add('hidden');
}

async function refreshAccountView() {
  if (!authState.token) {
    authState.user = null;
    return;
  }

  try {
    const meResponse = await apiRequest('/api/account/me');
    authState.user = meResponse.user;

    // Apply colourblind mode preference from server
    applyColorblindMode(!!authState.user.colorblindmode);

    const usernameTarget = document.getElementById('account-username-value');
    if (usernameTarget) {
      usernameTarget.textContent = authState.user.userName;
    }

    const savedRoutesResponse = await apiRequest('/api/account/saved-routes');
    renderSavedRoutes(savedRoutesResponse.savedRoutes || []);

    const notificationResponse = await apiRequest('/api/account/notifications');
    renderNotifications(notificationResponse.notifications || []);
  } catch (error) {
    console.warn(error.message);
    setAuthToken(null);
    authState.user = null;
  }
}

function renderSavedRoutes(savedRoutes) {
  const list = document.getElementById('saved-routes-list');
  if (!list) {
    return;
  }

  list.innerHTML = '';
  if (!savedRoutes.length) {
    const emptyItem = document.createElement('li');
    emptyItem.textContent = 'No saved routes yet.';
    list.appendChild(emptyItem);
    return;
  }

  savedRoutes.forEach(route => {
    const item = document.createElement('li');
    item.textContent = `${route.routeStart} → ${route.routeEnd}`;
    list.appendChild(item);
  });
}

function renderNotifications(notifications) {
  const notifList = document.querySelector('.notif-list');
  if (!notifList) {
    return;
  }

  notifList.innerHTML = '';
  if (!notifications.length) {
    const emptyNode = document.createElement('div');
    emptyNode.className = 'notif-item';
    emptyNode.textContent = 'No notifications yet.';
    notifList.appendChild(emptyNode);
    return;
  }

  notifications.slice(0, 5).forEach(item => {
    const row = document.createElement('div');
    row.className = 'notif-item';
    row.textContent = item.message;
    notifList.appendChild(row);
  });
}

async function handleLoginSubmit(event) {
  event.preventDefault();

  const email = document.getElementById('login-email')?.value || '';
  const password = document.getElementById('login-password')?.value || '';

  try {
    const response = await apiRequest('/api/auth/login', {
      method: 'POST',
      body: { email, password },
    });

    setAuthToken(response.token);
    await refreshAccountView();
    openAccountModal();
  } catch (error) {
    alert(error.message);
  }
}

async function handleRegisterSubmit(event) {
  event.preventDefault();

  const userName = document.getElementById('register-username')?.value || '';
  const email = document.getElementById('register-email')?.value || '';
  const password = document.getElementById('register-password')?.value || '';

  try {
    const response = await apiRequest('/api/auth/register', {
      method: 'POST',
      body: { userName, email, password },
    });

    setAuthToken(response.token);
    await refreshAccountView();
    openAccountModal();
  } catch (error) {
    alert(error.message);
  }
}

async function handleLogout() {
  try {
    await apiRequest('/api/auth/logout', { method: 'POST' });
  } catch (error) {
    console.warn(error.message);
  }

  setAuthToken(null);
  authState.user = null;
  closeAccountModal();
  openAuthModal();
}

async function handleUpdatePassword() {
  if (!authState.user) {
    return;
  }

  const currentPassword = window.prompt('Enter current password:');
  if (!currentPassword) {
    return;
  }
  const newPassword = window.prompt('Enter new password (8+ characters):');
  if (!newPassword) {
    return;
  }

  try {
    await apiRequest('/api/account/password', {
      method: 'PATCH',
      body: { currentPassword, newPassword },
    });
    alert('Password updated successfully.');
  } catch (error) {
    alert(error.message);
  }
}

async function handleDeleteAccount() {
  if (!authState.user) {
    return;
  }

  const confirmation = window.confirm('This will permanently delete your account. Continue?');
  if (!confirmation) {
    return;
  }

  const password = window.prompt('Confirm your password to delete account:');
  if (!password) {
    return;
  }

  try {
    await apiRequest('/api/account', {
      method: 'DELETE',
      body: { password },
    });
    setAuthToken(null);
    authState.user = null;
    closeAccountModal();
    openAuthModal();
    alert('Your account has been deleted.');
  } catch (error) {
    alert(error.message);
  }
}

function attachAccountEventHandlers() {
  const accountLink = document.getElementById('account-link');
  if (accountLink) {
    accountLink.addEventListener('click', async event => {
      event.preventDefault();

      if (!authState.token) {
        openAuthModal();
        return;
      }

      await refreshAccountView();
      openAccountModal();
    });
  }

  document.getElementById('close-auth-modal')?.addEventListener('click', closeAuthModal);
  document.getElementById('close-account-modal')?.addEventListener('click', closeAccountModal);
  document.getElementById('login-form')?.addEventListener('submit', handleLoginSubmit);
  document.getElementById('register-form')?.addEventListener('submit', handleRegisterSubmit);
  document.getElementById('logout-btn')?.addEventListener('click', handleLogout);
  document.getElementById('update-password-btn')?.addEventListener('click', handleUpdatePassword);
  document.getElementById('delete-account-btn')?.addEventListener('click', handleDeleteAccount);

  // Colourblind mode toggle in account settings
  document.getElementById('colorblind-checkbox')?.addEventListener('change', async (e) => {
    const enabled = e.target.checked;
    applyColorblindMode(enabled);
    if (authState.token) {
      try {
        await apiRequest('/api/account/profile', {
          method: 'PATCH',
          body: { colorblindmode: enabled },
        });
      } catch (err) {
        console.warn('Failed to save colourblind preference:', err.message);
      }
    }
  });

  // Sidebar accessibility link toggle (works without login)
  document.getElementById('colorblind-toggle-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    const isCurrentlyEnabled = document.body.classList.contains('colorblind-mode');
    applyColorblindMode(!isCurrentlyEnabled);
    if (authState.token) {
      apiRequest('/api/account/profile', {
        method: 'PATCH',
        body: { colorblindmode: !isCurrentlyEnabled },
      }).catch(err => console.warn('Failed to save colourblind preference:', err.message));
    }
  });
}

// ============================================================================
// AUTOCOMPLETE FUNCTIONALITY
// ============================================================================

// Store selected stop data for each input
const selectedStops = {
  from: null,
  to: null
};

// Debounce timer
let debounceTimer = null;

/**
 * Initialize autocomplete for both search inputs
 */
function initializeAutocomplete() {
  const fromInput = document.getElementById('from-input');
  const toInput = document.getElementById('to-input');
  const fromSuggestions = document.getElementById('from-suggestions');
  const toSuggestions = document.getElementById('to-suggestions');

  if (fromInput && fromSuggestions) {
    setupAutocomplete(fromInput, fromSuggestions, 'from');
  }

  if (toInput && toSuggestions) {
    setupAutocomplete(toInput, toSuggestions, 'to');
  }

  // Close suggestions when clicking outside
  document.addEventListener('click', function(event) {
    if (!event.target.closest('.autocomplete-wrapper')) {
      hideAllSuggestions();
    }
  });
}

/**
 * Setup autocomplete for a specific input
 */
function setupAutocomplete(input, suggestionsContainer, inputType) {
  let selectedIndex = -1;

  // Input event handler with debouncing
  input.addEventListener('input', function() {
    const query = this.value.trim();
    selectedIndex = -1;
    
    // Clear selected stop when user modifies input
    selectedStops[inputType] = null;

    // Debounce the search
    clearTimeout(debounceTimer);
    
    if (query.length < 2) {
      hideSuggestions(suggestionsContainer);
      return;
    }

    debounceTimer = setTimeout(() => {
      searchStops(query, suggestionsContainer, input, inputType);
    }, 300);
  });

  // Keyboard navigation
  input.addEventListener('keydown', function(event) {
    const suggestions = suggestionsContainer.querySelectorAll('.autocomplete-suggestion-item');
    
    if (suggestions.length === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
      updateSelectedSuggestion(suggestions, selectedIndex);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      updateSelectedSuggestion(suggestions, selectedIndex);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (selectedIndex >= 0 && suggestions[selectedIndex]) {
        suggestions[selectedIndex].click();
      }
    } else if (event.key === 'Escape') {
      hideSuggestions(suggestionsContainer);
      selectedIndex = -1;
    }
  });

  // Focus event - show suggestions if there's a query
  input.addEventListener('focus', function() {
    if (this.value.trim().length >= 2 && suggestionsContainer.children.length > 0) {
      showSuggestions(suggestionsContainer);
    }
  });
}

/**
 * Search for stops matching the query
 */
async function searchStops(query, suggestionsContainer, input, inputType) {
  try {
    const response = await fetch(`/api/stops/search?q=${encodeURIComponent(query)}&limit=10`);
    const data = await response.json();

    if (data.stops && data.stops.length > 0) {
      displaySuggestions(data.stops, suggestionsContainer, input, inputType);
    } else {
      displayNoResults(suggestionsContainer);
    }
  } catch (error) {
    console.error('Error searching stops:', error);
    displayError(suggestionsContainer);
  }
}

/**
 * Display suggestions in the dropdown
 */
function displaySuggestions(stops, suggestionsContainer, input, inputType) {
  suggestionsContainer.innerHTML = '';

  stops.forEach((stop, index) => {
    const item = document.createElement('div');
    item.className = 'autocomplete-suggestion-item';
    item.textContent = stop.name;
    item.dataset.atcoCode = stop.atcoCode;
    item.dataset.lat = stop.lat;
    item.dataset.lon = stop.lon;
    item.dataset.name = stop.name;
    item.dataset.stopType = stop.stopType;

    item.addEventListener('click', function() {
      selectStop(stop, input, suggestionsContainer, inputType);
    });

    // Hover effect
    item.addEventListener('mouseenter', function() {
      const allItems = suggestionsContainer.querySelectorAll('.autocomplete-suggestion-item');
      allItems.forEach(i => i.classList.remove('selected'));
      this.classList.add('selected');
    });

    suggestionsContainer.appendChild(item);
  });

  showSuggestions(suggestionsContainer);
}

/**
 * Display no results message
 */
function displayNoResults(suggestionsContainer) {
  suggestionsContainer.innerHTML = '<div class="autocomplete-no-results">No stops found within the region</div>';
  showSuggestions(suggestionsContainer);
}

/**
 * Display error message
 */
function displayError(suggestionsContainer) {
  suggestionsContainer.innerHTML = '<div class="autocomplete-no-results">Error loading stops</div>';
  showSuggestions(suggestionsContainer);
}

/**
 * Select a stop from suggestions
 */
function selectStop(stop, input, suggestionsContainer, inputType) {
  input.value = stop.name;
  selectedStops[inputType] = stop;
  hideSuggestions(suggestionsContainer);
  
  console.log(`Selected ${inputType} stop:`, stop);
  
  // Search for routes if both stops are selected
  if (selectedStops.from && selectedStops.to) {
    searchRoutes();
  }
}

/**
 * Update which suggestion is highlighted
 */
function updateSelectedSuggestion(suggestions, index) {
  suggestions.forEach((item, i) => {
    if (i === index) {
      item.classList.add('selected');
      item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else {
      item.classList.remove('selected');
    }
  });
}

/**
 * Show suggestions dropdown
 */
function showSuggestions(suggestionsContainer) {
  suggestionsContainer.classList.add('visible');
}

/**
 * Hide suggestions dropdown
 */
function hideSuggestions(suggestionsContainer) {
  suggestionsContainer.classList.remove('visible');
}

/**
 * Hide all suggestion dropdowns
 */
function hideAllSuggestions() {
  document.querySelectorAll('.autocomplete-suggestions').forEach(container => {
    hideSuggestions(container);
  });
}

/**
 * Get selected stop data
 */
function getSelectedStops() {
  return selectedStops;
}

/**
 * Search for routes between the selected stops
 */
async function searchRoutes() {
  // Only proceed if both stops are selected
  if (!selectedStops.from || !selectedStops.to) {
    console.warn('Both from and to stops must be selected');
    return;
  }

  try {
    const response = await fetch('/api/routes/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: selectedStops.from,
        to: selectedStops.to,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Error searching routes:', errorData.error);
      return;
    }

    const data = await response.json();
    console.log('Routes found:', data.routes);
    
    // Display the routes in the modal
    displayRoutesModal(data);
  } catch (error) {
    console.error('Error fetching routes:', error);
  }
}

/**
 * Display the routes modal with search results
 */
function displayRoutesModal(data) {
  const modal = document.getElementById('route-modal');
  const modalHeader = document.querySelector('.route-modal-header');
  const sortSelect = document.getElementById('sort');
  
  if (!modal) {
    console.error('Route modal not found');
    return;
  }

  // Store the routes data globally for sorting
  currentRoutesData = data;

  // Update the modal header with from/to information
  const headerText = document.createTextNode(`Routes from ${data.from} to ${data.to}`);
  
  // Clear previous content but preserve the close button
  const closeBtn = modalHeader.querySelector('#close-route-modal');
  modalHeader.textContent = ''; // Clear everything
  modalHeader.appendChild(headerText); // Add the new text
  if (closeBtn) {
    modalHeader.appendChild(closeBtn); // Re-add the close button at the end
  }

  // Reset sort dropdown to "Fastest"
  if (sortSelect) {
    sortSelect.value = 'Fastest';
  }

  // Render the routes with default (fastest) sorting applied
  const sorted = sortRoutes('Fastest', data.routes);
  renderRoutesTable(sorted);

  // Show the modal by removing the hidden class
  modal.classList.remove('hidden');
}

/**
 * Sort routes based on the selected criteria
 */
function sortRoutes(sortMethod, routes) {
  const routesCopy = [...routes];
  
  switch (sortMethod) {
    case 'Fastest':
      // Sort by duration (ascending), then by start time
      return routesCopy.sort((a, b) => {
        if (a.duration_mins !== b.duration_mins) {
          return a.duration_mins - b.duration_mins;
        }
        const aTime = parseInt(a.start_time.replace(':', ''));
        const bTime = parseInt(b.start_time.replace(':', ''));
        return aTime - bTime;
      });
    
    case 'Fewest Changes':
      // Sort by number of changes (ascending), then by duration
      return routesCopy.sort((a, b) => {
        if (a.changes !== b.changes) {
          return a.changes - b.changes;
        }
        return a.duration_mins - b.duration_mins;
      });
    
    default:
      return routesCopy;
  }
}

/**
 * Format a duration in minutes as human-readable text
 */
function formatDuration(mins) {
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  const remainder = mins % 60;
  return remainder > 0 ? `${hours}h ${remainder} min` : `${hours}h`;
}

/**
 * Build a walking-leg element for the detail panel
 */
function buildWalkLeg(leg) {
  const el = document.createElement('div');
  el.className = 'route-detail-leg route-detail-walk';
  el.innerHTML = `
    <span class="leg-icon icon-walk"></span>
    <div class="leg-info">
      <div class="leg-summary">Walk ${leg.distance_m}m • ${leg.duration_mins} min</div>
      <div class="leg-stops">${leg.from_stop} → ${leg.to_stop}</div>
    </div>
    <span class="leg-time">${leg.depart} – ${leg.arrive}</span>
  `;
  return el;
}

/**
 * Build a wait/transfer-leg element for the detail panel
 */
function buildWaitLeg(leg) {
  const el = document.createElement('div');
  el.className = 'route-detail-leg route-detail-wait';
  el.innerHTML = `
    <span class="leg-icon icon-walk"></span>
    <div class="leg-info">
      <div class="leg-summary">Change at ${leg.from_stop} • ${leg.duration_mins} min wait</div>
    </div>
    <span class="leg-time">${leg.depart} – ${leg.arrive}</span>
  `;
  return el;
}

/**
 * Build a transport (bus / train) leg element for the detail panel
 */
function buildTransportLeg(leg) {
  const el = document.createElement('div');
  el.className = 'route-detail-leg route-detail-ride';

  const modeIcon = leg.mode === 'bus' ? 'icon-bus' : 'icon-train';
  const service = leg.service || leg.mode;

  let intermediateHTML = '';
  if (leg.intermediate_stops && leg.intermediate_stops.length > 0) {
    const stopsHTML = leg.intermediate_stops
      .map(s => `<li><span class="intermediate-time">${s.time}</span> ${s.name}</li>`)
      .join('');
    intermediateHTML = `<ul class="intermediate-stops">${stopsHTML}</ul>`;
  }

  el.innerHTML = `
    <span class="leg-icon ${modeIcon}"></span>
    <div class="leg-info">
      <div class="leg-summary">${service} • ${leg.duration_mins} min</div>
      <div class="leg-stops">${leg.from_stop} → ${leg.to_stop}</div>
      ${intermediateHTML}
    </div>
    <span class="leg-time">${leg.depart} – ${leg.arrive}</span>
  `;
  return el;
}

/**
 * Toggle the expanded detail view for a route row
 */
function toggleRouteDetail(routeRow, route) {
  const existingDetail = routeRow.nextElementSibling;

  // If already expanded, collapse it
  if (existingDetail && existingDetail.classList.contains('route-detail')) {
    existingDetail.remove();
    routeRow.classList.remove('expanded');
    return;
  }

  // Collapse any other open detail
  document.querySelectorAll('.route-detail').forEach(d => d.remove());
  document.querySelectorAll('.route-row.expanded').forEach(r => r.classList.remove('expanded'));

  // Build the detail panel
  const detail = document.createElement('div');
  detail.className = 'route-detail';

  if (route.legs && route.legs.length > 0) {
    route.legs.forEach(leg => {
      if (leg.mode === 'walk') {
        detail.appendChild(buildWalkLeg(leg));
      } else if (leg.mode === 'wait') {
        detail.appendChild(buildWaitLeg(leg));
      } else {
        detail.appendChild(buildTransportLeg(leg));
      }
    });
  } else {
    detail.innerHTML = '<div class="route-detail-empty">No detailed leg information available for this route.</div>';
  }

  // Insert detail right after the clicked row
  routeRow.after(detail);
  routeRow.classList.add('expanded');
}

/**
 * Render the routes table with current data and sorting.
 * Each row is clickable to expand detailed leg information.
 */
function renderRoutesTable(routes) {
  const routeList = document.querySelector('.route-list');
  
  if (!routeList) {
    console.error('Route list not found');
    return;
  }

  // Clear existing routes (including any open details)
  routeList.innerHTML = '';

  if (!routes || routes.length === 0) {
    routeList.innerHTML = '<div class="route-row">No routes found for this journey.</div>';
    return;
  }

  // Add each route as a clickable row
  routes.forEach((route, index) => {
    const routeRow = document.createElement('div');
    routeRow.className = 'route-row' + (index % 2 === 1 ? ' alt' : '');
    routeRow.style.cursor = 'pointer';
    routeRow.title = 'Click to view route details';

    // Build transport icons container (shows full chain, e.g. bus → train → bus)
    const iconsContainer = document.createElement('span');
    iconsContainer.className = 'route-transport-icons';

    route.transport.forEach((mode, i) => {
      if (i > 0) {
        const arrow = document.createElement('span');
        arrow.className = 'transport-arrow';
        arrow.textContent = '›';
        iconsContainer.appendChild(arrow);
      }
      const icon = document.createElement('span');
      icon.className = mode === 'bus' ? 'icon-bus' : 'icon-train';
      iconsContainer.appendChild(icon);
    });

    // Changes badge
    if (route.changes > 0) {
      const badge = document.createElement('span');
      badge.className = 'changes-badge';
      badge.textContent = `${route.changes} change${route.changes > 1 ? 's' : ''}`;
      iconsContainer.appendChild(badge);
    }

    // Time display
    const timesSpan = document.createElement('span');
    timesSpan.className = 'route-times';
    timesSpan.textContent = `${route.start_time} − ${route.end_time}`;

    // Duration display
    const durationSpan = document.createElement('span');
    durationSpan.className = 'route-duration';
    durationSpan.textContent = formatDuration(route.duration_mins);

    // Expand indicator
    const expandIcon = document.createElement('span');
    expandIcon.className = 'route-expand-icon';
    expandIcon.textContent = '▼';

    // Assemble the row
    routeRow.appendChild(iconsContainer);
    routeRow.appendChild(timesSpan);
    routeRow.appendChild(durationSpan);
    routeRow.appendChild(expandIcon);

    // Click handler to toggle detail panel
    routeRow.addEventListener('click', () => toggleRouteDetail(routeRow, route));

    routeList.appendChild(routeRow);
  });
}

// ============================================================================
// END AUTOCOMPLETE FUNCTIONALITY
// ============================================================================

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize the interactive map
  initializeMap();
  
  // Initialize autocomplete for search inputs
  initializeAutocomplete();
  
  // Set up swap button functionality
  setupSwapButton();
  
  // Set up panel toggle event listeners
  const weatherBtn = document.getElementById('weather-btn');
  const notifBtn = document.getElementById('notif-btn');
  
  if (weatherBtn) {
    weatherBtn.addEventListener('click', toggleWeatherPanel);
  }
  
  if (notifBtn) {
    notifBtn.addEventListener('click', toggleNotificationsPanel);
  }

  // Set up route modal close button
  const closeRouteModalBtn = document.getElementById('close-route-modal');
  const routeModal = document.getElementById('route-modal');
  const sortSelect = document.getElementById('sort');
  
  if (closeRouteModalBtn && routeModal) {
    closeRouteModalBtn.addEventListener('click', () => {
      routeModal.classList.add('hidden');
    });
  }

  // Set up sort dropdown for routes
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      if (currentRoutesData && currentRoutesData.routes) {
        const sortMethod = e.target.value;
        const sortedRoutes = sortRoutes(sortMethod, currentRoutesData.routes);
        renderRoutesTable(sortedRoutes);
      }
    });
  }

  // Close modal when clicking outside of it
  if (routeModal) {
    routeModal.addEventListener('click', (event) => {
      if (event.target === routeModal) {
        routeModal.classList.add('hidden');
      }
    });
  }

  attachFaqEventHandlers();
  attachAccountEventHandlers();
  initWeatherSearch();

  // Restore colourblind mode from localStorage (before account fetch may override)
  const savedColorblindMode = JSON.parse(localStorage.getItem('colorblindMode') || 'false');
  if (savedColorblindMode) {
    applyColorblindMode(true);
  }

  refreshAccountView();
  
  // Health check for backend (if available)
  checkHealth();
});

// Check backend health status
async function checkHealth() {
  try {
    const res = await fetch('/api/health', { method: 'GET' });
    const data = await res.json();
    console.log('Backend status:', data.status || JSON.stringify(data));
  } catch (e) {
    console.log('Backend not reachable - running in frontend-only mode');
  }
}
