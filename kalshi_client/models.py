"""Data models for Kalshi API responses."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExchangeStatus:
    exchange_active: bool
    trading_active: bool


@dataclass
class Market:
    ticker: str
    event_ticker: str
    title: str
    status: str
    yes_bid: float = 0.0
    yes_ask: float = 0.0
    no_bid: float = 0.0
    no_ask: float = 0.0
    volume: int = 0
    open_interest: int = 0
    last_price: float = 0.0
    result: str = ""
    subtitle: str = ""
    close_time: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "Market":
        return cls(
            ticker=data.get("ticker", ""),
            event_ticker=data.get("event_ticker", ""),
            title=data.get("title", ""),
            status=data.get("status", ""),
            yes_bid=data.get("yes_bid", 0) / 100 if data.get("yes_bid") else 0.0,
            yes_ask=data.get("yes_ask", 0) / 100 if data.get("yes_ask") else 0.0,
            no_bid=data.get("no_bid", 0) / 100 if data.get("no_bid") else 0.0,
            no_ask=data.get("no_ask", 0) / 100 if data.get("no_ask") else 0.0,
            volume=data.get("volume", 0),
            open_interest=data.get("open_interest", 0),
            last_price=data.get("last_price", 0) / 100 if data.get("last_price") else 0.0,
            result=data.get("result", ""),
            subtitle=data.get("subtitle", ""),
            close_time=data.get("close_time", ""),
        )


@dataclass
class Event:
    event_ticker: str
    title: str
    category: str
    status: str
    markets: list = field(default_factory=list)
    subtitle: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "Event":
        return cls(
            event_ticker=data.get("event_ticker", ""),
            title=data.get("title", ""),
            category=data.get("category", ""),
            status=data.get("status", ""),
            markets=data.get("markets", []),
            subtitle=data.get("subtitle", ""),
        )


@dataclass
class Position:
    ticker: str
    market_exposure: int
    resting_orders_count: int
    total_traded: int
    realized_pnl: int
    fees_paid: int

    @classmethod
    def from_api(cls, data: dict) -> "Position":
        return cls(
            ticker=data.get("ticker", ""),
            market_exposure=data.get("market_exposure", 0),
            resting_orders_count=data.get("resting_orders_count", 0),
            total_traded=data.get("total_traded", 0),
            realized_pnl=data.get("realized_pnl", 0),
            fees_paid=data.get("fees_paid", 0),
        )


@dataclass
class Balance:
    balance: int  # in cents
    payout: int

    @property
    def balance_dollars(self) -> float:
        return self.balance / 100

    @classmethod
    def from_api(cls, data: dict) -> "Balance":
        return cls(
            balance=data.get("balance", 0),
            payout=data.get("payout", 0),
        )


@dataclass
class OrderBook:
    ticker: str
    yes_bids: list = field(default_factory=list)
    yes_asks: list = field(default_factory=list)
    no_bids: list = field(default_factory=list)
    no_asks: list = field(default_factory=list)

    @classmethod
    def from_api(cls, ticker: str, data: dict) -> "OrderBook":
        yes_data = data.get("yes") or {}
        no_data = data.get("no") or {}
        return cls(
            ticker=ticker,
            yes_bids=yes_data.get("bids") or [],
            yes_asks=yes_data.get("asks") or [],
            no_bids=no_data.get("bids") or [],
            no_asks=no_data.get("asks") or [],
        )


@dataclass
class Fill:
    trade_id: str
    ticker: str
    side: str
    action: str
    count: int
    yes_price: int
    no_price: int
    created_time: str

    @classmethod
    def from_api(cls, data: dict) -> "Fill":
        return cls(
            trade_id=data.get("trade_id", ""),
            ticker=data.get("ticker", ""),
            side=data.get("side", ""),
            action=data.get("action", ""),
            count=data.get("count", 0),
            yes_price=data.get("yes_price", 0),
            no_price=data.get("no_price", 0),
            created_time=data.get("created_time", ""),
        )
