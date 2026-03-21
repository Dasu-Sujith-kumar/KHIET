"""Aggregated reporting for ``batch_run.py`` results."""

from __future__ import annotations

import argparse
import math
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


_MODE_COLORS = {
    "passphrase_only": "#1f77b4",
    "x25519_only": "#ff7f0e",
    "hybrid": "#2ca02c",
}


def _fmt(value: Any) -> str:
    if isinstance(value, float) and math.isinf(value):
        return "∞"
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return str(value)


def _save_table_image(df: pd.DataFrame, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 0.7 + 0.35 * max(1, len(df))))
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


def _save_grouped_bar(df: pd.DataFrame, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    modes = [str(i) for i in df.index.tolist()]
    x = range(len(modes))
    metrics = [str(c) for c in df.columns.tolist()]
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
    ax.set_xticklabels(modes)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_bar(series: pd.Series, title: str, ylabel: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    modes = [str(i) for i in series.index.tolist()]
    colors = [_MODE_COLORS.get(m, "#666666") for m in modes]
    ax.bar(modes, series.astype(float).tolist(), color=colors)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_bar_generic(series: pd.Series, title: str, ylabel: str, out_path: Path, *, color: str = "#4c78a8") -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [str(i) for i in series.index.tolist()]
    ax.bar(labels, series.astype(float).tolist(), color=color)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_pie(series: pd.Series, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 5))
    labels = [str(i) for i in series.index.tolist()]
    ax.pie(series.astype(float).tolist(), labels=labels, autopct="%1.1f%%")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _save_boxplot(df: pd.DataFrame, column: str, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    groups = []
    labels = []
    for mode, group in df.groupby("mode", dropna=False):
        labels.append(str(mode))
        groups.append(group[column].astype(float).dropna().values)
    # Matplotlib 3.9 renamed `labels` -> `tick_labels` (keeping backward compat).
    try:
        ax.boxplot(groups, tick_labels=labels, showfliers=False)
    except TypeError:
        ax.boxplot(groups, labels=labels, showfliers=False)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _render_html(
    config: dict[str, Any],
    mode_summary_df: pd.DataFrame,
    dataset_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    profile_df: pd.DataFrame,
    crosstab_df: pd.DataFrame,
    unique_table_df: pd.DataFrame,
    images: list[str],
) -> str:
    def to_html_table(df: pd.DataFrame) -> str:
        display = df.copy()
        for col in display.columns:
            display[col] = display[col].map(_fmt)
        return display.to_html(classes="table", border=0)

    def maybe_table(df: pd.DataFrame, empty_msg: str) -> str:
        if df is None or df.empty:
            return f"<i>{empty_msg}</i>"
        return to_html_table(df)

    html_images = "\n".join([f'<div class="img"><img src="{name}" alt="{name}"/></div>' for name in images])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Batch Encryption Report</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; color: #111; }}
    h1 {{ margin: 0 0 8px 0; }}
    .meta {{ color: #444; margin-bottom: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 14px; }}
    .img img {{ width: 100%; height: auto; border: 1px solid #ddd; border-radius: 8px; }}
    .card {{ border: 1px solid #e6e6e6; border-radius: 10px; padding: 14px; background: #fff; }}
    .scroll {{ max-height: 420px; overflow: auto; border: 1px solid #f0f0f0; border-radius: 8px; padding: 6px; }}
    .table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    .table th, .table td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: center; }}
    .table th {{ background: #f6f6f6; }}
    code {{ background: #f3f3f3; padding: 1px 5px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>Batch Report</h1>
  <div class="meta">
    <div><b>Input</b>: <code>{_fmt(config.get("input_dir", ""))}</code></div>
    <div><b>Output</b>: <code>{_fmt(config.get("out_dir", ""))}</code></div>
    <div><b>Count</b>: <code>{_fmt(config.get("count", ""))}</code> &nbsp; <b>Seed</b>: <code>{_fmt(config.get("seed", ""))}</code></div>
    <div><b>Threat</b>: <code>{_fmt(config.get("threat_level", ""))}</code></div>
  </div>

  <div class="card">
    <h2 style="margin-top:0">Dataset Summary</h2>
    {maybe_table(dataset_df, "No dataset summary available")}
  </div>

  <div class="card" style="margin-top:14px">
    <h2 style="margin-top:0">Mode Summary</h2>
    {maybe_table(mode_summary_df, "No mode summary available")}
  </div>

  <div class="card" style="margin-top:14px">
    <h2 style="margin-top:0">Sensitivity Distribution (unique images)</h2>
    {maybe_table(sensitivity_df, "No sensitivity distribution available")}
  </div>

  <div class="card" style="margin-top:14px">
    <h2 style="margin-top:0">Encryption Profile Distribution (unique images)</h2>
    {maybe_table(profile_df, "No profile distribution available")}
  </div>

  <div class="card" style="margin-top:14px">
    <h2 style="margin-top:0">Sensitivity vs Profile (unique images)</h2>
    {maybe_table(crosstab_df, "No crosstab available")}
  </div>

  <div class="card" style="margin-top:14px">
    <h2 style="margin-top:0">Unique Images (no 100x3 repetition)</h2>
    <div class="scroll">{maybe_table(unique_table_df, "No unique image table available")}</div>
  </div>

  <h2>Plots</h2>
  <div class="grid">
    {html_images}
  </div>
</body>
</html>
"""


def write_batch_report(batch_results: dict[str, Any], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    report_dir = out_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    items = batch_results.get("items", []) or []
    df = pd.json_normalize(items, sep="__")
    if df.empty:
        raise ValueError("No batch items found in results.")

    # Summary table (recompute from df to ensure consistency).
    summary_rows: list[dict[str, Any]] = []
    for mode, group in df.groupby("mode", dropna=False):
        mode = str(mode)
        row: dict[str, Any] = {
            "mode": mode,
            "count": int(len(group)),
            "exact_match_rate": float(group.get("exact_match", 0).mean()),
            "encrypt_time_ms_mean": float(group.get("encrypt_time_ms", 0).mean()),
            "decrypt_time_ms_mean": float(group.get("decrypt_time_ms", 0).mean()),
            "cipher_entropy_mean": float(group.get("cipher_entropy", 0).mean()),
            "cipher_adj_corr_abs_mean": float(group.get("cipher_adj_corr", 0).abs().mean()),
            "cipher_size_bytes_mean": float(group.get("cipher_size_bytes", 0).mean()),
        }
        if "chosen_plaintext_npcr" in group:
            row["chosen_plaintext_npcr_mean"] = float(group["chosen_plaintext_npcr"].mean())
        if "chosen_plaintext_uaci" in group:
            row["chosen_plaintext_uaci_mean"] = float(group["chosen_plaintext_uaci"].mean())
        summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows).set_index("mode")
    preferred = ["passphrase_only", "x25519_only", "hybrid"]
    ordered = [m for m in preferred if m in summary_df.index] + [m for m in summary_df.index if m not in preferred]
    summary_df = summary_df.loc[ordered]

    summary_df.to_csv(report_dir / "mode_summary.csv")
    _save_table_image(summary_df, "Mode Summary", report_dir / "mode_summary_table.png")

    # Dataset summary + unique-image analysis (avoid repeating 100x3).
    if "image_id" not in df.columns and "enc_path" in df.columns:
        df["image_id"] = df["enc_path"].map(lambda p: Path(str(p)).stem)
    if "input_name" not in df.columns and "input_path" in df.columns:
        df["input_name"] = df["input_path"].map(lambda p: Path(str(p)).name)

    unique_df = df[df.get("mode") == "passphrase_only"].copy()
    if unique_df.empty and "image_id" in df.columns:
        unique_df = df.drop_duplicates(subset=["image_id"]).copy()

    dataset_rows: list[dict[str, Any]] = []
    unique_count = int(unique_df["image_id"].nunique()) if ("image_id" in unique_df.columns and not unique_df.empty) else 0
    dataset_rows.append({"metric": "unique_images", "value": unique_count})
    for mode in ordered:
        dataset_rows.append({"metric": f"pairs_{mode}", "value": int((df["mode"] == mode).sum())})
    dataset_rows.append({"metric": "total_pairs", "value": int(len(df))})
    dataset_rows.append({"metric": "total_output_files_estimate", "value": int(len(df) * 2)})
    dataset_df = pd.DataFrame(dataset_rows).set_index("metric")
    dataset_df.to_csv(report_dir / "dataset_summary.csv")
    _save_table_image(dataset_df, "Dataset Summary", report_dir / "dataset_summary_table.png")

    def load_meta_fields(meta_path: str) -> dict[str, Any]:
        try:
            data = json.loads(Path(str(meta_path)).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
        classification = data.get("classification", {}) or {}
        metrics = classification.get("metrics", {}) or {}
        profile = data.get("profile", {}) or {}
        return {
            "classification_label": str(classification.get("label", "")),
            "classification_score": float(classification.get("score", 0.0) or 0.0),
            "classification_entropy": float(metrics.get("entropy", 0.0) or 0.0),
            "classification_edge_density": float(metrics.get("edge_density", 0.0) or 0.0),
            "classification_variance_norm": float(metrics.get("variance_norm", 0.0) or 0.0),
            "profile_name": str(profile.get("name", "")),
            "profile_permutation_rounds": int(profile.get("permutation_rounds", 0) or 0),
            "profile_arnold_iterations": int(profile.get("arnold_iterations", 0) or 0),
        }

    needed_cols = [
        "classification_label",
        "classification_score",
        "profile_name",
        "profile_permutation_rounds",
        "profile_arnold_iterations",
    ]
    if not unique_df.empty and "meta_path" in unique_df.columns:
        missing = [c for c in needed_cols if c not in unique_df.columns]
        if missing:
            for col in missing:
                unique_df[col] = ""
        # Fill missing/empty values from metadata.
        for idx, row in unique_df.iterrows():
            if all(str(row.get(c, "")).strip() for c in needed_cols):
                continue
            fields = load_meta_fields(str(row.get("meta_path", "")))
            for k, v in fields.items():
                if k in unique_df.columns and (pd.isna(unique_df.at[idx, k]) or str(unique_df.at[idx, k]).strip() == ""):
                    unique_df.at[idx, k] = v

    unique_table_cols = [
        "image_id",
        "input_name",
        "classification_label",
        "classification_score",
        "profile_name",
        "profile_permutation_rounds",
        "profile_arnold_iterations",
    ]
    unique_table = unique_df[[c for c in unique_table_cols if c in unique_df.columns]].copy() if not unique_df.empty else pd.DataFrame()
    if not unique_table.empty:
        unique_table.to_csv(report_dir / "unique_images.csv", index=False)
        preview = unique_table.head(25).set_index("image_id")
        _save_table_image(preview, "Unique Images (first 25)", report_dir / "unique_images_table.png")

        sensitivity_counts = unique_table["classification_label"].value_counts().rename("count").to_frame()
        sensitivity_counts.to_csv(report_dir / "sensitivity_counts.csv")
        _save_table_image(sensitivity_counts, "Sensitivity Counts", report_dir / "sensitivity_counts_table.png")
        _save_bar_generic(sensitivity_counts["count"], "Sensitivity Counts", "images", report_dir / "sensitivity_counts.png", color="#72B7B2")
        _save_pie(sensitivity_counts["count"], "Sensitivity Share", report_dir / "sensitivity_share_pie.png")

        profile_counts = unique_table["profile_name"].value_counts().rename("count").to_frame()
        profile_counts.to_csv(report_dir / "profile_counts.csv")
        _save_table_image(profile_counts, "Profile Counts", report_dir / "profile_counts_table.png")
        _save_bar_generic(profile_counts["count"], "Profile Counts", "images", report_dir / "profile_counts.png", color="#F58518")
        _save_pie(profile_counts["count"], "Profile Share", report_dir / "profile_share_pie.png")

        crosstab = pd.crosstab(unique_table["classification_label"], unique_table["profile_name"])
        crosstab.to_csv(report_dir / "sensitivity_profile_crosstab.csv")
        _save_table_image(crosstab, "Sensitivity vs Profile", report_dir / "sensitivity_profile_crosstab_table.png")
    else:
        sensitivity_counts = pd.DataFrame()
        profile_counts = pd.DataFrame()
        crosstab = pd.DataFrame()
        preview = pd.DataFrame()

    # Core mean metrics.
    _save_bar(summary_df["cipher_entropy_mean"], "Mean Cipher Entropy", "bits", report_dir / "mean_entropy.png")
    _save_bar(
        summary_df["cipher_adj_corr_abs_mean"],
        "Mean |Adjacent Correlation| (cipher bytes)",
        "|corr|",
        report_dir / "mean_abs_corr.png",
    )
    _save_bar(
        summary_df["encrypt_time_ms_mean"],
        "Mean Encryption Time",
        "ms",
        report_dir / "mean_encrypt_time_ms.png",
    )
    _save_bar(
        summary_df["decrypt_time_ms_mean"],
        "Mean Decryption Time",
        "ms",
        report_dir / "mean_decrypt_time_ms.png",
    )

    if "chosen_plaintext_npcr_mean" in summary_df.columns:
        _save_bar(
            summary_df["chosen_plaintext_npcr_mean"],
            "Chosen Plaintext (1-pixel) Mean NPCR",
            "NPCR (%)",
            report_dir / "mean_chosen_plaintext_npcr.png",
        )
    if "chosen_plaintext_uaci_mean" in summary_df.columns:
        _save_bar(
            summary_df["chosen_plaintext_uaci_mean"],
            "Chosen Plaintext (1-pixel) Mean UACI",
            "UACI (%)",
            report_dir / "mean_chosen_plaintext_uaci.png",
        )

    # Attack success rates (decrypt success) + detection rates (1 - success).
    attack_cols = [c for c in df.columns if c.startswith("attack_resilience__")]
    if attack_cols:
        attack_success = df.groupby("mode")[attack_cols].mean()
        attack_success = attack_success.loc[[m for m in ordered if m in attack_success.index]]
        attack_success.to_csv(report_dir / "attack_success_rates.csv")
        attack_success_table = attack_success.T.copy()
        attack_success_table.index = [str(i).replace("attack_resilience__", "") for i in attack_success_table.index]
        _save_table_image(
            attack_success_table,
            "Attack Decrypt-Success Rates (lower is better)",
            report_dir / "attack_success_rates_table.png",
        )

        attack_detect = (1.0 - attack_success).clip(lower=0.0, upper=1.0) * 100.0
        attack_detect.to_csv(report_dir / "attack_detection_rates.csv")
        _save_bar(
            attack_detect.mean(axis=1),
            "Attack Tamper-Detection (mean %) (higher is better)",
            "%",
            report_dir / "attack_detection_mean.png",
        )

    meta_cols = [c for c in df.columns if c.startswith("metadata_tamper_suite__")]
    if meta_cols:
        meta_success = df.groupby("mode")[meta_cols].mean()
        meta_success = meta_success.loc[[m for m in ordered if m in meta_success.index]]
        meta_success.to_csv(report_dir / "metadata_tamper_success_rates.csv")
        meta_success_table = meta_success.T.copy()
        meta_success_table.index = [str(i).replace("metadata_tamper_suite__", "") for i in meta_success_table.index]
        _save_table_image(
            meta_success_table,
            "Metadata Tamper Decrypt-Success Rates (lower is better)",
            report_dir / "metadata_tamper_success_rates_table.png",
        )

        meta_detect = (1.0 - meta_success).clip(lower=0.0, upper=1.0) * 100.0
        meta_detect.to_csv(report_dir / "metadata_tamper_detection_rates.csv")
        _save_bar(
            meta_detect.mean(axis=1),
            "Metadata Tamper-Detection (mean %) (higher is better)",
            "%",
            report_dir / "metadata_tamper_detection_mean.png",
        )

    # Distributions.
    for col, name in [
        ("encrypt_time_ms", "Encryption Time Distribution (ms)"),
        ("decrypt_time_ms", "Decryption Time Distribution (ms)"),
        ("cipher_entropy", "Cipher Entropy Distribution"),
        ("chosen_plaintext_npcr", "Chosen Plaintext (1-pixel) NPCR Distribution"),
        ("chosen_plaintext_uaci", "Chosen Plaintext (1-pixel) UACI Distribution"),
    ]:
        if col in df.columns:
            _save_boxplot(df, col, name, report_dir / f"box_{col}.png")

    images = [
        "dataset_summary_table.png",
        "mode_summary_table.png",
        "unique_images_table.png",
        "sensitivity_counts.png",
        "sensitivity_share_pie.png",
        "profile_counts.png",
        "profile_share_pie.png",
        "sensitivity_profile_crosstab_table.png",
        "mean_entropy.png",
        "mean_abs_corr.png",
        "mean_encrypt_time_ms.png",
        "mean_decrypt_time_ms.png",
        "mean_chosen_plaintext_npcr.png",
        "mean_chosen_plaintext_uaci.png",
        "attack_success_rates_table.png",
        "attack_detection_mean.png",
        "metadata_tamper_success_rates_table.png",
        "metadata_tamper_detection_mean.png",
        "box_encrypt_time_ms.png",
        "box_decrypt_time_ms.png",
        "box_cipher_entropy.png",
        "box_chosen_plaintext_npcr.png",
        "box_chosen_plaintext_uaci.png",
    ]
    images = [img for img in images if (report_dir / img).exists()]

    config = batch_results.get("config", {}) or {}
    html = _render_html(
        config,
        summary_df,
        dataset_df,
        sensitivity_counts,
        profile_counts,
        crosstab,
        unique_table,
        images,
    )
    html_path = report_dir / "report.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate aggregated HTML report from batch_results.json")
    parser.add_argument("batch_results_json", help="Path to batch_results.json produced by batch_run.py")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (defaults to batch_results_json parent).",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    results_path = Path(args.batch_results_json)
    if results_path.is_dir():
        # Allow passing either the artifact root or the evaluation directory.
        for candidate in (
            results_path / "batch_results.json",
            results_path / "evaluation" / "batch_results.json",
        ):
            if candidate.exists():
                results_path = candidate
                break

    if not results_path.exists():
        print(f"ERROR: batch_results.json not found: {results_path}")
        print(f"CWD: {Path.cwd()}")
        artifacts_root = Path("artifacts")
        if artifacts_root.exists():
            found = sorted(artifacts_root.rglob("batch_results.json"))
            if found:
                print("Found these batch_results.json files under ./artifacts:")
                for path in found[:20]:
                    print(f"  - {path}")
        print("Tip: pass --out-dir to control where report files are written.")
        raise SystemExit(2)

    out_dir = Path(args.out_dir) if args.out_dir else results_path.parent
    results = json.loads(results_path.read_text(encoding="utf-8"))
    html_path = write_batch_report(results, out_dir)
    print(str(html_path))


if __name__ == "__main__":
    main()
