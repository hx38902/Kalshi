"""Agent Orchestrator - runs all test agents and produces a unified report."""

import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kalshi_client.client import KalshiClient
from agents.auth_agent import AuthAgent
from agents.market_data_agent import MarketDataAgent
from agents.portfolio_agent import PortfolioAgent
from agents.trading_agent import TradingAgent
from agents.event_agent import EventAgent
from agents.base_agent import TestStatus


class AgentOrchestrator:
    """Orchestrates all test agents and aggregates results."""

    AGENT_CLASSES = [
        AuthAgent,
        MarketDataAgent,
        EventAgent,
        PortfolioAgent,
        TradingAgent,
    ]

    def __init__(self, client: KalshiClient):
        self.client = client
        self.console = Console()
        self.agents = [cls(client) for cls in self.AGENT_CLASSES]

    def run_all(self) -> dict:
        """Run all agents sequentially and return aggregated results."""
        self.console.print(
            Panel(
                "[bold cyan]Kalshi Omni-Nexus Test Suite[/]\n"
                f"Running {len(self.agents)} test agents...",
                title="Agent Orchestrator",
                border_style="blue",
            )
        )

        start_time = time.time()
        all_summaries = []
        total_results = []

        for agent in self.agents:
            self.console.print()
            try:
                results = agent.run_all()
                total_results.extend(results)
                all_summaries.append(agent.summary)
            except Exception as e:
                self.console.print(f"[bold red]Agent {agent.name} crashed: {e}[/]")
                all_summaries.append({
                    "agent": agent.name,
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "warnings": 0,
                    "total": 1,
                    "total_time_ms": 0,
                    "error": str(e),
                })

        total_time = time.time() - start_time
        self._print_final_report(all_summaries, total_time)

        return {
            "summaries": all_summaries,
            "total_time_s": total_time,
            "total_passed": sum(s["passed"] for s in all_summaries),
            "total_failed": sum(s["failed"] for s in all_summaries),
            "total_skipped": sum(s["skipped"] for s in all_summaries),
            "total_warnings": sum(s.get("warnings", 0) for s in all_summaries),
            "total_tests": sum(s["total"] for s in all_summaries),
        }

    def _print_final_report(self, summaries: list[dict], total_time: float):
        """Print a final summary table across all agents."""
        self.console.print()

        table = Table(title="Final Report: All Agents", show_lines=True)
        table.add_column("Agent", style="cyan", min_width=20)
        table.add_column("Passed", justify="center", style="green")
        table.add_column("Failed", justify="center", style="red")
        table.add_column("Warnings", justify="center", style="orange1")
        table.add_column("Skipped", justify="center", style="yellow")
        table.add_column("Total", justify="center")
        table.add_column("Time", justify="right")

        for s in summaries:
            table.add_row(
                s["agent"],
                str(s["passed"]),
                str(s["failed"]),
                str(s.get("warnings", 0)),
                str(s["skipped"]),
                str(s["total"]),
                f"{s['total_time_ms']:.0f}ms",
            )

        # Totals row
        total_passed = sum(s["passed"] for s in summaries)
        total_failed = sum(s["failed"] for s in summaries)
        total_warnings = sum(s.get("warnings", 0) for s in summaries)
        total_skipped = sum(s["skipped"] for s in summaries)
        total_tests = sum(s["total"] for s in summaries)
        total_time_ms = sum(s["total_time_ms"] for s in summaries)

        table.add_row(
            "[bold]TOTAL[/]",
            f"[bold green]{total_passed}[/]",
            f"[bold red]{total_failed}[/]",
            f"[bold orange1]{total_warnings}[/]",
            f"[bold yellow]{total_skipped}[/]",
            f"[bold]{total_tests}[/]",
            f"[bold]{total_time_ms:.0f}ms[/]",
        )

        self.console.print(table)

        # Final verdict
        if total_failed == 0:
            verdict = Panel(
                f"[bold green]ALL {total_passed} TESTS PASSED[/] "
                f"({total_warnings} warnings, {total_skipped} skipped)\n"
                f"Total wall time: {total_time:.1f}s",
                title="VERDICT",
                border_style="green",
            )
        else:
            verdict = Panel(
                f"[bold red]{total_failed} TESTS FAILED[/] "
                f"out of {total_tests} "
                f"({total_passed} passed, {total_warnings} warnings, {total_skipped} skipped)\n"
                f"Total wall time: {total_time:.1f}s",
                title="VERDICT",
                border_style="red",
            )
        self.console.print(verdict)
