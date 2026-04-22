/*
  main.js - Main application script for Transport for North West
  Handles interactive map initialization, panel toggling, and API interactions
*/

const authState = {
  token: localStorage.getItem('authToken') || null,
  user: null,
};

const ACCESSIBILITY_DEFAULTS = {
  zoomLevel: 1,
  colorMode: 'none',
  fontSize: 'normal',
};

const ACCESSIBILITY_MODES = new Set(['none', 'deuteranopia', 'protanopia', 'tritanopia', 'achromatopsia']);

const ACCESSIBILITY_FONT_SIZES = new Set(['small', 'normal', 'large']);

const ACCESSIBILITY_MODE_DEFAULT_MAP_STYLE = {
  deuteranopia: 'osm-standard',
  protanopia: 'osm-standard',
  tritanopia: 'osm-standard',
  achromatopsia: 'osm-standard',
};

const accessibilityState = {
  ...ACCESSIBILITY_DEFAULTS,
};

const DEFAULT_LOCALE = 'en-GB';
const SUPPORTED_LOCALES = ['en-GB', 'en-US', 'cy-GB', 'fr-FR', 'de-DE', 'es-ES', 'zh-CN', 'hi-IN', 'ar', 'bn-BD', 'pt-BR', 'ru-RU', 'ur-PK'];
const RESOURCE_LOCALES = ['en-GB', 'cy-GB', 'fr-FR', 'de-DE', 'es-ES', 'zh-CN', 'hi-IN', 'ar', 'bn-BD', 'pt-BR', 'ru-RU', 'ur-PK'];
const LOCALE_STORAGE_KEY = 'preferredLocale';
const LOCALE_DISPLAY_LABELS = {
  'en-GB': '🇬🇧 English (United Kingdom)',
  'en-US': '🇺🇸 English (United States)',
  'cy-GB': '🏴 Cymraeg (Y Deyrnas Unedig)',
  'fr-FR': '🇫🇷 Français (France)',
  'de-DE': '🇩🇪 Deutsch (Deutschland)',
  'es-ES': '🇪🇸 Español (España)',
  'zh-CN': '🇨🇳 中文（中国）',
  'hi-IN': '🇮🇳 हिन्दी (भारत)',
  'ar': '🌍 العربية',
  'bn-BD': '🇧🇩 বাংলা (বাংলাদেশ)',
  'pt-BR': '🇧🇷 Português (Brasil)',
  'ru-RU': '🇷🇺 Русский (Россия)',
  'ur-PK': '🇵🇰 اردو (پاکستان)',
};

const i18nState = {
  locale: DEFAULT_LOCALE,
  bundles: new Map(),
};

function deepGetMessage(obj, key) {
  if (!obj || !key) return undefined;
  return key.split('.').reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), obj);
}

function interpolateMessage(template, params = {}) {
  return String(template).replace(/\{(\w+)\}/g, (_, token) => {
    return params[token] != null ? String(params[token]) : `{${token}}`;
  });
}

async function loadLocaleBundle(localeCode) {
  const locale = String(localeCode || '').trim();
  if (!locale) return {};

  if (i18nState.bundles.has(locale)) {
    return i18nState.bundles.get(locale);
  }

  try {
    const response = await fetch(`locales/${locale}.json`);
    if (!response.ok) {
      throw new Error(`Missing locale bundle: ${locale}`);
    }
    const bundle = await response.json();
    i18nState.bundles.set(locale, bundle);
    return bundle;
  } catch (error) {
    console.warn(error.message);
    i18nState.bundles.set(locale, {});
    return {};
  }
}

function resolveLanguageFallback(locale) {
  const lang = String(locale || '').split('-')[0].toLowerCase();
  if (!lang) return DEFAULT_LOCALE;

  const match = RESOURCE_LOCALES.find(code => code.toLowerCase().startsWith(`${lang}-`) || code.toLowerCase() === lang);
  return match || DEFAULT_LOCALE;
}

function t(key, params = {}) {
  const locale = i18nState.locale || DEFAULT_LOCALE;

  const specific = deepGetMessage(i18nState.bundles.get(locale), key);
  if (specific !== undefined) {
    return interpolateMessage(specific, params);
  }

  const genericLocale = resolveLanguageFallback(locale);
  const generic = deepGetMessage(i18nState.bundles.get(genericLocale), key);
  if (generic !== undefined) {
    return interpolateMessage(generic, params);
  }

  const fallback = deepGetMessage(i18nState.bundles.get(DEFAULT_LOCALE), key);
  if (fallback !== undefined) {
    return interpolateMessage(fallback, params);
  }

  return key;
}

function getLocaleDisplayName(localeCode) {
  if (LOCALE_DISPLAY_LABELS[localeCode]) {
    return LOCALE_DISPLAY_LABELS[localeCode];
  }
  const translated = t(`locale.${localeCode}`);
  return translated === `locale.${localeCode}` ? localeCode : translated;
}

function formatLocalizedNumber(value, options = {}) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value ?? '');
  }
  return new Intl.NumberFormat(i18nState.locale || DEFAULT_LOCALE, options).format(numberValue);
}

function formatLocalizedDateTime(value, options = {}) {
  const date = value instanceof Date ? value : new Date(value);
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
    return String(value ?? '');
  }

  return new Intl.DateTimeFormat(i18nState.locale || DEFAULT_LOCALE, {
    dateStyle: 'medium',
    timeStyle: 'short',
    ...options,
  }).format(date);
}

function formatLocalizedClockTime(timeString) {
  if (!timeString || typeof timeString !== 'string') {
    return String(timeString || '');
  }

  const [hourStr, minuteStr] = timeString.split(':');
  const hour = Number(hourStr);
  const minute = Number(minuteStr);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return timeString;
  }

  const date = new Date(Date.UTC(2000, 0, 1, hour, minute, 0));
  return new Intl.DateTimeFormat(i18nState.locale || DEFAULT_LOCALE, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(date);
}

function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(node => {
    const key = node.getAttribute('data-i18n');
    if (!key) return;
    node.textContent = t(key);
  });

  root.querySelectorAll('[data-i18n-placeholder]').forEach(node => {
    const key = node.getAttribute('data-i18n-placeholder');
    if (!key) return;
    node.setAttribute('placeholder', t(key));
  });

  root.querySelectorAll('[data-i18n-aria-label]').forEach(node => {
    const key = node.getAttribute('data-i18n-aria-label');
    if (!key) return;
    node.setAttribute('aria-label', t(key));
  });

  root.querySelectorAll('[data-i18n-title]').forEach(node => {
    const key = node.getAttribute('data-i18n-title');
    if (!key) return;
    node.setAttribute('title', t(key));
  });

  document.title = t('app.title');
}

async function setLocale(locale, options = {}) {
  const { persist = true, announce = true } = options;
  const requested = SUPPORTED_LOCALES.includes(locale) ? locale : DEFAULT_LOCALE;

  await loadLocaleBundle(DEFAULT_LOCALE);
  await loadLocaleBundle(resolveLanguageFallback(requested));

  i18nState.locale = requested;
  document.documentElement.setAttribute('lang', requested);

  if (persist) {
    localStorage.setItem(LOCALE_STORAGE_KEY, requested);
  }

  applyTranslations();
  refreshMapPopupTranslations();
  if (window.appMap && typeof window.appMap.getCurrentMapStyle === 'function') {
    updateMapStyleButtonUI(window.appMap.getCurrentMapStyle());
  }
  weatherCache = null;
  weatherCacheTimestamp = 0;
  updateRouteModalHeader();
  syncAccessibilityControls();
  updateAccessibilityLinkState(!document.getElementById('accessibility-panel')?.classList.contains('hidden'));
  updateRouteDownloadButtonState();

  if (currentRoutesData && !document.getElementById('route-modal')?.classList.contains('hidden')) {
    const sortMethod = document.getElementById('sort')?.value || 'soonest_arrival';
    renderRoutesTable(sortRoutes(sortMethod, currentRoutesData.routes));
  }

  if (!document.getElementById('weather-panel')?.classList.contains('hidden')) {
    renderWeatherPanel({ announce: false });
  }

  renderNotifications(latestNotifications, { announce: false });

  if (announce) {
    announceToScreenReader(t('announce.languageChanged', { locale: getLocaleDisplayName(requested) }));
  }
}

async function initializeLocalization() {
  await Promise.all(RESOURCE_LOCALES.map(loadLocaleBundle));

  const storedLocale = localStorage.getItem(LOCALE_STORAGE_KEY);
  const browserLocale = (navigator.languages || [navigator.language || DEFAULT_LOCALE])
    .find(code => SUPPORTED_LOCALES.includes(code) || SUPPORTED_LOCALES.some(supported => supported.split('-')[0] === String(code).split('-')[0]));

  const initialLocale = storedLocale || (SUPPORTED_LOCALES.includes(browserLocale) ? browserLocale : DEFAULT_LOCALE);
  await setLocale(initialLocale, { persist: false, announce: false });
}

function announceToScreenReader(message, priority = 'polite') {
  if (!message) {
    return;
  }

  const regionId = priority === 'assertive' ? 'sr-alert-region' : 'sr-live-region';
  const region = document.getElementById(regionId);
  if (!region) {
    return;
  }

  region.textContent = '';
  window.setTimeout(() => {
    region.textContent = message;
  }, 30);
}

function setFieldError(inputId, errorId, message = '') {
  const input = document.getElementById(inputId);
  const errorNode = document.getElementById(errorId);
  if (input) {
    input.setAttribute('aria-invalid', message ? 'true' : 'false');
  }
  if (errorNode) {
    errorNode.textContent = message;
  }
}

function validateEmailFormat(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
}

function localizeApiErrorMessage(rawMessage, fallbackKey = 'alerts.requestFailedGeneric') {
  const message = String(rawMessage || '').trim().toLowerCase();
  if (!message) {
    return t(fallbackKey);
  }

  const mappedErrors = [
    { pattern: 'invalid email', key: 'alerts.invalidEmail' },
    { pattern: 'invalid password', key: 'alerts.invalidPassword' },
    { pattern: 'already exists', key: 'alerts.accountAlreadyExists' },
    { pattern: 'unauthorized', key: 'alerts.unauthorized' },
    { pattern: 'forbidden', key: 'alerts.forbidden' },
    { pattern: 'not found', key: 'alerts.notFound' },
    { pattern: 'too many requests', key: 'alerts.tooManyRequests' },
    { pattern: 'network', key: 'alerts.networkError' },
    { pattern: 'request failed', key: 'alerts.requestFailedGeneric' },
  ];

  const match = mappedErrors.find(item => message.includes(item.pattern));
  return match ? t(match.key) : t(fallbackKey);
}

// Track which marker has an open popup
let currentOpenPopup = null;

// Store map marker references for theme updates
let mapMarkers = [];
const selectedStopMapMarkers = {
  from: null,
  to: null,
};
let activeMapStyleId = 'osm-standard';
let stopOverlayLayer = null;
let stopOverlayMarkers = new Map();
let stopOverlayRequestToken = 0;
let stopOverlayDebounceTimer = null;
const STOP_OVERLAY_ZOOM_THRESHOLD = 14;
const STOP_OVERLAY_FETCH_LIMIT = 450;
const STOP_NO_DATA_MESSAGE = 'Service information is currently unavailable for this stop. Please check again shortly.';

const LOCATION_CATALOG = [
  {
    id: 'liverpool',
    lat: 53.4072,
    lng: -2.9917,
    image: 'https://www.hope.ac.uk/media/lifeathope/images/City%20of%20Liverpool%20Main%20Image%20880x425.jpg',
  },
  {
    id: 'manchester',
    lat: 53.4795,
    lng: -2.2451,
    image: 'https://images.ctfassets.net/szez98lehkfm/5Et7n40qkVp1XWiFp8prq0/0d863f37c9779a0332b641616e280975/MyIC_Article_93787?w=730&h=410&fm=jpg&fit=fill',
  },
  {
    id: 'preston',
    lat: 53.7593,
    lng: -2.6993,
    image: 'https://visitpreston.co.uk/image/13304/Preston-Flag-Market/related.jpg?m=1677680887777',
  },
  {
    id: 'blackburn',
    lat: 53.7493,
    lng: -2.4841,
    image: 'https://upload.wikimedia.org/wikipedia/commons/5/55/Blackburn_Lancashire_Townscape.jpg',
  },
  {
    id: 'lytham_st_annes',
    lat: 53.7485,
    lng: -2.9991,
    image: 'https://hampshire.redkitedays.co.uk/wp-content/uploads/2024/06/Visit-Lytham-St-Annes-scaled.jpeg',
  },
  {
    id: 'kirkham',
    lat: 53.7827,
    lng: -2.8715,
    image: 'https://www.english-heritage.org.uk/siteassets/home/visit/places-to-visit/kirkham-priory/kirkham-twitter-card.jpg',
  },
  {
    id: 'poulton_le_fylde',
    lat: 53.8461,
    lng: -2.9905,
    image: 'https://upload.wikimedia.org/wikipedia/commons/1/1d/Market_day_in_Poulton_-_geograph.org.uk_-_4103554.jpg',
  },
  {
    id: 'fleetwood',
    lat: 53.9220,
    lng: -3.0327,
    image: 'https://www.visitfyldecoast.info/wp-content/uploads/2024/05/IMG_8526-scaled-1.jpg',
  },
  {
    id: 'blackpool',
    lat: 53.8179,
    lng: -3.0510,
    image: 'https://i.guim.co.uk/img/media/5d9e2da10d2400d30c68ed77c725bd04e124e0cd/0_179_5404_3242/master/5404.jpg?width=1200&height=900&quality=85&auto=format&fit=crop&s=86096e66ab7a04d4183121b8aa78f8c6',
  },
  {
    id: 'garstang',
    lat: 53.9016,
    lng: -2.7735,
    image: 'https://canalrivertrust.org.uk/media/image/ZUEi447LPBxcv0Ri4kX8tw/Jzvw5PsTGFJIY8aaA7cX9ZwNHe-7eZMHn3Ehx1aJ1P4/rs:fill:1900:1187:1:0/g:ce/aHR0cHM6Ly9jcnRwcm9kY21zdWtzMDEuYmxvYi5jb3JlLndpbmRvd3MubmV0L2ltYWdlLzAxODk5MjczLWNiMjQtNzk0YS04YjM1LTExNTU3MGNjMDY5Yg.webp',
  },
  {
    id: 'lancaster',
    lat: 54.0488,
    lng: -2.8013,
    image: 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/1c/02/20/ac/the-newly-restored-lower.jpg?w=800&h=500&s=1',
  },
  {
    id: 'morecambe',
    lat: 54.0721,
    lng: -2.8651,
    image: 'https://www.hawthornscaravanpark.co.uk/wp-content/uploads/2023/09/lancashires-coastline-morecambe-bay-scaled.jpg',
  },
  {
    id: 'heysham',
    lat: 54.0495,
    lng: -2.8903,
    image: 'https://nt.global.ssl.fastly.net/binaries/content/gallery/website/national/regions/liverpool-lancashire/places/heysham-coast/library/beach-heysham-coast-lancashire-1525498.jpg',
  },
  {
    id: 'carnforth',
    lat: 54.1282,
    lng: -2.7701,
    image: 'https://dynamic-media-cdn.tripadvisor.com/media/photo-o/28/eb/14/0c/leighton-hall-front-view.jpg?w=600&h=-1&s=1',
  },
  {
    id: 'kirkby_lonsdale',
    lat: 54.2018,
    lng: -2.5967,
    image: 'https://www.thetimes.com/imageserver/image/%2Fmethode%2Fsundaytimes%2Fprod%2Fweb%2Fbin%2F2fb016a4-44d1-11e9-8121-489737db5c2b.jpg?crop=2250%2C1266%2C0%2C117',
  },
  {
    id: 'grange_over_sands',
    lat: 54.1931,
    lng: -2.9095,
    image: 'https://www.visitcumbria.com/wp-content/uploads/2024/11/Grange-over-Sands-Village.jpg',
  },
  {
    id: 'cartmel',
    lat: 54.2009,
    lng: -2.9529,
    image: 'https://www.sykescottages.co.uk/inspiration/wp-content/uploads/things-to-do-in-Cartmel.jpg',
  },
  {
    id: 'kendal',
    lat: 54.3290,
    lng: -2.7472,
    image: 'https://eu-assets.simpleview-europe.com/golakes/imageresizer/?image=%2Fdmsimgs%2F6D1CFF58CABBCFA6EE82AAFCEE101B4D85DCC848.jpg&action=ProductDetailPro',
  },
  {
    id: 'windermere',
    lat: 54.3792,
    lng: -2.9063,
    image: 'https://www.lakelovers.co.uk/blog/wp-content/uploads/sites/15/2025/04/Blog-header-image-1400-x-950-18.png',
  },
  {
    id: 'ambleside',
    lat: 54.4316,
    lng: -2.9622,
    image: 'https://www.thegables-ambleside.co.uk/images/galleries/thingstodo/ambleside2.jpg',
  },
  {
    id: 'barrow_in_furness',
    lat: 54.289,
    lng: -3.2269,
    image: 'https://www.leahough.co.uk/wp-content/uploads/2025/06/Barrow-in-Furness.jpg',
  },
  {
    id: 'keswick',
    lat: 54.6010,
    lng: -3.1376,
    image: 'https://www.armathwaite-hall.com/wp-content/uploads/2019/08/Keswick.jpg',
  },
];

function getLocalizedLocation(locationId) {
  return {
    name: t(`locations.${locationId}.name`),
    description: t(`locations.${locationId}.description`),
  };
}

function buildMapPopupMarkup(location) {
  const localized = getLocalizedLocation(location.id);
  const popupImageMarkup = location.image
    ? `<img src="${location.image}" alt="${t('map.popupImageAlt', { location: localized.name })}" style="width: 100%; height: 120px; object-fit: cover; border-radius: 10px; margin-bottom: 10px;" />`
    : '';

  return `
      <div class="popup-content">
        ${popupImageMarkup}
        <h3 class="popup-title">${localized.name}</h3>
        <p class="popup-description">${localized.description}</p>
      </div>
    `;
}

function refreshMapPopupTranslations() {
  mapMarkers.forEach(({ marker, location }) => {
    marker.bindPopup(buildMapPopupMarkup(location));
  });
}

function getActiveLeafletMap() {
  if (!window.appMap || typeof window.appMap.addLayer !== 'function') {
    return null;
  }
  return window.appMap;
}

function getStopCoordinates(stop) {
  if (!stop) {
    return null;
  }
  const lat = Number(stop.lat);
  const lng = Number(stop.lon ?? stop.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null;
  }
  return [lat, lng];
}

function removeSelectedStopMarker(inputType) {
  const map = getActiveLeafletMap();
  const marker = selectedStopMapMarkers[inputType];
  if (!marker) {
    return;
  }

  if (map && map.hasLayer(marker)) {
    map.removeLayer(marker);
  }
  selectedStopMapMarkers[inputType] = null;
}

function focusMapOnSelectedStopMarkers() {
  const map = getActiveLeafletMap();
  if (!map) {
    return;
  }

  const activeMarkers = ['from', 'to']
    .map(key => selectedStopMapMarkers[key])
    .filter(marker => marker && map.hasLayer(marker));

  if (activeMarkers.length === 0) {
    return;
  }

  if (activeMarkers.length === 1) {
    map.flyTo(activeMarkers[0].getLatLng(), Math.max(13, map.getZoom()), {
      duration: 0.45,
    });
    return;
  }

  const bounds = L.latLngBounds(activeMarkers.map(marker => marker.getLatLng()));
  map.fitBounds(bounds, { padding: [60, 60], maxZoom: 14 });
}

function createStopMarkerIcon(number, color, label) {
  const html = `
    <div style="
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      background-color: ${color};
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      cursor: pointer;
      font-weight: bold;
      color: white;
      font-size: 18px;
      position: relative;
    ">
      <span>${number}</span>
      <div style="
        position: absolute;
        bottom: -10px;
        width: 0;
        height: 0;
        border-left: 7px solid transparent;
        border-right: 7px solid transparent;
        border-top: 10px solid ${color};
      "></div>
    </div>
  `;

  return L.divIcon({
    html: html,
    iconSize: [40, 50],
    iconAnchor: [20, 50],
    popupAnchor: [0, -50],
    className: 'custom-stop-marker',
  });
}

function syncSelectedStopMapMarkers(options = {}) {
  const { focus = false } = options;
  const map = getActiveLeafletMap();
  if (!map) {
    return;
  }

  const stopConfigs = [
    { key: 'from', color: '#0ea5e9', number: '1', popupLabel: 'Start' },
    { key: 'to', color: '#f97316', number: '2', popupLabel: 'End' },
  ];

  stopConfigs.forEach(({ key, color, number, popupLabel }) => {
    const stop = selectedStops[key];
    const coordinates = getStopCoordinates(stop);

    if (!coordinates) {
      removeSelectedStopMarker(key);
      return;
    }

    let marker = selectedStopMapMarkers[key];
    const icon = createStopMarkerIcon(number, color, popupLabel);

    if (!marker) {
      marker = L.marker(coordinates, { icon: icon }).addTo(map);
      selectedStopMapMarkers[key] = marker;
    } else {
      marker.setLatLng(coordinates);
      marker.setIcon(icon);
      if (!map.hasLayer(marker)) {
        marker.addTo(map);
      }
    }

    marker.bindPopup(`<strong>${popupLabel}:</strong> ${stop.name || ''}`);
  });

  if (focus) {
    focusMapOnSelectedStopMarkers();
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function openStopServicesModal(stopName) {
  const modal = document.getElementById('stop-services-modal');
  const title = document.getElementById('stop-services-modal-title-text');
  if (!modal || !title) {
    return;
  }
  title.textContent = stopName || 'Stop';
  resetFloatingPanelToDefault('stop-services-modal');
  modal.classList.remove('hidden');
  announceToScreenReader(`Opened service details for ${stopName || 'selected stop'}.`);
}

function closeStopServicesModal() {
  const modal = document.getElementById('stop-services-modal');
  if (!modal || modal.classList.contains('hidden')) {
    return;
  }
  modal.classList.add('hidden');
  resetFloatingPanelToDefault('stop-services-modal');
  announceToScreenReader('Closed stop service details.');
}

function renderStopServicesModalLoading(stop) {
  const list = document.getElementById('stop-services-list');
  if (!list) {
    return;
  }
  list.innerHTML = `
    <div class="route-loading" role="status" aria-live="polite">
      <div class="route-loading-spinner" aria-hidden="true"></div>
      <div class="route-loading-texts">
        <strong>Loading services…</strong>
        <span>${escapeHtml(stop?.name || 'Stop')}</span>
      </div>
    </div>
  `;
}

function renderStopServicesModalNoData() {
  const list = document.getElementById('stop-services-list');
  if (!list) {
    return;
  }
  list.innerHTML = `<div class="route-row stop-modal-empty">${escapeHtml(STOP_NO_DATA_MESSAGE)}</div>`;
}

function buildStopServiceRow(service) {
  const mode = String(service?.mode || '').trim().toLowerCase();
  const icon = mode === 'train'
    ? '<span class="icon-train" aria-hidden="true"></span>'
    : '<span class="icon-bus" aria-hidden="true"></span>';
  const serviceName = String(service?.service || '').trim() || 'Service';
  const finalDestination = String(service?.finalDestination || '').trim();
  const arrivalAtStop = String(service?.arrivalAtStop || '').trim();
  const arrivalAtFinalDestination = String(service?.arrivalAtFinalDestination || '').trim();

  if (!finalDestination || !arrivalAtStop || !arrivalAtFinalDestination) {
    return '';
  }

  return `
    <tr class="stop-service-row" role="row" aria-label="${escapeHtml(serviceName)} to ${escapeHtml(finalDestination)}">
      <td class="stop-service-col-mode" role="cell">${icon}</td>
      <td class="stop-service-col-stop-time" role="cell">${escapeHtml(formatLocalizedClockTime(arrivalAtStop))}</td>
      <td class="stop-service-col-final-time" role="cell">${escapeHtml(formatLocalizedClockTime(arrivalAtFinalDestination))}</td>
      <td class="stop-service-col-service" role="cell">${escapeHtml(serviceName)}</td>
      <td class="stop-service-col-destination" role="cell">${escapeHtml(finalDestination)}</td>
    </tr>
  `;
}

function renderStopServicesModal(stop, services) {
  const list = document.getElementById('stop-services-list');
  if (!list) {
    return;
  }

  if (!Array.isArray(services) || services.length === 0) {
    renderStopServicesModalNoData();
    return;
  }

  const rows = services.map(buildStopServiceRow).filter(Boolean).join('');

  if (!rows) {
    renderStopServicesModalNoData();
    return;
  }

  list.innerHTML = `
    <table class="stop-services-table" role="table" aria-label="Upcoming services for ${escapeHtml(stop?.name || 'stop')}">
      <thead>
        <tr>
          <th aria-hidden="true"></th>
          <th>At stop</th>
          <th>Final arrival</th>
          <th>Service</th>
          <th>Final destination</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `;
}

function createStopMarker(stop) {
  const marker = L.circleMarker([stop.lat, stop.lon], {
    radius: 5,
    fillColor: '#1D6FD6',
    color: '#0D3B80',
    weight: 1.3,
    opacity: 0.95,
    fillOpacity: 0.8,
  });

  marker.on('click', async () => {
    openStopServicesModal(stop.name || 'Stop');
    renderStopServicesModalLoading(stop);

    try {
      const response = await fetch(`/api/stops/${encodeURIComponent(stop.atcoCode)}/services?limit=10`);
      if (!response.ok) {
        renderStopServicesModalNoData();
        return;
      }

      const data = await response.json();
      renderStopServicesModal(stop, data?.services || []);
    } catch (error) {
      renderStopServicesModalNoData();
    }
  });

  return marker;
}

function clearStopOverlayMarkers() {
  if (stopOverlayLayer) {
    stopOverlayLayer.clearLayers();
  }
  stopOverlayMarkers.clear();
}

async function updateStopOverlayMarkers(map) {
  if (!map || !stopOverlayLayer) {
    return;
  }

  const currentZoom = map.getZoom();
  if (currentZoom < STOP_OVERLAY_ZOOM_THRESHOLD) {
    clearStopOverlayMarkers();
    return;
  }

  const bounds = map.getBounds();
  const params = new URLSearchParams({
    minLat: String(bounds.getSouth()),
    maxLat: String(bounds.getNorth()),
    minLon: String(bounds.getWest()),
    maxLon: String(bounds.getEast()),
    limit: String(STOP_OVERLAY_FETCH_LIMIT),
  });

  const requestToken = ++stopOverlayRequestToken;

  try {
    const response = await fetch(`/api/stops/in-bounds?${params.toString()}`);
    if (!response.ok) {
      return;
    }

    const payload = await response.json();
    if (requestToken !== stopOverlayRequestToken) {
      return;
    }

    const stops = Array.isArray(payload?.stops) ? payload.stops : [];
    const nextKeys = new Set();

    stops.forEach(stop => {
      const key = String(stop?.atcoCode || '').trim();
      if (!key || !Number.isFinite(Number(stop?.lat)) || !Number.isFinite(Number(stop?.lon))) {
        return;
      }

      nextKeys.add(key);
      if (stopOverlayMarkers.has(key)) {
        return;
      }

      const marker = createStopMarker(stop);
      stopOverlayMarkers.set(key, marker);
      marker.addTo(stopOverlayLayer);
    });

    Array.from(stopOverlayMarkers.keys()).forEach(existingKey => {
      if (nextKeys.has(existingKey)) {
        return;
      }
      const marker = stopOverlayMarkers.get(existingKey);
      if (marker && stopOverlayLayer.hasLayer(marker)) {
        stopOverlayLayer.removeLayer(marker);
      }
      stopOverlayMarkers.delete(existingKey);
    });
  } catch (error) {
    // Keep the previous visible markers when a fetch fails.
  }
}

function scheduleStopOverlayUpdate(map) {
  if (stopOverlayDebounceTimer) {
    clearTimeout(stopOverlayDebounceTimer);
  }
  stopOverlayDebounceTimer = setTimeout(() => {
    updateStopOverlayMarkers(map);
  }, 180);
}

// Store current routes data for sorting
let currentRoutesData = null;
const activeRouteSearchControllers = new Set();
const ROUTE_SEARCH_TIMEOUT_MS = 30000;
const DEFAULT_ROUTE_MODES = new Set(['walk', 'bus', 'rail', 'train', 'wait']);
let latestNotifications = [];

const FLOATING_PANEL_CONFIGS = [
  { id: 'route-modal', headerSelector: '.route-modal-header', minWidth: 500, minHeight: 300, resizable: true },
  { id: 'stop-services-modal', headerSelector: '.route-modal-header', minWidth: 540, minHeight: 260, resizable: true },
  { id: 'auth-modal', headerSelector: '.auth-modal-header', minWidth: 420, minHeight: 260, resizable: true },
  { id: 'support-panel', headerSelector: '.faq-header', minWidth: 540, minHeight: 300, resizable: true },
  { id: 'accessibility-panel', headerSelector: '.faq-header', minWidth: 500, minHeight: 320, resizable: true },
];

const floatingPanelDefaults = new Map();

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

      setFieldError('from-input', 'from-input-error', '');
      setFieldError('to-input', 'to-input-error', '');
      syncSelectedStopMapMarkers({ focus: true });
      syncRouteModalWithInputState();
      updateJourneySearchButtonState();
      announceToScreenReader(t('announce.journeySwapped'));
    });
  }
}

function updateJourneySearchButtonState() {
  const searchBtn = document.getElementById('journey-search-btn');
  if (!searchBtn) {
    return;
  }

  searchBtn.disabled = !(selectedStops.from && selectedStops.to);
}

function setupJourneySearchButton() {
  const searchBtn = document.getElementById('journey-search-btn');
  if (!searchBtn) {
    return;
  }

  searchBtn.addEventListener('click', () => {
    searchRoutes();
  });

  updateJourneySearchButtonState();
}

function getFloatingPanelConfig(panelId) {
  return FLOATING_PANEL_CONFIGS.find(item => item.id === panelId) || null;
}

function getMapAreaBounds() {
  const mapArea = document.querySelector('.map-area');
  if (!mapArea) {
    return null;
  }

  const mapRect = mapArea.getBoundingClientRect();
  let minLeft = 0;

  const sidebar = document.querySelector('.sidebar');
  if (sidebar && !sidebar.classList.contains('minimized')) {
    const sidebarRect = sidebar.getBoundingClientRect();
    const overlapsMapHorizontally = sidebarRect.right > mapRect.left && sidebarRect.left < mapRect.right;
    const overlapsMapVertically = sidebarRect.bottom > mapRect.top && sidebarRect.top < mapRect.bottom;
    if (overlapsMapHorizontally && overlapsMapVertically) {
      minLeft = Math.max(minLeft, sidebarRect.right - mapRect.left);
    }
  }

  return {
    mapArea,
    mapRect,
    minLeft,
    minTop: 0,
    maxWidth: mapRect.width,
    maxHeight: mapRect.height,
  };
}

function clampFloatingPanelRect(rect, bounds, config) {
  const minWidth = Math.max(320, Number(config?.minWidth || 320));
  const minHeight = Math.max(200, Number(config?.minHeight || 200));
  const availableWidth = Math.max(180, bounds.maxWidth - bounds.minLeft);
  const availableHeight = Math.max(160, bounds.maxHeight - bounds.minTop);

  const effectiveMinWidth = Math.min(minWidth, availableWidth);
  const effectiveMinHeight = Math.min(minHeight, availableHeight);

  const width = Math.min(Math.max(rect.width, effectiveMinWidth), availableWidth);
  const height = Math.min(Math.max(rect.height, effectiveMinHeight), availableHeight);

  const maxLeft = Math.max(bounds.minLeft, bounds.maxWidth - width);
  const maxTop = Math.max(bounds.minTop, bounds.maxHeight - height);

  return {
    left: Math.min(Math.max(rect.left, bounds.minLeft), maxLeft),
    top: Math.min(Math.max(rect.top, bounds.minTop), maxTop),
    width,
    height,
  };
}

function setFloatingPanelRect(panel, rect) {
  panel.style.left = `${rect.left}px`;
  panel.style.top = `${rect.top}px`;
  panel.style.width = `${rect.width}px`;
  panel.style.height = `${rect.height}px`;
  panel.style.maxHeight = 'none';
  panel.style.transform = 'none';
}

function pinFloatingPanelToCurrentRect(panel, panelId) {
  const bounds = getMapAreaBounds();
  if (!bounds) {
    return;
  }

  const panelRect = panel.getBoundingClientRect();
  const config = getFloatingPanelConfig(panelId);
  const localRect = clampFloatingPanelRect({
    left: panelRect.left - bounds.mapRect.left,
    top: panelRect.top - bounds.mapRect.top,
    width: panelRect.width,
    height: panelRect.height,
  }, bounds, config);

  setFloatingPanelRect(panel, localRect);
}

function captureFloatingPanelDefault(panel, panelId) {
  const wasHidden = panel.classList.contains('hidden');
  const previousVisibility = panel.style.visibility;
  const previousPointerEvents = panel.style.pointerEvents;

  panel.style.left = '';
  panel.style.top = '';
  panel.style.width = '';
  panel.style.height = '';
  panel.style.maxHeight = '';
  panel.style.transform = '';

  if (wasHidden) {
    panel.classList.remove('hidden');
  }
  panel.style.visibility = 'hidden';
  panel.style.pointerEvents = 'none';

  const bounds = getMapAreaBounds();
  const panelRect = panel.getBoundingClientRect();
  const config = getFloatingPanelConfig(panelId);

  if (bounds) {
    const defaultRect = clampFloatingPanelRect({
      left: panelRect.left - bounds.mapRect.left,
      top: panelRect.top - bounds.mapRect.top,
      width: panelRect.width,
      height: panelRect.height,
    }, bounds, config);

    floatingPanelDefaults.set(panelId, defaultRect);
  }

  panel.style.visibility = previousVisibility;
  panel.style.pointerEvents = previousPointerEvents;
  if (wasHidden) {
    panel.classList.add('hidden');
  }
}

function resetFloatingPanelToDefault(panelId) {
  const panel = document.getElementById(panelId);
  const defaults = floatingPanelDefaults.get(panelId);
  const bounds = getMapAreaBounds();
  const config = getFloatingPanelConfig(panelId);

  if (!panel || !defaults || !bounds) {
    return;
  }

  const clamped = clampFloatingPanelRect({ ...defaults }, bounds, config);
  setFloatingPanelRect(panel, clamped);
}

function clampVisibleFloatingPanels() {
  const bounds = getMapAreaBounds();
  if (!bounds) {
    return;
  }

  FLOATING_PANEL_CONFIGS.forEach(({ id }) => {
    const panel = document.getElementById(id);
    if (!panel || panel.classList.contains('hidden')) {
      return;
    }

    pinFloatingPanelToCurrentRect(panel, id);
  });
}

function makeFloatingPanelDraggableAndResizable(panelId, config) {
  const panel = document.getElementById(panelId);
  if (!panel) {
    return;
  }

  panel.classList.add('floating-panel-draggable');

  const header = panel.querySelector(config.headerSelector);
  if (header) {
    header.classList.add('floating-drag-handle');
    header.addEventListener('mousedown', event => {
      if (event.button !== 0) {
        return;
      }
      if (event.target instanceof Element && event.target.closest('button,input,select,textarea,a,label')) {
        return;
      }

      pinFloatingPanelToCurrentRect(panel, panelId);

      const startLeft = panel.offsetLeft;
      const startTop = panel.offsetTop;
      const startX = event.clientX;
      const startY = event.clientY;

      const handleMouseMove = moveEvent => {
        const bounds = getMapAreaBounds();
        if (!bounds) {
          return;
        }

        const nextRect = clampFloatingPanelRect({
          left: startLeft + (moveEvent.clientX - startX),
          top: startTop + (moveEvent.clientY - startY),
          width: panel.offsetWidth,
          height: panel.offsetHeight,
        }, bounds, config);

        setFloatingPanelRect(panel, nextRect);
      };

      const stopDrag = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', stopDrag);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', stopDrag);
      event.preventDefault();
    });
  }

  if (config.resizable) {
    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'floating-panel-resize-handle';
    resizeHandle.setAttribute('aria-hidden', 'true');
    panel.appendChild(resizeHandle);

    resizeHandle.addEventListener('mousedown', event => {
      if (event.button !== 0) {
        return;
      }

      pinFloatingPanelToCurrentRect(panel, panelId);

      const startWidth = panel.offsetWidth;
      const startHeight = panel.offsetHeight;
      const startX = event.clientX;
      const startY = event.clientY;
      const startLeft = panel.offsetLeft;
      const startTop = panel.offsetTop;

      const handleMouseMove = moveEvent => {
        const bounds = getMapAreaBounds();
        if (!bounds) {
          return;
        }

        const rawWidth = startWidth + (moveEvent.clientX - startX);
        const rawHeight = startHeight + (moveEvent.clientY - startY);

        const nextRect = clampFloatingPanelRect({
          left: startLeft,
          top: startTop,
          width: rawWidth,
          height: rawHeight,
        }, bounds, config);

        setFloatingPanelRect(panel, nextRect);
      };

      const stopResize = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', stopResize);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', stopResize);
      event.preventDefault();
      event.stopPropagation();
    });
  }
}

function initializeFloatingPanels() {
  FLOATING_PANEL_CONFIGS.forEach(config => {
    const panel = document.getElementById(config.id);
    if (!panel) {
      return;
    }

    captureFloatingPanelDefault(panel, config.id);
    makeFloatingPanelDraggableAndResizable(config.id, config);
    resetFloatingPanelToDefault(config.id);
  });
}

// Initialize Leaflet map focused on North West England (Preston, Blackpool, Fylde, Wyre)
function initializeMap() {
  // Center coordinates: Between Preston and Blackpool, spanning the Fylde and Wyre coastline
  // Approximate center: 53.8° N, -3.0° W
  const mapCenter = [53.88, -3.02];
  const initialZoom = 11;

  const mapStylePresets = [
    {
      id: 'osm-standard',
      label: 'OSM Standard',
      shortLabel: 'OSM',
      title: 'Switch map style (current: OSM Standard)',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      options: {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'osm-hot',
      label: 'OSM Humanitarian',
      shortLabel: 'HOT',
      title: 'Switch map style (current: OSM Humanitarian)',
      url: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
      options: {
        attribution: '© OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team hosted by OpenStreetMap France',
        maxZoom: 20,
        minZoom: 9,
      },
    },
    {
      id: 'cyclosm',
      label: 'CyclOSM',
      shortLabel: 'CyclOSM',
      title: 'Switch map style (current: CyclOSM)',
      url: 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png',
      options: {
        attribution: '© OpenStreetMap contributors, CyclOSM',
        subdomains: 'abc',
        maxZoom: 20,
        minZoom: 9,
      },
    },
    {
      id: 'opentopomap',
      label: 'OpenTopoMap',
      shortLabel: 'Topo',
      title: 'Switch map style (current: OpenTopoMap)',
      url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
      options: {
        attribution: 'Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap (CC-BY-SA)',
        maxZoom: 17,
        minZoom: 9,
      },
    },
    {
      id: 'carto-voyager',
      label: 'CARTO Voyager',
      shortLabel: 'Voyager',
      title: 'Switch map style (current: CARTO Voyager)',
      url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
      options: {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'carto-voyager-labels-under',
      label: 'CARTO Voyager Labels Under',
      shortLabel: 'Voyager LU',
      title: 'Switch map style (current: CARTO Voyager Labels Under)',
      url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png',
      options: {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'carto-positron',
      label: 'CARTO Positron',
      shortLabel: 'Positron',
      title: 'Switch map style (current: CARTO Positron)',
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      options: {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'carto-darkmatter',
      label: 'CARTO Dark Matter',
      shortLabel: 'Dark',
      title: 'Switch map style (current: CARTO Dark Matter)',
      url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      options: {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'esri-street',
      label: 'Esri Street',
      shortLabel: 'Esri Street',
      title: 'Switch map style (current: Esri Street)',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      options: {
        attribution: 'Tiles © Esri — Source: Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), swisstopo, OpenStreetMap contributors, and the GIS User Community',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'esri-topo',
      label: 'Esri Topographic',
      shortLabel: 'Esri Topo',
      title: 'Switch map style (current: Esri Topographic)',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
      options: {
        attribution: 'Tiles © Esri — Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), swisstopo, OpenStreetMap contributors, and GIS User Community',
        maxZoom: 19,
        minZoom: 9,
      },
    },
    {
      id: 'esri-natgeo',
      label: 'Esri NatGeo',
      shortLabel: 'NatGeo',
      title: 'Switch map style (current: Esri NatGeo)',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}',
      options: {
        attribution: 'Tiles © Esri — National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC',
        maxZoom: 16,
        minZoom: 9,
      },
    },
  ];

  // Create Leaflet map instance
  const map = L.map('map', { zoomControl: false }).setView(mapCenter, initialZoom);
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  stopOverlayLayer = L.layerGroup().addTo(map);
  stopOverlayMarkers = new Map();
  stopOverlayRequestToken = 0;

  // Add default tile layer and expose a cycle helper for quick in-app style testing.
  let currentMapStyleIndex = 0;
  let activeBaseLayer = L.tileLayer(mapStylePresets[currentMapStyleIndex].url, mapStylePresets[currentMapStyleIndex].options).addTo(map);

  function applyMapStyleByIndex(nextIndex) {
    const normalized = ((nextIndex % mapStylePresets.length) + mapStylePresets.length) % mapStylePresets.length;
    const selected = mapStylePresets[normalized];

    if (activeBaseLayer) {
      map.removeLayer(activeBaseLayer);
    }

    activeBaseLayer = L.tileLayer(selected.url, selected.options).addTo(map);
    currentMapStyleIndex = normalized;
    activeMapStyleId = selected.id;
    updateMapMarkerColors();
    return selected;
  }

  map.getCurrentMapStyle = function() {
    return mapStylePresets[currentMapStyleIndex];
  };

  map.cycleMapStyle = function() {
    return applyMapStyleByIndex(currentMapStyleIndex + 1);
  };

  map.setMapStyleById = function(styleId) {
    const index = mapStylePresets.findIndex(style => style.id === styleId);
    if (index === -1) {
      return null;
    }
    return applyMapStyleByIndex(index);
  };

  map.getAvailableMapStyles = function() {
    return mapStylePresets;
  };

  const locations = LOCATION_CATALOG;

  // Add markers for each location with popups and toggle functionality
  locations.forEach(location => {
    const colors = getMarkerColors();
    const marker = L.circleMarker([location.lat, location.lng], {
      radius: 9,
      fillColor: colors.fillColor,
      color: colors.color,
      weight: colors.weight,
      opacity: colors.opacity,
      fillOpacity: colors.fillOpacity,
    });
    mapMarkers.push({ marker, location });

    marker.addTo(map);

    marker.bindPopup(buildMapPopupMarkup(location));

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

  map.on('zoomend', () => {
    scheduleStopOverlayUpdate(map);
  });

  map.on('moveend', () => {
    scheduleStopOverlayUpdate(map);
  });

  scheduleStopOverlayUpdate(map);

  return map;
}

// ============================================================================
// COLOURBLIND MODE / ACCESSIBILITY FUNCTIONS
// ============================================================================

function clampZoom(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return ACCESSIBILITY_DEFAULTS.zoomLevel;
  }
  return Math.min(1.4, Math.max(0.85, Math.round(numeric * 100) / 100));
}

function normalizeAccessibilitySettings(rawSettings = {}) {
  const zoomLevel = clampZoom(rawSettings.zoomLevel ?? rawSettings.accessibilityzoom ?? ACCESSIBILITY_DEFAULTS.zoomLevel);
  const modeCandidate = String(rawSettings.colorMode ?? rawSettings.accessibilitymode ?? 'none').toLowerCase();
  const colorMode = ACCESSIBILITY_MODES.has(modeCandidate)
    ? modeCandidate
    : ((rawSettings.colorblindmode || rawSettings.colorblindMode) ? 'deuteranopia' : 'none');

  const fontCandidate = String(rawSettings.fontSize ?? rawSettings.accessibilityfontsize ?? ACCESSIBILITY_DEFAULTS.fontSize).toLowerCase();
  const fontSize = ACCESSIBILITY_FONT_SIZES.has(fontCandidate) ? fontCandidate : ACCESSIBILITY_DEFAULTS.fontSize;

  return { zoomLevel, colorMode, fontSize };
}

function getCurrentAccessibilitySettings() {
  return {
    zoomLevel: accessibilityState.zoomLevel,
    colorMode: accessibilityState.colorMode,
    fontSize: accessibilityState.fontSize || ACCESSIBILITY_DEFAULTS.fontSize,
  };
}

function updateAccessibilityLinkState(isOpen = false) {
  const sidebarLink = document.getElementById('accessibility-link');
  if (!sidebarLink) {
    return;
  }

  const hasCustomPreference = accessibilityState.colorMode !== 'none' || Math.abs(accessibilityState.zoomLevel - 1) > 0.001;
  sidebarLink.textContent = hasCustomPreference ? t('navigation.accessibilityActive') : t('navigation.accessibility');
  sidebarLink.setAttribute('aria-expanded', String(isOpen));
}

function syncAccessibilityControls() {
  const zoomSlider = document.getElementById('accessibility-zoom');
  const zoomValue = document.getElementById('accessibility-zoom-value');
  const modeRadios = document.querySelectorAll('input[name="accessibility-colour"]');
  const fontRadios = document.querySelectorAll('input[name="accessibility-font-size"]');
  const languageSelect = document.getElementById('accessibility-language');

  if (zoomSlider) {
    zoomSlider.value = String(accessibilityState.zoomLevel);
  }

  if (zoomValue) {
    zoomValue.textContent = `${Math.round(accessibilityState.zoomLevel * 100)}%`;
  }

  if (modeRadios && modeRadios.length) {
    modeRadios.forEach(r => r.checked = (r.value === accessibilityState.colorMode));
  }

  if (fontRadios && fontRadios.length) {
    fontRadios.forEach(r => r.checked = (r.value === (accessibilityState.fontSize || ACCESSIBILITY_DEFAULTS.fontSize)));
  }

  if (languageSelect) {
    languageSelect.value = i18nState.locale;
  }
}

function applyAccessibilitySettings(settings, options = {}) {
  const { persistLocal = true, syncControls = true } = options;
  const normalized = normalizeAccessibilitySettings(settings);
  const previousColorMode = accessibilityState.colorMode;

  accessibilityState.zoomLevel = normalized.zoomLevel;
  accessibilityState.colorMode = normalized.colorMode;
  accessibilityState.fontSize = normalized.fontSize;

  // Keep existing colourblind theme class for backwards-compatible styling.
  document.body.classList.toggle('colorblind-mode', normalized.colorMode !== 'none');

  // Swap per-mode helper classes for filter variants.
  document.body.classList.remove(
    'accessibility-mode-none',
    'accessibility-mode-deuteranopia',
    'accessibility-mode-protanopia',
    'accessibility-mode-tritanopia',
    'accessibility-mode-achromatopsia'
  );
  document.body.classList.add(`accessibility-mode-${normalized.colorMode}`);

  // Scale UI text and components that use rem units and apply font-size presets.
  const fontMultipliers = { small: 0.9, normal: 1.0, large: 1.15 };
  const multiplier = fontMultipliers[normalized.fontSize] || 1.0;
  document.documentElement.style.fontSize = `${Math.round(normalized.zoomLevel * multiplier * 100)}%`;

  // Apply a helper class for font size so CSS can target components if needed.
  document.body.classList.remove('accessibility-font-small', 'accessibility-font-normal', 'accessibility-font-large');
  document.body.classList.add(`accessibility-font-${normalized.fontSize}`);

  if (persistLocal) {
    localStorage.setItem('accessibilitySettings', JSON.stringify(normalized));
    // Keep old key in sync for compatibility with older flows.
    localStorage.setItem('colorblindMode', JSON.stringify(normalized.colorMode !== 'none'));
  }

  if (syncControls) {
    syncAccessibilityControls();
  }

  updateAccessibilityLinkState(!document.getElementById('accessibility-panel')?.classList.contains('hidden'));

  if (
    normalized.colorMode !== previousColorMode &&
    normalized.colorMode !== 'none' &&
    window.appMap &&
    typeof window.appMap.setMapStyleById === 'function'
  ) {
    const defaultStyleId = ACCESSIBILITY_MODE_DEFAULT_MAP_STYLE[normalized.colorMode];
    if (defaultStyleId) {
      window.appMap.setMapStyleById(defaultStyleId);
    }
  }

  updateMapMarkerColors();
}

/**
 * Get marker colours based on current map style and accessibility mode.
 */
function getMarkerColors() {
  const defaultStylePalette = {
    'osm-standard': { fillColor: '#d32f2f', color: '#8b0000', fillOpacity: 0.58, opacity: 0.95, weight: 1.5 },
    'osm-hot': { fillColor: '#0D47A1', color: '#002171', fillOpacity: 0.68, opacity: 0.95, weight: 1.5 },
    'cyclosm': { fillColor: '#AD1457', color: '#880E4F', fillOpacity: 0.68, opacity: 0.95, weight: 1.5 },
    'opentopomap': { fillColor: '#D81B60', color: '#880E4F', fillOpacity: 0.72, opacity: 0.95, weight: 1.5 },
    'carto-voyager': { fillColor: '#D32F2F', color: '#8E0000', fillOpacity: 0.64, opacity: 0.95, weight: 1.5 },
    'carto-voyager-labels-under': { fillColor: '#C62828', color: '#7F0000', fillOpacity: 0.64, opacity: 0.95, weight: 1.5 },
    'carto-positron': { fillColor: '#C2185B', color: '#880E4F', fillOpacity: 0.7, opacity: 0.95, weight: 1.5 },
    'carto-darkmatter': { fillColor: '#FF6D00', color: '#FFAB40', fillOpacity: 0.8, opacity: 0.98, weight: 2 },
    'esri-street': { fillColor: '#AD1457', color: '#6A1B9A', fillOpacity: 0.68, opacity: 0.95, weight: 1.5 },
    'esri-topo': { fillColor: '#D81B60', color: '#880E4F', fillOpacity: 0.7, opacity: 0.95, weight: 1.5 },
    'esri-natgeo': { fillColor: '#C62828', color: '#8E0000', fillOpacity: 0.7, opacity: 0.95, weight: 1.5 },
  };

  // Accessibility-first palette: when a colour-vision mode is active, these
  // colours remain consistent across map styles to preserve recognisability.
  const accessibleModePalette = {
    deuteranopia: { fillColor: '#0057B7', color: '#003A78', fillOpacity: 0.78, opacity: 1, weight: 2.2 },
    protanopia: { fillColor: '#7B1FA2', color: '#4A148C', fillOpacity: 0.8, opacity: 1, weight: 2.2 },
    tritanopia: { fillColor: '#C62828', color: '#7F0000', fillOpacity: 0.8, opacity: 1, weight: 2.2 },
    achromatopsia: { fillColor: '#F2F2F2', color: '#111111', fillOpacity: 0.9, opacity: 1, weight: 2.4 },
  };

  const mode = ACCESSIBILITY_MODES.has(accessibilityState.colorMode)
    ? accessibilityState.colorMode
    : 'none';

  if (mode !== 'none' && accessibleModePalette[mode]) {
    return accessibleModePalette[mode];
  }

  return defaultStylePalette[activeMapStyleId] || defaultStylePalette['osm-standard'];
}

/**
 * Update all map marker colours to match the current theme + map style.
 */
function updateMapMarkerColors() {
  const colors = getMarkerColors();
  mapMarkers.forEach(({ marker }) => {
    marker.setStyle({
      fillColor: colors.fillColor,
      color: colors.color,
      fillOpacity: colors.fillOpacity,
      opacity: colors.opacity,
      weight: colors.weight,
    });
  });
}

function getMapStyleA11yLabel(style) {
  const styleLabel = style?.label || '';
  return t('mapStyle.selectAria', { style: styleLabel });
}

function updateMapStyleButtonUI(style) {
  if (!style) return;

  const compactLabel = style.shortLabel || style.label;
  const mapStyleLabel = t('mapStyle.label');
  const a11yLabel = getMapStyleA11yLabel(style);

  const mapStyleBtn = document.getElementById('map-style-btn');
  if (mapStyleBtn) {
    mapStyleBtn.textContent = `${mapStyleLabel}: ${compactLabel}`;
    mapStyleBtn.title = a11yLabel;
    mapStyleBtn.setAttribute('aria-label', a11yLabel);
  }

  const mapStyleSelect = document.getElementById('map-style-select');
  if (mapStyleSelect) {
    // If options not yet populated, try to populate from the map if available
    if (!mapStyleSelect.options || mapStyleSelect.options.length === 0) {
      if (window.appMap && typeof window.appMap.getAvailableMapStyles === 'function') {
        const presets = window.appMap.getAvailableMapStyles();
        mapStyleSelect.innerHTML = presets
          .map(p => `<option value="${p.id}" title="${getMapStyleA11yLabel(p)}">${p.shortLabel || p.label}</option>`)
          .join('');
      }
    }
    mapStyleSelect.value = style.id;
    mapStyleSelect.title = a11yLabel;
    mapStyleSelect.setAttribute('aria-label', a11yLabel);
  }

  // Toggle a body-level class so CSS can adapt UI elements (popups/info cards)
  try {
    const id = String(style.id || '');
    const isDark = /dark|night|black/i.test(id);
    document.body.classList.toggle('map-style-dark', Boolean(isDark));
  } catch (e) {
    // ignore in non-browser environments
  }
}

/**
 * Backwards-compatible wrapper used by older flows.
 * @param {boolean} enabled - Whether colourblind mode should be active
 */
function applyColorblindMode(enabled) {
  const settings = getCurrentAccessibilitySettings();
  applyAccessibilitySettings({
    ...settings,
    colorMode: enabled ? (settings.colorMode === 'none' ? 'deuteranopia' : settings.colorMode) : 'none',
  });
}

// ============================================================================
// LIVE WEATHER FUNCTIONALITY
// ============================================================================

// Weather locations: all map locations with coordinates for API calls
function getWeatherLocations() {
  return LOCATION_CATALOG.map(location => ({
    id: location.id,
    name: t(`locations.${location.id}.name`),
    lat: location.lat,
    lon: location.lng,
  }));
}

// Cache for weather data to avoid repeated API calls
let weatherCache = null;
let weatherCacheTimestamp = 0;
const WEATHER_CACHE_DURATION_MS = 60 * 1000; // 1 minute cache TTL
const WEATHER_REFRESH_INTERVAL_MS = 30 * 1000; // 30 second UI refresh cadence
const WEATHER_FETCH_RETRY_DELAY_MS = 250;
const WEATHER_FETCH_MAX_ATTEMPTS = 2;

// Auto-refresh interval ID (runs while panel is open)
let weatherRefreshInterval = null;

// Debounce timer for weather search
let weatherSearchTimer = null;
let weatherRenderInFlight = false;
let queuedWeatherRenderOptions = null;
const weatherExpandedRowState = new Map();

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWeatherForLocation(loc) {
  for (let attempt = 1; attempt <= WEATHER_FETCH_MAX_ATTEMPTS; attempt += 1) {
    try {
      const res = await fetch(`/api/weather?lat=${loc.lat}&lon=${loc.lon}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { key: loc.id, name: loc.name, weather: normalizeWeatherPayload(data) };
    } catch (err) {
      if (attempt === WEATHER_FETCH_MAX_ATTEMPTS) {
        console.warn(`Weather fetch failed for ${loc.name}:`, err);
        return { key: loc.id, name: loc.name, weather: null };
      }
      await delay(WEATHER_FETCH_RETRY_DELAY_MS);
    }
  }
}

function normalizeWeatherPayload(payload) {
  if (!payload || payload.error) return payload;
  if (payload.temperature?.current != null || payload.temperature?.feels_like != null) {
    return payload;
  }

  const source = payload.weather && typeof payload.weather === 'object' ? payload.weather : payload;
  const main = source.main || {};
  const wind = source.wind || {};
  const clouds = source.clouds || {};
  const coord = source.coord || {};
  const firstCondition = Array.isArray(source.weather) ? source.weather[0] || {} : {};
  const iconCode = firstCondition.icon;

  return {
    location: {
      latitude: coord.lat ?? null,
      longitude: coord.lon ?? null,
    },
    temperature: {
      current: main.temp ?? null,
      feels_like: main.feels_like ?? null,
      unit: 'Celsius',
    },
    atmospheric_conditions: {
      humidity: main.humidity ?? null,
      humidity_unit: '%',
      pressure: main.pressure ?? null,
      pressure_unit: 'hPa',
    },
    wind: {
      speed: wind.speed ?? null,
      speed_unit: 'm/s',
      direction_degrees: wind.deg ?? null,
    },
    visibility: {
      distance: source.visibility ?? null,
      distance_unit: 'meters',
    },
    cloud_coverage: {
      percentage: clouds.all ?? null,
    },
    conditions: {
      code: firstCondition.main ?? null,
      description: firstCondition.description ?? null,
    },
    icon: {
      code: iconCode ?? null,
      icon_url: iconCode ? `/api/weather/icon/${iconCode}` : null,
    },
    timestamp: source.dt ?? null,
  };
}

/**
 * Fetch weather data for all default locations from the backend API.
 * Uses the /api/weather endpoint for each location.
 * Results are cached for 1 minute to reduce API load.
 * @returns {Promise<Array>} Array of { name, weather } objects
 */
async function fetchWeatherForAllLocations(options = {}) {
  const { forceRefresh = false } = options;
  const now = Date.now();
  if (!forceRefresh && weatherCache && (now - weatherCacheTimestamp) < WEATHER_CACHE_DURATION_MS) {
    return weatherCache;
  }

  const results = await Promise.allSettled(getWeatherLocations().map(fetchWeatherForLocation));
  const weatherData = results.map((result, index) => (
    result.status === 'fulfilled'
      ? result.value
      : { key: `fallback-${index}`, name: 'Unknown location', weather: null }
  ));

  weatherCache = weatherData;
  weatherCacheTimestamp = now;
  return weatherData;
}

function generateWeatherItemKey(entry) {
  const keyPart = entry?.key ? `id-${entry.key}` : `name-${entry?.name || 'unknown'}`;
  return keyPart.toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
}

function weatherRenderSignature(name, weather) {
  return JSON.stringify({
    locale: i18nState.locale,
    name,
    error: !!weather?.error,
    temp: weather?.temperature?.current ?? null,
    feelsLike: weather?.temperature?.feels_like ?? null,
    humidity: weather?.atmospheric_conditions?.humidity ?? null,
    windSpeed: weather?.wind?.speed ?? null,
    windUnit: weather?.wind?.speed_unit ?? null,
    cloudCoverage: weather?.cloud_coverage?.percentage ?? null,
    visibility: weather?.visibility?.distance ?? null,
    description: weather?.conditions?.description ?? null,
    icon: weather?.icon?.code ?? null,
  });
}

function isWeatherItemInitiallyOpen(itemKey, existingItem) {
  if (weatherExpandedRowState.has(itemKey)) {
    return !!weatherExpandedRowState.get(itemKey);
  }
  return !!existingItem?.classList.contains('weather-item-open');
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
    return (data.results || []).map(r => ({ name: r.name, weather: normalizeWeatherPayload(r.weather) }));
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
function buildWeatherListItem(name, weather, options = {}) {
  const { itemKey = generateWeatherItemKey({ name }), signature = weatherRenderSignature(name, weather), initiallyOpen = false } = options;
  const li = document.createElement('li');
  li.className = 'weather-item';
  li.dataset.weatherKey = itemKey;
  li.dataset.weatherSignature = signature;
  li.dataset.weatherName = name;
  const detailId = `weather-detail-${itemKey}`;

  // --- Top row (always visible): name + icon + temp ---
  const row = document.createElement('div');
  row.className = 'weather-row';
  row.setAttribute('role', 'button');
  row.setAttribute('tabindex', '0');
  row.setAttribute('aria-expanded', 'false');
  row.setAttribute('aria-controls', detailId);

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
      iconImg.alt = weather.conditions?.description || t('weather.iconAlt');
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
  detail.id = detailId;

  if (description) {
    // Capitalise first letter of description
    const desc = description.charAt(0).toUpperCase() + description.slice(1);
    let detailHTML = `<span class="weather-detail-desc">${desc}</span>`;
    const extras = [];
    if (feelsLike != null) extras.push(t('weather.feelsLike', { value: formatLocalizedNumber(Math.round(feelsLike)) }));
    if (humidity != null) extras.push(t('weather.humidity', { value: formatLocalizedNumber(humidity) }));
    if (windSpeed != null) extras.push(t('weather.wind', { value: formatLocalizedNumber(windSpeed), unit: windUnit }));
    if (cloudCoverage != null) extras.push(t('weather.cloudCover', { value: formatLocalizedNumber(cloudCoverage) }));
    if (visibility != null) extras.push(t('weather.visibility', { value: formatLocalizedNumber(visibility / 1000, { maximumFractionDigits: 1 }) }));
    if (extras.length) {
      detailHTML += `<span class="weather-detail-extras">${extras.join(' \u00b7 ')}</span>`;
    }
    detail.innerHTML = detailHTML;
  } else {
    detail.innerHTML = `<span class="weather-detail-desc">${t('weather.noDetail')}</span>`;
  }

  li.appendChild(row);
  li.appendChild(detail);

  const weatherLabel = rightSide.querySelector('.weather-temp')?.textContent || t('weather.temperatureUnavailable');
  row.setAttribute('aria-label', t('weather.rowAria', { location: name, temperature: weatherLabel }));

  // Toggle expand/collapse on click
  row.addEventListener('click', () => {
    const isOpen = li.classList.toggle('weather-item-open');
    row.setAttribute('aria-expanded', String(isOpen));
    weatherExpandedRowState.set(itemKey, isOpen);
  });
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      row.click();
    }
  });

  if (initiallyOpen) {
    li.classList.add('weather-item-open');
    row.setAttribute('aria-expanded', 'true');
    weatherExpandedRowState.set(itemKey, true);
  }

  return li;
}

function reconcileWeatherPanelList(weatherList, weatherData) {
  Array.from(weatherList.querySelectorAll('.weather-loading')).forEach(node => node.remove());

  const existingByKey = new Map(
    Array.from(weatherList.querySelectorAll('.weather-item')).map(item => [item.dataset.weatherKey, item])
  );
  const nextNodes = [];
  const nextKeys = new Set();

  weatherData.forEach((entry, index) => {
    const name = entry?.name || 'Unknown location';
    const weather = entry?.weather ?? null;
    const keyedEntry = entry?.key ? entry : { ...entry, key: `row-${index}-${name}` };
    const itemKey = generateWeatherItemKey(keyedEntry);
    if (nextKeys.has(itemKey)) return;
    nextKeys.add(itemKey);
    const signature = weatherRenderSignature(name, weather);
    const existing = existingByKey.get(itemKey);
    const initiallyOpen = isWeatherItemInitiallyOpen(itemKey, existing);

    if (existing && existing.dataset.weatherSignature === signature) {
      nextNodes.push(existing);
    } else {
      nextNodes.push(buildWeatherListItem(name, weather, { itemKey, signature, initiallyOpen }));
    }

    weatherExpandedRowState.set(itemKey, initiallyOpen);
    existingByKey.delete(itemKey);
  });

  existingByKey.forEach((_node, key) => weatherExpandedRowState.delete(key));

  let cursor = weatherList.firstElementChild;
  nextNodes.forEach(node => {
    if (node === cursor) {
      cursor = cursor?.nextElementSibling || null;
      return;
    }
    weatherList.insertBefore(node, cursor);
  });

  while (cursor) {
    const next = cursor.nextElementSibling;
    cursor.remove();
    cursor = next;
  }
}

/**
 * Render the weather list inside the weather panel with real API data.
 * Each item displays: location name, weather icon, temperature,
 * and an expandable detail section with a brief description.
 */
async function renderWeatherPanel(options = {}) {
  const { forceRefresh = false, announce = true } = options;
  const weatherList = document.getElementById('weather-list');
  if (!weatherList) return;

  const hasExistingRows = weatherList.querySelector('.weather-item');
  if (!hasExistingRows && !weatherList.querySelector('.weather-loading')) {
    weatherList.innerHTML = `<li class="weather-loading">${t('weather.loading')}</li>`;
  }

  if (weatherRenderInFlight) {
    queuedWeatherRenderOptions = {
      forceRefresh: !!(options.forceRefresh || queuedWeatherRenderOptions?.forceRefresh),
      announce: !!(options.announce || queuedWeatherRenderOptions?.announce),
    };
    return;
  }
  weatherRenderInFlight = true;
  weatherList.setAttribute('aria-busy', 'true');

  try {
    const weatherData = await fetchWeatherForAllLocations({ forceRefresh });
    reconcileWeatherPanelList(weatherList, weatherData);
    if (announce) {
      announceToScreenReader(t('announce.weatherUpdated', { count: weatherData.length }));
    }
  } catch (err) {
    console.error('Failed to load weather data:', err);
    if (!weatherList.querySelector('.weather-item')) {
      weatherList.innerHTML = `<li class="weather-loading">${t('weather.unableToLoad')}</li>`;
    }
    announceToScreenReader(t('announce.weatherLoadFailed'), 'assertive');
  } finally {
    weatherRenderInFlight = false;
    weatherList.setAttribute('aria-busy', 'false');
    if (queuedWeatherRenderOptions) {
      const nextOptions = queuedWeatherRenderOptions;
      queuedWeatherRenderOptions = null;
      renderWeatherPanel(nextOptions);
    }
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
    weatherList.innerHTML = `<li class="weather-loading">${t('weather.noLocations')}</li>`;
    announceToScreenReader(t('announce.weatherNoLocations'));
    return;
  }
  results.forEach(({ name, weather }) => {
    weatherList.appendChild(buildWeatherListItem(name, weather));
  });
  announceToScreenReader(t('announce.weatherShowingResults', { count: results.length }));
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
        loadingLi.textContent = t('weather.searchingMore');
        weatherList.appendChild(loadingLi);
      }

      const apiResults = await searchWeatherLocations(query);

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
  const accessibilityPanel = document.getElementById('accessibility-panel');
  const faqPanel = document.getElementById('faq-panel');
  const supportPanel = document.getElementById('support-panel');
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
    supportPanel?.classList.add('hidden');
    accessibilityPanel?.classList.add('hidden');
    accessibilityPanel?.setAttribute('aria-hidden', 'true');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
    updateAccessibilityLinkState(false);
    // Clear search input when opening the panel
    const searchInput = document.getElementById('weather-search-input');
    if (searchInput) searchInput.value = '';
    // Fetch and render live weather data when panel is opened
    renderWeatherPanel({ forceRefresh: true });
    // Start background auto-refresh while panel is open
    clearInterval(weatherRefreshInterval);
    weatherRefreshInterval = setInterval(() => {
      // Only re-render if search bar is empty (don't overwrite active search)
      const si = document.getElementById('weather-search-input');
      if (!si || si.value.trim() === '') {
        renderWeatherPanel({ forceRefresh: true, announce: false });
      }
    }, WEATHER_REFRESH_INTERVAL_MS);
    announceToScreenReader(t('announce.weatherPanelOpened'));
  } else {
    // Panel is closing — stop auto-refresh
    clearInterval(weatherRefreshInterval);
    weatherRefreshInterval = null;
    announceToScreenReader(t('announce.weatherPanelClosed'));
  }
}

// Toggle notifications panel visibility
function toggleNotificationsPanel() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const accessibilityPanel = document.getElementById('accessibility-panel');
  const faqPanel = document.getElementById('faq-panel');
  const supportPanel = document.getElementById('support-panel');
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
    supportPanel?.classList.add('hidden');
    accessibilityPanel?.classList.add('hidden');
    accessibilityPanel?.setAttribute('aria-hidden', 'true');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
    updateAccessibilityLinkState(false);
    announceToScreenReader(t('announce.notificationsPanelOpened'), 'assertive');
  } else {
    announceToScreenReader(t('announce.notificationsPanelClosed'));
  }
}

function openFaqPanel() {
  const faqPanel = document.getElementById('faq-panel');
  const supportPanel = document.getElementById('support-panel');
  const accessibilityPanel = document.getElementById('accessibility-panel');
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');
  
  if (faqPanel) {
    faqPanel.classList.remove('hidden');
    faqPanel.setAttribute('aria-hidden', 'false');
    
    // Close other panels when FAQ is opened
    supportPanel?.classList.add('hidden');
    supportPanel?.setAttribute('aria-hidden', 'true');
    accessibilityPanel?.classList.add('hidden');
    accessibilityPanel?.setAttribute('aria-hidden', 'true');
    weatherPanel?.classList.add('hidden');
    notifPanel?.classList.add('hidden');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
    updateAccessibilityLinkState(false);
    announceToScreenReader(t('announce.faqOpened'));
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
    announceToScreenReader(t('announce.faqClosed'));
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

function openSupportPanel() {
  const supportPanel = document.getElementById('support-panel');
  const faqPanel = document.getElementById('faq-panel');
  const accessibilityPanel = document.getElementById('accessibility-panel');
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');

  if (supportPanel) {
    resetFloatingPanelToDefault('support-panel');
    supportPanel.classList.remove('hidden');
    supportPanel.setAttribute('aria-hidden', 'false');

    // Close other panels when support is opened
    faqPanel?.classList.add('hidden');
    faqPanel?.setAttribute('aria-hidden', 'true');
    accessibilityPanel?.classList.add('hidden');
    accessibilityPanel?.setAttribute('aria-hidden', 'true');
    weatherPanel?.classList.add('hidden');
    notifPanel?.classList.add('hidden');
    authModal?.classList.add('hidden');
    accountModal?.classList.add('hidden');
    updateAccessibilityLinkState(false);
    announceToScreenReader(t('announce.supportOpened'));
  }
}

function closeSupportPanel() {
  const supportPanel = document.getElementById('support-panel');
  if (supportPanel) {
    supportPanel.classList.add('hidden');
    supportPanel.setAttribute('aria-hidden', 'true');
    resetFloatingPanelToDefault('support-panel');
    announceToScreenReader(t('announce.supportClosed'));
  }
}

function attachSupportEventHandlers() {
  const supportLink = document.querySelector('.sidebar-links a[href="#support"]');
  supportLink?.addEventListener('click', event => {
    event.preventDefault();
    openSupportPanel();
  });

  document.getElementById('support-close')?.addEventListener('click', closeSupportPanel);
}

function openAccessibilityPanel() {
  const panel = document.getElementById('accessibility-panel');
  const faqPanel = document.getElementById('faq-panel');
  const supportPanel = document.getElementById('support-panel');
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const authModal = document.getElementById('auth-modal');
  const accountModal = document.getElementById('account-modal');

  if (!panel) {
    return;
  }

  resetFloatingPanelToDefault('accessibility-panel');
  panel.classList.remove('hidden');
  panel.setAttribute('aria-hidden', 'false');
  faqPanel?.classList.add('hidden');
  supportPanel?.classList.add('hidden');
  weatherPanel?.classList.add('hidden');
  notifPanel?.classList.add('hidden');
  authModal?.classList.add('hidden');
  accountModal?.classList.add('hidden');

  syncAccessibilityControls();
  updateAccessibilityLinkState(true);
  announceToScreenReader(t('announce.accessibilityOpened'));
}

function closeAccessibilityPanel() {
  const panel = document.getElementById('accessibility-panel');
  if (!panel) {
    return;
  }

  panel.classList.add('hidden');
  panel.setAttribute('aria-hidden', 'true');
  resetFloatingPanelToDefault('accessibility-panel');
  updateAccessibilityLinkState(false);
  announceToScreenReader(t('announce.accessibilityClosed'));
}

function toggleAccessibilityPanel() {
  const panel = document.getElementById('accessibility-panel');
  if (!panel) {
    return;
  }

  if (panel.classList.contains('hidden')) {
    openAccessibilityPanel();
    return;
  }

  closeAccessibilityPanel();
}

async function saveAccessibilityToAccount() {
  if (!authState.token) {
    alert(t('alerts.loginToSaveAccessibility'));
    openAuthModal();
    return;
  }

  try {
    const payload = {
      colorblindmode: accessibilityState.colorMode !== 'none',
      accessibilitymode: accessibilityState.colorMode,
      accessibilityzoom: accessibilityState.zoomLevel,
      accessibilityfontsize: accessibilityState.fontSize || ACCESSIBILITY_DEFAULTS.fontSize,
    };

    const response = await apiRequest('/api/account/profile', {
      method: 'PATCH',
      body: payload,
    });

    authState.user = response.user;
    alert(t('alerts.accessibilitySaved'));
  } catch (err) {
    console.warn('Failed to save accessibility preferences:', err.message);
    alert(t('alerts.couldNotSavePreferences'));
  }
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
  const accessibilityPanel = document.getElementById('accessibility-panel');
  const faqPanel = document.getElementById('faq-panel');
  const supportPanel = document.getElementById('support-panel');
  
  resetFloatingPanelToDefault('auth-modal');
  document.getElementById('auth-modal')?.classList.remove('hidden');
  document.getElementById('account-modal')?.classList.add('hidden');
  showLoginAuthView();
  
  // Close other panels when auth modal is opened
  weatherPanel?.classList.add('hidden');
  notifPanel?.classList.add('hidden');
  accessibilityPanel?.classList.add('hidden');
  accessibilityPanel?.setAttribute('aria-hidden', 'true');
  faqPanel?.classList.add('hidden');
  supportPanel?.classList.add('hidden');
  updateAccessibilityLinkState(false);
  announceToScreenReader(t('announce.authOpened'));
}

function closeAuthModal() {
  document.getElementById('auth-modal')?.classList.add('hidden');
  resetFloatingPanelToDefault('auth-modal');
  showLoginAuthView();
  announceToScreenReader(t('announce.authClosed'));
}

function showLoginAuthView() {
  const authTitle = document.getElementById('auth-modal-title');
  if (authTitle) {
    authTitle.textContent = t('auth.loginTitle');
  }
  document.getElementById('auth-login-view')?.classList.remove('hidden');
  document.getElementById('auth-register-view')?.classList.add('hidden');
}

function showRegisterAuthView() {
  const authTitle = document.getElementById('auth-modal-title');
  if (authTitle) {
    authTitle.textContent = t('auth.registerTitle');
  }
  document.getElementById('auth-login-view')?.classList.add('hidden');
  document.getElementById('auth-register-view')?.classList.remove('hidden');
}

function openAccountModal() {
  const weatherPanel = document.querySelector('.weather-panel');
  const notifPanel = document.querySelector('.notif-panel');
  const accessibilityPanel = document.getElementById('accessibility-panel');
  const faqPanel = document.getElementById('faq-panel');
  const supportPanel = document.getElementById('support-panel');
  
  document.getElementById('account-modal')?.classList.remove('hidden');
  document.getElementById('auth-modal')?.classList.add('hidden');
  
  // Close other panels when account modal is opened
  weatherPanel?.classList.add('hidden');
  notifPanel?.classList.add('hidden');
  accessibilityPanel?.classList.add('hidden');
  accessibilityPanel?.setAttribute('aria-hidden', 'true');
  faqPanel?.classList.add('hidden');
  supportPanel?.classList.add('hidden');
  updateAccessibilityLinkState(false);
  announceToScreenReader(t('announce.accountOpened'));
}

function closeAccountModal() {
  document.getElementById('account-modal')?.classList.add('hidden');
  announceToScreenReader(t('announce.accountClosed'));
}

async function refreshAccountView() {
  if (!authState.token) {
    authState.user = null;
    return;
  }

  try {
    const meResponse = await apiRequest('/api/account/me');
    authState.user = meResponse.user;

    applyAccessibilitySettings({
      zoomLevel: authState.user.accessibilityzoom,
      colorMode: authState.user.accessibilitymode,
      accessibilityfontsize: authState.user.accessibilityfontsize,
      colorblindmode: authState.user.colorblindmode,
    });

    const usernameTarget = document.getElementById('account-username-value');
    if (usernameTarget) {
      usernameTarget.textContent = authState.user.userName;
    }

    const adminPanel = document.getElementById('admin-notification-panel');
    const adminForm = document.getElementById('admin-notification-form');
    const adminStatus = document.getElementById('admin-notification-status');
    if (adminPanel) {
      const isAdmin = Boolean(authState.user?.isAdmin);
      adminPanel.classList.toggle('hidden', !isAdmin);
      if (!isAdmin) {
        adminForm?.reset();
        if (adminStatus) {
          adminStatus.textContent = '';
        }
      }
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
    emptyItem.className = 'saved-route-item empty';
    emptyItem.textContent = t('account.noSavedRoutes');
    list.appendChild(emptyItem);
    updateSavedRoutesScrollButton();
    return;
  }

  savedRoutes.forEach((route, index) => {
    const item = document.createElement('li');
    item.className = 'saved-route-item clickable';
    item.setAttribute('role', 'button');
    item.setAttribute('tabindex', '0');
    item.title = t('account.searchRoutesTitle', { from: route.routeStart, to: route.routeEnd });
    item.setAttribute('aria-label', t('account.savedRouteAria', { from: route.routeStart, to: route.routeEnd }));

    const icon = document.createElement('span');
    icon.className = 'saved-route-icon';
    icon.setAttribute('aria-hidden', 'true');
    const name = (route.routeName || '').toLowerCase();
    const hasTrain = name.includes('train') || name.includes('rail');
    const hasBus   = name.includes('bus');
    // Mixed (bus + train) → train takes precedence; unknown → train as default
    icon.textContent = (hasBus && !hasTrain) ? '🚌' : '🚆';

    const label = document.createElement('span');
    label.className = 'saved-route-label';
    label.textContent = t('account.routeFromTo', { from: route.routeStart, to: route.routeEnd });

    const chevron = document.createElement('span');
    chevron.className = 'saved-route-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '›';

    item.appendChild(icon);
    item.appendChild(label);
    item.appendChild(chevron);

    const activate = () => viewSavedRoute(route);
    item.addEventListener('click', activate);
    item.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); } });

    list.appendChild(item);
  });

  updateSavedRoutesScrollButton();
}

async function viewSavedRoute(savedRoute) {
  // Close account modal first
  closeAccountModal();

  // Fill the search inputs with the saved route names
  const fromInput = document.getElementById('from-input');
  const toInput = document.getElementById('to-input');
  if (fromInput) fromInput.value = savedRoute.routeStart;
  if (toInput) toInput.value = savedRoute.routeEnd;

  const resolveSavedRouteStop = async (name) => {
    if (!name || typeof name !== 'string') {
      return { name: name || '' };
    }
    try {
      const response = await fetch(`/api/stops/search?q=${encodeURIComponent(name)}&limit=1`);
      if (!response.ok) {
        return { name };
      }
      const data = await response.json();
      if (Array.isArray(data?.stops) && data.stops.length > 0) {
        return data.stops[0];
      }
      return { name };
    } catch (_error) {
      return { name };
    }
  };

  const [fromResolved, toResolved] = await Promise.all([
    resolveSavedRouteStop(savedRoute.routeStart),
    resolveSavedRouteStop(savedRoute.routeEnd),
  ]);
  selectedStops.from = fromResolved;
  selectedStops.to = toResolved;
  syncSelectedStopMapMarkers({ focus: true });
  setFieldError('from-input', 'from-input-error', '');
  setFieldError('to-input', 'to-input-error', '');

  try {
    const [resolvedFrom, resolvedTo] = await Promise.all([
      resolveSavedRouteStop(savedRoute.routeStart),
      resolveSavedRouteStop(savedRoute.routeEnd),
    ]);

    if (!resolvedFrom || !resolvedTo) {
      alert(t('alerts.couldNotLoadSavedJourneyRoutes'));
      announceToScreenReader(t('alerts.couldNotLoadSavedJourneyRoutes'), 'assertive');
      return;
    }

    selectedStops.from = resolvedFrom;
    selectedStops.to = resolvedTo;
    syncSelectedStopMapMarkers({ focus: true });

    // Use the standard route search flow so all journeys for this origin/destination
    // are fetched and rendered consistently with normal autocomplete searches.
    await searchRoutes();
  } catch (error) {
    console.error('Error loading saved route:', error);
    if (error && error.name === 'AbortError') {
      alert('Route search timed out. Please try again.');
    } else {
      alert(t('alerts.couldNotLoadRoutesTryAgain'));
    }
  }
}

function normalizeStopNameForMatching(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/\([^)]*\)/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function pickBestSavedRouteStop(stopName, stops) {
  if (!Array.isArray(stops) || stops.length === 0) {
    return null;
  }

  const target = normalizeStopNameForMatching(stopName);
  const withCodes = stops.filter(stop => stop && stop.atcoCode);
  const candidates = withCodes.length ? withCodes : stops;

  const exact = candidates.find(stop => normalizeStopNameForMatching(stop.name) === target);
  if (exact) return exact;

  const startsWith = candidates.find(stop => normalizeStopNameForMatching(stop.name).startsWith(target));
  if (startsWith) return startsWith;

  const includes = candidates.find(stop => normalizeStopNameForMatching(stop.name).includes(target));
  if (includes) return includes;

  return candidates[0] || null;
}

function buildSavedRouteStopQueries(stopName) {
  const raw = String(stopName || '').trim();
  if (!raw) {
    return [];
  }

  const withoutBracketed = raw.replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  const beforeComma = raw.split(',')[0]?.trim() || '';
  const beforeCommaNoBrackets = beforeComma.replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  const localityOnly = raw.split(',').slice(-1)[0]?.trim() || '';

  const queries = [
    raw,
    withoutBracketed,
    beforeComma,
    beforeCommaNoBrackets,
    localityOnly,
  ].filter(Boolean);

  const words = normalizeStopNameForMatching(beforeCommaNoBrackets || raw)
    .split(' ')
    .filter(Boolean);
  if (words.length >= 2) {
    queries.push(words.slice(0, 2).join(' '));
  }
  if (words.length >= 1) {
    queries.push(words[0]);
  }

  // Preserve order and remove duplicates / too-short queries.
  return Array.from(new Set(queries.map(q => q.trim()))).filter(q => q.length >= 2);
}

async function resolveSavedRouteStop(stopName) {
  const queries = buildSavedRouteStopQueries(stopName);
  if (!queries.length) {
    return null;
  }

  for (const query of queries) {
    const response = await fetch(`/api/stops/search?q=${encodeURIComponent(query)}&limit=10`);
    if (!response.ok) {
      continue;
    }

    const data = await response.json();
    const best = pickBestSavedRouteStop(stopName, data?.stops || []);
    if (best) {
      return best;
    }
  }

  return null;
}

function updateSavedRoutesScrollButton() {
  const list = document.getElementById('saved-routes-list');
  const scrollBtn = document.querySelector('.saved-routes-more');
  if (!list || !scrollBtn) {
    return;
  }

  const needsScroll = list.scrollHeight > list.clientHeight + 2;
  scrollBtn.classList.toggle('hidden', !needsScroll);
}

function scrollSavedRoutes() {
  const list = document.getElementById('saved-routes-list');
  if (!list) {
    return;
  }

  const scrollStep = Math.max(80, Math.floor(list.clientHeight * 0.72));
  const nearBottom = list.scrollTop + list.clientHeight >= list.scrollHeight - 4;

  if (nearBottom) {
    list.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  list.scrollBy({ top: scrollStep, behavior: 'smooth' });
}

function localizeNotificationMessage(notification) {
  const message = String(notification?.message || '').trim();
  if (!message) {
    return '';
  }

  if (/^Welcome to Transport for North West\. Your account is now active\.?$/i.test(message)) {
    return t('notifications.messages.welcome');
  }

  const routeSavedMatch = message.match(/^Route saved:\s*(.+?)\s*(?:→|->)\s*(.+)$/i);
  if (routeSavedMatch) {
    return t('notifications.messages.routeSaved', {
      from: routeSavedMatch[1].trim(),
      to: routeSavedMatch[2].trim(),
    });
  }

  return message;
}

function renderNotifications(notifications, options = {}) {
  const { announce = true } = options;
  const notifList = document.querySelector('.notif-list');
  if (!notifList) {
    return;
  }

  latestNotifications = Array.isArray(notifications) ? notifications : [];

  notifList.innerHTML = '';
  if (!latestNotifications.length) {
    const emptyNode = document.createElement('div');
    emptyNode.className = 'notif-item';
    emptyNode.textContent = t('notifications.none');
    notifList.appendChild(emptyNode);
    if (announce) {
      announceToScreenReader(t('announce.noNotifications'));
    }
    return;
  }

  latestNotifications.slice(0, 5).forEach(item => {
    const row = document.createElement('div');
    row.className = 'notif-item';
    row.textContent = localizeNotificationMessage(item);
    notifList.appendChild(row);
  });

  if (announce) {
    announceToScreenReader(t('announce.notificationsLoaded', { count: Math.min(latestNotifications.length, 5) }), 'assertive');
  }
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
    alert(localizeApiErrorMessage(error.message, 'alerts.loginFailed'));
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
    alert(localizeApiErrorMessage(error.message, 'alerts.registrationFailed'));
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

  const currentPassword = window.prompt(t('account.promptCurrentPassword'));
  if (!currentPassword) {
    return;
  }
  const newPassword = window.prompt(t('account.promptNewPassword'));
  if (!newPassword) {
    return;
  }

  try {
    await apiRequest('/api/account/password', {
      method: 'PATCH',
      body: { currentPassword, newPassword },
    });
    alert(t('alerts.passwordUpdated'));
  } catch (error) {
    alert(localizeApiErrorMessage(error.message, 'alerts.passwordUpdateFailed'));
  }
}

async function handleDeleteAccount() {
  if (!authState.user) {
    return;
  }

  const confirmation = window.confirm(t('account.confirmDelete'));
  if (!confirmation) {
    return;
  }

  const password = window.prompt(t('account.promptConfirmDeletePassword'));
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
    alert(t('alerts.accountDeleted'));
  } catch (error) {
    alert(localizeApiErrorMessage(error.message, 'alerts.accountDeletionFailed'));
  }
}

async function handleAdminNotificationSubmit(event) {
  event.preventDefault();

  if (!authState.user?.isAdmin) {
    return;
  }

  const messageInput = document.getElementById('admin-notification-message');
  const statusNode = document.getElementById('admin-notification-status');
  const message = String(messageInput?.value || '').trim();

  if (!message) {
    if (statusNode) {
      statusNode.textContent = t('account.admin.emptyMessage');
    }
    return;
  }

  try {
    const response = await apiRequest('/api/admin/notifications', {
      method: 'POST',
      body: { message },
    });

    if (statusNode) {
      statusNode.textContent = t('account.admin.sentStatus', {
        count: formatLocalizedNumber(response.count || 0),
      });
    }
    if (messageInput) {
      messageInput.value = '';
    }
  } catch (error) {
    if (statusNode) {
      statusNode.textContent = localizeApiErrorMessage(error.message);
    }
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
  document.getElementById('show-register-view-btn')?.addEventListener('click', showRegisterAuthView);
  document.getElementById('show-login-view-btn')?.addEventListener('click', showLoginAuthView);
  document.getElementById('logout-btn')?.addEventListener('click', handleLogout);
  document.getElementById('update-password-btn')?.addEventListener('click', handleUpdatePassword);
  document.getElementById('delete-account-btn')?.addEventListener('click', handleDeleteAccount);
  document.getElementById('admin-notification-form')?.addEventListener('submit', handleAdminNotificationSubmit);
  document.querySelector('.saved-routes-more')?.addEventListener('click', scrollSavedRoutes);

  document.getElementById('accessibility-link')?.addEventListener('click', e => {
    e.preventDefault();
    toggleAccessibilityPanel();
  });
  document.getElementById('accessibility-close')?.addEventListener('click', closeAccessibilityPanel);

  document.getElementById('accessibility-zoom')?.addEventListener('input', e => {
    const current = getCurrentAccessibilitySettings();
    applyAccessibilitySettings({
      ...current,
      zoomLevel: e.target.value,
    });
  });

  document.getElementById('zoom-out-btn')?.addEventListener('click', () => {
    const next = clampZoom(accessibilityState.zoomLevel - 0.05);
    applyAccessibilitySettings({ ...getCurrentAccessibilitySettings(), zoomLevel: next });
  });

  document.getElementById('zoom-in-btn')?.addEventListener('click', () => {
    const next = clampZoom(accessibilityState.zoomLevel + 0.05);
    applyAccessibilitySettings({ ...getCurrentAccessibilitySettings(), zoomLevel: next });
  });

  // Radio inputs for colour profiles
  document.querySelectorAll('input[name="accessibility-colour"]').forEach(r => {
    r.addEventListener('change', e => {
      if (!e.target.checked) return;
      applyAccessibilitySettings({
        ...getCurrentAccessibilitySettings(),
        colorMode: e.target.value,
      });
    });
  });

  // Radio inputs for font size
  document.querySelectorAll('input[name="accessibility-font-size"]').forEach(r => {
    r.addEventListener('change', e => {
      if (!e.target.checked) return;
      applyAccessibilitySettings({
        ...getCurrentAccessibilitySettings(),
        fontSize: e.target.value,
      });
    });
  });

  document.getElementById('accessibility-reset-btn')?.addEventListener('click', () => {
    applyAccessibilitySettings(ACCESSIBILITY_DEFAULTS);
  });

  document.getElementById('accessibility-save-btn')?.addEventListener('click', saveAccessibilityToAccount);

  document.getElementById('accessibility-language')?.addEventListener('change', async e => {
    const nextLocale = e.target?.value;
    if (!nextLocale) {
      return;
    }
    await setLocale(nextLocale, { persist: true, announce: true });
  });

  window.addEventListener('resize', updateSavedRoutesScrollButton);
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

  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false');
  if (suggestionsContainer.id) {
    input.setAttribute('aria-controls', suggestionsContainer.id);
  }

  // Input event handler with debouncing
  input.addEventListener('input', function() {
    const query = this.value.trim();
    selectedIndex = -1;
    
    // Clear selected stop when user modifies input
    selectedStops[inputType] = null;
    syncSelectedStopMapMarkers();
    setFieldError(
      inputType === 'from' ? 'from-input' : 'to-input',
      inputType === 'from' ? 'from-input-error' : 'to-input-error',
      ''
    );
    syncRouteModalWithInputState();

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
    const suggestions = suggestionsContainer.querySelectorAll('.autocomplete-group-header, .autocomplete-suggestion-item');
    
    if (suggestions.length === 0) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
      updateSelectedSuggestion(suggestions, selectedIndex, input);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      updateSelectedSuggestion(suggestions, selectedIndex, input);
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
  // Group stops by a normalized name so visually identical/very-similar
  // stop names are merged in the autocomplete list.
  suggestionsContainer.innerHTML = '';

  const groups = new Map();
  stops.forEach(stop => {
    const key = normalizeStopNameForMatching(stop.name) || stop.name;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(stop);
  });

  let groupIndex = 0;
  groups.forEach((groupStops, key) => {
    if (!Array.isArray(groupStops) || groupStops.length === 0) return;

    if (groupStops.length === 1) {
      const stop = groupStops[0];
      const item = document.createElement('div');
      item.className = 'autocomplete-suggestion-item';
      item.id = `${inputType}-suggestion-${groupIndex}`;
      item.textContent = stop.name;
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', 'false');
      item.dataset.atcoCode = stop.atcoCode;
      item.dataset.lat = stop.lat;
      item.dataset.lon = stop.lon;
      item.dataset.name = stop.name;
      item.dataset.stopType = stop.stopType;

      item.addEventListener('click', function() {
        selectStop(stop, input, suggestionsContainer, inputType);
      });

      item.addEventListener('mouseenter', function() {
        const allItems = suggestionsContainer.querySelectorAll('.autocomplete-suggestion-item, .autocomplete-group-header');
        allItems.forEach(i => {
          i.classList.remove('selected');
          i.setAttribute('aria-selected', 'false');
        });
        this.classList.add('selected');
        this.setAttribute('aria-selected', 'true');
      });

      suggestionsContainer.appendChild(item);
    } else {
      // Create a group header that can be expanded to show each specific stop
      const header = document.createElement('div');
      header.className = 'autocomplete-group-header';
      header.id = `${inputType}-group-${groupIndex}`;
      header.setAttribute('role', 'option');
      header.setAttribute('aria-expanded', 'false');
      header.setAttribute('aria-selected', 'false');

      const title = document.createElement('span');
      title.className = 'group-title';
      title.textContent = groupStops[0].name;

      const count = document.createElement('span');
      count.className = 'group-count';
      count.textContent = ` (${groupStops.length})`;

      header.appendChild(title);
      header.appendChild(count);

      // Clicking header toggles expansion
      header.addEventListener('click', function() {
        const expanded = header.getAttribute('aria-expanded') === 'true';
        header.setAttribute('aria-expanded', String(!expanded));
        if (!expanded) {
          // Render children
          renderGroupChildren(groupStops, suggestionsContainer, input, inputType, header, groupIndex);
        } else {
          // Remove children
          removeGroupChildren(suggestionsContainer, groupIndex);
        }
      });

      header.addEventListener('mouseenter', function() {
        const allItems = suggestionsContainer.querySelectorAll('.autocomplete-suggestion-item, .autocomplete-group-header');
        allItems.forEach(i => { i.classList.remove('selected'); i.setAttribute('aria-selected', 'false'); });
        header.classList.add('selected');
        header.setAttribute('aria-selected', 'true');
      });

      suggestionsContainer.appendChild(header);
    }

    groupIndex += 1;
  });

  showSuggestions(suggestionsContainer);
}

function renderGroupChildren(groupStops, suggestionsContainer, input, inputType, header, groupIndex) {
  // Insert children directly after the header
  let insertAfter = header;
  groupStops.forEach((stop, idx) => {
    const child = document.createElement('div');
    child.className = 'autocomplete-suggestion-item group-child';
    child.id = `${inputType}-group-${groupIndex}-child-${idx}`;
    child.textContent = stop.name + (stop.atcoCode ? ` — ${stop.atcoCode}` : '');
    child.setAttribute('role', 'option');
    child.setAttribute('aria-selected', 'false');

    child.dataset.atcoCode = stop.atcoCode;
    child.dataset.lat = stop.lat;
    child.dataset.lon = stop.lon;
    child.dataset.name = stop.name;
    child.dataset.stopType = stop.stopType;

    child.addEventListener('click', function() {
      selectStop(stop, input, suggestionsContainer, inputType);
    });

    child.addEventListener('mouseenter', function() {
      const allItems = suggestionsContainer.querySelectorAll('.autocomplete-suggestion-item, .autocomplete-group-header');
      allItems.forEach(i => { i.classList.remove('selected'); i.setAttribute('aria-selected', 'false'); });
      this.classList.add('selected');
      this.setAttribute('aria-selected', 'true');
    });

    insertAfter.insertAdjacentElement('afterend', child);
    insertAfter = child;
  });
}

function removeGroupChildren(suggestionsContainer, groupIndex) {
  suggestionsContainer.querySelectorAll('.autocomplete-suggestion-item.group-child').forEach(n => {
    if (n.id.includes(`-group-${groupIndex}-child-`)) n.remove();
  });
}

/**
 * Display no results message
 */
function displayNoResults(suggestionsContainer) {
  suggestionsContainer.innerHTML = `<div class="autocomplete-no-results" role="status">${t('autocomplete.noStops')}</div>`;
  showSuggestions(suggestionsContainer);
}

/**
 * Display error message
 */
function displayError(suggestionsContainer) {
  suggestionsContainer.innerHTML = `<div class="autocomplete-no-results" role="status">${t('autocomplete.errorLoadingStops')}</div>`;
  announceToScreenReader(t('announce.stopSuggestionsUnavailable'), 'assertive');
  showSuggestions(suggestionsContainer);
}

/**
 * Select a stop from suggestions
 */
function selectStop(stop, input, suggestionsContainer, inputType) {
  input.value = stop.name;
  selectedStops[inputType] = stop;
  syncSelectedStopMapMarkers({ focus: true });
  hideSuggestions(suggestionsContainer);
  input.removeAttribute('aria-activedescendant');
  setFieldError(
    inputType === 'from' ? 'from-input' : 'to-input',
    inputType === 'from' ? 'from-input-error' : 'to-input-error',
    ''
  );
  syncRouteModalWithInputState();
  updateJourneySearchButtonState();
  
  console.log(`Selected ${inputType} stop:`, stop);
}

/**
 * Update which suggestion is highlighted
 */
function updateSelectedSuggestion(suggestions, index, input) {
  suggestions.forEach((item, i) => {
    if (i === index) {
      item.classList.add('selected');
      item.setAttribute('aria-selected', 'true');
      item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else {
      item.classList.remove('selected');
      item.setAttribute('aria-selected', 'false');
    }
  });

  const active = suggestions[index];
  if (input && active?.id) {
    input.setAttribute('aria-activedescendant', active.id);
  }
}

/**
 * Show suggestions dropdown
 */
function showSuggestions(suggestionsContainer) {
  suggestionsContainer.classList.add('visible');
  const controlledInput = document.querySelector(`input[aria-controls="${suggestionsContainer.id}"]`);
  if (controlledInput) {
    controlledInput.setAttribute('aria-expanded', 'true');
  }
}

/**
 * Hide suggestions dropdown
 */
function hideSuggestions(suggestionsContainer) {
  suggestionsContainer.classList.remove('visible');
  const controlledInput = document.querySelector(`input[aria-controls="${suggestionsContainer.id}"]`);
  if (controlledInput) {
    controlledInput.setAttribute('aria-expanded', 'false');
    controlledInput.removeAttribute('aria-activedescendant');
  }
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

function getRouteInputLabels() {
  const fromInputValue = document.getElementById('from-input')?.value?.trim() || '';
  const toInputValue = document.getElementById('to-input')?.value?.trim() || '';

  return {
    fromLabel: selectedStops.from?.name || fromInputValue || t('route.unknownFrom'),
    toLabel: selectedStops.to?.name || toInputValue || t('route.unknownTo'),
    hasBothStopsSelected: Boolean(selectedStops.from && selectedStops.to),
  };
}

function showRouteLoadingState() {
  const modal = document.getElementById('route-modal');
  const routeList = document.querySelector('.route-list');
  if (!modal || !routeList) {
    return;
  }

  const { fromLabel, toLabel } = getRouteInputLabels();
  currentRoutesData = {
    from: fromLabel,
    to: toLabel,
    routes: [],
  };

  updateRouteModalHeader();
  routeList.setAttribute('aria-busy', 'true');
  routeList.innerHTML = `
    <div class="route-loading" role="status" aria-live="polite">
      <span class="route-loading-spinner" aria-hidden="true"></span>
      <div class="route-loading-texts">
        <strong>${t('route.loadingTitle')}</strong>
        <span>${t('route.loadingSubtitle')}</span>
      </div>
    </div>
  `;
  modal.classList.remove('hidden');
  updateRouteDownloadButtonState();
}

function syncRouteModalWithInputState() {
  const modal = document.getElementById('route-modal');
  const routeList = document.querySelector('.route-list');
  if (!modal || !routeList) {
    return;
  }

  const { hasBothStopsSelected } = getRouteInputLabels();
  updateJourneySearchButtonState();

  if (hasBothStopsSelected) {
    updateRouteModalHeader();
    updateRouteDownloadButtonState();
    return;
  }

  currentRoutesData = null;
  routeList.removeAttribute('aria-busy');
  routeList.innerHTML = '';
  updateRouteDownloadButtonState();
  modal.classList.add('hidden');
  resetFloatingPanelToDefault('route-modal');
}

/**
 * Search for routes between the selected stops
 */
async function searchRoutes() {
  updateJourneySearchButtonState();

  // Only proceed if both stops are selected
  if (!selectedStops.from || !selectedStops.to) {
    console.warn('Both from and to stops must be selected');
    if (!selectedStops.from) {
      setFieldError('from-input', 'from-input-error', t('journey.departureRequired'));
    }
    if (!selectedStops.to) {
      setFieldError('to-input', 'to-input-error', t('journey.arrivalRequired'));
    }
    announceToScreenReader(t('announce.selectBothStops'), 'assertive');
    return;
  }

  setFieldError('from-input', 'from-input-error', '');
  setFieldError('to-input', 'to-input-error', '');

  showRouteLoadingState();
  announceToScreenReader(t('announce.searchingRoutes'));

  const requestFrom = selectedStops.from;
  const requestTo = selectedStops.to;
  const controller = new AbortController();
  activeRouteSearchControllers.add(controller);
  let timeoutId = null;

  try {
    timeoutId = window.setTimeout(() => controller.abort(), ROUTE_SEARCH_TIMEOUT_MS);

    const selectedSort = document.getElementById('sort')?.value || 'soonest_arrival';
    const selectedModes = getSelectedRouteModes();
    const body = {
      from: requestFrom,
      to: requestTo,
      sort_by: selectedSort,
      modes: selectedModes,
    };

    const response = await fetch('/api/routes/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
      body: JSON.stringify(body),
    });
    window.clearTimeout(timeoutId);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('Error searching routes:', errorData.error);
      announceToScreenReader(errorData.error || t('alerts.unableToFindRoutes'), 'assertive');
      const modal = document.getElementById('route-modal');
      const routeList = document.querySelector('.route-list');
      if (modal) {
        modal.classList.add('hidden');
        resetFloatingPanelToDefault('route-modal');
      }
      if (routeList) {
        routeList.removeAttribute('aria-busy');
      }
      return;
    }

    const data = await response.json();
    console.log('Routes found:', data.routes);
    
    // Display the routes in the modal
    displayRoutesModal(data);
  } catch (error) {
    console.error('Error fetching routes:', error);
    const routeList = document.querySelector('.route-list');
    if (routeList) {
      routeList.removeAttribute('aria-busy');
    }
    if (error && error.name === 'AbortError') {
      announceToScreenReader('Route search timed out. Please try again with different stops.', 'assertive');
    } else {
      announceToScreenReader(t('announce.routeFetchError'), 'assertive');
    }
  } finally {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
    activeRouteSearchControllers.delete(controller);
  }
}

/**
 * Display the routes modal with search results
 */
function displayRoutesModal(data) {
  const modal = document.getElementById('route-modal');
  const routeList = document.querySelector('.route-list');
  
  if (!modal) {
    console.error('Route modal not found');
    return;
  }

  if (routeList) {
    routeList.removeAttribute('aria-busy');
  }

  // Store the routes data globally for sorting
  currentRoutesData = data;

  // Update the modal header with from/to information
  updateRouteModalHeader();

  // Routes are already sorted server-side using the selected sort mode.
  renderRoutesTable(data.routes || []);
  updateRouteDownloadButtonState();

  // Show the modal by removing the hidden class
  resetFloatingPanelToDefault('route-modal');
  modal.classList.remove('hidden');
  announceToScreenReader(t('announce.routesShowing', {
    count: Array.isArray(data.routes) ? data.routes.length : 0,
    from: data.from,
    to: data.to,
  }));
}

/**
 * Sort routes based on the selected criteria
 */
function sortRoutes(sortMethod, routes) {
  const routesCopy = [...routes];

  const toSortableMinutes = (timeStr) => {
    if (!timeStr || typeof timeStr !== 'string') return Number.MAX_SAFE_INTEGER;
    const [hh, mm] = timeStr.split(':').map(Number);
    if (!Number.isFinite(hh) || !Number.isFinite(mm)) return Number.MAX_SAFE_INTEGER;
    return (hh * 60) + mm;
  };
  
  switch (sortMethod) {
    case 'soonest_arrival':
      // Sort by earliest arrival, then by duration
      return routesCopy.sort((a, b) => {
        const aArrive = toSortableMinutes(a.end_time);
        const bArrive = toSortableMinutes(b.end_time);
        if (aArrive !== bArrive) {
          return aArrive - bArrive;
        }
        return a.duration_mins - b.duration_mins;
      });
    
    case 'fewest_changes':
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
  if (mins < 60) return t('common.minutesOnly', { minutes: formatLocalizedNumber(mins) });
  const hours = Math.floor(mins / 60);
  const remainder = mins % 60;
  return remainder > 0
    ? t('common.hoursMinutes', { hours: formatLocalizedNumber(hours), minutes: formatLocalizedNumber(remainder) })
    : t('common.hoursOnly', { hours: formatLocalizedNumber(hours) });
}

function getCurrentSortedRoutes() {
  if (!currentRoutesData || !Array.isArray(currentRoutesData.routes)) {
    return [];
  }

  const sortMethod = document.getElementById('sort')?.value || 'soonest_arrival';
  return filterRoutesByModeSelection(sortRoutes(sortMethod, currentRoutesData.routes));
}

function updateRouteModalHeader() {
  const modalHeader = document.querySelector('.route-modal-header');
  if (!modalHeader) {
    return;
  }

  const closeBtn = modalHeader.querySelector('#close-route-modal');
  // Prefer explicit selected stop details when available to clarify which
  // physical stop was chosen (e.g. include ATCO code or other identifier).
  const fmtStop = (stopObj, fallback) => {
    if (!stopObj) return fallback;
    if (typeof stopObj === 'string') return stopObj;
    const parts = [stopObj.name];
    if (stopObj.atcoCode) parts.push(stopObj.atcoCode);
    else if (stopObj.naptan) parts.push(stopObj.naptan);
    return parts.filter(Boolean).join(' — ');
  };

  const fromLabel = currentRoutesData && currentRoutesData.from
    ? currentRoutesData.from
    : fmtStop(selectedStops.from, t('route.unknownFrom'));

  const toLabel = currentRoutesData && currentRoutesData.to
    ? currentRoutesData.to
    : fmtStop(selectedStops.to, t('route.unknownTo'));

  const headerLabel = currentRoutesData || selectedStops.from || selectedStops.to
    ? t('route.headerFromTo', { from: fromLabel, to: toLabel })
    : t('route.defaultHeader');

  modalHeader.textContent = '';
  modalHeader.appendChild(document.createTextNode(headerLabel));
  if (closeBtn) {
    modalHeader.appendChild(closeBtn);
  }
}

function updateRouteDownloadButtonState() {
  const downloadBtn = document.getElementById('download-routes-pdf');
  if (!downloadBtn) {
    return;
  }

  const hasRoutes = getCurrentSortedRoutes().length > 0;
  downloadBtn.disabled = !hasRoutes;
  downloadBtn.title = hasRoutes
    ? t('route.downloadTooltipEnabled')
    : t('route.downloadTooltipDisabled');
}

function formatRouteTransportSummary(route) {
  if (!route || !Array.isArray(route.transport) || route.transport.length === 0) {
    return t('route.walkingRoute');
  }

  return route.transport
    .map(mode => {
      const key = `transport.${mode}`;
      const translated = t(key);
      return translated === key ? mode : translated;
    })
    .join(' → ');
}

function formatPdfLegDescription(leg) {
  const departTime = formatLocalizedClockTime(leg.depart);
  const arriveTime = formatLocalizedClockTime(leg.arrive);

  if (leg.mode === 'walk') {
    return t('route.leg.walk', {
      from: leg.from_stop,
      to: leg.to_stop,
      distance: formatLocalizedNumber(leg.distance_m),
      duration: formatDuration(leg.duration_mins),
      depart: departTime,
      arrive: arriveTime,
    });
  }

  if (leg.mode === 'wait') {
    return t('route.leg.wait', {
      at: leg.from_stop,
      duration: formatDuration(leg.duration_mins),
      depart: departTime,
      arrive: arriveTime,
    });
  }

  const service = leg.service || leg.mode;
  return t('route.leg.transport', {
    service,
    from: leg.from_stop,
    to: leg.to_stop,
    duration: formatDuration(leg.duration_mins),
    depart: departTime,
    arrive: arriveTime,
  });
}

function sanitizePdfFileNamePart(value) {
  return String(value || 'route-plan')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40) || 'route-plan';
}

function addWrappedPdfText(doc, text, x, y, options = {}) {
  const {
    maxWidth,
    lineHeight = 14,
    topMargin = 48,
    bottomMargin = 48,
    fontSize = 11,
    fontStyle = 'normal',
  } = options;

  const pageHeight = doc.internal.pageSize.getHeight();
  doc.setFont('helvetica', fontStyle);
  doc.setFontSize(fontSize);

  const lines = doc.splitTextToSize(String(text || ''), maxWidth);
  lines.forEach(line => {
    if (y > pageHeight - bottomMargin) {
      doc.addPage();
      y = topMargin;
      doc.setFont('helvetica', fontStyle);
      doc.setFontSize(fontSize);
    }

    doc.text(line, x, y);
    y += lineHeight;
  });

  return y;
}

function getWrappedPdfLineCount(doc, text, maxWidth) {
  return doc.splitTextToSize(String(text || ''), maxWidth).length;
}

function exportRoutesToPdf() {
  const routes = getCurrentSortedRoutes();
  if (!currentRoutesData || routes.length === 0) {
    alert(t('alerts.searchRouteBeforePdf'));
    return;
  }

  const JsPdf = window.jspdf?.jsPDF;
  if (!JsPdf) {
    alert(t('alerts.pdfUnavailable'));
    return;
  }

  const doc = new JsPdf({ unit: 'pt', format: 'a4' });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const marginX = 48;
  const topMargin = 48;
  const bottomMargin = 48;
  const contentWidth = pageWidth - (marginX * 2);
  const sortSelect = document.getElementById('sort');
  const sortLabelText = sortSelect?.options?.[sortSelect.selectedIndex]?.textContent?.trim()
    || t('route.sort.arriveSoonest');
  const exportedAt = new Date();
  const colors = {
    maroon: [139, 17, 17],
    redMain: [183, 28, 28],
    redLight: [198, 40, 40],
    blush: [247, 236, 236],
    soft: [252, 247, 247],
    border: [226, 204, 204],
    text: [68, 68, 68],
    muted: [110, 110, 110],
    white: [255, 255, 255],
  };

  let currentPage = 1;
  const startStyledPage = (pageNumber) => {
    doc.setFillColor(...colors.soft);
    doc.rect(0, 0, pageWidth, pageHeight, 'F');

    doc.setFillColor(...colors.maroon);
    doc.rect(0, 0, pageWidth, 82, 'F');

    doc.setFillColor(...colors.redLight);
    doc.rect(0, 82, pageWidth, 10, 'F');

    doc.setTextColor(...colors.white);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(20);
    doc.text(t('app.title'), marginX, 38);
    doc.setFontSize(13);
    doc.text(pageNumber === 1 ? t('pdf.completeRoutePlan') : t('pdf.routePlanContinued'), marginX, 60);

    return 126;
  };

  let y = startStyledPage(currentPage);

  const summaryTitle = `${currentRoutesData.from} to ${currentRoutesData.to}`;
  const summaryMeta = t('pdf.summaryMeta', {
    exportedAt: formatLocalizedDateTime(exportedAt),
    count: routes.length,
    suffix: routes.length === 1 ? '' : 's',
    sortLabel: sortLabelText,
  });
  const summaryTitleHeight = getWrappedPdfLineCount(doc, summaryTitle, contentWidth - 48) * 18;
  const summaryMetaHeight = getWrappedPdfLineCount(doc, summaryMeta, contentWidth - 40) * 14;
  const summaryBoxHeight = Math.max(86, 26 + summaryTitleHeight + summaryMetaHeight + 26);
  const summaryStartY = y;

  doc.setFillColor(...colors.blush);
  doc.setDrawColor(...colors.border);
  doc.roundedRect(marginX, summaryStartY, contentWidth, summaryBoxHeight, 14, 14, 'FD');
  doc.setFillColor(...colors.redMain);
  doc.roundedRect(marginX, summaryStartY, 12, summaryBoxHeight, 14, 14, 'F');

  doc.setTextColor(...colors.redMain);
  y = addWrappedPdfText(doc, summaryTitle, marginX + 24, summaryStartY + 28, {
    maxWidth: contentWidth - 48,
    lineHeight: 18,
    topMargin: 126,
    bottomMargin,
    fontSize: 15,
    fontStyle: 'bold',
  });

  doc.setTextColor(...colors.text);
  y = addWrappedPdfText(
    doc,
    summaryMeta,
    marginX + 24,
    y + 6,
    {
      maxWidth: contentWidth - 40,
      lineHeight: 14,
      topMargin: 126,
      bottomMargin,
      fontSize: 10,
    }
  );

  y = summaryStartY + summaryBoxHeight + 18;

  routes.forEach((route, routeIndex) => {
    const routeTitle = t('pdf.routeTitle', {
      index: formatLocalizedNumber(routeIndex + 1),
      summary: formatRouteTransportSummary(route),
    });
    const routeMeta = t('pdf.routeMeta', {
      startTime: formatLocalizedClockTime(route.start_time),
      endTime: formatLocalizedClockTime(route.end_time),
      duration: formatDuration(route.duration_mins),
      changes: formatLocalizedNumber(route.changes),
    });
    const routeTitleHeight = getWrappedPdfLineCount(doc, routeTitle, contentWidth - 48) * 16;
    const routeMetaHeight = getWrappedPdfLineCount(doc, routeMeta, contentWidth - 48) * 13;

    let legHeight = 0;
    (route.legs || []).forEach((leg, legIndex) => {
      legHeight += getWrappedPdfLineCount(doc, `${formatLocalizedNumber(legIndex + 1)}. ${formatPdfLegDescription(leg)}`, contentWidth - 78) * 13 + 14;
      if (Array.isArray(leg.intermediate_stops) && leg.intermediate_stops.length > 0) {
        leg.intermediate_stops.forEach(stop => {
          const stopLabel = stop.time ? `${stop.time} ${stop.name}` : stop.name;
          legHeight += getWrappedPdfLineCount(doc, t('pdf.intermediateStop', { stop: stopLabel }), contentWidth - 108) * 11 + 6;
        });
      }
    });

    const routeBlockHeight = Math.max(118, 34 + routeTitleHeight + routeMetaHeight + legHeight + 28);

    if (y + routeBlockHeight > pageHeight - bottomMargin - 18) {
      doc.addPage();
      currentPage += 1;
      y = startStyledPage(currentPage);
    }

    doc.setFillColor(...colors.white);
    doc.setDrawColor(...colors.border);
    doc.roundedRect(marginX, y, contentWidth, routeBlockHeight, 14, 14, 'FD');
    doc.setFillColor(...colors.redMain);
    doc.roundedRect(marginX, y, 10, routeBlockHeight, 14, 14, 'F');

    doc.setTextColor(...colors.redMain);
    y = addWrappedPdfText(doc, routeTitle, marginX + 24, y + 26, {
      maxWidth: contentWidth - 48,
      lineHeight: 16,
      topMargin: 126,
      bottomMargin,
      fontSize: 13,
      fontStyle: 'bold',
    });

    doc.setTextColor(...colors.text);
    y = addWrappedPdfText(doc, routeMeta, marginX + 24, y + 2, {
      maxWidth: contentWidth - 48,
      lineHeight: 13,
      topMargin: 126,
      bottomMargin,
      fontSize: 10,
    });

    (route.legs || []).forEach((leg, legIndex) => {
      const accent = leg.mode === 'walk'
        ? [160, 160, 160]
        : leg.mode === 'train'
          ? colors.maroon
          : colors.redLight;

      doc.setFillColor(...accent);
      doc.circle(marginX + 28, y + 12, 4, 'F');
      doc.setTextColor(...colors.text);
      y = addWrappedPdfText(doc, `${formatLocalizedNumber(legIndex + 1)}. ${formatPdfLegDescription(leg)}`, marginX + 40, y + 16, {
        maxWidth: contentWidth - 78,
        lineHeight: 13,
        topMargin: 126,
        bottomMargin,
        fontSize: 10,
      });

      if (Array.isArray(leg.intermediate_stops) && leg.intermediate_stops.length > 0) {
        doc.setTextColor(...colors.muted);
        leg.intermediate_stops.forEach(stop => {
          const stopLabel = stop.time ? `${stop.time} ${stop.name}` : stop.name;
          y = addWrappedPdfText(doc, t('pdf.intermediateStop', { stop: stopLabel }), marginX + 56, y + 2, {
            maxWidth: contentWidth - 108,
            lineHeight: 11,
            topMargin: 126,
            bottomMargin,
            fontSize: 9,
          });
        });
      }

      y += 4;
    });

    y += 18;
  });

  const totalPages = doc.getNumberOfPages();
  for (let pageIndex = 1; pageIndex <= totalPages; pageIndex += 1) {
    doc.setPage(pageIndex);
    doc.setDrawColor(...colors.border);
    doc.line(marginX, pageHeight - 28, pageWidth - marginX, pageHeight - 28);
    doc.setTextColor(...colors.muted);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.text(
      t('pdf.pageXofY', {
        page: formatLocalizedNumber(pageIndex),
        total: formatLocalizedNumber(totalPages),
      }),
      pageWidth - marginX - 56,
      pageHeight - 14
    );
  }

  const fileName = `${sanitizePdfFileNamePart(currentRoutesData.from)}-to-${sanitizePdfFileNamePart(currentRoutesData.to)}-routes.pdf`;
  doc.save(fileName);
}

function buildRouteSavePayload(route) {
  const fromName = (currentRoutesData && currentRoutesData.from) || selectedStops.from?.name || '';
  const toName = (currentRoutesData && currentRoutesData.to) || selectedStops.to?.name || '';
  const transportLabel = (route.transport || [])
    .map(mode => t(`transport.${mode}`))
    .join(' + ') || t('route.genericName');

  return {
    routeName: `${transportLabel} (${route.start_time}–${route.end_time})`,
    routeStart: fromName,
    routeEnd: toName,
  };
}

function isZeroDistanceWalkLeg(leg) {
  if (!leg || String(leg.mode || '').toLowerCase() !== 'walk') {
    return false;
  }
  const distance = Number(leg.distance_m);
  return Number.isFinite(distance) && distance <= 0;
}

function isShortWalkLeg(leg) {
  if (!leg || String(leg.mode || '').toLowerCase() !== 'walk') {
    return false;
  }
  const duration = Number(leg.duration_mins);
  return Number.isFinite(duration) && duration <= 2;
}

function appendRouteLeg(detailContainer, leg) {
  if (!detailContainer || !leg) {
    return false;
  }

  if (String(leg.mode || '').toLowerCase() === 'walk') {
    if (isZeroDistanceWalkLeg(leg)) {
      return false;
    }
    detailContainer.appendChild(buildWalkLeg(leg));
    return true;
  }

  if (String(leg.mode || '').toLowerCase() === 'wait') {
    detailContainer.appendChild(buildWaitLeg(leg));
    return true;
  }

  detailContainer.appendChild(buildTransportLeg(leg));
  return true;
}

async function handleSaveSearchedRoute(route, saveButton) {
  if (!authState.token) {
    alert(t('alerts.loginToSaveRoutes'));
    openAuthModal();
    return;
  }

  try {
    const payload = buildRouteSavePayload(route);
    await apiRequest('/api/account/saved-routes', {
      method: 'POST',
      body: payload,
    });

    saveButton.textContent = t('route.saved');
    saveButton.classList.add('saved');
    saveButton.disabled = true;
    saveButton.setAttribute('aria-label', t('route.savedAria'));
    announceToScreenReader(t('announce.routeSaved'));

    await refreshAccountView();
  } catch (error) {
    alert(localizeApiErrorMessage(error.message, 'alerts.saveRouteFailed'));
  }
}

/**
 * Build a walking-leg element for the detail panel
 */
function buildWalkLeg(leg) {
  const el = document.createElement('div');
  el.className = 'route-detail-leg route-detail-walk';
  const departTime = formatLocalizedClockTime(leg.depart);
  const arriveTime = formatLocalizedClockTime(leg.arrive);
  el.innerHTML = `
    <span class="leg-icon icon-walk"></span>
    <div class="leg-info">
      <div class="leg-summary">${t('route.leg.walkSummary', { distance: formatLocalizedNumber(leg.distance_m), duration: formatDuration(leg.duration_mins) })}</div>
      <div class="leg-stops">${t('route.leg.stops', { from: leg.from_stop, to: leg.to_stop })}</div>
    </div>
    <span class="leg-time">${departTime} – ${arriveTime}</span>
  `;
  return el;
}

/**
 * Build a wait/transfer-leg element for the detail panel
 */
function buildWaitLeg(leg) {
  const el = document.createElement('div');
  el.className = 'route-detail-leg route-detail-wait';
  const departTime = formatLocalizedClockTime(leg.depart);
  const arriveTime = formatLocalizedClockTime(leg.arrive);
  el.innerHTML = `
    <span class="leg-icon icon-walk"></span>
    <div class="leg-info">
      <div class="leg-summary">${t('route.leg.waitSummary', { at: leg.from_stop, duration: formatDuration(leg.duration_mins) })}</div>
    </div>
    <span class="leg-time">${departTime} – ${arriveTime}</span>
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
  const departTime = formatLocalizedClockTime(leg.depart);
  const arriveTime = formatLocalizedClockTime(leg.arrive);

  let intermediateHTML = '';
  if (leg.intermediate_stops && leg.intermediate_stops.length > 0) {
    const stopsHTML = leg.intermediate_stops
      .map(s => `<li><span class="intermediate-time">${formatLocalizedClockTime(s.time)}</span> ${s.name}</li>`)
      .join('');
    intermediateHTML = `<ul class="intermediate-stops">${stopsHTML}</ul>`;
  }

  el.innerHTML = `
    <span class="leg-icon ${modeIcon}"></span>
    <div class="leg-info">
      <div class="leg-summary">${t('route.leg.transportSummary', { service, duration: formatDuration(leg.duration_mins) })}</div>
      <div class="leg-stops">${t('route.leg.stops', { from: leg.from_stop, to: leg.to_stop })}</div>
      ${intermediateHTML}
    </div>
    <span class="leg-time">${departTime} – ${arriveTime}</span>
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
    routeRow.setAttribute('aria-expanded', 'false');
    routeRow.removeAttribute('aria-controls');
    return;
  }

  // Collapse any other open detail
  document.querySelectorAll('.route-detail').forEach(d => d.remove());
  document.querySelectorAll('.route-row.expanded').forEach(r => {
    r.classList.remove('expanded');
    r.setAttribute('aria-expanded', 'false');
    r.removeAttribute('aria-controls');
  });

  // Build the detail panel
  const detail = document.createElement('div');
  detail.className = 'route-detail';
  const detailId = `route-detail-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  detail.id = detailId;

  if (route.legs && route.legs.length > 0) {
    let hasVisibleLeg = false;
    route.legs.forEach(leg => {
      if (appendRouteLeg(detail, leg)) {
        hasVisibleLeg = true;
      }
    });

    if (!hasVisibleLeg) {
      detail.innerHTML = `<div class="route-detail-empty">${t('route.noLegDetails')}</div>`;
    }
  } else {
    detail.innerHTML = `<div class="route-detail-empty">${t('route.noLegDetails')}</div>`;
  }

  // Insert detail right after the clicked row
  routeRow.after(detail);
  routeRow.classList.add('expanded');
  routeRow.setAttribute('aria-expanded', 'true');
  routeRow.setAttribute('aria-controls', detailId);
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

  routeList.removeAttribute('aria-busy');

  // Clear existing routes (including any open details)
  routeList.innerHTML = '';

  if (!routes || routes.length === 0) {
    routeList.innerHTML = `<div class="route-row">${t('route.noResults')}</div>`;
    announceToScreenReader(t('route.noResults'), 'assertive');
    return;
  }

  const modeFilteredRoutes = filterRoutesByModeSelection(routes);

  // Add each route as a clickable row
  modeFilteredRoutes.forEach((route, index) => {
    const routeRow = document.createElement('div');
    routeRow.className = 'route-row' + (index % 2 === 1 ? ' alt' : '');
    routeRow.style.cursor = 'pointer';
    routeRow.title = t('route.viewDetails');
    routeRow.setAttribute('role', 'button');
    routeRow.setAttribute('tabindex', '0');
    routeRow.setAttribute('aria-expanded', 'false');
    routeRow.setAttribute(
      'aria-label',
      t('route.rowAria', {
        index: index + 1,
        startTime: formatLocalizedClockTime(route.start_time),
        endTime: formatLocalizedClockTime(route.end_time),
        duration: formatDuration(route.duration_mins),
        changes: route.changes,
        suffix: route.changes === 1 ? '' : 's',
      })
    );

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
      icon.setAttribute('aria-hidden', 'true');
      iconsContainer.appendChild(icon);
    });

    // Changes badge
    if (route.changes > 0) {
      const badge = document.createElement('span');
      badge.className = 'changes-badge';
      badge.textContent = t('route.changesBadge', { count: route.changes, suffix: route.changes > 1 ? 's' : '' });
      iconsContainer.appendChild(badge);
    }

    // Time display
    const timesSpan = document.createElement('span');
    timesSpan.className = 'route-times';
    timesSpan.textContent = `${formatLocalizedClockTime(route.start_time)} − ${formatLocalizedClockTime(route.end_time)}`;

    // Duration display
    const durationSpan = document.createElement('span');
    durationSpan.className = 'route-duration';
    durationSpan.textContent = formatDuration(route.duration_mins);

    // Save route button
    const saveBtn = document.createElement('button');
    saveBtn.className = 'route-save-btn';
    saveBtn.type = 'button';
    saveBtn.textContent = t('route.save');
    saveBtn.setAttribute('aria-label', t('route.saveAria', {
      index: index + 1,
      startTime: formatLocalizedClockTime(route.start_time),
      endTime: formatLocalizedClockTime(route.end_time),
    }));
    saveBtn.addEventListener('click', event => {
      event.stopPropagation();
      handleSaveSearchedRoute(route, saveBtn);
    });

    // Expand indicator
    const expandIcon = document.createElement('span');
    expandIcon.className = 'route-expand-icon';
    expandIcon.textContent = '▼';
    expandIcon.setAttribute('aria-hidden', 'true');

    // Assemble the row
    routeRow.appendChild(iconsContainer);
    routeRow.appendChild(timesSpan);
    routeRow.appendChild(durationSpan);
    routeRow.appendChild(saveBtn);
    routeRow.appendChild(expandIcon);

    // Click handler to toggle detail panel
    routeRow.addEventListener('click', () => toggleRouteDetail(routeRow, route));
    routeRow.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleRouteDetail(routeRow, route);
      }
    });

    routeList.appendChild(routeRow);
  });

  announceToScreenReader(t('announce.routesAvailable', { count: modeFilteredRoutes.length }));
}

function getSelectedRouteModes() {
  const checkboxes = Array.from(document.querySelectorAll('.route-mode-filter'));
  const selected = checkboxes.filter(cb => cb.checked).map(cb => String(cb.value || '').toLowerCase());
  if (!selected.length) {
    return Array.from(DEFAULT_ROUTE_MODES);
  }
  return selected;
}

function routeModeAllowed(leg, selectedModes) {
  const normalized = String(leg?.mode || '').toLowerCase();
  // Wait/transfer legs are auxiliary and should not hide an otherwise
  // valid route when mode filters are applied.
  if (normalized === 'wait') {
    return true;
  }

  // Keep connector walks (<=2 minutes) even when walk filter is disabled.
  if (normalized === 'walk' && isShortWalkLeg(leg)) {
    return true;
  }

  // Legacy `/api/routes/search` can still emit `train` while v2 emits `rail`.
  if (normalized === 'train') {
    return selectedModes.has('rail') || selectedModes.has('train');
  }
  return selectedModes.has(normalized);
}

function filterRoutesByModeSelection(routes) {
  const selectedModes = new Set(getSelectedRouteModes());
  return (routes || []).filter(route => {
    const legs = Array.isArray(route.legs) ? route.legs : [];
    if (!legs.length) return true;
    return legs.every(leg => routeModeAllowed(leg, selectedModes));
  });
}

// ============================================================================
// END AUTOCOMPLETE FUNCTIONALITY
// ============================================================================

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', async function() {
  await initializeLocalization();
  updateRouteModalHeader();

  // Initialize the interactive map (store globally for later invalidation)
  window.appMap = initializeMap();
  
  // Initialize autocomplete for search inputs
  initializeAutocomplete();
  
  // Set up swap button functionality
  setupSwapButton();
  setupJourneySearchButton();

  document.querySelectorAll('.route-mode-filter').forEach(cb => {
    cb.addEventListener('change', () => {
      if (currentRoutesData && Array.isArray(currentRoutesData.routes)) {
        renderRoutesTable(getCurrentSortedRoutes());
      }
    });
  });
  
  // Set up panel toggle event listeners
  const weatherBtn = document.getElementById('weather-btn');
  const notifBtn = document.getElementById('notif-btn');
  const mapStyleSelect = document.getElementById('map-style-select');

  if (mapStyleSelect && window.appMap && typeof window.appMap.getAvailableMapStyles === 'function') {
    const presets = window.appMap.getAvailableMapStyles();
    mapStyleSelect.innerHTML = presets
      .map(p => `<option value="${p.id}" title="${getMapStyleA11yLabel(p)}">${p.shortLabel || p.label}</option>`)
      .join('');
    const current = window.appMap.getCurrentMapStyle();
    if (current) {
      mapStyleSelect.value = current.id;
      mapStyleSelect.title = getMapStyleA11yLabel(current);
      mapStyleSelect.setAttribute('aria-label', getMapStyleA11yLabel(current));
      // Ensure UI reflects the currently active map style on initial load
      try {
        updateMapStyleButtonUI(current);
      } catch (e) {
        // ignore in non-browser environments
      }
    }

    mapStyleSelect.addEventListener('change', function() {
      if (typeof window.appMap.setMapStyleById !== 'function') return;
      const applied = window.appMap.setMapStyleById(this.value);
      if (applied) {
        updateMapStyleButtonUI(applied);
        announceToScreenReader(t('announce.mapStyleChanged', { style: applied.label }));
      }
    });
  }
  
  if (weatherBtn) {
    weatherBtn.addEventListener('click', toggleWeatherPanel);
  }
  
  if (notifBtn) {
    notifBtn.addEventListener('click', toggleNotificationsPanel);
  }

  // Set up route modal close button
  const closeRouteModalBtn = document.getElementById('close-route-modal');
  const routeModal = document.getElementById('route-modal');
  const stopServicesModal = document.getElementById('stop-services-modal');
  const closeStopServicesModalBtn = document.getElementById('close-stop-services-modal');
  const sortSelect = document.getElementById('sort');
  const downloadRoutesPdfBtn = document.getElementById('download-routes-pdf');
  
  if (closeRouteModalBtn && routeModal) {
    closeRouteModalBtn.addEventListener('click', () => {
      routeModal.classList.add('hidden');
      resetFloatingPanelToDefault('route-modal');
      announceToScreenReader(t('announce.routesModalClosed'));
    });
  }

  if (closeStopServicesModalBtn && stopServicesModal) {
    closeStopServicesModalBtn.addEventListener('click', closeStopServicesModal);
  }

  // Set up sort dropdown for routes
  if (sortSelect) {
    sortSelect.addEventListener('change', () => {
      // Re-plan using the selected backend sort mode.
      if (selectedStops.from && selectedStops.to) {
        searchRoutes();
      }
    });
  }

  if (downloadRoutesPdfBtn) {
    downloadRoutesPdfBtn.addEventListener('click', exportRoutesToPdf);
    updateRouteDownloadButtonState();
  }

  // Close modal when clicking outside of it
  if (routeModal) {
    routeModal.addEventListener('click', (event) => {
      if (event.target === routeModal) {
        routeModal.classList.add('hidden');
        resetFloatingPanelToDefault('route-modal');
        announceToScreenReader(t('announce.routesModalClosed'));
      }
    });
  }

  if (stopServicesModal) {
    stopServicesModal.addEventListener('click', (event) => {
      if (event.target === stopServicesModal) {
        closeStopServicesModal();
      }
    });
  }

  attachFaqEventHandlers();
  attachSupportEventHandlers();
  attachAccountEventHandlers();
  initWeatherSearch();
  setupSidebarToggle();
  initializeFloatingPanels();
  clampVisibleFloatingPanels();

  // Restore accessibility settings from localStorage (account fetch may override)
  const savedAccessibility = JSON.parse(localStorage.getItem('accessibilitySettings') || 'null');
  if (savedAccessibility) {
    applyAccessibilitySettings(savedAccessibility);
  } else {
    // Backward compatibility with legacy colorblind setting
    const savedColorblindMode = JSON.parse(localStorage.getItem('colorblindMode') || 'false');
    if (savedColorblindMode) {
      applyAccessibilitySettings({ colorMode: 'deuteranopia', zoomLevel: 1 });
    } else {
      applyAccessibilitySettings(ACCESSIBILITY_DEFAULTS, { persistLocal: false });
    }
  }

  refreshAccountView();
  
  // Health check for backend (if available)
  checkHealth();
});

// ---------------------------------------------------------------------------
// Sidebar overlay helper (shows/hides backdrop on narrow viewports)
// ---------------------------------------------------------------------------
function updateSidebarOverlay(sidebarOpen) {
  const overlay = document.getElementById('sidebar-overlay');
  if (!overlay) return;
  if (window.innerWidth <= 768 && sidebarOpen) {
    overlay.classList.add('active');
  } else {
    overlay.classList.remove('active');
  }
}

// Keep overlay in sync when the window is resized across the breakpoint
window.addEventListener('resize', () => {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  const isOpen = !sidebar.classList.contains('minimized');
  updateSidebarOverlay(isOpen);
  clampVisibleFloatingPanels();

  // Invalidate map size after resize so tiles redraw correctly
  if (window.appMap && typeof window.appMap.invalidateSize === 'function') {
    window.appMap.invalidateSize();
  }
});

// ---------------------------------------------------------------------------
// Sidebar toggle: minimise / extend
// ---------------------------------------------------------------------------
function setupSidebarToggle() {
  const btn = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const mapArea = document.querySelector('.map-area');
  if (!btn || !sidebar || !mapArea) return;

  // Restore saved state
  const saved = JSON.parse(localStorage.getItem('sidebarMinimized') || 'false');
  if (saved) {
    sidebar.classList.add('minimized');
    mapArea.classList.add('minimized');
    document.body.classList.add('sidebar-minimized');
    btn.setAttribute('aria-expanded', 'false');
    const icon = btn.querySelector('.sidebar-toggle-icon');
    if (icon) icon.textContent = '›';
  } else {
    btn.setAttribute('aria-expanded', 'true');
    document.body.classList.remove('sidebar-minimized');
    const icon = btn.querySelector('.sidebar-toggle-icon');
    if (icon) icon.textContent = '‹';
  }

  // Ensure button has an accessible pressed state and title
  btn.setAttribute('role', 'button');
  btn.setAttribute('aria-pressed', String(!saved));
  btn.title = saved ? t('navigation.expandSidebar') : t('navigation.collapseSidebar');
  btn.setAttribute('aria-label', saved ? t('navigation.expandSidebarAria') : t('navigation.collapseSidebarAria'));

  btn.addEventListener('click', () => {
    const isNowMin = sidebar.classList.toggle('minimized');
    mapArea.classList.toggle('minimized', isNowMin);
    document.body.classList.toggle('sidebar-minimized', isNowMin);
    btn.setAttribute('aria-expanded', String(!isNowMin));
    btn.setAttribute('aria-pressed', String(!isNowMin));
    btn.title = isNowMin ? t('navigation.expandSidebar') : t('navigation.collapseSidebar');
    btn.setAttribute('aria-label', isNowMin ? t('navigation.expandSidebarAria') : t('navigation.collapseSidebarAria'));
    const icon = btn.querySelector('.sidebar-toggle-icon');
    if (icon) icon.textContent = isNowMin ? '›' : '‹';
    localStorage.setItem('sidebarMinimized', JSON.stringify(isNowMin));
    announceToScreenReader(isNowMin ? t('announce.sidebarCollapsed') : t('announce.sidebarExpanded'));

    // Toggle mobile overlay backdrop
    updateSidebarOverlay(!isNowMin);

    // If map exists, invalidate size so Leaflet redraws correctly
    if (window.appMap && typeof window.appMap.invalidateSize === 'function') {
      // allow CSS transition to complete
      setTimeout(() => window.appMap.invalidateSize(), 250);
    }

    // Keep movable/resizable panels inside the new map-area bounds.
    setTimeout(() => {
      clampVisibleFloatingPanels();
    }, 260);
  });

  // Overlay click closes sidebar on mobile
  const overlay = document.getElementById('sidebar-overlay');
  if (overlay) {
    overlay.addEventListener('click', () => {
      if (!sidebar.classList.contains('minimized')) {
        btn.click();
      }
    });
  }

  // On narrow viewports auto-close sidebar when a nav link is clicked
  const sidebarLinks = document.querySelectorAll('.sidebar-links a');
  sidebarLinks.forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768 && !sidebar.classList.contains('minimized')) {
        btn.click();
      }
    });
  });

  // Auto-minimise sidebar on narrow screens at initial load
  if (window.innerWidth <= 768 && !saved) {
    btn.click();
  }
}

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
