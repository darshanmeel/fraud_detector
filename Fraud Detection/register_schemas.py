import requests
import json
import os

schemas = {
    "tx-raw-value": "schemas/TransactionEvent.avsc",
    "feature-vector-value": "schemas/FeatureVector.avsc",
    "decision-value": "schemas/DecisionEnvelope.avsc"
}

url = "http://localhost:8081/subjects/{}/versions"

for subject, path in schemas.items():
    if os.path.exists(path):
        with open(path, 'r') as f:
            schema_content = f.read()
            payload = {"schema": schema_content}
            response = requests.post(url.format(subject), json=payload)
            print(f"Registering {subject}: {response.status_code} - {response.text}")
    else:
        print(f"File not found: {path}")
