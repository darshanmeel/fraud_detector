# tests/verify_minio_buckets.ps1
$MINIO_ROOT_USER = "minioadmin"
$MINIO_ROOT_PASSWORD = "minioadmin"
$MINIO_ENDPOINT = "http://localhost:9000"

# Check if buckets exist
$buckets = @("fraud-features-offline", "fraud-audit-logs", "fraud-models", "fraud-lineage")

foreach ($bucket in $buckets) {
    Write-Host "Checking bucket: $bucket"
    # Use curl.exe directly to avoid PowerShell alias for Invoke-WebRequest
    $response = & curl.exe -s -o NUL -w "%{http_code}" -u "${MINIO_ROOT_USER}:${MINIO_ROOT_PASSWORD}" "$MINIO_ENDPOINT/$bucket/"
    if ($response -ne "200") {
        Write-Error "Bucket $bucket does not exist or is inaccessible (HTTP $response)."
        exit 1
    }
}

Write-Host "All buckets verified successfully."
exit 0
