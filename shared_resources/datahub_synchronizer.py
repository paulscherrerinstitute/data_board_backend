from datahub import *

import time, datetime, psutil
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared_resources.variables import shared_variables as shared

def search_channels(search_text = ".*", allow_cached_response = True):
    matching_channels = []
    if allow_cached_response:
        cached_channel_list = []
        with shared.available_backend_channels_lock:
            cached_channel_list = shared.available_backend_channels.copy()
        for channel in cached_channel_list:
            if search_text.lower() in channel["name"]:
                matching_channels.append(channel)
        if not matching_channels:
            # Initiate a resync of available channels in case a new one was added
            Thread(target=cache_backend_channels).start()

    if not matching_channels:
        # While resync is running (effective only from next search onwards), query backend directly.
        with Daqbuf(backend=None, parallel=True) as source:
            # Verboses gets us the plain response without any formatting, which would only slow everything down.
            source.verbose = True
            result = source.search(search_text)
            if result is not None:
                matching_channels = result["channels"]
    return matching_channels

def get_curve_data(channel_name: str, begin_time: int, end_time: int, backend: str, num_bins: int, useEventsIfBinCountTooLarge: bool, removeEmptyBins: bool, entry: dict):
    if entry:
        with shared.recent_channels_lock:
            if entry in shared.recent_channels:
                shared.recent_channels.remove(entry)
            shared.recent_channels.insert(0, entry)
            while len(shared.recent_channels) > 10:
                shared.recent_channels.pop()

    query = {
        "channels": [channel_name],
        "start": datetime.datetime.fromtimestamp(begin_time / 1000, timezone.utc).isoformat(sep=' ', timespec='milliseconds'),
        "end": datetime.datetime.fromtimestamp(end_time / 1000, timezone.utc).isoformat(sep=' ', timespec='milliseconds')
    }

    if num_bins > 0:
        query["bins"] = num_bins

    curve = {}
    try:
        with Daqbuf(backend=backend) as source:
            table = Table()
            source.add_listener(table)
            source.request(query, background=True)
            source.join()
            source.verbose = True
            
            dataframe = table.as_dataframe()
            raw = False
            if dataframe is not None and not dataframe.empty:
                data = dataframe.to_dict(orient='index')
                items = data.items()
                if useEventsIfBinCountTooLarge:
                    actualData = 0
                    for _, entry in items:
                        try:
                            actualData += entry[channel_name + " count"]
                        except KeyError and ValueError and TypeError:
                            continue
                    if not actualData == 0 and actualData < num_bins:
                        raw = True
                        source.remove_listeners()
                        table = Table()
                        source.add_listener(table)
                        query.pop("bins")
                        source.request(query, background=True)
                        source.join()
                        dataframe = table.as_dataframe()
                        if dataframe is not None and not dataframe.empty:
                            data = dataframe.to_dict(orient='index')
                            items = data.items()
                for timestamp, entry in items:
                    if (removeEmptyBins and not raw and entry[channel_name + " count"] == 0):
                        continue
                    if (type(entry[channel_name]) == Enum):
                        curve.setdefault(channel_name, {})[timestamp] = entry[channel_name].id
                    else:
                        curve.setdefault(channel_name, {})[timestamp] = entry[channel_name]
                    if not raw:
                        curve.setdefault(channel_name + "_min", {})[timestamp] = entry[channel_name + " min"]
                        curve.setdefault(channel_name + "_max", {})[timestamp] = entry[channel_name + " max"]
            else:
                curve[channel_name] = {}
    except Exception as e:
        print(e)
        raise RuntimeError
    result = {"curve": curve}
    result["raw"] = raw
    return result

def data_aggregator():
    while True:
        # Create a separate list to use for thread safety with the main thread which adds new channels
        with shared.active_channels_lock:
            local_channel_list = shared.active_channels.copy()

        with ThreadPoolExecutor(max_workers=len(local_channel_list)) as executor:
            futures = [executor.submit(update_channel_data, channel) for channel in local_channel_list]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"An error occurred in an update_channel_data multithreaded execution: {e}")

        # Remove all channels that have not been accessed in the past 30 minutes
        current_time = time.time()
        time_thirty_minutes_ago = current_time - (30 * 60)
        to_remove_channels = []

        # Get available system memory
        available_memory = psutil.virtual_memory().available

        # If system memory is low, do a cleanup of unused channels
        if available_memory < 5000000000: # 5 GB
            with shared.active_channels_lock:
                for channel, last_accessed in shared.active_channels.items():
                    if last_accessed < time_thirty_minutes_ago:
                        to_remove_channels.append(channel)

                for channel in to_remove_channels:
                    del shared.active_channels[channel]
                    redis_key = f"curve_stream:{channel}"
                    if shared.redis_client.exists(redis_key):
                        shared.redis_client.delete(redis_key)

        time.sleep(1)

update_lock = Lock()
def update_channel_data(channel):
    with update_lock:
        # Testing channels, do not exist on datahub
        if channel in ['random.1|TEST', 'random.2|TEST']:
            return

        # Get the latest entry from redis
        redis_key = f"curve_stream:{channel}"
        latest_entry = {}
        if shared.redis_client.exists(redis_key):
            latest_entry = shared.redis_client.xrevrange(redis_key, max='+', min='-', count=1)
        # Determine the start time based on the latest entry's timestamp, or use a default if no data is present
        if latest_entry:
            latest_timestamp = float(latest_entry[0][1]['timestamp'])
        else:
            latest_timestamp = time.time() - shared.channel_store_time_seconds  # Default to start time if no data in Redis

        channel_name, backend_name = channel.split("|")
        query = {
            "channels": [channel_name],
            # Get the datetimes in local time with utc specifier to feed api correctly
            "start": datetime.datetime.fromtimestamp(latest_timestamp, datetime.timezone.utc).isoformat(sep='T', timespec='milliseconds') + 'Z',
            "end": datetime.datetime.fromtimestamp(time.time(), datetime.timezone.utc).isoformat(sep='T', timespec='milliseconds') + 'Z',
        }

        try:
            with Daqbuf(backend=backend_name, cbor=True) as source:
                table = Table()
                source.add_listener(table)
                source.request(query)
                dataframe = table.as_dataframe()
                # Convert DataFrame to a dictionry with timestamp as key and value as channel data
                data = {}
                if dataframe is not None:
                    data = {timestamp: entry[channel_name] for timestamp, entry in dataframe.to_dict(orient='index').items()}

                # Calculate the max length for the Redis stream
                max_calculated_len = shared.channel_store_time_seconds * shared.max_channel_frequency

                # Append the new data to Redis
                latest_timestamp = latest_timestamp * 1e9
                for timestamp, value in data.items():
                    if timestamp >= latest_timestamp:
                        latest_timestamp = timestamp
                        shared.redis_client.xadd(
                            redis_key,
                            {
                                'timestamp': timestamp / 1e9,
                                'value': value
                            },
                            #maxlen = max_calculated_len, --> No upper limit, due to automatic cleanup 
                            approximate=False
                        )

                if not data and not shared.redis_client.exists(redis_key):
                    entry_id = shared.redis_client.xadd(
                        redis_key,
                        {
                            'timestamp': "NaN",
                            'value': "NaN"
                        },
                        maxlen=max_calculated_len,
                        approximate=False
                    )

                    # Remove the newly created entry to keep the stream but not the data
                    shared.redis_client.xdel(redis_key, entry_id)

        except Exception as e:
            print(f"Error while fetching or storing data: {e}")

def backend_synchronizer():
    one_hour_in_seconds = 3600
    while True:
        try:
            cache_backend_channels()
            time.sleep(one_hour_in_seconds)
        except Exception as e:
            print(f"Error while retrieving available channels on backend: {e}")
            time.sleep(30)

def cache_backend_channels():
    if shared.backend_sync_active:
        return
    shared.backend_sync_active = True

    backend_channels = search_channels(allow_cached_response=False)

    with shared.available_backend_channels_lock:
        shared.available_backend_channels = [{'backend': 'TEST', 'name': 'random.1', 'seriesId': None, 'source': None, 'type': 'float', 'shape': [], 'unit': None, 'description': 'a test channel'}] + backend_channels

    # In case there are no recent channels, take the last ten of the ones just fetched
    if len(shared.recent_channels) == 0:
        with shared.recent_channels_lock:
            shared.recent_channels = backend_channels[-10:]
    shared.backend_sync_active = False

def get_recent_channels():
    return shared.recent_channels
