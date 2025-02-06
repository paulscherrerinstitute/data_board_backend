from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from os import getenv
from threading import Thread

from shared_resources.datahub_synchronizer import data_aggregator, backend_synchronizer

from routers import (
    channels,
    dashboards
)

# Connect to Redis
redis_host = getenv('REDIS_HOST', 'localhost')
redis_port = getenv('REDIS_PORT', '6379')
redis = Redis(host=redis_host, port=redis_port, db=0)

def is_redis_connected():
    try:
        redis.ping() 
    except Exception:
        raise RuntimeError("Redis server is not reachable")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check redis connectivity
    is_redis_connected()

    # Start the data aggregator in a separate thread
    aggregator_thread = Thread(target=data_aggregator)
    aggregator_thread.daemon = True
    aggregator_thread.start()

    # Start the backend synchronizer in a separate thread
    backend_channel_thread = Thread(target=backend_synchronizer)
    backend_channel_thread.daemon = True
    backend_channel_thread.start()
    
    # Execute app
    yield

    # Stop threads, give them 3 seconds to gracefully quit
    aggregator_thread.join(3)
    backend_channel_thread.join(3)

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

@app.get("/counter")
def get_counter_route():
    # Get the counter from Redis (default to 0 if not set)
    counter = redis.get('counter')
    if counter is None:
        counter = 0
        redis.set('counter', counter)
    return {"counter": int(counter)}

@app.post("/increment")
def increment_counter_route():
    # Increment the counter in Redis
    counter = redis.incr('counter')
    return {"counter": int(counter)}
