"""Train a Random Forest classifier from the local image folders.

The script treats each top-level directory under ``sample-images`` as one class.
It supports either strict balanced sampling or capped per-class sampling and
handles DICOM-heavy folders such as ``sample-images/medical``.

Example:

    .\.venv\Scripts\python.exe train_adaptive_random_forest.py ^
        --data-root sample-images ^
        --output-model adaptive_rf_report\adaptive_random_forest.pkl ^
        --report-dir adaptive_rf_report ^
        --samples-per-class 100 ^
        --sampling-strategy up_to_limit ^
        --export-medical-png ^
        --dicom-mode slice
"""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:  # pragma: no cover - optional at runtime
    cv2 = None

try:
    import pydicom
except ImportError:  # pragma: no cover - optional at runtime
    pydicom = None

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
    from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
except ImportError:  # pragma: no cover - optional at runtime
    RandomForestClassifier = None
    GridSearchCV = None
    StratifiedKFold = None
    accuracy_score = None
    classification_report = None
    confusion_matrix = None
    train_test_split = None


_RASTER_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_DICOM_EXT = ".dcm"
_DEFAULT_RISK_BY_CLASS = {
    "faces": "high",
    "forms": "high",
    "medical": "high",
    "manga": "medium",
    "land-scapes and others": "low",
}


def _natural_sort_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", str(path).lower())
    out: list[Any] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            out.append(int(part))
        else:
            out.append(part)
    return out


def _jsonify(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, Path):
        return str(value)
    return value


def _require_training_deps() -> None:
    missing: list[str] = []
    if RandomForestClassifier is None or train_test_split is None:
        missing.append("scikit-learn")
    if pydicom is None:
        missing.append("pydicom")
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing required packages: {joined}. "
            "Install them first, for example with `pip install -r requirements.txt`."
        )


def _discover_class_dirs(data_root: Path) -> list[Path]:
    class_dirs = [p for p in data_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    return sorted(class_dirs, key=lambda p: p.name.lower())


def _collect_dicom_samples(class_dir: Path, mode: str) -> list[Path]:
    dicom_paths = sorted((p for p in class_dir.rglob(f"*{_DICOM_EXT}") if p.is_file()), key=_natural_sort_key)
    if mode == "slice":
        return dicom_paths

    grouped: dict[Path, list[Path]] = defaultdict(list)
    for path in dicom_paths:
        grouped[path.parent].append(path)

    selected: list[Path] = []
    for parent in sorted(grouped, key=lambda p: str(p).lower()):
        series = sorted(grouped[parent], key=_natural_sort_key)
        selected.append(series[len(series) // 2])
    return selected


def _save_gray_png(gray: np.ndarray, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(gray.astype(np.uint8), mode="L")
    image.save(out_path, format="PNG")


def _export_dicom_tree_to_png(
    *,
    class_dir: Path,
    export_dir: Path,
    mode: str,
    force: bool,
) -> tuple[list[Path], list[dict[str, str]]]:
    dicom_paths = _collect_dicom_samples(class_dir, mode=mode)
    exported: list[Path] = []
    failed: list[dict[str, str]] = []
    for path in dicom_paths:
        rel = path.relative_to(class_dir).with_suffix(".png")
        out_path = export_dir / rel
        try:
            if force or not out_path.exists():
                gray = _load_dicom_gray(path)
                _save_gray_png(gray, out_path)
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": str(path), "error": str(exc)})
            continue
        exported.append(out_path)
    return exported, failed


def _collect_class_samples(
    class_dir: Path,
    dicom_mode: str,
    *,
    medical_export_dir: Path | None = None,
) -> list[Path]:
    if class_dir.name.lower() == "medical" and medical_export_dir is not None and medical_export_dir.exists():
        exported_rasters = sorted(
            (p for p in medical_export_dir.rglob("*") if p.is_file() and p.suffix.lower() in _RASTER_EXTS),
            key=_natural_sort_key,
        )
        if exported_rasters:
            return exported_rasters

    raster_paths = sorted(
        (p for p in class_dir.rglob("*") if p.is_file() and p.suffix.lower() in _RASTER_EXTS),
        key=_natural_sort_key,
    )
    dicom_paths = _collect_dicom_samples(class_dir, mode=dicom_mode)
    return raster_paths + dicom_paths


def _resolve_sample_plan(
    *,
    discovered_counts: dict[str, int],
    samples_per_class: str,
    sampling_strategy: str,
) -> dict[str, int]:
    if not discovered_counts:
        return {}

    if sampling_strategy not in {"balanced", "up_to_limit"}:
        raise ValueError("sampling_strategy must be `balanced` or `up_to_limit`.")

    if samples_per_class == "auto":
        if sampling_strategy == "balanced":
            target = min(discovered_counts.values())
            return {label: int(target) for label in discovered_counts}
        return {label: int(count) for label, count in discovered_counts.items()}

    requested = int(samples_per_class)
    if requested <= 0:
        raise ValueError("samples_per_class must be `auto` or a positive integer.")

    if sampling_strategy == "balanced":
        target = min(min(discovered_counts.values()), requested)
        return {label: int(target) for label in discovered_counts}
    return {label: int(min(count, requested)) for label, count in discovered_counts.items()}


def _normalize_to_u8(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.size == 0:
        raise ValueError("Image is empty.")

    if arr.ndim == 3 and arr.shape[2] > 3:
        arr = arr[..., :3]

    arr = arr.astype(np.float32, copy=False)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError("Image has no finite pixels.")

    lo = float(np.percentile(finite, 1.0))
    hi = float(np.percentile(finite, 99.0))
    if hi <= lo:
        lo = float(finite.min())
        hi = float(finite.max())
    if hi <= lo:
        return np.zeros(arr.shape[:2], dtype=np.uint8) if arr.ndim == 3 else np.zeros(arr.shape, dtype=np.uint8)

    scaled = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
    scaled = (scaled * 255.0).round().astype(np.uint8)
    return scaled


def _load_dicom_gray(path: Path) -> np.ndarray:
    if pydicom is None:
        raise RuntimeError("pydicom is required to read DICOM files.")

    ds = pydicom.dcmread(str(path), force=True)
    pixels = ds.pixel_array.astype(np.float32)

    slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
    intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
    pixels = pixels * slope + intercept

    if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
        pixels = pixels.max() - pixels

    return _normalize_to_u8(pixels)


def _load_raster_gray(path: Path) -> np.ndarray:
    if cv2 is not None:
        data = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
        if image is not None:
            return image.astype(np.uint8, copy=False)

    with Image.open(path) as img:
        gray = img.convert("L")
        return np.asarray(gray, dtype=np.uint8)


def _load_gray_image(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix == _DICOM_EXT:
        return _load_dicom_gray(path)
    if suffix in _RASTER_EXTS:
        return _load_raster_gray(path)
    raise ValueError(f"Unsupported file type: {path}")


def _resize_gray(gray: np.ndarray, size: int) -> np.ndarray:
    if cv2 is not None:
        return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    pil = Image.fromarray(gray, mode="L")
    resized = pil.resize((size, size), resample=Image.Resampling.BILINEAR)
    return np.asarray(resized, dtype=np.uint8)


def _entropy_u8(gray: np.ndarray) -> float:
    hist = np.bincount(gray.reshape(-1).astype(np.uint8), minlength=256).astype(np.float64)
    probs = hist / max(float(hist.sum()), 1.0)
    nz = probs[probs > 0]
    return float(-(nz * np.log2(nz)).sum())


def _edge_density(gray: np.ndarray) -> float:
    if cv2 is not None:
        edges = cv2.Canny(gray, threshold1=100, threshold2=200)
        return float(np.mean(edges > 0))

    gx = np.diff(gray.astype(np.float32), axis=1, prepend=gray[:, :1].astype(np.float32))
    gy = np.diff(gray.astype(np.float32), axis=0, prepend=gray[:1, :].astype(np.float32))
    mag = np.sqrt(gx * gx + gy * gy)
    threshold = float(np.percentile(mag, 75.0))
    return float(np.mean(mag > threshold))


def _extract_feature_vector(gray: np.ndarray, *, pixel_size: int) -> tuple[np.ndarray, list[str]]:
    h, w = gray.shape[:2]
    mean_intensity = float(np.mean(gray) / 255.0)
    std_intensity = float(np.std(gray) / 255.0)
    variance_norm = float(np.var(gray.astype(np.float32)) / (255.0 * 255.0))
    entropy = _entropy_u8(gray) / 8.0
    edge_density = _edge_density(gray)
    aspect_ratio = float(w / max(h, 1))
    dark_fraction = float(np.mean(gray < 32))
    bright_fraction = float(np.mean(gray > 223))

    small = _resize_gray(gray, pixel_size).astype(np.float32) / 255.0
    pixel_features = small.reshape(-1)

    stats = np.array(
        [
            entropy,
            edge_density,
            variance_norm,
            mean_intensity,
            std_intensity,
            aspect_ratio,
            dark_fraction,
            bright_fraction,
        ],
        dtype=np.float32,
    )
    feature_vector = np.concatenate([stats, pixel_features.astype(np.float32)], axis=0)
    feature_names = [
        "entropy_norm",
        "edge_density",
        "variance_norm",
        "mean_intensity",
        "std_intensity",
        "aspect_ratio",
        "dark_fraction",
        "bright_fraction",
    ] + [f"pixel_{idx:04d}" for idx in range(pixel_features.size)]
    return feature_vector, feature_names


def _build_dataset(
    *,
    data_root: Path,
    dicom_mode: str,
    sample_plan: dict[str, int],
    seed: int,
    pixel_size: int,
    medical_export_dir: Path | None,
) -> tuple[np.ndarray, list[str], list[str], list[dict[str, Any]], dict[str, int], dict[str, int], list[dict[str, str]]]:
    rng = random.Random(seed)
    class_dirs = _discover_class_dirs(data_root)
    if not class_dirs:
        raise ValueError(f"No class folders found under: {data_root}")

    discovered: dict[str, list[Path]] = {}
    for class_dir in class_dirs:
        paths = _collect_class_samples(
            class_dir,
            dicom_mode=dicom_mode,
            medical_export_dir=medical_export_dir,
        )
        if not paths:
            continue
        discovered[class_dir.name] = paths

    if not discovered:
        raise ValueError(f"No supported image or DICOM files found under: {data_root}")

    discovered_counts = {label: len(paths) for label, paths in discovered.items()}
    if set(sample_plan) != set(discovered_counts):
        missing = sorted(set(discovered_counts) - set(sample_plan))
        extra = sorted(set(sample_plan) - set(discovered_counts))
        raise ValueError(f"Sample plan mismatch. Missing={missing} Extra={extra}")
    for label, count in sample_plan.items():
        if int(count) < 2:
            raise ValueError(
                f"Class `{label}` would contribute fewer than 2 samples. "
                "Add more data or lower the number of classes."
            )

    rows: list[dict[str, Any]] = []
    feature_names: list[str] | None = None
    skipped: list[dict[str, str]] = []
    actual_counts: Counter[str] = Counter()

    for label, paths in sorted(discovered.items()):
        target_count = int(sample_plan[label])
        selected = rng.sample(paths, k=target_count) if len(paths) > target_count else list(paths)
        for path in sorted(selected, key=_natural_sort_key):
            try:
                gray = _load_gray_image(path)
            except Exception as exc:  # noqa: BLE001
                skipped.append({"label": label, "path": str(path), "error": str(exc)})
                continue
            features, names = _extract_feature_vector(gray, pixel_size=pixel_size)
            if feature_names is None:
                feature_names = names
            rows.append(
                {
                    "label": label,
                    "path": path,
                    "file_type": "dicom" if path.suffix.lower() == _DICOM_EXT else "raster",
                    "features": features,
                    "recommended_risk": _DEFAULT_RISK_BY_CLASS.get(label, "medium"),
                }
            )
            actual_counts[label] += 1

    if feature_names is None:
        raise ValueError("No training rows could be built from the selected files.")
    for label, count in actual_counts.items():
        if count < 2:
            raise ValueError(f"Class `{label}` has only {count} usable samples after file decoding.")

    X = np.vstack([row["features"] for row in rows]).astype(np.float32)
    y = [str(row["label"]) for row in rows]
    manifest = [
        {
            "label": row["label"],
            "path": str(row["path"]),
            "file_type": row["file_type"],
            "recommended_risk": row["recommended_risk"],
        }
        for row in rows
    ]
    return X, y, feature_names, manifest, discovered_counts, {label: int(actual_counts.get(label, 0)) for label in sample_plan}, skipped


def _write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["split", "label", "path", "file_type", "recommended_risk"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_feature_importances(path: Path, feature_names: list[str], importances: np.ndarray, top_n: int = 40) -> None:
    ranked = sorted(zip(feature_names, importances.tolist()), key=lambda item: item[1], reverse=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["feature", "importance"])
        for feature, importance in ranked[:top_n]:
            writer.writerow([feature, f"{importance:.8f}"])


def _write_confusion_matrix(path: Path, labels: list[str], matrix: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual/predicted", *labels])
        for label, row in zip(labels, matrix.tolist()):
            writer.writerow([label, *row])


def _train_model(
    *,
    X: np.ndarray,
    y: list[str],
    feature_names: list[str],
    manifest: list[dict[str, Any]],
    discovered_counts: dict[str, int],
    sampled_counts: dict[str, int],
    output_model: Path,
    report_dir: Path,
    test_size: float,
    seed: int,
    pixel_size: int,
    dicom_mode: str,
    data_root: Path,
    n_jobs: int,
    sampling_strategy: str,
    medical_export_dir: Path | None,
    skipped_files: list[dict[str, str]],
    export_failures: list[dict[str, str]],
) -> dict[str, Any]:
    _require_training_deps()

    indices = np.arange(len(y))
    train_idx, test_idx = train_test_split(
        indices,
        test_size=test_size,
        stratify=np.array(y),
        random_state=seed,
    )

    X_train = X[train_idx]
    X_test = X[test_idx]
    y_train = [y[i] for i in train_idx]
    y_test = [y[i] for i in test_idx]

    train_counts = Counter(y_train)
    min_train_per_class = min(train_counts.values())
    cv_splits = min(3, min_train_per_class)

    base_model = RandomForestClassifier(
        random_state=seed,
        n_jobs=n_jobs,
        class_weight="balanced_subsample",
    )

    if cv_splits >= 2 and GridSearchCV is not None and StratifiedKFold is not None:
        grid = GridSearchCV(
            estimator=base_model,
            param_grid={
                "n_estimators": [100, 200],
                "max_depth": [None, 12, 24],
                "min_samples_leaf": [1, 2, 4],
                "max_features": ["sqrt", 0.35],
            },
            scoring="f1_macro",
            cv=StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=seed),
            n_jobs=n_jobs,
            refit=True,
        )
        grid.fit(X_train, y_train)
        model = grid.best_estimator_
        best_params = dict(grid.best_params_)
        best_cv_score = float(grid.best_score_)
    else:
        model = base_model.set_params(
            n_estimators=200,
            max_depth=None,
            min_samples_leaf=1,
            max_features="sqrt",
        )
        model.fit(X_train, y_train)
        best_params = {
            "n_estimators": int(model.n_estimators),
            "max_depth": model.max_depth,
            "min_samples_leaf": int(model.min_samples_leaf),
            "max_features": model.max_features,
        }
        best_cv_score = None

    y_pred = model.predict(X_test)
    labels = sorted(set(y))
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, y_pred, labels=labels)

    output_model.parent.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    bundle = {
        "model_type": "random_forest_classifier",
        "model": model,
        "class_names": labels,
        "feature_names": feature_names,
        "pixel_size": int(pixel_size),
        "recommended_risk_by_class": dict(_DEFAULT_RISK_BY_CLASS),
        "training": {
            "data_root": str(data_root),
            "dicom_mode": dicom_mode,
            "sampling_strategy": str(sampling_strategy),
            "sampled_counts": dict(sampled_counts),
            "seed": int(seed),
            "test_size": float(test_size),
            "n_jobs": int(n_jobs),
            "discovered_counts": dict(discovered_counts),
            "train_counts": dict(train_counts),
            "test_counts": dict(Counter(y_test)),
            "best_params": dict(best_params),
            "best_cv_score": best_cv_score,
            "medical_export_dir": str(medical_export_dir) if medical_export_dir is not None else None,
            "skipped_file_count": int(len(skipped_files)),
            "medical_export_failure_count": int(len(export_failures)),
        },
    }

    with output_model.open("wb") as handle:
        pickle.dump(bundle, handle, protocol=pickle.HIGHEST_PROTOCOL)

    manifest_rows: list[dict[str, Any]] = []
    for idx in train_idx:
        row = dict(manifest[int(idx)])
        row["split"] = "train"
        manifest_rows.append(row)
    for idx in test_idx:
        row = dict(manifest[int(idx)])
        row["split"] = "test"
        manifest_rows.append(row)
    manifest_rows.sort(key=lambda row: (row["split"], row["label"], row["path"]))
    _write_manifest(report_dir / "sample_manifest.csv", manifest_rows)
    _write_confusion_matrix(report_dir / "confusion_matrix.csv", labels, matrix)
    _write_feature_importances(report_dir / "feature_importances.csv", feature_names, model.feature_importances_)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "labels": labels,
        "sampling_strategy": str(sampling_strategy),
        "sampled_counts": dict(sampled_counts),
        "discovered_counts": dict(discovered_counts),
        "train_counts": dict(train_counts),
        "test_counts": dict(Counter(y_test)),
        "best_params": dict(best_params),
        "best_cv_score": best_cv_score,
        "classification_report": report,
        "recommended_risk_by_class": dict(_DEFAULT_RISK_BY_CLASS),
        "output_model": str(output_model),
        "report_dir": str(report_dir),
        "medical_export_dir": str(medical_export_dir) if medical_export_dir is not None else None,
        "skipped_file_count": int(len(skipped_files)),
        "medical_export_failure_count": int(len(export_failures)),
    }
    (report_dir / "metrics.json").write_text(json.dumps(_jsonify(metrics), indent=2), encoding="utf-8")
    if skipped_files:
        (report_dir / "skipped_files.json").write_text(json.dumps(_jsonify(skipped_files), indent=2), encoding="utf-8")
    if export_failures:
        (report_dir / "medical_export_failures.json").write_text(
            json.dumps(_jsonify(export_failures), indent=2),
            encoding="utf-8",
        )
    return metrics


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a balanced Random Forest on the local class folders, including DICOM medical data."
    )
    parser.add_argument("--data-root", default="sample-images", help="Top-level dataset folder containing class subfolders.")
    parser.add_argument(
        "--output-model",
        default="adaptive_rf_report/adaptive_random_forest.pkl",
        help="Where to save the trained Random Forest bundle.",
    )
    parser.add_argument(
        "--report-dir",
        default="adaptive_rf_report",
        help="Directory for manifests, confusion matrix, feature importances, and metrics.",
    )
    parser.add_argument(
        "--samples-per-class",
        default="auto",
        help="Use `auto` or set an integer cap such as `100` or `200`.",
    )
    parser.add_argument(
        "--sampling-strategy",
        choices=["balanced", "up_to_limit"],
        default="balanced",
        help="`balanced` uses the same count for every class. `up_to_limit` uses up to N per class and keeps smaller classes as-is.",
    )
    parser.add_argument(
        "--dicom-mode",
        choices=["slice", "series-center"],
        default="slice",
        help="For DICOM folders, use every slice or one center slice per DICOM series.",
    )
    parser.add_argument(
        "--export-medical-png",
        action="store_true",
        help="Convert medical DICOM files to PNG on disk before sampling/training.",
    )
    parser.add_argument(
        "--force-medical-export",
        action="store_true",
        help="Rebuild medical PNG export even if PNG files already exist.",
    )
    parser.add_argument(
        "--medical-export-dir",
        default="adaptive_rf_report/medical_png_export",
        help="Directory where converted medical PNG slices are stored.",
    )
    parser.add_argument("--pixel-size", type=int, default=16, help="Resize grayscale image to N x N before flattening.")
    parser.add_argument("--test-size", type=float, default=0.25, help="Holdout fraction for evaluation.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Parallel workers for Random Forest / grid search. Default `1` avoids Windows sandbox issues.",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only print discovered counts and the balanced sample size without training.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    data_root = Path(args.data_root)
    if not data_root.exists():
        raise SystemExit(f"Dataset root not found: {data_root}")

    medical_export_dir = Path(args.medical_export_dir) if args.medical_export_dir else None
    class_dirs = _discover_class_dirs(data_root)
    medical_class_dir = next((p for p in class_dirs if p.name.lower() == "medical"), None)
    export_failures: list[dict[str, str]] = []
    if args.export_medical_png and medical_class_dir is not None:
        if medical_export_dir is None:
            raise SystemExit("medical_export_dir is required when --export-medical-png is used.")
        exported, export_failures = _export_dicom_tree_to_png(
            class_dir=medical_class_dir,
            export_dir=medical_export_dir,
            mode=str(args.dicom_mode),
            force=bool(args.force_medical_export),
        )
        print(f"Exported/available medical PNG slices: {len(exported)} -> {medical_export_dir}")
        if export_failures:
            print(f"Skipped malformed DICOM slices during export: {len(export_failures)}")

    discovered_counts: dict[str, int] = {}
    for class_dir in class_dirs:
        paths = _collect_class_samples(
            class_dir,
            dicom_mode=args.dicom_mode,
            medical_export_dir=medical_export_dir,
        )
        if paths:
            discovered_counts[class_dir.name] = len(paths)

    if not discovered_counts:
        raise SystemExit(f"No supported raster or DICOM files found under: {data_root}")

    sample_plan = _resolve_sample_plan(
        discovered_counts=discovered_counts,
        samples_per_class=str(args.samples_per_class),
        sampling_strategy=str(args.sampling_strategy),
    )

    print("Discovered class counts:")
    for label, count in sorted(discovered_counts.items()):
        print(f"  - {label}: {count}")
    print("Selected sample counts:")
    for label, count in sorted(sample_plan.items()):
        print(f"  - {label}: {count}")
    print(f"Sampling strategy: {args.sampling_strategy}")
    print(f"DICOM mode: {args.dicom_mode}")
    if medical_export_dir is not None:
        print(f"Medical export dir: {medical_export_dir}")

    if args.scan_only:
        return

    X, y, feature_names, manifest, discovered_counts, sampled_counts, skipped_files = _build_dataset(
        data_root=data_root,
        dicom_mode=args.dicom_mode,
        sample_plan=sample_plan,
        seed=int(args.seed),
        pixel_size=int(args.pixel_size),
        medical_export_dir=medical_export_dir,
    )
    if skipped_files:
        print(f"Skipped unreadable files during dataset build: {len(skipped_files)}")
    metrics = _train_model(
        X=X,
        y=y,
        feature_names=feature_names,
        manifest=manifest,
        discovered_counts=discovered_counts,
        sampled_counts=sampled_counts,
        output_model=Path(args.output_model),
        report_dir=Path(args.report_dir),
        test_size=float(args.test_size),
        seed=int(args.seed),
        pixel_size=int(args.pixel_size),
        dicom_mode=str(args.dicom_mode),
        data_root=data_root,
        n_jobs=int(args.n_jobs),
        sampling_strategy=str(args.sampling_strategy),
        medical_export_dir=medical_export_dir,
        skipped_files=skipped_files,
        export_failures=export_failures,
    )

    print("Training complete.")
    print(f"Model: {args.output_model}")
    print(f"Report dir: {args.report_dir}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")


if __name__ == "__main__":
    main()
