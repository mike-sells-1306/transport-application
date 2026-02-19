import requests

BASE_URL = "http://transport.scc.lancs.ac.uk"


class WeatherAdapter:
    """Adapter for fetching weather data from the transport API."""

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
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "latitude": latitude, "longitude": longitude}

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

        parsed = {
            "location": {
                "latitude": weather_data.get("lat"),
                "longitude": weather_data.get("lon"),
            },
            "temperature": {
                "current": weather_data.get("temp"),
                "feels_like": weather_data.get("feels_like"),
                "unit": "Celsius",
            },
            "atmospheric_conditions": {
                "humidity": weather_data.get("humidity"),
                "humidity_unit": "%",
                "pressure": weather_data.get("pressure"),
                "pressure_unit": "hPa",
            },
            "wind": {
                "speed": weather_data.get("wind_speed"),
                "speed_unit": "m/s",
                "direction_degrees": weather_data.get("wind_direction"),
            },
            "visibility": {
                "distance": weather_data.get("visibility"),
                "distance_unit": "meters",
            },
            "cloud_coverage": {
                "percentage": weather_data.get("clouds"),
            },
            "conditions": {
                "code": weather_data.get("main"),
                "description": weather_data.get("description"),
            },
            "icon": {
                "code": weather_data.get("icon"),
                "icon_url": f"/api/weather/icon/{weather_data.get('icon', 'unknown')}",
            },
            "timestamp": weather_data.get("dt"),
            "data_age_note": "Data updated every few minutes. Locations binned into areas due to API rate limits.",
        }
        return parsed
