# Feast Core Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the core Feast foundation: Dockerfile, configuration, and docker-compose service.

**Architecture:** 
- Feast will run as a separate service for its UI and offline/online feature management.
- Configuration will use MinIO (S3-compatible) for the registry and Redis for the online store.
- Local provider with file-based offline store for Task 5.

**Tech Stack:** 
- Feast 0.36.0 (based on .env)
- Python 3.11-slim
- Redis
- MinIO (S3)

---

### Task 1: Create Feast Dockerfile

**Files:**
- Create: `services/feast/Dockerfile`

- [ ] **Step 1: Write the Feast Dockerfile**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Feast and dependencies
RUN pip install --no-cache-dir "feast[redis]" "pyarrow"

# Command to run Feast UI
CMD ["feast", "ui"]
```

- [ ] **Step 2: Commit**

```bash
git add services/feast/Dockerfile
git commit -m "feat(feast): add Feast Dockerfile"
```

---

### Task 2: Create Feast Configuration

**Files:**
- Create: `config/feast/feature_store.yaml`

- [ ] **Step 1: Write the feature_store.yaml file**

```yaml
project: fraud_detection
registry: s3://fraud-features-offline/feast-registry.db
provider: local
online_store:
  type: redis
  connection_string: "fraud-redis:6379,password=,database=0"
offline_store:
  type: file
```

- [ ] **Step 2: Commit**

```bash
git add config/feast/feature_store.yaml
git commit -m "feat(feast): add Feast configuration"
```

---

### Task 3: Add Feast Service to Docker Compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add feast service to docker-compose.yml**

```yaml
  feast:
    build:
      context: .
      dockerfile: services/feast/Dockerfile
    container_name: fraud-feast
    profiles: [core]
    ports:
      - "8888:8888"
    networks:
      - act-net
      - explain-net
    volumes:
      - ./config/feast:/app
    environment:
      FEAST_USAGE: "False"
      AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      AWS_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      FEAST_S3_ENDPOINT_URL: "http://minio:9000"
    depends_on:
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
```

- [ ] **Step 2: Add act-net to minio service in docker-compose.yml**
To ensure Feast can reach MinIO via `act-net` or ensure `minio` is in `explain-net` (which Feast is already in).
Actually, Feast is in `act-net` and `explain-net`. MinIO is in `explain-net`. So Feast can reach MinIO.
I will double check minio network. `minio` has `explain-net`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(feast): add feast service to docker-compose.yml"
```

---

### Task 4: Verify Infrastructure

- [ ] **Step 1: Run infra_test.ps1 or similar to verify**
Since I cannot easily run full docker compose and check health in this environment, I'll verify the files are created correctly.

- [ ] **Step 2: Final Commit**
No changes needed if Step 1 is just verification.
