"""Configuration for Kalshi Omni-Nexus."""

import os
from dotenv import load_dotenv

load_dotenv()

KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_DEMO_API_BASE = "https://demo-api.kalshi.com/trade-api/v2"

KALSHI_TRADER_ID = os.getenv("KALSHI_TRADER_ID", "")
KALSHI_PRIVATE_KEY = os.getenv("KALSHI_PRIVATE_KEY", "")

USE_DEMO = os.getenv("KALSHI_USE_DEMO", "false").lower() == "true"

API_BASE = KALSHI_DEMO_API_BASE if USE_DEMO else KALSHI_API_BASE
