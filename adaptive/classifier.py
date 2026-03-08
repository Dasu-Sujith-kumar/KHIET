"""Sensitivity classifier used by the adaptive encryption policy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - runtime fallback
    cv2 = None


@dataclass(frozen=True)
class ClassificationResult:
    """Image sensitivity estimate."""

    label: str
    score: float
    metrics: dict[str, float]


def _entropy_u8(gray: np.ndarray) -> float:
    if cv2 is not None:
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    else:
        hist = np.bincount(gray.reshape(-1).astype(np.uint8), minlength=256).astype(np.float64)
    probs = hist / max(float(hist.sum()), 1.0)
    nz = probs[probs > 0]
    return float(-(nz * np.log2(nz)).sum())


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if cv2 is not None:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # BGR -> gray fallback without OpenCV.
    b = image[..., 0].astype(np.float32)
    g = image[..., 1].astype(np.float32)
    r = image[..., 2].astype(np.float32)
    gray = 0.114 * b + 0.587 * g + 0.299 * r
    return np.clip(gray, 0, 255).astype(np.uint8)


def _edge_density(gray: np.ndarray) -> float:
    if cv2 is not None:
        edges = cv2.Canny(gray, threshold1=100, threshold2=200)
        return float(np.mean(edges > 0))

    gx = np.diff(gray.astype(np.float32), axis=1, prepend=gray[:, :1].astype(np.float32))
    gy = np.diff(gray.astype(np.float32), axis=0, prepend=gray[:1, :].astype(np.float32))
    mag = np.sqrt(gx * gx + gy * gy)
    threshold = float(np.percentile(mag, 75.0))
    return float(np.mean(mag > threshold))


class SensitivityClassifier:
    """Heuristic image sensitivity classifier.

    The score combines entropy, edge density, and variance in order to produce
    one of three classes: ``low``, ``medium``, or ``high``.
    """

    def __init__(self) -> None:
        self.low_threshold = 0.35
        self.high_threshold = 0.62

    def classify(self, image: np.ndarray) -> ClassificationResult:
        if image is None or image.size == 0:
            raise ValueError("Input image is empty.")

        gray = _to_gray(image)

        entropy = _entropy_u8(gray)
        edge_density = _edge_density(gray)
        variance_norm = float(np.var(gray.astype(np.float32)) / (255.0 * 255.0))

        entropy_norm = min(entropy / 8.0, 1.0)
        score = float(
            np.clip(
                0.55 * entropy_norm + 0.30 * edge_density + 0.15 * variance_norm,
                0.0,
                1.0,
            )
        )

        if score < self.low_threshold:
            label = "low"
        elif score < self.high_threshold:
            label = "medium"
        else:
            label = "high"

        return ClassificationResult(
            label=label,
            score=score,
            metrics={
                "entropy": round(entropy, 6),
                "edge_density": round(edge_density, 6),
                "variance_norm": round(variance_norm, 6),
            },
        )
