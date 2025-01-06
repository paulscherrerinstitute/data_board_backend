from fastapi import APIRouter, Request, Query

from shared_resources.variables import shared_variables as shared
from shared_resources.datahub_synchronizer import search_channels, get_recent_channels

router = APIRouter()

@router.get("/search", tags=["channels"])
async def search_channels_route(search_text: str):
    if not search_text:
        # Return all channels
        channels = shared.available_backend_channels.copy()
        return {"channels": channels}
    channels = search_channels(search_text.strip())
    return {"channels": channels}

@router.get("/recent", tags=["channels"])
async def recent_channels_route():
    channels = get_recent_channels()
    return {"channels": channels}