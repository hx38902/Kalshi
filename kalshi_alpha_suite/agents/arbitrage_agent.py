"""
Arbitrageur Agent
==================
Compares Kalshi's implied probability against an external reference
(e.g. Polymarket CLOB API) and flags mispriced contracts where the
Kelly Criterion indicates an edge > 5 %.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from kalshi_alpha_suite.config import SuiteConfig
from kalshi_alpha_suite.kalshi_client import KalshiClient
from kalshi_alpha_suite.models import Side, Signal, SignalSource

logger = logging.getLogger(__name__)


def kelly_criterion(p: float, b: float) -> float:
    """
    Calculate the Kelly fraction.

    f* = (p(b + 1) - 1) / b

    Args:
        p: estimated true probability of winning.
        b: decimal odds minus 1  (net payout per $1 wagered).

    Returns:
        Optimal fraction of bankroll to wager (can be negative → don't bet).
    """
    if b <= 0:
        return 0.0
    return (p * (b + 1) - 1) / b


class ArbitrageAgent:
    """Detects cross-platform mispricings using Kalshi + an external feed."""

    def __init__(
        self,
        cfg: SuiteConfig,
        kalshi: KalshiClient,
        external_url: Optional[str] = None,
    ) -> None:
        self.cfg = cfg
        self.kalshi = kalshi
        self.external_url = external_url or cfg.polymarket_api_url
        self._http = httpx.AsyncClient(timeout=15.0)

    # ------------------------------------------------------------------
    # External price fetching (Polymarket CLOB as default)
    # ------------------------------------------------------------------

    async def _fetch_polymarket_markets(self) -> List[Dict[str, Any]]:
        """Fetch active markets from Polymarket CLOB."""
        try:
            resp = await self._http.get(
                f"{self.external_url}/markets",
                params={"active": "true", "limit": 100},
            )
            resp.raise_for_status()
            data = resp.json()
            # Polymarket returns a list or a paginated wrapper
            if isinstance(data, list):
                return data
            return data.get("data", data.get("markets", []))
        except Exception:
            logger.warning("Polymarket fetch failed", exc_info=True)
            return []

    @staticmethod
    def _match_markets(
        kalshi_markets: List[Dict[str, Any]],
        external_markets: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Heuristic matching between Kalshi and external markets based on
        overlapping keywords in titles.  Production systems should use a
        proper entity-resolution pipeline.
        """
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

        def _tokens(title: str) -> set:
            return {w.lower().strip("?.!,") for w in title.split() if len(w) > 3}

        for km in kalshi_markets:
            kt = _tokens(km.get("title", ""))
            if not kt:
                continue
            for em in external_markets:
                et = _tokens(em.get("question", em.get("title", "")))
                overlap = kt & et
                if len(overlap) >= 3:
                    pairs.append((km, em))
                    break  # first match only

        return pairs

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    async def scan(self) -> List[Signal]:
        """
        1. Fetch Kalshi open markets.
        2. Fetch external reference markets.
        3. Match pairs by title heuristic.
        4. Compare implied probs; flag if Kelly edge > threshold.
        """
        kalshi_resp = await self.kalshi.get_markets(status="open", limit=200)
        kalshi_markets = kalshi_resp.get("markets", [])

        ext_markets = await self._fetch_polymarket_markets()
        if not ext_markets:
            logger.info("No external markets fetched; skipping arbitrage scan.")
            return []

        pairs = self._match_markets(kalshi_markets, ext_markets)
        logger.info("Matched %d cross-platform pairs", len(pairs))

        signals: List[Signal] = []
        for km, em in pairs:
            ticker = km["ticker"]

            # Kalshi implied prob from yes_price / last_price
            kalshi_prob = (km.get("yes_price", 0) or km.get("last_price", 50)) / 100

            # External prob: try common field names
            ext_prob = (
                em.get("outcomePrices", [None, None])[0]
                or em.get("yes_price", em.get("lastTradePrice", 0.5))
            )
            try:
                ext_prob = float(ext_prob)
            except (TypeError, ValueError):
                continue

            # Edge: we treat external as "fair" and Kalshi as "market"
            edge = ext_prob - kalshi_prob

            # Decide side
            if edge > 0:
                side = Side.YES
                p = ext_prob
                market_price = kalshi_prob
            elif edge < 0:
                side = Side.NO
                p = 1 - ext_prob
                market_price = 1 - kalshi_prob
                edge = abs(edge)
            else:
                continue

            # Decimal odds from Kalshi price
            if market_price <= 0 or market_price >= 1:
                continue
            b = (1 / market_price) - 1  # net payout per $1

            f_star = kelly_criterion(p, b)
            if f_star < self.cfg.kelly_edge_min:
                continue

            signal = Signal(
                source=SignalSource.ARBITRAGE,
                ticker=ticker,
                side=side,
                implied_prob=kalshi_prob,
                estimated_fair_prob=ext_prob if side == Side.YES else 1 - ext_prob,
                edge=edge,
                confidence=min(f_star, 1.0),
                rationale=(
                    f"Cross-platform arb: Kalshi={kalshi_prob:.2f} vs "
                    f"External={ext_prob:.2f}, Kelly f*={f_star:.3f}"
                ),
            )
            signals.append(signal)
            logger.info("ARB SIGNAL %s %s edge=%.3f kelly=%.3f", ticker, side.value, edge, f_star)

        logger.info("Arbitrage scan complete: %d signals from %d pairs", len(signals), len(pairs))
        return signals

    async def close(self) -> None:
        await self._http.aclose()
