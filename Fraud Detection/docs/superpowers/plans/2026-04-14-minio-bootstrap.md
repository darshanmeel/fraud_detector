# Task 4: MinIO Bootstrap and Bucket Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate MinIO bucket creation (fraud-features-offline, fraud-audit-logs, fraud-models, fraud-lineage) with appropriate configurations (e.g., WORM/lock for audit logs).

**Architecture:** A bootstrap script (`config/minio/bootstrap.sh`) using the MinIO Client (`mc`) will be executed by an init container (`init-minio`) in the `docker-compose` environment. The `minio` service will serve as the primary object store.

**Tech Stack:** MinIO, MinIO Client (mc), Docker Compose, Shell Script.

---

### Task 1: Create MinIO Bootstrap Script

**Files:**
- Create: `config/minio/bootstrap.sh`

- [ ] **Step 1: Write the bootstrap script**

```bash
#!/bin/sh

# Set up alias for MinIO server
mc alias set myminio http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

# Create buckets
mc mb myminio/fraud-features-offline
mc mb myminio/fraud-audit-logs --with-lock
mc mb myminio/fraud-models
mc mb myminio/fraud-lineage

echo "MinIO buckets created successfully."
exit 0
```

### Task 2: Create Failing Test for Bucket Creation

**Files:**
- Create: `tests/verify_minio_buckets.ps1`

- [ ] **Step 1: Write the verification script**

```powershell
# tests/verify_minio_buckets.ps1
$MINIO_ROOT_USER = "minioadmin"
$MINIO_ROOT_PASSWORD = "minioadmin"
$MINIO_ENDPOINT = "http://localhost:9000"

# Check if buckets exist
$buckets = @("fraud-features-offline", "fraud-audit-logs", "fraud-models", "fraud-lineage")

foreach ($bucket in $buckets) {
    Write-Host "Checking bucket: $bucket"
    # Using curl for simplicity in this environment
    $response = curl -s -o /dev/null -w "%{http_code}" -u "${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}" "$MINIO_ENDPOINT/$bucket/"
    if ($response -ne "200") {
        Write-Error "Bucket $bucket does not exist or is inaccessible (HTTP $response)."
        exit 1
    }
}

Write-Host "All buckets verified successfully."
exit 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pwsh tests/verify_minio_buckets.ps1`
Expected: FAIL (MinIO not running or buckets not created)

### Task 3: Update docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add minio and init-minio services**

```yaml
  minio:
    image: minio/minio:${MINIO_VERSION}
    container_name: fraud-minio
    profiles: [core]
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - explain-net
      - mgmt-net
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - minio-data:/data
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: '0.5'

  init-minio:
    image: minio/mc:latest
    container_name: fraud-init-minio
    profiles: [core]
    networks:
      - explain-net
      - mgmt-net
    depends_on:
      minio:
        condition: service_healthy
    volumes:
      - ./config/minio/bootstrap.sh:/usr/local/bin/bootstrap.sh
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    entrypoint: ["/bin/sh", "/usr/local/bin/bootstrap.sh"]
```

- [ ] **Step 2: Add minio-data volume**

```yaml
volumes:
  redis-data:
  minio-data:
```

### Task 4: Verify Implementation

- [ ] **Step 1: Start the infrastructure**

Run: `docker-compose --profile core up -d minio init-minio`

- [ ] **Step 2: Run verification test**

Run: `pwsh tests/verify_minio_buckets.ps1`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add config/minio/bootstrap.sh docker-compose.yml tests/verify_minio_buckets.ps1
git commit -m "feat: implement MinIO bootstrap and bucket automation"
```
