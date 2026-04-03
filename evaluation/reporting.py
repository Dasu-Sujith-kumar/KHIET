"""Plotting + HTML report generation for ``evaluate_pipeline.py`` outputs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Headless/report usage.

import matplotlib.pyplot as plt
import pandas as pd


_VARIANT_COLORS = {
    "aes_only": "#1f77b4",
    "static_chaos_aes": "#ff7f0e",
    "proposed_hardened": "#2ca02c",
}


def _fmt(value: Any) -> str:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if isinstance(value, str) and value in {"Infinity", "+Infinity", "inf", "+inf"}:
        return "inf"
    if isinstance(value, str) and value in {"-Infinity", "-inf"}:
        return "-inf"
    if isinstance(value, str) and value == "NaN":
        return "NaN"
    if isinstance(value, float) and math.isinf(value):
        return "∞"
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return str(value)


def _save_bar(df: pd.DataFrame, metric: str, title: str, out_path: Path, ylabel: str | None = None) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = [_VARIANT_COLORS.get(str(v), "#666666") for v in df.index]
    ax.bar(df.index.astype(str), df[metric].astype(float), color=colors)
    ax.set_title(title)
    ax.set_ylabel(ylabel or metric)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_grouped_bar(
    df: pd.DataFrame,
    metrics: list[str],
    title: str,
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(df.index))
    width = 0.8 / max(1, len(metrics))
    base = -0.4 + width / 2
    for idx, metric in enumerate(metrics):
        ax.bar(
            [i + base + idx * width for i in x],
            df[metric].astype(float).tolist(),
            width=width,
            label=metric,
        )
    ax.set_xticks(list(x))
    ax.set_xticklabels(df.index.astype(str).tolist(), rotation=0)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_scatter(
    df: pd.DataFrame,
    x_metric: str,
    y_metric: str,
    title: str,
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for variant, row in df.iterrows():
        ax.scatter(
            float(row[x_metric]),
            float(row[y_metric]),
            label=str(variant),
            color=_VARIANT_COLORS.get(str(variant), "#666666"),
            s=60,
        )
    ax.set_xlabel(x_metric)
    ax.set_ylabel(y_metric)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_pie(series: pd.Series, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 5))
    labels = [str(x) for x in series.index.tolist()]
    colors = [_VARIANT_COLORS.get(str(v), "#666666") for v in series.index.tolist()]
    ax.pie(series.astype(float).tolist(), labels=labels, autopct="%1.1f%%", colors=colors)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_sweep_lines(
    *,
    variants: dict[str, Any],
    ordered_variants: list[str],
    sweep_key: str,
    x_key: str,
    title: str,
    out_path: Path,
) -> bool:
    any_points = False
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for variant in ordered_variants:
        rec = variants.get(variant, {}) or {}
        sim = rec.get("attack_simulation", {}) or {}
        sweeps = sim.get("sweeps", {}) or {}
        points = sweeps.get(sweep_key)
        if not isinstance(points, list) or not points:
            continue
        any_points = True
        xs = [float(p.get(x_key)) for p in points if x_key in p]
        ys = [float(p.get("success_rate", 0.0)) for p in points if x_key in p]
        ax.plot(
            xs,
            ys,
            marker="o",
            linewidth=2,
            label=str(variant),
            color=_VARIANT_COLORS.get(str(variant), "#666666"),
        )

    if not any_points:
        plt.close(fig)
        return False

    ax.set_title(title)
    ax.set_xlabel(x_key)
    ax.set_ylabel("decrypt success rate (lower is better)")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return True


def _save_table_image(df: pd.DataFrame, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 0.6 + 0.35 * max(1, len(df))))
    ax.axis("off")
    ax.set_title(title, pad=12)

    display_df = df.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].map(_fmt)

    table = ax.table(
        cellText=display_df.values.tolist(),
        colLabels=[str(c) for c in display_df.columns.tolist()],
        rowLabels=[str(i) for i in display_df.index.tolist()],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _variants_dataframe(results: dict[str, Any]) -> pd.DataFrame:
    variants: dict[str, Any] = dict(results.get("variants", {}))
    rows: list[dict[str, Any]] = []
    for name, rec in variants.items():
        row = {"variant": str(name)}
        for key in [
            "entropy_cipher",
            "adj_correlation_cipher",
            "npcr",
            "uaci",
            "key_sensitivity",
            "psnr",
            "mse",
            "cipher_size_bytes",
            "execution_time_ms",
            "peak_memory_kib",
        ]:
            row[key] = rec.get(key)
        resilience = rec.get("attack_resilience", {}) or {}
        row["attack_bit_flip_ok"] = bool(resilience.get("bit_flip_decrypt_success", False))
        row["attack_noise_ok"] = bool(resilience.get("noise_decrypt_success", False))
        row["attack_crop_ok"] = bool(resilience.get("crop_decrypt_success", False))
        rows.append(row)

    df = pd.DataFrame(rows).set_index("variant")
    preferred = ["aes_only", "static_chaos_aes", "proposed_hardened"]
    ordered = [v for v in preferred if v in df.index] + [v for v in df.index if v not in preferred]
    return df.loc[ordered]


def _render_html(results: dict[str, Any], metrics_df: pd.DataFrame, images: list[str]) -> str:
    input_block = results.get("input", {}) or {}
    ablation = results.get("ablation_table", []) or []
    ablation_df = pd.DataFrame(ablation)

    def to_html_table(df: pd.DataFrame) -> str:
        display = df.copy()
        for col in display.columns:
            display[col] = display[col].map(_fmt)
        return display.to_html(classes="table", border=0)

    html_images = "\n".join([f'<div class="img"><img src="{name}" alt="{name}"/></div>' for name in images])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Hybrid Encryption Evaluation Report</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; color: #111; }}
    h1 {{ margin: 0 0 8px 0; }}
    .meta {{ color: #444; margin-bottom: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 14px; }}
    .img img {{ width: 100%; height: auto; border: 1px solid #ddd; border-radius: 8px; }}
    .card {{ border: 1px solid #e6e6e6; border-radius: 10px; padding: 14px; background: #fff; }}
    .table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    .table th, .table td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: center; }}
    .table th {{ background: #f6f6f6; }}
    code {{ background: #f3f3f3; padding: 1px 5px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>Evaluation Report</h1>
  <div class="meta">
    <div><b>Input</b>: <code>{_fmt(input_block.get("path", ""))}</code></div>
    <div><b>Shape</b>: <code>{_fmt(input_block.get("shape", ""))}</code> &nbsp; <b>Dtype</b>: <code>{_fmt(input_block.get("dtype", ""))}</code></div>
    <div><b>Image entropy</b>: <code>{_fmt(input_block.get("image_entropy", ""))}</code></div>
  </div>

  <div class="card">
    <h2 style="margin-top:0">Variant Metrics</h2>
    {to_html_table(metrics_df)}
  </div>

  <div class="card" style="margin-top:14px">
    <h2 style="margin-top:0">Ablation Table</h2>
    {to_html_table(ablation_df) if not ablation_df.empty else "<i>No ablation data</i>"}
  </div>

  <h2>Plots</h2>
  <div class="grid">
    {html_images}
  </div>
</body>
</html>
"""


def write_evaluation_report(results: dict[str, Any], out_dir: Path) -> Path:
    report_dir = Path(out_dir) / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    df = _variants_dataframe(results)
    df.to_csv(report_dir / "variant_metrics.csv")

    # Table snapshot.
    _save_table_image(df, "Variant Metrics", report_dir / "variant_metrics_table.png")

    # Core plots.
    _save_grouped_bar(
        df,
        ["entropy_cipher", "npcr", "uaci", "key_sensitivity"],
        "Core Security Metrics (grouped)",
        report_dir / "core_metrics_grouped.png",
    )
    _save_bar(df, "execution_time_ms", "Execution Time (ms)", report_dir / "execution_time_ms.png", ylabel="ms")
    _save_bar(df, "peak_memory_kib", "Peak Memory (KiB)", report_dir / "peak_memory_kib.png", ylabel="KiB")
    _save_bar(df, "cipher_size_bytes", "Ciphertext Size (bytes)", report_dir / "cipher_size_bytes.png", ylabel="bytes")

    if "npcr" in df.columns and "uaci" in df.columns:
        _save_scatter(df, "npcr", "uaci", "NPCR vs UACI", report_dir / "npcr_vs_uaci.png")
    if "entropy_cipher" in df.columns and "adj_correlation_cipher" in df.columns:
        df_corr = df.copy()
        df_corr["abs_corr"] = df_corr["adj_correlation_cipher"].astype(float).abs()
        _save_scatter(df_corr, "entropy_cipher", "abs_corr", "Entropy vs |Adjacent Correlation|", report_dir / "entropy_vs_abs_corr.png")

    # Attack-resilience (basic) plot.
    attack_cols = ["attack_bit_flip_ok", "attack_noise_ok", "attack_crop_ok"]
    if all(c in df.columns for c in attack_cols):
        attack_df = df[attack_cols].astype(int)
        _save_grouped_bar(attack_df, attack_cols, "Attack Decrypt-Success (lower is better)", report_dir / "attack_basic.png")

    # Pie charts for shares.
    if "execution_time_ms" in df.columns and df["execution_time_ms"].notna().any():
        _save_pie(df["execution_time_ms"].fillna(0.0), "Execution Time Share", report_dir / "time_share_pie.png")
    if "peak_memory_kib" in df.columns and df["peak_memory_kib"].notna().any():
        _save_pie(df["peak_memory_kib"].fillna(0.0), "Peak Memory Share", report_dir / "memory_share_pie.png")

    # High-suite sweeps (if present).
    variants_block: dict[str, Any] = dict(results.get("variants", {}))
    ordered_variants = [str(v) for v in df.index.tolist()]
    sweep_specs = [
        ("bit_flip_bits", "n_bits", "Bit-Flip Sweep"),
        ("byte_mutation", "n_bytes", "Random Byte Mutation Sweep"),
        ("gaussian_noise", "sigma", "Gaussian Noise Sweep (bytes)"),
        ("truncation", "keep_ratio", "Truncation/Cropping Sweep"),
        ("block_shuffle", "swaps", "Block Shuffle Sweep (16-byte blocks)"),
    ]
    for sweep_key, x_key, title in sweep_specs:
        _save_sweep_lines(
            variants=variants_block,
            ordered_variants=ordered_variants,
            sweep_key=sweep_key,
            x_key=x_key,
            title=title,
            out_path=report_dir / f"attack_sweep_{sweep_key}.png",
        )

    # Metadata tamper suite summary (only present for proposed_hardened).
    hardened = variants_block.get("proposed_hardened", {}) or {}
    meta_suite = (
        (hardened.get("attack_simulation", {}) or {}).get("metadata_tamper_suite") if isinstance(hardened, dict) else None
    )
    if isinstance(meta_suite, dict) and meta_suite:
        meta_df = pd.DataFrame(
            [{"case": str(k), "decrypt_success": int(bool(v))} for k, v in meta_suite.items()]
        ).set_index("case")
        _save_table_image(meta_df, "Metadata Tamper Suite (decrypt success should be 0)", report_dir / "metadata_tamper_table.png")

    images = [
        "variant_metrics_table.png",
        "core_metrics_grouped.png",
        "execution_time_ms.png",
        "peak_memory_kib.png",
        "cipher_size_bytes.png",
        "npcr_vs_uaci.png",
        "entropy_vs_abs_corr.png",
        "attack_basic.png",
        "time_share_pie.png",
        "memory_share_pie.png",
        "attack_sweep_bit_flip_bits.png",
        "attack_sweep_byte_mutation.png",
        "attack_sweep_gaussian_noise.png",
        "attack_sweep_truncation.png",
        "attack_sweep_block_shuffle.png",
        "metadata_tamper_table.png",
    ]
    images = [img for img in images if (report_dir / img).exists()]

    html = _render_html(results, df, images)
    html_path = report_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate plots/HTML report from evaluation_results.json")
    parser.add_argument("results_json", help="Path to evaluation_results.json")
    parser.add_argument("--out-dir", default=None, help="Output directory (defaults to results_json parent).")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    results_path = Path(args.results_json)
    out_dir = Path(args.out_dir) if args.out_dir else results_path.parent
    results = json.loads(results_path.read_text(encoding="utf-8"))
    html_path = write_evaluation_report(results, out_dir)
    print(str(html_path))


if __name__ == "__main__":
    main()
