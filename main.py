from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from threading import Thread

from shared_resources.datahub_synchronizer import backend_synchronizer
from shared_resources.variables import shared_variables as shared

from routers import (
    channels,
    dashboards
)

import logging

logger = logging.getLogger("uvicorn")

def is_mongo_connected():
    try:
        shared.mongo_client.admin.command("ping")
    except Exception:
        raise RuntimeError("MongoDB server is not reachable. Have you set the MONGO_HOST and MONGO_PORT environment variables correctly?")

def configure_mongo_indices():
    indexes = shared.mongo_db["dashboards"].index_information()
    if not any("last_access" in idx.get("key", [])[0] for idx in indexes.values()):
        shared.mongo_db["dashboards"].create_index([("last_access", 1)])
        logger.info("Created index on last_access in MongoDB")
    else:
        logger.info("Index on last_access already exists in MongoDB")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check mongodb connectivity
    is_mongo_connected()

    # Make sure we have important indices
    configure_mongo_indices()

    # Start the backend synchronizer in a separate thread
    backend_channel_thread = Thread(target=backend_synchronizer)
    backend_channel_thread.daemon = True
    backend_channel_thread.start()
    
    # Execute app
    yield

    # Stop backend synchronizer
    backend_channel_thread.join(0)

app = FastAPI(lifespan=lifespan)

app.include_router(channels.router, prefix='/channels')
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

@app.get("/")
def root():
    return {"message": "Hello, World!"}

@app.get("/health")
def healthcheck():
    return {"message": "Alive and Well!"}