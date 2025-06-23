import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, ORJSONResponse

from shared_resources.channel_service import (
    get_curve_data,
    get_raw_data_link,
    get_recent_channels,
    search_channels,
)
from shared_resources.decorators import timeout

logger = logging.getLogger("uvicorn")

router = APIRouter(tags=["channels"])


@router.get("/search", description="Searches the cache for a channel. If not found in cache, archivers will be queried")
@timeout(15)
def search_channels_route(request: Request, search_text: str = "", allow_cached_response=True, backend=None):
    shared = request.app.state.shared
    channels = []
    if search_text == "" and allow_cached_response:
        # Return all channels
        channels = list(shared.available_backend_channels)
    else:
        # Workaround to sf-databuffer not offering a way to correctly cache channels.
        # With this many characters in the search text, the search should be fairly performant.
        if len(search_text) > 4:
            allow_cached_response = False
        channels = search_channels(
            shared, search_text=search_text.strip(), allow_cached_response=allow_cached_response, backend=backend
        )

    # To avoid precision loss in browsers, transmit seriresId as string
    processed_channels = []
    for channel in channels:
        channel_copy = channel.copy()
        if isinstance(channel_copy.get("seriesId"), int):
            channel_copy["seriesId"] = str(channel_copy["seriesId"])
        processed_channels.append(channel_copy)
    result = {"channels": processed_channels}

    return JSONResponse(content=result, status_code=200)


@router.get("/recent", description="Returns channels with recently accessed data")
@timeout(10)
def recent_channels_route(request: Request):
    channels = get_recent_channels(request.app.state.shared)
    result = {"channels": channels}
    return JSONResponse(content=result, status_code=200)


@router.get("/curve", description="Returns channel data for the specified parameters")
@timeout(60)
def curve_data_route(
    request: Request,
    channel_name: str,
    begin_time: int,
    end_time: int,
    backend: str = "sf-databuffer",
    num_bins: int = 0,
    useEventsIfBinCountTooLarge: bool = False,
    removeEmptyBins: bool = False,
):
    shared = request.app.state.shared
    entry = {}
    # If the channel name can be converted to an integer, treat it as seriesId.
    if channel_name.isdigit():
        entry = next(
            (item for item in shared.available_backend_channels if item["seriesId"] == channel_name),
            None,
        )
    else:
        entry = next(
            (item for item in shared.available_backend_channels if item["name"] == channel_name),
            None,
        )
    # Don't verify channel if seriesId is used
    if not channel_name.isdigit() and not search_channels(shared, channel_name.strip()):
        raise HTTPException(status_code=404, detail="Channel not found in backend")
    if begin_time * end_time == 0:
        raise HTTPException(
            status_code=400,
            detail="begin_time or end_time is invalid, must be valid unix time (seconds)",
        )
    if begin_time > end_time:
        raise HTTPException(
            status_code=400,
            detail="begin_time is bigger than end_time, must be smaller or equal",
        )
    if end_time > time.time() * 1000:
        raise HTTPException(
            status_code=400,
            detail="end_time is in the future, cannot request data for the future",
        )

    try:
        result = get_curve_data(
            shared,
            channel_name=channel_name,
            begin_time=begin_time,
            end_time=end_time,
            backend=backend,
            num_bins=num_bins,
            useEventsIfBinCountTooLarge=useEventsIfBinCountTooLarge,
            removeEmptyBins=removeEmptyBins,
            channel_entry=entry,
        )
        return ORJSONResponse(content=result, status_code=200)
    except RuntimeError as e:
        logger.error(f"Error in curve_data_route: {e}")
        raise HTTPException(status_code=500, detail="Error fetching data from backend") from e


@router.get("/raw-link", description="Returns a link to download raw data directly from data-api")
@timeout(5)
def raw_data_link_route(
    request: Request, channel_name: str, begin_time: int, end_time: int, backend: str = "sf-databuffer"
):
    shared = request.app.state.shared
    if begin_time * end_time == 0:
        raise HTTPException(
            status_code=400, detail="begin_time or end_time is invalid, must be valid unix time (seconds)"
        )
    if begin_time > end_time:
        raise HTTPException(status_code=400, detail="begin_time is bigger than end_time, must be smaller or equal")

    try:
        result = get_raw_data_link(
            shared, channel_name=channel_name, begin_time=begin_time, end_time=end_time, backend=backend
        )
        return JSONResponse(content=result, status_code=200)
    except RuntimeError as e:
        logger.error(f"Error in raw_data_link_route: {e}")
        raise HTTPException(status_code=500, detail="Error assembling link") from e
