# Testing, Entry Points, Commands, and Dataset Guide

## 1. Purpose

This document explains:

- how to start the project
- which files are the main entry points
- how to test the current implementation
- which commands to run
- which datasets and output folders matter now

This guide matches the current codebase as of 2026-04-02.

## 2. Environment Setup

Run all commands from the repository root:

```powershell
cd d:\Downloads\hybrid
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Current package requirements from `requirements.txt`:

- `numpy`
- `opencv-python`
- `cryptography`
- `onnxruntime`
- `streamlit`
- `Pillow`
- `matplotlib`
- `pandas`
- `scikit-learn`
- `pydicom`

## 3. Main Entry Points

### 3.1 CLI Entry Point

File:

- `main.py`

Purpose:

- encrypt an image
- decrypt an encrypted image

Check commands:

```powershell
python main.py --help
python main.py encrypt --help
python main.py decrypt --help
```

### 3.2 Single-Image Evaluation Entry Point

File:

- `evaluate_pipeline.py`

Purpose:

- run ablation and security-engineering evaluation on one image
- generate metrics JSON and optional plots

Check command:

```powershell
python evaluate_pipeline.py --help
```

### 3.3 Batch Encryption + Evaluation Entry Point

File:

- `batch_run.py`

Purpose:

- encrypt a folder of images in 3 modes:
  - `passphrase_only`
  - `x25519_only`
  - `hybrid`
- write 3 output folders with `.enc` + `.meta.json` pairs
- run attacks/evaluation across all pairs
- generate an aggregated HTML report

Check command:

```powershell
python batch_run.py --help
```

### 3.4 Adaptive-Model Training Entry Point

File:

- `train_adaptive_random_forest.py`

Purpose:

- train the Random Forest adaptive classifier
- balance or cap samples per class
- read `medical/*.dcm` files
- optionally export medical DICOM slices to PNG
- write model, manifests, confusion matrix, and metrics

Check command:

```powershell
python train_adaptive_random_forest.py --help
```

### 3.5 Finetuning Report Entry Point

File:

- `evaluation/model_finetuning_reporting.py`

Purpose:

- generate the adaptive-model finetuning graphs
- write `ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md`

Check command:

```powershell
python evaluation/model_finetuning_reporting.py --help
```

### 3.6 Batch Report Regeneration Entry Point

File:

- `evaluation/batch_reporting.py`

Purpose:

- regenerate dataset-level tables, graphs, and HTML from `batch_results.json`

Check command:

```powershell
python evaluation/batch_reporting.py --help
```

### 3.7 Key Management Entry Point

File:

- `key_manager.py`

Purpose:

- create base64 master keys
- create X25519 key pairs

Check command:

```powershell
python key_manager.py --help
python key_manager.py x25519 --help
```

### 3.8 Streamlit Entry Points

Files:

- `encrypt_app.py`
- `decrypt_app.py`

Start commands:

```powershell
streamlit run encrypt_app.py
streamlit run decrypt_app.py
```

## 4. Core Library-Level Entry Points

These are the main callable functions inside the project:

- `pipeline.encrypt.encrypt_array_adaptive`
- `pipeline.encrypt.encrypt_image_adaptive`
- `pipeline.decrypt.decrypt_array_adaptive`
- `pipeline.decrypt.decrypt_image_adaptive`
- `adaptive.classifier.SensitivityClassifier.classify`
- `batch_run.run`
- `evaluate_pipeline.run`
- `key_manager.create_x25519_keypair`

## 5. Datasets and Input Folders That Matter Now

### 5.1 Minimal Runtime Input

For encryption/decryption testing, one readable image file is enough.

Supported practical input formats:

- `.png`
- `.jpg`
- `.jpeg`
- `.bmp`
- `.webp`

Quick smoke-test image already in the workspace:

- `artifacts\eval_smoke\input.png`

### 5.2 Adaptive-Model Training Dataset

Main training root:

- `sample-images\`

Expected structure:

- one top-level folder per class
- current classes include:
  - `faces`
  - `forms`
  - `land-scapes and others`
  - `manga`
  - `medical`

Important note:

- `medical` can contain `.dcm` files instead of raster images
- the trainer reads those DICOM files directly
- it can also export them as PNG into `adaptive_rf_report\medical_png_export\`

### 5.3 Held-Out Input Used for the Current ML Pipeline Rerun

Current rerun input folder:

- `pipeline_eval_input_ml_cap200_test\`

This folder contains:

- `167` held-out test images copied from the best finetuning run

## 6. Quick Start Commands

### 6.1 Passphrase-Only Encryption

```powershell
python main.py encrypt `
  --input artifacts\eval_smoke\input.png `
  --output artifacts\doc_smoke\out.enc `
  --metadata artifacts\doc_smoke\out.meta.json `
  --passphrase p@ss
```

### 6.2 Passphrase-Only Decryption

```powershell
python main.py decrypt `
  --input artifacts\doc_smoke\out.enc `
  --output artifacts\doc_smoke\out.dec.png `
  --metadata artifacts\doc_smoke\out.meta.json `
  --passphrase p@ss
```

### 6.3 Generate X25519 Keys

```powershell
python key_manager.py x25519 `
  --private artifacts\doc_smoke\priv.pem `
  --public artifacts\doc_smoke\pub.pem
```

### 6.4 Train the Adaptive Random Forest

```powershell
python train_adaptive_random_forest.py `
  --data-root sample-images `
  --output-model adaptive_rf_report\adaptive_random_forest_cap200.pkl `
  --report-dir adaptive_rf_report_cap200 `
  --samples-per-class 200 `
  --sampling-strategy up_to_limit `
  --export-medical-png
```

### 6.5 Generate the Finetuning Report and Graphs

```powershell
python evaluation\model_finetuning_reporting.py
```

Expected outputs:

- `ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md`
- `adaptive_model_finetuning_report\`

### 6.6 Batch ML-Backed Pipeline Rerun

```powershell
python batch_run.py pipeline_eval_input_ml_cap200_test `
  --out-dir ml_pipeline_eval_run `
  --count 167 `
  --passphrase codex-demo-passphrase `
  --threat balanced `
  --report `
  --overwrite
```

Expected outputs:

- `ml_pipeline_eval_run\evaluation\batch_results.json`
- `ml_pipeline_eval_run\evaluation\batch_results.csv`
- `ml_pipeline_eval_run\evaluation\report\report.html`

## 7. What Was Verified in This Workspace

The following paths are already present and usable in this workspace:

- CLI encryption/decryption
- X25519 key generation
- single-image evaluation runner
- Random Forest adaptive-model training outputs
- finetuning graphs and report
- ML-backed batch pipeline rerun outputs

## 8. How to Test the Project Properly

There is currently **no dedicated `pytest` suite** in the repository.

The current testing approach is mainly:

- CLI smoke testing
- UI manual testing
- evaluation-runner validation
- batch tamper/attack validation
- adaptive-model finetuning validation

### 8.1 Functional Smoke Tests

Run these first:

1. Encrypt and decrypt in `passphrase_only` mode.
2. Encrypt and decrypt in `x25519_only` mode.
3. Encrypt and decrypt in `hybrid_passphrase_x25519` mode.
4. Run `evaluate_pipeline.py`.

Success criteria:

- encryption writes `.enc` and `.meta.json`
- decryption writes a valid image
- decrypt returns status `ok`
- evaluation writes `evaluation_results.json`

### 8.2 Adaptive-Model Tests

Run these:

1. `train_adaptive_random_forest.py`
2. `evaluation/model_finetuning_reporting.py`

Success criteria:

- model pickle is written
- `metrics.json` exists
- `sample_manifest.csv` exists
- confusion matrix and feature importances are written
- finetuning graphs are created

### 8.3 Batch Security-Oriented Tests

Run `batch_run.py` with `--report`.

Success criteria:

- all three mode folders are created
- `batch_results.json` and `batch_results.csv` are written
- `report/report.html` is written
- untampered decryptions are exact
- attack success rates remain `0.0`
- metadata tamper success rates remain `0.0`

### 8.4 Manual UI Tests

Start:

```powershell
streamlit run encrypt_app.py
streamlit run decrypt_app.py
```

Manual checks:

- upload an image and encrypt it
- confirm metadata downloads correctly
- decrypt using the generated metadata and keys
- verify UI warnings change when key mode changes
- verify X25519 mode asks for PEM material

## 9. What the Evaluation Paths Measure

### 9.1 `evaluate_pipeline.py`

Produces:

- entropy
- adjacent correlation
- NPCR
- UACI
- key sensitivity
- PSNR
- MSE
- execution time
- peak memory
- basic attack outcomes
- ablation across:
  - `aes_only`
  - `static_chaos_aes`
  - `proposed_hardened`

### 9.2 `batch_run.py`

Produces:

- dataset-level exact-match rates
- per-mode timing
- ciphertext entropy and correlation
- chosen-plaintext NPCR/UACI
- replay and corruption attack rejection
- wrong-credential rejection
- metadata-tamper rejection
- CSV tables, PNG charts, and HTML report

Important interpretation note:

- the attack checks test tamper detection and rejection behavior
- under AES-GCM, decryption failure after tampering is expected

## 10. Best Order for Testing

Use this order:

1. Install dependencies.
2. Run passphrase-only smoke test.
3. Generate X25519 keys.
4. Run X25519-only smoke test.
5. Run hybrid smoke test.
6. Run the single-image evaluation harness.
7. Run adaptive-model training.
8. Generate finetuning graphs.
9. Run the batch ML-backed pipeline evaluation.
10. Run Streamlit UI tests if needed.

## 11. Current Gaps in Testing

The project still needs:

- automated unit tests
- repeated benchmark runs with confidence intervals
- series-aware medical splits
- heuristic-vs-ML adaptive ablation inside one scripted benchmark
- automated external baseline comparison

## 12. Short Honest Summary

The project is runnable now from CLI and Streamlit entry points.

For quick smoke tests, `artifacts\eval_smoke\input.png` is enough.

For adaptive-model work, use `sample-images\`.

For the current ML-backed rerun, use `pipeline_eval_input_ml_cap200_test\`.
