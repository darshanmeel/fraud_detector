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
            # For the prototype, we push on every event, but in production
            # we might batch these or push on a timer.
            pd = import_pandas_as_pd()
            store.write_to_online_store(
                feature_view_name="account_velocity",
                df=pd.DataFrame([
                    {
                        "account_id": tx.account_id,
                        "txn_count_1m": float(new_count),
                        "event_timestamp": datetime.utcnow()
                    }
                ])
            )
            logger.info(f"Updated account {tx.account_id} txn_count_1m to {new_count}")
            
        except Exception as e:
            logger.error(f"Error updating features for account {tx.account_id}: {e}", exc_info=True)
