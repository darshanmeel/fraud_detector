import pytest
import json
import redis
from unittest.mock import MagicMock, patch
from services.shared.models import TransactionEvent, DecisionEnvelope
from services.fraud_processor.app import refresh_thresholds, get_thresholds

@pytest.mark.asyncio
async def test_threshold_caching():
    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps({"low": 0.5, "high": 0.9})
    
    with patch('services.fraud_processor.app.r', mock_redis):
        # Trigger refresh
        await refresh_thresholds()
        
        # Verify cache updated
        thresholds = get_thresholds()
        assert thresholds["low"] == 0.5
        assert thresholds["high"] == 0.9

@pytest.mark.asyncio
async def test_process_logic_routing():
    from services.fraud_processor.app import process, allow_topic, block_topic, review_topic
    
    mock_tx = TransactionEvent(
        transaction_id="tx_test",
        account_id="acc_1",
        amount_cents=100,
        merchant_id="m1",
        country_code="US",
        event_timestamp=1713110400
    )
    
    with patch('services.fraud_processor.app.store') as mock_store:
        with patch('services.fraud_processor.app.champion') as mock_model:
            # 1. Test ALLOW
            mock_model.predict.return_value = 0.1
            with patch.object(allow_topic, 'send') as mock_send:
                async def mock_stream(): yield mock_tx
                await process(mock_stream())
                mock_send.assert_called_once()
            
            # 2. Test BLOCK
            mock_model.predict.return_value = 0.9
            with patch.object(block_topic, 'send') as mock_send:
                async def mock_stream(): yield mock_tx
                await process(mock_stream())
                mock_send.assert_called_once()
                
            # 3. Test REVIEW
            mock_model.predict.return_value = 0.5
            with patch.object(review_topic, 'send') as mock_send:
                async def mock_stream(): yield mock_tx
                await process(mock_stream())
                mock_send.assert_called_once()
