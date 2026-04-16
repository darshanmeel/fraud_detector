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

Write-Host "--- Running Infrastructure Tests ---"

# 1. File Existence
Assert-FileExists "docker-compose.yml"
Assert-FileExists "config/redis/redis.conf"

# 2. Redis Configuration in docker-compose.yml
Assert-StringInFile "docker-compose.yml" "redis:"
Assert-StringInFile "docker-compose.yml" "image: redis:`${REDIS_VERSION}"
Assert-StringInFile "docker-compose.yml" "profiles: [core]"
Assert-StringInFile "docker-compose.yml" "act-net"
Assert-StringInFile "docker-compose.yml" "obs-net"
Assert-StringInFile "docker-compose.yml" "redis-data:/data"
Assert-StringInFile "docker-compose.yml" "redis-server"
Assert-StringInFile "docker-compose.yml" "/usr/local/etc/redis/redis.conf"
Assert-StringInFile "docker-compose.yml" "memory: 512m"
Assert-StringInFile "docker-compose.yml" "cpus: '0.5'"

# 3. Redpanda Configuration in docker-compose.yml
Assert-StringInFile "docker-compose.yml" "redpanda:"
Assert-StringInFile "docker-compose.yml" "image: redpandadata/redpanda:`${REDPANDA_VERSION}"
Assert-StringInFile "docker-compose.yml" "explain-net"
Assert-StringInFile "docker-compose.yml" "9092"
Assert-StringInFile "docker-compose.yml" "9644"
Assert-StringInFile "docker-compose.yml" "8081"
Assert-StringInFile "docker-compose.yml" "8080"
Assert-StringInFile "docker-compose.yml" "redpanda start"
Assert-StringInFile "docker-compose.yml" "--smp 1"
Assert-StringInFile "docker-compose.yml" "--memory 1G"
Assert-StringInFile "docker-compose.yml" "--overprovisioned"
Assert-StringInFile "docker-compose.yml" "rpk"
Assert-StringInFile "docker-compose.yml" "cluster"
Assert-StringInFile "docker-compose.yml" "health"
Assert-StringInFile "docker-compose.yml" "memory: 2g"
Assert-StringInFile "docker-compose.yml" "cpus: '2.0'"

# 4. Redis.conf content
Assert-StringInFile "config/redis/redis.conf" "appendonly yes"

if ($global:Passed) {
    Write-Host "--- ALL TESTS PASSED ---"
    exit 0
} else {
    Write-Host "--- TESTS FAILED ---"
    exit 1
}
