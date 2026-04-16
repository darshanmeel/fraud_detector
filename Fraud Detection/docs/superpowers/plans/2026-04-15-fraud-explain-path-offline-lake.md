# Explain Path & Offline Data Lake (Phase 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a structured offline lake using Apache Iceberg on MinIO and compute SHAP explanations for compliance.

**Architecture:** `explain-consumer` writes to Iceberg tables. A new `label-joiner` service handles delayed chargebacks. MinIO object locking ensures audit immutability.

**Tech Stack:** Apache Iceberg (via `pyiceberg`), MinIO, SHAP (lite version), PyArrow.

---

### Task 1: Setup Iceberg Storage (MinIO)

**Files:**
- Modify: `config/minio/bootstrap.sh`

- [ ] **Step 1: Update MinIO Bootstrap**
Add logic to create the `fraud-iceberg` bucket with object locking enabled.

```bash
mc mb --with-lock local/fraud-audit-logs
mc mb local/fraud-iceberg
```

- [ ] **Step 2: Commit**
```bash
git add config/minio/bootstrap.sh
git commit -m "feat: enable object locking for audit bucket in minio"
```

---

### Task 2: Implement Iceberg Table in Explain Consumer

**Files:**
- Modify: `services/explain-consumer/app.py`
- Modify: `services/explain-consumer/requirements.txt`

- [ ] **Step 1: Add Iceberg Requirements**
Update `requirements.txt`.

```text
pyiceberg[pyarrow]
s3fs
thrift-py3
```

- [ ] **Step 2: Initialize Iceberg Table**
Update `services/explain-consumer/app.py` to create and write to an Iceberg table.

```python
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, DoubleType, TimestampType

# Setup Catalog
catalog = load_catalog("fraud_catalog", **{
    "type": "rest",
    "uri": "http://iceberg-catalog:8181",
    "s3.endpoint": "http://minio:9000",
    "s3.access-key-id": "admin",
    "s3.secret-access-key": "password"
})

# Create Table Schema
schema = Schema(
    NestedField(1, "transaction_id", StringType()),
    NestedField(2, "risk_score", DoubleType()),
    NestedField(3, "event_timestamp", TimestampType())
)

table = catalog.create_table_if_not_exists("fraud.transactions", schema=schema)

# Inside process loop:
table.append(pa.Table.from_pydict({
    "transaction_id": [tx.transaction_id],
    "risk_score": [score],
    "event_timestamp": [timestamp]
}))
```

- [ ] **Step 3: Commit**
```bash
git add services/explain-consumer/
git commit -m "feat: integrate pyiceberg into explain-consumer"
```

---

### Task 3: Implement SHAP Lite Explanations

**Files:**
- Modify: `services/shared/inference.py`
- Modify: `services/explain-consumer/app.py`

- [ ] **Step 1: Add SHAP Approximation**
Update `ONNXInferenceEngine` to provide feature contributions.

```python
# In inference.py:
def explain(self, features: dict):
    # Mock SHAP: Return features sorted by their contribution to the score
    # In a real system, you'd use the SHAP library here
    return sorted(features.items(), key=lambda x: x[1], reverse=True)[:3]
```

- [ ] **Step 2: Write Audit Log**
Update `explain-consumer` to write a text explanation to the audit bucket.

```python
explanation = model.explain(features)
audit_key = f"audit/{tx_id}.json"
# Write to MinIO fraud-audit-logs bucket
```

- [ ] **Step 3: Commit**
```bash
git add services/shared/inference.py services/explain-consumer/app.py
git commit -m "feat: implement SHAP lite explanations for audit logs"
```

---

### Task 4: Implement Delayed Label Joiner

**Files:**
- Create: `services/label-joiner/app.py`
- Create: `services/label-joiner/Dockerfile`

- [ ] **Step 1: Implement Joiner Logic**
The service consumes from `tx.chargeback` and updates the Iceberg table.

```python
@app.agent(chargeback_topic)
async def join_labels(chargebacks):
    async for cb in chargebacks:
        # Update Iceberg table: set is_fraud=True where tx_id = cb.tx_id
        # In a real lake, this is an UPSERT or MERGE operation
        pass
```

- [ ] **Step 2: Commit**
```bash
git add services/label-joiner/
git commit -m "feat: implement delayed label joiner service"
```
