"""Sensitivity classifier used by the adaptive encryption policy."""

from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover - runtime fallback
    cv2 = None


_DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "adaptive_rf_report" / "adaptive_random_forest_cap200.pkl"
_CLASS_TO_RISK = {
    "faces": "high",
    "forms": "high",
    "medical": "high",
    "manga": "medium",
    "land-scapes and others": "low",
}
_RISK_TO_WEIGHT = {"low": 0.0, "medium": 0.5, "high": 1.0}
_MODEL_CACHE: dict[str, Any] = {}


@dataclass(frozen=True)
class ClassificationResult:
    """Image sensitivity estimate."""

    label: str
    score: float
    metrics: dict[str, Any]


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
        gray = image
    elif cv2 is not None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
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


def _resize_gray(gray: np.ndarray, size: int) -> np.ndarray:
    if cv2 is not None:
        return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    pil = Image.fromarray(gray, mode="L")
    resized = pil.resize((size, size), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.uint8)


def _extract_stats(gray: np.ndarray) -> dict[str, float]:
    h, w = gray.shape[:2]
    return {
        "entropy": float(_entropy_u8(gray)),
        "edge_density": float(_edge_density(gray)),
        "variance_norm": float(np.var(gray.astype(np.float32)) / (255.0 * 255.0)),
        "mean_intensity": float(np.mean(gray) / 255.0),
        "std_intensity": float(np.std(gray) / 255.0),
        "aspect_ratio": float(w / max(h, 1)),
        "dark_fraction": float(np.mean(gray < 32)),
        "bright_fraction": float(np.mean(gray > 223)),
    }


def _extract_ml_features(gray: np.ndarray, *, pixel_size: int) -> np.ndarray:
    stats = _extract_stats(gray)
    small = _resize_gray(gray, pixel_size).astype(np.float32) / 255.0
    pixel_features = small.reshape(-1).astype(np.float32)
    stats_arr = np.array(
        [
            stats["entropy"] / 8.0,
            stats["edge_density"],
            stats["variance_norm"],
            stats["mean_intensity"],
            stats["std_intensity"],
            stats["aspect_ratio"],
            stats["dark_fraction"],
            stats["bright_fraction"],
        ],
        dtype=np.float32,
    )
    return np.concatenate([stats_arr, pixel_features], axis=0)


def _risk_probabilities_from_classes(class_names: list[str], probabilities: np.ndarray) -> dict[str, float]:
    risk_probs = {"low": 0.0, "medium": 0.0, "high": 0.0}
    for class_name, prob in zip(class_names, probabilities.tolist()):
        risk_label = _CLASS_TO_RISK.get(str(class_name), "medium")
        risk_probs[risk_label] += float(prob)
    return risk_probs


def _load_model_bundle(model_path: Path | None) -> Any | None:
    if model_path is None:
        return None
    key = str(model_path.resolve()) if model_path.exists() else str(model_path)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    if not model_path.exists():
        _MODEL_CACHE[key] = None
        return None
    try:
        with model_path.open("rb") as handle:
            bundle = pickle.load(handle)
    except Exception:  # noqa: BLE001
        bundle = None
    _MODEL_CACHE[key] = bundle
    return bundle


class SensitivityClassifier:
    """Image sensitivity classifier with ML-first inference and heuristic fallback."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.low_threshold = 0.35
        self.high_threshold = 0.62
        env_path = os.environ.get("ADAPTIVE_RF_MODEL_PATH", "").strip()
        resolved_path = Path(env_path) if env_path else (Path(model_path) if model_path else _DEFAULT_MODEL_PATH)
        self.model_path = resolved_path
        self.bundle = _load_model_bundle(resolved_path)

    def _classify_heuristic(self, gray: np.ndarray) -> ClassificationResult:
        stats = _extract_stats(gray)
        entropy_norm = min(stats["entropy"] / 8.0, 1.0)
        score = float(
            np.clip(
                0.55 * entropy_norm + 0.30 * stats["edge_density"] + 0.15 * stats["variance_norm"],
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
                "entropy": round(stats["entropy"], 6),
                "edge_density": round(stats["edge_density"], 6),
                "variance_norm": round(stats["variance_norm"], 6),
                "mean_intensity": round(stats["mean_intensity"], 6),
                "std_intensity": round(stats["std_intensity"], 6),
                "aspect_ratio": round(stats["aspect_ratio"], 6),
                "dark_fraction": round(stats["dark_fraction"], 6),
                "bright_fraction": round(stats["bright_fraction"], 6),
                "classifier_source": "heuristic",
            },
        )

    def _classify_ml(self, gray: np.ndarray) -> ClassificationResult | None:
        bundle = self.bundle
        if not isinstance(bundle, dict):
            return None

        model = bundle.get("model")
        class_names = [str(x) for x in bundle.get("class_names", [])]
        pixel_size = int(bundle.get("pixel_size", 16) or 16)
        if model is None or not class_names or not hasattr(model, "predict_proba"):
            return None

        features = _extract_ml_features(gray, pixel_size=pixel_size).reshape(1, -1)
        probs = model.predict_proba(features)[0]
        predicted_index = int(np.argmax(probs))
        predicted_class = class_names[predicted_index]
        risk_probs = _risk_probabilities_from_classes(class_names, probs)
        label = max(risk_probs, key=risk_probs.get)
        score = float(sum(risk_probs[risk] * weight for risk, weight in _RISK_TO_WEIGHT.items()))
        confidence = float(max(risk_probs.values()))
        class_confidence = float(np.max(probs))
        stats = _extract_stats(gray)

        metrics: dict[str, Any] = {
            "entropy": round(stats["entropy"], 6),
            "edge_density": round(stats["edge_density"], 6),
            "variance_norm": round(stats["variance_norm"], 6),
            "mean_intensity": round(stats["mean_intensity"], 6),
            "std_intensity": round(stats["std_intensity"], 6),
            "aspect_ratio": round(stats["aspect_ratio"], 6),
            "dark_fraction": round(stats["dark_fraction"], 6),
            "bright_fraction": round(stats["bright_fraction"], 6),
            "confidence": round(confidence, 6),
            "class_confidence": round(class_confidence, 6),
            "p_low": round(float(risk_probs["low"]), 6),
            "p_medium": round(float(risk_probs["medium"]), 6),
            "p_high": round(float(risk_probs["high"]), 6),
            "predicted_class": predicted_class,
            "classifier_source": "random_forest",
            "model_path": str(self.model_path),
        }
        for class_name, prob in zip(class_names, probs.tolist()):
            metrics[f"class_prob__{class_name}"] = round(float(prob), 6)

        return ClassificationResult(label=label, score=score, metrics=metrics)

    def classify(self, image: np.ndarray) -> ClassificationResult:
        if image is None or image.size == 0:
            raise ValueError("Input image is empty.")

        gray = _to_gray(image)
        ml_result = self._classify_ml(gray)
        if ml_result is not None:
            return ml_result
        return self._classify_heuristic(gray)
