from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiokafka
import json
import asyncio
import os
import uuid
from datetime import datetime
import boto3
import docker

app = FastAPI()

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'redpanda:29092')
S3_ENDPOINT = os.environ.get('FEAST_S3_ENDPOINT_URL', 'http://minio:9000')
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID', 'admin')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'fraud-local-secret')

# Docker client
try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None

class TransactionRequest(BaseModel):
    account_id: str
    amount_cents: int
    merchant_id: str

s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name='us-east-1'
)

UI_MAPPING = {
    "fraud-redpanda-console": "http://localhost:8080",
    "fraud-feast": "http://localhost:6566",
    "fraud-signoz": "http://localhost:3301",
    "fraud-airflow-webserver": "http://localhost:8082",
    "fraud-mlflow": "http://localhost:5000",
    "fraud-mgmt-api": "http://localhost:8000",
    "fraud-minio": "http://localhost:9001",
}

@app.post("/simulate")
async def simulate_tx(req: TransactionRequest):
    tx_id = str(uuid.uuid4())
    payload = {
        "transaction_id": tx_id,
        "account_id": req.account_id,
        "amount_cents": req.amount_cents,
        "merchant_id": req.merchant_id,
        "event_timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    producer = aiokafka.AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    await producer.start()
    try:
        await producer.send_and_wait("tx.raw.hot", json.dumps(payload).encode('utf-8'))
    finally:
        await producer.stop()
        
    return {"transaction_id": tx_id, "status": "sent"}

@app.get("/result/{tx_id}")
async def get_result(tx_id: str):
    try:
        response = s3.get_object(Bucket='fraud-audit-logs', Key=f"audit/{tx_id}.json")
        data = json.loads(response['Body'].read().decode('utf-8'))
        return data
    except Exception:
        return {"status": "pending", "message": "Result not yet available in audit logs."}

@app.get("/services")
async def get_services():
    if not docker_client:
        return []
    
    services = []
    for container in docker_client.containers.list(all=True):
        name = container.name
        if not name.startswith("fraud-"): continue
        
        status = container.status
        ui_url = UI_MAPPING.get(name)
        
        services.append({
            "name": name,
            "status": status,
            "ui_url": ui_url
        })
    return services

@app.get("/logs")
async def get_logs():
    if not docker_client:
        yield "data: Docker not connected\n\n"
        return

    def stream_logs():
        # This is a simplified log streamer for all fraud containers
        # In a real app, we'd use a more sophisticated multiplexer
        containers = [c for c in docker_client.containers.list() if c.name.startswith("fraud-")]
        for container in containers:
            try:
                logs = container.logs(tail=10, stdout=True, stderr=True).decode('utf-8')
                for line in logs.split('\n'):
                    if line.strip():
                        # Simple error highlighting
                        is_error = "error" in line.lower() or "exception" in line.lower() or "fail" in line.lower() or "warning" in line.lower()
                        payload = {"container": container.name, "line": line, "is_error": is_error}
                        yield f"data: {json.dumps(payload)}\n\n"
            except Exception:
                continue

    return StreamingResponse(stream_logs(), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r") as f:
        return f.read()
