import gc
from datahub import *
import datetime

from shared_resources.variables import shared_variables as shared

def search_channels(search_text = ".*"):
    matching_channels = []

    if not matching_channels:
        # While resync is running (effective only from next search onwards), query backend directly.
        with Daqbuf(backend=None, parallel=False) as source:
            # Verboses gets us the plain response without any formatting, which would only slow everything down.
            source.verbose = True
            result = source.search(search_text)
            if result is not None:
                matching_channels = result["channels"]
    return matching_channels

def get_curve_data(channel_name: str, begin_time: int, end_time: int, backend: str, num_bins: int, useEventsIfBinCountTooLarge: bool, removeEmptyBins: bool, entry: dict):

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
    finally:
        table.clear()
        table.close()
        source.remove_listeners()
        source.close()
        del dataframe
        del data
        del items
        del table
        del source
        dataframe = None
        data = None
        items = None
        table = None
        source = None
    result = {"curve": curve}
    del curve
    curve = None
    gc.collect()
    result["raw"] = raw
    return result

def get_recent_channels():
    return shared.recent_channels
