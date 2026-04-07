import sqlite3
from pathlib import Path


class ConnectionIndexStore:
    """Persistent offline index for timetable connections and transfer footpaths."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.db_path), timeout=30)
        con.execute("PRAGMA busy_timeout=30000")
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        con.execute("PRAGMA synchronous=NORMAL")
        return con

    def init_schema(self):
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    stamp TEXT,
                    operator_name TEXT
                );

                CREATE TABLE IF NOT EXISTS stops (
                    ref TEXT PRIMARY KEY,
                    name TEXT,
                    lat REAL,
                    lon REAL,
                    kind TEXT
                );

                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id TEXT,
                    from_ref TEXT,
                    to_ref TEXT,
                    dep_raw INTEGER,
                    arr_raw INTEGER,
                    trip_id TEXT,
                    service TEXT,
                    mode TEXT
                );

                CREATE TABLE IF NOT EXISTS footpaths (
                    from_ref TEXT,
                    to_ref TEXT,
                    walk_mins INTEGER,
                    distance_m INTEGER,
                    PRIMARY KEY (from_ref, to_ref)
                );

                CREATE INDEX IF NOT EXISTS idx_connections_from_dep
                    ON connections(from_ref, dep_raw);
                CREATE INDEX IF NOT EXISTS idx_connections_to
                    ON connections(to_ref);
                CREATE INDEX IF NOT EXISTS idx_stops_lat_lon
                    ON stops(lat, lon);
                """
            )

    def clear(self):
        with self._connect() as con:
            con.executescript(
                """
                DELETE FROM connections;
                DELETE FROM footpaths;
                DELETE FROM stops;
                DELETE FROM datasets;
                """
            )

    def upsert_dataset(self, dataset_id: str, stamp: str, operator_name: str):
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO datasets(dataset_id, stamp, operator_name)
                VALUES (?, ?, ?)
                ON CONFLICT(dataset_id) DO UPDATE SET
                    stamp=excluded.stamp,
                    operator_name=excluded.operator_name
                """,
                (dataset_id, stamp or '', operator_name or ''),
            )

    def replace_dataset_connections(self, dataset_id: str, stop_meta: dict, connections: list):
        with self._connect() as con:
            con.execute("DELETE FROM connections WHERE dataset_id = ?", (dataset_id,))

            stop_rows = [
                (ref, m.get('name', ref), float(m.get('lat', 0.0)), float(m.get('lon', 0.0)), m.get('kind', 'bus'))
                for ref, m in stop_meta.items()
            ]
            con.executemany(
                """
                INSERT INTO stops(ref, name, lat, lon, kind)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ref) DO UPDATE SET
                    name=excluded.name,
                    lat=excluded.lat,
                    lon=excluded.lon,
                    kind=excluded.kind
                """,
                stop_rows,
            )

            conn_rows = [
                (
                    dataset_id,
                    c.get('from_ref', ''),
                    c.get('to_ref', ''),
                    int(c.get('dep_raw', 0)),
                    int(c.get('arr_raw', 0)),
                    c.get('trip_id', ''),
                    c.get('service', ''),
                    c.get('mode', 'bus'),
                )
                for c in connections
                if c.get('from_ref') and c.get('to_ref')
            ]
            con.executemany(
                """
                INSERT INTO connections(dataset_id, from_ref, to_ref, dep_raw, arr_raw, trip_id, service, mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                conn_rows,
            )

    def rebuild_footpaths(self, max_walk_km=0.6, walk_speed_m_per_min=80, walk_factor=1.35):
        with self._connect() as con:
            rows = con.execute("SELECT ref, lat, lon, kind FROM stops").fetchall()
            con.execute("DELETE FROM footpaths")

            # lightweight grid bucketing
            cell = 0.01
            buckets = {}
            for ref, lat, lon, kind in rows:
                key = (int(lat / cell), int(lon / cell))
                buckets.setdefault(key, []).append((ref, lat, lon, kind))

            def hav(lat1, lon1, lat2, lon2):
                import math
                R = 6371.0
                la1, lo1, la2, lo2 = map(math.radians, [lat1, lon1, lat2, lon2])
                dlat = la2 - la1
                dlon = lo2 - lo1
                a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
                return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

            inserts = []
            for (gx, gy), items in buckets.items():
                neigh = []
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        neigh.extend(buckets.get((gx + dx, gy + dy), []))
                for ref_a, la, loa, kind_a in items:
                    for ref_b, lb, lob, kind_b in neigh:
                        if ref_a == ref_b:
                            continue
                        if kind_a == kind_b:
                            continue
                        d_km = hav(la, loa, lb, lob)
                        if d_km > max_walk_km:
                            continue
                        dist_m = int(d_km * 1000 * walk_factor)
                        walk_mins = max(1, int(dist_m / walk_speed_m_per_min))
                        inserts.append((ref_a, ref_b, walk_mins, dist_m))

            con.executemany(
                """
                INSERT OR REPLACE INTO footpaths(from_ref, to_ref, walk_mins, distance_m)
                VALUES (?, ?, ?, ?)
                """,
                inserts,
            )

    def has_connections(self) -> bool:
        with self._connect() as con:
            row = con.execute("SELECT COUNT(1) FROM connections").fetchone()
            return bool(row and row[0] > 0)

    def get_dataset_connections_and_stops(self, dataset_ids):
        """Load connections + referenced stop metadata for selected datasets."""
        dataset_ids = [d for d in (dataset_ids or []) if d]
        if not dataset_ids:
            return [], {}

        placeholders = ",".join(["?"] * len(dataset_ids))
        with self._connect() as con:
            conn_rows = con.execute(
                f"""
                SELECT from_ref, to_ref, dep_raw, arr_raw, trip_id, service, mode
                FROM connections
                WHERE dataset_id IN ({placeholders})
                """,
                dataset_ids,
            ).fetchall()

            refs = set()
            for r in conn_rows:
                refs.add(r[0])
                refs.add(r[1])

            stop_meta = {}
            if refs:
                rlist = list(refs)
                ph2 = ",".join(["?"] * len(rlist))
                stop_rows = con.execute(
                    f"""
                    SELECT ref, name, lat, lon, kind
                    FROM stops
                    WHERE ref IN ({ph2})
                    """,
                    rlist,
                ).fetchall()
                for ref, name, lat, lon, kind in stop_rows:
                    stop_meta[ref] = {
                        'name': name,
                        'lat': float(lat),
                        'lon': float(lon),
                        'kind': kind,
                    }

        connections = [
            {
                'from_ref': r[0],
                'to_ref': r[1],
                'dep_raw': int(r[2]),
                'arr_raw': int(r[3]),
                'trip_id': r[4],
                'service': r[5],
                'mode': r[6],
            }
            for r in conn_rows
        ]
        return connections, stop_meta

    def get_footpaths(self):
        with self._connect() as con:
            rows = con.execute(
                "SELECT from_ref, to_ref, walk_mins, distance_m FROM footpaths"
            ).fetchall()
        return [
            {
                'from_ref': r[0],
                'to_ref': r[1],
                'walk_mins': int(r[2]),
                'distance_m': int(r[3]),
            }
            for r in rows
        ]
