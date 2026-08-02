# Repo root = site + backend/. Build: docker build -t agritech .  Run: docker run -p 5001:5001 agritech
FROM python:3.11-slim

WORKDIR /app

COPY backend/python/requirements.txt /app/backend/python/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/python/requirements.txt

COPY . /app

WORKDIR /app/backend/python
ENV ML_PORT=5001

EXPOSE 5001

# Render sets PORT; exec so Gunicorn gets signals correctly.
CMD ["/bin/sh", "-c", "exec gunicorn -w 2 -b 0.0.0.0:${PORT:-5001} app:app"]
