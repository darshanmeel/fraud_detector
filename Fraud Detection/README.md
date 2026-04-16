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

1. **Clone the repository and enter the project directory:**
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

## 🧪 Testing

### 1. Register Schemas
Register Avro schemas with the built-in Redpanda Schema Registry:
```bash
make schemas
```

### 2. Run Simulations
Generate transactions to see the engine in action:
- **Normal Traffic:** `make sim-normal`
- **Anomaly/Fraud Traffic:** `make sim-anomaly`

### 3. Verify Decisions
Monitor the block topic for fraud detections:
```bash
docker exec fraud-redpanda rpk topic consume decision.block --brokers localhost:29092
```

## 📊 Observability

Access the dashboards:
- **SigNoz (Metrics/Traces):** [http://localhost:3301](http://localhost:3301)
- **Feast UI:** [http://localhost:6566](http://localhost:6566)
- **Redpanda Console:** [http://localhost:8080](http://localhost:8080)

## 📁 Repository Structure

- `/services`: Individual micro-agents (fraud-processor, feature-writer, etc.)
- `/config`: Component configurations (Feast, Redis, Redpanda, OTel)
- `/schemas`: Avro schema definitions for event versioning
- `/docs`: Technical specifications and architectural deep-dives
- `/reviews`: Historical code review summaries indexed by commit hash

## ⚖️ Governance & Compliance

This engine is designed to comply with **DORA** and the **EU AI Act**:
- **Explainability:** Asynchronous SHAP value computation for high-risk decisions.
- **Auditability:** Immutable WORM storage for all decision envelopes.
- **Human-in-the-Loop:** `REVIEW` decision class for manual operator intervention via Management API.
