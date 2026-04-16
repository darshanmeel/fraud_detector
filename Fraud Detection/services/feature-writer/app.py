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

# Feature Store
FEAST_REPO_PATH = os.environ.get('FEAST_REPO_PATH', '.')
store = FeatureStore(repo_path=FEAST_REPO_PATH)

@app.agent(tx_topic)
async def update_features(transactions):
    async for tx in transactions:
        logger.info(f"Updating features for account: {tx.account_id}")
        
        try:
            # For the prototype, we'll just increment the txn count.
            # In a real system, we'd query the current count and increment, 
            # or use a more sophisticated stateful processor.
            # Here we simulate a push update to Feast.
            
            # First, we get the current feature value to increment it (simplified)
            # In a real high-throughput system, you'd use Faust state (RocksDB) 
            # to keep track of the count and push periodically or use a real stream processor.
            
            feature_vector = store.get_online_features(
                features=["account_velocity:txn_count_1m"],
                entity_rows=[{"account_id": tx.account_id}]
            ).to_dict()
            
            current_count = feature_vector.get("txn_count_1m", [0])[0] or 0
            new_count = current_count + 1
            
            # Write the updated feature directly to Feast Online Store
            store.write_to_online_store(
                feature_view_name="account_velocity",
                df=import_pandas_as_pd().DataFrame([
                    {
                        "account_id": tx.account_id,
                        "txn_count_1m": new_count,
                        "event_timestamp": datetime.utcnow()
                    }
                ])
            )
            logger.info(f"Updated account {tx.account_id} txn_count_1m to {new_count}")
            
            # Read back to verify
            verify_vector = store.get_online_features(
                features=["account_velocity:txn_count_1m"],
                entity_rows=[{"account_id": tx.account_id}]
            ).to_dict()
            logger.info(f"Verify back for {tx.account_id}: {verify_vector.get('txn_count_1m', [0])[0]}")
            
        except Exception as e:
            logger.error(f"Error updating features for account {tx.account_id}: {e}", exc_info=True)

def import_pandas_as_pd():
    import pandas as pd
    return pd
