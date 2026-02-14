"""
Main Orchestrator
==================
Coordinates all four agents in a continuous loop:

  1. Orderbook Reciprocity Agent  → liquidity-void signals
  2. News-to-Ticker NLP Agent     → headline-driven signals
  3. Arbitrageur Agent            → cross-platform arb signals
  4. Risk & Execution Agent       → sizes + executes (paper or live)

Run with:
    python -m kalshi_alpha_suite.orchestrator
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import List

from kalshi_alpha_suite.agents.arbitrage_agent import ArbitrageAgent
from kalshi_alpha_suite.agents.nlp_agent import NLPAgent
from kalshi_alpha_suite.agents.orderbook_agent import OrderbookAgent
from kalshi_alpha_suite.agents.risk_execution_agent import RiskExecutionAgent
from kalshi_alpha_suite.config import SuiteConfig, load_config
from kalshi_alpha_suite.kalshi_client import KalshiClient
from kalshi_alpha_suite.models import Signal

logger = logging.getLogger("kalshi_alpha_suite")


def _setup_logging(cfg: SuiteConfig) -> None:
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(cfg.log_dir / "suite.log"),
    ]
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


async def run_cycle(
    cfg: SuiteConfig,
    client: KalshiClient,
    ob_agent: OrderbookAgent,
    nlp_agent: NLPAgent,
    arb_agent: ArbitrageAgent,
    risk_agent: RiskExecutionAgent,
    bankroll_usd: float,
) -> None:
    """Execute one full scan-analyse-execute cycle."""
    logger.info("=== Cycle start ===")

    # 1-3: Run signal-generating agents concurrently
    ob_task = asyncio.create_task(ob_agent.scan_all_open_markets())
    nlp_task = asyncio.create_task(nlp_agent.run(client))
    arb_task = asyncio.create_task(arb_agent.scan())

    ob_signals, nlp_signals, arb_signals = await asyncio.gather(
        ob_task, nlp_task, arb_task, return_exceptions=False,
    )

    all_signals: List[Signal] = []
    if isinstance(ob_signals, list):
        all_signals.extend(ob_signals)
    if isinstance(nlp_signals, list):
        all_signals.extend(nlp_signals)
    if isinstance(arb_signals, list):
        all_signals.extend(arb_signals)

    logger.info(
        "Signals collected: orderbook=%d, nlp=%d, arb=%d, total=%d",
        len(ob_signals) if isinstance(ob_signals, list) else 0,
        len(nlp_signals) if isinstance(nlp_signals, list) else 0,
        len(arb_signals) if isinstance(arb_signals, list) else 0,
        len(all_signals),
    )

    if not all_signals:
        logger.info("No actionable signals this cycle.")
        return

    # 4: Risk & Execution
    orders = await risk_agent.process_signals(all_signals, bankroll_usd)
    logger.info(
        "=== Cycle complete: %d orders executed (%s mode) ===",
        len(orders),
        "PAPER" if cfg.paper_trading else "LIVE",
    )


async def main() -> None:
    cfg = load_config()
    _setup_logging(cfg)

    mode = "PAPER" if cfg.paper_trading else "LIVE"
    logger.info("Kalshi Alpha Suite starting in %s mode", mode)

    async with KalshiClient(cfg) as client:
        # Fetch starting bankroll (paper mode uses a fixed amount)
        if cfg.paper_trading:
            bankroll_usd = cfg.max_position_usd * 10  # simulated bankroll
            logger.info("Paper bankroll: $%.2f", bankroll_usd)
        else:
            balance_resp = await client.get_balance()
            bankroll_usd = balance_resp.get("balance", 0) / 100  # cents → dollars
            logger.info("Live bankroll: $%.2f", bankroll_usd)

        ob_agent = OrderbookAgent(cfg, client)
        nlp_agent = NLPAgent(cfg)
        arb_agent = ArbitrageAgent(cfg, client)
        risk_agent = RiskExecutionAgent(cfg, client)

        try:
            while True:
                try:
                    await run_cycle(
                        cfg, client, ob_agent, nlp_agent, arb_agent, risk_agent, bankroll_usd,
                    )
                except Exception:
                    logger.error("Cycle failed", exc_info=True)

                logger.info("Sleeping 60 s before next cycle…")
                await asyncio.sleep(60)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutting down…")
        finally:
            await nlp_agent.close()
            await arb_agent.close()


if __name__ == "__main__":
    asyncio.run(main())
