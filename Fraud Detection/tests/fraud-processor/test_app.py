import pytest
from unittest.mock import MagicMock, patch
from shared.models import TransactionEvent, DecisionEnvelope

# Since app.py is not yet created, this test will fail on import.
# That's part of TDD (Red phase).

@pytest.mark.asyncio
async def test_process_logic_allow():
    from services.fraud_processor.app import process, allow_topic, block_topic
    
    # Mock dependencies
    mock_tx = TransactionEvent(
        transaction_id="tx1",
        account_id="acc1",
        amount_cents=100,
        merchant_id="m1",
        country_code="US",
        event_timestamp=1713110400
    )
    
    with patch('services.fraud_processor.app.store') as mock_store:
        with patch('services.fraud_processor.app.model') as mock_model:
            # Set up mocks
            mock_store.get_online_features.return_value.to_dict.return_value = {"txn_count_1m": 1}
            mock_model.predict.return_value = 0.1 # < 0.5 -> ALLOW
            
            with patch.object(allow_topic, 'send') as mock_allow_send:
                with patch.object(block_topic, 'send') as mock_block_send:
                    # Run the agent logic for one event
                    # We need to simulate the "async for tx in transactions"
                    async def mock_stream():
                        yield mock_tx
                    
                    await process(mock_stream())
                    
                    # Verify
                    mock_allow_send.assert_called_once()
                    mock_block_send.assert_not_called()
                    
                    envelope = mock_allow_send.call_args[1]['value']
                    assert envelope.transaction_id == "tx1"
                    assert envelope.decision == "ALLOW"
                    assert envelope.risk_score == 0.1

@pytest.mark.asyncio
async def test_process_logic_block():
    from services.fraud_processor.app import process, allow_topic, block_topic
    
    # Mock dependencies
    mock_tx = TransactionEvent(
        transaction_id="tx2",
        account_id="acc1",
        amount_cents=200000, # $2000
        merchant_id="m1",
        country_code="US",
        event_timestamp=1713110400
    )
    
    with patch('services.fraud_processor.app.store') as mock_store:
        with patch('services.fraud_processor.app.model') as mock_model:
            # Set up mocks
            mock_store.get_online_features.return_value.to_dict.return_value = {"txn_count_1m": 1}
            mock_model.predict.return_value = 0.7 # >= 0.5 -> BLOCK
            
            with patch.object(allow_topic, 'send') as mock_allow_send:
                with patch.object(block_topic, 'send') as mock_block_send:
                    # Run the agent logic for one event
                    async def mock_stream():
                        yield mock_tx
                    
                    await process(mock_stream())
                    
                    # Verify
                    mock_allow_send.assert_not_called()
                    mock_block_send.assert_called_once()
                    
                    envelope = mock_block_send.call_args[1]['value']
                    assert envelope.transaction_id == "tx2"
                    assert envelope.decision == "BLOCK"
                    assert envelope.risk_score == 0.7
