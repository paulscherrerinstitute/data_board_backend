import logging
import time

from shared_resources.channel_service import search_channels
from shared_resources.variables import SharedState

logger = logging.getLogger("uvicorn")


def cache_backend_channels(shared: SharedState):
    if shared.backend_sync_active:
        return
    shared.backend_sync_active = True

    backend_channels = search_channels(shared, allow_cached_response=False)

    with shared.available_backend_channels_lock:
        shared.available_backend_channels = backend_channels

    # In case there are no recent channels, take the last ten of the ones just fetched
    if len(shared.recent_channels) == 0:
        with shared.recent_channels_lock:
            shared.recent_channels = backend_channels[-10:]
    shared.backend_sync_active = False


def backend_synchronizer(shared: SharedState):
    one_week_in_seconds = 604_800
    while True:
        try:
            cache_backend_channels(shared)
            time.sleep(one_week_in_seconds)
        except Exception as e:
            logger.error(f"Error in backend_synchronizer: {e}")
            time.sleep(30)
