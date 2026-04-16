import pytest
from unittest.mock import MagicMock, patch
from services.shared.models import TransactionEvent
from services.feature_writer.app import account_tx_counts, update_features

@pytest.mark.asyncio
async def test_atomic_increment():
    mock_tx = TransactionEvent(
        transaction_id="tx_1",
        account_id="acc_99",
        amount_cents=100,
        merchant_id="m1",
        country_code="US",
        event_timestamp=1713110400
    )
    
    # Initialize count
    account_tx_counts["acc_99"] = 10
    
    with patch('services.feature_writer.app.store') as mock_store:
        async def mock_stream(): yield mock_tx
        await update_features(mock_stream())
        
        # Verify increment
        assert account_tx_counts["acc_99"] == 11
        
        # Verify Feast write
        mock_store.write_to_online_store.assert_called_once()
        df = mock_store.write_to_online_store.call_args[1]['df']
        assert df.iloc[0]['txn_count_1m'] == 11.0
