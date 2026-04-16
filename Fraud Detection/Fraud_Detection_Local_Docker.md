# Real-Time Behavioral Fraud Detection Engine
## Local Docker Implementation Guide — v1.0

**Based on:** `Fraud_Detection_Architecture.md` (OSS Edition)
**SRS Reference:** `Fraud_Detection_SRS.pdf`
**Target:** Developer workstation running Docker Desktop / Docker Engine with Compose V2
**Status:** Documentation — No application code yet

---

## 1. Purpose & Scope

This document translates the 6-layer production architecture into a runnable local Docker Compose environment. It is the single source of truth for:

- Every Docker service, its configuration, and which agent owns it
- Every Kafka topic and its parameters
- Every Avro schema and its field definitions
- The startup sequence and health-check gates
- The latency budget adjusted for single-host Docker overhead
- Failure injection procedures and expected observable outcomes

### What This IS
A faithful OSS prototype of the production architecture that runs on a single developer machine. It lets engineers develop, integrate, and validate each system layer before any cloud infrastructure is provisioned.

### What This IS NOT
- A production deployment. No high-availability, no multi-node Kafka/Flink/Redis clusters.
- A performance benchmark against production SLAs. Latency targets are relaxed to 2× production budget (see Section 9).
- A security-hardened environment. mTLS, RBAC, and Vault are not configured locally.

---

## 2. Prerequisites

### Hardware
| Resource | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB (12 GB allocated to Docker) | 32 GB |
| CPU | 8 cores | 16 cores |
| Disk | 40 GB free | 100 GB SSD |
| OS | Windows 11 (WSL2), macOS 13+, Ubuntu 22.04+ | — |

### Software
| Tool | Version | Purpose |
|---|---|---|
| Docker Desktop / Engine | 4.28+ / 26+ | Container runtime |
| Docker Compose | V2 (bundled) | Service orchestration |
| Java | 17 LTS | Flink job compilation (host) |
| Python | 3.11+ | Simulator, MLflow scripts, SHAP |
| `kcat` (kafkacat) | Latest | Kafka topic inspection |
| `curl` | Any | API health checks |
| `jq` | 1.6+ | JSON output formatting |

### Reserved Ports
Ensure these ports are free on the host before starting:

| Port | Service |
|---|---|
| 9092 | Kafka broker |
| 9093 | Kafka controller (KRaft) |
| 8081 | Schema Registry |
| 8080 | Flink Job Manager UI |
| 6379 | Redis |
| 9000 | MinIO S3 API |
| 9001 | MinIO Console |
| 5432 | PostgreSQL |
| 5000 | MLflow UI |
| 9090 | Prometheus |
| 3000 | Grafana |
| 4317 | OTel Collector (gRPC) |
| 4318 | OTel Collector (HTTP) |
| 16686 | Jaeger UI |
| 3100 | Loki |
| 8082 | Airflow Web UI |

---

## 3. Repository Layout

```
fraud-detection-local/
│
├── docker-compose.yml                    # Master Compose file
├── Makefile                              # Convenience targets: up, down, reset, logs, status
├── .env                                  # Environment variable overrides
│
├── config/
│   ├── kafka/
│   │   ├── topics.sh                     # Topic creation script (run after Kafka starts)
│   │   └── server.properties             # KRaft mode overrides
│   ├── schema-registry/
│   │   └── schema-registry.properties
│   ├── flink/
│   │   ├── flink-conf.yaml               # Memory, parallelism, RocksDB settings
│   │   └── job-params.json               # Window sizes, thresholds (configurable)
│   ├── redis/
│   │   └── redis.conf                    # AOF persistence, keyspace notifications
│   ├── minio/
│   │   └── bootstrap.sh                  # Bucket creation script
│   ├── prometheus/
│   │   ├── prometheus.yml                # Scrape configs
│   │   └── alert-rules.yml               # SLO alert thresholds
│   ├── otel/
│   │   └── otel-collector-config.yaml    # Receivers, processors, exporters
│   ├── loki/
│   │   └── loki-config.yaml
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/              # Prometheus, Loki, Jaeger auto-provisioned
│       │   └── dashboards/               # Dashboard JSON auto-provisioned
│       └── dashboards/
│           ├── act-path-slo.json
│           ├── stage-latency.json
│           ├── infrastructure-health.json
│           ├── model-performance.json
│           └── compliance.json
│
├── schemas/
│   ├── TransactionEvent.avsc             # Raw input schema
│   ├── FeatureVector.avsc                # Assembled at inference
│   └── DecisionEnvelope.avsc            # Decision output schema
│
├── models/
│   └── README.md                         # How to register an ONNX model in MLflow
│
├── services/
│   ├── feature-store-writer/             # Consumes feature.update → writes Redis
│   ├── explain-consumer/                 # Consumes cold path → writes Iceberg
│   └── drift-monitor/                    # Consumes decision.* → computes PSI / KL
│
├── tools/
│   └── tx-simulator/                     # Transaction event generator (configurable TPS)
│
├── dags/
│   ├── fraud_label_joiner.py
│   ├── fraud_feature_engineering.py
│   ├── fraud_model_training.py
│   ├── fraud_shadow_deployment.py
│   └── fraud_model_promotion.py
│
└── agents/
    ├── 00-agent-overview.md
    ├── 01-infrastructure-agent.md
    ├── 02-ingestion-agent.md
    ├── 03-stream-processing-agent.md
    ├── 04-feature-store-agent.md
    ├── 05-inference-agent.md
    ├── 06-decision-action-agent.md
    ├── 07-observability-agent.md
    ├── 08-explain-compliance-agent.md
    ├── 09-model-governance-agent.md
    └── 10-testing-validation-agent.md
```

---

## 4. Docker Compose Architecture

### Network Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│  act-net (hot path — latency critical)                                  │
│                                                                         │
│  kafka ──► schema-registry                                              │
│    │                                                                    │
│    ▼                                                                    │
│  flink-jobmanager ──► flink-taskmanager ──► [inference sidecar]        │
│                              │                                          │
│                              ▼                                          │
│                           redis  ◄──── feature-store-writer            │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                    (feature.update topic)
                                │
┌─────────────────────────────────────────────────────────────────────────┐
│  explain-net (cold path — async, seconds SLA)                           │
│                                                                         │
│  kafka ──► explain-consumer ──► minio (Iceberg tables)                 │
│                │                                                        │
│                └──► drift-monitor ──► prometheus                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  obs-net (observability)                                                │
│                                                                         │
│  otel-collector ──► jaeger                                              │
│       │         └──► prometheus ──► grafana                             │
│       └──────────► loki ──────────► grafana                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  mgmt-net (management / training)                                       │
│                                                                         │
│  postgres ◄──── mlflow                                                  │
│     │      └──► minio (artifact store)                                  │
│     └────────── airflow-scheduler + airflow-webserver                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Service-to-Network Membership

| Service | act-net | explain-net | obs-net | mgmt-net |
|---|---|---|---|---|
| kafka | ✓ | ✓ | — | — |
| schema-registry | ✓ | — | — | — |
| flink-jobmanager | ✓ | ✓ | ✓ | — |
| flink-taskmanager | ✓ | ✓ | ✓ | — |
| redis | ✓ | — | ✓ | — |
| minio | — | ✓ | — | ✓ |
| postgres | — | — | — | ✓ |
| mlflow | — | — | — | ✓ |
| feature-store-writer | ✓ | — | ✓ | — |
| explain-consumer | — | ✓ | ✓ | — |
| drift-monitor | — | ✓ | ✓ | — |
| prometheus | — | — | ✓ | — |
| grafana | — | — | ✓ | — |
| otel-collector | ✓ | ✓ | ✓ | — |
| jaeger | — | — | ✓ | — |
| loki | — | — | ✓ | — |
| airflow-webserver | — | — | — | ✓ |
| airflow-scheduler | — | — | — | ✓ |

---

## 5. Service Reference

### 5.1 kafka
| Property | Value |
|---|---|
| Image | `apache/kafka:3.7` |
| Mode | KRaft (no Zookeeper) |
| Ports | `9092` (broker), `9093` (controller) |
| Network | act-net, explain-net |
| Owner | Infrastructure Agent + Ingestion Agent |
| Health check | `kafka-broker-api-versions.sh --bootstrap-server localhost:9092` |
| Startup log | `Kafka Server started` |
| Key env vars | `KAFKA_NODE_ID=1`, `KAFKA_PROCESS_ROLES=broker,controller`, `KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093` |
| Volumes | `kafka-data:/var/lib/kafka/data` |
| Local divergence | Single-node broker. Production: 3+ broker cluster with separate controllers. |

### 5.2 schema-registry
| Property | Value |
|---|---|
| Image | `confluentinc/cp-schema-registry:7.6` |
| Ports | `8081` |
| Network | act-net |
| Owner | Ingestion Agent |
| Depends on | kafka (healthy) |
| Health check | `curl -sf http://localhost:8081/subjects` |
| Startup log | `Server started, listening for requests` |
| Key env vars | `SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS=kafka:9092`, `SCHEMA_REGISTRY_HOST_NAME=schema-registry` |

### 5.3 flink-jobmanager
| Property | Value |
|---|---|
| Image | `flink:1.19-scala_2.12-java17` |
| Ports | `8080` (UI), `6123` (RPC) |
| Network | act-net, explain-net, obs-net |
| Owner | Stream Processing Agent |
| Depends on | kafka (healthy), redis (healthy) |
| Health check | `curl -sf http://localhost:8080/overview` |
| Startup log | `Starting the resource manager` |
| Key env vars | `JOB_MANAGER_RPC_ADDRESS=flink-jobmanager` |
| Command | `jobmanager` |

### 5.4 flink-taskmanager
| Property | Value |
|---|---|
| Image | `flink:1.19-scala_2.12-java17` |
| Ports | `6121` (data), `6122` (IPC) |
| Network | act-net, explain-net, obs-net |
| Owner | Stream Processing Agent |
| Depends on | flink-jobmanager (healthy) |
| Health check | `curl -sf http://flink-jobmanager:8080/taskmanagers` |
| Key env vars | `JOB_MANAGER_RPC_ADDRESS=flink-jobmanager`, `TASK_MANAGER_NUMBER_OF_TASK_SLOTS=4` |
| Command | `taskmanager` |
| Local divergence | 1 TaskManager with 4 slots. Production: N TaskManagers, 128 slots total per 10K TPS. |

### 5.5 redis
| Property | Value |
|---|---|
| Image | `redis:7.2-alpine` |
| Ports | `6379` |
| Network | act-net, obs-net |
| Owner | Feature Store Agent |
| Health check | `redis-cli ping` |
| Startup log | `Ready to accept connections` |
| Config | `redis.conf` mounted; AOF enabled; keyspace notifications: `Ex` (expired events) |
| Volumes | `redis-data:/data` |
| Local divergence | Standalone instance. Production: Redis Cluster (3+ primaries, 3 replicas). |

### 5.6 minio
| Property | Value |
|---|---|
| Image | `minio/minio:RELEASE.2024-04-06T05-26-02Z` |
| Ports | `9000` (S3 API), `9001` (console) |
| Network | explain-net, mgmt-net |
| Owner | Feature Store Agent |
| Health check | `curl -sf http://localhost:9000/minio/health/live` |
| Command | `server /data --console-address :9001` |
| Volumes | `minio-data:/data` |
| Buckets (created by bootstrap) | `fraud-features-offline`, `fraud-audit-logs` (WORM), `fraud-models`, `fraud-lineage` |

### 5.7 postgres
| Property | Value |
|---|---|
| Image | `postgres:16-alpine` |
| Ports | `5432` |
| Network | mgmt-net |
| Owner | Infrastructure Agent |
| Health check | `pg_isready -U fraud` |
| Databases | `mlflow`, `airflow`, `hive_metastore` |
| Volumes | `postgres-data:/var/lib/postgresql/data` |

### 5.8 mlflow
| Property | Value |
|---|---|
| Image | `ghcr.io/mlflow/mlflow:v2.12.1` |
| Ports | `5000` |
| Network | mgmt-net |
| Owner | Inference Agent |
| Depends on | postgres (healthy), minio (healthy) |
| Health check | `curl -sf http://localhost:5000/health` |
| Key env vars | `MLFLOW_BACKEND_STORE_URI=postgresql://fraud:fraud@postgres/mlflow`, `MLFLOW_ARTIFACT_ROOT=s3://fraud-models/` |
| Startup log | `Serving on http://0.0.0.0:5000` |

### 5.9 prometheus
| Property | Value |
|---|---|
| Image | `prom/prometheus:v2.51.2` |
| Ports | `9090` |
| Network | obs-net |
| Owner | Observability Agent |
| Config | `config/prometheus/prometheus.yml` |
| Volumes | `prometheus-data:/prometheus` |

### 5.10 grafana
| Property | Value |
|---|---|
| Image | `grafana/grafana:10.4.2` |
| Ports | `3000` |
| Network | obs-net |
| Owner | Observability Agent |
| Depends on | prometheus, loki, jaeger |
| Default credentials | `admin / fraud-local` |
| Volumes | `grafana-data:/var/lib/grafana` |

### 5.11 otel-collector
| Property | Value |
|---|---|
| Image | `otel/opentelemetry-collector-contrib:0.99.0` |
| Ports | `4317` (gRPC), `4318` (HTTP) |
| Network | act-net, explain-net, obs-net |
| Owner | Observability Agent |
| Config | `config/otel/otel-collector-config.yaml` |

### 5.12 jaeger
| Property | Value |
|---|---|
| Image | `jaegertracing/all-in-one:1.56` |
| Ports | `16686` (UI), `14250` (gRPC collector) |
| Network | obs-net |
| Owner | Observability Agent |
| Local divergence | All-in-one mode. Production: separate collector, query, storage (Elasticsearch/Cassandra). |

### 5.13 loki
| Property | Value |
|---|---|
| Image | `grafana/loki:2.9.8` |
| Ports | `3100` |
| Network | obs-net |
| Owner | Observability Agent |
| Config | `config/loki/loki-config.yaml` |

### 5.14 airflow-webserver & airflow-scheduler
| Property | Value |
|---|---|
| Image | `apache/airflow:2.9.1-python3.11` |
| Ports | `8082` (webserver only) |
| Network | mgmt-net |
| Owner | Model Governance Agent |
| Depends on | postgres (healthy), minio (healthy) |
| Volumes | `airflow-dags:/opt/airflow/dags` |
| Default credentials | `admin / fraud-local` |

---

## 6. Startup Sequence

Boot services in groups, waiting for all health checks in a group to pass before starting the next.

```
GROUP 1 — Foundation (no dependencies)
  postgres
  minio
  redis

GROUP 2 — Message Bus (depends on postgres)
  kafka (KRaft — no Zookeeper needed)

GROUP 3 — Schema Layer (depends on kafka)
  schema-registry

GROUP 4 — Application Services (depends on kafka, redis, postgres, minio)
  mlflow
  flink-jobmanager

GROUP 5 — Processing (depends on flink-jobmanager)
  flink-taskmanager

GROUP 6 — Custom Services (depends on kafka, redis, minio)
  feature-store-writer
  explain-consumer
  drift-monitor

GROUP 7 — Observability (depends on infrastructure being up)
  otel-collector
  prometheus
  loki
  jaeger
  grafana

GROUP 8 — Orchestration (depends on postgres, minio)
  airflow-scheduler
  airflow-webserver
```

**Makefile targets:**
```
make up          # Start all services in order
make down        # Stop all services (preserve volumes)
make reset       # Stop + remove volumes (clean slate)
make logs        # Tail logs for all services
make status      # docker compose ps with health status
make topics      # Create all Kafka topics (run after GROUP 2)
make schemas     # Register all Avro schemas (run after GROUP 3)
make buckets     # Create MinIO buckets (run after GROUP 1)
```

---

## 7. Kafka Topic Inventory

All topics use `account_id` as the partition key unless noted.

| Topic | Partitions | Retention | Replication | Consumer Groups | Description |
|---|---|---|---|---|---|
| `tx.raw.hot` | 64 | 2 hours | 1 (local) | `flink-act-path` | Hot path — real-time inference |
| `tx.raw.cold` | 32 | 7 days | 1 (local) | `flink-explain-path` | Cold path — offline lake, audit |
| `feature.update` | 32 | 1 hour | 1 (local) | `feature-store-writer` | Feature delta events → Redis |
| `decision.block` | 16 | 30 days | 1 (local) | `fraud-case-mgmt`, `drift-monitor`, `explain-consumer` | Blocked transactions |
| `decision.allow` | 16 | 24 hours | 1 (local) | `drift-monitor` | Approved transactions |
| `decision.review` | 16 | 30 days | 1 (local) | `human-review`, `drift-monitor`, `explain-consumer` | Flagged for manual review |
| `decision.degraded` | 8 | 30 days | 1 (local) | `fraud-case-mgmt`, `explain-consumer` | Degraded-mode decisions |
| `tx.dead-letter` | 8 | 7 days | 1 (local) | `manual-remediation` | Schema-rejected / shed events |

**Local divergence:** Replication factor 1 on all topics (single broker). Production: replication factor 3, `min.insync.replicas=2`.

---

## 8. Avro Schema Definitions

Schemas are registered in Schema Registry under the naming convention `{subject}.{version}`.

### 8.1 TransactionEvent (subject: `tx-raw-value`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `transaction_id` | string | No | UUID v4 — unique per event |
| `source_system` | string | No | `mobile`, `web`, `gateway-{name}` |
| `account_id` | string | No | Primary partition key |
| `device_id` | string | Yes | Null for web/gateway sources |
| `ip_address` | string | Yes | IPv4 or IPv6 |
| `merchant_id` | string | No | |
| `merchant_category` | string | No | MCC code |
| `amount_cents` | long | No | Transaction amount in smallest currency unit |
| `currency` | string | No | ISO 4217 code |
| `country_code` | string | No | ISO 3166-1 alpha-2 |
| `event_timestamp` | long | No | Unix epoch milliseconds (event-time) |
| `ingestion_timestamp` | long | No | Unix epoch milliseconds (processing-time) |
| `source_system_hash` | string | No | SHA-256 of `transaction_id + source_system` (deduplication key) |

### 8.2 FeatureVector (subject: `feature-vector-value`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `entity_id` | string | No | `account:{account_id}` |
| `schema_version` | string | No | Must match model's pinned schema version |
| `feature_timestamp` | long | No | Timestamp of most recent contributing event |
| `txn_count_1m` | double | No | Transaction count in last 1 minute |
| `txn_count_5m` | double | No | Transaction count in last 5 minutes |
| `txn_count_15m` | double | No | Transaction count in last 15 minutes |
| `txn_count_1h` | double | No | Transaction count in last 1 hour |
| `txn_count_24h` | double | No | Transaction count in last 24 hours |
| `spend_sum_1m` | double | No | Sum of amounts in last 1 minute |
| `spend_sum_5m` | double | No | Sum of amounts in last 5 minutes |
| `spend_sum_1h` | double | No | Sum of amounts in last 1 hour |
| `spend_avg_24h` | double | No | Rolling spend average over 24 hours |
| `distinct_merchants_1h` | int | No | Unique merchants in last 1 hour |
| `distinct_countries_24h` | int | No | Unique countries in last 24 hours |
| `distinct_devices_24h` | int | No | Unique device IDs in last 24 hours |
| `session_txn_count` | int | No | Transactions in current session (30m inactivity gap) |
| `session_duration_s` | double | No | Current session duration in seconds |
| `low_confidence` | boolean | No | True if cold-start or TTL expiry (prior profile used) |

### 8.3 DecisionEnvelope (subject: `decision-value`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `transaction_id` | string | No | Correlates to TransactionEvent |
| `source_correlation_id` | string | No | End-to-end trace ID |
| `decision` | enum | No | `ALLOW`, `REVIEW`, `BLOCK`, `DEGRADED_BLOCK` |
| `risk_score` | double | No | 0.0 (low risk) – 1.0 (high risk) |
| `confidence_lower` | double | No | Lower bound of confidence band |
| `confidence_upper` | double | No | Upper bound of confidence band |
| `model_version` | string | No | MLflow model version tag |
| `feature_schema_version` | string | No | Schema Registry schema version |
| `processing_ts` | long | No | Unix epoch milliseconds |
| `latency_ingestion_us` | long | No | Ingestion stage duration (microseconds) |
| `latency_feature_us` | long | No | Feature hydration duration (microseconds) |
| `latency_inference_us` | long | No | Inference scoring duration (microseconds) |
| `latency_emission_us` | long | No | Action emission duration (microseconds) |
| `latency_total_us` | long | No | Sum of all stages (microseconds) |
| `low_confidence` | boolean | No | True if prior profile used |
| `flags` | array[string] | No | e.g., `cold_start`, `degraded_mode`, `challenger_scored` |

---

## 9. Latency Budget — Local Docker

**Local target: <60ms P99** (2× production budget — single host, Docker bridge network overhead, no kernel bypass, no NUMA pinning)

| Stage | Component | Local P99 Target | Production P99 Target | Notes |
|---|---|---|---|---|
| Ingestion & Schema Validation | Kafka + Schema Registry | 4–6ms | 2–3ms | Docker bridge overhead |
| Internal Bus Transit | Topic → Consumer | 2ms | 1ms | |
| Feature Retrieval (Redis) | Pipeline HGETALL | 3–5ms | 4–6ms | Faster locally (no network hop) |
| Feature Vector Assembly | In-process | <1ms | <0.5ms | |
| Inference (ONNX, CPU) | ONNX Runtime | 8–15ms | 6–10ms | No GPU locally |
| Decision Envelope Construction | In-process | <1ms | <0.5ms | |
| Action Emission | Kafka produce + sync response | 4–6ms | 2–3ms | |
| **Total** | | **~22–36ms** | **~16–24ms** | **Local headroom: 24–38ms** |

**Measuring latency locally:**
- Query Jaeger UI at `http://localhost:16686`, search by service `fraud-inference`, look for traces with service span tags `latency_total_us`
- Query Prometheus: `histogram_quantile(0.99, fraud_e2e_latency_ms_bucket)`
- The `latency_trace` fields in `DecisionEnvelope` give per-transaction microsecond breakdowns

---

## 10. Redis Feature Store — Key Schema

```
Outer key:    feat:{entity_type}:{entity_id}
              e.g., feat:account:acc-8821af3c

Inner fields: (hash map — HGETALL in single round-trip)
  txn_count_1m      → double (string-encoded float)
  txn_count_5m      → double
  txn_count_15m     → double
  txn_count_1h      → double
  txn_count_24h     → double
  spend_sum_1m      → double
  spend_sum_5m      → double
  spend_sum_1h      → double
  spend_avg_24h     → double
  distinct_merchants_1h  → int
  distinct_countries_24h → int
  distinct_devices_24h   → int
  session_txn_count → int
  session_duration_s → double
  schema_version    → string (e.g., "1.0")
  feature_timestamp → long (epoch ms)

TTL:  72 hours (259200 seconds)
      Set/refreshed on every HSET write

On MISS (new entity or expired):
  → Return prior_profile defaults (all zeros except schema_version)
  → Set low_confidence=true in FeatureVector
  → Trigger async pre-fetch from Offline Store (non-blocking)
```

---

## 11. MinIO Bucket & Iceberg Table Inventory

### Buckets

| Bucket | Purpose | WORM | Lifecycle |
|---|---|---|---|
| `fraud-features-offline` | Historical feature snapshots (Iceberg) | No | 90 days |
| `fraud-audit-logs` | Immutable decision + explain records (Iceberg) | **Yes** | 7 years |
| `fraud-models` | MLflow model artifacts (ONNX files, metadata) | No | Indefinite |
| `fraud-lineage` | OpenLineage facets, data provenance | No | 2 years |

### Iceberg Tables

| Table | Partition Spec | Description |
|---|---|---|
| `fraud_features.entity_features` | `date(feature_timestamp), entity_id_prefix(4)` | Historical feature snapshots from stream |
| `fraud_audit.decision_log` | `date(processing_ts), decision` | Every DecisionEnvelope produced |
| `fraud_audit.explain_log` | `date(processing_ts)` | SHAP values + counterfactuals (async) |
| `fraud_training.labeled_dataset` | `date(label_join_ts)` | Point-in-time correct training rows |

---

## 12. Failure Injection Procedures

These procedures test the failure modes defined in Section 6 of the Architecture document.

### 12.1 Feature Store Unavailable
```bash
docker pause redis
# Expected: feature.update writes queue in kafka; inference uses prior_profile
# Expected: DecisionEnvelope has low_confidence=true, flags includes "degraded_mode"
# Expected: Prometheus alert "FeatureStoreReadHighLatency" fires within 30s
docker unpause redis
# Expected: Backlog clears; low_confidence returns to false for known entities
```

### 12.2 Inference Sidecar Crash
```bash
# Simulate by stopping taskmanager (sidecar co-located)
docker kill fraud-detection-local-flink-taskmanager-1
# Expected: Flink rebalances partitions to remaining slots within 10–30s
# Expected: Processing gap visible in Kafka consumer lag metric
# Expected: On-call alert "FlinkCheckpointFailure" fires
docker compose up -d flink-taskmanager
# Expected: Job resumes from last checkpoint; no events lost
```

### 12.3 Schema Mismatch
```bash
# Produce an event with a missing required field via kcat:
echo '{"transaction_id":"test","amount_cents":100}' | \
  kcat -P -b localhost:9092 -t tx.raw.hot -s avro \
  -r http://localhost:8081
# Expected: Schema Registry rejects; event routes to tx.dead-letter
# Expected: No inference attempted; no BLOCK/ALLOW emitted
```

### 12.4 Downstream Consumer Down
```bash
docker pause fraud-detection-local-explain-consumer-1
# Expected: decision.block topic depth increases (consumer lag)
# Expected: Act path UNAFFECTED — decisions still emit to topic
# Expected: Circuit breaker opens for explain-consumer downstream
docker unpause fraud-detection-local-explain-consumer-1
# Expected: Lag clears; explain records written to Iceberg
```

---

## 13. Compliance Checklist — Local Validation

| EU AI Act / DORA Requirement | Local Implementation | Validated By |
|---|---|---|
| Auditability of AI decisions | `fraud_audit.decision_log` Iceberg table | Explain Agent |
| Explainability (SHAP) | `fraud_audit.explain_log` with SHAP values | Explain Agent |
| Human oversight (`REVIEW` class) | Decision routes to `decision.review` topic | Decision Agent |
| Data lineage | OpenLineage facets in `fraud-lineage` bucket | Governance Agent |
| Model documentation (model card) | MLflow experiment description + tags | Inference Agent |
| Bias / fairness report | Drift Monitor PSI by merchant category proxy | Governance Agent |
| Incident logging | Prometheus alert → Grafana annotation | Observability Agent |
| Right to explanation (GDPR Art. 22) | `GET /audit/transaction/{id}` query API | Explain Agent |
| Data retention (7 years) | `fraud-audit-logs` bucket lifecycle policy | Feature Store Agent |
| Rollback capability | MLflow re-tag + Flink hot-reload | Inference Agent |

---

*Document Owner: Lead Application Architect*
*Implementation: Multi-agent Docker local prototype*
*Review cycle: After each agent completes their implementation phase*
*Classification: Internal — Implementation*
