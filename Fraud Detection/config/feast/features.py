from datetime import timedelta
from feast import Entity, FeatureView, Field, PushSource, FileSource
from feast.value_type import ValueType
from feast.types import Int64, String, Float64, Int32, Bool

# Entity
account = Entity(name="account_id", value_type=ValueType.STRING, description="Account ID")

# Batch Source for the Push Source
account_velocity_batch_source = FileSource(
    name="account_velocity_batch_source",
    path="/app/feast_repo/dummy.parquet",
    timestamp_field="event_timestamp",
)

# Push Source for real-time updates
account_velocity_push_source = PushSource(
    name="account_velocity_push_source",
    batch_source=account_velocity_batch_source,
)

# Feature View
account_velocity = FeatureView(
    name="account_velocity",
    entities=[account],
    ttl=timedelta(days=3),
    schema=[
        Field(name="txn_count_1m", dtype=Float64),
        Field(name="txn_count_5m", dtype=Float64),
        Field(name="txn_count_15m", dtype=Float64),
        Field(name="txn_count_1h", dtype=Float64),
        Field(name="txn_count_24h", dtype=Float64),
        Field(name="spend_sum_1m", dtype=Float64),
        Field(name="spend_sum_5m", dtype=Float64),
        Field(name="spend_sum_1h", dtype=Float64),
        Field(name="spend_avg_24h", dtype=Float64),
        Field(name="distinct_merchants_1h", dtype=Int32),
        Field(name="distinct_countries_24h", dtype=Int32),
        Field(name="distinct_devices_24h", dtype=Int32),
        Field(name="session_txn_count", dtype=Int32),
        Field(name="session_duration_s", dtype=Float64),
        Field(name="schema_version", dtype=String),
        Field(name="feature_timestamp", dtype=Int64),
        Field(name="low_confidence", dtype=Bool),
    ],
    source=account_velocity_push_source,
    online=True,
)
