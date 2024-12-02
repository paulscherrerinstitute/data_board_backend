import redis
from collections import deque
from threading import Lock

class SharedVariables:
    def __init__(self):
        # Initialize Redis client
        self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)
        self.REDIS_IMAGE_STREAM = 'image_stream'

        # Initialize a dictionary of channels to fetch: channel is the key and the last accessed time (secssinceepoch) is the value
        self.channel_list = {'random.1|TEST': 1e20, 'random.2|TEST': 1e20}
        # Lock used to delete unused channels while making sure no others are added
        self.channel_list_lock = Lock()
        # How many seconds of channel data should be
        self.channel_store_time_seconds = 3600
        self.max_channel_frequency = 100

        # List to store channels available on backend & corresponding lock
        self.backend_channels = []
        self.backend_channels_lock = Lock()

        # Boolean to ensure only on backend sync is happening at a time
        self.backend_sync_active = False

shared_variables = SharedVariables()