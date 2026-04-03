"""Adaptive image decryption pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from chaso.arnold_map import inverse_arnold_map
from chaso.keyed_permutation import inverse_adaptive_permute
from crypto.aes_gcm import decrypt_aes, derive_gcm_nonce
from crypto.ecc_keywrap import derive_x25519_shared_secret
from crypto.key_schedule import derive_master_key_material, derive_subkeys, master_key_from_passphrase
from crypto.metadata_auth import verify_metadata
from pipeline.adaptive_common import b64_decode_bytes, b64_encode_bytes, save_image, unpad_from_square
from pipeline.metadata_io import read_metadata

PIPELINE_VERSION = "3.0"


def _aad(profile_name: str, threat_level: str, version: str = PIPELINE_VERSION) -> bytes:
    return f"hybrid|{version}|{profile_name}|{threat_level}".encode("utf-8")


def _nonce_context(
    *,
    version: str,
    profile_name: str,
    threat_level: str,
    working_shape: tuple[int, ...],
    dtype: str,
    chaos_seed: int,
    image_digest: bytes,
) -> bytes:
    payload = {
        "chaos_seed": int(chaos_seed),
        "dtype": dtype,
        "image_sha256_b64": b64_encode_bytes(image_digest),
        "profile": profile_name,
        "shape": [int(x) for x in working_shape],
        "threat_level": threat_level,
        "version": version,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _shared_secret_from_metadata(
    metadata: dict[str, Any],
    recipient_private_key_pem: bytes | None,
) -> bytes | None:
    key_exchange = metadata.get("key_exchange", {})
    mode = str(key_exchange.get("mode", "passphrase_only"))
    if mode not in {"x25519_only", "hybrid_passphrase_x25519"}:
        return None

    if recipient_private_key_pem is None:
        raise ValueError("Metadata requires X25519 decryption, but recipient_private_key_pem was not provided.")

    ephemeral_b64 = key_exchange.get("ephemeral_public_key_pem_b64")
    if not ephemeral_b64:
        raise ValueError("Missing ephemeral public key metadata for X25519 mode.")

    ephemeral_public_pem = b64_decode_bytes(str(ephemeral_b64))
    return derive_x25519_shared_secret(
        private_key_pem=recipient_private_key_pem,
        peer_public_key_pem=ephemeral_public_pem,
    )


def _verify_metadata(metadata: dict[str, Any], metadata_key: bytes) -> None:
    signature = str(metadata.get("metadata_hmac", ""))
    unsigned = dict(metadata)
    unsigned.pop("metadata_hmac", None)
    if not verify_metadata(signature, unsigned, metadata_key):
        raise ValueError("Metadata authentication failed. Credential mismatch or metadata tampering detected.")


def decrypt_array_adaptive(
    ciphertext: bytes,
    metadata: dict[str, Any],
    passphrase: str | None = None,
    recipient_private_key_pem: bytes | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Decrypt encrypted image bytes using metadata, returning image array and metadata."""

    if "image_sha256_b64" in metadata:
        image_digest = b64_decode_bytes(str(metadata["image_sha256_b64"]))
        salt = b64_decode_bytes(str(metadata["salt_b64"]))
        shared_secret = _shared_secret_from_metadata(metadata, recipient_private_key_pem)

        key_mode = str(metadata.get("key_exchange", {}).get("mode", "passphrase_only"))
        if key_mode == "passphrase_only" and passphrase is None:
            raise ValueError("passphrase is required for passphrase_only mode.")
        if key_mode == "x25519_only":
            passphrase = None

        master_key = derive_master_key_material(
            salt=salt,
            image_digest=image_digest,
            passphrase=passphrase,
            shared_secret=shared_secret,
        )
        subkeys = derive_subkeys(master_key, salt)
        _verify_metadata(metadata, subkeys.metadata_key)

        profile = metadata["profile"]
        profile_name = str(profile["name"])
        threat_level = str(metadata["threat_level"])
        version = str(metadata.get("version", PIPELINE_VERSION))
        aad = _aad(profile_name, threat_level, version=version)

        if "nonce_salt_b64" in metadata:
            nonce_salt = b64_decode_bytes(str(metadata["nonce_salt_b64"]))
            nonce_context = _nonce_context(
                version=version,
                profile_name=profile_name,
                threat_level=threat_level,
                working_shape=tuple(int(x) for x in metadata["working_shape"]),
                dtype=str(metadata["dtype"]),
                chaos_seed=int(metadata["chaos_seed"]),
                image_digest=image_digest,
            )
            nonce = derive_gcm_nonce(subkeys.nonce_key, nonce_salt, context=nonce_context)
        else:
            nonce = b64_decode_bytes(str(metadata["nonce_b64"]))
    else:
        # Backward compatibility for legacy metadata prior to image-bound derivation.
        salt = b64_decode_bytes(str(metadata["salt_b64"]))
        if passphrase is None:
            raise ValueError("passphrase is required for legacy metadata.")
        master_key = master_key_from_passphrase(passphrase=passphrase, salt=salt)
        subkeys = derive_subkeys(master_key, salt)
        _verify_metadata(metadata, subkeys.metadata_key)
        nonce = b64_decode_bytes(str(metadata["nonce_b64"]))
        profile = metadata["profile"]
        aad = _aad(
            str(profile["name"]),
            str(metadata["threat_level"]),
            version=str(metadata.get("version", PIPELINE_VERSION)),
        )

    permuted_bytes = decrypt_aes(ciphertext, subkeys.aes_key, nonce=nonce, aad=aad)

    dtype = np.dtype(str(metadata["dtype"]))
    working_shape = tuple(int(x) for x in metadata["working_shape"])
    expected_size = int(np.prod(working_shape))

    permuted = np.frombuffer(permuted_bytes, dtype=dtype)
    if permuted.size != expected_size:
        raise ValueError("Ciphertext payload size does not match metadata shape.")

    seed = int(metadata["chaos_seed"])
    rounds = int(metadata["profile"]["permutation_rounds"])

    restored_flat = inverse_adaptive_permute(permuted.reshape(-1), seed=seed, rounds=rounds)
    restored = restored_flat.reshape(working_shape)

    arnold_iterations = int(metadata["profile"]["arnold_iterations"])
    if arnold_iterations > 0:
        restored = inverse_arnold_map(restored, iterations=arnold_iterations)

    if bool(metadata.get("arnold_padding_applied", False)):
        original_height = int(metadata["original_height"])
        original_width = int(metadata["original_width"])
        restored = unpad_from_square(restored, original_height, original_width)

    restored_array = restored.astype(dtype, copy=False)
    return np.ascontiguousarray(restored_array), metadata


def decrypt_image_adaptive(
    encrypted_input_path: str,
    output_image_path: str,
    metadata_path: str,
    passphrase: str | None = None,
    recipient_private_key_path: str | None = None,
    recipient_private_key_pem: bytes | None = None,
) -> dict[str, Any]:
    """Decrypt image bytes using metadata produced by ``encrypt_image_adaptive``."""

    if recipient_private_key_path and recipient_private_key_pem is not None:
        raise ValueError("Provide either recipient_private_key_path or recipient_private_key_pem, not both.")

    resolved_private_pem = recipient_private_key_pem
    if recipient_private_key_path:
        resolved_private_pem = Path(recipient_private_key_path).read_bytes()

    metadata = read_metadata(metadata_path)
    ciphertext = Path(encrypted_input_path).read_bytes()
    restored_u8, metadata = decrypt_array_adaptive(
        ciphertext=ciphertext,
        metadata=metadata,
        passphrase=passphrase,
        recipient_private_key_pem=resolved_private_pem,
    )
    save_image(output_image_path, restored_u8)
    return metadata


def decrypt_image(
    encrypted_input_path: str,
    output_image_path: str,
    metadata_path: str,
    passphrase: str = "change-me",
) -> dict[str, Any]:
    """Backward-compatible wrapper over adaptive decryption."""

    return decrypt_image_adaptive(
        encrypted_input_path=encrypted_input_path,
        output_image_path=output_image_path,
        metadata_path=metadata_path,
        passphrase=passphrase,
    )
