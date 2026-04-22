import sqlite3
from datetime import datetime

from app import StopCache, _align_at_or_after, app, db, transport_service


class DummyStore:
    def __init__(self, db_path, has_connections=True):
        self.db_path = db_path
        self._has_connections = has_connections

    def has_connections(self):
        return self._has_connections


def _seed_stop_cache():
    db.session.query(StopCache).delete()
    db.session.add(
        StopCache(
            atco_code='TEST:STOP1',
            naptan_code='TST1',
            common_name='Common Street Garder',
            indicator='Stop A',
            locality_name='Lancaster',
            latitude=54.05,
            longitude=-2.80,
            stop_type='bus',
            search_text='common street garder stop a lancaster',
        )
    )
    db.session.commit()


def test_stops_in_bounds_returns_visible_stops():
    client = app.test_client()

    with app.app_context():
        _seed_stop_cache()

    response = client.get('/api/stops/in-bounds?minLat=54.0&maxLat=54.1&minLon=-2.9&maxLon=-2.7&limit=100')
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload.get('stops'), list)
    assert any(stop.get('atcoCode') == 'TEST:STOP1' for stop in payload['stops'])


def test_stop_services_returns_no_data_when_index_missing(monkeypatch):
    client = app.test_client()

    with app.app_context():
        _seed_stop_cache()

    monkeypatch.setattr(
        transport_service.route_planner,
        '_connection_index_store',
        DummyStore('/tmp/does-not-matter.sqlite3', has_connections=False),
        raising=False,
    )

    response = client.get('/api/stops/TEST:STOP1/services')
    assert response.status_code == 200

    payload = response.get_json()
    assert payload.get('services') == []


def test_stop_services_returns_upcoming_trip_data(tmp_path, monkeypatch):
    client = app.test_client()

    with app.app_context():
        _seed_stop_cache()

    now = datetime.now()
    now_mins = now.hour * 60 + now.minute
    dep_raw = (now_mins + 8) % (24 * 60)
    arr_mid_raw = (now_mins + 22) % (24 * 60)
    arr_final_raw = (now_mins + 38) % (24 * 60)

    db_path = tmp_path / 'connection_index.sqlite3'
    with sqlite3.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT,
                from_ref TEXT,
                to_ref TEXT,
                dep_raw INTEGER,
                arr_raw INTEGER,
                trip_id TEXT,
                service TEXT,
                mode TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE stops (
                ref TEXT PRIMARY KEY,
                name TEXT,
                lat REAL,
                lon REAL,
                kind TEXT
            )
            """
        )
        con.execute(
            "INSERT INTO stops(ref, name, lat, lon, kind) VALUES (?, ?, ?, ?, ?)",
            ('TEST:STOP1', 'Common Street Garder', 54.05, -2.80, 'bus'),
        )
        con.execute(
            "INSERT INTO stops(ref, name, lat, lon, kind) VALUES (?, ?, ?, ?, ?)",
            ('STOP:MID', 'Lancaster University', 54.01, -2.79, 'bus'),
        )
        con.execute(
            "INSERT INTO stops(ref, name, lat, lon, kind) VALUES (?, ?, ?, ?, ?)",
            ('STOP:FINAL', 'Lancaster City Centre', 54.05, -2.80, 'bus'),
        )
        con.execute(
            """
            INSERT INTO connections(dataset_id, from_ref, to_ref, dep_raw, arr_raw, trip_id, service, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('ds-1', 'TEST:STOP1', 'STOP:MID', dep_raw, arr_mid_raw, 'trip-1', 'Bus 1', 'bus'),
        )
        con.execute(
            """
            INSERT INTO connections(dataset_id, from_ref, to_ref, dep_raw, arr_raw, trip_id, service, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('ds-1', 'STOP:MID', 'STOP:FINAL', arr_mid_raw, arr_final_raw, 'trip-1', 'Bus 1', 'bus'),
        )
        con.commit()

    monkeypatch.setattr(
        transport_service.route_planner,
        '_connection_index_store',
        DummyStore(str(db_path), has_connections=True),
        raising=False,
    )

    response = client.get('/api/stops/TEST:STOP1/services?limit=5&horizonMins=180')
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload.get('services'), list)
    assert payload['services'], 'Expected at least one service for seeded trip'

    first = payload['services'][0]
    assert first.get('service') == 'Bus 1'
    assert first.get('finalDestination') == 'Lancaster City Centre'
    assert first.get('arrivalAtStop')
    assert first.get('arrivalAtFinalDestination')


def test_stop_services_rail_stop_uses_live_departures(monkeypatch):
    client = app.test_client()

    now = datetime.now()
    now_mins = now.hour * 60 + now.minute
    dep = (now_mins + 10) % (24 * 60)
    mid = (now_mins + 30) % (24 * 60)
    final = (now_mins + 65) % (24 * 60)

    dep_str = f"{dep // 60:02d}:{dep % 60:02d}"
    mid_str = f"{mid // 60:02d}:{mid % 60:02d}"
    final_str = f"{final // 60:02d}:{final % 60:02d}"

    with app.app_context():
        _seed_stop_cache()
        db.session.add(
            StopCache(
                atco_code='RAIL:LANX',
                naptan_code='LAN',
                common_name='Lancaster Railway Station',
                indicator='',
                locality_name='Lancaster',
                latitude=54.0488,
                longitude=-2.8013,
                stop_type='rail',
                search_text='lancaster railway station lancaster',
            )
        )
        db.session.commit()

    monkeypatch.setattr(
        transport_service.route_planner,
        '_crs_for_locality',
        lambda name: ['LAN'],
        raising=False,
    )
    monkeypatch.setattr(
        transport_service.route_planner,
        '_find_nearest_stations',
        lambda lat, lon, max_km=2.2, max_results=3: [('LAN', {'name': 'Lancaster'}, 0.1)],
        raising=False,
    )
    monkeypatch.setattr(
        transport_service.route_planner,
        '_fetch_rail_departures_cached',
        lambda crs: {
            'services': [
                {
                    'std': dep_str,
                    'service_type': 'train',
                    'operator': 'Northern',
                    'service_id': 'N123',
                    'destination': {'name': 'Manchester Piccadilly', 'crs': 'MAN'},
                    'calling_points': [
                        {'name': 'Preston', 'crs': 'PRE', 'scheduled': mid_str, 'estimated': mid_str},
                        {'name': 'Manchester Piccadilly', 'crs': 'MAN', 'scheduled': final_str, 'estimated': final_str},
                    ],
                }
            ]
        },
        raising=False,
    )

    response = client.get('/api/stops/RAIL:LANX/services?limit=5&horizonMins=720')
    assert response.status_code == 200

    payload = response.get_json()
    assert isinstance(payload.get('services'), list)
    assert payload['services'], 'Expected rail departures for rail stop'

    first = payload['services'][0]
    assert first.get('mode') == 'train'
    assert first.get('service') == 'Northern'
    assert first.get('finalDestination') == 'Manchester Piccadilly'
    assert first.get('arrivalAtStop')
    assert first.get('arrivalAtFinalDestination')


def test_align_at_or_after_handles_multiple_day_wraps():
    # 00:09 aligned against an absolute baseline late on day 2.
    # Expect value to be pushed to day 3 so it is not before baseline.
    baseline_abs = (2 * 24 * 60) - 10  # 23:50 on day 2
    aligned = _align_at_or_after(9, baseline_abs)
    assert aligned >= baseline_abs
    assert (aligned % (24 * 60)) == 9
