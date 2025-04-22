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

def is_mongo_connected():
    try:
        shared.mongo_client.admin.command("ping")
    except Exception:
        raise RuntimeError("MongoDB server is not reachable. Have you set the MONGO_HOST and MONGO_PORT environment variables correctly?")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check mongodb connectivity
    is_mongo_connected()

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