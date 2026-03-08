"""Keyed chaos-like permutation helpers."""

from __future__ import annotations

import hashlib

import numpy as np


def derive_chaos_seed(key: bytes, nonce: bytes = b"") -> int:
    """Derive a deterministic integer seed from key material."""

    digest = hashlib.sha256(key + nonce).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _round_seed(seed: int, round_index: int) -> int:
    return (seed + (round_index + 1) * 104_729) % (2**63 - 1)


def adaptive_permute(data: np.ndarray, seed: int, rounds: int = 1) -> np.ndarray:
    """Apply repeated keyed permutations to a flattened array."""

    if rounds < 1:
        raise ValueError("rounds must be >= 1.")

    working = np.asarray(data).reshape(-1).copy()
    size = working.size
    if size == 0:
        return working

    for round_index in range(rounds):
        rng = np.random.default_rng(_round_seed(seed, round_index))
        perm = rng.permutation(size)
        working = working[perm]
    return working


def inverse_adaptive_permute(data: np.ndarray, seed: int, rounds: int = 1) -> np.ndarray:
    """Invert ``adaptive_permute`` for the same seed and round count."""

    if rounds < 1:
        raise ValueError("rounds must be >= 1.")

    working = np.asarray(data).reshape(-1).copy()
    size = working.size
    if size == 0:
        return working

    for round_index in range(rounds - 1, -1, -1):
        rng = np.random.default_rng(_round_seed(seed, round_index))
        perm = rng.permutation(size)
        inverse = np.empty_like(perm)
        inverse[perm] = np.arange(size)
        working = working[inverse]
    return working
