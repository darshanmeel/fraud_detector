FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY services/feature-writer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patch faust for mode-streaming compatibility
RUN find /usr/local/lib/python3.10/site-packages/faust -name "*.py" -exec sed -i 's/from mode.utils.compat import OrderedDict/from collections import OrderedDict/g' {} +
RUN find /usr/local/lib/python3.10/site-packages/faust -name "*.py" -exec sed -i 's/from mode.utils.contexts import nullcontext/from contextlib import nullcontext/g' {} +
RUN find /usr/local/lib/python3.10/site-packages/faust -name "*.py" -exec sed -i 's/from mode.utils.contexts import asynccontextmanager/from contextlib import asynccontextmanager/g' {} +

# Patch feast for redis-py 4.x compatibility (remove 'database' kwarg)
RUN sed -i 's/self._client = Redis(\*\*kwargs)/kwargs.pop("database", None); self._client = Redis(**kwargs)/g' /usr/local/lib/python3.10/site-packages/feast/infra/online_stores/redis.py
RUN sed -i 's/self._client_async = redis_asyncio.Redis(\*\*kwargs)/kwargs.pop("database", None); self._client_async = redis_asyncio.Redis(**kwargs)/g' /usr/local/lib/python3.10/site-packages/feast/infra/online_stores/redis.py

# Copy shared models and agent code
COPY services/shared /app/shared
COPY services/feature-writer/app.py /app/app.py

# Set python path to find shared and app
ENV PYTHONPATH="/app"

# Command to run Faust worker
CMD ["faust", "-A", "app", "worker", "-l", "info"]
