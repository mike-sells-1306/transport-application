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
  const mapCenter = [53.8, -3.0];
  const initialZoom = 10;

  // Create Leaflet map instance
  const map = L.map('map').setView(mapCenter, initialZoom);

  // Add OpenStreetMap tile layer
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19,
    minZoom: 8,
  }).addTo(map);

  // Define key towns and locations in the North West region
  const locations = [
    { name: 'Preston', lat: 53.7578, lng: -2.7059, description: 'Preston - England\'s newest city, cultural hub of Lancashire' },
    { name: 'Blackpool', lat: 53.8132, lng: -3.0527, description: 'Blackpool - Iconic seaside resort with the famous Blackpool Tower' },
    { name: 'Lancaster', lat: 54.0457, lng: -2.8007, description: 'Lancaster - Historic city with a medieval castle and university' },
    { name: 'Wyre Bay', lat: 53.9, lng: -3.2, description: 'Wyre Bay - Beautiful coastal area on the Irish Sea' },
    { name: 'Fleetwood', lat: 53.9175, lng: -3.2868, description: 'Fleetwood - Charming seaside town and major fishing port' },
    { name: 'Poulton-le-Fylde', lat: 53.8657, lng: -3.0396, description: 'Poulton-le-Fylde - Market town in the heart of the Fylde' },
    { name: 'Blackburn', lat: 53.7444, lng: -2.4829, description: 'Blackburn - Historic textile town, home to the cathedral' },
    { name: 'Barrow-in-Furness', lat: 54.1088, lng: -3.2342, description: 'Barrow-in-Furness - Industrial town on the Irish Sea coast' },
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

    // Add popup on marker click
    marker.bindPopup(`
      <div style="font-family: 'Segoe UI', Arial; min-width: 220px;">
        <h3 style="margin: 0 0 8px 0; color: #b71c1c; font-size: 1.1rem;">${location.name}</h3>
        <p style="margin: 0; font-size: 0.95rem; color: #333;">${location.description}</p>
      </div>
    `);

    // Update info card when marker is clicked
    marker.on('click', () => {
      updateInfoCard(location);
    });
  });

  // Set max bounds to prevent panning too far from region
  const bounds = L.latLngBounds(
    L.latLng(53.5, -3.5),  // Southwest
    L.latLng(54.5, -2.0)   // Northeast
  );
  map.setMaxBounds(bounds);

  return map;
}

// Update info card with location information
function updateInfoCard(location) {
  const infoCard = document.querySelector('.info-card');
  const heading = infoCard.querySelector('h2');
  const description = infoCard.querySelector('p');
  
  heading.textContent = location.name.toUpperCase();
  description.textContent = location.description;
  
  // Show the info card
  infoCard.classList.remove('hidden');
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
