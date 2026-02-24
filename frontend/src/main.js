/*
  main.js - Main application script for Transport for North West
  Handles interactive map initialization, panel toggling, and API interactions
*/

const authState = {
  token: localStorage.getItem('authToken') || null,
  user: null,
};

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
      name: 'Preston',
      lat: 53.7578,
      lng: -2.7059,
      description: 'Preston - England\'s newest city, cultural hub of Lancashire.',
      image: '../../docs/software-design-doc-source/Assets/preston.png',
    },
    {
      name: 'Blackpool',
      lat: 53.8160,
      lng: -3.0500,
      description: 'Blackpool - Iconic seaside resort with the famous Blackpool Tower.',
      image: '../../docs/software-design-doc-source/Assets/blackpool.png',
    },
    {
      name: 'Lancaster',
      lat: 54.0466,
      lng: -2.8015,
      description: 'Lancaster - Historic city with a medieval castle and university.',
      image: '../../docs/software-design-doc-source/Assets/lancaster.png',
    },
    {
      name: 'Morecambe',
      lat: 54.0740,
      lng: -2.8650,
      description: 'Morecambe - Seaside town known for its promenade and bay views.',
      image: '../../docs/software-design-doc-source/Assets/morecambe.png',
    },
    {
      name: 'Fleetwood',
      lat: 53.9176,
      lng: -3.0102,
      description: 'Fleetwood - Coastal town at the mouth of the River Wyre and historic fishing port.',
      image: '',
    },
    {
      name: 'Wyre Coast',
      lat: 53.8820,
      lng: -3.0380,
      description: 'Wyre Coast - Coastal stretch covering Cleveleys and the Wyre estuary shoreline.',
      image: '',
    },
    {
      name: 'Poulton-le-Fylde',
      lat: 53.8468,
      lng: -2.9920,
      description: 'Poulton-le-Fylde - Market town in the heart of the Fylde.',
      image: '../../docs/software-design-doc-source/Assets/poulton_le_fylde.png',
    },
  ];

  // Add markers for each location with popups
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
  });

  // Set max bounds to prevent panning too far from region
  const bounds = L.latLngBounds(
    L.latLng(53.68, -3.28),  // Southwest
    L.latLng(54.12, -2.62)   // Northeast
  );
  map.setMaxBounds(bounds);

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
