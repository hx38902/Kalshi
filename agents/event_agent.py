"""Event Discovery Test Agent - validates events listing and nested market resolution."""

from agents.base_agent import BaseAgent, TestResult, TestStatus
from kalshi_client.models import Event


class EventAgent(BaseAgent):
    name = "EventAgent"
    description = "Tests event discovery: listing, details, nested markets, and filtering"

    def run_all(self) -> list["TestResult"]:
        self.console.rule(f"[bold blue]{self.name}: {self.description}")

        self.run_test("List Events", self._test_list_events)
        self.run_test("Event Pagination", self._test_event_pagination)
        self.run_test("Filter Active Events", self._test_active_events)
        self.run_test("Single Event Detail", self._test_single_event)
        self.run_test("Event with Nested Markets", self._test_nested_markets)
        self.run_test("Event Data Integrity", self._test_data_integrity)
        self.run_test("Invalid Event Ticker", self._test_invalid_event)

        self.print_results()
        return self.results

    def _test_list_events(self):
        events, cursor = self.client.get_events(limit=5)
        assert len(events) > 0, "No events returned"
        assert all(isinstance(e, Event) for e in events), "Invalid event objects"
        self._events = events
        return TestResult(
            name="List Events",
            status=TestStatus.PASSED,
            message=f"Retrieved {len(events)} events, cursor: {bool(cursor)}",
        )

    def _test_event_pagination(self):
        events_1, cursor_1 = self.client.get_events(limit=3)
        if not cursor_1:
            return TestResult(
                name="Event Pagination",
                status=TestStatus.WARNING,
                message="No cursor returned",
            )
        events_2, _ = self.client.get_events(limit=3, cursor=cursor_1)
        tickers_1 = {e.event_ticker for e in events_1}
        tickers_2 = {e.event_ticker for e in events_2}
        overlap = tickers_1 & tickers_2
        assert len(overlap) == 0, f"Pagination overlap: {overlap}"
        return TestResult(
            name="Event Pagination",
            status=TestStatus.PASSED,
            message=f"Page 1: {len(events_1)}, Page 2: {len(events_2)}, no overlap",
        )

    def _test_active_events(self):
        events, _ = self.client.get_events(limit=10, status="open")
        self._active_events = events
        return TestResult(
            name="Filter Active Events",
            status=TestStatus.PASSED,
            message=f"{len(events)} active events found",
        )

    def _test_single_event(self):
        events = getattr(self, "_active_events", None) or getattr(self, "_events", [])
        if not events:
            return TestResult(
                name="Single Event Detail",
                status=TestStatus.SKIPPED,
                message="No events available",
            )
        ticker = events[0].event_ticker
        event = self.client.get_event(ticker)
        assert event.event_ticker == ticker, f"Ticker mismatch: {event.event_ticker} != {ticker}"
        assert event.title, "Event title is empty"
        return TestResult(
            name="Single Event Detail",
            status=TestStatus.PASSED,
            message=f"[{event.event_ticker}] {event.title[:50]}",
        )

    def _test_nested_markets(self):
        events = getattr(self, "_active_events", None) or getattr(self, "_events", [])
        if not events:
            return TestResult(
                name="Event with Nested Markets",
                status=TestStatus.SKIPPED,
                message="No events available",
            )
        ticker = events[0].event_ticker
        event = self.client.get_event(ticker, with_nested_markets=True)
        market_count = len(event.markets) if event.markets else 0
        return TestResult(
            name="Event with Nested Markets",
            status=TestStatus.PASSED,
            message=f"[{ticker}] has {market_count} nested markets",
        )

    def _test_data_integrity(self):
        events = getattr(self, "_events", [])
        if not events:
            return TestResult(
                name="Event Data Integrity",
                status=TestStatus.SKIPPED,
                message="No events to check",
            )
        issues = []
        for e in events:
            if not e.event_ticker:
                issues.append("Missing event_ticker")
            if not e.title:
                issues.append(f"{e.event_ticker}: missing title")
        if issues:
            return TestResult(
                name="Event Data Integrity",
                status=TestStatus.WARNING,
                message=f"Issues: {', '.join(issues[:3])}",
            )
        return TestResult(
            name="Event Data Integrity",
            status=TestStatus.PASSED,
            message=f"All {len(events)} events have valid data",
        )

    def _test_invalid_event(self):
        from kalshi_client.exceptions import KalshiAPIError
        try:
            self.client.get_event("INVALID_EVENT_XYZ_999")
            return TestResult(
                name="Invalid Event Ticker",
                status=TestStatus.WARNING,
                message="Expected error for invalid event but got success",
            )
        except KalshiAPIError as e:
            return TestResult(
                name="Invalid Event Ticker",
                status=TestStatus.PASSED,
                message=f"Correctly returned HTTP {e.status_code}",
            )
