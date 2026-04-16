.PHONY: core obs mgmt up down reset status topics buckets schemas feast-apply sim-normal sim-anomaly logs

core:
	docker compose --profile core up -d

obs:
	docker compose --profile core --profile obs up -d

mgmt:
	docker compose --profile core --profile mgmt up -d

up:
	docker compose --profile core --profile obs --profile mgmt up -d

all-up: up

down:
	docker compose --profile core --profile obs --profile mgmt down

all-down:
	docker compose --profile core --profile obs --profile mgmt down -v

reset:
	docker compose --profile core --profile obs --profile mgmt down -v

status:
	docker compose ps --all

topics:
	docker compose run --rm init-redpanda

buckets:
	docker compose run --rm init-minio

schemas:
	@echo "Registering schemas..."
	@python register_schemas.py

feast-apply:
	docker compose exec feast feast apply

test:
	@echo "Running automated test suite..."
	cd .. && pytest "Fraud Detection/tests"

sim-normal:
	@echo "Running normal simulation..."
	# Assuming a simulator script exists at tools/tx-simulator/simulate.py
	python tools/tx-simulator/simulate.py --mode normal --tps 10 --duration 60

sim-anomaly:
	@echo "Running anomaly simulation..."
	python tools/tx-simulator/simulate.py --mode anomaly --scenario all

logs:
	docker compose --profile core --profile obs --profile mgmt logs -f

all-logs: logs
