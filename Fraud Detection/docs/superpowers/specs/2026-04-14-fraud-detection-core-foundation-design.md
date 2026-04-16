# Design Spec: Fraud Detection Core Infrastructure Foundation (Phase 1)

**Status:** Approved
**Date:** 2026-04-14
**Topic:** Phase 1 — Core Infrastructure (Redpanda, Redis, MinIO, Feast)
**Target:** Local Docker Compose (V2)

## 1. Executive Summary
This phase establishes the foundational data layer for the Real-Time Behavioral Fraud Detection Engine. It implements a multi-network, containerized environment that strictly separates the "Act" (hot) and "Explain" (cold) paths. The goal is to provide a reliable, reproducible base for the subsequent stream processing and inference layers.

## 2. Architecture & Components

### 2.1 Network Topology
Four isolated bridge networks will be created to enforce traffic separation and security:
- `act-net`: Hot path for latency-critical operations (Redpanda, Redis, Feast).
- `explain-net`: Cold path for asynchronous processing and auditing (Redpanda, MinIO).
- `obs-net`: Observability traffic (future SigNoz/OTel).
- `mgmt-net`: Management and training traffic (future MLflow/Airflow).

### 2.2 Core Services (Profile: `core`)

| Service | Image | Role | Networks |
|---|---|---|---|
| `redpanda` | `redpandadata/redpanda:v24.1` | Message Broker + Schema Registry | `act-net`, `explain-net` |
| `redis` | `redis:7.2-alpine` | Online Feature Store | `act-net` |
| `minio` | `minio/minio:RELEASE.2024-04-06T05-26-02Z` | S3-compatible Offline Store | `explain-net`, `mgmt-net` |
| `feast` | Custom (Approach A) | Feature Store Abstraction / UI | `act-net` |

### 2.3 Automation & Init Containers
To ensure a "single-command" setup, we will use lightweight init-containers for bootstrapping:
- `init-redpanda`: Runs `rpk topic create` for all topics defined in Section 7 of `v2.0` guide.
- `init-minio`: Uses `mc` (MinIO Client) to create 4 buckets: `fraud-features-offline`, `fraud-audit-logs` (WORM enabled), `fraud-models`, `fraud-lineage`.

## 3. Data Strategy

### 3.1 Topic Inventory (Redpanda)
- `tx.raw.hot` (16 partitions)
- `tx.raw.cold` (8 partitions)
- `feature.update` (8 partitions)
- `decision.block` (4 partitions)
- `decision.allow` (4 partitions)
- `decision.review` (4 partitions)
- `decision.degraded` (2 partitions)
- `tx.dead-letter` (2 partitions)

### 3.2 Storage Configuration
- **Redis:** AOF (Append Only File) enabled for persistence. Keyspace notifications set to `Ex` (Expired) for future drift monitoring.
- **MinIO:** `fraud-audit-logs` bucket will have object locking (WORM) enabled to satisfy compliance requirements (EU AI Act/DORA).

## 4. Implementation Details

### 4.1 Custom Feast Image (`services/feast/Dockerfile`)
```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir "feast[redis]" "pyarrow"
WORKDIR /app
CMD ["feast", "ui", "--host", "0.0.0.0", "--port", "6566"]
```

### 4.2 Resource Limits (Core)
- Redpanda: 2g Mem, 2.0 CPU
- Redis: 512m Mem, 0.5 CPU
- MinIO: 512m Mem, 0.5 CPU
- Feast: 512m Mem, 0.5 CPU

## 5. Verification Plan
- **Orchestration:** `docker compose --profile core up -d` results in all containers in `healthy` state.
- **Messaging:** `docker exec redpanda rpk topic list` confirms all 8 topics exist.
- **Storage:** `docker exec minio mc ls local/` confirms all 4 buckets exist.
- **Feature Store:** Feast UI accessible at `http://localhost:6566`.

## 6. Success Criteria
- [ ] Base directory structure created.
- [ ] `.env` file populated with versioning and defaults.
- [ ] `docker-compose.yml` implements Section 2 networks and Section 2.2 services.
- [ ] Bootstrap scripts (`topics.sh`, `bootstrap.sh`) successfully execute via init-containers.
- [ ] All resource limits and health checks are verified.
