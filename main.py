import logging
from contextlib import asynccontextmanager
from os import getenv
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import channels, dashboards, root
from shared_resources.datahub_synchronizer import backend_synchronizer
from shared_resources.mongo_service import (
    check_mongo_connected,
    configure_mongo_indices,
)
from shared_resources.variables import SharedState

logger = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Instantiate shared variables
    app.state.shared = SharedState()
    # Check mongodb connectivity
    check_mongo_connected(app.state.shared)

    # Make sure we have important indices
    configure_mongo_indices(app.state.shared)

    # Start the backend synchronizer in a separate thread
    backend_channel_thread = Thread(target=backend_synchronizer, args=(app.state.shared,))
    backend_channel_thread.daemon = True
    backend_channel_thread.start()
    app.state._backend_channel_thread = backend_channel_thread

    # Execute app
    yield

    # Stop backend synchronizer
    app.state._backend_channel_thread.join(0)
    app.state.shared.mongo_client.close()


tags_metadata = [
    {
        "name": "maintenance",
        "description": "Only accessible within the docker network.",
    }
]

root_path = getenv("ROOT_PATH", "/")

app = FastAPI(lifespan=lifespan, openapi_tags=tags_metadata, root_path=root_path)

app.include_router(root.router)
app.include_router(channels.router, prefix="/channels")
app.include_router(dashboards.router, prefix="/dashboard")
app.include_router(dashboards.maintenance_router, prefix="/maintenance/dashboard")

# Allow requests from everywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
