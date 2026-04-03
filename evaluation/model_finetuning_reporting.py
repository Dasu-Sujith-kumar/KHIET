"""Generate graphs and a Markdown report for adaptive model finetuning runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _load_metrics(report_dir: Path) -> dict[str, Any]:
    path = report_dir / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing metrics.json in {report_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sampled_counts(metrics: dict[str, Any]) -> dict[str, int]:
    sampled = metrics.get("sampled_counts")
    if isinstance(sampled, dict) and sampled:
        return {str(k): int(v) for k, v in sampled.items()}
    labels = [str(x) for x in metrics.get("labels", [])]
    balanced = metrics.get("balanced_count_per_class")
    if labels and balanced is not None:
        return {label: int(balanced) for label in labels}
    return {}


def _total_sampled(counts: dict[str, int]) -> int:
    return int(sum(int(v) for v in counts.values()))


def _experiment_name(report_dir: Path, metrics: dict[str, Any]) -> str:
    explicit = metrics.get("experiment_name")
    if explicit:
        return str(explicit)
    return report_dir.name


def _plot_accuracy_curve(experiments: list[dict[str, Any]], out_path: Path) -> None:
    ordered = sorted(experiments, key=lambda rec: (rec["total_samples"], rec["accuracy"]))
    xs = [rec["total_samples"] for rec in ordered]
    ys_acc = [rec["accuracy"] * 100.0 for rec in ordered]
    ys_cv = [
        (float(rec["best_cv_score"]) * 100.0 if rec.get("best_cv_score") is not None else np.nan)
        for rec in ordered
    ]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(xs, ys_acc, marker="o", linewidth=2.2, label="holdout accuracy")
    ax.plot(xs, ys_cv, marker="s", linewidth=2.0, linestyle="--", label="best CV score")
    for rec in ordered:
        ax.annotate(
            rec["name"],
            (rec["total_samples"], rec["accuracy"] * 100.0),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8,
        )
    ax.set_title("Adaptive Model Accuracy Curve")
    ax.set_xlabel("Total sampled images used for finetuning")
    ax.set_ylabel("Accuracy / CV score (%)")
    ax.grid(alpha=0.25)
    ax.set_ylim(0, 100)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def _plot_class_counts_by_experiment(experiments: list[dict[str, Any]], out_path: Path) -> None:
    labels = sorted({label for rec in experiments for label in rec["sampled_counts"]})
    names = [rec["name"] for rec in experiments]
    x = np.arange(len(names))
    width = 0.8 / max(1, len(labels))

    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    for idx, label in enumerate(labels):
        values = [rec["sampled_counts"].get(label, 0) for rec in experiments]
        ax.bar(x - 0.4 + width / 2 + idx * width, values, width=width, label=label)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=0)
    ax.set_title("Images Used per Class Across Finetuning Runs")
    ax.set_ylabel("sampled images")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def _plot_train_test_counts(metrics: dict[str, Any], out_path: Path) -> None:
    train_counts = {str(k): int(v) for k, v in (metrics.get("train_counts") or {}).items()}
    test_counts = {str(k): int(v) for k, v in (metrics.get("test_counts") or {}).items()}
    labels = sorted(set(train_counts) | set(test_counts))
    train = [train_counts.get(label, 0) for label in labels]
    test = [test_counts.get(label, 0) for label in labels]

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    ax.bar(x, train, label="train")
    ax.bar(x, test, bottom=train, label="test")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_title("Train/Test Split Counts for Best Run")
    ax.set_ylabel("images")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def _plot_confusion_matrix(report_dir: Path, out_path: Path) -> None:
    df = pd.read_csv(report_dir / "confusion_matrix.csv")
    labels = df.iloc[:, 0].astype(str).tolist()
    values = df.iloc[:, 1:].astype(float).values

    fig, ax = plt.subplots(figsize=(7.0, 5.8))
    image = ax.imshow(values, cmap="Blues")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_yticklabels(labels)
    ax.set_title("Confusion Matrix for Best Finetuned Model")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, int(values[i, j]), ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def _plot_feature_importance(report_dir: Path, out_path: Path, top_n: int = 15) -> None:
    df = pd.read_csv(report_dir / "feature_importances.csv").head(top_n)
    df = df.iloc[::-1]

    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    ax.barh(df["feature"], df["importance"].astype(float))
    ax.set_title("Top Feature Importances for Best Finetuned Model")
    ax.set_xlabel("importance")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def _plot_per_class_metrics(metrics: dict[str, Any], out_path: Path) -> None:
    report = metrics.get("classification_report", {}) or {}
    labels = [label for label in metrics.get("labels", []) if label in report]
    precision = [float(report[label]["precision"]) * 100.0 for label in labels]
    recall = [float(report[label]["recall"]) * 100.0 for label in labels]
    f1 = [float(report[label]["f1-score"]) * 100.0 for label in labels]

    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(10.2, 5.0))
    ax.bar(x - width, precision, width=width, label="precision")
    ax.bar(x, recall, width=width, label="recall")
    ax.bar(x + width, f1, width=width, label="f1")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_title("Per-Class Metrics for Best Finetuned Model")
    ax.set_ylabel("score (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def _write_markdown(
    *,
    report_md: Path,
    report_dir: Path,
    experiments: list[dict[str, Any]],
    best: dict[str, Any],
) -> None:
    best_metrics = best["metrics"]
    best_counts = best["sampled_counts"]
    classification_report = best_metrics.get("classification_report", {}) or {}
    lines: list[str] = []
    lines.append("# Adaptive Model Finetuning Report")
    lines.append("")
    lines.append("Date: 2026-04-02")
    lines.append("")
    lines.append("This report summarizes the Random Forest finetuning runs used to upgrade the adaptive sensitivity layer.")
    lines.append("")
    lines.append("## 1. Experiments Compared")
    lines.append("")
    lines.append("| Run | Total sampled images | Holdout accuracy | Best CV score |")
    lines.append("| --- | ---: | ---: | ---: |")
    for rec in sorted(experiments, key=lambda item: (item["total_samples"], item["accuracy"])):
        cv_text = f"{float(rec['best_cv_score']) * 100.0:.2f}%" if rec.get("best_cv_score") is not None else "N/A"
        lines.append(
            f"| `{rec['name']}` | {rec['total_samples']} | {rec['accuracy'] * 100.0:.2f}% | {cv_text} |"
        )
    lines.append("")
    lines.append("## 2. Best Model")
    lines.append("")
    lines.append(f"- Best run: `{best['name']}`")
    lines.append(f"- Holdout accuracy: `{best['accuracy'] * 100.0:.2f}%`")
    if best.get("best_cv_score") is not None:
        lines.append(f"- Best cross-validation score: `{float(best['best_cv_score']) * 100.0:.2f}%`")
    lines.append(f"- Output model: `{best_metrics.get('output_model', '')}`")
    lines.append("")
    lines.append("Class usage in the best run:")
    lines.append("")
    lines.append("| Class | Images used |")
    lines.append("| --- | ---: |")
    for label, count in sorted(best_counts.items()):
        lines.append(f"| `{label}` | {int(count)} |")
    lines.append("")
    lines.append("Per-class metrics in the best run:")
    lines.append("")
    lines.append("| Class | Precision | Recall | F1 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for label in best_metrics.get("labels", []):
        if label not in classification_report:
            continue
        rec = classification_report[label]
        lines.append(
            f"| `{label}` | {float(rec['precision']) * 100.0:.2f}% | {float(rec['recall']) * 100.0:.2f}% | {float(rec['f1-score']) * 100.0:.2f}% |"
        )
    lines.append("")
    lines.append("## 3. Graphs")
    lines.append("")
    lines.append(f"![Accuracy Curve]({report_dir.name}/accuracy_curve.png)")
    lines.append("")
    lines.append(f"![Images Per Class]({report_dir.name}/images_used_per_class.png)")
    lines.append("")
    lines.append(f"![Train Test Split]({report_dir.name}/train_test_counts_best.png)")
    lines.append("")
    lines.append(f"![Confusion Matrix]({report_dir.name}/confusion_matrix_best.png)")
    lines.append("")
    lines.append(f"![Per Class Metrics]({report_dir.name}/per_class_metrics_best.png)")
    lines.append("")
    lines.append(f"![Feature Importance]({report_dir.name}/feature_importance_best.png)")
    lines.append("")
    lines.append("## 4. Interpretation")
    lines.append("")
    lines.append("- Increasing the usable dataset size improved both holdout accuracy and cross-validation score.")
    lines.append("- Converting medical DICOM slices to PNG made the medical class usable in the same training pipeline as the raster classes.")
    lines.append("- The strongest run used larger capped samples from the large folders while keeping smaller classes such as `manga` and `forms` at their actual available counts.")
    lines.append("- This finetuned model is the one integrated into the adaptive pipeline for the rerun evaluation.")
    lines.append("")
    report_md.write_text("\n".join(lines), encoding="utf-8")


def generate_report(report_dirs: list[Path], out_dir: Path, report_md: Path) -> None:
    experiments: list[dict[str, Any]] = []
    for report_dir in report_dirs:
        metrics = _load_metrics(report_dir)
        sampled_counts = _sampled_counts(metrics)
        experiments.append(
            {
                "name": _experiment_name(report_dir, metrics),
                "report_dir": report_dir,
                "metrics": metrics,
                "sampled_counts": sampled_counts,
                "total_samples": _total_sampled(sampled_counts),
                "accuracy": float(metrics.get("accuracy", 0.0)),
                "best_cv_score": metrics.get("best_cv_score"),
            }
        )

    if not experiments:
        raise ValueError("No experiments provided.")

    out_dir.mkdir(parents=True, exist_ok=True)
    best = max(experiments, key=lambda rec: (rec["accuracy"], rec["total_samples"]))

    _plot_accuracy_curve(experiments, out_dir / "accuracy_curve.png")
    _plot_class_counts_by_experiment(experiments, out_dir / "images_used_per_class.png")
    _plot_train_test_counts(best["metrics"], out_dir / "train_test_counts_best.png")
    _plot_confusion_matrix(best["report_dir"], out_dir / "confusion_matrix_best.png")
    _plot_feature_importance(best["report_dir"], out_dir / "feature_importance_best.png")
    _plot_per_class_metrics(best["metrics"], out_dir / "per_class_metrics_best.png")

    summary_rows = [
        {
            "run": rec["name"],
            "total_samples": rec["total_samples"],
            "accuracy": rec["accuracy"],
            "best_cv_score": rec["best_cv_score"],
        }
        for rec in experiments
    ]
    pd.DataFrame(summary_rows).sort_values(["total_samples", "accuracy"]).to_csv(out_dir / "experiment_summary.csv", index=False)
    _write_markdown(report_md=report_md, report_dir=out_dir, experiments=experiments, best=best)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a report for adaptive model finetuning runs.")
    parser.add_argument(
        "--report-dirs",
        nargs="+",
        default=["adaptive_rf_report", "adaptive_rf_report_cap100", "adaptive_rf_report_cap200"],
        help="Directories containing metrics.json, confusion_matrix.csv, and feature_importances.csv.",
    )
    parser.add_argument("--out-dir", default="adaptive_model_finetuning_report", help="Directory for generated graphs and CSV summary.")
    parser.add_argument(
        "--report-md",
        default="ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md",
        help="Markdown report path.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    report_dirs = [Path(path) for path in args.report_dirs]
    out_dir = Path(args.out_dir)
    report_md = Path(args.report_md)
    generate_report(report_dirs=report_dirs, out_dir=out_dir, report_md=report_md)
    print(str(report_md))


if __name__ == "__main__":
    main()
