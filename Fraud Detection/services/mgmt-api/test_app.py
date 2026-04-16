from fastapi.testclient import TestClient
from app import app
from unittest.mock import patch

client = TestClient(app)

@patch('app.r')
def test_get_config(mock_redis):
    mock_redis.get.return_value = '{"low": 0.4, "high": 0.8}'
    response = client.get("/config")
    assert response.status_code == 200
    assert "thresholds" in response.json()
    assert response.json()["thresholds"]["low"] == 0.4
