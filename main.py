from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared_resources.variables import shared_variables as shared

from routers import (
    channels,
    dashboards
)

def is_redis_connected():
    try:
        shared.redis_client.ping() 
    except Exception:
        raise RuntimeError("Redis server is not reachable. Have you set the REDIS_HOST and REDIS_PORT environment variables correctly?")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check redis connectivity
    is_redis_connected()
    
    # Execute app
    yield

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