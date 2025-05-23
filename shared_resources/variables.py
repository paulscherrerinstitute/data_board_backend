from os import getenv
from threading import Lock

from pymongo import MongoClient


class SharedState:
    def __init__(self):
        self.mongo_client = MongoClient(
            host=getenv("MONGO_HOST", "localhost"),
            port=int(getenv("MONGO_PORT", 27017)),
        )
        self.mongo_db = self.mongo_client[getenv("MONGO_DB_NAME", "databoard")]
        self.recent_channels = []
        self.recent_channels_lock = Lock()

        # Channels available on backend and therefore to be used to answer channel searches
        self.available_backend_channels = []
        self.available_backend_channels_lock = Lock()

        self.backend_sync_active = False

        self.DATA_API_BASE_URL = getenv("DAQBUF_DEFAULT_URL", "https://data-api.psi.ch/api/4")
