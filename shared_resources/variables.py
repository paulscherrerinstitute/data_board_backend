from os import getenv
import redis
from threading import Lock

class SharedVariables:
    def __init__(self):
        self.redis_client = redis.StrictRedis(host=getenv("REDIS_HOST", "redis"), port=getenv("REDIS_PORT", 6379), db=0, decode_responses=True)

        self.recent_channels = []
        self.recent_channels_lock = Lock()

        # Channels available on backend and therefore to be used to answer channel searches
        self.available_backend_channels = []
        self.available_backend_channels_lock = Lock()

        self.backend_sync_active = False

shared_variables = SharedVariables()