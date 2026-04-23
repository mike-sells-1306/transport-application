from adapters.transport_adapters import (
    NPTGAdapter, NaPTANAdapter, BusAdapter, RailAdapter,
    RailDeparturesAdapter, RoutePlannerAdapter,
)
from adapters.weather_adapter import WeatherAdapter
from datetime import datetime, timedelta, timezone
import os

from routing.aggregator import RouteAggregator
from routing.models import RoutingQuery
from routing.providers.active_travel_provider import ActiveTravelProvider
from routing.providers.scc_provider import SCCRoutingProvider
from routing.providers.transit_provider import ExternalTransitProvider

class TransportService:
    def __init__(self):
        self.nptg = NPTGAdapter()
        self.naptan = NaPTANAdapter()
        self.bus = BusAdapter()
        self.rail = RailAdapter()
        self.rail_departures = RailDeparturesAdapter()
        self.route_planner = RoutePlannerAdapter()
        self.weather = WeatherAdapter()
        self.route_aggregator = RouteAggregator(
            providers=[
                SCCRoutingProvider(self.route_planner),
                ExternalTransitProvider(
                    enabled=os.getenv("ENABLE_TRANSIT_ENGINE_PROVIDER", "false").strip().lower() == "true"
                ),
                ActiveTravelProvider(
                    enabled=os.getenv("ENABLE_ACTIVE_TRAVEL_PROVIDER", "false").strip().lower() == "true"
                ),
            ],
            enable_cache=os.getenv("ENABLE_ROUTE_AGGREGATOR_CACHE", "true").strip().lower() == "true",
            cache_ttl_seconds=int(os.getenv("ROUTE_AGGREGATOR_CACHE_TTL_SECONDS", "90")),
            cache_time_bucket_mins=int(os.getenv("ROUTE_AGGREGATOR_CACHE_TIME_BUCKET_MINS", "5")),
        )
        
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

    def get_routes_v2(self, from_name, to_name, from_lat, from_lon, to_lat, to_lon,
                      from_stop_code=None, to_stop_code=None, depart_time=None,
                      sort_by='soonest_arrival', modes=None, prefer_reliability=False,
                      max_walk_meters=None):
        query = RoutingQuery(
            from_name=from_name,
            to_name=to_name,
            from_lat=from_lat,
            from_lon=from_lon,
            to_lat=to_lat,
            to_lon=to_lon,
            from_stop_code=from_stop_code,
            to_stop_code=to_stop_code,
            depart_time=depart_time,
            sort_by=sort_by,
            modes=list(modes or []),
            prefer_reliability=bool(prefer_reliability),
            max_walk_meters=max_walk_meters,
        )
        return self.route_aggregator.search(query)

    def get_weather(self, latitude: float, longitude: float):
        raw_data = self.weather.fetch_weather(latitude, longitude)
        return self.weather.parse_weather(raw_data)

    def get_transport_notifications(self, limit: int = 30):
        """Return a live notification feed derived from SCC transport data.

        The feed combines rail departure board delay notices with bus live
        journey-time updates. Results are sorted by severity and truncated to
        *limit* items.
        """

        def _hhmm_to_minutes(value):
            value = str(value or '').strip()
            if not value or ':' not in value:
                return None
            try:
                hour_str, minute_str = value.split(':', 1)
                return int(hour_str) * 60 + int(minute_str)
            except Exception:
                return None

        def _fmt_minutes(total_minutes):
            total_minutes = int(total_minutes or 0)
            return f"{(total_minutes // 60) % 24:02d}:{total_minutes % 60:02d}"

        def _iso_now(dt_value):
            return dt_value.replace(microsecond=0).isoformat().replace('+00:00', 'Z')

        def _format_area(start, end):
            start = str(start or '').strip()
            end = str(end or '').strip()
            if start and end and start != end:
                return f"{start} → {end}"
            return start or end or 'Unknown area'

        def _build_service_stops(stops, segment_mins, depart_mins, max_count=None):
            service_stops = []
            if not stops:
                return service_stops

            limit = len(stops) if max_count is None else min(len(stops), max(0, int(max_count)))
            elapsed = 0
            for idx, stop in enumerate(stops[:limit]):
                if idx > 0 and segment_mins:
                    segment_index = min(idx - 1, len(segment_mins) - 1)
                    elapsed += int(segment_mins[segment_index] or 0)
                service_stops.append({
                    'name': str(stop.get('name') or '').strip(),
                    'estimated': _fmt_minutes(depart_mins + elapsed),
                })
            return service_stops

        now = datetime.now(timezone.utc)
        now_iso = _iso_now(now)
        expires_iso = _iso_now(now + timedelta(hours=2))
        updates = []

        # Rail delays from departure boards.
        for crs_code, station in self.route_planner.STATIONS.items():
            try:
                departures = self.route_planner._fetch_rail_departures_cached(crs_code)
            except Exception:
                continue

            station_name = station.get('name') or crs_code
            for service in departures.get('services', []):
                std = str(service.get('std') or '').strip()
                etd = str(service.get('etd') or '').strip()
                std_mins = _hhmm_to_minutes(std)
                etd_mins = _hhmm_to_minutes(etd)

                delay_mins = None
                status_text = ''
                if std_mins is not None and etd_mins is not None:
                    delay_mins = etd_mins - std_mins
                    if delay_mins < -12 * 60:
                        delay_mins += 24 * 60
                    delay_mins = max(0, delay_mins)
                    if delay_mins == 0:
                        continue
                    if delay_mins > 12 * 60:
                        continue
                    status_text = f"Delayed by {delay_mins} min"
                elif etd and etd.lower() not in {'on time', 'due', 'now'}:
                    status_text = etd
                else:
                    continue

                origin = (service.get('origin') or {}).get('name') or station_name
                destination = (service.get('destination') or {}).get('name') or ''
                operator = service.get('operator') or service.get('operator_code') or 'Rail'
                platform = str(service.get('platform') or '').strip()
                calling_points = service.get('calling_points') or []
                next_stop = calling_points[0] if calling_points else {}
                detail_points = [
                    {
                        'name': point.get('name') or '',
                        'scheduled': point.get('scheduled') or '',
                        'estimated': point.get('estimated') or '',
                    }
                    for point in calling_points[:4]
                    if point
                ]

                updates.append({
                    'notificationID': f"rail-{crs_code}-{service.get('service_id') or std or etd}",
                    'area': station_name,
                    'category': 'delay',
                    'transportType': 'rail',
                    'title': f"{origin} → {destination}".strip(' →'),
                    'summary': f"{operator} · {status_text}".strip(' ·'),
                    'message': f"{operator} service {std or 'unknown'} → {etd or 'unknown'} at {station_name}",
                    'issuedAt': now_iso,
                    'expiresAt': expires_iso,
                    'details': {
                        'station': station_name,
                        'origin': origin,
                        'destination': destination,
                        'nextStop': next_stop.get('name') or destination,
                        'serviceId': service.get('service_id') or '',
                        'serviceType': service.get('service_type') or 'rail',
                        'operator': operator,
                        'platform': platform,
                        'scheduledDeparture': std,
                        'estimatedDeparture': etd,
                        'delayMinutes': delay_mins,
                        'serviceStops': detail_points,
                        'callingPoints': detail_points,
                        'source': 'SCC rail departures',
                    },
                    'priority': 100 + min(int(delay_mins or 0), 60),
                })

        # Bus live journey-time updates.
        try:
            current_mins = now.hour * 60 + now.minute
        except Exception:
            current_mins = 0

        for service in getattr(self.route_planner, 'BUS_SERVICES', []):
            live_origin_deps, live_total_duration = self.route_planner._live_departures_for_service(
                service.get('service', ''),
                current_mins,
            )
            if live_total_duration is None:
                continue

            expected_total_duration = sum(self.route_planner._estimate_segment_mins(service))
            duration_delta = int(live_total_duration - expected_total_duration)
            stops = service.get('stops') or []
            start_stop = (stops[0].get('name') if stops else '') or service.get('service', '')
            end_stop = (stops[-1].get('name') if len(stops) > 1 else '') or start_stop
            area = _format_area(start_stop, end_stop)
            operator = service.get('operator') or 'Bus'
            route_label = service.get('service') or operator
            upcoming_departures = [_fmt_minutes(dep) for dep in live_origin_deps[:3]]
            segment_mins = self.route_planner._estimate_segment_mins(service)
            base_depart_mins = live_origin_deps[0] if live_origin_deps else current_mins
            service_stops = _build_service_stops(stops, segment_mins, base_depart_mins)
            next_stop = service_stops[1]['name'] if len(service_stops) > 1 else end_stop

            is_delay = duration_delta > 4
            category = 'delay' if is_delay else 'travel-info'
            delay_text = f"{duration_delta} min delay" if is_delay else f"live journey {live_total_duration} min"

            updates.append({
                'notificationID': f"bus-{route_label.replace(' ', '-').lower()}-{area.replace(' ', '-').lower()}",
                'area': area,
                'category': category,
                'transportType': 'bus',
                'title': f"{start_stop} → {end_stop}",
                'summary': f"{operator} · {delay_text}",
                'message': f"{operator} live feed reports {live_total_duration} minutes for {route_label}.",
                'issuedAt': now_iso,
                'expiresAt': expires_iso,
                'details': {
                    'service': route_label,
                    'operator': operator,
                    'area': area,
                    'origin': start_stop,
                    'destination': end_stop,
                    'nextStop': next_stop,
                    'expectedDurationMinutes': expected_total_duration,
                    'liveDurationMinutes': live_total_duration,
                    'delayMinutes': duration_delta if duration_delta > 4 else None,
                    'upcomingDepartures': upcoming_departures,
                    'serviceStops': service_stops,
                    'source': 'SCC live bus feed',
                },
                'priority': 70 + min(max(duration_delta, 0), 40),
            })

        updates.sort(
            key=lambda item: (
                -int(item.get('priority', 0) or 0),
                item.get('issuedAt', ''),
                item.get('notificationID', ''),
            )
        )
        return updates[:max(0, int(limit))]
