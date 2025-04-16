from datahub import *

import time, datetime
from threading import Thread

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

def backend_synchronizer():
    one_hour_in_seconds = 3600
    while True:
        try:
            cache_backend_channels()
            time.sleep(one_hour_in_seconds)
        except Exception as e:
            print(f"Error while retrieving available channels on backend: {e}")
            time.sleep(30)

def get_recent_channels():
    return shared.recent_channels
