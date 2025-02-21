from functools import wraps
import asyncio
from fastapi import HTTPException

def timeout(limit: float):
    """
    A decorator that runs a function in a separate thread using asyncio.to_thread().
    
    If the function execution exceeds the specified time limit (in seconds), it will be 
    terminated and an HTTP 504 Timeout error will be raised.
    
    This decorator is designed for blocking (synchronous) functions only and will not 
    work as expected with asynchronous functions (i.e., functions defined with `async def`).
    
    Args:
        limit (float): The time limit in seconds for the function execution.
    
    Returns:
        The result of the function if it completes within the time limit.
    
    Raises:
        HTTPException: If the function takes longer than the specified time limit.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await asyncio.wait_for(asyncio.to_thread(func, *args, **kwargs), timeout=limit)
                return result
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="Request timed out")
        return wrapper
    return decorator
