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
    if not (0.0 <= thresholds.low <= 1.0) or not (0.0 <= thresholds.high <= 1.0):
        raise HTTPException(status_code=400, detail="Thresholds must be between 0.0 and 1.0")
    if thresholds.low > thresholds.high:
        raise HTTPException(status_code=400, detail="Low threshold cannot be higher than high threshold")
    
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
