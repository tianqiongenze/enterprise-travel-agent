"""Module provides service components and helpers."""

import hashlib


def make_internal_signature(idempotency_key: str, shared_secret: str) -> str:
    raw = idempotency_key + "." + shared_secret
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
