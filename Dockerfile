FROM python:alpine

WORKDIR /app

RUN addgroup -S databoard && adduser -S -D -H -s /sbin/nologin -G databoard databoard

RUN apk add --update --no-cache --virtual .tmp pkgconfig hdf5-dev gcc libc-dev linux-headers curl mongodb-tools

COPY requirements.txt .
# --progress-bar off is done so it won't spawn a new thread for it, which makes the pipeline break 
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

COPY main.py .
COPY shared_resources/ shared_resources/
COPY routers/ routers/
COPY migrate_whitelisted_dashboards.sh .
RUN chmod +x migrate_whitelisted_dashboards.sh
RUN chown -R databoard:databoard /app

EXPOSE 8080

USER databoard

CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8080"]