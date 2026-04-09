FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV THE_DDNS_THING_HOST=0.0.0.0
ENV THE_DDNS_THING_PORT=10710
ENV THE_DDNS_THING_SYNC_INTERVAL=300
ENV THE_DDNS_THING_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10710
VOLUME ["/data"]
CMD ["/bin/sh", "-c", "gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${THE_DDNS_THING_PORT} the_ddns_thing.wsgi:app"]
