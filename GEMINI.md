# 📜 Project Mandates & Foundational Context

This document is the **Foundational Truth** for the Real-Time Behavioral Fraud Detection Engine. All AI agents (Gemini, Claude, etc.) MUST adhere to these instructions.

---

## 🚀 Primary Objective
Implement and maintain a high-performance behavioral fraud detection engine with **sub-30ms P99 latency**, 100% auditability, and DORA/EU AI Act compliance.

## 🛠️ Core Tech Stack (Non-Negotiable)
- **Engine:** [Faust Streaming](https://github.com/robinhood/faust) (Python-based).
- **Bus:** [Redpanda](https://redpanda.com/) (Kafka-compatible).
- **Features:** [Feast](https://feast.dev/) (Online: Redis, Offline: MinIO).
- **Inference:** [ONNX Runtime](https://onnxruntime.ai/).
- **Observability:** [SigNoz](https://signoz.io/) & OpenTelemetry.
- **Storage:** [MinIO](https://min.io/) (WORM-enabled audit logs).

## 🚦 Operational Constraints
1. **Stateless Inference:** The `fraud-processor` MUST NOT write to any database. It is a pure function: `(Transaction + History) -> Score`.
2. **Atomic Behavioral Counting:** Use Faust Tables (RocksDB) in the `feature-writer` to ensure atomic transaction counting.
3. **Hot/Explain Split:** Never perform SHAP explanations or heavy I/O on the hot inference path. Use the `explain-consumer` sidecar.
4. **Schema Enforcement:** All events MUST use Avro schemas defined in `schemas/`.
5. **No Local Shell Scripts:** Use the root `Makefile` for cross-platform infrastructure management.

## 📁 Critical Documentation
- **[AGENTS.md](./AGENTS.md):** Role-specific personae and mental models.
- **[TECHNICAL_BLUEPRINT.md](./TECHNICAL_BLUEPRINT.md):** Deep-dive into paths, patterns, and scaling.
- **[README.md](./README.md):** Architecture diagrams and quick-start guides.

---

## 🧪 Testing Standard
- A task is incomplete without a corresponding `pytest` file in `tests/`.
- Use `pytest-asyncio` for agent verification.
- Bug fixes MUST include a reproduction test case.

## 📖 Style & Convention
- **Naming:** CamelCase for classes, snake_case for functions/variables.
- **Validation:** Use Pydantic V2 for all data models.
- **Documentation:** Use Mermaid.js for all sequence and flow diagrams.
