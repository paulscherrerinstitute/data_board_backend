from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from os import getenv
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared_resources.datahub_synchronizer import data_aggregator, backend_synchronizer

from routers import (
    channels
)

app = FastAPI()

app.include_router(channels.router, prefix='/channels')

# Connect to Redis
redis_host = getenv('REDIS_HOST', 'localhost')
redis_port = getenv('REDIS_PORT', '6379')
redis = Redis(host=redis_host, port=redis_port, db=0)

# Allow requests from everywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
	allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    # Start the data aggregator in a separate thread
    aggregator_thread = Thread(target=data_aggregator)
    aggregator_thread.daemon = True
    aggregator_thread.start()

    # Start the backend synchronizer in a separate thread
    backend_channel_thread = Thread(target=backend_synchronizer)
    backend_channel_thread.daemon = True
    backend_channel_thread.start()

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
