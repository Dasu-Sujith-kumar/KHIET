"""Metadata authentication utilities."""

from __future__ import annotations

import hmac
import json
from hashlib import sha256
from typing import Any


def _canonical_metadata_bytes(metadata: dict[str, Any]) -> bytes:
    return json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_metadata(metadata: dict[str, Any], key: bytes) -> str:
    """Return HMAC-SHA256 signature (hex)."""

    payload = _canonical_metadata_bytes(metadata)
    return hmac.new(key, payload, sha256).hexdigest()


def verify_metadata(signature_hex: str, metadata: dict[str, Any], key: bytes) -> bool:
    """Verify HMAC-SHA256 signature."""

    expected = sign_metadata(metadata, key)
    return hmac.compare_digest(expected, signature_hex or "")
