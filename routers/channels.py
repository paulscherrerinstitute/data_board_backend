from fastapi import APIRouter, HTTPException

from datahub import *
from fastapi.responses import JSONResponse

from shared_resources.decorators import timeout
from shared_resources.variables import shared_variables as shared
from shared_resources.datahub_synchronizer import search_channels, get_curve_data, get_recent_channels

import logging
logger = logging.getLogger("uvicorn")

router = APIRouter()

@router.get("/search", tags=["channels"])
@timeout(15)
def search_channels_route(search_text: str = "", allow_cached_response = True):
    channels = []
    if search_text == "" and allow_cached_response:
        # Return all channels
        channels = list(shared.available_backend_channels)
    else: 
        channels = search_channels(search_text=search_text.strip(), allow_cached_response=allow_cached_response)

    # To avoid precision loss in browsers, transmit seriresId as string
    processed_channels = []
    for channel in channels:
        channel_copy = channel.copy()
        if isinstance(channel_copy.get("seriesId"), int):
            channel_copy["seriesId"] = str(channel_copy["seriesId"])
        processed_channels.append(channel_copy)
    result = {"channels": processed_channels}
    
    return JSONResponse(content=result, status_code=200)

@router.get("/recent", tags=["channels"])
@timeout(10)
def recent_channels_route():
    channels = get_recent_channels()
    result = {"channels": channels}
    return JSONResponse(content=result, status_code=200)

@router.get("/curve", tags=["channels"])
@timeout(30)
def curve_data_route(channel_name: str, begin_time: int, end_time: int, backend: str = "sf-databuffer", num_bins: int = 0, useEventsIfBinCountTooLarge: bool = False, removeEmptyBins: bool = False):
    entry = {}
    # If the channel name can be converted to an integer, treat it as seriesId.
    if channel_name.isdigit():
        entry = next((item for item in shared.available_backend_channels if item['seriesId'] == channel_name), None)
    else:
        entry = next((item for item in shared.available_backend_channels if item['name'] == channel_name), None)
    # Don't verify channel if seriesId is used
    if not channel_name.isdigit() and not search_channels(channel_name.strip()):
        raise HTTPException(status_code=404, detail="Channel does not exist in backend")
    if begin_time * end_time == 0:
        raise HTTPException(status_code=400, detail="begin_time or end_time is invalid, must be valid unix time (seconds)")
    if begin_time > end_time:
        raise HTTPException(status_code=400, detail="begin_time is bigger than end_time, must be smaller or equal")
    if end_time > time.time() * 1000:
        raise HTTPException(status_code=400, detail="end_time is in the future, cannot request data for the future")

    try:
        result = get_curve_data(channel_name=channel_name, begin_time=begin_time, end_time=end_time, backend=backend, num_bins=num_bins, useEventsIfBinCountTooLarge=useEventsIfBinCountTooLarge, removeEmptyBins=removeEmptyBins,  channel_entry=entry)
        return JSONResponse(content=result, status_code=200)
    except RuntimeError as e:
        logger.error(f"Error in curve_data_route: {e}")
        raise HTTPException(status_code=500, detail="Error fetching data from backend")
