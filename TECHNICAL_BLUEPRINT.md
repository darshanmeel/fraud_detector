# 📐 Technical Blueprint & Development Guide

This guide provides the technical specifications and patterns required to extend or reimplement the **Real-Time Behavioral Fraud Detection Engine**.

---

## 1. System Architecture: The "Hot" vs "Cold" Path

The core principle of this engine is the strict separation of concerns to maintain sub-30ms P99 latency.

### 🔥 The Hot Path (Inference)
- **Services:** `fraud-processor`, `feature-writer`.
- **Constraint:** Must be **fully asynchronous** and **stateless**.
- **Data Flow:** Redpanda `tx.raw.hot` → Faust Agent → ONNX Predict → Redpanda `decision.*`.
- **Optimization:** Risk thresholds are cached in-memory and refreshed every 5 seconds to avoid Redis round-trips for every transaction.

### ❄️ The Cold Path (Explainability & Governance)
- **Services:** `explain-consumer`, `drift-monitor`.
- **Constraint:** Can afford higher latency (sub-second or second-scale).
- **Data Flow:** Redpanda `decision.block` → SHAP Explainer → MinIO (Audit Log) / Iceberg.

---

## 2. Feature Engineering with Feast

We treat **behavioral features** (e.g., "how many transactions in the last minute") as state that is updated by the `feature-writer` and read by the `fraud-processor`.

### Pattern: Atomic Updates
To prevent lost updates during account bursts, use the **Faust Table** pattern:
```python
# feature-writer/app.py
account_tx_counts = app.Table('account_tx_counts', default=int)

@app.agent(transactions)
async def update_features(stream):
    async for tx in stream:
        account_tx_counts[tx.account_id] += 1  # Atomic increment
        # Then sync to Feast Online Store (Redis) for the Processor to read
        store.write_to_online_store(feature_view="behavioral_features", df=...)
```

---

## 3. Model Serving with ONNX Runtime

We use ONNX as the canonical format for portability and performance.

### Pattern: sidecar Execution
The `fraud-processor` loads the model at startup and executes it inside the Faust event loop (using `loop.run_in_executor` if the model is large).
- **Champion:** The primary model used for the final `DecisionEnvelope`.
- **Challenger:** Run in "Shadow Mode" for performance and drift comparison.

---

## 4. Telemetry & Observability (OTel)

Every service must contribute to the global trace.

### Pattern: Span Decoration
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_event(event):
    with tracer.start_as_current_span("fraud-check") as span:
        span.set_attribute("account_id", event.account_id)
        # Logic...
```

---

## 5. Deployment & Environment

- **Infrastructure:** Managed via `docker-compose.yml`.
- **Local Dev:** Use `make core` for base infrastructure and `make up` for the full stack.
- **Secrets:** Never commit `.env`. Use `Fraud Detection/.env.example` as a template.

---

## 6. How to Add a New Feature
1. **Schema:** Define the new feature in `Fraud Detection/schemas/FeatureVector.avsc`.
2. **Feast:** Add the feature to `Fraud Detection/config/feast/features.py`.
3. **Writer:** Update `feature-writer` to calculate and push the new feature.
4. **Processor:** Update the model input shape in `shared/inference.py` to include the new feature.
5. **Verify:** Run `make test` and check SigNoz for latency changes.
