"""Crypto module for encryption and key management."""

from crypto.aes_gcm import decrypt_aes, derive_gcm_nonce, encrypt_aes
from crypto.ecc_keywrap import generate_keys, unwrap_key, wrap_key
from crypto.key_schedule import (
    DerivedKeys,
    derive_subkeys,
    derive_master_key_material,
    generate_kdf_salt,
    generate_master_key,
    master_key_from_passphrase,
)

__all__ = [
    "DerivedKeys",
    "decrypt_aes",
    "derive_gcm_nonce",
    "derive_subkeys",
    "derive_master_key_material",
    "encrypt_aes",
    "generate_keys",
    "generate_kdf_salt",
    "generate_master_key",
    "master_key_from_passphrase",
    "unwrap_key",
    "wrap_key",
]
