"""Authentication Test Agent - validates API key loading and request signing."""

from agents.base_agent import BaseAgent, TestResult, TestStatus
from kalshi_client.client import KalshiClient
from kalshi_client.exceptions import KalshiAuthError, KalshiAPIError


class AuthAgent(BaseAgent):
    name = "AuthAgent"
    description = "Tests authentication: key loading, signing, and authenticated requests"

    def run_all(self) -> list["TestResult"]:
        self.console.rule(f"[bold blue]{self.name}: {self.description}")

        self.run_test("Key Loaded", self._test_key_loaded)
        self.run_test("Signature Generation", self._test_signature_generation)
        self.run_test("Authenticated GET Request", self._test_authenticated_get)
        self.run_test("Exchange Status (Auth Check)", self._test_exchange_status)
        self.run_test("Balance Endpoint (Auth Check)", self._test_balance_auth)

        self.print_results()
        return self.results

    def _test_key_loaded(self):
        ok = self.client.auth.verify_key_loaded()
        if not ok:
            return TestResult(
                name="Key Loaded",
                status=TestStatus.FAILED,
                message="RSA private key failed verification",
            )
        return TestResult(
            name="Key Loaded",
            status=TestStatus.PASSED,
            message="RSA private key loaded and verified",
        )

    def _test_signature_generation(self):
        headers = self.client.auth.get_auth_headers("GET", "/trade-api/v2/exchange/status")
        assert "KALSHI-ACCESS-KEY" in headers, "Missing access key header"
        assert "KALSHI-ACCESS-SIGNATURE" in headers, "Missing signature header"
        assert "KALSHI-ACCESS-TIMESTAMP" in headers, "Missing timestamp header"
        assert len(headers["KALSHI-ACCESS-SIGNATURE"]) > 50, "Signature too short"
        return TestResult(
            name="Signature Generation",
            status=TestStatus.PASSED,
            message=f"Signature generated ({len(headers['KALSHI-ACCESS-SIGNATURE'])} chars)",
        )

    def _test_authenticated_get(self):
        data = self.client._request("GET", "/exchange/status")
        return TestResult(
            name="Authenticated GET Request",
            status=TestStatus.PASSED,
            message=f"Response keys: {list(data.keys())}",
        )

    def _test_exchange_status(self):
        status = self.client.get_exchange_status()
        return TestResult(
            name="Exchange Status (Auth Check)",
            status=TestStatus.PASSED,
            message=f"Exchange active: {status.exchange_active}, Trading active: {status.trading_active}",
        )

    def _test_balance_auth(self):
        """Test that we can access a protected endpoint (balance)."""
        try:
            balance = self.client.get_balance()
            return TestResult(
                name="Balance Endpoint (Auth Check)",
                status=TestStatus.PASSED,
                message=f"Balance: ${balance.balance_dollars:.2f}",
            )
        except KalshiAPIError as e:
            if e.status_code == 401:
                return TestResult(
                    name="Balance Endpoint (Auth Check)",
                    status=TestStatus.WARNING,
                    message="Auth 401 on protected endpoint - key may lack portfolio scope",
                )
            raise
