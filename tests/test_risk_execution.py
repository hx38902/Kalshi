"""Unit tests for the Risk & Execution agent sizing logic."""

from unittest.mock import MagicMock

from kalshi_alpha_suite.agents.risk_execution_agent import RiskExecutionAgent
from kalshi_alpha_suite.config import SuiteConfig
from kalshi_alpha_suite.models import Side, Signal, SignalSource


def _make_cfg(**overrides) -> SuiteConfig:
    defaults = dict(
        kalshi_base_url="https://example.com",
        kalshi_key_id="test",
        kalshi_private_key_b64="",
        kalshi_private_key_path="",
        openai_api_key="test",
        openai_model="gpt-4o",
        polymarket_api_url="https://example.com",
        paper_trading=True,
        kalshi_fee_rate=0.07,
        spread_threshold_cents=3,
        kelly_edge_min=0.05,
        nlp_prob_shift_min=0.10,
        max_position_usd=500.0,
        kelly_fraction=0.25,
    )
    defaults.update(overrides)
    return SuiteConfig(**defaults)


def _make_signal(implied: float = 0.40, fair: float = 0.55, side: Side = Side.YES) -> Signal:
    return Signal(
        source=SignalSource.ORDERBOOK,
        ticker="TEST-TICKER",
        side=side,
        implied_prob=implied,
        estimated_fair_prob=fair,
        edge=abs(fair - implied),
        confidence=0.8,
        rationale="test signal",
    )


def test_size_positive_ev():
    cfg = _make_cfg()
    agent = RiskExecutionAgent(cfg, MagicMock())
    sig = _make_signal(implied=0.40, fair=0.60)
    result = agent.size(sig, bankroll_usd=1000)
    assert result.should_trade is True
    assert result.net_ev > 0
    assert result.position_size_usd > 0


def test_size_negative_ev():
    cfg = _make_cfg()
    agent = RiskExecutionAgent(cfg, MagicMock())
    sig = _make_signal(implied=0.50, fair=0.51)
    result = agent.size(sig, bankroll_usd=1000)
    # Edge is too small for kelly_edge_min=0.05
    assert result.should_trade is False


def test_size_respects_max_position():
    cfg = _make_cfg(max_position_usd=100.0, kelly_fraction=1.0)
    agent = RiskExecutionAgent(cfg, MagicMock())
    sig = _make_signal(implied=0.20, fair=0.80)
    result = agent.size(sig, bankroll_usd=100_000)
    assert result.position_size_usd <= 100.0


def test_build_order_no_trade():
    cfg = _make_cfg()
    agent = RiskExecutionAgent(cfg, MagicMock())
    sig = _make_signal(implied=0.50, fair=0.51)
    kelly = agent.size(sig, bankroll_usd=1000)
    order = agent.build_order(sig, kelly)
    assert order is None


def test_build_order_yes_side():
    cfg = _make_cfg()
    agent = RiskExecutionAgent(cfg, MagicMock())
    sig = _make_signal(implied=0.35, fair=0.60, side=Side.YES)
    kelly = agent.size(sig, bankroll_usd=2000)
    if kelly.should_trade:
        order = agent.build_order(sig, kelly)
        assert order is not None
        assert order.side == Side.YES
        assert 1 <= order.limit_price_cents <= 99
        assert order.paper is True
