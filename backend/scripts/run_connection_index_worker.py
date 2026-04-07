import os
import time
from datetime import datetime

from services.transport_service import TransportService


def main():
    interval_seconds = int(os.getenv('ROUTE_INDEX_INTERVAL_SECONDS', '3600'))
    force_first = os.getenv('ROUTE_INDEX_FORCE_FIRST', 'false').lower() == 'true'

    svc = TransportService()
    planner = svc.route_planner

    first = True
    while True:
        try:
            result = planner.build_connection_index(force_rebuild=(force_first and first))
            print(f"[{datetime.utcnow().isoformat()}] connection index build: {result}")
        except Exception as exc:
            print(f"[{datetime.utcnow().isoformat()}] connection index build failed: {exc}")
        first = False
        time.sleep(max(60, interval_seconds))


if __name__ == '__main__':
    main()
