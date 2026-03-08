"""Arnold map transform and inverse for square images."""

from __future__ import annotations

import numpy as np


def _validate_square_image(image: np.ndarray) -> None:
    if image.ndim not in {2, 3}:
        raise ValueError("Arnold map expects a 2D grayscale or 3D color array.")
    if image.shape[0] != image.shape[1]:
        raise ValueError("Arnold map requires square images.")


def arnold_map(image: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Apply the Arnold cat map ``iterations`` times."""

    if iterations < 0:
        raise ValueError("iterations must be >= 0.")
    _validate_square_image(image)
    if iterations == 0:
        return image.copy()

    out = image.copy()
    n = out.shape[0]
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")

    for _ in range(iterations):
        nx = (x + y) % n
        ny = (x + 2 * y) % n
        transformed = np.empty_like(out)
        transformed[nx, ny] = out[x, y]
        out = transformed
    return out


def inverse_arnold_map(image: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Invert the Arnold cat map for the same number of iterations."""

    if iterations < 0:
        raise ValueError("iterations must be >= 0.")
    _validate_square_image(image)
    if iterations == 0:
        return image.copy()

    out = image.copy()
    n = out.shape[0]
    u, v = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")

    for _ in range(iterations):
        x = (2 * u - v) % n
        y = (v - u) % n
        restored = np.empty_like(out)
        restored[x, y] = out[u, v]
        out = restored
    return out
