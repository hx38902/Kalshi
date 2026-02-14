"""Unit tests for core models and Kelly math."""

from kalshi_alpha_suite.agents.arbitrage_agent import kelly_criterion
from kalshi_alpha_suite.agents.risk_execution_agent import (
    kelly_fraction,
    net_payout_after_fees,
)
from kalshi_alpha_suite.agents.orderbook_agent import _parse_orderbook
from kalshi_alpha_suite.models import (
    KellyResult,
    OrderbookSnapshot,
    Side,
    Signal,
    SignalSource,
)


# ── Kelly Criterion tests ──────────────────────────────────────


def test_kelly_positive_edge():
    """60% true prob at even money (b=1) → f* = 0.20."""
    assert abs(kelly_fraction(0.6, 1.0) - 0.20) < 1e-9


def test_kelly_no_edge():
    """50% true prob at even money → f* = 0."""
    assert abs(kelly_fraction(0.5, 1.0) - 0.0) < 1e-9


def test_kelly_negative_edge():
    """40% true prob at even money → f* = -0.20 (don't bet)."""
    assert kelly_fraction(0.4, 1.0) < 0


def test_kelly_criterion_alias():
    """The arb agent's kelly_criterion should match."""
    assert abs(kelly_criterion(0.7, 2.0) - kelly_fraction(0.7, 2.0)) < 1e-9


def test_net_payout_after_fees():
    """7% fee on gross b=1.5 → net b = 1.395."""
    assert abs(net_payout_after_fees(1.5, 0.07) - 1.395) < 1e-9


# ── Orderbook parsing tests ───────────────────────────────────


def test_parse_orderbook_basic():
    raw = {
        "orderbook": {
            "yes": [[40, 100], [38, 50]],
            "no": [[55, 80], [53, 40]],
        }
    }
    snap = _parse_orderbook("TEST-TICKER", raw)
    assert snap is not None
    assert snap.best_yes_bid == 40
    assert snap.best_no_bid == 55
    assert snap.synthetic_yes_ask == 45  # 100 - 55
    assert snap.spread_cents == 5  # 45 - 40


def test_parse_orderbook_no_bids():
    raw = {"orderbook": {"yes": [], "no": []}}
    snap = _parse_orderbook("EMPTY", raw)
    assert snap is None


def test_parse_orderbook_only_yes():
    raw = {"orderbook": {"yes": [[30, 10]], "no": []}}
    snap = _parse_orderbook("YES-ONLY", raw)
    assert snap is not None
    assert snap.best_yes_bid == 30
    assert snap.synthetic_yes_ask == 100  # no NO bids → ask = 100
    assert snap.spread_cents == 70


def test_liquidity_void_flag():
    snap = OrderbookSnapshot(
        ticker="T",
        best_yes_bid=40,
        best_no_bid=55,
        synthetic_yes_ask=45,
        spread_cents=5,
    )
    assert snap.has_liquidity_void is True

    snap2 = OrderbookSnapshot(
        ticker="T",
        best_yes_bid=45,
        best_no_bid=55,
        synthetic_yes_ask=45,
        spread_cents=0,
    )
    assert snap2.has_liquidity_void is False


# ── Signal model tests ────────────────────────────────────────


def test_signal_creation():
    sig = Signal(
        source=SignalSource.ORDERBOOK,
        ticker="ABC-123",
        side=Side.YES,
        implied_prob=0.40,
        estimated_fair_prob=0.50,
        edge=0.10,
        confidence=0.8,
        rationale="test",
    )
    assert sig.source == SignalSource.ORDERBOOK
    assert sig.edge == 0.10
