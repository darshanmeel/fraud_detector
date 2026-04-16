import faust
from typing import List, Optional

class TransactionEvent(faust.Record, serializer='json'):
    transaction_id: str
    account_id: str
    amount_cents: int
    merchant_id: str
    country_code: str
    event_timestamp: int
    source_system: str = 'mobile'
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    merchant_category: str = '5411'
    currency: str = 'USD'
    ingestion_timestamp: Optional[int] = None
    source_system_hash: Optional[str] = None

class DecisionEnvelope(faust.Record, serializer='json'):
    transaction_id: str
    decision: str  # ALLOW, REVIEW, BLOCK, DEGRADED_BLOCK
    risk_score: float
    model_version: str = 'heuristic-v1'
    low_confidence: bool = False
    source_correlation_id: Optional[str] = None
    confidence_lower: Optional[float] = None
    confidence_upper: Optional[float] = None
    feature_schema_version: Optional[str] = None
    processing_ts: Optional[int] = None
    latency_total_us: Optional[int] = None
    flags: List[str] = []

class ResolvedDecision(faust.Record, serializer='json'):
    transaction_id: str
    resolution: str  # APPROVED, REJECTED
    reason: str
    operator_id: str

class ModelPerformanceEvent(faust.Record, serializer='json'):
    transaction_id: str
    champion_score: float
    challenger_score: float
    champion_version: str
    challenger_version: str
