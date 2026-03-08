"""AES-GCM helpers."""

from __future__ import annotations

import hmac
import os
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def derive_gcm_nonce(nonce_key: bytes, nonce_salt: bytes, context: bytes = b"") -> bytes:
    """Derive a deterministic 96-bit nonce from a dedicated nonce key."""

    if len(nonce_key) < 16:
        raise ValueError("nonce_key must be at least 16 bytes.")
    if len(nonce_salt) < 8:
        raise ValueError("nonce_salt must be at least 8 bytes.")
    material = hmac.new(nonce_key, nonce_salt + context, sha256).digest()
    return material[:12]


def encrypt_aes(
    plaintext: bytes,
    key: bytes,
    aad: bytes = b"",
    nonce: bytes | None = None,
) -> tuple[bytes, bytes]:
    """Encrypt data and return (ciphertext, nonce)."""

    if len(key) not in {16, 24, 32}:
        raise ValueError("AES-GCM key must be 16, 24, or 32 bytes.")
    if nonce is None:
        nonce = os.urandom(12)
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes.")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad or None)
    return ciphertext, nonce


def decrypt_aes(ciphertext: bytes, key: bytes, nonce: bytes, aad: bytes = b"") -> bytes:
    """Decrypt AES-GCM ciphertext."""

    if len(key) not in {16, 24, 32}:
        raise ValueError("AES-GCM key must be 16, 24, or 32 bytes.")
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes.")
    return AESGCM(key).decrypt(nonce, ciphertext, aad or None)
