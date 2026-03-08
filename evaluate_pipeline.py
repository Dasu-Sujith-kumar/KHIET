"""Comprehensive evaluation and ablation runner for hybrid image encryption."""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover - runtime fallback
    cv2 = None

from chaso.arnold_map import arnold_map, inverse_arnold_map
from chaso.keyed_permutation import adaptive_permute, derive_chaos_seed, inverse_adaptive_permute
from crypto.aes_gcm import decrypt_aes, derive_gcm_nonce, encrypt_aes
from crypto.key_schedule import derive_master_key_material, derive_subkeys, generate_kdf_salt
from evaluation.attacks import add_gaussian_noise_to_bytes, crop_image_center, flip_random_bit
from evaluation.metrics import adjacent_correlation, key_sensitivity, mse, npcr, psnr, shannon_entropy, uaci
from pipeline.adaptive_common import image_sha256_digest, pad_to_square, unpad_from_square
from pipeline.decrypt import decrypt_array_adaptive
from pipeline.encrypt import encrypt_array_adaptive


def _load_image(image_path: str) -> np.ndarray:
    if cv2 is not None:
        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Unable to load image: {image_path}")
        return image

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        arr = np.array(rgb, dtype=np.uint8)
    # Convert RGB -> BGR to match pipeline assumptions.
    return arr[..., ::-1].copy()


def _bytes_entropy(ciphertext: bytes) -> float:
    arr = np.frombuffer(ciphertext, dtype=np.uint8)
    return shannon_entropy(arr)


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
    return adjacent_correlation(matrix, axis=1)


def _cipher_npcr_uaci(cipher_a: bytes, cipher_b: bytes) -> tuple[float, float]:
    length = min(len(cipher_a), len(cipher_b))
    if length == 0:
        return 0.0, 0.0
    a = np.frombuffer(cipher_a[:length], dtype=np.uint8).reshape(-1, 1)
    b = np.frombuffer(cipher_b[:length], dtype=np.uint8).reshape(-1, 1)
    return npcr(a, b), uaci(a, b)


def _cropped_ciphertext(ciphertext: bytes, keep_ratio: float = 0.8) -> bytes:
    if not (0.0 < keep_ratio <= 1.0):
        raise ValueError("keep_ratio must be in (0, 1].")
    if not ciphertext:
        return ciphertext
    keep = max(1, int(len(ciphertext) * keep_ratio))
    start = (len(ciphertext) - keep) // 2
    return ciphertext[start : start + keep]


def _measure_run(fn: Callable[[], dict]) -> dict:
    tracemalloc.start()
    start = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result["execution_time_ms"] = round(elapsed_ms, 6)
    result["peak_memory_kib"] = round(peak / 1024.0, 6)
    return result


def _variant_aes_only(image: np.ndarray, passphrase: str, fixed_salt: bytes, fixed_nonce_salt: bytes) -> dict:
    image_digest = image_sha256_digest(image)
    master_key = derive_master_key_material(
        salt=fixed_salt,
        image_digest=image_digest,
        passphrase=passphrase,
    )
    keys = derive_subkeys(master_key, fixed_salt)

    aad = b"ablation|aes_only"
    nonce_context = b"aes_only|" + image_digest + str(image.shape).encode("utf-8")
    nonce = derive_gcm_nonce(keys.nonce_key, fixed_nonce_salt, context=nonce_context)

    ciphertext, _ = encrypt_aes(image.tobytes(), keys.aes_key, aad=aad, nonce=nonce)
    plaintext = decrypt_aes(ciphertext, keys.aes_key, nonce=nonce, aad=aad)
    decrypted = np.frombuffer(plaintext, dtype=image.dtype).reshape(image.shape).copy()

    def decrypt_test(candidate_ciphertext: bytes) -> bool:
        try:
            payload = decrypt_aes(candidate_ciphertext, keys.aes_key, nonce=nonce, aad=aad)
            _ = np.frombuffer(payload, dtype=image.dtype).reshape(image.shape)
            return True
        except Exception:  # noqa: BLE001
            return False

    return {
        "variant": "aes_only",
        "ciphertext": ciphertext,
        "decrypted": decrypted,
        "decrypt_test": decrypt_test,
    }


def _variant_static_chaos_aes(
    image: np.ndarray,
    passphrase: str,
    fixed_salt: bytes,
    fixed_nonce_salt: bytes,
) -> dict:
    image_digest = image_sha256_digest(image)
    master_key = derive_master_key_material(
        salt=fixed_salt,
        image_digest=image_digest,
        passphrase=passphrase,
    )
    keys = derive_subkeys(master_key, fixed_salt)

    working, original_h, original_w = pad_to_square(image)
    arnold_iterations = 3
    permutation_rounds = 2
    working = arnold_map(working, iterations=arnold_iterations)

    chaos_seed = derive_chaos_seed(keys.chaos_key, fixed_salt)
    permuted = adaptive_permute(working.reshape(-1), seed=chaos_seed, rounds=permutation_rounds)

    aad = b"ablation|static_chaos_aes"
    nonce_context = (
        b"static_chaos_aes|"
        + image_digest
        + str(working.shape).encode("utf-8")
        + str(chaos_seed).encode("utf-8")
    )
    nonce = derive_gcm_nonce(keys.nonce_key, fixed_nonce_salt, context=nonce_context)
    ciphertext, _ = encrypt_aes(permuted.tobytes(), keys.aes_key, aad=aad, nonce=nonce)

    recovered_permuted_bytes = decrypt_aes(ciphertext, keys.aes_key, nonce=nonce, aad=aad)
    recovered_permuted = np.frombuffer(recovered_permuted_bytes, dtype=working.dtype)
    recovered_flat = inverse_adaptive_permute(
        recovered_permuted.reshape(-1),
        seed=chaos_seed,
        rounds=permutation_rounds,
    )
    recovered = recovered_flat.reshape(working.shape)
    recovered = inverse_arnold_map(recovered, iterations=arnold_iterations)
    decrypted = unpad_from_square(recovered, original_h, original_w).astype(np.uint8, copy=False)

    def decrypt_test(candidate_ciphertext: bytes) -> bool:
        try:
            payload = decrypt_aes(candidate_ciphertext, keys.aes_key, nonce=nonce, aad=aad)
            arr = np.frombuffer(payload, dtype=working.dtype)
            arr = inverse_adaptive_permute(arr.reshape(-1), seed=chaos_seed, rounds=permutation_rounds)
            arr = arr.reshape(working.shape)
            arr = inverse_arnold_map(arr, iterations=arnold_iterations)
            _ = unpad_from_square(arr, original_h, original_w)
            return True
        except Exception:  # noqa: BLE001
            return False

    return {
        "variant": "static_chaos_aes",
        "ciphertext": ciphertext,
        "decrypted": decrypted,
        "decrypt_test": decrypt_test,
    }


def _variant_proposed_hardened(
    image: np.ndarray,
    passphrase: str,
    fixed_salt: bytes,
    fixed_nonce_salt: bytes,
) -> dict:
    ciphertext, metadata = encrypt_array_adaptive(
        image=image,
        passphrase=passphrase,
        threat_level="balanced",
        fixed_salt=fixed_salt,
        fixed_nonce_salt=fixed_nonce_salt,
    )
    decrypted, _ = decrypt_array_adaptive(
        ciphertext=ciphertext,
        metadata=metadata,
        passphrase=passphrase,
    )

    def decrypt_test(candidate_ciphertext: bytes) -> bool:
        try:
            _arr, _meta = decrypt_array_adaptive(
                ciphertext=candidate_ciphertext,
                metadata=metadata,
                passphrase=passphrase,
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    return {
        "variant": "proposed_hardened",
        "ciphertext": ciphertext,
        "decrypted": decrypted,
        "decrypt_test": decrypt_test,
    }


def _variant_encrypt_only(
    variant: str,
    image: np.ndarray,
    passphrase: str,
    fixed_salt: bytes,
    fixed_nonce_salt: bytes,
) -> bytes:
    if variant == "aes_only":
        return _variant_aes_only(image, passphrase, fixed_salt, fixed_nonce_salt)["ciphertext"]
    if variant == "static_chaos_aes":
        return _variant_static_chaos_aes(image, passphrase, fixed_salt, fixed_nonce_salt)["ciphertext"]
    if variant == "proposed_hardened":
        return _variant_proposed_hardened(image, passphrase, fixed_salt, fixed_nonce_salt)["ciphertext"]
    raise ValueError(f"Unknown variant: {variant}")


def _build_metrics_block(
    variant_result: dict,
    image: np.ndarray,
    passphrase: str,
    fixed_salt: bytes,
    fixed_nonce_salt: bytes,
) -> dict[str, float | dict]:
    variant = str(variant_result["variant"])
    ciphertext: bytes = variant_result["ciphertext"]
    decrypted: np.ndarray = variant_result["decrypted"]
    decrypt_test: Callable[[bytes], bool] = variant_result["decrypt_test"]

    image_perturbed = image.copy()
    image_perturbed[0, 0, 0] = np.uint8((int(image_perturbed[0, 0, 0]) + 1) % 256)
    cipher_perturbed = _variant_encrypt_only(
        variant,
        image_perturbed,
        passphrase,
        fixed_salt,
        fixed_nonce_salt,
    )
    npcr_val, uaci_val = _cipher_npcr_uaci(ciphertext, cipher_perturbed)

    alt_passphrase = passphrase + "#"
    cipher_alt_key = _variant_encrypt_only(
        variant,
        image,
        alt_passphrase,
        fixed_salt,
        fixed_nonce_salt,
    )
    key_sens = key_sensitivity(ciphertext, cipher_alt_key)

    bitflip_ok = decrypt_test(flip_random_bit(ciphertext, seed=11))
    noise_ok = decrypt_test(add_gaussian_noise_to_bytes(ciphertext, sigma=8.0, seed=23))
    crop_ok = decrypt_test(_cropped_ciphertext(ciphertext, keep_ratio=0.8))

    cropped_img = crop_image_center(image, crop_ratio=0.8)

    return {
        "entropy_cipher": round(_bytes_entropy(ciphertext), 6),
        "adj_correlation_cipher": round(_bytes_adj_corr(ciphertext), 6),
        "npcr": round(npcr_val, 6),
        "uaci": round(uaci_val, 6),
        "key_sensitivity": round(key_sens, 6),
        "psnr": round(psnr(image, decrypted), 6),
        "mse": round(mse(image, decrypted), 6),
        "cipher_size_bytes": len(ciphertext),
        "cropped_input_shape": [int(x) for x in cropped_img.shape],
        "attack_resilience": {
            "bit_flip_decrypt_success": bool(bitflip_ok),
            "noise_decrypt_success": bool(noise_ok),
            "crop_decrypt_success": bool(crop_ok),
        },
    }


def run(image_path: str, passphrase: str, out_dir: str) -> dict[str, Any]:
    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    image = _load_image(image_path)

    fixed_salt = generate_kdf_salt(16)
    fixed_nonce_salt = generate_kdf_salt(16)

    variants: dict[str, Callable[[], dict]] = {
        "aes_only": lambda: _variant_aes_only(image, passphrase, fixed_salt, fixed_nonce_salt),
        "static_chaos_aes": lambda: _variant_static_chaos_aes(image, passphrase, fixed_salt, fixed_nonce_salt),
        "proposed_hardened": lambda: _variant_proposed_hardened(image, passphrase, fixed_salt, fixed_nonce_salt),
    }

    results: dict[str, Any] = {
        "input": {
            "path": str(Path(image_path).resolve()),
            "shape": [int(x) for x in image.shape],
            "dtype": str(image.dtype),
            "image_entropy": round(shannon_entropy(image), 6),
        },
        "variants": {},
        "ablation_table": [],
    }

    for name, run_fn in variants.items():
        measured = _measure_run(run_fn)
        metrics = _build_metrics_block(measured, image, passphrase, fixed_salt, fixed_nonce_salt)
        variant_record = {
            "variant": name,
            "execution_time_ms": measured["execution_time_ms"],
            "peak_memory_kib": measured["peak_memory_kib"],
            **metrics,
        }
        results["variants"][name] = variant_record
        results["ablation_table"].append(
            {
                "version": name,
                "entropy": variant_record["entropy_cipher"],
                "npcr": variant_record["npcr"],
                "uaci": variant_record["uaci"],
                "time_ms": variant_record["execution_time_ms"],
                "peak_memory_kib": variant_record["peak_memory_kib"],
            }
        )

    out_path = output_root / "evaluation_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run comprehensive security-engineering evaluation.")
    parser.add_argument("image_path", help="Input image file path.")
    parser.add_argument("--passphrase", default="change-me", help="Passphrase used for evaluation runs.")
    parser.add_argument("--out-dir", default="artifacts/eval", help="Directory to write evaluation outputs.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    results = run(args.image_path, args.passphrase, args.out_dir)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
