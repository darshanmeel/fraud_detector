# Real-Time Behavioral Fraud Detection Engine

A high-performance, sub-30ms P99 behavioral fraud detection engine built with a multi-agent, event-driven architecture. The system separates the **hot path** (real-time inference) from the **explain path** (asynchronous auditing and explainability).

## 🚀 Features

- **Sub-30ms Latency:** Optimized hot path using Faust streaming and in-memory caching.
- **Behavioral Analysis:** Real-time feature engineering using **Feast** (Online Store: Redis, Offline Store: MinIO).
- **ML Inference:** sidecar model execution using **ONNX Runtime** (Champion/Challenger routing).
- **Observability:** Full-stack telemetry with **OpenTelemetry**, **SigNoz**, and **Prometheus**.
- **Governance:** Immutable audit logs via MinIO WORM buckets and **Apache Iceberg**.
- **Management API:** FastAPI for manual review overrides and dynamic risk thresholds.

## 🏗️ Architecture

```mermaid
graph TD
    subgraph "Act Path (Hot)"
        A[Transaction Event] --> B[Redpanda: tx.raw.hot]
        B --> C[Fraud Processor]
        C --> D{Inference Score}
        D -->|ALLOW| E[Redpanda: decision.allow]
        D -->|BLOCK| F[Redpanda: decision.block]
        D -->|REVIEW| G[Redpanda: decision.review]
    end
    subgraph "State & Infrastructure"
        C --> H[(Feast Online: Redis)]
        I[Feature Writer] --> H
        B --> I
    end
    subgraph "Explain Path (Cold)"
        F --> J[Explain Consumer]
        G --> J
        J --> K[(MinIO: Audit Logs)]
        J --> L[(Apache Iceberg)]
    end
```

## 🧩 Roles & Responsibilities: Who does what?

Understanding the difference between behavioral tracking, system monitoring, and manual judging:

| Component | Responsibility | Scope | Logic Trigger |
| :--- | :--- | :--- | :--- |
| **✍️ Feature Writer** | **Behavioral Tracking.** Updates the history of a *specific* account (e.g., "This user has 5 txns in 1 min"). | **Individual** | Increments RocksDB counters on every event. |
| **📈 Drift Monitor** | **System Health.** Detects if *global* spending patterns have shifted away from what the model was trained on. | **Global** | Calculates a system-wide rolling average. |
| **🧠 Fraud Processor**| **The Decider.** Combines the user's history with the current transaction to give a 0-1 risk score. | **Transactional** | Runs ONNX inference for every event. |
| **🕹️ Management API** | **Human-in-the-Loop.** Allows operators to manually approve `REVIEW` cases or update risk thresholds. | **Administrative** | Manual HTTP request from an operator. |

## 🔄 Transaction Lifecycle Deep-Dive

```mermaid
sequenceDiagram
    autonumber
    participant S as 🛠️ Simulator
    participant FW as ✍️ Feature Writer
    participant FP as 🧠 Fraud Processor
    participant FS as 🍽️ Feast/Redis
    participant EC as 🧐 Explain Consumer
    participant DM as 📈 Drift Monitor

    Note over S: [Input]: Raw TX Parameters<br/>[Trigger]: simulate.py -> produce_event()
    S->>FP: 1. Input: TransactionEvent (JSON)
    S->>FW: 1. Input: TransactionEvent (JSON)
    S->>DM: 1. Input: TransactionEvent (JSON)

    rect rgb(240, 240, 240)
    Note over FW: [Internal]: account_tx_counts[id] += 1
    FW->>FS: 2. Output: store.write_to_online_store()
    end

    rect rgb(230, 240, 255)
    Note over FP: [Internal]: hydrate -> predict -> route
    FP->>FS: 3. Input: account_id
    FS-->>FP: 4. Output: txn_count_1m (e.g. 15)
    
    Note over FP: Logic: score = model.predict(X)
    
    alt score < 0.3 (ALLOW)
        FP->>S: 5. Output: decision.allow
    else 0.3 < score < 0.7 (REVIEW)
        FP->>S: 5. Output: decision.review
        FP-->>EC: 6. Input: Decision + Features
    else score > 0.7 (BLOCK)
        FP->>S: 5. Output: decision.block
        FP-->>EC: 6. Input: Decision + Features
    end
    end

    rect rgb(255, 245, 230)
    Note over EC: [Internal]: model.explain() (SHAP)
    EC->>EC: 7. Output: Write MinIO audit/{id}.json
    end

    rect rgb(245, 255, 245)
    Note over DM: [Internal]: rolling_avg['total'] update
    DM->>DM: 8. Trigger: warning if avg > $100
    end
```

---

## 🛠️ Tech Stack

- **Message Bus:** [Redpanda](https://redpanda.com/) (Kafka-compatible)
- **Stream Processing:** [Faust Streaming](https://github.com/robinhood/faust)
- **Feature Store:** [Feast](https://feast.dev/)
- **Model Runtime:** [ONNX Runtime](https://onnxruntime.ai/)
- **Object Storage:** [MinIO](https://min.io/)
- **Observability:** [SigNoz](https://signoz.io/) / [OpenTelemetry](https://opentelemetry.io/)
- **API Framework:** [FastAPI](https://fastapi.tiangolo.com/)

## 🏁 Getting Started

### Prerequisites

- Docker Desktop / Docker Engine with Compose V2
- Python 3.11+
- `rpk` (Redpanda CLI) - Optional, for inspection

### Quick Start

1. **Enter the project directory:**
   ```bash
   cd "Fraud Detection"
   ```

2. **Start the core infrastructure:**
   ```bash
   make core
   ```

3. **Bootstrap topics and buckets:**
   ```bash
   make topics
   make buckets
   ```

4. **Start the full stack (including observability):**
   ```bash
   make obs
   ```

## 🧪 Testing & Real-Time Monitoring

### 1. Register Schemas
Register Avro schemas with the built-in Redpanda Schema Registry:
```bash
make schemas
```

### 2. Run Simulations
Generate transactions to see the engine in action:
- **Normal Traffic (Happy Path):** `make sim-normal`
- **Anomaly Traffic (Triggers Blocks/Reviews):** `make sim-anomaly`

### 3. Real-Time UI Monitoring

| UI | URL | Purpose |
| :--- | :--- | :--- |
| **Redpanda Console** | [http://localhost:8080](http://localhost:8080) | **View Live Transactions.** Navigate to `Topics -> decision.block` to see fraud detections in real-time. |
| **SigNoz** | [http://localhost:3301](http://localhost:3301) | **Latency Tracing.** Search for `fraud-processor` traces to see microsecond breakdowns. |
| **Feast UI** | [http://localhost:6566](http://localhost:6566) | **Feature State.** Monitor real-time behavioral features like `txn_count_1m`. |

## 📁 Repository Structure

- `Fraud Detection/services`: Individual micro-agents (fraud-processor, feature-writer, etc.)
- `Fraud Detection/config`: Component configurations (Feast, Redis, Redpanda, OTel)
- `Fraud Detection/schemas`: Avro schema definitions for event versioning
- `Fraud Detection/docs`: Technical specifications and architectural deep-dives
- `Fraud Detection/reviews`: Historical code review summaries indexed by commit hash

## ⚖️ Governance & Compliance

This engine is designed to comply with **DORA** and the **EU AI Act**:
- **Explainability:** Asynchronous SHAP value computation for high-risk decisions.
- **Auditability:** Immutable WORM storage for all decision envelopes in MinIO.
- **Human-in-the-Loop:** `REVIEW` decision class for manual operator intervention via Management API.
