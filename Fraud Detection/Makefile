.PHONY: core obs mgmt up down reset status topics buckets schemas feast-apply sim-normal sim-anomaly logs

core:
	docker compose --profile core up -d

obs:
	docker compose --profile core --profile obs up -d

mgmt:
	docker compose --profile core --profile mgmt up -d

up:
	docker compose --profile core --profile obs --profile mgmt up -d

down:
	docker compose down

reset:
	docker compose down -v

status:
	docker compose ps --all

topics:
	docker compose run --rm init-redpanda

buckets:
	docker compose run --rm init-minio

schemas:
	@echo "Registering schemas..."
	@curl -X POST http://localhost:8081/subjects/tx-raw-value/versions -H "Content-Type: application/vnd.schemaregistry.v1+json" -d @schemas/TransactionEvent.avsc
	@curl -X POST http://localhost:8081/subjects/feature-vector-value/versions -H "Content-Type: application/vnd.schemaregistry.v1+json" -d @schemas/FeatureVector.avsc
	@curl -X POST http://localhost:8081/subjects/decision-value/versions -H "Content-Type: application/vnd.schemaregistry.v1+json" -d @schemas/DecisionEnvelope.avsc

feast-apply:
	docker compose exec feast feast apply

sim-normal:
	@echo "Running normal simulation..."
	# Assuming a simulator script exists at tools/tx-simulator/simulate.py
	python tools/tx-simulator/simulate.py --mode normal --tps 10 --duration 60

sim-anomaly:
	@echo "Running anomaly simulation..."
	python tools/tx-simulator/simulate.py --mode anomaly --scenario all

logs:
	docker compose logs -f
