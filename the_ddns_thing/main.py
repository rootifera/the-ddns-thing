import argparse
import os

from .sync_service import SyncWorker
from .web import create_app


def main():
    parser = argparse.ArgumentParser(description="Run the DDNS Thing web UI.")
    parser.add_argument(
        "--host",
        default=os.environ.get("THE_DDNS_THING_HOST", "127.0.0.1"),
        help="Host interface to bind to.",
    )
    parser.add_argument(
        "--port",
        default=int(os.environ.get("THE_DDNS_THING_PORT", "5000")),
        type=int,
        help="Port to listen on.",
    )
    parser.add_argument(
        "--sync-interval",
        default=int(os.environ.get("THE_DDNS_THING_SYNC_INTERVAL", "300")),
        type=int,
        help="Background sync interval in seconds.",
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("THE_DDNS_THING_DATA_DIR"),
        help="Directory used for the SQLite database and secret key.",
    )
    args = parser.parse_args()

    if args.data_dir:
        os.environ["THE_DDNS_THING_DATA_DIR"] = args.data_dir

    app = create_app(sync_interval_seconds=args.sync_interval)
    worker = SyncWorker(app, args.sync_interval)
    worker.start()

    try:
        app.run(host=args.host, port=args.port, debug=False)
    finally:
        worker.stop()


if __name__ == "__main__":
    main()
