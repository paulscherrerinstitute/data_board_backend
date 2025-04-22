from os import getenv
from threading import Lock
from pymongo import MongoClient

class SharedVariables:
    def __init__(self):
        mongo_host = getenv("MONGO_HOST", "localhost")
        mongo_port = int(getenv("MONGO_PORT", 27017))
        mongo_db_name = getenv("MONGO_DB_NAME", "databoard")

        self.mongo_client = MongoClient(host=mongo_host, port=mongo_port)
        self.mongo_db = self.mongo_client[mongo_db_name]

        self.recent_channels = []
        self.recent_channels_lock = Lock()

        # Channels available on backend and therefore to be used to answer channel searches
        self.available_backend_channels = []
        self.available_backend_channels_lock = Lock()

        self.backend_sync_active = False

shared_variables = SharedVariables()