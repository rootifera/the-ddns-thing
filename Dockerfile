FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV THE_DDNS_THING_HOST=0.0.0.0
ENV THE_DDNS_THING_PORT=5000
ENV THE_DDNS_THING_SYNC_INTERVAL=300
ENV THE_DDNS_THING_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
VOLUME ["/data"]

CMD ["python", "-m", "the_ddns_thing.main"]
