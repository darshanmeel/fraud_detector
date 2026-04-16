# Real-Time Behavioral Fraud Detection Engine
## Architecture Design Document — v1.0

**Scope:** End-to-end system architecture for a sub-30ms, 5K–15K TPS behavioral fraud detection platform.
**Editions:** Open Source (OSS) and Enterprise. Where they differ, both are called out explicitly.
**Constraints:** No code. No vendor lock-in mandated. DORA / EU AI Act compliant.

---

## 1. Architectural Philosophy

The system is built on three axioms:

1. **The hot path must be stateless at inference time.** All state (features, model weights, thresholds) must be pre-materialized before a transaction arrives.
2. **Act fast, explain later.** The <30ms "Act" path and the compliance "Explain" path are physically separated at the event bus level—never in the same execution context.
3. **Degrade gracefully, never silently.** Every component publishes a health signal. The failure posture is a deliberate, observable choice—not an accident.

---

## 2. High-Level Layer Description

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — INGESTION                                    │
│  Event Intake · Schema Validation · Deduplication       │
├─────────────────────────────────────────────────────────┤
│  LAYER 2 — STREAM TRANSFORMATION (Kappa)                │
│  Windowed Aggregation · Feature Delta Computation       │
├─────────────────────────────────────────────────────────┤
│  LAYER 3 — DUAL-TIER STORAGE                            │
│  Online Feature Store (μs reads) · Offline Lake (batch) │
├─────────────────────────────────────────────────────────┤
│  LAYER 4 — INFERENCE                                    │
│  Sidecar Model Runtime · Champion/Challenger Routing    │
├─────────────────────────────────────────────────────────┤
│  LAYER 5 — ACTION                                       │
│  Decision Emission · Downstream Routing · Circuit Break │
├──────────────────────────┬──────────────────────────────┤
│  LAYER 6a — ACT PATH     │  LAYER 6b — EXPLAIN PATH    │
│  Synchronous (<30ms)     │  Async (seconds–minutes)    │
│  Block / Allow / Review  │  SHAP · Audit Log · DORA    │
└──────────────────────────┴──────────────────────────────┘
```

---

## 3. Layer Detail

### Layer 1 — Ingestion

**Responsibilities:**
- Accept raw transaction events from payment rails, mobile SDK, and internal services
- Enforce schema contracts at the boundary (Avro or Protobuf schemas pinned to a Schema Registry)
- Idempotent deduplication via an at-most-once key (transaction ID + source system hash) backed by a short-TTL bloom filter
- Produce to two partitioned topics: `tx.raw.hot` (Act path) and `tx.raw.cold` (Explain/Lake path)

**Partitioning Key:** Account entity ID — ensures all events for a single behavioral profile land on the same partition, enabling ordered processing without cross-partition coordination.

**Back-pressure:** Ingestion nodes expose a load-shedding contract. At >90% queue depth, events are marked with a `shed` flag and routed to a dead-letter topic for deferred processing. This is never silent — it triggers an SLO alert.

**OSS:** Apache Kafka + Confluent Schema Registry (community) + Kafka Streams for edge deduplication
**Enterprise:** Confluent Platform / IBM Event Streams + Apicurio Registry

---

### Layer 2 — Stream Transformation (Kappa Architecture)

The system uses a pure **Kappa Architecture** — one streaming pipeline for both real-time and historical reprocessing. There is no Lambda dual-path. Historical reprocessing is achieved by replaying the `tx.raw.hot` topic from offset zero with a separate consumer group.

**Windowed Feature Computation:**
- Tumbling windows (1m, 5m, 15m, 1h, 24h) computed per entity
- Sliding windows for velocity metrics (e.g., txn count in last 10 minutes, rolling spend average)
- Session windows for behavioral session modeling (inactivity gap = 30 minutes)

**State Management Strategy (critical — see Section 4):**
- Window state is stored in an embedded RocksDB state store local to each stream processor node (LSM-tree backed, sequential write optimized)
- State is changelog-backed to the event bus for fault recovery — no external state store round-trips in the hot path
- Watermarks with a 2-second allowed lateness prevent window recomputation from late-arriving events disrupting the hot path

**Feature Delta Emission:**
- On each window close or significant delta trigger (configurable threshold), a `feature.update` event is emitted
- This is consumed by the Online Feature Store writer — keeping the store eventually consistent without polling

**OSS:** Apache Flink (with RocksDB state backend) + Kafka Streams for lightweight entity-level aggregations
**Enterprise:** Hazelcast Jet / Ksqldb for stateful transforms + Confluent Platform

---

### Layer 3 — Dual-Tier Storage

Two entirely separate storage tiers serve different latency SLAs and access patterns.

#### Online Feature Store (Act Path — μs reads)
- In-memory Key-Value store organized by entity key (account ID, device ID, merchant ID)
- Data structure: hash-of-hashes — one outer key per entity, inner keys per feature vector dimension
- Reads must be single round-trip (pipeline all feature keys in one command)
- TTL-managed: features expire if no event is seen for the entity within 72 hours (reduces memory footprint, forces cold-start handling)
- Persistence: AOF or equivalent write-ahead log for fast restart; snapshot for warm boot

**Cold Start Handling:** On a cache miss (new entity or TTL expiry), the inference layer fetches a "prior profile" from the Offline Store via an async pre-fetch, applies conservative default thresholds, and flags the decision as `low-confidence` in the audit envelope.

**OSS:** Redis (cluster mode) / Apache Ignite / Aerospike (community)
**Enterprise:** Aerospike Enterprise / Redis Enterprise / Tecton Online Store

#### Offline Feature Store / Data Lake (Explain Path — seconds)
- Columnar format (Parquet / ORC) partitioned by date and entity_id prefix
- Stores full feature history, raw events, model input vectors, and decision outputs
- Serves: model retraining, drift analysis, regulatory audit queries, explainability reconstruction
- Schema-on-read with a governed catalog

**OSS:** Apache Iceberg on object storage (MinIO / S3-compatible) + Apache Hive Metastore
**Enterprise:** Databricks Delta Lake / Cloudera Data Platform / Snowflake (with Iceberg open table format)

---

### Layer 4 — Inference

**Sidecar Inference Pattern:**
- Each inference node runs a **sidecar model runtime** co-located with the stream processor — not a remote gRPC call
- Eliminates network hop for inference; model is loaded into the same memory space or on a local socket
- Model weights are read-only memory-mapped files; updated atomically via a model artifact registry publish/subscribe event

**Model Format:** ONNX as the canonical interchange format — both OSS and enterprise runtimes consume it. This decouples training framework (XGBoost, LightGBM, PyTorch, scikit-learn) from the serving runtime.

**Champion / Challenger Routing:**
- Traffic split at the inference layer: 95% Champion, 5% Challenger (configurable)
- Both models score every transaction routed to them; only the Champion's output drives the Act decision
- Challenger scores are emitted asynchronously to the Explain path for comparison
- Promotion is a controlled event: model artifact is re-tagged; stream processors hot-reload via file watch — no restart required

**Feature Hydration at Inference:**
- The inference node receives the raw transaction event plus a feature key
- It issues a single pipelined read to the Online Feature Store (Layer 3)
- The hydrated feature vector is assembled in-process before scoring
- Feature schema is version-pinned to the model version via the Schema Registry — mismatches are a hard rejection, not a silent error

**OSS:** ONNX Runtime (CPU/GPU) + Triton Inference Server (self-hosted) + MLflow Model Registry
**Enterprise:** DataRobot MLOps / Azure ML Managed Endpoints / SageMaker Real-Time Inference + MLflow (Databricks-managed)

---

### Layer 5 — Action Emission

**Decision Envelope:**
Every decision emitted from Layer 4 is wrapped in a structured envelope containing:
- Transaction ID + source correlation ID
- Decision: `BLOCK` / `ALLOW` / `REVIEW`
- Risk score (0.0–1.0) with confidence band
- Model version + feature schema version
- Processing timestamp + latency trace (per-stage microsecond breakdowns)
- `low-confidence` flag (set on cold-start or degraded mode)

**Routing:**
- `BLOCK` → synchronous rejection response to upstream caller + publish to `decision.block` topic
- `ALLOW` → synchronous pass-through + publish to `decision.allow` topic
- `REVIEW` → synchronous pass-through with friction signal + publish to `decision.review` topic (triggers async human review workflow)

**Downstream consumers** of decision topics: fraud case management, customer notification service, model feedback loop, regulatory reporting pipeline.

**Circuit Breaker (per downstream):**
- Each downstream consumer has a circuit breaker in front of it
- Open circuit → decisions buffer to a durable topic; downstream catches up when circuit closes
- The Act path itself is never blocked waiting for a downstream to acknowledge

---

## 4. State Management Strategy — Deep Dive

The bottleneck risk is windowed state at high TPS. Mitigation is layered:

**Layer A — Partition Affinity:** Kafka/Flink partition key = entity ID. All events for one entity process sequentially on one node. No cross-node state coordination.

**Layer B — Local State (RocksDB / LSM-tree):** State is on-disk on the stream processor node. LSM-tree's sequential write pattern handles the write throughput. Reads hit the in-memory memtable for recent windows (sub-millisecond).

**Layer C — Incremental Aggregation:** Windows are never recomputed from raw events on every message. Partial aggregates (count, sum, min, max) are maintained incrementally. Only the delta is computed per event.

**Layer D — Async Feature Store Sync:** The Online Feature Store write is not in the critical path. The stream processor emits a `feature.update` event asynchronously. A dedicated Feature Store Writer service consumes this and performs the store write — isolated from the Act path latency budget.

**Layer E — Watermarks + Allowed Lateness:** Late-arriving events (network jitter, mobile offline transactions) are handled by a 2-second allowed lateness window. They update state correctly but do not block active processing.

**Projected State Memory per Node:** ~500MB–2GB depending on window count and entity cardinality. Horizontal scaling (more partitions = more nodes) linearly extends total state capacity.

---

## 5. The "Act vs. Explain" Split

This is a first-class architectural concern, not a logging afterthought.

### Act Path (Synchronous — <30ms SLA)
```
Ingestion → tx.raw.hot topic → Stream Processor (feature delta) → 
Inference Sidecar (feature hydration + model score) → 
Decision Envelope → Action Emission → Response to caller
```
- Completely synchronous end-to-end
- No I/O to the Offline Lake
- No SHAP computation
- No audit log write (fire-and-forget to durable topic)
- Single thread of execution per transaction

### Explain Path (Asynchronous — SLA: seconds to minutes)
```
tx.raw.cold topic + decision.* topics → 
Explain Consumer (reconstruct feature vector from Offline Store) → 
SHAP / LIME explainability runtime → 
Audit Record Writer → 
Compliance Data Store (queryable, immutable, append-only)
```

**What the Audit Record Contains (EU AI Act / DORA requirements):**
- Full input feature vector (not just the decision)
- Model version, training dataset hash, model card reference
- Counterfactual: "what would have changed the decision" (top-3 feature deltas)
- Human-readable explanation text (generated by a secondary LLM or template engine — not in the Act path)
- Data lineage trace: which source events contributed to each feature value
- Retention: 7 years (configurable by jurisdiction), stored in immutable append-only storage

**Compliance Queryability:** Regulators and internal audit teams query the Compliance Data Store via a governed API — never directly against the Act path systems. The query interface supports: transaction lookup by ID, entity-level decision history, model performance reports by time window, and bias/fairness metric exports.

**OSS Explain Stack:** Apache Flink (consumer) + SHAP (offline) + Apache Iceberg (audit store) + OpenLineage (data lineage) + Apache Atlas (governance catalog)
**Enterprise Explain Stack:** Informatica / Collibra (governance) + DataRobot Explainability + Databricks Unity Catalog + IBM OpenPages (regulatory reporting)

---

## 6. Failure Modes — Fail-Open vs. Fail-Closed

**Design Principle:** The failure posture is a business decision, not a technical default. The system supports both modes, configurable per transaction type, merchant category, or risk tier.

### Failure Scenarios and Responses

| Failure | Fail-Open Behavior | Fail-Closed Behavior |
|---|---|---|
| Online Feature Store unreachable | Use degraded prior profile + flag `low-confidence` | BLOCK transaction; emit `DEGRADED_BLOCK` |
| Inference sidecar crash | Route to fallback rule engine (deterministic, low-latency) | BLOCK; page on-call; circuit opens |
| Stream processor node loss | Kafka rebalance; surviving nodes absorb partitions | Same; auto-rebalance within 10–30s |
| Schema mismatch (model vs. feature) | Reject event to dead-letter; do not score | Same — this is always Fail-Closed |
| Downstream action consumer down | Buffer decisions in durable topic; no Act path impact | Same — downstream failure never blocks Act path |
| Cluster partition (split-brain) | Each partition operates independently; reconcile on heal | Majority partition operates; minority sheds load |

**Cluster Partition — Detailed:**
In a network partition, the majority quorum (>N/2 nodes) continues processing. The minority partition sheds load: all incoming transactions receive a synthetic `REVIEW` decision (neither blocked nor approved without data) and are buffered. On partition heal, the minority replays from its last committed offset. No data is lost; the Act path SLA degrades gracefully for the minority's traffic.

**Degraded Mode Signaling:**
All `low-confidence` and `DEGRADED_BLOCK` decisions are tagged distinctly in the decision envelope. Downstream systems (fraud ops, customer notification) have conditional logic for these tags — e.g., a `low-confidence BLOCK` may trigger a soft block with a customer verification challenge rather than a hard decline.

**Runbook Trigger Thresholds (SLO-based):**
- Feature Store read P99 > 8ms → alert; degrade to prior profile
- Inference P99 > 15ms → alert; evaluate sidecar health
- End-to-end P99 > 25ms → page; investigate all stages
- End-to-end P99 > 30ms (SLA breach) → incident declared; automatic load shedding at 110% capacity

---

## 7. Latency Budget — P99 Breakdown

**Target: < 30ms end-to-end P99**

| Stage | Component | OSS P99 | Enterprise P99 | Notes |
|---|---|---|---|---|
| Ingestion & Schema Validation | Kafka producer + Schema Registry validation | 2–3ms | 1–2ms | Network + broker write |
| Internal Bus Transit | Topic produce → consumer assignment | 1ms | <1ms | Co-located brokers |
| Feature Retrieval / Hydration | Online KV store pipelined read | 4–6ms | 2–4ms | Single round-trip, pipelined keys |
| Feature Vector Assembly | In-process construction | <0.5ms | <0.5ms | CPU only, no I/O |
| Inference Runtime | ONNX model score (GBT, ~500 trees) | 6–10ms | 4–8ms | CPU inference; GPU shaves 2–4ms |
| Decision Envelope Construction | In-process serialization | <0.5ms | <0.5ms | |
| Action Emission | Async Kafka produce + sync response to caller | 2–3ms | 1–2ms | Fire-and-forget to topic |
| **Total Budget** | | **~16–24ms** | **~10–18ms** | **Headroom: 6–14ms** |

**P99 Headroom Usage:**
The 6–14ms headroom absorbs: GC pauses (JVM-based runtimes), kernel scheduling jitter, occasional cold cache reads, and network variance. For OSS deployments, JVM GC tuning (ZGC or Shenandoah) is critical to keep GC pauses below 5ms P99.

**GPU Inference Note:** GPU inference (ONNX Runtime with CUDA) reduces model score time to 1–3ms but introduces GPU scheduling latency of 1–2ms. Net benefit: ~3ms. Only justified if P99 headroom is consistently below 5ms.

---

## 8. Additional Architecture Concerns (Architect's Additions)

### 8.1 Model Governance & Versioning Pipeline

A fraud model without governance is a regulatory liability. The following pipeline is mandatory:

- **Model Registry:** Every model artifact is registered with: training data hash, evaluation metrics (AUC, KS statistic, false positive rate by segment), bias/fairness report (performance parity across demographic proxies), and a signed approval record
- **Promotion Gates:** Models cannot be promoted to Champion without passing: offline evaluation threshold, shadow mode comparison (7-day minimum), and a human sign-off workflow
- **Rollback:** Champion can be rolled back to any prior version in <60 seconds via a re-tag event; stream processors hot-reload

### 8.2 Data Drift & Model Decay Detection

- A dedicated **Drift Monitor** service consumes the `decision.*` topics and computes:
  - Feature distribution drift (PSI — Population Stability Index per feature, daily)
  - Score distribution drift (KL divergence on risk score histograms)
  - False positive / false negative rate (where ground truth is available from fraud chargebacks)
- Drift beyond configurable thresholds triggers a retraining pipeline trigger and an alert to the ML team
- **Ground Truth Latency:** Fraud chargebacks arrive 30–90 days after the transaction. The feedback loop is designed for delayed label ingestion — model evaluation windows are always lagged by a configurable offset

### 8.3 Feedback Loop & Retraining Pipeline

```
Fraud Chargeback Events → Label Joiner (match to original decision by transaction ID) →
Labeled Training Dataset (Offline Lake) → 
Feature Engineering Pipeline (batch, daily/weekly) →
Model Training (distributed compute) →
Model Registry (gated) →
Shadow Deployment → Champion Promotion
```

The Label Joiner handles the temporal mismatch between prediction (real-time) and label (delayed). It performs a point-in-time correct join — features used at prediction time, not current features, are used for training. This prevents target leakage.

### 8.4 Multi-Entity Behavioral Graph (Enhancement)

Standard behavioral fraud detection models transactions per account. Sophisticated fraud rings operate across entities. The architecture includes an optional **Behavioral Graph Layer**:

- Entity nodes: accounts, devices, IP addresses, merchants, card numbers, physical addresses
- Edges: shared usage events (same device used by two accounts = edge)
- Graph features (degree centrality, community membership, connected component size) are pre-computed in a graph processing engine on a 1-hour micro-batch cadence
- Graph features are materialized into the Online Feature Store alongside time-series features
- This layer is batch, not real-time — it enriches the feature set without adding to the Act path latency

**OSS:** Apache Spark GraphX / NetworkX (offline) → Online Feature Store
**Enterprise:** TigerGraph / Neo4j Enterprise + Databricks Graph

### 8.5 Observability Architecture

Observability is three pillars, each independently queryable:

**Metrics (RED + USE):**
- Rate: TPS per stage, decisions per outcome class
- Errors: schema rejections, dead-letter queue depth, circuit breaker state
- Duration: P50/P95/P99/P999 per stage
- Utilization: CPU, memory, network I/O per node
- OSS: Prometheus + Grafana | Enterprise: Dynatrace / Datadog

**Distributed Tracing:**
- Every transaction carries a trace context (W3C TraceContext standard)
- Per-stage spans are emitted: ingestion, feature hydration, inference, emission
- Enables root-cause analysis for P99 latency spikes without log archaeology
- OSS: OpenTelemetry + Jaeger / Tempo | Enterprise: Dynatrace / Honeycomb

**Structured Logging:**
- All logs are structured (JSON), include trace_id and transaction_id
- Log levels are runtime-configurable per component without restart
- OSS: Loki + Grafana | Enterprise: Splunk / Elastic SIEM

**SLO Dashboard (mandatory for DORA):**
- Real-time SLO burn rate display
- 30-day rolling availability and latency compliance
- Automatic incident ticket creation on SLO breach

### 8.6 Security Architecture

- **mTLS everywhere** between internal services — no plaintext internal traffic
- **Encryption at rest** for Online Feature Store and Offline Lake (AES-256)
- **Secret management** via a dedicated secrets vault — no credentials in config files or environment variables
- **RBAC on all data planes** — inference nodes have read-only access to feature stores; write access scoped to Feature Store Writer service only
- **Audit log is immutable** — implemented as an append-only log; no update or delete operations permitted at the storage layer; protected by WORM policy
- **Network segmentation** — Act path components in a dedicated network segment; Explain path in a separate segment; no direct cross-segment calls

**OSS:** HashiCorp Vault + cert-manager + OPA (Open Policy Agent) for RBAC
**Enterprise:** CyberArk + Istio service mesh + enterprise SIEM integration

---

## 9. Technology Stack Summary

### Open Source Edition

| Layer | Technology |
|---|---|
| Ingestion / Messaging | Apache Kafka |
| Schema Registry | Confluent Schema Registry (community) / Apicurio |
| Stream Processing | Apache Flink (RocksDB state backend) |
| Online Feature Store | Redis Cluster / Apache Ignite |
| Offline Lake | Apache Iceberg on MinIO + Apache Hive Metastore |
| Inference Runtime | ONNX Runtime + Triton Inference Server |
| Model Registry | MLflow |
| Orchestration | Apache Airflow (batch pipelines) |
| Graph Processing | Apache Spark GraphX |
| Observability | Prometheus + Grafana + OpenTelemetry + Jaeger + Loki |
| Governance / Lineage | Apache Atlas + OpenLineage |
| Security | HashiCorp Vault + OPA + cert-manager |

### Enterprise Edition

| Layer | Technology |
|---|---|
| Ingestion / Messaging | Confluent Platform / IBM Event Streams |
| Schema Registry | Confluent Schema Registry (enterprise) |
| Stream Processing | Hazelcast Jet / Ksqldb + Flink (Confluent managed) |
| Online Feature Store | Aerospike Enterprise / Redis Enterprise / Tecton |
| Offline Lake | Databricks Delta Lake / Snowflake (Iceberg OTF) |
| Inference Runtime | ONNX Runtime + SageMaker / Azure ML / DataRobot |
| Model Registry | MLflow (Databricks-managed) / DataRobot MLOps |
| Orchestration | Databricks Workflows / Apache Airflow (managed) |
| Graph Processing | TigerGraph / Neo4j Enterprise |
| Observability | Dynatrace / Datadog + Splunk SIEM |
| Governance / Lineage | Collibra / Informatica + Databricks Unity Catalog |
| Compliance Reporting | IBM OpenPages / OneTrust |
| Security | CyberArk + Istio + enterprise SIEM |

---

## 10. Scaling Model

| TPS Range | Kafka Partitions | Flink Parallelism | Online Store Nodes | Inference Nodes |
|---|---|---|---|---|
| 5,000 | 64 | 32 | 3 | 8 |
| 10,000 | 128 | 64 | 6 | 16 |
| 15,000 | 256 | 128 | 9 | 24 |

Scaling is horizontal and near-linear up to the partition count ceiling. Partition count is the primary lever — it determines maximum parallelism for both Kafka and Flink.

**Auto-scaling Trigger:** Consumer lag on `tx.raw.hot` > 5,000 events → scale out inference and stream processor node count. Lag returns to <500 events within 90 seconds under normal elasticity.

---

## 11. DORA / EU AI Act Compliance Checklist

| Requirement | Implementation |
|---|---|
| Auditability of AI decisions | Full audit record per decision in immutable Compliance Data Store |
| Explainability | SHAP values + counterfactual explanation in Explain path |
| Human oversight | `REVIEW` decision class + human review workflow integration |
| Data lineage | OpenLineage / Unity Catalog tracking from source event to model input |
| Model documentation | Model card in Model Registry (mandatory for promotion) |
| Bias / fairness assessment | Mandatory promotion gate; ongoing drift monitoring by demographic proxy |
| Incident logging | SLO breach → automatic incident; DORA-compliant incident record |
| Right to explanation (GDPR Art. 22) | Customer-facing explanation API backed by Explain path output |
| Data retention | Configurable 7-year retention on Compliance Data Store; WORM protected |
| Rollback capability | Champion rollback <60 seconds; model version pinned in every audit record |

---

*Document Owner: Lead Application Architect*
*Review Cycle: Quarterly or on major architectural change*
*Classification: Internal — Architecture*
