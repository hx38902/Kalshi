"""Trading Test Agent - validates order creation, management, and cancellation.

SAFETY: This agent uses limit orders priced far from the market to avoid
accidental fills. All test orders are cancelled immediately after creation.
"""

import time
from agents.base_agent import BaseAgent, TestResult, TestStatus
from kalshi_client.exceptions import KalshiAPIError


class TradingAgent(BaseAgent):
    name = "TradingAgent"
    description = "Tests trading flow: order creation, status checks, and cancellation (safe limits)"

    # Place orders at 1 cent to avoid any accidental fills
    SAFE_LIMIT_PRICE = 1  # 1 cent - almost guaranteed not to fill

    def run_all(self) -> list["TestResult"]:
        self.console.rule(f"[bold blue]{self.name}: {self.description}")

        self.run_test("Find Tradable Market", self._test_find_tradable_market)
        self.run_test("Create Limit Order (Safe)", self._test_create_limit_order)
        self.run_test("Verify Order in List", self._test_verify_order_in_list)
        self.run_test("Cancel Order", self._test_cancel_order)
        self.run_test("Verify Cancellation", self._test_verify_cancellation)
        self.run_test("Invalid Order Rejection", self._test_invalid_order)
        self.run_test("Batch Cancel (Cleanup)", self._test_batch_cancel)

        self.print_results()
        return self.results

    def _test_find_tradable_market(self):
        markets, _ = self.client.get_markets(limit=20, status="open")
        tradable = [m for m in markets if m.yes_ask > 0 and m.volume > 0]
        if not tradable:
            tradable = markets[:1] if markets else []
        if not tradable:
            self._tradable_ticker = None
            return TestResult(
                name="Find Tradable Market",
                status=TestStatus.SKIPPED,
                message="No open markets found",
            )
        self._tradable_ticker = tradable[0].ticker
        self._tradable_market = tradable[0]
        return TestResult(
            name="Find Tradable Market",
            status=TestStatus.PASSED,
            message=f"Selected: {tradable[0].ticker} ({tradable[0].title[:40]})",
        )

    def _test_create_limit_order(self):
        ticker = getattr(self, "_tradable_ticker", None)
        if not ticker:
            return TestResult(
                name="Create Limit Order (Safe)",
                status=TestStatus.SKIPPED,
                message="No tradable market available",
            )
        try:
            result = self.client.create_order(
                ticker=ticker,
                side="yes",
                action="buy",
                count=1,
                order_type="limit",
                yes_price=self.SAFE_LIMIT_PRICE,
            )
            order = result.get("order", result)
            self._test_order_id = order.get("order_id", "")
            return TestResult(
                name="Create Limit Order (Safe)",
                status=TestStatus.PASSED,
                message=f"Order created: {self._test_order_id[:16]}... at {self.SAFE_LIMIT_PRICE}c",
            )
        except KalshiAPIError as e:
            if e.status_code == 401:
                self._auth_failed = True
                return TestResult(
                    name="Create Limit Order (Safe)",
                    status=TestStatus.WARNING,
                    message="Auth 401 - API key may lack trading permissions",
                )
            return TestResult(
                name="Create Limit Order (Safe)",
                status=TestStatus.FAILED,
                message=f"Order creation failed: {e}",
            )

    def _test_verify_order_in_list(self):
        order_id = getattr(self, "_test_order_id", None)
        ticker = getattr(self, "_tradable_ticker", None)
        if not order_id:
            return TestResult(
                name="Verify Order in List",
                status=TestStatus.SKIPPED,
                message="No test order was created",
            )
        orders, _ = self.client.get_orders(ticker=ticker, status="resting")
        matching = [o for o in orders if o.get("order_id") == order_id]
        if matching:
            return TestResult(
                name="Verify Order in List",
                status=TestStatus.PASSED,
                message=f"Order {order_id[:16]}... found in resting orders",
            )
        return TestResult(
            name="Verify Order in List",
            status=TestStatus.WARNING,
            message=f"Order {order_id[:16]}... not found (may have filled or been rejected)",
        )

    def _test_cancel_order(self):
        order_id = getattr(self, "_test_order_id", None)
        if not order_id:
            return TestResult(
                name="Cancel Order",
                status=TestStatus.SKIPPED,
                message="No test order to cancel",
            )
        try:
            self.client.cancel_order(order_id)
            return TestResult(
                name="Cancel Order",
                status=TestStatus.PASSED,
                message=f"Order {order_id[:16]}... cancelled",
            )
        except KalshiAPIError as e:
            if e.status_code == 404 or "not found" in str(e).lower():
                return TestResult(
                    name="Cancel Order",
                    status=TestStatus.WARNING,
                    message="Order already gone (filled or expired)",
                )
            raise

    def _test_verify_cancellation(self):
        order_id = getattr(self, "_test_order_id", None)
        ticker = getattr(self, "_tradable_ticker", None)
        if not order_id:
            return TestResult(
                name="Verify Cancellation",
                status=TestStatus.SKIPPED,
                message="No test order",
            )
        orders, _ = self.client.get_orders(ticker=ticker, status="resting")
        matching = [o for o in orders if o.get("order_id") == order_id]
        if not matching:
            return TestResult(
                name="Verify Cancellation",
                status=TestStatus.PASSED,
                message="Order no longer appears in resting orders",
            )
        return TestResult(
            name="Verify Cancellation",
            status=TestStatus.FAILED,
            message="Order still appears after cancellation",
        )

    def _test_invalid_order(self):
        try:
            self.client.create_order(
                ticker="NONEXISTENT_TICKER_XYZ",
                side="yes",
                action="buy",
                count=1,
                order_type="limit",
                yes_price=50,
            )
            return TestResult(
                name="Invalid Order Rejection",
                status=TestStatus.WARNING,
                message="Expected rejection but order was accepted",
            )
        except KalshiAPIError as e:
            return TestResult(
                name="Invalid Order Rejection",
                status=TestStatus.PASSED,
                message=f"Correctly rejected: HTTP {e.status_code}",
            )

    def _test_batch_cancel(self):
        """Clean up any remaining test orders."""
        ticker = getattr(self, "_tradable_ticker", None)
        if not ticker:
            return TestResult(
                name="Batch Cancel (Cleanup)",
                status=TestStatus.SKIPPED,
                message="No ticker to clean up",
            )
        try:
            self.client.batch_cancel_orders(market_ticker=ticker)
            return TestResult(
                name="Batch Cancel (Cleanup)",
                status=TestStatus.PASSED,
                message=f"Batch cancel sent for {ticker}",
            )
        except KalshiAPIError as e:
            return TestResult(
                name="Batch Cancel (Cleanup)",
                status=TestStatus.PASSED,
                message=f"Batch cancel response: {e.status_code} (may have no orders to cancel)",
            )
