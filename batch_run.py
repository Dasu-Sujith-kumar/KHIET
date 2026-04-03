"""Batch encrypt (3 modes) + evaluate attacks/metrics across all outputs.

Creates:
- 3 mode folders with `.enc` + `.meta.json` pairs (300 files for 100 images).
- an evaluation folder with per-item metrics + an aggregated HTML report.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from crypto.ecc_keywrap import derive_x25519_shared_secret, generate_keys
from evaluation.attacks import (
    add_gaussian_noise_to_bytes,
    flip_random_bit,
    mutate_random_bytes,
    shuffle_blocks,
    truncate_bytes,
)
from evaluation.json_utils import dumps_strict_json
from evaluation.metrics import adjacent_correlation, mse, npcr, psnr, shannon_entropy, uaci
from pipeline.adaptive_common import b64_decode_bytes, load_image
from pipeline.decrypt import decrypt_array_adaptive
from pipeline.encrypt import encrypt_array_adaptive, encrypt_image_adaptive
from pipeline.metadata_io import read_metadata


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _slugify(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "image"


def _list_images(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    paths = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in _IMAGE_EXTS]
    return sorted(paths, key=lambda p: str(p).lower())


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _bytes_entropy(ciphertext: bytes) -> float:
    arr = np.frombuffer(ciphertext, dtype=np.uint8)
    return float(shannon_entropy(arr))


def _bytes_adj_corr(ciphertext: bytes) -> float:
    arr = np.frombuffer(ciphertext, dtype=np.uint8)
    if arr.size < 4:
        return 0.0
    side = int(np.sqrt(arr.size))
    side = max(side, 2)
    usable = side * side
    if usable > arr.size:
        side -= 1
        usable = side * side
    matrix = arr[:usable].reshape(side, side)
    return float(adjacent_correlation(matrix, axis=1))


def _cipher_npcr_uaci_bytes(cipher_a: bytes, cipher_b: bytes) -> tuple[float, float]:
    length = min(len(cipher_a), len(cipher_b))
    if length == 0:
        return 0.0, 0.0
    a = np.frombuffer(cipher_a[:length], dtype=np.uint8).reshape(-1, 1)
    b = np.frombuffer(cipher_b[:length], dtype=np.uint8).reshape(-1, 1)
    return float(npcr(a, b)), float(uaci(a, b))


def _decrypt_test(
    *,
    metadata: dict[str, Any],
    passphrase: str | None,
    recipient_private_key_pem: bytes | None,
) -> Callable[[bytes, dict[str, Any] | None], bool]:
    def _inner(candidate_ciphertext: bytes, candidate_metadata: dict[str, Any] | None = None) -> bool:
        try:
            decrypt_array_adaptive(
                ciphertext=candidate_ciphertext,
                metadata=candidate_metadata or metadata,
                passphrase=passphrase,
                recipient_private_key_pem=recipient_private_key_pem,
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    return _inner


def _metadata_tamper_suite(
    *,
    ciphertext: bytes,
    metadata: dict[str, Any],
    decrypt_test: Callable[[bytes, dict[str, Any] | None], bool],
) -> dict[str, bool]:
    suite: dict[str, bool] = {}

    # Missing signature.
    missing_sig = dict(metadata)
    missing_sig.pop("metadata_hmac", None)
    suite["missing_metadata_hmac"] = bool(decrypt_test(ciphertext, missing_sig))

    # Threat-level tamper.
    threat = json.loads(json.dumps(metadata))
    threat["threat_level"] = "hardened" if str(metadata.get("threat_level", "")) != "hardened" else "speed"
    suite["tamper_threat_level"] = bool(decrypt_test(ciphertext, threat))

    # Profile rounds tamper.
    profile = json.loads(json.dumps(metadata))
    if isinstance(profile.get("profile"), dict) and "permutation_rounds" in profile["profile"]:
        profile["profile"]["permutation_rounds"] = int(profile["profile"]["permutation_rounds"]) + 1
    suite["tamper_profile_rounds"] = bool(decrypt_test(ciphertext, profile))

    # Nonce salt tamper (when present).
    nonce_salt = json.loads(json.dumps(metadata))
    if "nonce_salt_b64" in nonce_salt and isinstance(nonce_salt["nonce_salt_b64"], str):
        s = nonce_salt["nonce_salt_b64"]
        nonce_salt["nonce_salt_b64"] = (s[:-1] + ("A" if s[-1:] != "A" else "B")) if s else "A"
    suite["tamper_nonce_salt_b64"] = bool(decrypt_test(ciphertext, nonce_salt))

    # Extra field.
    extra = json.loads(json.dumps(metadata))
    extra["evil_extra_field"] = "1"
    suite["add_extra_field"] = bool(decrypt_test(ciphertext, extra))

    # Salt tamper.
    salt = json.loads(json.dumps(metadata))
    if "salt_b64" in salt and isinstance(salt["salt_b64"], str):
        s = salt["salt_b64"]
        salt["salt_b64"] = (s[:-1] + ("A" if s[-1:] != "A" else "B")) if s else "A"
    suite["tamper_salt_b64"] = bool(decrypt_test(ciphertext, salt))

    # Image digest tamper.
    digest = json.loads(json.dumps(metadata))
    if "image_sha256_b64" in digest and isinstance(digest["image_sha256_b64"], str):
        s = digest["image_sha256_b64"]
        digest["image_sha256_b64"] = (s[:-1] + ("A" if s[-1:] != "A" else "B")) if s else "A"
    suite["tamper_image_sha256_b64"] = bool(decrypt_test(ciphertext, digest))

    # Shape/dtype tamper.
    shape = json.loads(json.dumps(metadata))
    if "working_shape" in shape and isinstance(shape["working_shape"], list) and shape["working_shape"]:
        shape["working_shape"][0] = int(shape["working_shape"][0]) + 1
    suite["tamper_working_shape"] = bool(decrypt_test(ciphertext, shape))

    dtype = json.loads(json.dumps(metadata))
    if "dtype" in dtype and isinstance(dtype["dtype"], str):
        dtype["dtype"] = "uint16" if dtype["dtype"] != "uint16" else "uint8"
    suite["tamper_dtype"] = bool(decrypt_test(ciphertext, dtype))

    # Chaos seed tamper.
    chaos = json.loads(json.dumps(metadata))
    if "chaos_seed" in chaos:
        chaos["chaos_seed"] = int(chaos["chaos_seed"]) + 1
    suite["tamper_chaos_seed"] = bool(decrypt_test(ciphertext, chaos))

    return suite


def _attack_basic_suite(ciphertext: bytes, decrypt_test: Callable[[bytes, dict[str, Any] | None], bool]) -> dict[str, bool]:
    return {
        "bit_flip_decrypt_success": bool(decrypt_test(flip_random_bit(ciphertext, seed=11))),
        "noise_decrypt_success": bool(decrypt_test(add_gaussian_noise_to_bytes(ciphertext, sigma=8.0, seed=23))),
        "partial_ciphertext_loss_center_0_8_decrypt_success": bool(
            decrypt_test(truncate_bytes(ciphertext, keep_ratio=0.8, mode="center"))
        ),
        "partial_ciphertext_loss_head_0_9_decrypt_success": bool(
            decrypt_test(truncate_bytes(ciphertext, keep_ratio=0.9, mode="head"))
        ),
        "partial_ciphertext_loss_tail_0_9_decrypt_success": bool(
            decrypt_test(truncate_bytes(ciphertext, keep_ratio=0.9, mode="tail"))
        ),
        "byte_mutation_decrypt_success": bool(decrypt_test(mutate_random_bytes(ciphertext, n_bytes=16, seed=29))),
        "block_shuffle_decrypt_success": bool(decrypt_test(shuffle_blocks(ciphertext, block_size=16, swaps=4, seed=31))),
    }


def _encrypt_for_mode(
    *,
    image: np.ndarray,
    mode: str,
    passphrase: str,
    recipient_public_key_pem: bytes,
    threat_level: str,
    forced_profile: str | None,
    fixed_salt: bytes | None = None,
    fixed_nonce_salt: bytes | None = None,
    shared_secret_override: bytes | None = None,
) -> bytes:
    if mode == "passphrase_only":
        ciphertext, _ = encrypt_array_adaptive(
            image=image,
            passphrase=passphrase,
            threat_level=threat_level,
            forced_profile=forced_profile,
            recipient_public_key_pem=None,
            fixed_salt=fixed_salt,
            fixed_nonce_salt=fixed_nonce_salt,
            shared_secret_override=shared_secret_override,
        )
        return ciphertext
    if mode == "x25519_only":
        ciphertext, _ = encrypt_array_adaptive(
            image=image,
            passphrase=None,
            threat_level=threat_level,
            forced_profile=forced_profile,
            recipient_public_key_pem=recipient_public_key_pem if shared_secret_override is None else None,
            fixed_salt=fixed_salt,
            fixed_nonce_salt=fixed_nonce_salt,
            shared_secret_override=shared_secret_override,
        )
        return ciphertext
    if mode == "hybrid":
        ciphertext, _ = encrypt_array_adaptive(
            image=image,
            passphrase=passphrase,
            threat_level=threat_level,
            forced_profile=forced_profile,
            recipient_public_key_pem=recipient_public_key_pem if shared_secret_override is None else None,
            fixed_salt=fixed_salt,
            fixed_nonce_salt=fixed_nonce_salt,
            shared_secret_override=shared_secret_override,
        )
        return ciphertext
    raise ValueError(f"Unknown mode: {mode}")


def _shared_secret_for_metadata(metadata: dict[str, Any], recipient_private_key_pem: bytes) -> bytes | None:
    key_exchange = metadata.get("key_exchange", {}) or {}
    mode = str(key_exchange.get("mode", "passphrase_only"))
    if mode not in {"x25519_only", "hybrid_passphrase_x25519"}:
        return None

    ephemeral_b64 = key_exchange.get("ephemeral_public_key_pem_b64")
    if not ephemeral_b64:
        raise ValueError("Missing ephemeral public key metadata for X25519 mode.")

    return derive_x25519_shared_secret(
        private_key_pem=recipient_private_key_pem,
        peer_public_key_pem=b64_decode_bytes(str(ephemeral_b64)),
    )


def _encrypt_one(
    *,
    mode: str,
    input_path: Path,
    out_folder: Path,
    base_name: str,
    passphrase: str,
    recipient_public_key_path: str | None,
    threat_level: str,
) -> dict[str, Any]:
    enc_path = out_folder / f"{base_name}.enc"
    meta_path = out_folder / f"{base_name}.meta.json"

    t0 = time.perf_counter()
    encrypt_image_adaptive(
        input_image_path=str(input_path),
        encrypted_output_path=str(enc_path),
        metadata_output_path=str(meta_path),
        passphrase=passphrase if mode in {"passphrase_only", "hybrid"} else None,
        threat_level=threat_level,
        forced_profile=None,
        security_context={"batch_mode": True, "batch_mode_label": mode},
        recipient_public_key_path=recipient_public_key_path if mode in {"x25519_only", "hybrid"} else None,
    )
    encrypt_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "mode": mode,
        "image_id": base_name,
        "input_path": str(input_path),
        "enc_path": str(enc_path),
        "meta_path": str(meta_path),
        "encrypt_time_ms": round(encrypt_ms, 6),
    }


def _evaluate_one(
    *,
    record: dict[str, Any],
    passphrase: str,
    recipient_private_key_pem: bytes,
    wrong_private_key_pem: bytes,
    recipient_public_key_pem: bytes,
    threat_level: str,
    replay_other_ciphertext: bytes | None,
    replay_other_metadata: dict[str, Any] | None,
    chosen_plaintext: bool,
) -> dict[str, Any]:
    mode = str(record["mode"])
    input_path = Path(str(record["input_path"]))
    ciphertext = Path(str(record["enc_path"])).read_bytes()
    metadata = read_metadata(str(record["meta_path"]))
    image = load_image(str(input_path))

    classification = metadata.get("classification", {}) or {}
    profile = metadata.get("profile", {}) or {}

    key_mode = str((metadata.get("key_exchange", {}) or {}).get("mode", "passphrase_only"))
    needs_pass = key_mode in {"passphrase_only", "hybrid_passphrase_x25519"}
    needs_priv = key_mode in {"x25519_only", "hybrid_passphrase_x25519"}

    dec_pass = passphrase if needs_pass else None
    dec_priv = recipient_private_key_pem if needs_priv else None

    decrypt_test = _decrypt_test(metadata=metadata, passphrase=dec_pass, recipient_private_key_pem=dec_priv)

    # Untampered decrypt.
    t0 = time.perf_counter()
    decrypted, _ = decrypt_array_adaptive(
        ciphertext=ciphertext,
        metadata=metadata,
        passphrase=dec_pass,
        recipient_private_key_pem=dec_priv,
    )
    decrypt_ms = (time.perf_counter() - t0) * 1000.0

    exact_match = bool(np.array_equal(image, decrypted))

    # Credential mismatch tests.
    wrong_pass_ok = False
    wrong_priv_ok = False
    if needs_pass:
        wrong_pass_ok = bool(
            _decrypt_test(metadata=metadata, passphrase=passphrase + "#", recipient_private_key_pem=dec_priv)(ciphertext)
        )
    if needs_priv:
        wrong_priv_ok = bool(
            _decrypt_test(metadata=metadata, passphrase=dec_pass, recipient_private_key_pem=wrong_private_key_pem)(ciphertext)
        )

    attacks = _attack_basic_suite(ciphertext, decrypt_test)

    # Wrong-key attack (should fail).
    attacks["wrong_passphrase_decrypt_success"] = bool(wrong_pass_ok) if needs_pass else False
    attacks["wrong_private_key_decrypt_success"] = bool(wrong_priv_ok) if needs_priv else False

    # Replay/substitution attack (swap ciphertext/metadata with a different item).
    attacks["replay_swap_ciphertext_decrypt_success"] = (
        bool(decrypt_test(replay_other_ciphertext)) if replay_other_ciphertext is not None else False
    )
    attacks["replay_swap_metadata_decrypt_success"] = (
        bool(decrypt_test(ciphertext, replay_other_metadata)) if replay_other_metadata is not None else False
    )

    metadata_attacks = _metadata_tamper_suite(ciphertext=ciphertext, metadata=metadata, decrypt_test=decrypt_test)

    chosen_plaintext_metrics: dict[str, Any] = {}
    if chosen_plaintext:
        forced_profile = None
        profile_block = metadata.get("profile", {}) or {}
        if isinstance(profile_block, dict) and "name" in profile_block:
            forced_profile = str(profile_block["name"])

        fixed_salt = b64_decode_bytes(str(metadata["salt_b64"]))
        fixed_nonce_salt = b64_decode_bytes(str(metadata["nonce_salt_b64"]))
        shared_secret_override = _shared_secret_for_metadata(metadata, recipient_private_key_pem)

        perturbed = image.copy()
        perturbed[0, 0, 0] = np.uint8((int(perturbed[0, 0, 0]) + 1) % 256)

        t1 = time.perf_counter()
        cipher_perturbed = _encrypt_for_mode(
            image=perturbed,
            mode=mode,
            passphrase=passphrase,
            recipient_public_key_pem=recipient_public_key_pem,
            threat_level=str(metadata.get("threat_level", threat_level)),
            forced_profile=forced_profile,
            fixed_salt=fixed_salt,
            fixed_nonce_salt=fixed_nonce_salt,
            shared_secret_override=shared_secret_override,
        )
        chosen_plaintext_metrics["chosen_plaintext_encrypt_time_ms"] = round((time.perf_counter() - t1) * 1000.0, 6)
        npcr_val, uaci_val = _cipher_npcr_uaci_bytes(ciphertext, cipher_perturbed)
        chosen_plaintext_metrics["chosen_plaintext_npcr"] = round(float(npcr_val), 6)
        chosen_plaintext_metrics["chosen_plaintext_uaci"] = round(float(uaci_val), 6)

    return {
        **record,
        "classification_label": str(classification.get("label", "")),
        "classification_score": float(classification.get("score", 0.0) or 0.0),
        "classification_entropy": float((classification.get("metrics", {}) or {}).get("entropy", 0.0) or 0.0),
        "classification_edge_density": float((classification.get("metrics", {}) or {}).get("edge_density", 0.0) or 0.0),
        "classification_variance_norm": float((classification.get("metrics", {}) or {}).get("variance_norm", 0.0) or 0.0),
        "profile_name": str(profile.get("name", "")),
        "profile_permutation_rounds": int(profile.get("permutation_rounds", 0) or 0),
        "profile_arnold_iterations": int(profile.get("arnold_iterations", 0) or 0),
        "metadata_threat_level": str(metadata.get("threat_level", "")),
        "metadata_key_mode": key_mode,
        "cipher_size_bytes": int(len(ciphertext)),
        "cipher_entropy": round(_bytes_entropy(ciphertext), 6),
        "cipher_adj_corr": round(_bytes_adj_corr(ciphertext), 6),
        "decrypt_time_ms": round(decrypt_ms, 6),
        "decrypt_ok": True,
        "exact_match": exact_match,
        "psnr": float(psnr(image, decrypted)),
        "mse": float(mse(image, decrypted)),
        "wrong_passphrase_decrypt_success": bool(wrong_pass_ok),
        "wrong_private_key_decrypt_success": bool(wrong_priv_ok),
        "attack_resilience": attacks,
        "metadata_tamper_suite": metadata_attacks,
        **chosen_plaintext_metrics,
    }


def _summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    df = pd.json_normalize(items, sep="__")
    if df.empty:
        return {}

    summary: dict[str, Any] = {}
    for mode, group in df.groupby("mode", dropna=False):
        mode = str(mode)
        rec: dict[str, Any] = {
            "count": int(len(group)),
            "encrypt_time_ms_mean": float(group["encrypt_time_ms"].mean()),
            "decrypt_time_ms_mean": float(group["decrypt_time_ms"].mean()),
            "cipher_entropy_mean": float(group["cipher_entropy"].mean()),
            "cipher_adj_corr_mean": float(group["cipher_adj_corr"].abs().mean()),
            "cipher_size_bytes_mean": float(group["cipher_size_bytes"].mean()),
            "exact_match_rate": float(group["exact_match"].mean()),
            "wrong_passphrase_success_rate": float(group.get("wrong_passphrase_decrypt_success", 0).mean()),
            "wrong_private_key_success_rate": float(group.get("wrong_private_key_decrypt_success", 0).mean()),
        }

        if "chosen_plaintext_npcr" in group:
            rec["chosen_plaintext_npcr_mean"] = float(group["chosen_plaintext_npcr"].mean())
        if "chosen_plaintext_uaci" in group:
            rec["chosen_plaintext_uaci_mean"] = float(group["chosen_plaintext_uaci"].mean())
        if "chosen_plaintext_encrypt_time_ms" in group:
            rec["chosen_plaintext_encrypt_time_ms_mean"] = float(group["chosen_plaintext_encrypt_time_ms"].mean())

        # Attack success rates (lower is better).
        for col in group.columns:
            if col.startswith("attack_resilience__") or col.startswith("metadata_tamper_suite__"):
                rec[f"{col}_rate"] = float(group[col].mean())

        summary[mode] = rec

    return summary


def run(
    *,
    input_dir: str,
    out_dir: str,
    count: int,
    passphrase: str,
    seed: int,
    shuffle: bool,
    threat_level: str,
    overwrite: bool,
    report: bool,
    recipient_private_key: str | None,
    recipient_public_key: str | None,
    chosen_plaintext: bool,
) -> dict[str, Any]:
    input_root = Path(input_dir)
    output_root = Path(out_dir)

    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise ValueError(f"Output directory is not empty: {output_root} (use --overwrite to reuse it)")

    # Folder layout.
    passphrase_dir = output_root / "passphrase_only"
    x25519_dir = output_root / "x25519_only"
    hybrid_dir = output_root / "hybrid"
    eval_dir = output_root / "evaluation"
    keys_dir = output_root / "keys"
    for p in [passphrase_dir, x25519_dir, hybrid_dir, eval_dir, keys_dir]:
        _ensure_dir(p)

    # Keypair reused for x25519_only and hybrid.
    priv_path = keys_dir / "recipient_private.pem"
    pub_path = keys_dir / "recipient_public.pem"
    if (recipient_private_key is None) != (recipient_public_key is None):
        raise ValueError("Provide both --recipient-private-key and --recipient-public-key, or neither.")

    if recipient_private_key and recipient_public_key:
        priv_bytes = Path(recipient_private_key).read_bytes()
        pub_bytes = Path(recipient_public_key).read_bytes()
        priv_path.write_bytes(priv_bytes)
        pub_path.write_bytes(pub_bytes)
    elif not (priv_path.exists() and pub_path.exists()):
        generate_keys(private_key_path=str(priv_path), public_key_path=str(pub_path))

    recipient_private_key_pem = priv_path.read_bytes()
    recipient_public_key_pem = pub_path.read_bytes()

    # Wrong private key for negative tests.
    wrong_priv = keys_dir / "wrong_private.pem"
    wrong_pub = keys_dir / "wrong_public.pem"
    if not (wrong_priv.exists() and wrong_pub.exists()):
        generate_keys(private_key_path=str(wrong_priv), public_key_path=str(wrong_pub))
    wrong_private_key_pem = wrong_priv.read_bytes()

    # Select images.
    images = _list_images(input_root)
    if not images:
        raise ValueError(f"No images found under: {input_root}")

    if len(images) < int(count):
        raise ValueError(f"Requested --count {count}, but only found {len(images)} images under: {input_root}")

    if shuffle:
        rng = random.Random(int(seed))
        rng.shuffle(images)
    selected = images[: int(count)]

    print(f"Selected {len(selected)} images from {input_root}")
    print(f"Output root: {output_root}")

    items: list[dict[str, Any]] = []
    for idx, image_path in enumerate(selected, start=1):
        if idx == 1 or idx % 10 == 0 or idx == len(selected):
            print(f"[encrypt] {idx}/{len(selected)}: {image_path.name}")
        stem = _slugify(image_path.stem)[:64]
        base = f"{idx:04d}_{stem}"

        items.append(
            _encrypt_one(
                mode="passphrase_only",
                input_path=image_path,
                out_folder=passphrase_dir,
                base_name=base,
                passphrase=passphrase,
                recipient_public_key_path=None,
                threat_level=threat_level,
            )
        )
        items.append(
            _encrypt_one(
                mode="x25519_only",
                input_path=image_path,
                out_folder=x25519_dir,
                base_name=base,
                passphrase=passphrase,
                recipient_public_key_path=str(pub_path),
                threat_level=threat_level,
            )
        )
        items.append(
            _encrypt_one(
                mode="hybrid",
                input_path=image_path,
                out_folder=hybrid_dir,
                base_name=base,
                passphrase=passphrase,
                recipient_public_key_path=str(pub_path),
                threat_level=threat_level,
            )
        )

    # Preload a small set of "other" payloads per mode for replay/substitution tests.
    mode_to_indices: dict[str, list[int]] = {}
    for idx, rec in enumerate(items):
        mode_to_indices.setdefault(str(rec["mode"]), []).append(idx)

    replay_other: dict[int, tuple[bytes, dict[str, Any]]] = {}
    for mode, idxs in mode_to_indices.items():
        if len(idxs) < 2:
            continue
        a, b = idxs[0], idxs[1]
        cipher_a = Path(str(items[a]["enc_path"])).read_bytes()
        meta_a = read_metadata(str(items[a]["meta_path"]))
        cipher_b = Path(str(items[b]["enc_path"])).read_bytes()
        meta_b = read_metadata(str(items[b]["meta_path"]))
        for idx in idxs:
            replay_other[idx] = (cipher_b, meta_b) if idx == a else (cipher_a, meta_a)

    # Evaluate all pairs.
    evaluated: list[dict[str, Any]] = []
    for i, rec in enumerate(items):
        if i == 0 or (i + 1) % 50 == 0 or (i + 1) == len(items):
            print(f"[eval] {i + 1}/{len(items)}: {Path(str(rec['enc_path'])).name}")
        other = replay_other.get(i)
        evaluated.append(
            _evaluate_one(
                record=rec,
                passphrase=passphrase,
                recipient_private_key_pem=recipient_private_key_pem,
                wrong_private_key_pem=wrong_private_key_pem,
                recipient_public_key_pem=recipient_public_key_pem,
                threat_level=threat_level,
                replay_other_ciphertext=other[0] if other else None,
                replay_other_metadata=other[1] if other else None,
                chosen_plaintext=bool(chosen_plaintext),
            )
        )

    results: dict[str, Any] = {
        "config": {
            "input_dir": str(input_root.resolve()),
            "out_dir": str(output_root.resolve()),
            "count": int(count),
            "seed": int(seed),
            "threat_level": str(threat_level),
            "chosen_plaintext": bool(chosen_plaintext),
        },
        "keys": {
            "recipient_private_key_pem": str(priv_path),
            "recipient_public_key_pem": str(pub_path),
        },
        "items": evaluated,
        "summary": _summarize(evaluated),
    }

    # Persist results.
    (eval_dir / "batch_results.json").write_text(dumps_strict_json(results, indent=2), encoding="utf-8")
    df = pd.json_normalize(evaluated, sep="__")
    df.to_csv(eval_dir / "batch_results.csv", index=False)

    if report:
        try:
            from evaluation.batch_reporting import write_batch_report

            html_path = write_batch_report(results, eval_dir)
            results["report"] = {"html": str(html_path)}
        except Exception as exc:  # noqa: BLE001
            results["report_error"] = str(exc)
        (eval_dir / "batch_results.json").write_text(dumps_strict_json(results, indent=2), encoding="utf-8")

    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch encrypt 100 images in 3 modes + evaluate attacks/metrics.")
    parser.add_argument("input_dir", help="Directory containing input images.")
    parser.add_argument("--out-dir", required=True, help="Output directory (will contain 3 mode folders).")
    parser.add_argument("--count", type=int, default=100, help="Number of images to process (default: 100).")
    parser.add_argument("--passphrase", required=True, help="Passphrase used for passphrase_only + hybrid.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle input images before taking --count.")
    parser.add_argument("--seed", type=int, default=0, help="Shuffle seed (only used with --shuffle).")
    parser.add_argument(
        "--threat",
        default="balanced",
        choices=["speed", "balanced", "hardened"],
        help="Threat profile used by adaptive selector.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Allow reusing a non-empty out-dir.")
    parser.add_argument("--report", action="store_true", help="Generate aggregated HTML report under out-dir/evaluation/report/.")
    parser.add_argument(
        "--skip-chosen-plaintext",
        action="store_true",
        help="Skip chosen-plaintext (one-pixel change) re-encryption metrics to speed up batch evaluation.",
    )
    parser.add_argument("--recipient-private-key", help="Use an existing recipient X25519 private key PEM.")
    parser.add_argument("--recipient-public-key", help="Use an existing recipient X25519 public key PEM.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    results = run(
        input_dir=str(args.input_dir),
        out_dir=str(args.out_dir),
        count=int(args.count),
        passphrase=str(args.passphrase),
        seed=int(args.seed),
        shuffle=bool(args.shuffle),
        threat_level=str(args.threat),
        overwrite=bool(args.overwrite),
        report=bool(args.report),
        recipient_private_key=str(args.recipient_private_key) if args.recipient_private_key else None,
        recipient_public_key=str(args.recipient_public_key) if args.recipient_public_key else None,
        chosen_plaintext=not bool(args.skip_chosen_plaintext),
    )
    print(json.dumps({"status": "ok", "out_dir": results["config"]["out_dir"]}, indent=2))


if __name__ == "__main__":
    main()
