from fastapi import APIRouter, HTTPException

from datahub import *
from fastapi.responses import JSONResponse

from shared_resources.decorators import timeout
from shared_resources.variables import shared_variables as shared
from shared_resources.datahub_synchronizer import search_channels, get_curve_data, get_recent_channels

router = APIRouter()

@router.get("/search", tags=["channels"])
@timeout(10)
def search_channels_route(search_text: str = ""):
    channels = []
    if search_text == "":
        # Return all channels
        channels = shared.available_backend_channels.copy()
    else: 
        channels = search_channels(search_text=search_text.strip())
    result = {"channels": channels}
    return JSONResponse(content=result, status_code=200)

@router.get("/recent", tags=["channels"])
@timeout(10)
def recent_channels_route():
    channels = get_recent_channels()
    result = {"channels": channels}
    return JSONResponse(content=result, status_code=200)

@router.get("/curve", tags=["channels"])
@timeout(10)
def curve_data_route(channel_name: str, begin_time: int, end_time: int, backend: str = "sf-databuffer", num_bins: int = 0, query_expansion: bool = False):
    entry = {}
    # If the channel name can be converted to an integer, treat it as seriesId.
    if channel_name.isdigit():
        entry = next((item for item in shared.available_backend_channels if item['seriesId'] == int(channel_name)), None)
    else:
        entry = next((item for item in shared.available_backend_channels if item['name'] == channel_name), None)
    if not entry and not search_channels(channel_name.strip()):
        raise HTTPException(status_code=404, detail="Channel does not exist in backend")
    if begin_time * end_time == 0:
        raise HTTPException(status_code=400, detail="begin_time or end_time is invalid, must be valid unix time (seconds)")

    try:
        result = get_curve_data(channel_name=channel_name, begin_time=begin_time, end_time=end_time, backend=backend, num_bins=num_bins, query_expansion=query_expansion, entry=entry)
        return JSONResponse(content=result, status_code=200)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail="Error fetching data from backend")
