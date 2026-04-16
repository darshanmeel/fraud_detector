$global:Passed = $true

function Assert-FileExists($Path) {
    if (-not (Test-Path $Path)) {
        Write-Error "Test Failed: File $Path does not exist."
        $global:Passed = $false
    }
}

function Assert-StringInFile($Path, $String) {
    if (Test-Path $Path) {
        $Content = Get-Content $Path -Raw
        if ($Content -notmatch [regex]::Escape($String)) {
            Write-Error "Test Failed: File $Path does not contain '$String'."
            $global:Passed = $false
        }
    } else {
        $global:Passed = $false
    }
}

Write-Host "--- Running Task 3 Infrastructure Tests ---"

# 1. Topic Bootstrap Script Existence
Assert-FileExists "config/redpanda/topics.sh"

# 2. Topic Creation in Script
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create tx.raw.hot -p 16"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create tx.raw.cold -p 8"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create feature.update -p 8"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create decision.block -p 4"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create decision.allow -p 4"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create decision.review -p 4"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create decision.degraded -p 2"
Assert-StringInFile "config/redpanda/topics.sh" "rpk topic create tx.dead-letter -p 2"

# 3. init-redpanda Service in docker-compose.yml
Assert-StringInFile "docker-compose.yml" "init-redpanda:"
Assert-StringInFile "docker-compose.yml" "image: redpandadata/redpanda:`${REDPANDA_VERSION}"
Assert-StringInFile "docker-compose.yml" "container_name: fraud-init-redpanda"
Assert-StringInFile "docker-compose.yml" "./config/redpanda/topics.sh:/usr/local/bin/topics.sh"
Assert-StringInFile "docker-compose.yml" 'entrypoint: ["/bin/bash", "/usr/local/bin/topics.sh"]'
Assert-StringInFile "docker-compose.yml" "depends_on:"
Assert-StringInFile "docker-compose.yml" "redpanda:"
Assert-StringInFile "docker-compose.yml" "condition: service_healthy"

if ($global:Passed) {
    Write-Host "--- TASK 3 TESTS PASSED ---"
    exit 0
} else {
    Write-Host "--- TASK 3 TESTS FAILED ---"
    exit 1
}
