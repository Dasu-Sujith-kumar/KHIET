# Hybrid Image Encryption (Security-Engineering Focus)

This project is a security-engineered hybrid image-protection framework, not a new cipher proposal.

## Claim Boundary

This implementation does **not** claim:

- a new cryptographic primitive
- a modification to AES
- that chaos is stronger than AES

It **does** claim:

- domain-separated key derivation
- image-bound key and nonce context
- authenticated metadata
- optional X25519 key exchange
- an adaptive layer that now uses a finetuned Random Forest model with heuristic fallback
- reproducible evaluation outputs

## Hardened Architecture

```text
Input Image
  -> Adaptive Classifier (Random Forest or heuristic fallback)
  -> Security Profile Selection
  -> SHA-256(image || shape || dtype)
  -> Passphrase and/or X25519 shared secret
  -> HKDF-based master derivation
  -> Domain-separated keys: K_AES, K_Nonce, K_Chaos, K_Metadata
  -> Keyed permutation (+ optional Arnold map)
  -> AES-256-GCM payload encryption
  -> HMAC-authenticated metadata
```

## Key Roles

- `K1` (`aes_key`): AES-GCM payload protection
- `K2` (`nonce_key`): nonce derivation
- `K3` (`chaos_key`): chaos seed derivation
- `K4` (`metadata_key`): metadata HMAC authentication

Nonce derivation:

- `nonce = HMAC-SHA256(K2, nonce_salt || deterministic_context)[:12]`

## Key Exchange Modes

- `passphrase_only`
- `x25519_only`
- `hybrid_passphrase_x25519`

## Adaptive ML Layer

The current adaptive classifier tries to load:

- `adaptive_rf_report/adaptive_random_forest_cap200.pkl`

If that model is not available, the pipeline falls back to the earlier heuristic classifier so the encryption path still works.

The best current finetuning run used:

- `200` faces
- `50` forms
- `200` land-scapes and others
- `16` manga
- `200` medical

and achieved:

- `97.60%` holdout accuracy
- `98.45%` best CV score

## Installation

```bash
pip install -r requirements.txt
```

Current requirements include:

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

## CLI Usage

Passphrase only:

```bash
python main.py encrypt --input sample.png --output out/sample.enc --metadata out/sample.meta.json --passphrase "p@ss"
python main.py decrypt --input out/sample.enc --output out/sample.dec.png --metadata out/sample.meta.json --passphrase "p@ss"
```

X25519 only:

```bash
python key_manager.py x25519 --private keys/recipient_private.pem --public keys/recipient_public.pem
python main.py encrypt --input sample.png --output out/sample.enc --metadata out/sample.meta.json --recipient-public-key keys/recipient_public.pem
python main.py decrypt --input out/sample.enc --output out/sample.dec.png --metadata out/sample.meta.json --recipient-private-key keys/recipient_private.pem
```

Hybrid mode:

```bash
python main.py encrypt --input sample.png --output out/sample.enc --metadata out/sample.meta.json --passphrase "p@ss" --recipient-public-key keys/recipient_public.pem
python main.py decrypt --input out/sample.enc --output out/sample.dec.png --metadata out/sample.meta.json --passphrase "p@ss" --recipient-private-key keys/recipient_private.pem
```

## UI

```bash
streamlit run encrypt_app.py
streamlit run decrypt_app.py
```

## Finetune the Adaptive Model

Train the Random Forest and export medical DICOM slices to PNG:

```bash
python train_adaptive_random_forest.py --data-root sample-images --output-model adaptive_rf_report/adaptive_random_forest_cap200.pkl --report-dir adaptive_rf_report_cap200 --samples-per-class 200 --sampling-strategy up_to_limit --export-medical-png
```

Generate the finetuning report and graphs:

```bash
python evaluation/model_finetuning_reporting.py
```

Main outputs:

- `ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md`
- `adaptive_model_finetuning_report/`

## Evaluation / Ablation

Single-image ablation:

```bash
python evaluate_pipeline.py sample.png --passphrase "p@ss" --out-dir artifacts/eval --attack-suite high --report
```

Batch pipeline evaluation:

```bash
python batch_run.py pipeline_eval_input_ml_cap200_test --out-dir ml_pipeline_eval_run --count 167 --passphrase "codex-demo-passphrase" --threat balanced --report --overwrite
```

Main batch outputs:

- `ml_pipeline_eval_run/evaluation/batch_results.json`
- `ml_pipeline_eval_run/evaluation/batch_results.csv`
- `ml_pipeline_eval_run/evaluation/report/report.html`

## Current Batch Rerun Snapshot

The latest ML-backed rerun in this workspace used `167` held-out images and produced `501` evaluated pairs.

Key results:

- exact reconstruction rate: `1.0` in all three modes
- mean ciphertext entropy: about `7.99953`
- mean absolute adjacent correlation: about `0.0010`
- mean chosen-plaintext NPCR: about `99.61%`
- mean chosen-plaintext UACI: about `33.46%`
- all implemented ciphertext, replay, credential-mismatch, and metadata-tamper checks had `0.0` decrypt-success rate

## Security Mapping

- payload confidentiality/integrity -> AES-GCM assumptions
- key exchange hardness -> X25519 assumptions
- KDF separation -> HKDF assumptions
- metadata tamper detection -> HMAC-SHA256 assumptions

## Main Reports

- `ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md`
- `ML_ADAPTIVE_PIPELINE_RERUN_REPORT.md`
- `ATTACK_SIMULATION_AND_EVALUATION_REPORT.md`
- `ATTACKS_AND_GRAPH_EXPLANATION.md`
- `OUTPUT_FOLDERS_AND_RESULTS_INDEX.md`
