from fastapi import APIRouter, HTTPException

from datetime import datetime, timezone
from datahub import *

from shared_resources.variables import shared_variables as shared
from shared_resources.datahub_synchronizer import search_channels, get_recent_channels

router = APIRouter()

@router.get("/search", tags=["channels"])
async def search_channels_route(search_text: str = ""):
    if search_text == "":
        # Return all channels
        channels = shared.available_backend_channels.copy()
        return {"channels": channels}
    channels = search_channels(search_text.strip())
    return {"channels": channels}

@router.get("/recent", tags=["channels"])
async def recent_channels_route():
    channels = get_recent_channels()
    return {"channels": channels}

@router.get("/curve", tags=["channels"])
async def curve_data_route(channel_name: str, begin_time: int, end_time: int, backend: str = "sf-databuffer", num_bins: int = 0, query_expansion: bool = False):
    # If the channel name is a number interpret it as seriesId and don't check if it exists. Otherwise verify the channel name exists
    if not channel_name.isdigit() and not search_channels(channel_name.strip()):
        raise HTTPException(status_code=404, detail="Channel does not exist in backend")
    if begin_time * end_time == 0:
        raise HTTPException(status_code=400, detail="begin_time or end_time is invalid, must be valid unix time (seconds)")

    query = {
        "channels": [channel_name],
        "start": datetime.fromtimestamp(begin_time, timezone.utc).isoformat(sep=' ', timespec='milliseconds'),
        "end": datetime.fromtimestamp(end_time, timezone.utc).isoformat(sep=' ', timespec='milliseconds')
    }
    if num_bins > 0:
        query["bins"] = num_bins

    curve = {}
    try:
        with Daqbuf(backend=backend) as source:
            table = Table()
            source.add_listener(table)
            source.request(query)
            dataframe = table.as_dataframe()
            data = dataframe.to_dict(orient='index')
            curve[channel_name] = {timestamp: entry[channel_name] for timestamp, entry in data.items()}
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching data from backend")
    return {"curve": curve}