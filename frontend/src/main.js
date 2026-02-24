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
      image: '',
    },
    {
      name: 'Manchester',
      lat: 53.4795,
      lng: -2.2451,
      description: 'Manchester - Major industrial and commercial city in the heart of Greater Manchester.',
      image: '',
    },
    {
      name: 'Preston',
      lat: 53.7593,
      lng: -2.6993,
      description: 'Preston - England\'s newest city, cultural hub of Lancashire.',
      image: '../../docs/software-design-doc-source/Assets/preston.png',
    },
    {
      name: 'Blackburn',
      lat: 53.7493,
      lng: -2.4841,
      description: 'Blackburn - Historic textile town, home to the cathedral.',
      image: '../../docs/software-design-doc-source/Assets/blackburn.png',
    },
    {
      name: 'Lytham-St-Annes',
      lat: 53.7485,
      lng: -2.9991,
      description: 'Lytham-St-Annes - Seaside town on the Fylde coast.',
      image: '',
    },
    {
      name: 'Kirkham',
      lat: 53.7827,
      lng: -2.8715,
      description: 'Kirkham - Market town in the heart of the Fylde.',
      image: '',
    },
    {
      name: 'Poulton-le-Fylde',
      lat: 53.8461,
      lng: -2.9905,
      description: 'Poulton-le-Fylde - Market town in the heart of the Fylde.',
      image: '../../docs/software-design-doc-source/Assets/poulton_le_fylde.png',
    },
    {
      name: 'Fleetwood',
      lat: 53.9220,
      lng: -3.0327,
      description: 'Fleetwood - Coastal town at the mouth of the River Wyre and historic fishing port.',
      image: '',
    },
    {
      name: 'Blackpool',
      lat: 53.8179,
      lng: -3.0510,
      description: 'Blackpool - Iconic seaside resort with the famous Blackpool Tower.',
      image: '../../docs/software-design-doc-source/Assets/blackpool.png',
    },
    {
      name: 'Garstang',
      lat: 53.9016,
      lng: -2.7735,
      description: 'Garstang - Historic market town on the River Wyre.',
      image: '',
    },
    {
      name: 'Lancaster',
      lat: 54.0488,
      lng: -2.8013,
      description: 'Lancaster - Historic city with a medieval castle and university.',
      image: '../../docs/software-design-doc-source/Assets/lancaster.png',
    },
    {
      name: 'Morecambe',
      lat: 54.0721,
      lng: -2.8651,
      description: 'Morecambe - Seaside town known for its promenade and bay views.',
      image: '../../docs/software-design-doc-source/Assets/morecambe.png',
    },
    {
      name: 'Heysham',
      lat: 54.0495,
      lng: -2.8903,
      description: 'Heysham - Coastal village with nuclear power station and maritime heritage.',
      image: '',
    },
    {
      name: 'Carnforth',
      lat: 54.1282,
      lng: -2.7701,
      description: 'Carnforth - Village known for its railway heritage.',
      image: '',
    },
    {
      name: 'Kirkby-Lonsdale',
      lat: 54.2018,
      lng: -2.5967,
      description: 'Kirkby-Lonsdale - Picturesque village in the Lune Valley.',
      image: '',
    },
    {
      name: 'Grange-Over-Sands',
      lat: 54.1931,
      lng: -2.9095,
      description: 'Grange-Over-Sands - Charming coastal resort on Morecambe Bay.',
      image: '',
    },
    {
      name: 'Cartmel',
      lat: 54.2009,
      lng: -2.9529,
      description: 'Cartmel - Picturesque village famous for its Priory and steeplechase racecourse.',
      image: '',
    },
    {
      name: 'Kendal',
      lat: 54.3290,
      lng: -2.7472,
      description: 'Kendal - Gateway to the Lake District, historic market town.',
      image: '',
    },
    {
      name: 'Windermere',
      lat: 54.3792,
      lng: -2.9063,
      description: 'Windermere - Heart of the Lake District with England\'s largest lake.',
      image: '',
    },
    {
      name: 'Ambleside',
      lat: 54.4316,
      lng: -2.9622,
      description: 'Ambleside - Picturesque Lake District town on the shores of Lake Windermere.',
      image: '',
    },
    {
      name: 'Barrow-in-Furness',
      lat: 54.1289,
      lng: -3.2269,
      description: 'Barrow-in-Furness - Industrial town on the Irish Sea coast.',
      image: '',
    },
    {
      name: 'Keswick',
      lat: 54.6010,
      lng: -3.1376,
      description: 'Keswick - Historic market town in the northern Lake District.',
      image: '',
    },
  ];

  // Add markers for each location with popups and toggle functionality
  locations.forEach(location => {
    const marker = L.circleMarker([location.lat, location.lng], {
      radius: 8,
      fillColor: '#d32f2f',
      color: '#b71c1c',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
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
  
  weatherPanel.classList.toggle('hidden');
  notifPanel.classList.add('hidden');
}

// Toggle notifications panel visibility
function toggleNotificationsPanel() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  
  notifPanel.classList.toggle('hidden');
  weatherPanel.classList.add('hidden');
}

function openFaqPanel() {
  const faqPanel = document.getElementById('faq-panel');
  if (faqPanel) {
    faqPanel.classList.remove('hidden');
    faqPanel.setAttribute('aria-hidden', 'false');
  }
}

function closeFaqPanel() {
  const faqPanel = document.getElementById('faq-panel');
  if (faqPanel) {
    faqPanel.classList.add('hidden');
    faqPanel.setAttribute('aria-hidden', 'true');
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
  document.getElementById('auth-modal')?.classList.remove('hidden');
  document.getElementById('account-modal')?.classList.add('hidden');
}

function closeAuthModal() {
  document.getElementById('auth-modal')?.classList.add('hidden');
}

function openAccountModal() {
  document.getElementById('account-modal')?.classList.remove('hidden');
  document.getElementById('auth-modal')?.classList.add('hidden');
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

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize the interactive map
  initializeMap();
  
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
