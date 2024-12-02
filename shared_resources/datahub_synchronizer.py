from datahub import *

import time, datetime, psutil
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared_resources.variables import shared_variables as shared

def search_channels(search_text = ".*", avoid_cached_result = False):
    matching_channels = []

    if not avoid_cached_result:
        cached_channel_list = []
        with shared.backend_channels_lock:
            cached_channel_list = shared.backend_channels.copy()
        for channel_tuple in cached_channel_list:
            channel = channel_tuple[1]
            if search_text.lower() in channel.lower():
                matching_channels.append(channel_tuple)
        if not matching_channels:
            # Initiate a resync of available channels in case a new one was added
            Thread(target=cache_backend_channels).start()

    if not matching_channels:
        # While resync is running (effective only from next search onwards), query backend directly.
        with Daqbuf(backend=None, parallel=True) as source:
            result = source.search(search_text)
            if result is not None:
                # Split the output into lines
                lines = result.strip().split('\n')
                # Extract channel names from each line after the header
                channels = [line.split() for line in lines[1:]]
                matching_channels = channels
    return matching_channels


def data_aggregator():
    while True:
        # Create a separate list to use for thread safety with the main thread which adds new channels
        with shared.channel_list_lock:
            local_channel_list = shared.channel_list.copy()

        with ThreadPoolExecutor(max_workers=len(local_channel_list)) as executor:
            futures = [executor.submit(update_channel_data, channel) for channel in local_channel_list]

            # Wait for all futures to complete
            for future in as_completed(futures):
                # Check the result to detect exceptions
                try:
                    future.result()
                except Exception as e:
                    # Will be logged by docker
                    print(f"An error occurred in an update_channel_data multithreaded execution: {e}")
        # Remove all channels that have not been accessed in the past 30 minutes
        current_time = time.time()
        time_thirty_minutes_ago = current_time - (30 * 60)
        to_remove_channels = []

        # Get available system memory
        available_memory = psutil.virtual_memory().available

        # If system memory is low, do a cleanup of unused channels
        if available_memory < 5000000000: # 5 GB
            with shared.channel_list_lock:
                for channel, last_accessed in shared.channel_list.items():
                    if last_accessed < time_thirty_minutes_ago:
                        to_remove_channels.append(channel)

                for channel in to_remove_channels:
                    del shared.channel_list[channel]
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

        # Get the latest entry from
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
            "start": datetime.datetime.utcfromtimestamp(latest_timestamp).isoformat(sep='T', timespec='milliseconds') + 'Z',
            "end": datetime.datetime.utcfromtimestamp(time.time()).isoformat(sep='T', timespec='milliseconds') + 'Z',
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

    # This takes forever, up to a minute.
    backend_channels = search_channels(avoid_cached_result = True)

    with shared.backend_channels_lock:
        shared.backend_channels = [('TEST', 'random.1', None, 'float'), ('TEST', 'random.2', None, 'float')] + backend_channels
    shared.backend_sync_active = False

