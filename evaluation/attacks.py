"""Simple perturbation helpers for robustness checks."""

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
