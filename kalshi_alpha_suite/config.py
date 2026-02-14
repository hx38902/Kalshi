"""
Configuration template for the Kalshi Alpha Suite.

Copy this file or set the corresponding environment variables.
All secrets should live in a .env file (never committed) or env vars.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Kalshi API
# ---------------------------------------------------------------------------
KALSHI_BASE_URL: str = os.getenv(
    "KALSHI_BASE_URL",
    "https://api.elections.kalshi.com/trade-api/v2",
)
KALSHI_KEY_ID: str = os.getenv("KALSHI_KEY_ID", "")
# Base-64 encoded Ed25519 private key (PEM or raw seed)
KALSHI_PRIVATE_KEY_B64: str = os.getenv("KALSHI_PRIVATE_KEY_B64", "")
# Alternatively, path to a PEM file
KALSHI_PRIVATE_KEY_PATH: str = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")

# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# ---------------------------------------------------------------------------
# External data / secondary platform
# ---------------------------------------------------------------------------
POLYMARKET_API_URL: str = os.getenv(
    "POLYMARKET_API_URL",
    "https://clob.polymarket.com",
)

# ---------------------------------------------------------------------------
# Execution parameters
# ---------------------------------------------------------------------------
PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "true").lower() in ("true", "1", "yes")
KALSHI_FEE_RATE: float = float(os.getenv("KALSHI_FEE_RATE", "0.07"))  # 7 % of profit
SPREAD_THRESHOLD_CENTS: int = int(os.getenv("SPREAD_THRESHOLD_CENTS", "3"))
KELLY_EDGE_MIN: float = float(os.getenv("KELLY_EDGE_MIN", "0.05"))  # 5 %
NLP_PROB_SHIFT_MIN: float = float(os.getenv("NLP_PROB_SHIFT_MIN", "0.10"))  # 10 %
MAX_POSITION_USD: float = float(os.getenv("MAX_POSITION_USD", "500.0"))
KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.25"))  # quarter-Kelly

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR: Path = Path(os.getenv("LOG_DIR", str(Path(__file__).resolve().parent / "logs")))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


@dataclass(frozen=True)
class SuiteConfig:
    """Immutable snapshot of the full configuration."""

    kalshi_base_url: str = KALSHI_BASE_URL
    kalshi_key_id: str = KALSHI_KEY_ID
    kalshi_private_key_b64: str = KALSHI_PRIVATE_KEY_B64
    kalshi_private_key_path: str = KALSHI_PRIVATE_KEY_PATH

    openai_api_key: str = OPENAI_API_KEY
    openai_model: str = OPENAI_MODEL

    polymarket_api_url: str = POLYMARKET_API_URL

    paper_trading: bool = PAPER_TRADING
    kalshi_fee_rate: float = KALSHI_FEE_RATE
    spread_threshold_cents: int = SPREAD_THRESHOLD_CENTS
    kelly_edge_min: float = KELLY_EDGE_MIN
    nlp_prob_shift_min: float = NLP_PROB_SHIFT_MIN
    max_position_usd: float = MAX_POSITION_USD
    kelly_fraction: float = KELLY_FRACTION

    log_dir: Path = LOG_DIR
    log_level: str = LOG_LEVEL


def load_config() -> SuiteConfig:
    """Return a SuiteConfig built from the current environment."""
    return SuiteConfig()
