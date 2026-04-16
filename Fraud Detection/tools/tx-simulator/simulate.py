import json
import time
import random
import uuid
import argparse
from kafka import KafkaProducer

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["normal", "anomaly"], default="normal")
    parser.add_argument("--tps", type=int, default=1)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--scenario", default="all")
    parser.add_argument("--broker", default="localhost:9092")
    return parser.parse_args()

def produce_event(producer, topic, event):
    producer.send(topic, key=event["account_id"].encode('utf-8'), value=json.dumps(event).encode('utf-8'))
    producer.flush()

def generate_tx(account_id=None, amount=None):
    if not account_id:
        account_id = f"acc_{random.randint(1000, 9999)}"
    if not amount:
        amount = random.randint(100, 100000) # 1.00 to 1000.00
        
    return {
        "transaction_id": str(uuid.uuid4()),
        "source_system": "mobile",
        "account_id": account_id,
        "device_id": f"dev_{random.randint(100, 999)}",
        "ip_address": f"192.168.1.{random.randint(1, 254)}",
        "merchant_id": f"merch_{random.randint(10, 99)}",
        "merchant_category": "5411",
        "amount_cents": amount,
        "currency": "USD",
        "country_code": "US",
        "event_timestamp": int(time.time() * 1000),
        "ingestion_timestamp": int(time.time() * 1000),
        "source_system_hash": "hash"
    }

def main():
    args = get_args()
    producer = KafkaProducer(bootstrap_servers=args.broker)
    
    start_time = time.time()
    print(f"Starting {args.mode} simulation for {args.duration}s at {args.tps} TPS")
    
    while time.time() - start_time < args.duration:
        if args.mode == "normal":
            event = generate_tx()
            produce_event(producer, "tx.raw.hot", event)
        else:
            # Anomaly scenarios
            if args.scenario == "velocity_burst" or args.scenario == "all":
                acc = "acc_burst_1"
                for _ in range(10):
                    produce_event(producer, "tx.raw.hot", generate_tx(account_id=acc))
                    
            if args.scenario == "amount_spike" or args.scenario == "all":
                produce_event(producer, "tx.raw.hot", generate_tx(amount=1000000)) # 10,000.00
        
        time.sleep(1.0 / args.tps)
    
    print("Simulation complete.")

if __name__ == "__main__":
    main()
