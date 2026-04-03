"""X25519-based key wrapping for master key exchange."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _derive_wrap_key(shared_secret: bytes, salt: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"hybrid-x25519-wrap-v1",
    )
    return hkdf.derive(shared_secret)


def generate_keys(
    private_key_path: str | None = None,
    public_key_path: str | None = None,
) -> tuple[bytes, bytes]:
    """Generate an X25519 key pair and optionally write PEM files."""

    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    if private_key_path:
        private_path = Path(private_key_path)
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_bytes(private_pem)
    if public_key_path:
        public_path = Path(public_key_path)
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_bytes(public_pem)

    return private_pem, public_pem


def derive_x25519_shared_secret(*, private_key_pem: bytes, peer_public_key_pem: bytes) -> bytes:
    """Derive an X25519 shared secret from PEM-encoded keys."""

    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private_key, x25519.X25519PrivateKey):
        raise TypeError("private_key_pem must be an X25519 private key.")

    peer_public = serialization.load_pem_public_key(peer_public_key_pem)
    if not isinstance(peer_public, x25519.X25519PublicKey):
        raise TypeError("peer_public_key_pem must be an X25519 public key.")

    return private_key.exchange(peer_public)


def wrap_key(master_key: bytes, recipient_public_key_pem: bytes) -> dict[str, str]:
    """Wrap a symmetric key for a recipient public key."""

    recipient_public = serialization.load_pem_public_key(recipient_public_key_pem)
    if not isinstance(recipient_public, x25519.X25519PublicKey):
        raise TypeError("recipient_public_key_pem must be an X25519 public key.")

    ephemeral_private = x25519.X25519PrivateKey.generate()
    shared_secret = ephemeral_private.exchange(recipient_public)

    salt = os.urandom(16)
    nonce = os.urandom(12)
    wrap_key_material = _derive_wrap_key(shared_secret, salt)
    wrapped = AESGCM(wrap_key_material).encrypt(nonce, master_key, None)

    ephemeral_public_pem = ephemeral_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return {
        "ephemeral_public_key_pem_b64": _b64e(ephemeral_public_pem),
        "salt_b64": _b64e(salt),
        "nonce_b64": _b64e(nonce),
        "wrapped_key_b64": _b64e(wrapped),
    }


def unwrap_key(payload: dict[str, Any], recipient_private_key_pem: bytes) -> bytes:
    """Recover a wrapped symmetric key using recipient private key."""

    ephemeral_public_pem = _b64d(str(payload["ephemeral_public_key_pem_b64"]))
    salt = _b64d(str(payload["salt_b64"]))
    nonce = _b64d(str(payload["nonce_b64"]))
    wrapped = _b64d(str(payload["wrapped_key_b64"]))

    shared_secret = derive_x25519_shared_secret(
        private_key_pem=recipient_private_key_pem,
        peer_public_key_pem=ephemeral_public_pem,
    )
    wrap_key_material = _derive_wrap_key(shared_secret, salt)
    return AESGCM(wrap_key_material).decrypt(nonce, wrapped, None)
