# Fraud Detection Core Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the foundational data layer (Redpanda, Redis, MinIO, Feast) using Docker Compose with automated bootstrapping of topics and buckets.

**Architecture:** Multi-network bridge topology (`act-net`, `explain-net`, `obs-net`, `mgmt-net`) to physically isolate hot path from cold path traffic. Uses init-containers for declarative infrastructure setup.

**Tech Stack:** Docker Compose V2, Redpanda (v24.1), Redis (7.2-alpine), MinIO, Feast (0.36.0), Python 3.11.

---

### Task 1: Environment & Directory Scaffolding

**Files:**
- Create: `.env`
- Create: `docker-compose.yml`
- Create: `Makefile`
- Create: `config/redpanda/topics.sh`
- Create: `config/minio/bootstrap.sh`
- Create: `config/redis/redis.conf`
- Create: `config/feast/feature_store.yaml`

- [ ] **Step 1: Create the `.env` file**

```bash
cat <<EOF > .env
# Project Versions
REDPANDA_VERSION=v24.1
REDIS_VERSION=7.2-alpine
MINIO_VERSION=RELEASE.2024-04-06T05-26-02Z
FEAST_VERSION=0.36.0

# Credentials
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Network Settings
DOMAIN=fraud.local
EOF
```

- [ ] **Step 2: Create the base directory structure**

```bash
mkdir -p config/redpanda config/redis config/minio config/feast schemas services/feast
```

- [ ] **Step 3: Create the `Makefile` with core targets**

```makefile
.PHONY: core down reset status topics buckets

core:
	docker compose --profile core up -d

down:
	docker compose down

reset:
	docker compose down -v

status:
	docker compose ps --all

topics:
	docker compose run --rm init-redpanda

buckets:
	docker compose run --rm init-minio
```

- [ ] **Step 4: Commit scaffolding**

```bash
git add .env Makefile config/
git commit -m "infra: initial scaffolding for core infrastructure"
```

---

### Task 2: Network & Foundation Services (Redis, Redpanda)

**Files:**
- Modify: `docker-compose.yml`
- Create: `config/redis/redis.conf`

- [ ] **Step 1: Define networks and base Redis in `docker-compose.yml`**

```yaml
version: '3.8'

networks:
  act-net:
    driver: bridge
  explain-net:
    driver: bridge
  obs-net:
    driver: bridge
  mgmt-net:
    driver: bridge

services:
  redis:
    image: redis:${REDIS_VERSION}
    container_name: fraud-redis
    profiles: [core]
    ports:
      - "6379:6379"
    networks:
      - act-net
      - obs-net
    volumes:
      - redis-data:/data
      - ./config/redis/redis.conf:/usr/local/etc/redis/redis.conf
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: '0.5'

volumes:
  redis-data:
```

- [ ] **Step 2: Create `config/redis/redis.conf`**

```conf
appendonly yes
notify-keyspace-events Ex
```

- [ ] **Step 3: Add Redpanda to `docker-compose.yml`**

```yaml
  redpanda:
    image: redpandadata/redpanda:${REDPANDA_VERSION}
    container_name: fraud-redpanda
    profiles: [core]
    ports:
      - "9092:9092"
      - "9644:9644"
      - "8081:8081"
      - "8080:8080"
    networks:
      - act-net
      - explain-net
    command:
      - redpanda start
      - --smp 1
      - --memory 1G
      - --reserve-memory 0M
      - --overprovisioned
      - --node-id 0
      - --check=false
      - --kafka-addr PLAINTEXT://0.0.0.0:29092,OUTSIDE://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://redpanda:29092,OUTSIDE://localhost:9092
    healthcheck:
      test: ["CMD", "rpk", "cluster", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 2g
          cpus: '2.0'
```

- [ ] **Step 4: Verify startup**

Run: `make core`
Expect: `fraud-redis` and `fraud-redpanda` containers running.

- [ ] **Step 5: Commit foundation**

```bash
git add docker-compose.yml config/redis/redis.conf
git commit -m "infra: add redis and redpanda services"
```

---

### Task 3: Bootstrapping Redpanda Topics

**Files:**
- Create: `config/redpanda/topics.sh`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write the topic creation script**

```bash
cat <<EOF > config/redpanda/topics.sh
#!/bin/bash
rpk topic create tx.raw.hot -p 16 --brokers redpanda:29092
rpk topic create tx.raw.cold -p 8 --brokers redpanda:29092
rpk topic create feature.update -p 8 --brokers redpanda:29092
rpk topic create decision.block -p 4 --brokers redpanda:29092
rpk topic create decision.allow -p 4 --brokers redpanda:29092
rpk topic create decision.review -p 4 --brokers redpanda:29092
rpk topic create decision.degraded -p 2 --brokers redpanda:29092
rpk topic create tx.dead-letter -p 2 --brokers redpanda:29092
EOF
chmod +x config/redpanda/topics.sh
```

- [ ] **Step 2: Add `init-redpanda` service to `docker-compose.yml`**

```yaml
  init-redpanda:
    image: redpandadata/redpanda:${REDPANDA_VERSION}
    container_name: fraud-init-redpanda
    profiles: [core]
    networks:
      - act-net
    volumes:
      - ./config/redpanda/topics.sh:/usr/local/bin/topics.sh
    entrypoint: ["/bin/bash", "/usr/local/bin/topics.sh"]
    depends_on:
      redpanda:
        condition: service_healthy
```

- [ ] **Step 3: Run topic creation**

Run: `make topics`
Expect: List of created topics in output.

- [ ] **Step 4: Commit topics**

```bash
git add config/redpanda/topics.sh docker-compose.yml
git commit -m "infra: automate redpanda topic creation"
```

---

### Task 4: MinIO Storage & Bootstrapping

**Files:**
- Create: `config/minio/bootstrap.sh`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write the MinIO bootstrap script**

```bash
cat <<EOF > config/minio/bootstrap.sh
#!/bin/sh
/usr/bin/mc alias set local http://minio:9000 minioadmin minioadmin
/usr/bin/mc mb local/fraud-features-offline
/usr/bin/mc mb local/fraud-audit-logs --with-lock
/usr/bin/mc mb local/fraud-models
/usr/bin/mc mb local/fraud-lineage
EOF
chmod +x config/minio/bootstrap.sh
```

- [ ] **Step 2: Add MinIO and `init-minio` to `docker-compose.yml`**

```yaml
  minio:
    image: minio/minio:${MINIO_VERSION}
    container_name: fraud-minio
    profiles: [core]
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - explain-net
      - mgmt-net
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 3s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: '0.5'

  init-minio:
    image: minio/mc
    container_name: fraud-init-minio
    profiles: [core]
    networks:
      - explain-net
    volumes:
      - ./config/minio/bootstrap.sh:/usr/local/bin/bootstrap.sh
    entrypoint: ["/bin/sh", "/usr/local/bin/bootstrap.sh"]
    depends_on:
      minio:
        condition: service_healthy
```

- [ ] **Step 3: Run MinIO bootstrap**

Run: `make buckets`
Expect: "Bucket created successfully" for all 4 buckets.

- [ ] **Step 4: Commit MinIO**

```bash
git add config/minio/bootstrap.sh docker-compose.yml
git commit -m "infra: add minio and bucket bootstrapping"
```

---

### Task 5: Feast Server (Custom Build)

**Files:**
- Create: `services/feast/Dockerfile`
- Create: `config/feast/feature_store.yaml`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create `services/feast/Dockerfile`**

```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir "feast[redis]" "pyarrow"
WORKDIR /app
CMD ["feast", "ui", "--host", "0.0.0.0", "--port", "6566"]
```

- [ ] **Step 2: Create `config/feast/feature_store.yaml`**

```yaml
project: fraud_detection
registry: s3://fraud-features-offline/feast-registry.db
provider: local
online_store:
  type: redis
  connection_string: redis:6379
offline_store:
  type: file
  path: /app/data/offline_store.db
```

- [ ] **Step 3: Add Feast to `docker-compose.yml`**

```yaml
  feast:
    build:
      context: .
      dockerfile: services/feast/Dockerfile
    container_name: fraud-feast
    profiles: [core]
    ports:
      - "6566:6566"
    networks:
      - act-net
    volumes:
      - ./config/feast:/app
    environment:
      AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
      AWS_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
      FEAST_S3_ENDPOINT_URL: http://minio:9000
    depends_on:
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: '0.5'
```

- [ ] **Step 4: Verify all services**

Run: `make core && sleep 10 && make topics buckets`
Run: `docker compose ps`
Expect: All core services healthy. Access `http://localhost:6566` in browser.

- [ ] **Step 5: Commit Feast**

```bash
git add services/feast/Dockerfile config/feast/feature_store.yaml docker-compose.yml
git commit -m "infra: add feast service with custom build"
```
