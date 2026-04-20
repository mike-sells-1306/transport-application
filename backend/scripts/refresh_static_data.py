import argparse
import json

from app import refresh_static_data


def main():
    parser = argparse.ArgumentParser(description="Refresh static transport data (stops + timetable index)")
    parser.add_argument(
        "--force-rebuild-index",
        action="store_true",
        help="Drop and rebuild the connection index before re-populating",
    )
    parser.add_argument(
        "--warm-route-cache",
        action="store_true",
        help="Warm route-planner caches after static refresh",
    )
    args = parser.parse_args()

    result = refresh_static_data(
        force_rebuild_index=args.force_rebuild_index,
        warm_route_cache=args.warm_route_cache,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
