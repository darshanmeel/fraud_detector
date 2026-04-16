import faust
import os
import json
import boto3
import logging
from shared.models import TransactionEvent, DecisionEnvelope
from shared.inference import ONNXInferenceEngine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka://redpanda:29092')
app = faust.App('explain-consumer', broker=KAFKA_BROKER)

# S3 for Audit Logs
s3 = boto3.client(
    's3',
    endpoint_url=os.environ.get('FEAST_S3_ENDPOINT_URL', 'http://minio:9000'),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', 'admin'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', 'fraud-local-secret'),
    region_name='us-east-1' # MinIO usually works with any region string
)

# Topics
tx_topic = app.topic('tx.raw.hot', value_type=TransactionEvent)

CHAMPION_PATH = os.environ.get('CHAMPION_PATH', '/models/champion.onnx')
model = ONNXInferenceEngine(CHAMPION_PATH, "v1-prod")

@app.agent(tx_topic)
async def explain_transaction(transactions):
    async for tx in transactions:
        try:
            # Mock feature re-hydration
            features = {
                "txn_count_1m": 5, 
                "amount_cents": tx.amount_cents
            }
            
            explanation = model.explain(features)
            
            audit_log = {
                "transaction_id": tx.transaction_id,
                "explanation": explanation,
                "timestamp": tx.event_timestamp
            }
            
            s3.put_object(
                Bucket='fraud-audit-logs',
                Key=f"audit/{tx.transaction_id}.json",
                Body=json.dumps(audit_log)
            )
            logger.info(f"Audit log saved for TX: {tx.transaction_id}")
            
        except Exception as e:
            logger.error(f"Error in explain-consumer for TX {tx.transaction_id}: {e}")
