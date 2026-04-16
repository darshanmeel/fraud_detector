# Observability & Telemetry (Phase 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a full-stack observability pipeline with OpenTelemetry, Prometheus, and Grafana to track SLA and drift.

**Architecture:** Services emit OTLP traces and metrics to an OTel Collector. Prometheus scrapes the Collector, and Grafana visualizes the data. Tracing context is propagated across Redpanda topics.

**Tech Stack:** OpenTelemetry (OTel), Prometheus, Grafana, Jaeger/Tempo.

---

### Task 1: Setup Infrastructure (The "Obs" Profile)

**Files:**
- Modify: `docker-compose.yml`
- Create: `config/otel/collector-config.yaml`
- Create: `config/prometheus/prometheus.yaml`

- [ ] **Step 1: Create OTel Collector Config**
Define receivers (OTLP), processors (batch), and exporters (Prometheus, Logging).

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
  logging:
    loglevel: debug

service:
  pipelines:
    metrics:
      receivers: [otlp]
      exporters: [prometheus, logging]
```

- [ ] **Step 2: Update Docker Compose**
Add `otel-collector`, `prometheus`, and `grafana` to the `obs` profile.

```yaml
  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./config/otel/collector-config.yaml:/etc/otel-collector-config.yaml
    networks:
      - obs-net
      - act-net

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./config/prometheus/prometheus.yaml:/etc/prometheus/prometheus.yaml
    networks:
      - obs-net

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    networks:
      - obs-net
```

- [ ] **Step 3: Commit**
```bash
git add docker-compose.yml config/
git commit -m "feat: setup observability infrastructure profile"
```

---

### Task 2: Update Base Image for Instrumentation

**Files:**
- Modify: `services/base/Dockerfile`

- [ ] **Step 1: Install OTel Dependencies**
Add instrumentation packages to the shared base image.

```dockerfile
RUN pip install --no-cache-dir \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-kafka-python
```

- [ ] **Step 2: Commit**
```bash
git add services/base/Dockerfile
git commit -m "feat: add opentelemetry to base service image"
```

---

### Task 3: Instrument Fraud Processor (Latency Tracking)

**Files:**
- Modify: `services/fraud-processor/app.py`

- [ ] **Step 1: Initialize Tracer**
Set up the OTel tracer and add a span to the `process` agent.

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup OTel
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

@app.agent(tx_topic)
async def process(transactions):
    async for tx in transactions:
        with tracer.start_as_current_span("process_transaction") as span:
            span.set_attribute("transaction_id", tx.transaction_id)
            # ... process logic ...
```

- [ ] **Step 2: Commit**
```bash
git add services/fraud-processor/app.py
git commit -m "feat: instrument fraud-processor for tracing"
```

---

### Task 4: Provision Dashboards

**Files:**
- Create: `config/grafana/provisioning/dashboards/dashboard.yaml`
- Create: `config/grafana/dashboards/sla-monitor.json`

- [ ] **Step 1: Configure Provisioning**
Point Grafana to the dashboards directory.

- [ ] **Step 2: Create SLA Monitor JSON**
Provide a basic JSON definition for a P99 Latency graph and Throughput (TPS) counter.

- [ ] **Step 3: Commit**
```bash
git add config/grafana/
git commit -m "feat: provision SLA monitor dashboard"
```
