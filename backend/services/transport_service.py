from adapters.transport_adapters import NPTGAdapter, NaPTANAdapter, BusAdapter, RailAdapter, JourneyPlannerAdapter
from adapters.weather_adapter import WeatherAdapter
from datetime import datetime, timedelta

class TransportService:
    def __init__(self):
        self.nptg = NPTGAdapter()
        self.naptan = NaPTANAdapter()
        self.bus = BusAdapter()
        self.rail = RailAdapter()
        self.journey_planner = JourneyPlannerAdapter()
        self.weather = WeatherAdapter()
        
        # Cache for NaPTAN data (expires after 1 hour)
        self._naptan_cache = {}
        self._naptan_cache_time = {}

    def get_gazetteer(self):
        xml_data = self.nptg.fetch_nptg()
        return self.nptg.parse_nptg(xml_data)

    def get_naptan(self, full=False):
        cache_key = 'full' if full else 'normal'
        
        # Check if cache exists and is still valid (< 1 hour old)
        if cache_key in self._naptan_cache:
            cache_time = self._naptan_cache_time.get(cache_key)
            if cache_time and (datetime.now() - cache_time) < timedelta(hours=1):
                return self._naptan_cache[cache_key]
        
        # Fetch and parse if not cached or expired
        xml_data = self.naptan.fetch_naptan(full=full)
        parsed_data = self.naptan.parse_naptan(xml_data)
        
        # Update cache
        self._naptan_cache[cache_key] = parsed_data
        self._naptan_cache_time[cache_key] = datetime.now()
        
        return parsed_data

    def get_bus_timetable(self, bus_code):
        return self.bus.fetch_bus_timetable(bus_code)

    def get_bus_live(self, bus_code):
        return self.bus.fetch_bus_live(bus_code)

    def get_rail_corpus(self):
        return self.rail.fetch_corpus()

    def get_routes(self, from_name, to_name, date=None, time=None):
        """Get routes between two stops from the journey planner API"""
        return self.journey_planner.fetch_routes(from_name, to_name, date, time)

    def get_weather(self, latitude: float, longitude: float):
        raw_data = self.weather.fetch_weather(latitude, longitude)
        return self.weather.parse_weather(raw_data)
