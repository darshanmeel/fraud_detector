# Design Spec: Explain Path & Offline Data Lake (Phase 6)

**Status:** Draft
**Date:** 2026-04-15
**Topic:** Phase 6 — Apache Iceberg, MinIO, & Label Joining
**Target:** Local Docker Compose (V2)

## 1. Executive Summary
This phase implements Layers 5, 6b, and 8.3 of the architecture. It completes the feedback loop by persisting all transactions and decisions into an **Apache Iceberg** data lake (on MinIO). It also introduces the "Label Joiner" to handle delayed fraud chargebacks, creating a ground-truth dataset for future model retraining.

## 2. Architecture & Components

### 2.1 Structured Offline Lake (Iceberg)
We will upgrade the storage from raw JSON files to **Apache Iceberg** tables. 
- **Storage:** MinIO `fraud-features-offline` bucket.
- **Catalog:** Project-local file catalog (for prototype).
- **Format:** Parquet.

### 2.2 Explainability (SHAP Lite)
The `explain-consumer` will be updated to:
1. Re-run the ONNX model in a separate "Explain" context.
2. Compute **SHAP values** (Feature Importance) for high-risk decisions.
3. Write the explanation (e.g., "Blocked due to high velocity in US") to the `fraud-audit-logs` bucket.

### 2.3 Delayed Label Joiner
A new batch service that:
1. Consumes `tx.chargeback` events (simulated delayed labels).
2. Performs a point-in-time join with the original feature vector in the Iceberg lake.
3. Produces a "Labeled Dataset" ready for retraining.

## 3. Data Strategy

### 3.1 Partitioning
Iceberg tables will be partitioned by `event_timestamp_day` and `entity_id_prefix` to ensure efficient queries for audit and retraining.

### 3.2 Immutability
The `fraud-audit-logs` bucket will have **WORM (Write Once Read Many)** enabled via MinIO object locking to satisfy EU AI Act compliance.

## 4. Implementation Details

### 4.1 PyIceberg Integration
The `explain-consumer` will use the `pyiceberg` library to manage the offline table schema and data inserts.

### 4.2 SHAP Mocking
For the prototype, we will use a simplified SHAP approximation (returning the top-3 features that contributed most to the ONNX score).

## 5. Verification Plan
- **Data Query Test:** Use a Python script to query the Iceberg table and verify the schema.
- **Explainability Test:** Resolve a `BLOCK` decision and verify that a SHAP explanation exists in the audit bucket.
- **Label Join Test:** Inject a chargeback for a 2-day-old transaction and verify the labeled record is correctly matched.

## 6. Success Criteria
- [ ] Apache Iceberg tables established on MinIO.
- [ ] SHAP explanations generated for high-risk decisions.
- [ ] Labeled dataset generated from delayed chargebacks.
