"""Image/cipher evaluation metrics."""

from __future__ import annotations

import numpy as np


def shannon_entropy(image: np.ndarray) -> float:
    arr = np.asarray(image).reshape(-1)
    if arr.size == 0:
        return 0.0
    hist = np.bincount(arr.astype(np.uint8), minlength=256).astype(np.float64)
    probs = hist / hist.sum()
    nz = probs[probs > 0]
    return float(-(nz * np.log2(nz)).sum())


def npcr(image_a: np.ndarray, image_b: np.ndarray) -> float:
    a = np.asarray(image_a)
    b = np.asarray(image_b)
    if a.shape != b.shape:
        raise ValueError("NPCR requires arrays with identical shape.")
    return float(np.mean(a != b) * 100.0)


def uaci(image_a: np.ndarray, image_b: np.ndarray) -> float:
    a = np.asarray(image_a, dtype=np.float32)
    b = np.asarray(image_b, dtype=np.float32)
    if a.shape != b.shape:
        raise ValueError("UACI requires arrays with identical shape.")
    return float(np.mean(np.abs(a - b) / 255.0) * 100.0)


def psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=np.float32)
    cand = np.asarray(candidate, dtype=np.float32)
    if ref.shape != cand.shape:
        raise ValueError("PSNR requires arrays with identical shape.")
    mse = float(np.mean((ref - cand) ** 2))
    if mse == 0.0:
        return float("inf")
    return float(20.0 * np.log10(255.0 / np.sqrt(mse)))


def mse(reference: np.ndarray, candidate: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=np.float32)
    cand = np.asarray(candidate, dtype=np.float32)
    if ref.shape != cand.shape:
        raise ValueError("MSE requires arrays with identical shape.")
    return float(np.mean((ref - cand) ** 2))


def adjacent_correlation(image: np.ndarray, axis: int = 1) -> float:
    arr = np.asarray(image, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr.mean(axis=2)
    if axis not in {0, 1}:
        raise ValueError("axis must be 0 (vertical) or 1 (horizontal).")

    if axis == 1:
        x = arr[:, :-1].reshape(-1)
        y = arr[:, 1:].reshape(-1)
    else:
        x = arr[:-1, :].reshape(-1)
        y = arr[1:, :].reshape(-1)

    if x.size < 2:
        return 0.0
    corr = np.corrcoef(x, y)[0, 1]
    if np.isnan(corr):
        return 0.0
    return float(corr)


def key_sensitivity(cipher_a: bytes, cipher_b: bytes) -> float:
    """Bit-level Hamming distance ratio in percentage."""

    if len(cipher_a) != len(cipher_b):
        min_len = min(len(cipher_a), len(cipher_b))
        cipher_a = cipher_a[:min_len]
        cipher_b = cipher_b[:min_len]

    if not cipher_a:
        return 0.0

    a = np.frombuffer(cipher_a, dtype=np.uint8)
    b = np.frombuffer(cipher_b, dtype=np.uint8)
    xor = np.bitwise_xor(a, b)
    bits_diff = int(np.unpackbits(xor).sum())
    total_bits = xor.size * 8
    return float((bits_diff / total_bits) * 100.0)
