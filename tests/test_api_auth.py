"""Unit tests for OIDC bearer token verification (api/auth.py)."""

from __future__ import annotations

import base64
import importlib
import json
import os
import time
import unittest
from typing import Any, Dict


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _make_jwks_and_signer():
    _cryptography = importlib.import_module("cryptography")
    primitives = importlib.import_module("cryptography.hazmat.primitives")
    rsa = importlib.import_module("cryptography.hazmat.primitives.asymmetric.rsa")
    padding = importlib.import_module("cryptography.hazmat.primitives.asymmetric.padding")
    _ = _cryptography

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-1",
                "alg": "RS256",
                "use": "sig",
                "n": _b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64url(numbers.e.to_bytes(3, "big")),
            }
        ]
    }

    def sign(header: Dict[str, Any], claims: Dict[str, Any]) -> str:
        signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(claims).encode())}"
        signature = private_key.sign(
            signing_input.encode("ascii"),
            padding.PKCS1v15(),
            primitives.hashes.SHA256(),
        )
        return f"{signing_input}.{_b64url(signature)}"

    return jwks, sign


class OidcAuthTestCase(unittest.TestCase):
    ISSUER = "https://kc.example.com/realms/travel"
    AUDIENCE = "travel-api"

    def setUp(self) -> None:
        from src.travel_agent.api.auth import verify_token

        self.verify_token = verify_token
        self.jwks, self.sign = _make_jwks_and_signer()
        self.claims = {
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
            "sub": "user-123",
            "exp": int(time.time()) + 300,
            "realm_access": {"roles": ["gold"]},
            "tenant_id": "tenant-abc",
        }

    def test_valid_token_returns_claims(self) -> None:
        token = self.sign({"alg": "RS256", "kid": "test-key-1", "typ": "JWT"}, self.claims)
        identity_claims = self.verify_token(token, self.jwks, self.ISSUER, self.AUDIENCE)
        self.assertEqual(identity_claims["sub"], "user-123")

    def test_expired_token_rejected(self) -> None:
        self.claims["exp"] = int(time.time()) - 10
        token = self.sign({"alg": "RS256", "kid": "test-key-1"}, self.claims)
        with self.assertRaises(Exception):
            self.verify_token(token, self.jwks, self.ISSUER, self.AUDIENCE)

    def test_wrong_audience_rejected(self) -> None:
        token = self.sign({"alg": "RS256", "kid": "test-key-1"}, self.claims)
        with self.assertRaises(Exception):
            self.verify_token(token, self.jwks, self.ISSUER, "other-api")

    def test_wrong_issuer_rejected(self) -> None:
        self.claims["iss"] = "https://evil.example.com/realms/travel"
        token = self.sign({"alg": "RS256", "kid": "test-key-1"}, self.claims)
        with self.assertRaises(Exception):
            self.verify_token(token, self.jwks, self.ISSUER, self.AUDIENCE)

    def test_alg_none_rejected(self) -> None:
        header = {"alg": "none", "kid": "test-key-1"}
        signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(self.claims).encode())}"
        with self.assertRaises(Exception):
            self.verify_token(f"{signing_input}.", self.jwks, self.ISSUER, self.AUDIENCE)

    def test_unsigned_garbage_rejected(self) -> None:
        with self.assertRaises(Exception):
            self.verify_token("not.a.token", self.jwks, self.ISSUER, self.AUDIENCE)

    def test_identity_mapping_prefers_strongest_tier(self) -> None:
        from src.travel_agent.api.auth import OidcAuthenticator

        identity = OidcAuthenticator.identity_from_claims(
            {"sub": "user-9", "realm_access": {"roles": ["basic", "gold"]}}
        )
        self.assertEqual(identity, {"userId": "user-9", "tenantId": "default-tenant", "membershipTier": "gold"})

    def test_auth_mode_env(self) -> None:
        from src.travel_agent.api.auth import auth_mode

        previous = os.environ.get("TRAVEL_AUTH_MODE")
        try:
            os.environ["TRAVEL_AUTH_MODE"] = "oidc"
            self.assertEqual(auth_mode(), "oidc")
            os.environ["TRAVEL_AUTH_MODE"] = "bogus"
            self.assertEqual(auth_mode(), "internal")
        finally:
            if previous is None:
                os.environ.pop("TRAVEL_AUTH_MODE", None)
            else:
                os.environ["TRAVEL_AUTH_MODE"] = previous


if __name__ == "__main__":
    unittest.main()
