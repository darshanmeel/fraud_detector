# Design Spec: Fraud Detection Stream Processing Agents (Phase 2)

**Status:** Approved
**Date:** 2026-04-14
**Topic:** Phase 2 — Faust Stream Processing Agents
**Target:** Local Docker Compose (V2)

## 1. Executive Summary
This phase implements the "Intelligence Layer" of the Fraud Detection Engine. We will deploy four specialized, independent Faust agents that handle the hot path inference, feature store updates, compliance auditing, and drift monitoring. This design prioritizes isolation, stateful processing, and high-speed behavioral analysis.

## 2. Agent Architecture

### 2.1 Agent Roles & Topic Participation

| Agent | Responsibility | Ingress Topic(s) | Egress Topic(s) | Dependencies |
|---|---|---|---|---|
| `fraud-processor` | Core Inference Engine | `tx.raw.hot` | `decision.*` | Redpanda, Redis, Feast |
| `feature-store-writer`| Online Feature Sync | `feature.update`| - | Redpanda, Redis, Feast |
| `explain-consumer` | Audit & Explainability | `decision.block/review`| MinIO (Iceberg) | Redpanda, MinIO |
| `drift-monitor` | Real-time Observability | `tx.raw.hot`, `decision.*`| OTel Collector | Redpanda, OTel |

### 2.2 Data Flow (Hot Path)
1. **Ingress:** `fraud-processor` consumes a `TransactionEvent` from `tx.raw.hot`.
2. **Hydration:** Agent retrieves the `account_velocity` feature view from **Feast Online Store (Redis)**.
3. **Inference:** A heuristic "XGBoost-like" model processes the feature vector and generates a risk score (0.0 - 1.0).
4. **Action:** A `DecisionEnvelope` is emitted to the appropriate topic based on thresholds:
   - `< 0.3`: `decision.allow`
   - `0.3 - 0.7`: `decision.review`
   - `> 0.7`: `decision.block`

## 3. Implementation Details

### 3.1 Inference Engine (Phase 2 Mock)
We will implement a `HeuristicModel` class that mimics an XGBoost interface. It will use hardcoded behavioral rules for the prototype phase:
- **Velocity Burst:** If `txn_count_1m > 10` -> Score 0.9 (Block).
- **Amount Spike:** If `amount_cents > 5 * spend_avg_24h` -> Score 0.6 (Review).
- **Geo-Hop:** If `distinct_countries_24h > 2` -> Score 0.8 (Block).

### 3.2 Error Handling & Resiliency
- **Dead Letter Queue:** Any event failing schema validation or processing is routed to `tx.dead-letter` with an error reason header.
- **Degraded Mode:** If the Feature Store (Redis) is unreachable, the processor falls back to a "global mean" feature vector, sets `low_confidence=true` in the envelope, and routes the decision to `decision.degraded`.
- **Checkpointing:** Faust will use a host-mounted volume for RocksDB state to ensure exactly-once semantics and recovery after container restarts.

### 3.3 Base Docker Image (`services/base/Dockerfile`)
To optimize build times, we'll use a shared base image for all agents:
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "faust-streaming" "feast[redis]" "fastavro" "opentelemetry-sdk"
```

## 4. Testing & Verification Plan

### 4.1 Automated Tests
- **Unit Tests:** Verify the `HeuristicModel` logic against synthetic feature vectors.
- **Topology Tests:** Use `faust.testing` to verify the stream routing logic without requiring a live Redpanda cluster.

### 4.2 Manual Verification
1. Start agents: `docker compose --profile core up -d`.
2. Inject a "Happy Path" event using `rpk topic produce tx.raw.hot`.
3. Verify the decision appears in `decision.allow`.
4. Inject an "Anomaly" event (e.g., high amount).
5. Verify the decision appears in `decision.block` or `decision.review`.

## 5. Success Criteria
- [ ] Four independent Faust services defined in `docker-compose.yml`.
- [ ] Shared data models (Avro) implemented in `services/shared/`.
- [ ] `fraud-processor` successfully performs feature hydration from Redis.
- [ ] `explain-consumer` successfully writes audit records to MinIO.
- [ ] All agents emit OTLP traces to the `obs-net` (Otel Collector ready).
