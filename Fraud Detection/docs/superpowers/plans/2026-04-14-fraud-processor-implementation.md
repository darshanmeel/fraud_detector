# Fraud Processor Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the primary hot-path Faust agent (`fraud-processor`) that performs real-time feature hydration and heuristic inference.

**Architecture:** A stateful Faust stream processor consuming `tx.raw.hot` and emitting to `decision.*` topics. It uses a mock heuristic model to simulate XGBoost inference during the prototype phase.

**Tech Stack:** Faust Streaming, Python 3.11, Feast (Redis), FastAvro.

---

### Task 1: Shared Models & Mock Heuristic Model

**Files:**
- Create: `services/shared/models.py`
- Create: `services/shared/inference.py`
- Test: `tests/shared/test_inference.py`

- [ ] **Step 1: Create shared Avro-compatible Faust records**

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
```

- [ ] **Step 2: Implement the `HeuristicModel`**

```python
class HeuristicModel:
    def predict(self, features: dict) -> float:
        score = 0.1
        # Velocity Burst
        if features.get('txn_count_1m', 0) > 10:
            score = max(score, 0.9)
        # Amount Spike
        if features.get('amount_cents', 0) > 100000: # $1000
            score = max(score, 0.6)
        return score
```

- [ ] **Step 3: Write tests for the model**

```python
def test_heuristic_velocity_burst():
    model = HeuristicModel()
    assert model.predict({'txn_count_1m': 15}) == 0.9

def test_heuristic_normal():
    model = HeuristicModel()
    assert model.predict({'txn_count_1m': 2}) == 0.1
```

- [ ] **Step 4: Commit shared logic**

```bash
git add services/shared tests/shared
git commit -m "feat: add shared models and heuristic inference logic"
```

---

### Task 2: Fraud Processor Agent Implementation

**Files:**
- Create: `services/fraud-processor/app.py`
- Create: `services/fraud-processor/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Implement the Faust agent logic**

```python
import faust
from shared.models import TransactionEvent, DecisionEnvelope
from shared.inference import HeuristicModel
from feast import FeatureStore

app = faust.App('fraud-processor', broker='kafka://redpanda:29092')
tx_topic = app.topic('tx.raw.hot', value_type=TransactionEvent)
allow_topic = app.topic('decision.allow', value_type=DecisionEnvelope)
block_topic = app.topic('decision.block', value_type=DecisionEnvelope)

store = FeatureStore(repo_path=".")
model = HeuristicModel()

@app.agent(tx_topic)
async def process(transactions):
    async for tx in transactions:
        # Hydrate features
        features = store.get_online_features(
            features=["account_velocity:txn_count_1m"],
            entity_rows=[{"account_id": tx.account_id}]
        ).to_dict()
        features['amount_cents'] = tx.amount_cents
        
        # Inference
        score = model.predict(features)
        
        # Decision
        decision = "ALLOW" if score < 0.5 else "BLOCK"
        envelope = DecisionEnvelope(transaction_id=tx.transaction_id, decision=decision, risk_score=score)
        
        if decision == "BLOCK":
            await block_topic.send(value=envelope)
        else:
            await allow_topic.send(value=envelope)
```

- [ ] **Step 2: Create Dockerfile for the agent**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["faust", "-A", "app", "worker", "-l", "info"]
```

- [ ] **Step 3: Add service to `docker-compose.yml`**

```yaml
  fraud-processor:
    build:
      context: ./services/fraud-processor
    container_name: fraud-processor
    profiles: [core]
    networks:
      - act-net
    environment:
      FEAST_USAGE: "False"
    depends_on:
      redpanda:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 4: Commit agent**

```bash
git add services/fraud-processor docker-compose.yml
git commit -m "feat: implement fraud-processor agent with feast integration"
```

---

### Task 3: Integration & Manual Verification

- [ ] **Step 1: Start the processor**

Run: `docker compose --profile core up -d fraud-processor`

- [ ] **Step 2: Inject a test transaction**

Run: `echo '{"transaction_id":"tx1", "account_id":"acc1", "amount_cents":500, "merchant_id":"m1", "country_code":"US", "event_timestamp":1713110400}' | docker exec -i fraud-redpanda rpk topic produce tx.raw.hot`

- [ ] **Step 3: Verify decision**

Run: `docker exec fraud-redpanda rpk topic consume decision.allow --num 1`
Expect: A DecisionEnvelope for tx1.

- [ ] **Step 4: Final commit**

```bash
git commit --allow-empty -m "docs: phase 2 task 1 complete"
```
