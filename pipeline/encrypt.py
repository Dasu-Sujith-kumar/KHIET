"""Adaptive image encryption pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from adaptive.classifier import SensitivityClassifier
from adaptive.policy import SecurityProfile, select_security_profile
from chaso.arnold_map import arnold_map
from chaso.keyed_permutation import adaptive_permute, derive_chaos_seed
from crypto.aes_gcm import derive_gcm_nonce, encrypt_aes
from crypto.key_schedule import derive_master_key_material, derive_subkeys, generate_kdf_salt
from crypto.metadata_auth import sign_metadata
from pipeline.adaptive_common import b64_encode_bytes, image_sha256_digest, load_image, pad_to_square
from pipeline.metadata_io import write_metadata


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


def _derive_shared_secret(
    recipient_public_key_pem: bytes | None,
) -> tuple[bytes | None, str | None]:
    if recipient_public_key_pem is None:
        return None, None

    recipient_public = serialization.load_pem_public_key(recipient_public_key_pem)
    if not isinstance(recipient_public, x25519.X25519PublicKey):
        raise TypeError("recipient_public_key_pem must be an X25519 public key.")

    ephemeral_private = x25519.X25519PrivateKey.generate()
    shared_secret = ephemeral_private.exchange(recipient_public)
    ephemeral_public_pem = ephemeral_private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return shared_secret, b64_encode_bytes(ephemeral_public_pem)


def _resolve_key_exchange_mode(passphrase: str | None, shared_secret: bytes | None) -> str:
    if passphrase and shared_secret:
        return "hybrid_passphrase_x25519"
    if shared_secret:
        return "x25519_only"
    return "passphrase_only"


def _build_metadata(
    classification_label: str,
    classification_score: float,
    classification_metrics: dict[str, float],
    profile: SecurityProfile,
    threat_level: str,
    forced_profile: str | None,
    salt: bytes,
    nonce: bytes,
    nonce_salt: bytes,
    chaos_seed: int,
    image_digest: bytes,
    original_shape: tuple[int, ...],
    working_shape: tuple[int, ...],
    dtype: str,
    original_height: int,
    original_width: int,
    arnold_padding_applied: bool,
    security_context: dict[str, Any] | None,
    key_exchange: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": PIPELINE_VERSION,
        "threat_level": threat_level,
        "forced_profile": forced_profile,
        "classification": {
            "label": classification_label,
            "score": round(float(classification_score), 6),
            "metrics": classification_metrics,
        },
        "profile": {
            "name": profile.name,
            "permutation_rounds": int(profile.permutation_rounds),
            "arnold_iterations": int(profile.arnold_iterations),
            "description": profile.description,
        },
        "salt_b64": b64_encode_bytes(salt),
        "nonce_b64": b64_encode_bytes(nonce),
        "nonce_salt_b64": b64_encode_bytes(nonce_salt),
        "nonce_strategy": "hmac_sha256(nonce_key, nonce_salt || context)[:12]",
        "image_sha256_b64": b64_encode_bytes(image_digest),
        "chaos_seed": int(chaos_seed),
        "original_shape": [int(x) for x in original_shape],
        "working_shape": [int(x) for x in working_shape],
        "dtype": dtype,
        "original_height": int(original_height),
        "original_width": int(original_width),
        "arnold_padding_applied": bool(arnold_padding_applied),
        "key_domains": {
            "K1": "aes_key",
            "K2": "nonce_key",
            "K3": "chaos_key",
            "K4": "metadata_mac_key",
        },
        "key_exchange": key_exchange,
        "security_context": security_context or {},
        "threat_model": {
            "adversary_classes": list((security_context or {}).get("adversary_models", [])),
            "attack_surface": [
                "key_reuse",
                "seed_predictability",
                "metadata_tampering",
                "integrity_forgery",
                "replay",
            ],
        },
        "claims_boundary": {
            "does_not_modify_aes": True,
            "does_not_claim_custom_cipher": True,
            "maps_confidentiality_integrity_to": "AES-GCM under standard assumptions",
            "maps_key_exchange_to": "X25519 ECDH hardness (when key_exchange mode uses x25519)",
        },
    }


def encrypt_array_adaptive(
    image: np.ndarray,
    passphrase: str | None = None,
    threat_level: str = "balanced",
    forced_profile: str | None = None,
    security_context: dict[str, Any] | None = None,
    recipient_public_key_pem: bytes | None = None,
    fixed_salt: bytes | None = None,
    fixed_nonce_salt: bytes | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """
    Encrypt an in-memory image array with adaptive profile selection.

    Returns encrypted bytes and metadata dictionary.
    ``security_context`` is persisted to metadata for research traceability.
    """

    if passphrase is None and recipient_public_key_pem is None:
        raise ValueError("Provide passphrase and/or recipient_public_key_pem.")

    classifier = SensitivityClassifier()
    classification = classifier.classify(image)
    profile = select_security_profile(
        sensitivity_label=classification.label,
        threat_level=threat_level,
        forced_profile=forced_profile,
    )

    image_digest = image_sha256_digest(image)
    shared_secret, ephemeral_public_key_pem_b64 = _derive_shared_secret(recipient_public_key_pem)

    salt = fixed_salt if fixed_salt is not None else generate_kdf_salt()
    if len(salt) < 8:
        raise ValueError("salt must be at least 8 bytes.")
    master_key = derive_master_key_material(
        salt=salt,
        image_digest=image_digest,
        passphrase=passphrase,
        shared_secret=shared_secret,
    )
    subkeys = derive_subkeys(master_key, salt)

    original_shape = tuple(int(x) for x in image.shape)
    working = image.copy()
    original_height, original_width = working.shape[:2]
    arnold_padding_applied = False

    if profile.arnold_iterations > 0:
        working, original_height, original_width = pad_to_square(working)
        arnold_padding_applied = True
        working = arnold_map(working, iterations=profile.arnold_iterations)

    chaos_seed = derive_chaos_seed(subkeys.chaos_key, image_digest + salt)
    flattened = working.reshape(-1)
    permuted = adaptive_permute(
        flattened,
        seed=chaos_seed,
        rounds=profile.permutation_rounds,
    )

    aad = _aad(profile.name, threat_level, version=PIPELINE_VERSION)
    nonce_salt = fixed_nonce_salt if fixed_nonce_salt is not None else generate_kdf_salt(length=16)
    if len(nonce_salt) < 8:
        raise ValueError("nonce_salt must be at least 8 bytes.")
    nonce_context = _nonce_context(
        version=PIPELINE_VERSION,
        profile_name=profile.name,
        threat_level=threat_level,
        working_shape=tuple(int(x) for x in working.shape),
        dtype=str(working.dtype),
        chaos_seed=chaos_seed,
        image_digest=image_digest,
    )
    nonce = derive_gcm_nonce(subkeys.nonce_key, nonce_salt, context=nonce_context)
    ciphertext, nonce = encrypt_aes(permuted.tobytes(), subkeys.aes_key, aad=aad, nonce=nonce)

    key_exchange_mode = _resolve_key_exchange_mode(passphrase, shared_secret)
    key_exchange = {
        "mode": key_exchange_mode,
        "forward_secrecy": key_exchange_mode in {"x25519_only", "hybrid_passphrase_x25519"},
        "ephemeral_public_key_pem_b64": ephemeral_public_key_pem_b64,
    }

    metadata = _build_metadata(
        classification_label=classification.label,
        classification_score=classification.score,
        classification_metrics=classification.metrics,
        profile=profile,
        threat_level=threat_level,
        forced_profile=forced_profile,
        salt=salt,
        nonce=nonce,
        nonce_salt=nonce_salt,
        chaos_seed=chaos_seed,
        image_digest=image_digest,
        original_shape=original_shape,
        working_shape=tuple(int(x) for x in working.shape),
        dtype=str(working.dtype),
        original_height=original_height,
        original_width=original_width,
        arnold_padding_applied=arnold_padding_applied,
        security_context=security_context,
        key_exchange=key_exchange,
    )

    signature = sign_metadata(metadata, key=subkeys.metadata_key)
    metadata["metadata_hmac"] = signature

    return ciphertext, metadata


def encrypt_image_adaptive(
    input_image_path: str,
    encrypted_output_path: str,
    metadata_output_path: str,
    passphrase: str | None = None,
    threat_level: str = "balanced",
    forced_profile: str | None = None,
    security_context: dict[str, Any] | None = None,
    recipient_public_key_path: str | None = None,
    recipient_public_key_pem: bytes | None = None,
) -> dict[str, Any]:
    """Encrypt an image from disk and persist encrypted bytes + metadata."""

    if recipient_public_key_path and recipient_public_key_pem is not None:
        raise ValueError("Provide either recipient_public_key_path or recipient_public_key_pem, not both.")

    resolved_recipient_pem = recipient_public_key_pem
    if recipient_public_key_path:
        resolved_recipient_pem = Path(recipient_public_key_path).read_bytes()

    image = load_image(input_image_path)
    ciphertext, metadata = encrypt_array_adaptive(
        image=image,
        passphrase=passphrase,
        threat_level=threat_level,
        forced_profile=forced_profile,
        security_context=security_context,
        recipient_public_key_pem=resolved_recipient_pem,
    )

    encrypted_path = Path(encrypted_output_path)
    encrypted_path.parent.mkdir(parents=True, exist_ok=True)
    encrypted_path.write_bytes(ciphertext)

    write_metadata(metadata_output_path, metadata)
    return metadata


def encrypt_image(
    input_image_path: str,
    encrypted_output_path: str,
    passphrase: str = "change-me",
    metadata_output_path: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible wrapper over adaptive encryption."""

    if metadata_output_path is None:
        metadata_output_path = f"{encrypted_output_path}.meta.json"

    return encrypt_image_adaptive(
        input_image_path=input_image_path,
        encrypted_output_path=encrypted_output_path,
        metadata_output_path=metadata_output_path,
        passphrase=passphrase,
        threat_level="balanced",
        forced_profile=None,
    )
