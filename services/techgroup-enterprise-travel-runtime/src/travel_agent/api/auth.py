"""OIDC (Keycloak) token verification for the Runtime API.

Auth modes (``TRAVEL_AUTH_MODE``):
- ``oidc``: validate ``Authorization: Bearer <jwt>`` against the Keycloak
  realm's JWKS (RS256), plus ``iss``/``aud``/``exp`` claims. Recommended for
  dev/staging/prod; required by the go-live gate outside local dev.
- ``internal``: gateway-to-runtime HMAC signatures only (service trust), kept
  for local development and backwards compatibility.
- ``none``: explicit unauthenticated mode; never allowed by go-live gates.

The verification core (:func:`verify_token`) is pure so tests can sign tokens
with a locally generated RSA key and pass the JWKS document directly.
"""

from __future__ import annotations

import base64
import importlib
import json
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("travel_agent.api.auth")


class AuthError(ValueError):
    """Raised when a request fails authentication."""


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _parse_unverified(token: str) -> Tuple[Dict[str, Any], Dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed bearer token")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        claims = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    except (ValueError, TypeError) as error:
        raise AuthError(f"malformed bearer token: {error}") from error
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise AuthError("malformed bearer token payload")
    return header, claims, signing_input, signature


def verify_token(
    token: str,
    jwks: Dict[str, Any],
    issuer: str,
    audience: str,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Verify a JWS token against a JWKS document and return its claims."""
    header, claims, signing_input, signature = _parse_unverified(token)
    if header.get("alg") != "RS256":
        raise AuthError(f"unsupported token alg: {header.get('alg')!r}")
    if str(claims.get("iss", "")) != issuer:
        raise AuthError("token issuer mismatch")
    expected_aud = claims.get("aud")
    audiences = expected_aud if isinstance(expected_aud, list) else [expected_aud]
    if audience not in audiences:
        raise AuthError("token audience mismatch")
    current = time.time() if now is None else now
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or float(exp) <= current:
        raise AuthError("token expired")
    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and float(nbf) > current + 5:
        raise AuthError("token not yet valid")

    kid = header.get("kid")
    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    candidates = [key for key in keys if isinstance(key, dict) and key.get("kty") == "RSA"]
    if kid:
        candidates = [key for key in candidates if key.get("kid") == kid] or candidates
    if not candidates:
        raise AuthError("no matching signing key in JWKS")

    cryptography = importlib.import_module("cryptography")
    hashes = importlib.import_module("cryptography.hazmat.primitives.hashes")
    asymmetric = importlib.import_module("cryptography.hazmat.primitives.asymmetric.rsa")
    padding = importlib.import_module("cryptography.hazmat.primitives.asymmetric.padding")

    last_error: Optional[Exception] = None
    for jwk in candidates:
        try:
            numbers = {
                "n": int.from_bytes(_b64url_decode(jwk["n"]), "big"),
                "e": int.from_bytes(_b64url_decode(jwk["e"]), "big"),
            }
            public_key = asymmetric.RSAPublicNumbers(
                numbers["e"], numbers["n"]
            ).public_key()
            public_key.verify(
                signature,
                signing_input,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return claims
        except Exception as error:  # noqa: BLE001 - try next key
            last_error = error
            _ = cryptography
    raise AuthError(f"token signature verification failed: {last_error}")


class OidcAuthenticator:
    """Fetches and caches the realm JWKS; verifies bearer tokens."""

    def __init__(self, issuer: str, audience: str, jwks_fetcher=None) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self._jwks: Optional[Dict[str, Any]] = None
        self._jwks_fetched_at = 0.0
        self._fetcher = jwks_fetcher or self._http_fetch_jwks
        self._cache_ttl = float(os.getenv("TRAVEL_OIDC_JWKS_CACHE_SEC", "300"))

    def _jwks_url(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"

    def _http_fetch_jwks(self, url: str) -> Dict[str, Any]:
        import requests

        response = requests.get(url, timeout=float(os.getenv("TRAVEL_OIDC_TIMEOUT_SEC", "3.0")))
        if response.status_code != 200:
            raise AuthError(f"jwks fetch failed: {response.status_code}")
        return response.json()

    def _get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        current = time.time()
        if (
            force_refresh
            or self._jwks is None
            or current - self._jwks_fetched_at > self._cache_ttl
        ):
            self._jwks = self._fetcher(self._jwks_url())
            self._jwks_fetched_at = current
        return self._jwks or {"keys": []}

    def authenticate(self, authorization_header: str) -> Dict[str, Any]:
        if not authorization_header or not authorization_header.lower().startswith("bearer "):
            raise AuthError("missing bearer token")
        token = authorization_header.split(" ", 1)[1].strip()
        try:
            return verify_token(token, self._get_jwks(), self.issuer, self.audience)
        except AuthError as unknown_kid_error:
            if "signing key" in str(unknown_kid_error) or "signature" in str(unknown_kid_error):
                # Key rotation: refresh once before failing the request.
                return verify_token(
                    token, self._get_jwks(force_refresh=True), self.issuer, self.audience
                )
            raise

    @staticmethod
    def identity_from_claims(claims: Dict[str, Any]) -> Dict[str, str]:
        user_id = str(claims.get("sub", "")).strip()
        tenant_id = str(
            claims.get("tenant_id") or claims.get("tenantId") or "default-tenant"
        ).strip()
        realm_access = claims.get("realm_access") or {}
        roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else []
        tier = "basic"
        for role in ("platinum", "gold", "silver"):
            if role in roles or role in str(claims.get("membershipTier", "")).lower():
                tier = role
                break
        if not user_id:
            raise AuthError("token missing sub claim")
        return {"userId": user_id, "tenantId": tenant_id, "membershipTier": tier}


def build_authenticator_from_env() -> Optional[OidcAuthenticator]:
    issuer = os.getenv("TRAVEL_OIDC_ISSUER", "").strip()
    if not issuer:
        return None
    audience = os.getenv("TRAVEL_OIDC_AUDIENCE", "travel-api").strip()
    return OidcAuthenticator(issuer, audience)


def auth_mode() -> str:
    mode = os.getenv("TRAVEL_AUTH_MODE", "internal").strip().lower()
    return mode if mode in {"oidc", "internal", "none"} else "internal"


def jwks_well_known_url(issuer: str) -> str:
    return urllib.parse.urljoin(issuer.rstrip("/") + "/", ".well-known/openid-configuration")
