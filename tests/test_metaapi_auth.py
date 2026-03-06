import os
import pytest
from unittest.mock import patch, MagicMock
from src.adapters.execution.meta_api_adapter import MetaApiAdapter
from src.services.account_sync_service import AccountSyncService

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {"META_API_TOKEN": "valid-token"}):
        yield

def test_metaapi_adapter_headers():
    """Verify MetaApiAdapter forms the correct headers."""
    adapter = MetaApiAdapter(token="test-token", account_id="acc-id")
    headers = adapter._headers()
    assert headers["auth-token"] == "test-token"
    assert "Bearer" not in headers["auth-token"]
    assert "Authorization" not in headers

@patch("src.adapters.execution.meta_api_adapter.requests.get")
def test_metaapi_adapter_401_throws_permission_error(mock_get):
    """Verify MetaApiAdapter raises PermissionError on 401."""
    adapter = MetaApiAdapter(token="invalid-token", account_id="acc-id")
    
    # Mock a 401 response
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_get.return_value = mock_resp
    
    with pytest.raises(PermissionError) as excinfo:
        adapter.get_account_information()
        
    assert str(excinfo.value) == "METAAPI_AUTH_FAILED"

def test_account_sync_service_missing_token_raises_value_error():
    """Verify AccountSyncService raises ValueError when token is missing."""
    service = AccountSyncService(MagicMock())
    
    account_data = {
        "account_name": "Test Account",
        "meta_api_account_id": "acc-id",
        "meta_api_token_env_key": "MISSING_ENV_VAR"
    }
    
    with pytest.raises(ValueError) as excinfo:
        service._get_adapter_for_account(account_data)
        
    assert str(excinfo.value) == "METAAPI_TOKEN_MISSING"

@patch("src.services.account_sync_service.AccountSyncService._get_adapter_for_account")
def test_account_sync_service_status_catches_auth_errors(mock_get_adapter):
    """Verify AccountSyncService catches auth exceptions and updates DB."""
    mock_db = MagicMock()
    # Mock DB table chain: client.table().update().eq().execute()
    mock_execute = MagicMock()
    mock_eq = MagicMock()
    mock_eq.eq.return_value = mock_execute
    mock_update = MagicMock()
    mock_update.update.return_value = mock_eq
    mock_db.table.return_value = mock_update
    
    service = AccountSyncService(mock_db)
    
    # Test 1: Missing Token → implementation sets "not_configured"
    mock_get_adapter.side_effect = ValueError("METAAPI_TOKEN_MISSING")

    result = service.sync_account_status("Test1")
    assert result is False

    # Verify DB update called with "not_configured" (implementation-defined status)
    update_call_args = mock_update.update.call_args[0][0]
    assert update_call_args["connection_status"] == "not_configured"

    # Test 2: 401 Unauthorized → implementation sets "error"
    mock_get_adapter.side_effect = PermissionError("METAAPI_AUTH_FAILED")

    result = service.sync_account_status("Test2")
    assert result is False

    # Verify DB update called with "error" (implementation-defined status)
    update_call_args = mock_update.update.call_args[0][0]
    assert update_call_args["connection_status"] == "error"
