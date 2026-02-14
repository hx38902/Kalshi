"""Shared domain models used across all agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Side(str, Enum):
    YES = "yes"
    NO = "no"


class SignalSource(str, Enum):
    ORDERBOOK = "orderbook"
    NLP = "nlp"
    ARBITRAGE = "arbitrage"


@dataclass
class OrderbookSnapshot:
    """Minimal representation of a Kalshi contract orderbook."""

    ticker: str
    best_yes_bid: int  # cents
    best_no_bid: int   # cents
    synthetic_yes_ask: int  # = 100 - best_no_bid
    spread_cents: int       # synthetic_yes_ask - best_yes_bid
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_liquidity_void(self) -> bool:
        return self.spread_cents > 0  # threshold applied externally


@dataclass
class Signal:
    """A trading signal produced by any agent."""

    source: SignalSource
    ticker: str
    side: Side
    implied_prob: float        # 0-1
    estimated_fair_prob: float # 0-1
    edge: float                # fair - implied  (positive = buy YES)
    confidence: float          # 0-1
    rationale: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class KellyResult:
    """Output of the Kelly position-sizing calculation."""

    optimal_fraction: float   # f*
    position_size_usd: float
    net_ev: float             # expected value after fees
    should_trade: bool


@dataclass
class TradeOrder:
    """An order to be placed (or paper-logged)."""

    ticker: str
    side: Side
    contracts: int
    limit_price_cents: int  # 1-99
    signal: Signal
    kelly: KellyResult
    paper: bool = True
    order_id: Optional[str] = None
    fill_price_cents: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
