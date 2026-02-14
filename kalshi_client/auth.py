"""Kalshi API authentication using RSA key signing."""

import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature
import base64

from kalshi_client.exceptions import KalshiAuthError


class KalshiAuth:
    """Handles RSA-based authentication for the Kalshi API.

    Kalshi requires each request to be signed with an RSA private key.
    The signature covers: timestamp + method + request_path
    """

    def __init__(self, key_id: str, private_key_pem: str):
        self.key_id = key_id
        try:
            # Handle keys that may have literal \\n instead of actual newlines
            cleaned_key = private_key_pem.replace("\\n", "\n").strip()
            self.private_key = serialization.load_pem_private_key(
                cleaned_key.encode(), password=None
            )
        except Exception as e:
            raise KalshiAuthError(f"Failed to load RSA private key: {e}")

    def get_auth_headers(self, method: str, path: str) -> dict:
        """Generate authentication headers for an API request.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: Request path (e.g., /trade-api/v2/exchange/status)

        Returns:
            Dict with KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP
        """
        timestamp_ms = str(int(time.time() * 1000))
        message = timestamp_ms + method.upper() + path
        signature = self._sign(message)

        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "Content-Type": "application/json",
        }

    def _sign(self, message: str) -> str:
        """Sign a message with the RSA private key using PSS padding."""
        try:
            signature_bytes = self.private_key.sign(
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return base64.b64encode(signature_bytes).decode()
        except Exception as e:
            raise KalshiAuthError(f"Failed to sign request: {e}")

    def verify_key_loaded(self) -> bool:
        """Verify the private key is properly loaded by signing a test message."""
        try:
            self._sign("test_message")
            return True
        except KalshiAuthError:
            return False
