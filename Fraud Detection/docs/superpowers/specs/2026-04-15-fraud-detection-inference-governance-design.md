# Design Spec: Real-Time Inference & Model Governance (Phase 4)

**Status:** Draft
**Date:** 2026-04-15
**Topic:** Phase 4 — ONNX Runtime & Champion/Challenger Routing
**Target:** Local Docker Compose (V2)

## 1. Executive Summary
This phase implements the "Inference Layer" (Layer 4) of the architecture. It replaces the heuristic "mock" model with the **ONNX Runtime**, allowing the system to serve real ML models (XGBoost/LightGBM) with sub-10ms latency. It also introduces the infrastructure for Champion/Challenger testing to safely validate new models.

## 2. Architecture & Components

### 2.1 Sidecar Inference Pattern
The `fraud-processor` will now include an `InferenceEngine` that loads model artifacts from a local directory (mounted volume). 
- **Format:** ONNX (Open Neural Network Exchange).
- **Runtime:** `onnxruntime` Python package.

### 2.2 Model Registry (Mock)
A directory-based registry (`/models`) where artifacts are versioned.
- `models/champion.onnx` -> Current production model.
- `models/challenger.onnx` -> Candidate model for testing.

### 2.3 Champion/Challenger Routing
The `fraud-processor` will implement a traffic splitter:
1. Every transaction is scored by **both** models (if a challenger exists).
2. Only the `champion` score is used for the synchronous `decision.*` emission.
3. Both scores are emitted to a new `model.performance` topic for side-by-side comparison in Phase 5.

## 3. Data Strategy

### 3.1 Inference Payload
The model will expect a flattened feature vector derived from the Feast hydration:
- `txn_count_1m` (Float)
- `amount_cents` (Float)
- `account_age_days` (Float) - *New feature view required.*

### 3.2 Dynamic Reloading
The agent will watch the `/models` directory for file changes. When a new `.onnx` file is detected, the runtime will hot-reload the model without dropping the Faust stream.

## 4. Implementation Details

### 4.1 Update `shared/inference.py`
Replace `HeuristicModel` with `ONNXInferenceEngine`.

### 4.2 Update `shared/models.py`
Add `ModelPerformanceEvent` to track side-by-side scores.

## 5. Verification Plan
- **Latency Test:** Measure inference time (Target: <10ms for ONNX score).
- **Reload Test:** Swap `champion.onnx` and verify the `model_version` field in `DecisionEnvelope` updates.
- **Shadow Test:** Verify that `challenger` scores are being logged to Kafka without affecting the `ALLOW/BLOCK` decision.

## 6. Success Criteria
- [ ] ONNX Runtime integrated into `fraud-processor`.
- [ ] Champion/Challenger routing implemented.
- [ ] Zero-downtime model reloading verified.
