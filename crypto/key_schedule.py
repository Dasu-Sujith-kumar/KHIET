"""Key generation and derivation for encryption subkeys."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass(frozen=True)
class DerivedKeys:
    """Subkeys used by the hybrid pipeline."""

    aes_key: bytes
    nonce_key: bytes
    chaos_key: bytes
    metadata_key: bytes


def generate_master_key(length: int = 32) -> bytes:
    if length < 16:
        raise ValueError("Master key length must be at least 16 bytes.")
    return os.urandom(length)


def generate_kdf_salt(length: int = 16) -> bytes:
    if length < 8:
        raise ValueError("KDF salt length must be at least 8 bytes.")
    return os.urandom(length)


def master_key_from_passphrase(passphrase: str, salt: bytes, iterations: int = 200_000) -> bytes:
    """Derive a 256-bit master key from a passphrase."""

    if not passphrase:
        raise ValueError("passphrase must not be empty.")
    if not salt:
        raise ValueError("salt must not be empty.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def derive_master_key_material(
    *,
    salt: bytes,
    image_digest: bytes,
    passphrase: str | None = None,
    shared_secret: bytes | None = None,
    iterations: int = 200_000,
) -> bytes:
    """
    Derive a master key from one or both of passphrase and X25519 shared secret.

    The derivation is bound to the input image digest to avoid cross-image key reuse.
    """

    if len(salt) < 8:
        raise ValueError("salt must be at least 8 bytes.")
    if len(image_digest) != 32:
        raise ValueError("image_digest must be a SHA-256 digest (32 bytes).")
    if passphrase is None and shared_secret is None:
        raise ValueError("At least one of passphrase or shared_secret must be provided.")

    chunks: list[bytes] = []
    if passphrase is not None:
        passphrase_key = master_key_from_passphrase(passphrase, salt, iterations=iterations)
        chunks.append(b"passphrase:" + passphrase_key)
    if shared_secret is not None:
        chunks.append(b"x25519:" + shared_secret)
    chunks.append(b"image_sha256:" + image_digest)

    ikm = b"|".join(chunks)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"hybrid-master-key-v4-image-bound",
    )
    return hkdf.derive(ikm)


def derive_subkeys(master_key: bytes, salt: bytes) -> DerivedKeys:
    """Derive domain-separated subkeys for independent security roles."""

    if len(master_key) < 16:
        raise ValueError("master_key must be at least 16 bytes.")
    if len(salt) < 8:
        raise ValueError("salt must be at least 8 bytes.")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=128,
        salt=salt,
        info=b"hybrid-image-subkeys-v3-domain-separated",
    )
    material = hkdf.derive(master_key)
    return DerivedKeys(
        aes_key=material[0:32],
        nonce_key=material[32:64],
        chaos_key=material[64:96],
        metadata_key=material[96:128],
    )
