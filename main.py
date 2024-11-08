from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
import os

app = FastAPI()

# Connect to Redis
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = os.getenv('REDIS_PORT', '6379')
redis = Redis(host=redis_host, port=redis_port, db=0)

# Get frontend URL for CORS
frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
# Allow only requests from frontend and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, 'http://localhost'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Hello, World!"}

@app.get("/counter")
def get_counter():
    # Get the counter from Redis (default to 0 if not set)
    counter = redis.get('counter')
    if counter is None:
        counter = 0
        redis.set('counter', counter)
    return {"counter": int(counter)}

@app.post("/increment")
def increment_counter():
    # Increment the counter in Redis
    counter = redis.incr('counter')
    return {"counter": int(counter)}
