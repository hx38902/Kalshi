"""
Orderbook Reciprocity Agent
============================
Scans Kalshi orderbooks for "Liquidity Voids" — wide spreads between the
Best YES Bid and the *Synthetic YES Ask* (100 − Best NO Bid).

When the spread exceeds the configured threshold (default 3¢), the agent
flags the contract as a stink-bid entry opportunity.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from kalshi_alpha_suite.config import SuiteConfig
from kalshi_alpha_suite.kalshi_client import KalshiClient
from kalshi_alpha_suite.models import OrderbookSnapshot, Side, Signal, SignalSource

logger = logging.getLogger(__name__)


def _parse_orderbook(ticker: str, raw: dict) -> Optional[OrderbookSnapshot]:
    """
    Parse a Kalshi orderbook response into an OrderbookSnapshot.

    Kalshi orderbooks contain 'yes' and 'no' arrays, each a list of
    [price_cents, quantity] pairs sorted best-first.
    """
    ob = raw.get("orderbook", raw)

    yes_bids: list = ob.get("yes", [])
    no_bids: list = ob.get("no", [])

    if not yes_bids and not no_bids:
        return None

    # Best YES bid = highest price someone will pay for YES
    best_yes_bid = yes_bids[0][0] if yes_bids else 0
    # Best NO bid = highest price someone will pay for NO
    best_no_bid = no_bids[0][0] if no_bids else 0

    # Synthetic YES ask: to *buy* YES you can equivalently *sell* NO at
    # the best NO bid.  The YES-equivalent price is (100 − best_no_bid).
    synthetic_yes_ask = 100 - best_no_bid if best_no_bid > 0 else 100

    spread = synthetic_yes_ask - best_yes_bid

    return OrderbookSnapshot(
        ticker=ticker,
        best_yes_bid=best_yes_bid,
        best_no_bid=best_no_bid,
        synthetic_yes_ask=synthetic_yes_ask,
        spread_cents=spread,
    )


class OrderbookAgent:
    """Continuously scans orderbooks and emits signals for liquidity voids."""

    def __init__(self, cfg: SuiteConfig, client: KalshiClient) -> None:
        self.cfg = cfg
        self.client = client
        self.threshold = cfg.spread_threshold_cents

    async def scan_market(self, ticker: str) -> Optional[Signal]:
        """Check a single market for a liquidity void."""
        try:
            raw = await self.client.get_orderbook(ticker)
        except Exception:
            logger.warning("Failed to fetch orderbook for %s", ticker, exc_info=True)
            return None

        snap = _parse_orderbook(ticker, raw)
        if snap is None:
            return None

        logger.debug(
            "%s  YES_bid=%d  synth_ask=%d  spread=%d",
            ticker,
            snap.best_yes_bid,
            snap.synthetic_yes_ask,
            snap.spread_cents,
        )

        if snap.spread_cents <= self.threshold:
            return None

        # Midpoint as the implied fair probability
        midpoint = (snap.best_yes_bid + snap.synthetic_yes_ask) / 2 / 100
        implied = snap.best_yes_bid / 100 if snap.best_yes_bid else 0.5

        signal = Signal(
            source=SignalSource.ORDERBOOK,
            ticker=ticker,
            side=Side.YES,
            implied_prob=implied,
            estimated_fair_prob=midpoint,
            edge=midpoint - implied,
            confidence=min(snap.spread_cents / 10, 1.0),
            rationale=(
                f"Liquidity void: spread={snap.spread_cents}¢ "
                f"(YES bid={snap.best_yes_bid}¢, synth ask={snap.synthetic_yes_ask}¢). "
                f"Stink bid opportunity at {snap.best_yes_bid + 1}¢."
            ),
        )
        logger.info("SIGNAL %s: %s", ticker, signal.rationale)
        return signal

    async def scan_all_open_markets(
        self,
        *,
        limit: int = 200,
    ) -> List[Signal]:
        """Paginate through open markets and scan each orderbook."""
        signals: List[Signal] = []
        cursor: Optional[str] = None

        fetched = 0
        while fetched < limit:
            batch_size = min(100, limit - fetched)
            resp = await self.client.get_markets(
                status="open", limit=batch_size, cursor=cursor,
            )
            markets = resp.get("markets", [])
            if not markets:
                break

            tasks = [self.scan_market(m["ticker"]) for m in markets]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Signal):
                    signals.append(r)
                elif isinstance(r, Exception):
                    logger.warning("scan error: %s", r)

            cursor = resp.get("cursor")
            fetched += len(markets)
            if not cursor:
                break

        logger.info("Orderbook scan complete: %d signals from %d markets", len(signals), fetched)
        return signals
