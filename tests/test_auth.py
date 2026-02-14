"""Unit tests for the authentication module."""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from kalshi_client.auth import KalshiAuth
from kalshi_client.exceptions import KalshiAuthError


@pytest.fixture(scope="module")
def test_key_pem():
    """Generate a real RSA key for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()


def test_auth_init_valid_key(test_key_pem):
    auth = KalshiAuth(key_id="test-id", private_key_pem=test_key_pem)
    assert auth.key_id == "test-id"
    assert auth.verify_key_loaded()


def test_auth_init_invalid_key():
    with pytest.raises(KalshiAuthError):
        KalshiAuth(key_id="test-id", private_key_pem="not-a-valid-key")


def test_get_auth_headers(test_key_pem):
    auth = KalshiAuth(key_id="test-id", private_key_pem=test_key_pem)
    headers = auth.get_auth_headers("GET", "/trade-api/v2/exchange/status")

    assert "KALSHI-ACCESS-KEY" in headers
    assert headers["KALSHI-ACCESS-KEY"] == "test-id"
    assert "KALSHI-ACCESS-SIGNATURE" in headers
    assert "KALSHI-ACCESS-TIMESTAMP" in headers
    assert headers["Content-Type"] == "application/json"


def test_signature_is_unique_per_call(test_key_pem):
    auth = KalshiAuth(key_id="test-id", private_key_pem=test_key_pem)
    h1 = auth.get_auth_headers("GET", "/trade-api/v2/markets")
    h2 = auth.get_auth_headers("POST", "/trade-api/v2/portfolio/orders")
    assert h1["KALSHI-ACCESS-SIGNATURE"] != h2["KALSHI-ACCESS-SIGNATURE"]


def test_escaped_newlines_in_key(test_key_pem):
    """Verify keys with literal \\n are handled correctly."""
    escaped_key = test_key_pem.replace("\n", "\\n")
    auth = KalshiAuth(key_id="test-id", private_key_pem=escaped_key)
    assert auth.verify_key_loaded()
