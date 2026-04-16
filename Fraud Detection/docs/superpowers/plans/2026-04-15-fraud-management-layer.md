# Fraud Detection Management Layer (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a FastAPI-based Management API to handle manual reviews, dynamic risk thresholds, and feature store overrides.

**Architecture:** A centralized FastAPI service (`mgmt-api`) interacting with Redis for configuration/state, Redpanda for event broadcasting, and Feast for feature management. The `fraud-processor` is updated to consume dynamic configuration from Redis.

**Tech Stack:** Python 3.11, FastAPI, Redis, Redpanda (confluent-kafka), Feast, Faust.

---

### Task 1: Update Shared Models

**Files:**
- Modify: `services/shared/models.py`

- [ ] **Step 1: Add Resolution models**
Update `services/shared/models.py` to include `ResolvedDecision` and update `DecisionEnvelope`.

```python
import faust

class TransactionEvent(faust.Record, serializer='json'):
    transaction_id: str
    account_id: str
    amount_cents: int
    merchant_id: str
    country_code: str
    event_timestamp: int

class DecisionEnvelope(faust.Record, serializer='json'):
    transaction_id: str
    decision: str  # ALLOW, REVIEW, BLOCK
    risk_score: float
    model_version: str = 'heuristic-v1'
    low_confidence: bool = False

class ResolvedDecision(faust.Record, serializer='json'):
    transaction_id: str
    resolution: str  # APPROVED, REJECTED
    reason: str
    operator_id: str
```

- [ ] **Step 2: Commit changes**
```bash
git add services/shared/models.py
git commit -m "chore: add resolution models to shared library"
```

---

### Task 2: Management API - Service Setup

**Files:**
- Create: `services/mgmt-api/requirements.txt`
- Create: `services/mgmt-api/Dockerfile`

- [ ] **Step 1: Create requirements.txt**
```text
fastapi
uvicorn
redis
confluent-kafka
feast[redis]
pandas
```

- [ ] **Step 2: Create Dockerfile**
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Commit**
```bash
git add services/mgmt-api/
git commit -m "feat: setup mgmt-api service infrastructure"
```

---

### Task 3: Management API - Core Implementation

**Files:**
- Create: `services/mgmt-api/app.py`
- Create: `tests/mgmt-api/test_app.py`

- [ ] **Step 1: Write failing test for config endpoint**
```python
from fastapi.testclient import TestClient
from mgmt_api.app import app

client = TestClient(app)

def test_get_config():
    response = client.get("/config")
    assert response.status_code == 200
    assert "thresholds" in response.json()
```

- [ ] **Step 2: Implement FastAPI Application**
Create `services/mgmt-api/app.py`.

```python
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
from confluent_kafka import Producer
from feast import FeatureStore

app = FastAPI(title="Fraud Detection Management API")

# Clients
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'localhost:9092')
producer = Producer({'bootstrap.servers': KAFKA_BROKER})

FEAST_REPO_PATH = os.environ.get('FEAST_REPO_PATH', '/app/config/feast')
store = FeatureStore(repo_path=FEAST_REPO_PATH)

class Thresholds(BaseModel):
    low: float
    high: float

class Resolution(BaseModel):
    resolution: str
    reason: str
    operator_id: str

@app.get("/config")
async def get_config():
    cfg = r.get("cfg:thresholds")
    if not cfg:
        return {"thresholds": {"low": 0.3, "high": 0.7}}
    return {"thresholds": json.loads(cfg)}

@app.patch("/config")
async def update_config(thresholds: Thresholds):
    r.set("cfg:thresholds", thresholds.json())
    return {"status": "updated", "config": thresholds}

@app.post("/reviews/{tx_id}/resolve")
async def resolve_review(tx_id: str, res: Resolution):
    msg = {
        "transaction_id": tx_id,
        "resolution": res.resolution,
        "reason": res.reason,
        "operator_id": res.operator_id
    }
    producer.produce("decision.resolved", key=tx_id, value=json.dumps(msg))
    producer.flush()
    return {"status": "resolved", "tx_id": tx_id}

@app.post("/features/override")
async def override_feature(account_id: str, feature_name: str, value: float):
    # This assumes we are overriding a specific feature view
    # In a real system, we'd look up the feature view name
    store.write_to_online_store(
        feature_view_name="account_velocity",
        entity_rows=[{
            "account_id": account_id,
            feature_name: value,
            "event_timestamp": 1713175200 # Fixed timestamp for prototype
        }]
    )
    return {"status": "overridden", "account_id": account_id}
```

- [ ] **Step 3: Verify tests pass**
```bash
pytest tests/mgmt-api/test_app.py
```

- [ ] **Step 4: Commit**
```bash
git add services/mgmt-api/app.py tests/mgmt-api/test_app.py
git commit -m "feat: implement management api endpoints"
```

---

### Task 4: Update Fraud Processor for Dynamic Thresholds

**Files:**
- Modify: `services/fraud-processor/app.py`

- [ ] **Step 1: Implement Dynamic Config Fetching**
Modify `services/fraud-processor/app.py` to read thresholds from Redis.

```python
import faust
import os
import json
import redis
import logging
from shared.models import TransactionEvent, DecisionEnvelope
from shared.inference import HeuristicModel
from feast import FeatureStore

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka://redpanda:29092')
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
app = faust.App('fraud-processor', broker=KAFKA_BROKER)

# Redis for config
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# Topics
tx_topic = app.topic('tx.raw.hot', value_type=TransactionEvent)
allow_topic = app.topic('decision.allow', value_type=DecisionEnvelope)
review_topic = app.topic('decision.review', value_type=DecisionEnvelope)
block_topic = app.topic('decision.block', value_type=DecisionEnvelope)

FEAST_REPO_PATH = os.environ.get('FEAST_REPO_PATH', '.')
store = FeatureStore(repo_path=FEAST_REPO_PATH)
model = HeuristicModel()

def get_thresholds():
    try:
        cfg = r.get("cfg:thresholds")
        if cfg:
            return json.loads(cfg)
    except Exception as e:
        logger.error(f"Error fetching thresholds from Redis: {e}")
    return {"low": 0.3, "high": 0.7}

@app.agent(tx_topic)
async def process(transactions):
    async for tx in transactions:
        try:
            # Hydrate
            feature_vector = store.get_online_features(
                features=["account_velocity:txn_count_1m"],
                entity_rows=[{"account_id": tx.account_id}]
            ).to_dict()
            
            features = {
                "txn_count_1m": feature_vector.get("txn_count_1m", [0])[0],
                "amount_cents": tx.amount_cents
            }
            
            # Inference
            score = model.predict(features)
            thresholds = get_thresholds()
            
            # Decision Logic
            if score >= thresholds["high"]:
                decision = "BLOCK"
                target_topic = block_topic
            elif score >= thresholds["low"]:
                decision = "REVIEW"
                target_topic = review_topic
            else:
                decision = "ALLOW"
                target_topic = allow_topic
                
            envelope = DecisionEnvelope(
                transaction_id=tx.transaction_id,
                decision=decision,
                risk_score=score
            )
            
            await target_topic.send(value=envelope)
            logger.info(f"TX {tx.transaction_id} -> {decision} (Score: {score})")
            
        except Exception as e:
            logger.error(f"Error: {e}")
```

- [ ] **Step 2: Commit**
```bash
git add services/fraud-processor/app.py
git commit -m "feat: update fraud-processor with dynamic thresholds"
```

---

### Task 5: Docker Compose Integration

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add mgmt-api service**
Add the following to `services:` section.

```yaml
  mgmt-api:
    build: 
      context: ./services/mgmt-api
    container_name: mgmt-api
    environment:
      - KAFKA_BROKER=redpanda:29092
      - REDIS_HOST=redis
      - FEAST_REPO_PATH=/app/config/feast
    volumes:
      - ./config/feast:/app/config/feast
    ports:
      - "8000:8000"
    networks:
      - act-net
    depends_on:
      - redpanda
      - redis
```

- [ ] **Step 2: Commit**
```bash
git add docker-compose.yml
git commit -m "feat: add mgmt-api to docker-compose"
```
