#!/usr/bin/env python3
"""Entry point for the Kalshi test agent suite."""

import sys
from rich.console import Console

from config import API_BASE, KALSHI_TRADER_ID, KALSHI_PRIVATE_KEY
from kalshi_client.auth import KalshiAuth
from kalshi_client.client import KalshiClient
from agents.orchestrator import AgentOrchestrator


def main():
    console = Console()

    if not KALSHI_TRADER_ID or not KALSHI_PRIVATE_KEY:
        console.print("[bold red]ERROR: KALSHI_TRADER_ID and KALSHI_PRIVATE_KEY must be set in .env[/]")
        sys.exit(1)

    console.print(f"[dim]API Base: {API_BASE}[/]")
    console.print(f"[dim]Trader ID: {KALSHI_TRADER_ID[:8]}...[/]")

    # Initialize auth and client
    auth = KalshiAuth(key_id=KALSHI_TRADER_ID, private_key_pem=KALSHI_PRIVATE_KEY)
    client = KalshiClient(base_url=API_BASE, auth=auth)

    # Run all agents
    orchestrator = AgentOrchestrator(client)
    results = orchestrator.run_all()

    # Exit with appropriate code
    sys.exit(0 if results["total_failed"] == 0 else 1)


if __name__ == "__main__":
    main()
