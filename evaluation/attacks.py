"""Perturbation helpers for robustness/tamper-detection evaluation.

These functions are used to *simulate attacks* (ciphertext/metadata tampering,
loss, corruption) in order to confirm that authenticated encryption detects the
modification. They are not cryptanalytic tools.
"""

from __future__ import annotations

import random

import numpy as np


def flip_random_bit(data: bytes, seed: int | None = None) -> bytes:
    """Flip one random bit in a byte-string."""

    if not data:
        return data
    rng = random.Random(seed)
    index = rng.randrange(len(data))
    bit = 1 << rng.randrange(8)
    mutated = bytearray(data)
    mutated[index] ^= bit
    return bytes(mutated)


def flip_random_bits(data: bytes, n_bits: int, seed: int | None = None) -> bytes:
    """Flip ``n_bits`` distinct random bits in a byte-string."""

    if n_bits <= 0 or not data:
        return data

    total_bits = len(data) * 8
    n_bits = min(int(n_bits), total_bits)
    rng = random.Random(seed)
    bit_positions = rng.sample(range(total_bits), k=n_bits)

    mutated = bytearray(data)
    for bit_pos in bit_positions:
        byte_index = bit_pos // 8
        mask = 1 << (bit_pos % 8)
        mutated[byte_index] ^= mask
    return bytes(mutated)


def mutate_random_bytes(data: bytes, n_bytes: int, seed: int | None = None) -> bytes:
    """Replace ``n_bytes`` distinct random byte positions with random values."""

    if n_bytes <= 0 or not data:
        return data

    n_bytes = min(int(n_bytes), len(data))
    rng = random.Random(seed)
    indices = rng.sample(range(len(data)), k=n_bytes)

    mutated = bytearray(data)
    for idx in indices:
        mutated[idx] = rng.randrange(256)
    return bytes(mutated)


def shuffle_blocks(data: bytes, block_size: int = 16, swaps: int = 1, seed: int | None = None) -> bytes:
    """Swap random blocks inside a byte-string (keeps length unchanged)."""

    if not data:
        return data
    if block_size <= 0:
        raise ValueError("block_size must be > 0.")
    if swaps <= 0:
        return data

    n_blocks = len(data) // block_size
    if n_blocks < 2:
        return data

    rng = random.Random(seed)
    mutated = bytearray(data)
    for _ in range(int(swaps)):
        a, b = rng.sample(range(n_blocks), k=2)
        start_a = a * block_size
        start_b = b * block_size
        tmp = mutated[start_a : start_a + block_size]
        mutated[start_a : start_a + block_size] = mutated[start_b : start_b + block_size]
        mutated[start_b : start_b + block_size] = tmp
    return bytes(mutated)


def truncate_bytes(data: bytes, keep_ratio: float = 0.8, *, mode: str = "center") -> bytes:
    """Keep a contiguous slice of the bytes, simulating loss/cropping."""

    if not (0.0 < keep_ratio <= 1.0):
        raise ValueError("keep_ratio must be in (0, 1].")
    if not data:
        return data

    keep = max(1, int(len(data) * keep_ratio))
    if keep >= len(data):
        return data

    if mode == "head":
        start = 0
    elif mode == "tail":
        start = len(data) - keep
    elif mode == "center":
        start = (len(data) - keep) // 2
    else:
        raise ValueError("mode must be one of: 'head', 'tail', 'center'.")

    return data[start : start + keep]


def add_gaussian_noise_to_bytes(data: bytes, sigma: float = 10.0, seed: int | None = None) -> bytes:
    """Treat byte stream as uint8 and add Gaussian noise."""

    if not data:
        return data

    rng = np.random.default_rng(seed)
    arr = np.frombuffer(data, dtype=np.uint8).astype(np.float32)
    noise = rng.normal(0.0, sigma, arr.shape).astype(np.float32)
    out = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return out.tobytes()


def crop_image_center(image: np.ndarray, crop_ratio: float = 0.8) -> np.ndarray:
    """Return center crop of an image."""

    if not (0.0 < crop_ratio <= 1.0):
        raise ValueError("crop_ratio must be in (0, 1].")
    if image.ndim not in {2, 3}:
        raise ValueError("image must be 2D or 3D.")

    h, w = image.shape[:2]
    crop_h = max(1, int(h * crop_ratio))
    crop_w = max(1, int(w * crop_ratio))
    y0 = (h - crop_h) // 2
    x0 = (w - crop_w) // 2
    return image[y0 : y0 + crop_h, x0 : x0 + crop_w].copy()
