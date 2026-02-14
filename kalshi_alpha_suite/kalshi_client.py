"""
Async Kalshi API v2 client with Ed25519 request signing.

Authentication follows Kalshi's scheme:
  - Each request is signed with an Ed25519 private key.
  - The signature covers: timestamp + method + path (no body).
  - Headers sent: KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

from kalshi_alpha_suite.config import SuiteConfig

logger = logging.getLogger(__name__)


class KalshiAuth:
    """Handles Ed25519 signing for Kalshi API v2 requests."""

    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        self.key_id = key_id
        self._private_key = private_key

    @classmethod
    def from_config(cls, cfg: SuiteConfig) -> "KalshiAuth":
        if cfg.kalshi_private_key_path:
            with open(cfg.kalshi_private_key_path, "rb") as f:
                pem_data = f.read()
            private_key = load_pem_private_key(pem_data, password=None)
        elif cfg.kalshi_private_key_b64:
            decoded = base64.b64decode(cfg.kalshi_private_key_b64)
            # Try PEM first, fall back to raw 32-byte seed
            try:
                private_key = load_pem_private_key(decoded, password=None)
            except Exception:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                    Ed25519PrivateKey,
                )
                private_key = Ed25519PrivateKey.from_private_bytes(decoded[:32])
        else:
            raise ValueError(
                "Provide KALSHI_PRIVATE_KEY_B64 or KALSHI_PRIVATE_KEY_PATH"
            )
        if not isinstance(private_key, Ed25519PrivateKey):
            raise TypeError(f"Expected Ed25519 key, got {type(private_key)}")
        return cls(key_id=cfg.kalshi_key_id, private_key=private_key)

    def sign_request(self, method: str, path: str) -> Dict[str, str]:
        """Return auth headers for a single request."""
        timestamp_ms = str(int(time.time() * 1000))
        message = timestamp_ms + method.upper() + path
        signature = self._private_key.sign(message.encode())
        sig_b64 = base64.b64encode(signature).decode()
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": sig_b64,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        }


class KalshiClient:
    """Async HTTP client for Kalshi Trade API v2."""

    def __init__(self, cfg: SuiteConfig) -> None:
        self.cfg = cfg
        self.base_url = cfg.kalshi_base_url.rstrip("/")
        self._auth: Optional[KalshiAuth] = None
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    async def _ensure_auth(self) -> KalshiAuth:
        if self._auth is None:
            self._auth = KalshiAuth.from_config(self.cfg)
        return self._auth

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        auth = await self._ensure_auth()
        headers = auth.sign_request(method, path)
        resp = await self._http.request(
            method,
            path,
            params=params,
            json=json_body,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_markets(
        self,
        *,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List markets with optional filters."""
        params: Dict[str, Any] = {"status": status, "limit": limit}
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/markets", params=params)

    async def get_market(self, ticker: str) -> Dict[str, Any]:
        """Get a single market by ticker."""
        return await self._request("GET", f"/markets/{ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> Dict[str, Any]:
        """Fetch the orderbook for a contract."""
        return await self._request(
            "GET",
            f"/markets/{ticker}/orderbook",
            params={"depth": depth},
        )

    async def get_event(self, event_ticker: str) -> Dict[str, Any]:
        return await self._request("GET", f"/events/{event_ticker}")

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------

    async def place_order(
        self,
        *,
        ticker: str,
        side: str,
        action: str = "buy",
        order_type: str = "limit",
        count: int = 1,
        yes_price: Optional[int] = None,
        no_price: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Place an order. Prices in cents (1-99)."""
        body: Dict[str, Any] = {
            "ticker": ticker,
            "action": action,
            "side": side,
            "type": order_type,
            "count": count,
        }
        if yes_price is not None:
            body["yes_price"] = yes_price
        if no_price is not None:
            body["no_price"] = no_price
        return await self._request("POST", "/portfolio/orders", json_body=body)

    async def get_positions(self) -> Dict[str, Any]:
        return await self._request("GET", "/portfolio/positions")

    async def get_balance(self) -> Dict[str, Any]:
        return await self._request("GET", "/portfolio/balance")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "KalshiClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
