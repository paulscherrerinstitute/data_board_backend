import datetime
import logging
from urllib.parse import urlencode

import numpy as np
from datahub import Daqbuf, Enum, Table, re

from shared_resources.variables import SharedState

logger = logging.getLogger("uvicorn")


def search_channels(shared: SharedState, search_text=".*", allow_cached_response=True):
    matching_channels = []
    cache_miss = False
    if allow_cached_response:
        with shared.available_backend_channels_lock:
            cached_channel_list = list(shared.available_backend_channels)
        for channel in cached_channel_list:
            if re.search(search_text, channel["name"], re.IGNORECASE):
                matching_channels.append(
                    {
                        "backend": str(channel.get("backend", "")),
                        "name": str(channel.get("name", "")),
                        "seriesId": str(channel.get("seriesId", "")),
                        "source": str(channel.get("source", "")),
                        "type": str(channel.get("type", "")),
                        "shape": channel.get("shape", ""),  # May be []
                        "unit": str(channel.get("unit", "")),
                        "description": str(channel.get("description", "")),
                    }
                )
        if not matching_channels:
            cache_miss = True

    if not matching_channels:
        with Daqbuf(backend=None, parallel=True) as source:
            # Verbose gets us the plain response without any formatting, which would only slow everything down.
            source.verbose = True
            result = source.search(regex=search_text, case_sensitive=False)
            if result is not None:
                matching_channels = [
                    {
                        "backend": str(channel.get("backend", "")),
                        "name": str(channel.get("name", "")),
                        "seriesId": str(channel.get("seriesId", "")),
                        "source": str(channel.get("source", "")),
                        "type": str(channel.get("type", "")),
                        "shape": channel.get("shape", ""),  # May be []
                        "unit": str(channel.get("unit", "")),
                        "description": str(channel.get("description", "")),
                    }
                    for channel in result.get("channels", [])
                ]

    # In case uncached channels were discovered, add them to the cache
    if matching_channels and cache_miss:
        for channel in matching_channels:
            if not any(channel == existing for existing in shared.available_backend_channels):
                with shared.available_backend_channels_lock:
                    shared.available_backend_channels.append(channel)

    return matching_channels


def process_curve_data_entry(
    record,
    channel_name,
    remove_empty_bins,
    raw,
    count_name,
    count_map,
    min_map,
    max_map,
    min_name,
    max_name,
    curve,
):
    timestamp = str(record["timestamp"])

    # skip empty bins if specified
    if remove_empty_bins and not raw:
        count = count_map.get(timestamp)
        if count and int(count[count_name]) == 0:
            return

    # value
    value = record[channel_name]
    curve[channel_name][timestamp] = value.id if isinstance(value, Enum) else float(value)

    # min
    if timestamp in min_map:
        curve[f"{channel_name}_min"][timestamp] = float(min_map[timestamp][min_name])

    # max
    if timestamp in max_map:
        curve[f"{channel_name}_max"][timestamp] = float(max_map[timestamp][max_name])

    # Metainformation
    count = count_map.get(timestamp)
    if count or raw:
        meta = curve[f"{channel_name}_meta"]["pointMeta"].setdefault(timestamp, {})
        if count:
            meta["count"] = int(count[count_name])
        if raw:
            meta["pulseId"] = record.get("pulse_id")


def is_waveform_entry(entry, channel_name):
    return isinstance(entry[channel_name], np.ndarray)


def process_curve_data_waveform_entry(record, channel_name, curve):
    timestamp = str(record["timestamp"])
    for index, value in enumerate(record[channel_name]):
        curve[channel_name][f"{timestamp}_{str(index)}"] = float(value)
    meta = curve[f"{channel_name}_meta"]["pointMeta"].setdefault(timestamp, {})
    meta["pulseId"] = record.get("pulse_id")


def transform_curve_data(daqbuf_data, channel_name, remove_empty_bins=False, raw=True):
    count_name = f"{channel_name} count"
    min_name = f"{channel_name} min"
    max_name = f"{channel_name} max"

    # prepare output containers
    curve = {channel_name: {}}
    curve[f"{channel_name}_meta"] = {"pointMeta": {}, "raw": raw}

    # Check if waveform and divert if that's the case
    try:
        first_entry = daqbuf_data[channel_name][0]
        is_waveform = is_waveform_entry(first_entry, channel_name)
    except (KeyError, IndexError):
        is_waveform = False

    curve[f"{channel_name}_meta"]["waveform"] = is_waveform

    if is_waveform:
        for record in daqbuf_data.get(channel_name, []):
            process_curve_data_waveform_entry(
                record,
                channel_name,
                curve,
            )
        return {"curve": curve}

    if min_name in daqbuf_data:
        curve[f"{channel_name}_min"] = {}
    if max_name in daqbuf_data:
        curve[f"{channel_name}_max"] = {}

    # build timestamp => record maps once
    count_map = {str(r["timestamp"]): r for r in daqbuf_data.get(count_name, [])}
    min_map = {str(r["timestamp"]): r for r in daqbuf_data.get(min_name, [])} if min_name in daqbuf_data else {}
    max_map = {str(r["timestamp"]): r for r in daqbuf_data.get(max_name, [])} if max_name in daqbuf_data else {}

    timestamps = np.sort([r["timestamp"] for r in daqbuf_data.get(count_name, [])])
    intervals = np.diff(timestamps)

    meta = curve.setdefault(f"{channel_name}_meta", {})
    meta["interval_avg"] = intervals.mean() if len(intervals) > 0 else 0
    meta["interval_stddev"] = intervals.std() if len(intervals) > 0 else 0

    for record in daqbuf_data.get(channel_name, []):
        process_curve_data_entry(
            record,
            channel_name,
            remove_empty_bins,
            raw,
            count_name,
            count_map,
            min_map,
            max_map,
            min_name,
            max_name,
            curve,
        )

    return {"curve": curve}


def update_recent_channels(shared: SharedState, channel_entry: dict):
    if channel_entry:
        with shared.recent_channels_lock:
            if channel_entry in shared.recent_channels:
                shared.recent_channels.remove(channel_entry)
            shared.recent_channels.insert(0, channel_entry)
            while len(shared.recent_channels) > 10:
                shared.recent_channels.pop()


def get_curve_data(
    shared: SharedState,
    channel_name: str,
    begin_time: int,
    end_time: int,
    backend: str,
    num_bins: int,
    useEventsIfBinCountTooLarge: bool,
    removeEmptyBins: bool,
    channel_entry: dict,
):
    update_recent_channels(shared, channel_entry)

    query = {
        "channels": [channel_name],
        "start": datetime.datetime.fromtimestamp(begin_time / 1000, datetime.timezone.utc).isoformat(
            sep=" ", timespec="milliseconds"
        ),
        "end": datetime.datetime.fromtimestamp(end_time / 1000, datetime.timezone.utc).isoformat(
            sep=" ", timespec="milliseconds"
        ),
    }

    raw = num_bins <= 0
    if not raw:
        query["bins"] = num_bins

    curve = {}
    try:
        with Daqbuf(backend=backend) as source:
            table = Table()
            source.add_listener(table)
            source.request(query, background=True)
            source.join()
            source.remove_listeners()
            daqbuf_data = table.data

            if daqbuf_data is not None and len(daqbuf_data) > 0:
                if not raw and useEventsIfBinCountTooLarge and channel_name + " count" in daqbuf_data:
                    count_key = f"{channel_name} count"
                    data_count = sum(item.get(count_key, 0) for item in daqbuf_data[count_key])

                    if data_count < num_bins:
                        table.clear()
                        source.add_listener(table)
                        query.pop("bins")
                        source.request(query, background=True)
                        source.join()
                        source.remove_listeners()

                        entries = table.data.get(channel_name, [])
                        is_waveform = is_waveform_entry(entries[0], channel_name) if entries else False
                        is_single_waveform = len(entries) == 1 and is_waveform

                        if not is_waveform or is_single_waveform:
                            raw = True
                            daqbuf_data = table.data
                curve = transform_curve_data(daqbuf_data, channel_name, removeEmptyBins, raw)
                table.clear()
            else:
                curve[channel_name] = {}
    except Exception as e:
        logger.error(f"Error in get_curve_data: {e}")
        raise RuntimeError from e
    return curve


def get_recent_channels(shared: SharedState):
    return shared.recent_channels


def get_raw_data_link(shared: SharedState, channel_name, begin_time, end_time, backend="sf-databuffer"):
    base_url = shared.DATA_API_BASE_URL + "/events"
    params = {
        "backend": backend,
        "channelName": channel_name,
        "begDate": datetime.datetime.fromtimestamp(begin_time / 1000, datetime.timezone.utc).isoformat(
            sep=" ", timespec="milliseconds"
        ),
        "endDate": datetime.datetime.fromtimestamp(end_time / 1000, datetime.timezone.utc).isoformat(
            sep=" ", timespec="milliseconds"
        ),
    }
    return {"link": f"{base_url}?{urlencode(params)}"}
