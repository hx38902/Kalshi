"""Market Data Test Agent - validates market listing, search, and orderbook endpoints."""

from agents.base_agent import BaseAgent, TestResult, TestStatus
from kalshi_client.models import Market, OrderBook


class MarketDataAgent(BaseAgent):
    name = "MarketDataAgent"
    description = "Tests market data: listing, details, orderbooks, and pagination"

    def run_all(self) -> list["TestResult"]:
        self.console.rule(f"[bold blue]{self.name}: {self.description}")

        self.run_test("List Markets", self._test_list_markets)
        self.run_test("Market Pagination", self._test_pagination)
        self.run_test("Filter Active Markets", self._test_active_markets)
        self.run_test("Single Market Detail", self._test_single_market)
        self.run_test("Orderbook Fetch", self._test_orderbook)
        self.run_test("Orderbook Depth", self._test_orderbook_depth)
        self.run_test("Market Data Integrity", self._test_data_integrity)
        self.run_test("Invalid Market Ticker", self._test_invalid_ticker)

        self.print_results()
        return self.results

    def _test_list_markets(self):
        markets, cursor = self.client.get_markets(limit=5)
        assert len(markets) > 0, "No markets returned"
        assert all(isinstance(m, Market) for m in markets), "Invalid market objects"
        self._cached_markets = markets
        return TestResult(
            name="List Markets",
            status=TestStatus.PASSED,
            message=f"Retrieved {len(markets)} markets, cursor: {bool(cursor)}",
        )

    def _test_pagination(self):
        markets_1, cursor_1 = self.client.get_markets(limit=3)
        if not cursor_1:
            return TestResult(
                name="Market Pagination",
                status=TestStatus.WARNING,
                message="No cursor returned - cannot test pagination",
            )
        markets_2, cursor_2 = self.client.get_markets(limit=3, cursor=cursor_1)
        tickers_1 = {m.ticker for m in markets_1}
        tickers_2 = {m.ticker for m in markets_2}
        overlap = tickers_1 & tickers_2
        assert len(overlap) == 0, f"Pagination overlap: {overlap}"
        return TestResult(
            name="Market Pagination",
            status=TestStatus.PASSED,
            message=f"Page 1: {len(markets_1)} markets, Page 2: {len(markets_2)} markets, no overlap",
        )

    def _test_active_markets(self):
        # Kalshi filter uses "open" but market objects report status as "active"
        markets, _ = self.client.get_markets(limit=10, status="open")
        self._active_markets = markets
        if not markets:
            return TestResult(
                name="Filter Active Markets",
                status=TestStatus.WARNING,
                message="No open markets found",
            )
        return TestResult(
            name="Filter Active Markets",
            status=TestStatus.PASSED,
            message=f"{len(markets)} open markets (obj status: {markets[0].status})",
        )

    def _test_single_market(self):
        markets = getattr(self, "_active_markets", None) or getattr(self, "_cached_markets", [])
        if not markets:
            return TestResult(
                name="Single Market Detail",
                status=TestStatus.SKIPPED,
                message="No markets available to test",
            )
        ticker = markets[0].ticker
        market = self.client.get_market(ticker)
        assert market.ticker == ticker, f"Ticker mismatch: {market.ticker} != {ticker}"
        assert market.title, "Market title is empty"
        return TestResult(
            name="Single Market Detail",
            status=TestStatus.PASSED,
            message=f"[{market.ticker}] {market.title[:50]}",
        )

    def _test_orderbook(self):
        markets = getattr(self, "_active_markets", None) or getattr(self, "_cached_markets", [])
        if not markets:
            return TestResult(
                name="Orderbook Fetch",
                status=TestStatus.SKIPPED,
                message="No markets available",
            )
        ticker = markets[0].ticker
        ob = self.client.get_orderbook(ticker)
        assert isinstance(ob, OrderBook), "Invalid orderbook object"
        assert ob.ticker == ticker, "Ticker mismatch"
        return TestResult(
            name="Orderbook Fetch",
            status=TestStatus.PASSED,
            message=f"[{ticker}] bids: {len(ob.yes_bids)}, asks: {len(ob.yes_asks)}",
        )

    def _test_orderbook_depth(self):
        markets = getattr(self, "_active_markets", None) or getattr(self, "_cached_markets", [])
        if not markets:
            return TestResult(
                name="Orderbook Depth",
                status=TestStatus.SKIPPED,
                message="No markets available",
            )
        ticker = markets[0].ticker
        ob = self.client.get_orderbook(ticker, depth=3)
        total_levels = len(ob.yes_bids) + len(ob.yes_asks)
        return TestResult(
            name="Orderbook Depth",
            status=TestStatus.PASSED,
            message=f"Depth=3: {total_levels} total levels returned",
        )

    def _test_data_integrity(self):
        markets = getattr(self, "_active_markets", None) or getattr(self, "_cached_markets", [])
        if not markets:
            return TestResult(
                name="Market Data Integrity",
                status=TestStatus.SKIPPED,
                message="No markets available",
            )
        issues = []
        for m in markets[:5]:
            if m.yes_bid < 0 or m.yes_bid > 1:
                issues.append(f"{m.ticker}: yes_bid={m.yes_bid}")
            if m.yes_ask < 0 or m.yes_ask > 1:
                issues.append(f"{m.ticker}: yes_ask={m.yes_ask}")
        if issues:
            return TestResult(
                name="Market Data Integrity",
                status=TestStatus.WARNING,
                message=f"Data issues: {', '.join(issues[:3])}",
            )
        return TestResult(
            name="Market Data Integrity",
            status=TestStatus.PASSED,
            message=f"All {min(5, len(markets))} markets have valid price ranges",
        )

    def _test_invalid_ticker(self):
        from kalshi_client.exceptions import KalshiAPIError
        try:
            self.client.get_market("INVALID_TICKER_XYZ_999")
            return TestResult(
                name="Invalid Market Ticker",
                status=TestStatus.WARNING,
                message="Expected error for invalid ticker but got success",
            )
        except KalshiAPIError as e:
            return TestResult(
                name="Invalid Market Ticker",
                status=TestStatus.PASSED,
                message=f"Correctly returned HTTP {e.status_code}",
            )
