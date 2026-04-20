from adapters.transport_adapters import (
    NPTGAdapter, NaPTANAdapter, BusAdapter, RailAdapter,
    RailDeparturesAdapter, RoutePlannerAdapter,
)
from adapters.weather_adapter import WeatherAdapter
from datetime import datetime, timedelta

class TransportService:
    def __init__(self):
        self.nptg = NPTGAdapter()
        self.naptan = NaPTANAdapter()
        self.bus = BusAdapter()
        self.rail = RailAdapter()
        self.rail_departures = RailDeparturesAdapter()
        self.route_planner = RoutePlannerAdapter()
        self.weather = WeatherAdapter()
        
        # Cache for NaPTAN data (expires after 1 hour)
        self._naptan_cache = {}
        self._naptan_cache_time = {}

    def get_gazetteer(self):
        xml_data = self.nptg.fetch_nptg()
        return self.nptg.parse_nptg(xml_data)

    def get_naptan(self, dataset='lancashire', full=False):
        if full:
            dataset = 'full'
        cache_key = dataset
        
        # Check if cache exists and is still valid (< 1 hour old)
        if cache_key in self._naptan_cache:
            cache_time = self._naptan_cache_time.get(cache_key)
            if cache_time and (datetime.now() - cache_time) < timedelta(hours=1):
                return self._naptan_cache[cache_key]
        
        # Fetch and parse if not cached or expired
        xml_data = self.naptan.fetch_naptan(dataset=dataset, full=full)
        parsed_data = self.naptan.parse_naptan(xml_data)
        
        # Update cache
        self._naptan_cache[cache_key] = parsed_data
        self._naptan_cache_time[cache_key] = datetime.now()
        
        return parsed_data

    def get_bus_timetable(self, bus_code):
        return self.route_planner.get_bus_timetable(bus_code)

    def get_bus_live(self, bus_code):
        return self.bus.fetch_bus_live(bus_code)

    def get_rail_corpus(self):
        return self.rail.fetch_corpus()

    def get_rail_departures(self, crs_code):
        """Get real-time rail departures for a station by CRS code."""
        return self.rail_departures.fetch_departures(crs_code)

    def get_routes(self, from_name, to_name, date=None, time=None,
                   depart_time=None,
                   from_lat=None, from_lon=None, to_lat=None, to_lon=None,
                   from_stop_code=None, to_stop_code=None,
                   sort_by='soonest_arrival'):
        """Plan routes between two locations using real API data.

        Uses SCC rail departure boards and SCC bus timetable datasets
        (TransXChange) to build real multi-modal route options.
        """
        routes = self.route_planner.plan_routes(
            from_name, to_name,
            from_lat=from_lat, from_lon=from_lon,
            to_lat=to_lat, to_lon=to_lon,
            from_stop_code=from_stop_code,
            to_stop_code=to_stop_code,
            depart_time=depart_time,
            sort_by=sort_by,
        )
        return {
            "routes": routes,
            "metrics": self.route_planner.get_last_processing_metrics(),
        }

    def get_route_processing_metrics(self):
        return self.route_planner.get_last_processing_metrics()

    def get_weather(self, latitude: float, longitude: float):
        raw_data = self.weather.fetch_weather(latitude, longitude)
        return self.weather.parse_weather(raw_data)
