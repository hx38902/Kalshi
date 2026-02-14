"""Unit tests for the KalshiClient (mocked HTTP)."""

import pytest
from unittest.mock import MagicMock, patch
from kalshi_client.client import KalshiClient
from kalshi_client.auth import KalshiAuth
from kalshi_client.exceptions import KalshiAPIError, KalshiRateLimitError


@pytest.fixture
def mock_auth():
    auth = MagicMock(spec=KalshiAuth)
    auth.get_auth_headers.return_value = {
        "KALSHI-ACCESS-KEY": "test",
        "KALSHI-ACCESS-SIGNATURE": "sig",
        "KALSHI-ACCESS-TIMESTAMP": "12345",
        "Content-Type": "application/json",
    }
    return auth


@pytest.fixture
def client(mock_auth):
    return KalshiClient(base_url="https://api.test.com/trade-api/v2", auth=mock_auth)


def test_request_success(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"exchange_active": True, "trading_active": True}

    with patch.object(client.session, "request", return_value=mock_resp):
        status = client.get_exchange_status()
        assert status.exchange_active is True
        assert status.trading_active is True


def test_request_rate_limit(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "1"}

    with patch("kalshi_client.client.time.sleep"), \
         patch.object(client.session, "request", return_value=mock_resp):
        with pytest.raises(KalshiRateLimitError):
            client._request("GET", "/exchange/status", _retries=0)


def test_request_rate_limit_retries(client):
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"Retry-After": "1"}

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"exchange_active": True, "trading_active": True}

    with patch("kalshi_client.client.time.sleep") as mock_sleep, \
         patch.object(client.session, "request", side_effect=[mock_429, mock_200]):
        status = client.get_exchange_status()
        assert status.exchange_active is True
        mock_sleep.assert_called_once_with(1)


def test_request_api_error(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"message": "Not found"}
    mock_resp.text = "Not found"

    with patch.object(client.session, "request", return_value=mock_resp):
        with pytest.raises(KalshiAPIError) as exc_info:
            client.get_market("NONEXISTENT")
        assert exc_info.value.status_code == 404


def test_get_markets(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "markets": [
            {"ticker": "MKT1", "event_ticker": "E1", "title": "Market 1", "status": "open"},
            {"ticker": "MKT2", "event_ticker": "E2", "title": "Market 2", "status": "open"},
        ],
        "cursor": "next_page",
    }

    with patch.object(client.session, "request", return_value=mock_resp):
        markets, cursor = client.get_markets(limit=2)
        assert len(markets) == 2
        assert markets[0].ticker == "MKT1"
        assert cursor == "next_page"


def test_get_balance(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"balance": 5000, "payout": 200}

    with patch.object(client.session, "request", return_value=mock_resp):
        balance = client.get_balance()
        assert balance.balance == 5000
        assert balance.balance_dollars == 50.0


def test_create_order(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "order": {"order_id": "ord123", "status": "resting"}
    }

    with patch.object(client.session, "request", return_value=mock_resp):
        result = client.create_order(
            ticker="MKT1", side="yes", action="buy", count=1,
            order_type="limit", yes_price=50,
        )
        assert result["order"]["order_id"] == "ord123"


def test_cancel_order(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch.object(client.session, "request", return_value=mock_resp):
        result = client.cancel_order("ord123")
        assert result == {}
