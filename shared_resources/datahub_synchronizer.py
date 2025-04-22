from datahub import *

import time, datetime
from threading import Thread

from shared_resources.variables import shared_variables as shared

import logging
logger = logging.getLogger("uvicorn")

def search_channels(search_text = ".*", allow_cached_response = True):
    matching_channels = []
    cache_miss = False
    if allow_cached_response:
        with shared.available_backend_channels_lock:
            cached_channel_list = list(shared.available_backend_channels)
        for channel in cached_channel_list:
            if search_text.lower() in channel["name"]:
                matching_channels.append({
                    "backend": str(channel.get("backend", "")),
                    "name": str(channel.get("name", "")),
                    "seriesId": str(channel.get("seriesId", "")),
                    "source": str(channel.get("source", "")),
                    "type": str(channel.get("type", "")),
                    "shape": channel.get("shape", ""), # May be []
                    "unit": str(channel.get("unit", "")),
                    "description": str(channel.get("description", ""))
                })
        if not matching_channels:
            cache_miss = True

    if not matching_channels:
        # While resync is running (effective only from next search onwards), query backend directly.
        with Daqbuf(backend=None, parallel=True) as source:
            # Verboses gets us the plain response without any formatting, which would only slow everything down.
            source.verbose = True
            result = source.search(search_text)
            if result is not None:
                matching_channels = [
                    {
                        "backend": str(channel.get("backend", "")),
                        "name": str(channel.get("name", "")),
                        "seriesId": str(channel.get("seriesId", "")),
                        "source": str(channel.get("source", "")),
                        "type": str(channel.get("type", "")),
                        "shape": channel.get("shape", ""), # May be []
                        "unit": str(channel.get("unit", "")),
                        "description": str(channel.get("description", ""))
                    }
                    for channel in result.get("channels", [])
                ]

    # Initiate a resync of available channels in case a new one was added
    if matching_channels and cache_miss:
        Thread(target=cache_backend_channels).start()

    return matching_channels

def transform_curve_data(daqbuf_data, channel_name, remove_empty_bins=False, raw=True):
    count_name = f"{channel_name} count"
    min_name   = f"{channel_name} min"
    max_name   = f"{channel_name} max"

    # prepare output containers
    curve = {channel_name: {}}
    curve[f"{channel_name}_meta"] = {"raw": raw}
    if min_name in daqbuf_data:
        curve[f"{channel_name}_min"] = {}
    if max_name in daqbuf_data:
        curve[f"{channel_name}_max"] = {}

    # build timestamp → record maps once
    count_map = {r["timestamp"]: r for r in daqbuf_data.get(count_name, [])}
    min_map   = {r["timestamp"]: r for r in daqbuf_data.get(min_name, [])} if min_name in daqbuf_data else {}
    max_map   = {r["timestamp"]: r for r in daqbuf_data.get(max_name, [])} if max_name in daqbuf_data else {}

    for record in daqbuf_data.get(channel_name, []):
        timestamp = record["timestamp"]

        # skip empty bins if specified
        if remove_empty_bins and not raw:
            count = count_map.get(timestamp)
            if count and int(count[count_name]) == 0:
                continue

        # value
        value = record[channel_name]
        curve[channel_name][timestamp] = value.id if isinstance(value, datahub.Enum) else float(value)

        # min
        if timestamp in min_map:
            curve[f"{channel_name}_min"][timestamp] = float(min_map[timestamp][min_name])

        # max
        if timestamp in max_map:
            curve[f"{channel_name}_max"][timestamp] = float(max_map[timestamp][max_name])

        # Metainformation
        count = count_map.get(timestamp)
        if count or raw:
            meta = curve[f"{channel_name}_meta"].setdefault(timestamp, {})
            if count:
                meta["count"] = int(count[count_name])
            if raw:
                meta["pulseId"] = record.get("pulse_id")

    return {"curve": curve}


def get_curve_data(channel_name: str, begin_time: int, end_time: int, backend: str, num_bins: int, useEventsIfBinCountTooLarge: bool, removeEmptyBins: bool, channel_entry: dict):
    if channel_entry:
        with shared.recent_channels_lock:
            if channel_entry in shared.recent_channels:
                shared.recent_channels.remove(channel_entry)
            shared.recent_channels.insert(0, channel_entry)
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
            source.remove_listeners()
            source.verbose = True
            daqbuf_data = table.data

            raw = False
            if daqbuf_data is not None and len(daqbuf_data) > 0:
                if useEventsIfBinCountTooLarge and channel_name + " count" in daqbuf_data:
                    actualData = 0
                    for entry in daqbuf_data[channel_name + " count"]:
                        try:
                            actualData += int(entry[channel_name + " count"])
                        except (KeyError, ValueError, TypeError):
                            continue
                    if not actualData == 0 and actualData < num_bins:
                        raw = True

                        table.clear()
                        source.add_listener(table)
                        query.pop("bins")
                        source.request(query, background=True)
                        source.join()
                        source.remove_listeners()
                        daqbuf_data = table.data
                curve = transform_curve_data(daqbuf_data, channel_name, removeEmptyBins, raw)
                table.clear()
            else:
                curve[channel_name] = {}
    except Exception as e:
        logger.error(f"Error in get_curve_data: {e}")
        raise RuntimeError
    return curve

def cache_backend_channels():
    if shared.backend_sync_active:
        return
    shared.backend_sync_active = True

    backend_channels = search_channels(allow_cached_response=False)

    with shared.available_backend_channels_lock:
        shared.available_backend_channels = backend_channels

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
            logger.error(f"Error in backend_synchronizer: {e}")
            time.sleep(30)

def get_recent_channels():
    return shared.recent_channels
