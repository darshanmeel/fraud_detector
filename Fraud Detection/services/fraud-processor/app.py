import faust
import os
import json
import redis
import logging
from shared.models import TransactionEvent, DecisionEnvelope, ModelPerformanceEvent
from shared.inference import ONNXInferenceEngine
from feast import FeatureStore
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OTel Setup
OTEL_ENDPOINT = os.environ.get('OTEL_ENDPOINT', 'otel-collector:4317')

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True))
)
tracer = trace.get_tracer(__name__)

metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
)
metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
meter = metrics.get_meter(__name__)

latency_histogram = meter.create_histogram(
    "process_latency",
    unit="ms",
    description="Latency of transaction processing"
)

KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka://redpanda:29092')
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
app = faust.App('fraud-processor', broker=KAFKA_BROKER)

# Redis for config
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# In-memory cache for thresholds
cached_thresholds = {"low": 0.3, "high": 0.7}

@app.timer(interval=5.0)
async def refresh_thresholds():
    global cached_thresholds
    try:
        cfg = r.get("cfg:thresholds")
        if cfg:
            cached_thresholds = json.loads(cfg)
            logger.debug(f"Thresholds refreshed: {cached_thresholds}")
    except Exception as e:
        logger.error(f"Error refreshing thresholds: {e}")

def get_thresholds():
    return cached_thresholds

# Topics
tx_topic = app.topic('tx.raw.hot', value_type=TransactionEvent)
allow_topic = app.topic('decision.allow', value_type=DecisionEnvelope)
review_topic = app.topic('decision.review', value_type=DecisionEnvelope)
block_topic = app.topic('decision.block', value_type=DecisionEnvelope)
performance_topic = app.topic('model.performance', value_type=ModelPerformanceEvent)

FEAST_REPO_PATH = os.environ.get('FEAST_REPO_PATH', '.')
store = FeatureStore(repo_path=FEAST_REPO_PATH)

CHAMPION_PATH = os.environ.get('CHAMPION_PATH', '/models/champion.onnx')
CHALLENGER_PATH = os.environ.get('CHALLENGER_PATH', '/models/challenger.onnx')

champion = ONNXInferenceEngine(CHAMPION_PATH, "v1-prod")
challenger = None
if os.path.exists(CHALLENGER_PATH):
    challenger = ONNXInferenceEngine(CHALLENGER_PATH, "v2-shadow")

@app.agent(tx_topic)
async def process(transactions):
    async for tx in transactions:
        with tracer.start_as_current_span("process_transaction") as span:
            span.set_attribute("transaction_id", tx.transaction_id)
            start_time = app.loop.time()
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
                score = champion.predict(features)

                challenger_score = -1.0
                if challenger:
                    challenger_score = challenger.predict(features)
                    await performance_topic.send(value=ModelPerformanceEvent(
                        transaction_id=tx.transaction_id,
                        champion_score=score,
                        challenger_score=challenger_score,
                        champion_version=champion.version,
                        challenger_version=challenger.version
                    ))

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
                    risk_score=score,
                    model_version=champion.version
                )

                await target_topic.send(value=envelope)
                latency = (app.loop.time() - start_time) * 1000
                latency_histogram.record(latency)
                logger.info(f"TX {tx.transaction_id} -> {decision} (Score: {score}, Latency: {latency:.2f}ms)")

            except Exception as e:
                logger.error(f"Error: {e}")
                span.record_exception(e)

@app.timer(interval=60.0)
async def reload_models():
    # Simple mock for reload
    global champion, challenger
    pass
