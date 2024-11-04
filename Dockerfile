FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port specified in the environment variable, default to 8000
ENV PORT=${PORT:-8000}
EXPOSE $PORT

# Run FastAPI, binding to all interfaces on the specified port
CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "${PORT}"]

