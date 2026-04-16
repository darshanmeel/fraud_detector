import faust
import os
import logging
from shared.models import TransactionEvent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Faust App configuration
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka://redpanda:29092')
app = faust.App('drift-monitor', broker=KAFKA_BROKER, topic_partitions=16)

# Topics
tx_topic = app.topic('tx.raw.hot', value_type=TransactionEvent)

# State for rolling average
# In a real system, use Faust Tables for persistent state across workers
rolling_avg = app.Table('rolling_avg', default=float)
txn_count = app.Table('txn_count', default=int)

@app.agent(tx_topic)
async def monitor_drift(transactions):
    async for tx in transactions:
        # Update rolling average (simplified)
        count = txn_count['total'] or 0
        current_avg = rolling_avg['total'] or 0.0
        
        new_count = count + 1
        new_avg = ((current_avg * count) + tx.amount_cents) / new_count
        
        txn_count['total'] = new_count
        rolling_avg['total'] = new_avg
        
        # Drift Detection Threshold (e.g., $100 average)
        THRESHOLD = 10000 
        
        if new_avg > THRESHOLD:
            logger.warning(f"DRIFT DETECTED: Average transaction amount ({new_avg/100:.2f}) exceeded threshold ({THRESHOLD/100:.2f})!")
        
        if new_count % 10 == 0:
            logger.info(f"Drift Monitor: Total txns: {new_count}, Current avg: {new_avg/100:.2f}")
