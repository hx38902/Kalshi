"""Portfolio Test Agent - validates balance, positions, and fills endpoints."""

from agents.base_agent import BaseAgent, TestResult, TestStatus
from kalshi_client.models import Balance, Position, Fill
from kalshi_client.exceptions import KalshiAPIError


class PortfolioAgent(BaseAgent):
    name = "PortfolioAgent"
    description = "Tests portfolio endpoints: balance, positions, fills, and orders"

    def run_all(self) -> list["TestResult"]:
        self.console.rule(f"[bold blue]{self.name}: {self.description}")

        self.run_test("Get Balance", self._test_get_balance)
        self.run_test("Balance Data Types", self._test_balance_types)
        self.run_test("Get Positions", self._test_get_positions)
        self.run_test("Positions Pagination", self._test_positions_pagination)
        self.run_test("Get Fills", self._test_get_fills)
        self.run_test("Get Orders", self._test_get_orders)
        self.run_test("Portfolio Summary", self._test_portfolio_summary)

        self.print_results()
        return self.results

    def _test_get_balance(self):
        try:
            balance = self.client.get_balance()
        except KalshiAPIError as e:
            if e.status_code == 401:
                self._auth_failed = True
                return TestResult(
                    name="Get Balance",
                    status=TestStatus.WARNING,
                    message="Auth 401 - API key may lack portfolio permissions or needs re-auth",
                )
            raise
        assert isinstance(balance, Balance), "Invalid balance object"
        self._balance = balance
        return TestResult(
            name="Get Balance",
            status=TestStatus.PASSED,
            message=f"Balance: ${balance.balance_dollars:.2f}, Payout: {balance.payout}c",
        )

    def _test_balance_types(self):
        if getattr(self, "_auth_failed", False):
            return TestResult(name="Balance Data Types", status=TestStatus.SKIPPED,
                              message="Skipped due to auth failure")
        balance = getattr(self, "_balance", None)
        if not balance:
            balance = self.client.get_balance()
        assert isinstance(balance.balance, int), f"Balance should be int, got {type(balance.balance)}"
        assert isinstance(balance.payout, int), f"Payout should be int, got {type(balance.payout)}"
        assert balance.balance >= 0, f"Balance is negative: {balance.balance}"
        return TestResult(
            name="Balance Data Types",
            status=TestStatus.PASSED,
            message=f"balance(int)={balance.balance}, payout(int)={balance.payout}",
        )

    def _test_get_positions(self):
        if getattr(self, "_auth_failed", False):
            return TestResult(name="Get Positions", status=TestStatus.SKIPPED,
                              message="Skipped due to auth failure")
        positions, cursor = self.client.get_positions(limit=50)
        assert isinstance(positions, list), "Positions should be a list"
        self._positions = positions
        if not positions:
            return TestResult(
                name="Get Positions",
                status=TestStatus.PASSED,
                message="No open positions (empty portfolio)",
            )
        assert all(isinstance(p, Position) for p in positions), "Invalid position objects"
        return TestResult(
            name="Get Positions",
            status=TestStatus.PASSED,
            message=f"{len(positions)} positions found",
        )

    def _test_positions_pagination(self):
        if getattr(self, "_auth_failed", False):
            return TestResult(name="Positions Pagination", status=TestStatus.SKIPPED,
                              message="Skipped due to auth failure")
        positions_1, cursor_1 = self.client.get_positions(limit=2)
        if not cursor_1:
            return TestResult(
                name="Positions Pagination",
                status=TestStatus.PASSED,
                message=f"Only {len(positions_1)} positions, no pagination needed",
            )
        positions_2, _ = self.client.get_positions(limit=2, cursor=cursor_1)
        return TestResult(
            name="Positions Pagination",
            status=TestStatus.PASSED,
            message=f"Page 1: {len(positions_1)}, Page 2: {len(positions_2)}",
        )

    def _test_get_fills(self):
        if getattr(self, "_auth_failed", False):
            return TestResult(name="Get Fills", status=TestStatus.SKIPPED,
                              message="Skipped due to auth failure")
        fills, cursor = self.client.get_fills(limit=20)
        assert isinstance(fills, list), "Fills should be a list"
        self._fills = fills
        if not fills:
            return TestResult(
                name="Get Fills",
                status=TestStatus.PASSED,
                message="No fills (no trade history)",
            )
        assert all(isinstance(f, Fill) for f in fills), "Invalid fill objects"
        return TestResult(
            name="Get Fills",
            status=TestStatus.PASSED,
            message=f"{len(fills)} fills found, latest: {fills[0].ticker}",
        )

    def _test_get_orders(self):
        if getattr(self, "_auth_failed", False):
            return TestResult(name="Get Orders", status=TestStatus.SKIPPED,
                              message="Skipped due to auth failure")
        orders, cursor = self.client.get_orders(limit=20)
        assert isinstance(orders, list), "Orders should be a list"
        self._orders = orders
        return TestResult(
            name="Get Orders",
            status=TestStatus.PASSED,
            message=f"{len(orders)} orders found",
        )

    def _test_portfolio_summary(self):
        if getattr(self, "_auth_failed", False):
            return TestResult(
                name="Portfolio Summary",
                status=TestStatus.WARNING,
                message="Portfolio inaccessible - API key returned 401 on all portfolio endpoints",
            )
        balance = getattr(self, "_balance", None)
        positions = getattr(self, "_positions", [])
        fills = getattr(self, "_fills", [])
        orders = getattr(self, "_orders", [])

        if not balance:
            return TestResult(
                name="Portfolio Summary",
                status=TestStatus.SKIPPED,
                message="Balance not available",
            )

        total_exposure = sum(p.market_exposure for p in positions)
        total_pnl = sum(p.realized_pnl for p in positions)

        return TestResult(
            name="Portfolio Summary",
            status=TestStatus.PASSED,
            message=(
                f"Balance: ${balance.balance_dollars:.2f} | "
                f"Positions: {len(positions)} | "
                f"Exposure: {total_exposure}c | "
                f"PnL: {total_pnl}c | "
                f"Fills: {len(fills)} | "
                f"Orders: {len(orders)}"
            ),
        )
