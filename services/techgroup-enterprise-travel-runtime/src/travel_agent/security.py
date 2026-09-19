"""Internal service-to-service request signing (HMAC-SHA256, full digest)."""

from __future__ import annotations

import hashlib
import hmac


def make_internal_signature(idempotency_key: str, shared_secret: str, client_id: str = "") -> str:
    """HMAC over the idempotency key and calling client id.

    The client id is bound into the message so a signature captured for one
    caller cannot be replayed by another; HMAC (not a bare SHA-256 concat)
    protects the secret against extension/forgery analysis.
    """
    message = f"{idempotency_key}.{client_id}"
    return hmac.new(
        shared_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_internal_signature(idempotency_key: str, shared_secret: str, client_id: str, signature: str) -> bool:
    expected = make_internal_signature(idempotency_key, shared_secret, client_id)
    if not signature or not isinstance(signature, str):
        return False
    return hmac.compare_digest(expected, signature.strip().lower())
