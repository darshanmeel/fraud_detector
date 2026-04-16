# Design Spec: Observability & Telemetry (Phase 5)

**Status:** Draft
**Date:** 2026-04-15
**Topic:** Phase 5 — OpenTelemetry, Prometheus, & Grafana
**Target:** Local Docker Compose (V2)

## 1. Executive Summary
This phase implements Layer 8.5 of the architecture. It establishes a full-stack observability pipeline to monitor the health, performance (latency), and drift of the fraud engine. We will use the **OpenTelemetry (OTel)** standard to ensure vendor-neutral instrumentation across all Faust agents and the Management API.

## 2. Architecture & Components

### 2.1 The "Obs" Profile
A new `obs` profile in `docker-compose.yml` containing:
- **OTel Collector:** Receives traces and metrics from services.
- **Prometheus:** Scrapes metrics from the Collector.
- **Grafana:** Visualizes metrics and traces.

### 2.2 Instrumentation
- **Metrics:** Every service will emit "RED" metrics (Rate, Errors, Duration).
- **Tracing:** W3C TraceContext headers will be propagated through Redpanda topics to enable end-to-end tracing from `tx.raw.hot` to `decision.allow/block`.

## 3. Key Dashboards

### 3.1 The "SLA Monitor" (P99)
- **Ingestion Latency:** Time from Producer to `tx.raw.hot`.
- **Inference Latency:** Time spent in `fraud-processor` (Hydration + ONNX).
- **End-to-End P99:** Total time from event intake to decision emission.

### 3.2 The "Model Drift" Dashboard
- Score distribution histograms (Champion vs. Challenger).
- Feature value distributions (detecting if incoming data has shifted).
- Service health (Container CPU/Mem vs. Kafka Lag).

## 4. Implementation Details

### 4.1 Base Image Update
Update `services/base/Dockerfile` to include `opentelemetry-instrumentation-fastapi` and `opentelemetry-instrumentation-kafka-python`.

### 4.2 Grafana Provisioning
Pre-load dashboards into `config/grafana/dashboards/` so they are available on startup.

## 5. Verification Plan
- **Trace Verification:** Open Grafana and find a trace spanning multiple containers.
- **Load Test:** Simulate 100 TPS and verify the P99 latency remains below 30ms.
- **Alert Test:** Manually stop the `redis` container and verify the "Degraded Mode" alerts trigger in Grafana.

## 6. Success Criteria
- [ ] OTel Collector, Prometheus, and Grafana running.
- [ ] End-to-end P99 latency visible in a dashboard.
- [ ] Distributed tracing verified across Redpanda hops.
