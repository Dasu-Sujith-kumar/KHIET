# Code File Main Functions

This document explains what each Python file mainly does in the current codebase.
It is a navigation guide, not a line-by-line reference.

## End-to-End Flows

Main runtime path:

`main.py` or Streamlit app -> `pipeline/encrypt.py` / `pipeline/decrypt.py` -> `adaptive/*` + `chaso/*` + `crypto/*` + `pipeline/metadata_io.py`

Batch evaluation path:

`batch_run.py` -> `evaluation/attacks.py` + `evaluation/batch_reporting.py` + pipeline helpers

Adaptive-model training path:

`train_adaptive_random_forest.py` -> `adaptive_rf_report*` -> `evaluation/model_finetuning_reporting.py` -> `adaptive/classifier.py`

## Top-Level Scripts

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `main.py` | CLI entrypoint for encryption and decryption. Parses arguments, builds security-context metadata, and calls the adaptive pipeline. | `_build_parser()`, `main()` |
| `encrypt_app.py` | Streamlit UI for encrypting images. Handles uploads, passphrase/X25519 options, artifact naming, and downloads. | `_save_uploaded_image()`, `_artifact_paths()`, `_resolve_pem_input()`, `_render_encrypt_result()`, `main()` |
| `decrypt_app.py` | Streamlit UI for decrypting encrypted payloads using metadata and credentials. | `_write_temp()`, `_output_image_path()`, `_resolve_pem_input()`, `_parse_metadata_preview()`, `_expected_key_exchange_mode()`, `_render_decrypt_result()`, `main()` |
| `evaluate_pipeline.py` | Single-image ablation/evaluation runner. Compares `aes_only`, `static_chaos_aes`, and `proposed_hardened`, then writes metrics, timing, memory, and attack results. | `_variant_aes_only()`, `_variant_static_chaos_aes()`, `_variant_proposed_hardened()`, `_build_metrics_block()`, `run()`, `main()` |
| `batch_run.py` | Batch runner that encrypts a folder of images in 3 key-exchange modes, evaluates attacks/metrics across all outputs, and optionally writes an aggregated HTML report. | `run()`, `main()` |
| `train_adaptive_random_forest.py` | Builds the adaptive-layer dataset from class folders, handles DICOM input, exports medical PNG slices when requested, tunes a Random Forest, and writes manifests/metrics/models. | `_export_dicom_tree_to_png()`, `_build_dataset()`, `_train_model()`, `main()` |
| `key_manager.py` | Utility script for generating symmetric master keys and X25519 key pairs. | `write_key_file()`, `read_key_file()`, `create_master_key_file()`, `create_x25519_keypair()`, `main()` |

## Adaptive Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `adaptive/classifier.py` | ML-first sensitivity classifier. Loads the finetuned Random Forest model when available, predicts class probabilities, maps them into `low` / `medium` / `high`, and falls back to the old heuristic if the model is missing. | `ClassificationResult`, `SensitivityClassifier.classify()`, `_classify_ml()`, `_classify_heuristic()` |
| `adaptive/policy.py` | Maps sensitivity output and threat level to one runtime security profile: `lite`, `standard`, or `max`. | `SecurityProfile`, `select_security_profile()` |
| `adaptive/__init__.py` | Package export file for the adaptive API. | `ClassificationResult`, `SensitivityClassifier`, `SecurityProfile`, `select_security_profile` |

## Chaos / Transform Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `chaso/arnold_map.py` | Reversible Arnold cat map for square images. Used as an optional scrambling stage before AES encryption. | `arnold_map()`, `inverse_arnold_map()`, `_validate_square_image()` |
| `chaso/keyed_permutation.py` | Deterministic keyed permutation over flattened image data. Also derives the integer chaos seed from key material. | `derive_chaos_seed()`, `adaptive_permute()`, `inverse_adaptive_permute()`, `_round_seed()` |
| `chaso/__init__.py` | Package export file for transform helpers. | `arnold_map`, `inverse_arnold_map`, `adaptive_permute`, `inverse_adaptive_permute`, `derive_chaos_seed` |

## Cryptography Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `crypto/aes_gcm.py` | AES-GCM helpers plus deterministic nonce derivation from a dedicated nonce key and nonce salt. | `derive_gcm_nonce()`, `encrypt_aes()`, `decrypt_aes()` |
| `crypto/key_schedule.py` | Key derivation core. Builds the master key from passphrase and/or shared secret plus image digest, then expands it into domain-separated subkeys for AES, nonce, chaos, and metadata MAC. | `DerivedKeys`, `generate_master_key()`, `generate_kdf_salt()`, `master_key_from_passphrase()`, `derive_master_key_material()`, `derive_subkeys()` |
| `crypto/metadata_auth.py` | Canonicalizes metadata JSON and authenticates it with HMAC-SHA256. | `sign_metadata()`, `verify_metadata()`, `_canonical_metadata_bytes()` |
| `crypto/ecc_keywrap.py` | X25519 helpers for optional public-key support. Generates keys and derives shared secrets used by the pipeline. | `generate_keys()`, `wrap_key()`, `unwrap_key()`, `derive_x25519_shared_secret()`, `_derive_wrap_key()` |
| `crypto/__init__.py` | Package export file for crypto helpers. | Re-exports AES, KDF, and X25519 helpers |

## Pipeline Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `pipeline/adaptive_common.py` | Shared pipeline utilities: base64 conversion, image load/save, square padding, unpadding, and image digest generation. | `b64_encode_bytes()`, `b64_decode_bytes()`, `load_image()`, `save_image()`, `pad_to_square()`, `unpad_from_square()`, `image_sha256_digest()` |
| `pipeline/encrypt.py` | Core adaptive encryption pipeline. Classifies the image, selects the profile, derives keys, applies Arnold/permutation transforms, encrypts with AES-GCM, then builds and signs metadata. | `encrypt_array_adaptive()`, `encrypt_image_adaptive()`, `encrypt_image()`, `_derive_shared_secret()`, `_build_metadata()`, `_nonce_context()`, `_aad()` |
| `pipeline/decrypt.py` | Core adaptive decryption pipeline. Re-derives keys from metadata and credentials, verifies metadata HMAC, decrypts AES-GCM payload, reverses the transforms, and restores the image. | `decrypt_array_adaptive()`, `decrypt_image_adaptive()`, `decrypt_image()`, `_shared_secret_from_metadata()`, `_verify_metadata()`, `_nonce_context()`, `_aad()` |
| `pipeline/metadata_io.py` | Reads, validates, and writes metadata JSON files used by the pipeline. | `validate_metadata()`, `write_metadata()`, `read_metadata()` |
| `pipeline/__init__.py` | Package export file for pipeline entrypoints. | `encrypt_array_adaptive`, `encrypt_image`, `encrypt_image_adaptive`, `decrypt_array_adaptive`, `decrypt_image`, `decrypt_image_adaptive` |

## Evaluation Package

| File | Main responsibility | Main functions/classes |
| --- | --- | --- |
| `evaluation/metrics.py` | Quantitative metrics used in the project: entropy, NPCR, UACI, PSNR, MSE, adjacent correlation, and key sensitivity. | `shannon_entropy()`, `npcr()`, `uaci()`, `psnr()`, `mse()`, `adjacent_correlation()`, `key_sensitivity()` |
| `evaluation/attacks.py` | Perturbation helpers used during robustness/tamper checks. | `flip_random_bit()`, `add_gaussian_noise_to_bytes()`, `mutate_random_bytes()`, `shuffle_blocks()`, `truncate_bytes()` |
| `evaluation/reporting.py` | Generates plots + an HTML report from `evaluate_pipeline.py` results. | `write_evaluation_report()`, `main()` |
| `evaluation/batch_reporting.py` | Generates dataset-level CSV tables, plots, and HTML reports from `batch_run.py` outputs. | `write_batch_report()`, `main()` |
| `evaluation/model_finetuning_reporting.py` | Generates the finetuning graphs and `ML_ADAPTIVE_MODEL_FINETUNING_REPORT.md` from the Random Forest experiment folders. | `generate_report()`, `main()` |
| `evaluation/json_utils.py` | Strict-JSON helpers for result files so `NaN` and `Infinity` are serialized safely. | `sanitize_for_json()`, `dumps_strict_json()` |
| `evaluation/__init__.py` | Package export file for evaluation helpers. | Re-exports functions from `metrics.py` and `attacks.py` |

## Which Files Matter Most First

If someone is new to the project, read these first:

1. `main.py`
2. `pipeline/encrypt.py`
3. `pipeline/decrypt.py`
4. `adaptive/classifier.py`
5. `adaptive/policy.py`
6. `crypto/key_schedule.py`
7. `crypto/aes_gcm.py`
8. `batch_run.py`
9. `train_adaptive_random_forest.py`
10. `evaluation/batch_reporting.py`

That order gives the clearest picture of the current system from adaptive classification to encryption, decryption, model training, and report generation.
