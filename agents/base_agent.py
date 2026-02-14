"""Base agent class for all Kalshi test agents."""

import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kalshi_client.client import KalshiClient


class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WARNING = "WARNING"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str = ""
    duration_ms: float = 0
    details: dict = field(default_factory=dict)


class BaseAgent:
    """Base class for all test agents.

    Each agent runs a series of tests against the Kalshi API
    and reports results with rich formatting.
    """

    name: str = "BaseAgent"
    description: str = "Base test agent"

    def __init__(self, client: KalshiClient):
        self.client = client
        self.console = Console()
        self.results: list[TestResult] = []

    def run_test(self, test_name: str, test_fn, *args, **kwargs) -> TestResult:
        """Execute a single test and record results."""
        start = time.time()
        try:
            result = test_fn(*args, **kwargs)
            duration = (time.time() - start) * 1000

            if isinstance(result, TestResult):
                result.duration_ms = duration
                self.results.append(result)
                return result

            test_result = TestResult(
                name=test_name,
                status=TestStatus.PASSED,
                message=str(result) if result else "OK",
                duration_ms=duration,
            )
            self.results.append(test_result)
            return test_result

        except Exception as e:
            duration = (time.time() - start) * 1000
            test_result = TestResult(
                name=test_name,
                status=TestStatus.FAILED,
                message=str(e),
                duration_ms=duration,
                details={"traceback": traceback.format_exc()},
            )
            self.results.append(test_result)
            return test_result

    def run_all(self) -> list[TestResult]:
        """Run all tests. Override in subclasses."""
        raise NotImplementedError

    def print_results(self):
        """Print a formatted summary of test results."""
        table = Table(title=f"{self.name} Results", show_lines=True)
        table.add_column("Test", style="cyan", min_width=30)
        table.add_column("Status", justify="center", min_width=10)
        table.add_column("Duration", justify="right", min_width=10)
        table.add_column("Message", min_width=30)

        status_styles = {
            TestStatus.PASSED: "[bold green]PASS[/]",
            TestStatus.FAILED: "[bold red]FAIL[/]",
            TestStatus.SKIPPED: "[bold yellow]SKIP[/]",
            TestStatus.WARNING: "[bold orange1]WARN[/]",
        }

        for r in self.results:
            table.add_row(
                r.name,
                status_styles.get(r.status, str(r.status.value)),
                f"{r.duration_ms:.0f}ms",
                r.message[:80],
            )

        self.console.print(table)

    @property
    def summary(self) -> dict:
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        warnings = sum(1 for r in self.results if r.status == TestStatus.WARNING)
        total_time = sum(r.duration_ms for r in self.results)
        return {
            "agent": self.name,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "warnings": warnings,
            "total": len(self.results),
            "total_time_ms": total_time,
        }
