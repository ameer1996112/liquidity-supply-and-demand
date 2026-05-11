import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

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

@patch("src.adapters.execution.meta_api_adapter._is_forex_weekend", return_value=False)
@patch("src.adapters.execution.meta_api_adapter.MetaApiAdapter._send_broker_disconnect_alert")
@patch("src.core.circuit_breaker.set_metaapi_circuit_open")
@patch("src.adapters.execution.meta_api_adapter.time.sleep")
@patch("src.adapters.execution.meta_api_adapter.requests.get")
def test_metaapi_504_opens_account_scoped_circuit_breaker(
    mock_get,
    mock_sleep,
    mock_set_circuit,
    mock_alert,
    _mock_weekend,
):
    """A disconnected account should not open the legacy global breaker."""
    mock_resp = MagicMock()
    mock_resp.status_code = 504
    mock_resp.text = '{"error":"TimeoutError"}'
    mock_get.return_value = mock_resp

    adapter = MetaApiAdapter(
        token="valid-token",
        account_id="acc-id",
        account_name="ACG-DEMO-2",
    )

    resp = adapter._request_with_retry("GET", "https://example.test/account", timeout=1)

    assert resp is mock_resp
    mock_set_circuit.assert_called_once_with(
        ttl_seconds=120,
        account_name="ACG-DEMO-2",
    )
    assert mock_sleep.call_count == 2
    mock_alert.assert_called_once_with("504_broker_not_connected")


@patch("src.adapters.execution.meta_api_adapter.MetaApiAdapter._check_circuit_breaker", return_value=True)
def test_metaapi_open_positions_records_circuit_breaker_error(_mock_check):
    adapter = MetaApiAdapter(token="valid-token", account_id="acc-id")

    positions = adapter.get_open_positions()

    assert positions == []
    assert adapter.last_positions_fetch_error == "circuit_breaker_open"


class _AccountSyncFakeTable:
    def __init__(self, client, name: str) -> None:
        self.client = client
        self.name = name
        self.op = ""
        self.payload = None

    def select(self, *args, **kwargs):
        self.op = "select"
        return self

    def update(self, payload: dict):
        self.op = "update"
        self.payload = payload
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        if self.name == "account_strategies" and self.op == "select":
            return SimpleNamespace(data=[
                {
                    "account_name": "ACG-DEMO-2",
                    "broker_profile_id": 7,
                    "meta_api_account_id": "acc-id",
                    "meta_api_token_env_key": "META_API_TOKEN",
                }
            ])
        if self.name == "account_strategies" and self.op == "update":
            self.client.updates.append(self.payload)
        return SimpleNamespace(data=[])


class _AccountSyncFakeClient:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    def table(self, name: str) -> _AccountSyncFakeTable:
        return _AccountSyncFakeTable(self, name)


class _UnavailablePositionsAdapter:
    last_positions_fetch_error = None

    def get_open_positions(self):
        self.last_positions_fetch_error = "circuit_breaker_open"
        return []


def test_account_sync_skips_reconciliation_when_positions_fetch_failed():
    client = _AccountSyncFakeClient()
    service = AccountSyncService(client)

    with patch.object(service, "_get_adapter_for_account", return_value=_UnavailablePositionsAdapter()), \
         patch.object(service, "_reconcile_positions") as mock_reconcile:
        result = service.sync_account_positions("ACG-DEMO-2")

    assert result is False
    mock_reconcile.assert_not_called()
    assert client.updates[-1]["connection_status"] == "error"


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
