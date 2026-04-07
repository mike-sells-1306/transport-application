from services.transport_service import TransportService
import os


def main():
    svc = TransportService()
    force = os.getenv('ROUTE_INDEX_FORCE_REBUILD', 'false').lower() == 'true'
    result = svc.route_planner.build_connection_index(force_rebuild=force)
    print(result)


if __name__ == '__main__':
    main()
