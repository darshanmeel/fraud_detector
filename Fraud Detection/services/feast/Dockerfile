FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Feast and dependencies
RUN pip install --no-cache-dir "feast[redis,aws]" "pyarrow" "boto3"

# Command to run Feast UI
CMD ["feast", "ui", "--port", "6566", "--host", "0.0.0.0"]
