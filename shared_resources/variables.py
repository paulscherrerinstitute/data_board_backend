from os import getenv
import redis
from threading import Lock

class SharedVariables:
    def __init__(self):
        self.redis_client = redis.StrictRedis(host=getenv("REDIS_HOST", "redis"), port=6379, db=0, decode_responses=True)
        self.REDIS_IMAGE_STREAM = 'image_stream'

        # Channels to fetch: channel is the key and the last accessed time (secssinceepoch) is the value
        self.active_channels = {'random.1|TEST': 1e20, 'random.2|TEST': 1e20}
        self.active_channels_lock = Lock()

        self.channel_store_time_seconds = 3600
        self.max_channel_frequency = 100

        # Recently accessed channels, doesnt invalidate, unlike active channels
        self.recent_channels = {}
        self.recent_channels_lock = Lock()

        # Channels available on backend and therefore to be used to answer channel searches
        self.available_backend_channels = []
        self.available_backend_channels_lock = Lock()

        self.backend_sync_active = False

shared_variables = SharedVariables()