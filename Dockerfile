FROM python:alpine

WORKDIR /app

RUN apk add --update --no-cache --virtual .tmp pkgconfig hdf5-dev gcc libc-dev linux-headers

COPY requirements.txt .
# --progress-bar off is done so it won't spawn a new thread for it, which makes the pipeline break 
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8080"]