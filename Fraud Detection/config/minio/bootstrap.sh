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