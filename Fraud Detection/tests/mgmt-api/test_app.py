from fastapi.testclient import TestClient
from services.mgmt_api.app import app
from unittest.mock import patch
import json

client = TestClient(app)

def test_get_config():
    with patch('services.mgmt_api.app.r') as mock_redis:
        mock_redis.get.return_value = json.dumps({"low": 0.4, "high": 0.8})
        response = client.get("/config")
        assert response.status_code == 200
        assert "thresholds" in response.json()
        assert response.json()["thresholds"]["low"] == 0.4

def test_update_config_validation_pass():
    with patch('services.mgmt_api.app.r') as mock_redis:
        response = client.patch("/config", json={"low": 0.2, "high": 0.6})
        assert response.status_code == 200
        mock_redis.set.assert_called_once()

def test_update_config_validation_fail_bounds():
    response = client.patch("/config", json={"low": -0.1, "high": 1.2})
    assert response.status_code == 400
    assert "Thresholds must be between 0.0 and 1.0" in response.json()["detail"]

def test_update_config_validation_fail_logic():
    response = client.patch("/config", json={"low": 0.8, "high": 0.3})
    assert response.status_code == 400
    assert "Low threshold cannot be higher than high threshold" in response.json()["detail"]

def test_override_feature_integration():
    with patch('services.mgmt_api.app.store') as mock_store:
        response = client.post("/features/override?account_id=acc1&feature_name=txn_count_1m&value=10.0")
        assert response.status_code == 200
        mock_store.write_to_online_store.assert_called_once()
