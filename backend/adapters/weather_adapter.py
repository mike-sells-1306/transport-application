import requests
import os
from datetime import datetime, timedelta

BASE_URL = "https://transport.scc.lancs.ac.uk"


class WeatherAdapter:
    """Adapter for fetching weather data from the transport API."""

    def __init__(self):
        self._poll_min_seconds = max(5, int(os.getenv("LIVE_POLL_MIN_SECONDS", "5")))
        self._weather_cache = {}

    def _cache_key(self, latitude: float, longitude: float) -> tuple:
        # Round to reduce duplicate requests for visually identical map points.
        return (round(float(latitude), 4), round(float(longitude), 4))

    def fetch_weather(self, latitude: float, longitude: float) -> dict:
        """
        Fetch current weather for given coordinates.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Dictionary containing weather data
        """
        url = f"{BASE_URL}/weather?lat={latitude}&lon={longitude}"
        key = self._cache_key(latitude, longitude)
        now = datetime.utcnow()
        cached = self._weather_cache.get(key)
        if cached:
            ts, payload = cached
            if (now - ts) < timedelta(seconds=self._poll_min_seconds):
                return payload
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            self._weather_cache[key] = (now, payload)
            return payload
        except requests.exceptions.RequestException as e:
            payload = {"error": str(e), "latitude": latitude, "longitude": longitude}
            self._weather_cache[key] = (now, payload)
            return payload

    def get_weather_icon(self, icon_code: str) -> bytes:
        """
        Fetch weather icon image.
        
        Args:
            icon_code: Icon code (e.g., '04n', '01d')
            
        Returns:
            PNG image bytes
        """
        url = f"{BASE_URL}/weather/icons/{icon_code}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            return None

    def parse_weather(self, weather_data: dict) -> dict:
        """
        Parse and structure weather data for application use.
        Returns raw API data with consistent structure and units noted.
        
        Args:
            weather_data: Raw weather data from API
            
        Returns:
            Structured weather data with units
        """
        if "error" in weather_data:
            return weather_data

        # The external API wraps weather data inside a "weather" key with nested
        # OpenWeatherMap-style structure. Extract the inner data for parsing.
        w = weather_data.get("weather", weather_data)

        # Weather conditions list (e.g. [{"main": "Rain", "description": "moderate rain", "icon": "10d"}])
        conditions_list = w.get("weather", [])
        first_condition = conditions_list[0] if conditions_list else {}

        # Main temperature / atmospheric block
        main_block = w.get("main", {})
        wind_block = w.get("wind", {})
        clouds_block = w.get("clouds", {})
        coord_block = w.get("coord", {})

        icon_code = first_condition.get("icon", "unknown")

        parsed = {
            "location": {
                "latitude": coord_block.get("lat"),
                "longitude": coord_block.get("lon"),
            },
            "temperature": {
                "current": main_block.get("temp"),
                "feels_like": main_block.get("feels_like"),
                "unit": "Celsius",
            },
            "atmospheric_conditions": {
                "humidity": main_block.get("humidity"),
                "humidity_unit": "%",
                "pressure": main_block.get("pressure"),
                "pressure_unit": "hPa",
            },
            "wind": {
                "speed": wind_block.get("speed"),
                "speed_unit": "m/s",
                "direction_degrees": wind_block.get("deg"),
            },
            "visibility": {
                "distance": w.get("visibility"),
                "distance_unit": "meters",
            },
            "cloud_coverage": {
                "percentage": clouds_block.get("all"),
            },
            "conditions": {
                "code": first_condition.get("main"),
                "description": first_condition.get("description"),
            },
            "icon": {
                "code": icon_code,
                "icon_url": f"/api/weather/icon/{icon_code}",
            },
            "timestamp": w.get("dt"),
            "data_age_note": "Data updated every few minutes. Locations binned into areas due to API rate limits.",
        }
        return parsed
