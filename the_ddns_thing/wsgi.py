import os

from .sync_service import SyncWorker
from .web import create_app

SYNC_INTERVAL_SECONDS = int(os.environ.get("THE_DDNS_THING_SYNC_INTERVAL", "300"))

app = create_app(sync_interval_seconds=SYNC_INTERVAL_SECONDS)
worker = SyncWorker(app, SYNC_INTERVAL_SECONDS)
worker.start()
