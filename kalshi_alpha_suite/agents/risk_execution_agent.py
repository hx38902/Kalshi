"""
Risk & Execution Agent
=======================
Implements Kelly Criterion position sizing with Kalshi fee awareness.

Kelly formula:  f* = (p(b+1) − 1) / b
where:
  p = estimated true probability of YES
  b = decimal odds − 1  (net payout per $1 wagered)

Kalshi charges a fee on *profit* (default 7 %).  This agent adjusts the
payout to Net Expected Value *after fees* and only executes when net EV > 0.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from kalshi_alpha_suite.config import SuiteConfig
from kalshi_alpha_suite.kalshi_client import KalshiClient
from kalshi_alpha_suite.models import KellyResult, Side, Signal, TradeOrder

logger = logging.getLogger(__name__)


def kelly_fraction(p: float, b: float) -> float:
    """Pure Kelly fraction: f* = (p(b+1) - 1) / b."""
    if b <= 0:
        return 0.0
    return (p * (b + 1) - 1) / b


def net_payout_after_fees(gross_b: float, fee_rate: float) -> float:
    """
    Adjust the net payout ratio *b* for Kalshi's fee on profit.
    If you win, profit = gross_b per $1 risked, fee = fee_rate * profit.
    Net b = gross_b * (1 − fee_rate).
    """
    return gross_b * (1 - fee_rate)


class RiskExecutionAgent:
    """
    Sizes positions via Kelly and routes orders (live or paper).
    """

    def __init__(self, cfg: SuiteConfig, client: KalshiClient) -> None:
        self.cfg = cfg
        self.client = client
        self._trade_log_path = cfg.log_dir / "paper_trades.jsonl"
        cfg.log_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def size(self, signal: Signal, bankroll_usd: float) -> KellyResult:
        """
        Compute position size using the Kelly Criterion, adjusted for fees.

        Args:
            signal: trading signal with implied & estimated probs.
            bankroll_usd: current available capital.

        Returns:
            KellyResult with sizing and go/no-go decision.
        """
        if signal.side == Side.YES:
            p = signal.estimated_fair_prob
            market_price = signal.implied_prob
        else:
            p = 1 - signal.estimated_fair_prob
            market_price = 1 - signal.implied_prob

        if market_price <= 0 or market_price >= 1:
            return KellyResult(
                optimal_fraction=0,
                position_size_usd=0,
                net_ev=0,
                should_trade=False,
            )

        gross_b = (1 / market_price) - 1
        b = net_payout_after_fees(gross_b, self.cfg.kalshi_fee_rate)

        f_star = kelly_fraction(p, b)

        # Apply fractional Kelly (quarter-Kelly by default) for safety
        f_used = max(0, f_star * self.cfg.kelly_fraction)

        position_usd = min(f_used * bankroll_usd, self.cfg.max_position_usd)

        # Net EV per dollar wagered = p * b - (1 - p)
        net_ev = p * b - (1 - p)

        should_trade = (
            f_star > self.cfg.kelly_edge_min
            and net_ev > 0
            and position_usd > 0
        )

        return KellyResult(
            optimal_fraction=f_star,
            position_size_usd=round(position_usd, 2),
            net_ev=round(net_ev, 4),
            should_trade=should_trade,
        )

    # ------------------------------------------------------------------
    # Order building
    # ------------------------------------------------------------------

    def build_order(self, signal: Signal, kelly: KellyResult) -> Optional[TradeOrder]:
        """Construct a TradeOrder from a signal and Kelly result."""
        if not kelly.should_trade:
            return None

        # Convert to contracts and price
        price_cents = int(signal.implied_prob * 100)
        if signal.side == Side.NO:
            price_cents = 100 - price_cents
        price_cents = max(1, min(99, price_cents))

        contracts = max(1, int(kelly.position_size_usd * 100 / price_cents))

        return TradeOrder(
            ticker=signal.ticker,
            side=signal.side,
            contracts=contracts,
            limit_price_cents=price_cents,
            signal=signal,
            kelly=kelly,
            paper=self.cfg.paper_trading,
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, order: TradeOrder) -> TradeOrder:
        """Execute an order live or log it in paper mode."""
        if order.paper:
            return self._paper_execute(order)
        return await self._live_execute(order)

    def _paper_execute(self, order: TradeOrder) -> TradeOrder:
        """Log the trade to a JSONL file without touching real capital."""
        order.fill_price_cents = order.limit_price_cents
        record = {
            "timestamp": order.timestamp.isoformat(),
            "ticker": order.ticker,
            "side": order.side.value,
            "contracts": order.contracts,
            "limit_price_cents": order.limit_price_cents,
            "fill_price_cents": order.fill_price_cents,
            "kelly_f_star": round(order.kelly.optimal_fraction, 4),
            "position_usd": order.kelly.position_size_usd,
            "net_ev": order.kelly.net_ev,
            "source": order.signal.source.value,
            "rationale": order.signal.rationale,
            "paper": True,
        }
        with open(self._trade_log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
        logger.info(
            "PAPER TRADE  %s %s x%d @%d¢  (f*=%.3f, EV=%.4f)",
            order.ticker,
            order.side.value,
            order.contracts,
            order.limit_price_cents,
            order.kelly.optimal_fraction,
            order.kelly.net_ev,
        )
        return order

    async def _live_execute(self, order: TradeOrder) -> TradeOrder:
        """Place a real limit order on Kalshi."""
        price_kwarg = (
            {"yes_price": order.limit_price_cents}
            if order.side == Side.YES
            else {"no_price": order.limit_price_cents}
        )
        try:
            resp = await self.client.place_order(
                ticker=order.ticker,
                side=order.side.value,
                action="buy",
                order_type="limit",
                count=order.contracts,
                **price_kwarg,
            )
            order.order_id = resp.get("order", {}).get("order_id")
            logger.info("LIVE ORDER placed: %s", order.order_id)
        except Exception:
            logger.error("Order placement failed for %s", order.ticker, exc_info=True)
        return order

    # ------------------------------------------------------------------
    # High-level: evaluate signals and execute
    # ------------------------------------------------------------------

    async def process_signals(
        self,
        signals: List[Signal],
        bankroll_usd: float,
    ) -> List[TradeOrder]:
        """Size, filter, and execute a batch of signals."""
        orders: List[TradeOrder] = []
        for sig in signals:
            kelly = self.size(sig, bankroll_usd)
            order = self.build_order(sig, kelly)
            if order is None:
                logger.debug(
                    "SKIP %s: f*=%.3f, EV=%.4f, should_trade=%s",
                    sig.ticker,
                    kelly.optimal_fraction,
                    kelly.net_ev,
                    kelly.should_trade,
                )
                continue
            order = await self.execute(order)
            orders.append(order)
        logger.info("Executed %d / %d signals", len(orders), len(signals))
        return orders
