# Design Spec: Fraud Detection Management Layer (Phase 3)

**Status:** Draft
**Date:** 2026-04-15
**Topic:** Phase 3 — Management API & Control Systems
**Target:** FastAPI Service + Redis/Redpanda Integration

## 1. Executive Summary
This phase implements the administrative control plane for the Fraud Detection Engine. It introduces a central FastAPI service (`mgmt-api`) that provides endpoints for manual review processing, dynamic model configuration (thresholds), and direct feature store overrides. This transforms the system from a static inference engine into a manageable platform.

## 2. Core Components

### 2.1 Management API (`services/mgmt-api`)
A FastAPI application serving as the primary interface for operators and the dashboard.

| Endpoint | Method | Description | Backend Action |
|---|---|---|---|
| `/reviews` | GET | List transactions awaiting manual review. | Query Redis/MinIO |
| `/reviews/{tx_id}` | POST | Resolve a pending review (Approve/Reject). | Produce to `decision.resolved` |
| `/config` | GET/PATCH| Read or Update risk thresholds (e.g., 0.3, 0.7). | Read/Write to Redis `cfg:thresholds` |
| `/features/override`| POST | Manually update a feature for an account. | Call `feast.write_to_online_store` |

### 2.2 Shared Configuration (Redis)
We will use Redis as a high-speed configuration store to decouple the API from the stream processors.
- **Key:** `cfg:thresholds`
- **Structure:** `{"low": 0.3, "high": 0.7}`

### 2.3 New Redpanda Topic: `decision.resolved`
Used to broadcast manual overrides from the `mgmt-api` to downstream systems (e.g., updating the Offline Store or notifying the customer).

## 3. Implementation Plan

### 3.1 Step 1: Update `shared/models.py`
Add `ResolvedDecision` model to track manual actions.

### 3.2 Step 2: Implement `mgmt-api` Service
- Create `services/mgmt-api/app.py` with FastAPI.
- Implement Redis client for config and Feast client for overrides.
- Implement Redpanda producer for resolutions.

### 3.3 Step 3: Update `fraud-processor`
- Modify the processing logic to fetch thresholds from Redis.
- Support three-way branching: `ALLOW`, `REVIEW`, `BLOCK`.

### 3.4 Step 4: Docker Integration
- Add `mgmt-api` to `docker-compose.yml`.
- Expose port `8000` for the API.

## 4. Verification Plan
- **Threshold Test:** Update thresholds via API, verify `fraud-processor` behavior changes immediately.
- **Review Test:** Trigger a `REVIEW` decision, resolve it via API, verify the `decision.resolved` message.
- **Override Test:** Push an override for `txn_count_1m`, verify subsequent transactions for that account are blocked.

## 5. Success Criteria
- [ ] FastAPI service running on port 8000.
- [ ] Risk thresholds are dynamic (not hardcoded).
- [ ] Manual resolutions can be emitted to the event bus.
- [ ] Feature store overrides are reflected in real-time.
