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
      
      // Clear autocomplete suggestions
      fromSuggestions.innerHTML = '';
      fromSuggestions.classList.remove('visible');
      toSuggestions.innerHTML = '';
      toSuggestions.classList.remove('visible');
      
      // Trigger input event on from-input to update autocomplete if needed
      fromInput.dispatchEvent(new Event('input', { bubbles: true }));
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
    const marker = L.circleMarker([location.lat, location.lng], {
      radius: 9,
      fillColor: '#d32f2f',
      color: '#b71c1c',
      weight: 1,
      opacity: 1,
      fillOpacity: 0.35,
    });

    marker.addTo(map);

    const popupImageMarkup = location.image
      ? `<img src="${location.image}" alt="${location.name} photo" style="width: 100%; height: 120px; object-fit: cover; border-radius: 10px; margin-bottom: 10px;" />`
      : '';

    marker.bindPopup(`
      <div style="font-family: 'Segoe UI', Arial; min-width: 220px; max-width: 260px;">
        ${popupImageMarkup}
        <h3 style="margin: 0 0 8px 0; color: #b71c1c; font-size: 1.1rem;">${location.name}</h3>
        <p style="margin: 0; font-size: 0.95rem; color: #333;">${location.description}</p>
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

  // Set max bounds with edges at: far right Manchester (east), bottom Liverpool (south), 
  // most western coast (west), top Keswick (north). Prevent viewing beyond these limits.
  const bounds = L.latLngBounds(
    L.latLng(53.3665, -3.5),      // Southwest: bottom of Liverpool, most western coast
    L.latLng(54.6200, -2.211)     // Northeast: top of Keswick, far right of Manchester
  );
  map.setMaxBounds(bounds);
  
  // Fit map to bounds with padding to ensure bounds are visible
  map.fitBounds(bounds, { padding: [50, 50] });
  
  // Set zoom constraints to prevent seeing beyond bounds at any zoom level
  map.setMinZoom(9);
  map.setMaxZoom(19);
  
  // Add responsive zoom: when window is resized (including fullscreen), 
  // adjust zoom to maintain the same geographic bounds visibility
  window.addEventListener('resize', function() {
    map.fitBounds(bounds, { padding: [50, 50] });
  });

  return map;
}

// Toggle weather panel visibility
function toggleWeatherPanel() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const faqPanel = document.getElementById('faq-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');
  
  weatherPanel.classList.toggle('hidden');
  notifPanel.classList.add('hidden');
  
  // Close other panels when weather is opened
  if (!weatherPanel.classList.contains('hidden')) {
    faqPanel?.classList.add('hidden');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
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

  attachFaqEventHandlers();
  attachAccountEventHandlers();
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
