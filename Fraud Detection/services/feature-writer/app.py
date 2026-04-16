import faust
import os
import logging
from datetime import datetime
from shared.models import TransactionEvent
from feast import FeatureStore

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Faust App configuration
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka://redpanda:29092')
app = faust.App('feature-writer', broker=KAFKA_BROKER)

# Topics
tx_topic = app.topic('tx.raw.hot', value_type=TransactionEvent)

# Faust Table for stateful aggregation (RocksDB backed)
# This prevents race conditions during high concurrency bursts
account_tx_counts = app.Table('account_tx_counts', default=int)

# Feature Store
FEAST_REPO_PATH = os.environ.get('FEAST_REPO_PATH', '.')
store = FeatureStore(repo_path=FEAST_REPO_PATH)

def import_pandas_as_pd():
    import pandas as pd
    return pd

@app.agent(tx_topic)
async def update_features(transactions):
    async for tx in transactions:
        logger.info(f"Processing features for account: {tx.account_id}")
        
        try:
            # Atomic increment in Faust state table
            account_tx_counts[tx.account_id] += 1
            new_count = account_tx_counts[tx.account_id]
            
            # Write the updated feature to Feast Online Store
            pd = import_pandas_as_pd()
            
            # Provide all fields required by the Feature View schema
            feature_data = {
                "account_id": tx.account_id,
                "event_timestamp": datetime.utcnow(),
                "txn_count_1m": float(new_count),
                "txn_count_5m": 0.0,
                "txn_count_15m": 0.0,
                "txn_count_1h": 0.0,
                "txn_count_24h": 0.0,
                "spend_sum_1m": 0.0,
                "spend_sum_5m": 0.0,
                "spend_sum_1h": 0.0,
                "spend_avg_24h": 0.0,
                "distinct_merchants_1h": 0,
                "distinct_countries_24h": 0,
                "distinct_devices_24h": 0,
                "session_txn_count": 0,
                "session_duration_s": 0.0,
                "schema_version": "1.0",
                "feature_timestamp": int(datetime.utcnow().timestamp()),
                "low_confidence": False
            }
            
            store.write_to_online_store(
                feature_view_name="account_velocity",
                df=pd.DataFrame([feature_data])
            )
            logger.info(f"Updated account {tx.account_id} txn_count_1m to {new_count}")
            
        except Exception as e:
            logger.error(f"Error updating features for account {tx.account_id}: {e}", exc_info=True)
