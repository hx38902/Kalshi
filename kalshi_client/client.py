"""Main Kalshi API client."""

import time
import requests
from urllib.parse import urljoin, urlparse

from kalshi_client.auth import KalshiAuth
from kalshi_client.exceptions import KalshiAPIError, KalshiRateLimitError
from kalshi_client.models import (
    ExchangeStatus,
    Market,
    Event,
    Position,
    Balance,
    OrderBook,
    Fill,
)


class KalshiClient:
    """HTTP client for the Kalshi Trading API v2."""

    def __init__(self, base_url: str, auth: KalshiAuth):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.session = requests.Session()

    def _request(self, method: str, endpoint: str, params: dict = None,
                  json_body: dict = None, _retries: int = 3) -> dict:
        """Make an authenticated request to the API with rate limit retry."""
        url = f"{self.base_url}{endpoint}"
        path = urlparse(url).path

        headers = self.auth.get_auth_headers(method.upper(), path)
        resp = self.session.request(
            method=method.upper(),
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=30,
        )

        if resp.status_code == 429 and _retries > 0:
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after else 2
            time.sleep(wait)
            return self._request(method, endpoint, params, json_body, _retries - 1)

        if resp.status_code == 429:
            raise KalshiRateLimitError()

        if resp.status_code >= 400:
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            raise KalshiAPIError(
                resp.status_code,
                body.get("message", resp.text[:200]),
                body,
            )

        if resp.status_code == 204:
            return {}
        return resp.json()

    # --- Exchange ---

    def get_exchange_status(self) -> ExchangeStatus:
        data = self._request("GET", "/exchange/status")
        return ExchangeStatus(
            exchange_active=data.get("exchange_active", False),
            trading_active=data.get("trading_active", False),
        )

    # --- Markets ---

    def get_markets(self, limit: int = 20, cursor: str = None, status: str = None,
                    event_ticker: str = None, series_ticker: str = None,
                    tickers: str = None) -> tuple[list[Market], str]:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if tickers:
            params["tickers"] = tickers

        data = self._request("GET", "/markets", params=params)
        markets = [Market.from_api(m) for m in data.get("markets", [])]
        return markets, data.get("cursor", "")

    def get_market(self, ticker: str) -> Market:
        data = self._request("GET", f"/markets/{ticker}")
        return Market.from_api(data.get("market", data))

    def get_orderbook(self, ticker: str, depth: int = 10) -> OrderBook:
        data = self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
        ob_data = data.get("orderbook") or data
        return OrderBook.from_api(ticker, ob_data)

    def get_market_candlesticks(self, ticker: str, series_ticker: str,
                                 period_interval: int = 1) -> list[dict]:
        params = {"series_ticker": series_ticker, "period_interval": period_interval}
        data = self._request("GET", f"/markets/{ticker}/candlesticks", params=params)
        return data.get("candlesticks", [])

    # --- Events ---

    def get_events(self, limit: int = 20, cursor: str = None, status: str = None,
                   with_nested_markets: bool = False) -> tuple[list[Event], str]:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        if with_nested_markets:
            params["with_nested_markets"] = "true"

        data = self._request("GET", "/events", params=params)
        events = [Event.from_api(e) for e in data.get("events", [])]
        return events, data.get("cursor", "")

    def get_event(self, event_ticker: str, with_nested_markets: bool = False) -> Event:
        params = {}
        if with_nested_markets:
            params["with_nested_markets"] = "true"
        data = self._request("GET", f"/events/{event_ticker}", params=params)
        return Event.from_api(data.get("event", data))

    # --- Portfolio ---

    def get_balance(self) -> Balance:
        data = self._request("GET", "/portfolio/balance")
        return Balance.from_api(data)

    def get_positions(self, limit: int = 100, cursor: str = None,
                      settlement_status: str = None,
                      ticker: str = None) -> tuple[list[Position], str]:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if settlement_status:
            params["settlement_status"] = settlement_status
        if ticker:
            params["ticker"] = ticker

        data = self._request("GET", "/portfolio/positions", params=params)
        positions = [Position.from_api(p) for p in data.get("market_positions", [])]
        return positions, data.get("cursor", "")

    def get_fills(self, limit: int = 100, cursor: str = None,
                  ticker: str = None) -> tuple[list[Fill], str]:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if ticker:
            params["ticker"] = ticker

        data = self._request("GET", "/portfolio/fills", params=params)
        fills = [Fill.from_api(f) for f in data.get("fills", [])]
        return fills, data.get("cursor", "")

    # --- Trading ---

    def create_order(self, ticker: str, side: str, action: str,
                     count: int, order_type: str = "market",
                     yes_price: int = None, no_price: int = None,
                     expiration_ts: int = None,
                     buy_max_cost: int = None) -> dict:
        body = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
        }
        if yes_price is not None:
            body["yes_price"] = yes_price
        if no_price is not None:
            body["no_price"] = no_price
        if expiration_ts is not None:
            body["expiration_ts"] = expiration_ts
        if buy_max_cost is not None:
            body["buy_max_cost"] = buy_max_cost

        return self._request("POST", "/portfolio/orders", json_body=body)

    def get_orders(self, limit: int = 100, cursor: str = None,
                   ticker: str = None, status: str = None) -> tuple[list[dict], str]:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status

        data = self._request("GET", "/portfolio/orders", params=params)
        return data.get("orders", []), data.get("cursor", "")

    def cancel_order(self, order_id: str) -> dict:
        return self._request("DELETE", f"/portfolio/orders/{order_id}")

    def batch_cancel_orders(self, market_ticker: str = None) -> dict:
        body = {}
        if market_ticker:
            body["market_ticker"] = market_ticker
        return self._request("DELETE", "/portfolio/orders", json_body=body)
